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
# Downscale factor applied before grayscale+Canny. Motion runs on 100% of frames,
# so shrinking here is the single biggest per-frame CPU win. The threshold is a
# percentage of pixels, so sensitivity is unaffected. 0.5 => ~4x less work.
MOTION_DOWNSCALE = float(os.getenv("MOTION_DOWNSCALE", "0.5"))

# ============================================================================
# YOLO Configuration
# ============================================================================
YOLO_MODEL = "yolov8n"  # Lightweight model
YOLO_CONFIDENCE_THRESHOLD = float(os.getenv("YOLO_CONFIDENCE", "0.5"))
YOLO_ENABLE_TRACKING = True
# Use an OpenVINO-exported model for ~2-3x faster CPU inference on Intel hardware.
# The model is exported once on first run; falls back to the PyTorch .pt if OpenVINO
# is unavailable or export fails, so the app always starts.
YOLO_USE_OPENVINO = _str_to_bool(os.getenv("YOLO_USE_OPENVINO", "true"))

# ============================================================================
# CPU / Threading
# ============================================================================
# Cap OpenCV + PyTorch worker threads. On weak/old CPUs, letting both libraries
# spin up all cores oversubscribes the machine (motion encode in alert threads vs
# YOLO in the main loop). Defaults to all logical cores; set lower (e.g. 2) on
# shared or very old boxes.
CPU_THREADS = int(os.getenv("CPU_THREADS", str(os.cpu_count() or 1)))

# ============================================================================
# Data Management
# ============================================================================
DETECTION_HISTORY_MAXLEN = 500  # Auto-purge old detections (sufficient for 24h at 1 detection/min)
TELEGRAM_IMAGE_QUALITY = 60  # JPEG quality for Telegram (0-100)
DETECTION_STABILITY_FRAMES = int(os.getenv("DETECTION_STABILITY_FRAMES", "2"))
DETECTION_STABILITY_MAX_MISSES = int(os.getenv("DETECTION_STABILITY_MAX_MISSES", "2"))

# ============================================================================
# Frame Post-Processing (Best-Frame Selection) - ENABLED BY DEFAULT
# ============================================================================
# Smart frame selection to reduce blur in Telegram images
# Automatically selects the sharpest, clearest frame from detection sequences
# Hierarchy: face detection > sharpness (Laplacian variance) > confidence score
FRAME_SELECTION_ENABLED = _str_to_bool(os.getenv("FRAME_SELECTION_ENABLED", "true"))
FRAME_SELECTION_MODE = {
    "alerts": _str_to_bool(os.getenv("FRAME_SELECTION_ALERTS", "true")),    # Dual alerts: confirmation + best frame on track end
    "scan": _str_to_bool(os.getenv("FRAME_SELECTION_SCAN", "true")),        # /scan command uses best frame
    "summary": _str_to_bool(os.getenv("FRAME_SELECTION_SUMMARY", "true")),  # /summary uses one best frame per track
}

# Face detection settings
FACE_DETECTOR_TYPE = os.getenv("FACE_DETECTOR_TYPE", "cascade")  # "cascade" for OpenCV Haar Cascade
FACE_DETECTOR_MIN_SIZE = (30, 30)  # Minimum face size to detect (width, height)

# Scoring weights for frame selection (face weight is highest priority)
FRAME_SELECTION_FACE_WEIGHT = float(os.getenv("FRAME_SCORE_FACE_WEIGHT", "1.0"))      # Highest priority: face detection
FRAME_SELECTION_SHARPNESS_WEIGHT = float(os.getenv("FRAME_SCORE_SHARPNESS_WEIGHT", "0.8"))  # Medium priority: image clarity
FRAME_SELECTION_CONFIDENCE_WEIGHT = float(os.getenv("FRAME_SCORE_CONFIDENCE_WEIGHT", "0.5"))  # Lowest priority: detection confidence

# Frame buffering settings
# Each buffered frame is a full 640x480x3 array (~0.9 MB), kept per track_id.
# 150 => ~135 MB/track, so keep this modest. Best-frame selection subsamples
# anyway (FRAME_SELECTION_MAX_SCORED), so a large buffer buys little.
FRAME_BUFFER_MAX_FRAMES_PER_TRACK = int(os.getenv("FRAME_BUFFER_MAX", "30"))  # Max frames to buffer per track_id before earliest are purged
# Cap how many buffered frames the quality scorer evaluates (Haar cascade is the
# bottleneck). Frames are sampled evenly across the buffer.
FRAME_SELECTION_MAX_SCORED = int(os.getenv("FRAME_SELECTION_MAX_SCORED", "18"))
# Downscale width (px) used before the Haar cascade during scoring. Face presence
# is binary, so full resolution is wasted here. 0 disables downscaling.
FRAME_SELECTION_FACE_MAX_WIDTH = int(os.getenv("FRAME_SELECTION_FACE_MAX_WIDTH", "320"))

# ============================================================================
# Logging
# ============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
