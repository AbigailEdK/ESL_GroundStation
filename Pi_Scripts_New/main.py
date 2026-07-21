'''
TODO:
   - Start automatically on boot such as with systemd and integrates all functionalities.
   - Two primary modes: 
        1. External MCS: 
            - Target AZ/EL are received, formatted, and sent to STM32.
        2. Standalone:
            - Satellite name/TLE data is sent to Pi and Pi must generate the target angles. 
            - Automate the TLE update via secure channel. 
    - Add method that can give the STM32 step/ramp reference inputs for when dish control loops and PID gains are tuned.
'''

# region ABOUT
'''

'''
# endregion
# region IMPORTS
import os
import time
import json
from datetime import datetime, timezone
from urllib import request, error

try:
    import RPi.GPIO as GPIO  # type: ignore[import-not-found]
except Exception:
    GPIO = None

try:
    from .utils import startBrowser
except ImportError:
    from utils import startBrowser

# endregion

# region PATHS
HOME_DIR = os.path.expanduser("~")
# PROJECT_ROOT = os.path.join(HOME_DIR, "Desktop", "ESL_GroundStation") # ! Uncomment for Ubuntu use
PROJECT_ROOT = os.path.join(HOME_DIR, "iCloudDrive", "Varsity", "Masters", "ESL_GroundStation") # ! Uncomment for Laptop use

PI_SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "Pi_Scripts_New")
PROTOTYPE_SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "Prototype_Pi_Scripts")
BROWSER_SCRIPTS_DIR = os.path.join(PROJECT_ROOT, "Browser")
WEB_MANAGER_PATH = os.path.join(BROWSER_SCRIPTS_DIR, "webManager.py")
INTEGRATION_SETTINGS_PATH = os.path.join(PROJECT_ROOT, 'Config', 'integration_settings.json')
# endregion

# region CLASSES
# endregion

# region VARIABLES
MAIN_LOOP_SLEEP_SECONDS = 1.0
API_BASE_URL = 'http://127.0.0.1:5000'
# endregion


def _load_integration_settings():
    #  % ------------------------------------------------------------
    #  % Inputs: None directly; reads Config/integration_settings.json and falls back to empty settings.
    #  % Side-effects: Loads runtime configuration used to initialize controller and optional standalone mode.
    #  % Returns: Settings dictionary parsed from disk, or empty dict when unavailable/invalid.
    #  % ------------------------------------------------------------
    try:
        with open(INTEGRATION_SETTINGS_PATH, 'r', encoding='utf-8') as file:
            loaded = json.load(file)
        return loaded if isinstance(loaded, dict) else {}
    except Exception:
        return {}


