"""Descarga el bundle de MediaPipe HandLandmarker a assets/models/.

Uso:
    python scripts/download_models.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from mano_musical.utils import ensure_model, setup_logging  # noqa: E402


def main() -> int:
    setup_logging()
    logging.getLogger("mano_musical").info("Preparando modelo de manos...")
    path = ensure_model()
    size_mb = path.stat().st_size / (1024 * 1024)
    print(f"Modelo listo: {path} ({size_mb:.1f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
