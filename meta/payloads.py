"""Presupuesto de campaña y payloads de creación para la Marketing API (D7, docs/06 N06 y N11).

``calcular_presupuesto`` reproduce las fórmulas de ``departamentos/08-campanas-meta.md`` §3.4 (Anexo
A3, espejadas hoy en ``.claude/skills/d7-campanas-meta/scripts/d7.py presupuesto``, que esta función
vuelve redundante: ver «Pedidos» en ``meta/README.md``) y de ``scripts.validar_esquemas.regla_campana``/
``_regla_spend_cap`` (la misma aritmética que valida ``campana.json``, para que lo que este módulo
construye sea lo que el validador acepta):

* ``n_anuncios = min(n_anuncios_paquete, campana.n_anuncios_tope, techo_total // (k_corte × cpa_max))``,
  bajado mientras no quepa en ``total_visible_max`` (abajo), nunca por debajo de ``campana.n_anuncios_min``
  (menos anuncios, **no** menos gasto por anuncio; si no entra ni con el mínimo, ``ErrorLimite``).
* ``total_visible_max = floor(techo_total / (spend_cap_factor × (1 + tarifa_meta_bp/10000)))`` (el
  ``spend_cap`` facturado con la tarifa de Meta no puede pasar del techo del test).
* ``corte = n_anuncios × testeo.k_corte × cpa_max``; ``validar = testeo.n_dec × cpa_esperado``. Si
  ``validar > total_visible_max``: ``total_plan = corte`` y se declara ``solo_refuta=True`` (un test así
  descarta pero no confirma un ganador; subir el techo es decisión del dueño). Si no: ``total_plan =
  max(corte, validar)``.
* ``total_test = (min(total_plan, total_visible_max) // dias) × dias``; ``max_teorico_diario =
  techo(diario × factor_techo_teorico_diario)`` (redondeo hacia arriba: peor caso).
* ``spend_cap = half_up(total_test × spend_cap_factor)``; si queda por debajo de
  ``campana.spend_cap_minimo_meta`` (convertido a la moneda de la campaña), ``spend_cap`` es ``null`` y
  se exige ``candado_alternativo`` (``stop_time`` + ``lifetime_budget`` ≥ ``total_test`` y ≤ el ``spend_cap``
  que se habría calculado), nunca los dos a la vez (B05/MA-08).
* ``facturado_plan = techo(total_test × (1 + tarifa_meta_bp/10000))``: la tarifa va en la factura y no se
  ve en Ads Manager (el CPA que Ads Manager muestra es ``cpa_max / (1 + tarifa)``, lo calcula quien
  arma la tarjeta, no este módulo).

Los únicos campos que ``campana.presupuesto`` acepta son los nueve de ``contratos/campana.schema.json``
(``additionalProperties: false``): quien escribe el archivo copia solo esos del resultado; el resto
(``n_anuncios``, ``k_corte``, ``cpa_max``, ``corte``, ``validar``, ``solo_refuta``, ``tarifa_meta_bp``,
``facturado_plan``, ``techo_necesario_para_validar``) es diagnóstico para la tarjeta de gate y para
``campana.economia`` (``cpa_equilibrio``, ``cpa_objetivo``, ``cpa_max``, ``k_corte``, ``n_anuncios``).

``payload_campana``/``payload_conjunto``/``payload_anuncio`` traducen un ``campana.json`` ya válido a
los objetos que ``POST``-ea la Marketing API (todo ``PAUSED``; nunca entrega, docs/06 N11).
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine import comun, limites as motor_limites, parametros as motor_parametros
from engine.errores import ErrorLimite, ErrorUso, ErrorValidacion
from engine.limites import Limites
from engine.parametros import Parametros
from meta import monedas
from scripts.validar_esquemas import dec, entero_redondeado

__all__ = [
    "CAMPOS_PRESUPUESTO_SCHEMA", "calcular_presupuesto", "main", "payload_anuncio", "payload_campana",
    "payload_conjunto", "targeting_payload",
]

_OBJETIVO_META = {"VENTAS": "OUTCOME_SALES"}
_EVENTO_OPTIMIZACION_META = {"PURCHASE": "OFFSITE_CONVERSIONS", "INITIATE_CHECKOUT": "OFFSITE_CONVERSIONS"}
_UBICACIONES_META = {"automaticas": {}, "feeds_y_reels": {"publisher_platforms": ["facebook", "instagram"], "facebook_positions": ["feed"], "instagram_positions": ["stream", "reels"]}}
# Las únicas claves que contratos/campana.schema.json acepta dentro de `presupuesto` (additionalProperties: false).
CAMPOS_PRESUPUESTO_SCHEMA = (
    "moneda", "decimales", "diario", "total_test", "dias", "spend_cap", "spend_cap_minimo_meta",
    "candado_alternativo", "max_teorico_diario",
)


def _entero_no_negativo(valor: Any, nombre: str) -> None:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ErrorValidacion(f"calcular_presupuesto: {nombre} debe ser un entero >= 0")


def _entero_positivo(valor: Any, nombre: str) -> None:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 1:
        raise ErrorValidacion(f"calcular_presupuesto: {nombre} debe ser un entero >= 1")


def calcular_presupuesto(*, moneda: str, dias: int, limites: Limites, parametros: Parametros,
                         spend_cap_minimo_meta_minor: int | None, inicio: datetime, tarifa_meta_bp: int,
                         cpa_max_minor: int, cpa_esperado_minor: int, n_anuncios_paquete: int) -> dict[str, Any]:
    """Presupuesto y ``n_anuncios`` de D7 (Anexo A3/§3.4), listos para ``campana.presupuesto``/``economia``.

    ``tarifa_meta_bp`` es SIEMPRE ``economia.entradas_usadas.tarifa_meta_bp`` (nunca un literal: quien
    llama lo lee de ``economia.json``, D3). ``cpa_max_minor``/``cpa_esperado_minor`` son
    ``economia.cpa_be``/``economia.cpa_real.central`` (o el escenario que decida la tarjeta) en la
    unidad menor de ``moneda``. ``n_anuncios_paquete`` es la cantidad de anuncios que D6 entregó
    (``len(paquete.anuncios)``), no un tope de negocio.

    ``spend_cap_minimo_meta_minor`` es el mínimo de Meta para la moneda de la campaña, ya convertido
    (un tipo de cambio registrado si la moneda no es la del parámetro); ``None`` si aún no se convirtió
    (tolerado, el ``spend_cap`` calculado queda sin comparar y la campaña no puede pasar de ``borrador``).
    ``inicio`` (UTC con zona) es el instante de activación previsto: solo se usa para ``stop_time``
    del candado alternativo (``inicio + dias``) cuando ``spend_cap`` queda en ``null``.

    Errores: ``ErrorValidacion`` (3) si un entero de entrada es inválido; ``ErrorLimite`` (5) si falta
    algún límite o parámetro necesario, o si ni con ``campana.n_anuncios_min`` anuncios el techo del
    test alcanza (fail-closed: D3 puede proponer con límites en ``null``, pero D7 no construye un
    presupuesto sin ellos).
    """
    if isinstance(dias, bool) or not isinstance(dias, int) or dias < 1:
        raise ErrorValidacion("calcular_presupuesto: dias debe ser un entero >= 1")
    _entero_no_negativo(tarifa_meta_bp, "tarifa_meta_bp")
    _entero_positivo(cpa_max_minor, "cpa_max_minor")
    _entero_positivo(cpa_esperado_minor, "cpa_esperado_minor")
    _entero_positivo(n_anuncios_paquete, "n_anuncios_paquete")

    techo_total = min(limites.valor("gasto_total_test_por_oferta"), limites.valor("perdida_max_test_por_oferta"))
    spend_cap_factor = dec(parametros.valor("campana.spend_cap_factor"))
    tarifa_fraccion = dec(tarifa_meta_bp) / dec(10000)
    total_visible_max = int((dec(techo_total) / (spend_cap_factor * (dec(1) + tarifa_fraccion))).to_integral_value(rounding=ROUND_FLOOR))

    k_corte = int(parametros.valor("testeo.k_corte"))
    n_dec = int(parametros.valor("testeo.n_dec"))
    n_tope = int(parametros.valor("campana.n_anuncios_tope"))
    n_min = int(parametros.valor("campana.n_anuncios_min"))

    n_anuncios = min(n_anuncios_paquete, n_tope, techo_total // (k_corte * cpa_max_minor))
    while n_anuncios >= n_min and n_anuncios * k_corte * cpa_max_minor > total_visible_max:
        n_anuncios -= 1
    if n_anuncios < n_min:
        raise ErrorLimite(
            f"el techo del test ({techo_total}) no alcanza para {n_min} anuncios x k_corte({k_corte}) x "
            f"cpa_max({cpa_max_minor}) con spend_cap_factor y tarifa_meta_bp={tarifa_meta_bp}: menos anuncios "
            "no es posible; subir el tope es decisión del dueño",
            detalle={"n_anuncios_min": n_min, "total_visible_max": total_visible_max},
        )

    corte = n_anuncios * k_corte * cpa_max_minor
    validar = n_dec * cpa_esperado_minor
    solo_refuta = validar > total_visible_max
    total_plan = corte if solo_refuta else max(corte, validar)

    total_test_plan = min(total_plan, total_visible_max)
    diario = total_test_plan // dias
    total_test = diario * dias
    factor_techo = dec(limites.valor("factor_techo_teorico_diario"))
    max_teorico_diario = entero_redondeado(diario * int(factor_techo * 100), 100, "techo")
    spend_cap_calculado = entero_redondeado(total_test * int(spend_cap_factor * 100), 100, "half_up")
    facturado_plan = int((dec(total_test) * (dec(1) + tarifa_fraccion)).to_integral_value(rounding=ROUND_CEILING))
    techo_necesario_para_validar = (
        int((dec(validar) * spend_cap_factor * (dec(1) + tarifa_fraccion)).to_integral_value(rounding=ROUND_CEILING))
        if solo_refuta else None
    )
    presupuesto: dict[str, Any] = {
        "moneda": moneda, "decimales": _decimales_iso(moneda), "diario": diario, "total_test": total_test,
        "dias": dias, "max_teorico_diario": max_teorico_diario, "spend_cap_minimo_meta": spend_cap_minimo_meta_minor,
        # Diagnóstico para la tarjeta de gate y campana.economia: NO forman parte de campana.presupuesto
        # (additionalProperties: false; ver CAMPOS_PRESUPUESTO_SCHEMA).
        "n_anuncios": n_anuncios, "k_corte": k_corte, "cpa_max": cpa_max_minor, "corte": corte, "validar": validar,
        "solo_refuta": solo_refuta, "tarifa_meta_bp": tarifa_meta_bp, "facturado_plan": facturado_plan,
        "techo_necesario_para_validar": techo_necesario_para_validar,
    }
    if spend_cap_minimo_meta_minor is not None and spend_cap_calculado < spend_cap_minimo_meta_minor:
        lifetime = max(total_test, min(spend_cap_calculado, spend_cap_minimo_meta_minor - 1))
        presupuesto["spend_cap"] = None
        presupuesto["candado_alternativo"] = {
            "tipo": "stop_time_lifetime_budget", "stop_time": comun.iso_z(inicio + timedelta(days=dias)), "lifetime_budget": lifetime,
        }
    else:
        presupuesto["spend_cap"] = spend_cap_calculado
        presupuesto["candado_alternativo"] = None
    return presupuesto


def _decimales_iso(moneda: str) -> int:
    from scripts.validar_esquemas import EXPONENTE_ISO4217
    exp = EXPONENTE_ISO4217.get(moneda)
    if exp is None:
        raise ErrorValidacion(f"calcular_presupuesto: moneda sin exponente ISO 4217 registrado: {moneda!r}")
    return exp


def payload_campana(campana: Mapping[str, Any]) -> dict[str, Any]:
    """Payload de ``POST act_<id>/campaigns``: ``PAUSED`` siempre (nunca entrega, docs/06 N11)."""
    objetivo = _OBJETIVO_META.get(campana["objetivo"])
    if objetivo is None:
        raise ErrorValidacion(f"payload_campana: objetivo desconocido {campana['objetivo']!r}")
    payload: dict[str, Any] = {
        "name": campana["nombres"]["campana"], "objective": objetivo, "status": "PAUSED",
        "special_ad_categories": list(campana.get("special_ad_categories") or []),
        "buying_type": "AUCTION",
    }
    presupuesto = campana["presupuesto"]
    if presupuesto.get("spend_cap") is not None:
        payload["spend_cap"] = monedas.a_unidad_meta(presupuesto["spend_cap"], presupuesto["moneda"])
    return payload


def targeting_payload(campana: Mapping[str, Any]) -> dict[str, Any]:
    """El sub-objeto ``targeting`` que ``payload_conjunto`` manda a ``POST act_<id>/adsets``.

    Aparte para que ``meta.activar`` pueda reconstruir el targeting ESPERADO desde ``campana.json`` y
    compararlo con el que lee en vivo (A5, docs/06 N12) sin necesitar ``campaign_id``/``pixel_id``
    (que ``payload_conjunto`` solo usa para ``campaign_id``/``promoted_object``, ajenos al targeting).
    """
    audiencia = campana["audiencia"]
    return {
        "geo_locations": {"countries": list(campana["paises"])},
        "age_min": audiencia["edad_min"], "age_max": audiencia["edad_max"],
        **({"genders": [1]} if audiencia["genero"] == "mujeres" else {"genders": [2]} if audiencia["genero"] == "hombres" else {}),
        **({"flexible_spec": [{"interests": [{"name": i} for i in audiencia["intereses"]]}]} if audiencia.get("intereses") else {}),
        "publisher_platforms": _UBICACIONES_META.get(campana["ubicaciones"], {}).get("publisher_platforms", ["facebook", "instagram"]),
    }


def payload_conjunto(campana: Mapping[str, Any], *, campaign_id: str, pixel_id: str) -> dict[str, Any]:
    """Payload de ``POST act_<id>/adsets``: presupuesto diario o candado alternativo, ``PAUSED``."""
    presupuesto = campana["presupuesto"]
    evento_meta = _EVENTO_OPTIMIZACION_META.get(campana["evento_optimizacion"])
    if evento_meta is None:
        raise ErrorValidacion(f"payload_conjunto: evento_optimizacion desconocido {campana['evento_optimizacion']!r}")
    payload: dict[str, Any] = {
        "name": campana["nombres"]["conjunto"], "campaign_id": campaign_id, "status": "PAUSED",
        "optimization_goal": evento_meta, "billing_event": "IMPRESSIONS", "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        "promoted_object": {"pixel_id": pixel_id, "custom_event_type": campana["evento_optimizacion"]},
        "targeting": targeting_payload(campana),
    }
    candado = presupuesto.get("candado_alternativo")
    if candado:
        payload["lifetime_budget"] = monedas.a_unidad_meta(candado["lifetime_budget"], presupuesto["moneda"])
        if candado.get("stop_time"):
            payload["end_time"] = candado["stop_time"]
    else:
        payload["daily_budget"] = monedas.a_unidad_meta(presupuesto["diario"], presupuesto["moneda"])
    return payload


def payload_anuncio(anuncio: Mapping[str, Any], *, adset_id: str, creative_id: str) -> dict[str, Any]:
    """Payload de ``POST act_<id>/ads``: referencia a un creativo ya subido (D6), ``PAUSED``."""
    return {"name": anuncio["ad_name"], "adset_id": adset_id, "status": "PAUSED", "creative": {"creative_id": creative_id}}


# ----------------------------------------------------------------------------------------------
# CLI (A3, ola 2 B5b): sin red (lee economia.json, limites.yaml y parametros.yaml, calcula, imprime).
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """``python -m meta.payloads presupuesto --economia economia.json --n-anuncios-paquete N …``.

    Sin ``--modo``: no hay efecto externo (no llama a Meta, no escribe nada); solo lee
    ``economia.json`` (D3) y los límites/parámetros de la raíz y aplica :func:`calcular_presupuesto`.
    Salidas: 0 correcto · 2 uso · 3 validación · 5 límite o parámetro faltante.
    """
    ap = argparse.ArgumentParser(prog="python -m meta.payloads", description="Presupuesto de D7 (Anexo A3/§3.4): tarifa, n_anuncios y total.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("presupuesto")
    s.add_argument("--economia", required=True, dest="economia_ruta", help="ruta a economia.json (D3)")
    s.add_argument("--n-anuncios-paquete", required=True, type=int, dest="n_anuncios_paquete", help="len(paquete.anuncios), D6")
    s.add_argument("--escenario", choices=("pes", "central", "opt"), default="central", help="economia.cpa_real.<escenario> como cpa_esperado")
    s.add_argument("--dias", type=int, help="por defecto economia.dias_test")
    s.add_argument("--spend-cap-minimo-meta", type=int, dest="spend_cap_minimo_meta", help="ya convertido a la unidad menor de la moneda")
    s.add_argument("--raiz", help="raíz alternativa (solo con FABRICA_ENTORNO distinto de produccion)")
    s.add_argument("--ahora", help="instante UTC con Z para 'inicio' (candado alternativo); por defecto ahora")
    s.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if (args.raiz or args.ahora) and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz y --ahora no existen con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz(env)
        inicio = comun.parsear_z(args.ahora) if args.ahora else comun.ahora_utc()
        economia = comun.cargar_json(Path(args.economia_ruta))
        lim = motor_limites.cargar_limites(raiz / "empresa" / "limites.yaml", env=env)
        par = motor_parametros.cargar_parametros(raiz / "empresa" / "parametros.yaml")
        entradas = economia.get("entradas_usadas") or {}
        moneda = entradas.get("moneda") or economia["cpa_be"]["moneda"]
        resultado = calcular_presupuesto(
            moneda=moneda, dias=args.dias or economia["dias_test"], limites=lim, parametros=par,
            spend_cap_minimo_meta_minor=args.spend_cap_minimo_meta, inicio=inicio,
            tarifa_meta_bp=int(entradas.get("tarifa_meta_bp") or 0),
            cpa_max_minor=economia["cpa_be"]["monto"], cpa_esperado_minor=economia["cpa_real"][args.escenario]["monto"],
            n_anuncios_paquete=args.n_anuncios_paquete,
        )
        if args.json:
            print(comun.json_canonico({"ok": True, "modo": "dry_run", "codigo": 0, "datos": resultado, "avisos": []}).decode("utf-8"))
        else:
            import json as _json

            print(_json.dumps(resultado, indent=2, ensure_ascii=False, sort_keys=True))
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
