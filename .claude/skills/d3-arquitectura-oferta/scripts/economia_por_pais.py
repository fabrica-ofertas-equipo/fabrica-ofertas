"""Envoltorio de ``engine.factibilidad``: la economía de D3 POR PAÍS del clúster, sin una sola fórmula propia.

La economía la calcula ``engine.factibilidad`` (D-01: una sola fórmula en todo el sistema). Este script solo (1) arma las entradas de
cada país a partir de una base común y los datos propios de cada país (IVA, recargo de Meta, CPM, mezcla de métodos), (2) llama a
``engine.factibilidad.documento_economia`` una vez por país, (3) elige el PEOR país (menor ``razon``) y escribe SU ``economia.json``
(el contrato guarda uno solo; ``contratos/economia.schema.json``), (4) re-verifica el archivo escrito con ``engine.factibilidad.verificar``
y (5) imprime la tabla por país que va arriba de ``oferta.md``.

Uso (desde la raíz del repositorio)::

    .venv/bin/python .claude/skills/d3-arquitectura-oferta/scripts/economia_por_pais.py --plan PLAN.json \
        [--parametros empresa/parametros.yaml] [--limites empresa/limites.yaml] \
        [--salida-economia ofertas/<id>/03-oferta/economia.json] [--salida-tabla TABLA.md] [--json]

El evento de optimización (``Purchase`` o ``InitiateCheckout``) lo decide el motor con ``estadistica.meta_eventos_aprendizaje_semana`` y
``estadistica.meta_fraccion_min_purchase`` de ``--parametros`` (el plan NO los lleva; si faltan, sale 5). Sin ``--parametros`` no se calcula.

``PLAN.json`` (ver ``templates/plan-economia.json``)::

    {"oferta_id": "OF-AAAAMM-NN", "version": "v1", "origen_version": "maker",
     "base": {<entradas comunes de engine.factibilidad: moneda, precio, precio_bump, tasa_*_bp, comision_*, escenarios, gasto_diario, ...>},
     "paises": {"IT": {"tasa_iva_bp": 2200, "tarifa_meta_bp": 300, ...}, "FR": {...}}}

Cada país sobreescribe claves de ``base`` (las que empiezan por ``_`` o ``fuente_`` son anotaciones y se ignoran). Salida 0 aunque el
veredicto sea NO_FACTIBLE (el veredicto es un dato, no un error); 2 uso; 3 entrada inválida o ``verificar`` con diferencias; 5 falta un
parámetro (el umbral ausente falla cerrado, igual que el motor). Sin red, sin credenciales, sin efectos fuera de ``--salida-*``.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

RAIZ = Path(os.environ.get("D3_RAIZ_REPO") or Path(__file__).resolve().parents[4])
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from engine import factibilidad as F  # noqa: E402  (tras ajustar sys.path)
from engine.errores import ErrorFabrica, ErrorValidacion, ParametroFaltante, codigo_de_excepcion  # noqa: E402

ORDEN_VEREDICTO = {"NO_FACTIBLE": 0, "AJUSTADA": 1, "FACTIBLE": 2}
# Hechos de plataforma del evento de optimización: la clave canónica es ``estadistica.*`` (LT-44 a; NO ``economia.*``). El motor los pide como
# ``eventos_semana_aprendizaje`` y ``fraccion_aprendizaje_min_bp`` (bp = fracción × 10000, igual que ``decision/entradas.py``).
CLAVE_EVENTOS = "estadistica.meta_eventos_aprendizaje_semana"
CLAVE_FRACCION = "estadistica.meta_fraccion_min_purchase"


def _parametro(parametros: Any, clave: str) -> Any:
    grupo, _, nombre = clave.partition(".")
    try:
        valor = parametros["grupos"][grupo][nombre]["valor"]
    except (TypeError, KeyError):
        valor = None
    if valor is None:
        raise ParametroFaltante(clave)   # falla cerrado: sin ellos el motor asumiría Purchase en silencio
    return valor


def aprendizaje_de_parametros(parametros: Any) -> dict[str, int]:
    """``{eventos_semana_aprendizaje, fraccion_aprendizaje_min_bp}`` desde ``estadistica.*`` (``ParametroFaltante`` si faltan)."""
    eventos = _parametro(parametros, CLAVE_EVENTOS)
    if not isinstance(eventos, int) or isinstance(eventos, bool) or eventos < 1:
        raise ErrorValidacion(f"{CLAVE_EVENTOS} debe ser un entero >= 1, llegó {eventos!r}")
    try:
        bp = Fraction(str(_parametro(parametros, CLAVE_FRACCION))) * 10000
    except (ValueError, ZeroDivisionError) as exc:
        raise ErrorValidacion(f"{CLAVE_FRACCION} no es una fracción decimal válida") from exc
    if bp.denominator != 1 or not 0 < bp <= 10000:
        raise ErrorValidacion(f"{CLAVE_FRACCION} debe ser una fracción en (0, 1] con a lo sumo 4 decimales (bp enteros)")
    return {"eventos_semana_aprendizaje": eventos, "fraccion_aprendizaje_min_bp": int(bp)}


def _base_del_plan(base: Mapping[str, Any], parametros: Any) -> dict[str, Any]:
    """``base`` + los parámetros del evento de aprendizaje de ``estadistica.*``. Un valor distinto en el plan es un override sin fuente: se rechaza.

    Si el plan fija ``evento_optimizacion_inicial`` (solo para reproducir un ``economia.json`` ya existente; el Maker NO decide el evento) no se
    añaden: el motor usa ese evento tal cual.
    """
    base = copy.deepcopy(dict(base))
    if base.get("evento_optimizacion_inicial") is not None:
        return base
    for clave, valor in aprendizaje_de_parametros(parametros).items():
        if clave in base and base[clave] != valor:
            raise ErrorValidacion(f"el plan trae {clave}={base[clave]!r} pero el valor sale de estadistica.* ({valor!r}); quita la clave del plan")
        base[clave] = valor
    return base


def _entradas_de_pais(base: Mapping[str, Any], pais: str, datos: Mapping[str, Any]) -> dict[str, Any]:
    """``base`` con los datos del país encima; descarta anotaciones (``_*``, ``fuente_*``) que el motor no usa."""
    entradas = copy.deepcopy(dict(base))
    for clave, valor in datos.items():
        if clave.startswith("_") or clave.startswith("fuente_"):
            continue
        entradas[clave] = copy.deepcopy(valor)
    entradas["pais"] = pais  # informativo; el motor ignora claves desconocidas
    return entradas


def economia_por_pais(plan: Mapping[str, Any], parametros: Any = None, limites: Any = None) -> dict[str, Any]:
    """``{"paises": {pais: documento_economia}, "peor": pais, "veredicto_cluster": str}`` (todo lo calcula el motor)."""
    for clave in ("oferta_id", "base", "paises"):
        if clave not in plan:
            raise ErrorValidacion(f"el plan no trae {clave!r}")
    if not isinstance(plan["paises"], Mapping) or not plan["paises"]:
        raise ErrorValidacion("paises debe ser un mapa pais -> datos con al menos un país")
    version = plan.get("version", "v1")
    origen = plan.get("origen_version", "maker")
    base = _base_del_plan(plan["base"], parametros)
    docs: dict[str, dict[str, Any]] = {}
    for pais, datos in plan["paises"].items():
        entradas = _entradas_de_pais(base, pais, datos or {})
        docs[pais] = F.documento_economia(entradas, parametros, limites, oferta_id=plan["oferta_id"], version=version,
                                          origen_version=origen)
    monedas = {d["entradas_usadas"]["moneda"] for d in docs.values()}
    if len(monedas) != 1:
        raise ErrorValidacion(f"una oferta tiene una sola moneda de cobro; el plan mezcla {sorted(monedas)}")
    peor = min(docs, key=lambda p: (ORDEN_VEREDICTO[docs[p]["veredicto"]], Fraction(docs[p]["razon"])))
    return {"paises": docs, "peor": peor, "veredicto_cluster": docs[peor]["veredicto"]}


def _monto(d: Mapping[str, Any]) -> str:
    m = d["monto"]
    return f"{m // 100},{m % 100:02d} {d['moneda']}"


def tabla_markdown(resultado: Mapping[str, Any]) -> str:
    """Tabla por país (cifras del motor, formateadas) para la cabecera de ``oferta.md``. Los importes asumen 2 decimales de moneda."""
    filas = ["| País | IVA (bp) | Meta (bp) | AOV | CPA be visto | CPA obj | CPA real central | razón | razón obj | veredicto | presup. test mín | días | pérdida máx. test |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for pais, d in resultado["paises"].items():
        e = d["entradas_usadas"]
        filas.append(
            f"| {pais}{' (peor)' if pais == resultado['peor'] else ''} | {e['tasa_iva_bp']} | {e['tarifa_meta_bp']} | {_monto(d['aov'])} | "
            f"{_monto(d['cpa_be_visto'])} | {_monto(d['cpa_obj'])} | {_monto(d['cpa_real']['central'])} | {d['razon']} | {d['razon_obj']} | "
            f"{d['veredicto']} | {_monto(d['presupuesto_test_min'])} | {d['dias_test']} | {_monto(d['perdida_max_test'])} |")
    filas.append("")
    filas.append(f"Veredicto del clúster = el del peor país ({resultado['peor']}): **{resultado['veredicto_cluster']}**. "
                 f"Cifras de `engine.factibilidad` {F.VERSION}; nada calculado a mano.")
    return "\n".join(filas) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="economia_por_pais.py", description=__doc__.splitlines()[0])
    ap.add_argument("--plan", required=True)
    ap.add_argument("--parametros", help="parametros.yaml (razon_min_factible, k_corte, n_dec, penal_evento_senal)")
    ap.add_argument("--limites", help="limites.yaml (para limites_pendientes)")
    ap.add_argument("--salida-economia", help="escribe aquí el economia.json del PEOR país")
    ap.add_argument("--salida-tabla", help="escribe aquí la tabla Markdown por país")
    ap.add_argument("--json", action="store_true", help="imprime el resultado completo como JSON")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code not in (0, None) else 0
    try:
        par = F._cargar(args.parametros) if args.parametros else None
        lim = F._cargar(args.limites) if args.limites else None
        res = economia_por_pais(F._cargar(args.plan), par, lim)
        peor = res["paises"][res["peor"]]
        if args.salida_economia:
            F._escribir_atomico(Path(args.salida_economia), json.dumps(peor, ensure_ascii=False, indent=2) + "\n")
            difs = F.verificar(F._cargar(args.salida_economia), par, lim)
            if difs:
                for d in difs:
                    print(f"DIFERENCIA {d}", file=sys.stderr)
                return ErrorValidacion.codigo_salida
        tabla = tabla_markdown(res)
        if args.salida_tabla:
            F._escribir_atomico(Path(args.salida_tabla), tabla)
        if args.json:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        else:
            print(tabla, end="")
        return 0
    except ErrorFabrica as exc:
        print(f"ERROR: {exc.mensaje}", file=sys.stderr)
        return codigo_de_excepcion(exc)
    except (KeyError, TypeError, ZeroDivisionError, AttributeError) as exc:
        print(f"ERROR: entrada con forma inválida ({type(exc).__name__}: {exc})", file=sys.stderr)
        return ErrorValidacion.codigo_salida


if __name__ == "__main__":
    sys.exit(main())
