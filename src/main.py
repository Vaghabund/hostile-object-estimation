import argparse
import logging
import signal
import sys
import time

import cv2
import numpy as np
from PIL import Image

from config.settings import (
    ACTIVE_WINDOW_SECONDS,
    BURST_GAP_SECONDS,
    BURST_WINDOW_SECONDS,
    DISPLAY_SIZE,
    LOG_LEVEL,
    MIN_REFRESH_INTERVAL_SECONDS,
)
from src.burst import BurstSelector, Capture
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


def publish(display, capture, mood, shown=None, analyzer=None):
    """
    `mood` is (average hostility, burst count) for the barometer; `shown` keeps the picture for /review.
    `analyzer` re-places the face marks on the picture's crop, where they sit more accurately than from the full frame.
    """
    landmarks = capture.face.landmarks
    if analyzer is not None:
        refined = analyzer.refine_landmarks(capture.frame, capture.face.box)
        if refined is not None:
            h, w = capture.frame.shape[:2]
            moved = np.mean([np.hypot((a[0] - b[0]) * w, (a[1] - b[1]) * h) for a, b in zip(refined, landmarks)])
            logger.debug("Face marks moved %.0f px when re-placed on the crop", moved)
            landmarks = refined
    image = render(
        capture.frame, capture.face.box, capture.face.hostility, capture.timestamp,
        size=display.size or DISPLAY_SIZE, mono=display.mono, mood=mood, landmarks=landmarks,
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
    found = analyzer.find(frame)
    face = analyzer.grade(frame, found) if found is not None else None
    if face is None:
        analyzer.close()
        sys.exit("No usable face found (too small, too blurry, or none at all).")

    display = get_display()
    capture = Capture(frame, face, time.time())
    # Read-only: a test image must not pollute the real mood log. Show the
    # existing average, or just this image's hostility if the log is empty.
    mood = MoodLog()
    average = mood.average() or (capture.face.hostility, 1)
    publish(display, capture, average, analyzer=analyzer)
    analyzer.close()
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
    burst = BurstSelector(BURST_WINDOW_SECONDS, BURST_GAP_SECONDS)
    mood = MoodLog()
    shown = ShownPictures()
    TelegramBot(camera, shown, mood).start()

    active_until = 0.0
    pending = None
    last_refresh = float("-inf")
    logger.info("Watching the hallway.")
    heartbeat_at, frames, peak_change = time.monotonic() + 30, 0, 0.0

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
            moving = motion.detect(frame)
            frames += 1
            peak_change = max(peak_change, motion.last_change)
            if now >= heartbeat_at:
                logger.debug("Last 30s: %d frames, peak edge change %.2f%%", frames, peak_change)
                heartbeat_at, frames, peak_change = now + 30, 0, 0.0
            if moving:
                active_until = now + ACTIVE_WINDOW_SECONDS

            # The face model only looks for faces while something is moving, and once a burst
            # has been graded it only needs to notice that the person is still about.
            if burst.collecting or (now < active_until and burst.ready_for_new_burst(now)):
                face = analyzer.find(frame)
                if face is not None:
                    burst.add(frame, face, now)
            elif moving:
                burst.keep_alive(now)

            finished = burst.poll(now)
            if finished is not None:
                graded = analyzer.grade(finished.frame, finished.face)
                if graded is None:
                    logger.debug("Burst dropped: the sharpest face could not be graded")
                else:
                    finished.face = graded
                    mood.record(graded.hostility, finished.timestamp)  # every burst counts, shown or not
                    pending = finished  # a newer burst replaces one still waiting out the refresh limit

            if pending is not None and now - last_refresh >= MIN_REFRESH_INTERVAL_SECONDS:
                publish(display, pending, mood.average(), shown, analyzer)
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
