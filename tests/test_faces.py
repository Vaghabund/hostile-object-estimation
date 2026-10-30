import cv2
import numpy as np

from src.faces import sharpness


def texture(side):
    rng = np.random.default_rng(0)
    small = rng.integers(0, 255, (32, 32, 3), dtype=np.uint8)
    return cv2.resize(small, (side, side), interpolation=cv2.INTER_NEAREST)


def test_same_face_scores_alike_at_any_size():
    small, big = texture(160), texture(480)
    a = sharpness(small, (0, 0, 160, 160))
    b = sharpness(big, (0, 0, 480, 480))
    assert abs(a - b) / max(a, b) < 0.2


def test_motion_blur_lowers_sharpness():
    img = texture(256)
    kernel = np.zeros((15, 15), np.float32)
    kernel[7, :] = 1 / 15  # horizontal smear
    smeared = cv2.filter2D(img, -1, kernel)
    box = (0, 0, 256, 256)
    assert sharpness(smeared, box) < 0.5 * sharpness(img, box)
