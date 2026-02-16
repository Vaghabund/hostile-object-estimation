import cv2
import time
import logging
import numpy as np
from config.settings import (
    MOTION_CANNY_THRESHOLD_LOW,
    MOTION_CANNY_THRESHOLD_HIGH,
    MOTION_CHANGED_PIXELS_THRESHOLD,
    MOTION_COOLDOWN_SECONDS
)

logger = logging.getLogger(__name__)


class MotionDetector:
    """
    Edge-based motion detection resilient to lighting changes.
    Compares Canny edge maps of consecutive frames.
    """

    def __init__(self):
        self.last_detection_time = 0
        self.prev_edges = None
        self.initialized = False

    def detect(self, frame):
        """
        Detect motion in the current frame compared to the previous frame.

        Args:
            frame: The current video frame (numpy array)

        Returns:
            bool: True if motion detected, False otherwise
        """
        if frame is None:
            return False

        # Convert to grayscale for edge detection
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Apply Canny edge detection
        edges = cv2.Canny(
            gray, 
            MOTION_CANNY_THRESHOLD_LOW, 
            MOTION_CANNY_THRESHOLD_HIGH
        )

        # If this is the first frame, just store it and return
        if not self.initialized:
            self.prev_edges = edges
            self.initialized = True
            return False

        # Check cooldown
        current_time = time.time()
        if (current_time - self.last_detection_time) < MOTION_COOLDOWN_SECONDS:
            # Still update reference frame during cooldown to avoid stale comparisons
            self.prev_edges = edges
            return False

        # Calculate absolute difference between edge maps
        if self.prev_edges is None:
            self.prev_edges = edges
            return False

        # This highlights edges that have moved or appeared/disappeared
        edge_diff = cv2.absdiff(self.prev_edges, edges)

        # Count non-zero pixels (changed edges)
        changed_pixels = np.count_nonzero(edge_diff)
        
        # Calculate percentage of changed pixels relative to total resolution
        total_pixels = edge_diff.size
        change_percentage = (changed_pixels / total_pixels) * 100

        is_motion = change_percentage > MOTION_CHANGED_PIXELS_THRESHOLD

        if is_motion:
            logger.info(
                f"Motion detected! Change: {change_percentage:.2f}% "
                f"(Threshold: {MOTION_CHANGED_PIXELS_THRESHOLD}%)"
            )
            self.last_detection_time = current_time

        # Update previous frame state
        self.prev_edges = edges

        return is_motion
