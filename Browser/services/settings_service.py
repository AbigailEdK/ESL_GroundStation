import json
import os

from flask import jsonify


class SettingsService:
    #  % ------------------------------------------------------------
    #  % Inputs: Absolute path to integration settings JSON file.
    #  % Side-effects: Persists Settings UI updates and serves current settings to clients.
    #  % Returns: Service object used by settings API routes.
    #  % ------------------------------------------------------------
    def __init__(self, settings_path):
        self.settings_path = os.path.abspath(os.path.expanduser(settings_path))
        settings_dir = os.path.dirname(self.settings_path)
        if settings_dir:
            os.makedirs(settings_dir, exist_ok=True)
        if not os.path.exists(self.settings_path):
            with open(self.settings_path, 'w', encoding='utf-8') as file:
                json.dump({}, file, indent=4)

    def _read_settings(self):
        try:
            with open(self.settings_path, 'r', encoding='utf-8') as file:
                payload = json.load(file)
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _write_settings(self, payload):
        with open(self.settings_path, 'w', encoding='utf-8') as file:
            json.dump(payload, file, indent=4)

    @staticmethod
    def _parse_float(value, fallback):
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _parse_int(value, fallback):
        try:
            return int(value)
        except (TypeError, ValueError):
            return fallback

    def get_settings(self):
        return jsonify(self._read_settings())

    def update_general(self, data):
        payload = self._read_settings()
        ui = payload.setdefault('ui', {})

        update_interval = self._parse_int(data.get('update_interval_seconds'), 2)
        theme = str(data.get('theme') or 'dark').strip().lower()
        if theme not in ('dark', 'light'):
            theme = 'dark'

        ui['update_interval_seconds'] = max(update_interval, 1)
        ui['theme'] = theme

        self._write_settings(payload)
        return jsonify({'status': 'ok', 'message': 'General settings saved', 'settings': payload})

    def update_receiver(self, data):
        payload = self._read_settings()
        receiver = payload.setdefault('receiver', {})
        telemetry = payload.setdefault('telemetry', {})

        frequency_mhz = self._parse_float(data.get('frequency_mhz'), telemetry.get('frequency_mhz', 145.8))
        modulation = str(data.get('modulation') or receiver.get('modulation') or 'FM').strip().upper()
        if modulation not in ('FM', 'AM', 'SSB'):
            modulation = 'FM'
        bandwidth_khz = self._parse_float(data.get('bandwidth_khz'), receiver.get('bandwidth_khz', 25.0))

        receiver['frequency_mhz'] = round(float(frequency_mhz), 3)
        receiver['modulation'] = modulation
        receiver['bandwidth_khz'] = max(float(bandwidth_khz), 0.1)

        telemetry['frequency_mhz'] = round(float(frequency_mhz), 3)

        self._write_settings(payload)
        return jsonify({'status': 'ok', 'message': 'Receiver settings saved', 'settings': payload})

    def update_transmitter(self, data):
        payload = self._read_settings()
        transmitter = payload.setdefault('transmitter', {})
        telemetry = payload.setdefault('telemetry', {})

        frequency_mhz = self._parse_float(data.get('frequency_mhz'), telemetry.get('tx_frequency_mhz', 145.2))
        power_output_w = self._parse_float(data.get('power_output_w'), transmitter.get('power_output_w', 10.0))
        status = str(data.get('status') or transmitter.get('status') or 'Standby').strip().capitalize()
        if status not in ('Standby', 'Active'):
            status = 'Standby'

        transmitter['frequency_mhz'] = round(float(frequency_mhz), 3)
        transmitter['power_output_w'] = max(float(power_output_w), 0.0)
        transmitter['status'] = status

        telemetry['tx_frequency_mhz'] = round(float(frequency_mhz), 3)

        self._write_settings(payload)
        return jsonify({'status': 'ok', 'message': 'Transmitter settings saved', 'settings': payload})
