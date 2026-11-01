"""Pick the sharpest face of a burst (one person walking past the camera)."""
import time
from dataclasses import dataclass
from typing import Any, Optional

from src.faces import FaceResult


@dataclass
class Capture:
    frame: Any
    face: FaceResult
    timestamp: float  # wall clock, for the caption


class BurstSelector:
    """
    The first face starts a window of `window_seconds`; the sharpest face seen in it is
    released when it ends. The burst then stays closed, ignoring faces, until nothing
    has kept it alive for `gap_seconds`, so a person who lingers is not graded twice.
    """

    def __init__(self, window_seconds: float, gap_seconds: float):
        self.window_seconds = window_seconds
        self.gap_seconds = gap_seconds
        self._best: Optional[Capture] = None
        self._started = 0.0
        self._last_seen = float("-inf")
        self._collecting = False

    @property
    def collecting(self) -> bool:
        """True from the first face until the window ends: the faces being compared."""
        return self._collecting

    def ready_for_new_burst(self, now: float) -> bool:
        return not self._collecting and now - self._last_seen >= self.gap_seconds

    def add(self, frame, face: FaceResult, now: float) -> None:
        """`now` is a monotonic clock reading."""
        if not self._collecting:
            if not self.ready_for_new_burst(now):
                self._last_seen = now  # same person still here
                return
            self._collecting, self._started, self._best = True, now, None
        self._last_seen = now
        if self._best is None or face.sharpness > self._best.face.sharpness:
            # Copy: the capture loop may reuse the buffer.
            self._best = Capture(frame.copy(), face, time.time())

    def keep_alive(self, now: float) -> None:
        """The person is still around (movement, no face needed): don't start a new burst yet."""
        if not self._collecting and self._last_seen > float("-inf"):
            self._last_seen = now

    def poll(self, now: float) -> Optional[Capture]:
        """Return the sharpest capture once the window has ended, else None."""
        if not self._collecting or now - self._started < self.window_seconds:
            return None
        done, self._best, self._collecting = self._best, None, False
        return done
