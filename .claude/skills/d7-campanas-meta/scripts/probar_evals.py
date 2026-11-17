#!/usr/bin/env python3
"""probar_evals.py: corre offline los evals de D7 que el código puede verificar (dorados y sembrados).

Cada caso de ``evals/sembrados/S*.json`` muta una copia temporal de ``evals/_base`` (la campaña dorada) y exige que
``d7.py lint`` (o ``presupuesto`` / ``preflight``) produzca el hallazgo esperado. Los casos con ``capa`` ``qa-l2`` o
``hook`` no se automatizan: son entradas para el agente QA y la sonda de hooks (se listan como NO_AUTOMATIZABLE).
Los dorados de ``evals/dorados/D*.json`` comparan la salida de ``d7.py presupuesto`` / ``preflight`` con lo esperado.

Uso (desde la raíz): ``.venv/bin/python .claude/skills/d7-campanas-meta/scripts/probar_evals.py [--solo S07]``.
Sin red, sin escrituras fuera de un directorio temporal. Salida 0 si todo lo automatizable pasa; 4 si algo falla.
"""
from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import yaml  # noqa: E402

import d7  # noqa: E402
from engine.parametros import Parametros  # noqa: E402
from scripts import validar_esquemas as V  # noqa: E402

SKILL = AQUI.parent
BASE = SKILL / "evals" / "_base"


def _poner(obj, ruta, valor, borrar=False):
    for clave in ruta[:-1]:
        obj = obj[clave]
    if borrar:
        del obj[ruta[-1]]
    else:
        obj[ruta[-1]] = valor


def _lim_par(caso):
    lim = json.loads((BASE / "limites_prueba.json").read_text(encoding="utf-8"))
    lim.update(caso.get("limites_override", {}))
    par = json.loads((BASE / "parametros_prueba.json").read_text(encoding="utf-8"))
    for k, v in caso.get("parametros_override", {}).items():
        g, n = k.split(".")
        par["grupos"][g][n] = {"valor": v, "unidad": "prueba", "hipotesis": True}
    return d7._limites_de(lim), Parametros(par)


def _preparar(caso, destino: Path) -> Path:
    shutil.copytree(BASE, destino)
    tocados = set()
    for m in caso.get("mutaciones", []):
        ruta = destino / m["archivo"]
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        _poner(datos, m["ruta"], m.get("valor"), m.get("borrar", False))
        ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
        tocados.add(m["archivo"])
    camp = destino / "07-campana" / "campana.json"
    if "07-campana/campana.json" in tocados and caso.get("resellar", True):
        datos = json.loads(camp.read_text(encoding="utf-8"))
        datos["hash_config"] = V.hash_objeto(datos, ("hash_config",))
        camp.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    for nuevo in caso.get("archivos_nuevos", []):
        ruta = destino / nuevo["archivo"]
        ruta.parent.mkdir(parents=True, exist_ok=True)
        if "lineas" in nuevo:
            with open(ruta, "a", encoding="utf-8") as f:
                f.writelines(json.dumps(x, ensure_ascii=False) + "\n" for x in nuevo["lineas"])
        else:
            datos = nuevo["json"]
            if nuevo.get("hash_de_campana"):  # nombre de la clave que debe llevar el hash vigente de campana.json
                datos = {**datos, nuevo["hash_de_campana"]: json.loads(camp.read_text(encoding="utf-8"))["hash_config"]}
            ruta.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    return destino


def _terminos():
    return list(yaml.safe_load((BASE / "terminos_prueba.yaml").read_text(encoding="utf-8"))["terminos"])


def _correr_lint(caso, tmp: Path):
    lim, par = _lim_par(caso)
    return d7.lint(_preparar(caso, tmp / "oferta"), lim, par, _terminos())


def _correr_presupuesto(caso):
    entrada = json.loads((AQUI.parent / "evals" / "dorados" / "_entradas" / f"{caso['entrada_presupuesto']}.json").read_text(encoding="utf-8")) \
        if isinstance(caso["entrada_presupuesto"], str) else copy.deepcopy(caso["entrada_presupuesto"])
    return d7.presupuesto(entrada, d7._limites_de(entrada["limites"]), d7._parametros_de(entrada["parametros"]))


