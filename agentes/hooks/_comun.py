"""Envoltorio fail-closed común a todos los hooks (docs/09-runtime-de-agentes.md §14.1) y ayudas
compartidas: clasificación de herramientas, rutas desde ``AGENT_RAIZ`` (nunca el directorio actual)
y anotación al spool de ``posttooluse_registro``. Ruta protegida: el agente no la edita.

Un hook roto (excepción, JSON ilegible, timeout interno) **siempre** sale con 2 (deny): H3 documenta
que un hook que falla «abierto» (código distinto de 0/2, o que se cuelga) deja pasar la acción, así
que aquí toda falla se traduce a 2 explícitamente, nunca se deja escapar sin código.
"""
from __future__ import annotations

import fnmatch
import json
import os
import signal
import sys
import threading
from pathlib import Path
from typing import Any, Callable, Mapping

import yaml

# Bootstrap de sys.path: los hooks se invocan como SCRIPT (``${CLAUDE_PROJECT_DIR}/.venv/bin/python
# .../pretooluse_gasto.py``), no con ``-m``; sin esto ``import engine`` fallaría. Nunca se usa el
# directorio actual (convenciones §1): la raíz es la carpeta que contiene este archivo, tres niveles
# arriba (agentes/hooks/_comun.py -> agentes/hooks -> agentes -> raíz).
_RAIZ_REPO = Path(__file__).resolve().parents[2]
if str(_RAIZ_REPO) not in sys.path:
    sys.path.insert(0, str(_RAIZ_REPO))

from engine import comun as motor  # noqa: E402  (tras el bootstrap de sys.path, a propósito)

__all__ = [
    "PLAZO_INTERNO_S_DEFECTO", "anotar_spool", "cargar_herramientas", "clasificar_herramienta",
    "construir_entrada_registro", "contiene_secreto", "ejecutar", "ejecutar_con_salida",
    "es_herramienta_de_creditos", "raiz_agente", "redactar", "ruta_dentro_de",
]

PLAZO_INTERNO_S_DEFECTO = 10  # menor que el timeout EXTERNO del hook (15 s, agentes/settings.propuesto.json)
_ARCHIVO_HERRAMIENTAS = Path(__file__).resolve().parent / "herramientas.yaml"


class _TiempoAgotado(Exception):
    """Señal interna: el manejador tardó más que su plazo propio."""


def _alarma(signum: int, frame: Any) -> None:  # noqa: ANN401, ARG001
    raise _TiempoAgotado("plazo interno del hook agotado")


def redactar(texto: str) -> str:
    """Quita secretos y datos personales de un texto antes de escribirlo a stderr o al spool."""
    return motor.ocultar_datos_sensibles(str(texto))


def ejecutar(manejador: Callable[[dict[str, Any]], str | None], *, plazo_s: int | None = None) -> None:
    """Lee JSON de ``stdin``, llama a ``manejador(datos)`` y traduce el resultado a un código de salida.

    ``manejador`` devuelve ``None`` (sin opinión: ``exit 0``) o un ``str`` con el motivo de bloqueo
    (a ``stderr``, ``exit 2``). Cualquier excepción —incluida entrada no JSON, un timeout interno
    (``plazo_s``, por defecto ``AGENT_HOOK_PLAZO_S`` o 10 s) o un error de programación— también
    sale con 2: nunca se deja pasar una acción por un fallo del hook.
    """
    plazo = plazo_s if plazo_s is not None else int(os.environ.get("AGENT_HOOK_PLAZO_S") or PLAZO_INTERNO_S_DEFECTO)
    usa_alarma = hasattr(signal, "SIGALRM") and threading.current_thread() is threading.main_thread()
    anterior = None
    try:
        if usa_alarma:
            anterior = signal.signal(signal.SIGALRM, _alarma)
            signal.alarm(max(1, plazo))
        try:
            datos = json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            raise ValueError(f"entrada no es JSON válido: {exc}") from exc
        if not isinstance(datos, dict):
            raise ValueError("la entrada del hook debe ser un objeto JSON")
        motivo = manejador(datos)
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - a propósito: falla cerrado ante CUALQUIER excepción
        sys.stderr.write(f"hook fail-closed: {type(exc).__name__}: {redactar(str(exc))}\n")
        sys.exit(2)
    finally:
        if usa_alarma:
            signal.alarm(0)
            if anterior is not None:
                signal.signal(signal.SIGALRM, anterior)
    if motivo:
        sys.stderr.write(redactar(str(motivo)) + "\n")
        sys.exit(2)
    sys.exit(0)


def ejecutar_con_salida(manejador: Callable[[dict[str, Any]], dict[str, Any] | None], *, plazo_s: int | None = None) -> None:
    """Como :func:`ejecutar`, para hooks que NO deniegan por ``stderr``/``exit 2`` sino que devuelven
    una decisión estructurada por ``stdout`` con ``exit 0`` (p. ej. ``Stop``:
    ``{"decision":"block","reason":...}``). Cualquier excepción sigue siendo ``exit 2`` (fail-closed);
    sin excepción, SIEMPRE ``exit 0`` (con o sin JSON de salida).
    """
    plazo = plazo_s if plazo_s is not None else int(os.environ.get("AGENT_HOOK_PLAZO_S") or PLAZO_INTERNO_S_DEFECTO)
    usa_alarma = hasattr(signal, "SIGALRM") and threading.current_thread() is threading.main_thread()
    anterior = None
    try:
        if usa_alarma:
            anterior = signal.signal(signal.SIGALRM, _alarma)
            signal.alarm(max(1, plazo))
        try:
            datos = json.load(sys.stdin)
        except json.JSONDecodeError as exc:
            raise ValueError(f"entrada no es JSON válido: {exc}") from exc
        if not isinstance(datos, dict):
            raise ValueError("la entrada del hook debe ser un objeto JSON")
        salida = manejador(datos)
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - a propósito: falla cerrado ante CUALQUIER excepción
        sys.stderr.write(f"hook fail-closed: {type(exc).__name__}: {redactar(str(exc))}\n")
        sys.exit(2)
    finally:
        if usa_alarma:
            signal.alarm(0)
            if anterior is not None:
                signal.signal(signal.SIGALRM, anterior)
    if salida:
        print(json.dumps(salida, ensure_ascii=False))
    sys.exit(0)


