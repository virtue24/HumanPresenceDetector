import serial
import serial.tools.list_ports
import time
from typing import Optional

class ArduinoController:
    """Simple Arduino relay controller."""
    
    def __init__(self, baud_rate: int = 9600):
        """Initialize Arduino controller."""
        self.baud_rate = baud_rate
        self.serial_connection: Optional[serial.Serial] = None
        self.port: Optional[str] = None
        
        # Find and connect to Arduino
        self._find_and_connect()
        print(f"ArduinoController initialized on port: {self.port}")
    
    def _find_arduino_port(self) -> Optional[str]:
        """Find Arduino port by handshaking."""
        ports = serial.tools.list_ports.comports()
        print(f"Found {len(ports)} serial ports:")
        
        for port in ports:
            # Skip Bluetooth ports (Not reliable)
            if "bluetooth" in port.description.lower():
                print(f"  Skipping Bluetooth port: {port.device}")
                continue
                
            print(f"  Trying port: {port.device} ({port.description})")
            ser = None
            try:
                # Use shorter timeout to prevent hanging
                ser = serial.Serial(port.device, self.baud_rate, timeout=1, write_timeout=1)
                time.sleep(5)  # Shorter wait time
                
                # Handshake
                ser.write(b"Hi, are you arduino?\n")
                ser.flush()  # Force write
                
                # Read with timeout
                response = ser.readline().decode().strip()
                print(f"    Response: '{response}'")
                
                if response == "This is Arduino":
                    ser.close()
                    print(f"  ✓ Found Arduino on {port.device}")
                    return port.device
                    
                ser.close()
                print(f"    Not Arduino")
                
            except Exception as e:
                print(f"    Error: {e}")
                if ser and ser.is_open:
                    try:
                        ser.close()
                    except:
                        pass
                continue
                
        print("  ✗ No Arduino found on any port")
        return None
    
    def _find_and_connect(self):
        """Find Arduino and connect."""
        self.port = self._find_arduino_port()
        if self.port:
            self._connect()
    
    def _connect(self) -> bool:
        """Connect to Arduino on known port."""
        if not self.port:
            return False
            
        try:
            self.serial_connection = serial.Serial(self.port, self.baud_rate, timeout=2)
            time.sleep(2)
            
            # Test connection
            if self._send_command("PING") == "PONG":
                return True
            else:
                self.serial_connection.close()
                return False
        except:
            return False
    
    def _send_command(self, command: str) -> Optional[str]:
        """Send command to Arduino."""
        if not self.serial_connection or not self.serial_connection.is_open:
            return None
            
        try:
            self.serial_connection.write(f"{command}\n".encode())
            response = self.serial_connection.readline().decode().strip()
            return response
        except:
            return None
    
    def _try_reconnect(self):
        """Try to reconnect if connection is lost."""
        if not self.is_connected():
            # Try to reconnect on current port first
            if self.port and self._connect():
                return True
            else:
                # Find new port if current failed
                self._find_and_connect()
                return self.is_connected()
        return True
    
    def is_connected(self) -> bool:
        """Check if Arduino is connected via ping-pong."""
        return self._send_command("PING") == "PONG"
    
    def relay_on(self, pin: int, delay_ms: int = 0, duration_ms: int = 1000) -> str:
        """
        Control relay.
        
        Args:
            pin: Arduino pin number
            delay_ms: Delay before activation
            duration_ms: How long to keep active
            
        Returns:
            "OK", "BUSY", or "ERR"
        """
        command = f"RELAY_ON;{pin};{delay_ms};{duration_ms}"
        response = self._send_command(command)
        
        # Try to reconnect if command failed
        if not response:
            if self._try_reconnect():
                response = self._send_command(command)
        
        return response if response in ["OK", "BUSY", "ERR"] else "ERR"
    
    def relay_on_overwrite(self, pin: int, delay_ms: int = 0, duration_ms: int = 1000) -> str:
        """
        Control relay.
        
        Args:
            pin: Arduino pin number
            delay_ms: Delay before activation
            duration_ms: How long to keep active
            
        Returns:
            "OK", "BUSY", or "ERR"
        """
        command = f"RELAY_ON_OVERWRITE;{pin};{delay_ms};{duration_ms}"
        response = self._send_command(command)
        
        # Try to reconnect if command failed
        if not response:
            if self._try_reconnect():
                response = self._send_command(command)
        
        return response if response in ["OK", "BUSY", "ERR"] else "ERR"
    
    def disconnect(self):
        """Disconnect from Arduino."""
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
    
    def __del__(self):
        """Cleanup on deletion."""
        try:
            self.disconnect()
        except:
            pass

if __name__ == "__main__":
    print("Testing Arduino Controller...")
    
    arduino = ArduinoController()
    
    if arduino.is_connected():
        print("✓ Arduino found and connected")
        print(f"Port: {arduino.port}")
        
        # Test relay
        response = arduino.relay_on(pin=2, duration_ms=3000)
        print(f"Relay test: {response}")
        
    else:
        print("✗ Arduino not found")
    
    # Test reconnection
    print("Testing reconnection...")
    time.sleep(2)
    if arduino.is_connected():
        print("✓ Still connected")
    else:
        print("✗ Connection lost")
    
    arduino.disconnect()
    print("✓ Disconnected")