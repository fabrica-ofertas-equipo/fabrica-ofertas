"""Reglas de decision secuenciales para D8 (y consumidas por D7/D9/F1): funciones puras y deterministas.

Principio: el codigo decide el "cuanto" y el "cuando"; el LLM solo explica. Toda salida lleva una
explicacion legible para `empresa/registro.jsonl`.

Nada esta fijado aqui: umbrales de `parametros.yaml`, topes de `limites.yaml`, economia de `economia.json`.
Si falta el tope de gasto, `evaluar_celda` devuelve BLOQUEADO (no se gasta ni se activa).

Metrica: CPA con compras de Stripe (nunca las de Meta) frente a CPA_BE (equilibrio) y CPA_obj (objetivo)
de economia.json. Modelo: conv ~ Beta (prior debil + compras/clics), clics por unidad de gasto ~ Gamma.
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Mapping, Optional, Sequence

from . import estadistica as est
from . import presupuesto as pre


class Accion(str, Enum):
    MATAR = "MATAR"
    SEGUIR = "SEGUIR"
    ESCALAR = "ESCALAR"
    INCONCLUSO = "INCONCLUSO"
    BLOQUEADO = "BLOQUEADO"


class ParametroFaltante(KeyError):
    """Falta un parametro o un limite: ningun script debe gastar ni activar."""


# ---------------------------------------------------------------------------
# Entradas y salidas tipadas
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ParametrosDecision:
    """Umbrales (parametros.yaml) y economia (economia.json) de una oferta-mercado. Sin valores por defecto."""

    moneda: str
    cpa_equilibrio_minor: int         # CPA_BE visto en Ads Manager
    cpa_objetivo_minor: int           # CPA_obj = f * CPA_BE
    cpc_prior_minor: float            # CPC esperado (D3), centro del prior de CPC
    prior_conv_media: float           # conversion central esperada (D3)
    prior_conv_fuerza_clics: float    # peso del prior en clics equivalentes
    prior_cpc_fuerza_clics: float
    alfa_descarte: float              # matar si P(CPA > BE) >= 1 - alfa_descarte
    alfa_descarte_tope: float         # umbral relajado al agotar el tope: matar si P(CPA > BE) >= 1 - alfa_tope
    p_escala: float                   # escalar si P(CPA <= BE) >= p_escala
    k_min_matar: float                # gasto minimo para matar = k_min * CPA_BE
    n_min_escala: int                 # compras minimas para escalar
    ventana_no_decidir_h: float       # horas tras una edicion significativa
    nodos_cpc: int                    # puntos de integracion del CPC

    def __post_init__(self) -> None:
        if self.cpa_equilibrio_minor <= 0 or self.cpa_objetivo_minor <= 0:
            raise ValueError("CPA de equilibrio y objetivo deben ser > 0")
        if self.cpa_objetivo_minor > self.cpa_equilibrio_minor:
            raise ValueError("CPA objetivo no puede superar el de equilibrio")
        for n in ("alfa_descarte", "alfa_descarte_tope"):
            if not 0.0 < getattr(self, n) < 0.5:
                raise ValueError(f"{n} debe estar en (0, 0,5)")
        if not 0.5 < self.p_escala < 1.0:
            raise ValueError("p_escala debe estar en (0,5, 1)")
        # Un parametro mal cargado no puede escalar con cero compras ni matar de inmediato (critica M03).
        if self.n_min_escala < 1:
            raise ValueError("n_min_escala debe ser >= 1")
        if self.k_min_matar <= 0:
            raise ValueError("k_min_matar debe ser > 0")
        if self.ventana_no_decidir_h < 0:
            raise ValueError("ventana_no_decidir_h debe ser >= 0")
        if self.nodos_cpc < 3:
            raise ValueError("nodos_cpc debe ser >= 3")
        if not 0.0 < self.prior_conv_media < 0.5:
            raise ValueError("prior_conv_media implausible: debe estar en (0, 0,5)")
        if self.prior_conv_fuerza_clics < 10 or self.prior_cpc_fuerza_clics < 5:
            raise ValueError("prior demasiado debil (fuerza de conversion >= 10 clics, de CPC >= 5)")


@dataclass(frozen=True)
class LimitesCelda:
    """De limites.yaml (solo el dueño los escribe). `None` = dato no cargado = no se gasta."""

    tope_gasto_celda_minor: Optional[int]


@dataclass(frozen=True)
class EvidenciaCelda:
    """Lo observado de una celda (anuncio, angulo, conjunto u oferta-mercado). Compras = Stripe, validas."""

    celda_id: str
    nivel: str                        # 'anuncio' | 'angulo' | 'oferta_mercado'
    moneda: str
    gasto_minor: int
    clics: int                        # clics de enlace
    compras: int                      # pagadas, no reembolsadas ni disputadas, con adid
    horas_desde_edicion: float        # desde la ultima edicion significativa (HC-3) o la activacion
    tracking_sano: bool               # razon Meta/Stripe y cobertura de adid dentro de rango (D8 G4)
    datos_maduros: bool               # sin los ultimos 2 dias (HC-45)


@dataclass(frozen=True)
class Decision:
    celda_id: str
    accion: Accion
    codigo: str                       # motivo canonico, estable para el registro
    explicacion: str                  # texto legible
    p_cpa_menor_equilibrio: Optional[float]
    p_cpa_menor_objetivo: Optional[float]
    cpa_mediano_minor: Optional[int]
    cpa_ic90_minor: Optional[tuple[float, float]]
    gasto_minor: int
    tope_minor: Optional[int]
    clics: int
    compras: int
    umbrales: Mapping[str, float] = field(default_factory=dict)

    def a_dict(self) -> dict:
        d = asdict(self)
        d["accion"] = self.accion.value
        return d


DECIMALES_MONEDA = {  # [VERIFICAR] https://docs.stripe.com/currencies (monedas de cero decimales mas comunes)
    "BIF": 0, "CLP": 0, "DJF": 0, "GNF": 0, "JPY": 0, "KMF": 0, "KRW": 0, "MGA": 0, "PYG": 0,
    "RWF": 0, "VND": 0, "VUV": 0, "XAF": 0, "XOF": 0, "XPF": 0,
    "BHD": 3, "JOD": 3, "KWD": 3, "OMR": 3, "TND": 3,  # ISO 4217: tres decimales (solo afecta el texto; m05)
}


def formatear_dinero(monto_minor: float, moneda: str) -> str:
    """'12,34 USD' a partir de unidad menor; separador decimal coma (documentos en español)."""
    dec = DECIMALES_MONEDA.get(moneda, 2)
    v = monto_minor / (10 ** dec)
    if math.isinf(v):
        return "infinito"
    return f"{v:.{dec}f}".replace(".", ",") + f" {moneda}"


def _pct(x: float) -> str:
    return f"{100.0 * x:.1f} %".replace(".", ",")


def parametros_desde_mapeo(parametros: Mapping, economia: Mapping) -> ParametrosDecision:
    """Construye ParametrosDecision desde la estructura de parametros.yaml (clave -> {valor, ...}) y
    de economia.json (moneda, cpa_equilibrio_visto_minor, cpa_objetivo_minor, cpc_esperado_minor, conv_central).
    Lanza ParametroFaltante si falta algo: no hay valores por defecto.
    """
    def p(nombre: str) -> float:
        clave = f"estadistica.{nombre}"
        try:
            entrada = parametros[clave]
            return entrada["valor"] if isinstance(entrada, Mapping) else entrada
        except KeyError as exc:
            raise ParametroFaltante(clave) from exc

    def ec(nombre: str):
        try:
            return economia[nombre]
        except KeyError as exc:
            raise ParametroFaltante(f"economia.{nombre}") from exc

    return ParametrosDecision(
        moneda=ec("moneda"),
        cpa_equilibrio_minor=int(ec("cpa_equilibrio_visto_minor")),
        cpa_objetivo_minor=int(ec("cpa_objetivo_minor")),
        cpc_prior_minor=float(ec("cpc_esperado_minor")),
        prior_conv_media=float(ec("conv_central")),
        prior_conv_fuerza_clics=float(p("prior_conv_fuerza_clics")),
        prior_cpc_fuerza_clics=float(p("prior_cpc_fuerza_clics")),
        alfa_descarte=float(p("alfa_descarte")),
        alfa_descarte_tope=float(p("alfa_descarte_tope")),
        p_escala=float(p("p_escala")),
        k_min_matar=float(p("k_min_matar")),
        n_min_escala=int(p("n_min_escala")),
        ventana_no_decidir_h=float(p("ventana_no_decidir_h")),
        nodos_cpc=int(p("nodos_cpc")),
    )


# ---------------------------------------------------------------------------
# Posterior de una celda
# ---------------------------------------------------------------------------

def posterior_celda(ev: EvidenciaCelda, par: ParametrosDecision) -> tuple[est.Beta, est.Gamma]:
    conv = est.actualizar_beta(est.beta_desde_media_fuerza(par.prior_conv_media, par.prior_conv_fuerza_clics),
                               ev.compras, ev.clics)
    lam = est.actualizar_gamma_clics(est.gamma_tasa_desde_cpc(par.cpc_prior_minor, par.prior_cpc_fuerza_clics),
                                     ev.clics, float(ev.gasto_minor))
    return conv, lam


# ---------------------------------------------------------------------------
# Regla secuencial por celda
# ---------------------------------------------------------------------------

def evaluar_celda(ev: EvidenciaCelda, par: ParametrosDecision, lim: LimitesCelda, con_intervalo: bool = True) -> Decision:
    """Decide MATAR / SEGUIR / ESCALAR / INCONCLUSO para una celda con la evidencia acumulada hasta hoy.

    Orden (manda el primero que dispara):
      0. Sin tope de gasto, moneda distinta o datos invalidos -> BLOQUEADO (no se gasta).
      1. Sin clics -> SEGUIR sin evidencia (o INCONCLUSO si ya se alcanzo el tope).
      2. MATAR si gasto >= k_min*CPA_BE y P(CPA > BE) >= 1 - alfa (1 - alfa_tope al alcanzar el tope).
         Dentro de la ventana de no decidir o con tracking/datos dudosos solo se mata con 0 compras
         y tracking sano (K1 de D8); con tracking dudoso no se mata.
      3. ESCALAR si compras >= n_min, P(CPA <= BE) >= p_escala y CPA mediano <= CPA_obj, fuera de ventana.
      4. Tope alcanzado sin lo anterior -> INCONCLUSO.
      5. Si no -> SEGUIR (con subtipo).
    """
    def bloqueo(codigo: str, texto: str) -> Decision:
        return Decision(ev.celda_id, Accion.BLOQUEADO, codigo, texto, None, None, None, None,
                        ev.gasto_minor, lim.tope_gasto_celda_minor, ev.clics, ev.compras)

    if lim.tope_gasto_celda_minor is None or lim.tope_gasto_celda_minor <= 0:
        return bloqueo("sin_limites", "Falta el tope de gasto por celda en limites.yaml: no se gasta ni se activa nada.")
    if ev.moneda != par.moneda:
        return bloqueo("moneda_distinta", f"La evidencia esta en {ev.moneda} y la economia en {par.moneda}.")
    if ev.gasto_minor < 0 or ev.clics < 0 or ev.compras < 0 or ev.compras > ev.clics:
        return bloqueo("datos_invalidos", "Datos inconsistentes (gasto, clics o compras negativos, o compras > clics).")

    tope = lim.tope_gasto_celda_minor
    en_tope = ev.gasto_minor >= tope
    m = par.moneda
    gasto_txt = formatear_dinero(ev.gasto_minor, m)
    umbrales = {
        "p_matar": 1.0 - par.alfa_descarte, "p_matar_en_tope": 1.0 - par.alfa_descarte_tope,
        "p_escala": par.p_escala, "gasto_min_matar_minor": par.k_min_matar * par.cpa_equilibrio_minor,
        "n_min_escala": float(par.n_min_escala), "cpa_equilibrio_minor": float(par.cpa_equilibrio_minor),
        "cpa_objetivo_minor": float(par.cpa_objetivo_minor),
    }

    def dec(accion: Accion, codigo: str, texto: str, p_be=None, p_obj=None, mediano=None, ic=None) -> Decision:
        return Decision(ev.celda_id, accion, codigo, texto, p_be, p_obj,
                        None if mediano is None else int(round(mediano)), ic, ev.gasto_minor, tope,
                        ev.clics, ev.compras, umbrales)

    if ev.clics == 0:
        if en_tope:
            return dec(Accion.INCONCLUSO, "tope_sin_clics",
                       f"Se gasto {gasto_txt} (tope {formatear_dinero(tope, m)}) sin un solo clic: falla de entrega, no de la oferta.")
        return dec(Accion.SEGUIR, "sin_evidencia", f"Sin clics todavia (gasto {gasto_txt}): no hay evidencia para decidir.")

    conv, lam = posterior_celda(ev, par)
    p_be = est.prob_cpa_menor(conv, lam, par.cpa_equilibrio_minor, par.nodos_cpc)
    p_obj = est.prob_cpa_menor(conv, lam, par.cpa_objetivo_minor, par.nodos_cpc)
    mediano = est.cpa_mediano_minor(conv, lam)
    ic = est.intervalo_cpa_minor(conv, lam, 0.90) if con_intervalo else None
    ic_txt = f" (IC90 {formatear_dinero(ic[0], m)} a {formatear_dinero(ic[1], m)})" if ic else ""
    resumen = (f"{ev.compras} compras en {ev.clics} clics y {gasto_txt}; CPA tipico {formatear_dinero(mediano, m)}"
               f"{ic_txt}; equilibrio "
               f"{formatear_dinero(par.cpa_equilibrio_minor, m)}, objetivo {formatear_dinero(par.cpa_objetivo_minor, m)}; "
               f"P(CPA<=equilibrio)={_pct(p_be)}, P(CPA<=objetivo)={_pct(p_obj)}.")
    kw = dict(p_be=p_be, p_obj=p_obj, mediano=mediano, ic=ic)

    en_ventana = ev.horas_desde_edicion < par.ventana_no_decidir_h
    gasto_min_matar = par.k_min_matar * par.cpa_equilibrio_minor
    p_peor = 1.0 - p_be
    umbral_matar = 1.0 - (par.alfa_descarte_tope if en_tope else par.alfa_descarte)

    # 2. MATAR
    if ev.tracking_sano and ev.gasto_minor >= gasto_min_matar and p_peor >= umbral_matar:
        # Con 0 compras tambien se espera media ventana: justo ahi el retraso clic->compra pesa mas (critica M02).
        if (not en_ventana and ev.datos_maduros) or (ev.compras == 0 and ev.horas_desde_edicion >= 0.5 * par.ventana_no_decidir_h):
            sufijo = " (cierre por tope de gasto)" if en_tope else ""
            return dec(Accion.MATAR, "sin_compras" if ev.compras == 0 else "cpa_peor_que_equilibrio",
                       f"MATAR{sufijo}: {resumen} La probabilidad de que el CPA real supere el equilibrio es "
                       f"{_pct(p_peor)} >= {_pct(umbral_matar)} y el gasto supera el minimo para matar "
                       f"({formatear_dinero(gasto_min_matar, m)}).", **kw)

    puede_actuar = ev.tracking_sano and ev.datos_maduros and not en_ventana

    # 3. ESCALAR
    if puede_actuar and ev.compras >= par.n_min_escala and p_be >= par.p_escala and mediano <= par.cpa_objetivo_minor:
        return dec(Accion.ESCALAR, "ganador_probable",
                   f"ESCALAR (propuesta a D9, dentro del paso permitido): {resumen} Cumple {ev.compras} >= "
                   f"{par.n_min_escala} compras, P(CPA<=equilibrio) >= {_pct(par.p_escala)} y CPA tipico <= objetivo.", **kw)

    # 4. Tope
    if en_tope:
        if not ev.tracking_sano or not ev.datos_maduros:
            return dec(Accion.INCONCLUSO, "tope_con_datos_dudosos",
                       f"INCONCLUSO: se alcanzo el tope ({formatear_dinero(tope, m)}) pero el tracking o la madurez de datos "
                       f"no permiten decidir (responsable: D5/D7). {resumen}", **kw)
        causa = ("justa: probablemente rentable pero sin margen o sin las compras minimas para escalar"
                 if p_be >= par.p_escala else "ruidosa: la evidencia no separa el CPA del equilibrio")
        return dec(Accion.INCONCLUSO, "tope_sin_veredicto",
                   f"INCONCLUSO: se alcanzo el tope de gasto ({formatear_dinero(tope, m)}) sin evidencia suficiente para "
                   f"matar ni escalar; causa {causa}. Decide el dueño: extender, rediseñar o cerrar. {resumen}", **kw)

    # 5. SEGUIR
    if ev.gasto_minor < gasto_min_matar and ev.compras == 0:
        return dec(Accion.SEGUIR, "sin_evidencia",
                   f"SEGUIR: aun no se gasto el minimo para poder matar ({formatear_dinero(gasto_min_matar, m)}). {resumen}", **kw)
    if not ev.tracking_sano:
        return dec(Accion.SEGUIR, "tracking_dudoso",
                   f"SEGUIR sin decidir (solo guardarrailes): tracking o conciliacion fuera de rango. {resumen}", **kw)
    if en_ventana:
        return dec(Accion.SEGUIR, "ventana_no_decidir",
                   f"SEGUIR: {ev.horas_desde_edicion:.0f} h desde la ultima edicion (< {par.ventana_no_decidir_h:.0f} h). {resumen}", **kw)
    if p_be >= par.p_escala:
        return dec(Accion.SEGUIR, "prometedora",
                   f"SEGUIR (prometedora): probablemente rentable pero todavia no cumple compras minimas o CPA objetivo. {resumen}", **kw)
    return dec(Accion.SEGUIR, "zona_gris", f"SEGUIR: la evidencia aun no separa el CPA del equilibrio. {resumen}", **kw)


# ---------------------------------------------------------------------------
# Comparacion de hermanos (angulos/anuncios): solo ordena, no mata por CPA con pocas compras
# ---------------------------------------------------------------------------

def ranking_hermanos(celdas: Sequence[EvidenciaCelda], par: ParametrosDecision, semilla: int) -> list[dict]:
    """Ordena celdas hermanas por P(conv mas alta). Etiqueta 'exploratorio' si hay menos de 20 compras en total
    (D8: con pocas compras los CPA entre anuncios no se comparan)."""
    if not celdas:
        return []
    prior = est.beta_desde_media_fuerza(par.prior_conv_media, par.prior_conv_fuerza_clics)
    post = [est.actualizar_beta(prior, c.compras, c.clics) for c in celdas]
    pm = est.prob_mejor(post, semilla)
    total = sum(c.compras for c in celdas)
    filas = [{"celda_id": c.celda_id, "p_mejor": pm[i], "conv_media": post[i].media,
              "compras": c.compras, "clics": c.clics,
              "etiqueta": "exploratorio" if total < 20 else "comparable"}
             for i, c in enumerate(celdas)]
    return sorted(filas, key=lambda f: -f["p_mejor"])


# ---------------------------------------------------------------------------
# Grupo de control de lo apagado
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CeldaApagada:
    celda_id: str
    presupuesto_diario_minor: int
    motivo: str


@dataclass(frozen=True)
class PlanControl:
    celdas_control: tuple[str, ...]
    presupuesto_diario_control_minor: Mapping[str, int]
    gasto_maximo_control_minor: int
    fraccion_pedida: float
    fraccion_efectiva: float
    explicacion: str


def _uniforme_determinista(semilla: int, clave: str) -> float:
    h = hashlib.sha256(f"{semilla}:{clave}".encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") / 2 ** 64


def plan_grupo_control(
    apagadas: Sequence[CeldaApagada], fraccion: float, fraccion_presupuesto: float,
    gasto_max_por_celda_minor: int, semilla: int, moneda: str,
) -> PlanControl:
    """Elige que celdas apagadas siguen vivas como control para medir los falsos descartes.

    Cada celda apagada entra al control con probabilidad `fraccion` (10-20 %), decidida por un hash con la semilla:
    determinista, independiente del orden y sin sesgo aunque haya pocas celdas. Las celdas de control reciben
    `fraccion_presupuesto` de su presupuesto previo y un gasto maximo propio. El control NO es para rescatar una
    celda: es para estimar, agregando muchas ofertas, cuantos descartes eran ganadores (ver estimar_falsos_descartes).
    """
    if not 0.0 <= fraccion <= 1.0 or not 0.0 < fraccion_presupuesto <= 1.0:
        raise ValueError("fraccion en [0,1] y fraccion_presupuesto en (0,1]")
    elegidas = [c for c in apagadas if _uniforme_determinista(semilla, c.celda_id) < fraccion]
    presup = {c.celda_id: max(1, int(round(c.presupuesto_diario_minor * fraccion_presupuesto))) for c in elegidas}
    tope = len(elegidas) * gasto_max_por_celda_minor
    efectiva = (len(elegidas) / len(apagadas)) if apagadas else 0.0
    return PlanControl(
        tuple(c.celda_id for c in elegidas), presup, tope, fraccion, efectiva,
        f"{len(elegidas)} de {len(apagadas)} celdas apagadas quedan como control ({_pct(efectiva)}; objetivo {_pct(fraccion)}), "
        f"con {_pct(fraccion_presupuesto)} de su presupuesto y un gasto maximo total de {formatear_dinero(tope, moneda)}.")


def estimar_falsos_descartes(n_controles: int, n_ganadores_entre_controles: int, confianza: float = 0.90) -> dict:
    """Tasa observada de falsos descartes (control que resulto cumplir P(CPA<=BE) >= p_escala) con IC exacto."""
    if n_controles <= 0:
        return {"tasa": None, "ic": None, "n": 0}
    ic = est.intervalo_clopper_pearson(n_ganadores_entre_controles, n_controles, confianza)
    return {"tasa": n_ganadores_entre_controles / n_controles, "ic": ic, "n": n_controles}


def n_controles_para_detectar(tasa_aceptable: float, tasa_inaceptable: float, alfa: float, potencia: float) -> int:
    """Controles (acumulados entre ofertas) para detectar que la tasa de falsos descartes es `tasa_inaceptable`
    y no `tasa_aceptable` (prueba unilateral aproximada)."""
    return est.n_contraste_unilateral(tasa_aceptable, tasa_inaceptable, alfa, potencia)


# ---------------------------------------------------------------------------
# Compatibilidad con las restricciones de Meta
# ---------------------------------------------------------------------------

FACTOR_META_MIN = 1.75  # hecho de plataforma (HC-26 [VERIFICAR]); limites.schema lo fija como constante


@dataclass(frozen=True)
class LimitesMeta:
    """Restricciones de edicion (limites.yaml / parametros.yaml). Sin defaults: hay que cargarlas."""

    paso_max_pct: float               # aumento maximo por paso (referencia: 0,20)
    horas_min_entre_aumentos: float   # referencia: 72
    max_teorico_factor: float         # Meta puede gastar hasta 1,75 x el diario (HC-26)
    max_cambios_por_hora: int         # 4 por conjunto (DV-2)
    segundos_min_entre_ediciones: int # 30 (DV-2)

    def __post_init__(self) -> None:
        # paso_max_pct es una FRACCION (0,20), no el "20" de limites.yaml: la conversion es unica, en decision/entradas.py (M01).
        if not 0.0 < self.paso_max_pct <= 1.0:
            raise ValueError("paso_max_pct debe ser una fraccion en (0, 1]; limites.yaml usa unidades de porcentaje (20 = 20 %)")
        if self.max_teorico_factor < FACTOR_META_MIN:
            raise ValueError(f"max_teorico_factor debe ser >= {FACTOR_META_MIN} (Meta puede gastar hasta 1,75 x el diario)")
        if self.horas_min_entre_aumentos < 0:
            raise ValueError("horas_min_entre_aumentos debe ser >= 0")
        if self.max_cambios_por_hora < 1 or self.segundos_min_entre_ediciones < 1:
            raise ValueError("max_cambios_por_hora y segundos_min_entre_ediciones deben ser >= 1")


@dataclass(frozen=True)
class PropuestaPresupuesto:
    permitido: bool
    nuevo_presupuesto_minor: int
    max_teorico_diario_minor: int
    proximo_intento_utc: Optional[str]
    motivos: tuple[str, ...]


def _parse_utc(s: str) -> datetime:
    """Instante UTC ISO-8601 con sufijo Z obligatorio: sin Z se tomaria la hora local del servidor (m06)."""
    if not s.endswith("Z"):
        raise ValueError(f"instante sin sufijo Z (UTC): {s!r}")
    return datetime.fromisoformat(s[:-1] + "+00:00").astimezone(timezone.utc)


def _iso_utc(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def proponer_aumento_presupuesto(
    actual_minor: int, deseado_minor: int, ultimo_aumento_utc: Optional[str], ahora_utc: str,
    cambios_ultima_hora: int, segundos_desde_ultima_edicion: float,
    techo_diario_oferta_minor: Optional[int], lim: LimitesMeta,
) -> PropuestaPresupuesto:
    """Proximo presupuesto diario permitido: <= +paso_max_pct, >= horas minimas desde el ultimo aumento,
    <= max_cambios_por_hora, >= segundos minimos entre ediciones y max_teorico (factor x nuevo) <= techo de limites.yaml.
    Sin techo cargado no se permite nada."""
    motivos: list[str] = []
    ahora = _parse_utc(ahora_utc)
    proximo: Optional[datetime] = None
    if techo_diario_oferta_minor is None:
        return PropuestaPresupuesto(False, actual_minor, int(round(actual_minor * lim.max_teorico_factor)), None,
                                    ("falta el techo diario de la oferta en limites.yaml",))
    if deseado_minor <= actual_minor:
        return PropuestaPresupuesto(False, actual_minor, int(round(actual_minor * lim.max_teorico_factor)), None,
                                    ("no es un aumento: bajar o mantener no usa este camino",))
    nuevo = min(deseado_minor, int(math.floor(actual_minor * (1.0 + lim.paso_max_pct))))
    if nuevo < deseado_minor:
        motivos.append(f"recortado al paso maximo de +{_pct(lim.paso_max_pct)}")
    techo_base = int(math.floor(techo_diario_oferta_minor / lim.max_teorico_factor))
    if nuevo > techo_base:
        nuevo = techo_base
        motivos.append("recortado para que el maximo teorico diario no supere el techo de la oferta")
    if nuevo <= actual_minor:
        motivos.append("el techo de la oferta no deja margen para aumentar")
        return PropuestaPresupuesto(False, actual_minor, int(round(actual_minor * lim.max_teorico_factor)), None, tuple(motivos))
    if ultimo_aumento_utc is not None:
        listo = _parse_utc(ultimo_aumento_utc) + timedelta(hours=lim.horas_min_entre_aumentos)
        if ahora < listo:
            proximo = listo
            motivos.append(f"faltan horas para el proximo aumento (minimo {lim.horas_min_entre_aumentos:.0f} h)")
    if cambios_ultima_hora >= lim.max_cambios_por_hora:
        proximo = max(proximo or ahora, ahora + timedelta(hours=1))
        motivos.append(f"ya hubo {cambios_ultima_hora} cambios de presupuesto en la ultima hora (maximo {lim.max_cambios_por_hora})")
    if segundos_desde_ultima_edicion < lim.segundos_min_entre_ediciones:
        espera = timedelta(seconds=lim.segundos_min_entre_ediciones - segundos_desde_ultima_edicion)
        proximo = max(proximo or ahora, ahora + espera)
        motivos.append(f"deben pasar {lim.segundos_min_entre_ediciones} s entre ediciones del mismo objeto")
    permitido = proximo is None
    return PropuestaPresupuesto(
        permitido, nuevo if permitido else actual_minor, int(round(nuevo * lim.max_teorico_factor)),
        None if permitido else _iso_utc(proximo), tuple(motivos) or ("aumento permitido",))


def pasos_para_alcanzar(actual_minor: float, objetivo_minor: float, paso_max_pct: float, horas_entre_aumentos: float) -> tuple[int, float]:
    """(numero de aumentos, dias) para pasar de `actual` a `objetivo` con el paso y la espera minimos."""
    if objetivo_minor <= actual_minor:
        return 0, 0.0
    n = math.ceil(math.log(objetivo_minor / actual_minor) / math.log(1.0 + paso_max_pct) - 1e-12)
    return n, (n - 1) * horas_entre_aumentos / 24.0


# ---------------------------------------------------------------------------
# Oferta validada (backbone 5.9): cohortes maduras, neta de reembolsos e IVA
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PedidoStripe:
    pedido_id: str
    pagado_en: str                    # UTC ISO-8601 con Z
    moneda: str
    bruto_minor: int
    impuesto_minor: int
    comision_minor: int               # real, de balance_transaction.fee (no se devuelve en reembolsos)
    reembolso_bruto_minor: int = 0
    reembolso_impuesto_minor: int = 0
    perdida_disputa_minor: int = 0    # disputa perdida (monto + tarifa); las abiertas van a reserva (F1)
    disputa_abierta_minor: int = 0    # disputa abierta o EFW (monto + tarifa): el veredicto la resta como si estuviera perdida (M14)
    atribuido_a_anuncio: bool = True  # tiene adid


@dataclass(frozen=True)
class DiaMedia:
    fecha: str                        # 'AAAA-MM-DD' en la zona de la cuenta
    gasto_minor: int                  # gasto de Meta, con tarifa
    clics: int


@dataclass(frozen=True)
class ParametrosValidacion:
    garantia_dias: int                # reembolso_dias
    margen_madurez_dias: int          # backbone: garantia + 7
    n_val: int
    dias_con_compras_min: int
    max_dia_pct: float
    reembolso_max: float
    p_validada: float                 # P(CPA <= BE real) minimo
    p_fallida: float
    k_min_fallida: float              # gasto minimo para FALLIDA = k * CPA_BE
    factor_objetivo: float            # f
    costo_var_pedido_minor: int
    tasa_reembolso_esperada: float    # para la vista provisional de cohortes inmaduras


@dataclass(frozen=True)
class VistaCohorte:
    pedidos_pagados: int
    compras_netas: int                # pagadas y no reembolsadas por completo
    gasto_minor: int
    clics: int
    contribucion_minor: int
    cpa_neto_minor: Optional[float]
    mc_neta_minor: Optional[float]    # = CPA_BE real
    roas_neto: Optional[float]
    reembolso_pct: Optional[float]
    dias_con_compras: int
    max_dia_pct: Optional[float]
    p_cpa_menor_equilibrio_real: Optional[float]


@dataclass(frozen=True)
class VeredictoValidacion:
    estado: str                       # VALIDADA | PROVISIONAL | PROMETEDORA | FALLIDA | INCONCLUSA
    explicacion: str
    madura: VistaCohorte
    provisional: VistaCohorte
    fecha_corte_madurez_utc: str
    fallos: tuple[str, ...]


def _contribucion_pedido(p: PedidoStripe, costo_var: int, r_esperada: float, inmaduro: bool) -> tuple[int, bool]:
    """(contribucion esperada del pedido, es_compra_neta). Neto de IVA, comision real, reembolso y disputa."""
    neto = p.bruto_minor - p.impuesto_minor
    reembolso_neto = max(0, p.reembolso_bruto_minor - p.reembolso_impuesto_minor)
    if inmaduro:
        reembolso_neto = max(reembolso_neto, int(round(r_esperada * neto)))
    total_reembolsado = p.reembolso_bruto_minor >= p.bruto_minor
    contrib = neto - p.comision_minor - reembolso_neto - p.perdida_disputa_minor - p.disputa_abierta_minor - costo_var
    return contrib, not total_reembolsado


def _vista(
    pedidos: Sequence[PedidoStripe], dias: Sequence[DiaMedia], pv: ParametrosValidacion,
    par: ParametrosDecision, inmaduros: Sequence[PedidoStripe], conv_prior: est.Beta,
) -> VistaCohorte:
    """Calcula la vista sobre `pedidos` (los de `inmaduros` se penalizan con el reembolso esperado)."""
    ids_inm = {p.pedido_id for p in inmaduros}
    contrib = 0
    netas = 0
    por_dia: dict[str, int] = {}
    reemb = 0
    for p in pedidos:
        c, es_neta = _contribucion_pedido(p, pv.costo_var_pedido_minor, pv.tasa_reembolso_esperada, p.pedido_id in ids_inm)
        contrib += c
        if es_neta:
            netas += 1
            por_dia[p.pagado_en[:10]] = por_dia.get(p.pagado_en[:10], 0) + 1
        reemb += p.reembolso_bruto_minor > 0
    gasto = sum(d.gasto_minor for d in dias)
    clics = sum(d.clics for d in dias)
    n_pag = len(pedidos)
    if netas == 0 or clics == 0 or gasto == 0:
        return VistaCohorte(n_pag, netas, gasto, clics, contrib, None, None, None,
                            (reemb / n_pag) if n_pag else None, len(por_dia), None, None)
    cpa = gasto / netas
    mc = contrib / netas
    maxd = max(por_dia.values()) / netas
    p_be = None
    if mc > 0 and clics >= netas:
        conv = est.actualizar_beta(conv_prior, netas, clics)
        lam = est.actualizar_gamma_clics(est.gamma_tasa_desde_cpc(par.cpc_prior_minor, par.prior_cpc_fuerza_clics),
                                         clics, float(gasto))
        p_be = est.prob_cpa_menor(conv, lam, mc, par.nodos_cpc)
    return VistaCohorte(n_pag, netas, gasto, clics, contrib, cpa, mc, contrib / gasto,
                        reemb / n_pag, len(por_dia), maxd, p_be)


def _cumple(v: VistaCohorte, pv: ParametrosValidacion) -> tuple[bool, list[str], bool]:
    """(cumple todo, fallos, es_prometedora): prometedora = todo salvo CPA > objetivo (pero <= equilibrio con P suficiente)."""
    fallos: list[str] = []
    if v.cpa_neto_minor is None or v.mc_neta_minor is None:
        return False, ["sin compras netas, clics o gasto en la cohorte"], False
    if v.compras_netas < pv.n_val:
        fallos.append(f"compras netas {v.compras_netas} < {pv.n_val}")
    if v.dias_con_compras < pv.dias_con_compras_min:
        fallos.append(f"compras en {v.dias_con_compras} dias < {pv.dias_con_compras_min}")
    if v.max_dia_pct is not None and v.max_dia_pct > pv.max_dia_pct:
        fallos.append(f"un solo dia concentra {_pct(v.max_dia_pct)} > {_pct(pv.max_dia_pct)} de las compras")
    if v.reembolso_pct is not None and v.reembolso_pct > pv.reembolso_max:
        fallos.append(f"reembolsos {_pct(v.reembolso_pct)} > {_pct(pv.reembolso_max)}")
    if v.p_cpa_menor_equilibrio_real is None or v.p_cpa_menor_equilibrio_real < pv.p_validada:
        fallos.append("P(CPA <= equilibrio real) < p_validada")
    otros = list(fallos)
    objetivo_ok = v.cpa_neto_minor <= pv.factor_objetivo * v.mc_neta_minor
    if not objetivo_ok:
        fallos.append("CPA neto > CPA objetivo real")
    return (not fallos), fallos, ((not objetivo_ok) and not otros and v.cpa_neto_minor <= v.mc_neta_minor)


def evaluar_oferta_validada(
    pedidos: Sequence[PedidoStripe], dias: Sequence[DiaMedia], ahora_utc: str,
    pv: ParametrosValidacion, par: ParametrosDecision,
) -> VeredictoValidacion:
    """Veredicto de oferta segun backbone 5.9.

    - Cohorte madura: pedidos pagados hace al menos garantia + margen dias (y gasto de los dias <= la fecha de corte).
    - Neta: compras pagadas y no reembolsadas por completo; contribucion neta de IVA, comision real, reembolsos y disputas.
    - CPA_BE real = contribucion neta / compras netas (reemplaza al de D3); CPA_obj real = f * CPA_BE real.
    - VALIDADA: cohorte madura cumple n_val, dias con compras, concentracion, reembolsos, P(CPA<=BE real) y CPA<=obj real.
    - PROVISIONAL: la vista que incluye cohortes inmaduras (con reembolso esperado) cumple, pero la madura aun no tiene n_val.
    - PROMETEDORA: cumple todo salvo CPA > obj real con CPA <= BE real.
    - FALLIDA: gasto >= k_min_fallida * CPA_BE y P(CPA<=BE real) <= 1 - p_fallida (vista madura o provisional).
    - INCONCLUSA: el resto.
    """
    ahora = _parse_utc(ahora_utc)
    corte = ahora - timedelta(days=pv.garantia_dias + pv.margen_madurez_dias)
    corte_fecha = corte.strftime("%Y-%m-%d")
    for p in pedidos:
        if p.moneda != par.moneda:
            raise ValueError("pedido en moneda distinta a la economia: convertir antes (F1)")
    atribuidos = [p for p in pedidos if p.atribuido_a_anuncio]
    maduros = [p for p in atribuidos if _parse_utc(p.pagado_en) <= corte]
    inmaduros = [p for p in atribuidos if _parse_utc(p.pagado_en) > corte]
    dias_maduros = [d for d in dias if d.fecha <= corte_fecha]
    prior = est.beta_desde_media_fuerza(par.prior_conv_media, par.prior_conv_fuerza_clics)
    v_mad = _vista(maduros, dias_maduros, pv, par, [], prior)
    v_pro = _vista(atribuidos, dias, pv, par, inmaduros, prior)
    ok_m, fallos_m, prom_m = _cumple(v_mad, pv)
    ok_p, fallos_p, prom_p = _cumple(v_pro, pv)
    m = par.moneda
    corte_txt = _iso_utc(corte)

    def falla_dura(v: VistaCohorte) -> bool:
        return (v.p_cpa_menor_equilibrio_real is not None and v.p_cpa_menor_equilibrio_real <= 1.0 - pv.p_fallida
                and v.gasto_minor >= pv.k_min_fallida * par.cpa_equilibrio_minor)

    if ok_m:
        estado, fallos = "VALIDADA", ()
        texto = (f"VALIDADA con cohorte madura (pagos hasta {corte_txt}): {v_mad.compras_netas} compras netas, "
                 f"CPA neto {formatear_dinero(v_mad.cpa_neto_minor, m)} <= objetivo real "
                 f"{formatear_dinero(pv.factor_objetivo * v_mad.mc_neta_minor, m)}, ROAS neto {v_mad.roas_neto:.2f}, "
                 f"P(CPA<=equilibrio real)={_pct(v_mad.p_cpa_menor_equilibrio_real)}.")
    elif falla_dura(v_mad) or (v_mad.compras_netas < pv.n_val and falla_dura(v_pro)):
        estado, fallos = "FALLIDA", tuple(fallos_m if falla_dura(v_mad) else fallos_p)
        texto = ("FALLIDA: la probabilidad de que el CPA neto este por debajo del equilibrio real es baja con gasto suficiente "
                 f"(vista {'madura' if falla_dura(v_mad) else 'provisional'}).")
    elif ok_p and v_mad.compras_netas < pv.n_val:
        estado, fallos = "PROVISIONAL", tuple(fallos_m)
        texto = (f"PROVISIONAL: la vista con cohortes inmaduras (reembolso esperado aplicado) cumple, pero la madura tiene "
                 f"{v_mad.compras_netas} compras netas (< {pv.n_val}). No escalar mas alla de un paso pequeño hasta madurar.")
    elif prom_m or (v_mad.compras_netas < pv.n_val and prom_p):
        estado, fallos = "PROMETEDORA", tuple(fallos_m if prom_m else fallos_p)
        texto = "PROMETEDORA: rentable pero justa (CPA entre el objetivo y el equilibrio reales); optimizar creativos sin escalar."
    else:
        estado, fallos = "INCONCLUSA", tuple(fallos_m or fallos_p)
        texto = "INCONCLUSA: no cumple los criterios ni hay evidencia para declararla fallida."
    return VeredictoValidacion(estado, texto + (" Fallos: " + "; ".join(fallos) + "." if fallos else ""),
                               v_mad, v_pro, corte_txt, tuple(fallos))
