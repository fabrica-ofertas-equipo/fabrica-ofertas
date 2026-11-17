"""Envoltorio de una línea (convenciones §1): ``python -m scripts.subir_presupuesto`` corre ``meta.subir_presupuesto``."""
from meta.subir_presupuesto import main

if __name__ == "__main__":
    raise SystemExit(main())