def raiz_agente(env: Mapping[str, str] | None = None) -> Path:
    """Raíz del repositorio para el hook: SIEMPRE ``AGENT_RAIZ`` (nunca el directorio actual).

    Sin ``AGENT_RAIZ`` o con una ruta que no existe, ``ValueError`` (fail-closed vía :func:`ejecutar`).
    """
    entorno = os.environ if env is None else env
    valor = (entorno.get("AGENT_RAIZ") or "").strip()
    if not valor:
        raise ValueError("falta AGENT_RAIZ: el hook no puede resolver rutas sin ella")
    ruta = Path(valor)
    if not ruta.is_dir():
        raise ValueError(f"AGENT_RAIZ no apunta a una carpeta existente: {valor}")
    return ruta.resolve()


def cargar_herramientas(ruta: Path | None = None) -> dict[str, Any]:
    """Carga ``agentes/hooks/herramientas.yaml`` (clasificación lectura/neutra/escritura/créditos)."""
    destino = ruta or _ARCHIVO_HERRAMIENTAS
    with open(destino, "r", encoding="utf-8") as f:
        datos = yaml.safe_load(f)
    if not isinstance(datos, dict):
        raise ValueError("herramientas.yaml ilegible: se esperaba un mapa")
    return datos


def _coincide_alguno(tool_name: str, patrones: Any) -> bool:
    return any(fnmatch.fnmatchcase(tool_name, str(p)) for p in (patrones or ()))


def clasificar_herramienta(tool_name: str, catalogo: Mapping[str, Any] | None = None) -> str:
    """Clasifica ``tool_name`` en ``"lectura"``, ``"neutra"`` o ``"escritura"`` (default fail-closed).

    Lo que no aparece en ``lectura`` ni en ``neutra`` es ``"escritura"`` (docs/09 §14.2): una
    herramienta nueva o mal escrita en el catálogo NUNCA cae en lectura por accidente.
    """
    cat = catalogo if catalogo is not None else cargar_herramientas()
    if not isinstance(tool_name, str) or not tool_name:
        return "escritura"
    if _coincide_alguno(tool_name, cat.get("lectura")):
        return "lectura"
    if _coincide_alguno(tool_name, cat.get("neutra")):
        return "neutra"
    return "escritura"


def es_herramienta_de_creditos(tool_name: str, catalogo: Mapping[str, Any] | None = None) -> bool:
    """¿``tool_name`` es una herramienta de generación que consume créditos (``generate_*``…)?"""
    cat = catalogo if catalogo is not None else cargar_herramientas()
    return isinstance(tool_name, str) and _coincide_alguno(tool_name, cat.get("creditos"))


def ruta_dentro_de(ruta: str | Path, base: Path) -> bool:
    """¿``ruta`` (resuelta) es ``base`` o está contenida en ella? Resuelve símlinks (sin asumir nada)."""
    try:
        candidato = Path(ruta).resolve()
    except (OSError, RuntimeError, ValueError):
        return False
    base_resuelta = base.resolve()
    return candidato == base_resuelta or base_resuelta in candidato.parents


def contiene_secreto(valor: Any) -> bool:
    """¿El volcado JSON de ``valor`` contiene algo que parezca una credencial (prefijos conocidos)?"""
    try:
        texto = json.dumps(valor, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        texto = str(valor)
    return motor.enmascarar_secretos(texto) != texto


def construir_entrada_registro(env: Mapping[str, str], *, evento: str, tool: str, tool_use_id: str | None,
                               entrada: Mapping[str, Any], resultado: str, duracion_ms: int | None = None,
                               costo_estimado_centavos: int | None = None) -> dict[str, Any]:
    """Línea de registro de una llamada de herramienta (docs/09 §14.4), sin ``tool_response`` ni contenido."""
    return {
        "ts": motor.iso_z(motor.ahora_utc()),
        "run_id": env.get("AGENT_RUN_ID"),
        "oferta_id": env.get("AGENT_OFERTA_ID"),
        "etapa": env.get("AGENT_ETAPA"),
        "rol": env.get("AGENT_ROL"),
        "agente": env.get("AGENT_NOMBRE"),
        "evento": evento,
        "tool": tool,
        "tool_use_id": tool_use_id,
        "entrada": dict(entrada),
        "resultado": resultado,
        "duracion_ms": duracion_ms,
        "costo_estimado_centavos": costo_estimado_centavos,
    }


def anotar_spool(env: Mapping[str, str], registro: Mapping[str, Any]) -> None:
    """Agrega UNA línea JSON a ``$AGENT_SPOOL`` (o ``empresa/registro.jsonl`` de ``AGENT_RAIZ`` si no
    está definida), con bloqueo de archivo y escritura atómica en append (``engine.comun.anexar_jsonl``).
    """
    raiz = raiz_agente(env)
    spool = (env.get("AGENT_SPOOL") or "").strip() or str(raiz / "empresa" / "registro.jsonl")
    motor.anexar_jsonl(Path(spool), registro)
