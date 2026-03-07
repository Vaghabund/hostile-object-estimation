from collections import deque
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from config.settings import DETECTION_HISTORY_MAXLEN, FRAME_BUFFER_MAX_FRAMES_PER_TRACK

@dataclass
class Detection:
    """Represents a single detected object instance."""
    timestamp: float
    class_name: str
    confidence: float
    track_id: Optional[int]
    bbox: List[int]  # [x1, y1, x2, y2]
    thumbnail: Optional[bytes] = field(default=None, repr=False)

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "class": self.class_name,
            "confidence": self.confidence,
            "track_id": self.track_id,
            "bbox": self.bbox
        }

class SharedState:
    """
    Thread-safe shared state between Detection and Telegram Bot threads.
    """
    def __init__(self):
        self._lock = threading.Lock()
        
        # Latest frame for snapshots
        self.latest_frame = None  
        self.latest_frame_time = 0
        self.latest_detections = []  # Detections associated with latest_frame
        
        # Detection history (auto-purging)
        self.detections = deque(maxlen=DETECTION_HISTORY_MAXLEN)
        
        # Frame buffering per track_id for best-frame selection
        # track_frames[track_id] = deque([(frame, detection, timestamp), ...], maxlen=FRAME_BUFFER_MAX_FRAMES_PER_TRACK)
        self.track_frames: Dict[int, deque] = {}
        self.track_last_confirmed: Dict[int, float] = {}  # track_id -> last confirmation timestamp
        
        # Stats
        self.class_counts = {}
        self.last_detection_time = 0
        self.start_time = time.time()

    def update_frame(self, frame):
        with self._lock:
            # Copy frame to ensure thread safety across different OpenCV backends
            # (DSHOW on Windows, V4L2 on Linux, AVFoundation on macOS may behave differently)
            self.latest_frame = frame.copy() if frame is not None else None
            self.latest_frame_time = time.time()

    def add_detections(self, new_detections: List[Detection]):
        """Add new detections and update stats."""
        if not new_detections:
            return

        with self._lock:
            self.last_detection_time = time.time()
            
            for d in new_detections:
                # Add to history
                self.detections.append(d)
                
                # Update per-class stats
                # Using track_id to avoid double counting could be handled by a specific logic later
                # For now, we count every verified detection event
                self.class_counts[d.class_name] = self.class_counts.get(d.class_name, 0) + 1

    def get_latest_frame(self):
        with self._lock:
            return self.latest_frame.copy() if self.latest_frame is not None else None

    def get_latest_frame_with_detections(self):
        """Get latest frame and its associated detections."""
        with self._lock:
            frame_copy = self.latest_frame.copy() if self.latest_frame is not None else None
            detections_copy = self.latest_detections.copy() if self.latest_detections else []
            return frame_copy, detections_copy

    def update_frame_with_detections(self, frame, detections):
        """Update frame and store associated detections."""
        with self._lock:
            # Copy frame to ensure thread safety across different OpenCV backends
            # (DSHOW on Windows, V4L2 on Linux, AVFoundation on macOS may behave differently)
            self.latest_frame = frame.copy() if frame is not None else None
            self.latest_frame_time = time.time()
            self.latest_detections = detections.copy() if detections else []

    def get_stats(self):
        with self._lock:
            return {
                "uptime": time.time() - self.start_time,
                "total_detections": sum(self.class_counts.values()),
                "class_counts": self.class_counts.copy(),
                "last_detection": self.last_detection_time
            }

    def buffer_frame(self, frame: Optional[object], detection: Detection) -> None:
        """
        Buffer a frame with its detection for best-frame selection.
        
        Used to collect frames from a continuous detection sequence.
        Only buffers if detection has a track_id.
        
        Args:
            frame: numpy array (or None)
            detection: Detection object with track_id
        """
        if detection.track_id is None or frame is None:
            return
        
        with self._lock:
            # Initialize track buffer if needed
            if detection.track_id not in self.track_frames:
                self.track_frames[detection.track_id] = deque(
                    maxlen=FRAME_BUFFER_MAX_FRAMES_PER_TRACK
                )
            
            # Store (frame copy, detection, timestamp)
            self.track_frames[detection.track_id].append(
                (frame.copy() if hasattr(frame, 'copy') else frame, detection, time.time())
            )

    def get_track_frames(self, track_id: int) -> List[Tuple[object, Detection, float]]:
        """
        Retrieve all buffered frames for a track_id.
        
        Args:
            track_id: The track identifier
            
        Returns:
            List of (frame, detection, timestamp) tuples or empty list
        """
        with self._lock:
            if track_id not in self.track_frames:
                return []
            return list(self.track_frames[track_id])

    def clear_track_frames(self, track_id: int) -> None:
        """
        Clear buffered frames for a track_id (called when track ends).
        
        Args:
            track_id: The track identifier to clear
        """
        with self._lock:
            self.track_frames.pop(track_id, None)
            self.track_last_confirmed.pop(track_id, None)
