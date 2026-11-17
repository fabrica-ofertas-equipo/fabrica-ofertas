"""Ruta B del barrido: las consultas de la Biblioteca de Anuncios corren SIN pantalla, con `claude -p`.

Qué hace (contrato: scripts/modelado/barrido/CONTRATO.md §2, §3 y §5; informe: docs/_historial/barrido-ruta-b.md):

- `ejecutar_plan` recorre el plan (`empresa/barrido/planes/<corrida_id>.json`) y lanza UNA consulta por proceso
  `claude -p` (lista de argumentos, sin shell, con plazo, tope de gasto por consulta y total, entorno mínimo).
  Cada proceso usa el conector de claude.ai de Meta Ads de la sesión de suscripción de esta máquina.
- El modelo NO escribe nada: solo llama a `ads_library_search` con los argumentos del plan. El código lee el flujo
  `stream-json`, toma el resultado EXACTO que devolvió el conector (no una copia del modelo), comprueba que hubo UNA
  sola llamada y que fue la planificada, y arma el crudo del CONTRATO §2 con `ruta: "B"`. Se valida con `comun.validar_crudo` y se escribe
  con `comun.escribir_json_nuevo` (atómico, sin sobrescribir). Principio del repo: la IA propone, el código dispone.
- Idempotente por `qid`: un `<qid>.json` válido ya existente se salta; un `<qid>.error.json` también (se reintenta solo
  con `reintentar_fallidas=True`); un `<qid>.json` corrupto nunca se sobrescribe, se informa.
- Frenos (todos leídos de parámetros, ninguno fijo aquí): tanda, día, corrida (tope de consultas del modelado, contando
  también los reintentos), gasto por consulta y total, errores seguidos y errores totales, pausa entre lanzamientos.
  Un cierre de sesión o un límite de uso detienen la ejecución en el acto; un límite o bloqueo de Meta además deja el
  pestillo `empresa/barrido/ruta_b/BLOQUEO.json` (revisión de seguridad m3), que solo una persona borra.
- Un solo proceso a la vez por corrida (`flock` sobre `empresa/barrido/ruta_b/<corrida_id>.lock`).
- Registro de auditoría append-only: `empresa/barrido/ruta_b/<corrida_id>.jsonl` (una línea por lanzamiento, sin floats).
  De ahí salen el gasto acumulado y los lanzamientos del día, de modo que los topes sobreviven a reinicios.

CLI: `python -m scripts.modelado.barrido.ruta_b --corrida 2026-11-06-a` (simulación: no lanza nada) y con `--vivo`
lanza de verdad. Códigos de salida (docs/convenciones-de-codigo.md §8): 0 correcto o tanda hecha, 2 uso, 3 validación,
4 bloqueado (`empresa/PAUSA`, `BLOQUEO.json` o inyección sospechada), 5 tope o parámetro de límites, 6 externo (sesión,
límite de uso, límite de Meta, errores repetidos). Con `FABRICA_ENTORNO=produccion` se rechazan `--raiz`, `--parametros`
y `--parametros-modelado` (M1), y con `--vivo` el registro, el tope diario, `PAUSA` y `BLOQUEO.json` se leen y escriben
SIEMPRE en `comun.RAIZ`, nunca en `--raiz`: quien invoca no puede reiniciar los frenos apuntando a otra carpeta.

Seguridad (revisión independiente, docs/_historial/barrido-revision-seguridad.md M1, M2 y m3): los títulos y nombres que
devuelve la Biblioteca son dato NO confiable y el modelo del hijo SÍ ve los resultados (en `claude -p` el `tool_result`
vuelve al modelo por fuerza), así que un anunciante podría intentar inyectarle instrucciones. Por eso la defensa no
descansa en el prompt sino en capas técnicas: (1) lista blanca estricta, solo `ToolSearch` y `ads_library_search`
(`--allowedTools` + `dontAsk`); (2) denegaciones explícitas de todo lo que escribe en Meta o lee/escribe archivos o sale a
la red (`barrido_b_herramientas_excluidas`, con un mínimo que el código exige); (3) cualquier llamada al conector distinta
de UNA sola se trata como `inyeccion_sospechada` y detiene la ejecución; (4) la llamada debe coincidir con el plan;
(5) el crudo sale del `tool_result` y se valida, no del texto del modelo; (6) carpeta de trabajo vacía y entorno mínimo.
"""

from __future__ import annotations

import argparse
import fcntl
import fnmatch
import json
import math
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

from scripts.modelado.barrido import comun

ErrorFabrica = comun.ErrorFabrica
ErrorUso = comun.ErrorUso
ErrorValidacion = comun.ErrorValidacion
ErrorBloqueado = comun.ErrorBloqueado
ErrorLimite = comun.ErrorLimite


class ErrorExterno(ErrorFabrica):
    """Falla fuera del programa: sesión caída, límite de uso, conector que no responde (6)."""

    codigo_salida = 6


# ---------------------------------------------------------------------------
# Constantes que son HECHOS de la herramienta o del contrato (no umbrales calibrables)
# ---------------------------------------------------------------------------

RUTA_PARAMETROS_RUTA_B: Path = comun.RAIZ / "scripts" / "modelado" / "barrido" / "parametros_ruta_b.propuesta.yaml"

CLAVES_ENTERAS = {  # clave -> mínimo permitido
    "barrido_b_turnos_max": 1,
    "barrido_b_timeout_consulta_seg": 1,
    "barrido_b_gracia_seg": 1,
    "barrido_b_pausa_entre_consultas_seg": 0,
    "barrido_b_consultas_por_tanda_max": 1,
    "barrido_b_max_consultas_por_dia": 1,
    "barrido_b_errores_consecutivos_max": 1,
    "barrido_b_errores_corrida_max": 1,
    "barrido_b_reintentos_por_consulta": 0,
}
CLAVES_DECIMALES = ("barrido_b_presupuesto_consulta_usd", "barrido_b_presupuesto_corrida_usd")
CLAVES_TEXTO = ("barrido_b_modelo", "barrido_b_herramienta")
CLAVES_LISTA = ("barrido_b_herramientas_excluidas",)
CLAVES_PARAMETROS = tuple(CLAVES_ENTERAS) + CLAVES_DECIMALES + CLAVES_TEXTO + CLAVES_LISTA

# Variables que SÍ se heredan al proceso hijo (identidad del usuario para leer su sesión y rutas). Nada de
# ANTHROPIC_*, CLAUDE_CODE_*, GITHUB_*, STRIPE_*, META_*: con una clave de API los conectores de claude.ai no cargan
# (docs/09-runtime-de-agentes.md H2) y el resto sobra.
ENTORNO_HEREDADO = ("HOME", "USER", "LOGNAME", "PATH", "LANG", "LC_ALL", "TMPDIR")
ENTORNO_FIJO = {"CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1"}

ENTORNOS = ("desarrollo", "prueba", "produccion")  # mismo vocabulario que cli.py (FABRICA_ENTORNO)

# Piso de seguridad (revisión M2): lo que el hijo NUNCA debe poder usar aunque alguien edite el YAML. Son nombres de
# herramientas (hechos), no umbrales. La lista blanca real es `--allowedTools`; esto es la segunda capa.
EXCLUSIONES_MINIMAS = (
    "mcp__claude_ai_Meta_ADS__ads_create_*", "mcp__claude_ai_Meta_ADS__ads_update_*",
    "mcp__claude_ai_Meta_ADS__ads_activate_entity", "mcp__claude_ai_Meta_ADS__ads_boost_ig_post",
    "mcp__claude_ai_Meta_ADS__ads_delete_*", "mcp__claude_ai_Meta_ADS__ads_creative_*",
    "mcp__claude_ai_Meta_ADS__ads_catalog_*", "mcp__claude_ai_Meta_ADS__ads_pixel_*",
    "mcp__claude_ai_Meta_ADS__ads_experiment_*",
    "Bash", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch", "Read", "Glob", "Grep", "Skill",
)

