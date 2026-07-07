import threading
import time
from datetime import datetime, timezone
import re

from . import config
from .utils import startTracker, startUART, stopUART


class GroundStationController:
    def __init__(self, auto_connect_uart=False, settings=None):
        self.settings = settings or {}
        self._lock = threading.Lock()
        self._tracking_thread = None
        self._tracking_running = False
        self._refresh_rate_hz = float(
            self.settings.get('refresh_rate_hz', config.REFRESH_RATE_HZ)
        )

        self._uart_port = self.settings.get('uart_port', config.UART_PORT)
        self._uart_baudrate = int(
            self.settings.get('uart_baudrate', config.UART_BAUDRATE)
        )
        self._uart_timeout = float(self.settings.get('uart_timeout', 0.5))
        self._feedback_enabled = bool(self.settings.get('feedback_enabled', True))

        self.tracker = startTracker(
            config.LATITUDE,
            config.LONGITUDE,
            config.ELEVATION_M,
        )
        self.uart = None

        self.state = {
            'mode': 'idle',
            'satellite_name': None,
            'target_azimuth': None,
            'target_elevation': None,
            'actual_azimuth': None,
            'actual_elevation': None,
            'distance_km': None,
            'is_visible': False,
            'uart_connected': False,
            'uart_port': self._uart_port,
            'feedback_enabled': self._feedback_enabled,
            'fault_state': None,
            'last_rx_utc': None,
            'last_rx_raw': None,
            'last_error': None,
            'last_tx_utc': None,
            'last_update_utc': None,
        }

        if auto_connect_uart:
            self.connect_uart()

    def connect_uart(self):
        with self._lock:
            if self.uart is not None:
                self.state['uart_connected'] = True
                return True, 'UART already connected'
            try:
                self.uart = startUART(
                    port=self._uart_port,
                    baudrate=self._uart_baudrate,
                    timeout=self._uart_timeout,
                )
                if self.uart is None:
                    raise RuntimeError('Failed to initialize UART')
                self.uart.clear_input_buffer()
                if self._feedback_enabled:
                    self.uart.start_rx_loop(
                        self._handle_feedback_line,
                        thread_name='uart-feedback-rx',
                    )
                self.state['uart_connected'] = True
                self.state['last_error'] = None
                return True, 'UART connected'
            except Exception as exc:
                self.uart = None
                self.state['uart_connected'] = False
                self.state['last_error'] = str(exc)
                return False, str(exc)

    def disconnect_uart(self):
        with self._lock:
            if self.uart is not None:
                try:
                    stopUART(self.uart)
                except Exception as exc:
                    self.state['last_error'] = str(exc)
                self.uart = None
            self.state['uart_connected'] = False
            return True, 'UART disconnected'

    @staticmethod
    def _parse_feedback_line(line):
        """Parse STM32 feedback lines into partial state fields.

        Accepted loose formats include examples like:
        - "AZ123.4 EL056.7"
        - "ACT_AZ=123.4 ACT_EL=56.7"
        - "ERR:OVERCURRENT"
        - "STATE:TRACKING"
        """
        if not line:
            return {}

        payload = {}

        az_match = re.search(r'(?:ACT_)?AZ\s*[:=]?\s*(-?\d+(?:\.\d+)?)', line, re.IGNORECASE)
        if az_match:
            payload['actual_azimuth'] = round(float(az_match.group(1)), 2)

        el_match = re.search(r'(?:ACT_)?EL\s*[:=]?\s*(-?\d+(?:\.\d+)?)', line, re.IGNORECASE)
        if el_match:
            payload['actual_elevation'] = round(float(el_match.group(1)), 2)

        err_match = re.search(r'(?:ERR|ERROR|FAULT)\s*[:=]\s*([^,;]+)', line, re.IGNORECASE)
        if err_match:
            payload['fault_state'] = err_match.group(1).strip()

        state_match = re.search(r'STATE\s*[:=]\s*([^,;]+)', line, re.IGNORECASE)
        if state_match:
            payload['stm32_state'] = state_match.group(1).strip()

        return payload

    def _handle_feedback_line(self, line):
        parsed = self._parse_feedback_line(line)
        now_iso = datetime.now(timezone.utc).isoformat()

        with self._lock:
            self.state['last_rx_utc'] = now_iso
            self.state['last_rx_raw'] = line
            if parsed:
                self.state.update(parsed)
                if self.state.get('fault_state'):
                    self.state['last_error'] = self.state['fault_state']
                else:
                    self.state['last_error'] = None

    def load_tle(self, name, line1, line2):
        ok = self.tracker.load_tle_from_csv_data(name, line1, line2)
        with self._lock:
            if ok:
                self.state['satellite_name'] = name
                self.state['last_error'] = None
                return True, 'TLE loaded'
            self.state['last_error'] = 'Failed to load TLE'
            return False, 'Failed to load TLE'

    def send_external_target(self, azimuth, elevation):
        with self._lock:
            self.state['mode'] = 'external'
            self.state['target_azimuth'] = azimuth
            self.state['target_elevation'] = elevation
            self.state['last_update_utc'] = datetime.now(timezone.utc).isoformat()

            if self.uart is None:
                self.state['last_error'] = 'UART not connected'
                return False, 'UART not connected'

            try:
                self.uart.send_position(azimuth, elevation)
                self.state['last_tx_utc'] = datetime.now(timezone.utc).isoformat()
                self.state['last_error'] = None
                return True, 'Target sent'
            except Exception as exc:
                self.state['last_error'] = str(exc)
                return False, str(exc)

    def start_standalone_tracking(self, refresh_rate_hz=None):
        with self._lock:
            if self.tracker.satellite is None:
                return False, 'Load TLE first'
            if self._tracking_running:
                return True, 'Standalone tracking already running'

            if refresh_rate_hz is not None:
                self._refresh_rate_hz = max(0.2, float(refresh_rate_hz))

            self._tracking_running = True
            self.state['mode'] = 'standalone'
            self._tracking_thread = threading.Thread(
                target=self._tracking_loop,
                name='standalone-tracking',
                daemon=True,
            )
            self._tracking_thread.start()
            return True, 'Standalone tracking started'

    def stop_standalone_tracking(self):
        with self._lock:
            self._tracking_running = False
            self.state['mode'] = 'idle'
        return True, 'Standalone tracking stopped'

    def _tracking_loop(self):
        while True:
            with self._lock:
                if not self._tracking_running:
                    break
                refresh_hz = self._refresh_rate_hz

            try:
                now_utc = datetime.now(timezone.utc)
                azimuth, elevation, distance_km, is_visible = self.tracker.get_position(now_utc)

                with self._lock:
                    self.state['target_azimuth'] = round(azimuth, 2)
                    self.state['target_elevation'] = round(elevation, 2)
                    self.state['distance_km'] = round(distance_km, 2)
                    self.state['is_visible'] = bool(is_visible)
                    self.state['last_update_utc'] = now_utc.isoformat()

                    if self.uart is not None:
                        self.uart.send_position(azimuth, elevation)
                        self.state['last_tx_utc'] = datetime.now(timezone.utc).isoformat()
                        self.state['last_error'] = None
            except Exception as exc:
                with self._lock:
                    self.state['last_error'] = str(exc)

            sleep_seconds = 1.0 / max(refresh_hz, 0.2)
            time.sleep(sleep_seconds)

    def get_state(self):
        with self._lock:
            state = dict(self.state)
            state['standalone_running'] = self._tracking_running
            az = state.get('target_azimuth')
            el = state.get('target_elevation')
            a_az = state.get('actual_azimuth')
            a_el = state.get('actual_elevation')
            if az is not None and a_az is not None:
                state['azimuth_error'] = round(az - a_az, 2)
            else:
                state['azimuth_error'] = None
            if el is not None and a_el is not None:
                state['elevation_error'] = round(el - a_el, 2)
            else:
                state['elevation_error'] = None
            return state
