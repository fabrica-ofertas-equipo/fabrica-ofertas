"""Calculadoras de economia por pedido y de presupuesto minimo del testeo.

El presupuesto de un test es una FUNCION de los parametros: este modulo nunca fija un tope. El tope
maximo lo fija el dueño en `empresa/limites.yaml`; aqui solo se compara (`autorizado`, `cabe_en_tope`).

Convenciones:
  - Montos (precio, comision, CPA de equilibrio, gasto, presupuesto) = int en unidad menor de la
    moneda. La economia por pedido NO se calcula aqui: `economia_por_pedido` envuelve `engine.factibilidad` (enteros y
    Fraction, half-even; D-01). El resto de los valores esperados de este modulo son float en memoria y se redondean half-even al salir.
  - Tasas (IVA, comision, conversion, reembolso, tarifa de Meta) = float.
  - CPC y CPM son TASAS de costo unitario, no saldos: float en unidad menor por clic / por mil
    impresiones (un CPC de 0,31 USD es 31,0; redondear a int destruiria el 10 % de precision).
  - El precio es el precio final al cliente, con IVA incluido (`tasa_iva` = 0 si no aplica).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from fractions import Fraction
from typing import Optional

from engine import factibilidad as fact

from . import estadistica as est


def _a_menor(valor: float) -> int:
    """Redondeo half-even (el de `round`) a unidad menor."""
    return int(round(valor))


# ---------------------------------------------------------------------------
# Economia por pedido (envoltorio de engine.factibilidad: una sola formula en todo el sistema, D-01)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParametrosPrecio:
    """Entradas de la economia unitaria. Todas obligatorias salvo el upsell (explicito en 0)."""

    moneda: str
    precio_bruto_minor: int            # precio del frontal, con IVA incluido
    tasa_iva: float                    # 0,23 = 23 % incluido en el precio; 0 si no se remite
    comision_pct: float                # suma de % de Stripe (base + internacional + conversion)
    comision_fija_minor: int           # fija por transaccion
    stripe_tax_pct: float              # 0,005 si Stripe Tax Basic en %, 0 si va fija
    stripe_tax_fijo_minor: int         # p. ej. 50 si Stripe Tax por API, 0 si va en %
    tasa_bump: float                   # fraccion de pedidos que toma el order bump
    precio_bump_minor: int
    tasa_reembolso: float              # r: fraccion de pedidos reembolsados (la comision no se devuelve)
    tasa_disputa: float                # d: fraccion de pedidos en disputa perdida
    tarifa_disputa_minor: int
    costo_var_minor: int               # costo variable por pedido (entrega, correo)
    tarifa_meta_pct: float             # recargo de Meta sobre la entrega (p. ej. 0,03 en Italia)
    factor_objetivo: float             # f = CPA_obj / CPA_BE (D3: 0,6)
    tasa_upsell: float = 0.0
    precio_upsell_minor: int = 0

    def __post_init__(self) -> None:
        for nombre in ("tasa_iva", "comision_pct", "stripe_tax_pct", "tasa_bump", "tasa_reembolso",
                       "tasa_disputa", "tarifa_meta_pct", "tasa_upsell"):
            v = getattr(self, nombre)
            if not 0.0 <= v < 1.0:
                raise ValueError(f"{nombre} debe estar en [0, 1)")
        if not 0.0 < self.factor_objetivo <= 1.0:
            raise ValueError("factor_objetivo debe estar en (0, 1]")
        for nombre in ("precio_bruto_minor", "comision_fija_minor", "stripe_tax_fijo_minor", "precio_bump_minor",
                       "tarifa_disputa_minor", "costo_var_minor", "precio_upsell_minor"):
            v = getattr(self, nombre)
            if not isinstance(v, int) or isinstance(v, bool) or v < 0:
                raise ValueError(f"{nombre} debe ser un entero >= 0 en unidad menor")
        if self.precio_bruto_minor == 0:
            raise ValueError("precio_bruto_minor debe ser > 0")


@dataclass(frozen=True)
class EconomiaPedido:
    """Valores esperados por pedido (unidad menor)."""

    moneda: str
    aov_bruto_minor: int
    iva_minor: int
    neto_minor: int
    comision_minor: int
    stripe_tax_minor: int
    reembolso_esperado_minor: int
    disputa_esperada_minor: int
    costo_var_minor: int
    contribucion_minor: int            # MC: lo que deja un pedido antes de pagar anuncios
    cpa_equilibrio_minor: int          # CPA_BE = MC
    cpa_equilibrio_visto_minor: int    # CPA que se ve en Ads Manager = MC / (1 + tarifa Meta)
    cpa_objetivo_minor: int            # CPA_obj = f * CPA_BE (visto en Ads Manager)
    roas_bruto_equilibrio: float       # AOV bruto / CPA_BE (compararlo con el ROAS bruto de Stripe)

    @property
    def margen_positivo(self) -> bool:
        return self.contribucion_minor > 0


def _a_bp(tasa: float) -> int:
    """Tasa (fraccion, p. ej. 0,029) a puntos basicos enteros, half-even: lo que persisten los contratos."""
    bp = Fraction(repr(tasa)) * 10000
    if bp.denominator != 1:   # 0,02925 = 292,5 bp: redondear en silencio cambiaría la economía sin que nadie lo vea (CT2-35)
        raise ValueError(f"tasa {tasa!r} no representable en puntos basicos enteros")
    return int(bp)


def economia_por_pedido(p: ParametrosPrecio) -> EconomiaPedido:
    """AOV, neto de IVA, comisiones, reembolsos y disputas esperados, y CPA de equilibrio.

    ENVOLTORIO de `engine.factibilidad.economia_unitaria` (D-01): la unica formula del sistema. Convierte las tasas
    (float en memoria) a puntos basicos enteros y delega; no calcula nada por su cuenta.

    AOV = P + b*Pb + u*Pu          neto = AOV / (1 + t)           IVA = AOV - neto
    comision = pct*AOV + fija*(1 + u)          stripe_tax = pct_tax*AOV + fijo_tax*(1 + u)
    MC = neto - comision - stripe_tax - r*neto - d*(neto + tarifa_disputa) - costo_var
    CPA_BE = MC;   CPA_visto = MC / (1 + tarifa_meta);   CPA_obj = f * CPA_visto

    El reembolso devuelve el bruto y el IVA pero la comision se pierde (03 §4.3): por eso r multiplica
    el neto y la comision se resta entera. La disputa perdida cuesta el neto mas la tarifa.
    """
    m = p.moneda
    u = fact.economia_unitaria({
        "moneda": m, "precio": p.precio_bruto_minor, "precio_bump": p.precio_bump_minor, "tasa_bump_bp": _a_bp(p.tasa_bump),
        "precio_upsell": p.precio_upsell_minor, "tasa_upsell_bp": _a_bp(p.tasa_upsell), "tasa_iva_bp": _a_bp(p.tasa_iva),
        "comision_pct_bp": _a_bp(p.comision_pct), "comision_fija": p.comision_fija_minor,
        "stripe_tax": {"pct_bp": _a_bp(p.stripe_tax_pct), "fijo": p.stripe_tax_fijo_minor},
        "tasa_reembolso_bp": _a_bp(p.tasa_reembolso), "tasa_disputa_bp": _a_bp(p.tasa_disputa),
        "tarifa_disputa": p.tarifa_disputa_minor, "costo_variable": p.costo_var_minor,
        "tarifa_meta_bp": _a_bp(p.tarifa_meta_pct), "factor_cpa_objetivo_bp": _a_bp(p.factor_objetivo),
    })
    return EconomiaPedido(
        moneda=m,
        aov_bruto_minor=u["aov"],
        iva_minor=u["iva"],
        neto_minor=u["neto"],
        comision_minor=u["comision"],
        stripe_tax_minor=u["stripe_tax"],
        reembolso_esperado_minor=u["reembolso_esperado"],
        disputa_esperada_minor=u["disputa_esperada"],
        costo_var_minor=p.costo_var_minor,
        contribucion_minor=u["mc_con_signo"],
        cpa_equilibrio_minor=u["cpa_be"],
        cpa_equilibrio_visto_minor=u["cpa_be_visto"],
        cpa_objetivo_minor=u["cpa_obj"],
        roas_bruto_equilibrio=(u["aov"] / u["cpa_be"]) if u["cpa_be"] > 0 else math.inf,
    )


# ---------------------------------------------------------------------------
# Costos de adquisicion: CPC, CPA, conversion
# ---------------------------------------------------------------------------

def cpc_desde_cpm_ctr(cpm_minor: float, ctr_enlace: float) -> float:
    """CPC = CPM / (1000 * CTR de enlace). Devuelve unidad menor por clic (float, es una tasa).

    Es un ESTIMADOR de planificacion, no el ``cpc_esperado`` de ``economia.json`` (ese sale de ``engine.factibilidad`` como cadena decimal
    exacta; X14 tolera 1/1000 entre ambos).
    """
    if cpm_minor <= 0 or not 0.0 < ctr_enlace < 1.0:
        raise ValueError("cpm > 0 y ctr_enlace en (0,1)")
    return cpm_minor / (1000.0 * ctr_enlace)


def cpa_desde_cpc_conv(cpc_minor: float, conv: float) -> float:
    """CPA = CPC / conversion clic->compra (float, unidad menor)."""
    if conv <= 0:
        return math.inf
    return cpc_minor / conv


def conversion_equilibrio(cpc_minor: float, cpa_equilibrio_minor: float) -> float:
    """c* = CPC / CPA_BE: conversion clic->compra necesaria para no perder dinero."""
    if cpa_equilibrio_minor <= 0:
        return math.inf
    return cpc_minor / cpa_equilibrio_minor


def conversion_desde_embudo(tasa_conexion: float, tasa_ic: float, tasa_compra_ic: float) -> float:
    """Conversion clic->compra como producto del embudo: vistas/clics * IC/vistas * compra/IC (D8 §3.4)."""
    for v in (tasa_conexion, tasa_ic, tasa_compra_ic):
        if not 0.0 <= v <= 1.0:
            raise ValueError("las tasas del embudo deben estar en [0,1]")
    return tasa_conexion * tasa_ic * tasa_compra_ic


# ---------------------------------------------------------------------------
# Plan de presupuesto de una celda (una oferta-mercado, un angulo o un anuncio agrupado)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EntradaPlan:
    """Parametros del plan de una celda. Todos vienen de economia.json / parametros.yaml / limites.yaml."""

    moneda: str
    cpa_equilibrio_visto_minor: int
    cpa_objetivo_minor: int
    cpc_minor: float                     # CPC esperado, tasa
    conv_plausible: float                # conversion clic->compra esperada (escenario central de D3)
    alfa: float                          # error tolerable de dar por bueno un perdedor / descartar un ganador
    potencia: float                      # 1 - beta: probabilidad de reconocer un ganador de CPA = objetivo
    k_min_matar: float                   # gasto minimo para matar = k * CPA_BE (piso que protege del prior)
    precision_relativa: float            # para estimar la conversion (nota 16: 0,25)
    prior_conv_media: float
    prior_conv_fuerza_clics: float
    n_dec: int                           # compras minimas para validar (D3/D8)
    tarifa_meta_pct: float               # recargo de Meta sobre la entrega (solo afecta al total)
    n_celdas: int = 1
    tope_gasto_celda_minor: Optional[int] = None   # de limites.yaml; None = no hay dato = no se autoriza


@dataclass(frozen=True)
class PlanCelda:
    conv_equilibrio: float
    conv_ganadora: float                 # conversion que da exactamente CPA_obj
    clics_descartar_sin_compras: int
    clics_confirmar_ganador: int
    clics_precision: int
    compras_esperadas_confirmar: float
    gasto_regla_k_minor: int             # k_min_matar * CPA_BE (piso para poder matar)
    gasto_descartar_minor: int
    gasto_confirmar_minor: int
    gasto_precision_minor: int
    gasto_n_dec_minor: int               # N_dec * CPA esperado
    gasto_recomendado_minor: int         # el necesario para refutar o confirmar, el mayor de ambos
    gasto_total_minor: int               # * n_celdas, con tarifa de Meta
    cabe_en_tope: Optional[bool]         # None si no hay tope cargado
    autorizado: bool                     # False si falta el tope: ningun script gasta
    avisos: tuple[str, ...] = field(default_factory=tuple)


def plan_celda(e: EntradaPlan) -> PlanCelda:
    """Clics y gasto minimos para REFUTAR (descartar con `alfa`) y para CONFIRMAR un ganador (potencia).

    - Descartar: n tal que con 0 compras P(conv > c*) <= alfa (prior debil). Es ~ln(1/alfa) * CPA_BE de gasto
      con un prior casi plano; un prior que ya cree que la conversion es baja lo acorta, por eso se impone el
      piso k_min_matar * CPA_BE (el mismo que usa reglas.evaluar_celda) para no depender del prior.
    - Confirmar: n del contraste unilateral conv_nula = c* contra conv_ganadora = CPC / CPA_obj.
    - Precision: clics para estimar la conversion esperada con semiancho relativo `precision_relativa`.
    El gasto es clics * CPC (visto en Ads Manager); la tarifa de Meta se suma en el total.
    """
    if e.cpa_equilibrio_visto_minor <= 0:
        raise ValueError("cpa_equilibrio_visto_minor debe ser > 0: sin margen no hay test")
    c_eq = conversion_equilibrio(e.cpc_minor, e.cpa_equilibrio_visto_minor)
    c_gan = conversion_equilibrio(e.cpc_minor, e.cpa_objetivo_minor)
    avisos: list[str] = []
    if c_eq >= 1.0:
        raise ValueError("conversion de equilibrio >= 100 %: el CPC supera el CPA de equilibrio")
    prior = est.beta_desde_media_fuerza(e.prior_conv_media, e.prior_conv_fuerza_clics)
    n_desc = est.clics_para_descartar_sin_compras(c_eq, e.alfa, prior)
    if c_gan >= 1.0 or c_gan <= c_eq:
        n_conf = 0
        avisos.append("no hay ganador separable: CPA_obj >= CPA_BE o conversion ganadora >= 100 %")
    else:
        n_conf = est.n_contraste_unilateral(c_eq, c_gan, e.alfa, e.potencia)
    n_prec = est.n_precision_relativa(min(max(e.conv_plausible, 1e-6), 0.999), e.precision_relativa)
    gasto = lambda clics: _a_menor(clics * e.cpc_minor)
    g_desc = max(gasto(n_desc), _a_menor(e.k_min_matar * e.cpa_equilibrio_visto_minor))
    g_conf, g_prec = gasto(n_conf), gasto(n_prec)
    cpa_esperado = cpa_desde_cpc_conv(e.cpc_minor, e.conv_plausible)
    g_ndec = _a_menor(e.n_dec * cpa_esperado) if math.isfinite(cpa_esperado) else 0
    recomendado = max(g_desc, g_conf)
    if cpa_esperado > e.cpa_equilibrio_visto_minor:
        avisos.append("el CPA esperado supera el CPA de equilibrio: el escenario central pierde dinero; "
                      "el test solo puede refutar")
    if g_ndec > recomendado:
        avisos.append("validar con N_dec compras al CPA esperado cuesta mas que confirmar con el contraste")
    total = _a_menor(recomendado * e.n_celdas * (1.0 + e.tarifa_meta_pct))
    if e.tope_gasto_celda_minor is None:
        cabe, autorizado = None, False
        avisos.append("falta tope_gasto_celda en limites.yaml: no se autoriza gasto")
    else:
        cabe = recomendado <= e.tope_gasto_celda_minor
        autorizado = cabe
        if not cabe:
            avisos.append("el gasto recomendado supera el tope por celda: el test no alcanza para decidir")
    return PlanCelda(
        conv_equilibrio=c_eq, conv_ganadora=c_gan,
        clics_descartar_sin_compras=n_desc, clics_confirmar_ganador=n_conf, clics_precision=n_prec,
        compras_esperadas_confirmar=n_conf * c_gan,
        gasto_regla_k_minor=_a_menor(e.k_min_matar * e.cpa_equilibrio_visto_minor),
        gasto_descartar_minor=g_desc, gasto_confirmar_minor=g_conf, gasto_precision_minor=g_prec,
        gasto_n_dec_minor=g_ndec, gasto_recomendado_minor=recomendado, gasto_total_minor=total,
        cabe_en_tope=cabe, autorizado=autorizado, avisos=tuple(avisos),
    )


# ---------------------------------------------------------------------------
# Presupuesto de precision (nota 16) y tabla de sensibilidad
# ---------------------------------------------------------------------------

def presupuesto_precision(conv: float, precision_relativa: float, confianza: float, cpc_minor: float) -> tuple[int, int, int]:
    """(clics, compras esperadas, gasto) para estimar `conv` con la precision dada. Reproduce la nota 16:
    conv 2,5 %, +-25 %, 95 % -> ~2.400 clics, ~60 compras; 740 USD a CPC 0,31 y 1.220 USD a CPC 0,51."""
    clics = est.n_precision_relativa(conv, precision_relativa, confianza)
    return clics, round(clics * conv), _a_menor(clics * cpc_minor)


def tabla_sensibilidad(
    cpa_equilibrio_visto_minor: int, factor_objetivo: float, cpcs_minor: list[float], convs: list[float],
    alfa: float, potencia: float, prior_media: float, prior_fuerza: float,
) -> list[dict]:
    """Una fila por (CPC, conversion): CPA, razon CPA/BE, c*, clics para descartar y para confirmar, gasto.

    `gasto_confirmar_minor` = gasto para confirmar un ganador de CPA = f * CPA_BE a ese CPC.
    """
    prior = est.beta_desde_media_fuerza(prior_media, prior_fuerza)
    filas = []
    for cpc in cpcs_minor:
        c_eq = conversion_equilibrio(cpc, cpa_equilibrio_visto_minor)
        c_gan = conversion_equilibrio(cpc, factor_objetivo * cpa_equilibrio_visto_minor)
        n_desc = est.clics_para_descartar_sin_compras(c_eq, alfa, prior) if c_eq < 1.0 else None
        n_conf = (est.n_contraste_unilateral(c_eq, c_gan, alfa, potencia) if (c_eq < c_gan < 1.0) else None)
        for conv in convs:
            cpa = cpa_desde_cpc_conv(cpc, conv)
            filas.append({
                "cpc_minor": cpc, "conv": conv, "cpa_minor": cpa,
                "razon_cpa_sobre_be": cpa / cpa_equilibrio_visto_minor,
                "conv_equilibrio": c_eq,
                "clics_descartar": n_desc,
                "gasto_descartar_minor": None if n_desc is None else _a_menor(n_desc * cpc),
                "clics_confirmar": n_conf,
                "gasto_confirmar_minor": None if n_conf is None else _a_menor(n_conf * cpc),
            })
    return filas


def max_celdas(presupuesto_total_minor: int, gasto_minimo_por_celda_minor: int) -> int:
    """Cuantas celdas (anuncios o conjuntos) caben sin diluir la muestra por debajo del minimo por celda."""
    if gasto_minimo_por_celda_minor <= 0:
        raise ValueError("el gasto minimo por celda debe ser > 0")
    return presupuesto_total_minor // gasto_minimo_por_celda_minor


# ---------------------------------------------------------------------------
# Fase de aprendizaje de Meta
# ---------------------------------------------------------------------------

def eventos_semanales_esperados(presupuesto_diario_minor: float, cpa_esperado_minor: float) -> float:
    """Eventos de optimizacion por semana de un conjunto = 7 * presupuesto diario / CPA."""
    if cpa_esperado_minor <= 0:
        raise ValueError("cpa_esperado debe ser > 0")
    return 7.0 * presupuesto_diario_minor / cpa_esperado_minor


def presupuesto_diario_para_aprendizaje(cpa_esperado_minor: float, eventos_semana: float) -> float:
    """Presupuesto diario por conjunto para alcanzar `eventos_semana` (Meta: ~50, HC-1): eventos/7 * CPA."""
    return eventos_semana / 7.0 * cpa_esperado_minor


def evento_optimizacion_recomendado(
    presupuesto_diario_minor: float, cpa_esperado_minor: float, eventos_semana: float, fraccion_minima: float,
) -> str:
    """'PURCHASE' si el presupuesto cubre al menos `fraccion_minima` del necesario para salir de aprendizaje
    limitado; si no, 'INITIATE_CHECKOUT' (evento mas frecuente, que Meta recomienda). Se juzga siempre por Stripe."""
    necesario = presupuesto_diario_para_aprendizaje(cpa_esperado_minor, eventos_semana)
    return "PURCHASE" if presupuesto_diario_minor >= fraccion_minima * necesario else "INITIATE_CHECKOUT"


# ---------------------------------------------------------------------------
# Comparacion de mercados con la misma oferta
# ---------------------------------------------------------------------------

def costo_comparacion_mercados(
    n_mercados: int, clics_por_mercado: int, cpcs_minor: list[float], tarifas_meta_pct: list[float],
) -> int:
    """Gasto total de probar `n_mercados` con iguales clics objetivo por mercado (el CPC y la tarifa difieren)."""
    if not (len(cpcs_minor) == len(tarifas_meta_pct) == n_mercados):
        raise ValueError("una entrada de CPC y de tarifa por mercado")
    total = sum(clics_por_mercado * cpc * (1.0 + t) for cpc, t in zip(cpcs_minor, tarifas_meta_pct))
    return _a_menor(total)


def clics_para_distinguir_mercados(conv_a: float, conv_b: float, alfa: float, potencia: float) -> int:
    """Clics POR MERCADO para distinguir dos conversiones (prueba bilateral)."""
    return est.n_dos_proporciones(conv_a, conv_b, alfa, potencia, unilateral=False)
