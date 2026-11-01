import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from config.settings import FACE_MODEL_PATH, FACE_MIN_WIDTH_PX, FACE_MIN_SHARPNESS
from src.hostility import hostility_score
from src.render import crop_rect

logger = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)


@dataclass
class FaceResult:
    box: tuple          # (x1, y1, x2, y2) in pixels
    hostility: float    # 0..1
    sharpness: float    # Laplacian variance of the face crop at SHARPNESS_SIZE; higher = sharper
    landmarks: tuple = ()  # the 478 mesh points as (x, y), each 0..1 across the frame

    @property
    def width(self):
        return self.box[2] - self.box[0]


def ensure_model(path: Path = FACE_MODEL_PATH) -> Path:
    """Download the face landmarker model on first run."""
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading face model to %s ...", path)
    tmp = path.with_name(path.name + ".part")
    urllib.request.urlretrieve(MODEL_URL, tmp)
    tmp.replace(path)
    return path


SHARPNESS_SIZE = 128  # crops are compared at one size, so big and small faces score alike


def sharpness(frame, box):
    x1, y1, x2, y2 = box
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return 0.0
    gray = cv2.resize(
        cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), (SHARPNESS_SIZE, SHARPNESS_SIZE), interpolation=cv2.INTER_AREA
    )
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


class FaceAnalyzer:
    """MediaPipe Face Landmarker: finds faces and their expression blendshapes in one pass."""

    def __init__(self, model_path: Path = FACE_MODEL_PATH):
        import mediapipe as mp
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python import vision

        self._mp = mp
        options = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=str(ensure_model(model_path))),
            running_mode=vision.RunningMode.IMAGE,
            output_face_blendshapes=True,
            num_faces=2,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

    def _detect(self, frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return self._landmarker.detect(
            self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        )

    def refine_landmarks(self, frame, box):
        """
        The face mesh found again in a tight crop around `box`, as (x, y) across the whole frame, or None.

        A small face in a 1280x720 frame gets a mesh that can sit tens of pixels off it; the same
        face filling a crop is placed accurately. Too slow to run on every frame, fine once per picture.
        """
        h, w = frame.shape[:2]
        left, top, side = crop_rect(frame, box)
        result = self._detect(frame[top:top + side, left:left + side])
        if not result.face_landmarks:
            return None
        # The face the box was drawn around is the one nearest the crop's centre.
        def off_centre(landmarks):
            return abs(np.mean([p.x for p in landmarks]) - 0.5) + abs(np.mean([p.y for p in landmarks]) - 0.5)
        landmarks = min(result.face_landmarks, key=off_centre)
        return tuple(((left + p.x * side) / w, (top + p.y * side) / h) for p in landmarks)

    def analyze(self, frame):
        """Return the most hostile usable FaceResult in a BGR frame, or None."""
        h, w = frame.shape[:2]
        result = self._detect(frame)

        best = None
        for landmarks, shapes in zip(result.face_landmarks, result.face_blendshapes):
            xs = [p.x for p in landmarks]
            ys = [p.y for p in landmarks]
            # A face running off the frame edge would show up cut off on the panel.
            if min(xs) < 0 or min(ys) < 0 or max(xs) > 1 or max(ys) > 1:
                logger.debug("Face rejected: runs off the frame edge")
                continue
            box = (
                max(0, int(min(xs) * w)), max(0, int(min(ys) * h)),
                min(w, int(max(xs) * w)), min(h, int(max(ys) * h)),
            )
            if box[2] - box[0] < FACE_MIN_WIDTH_PX:
                logger.debug("Face rejected: %d px wide (min %d)", box[2] - box[0], FACE_MIN_WIDTH_PX)
                continue
            blend = {c.category_name: c.score for c in shapes}
            face = FaceResult(
                box, hostility_score(blend), sharpness(frame, box),
                tuple((p.x, p.y) for p in landmarks),
            )
            if face.sharpness < FACE_MIN_SHARPNESS:
                logger.debug("Face rejected: sharpness %.0f (min %.0f)", face.sharpness, FACE_MIN_SHARPNESS)
                continue
            if best is None or face.hostility > best.hostility:
                best = face
        return best

    def close(self):
        self._landmarker.close()
