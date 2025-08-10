# human_presence_detector.py
from ultralytics import YOLO
import cv2, time

class HumanPresenceDetector:
    def __init__(self, model_name="yolov8n.pt", conf_threshold=0.3, reset_time=3.0):
        """
        Args:
            model_name (str): Path or name of YOLO model.
            conf_threshold (float): Minimum confidence for detection.
            reset_time (float): Seconds without detection before counter resets.
        """
        self.model = YOLO(model_name)
        self.conf_threshold = conf_threshold
        self.reset_time = reset_time

        # Tracking state
        self.start_presence_time = None
        self.last_seen_time = None
        self.presence_duration = 0.0

    def detect(self, frame):
        """
        Detect human presence in the given frame and update duration.
        
        Args:
            frame (np.ndarray): Image in OpenCV BGR format.
        
        Returns:
            (bool, float): Tuple -> (human_detected, presence_duration_seconds)
        """
        results = self.model.predict(frame, conf=self.conf_threshold, verbose=False)
        human_detected = any(int(box.cls[0]) == 0 for box in results[0].boxes)

        now = time.time()

        if human_detected:
            if self.start_presence_time is None:
                self.start_presence_time = now
            self.last_seen_time = now
            self.presence_duration = now - self.start_presence_time
        else:
            if self.last_seen_time and (now - self.last_seen_time) > self.reset_time:
                self.start_presence_time = None
                self.presence_duration = 0.0

        return human_detected, self.presence_duration

