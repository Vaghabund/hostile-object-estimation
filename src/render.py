"""Compose the picture shown on the e-ink display."""
from datetime import datetime

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

from config.settings import DISPLAY_SIZE

FACE_MARGIN = 0.6   # extra context around the face box, as a fraction of its size


def _font(size):
    return ImageFont.load_default(size=size)


LABELS = ("serene", "mildly irked", "displeased", "hostile", "furious")


def _label(score):
    return LABELS[sum(score >= t for t in (0.15, 0.35, 0.6, 0.85))]


def _label_font(draw, max_size, max_width):
    """One size for every mood label: the largest at which the longest still fits."""
    size = max_size
    while size > 12 and max(draw.textlength(t, font=_font(size)) for t in LABELS) > max_width:
        size -= 2
    return _font(size)


def _square_crop(frame, box):
    """Square crop centred on the face box, padded by FACE_MARGIN and clamped to the frame."""
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = box
    side = int(max(x2 - x1, y2 - y1) * (1 + FACE_MARGIN))
    side = min(side, w, h)
    cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
    left = min(max(cx - side // 2, 0), w - side)
    top = min(max(cy - side // 2, 0), h - side)
    return frame[top:top + side, left:left + side]


def render(frame, face_box, hostility, timestamp, size=DISPLAY_SIZE, mono=True, mood=None):
    """
    Return an RGB PIL image of `size`: the face on the left as a grayscale
    portrait, the hostility reading on the right.

    `mood` is (average hostility, visit count) over the last 24 h, drawn as a
    barometer above the date; None leaves it out.

    With mono=True the portrait is Floyd-Steinberg dithered here (text stays
    crisp); colour panels get the plain grayscale and do their own palette work.
    """
    width, height = size
    canvas = Image.new("RGB", size, "white")
    draw = ImageDraw.Draw(canvas)

    crop = _square_crop(frame, face_box)
    portrait = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)).convert("L")
    portrait = ImageOps.autocontrast(portrait.resize((height, height), Image.LANCZOS), cutoff=1)
    if mono:
        portrait = portrait.convert("1")
    canvas.paste(portrait.convert("RGB"), (0, 0))

    pad = 28
    x = height + pad
    panel_w = width - x - pad
    draw.text((x, pad), "HOSTILITY", fill="black", font=_font(24))
    draw.text((x, pad + 28), f"{round(hostility * 100)}%", fill="black", font=_font(120))
    draw.text((x, pad + 172), _label(hostility), fill="black", font=_label_font(draw, 64, panel_w))

    bar_y = pad + 260
    draw.rectangle([x, bar_y, x + panel_w, bar_y + 28], outline="black", width=3)
    fill_w = int(panel_w * hostility)
    if fill_w:
        draw.rectangle([x, bar_y, x + fill_w, bar_y + 28], fill="black")

    if mood is not None:
        _draw_barometer(canvas, draw, x, height - pad - 116, panel_w, *mood)

    when = datetime.fromtimestamp(timestamp)
    foot_y, foot_font = height - pad - 24, _font(24)
    draw.text((x, foot_y), when.strftime("%a %d %b"), fill="black", font=foot_font)
    draw.text((x + panel_w, foot_y), when.strftime("%H:%M"), fill="black", font=foot_font, anchor="ra")
    return canvas


BAROMETER_STRIP_TOP = 34     # offsets from the barometer's y
BAROMETER_STRIP_HEIGHT = 26
_END_LABEL_CLEARANCE = 60    # hide an end label when the marker is this close to it


def _dither_strip(w, h):
    """White-to-black ramp, Floyd-Steinberg dithered to pure black/white pixels."""
    ramp = np.tile(np.linspace(255, 0, w, dtype=np.float32), (h, 1))
    return Image.fromarray(ramp.astype(np.uint8), "L").convert("1").convert("RGB")


def _draw_barometer(canvas, draw, x, y, w, average, visits):
    """A dithered calm (white) to hostile (black) spectrum with a marker at the 24 h average."""
    draw.text((x, y), "LAST 24H", fill="black", font=_font(26))
    draw.text((x + w, y), f"{round(average * 100)}%", fill="black", font=_font(26), anchor="ra")

    top = y + BAROMETER_STRIP_TOP
    bottom = top + BAROMETER_STRIP_HEIGHT
    canvas.paste(_dither_strip(w + 1, BAROMETER_STRIP_HEIGHT + 1), (x, top))
    draw.rectangle([x, top, x + w, bottom], outline="black", width=2)  # keeps the white end visible

    mx = x + round(w * average)
    draw.polygon([(mx, bottom + 4), (mx - 9, bottom + 20), (mx + 9, bottom + 20)], fill="black")

    label_y = bottom + 6
    if mx - x > _END_LABEL_CLEARANCE:
        draw.text((x, label_y), "calm", fill="black", font=_font(18))
    if x + w - mx > _END_LABEL_CLEARANCE:
        draw.text((x + w, label_y), "hostile", fill="black", font=_font(18), anchor="ra")
