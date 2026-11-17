#!/usr/bin/env python3
"""L1-11 (parte local) · Empaquetado: sha256 y peso de cada entregable, nombres neutros y huérfanos. NO sube nada (la subida a ``preprod/`` es de
``scripts/producto/subir_preprod`` [PENDIENTE]).

Para cada ítem de ``04-producto/producto.json`` calcula ``sha256`` con la regla del validador de esquemas (JSON canónico, texto NFC/LF, resto por bytes) y
``peso_mb`` (2 decimales, cadena). Con ``--actualizar`` escribe esos dos campos en ``producto.json`` (único archivo que toca; nunca borra ítems).

Comprueba: el archivo existe; el nombre sigue ``slug-vN[-tipo].ext`` en minúsculas ASCII y SIN términos de condición, deuda o estado (neutralidad,
X1-D01/D04; interino hasta ``terminos_sensibles/<locale>.yaml``); un PDF no excede ``producto.peso_max_mb_pdf`` y el paquete (``en_paquete``) no excede
``producto.peso_max_mb_paquete``; hay ≥ 1 ítem en paquete; no hay archivos en ``entregables/`` que no estén en ``items`` (huérfanos; ``fuente/`` y
``muestras/`` se ignoran como apoyo).

Uso: python3 empaquetar.py --oferta-dir ofertas/OF-AAAAMM-NN [--actualizar] [--parametros empresa/parametros.yaml] [--terminos lista.txt] [--salida X]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun as c  # noqa: E402
import _patrones as pt  # noqa: E402

RX_NOMBRE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*-v[1-9][0-9]*(?:-[a-z0-9]+)?\.[a-z0-9]+$")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--oferta-dir", required=True)
    ap.add_argument("--actualizar", action="store_true")
    ap.add_argument("--parametros")
    ap.add_argument("--terminos", help="archivo con un patrón regex por línea (términos sensibles del locale) que se suma a la lista interina")
    ap.add_argument("--max-mb-pdf", type=Decimal)
    ap.add_argument("--max-mb-paquete", type=Decimal)
    ap.add_argument("--salida")
    a = ap.parse_args(argv)
    d = Path(a.oferta_dir)
    base = d / "04-producto"
    try:
        par = c.parametros_por_defecto(a.parametros)
        max_pdf = Decimal(str(c.parametro(par, "producto", "peso_max_mb_pdf", a.max_mb_pdf)))
        max_paq = Decimal(str(c.parametro(par, "producto", "peso_max_mb_paquete", a.max_mb_paquete)))
        prod = c.cargar_json(base / "producto.json")
    except c.ParametroFaltante as e:
        return c.error_uso(str(e), 5)
    except (OSError, ValueError) as e:
        return c.error_uso(f"entrada inválida: {e}", 3)
    sensibles = list(pt.NOMBRES_SENSIBLES)
    if a.terminos:
        sensibles += [l.strip() for l in Path(a.terminos).read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    rx_sens = re.compile("|".join(sensibles), re.I)
    h: list[dict] = []
    total_paquete = Decimal(0)
    manifiesto = []
    registrados = set()
    for it in prod["items"]:
        ruta = base / it["archivo"]
        registrados.add(ruta.resolve())
        if not ruta.is_file():
            h.append(c.hallazgo("L1-11", "BLOQUEANTE", f"ítem {it['id']}: no existe {it['archivo']}", "producto.json#items"))
            continue
        peso = (Decimal(ruta.stat().st_size) / Decimal(1024 * 1024)).quantize(Decimal("0.01"), ROUND_HALF_EVEN)
        sha = c.hash_archivo(ruta)
        manifiesto.append({"id": it["id"], "archivo": it["archivo"], "sha256": sha, "peso_mb": str(peso), "en_paquete": it["en_paquete"]})
        nombre = ruta.name
        if it["en_paquete"]:
            total_paquete += peso
            if not RX_NOMBRE.match(nombre):
                h.append(c.hallazgo("L1-11", "MAYOR", f"nombre «{nombre}» no sigue slug-vN[-tipo].ext (minúsculas, ASCII, guiones)", it["archivo"], "nombre-no-neutro"))
            if rx_sens.search(nombre) or rx_sens.search(str(Path(it["archivo"]).parent)):
                h.append(c.hallazgo("L1-11", "BLOQUEANTE", f"el nombre o la ruta «{it['archivo']}» contiene un término de condición, deuda o estado (archivo, clave de objeto y URL deben ser neutros)", it["archivo"], "nombre-sensible"))
        if ruta.suffix.lower() == ".pdf" and peso > max_pdf:
            h.append(c.hallazgo("L1-03", "MAYOR", f"PDF de {peso} MB > máximo {max_pdf} MB", it["archivo"], "peso"))
        if it["sha256"] != sha and not a.actualizar:
            h.append(c.hallazgo("L1-11", "BLOQUEANTE", f"sha256 de {it['id']} no coincide con el archivo (esperado {sha[:19]}…): usar --actualizar tras cada cambio", it["archivo"], "hash-desactualizado"))
        if a.actualizar:
            it["sha256"], it["peso_mb"] = sha, str(peso)
    if total_paquete > max_paq:
        h.append(c.hallazgo("L1-03", "MAYOR", f"paquete de {total_paquete} MB > máximo {max_paq} MB", "producto.json#items", "peso"))
    if not any(i["en_paquete"] for i in prod["items"]):
        h.append(c.hallazgo("L1-11", "BLOQUEANTE", "ningún ítem en paquete", "producto.json#items"))
    ent = base / "entregables"
    if ent.is_dir():
        for f in sorted(x for x in ent.iterdir() if x.is_file()):
            if f.resolve() not in registrados:
                h.append(c.hallazgo("L1-11", "MENOR", f"archivo huérfano en entregables/: {f.name} (no figura en items)", str(f.relative_to(d)), "huerfano"))
    if a.actualizar and not any(x["severidad"] == "BLOQUEANTE" and "no existe" in x["mensaje"] for x in h):
        (base / "producto.json").write_text(json.dumps(prod, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return c.emitir("empaquetar", ["L1-11", "L1-03"], h, {"paquete_mb": str(total_paquete), "manifiesto": manifiesto, "actualizado": a.actualizar}, a.salida)


if __name__ == "__main__":
    sys.exit(main())
