"""The main face marks (outline, brows, eyes, nose, mouth), drawn as line art over the portrait."""
from PIL import Image, ImageDraw

# Indices into MediaPipe's 478-point face mesh, in drawing order.
OUTLINE = (10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152,
           148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109)
EYE_LEFT = (263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466)
EYE_RIGHT = (33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246)
LIPS_OUTER = (61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291, 375, 321, 405, 314, 17, 84, 181, 91, 146)
LIPS_INNER = (78, 191, 80, 81, 82, 13, 312, 311, 310, 415, 308, 324, 318, 402, 317, 14, 87, 178, 88, 95)
CLOSED = (OUTLINE, EYE_LEFT, EYE_RIGHT, LIPS_OUTER, LIPS_INNER)

BROW_LEFT = (336, 296, 334, 293, 300)
BROW_RIGHT = (70, 63, 105, 66, 107)
NOSE = (129, 98, 97, 2, 326, 327, 358)
OPEN = (BROW_LEFT, BROW_RIGHT, NOSE)


def marks_mask(size, points, width):
    """
    A mask (white where a mark is) for a `size` image. `points` maps a mesh
    index to an (x, y) pixel position; `width` is the line width in pixels.
    Inverting the portrait through this mask gives lines that are white over
    dark areas and black over light ones, so they read on any picture.
    """
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    for path in [(p + p[:1]) for p in CLOSED] + [list(p) for p in OPEN]:
        draw.line([points[i] for i in path], fill=255, width=width, joint="curve")
    return mask
