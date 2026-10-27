import numpy as np

from src.burst import BurstSelector
from src.faces import FaceResult


def face(hostility, sharpness=100.0):
    return FaceResult(box=(0, 0, 100, 100), hostility=hostility, sharpness=sharpness)


def frame(value=0):
    return np.full((4, 4, 3), value, dtype=np.uint8)


def test_nothing_released_before_gap():
    b = BurstSelector(gap_seconds=2.0)
    b.add(frame(), face(0.5), now=0.0)
    assert b.poll(now=1.0) is None
    assert b.in_progress


def test_releases_most_hostile_after_gap():
    b = BurstSelector(gap_seconds=2.0)
    b.add(frame(1), face(0.2), now=0.0)
    b.add(frame(2), face(0.9), now=0.5)
    b.add(frame(3), face(0.4), now=1.0)
    done = b.poll(now=3.5)
    assert done.face.hostility == 0.9
    assert done.frame[0, 0, 0] == 2
    assert not b.in_progress
    assert b.poll(now=10.0) is None


def test_sharpness_breaks_ties():
    b = BurstSelector(gap_seconds=1.0)
    b.add(frame(1), face(0.5, sharpness=40), now=0.0)
    b.add(frame(2), face(0.5, sharpness=90), now=0.1)
    assert b.poll(now=5.0).frame[0, 0, 0] == 2


def test_stores_a_copy_of_the_frame():
    b = BurstSelector(gap_seconds=1.0)
    f = frame(7)
    b.add(f, face(0.5), now=0.0)
    f[:] = 0
    assert b.poll(now=5.0).frame[0, 0, 0] == 7
