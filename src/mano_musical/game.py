"""Modo juego: notas que caen, juicio por ventanas de tiempo y puntaje.

Reutiliza la ``Song`` de ``music.py``. La detección real (manos) o el teclado
emiten notas; ``register_input`` las compara con las notas objetivo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from . import config, music

log = logging.getLogger("mano_musical.game")

JUDGEMENTS = {
    "perfect": (config.HIT_WINDOW_PERFECT, config.SCORE_PERFECT),
    "good": (config.HIT_WINDOW_GOOD, config.SCORE_GOOD),
    "ok": (config.HIT_WINDOW_OK, config.SCORE_OK),
    "miss": (float("inf"), config.SCORE_MISS),
}


@dataclass
class Target:
    """Nota objetivo de la canción."""

    time: float
    note: str
    beats: float
    seconds: float = 0.0
    hit: bool = False
    judged: bool = False
    judgement: str = ""


@dataclass
class GameResult:
    """Resultado de un input o juicio."""

    note: str
    judgement: str
    points: int
    combo: int
    delta: float


@dataclass
class GameState:
    score: int = 0
    combo: int = 0
    max_combo: int = 0
    hits: int = 0
    misses: int = 0
    counts: dict = field(default_factory=lambda: {k: 0 for k in JUDGEMENTS})


class RhythmGame:
    """Juego de ritmo estilo piano tiles sobre cualquier ``Song``."""

    def __init__(self, song: Optional[music.Song] = None) -> None:
        self.song = song or music.jingle_bells()
        self._targets: list[Target] = []
        self.start_time: Optional[float] = None
        self.state = GameState()
        self.build()

    def build(self) -> None:
        self._targets = []
        for start, dur, note in self.song.timeline():
            if note:
                self._targets.append(
                    Target(time=start, note=note, beats=dur / self.song.beat_duration, seconds=dur)
                )
        self._targets.sort(key=lambda t: t.time)

    @property
    def targets(self) -> list[Target]:
        return self._targets

    def reset(self) -> None:
        for target in self._targets:
            target.hit = False
            target.judged = False
            target.judgement = ""
        self.state = GameState()
        self.start_time = None

    def start(self, now: float) -> None:
        if self.start_time is None:
            self.start_time = now + config.COUNTDOWN_SECONDS

    def elapsed(self, now: float) -> float:
        if self.start_time is None:
            return -config.COUNTDOWN_SECONDS
        return now - self.start_time

    def countdown(self, now: float) -> float:
        if self.start_time is None:
            return config.COUNTDOWN_SECONDS
        return max(0.0, self.start_time - now)

    @property
    def finished(self) -> bool:
        return bool(self._targets) and all(t.judged for t in self._targets)

    def register_input(self, note: str, now: float) -> Optional[GameResult]:
        """Evalúa una nota tocada por el usuario contra los objetivos."""
        if self.start_time is None:
            return None
        t = self.elapsed(now)
        best: Optional[Target] = None
        best_delta = float("inf")
        for target in self._targets:
            if target.judged or target.note != note:
                continue
            delta = abs(target.time - t)
            if delta < best_delta and delta <= config.HIT_WINDOW_OK:
                best = target
                best_delta = delta
        if best is None:
            return None
        judgement = "miss"
        points = 0
        for name, (window, value) in JUDGEMENTS.items():
            if best_delta <= window:
                judgement = name
                points = value
                break
        return self._apply(best, judgement, points, best.time - t)

    def _apply(self, target: Target, judgement: str, points: int, delta: float) -> GameResult:
        target.judged = True
        target.judgement = judgement
        target.hit = judgement != "miss"
        st = self.state
        st.counts[judgement] = st.counts.get(judgement, 0) + 1
        if judgement == "miss":
            st.misses += 1
            st.combo = 0
        else:
            st.hits += 1
            st.combo += 1
            st.max_combo = max(st.max_combo, st.combo)
            st.score += points + (st.combo - 1) * 2
        return GameResult(target.note, judgement, points, st.combo, delta)

    def update(self, now: float) -> list[GameResult]:
        """Marca como falladas las notas objetivo ya vencidas."""
        results = []
        if self.start_time is None:
            return results
        t = self.elapsed(now)
        for target in self._targets:
            if not target.judged and t > target.time + config.HIT_WINDOW_OK:
                results.append(self._apply(target, "miss", 0, target.time - t))
        return results

    def accuracy(self) -> float:
        total = sum(self.state.counts.values())
        if total == 0:
            return 0.0
        weighted = (
            self.state.counts["perfect"] + 0.7 * self.state.counts["good"] + 0.4 * self.state.counts["ok"]
        )
        return 100.0 * weighted / total

    def upcoming(self, now: float, horizon: float = config.GAME_FALL_HORIZON) -> list[tuple[Target, float]]:
        """Objetivos visibles para el render: ``(target, delta_s)``."""
        if self.start_time is None:
            return []
        t = self.elapsed(now)
        out = []
        for target in self._targets:
            if target.judged:
                continue
            delta = target.time - t
            if -config.HIT_WINDOW_OK <= delta <= horizon:
                out.append((target, delta))
        return out


class SongPlayer:
    """Reproductor automático de una canción (modo demo / acompañamiento)."""

    def __init__(self, song: Optional[music.Song] = None, loop: bool = True) -> None:
        self.song = song or music.jingle_bells()
        self.loop = loop
        self._index = 0
        self.start_time: Optional[float] = None

    def start(self, now: float) -> None:
        self.start_time = now
        self._index = 0

    def stop(self) -> None:
        self.start_time = None
        self._index = 0

    @property
    def playing(self) -> bool:
        return self.start_time is not None

    def update(self, now: float) -> list[tuple[str, float]]:
        """Devuelve ``(nota, duración_s)`` de las notas que deben sonar ahora."""
        if self.start_time is None:
            return []
        elapsed = now - self.start_time
        timeline = self.song.timeline()
        total = self.song.total_seconds()
        if self.loop and total > 0 and elapsed >= total:
            self.start_time = now
            elapsed = 0.0
            self._index = 0
        due = []
        while self._index < len(timeline):
            start, dur, note = timeline[self._index]
            if start > elapsed:
                break
            if note:
                due.append((note, dur))
            self._index += 1
        return due


# Alias histórico: el juego funciona con cualquier canción, no solo Jingle Bells.
JingleBellsGame = RhythmGame
