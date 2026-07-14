from ultralytics import YOLO
import logging
import time
from typing import TYPE_CHECKING
from config.settings import (
    YOLO_MODEL,
    YOLO_ENABLE_TRACKING,
)
from src.shared_state import Detection

if TYPE_CHECKING:
    from src.runtime_settings import RuntimeSettings

logger = logging.getLogger(__name__)

class YOLODetector:
    """
    Wrapper for YOLOv8 inference and tracking.
    """
    def __init__(self, runtime_settings: 'RuntimeSettings'):
        self.settings = runtime_settings
        self.model = self._load_model()

    def _load_model(self):
        """Load the YOLO .pt model."""
        pt_path = YOLO_MODEL + ".pt"
        logger.info(f"Loading YOLO model (PyTorch): {pt_path}...")
        model = self._load_pt(pt_path)
        logger.info("YOLO model loaded successfully.")
        return model

    def _load_pt(self, pt_path):
        """Load a .pt model, working around the PyTorch 2.6+ weights_only default."""
        # Monkey patch torch.load to default weights_only=False temporarily.
        # weights_only=True rejects the non-tensor data stored in ultralytics .pt files.
        # We pop any caller-supplied 'weights_only' from kwargs to avoid a TypeError
        # when both the positional override and a kwarg are present simultaneously.
        import torch
        original_load = torch.load

        def _patched_load(f, map_location=None, pickle_module=None, **kwargs):
            kwargs.pop('weights_only', None)
            return original_load(f, map_location=map_location, pickle_module=pickle_module, weights_only=False, **kwargs)

        torch.load = _patched_load
        try:
            # Auto-downloads model on first run
            return YOLO(pt_path)
        finally:
            torch.load = original_load

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
        
        # Get current confidence threshold
        conf_threshold = self.settings.get_yolo_confidence()
        
        # Run inference (with tracking if enabled)
        # persist=True is crucial for tracking across frames
        if YOLO_ENABLE_TRACKING:
            results = self.model.track(
                frame, 
                conf=conf_threshold, 
                persist=True, 
                verbose=False
            )
        else:
            results = self.model.predict(
                frame, 
                conf=conf_threshold, 
                verbose=False
            )
        
        detections = []
        timestamp = time.time()
        names = self.model.names

        # Process results. Pull the whole boxes tensor to CPU once per result and
        # index numpy rows, instead of doing a per-box .cpu().numpy() device sync.
        for r in results:
            if r.boxes is None or len(r.boxes) == 0:
                continue

            boxes = r.boxes
            if boxes.xyxy is None or boxes.conf is None or boxes.cls is None:
                continue

            xyxy = boxes.xyxy.cpu().numpy().astype(int)
            confs = boxes.conf.cpu().numpy()
            clss = boxes.cls.cpu().numpy().astype(int)
            ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else None

            for i in range(len(xyxy)):
                cls_id = int(clss[i])
                if names and cls_id in names:
                    class_name = names[cls_id]
                else:
                    class_name = f"unknown_{cls_id}"

                # Filter by enabled classes (cheap check before building the object)
                if not self.settings.is_class_enabled(class_name):
                    continue

                det = Detection(
                    timestamp,
                    class_name,
                    float(confs[i]),
                    int(ids[i]) if ids is not None else None,
                    xyxy[i].tolist(),
                )
                detections.append(det)

        # Log performance occasionally
        inference_time = (time.time() - start_time) * 1000
        if len(detections) > 0:
            logger.debug(f"YOLO: Found {len(detections)} objects in {inference_time:.1f}ms")

        return detections
