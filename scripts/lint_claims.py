"""Envoltorio de una línea (docs/06 §4.1): la lógica vive en ``compliance.lint_claims`` (B6)."""
from compliance.lint_claims import main

if __name__ == "__main__":
    import sys

    sys.exit(main())
