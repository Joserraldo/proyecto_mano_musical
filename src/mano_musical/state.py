"""Estado compartido entre hilos (captura, inferencia y render).

El render ocurre en el hilo principal de pygame; la captura y la inferencia
corren en hilos aparte. Un ``threading.Lock`` protege los últimos datos y una
``queue.Queue`` transporta eventos de nota hacia el hilo principal.
"""

from __future__ import annotations

import queue
import threading
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .hand_tracker import HandFrame


@dataclass
class AppStats:
    """Contadores mostrados en el HUD."""

    fps: float = 0.0
    infer_ms: float = 0.0
    hands: int = 0
    active_notes: int = 0
    events_total: int = 0


@dataclass
class SharedState:
    """Contenedor seguro para hilos."""

    running: threading.Event = field(default_factory=threading.Event)
    frame: Optional[np.ndarray] = None
    frame_id: int = 0
    frame_time: float = 0.0
    hand_frame: HandFrame = field(default_factory=HandFrame)
    events: "queue.Queue" = field(default_factory=queue.Queue)
    stats: AppStats = field(default_factory=AppStats)
    camera_available: bool = False
    tracker_available: bool = False
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set_frame(self, frame: Optional[np.ndarray], ts: float) -> None:
        with self._lock:
            self.frame = frame
            self.frame_id += 1
            self.frame_time = ts

    def get_frame(self) -> tuple[Optional[np.ndarray], int, float]:
        with self._lock:
            return self.frame, self.frame_id, self.frame_time

    def set_hand_frame(self, hand_frame: HandFrame) -> None:
        with self._lock:
            self.hand_frame = hand_frame

    def get_hand_frame(self) -> HandFrame:
        with self._lock:
            return self.hand_frame

    def push_event(self, event) -> None:
        self.events.put(event)

    def drain_events(self, max_items: int = 256) -> list:
        out = []
        for _ in range(max_items):
            try:
                out.append(self.events.get_nowait())
            except queue.Empty:
                break
        return out

    def stop(self) -> None:
        self.running.clear()
