import serial
import time

class UARTComm:
    def __init__(self, port="/dev/serial0", baudrate=115200, timeout=1):
        """Initialize UART communication"""
        self.ser = serial.Serial(port, baudrate=baudrate, timeout=timeout)
        print(f"UART initialized on {port} at {baudrate} baud")
    
    def send_position(self, azimuth=None, elevation=None):
        """
        Send AZ/EL command in fixed 16-byte format: "AZ###.# EL###.#\n"
        
        Args:
            azimuth: Azimuth angle in degrees, or None to skip
            elevation: Elevation angle in degrees, or None to skip
        """
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
    
    def close(self):
        """Close UART connection"""
        self.ser.close()
        print("UART connection closed")