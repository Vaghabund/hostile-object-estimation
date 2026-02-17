"""
Runtime settings that can be modified via Telegram bot without restarting the system.
"""
import threading
from typing import Set
from config.settings import (
    MOTION_CANNY_THRESHOLD_LOW,
    MOTION_CANNY_THRESHOLD_HIGH,
    MOTION_CHANGED_PIXELS_THRESHOLD,
    MOTION_COOLDOWN_SECONDS,
    YOLO_CONFIDENCE_THRESHOLD,
    DETECTION_STABILITY_FRAMES,
    DETECTION_STABILITY_MAX_MISSES,
)


class RuntimeSettings:
    """Thread-safe runtime settings that can be modified on-the-fly."""
    
    def __init__(self):
        self._lock = threading.Lock()
        
        # Motion detection settings
        self.motion_canny_low = MOTION_CANNY_THRESHOLD_LOW
        self.motion_canny_high = MOTION_CANNY_THRESHOLD_HIGH
        self.motion_pixel_threshold = MOTION_CHANGED_PIXELS_THRESHOLD
        self.motion_cooldown = MOTION_COOLDOWN_SECONDS
        
        # YOLO settings
        self.yolo_confidence = YOLO_CONFIDENCE_THRESHOLD
        
        # Detection stability settings
        self.stability_frames = DETECTION_STABILITY_FRAMES
        self.stability_max_misses = DETECTION_STABILITY_MAX_MISSES
        
        # Class filtering (empty set = allow all classes)
        self.enabled_classes: Set[str] = set()
        
    # Motion detection getters/setters
    def get_motion_canny_low(self) -> int:
        with self._lock:
            return self.motion_canny_low
    
    def set_motion_canny_low(self, value: int):
        with self._lock:
            self.motion_canny_low = max(0, min(255, value))
    
    def get_motion_canny_high(self) -> int:
        with self._lock:
            return self.motion_canny_high
    
    def set_motion_canny_high(self, value: int):
        with self._lock:
            self.motion_canny_high = max(0, min(255, value))
    
    def get_motion_pixel_threshold(self) -> float:
        with self._lock:
            return self.motion_pixel_threshold
    
    def set_motion_pixel_threshold(self, value: float):
        with self._lock:
            self.motion_pixel_threshold = max(0.0, min(100.0, value))
    
    def get_motion_cooldown(self) -> float:
        with self._lock:
            return self.motion_cooldown
    
    def set_motion_cooldown(self, value: float):
        with self._lock:
            self.motion_cooldown = max(0.0, value)
    
    # YOLO settings
    def get_yolo_confidence(self) -> float:
        with self._lock:
            return self.yolo_confidence
    
    def set_yolo_confidence(self, value: float):
        with self._lock:
            self.yolo_confidence = max(0.0, min(1.0, value))
    
    # Detection stability settings
    def get_stability_frames(self) -> int:
        with self._lock:
            return self.stability_frames
    
    def set_stability_frames(self, value: int):
        with self._lock:
            self.stability_frames = max(1, value)
    
    def get_stability_max_misses(self) -> int:
        with self._lock:
            return self.stability_max_misses
    
    def set_stability_max_misses(self, value: int):
        with self._lock:
            self.stability_max_misses = max(1, value)
    
    # Class filtering
    def get_enabled_classes(self) -> Set[str]:
        with self._lock:
            return self.enabled_classes.copy()
    
    def set_enabled_classes(self, classes: Set[str]):
        with self._lock:
            self.enabled_classes = classes.copy()
    
    def add_enabled_class(self, class_name: str):
        with self._lock:
            self.enabled_classes.add(class_name)
    
    def remove_enabled_class(self, class_name: str):
        with self._lock:
            self.enabled_classes.discard(class_name)
    
    def is_class_enabled(self, class_name: str) -> bool:
        with self._lock:
            # Empty set means all classes enabled
            if not self.enabled_classes:
                return True
            return class_name in self.enabled_classes
    
    def get_settings_summary(self) -> str:
        """Get a formatted summary of current settings."""
        with self._lock:
            enabled_classes_str = ", ".join(sorted(self.enabled_classes)) if self.enabled_classes else "All"
            
            return f"""⚙️ *Runtime Settings*

*Motion Detection:*
• Canny Low: {self.motion_canny_low}
• Canny High: {self.motion_canny_high}
• Pixel Threshold: {self.motion_pixel_threshold}%
• Cooldown: {self.motion_cooldown}s

*YOLO Detection:*
• Confidence: {self.yolo_confidence:.2f}

*Detection Stability:*
• Min Frames: {self.stability_frames}
• Max Misses: {self.stability_max_misses}

*Enabled Classes:*
{enabled_classes_str}"""
