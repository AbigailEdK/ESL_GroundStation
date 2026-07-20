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
import threading

try:
    from .tracker import SatelliteTracker
    from .uart import UARTComm
    from .config import UART_PORT, UART_BAUDRATE, LOG_DIR
except ImportError:
    from tracker import SatelliteTracker
    from uart import UARTComm
    from config import UART_PORT, UART_BAUDRATE, LOG_DIR

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
browser_process = None
uart_comm = None
satellite_tracker = None
# endregion

def startBrowser(background=True):
    #  % ------------------------------------------------------------
    #  % Inputs: background flag controlling subprocess (non-blocking) versus run (blocking) behavior.
    #  % Side-effects: Checks web manager path and launches Browser webManager.py process accordingly.
    #  % Returns: Popen object in background mode, otherwise CompletedProcess from blocking run.
    #  % ------------------------------------------------------------
    if not os.path.exists(WEB_MANAGER_PATH):
        raise FileNotFoundError(f"webManager.py not found: {WEB_MANAGER_PATH}")

    command = [sys.executable, WEB_MANAGER_PATH]
    if background:
        # Start Flask server without blocking the rest of main.py.
        return subprocess.Popen(command, cwd=BROWSER_SCRIPTS_DIR)

    return subprocess.run(command, cwd=BROWSER_SCRIPTS_DIR, check=True)


def stopBrowser():
    #  % ------------------------------------------------------------
    #  % Inputs: No direct parameters; uses global browser_process handle.
    #  % Side-effects: Attempts graceful terminate then force kill if Browser process does not exit in timeout.
    #  % Returns: None; process handle is managed for shutdown semantics.
    #  % ------------------------------------------------------------
    global browser_process
    if browser_process is None or browser_process.poll() is not None:
        return

    browser_process.terminate()
    try:
        browser_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        browser_process.kill()
        browser_process.wait()

def startUART(
    latest=None,
    lock=None,
    log_writer=None,
    log_file=None,
    port=UART_PORT,
    baudrate=UART_BAUDRATE,
    timeout=1,
    start_rx=False,
    rx_target=None,
    rx_thread_name='uart-rx',
):
    #  % ------------------------------------------------------------
    #  % Inputs: Optional telemetry storage objects, UART port settings, and optional custom RX callback settings.
    #  % Side-effects: Creates UARTComm singleton if missing and may start RX loop using custom or default telemetry handler.
    #  % Returns: UARTComm instance when available, otherwise None if serial initialization failed.
    #  % ------------------------------------------------------------
    global uart_comm
    if uart_comm is None:
        try:
            uart_comm = UARTComm(port, baudrate, timeout)
        except Exception as e:
            print(f"Failed to open UART: {e}")
            uart_comm = None
            return None

    default_rx_requested = all(arg is not None for arg in (latest, lock, log_writer, log_file))

    if start_rx and rx_target is not None:
        uart_comm.start_rx_loop(rx_target, thread_name=rx_thread_name)
    elif default_rx_requested:
        def _default_line_handler(line):
            #  % ------------------------------------------------------------
            #  % Inputs: line text from UART RX thread for default $TLM telemetry parsing path.
            #  % Side-effects: Parses telemetry values, updates shared latest dict under lock, and appends row to CSV log.
            #  % Returns: None; mutates shared telemetry/log objects captured from outer scope.
            #  % ------------------------------------------------------------
            if not line.startswith('$TLM,'):
                return

            parts = line[5:].split(',')
            if len(parts) < 4:
                return

            data = {
                'az_actual': float(parts[0]),
                'az_target': float(parts[1]),
                'el_actual': float(parts[2]),
                'el_target': float(parts[3]),
            }

            with lock:
                latest.update(data)

            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            log_writer.writerow([
                ts,
                data['az_actual'],
                data['az_target'],
                data['el_actual'],
                data['el_target'],
            ])
            log_file.flush()

        uart_comm.start_rx_loop(_default_line_handler, thread_name=rx_thread_name)

    return uart_comm

def stopUART(uart_instance=None):
    #  % ------------------------------------------------------------
    #  % Inputs: Optional uart_instance to close directly; otherwise uses global uart_comm reference.
    #  % Side-effects: Stops RX loop via close, clears global UART reference when applicable.
    #  % Returns: None; UART resources are released in-place.
    #  % ------------------------------------------------------------
    global uart_comm
    if uart_instance is not None:
        uart_instance.close()
        if uart_comm is uart_instance:
            uart_comm = None
        return

    if uart_comm is not None:
        uart_comm.close()
        uart_comm = None

def startTracker(lat=-33.918861, lon=18.4233, elevation_m=0):
    #  % ------------------------------------------------------------
    #  % Inputs: lat, lon, elevation_m observer coordinates for tracker initialization.
    #  % Side-effects: Creates global SatelliteTracker singleton if not already present.
    #  % Returns: SatelliteTracker instance used by controller/tracking workflows.
    #  % ------------------------------------------------------------
    global satellite_tracker
    if satellite_tracker is None:
        satellite_tracker = SatelliteTracker(lat=lat, lon=lon, elevation_m=elevation_m)

    return satellite_tracker

def stopTracker():
    #  % ------------------------------------------------------------
    #  % Inputs: No direct parameters; uses global satellite_tracker reference.
    #  % Side-effects: Clears tracker singleton reference so it can be reinitialized later.
    #  % Returns: None; tracker reference is removed in-place.
    #  % ------------------------------------------------------------
    global satellite_tracker
    if satellite_tracker is not None:
        satellite_tracker = None


def handle_exit_signal(signum, _frame):
    #  % ------------------------------------------------------------
    #  % Inputs: signum and frame values from OS signal handler invocation.
    #  % Side-effects: Stops Browser, UART, and tracker subsystems, then exits process.
    #  % Returns: Does not return normally; raises SystemExit(0).
    #  % ------------------------------------------------------------
    stopBrowser()
    stopUART()
    stopTracker()
    raise SystemExit(0)

def csvLogSetup(log_dir):
    #  % ------------------------------------------------------------
    #  % Inputs: log_dir path for telemetry CSV output.
    #  % Side-effects: Creates log directory/file, writes header row, and flushes file handle.
    #  % Returns: Tuple (log_file, log_writer) for subsequent telemetry logging.
    #  % ------------------------------------------------------------
    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(log_dir, f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    log_file = open(log_filename, 'w', newline='')
    log_writer = csv.writer(log_file)
    log_writer.writerow(['Timestamp', 'AZ_Actual', 'AZ_Target', 'EL_Actual', 'EL_Target'])
    log_file.flush()
    print(f"Logging to {log_filename}")
    
    return log_file, log_writer