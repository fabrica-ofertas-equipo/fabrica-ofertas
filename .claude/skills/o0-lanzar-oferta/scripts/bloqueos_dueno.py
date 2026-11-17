#!/usr/bin/env python3
"""Bloqueos de DECISIONES DEL DUEÑO, derivados de los archivos reales (solo lectura, sin red, no escribe nada).

Convierte las decisiones que hoy esperan al dueño (primer mercado, cuenta de Meta, límites, métodos de pago, líneas rojas; `docs/00` §0, §3, §4;
hueco 7 de `docs/_historial/auditoria-pedidos-primera-sesion.md`) en una lista de bloqueos VISIBLES: cada uno dice cómo se sabe que está resuelto
(qué clave de qué archivo), qué bloquea y quién/cómo lo cierra. El panel puede mostrarla tal cual (`--json`); esta ayuda no firma ni resuelve nada.

Uso (raíz del repositorio):
    .venv/bin/python .claude/skills/o0-lanzar-oferta/scripts/bloqueos_dueno.py [--raiz R] [--oferta OF-AAAAMM-NN] [--estricto] [--json]
Salida: 0 (informativa; con --estricto: 5 si hay algún bloqueo abierto) · 2 uso · 3 archivo ilegible.
Estados: `abierta` (bloquea ahora) · `diferida` (el dueño decidió dejarla para después; bloquea al llegar a la etapa indicada) ·
`resuelta` · `no_verificable` (depende de una oferta que no se pasó).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

RAIZ_CODIGO = next(p for p in Path(__file__).resolve().parents if (p / "contratos").is_dir() and (p / "scripts" / "validar_esquemas.py").is_file())
sys.path.insert(0, str(RAIZ_CODIGO))
from scripts import validar_esquemas as ve  # noqa: E402

ORQ = ".venv/bin/python -m engine"


def _item(id_: str, titulo: str, estado: str, evidencia: str, bloquea: list[str], como: str, quien: str = "dueño", comando: str | None = None, ref: str = "") -> dict:
    return {"id": id_, "titulo": titulo, "estado": estado, "evidencia": evidencia, "bloquea": bloquea, "como_se_cierra": como, "quien": quien, "comando": comando, "referencia": ref}


def calcular(lim: dict | None, mercado: dict | None, oferta_id: str | None, entorno: str | None = None) -> list[dict]:
    """Lista de bloqueos a partir de `limites.yaml` (ya cargado; None = ausente) y, si hay oferta, de su `mercado.json`."""
    lim = lim if isinstance(lim, dict) else {}
    out: list[dict] = []
    # 1. Límites (incluye la pérdida máxima diferida y el sello)
    faltan: list[str] = []
    for op in ("gastar", "activar"):
        faltan += [k for k in ve.evaluar_limites(lim or None, op, entorno=entorno or "").faltantes if k not in faltan]
    out.append(_item("limites", "Límites del dueño completos y sellados", "resuelta" if not faltan else "abierta",
                     "empresa/limites.yaml" + (": completo y sellado" if not faltan else f": {len(faltan)} claves en null, vacías o sin sello ({', '.join(faltan[:6])}{'…' if len(faltan) > 6 else ''})"),
                     ["gastar", "activar", "D7", "brief aprobable (orq crear sale 5)"],
                     "Fijar los presupuestos de testeo con `engine.propuestas proponer` (muestra, por tope, cuántas veces el sistema decide bien y cuánto gasta; necesita la `economia.json` de D3 de una oferta), elegir la pérdida máxima por oferta y de cartera, y sellar con `engine.propuestas sellar` en tu terminal (`--live` solo con `FABRICA_ENTORNO=produccion` y `--clave-privada` con la ruta que pones tú: nunca en un chat ni en el repositorio). No existe `engine.limites proponer|sellar`.",
                     comando=f"{ORQ}.propuestas proponer --oferta <OF-…>   →   {ORQ}.propuestas sellar --propuesta empresa/propuestas/limites.propuesta.yaml --como dueno [--live --clave-privada <RUTA_QUE_PONES_TÚ>]",
                     ref="docs/00-decisiones-y-tareas-del-dueno.md §0.C y §2 (pérdida máxima diferida)"))
    # 2. Primer mercado
    mer = bool(lim.get("locales_permitidos")) and bool(lim.get("paises_permitidos"))
    out.append(_item("primer_mercado", "Primer mercado (idioma y países permitidos)", "resuelta" if mer else "abierta",
                     "empresa/limites.yaml: " + ("locales_permitidos y paises_permitidos con datos" if mer else "locales_permitidos o paises_permitidos vacíos"),
                     ["brief (B13_LOCALE, B13_PAIS)", "M1 primer lanzamiento", "D2 en adelante"],
                     "Decidir el primer locale con datos de M1 (Polonia, Italia o cualquier mercado son **hipótesis**, no prior) y cargarlo en límites con `sellar`. El primer lanzamiento en país o idioma nuevo es H en todo nivel.",
                     ref="docs/00 §0.B 2 y 4; backbone decisión 7 y 13"))
    # 3. Cuenta de Meta
    cta = bool(lim.get("cuentas_permitidas")) and lim.get("moneda_limites") is not None
    out.append(_item("cuenta_meta", "Cuenta de Meta única (y moneda de la cuenta)", "resuelta" if cta else "abierta",
                     "empresa/limites.yaml: " + ("cuentas_permitidas y moneda_limites con datos" if cta else "cuentas_permitidas vacía o moneda_limites null"),
                     ["brief (B13_CUENTA, B10_MONEDA)", "D7 y toda activación"],
                     "Elegir una sola cuenta limpia con método de pago y fan page propia; moneda y zona horaria no se pueden cambiar después. La cuenta deshabilitada se apela o se abandona; **nunca** se abre otra para esquivarla. Cargarla en límites con `sellar`.",
                     ref="docs/00 §0.B 2 y §3 (Meta: una sola cuenta publicitaria limpia)"))
    # 4. Líneas rojas
    lr = bool(lim.get("lineas_rojas"))
    out.append(_item("lineas_rojas", "Líneas rojas (promesas, contenidos y modelos de negocio) aprobadas", "resuelta" if lr else "abierta",
                     "empresa/limites.yaml: " + ("lineas_rojas con datos" if lr else "lineas_rojas vacía: el QA no puede comprobar «ninguna línea roja» (check 3)"),
                     ["QA del brief (check 3)", "nivel máximo lanzable", "elegir candidato amarillo"],
                     "Aprobar o recortar la propuesta de líneas rojas y cargarla en límites. El criterio es de promesas, contenidos y modelos de negocio, **no de temas**.",
                     ref="docs/00 §0.B 5 y §2; docs/_historial/hwr-resumen-para-el-dueno.md"))
    # 5. Métodos de pago / régimen fiscal (por oferta y mercado)
    if mercado is None:
        est, ev = ("diferida" if not oferta_id else "no_verificable"), ("decisión diferida por el dueño (2026-11-06); es por oferta y por mercado: " + ("no hay `mercado.json` de esta oferta" if oferta_id else "pasa --oferta para verificarla"))
    else:
        fis = mercado.get("fiscal") or {}
        sin_firma = fis.get("regimen") == "diferido" and not fis.get("exposicion_aceptada")
        est = "abierta" if sin_firma else "diferida" if (mercado.get("metodos_pago") or {}).get("locales_diferidos") else "resuelta"
        ev = (f"mercado.json de {oferta_id}: fiscal.regimen={fis.get('regimen')}, exposicion_aceptada={'firmada' if fis.get('exposicion_aceptada') else 'ausente'}, "
              f"metodos_pago.fase={(mercado.get('metodos_pago') or {}).get('fase')}")
    out.append(_item("metodos_pago", "Métodos de pago y régimen fiscal del mercado", est, ev, ["D5 (checkout)", "D7 (campaña sin checkout no es activable)", "X1 (X32_FISCAL)"],
                     "Con el contador: Managed Payments **o** IVA simple con métodos locales (no son compatibles entre sí: Polonia depende de eso); firmar `mercado.fiscal.exposicion_aceptada`. No bloquea D1-D4; se retoma antes de D5.",
                     quien="dueño + contador (lo fiscal; el abogado no es requisito)", ref="docs/00 §0.B 4 y §4"))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--raiz")
    ap.add_argument("--oferta")
    ap.add_argument("--estricto", action="store_true")
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code not in (0, None) else 0
    raiz = Path(a.raiz) if a.raiz else RAIZ_CODIGO
    try:
        ruta_l = raiz / "empresa" / "limites.yaml"
        lim = ve.cargar_yaml(ruta_l) if ruta_l.is_file() else None
        ruta_m = raiz / "ofertas" / a.oferta / "mercado.json" if a.oferta else None
        mercado = ve.cargar_json(ruta_m) if ruta_m and ruta_m.is_file() else None
    except Exception as exc:  # noqa: BLE001 - archivo ilegible = salida 3, sin traza
        print(f"ERROR: archivo ilegible ({type(exc).__name__}: {str(exc)[:160]})", file=sys.stderr)
        return 3
    items = calcular(lim, mercado, a.oferta)
    abiertas = [i for i in items if i["estado"] == "abierta"]
    res = {"generado_en": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "abiertas": len(abiertas), "total": len(items), "items": items}
    if a.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        print(f"BLOQUEOS DEL DUEÑO: {len(abiertas)} abiertos de {len(items)}")
        for i in items:
            print(f"  [{i['estado'].upper():<14}] {i['titulo']}\n      evidencia: {i['evidencia']}\n      bloquea: {', '.join(i['bloquea'])}\n      se cierra: {i['como_se_cierra']}")
    return 5 if (a.estricto and abiertas) else 0


if __name__ == "__main__":
    sys.exit(main())
