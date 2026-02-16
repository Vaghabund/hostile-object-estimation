from ultralytics import YOLO
import logging
import time
from config.settings import (
    YOLO_MODEL, 
    YOLO_CONFIDENCE_THRESHOLD, 
    YOLO_ENABLE_TRACKING
)
from src.shared_state import Detection

logger = logging.getLogger(__name__)

class YOLODetector:
    """
    Wrapper for YOLOv8 inference and tracking.
    """
    def __init__(self):
        logger.info(f"Loading YOLO model: {YOLO_MODEL}...")
        try:
            # Fix for PyTorch 2.6+ weights_only=True default
            import torch
            # Monkey patch torch.load to default weights_only=False temporarily
            # This is safer/easier than listing all safe globals which change between versions
            original_load = torch.load
            torch.load = lambda f, map_location=None, pickle_module=None, **kwargs: original_load(f, map_location, pickle_module, weights_only=False, **kwargs)
            
            # Auto-downloads model on first run
            self.model = YOLO(YOLO_MODEL + ".pt")
            
            # Restore original load
            torch.load = original_load
            
            logger.info("YOLO model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise

    def detect(self, frame):
        """
        Run inference on a frame.
        
        Args:
            frame: Numpy array (image)
            
        Returns:
            List[Detection]: List of detected objects
        """
        if frame is None:
            return []

        start_time = time.time()
        
        # Run inference (with tracking if enabled)
        # persist=True is crucial for tracking across frames
        if YOLO_ENABLE_TRACKING:
            results = self.model.track(
                frame, 
                conf=YOLO_CONFIDENCE_THRESHOLD, 
                persist=True, 
                verbose=False
            )
        else:
            results = self.model.predict(
                frame, 
                conf=YOLO_CONFIDENCE_THRESHOLD, 
                verbose=False
            )
        
        detections = []
        timestamp = time.time()
        
        # Process results
        for r in results:
            if r.boxes is None:
                continue
                
            boxes = r.boxes
            for box in boxes:
                # Get class name
                if box.cls is None:
                    continue
                cls_id = int(box.cls[0])
                if self.model.names and cls_id in self.model.names:
                    class_name = self.model.names[cls_id]
                else:
                    class_name = f"unknown_{cls_id}"
                
                # Get confidence
                if box.conf is None:
                    continue
                conf = float(box.conf[0])
                
                # Get track ID (if available)
                # handle box.id being None safely
                track_id = None
                if box.id is not None:
                     track_id = int(box.id[0])
                
                # Get bounding box [x1, y1, x2, y2]
                if box.xyxy is None:
                    continue
                bbox = box.xyxy[0].cpu().numpy().astype(int).tolist()
                
                det = Detection(
                    timestamp=timestamp,
                    class_name=class_name,
                    confidence=conf,
                    track_id=track_id,
                    bbox=bbox
                )
                detections.append(det)

        # Log performance occasionally
        inference_time = (time.time() - start_time) * 1000
        if len(detections) > 0:
            logger.debug(f"YOLO: Found {len(detections)} objects in {inference_time:.1f}ms")

        return detections
