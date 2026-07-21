from datetime import datetime, timedelta, timezone

from flask import jsonify


class TelemetryService:
    #  % ------------------------------------------------------------
    #  % Inputs: Class constructor arguments at instantiation and module dependencies used by its methods.
    #  % Side-effects: Defines state and behavior used by instances across the module.
    #  % Returns: A class definition used to construct and manage instances.
    #  % ------------------------------------------------------------
    def __init__(self, controller=None, settings=None):
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: controller, settings.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: An internal helper result consumed by the caller.
        #  % ------------------------------------------------------------
        self.controller = controller
        self.settings = settings or {}

    def _controller_state(self):
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
        if self.controller is None:
            return {}
        try:
            return self.controller.get_state() or {}
        except Exception:
            return {}

    def system_info(self):
        """Return system information as JSON."""
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
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
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
        state = self._controller_state()

        raw_target_azimuth = state.get('target_azimuth')
        raw_target_elevation = state.get('target_elevation')
        azimuth = raw_target_azimuth
        elevation = raw_target_elevation
        distance_km = state.get('distance_km')
        is_visible = state.get('is_visible')
        predicted_target_used = False
        comm_connected = state.get('uart_connected', False)
        signal_strength = self.settings.get('signal_strength_dbm')
        snr = self.settings.get('snr_db')
        frequency = self.settings.get('frequency_mhz', 145.800)
        data_rate = self.settings.get('data_rate_bps')

        # If standalone loop is not running yet, derive predicted pointing from loaded TLE.
        controller = self.controller
        tracker = getattr(controller, 'tracker', None) if controller is not None else None
        satellite = getattr(tracker, 'satellite', None) if tracker is not None else None
        if (azimuth is None or elevation is None) and tracker is not None and satellite is not None:
            try:
                predicted_az, predicted_el, predicted_dist, predicted_visible = tracker.get_position(
                    datetime.now(timezone.utc)
                )
                if azimuth is None:
                    azimuth = round(predicted_az, 2)
                if elevation is None:
                    elevation = round(predicted_el, 2)
                if distance_km is None:
                    distance_km = round(predicted_dist, 2)
                if is_visible is None:
                    is_visible = bool(predicted_visible)
                predicted_target_used = True
            except Exception:
                pass

        target_source = 'Unavailable'
        if raw_target_azimuth is not None and raw_target_elevation is not None:
            target_source = 'Live (Controller)'
        elif predicted_target_used:
            target_source = 'Predicted (TLE)'

        measured_source = 'Live (STM32 feedback)'
        if state.get('actual_azimuth') is None or state.get('actual_elevation') is None:
            measured_source = 'Unavailable'

        return jsonify(
            {
                'satellite_name': state.get('satellite_name') or 'ISS (ZARYA)',
                'azimuth': azimuth,
                'elevation': elevation,
                'target_source': target_source,
                'distance_km': distance_km,
                'is_visible': is_visible,
                'actual_azimuth': state.get('actual_azimuth'),
                'actual_elevation': state.get('actual_elevation'),
                'measured_source': measured_source,
                'azimuth_error': state.get('azimuth_error'),
                'elevation_error': state.get('elevation_error'),
                'mode': state.get('mode'),
                'requested_mode': state.get('requested_mode') or 'mcs',
                'mode_owner': state.get('mode_owner') or 'browser',
                'hardware_mode': state.get('hardware_mode'),
                'standalone_running': state.get('standalone_running', False),
                'bridge_running': state.get('bridge_running', False),
                'run_state': 'Running'
                if state.get('standalone_running') or state.get('bridge_running')
                else 'Idle',
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
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        state = self._controller_state()
        satellite_name = state.get('satellite_name')
        controller = self.controller
        tracker = getattr(controller, 'tracker', None) if controller is not None else None
        satellite = getattr(tracker, 'satellite', None) if tracker is not None else None
        observer = getattr(tracker, 'observer', None) if tracker is not None else None
        ts = getattr(tracker, 'ts', None) if tracker is not None else None

        if not satellite_name or tracker is None or satellite is None or observer is None or ts is None:
            return jsonify([])

        max_search_hours = float(self.settings.get('pass_search_hours', 24.0))
        min_elevation = float(self.settings.get('pass_min_elevation_deg', 10.0))
        now_utc = datetime.now(timezone.utc)
        t0 = ts.from_datetime(now_utc)
        t1 = ts.from_datetime(now_utc + timedelta(hours=max_search_hours))

        try:
            t_events, events = satellite.find_events(observer, t0, t1, altitude_degrees=min_elevation)
        except Exception:
            return jsonify([])

        upcoming_passes = []
        current_pass = None

        for t_event, event in zip(t_events, events):
            event_time = t_event.utc_datetime()

            if event == 0:
                current_pass = {
                    'satellite': satellite_name,
                    'rise_time': event_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'max_elevation': None,
                    'max_elevation_time': None,
                    'set_time': None,
                    'duration': None,
                }
            elif event == 1 and current_pass is not None:
                azimuth, elevation, _, _ = tracker.get_position(event_time)
                current_pass['max_elevation'] = round(elevation, 1)
                current_pass['max_elevation_time'] = event_time.strftime('%Y-%m-%d %H:%M:%S')
                current_pass['peak_azimuth'] = round(azimuth, 1)
            elif event == 2 and current_pass is not None:
                current_pass['set_time'] = event_time.strftime('%Y-%m-%d %H:%M:%S')
                rise_dt = datetime.strptime(current_pass['rise_time'], '%Y-%m-%d %H:%M:%S').replace(
                    tzinfo=timezone.utc
                )
                duration_minutes = (event_time - rise_dt).total_seconds() / 60.0
                current_pass['duration'] = round(duration_minutes, 1)
                if current_pass.get('max_elevation') is None:
                    azimuth, elevation, _, _ = tracker.get_position(event_time)
                    current_pass['max_elevation'] = round(elevation, 1)
                    current_pass['peak_azimuth'] = round(azimuth, 1)
                upcoming_passes.append(current_pass)
                current_pass = None

        return jsonify(upcoming_passes)

    def receiver_config(self):
        """Return receiver configuration."""
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
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
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
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
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
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
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: A state/report payload for API or internal callers.
        #  % ------------------------------------------------------------
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
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: Reads current state and may compute derived values for reporting.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        try:
            with open('/sys/class/thermal/thermal_zone0/temp', 'r', encoding='utf-8') as file:
                temp = int(file.read()) / 1000
                return round(temp, 1)
        except Exception:
            return None
