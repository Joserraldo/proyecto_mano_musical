"""Tests del modo juego y del reproductor automático."""

from __future__ import annotations

import pytest

from mano_musical import config, music
from mano_musical.game import JingleBellsGame, SongPlayer


def test_game_builds_targets_without_rests():
    game = JingleBellsGame(music.jingle_bells())
    assert len(game.targets) > 0
    assert all(t.note for t in game.targets)
    times = [t.time for t in game.targets]
    assert times == sorted(times)


def test_perfect_hit_and_combo():
    game = JingleBellsGame(music.jingle_bells())
    game.start(now=0.0)
    first = game.targets[0]
    result = game.register_input(first.note, now=game.start_time + first.time)
    assert result is not None
    assert result.judgement == "perfect"
    assert game.state.combo == 1
    assert game.state.score >= config.SCORE_PERFECT


def test_late_hit_is_ok_or_good():
    game = JingleBellsGame(music.jingle_bells())
    game.start(now=0.0)
    first = game.targets[0]
    offset = config.HIT_WINDOW_PERFECT + 0.02
    result = game.register_input(first.note, now=game.start_time + first.time + offset)
    assert result is not None
    assert result.judgement in ("good", "ok")


def test_input_outside_window_ignored():
    game = JingleBellsGame(music.jingle_bells())
    game.start(now=0.0)
    first = game.targets[0]
    far = game.start_time + first.time + config.HIT_WINDOW_OK + 1.0
    assert game.register_input(first.note, now=far) is None


def test_miss_is_recorded_after_window():
    game = JingleBellsGame(music.jingle_bells())
    game.start(now=0.0)
    first = game.targets[0]
    later = game.start_time + first.time + config.HIT_WINDOW_OK + 0.05
    results = game.update(later)
    assert any(r.judgement == "miss" for r in results)
    assert game.state.misses >= 1
    assert game.state.combo == 0


def test_wrong_note_does_not_score():
    game = JingleBellsGame(music.jingle_bells())
    game.start(now=0.0)
    first = game.targets[0]
    wrong = "A4" if first.note != "A4" else "C4"
    assert game.register_input(wrong, now=game.start_time + first.time) is None


def test_countdown_and_elapsed():
    game = JingleBellsGame()
    game.start(now=10.0)
    assert game.countdown(10.5) == pytest.approx(config.COUNTDOWN_SECONDS - 0.5)
    assert game.elapsed(game.start_time) == pytest.approx(0.0)


def test_song_player_emits_first_notes_once():
    player = SongPlayer(music.jingle_bells(), loop=False)
    player.start(now=0.0)
    due = player.update(0.001)
    assert due and due[0][0] == "E4"
    again = player.update(0.001)
    assert again == []


def test_song_player_orders_notes_by_time():
    player = SongPlayer(music.jingle_bells(), loop=False)
    player.start(now=0.0)
    first = player.update(0.0)
    second = player.update(0.6)
    assert first and second
    assert first[0][0] == "E4"
