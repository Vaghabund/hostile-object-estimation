import os
from pathlib import Path
from dotenv import load_dotenv


def _str_to_bool(value: str) -> bool:
	return value.strip().lower() in {"1", "true", "yes", "on"}

# Load environment variables from .env file
ENV_FILE = Path(__file__).parent.parent / ".env"
load_dotenv(ENV_FILE)

# ============================================================================
# Telegram Configuration
# ============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
AUTHORIZED_USER_ID = os.getenv("AUTHORIZED_USER_ID", "")

# ============================================================================
# Camera Configuration
# ============================================================================
CAMERA_ID = int(os.getenv("CAMERA_ID", "0"))
CAMERA_RESOLUTION = (640, 480)  # (width, height)
CAMERA_FPS = 30
CAMERA_WARMUP_FRAMES = 5  # Discard first N frames to let camera stabilize
PREFER_EXTERNAL_CAMERA = _str_to_bool(os.getenv("PREFER_EXTERNAL_CAMERA", "true"))
CAMERA_PROBE_LIMIT = int(os.getenv("CAMERA_PROBE_LIMIT", "3"))  # Max camera indices to check

# ============================================================================
# Motion Detection Configuration
# ============================================================================
MOTION_CANNY_THRESHOLD_LOW = int(os.getenv("MOTION_CANNY_LOW", "50"))
MOTION_CANNY_THRESHOLD_HIGH = int(os.getenv("MOTION_CANNY_HIGH", "150"))
MOTION_CHANGED_PIXELS_THRESHOLD = float(os.getenv("MOTION_PIXEL_THRESHOLD", "0.5"))  # % of pixels changed
MOTION_COOLDOWN_SECONDS = float(os.getenv("MOTION_COOLDOWN", "2.0"))

# ============================================================================
# YOLO Configuration
# ============================================================================
YOLO_MODEL = "yolov8n"  # Lightweight model
YOLO_CONFIDENCE_THRESHOLD = float(os.getenv("YOLO_CONFIDENCE", "0.5"))
YOLO_ENABLE_TRACKING = True

# ============================================================================
# Data Management
# ============================================================================
DETECTION_HISTORY_MAXLEN = 1000  # Auto-purge old detections
TELEGRAM_IMAGE_QUALITY = 60  # JPEG quality for Telegram (0-100)
DETECTION_STABILITY_FRAMES = int(os.getenv("DETECTION_STABILITY_FRAMES", "2"))
DETECTION_STABILITY_MAX_MISSES = int(os.getenv("DETECTION_STABILITY_MAX_MISSES", "2"))

# ============================================================================
# Logging
# ============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
