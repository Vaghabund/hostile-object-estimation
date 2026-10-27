import json

from src.mood import MoodLog

HOUR = 3600


def make(tmp_path, now):
    clock = {"t": now}
    return MoodLog(tmp_path / "moods.jsonl", window_hours=24, clock=lambda: clock["t"]), clock


def test_empty_log_has_no_average(tmp_path):
    log, _ = make(tmp_path, 1000 * HOUR)
    assert log.average() is None


def test_average_over_window(tmp_path):
    log, clock = make(tmp_path, 1000 * HOUR)
    log.record(0.2)
    log.record(0.6)
    avg, n = log.average()
    assert abs(avg - 0.4) < 1e-9 and n == 2


def test_old_visits_drop_out(tmp_path):
    log, clock = make(tmp_path, 1000 * HOUR)
    log.record(0.9)
    clock["t"] += 25 * HOUR
    log.record(0.1)
    assert log.average() == (0.1, 1)


def test_survives_restart_and_trims_expired(tmp_path):
    now = 1000 * HOUR
    path = tmp_path / "moods.jsonl"
    path.write_text(
        json.dumps({"t": now - 30 * HOUR, "v": 1.0}) + "\n"
        + json.dumps({"t": now - 1 * HOUR, "v": 0.3}) + "\n"
        + "not json\n"
    )
    log = MoodLog(path, window_hours=24, clock=lambda: now)
    assert log.average() == (0.3, 1)
    assert len(path.read_text().splitlines()) == 1
