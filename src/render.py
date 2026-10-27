"""Compose the picture shown on the e-ink display."""
from datetime import datetime

import cv2
from PIL import Image, ImageDraw, ImageFont, ImageOps

from config.settings import DISPLAY_SIZE

FACE_MARGIN = 0.6   # extra context around the face box, as a fraction of its size


def _font(size):
    return ImageFont.load_default(size=size)


def _label(score):
    if score < 0.15:
        return "serene"
    if score < 0.35:
        return "mildly irked"
    if score < 0.6:
        return "displeased"
    if score < 0.85:
        return "hostile"
    return "furious"


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


def render(frame, face_box, hostility, timestamp, size=DISPLAY_SIZE, mono=True):
    """
    Return an RGB PIL image of `size`: the face on the left as a grayscale
    portrait, the hostility reading on the right.

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
    draw.text((x, pad), "HOSTILITY", fill="black", font=_font(36))
    draw.text((x, pad + 50), f"{round(hostility * 100)}%", fill="black", font=_font(110))
    draw.text((x, pad + 190), _label(hostility), fill="black", font=_font(40))

    bar_y = pad + 260
    draw.rectangle([x, bar_y, x + panel_w, bar_y + 28], outline="black", width=3)
    fill_w = int(panel_w * hostility)
    if fill_w:
        draw.rectangle([x, bar_y, x + fill_w, bar_y + 28], fill="black")

    stamp = datetime.fromtimestamp(timestamp).strftime("%a %d %b  %H:%M")
    draw.text((x, height - pad - 28), stamp, fill="black", font=_font(28))
    return canvas
