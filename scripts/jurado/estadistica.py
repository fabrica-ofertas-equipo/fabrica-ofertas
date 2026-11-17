"""Estadística del Jurado de creativos, sin dependencias: AUC, DeLong, p-valor por permutación, Brier, Wilson, kappa y bootstrap.

Convención: ``etiquetas`` es una lista de 0/1 (1 = «positivo»: la pieza rindió por encima de lo esperado en esa madurez);
``puntajes`` es lo que predijo el jurado (mayor = más probable que rinda). Cada función devuelve ``None`` cuando el cálculo
no tiene sentido (una sola clase, muestra mínima): nunca un número inventado.
"""
from __future__ import annotations

import math
import random
from typing import Sequence

Z95 = 1.959963984540054


def _redondear(xs: Sequence[float]) -> list[float]:
    # Los empates deben ser empates exactos aunque el cálculo previo deje ruido de coma flotante.
    return [round(float(x), 12) for x in xs]


def rangos_promedio(valores: Sequence[float]) -> list[float]:
    """Rangos 1..n con empates promediados (midrank)."""
    v = _redondear(valores)
    n = len(v)
    orden = sorted(range(n), key=lambda i: v[i])
    rangos = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and v[orden[j + 1]] == v[orden[i]]:
            j += 1
        medio = (i + j) / 2 + 1
        for k in range(i, j + 1):
            rangos[orden[k]] = medio
        i = j + 1
    return rangos


def _validar(puntajes: Sequence[float], etiquetas: Sequence[int]) -> tuple[int, int] | None:
    if len(puntajes) != len(etiquetas):
        raise ValueError("puntajes y etiquetas deben tener el mismo largo")
    m = sum(1 for e in etiquetas if e)
    n = len(etiquetas) - m
    return (m, n) if m and n else None


def auc(puntajes: Sequence[float], etiquetas: Sequence[int]) -> float | None:
    """AUC de Mann-Whitney con empates a medias. 0,5 = azar; 1 = perfecto; 0 = perfectamente invertido."""
    mn = _validar(puntajes, etiquetas)
    if mn is None:
        return None
    m, n = mn
    rangos = rangos_promedio(puntajes)
    suma = sum(r for r, e in zip(rangos, etiquetas) if e)
    return (suma - m * (m + 1) / 2) / (m * n)


def _componentes_delong(puntajes: Sequence[float], etiquetas: Sequence[int]) -> tuple[list[float], list[float]]:
    """V10 (por positivo) y V01 (por negativo), algoritmo rápido de Sun y Xu (2014) con empates."""
    pos = [p for p, e in zip(puntajes, etiquetas) if e]
    neg = [p for p, e in zip(puntajes, etiquetas) if not e]
    m, n = len(pos), len(neg)
    tz = rangos_promedio(list(pos) + list(neg))
    tx = rangos_promedio(pos)
    ty = rangos_promedio(neg)
    v10 = [(tz[i] - tx[i]) / n for i in range(m)]
    v01 = [1.0 - (tz[m + j] - ty[j]) / m for j in range(n)]
    return v10, v01


def _cov(a: Sequence[float], b: Sequence[float]) -> float:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (n - 1)


def auc_con_ic(puntajes: Sequence[float], etiquetas: Sequence[int]) -> dict | None:
    """AUC con intervalo de confianza al 95 % de DeLong (aprox. normal, recortado a [0, 1]).

    ``ic95`` es ``None`` si hay menos de 2 positivos o 2 negativos. Con separación perfecta la varianza es 0 y el
    intervalo se reduce al punto (un AUC de 1,0 con pocos casos no es una prueba: lo dicen ``positivos`` y ``negativos``).
    """
    mn = _validar(puntajes, etiquetas)
    if mn is None:
        return None
    m, n = mn
    a = auc(puntajes, etiquetas)
    res = {"auc": a, "positivos": m, "negativos": n, "ic95": None, "se": None}
    if m < 2 or n < 2:
        return res
    v10, v01 = _componentes_delong(puntajes, etiquetas)
    var = _cov(v10, v10) / m + _cov(v01, v01) / n
    se = math.sqrt(max(var, 0.0))
    res["se"] = se
    res["ic95"] = [max(0.0, a - Z95 * se), min(1.0, a + Z95 * se)]
    return res


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def comparar_auc_pareado(a: Sequence[float], b: Sequence[float], etiquetas: Sequence[int]) -> dict | None:
    """Prueba de DeLong para dos AUC correlacionados sobre las MISMAS piezas. H1: AUC(a) > AUC(b), p unilateral."""
    if len(a) != len(b):
        raise ValueError("a y b deben tener el mismo largo")
    mn = _validar(a, etiquetas)
    if mn is None or mn[0] < 2 or mn[1] < 2:
        return None
    m, n = mn
    va10, va01 = _componentes_delong(a, etiquetas)
    vb10, vb01 = _componentes_delong(b, etiquetas)
    auc_a, auc_b = sum(va10) / m, sum(vb10) / m
    var_a = _cov(va10, va10) / m + _cov(va01, va01) / n
    var_b = _cov(vb10, vb10) / m + _cov(vb01, vb01) / n
    cov_ab = _cov(va10, vb10) / m + _cov(va01, vb01) / n
    var_d = var_a + var_b - 2.0 * cov_ab
    dif = auc_a - auc_b
    res = {"auc_a": auc_a, "auc_b": auc_b, "diferencia": dif, "se_diferencia": None, "z": None, "p_unilateral": None}
    if var_d <= 1e-15:
        # Sin variabilidad en la diferencia: si es 0 no hay evidencia; si no, es determinista pero no inferible.
        res["p_unilateral"] = 0.5 if abs(dif) < 1e-12 else None
        return res
    se = math.sqrt(var_d)
    z = dif / se
    res.update({"se_diferencia": se, "z": z, "p_unilateral": 1.0 - normal_cdf(z)})
    return res


