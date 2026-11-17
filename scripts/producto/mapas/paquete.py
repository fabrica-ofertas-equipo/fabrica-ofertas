"""``producto.json`` de los mapas con sha256 por archivo (contrato ``contratos/producto.schema.json``).

Reutiliza ``scripts.producto.empaquetar`` (recalcula siempre sha256 y peso desde el archivo real y valida contra el esquema). Este módulo
solo sabe QUÉ archivos del piloto son ítems (PDF por nivel, índice, muestras) y calcula los tiempos a partir de los mapas.

CLI::

    .venv/bin/python -m scripts.producto.mapas.paquete --base ofertas/OF-202611-91/04-producto --prometido-min 10 [--salida producto.json] [--indice-en-paquete]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.producto.mapas.esquema import NIVELES, palabras_visibles
from scripts.producto.mapas.lote import cargar_mapas

LOCALE = "pl-PL"
_RX_PAGINA = re.compile(rb"/Type\s*/Page(?![A-Za-z])")


def paginas_pdf(ruta: Path) -> int:
    return len(_RX_PAGINA.findall(ruta.read_bytes()))


def tiempos_desde_mapas(mapas: Sequence[Mapping[str, Any]], pasos: Sequence[Mapping[str, Any]], *, prometido_min: int, wpm: int = 180) -> dict[str, Any]:
    """Tiempo = lectura del mapa MÁS cargado + Σ pasos (base «estimado»: no hay cronometraje humano)."""
    maximo = max(palabras_visibles(m) for m in mapas)
    lectura = math.ceil(maximo / wpm)
    ejec = sum(p["t_humano_min"] for p in pasos)
    return {"lectura_min": lectura, "ejecucion_min": ejec, "total_min": lectura + ejec, "prometido_min": prometido_min, "base": "estimado"}


def escanear_items(base: Path, mapas: Sequence[Mapping[str, Any]], *, indice_en_paquete: bool) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    nivel_de = {m["nivel"] for m in mapas}
    for nv in NIVELES:
        if nv not in nivel_de:
            continue
        ruta = base / "entregables" / f"slowomapa-v1-{nv.lower()}.pdf"
        items.append({"id": f"slowomapa-{nv.lower()}", "tipo": "guia_pdf", "archivo": f"entregables/{ruta.name}", "paginas": paginas_pdf(ruta), "formato": "pdf", "en_paquete": True})
    ruta = base / "entregables" / "slowomapa-v1-indice.pdf"
    if ruta.is_file():
        items.append({"id": "slowomapa-indice", "tipo": "guia_pdf", "archivo": f"entregables/{ruta.name}", "paginas": paginas_pdf(ruta), "formato": "pdf", "en_paquete": indice_en_paquete})
    for f in sorted((base / "muestra" / "gratis").glob("*.pdf")):
        items.append({"id": f"gratis-{f.stem}", "tipo": "muestra", "archivo": f"muestra/gratis/{f.name}", "paginas": paginas_pdf(f), "formato": "pdf", "en_paquete": False})
    for f in sorted((base / "muestra").glob("muestra-*.png")):
        items.append({"id": f.stem, "tipo": "muestra", "archivo": f"muestra/{f.name}", "paginas": None, "formato": "png", "en_paquete": False})
    for it in items:
        it.update({"idioma": LOCALE, "sha256": "sha256:" + "0" * 64, "peso_mb": "0"})
    return items


def construir(base: Path, *, prometido_min: int, indice_en_paquete: bool = False) -> dict[str, Any]:
    from scripts.producto import empaquetar as E

    mapas = cargar_mapas(base / "entregables" / "fuente" / "mapas")
    plantilla = json.loads((base / "entregables" / "fuente" / "producto-base.json").read_text(encoding="utf-8"))
    entrada = dict(plantilla)
    entrada["items"] = escanear_items(base, mapas, indice_en_paquete=indice_en_paquete)
    entrada["tiempos"] = tiempos_desde_mapas(mapas, plantilla["pasos"], prometido_min=prometido_min)
    return E.empaquetar(entrada, base, prometido_min=prometido_min)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.producto.mapas.paquete")
    ap.add_argument("--base", required=True)
    ap.add_argument("--prometido-min", type=int, required=True)
    ap.add_argument("--salida")
    ap.add_argument("--indice-en-paquete", action="store_true")
    a = ap.parse_args(argv)
    res = construir(Path(a.base), prometido_min=a.prometido_min, indice_en_paquete=a.indice_en_paquete)
    texto = json.dumps(res["producto"], ensure_ascii=False, indent=2) + "\n"
    if a.salida:
        Path(a.salida).write_text(texto, encoding="utf-8")
    print(json.dumps({"producto_sha256": res["producto_sha256"], "items": len(res["producto"]["items"]), "total_min": res["producto"]["tiempos"]["total_min"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
