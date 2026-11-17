#!/usr/bin/env python3
"""escala_lectura.py: apoyo determinista y de SOLO LECTURA de la skill D9 (escalado). Sin red, sin escrituras, sin claves.

«La IA propone, el código dispone»: este script es el código. Calcula lo que el Maker de D9 no debe calcular a mano (nivel de
ganador, señales de suba, techos, paso permitido, orden de presupuesto en borrador) REUSANDO el código del motor, sin
reimplementarlo: ``engine.limites`` (agregados, ritmo, máximo teórico), ``decision.entradas.limites_meta_desde`` y
``decision.reglas.proponer_aumento_presupuesto`` (paso, horas mínimas, 1,75 ×), ``scripts.validar_esquemas`` (claves críticas y
coherencia de límites) y el esquema ``orden_presupuesto``. No ejecuta nada: imprime un JSON en stdout. Quien ejecuta (guard,
``meta.subir_presupuesto``, dueño) vuelve a comprobar todo; este dictamen NO es una autorización.

Es PROVISIONAL: ``engine/`` aún no tiene ``escala.py`` (brecha B2-08/B2-10). Cuando exista, este archivo pasa a ser un
envoltorio y manda el motor (``PEDIDOS.md`` P-10).

Uso (desde la raíz, con el intérprete del proyecto)::

    .venv/bin/python .claude/skills/d9-escalado/scripts/escala_lectura.py dictamen --entrada e.json [--limites L.yaml] [--parametros P.yaml]
    .venv/bin/python .claude/skills/d9-escalado/scripts/escala_lectura.py replica  --entrada r.json [--limites L.yaml] [--parametros P.yaml]
    .venv/bin/python .claude/skills/d9-escalado/scripts/escala_lectura.py validar  --archivo propuesta-de-suba.json

Con ``--limites`` / ``--parametros`` se leen los archivos reales (``empresa/limites.yaml``, ``empresa/parametros.yaml``) y sustituyen
a los bloques ``limites`` / ``parametros`` de la entrada. Hoy esos archivos están en ``null``: el resultado correcto es BLOQUEADO (5).

Salida: 0 = dictamen emitido (PROPONER o NO_PROPONER; léase ``estado``) · 2 uso · 3 validación (dato incoherente, float, moneda) ·
4 bloqueado por PAUSA · 5 límite o parámetro ausente (fail-closed). Todo importe es entero en la unidad menor; nunca ``float``.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from decimal import ROUND_FLOOR, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Mapping

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))

import yaml  # noqa: E402

from decision.entradas import limites_meta_desde  # noqa: E402
from decision.reglas import proponer_aumento_presupuesto  # noqa: E402
from engine import comun  # noqa: E402
from engine.errores import ErrorFabrica, ErrorLimite, ErrorUso, ErrorValidacion  # noqa: E402
from engine.limites import CampanaActiva, Limites, exigir_agregados_del_efecto, exigir_ritmo, max_teorico_diario  # noqa: E402
from scripts import validar_esquemas as V  # noqa: E402

VERSION_SCRIPT = "0.1.0"
VERSION_REGLAS = "0.1.0"
RX_OFERTA = re.compile(r"^OF-[0-9]{6}-[0-9]{2}$")
ROLES = ("test", "escala")
NIVELES = ("N0", "N1", "N2", "N3", "N4")
# Claves de parámetros que este script lee (grupo.clave). Las que NO existen aún en empresa/parametros.yaml son pedidos a S-A
# (PEDIDOS.md P-02): sin ellas el script se detiene en 5 (fail-closed); no se inventa ningún valor.
PARAMETROS_ESCALA = (
    "escalado.campeon_compras_min", "escalado.campeon_cpa_max_x_be", "escalado.cpa_3d_factor",
    "escalado.suba_presupuesto_gastado_min_pct", "escalado.escalera_multiplo_max", "escalado.reduccion_pct",
    "escalado.compras_min_ventana", "escalado.cpa_subir_factor", "escalado.revertir_cpa_factor",
    "escalado.max_campanas_escala", "testeo.p_escala", "testeo.k_corte",
)
PARAMETROS_REPLICA = (
    "mercados.hija_requiere_madre_validada", "mercados.aperturas_max_por_ventana", "mercados.ventana_dias",
    "mercados.ganadores_transferidos_max",
)
# Elegibilidad E0 (spec 10-escalado §4 paso 1): banderas que debe producir CÓDIGO (preflight, compliance.verificar, senal_pausa, meta.monitor, D8); el Maker
# solo las copia citando la fuente y el QA las recomputa. Faltar una = BLOQUEADO (5); estar en false = NO_PROPONER. Hasta que exista ``engine/escala.py
# elegibilidad`` (PEDIDOS.md P-10) las reúne quien arma la entrada.
CHEQUEOS_E0 = ("riesgo_nivel", "sello_x1_vigente", "cuenta_saludable", "tracking_sano", "sin_incidente_d10", "sin_congelacion",
               "sin_alerta_fatiga", "reembolsos_disputas_ok", "hoja_no_pausada", "macro_nicho_permitido", "limite_diario_meta_ok")
# Extras que la operación «escalar» necesita y CLAVES_CRITICAS["escalar"] no lista (las usa el cálculo de este script).
LIMITES_EXTRA = ("moneda_limites", "factor_techo_teorico_diario", "max_cambios_presupuesto_por_hora_por_conjunto",
                 "segundos_min_entre_ediciones", "ofertas_en_test_simultaneas_max")


# ----------------------------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------------------------
def _leer(ruta: str | Path) -> Any:
    ruta = Path(ruta)
    try:
        texto = ruta.read_text(encoding="utf-8")
    except OSError as exc:
        raise ErrorUso(f"no se puede leer {ruta}: {exc.strerror}") from exc
    try:
        return yaml.safe_load(texto) if ruta.suffix in (".yaml", ".yml") else json.loads(texto)
    except (ValueError, yaml.YAMLError) as exc:
        raise ErrorValidacion(f"{ruta} no es un {ruta.suffix[1:] or 'JSON'} válido") from exc


def _aplanar_parametros(doc: Mapping[str, Any]) -> dict[str, Any]:
    """``{"grupos": {g: {k: {"valor": v}}}}`` (parametros.yaml) -> ``{"g.k": v}``; un mapa ya plano pasa tal cual."""
    grupos = doc.get("grupos")
    if not isinstance(grupos, Mapping):
        return dict(doc)
    plano: dict[str, Any] = {}
    for g, claves in grupos.items():
        if isinstance(claves, Mapping):
            for k, entrada in claves.items():
                if isinstance(entrada, Mapping) and "valor" in entrada:
                    plano[f"{g}.{k}"] = entrada["valor"]
    return plano


def _dec(valor: Any, nombre: str) -> Decimal:
    if isinstance(valor, bool) or valor is None:
        raise ErrorValidacion(f"{nombre}: se esperaba un número, llegó {valor!r}")
    try:
        return Decimal(str(valor))
    except InvalidOperation as exc:
        raise ErrorValidacion(f"{nombre}: no es un decimal: {valor!r}") from exc


def _entero(valor: Any, nombre: str) -> int:
    return comun.exigir_importe(valor, nombre)


def _piso(x: Decimal) -> int:
    return int(x.to_integral_value(rounding=ROUND_FLOOR))


def _vacio(v: Any) -> bool:
    return v is None or (isinstance(v, (list, dict)) and not v)


def _pct_texto(x: Decimal) -> str:
    return format(x.quantize(Decimal("0.01")), "f")


def _resultado(estado: str, codigo: str, **resto: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "version_script": VERSION_SCRIPT, "version_reglas": VERSION_REGLAS, "estado": estado, "codigo": codigo,
        "aviso": "Dictamen de apoyo (código de solo lectura). No autoriza nada: el guard, el sello de X1 y el dueño vuelven a comprobar.",
    }
    base.update(resto)
    return base


def _preparar(entrada: Any, args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not isinstance(entrada, dict):
        raise ErrorValidacion("la entrada debe ser un objeto JSON")
    flotantes = V.buscar_floats(entrada)
    if flotantes:
        raise ErrorValidacion(f"float prohibido en la entrada (usar enteros o cadenas decimales): {flotantes[:5]}")
    lim = _leer(args.limites) if getattr(args, "limites", None) else entrada.get("limites")
    par_doc = _leer(args.parametros) if getattr(args, "parametros", None) else entrada.get("parametros")
    if not isinstance(lim, dict):
        raise ErrorValidacion("faltan los límites (bloque «limites» de la entrada o --limites)")
    if not isinstance(par_doc, dict):
        raise ErrorValidacion("faltan los parámetros (bloque «parametros» de la entrada o --parametros)")
    return entrada, lim, _aplanar_parametros(par_doc)


def _faltantes_limites(lim: Mapping[str, Any]) -> list[str]:
    claves = list(V.CLAVES_CRITICAS["escalar"]) + [k for k in LIMITES_EXTRA if k not in V.CLAVES_CRITICAS["escalar"]]
    return [k for k in claves if _vacio(lim.get(k))]


def _gate_de(nivel: str, accion: str = "accion:subir_presupuesto_d9") -> str:
    """Gate de la tabla única (``contratos/gates.json``); nunca se escribe a mano."""
    gates = json.loads((RAIZ / "contratos" / "gates.json").read_text(encoding="utf-8"))
    return str(gates["entradas"][accion]["gate"][nivel])


# ----------------------------------------------------------------------------------------------
# Nivel de ganador (criterio-de-ganador.md). Los umbrales llegan por parámetro; aquí no hay ninguno.
# ----------------------------------------------------------------------------------------------
def nivel_de_ganador(m: Mapping[str, Any], par: Mapping[str, Any]) -> dict[str, Any]:
    """``SIN_SENAL < VENDIO < RENTABLE < CAMPEON``; ``VALIDADA`` lo declara el veredicto de D8 (código), no se recalcula aquí."""
    compras = _entero(m["compras_netas"], "metricas.compras_netas")
    cpa = _entero(m["cpa_neto_minor"], "metricas.cpa_neto_minor") if m.get("cpa_neto_minor") is not None else None
    be = _entero(m["cpa_be_minor"], "metricas.cpa_be_minor")
    obj = _entero(m["cpa_obj_minor"], "metricas.cpa_obj_minor")
    p = _dec(m["p_cpa_menor_equilibrio"], "metricas.p_cpa_menor_equilibrio") if m.get("p_cpa_menor_equilibrio") is not None else None
    cumple: list[str] = []
    no_cumple: list[str] = []
    nivel = "SIN_SENAL"
    if compras >= 1:
        nivel = "VENDIO"
        cumple.append("compras_netas >= 1")
    else:
        no_cumple.append("compras_netas >= 1")
    if cpa is not None and compras >= 1 and cpa <= obj:
        nivel = "RENTABLE"
        cumple.append("cpa_neto <= cpa_obj")
    else:
        no_cumple.append("cpa_neto <= cpa_obj")
    min_compras = _entero(par["escalado.campeon_compras_min"], "escalado.campeon_compras_min")
    factor_be = _dec(par["escalado.campeon_cpa_max_x_be"], "escalado.campeon_cpa_max_x_be")
    p_min = _dec(par["testeo.p_escala"], "testeo.p_escala")
    c1 = compras >= min_compras
    c2 = cpa is not None and Decimal(cpa) <= factor_be * Decimal(be)
    c3 = p is not None and p >= p_min
    (cumple if c1 else no_cumple).append(f"compras_netas >= escalado.campeon_compras_min ({min_compras})")
    (cumple if c2 else no_cumple).append("cpa_neto <= escalado.campeon_cpa_max_x_be * cpa_be")
    (cumple if c3 else no_cumple).append("P(CPA <= equilibrio) >= testeo.p_escala")
    if c1 and c2 and c3:
        nivel = "CAMPEON"
    if m.get("veredicto_d8") == "VALIDADA":
        nivel = "VALIDADA"
        cumple.append("veredicto_oferta.estado = VALIDADA (D8, código)")
    return {"nivel": nivel, "cumple": cumple, "no_cumple": no_cumple}


def senales_de_suba(m: Mapping[str, Any], par: Mapping[str, Any]) -> dict[str, Any]:
    """Dos señales (retorno y tendencia de 3 días) más compras mínimas, presupuesto previo gastado y datos maduros."""
    obj = Decimal(_entero(m["cpa_obj_minor"], "metricas.cpa_obj_minor"))
    umbral_7d = _dec(par["escalado.cpa_subir_factor"], "escalado.cpa_subir_factor") * obj
    umbral_3d = _dec(par["escalado.cpa_3d_factor"], "escalado.cpa_3d_factor") * umbral_7d
    cpa7 = _entero(m["cpa_7d_minor"], "metricas.cpa_7d_minor")
    cpa3 = _entero(m["cpa_3d_minor"], "metricas.cpa_3d_minor")
    retorno = Decimal(cpa7) <= umbral_7d
    tendencia = Decimal(cpa3) <= umbral_3d
    compras7 = _entero(m["compras_7d"], "metricas.compras_7d")
    return {
        "retorno_7d": retorno, "tendencia_3d": tendencia,
        "umbral_cpa_7d_minor": str(umbral_7d.quantize(Decimal("0.01"))), "umbral_cpa_3d_minor": str(umbral_3d.quantize(Decimal("0.01"))),
        "compras_ventana_ok": compras7 >= _entero(par["escalado.compras_min_ventana"], "escalado.compras_min_ventana"),
        "presupuesto_previo_gastado_ok": _entero(m["presupuesto_previo_gastado_pct"], "metricas.presupuesto_previo_gastado_pct")
        >= _entero(par["escalado.suba_presupuesto_gastado_min_pct"], "escalado.suba_presupuesto_gastado_min_pct"),
        "datos_maduros": m.get("datos_maduros") is True,
    }


def hay_deterioro(m: Mapping[str, Any], par: Mapping[str, Any]) -> bool:
    """Reducción (-reduccion_pct): CPA de 72 h >= revertir_cpa_factor x cpa_obj con gasto >= k_corte x cpa_be (no es ruido)."""
    cpa72 = Decimal(_entero(m["cpa_72h_minor"], "metricas.cpa_72h_minor"))
    obj = Decimal(_entero(m["cpa_obj_minor"], "metricas.cpa_obj_minor"))
    be = Decimal(_entero(m["cpa_be_minor"], "metricas.cpa_be_minor"))
    gasto72 = Decimal(_entero(m["gasto_72h_minor"], "metricas.gasto_72h_minor"))
    return cpa72 >= _dec(par["escalado.revertir_cpa_factor"], "escalado.revertir_cpa_factor") * obj and gasto72 >= _dec(par["testeo.k_corte"], "testeo.k_corte") * be


# ----------------------------------------------------------------------------------------------
# Techos (frenos de empresa) y paso
# ----------------------------------------------------------------------------------------------
def techos(lim: Limites, activas: list[CampanaActiva], oferta_id: str, excluir_campaign: str | None) -> dict[str, Any]:
    """Presupuesto diario máximo que cabe hoy: (techo - Σ máx. teórico de las demás) / factor, hacia abajo."""
    factor = _dec(lim.valor("factor_techo_teorico_diario"), "factor_techo_teorico_diario")
    otras = [c for c in activas if c.campaign_id != excluir_campaign]
    suma_global = sum(c.max_teorico_diario_minor for c in otras)
    suma_oferta = sum(c.max_teorico_diario_minor for c in otras if c.oferta_id == oferta_id)
    tope_global = _entero(lim.valor("gasto_diario_global"), "gasto_diario_global")
    tope_oferta = _entero(lim.valor("gasto_diario_por_oferta"), "gasto_diario_por_oferta")
    max_global = max(0, _piso(Decimal(tope_global - suma_global) / factor))
    max_oferta = max(0, _piso(Decimal(tope_oferta - suma_oferta) / factor))
    return {
        "factor": str(factor), "gasto_diario_global_minor": tope_global, "gasto_diario_por_oferta_minor": tope_oferta,
        "suma_otras_max_teorico_minor": suma_global, "suma_otras_de_la_oferta_max_teorico_minor": suma_oferta,
        "max_presupuesto_por_global_minor": max_global, "max_presupuesto_por_oferta_minor": max_oferta,
        "max_presupuesto_permitido_minor": min(max_global, max_oferta),
        "limita": "gasto_diario_global" if max_global <= max_oferta else "gasto_diario_por_oferta",
    }


_CODIGO_POR_CLAVE = {
    "gasto_diario_global": "LIMITE_DIARIO_EMPRESA", "gasto_diario_por_oferta": "TECHO_OFERTA",
    "perdida_neta_acumulada_max": "PERDIDA_ACUMULADA_EMPRESA", "limite_gasto_cuenta_meta": "LIMITE_CUENTA_META",
    "ofertas_en_test_simultaneas_max": "OFERTAS_SIMULTANEAS",
}


def _gate_efectivo(nivel: str) -> dict[str, str]:
    return {"accion_gate": "accion:subir_presupuesto_d9", "nivel": nivel, "gate": _gate_de(nivel)}


# ----------------------------------------------------------------------------------------------
# dictamen
# ----------------------------------------------------------------------------------------------
def dictamen(e: dict[str, Any], lim_doc: dict[str, Any], par: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """Devuelve ``(resultado, código_de_salida)``. Nunca escribe nada."""
    oferta_id = str(e.get("oferta_id", ""))
    if not RX_OFERTA.fullmatch(oferta_id):
        raise ErrorValidacion(f"oferta_id inválido: {oferta_id!r}")
    ahora = comun.parsear_z(str(e.get("ahora", "")))
    nivel_d9 = str(e.get("nivel_autonomia_d9", ""))
    if nivel_d9 not in NIVELES:
        raise ErrorValidacion(f"nivel_autonomia_d9 inválido: {nivel_d9!r}")
    objeto = e.get("objeto") or {}
    rol = objeto.get("rol")
    if rol not in ROLES:
        raise ErrorValidacion("objeto.rol debe ser «test» (se gradúa a una ESCALA nueva) o «escala» (se sube o reduce la ESCALA)")
    # 1. PAUSA manda sobre todo.
    if e.get("pausa") is True:
        return _resultado("BLOQUEADO", "PAUSA_ACTIVA", motivos=["empresa/PAUSA existe: no se propone nada"]), 4
    # 2. Límites completos y coherentes (fail-closed: null = nada escala).
    faltan = _faltantes_limites(lim_doc)
    if faltan:
        return _resultado("BLOQUEADO", "LIMITES_INCOMPLETOS", faltantes=faltan,
                          motivos=["clave en null o vacía en limites.yaml: nada escala (código 5)"]), 5
    incoherencias = V.coherencia_limites(dict(lim_doc))
    if incoherencias:
        return _resultado("BLOQUEADO", "LIMITES_INCOHERENTES", motivos=incoherencias), 5
    if e.get("exigir_sello") is True:
        ev = V.evaluar_limites(dict(lim_doc), "escalar")
        if not ev.ok:
            return _resultado("BLOQUEADO", "LIMITES_SIN_SELLO_VALIDO", faltantes=ev.faltantes, motivos=[ev.motivo]), 5
    faltan_par = [k for k in PARAMETROS_ESCALA if _vacio(par.get(k))]
    if faltan_par:
        return _resultado("BLOQUEADO", "PARAMETRO_FALTANTE", faltantes=faltan_par,
                          motivos=["parámetro ausente o null: no se inventa un valor (PEDIDOS.md P-02)"]), 5
    lim = Limites(datos=lim_doc)
    moneda = lim.moneda
    if e.get("moneda") != moneda:
        raise ErrorValidacion(f"moneda de la entrada {e.get('moneda')!r} distinta de moneda_limites {moneda!r}")
    cuenta = e.get("cuenta") or {}
    activas = [CampanaActiva.desde(c) for c in cuenta.get("activas", [])]
    m = e["metricas"]
    # En una graduación la campaña de TEST sigue viva (el ganador sigue en testeo): no se excluye de la suma. La ESCALA nueva aún no existe.
    campaign_id = objeto.get("campaign_id") if rol == "escala" else None
    actual = _entero(e["presupuesto_actual_minor"], "presupuesto_actual_minor")
    ganador = nivel_de_ganador(m, par)
    senales = senales_de_suba(m, par)
    tec = techos(lim, activas, oferta_id, campaign_id)
    base = {"ganador": ganador, "senales": senales, "techo": tec, "gate_efectivo": _gate_efectivo(nivel_d9)}

    # 3. Deterioro de una ESCALA: reducir (no necesita ganador ni techo de subida).
    if rol == "escala" and hay_deterioro(m, par):
        pct = _dec(par["escalado.reduccion_pct"], "escalado.reduccion_pct")
        nuevo = _piso(Decimal(actual) * (Decimal(100) - pct) / Decimal(100))
        return _con_orden(e, lim, par, base, "reducir", "REDUCCION_PROPUESTA", actual, nuevo, ahora, moneda, nivel_d9,
                          [f"CPA de 72 h >= revertir_cpa_factor x cpa_obj con gasto suficiente: reducir {_pct_texto(pct)} %"], "D9-R1"), 0

    # 3b. Elegibilidad E0: se escala solo lo que la empresa puede sostener (reducir, en cambio, nunca la exige: baja exposición).
    elig = e.get("elegibilidad") or {}
    sin_dato = [k for k in CHEQUEOS_E0 if k not in elig]
    if sin_dato:
        return _resultado("BLOQUEADO", "ELEGIBILIDAD_SIN_DATO", **base, faltantes=sin_dato,
                          motivos=["falta una bandera de elegibilidad E0: lo desconocido no se asume cumplido"]), 5
    fallan = [k for k in CHEQUEOS_E0 if k != "riesgo_nivel" and elig[k] is not True]
    if elig["riesgo_nivel"] != "verde":
        fallan.insert(0, f"riesgo_nivel={elig['riesgo_nivel']} (solo verde sube sin H; el amarillo lo decide X1/el dueño)")
    if fallan:
        return _resultado("NO_PROPONER", "ELEGIBILIDAD_NO_CUMPLIDA", **base, no_cumple_e0=fallan,
                          motivos=["no se cumple la elegibilidad E0: " + ", ".join(fallan)]), 0

    # 4. Suba / graduación: primero ¿hay ganador? ¿hay señales?
    if ganador["nivel"] not in ("CAMPEON", "VALIDADA"):
        return _resultado("NO_PROPONER", "SIN_GANADOR", **base, motivos=[f"nivel {ganador['nivel']}: no alcanza para escalar (el rentable se queda en test)"]), 0
    if not senales["datos_maduros"]:
        return _resultado("NO_PROPONER", "DATOS_INMADUROS", **base, motivos=["las lecturas no excluyen los últimos 2 días inmaduros"]), 0
    if not senales["compras_ventana_ok"]:
        return _resultado("NO_PROPONER", "COMPRAS_INSUFICIENTES", **base, motivos=["compras de la ventana < escalado.compras_min_ventana"]), 0
    if senales["retorno_7d"] != senales["tendencia_3d"]:
        return _resultado("NO_PROPONER", "SENAL_AMBIGUA", **base,
                          motivos=["retorno de 7 días y tendencia de 3 días no coinciden: una sola señal no sube presupuesto (solo 1 de cada 3 subas acierta)"]), 0
    if not senales["retorno_7d"]:
        return _resultado("NO_PROPONER", "SIN_SENAL_DE_SUBA", **base, motivos=["ni el retorno de 7 días ni la tendencia de 3 días respaldan subir"]), 0
    if not senales["presupuesto_previo_gastado_ok"]:
        return _resultado("NO_PROPONER", "PRESUPUESTO_PREVIO_NO_GASTADO", **base,
                          motivos=["Meta no gastó el presupuesto anterior: subir de nuevo sería pisar el acelerador sin evidencia"]), 0

    # 5. Techos de empresa (J4) y de oferta.
    piso_techo = actual if rol == "escala" else 0
    if tec["max_presupuesto_permitido_minor"] <= piso_techo:
        codigo = _CODIGO_POR_CLAVE[tec["limita"]]
        return _resultado("NO_PROPONER", codigo, **base, motivos=[f"no queda holgura bajo {tec['limita']}: el máximo teórico diario ya está en el tope"]), 0

    # 6. Ritmo (horas mínimas, cambios por hora, segundos entre ediciones): el mismo código del guard.
    try:
        exigir_ritmo(lim, ahora, ediciones_recientes=tuple(cuenta.get("ediciones_recientes", ())), ultimo_aumento=cuenta.get("ultimo_aumento"))
    except ErrorLimite as exc:
        return _resultado("NO_PROPONER", "ESPERAR_PASO_PREVIO", **base, motivos=[exc.mensaje]), 0

    # 7. Cuánto: recortes por múltiplo habilitado, por % de paso y por techos.
    multiplo = _entero(par["escalado.escalera_multiplo_max"], "escalado.escalera_multiplo_max")
    recortes: list[str] = []
    if rol == "escala":
        deseado = _entero(e["presupuesto_deseado_minor"], "presupuesto_deseado_minor")
        if deseado > actual * multiplo:
            deseado = actual * multiplo
            recortes.append(f"recortado al múltiplo habilitado (x{multiplo})")
        meta = limites_meta_desde(lim)
        techo_oferta_restante = _entero(lim.valor("gasto_diario_por_oferta"), "gasto_diario_por_oferta") - tec["suma_otras_de_la_oferta_max_teorico_minor"]
        propuesta = proponer_aumento_presupuesto(
            actual, deseado, cuenta.get("ultimo_aumento"), e["ahora"], _entero(cuenta.get("cambios_ultima_hora", 0), "cambios_ultima_hora"),
            float(_dec(cuenta.get("segundos_desde_ultima_edicion", 86400), "segundos_desde_ultima_edicion")), techo_oferta_restante, meta)
        if not propuesta.permitido:
            return _resultado("NO_PROPONER", "ESPERAR_PASO_PREVIO" if propuesta.proximo_intento_utc else "TECHO_OFERTA", **base,
                              motivos=list(propuesta.motivos), proximo_intento_utc=propuesta.proximo_intento_utc), 0
        nuevo = propuesta.nuevo_presupuesto_minor
        recortes.extend(m_ for m_ in propuesta.motivos if m_ != "aumento permitido")
        if nuevo > tec["max_presupuesto_permitido_minor"]:
            nuevo = tec["max_presupuesto_permitido_minor"]
            recortes.append("recortado para respetar gasto_diario_global")
        if nuevo <= actual:
            return _resultado("NO_PROPONER", _CODIGO_POR_CLAVE[tec["limita"]], **base, motivos=["sin holgura tras los recortes"]), 0
        accion = "aumentar"
        codigo = "SUBA_PERMITIDA"
        antes = actual
    else:  # graduación: ESCALA nueva; su presupuesto cuenta como un PASO sobre el agregado de la oferta
        if _entero(e.get("campanas_escala_existentes", 0), "campanas_escala_existentes") >= _entero(par["escalado.max_campanas_escala"], "escalado.max_campanas_escala"):
            return _resultado("NO_PROPONER", "MAX_CAMPANAS_ESCALA", **base, motivos=["ya hay el máximo de campañas de escala de la oferta"]), 0
        agregado = _entero(e.get("presupuesto_agregado_oferta_minor", actual), "presupuesto_agregado_oferta_minor")
        tope_paso = _piso(Decimal(agregado) * Decimal(str(limites_meta_desde(lim).paso_max_pct)))
        topes = {"paso": tope_paso, "multiplo": agregado * max(0, multiplo - 1), "techo": tec["max_presupuesto_permitido_minor"]}
        deseado = _entero(e.get("presupuesto_inicial_deseado_minor", topes["paso"]), "presupuesto_inicial_deseado_minor")
        nuevo = min(deseado, *topes.values())
        if deseado > nuevo:
            ligados = [k for k, v in topes.items() if v == nuevo]
            recortes.append("recortado al límite más estricto: " + ", ".join({"paso": "% de paso", "multiplo": f"múltiplo x{multiplo}", "techo": tec["limita"]}[k] for k in ligados))
        if nuevo <= 0:
            return _resultado("NO_PROPONER", "TECHO_OFERTA", **base, motivos=["el paso permitido no deja presupuesto para una ESCALA nueva"]), 0
        accion = "graduar"
        codigo = "GRADUACION_PERMITIDA"
        antes = 0

    # 8. Verificación final con el MISMO código del guard (agregados J4 incluidos).
    spend_cap = e.get("spend_cap_restante_minor")
    if spend_cap is None:
        return _resultado("BLOQUEADO", "FALTA_SPEND_CAP", **base, faltantes=["spend_cap_restante_minor"],
                          motivos=["el spend_cap de la campaña lo define D7/payloads, no la IA"]), 5
    nueva = CampanaActiva(oferta_id=oferta_id, campaign_id=str(campaign_id or "ESCALA-NUEVA"), max_teorico_diario_minor=max_teorico_diario(lim, nuevo),
                          spend_cap_restante_minor=_entero(spend_cap, "spend_cap_restante_minor"), moneda=moneda,
                          perdida_acumulada_minor=_entero(e.get("perdida_acumulada_oferta_minor", 0), "perdida_acumulada_oferta_minor"))
    try:
        exigir_agregados_del_efecto(lim, activas, nueva, gasto_vitalicio_minor=cuenta.get("gasto_vitalicio_minor"))
    except ErrorLimite as exc:
        clave = exc.detalle.get("clave")
        if clave is None:
            return _resultado("BLOQUEADO", "DATO_DE_CUENTA_FALTANTE", **base, faltantes=list(exc.detalle.get("faltantes", [])), motivos=[exc.mensaje]), 5
        return _resultado("NO_PROPONER", _CODIGO_POR_CLAVE.get(str(clave), "LIMITE_EMPRESA"), **base, motivos=[exc.mensaje]), 0
    motivos = recortes or ["dentro del paso, del múltiplo habilitado y de los techos"]
    return _con_orden(e, lim, par, base, accion, codigo, antes, nuevo, ahora, moneda, nivel_d9, motivos, "D9-E1"), 0


def _con_orden(e: dict[str, Any], lim: Limites, par: Mapping[str, Any], base: dict[str, Any], accion: str, codigo: str, antes: int,
               despues: int, ahora: datetime, moneda: str, nivel: str, motivos: list[str], regla_id: str) -> dict[str, Any]:
    """Arma la ``orden_presupuesto`` en borrador (estado «propuesta») y la valida contra su esquema."""
    objeto = e["objeto"]
    m = e["metricas"]
    cuenta = e.get("cuenta") or {}
    delta = Decimal(0)
    if antes > 0:
        delta = (Decimal(despues) - Decimal(antes)) * Decimal(100) / Decimal(antes)
    elif e.get("presupuesto_agregado_oferta_minor"):
        delta = Decimal(despues) * Decimal(100) / Decimal(int(e["presupuesto_agregado_oferta_minor"]))
    horas = None
    if cuenta.get("ultimo_aumento"):
        horas = int((ahora - comun.parsear_z(str(cuenta["ultimo_aumento"]))).total_seconds() // 3600)
    usados = {k: par[k] for k in PARAMETROS_ESCALA}
    hash_par = comun.hash_objeto({"parametros": usados, "limites": {k: lim.get(k) for k in sorted(V.CLAVES_CRITICAS["escalar"])}})
    p_texto = m.get("p_cpa_menor_equilibrio")
    orden = {
        "schema_version": "1.0.0",
        "orden_id": f"ORD-{e['oferta_id']}-{_entero(e.get('secuencia_orden', 1), 'secuencia_orden'):04d}",
        "oferta_id": e["oferta_id"], "ts": comun.iso_z(ahora), "emisor": "D9", "plan_ref": e.get("plan_ref", "09-escalado/propuesta-de-suba.json"),
        "accion": "aumentar" if accion in ("aumentar", "graduar") else "reducir",
        "objeto": ({"tipo": "campana", "nombre": str((e.get("escala_nueva") or {}).get("nombre", "")), "id_meta": None} if accion == "graduar"
                   else {"tipo": "campana", "nombre": str(objeto.get("nombre", "")), "id_meta": objeto.get("campaign_id")}),
        "antes": {"monto": antes, "moneda": moneda}, "despues": {"monto": despues, "moneda": moneda},
        "delta_pct": _pct_texto(delta), "horas_desde_ultimo_aumento": horas, "regla_id": regla_id, "version_reglas": VERSION_REGLAS,
        "hash_parametros": hash_par,
        "evidencia": {"ventana": "7d", "gasto": {"monto": _entero(m["gasto_7d_minor"], "metricas.gasto_7d_minor"), "moneda": moneda},
                      "compras_stripe": _entero(m["compras_7d"], "metricas.compras_7d"), "p": None if p_texto is None else str(p_texto),
                      "nota": "; ".join(motivos)[:400] + (". El delta de una graduación se mide sobre el agregado de la oferta." if accion == "graduar" else "")},
        "gate": _gate_efectivo(nivel), "aprobado_por": None, "estado": "propuesta", "ejecutor": "humano" if _gate_de(nivel) == "H" else "script",
        "idempotency_key": comun.hash_objeto({"oferta_id": e["oferta_id"], "accion": accion, "objeto": ((e.get("escala_nueva") or {}).get("nombre") if accion == "graduar" else objeto.get("nombre")), "antes": antes, "despues": despues, "ts": comun.iso_z(ahora)}),
        "verificacion_post": None,
    }
    errores = comun.errores_de_esquema("orden_presupuesto", orden)
    if errores:
        raise ErrorValidacion(f"la orden en borrador no cumple orden_presupuesto.schema.json: {comun.resumir_errores_esquema(errores)}")
    return _resultado("PROPONER", codigo, **base, accion=accion, paso={"actual_minor": antes, "nuevo_minor": despues, "delta_pct": orden["delta_pct"], "recortes": [x for x in motivos]},
                      orden_borrador=orden, motivos=motivos)


# ----------------------------------------------------------------------------------------------
# replica: puerta para crear una oferta hija (J5)
# ----------------------------------------------------------------------------------------------
def puerta_replica(e: dict[str, Any], lim_doc: dict[str, Any], par: dict[str, Any]) -> tuple[dict[str, Any], int]:
    """¿Puede crearse la hija? Madre validada antes (J5), locale permitido, cadencia, tablero completo y tope de ganadores."""
    if e.get("pausa") is True:
        return _resultado("BLOQUEADO", "PAUSA_ACTIVA", motivos=["empresa/PAUSA existe"]), 4
    faltan_par = [k for k in PARAMETROS_REPLICA if par.get(k) is None]
    if faltan_par:
        return _resultado("BLOQUEADO", "PARAMETRO_FALTANTE", faltantes=faltan_par, motivos=["grupo mercados incompleto (PEDIDOS.md P-03)"]), 5
    locales = lim_doc.get("locales_permitidos")
    paises = lim_doc.get("paises_permitidos")
    if _vacio(locales) or _vacio(paises):
        return _resultado("BLOQUEADO", "LIMITES_INCOMPLETOS", faltantes=[k for k, v in (("locales_permitidos", locales), ("paises_permitidos", paises)) if _vacio(v)],
                          motivos=["listas vacías: ningún idioma puede lanzarse"]), 5
    madre, hija = e.get("madre") or {}, e.get("hija") or {}
    ahora = comun.parsear_z(str(e.get("ahora", "")))
    motivos: list[str] = []
    if par["mercados.hija_requiere_madre_validada"] is True and madre.get("estado_veredicto") != "VALIDADA":
        motivos.append("MADRE_NO_VALIDADA: la madre debe estar VALIDADA antes de crear hijas (J5)")
    if hija.get("locale") not in locales:
        motivos.append(f"LOCALE_NO_PERMITIDO: {hija.get('locale')!r} no está en limites.locales_permitidos (lo firma el dueño)")
    if not set(hija.get("paises", [])) <= set(paises):
        motivos.append("PAIS_NO_PERMITIDO: algún país de la hija no está en limites.paises_permitidos")
    if hija.get("variante_de") != madre.get("oferta_id"):
        motivos.append("VARIANTE_DE_INCORRECTA: la hija debe declarar variante_de = oferta_id de la madre y el mismo familia_id")
    if hija.get("familia_id") != madre.get("familia_id"):
        motivos.append("FAMILIA_DISTINTA: la hija comparte el familia_id de la madre")
    if hija.get("locale") == madre.get("locale"):
        motivos.append("MISMO_LOCALE: una hija es otro idioma o clúster, no una copia")
    ventana = _entero(par["mercados.ventana_dias"], "mercados.ventana_dias")
    recientes = [comun.parsear_z(str(t)) for t in e.get("aperturas_recientes", [])]
    en_ventana = [t for t in recientes if (ahora - t).total_seconds() < ventana * 86400]
    if len(en_ventana) >= _entero(par["mercados.aperturas_max_por_ventana"], "mercados.aperturas_max_por_ventana"):
        motivos.append("CADENCIA: ya se abrió el máximo de idiomas en la ventana")
    if len(e.get("ganadores_a_transferir", [])) > _entero(par["mercados.ganadores_transferidos_max"], "mercados.ganadores_transferidos_max"):
        motivos.append("GANADORES_EXCEDEN_TOPE: se transfieren más ganadores que mercados.ganadores_transferidos_max")
    tablero = e.get("tablero") or {}
    if tablero.get("origen") != "codigo":
        motivos.append("TABLERO_NO_CALCULADO: el tablero de lanzamiento de idioma lo calcula el código; una tarjeta marcada a mano no vale")
    if tablero.get("estado") != "completo":
        motivos.append("TABLERO_INCOMPLETO: todas las tarjetas deben estar en LISTO PARA LANZAR antes de prender nada en ese idioma")
    if motivos:
        return _resultado("NO_PROPONER", "REPLICA_NO_PERMITIDA", motivos=motivos), 0
    return _resultado("PROPONER", "REPLICA_PERMITIDA", motivos=["madre validada, locale permitido, cadencia y tablero en regla"],
                      gate_efectivo={"accion_gate": "accion:lanzamiento_pais_idioma_nuevo", "nota": "H hoy (limites.acciones_gate_humano); lo firma el dueño"}), 0


# ----------------------------------------------------------------------------------------------
# validar: la propuesta que escribió el Maker es una propuesta (no una orden) y coincide con el dictamen
# ----------------------------------------------------------------------------------------------
def validar_propuesta(doc: Any) -> tuple[dict[str, Any], int]:
    """Comprueba ``propuesta-de-suba.json``: su ``orden_presupuesto`` valida contra el esquema, es ``propuesta`` sin firma y sus cifras
    son las del dictamen del código. Devuelve ``(resultado, salida)``: 0 sin defectos, 4 con defectos."""
    defectos: list[str] = []
    if not isinstance(doc, dict):
        raise ErrorValidacion("la propuesta debe ser un objeto JSON")
    flotantes = V.buscar_floats(doc)
    if flotantes:
        defectos.append(f"float prohibido: {flotantes[:5]}")
    orden = doc.get("orden_presupuesto")
    if not isinstance(orden, dict):
        defectos.append("falta el bloque orden_presupuesto")
        orden = {}
    else:
        errores = comun.errores_de_esquema("orden_presupuesto", orden)
        if errores:
            defectos.append("orden_presupuesto no valida: " + comun.resumir_errores_esquema(errores))
    if doc.get("estado") != "propuesta" or orden.get("estado") != "propuesta":
        defectos.append("la propuesta y su orden deben estar en estado «propuesta» (el Maker nunca aprueba ni ejecuta)")
    if orden.get("aprobado_por") is not None:
        defectos.append("aprobado_por debe ser null: la firma no es del Maker")
    if orden.get("emisor") != "D9":
        defectos.append("emisor debe ser D9")
    dictamen_c = doc.get("dictamen_codigo") or {}
    if dictamen_c.get("estado") != "PROPONER":
        defectos.append(f"el dictamen del código dice {dictamen_c.get('estado')!r}: solo con PROPONER existe una propuesta de suba")
    paso = dictamen_c.get("paso") or {}
    if orden:
        if (orden.get("antes") or {}).get("monto") != paso.get("actual_minor"):
            defectos.append("orden.antes no coincide con dictamen_codigo.paso.actual_minor")
        if (orden.get("despues") or {}).get("monto") != paso.get("nuevo_minor"):
            defectos.append("orden.despues no coincide con dictamen_codigo.paso.nuevo_minor")
        if orden.get("delta_pct") != paso.get("delta_pct"):
            defectos.append("orden.delta_pct no coincide con dictamen_codigo.paso.delta_pct")
    resultado = {"version_script": VERSION_SCRIPT, "ok": not defectos, "defectos": defectos}
    return resultado, (4 if defectos else 0)


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="escala_lectura.py", description="Apoyo determinista y de solo lectura de D9 (escalado).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nombre in ("dictamen", "replica"):
        p = sub.add_parser(nombre)
        p.add_argument("--entrada", required=True)
        p.add_argument("--limites", help="empresa/limites.yaml (sustituye al bloque «limites» de la entrada)")
        p.add_argument("--parametros", help="empresa/parametros.yaml (sustituye al bloque «parametros» de la entrada)")
        p.add_argument("--raiz", help="raíz donde buscar empresa/PAUSA (por defecto la del repositorio)")
    pv = sub.add_parser("validar")
    pv.add_argument("--archivo", required=True, help="propuesta-de-suba.json")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if args.cmd == "validar":
        try:
            resultado, codigo = validar_propuesta(_leer(args.archivo))
        except ErrorFabrica as exc:
            print(json.dumps({"ok": False, "error": exc.mensaje}, ensure_ascii=False))
            return exc.codigo_salida
        print(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2))
        return codigo
    try:
        entrada, lim, par = _preparar(_leer(args.entrada), args)
        if (Path(args.raiz) if args.raiz else RAIZ).joinpath("empresa", "PAUSA").exists():
            entrada["pausa"] = True  # la presencia del archivo manda sobre lo que diga la entrada
        resultado, codigo = (dictamen if args.cmd == "dictamen" else puerta_replica)(entrada, lim, par)
    except ErrorFabrica as exc:
        print(json.dumps({"ok": False, "error": exc.mensaje, "detalle": exc.detalle}, ensure_ascii=False, sort_keys=True, indent=2))
        return exc.codigo_salida
    except (KeyError, TypeError, ValueError) as exc:
        print(json.dumps({"ok": False, "error": f"entrada incompleta o con forma inesperada: {exc!r}"}, ensure_ascii=False))
        return 3
    print(json.dumps(resultado, ensure_ascii=False, sort_keys=True, indent=2))
    return codigo


if __name__ == "__main__":
    sys.exit(main())
