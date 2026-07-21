import threading
import time
from datetime import datetime, timedelta, timezone
import re

import serial

try:
    from . import config
    from .utils import startTracker, startUART, stopUART
except ImportError:
    import config
    from utils import startTracker, startUART, stopUART


class GroundStationController:
    #  % ------------------------------------------------------------
    #  % Inputs: Runtime settings (UART, refresh, feedback) plus tracker/UART dependencies from module imports.
    #  % Side-effects: Defines shared ground-station state and methods for UART control, feedback parsing, and tracking loops.
    #  % Returns: The GroundStationController class type used by Browser services and API handlers.
    #  % ------------------------------------------------------------
    def __init__(self, auto_connect_uart=False, settings=None):
        #  % ------------------------------------------------------------
        #  % Inputs: auto_connect_uart flag and optional settings dict with UART/tracking parameters.
        #  % Side-effects: Initializes locks, tracker instance, controller state fields, and optionally opens UART immediately.
        #  % Returns: None; prepares controller object for command/telemetry operations.
        #  % ------------------------------------------------------------
        self.settings = settings or {}
        self._lock = threading.Lock()
        self._tracking_thread = None
        self._tracking_running = False
        self._bridge_thread = None
        self._bridge_running = False
        self._bridge_uart = None
        self._scheduled_start_utc = None
        self._scheduled_source = None
        self._refresh_rate_hz = float(
            self.settings.get('refresh_rate_hz', config.REFRESH_RATE_HZ)
        )

        self._uart_port = self.settings.get('uart_port', config.UART_PORT)
        self._uart_baudrate = int(
            self.settings.get('uart_baudrate', config.UART_BAUDRATE)
        )
        self._uart_timeout = float(self.settings.get('uart_timeout', 0.5))
        self._feedback_enabled = bool(self.settings.get('feedback_enabled', True))
        self._telemetry_enable_delay_s = float(self.settings.get('telemetry_enable_delay_s', 0.1))
        self._bridge_port = self.settings.get('bridge_port', '/dev/ttyGS0')
        self._bridge_timeout = float(self.settings.get('bridge_timeout', 0.1))

        self.tracker = startTracker(
            config.LATITUDE,
            config.LONGITUDE,
            config.ELEVATION_M,
        )
        self.uart = None

        self.state = {
            'mode': 'idle',
            'requested_mode': 'mcs',
            'mode_owner': 'browser',
            'hardware_mode': None,
            'mode_command_utc': datetime.now(timezone.utc).isoformat(),
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
            'bridge_running': False,
            'scheduled_start_utc': None,
            'scheduled_source': None,
        }

        if auto_connect_uart:
            self.connect_uart()

    def connect_uart(self, start_feedback=None):
        #  % ------------------------------------------------------------
        #  % Inputs: Optional start_feedback override controlling whether the Pi parses incoming UART lines.
        #  % Side-effects: Opens serial connection, clears input buffer, may start RX loop callback, and updates state/error fields.
        #  % Returns: Tuple (ok, message) describing UART connection result.
        #  % ------------------------------------------------------------
        with self._lock:
            if self.uart is not None:
                self.state['uart_connected'] = True
                return True, 'UART already connected'
            try:
                if start_feedback is None:
                    start_feedback = self._feedback_enabled
                self.uart = startUART(
                    port=self._uart_port,
                    baudrate=self._uart_baudrate,
                    timeout=self._uart_timeout,
                )
                if self.uart is None:
                    raise RuntimeError('Failed to initialize UART')
                self.uart.clear_input_buffer()
                if start_feedback:
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
        #  % ------------------------------------------------------------
        #  % Inputs: No direct parameters; uses current self.uart instance if connected.
        #  % Side-effects: Stops UART activity, closes serial resources, clears connection flags, and records close errors if any.
        #  % Returns: Tuple (ok, message) describing UART disconnection result.
        #  % ------------------------------------------------------------
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
        #  % ------------------------------------------------------------
        #  % Inputs: line text received from STM32 UART feedback stream.
        #  % Side-effects: Parses regex fields for actual angles, fault text, and STM32 state markers.
        #  % Returns: Dictionary of parsed feedback keys; empty dict when line has no recognized data.
        #  % ------------------------------------------------------------
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

        telemetry_match = re.search(
            r'\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$',
            line,
        )
        if telemetry_match:
            payload['actual_azimuth'] = round(float(telemetry_match.group(1)), 2)
            payload['actual_elevation'] = round(float(telemetry_match.group(2)), 2)
            payload['target_azimuth'] = round(float(telemetry_match.group(3)), 2)
            payload['target_elevation'] = round(float(telemetry_match.group(4)), 2)

        return payload

    def _handle_feedback_line(self, line):
        #  % ------------------------------------------------------------
        #  % Inputs: line text forwarded from the UART RX callback.
        #  % Side-effects: Updates last RX metadata and merges parsed telemetry/fault fields into locked controller state.
        #  % Returns: None; mutates controller state in-place.
        #  % ------------------------------------------------------------
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

    def _set_schedule(self, scheduled_start_utc=None, source=None):
        with self._lock:
            self._scheduled_start_utc = scheduled_start_utc
            self._scheduled_source = source
            self.state['scheduled_start_utc'] = scheduled_start_utc
            self.state['scheduled_source'] = source

    def set_mode_command(self, mode, owner='browser', hardware_mode=None):
        #  % ------------------------------------------------------------
        #  % Inputs: Requested mode (`mcs` or `standalone`), ownership source, and optional hardware mode snapshot.
        #  % Side-effects: Updates mode arbitration fields used by the runtime control loop and dashboard UI.
        #  % Returns: Tuple (ok, message) describing command acceptance.
        #  % ------------------------------------------------------------
        mode = str(mode or '').strip().lower()
        owner = str(owner or 'browser').strip().lower()
        hardware_mode = str(hardware_mode or '').strip().lower() or None

        if mode not in ('mcs', 'standalone'):
            return False, 'mode must be mcs or standalone'
        if owner not in ('browser', 'hardware'):
            return False, 'owner must be browser or hardware'
        if hardware_mode is not None and hardware_mode not in ('mcs', 'standalone'):
            return False, 'hardware_mode must be mcs or standalone'

        with self._lock:
            self.state['requested_mode'] = mode
            self.state['mode_owner'] = owner
            if hardware_mode is not None:
                self.state['hardware_mode'] = hardware_mode
            elif owner == 'hardware':
                self.state['hardware_mode'] = mode
            self.state['mode_command_utc'] = datetime.now(timezone.utc).isoformat()

        return True, f'{owner} requested {mode}'

    def _open_bridge_uart(self):
        if self._bridge_uart is not None:
            return self._bridge_uart
        self._bridge_uart = serial.Serial(self._bridge_port, baudrate=self._uart_baudrate, timeout=self._bridge_timeout)
        return self._bridge_uart

    def _close_bridge_uart(self):
        if self._bridge_uart is not None:
            try:
                self._bridge_uart.close()
            except Exception:
                pass
            self._bridge_uart = None

    def start_computer_bridge(self, bridge_port=None):
        #  % ------------------------------------------------------------
        #  % Inputs: Optional USB bridge serial port.
        #  % Side-effects: Opens the USB-side serial device and starts a raw byte relay thread.
        #  % Returns: Tuple (ok, message) describing bridge startup state.
        #  % ------------------------------------------------------------
        with self._lock:
            if bridge_port:
                self._bridge_port = bridge_port
            if self._bridge_running:
                return True, 'Computer bridge already running'
            if self.uart is None:
                ok, message = self.connect_uart(start_feedback=False)
                if not ok:
                    return False, message

            try:
                self._open_bridge_uart()
            except Exception as exc:
                self.state['last_error'] = str(exc)
                return False, str(exc)

            self._bridge_running = True
            self.state['mode'] = 'computer'
            self.state['bridge_running'] = True
            self._bridge_thread = threading.Thread(target=self._bridge_loop, name='computer-bridge', daemon=True)
            self._bridge_thread.start()
            return True, 'Computer bridge started'

    def stop_computer_bridge(self):
        #  % ------------------------------------------------------------
        #  % Inputs: No direct parameters.
        #  % Side-effects: Stops the raw bridge and closes the USB-side serial port.
        #  % Returns: Tuple (ok, message) describing bridge shutdown.
        #  % ------------------------------------------------------------
        with self._lock:
            self._bridge_running = False
            self.state['bridge_running'] = False
            if self.state.get('mode') == 'computer':
                self.state['mode'] = 'idle'
        self._close_bridge_uart()
        return True, 'Computer bridge stopped'

    def _bridge_loop(self):
        #  % ------------------------------------------------------------
        #  % Inputs: No direct parameters; uses USB bridge UART and STM32 UART state.
        #  % Side-effects: Relays raw bytes in both directions without parsing or reformatting.
        #  % Returns: None; loop exits when bridge flag is cleared.
        #  % ------------------------------------------------------------
        while True:
            with self._lock:
                if not self._bridge_running:
                    break
                uart = self.uart
                bridge_uart = self._bridge_uart

            if uart is None or bridge_uart is None:
                time.sleep(0.05)
                continue

            try:
                if bridge_uart.in_waiting:
                    data = bridge_uart.read(bridge_uart.in_waiting)
                    if data:
                        uart.send_raw_bytes(data)
                        with self._lock:
                            self.state['last_tx_utc'] = datetime.now(timezone.utc).isoformat()

                if uart.in_waiting:
                    data = uart.read_bytes(uart.in_waiting)
                    if data:
                        bridge_uart.write(data)
                        with self._lock:
                            self.state['last_rx_utc'] = datetime.now(timezone.utc).isoformat()
            except Exception as exc:
                with self._lock:
                    self.state['last_error'] = str(exc)
                time.sleep(0.1)

            time.sleep(0.01)

    def load_tle(self, name, line1, line2):
        #  % ------------------------------------------------------------
        #  % Inputs: Satellite name and TLE line1/line2 strings.
        #  % Side-effects: Loads TLE into tracker and updates satellite_name/last_error state fields.
        #  % Returns: Tuple (ok, message) indicating whether TLE load succeeded.
        #  % ------------------------------------------------------------
        ok = self.tracker.load_tle_from_csv_data(name, line1, line2)
        with self._lock:
            if ok:
                self.state['satellite_name'] = name
                self.state['last_error'] = None
                return True, 'TLE loaded'
            self.state['last_error'] = 'Failed to load TLE'
            return False, 'Failed to load TLE'

    def get_next_pass(self, max_search_hours=None, min_elevation_deg=None):
        #  % ------------------------------------------------------------
        #  % Inputs: Optional search horizon and minimum elevation threshold.
        #  % Side-effects: Computes pass prediction from the current tracker state.
        #  % Returns: Tuple (ok, message, payload) with the next pass summary when available.
        #  % ------------------------------------------------------------
        if self.tracker.satellite is None:
            return False, 'Load TLE first', None

        max_search_hours = float(max_search_hours if max_search_hours is not None else config.MAX_SEARCH_HOURS)
        min_elevation_deg = float(min_elevation_deg if min_elevation_deg is not None else 10.0)
        now_utc = datetime.now(timezone.utc)
        t0 = self.tracker.ts.from_datetime(now_utc)
        t1 = self.tracker.ts.from_datetime(now_utc + timedelta(hours=max_search_hours))

        try:
            t_events, events = self.tracker.satellite.find_events(
                self.tracker.observer,
                t0,
                t1,
                altitude_degrees=min_elevation_deg,
            )
        except Exception as exc:
            return False, str(exc), None

        current_pass = None
        for t_event, event in zip(t_events, events):
            event_time = t_event.utc_datetime()
            if event == 0:
                current_pass = {
                    'rise_time': event_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'max_elevation': None,
                    'set_time': None,
                    'duration': None,
                }
            elif event == 1 and current_pass is not None:
                azimuth, elevation, _, _ = self.tracker.get_position(event_time)
                current_pass['max_elevation'] = round(elevation, 1)
                current_pass['peak_azimuth'] = round(azimuth, 1)
            elif event == 2 and current_pass is not None:
                current_pass['set_time'] = event_time.strftime('%Y-%m-%d %H:%M:%S')
                rise_dt = datetime.strptime(current_pass['rise_time'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                current_pass['duration'] = round((event_time - rise_dt).total_seconds() / 60.0, 1)
                return True, 'Next pass computed', current_pass

        return False, 'No upcoming pass found', None

    def send_external_target(self, azimuth, elevation):
        #  % ------------------------------------------------------------
        #  % Inputs: azimuth and elevation target values supplied by external MCS/API requests.
        #  % Side-effects: Stores target fields, attempts UART transmission, and updates tx timestamp/error status.
        #  % Returns: Tuple (ok, message) indicating whether target was accepted/transmitted.
        #  % ------------------------------------------------------------
        with self._lock:
            self.state['mode'] = 'external'
            self.state['target_azimuth'] = azimuth
            self.state['target_elevation'] = elevation
            self.state['last_update_utc'] = datetime.now(timezone.utc).isoformat()

            if self.uart is None:
                self.state['last_error'] = 'UART not connected'
                return False, 'UART not connected'

            try:
                self.uart.send_target_pair(azimuth, elevation)
                self.state['last_tx_utc'] = datetime.now(timezone.utc).isoformat()
                self.state['last_error'] = None
                return True, 'Target sent'
            except Exception as exc:
                self.state['last_error'] = str(exc)
                return False, str(exc)

    def start_standalone_tracking(self, refresh_rate_hz=None):
        #  % ------------------------------------------------------------
        #  % Inputs: Optional refresh_rate_hz override for tracking update cadence.
        #  % Side-effects: Validates tracker readiness, sets mode, starts background tracking thread, and updates run flags.
        #  % Returns: Tuple (ok, message) indicating start result or reason tracking was not started.
        #  % ------------------------------------------------------------
        with self._lock:
            if self.tracker.satellite is None:
                return False, 'Load TLE first'
            if self._tracking_running:
                return True, 'Standalone tracking already running'

            if refresh_rate_hz is not None:
                self._refresh_rate_hz = max(0.2, float(refresh_rate_hz))

            self._tracking_running = True
            self.state['mode'] = 'standalone'
            self.state['bridge_running'] = False
            self._tracking_thread = threading.Thread(
                target=self._tracking_loop,
                name='standalone-tracking',
                daemon=True,
            )
            self._tracking_thread.start()
            try:
                if self.uart is None:
                    self.connect_uart()
                if self.uart is not None:
                    self.uart.send_line('T')
                    time.sleep(self._telemetry_enable_delay_s)
            except Exception as exc:
                self.state['last_error'] = str(exc)
            return True, 'Standalone tracking started'

    def schedule_standalone_tracking(self, start_utc, refresh_rate_hz=None):
        #  % ------------------------------------------------------------
        #  % Inputs: ISO start time and optional refresh rate override.
        #  % Side-effects: Stores a pending standalone tracking start request in controller state.
        #  % Returns: Tuple (ok, message) describing schedule state.
        #  % ------------------------------------------------------------
        if self.tracker.satellite is None:
            return False, 'Load TLE first'
        try:
            start_dt = datetime.fromisoformat(str(start_utc).replace('Z', '+00:00'))
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
        except Exception:
            return False, 'Invalid start time'

        if refresh_rate_hz is not None:
            with self._lock:
                self._refresh_rate_hz = max(0.2, float(refresh_rate_hz))

        self._set_schedule(start_dt.isoformat(), self.tracker.satellite.name)
        with self._lock:
            self.state['mode'] = 'standby'
        return True, f'Standalone tracking scheduled for {start_dt.isoformat()}'

    def stop_standalone_tracking(self):
        #  % ------------------------------------------------------------
        #  % Inputs: No direct parameters.
        #  % Side-effects: Clears tracking run flag and returns controller mode to idle.
        #  % Returns: Tuple (ok, message) confirming standalone tracking stop request.
        #  % ------------------------------------------------------------
        with self._lock:
            self._tracking_running = False
            self.state['mode'] = 'idle'
            self._scheduled_start_utc = None
            self._scheduled_source = None
            self.state['scheduled_start_utc'] = None
            self.state['scheduled_source'] = None
        return True, 'Standalone tracking stopped'

    def _tracking_loop(self):
        #  % ------------------------------------------------------------
        #  % Inputs: No direct parameters; uses tracker, refresh rate, and UART connection state.
        #  % Side-effects: Continuously computes target angles from TLE, updates state, and sends commands while tracking is enabled.
        #  % Returns: None; loop exits when tracking flag is cleared.
        #  % ------------------------------------------------------------
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
                        self.uart.send_target_pair(azimuth, elevation)
                        self.state['last_tx_utc'] = datetime.now(timezone.utc).isoformat()
                        self.state['last_error'] = None
            except Exception as exc:
                with self._lock:
                    self.state['last_error'] = str(exc)

            sleep_seconds = 1.0 / max(refresh_hz, 0.2)
            time.sleep(sleep_seconds)

    def get_state(self):
        #  % ------------------------------------------------------------
        #  % Inputs: No direct parameters.
        #  % Side-effects: Copies state under lock and computes azimuth/elevation error convenience values.
        #  % Returns: Dictionary snapshot of current controller state for API consumers.
        #  % ------------------------------------------------------------
        with self._lock:
            state = dict(self.state)
            state['standalone_running'] = self._tracking_running
            state['bridge_running'] = self._bridge_running
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
