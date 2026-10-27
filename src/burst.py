"""Pick the best frame from one visit (a person walking past the camera)."""
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
    Collects face sightings and, once no face has been seen for `gap_seconds`,
    releases the most hostile one. Sharpness breaks ties so a scowl in motion
    blur doesn't beat a nearly-as-angry sharp one.
    """

    def __init__(self, gap_seconds: float):
        self.gap_seconds = gap_seconds
        self._best: Optional[Capture] = None
        self._last_seen = 0.0

    @property
    def in_progress(self) -> bool:
        return self._best is not None

    def add(self, frame, face: FaceResult, now: float) -> None:
        """`now` is a monotonic clock reading."""
        self._last_seen = now
        # Copy: the capture loop may reuse the buffer.
        candidate = Capture(frame.copy(), face, time.time())
        best = self._best
        if (
            best is None
            or face.hostility > best.face.hostility
            or (face.hostility == best.face.hostility and face.sharpness > best.face.sharpness)
        ):
            self._best = candidate

    def poll(self, now: float) -> Optional[Capture]:
        """Return the finished visit's best capture once the gap has elapsed, else None."""
        if self._best is not None and now - self._last_seen >= self.gap_seconds:
            done, self._best = self._best, None
            return done
        return None
