import numpy as np

from src.render import render


def test_render_has_requested_size_and_is_mono_when_asked():
    frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    img = render(frame, (200, 100, 360, 300), 0.7, timestamp=0, size=(800, 480), mono=True)
    assert img.size == (800, 480)
    # Portrait area contains only pure black/white after dithering.
    left = np.asarray(img.convert("L"))[:, :480]
    assert set(np.unique(left)) <= {0, 255}


def test_face_box_at_frame_edge_does_not_crash():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    img = render(frame, (0, 0, 120, 140), 0.0, timestamp=0, size=(800, 480))
    assert img.size == (800, 480)


def test_barometer_changes_the_picture():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    args = (frame, (200, 100, 360, 300), 0.5)
    without = render(*args, timestamp=0, mood=None)
    with_mood = render(*args, timestamp=0, mood=(0.3, 12))
    assert np.any(np.asarray(without) != np.asarray(with_mood))


def test_barometer_is_a_dithered_ramp_from_white_to_black():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    img = render(frame, (200, 100, 360, 300), 0.5, timestamp=0, size=(800, 480), mood=(0.5, 3))
    # Barometer layout for the default 800x480 display: panel x=508..772, y=336, strip below the header.
    strip = np.asarray(img.convert("L"))[336 + 36:336 + 50, 508 + 8:772 - 8]
    assert set(np.unique(strip)) <= {0, 255}
    third = strip.shape[1] // 3
    assert strip[:, :third].mean() > strip[:, -third:].mean() + 100
