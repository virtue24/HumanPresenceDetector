from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import uvicorn
import threading
import time
import numpy as np
from typing import Optional, Tuple, List
import cv2
from fastapi.responses import StreamingResponse
from io import BytesIO
from pydantic import BaseModel

class PolygonPointsRequest(BaseModel):
    points: List[List[float]]

class StateAPIServer:
    def __init__(self, detector, stream_source, host: str = "0.0.0.0", port: int = 8000):
        """
        Initialize the FastAPI server for state monitoring.
        
        Args:
            detector: HumanPresenceDetector instance
            stream_source: Stream source instance (webcam or RTSP)
            host: Server host address
            port: Server port
        """
        self.detector = detector
        self.stream_source = stream_source
        self.host = host
        self.port = port
        self.start_time = time.time()
        
        # State storage - updated by main loop
        self.current_state_data = {
            'current_state': 'human_absent',
            'human_presence_duration': 0.0,
            'human_absence_duration': 0.0,
            'is_stream_running': False,
            'is_arduino_connected': False,
            'timestamp': time.time()
        }

        self.debug_frame:np.ndarray = np.zeros((1,1,3), dtype=np.uint8)
        
        # Relay trigger state
        self.relay_trigger_pin: Optional[int] = None
        
        # Polygon points update state
        self.polygon_points_updated: tuple[bool, Optional[list]] = (False, None)
        
        # FastAPI app
        self.app = FastAPI(title="Human Presence Detection API", version="1.0.0")
        self._setup_routes()
        
        # Server thread
        self.server_thread = None
        self.is_running = False
        
    def _setup_routes(self):
        """Setup API routes."""
        
        @self.app.get("/")
        async def root():
            return {"message": "Human Presence Detection API", "version": "1.0.0"}
        
        @self.app.get("/state")
        async def get_state():
            """Get current detection state."""
            return JSONResponse(content=self.current_state_data)
        
        @self.app.get("/health_status")
        async def get_status():
            """Get system status."""
            return {
                "api_server_running": self.is_running,
                "is_stream_running": self.current_state_data['is_stream_running'],
                "is_arduino_connected": self.current_state_data['is_arduino_connected'],
                "server_uptime_sec": time.time() - self.start_time,              
            }
        
                
        @self.app.get("/get_frame")
        async def get_debug_frame():
            """Get the latest debug frame as a JPEG image."""

            if self.debug_frame is None or self.debug_frame.size == 0:
                raise HTTPException(status_code=404, detail="No debug frame available")

            # Encode frame as JPEG
            ret, jpeg = cv2.imencode('.jpg', self.debug_frame)
            if not ret:
                raise HTTPException(status_code=500, detail="Failed to encode debug frame")

            return StreamingResponse(BytesIO(jpeg.tobytes()), media_type="image/jpeg")
        
        @self.app.get("/trigger_relay")
        async def trigger_relay(pin: int):
            """Trigger relay on specified pin."""
            try:
                # Validate pin number
                if pin < 0 or pin > 255:
                    raise HTTPException(status_code=400, detail="Invalid pin number")
                
                # Set the trigger pin - main loop will handle it
                self.relay_trigger_pin = pin
                
                return {
                    "message": f"Relay trigger queued for pin {pin}",
                    "pin": pin,
                    "timestamp": time.time()
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/update_polygon_points")
        async def update_polygon_points(request: PolygonPointsRequest):
            """
            Update polygon points for detection area.

            Args:
                request: PolygonPointsRequest containing list of [x, y] points

            Example json body is; 
            {
              "points": [
                [0.0, 0.0],
                [1.0, 0.0], 
                [1.0, 1.0],
                [0.0, 1.0]
              ]
            }
            """

            try:
                points = request.points
                
                # Validate points format
                if not isinstance(points, list) or len(points) < 3:
                    raise HTTPException(status_code=400, detail="At least 3 points required for polygon")
                
                validated_points = []
                for i, point in enumerate(points):
                    if not isinstance(point, (list, tuple)) or len(point) != 2:
                        raise HTTPException(status_code=400, detail=f"Point {i} must be [x, y] format")
                    
                    x, y = point
                    if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
                        raise HTTPException(status_code=400, detail=f"Point {i} coordinates must be numbers")
                    
                    if not (0.0 <= x <= 1.0) or not (0.0 <= y <= 1.0):
                        raise HTTPException(status_code=400, detail=f"Point {i} coordinates must be normalized (0.0-1.0)")
                    
                    validated_points.append((float(x), float(y)))
                
                # Set the update flag with new points
                self.polygon_points_updated = (True, validated_points)
                
                return {
                    "message": f"Polygon points updated successfully",
                    "points": validated_points,
                    "point_count": len(validated_points),
                    "timestamp": time.time()
                }
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
    
    def update_state(self, current_state: str, presence_duration: float, absence_duration: float, 
                    is_stream_running: bool = True, is_arduino_connected: bool = False, debug_frame:np.ndarray = np.zeros((1,1,3), dtype=np.uint8), current_cooldown_sec: float = 0):
        """
        Update the current state data. Called from main detection loop.
        
        Args:
            current_state: Current detection state
            presence_duration: Human presence duration
            absence_duration: Human absence duration  
            is_stream_running: Stream source status
            is_arduino_connected: Arduino connection status
            current_cooldown_sec: Current cooldown duration in seconds

            debug_frame: Debug frame with drawings
        """

        self.current_state_data = {
            'current_state': current_state,
            'human_presence_duration': presence_duration,
            'human_absence_duration': absence_duration,
            'is_stream_running': is_stream_running,
            'is_arduino_connected': is_arduino_connected,
            'timestamp': time.time(),
            'current_cooldown_sec': current_cooldown_sec
        }

        self.debug_frame = debug_frame
    
    def get_and_clear_relay_trigger(self) -> Optional[int]:
        """
        Get the relay trigger pin and clear it.
        
        Returns:
            int: Pin number to trigger, or None if no trigger pending
        """
        if self.relay_trigger_pin is not None:
            pin = self.relay_trigger_pin
            self.relay_trigger_pin = None  # Clear after getting
            return pin
        return None
    
    def get_and_clear_polygon_update(self) -> Tuple[bool, Optional[list]]:
        """
        Get the polygon points update flag and new points, then clear the flag.
        
        Returns:
            tuple: (is_updated, new_polygon_points) where is_updated is bool and 
                   new_polygon_points is list of tuples or None
        """
        if self.polygon_points_updated[0]:  # If update flag is True
            is_updated, new_points = self.polygon_points_updated
            self.polygon_points_updated = (False, None)  # Clear after getting
            return is_updated, new_points
        return False, None
    
    def start_server(self):
        """Start the FastAPI server in a separate thread."""
        if self.is_running:
            print("API server is already running.")
            return
            
        def run_server():
            self.is_running = True
            print(f"Starting Human Presence Detection API server on {self.host}:{self.port}")
            uvicorn.run(self.app, host=self.host, port=self.port, log_level="info")
            
        self.server_thread = threading.Thread(target=run_server, daemon=True)
        self.server_thread.start()
        
        # Give server time to start
        time.sleep(2)
        print(f"API server started successfully!")
        print(f"Access API at: http://{self.host}:{self.port}")
        print(f"API documentation: http://{self.host}:{self.port}/docs")
        
    def stop_server(self):
        """Stop the API server."""
        self.is_running = False
        print("API server stopped.")


if __name__ == "__main__":
    # Example usage
    from human_presence_detector import HumanPresenceDetector
    from streamer_modules.webcam_streamer import WebcamStreamer
    
    detector = HumanPresenceDetector()
    stream_source = WebcamStreamer()
    
    api_server = StateAPIServer(detector, stream_source, port=8000)
    api_server.start_server()
    
    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        api_server.stop_server()