"""Detección de manos con MediaPipe Tasks (``HandLandmarker``).

MediaPipe 1.x ya no expone ``mp.solutions.hands``; usamos la API de tareas en
modo VIDEO dentro de un hilo de inferencia. Si la librería o el modelo no
están disponibles, ``HandTracker.available`` es ``False`` y la app entra en
modo teclado/demo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from . import config
from .utils import ensure_model

log = logging.getLogger("mano_musical.tracker")

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]


@dataclass
class Hand:
    """Una mano detectada: 21 landmarks normalizados + lateralidad."""

    handedness: str
    score: float
    landmarks: np.ndarray  # (21, 3) con x, y normalizados en [0, 1]

    def pixel(self, index: int, width: int, height: int) -> tuple[int, int]:
        x, y = self.landmarks[index, 0], self.landmarks[index, 1]
        return int(x * width), int(y * height)

    def palm_size(self) -> float:
        return float(np.linalg.norm(self.landmarks[0, :2] - self.landmarks[9, :2]))

    def center(self) -> tuple[float, float]:
        return float(np.mean(self.landmarks[:, 0])), float(np.mean(self.landmarks[:, 1]))


@dataclass
class HandFrame:
    """Resultado de un frame: manos detectadas y contexto temporal."""

    hands: list[Hand] = field(default_factory=list)
    timestamp_ms: int = 0
    width: int = 0
    height: int = 0


class HandTracker:
    """Wrapper delgado sobre ``mediapipe.tasks.vision.HandLandmarker``."""

    def __init__(
        self,
        model_path: Path | None = None,
        max_hands: int = 2,
        detection_confidence: float = 0.5,
        presence_confidence: float = 0.5,
        tracking_confidence: float = 0.5,
        swap_handedness: bool = False,
    ) -> None:
        self.available = False
        self.swap_handedness = swap_handedness
        self._landmarker = None
        self._vision = None
        self._mp = None
        self._load(model_path, max_hands, detection_confidence, presence_confidence, tracking_confidence)

    def _load(self, model_path, max_hands, det, pres, track) -> None:
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision as mp_vision

            path = ensure_model(model_path)
            options = mp_vision.HandLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(path)),
                running_mode=mp_vision.RunningMode.VIDEO,
                num_hands=max_hands,
                min_hand_detection_confidence=det,
                min_hand_presence_confidence=pres,
                min_tracking_confidence=track,
            )
            self._mp = mp
            self._vision = mp_vision
            self._landmarker = mp_vision.HandLandmarker.create_from_options(options)
            self.available = True
            log.info("HandTracker listo (máx %d manos)", max_hands)
        except Exception as exc:  # pragma: no cover
            log.warning("HandTracker no disponible (%s). Modo teclado activo.", exc)
            self.available = False

    def process(self, frame_bgr: np.ndarray, timestamp_ms: int) -> HandFrame:
        """Procesa un frame BGR y devuelve las manos detectadas."""
        h, w = frame_bgr.shape[:2]
        out = HandFrame(timestamp_ms=timestamp_ms, width=w, height=h)
        if not self.available or cv2 is None:
            return out
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = self._mp.Image(
            image_format=self._mp.ImageFormat.SRGB, data=np.ascontiguousarray(rgb)
        )
        result = self._landmarker.detect_for_video(mp_image, int(timestamp_ms))
        if not result.hand_landmarks:
            return out
        for i, landmarks in enumerate(result.hand_landmarks):
            points = np.array([[lm.x, lm.y, lm.z] for lm in landmarks], dtype=np.float32)
            label = "Right"
            score = 0.0
            if i < len(result.handedness) and result.handedness[i]:
                category = result.handedness[i][0]
                label = category.category_name or "Right"
                score = float(getattr(category, "score", 0.0))
            if self.swap_handedness:
                label = "Left" if label == "Right" else "Right"
            out.hands.append(Hand(label, score, points))
        return out

    def close(self) -> None:
        if self._landmarker is not None:
            try:
                self._landmarker.close()
            except Exception:  # pragma: no cover
                pass
            self._landmarker = None
