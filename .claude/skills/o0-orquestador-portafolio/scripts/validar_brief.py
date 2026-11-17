#!/usr/bin/env python3
"""Validador determinista de un brief de O0 (validación EN SECO previa al gate H y a `orq crear`; NO crea nada, NO asigna `oferta_id`, NO firma, sin red).

Uso (desde la raíz del repositorio):
    .venv/bin/python .claude/skills/o0-orquestador-portafolio/scripts/validar_brief.py BRIEF.yaml \
        [--limites empresa/limites.yaml] [--autonomia empresa/autonomia.yaml] \
        [--candidatos candidatos.json --candidato CAND-NN] [--presupuesto-test-min MONTO] \
        [--calcular-hash] [--json]

Qué comprueba (los códigos B** son de esta ayuda; `engine.orq crear` repite solo esquema, moneda y países permitidos, y `orq validar` [PENDIENTE: SB-8] mandará sobre ella):
  B01 esquema `brief` · B02 hash del contenido · B03 firma (borrador sin firma = aviso, no error)
  B10 moneda del presupuesto == `moneda_limites` · B11 techos (<= límites y diario <= tope / factor) ·
  B12 nichos y sub-nichos · B13 locale, países y cuenta ∈ límites · B14 nivel <= autonomía de O0 ·
  B20-B24 candidato (existe, no ROJO, macro-nicho del brief, mismo locale; el AMARILLO-A|B se avisa) · B30 presupuesto de test mínimo.
Salida: 0 sin errores · 2 uso · 3 validación (esquema, hash, moneda, encuadre) · 5 límites ausentes o brief fuera de límites.
El criterio de moneda y de límites es FAIL-CLOSED: sin `limites.yaml` utilizable no se aprueba nada.
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path


def _raiz() -> Path:
    for p in Path(__file__).resolve().parents:
        if (p / "contratos").is_dir() and (p / "scripts" / "validar_esquemas.py").is_file():
            return p
    raise SystemExit("no se encontró la raíz del repositorio (contratos/ y scripts/validar_esquemas.py)")


RAIZ = _raiz()
sys.path.insert(0, str(RAIZ))
from scripts import validar_esquemas as ve  # noqa: E402

NIVELES = ["N0", "N1", "N2", "N3", "N4"]
CLAVES_LIMITE = ("moneda_limites", "gasto_total_test_por_oferta", "gasto_diario_por_oferta", "paises_permitidos", "locales_permitidos",
                 "cuentas_permitidas", "factor_techo_teorico_diario")


class Informe:
    """Acumula hallazgos; `codigo` 3 gana sobre 5 (como en `engine.guard`: la moneda y el dato incoherente se miran primero)."""

    def __init__(self) -> None:
        self.errores: list[dict] = []
        self.avisos: list[dict] = []

    def error(self, codigo: str, msg: str, salida: int = 3) -> None:
        self.errores.append({"codigo": codigo, "mensaje": msg, "salida": salida})

    def aviso(self, codigo: str, msg: str) -> None:
        self.avisos.append({"codigo": codigo, "mensaje": msg})

    def salida(self) -> int:
        if any(e["salida"] == 3 for e in self.errores):
            return 3
        return 5 if self.errores else 0


def _monto(d: dict) -> tuple[int, str]:
    return int(d["monto"]), str(d["moneda"])


def validar(brief: dict, lim: dict | None, aut: dict | None, cands: dict | None, cand_id: str | None,
            presupuesto_test_min: int | None, inf: Informe) -> str:
    """Corre todos los chequeos sobre datos ya cargados. Devuelve el hash calculado del contenido."""
    for e in ve.errores_de_esquema("brief", brief):
        inf.error("B01_ESQUEMA", f"{ve.ruta_json(e) or '/'}: {e.message[:160]}")
    if inf.errores:
        return ""  # sin esquema válido no se puede razonar sobre el resto
    calculado = ve.hash_objeto(brief, excluir=("hash", "aprobado_por"))
    if not ve.comparar_hash(brief["hash"], calculado):
        inf.error("B02_HASH", f"hash declarado {brief['hash']} != calculado {calculado} (el hash cubre todo salvo `hash` y `aprobado_por`)")
    firma = brief["aprobado_por"].get("firma")
    if firma is None:
        inf.aviso("B03_SIN_FIRMA", "BORRADOR: `aprobado_por.firma` es null; el gate H del brief aún no está firmado (solo el dueño; el mecanismo de firma del brief antes de `orq crear` es LT-54)")
    elif ve.tipo_firma(firma) is None:
        inf.error("B03_FIRMA", "firma con formato inválido (se espera ed25519:… o hmac-sha256:…); la verificación criptográfica es del motor")
    else:
        inf.aviso("B03_FIRMA_NO_VERIFICADA", "formato de firma correcto; esta ayuda NO la verifica (lo hace `engine.guard` con la clave pública)")
    bp = brief["presupuesto"]
    monedas = {bp[k]["moneda"] for k in ("test_total_max", "test_diario_max", "ia_max")}
    if len(monedas) != 1:
        inf.error("B10_MONEDA", f"presupuesto en monedas distintas: {sorted(monedas)}")
    if bp["test_diario_max"]["monto"] > bp["test_total_max"]["monto"]:
        inf.error("B11_TOPES", "test_diario_max > test_total_max")
    pr, mo = brief["precio_rango"], brief["mercado_objetivo"]
    if pr["min"]["moneda"] != mo["moneda_cobro"] or pr["max"]["moneda"] != mo["moneda_cobro"]:
        inf.error("B10_MONEDA", "precio_rango en una moneda distinta de mercado_objetivo.moneda_cobro")
    if pr["min"]["monto"] > pr["max"]["monto"]:
        inf.error("B11_TOPES", "precio_rango.min > max")
    # --- límites (fail-closed) ---
    if not isinstance(lim, dict):
        inf.error("B05_LIMITES", "limites.yaml no cargado: sin límites no se aprueba ningún brief (código 5)", 5)
    else:
        faltan = [k for k in CLAVES_LIMITE if lim.get(k) is None or lim.get(k) == []]
        if faltan:
            inf.error("B05_LIMITES", "límites incompletos (null o lista vacía = obligatorio del dueño): " + ", ".join(faltan), 5)
        else:
            _contra_limites(brief, lim, inf)
    if aut is not None:
        nivel_o0 = ((aut.get("nivel_por_etapa") or {}).get("O0") or {}).get("nivel")
        if nivel_o0 in NIVELES and NIVELES.index(brief["nivel_autonomia"]) > NIVELES.index(nivel_o0):
            inf.error("B14_NIVEL", f"nivel_autonomia {brief['nivel_autonomia']} supera el de O0 en autonomia.yaml ({nivel_o0})", 5)
    else:
        inf.aviso("B14_SIN_AUTONOMIA", "no se pasó --autonomia: nivel del brief no contrastado con autonomia.yaml")
    if cands is not None:
        _candidato(brief, cands, cand_id, inf)
    elif cand_id:
        inf.error("B20_CANDIDATO", "se pidió --candidato sin --candidatos")
    else:
        inf.aviso("B20_SIN_CANDIDATO", "sin --candidatos: no se verificó riesgo ni macro-nicho del candidato (lo exige el QA y `orq crear`)")
    if presupuesto_test_min is None:
        inf.aviso("B30_SIN_MINIMO", "sin --presupuesto-test-min: no se verificó test_total_max >= economia.presupuesto_test_min (MAYOR en QA si falla)")
    elif bp["test_total_max"]["monto"] < presupuesto_test_min:
        inf.error("B30_PRESUPUESTO_MIN", f"test_total_max {bp['test_total_max']['monto']} < presupuesto_test_min {presupuesto_test_min}: la oferta solo podría morir, no validarse (MAYOR; validarse exige reconocimiento firmado)", 5)
    return calculado


def _contra_limites(brief: dict, lim: dict, inf: Informe) -> None:
    bp, mo = brief["presupuesto"], brief["mercado_objetivo"]
    if bp["test_total_max"]["moneda"] != lim["moneda_limites"]:
        inf.error("B10_MONEDA", f"moneda del brief {bp['test_total_max']['moneda']} != moneda_limites {lim['moneda_limites']}: no crea nada sin tipo de cambio registrado")
        return
    for k, kl in (("test_total_max", "gasto_total_test_por_oferta"), ("test_diario_max", "gasto_diario_por_oferta")):
        if bp[k]["monto"] > lim[kl]:
            inf.error("B11_TOPES", f"{k} {bp[k]['monto']} supera limites.{kl} {lim[kl]} (el brief solo restringe)", 5)
    try:
        factor = Decimal(str(lim["factor_techo_teorico_diario"]))
        if factor > 0 and Decimal(bp["test_diario_max"]["monto"]) * factor > Decimal(lim["gasto_diario_por_oferta"]):
            inf.error("B11_TOPES", f"test_diario_max x {factor} (techo teórico de Meta) supera limites.gasto_diario_por_oferta {lim['gasto_diario_por_oferta']}", 5)
    except (InvalidOperation, ValueError):
        inf.error("B11_TOPES", "factor_techo_teorico_diario ilegible")
    nichos = lim.get("macro_nichos_permitidos") or []
    if not set(brief["nichos"]["permitidos"]) <= set(nichos):
        inf.error("B12_NICHOS", f"nichos fuera de limites.macro_nichos_permitidos: {sorted(set(brief['nichos']['permitidos']) - set(nichos))}")
    if not set(brief["nichos"]["subnichos_prohibidos"]) >= set(lim.get("subnichos_prohibidos") or []):
        inf.error("B12_NICHOS", "el brief no puede quitar subnichos_prohibidos de limites")
    if mo["locale"] not in lim["locales_permitidos"]:
        inf.error("B13_LOCALE", f"locale {mo['locale']} fuera de limites.locales_permitidos", 5)
    fuera = sorted(set(mo["paises_segmentacion"]) - set(lim["paises_permitidos"]))
    if fuera:
        inf.error("B13_PAIS", f"países fuera de limites.paises_permitidos: {fuera}", 5)
    if brief["cuenta_meta_id"] not in lim["cuentas_permitidas"]:
        inf.error("B13_CUENTA", "cuenta_meta_id fuera de limites.cuentas_permitidas", 5)


def _candidato(brief: dict, cands: dict, cand_id: str | None, inf: Informe) -> None:
    for e in ve.errores_de_esquema("candidatos", cands):
        inf.error("B20_CANDIDATOS_ESQUEMA", f"{ve.ruta_json(e) or '/'}: {e.message[:120]}")
        return
    elegido = next((c for c in cands["candidatos"] if c["candidato_id"] == cand_id), None)
    if elegido is None:
        inf.error("B20_CANDIDATO", f"candidato {cand_id} no está en el snapshot")
        return
    r = elegido["riesgo"]
    if r["nivel"] == "rojo":
        inf.error("B21_ROJO", f"candidato {cand_id} ROJO: no avanza (solo un reencuadre registrado y re-evaluado lo cambia)")
    elif r["nivel"] == "amarillo":
        colores = [r.get(eje) for eje in ("P", "C", "E", "N")]
        sub = r.get("subnivel") or ("B" if colores.count("amarillo") >= 2 else "A")   # [SUPUESTO] sin `subnivel`/`ejes_codigo` en el snapshot: >= 2 amarillos = B
        inf.aviso("B21_AMARILLO", f"candidato AMARILLO-{sub}: la variante B exige gate H y cuota amarilla; el nivel lo recomputa `python -m scripts.nivel_riesgo` con los ejes P/C/E/N (esta ayuda no lo importa)")
    if elegido["macro_nicho"] not in brief["nichos"]["permitidos"]:
        inf.error("B22_MACRO_NICHO", f"macro_nicho {elegido['macro_nicho']} fuera de brief.nichos.permitidos (rechazo canónico: fuera_de_macro_nicho)")
    mo = brief["mercado_objetivo"]
    if cands["mercado"]["locale"] != mo["locale"]:
        inf.error("B23_LOCALE", f"la evidencia del candidato es de {cands['mercado']['locale']} y el brief es {mo['locale']}: un problema no se asume válido en otro idioma")
    if not set(mo["paises_segmentacion"]) <= set(cands["mercado"]["paises"]):
        inf.aviso("B24_PAISES", "el brief segmenta países que el snapshot no cubre")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("brief")
    ap.add_argument("--limites", default=str(RAIZ / "empresa" / "limites.yaml"))
    ap.add_argument("--autonomia")
    ap.add_argument("--candidatos")
    ap.add_argument("--candidato")
    ap.add_argument("--presupuesto-test-min", type=int)
    ap.add_argument("--calcular-hash", action="store_true", help="imprime el hash del contenido y sale (el dueño/Maker lo copia al borrador)")
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code not in (0, None) else 0
    try:
        brief = ve.cargar_datos(a.brief)
        lim = ve.cargar_yaml(a.limites) if Path(a.limites).is_file() else None
        aut = ve.cargar_yaml(a.autonomia) if a.autonomia else None
        cands = ve.cargar_datos(a.candidatos) if a.candidatos else None
    except Exception as exc:  # noqa: BLE001 - YAML/JSON ilegible = error de uso, no traza
        print(f"ERROR de lectura: {type(exc).__name__}: {str(exc)[:200]}", file=sys.stderr)
        return 2
    if a.calcular_hash:
        print(ve.hash_objeto(brief, excluir=("hash", "aprobado_por")))
        return 0
    inf = Informe()
    calculado = validar(brief, lim, aut, cands, a.candidato, a.presupuesto_test_min, inf)
    codigo = inf.salida()
    if a.json:
        print(json.dumps({"ok": codigo == 0, "codigo": codigo, "hash_calculado": calculado, "errores": inf.errores, "avisos": inf.avisos}, ensure_ascii=False))
    else:
        for e in inf.errores:
            print(f"ERROR {e['codigo']}: {e['mensaje']}")
        for w in inf.avisos:
            print(f"AVISO {w['codigo']}: {w['mensaje']}")
        print("BRIEF VÁLIDO (esta ayuda no crea nada: `engine.orq crear` repite y manda)" if codigo == 0 else f"BRIEF RECHAZADO (salida {codigo}): no se crea nada")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
