"""Answer /snap and /review from the configured Telegram chat (optional)."""
import json
import logging
import threading
import time
import urllib.request

import cv2
from PIL import Image

from config.settings import MOOD_WINDOW_HOURS, REVIEW_MAX_PICTURES, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from src.notify import send_photo_now
from src.review import render_review

logger = logging.getLogger(__name__)

WINDOW = f"{MOOD_WINDOW_HOURS:g}h"
COMMANDS = {
    "snap": "what the camera sees right now",
    "review": f"the most hostile pictures of the last {WINDOW}",
}
POLL_SECONDS = 25        # long poll: Telegram holds the request open until a message arrives
MAX_BACKOFF_SECONDS = 60


def _api(method, **params):
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}",
        data=json.dumps(params).encode(), headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=POLL_SECONDS + 10) as response:
        body = json.load(response)
    if not body.get("ok"):
        raise RuntimeError(f"{method}: {body.get('description')}")
    return body["result"]


class TelegramBot:
    """
    Polls getUpdates on a daemon thread. Only TELEGRAM_CHAT_ID gets an answer;
    anyone else is ignored without a reply, since /snap is a live camera.
    Never touches the capture loop: /snap copies the camera's last frame.
    """

    def __init__(self, camera, shown, mood):
        self.camera = camera
        self.shown = shown
        self.mood = mood
        self._offset = None  # None until the backlog from before startup is skipped

    def start(self):
        """Does nothing unless TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are set."""
        if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
            return
        threading.Thread(target=self._run, name="telegram", daemon=True).start()

    def _run(self):
        delay, failing = 1, False
        while True:
            try:
                self._poll()
            except Exception as e:  # an outage must never stop the meter; log it once, retry quietly
                if not failing:
                    logger.warning("Telegram unreachable, retrying in the background: %s", e)
                failing = True
                time.sleep(delay)
                delay = min(delay * 2, MAX_BACKOFF_SECONDS)
                continue
            if failing:
                logger.info("Telegram reachable again")
            delay, failing = 1, False

    def _poll(self):
        if self._offset is None:
            self._start_fresh()
            return
        for update in _api("getUpdates", offset=self._offset, timeout=POLL_SECONDS, allowed_updates=["message"]):
            self._offset = update["update_id"] + 1
            try:
                self.handle(update.get("message") or {})
            except Exception:
                logger.exception("Telegram command failed")

    def _start_fresh(self):
        """Fill the chat's / menu, and drop commands sent while we were off (no 3 a.m. /snap on boot)."""
        _api("setMyCommands", commands=[{"command": c, "description": d} for c, d in COMMANDS.items()])
        latest = _api("getUpdates", offset=-1, timeout=0)
        self._offset = latest[-1]["update_id"] + 1 if latest else 0

    def handle(self, message):
        chat = str(message.get("chat", {}).get("id", ""))
        if chat != TELEGRAM_CHAT_ID.strip():
            logger.debug("Ignoring a message from chat %s", chat)
            return
        words = message.get("text", "").split()
        command = words[0].split("@")[0].lstrip("/").lower() if words else ""
        if command == "snap":
            self._snap()
        elif command == "review":
            self._review()
        else:
            self._say("  ".join(f"/{c}: {d}" for c, d in COMMANDS.items()))

    def _snap(self):
        frame = self.camera.get_latest_frame() if self.camera.is_active else None
        if frame is None:
            self._say("Camera unavailable")
            return
        image = Image.fromarray(cv2.cvtColor(frame.copy(), cv2.COLOR_BGR2RGB))
        send_photo_now(image, time.strftime("%H:%M:%S"))

    def _review(self):
        pictures = self.shown.most_hostile(REVIEW_MAX_PICTURES)
        if not pictures:
            self._say(f"Nothing shown in the last {WINDOW}")
            return
        mood = self.mood.average()
        caption = f"Last {WINDOW}"
        if mood is not None:
            caption += f": {mood[1]} visits, mood {round(mood[0] * 100)}%"
        send_photo_now(render_review(pictures, mood), caption)

    def _say(self, text):
        try:
            _api("sendMessage", chat_id=TELEGRAM_CHAT_ID, text=text)
        except Exception as e:
            logger.warning("Telegram reply failed: %s", e)
