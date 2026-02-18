from typing import Dict, Hashable, List, TYPE_CHECKING
from dataclasses import dataclass
import threading
from src.shared_state import Detection

if TYPE_CHECKING:
    from src.runtime_settings import RuntimeSettings


@dataclass
class _TrackState:
    consecutive: int
    last_frame: int
    detection: Detection


@dataclass
class StabilizedDetections:
    display: List[Detection]
    confirmed: List[Detection]


class DetectionStabilizer:
    """Filter detections to only keep signals that persist across frames."""

    def __init__(self, runtime_settings: 'RuntimeSettings'):
        self.settings = runtime_settings
        self._lock = threading.Lock()
        self._frame_index = 0
        self._tracks: Dict[Hashable, _TrackState] = {}

    def filter(self, detections: List[Detection]) -> StabilizedDetections:
        with self._lock:
            self._frame_index += 1
            frame_idx = self._frame_index
            display: List[Detection] = []
            confirmed: List[Detection] = []
            seen_keys = set()
            
            # Get current thresholds
            min_consecutive = max(1, self.settings.get_stability_frames())
            max_missed = max(1, self.settings.get_stability_max_misses())

            for det in detections:
                key = self._make_key(det)
                track = self._tracks.get(key)

                if track is None:
                    track = _TrackState(consecutive=0, last_frame=0, detection=det)

                if track.last_frame == frame_idx - 1:
                    track.consecutive += 1
                else:
                    track.consecutive = 1

                track.last_frame = frame_idx
                track.detection = det
                self._tracks[key] = track
                seen_keys.add(key)

                if track.consecutive >= min_consecutive:
                    display.append(det)
                    if track.consecutive == min_consecutive:
                        confirmed.append(det)

            # Decay or remove stale tracks
            stale_keys = []
            for key, track in self._tracks.items():
                if key in seen_keys:
                    continue

                if frame_idx - track.last_frame > max_missed:
                    stale_keys.append(key)
                else:
                    track.consecutive = 0

            for key in stale_keys:
                self._tracks.pop(key, None)

            return StabilizedDetections(display=display, confirmed=confirmed)

    @staticmethod
    def _make_key(detection: Detection) -> Hashable:
        if detection.track_id is not None:
            return (detection.class_name, detection.track_id)

        x1, y1, x2, y2 = detection.bbox
        return (detection.class_name, x1 // 16, y1 // 16, x2 // 16, y2 // 16)
