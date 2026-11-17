"""Envoltorio de una línea (convenciones §1): ``python -m scripts.meta_crear`` corre ``meta.crear``."""
from meta.crear import main

if __name__ == "__main__":
    raise SystemExit(main())
