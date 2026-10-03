"""Detección de pulsaciones de dedo ("air-piano").

Convierte landmarks de MediaPipe en eventos nota ON/OFF aplicando histéresis
sobre el ángulo de flexión de cada dedo, con suavizado temporal y estimación
de velocidad para dar dinámica (volumen). Modos: ``curl`` (doblar el dedo,
por defecto) y ``drop`` (bajar el dedo respecto a una línea base calibrada).
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np

from . import config
from .hand_tracker import HandFrame
from .utils import clamp

log = logging.getLogger("mano_musical.gesture")


def _angle_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> float:
    """Ángulo en ``b`` formado por los puntos ``a-b-c`` (grados)."""
    v1 = a - b
    v2 = c - b
    n1 = float(np.linalg.norm(v1))
    n2 = float(np.linalg.norm(v2))
    if n1 < 1e-6 or n2 < 1e-6:
        return 180.0
    cos = float(np.dot(v1, v2) / (n1 * n2))
    return math.degrees(math.acos(clamp(cos, -1.0, 1.0)))


def finger_curl_angle(landmarks: np.ndarray, finger: str) -> float:
    """Ángulo de flexión representativo del dedo (grados, 180 = extendido)."""
    joints = config.FINGER_JOINTS[finger]
    mcp_idx, pip_idx, tip_idx = joints[0], joints[1], joints[3]
    pip_angle = _angle_deg(
        landmarks[mcp_idx, :2], landmarks[pip_idx, :2], landmarks[tip_idx, :2]
    )
    if finger == "thumb":
        ip_angle = _angle_deg(
            landmarks[joints[1], :2], landmarks[joints[2], :2], landmarks[tip_idx, :2]
        )
        return min(pip_angle, ip_angle)
    return pip_angle


def fingertip(landmarks: np.ndarray, finger: str) -> np.ndarray:
    return landmarks[config.FINGER_JOINTS[finger][-1], :2]


@dataclass
class NoteTrigger:
    """Evento de nota emitido por el detector."""

    note: str
    hand: str
    finger: str
    kind: str  # "on" | "off"
    velocity: float
    timestamp: float


@dataclass
class FingerState:
    """Estado interno de un dedo entre frames."""

    pressed: bool = False
    angle_ema: Optional[float] = None
    baseline_y: Optional[float] = None
    last_change: float = -1e9
    last_angle: float = 0.0
    last_time: float = 0.0
    ext_ref: float = 0.0
    calibrated: bool = False


class FingerPressDetector:
    """Detector con histéresis de pulsaciones por (mano, dedo)."""

    def __init__(
        self,
        mode: str = "curl",
        press_enter: float = config.PRESS_ANGLE_ENTER,
        press_release: float = config.PRESS_ANGLE_RELEASE,
        smoothing: float = config.LANDMARK_SMOOTHING,
        drop_delta: float = 0.35,
        debounce: float = 0.05,
        swap_hands: bool = False,
    ) -> None:
        self.mode = mode
        self.press_enter = press_enter
        self.press_release = press_release
        self.smoothing = smoothing
        self.drop_delta = drop_delta
        self.debounce = debounce
        self.swap_hands = swap_hands
        self._states: dict[tuple[str, str], FingerState] = {}
        self._last_angles: dict[tuple[str, str], float] = {}
        self.last_readings: dict[str, dict] = {}
        self.calibrating = False
        self.calib_until = 0.0

    # ------------------------------------------------------------ calibración
    def begin_calibration(self, now: float, seconds: float = config.CALIBRATION_SECONDS) -> None:
        """Inicia una ventana en la que se mide el ángulo extendido real."""
        for state in self._states.values():
            state.ext_ref = 0.0
            state.calibrated = False
        self.calibrating = True
        self.calib_until = now + seconds

    def calibration_remaining(self, now: float) -> float:
        return max(0.0, self.calib_until - now) if self.calibrating else 0.0

    def _finish_calibration(self) -> None:
        self.calibrating = False
        for state in self._states.values():
            if state.ext_ref >= config.CALIB_MIN_EXTENDED:
                state.calibrated = True

    def _thresholds(self, state: FingerState) -> tuple[float, float]:
        if self.mode == "curl" and state.calibrated:
            enter = max(60.0, state.ext_ref - config.CALIB_MARGIN_ENTER)
            release = max(enter + 10.0, state.ext_ref - config.CALIB_MARGIN_RELEASE)
            return enter, release
        return self.press_enter, self.press_release

    def nudge_sensitivity(self, delta: float) -> None:
        """Ajusta cuán fácil es disparar una nota (sube = más sensible)."""
        self.press_enter = clamp(self.press_enter + delta, config.SENSITIVITY_MIN, config.SENSITIVITY_MAX)
        self.press_release = clamp(self.press_release + delta, self.press_enter + 5.0, 179.0)

    # ------------------------------------------------------------------ utils
    def _note_for(self, hand: str, finger: str) -> Optional[str]:
        label = hand
        if self.swap_hands:
            label = "Left" if hand == "Right" else "Right"
        return config.NOTE_MAP.get((label, finger))

    def _smooth_landmarks(self, hand, key: str) -> np.ndarray:
        lm = hand.landmarks
        prev = getattr(self, "_lm_ema", {}).get(key)
        if prev is None or self.smoothing <= 0:
            smoothed = lm
        else:
            alpha = self.smoothing
            smoothed = alpha * prev + (1.0 - alpha) * lm
        if not hasattr(self, "_lm_ema"):
            self._lm_ema = {}
        self._lm_ema[key] = smoothed
        return smoothed

    def reset(self) -> None:
        self._states.clear()
        self._last_angles.clear()
        self.last_readings.clear()
        self.calibrating = False
        self.calib_until = 0.0
        if hasattr(self, "_lm_ema"):
            self._lm_ema.clear()

    # ------------------------------------------------------------------ update
    def update(self, frame: HandFrame, now: float) -> list[NoteTrigger]:
        """Procesa un ``HandFrame`` y devuelve los eventos de nota detectados."""
        if self.calibrating and now >= self.calib_until:
            self._finish_calibration()
        triggers: list[NoteTrigger] = []
        active: dict[str, dict] = {}
        for hand in frame.hands:
            key = hand.handedness
            landmarks = self._smooth_landmarks(hand, key)
            palm = hand.palm_size() or 1e-6
            for finger in config.FINGER_ORDER:
                note = self._note_for(hand.handedness, finger)
                if note is None:
                    continue
                state = self._states.setdefault((key, finger), FingerState())
                angle = finger_curl_angle(landmarks, finger)
                if state.angle_ema is None:
                    state.angle_ema = angle
                else:
                    state.angle_ema = 0.6 * state.angle_ema + 0.4 * angle
                smooth_angle = state.angle_ema
                if self.calibrating:
                    state.ext_ref = max(state.ext_ref, smooth_angle)
                tip = fingertip(landmarks, finger)
                value = self._press_value(state, smooth_angle, tip, palm)
                enter, release = self._thresholds(state)
                pressed = state.pressed
                if not pressed and value <= enter:
                    pressed = True
                elif pressed and value >= release:
                    pressed = False

                changed = pressed != state.pressed
                velocity = 0.0
                if changed and (now - state.last_change) >= self.debounce:
                    velocity = self._estimate_velocity(state, smooth_angle, now)
                    triggers.append(
                        NoteTrigger(
                            note=note,
                            hand=key,
                            finger=finger,
                            kind="on" if pressed else "off",
                            velocity=velocity if pressed else 0.0,
                            timestamp=now,
                        )
                    )
                    state.pressed = pressed
                    state.last_change = now
                    state.last_angle = smooth_angle
                    state.last_time = now

                if self.mode == "drop" and not pressed and value >= self.press_release:
                    state.baseline_y = self._update_baseline(state.baseline_y, tip[1])

                active[note] = {
                    "pressed": state.pressed,
                    "angle": smooth_angle,
                    "value": value,
                    "hand": key,
                    "finger": finger,
                    "tip": (float(tip[0]), float(tip[1])),
                    "velocity": velocity if changed and pressed else 0.0,
                }
        self.last_readings = active
        return triggers

    # ------------------------------------------------------------------ helpers
    def _press_value(self, state: FingerState, angle: float, tip: np.ndarray, palm: float) -> float:
        """Valor comparable con los umbrales (menor = más presionado)."""
        if self.mode == "drop" and state.baseline_y is not None:
            delta = (tip[1] - state.baseline_y) / palm
            return config.PRESS_ANGLE_ENTER - clamp(delta / self.drop_delta, 0.0, 1.5) * 90.0
        return angle

    def _update_baseline(self, baseline: Optional[float], y: float) -> float:
        if baseline is None:
            return y
        return 0.99 * baseline + 0.01 * y

    def _estimate_velocity(self, state: FingerState, angle: float, now: float) -> float:
        dt = max(now - state.last_time, 1e-3) if state.last_time else 1e-3
        rate = abs(angle - state.last_angle) / dt
        norm = (rate - config.PRESS_VELOCITY_MIN) / (
            config.PRESS_VELOCITY_MAX - config.PRESS_VELOCITY_MIN
        )
        return float(clamp(0.55 + 0.45 * norm, 0.0, 1.0))


class SwipeDetector:
    """Detecta barridos horizontales rápidos para cambiar de octava."""

    def __init__(self, window: float = 0.35, distance: float = 0.22) -> None:
        self.window = window
        self.distance = distance
        self._samples: deque[tuple[float, float]] = deque()

    def update(self, x: float, now: float) -> int:
        """Devuelve -1 (izquierda), +1 (derecha) o 0 (sin gesto)."""
        self._samples.append((now, x))
        while self._samples and now - self._samples[0][0] > self.window:
            self._samples.popleft()
        if len(self._samples) < 2:
            return 0
        dx = self._samples[-1][1] - self._samples[0][1]
        if dx >= self.distance:
            self._samples.clear()
            return 1
        if dx <= -self.distance:
            self._samples.clear()
            return -1
        return 0
