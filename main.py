import preferences
import cv2, time

# Initialize FastAPI server
from api_server import StateAPIServer

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

# Initialize and start FastAPI server
api_server = StateAPIServer(detector, stream_source, host="0.0.0.0", port=preferences.BACKEND_SERVER_PORT) # Listen on all interfaces
api_server.start_server()

# Import Arduino module if enabled
arduino_module = None
if preferences.USE_ARDUINO:
    from arduino_module import ArduinoController
    arduino_module = ArduinoController(**preferences.ARDUINO_KWARGS)

# Start 
current_cooldown_sec = preferences.COOLDOWN_RANGE_PER_ITERATION[0]
while True:
    detection_start_time = time.time()
    if stream_source.is_running():
        frame, timestamp = stream_source.get_frame_with_timestamp()
        if frame is None:
            continue        

        # Detect human presence
        current_state, human_presence_duration, human_absence_duration, debug_frame = detector.detect(frame)   
        
        # Update API server state (without altering the loop)
        api_server.update_state(
            current_state=current_state,
            presence_duration=human_presence_duration,
            absence_duration=human_absence_duration,
            is_stream_running=stream_source.is_running(),
            is_arduino_connected= arduino_module is not None and arduino_module.is_connected(),
            debug_frame=debug_frame,
            current_cooldown_sec=current_cooldown_sec
        )

        # Check for polygon points update from API
        is_polygon_updated, new_polygon_points = api_server.get_and_clear_polygon_update()
        if is_polygon_updated and new_polygon_points is not None:
            print(f"API polygon update: {len(new_polygon_points)} points")
            detector.update_polygon_points(new_polygon_points)
            
            # Save to file
            try:
                with open(preferences.POLYGON_POINTS_FILE, 'w') as f:
                    f.write("\n".join([f"{x},{y}" for x, y in new_polygon_points]))
                print(f"Polygon points saved to {preferences.POLYGON_POINTS_FILE}")
            except Exception as e:
                print(f"Error saving polygon points: {e}")

        # Determine if slow down or speed up the loop based on is human presence detected (To reduce CPU usage when no one is around, to protect device lifespan and lower the temperature)
        if current_state in ["human_present", "changing_to_present", "changing_to_absent"]:
            current_cooldown_sec = preferences.COOLDOWN_RANGE_PER_ITERATION[0]  # Reset cooldown to minimum
        elif current_state == "human_absent":
            current_cooldown_sec = min(current_cooldown_sec + preferences.COOLDOWN_INCEMENT_PER_ITERATION, preferences.COOLDOWN_RANGE_PER_ITERATION[1])
        detection_end_time = time.time()
        detection_duration = detection_end_time - detection_start_time
        # Handle Arduino relay control if module is available
        if arduino_module:
            _relay_on_duration_ms = 1000* (current_cooldown_sec + preferences.RELAY_ON_TIME_ADJUSTMENT_SEC + detection_duration)

            # Check for API relay trigger requests (For testing, this is useful)
            trigger_pin = api_server.get_and_clear_relay_trigger()
            if trigger_pin is not None:
                response = arduino_module.relay_on_overwrite(pin=trigger_pin, duration_ms=_relay_on_duration_ms)

            # Always set system is working fine pin high if possible (to indicate the system is operational)
            # At this point, it is known that both the streamer, relay module and detector are working fine. 
            arduino_module.relay_on_overwrite(pin=preferences.RELAY_KWARGS['system_is_working_fine_pin'], duration_ms = _relay_on_duration_ms)

            # If Human Present, set relay for presence pin
            if current_state == "human_present":
                response = arduino_module.relay_on_overwrite(pin=preferences.RELAY_KWARGS['human_presence_pin'], duration_ms=_relay_on_duration_ms)

            # If changing state, set both pins to ensure correct state
            elif current_state == "changing_to_absent" or current_state == "changing_to_present":
                response_1 = arduino_module.relay_on_overwrite(pin=preferences.RELAY_KWARGS['human_presence_pin'], duration_ms=_relay_on_duration_ms)
                response_2 = arduino_module.relay_on_overwrite(pin=preferences.RELAY_KWARGS['human_absence_pin'], duration_ms=_relay_on_duration_ms)
            
            # If Human Absent, set relay for absence pin
            elif current_state == "human_absent":
                response = arduino_module.relay_on_overwrite(pin=preferences.RELAY_KWARGS['human_absence_pin'], duration_ms=_relay_on_duration_ms)
        
        time.sleep(current_cooldown_sec) # Cooldown to reduce CPU usage

        # Show debug frame if enabled
        if preferences.SHOW_DEBUG_FRAME and debug_frame is not None:
            cv2.imshow("Stream", debug_frame)
            cv2.waitKey(1)            
    else:
        print("Stream source is not running.")
        api_server.update_state(
            current_state="streamer_not_running",
            presence_duration=0,
            absence_duration=0,
            is_stream_running=stream_source.is_running(),
            is_arduino_connected= arduino_module is not None and arduino_module.is_connected(),
            debug_frame=debug_frame,
            current_cooldown_sec=1
        )
        time.sleep(1)

