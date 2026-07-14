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

### Windows
```cmd
git clone https://github.com/Vaghabund/hostile-object-estimation.git
cd hostile-object-estimation
run.bat
```
*No Git? Download the [ZIP from GitHub](https://github.com/Vaghabund/hostile-object-estimation/archive/refs/heads/main.zip), extract, and run `run.bat`*

### Linux / Ubuntu
```bash
git clone https://github.com/Vaghabund/hostile-object-estimation.git
cd hostile-object-estimation
chmod +x deploy.sh
./deploy.sh
```
*Don't have Git? The installer will detect this and show you how to install it.*

**Note:** If the script prompts you to install system packages, copy-paste the command it provides, then run the installer again.

---

## Installation

### Windows Installation

#### Prerequisites
- Windows 10 or later
- Python 3.7 or higher ([Download Python](https://www.python.org/downloads/))
  - **Important:** Check "Add Python to PATH" during installation
- Webcam or video source
- Git (optional, for cloning)

#### Installation Steps

1. **Get the Repository**
   - Download and extract the ZIP from GitHub, OR
   - Clone with Git:
     ```cmd
     git clone https://github.com/Vaghabund/hostile-object-estimation.git
     cd hostile-object-estimation
     ```

2. **Run the Installer**
   - Double-click `run.bat`, OR
   - Run in Command Prompt/PowerShell:
     ```cmd
     run.bat
     ```

3. **What Happens Automatically**
   - ✅ Checks Python installation
   - ✅ Creates `.env` configuration file
   - ✅ Creates isolated virtual environment (`.venv`)
   - ✅ Installs all required packages
   - ✅ Starts the application

4. **Configure Telegram Bot (Optional)**
   - Run the guided setup: `python src\setup.py` (validates your token and auto-detects your user ID), OR
   - Edit `.env` file manually with your Telegram credentials:
     ```
     TELEGRAM_BOT_TOKEN=your_bot_token_here
     AUTHORIZED_USER_ID=your_telegram_user_id
     ```
   - See [Telegram Bot Setup](#telegram-bot-setup) for details

#### Subsequent Runs
- Simply run `run.bat` again
- Dependencies are cached and only reinstalled if `requirements.txt` changes
- To force clean reinstall: delete `.venv` folder and run `run.bat`

---

### Linux / Ubuntu Installation

#### Prerequisites
- Ubuntu 18.04 or later (or compatible Linux distribution)
- Terminal access with sudo privileges
- Webcam or video source (for local installations)

#### Installation Steps

1. **Get the Repository**
   ```bash
   cd ~
   git clone https://github.com/Vaghabund/hostile-object-estimation.git
   cd hostile-object-estimation
   ```

2. **Run the Installer**
   ```bash
   chmod +x deploy.sh
   ./deploy.sh
   ```

3. **Install System Dependencies (if prompted)**
   - The installer will check for required system packages
   - If any are missing, it will show you exactly what to install
   - Simply copy-paste the command it provides, for example:
     ```bash
     sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
     ```
   - Then run `./deploy.sh` again

4. **Set Up the Telegram Bot (Optional)**
   - On first run, an interactive wizard prompts for your bot token, validates it against Telegram, and auto-detects your user ID
   - You can skip it and configure later — see [Telegram Bot Setup](#telegram-bot-setup)

5. **What Happens Automatically**
   - ✅ Checks system dependencies (Python, git, etc.)
   - ✅ Verifies Python installation
   - ✅ Creates `.env` from template
   - ✅ Creates isolated virtual environment (`.venv`)
   - ✅ Upgrades pip
   - ✅ Installs all Python dependencies
   - ✅ Starts the application

#### Subsequent Runs
```bash
cd ~/hostile-object-estimation
./deploy.sh
```

Dependencies are cached and only reinstalled if needed.

---

### Remote Server / Headless Installation

For servers without a display or camera:

```bash
# Install with virtual framebuffer
sudo apt install -y xvfb

# Run with virtual display
xvfb-run -a ./deploy.sh
```

Or modify configuration to disable preview:
```bash
nano .env
# Add: SHOW_PREVIEW=false
```

---

### Manual Installation (Advanced)

If you prefer manual control:

**Windows:**
```cmd
cd hostile-object-estimation
py -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
notepad .env
python src/main.py
```

**Linux:**
```bash
cd hostile-object-estimation
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
nano .env
python3 src/main.py
```

---

## Telegram Bot Setup

The Telegram bot is **optional** — motion detection and logging run fine without it. When configured, it lets you control the system remotely and receive detection alerts. The bot needs two values in `.env`:

- `TELEGRAM_BOT_TOKEN` — issued by Telegram's [@BotFather](https://t.me/BotFather)
- `AUTHORIZED_USER_ID` — your numeric Telegram user ID (this account also receives the alerts)

### Interactive setup (recommended)

On Linux, the **first** `./deploy.sh` run launches this wizard automatically. You can also re-run it any time:

```bash
./deploy.sh --setup
```

Or run it directly — it uses only the Python standard library, so it works on a fresh clone before any packages are installed, on both Linux and Windows:

```bash
python3 src/setup.py      # Windows: python src\setup.py
```

The wizard will:

1. **Create a bot token.** Open Telegram, message [@BotFather](https://t.me/BotFather), send `/newbot`, follow the prompts, and copy the token it gives you. Paste it when asked — the wizard validates it against Telegram and confirms your bot's `@username`.
2. **Detect your user ID automatically.** Send any message (e.g. `/start`) to your new bot, then press Enter. The wizard reads that message back and fills in your numeric user ID for you (with a manual-entry fallback if it can't).

Both values are written to `.env` automatically. Leave the token blank to skip — the bot stays disabled and detection still runs.

### Manual configuration

Prefer to do it by hand? Get the token from [@BotFather](https://t.me/BotFather) and your numeric ID from [@userinfobot](https://t.me/userinfobot), then edit `.env`:

```
TELEGRAM_BOT_TOKEN=123456789:AA...your_token...
AUTHORIZED_USER_ID=987654321
```

> **Windows note:** `run.bat` creates `.env` but does not launch the wizard automatically. Run `python src\setup.py` yourself, or edit `.env` by hand.

---

## Troubleshooting

### Windows Issues

**"Python is not installed or not in PATH"**
- Install Python from [python.org](https://www.python.org/downloads/)
- During installation, CHECK the box "Add Python to PATH"
- Restart your terminal after installation

**"Failed to create virtual environment"**
- Ensure you have enough disk space (need ~500MB for dependencies)
- Try running `run.bat` as Administrator
- Temporarily disable antivirus if it's blocking file creation

**Dependencies fail to install**
- Check internet connection
- Try running as Administrator
- Delete `.venv` folder and run `run.bat` again

### Linux Issues

**Script says packages are missing**
- Simply copy-paste the command the script provides
- It will look like: `sudo apt update && sudo apt install -y python3 python3-pip python3-venv git`
- After installation completes, run `./deploy.sh` again

**"python3: command not found"**
```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv
```

**"python3-venv is not available"**
```bash
sudo apt install -y python3-venv
```

**Camera permission denied / Failed to open camera**
This is a very common issue. The user needs to be in the `video` group:
```bash
# Add user to video group
sudo usermod -a -G video $USER

# Verify the group was added
groups $USER
```

You should see `video` in the list.

**IMPORTANT: Log out and log back in** for changes to take effect:
- If using the system directly: Log out and log back in to your desktop session
- If using SSH (remote connection): Type `exit`, then reconnect with `ssh user@hostname`

After logging back in, verify the group is active:
```bash
groups
```

You should now see `video` in your active groups. Then run the application again.

**Check which video devices are available:**
```bash
# List video devices
ls -la /dev/video*

# Install v4l-utils for more details (optional)
sudo apt install -y v4l-utils
v4l2-ctl --list-devices
```

**OpenCV errors or slow performance** (optional optimization)
```bash
# Install system OpenCV libraries for better performance
sudo apt install -y python3-opencv libglib2.0-0 libsm6 libxext6 libxrender-dev libgomp1
```
Note: The script installs opencv-python via pip, so this is optional.

**"libgl1-mesa-glx has no installation candidate"** (newer Ubuntu)
```bash
# Use libgl1 instead
sudo apt install -y libgl1 libglib2.0-0
```

### General Issues

**Corrupted virtual environment**
- Delete `.venv` folder
- Run installation script again (`run.bat` or `./deploy.sh`)

**Application exits immediately**
- Check if webcam is connected and accessible
- Review error messages in the terminal
- Check `.env` configuration

**Package installation very slow**
- First installation downloads ~500MB of packages
- Be patient, especially with OpenCV and Ultralytics
- Subsequent runs are much faster (cached)

---

## Updating

To update to the latest version:

**Windows:**
```cmd
git pull
run.bat
```

**Linux:**
```bash
git pull
./deploy.sh
```

The scripts automatically detect changes to `requirements.txt` and update dependencies.

## Project Structure

```
hostile-object-estimation/
├── config/
│   ├── __init__.py
│   └── settings.py          # Central configuration
├── src/
│   ├── camera.py            # Frame capture
│   ├── detection_stabilizer.py  # Multi-frame detection filtering
│   ├── image_utils.py       # Bounding-box drawing & collage helpers
│   ├── main.py              # Main loop
│   ├── motion_detector.py   # Motion logic
│   ├── runtime_settings.py  # Live-adjustable settings (via Telegram)
│   ├── shared_state.py      # Thread-safe data
│   ├── stats.py             # Statistics generator
│   ├── telegram_bot.py      # Telegram interface
│   └── yolo_detector.py     # YOLO + Tracking
├── run.bat                  # Windows launcher
├── deploy.sh                # Linux launcher
├── requirements.txt         # Dependencies
└── .env                     # Secrets (git-ignored)
```

## Development Phases

1. **Phase 1 (Complete):** Project setup + frame capture ✅
2. **Phase 2 (Complete):** Motion detection (edge detection + contours) ✅
3. **Phase 3 (Complete):** YOLO inference + object tracking ✅
4. **Phase 4 (Complete):** In-memory logging & statistics ✅
5. **Phase 5 (Complete):** Telegram bot (commands, snapshots, summaries) ✅
6. **Phase 6 (Complete):** Testing & deployment prep ✅

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
| MOTION_DOWNSCALE | 0.5 | Downscale factor before motion detection (0.5 ≈ 4× less CPU; sensitivity unchanged) |
| YOLO_CONFIDENCE | 0.5 | Min detection confidence (0.0-1.0) |
| YOLO_USE_OPENVINO | true | Use OpenVINO for ~2-3× faster CPU inference (falls back to PyTorch if unavailable) |
| YOLO_MODEL | yolov8n | YOLOv8 model size (n=tiny, s=small, m=medium) |
| CPU_THREADS | all cores | Cap OpenCV + PyTorch worker threads; set lower (e.g. 2) on weak/old CPUs |
| DETECTION_STABILITY_FRAMES | 2 | Min consecutive frames before logging detection |
| DETECTION_STABILITY_MAX_MISSES | 2 | Frames a track may be missing before it is dropped |
| DETECTION_HISTORY_MAXLEN | 500 | Max in-memory detections (auto-purge) |
| TELEGRAM_IMAGE_QUALITY | 60 | JPEG quality for Telegram (0-100) |
| FRAME_SELECTION_ENABLED | true | Pick the sharpest/clearest frame to reduce blur in sent images |
| FRAME_SELECTION_ALERTS | true | Apply best-frame selection to detection alerts |
| FRAME_SELECTION_SCAN | true | Apply best-frame selection to the /scan command |
| FRAME_SELECTION_SUMMARY | true | Apply best-frame selection to /summary |
| FACE_DETECTOR_TYPE | cascade | Face detector used for scoring (OpenCV Haar cascade) |
| FRAME_SCORE_FACE_WEIGHT | 1.0 | Best-frame scoring weight — face presence (highest priority) |
| FRAME_SCORE_SHARPNESS_WEIGHT | 0.8 | Best-frame scoring weight — image sharpness |
| FRAME_SCORE_CONFIDENCE_WEIGHT | 0.5 | Best-frame scoring weight — detection confidence |
| FRAME_BUFFER_MAX | 30 | Max frames buffered per track before earliest are purged |
| FRAME_SELECTION_MAX_SCORED | 18 | Max buffered frames the quality scorer evaluates |
| FRAME_SELECTION_FACE_MAX_WIDTH | 320 | Downscale width (px) before the Haar cascade during scoring (0 = off) |
| LOG_LEVEL | INFO | Python logging level |

**Tip:** For faster startup, set `PREFER_EXTERNAL_CAMERA=false` and specify `CAMERA_ID` directly if you know which camera to use.

## Notes

- Line endings: `.gitattributes` ensures CRLF (Windows) → LF (Ubuntu) on git push
- Dependencies: All pinned to specific versions for reproducibility
- Threading: Detection + Telegram bot use shared thread-safe state (Phase 3+)
- No database: In-memory deque is sufficient; summaries are temporal
