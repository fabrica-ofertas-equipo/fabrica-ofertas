#!/usr/bin/env python3
"""verificar_competidores.py — ¿`anuncios_competencia.json` trae competidores que el dueño pueda verificar en ≤ 15 min? (D2). v0.1.0.

Comprueba, sin red:
  * ≥ `competidores_verificables_min` competidores VERIFICABLES. Un competidor lo es si trae: `operador_id`, `page_id` (dígitos),
    ≥ 1 anuncio con `snapshot_url` = https://www.facebook.com/ads/library/?id=<id> (el id coincide con el del anuncio y, con --crudo,
    EXISTE en los crudos de la corrida: un enlace inventado no pasa), `promesa` y `mecanismo_declarado` no vacíos con su
    `tipo_mecanismo` M1-M8, `evidencia{id,url https,fecha,leido_por}` con `leido_por` ∈ {dueno, navegador_auto, maker_titulo},
    y `enlaces_verificacion` (ids de anuncio) entre 1 y `verificacion_enlaces_max_por_competidor`.
  * Costo de verificación del dueño = Σ enlaces_verificacion × `minutos_por_enlace_verificacion` ≤ `tiempo_verificacion_dueno_max_min`.
  * Todo claim de nivel rojo lleva `prohibido_copiar: true`. Ningún competidor sin lectura humana de snapshot presenta como `observado`
    un campo de texto de anuncio (sin snapshot leído los campos son `no_disponible`/`inferido`).
  * Sin PII (email, @handle, teléfono, URL en texto) en los campos de texto.
`leido_por = maker_titulo` significa que solo se vio el título del enlace del conector: el competidor cuenta como NO verificable para el
mínimo (promesa y mecanismo serían inferencias sin snapshot).

Uso:
  .venv/bin/python .claude/skills/d2-validacion/scripts/verificar_competidores.py ANUNCIOS_COMPETENCIA.json [--crudo CARPETA_CRUDO] [--parametros P.yaml]
Salida 0 correcto · 2 uso · 3 falla algún criterio · 5 falta un parámetro.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import params as P  # noqa: E402
import verificar_citas as VC  # noqa: E402

RX_SNAP = re.compile(r"^https://www\.facebook\.com/ads/library/\?id=(\d+)$")
RX_FECHA = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])(T\d{2}:\d{2}:\d{2}Z)?$")
LEIDO = ("dueno", "navegador_auto", "maker_titulo")
LEIDO_REAL = ("dueno", "navegador_auto")
MEC = tuple(f"M{i}" for i in range(1, 9))
REQUERIDOS = ["competidores_verificables_min", "tiempo_verificacion_dueno_max_min", "minutos_por_enlace_verificacion",
              "verificacion_enlaces_max_por_competidor"]


def ids_de_crudo(carpeta: Path) -> set[str]:
    ids: set[str] = set()
    for r in sorted(carpeta.glob("*.json")):
        if r.name.endswith(".error.json"):
            continue
        for a in json.loads(r.read_text(encoding="utf-8")).get("ads", []):
            ids.add(str(a.get("id")))
    return ids


def _textos(o) -> list[str]:
    return VC._textos(o)


def verificar(doc: dict, p: dict, ids_crudo: set[str] | None = None) -> dict:
    P.exigir(p, REQUERIDOS)
    comps = doc.get("competidores")
    if not isinstance(comps, list):
        raise P.ErrorValidacion("anuncios_competencia.json: falta `competidores` (lista)")
    fallas: list[dict] = []
    n_ok = 0
    enlaces_total = 0
    max_enl = int(p["verificacion_enlaces_max_por_competidor"])
    resumen = []
    for i, c in enumerate(comps):
        oid = c.get("operador_id") or f"competidores[{i}]"
        problemas: list[str] = []
        if not (isinstance(c.get("page_id"), str) and c["page_id"].isdigit()):
            problemas.append("page_id_ausente_o_no_numerico")
        anuncios = c.get("anuncios") or []
        por_id = {}
        for a in anuncios:
            m = RX_SNAP.match(a.get("snapshot_url") or "")
            if not m or m.group(1) != str(a.get("id")):
                problemas.append(f"snapshot_url_invalida_o_no_coincide_con_id:{a.get('id')}")
                continue
            if ids_crudo is not None and str(a["id"]) not in ids_crudo:
                problemas.append(f"anuncio_{a['id']}_NO_esta_en_el_crudo (enlace inventado)")
                continue
            por_id[str(a["id"])] = a
        if not por_id:
            problemas.append("sin_anuncios_con_snapshot_valido")
        promesas = [a for a in por_id.values() if (a.get("promesa") or "").strip()]
        if not promesas:
            problemas.append("sin_promesa")
        mecs = [a for a in por_id.values() if (a.get("mecanismo_declarado") or "").strip() and a.get("tipo_mecanismo") in MEC]
        if not mecs:
            problemas.append("sin_mecanismo_declarado_con_tipo_M1_M8")
        ev_ok = False
        leido_real = False
        for a in por_id.values():
            e = a.get("evidencia") or {}
            if (isinstance(e.get("url"), str) and e["url"].startswith("https://") and isinstance(e.get("fecha"), str)
                    and RX_FECHA.match(e["fecha"]) and e.get("id") and e.get("leido_por") in LEIDO):
                ev_ok = True
                leido_real = leido_real or e["leido_por"] in LEIDO_REAL
        if not ev_ok:
            problemas.append("evidencia_sin_url_fecha_o_leido_por")
        enl = c.get("enlaces_verificacion") or []
        if not (1 <= len(enl) <= max_enl) or any(str(x) not in por_id for x in enl):
            problemas.append(f"enlaces_verificacion_fuera_de_1_a_{max_enl}_o_no_son_de_sus_anuncios")
        for a in por_id.values():
            for cl in a.get("claims") or []:
                if cl.get("nivel_riesgo") == "rojo" and cl.get("prohibido_copiar") is not True:
                    problemas.append(f"claim_rojo_sin_prohibido_copiar:{a['id']}")
            if not leido_real:
                for campo in ("hook", "promesa", "mecanismo_declarado"):
                    if (a.get("estado_campos") or {}).get(campo) == "observado":
                        problemas.append(f"campo_{campo}_observado_sin_snapshot_leido:{a['id']}")
        libres = [c.get("motivo_clustering"), (c.get("oferta") or {}).get("entregables"), (c.get("oferta") or {}).get("garantia"),
                  (c.get("oferta") or {}).get("bump")]
        for a in anuncios:
            libres += [a.get(k) for k in ("hook", "promesa", "mecanismo_declarado", "prueba_social", "cta", "garantia")]
            libres += [cl.get("texto_parafraseado") for cl in a.get("claims") or []]
        for t in [x for x in libres if isinstance(x, str)]:  # solo texto libre: ids, URLs y page_id no son PII
            for pi in VC.pii_en(t):
                problemas.append(f"PII:{pi}")
        verificable = not problemas and leido_real
        if not leido_real and not problemas:
            problemas.append("solo_titulo_del_conector (leido_por=maker_titulo): no cuenta como verificable")
        if verificable:
            n_ok += 1
            enlaces_total += len(enl)
        resumen.append({"operador_id": oid, "verificable": verificable, "enlaces_verificacion": len(enl), "problemas": sorted(set(problemas))})
        for pr in sorted(set(problemas)):
            fallas.append({"operador_id": oid, "problema": pr})
    minutos = enlaces_total * int(p["minutos_por_enlace_verificacion"])
    gating = []
    if n_ok < int(p["competidores_verificables_min"]):
        gating.append(f"{n_ok} competidor(es) verificable(s) < mínimo {p['competidores_verificables_min']}")
    if minutos > int(p["tiempo_verificacion_dueno_max_min"]):
        gating.append(f"verificar cuesta ~{minutos} min > {p['tiempo_verificacion_dueno_max_min']} min: baja enlaces_verificacion")
    if any(f["problema"].startswith("PII") or "NO_esta_en_el_crudo" in f["problema"] for f in fallas):
        gating.append("PII o enlace inventado")
    return {"n_competidores": len(comps), "n_verificables": n_ok, "enlaces_a_verificar": enlaces_total,
            "minutos_estimados_dueno": minutos, "competidores": resumen, "falla": gating}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("anuncios_competencia")
    ap.add_argument("--crudo", help="carpeta de crudo de la corrida (comprueba que cada enlace exista en lo capturado)")
    ap.add_argument("--parametros")
    a = ap.parse_args(argv)
    try:
        doc = json.load(open(a.anuncios_competencia, encoding="utf-8"))
        ids = ids_de_crudo(Path(a.crudo)) if a.crudo else None
        valores, _ = P.cargar(Path(a.parametros) if a.parametros else None)
        out = verificar(doc, valores, ids)
    except P.ErrorD2 as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return ex.codigo
    except (OSError, json.JSONDecodeError) as ex:
        print(f"ERROR: {ex}", file=sys.stderr)
        return 2
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 3 if out["falla"] else 0


if __name__ == "__main__":
    sys.exit(main())
