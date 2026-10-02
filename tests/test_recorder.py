"""Tests de grabación/reproducción y del motor de audio (sin dispositivo)."""

from __future__ import annotations

from pathlib import Path

from mano_musical.audio_engine import AudioEngine
from mano_musical.recorder import (
    PerformancePlayer,
    PerformanceRecorder,
    load_performance,
    save_performance,
)


def test_recorder_captures_relative_times():
    rec = PerformanceRecorder()
    rec.start(now=100.0)
    rec.record("E4", 1.0, "on", now=100.1)
    rec.record("E4", 0.0, "off", now=100.5)
    perf = rec.stop("demo")
    assert len(perf.events) == 2
    assert perf.events[0].time == pytest_approx(0.1)
    assert perf.events[1].time == pytest_approx(0.5)
    assert perf.duration == pytest_approx(0.5)


def test_recorder_ignores_events_when_stopped():
    rec = PerformanceRecorder()
    rec.record("E4", 1.0, "on", now=0.2)
    assert rec.stop().events == []


def test_save_and_load_roundtrip(tmp_path: Path):
    rec = PerformanceRecorder()
    rec.start(now=0.0)
    rec.record("C4", 0.8, "on", now=0.2)
    perf = rec.stop("round")
    path = save_performance(perf, tmp_path / "perf.json")
    loaded = load_performance(path)
    assert loaded.name == "round"
    assert len(loaded.events) == 1
    assert loaded.events[0].note == "C4"


def test_player_plays_events_in_order():
    rec = PerformanceRecorder()
    rec.start(now=0.0)
    rec.record("C4", 1.0, "on", now=0.1)
    rec.record("D4", 1.0, "on", now=0.3)
    perf = rec.stop()
    player = PerformancePlayer(perf)
    player.start(now=0.0)
    first = player.update(0.15)
    assert [e.note for e in first] == ["C4"]
    second = player.update(0.35)
    assert [e.note for e in second] == ["D4"]


def test_audio_engine_disabled_is_safe():
    engine = AudioEngine(enabled=False)
    assert engine.available is False
    engine.note_on("v", "C4", 1.0)
    engine.note_off("v")
    engine.stop_all()
    engine.set_timbre("organ")
    assert engine.timbre == "organ"
    engine.shutdown()


def pytest_approx(value, rel=1e-6):
    import pytest

    return pytest.approx(value, rel=rel)