def p_contra_azar(puntajes: Sequence[float], etiquetas: Sequence[int], semilla: int, permutaciones: int = 2000) -> float | None:
    """p-valor unilateral por permutación de etiquetas: P(AUC_azar ≥ AUC observado). Reproducible con la semilla."""
    mn = _validar(puntajes, etiquetas)
    if mn is None:
        return None
    m, n = mn
    rangos = rangos_promedio(puntajes)
    obs = (sum(r for r, e in zip(rangos, etiquetas) if e) - m * (m + 1) / 2) / (m * n)
    rng = random.Random(semilla)
    idx = list(range(len(rangos)))
    mayores = 0
    for _ in range(permutaciones):
        suma = sum(rangos[i] for i in rng.sample(idx, m))
        a = (suma - m * (m + 1) / 2) / (m * n)
        if a >= obs - 1e-12:
            mayores += 1
    return (1 + mayores) / (permutaciones + 1)


def brier(probabilidades: Sequence[float], etiquetas: Sequence[int]) -> float | None:
    """Error cuadrático medio de las probabilidades. 0 = perfecto; 0,25 = apostar siempre 50/50."""
    if not etiquetas or len(probabilidades) != len(etiquetas):
        return None
    return sum((min(1.0, max(0.0, p)) - e) ** 2 for p, e in zip(probabilidades, etiquetas)) / len(etiquetas)


def brier_prevalencia(etiquetas: Sequence[int]) -> float | None:
    """Brier de predecir siempre la tasa de positivos: la línea base honesta (el 0,25 solo vale con prevalencia 50 %)."""
    if not etiquetas:
        return None
    prev = sum(1 for e in etiquetas if e) / len(etiquetas)
    return sum((prev - e) ** 2 for e in etiquetas) / len(etiquetas)


def wilson(aciertos: int, n: int, z: float = Z95) -> list[float] | None:
    """Intervalo de Wilson para una proporción. Supone votos independientes: con jueces del mismo modelo es OPTIMISTA."""
    if n <= 0:
        return None
    p = aciertos / n
    d = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / d
    mitad = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [max(0.0, centro - mitad), min(1.0, centro + mitad)]


def kappa_fleiss_binario(conteos_si: Sequence[int], jueces_por_item: int) -> float | None:
    """Kappa de Fleiss para votos sí/no; ``conteos_si[i]`` = votos «sí» del ítem i entre ``jueces_por_item`` jueces."""
    n = jueces_por_item
    items = len(conteos_si)
    if n < 2 or items < 1:
        return None
    p_i = [(k * (k - 1) + (n - k) * (n - k - 1)) / (n * (n - 1)) for k in conteos_si]
    p_barra = sum(p_i) / items
    p_si = sum(conteos_si) / (items * n)
    p_e = p_si ** 2 + (1 - p_si) ** 2
    if p_e >= 1.0 - 1e-12:
        return None  # todos votaron igual en todo: el kappa no está definido
    return (p_barra - p_e) / (1 - p_e)


def percentil(valores: Sequence[float], p: float) -> float:
    """Percentil por rango más cercano (determinista, sin interpolar)."""
    v = sorted(valores)
    return v[min(len(v) - 1, max(0, int(p * (len(v) - 1) + 0.5)))]


def rangos_bootstrap(matriz: Sequence[Sequence[tuple[int, float] | None]], semilla: int, replicas: int = 1000,
                     epsilon: float = 1e-3) -> list[dict]:
    """Puestos probables de cada pieza al remuestrear AVATARES con reemplazo.

    ``matriz[a][p]`` = ``(voto 0/1, puntaje_general 0-10)`` del avatar ``a`` sobre la pieza ``p``, o ``None`` si no votó.
    Puesto 1 = el mejor. Devuelve ``[{p05, p50, p95}, ...]`` por pieza. Mide solo la incertidumbre por la elección de
    avatares; el sesgo COMÚN del modelo (todos los avatares se equivocan igual) solo lo mide la calibración con lo cobrado.
    """
    n_av = len(matriz)
    n_pz = len(matriz[0]) if n_av else 0
    rng = random.Random(semilla)
    puestos: list[list[float]] = [[] for _ in range(n_pz)]
    for _ in range(replicas):
        muestra = [matriz[rng.randrange(n_av)] for _ in range(n_av)]
        scores = []
        for p in range(n_pz):
            vs = [fila[p] for fila in muestra if fila[p] is not None]
            if not vs:
                scores.append(-1.0)
            else:
                scores.append(sum(v for v, _ in vs) / len(vs) + epsilon * (sum(q for _, q in vs) / len(vs)) / 10.0)
        rangos = rangos_promedio([-s for s in scores])  # mayor score = puesto 1
        for p in range(n_pz):
            puestos[p].append(rangos[p])
    return [{"p05": percentil(x, 0.05), "p50": percentil(x, 0.50), "p95": percentil(x, 0.95)} for x in puestos]
