from src.hostility import hostility_score


def test_neutral_face_scores_zero():
    assert hostility_score({}) == 0.0


def test_scowl_scores_high():
    scowl = {
        "browDownLeft": 0.8, "browDownRight": 0.8,
        "mouthFrownLeft": 0.6, "mouthFrownRight": 0.6,
        "eyeSquintLeft": 0.5, "eyeSquintRight": 0.5,
    }
    assert hostility_score(scowl) > 0.6


def test_smile_cancels_hostility():
    scowl = {"browDownLeft": 0.8, "browDownRight": 0.8}
    smiling = {**scowl, "mouthSmileLeft": 1.0, "mouthSmileRight": 1.0}
    assert hostility_score(smiling) == 0.0 < hostility_score(scowl)


def test_score_is_clamped_to_unit_range():
    everything = {k: 1.0 for k in (
        "browDownLeft", "browDownRight", "mouthFrownLeft", "mouthFrownRight",
        "eyeSquintLeft", "eyeSquintRight", "mouthPressLeft", "mouthPressRight",
        "noseSneerLeft", "noseSneerRight",
    )}
    assert hostility_score(everything, gain=10) == 1.0
