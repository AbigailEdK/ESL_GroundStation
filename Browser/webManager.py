'''
TODO:
    - Hosted locally and available from any machine on the closed network
    - Live monitoring: time, current target AZ/EL, actual AZ/EL reported by STM32, error between them
    - Later: STM32 firmware will be updated to send states and error messages which should also show on the broswer
    - Pass countdown and satellite name display would be useful during tracking operations
    - Ground track map showing satellite position over Earth based on TLE data would be a very cool addition. Leaftlet.js could be used for this map.
    - Basic commanding: selecting a satellite to track, or entering manual AZ/EL targets

N.B! The serial port to STM32 can only be opened by one process, so the web server must absorb the UART handling rather than running alongside other scripts.
'''

from flask import Flask
import json
import os
import sys
from routes import (
    create_control_blueprint,
    create_recording_blueprint,
    create_snapshots_blueprint,
    create_telemetry_blueprint,
    create_ui_blueprint,
)
from services import ControlService, RecordingService, SnapshotService, TelemetryService

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Pi_Scripts_New.controller import GroundStationController


def _load_integration_settings():
    settings_path = os.path.join(PROJECT_ROOT, 'Config', 'integration_settings.json')
    default_settings = {
        'controller': {
            'auto_connect_uart': False,
            'uart_port': '/dev/serial0',
            'uart_baudrate': 115200,
            'uart_timeout': 0.5,
            'refresh_rate_hz': 1.0,
            'feedback_enabled': True,
        },
        'telemetry': {},
        'storage': {
            'recordings_dir': '~/GSWebUI/recordings',
            'snapshots_dir': '~/GSWebUI/snapshots',
        },
    }

    try:
        with open(settings_path, 'r', encoding='utf-8') as file:
            loaded = json.load(file)
        if isinstance(loaded, dict):
            for section, values in loaded.items():
                if isinstance(values, dict) and isinstance(default_settings.get(section), dict):
                    default_settings[section].update(values)
                else:
                    default_settings[section] = values
    except Exception as exc:
        print(f'Using default integration settings: {exc}')

    return default_settings


class WebManagerApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.app.template_folder = os.path.join(os.path.dirname(__file__), 'templates')
        self.app.static_folder = os.path.join(os.path.dirname(__file__), 'static')

        self.settings = _load_integration_settings()

        self.controller = self._create_controller()

        self.telemetry_service = TelemetryService(
            controller=self.controller,
            settings=self.settings.get('telemetry', {}),
        )
        self.control_service = ControlService(controller=self.controller)
        storage = self.settings.get('storage', {})
        self.recording_service = RecordingService(
            os.path.expanduser(storage.get('recordings_dir', '~/GSWebUI/recordings'))
        )
        self.snapshot_service = SnapshotService(
            os.path.expanduser(storage.get('snapshots_dir', '~/GSWebUI/snapshots'))
        )

        self._register_blueprints()

    def _create_controller(self):
        controller_settings = self.settings.get('controller', {})
        auto_connect_uart = bool(controller_settings.get('auto_connect_uart', False))
        try:
            return GroundStationController(
                auto_connect_uart=auto_connect_uart,
                settings=controller_settings,
            )
        except Exception as exc:
            print(f'Controller unavailable: {exc}')
            return None

    def _register_blueprints(self):
        self.app.register_blueprint(create_ui_blueprint())
        self.app.register_blueprint(
            create_telemetry_blueprint(self.telemetry_service)
        )
        self.app.register_blueprint(
            create_control_blueprint(self.control_service)
        )
        self.app.register_blueprint(
            create_recording_blueprint(self.recording_service)
        )
        self.app.register_blueprint(
            create_snapshots_blueprint(self.snapshot_service)
        )


def create_app():
    return WebManagerApp().app


app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)