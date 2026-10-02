"""Tests de teoría musical, síntesis y serialización de canciones."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from mano_musical import config, music


def test_note_to_freq_reference_pitches():
    assert music.note_to_freq("A4") == pytest.approx(440.0)
    assert music.note_to_freq("C4") == pytest.approx(261.6256, rel=1e-3)
    assert music.note_to_freq("C5") == pytest.approx(523.2511, rel=1e-3)


def test_note_to_midi_roundtrip():
    for note in config.SCALE:
        assert music.midi_to_name(music.note_to_midi(note)) == note


def test_transpose_note():
    assert music.transpose_note("C4", 0) == "C4"
    assert music.transpose_note("C4", 12) == "C5"
    assert music.transpose_note("C4", -12) == "C3"
    assert music.transpose_note("B4", 1) == "C5"


def test_is_valid_note():
    assert music.is_valid_note("G4")
    assert not music.is_valid_note("H4")
    assert not music.is_valid_note("")


def test_synthesize_note_shape_and_range():
    audio = music.synthesize_note(music.note_to_freq("E4"), duration=0.2)
    assert audio.dtype == np.int16
    assert audio.ndim == 2 and audio.shape[1] == 2
    assert audio.shape[0] == int(0.2 * config.SAMPLE_RATE)
    assert int(np.max(np.abs(audio))) <= 32767
    assert not np.all(audio == 0)


def test_synthesize_all_scale_notes():
    for note in config.SCALE:
        audio = music.synthesize_note_timbre(note, timbre="piano", duration=0.1)
        assert audio.shape[1] == 2


def test_jingle_bells_uses_scale_and_range():
    song = music.jingle_bells()
    assert song.total_beats() > 0
    assert song.total_seconds() == pytest.approx(song.total_beats() * 0.5)
    for note in song.used_notes():
        assert note in config.SCALE, f"{note} fuera de la escala de 10 notas"


def test_song_timeline_is_monotonic():
    song = music.jingle_bells()
    last = -1.0
    for start, dur, note in song.timeline():
        assert start >= last
        assert dur > 0
        last = start


def test_save_and_load_song(tmp_path: Path):
    song = music.jingle_bells()
    path = tmp_path / "song.json"
    music.save_song(song, path)
    loaded = music.load_song(path)
    assert loaded.name == song.name
    assert len(loaded.events) == len(song.events)
    assert loaded.events[0].note == song.events[0].note


def test_embedded_song_json_matches_module():
    path = config.SONGS_DIR / "jingle_bells.json"
    if not path.exists():  # pragma: no cover
        pytest.skip("assets no disponibles")
    from_asset = music.load_song(path)
    from_module = music.jingle_bells()
    assert from_asset.total_beats() == pytest.approx(from_module.total_beats())
    assert [e.note for e in from_asset.events] == [e.note for e in from_module.events]


def test_synthesize_rejects_bad_freq():
    with pytest.raises(ValueError):
        music.synthesize_note(0.0, duration=0.05)
