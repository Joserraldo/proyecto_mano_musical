"""Hilos de captura de cámara e inferencia de manos.

- ``CameraThread``: lee frames de OpenCV, aplica espejo y publica el último en
  el estado compartido (descarta frames viejos para no acumular latencia).
- ``InferenceThread``: toma el último frame nuevo, corre MediaPipe + el
  detector de pulsaciones y publica ``HandFrame`` y eventos de nota.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import numpy as np

from . import config
from .gesture import FingerPressDetector
from .hand_tracker import HandTracker
from .state import SharedState

log = logging.getLogger("mano_musical.capture")

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]


class CameraThread(threading.Thread):
    """Hilo productor de frames."""

    def __init__(
        self,
        state: SharedState,
        index: int = config.CAMERA_INDEX,
        width: int = config.CAMERA_WIDTH,
        height: int = config.CAMERA_HEIGHT,
        mirror: bool = config.MIRROR,
        fps: int = 30,
    ) -> None:
        super().__init__(name="CameraThread", daemon=True)
        self.state = state
        self.index = index
        self.width = width
        self.height = height
        self.mirror = mirror
        self.interval = 1.0 / max(1, fps)
        self._cap = None

    def _open(self) -> bool:
        if cv2 is None:
            return False
        backends = []
        if hasattr(cv2, "CAP_DSHOW"):
            backends.append(cv2.CAP_DSHOW)
        backends.append(cv2.CAP_ANY)
        for backend in backends:
            cap = cv2.VideoCapture(self.index, backend)
            if not cap.isOpened():
                cap.release()
                continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            cap.set(cv2.CAP_PROP_FPS, 30)
            self._cap = cap
            return True
        return False

    def run(self) -> None:
        self.state.camera_available = self._open()
        if not self.state.camera_available:
            log.warning("Cámara %s no disponible. Modo teclado/demo activo.", self.index)
            return
        log.info("Cámara %s abierta.", self.index)
        while self.state.running.is_set():
            ok, frame = self._cap.read()
            now = time.perf_counter()
            if not ok or frame is None:
                time.sleep(self.interval)
                continue
            if self.mirror:
                frame = cv2.flip(frame, 1)
            self.state.set_frame(np.ascontiguousarray(frame), now)
            time.sleep(self.interval)
        if self._cap is not None:
            self._cap.release()

    def stop(self) -> None:
        self.state.running.clear()


class InferenceThread(threading.Thread):
    """Hilo consumidor: MediaPipe + detección de pulsaciones."""

    def __init__(
        self,
        state: SharedState,
        tracker: HandTracker,
        detector: FingerPressDetector,
    ) -> None:
        super().__init__(name="InferenceThread", daemon=True)
        self.state = state
        self.tracker = tracker
        self.detector = detector
        self._last_frame_id = -1
        self._t0 = time.perf_counter()

    def run(self) -> None:
        while self.state.running.is_set():
            frame, frame_id, ts = self.state.get_frame()
            if frame is None or frame_id == self._last_frame_id:
                time.sleep(0.002)
                continue
            self._last_frame_id = frame_id
            start = time.perf_counter()
            timestamp_ms = int((ts - self._t0) * 1000.0)
            hand_frame = self.tracker.process(frame, timestamp_ms)
            self.state.set_hand_frame(hand_frame)
            triggers = self.detector.update(hand_frame, time.perf_counter())
            for trigger in triggers:
                self.state.push_event(trigger)
                self.state.stats.events_total += 1
            self.state.stats.infer_ms = (time.perf_counter() - start) * 1000.0
            self.state.stats.hands = len(hand_frame.hands)

    def stop(self) -> None:
        pass
