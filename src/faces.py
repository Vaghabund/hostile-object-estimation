import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from config.settings import FACE_MODEL_PATH, FACE_MIN_WIDTH_PX, FACE_MIN_SHARPNESS
from src.hostility import hostility_score

logger = logging.getLogger(__name__)

MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)


@dataclass
class FaceResult:
    box: tuple          # (x1, y1, x2, y2) in pixels
    hostility: float    # 0..1
    sharpness: float    # Laplacian variance of the face crop; higher = sharper

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


def sharpness(frame, box):
    x1, y1, x2, y2 = box
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return 0.0
    return float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())


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

    def analyze(self, frame):
        """Return the most hostile usable FaceResult in a BGR frame, or None."""
        h, w = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = self._landmarker.detect(
            self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb))
        )

        best = None
        for landmarks, shapes in zip(result.face_landmarks, result.face_blendshapes):
            xs = [p.x for p in landmarks]
            ys = [p.y for p in landmarks]
            # A face running off the frame edge would show up cut off on the panel.
            if min(xs) < 0 or min(ys) < 0 or max(xs) > 1 or max(ys) > 1:
                continue
            box = (
                max(0, int(min(xs) * w)), max(0, int(min(ys) * h)),
                min(w, int(max(xs) * w)), min(h, int(max(ys) * h)),
            )
            if box[2] - box[0] < FACE_MIN_WIDTH_PX:
                continue
            blend = {c.category_name: c.score for c in shapes}
            face = FaceResult(box, hostility_score(blend), sharpness(frame, box))
            if face.sharpness < FACE_MIN_SHARPNESS:
                continue
            if best is None or face.hostility > best.hostility:
                best = face
        return best

    def close(self):
        self._landmarker.close()