FATALES_CON_ERROR_DE_CONSULTA = ("inyeccion_sospechada",)  # el problema es de ESA consulta: se marca como fallida
ESTADO_POR_FATAL = {"sesion": "sesion_invalida", "limite_uso": "limite_uso", "limite_meta": "limite_meta",
                    "inyeccion_sospechada": "inyeccion_sospechada"}

ESTADOS_LIMITE_USO_OK = ("allowed", "allowed_warning")
CAMPOS_EXTRA_PERMITIDOS = ("advertiser_job", "advertiser_request", "client_conversation_id", "client_model",
                           "scheduled_task_run")  # campos de telemetría del conector: no cambian la consulta
CAMPOS_CONSULTA_HERRAMIENTA = ("search_terms", "countries", "ad_active_status", "limit", "page_ids")

_RE_HERRAMIENTA = re.compile(r"mcp__[A-Za-z0-9_]+__[A-Za-z0-9_]+")
_RE_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f\u2028\u2029]")
_RE_DIGITOS = re.compile(r"[0-9]+")
_RE_PAIS = re.compile(r"[A-Z]{2}")
# Textos con los que el conector/Meta avisa de límite de tasa o bloqueo (revisión m3): (#4), (#17) y (#613) son los
# códigos de límite de la API de Meta. `(?![0-9])` evita confundir #4 con #41 o #170.
_RE_LIMITE_META = re.compile(r"rate[ _-]?limit|blocked|temporarily|too many|#(?:4|17|613)(?![0-9])", re.IGNORECASE)
_CENTAVOS_MICRO = Decimal("0.000001")  # precisión de presentación del gasto (no es un umbral)
_MAX_MENSAJE = 300  # largo de los mensajes de error que se copian al registro (solo presentación)

Reloj = Callable[[], datetime]


# ---------------------------------------------------------------------------
# Parámetros (propios de la ruta B; el tope de consultas por corrida viene del modelado)
# ---------------------------------------------------------------------------

def _decimal(clave: str, valor: Any) -> Decimal:
    if isinstance(valor, bool) or isinstance(valor, float) or not isinstance(valor, (int, str, Decimal)):
        raise ErrorValidacion(f"{clave}: use entero o cadena decimal, llegó {type(valor).__name__}")
    try:
        d = Decimal(valor) if not isinstance(valor, str) else Decimal(valor.strip())
    except InvalidOperation as exc:
        raise ErrorValidacion(f"{clave}: «{valor}» no es un decimal") from exc
    if not d.is_finite() or d <= 0:
        raise ErrorValidacion(f"{clave}: debe ser un decimal finito mayor que 0")
    return d


def normalizar_parametros(crudos: Mapping[str, Any]) -> dict[str, Any]:
    """Valida y tipa los parámetros de la ruta B. Falta una clave = ErrorLimite (5); tipo raro = ErrorValidacion (3)."""
    faltan = [c for c in CLAVES_PARAMETROS if c not in crudos or crudos[c] is None]
    if faltan:
        raise ErrorLimite(f"faltan parámetros de la ruta B: {', '.join(faltan)} (falla cerrado: no se asume ninguno)")
    p: dict[str, Any] = {}
    for clave, minimo in CLAVES_ENTERAS.items():
        v = crudos[clave]
        if isinstance(v, bool) or not isinstance(v, int):
            raise ErrorValidacion(f"{clave}: se esperaba un entero, llegó {type(v).__name__}")
        if v < minimo:
            raise ErrorLimite(f"{clave}: {v} es menor que el mínimo permitido {minimo}")
        p[clave] = v
    for clave in CLAVES_DECIMALES:
        p[clave] = _decimal(clave, crudos[clave])
    if p["barrido_b_presupuesto_consulta_usd"] > p["barrido_b_presupuesto_corrida_usd"]:
        raise ErrorLimite("el tope por consulta no puede superar el tope de la corrida")
    for clave in CLAVES_TEXTO:
        v = crudos[clave]
        if not isinstance(v, str) or not v.strip() or _RE_CONTROL.search(v) or v.startswith("-"):
            raise ErrorValidacion(f"{clave}: se esperaba un texto no vacío, sin controles ni guion inicial")
        p[clave] = v.strip()
    if not _RE_HERRAMIENTA.fullmatch(p["barrido_b_herramienta"]):
        raise ErrorValidacion("barrido_b_herramienta: se esperaba el nombre exacto mcp__<servidor>__<herramienta>")
    for clave in CLAVES_LISTA:
        v = crudos[clave]
        if not isinstance(v, (list, tuple)) or any(not isinstance(x, str) or not x or _RE_CONTROL.search(x)
                                                  or x.startswith("-") for x in v):
            raise ErrorValidacion(f"{clave}: se esperaba una lista de patrones de herramienta (texto sin controles)")
        p[clave] = list(v)
    faltan_exclusiones = [x for x in EXCLUSIONES_MINIMAS if x not in p["barrido_b_herramientas_excluidas"]]
    if faltan_exclusiones:
        raise ErrorLimite("barrido_b_herramientas_excluidas debe denegar como mínimo: " + ", ".join(faltan_exclusiones)
                          + " (revisión de seguridad M2; falla cerrado)")
    cubiertas = [x for x in p["barrido_b_herramientas_excluidas"]
                 if fnmatch.fnmatchcase(p["barrido_b_herramienta"], x)]
    if cubiertas:  # una denegación gana a una permisión: la ruta B no funcionaría nunca
        raise ErrorValidacion(f"barrido_b_herramientas_excluidas {cubiertas} cubre la herramienta permitida "
                              f"{p['barrido_b_herramienta']}")
    return p


def cargar_parametros_ruta_b(ruta: Path | None = None) -> dict[str, Any]:
    """Lee `parametros_ruta_b.propuesta.yaml` (o `ruta`): mismo formato `{valor, unidad, hipotesis, fuente, rango}`.

    Falla cerrado: archivo ilegible o clave ausente = ErrorLimite; valor fuera de su `rango` = ErrorLimite; clave
    NUMÉRICA sin `rango` (null o ausente) = ErrorLimite (revisión M1: un `rango: null` no puede saltarse el control).
    """
    import yaml  # PyYAML está en requirements.txt de la raíz

    ruta = Path(ruta) if ruta is not None else RUTA_PARAMETROS_RUTA_B
    try:
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErrorLimite(f"no se pudo leer {ruta}: {exc} (falla cerrado)") from exc
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ErrorValidacion(f"{ruta}: YAML inválido ({exc})") from exc
    if not isinstance(datos, dict) or not isinstance(datos.get("grupos"), dict):
        raise ErrorValidacion(f"{ruta}: se esperaba `grupos:` con las entradas de parámetros")
    entradas: dict[str, Mapping[str, Any]] = {}
    for grupo in datos["grupos"].values():
        if isinstance(grupo, dict):
            for clave, entrada in grupo.items():
                if isinstance(entrada, dict) and "valor" in entrada:
                    entradas[str(clave)] = entrada
    crudos = {c: e["valor"] for c, e in entradas.items()}
    p = normalizar_parametros(crudos)
    for clave in CLAVES_PARAMETROS:
        if isinstance(p[clave], (str, list)):
            continue  # texto y listas no llevan rango numérico
        rango = entradas[clave].get("rango")
        if rango is None:
            raise ErrorLimite(f"{clave}: sin «rango» aprobado en {ruta}; un parámetro numérico exige rango "
                              "(falla cerrado: sin rango no hay control)")
        if not (isinstance(rango, list) and len(rango) == 2):
            raise ErrorValidacion(f"{clave}: «rango» debe ser [mínimo, máximo]")
        lo, hi = (_decimal_rango(clave, e) for e in rango)
        if not lo <= Decimal(p[clave]) <= hi:
            raise ErrorLimite(f"{clave}: {p[clave]} fuera del rango aprobado [{lo}, {hi}] (falla cerrado)")
    return p


