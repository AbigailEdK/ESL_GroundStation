import serial
import threading
import time

class UARTComm:
    #  % ------------------------------------------------------------
    #  % Inputs: Serial port configuration values and pyserial dependency.
    #  % Side-effects: Defines UART command/telemetry methods and RX thread lifecycle helpers.
    #  % Returns: The UARTComm class type used by controller and utilities.
    #  % ------------------------------------------------------------
    def __init__(self, port="/dev/serial0", baudrate=115200, timeout=1):
        """Initialize UART communication"""
        #  % ------------------------------------------------------------
        #  % Inputs: port path/name, baudrate, and serial timeout.
        #  % Side-effects: Opens serial port immediately, initializes RX thread state, and prints startup banner.
        #  % Returns: None; prepares UARTComm instance for send/read operations.
        #  % ------------------------------------------------------------
        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        self.running = True
        self.rx_thread = None
        print(f"UART initialized on {port} at {baudrate} baud")
    
    def send_position(self, azimuth=None, elevation=None):
        """
        Send AZ/EL command in fixed 16-byte format: "AZ###.# EL###.#\n"
        
        Args:
            azimuth: Azimuth angle in degrees, or None to skip
            elevation: Elevation angle in degrees, or None to skip
        """
        #  % ------------------------------------------------------------
        #  % Inputs: Optional azimuth/elevation numeric targets; missing values are encoded as placeholders.
        #  % Side-effects: Formats command string and writes bytes to serial port.
        #  % Returns: None; command is transmitted over UART.
        #  % ------------------------------------------------------------
        # Format azimuth 
        if azimuth is None:
            az_str = "AZxxx.x"
        else:
            az_str = f"AZ{azimuth:05.1f}"
        
        # Format elevation 
        if elevation is None:
            el_str = "ELxxx.x"
        else:
            el_str = f"EL{elevation:05.1f}"
        
        # Combine: AZ###.# EL###.#\n = 16 bytes total
        message = f"{az_str} {el_str}\n"
        
        self.ser.write(message.encode())
        print(f"UART TX: {message.strip()}")

    def read_line(self):
        """Read a single UART line, returning None on timeout/no data."""
        #  % ------------------------------------------------------------
        #  % Inputs: No direct parameters; reads from current serial connection.
        #  % Side-effects: Performs a single serial readline decode step.
        #  % Returns: Decoded string for one line, or None when timeout/no data occurs.
        #  % ------------------------------------------------------------
        raw = self.ser.readline()
        if not raw:
            return None
        text = raw.decode(errors='ignore').strip()
        return text or None

    def start_rx_loop(self, line_handler, thread_name='uart-rx'):
        """Start a daemon RX thread and invoke line_handler for each line."""
        #  % ------------------------------------------------------------
        #  % Inputs: line_handler callback and optional thread_name label.
        #  % Side-effects: Starts daemon thread that repeatedly reads UART and dispatches each line to callback.
        #  % Returns: None; RX thread state is updated in-place.
        #  % ------------------------------------------------------------
        if line_handler is None:
            raise ValueError("line_handler is required")

        if self.rx_thread is not None and self.rx_thread.is_alive():
            return

        self.running = True

        def _worker():
            #  % ------------------------------------------------------------
            #  % Inputs: No direct parameters; closes over self and line_handler from outer function.
            #  % Side-effects: Runs RX loop, invoking callback per line and sleeping briefly on exceptions.
            #  % Returns: None; loop exits when self.running becomes False.
            #  % ------------------------------------------------------------
            while self.running:
                try:
                    line = self.read_line()
                    if line is None:
                        continue
                    line_handler(line)
                except Exception as exc:
                    print(f"UART RX loop error: {exc}")
                    time.sleep(0.1)

        self.rx_thread = threading.Thread(target=_worker, name=thread_name, daemon=True)
        self.rx_thread.start()

    def stop_rx_loop(self, join_timeout=1.0):
        """Stop the RX loop and join thread briefly."""
        #  % ------------------------------------------------------------
        #  % Inputs: join_timeout seconds for optional thread join wait.
        #  % Side-effects: Signals RX loop stop and joins worker thread when safe.
        #  % Returns: None; RX thread handle is cleared.
        #  % ------------------------------------------------------------
        self.running = False
        thread = self.rx_thread
        if thread is not None and thread.is_alive() and threading.current_thread() is not thread:
            thread.join(timeout=join_timeout)
        self.rx_thread = None

    def clear_input_buffer(self):
        """Clear pending UART RX bytes to start from fresh state."""
        #  % ------------------------------------------------------------
        #  % Inputs: No direct parameters.
        #  % Side-effects: Resets serial input buffer to discard unread bytes.
        #  % Returns: None; serial buffer state is modified.
        #  % ------------------------------------------------------------
        self.ser.reset_input_buffer()
    
    def close(self):
        """Close UART connection"""
        #  % ------------------------------------------------------------
        #  % Inputs: No direct parameters.
        #  % Side-effects: Stops RX loop and closes underlying serial port.
        #  % Returns: None; UART connection is fully closed.
        #  % ------------------------------------------------------------
        self.stop_rx_loop()
        self.ser.close()
        print("UART connection closed")