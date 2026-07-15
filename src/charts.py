"""Chart rendering for pattern-of-life analytics.

Builds on cv2/numpy/PIL only (all already project dependencies) — no
matplotlib or other charting library needed for two fairly simple plots.
"""
import logging
from typing import List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageDraw

from src.image_utils import _load_font

logger = logging.getLogger(__name__)

_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def render_hour_weekday_heatmap(matrix: List[List[int]],
                                title: str = "Activity by Hour & Weekday") -> Image.Image:
    """Render a 7x24 (weekday x hour) activity matrix as a calendar-style heatmap."""
    arr = np.array(matrix, dtype=np.float32)  # 7 rows x 24 cols
    max_val = float(arr.max())

    if max_val <= 0:
        norm = np.zeros_like(arr, dtype=np.uint8)
    else:
        norm = np.clip(arr / max_val * 255, 0, 255).astype(np.uint8)

    colored_bgr = cv2.applyColorMap(norm, cv2.COLORMAP_TURBO)

    cell = 24
    grid_bgr = cv2.resize(colored_bgr, (24 * cell, 7 * cell), interpolation=cv2.INTER_NEAREST)

    # Force empty cells to a neutral gray instead of the colormap's color-for-0,
    # so "no activity" reads visually distinct from "low activity".
    zero_mask = (arr == 0)
    if zero_mask.any():
        zero_big = cv2.resize(zero_mask.astype(np.uint8), (24 * cell, 7 * cell),
                              interpolation=cv2.INTER_NEAREST).astype(bool)
        grid_bgr[zero_big] = (40, 40, 40)

    grid_rgb = cv2.cvtColor(grid_bgr, cv2.COLOR_BGR2RGB)
    grid_img = Image.fromarray(grid_rgb)

    left_margin, top_margin, bottom_margin = 46, 34, 28
    width = left_margin + grid_img.width
    height = top_margin + grid_img.height + bottom_margin

    canvas = Image.new("RGB", (width, height), color=(18, 18, 18))
    canvas.paste(grid_img, (left_margin, top_margin))

    draw = ImageDraw.Draw(canvas)
    font_title = _load_font(13, bold=True)
    font_label = _load_font(11)

    draw.text((10, 8), title, fill="white", font=font_title)
    for i, wd in enumerate(_WEEKDAYS):
        y = top_margin + i * cell + cell // 2 - 6
        draw.text((6, y), wd, fill="white", font=font_label)
    for h in range(0, 24, 3):
        x = left_margin + h * cell + 4
        draw.text((x, top_margin + grid_img.height + 6), str(h), fill="white", font=font_label)

    return canvas


def render_spatial_heatmap(points: List[Tuple[float, float]],
                           background: Optional[np.ndarray] = None,
                           grid_size: Tuple[int, int] = (32, 24),
                           out_size: Tuple[int, int] = (480, 360)) -> Optional[Image.Image]:
    """Render normalized (cx, cy) detection centroids as a heatmap, optionally
    alpha-blended over a reference frame (BGR numpy array) for spatial context."""
    if not points:
        return None

    cols, rows = grid_size
    grid = np.zeros((rows, cols), dtype=np.float32)
    for cx, cy in points:
        cx = min(max(cx, 0.0), 0.999)
        cy = min(max(cy, 0.0), 0.999)
        grid[int(cy * rows), int(cx * cols)] += 1

    grid = cv2.GaussianBlur(grid, (0, 0), sigmaX=1.2)
    max_val = float(grid.max())
    if max_val <= 0:
        return None

    norm = np.clip(grid / max_val * 255, 0, 255).astype(np.uint8)
    colored = cv2.applyColorMap(norm, cv2.COLORMAP_JET)
    colored_big = cv2.resize(colored, out_size, interpolation=cv2.INTER_LINEAR)

    if background is not None:
        bg = cv2.resize(background, out_size)
        if bg.ndim == 2:  # grayscale safety net
            bg = cv2.cvtColor(bg, cv2.COLOR_GRAY2BGR)
        blended = cv2.addWeighted(bg, 0.55, colored_big, 0.45, 0)
    else:
        blended = colored_big

    rgb = cv2.cvtColor(blended, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)
