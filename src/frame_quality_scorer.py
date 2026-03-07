"""
Frame Quality Scoring Module

Evaluates frame quality based on:
1. Face presence (highest priority)
2. Image sharpness (Laplacian variance)
3. Detection confidence (lowest priority)

Provides a composite score for selecting the best frame from a detection sequence.
"""

import cv2
import logging
import numpy as np
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


class FrameQualityScorer:
    """Scores frames based on quality metrics."""
    
    def __init__(
        self,
        face_detector_type: str = "cascade",
        min_face_size: Tuple[int, int] = (30, 30),
        face_weight: float = 1.0,
        sharpness_weight: float = 0.8,
        confidence_weight: float = 0.5
    ):
        """
        Initialize frame quality scorer.
        
        Args:
            face_detector_type: "cascade" for OpenCV Haar Cascade (default, fast)
            min_face_size: Minimum face size (width, height) to detect
            face_weight: Weight for face presence (0-1, default 1.0)
            sharpness_weight: Weight for sharpness metric (0-1, default 0.8)
            confidence_weight: Weight for detection confidence (0-1, default 0.5)
        """
        self.face_detector_type = face_detector_type
        self.min_face_size = min_face_size
        self.face_weight = face_weight
        self.sharpness_weight = sharpness_weight
        self.confidence_weight = confidence_weight
        
        # Initialize face detector
        self.face_cascade = None
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            if self.face_cascade.empty():
                logger.warning("Failed to load Haar Cascade face detector")
                self.face_cascade = None
            else:
                logger.info(f"Loaded face detector: {self.face_detector_type}")
        except Exception as e:
            logger.error(f"Error initializing face detector: {e}")
            self.face_cascade = None

    def calculate_sharpness(self, frame: np.ndarray) -> float:
        """
        Calculate image sharpness using Laplacian variance.
        
        Higher values = sharper image.
        Typical range: 0-1000+ (normalized to 0-1 for scoring)
        
        Args:
            frame: Input frame (BGR or grayscale)
            
        Returns:
            Normalized sharpness score (0-1, but can exceed 1 for very sharp images)
        """
        try:
            if frame is None or frame.size == 0:
                return 0.0
            
            # Convert to grayscale if needed
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            
            # Calculate Laplacian variance (measures edge/detail intensity)
            laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
            
            # Normalize: typical range 0-500+, scale to 0-1 with saturation
            # Very sharp images can exceed 1.0
            normalized = min(laplacian_var / 500.0, 1.0)
            return max(0.0, normalized)
        except Exception as e:
            logger.warning(f"Error calculating sharpness: {e}")
            return 0.0

    def detect_face(self, frame: np.ndarray) -> bool:
        """
        Detect if frame contains a face.
        
        Args:
            frame: Input frame (BGR)
            
        Returns:
            True if face detected, False otherwise
        """
        if self.face_cascade is None or frame is None or frame.size == 0:
            return False
        
        try:
            # Convert to grayscale
            if len(frame.shape) == 3:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            else:
                gray = frame
            
            # Detect faces
            faces = self.face_cascade.detectMultiScale(
                gray,
                scaleFactor=1.1,
                minNeighbors=5,
                minSize=self.min_face_size,
                flags=cv2.CASCADE_SCALE_IMAGE
            )
            
            return len(faces) > 0
        except Exception as e:
            logger.warning(f"Error detecting face: {e}")
            return False

    def score_frame(
        self,
        frame: np.ndarray,
        confidence: float = 0.5
    ) -> float:
        """
        Calculate composite quality score for a frame.
        
        Hierarchy (from most to least important):
        1. Face presence (binary, highest weight)
        2. Image sharpness (continuous, medium weight)
        3. Detection confidence (continuous, lowest weight)
        
        Args:
            frame: Input frame (BGR)
            confidence: Detection confidence (0-1)
            
        Returns:
            Composite score (0-1, but can exceed 1 if face present + sharp)
        """
        try:
            # Ensure confidence is in valid range
            confidence = max(0.0, min(1.0, confidence))
            
            # Component 1: Face detection (highest priority)
            has_face = self.detect_face(frame)
            face_score = self.face_weight if has_face else 0.0
            
            # Component 2: Sharpness (medium priority)
            sharpness = self.calculate_sharpness(frame)
            sharpness_score = sharpness * self.sharpness_weight
            
            # Component 3: Confidence (lowest priority)
            confidence_score = confidence * self.confidence_weight
            
            # Weighted sum: face presence is considered "on top" of other metrics
            # If face present, sharpness and confidence are multipliers
            if has_face:
                # Face present: boost score significantly, still consider sharpness
                composite = self.face_weight + (sharpness_score * 0.5) + (confidence_score * 0.3)
            else:
                # No face: score based on sharpness and confidence
                composite = sharpness_score + confidence_score
            
            return composite
        except Exception as e:
            logger.error(f"Error scoring frame: {e}")
            return 0.0

    def select_best_frame(
        self,
        frames: list,
        detections: Optional[list] = None
    ) -> Tuple[Optional[np.ndarray], int]:
        """
        Select the best frame from a list of frames.
        
        Args:
            frames: List of frames (np.ndarray) to evaluate
            detections: Optional list of Detection objects (same length as frames)
                      Used to extract confidence scores
            
        Returns:
            Tuple of (best_frame, best_index) or (None, -1) if list is empty
        """
        if not frames or len(frames) == 0:
            return None, -1
        
        try:
            scores = []
            for i, frame in enumerate(frames):
                if frame is None:
                    scores.append(-1.0)  # Penalize None frames
                    continue
                
                # Get confidence from corresponding detection if available
                confidence = 0.5  # Default confidence
                if detections and i < len(detections) and detections[i] is not None:
                    confidence = detections[i].confidence
                
                score = self.score_frame(frame, confidence)
                scores.append(score)
            
            # Find best frame
            best_idx = scores.index(max(scores)) if scores else -1
            best_frame = frames[best_idx] if best_idx >= 0 else None
            
            logger.debug(f"Selected frame {best_idx} (score: {scores[best_idx]:.3f}) from {len(frames)} frames")
            return best_frame, best_idx
        except Exception as e:
            logger.error(f"Error selecting best frame: {e}")
            return frames[0] if frames[0] is not None else None, 0