def _decimal_rango(clave: str, e: Any) -> Decimal:
    if isinstance(e, bool) or isinstance(e, float) or not isinstance(e, (int, str)):
        raise ErrorValidacion(f"{clave}: extremo de «rango» inválido {e!r} (entero o cadena decimal)")
    try:
        return Decimal(e) if isinstance(e, int) else Decimal(e.strip())
    except InvalidOperation as exc:
        raise ErrorValidacion(f"{clave}: extremo de «rango» inválido {e!r}") from exc


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

def validar_plan(plan: Any, tope_modelado: int | None = None) -> dict[str, Any]:
    """Normaliza el plan (CONTRATO §3) y rechaza lo que la ruta B no puede ejecutar con seguridad.

    Acepta el dict ya leído o la ruta del JSON. Devuelve `{corrida_id, tope, consultas:[{qid, search_terms, countries,
    ad_active_status, limit, page_ids}]}`. Errores: ErrorValidacion (forma), ErrorLimite (más consultas que el tope).
    """
    if isinstance(plan, (str, Path)):
        plan = comun.leer_json(Path(plan))
    if not isinstance(plan, Mapping):
        raise ErrorValidacion("plan: se esperaba un objeto JSON")
    corrida = plan.get("corrida_id")
    if not comun.corrida_id_valido(corrida):
        raise ErrorValidacion(f"plan.corrida_id inválido: {corrida!r}")
    consultas = plan.get("consultas")
    if not isinstance(consultas, list) or not consultas:
        raise ErrorValidacion("plan.consultas: se esperaba una lista no vacía")
    topes = []
    if tope_modelado is not None:
        topes.append(tope_modelado)
    if plan.get("tope_consultas") is not None:
        t = plan["tope_consultas"]
        if isinstance(t, bool) or not isinstance(t, int) or t < 1:
            raise ErrorValidacion(f"plan.tope_consultas inválido: {t!r}")
        topes.append(t)
    if not topes:
        raise ErrorLimite("no hay tope de consultas por corrida (ni en el plan ni en los parámetros): falla cerrado")
    tope = min(topes)
    if len(consultas) > tope:
        raise ErrorLimite(f"el plan trae {len(consultas)} consultas y el tope de la corrida es {tope} (falla cerrado)")
    vistos: set[str] = set()
    normalizadas = []
    for i, c in enumerate(consultas):
        normalizadas.append(_validar_consulta(c, i, vistos))
    return {"corrida_id": corrida, "tope": tope, "consultas": normalizadas}


def _validar_consulta(c: Any, i: int, vistos: set[str]) -> dict[str, Any]:
    donde = f"plan.consultas[{i}]"
    if not isinstance(c, Mapping):
        raise ErrorValidacion(f"{donde}: se esperaba un objeto")
    qid = c.get("qid")
    if not comun.qid_valido(qid):
        raise ErrorValidacion(f"{donde}.qid inválido: {qid!r}")
    if qid in vistos:
        raise ErrorValidacion(f"{donde}.qid repetido: {qid}")
    vistos.add(qid)
    paises = c.get("countries")
    if not (isinstance(paises, list) and len(paises) == 1 and isinstance(paises[0], str)
            and _RE_PAIS.fullmatch(paises[0])):
        raise ErrorValidacion(f"{donde}.countries: se esperaba UN país ISO-2 en mayúsculas (un país por consulta)")
    estado = c.get("ad_active_status")
    if estado not in comun.ESTADOS_ANUNCIO:
        raise ErrorValidacion(f"{donde}.ad_active_status: {estado!r} no está en {comun.ESTADOS_ANUNCIO}")
    limite = c.get("limit")
    if isinstance(limite, bool) or not isinstance(limite, int) or not 1 <= limite <= comun.LIMITE_MAX_CONECTOR:
        raise ErrorValidacion(f"{donde}.limit: se esperaba un entero entre 1 y {comun.LIMITE_MAX_CONECTOR}")
    terminos = c.get("search_terms")
    if terminos is not None:
        if not isinstance(terminos, str) or _RE_CONTROL.search(terminos):
            raise ErrorValidacion(f"{donde}.search_terms: texto sin saltos de línea ni caracteres de control")
        if not terminos.strip():
            terminos = None
    page_ids = c.get("page_ids")
    if page_ids is not None:
        if not isinstance(page_ids, list) or not page_ids:
            raise ErrorValidacion(f"{donde}.page_ids: null o lista no vacía")
        normalizados = []
        for p in page_ids:
            if isinstance(p, bool) or not isinstance(p, (int, str)) or not _RE_DIGITOS.fullmatch(str(p)):
                raise ErrorValidacion(f"{donde}.page_ids: se esperaban ids de solo dígitos, llegó {p!r}")
            normalizados.append(str(p))
        if len(set(normalizados)) != len(normalizados):
            raise ErrorValidacion(f"{donde}.page_ids repetidos")
        page_ids = normalizados
    if terminos is None and page_ids is None:
        raise ErrorValidacion(f"{donde}: sin search_terms ni page_ids no hay qué buscar")
    return {"qid": qid, "search_terms": terminos, "countries": [paises[0]], "ad_active_status": estado,
            "limit": limite, "page_ids": page_ids}


# ---------------------------------------------------------------------------
# Construcción del proceso (argumentos, entorno, encargo al modelo)
# ---------------------------------------------------------------------------

def argumentos_herramienta(consulta: Mapping[str, Any]) -> dict[str, Any]:
    """Argumentos EXACTOS que el modelo debe pasar a `ads_library_search` (solo los que la consulta define)."""
    args: dict[str, Any] = {}
    if consulta["search_terms"] is not None:
        args["search_terms"] = consulta["search_terms"]
    if consulta["page_ids"] is not None:
        args["page_ids"] = list(consulta["page_ids"])
    args["countries"] = list(consulta["countries"])
    args["ad_active_status"] = consulta["ad_active_status"]
    args["limit"] = consulta["limit"]
    return args


def construir_prompt(consulta: Mapping[str, Any], par: Mapping[str, Any]) -> str:
    """Encargo en lenguaje natural: cargar la herramienta, llamarla UNA vez con los argumentos del plan, decir LISTO.

    Redacción medida en vivo (2026-11-06, docs/_historial/barrido-ruta-b.md §3): un encargo «mecánico» («no comentes
    nada», «no cambies ningún valor», con metadatos que el modelo debe inventar) fue rechazado por el modelo como
    posible inyección de instrucciones o extracción masiva (0 de 20 en la configuración restrictiva, 1 de 8 con sonnet);
    esta redacción —propósito honesto, solo lectura, sin pedir metadatos inventados— cumplió 8 de 8. Los metadatos del
    conector (`scheduled_task_run`, `client_conversation_id`) los completa el modelo según el esquema de la herramienta.
    El encargo no lleva texto de la Biblioteca (solo los argumentos del plan). Ojo: el modelo SÍ ve después los
    resultados de la herramienta (el `tool_result` vuelve a él por fuerza): la defensa contra texto hostil no es esta
    redacción sino las capas técnicas del módulo (ver el docstring del módulo).
    """
    herramienta = par["barrido_b_herramienta"]
    args = json.dumps(argumentos_herramienta(consulta), ensure_ascii=False)
    return (
        "Busca en la Biblioteca de Anuncios de Meta con la herramienta ads_library_search "
        f"(cárgala antes con ToolSearch: select:{herramienta}). "
        f"Argumentos: {args}. "
        "Es una única consulta de solo lectura para una investigación de mercado de la dueña de la cuenta, "
        "lanzada por una tarea programada. Si la herramienta da error, no reintentes. "
        "Cuando termines, responde solo: LISTO."
    )