def _correr_preflight(caso, tmp: Path):
    destino = _preparar(caso, tmp / "oferta")
    ent = json.loads((destino / "entradas_preflight.json").read_text(encoding="utf-8"))
    for m in caso.get("mutaciones_entradas", []):
        _poner(ent, m["ruta"], m.get("valor"))
    (destino / "entradas_preflight.json").write_text(json.dumps(ent), encoding="utf-8")
    salida = io.StringIO()
    with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(io.StringIO()):
        d7.main(["--limites", str(BASE / "limites_prueba.json"), "--parametros", str(BASE / "parametros_prueba.json"), "preflight",
                 "--entradas", str(destino / "entradas_preflight.json"), "--campana", str(destino / "07-campana" / "campana.json"),
                 "--ahora", "2026-11-16T08:00:00Z"])
    return json.loads(salida.getvalue())["preflight"]


def _sub(obtenido, esperado, ruta=""):
    """Todo lo de ``esperado`` debe estar en ``obtenido`` (comparación parcial por claves)."""
    if isinstance(esperado, dict):
        return all(_sub(obtenido.get(k) if isinstance(obtenido, dict) else None, v, f"{ruta}/{k}") for k, v in esperado.items())
    return obtenido == esperado


def evaluar(caso, tmp: Path):
    capa = caso.get("capa", "script-lint")
    if capa in ("qa-l2", "hook"):
        return "NO_AUTOMATIZABLE", f"capa {capa}: la corre el agente QA o la sonda de hooks"
    if capa == "script-presupuesto":
        codigo, res = _correr_presupuesto(caso)
        ok = _sub(res, caso["esperado"])
        return ("OK" if ok else "FALLA"), json.dumps({k: res.get(k) for k in caso["esperado"]}, ensure_ascii=False)[:200]
    if capa == "script-preflight":
        pf = _correr_preflight(caso, tmp)
        ok = all(pf["checks"][k]["estado"] == v for k, v in caso["esperado"].items()) and pf["semaforo"] == caso.get("semaforo", pf["semaforo"])
        return ("OK" if ok else "FALLA"), f"semaforo {pf['semaforo']}; " + ", ".join(f"{k}={pf['checks'][k]['estado']}" for k in caso["esperado"])
    hallazgos = _correr_lint(caso, tmp)
    exp = caso["esperado"]
    if exp.get("sin_bloqueos"):
        malos = [h for h in hallazgos if h["severidad"] in d7.BLOQUEA]
        return ("OK" if not malos else "FALLA"), f"{len(malos)} hallazgos bloqueantes"
    coincide = [h for h in hallazgos if h["codigo"] == exp["codigo"] and h["check_id"] == exp["check_id"] and h["severidad"] == exp["severidad"]]
    return ("OK" if coincide else "FALLA"), ", ".join(f"{h['check_id']}:{h['codigo']}" for h in hallazgos)[:200]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo")
    args = ap.parse_args()
    casos = []
    for carpeta in ("dorados", "sembrados"):
        for ruta in sorted((SKILL / "evals" / carpeta).glob("[DS][0-9]*.json")):
            casos.append(json.loads(ruta.read_text(encoding="utf-8")))
    fallas = 0
    with tempfile.TemporaryDirectory() as t:
        # control: la campaña dorada no debe producir hallazgos bloqueantes
        control = evaluar({"capa": "script-lint", "esperado": {"sin_bloqueos": True}}, Path(t) / "control")
        print(f"CONTROL _base: {control[0]} ({control[1]})")
        fallas += control[0] != "OK"
        for caso in casos:
            if args.solo and caso["id"] != args.solo:
                continue
            estado, detalle = evaluar(caso, Path(t) / caso["id"])
            fallas += estado == "FALLA"
            print(f"{caso['id']:<4} {estado:<17} {caso.get('check_id', ''):<5} {detalle}")
    print("RESULTADO:", "todo lo automatizable pasa" if not fallas else f"{fallas} falla(s)")
    return 4 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
