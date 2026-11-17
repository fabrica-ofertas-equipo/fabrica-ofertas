"""Punto de entrada: `.venv/bin/python -m scripts.modelado.barrido <subcomando> …` (ver cli.py y README.md)."""

from __future__ import annotations

from scripts.modelado.barrido.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
