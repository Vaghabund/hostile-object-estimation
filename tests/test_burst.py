import numpy as np

from src.burst import BurstSelector
from src.faces import FaceResult


def face(sharpness=100.0):
    return FaceResult(box=(0, 0, 100, 100), sharpness=sharpness)


def frame(value=0):
    return np.full((4, 4, 3), value, dtype=np.uint8)


def burst(window=1.5, gap=2.5):
    return BurstSelector(window_seconds=window, gap_seconds=gap)


def test_nothing_released_before_the_window_ends():
    b = burst()
    b.add(frame(), face(), now=0.0)
    assert b.poll(now=1.0) is None
    assert b.collecting


def test_releases_the_sharpest_face_when_the_window_ends():
    b = burst(window=1.5)
    b.add(frame(1), face(20), now=0.0)
    b.add(frame(2), face(90), now=0.5)
    b.add(frame(3), face(60), now=1.0)
    done = b.poll(now=1.5)
    assert done.face.sharpness == 90
    assert done.frame[0, 0, 0] == 2
    assert not b.collecting


def test_the_window_runs_from_the_first_face_not_the_last():
    b = burst(window=1.5)
    b.add(frame(), face(), now=0.0)
    b.add(frame(), face(), now=1.4)
    assert b.poll(now=1.5) is not None


def test_a_face_after_the_window_is_not_a_candidate():
    b = burst(window=1.0)
    b.add(frame(1), face(10), now=0.0)
    done = b.poll(now=1.0)
    b.add(frame(2), face(500), now=1.2)
    assert done.frame[0, 0, 0] == 1
    assert b.poll(now=1.3) is None


def test_stays_closed_until_the_person_has_gone():
    b = burst(window=1.0, gap=2.5)
    b.add(frame(), face(), now=0.0)
    b.poll(now=1.0)
    b.keep_alive(now=3.0)   # still moving about
    b.add(frame(), face(), now=4.0)
    assert not b.ready_for_new_burst(now=5.0)
    assert b.ready_for_new_burst(now=6.6)


def test_a_new_burst_starts_after_the_quiet_time():
    b = burst(window=1.0, gap=2.5)
    b.add(frame(1), face(10), now=0.0)
    b.poll(now=1.0)
    assert b.ready_for_new_burst(now=10.0)
    b.add(frame(2), face(70), now=10.0)
    assert b.poll(now=11.0).face.sharpness == 70


def test_keep_alive_does_nothing_before_a_burst():
    b = burst()
    b.keep_alive(now=0.0)
    assert not b.collecting
    assert b.ready_for_new_burst(now=0.0)


def test_stores_a_copy_of_the_frame():
    b = burst(window=1.0)
    f = frame(7)
    b.add(f, face(), now=0.0)
    f[:] = 0
    assert b.poll(now=1.0).frame[0, 0, 0] == 7
