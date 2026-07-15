"""SQLite persistence for detection analytics.

Pure storage layer: two tables (per-frame detections, per-track events) plus
the queries the analysis layer builds on. Interpretation (baselines, anomaly
scoring, digests) lives in src/analysis.py.

Thread safety: the main detection loop and the Telegram bot thread both touch
the DB, so a single connection is guarded by a lock and WAL mode keeps readers
from blocking the writer.
"""
import logging
import sqlite3
import threading
import time
from pathlib import Path
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS detections (
    id INTEGER PRIMARY KEY,
    ts REAL NOT NULL,
    class TEXT NOT NULL,
    confidence REAL NOT NULL,
    track_id INTEGER,
    cx REAL NOT NULL,  -- bbox centroid, normalized 0..1
    cy REAL NOT NULL,
    w REAL NOT NULL,   -- bbox size, normalized 0..1
    h REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_detections_ts ON detections(ts);
CREATE INDEX IF NOT EXISTS idx_detections_class_ts ON detections(class, ts);

CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY,
    track_id INTEGER,
    class TEXT NOT NULL,
    first_ts REAL NOT NULL,
    last_ts REAL NOT NULL,
    n_detections INTEGER NOT NULL,
    avg_conf REAL,
    max_conf REAL,
    start_cx REAL, start_cy REAL,
    end_cx REAL, end_cy REAL,
    direction TEXT,
    zones TEXT
);
CREATE INDEX IF NOT EXISTS idx_tracks_first_ts ON tracks(first_ts);
CREATE INDEX IF NOT EXISTS idx_tracks_class_first_ts ON tracks(class, first_ts);
"""


class AnalyticsDB:
    """Thread-safe SQLite store for detections and completed tracks."""

    def __init__(self, db_path: Path):
        self._lock = threading.Lock()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()
        logger.info(f"Analytics DB ready at {db_path}")

    # ------------------------------------------------------------------ writes

    def insert_detections(self, rows: List[Tuple]) -> None:
        """Insert detection rows: (ts, class, confidence, track_id, cx, cy, w, h)."""
        if not rows:
            return
        with self._lock:
            self._conn.executemany(
                "INSERT INTO detections (ts, class, confidence, track_id, cx, cy, w, h) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            self._conn.commit()

    def insert_track(self, track_id: Optional[int], class_name: str,
                     first_ts: float, last_ts: float, n_detections: int,
                     avg_conf: float, max_conf: float,
                     start_c: Tuple[float, float], end_c: Tuple[float, float],
                     direction: str, zones: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO tracks (track_id, class, first_ts, last_ts, n_detections, "
                "avg_conf, max_conf, start_cx, start_cy, end_cx, end_cy, direction, zones) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (track_id, class_name, first_ts, last_ts, n_detections,
                 avg_conf, max_conf, start_c[0], start_c[1], end_c[0], end_c[1],
                 direction, zones),
            )
            self._conn.commit()

    def prune(self, detection_retention_days: int) -> None:
        """Drop old per-frame detections; completed tracks are tiny and kept 4x longer."""
        now = time.time()
        with self._lock:
            self._conn.execute(
                "DELETE FROM detections WHERE ts < ?",
                (now - detection_retention_days * 86400,),
            )
            self._conn.execute(
                "DELETE FROM tracks WHERE first_ts < ?",
                (now - detection_retention_days * 4 * 86400,),
            )
            self._conn.commit()

    # ------------------------------------------------------------------ queries

    def track_rows(self, since_ts: float, until_ts: Optional[float] = None,
                   class_name: Optional[str] = None) -> List[sqlite3.Row]:
        """Completed tracks in [since_ts, until_ts), newest last."""
        q = ("SELECT track_id, class, first_ts, last_ts, n_detections, avg_conf, "
             "max_conf, start_cx, start_cy, end_cx, end_cy, direction, zones "
             "FROM tracks WHERE first_ts >= ?")
        params: List = [since_ts]
        if until_ts is not None:
            q += " AND first_ts < ?"
            params.append(until_ts)
        if class_name:
            q += " AND class = ?"
            params.append(class_name)
        q += " ORDER BY first_ts"
        with self._lock:
            cur = self._conn.execute(q, params)
            cur.row_factory = sqlite3.Row
            return cur.fetchall()

    def track_count(self, since_ts: float, until_ts: Optional[float] = None) -> int:
        q = "SELECT COUNT(*) FROM tracks WHERE first_ts >= ?"
        params: List = [since_ts]
        if until_ts is not None:
            q += " AND first_ts < ?"
            params.append(until_ts)
        with self._lock:
            return int(self._conn.execute(q, params).fetchone()[0])

    def dwell_values(self, class_name: str, since_ts: float) -> List[float]:
        """Dwell times (seconds) of completed tracks of a class."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT last_ts - first_ts FROM tracks WHERE class = ? AND first_ts >= ?",
                (class_name, since_ts),
            ).fetchall()
        return [r[0] for r in rows]

    def centroid_points(self, since_ts: float,
                        class_name: Optional[str] = None) -> List[Tuple[float, float]]:
        """Normalized detection centroids for spatial heatmaps."""
        q = "SELECT cx, cy FROM detections WHERE ts >= ?"
        params: List = [since_ts]
        if class_name:
            q += " AND class = ?"
            params.append(class_name)
        with self._lock:
            return self._conn.execute(q, params).fetchall()

    def sequence_pairs(self, since_ts: float, vehicle_classes: List[str],
                       target_class: str, window_s: float) -> List[Tuple[float, str]]:
        """(person_first_ts, vehicle_class) where a target track started within
        window_s after a vehicle track started — 'vehicle arrival with occupant'."""
        placeholders = ",".join("?" * len(vehicle_classes))
        q = (f"SELECT p.first_ts, v.class FROM tracks p JOIN tracks v "
             f"ON v.class IN ({placeholders}) "
             f"AND p.first_ts >= v.first_ts AND p.first_ts <= v.first_ts + ? "
             f"WHERE p.class = ? AND p.first_ts >= ? "
             f"GROUP BY p.id")
        with self._lock:
            return self._conn.execute(
                q, (*vehicle_classes, window_s, target_class, since_ts)
            ).fetchall()

    def latest_vehicle_arrival(self, vehicle_classes: List[str], since_ts: float,
                               until_ts: Optional[float] = None) -> Optional[float]:
        """first_ts of the most recent vehicle track in [since_ts, until_ts], if any."""
        if not vehicle_classes:
            return None
        placeholders = ",".join("?" * len(vehicle_classes))
        q = (f"SELECT MAX(first_ts) FROM tracks WHERE class IN ({placeholders}) "
             f"AND first_ts >= ?")
        params: List = [*vehicle_classes, since_ts]
        if until_ts is not None:
            q += " AND first_ts <= ?"
            params.append(until_ts)
        with self._lock:
            row = self._conn.execute(q, params).fetchone()
        return row[0] if row and row[0] is not None else None

    def close(self) -> None:
        with self._lock:
            self._conn.close()
