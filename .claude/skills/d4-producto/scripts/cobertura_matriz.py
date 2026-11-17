#!/usr/bin/env python3
"""L1-01 · L1-02 · L1-14 · Matriz «promesas ↔ entregables» en los dos sentidos, más reglas de la ficha EU.

Lee ``<oferta-dir>/03-oferta/oferta.json`` y ``<oferta-dir>/04-producto/producto.json`` (y los archivos de ``04-producto/``). Comprueba:
 1. Toda promesa de producto (``claims_permitidos`` cuya ``evidencia_ref`` apunta a ``04-producto/``), todo ``entregables[]``, todo ``bonus[]`` y el
    ``bump`` tiene una fila en ``matriz_promesas[]`` y un ítem existente (cruce por ``claim_id``/``promesa_id`` o por texto idéntico).
 2. Todo ítem ``en_paquete`` está referenciado por ≥ 1 fila (si no, es relleno: «tachar toda página que no mapee a una promesa»).
 3. Cada fila: ``entregable_id`` existe, ``estado`` = cumplida, ``prueba`` no vacía y, si cita un archivo, ese archivo existe.
 4. El bump es un ítem SEPARABLE (archivo propio, distinto del resto) y ninguno lleva servicio humano, comunidad, vivo, suscripción ni mantenimiento.
 5. ``idioma`` de cada ítem = ``oferta.locale``; ``tiempos.prometido_min`` = ``oferta.promesa.tiempo_prometido_min``.
 6. Bibliotecas de N: ``entregables[].cantidad`` = nº de líneas de ``04-producto/entregables/fuente/<id>-unidades.jsonl`` si existe.

Uso: python3 cobertura_matriz.py --oferta-dir ofertas/OF-AAAAMM-NN [--salida X]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun as c  # noqa: E402
import _patrones as pt  # noqa: E402


def norm(t: str) -> str:
    return c.normalizar_busqueda(t)


def servicios_en(texto: str, locale: str) -> list[str]:
    idi = pt.idioma(locale)
    pats = pt.compilar(pt.SERVICIO.get(idi, []) + pt.SERVICIO["en"])
    return [m.group(0) for rx in pats for m in rx.finditer(texto)]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--oferta-dir", required=True)
    ap.add_argument("--permitir-pendientes", action="store_true", help="etapa intermedia (paso 2 del SOP): una fila «pendiente»/«parcial» no falla; en la corrida final NO se usa")
    ap.add_argument("--salida")
    a = ap.parse_args(argv)
    d = Path(a.oferta_dir)
    try:
        oferta = c.cargar_json(d / "03-oferta" / "oferta.json")
        prod = c.cargar_json(d / "04-producto" / "producto.json")
    except (OSError, ValueError) as e:
        return c.error_uso(f"entrada inválida: {e}", 3)
    base = d / "04-producto"
    h: list[dict] = []
    locale = oferta["locale"]
    items = {i["id"]: i for i in prod["items"]}
    filas = prod["matriz_promesas"]
    filas_por_id = {f["promesa_id"]: f for f in filas}
    filas_por_texto = {norm(f["texto"]): f for f in filas}
    entregables_ref: set[str] = {f["entregable_id"] for f in filas}

    # 5. idioma y tiempo prometido
    for i in prod["items"]:
        if i["idioma"] != locale:
            h.append(c.hallazgo("L1-01", "BLOQUEANTE", f"ítem {i['id']}: idioma {i['idioma']} != oferta.locale {locale} (nunca se traduce el archivo de otro idioma: se produce de nuevo)", "producto.json#items"))
    if prod["tiempos"]["prometido_min"] != oferta["promesa"]["tiempo_prometido_min"]:
        h.append(c.hallazgo("L1-01", "BLOQUEANTE", "tiempos.prometido_min != oferta.promesa.tiempo_prometido_min", "producto.json#tiempos"))

    # 1a. promesas de la oferta -> fila de matriz
    promesas_producto = []
    for cl in oferta["promesa"]["claims_permitidos"]:
        if cl["evidencia_ref"].startswith("04-producto/"):
            promesas_producto.append(cl)
            fila = filas_por_id.get(cl["claim_id"]) or filas_por_texto.get(norm(cl["texto"]))
            if not fila:
                h.append(c.hallazgo("L1-02", "BLOQUEANTE", f"promesa «{cl['claim_id']}» (evidencia {cl['evidencia_ref']}) sin fila en matriz_promesas", "oferta.json#promesa.claims_permitidos", "promesa-sin-entregable"))
    # 1b. entregables, bonus, bump -> ítem y fila
    requeridos = [(e["id"], "entregable") for e in oferta["entregables"]] + [(b["id"], "bonus") for b in oferta["bonus"]]
    if oferta.get("bump"):
        requeridos.append((oferta["bump"]["id"], "bump"))
    for rid, tipo in requeridos:
        if rid not in items:
            h.append(c.hallazgo("L1-02", "BLOQUEANTE", f"{tipo} «{rid}» prometido en la oferta y sin ítem en producto.json (ítem prometido ausente)", "oferta.json", "item-prometido-ausente"))
        elif rid not in entregables_ref:
            h.append(c.hallazgo("L1-02", "MAYOR", f"{tipo} «{rid}» existe como ítem pero ninguna fila de la matriz lo prueba", "producto.json#matriz_promesas", "item-sin-prueba"))
    # 2. ítems en paquete sin promesa
    for iid, i in items.items():
        if i["en_paquete"] and iid not in entregables_ref:
            h.append(c.hallazgo("L1-02", "MAYOR", f"ítem en paquete «{iid}» no mapea a ninguna promesa (relleno o promesa omitida)", "producto.json#items", "item-sin-promesa"))
    # 3. filas
    for f in filas:
        if f["entregable_id"] not in items:
            h.append(c.hallazgo("L1-02", "BLOQUEANTE", f"fila «{f['promesa_id']}»: entregable_id «{f['entregable_id']}» no existe en items", "producto.json#matriz_promesas"))
        elif not (base / items[f["entregable_id"]]["archivo"]).is_file():
            h.append(c.hallazgo("L1-02", "BLOQUEANTE", f"fila «{f['promesa_id']}»: no existe el archivo {items[f['entregable_id']]['archivo']}", "producto.json#items"))
        if f["estado"] != "cumplida":
            h.append(c.hallazgo("L1-02", "MENOR" if a.permitir_pendientes else "MAYOR", f"fila «{f['promesa_id']}» en estado «{f['estado']}»: solo «cumplida» admite PASS", "producto.json#matriz_promesas"))
        for token in re.findall(r"[\w./-]+\.(?:md|pdf|html|xlsx|csv|json|docx|txt)", f["prueba"]):
            if not (list(base.rglob(Path(token).name))):
                h.append(c.hallazgo("L1-02", "MAYOR", f"fila «{f['promesa_id']}»: la prueba cita «{token}» y no existe en 04-producto/", "producto.json#matriz_promesas"))
        if not f["prueba"].strip():
            h.append(c.hallazgo("L1-02", "BLOQUEANTE", f"fila «{f['promesa_id']}» sin prueba", "producto.json#matriz_promesas"))
    # 4. bump separable y EU sin servicio
    if oferta.get("bump") and oferta["bump"]["id"] in items:
        b = items[oferta["bump"]["id"]]
        otros = {i["archivo"] for k, i in items.items() if k != b["id"]}
        if b["archivo"] in otros:
            h.append(c.hallazgo("L1-02", "MAYOR", "el bump comparte archivo con otro ítem: debe ser un ítem separable (BLIK, Bancontact, EPS y Pix no guardan tarjeta: el bump va pre-pago)", "producto.json#items", "bump-no-separable"))
    campos = [("bonus", b["descripcion"]) for b in oferta["bonus"]]
    if oferta.get("bump"):
        campos += [("bump", oferta["bump"]["nombre"]), ("bump", oferta["bump"]["descripcion"])]
    campos += [("entregables", f"{e['tipo']} {e['formato']}") for e in oferta["entregables"]]
    campos += [("matriz", f["texto"]) for f in filas]
    for origen, txt in campos:
        for m in servicios_en(txt, locale):
            h.append(c.hallazgo("L1-14", "BLOQUEANTE", f"«{m}» en {origen}: el entregable único no admite servicio humano, comunidad, vivo, suscripción ni mantenimiento continuo (devolver con motivo canónico requiere_servicio o requiere_comunidad_o_en_vivo)", f"oferta/producto:{origen}", "servicio-oculto"))
    # 6. bibliotecas
    unidades = {}
    for e in oferta["entregables"]:
        ruta = base / "entregables" / "fuente" / f"{e['id']}-unidades.jsonl"
        if ruta.is_file():
            n = len(c.cargar_jsonl(ruta))
            unidades[e["id"]] = n
            if n != e["cantidad"]:
                h.append(c.hallazgo("L1-02", "BLOQUEANTE", f"«{e['id']}»: prometidas {e['cantidad']} unidades y entregadas {n} (n_unidades prometido = entregado)", str(ruta.relative_to(d)), "n-unidades"))
        elif e["cantidad"] > 1 and e["tipo"].lower().startswith(("biblioteca", "pack", "recetario", "fichas")):
            h.append(c.hallazgo("L1-02", "MAYOR", f"«{e['id']}»: {e['cantidad']} unidades prometidas y no hay fuente/{e['id']}-unidades.jsonl para contarlas", "04-producto/entregables/fuente"))
    return c.emitir("cobertura_matriz", ["L1-01", "L1-02", "L1-14"], h, {
        "promesas_de_producto": len(promesas_producto), "filas_matriz": len(filas), "items": len(items),
        "items_en_paquete": sum(1 for i in items.values() if i["en_paquete"]), "unidades_contadas": unidades,
    }, a.salida)


if __name__ == "__main__":
    sys.exit(main())
