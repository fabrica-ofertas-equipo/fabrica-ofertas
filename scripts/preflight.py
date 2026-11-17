"""Envoltorio de una línea (docs/06 §4.1): la lógica vive en ``infra.preflight`` (dueño: B8)."""
from infra.preflight import main

if __name__ == "__main__":
    import sys

    sys.exit(main())
