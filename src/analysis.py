"""Interpretation layer on top of AnalyticsDB: baselines, anomaly scoring,
zone/direction inference, and the text builders for digests and reports.

This is what turns raw detections into "is this normal?" and "what happened
today?" instead of a flat stream of alerts.
"""
import logging
import statistics
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from src.analytics_db import AnalyticsDB
from src.shared_state import SharedState

logger = logging.getLogger(__name__)


@dataclass
class TrackSummary:
    track_id: Optional[int]
    class_name: str
    dwell_s: float
    n_detections: int
    avg_conf: float
    zones: str          # comma-separated zone names touched, "" if none/unconfigured
    direction: str
    alert_immediately: bool
    reason: Optional[str]  # human-readable reason when alert_immediately, else None


_MD_SPECIAL = ("_", "*", "`", "[")


def _md_escape(text: str) -> str:
    """Escape legacy-Markdown special characters in user-controlled text (zone
    names from ZONES) before interpolating it into a Markdown-mode message —
    a single unmatched '_' otherwise breaks parsing and drops the whole message."""
    for ch in _MD_SPECIAL:
        text = text.replace(ch, "\\" + ch)
    return text


def _fmt_time(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M")


def _fmt_duration(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m{secs:02d}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h{minutes:02d}m"


class AnalysisEngine:
    """Interpretation layer: baselines, anomaly checks, zones, digests, reports."""

    def __init__(self, db: AnalyticsDB, *,
                 priority_classes: set,
                 zones: Dict[str, Tuple[float, float, float, float]],
                 anomaly_enabled: bool,
                 anomaly_min_history_days: int,
                 dwell_outlier_min_samples: int,
                 sequence_target_class: str,
                 sequence_vehicle_classes: List[str],
                 sequence_window_s: float):
        self.db = db
        self.priority_classes = priority_classes
        self.zones = zones
        self.anomaly_enabled = anomaly_enabled
        self.anomaly_min_history_days = anomaly_min_history_days
        self.dwell_outlier_min_samples = dwell_outlier_min_samples
        self.sequence_target_class = sequence_target_class
        self.sequence_vehicle_classes = sequence_vehicle_classes
        self.sequence_window_s = sequence_window_s

    # ------------------------------------------------------------ recording

    def record_detections(self, detections: List, frame_shape: Tuple[int, int]) -> None:
        """Log confirmed detections as raw rows (drives spatial heatmaps)."""
        h, w = frame_shape[0], frame_shape[1]
        if not h or not w:
            return
        rows = []
        for d in detections:
            x1, y1, x2, y2 = d.bbox
            cx = ((x1 + x2) / 2.0) / w
            cy = ((y1 + y2) / 2.0) / h
            bw = (x2 - x1) / w
            bh = (y2 - y1) / h
            rows.append((d.timestamp, d.class_name, d.confidence, d.track_id, cx, cy, bw, bh))
        self.db.insert_detections(rows)

    def finalize_track(self, track_id: int, shared_state: SharedState,
                       frame_shape: Tuple[int, int]) -> Optional[TrackSummary]:
        """Aggregate a completed track's detections, persist it, and decide
        whether it should trigger an immediate alert. Call once per track-end."""
        with shared_state._lock:
            track_detections = [d for d in shared_state.detections if d.track_id == track_id]

        if not track_detections:
            return None

        track_detections.sort(key=lambda d: d.timestamp)
        class_name = track_detections[-1].class_name
        first_ts = track_detections[0].timestamp
        last_ts = track_detections[-1].timestamp
        confs = [d.confidence for d in track_detections]
        avg_conf = sum(confs) / len(confs)
        max_conf = max(confs)
        dwell_s = last_ts - first_ts

        h, w = frame_shape[0], frame_shape[1]

        def centroid(d):
            x1, y1, x2, y2 = d.bbox
            return ((x1 + x2) / 2.0 / w, (y1 + y2) / 2.0 / h)

        start_c = centroid(track_detections[0])
        end_c = centroid(track_detections[-1])

        zones_touched: List[str] = []
        for d in track_detections:
            z = self.zone_for_point(*centroid(d))
            if z and z not in zones_touched:
                zones_touched.append(z)
        zones_str = ",".join(zones_touched)
        direction = self._direction_text(start_c, end_c, zones_touched)

        # Check the dwell baseline BEFORE inserting this track, so its own
        # sample doesn't skew the baseline it's being compared against.
        is_dwell_outlier, dwell_reason = self.check_dwell_outlier(class_name, dwell_s)
        immediate, immediate_reason = self.should_alert_immediately(class_name, first_ts)

        self.db.insert_track(
            track_id, class_name, first_ts, last_ts, len(track_detections),
            avg_conf, max_conf, start_c, end_c, direction, zones_str,
        )

        reasons = [r for r in (immediate_reason, dwell_reason) if r]
        return TrackSummary(
            track_id=track_id,
            class_name=class_name,
            dwell_s=dwell_s,
            n_detections=len(track_detections),
            avg_conf=avg_conf,
            zones=zones_str,
            direction=direction,
            alert_immediately=immediate or is_dwell_outlier,
            reason="; ".join(reasons) if reasons else None,
        )

    # ------------------------------------------------------------- zones

    def zone_for_point(self, cx: float, cy: float) -> Optional[str]:
        for name, (x1, y1, x2, y2) in self.zones.items():
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                return name
        return None

    @staticmethod
    def _direction_text(start_c: Tuple[float, float], end_c: Tuple[float, float],
                        zones_touched: List[str]) -> str:
        if len(zones_touched) >= 2:
            return f"{zones_touched[0]} → {zones_touched[-1]}"
        dx = end_c[0] - start_c[0]
        dy = end_c[1] - start_c[1]
        if abs(dx) < 0.08 and abs(dy) < 0.08:
            return "stationary"
        if abs(dx) >= abs(dy):
            return "left→right" if dx > 0 else "right→left"
        return "top→bottom" if dy > 0 else "bottom→top"

    # ----------------------------------------------------------- anomalies

    def should_alert_immediately(self, class_name: str, ts: float) -> Tuple[bool, Optional[str]]:
        """Priority class, or an anomaly that promotes a normally-quiet class."""
        if class_name in self.priority_classes:
            return True, None
        novel, reason = self.check_novel_hour(class_name, ts)
        if novel:
            return True, reason
        seq_reason = self.check_sequence_event(class_name, ts)
        if seq_reason:
            return True, seq_reason
        return False, None

    def check_novel_hour(self, class_name: str, ts: float) -> Tuple[bool, Optional[str]]:
        """Flag a class appearing at an hour-of-day it has never been seen at,
        once enough history exists to make that meaningful."""
        if not self.anomaly_enabled:
            return False, None

        local_dt = datetime.fromtimestamp(ts)
        today_start = datetime(local_dt.year, local_dt.month, local_dt.day).timestamp()
        rows = self.db.track_rows(since_ts=0, until_ts=today_start, class_name=class_name)
        if not rows:
            return False, None  # no history yet; don't flag during bootstrap

        days_seen = {datetime.fromtimestamp(r["first_ts"]).date() for r in rows}
        if len(days_seen) < self.anomaly_min_history_days:
            return False, None

        hours_seen = {datetime.fromtimestamp(r["first_ts"]).hour for r in rows}
        if local_dt.hour not in hours_seen:
            return True, (
                f"⚠️ First {class_name} activity at this hour "
                f"({local_dt.hour:02d}:00) in {len(days_seen)}d of history"
            )
        return False, None

    def check_dwell_outlier(self, class_name: str, dwell_s: float) -> Tuple[bool, Optional[str]]:
        """Flag a track that lingered far longer than this class's baseline."""
        if not self.anomaly_enabled:
            return False, None

        values = self.db.dwell_values(class_name, since_ts=time.time() - 30 * 86400)
        if len(values) < self.dwell_outlier_min_samples:
            return False, None

        median = statistics.median(values)
        mad = statistics.median([abs(v - median) for v in values]) or 1e-6
        robust_z = 0.6745 * (dwell_s - median) / mad
        # Require both a robust-z spike AND a meaningful absolute multiple of the
        # median, so a baseline of near-zero dwell times can't trigger on noise.
        if robust_z > 5 and dwell_s > median * 2 and dwell_s > 5:
            return True, (
                f"⏱ Unusually long dwell: {_fmt_duration(dwell_s)} "
                f"(baseline median {_fmt_duration(median)})"
            )
        return False, None

    def check_sequence_event(self, class_name: str, ts: float) -> Optional[str]:
        """'Vehicle arrival with occupant': a target-class track starting
        shortly after a vehicle-class track."""
        if class_name != self.sequence_target_class or not self.sequence_vehicle_classes:
            return None
        arrival = self.db.latest_vehicle_arrival(
            self.sequence_vehicle_classes, since_ts=ts - self.sequence_window_s, until_ts=ts,
        )
        if arrival is not None:
            return f"\U0001f697 Possible vehicle arrival — then {class_name} {int(ts - arrival)}s later"
        return None

    # -------------------------------------------------------------- digest

    def build_digest_text(self, since_ts: float, until_ts: float) -> str:
        rows = self.db.track_rows(since_ts, until_ts)
        period = f"{_fmt_time(since_ts)}–{_fmt_time(until_ts)}"

        if not rows:
            return f"\U0001f4cb *Digest* ({period})\nNo activity."

        counts = Counter(r["class"] for r in rows)
        lines = [f"\U0001f4cb *Digest* ({period})", f"Total tracks: {len(rows)}", ""]
        for cls, n in counts.most_common():
            lines.append(f"• {cls}: {n}")

        first_ts = min(r["first_ts"] for r in rows)
        last_ts = max(r["first_ts"] for r in rows)
        lines.append("")
        lines.append(f"First: {_fmt_time(first_ts)}   Last: {_fmt_time(last_ts)}")

        zone_counts = Counter()
        for r in rows:
            if r["zones"]:
                zone_counts.update(r["zones"].split(","))
        if zone_counts:
            lines.append("Zones: " + ", ".join(f"{_md_escape(z)} ({n})" for z, n in zone_counts.most_common()))

        pairs = self.db.sequence_pairs(
            since_ts, self.sequence_vehicle_classes, self.sequence_target_class, self.sequence_window_s,
        )
        pairs_in_window = [p for p in pairs if since_ts <= p[0] < until_ts]
        if pairs_in_window:
            lines.append(f"\U0001f697➡🚶 {len(pairs_in_window)} possible vehicle arrival(s) with occupant")

        return "\n".join(lines)

    # -------------------------------------------------------------- report

    def build_daily_report_text(self) -> str:
        now = time.time()
        local_now = datetime.fromtimestamp(now)
        today_start = datetime(local_now.year, local_now.month, local_now.day).timestamp()
        today_rows = self.db.track_rows(today_start)
        week_ago = now - 7 * 86400
        week_rows = self.db.track_rows(week_ago)

        if not today_rows and not week_rows:
            return "\U0001f4ca *Pattern-of-Life Report*\nNo activity recorded yet."

        lines = ["\U0001f4ca *Pattern-of-Life Report*", ""]

        counts_today = Counter(r["class"] for r in today_rows)
        lines.append(f"*Today:* {len(today_rows)} tracks")
        for cls, n in counts_today.most_common():
            lines.append(f"  • {cls}: {n}")

        if today_rows:
            first = min(r["first_ts"] for r in today_rows)
            last = max(r["first_ts"] for r in today_rows)
            lines.append(f"  First: {_fmt_time(first)}  Last: {_fmt_time(last)}")

            hour_counts = Counter(datetime.fromtimestamp(r["first_ts"]).hour for r in today_rows)
            busiest_hr, busiest_n = hour_counts.most_common(1)[0]
            lines.append(f"  Busiest hour: {busiest_hr:02d}:00 ({busiest_n} tracks)")

        days_counted = max(1, len({datetime.fromtimestamp(r["first_ts"]).date() for r in week_rows}))
        avg_per_day = len(week_rows) / days_counted
        lines.append("")
        lines.append(f"*7-day average:* {avg_per_day:.1f} tracks/day")
        if today_rows and avg_per_day > 0:
            ratio = len(today_rows) / avg_per_day
            if ratio > 1.5:
                lines.append(f"↑ Today is {ratio:.1f}× busier than average")
            elif ratio < 0.5:
                lines.append(f"↓ Today is quieter than average ({ratio:.1f}×)")

        zone_counts = Counter()
        for r in week_rows:
            if r["zones"]:
                zone_counts.update(r["zones"].split(","))
        if zone_counts:
            lines.append("")
            lines.append("*Zone activity (7d):* " + ", ".join(f"{_md_escape(z)} ({n})" for z, n in zone_counts.most_common()))

        return "\n".join(lines)

    # --------------------------------------------------------- chart data

    def get_heatmap_matrix(self, days: int = 30, class_name: Optional[str] = None) -> List[List[int]]:
        """7x24 matrix (row 0 = Monday) of completed-track counts, local time."""
        since = time.time() - days * 86400
        rows = self.db.track_rows(since, class_name=class_name)
        matrix = [[0] * 24 for _ in range(7)]
        for r in rows:
            dt = datetime.fromtimestamp(r["first_ts"])
            matrix[dt.weekday()][dt.hour] += 1
        return matrix

    def get_spatial_points(self, hours: float = 24 * 7,
                           class_name: Optional[str] = None) -> List[Tuple[float, float]]:
        since = time.time() - hours * 3600
        return [(r[0], r[1]) for r in self.db.centroid_points(since, class_name=class_name)]
