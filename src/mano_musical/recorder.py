"""Grabación y reproducción de performances (air-piano).

Guarda en JSON los eventos de nota con su tiempo relativo y permite
reproducirlos sobre el motor de audio para revisar o compartir la ejecución.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import config

log = logging.getLogger("mano_musical.recorder")


@dataclass
class RecordedEvent:
    time: float
    note: str
    velocity: float
    kind: str


@dataclass
class Performance:
    events: list[RecordedEvent] = field(default_factory=list)
    duration: float = 0.0
    name: str = "performance"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "duration": self.duration,
            "events": [vars(e) for e in self.events],
        }


class PerformanceRecorder:
    """Captura eventos mientras el usuario toca."""

    def __init__(self) -> None:
        self._events: list[RecordedEvent] = []
        self._t0: Optional[float] = None
        self.recording = False

    def start(self, now: Optional[float] = None) -> None:
        self._events = []
        self._t0 = now if now is not None else time.perf_counter()
        self.recording = True

    def record(self, note: str, velocity: float, kind: str, now: float) -> None:
        if not self.recording or self._t0 is None:
            return
        self._events.append(RecordedEvent(now - self._t0, note, float(velocity), kind))

    def stop(self, name: str = "performance") -> Performance:
        self.recording = False
        duration = 0.0
        if self._events:
            duration = max(e.time for e in self._events)
        perf = Performance(events=list(self._events), duration=duration, name=name)
        return perf

    def result_path(self, name: str = "performance") -> Path:
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        return config.OUTPUT_DIR / f"{name}-{stamp}.json"


def save_performance(perf: Performance, path: Optional[Path] = None) -> Path:
    path = path or PerformanceRecorder().result_path(perf.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(perf.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
    log.info("Performance guardada en %s", path)
    return path


def load_performance(path: str | Path) -> Performance:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    events = [
        RecordedEvent(float(e["time"]), str(e["note"]), float(e["velocity"]), str(e["kind"]))
        for e in data.get("events", [])
    ]
    return Performance(events, float(data.get("duration", 0.0)), data.get("name", "performance"))


class PerformancePlayer:
    """Reproduce una ``Performance`` en sincronía con ``update``."""

    def __init__(self, perf: Performance, loop: bool = False) -> None:
        self.perf = perf
        self.loop = loop
        self.start_time: Optional[float] = None
        self._index = 0

    def start(self, now: float) -> None:
        self.start_time = now
        self._index = 0

    def stop(self) -> None:
        self.start_time = None
        self._index = 0

    @property
    def playing(self) -> bool:
        return self.start_time is not None

    def update(self, now: float) -> list[RecordedEvent]:
        if self.start_time is None:
            return []
        elapsed = now - self.start_time
        if self.loop and self.perf.duration and elapsed >= self.perf.duration:
            self.start_time = now
            elapsed = 0.0
            self._index = 0
        due = []
        while self._index < len(self.perf.events):
            event = self.perf.events[self._index]
            if event.time > elapsed:
                break
            due.append(event)
            self._index += 1
        return due
