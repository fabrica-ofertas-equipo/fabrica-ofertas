"""``compliance.salud`` — X1: salud de cuentas y regla de congelamiento (D-04).

La salud diaria es de CÓDIGO (``departamentos/14-compliance.md`` §4 paso 8). Este módulo decide
(``evaluar``) y, con ``pausa``, arma la propuesta de ``senal_pausa.json`` que ``engine.d8`` sabe leer
(``engine/d8.py::_procesar_senal_pausa``). **No pausa nada por sí mismo, no llama a Meta ni a Stripe,
no lee credenciales:** recibe un estado ya leído (``--estado``, formato ``[SUPUESTO]``: todavía no hay
``contratos/*.schema.json`` para ``salud_actual.json``, ver ``compliance/README.md``) y devuelve una
acción propuesta. **Reanudar es siempre humano** — igual que dice
``.claude/skills/x1-compliance/references/salud-de-cuentas.md`` (de solo lectura).

La regla (:func:`decidir`) es una traducción literal, a parámetros reales de
``engine.parametros``/``engine.limites`` (nunca un número de negocio en este archivo), del oráculo de
pruebas ``.claude/skills/x1-compliance/scripts/regla_salud.py`` y sus 21 series
(``evals/salud/series.json``): ``tests/compliance/test_salud.py`` compara ambas implementaciones
sobre esas 21 series.

Ningún parámetro de dinero, plazo o porcentaje vive en el código: todo sale de
``empresa/parametros.yaml`` (grupos ``compliance`` y ``salud_operativa``) y de
``empresa/limites.yaml`` (``ratio_disputas_pausa``); si falta uno, ``ParametroFaltante``/
``ErrorLimite`` (código 5) y la operación no decide nada (fail-closed, convenciones §3/§8).
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion
from engine.limites import Limites, cargar_limites
from engine.parametros import Parametros, cargar_parametros

__all__ = [
    "ACCIONES", "ParametrosSalud", "cargar_parametros_salud", "construir_senal_pausa", "decidir",
    "escribir_senal_pausa", "main", "resultado_publico", "validar_estado",
]

_SCHEMA_VERSION_SENAL_PAUSA = "1.1.0"  # x-version vigente de contratos/senal_pausa.schema.json

# Severidad creciente (la más grave manda): igual orden que el oráculo (regla_salud.ACCIONES).
ACCIONES = ("seguir", "congelar_angulo", "congelar_hoja", "pausar_oferta", "PAUSA")
_SEVERIDAD = {accion: indice for indice, accion in enumerate(ACCIONES)}

_TIPOS_RECHAZO = ("producto", "contenido", "pieza")
_TIPOS_RECHAZO_HOJA = ("producto", "contenido")
_AVISOS_STRIPE_CUENTA = ("suspension", "cierre", "monitoreo_vamp")
_AVISOS_STRIPE_OFERTA = ("retraso_pago", "reserva")
_AVISOS_STRIPE_VALIDOS = _AVISOS_STRIPE_CUENTA + _AVISOS_STRIPE_OFERTA + ("informacion",)

_CAMPOS_ESTADO_OBLIGATORIOS = ("account_status", "pagos_30d", "disputas_30d", "reembolsos_n", "reembolsos_pct", "edad_salud_h")
_DECIMALES_PCT = Decimal("0.0001")

# Claves de empresa/parametros.yaml (grupo compliance) y empresa/parametros.yaml (grupo
# salud_operativa) que la regla necesita; igual a CLAVES_PARAMS del oráculo salvo
# "disputas_ventana_dias" (solo hace falta para armar el senal_pausa, no para decidir()).
_CLAVES_COMPLIANCE = (
    "rechazos_congelar", "rechazos_ventana_dias", "estado_meta_requerido_para_lanzar",
    "salud_max_antiguedad_h", "declaracion_calidad_cuenta_max_dias",
)
_CLAVES_SALUD_OPERATIVA = (
    "disputas_alerta_pct", "disputas_casos_alerta", "disputas_casos_pausa", "disputas_muestra_min_pagos",
    "reembolsos_alerta_pct", "reembolsos_pausa_pct", "reembolsos_n_min",
)


@dataclass(frozen=True)
class ParametrosSalud:
    """Umbrales resueltos de ``parametros.yaml``/``limites.yaml`` que necesita :func:`decidir`.

    ``disputas_ventana_dias`` es opcional: solo lo usa :func:`construir_senal_pausa` (campo
    ``metricas.ventana_dias`` del contrato); si falta y se intenta construir un ``senal_pausa``, la
    validación de esquema lo rechaza (``ErrorValidacion``, nunca se asume un valor).
    """

    rechazos_congelar: int
    rechazos_ventana_dias: int
    estado_meta_requerido_para_lanzar: str
    salud_max_antiguedad_h: int
    declaracion_calidad_cuenta_max_dias: int
    disputas_alerta_pct: Any
    disputas_casos_alerta: int
    disputas_casos_pausa: int
    disputas_muestra_min_pagos: int
    ratio_disputas_pausa: Any
    reembolsos_alerta_pct: Any
    reembolsos_pausa_pct: Any
    reembolsos_n_min: int
    disputas_ventana_dias: int | None = None


def cargar_parametros_salud(par: Parametros, lim: Limites) -> ParametrosSalud:
    """Lee los umbrales de salud de ``par``/``lim`` (``ParametroFaltante``/``ErrorLimite``, código 5, si falta alguno)."""
    valores: dict[str, Any] = {clave: par.valor(f"compliance.{clave}") for clave in _CLAVES_COMPLIANCE}
    valores.update({clave: par.valor(f"salud_operativa.{clave}") for clave in _CLAVES_SALUD_OPERATIVA})
    valores["ratio_disputas_pausa"] = lim.valor("ratio_disputas_pausa")
    if par.tiene("salud_operativa.disputas_ventana_dias"):
        valores["disputas_ventana_dias"] = par.valor("salud_operativa.disputas_ventana_dias")
    return ParametrosSalud(**valores)


# ----------------------------------------------------------------------------------------------
# Estado de salud de entrada: formato [SUPUESTO] (sin contrato todavía, ver README «Decisiones»).
# ----------------------------------------------------------------------------------------------
def _exigir_entero_no_negativo(valor: Any, nombre: str) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int) or valor < 0:
        raise ErrorValidacion(f"estado.{nombre}: se espera un entero >= 0")
    return valor


def _exigir_decimal(valor: Any, nombre: str) -> Decimal:
    if isinstance(valor, bool):
        raise ErrorValidacion(f"estado.{nombre}: decimal inválido ({valor!r})")
    try:
        return Decimal(str(valor))
    except InvalidOperation as exc:
        raise ErrorValidacion(f"estado.{nombre}: decimal inválido ({valor!r})") from exc


def _validar_rechazo(rechazo: Any, indice: int) -> dict[str, Any]:
    if not isinstance(rechazo, Mapping):
        raise ErrorValidacion(f"estado.rechazos[{indice}]: se espera un objeto")
    hace_dias = _exigir_entero_no_negativo(rechazo.get("hace_dias"), f"rechazos[{indice}].hace_dias")
    tipo = rechazo.get("tipo")
    if tipo not in _TIPOS_RECHAZO:
        raise ErrorValidacion(f"estado.rechazos[{indice}].tipo: debe ser uno de {_TIPOS_RECHAZO}, no {tipo!r}")
    revertido = rechazo.get("revertido", False)
    if not isinstance(revertido, bool):
        raise ErrorValidacion(f"estado.rechazos[{indice}].revertido: debe ser booleano")
    return {"hace_dias": hace_dias, "tipo": tipo, "revertido": revertido}


def validar_estado(estado: Any) -> dict[str, Any]:
    """Normaliza y valida el estado de salud leído. Falla cerrado: ``ErrorValidacion`` (3) ante
    cualquier dato ausente o con forma incorrecta; nunca se asume un valor por defecto salvo los
    documentados (``calidad_cuenta_meta``/``stripe_aviso`` ausentes = ``None``; ``rechazos`` ausente = []).
    """
    if not isinstance(estado, Mapping):
        raise ErrorValidacion("estado de salud: se espera un objeto JSON")
    faltan = [c for c in _CAMPOS_ESTADO_OBLIGATORIOS if c not in estado]
    if faltan:
        raise ErrorValidacion(f"estado de salud: faltan campos obligatorios: {', '.join(faltan)}")
    account_status = estado["account_status"]
    if not isinstance(account_status, str) or not account_status:
        raise ErrorValidacion("estado.account_status: se espera una cadena no vacía")
    calidad = estado.get("calidad_cuenta_meta")
    if calidad is not None and (not isinstance(calidad, str) or not calidad):
        raise ErrorValidacion("estado.calidad_cuenta_meta: debe ser una cadena no vacía o null")
    stripe_aviso = estado.get("stripe_aviso")
    if stripe_aviso is not None and stripe_aviso not in _AVISOS_STRIPE_VALIDOS:
        raise ErrorValidacion(f"estado.stripe_aviso: valor desconocido {stripe_aviso!r} (se esperaba uno de {_AVISOS_STRIPE_VALIDOS} o null)")
    rechazos_crudos = estado.get("rechazos", [])
    if not isinstance(rechazos_crudos, list):
        raise ErrorValidacion("estado.rechazos: se espera una lista")
    rechazos = [_validar_rechazo(r, i) for i, r in enumerate(rechazos_crudos)]
    return {
        "account_status": account_status,
        "calidad_cuenta_meta": calidad,
        "calidad_edad_dias": _exigir_entero_no_negativo(estado.get("calidad_edad_dias", 0), "calidad_edad_dias"),
        "stripe_aviso": stripe_aviso,
        "rechazos": rechazos,
        "pagos_30d": _exigir_entero_no_negativo(estado["pagos_30d"], "pagos_30d"),
        "disputas_30d": _exigir_entero_no_negativo(estado["disputas_30d"], "disputas_30d"),
        "reembolsos_n": _exigir_entero_no_negativo(estado["reembolsos_n"], "reembolsos_n"),
        "reembolsos_pct": _exigir_decimal(estado["reembolsos_pct"], "reembolsos_pct"),
        "edad_salud_h": _exigir_entero_no_negativo(estado["edad_salud_h"], "edad_salud_h"),
    }


# ----------------------------------------------------------------------------------------------
# La regla (traducción de .claude/skills/x1-compliance/scripts/regla_salud.py::decidir)
# ----------------------------------------------------------------------------------------------
def decidir(estado: Any, params: ParametrosSalud) -> dict[str, Any]:
    """Acción propuesta para ``estado`` (ver :func:`validar_estado` para su forma).

    Devuelve ``{accion, alcance, alertas, lanzamientos_bloqueados, motivos, motivo_ganador,
    pagos_30d, disputas_30d, ratio_disputas, reembolsos_n, reembolsos_pct}``. Las cuatro primeras
    claves (más ``alertas`` como superconjunto) coinciden, serie por serie, con el oráculo
    ``regla_salud.decidir`` sobre ``evals/salud/series.json`` (``tests/compliance/test_salud.py``).
    No pausa nada: es una función pura, sin E/S.
    """
    e = validar_estado(estado)
    accion = "seguir"
    alcance: str | None = None
    alertas: set[str] = set()
    escalaciones: list[tuple[str, str]] = []  # (accion, motivo) de cada escalón que SÍ subió la severidad

    def subir(nueva: str, motivo: str, alc: str | None = None) -> None:
        nonlocal accion, alcance
        if _SEVERIDAD[nueva] > _SEVERIDAD[accion]:
            accion, alcance = nueva, alc
            escalaciones.append((nueva, motivo))

    # 1) cuenta y procesador (lo más grave primero)
    if e["account_status"] != "ACTIVE":
        subir("PAUSA", f"account_status={e['account_status']}", "cuenta")
    calidad = e["calidad_cuenta_meta"]
    if calidad == "Restringida":
        subir("PAUSA", "calidad de cuenta Restringida", "cuenta")
    elif calidad is not None and calidad != params.estado_meta_requerido_para_lanzar:
        subir("congelar_hoja", f"calidad de cuenta {calidad}: congelar lanzamientos y auditar", "cuenta")  # [SUPUESTO] alcance = toda hoja nueva
        alertas.add("auditar_14_dias")
    aviso = e["stripe_aviso"]
    if aviso in _AVISOS_STRIPE_CUENTA:
        subir("PAUSA", f"aviso de Stripe: {aviso}", "cuenta")
    elif aviso in _AVISOS_STRIPE_OFERTA:
        subir("pausar_oferta", f"aviso de Stripe: {aviso}", "oferta")
    elif aviso == "informacion":
        alertas.add("stripe_pide_informacion")

    # 2) rechazos de Meta en la ventana (un rechazo revertido en revisión no cuenta)
    vivos = [r for r in e["rechazos"] if not r["revertido"] and r["hace_dias"] <= params.rechazos_ventana_dias]
    if any(r["tipo"] in _TIPOS_RECHAZO_HOJA for r in vivos):
        subir("congelar_hoja", "rechazo de producto o contenido", "hoja")
    if any(r["tipo"] == "pieza" for r in vivos):
        subir("congelar_angulo", "rechazo de pieza", "angulo")
    if len(vivos) >= params.rechazos_congelar:
        subir("congelar_hoja", f"{len(vivos)} rechazos en la ventana (>= rechazos_congelar)", "cuenta")
        alertas.add("bajar_D5_D9_a_N1")

    # 3) disputas + EFW
    pagos, casos = e["pagos_30d"], e["disputas_30d"]
    ratio = (Decimal(casos) / Decimal(pagos)) if pagos else Decimal(0)
    if pagos >= params.disputas_muestra_min_pagos and ratio >= Decimal(str(params.ratio_disputas_pausa)):
        subir("pausar_oferta", "ratio de disputas >= limites.ratio_disputas_pausa", "oferta")
        alertas.add("proponer_pausa_macro_gate_H")
    if casos >= params.disputas_casos_pausa:
        subir("pausar_oferta", "casos de disputa >= disputas_casos_pausa", "oferta")
    elif casos >= params.disputas_casos_alerta or (pagos >= params.disputas_muestra_min_pagos
                                                    and ratio * 100 >= Decimal(str(params.disputas_alerta_pct))):
        alertas.add("alerta_disputas")

    # 4) reembolsos (solo con muestra suficiente)
    if e["reembolsos_n"] >= params.reembolsos_n_min:
        pct = e["reembolsos_pct"]
        if pct >= Decimal(str(params.reembolsos_pausa_pct)):
            subir("pausar_oferta", "reembolsos >= reembolsos_pausa_pct", "oferta")
        elif pct >= Decimal(str(params.reembolsos_alerta_pct)):
            alertas.add("alerta_reembolsos")

    # 5) frescura de los datos de salud: sin dato fresco no se lanza
    bloqueados = accion != "seguir"
    if e["edad_salud_h"] > params.salud_max_antiguedad_h:
        alertas.add("salud_vieja")
        bloqueados = True
    if calidad is not None and e["calidad_edad_dias"] > params.declaracion_calidad_cuenta_max_dias:
        alertas.add("declaracion_calidad_vencida")
        bloqueados = True

    return {
        "accion": accion,
        "alcance": alcance,
        "alertas": sorted(alertas),
        "lanzamientos_bloqueados": bloqueados,
        "motivos": [motivo for _, motivo in escalaciones],
        "motivo_ganador": escalaciones[-1][1] if escalaciones else None,
        "pagos_30d": pagos,
        "disputas_30d": casos,
        "ratio_disputas": ratio,
        "reembolsos_n": e["reembolsos_n"],
        "reembolsos_pct": e["reembolsos_pct"],
    }


def resultado_publico(resultado: Mapping[str, Any]) -> dict[str, Any]:
    """``resultado`` de :func:`decidir` con los ``Decimal`` internos como cadena (JSON-serializable)."""
    publico = dict(resultado)
    publico["ratio_disputas"] = str(resultado["ratio_disputas"])
    publico["reembolsos_pct"] = str(resultado["reembolsos_pct"])
    return publico


# ----------------------------------------------------------------------------------------------
# senal_pausa.json: propuesta de X1 (solo escribe en la ruta que indique quien llama)
# ----------------------------------------------------------------------------------------------
def _formatear_decimal(valor: Any) -> str:
    try:
        d = Decimal(str(valor))
    except InvalidOperation as exc:
        raise ErrorValidacion(f"valor decimal inválido: {valor!r}") from exc
    return format(d, "f")


def _categoria_motivo(texto: str) -> str:
    bajo = texto.lower()
    if "disputa" in bajo:
        return "disputas"
    if "reembolso" in bajo:
        return "reembolsos"
    return "otro"


def _motivo_senal(resultado: Mapping[str, Any]) -> str:
    if resultado["motivo_ganador"] is not None:
        return _categoria_motivo(resultado["motivo_ganador"])
    if "alerta_disputas" in resultado["alertas"]:
        return "disputas"
    if "alerta_reembolsos" in resultado["alertas"]:
        return "reembolsos"
    if resultado["alertas"]:
        return "otro"
    return "ninguno"


def _nivel_y_accion_solicitada(resultado: Mapping[str, Any]) -> tuple[str, str]:
    accion = resultado["accion"]
    if accion == "seguir":
        return ("amarillo", "alertar") if resultado["alertas"] else ("verde", "ninguna")
    return ("rojo" if accion in ("pausar_oferta", "PAUSA") else "amarillo"), "pausar"


def construir_senal_pausa(*, oferta_id: str, resultado: Mapping[str, Any], params: ParametrosSalud,
                          ahora: Callable[[], datetime] = comun.ahora_utc, sintetico: bool = True) -> dict[str, Any]:
    """Arma (sin escribir) el ``senal_pausa.json`` que propone ``compliance.salud pausa``.

    Decisiones (``compliance/README.md``): el ``motivo`` del contrato (``ninguno/disputas/
    reembolsos/.../otro``) es más angosto que las causas reales de X1 (cuenta de Meta, calidad,
    rechazos, avisos de Stripe que no son disputas ni reembolsos): todo lo demás se informa como
    ``otro``. ``accion_solicitada`` tampoco distingue ``congelar_angulo``/``congelar_hoja`` de
    ``pausar_oferta``/``PAUSA``: cualquier acción distinta de ``seguir`` pide ``pausar`` (más
    conservador que pedir solo ``alertar``); el detalle fino de :func:`decidir` viaja en
    ``datos.decision`` de la CLI, no en este artefacto. ``muestra_suficiente`` exige las DOS
    muestras (pagos y pedidos de reembolso) por encima de su mínimo: es deliberadamente
    conservador (ver README).

    Errores: ``ErrorValidacion`` (3) si el resultado no cumple ``senal_pausa.schema.json`` (defensivo:
    no debería ocurrir con entradas bien formadas) o si falta ``params.disputas_ventana_dias``.
    """
    if params.disputas_ventana_dias is None:
        raise ErrorValidacion("falta salud_operativa.disputas_ventana_dias: no se puede armar metricas.ventana_dias")
    pagos, casos = resultado["pagos_30d"], resultado["disputas_30d"]
    ratio_pct = (resultado["ratio_disputas"] * 100).quantize(_DECIMALES_PCT, rounding=ROUND_HALF_EVEN)
    muestra_suficiente = pagos >= params.disputas_muestra_min_pagos and resultado["reembolsos_n"] >= params.reembolsos_n_min
    nivel, accion_solicitada = _nivel_y_accion_solicitada(resultado)
    momento = comun.instante(ahora)
    datos = {
        "schema_version": _SCHEMA_VERSION_SENAL_PAUSA,
        "oferta_id": oferta_id,
        "ts": comun.iso_z(momento),
        "emitida": accion_solicitada != "ninguna",
        "nivel": nivel,
        "motivo": _motivo_senal(resultado),
        "metricas": {
            "muestra_suficiente": muestra_suficiente,
            "pagos_ventana": pagos,
            "casos_disputa_efw": casos,
            "disputas_efw_pct": format(ratio_pct, "f"),
            "reembolsos_pct": _formatear_decimal(resultado["reembolsos_pct"]),
            "ventana_dias": params.disputas_ventana_dias,
        },
        "umbrales_usados": {
            "disputas_alerta_pct": _formatear_decimal(params.disputas_alerta_pct),
            "ratio_disputas_pausa": _formatear_decimal(params.ratio_disputas_pausa),
            "reembolsos_alerta_pct": _formatear_decimal(params.reembolsos_alerta_pct),
            "reembolsos_pausa_pct": _formatear_decimal(params.reembolsos_pausa_pct),
        },
        "accion_solicitada": accion_solicitada,
        "consumida_por": None,
        "sintetico": bool(sintetico),
    }
    errores = comun.errores_de_esquema("senal_pausa", datos)
    if errores:
        raise ErrorValidacion(f"senal_pausa construida inválida: {comun.resumir_errores_esquema(errores)}")
    return datos


def _ruta_dentro_de_oferta(ruta: Path, *, raiz: Path, oferta_id: str) -> Path:
    """``ruta`` resuelta; ``ErrorUso`` (2) si no cae bajo ``<raiz>/ofertas/<oferta_id>/``."""
    base = (raiz / "ofertas" / oferta_id).resolve()
    destino = (ruta if ruta.is_absolute() else raiz / ruta).resolve()
    try:
        destino.relative_to(base)
    except ValueError as exc:
        raise ErrorUso(f"--salida debe caer dentro de ofertas/{oferta_id}/ (una carpeta de la propia oferta): {destino}") from exc
    return destino


def escribir_senal_pausa(datos: Mapping[str, Any], destino: Path) -> None:
    """Escribe ``datos`` (ya construido y validado) en ``destino`` de forma atómica."""
    comun.escribir_atomico(destino, comun.json_canonico(dict(datos)))


# ----------------------------------------------------------------------------------------------
# CLI: python -m compliance.salud {evaluar,pausa}
# ----------------------------------------------------------------------------------------------
def _cargar_estado(ruta: Path) -> Any:
    try:
        return comun.cargar_json(ruta)
    except FileNotFoundError as exc:
        raise ErrorUso(f"no existe --estado: {ruta}") from exc
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ErrorValidacion(f"--estado ilegible: {exc}") from exc


def _cargar_params(args: argparse.Namespace, *, raiz: Path, env: Mapping[str, str]) -> ParametrosSalud:
    par = cargar_parametros(args.parametros) if args.parametros else cargar_parametros(raiz / "empresa" / "parametros.yaml")
    entorno = comun.entorno(env)
    lim = cargar_limites(args.limites, env=env, entorno=entorno) if args.limites else cargar_limites(
        raiz / "empresa" / "limites.yaml", env=env, entorno=entorno)
    return cargar_parametros_salud(par, lim)


def _construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m compliance.salud", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("evaluar", help="decide la acción de salud (solo lectura; nunca pausa nada)")
    pe.add_argument("--estado", required=True, type=Path, help="JSON con el estado de salud (ver compliance/README.md)")
    pe.add_argument("--parametros", type=Path, default=None, help="por defecto, <raíz>/empresa/parametros.yaml")
    pe.add_argument("--limites", type=Path, default=None, help="por defecto, <raíz>/empresa/limites.yaml")
    pe.add_argument("--raiz", type=Path, default=None)
    pe.add_argument("--json", action="store_true")

    pp = sub.add_parser("pausa", help="evalúa y arma (o, con --aplicar, escribe) la propuesta de senal_pausa.json")
    pp.add_argument("--estado", required=True, type=Path)
    pp.add_argument("--oferta", required=True, help="OF-AAAAMM-NN")
    pp.add_argument("--salida", required=True, type=Path, help="ruta del senal_pausa.json a proponer; debe caer bajo ofertas/<oferta>/")
    pp.add_argument("--aplicar", action="store_true", help="sin esto: dry-run (convenciones §9), solo imprime el plan")
    pp.add_argument("--sintetico", action=argparse.BooleanOptionalAction, default=True, help="marca sintetico=true/false en el artefacto")
    pp.add_argument("--ahora", default=None, help="instante ISO con Z (solo fuera de produccion)")
    pp.add_argument("--parametros", type=Path, default=None)
    pp.add_argument("--limites", type=Path, default=None)
    pp.add_argument("--raiz", type=Path, default=None)
    pp.add_argument("--json", action="store_true")
    return p


def _imprimir(salida: Mapping[str, Any], *, usar_json: bool, resultado: Mapping[str, Any]) -> None:
    if usar_json:
        print(comun.json_canonico(salida).decode("utf-8"))
    else:
        print(f"accion={resultado['accion']} alcance={resultado['alcance']} "
              f"bloqueados={resultado['lanzamientos_bloqueados']} alertas={','.join(resultado['alertas']) or '-'}")


def main(argv: list[str] | None = None) -> int:
    """``python -m compliance.salud {evaluar,pausa} ...``. Salida: 0 ok · 2 uso · 3 dato inválido ·
    5 falta un parámetro de ``parametros.yaml``/``limites.yaml`` (convenciones §8)."""
    try:
        args = _construir_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if args.raiz and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz no existe con FABRICA_ENTORNO=produccion")
        if args.cmd == "pausa" and args.ahora and comun.entorno(env) == "produccion":
            raise ErrorUso("--ahora no existe con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz(env)
        estado = _cargar_estado(args.estado)
        params = _cargar_params(args, raiz=raiz, env=env)
        resultado = decidir(estado, params)

        if args.cmd == "evaluar":
            salida = {"ok": True, "modo": "dry_run", "codigo": 0, "datos": resultado_publico(resultado), "avisos": []}
            _imprimir(salida, usar_json=args.json, resultado=resultado)
            return 0

        reloj = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        senal = construir_senal_pausa(oferta_id=args.oferta, resultado=resultado, params=params, ahora=reloj, sintetico=args.sintetico)
        destino = _ruta_dentro_de_oferta(args.salida, raiz=raiz, oferta_id=args.oferta)
        avisos: list[str] = []
        if args.aplicar:
            escribir_senal_pausa(senal, destino)
            modo = "live"
        else:
            modo = "dry_run"
            avisos.append(f"dry-run: no se escribió nada; repetir con --aplicar para escribir en {destino}")
        salida = {
            "ok": True, "modo": modo, "codigo": 0,
            "datos": {"decision": resultado_publico(resultado), "senal_pausa": senal, "destino": str(destino)},
            "avisos": avisos,
        }
        _imprimir(salida, usar_json=args.json, resultado=resultado)
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    import sys

    sys.exit(main())
