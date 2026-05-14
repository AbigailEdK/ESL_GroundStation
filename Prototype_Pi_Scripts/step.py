#!/usr/bin/env python3

import sys
import subprocess
import select
import RPi.GPIO as GPIO
from ESL_GroundStation.Prototype_Pi_Scripts.uart import UARTComm

#Step angle limits
AZ_MIN = 0.0
AZ_MAX = 360.0
EL_MIN = 15.0
EL_MAX = 85.0

# Setup GPIO for LED
GPIO.setmode(GPIO.BCM)
GPIO.setup(2, GPIO.OUT)  # Red LED
GPIO.output(2, GPIO.HIGH)  # Red OFF (active low)
GPIO.setup(3, GPIO.OUT)  # Green LED
GPIO.output(3, GPIO.HIGH)  # Green OFF

uart = UARTComm(port="/dev/serial0", baudrate=115200, timeout=0.1)
log_process = None
led_flash = False

print("Control with: 'az <val>', 'el <val>', or 'az <val> el <val>'")
print("Listening for PI_START/PI_STOP commands from STM32...\n")

# Solid red on startup
GPIO.output(2, GPIO.LOW)
GPIO.output(3, GPIO.HIGH)

def is_angle_valid(value, angle_type):
    """Checks if an angle is within the defined MIN/MAX bounds."""
    if angle_type == 'az':
        if not (AZ_MIN <= value <= AZ_MAX):
            print(f"AZ Error: Azimuth must be between {AZ_MIN} and {AZ_MAX}.")
            return False
    elif angle_type == 'el':
        if not (EL_MIN <= value <= EL_MAX):
            print(f"EL Error: Elevation must be between {EL_MIN} and {EL_MAX}.")
            return False
    return True

def start_logging():
    global log_process, led_flash
    if log_process is None:
        log_process = subprocess.Popen(
            ['python3', 'log.py'],
            stdin=subprocess.PIPE,
            text=True,
            stderr=subprocess.PIPE
        )

        # Read the CSV filename line from log.py
        first_line = log_process.stderr.readline().strip()
        if first_line:
            print(f"[STEP] {first_line}")

        led_flash = True
        print("[STEP] Logging started")

def stop_logging():
    global log_process, led_flash
    if log_process is not None:
        try:
            log_process.stdin.close()
            log_process.wait(timeout=2)
            # Print the CSV filename from stderr
            stderr_output = log_process.stderr.read().decode()
            for line in stderr_output.split('\n'):
                if 'log_' in line and '.csv' in line:
                    print(f"[STEP] {line.strip()}")
        except:
            log_process.terminate()
        log_process = None
        led_flash = False
        GPIO.output(2, GPIO.LOW)  # Back to solid red
        print("[STEP] Logging stopped")

led_counter = 0

while True:
    try:
        # Check UART for incoming data (non-blocking)
        line = uart.ser.readline().decode('utf-8', errors='ignore').strip()
        
        if line == "PI_START":
            start_logging()
            continue
        
        if line == "PI_STOP":
            stop_logging()
            continue
        
        # Forward log data to subprocess if it's running
        if line.startswith('#') and log_process is not None:
            try:
                log_process.stdin.write(line + '\n')
                log_process.stdin.flush()
            except:
                stop_logging()
        
        # LED flashing when logging
        if led_flash:
            if led_counter % 2:
                GPIO.output(2, GPIO.LOW)   # Red ON
            else:
                GPIO.output(2, GPIO.HIGH)  # Red OFF
            led_counter = (led_counter + 1) % 4
        
        # Non-blocking user input check
        if sys.stdin in select.select([sys.stdin], [], [], 0)[0]:
            try:
                user_input = input("step> ").strip()
                
                if not user_input or user_input == 'exit':
                    break
                
                parts = user_input.split()
                 # Handle single command: az <val> OR el <val>
                if len(parts) == 2:
                    cmd, value = parts[0].lower(), float(parts[1])
                    if cmd in ['az', 'el'] and is_angle_valid(value, cmd):
                        if cmd == 'az':
                            uart.send_position(azimuth=value)
                        elif cmd == 'el':
                            uart.send_position(elevation=value)
                    elif cmd not in ['az', 'el']:
                         print("Invalid command. Use 'az' or 'el'")
                # Handle el and az command
                elif len(parts) == 4:
                    if parts[0].lower() == 'az' and parts[2].lower() == 'el':
                        az_val = float(parts[1])
                        el_val = float(parts[3])
                        # Check both values are valid before sending
                        if is_angle_valid(az_val, 'az') and is_angle_valid(el_val, 'el'):
                            uart.send_position(azimuth=az_val, elevation=el_val)
                    else:
                        print("Invalid format. Use: az <value> el <value>")
                else:
                    print("Invalid format. Use: 'az <val>', 'el <val>', or 'az <val> el <val>'")
                # --------------------------------------------------------------------------

            except ValueError:
                print("Invalid number value")
    
    except KeyboardInterrupt:
        break
    except Exception as e:
        print(f"Error: {e}")

stop_logging()
uart.close()
GPIO.cleanup()