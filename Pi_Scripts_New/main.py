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
import sys
import csv
import time
import subprocess
import atexit
import signal
from datetime import datetime, timedelta, timezone
from tracker import SatelliteTracker
from uart import UARTComm
from utils import startBrowser, stopBrowser, handle_exit_signal, startUART, stopUART, startTracker, stopTracker, csvLogSetup
import serial
import threading

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
from config import UART_PORT, UART_BAUDRATE, LOG_DIR
# endregion

# region MAIN
def main():
    global browser_process
    global uart_comm
    global satellite_tracker

    latest = {}
    lock = threading.Lock()
    log_file, log_writer = csvLogSetup(LOG_DIR)

    browser_process = None
    uart_comm = None
    satellite_tracker = None

    # | Start web browser
    browser_process = startBrowser(background=True)

    # | Start UART and reception loop 
    uart_comm = startUART(latest=latest, lock=lock, log_writer=log_writer, log_file=log_file, port=UART_PORT, baudrate=UART_BAUDRATE, timeout=1)

    # | Start satellite tracker
    satellite_tracker = startTracker(lat=-33.918861, lon=18.4233, elevation_m=0)  # Example coordinates; replace with actual

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
            # - AZ/EL TARGETS RECEIVED


            # - FORMATTING


            # - SENDING TO STM32
            uart_comm.send_position(azimuth=az, elevation=el)  # Example values; replace with actual received targets



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
        atexit.register(stopBrowser)
        signal.signal(signal.SIGINT, handle_exit_signal)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, handle_exit_signal)

if __name__ == "__main__": threading.Thread(target=main, daemon=True).start()
# endregion