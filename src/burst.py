"""Pick the best frame from one visit (a person walking past the camera)."""
import time
from dataclasses import dataclass
from typing import Any, List, Optional

from config.settings import BURST_SHARPNESS_RATIO
from src.faces import FaceResult


@dataclass
class Capture:
    frame: Any
    face: FaceResult
    timestamp: float  # wall clock, for the caption
    mean_hostility: float = 0.0  # average over the whole visit


def _beats(a: Capture, b: Capture) -> bool:
    """True if `a` is at least as hostile and at least as sharp as `b`."""
    return a.face.hostility >= b.face.hostility and a.face.sharpness >= b.face.sharpness


class BurstSelector:
    """
    Collects face sightings and, once no face has been seen for `gap_seconds`,
    releases one. Frames blurrier than `sharpness_ratio` times the visit's
    sharpest are out; of the rest the most hostile wins (the sharper on ties).
    So a scowl smeared by walking up never beats a nearly-as-angry sharp face.
    """

    def __init__(self, gap_seconds: float, sharpness_ratio: float = BURST_SHARPNESS_RATIO):
        self.gap_seconds = gap_seconds
        self.sharpness_ratio = sharpness_ratio
        # Only captures no other one beats on both counts: the winner is always
        # among them, and it keeps a few frames in memory instead of the whole visit.
        self._front: List[Capture] = []
        self._last_seen = 0.0
        self._sum = 0.0
        self._count = 0

    @property
    def in_progress(self) -> bool:
        return bool(self._front)

    def add(self, frame, face: FaceResult, now: float) -> None:
        """`now` is a monotonic clock reading."""
        self._last_seen = now
        self._sum += face.hostility
        self._count += 1
        # Copy: the capture loop may reuse the buffer.
        candidate = Capture(frame.copy(), face, time.time())
        if any(_beats(c, candidate) for c in self._front):
            return
        self._front = [c for c in self._front if not _beats(candidate, c)] + [candidate]

    def poll(self, now: float) -> Optional[Capture]:
        """Return the finished visit's best capture once the gap has elapsed, else None."""
        if not self._front or now - self._last_seen < self.gap_seconds:
            return None
        sharpest = max(c.face.sharpness for c in self._front)
        sharp_enough = [c for c in self._front if c.face.sharpness >= self.sharpness_ratio * sharpest]
        done = max(sharp_enough, key=lambda c: (c.face.hostility, c.face.sharpness))
        done.mean_hostility = self._sum / self._count
        self._front, self._sum, self._count = [], 0.0, 0
        return done
