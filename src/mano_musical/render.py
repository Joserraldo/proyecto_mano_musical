"""Renderizado con pygame: cámara, esqueleto, teclas, partículas y HUD.

Todo el dibujo ocurre en el hilo principal. Si no hay cámara se dibuja un fondo
animado y la ayuda de teclado. El layout reserva una franja superior (HUD) y
una inferior (piano de 10 teclas) alineadas con ``config.VISUAL_KEYS``.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from . import config
from .hand_tracker import HandFrame
from .utils import clamp

log = logging.getLogger("mano_musical.render")

try:
    import pygame
except Exception:  # pragma: no cover
    pygame = None  # type: ignore[assignment]

try:
    import cv2
except Exception:  # pragma: no cover
    cv2 = None  # type: ignore[assignment]


def _font(size: int, bold: bool = False) -> "pygame.font.Font":
    try:
        return pygame.font.SysFont("Consolas", size, bold=bold)
    except Exception:  # pragma: no cover
        return pygame.font.Font(None, size)


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: tuple
    size: float
    gravity: float = 260.0

    def update(self, dt: float) -> bool:
        self.life -= dt
        self.vy += self.gravity * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        return self.life > 0


class ParticleSystem:
    """Partículas que brotan al tocar cada nota."""

    def __init__(self, limit: int = 600) -> None:
        self.items: list[Particle] = []
        self.limit = limit

    def burst(self, x: float, y: float, color: tuple, count: int = 22, power: float = 1.0) -> None:
        for _ in range(count):
            angle = random.uniform(0, math.tau)
            speed = random.uniform(60, 320) * power
            life = random.uniform(0.45, 1.1)
            self.items.append(
                Particle(
                    x,
                    y,
                    math.cos(angle) * speed,
                    math.sin(angle) * speed - 80,
                    life,
                    life,
                    color,
                    random.uniform(2.5, 6.5),
                )
            )
        if len(self.items) > self.limit:
            self.items = self.items[-self.limit:]

    def update(self, dt: float) -> None:
        self.items = [p for p in self.items if p.update(dt)]

    def draw(self, surface: "pygame.Surface", alpha: bool = True) -> None:
        for p in self.items:
            ratio = clamp(p.life / p.max_life, 0.0, 1.0)
            color = tuple(int(c * (0.35 + 0.65 * ratio)) for c in p.color)
            radius = max(1, int(p.size * ratio))
            pygame.draw.circle(surface, color, (int(p.x), int(p.y)), radius)


@dataclass
class HudData:
    """Datos que alimentan el HUD desde la app."""

    mode: str = "free"
    fps: float = 0.0
    infer_ms: float = 0.0
    hands: int = 0
    active_notes: list[str] = field(default_factory=list)
    camera: bool = True
    tracker: bool = True
    timbre: str = "piano"
    octave: int = 0
    recording: bool = False
    message: str = ""
    submessage: str = ""
    show_help: bool = False
    countdown: float = 0.0
    banner: str = ""
    banner_timer: float = 0.0
    game: Optional[dict] = None


class Renderer:
    """Dibuja un frame completo de Mano Musical."""

    KEY_BAND_HEIGHT = 190
    HUD_HEIGHT = 74

    def __init__(self, width: int = config.WINDOW_WIDTH, height: int = config.WINDOW_HEIGHT) -> None:
        if pygame is None:  # pragma: no cover
            raise RuntimeError("pygame no está disponible")
        self.width = width
        self.height = height
        self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
        pygame.display.set_caption(config.WINDOW_TITLE)
        self.font_sm = _font(15)
        self.font_md = _font(22, bold=True)
        self.font_lg = _font(38, bold=True)
        self.font_xl = _font(90, bold=True)
        self.particles = ParticleSystem()
        self.view_rect = pygame.Rect(0, self.HUD_HEIGHT, width, height - self.HUD_HEIGHT - self.KEY_BAND_HEIGHT)
        self._text_cache: dict = {}
        self.time = 0.0

    # -------------------------------------------------------------- utilities
    def _text(self, text: str, font, color) -> "pygame.Surface":
        key = (text, id(font), color)
        surf = self._text_cache.get(key)
        if surf is None:
            surf = font.render(text, True, color)
            if len(self._text_cache) > 800:
                self._text_cache.clear()
            self._text_cache[key] = surf
        return surf

    def _blit_text(self, text: str, font, color, x: int, y: int, center: bool = False) -> pygame.Rect:
        surf = self._text(text, font, color)
        rect = surf.get_rect()
        if center:
            rect.center = (x, y)
        else:
            rect.topleft = (x, y)
        self.screen.blit(surf, rect)
        return rect

    def _stage_rect(self) -> pygame.Rect:
        top = self.HUD_HEIGHT
        bottom = self.height - self.KEY_BAND_HEIGHT
        return pygame.Rect(0, top, self.width, max(1, bottom - top))

    def to_screen(self, nx: float, ny: float) -> tuple[float, float]:
        r = self.view_rect
        return r.x + nx * r.width, r.y + ny * r.height

    def key_rect(self, note: str) -> pygame.Rect:
        idx = config.VISUAL_KEYS.index(note)
        n = len(config.VISUAL_KEYS)
        band_top = self.height - self.KEY_BAND_HEIGHT
        pad = 6
        w = self.width / n
        return pygame.Rect(int(idx * w) + pad, band_top + pad, int(w) - 2 * pad, self.KEY_BAND_HEIGHT - 2 * pad)

    def burst_note(self, note: str, screen_pos: tuple[float, float], velocity: float = 1.0) -> None:
        color = config.NOTE_COLORS.get(note, config.COLOR_ACCENT)
        self.particles.burst(screen_pos[0], screen_pos[1], color, count=20, power=0.6 + velocity)

    # ----------------------------------------------------------------- drawing
    def draw_background(self) -> None:
        self.screen.fill(config.COLOR_BG)
        band = pygame.Surface((self.width, self.KEY_BAND_HEIGHT))
        band.fill(config.COLOR_PANEL)
        self.screen.blit(band, (0, self.height - self.KEY_BAND_HEIGHT))
        top = pygame.Surface((self.width, self.HUD_HEIGHT))
        top.fill(config.COLOR_PANEL)
        self.screen.blit(top, (0, 0))

    def draw_camera(self, frame: Optional[np.ndarray]) -> None:
        stage = self._stage_rect()
        if frame is None or cv2 is None:
            self.view_rect = stage
            self._draw_idle_stage(stage)
            return
        h, w = frame.shape[:2]
        scale = min(stage.width / w, stage.height / h)
        new_size = (max(1, int(w * scale)), max(1, int(h * scale)))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        surf = pygame.image.frombuffer(rgb.tobytes(), (w, h), "RGB")
        surf = pygame.transform.scale(surf, new_size)
        x = stage.x + (stage.width - new_size[0]) // 2
        y = stage.y + (stage.height - new_size[1]) // 2
        self.view_rect = pygame.Rect(x, y, new_size[0], new_size[1])
        self.screen.blit(surf, (x, y))
        shade = pygame.Surface(new_size, pygame.SRCALPHA)
        shade.fill((0, 0, 0, 40))
        self.screen.blit(shade, (x, y))
        pygame.draw.rect(self.screen, config.COLOR_PANEL_LIGHT, self.view_rect, 2, border_radius=12)

    def _draw_idle_stage(self, stage: pygame.Rect) -> None:
        t = self.time
        for i in range(0, stage.width, 40):
            alpha = int(18 + 14 * math.sin(t * 1.5 + i * 0.02))
            color = (alpha, min(255, alpha + 20), 60)
            pygame.draw.line(self.screen, color, (stage.x + i, stage.y), (stage.x + i, stage.bottom))
        self._blit_text(
            "SIN CÁMARA  ·  usa el teclado",
            self.font_lg,
            config.COLOR_TEXT_DIM,
            stage.centerx,
            stage.centery - 40,
            center=True,
        )
        self._blit_text(
            "A S D F G   H J K L ;   =   Do Re Mi Fa Sol La Si Do' Re' Mi'",
            self.font_md,
            config.COLOR_ACCENT,
            stage.centerx,
            stage.centery + 20,
            center=True,
        )

    def draw_hands(self, hand_frame: HandFrame, readings: dict) -> None:
        if not hand_frame.hands:
            return
        for hand in hand_frame.hands:
            label = "IZQ" if hand.handedness == "Left" else "DER"
            pts = [self.to_screen(hand.landmarks[i, 0], hand.landmarks[i, 1]) for i in range(21)]
            for a, b in config.HAND_CONNECTIONS:
                pressed_link = self._link_pressed(hand, readings, a, b)
                color = config.COLOR_ACCENT if pressed_link else config.COLOR_PANEL_LIGHT
                width = 4 if pressed_link else 2
                pygame.draw.line(self.screen, color, pts[a], pts[b], width)
            for i, (sx, sy) in enumerate(pts):
                pygame.draw.circle(self.screen, (245, 245, 255), (int(sx), int(sy)), 3)
            for finger in config.FINGER_ORDER:
                note = config.NOTE_MAP.get((hand.handedness, finger))
                if note is None:
                    continue
                tip_idx = config.FINGER_JOINTS[finger][-1]
                sx, sy = pts[tip_idx]
                reading = readings.get(note, {})
                pressed = bool(reading.get("pressed"))
                color = config.NOTE_COLORS.get(note, config.COLOR_ACCENT)
                radius = 14 if pressed else 9
                if pressed:
                    pygame.draw.circle(self.screen, color, (int(sx), int(sy)), radius + 8, 3)
                pygame.draw.circle(self.screen, color, (int(sx), int(sy)), radius)
                if pressed:
                    self._blit_text(note, self.font_sm, (0, 0, 0), int(sx), int(sy), center=True)
            cx, cy = hand.center()
            sx, sy = self.to_screen(cx, cy)
            self._blit_text(label, self.font_sm, config.COLOR_TEXT_DIM, int(sx), int(sy) - 30, center=True)

    def _link_pressed(self, hand, readings: dict, a: int, b: int) -> bool:
        for finger, joints in config.FINGER_JOINTS.items():
            if a in joints and b in joints:
                note = config.NOTE_MAP.get((hand.handedness, finger))
                return bool(readings.get(note, {}).get("pressed")) if note else False
        return False

    def draw_keys(self, active_notes: list[str], flash: Optional[dict] = None) -> None:
        flash = flash or {}
        band_top = self.height - self.KEY_BAND_HEIGHT
        for note in config.VISUAL_KEYS:
            rect = self.key_rect(note)
            color = config.NOTE_COLORS.get(note, config.COLOR_ACCENT)
            active = note in active_notes
            glow = flash.get(note, 0.0)
            base = tuple(min(255, int(c * (0.28 + 0.5 * glow))) for c in color)
            if active:
                base = color
            pygame.draw.rect(self.screen, base, rect, border_radius=10)
            pygame.draw.rect(self.screen, color, rect, 3, border_radius=10)
            solfeo = config.SOLFEGE.get(note[0], "?")
            text_color = (10, 10, 20) if active else config.COLOR_TEXT
            self._blit_text(solfeo, self.font_md, text_color, rect.centerx, rect.y + 34, center=True)
            self._blit_text(note, self.font_sm, text_color, rect.centerx, rect.y + 62, center=True)
            key_char = next((k for k, v in config.KEYBOARD_MAP.items() if v == note), "")
            self._blit_text(key_char.upper(), self.font_md, text_color, rect.centerx, rect.bottom - 34, center=True)
        self._blit_text("Do Re Mi ... escala", self.font_sm, config.COLOR_TEXT_DIM, 12, band_top - 22)

    def draw_falling_notes(self, upcoming: list, horizon: float = 3.0) -> None:
        stage = self._stage_rect()
        for target, delta in upcoming:
            ratio = clamp((horizon - delta) / horizon, 0.0, 1.0)
            y = int(stage.y + ratio * (stage.height - 10))
            rect = self.key_rect(target.note)
            color = config.NOTE_COLORS.get(target.note, config.COLOR_ACCENT)
            pill = pygame.Rect(rect.x + 10, y - 16, rect.width - 20, 32)
            pygame.draw.rect(self.screen, color, pill, border_radius=16)
            pygame.draw.rect(self.screen, (255, 255, 255), pill, 2, border_radius=16)
            self._blit_text(target.note, self.font_sm, (0, 0, 0), pill.centerx, pill.centery, center=True)
        hit_line = pygame.Rect(stage.x, self.height - self.KEY_BAND_HEIGHT - 6, stage.width, 6)
        pygame.draw.rect(self.screen, config.COLOR_ACCENT, hit_line, border_radius=3)

    def draw_hud(self, hud: HudData) -> None:
        self._blit_text("MANO MUSICAL", self.font_md, config.COLOR_ACCENT, 16, 12)
        mode_label = {"free": "LIBRE", "game": "JUEGO: JINGLE BELLS", "demo": "DEMO AUTOMÁTICA", "replay": "REPLAY"}.get(
            hud.mode, hud.mode.upper()
        )
        self._blit_text(mode_label, self.font_md, config.COLOR_TEXT, 230, 12)
        info = f"{hud.fps:4.0f} FPS · infer {hud.infer_ms:4.1f} ms · manos {hud.hands} · timbre {hud.timbre} · oct {hud.octave:+d}"
        self._blit_text(info, self.font_sm, config.COLOR_TEXT_DIM, 16, 44)
        if hud.recording:
            pygame.draw.circle(self.screen, config.COLOR_ACCENT_2, (self.width - 200, 30), 10)
            self._blit_text("REC", self.font_md, config.COLOR_ACCENT_2, self.width - 186, 18)
        estado = "cámara OK" if hud.camera else "sin cámara"
        estado += " · tracker OK" if hud.tracker else " · tracker off"
        self._blit_text(estado, self.font_sm, config.COLOR_TEXT_DIM, self.width - 260, 44)
        notes = " ".join(hud.active_notes) if hud.active_notes else "—"
        self._blit_text(f"Sonando: {notes}", self.font_sm, config.COLOR_TEXT, self.width - 470, 12)
        if hud.game:
            self._draw_game_hud(hud.game)
        if hud.countdown > 0:
            self._blit_text(str(int(math.ceil(hud.countdown))), self.font_xl, config.COLOR_ACCENT, self.width // 2, self.height // 2, center=True)
        if hud.banner and hud.banner_timer > 0:
            self._blit_text(hud.banner, self.font_lg, config.COLOR_WARN, self.width // 2, self.HUD_HEIGHT + 60, center=True)

    def _draw_game_hud(self, game: dict) -> None:
        x = self.width // 2 - 120
        self._blit_text(f"SCORE {game.get('score', 0):>6}", self.font_md, config.COLOR_TEXT, x, 10)
        self._blit_text(f"COMBO x{game.get('combo', 0)}", self.font_sm, config.COLOR_ACCENT, x, 40)
        self._blit_text(f"ACC {game.get('accuracy', 0):5.1f}%", self.font_sm, config.COLOR_TEXT_DIM, x + 200, 40)
        judgement = game.get("last_judgement", "")
        colors = {"perfect": config.COLOR_ACCENT, "good": config.COLOR_OK, "ok": config.COLOR_WARN, "miss": config.COLOR_ACCENT_2}
        if judgement and game.get("judgement_timer", 0) > 0:
            self._blit_text(judgement.upper(), self.font_lg, colors.get(judgement, config.COLOR_TEXT), self.width // 2, self.height - self.KEY_BAND_HEIGHT - 60, center=True)

    def draw_help(self) -> None:
        overlay = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        overlay.fill((6, 8, 18, 225))
        self.screen.blit(overlay, (0, 0))
        lines = [
            ("MANO MUSICAL — AYUDA", config.COLOR_ACCENT, self.font_lg),
            ("Baja/dobla un dedo para tocar su nota (air-piano).", config.COLOR_TEXT, self.font_md),
            ("Izq: meñique C4 · anular D4 · medio E4 · índice F4 · pulgar G4", config.COLOR_TEXT_DIM, self.font_sm),
            ("Der: pulgar A4 · índice B4 · medio C5 · anular D5 · meñique E5", config.COLOR_TEXT_DIM, self.font_sm),
            ("", config.COLOR_TEXT, self.font_sm),
            ("F1 modo libre   F2 juego Jingle Bells   F3 demo   F4 replay", config.COLOR_TEXT, self.font_sm),
            ("R grabar/reproducir   T timbre   M mutear   O octava   C calibrar", config.COLOR_TEXT, self.font_sm),
            ("[ / ] cambiar modo de detección (curl/drop)   H ayuda   ESC salir", config.COLOR_TEXT, self.font_sm),
            ("", config.COLOR_TEXT, self.font_sm),
            ("Jingle Bells se toca así:  E E E · E E E · E G C D E · ...", config.COLOR_WARN, self.font_md),
        ]
        y = 120
        for text, color, font in lines:
            if text:
                self._blit_text(text, font, color, self.width // 2, y, center=True)
            y += 40 if font is not self.font_sm else 30
        self._blit_text("H para cerrar", self.font_sm, config.COLOR_TEXT_DIM, self.width // 2, self.height - 40, center=True)

    def present(self, dt: float) -> None:
        self.particles.update(dt)
        self.particles.draw(self.screen)
        self.time += dt
        pygame.display.flip()
