"""Rolling log of how hostile recent visits were, for the mood barometer."""
import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

from config.settings import MOOD_LOG_PATH, MOOD_WINDOW_HOURS

logger = logging.getLogger(__name__)


class MoodLog:
    """
    Appends one {"t": unix time, "v": hostility} line per visit and averages the
    ones inside the window. Survives restarts; the file is trimmed on startup.
    """

    def __init__(self, path: Path = MOOD_LOG_PATH, window_hours: float = MOOD_WINDOW_HOURS, clock=time.time):
        self.path = path
        self.window = window_hours * 3600
        self._clock = clock
        self._lock = threading.Lock()
        self._entries = self._load()
        self._rewrite()  # drop expired lines so the file stays small

    def _load(self):
        if not self.path.exists():
            return []
        cutoff = self._clock() - self.window
        entries = []
        for line in self.path.read_text().splitlines():
            try:
                row = json.loads(line)
                entry = (float(row["t"]), float(row["v"]))
            except (ValueError, KeyError, TypeError):
                logger.warning("Skipping unreadable mood log line: %r", line[:80])
                continue
            if entry[0] >= cutoff:
                entries.append(entry)
        return entries

    def _rewrite(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        tmp.write_text("".join(json.dumps({"t": t, "v": v}) + "\n" for t, v in self._entries))
        tmp.replace(self.path)

    def record(self, hostility: float, timestamp: float = None):
        entry = (self._clock() if timestamp is None else timestamp, hostility)
        with self._lock:
            self._entries.append(entry)
            with open(self.path, "a") as f:
                f.write(json.dumps({"t": entry[0], "v": entry[1]}) + "\n")

    def average(self):
        """Return (mean hostility, number of visits) over the window, or None if empty."""
        cutoff = self._clock() - self.window
        with self._lock:  # the Telegram bot reads this from its own thread
            self._entries = [e for e in self._entries if e[0] >= cutoff]
            if not self._entries:
                return None
            return sum(v for _, v in self._entries) / len(self._entries), len(self._entries)

    def hourly(self):
        """Mean hostility per clock hour across the window, oldest first, ending with the current hour; None where nobody came."""
        hours = max(1, round(self.window / 3600))
        this_hour = datetime.fromtimestamp(self._clock()).replace(minute=0, second=0, microsecond=0)
        first = this_hour.timestamp() - (hours - 1) * 3600  # local clock hours, matching the chart's labels
        buckets = [[] for _ in range(hours)]
        with self._lock:
            for t, v in self._entries:
                i = int(t - first) // 3600
                if 0 <= i < hours:
                    buckets[i].append(v)
        return [sum(b) / len(b) if b else None for b in buckets]
