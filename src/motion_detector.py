import cv2
import logging
import numpy as np

from config.settings import (
    MOTION_CANNY_THRESHOLD_LOW,
    MOTION_CANNY_THRESHOLD_HIGH,
    MOTION_CHANGED_PIXELS_THRESHOLD,
    MOTION_DOWNSCALE,
)

logger = logging.getLogger(__name__)


class MotionDetector:
    """
    Edge-based motion detection resilient to lighting changes.
    Compares Canny edge maps of consecutive frames.
    """

    def __init__(
        self,
        canny_low=MOTION_CANNY_THRESHOLD_LOW,
        canny_high=MOTION_CANNY_THRESHOLD_HIGH,
        pixel_threshold=MOTION_CHANGED_PIXELS_THRESHOLD,
        downscale=MOTION_DOWNSCALE,
    ):
        self.canny_low = canny_low
        self.canny_high = canny_high
        self.pixel_threshold = pixel_threshold
        self.downscale = downscale
        self.prev_edges = None

    def detect(self, frame):
        """Return True if enough edges changed since the previous frame."""
        if frame is None:
            return False

        # Motion runs on every frame, so shrink first: the change metric is a
        # percentage, so sensitivity is unaffected.
        if 0 < self.downscale < 1.0:
            frame = cv2.resize(
                frame, None, fx=self.downscale, fy=self.downscale,
                interpolation=cv2.INTER_AREA,
            )

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, self.canny_low, self.canny_high)

        prev, self.prev_edges = self.prev_edges, edges
        if prev is None or prev.shape != edges.shape:
            return False

        change_percentage = np.count_nonzero(cv2.absdiff(prev, edges)) / edges.size * 100
        is_motion = bool(change_percentage > self.pixel_threshold)
        if is_motion:
            logger.debug(
                "Motion: %.2f%% edges changed (threshold %.2f%%)",
                change_percentage, self.pixel_threshold,
            )
        return is_motion
