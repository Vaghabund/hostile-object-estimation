"""
Image utility functions for drawing bounding boxes and creating collages.
Optimized for low hardware specs and efficient memory usage.
"""
import cv2
import numpy as np
from PIL import Image
import logging
from typing import List
from src.shared_state import Detection

logger = logging.getLogger(__name__)

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


def create_detection_collage(detections: List[Detection], frame_getter, 
                             max_images=12, target_size=(120, 120),
                             collage_width=4):
    """
    Create a collage from recent detections.
    Optimized for low memory usage.
    
    Args:
        detections: List of Detection objects (most recent first)
        frame_getter: Function to get frames by timestamp
        max_images: Maximum number of crops to include
        target_size: Size to resize each crop (width, height)
        collage_width: Number of images per row
        
    Returns:
        PIL Image of the collage, or None if no valid crops
    """
    if not detections:
        return None
    
    # Limit number of images for memory efficiency
    detections_to_use = detections[:max_images]
    crops = []
    
    for det in detections_to_use:
        # Get the frame (assuming we can still access it)
        # For now, we'll skip this as we don't store historical frames
        # This function will be called with the latest detections and frame
        # So we need a different approach
        pass
    
    # This function needs to be called differently - see create_detection_collage_from_history
    return None


def create_detection_collage_from_history(detections: List[Detection],
                                          max_images=12, 
                                          collage_width=4):
    """
    Create a text-based summary collage since we don't store historical frames.
    For low hardware, we avoid storing frames in memory.
    
    Args:
        detections: List of Detection objects
        max_images: Maximum items to show
        collage_width: Items per row (for formatting)
        
    Returns:
        PIL Image with text summary, or None if no detections
    """
    if not detections:
        return None
    
    # Group detections by class
    from collections import Counter
    class_counts = Counter(det.class_name for det in detections[-max_images:])
    
    # Create a simple visualization as a bar chart
    # Calculate dimensions
    img_width = 600
    img_height = max(300, len(class_counts) * 50 + 100)
    
    # Create white background
    img = Image.new('RGB', (img_width, img_height), color='white')
    
    # Use PIL ImageDraw to create visualization
    from PIL import ImageDraw, ImageFont
    draw = ImageDraw.Draw(img)
    
    try:
        # Try to use default font, fall back to basic if not available
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        small_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    except:
        font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # Title
    draw.text((20, 20), "Detection Summary", fill='black', font=font)
    draw.text((20, 50), f"Total: {len(detections[-max_images:])} detections", 
              fill='gray', font=small_font)
    
    # Draw bars
    y_offset = 90
    max_count = max(class_counts.values()) if class_counts else 1
    bar_max_width = img_width - 200
    
    for class_name, count in class_counts.most_common():
        # Label
        draw.text((20, y_offset), f"{class_name}:", fill='black', font=small_font)
        
        # Bar
        bar_width = int((count / max_count) * bar_max_width)
        draw.rectangle(
            [(150, y_offset), (150 + bar_width, y_offset + 30)],
            fill='#4CAF50',
            outline='#2E7D32'
        )
        
        # Count
        draw.text((160 + bar_width, y_offset + 5), str(count), 
                 fill='black', font=small_font)
        
        y_offset += 45
    
    return img


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
        try:
            x1, y1, x2, y2 = det.bbox
            
            # Add some padding (10% of bbox size)
            width = x2 - x1
            height = y2 - y1
            pad_x = int(width * 0.1)
            pad_y = int(height * 0.1)
            
            # Ensure coordinates are within frame bounds
            h, w = frame.shape[:2]
            x1 = max(0, x1 - pad_x)
            y1 = max(0, y1 - pad_y)
            x2 = min(w, x2 + pad_x)
            y2 = min(h, y2 + pad_y)
            
            # Crop the detection
            crop = frame[y1:y2, x1:x2]
            
            if crop.size == 0:
                continue
            
            # Convert BGR to RGB
            crop_rgb = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
            
            # Resize to target size
            crop_resized = cv2.resize(crop_rgb, target_size, interpolation=cv2.INTER_AREA)
            
            # Convert to PIL Image
            crop_pil = Image.fromarray(crop_resized)
            
            # Add label
            from PIL import ImageDraw, ImageFont
            draw = ImageDraw.Draw(crop_pil)
            label = f"{det.class_name}\n{det.confidence:.2f}"
            
            # Draw semi-transparent background for text
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
            except:
                font = ImageFont.load_default()
            
            # Text background - use simple opaque background for efficiency
            draw.rectangle([(0, 0), (target_size[0], 35)], fill=(0, 0, 0))
            draw.text((5, 5), label, fill='white', font=font)
            
            crops.append(crop_pil)
            
        except Exception as e:
            logger.warning(f"Failed to crop detection: {e}")
            continue
    
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
