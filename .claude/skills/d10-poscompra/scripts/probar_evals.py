#!/usr/bin/env python3
"""Ejecuta los evals automatizables de la skill d10-poscompra (sin red, sin claves). Desde la raíz del repositorio:

    .venv/bin/python .claude/skills/d10-poscompra/scripts/probar_evals.py [--json]

Los casos con ``"capa": "script"`` (y la parte determinista de D02) se ejecutan aquí contra ``d10.py``; los ``"capa": "qa-l3"`` los juzga el agente ``d10-qa`` con ``rubric.md`` y aquí solo
se listan. Código de salida 0 si todo lo automatizable pasa, 3 si alguno falla.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Callable

AQUI = Path(__file__).resolve().parent
SKILL = AQUI.parent


def _cargar_d10():
    spec = importlib.util.spec_from_file_location("d10_skill", AQUI / "d10.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["d10_skill"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


d10 = _cargar_d10()


def cargar_casos() -> list[dict[str, Any]]:
    casos: list[dict[str, Any]] = []
    for ruta in sorted((SKILL / "evals" / "dorados").glob("D*.json")):
        casos.append(json.loads(ruta.read_text(encoding="utf-8")))
    casos += json.loads((SKILL / "evals" / "sembrados" / "sembrados.json").read_text(encoding="utf-8"))["casos"]
    return casos


def _leer(rel: str) -> str:
    return (SKILL / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------------------------------------------------------------
def _c_plan_entrega(caso: dict[str, Any]) -> list[str]:
    e, fallos = caso["entrada"], []
    for sub in e["casos"]:
        res = d10.plan_entrega(e["oferta"], e["producto"], sub["lineas_pagadas"])
        if {x["id"] for x in res["entregar"]} != set(sub["entregar_ids"]):
            fallos.append(f"líneas {sub['lineas_pagadas']}: entrega {sorted(x['id'] for x in res['entregar'])} ≠ {sorted(sub['entregar_ids'])}")
        if {x["id"] for x in res["no_entregar"]} != set(sub["no_entregar_ids"]):
            fallos.append(f"líneas {sub['lineas_pagadas']}: no_entregar {sorted(x['id'] for x in res['no_entregar'])} ≠ {sorted(sub['no_entregar_ids'])}")
    c = e.get("correo")
    if c:
        out = d10.renderizar(_leer(c["plantilla"]), json.loads(_leer(c["datos"])), dominios=["mapymysli-angielski.example"])
        for frase in c["debe_contener"]:
            if frase not in out["texto"]:
                fallos.append(f"el correo no contiene {frase!r}")
    return fallos


def _c_construir(caso: dict[str, Any]) -> list[str]:
    e, x, fallos = caso["entrada"], caso["esperado"], []
    doc, inf = d10.construir_prueba_social(e["resenas"], oferta_id=e["oferta_id"], hoy=date.fromisoformat(e["hoy"]), permitir_sinteticos=e.get("permitir_sinteticos", False))
    val = doc.get("valoracion")
    esperado = x["valoracion"]
    if (val is None) != (esperado is None) or (val and (val["n"], val["media_decimas"]) != (esperado["n"], esperado["media_decimas"])):
        fallos.append(f"valoracion {val and (val['n'], val['media_decimas'])} ≠ {esperado and (esperado['n'], esperado['media_decimas'])}")
    if {p["resena_id"] for p in inf["publicables"]} != set(x["publicables_ids"]):
        fallos.append(f"publicables {sorted(p['resena_id'] for p in inf['publicables'])} ≠ {sorted(x['publicables_ids'])}")
    if {p["resena_id"] for p in inf["requieren_revision_humana"]} != set(x["revision_ids"]):
        fallos.append(f"revisión humana {sorted(p['resena_id'] for p in inf['requieren_revision_humana'])} ≠ {sorted(x['revision_ids'])}")
    if {d["resena_id"]: d["motivo"] for d in inf["descartadas"]} != x["descartadas"]:
        fallos.append(f"descartadas {inf['descartadas']} ≠ {x['descartadas']}")
    return fallos


def _c_validar_orden(caso: dict[str, Any]) -> list[str]:
    errs = d10.validar_orden(caso["entrada"]["orden"])
    x, fallos = caso["esperado"], []
    if (not errs) != x["ok"]:
        fallos.append(f"ok={not errs} ≠ {x['ok']} ({errs})")
    plano = " | ".join(errs).lower()
    fallos += [f"falta un error que contenga {t!r}" for t in x.get("errores_contienen", []) if t.lower() not in plano]
    return fallos


def _c_render(caso: dict[str, Any]) -> list[str]:
    e, x, fallos = caso["entrada"], caso["esperado"], []
    plantilla = e["plantilla_inline"] if "plantilla_inline" in e else _leer(e["plantilla"])
    datos = {**json.loads(_leer(e["datos"])), **e.get("override", {})}
    try:
        out = d10.renderizar(plantilla, datos, dominios=e.get("dominios"), formato="ambos")
    except d10.ErrorD10 as exc:
        if "error_contiene" in x and x["error_contiene"] in str(exc):
            return []
        return [f"error inesperado: {exc}"]
    if "error_contiene" in x:
        return [f"debía fallar con {x['error_contiene']!r} y se renderizó"]
    if x.get("asunto_sin_salto") and ("\n" in out["asunto"] or "\r" in out["asunto"]):
        fallos.append("el asunto contiene un salto de línea (inyección de cabecera)")
    fallos += [f"el HTML no contiene {t!r}" for t in x.get("html_contiene", []) if t not in out["html"]]
    fallos += [f"el HTML contiene {t!r}" for t in x.get("html_no_contiene", []) if t in out["html"]]
    fallos += [f"el texto no contiene {t!r}" for t in x.get("texto_contiene", []) if t not in out["texto"]]
    return fallos


def _c_lint_texto(caso: dict[str, Any]) -> list[str]:
    codigos = {h["codigo"] for h in d10.lint_plantilla(caso["entrada"]["plantilla"])}
    return [f"el lint no emitió {c!r} (emitió {sorted(codigos)})" for c in caso["esperado"]["codigos"] if c not in codigos]


def _c_validar_ps(caso: dict[str, Any]) -> list[str]:
    e = caso["entrada"]
    errs, _ = d10.validar_prueba_social(e["doc"], oferta_id=e.get("oferta_id"), hoy=date.fromisoformat(e["hoy"]))
    plano = " | ".join(errs).lower()
    return [f"falta un error que contenga {t!r}" for t in caso["esperado"]["errores_contienen"] if t.lower() not in plano]


def _c_orden_y_respuesta(caso: dict[str, Any]) -> list[str]:
    e, x, fallos = caso["entrada"], caso["esperado"], []
    errs = d10.validar_orden(x["orden"])
    if errs:
        fallos.append(f"la orden dorada no valida: {errs}")
    h = e["hechos_del_codigo"]
    if not (h["dentro_garantia"] and h["dias_desde_compra"] <= h["garantia_dias"] and not h["disputa_abierta"] and not h["pausa_global"]):
        fallos.append("los hechos del caso no corresponden a un reembolso dentro de plazo")
    garantia = e["oferta"]["garantia"]["texto_visible"]
    ok, no = caso["respuesta_dorada"]["si_orden_aceptada"], caso["respuesta_dorada"]["si_orden_rechazada"]
    if garantia not in ok:
        fallos.append("la respuesta no cita literal la garantía publicada (oferta.garantia.texto_visible)")
    for frase in ("musisz podać powód", "podaj powód", "uzasadnij"):
        if frase in ok.lower():
            fallos.append(f"la respuesta condiciona el reembolso a dar un motivo ({frase!r})")
    if "zleciliśmy zwrot" in no.lower():
        fallos.append("la alternativa (orden rechazada) promete un reembolso que el código no aceptó")
    for texto in (ok, no):
        if d10.texto_hostil(texto):
            fallos.append("texto con marcado o caracteres no admisibles")
    return fallos


COMPROBACIONES: dict[str, Callable[[dict[str, Any]], list[str]]] = {
    "plan_entrega": _c_plan_entrega, "construir": _c_construir, "validar_orden": _c_validar_orden, "render": _c_render,
    "lint_texto": _c_lint_texto, "validar_ps": _c_validar_ps, "orden_y_respuesta": _c_orden_y_respuesta,
}


def ejecutar_todos() -> dict[str, Any]:
    resultados, para_qa = [], []
    for caso in cargar_casos():
        auto = caso.get("auto")
        if auto is None:
            para_qa.append({"id": caso["id"], "descripcion": caso["descripcion"]})
            continue
        try:
            fallos = COMPROBACIONES[auto](caso)
        except Exception as exc:  # un eval roto debe verse como fallo, no esconderse
            fallos = [f"excepción {type(exc).__name__}: {exc}"]
        resultados.append({"id": caso["id"], "auto": auto, "ok": not fallos, "fallos": fallos})
    return {"resultados": resultados, "para_qa_l3": para_qa}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    res = ejecutar_todos()
    fallidos = [r for r in res["resultados"] if not r["ok"]]
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        for r in res["resultados"]:
            print(f"{'OK  ' if r['ok'] else 'FALLA'} {r['id']:<4} {r['auto']}" + "".join(f"\n      - {f}" for f in r["fallos"]))
        print(f"\nautomatizados: {len(res['resultados']) - len(fallidos)}/{len(res['resultados'])} · para el QA (L3): {', '.join(c['id'] for c in res['para_qa_l3'])}")
    return 0 if not fallidos else 3


if __name__ == "__main__":
    sys.exit(main())
