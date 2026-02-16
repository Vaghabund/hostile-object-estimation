import cv2
import logging
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import (
    CAMERA_ID,
    CAMERA_RESOLUTION,
    CAMERA_FPS,
    CAMERA_WARMUP_FRAMES,
)

logger = logging.getLogger(__name__)


class FrameCapture:
    """
    Thread-safe frame capture from webcam using OpenCV.
    Stores the latest frame for access by other threads.
    """

    def __init__(self, camera_id=CAMERA_ID, resolution=CAMERA_RESOLUTION, fps=CAMERA_FPS):
        """
        Initialize frame capture.

        Args:
            camera_id: OpenCV camera ID (default: 0 for first camera)
            resolution: (width, height) tuple
            fps: Target frames per second
        """
        self.camera_id = camera_id
        self.resolution = resolution
        self.fps = fps
        self.cap = None
        self.latest_frame = None
        self.frame_count = 0
        self.is_active = False

    def start(self):
        """Open camera and warm up."""
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
            if not self.cap.isOpened():
                raise RuntimeError(f"Failed to open camera {self.camera_id}")

            # Set resolution
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
            
            # Set FPS
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)

            self.is_active = True
            logger.info(
                f"Camera started: ID={self.camera_id}, "
                f"resolution={self.resolution}, fps={self.fps}"
            )

            # Warm up camera (discard first N frames)
            for _ in range(CAMERA_WARMUP_FRAMES):
                self.cap.read()
            logger.debug(f"Camera warmup complete ({CAMERA_WARMUP_FRAMES} frames discarded)")

        except Exception as e:
            logger.error(f"Error starting camera: {e}")
            self.is_active = False
            raise

    def get_frame(self):
        """
        Capture and return the latest frame.

        Returns:
            tuple: (frame, timestamp) or (None, None) if capture fails
        """
        if not self.is_active or self.cap is None:
            return None, None

        try:
            ret, frame = self.cap.read()
            if not ret:
                logger.warning("Failed to read frame from camera")
                return None, None

            self.latest_frame = frame
            self.frame_count += 1
            return frame, self.frame_count

        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            return None, None

    def get_latest_frame(self):
        """Get the most recent frame without capturing a new one."""
        return self.latest_frame

    def stop(self):
        """Release camera resources."""
        if self.cap is not None:
            self.cap.release()
            self.is_active = False
            logger.info("Camera stopped")

    def __del__(self):
        """Cleanup on object destruction."""
        self.stop()
