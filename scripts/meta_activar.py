"""Envoltorio de una línea (convenciones §1): ``python -m scripts.meta_activar`` corre ``meta.activar``."""
from meta.activar import main

if __name__ == "__main__":
    raise SystemExit(main())
