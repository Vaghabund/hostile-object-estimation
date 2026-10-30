"""The /review picture: the most hostile recent panels in one image.

Placeholder layout until the design review: a plain grid, most hostile at top-left.
"""
import math

from PIL import Image

TILE_WIDTH = 320


def render_review(pictures, mood):
    """
    `pictures` are ShownPicture, already sorted most hostile first; `mood` is
    (average hostility, visit count) or None. Returns an RGB PIL image.
    """
    panels = [Image.open(p.panel).convert("RGB") for p in pictures]
    tile_w = TILE_WIDTH
    tile_h = round(tile_w * panels[0].height / panels[0].width)
    cols = math.ceil(math.sqrt(len(panels)))
    rows = math.ceil(len(panels) / cols)
    gap = 4

    sheet = Image.new("RGB", (cols * tile_w + (cols - 1) * gap, rows * tile_h + (rows - 1) * gap), "white")
    for i, panel in enumerate(panels):
        row, col = divmod(i, cols)
        sheet.paste(panel.resize((tile_w, tile_h), Image.LANCZOS), (col * (tile_w + gap), row * (tile_h + gap)))
    return sheet
