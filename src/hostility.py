"""Turn MediaPipe face blendshapes into a 0-1 "hostility" score.

Pure functions, no model dependency, so the weights are easy to tune and test.
"""
from config.settings import HOSTILITY_GAIN

# Blendshape name stems (MediaPipe reports a Left/Right pair for each) and how
# much each one contributes to looking cross.
WEIGHTS = {
    "browDown": 0.35,     # the furrowed brow
    "mouthFrown": 0.25,
    "eyeSquint": 0.15,
    "mouthPress": 0.15,   # tight lips
    "noseSneer": 0.10,
}
# A smile cancels hostility: score is scaled by (1 - smile).
SMILE_STEM = "mouthSmile"


def _pair_mean(blendshapes, stem):
    return (blendshapes.get(stem + "Left", 0.0) + blendshapes.get(stem + "Right", 0.0)) / 2


def hostility_score(blendshapes, gain=HOSTILITY_GAIN):
    """blendshapes: {name: 0..1}. Returns a float in [0, 1]."""
    raw = sum(w * _pair_mean(blendshapes, stem) for stem, w in WEIGHTS.items())
    raw *= 1.0 - _pair_mean(blendshapes, SMILE_STEM)
    return max(0.0, min(1.0, raw * gain))
