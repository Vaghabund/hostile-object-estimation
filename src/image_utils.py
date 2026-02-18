"""
Image utility functions for drawing bounding boxes and creating collages.
Optimized for low hardware specs and efficient memory usage.
"""
import cv2
import io
import logging
import time
from PIL import Image, ImageDraw, ImageFont
from typing import List, Optional, Tuple
from src.shared_state import Detection

logger = logging.getLogger(__name__)


def _resample_high_quality():
    """Return a high-quality resample filter compatible with multiple Pillow versions."""
    resampling = getattr(Image, "Resampling", None)
    if resampling and hasattr(resampling, "LANCZOS"):
        return resampling.LANCZOS
    if hasattr(Image, "LANCZOS"):
        return Image.LANCZOS
    return Image.ANTIALIAS


def _create_detection_crop(frame, det: Detection, target_size: Tuple[int, int], padding: float = 0.1) -> Optional[Image.Image]:
    """Crop and resize a detection region from the frame."""
    if frame is None or not det or not det.bbox:
        return None

    try:
        x1, y1, x2, y2 = det.bbox
        width = max(1, x2 - x1)
        height = max(1, y2 - y1)
        pad_x = int(width * padding)
        pad_y = int(height * padding)

        h, w = frame.shape[:2]
        x1 = max(0, x1 - pad_x)
        y1 = max(0, y1 - pad_y)
        x2 = min(w, x2 + pad_x)
        y2 = min(h, y2 + pad_y)

        if x2 <= x1 or y2 <= y1:
            return None

        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            return None

        crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(crop_rgb, target_size, interpolation=cv2.INTER_AREA)
        return Image.fromarray(resized)
    except Exception as exc:
        logger.warning("Failed to create crop for %s: %s", det.class_name, exc)
        return None


def attach_detection_thumbnails(frame, detections: List[Detection], target_size: Tuple[int, int] = (200, 200), quality: int = 50) -> None:
    """Attach serialized thumbnails to detections for later collages."""
    if frame is None or not detections:
        return

    for det in detections:
        if det.thumbnail is not None:
            continue

        crop_image = _create_detection_crop(frame, det, target_size)
        if crop_image is None:
            continue

        try:
            buffer = io.BytesIO()
            crop_image.save(buffer, "JPEG", quality=quality, optimize=True)
            det.thumbnail = buffer.getvalue()
        except Exception as exc:
            logger.warning("Failed to serialize thumbnail for %s: %s", det.class_name, exc)


def draw_detections_on_frame(frame, detections: List[Detection]):
    """
    Draw bounding boxes and labels on frame.
    
    Args:
        frame: numpy array (BGR format)
        detections: List of Detection objects
        
    Returns:
        Frame with drawn bounding boxes and labels
    """
    if frame is None:
        return None
    
    # Create a copy to avoid modifying original
    annotated_frame = frame.copy()
    
    for det in detections:
        x1, y1, x2, y2 = det.bbox
        
        # Choose color based on class (simple hash-based color assignment)
        color_hash = hash(det.class_name) % 7
        colors = [
            (0, 255, 0),    # Green
            (255, 0, 0),    # Blue
            (0, 0, 255),    # Red
            (255, 255, 0),  # Cyan
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Yellow
            (128, 0, 128),  # Purple
        ]
        color = colors[color_hash]
        
        # Draw bounding box
        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
        
        # Prepare label text
        label = f"{det.class_name} {det.confidence:.2f}"
        if det.track_id is not None:
            label += f" ID:{det.track_id}"
        
        # Calculate label size
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 1
        (text_width, text_height), baseline = cv2.getTextSize(
            label, font, font_scale, thickness
        )
        
        # Draw label background
        label_y = max(y1 - 5, text_height + 5)
        cv2.rectangle(
            annotated_frame,
            (x1, label_y - text_height - baseline - 2),
            (x1 + text_width + 2, label_y),
            color,
            -1  # Filled
        )
        
        # Draw label text
        cv2.putText(
            annotated_frame,
            label,
            (x1 + 1, label_y - baseline - 1),
            font,
            font_scale,
            (255, 255, 255),  # White text
            thickness,
            cv2.LINE_AA
        )
    
    return annotated_frame


