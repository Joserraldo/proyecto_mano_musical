"""Motor de audio polifónico sobre ``pygame.mixer``.

Cada dedo/pulsación ocupa un "voice" con su propio canal, así varias notas
suenan a la vez. Las muestras se sintetizan con ``music.synthesize_note`` y se
cachean. Si el mixer no puede inicializarse el motor queda deshabilitado y el
resto de la app sigue funcionando (modo silencioso).
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from . import config, music

try:  # pygame es opcional a nivel de import para tests sin audio
    import pygame
except Exception:  # pragma: no cover
    pygame = None  # type: ignore[assignment]

log = logging.getLogger("mano_musical.audio")


class AudioEngine:
    """Sintetizador polifónico con canales independientes por voz."""

    def __init__(
        self,
        sample_rate: int = config.AUDIO_FREQUENCY,
        buffer: int = config.AUDIO_BUFFER,
        polyphony: int = config.AUDIO_POLYPHONY,
        master_volume: float = config.MASTER_VOLUME,
        timbre: str = "piano",
        enabled: bool = True,
    ) -> None:
        self.sample_rate = sample_rate
        self.polyphony = polyphony
        self.master_volume = float(np.clip(master_volume, 0.0, 1.0))
        self.timbre = timbre
        self.channels = config.AUDIO_CHANNELS
        self.available = False
        self._sounds: dict[tuple[str, str], "pygame.mixer.Sound"] = {}
        self._voices: dict[str, "pygame.mixer.Channel"] = {}
        self._backing: Optional["pygame.mixer.Channel"] = None
        if enabled:
            self.available = self._init_mixer(buffer)

    # ------------------------------------------------------------------ init
    def _init_mixer(self, buffer: int) -> bool:
        if pygame is None:
            log.warning("pygame no disponible: audio deshabilitado")
            return False
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.pre_init(
                    frequency=self.sample_rate,
                    size=config.AUDIO_SIZE,
                    channels=config.AUDIO_CHANNELS,
                    buffer=buffer,
                )
                pygame.mixer.init()
            pygame.mixer.set_num_channels(max(self.polyphony, 16))
            info = pygame.mixer.get_init()
            if info:
                self.channels = int(info[2])
            log.info("Mixer iniciado: %s (canales=%d)", info, self.channels)
            return True
        except Exception as exc:  # pragma: no cover
            log.warning("No se pudo iniciar el mixer (%s): audio deshabilitado", exc)
            return False

    # --------------------------------------------------------------- samples
    def _to_mixer(self, array: np.ndarray) -> np.ndarray:
        """Adapta una muestra al número real de canales del dispositivo."""
        if array.ndim == 1:
            array = array[:, None]
        if array.shape[1] == self.channels:
            return np.ascontiguousarray(array)
        mono = array[:, 0]
        tiled = np.repeat(mono[:, None], self.channels, axis=1)
        return np.ascontiguousarray(tiled)

    def _sound_for(self, note: str, timbre: str | None = None) -> Optional["pygame.mixer.Sound"]:
        if not self.available:
            return None
        timbre = timbre or self.timbre
        key = (note, timbre)
        if key not in self._sounds:
            array = music.synthesize_note_timbre(
                note, timbre=timbre, duration=config.NOTE_DURATION, sample_rate=self.sample_rate
            )
            self._sounds[key] = pygame.sndarray.make_sound(self._to_mixer(array))
        return self._sounds[key]

    def set_timbre(self, timbre: str) -> None:
        """Cambia el timbre global (se renderiza perezosamente)."""
        self.timbre = timbre if timbre in music.Timbres else "piano"

    # ----------------------------------------------------------------- voices
    def note_on(self, voice: str, note: str, velocity: float = 1.0) -> None:
        """Enciende una nota en la voz indicada (reactiva si ya sonaba)."""
        if not self.available:
            return
        sound = self._sound_for(note)
        if sound is None:
            return
        channel = self._voices.get(voice)
        if channel is None or channel.get_busy():
            free = pygame.mixer.find_channel(True)
            if free is None:
                return
            channel = free
        self._voices[voice] = channel
        channel.set_volume(self.master_volume * float(np.clip(velocity, 0.0, 1.0)))
        channel.play(sound)

    def note_off(self, voice: str, fade_ms: int = config.RELEASE_FADE_MS) -> None:
        """Suelta la voz con un fade corto para evitar clicks."""
        channel = self._voices.pop(voice, None)
        if channel is not None and self.available:
            channel.fadeout(max(0, fade_ms))

    def play_once(self, note: str, velocity: float = 1.0) -> None:
        """Reproduce una nota sin gestionar voice (para juego/autoplay)."""
        self.note_on(f"once:{note}:{pygame.time.get_ticks() if self.available else 0}", note, velocity)

    def stop_all(self) -> None:
        if not self.available:
            return
        for channel in list(self._voices.values()):
            channel.fadeout(60)
        self._voices.clear()
        pygame.mixer.stop()

    # --------------------------------------------------------------- backing
    def play_backing(self, samples: np.ndarray, loops: int = 0) -> None:
        """Reproduce una pista de acompañamiento en un canal dedicado."""
        if not self.available:
            return
        sound = pygame.sndarray.make_sound(self._to_mixer(samples))
        if self._backing is None or not self._backing.get_busy():
            self._backing = pygame.mixer.find_channel(True)
        if self._backing is None:
            return
        self._backing.set_volume(self.master_volume)
        self._backing.play(sound, loops=loops)

    def stop_backing(self) -> None:
        if self._backing is not None and self.available:
            self._backing.fadeout(200)
            self._backing = None

    def set_master_volume(self, value: float) -> None:
        self.master_volume = float(np.clip(value, 0.0, 1.0))

    def active_count(self) -> int:
        return sum(1 for ch in self._voices.values() if ch.get_busy())

    def shutdown(self) -> None:
        self.stop_all()
        self.stop_backing()
