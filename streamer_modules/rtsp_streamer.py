import cv2
import threading
import time
from typing import Optional
import numpy as np

class RTSPStreamer:
    def __init__(self, ip_address: str, username: str, password: str, endpoint: str = "/stream", port: int = 554, fps: int = 30):
        """
        Initialize the RTSP streamer for CCTV camera.
        
        Args:
            ip_address (str): IPv4 address of the CCTV camera
            username (str): Username for RTSP authentication
            password (str): Password for RTSP authentication
            endpoint (str): RTSP endpoint path (default: "/stream")
            port (int): RTSP port (default: 554)
            fps (int): Target frames per second for capture
        """
        self.ip_address = ip_address
        self.username = username
        self.password = password
        self.endpoint = endpoint
        self.port = port
        self.fps = fps
        self.frame_delay = 1.0 / fps
        
        # Build RTSP URL
        self.rtsp_url = f"rtsp://{username}:{password}@{ip_address}:{port}{endpoint}"
        
        # Threading components
        self._capture_thread = None
        self._stop_event = threading.Event()
        self._frame_lock = threading.Lock()
        
        # Frame storage
        self._last_frame: Optional[np.ndarray] = None
        self._frame_timestamp = 0
        
        # OpenCV VideoCapture object
        self._cap = None
        self._is_running = False
        
    def start(self) -> bool:
        """
        Start the RTSP streaming thread.
        
        Returns:
            bool: True if successfully started, False otherwise
        """
        if self._is_running:
            print("RTSP streamer is already running.")
            return True
            
        # Initialize RTSP connection
        self._cap = cv2.VideoCapture(self.rtsp_url)
        if not self._cap.isOpened():
            print(f"Error: Could not open RTSP stream at {self.ip_address}")
            return False
            
        # Set camera properties for better performance
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        # Start capture thread
        self._stop_event.clear()
        self._capture_thread = threading.Thread(target=self._capture_frames, daemon=True)
        self._capture_thread.start()
        self._is_running = True
        
        print(f"RTSP streamer started for camera at {self.ip_address} at {self.fps} FPS")
        return True
        
    def stop(self):
        """Stop the RTSP streaming thread."""
        if not self._is_running:
            return
            
        self._stop_event.set()
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=3.0)
            
        if self._cap:
            self._cap.release()
            
        self._is_running = False
        print("RTSP streamer stopped.")
        
    def _capture_frames(self):
        """Internal method to capture frames in a separate thread."""
        while not self._stop_event.is_set():
            try:
                ret, frame = self._cap.read()
                if ret:
                    with self._frame_lock:
                        self._last_frame = frame.copy()
                        self._frame_timestamp = time.time()
                else:
                    print(f"Warning: Failed to read frame from RTSP stream {self.ip_address}")
                    time.sleep(0.5)  # Longer pause for network streams before retrying
                    
                # Control frame rate
                time.sleep(self.frame_delay)
                
            except Exception as e:
                print(f"Error in RTSP frame capture: {e}")
                time.sleep(1.0)  # Wait before retrying on error
                
    def get_last_frame(self) -> Optional[np.ndarray]:
        """
        Get the most recent frame from the RTSP stream.
        
        Returns:
            Optional[np.ndarray]: The last captured frame, or None if no frame available
        """
        with self._frame_lock:
            if self._last_frame is not None:
                return self._last_frame.copy()
            return None
            
    def get_frame_with_timestamp(self) -> tuple[Optional[np.ndarray], float]:
        """
        Get the most recent frame along with its timestamp.
        
        Returns:
            tuple: (frame, timestamp) where frame is np.ndarray or None, timestamp is float
        """
        with self._frame_lock:
            frame = self._last_frame.copy() if self._last_frame is not None else None
            return frame, self._frame_timestamp
            
    def is_running(self) -> bool:
        """Check if the streamer is currently running."""
        return self._is_running
        
    def get_stream_info(self) -> dict:
        """
        Get information about the RTSP stream.
        
        Returns:
            dict: Dictionary containing stream properties
        """
        info = {
            'ip_address': self.ip_address,
            'port': self.port,
            'endpoint': self.endpoint,
            'rtsp_url': self.rtsp_url.replace(f"{self.username}:{self.password}@", "***:***@"),  # Hide credentials
            'is_running': self._is_running
        }
        
        if self._cap and self._cap.isOpened():
            info.update({
                'width': int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'fps': self._cap.get(cv2.CAP_PROP_FPS),
                'backend': self._cap.getBackendName()
            })
            
        return info
        
    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        
    def __del__(self):
        """Destructor to ensure cleanup."""
        self.stop()


if __name__ == "__main__":
    # Example usage
    streamer = RTSPStreamer(
        ip_address="192.168.1.100",
        username="admin", 
        password="password123",
        endpoint="/stream1",
        fps=25
    )
    
    if streamer.start():
        try:
            while True:
                frame = streamer.get_last_frame()
                if frame is not None:
                    cv2.imshow("RTSP Stream", frame)
                    
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        finally:
            streamer.stop()
            cv2.destroyAllWindows()
