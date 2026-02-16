from collections import Counter
import time
from datetime import datetime, timedelta
from src.shared_state import SharedState

class StatsGenerator:
    """
    Generates human-readable summaries from SharedState data.
    """
    def __init__(self, shared_state: SharedState):
        self.state = shared_state

    def get_summary(self, hours=24):
        """
        Generate a summary text for the last N hours.
        """
        now = time.time()
        cutoff_time = now - (hours * 3600)
        
        with self.state._lock:
            # Filter detections within timeframe
            recent_detections = [
                d for d in self.state.detections 
                if d.timestamp >= cutoff_time
            ]
            
            # Get latest detection info
            last_det = None
            if self.state.detections:
                last_det = self.state.detections[-1]

            # Current uptime
            uptime_seconds = int(now - self.state.start_time)
            uptime_str = str(timedelta(seconds=uptime_seconds))

        if not recent_detections:
            return (
                f"📊 *Status Report*\n"
                f"⏱ Uptime: {uptime_str}\n"
                f"🚫 No detections in last {hours}h"
            )

        # Calculate stats
        total_count = len(recent_detections)
        class_counts = Counter(d.class_name for d in recent_detections)
        
        # Format breakdown
        breakdown = "\n".join([f"- {cls}: {count}" for cls, count in class_counts.items()])
        
        # Last detection string
        last_det_str = "None"
        if last_det:
            dt = datetime.fromtimestamp(last_det.timestamp)
            last_det_str = f"{last_det.class_name} at {dt.strftime('%H:%M:%S')}"

        return (
            f"📊 *Activity Report (Last {hours}h)*\n"
            f"⏱ Uptime: {uptime_str}\n"
            f"🔢 Total Detections: {total_count}\n\n"
            f"*Breakdown:*\n{breakdown}\n\n"
            f"👀 Last Sighted: {last_det_str}"
        )

    def get_status_short(self):
        """
        Quick status check (uptime + last detection).
        """
        now = time.time()
        with self.state._lock:
            uptime = str(timedelta(seconds=int(now - self.state.start_time)))
            total = sum(self.state.class_counts.values())
            last_time = self.state.last_detection_time
            
        last_seen = "Never"
        if last_time > 0:
            minutes_ago = int((now - last_time) / 60)
            if minutes_ago < 1:
                last_seen = "Just now"
            else:
                last_seen = f"{minutes_ago}m ago"

        return (
            f"🟢 *System Online*\n"
            f"⏱ Uptime: {uptime}\n"
            f"📈 Total Events: {total}\n"
            f"👀 Last Activity: {last_seen}"
        )
