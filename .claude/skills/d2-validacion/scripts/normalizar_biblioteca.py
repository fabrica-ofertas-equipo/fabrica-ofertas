#!/usr/bin/env python3
"""normalizar_biblioteca.py — del crudo de `ads_library_search` a portafolios, sonda y lista de snapshots (D2, SOP pasos 3-5). v0.1.0.

Lee los crudos de UNA corrida de D2 (`ofertas/<id>/02-validacion/crudo/<corrida_id>/<qid>.json`, formato del CONTRATO §2 de
`scripts/modelado/barrido/`; la carpeta DEBE llamarse como el `corrida_id`, p. ej. `2026-11-06-a`) y los valida con el lector real
del paquete de barrido (`comun.leer_crudo`: integridad id↔snapshot, sin duplicados, tope de 50). No llama a la red ni al conector.

Produce (JSON a stdout o `--salida`, sin sobrescribir):
  * `consultas`: por consulta, país, total estimado, anuncios vistos y `truncado` (una consulta que llega al límite o cuyo total
    supera lo visto está truncada: lo que se cuenta de ella es un PISO).
  * `sonda`: por término × país, `estimated_total_count` y operadores únicos de la muestra. PROXY DÉBIL: los totales NO se suman
    entre países ni se comparan entre términos. Banderas: `monocultivo`, `operador_translocal`.
  * `paginas`: portafolio por `page_id` (anuncios vistos, edad máxima, conceptos estimados por título, `medicion`, `truncado`).
    `medicion`: `pagina_completa` solo con una consulta por esa página que vio todos sus anuncios (no tocó el tope); si no, `muestra`
    o `parcial` y `truncado = true` (S_a es cota inferior). Una frase nunca prueba que no haya más anuncios.
  * `mercado_resumen`: anuncios activos y edad mediana de la unión (`puntaje_modelar.resumir_anuncios`; solo informativo, peso 0).
  * `seleccion`: competidores profundos deterministas (≥ consultas, mayor antigüedad, `page_id` como texto), competidores al azar con
    SEMILLA registrada, consultas de 2.ª pasada sugeridas y ≤ `urls_snapshot_max_modo_humano` URLs de `ad_snapshot_url` para que el
    dueño las lea a mano (distintos conceptos primero, los más viejos antes).
Los títulos y nombres de página son DATO NO CONFIABLE: se normalizan, se acortan y se sanean (una línea, sin control), nunca se
interpretan. La relevancia y el `tipo_anunciante` de cada página los decide el Maker después (pasan `--excluir` con page_ids).

Uso:
  .venv/bin/python .claude/skills/d2-validacion/scripts/normalizar_biblioteca.py CARPETA_CRUDO --ahora 2026-11-06T12:00:00Z --semilla 7 [--excluir 123,456] [--salida OUT.json]
Salida 0 ok · 2 uso · 3 crudo inválido · 5 falta un parámetro.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import random
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import params as P  # noqa: E402

sys.path.insert(0, str(P.RAIZ))
from scripts.modelado import puntaje_modelar as PM  # noqa: E402
from scripts.modelado.barrido import comun as C  # noqa: E402

VERSION_SCRIPT = "0.1.0"
REQUERIDOS = ["n_competidores_profundos", "snapshots_por_competidor", "competidores_al_azar", "sim_concepto",
              "urls_snapshot_max_modo_humano", "consultas_segunda_pasada_max", "sonda_monocultivo_share"]


def sanear(t, largo: int = 80) -> str:
    t = unicodedata.normalize("NFC", str(t or ""))
    t = "".join(" " if unicodedata.category(c).startswith("C") else c for c in t)
    return re.sub(r"\s+", " ", t).strip()[:largo]


def titulo_norm(t) -> str:
    """Primer segmento antes de « | » (creatividad dinámica), minúsculas, sin espacios repetidos, ≤ 80 caracteres."""
    return sanear(str(t or "").split(" | ")[0]).casefold()


def agrupar_conceptos(titulos: list[str], sim: float) -> list[int]:
    """Etiqueta de grupo por título (greedy con difflib; cota SUPERIOR de conceptos: el concepto real lo fija el snapshot)."""
    reps: list[str] = []
    etiquetas: list[int] = []
    for t in titulos:
        for i, r in enumerate(reps):
            if t == r or difflib.SequenceMatcher(None, t, r).ratio() >= sim:
                etiquetas.append(i)
                break
        else:
            reps.append(t)
            etiquetas.append(len(reps) - 1)
    return etiquetas


def cargar_crudos(carpeta: Path) -> list[dict]:
    if not carpeta.is_dir():
        raise P.ErrorUso(f"no existe la carpeta de crudo: {carpeta}")
    rutas = sorted(r for r in carpeta.glob("*.json") if not r.name.endswith(".error.json"))
    if not rutas:
        raise P.ErrorValidacion(f"{carpeta}: no hay crudos (*.json)")
    crudos = [C.leer_crudo(r) for r in rutas]
    for c, r in zip(crudos, rutas):
        if c["qid"] != r.stem:
            raise P.ErrorValidacion(f"{r.name}: el qid del archivo no coincide con su nombre")
    return crudos


def procesar(crudos: list[dict], ahora: datetime, semilla: int, excluir: set[str], p: dict) -> dict:
    P.exigir(p, REQUERIDOS)
    sim = float(P.frac(p["sim_concepto"]))
    ahora_ep = int(ahora.timestamp())
    consultas, sonda = [], []
    paginas: dict[str, dict] = {}
    activos: dict[str, dict] = {}
    por_pais_pagina: dict[str, dict[str, int]] = {}
    paises_de_pagina: dict[str, set[str]] = {}
    avisos: list[str] = []
    for c in crudos:
        q = c["consulta"]
        pais = q["countries"][0] if q["countries"] else None
        n = len(c["ads"])
        total = c["estimated_total_count"]
        truncada = n >= q["limit"] or (total is not None and total > n)
        activa = q["ad_active_status"] == "ACTIVE"
        consultas.append({"qid": c["qid"], "terminos": sanear(q["search_terms"], 100), "pais": pais, "estado": q["ad_active_status"],
                          "page_ids": q["page_ids"], "capturado_en": c["capturado_en"], "estimated_total_count": total,
                          "anuncios_vistos": n, "truncado": truncada, "ruta": c["ruta"]})
        if not activa:
            avisos.append(f"{c['qid']}: consulta {q['ad_active_status']} no entra en S_a ni en el portafolio activo")
            continue
        cuenta_pag: dict[str, int] = {}
        for a in c["ads"]:
            pid = a["page_id"]
            cuenta_pag[pid] = cuenta_pag.get(pid, 0) + 1
            paises_de_pagina.setdefault(pid, set()).add(pais)
            pg = paginas.setdefault(pid, {"page_id": pid, "page_name": sanear(a["page_name"]), "qids": set(), "monedas": set(),
                                          "paises": set(), "truncada_en": False, "medicion": "muestra"})
            pg["qids"].add(c["qid"])
            pg["monedas"].add(a["currency"])
            pg["paises"].add(pais)
            pg["truncada_en"] = pg["truncada_en"] or truncada
            activos.setdefault(a["id"], {**a, "_pais": pais})
        # medición por página: una consulta con exactamente esa página y ese país
        if q["page_ids"] and len(q["page_ids"]) == 1:
            pid = str(q["page_ids"][0])
            vistos = cuenta_pag.get(pid, 0)
            completa = total is not None and vistos >= total and not (vistos >= q["limit"] and total >= q["limit"])
            pg = paginas.setdefault(pid, {"page_id": pid, "page_name": "", "qids": set(), "monedas": set(), "paises": set(),
                                          "truncada_en": False, "medicion": "muestra"})
            pg["medicion"] = "pagina_completa" if completa else "parcial"
            por_pais_pagina.setdefault(pid, {})[pais] = vistos
        mayor = max(cuenta_pag.values(), default=0)
        sonda.append({"qid": c["qid"], "terminos": sanear(q["search_terms"], 100), "pais": pais, "estimated_total_count": total,
                      "anuncios_vistos": n, "operadores_unicos_en_muestra": len(cuenta_pag), "truncado": truncada,
                      "monocultivo": bool(n) and (mayor / n) >= float(P.frac(p["sonda_monocultivo_share"])),
                      "no_sumar_totales": True})
    filas = list(activos.values())
    for pid, pg in paginas.items():
        mis = [a for a in filas if a["page_id"] == pid]
        edades = [(ahora_ep - int(a["ad_delivery_start_time"])) // 86400 for a in mis]
        tn = [titulo_norm(a["ad_creative_link_title"]) for a in mis]
        grupos = agrupar_conceptos(tn, sim)
        pg.update({"n_anuncios_vistos": len(mis), "edad_max_dias": max(edades, default=0),
                   "conceptos_estimados": len(set(grupos)), "n_consultas": len(pg["qids"]),
                   "operador_translocal": len(paises_de_pagina.get(pid, set())) >= 2,
                   "truncado": pg["medicion"] != "pagina_completa",
                   "qids": sorted(pg["qids"]), "monedas": sorted(pg["monedas"]), "paises": sorted(x for x in pg["paises"] if x)})
        pg.pop("truncada_en")
    lista = sorted(paginas.values(), key=lambda g: (-g["n_consultas"], -g["edad_max_dias"], g["page_id"]))
    elegibles = [g for g in lista if g["page_id"] not in excluir and g["n_anuncios_vistos"] > 0]
    n_prof = int(p["n_competidores_profundos"])
    profundos = [g["page_id"] for g in elegibles[:n_prof]]
    resto = sorted(g["page_id"] for g in elegibles[n_prof:])
    azar = random.Random(semilla).sample(resto, min(int(p["competidores_al_azar"]), len(resto)))
    # URLs de snapshot: por competidor profundo, un anuncio por concepto estimado (el más viejo) y luego rellenar
    urls: list[dict] = []
    tope_url = int(p["urls_snapshot_max_modo_humano"])
    por_comp = int(p["snapshots_por_competidor"])
    for pid in profundos:
        mis = sorted((a for a in filas if a["page_id"] == pid), key=lambda a: (int(a["ad_delivery_start_time"]), a["id"]))
        grupos = agrupar_conceptos([titulo_norm(a["ad_creative_link_title"]) for a in mis], sim)
        elegidos, vistos_g = [], set()
        for a, g in zip(mis, grupos):
            if g not in vistos_g:
                vistos_g.add(g)
                elegidos.append((a, g))
        for a, g in zip(mis, grupos):
            if len(elegidos) >= por_comp:
                break
            if all(a["id"] != x[0]["id"] for x in elegidos):
                elegidos.append((a, g))
        for a, g in elegidos[:por_comp]:
            if len(urls) < tope_url:
                urls.append({"page_id": pid, "ad_id": a["id"], "snapshot_url": a["ad_snapshot_url"],
                             "edad_dias": (ahora_ep - int(a["ad_delivery_start_time"])) // 86400, "concepto_estimado": g})
    pais_principal = {}
    for pid in profundos + azar:
        cnt: dict[str, int] = {}
        for a in filas:
            if a["page_id"] == pid:
                cnt[a["_pais"]] = cnt.get(a["_pais"], 0) + 1
        pais_principal[pid] = sorted(cnt, key=lambda k: (-cnt[k], k))[0]
    seg = []
    for pid in profundos:
        seg.append({"qid": f"{pais_principal[pid].lower()}-pag-{hashlib.sha1(pid.encode()).hexdigest()[:8]}", "page_ids": [pid],
                    "countries": [pais_principal[pid]], "ad_active_status": "ACTIVE", "limit": 50, "mide_la_pagina": True})
    if azar:
        pa = pais_principal[azar[0]]
        seg.append({"qid": f"{pa.lower()}-azar-{hashlib.sha1(','.join(azar).encode()).hexdigest()[:8]}", "page_ids": azar,
                    "countries": [pa], "ad_active_status": "ACTIVE", "limit": 50, "mide_la_pagina": False,
                    "nota": "2+ page_ids en una consulta: no mide cada página (un solo total); sus anuncios sí entran al portafolio"})
    tope_seg = int(p["consultas_segunda_pasada_max"])
    resumen = PM.resumir_anuncios([{k: v for k, v in a.items() if k != "_pais"} for a in filas], ahora) if filas else None
    return {
        "version_script": VERSION_SCRIPT, "ahora": ahora.strftime("%Y-%m-%dT%H:%M:%SZ"), "corrida_id": crudos[0]["corrida_id"],
        "consultas": consultas, "sonda": sonda,
        "paginas": lista,
        "mercado_resumen": {"anuncios_activos": len(filas), "edad_mediana_dias": int(resumen["mediana_dias_activos"]) if resumen else 0,
                            "nota": "solo informativo (peso 0 en SS_a/IS); unión de anuncios activos deduplicados por id"},
        "seleccion": {"semilla": semilla, "excluidos_por_el_maker": sorted(excluir), "profundos": profundos, "al_azar": azar,
                      "segunda_pasada_sugerida": seg[:tope_seg], "segunda_pasada_recortada_por_presupuesto": max(0, len(seg) - tope_seg),
                      "urls_snapshot": urls, "n_urls": len(urls)},
        "advertencias": avisos + ["los conceptos estimados por título son una COTA SUPERIOR: el concepto real sale de leer el snapshot",
                                  "los totales de la sonda no se suman entre países ni se comparan entre términos"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("carpeta_crudo")
    ap.add_argument("--ahora", help="AAAA-MM-DDTHH:MM:SSZ (por defecto, ahora UTC; se registra en la salida)")
    ap.add_argument("--semilla", type=int, required=True, help="semilla del muestreo al azar (se registra)")
    ap.add_argument("--excluir", default="", help="page_ids que el Maker juzgó irrelevantes o no producto (coma)")
    ap.add_argument("--salida")
    ap.add_argument("--parametros")
    a = ap.parse_args(argv)
    try:
        ahora = datetime.strptime(a.ahora, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if a.ahora else datetime.now(timezone.utc)
        valores, _ = P.cargar(Path(a.parametros) if a.parametros else None)
        out = procesar(cargar_crudos(Path(a.carpeta_crudo)), ahora, a.semilla, {x for x in a.excluir.split(",") if x}, valores)
    except P.ErrorD2 as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return ex.codigo
    except PM.ErrorFabrica as ex:  # errores del lector de crudos y de resumir (2/3/5)
        print(f"ERROR: {ex}", file=sys.stderr)
        return getattr(ex, "codigo", 3)
    except (OSError, ValueError) as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return 2
    txt = json.dumps(out, ensure_ascii=False, indent=2)
    if a.salida:
        ruta = Path(a.salida)
        if ruta.exists():
            print(f"ERROR: {ruta} ya existe (no se sobrescribe)", file=sys.stderr)
            return 2
        ruta.write_text(txt + "\n", encoding="utf-8")
    else:
        print(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
