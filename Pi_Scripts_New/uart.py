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
        """Send one AZ line and one EL line using the terminal protocol."""
        #  % ------------------------------------------------------------
        #  % Inputs: Optional azimuth/elevation numeric targets; missing values are encoded as placeholders.
        #  % Side-effects: Formats two command lines and writes bytes to serial port.
        #  % Returns: None; command is transmitted over UART.
        #  % ------------------------------------------------------------
        self.send_target_pair(azimuth, elevation)

    def send_line(self, text):
        """Send one raw text line with a trailing newline if needed."""
        #  % ------------------------------------------------------------
        #  % Inputs: Text line to send to the serial peer.
        #  % Side-effects: Writes a newline-terminated payload to the serial port.
        #  % Returns: None; line is transmitted over UART.
        #  % ------------------------------------------------------------
        if text is None:
            return
        payload = str(text)
        if not payload.endswith('\n'):
            payload += '\n'
        self.ser.write(payload.encode())
        print(f"UART TX: {payload.strip()}")

    def send_target_pair(self, azimuth=None, elevation=None, interline_delay=0.02):
        """Send separate AZ and EL target lines as required by the updated STM32 protocol."""
        #  % ------------------------------------------------------------
        #  % Inputs: Optional azimuth/elevation numeric targets and a small delay between lines.
        #  % Side-effects: Sends AZ and EL commands as individual lines over UART.
        #  % Returns: None; both lines are transmitted over UART.
        #  % ------------------------------------------------------------
        if azimuth is None:
            az_line = 'AZxxx.xx'
        else:
            az_line = f'AZ{float(azimuth):06.2f}'

        if elevation is None:
            el_line = 'ELyyy.yy'
        else:
            el_line = f'EL{float(elevation):06.2f}'

        self.send_line(az_line)
        time.sleep(max(float(interline_delay), 0.0))
        self.send_line(el_line)

    def send_raw_bytes(self, data):
        """Write raw bytes to the serial port."""
        #  % ------------------------------------------------------------
        #  % Inputs: Raw bytes or bytearray payload.
        #  % Side-effects: Writes the payload directly to the serial port.
        #  % Returns: Number of bytes written by the serial layer.
        #  % ------------------------------------------------------------
        return self.ser.write(data)

    def read_bytes(self, size=1):
        """Read raw bytes from the serial port without text decoding."""
        #  % ------------------------------------------------------------
        #  % Inputs: Number of bytes to read.
        #  % Side-effects: Reads from the serial port buffer.
        #  % Returns: Raw bytes object, possibly empty when no data is available.
        #  % ------------------------------------------------------------
        return self.ser.read(size)

    @property
    def in_waiting(self):
        #  % ------------------------------------------------------------
        #  % Inputs: No explicit parameters; reads current serial buffer state.
        #  % Side-effects: None.
        #  % Returns: Number of pending bytes available to read.
        #  % ------------------------------------------------------------
        return self.ser.in_waiting

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