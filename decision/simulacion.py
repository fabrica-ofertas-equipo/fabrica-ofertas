"""Simulaciones Monte Carlo (con semilla) de las reglas secuenciales de `reglas.py`.

Miden las garantias operativas: tasa de ganadores descartados, de perdedores escalados, de resultados
inconclusos y gasto hasta la decision, bajo lectura diaria completa ("espiar" cada dia infla los falsos
positivos: por eso se simula la regla tal como correra, no una prueba unica al final).

Todo es reproducible: cada corrida usa `random.Random(semilla + indice)`. Sin red, sin dependencias.

Uso desde la raiz del repositorio:
    python3 -m decision.simulacion --corridas 2000 --semilla 20261106

Los escenarios y la economia de referencia son DATOS DE PRUEBA, no recomendaciones: la economia real viene
de economia.json y los umbrales de empresa/parametros.yaml.
"""

from __future__ import annotations

import argparse
import math
import random
import statistics
from dataclasses import dataclass
from typing import Optional

from . import estadistica as est
from .reglas import Accion, EvidenciaCelda, LimitesCelda, ParametrosDecision, evaluar_celda, parametros_desde_mapeo

# Espejo del bloque YAML de docs/08-protocolo-estadistico-del-testeo.md (parametros.yaml, prefijo estadistica.).
# Un test verifica que ambos coinciden. Son [HIPOTESIS] a calibrar con datos propios.
PARAMETROS_REFERENCIA: dict = {
    "estadistica.prior_conv_fuerza_clics": 50,
    "estadistica.prior_cpc_fuerza_clics": 20,
    "estadistica.alfa_descarte": 0.05,
    "estadistica.alfa_descarte_tope": 0.20,
    "estadistica.p_escala": 0.80,
    "estadistica.k_min_matar": 2.0,
    "estadistica.n_min_escala": 15,
    "estadistica.ventana_no_decidir_h": 72,
    "estadistica.nodos_cpc": 5,
}

# Economia de referencia de la simulacion (USD, unidad menor): CPA_BE 15,00 y CPA_obj = 0,6 * CPA_BE.
CPA_BE_REF_MINOR = 1500
FACTOR_OBJETIVO_REF = 0.6


@dataclass(frozen=True)
class Escenario:
    nombre: str
    cpc_minor: float      # CPC real (unidad menor por clic)
    conv: float           # conversion clic->compra real
    descripcion: str

    @property
    def cpa_minor(self) -> float:
        return self.cpc_minor / self.conv

    def razon_cpa_sobre_be(self, cpa_be_minor: int = CPA_BE_REF_MINOR) -> float:
        return self.cpa_minor / cpa_be_minor


ESCENARIOS_REFERENCIA: tuple[Escenario, ...] = (
    Escenario("A ganador fuerte, CPC bajo", 25.0, 0.25 / 6.75, "CPC 0,25; conversion 3,70 %; CPA 6,75 = 0,45 x equilibrio"),
    Escenario("B ganador en objetivo, CPC alto", 45.0, 0.05, "CPC 0,45; conversion 5,00 %; CPA 9,00 = objetivo (0,60 x equilibrio)"),
    Escenario("C ganador justo", 35.0, 0.0275, "CPC 0,35; conversion 2,75 %; CPA 12,73 = 0,85 x equilibrio"),
    Escenario("D equilibrio", 40.0, 0.40 / 15.0, "CPC 0,40; conversion 2,67 %; CPA 15,00 = equilibrio"),
    Escenario("E perdedor moderado", 45.0, 0.02, "CPC 0,45; conversion 2,00 %; CPA 22,50 = 1,5 x equilibrio"),
    Escenario("F perdedor severo", 70.0, 0.01, "CPC 0,70; conversion 1,00 %; CPA 70,00 = 4,7 x equilibrio"),
)


