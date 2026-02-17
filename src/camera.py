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
    PREFER_EXTERNAL_CAMERA,
    CAMERA_PROBE_LIMIT,
)

logger = logging.getLogger(__name__)


class FrameCapture:
    """
    Thread-safe frame capture from webcam using OpenCV.
    Stores the latest frame for access by other threads.
    """

    def __init__(
        self,
        camera_id=CAMERA_ID,
        resolution=CAMERA_RESOLUTION,
        fps=CAMERA_FPS,
        prefer_external=PREFER_EXTERNAL_CAMERA,
    ):
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
        self.prefer_external = prefer_external
        self.cap = None
        self.latest_frame = None
        self.frame_count = 0
        self.is_active = False

    def start(self):
        """Open camera and warm up."""
        try:
            selected_camera_id = self._choose_camera_id()
            self.camera_id = selected_camera_id
            logger.info(f"Opening camera {self.camera_id}...")
            # Use DirectShow backend on Windows for better compatibility
            import sys
            backend = cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY
            self.cap = cv2.VideoCapture(self.camera_id, backend)
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

    def _choose_camera_id(self):
        """Select the best available camera based on preference."""
        if not self.prefer_external:
            return self.camera_id

        logger.info(f"Scanning for external USB cameras (checking up to {CAMERA_PROBE_LIMIT - 1} devices)...")
        external_id = self._find_external_camera(CAMERA_PROBE_LIMIT)
        if external_id is not None:
            logger.info(f"External USB camera detected at index {external_id}. Using it.")
            return external_id

        logger.info("No external USB camera found. Using default camera index %s", self.camera_id)
        return self.camera_id

    @staticmethod
    def _find_external_camera(max_devices=3):
        """Probe for camera indices greater than zero."""
        for index in range(1, max_devices):
            logger.debug(f"Probing camera index {index}...")
            if FrameCapture._probe_camera(index):
                return index
        return None

    @staticmethod
    def _probe_camera(index):
        # Use DirectShow backend on Windows for faster detection
        import sys
        backend = cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY
        cap = cv2.VideoCapture(index, backend)
        try:
            if not cap.isOpened():
                return False
            # Set a short timeout for the read operation
            cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            ret, _ = cap.read()
            return ret
        finally:
            cap.release()

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