def _api_post(path, payload=None, timeout=2.0):
    #  % ------------------------------------------------------------
    #  % Inputs: path endpoint suffix, optional payload dict, and timeout seconds.
    #  % Side-effects: Issues HTTP POST to local Browser API and JSON-decodes the response body.
    #  % Returns: Dictionary parsed from API response, or empty dict when response has no body.
    #  % ------------------------------------------------------------
    data = json.dumps(payload or {}).encode('utf-8')
    req = request.Request(
        f"{API_BASE_URL}{path}",
        data=data,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode('utf-8')
        return json.loads(body) if body else {}


def _api_get(path, timeout=2.0):
    #  % ------------------------------------------------------------
    #  % Inputs: path endpoint suffix and timeout seconds.
    #  % Side-effects: Issues HTTP GET to local Browser API and JSON-decodes the response body.
    #  % Returns: Dictionary parsed from API response, or empty dict when response has no body.
    #  % ------------------------------------------------------------
    req = request.Request(f"{API_BASE_URL}{path}", method='GET')
    with request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode('utf-8')
        return json.loads(body) if body else {}


def _read_standalone_config(settings):
    #  % ------------------------------------------------------------
    #  % Inputs: settings dictionary loaded from integration settings file.
    #  % Side-effects: Normalizes standalone mode values (enabled/name/line1/line2/refresh rate).
    #  % Returns: Sanitized standalone configuration dictionary used by main loop.
    #  % ------------------------------------------------------------
    standalone = settings.get('standalone', {})
    if not isinstance(standalone, dict):
        standalone = {}

    refresh_rate_hz = standalone.get('refresh_rate_hz')
    try:
        refresh_rate_hz = float(refresh_rate_hz) if refresh_rate_hz is not None else None
    except (TypeError, ValueError):
        refresh_rate_hz = None

    return {
        'enabled': bool(standalone.get('enabled', False)),
        'name': standalone.get('name') or standalone.get('satellite_name'),
        'line1': standalone.get('line1') or standalone.get('tle_line1'),
        'line2': standalone.get('line2') or standalone.get('tle_line2'),
        'refresh_rate_hz': refresh_rate_hz,
    }


def _read_mode_switch_config(settings):
    #  % ------------------------------------------------------------
    #  % Inputs: settings dictionary loaded from integration settings file.
    #  % Side-effects: Normalizes mode switch pin/polarity defaults for Raspberry Pi GPIO reads.
    #  % Returns: Sanitized mode switch configuration dictionary.
    #  % ------------------------------------------------------------
    switch = settings.get('mode_switch', {})
    if not isinstance(switch, dict):
        switch = {}

    pin = switch.get('pin', 16)
    try:
        pin = int(pin)
    except (TypeError, ValueError):
        pin = 16

    pull_resistor = str(switch.get('pull_resistor', 'none')).strip().lower()
    if pull_resistor not in ('none', 'up', 'down'):
        pull_resistor = 'none'

    standalone_when_low = bool(switch.get('standalone_when_low', True))
    default_mode = str(switch.get('default_mode', 'mcs')).strip().lower()
    if default_mode not in ('mcs', 'standalone'):
        default_mode = 'mcs'

    return {
        'enabled': bool(switch.get('enabled', True)),
        'pin': pin,
        'pull_resistor': pull_resistor,
        'standalone_when_low': standalone_when_low,
        'default_mode': default_mode,
    }


def _read_bridge_config(settings):
    #  % ------------------------------------------------------------
    #  % Inputs: settings dictionary loaded from integration settings file.
    #  % Side-effects: Normalizes USB bridge port settings for computer mode.
    #  % Returns: Sanitized bridge configuration dictionary.
    #  % ------------------------------------------------------------
    bridge = settings.get('computer_mode', {})
    if not isinstance(bridge, dict):
        bridge = {}

    bridge_port = bridge.get('bridge_port', '/dev/ttyGS0')
    bridge_port = str(bridge_port).strip() or '/dev/ttyGS0'

    try:
        bridge_timeout = float(bridge.get('bridge_timeout', 0.1))
    except (TypeError, ValueError):
        bridge_timeout = 0.1

    return {
        'bridge_port': bridge_port,
        'bridge_timeout': bridge_timeout,
    }


def _setup_mode_switch(mode_switch_cfg):
    #  % ------------------------------------------------------------
    #  % Inputs: Sanitized mode switch configuration values.
    #  % Side-effects: Initializes optional GPIO input pin and creates mode reader/cleanup callables.
    #  % Returns: Tuple (read_mode, cleanup_mode_switch, source_label).
    #  % ------------------------------------------------------------
    default_mode = mode_switch_cfg['default_mode']

    def _default_reader():
        return default_mode

    def _noop_cleanup():
        return None

    if not mode_switch_cfg.get('enabled'):
        return _default_reader, _noop_cleanup, 'config-default'

    if GPIO is None:
        return _default_reader, _noop_cleanup, 'gpio-unavailable'

    pin = mode_switch_cfg['pin']
    pull_resistor = mode_switch_cfg['pull_resistor']
    standalone_when_low = mode_switch_cfg['standalone_when_low']

    GPIO.setmode(GPIO.BCM)
    if pull_resistor == 'up':
        pud = GPIO.PUD_UP
    elif pull_resistor == 'down':
        pud = GPIO.PUD_DOWN
    else:
        pud = GPIO.PUD_OFF
    GPIO.setup(pin, GPIO.IN, pull_up_down=pud)

    def _gpio_reader():
        raw = GPIO.input(pin)
        is_low = (raw == GPIO.LOW)
        standalone = is_low if standalone_when_low else (not is_low)
        return 'standalone' if standalone else 'mcs'

    def _gpio_cleanup():
        try:
            GPIO.cleanup(pin)
        except Exception:
            pass

    return _gpio_reader, _gpio_cleanup, f'gpio-bcm-{pin}'

# region MAIN
def main():
    #  % ------------------------------------------------------------
    #  % Inputs: No direct parameters; uses MAIN_LOOP_SLEEP_SECONDS and Browser subprocess state.
    #  % Side-effects: Starts/restarts Browser process, drives GroundStationController UART lifecycle, and prints live telemetry rows.
    #  % Returns: None; runs until interrupted or process termination.
    #  % ------------------------------------------------------------
    global browser_process

    browser_process = None

    # * Load JSON file
    # | Contains standalone mode and mode switch GPIO configuration (in Config folder).
    settings = _load_integration_settings() 

    # * Setup mode switch GPIO reader and cleanup callables
    # | Get standalone configuration values from loaded JSON, defaulting to disabled if missing or invalid.
    standalone_cfg = _read_standalone_config(settings)

    # | Get computer bridge configuration values from loaded JSON.
    bridge_cfg = _read_bridge_config(settings)

    # | Get mode switch configuration values from loaded JSON, defaulting to disabled if missing or invalid.
    mode_switch_cfg = _read_mode_switch_config(settings)

    # | read_mode() returns 'mcs' or 'standalone' based on GPIO pin state or default config.
    # | cleanup_mode_switch() releases GPIO resources when main loop exits.
    read_mode, cleanup_mode_switch, mode_source = _setup_mode_switch(mode_switch_cfg)
    enforce_mode_switch = mode_source.startswith('gpio-bcm-')

    # * Main loop state variables
    # | standalone_loaded: True if TLE data has been successfully loaded for standalone mode.
    standalone_loaded = False
    
    # | standalone_started: True if standalone tracking has been started.
    standalone_started = False
    
    # | standalone_tle_warning_printed: True if a warning about missing TLE data has been printed to avoid repeated warnings.
    standalone_tle_warning_printed = False
    
    # | active_mode: Tracks the current mode ('mcs' or 'standalone') to detect changes and print mode switch messages.
    active_mode = None

    # | last_uart_retry: Timestamp of the last UART connection attempt to throttle retries.
    last_uart_retry = 0.0

    # | computer_bridge_started: True if raw USB↔UART relay mode is active.
    computer_bridge_started = False

    # * Start web browser
    # | Start Browser subprocess in background mode to serve web UI.
    browser_process = startBrowser(background=True)

    # * Main loop
    print(f"Starting Ground Station Prototype... mode source: {mode_source}")
    if not enforce_mode_switch:
        print('Mode switch enforcement disabled (GPIO input unavailable); browser actions control mode.')
    try:
        while True:
            
            # > ------------------
            # > BROWSER PROCESSING
            # > ------------------
            # - KEEP BROWSER ALIVE
            # | Keep the process alive and restart browser server if it exits unexpectedly.
            if browser_process is None or browser_process.poll() is not None:
                print("Browser process stopped, restarting...")
                # | Start browser
                browser_process = startBrowser(background=True)
                # | Reset standalone state to ensure TLE is reloaded and tracking is restarted after browser restart.
                standalone_loaded = False
                standalone_started = False
                standalone_tle_warning_printed = False
                last_uart_retry = 0.0
                computer_bridge_started = False

            # > ------------------
            # >  STATE MANAGEMENT
            # > ------------------
            # - READ CURRENT STATE FROM CONTROLLER
            # | Returns a dictionary containing telemetry values (target and actual azimuth/elevation) 
            state = {}
            try:
                # | Get through API to avoid direct UART access in this script, since Browser process owns the serial port.
                state = _api_get('/api/control/state')
            except error.URLError:
                pass
            except Exception:
                pass

            # > ------------------
            # >    MODE CHECK
            # > ------------------
            requested_mode = None
            if enforce_mode_switch:
                # - READ CURRENT MODE
                # | From GPIO pin when hardware mode switch is active.
                requested_mode = read_mode()
                if requested_mode != active_mode:
                    print(f"Mode switch -> {requested_mode.upper()}")
                    active_mode = requested_mode

            # > ------------------
            # >  UART / BRIDGE CONNECTION
            # > ------------------
            now = time.time()
            if (
                not state.get('uart_connected')
                and not state.get('bridge_running')
                and (not enforce_mode_switch or requested_mode != 'mcs')
            ):
                # | Attempt to reconnect UART every 5 seconds if not connected and not in raw bridge mode.
                if now - last_uart_retry >= 5.0:
                    try:
                        response = _api_post('/api/control/connect-uart')
                        if response.get('status') != 'ok':
                            print(f"UART reconnect failed: {response.get('message', 'unknown error')}")
                    except Exception as exc:
                        print(f"UART reconnect failed: {exc}")
                    last_uart_retry = now
                    try:
                        state = _api_get('/api/control/state')
                    except Exception:
                        state = {}

            # > ------------------
            # >  TELEMETRY DATA
            # > ------------------
            # - PRINT LATEST TELEMETRY ROW
            # | Get current UTC time 
            ts = time.strftime('%H:%M:%S')

            # | Get current target and actual azimuth/elevation values from state dictionary.
            target_az = state.get('target_azimuth')
            target_el = state.get('target_elevation')
            actual_az = state.get('actual_azimuth')
            actual_el = state.get('actual_elevation')

            # | Print telemetry row with timestamp, target/actual values, and errors if available; otherwise indicate waiting for STM32.
            if None not in (target_az, target_el, actual_az, actual_el):
                az_e = actual_az - target_az
                el_e = actual_el - target_el
                print(f"{ts:10} | {target_az:>8.1f} {actual_az:>8.1f} {az_e:>+8.1f} | "
                    f"{target_el:>8.1f} {actual_el:>8.1f} {el_e:>+8.1f}")
            else:
                print(f"{ts:10} | waiting for STM32...")

            # | Re-read state after mode changes so bridge/tracking transitions use current controller values.
            try:
                state = _api_get('/api/control/state')
            except Exception:
                state = {}

            if enforce_mode_switch:
                # > ------------------
                # >  COMPUTER MODE
                # > ------------------
                if requested_mode == 'mcs':
                    if computer_bridge_started:
                        try:
                            _api_post('/api/control/computer-bridge/stop')
                        except Exception:
                            pass
                        computer_bridge_started = False

                    if standalone_started:
                        try:
                            _api_post('/api/control/stop-standalone')
                        except Exception:
                            pass
                        standalone_started = False
                        print('Standalone tracking: stopped (computer mode)')

                    if not computer_bridge_started:
                        try:
                            response = _api_post('/api/control/computer-bridge', {'bridge_port': bridge_cfg.get('bridge_port')})
                            computer_bridge_started = response.get('status') == 'ok'
                            print(f"Computer bridge: {response.get('message', 'no response message')}")
                        except Exception as exc:
                            computer_bridge_started = False
                            print(f"Computer bridge failed: {exc}")

                # > ------------------
                # >  STANDALONE MODE
                # > ------------------
                elif requested_mode == 'standalone' and standalone_cfg.get('enabled'):
                    if computer_bridge_started:
                        try:
                            _api_post('/api/control/computer-bridge/stop')
                        except Exception:
                            pass
                        computer_bridge_started = False

                    name = standalone_cfg.get('name')
                    line1 = standalone_cfg.get('line1')
                    line2 = standalone_cfg.get('line2')

                    if not standalone_loaded:
                        if name and line1 and line2:
                            try:
                                response = _api_post(
                                    '/api/control/load-tle',
                                    {'name': name, 'line1': line1, 'line2': line2},
                                )
                                standalone_loaded = response.get('status') == 'ok'
                                print(f"Standalone TLE load: {response.get('message', 'no response message')}")
                            except Exception as exc:
                                standalone_loaded = False
                                print(f"Standalone TLE load failed: {exc}")
                            standalone_tle_warning_printed = False
                        else:
                            if not standalone_tle_warning_printed:
                                print('Standalone mode enabled but TLE fields are incomplete')
                                standalone_tle_warning_printed = True
                            standalone_loaded = False

                    scheduled_start_utc = state.get('scheduled_start_utc')
                    if scheduled_start_utc and not standalone_started:
                        try:
                            scheduled_dt = datetime.fromisoformat(str(scheduled_start_utc).replace('Z', '+00:00'))
                            if scheduled_dt.tzinfo is None:
                                scheduled_dt = scheduled_dt.replace(tzinfo=timezone.utc)
                            if datetime.now(timezone.utc) >= scheduled_dt:
                                response = _api_post(
                                    '/api/control/start-standalone',
                                    {'refresh_rate_hz': standalone_cfg.get('refresh_rate_hz')},
                                )
                                standalone_started = response.get('status') == 'ok'
                                print(f"Scheduled standalone start: {response.get('message', 'no response message')}")
                        except Exception as exc:
                            print(f"Scheduled standalone start failed: {exc}")

                    if standalone_loaded and not standalone_started and not scheduled_start_utc:
                        try:
                            response = _api_post(
                                '/api/control/start-standalone',
                                {'refresh_rate_hz': standalone_cfg.get('refresh_rate_hz')},
                            )
                            standalone_started = response.get('status') == 'ok'
                            print(f"Standalone tracking: {response.get('message', 'no response message')}")
                        except Exception as exc:
                            standalone_started = False
                            print(f"Standalone tracking failed: {exc}")
                else:
                    if requested_mode == 'standalone' and not standalone_cfg.get('enabled'):
                        if not standalone_tle_warning_printed:
                            print('Standalone switch selected but standalone mode is disabled in config')
                            standalone_tle_warning_printed = True

                    if standalone_started:
                        try:
                            _api_post('/api/control/stop-standalone')
                        except Exception:
                            pass
                        standalone_started = False
                        print('Standalone tracking: stopped (MCS mode)')

                    if requested_mode != 'standalone':
                        standalone_tle_warning_printed = False

                    if computer_bridge_started:
                        try:
                            _api_post('/api/control/computer-bridge/stop')
                        except Exception:
                            pass
                        computer_bridge_started = False
            else:
                standalone_started = bool(state.get('standalone_running'))
                computer_bridge_started = bool(state.get('bridge_running'))

            # > ------------------
            # >  EXTERNAL MCS MODE
            # > ------------------

            # > ------------------
            # > REFERENCE INPUTS
            # > ------------------
            # - STEP/RAMP REFERENCE INPUTS GENERATED


            # - SENDING TO STM32



            time.sleep(MAIN_LOOP_SLEEP_SECONDS)
    except KeyboardInterrupt:
        # | Graceful shutdown on Ctrl+C
        print("Shutting down Ground Station Prototype...")
    finally:
        # | Cleanup resources and terminate processes
        try:
            # | Stop standalone tracking if it was running
            _api_post('/api/control/stop-standalone')
        except Exception:
            pass
        try:
            # | Disconnect UART if it was connected
            _api_post('/api/control/disconnect-uart')
        except Exception:
            pass
        # | Cleanup GPIO resources for mode switch if applicable
        cleanup_mode_switch()

        # | Terminate Browser process if still running
        if browser_process is not None and browser_process.poll() is None:
            browser_process.terminate()
            try:
                browser_process.wait(timeout=5)
            except Exception:
                browser_process.kill()

# * Main entry point
# | Run main loop on the main thread so the process stays alive and Ctrl+C is handled correctly.
if __name__ == "__main__":
    main()
# endregion