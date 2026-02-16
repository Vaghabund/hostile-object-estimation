from collections import deque
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional
from config.settings import DETECTION_HISTORY_MAXLEN

@dataclass
class Detection:
    """Represents a single detected object instance."""
    timestamp: float
    class_name: str
    confidence: float
    track_id: Optional[int]
    bbox: List[int]  # [x1, y1, x2, y2]

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
        
        # Detection history (auto-purging)
        self.detections = deque(maxlen=DETECTION_HISTORY_MAXLEN)
        
        # Stats
        self.class_counts = {}
        self.last_detection_time = 0
        self.start_time = time.time()

    def update_frame(self, frame):
        with self._lock:
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

    def get_stats(self):
        with self._lock:
            return {
                "uptime": time.time() - self.start_time,
                "total_detections": sum(self.class_counts.values()),
                "class_counts": self.class_counts.copy(),
                "last_detection": self.last_detection_time
            }
