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

# region VARIABLES
from config import UART_PORT, UART_BAUDRATE, LOG_DIR
# endregion

def startBrowser(background=True):
    if not os.path.exists(WEB_MANAGER_PATH):
        raise FileNotFoundError(f"webManager.py not found: {WEB_MANAGER_PATH}")

    command = [sys.executable, WEB_MANAGER_PATH]
    if background:
        # Start Flask server without blocking the rest of main.py.
        return subprocess.Popen(command, cwd=BROWSER_SCRIPTS_DIR)

    return subprocess.run(command, cwd=BROWSER_SCRIPTS_DIR, check=True)


def stopBrowser():
    global browser_process
    if browser_process is None or browser_process.poll() is not None:
        return

    browser_process.terminate()
    try:
        browser_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        browser_process.kill()
        browser_process.wait()

def startUART(latest, lock, log_writer, log_file, port=UART_PORT, baudrate=UART_BAUDRATE, timeout=1):
    global uart_comm
    if uart_comm is None:
        uart_comm = UARTComm(port=port, baudrate=baudrate, timeout=timeout)

        uart_comm.rx_thread = threading.Thread(
            target=uart_comm.rx_loop,
            args=(latest, lock, log_writer, log_file),
            daemon=True,
        )
        uart_comm.rx_thread.start()

    return uart_comm

def stopUART():
    global uart_comm
    if uart_comm is not None:
        uart_comm.close()
        uart_comm = None

def startTracker(lat=-33.918861, lon=18.4233, elevation_m=0):
    global satellite_tracker
    if satellite_tracker is None:
        satellite_tracker = SatelliteTracker(lat=lat, lon=lon, elevation_m=elevation_m)

    return satellite_tracker

def stopTracker():
    global satellite_tracker
    if satellite_tracker is not None:
        satellite_tracker = None


def handle_exit_signal(signum, _frame):
    stopBrowser()
    stopUART()
    stopTracker()
    raise SystemExit(0)

def csvLogSetup(log_dir):
    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(log_dir, f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    log_file = open(log_filename, 'w', newline='')
    log_writer = csv.writer(log_file)
    log_writer.writerow(['Timestamp', 'AZ_Actual', 'AZ_Target', 'EL_Actual', 'EL_Target'])
    log_file.flush()
    print(f"Logging to {log_filename}")
    
    return log_file, log_writer