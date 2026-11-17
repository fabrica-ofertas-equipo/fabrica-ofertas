"""Economía única de la fábrica (D-01, hallazgo C14): ``economia.json`` sale de AQUÍ y de ningún otro sitio.

Una sola fórmula en todo el sistema. ``decision.presupuesto.economia_por_pedido`` la envuelve y la regla X14 de
``scripts/validar_esquemas.py`` la llama; el ``scripts/factibilidad.py`` de la v1 se retiró.

Comando exacto (desde la raíz del repositorio; sin red ni credenciales)::

    .venv/bin/python -m engine.factibilidad calcular --entradas ENTRADAS.json [--parametros empresa/parametros.yaml] \
        [--limites empresa/limites.yaml] [--salida 03-oferta/economia.json]
    .venv/bin/python -m engine.factibilidad verificar --economia ofertas/<id>/03-oferta/economia.json [--parametros ...]

Salida: 0 correcto · 2 uso · 3 entrada inválida o ``verificar`` con diferencias · 5 falta un parámetro (``ParametroFaltante``).
Con ``limites.yaml`` en ``null`` NO sale 5: la factibilidad se calcula y ``limites_pendientes[]`` lista lo que falta (sin límites
la oferta se calcula pero no autoriza gasto; eso lo cierra ``engine.guard``).

Fórmulas (precio con IVA incluido; todo en enteros de la unidad menor y puntos básicos, aritmética exacta con ``Fraction``,
redondeo ``ROUND_HALF_EVEN`` al emitir cada magnitud; sin ``float``. Las derivadas parten de la magnitud YA emitida:
``cpa_be`` -> ``cpa_be_visto`` -> ``cpa_obj`` (p. ej. Italia: visto 1120 desde 1154, no desde la fracción); ``razon`` y
``resultado_esperado_central`` usan el CPA real sin redondear. La razón impresa (2 decimales) es informativa: el veredicto
usa la razón exacta)::

    aov      = P + b·Pb + u·Pu                    (b, u = fracciones de pedidos con bump / upsell)
    neto     = aov / (1 + t)                      (t = tasa_iva_bp; IVA = aov − neto)
    comision = (pct + recargos + conversion)·aov + fija·(1 + u)         (con mix_metodos: promedio ponderado por método)
    stripe_tax = pct_tax·aov + fijo_tax·(1 + u)
    mc       = neto − comision − stripe_tax − r·neto − d·(neto + tarifa_disputa) − costo_variable
    cpa_be   = mc                                 (la comisión NO se devuelve al reembolsar: r multiplica el neto)
    cpa_be_visto = cpa_be·10000 / (10000 + tarifa_meta_bp)   (CPA que se ve en Ads Manager)
    cpa_obj  = f·cpa_be_visto                     roas_be = aov / cpa_be
    cpa_real(esc) = cpm·100000 / (ctr_enlace_bp·clic_compra_bp)         razon = cpa_be_visto / cpa_real(central)
    presupuesto_test_min = max(5·k·cpa_be, n_dec·cpa_real(central))     dias_test = max(7, ⌈presupuesto_test_min / diario⌉)
    gasto_test_plan = diario·dias_test            perdida_max_test = gasto_test_plan + costos_fijos_oferta
    resultado_esperado_central = gasto_test_plan·(cpa_be_visto / cpa_real(central) − 1)   (contrato 1.2.0, CT2-06)
        gasto_test_plan es el gasto FACTURADO (incluye la tarifa de Meta); compras = gasto/((1 + m)·cpa_real) y cada una deja cpa_be,
        así el signo coincide siempre con ``razon`` (< 1 ⇒ pierde). Sin tarifa de Meta equivale a la fórmula de 1.1.0.

Vectores de referencia del plano (docs/08 §3.1; ``tests/contratos/test_factibilidad.py`` los reproduce):

    24,42  CPA_BE (= MC) del ejemplo de D3 §3.4: P 27, bump 10 % × 9, 2,9 % + 0,30, r 7 %, d 0,5 %, tarifa de disputa 15, costo 0,20 (USD).
    16,25  MC de F1 §3.5: P 17, bump 30 % × 7, 4,4 % + 0,30 (2,9 + 1,5 internacional), r 7 %, d 0,5 %, costo 0,20 (USD).
    11,54  CPA_BE de Italia base (nota 16 §2.2): frontal 17,28 con IVA 22 %, 5,4 % + 0,30 (2,9 + 1,5 + 1), Stripe Tax 0,5 %, r 8 %,
           d 0,6 %, sin bump ni costo variable (USD); visto en Ads Manager con Meta +3 %: 11,20.

Este módulo importa solo ``engine.errores`` (sin ciclos con ``scripts.validar_esquemas``, que lo llama de forma perezosa).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine.errores import ErrorFabrica, ErrorUso, ErrorValidacion, ParametroFaltante, codigo_de_excepcion

__all__ = ["VERSION", "calcular", "economia_unitaria", "documento_economia", "verificar", "main"]

VERSION = "1.2.0"

BP = 10000                       # un punto básico = 1/10000
# Constantes DE LA FÓRMULA de D3 §3.4 (no son umbrales operativos; se pueden sobrescribir desde las entradas).
FACTOR_PRESUPUESTO_MIN_K = 5     # presupuesto_test_min = 5·k·cpa_be …
DIAS_MIN_TEST = 7                # … y el test dura al menos una semana completa
IVA_MAX_BP = 100000              # cota de cordura del IVA (1000 %): una tasa mayor es un error de unidades, no un impuesto
RAZON_EQUILIBRIO = Fraction(1)   # razon < 1 ⇒ el escenario central pierde dinero ⇒ NO_FACTIBLE

# Claves de ``entradas_usadas`` del esquema ``economia`` (el resto de las entradas son de planificación y no se escriben ahí).
_CLAVES_ENTRADAS_USADAS = (
    "tarifas_fecha", "tarifas_fuente", "moneda", "precio", "precio_bump", "tasa_bump_bp", "tasa_reembolso_bp", "tasa_disputa_bp",
    "comision_pct_bp", "comision_fija", "tarifa_disputa", "costo_variable", "factor_cpa_objetivo_bp", "escenarios",
    "tasa_iva_bp", "stripe_tax", "tarifa_meta_bp", "recargos_bp", "conversion_bp", "tarifas_origen", "costos_fijos_oferta",
)
_ESCENARIOS = ("pes", "central", "opt")


# --------------------------------------------------------------------------------------------------------------------
# Aritmética exacta y formato
# --------------------------------------------------------------------------------------------------------------------
def _redondear(x: Fraction) -> int:
    """Entero más cercano; el empate va al par (``ROUND_HALF_EVEN``)."""
    return round(x)


def _div(a: int | Fraction, b: int | Fraction) -> Fraction:
    """División exacta (nunca ``float``)."""
    if b == 0:
        raise ErrorValidacion("división por cero en la economía (ctr, conversión o tasa en 0)")
    return Fraction(a) / Fraction(b)


def _texto(x: Fraction, decimales: int, *, recortar: bool) -> str:
    """Decimal como cadena con ``decimales`` (half-even); ``recortar`` quita ceros finales (``28.125``, ``0.022``)."""
    if x < 0:
        raise ErrorValidacion("magnitud negativa donde el contrato exige un decimal no negativo")
    escalado = _redondear(x * 10 ** decimales)
    cadena = f"{escalado:0{decimales + 1}d}"
    entera, fraccion = cadena[: len(cadena) - decimales], cadena[len(cadena) - decimales:]
    if recortar:
        fraccion = fraccion.rstrip("0")
    return f"{entera}.{fraccion}" if fraccion else entera


def _entero(valor: Any, nombre: str, *, minimo: int = 0, maximo: int | None = None) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErrorValidacion(f"{nombre}: se esperaba un entero (dinero en unidad menor, tasas en puntos básicos), llegó {type(valor).__name__}")
    if valor < minimo:
        raise ErrorValidacion(f"{nombre}: debe ser >= {minimo}")
    if maximo is not None and valor > maximo:
        raise ErrorValidacion(f"{nombre}: debe ser <= {maximo}")
    return valor


def _dinero(entradas: Mapping[str, Any], clave: str, moneda: str, *, defecto: int | None = None) -> int:
    """Monto entero de ``entradas[clave]`` (``{"monto", "moneda"}`` o un entero ya en la moneda de la economía)."""
    if clave not in entradas or entradas[clave] is None:
        if defecto is None:
            raise ErrorValidacion(f"falta la entrada {clave}")
        return defecto
    v = entradas[clave]
    if isinstance(v, Mapping):
        if v.get("moneda") != moneda:
            raise ErrorValidacion(f"{clave}: moneda {v.get('moneda')!r} distinta de {moneda!r} (monedas mezcladas)")
        v = v.get("monto")
    return _entero(v, clave)


def _bp(entradas: Mapping[str, Any], clave: str, *, defecto: int | None = None, maximo: int = BP) -> int:
    """Tasa en puntos básicos enteros, ``0 <= bp <= maximo`` (por defecto 100 %; el IVA admite hasta 1000 %, cota de cordura)."""
    if clave not in entradas or entradas[clave] is None:
        if defecto is None:
            raise ErrorValidacion(f"falta la entrada {clave}")
        return defecto
    return _entero(entradas[clave], clave, maximo=maximo)


def _parametro(parametros: Any, clave: str) -> Any:
    """Valor de ``grupo.clave`` de un ``engine.parametros.Parametros`` o del mapa cargado de ``parametros.yaml``; ``None`` si falta."""
    if parametros is None:
        return None
    if hasattr(parametros, "valor"):
        try:
            return parametros.valor(clave)
        except ParametroFaltante:
            return None
    grupo, _, nombre = clave.partition(".")
    try:
        return parametros["grupos"][grupo][nombre]["valor"]
    except (TypeError, KeyError):
        return None


def _umbral(entradas: Mapping[str, Any], parametros: Any, clave_entrada: str, clave_parametro: str, *, estricto: bool) -> Any:
    """Umbral de las entradas o de ``parametros``; sin ninguno falla cerrado (``ParametroFaltante``, salida 5) salvo ``estricto=False``."""
    if entradas.get(clave_entrada) is not None:
        return entradas[clave_entrada]
    valor = _parametro(parametros, clave_parametro)
    if valor is None and estricto:
        raise ParametroFaltante(clave_parametro, "sin valor: la factibilidad no inventa umbrales")
    return valor


def _fraccion_decimal(valor: Any, nombre: str) -> Fraction:
    """Fracción exacta desde una cadena decimal (``"1.3"``) o un entero; el ``float`` está prohibido."""
    if isinstance(valor, float) or isinstance(valor, bool):
        raise ErrorValidacion(f"{nombre}: los decimales van como cadena, no como float")
    try:
        return Fraction(str(valor))
    except (ValueError, ZeroDivisionError) as exc:
        raise ErrorValidacion(f"{nombre}: decimal inválido {valor!r}") from exc


# --------------------------------------------------------------------------------------------------------------------
# Núcleo: economía por pedido
# --------------------------------------------------------------------------------------------------------------------
def _comision(entradas: Mapping[str, Any], moneda: str) -> tuple[Fraction, Fraction, Fraction]:
    """(tasa total sobre el AOV, fija por transacción, tarifa de disputa) en fracciones exactas.

    Sin ``mix_metodos`` es ``comision_pct_bp + recargos_bp + conversion_bp``, ``comision_fija`` y ``tarifa_disputa``.
    Con ``mix_metodos`` (lista de ``{metodo, peso_bp, comision_pct_bp, comision_fija, tarifa_disputa?}``; los pesos suman 10000) es el
    promedio ponderado; el resultado debe ser entero (bp y unidad menor) para que ``economia.json`` siga siendo reproducible.
    """
    recargos = _bp(entradas, "recargos_bp", defecto=0) + _bp(entradas, "conversion_bp", defecto=0)
    mezcla = entradas.get("mix_metodos")
    if not mezcla:
        return (Fraction(_bp(entradas, "comision_pct_bp") + recargos, BP), Fraction(_dinero(entradas, "comision_fija", moneda)),
                Fraction(_dinero(entradas, "tarifa_disputa", moneda)))
    if sum(_entero(m.get("peso_bp"), "mix_metodos.peso_bp", maximo=BP) for m in mezcla) != BP:
        raise ErrorValidacion("mix_metodos: los pesos (peso_bp) deben sumar 10000")
    pct = fija = disputa = Fraction(0)
    for m in mezcla:
        peso = Fraction(m["peso_bp"], BP)
        pct += peso * _entero(m.get("comision_pct_bp"), "mix_metodos.comision_pct_bp", maximo=BP)
        fija += peso * _dinero(m, "comision_fija", moneda)
        disputa += peso * _dinero(m, "tarifa_disputa", moneda, defecto=_dinero(entradas, "tarifa_disputa", moneda))
    for nombre, v in (("comision_pct_bp", pct), ("comision_fija", fija), ("tarifa_disputa", disputa)):
        if v.denominator != 1:
            raise ErrorValidacion(f"mix_metodos: el promedio ponderado de {nombre} no es entero ({v}); ajustá los pesos o usá bp enteros")
    return (pct + recargos) / BP, fija, disputa


def economia_unitaria(entradas: Mapping[str, Any]) -> dict[str, Any]:
    """Economía de UN pedido esperado: AOV, IVA, neto, comisiones, reembolso, disputa, MC y CPA de equilibrio.

    Entradas (las de ``economia.entradas_usadas``; dinero como ``{"monto", "moneda"}`` o entero en la ``moneda`` dada; los campos de la
    1.1.0 valen 0 si faltan; opcionales ``precio_upsell``/``tasa_upsell_bp`` y ``mix_metodos``). Devuelve enteros (``mc_con_signo`` puede
    ser negativo; ``mc``/``cpa_be`` se acotan a 0), más ``exactos`` con las fracciones sin redondear para los cálculos encadenados.
    """
    if not isinstance(entradas.get("moneda"), str) or not re.fullmatch(r"[A-Z]{3}", entradas["moneda"]):
        raise ErrorValidacion("moneda debe ser un código ISO 4217 de tres letras mayúsculas (EUR, USD…)")
    moneda = entradas["moneda"]
    precio = _dinero(entradas, "precio", moneda)
    if precio <= 0:
        raise ErrorValidacion("precio debe ser > 0")
    b = Fraction(_bp(entradas, "tasa_bump_bp"), BP)
    u = Fraction(_bp(entradas, "tasa_upsell_bp", defecto=0), BP)
    aov = precio + b * _dinero(entradas, "precio_bump", moneda) + u * _dinero(entradas, "precio_upsell", moneda, defecto=0)
    transacciones = 1 + u                       # el upsell es una segunda transacción: la tarifa fija se paga de nuevo
    t = Fraction(_bp(entradas, "tasa_iva_bp", defecto=0, maximo=IVA_MAX_BP), BP)
    neto = _div(aov, 1 + t)
    pct, fija, tarifa_disputa = _comision(entradas, moneda)
    comisiones = pct * aov + fija * transacciones
    tax = entradas.get("stripe_tax") or {"pct_bp": 0, "fijo": 0}
    stripe_tax = Fraction(_bp(tax, "pct_bp", defecto=0), BP) * aov + _dinero(tax, "fijo", moneda, defecto=0) * transacciones
    reembolso = Fraction(_bp(entradas, "tasa_reembolso_bp"), BP) * neto
    disputa = Fraction(_bp(entradas, "tasa_disputa_bp"), BP) * (neto + tarifa_disputa)
    costo = _dinero(entradas, "costo_variable", moneda)
    mc = neto - comisiones - stripe_tax - reembolso - disputa - costo
    mc_int = _redondear(mc)
    cpa_be = max(mc_int, 0)
    meta = _bp(entradas, "tarifa_meta_bp", defecto=0)
    visto = _redondear(_div(cpa_be * BP, BP + meta))
    factor = _bp(entradas, "factor_cpa_objetivo_bp")
    if not 0 < factor <= BP:
        raise ErrorValidacion("factor_cpa_objetivo_bp debe estar en (0, 10000]")
    return {
        "moneda": moneda,
        "aov": _redondear(aov), "iva": _redondear(aov - neto), "neto": _redondear(neto),
        "comision": _redondear(comisiones), "stripe_tax": _redondear(stripe_tax),
        "reembolso_esperado": _redondear(reembolso), "disputa_esperada": _redondear(disputa), "costo_variable": costo,
        "mc_con_signo": mc_int, "mc": cpa_be, "cpa_be": cpa_be, "cpa_be_visto": visto,
        "cpa_obj": _redondear(_div(visto * factor, BP)),
        "roas_be": None if cpa_be == 0 else _texto(_div(_redondear(aov), cpa_be), 2, recortar=False),
        "entradas_efectivas": {
            "comision_pct_bp": _redondear(pct * BP) - _bp(entradas, "recargos_bp", defecto=0) - _bp(entradas, "conversion_bp", defecto=0),
            "comision_fija": _redondear(fija), "tarifa_disputa": _redondear(tarifa_disputa),
        },
        "exactos": {"aov": aov, "neto": neto, "mc": mc},
    }


# --------------------------------------------------------------------------------------------------------------------
# Escenarios, plan del test y documento
# --------------------------------------------------------------------------------------------------------------------
def _limites_pendientes(limites: Any, operacion: str) -> list[str]:
    """Claves de ``limites.yaml`` que la operación necesita y siguen en ``null`` (sin límites cargados: todas)."""
    from scripts.validar_esquemas import CLAVES_CRITICAS  # perezoso: este módulo no importa el validador al cargarse

    if operacion not in CLAVES_CRITICAS:
        raise ErrorUso(f"operación desconocida: {operacion}")
    pendientes = []
    for clave in CLAVES_CRITICAS[operacion]:
        valor = None
        if limites is not None:
            valor = limites.get(clave) if hasattr(limites, "get") else None
        if valor in (None, [], {}):
            pendientes.append(clave)
    return pendientes


def calcular(entradas: Mapping[str, Any], parametros: Any = None, limites: Any = None, *, estricto: bool = True,
             operacion_limites: str = "gastar") -> dict[str, Any]:
    """Economía completa de una oferta: los campos derivados de ``economia`` 1.1.0 más el ``desglose`` por pedido.

    Entradas: ver :func:`economia_unitaria`, más ``escenarios`` (``pes``/``central``/``opt`` con ``cpm``, ``ctr_enlace_bp``,
    ``clic_compra_bp``) y, para el plan del test, ``gasto_diario`` (o ``gasto_test_plan`` y ``dias_test``), ``k``, ``n_dec`` y
    ``razon_min_factible`` (de las entradas o de ``parametros``: ``testeo.k_corte``, ``testeo.n_dec``, ``economia.razon_min_factible``).
    Opcionales: ``dias_test`` (fija los días), ``costos_fijos_oferta``, ``evento_optimizacion_inicial`` o ``eventos_semana_aprendizaje`` +
    ``fraccion_aprendizaje_min_bp`` + ``penal_evento_senal`` (regla de D3 para ``InitiateCheckout``), ``validada``.

    Un umbral ausente falla cerrado (``ParametroFaltante``, salida 5) salvo ``estricto=False`` (el veredicto queda en ``None``).
    Los LÍMITES en ``null`` no fallan: se devuelven en ``limites_pendientes``.
    """
    u = economia_unitaria(entradas)
    moneda = u["moneda"]
    esc = entradas.get("escenarios")
    if not isinstance(esc, Mapping) or set(esc) != set(_ESCENARIOS):
        raise ErrorValidacion("escenarios debe traer exactamente pes, central y opt")
    cpa_exacto: dict[str, Fraction] = {}
    for nombre in _ESCENARIOS:
        e = esc[nombre]
        cpm, ctr, conv = _dinero(e, "cpm", moneda), _bp(e, "ctr_enlace_bp"), _bp(e, "clic_compra_bp")
        if ctr == 0 or conv == 0:
            raise ErrorValidacion(f"escenario {nombre}: ctr_enlace_bp y clic_compra_bp deben ser > 0")
        cpa_exacto[nombre] = Fraction(cpm * BP * 10, ctr * conv)          # cpm / (1000 · ctr · conv), ctr y conv en bp
    central = esc["central"]

    # Plan del test: gasto diario, días y evento de optimización (D3 §3.4).
    k = _umbral(entradas, parametros, "k", "testeo.k_corte", estricto=estricto)
    n_dec = _umbral(entradas, parametros, "n_dec", "testeo.n_dec", estricto=estricto)
    razon_min = _umbral(entradas, parametros, "razon_min_factible", "economia.razon_min_factible", estricto=estricto)
    diario = _dinero(entradas, "gasto_diario", moneda, defecto=0) or None
    evento = entradas.get("evento_optimizacion_inicial")
    penal = Fraction(1)
    if evento is None:
        semana, minimo = entradas.get("eventos_semana_aprendizaje"), entradas.get("fraccion_aprendizaje_min_bp")
        if semana is not None and minimo is not None and diario is not None:
            necesario = _div(_entero(semana, "eventos_semana_aprendizaje", minimo=1), 7) * cpa_exacto["central"]
            evento = "InitiateCheckout" if diario < Fraction(_entero(minimo, "fraccion_aprendizaje_min_bp"), BP) * necesario else "Purchase"
        else:
            evento = "Purchase"
    if evento not in ("Purchase", "InitiateCheckout"):
        raise ErrorValidacion("evento_optimizacion_inicial debe ser Purchase o InitiateCheckout")
    if evento == "InitiateCheckout":
        penal = _fraccion_decimal(_umbral(entradas, parametros, "penal_evento_senal", "economia.penal_evento_senal", estricto=True),
                                  "penal_evento_senal")
    cpa_real = {n: cpa_exacto[n] * penal for n in _ESCENARIOS}

    cpa_be, visto, cpa_obj = u["cpa_be"], u["cpa_be_visto"], u["cpa_obj"]
    razon = _div(visto, cpa_real["central"])
    razon_obj = _div(cpa_obj, cpa_real["central"])
    veredicto = None
    if razon_min is not None:
        minimo = _fraccion_decimal(razon_min, "razon_min_factible")
        veredicto = "FACTIBLE" if razon >= minimo and cpa_be > 0 else ("NO_FACTIBLE" if razon < RAZON_EQUILIBRIO or cpa_be == 0 else "AJUSTADA")

    plan: dict[str, Any] = {"presupuesto_test_min": None, "dias_test": None, "gasto_test_plan": None, "perdida_max_test": None,
                            "resultado_esperado_central": None}
    if k is not None and n_dec is not None:
        factor_k = _entero(entradas.get("factor_presupuesto_min_k", FACTOR_PRESUPUESTO_MIN_K), "factor_presupuesto_min_k", minimo=1)
        minimo_test = _redondear(max(factor_k * _entero(k, "k", minimo=1) * cpa_be, _entero(n_dec, "n_dec", minimo=1) * cpa_real["central"]))
        plan["presupuesto_test_min"] = minimo_test
        dias = entradas.get("dias_test")
        dias_min = _entero(entradas.get("dias_min_test", DIAS_MIN_TEST), "dias_min_test", minimo=1)
        if diario is not None:
            dias_min = max(dias_min, -(-minimo_test // diario))          # max(7, ⌈presupuesto_test_min / diario⌉)
        if dias is None and diario is not None:
            dias = dias_min
        elif dias is not None and _entero(dias, "dias_test", minimo=1) < dias_min:
            raise ErrorValidacion(f"dias_test {dias} < mínimo {dias_min} de D3 §3.4 (max(7, ⌈presupuesto_test_min / gasto_diario⌉))")
        gasto_plan = _dinero(entradas, "gasto_test_plan", moneda, defecto=0) or None
        if diario is not None and dias is not None:
            gasto_plan = diario * _entero(dias, "dias_test", minimo=1)
        if gasto_plan is not None and dias is not None:
            plan.update(dias_test=dias, gasto_test_plan=gasto_plan,
                        perdida_max_test=gasto_plan + _dinero(entradas, "costos_fijos_oferta", moneda, defecto=0),
                        resultado_esperado_central=_redondear(gasto_plan * (_div(visto, cpa_real["central"]) - 1)))

    return {
        "aov": {"monto": u["aov"], "moneda": moneda},
        "mc": {"monto": u["mc"], "moneda": moneda},
        "cpa_be": {"monto": cpa_be, "moneda": moneda},
        "cpa_obj": {"monto": cpa_obj, "moneda": moneda},
        "roas_be": u["roas_be"] if u["roas_be"] is not None else "0",
        "cpa_real": {n: {"monto": _redondear(cpa_real[n]), "moneda": moneda} for n in _ESCENARIOS},
        "razon": _texto(razon, 2, recortar=False),
        "razon_obj": _texto(razon_obj, 2, recortar=False),
        "veredicto": veredicto,
        "presupuesto_test_min": None if plan["presupuesto_test_min"] is None else {"monto": plan["presupuesto_test_min"], "moneda": moneda},
        "dias_test": plan["dias_test"],
        "gasto_test_plan": None if plan["gasto_test_plan"] is None else {"monto": plan["gasto_test_plan"], "moneda": moneda},
        "perdida_max_test": None if plan["perdida_max_test"] is None else {"monto": plan["perdida_max_test"], "moneda": moneda},
        "evento_optimizacion_inicial": evento,
        "criterios_corte": None if k is None or n_dec is None else {
            "k": k, "n_dec": n_dec, "validada": entradas.get("validada") or "backbone 5.9 (parametros.veredicto)"},
        "conv_central": _texto(Fraction(central["clic_compra_bp"], BP), 4, recortar=True),
        "cpc_esperado": {"monto": _texto(Fraction(_dinero(central, "cpm", moneda) * 10, central["ctr_enlace_bp"]), 3, recortar=True), "moneda": moneda},
        "cpa_be_visto": {"monto": visto, "moneda": moneda},
        "limites_pendientes": _limites_pendientes(limites, operacion_limites),
        "resultado_esperado_central": None if plan["resultado_esperado_central"] is None else {"monto": plan["resultado_esperado_central"], "moneda": moneda},
        "desglose": {k_: v for k_, v in u.items() if k_ not in ("exactos", "roas_be", "moneda")} | {"moneda": moneda},
    }


def _normalizar_dinero(valor: Any, moneda: str) -> Any:
    """Entero (unidad menor) o ``{"monto", "moneda"}`` -> ``{"monto", "moneda"}`` (el esquema exige el objeto)."""
    return dict(valor) if isinstance(valor, Mapping) else {"monto": valor, "moneda": moneda}


def _errores_de_esquema(doc: Mapping[str, Any]) -> list[str]:
    from scripts.validar_esquemas import errores_de_esquema, ruta_json  # perezoso: el validador llama a este módulo

    return [f"{ruta_json(e) or '/'}: {e.message[:160]}" for e in errores_de_esquema("economia", doc)]


def documento_economia(entradas: Mapping[str, Any], parametros: Any = None, limites: Any = None, *, oferta_id: str | None = None,
                       version: str = "v1", origen_version: str = "maker", **kw: Any) -> dict[str, Any]:
    """``economia.json`` completo (esquema 1.2.0) a partir de las entradas: lo que escribe D3. Sin ``desglose``.

    El documento nunca sale inválido: el dinero entero se normaliza a ``{"monto", "moneda"}`` y el resultado se valida contra el esquema.
    """
    r = calcular(entradas, parametros, limites, **kw)
    faltan = [c for c in ("veredicto", "presupuesto_test_min", "dias_test", "gasto_test_plan", "perdida_max_test",
                          "criterios_corte", "resultado_esperado_central") if r[c] is None]
    if faltan:
        raise ErrorValidacion(f"economia.json incompleta: faltan entradas para {', '.join(faltan)} (gasto_diario, k, n_dec, razon_min_factible)")
    oferta_id = oferta_id or entradas.get("oferta_id")
    if not oferta_id:
        raise ErrorValidacion("falta oferta_id")
    moneda = entradas["moneda"]
    efectivas = {k_: entradas[k_] for k_ in _CLAVES_ENTRADAS_USADAS if k_ in entradas}
    efectivas.update(tasa_iva_bp=_bp(entradas, "tasa_iva_bp", defecto=0, maximo=IVA_MAX_BP), tarifa_meta_bp=_bp(entradas, "tarifa_meta_bp", defecto=0),
                     recargos_bp=_bp(entradas, "recargos_bp", defecto=0), conversion_bp=_bp(entradas, "conversion_bp", defecto=0),
                     stripe_tax=entradas.get("stripe_tax") or {"pct_bp": 0, "fijo": 0},
                     costos_fijos_oferta=_dinero(entradas, "costos_fijos_oferta", moneda, defecto=0))
    if entradas.get("mix_metodos"):   # el documento guarda los efectivos (enteros por construcción): X14 los recalcula sin la mezcla
        ef = economia_unitaria(entradas)["entradas_efectivas"]
        efectivas.update(comision_pct_bp=ef["comision_pct_bp"], comision_fija=ef["comision_fija"], tarifa_disputa=ef["tarifa_disputa"])
    for k_ in ("precio", "precio_bump", "comision_fija", "tarifa_disputa", "costo_variable", "costos_fijos_oferta"):
        if k_ in efectivas:
            efectivas[k_] = _normalizar_dinero(efectivas[k_], moneda)
    if "escenarios" in efectivas:
        efectivas["escenarios"] = {n: {**e, "cpm": _normalizar_dinero(e["cpm"], moneda)} for n, e in efectivas["escenarios"].items()}
    tax = dict(efectivas["stripe_tax"])
    tax["fijo"] = _normalizar_dinero(tax.get("fijo", 0), moneda)
    efectivas["stripe_tax"] = tax
    doc = {"schema_version": "1.2.0", "oferta_id": oferta_id, "version": version, "origen_version": origen_version,
           "script_version": VERSION, "entradas_usadas": efectivas}
    doc.update({k_: v for k_, v in r.items() if k_ != "desglose"})
    errs = _errores_de_esquema(doc)
    if errs:
        raise ErrorValidacion("economia.json no cumple el esquema economia: " + "; ".join(errs[:3]))
    return doc


def verificar(economia: Mapping[str, Any], parametros: Any = None, limites: Any = None) -> list[str]:
    """Recalcula ``economia`` desde sus ``entradas_usadas`` y devuelve las diferencias (lista vacía = reproducible). Lo usa la CLI.

    Compara lo derivado, incluidos ``veredicto`` (sin ``razon_min_factible`` no es verificable: es una diferencia) y ``perdida_max_test``;
    con ``parametros`` también ``criterios_corte`` frente a ``testeo.k_corte``/``testeo.n_dec``, y con ``limites`` los ``limites_pendientes``.
    ``dias_test`` por debajo de ``max(7, ⌈presupuesto_test_min / gasto_diario⌉)`` sale como ``ErrorValidacion`` (lo levanta ``calcular``).
    """
    if not isinstance(economia, Mapping):
        raise ErrorValidacion("se esperaba un objeto economia.json")
    errs = _errores_de_esquema(economia)
    if errs:
        raise ErrorValidacion("economia.json no cumple el esquema economia: " + "; ".join(errs[:3]))
    entradas = dict(economia["entradas_usadas"])
    dias, plan = economia["dias_test"], economia["gasto_test_plan"]["monto"]
    if not isinstance(dias, int) or isinstance(dias, bool) or dias < 1:
        raise ErrorValidacion(f"dias_test debe ser un entero >= 1, llegó {dias!r}")
    if plan % dias:
        return [f"gasto_test_plan {plan} no es múltiplo entero de dias_test {dias} (diario × días)"]
    entradas.update(gasto_diario=plan // dias, dias_test=dias, k=economia["criterios_corte"]["k"], n_dec=economia["criterios_corte"]["n_dec"],
                    evento_optimizacion_inicial=economia["evento_optimizacion_inicial"], validada=economia["criterios_corte"]["validada"])
    nuevo = calcular(entradas, parametros, limites, estricto=False)
    comparables = ["aov", "mc", "cpa_be", "cpa_obj", "roas_be", "cpa_real", "razon", "razon_obj", "veredicto", "presupuesto_test_min", "perdida_max_test",
                   "conv_central", "cpc_esperado", "cpa_be_visto", "resultado_esperado_central"]
    if limites is not None:
        comparables.append("limites_pendientes")
    difs = [f"{c}: declarado {economia.get(c)!r} != recalculado {nuevo[c]!r}" for c in comparables if c != "veredicto" and economia.get(c) != nuevo[c]]
    if nuevo["veredicto"] is None:
        difs.append("veredicto: no verificable sin razon_min_factible (use --parametros)")
    elif economia.get("veredicto") != nuevo["veredicto"]:
        difs.append(f"veredicto: declarado {economia.get('veredicto')!r} != recalculado {nuevo['veredicto']!r} (razón exacta {nuevo['razon']} impresa)")
    for clave, campo in (("testeo.k_corte", "k"), ("testeo.n_dec", "n_dec")):
        esperado = _parametro(parametros, clave)
        if esperado is not None and economia["criterios_corte"][campo] != esperado:
            difs.append(f"criterios_corte.{campo}: declarado {economia['criterios_corte'][campo]!r} != parametros {clave} {esperado!r}")
    return difs


# --------------------------------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------------------------------
def _cargar(ruta: str) -> Any:
    from scripts.validar_esquemas import cargar_datos  # perezoso

    try:
        datos = cargar_datos(ruta)
    except FileNotFoundError as exc:
        raise ErrorUso(f"no existe {ruta}") from exc
    except (OSError, ValueError) as exc:
        raise ErrorValidacion(f"{ruta} ilegible: {exc}") from exc
    if not isinstance(datos, Mapping):
        raise ErrorValidacion(f"{ruta}: se esperaba un objeto (mapa clave-valor), llegó {type(datos).__name__}")
    return datos


def _escribir_atomico(ruta: Path, texto: str) -> None:
    """Escribe en un temporal del mismo directorio y renombra: una interrupción no deja un ``economia.json`` truncado."""
    tmp = ruta.with_name(ruta.name + ".tmp")
    tmp.write_text(texto, encoding="utf-8")
    os.replace(tmp, ruta)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada de ``python -m engine.factibilidad``; devuelve el código de salida (0, 2, 3, 5)."""
    ap = argparse.ArgumentParser(prog="python -m engine.factibilidad", description="Economía única de la fábrica (D-01)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("calcular", help="calcula economia.json desde un JSON/YAML de entradas")
    pc.add_argument("--entradas", required=True)
    pv = sub.add_parser("verificar", help="recalcula un economia.json y lista las diferencias")
    pv.add_argument("--economia", required=True)
    for p in (pc, pv):
        p.add_argument("--parametros", help="parametros.yaml (razon_min_factible, k_corte, n_dec)")
        p.add_argument("--limites", help="limites.yaml (para limites_pendientes)")
    pc.add_argument("--salida", help="escribe economia.json aquí (por defecto, a stdout)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code not in (0, None) else 0
    try:
        par = _cargar(args.parametros) if args.parametros else None
        lim = _cargar(args.limites) if args.limites else None
        if args.cmd == "calcular":
            doc = documento_economia(_cargar(args.entradas), par, lim)
            texto = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
            if args.salida:
                _escribir_atomico(Path(args.salida), texto)
            else:
                sys.stdout.write(texto)
            return 0
        difs = verificar(_cargar(args.economia), par, lim)
        for d in difs:
            print(f"DIFERENCIA {d}")
        print("economia reproducible" if not difs else f"{len(difs)} diferencia(s)")
        return 0 if not difs else ErrorValidacion.codigo_salida
    except ErrorFabrica as exc:
        print(f"ERROR: {exc.mensaje}", file=sys.stderr)
        return codigo_de_excepcion(exc)
    except (KeyError, TypeError, ZeroDivisionError, AttributeError) as exc:    # entrada con forma inesperada: salida 3, sin traceback
        print(f"ERROR: entrada con forma inválida ({type(exc).__name__}: {exc})", file=sys.stderr)
        return ErrorValidacion.codigo_salida


if __name__ == "__main__":
    sys.exit(main())
