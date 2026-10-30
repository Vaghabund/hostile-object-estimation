"""The pictures put on the panel in the last MOOD_WINDOW_HOURS, kept on disk for /review."""
import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from config.settings import MOOD_WINDOW_HOURS, SHOWN_DIR

logger = logging.getLogger(__name__)


@dataclass
class ShownPicture:
    timestamp: float
    hostility: float
    panel: Path   # the full render, as it was on the panel
    face: Path    # the face crop alone, for a review layout that wants it


class ShownPictures:
    """
    One `<unix time>_<hostility>.png` (the panel) plus `<same>_face.png` per shown
    picture. The name carries everything, so there is no index to keep in sync.
    Files older than the window are deleted on startup and on every save.
    """

    def __init__(self, directory: Path = SHOWN_DIR, window_hours: float = MOOD_WINDOW_HOURS, clock=time.time):
        self.dir = directory
        self.window = window_hours * 3600
        self._clock = clock
        self._lock = threading.Lock()  # the main loop saves while the Telegram bot reads
        self.dir.mkdir(parents=True, exist_ok=True)
        with self._lock:
            self._prune()

    def save(self, panel_image, face_image, hostility: float, timestamp: float):
        stem = f"{int(timestamp)}_{hostility:.3f}"
        with self._lock:
            panel_image.save(self.dir / f"{stem}.png")
            face_image.save(self.dir / f"{stem}_face.png")
            self._prune()

    def recent(self):
        """Every picture inside the window, oldest first."""
        cutoff = self._clock() - self.window
        with self._lock:
            return [p for p in self._scan() if p.timestamp >= cutoff]

    def most_hostile(self, limit: int):
        return sorted(self.recent(), key=lambda p: p.hostility, reverse=True)[:limit]

    def _scan(self):
        pictures = []
        for panel in self.dir.glob("*.png"):
            if panel.stem.endswith("_face"):
                continue
            try:
                t, h = panel.stem.split("_")
                pictures.append(ShownPicture(float(t), float(h), panel, panel.with_name(f"{panel.stem}_face.png")))
            except ValueError:
                logger.warning("Ignoring unexpected file %s", panel.name)
        return sorted(pictures, key=lambda p: p.timestamp)

    def _prune(self):
        cutoff = self._clock() - self.window
        for picture in self._scan():
            if picture.timestamp < cutoff:
                picture.panel.unlink(missing_ok=True)
                picture.face.unlink(missing_ok=True)
