"""CLI del pipeline de mapas: validar → QA de idioma → render por lotes → OCR → muestra → estado por mapa.

    .venv/bin/python -m scripts.producto.mapas.lote validar --mapas DIR [--temario T]
    .venv/bin/python -m scripts.producto.mapas.lote qa      --mapas DIR [--excepciones F] [--salida qa.json]
    .venv/bin/python -m scripts.producto.mapas.lote render  --mapas DIR --temario T --salida CARPETA [--niveles A1,B2] [--por-mapa] [--indice] [--borrador] [--sobrescribir]
    .venv/bin/python -m scripts.producto.mapas.lote ocr     --mapas DIR --salida CARPETA_PDF --reporte ocr.json
    .venv/bin/python -m scripts.producto.mapas.lote muestra --mapas DIR --temario T --salida CARPETA --gratis id1,id2,... --principal id1,id2,id3
    .venv/bin/python -m scripts.producto.mapas.lote estado  --mapas DIR --temario T --qa-dir DIR --salida estado.json

Todo offline: ninguna llamada de red ni gasto. Salida: 0 ok · 1 con hallazgos bloqueantes · 2 uso.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.producto.mapas import duplicados, qa_idioma, render as R, revision_ciega as RC
from scripts.producto.mapas.esquema import NIVELES, REPARTO, cargar_dir, hay_bloqueo, validar_mapa
from scripts.producto.mapas.temario import cargar as cargar_temario, validar_temario

NOMBRE_NIVEL_ARCHIVO = "slowomapa-v1-{nivel}.pdf"
NOMBRE_INDICE = "slowomapa-v1-indice.pdf"


def cargar_mapas(carpeta: str | Path) -> list[dict[str, Any]]:
    return [m for _, m in cargar_dir(carpeta)]


def por_nivel(mapas: Sequence[Mapping[str, Any]]) -> dict[str, list[Mapping[str, Any]]]:
    d: dict[str, list[Mapping[str, Any]]] = {n: [] for n in NIVELES}
    for m in sorted(mapas, key=lambda x: (NIVELES.index(x["nivel"]), x["numero"])):
        d[m["nivel"]].append(m)
    return d


def validar_lote(mapas: Sequence[Mapping[str, Any]], temario: Mapping[str, Any] | None) -> dict[str, list[dict[str, str]]]:
    return {m["mapa_id"]: validar_mapa(m, temario=temario) for m in mapas}


def render_lote(mapas: Sequence[Mapping[str, Any]], temario: Mapping[str, Any], salida: Path, *, niveles: Sequence[str] | None = None,
                por_mapa: bool = False, indice: bool = False, borrador: bool = True, sobrescribir: bool = False, trabajo: Path | None = None) -> dict[str, Any]:
    """PDF por nivel (portada del nivel + hojas), PDF por mapa (opcional) y PDF de portada/índice (opcional). Devuelve lo producido con su tiempo."""
    salida.mkdir(parents=True, exist_ok=True)
    escritos = {m["mapa_id"] for m in mapas}
    agrupados = por_nivel(mapas)
    tit = R.titulos_de(temario)
    layout = R.elegir_densidades(mapas, titulos=tit)  # primera densidad con la que cabe cada hoja (d0, d1, d2)
    dens = {i: v["densidad"] for i, v in layout.items()}
    res: dict[str, Any] = {"niveles": {}, "mapas": {}, "indice": None, "layout": layout}
    nombres, paginas = {}, {}
    for nv in NIVELES:
        ms = agrupados[nv]
        if (niveles and nv not in niveles) or not ms:
            continue
        nombres[nv] = NOMBRE_NIVEL_ARCHIVO.format(nivel=nv.lower())
        paginas[nv] = len(ms) + 1
        res["niveles"][nv] = R.renderizar_pdf(R.html_nivel(ms, nv, temario, escritos, borrador=borrador, densidades=dens), salida / nombres[nv], trabajo=trabajo, sobrescribir=sobrescribir)
        res["niveles"][nv]["mapas"] = [m["mapa_id"] for m in ms]
    if por_mapa:
        pdfs = salida / "pdf-mapas"
        pdfs.mkdir(exist_ok=True)
        for nv, ms in agrupados.items():
            if niveles and nv not in niveles:
                continue
            for m in ms:
                doc = R.documento(m["tema"]["pl"], R.html_pagina(m, total_nivel=temario["niveles"][nv]["n"], titulos=tit, densidad=dens[m["mapa_id"]]))
                res["mapas"][m["mapa_id"]] = R.renderizar_pdf(doc, pdfs / f"{m['mapa_id']}.pdf", trabajo=trabajo, sobrescribir=sobrescribir)
    if indice:
        nombres_todos = {nv: NOMBRE_NIVEL_ARCHIVO.format(nivel=nv.lower()) for nv in NIVELES}
        pag_todas = {nv: (len(agrupados[nv]) + 1 if agrupados[nv] else 0) for nv in NIVELES}
        res["indice"] = R.renderizar_pdf(R.html_indice(temario, escritos, nombres_todos, pag_todas, borrador=borrador), salida / NOMBRE_INDICE, trabajo=trabajo, sobrescribir=sobrescribir)
    return res


def estado_por_mapa(mapas: Sequence[Mapping[str, Any]], temario: Mapping[str, Any] | None, qa_dir: Path, *, ocr: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Criterio de aceptación por mapa: esquema + QA automático + revisión ciega (la última ronda disponible) [+ OCR]."""
    v = validar_lote(mapas, temario)
    capas = qa_idioma.ejecutar_capas(mapas)
    informes = []
    for f in sorted(qa_dir.glob("revision_ciega-ronda*.json")):
        informes.append((f.stem.split("ronda")[-1], json.loads(f.read_text(encoding="utf-8"))))
    ultima: dict[str, dict[str, Any]] = {}
    for ronda, inf in informes:
        for m in inf["mapas"]:
            d = RC.decidir(m)
            d["ronda"] = int(ronda)
            ultima[m["mapa_id"]] = d
    out: dict[str, Any] = {}
    dup_ids = {i for h in capas["lote"] if h["severidad"] in ("BLOQUEANTE", "MAYOR") for i in h["campo"].split(",")}
    for m in mapas:
        mid = m["mapa_id"]
        esq = hay_bloqueo(v[mid])
        auto = [h for h in capas["por_mapa"].get(mid, []) if h["severidad"] in ("BLOQUEANTE", "MAYOR")]
        ciega = ultima.get(mid)
        pend = []
        if esq:
            pend.append("esquema")
        if auto or mid in dup_ids or not capas["ortografia"].get("ejecutada"):
            pend.append("qa_automatico")
        if ciega is None:
            pend.append("revision_ciega_sin_hacer")
        elif not ciega["aceptado"]:
            pend.append("revision_ciega_devuelto")
        if ocr is not None and not ocr.get(mid, {}).get("ok", False):
            pend.append("ocr_pdf")
        out[mid] = {"esquema_ok": not esq, "qa_automatico_ok": not (auto or mid in dup_ids), "revision_ciega": ciega, "ocr_ok": None if ocr is None else ocr.get(mid, {}).get("ok", False),
                    "estado": "aceptado" if not pend else "pendiente", "pendiente_de": pend}
    return out