def create_detection_collage_from_history(detections: List[Detection],
                                          max_images: int = 12,
                                          target_size: Tuple[int, int] = (200, 200),
                                          collage_width: int = 3):
    """Build a collage of detection thumbnails ordered by recency."""
    if not detections:
        return None

    try:
        font_main = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except (OSError, IOError):
        font_main = ImageFont.load_default()
        font_small = ImageFont.load_default()

    sorted_detections = sorted(detections, key=lambda d: d.timestamp, reverse=True)
    resample_filter = _resample_high_quality()
    tiles: List[Image.Image] = []

    for det in sorted_detections:
        if det.thumbnail is None:
            continue

        try:
            thumb = Image.open(io.BytesIO(det.thumbnail)).convert("RGB")
        except Exception as exc:
            logger.warning("Failed to load stored thumbnail for %s: %s", det.class_name, exc)
            continue

        if thumb.size != target_size:
            thumb = thumb.resize(target_size, resample_filter)

        draw = ImageDraw.Draw(thumb)
        overlay_height = 46
        draw.rectangle(
            [
                (0, target_size[1] - overlay_height),
                (target_size[0], target_size[1])
            ],
            fill=(0, 0, 0)
        )

        timestamp_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(det.timestamp))
        label = f"{det.class_name} ({det.confidence:.2f})"

        draw.text((6, target_size[1] - overlay_height + 6), label, fill='white', font=font_main)
        draw.text((6, target_size[1] - overlay_height + 24), timestamp_text, fill='white', font=font_small)

        tiles.append(thumb)

        if len(tiles) >= max_images:
            break

    if not tiles:
        return None

    rows = (len(tiles) + collage_width - 1) // collage_width
    collage_height = rows * target_size[1]
    collage_width_px = collage_width * target_size[0]

    collage = Image.new('RGB', (collage_width_px, collage_height), color='black')

    for idx, tile in enumerate(tiles):
        row = idx // collage_width
        col = idx % collage_width
        x = col * target_size[0]
        y = row * target_size[1]
        collage.paste(tile, (x, y))

    return collage


def create_latest_detections_collage(frame, detections: List[Detection],
                                     max_crops=9, target_size=(150, 150),
                                     collage_width=3):
    """
    Create a collage from the latest frame's detections by cropping detected regions.
    Optimized for low memory usage.
    
    Args:
        frame: The current frame (BGR format)
        detections: List of Detection objects from current frame
        max_crops: Maximum number of crops
        target_size: Size to resize each crop (width, height)
        collage_width: Number of images per row
        
    Returns:
        PIL Image of the collage, or None if no valid crops
    """
    if frame is None or not detections:
        return None
    
    # Limit for memory efficiency
    detections_to_use = detections[:max_crops]
    crops = []
    
    for det in detections_to_use:
        crop_pil = _create_detection_crop(frame, det, target_size)
        if crop_pil is None:
            continue

        draw = ImageDraw.Draw(crop_pil)
        label = f"{det.class_name}\n{det.confidence:.2f}"

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
        except (OSError, IOError):
            font = ImageFont.load_default()

        draw.rectangle([(0, 0), (target_size[0], 35)], fill=(0, 0, 0))
        draw.text((5, 5), label, fill='white', font=font)

        crops.append(crop_pil)
    
    if not crops:
        return None
    
    # Calculate collage dimensions
    rows = (len(crops) + collage_width - 1) // collage_width
    collage_height = rows * target_size[1]
    collage_img_width = collage_width * target_size[0]
    
    # Create collage
    collage = Image.new('RGB', (collage_img_width, collage_height), color='black')
    
    for idx, crop in enumerate(crops):
        row = idx // collage_width
        col = idx % collage_width
        x = col * target_size[0]
        y = row * target_size[1]
        collage.paste(crop, (x, y))
    
    return collage