@dataclass(frozen=True)
class ConfigSim:
    presupuesto_diario_minor: int
    tope_gasto_minor: int                 # tope por celda de la simulacion (dato de prueba, lo fija el dueño en la vida real)
    max_dias: int
    sigma_gasto: float                    # variacion diaria del gasto respecto del presupuesto
    sigma_cpc: float                      # variacion diaria del CPC
    sigma_conv: float                     # sobredispersion diaria de la conversion (0 = binomial puro)
    horas_iniciales: float = 0.0


CONFIG_REFERENCIA = ConfigSim(presupuesto_diario_minor=1500, tope_gasto_minor=22500, max_dias=40,
                              sigma_gasto=0.15, sigma_cpc=0.20, sigma_conv=0.0)


def parametros_referencia(cpa_be_minor: int = CPA_BE_REF_MINOR, factor: float = FACTOR_OBJETIVO_REF,
                          cpc_prior_minor: float = 40.0, conv_prior: float = 0.025,
                          cambios: Optional[dict] = None) -> ParametrosDecision:
    """Parametros de la simulacion; `cambios` = {"alfa_descarte": 0.1, ...} para sensibilidades (no muta el espejo)."""
    economia = {"moneda": "USD", "cpa_equilibrio_visto_minor": cpa_be_minor,
                "cpa_objetivo_minor": int(round(factor * cpa_be_minor)),
                "cpc_esperado_minor": cpc_prior_minor, "conv_central": conv_prior}
    mapeo = dict(PARAMETROS_REFERENCIA)
    for nombre, valor in (cambios or {}).items():
        mapeo[f"estadistica.{nombre}"] = valor
    return parametros_desde_mapeo(mapeo, economia)


@dataclass(frozen=True)
class ResultadoCorrida:
    accion: Accion
    codigo: str
    gasto_minor: int
    dias: int
    clics: int
    compras: int


def _poisson(rng: random.Random, lam: float) -> int:
    """Poisson(lam) como Binomial(N, lam/N) con N grande (determinista dada la semilla)."""
    if lam <= 0:
        return 0
    n = max(2000, int(50 * lam))
    return rng.binomialvariate(n, lam / n)


def simular_corrida(esc: Escenario, par: ParametrosDecision, lim: LimitesCelda, cfg: ConfigSim, semilla: int) -> ResultadoCorrida:
    """Una celda con lectura y decision diaria hasta MATAR / ESCALAR / INCONCLUSO (o max_dias)."""
    rng = random.Random(semilla)
    gasto = clics = compras = 0
    res_ultimo = None
    for dia in range(1, cfg.max_dias + 1):
        g_dia = cfg.presupuesto_diario_minor * math.exp(rng.gauss(-0.5 * cfg.sigma_gasto ** 2, cfg.sigma_gasto))
        g_dia = min(g_dia, 1.75 * cfg.presupuesto_diario_minor)
        g_dia = int(round(min(g_dia, max(0, (lim.tope_gasto_celda_minor or 0) - gasto))))  # el spend_cap corta en el tope
        cpc_dia = esc.cpc_minor * math.exp(rng.gauss(-0.5 * cfg.sigma_cpc ** 2, cfg.sigma_cpc))
        c_dia = _poisson(rng, g_dia / cpc_dia)
        conv_dia = esc.conv * (math.exp(rng.gauss(-0.5 * cfg.sigma_conv ** 2, cfg.sigma_conv)) if cfg.sigma_conv else 1.0)
        k_dia = rng.binomialvariate(c_dia, min(conv_dia, 0.999)) if c_dia else 0
        gasto += g_dia
        clics += c_dia
        compras += k_dia
        ev = EvidenciaCelda("sim", "oferta_mercado", par.moneda, gasto, clics, compras,
                            cfg.horas_iniciales + 24.0 * dia, True, True)
        d = evaluar_celda(ev, par, lim, con_intervalo=False)
        res_ultimo = ResultadoCorrida(d.accion, d.codigo, gasto, dia, clics, compras)
        if d.accion in (Accion.MATAR, Accion.ESCALAR, Accion.INCONCLUSO, Accion.BLOQUEADO):
            return res_ultimo
    return ResultadoCorrida(Accion.INCONCLUSO, "max_dias", gasto, cfg.max_dias, clics, compras)


