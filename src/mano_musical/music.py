"""Teoría musical mínima, síntesis de audio y definición de canciones.

No depende de pygame: entrega arreglos NumPy int16 estéreo listos para
convertirse en ``pygame.mixer.Sound``. Esto mantiene el motor de síntesis
testeable sin dispositivo de audio.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np

from . import config

A4_FREQ = 440.0
A4_MIDI = 69

_SEMITONES = {
    "C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "F": 5, "F#": 6, "Gb": 6, "G": 7, "G#": 8,
    "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11,
}


def note_to_midi(note: str) -> int:
    """Convierte ``"C4"``/``"A#3"`` a número MIDI (C4 = 60)."""
    token = note.strip()
    if not token:
        raise ValueError("nota vacía")
    name, octave = token[:-1], token[-1]
    if name not in _SEMITONES:
        raise ValueError(f"nota inválida: {note!r}")
    return (int(octave) + 1) * 12 + _SEMITONES[name]


_SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def midi_to_name(midi: int) -> str:
    """Convierte un número MIDI a nombre con sostenidos (``60 -> C4``)."""
    return f"{_SHARP_NAMES[int(midi) % 12]}{int(midi) // 12 - 1}"


def transpose_note(note: str, semitones: int) -> str:
    """Transpone una nota ``n`` semitonos (positivo = agudo)."""
    if semitones == 0:
        return note
    return midi_to_name(note_to_midi(note) + semitones)


def midi_to_freq(midi: float) -> float:
    """Frecuencia (Hz) de un número MIDI, temperamento igual."""
    return A4_FREQ * (2.0 ** ((midi - A4_MIDI) / 12.0))


def note_to_freq(note: str) -> float:
    """Frecuencia (Hz) de una nota como ``"C4"``."""
    return midi_to_freq(note_to_midi(note))


def is_valid_note(note: str) -> bool:
    try:
        note_to_midi(note)
        return True
    except ValueError:
        return False


def _adsr_envelope(n: int, sample_rate: int, attack: float, decay: float) -> np.ndarray:
    """Envolvente ataque + caída exponencial (sin clicks al inicio)."""
    t = np.arange(n, dtype=np.float64) / sample_rate
    attack_n = max(1, int(attack * sample_rate))
    env = np.exp(-decay * t)
    ramp = np.linspace(0.0, 1.0, attack_n, dtype=np.float64)
    env[:attack_n] *= ramp
    return env


def synthesize_note(
    freq: float,
    duration: float = config.NOTE_DURATION,
    sample_rate: int = config.SAMPLE_RATE,
    volume: float = 0.8,
    harmonics: Sequence[float] = (1.0, 0.5, 0.28, 0.14, 0.07),
    decay: float = 3.0,
    attack: float = 0.008,
    detune: float = 0.0025,
    vibrato_hz: float = 5.2,
    vibrato_cents: float = 5.0,
) -> np.ndarray:
    """Sintetiza una nota con armónicos, vibrato y envolvente.

    Devuelve un arreglo ``(n, 2)`` ``int16`` estéreo listo para el mixer.
    """
    if freq <= 0:
        raise ValueError("freq debe ser > 0")
    n = max(1, int(duration * sample_rate))
    t = np.arange(n, dtype=np.float64) / sample_rate

    vibrato = (vibrato_cents / 1200.0) * np.sin(2 * np.pi * vibrato_hz * t)
    wave = np.zeros(n, dtype=np.float64)
    for i, amp in enumerate(harmonics, start=1):
        partial_freq = freq * i * (1.0 + detune * (i - 1))
        phase = 2 * np.pi * partial_freq * t * (1.0 + vibrato)
        wave += amp * np.sin(phase)

    wave *= _adsr_envelope(n, sample_rate, attack, decay)
    peak = float(np.max(np.abs(wave))) or 1.0
    wave = (wave / peak) * float(np.clip(volume, 0.0, 1.0))
    data = np.clip(wave * 32767.0, -32768, 32767).astype(np.int16)
    return np.ascontiguousarray(np.column_stack((data, data)))


Timbres = {
    "piano": {"harmonics": (1.0, 0.5, 0.28, 0.14, 0.07), "decay": 3.0, "vibrato_cents": 5.0},
    "organ": {"harmonics": (1.0, 0.7, 0.5, 0.35, 0.25), "decay": 0.6, "vibrato_cents": 3.0},
    "chiptune": {"harmonics": (1.0, 0.0, 0.33, 0.0, 0.2), "decay": 1.4, "vibrato_cents": 0.0},
    "synth": {"harmonics": (1.0, 0.6, 0.4, 0.25, 0.15), "decay": 1.2, "vibrato_cents": 9.0},
}


def synthesize_note_timbre(
    note: str,
    timbre: str = "piano",
    duration: float = config.NOTE_DURATION,
    sample_rate: int = config.SAMPLE_RATE,
) -> np.ndarray:
    """Sintetiza una nota aplicando un timbre predefinido."""
    params = Timbres.get(timbre, Timbres["piano"])
    return synthesize_note(
        note_to_freq(note), duration=duration, sample_rate=sample_rate, **params
    )


@dataclass(frozen=True)
class NoteEvent:
    """Nota con duración relativa en beats (``None`` = silencio)."""

    note: str | None
    beats: float


@dataclass
class Song:
    """Canción: secuencia de notas y metadatos."""

    name: str
    bpm: int
    events: list[NoteEvent] = field(default_factory=list)

    @property
    def beat_duration(self) -> float:
        return 60.0 / float(self.bpm)

    def total_beats(self) -> float:
        return float(sum(e.beats for e in self.events))

    def total_seconds(self) -> float:
        return self.total_beats() * self.beat_duration

    def timeline(self) -> list[tuple[float, float, str | None]]:
        """Lista de ``(inicio_s, duración_s, nota)`` acumulando tiempos."""
        out: list[tuple[float, float, str | None]] = []
        t = 0.0
        for event in self.events:
            dur = event.beats * self.beat_duration
            out.append((t, dur, event.note))
            t += dur
        return out

    def used_notes(self) -> list[str]:
        seen: list[str] = []
        for event in self.events:
            if event.note and event.note not in seen:
                seen.append(event.note)
        return seen


def _events(pairs: Iterable[tuple[str | None, float]]) -> list[NoteEvent]:
    return [NoteEvent(note, beats) for note, beats in pairs]


# Jingle Bells en Do mayor. Silencio = None. beats: 1 = negra.
# Frase 1:  E E E | E E E | E G C D | E
# Frase 2:  F F F F | F E E | E E D D | E D G
# (se repite y cierra en C)
JINGLE_BELLS_EVENTS: list[tuple[str | None, float]] = [
    ("E4", 1), ("E4", 1), ("E4", 2),
    ("E4", 1), ("E4", 1), ("E4", 2),
    ("E4", 1), ("G4", 1), ("C5", 1), ("D5", 1),
    ("E5", 4),
    ("F4", 1), ("F4", 1), ("F4", 1), ("F4", 1),
    ("F4", 1), ("E4", 1), ("E4", 2),
    ("E4", 1), ("E4", 1), ("D4", 1), ("D4", 1),
    ("E4", 1), ("D4", 1), ("G4", 2),
    ("E4", 1), ("E4", 1), ("E4", 2),
    ("E4", 1), ("E4", 1), ("E4", 2),
    ("E4", 1), ("G4", 1), ("C5", 1), ("D5", 1),
    ("E5", 4),
    ("F4", 1), ("F4", 1), ("F4", 1), ("F4", 1),
    ("F4", 1), ("E4", 1), ("E4", 2),
    ("E4", 1), ("E4", 1), ("D4", 1), ("D4", 1),
    ("E4", 1), ("D4", 1), ("C4", 4),
]


def jingle_bells() -> Song:
    """Canción Jingle Bells embebida (sin dependencias externas)."""
    return Song("Jingle Bells", bpm=config.TEMPO_BPM, events=_events(JINGLE_BELLS_EVENTS))


# Estrellita (Twinkle Twinkle) en Do mayor: rango C4-A4, tempo lento. Ideal fácil.
ESTRELLITA_EVENTS: list[tuple[str | None, float]] = [
    ("C4", 1), ("C4", 1), ("G4", 1), ("G4", 1), ("A4", 1), ("A4", 1), ("G4", 2),
    ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1), ("D4", 1), ("D4", 1), ("C4", 2),
    ("G4", 1), ("G4", 1), ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1), ("D4", 2),
    ("G4", 1), ("G4", 1), ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1), ("D4", 2),
    ("C4", 1), ("C4", 1), ("G4", 1), ("G4", 1), ("A4", 1), ("A4", 1), ("G4", 2),
    ("F4", 1), ("F4", 1), ("E4", 1), ("E4", 1), ("D4", 1), ("D4", 1), ("C4", 2),
]


def estrellita() -> Song:
    return Song("Estrellita", bpm=78, events=_events(ESTRELLITA_EVENTS))


# Campana sobre campana: solo C4 D4 E4 G4, muy fácil y lenta.
CAMPANA_EVENTS: list[tuple[str | None, float]] = [
    ("E4", 1), ("C4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("E4", 1), ("E4", 2),
    ("D4", 1), ("D4", 1), ("D4", 2), ("E4", 1), ("G4", 1), ("G4", 2),
    ("E4", 1), ("C4", 1), ("C4", 1), ("D4", 1), ("E4", 1), ("E4", 1), ("E4", 1), ("E4", 1),
    ("D4", 1), ("D4", 1), ("E4", 1), ("C4", 1), ("G4", 1), ("G4", 1), ("C4", 2),
]


def campana() -> Song:
    return Song("Campana sobre Campana", bpm=84, events=_events(CAMPANA_EVENTS))


# Cumpleaños Feliz en Do mayor. Se repite una vez para que dure un poco más.
CUMPLEANOS_PHRASE: list[tuple[str | None, float]] = [
    ("G4", 0.5), ("G4", 0.5), ("A4", 1), ("G4", 1), ("C5", 1.5), ("B4", 0.5),
    ("G4", 0.5), ("G4", 0.5), ("A4", 1), ("G4", 1), ("D5", 1.5), ("C5", 0.5),
    ("G4", 0.5), ("G4", 0.5), ("E5", 1), ("C5", 1), ("B4", 1), ("A4", 1),
    ("F4", 0.5), ("F4", 0.5), ("E4", 1), ("D4", 1), ("C4", 2),
]


def cumpleanos() -> Song:
    return Song("Cumpleaños Feliz", bpm=92, events=_events(CUMPLEANOS_PHRASE * 2))


def scale_tempo(song: Song, factor: float) -> Song:
    """Copia de la canción con el BPM multiplicado (más rápido = más difícil)."""
    return replace(song, bpm=max(40, int(round(song.bpm * factor))))


# Orden = teclas 1..4 del modo juego.
SONGS = (jingle_bells, estrellita, campana, cumpleanos)


def load_song(path: str | Path) -> Song:
    """Carga una canción desde JSON ``{name, bpm, events:[{note,beats}]}``."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    events = [NoteEvent(e.get("note"), float(e["beats"])) for e in data["events"]]
    return Song(str(data.get("name", "Song")), int(data.get("bpm", 120)), events)


def save_song(song: Song, path: str | Path) -> None:
    """Guarda una canción a JSON."""
    payload = {
        "name": song.name,
        "bpm": song.bpm,
        "events": [{"note": e.note, "beats": e.beats} for e in song.events],
    }
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
