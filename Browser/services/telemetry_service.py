from datetime import datetime, timedelta

from flask import jsonify


class TelemetryService:
    def __init__(self, controller=None, settings=None):
        self.controller = controller
        self.settings = settings or {}

    def _controller_state(self):
        if self.controller is None:
            return {}
        try:
            return self.controller.get_state() or {}
        except Exception:
            return {}

    def system_info(self):
        """Return system information as JSON."""
        import psutil

        return jsonify(
            {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'disk_percent': psutil.disk_usage('/').percent,
                'temperature': self.get_cpu_temperature(),
            }
        )

    def satellite_status(self):
        """Return current satellite tracking status."""
        state = self._controller_state()

        azimuth = state.get('target_azimuth')
        elevation = state.get('target_elevation')
        comm_connected = state.get('uart_connected', False)
        signal_strength = self.settings.get('signal_strength_dbm')
        snr = self.settings.get('snr_db')
        frequency = self.settings.get('frequency_mhz', 145.800)
        data_rate = self.settings.get('data_rate_bps')

        return jsonify(
            {
                'satellite_name': state.get('satellite_name') or 'ISS (ZARYA)',
                'azimuth': azimuth,
                'elevation': elevation,
                'actual_azimuth': state.get('actual_azimuth'),
                'actual_elevation': state.get('actual_elevation'),
                'azimuth_error': state.get('azimuth_error'),
                'elevation_error': state.get('elevation_error'),
                'signal_strength': signal_strength,
                'snr': snr,
                'frequency': frequency,
                'data_rate': data_rate,
                'communication_status': 'Connected' if comm_connected else 'Disconnected',
                'gps_latitude': self.settings.get('gps_latitude'),
                'gps_longitude': self.settings.get('gps_longitude'),
                'gps_altitude': self.settings.get('gps_altitude_m'),
                'time_sync': True,
                'fault_state': state.get('fault_state'),
                'last_rx_utc': state.get('last_rx_utc'),
            }
        )

    def upcoming_passes(self):
        """Return upcoming satellite passes."""
        state = self._controller_state()
        satellite = state.get('satellite_name')
        if not satellite:
            return jsonify([])

        if state.get('is_visible'):
            now = datetime.now()
            pass_hint = {
                'satellite': satellite,
                'rise_time': now.strftime('%Y-%m-%d %H:%M:%S'),
                'max_elevation': state.get('target_elevation'),
                'set_time': (now + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S'),
                'duration': 10,
            }
            return jsonify([pass_hint])

        return jsonify([])

    def receiver_config(self):
        """Return receiver configuration."""
        return jsonify(
            {
                'frequency': self.settings.get('frequency_mhz', 145.800),
                'modulation': 'FM',
                'bandwidth': 25000,
                'squelch': -100,
                'recording_enabled': True,
                'recording_path': '/data/recordings/',
            }
        )

    def transmitter_config(self):
        """Return transmitter configuration."""
        mode = self._controller_state().get('mode') or 'idle'
        return jsonify(
            {
                'frequency': self.settings.get('tx_frequency_mhz', 145.200),
                'modulation': 'FM',
                'power_output': 10,
                'bandwidth': 25000,
                'status': 'Active' if mode in ('external', 'standalone') else 'Standby',
            }
        )

    def telemetry_data(self):
        """Return recent telemetry data."""
        state = self._controller_state()
        telemetry = []
        for i in range(10):
            timestamp = datetime.now() - timedelta(minutes=i)
            telemetry.append(
                {
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'signal_strength': self.settings.get('signal_strength_dbm'),
                    'snr': self.settings.get('snr_db'),
                    'bit_error_rate': 0.0
                    if state.get('uart_connected')
                    else None,
                    'packet_count': None,
                    'target_azimuth': state.get('target_azimuth'),
                    'target_elevation': state.get('target_elevation'),
                    'actual_azimuth': state.get('actual_azimuth'),
                    'actual_elevation': state.get('actual_elevation'),
                    'azimuth_error': state.get('azimuth_error'),
                    'elevation_error': state.get('elevation_error'),
                    'last_rx_utc': state.get('last_rx_utc'),
                }
            )
        return jsonify(telemetry)

    def system_health(self):
        """Return detailed system health."""
        state = self._controller_state()
        mode = state.get('mode') or 'idle'
        tracking_active = mode == 'standalone' and state.get('standalone_running')
        external_active = mode == 'external'
        return jsonify(
            {
                'receiver_temp': None,
                'transmitter_temp': None,
                'antenna_temp': None,
                'power_consumption': None,
                'network_status': 'Online',
                'receiver_status': 'Active' if state.get('uart_connected') else 'Idle',
                'transmitter_status': 'Active' if external_active or tracking_active else 'Standby',
                'tracking_status': 'Active' if tracking_active else 'Idle',
                'last_error': state.get('last_error'),
                'fault_state': state.get('fault_state'),
            }
        )

    @staticmethod
    def get_cpu_temperature():
        """Get Raspberry Pi CPU temperature."""
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r', encoding='utf-8') as file:
                temp = int(file.read()) / 1000
                return round(temp, 1)
        except Exception:
            return None