@dataclass(frozen=True)
class ResumenEscenario:
    escenario: str
    corridas: int
    razon_cpa_be: float
    p_matar: float
    p_matar_antes_tope: float
    p_escalar: float
    p_inconcluso: float
    gasto_medio_minor: float
    gasto_mediano_minor: float
    gasto_p90_minor: float
    dias_medios: float
    compras_medias: float
    ic95_p_matar: tuple[float, float]
    ic95_p_escalar: tuple[float, float]


def simular_escenario(
    esc: Escenario, par: ParametrosDecision, lim: LimitesCelda, cfg: ConfigSim, corridas: int, semilla: int,
) -> ResumenEscenario:
    res = [simular_corrida(esc, par, lim, cfg, semilla * 1_000_003 + i) for i in range(corridas)]
    n = len(res)
    matar = sum(r.accion == Accion.MATAR for r in res)
    escalar = sum(r.accion == Accion.ESCALAR for r in res)
    incon = n - matar - escalar
    gastos = sorted(r.gasto_minor for r in res)
    p90 = gastos[min(n - 1, int(math.ceil(0.9 * n)) - 1)]
    return ResumenEscenario(
        esc.nombre, n, esc.razon_cpa_sobre_be(par.cpa_equilibrio_minor),
        matar / n, sum(r.accion == Accion.MATAR and r.gasto_minor < (lim.tope_gasto_celda_minor or 0) for r in res) / n,
        escalar / n, incon / n,
        statistics.fmean(gastos), statistics.median(gastos), float(p90),
        statistics.fmean(r.dias for r in res), statistics.fmean(r.compras for r in res),
        est.intervalo_clopper_pearson(matar, n, 0.95), est.intervalo_clopper_pearson(escalar, n, 0.95),
    )


def curva_operativa(
    razones: list[float], cpc_minor: float, par: ParametrosDecision, lim: LimitesCelda, cfg: ConfigSim,
    corridas: int, semilla: int,
) -> list[ResumenEscenario]:
    """P(MATAR) y P(ESCALAR) en funcion de la razon CPA real / CPA_BE, a un CPC fijo (curva operativa de la regla)."""
    out = []
    for rho in razones:
        conv = cpc_minor / (rho * par.cpa_equilibrio_minor)
        e = Escenario(f"rho={rho:.2f}", cpc_minor, conv, f"CPA real = {rho:.2f} x equilibrio")
        out.append(simular_escenario(e, par, lim, cfg, corridas, semilla))
    return out


def falso_descarte_regla_ingenua(esc: Escenario, gasto_corte_minor: float, corridas: int, semilla: int) -> tuple[float, float]:
    """(simulado, analitico) de matar un anuncio cuando gasta `gasto_corte` sin ninguna compra.

    Analitico: exp(-gasto/CPA). Con CPA = 16,2 y corte de 10: ~54 % de ganadores muertos (nota 12 §7.2)."""
    rng = random.Random(semilla)
    clics_medios = gasto_corte_minor / esc.cpc_minor
    cuenta = 0
    for _ in range(corridas):
        clics = _poisson(rng, clics_medios)
        cuenta += (rng.binomialvariate(clics, esc.conv) if clics else 0) == 0
    return cuenta / corridas, est.prob_sin_compras_poisson(gasto_corte_minor, esc.cpa_minor)


def ejecutar_referencia(corridas: int, semilla: int, cfg: ConfigSim = CONFIG_REFERENCIA,
                        escenarios: tuple[Escenario, ...] = ESCENARIOS_REFERENCIA,
                        par: Optional[ParametrosDecision] = None) -> list[ResumenEscenario]:
    par = par or parametros_referencia()
    lim = LimitesCelda(cfg.tope_gasto_minor)
    return [simular_escenario(e, par, lim, cfg, corridas, semilla) for e in escenarios]