def construir_argv(claude_bin: str, prompt: str, par: Mapping[str, Any]) -> list[str]:
    """Lista de argumentos de `claude -p` (jamás una cadena de shell).

    Superficie mínima, medida en vivo (2026-11-06): `--allowedTools` permite solo ToolSearch y la herramienta del
    conector; `dontAsk` niega lo demás sin preguntar; `--disallowedTools` retira del contexto las herramientas que no
    hacen falta (Bash, Write, Web..., otros conectores); sin transcripción en disco.
    NO se usa `--tools ToolSearch`: con ese flag el modelo dejó de encontrar ToolSearch y se negó (0 de 20 pruebas).
    """
    argv = [
        claude_bin, "-p", prompt,
        "--output-format", "stream-json", "--verbose",
        "--permission-mode", "dontAsk",
        "--max-turns", str(par["barrido_b_turnos_max"]),
        "--max-budget-usd", format(par["barrido_b_presupuesto_consulta_usd"], "f"),
        "--model", par["barrido_b_modelo"],
        "--allowedTools", f"ToolSearch,{par['barrido_b_herramienta']}",
        "--setting-sources", "project",
        "--disable-slash-commands",
        "--exclude-dynamic-system-prompt-sections",
        "--no-session-persistence",
    ]
    if par["barrido_b_herramientas_excluidas"]:
        argv += ["--disallowedTools", ",".join(par["barrido_b_herramientas_excluidas"])]
    return argv


def construir_entorno(base: Mapping[str, str]) -> dict[str, str]:
    """Entorno MÍNIMO del hijo, construido desde cero: solo identidad del usuario + banderas fijas.

    Nunca hereda `ANTHROPIC_*` (con clave de API no cargan los conectores), `CLAUDECODE` ni `CLAUDE_CODE_*`
    de la sesión padre (la anidarían), ni secretos de otros sistemas.
    """
    entorno = {k: base[k] for k in ENTORNO_HEREDADO if base.get(k)}
    entorno.update(ENTORNO_FIJO)
    return entorno


# ---------------------------------------------------------------------------
# Ejecución del proceso (inyectable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResultadoProceso:
    codigo: int | None  # None si se mató por plazo
    salida: str
    error: str
    agotado: bool = False


Ejecutor = Callable[..., ResultadoProceso]


def ejecutor_subprocess(argv: Sequence[str], *, entorno: Mapping[str, str], cwd: Path, timeout_seg: int,
                        gracia_seg: int) -> ResultadoProceso:
    """Ejecutor real: `subprocess.Popen` con lista de argumentos, sin shell, sin stdin, en su propio grupo de procesos.

    Si pasa el plazo: SIGTERM al grupo, `gracia_seg` de espera y SIGKILL. Devuelve lo que alcanzó a salir.
    """
    try:
        proc = subprocess.Popen(list(argv), env=dict(entorno), cwd=str(cwd), stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                                errors="replace", start_new_session=True)
    except OSError as exc:
        raise ErrorUso(f"no se pudo lanzar {argv[0]!r}: {exc}") from exc
    try:
        salida, error = proc.communicate(timeout=timeout_seg)
        return ResultadoProceso(proc.returncode, salida or "", error or "")
    except subprocess.TimeoutExpired:
        _terminar_grupo(proc, gracia_seg)
        salida, error = proc.communicate()
        return ResultadoProceso(None, salida or "", error or "", agotado=True)


def _terminar_grupo(proc: "subprocess.Popen[str]", gracia_seg: int) -> None:
    for senal, espera in ((signal.SIGTERM, gracia_seg), (signal.SIGKILL, None)):
        try:
            os.killpg(proc.pid, senal)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=espera)
            return
        except subprocess.TimeoutExpired:
            continue


# ---------------------------------------------------------------------------
# Lectura del flujo `stream-json`
# ---------------------------------------------------------------------------

@dataclass
class Flujo:
    """Lo que interesa del flujo de eventos de un proceso `claude -p --output-format stream-json`."""

    version: str | None = None
    fuente_clave: str | None = None
    llamadas: list[dict[str, Any]] = field(default_factory=list)  # [{"id", "entrada"}] del conector, en orden
    resultados: dict[str, dict[str, Any]] = field(default_factory=dict)  # tool_use_id -> {"texto", "error"}
    final: dict[str, Any] | None = None  # evento `result`
    estado_limite: str | None = None  # último `rate_limit_event.status`
    lineas_ilegibles: int = 0


def _texto_resultado(contenido: Any) -> str:
    if isinstance(contenido, str):
        return contenido
    if isinstance(contenido, list):
        return "".join(b.get("text", "") for b in contenido if isinstance(b, dict) and b.get("type") == "text")
    return ""


def analizar_flujo(texto: str, herramienta: str) -> Flujo:
    """Lee las líneas JSON del flujo. Las ilegibles se cuentan y se ignoran; los decimales llegan como `Decimal`."""
    flujo = Flujo()
    vistas: set[str] = set()
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea:
            continue
        try:
            ev = json.loads(linea, parse_float=Decimal)
        except (ValueError, RecursionError):
            flujo.lineas_ilegibles += 1
            continue
        if not isinstance(ev, dict):
            flujo.lineas_ilegibles += 1
            continue
        tipo = ev.get("type")
        if tipo == "system" and ev.get("subtype") == "init":
            flujo.version = ev.get("claude_code_version") if isinstance(ev.get("claude_code_version"), str) else None
            flujo.fuente_clave = ev.get("apiKeySource") if isinstance(ev.get("apiKeySource"), str) else None
        elif tipo == "rate_limit_event":
            info = ev.get("rate_limit_info")
            if isinstance(info, dict) and isinstance(info.get("status"), str):
                flujo.estado_limite = info["status"]
        elif tipo in ("assistant", "user"):
            mensaje = ev.get("message")
            contenido = mensaje.get("content") if isinstance(mensaje, dict) else None
            if not isinstance(contenido, list):
                continue
            for bloque in contenido:
                if not isinstance(bloque, dict):
                    continue
                if tipo == "assistant" and bloque.get("type") == "tool_use" and bloque.get("name") == herramienta:
                    bid = bloque.get("id")
                    if isinstance(bid, str) and bid not in vistas and isinstance(bloque.get("input"), dict):
                        vistas.add(bid)
                        flujo.llamadas.append({"id": bid, "entrada": bloque["input"]})
                elif tipo == "user" and bloque.get("type") == "tool_result" and isinstance(bloque.get("tool_use_id"), str):
                    flujo.resultados[bloque["tool_use_id"]] = {
                        "texto": _texto_resultado(bloque.get("content")), "error": bool(bloque.get("is_error"))}
        elif tipo == "result":
            flujo.final = ev
    return flujo


class FalloConsulta(Exception):
    """Una consulta no produjo un crudo válido. `tipo` clasifica; `fatal` detiene toda la ejecución."""

    def __init__(self, tipo: str, mensaje: str, fatal: str | None = None) -> None:
        super().__init__(mensaje)
        self.tipo = tipo
        self.fatal = fatal  # None | "sesion" | "limite_uso" | "limite_meta" | "inyeccion_sospechada"


