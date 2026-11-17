"""Envoltorio de una línea (convenciones §1): ``python -m scripts.pausar`` corre ``meta.pausar`` (capa 2 del kill switch)."""
from meta.pausar import main

if __name__ == "__main__":
    raise SystemExit(main())
