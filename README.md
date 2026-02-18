# Hostile Object Estimation System

Motion-triggered YOLO object detection with Telegram bot control. Optimized for old PC hardware with minimal CPU overhead.

## Features

- **Motion-triggered YOLO inference** (not continuous—saves CPU)
- **Edge-based motion detection** (immune to light changes)
- **Object tracking** (consistent IDs, no duplicate logging)
- **Telegram bot** for remote control & statistics
- **In-memory logging** (no disk bloat, auto-purge after 1000 detections)
- **Thread-safe** (detection + bot run in parallel)

## Quick Start

### One-Click Installation & Run

**Windows:**
1. Clone the repository
2. Double-click `run.bat` or run in terminal:
```bash
run.bat
```

The script will automatically:
- Create `.env` from `.env.example` if missing
- Create virtual environment (`.venv`) if missing
- Install/update all dependencies
- Start the system

**Linux / Ubuntu:**
```bash
chmod +x deploy.sh
./deploy.sh
```

The script will automatically:
- Create `.env` from `.env.example` if missing
- Prompt for Telegram bot credentials (optional)
- Create virtual environment if missing
- Install/update all dependencies
- Start the system

### Manual Setup (Optional)

If you prefer manual setup on Windows:

```bash
cd hostile-object-estimation
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Edit .env with your Telegram bot token and user ID
python src/main.py
```

## Project Structure

```
hostile-object-estimation/
├── config/
│   ├── __init__.py
│   └── settings.py          # Central configuration
├── src/
│   ├── camera.py            # Frame capture
│   ├── main.py              # Main loop
│   ├── motion_detector.py   # Motion logic
│   ├── yolo_detector.py     # YOLO + Tracking
│   ├── shared_state.py      # Thread-safe data
│   ├── stats.py             # Statistics generator
│   └── telegram_bot.py      # Telegram interface
├── run.bat                  # Windows launcher
├── deploy.sh                # Linux launcher
├── requirements.txt         # Dependencies
└── .env                     # Secrets (git-ignored)
```

## Development Phases

1. **Phase 1 (Complete):** Project setup + frame capture ✅
2. **Phase 2 (Next):** Motion detection (edge detection + contours)
3. **Phase 3:** YOLO inference + object tracking
4. **Phase 4:** In-memory logging & statistics
5. **Phase 5:** Telegram bot (commands, snapshots, summaries)
6. **Phase 6:** Testing & deployment prep

## Configuration

All settings are in [config/settings.py](config/settings.py) and can be overridden via `.env`:

| Setting | Default | Description |
|---------|---------|-------------|
| CAMERA_ID | 0 | OpenCV camera index |
| PREFER_EXTERNAL_CAMERA | true | Auto-detect USB cameras (set to false to skip probing) |
| CAMERA_PROBE_LIMIT | 3 | Max camera indices to check during auto-detection |
| CAMERA_RESOLUTION | (640, 480) | Frame size (width, height) |
| CAMERA_FPS | 30 | Target frames per second |
| MOTION_CANNY_LOW | 50 | Canny edge detection threshold (low) |
| MOTION_CANNY_HIGH | 150 | Canny edge detection threshold (high) |
| MOTION_PIXEL_THRESHOLD | 0.5 | % of pixels that must change to trigger motion |
| MOTION_COOLDOWN | 2.0 | Seconds between motion detections |
| YOLO_CONFIDENCE | 0.5 | Min detection confidence (0.0-1.0) |
| YOLO_MODEL | yolov8n | YOLOv8 model size (n=tiny, s=small, m=medium) |
| DETECTION_STABILITY_FRAMES | 2 | Min consecutive frames before logging detection |
| DETECTION_HISTORY_MAXLEN | 1000 | Max in-memory detections (auto-purge) |
| TELEGRAM_IMAGE_QUALITY | 60 | JPEG quality for Telegram (0-100) |
| LOG_LEVEL | INFO | Python logging level |

**Tip:** For faster startup, set `PREFER_EXTERNAL_CAMERA=false` and specify `CAMERA_ID` directly if you know which camera to use.

## Notes

- Line endings: `.gitattributes` ensures CRLF (Windows) → LF (Ubuntu) on git push
- Dependencies: All pinned to specific versions for reproducibility
- Threading: Detection + Telegram bot use shared thread-safe state (Phase 3+)
- No database: In-memory deque is sufficient; summaries are temporal
