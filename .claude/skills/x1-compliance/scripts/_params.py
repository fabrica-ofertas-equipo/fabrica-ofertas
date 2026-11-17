"""Lector mínimo de ``empresa/parametros.yaml`` sin dependencias (PyYAML puede no estar en el ``python3`` del sistema).

Solo lee ``grupos.<grupo>.<clave>.valor``. No valida el archivo (eso es de ``scripts/validar_esquemas.py``) y no
inventa un valor: si algo falta devuelve ``None`` y quien llama NO decide (nada gasta ni se sella sin parámetro).
"""
from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]


def leer_parametro(grupo: str, clave: str, ruta: Path | None = None) -> str | None:
    ruta = ruta or RAIZ / "empresa" / "parametros.yaml"
    try:
        lineas = ruta.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    en_grupo = en_clave = False
    for linea in lineas:
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        sangria = len(linea) - len(linea.lstrip())
        texto = linea.strip()
        if sangria == 2:
            en_grupo, en_clave = texto == f"{grupo}:", False
        elif en_grupo and sangria == 4:
            en_clave = texto == f"{clave}:"
        elif en_grupo and en_clave and sangria == 6 and texto.startswith("valor:"):
            valor = texto.split(":", 1)[1].split("#", 1)[0].strip()
            return re.sub(r'^["\']|["\']$', "", valor)
    return None
