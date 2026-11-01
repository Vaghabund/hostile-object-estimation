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


def test_grades_the_first_face_only():
    b = BurstSelector(gap_seconds=2.0)
    b.add(frame(1), face(0.2), now=0.0)
    b.add(frame(2), face(0.9, sharpness=500), now=0.5)  # angrier and sharper, but too late
    b.add(frame(3), face(0.4), now=1.0)
    done = b.poll(now=3.5)
    assert done.face.hostility == 0.2
    assert done.frame[0, 0, 0] == 1
    assert not b.in_progress
    assert b.poll(now=10.0) is None


def test_later_faces_keep_the_burst_open():
    b = BurstSelector(gap_seconds=2.0)
    b.add(frame(), face(0.2), now=0.0)
    b.add(frame(), face(0.3), now=1.5)
    assert b.poll(now=3.0) is None   # only 1.5 s since the last face
    assert b.poll(now=3.6) is not None


def test_keep_alive_extends_a_graded_burst():
    b = BurstSelector(gap_seconds=2.0)
    b.add(frame(), face(0.2), now=0.0)
    b.keep_alive(now=1.5)
    assert b.poll(now=3.0) is None
    assert b.poll(now=3.6) is not None


def test_keep_alive_does_nothing_without_a_graded_face():
    b = BurstSelector(gap_seconds=2.0)
    b.keep_alive(now=0.0)
    assert not b.in_progress
    assert b.poll(now=10.0) is None


def test_next_burst_grades_its_own_first_face():
    b = BurstSelector(gap_seconds=1.0)
    b.add(frame(1), face(0.2), now=0.0)
    assert b.poll(now=5.0).face.hostility == 0.2
    b.add(frame(2), face(0.7), now=10.0)
    assert b.poll(now=15.0).face.hostility == 0.7


def test_stores_a_copy_of_the_frame():
    b = BurstSelector(gap_seconds=1.0)
    f = frame(7)
    b.add(f, face(0.5), now=0.0)
    f[:] = 0
    assert b.poll(now=5.0).frame[0, 0, 0] == 7
