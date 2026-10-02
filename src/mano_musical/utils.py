"""Utilidades compartidas: logging, rutas, descarga de modelos y texto."""

from __future__ import annotations

import logging
import sys
import urllib.request
from pathlib import Path

from . import config


def setup_logging(debug: bool = False) -> logging.Logger:
    """Configura logging de consola y devuelve el logger del paquete."""
    level = logging.DEBUG if debug else logging.INFO
    logger = logging.getLogger("mano_musical")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def ensure_model(path: Path | None = None, url: str | None = None) -> Path:
    """Garantiza que exista el bundle de MediaPipe; lo descarga si falta."""
    path = path or config.HAND_LANDMARKER_MODEL
    url = url or config.HAND_LANDMARKER_URL
    if path.exists() and path.stat().st_size > 0:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    logging.getLogger("mano_musical").info("Descargando modelo MediaPipe -> %s", path)
    tmp = path.with_suffix(path.suffix + ".part")
    urllib.request.urlretrieve(url, tmp)
    tmp.replace(path)
    return path


def format_note(note: str | None) -> str:
    """Etiqueta humana ``E4 (Mi)`` para mostrar en pantalla."""
    if not note:
        return "—"
    solfeo = config.SOLFEGE.get(note[0], "?")
    return f"{note} ({solfeo})"


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
