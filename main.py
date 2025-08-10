import cv2
from human_presence_detector import HumanPresenceDetector

if __name__ == "__main__":
    detector:HumanPresenceDetector = HumanPresenceDetector(model_name="yolov8n.pt", conf_threshold=0.5, reset_time=3.0)

    # open a webcam stream
    cap = cv2.VideoCapture(1)
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        exit()

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error: Could not read frame.")
            break

        # Detect human presence
        human_detected, presence_duration = detector.detect(frame)

        # State logic
        if presence_duration == 0:
            state = "no_human"
        elif presence_duration < 5:
            state = "short_presence"
        else:
            state = "long_presence"

        # Indicate state visually and textually
        if state == "no_human":
            color = (0, 255, 0)
            cv2.putText(frame, "No Human", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        elif state == "short_presence":
            color = (0, 255, 255)
            cv2.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]), color, 10)
            cv2.putText(frame, f"Human Detected: {presence_duration:.1f}s", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            cv2.putText(frame, "State: Short Presence", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        elif state == "long_presence":
            color = (0, 0, 255)
            cv2.rectangle(frame, (0, 0), (frame.shape[1], frame.shape[0]), color, 10)
            cv2.putText(frame, f"Human Detected: {presence_duration:.1f}s", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
            cv2.putText(frame, "Alert! Long Presence", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

        # Display the frame
        cv2.imshow("Human Presence Detection", frame)

        # Break the loop on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break


