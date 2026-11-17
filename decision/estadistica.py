"""Estadistica del testeo: distribuciones, intervalos, tamanos de muestra y probabilidades de error.

Solo biblioteca estandar (math, random, statistics). Funciones puras y deterministas; las que usan
Monte Carlo reciben una semilla y crean su propio `random.Random`.

Convenciones:
  - Las cantidades de dinero que entran a las formulas estan en unidad menor (centavos) y son float
    SOLO dentro de los calculos; los modulos que producen montos (presupuesto.py) los devuelven como int.
  - `conv` = conversion clic->compra (compras / clics de enlace), `lam` = clics por unidad menor de gasto
    (inverso del CPC), `cpa` = gasto por compra en unidad menor.
  - Modelo: compras ~ Binomial(clics, conv); clics ~ Poisson(lam * gasto); CPA = 1 / (lam * conv).
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from statistics import NormalDist
from typing import Callable, Sequence

_NORMAL = NormalDist()
_EPS = 1e-15
_MAX_ITER = 2000


# ---------------------------------------------------------------------------
# Funciones especiales: beta incompleta regularizada y gamma incompleta regularizada
# ---------------------------------------------------------------------------

def _fraccion_continua_beta(a: float, b: float, x: float) -> float:
    """Fraccion continua de la beta incompleta (algoritmo de Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, _MAX_ITER):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = tiny if abs(d) < tiny else d
        c = 1.0 + aa / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            break
    return h


