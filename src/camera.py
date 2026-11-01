import cv2
import logging
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

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
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 3

    def start(self):
        """Open camera and warm up."""
        try:
            selected_camera_id = self._choose_camera_id()
            self.camera_id = selected_camera_id
            logger.info(f"Opening camera {self.camera_id}...")
            # Use DirectShow backend on Windows for better compatibility
            backend = cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY
            self.cap = cv2.VideoCapture(self.camera_id, backend)
            if not self.cap.isOpened():
                raise RuntimeError(f"Failed to open camera {self.camera_id}")

            self._configure()
            self.is_active = True
            logger.info(f"Camera started: ID={self.camera_id}")

            # Warm up camera (discard first N frames)
            for _ in range(CAMERA_WARMUP_FRAMES):
                self.cap.read()
            logger.debug(f"Camera warmup complete ({CAMERA_WARMUP_FRAMES} frames discarded)")

        except Exception as e:
            logger.error(f"Error starting camera: {e}")
            self.is_active = False
            raise

    def _configure(self):
        """Apply format, size and frame rate, then log what the driver actually gave us."""
        # MJPG first: webcams often reach 720p at 30 fps only compressed (this one does 10 fps in YUYV).
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
        self.cap.set(cv2.CAP_PROP_FPS, self.fps)

        # Keep only the newest frame in the driver buffer. While face analysis
        # runs, no reads happen; without this the driver queues stale frames and
        # every subsequent read lags behind real time.
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._limit_exposure()

        fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, "little").decode(errors="replace")
        logger.info(
            "Camera delivers %dx%d %s at %.0f fps",
            self.cap.get(cv2.CAP_PROP_FRAME_WIDTH), self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT),
            fourcc, self.cap.get(cv2.CAP_PROP_FPS),
        )

    def _limit_exposure(self):
        """Stop the camera lowering its frame rate for longer exposures in dim light; those smear moving faces."""
        if not sys.platform.startswith("linux"):
            return
        try:
            result = subprocess.run(
                ["v4l2-ctl", "-d", f"/dev/video{self.camera_id}", "-c", "exposure_dynamic_framerate=0"],
                capture_output=True, timeout=5,
            )
            if result.returncode:
                logger.debug("Camera has no exposure_dynamic_framerate control: %s", result.stderr.decode().strip())
        except (OSError, subprocess.SubprocessError) as e:
            logger.debug("Could not run v4l2-ctl: %s", e)

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
        """Probe for camera indices greater than zero in parallel."""
        indices_to_check = list(range(1, max_devices))
        
        with ThreadPoolExecutor(max_workers=len(indices_to_check)) as executor:
            # Submit all probe tasks
            future_to_index = {
                executor.submit(FrameCapture._probe_camera, index): index 
                for index in indices_to_check
            }
            
            # Check results with timeout, prioritizing lower camera indices
            # Sort by camera index to ensure deterministic selection
            for future, index in sorted(future_to_index.items(), key=lambda x: x[1]):
                try:
                    if future.result(timeout=2.0):  # 2 second timeout per probe
                        return index
                except (FuturesTimeout, Exception) as e:
                    logger.debug(f"Probe timeout/error for camera {index}: {e}")
                    continue
        
        return None

    @staticmethod
    def _probe_camera(index):
        # Use DirectShow backend on Windows for faster detection
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
                
                # Attempt reconnection
                if self._reconnect_attempts < self._max_reconnect_attempts:
                    logger.info(f"Attempting camera reconnection ({self._reconnect_attempts + 1}/{self._max_reconnect_attempts})")
                    if self._reconnect():
                        return None, None  # Return None this frame, next frame should work
                
                return None, None

            # Reset reconnect counter on successful read
            self._reconnect_attempts = 0
            
            self.latest_frame = frame
            self.frame_count += 1
            return frame, self.frame_count

        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            return None, None

    def _reconnect(self):
        """Attempt to reconnect to the camera."""
        self._reconnect_attempts += 1
        
        try:
            logger.info("Releasing current camera connection...")
            if self.cap is not None:
                self.cap.release()
            
            time.sleep(1)  # Brief pause
            
            logger.info(f"Reopening camera {self.camera_id}...")
            backend = cv2.CAP_DSHOW if sys.platform == 'win32' else cv2.CAP_ANY
            self.cap = cv2.VideoCapture(self.camera_id, backend)
            
            if not self.cap.isOpened():
                raise RuntimeError(f"Failed to reopen camera {self.camera_id}")
            
            self._configure()

            logger.info("Camera reconnected successfully")
            self.is_active = True
            return True
            
        except Exception as e:
            logger.error(f"Camera reconnection failed: {e}")
            if self._reconnect_attempts >= self._max_reconnect_attempts:
                logger.critical("Max reconnection attempts reached. Camera unavailable.")
                self.is_active = False
            return False

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