def _corto(texto: Any, largo: int = _MAX_MENSAJE) -> str:
    limpio = _RE_CONTROL.sub(" ", str(texto))
    limpio = " ".join(limpio.split())
    return limpio if len(limpio) <= largo else limpio[: largo - 1] + "…"


def _diferencias(entrada: Mapping[str, Any], consulta: Mapping[str, Any]) -> list[str]:
    """Diferencias entre lo que el modelo llamó y lo planificado. Vacía = la llamada es la correcta."""
    esperado = argumentos_herramienta(consulta)
    difs: list[str] = []
    for clave in CAMPOS_CONSULTA_HERRAMIENTA:
        real = entrada.get(clave)
        quiero = esperado.get(clave)
        if clave == "page_ids":
            real = sorted(str(x) for x in real) if isinstance(real, list) and real else None
            quiero = sorted(quiero) if quiero else None
        elif clave == "search_terms":
            real = real if isinstance(real, str) and real.strip() else None
        if real != quiero or (clave == "limit" and isinstance(entrada.get(clave), bool)):
            difs.append(f"{clave}: planificado {quiero!r}, llamado {real!r}")
    for clave in entrada:
        if clave not in CAMPOS_CONSULTA_HERRAMIENTA and clave not in CAMPOS_EXTRA_PERMITIDOS:
            difs.append(f"parámetro inesperado {clave!r}")
    return difs


def _es_limite_meta(texto: str) -> bool:
    """¿El texto de un ERROR del conector avisa de límite de tasa o bloqueo de Meta? (revisión m3)."""
    return _RE_LIMITE_META.search(texto) is not None


def _clasificar_fatal(flujo: Flujo, codigo: int | None, error: str) -> str | None:
    """Sesión caída o límite de uso: no tiene sentido seguir lanzando consultas."""
    final = flujo.final or {}
    estado_http = final.get("api_error_status")
    texto = f"{final.get('result', '')} {error}".lower()
    if estado_http == 401 or "not logged in" in texto or "/login" in texto or "invalid api key" in texto:
        return "sesion"
    if (estado_http == 429 or "usage limit" in texto or "rate limit" in texto or "limit reached" in texto
            or (flujo.estado_limite is not None and flujo.estado_limite not in ESTADOS_LIMITE_USO_OK)):
        return "limite_uso"
    return None


def extraer_crudo(proceso: ResultadoProceso, consulta: Mapping[str, Any], corrida_id: str, par: Mapping[str, Any],
                  capturado_en: str) -> tuple[dict[str, Any], Flujo]:
    """Del resultado de un proceso al crudo normalizado (CONTRATO §2, `ruta: "B"`), o `FalloConsulta`.

    Pasos: (1) el proceso terminó; (2) el modelo llamó UNA vez a la herramienta, con los argumentos del plan (más de
    una llamada = `inyeccion_sospechada`, fatal); (3) el conector devolvió un resultado sin error (un límite o bloqueo de
    Meta = `limite_meta`, fatal); (4) se decodifica `{"results": "<json>"}`; (5) `comun.validar_crudo` aprueba.
    El contenido de los anuncios sale del conector, nunca de texto escrito por el modelo.
    """
    flujo = analizar_flujo(proceso.salida, par["barrido_b_herramienta"])
    if proceso.agotado:
        raise FalloConsulta("timeout", f"el proceso superó el plazo de {par['barrido_b_timeout_consulta_seg']} s")
    if not flujo.llamadas:
        fatal = _clasificar_fatal(flujo, proceso.codigo, proceso.error)
        if fatal:
            raise FalloConsulta(fatal, _corto((flujo.final or {}).get("result") or proceso.error), fatal=fatal)
        if flujo.final is None:
            raise FalloConsulta("proceso", f"sin evento final (código {proceso.codigo}): {_corto(proceso.error)}")
        raise FalloConsulta("sin_llamada", "el modelo no llamó a la herramienta (¿conector sin autorizar?): "
                                           + _corto(flujo.final.get("result", "")))
    if len(flujo.llamadas) != 1:  # (aquí siempre ≥ 1: el caso 0 se resolvió arriba)
        raise FalloConsulta("inyeccion_sospechada", f"{len(flujo.llamadas)} llamadas al conector (se esperaba 1): un "
                            "texto de la Biblioteca pudo inducir llamadas extra", fatal="inyeccion_sospechada")
    llamada = flujo.llamadas[0]
    difs = _diferencias(llamada["entrada"], consulta)
    if difs:
        raise FalloConsulta("consulta_distinta", "la llamada no es la planificada: " + "; ".join(difs))
    resultado = flujo.resultados.get(llamada["id"])
    if resultado is None:
        raise FalloConsulta("sin_resultado", "la llamada no tiene resultado en el flujo")
    if resultado["error"]:
        if _es_limite_meta(resultado["texto"]):
            raise FalloConsulta("limite_meta", _corto(resultado["texto"]), fatal="limite_meta")
        raise FalloConsulta("error_conector", _corto(resultado["texto"]))
    try:
        externo = json.loads(resultado["texto"])
        interno = externo["results"] if isinstance(externo, dict) else None
        if isinstance(interno, str):
            interno = json.loads(interno)
        anuncios = interno["ads"]
        total = interno.get("estimated_total_count")
    except (ValueError, KeyError, TypeError, RecursionError):
        if _es_limite_meta(resultado["texto"]):  # un error de Meta que no llegó marcado como error
            raise FalloConsulta("limite_meta", _corto(resultado["texto"]), fatal="limite_meta") from None
        raise FalloConsulta("resultado_ilegible", "el resultado del conector no es {results: {ads, ...}}: "
                            + _corto(resultado["texto"])) from None
    if not isinstance(anuncios, list):
        raise FalloConsulta("resultado_ilegible", "`ads` no es una lista")
    doc = {
        "schema_version": comun.VERSION_ESQUEMA, "corrida_id": corrida_id, "qid": consulta["qid"],
        "consulta": {"search_terms": consulta["search_terms"], "countries": list(consulta["countries"]),
                     "ad_active_status": consulta["ad_active_status"], "limit": consulta["limit"],
                     "page_ids": consulta["page_ids"]},
        "capturado_en": capturado_en, "ruta": "B", "estimated_total_count": total, "ads": anuncios,
    }
    try:
        return comun.validar_crudo(doc, origen=f"{consulta['qid']} (ruta B)"), flujo
    except ErrorValidacion as exc:
        raise FalloConsulta("validacion", _corto(exc)) from None


# ---------------------------------------------------------------------------
# Registro de auditoría, bloqueo y reloj
# ---------------------------------------------------------------------------

def ruta_registro(corrida_id: str, raiz: Path) -> Path:
    return comun.dir_barrido(raiz) / "ruta_b" / f"{corrida_id}.jsonl"


def ruta_bloqueo(raiz_control: Path) -> Path:
    """Pestillo de Meta: mientras exista este archivo no corre nada. Solo una persona lo borra."""
    return comun.dir_barrido(raiz_control) / "ruta_b" / "BLOQUEO.json"


def _escribir_bloqueo(raiz_control: Path, corrida: str, qid: str, fallo: FalloConsulta, reloj: Reloj) -> None:
    try:
        comun.escribir_json_nuevo(ruta_bloqueo(raiz_control), {
            "motivo": fallo.tipo, "ts": comun.iso_z(reloj()), "corrida_id": corrida, "qid": qid,
            "error": _corto(fallo),
            "como_levantarlo": "una persona revisa el estado de la cuenta/conector en Meta y borra este archivo"})
    except ErrorUso:
        pass  # ya existía (otro proceso lo dejó primero): el pestillo ya está puesto


