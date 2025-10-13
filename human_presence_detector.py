from ultralytics import YOLO
import cv2, time
import numpy as np

from typing import List, Tuple, Optional

class HumanPresenceDetector:
    def __init__(self,                  
            model_name="yolov8n.pt",
            conf_threshold=0.3,
            t1_threshold=2.0,
            t2_threshold=2.0,
            polygon_points = [0.0,0.0, 1.0,0.0, 1.0,1.0, 0.0,1.0],
        ):
        """
        Args:
            model_name (str): Path or name of YOLO model.
            conf_threshold (float): Minimum confidence for detection
            t1_threshold (float): Duration to transition from absent to changing_to_present.
            t2_threshold (float): Duration to transition from present to changing_to_absent.
            polygon_points: List of polygon points for detection area.
        """
        self.model = YOLO(model_name)
        self.conf_threshold = conf_threshold
        self.polygon_points = polygon_points
        
        # Transition thresholds
        self.t1_threshold = t1_threshold  # Time to confirm presence
        self.t2_threshold = t2_threshold  # Time to confirm absence

        # State management
        self.current_state = "human_absent"  # Initial state
        
        # Counters
        self.human_presence_duration = 0.0
        self.human_absence_duration = 0.0
        
        # Timing variables
        self.state_start_time = time.time()
        self.last_detection_time = None

    def is_polygons_intersecting(self, polygon1: List[Tuple[float, float]], polygon2: List[Tuple[float, float]]) -> bool:
        """
        Robust polygon intersection check for simple polygons (convex or concave).
        Touching (edge/vertex) counts as intersecting. Works with ints or floats.
        """

        # ---- inline helpers ----
        def edges(poly):
            n = len(poly)
            for i in range(n):
                yield poly[i], poly[(i + 1) % n]

        def aabb(poly):
            xs = [p[0] for p in poly]; ys = [p[1] for p in poly]
            return min(xs), min(ys), max(xs), max(ys)

        def aabb_overlaps(p1, p2):
            minx1, miny1, maxx1, maxy1 = aabb(p1)
            minx2, miny2, maxx2, maxy2 = aabb(p2)
            return not (maxx1 < minx2 or maxx2 < minx1 or maxy1 < miny2 or maxy2 < miny1)

        def orient(a, b, c):
            # cross((b-a), (c-a))
            return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

        def on_segment(a, b, p):
            return (min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and
                    min(a[1], b[1]) <= p[1] <= max(a[1], b[1]))

        def segments_intersect(p1, p2, q1, q2):
            o1 = orient(p1, p2, q1)
            o2 = orient(p1, p2, q2)
            o3 = orient(q1, q2, p1)
            o4 = orient(q1, q2, p2)

            # Proper intersection
            if (o1 > 0 and o2 < 0 or o1 < 0 and o2 > 0) and \
            (o3 > 0 and o4 < 0 or o3 < 0 and o4 > 0):
                return True

            # Colinear/touching cases
            if o1 == 0 and on_segment(p1, p2, q1): return True
            if o2 == 0 and on_segment(p1, p2, q2): return True
            if o3 == 0 and on_segment(q1, q2, p1): return True
            if o4 == 0 and on_segment(q1, q2, p2): return True
            return False

        def point_in_polygon(pt, poly):
            # boundary check first
            for a, b in edges(poly):
                if orient(a, b, pt) == 0 and on_segment(a, b, pt):
                    return True

            x, y = pt
            inside = False
            n = len(poly)
            for i in range(n):
                x1, y1 = poly[i]
                x2, y2 = poly[(i + 1) % n]
                # Check if edge straddles horizontal line at y
                if (y1 > y) != (y2 > y):
                    xinters = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                    if xinters == x:    # exactly on the ray
                        return True
                    if xinters > x:
                        inside = not inside
            return inside
        # ---- end helpers ----

        if not polygon1 or not polygon2:
            return False

        # 1) Quick reject
        if not aabb_overlaps(polygon1, polygon2):
            return False

        # 2) Any edge pair intersects?
        for a1, a2 in edges(polygon1):
            for b1, b2 in edges(polygon2):
                if segments_intersect(a1, a2, b1, b2):
                    return True

        # 3) Containment
        if point_in_polygon(polygon1[0], polygon2): return True
        if point_in_polygon(polygon2[0], polygon1): return True

        return False
    
    #    def draw_debug_info(self, frame, human_bboxes, polygon_points, current_state):

    def draw_debug_frame(self, frame, human_bboxes: List, polygon_points: List[Tuple[int, int]], current_state: str):
        """Draw bounding boxes and polygon for debugging."""
        copied_frame = frame.copy()

        for box in human_bboxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cv2.rectangle(copied_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(copied_frame, f"Person: {box.conf[0]:.2f}", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)


        color_map = {
            "human_absent": (255, 0, 0),           # Blue
            "changing_to_present": (0, 255, 255),  # Yellow
            "human_present": (0, 0, 255),          # Red
            "changing_to_absent": (255, 0, 255)    # Magenta
        }
        color = color_map.get(current_state, (255, 255, 255))
        polygon_points = [ (int(x * copied_frame.shape[1]), int(y * copied_frame.shape[0])) for x, y in self.polygon_points ] 
        cv2.polylines(copied_frame, [np.array(polygon_points)], isClosed=True, color=color, thickness=2)
        
        cv2.putText(copied_frame, f"State: {current_state}s", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(copied_frame, f"Presence Duration: {self.human_presence_duration:.1f}s", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        cv2.putText(copied_frame, f"Absence Duration: {self.human_absence_duration:.1f}s", (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        return copied_frame
    
    def detect(self, frame):
        """
        Detect human presence in the given frame and update state machine.
        
        Args:
            frame (np.ndarray): Image in OpenCV BGR format.
        
        Returns:
            tuple: (current_state, human_presence_duration, human_absence_duration)
        """
        results = self.model.predict(frame, conf=self.conf_threshold, verbose=False)

        # first class is 'person' in COCO dataset. You can print classnames via: print(self.model.names)
        human_bboxes = [box for box in results[0].boxes if int(box.cls[0]) == 0 and box.conf[0] >= self.conf_threshold]
        
        polygon_points = [ (int(x * frame.shape[1]), int(y * frame.shape[0])) for x, y in self.polygon_points ] 

        # Check if any human bbox intersects with the polygon (if defined)
        human_detected = any(
            self.is_polygons_intersecting(
                polygon_points,
                [
                    (int(box.xyxy[0][0]), int(box.xyxy[0][1])),
                    (int(box.xyxy[0][2]), int(box.xyxy[0][1])),
                    (int(box.xyxy[0][2]), int(box.xyxy[0][3])),
                    (int(box.xyxy[0][0]), int(box.xyxy[0][3])),
                ]
            ) for box in human_bboxes
        )
        
        now = time.time()
        time_in_current_state = now - self.state_start_time
        
        # State machine logic
        if self.current_state == "human_absent":
            if human_detected:
                self._transition_to_state("changing_to_present", now)
            else:
                self.human_absence_duration += time_in_current_state
                self._reset_state_timer(now)
                
        elif self.current_state == "changing_to_present":
            if human_detected:
                if time_in_current_state >= self.t1_threshold:
                    self._transition_to_state("human_present", now)
            else:
                self._transition_to_state("human_absent", now)
                
        elif self.current_state == "human_present":
            if human_detected:
                self.human_presence_duration += time_in_current_state
                self._reset_state_timer(now)
            else:
                self._transition_to_state("changing_to_absent", now)
                
        elif self.current_state == "changing_to_absent":
            if human_detected:
                self._transition_to_state("human_present", now)
            else:
                if time_in_current_state >= self.t2_threshold:
                    self._transition_to_state("human_absent", now)

        debug_frame = self.draw_debug_frame(frame, human_bboxes, polygon_points, self.current_state)
        return self.current_state, self.human_presence_duration, self.human_absence_duration, debug_frame   
    
    def _transition_to_state(self, new_state: str, timestamp: float):
        """Transition to a new state and reset the timer."""
        old_state = self.current_state
        
        # Reset counters when transitioning between presence/absence states
        if old_state in ["human_absent", "changing_to_present"] and new_state in ["human_present", "changing_to_absent"]:
            # Transitioning from absence to presence - reset absence counter
            self.human_absence_duration = 0.0
        elif old_state in ["human_present", "changing_to_absent"] and new_state in ["human_absent", "changing_to_present"]:
            # Transitioning from presence to absence - reset presence counter
            self.human_presence_duration = 0.0
            
        self.current_state = new_state
        self.state_start_time = timestamp
        
    def _reset_state_timer(self, timestamp: float):
        """Reset the timer for the current state without changing state."""
        self.state_start_time = timestamp
    
    def get_state_info(self) -> dict:
        """
        Get comprehensive state information.
        
        Returns:
            dict: Current state, durations, and timing information
        """
        now = time.time()
        return {
            'current_state': self.current_state,
            'human_presence_duration': self.human_presence_duration,
            'human_absence_duration': self.human_absence_duration,
            'time_in_current_state': now - self.state_start_time,
            't1_threshold': self.t1_threshold,
            't2_threshold': self.t2_threshold
        }

