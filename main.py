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
api_server = StateAPIServer(detector, stream_source, host=preferences.IPV4_ADDRESS, port=preferences.BACKEND_SERVER_PORT)
api_server.start_server()

# Import Arduino module if enabled
arduino_module = None
if preferences.USE_ARDUINO:
    from arduino_module import ArduinoController
    arduino_module = ArduinoController(**preferences.ARDUINO_KWARGS)

# Start 

current_cooldown = preferences.COOLDOWN_RANGE_PER_ITERATION[0]
while True:
    time.sleep(current_cooldown) # Cooldown to reduce CPU usage

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
            debug_frame=debug_frame
        )

        if arduino_module:
            # Check for API relay trigger requests
            trigger_pin = api_server.get_and_clear_relay_trigger()
            if trigger_pin is not None:
                print(f"API relay trigger requested for pin {trigger_pin}")
                response = arduino_module.relay_on(pin=trigger_pin, duration_ms=3000)  # 3 second default
                print(f"API relay trigger response: {response}")
            
            # Trigger relay if Human presence detected
            if current_state == "human_present":
                response = arduino_module.relay_on_overwrite(pin=preferences.RELAY_KWARGS['human_presence_pin'], duration_ms=preferences.RELAY_KWARGS['human_presence_duration_ms'])
                current_cooldown = preferences.COOLDOWN_RANGE_PER_ITERATION[0]  # Reset cooldown to minimum
                print(f"Arduino relay response: {response}, current_cooldown: {current_cooldown}")
            elif current_state == "changing_to_absent" or current_state == "changing_to_present":
                response_1 = arduino_module.relay_on_overwrite(pin=preferences.RELAY_KWARGS['human_presence_pin'], duration_ms=preferences.RELAY_KWARGS['human_presence_duration_ms'])
                response_2 = arduino_module.relay_on_overwrite(pin=preferences.RELAY_KWARGS['human_absence_pin'], duration_ms=preferences.RELAY_KWARGS['human_absence_duration_ms'])
                current_cooldown = preferences.COOLDOWN_RANGE_PER_ITERATION[0]  # Reset cooldown to minimum
                print(f"Arduino relay response: {response_1}, {response_2}")
            elif current_state == "human_absent":
                response = arduino_module.relay_on_overwrite(pin=preferences.RELAY_KWARGS['human_absence_pin'], duration_ms=preferences.RELAY_KWARGS['human_absence_duration_ms'])
                current_cooldown = min(current_cooldown + preferences.COOLDOWN_INCEMENT_PER_ITERATION, preferences.COOLDOWN_RANGE_PER_ITERATION[1])
                print(f"Arduino relay response: {response}, current_cooldown: {current_cooldown}")
            elif False:
                #TODO: if test is triggered, do testing then reset flag.
                pass
        
        # Show debug frame if enabled
        if preferences.SHOW_DEBUG_FRAME and debug_frame is not None:
            cv2.imshow("Stream", debug_frame)
            cv2.waitKey(1)            
    else:
        print("Stream source is not running.")
        time.sleep(1)

