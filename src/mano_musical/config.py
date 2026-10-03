"""Configuración global, constantes y mapas de notas de Mano Musical.

Todo valor "mágico" del proyecto vive acá para que sea fácil tunearlo sin
tocar la lógica. Los nombres de notas usan notación científica anglosajona
(C4 = do central).
"""

from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------
# Rutas del proyecto
# --------------------------------------------------------------------------
PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"
SONGS_DIR = ASSETS_DIR / "songs"
MODELS_DIR = ASSETS_DIR / "models"
OUTPUT_DIR = PROJECT_ROOT / "recordings"

HAND_LANDMARKER_MODEL = MODELS_DIR / "hand_landmarker.task"
HAND_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
    "hand_landmarker/float16/1/hand_landmarker.task"
)

# --------------------------------------------------------------------------
# Ventana / captura
# --------------------------------------------------------------------------
WINDOW_TITLE = "Mano Musical :: Air-Piano con MediaPipe"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
TARGET_FPS = 60
CAMERA_INDEX = 0
CAMERA_WIDTH = 1280
CAMERA_HEIGHT = 720
MIRROR = True  # efecto espejo: muevo mi mano derecha y se mueve a la derecha en pantalla
# MediaPipe 1.x etiqueta la lateralidad al revés para nuestra configuración de
# espejo; invertir por defecto hace que la mano derecha toque las notas agudas.
DEFAULT_SWAP_HANDS = True

# --------------------------------------------------------------------------
# Audio
# --------------------------------------------------------------------------
SAMPLE_RATE = 44_100
AUDIO_CHANNELS = 2
AUDIO_BUFFER = 512
AUDIO_FREQUENCY = 44_100
AUDIO_SIZE = -16
AUDIO_POLYPHONY = 32  # canales simultáneos del mixer
MASTER_VOLUME = 0.85
NOTE_DURATION = 3.0  # segundos de la muestra sintetizada por nota
RELEASE_FADE_MS = 140  # fadeout al soltar el dedo

# --------------------------------------------------------------------------
# Escala: 10 notas -> 10 dedos (rango exacto de Jingle Bells en Do mayor)
# --------------------------------------------------------------------------
SCALE = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5", "D5", "E5"]

FINGER_ORDER = ["thumb", "index", "middle", "ring", "pinky"]

FINGER_NAMES_ES = {
    "thumb": "pulgar",
    "index": "índice",
    "middle": "medio",
    "ring": "anular",
    "pinky": "meñique",
}

# Mapa (mano, dedo) -> nota. Los pulgares quedan al centro (G4 / A4) y las
# notas suben hacia los meñiques, como un piano "desplegado" en el aire.
NOTE_MAP: dict[tuple[str, str], str] = {
    ("Left", "pinky"): "C4",
    ("Left", "ring"): "D4",
    ("Left", "middle"): "E4",
    ("Left", "index"): "F4",
    ("Left", "thumb"): "G4",
    ("Right", "thumb"): "A4",
    ("Right", "index"): "B4",
    ("Right", "middle"): "C5",
    ("Right", "ring"): "D5",
    ("Right", "pinky"): "E5",
}

# Orden visual de las teclas de izquierda a derecha.
VISUAL_KEYS = ["C4", "D4", "E4", "F4", "G4", "A4", "B4", "C5", "D5", "E5"]

# Etiquetas solfeo (latino) para mostrar en pantalla.
SOLFEGE = {
    "C": "Do",
    "D": "Re",
    "E": "Mi",
    "F": "Fa",
    "G": "Sol",
    "A": "La",
    "B": "Si",
}

# Teclas de respaldo (modo sin cámara / accesibilidad).
KEYBOARD_MAP = {
    "a": "C4",
    "s": "D4",
    "d": "E4",
    "f": "F4",
    "g": "G4",
    "h": "A4",
    "j": "B4",
    "k": "C5",
    "l": "D5",
    ";": "E5",
}

# --------------------------------------------------------------------------
# Detección de "dedo presionado"
# --------------------------------------------------------------------------
# Ángulo de la articulación PIP (grados). Dedo extendido ~180°, dedo doblado ~70°.
PRESS_ANGLE_ENTER = 118.0  # por debajo de esto: se considera presionado
PRESS_ANGLE_RELEASE = 145.0  # por encima de esto: se considera suelto (histéresis)
PRESS_VELOCITY_MIN = 0.0
PRESS_VELOCITY_MAX = 900.0  # grados/segundo
LANDMARK_SMOOTHING = 0.55  # 0 = sin suavizado, 0.9 = muy suave

# Calibración: al abrir la mano se mide el ángulo "extendido" real de cada dedo
# y los umbrales se derivan de ahí (enter = extendido - margen).
CALIBRATION_SECONDS = 4.0
CALIB_MARGIN_ENTER = 55.0
CALIB_MARGIN_RELEASE = 25.0
CALIB_MIN_EXTENDED = 120.0  # si un dedo nunca pasó de acá, se usa el umbral global
SENSITIVITY_STEP = 7.0
SENSITIVITY_MIN = 70.0
SENSITIVITY_MAX = 168.0

# --------------------------------------------------------------------------
# Puntaje / modo juego
# --------------------------------------------------------------------------
TEMPO_BPM = 120
COUNTDOWN_SECONDS = 3.0
HIT_WINDOW_PERFECT = 0.09  # s
HIT_WINDOW_GOOD = 0.20  # s
HIT_WINDOW_OK = 0.32  # s
SCORE_PERFECT = 100
SCORE_GOOD = 70
SCORE_OK = 40
SCORE_MISS = 0

# --------------------------------------------------------------------------
# Paleta visual
# --------------------------------------------------------------------------
COLOR_BG = (10, 12, 24)
COLOR_PANEL = (18, 22, 42)
COLOR_PANEL_LIGHT = (30, 36, 64)
COLOR_TEXT = (232, 236, 255)
COLOR_TEXT_DIM = (128, 138, 176)
COLOR_ACCENT = (0, 224, 200)
COLOR_ACCENT_2 = (255, 96, 160)
COLOR_WARN = (255, 196, 64)
COLOR_OK = (96, 230, 140)

NOTE_COLORS = {
    "C4": (255, 99, 132),
    "D4": (255, 159, 64),
    "E4": (255, 206, 86),
    "F4": (153, 220, 92),
    "G4": (86, 220, 160),
    "A4": (86, 196, 240),
    "B4": (120, 150, 255),
    "C5": (170, 120, 255),
    "D5": (230, 120, 255),
    "E5": (255, 120, 200),
}

# Conexiones del esqueleto de la mano (índices de landmarks MediaPipe).
HAND_CONNECTIONS: list[tuple[int, int]] = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
]

FINGER_JOINTS = {
    "thumb": [1, 2, 3, 4],
    "index": [5, 6, 7, 8],
    "middle": [9, 10, 11, 12],
    "ring": [13, 14, 15, 16],
    "pinky": [17, 18, 19, 20],
}

# Silencia logs verbosos de TensorFlow/absl antes de importar mediapipe.
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
os.environ.setdefault("GLOG_minloglevel", "3")
os.environ.setdefault("ABSL_MIN_LOG_LEVEL", "3")
