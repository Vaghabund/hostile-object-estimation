import os
from pathlib import Path
from dotenv import load_dotenv


def _str_to_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")


def _path(env_name: str, default: str) -> Path:
    p = Path(os.getenv(env_name, default))
    return p if p.is_absolute() else ROOT / p


# ============================================================================
# Camera
# ============================================================================
CAMERA_ID = int(os.getenv("CAMERA_ID", "0"))
CAMERA_RESOLUTION = (640, 480)  # (width, height)
# Low on purpose: fewer frames to decode and motion-check keeps an always-on Pi cool.
CAMERA_FPS = int(os.getenv("CAMERA_FPS", "10"))
CAMERA_WARMUP_FRAMES = 5
PREFER_EXTERNAL_CAMERA = _str_to_bool(os.getenv("PREFER_EXTERNAL_CAMERA", "true"))
CAMERA_PROBE_LIMIT = int(os.getenv("CAMERA_PROBE_LIMIT", "3"))

# ============================================================================
# Motion gate (the cheap check that keeps the face model asleep)
# ============================================================================
MOTION_CANNY_THRESHOLD_LOW = int(os.getenv("MOTION_CANNY_LOW", "50"))
MOTION_CANNY_THRESHOLD_HIGH = int(os.getenv("MOTION_CANNY_HIGH", "150"))
MOTION_CHANGED_PIXELS_THRESHOLD = float(os.getenv("MOTION_PIXEL_THRESHOLD", "0.5"))  # % of pixels
MOTION_DOWNSCALE = float(os.getenv("MOTION_DOWNSCALE", "0.5"))
# After motion, keep looking for faces this long (extended whenever a face is seen).
ACTIVE_WINDOW_SECONDS = float(os.getenv("ACTIVE_WINDOW_SECONDS", "4.0"))

# ============================================================================
# Face analysis + hostility
# ============================================================================
FACE_MODEL_PATH = _path("FACE_MODEL_PATH", "models/face_landmarker.task")
FACE_MIN_WIDTH_PX = int(os.getenv("FACE_MIN_WIDTH_PX", "80"))  # ignore faces smaller than this
# Raw blendshape sums are small even for a good scowl; this scales them to 0-1.
HOSTILITY_GAIN = float(os.getenv("HOSTILITY_GAIN", "2.0"))
# Faces blurrier than this (Laplacian variance of the crop) are not candidates.
FACE_MIN_SHARPNESS = float(os.getenv("FACE_MIN_SHARPNESS", "30"))

# ============================================================================
# Burst selection and display refresh
# ============================================================================
# A visit ends when no face has been seen for this long; the best frame of the visit is kept.
BURST_GAP_SECONDS = float(os.getenv("BURST_GAP_SECONDS", "2.5"))
# E-ink wears with refreshes and takes seconds per update. Never redraw faster than this.
MIN_REFRESH_INTERVAL_SECONDS = float(os.getenv("MIN_REFRESH_INTERVAL_SECONDS", "180"))

# ============================================================================
# Mood barometer (average hostility of recent visits)
# ============================================================================
MOOD_LOG_PATH = _path("MOOD_LOG_PATH", "data/moods.jsonl")
MOOD_WINDOW_HOURS = float(os.getenv("MOOD_WINDOW_HOURS", "24"))

# ============================================================================
# Display
# ============================================================================
DISPLAY_BACKEND = os.getenv("DISPLAY_BACKEND", "preview")  # preview | waveshare
DISPLAY_SIZE = (
    int(os.getenv("DISPLAY_WIDTH", "800")),
    int(os.getenv("DISPLAY_HEIGHT", "480")),
)
WAVESHARE_MODEL = os.getenv("WAVESHARE_MODEL", "epd7in5_V2")
PREVIEW_PATH = _path("PREVIEW_PATH", "data/display.png")

# Every picture put on the panel is kept here for MOOD_WINDOW_HOURS, for /review.
SHOWN_DIR = _path("SHOWN_DIR", "data/shown")
REVIEW_MAX_PICTURES = int(os.getenv("REVIEW_MAX_PICTURES", "25"))

# ============================================================================
# Telegram (optional): every picture put on the panel is also sent to this chat,
# and the chat can send /snap and /review. No other chat gets an answer.
# ============================================================================
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# ============================================================================
# Logging
# ============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
