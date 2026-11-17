"""Veredicto CALCULADO de D2 (``validacion.json#veredicto.calculado``): determinista, sin LLM, sin red.

Promueve a ``scripts/`` la lógica de ``.claude/skills/d2-validacion/scripts/{veredicto,metricas}.py``
(departamentos/03-validacion.md §3.4), adaptada para que la salida cumpla ``contratos/validacion.schema.json``
y para que NINGÚN umbral viva en el código: todos salen de ``empresa/parametros.yaml`` (grupo ``validacion``),
nunca de un literal. A diferencia de la skill, este módulo NO recalcula ``SS_a``/``IS`` desde datos crudos de
anunciantes (esas fórmulas usan pesos que hoy NO están en ``contratos/parametros.schema.json``: la skill los
toma de su propia propuesta no aprobada, ``.claude/skills/d2-validacion/references/parametros_d2.propuesta.yaml``,
fuera del esquema). Este módulo recibe esos agregados YA calculados (``saturacion.indice``,
``saturacion.n_ind_sostenidos``, ``saturacion.saturacion_mecanismo``, ``convergencia.estado``) y decide el
veredicto con los 5 umbrales de decisión que SÍ son oficiales: ``n_ind_sost_go``, ``is_go_max``, ``is_nogo_min``,
``min_frases_voz``, ``min_fuentes_voz`` (decisión registrada en el README del componente).

Entrada (``ENTRADA.json``, formato propio de este script, NO es ``validacion.json``): los campos que pasan
TAL CUAL al artefacto final (``schema_version, oferta_id, version, origen_version, version_script, candidato_id,
macro_nicho, consultas, metricas_mercado, saturacion, convergencia, huecos, senales_demanda_organica,
restricciones_originalidad, riesgo_politica, no_inferible, hipotesis_para_d7, handoff_d3``) más los insumos de
decisión que el esquema de salida NO almacena (``lectura_snapshots, voz, evidencia_locale_e1_o_e2,
sustituto_gratis, angulo_seguro_existe, reencuadre_verificable_x1, x1_dictamen, confianza, n_competidores,
riesgo_subnivel``). Ver ``scripts/validacion/README.md`` para el detalle completo y un ejemplo.

Subcomandos (devuelven 0 ok · 2 uso · 3 entrada o incoherencia · 5 falta un parámetro)::

    .venv/bin/python -m scripts.validacion.veredicto_d2 calcular ENTRADA.json [--parametros P.yaml] [--salida OUT.json]
    .venv/bin/python -m scripts.validacion.veredicto_d2 comprobar ENTRADA.json VALIDACION.json [--parametros P.yaml]

Sin red, sin credenciales. El Maker puede PROPONER (``veredicto.propuesto``) pero solo puede DEGRADAR el
calculado (GO > GO_CONDICIONAL > NO_GO), nunca mejorarlo; mejorarlo exige ``origen_version = humano`` (S11).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion, ParametroFaltante
from engine.parametros import Parametros, cargar_parametros

__all__ = ["calcular_validacion", "decidir", "comprobar", "main"]

VERSION_SCRIPT = "1.0.0"
RANGO_VEREDICTO = {"NO_GO": 0, "GO_CONDICIONAL": 1, "GO": 2}
LECTURAS = ("humano_muestreo", "navegador_auto", "ninguno", "pendiente_humano")
SUSTITUTOS = ("no_dominante", "diferenciado", "dominante", "no_medido")
CONFIANZA_NIVELES = ("baja", "media", "alta")
X1_DICTAMENES = ("PASS", "PASS_CON_NOTAS", "FAIL", "no_aplica")
NIVELES_RIESGO = ("verde", "amarillo", "rojo")

# Campos que pasan sin cambios de ENTRADA a validacion.json (el resto de las claves del esquema).
_CAMPOS_PASE = (
    "schema_version", "oferta_id", "version", "origen_version", "version_script", "candidato_id", "macro_nicho",
    "consultas", "metricas_mercado", "saturacion", "convergencia", "huecos", "senales_demanda_organica",
    "restricciones_originalidad", "riesgo_politica", "no_inferible", "hipotesis_para_d7", "handoff_d3",
)
# Parámetros de empresa/parametros.yaml#grupos.validacion que usa la decisión (nunca literales en el código).
_PARAMETROS_DECISION = ("n_ind_sost_go", "is_go_max", "is_nogo_min", "min_frases_voz", "min_fuentes_voz")


def _valor_parametro(parametros: Any, clave: str) -> Any:
    """Valor de ``validacion.<clave>`` de un ``Parametros`` o de un mapa ``{grupos: {...}}`` ya cargado.

    Falla cerrado (``ParametroFaltante``, código 5) si el parámetro no existe o está en ``null``: ningún
    umbral se asume. Acepta un mapa plano (en vez de ``Parametros``) para que las pruebas puedan fijar solo
    los parámetros que necesitan, sin construir un ``empresa/parametros.yaml`` completo.
    """
    if isinstance(parametros, Parametros):
        return parametros.valor(f"validacion.{clave}")
    if not isinstance(parametros, Mapping):
        raise ParametroFaltante(f"validacion.{clave}", "no se proporcionó ningún parámetro")
    try:
        entrada = parametros["grupos"]["validacion"][clave]
        valor = entrada["valor"] if isinstance(entrada, Mapping) else entrada
    except (KeyError, TypeError) as exc:
        raise ParametroFaltante(f"validacion.{clave}", "no existe en parametros.yaml") from exc
    if valor is None:
        raise ParametroFaltante(f"validacion.{clave}", "sin valor (null): pendiente de calibrar por el dueño")
    return valor


def _cargar_umbrales(parametros: Any) -> dict[str, int]:
    return {clave: int(_valor_parametro(parametros, clave)) for clave in _PARAMETROS_DECISION}


# ----------------------------------------------------------------------------------------------
# Validación de la entrada (falla cerrado ante cualquier dato fuera de forma; código 3)
# ----------------------------------------------------------------------------------------------
def _validar_entrada(e: Mapping[str, Any]) -> None:
    err: list[str] = []

    def req(cond: bool, msg: str) -> None:
        if not cond:
            err.append(msg)

    req(isinstance(e, Mapping), "la entrada debe ser un objeto")
    if not isinstance(e, Mapping):
        raise ErrorValidacion("entrada inválida: " + "; ".join(err))
    for clave in (*_CAMPOS_PASE, "lectura_snapshots", "voz", "evidencia_locale_e1_o_e2", "sustituto_gratis",
                  "angulo_seguro_existe", "reencuadre_verificable_x1", "x1_dictamen", "confianza", "n_competidores"):
        req(clave in e, f"falta «{clave}»")
    if err:
        raise ErrorValidacion("entrada inválida: " + "; ".join(err))
    req(e["lectura_snapshots"] in LECTURAS, f"lectura_snapshots ∈ {LECTURAS}")
    voz = e["voz"]
    req(isinstance(voz, Mapping) and isinstance(voz.get("frases_total"), int) and not isinstance(voz.get("frases_total"), bool)
        and voz["frases_total"] >= 0, "voz.frases_total: entero >= 0")
    req(isinstance(voz, Mapping) and isinstance(voz.get("fuentes_distintas"), int) and not isinstance(voz.get("fuentes_distintas"), bool)
        and voz.get("fuentes_distintas", -1) >= 0, "voz.fuentes_distintas: entero >= 0")
    req(isinstance(e["evidencia_locale_e1_o_e2"], int) and not isinstance(e["evidencia_locale_e1_o_e2"], bool)
        and e["evidencia_locale_e1_o_e2"] >= 0, "evidencia_locale_e1_o_e2: entero >= 0")
    req(e["sustituto_gratis"] in SUSTITUTOS, f"sustituto_gratis ∈ {SUSTITUTOS}")
    req(isinstance(e["angulo_seguro_existe"], bool), "angulo_seguro_existe: booleano")
    req(isinstance(e["reencuadre_verificable_x1"], bool), "reencuadre_verificable_x1: booleano")
    req(e["x1_dictamen"] in X1_DICTAMENES, f"x1_dictamen ∈ {X1_DICTAMENES}")
    conf = e["confianza"]
    req(isinstance(conf, Mapping) and isinstance(conf.get("puntos"), int) and not isinstance(conf.get("puntos"), bool)
        and 0 <= conf.get("puntos", -1) <= 100, "confianza.puntos: entero 0..100")
    req(isinstance(conf, Mapping) and conf.get("nivel") in CONFIANZA_NIVELES, f"confianza.nivel ∈ {CONFIANZA_NIVELES}")
    req(isinstance(e["n_competidores"], int) and not isinstance(e["n_competidores"], bool) and e["n_competidores"] >= 0,
        "n_competidores: entero >= 0")
    subnivel = e.get("riesgo_subnivel")
    req(subnivel in (None, "A", "B"), "riesgo_subnivel ∈ {null, 'A', 'B'}")
    sat = e.get("saturacion")
    req(isinstance(sat, Mapping) and isinstance(sat.get("indice"), int) and not isinstance(sat.get("indice"), bool)
        and 0 <= sat.get("indice", -1) <= 100, "saturacion.indice: entero 0..100")
    req(isinstance(sat, Mapping) and isinstance(sat.get("n_ind_sostenidos"), int) and not isinstance(sat.get("n_ind_sostenidos"), bool)
        and sat.get("n_ind_sostenidos", -1) >= 0, "saturacion.n_ind_sostenidos: entero >= 0")
    req(isinstance(sat, Mapping) and sat.get("saturacion_mecanismo") in ("baja", "media", "alta"),
        "saturacion.saturacion_mecanismo ∈ {baja, media, alta}")
    conv = e.get("convergencia")
    req(isinstance(conv, Mapping) and conv.get("estado") in ("alta", "media", "baja"), "convergencia.estado ∈ {alta, media, baja}")
    huecos = e.get("huecos")
    req(isinstance(huecos, list), "huecos: lista")
    riesgo = e.get("riesgo_politica")
    req(isinstance(riesgo, Mapping) and riesgo.get("nivel") in NIVELES_RIESGO, f"riesgo_politica.nivel ∈ {NIVELES_RIESGO}")
    if err:
        raise ErrorValidacion("entrada inválida: " + "; ".join(err))


def _riesgo_apto_go(riesgo: Mapping[str, Any], subnivel: str | None) -> bool:
    """¿El riesgo de políticas permite GO? Verde siempre; amarillo solo si el subnivel es ``A`` (nota 25 §2.3).

    Sin ``riesgo_subnivel`` (no está en ``contratos/candidatos.schema.json#/$defs/riesgo``, solo en el cálculo
    de ``scripts/nivel_riesgo.py``) un amarillo se trata como NO apto para GO: falla cerrado ante el dato
    faltante en vez de asumir el subnivel más favorable (decisión registrada en el README).
    """
    nivel = riesgo["nivel"]
    if nivel == "verde":
        return True
    if nivel == "amarillo":
        return subnivel == "A"
    return False


def decidir(e: Mapping[str, Any], umbrales: Mapping[str, int]) -> dict[str, Any]:
    """Bloque ``veredicto`` (sin ``propuesto``/``final``) a partir de la ``ENTRADA`` y los umbrales oficiales.

    Reglas de departamentos/03-validacion.md §3.4, acotadas a los parámetros que hoy existen en
    ``contratos/parametros.schema.json#grupos.validacion`` (ver README «Decisiones» para lo que queda fuera:
    pesos de ``SS_a``/``IS``, saturación de mecanismo por ``share``, puntos de confianza por criterio y el
    hueco de localización, todos sin parámetro oficial).
    """
    sat, conv, voz, conf = e["saturacion"], e["convergencia"], e["voz"], e["confianza"]
    riesgo_apto = _riesgo_apto_go(e["riesgo_politica"], e.get("riesgo_subnivel"))
    hueco_sustentado = bool(e["huecos"])
    voz_minima = voz["frases_total"] >= umbrales["min_frases_voz"] and voz["fuentes_distintas"] >= umbrales["min_fuentes_voz"]
    confianza_ok = conf["nivel"] in ("media", "alta")
    cond_go = {
        "lectura_snapshots_distinta_de_ninguno": e["lectura_snapshots"] != "ninguno",
        "n_ind_sost_minimo": sat["n_ind_sostenidos"] >= umbrales["n_ind_sost_go"],
        "frases_y_fuentes_minimas": voz_minima,
        "evidencia_e1_o_e2_en_locale": e["evidencia_locale_e1_o_e2"] >= 1,
        "hueco_sustentado": hueco_sustentado,
        "is_no_supera_maximo": sat["indice"] <= umbrales["is_go_max"],
        "convergencia_no_alta": conv["estado"] != "alta",
        "saturacion_mecanismo_no_alta": sat["saturacion_mecanismo"] != "alta",
        "sustituto_gratis_no_dominante": e["sustituto_gratis"] in ("no_dominante", "diferenciado"),
        "riesgo_verde_o_amarillo_a": riesgo_apto,
        "x1_no_veta": e["x1_dictamen"] != "FAIL",
        "confianza_media_o_mas": confianza_ok,
        "al_menos_un_competidor": e["n_competidores"] >= 1,
    }
    cond_nogo = {
        "is_muy_alto_sin_hueco": sat["indice"] >= umbrales["is_nogo_min"] and not hueco_sustentado,
        "mecanismo_saturado_sin_hueco_con_confianza": sat["saturacion_mecanismo"] == "alta" and not hueco_sustentado and confianza_ok,
        "riesgo_rojo_sin_reencuadre_verificable": e["riesgo_politica"]["nivel"] == "rojo" and not e["reencuadre_verificable_x1"],
        "ningun_angulo_seguro": not e["angulo_seguro_existe"],
        "cero_sostenidos_pocas_frases_con_confianza": (
            sat["n_ind_sostenidos"] == 0 and voz["frases_total"] < umbrales["min_frases_voz"] and confianza_ok
        ),
        "cero_competidores": e["n_competidores"] == 0,
    }
    if any(cond_nogo.values()):
        calculado = "NO_GO"
    elif all(cond_go.values()):
        calculado = "GO"
    else:
        calculado = "GO_CONDICIONAL"
    razones = [f"NO_GO:{k}" for k, v in cond_nogo.items() if v]
    if calculado != "NO_GO":
        razones += [f"falta:{k}" for k, v in cond_go.items() if not v]
    evidencia_faltante = [k for k, v in cond_go.items() if not v] if calculado != "GO" else []
    detalle = f"calculado={calculado} condiciones_go={sum(cond_go.values())}/{len(cond_go)} condiciones_nogo={sum(cond_nogo.values())}"
    return {
        "calculado": calculado,
        "propuesto": calculado,
        "final": calculado,
        "confianza": {"puntos": conf["puntos"], "detalle": f"nivel={conf['nivel']} ({detalle})"},
        "razones": razones or ["sin_hallazgos"],
        "evidencia_faltante": evidencia_faltante or ["ninguna"],
    }


def calcular_validacion(entrada: Mapping[str, Any], parametros: Any) -> dict[str, Any]:
    """``validacion.json`` completo (cumple el esquema) a partir de ``ENTRADA`` y ``empresa/parametros.yaml``.

    Errores: ``ErrorValidacion`` (3) si la entrada no tiene la forma esperada o la salida no cumple
    ``contratos/validacion.schema.json``; ``ParametroFaltante`` (5) si falta un umbral de decisión.
    """
    _validar_entrada(entrada)
    umbrales = _cargar_umbrales(parametros)
    doc = {clave: entrada[clave] for clave in _CAMPOS_PASE}
    doc["veredicto"] = decidir(entrada, umbrales)
    errores = comun.errores_de_esquema("validacion", doc)
    if errores:
        raise ErrorValidacion("validacion.json calculado no cumple el esquema: " + comun.resumir_errores_esquema(errores))
    return doc


def comprobar(entrada: Mapping[str, Any], validacion: Mapping[str, Any], parametros: Any) -> list[str]:
    """Incoherencias de un ``validacion.json`` ya escrito frente al cálculo (lista vacía = coherente).

    Verifica que ``veredicto.calculado`` coincida con el recálculo, que ``propuesto`` no lo MEJORE (el Maker
    solo puede degradar, S11) y que ``final`` no lo mejore sin ``origen_version = humano``.
    """
    doc = calcular_validacion(entrada, parametros)
    calc = doc["veredicto"]["calculado"]
    err: list[str] = []
    vv = validacion.get("veredicto") if isinstance(validacion, Mapping) else None
    if not isinstance(vv, Mapping):
        return ["validacion.json no tiene «veredicto»"]
    if vv.get("calculado") != calc:
        err.append(f"veredicto.calculado={vv.get('calculado')!r} pero el cálculo da {calc!r}")
    propuesto = vv.get("propuesto")
    if propuesto not in RANGO_VEREDICTO:
        err.append(f"veredicto.propuesto inválido: {propuesto!r}")
    elif RANGO_VEREDICTO[propuesto] > RANGO_VEREDICTO[calc]:
        err.append(f"veredicto.propuesto={propuesto!r} MEJORA el calculado {calc!r}: el Maker solo puede degradar (S11)")
    final = vv.get("final")
    if final not in RANGO_VEREDICTO:
        err.append(f"veredicto.final inválido: {final!r}")
    elif RANGO_VEREDICTO[final] > RANGO_VEREDICTO[calc] and validacion.get("origen_version") != "humano":
        err.append(f"veredicto.final={final!r} es mejor que el calculado {calc!r} sin origen_version=humano (S11)")
    return err


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def _cargar_json(ruta: str) -> Any:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ErrorUso(f"no existe {ruta}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErrorValidacion(f"{ruta} ilegible: {exc}") from exc


def _principal(argv: list[str] | None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.validacion.veredicto_d2",
                                 description="Veredicto calculado de D2 (determinista, sin LLM)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("calcular")
    pc.add_argument("entrada")
    pc.add_argument("--parametros")
    pc.add_argument("--salida")
    pv = sub.add_parser("comprobar")
    pv.add_argument("entrada")
    pv.add_argument("validacion")
    pv.add_argument("--parametros")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None):
            return 0
        raise ErrorUso("argumentos inválidos (ver --help)") from None
    parametros = cargar_parametros(a.parametros) if a.parametros else cargar_parametros()
    entrada = _cargar_json(a.entrada)
    if a.cmd == "calcular":
        doc = calcular_validacion(entrada, parametros)
        texto = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if a.salida:
            comun.escribir_atomico(Path(a.salida), texto.encode("utf-8"))
        else:
            sys.stdout.write(texto)
        return 0
    validacion = _cargar_json(a.validacion)
    errores = comprobar(entrada, validacion, parametros)
    for err in errores:
        print(f"INCOHERENTE: {err}", file=sys.stderr)
    print("OK: validacion.json coincide con el cálculo" if not errores else f"{len(errores)} incoherencia(s)")
    return ErrorValidacion.codigo_salida if errores else 0


def main(argv: list[str] | None = None) -> int:
    return comun.ejecutar_cli(lambda: _principal(argv))


if __name__ == "__main__":
    raise SystemExit(main())
