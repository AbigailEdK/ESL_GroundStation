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
    create_settings_blueprint,
    create_snapshots_blueprint,
    create_telemetry_blueprint,
    create_tle_library_blueprint,
    create_ui_blueprint,
)
from services import (
    ControlService,
    RecordingService,
    SettingsService,
    SnapshotService,
    TelemetryService,
    TleLibraryService,
)

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from Pi_Scripts_New.controller import GroundStationController


def _load_integration_settings():
    #  % ------------------------------------------------------------
    #  % Inputs: None directly; reads Config/integration_settings.json and uses built-in default settings.
    #  % Side-effects: Reads configuration from disk and merges loaded sections into default controller/telemetry/storage values.
    #  % Returns: A settings dictionary used to configure controller behavior and service wiring.
    #  % ------------------------------------------------------------
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
            'tle_library_path': os.path.join(PROJECT_ROOT, 'Config', 'saved_satellites.json'),
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
    #  % ------------------------------------------------------------
    #  % Inputs: Flask runtime context and project settings resolved by this module.
    #  % Side-effects: Defines the app container that owns services and the shared controller instance.
    #  % Returns: The WebManagerApp class type for creating configured web app instances.
    #  % ------------------------------------------------------------
    def __init__(self):
        #  % ------------------------------------------------------------
        #  % Inputs: None directly; uses loaded settings to configure telemetry, control, recording, and snapshot services.
        #  % Side-effects: Initializes Flask app folders, creates controller/service objects, and registers all blueprints.
        #  % Returns: None; stores initialized components on self for the process lifetime.
        #  % ------------------------------------------------------------
        self.app = Flask(__name__)
        self.app.template_folder = os.path.join(os.path.dirname(__file__), 'webpages')
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
        self.tle_library_service = TleLibraryService(
            os.path.expanduser(
                storage.get('tle_library_path', os.path.join(PROJECT_ROOT, 'Config', 'saved_satellites.json'))
            ),
            controller=self.controller,
        )
        self.settings_service = SettingsService(
            os.path.join(PROJECT_ROOT, 'Config', 'integration_settings.json')
        )

        self._register_blueprints()

    def _create_controller(self):
        #  % ------------------------------------------------------------
        #  % Inputs: Controller settings section from self.settings, including UART and feedback options.
        #  % Side-effects: Attempts to construct GroundStationController and logs errors if construction fails.
        #  % Returns: A GroundStationController instance, or None when initialization fails.
        #  % ------------------------------------------------------------
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
        #  % ------------------------------------------------------------
        #  % Inputs: Already-created service instances attached to self.
        #  % Side-effects: Registers UI, telemetry, control, recording, and snapshot routes on the Flask app.
        #  % Returns: None; blueprints are attached to self.app in-place.
        #  % ------------------------------------------------------------
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
        self.app.register_blueprint(
            create_tle_library_blueprint(self.tle_library_service)
        )
        self.app.register_blueprint(
            create_settings_blueprint(self.settings_service)
        )


def create_app():
    #  % ------------------------------------------------------------
    #  % Inputs: None.
    #  % Side-effects: Instantiates WebManagerApp and builds all web/service/controller wiring.
    #  % Returns: A configured Flask application object ready for app.run or WSGI hosting.
    #  % ------------------------------------------------------------
    return WebManagerApp().app


app = create_app()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)