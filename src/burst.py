"""Grade the first sharp face of a burst (one person walking past the camera)."""
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
    Keeps the first face of a burst and ignores the rest. The burst ends, and
    the graded face is released, once nothing has kept it alive for `gap_seconds`.
    """

    def __init__(self, gap_seconds: float):
        self.gap_seconds = gap_seconds
        self._graded: Optional[Capture] = None
        self._last_seen = 0.0

    @property
    def in_progress(self) -> bool:
        return self._graded is not None

    def add(self, frame, face: FaceResult, now: float) -> None:
        """`now` is a monotonic clock reading."""
        self._last_seen = now
        if self._graded is None:
            # Copy: the capture loop may reuse the buffer.
            self._graded = Capture(frame.copy(), face, time.time())

    def keep_alive(self, now: float) -> None:
        """The person is still around (movement, no face needed): don't end the burst yet."""
        if self._graded is not None:
            self._last_seen = now

    def poll(self, now: float) -> Optional[Capture]:
        """Return the graded face once the gap has elapsed, else None."""
        if self._graded is None or now - self._last_seen < self.gap_seconds:
            return None
        done, self._graded = self._graded, None
        return done
