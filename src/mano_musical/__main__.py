"""Punto de entrada: ``python -m mano_musical``."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    from .app import ManoMusicalApp, build_parser

    parser = build_parser()
    args = parser.parse_args(argv)
    app = ManoMusicalApp(args)
    return app.run()


if __name__ == "__main__":
    raise SystemExit(main())
