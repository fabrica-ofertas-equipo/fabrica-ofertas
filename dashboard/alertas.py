"""``python -m dashboard.alertas``: el productor de alertas (B10 de ``docs/04`` §5) con el nombre que prometen ``contratos/alertas.schema.json`` y ``GET /api/finanzas``.

Es solo un atajo: la lógica vive en ``scripts/alertas/`` (``producir.py``) para que la compartan el panel, el informe de las 08:30 y la línea de comandos.
Por defecto NO escribe (``--simular``); ``--escribir`` guarda ``empresa/datos/alertas.jsonl``. Ver ``python -m dashboard.alertas --help``.
"""
from __future__ import annotations

import sys

from scripts.alertas.producir import main

__all__ = ["main"]

if __name__ == "__main__":
    sys.exit(main())