def beta_inc_reg(x: float, a: float, b: float) -> float:
    """I_x(a, b): funcion de distribucion de una Beta(a, b) en x."""
    if a <= 0 or b <= 0:
        raise ValueError("a y b deben ser positivos")
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_bt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    bt = math.exp(ln_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return min(1.0, bt * _fraccion_continua_beta(a, b, x) / a)
    return max(0.0, 1.0 - bt * _fraccion_continua_beta(b, a, 1.0 - x) / b)


def gamma_inc_reg(a: float, x: float) -> float:
    """P(a, x): funcion de distribucion de una Gamma(forma=a, tasa=1) en x."""
    if a <= 0:
        raise ValueError("a debe ser positivo")
    if x <= 0.0:
        return 0.0
    ln_pref = -x + a * math.log(x) - math.lgamma(a)
    if x < a + 1.0:
        ap, termino, suma = a, 1.0 / a, 1.0 / a
        for _ in range(_MAX_ITER):
            ap += 1.0
            termino *= x / ap
            suma += termino
            if abs(termino) < abs(suma) * _EPS:
                break
        return min(1.0, suma * math.exp(ln_pref))
    tiny = 1e-300
    b = x + 1.0 - a
    c = 1.0 / tiny
    d = 1.0 / b
    h = d
    for i in range(1, _MAX_ITER):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        d = tiny if abs(d) < tiny else d
        c = b + an / c
        c = tiny if abs(c) < tiny else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < _EPS:
            break
    return max(0.0, 1.0 - math.exp(ln_pref) * h)


def _biseccion(f: Callable[[float], float], objetivo: float, lo: float, hi: float, iteraciones: int = 100) -> float:
    """Raiz de f(x) = objetivo para f creciente en [lo, hi]."""
    for _ in range(iteraciones):
        medio = 0.5 * (lo + hi)
        if f(medio) < objetivo:
            lo = medio
        else:
            hi = medio
        if hi - lo <= 1e-15 * max(1.0, abs(hi)):
            break
    return 0.5 * (lo + hi)


def beta_ppf(q: float, a: float, b: float) -> float:
    """Cuantil q de una Beta(a, b)."""
    if not 0.0 <= q <= 1.0:
        raise ValueError("q debe estar en [0, 1]")
    if q == 0.0:
        return 0.0
    if q == 1.0:
        return 1.0
    return _biseccion(lambda x: beta_inc_reg(x, a, b), q, 0.0, 1.0)


def gamma_cdf(x: float, forma: float, tasa: float) -> float:
    return gamma_inc_reg(forma, x * tasa)


def gamma_ppf(q: float, forma: float, tasa: float) -> float:
    """Cuantil q de una Gamma(forma, tasa) (exacto, por biseccion)."""
    if not 0.0 < q < 1.0:
        raise ValueError("q debe estar en (0, 1)")
    hi = max(1.0, forma)
    while gamma_inc_reg(forma, hi) < q:
        hi *= 2.0
    return _biseccion(lambda x: gamma_inc_reg(forma, x), q, 0.0, hi) / tasa


def _gamma_ppf_rapida(q: float, forma: float, tasa: float) -> float:
    """Cuantil de la Gamma por Wilson-Hilferty (forma >= 10) o exacto en otro caso.

    Error relativo < 1e-3 para forma >= 10: suficiente para integrar un parametro de estorbo (CPC).
    """
    if forma < 10.0:
        return gamma_ppf(q, forma, tasa)
    z = _NORMAL.inv_cdf(q)
    t = 1.0 - 1.0 / (9.0 * forma) + z / (3.0 * math.sqrt(forma))
    return forma * max(t, 1e-9) ** 3 / tasa


def z_normal(prob: float) -> float:
    """Cuantil de la normal estandar."""
    return _NORMAL.inv_cdf(prob)


# ---------------------------------------------------------------------------
# Distribuciones posteriores
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Beta:
    """Beta(a, b) para una conversion (probabilidad) clic->compra."""

    a: float
    b: float

    def __post_init__(self) -> None:
        if self.a <= 0 or self.b <= 0:
            raise ValueError("Beta requiere a > 0 y b > 0")

    @property
    def media(self) -> float:
        return self.a / (self.a + self.b)

    @property
    def varianza(self) -> float:
        s = self.a + self.b
        return self.a * self.b / (s * s * (s + 1.0))

    def cdf(self, x: float) -> float:
        return beta_inc_reg(x, self.a, self.b)

    def sf(self, x: float) -> float:
        """P(conv > x)."""
        return 1.0 - beta_inc_reg(x, self.a, self.b)

    def ppf(self, q: float) -> float:
        return beta_ppf(q, self.a, self.b)

    def mediana_aprox(self) -> float:
        """Mediana aproximada (a - 1/3) / (a + b - 2/3), valida para a, b >= 1; si no, exacta."""
        if self.a >= 1.0 and self.b >= 1.0:
            return (self.a - 1.0 / 3.0) / (self.a + self.b - 2.0 / 3.0)
        return self.ppf(0.5)

    def intervalo(self, nivel: float) -> tuple[float, float]:
        cola = (1.0 - nivel) / 2.0
        return self.ppf(cola), self.ppf(1.0 - cola)


@dataclass(frozen=True)
class Gamma:
    """Gamma(forma, tasa) para la tasa de clics por unidad menor de gasto (lam = 1 / CPC)."""

    forma: float
    tasa: float

    def __post_init__(self) -> None:
        if self.forma <= 0 or self.tasa <= 0:
            raise ValueError("Gamma requiere forma > 0 y tasa > 0")

    @property
    def media(self) -> float:
        return self.forma / self.tasa

    def ppf(self, q: float) -> float:
        return gamma_ppf(q, self.forma, self.tasa)


def beta_desde_media_fuerza(media: float, fuerza_clics: float) -> Beta:
    """Prior debil: media esperada y 'fuerza' en clics equivalentes (a + b = fuerza)."""
    if not 0.0 < media < 1.0:
        raise ValueError("la media del prior debe estar en (0, 1)")
    if fuerza_clics <= 0:
        raise ValueError("la fuerza del prior debe ser positiva")
    return Beta(media * fuerza_clics, (1.0 - media) * fuerza_clics)


def actualizar_beta(prior: Beta, compras: int, clics: int) -> Beta:
    """Posterior Beta-Binomial."""
    if compras < 0 or clics < compras:
        raise ValueError("se exige 0 <= compras <= clics")
    return Beta(prior.a + compras, prior.b + (clics - compras))


def gamma_tasa_desde_cpc(cpc_prior_minor: float, fuerza_clics: float) -> Gamma:
    """Prior debil del CPC: media = 1/cpc_prior en clics por unidad menor, con `fuerza_clics` de peso."""
    if cpc_prior_minor <= 0 or fuerza_clics <= 0:
        raise ValueError("cpc_prior y fuerza deben ser positivos")
    return Gamma(fuerza_clics, fuerza_clics * cpc_prior_minor)


def actualizar_gamma_clics(prior: Gamma, clics: int, gasto_minor: float) -> Gamma:
    """Posterior Gamma-Poisson para lam: clics ~ Poisson(lam * gasto)."""
    if clics < 0 or gasto_minor < 0:
        raise ValueError("clics y gasto no pueden ser negativos")
    return Gamma(prior.forma + clics, prior.tasa + gasto_minor)


# ---------------------------------------------------------------------------
# Probabilidades sobre el CPA
# ---------------------------------------------------------------------------

def prob_cpa_menor(conv: Beta, lam: Gamma, cpa_limite_minor: float, nodos: int = 5) -> float:
    """P(CPA <= cpa_limite) con CPA = 1 / (lam * conv), integrando la incertidumbre del CPC.

    CPA <= L  <=>  conv >= 1 / (L * lam). Se promedia sobre `nodos` cuantiles del posterior de lam
    (puntos medios de cuantiles equiespaciados): determinista y sin Monte Carlo. `nodos=1` usa la media.
    """
    if cpa_limite_minor <= 0:
        return 0.0
    if nodos < 1:
        raise ValueError("nodos >= 1")
    if nodos == 1:
        lams = [lam.media]
    else:
        lams = [_gamma_ppf_rapida((j + 0.5) / nodos, lam.forma, lam.tasa) for j in range(nodos)]
    total = 0.0
    for l in lams:
        umbral = 1.0 / (cpa_limite_minor * l)
        total += 0.0 if umbral >= 1.0 else conv.sf(umbral)
    return total / len(lams)


def cpa_mediano_minor(conv: Beta, lam: Gamma) -> float:
    """CPA tipico: 1 / (lam_media * mediana(conv)). Aproximacion (CPC en su media posterior)."""
    return 1.0 / (lam.media * conv.mediana_aprox())


def intervalo_cpa_minor(conv: Beta, lam: Gamma, nivel: float) -> tuple[float, float]:
    """Intervalo creible aproximado del CPA (CPC fijo en su media posterior): (inferior, superior)."""
    cola = (1.0 - nivel) / 2.0
    p_bajo, p_alto = conv.ppf(cola), conv.ppf(1.0 - cola)
    inf = 1.0 / (lam.media * p_alto) if p_alto > 0 else math.inf
    sup = 1.0 / (lam.media * p_bajo) if p_bajo > 0 else math.inf
    return inf, sup


def prob_mejor(posteriores: Sequence[Beta], semilla: int, n_muestras: int = 4000) -> list[float]:
    """P(cada celda tiene la mayor conversion) por Monte Carlo con semilla (suma 1)."""
    if not posteriores:
        return []
    rng = random.Random(semilla)
    victorias = [0] * len(posteriores)
    for _ in range(n_muestras):
        muestras = [rng.betavariate(p.a, p.b) for p in posteriores]
        victorias[max(range(len(muestras)), key=muestras.__getitem__)] += 1
    return [v / n_muestras for v in victorias]


def prob_mayor_a_mediana_hermanos(posteriores: Sequence[Beta], indice: int, semilla: int, n_muestras: int = 4000) -> float:
    """P(la conversion de `indice` supera la mediana de la conversion de los demas) (D8: p_ganador)."""
    otros = [p for i, p in enumerate(posteriores) if i != indice]
    if not otros:
        raise ValueError("se necesitan hermanos para comparar")
    rng = random.Random(semilla)
    cuenta = 0
    for _ in range(n_muestras):
        propio = rng.betavariate(posteriores[indice].a, posteriores[indice].b)
        ref = sorted(rng.betavariate(p.a, p.b) for p in otros)
        m = len(ref)
        mediana = ref[m // 2] if m % 2 else 0.5 * (ref[m // 2 - 1] + ref[m // 2])
        cuenta += propio > mediana
    return cuenta / n_muestras


def prob_margen_por_clic_mayor(
    conv_a: Beta, lam_a: Gamma, contribucion_a_minor: float, costo_extra_a_pct: float,
    conv_b: Beta, lam_b: Gamma, contribucion_b_minor: float, costo_extra_b_pct: float,
    semilla: int, n_muestras: int = 4000,
) -> float:
    """P(margen por clic de A > margen por clic de B), margen = conv * contribucion - CPC * (1 + extra).

    Sirve para comparar mercados con economias distintas (IVA, comision, ticket): se compara
    dinero ganado por clic comprado, no la conversion cruda.
    """
    rng = random.Random(semilla)
    cuenta = 0
    for _ in range(n_muestras):
        ma = rng.betavariate(conv_a.a, conv_a.b) * contribucion_a_minor - (1 + costo_extra_a_pct) / rng.gammavariate(lam_a.forma, 1.0 / lam_a.tasa)
        mb = rng.betavariate(conv_b.a, conv_b.b) * contribucion_b_minor - (1 + costo_extra_b_pct) / rng.gammavariate(lam_b.forma, 1.0 / lam_b.tasa)
        cuenta += ma > mb
    return cuenta / n_muestras


# ---------------------------------------------------------------------------
# Intervalos frecuentistas exactos
# ---------------------------------------------------------------------------

def intervalo_clopper_pearson(compras: int, clics: int, confianza: float = 0.95) -> tuple[float, float]:
    """Intervalo exacto para una proporcion binomial."""
    if not 0 <= compras <= clics or clics == 0:
        raise ValueError("se exige 0 <= compras <= clics y clics > 0")
    alfa = 1.0 - confianza
    inf = 0.0 if compras == 0 else beta_ppf(alfa / 2.0, compras, clics - compras + 1)
    sup = 1.0 if compras == clics else beta_ppf(1.0 - alfa / 2.0, compras + 1, clics - compras)
    return inf, sup


def intervalo_poisson_exacto(eventos: int, confianza: float = 0.90) -> tuple[float, float]:
    """Intervalo exacto (Garwood) para la media de un conteo Poisson (compras)."""
    if eventos < 0:
        raise ValueError("eventos >= 0")
    alfa = 1.0 - confianza
    inf = 0.0 if eventos == 0 else gamma_ppf(alfa / 2.0, eventos, 1.0)
    sup = gamma_ppf(1.0 - alfa / 2.0, eventos + 1, 1.0)
    return inf, sup


def intervalo_cpa_poisson_minor(gasto_minor: float, compras: int, confianza: float = 0.90) -> tuple[float, float]:
    """IC del CPA = gasto / compras con IC Poisson exacto de las compras (formato de F1). Superior = inf si 0 compras."""
    inf, sup = intervalo_poisson_exacto(compras, confianza)
    return gasto_minor / sup, (gasto_minor / inf if inf > 0 else math.inf)


# ---------------------------------------------------------------------------
# Errores de las reglas de corte (modelo Poisson / binomial)
# ---------------------------------------------------------------------------

def prob_sin_compras_poisson(gasto_minor: float, cpa_real_minor: float) -> float:
    """P(0 compras habiendo gastado `gasto`) si el CPA real es `cpa_real` (Poisson): e^(-gasto/cpa)."""
    if cpa_real_minor <= 0:
        raise ValueError("cpa_real debe ser positivo")
    return math.exp(-gasto_minor / cpa_real_minor)


def prob_sin_compras_binomial(clics: int, conv: float) -> float:
    """P(0 compras en `clics` clics) con conversion `conv`: (1 - conv)^clics."""
    return (1.0 - conv) ** clics


def prob_falso_descarte_por_corte(k_corte: float, razon_cpa_real_sobre_equilibrio: float) -> float:
    """P de matar un anuncio cuyo CPA real = razon * CPA_BE con la regla 'gasto >= k*CPA_BE sin compra': e^(-k/razon)."""
    return math.exp(-k_corte / razon_cpa_real_sobre_equilibrio)


def gasto_minimo_para_error(cpa_real_minor: float, error_tolerable: float) -> float:
    """Gasto sin compra a partir del cual descartar un anuncio de CPA real `cpa_real` se equivoca <= `error_tolerable`."""
    return cpa_real_minor * math.log(1.0 / error_tolerable)


def prob_descarte_en_cascada(errores_por_filtro: Sequence[float]) -> float:
    """P de que un ganador real caiga en al menos uno de varios filtros independientes: 1 - prod(1 - e_i)."""
    sobrevive = 1.0
    for e in errores_por_filtro:
        sobrevive *= 1.0 - e
    return 1.0 - sobrevive


# ---------------------------------------------------------------------------
# Tamanos de muestra y efecto minimo detectable
# ---------------------------------------------------------------------------

def n_precision_relativa(conv: float, precision_relativa: float, confianza: float = 0.95) -> int:
    """Clics para estimar `conv` con semiancho relativo `precision_relativa` (aprox. normal).

    n = z^2 (1 - conv) / (conv * rel^2). Con conv = 2,5 %, rel = 25 %, 95 % -> ~2.400 clics (nota 16).
    """
    if not 0.0 < conv < 1.0 or precision_relativa <= 0:
        raise ValueError("conv en (0,1) y precision > 0")
    z = z_normal(1.0 - (1.0 - confianza) / 2.0)
    return math.ceil(z * z * (1.0 - conv) / (conv * precision_relativa ** 2))


def n_contraste_unilateral(conv_nula: float, conv_alterna: float, alfa: float, potencia: float) -> int:
    """Clics para distinguir `conv_alterna` de `conv_nula` con una prueba unilateral (aprox. normal)."""
    if conv_nula == conv_alterna:
        raise ValueError("las conversiones deben diferir")
    za, zb = z_normal(1.0 - alfa), z_normal(potencia)
    num = za * math.sqrt(conv_nula * (1.0 - conv_nula)) + zb * math.sqrt(conv_alterna * (1.0 - conv_alterna))
    return math.ceil((num / (conv_alterna - conv_nula)) ** 2)


def n_dos_proporciones(conv_a: float, conv_b: float, alfa: float, potencia: float, unilateral: bool = False) -> int:
    """Clics POR BRAZO para distinguir dos conversiones (misma cantidad de clics en ambos)."""
    if conv_a == conv_b:
        raise ValueError("las conversiones deben diferir")
    za = z_normal(1.0 - (alfa if unilateral else alfa / 2.0))
    zb = z_normal(potencia)
    varianza = conv_a * (1.0 - conv_a) + conv_b * (1.0 - conv_b)
    return math.ceil((za + zb) ** 2 * varianza / (conv_a - conv_b) ** 2)


def mde_relativo(clics: int, conv_base: float, alfa: float, potencia: float) -> float:
    """Efecto minimo detectable (aumento relativo de la conversion) con `clics` clics en una prueba unilateral
    contra una conversion de referencia `conv_base`. Devuelve inf si ni conv=1 alcanza."""
    if clics <= 0:
        raise ValueError("clics > 0")
    limite = 1.0 - 1e-9
    if n_contraste_unilateral(conv_base, limite, alfa, potencia) > clics:
        return math.inf
    alto = _biseccion(
        lambda c: -float(n_contraste_unilateral(conv_base, c, alfa, potencia)),
        -float(clics), conv_base + 1e-9, limite, iteraciones=80,
    )
    return alto / conv_base - 1.0


def clics_para_descartar_sin_compras(conv_equilibrio: float, alfa: float, prior: Beta) -> int:
    """Menor n tal que, con 0 compras en n clics, P(conv > conv_equilibrio | datos) <= alfa."""
    if not 0.0 < conv_equilibrio < 1.0:
        raise ValueError("conv_equilibrio en (0,1)")
    n = 0
    paso = 1
    while Beta(prior.a, prior.b + n).sf(conv_equilibrio) > alfa:
        n += paso
        if n > 1_000_000:
            raise ValueError("no converge")
    return n


def umbral_compras_matar(clics: int, conv_equilibrio: float, alfa: float, prior: Beta) -> int:
    """Mayor numero de compras k (en `clics`) con P(conv > conv_equilibrio | k) <= alfa; -1 si ni k=0 alcanza."""
    k = -1
    while k + 1 <= clics and actualizar_beta(prior, k + 1, clics).sf(conv_equilibrio) <= alfa:
        k += 1
    return k


def umbral_compras_seguir(clics: int, conv_equilibrio: float, prob_min: float, prior: Beta) -> int | None:
    """Menor numero de compras k con P(conv > conv_equilibrio | k) >= prob_min; None si no se alcanza."""
    for k in range(clics + 1):
        if actualizar_beta(prior, k, clics).sf(conv_equilibrio) >= prob_min:
            return k
    return None
