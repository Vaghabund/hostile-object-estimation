import argparse
import logging
import signal
import sys
import time

import cv2
from PIL import Image

from config.settings import (
    ACTIVE_WINDOW_SECONDS,
    BURST_GAP_SECONDS,
    DISPLAY_SIZE,
    LOG_LEVEL,
    MIN_REFRESH_INTERVAL_SECONDS,
)
from src.burst import BurstSelector
from src.camera import FrameCapture
from src.display import get_display
from src.faces import FaceAnalyzer
from src.mood import MoodLog
from src.motion_detector import MotionDetector
from src.notify import send_photo
from src.render import render, square_crop
from src.shown import ShownPictures
from src.telegram_bot import TelegramBot

logger = logging.getLogger("hostile")


def publish(display, capture, mood, shown=None):
    """`mood` is (average hostility, visit count) for the barometer; `shown` keeps the picture for /review."""
    image = render(
        capture.frame, capture.face.box, capture.face.hostility, capture.timestamp,
        size=display.size or DISPLAY_SIZE, mono=display.mono, mood=mood,
    )
    display.show(image)
    logger.info(
        "Showing face with hostility %.0f%% (%d px wide, sharpness %.0f)",
        capture.face.hostility * 100, capture.face.width, capture.face.sharpness,
    )
    send_photo(image, f"Hostility {round(capture.face.hostility * 100)}%")
    if shown is not None:
        face = Image.fromarray(cv2.cvtColor(square_crop(capture.frame, capture.face.box), cv2.COLOR_BGR2RGB))
        shown.save(image, face, capture.face.hostility, capture.timestamp)


def run_once(image_path):
    """Run a single image through the whole pipeline (no camera, no refresh limit)."""
    frame = cv2.imread(image_path)
    if frame is None:
        sys.exit(f"Could not read image: {image_path}")
    analyzer = FaceAnalyzer()
    face = analyzer.analyze(frame)
    analyzer.close()
    if face is None:
        sys.exit("No usable face found (too small, too blurry, or none at all).")

    burst = BurstSelector(gap_seconds=0)
    burst.add(frame, face, now=0.0)
    display = get_display()
    capture = burst.poll(now=0.0)
    # Read-only: a test image must not pollute the real mood log. Show the
    # existing average, or just this image's score if the log is empty.
    mood = MoodLog()
    average = mood.average() or (capture.mean_hostility, 1)
    publish(display, capture, average)
    display.close()


def run_forever():
    stop = False

    def request_stop(signum, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    camera = FrameCapture()
    camera.start()
    analyzer = FaceAnalyzer()
    display = get_display()
    motion = MotionDetector()
    burst = BurstSelector(BURST_GAP_SECONDS)
    mood = MoodLog()
    shown = ShownPictures()
    TelegramBot(camera, shown, mood).start()

    active_until = 0.0
    pending = None
    last_refresh = float("-inf")
    logger.info("Watching the hallway.")

    try:
        while not stop:
            frame, _ = camera.get_frame()
            if frame is None:
                if not camera.is_active:
                    logger.critical("Camera lost; exiting so the service manager restarts us.")
                    sys.exit(1)
                time.sleep(0.5)
                continue

            now = time.monotonic()
            if motion.detect(frame):
                active_until = now + ACTIVE_WINDOW_SECONDS

            # The face model only runs while something is moving.
            if now < active_until:
                face = analyzer.analyze(frame)
                if face is not None:
                    burst.add(frame, face, now)
                    active_until = max(active_until, now + ACTIVE_WINDOW_SECONDS)

            finished = burst.poll(now)
            if finished is not None:
                mood.record(finished.mean_hostility, finished.timestamp)  # every visit counts, shown or not
                pending = finished  # a newer visit replaces one still waiting out the refresh limit

            if pending is not None and now - last_refresh >= MIN_REFRESH_INTERVAL_SECONDS:
                publish(display, pending, mood.average(), shown)
                pending = None
                last_refresh = now
    finally:
        logger.info("Shutting down.")
        camera.stop()
        analyzer.close()
        display.close()


def main():
    parser = argparse.ArgumentParser(description="Hallway hostility meter for e-ink.")
    parser.add_argument("--image", help="process one image and show it, instead of watching the camera")
    args = parser.parse_args()

    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.image:
        run_once(args.image)
    else:
        run_forever()


if __name__ == "__main__":
    main()