def _fila(r: ResumenEscenario) -> str:
    f = lambda x: f"{100 * x:.1f} %"
    return (f"| {r.escenario} | {r.razon_cpa_be:.2f} | {f(r.p_matar)} ({f(r.p_matar_antes_tope)}) | {f(r.p_escalar)} | {f(r.p_inconcluso)} | "
            f"{r.gasto_medio_minor / 100:.0f} | {r.gasto_mediano_minor / 100:.0f} | {r.gasto_p90_minor / 100:.0f} | "
            f"{r.dias_medios:.1f} | {r.compras_medias:.1f} |")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Simulaciones Monte Carlo de las reglas de decision (sin efectos externos).")
    ap.add_argument("--corridas", type=int, default=2000)
    ap.add_argument("--semilla", type=int, default=20261106)
    ap.add_argument("--sigma-conv", type=float, default=0.0, help="sobredispersion diaria de la conversion (robustez)")
    ap.add_argument("--presupuesto-diario", type=int, default=None, help="unidad menor")
    ap.add_argument("--tope", type=int, default=None, help="tope de gasto por celda, unidad menor")
    ap.add_argument("--alfa", type=float, default=None)
    ap.add_argument("--alfa-tope", type=float, default=None)
    ap.add_argument("--p-escala", type=float, default=None)
    a = ap.parse_args(argv)
    cfg = ConfigSim(**{**CONFIG_REFERENCIA.__dict__, "sigma_conv": a.sigma_conv,
                       "presupuesto_diario_minor": a.presupuesto_diario or CONFIG_REFERENCIA.presupuesto_diario_minor,
                       "tope_gasto_minor": a.tope or CONFIG_REFERENCIA.tope_gasto_minor})
    cambios = {n: v for n, v in (("alfa_descarte", a.alfa), ("alfa_descarte_tope", a.alfa_tope), ("p_escala", a.p_escala)) if v is not None}
    par = parametros_referencia(cambios=cambios)
    print(f"corridas={a.corridas} semilla={a.semilla} sigma_conv={a.sigma_conv} presupuesto_diario={cfg.presupuesto_diario_minor/100:.0f} "
          f"tope={cfg.tope_gasto_minor/100:.0f} (USD, datos de prueba)")
    print("| escenario | CPA/BE | MATAR (antes del tope) | ESCALAR | INCONCLUSO | gasto medio | mediana | p90 | dias | compras |")
    print("|---|---|---|---|---|---|---|---|---|---|")
    for r in ejecutar_referencia(a.corridas, a.semilla, cfg, par=par):
        print(_fila(r))
    print()
    print("Curva operativa (CPC 0,40 USD):")
    print("| CPA/BE | MATAR | ESCALAR | INCONCLUSO | gasto medio |")
    print("|---|---|---|---|---|")
    for r in curva_operativa([0.4, 0.5, 0.6, 0.7, 0.85, 1.0, 1.15, 1.3, 1.5, 2.0], 40.0, par,
                             LimitesCelda(cfg.tope_gasto_minor), cfg, a.corridas, a.semilla):
        print(f"| {r.razon_cpa_be:.2f} | {100*r.p_matar:.1f} % | {100*r.p_escalar:.1f} % | {100*r.p_inconcluso:.1f} % | {r.gasto_medio_minor/100:.0f} |")
    print()
    print("Regla ingenua 'matar al gastar G sin compras' (analitica | simulada):")
    for g in (600, 1000, 1500):
        for e in ESCENARIOS_REFERENCIA[:3]:
            sim, ana = falso_descarte_regla_ingenua(e, g, a.corridas, a.semilla)
            print(f"  G={g/100:.0f} USD, {e.nombre} (CPA {e.cpa_minor/100:.2f}): analitica {100*ana:.1f} %, simulada {100*sim:.1f} %")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
