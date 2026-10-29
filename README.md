# Hostile Object Estimation v2

A hallway art piece. A camera watches the corridor; when someone walks past, a Raspberry Pi finds their face, reads how much they are frowning, and shows the most hostile moment of the visit on an e-ink display with a "hostility" percentage.

```
USB camera -> motion gate -> face landmarks -> hostility score -> best frame of the visit -> e-ink
             (cheap, always)  (only on motion)  (brows, frown, squint)                       (rate limited)
```

- **Low power.** The camera runs at 10 fps and a cheap edge-difference check watches it. The face model only wakes while something moves. E-ink holds its image with no power.
- **Hostility** is a weighted sum of MediaPipe face blendshapes (brow down, mouth frown, eye squint, pressed lips, nose sneer), cancelled by smiling. Tune the weights in `src/hostility.py` and the overall scale with `HOSTILITY_GAIN`.
- **One picture per visit.** Frames from a visit are compared, and the most hostile (sharpest on ties) wins.
- **Easy on the panel.** Refreshes are limited to one per `MIN_REFRESH_INTERVAL_SECONDS` (default 3 min). A newer visit replaces one still waiting.
- **Mood barometer.** Above the date, a scale shows the average hostility of every visit in the last 24 hours (`MOOD_WINDOW_HOURS`). Each visit counts once, at its average over the whole walk-past, whether or not the screen was refreshed for it. The numbers live in `data/moods.jsonl` and survive restarts.
- **Whole faces only.** Faces partly outside the camera's view are skipped, so the panel never shows half a face.
- **Telegram (optional).** With `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` set, every picture put on the panel is also sent to that chat. Create the bot with @BotFather, message it once, then read your chat id from `https://api.telegram.org/bot<token>/getUpdates`.
- **No photos are stored.** The only frame kept is the one on the screen (and `data/display.png` in preview mode). The mood log is just timestamps and scores. If Telegram is on, the shown picture does leave the device, to Telegram's servers.

## Quick start (any machine, no hardware needed)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
python -m src.main --image some_portrait.jpg   # writes data/display.png
python -m src.main                              # watch the webcam; preview PNG updates
pytest
```

The face model (about 4 MB) is downloaded on first run into `models/`. On Linux, MediaPipe needs `libegl1` and `libgles2` (`sudo apt install libegl1 libgles2`).

## On the Pi

Built on a **Raspberry Pi 5** with a Waveshare e-Paper Driver HAT (SKU 13512), a 7.5" 800x480 black/white panel (`epd7in5_V2`) and a USB webcam. Use **64-bit** Raspberry Pi OS (Lite is enough), since MediaPipe has no 32-bit wheels.

Flash with Raspberry Pi Imager: hostname `hoe`, user `admin`, SSH on with public-key login. Then `ssh admin@hoe.local`. Passwords are not kept in this repo.

```bash
sudo raspi-config nonint do_spi 0 && sudo reboot   # the HAT talks SPI
sudo apt install git python3-venv python3-dev libegl1 libgles2 libgl1 python3-spidev python3-gpiozero python3-lgpio
git clone https://github.com/Vaghabund/hostile-object-estimation ~/hostile-object-estimation && cd ~/hostile-object-estimation
python3 -m venv --system-site-packages .venv && . .venv/bin/activate   # system packages: the GPIO/SPI libs above
pip install -r requirements.txt

# Waveshare's driver is not on PyPI; copy it in from their repo (ignored by git)
git clone --depth 1 --filter=blob:none --sparse https://github.com/waveshareteam/e-Paper /tmp/ws
git -C /tmp/ws sparse-checkout set RaspberryPi_JetsonNano/python/lib
cp -r /tmp/ws/RaspberryPi_JetsonNano/python/lib/waveshare_epd . && echo waveshare_epd/ >> .git/info/exclude

cp .env.example .env     # then set the values below
sed 's#/home/pi#/home/admin#g; s#User=pi#User=admin#' deploy/hostile.service | sudo tee /etc/systemd/system/hostile.service
sudo systemctl daemon-reload && sudo systemctl enable --now hostile
```

The Pi's `.env` differs from the defaults in these lines:

```
DISPLAY_BACKEND=waveshare
WAVESHARE_MODEL=epd7in5_V2
PREFER_EXTERNAL_CAMERA=false        # on the Pi, index 1 is the webcam's metadata node, not a camera
MOTION_PIXEL_THRESHOLD=1.0          # webcam noise alone reached 0.76%
MIN_REFRESH_INTERVAL_SECONDS=30
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Logs: `journalctl -u hostile -f`. After editing `.env`: `sudo systemctl restart hostile`.

**Changing Wi-Fi** needs no reflash. Add the new network while the Pi is still online (`sudo nmcli con add type wifi ssid "Name" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "Password"`), or plug in a LAN cable and do it then. `hoe.local` works on any network.

### Displays

Set `DISPLAY_BACKEND` in `.env`:

| Backend | Hardware | Extra install |
|---|---|---|
| `preview` | none (writes a PNG) | |
| `waveshare` | Waveshare black/white panel, `WAVESHARE_MODEL=epd7in5_V2` | Waveshare's `waveshare_epd` library |

The `preview` backend and the pipeline are tested, and `waveshare` runs on the Pi 5 described above.

## Configuration

Everything is optional; see `.env.example`. The settings you will most likely touch:

| Variable | Default | |
|---|---|---|
| `HOSTILITY_GAIN` | 2.0 | Raise if scowls read too low |
| `FACE_MIN_WIDTH_PX` | 80 | Ignore faces smaller (further away) than this |
| `MOTION_PIXEL_THRESHOLD` | 0.5 | % of edges that must change to count as motion |
| `MIN_REFRESH_INTERVAL_SECONDS` | 180 | Minimum time between e-ink redraws |
| `BURST_GAP_SECONDS` | 2.5 | Quiet time that ends a visit |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | empty | Send each shown picture to Telegram |

## Layout

```
src/main.py            capture loop and wiring
src/motion_detector.py cheap motion gate
src/faces.py           MediaPipe face landmarks + blendshapes
src/hostility.py       blendshapes -> 0..1 score
src/burst.py           best frame of a visit
src/mood.py            24 h rolling mood average
src/render.py          composes the e-ink picture
src/display/           preview and waveshare backends
src/notify.py          optional Telegram send
deploy/hostile.service systemd unit
```

## Ideas for later

Telegram commands and health checks (v1's bot is in the `v1.0.0` tag to crib from), a "no one has frowned today" screen, and a sleep schedule to blank the panel at night.

## v1 (parked)

The first version, a YOLO object detector that sent Telegram alerts, is no longer developed. It lives in the tag [`v1.0.0`](https://github.com/Vaghabund/hostile-object-estimation/releases/tag/v1.0.0).
