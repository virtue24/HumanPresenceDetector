import cv2
import threading
import time
from typing import Optional, Tuple
import numpy as np

class WebcamStreamer:
    def __init__(self, webcam_index: int = 0, fps: int = 30):
        """
        Initialize the webcam streamer.
        
        Args:
            webcam_index (int): Index of the webcam to use
            fps (int): Target frames per second for capture
        """
        self.webcam_index = webcam_index
        self.fps = fps
        self.frame_delay = 1.0 / fps
        
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
        Start the webcam streaming thread.
        
        Returns:
            bool: True if successfully started, False otherwise
        """
        if self._is_running:
            print("Webcam streamer is already running.")
            return True
            
        # Initialize webcam
        self._cap = cv2.VideoCapture(self.webcam_index)
        if not self._cap.isOpened():
            print(f"Error: Could not open webcam with index {self.webcam_index}")
            return False
            
        # Set camera properties for better performance
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        # Start capture thread
        self._stop_event.clear()
        self._capture_thread = threading.Thread(target=self._capture_frames, daemon=True)
        self._capture_thread.start()
        self._is_running = True
        
        print(f"Webcam streamer started with index {self.webcam_index} at {self.fps} FPS")
        return True
        
    def stop(self):
        """Stop the webcam streaming thread."""
        if not self._is_running:
            return
            
        self._stop_event.set()
        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=2.0)
            
        if self._cap:
            self._cap.release()
            
        self._is_running = False
        print("Webcam streamer stopped.")
        
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
                    print("Warning: Failed to read frame from webcam")
                    time.sleep(0.1)  # Brief pause before retrying
                    
                # Control frame rate
                time.sleep(self.frame_delay)
                
            except Exception as e:
                print(f"Error in frame capture: {e}")
                break
                
    def get_last_frame(self) -> Optional[np.ndarray]:
        """
        Get the most recent frame from the webcam.
        
        Returns:
            Optional[np.ndarray]: The last captured frame, or None if no frame available
        """
        with self._frame_lock:
            if self._last_frame is not None:
                return self._last_frame.copy()
            return None
            
    def get_frame_with_timestamp(self) -> Tuple[Optional[np.ndarray], float]:
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
        
    def get_webcam_info(self) -> dict:
        """
        Get information about the webcam.
        
        Returns:
            dict: Dictionary containing webcam properties
        """
        if not self._cap or not self._cap.isOpened():
            return {}
            
        return {
            'width': int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': self._cap.get(cv2.CAP_PROP_FPS),
            'backend': self._cap.getBackendName()
        }
        
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
    streamer = WebcamStreamer(webcam_index=0, fps=30)
    if streamer.start():
        try:
            while True:
                frame = streamer.get_last_frame()
                if frame is not None:
                    cv2.imshow("Webcam Stream", frame)
                    
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        finally:
            streamer.stop()
            cv2.destroyAllWindows()