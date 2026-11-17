"""Envoltorio de una línea (docs/06 §4.1): la lógica vive en ``compliance.html_checks`` (B6)."""
from compliance.html_checks import main

if __name__ == "__main__":
    import sys

    sys.exit(main())
