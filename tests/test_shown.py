from PIL import Image

from src.shown import ShownPictures

HOUR = 3600


def make(tmp_path, now):
    clock = {"t": now}
    return ShownPictures(tmp_path, window_hours=24, clock=lambda: clock["t"]), clock


def save(store, hostility, timestamp):
    store.save(Image.new("RGB", (40, 24)), Image.new("RGB", (8, 8)), hostility, timestamp)


def test_saves_panel_and_face(tmp_path):
    store, _ = make(tmp_path, 1000 * HOUR)
    save(store, 0.7, 1000 * HOUR)
    [picture] = store.recent()
    assert picture.hostility == 0.7 and picture.timestamp == 1000 * HOUR
    assert picture.panel.exists() and picture.face.exists()


def test_old_pictures_are_deleted_on_save(tmp_path):
    store, clock = make(tmp_path, 1000 * HOUR)
    save(store, 0.9, 1000 * HOUR)
    clock["t"] += 25 * HOUR
    save(store, 0.1, clock["t"])
    assert [p.hostility for p in store.recent()] == [0.1]
    assert len(list(tmp_path.glob("*.png"))) == 2  # one panel + its face


def test_old_pictures_are_deleted_on_startup(tmp_path):
    store, _ = make(tmp_path, 1000 * HOUR)
    save(store, 0.9, 1000 * HOUR)
    make(tmp_path, 1030 * HOUR)
    assert list(tmp_path.glob("*.png")) == []


def test_most_hostile_first_and_capped(tmp_path):
    store, _ = make(tmp_path, 1000 * HOUR)
    for i, h in enumerate([0.2, 0.9, 0.5, 0.7]):
        save(store, h, 1000 * HOUR - i * 60)
    assert [p.hostility for p in store.most_hostile(3)] == [0.9, 0.7, 0.5]
