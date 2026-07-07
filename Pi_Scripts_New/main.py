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
import threading
import json
from urllib import request, error

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
MAIN_LOOP_SLEEP_SECONDS = 1.0
# endregion

# region CLASSES
# endregion

# region VARIABLES
API_BASE_URL = 'http://127.0.0.1:5000'
# endregion


def _api_post(path, payload=None, timeout=2.0):
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
    req = request.Request(f"{API_BASE_URL}{path}", method='GET')
    with request.urlopen(req, timeout=timeout) as response:
        body = response.read().decode('utf-8')
        return json.loads(body) if body else {}

# region MAIN
def main():
    global browser_process

    browser_process = None

    # | Start web browser
    browser_process = startBrowser(background=True)

    print("Starting Ground Station Prototype...")
    try:
        while True:
            # Keep the process alive and restart browser server if it exits unexpectedly.
            
            # > ------------------
            # > BROWSER PROCESSING
            # > ------------------
            # - KEEP BROWSER ALIVE
            if browser_process is None or browser_process.poll() is not None:
                print("Browser process stopped, restarting...")
                browser_process = startBrowser(background=True)

            # > ------------------
            # > EXTERNAL MCS MODE
            # > ------------------
            state = {}
            try:
                state = _api_get('/api/control/state')
            except error.URLError:
                pass
            except Exception:
                pass

            # - FORMATTING


            # Print latest received telemetry 
            ts = time.strftime('%H:%M:%S')
            target_az = state.get('target_azimuth')
            target_el = state.get('target_elevation')
            actual_az = state.get('actual_azimuth')
            actual_el = state.get('actual_elevation')

            if None not in (target_az, target_el, actual_az, actual_el):
                az_e = actual_az - target_az
                el_e = actual_el - target_el
                print(f"{ts:10} | {target_az:>8.1f} {actual_az:>8.1f} {az_e:>+8.1f} | "
                    f"{target_el:>8.1f} {actual_el:>8.1f} {el_e:>+8.1f}")
            else:
                print(f"{ts:10} | waiting for STM32...")


            # > ------------------
            # > STANDALONE MODE
            # > ------------------
            # - TLE RECEIVED


            # - TARGET ANGLE GENERATION


            # - SENDING TO STM32



            # > ------------------
            # > REFERENCE INPUTS
            # > ------------------
            # - STEP/RAMP REFERENCE INPUTS GENERATED


            # - SENDING TO STM32



            time.sleep(MAIN_LOOP_SLEEP_SECONDS)
    except KeyboardInterrupt:
        print("Shutting down Ground Station Prototype...")
    finally:
        try:
            _api_post('/api/control/disconnect-uart')
        except Exception:
            pass
        if browser_process is not None and browser_process.poll() is None:
            browser_process.terminate()
            try:
                browser_process.wait(timeout=5)
            except Exception:
                browser_process.kill()

if __name__ == "__main__": threading.Thread(target=main, daemon=True).start()
# endregion