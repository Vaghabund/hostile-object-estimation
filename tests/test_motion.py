import numpy as np

from src.motion_detector import MotionDetector


def scene(shift=0):
    img = np.zeros((240, 320, 3), dtype=np.uint8)
    img[60:180, 100 + shift:160 + shift] = 255  # a bright block with strong edges
    return img


def test_first_frame_is_never_motion():
    assert MotionDetector().detect(scene()) is False


def test_static_scene_is_quiet():
    m = MotionDetector()
    m.detect(scene())
    assert m.detect(scene()) is False


def test_moving_object_triggers():
    m = MotionDetector()
    m.detect(scene())
    assert m.detect(scene(shift=40)) is True