def _fmt_usd(d: Decimal) -> str:
    return format(d.quantize(_CENTAVOS_MICRO, rounding=ROUND_HALF_UP), "f")


def _leer_registro(ruta: Path, presupuesto_consulta: Decimal) -> list[dict[str, Any]]:
    """Líneas del registro. Una línea ilegible (escritura cortada) cuenta como un lanzamiento que gastó el tope."""
    if not ruta.is_file():
        return []
    lineas: list[dict[str, Any]] = []
    for linea in ruta.read_text(encoding="utf-8", errors="replace").splitlines():
        if not linea.strip():
            continue
        try:
            obj = json.loads(linea)
        except ValueError:
            obj = None
        if isinstance(obj, dict):
            lineas.append(obj)
        else:
            lineas.append({"tipo": "consulta", "estado": "ilegible", "ts": None,
                           "costo_usd": _fmt_usd(presupuesto_consulta)})
    return lineas


def _ts_o_none(valor: Any) -> datetime | None:
    try:
        return comun.parsear_z(valor)
    except ErrorValidacion:
        return None


def _gasto(lineas: Sequence[Mapping[str, Any]], presupuesto_consulta: Decimal) -> Decimal:
    total = Decimal(0)
    for ln in lineas:
        if ln.get("tipo") != "consulta":
            continue
        try:
            total += Decimal(str(ln.get("costo_usd")))
        except InvalidOperation:
            total += presupuesto_consulta
    return total


def _lanzamientos_del_dia(raiz: Path, hoy: str, presupuesto_consulta: Decimal) -> int:
    carpeta = comun.dir_barrido(raiz) / "ruta_b"
    if not carpeta.is_dir():
        return 0
    n = 0
    for archivo in sorted(carpeta.glob("*.jsonl")):
        for ln in _leer_registro(archivo, presupuesto_consulta):
            if ln.get("tipo") == "consulta" and (ln.get("ts") is None or str(ln["ts"]).startswith(hoy)):
                n += 1
    return n


