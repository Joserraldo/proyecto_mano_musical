"""Tests del detector de pulsaciones con landmarks sintéticos."""

from __future__ import annotations

import math

import numpy as np

from mano_musical import config
from mano_musical.gesture import FingerPressDetector, SwipeDetector, _angle_deg, finger_curl_angle
from mano_musical.hand_tracker import Hand, HandFrame


def _base_landmarks() -> np.ndarray:
    """Mano extendida apuntando hacia arriba; dedos verticales."""
    lm = np.zeros((21, 3), dtype=np.float32)
    lm[0] = (0.5, 0.95, 0.0)  # wrist
    lm[9] = (0.5, 0.62, 0.0)  # middle MCP
    column = {
        "thumb": 0.35, "index": 0.44, "middle": 0.5, "ring": 0.56, "pinky": 0.62,
    }
    ys = [0.60, 0.50, 0.40, 0.30]
    for finger, x in column.items():
        for joint, y in zip(config.FINGER_JOINTS[finger], ys):
            lm[joint] = (x, y, 0.0)
    return lm


def _hand(landmarks: np.ndarray, side: str = "Right") -> Hand:
    return Hand(side, 0.9, landmarks)


def _bend(landmarks: np.ndarray, finger: str) -> np.ndarray:
    lm = landmarks.copy()
    joints = config.FINGER_JOINTS[finger]
    mcp = lm[joints[0]][:2]
    tip = mcp + np.array([0.0, 0.02])
    lm[joints[3]] = (tip[0], tip[1], 0.0)
    return lm


def test_angle_deg_right_angle():
    a = np.array([1.0, 0.0])
    b = np.array([0.0, 0.0])
    c = np.array([0.0, 1.0])
    assert _angle_deg(a, b, c) == math.degrees(math.pi / 2)


def test_finger_curl_extended_vs_bent():
    lm = _base_landmarks()
    extended = finger_curl_angle(lm, "index")
    bent = finger_curl_angle(_bend(lm, "index"), "index")
    assert extended > 150
    assert bent < extended


def test_detector_emits_on_and_off():
    detector = FingerPressDetector(mode="curl", smoothing=0.0)
    lm = _base_landmarks()
    hand = _hand(lm)

    # Frame extendido: sin eventos.
    triggers = detector.update(HandFrame([hand]), now=0.0)
    assert triggers == []

    # Frame con índice doblado: nota B4 -> ON.
    bent_hand = _hand(_bend(lm, "index"))
    triggers = detector.update(HandFrame([bent_hand]), now=0.1)
    on = [t for t in triggers if t.kind == "on"]
    assert len(on) == 1
    assert on[0].note == config.NOTE_MAP[("Right", "index")]
    assert 0.0 < on[0].velocity <= 1.0

    # Vuelve extendido: el suavizado temporal exige algunos frames -> OFF.
    off = []
    for i in range(6):
        triggers = detector.update(HandFrame([hand]), now=0.3 + 0.1 * i)
        off += [t for t in triggers if t.kind == "off"]
    assert len(off) == 1
    assert off[0].note == config.NOTE_MAP[("Right", "index")]


def test_left_hand_maps_low_notes():
    detector = FingerPressDetector(mode="curl", smoothing=0.0)
    lm = _bend(_base_landmarks(), "pinky")
    triggers = detector.update(HandFrame([_hand(lm, "Left")]), now=0.0)
    on = [t for t in triggers if t.kind == "on"]
    assert on and on[0].note == "C4"


def test_swap_hands_redirects_notes():
    detector = FingerPressDetector(mode="curl", smoothing=0.0, swap_hands=True)
    lm = _bend(_base_landmarks(), "pinky")
    triggers = detector.update(HandFrame([_hand(lm, "Left")]), now=0.0)
    on = [t for t in triggers if t.kind == "on"]
    assert on and on[0].note == config.NOTE_MAP[("Right", "pinky")]


def test_debounce_blocks_rapid_toggle():
    detector = FingerPressDetector(mode="curl", smoothing=0.0, debounce=1.0)
    lm = _base_landmarks()
    detector.update(HandFrame([_hand(lm)]), now=0.0)
    first = detector.update(HandFrame([_hand(_bend(lm, "index"))]), now=0.1)
    second = detector.update(HandFrame([_hand(lm)]), now=0.2)
    assert any(t.kind == "on" for t in first)
    assert second == []


def test_debounce_blocked_change_does_not_crash():
    detector = FingerPressDetector(mode="curl", smoothing=0.0, debounce=10.0)
    lm = _base_landmarks()
    detector.update(HandFrame([_hand(lm)]), now=0.0)
    on = detector.update(HandFrame([_hand(_bend(lm, "index"))]), now=0.1)
    assert any(t.kind == "on" for t in on)
    for i in range(1, 8):
        result = detector.update(HandFrame([_hand(lm)]), now=0.1 + 0.05 * i)
        assert result == []


def test_calibration_sets_per_finger_thresholds():
    detector = FingerPressDetector(mode="curl", smoothing=0.0)
    detector.begin_calibration(now=0.0, seconds=0.1)
    lm = _base_landmarks()
    detector.update(HandFrame([_hand(lm)]), now=0.05)
    detector.update(HandFrame([_hand(lm)]), now=0.2)
    assert detector.calibrating is False
    state = detector._states[("Right", "index")]
    assert state.calibrated is True
    assert state.ext_ref > 150.0
    enter, release = detector._thresholds(state)
    assert enter < release


def test_sensitivity_nudge_clamps():
    detector = FingerPressDetector()
    detector.nudge_sensitivity(-1000)
    assert detector.press_enter == config.SENSITIVITY_MIN
    detector.nudge_sensitivity(1000)
    assert detector.press_enter == config.SENSITIVITY_MAX
    assert detector.press_release > detector.press_enter


def test_swipe_detector_direction():
    swipe = SwipeDetector(window=1.0, distance=0.2)
    swipe.update(0.2, now=0.0)
    assert swipe.update(0.45, now=0.1) == 1
    swipe.update(0.8, now=0.0)
    assert swipe.update(0.5, now=0.1) == -1
