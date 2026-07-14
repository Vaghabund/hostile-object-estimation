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

from config.settings import (
    FRAME_SELECTION_MAX_SCORED,
    FRAME_SELECTION_FACE_MAX_WIDTH,
)

logger = logging.getLogger(__name__)


def _to_gray(frame: np.ndarray) -> np.ndarray:
    """Return a grayscale view of a BGR (or already-gray) frame."""
    if frame.ndim == 3:
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return frame


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
            return self._sharpness_from_gray(_to_gray(frame))
        except Exception as e:
            logger.warning(f"Error calculating sharpness: {e}")
            return 0.0

    def _sharpness_from_gray(self, gray: np.ndarray) -> float:
        """Laplacian-variance sharpness from a precomputed grayscale frame."""
        # Calculate Laplacian variance (measures edge/detail intensity)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        # Normalize: typical range 0-500+, scale to 0-1 with saturation.
        # Very sharp images can exceed 1.0
        normalized = min(laplacian_var / 500.0, 1.0)
        return max(0.0, normalized)

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
            return self._detect_face_from_gray(_to_gray(frame))
        except Exception as e:
            logger.warning(f"Error detecting face: {e}")
            return False

    def _detect_face_from_gray(self, gray: np.ndarray) -> bool:
        """Run the Haar cascade on a precomputed grayscale frame.

        Downscales first: face presence is binary, so full resolution is wasted
        and detectMultiScale cost scales with pixel count. minSize is scaled by
        the same factor so detection behaviour is preserved.
        """
        if self.face_cascade is None:
            return False

        min_size = self.min_face_size
        h, w = gray.shape[:2]
        if 0 < FRAME_SELECTION_FACE_MAX_WIDTH < w:
            scale = FRAME_SELECTION_FACE_MAX_WIDTH / w
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            min_size = (
                max(15, int(self.min_face_size[0] * scale)),
                max(15, int(self.min_face_size[1] * scale)),
            )

        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=min_size,
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        return len(faces) > 0

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
            if frame is None or frame.size == 0:
                return 0.0

            # Ensure confidence is in valid range
            confidence = max(0.0, min(1.0, confidence))

            # Convert to grayscale ONCE and reuse for both face + sharpness
            # (previously each helper re-ran cvtColor on every scored frame).
            gray = _to_gray(frame)

            # Component 1: Face detection (highest priority)
            has_face = self._detect_face_from_gray(gray)
            face_score = self.face_weight if has_face else 0.0

            # Component 2: Sharpness (medium priority)
            sharpness = self._sharpness_from_gray(gray)
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
            # Only score a bounded, evenly-spaced sample. The Haar cascade is the
            # bottleneck, so scoring every one of up to FRAME_BUFFER_MAX frames is
            # wasteful; sampling ~18 keeps quality while capping the burst cost.
            n = len(frames)
            if n <= FRAME_SELECTION_MAX_SCORED:
                candidate_indices = range(n)
            else:
                candidate_indices = sorted(set(
                    int(i) for i in np.linspace(0, n - 1, FRAME_SELECTION_MAX_SCORED)
                ))

            best_idx = -1
            best_score = float("-inf")
            for i in candidate_indices:
                frame = frames[i]
                if frame is None:
                    continue

                # Get confidence from corresponding detection if available
                confidence = 0.5  # Default confidence
                if detections and i < len(detections) and detections[i] is not None:
                    confidence = detections[i].confidence

                score = self.score_frame(frame, confidence)
                if score > best_score:
                    best_score = score
                    best_idx = i

            if best_idx < 0:
                return None, -1

            best_frame = frames[best_idx]
            logger.debug(
                f"Selected frame {best_idx} (score: {best_score:.3f}) from {n} frames "
                f"(scored {len(list(candidate_indices))})"
            )
            return best_frame, best_idx
        except Exception as e:
            logger.error(f"Error selecting best frame: {e}")
            return frames[0] if frames[0] is not None else None, 0