@contextmanager
def _bloqueo(ruta: Path) -> Iterator[bool]:
    """`flock` exclusivo no bloqueante; se libera solo si el proceso muere. Rinde False si otro proceso lo tiene."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(ruta, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        yield True
    finally:
        os.close(fd)


def _como_reloj(ahora: datetime | Reloj | None) -> Reloj:
    if ahora is None:
        return comun.ahora_utc
    if callable(ahora):
        return ahora
    return lambda: ahora


# ---------------------------------------------------------------------------
# Orquestación
# ---------------------------------------------------------------------------

def _estado_de_archivos(consultas: Sequence[Mapping[str, Any]], carpeta: Path) -> dict[str, str]:
    """qid -> hecha | fallida | corrupta | pendiente (sin tocar nada)."""
    estados: dict[str, str] = {}
    for c in consultas:
        crudo = carpeta / f"{c['qid']}.json"
        error = carpeta / f"{c['qid']}.error.json"
        if crudo.exists():
            try:
                doc = comun.leer_crudo(crudo)
                estados[c["qid"]] = "hecha" if doc["qid"] == c["qid"] else "corrupta"
            except ErrorFabrica:
                estados[c["qid"]] = "corrupta"
        elif error.exists():
            estados[c["qid"]] = "fallida"
        else:
            estados[c["qid"]] = "pendiente"
    return estados


def ejecutar_plan(plan: Any, *, raiz: Path | None = None, ahora: datetime | Reloj | None = None,
                  ejecutor: Ejecutor | None = None, parametros: Mapping[str, Any] | None = None,
                  parametros_modelado: Mapping[str, Any] | None = None, claude_bin: str | None = None,
                  entorno_base: Mapping[str, str] | None = None, dormir: Callable[[float], None] = time.sleep,
                  reintentar_fallidas: bool = False, simular: bool = False,
                  raiz_control: Path | None = None) -> dict[str, Any]:
    """Ejecuta (o reanuda) el plan en la ruta B. Devuelve un resumen JSON-compatible (sin floats).

    - `raiz`: raíz de datos (pruebas: carpeta temporal). `ahora`: datetime fijo o función sin argumentos.
    - `raiz_control`: dónde viven los FRENOS (registro, tope diario, bloqueo de archivo, `PAUSA`, `BLOQUEO.json`, cwd).
      Por defecto es `raiz`; la CLI con `--vivo` pasa siempre `comun.RAIZ` para que `--raiz` no pueda reiniciarlos.
    - `ejecutor`: reemplaza el lanzamiento del proceso (pruebas). Por defecto `ejecutor_subprocess`.
    - `parametros` / `parametros_modelado`: ya cargados (pruebas); si no, se leen de sus archivos y fallan cerrado.
    - `simular=True` no lanza nada: devuelve lo que haría (consultas pendientes y un ejemplo de argumentos).
    Errores: ErrorLimite (plan mayor que el tope, parámetro faltante), ErrorBloqueado (`empresa/PAUSA` o
    `empresa/barrido/ruta_b/BLOQUEO.json`), ErrorUso.
    """
    raiz = Path(raiz) if raiz is not None else comun.RAIZ
    raiz_control = Path(raiz_control) if raiz_control is not None else raiz
    reloj = _como_reloj(ahora)
    par = normalizar_parametros(parametros) if parametros is not None else cargar_parametros_ruta_b()
    pm = parametros_modelado if parametros_modelado is not None else comun.cargar_parametros_modelado()
    if comun.CLAVE_TOPE_CONSULTAS not in pm:
        raise ErrorLimite(f"falta {comun.CLAVE_TOPE_CONSULTAS} en los parámetros del modelado (falla cerrado)")
    p = validar_plan(plan, pm[comun.CLAVE_TOPE_CONSULTAS])
    corrida, tope, consultas = p["corrida_id"], p["tope"], p["consultas"]
    if (raiz_control / "empresa" / "PAUSA").exists():
        raise ErrorBloqueado("existe empresa/PAUSA: no se lanza ninguna consulta")
    if ruta_bloqueo(raiz_control).exists():
        raise ErrorBloqueado(f"existe {ruta_bloqueo(raiz_control)}: Meta limitó o bloqueó la cuenta; una persona debe "
                             "revisarlo y borrar BLOQUEO.json antes de volver a lanzar consultas")
    carpeta = comun.dir_crudo(corrida, raiz)
    estados = _estado_de_archivos(consultas, carpeta)
    ruta_reg = ruta_registro(corrida, raiz_control)
    base_resumen = {"corrida_id": corrida, "consultas_plan": len(consultas), "registro": str(ruta_reg)}

    if simular:
        pendientes = [c["qid"] for c in consultas if estados[c["qid"]] == "pendiente"
                      or (reintentar_fallidas and estados[c["qid"]] == "fallida")]
        ejemplo = None
        if pendientes:
            c0 = next(c for c in consultas if c["qid"] == pendientes[0])
            bin_ = claude_bin or "claude"
            ejemplo = construir_argv(bin_, construir_prompt(c0, par), par)
        return {**base_resumen, "estado": "simulacion", "pendientes": pendientes,
                "hechas": sum(1 for e in estados.values() if e == "hecha"),
                "fallidas": [q for q, e in estados.items() if e == "fallida"],
                "corruptas": [q for q, e in estados.items() if e == "corrupta"], "ejemplo_argv": ejemplo}

    entorno_padre = os.environ if entorno_base is None else entorno_base
    if ejecutor is None:
        ejecutor = ejecutor_subprocess
        if claude_bin is None:
            claude_bin = shutil.which("claude", path=entorno_padre.get("PATH"))
            if claude_bin is None:
                raise ErrorUso("no se encontró `claude` en el PATH: indique la ruta con --claude-bin")
    if claude_bin is None:
        raise ErrorUso("falta claude_bin (ruta absoluta del ejecutable `claude`)")
    entorno = construir_entorno(entorno_padre)
    cwd = comun.dir_barrido(raiz_control) / "ruta_b" / "cwd"  # carpeta vacía y neutra: el hijo no ve el repositorio
    cwd.mkdir(parents=True, exist_ok=True)

    with _bloqueo(ruta_reg.with_suffix(".lock")) as libre:
        if not libre:
            return {**base_resumen, "estado": "ocupada", "motivo_parada": "otro proceso ejecuta esta corrida"}
        return _ejecutar_bloqueado(
            consultas, corrida, tope, raiz_control, carpeta, ruta_reg, par, reloj, ejecutor, claude_bin, entorno, cwd,
            dormir, reintentar_fallidas, base_resumen)


def _ejecutar_bloqueado(consultas, corrida, tope, raiz_control, carpeta, ruta_reg, par, reloj, ejecutor, claude_bin,
                        entorno, cwd, dormir, reintentar_fallidas, base_resumen) -> dict[str, Any]:
    presupuesto_consulta = par["barrido_b_presupuesto_consulta_usd"]
    estados = _estado_de_archivos(consultas, carpeta)
    avisos: list[str] = []
    if reintentar_fallidas:
        for c in consultas:
            if estados[c["qid"]] == "fallida":
                (carpeta / f"{c['qid']}.error.json").unlink()
                comun.anexar_jsonl(ruta_reg, {"tipo": "reintento_manual", "ts": comun.iso_z(reloj()),
                                              "corrida_id": corrida, "qid": c["qid"]})
                estados[c["qid"]] = "pendiente"

    registro = _leer_registro(ruta_reg, presupuesto_consulta)
    lanzadas_corrida = sum(1 for ln in registro if ln.get("tipo") == "consulta")
    errores_corrida = sum(1 for ln in registro if ln.get("tipo") == "consulta" and ln.get("estado") != "ok")
    gasto = _gasto(registro, presupuesto_consulta)
    lanzadas_dia = _lanzamientos_del_dia(raiz_control, comun.iso_z(reloj())[:10], presupuesto_consulta)
    ultimo_ts = next((t for t in (_ts_o_none(ln.get("ts")) for ln in reversed(registro)
                                  if ln.get("tipo") == "consulta") if t is not None), None)
    lanzadas_tanda = 0
    consecutivos = 0
    nuevas = 0
    motivo: str | None = None
    estado_final: str | None = None

    def motivo_parada() -> tuple[str, str] | None:
        if lanzadas_tanda >= par["barrido_b_consultas_por_tanda_max"]:
            return "tanda_completa", "se alcanzó el máximo de consultas de esta ejecución"
        if consecutivos >= par["barrido_b_errores_consecutivos_max"]:
            return "detenida_por_errores", f"{consecutivos} fallos seguidos"
        if errores_corrida >= par["barrido_b_errores_corrida_max"]:
            return "detenida_por_errores", f"{errores_corrida} intentos fallidos en la corrida"
        if lanzadas_corrida >= tope:
            return "tope_corrida", f"{lanzadas_corrida} lanzamientos = tope de la corrida ({tope})"
        if lanzadas_dia >= par["barrido_b_max_consultas_por_dia"]:
            return "tope_diario", f"{lanzadas_dia} lanzamientos hoy = tope diario"
        if gasto + presupuesto_consulta > par["barrido_b_presupuesto_corrida_usd"]:
            return "presupuesto_agotado", f"gastado {_fmt_usd(gasto)} USD de {par['barrido_b_presupuesto_corrida_usd']}"
        return None

    for c in consultas:
        if estados[c["qid"]] != "pendiente":
            continue
        error_final: FalloConsulta | None = None
        crudo: dict[str, Any] | None = None
        for intento in range(1, par["barrido_b_reintentos_por_consulta"] + 2):
            parada = motivo_parada()
            if parada:
                estado_final, motivo = parada
                break
            if ultimo_ts is not None:  # pausa mínima también entre tandas y reintentos
                espera = par["barrido_b_pausa_entre_consultas_seg"] - (reloj() - ultimo_ts).total_seconds()
                if espera > 0:
                    dormir(math.ceil(espera))
            lanzadas_tanda += 1
            lanzadas_corrida += 1
            lanzadas_dia += 1
            resultado = _lanzar(c, corrida, par, ejecutor, claude_bin, entorno, cwd, reloj)
            ultimo_ts = reloj()  # la pausa se mide desde el FIN del lanzamiento anterior
            gasto += resultado["costo"]
            comun.anexar_jsonl(ruta_reg, resultado["linea"] | {"intento": intento})
            if resultado["crudo"] is not None:
                crudo, error_final = resultado["crudo"], None
                avisos += [f"{c['qid']}: {a}" for a in resultado["avisos"]]
                break
            errores_corrida += 1
            error_final = resultado["fallo"]
            if error_final.fatal:
                break
        if crudo is not None:
            try:
                comun.escribir_json_nuevo(carpeta / f"{c['qid']}.json", crudo)
            except ErrorFabrica as exc:  # no debería ocurrir con el bloqueo; si ocurre, queda como fallo visible
                error_final = FalloConsulta("escritura", _corto(exc))
                errores_corrida += 1
            else:
                estados[c["qid"]] = "hecha"
                nuevas += 1
                consecutivos = 0
                continue
        if estado_final is not None and error_final is None:
            break  # se detuvo ANTES de lanzar esta consulta: sigue pendiente
        if error_final is not None:
            if error_final.fatal:
                estado_final = ESTADO_POR_FATAL[error_final.fatal]
                motivo = str(error_final)
                if error_final.fatal == "limite_meta":  # pestillo: no corre nada hasta que una persona lo borre
                    _escribir_bloqueo(raiz_control, corrida, c["qid"], error_final, reloj)
                if error_final.fatal in FATALES_CON_ERROR_DE_CONSULTA:
                    comun.escribir_json_nuevo(carpeta / f"{c['qid']}.error.json",
                                              {"qid": c["qid"], "error": f"{error_final.tipo}: {error_final}",
                                               "ts": comun.iso_z(reloj())})
                    estados[c["qid"]] = "fallida"
                break
            consecutivos += 1
            comun.escribir_json_nuevo(carpeta / f"{c['qid']}.error.json",
                                      {"qid": c["qid"], "error": f"{error_final.tipo}: {error_final}",
                                       "ts": comun.iso_z(reloj())})
            estados[c["qid"]] = "fallida"
            if estado_final is not None:
                break

    conteo = {e: sum(1 for v in estados.values() if v == e) for e in ("hecha", "fallida", "corrupta", "pendiente")}
    if estado_final is None:
        motivo_final = motivo_parada()
        if conteo["pendiente"] == 0:
            estado_final = "completa" if not (conteo["fallida"] or conteo["corrupta"]) else "completa_con_fallos"
        elif motivo_final:
            estado_final, motivo = motivo_final
        else:
            estado_final = "tanda_completa"
    comun.anexar_jsonl(ruta_reg, {"tipo": "parada", "ts": comun.iso_z(reloj()), "corrida_id": corrida,
                                  "estado": estado_final, "motivo": motivo, "lanzadas_tanda": lanzadas_tanda,
                                  "nuevas": nuevas})
    return {**base_resumen, "estado": estado_final, "motivo_parada": motivo, "hechas": conteo["hecha"],
            "nuevas": nuevas, "fallidas": [q for q, e in estados.items() if e == "fallida"],
            "corruptas": [q for q, e in estados.items() if e == "corrupta"], "pendientes": conteo["pendiente"],
            "lanzadas": lanzadas_tanda, "gasto_corrida_usd": _fmt_usd(gasto), "avisos": avisos}


def _lanzar(consulta: Mapping[str, Any], corrida: str, par: Mapping[str, Any], ejecutor: Ejecutor, claude_bin: str,
            entorno: Mapping[str, str], cwd: Path, reloj: Reloj) -> dict[str, Any]:
    """Un lanzamiento: ejecuta el proceso, extrae el crudo o clasifica el fallo, y arma la línea del registro."""
    argv = construir_argv(claude_bin, construir_prompt(consulta, par), par)
    inicio = reloj()
    proceso = ejecutor(argv, entorno=entorno, cwd=cwd, timeout_seg=par["barrido_b_timeout_consulta_seg"],
                       gracia_seg=par["barrido_b_gracia_seg"])
    fin = reloj()
    flujo = analizar_flujo(proceso.salida, par["barrido_b_herramienta"])
    crudo, fallo, avisos = None, None, []
    try:
        crudo, flujo = extraer_crudo(proceso, consulta, corrida, par, comun.iso_z(fin))
        avisos = comun.advertencias_crudo(crudo)
    except FalloConsulta as exc:
        fallo = exc
    final = flujo.final or {}
    costo = final.get("total_cost_usd")
    confiable = (isinstance(costo, (Decimal, int)) and not isinstance(costo, bool) and costo >= 0
                 and not proceso.agotado and proceso.codigo is not None)
    gasto = Decimal(costo) if confiable else par["barrido_b_presupuesto_consulta_usd"]  # sin dato fiable: el tope
    linea: dict[str, Any] = {
        "tipo": "consulta", "ts": comun.iso_z(fin), "corrida_id": corrida, "qid": consulta["qid"],
        "estado": "ok" if crudo is not None else "error",
        "error_tipo": None if fallo is None else fallo.tipo,
        "error": None if fallo is None else _corto(fallo),
        "costo_usd": _fmt_usd(gasto), "costo_confiable": confiable,
        "duracion_s": int((fin - inicio).total_seconds()),
        "duracion_ms": final.get("duration_ms") if isinstance(final.get("duration_ms"), int) else None,
        "turnos": final.get("num_turns") if isinstance(final.get("num_turns"), int) else None,
        "subtipo": final.get("subtype") if isinstance(final.get("subtype"), str) else None,
        "codigo": proceso.codigo, "llamadas_conector": len(flujo.llamadas),
        "denegaciones": len(final["permission_denials"]) if isinstance(final.get("permission_denials"), list) else None,
        "anuncios": None if crudo is None else len(crudo["ads"]),
        "estimated_total_count": None if crudo is None else crudo["estimated_total_count"],
        "version_claude": flujo.version, "fuente_clave": flujo.fuente_clave, "estado_limite_uso": flujo.estado_limite,
        "modelo": par["barrido_b_modelo"], "lineas_ilegibles": flujo.lineas_ilegibles,
    }
    return {"crudo": crudo, "fallo": fallo, "linea": linea, "costo": gasto, "avisos": avisos}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_SALIDA_POR_ESTADO = {
    "completa": 0, "tanda_completa": 0, "ocupada": 0, "simulacion": 0,
    "completa_con_fallos": 6, "detenida_por_errores": 6, "sesion_invalida": 6, "limite_uso": 6, "limite_meta": 6,
    "inyeccion_sospechada": 4,
    "tope_corrida": 5, "tope_diario": 5, "presupuesto_agotado": 5,
}


def _guardia_de_produccion(args: argparse.Namespace) -> None:
    """Con `FABRICA_ENTORNO=produccion` no existen las vías que dejan a quien invoca elegir sus propios frenos (M1)."""
    if args.raiz is None and args.parametros is None and args.parametros_modelado is None:
        return
    entorno = (os.environ.get("FABRICA_ENTORNO") or "desarrollo").strip()
    if entorno not in ENTORNOS:
        raise ErrorUso(f"FABRICA_ENTORNO inválido: se esperaba uno de {', '.join(ENTORNOS)}")
    if entorno == "produccion":
        raise ErrorUso("--raiz, --parametros y --parametros-modelado no existen con FABRICA_ENTORNO=produccion")


def main(argv: Sequence[str] | None = None, salida=None, **inyectados: Any) -> int:
    """Punto de entrada. `inyectados` (`ejecutor`, `ahora`, `dormir`, `entorno_base`) permiten probar sin `claude`."""
    salida = salida or sys.stdout
    parser = argparse.ArgumentParser(prog="python -m scripts.modelado.barrido.ruta_b",
                                     description="Ruta B del barrido: consultas de la Biblioteca con `claude -p`.")
    origen = parser.add_mutually_exclusive_group(required=True)
    origen.add_argument("--corrida", help="id de corrida; usa empresa/barrido/planes/<id>.json")
    origen.add_argument("--ultima", action="store_true", help="usa el plan más reciente de empresa/barrido/planes/")
    origen.add_argument("--plan", type=Path, help="ruta de un plan JSON")
    parser.add_argument("--vivo", action="store_true", help="lanza las consultas de verdad (sin esto: simulación)")
    parser.add_argument("--reintentar-fallidas", action="store_true", help="borra los *.error.json del plan y reintenta")
    parser.add_argument("--claude-bin", default=None, help="ruta absoluta de `claude` (obligatoria bajo launchd/cron)")
    parser.add_argument("--raiz", type=Path, default=None)
    parser.add_argument("--parametros", type=Path, default=None, help="parametros_ruta_b.propuesta.yaml alterno")
    parser.add_argument("--parametros-modelado", type=Path, default=None)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        _guardia_de_produccion(args)
        raiz = args.raiz or comun.RAIZ
        plan = args.plan
        if args.ultima:
            planes = sorted(p for p in (comun.dir_barrido(raiz) / "planes").glob("*.json")
                            if comun.corrida_id_valido(p.stem))
            if not planes:
                raise ErrorUso("no hay ningún plan en empresa/barrido/planes/ (¿se generó con plan.py?)")
            plan = planes[-1]  # los ids AAAA-MM-DD-<letra> ordenan por fecha y letra
        elif plan is None:
            if not comun.corrida_id_valido(args.corrida):
                raise ErrorUso(f"corrida_id inválido: {args.corrida!r}")
            plan = comun.dir_barrido(raiz) / "planes" / f"{args.corrida}.json"
        resumen = ejecutar_plan(
            plan, raiz=raiz, simular=not args.vivo, reintentar_fallidas=args.reintentar_fallidas,
            claude_bin=args.claude_bin,
            raiz_control=comun.RAIZ if args.vivo else None,  # --vivo: los frenos viven SIEMPRE en comun.RAIZ (M1)
            parametros=cargar_parametros_ruta_b(args.parametros),
            parametros_modelado=comun.cargar_parametros_modelado(args.parametros_modelado), **inyectados)
        print(json.dumps(resumen, ensure_ascii=False, indent=2), file=salida)
        return _SALIDA_POR_ESTADO.get(resumen["estado"], 1)
    except ErrorFabrica as exc:
        print(f"ERROR ({type(exc).__name__}): {exc}", file=sys.stderr)
        return exc.codigo_salida


if __name__ == "__main__":
    raise SystemExit(main())
