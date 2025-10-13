import preferences
import cv2, time


# Initialize the appropriate stream source based on user preferences
stream_source = None
if preferences.STREAM_SOURCE == "webcam":
    from streamer_modules.webcam_streamer import WebcamStreamer
    stream_source = WebcamStreamer(**preferences.STREAM_SOURCE_KWARGS["webcam"])
    stream_source.start()

elif preferences.STREAM_SOURCE == "rtsp_streamer":
    from streamer_modules.rtsp_streamer import RTSPStreamer
    stream_source = RTSPStreamer(**preferences.STREAM_SOURCE_KWARGS["rtsp_streamer"])

# ınitialize the human presence detector
from human_presence_detector import HumanPresenceDetector
detector = HumanPresenceDetector(**preferences.HUMAN_PRESENCE_DETECTOR_KWARGS)

# Start 
while True:
    if stream_source.is_running():
        frame, timestamp = stream_source.get_frame_with_timestamp()
        if frame is None:
            continue        

        # Detect human presence
        current_state, human_presence_duration, human_absence_duration, debug_frame = detector.detect(frame)   
        
        # Show debug frame if enabled
        if preferences.SHOW_DEBUG_FRAME and debug_frame is not None:
            cv2.imshow("Stream", debug_frame)
            cv2.waitKey(1)            
    else:
        print("Stream source is not running.")
        time.sleep(1)