def _principal(argv: list[str] | None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.producto.mapas.lote")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nombre in ("validar", "qa", "render", "ocr", "muestra", "estado"):
        p = sub.add_parser(nombre)
        p.add_argument("--mapas", required=True)
        p.add_argument("--temario")
        p.add_argument("--salida")
        p.add_argument("--excepciones")
        p.add_argument("--niveles")
        p.add_argument("--por-mapa", action="store_true")
        p.add_argument("--indice", action="store_true")
        p.add_argument("--borrador", action="store_true")
        p.add_argument("--sobrescribir", action="store_true")
        p.add_argument("--gratis")
        p.add_argument("--principal")
        p.add_argument("--qa-dir")
        p.add_argument("--reporte")
    a = ap.parse_args(argv)
    mapas = cargar_mapas(a.mapas)
    tem = cargar_temario(a.temario) if a.temario else None
    if a.cmd == "validar":
        v = validar_lote(mapas, tem)
        malo = False
        for mid, hs in v.items():
            for h in hs:
                print(f"[{h['severidad']}] {mid} · {h['codigo']} · {h['campo']}: {h['mensaje']}")
            malo = malo or hay_bloqueo(hs)
        dup = duplicados.informe(mapas)
        for h in dup:
            print(f"[{h['severidad']}] LOTE · {h['codigo']}: {h['mensaje']}")
        malo = malo or any(h["severidad"] in ("BLOQUEANTE", "MAYOR") for h in dup)
        if tem:
            for h in validar_temario(tem):
                print(f"[{h['severidad']}] TEMARIO · {h['codigo']}: {h['mensaje']}")
        print(f"{len(mapas)} mapas · {'CON BLOQUEOS' if malo else 'sin bloqueos'}")
        return 1 if malo else 0
    if a.cmd == "qa":
        exc = json.loads(Path(a.excepciones).read_text(encoding="utf-8")) if a.excepciones else {}
        res = qa_idioma.ejecutar_capas(mapas, excepciones=exc)
        if a.salida:
            Path(a.salida).write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        for mid, hs in sorted(res["por_mapa"].items()):
            for h in hs:
                print(f"[{h['severidad']}] {mid} · {h['codigo']} · {h['campo']}: {h['mensaje']}")
        return 1 if qa_idioma.hay_bloqueo(res) else 0
    if a.cmd == "render":
        if not tem or not a.salida:
            print("render necesita --temario y --salida", file=sys.stderr)
            return 2
        res = render_lote(mapas, tem, Path(a.salida), niveles=a.niveles.split(",") if a.niveles else None, por_mapa=a.por_mapa, indice=a.indice,
                          borrador=a.borrador, sobrescribir=a.sobrescribir)
        resumen = {"niveles": {n: {"pdf": x["pdf"], "paginas": x["paginas"], "segundos": x["segundos"]} for n, x in res["niveles"].items()},
                   "mapas": {n: {"pdf": x["pdf"], "paginas": x["paginas"], "segundos": x["segundos"]} for n, x in res["mapas"].items()},
                   "layout": {i: {"densidad": v["densidad"], "ok": v["ok"]} for i, v in res["layout"].items()},
                   "indice": ({"pdf": res["indice"]["pdf"], "paginas": res["indice"]["paginas"], "segundos": res["indice"]["segundos"]} if res["indice"] else None)}
        print(json.dumps(resumen, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "muestra":
        if not tem or not a.salida:
            print("muestra necesita --temario y --salida", file=sys.stderr)
            return 2
        sal = Path(a.salida)
        sal.mkdir(parents=True, exist_ok=True)
        tit = R.titulos_de(tem)
        dens = {i: v["densidad"] for i, v in R.elegir_densidades(mapas, titulos=tit).items()}
        por_id = {m["mapa_id"]: m for m in mapas}
        agr = por_nivel(mapas)
        hechos = []
        for i, nv in enumerate(NIVELES, 1):
            if agr[nv]:
                hechos.append(R.png_miniatura(agr[nv][0], sal / f"muestra-{i}.png", titulos=tit, densidad=dens[agr[nv][0]["mapa_id"]]))
        if a.principal:
            hechos.append(R.png_principal([por_id[x] for x in a.principal.split(",")], sal / "muestra-principal.png", titulos=tit, densidades=dens))
        print(json.dumps(hechos, ensure_ascii=False, indent=1))
        return 0
    if a.cmd == "estado":
        if not a.qa_dir or not a.salida:
            print("estado necesita --qa-dir y --salida", file=sys.stderr)
            return 2
        ocr = None
        if a.reporte and Path(a.reporte).is_file():
            rep = json.loads(Path(a.reporte).read_text(encoding="utf-8"))
            ocr = {p["mapa_id"]: p for pdf in rep["pdfs"] for p in pdf["paginas"]}
        est = estado_por_mapa(mapas, tem, Path(a.qa_dir), ocr=ocr)
        Path(a.salida).write_text(json.dumps(est, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        n_ok = sum(1 for e in est.values() if e["estado"] == "aceptado")
        print(f"{n_ok} de {len(est)} mapas aceptados")
        return 0
    if a.cmd == "ocr":
        from scripts.producto.mapas import ocr as O

        if not a.salida:
            print("ocr necesita --salida (carpeta de PDF de nivel)", file=sys.stderr)
            return 2
        rep: dict[str, Any] = {"pdfs": []}
        for nv, ms in por_nivel(mapas).items():
            pdf = Path(a.salida) / NOMBRE_NIVEL_ARCHIVO.format(nivel=nv.lower())
            if ms and pdf.is_file():
                rep["pdfs"].append(O.verificar_pdf(pdf, ms, paginas_previas=1))
        if a.reporte:
            Path(a.reporte).write_text(json.dumps(rep, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        for r in rep["pdfs"]:
            print(r["pdf"], json.dumps(r["resumen"], ensure_ascii=False))
        return 0 if all(r["resumen"]["ok_capa"] for r in rep["pdfs"]) else 1
    return 2


def main(argv: list[str] | None = None) -> int:
    return _principal(argv)


if __name__ == "__main__":
    sys.exit(main())
