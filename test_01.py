#!/usr/bin/env python3
# scripts/test_01.py
# Friday test - send fixed target, monitor STM32 telemetry
# Ctrl+C to stop

import sys
import os
import serial
import threading
import time
import csv
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from ESL_GroundStation.config import UART_PORT, UART_BAUDRATE, LOG_DIR

# --- Config for this test ---
TEST_AZ = 120.4  # fixed target to send, change as needed
TEST_EL = 42.4
SEND_HZ = 1.0   # how often to send target to STM32

# --- Shared state ---
latest = {}
lock = threading.Lock()
running = True

# --- CSV log setup ---
os.makedirs(LOG_DIR, exist_ok=True)
log_filename = os.path.join(LOG_DIR, f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
log_file = open(log_filename, 'w', newline='')
log_writer = csv.writer(log_file)
log_writer.writerow(['Timestamp', 'AZ_Actual', 'AZ_Target', 'EL_Actual', 'EL_Target'])
log_file.flush()
print(f"Logging to {log_filename}")

# --- UART ---
try:
    ser = serial.Serial(UART_PORT, UART_BAUDRATE, timeout=1)
    print(f"UART open on {UART_PORT} at {UART_BAUDRATE} baud")
except Exception as e:
    print(f"Failed to open UART: {e}")
    sys.exit(1)

# --- RX thread ---
def rx_loop():
    while running:
        try:
            line = ser.readline().decode('ascii', errors='ignore').strip()
            if not line.startswith('$TLM,'):
                continue
            parts = line[5:].split(',')
            if len(parts) < 4:
                continue
            data = {
                'az_actual': float(parts[0]),
                'az_target': float(parts[1]),
                'el_actual': float(parts[2]),
                'el_target': float(parts[3]),
            }
            with lock:
                latest.update(data)
            # Log every received frame
            ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            log_writer.writerow([ts, data['az_actual'], data['az_target'],
                                      data['el_actual'], data['el_target']])
            log_file.flush()
        except Exception:
            pass

threading.Thread(target=rx_loop, daemon=True).start()

# --- Main loop: send target + print table ---
print(f"\nSending fixed target: AZ={TEST_AZ} EL={TEST_EL}")
print(f"{'Time':10} | {'AZ_tgt':>8} {'AZ_act':>8} {'AZ_err':>8} | {'EL_tgt':>8} {'EL_act':>8} {'EL_err':>8}")
print("-" * 72)

try:
    while True:
        # Send target to STM32
        az_str = f"AZ{TEST_AZ:05.1f}"
        el_str = f"EL{TEST_EL:05.1f}"
        msg = f"{az_str} {el_str}\n"
        ser.write(msg.encode())

        # Print latest received telemetry
        with lock:
            d = dict(latest)

        ts = time.strftime('%H:%M:%S')
        if d:
            az_e = d['az_actual'] - d['az_target']
            el_e = d['el_actual'] - d['el_target']
            print(f"{ts:10} | {d['az_target']:>8.1f} {d['az_actual']:>8.1f} {az_e:>+8.1f} | "
                  f"{d['el_target']:>8.1f} {d['el_actual']:>8.1f} {el_e:>+8.1f}")
        else:
            print(f"{ts:10} | waiting for STM32...")

        time.sleep(1.0 / SEND_HZ)

except KeyboardInterrupt:
    print("\nStopped.")
finally:
    running = False
    log_file.close()
    ser.close()
    print(f"Log saved: {log_filename}")