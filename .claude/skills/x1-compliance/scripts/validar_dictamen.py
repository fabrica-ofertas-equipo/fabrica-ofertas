#!/usr/bin/env python3
"""Valida un dictamen de X1 (un ``qa`` con ``etapa = X1``) ANTES de entregarlo a QA o al sello.

Hace dos cosas: (1) el esquema real (``contratos/qa.schema.json`` vía ``engine.comun.errores_de_esquema``) y
(2) las reglas propias de X1 que el esquema no cubre (spec 14 §3.3, §6, R15 de ``docs/contratos.md``).
NO firma, NO sella y NO decide nada: el sello lo emite ``compliance.sellar`` con una clave que el agente no
tiene. Un dictamen que pase este validador sigue sin valer hasta que exista el sello.

Uso (desde la raíz del repositorio):
  .venv/bin/python .claude/skills/x1-compliance/scripts/validar_dictamen.py RUTA/dictamen.json [--umbral 4.0] [--post-motor]
Salida: 0 sin errores (puede haber avisos) · 3 errores · 2 uso o entorno.
--sin-nombre omite la comprobación del nombre de archivo (plantillas y borradores en staging).
--post-motor admite ``firma_motor`` no nula (solo para archivos que ya pasaron por el motor).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _params import leer_parametro  # noqa: E402
import nivel_ejes  # noqa: E402
ITEMS_L2 = tuple(f"R{i}" for i in range(1, 9))
SIMULACIONES = ("revisor de meta", "consumidor esc", "riesgo de stripe", "espectador ajeno")
_RX_EJES = re.compile(r"P\s*=\s*(P[0-3][sn]?)\W+C\s*=\s*(C[0-3])\W+E\s*=\s*(E[0-3])\W+N\s*=\s*(N[0-3]s?)")
_ORDEN = {"verde": 0, "amarillo": 1, "rojo": 2}
_RX_CITA = re.compile(r"«[^»]{3,}»|\"[^\"]{3,}\"|sha256:[0-9a-f]{8,}|#[A-Za-z0-9_.\-\[\]]+")


def _cargar_umbral_por_defecto() -> str | None:
    return leer_parametro("compliance", "umbral_rubrica_pass")  # sin el parámetro no se inventa un umbral: se avisa


def validar(d: dict, *, ruta: Path | None = None, umbral: str | None = None, post_motor: bool = False) -> tuple[list[str], list[str]]:
    from engine import comun  # import tardío: exige correr desde el repositorio

    errores: list[str] = []
    avisos: list[str] = []
    for e in comun.errores_de_esquema("qa", d):
        errores.append(f"esquema: {comun.resumir_errores_esquema([e])}")
    if errores:
        return errores, avisos  # sin forma válida no tiene sentido seguir
    if d["etapa"] != "X1":
        errores.append("etapa debe ser X1 (R15: el dictamen de X1 es un qa con etapa = X1)")
    if not d.get("etapa_objetivo"):
        errores.append("falta etapa_objetivo")
    if d.get("x1") is not None:
        errores.append("x1 debe ser null en el propio dictamen (x1 lo usa el QA de la etapa para referenciarlo)")
    if d.get("firma_motor") is not None and not post_motor:
        errores.append("firma_motor debe ser null: la firma la pone el motor, nunca el agente (un dictamen escrito por el LLM no vale)")
    for campo in ("semaforo", "reglas_version", "politicas_fecha_min", "vigencia_hasta"):
        if d.get(campo) is None:
            errores.append(f"{campo} es obligatorio en un dictamen de X1")
    if ruta is not None and d.get("etapa_objetivo"):
        esperado = f"x1-{d['etapa_objetivo'].lower()}-{d['version']}.json"
        if ruta.name != esperado and not ruta.name.endswith(".borrador.json"):
            errores.append(f"el nombre debe ser {esperado} (R09/R15)")
    if d["ambito"] == "oferta" and not d.get("claims_trazados") and d.get("etapa_objetivo") in ("D3", "D5", "D6"):
        avisos.append("claims_trazados vacío en D3/D5/D6: todo claim debe trazarse a su evidencia (L1-11/13)")

    # semáforo, veredicto y hallazgos
    abiertos = [h for h in d["hallazgos"] if h["estado"] in ("abierto", "devuelto_al_maker")]
    bloq = [h for h in abiertos if h["severidad"] == "BLOQUEANTE"]
    mayor = [h for h in abiertos if h["severidad"] == "MAYOR"]
    if d.get("semaforo") == "rojo" and d["veredicto"] not in ("FAIL", "ESCALAR"):
        errores.append("semáforo rojo exige veredicto FAIL o ESCALAR (un ROJO bloquea; solo se levanta corrigiendo el artefacto)")
    if d["veredicto"] in ("PASS", "PASS_CON_NOTAS") and (bloq or mayor):
        errores.append("PASS con BLOQUEANTES o MAYORES abiertos")
    if d["veredicto"] == "FAIL" and not (bloq or mayor):
        avisos.append("FAIL sin BLOQUEANTE/MAYOR abierto: debe justificarse por puntaje bajo el umbral o ítem < 3")
    for h in d["hallazgos"]:
        if h["severidad"] in ("BLOQUEANTE", "MAYOR") and not (h.get("correccion") or "").strip():
            errores.append(f"{h['check_id']}: todo hallazgo BLOQUEANTE/MAYOR lleva corrección segura (reencuadre antes que bloqueo)")
        if not _RX_CITA.search(h["evidencia"]):
            avisos.append(f"{h['check_id']}: la evidencia no trae cita literal «…», hash ni ruta#campo")
        if not re.match(r"^(L1|L2|L3|X1)-", h["check_id"]):
            avisos.append(f"{h['check_id']}: usar prefijo L1-/L2-/L3-/X1- para el check_id")

    # rúbrica L2
    ids = [it["item_id"] for it in d["items"]]
    faltan = [i for i in ITEMS_L2 if i not in ids]
    if faltan:
        errores.append(f"faltan ítems de rúbrica: {', '.join(faltan)} (rubric.md define R1-R8)")
    try:
        media = sum(Decimal(it["puntaje"]) for it in d["items"]) / len(d["items"])
        if abs(media - Decimal(d["puntaje_global"])) > Decimal("0.05"):
            errores.append(f"puntaje_global {d['puntaje_global']} != media de ítems {media:.2f}")
        umbral = umbral or _cargar_umbral_por_defecto()
        if umbral is None:
            avisos.append("no se pudo leer compliance.umbral_rubrica_pass: umbral sin verificar")
        else:
            if Decimal(d["umbral"]) != Decimal(umbral):
                errores.append(f"umbral {d['umbral']} != compliance.umbral_rubrica_pass ({umbral})")
            if d["veredicto"] in ("PASS", "PASS_CON_NOTAS") and Decimal(d["puntaje_global"]) < Decimal(umbral):
                errores.append("PASS con puntaje bajo el umbral")
    except (InvalidOperation, ZeroDivisionError) as exc:
        errores.append(f"puntajes ilegibles: {exc}")
    if any(it["puntaje"] < 3 for it in d["items"]) and d["veredicto"] in ("PASS", "PASS_CON_NOTAS"):
        errores.append("PASS con un ítem de rúbrica < 3 (X1: ningún ítem < 3)")

    # nivel: el LLM asigna los códigos de eje, el script calcula el nivel; el semáforo no puede ser MENOR que el calculado
    niveles = []
    for c in d["checks_l1"]:
        if "NIVEL" in c["check_id"].upper():
            m = _RX_EJES.search(c["detalle"])
            if not m:
                errores.append(f"{c['check_id']}: el detalle debe traer los ejes como «P=P0 C=C1 E=E0 N=N1»")
                continue
            try:
                niveles.append(nivel_ejes.calcular(dict(zip("PCEN", m.groups())))["nivel"])
            except ValueError as exc:
                errores.append(f"{c['check_id']}: {exc}")
    if niveles and d.get("semaforo") and _ORDEN[d["semaforo"]] < _ORDEN[max(niveles, key=_ORDEN.__getitem__)]:
        errores.append(f"semaforo {d['semaforo']} es MENOR que el nivel calculado por scripts.nivel_riesgo ({max(niveles, key=_ORDEN.__getitem__)}): un LLM no baja un nivel")
    if not niveles and d["ambito"] == "oferta" and d.get("etapa_objetivo") in ("D2", "D3", "D6"):
        errores.append("D2/D3/D6 exigen un check L1-NIVEL con los ejes «P=… C=… E=… N=…» (X1 recalcula el riesgo; el script calcula el nivel)")

    # L1 y L3 (solo dictámenes por oferta)
    if d["ambito"] == "oferta":
        l1 = " ".join(c["check_id"].upper() for c in d["checks_l1"])
        if "LINT" not in l1:
            errores.append("checks_l1 sin la corrida del linter (L1-LINT: compliance.lint_claims); sin lint no hay sello")
        if "HASH" not in l1:
            errores.append("checks_l1 sin la comprobación de hash (L1-HASH)")
        nombres = " ".join(s["nombre"].lower() for s in d["simulaciones_l3"])
        if d.get("etapa_objetivo") in ("D5", "D6", "D7"):
            for s in SIMULACIONES:
                if s not in nombres:
                    avisos.append(f"simulaciones_l3 sin «{s}» (spec §6.3)")
    return errores, avisos


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("dictamen", type=Path)
    p.add_argument("--umbral", default=None, help="por defecto, compliance.umbral_rubrica_pass de empresa/parametros.yaml")
    p.add_argument("--post-motor", action="store_true")
    p.add_argument("--sin-nombre", action="store_true", help="no exigir el nombre x1-<etapa>-v<n>.json (plantillas y borradores)")
    try:
        a = p.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    sys.path.insert(0, str(RAIZ))
    try:
        d = json.loads(a.dictamen.read_text(encoding="utf-8"))
        errores, avisos = validar(d, ruta=None if a.sin_nombre else a.dictamen, umbral=a.umbral, post_motor=a.post_motor)
    except (OSError, ValueError, ImportError) as exc:
        print(f"no se pudo validar: {exc} (correr desde la raíz del repositorio con .venv/bin/python)", file=sys.stderr)
        return 2
    for e in errores:
        print(f"ERROR  {e}")
    for w in avisos:
        print(f"AVISO  {w}")
    print(f"dictamen: {len(errores)} errores, {len(avisos)} avisos")
    return 3 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
