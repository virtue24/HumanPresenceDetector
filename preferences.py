from ultralytics import settings
settings.update({"sync": False}) # Disable analytics and crash reporting

STREAM_SOURCE = "webcam"  # Options: "webcam", "rtsp_streamer"
STREAM_SOURCE_KWARGS = {
 "webcam": {     
    "webcam_index": 1  # Default camera index (0 for default webcam, 1 for external, etc.)
 },
 "rtsp_streamer": {
    "ipv4_address": "0.0.0.0",
    "endpoint": "stream",
    "username": "username",
    "password": "password"
 }
}

HUMAN_PRESENCE_DETECTOR_KWARGS = {
    "model_name": "yolov8n.pt",  # Model file name
    "conf_threshold": 0.60,       # Confidence threshold for detections
    "polygon_points": [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75), (0.45, 0.45), (0.123, 0.456)], # Defaulted to whole frame if empty.
    "t1_threshold": 1.0,         # Time in seconds to confirm human presence (absence to presence)
    "t2_threshold": 1.0          # Time in seconds to confirm human absence  (presence to absence)
}

ARDUINO_KWARGS = {
    "baud_rate": 9600,           # Serial baud rate
}
RELAY_KWARGS = {
    "human_presence_pin": 2,    # Pin number connected to relay for human presence
    "human_presence_delay_ms": 0,  # Delay before activating relay (ms)
    "human_presence_duration_ms": 1000,  # Duration to keep relay active (ms)
    "human_absence_pin": 3,   # Pin number connected to relay for human absence
    "human_absence_delay_ms": 0,   # Delay before activating relay (ms)
    "human_absence_duration_ms": 1000  # Duration to keep relay active (ms)
}
    
COOLDOWN_PER_ITERATION = 0.100  # Cooldown time between loop iterations (seconds)
USE_ARDUINO = True            # Whether to use Arduino module.
SHOW_DEBUG_FRAME = False  # Whether to show debug frame with drawings.

# VALIDATION ======================
# Basic validation of preferences
if STREAM_SOURCE not in STREAM_SOURCE_KWARGS.keys():
    raise ValueError(f"Invalid STREAM_SOURCE '{STREAM_SOURCE}'. Must be one of {list(STREAM_SOURCE_KWARGS.keys())}.")

# Validate polygon points
for x, y in HUMAN_PRESENCE_DETECTOR_KWARGS["polygon_points"]:
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        raise ValueError(f"Polygon point ({x}, {y}) must be normalized between 0 and 1.")
    
