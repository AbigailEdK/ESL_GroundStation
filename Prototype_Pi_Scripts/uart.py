import serial
import time
import datetime

# UART message format config (edit these to change TX format globally)
UART_MESSAGE_TEMPLATE = "{az} {el}\n"
AZ_VALUE_TEMPLATE = "AZ{value:05.1f}"
EL_VALUE_TEMPLATE = "EL{value:05.1f}"
AZ_MISSING_TEXT = "AZxxx.x"
EL_MISSING_TEXT = "ELxxx.x"

class UARTComm:
    #  % ------------------------------------------------------------
    #  % Inputs: Class constructor arguments at instantiation and module dependencies used by its methods.
    #  % Side-effects: Defines state and behavior used by instances across the module.
    #  % Returns: A class definition used to construct and manage instances.
    #  % ------------------------------------------------------------
    def __init__(self, port="/dev/serial0", baudrate=115200, timeout=1):
        """Initialize UART communication"""
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: port, baudrate, timeout.
        #  % Side-effects: Executes module logic and may read or mutate internal state.
        #  % Returns: An internal helper result consumed by the caller.
        #  % ------------------------------------------------------------
        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        self.running = True
        self.rx_thread = None
        print(f"UART initialized on {port} at {baudrate} baud")
    
    def send_position(self, azimuth=None, elevation=None):
        """
        Send AZ/EL command using the configured templates at file top.
        
        Args:
            azimuth: Azimuth angle in degrees, or None to skip
            elevation: Elevation angle in degrees, or None to skip
        """
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: azimuth, elevation.
        #  % Side-effects: May change device/file state and update in-memory tracking fields.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        if azimuth is None:
            az_str = AZ_MISSING_TEXT
        else:
            az_str = AZ_VALUE_TEMPLATE.format(value=azimuth)

        if elevation is None:
            el_str = EL_MISSING_TEXT
        else:
            el_str = EL_VALUE_TEMPLATE.format(value=elevation)

        message = UART_MESSAGE_TEMPLATE.format(az=az_str, el=el_str)
        
        self.ser.write(message.encode())
        print(f"UART TX: {message.strip()}")
    
    def close(self):
        """Close UART connection"""
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; uses internal state, constants, or environment context.
        #  % Side-effects: May stop active work, release resources, and update shared runtime state.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        self.running = False
        self.ser.close()
        print("UART connection closed")

    def rx_loop(self, latest, lock, log_writer, log_file):
        """Continuously read from UART and update latest telemetry data"""
        #  % ------------------------------------------------------------
        #  % Inputs: Parameters: latest, lock, log_writer, log_file.
        #  % Side-effects: Runs loop/supervisor logic that coordinates subsystems over time.
        #  % Returns: The function result for the caller (type depends on operation).
        #  % ------------------------------------------------------------
        while self.running:
            try:
                line = self.ser.readline().decode("ascii", errors="ignore").strip()

                if not line.startswith("$TLM,"):
                    continue

                parts = line[5:].split(",")

                if len(parts) < 4:
                    continue

                data = {
                    "az_actual": float(parts[0]),
                    "az_target": float(parts[1]),
                    "el_actual": float(parts[2]),
                    "el_target": float(parts[3]),
                }

                with lock:
                    latest.update(data)

                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                log_writer.writerow([
                    ts,
                    data["az_actual"],
                    data["az_target"],
                    data["el_actual"],
                    data["el_target"],
                ])
                log_file.flush()

            except Exception as e:
                print(f"RX error: {e}")

'''
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
            
            '''