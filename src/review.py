"""The /review picture: the most hostile recent faces next to the mood of the window.

Laid out like the panel (800x480 units, faces left, reading right) but only ever
sent to Telegram, so it is drawn at whatever size it is asked for. The dither is
done at that final size: rescaling a dithered image turns it to grey mush.
"""
import math
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageOps

from src.render import _font, _label, _label_font

PHOTO_SIZE = (1280, 768)      # inline Telegram photo; at most 1280 on the long edge so it is not rescaled
DOCUMENT_SIZE = (2560, 1536)  # sent as a file, untouched, for zooming into faces


def render_review(pictures, hourly, mood, now, window_label="24H", size=PHOTO_SIZE):
    """
    `pictures` are ShownPicture, most hostile first. `hourly` is one mean
    hostility (or None) per clock hour, oldest first, the last being the current
    hour. `mood` is (average hostility, visit count) or None. `now` is unix time.
    """
    width, height = size
    s = width / 800  # one panel pixel
    canvas = Image.new("RGB", size, "white")
    _draw_grid(canvas, pictures, height, s)

    draw = ImageDraw.Draw(canvas)
    pad = round(28 * s)
    x = height + pad
    w = width - x - pad
    average = mood[0] if mood else None
    draw.text((x, pad), f"MOOD · LAST {window_label}", fill="black", font=_font(round(24 * s)))
    draw.text((x, pad + 28 * s), "–" if average is None else f"{round(average * 100)}%",
              fill="black", font=_font(round(120 * s)))
    if average is not None:
        draw.text((x, pad + 172 * s), _label(average), fill="black", font=_label_font(draw, round(64 * s), w))

    _draw_chart(canvas, draw, x, round(pad + 268 * s), w, round(height - pad - 68 * s), hourly, average, now, s)

    when = datetime.fromtimestamp(now)
    foot_y, foot_font = height - pad - 24 * s, _font(round(24 * s))
    draw.text((x, foot_y), when.strftime("%a %d %b"), fill="black", font=foot_font)
    draw.text((x + w, foot_y), when.strftime("%H:%M"), fill="black", font=foot_font, anchor="ra")
    return canvas


def _draw_grid(canvas, pictures, side_total, s):
    """Square grid on the left, as many columns as needed, each face with its score in a black corner tag."""
    draw = ImageDraw.Draw(canvas)
    cols = math.ceil(math.sqrt(len(pictures)))
    gap = max(2, round(4 * s))
    tile = (side_total - (cols - 1) * gap) // cols
    tag_font = _font(round(max(14, 72 / cols) * s))
    inset = round(4 * s)
    for i, picture in enumerate(pictures):
        row, col = divmod(i, cols)
        x, y = col * (tile + gap), row * (tile + gap)
        with Image.open(picture.face) as face:
            face = ImageOps.autocontrast(face.convert("L").resize((tile, tile), Image.LANCZOS), cutoff=1)
        canvas.paste(face.convert("1").convert("RGB"), (x, y))

        text = f"{round(picture.hostility * 100)}%"
        left, top, right, bottom = draw.textbbox((0, 0), text, font=tag_font)
        tag_w, tag_h = right + 2 * inset, bottom + inset
        draw.rectangle([x, y + tile - tag_h, x + tag_w, y + tile], fill="black")
        draw.text((x + inset, y + tile - tag_h + inset // 2), text, fill="white", font=tag_font)


def _draw_chart(canvas, draw, x, top, w, bottom, hourly, average, now, s):
    """One bar per clock hour, height = mean hostility; a dot where nobody came; dashed line at the average."""
    line = max(1, round(s))
    bar_w = w / len(hourly)
    draw.line([(x, top), (x + w, top)], fill="black", width=line)  # 100% guide
    draw.text((x + w, top - 4 * s), "100%", fill="black", font=_font(round(16 * s)), anchor="rd")

    for i, value in enumerate(hourly):
        left, right = round(x + i * bar_w + line), round(x + (i + 1) * bar_w - line)
        if value is None:
            cx, r = (left + right) // 2, max(1, round(1.5 * s))
            draw.ellipse([cx - r, bottom - 5 * s - r, cx + r, bottom - 5 * s + r], fill="black")
            continue
        h = max(2 * line, round((bottom - top) * value))
        canvas.paste(_shade(right - left, h), (left, bottom - h))
        draw.rectangle([left, bottom - h, right, bottom], outline="black", width=line)

    if average is not None:
        y = round(bottom - (bottom - top) * average)
        dash = round(6 * s)
        for dx in range(0, w, 2 * dash):
            draw.line([(x + dx, y), (x + min(dx + dash, w), y)], fill="black", width=line * 2)
    draw.line([(x, bottom), (x + w, bottom)], fill="black", width=2 * line)

    start = datetime.fromtimestamp(now).replace(minute=0, second=0, microsecond=0) - timedelta(hours=len(hourly) - 1)
    axis_font = _font(round(16 * s))
    # first and last label flush with the chart's edges, the middle one centred under its bar
    for i, lx, anchor in ((0, x, "la"), (len(hourly) // 2, x + (len(hourly) // 2 + 0.5) * bar_w, "ma"),
                          (len(hourly) - 1, x + w, "ra")):
        label = (start + timedelta(hours=i)).strftime("%H:00")
        draw.text((lx, bottom + 6 * s), label, fill="black", font=axis_font, anchor=anchor)


def _shade(w, h):
    """A flat mid-grey, dithered: every bar the same so height alone carries the value."""
    return Image.new("L", (w, h), 150).convert("1").convert("RGB")
