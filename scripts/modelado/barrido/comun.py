"""Base común del barrido por forma (D1, Modo D): errores, lector JSON estricto, parámetros, reloj,
rutas, escritura atómica y validación del archivo crudo. Contrato: scripts/modelado/barrido/CONTRATO.md §2, §5.

Principios (los mismos del repositorio):
  · La IA propone, el código dispone: todo texto de la Biblioteca (títulos, nombres) es dato NO confiable.
  · Falla cerrado: dato faltante o raro -> error con mensaje claro; jamás un valor por defecto inventado.
  · Sin `float` en lo persistido: enteros y cadenas decimales.
  · Ningún umbral fijo aquí: salen de `parametros_barrido.propuesta.yaml` y de
    `scripts/modelado/parametros_modelado.propuesta.yaml`. Lo único fijo son hechos del contrato o del
    conector (máx. 50 anuncios por llamada, formato de los identificadores).
Solo biblioteca estándar y PyYAML. Sin red.
"""

from __future__ import annotations

import errno
import hashlib
import json
import os
import re
import secrets
from collections.abc import Mapping
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from scripts.modelado import puntaje_modelar as _pm
from scripts.modelado.puntaje_modelar import (  # noqa: F401  (se reexportan: no se redefinen)
    ErrorBloqueado,
    ErrorFabrica,
    ErrorLimite,
    ErrorUso,
    ErrorValidacion,
)

__all__ = [
    "ErrorFabrica", "ErrorUso", "ErrorValidacion", "ErrorBloqueado", "ErrorLimite",
    "RAIZ", "raiz_repositorio", "dir_barrido", "dir_crudo",
    "leer_json", "escribir_json_nuevo", "anexar_jsonl",
    "CLAVES_BARRIDO", "CLAVES_TEXTO_CRUDO", "RUTA_PARAMETROS_BARRIDO", "RUTA_PARAMETROS_MODELADO",
    "cargar_parametros_barrido", "cargar_parametros_modelado",
    "validar_crudo", "leer_crudo", "advertencias_crudo", "listar_crudos",
    "corrida_id_valido", "qid_valido",
    "ahora_utc", "iso_z", "parsear_z",
    "VERSION_ESQUEMA", "LIMITE_MAX_CONECTOR", "RUTAS_VALIDAS",
]

# ---------------------------------------------------------------------------
# Constantes del contrato (hechos, no umbrales calibrables)
# ---------------------------------------------------------------------------

RAIZ: Path = Path(__file__).resolve().parents[3]
"""Raíz del repositorio (este archivo está en <raíz>/scripts/modelado/barrido/)."""

VERSION_ESQUEMA = "1.0.0"
LIMITE_MAX_CONECTOR = 50  # máx. de anuncios por llamada de `ads_library_search` (CONTRATO §0, §2)
RUTAS_VALIDAS = ("A", "B", "C", "D")
ESTADOS_ANUNCIO = ("ACTIVE", "INACTIVE", "ALL")  # vocabulario de `ad_active_status` de la Biblioteca

CAMPOS_CRUDO = ("schema_version", "corrida_id", "qid", "consulta", "capturado_en", "ruta",
                "estimated_total_count", "ads")
CAMPOS_CONSULTA = ("search_terms", "countries", "ad_active_status", "limit", "page_ids")
CAMPOS_ANUNCIO = ("id", "page_id", "page_name", "ad_creative_link_title", "ad_delivery_start_time",
                  "currency", "ad_snapshot_url")
CAMPOS_ANUNCIO_OPCIONALES = ("ad_creation_time",)  # «se permite omitir ad_creation_time» (CONTRATO §2)

QID_MAX_LARGO = 120          # el qid es nombre de archivo: <qid>.json / <qid>.error.json bajo el límite de 255
DIGITOS_MAX = 30             # largo máximo sensato de un id numérico de Meta (hoy 15-16 dígitos)
EPOCH_S_MAX_EXCLUSIVO = 10 ** 10  # 10 dígitos separa segundos de milisegundos (error clásico de transcripción)
PROFUNDIDAD_MAX = 64         # tope de anidación al serializar (evita estructuras cíclicas)

RUTA_PARAMETROS_BARRIDO: Path = RAIZ / "scripts" / "modelado" / "barrido" / "parametros_barrido.propuesta.yaml"
RUTA_PARAMETROS_MODELADO: Path = RAIZ / "scripts" / "modelado" / "parametros_modelado.propuesta.yaml"

_RE_CORRIDA = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z]")
_RE_QID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_RE_DIGITOS = re.compile(r"[0-9]+")
_RE_PAIS = re.compile(r"[A-Z]{2}")
_RE_MONEDA = re.compile(r"[A-Z]{3}")
_RE_ZULU = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z")
_RE_CONTROL = re.compile(r"[\x00-\x20\x7f-\x9f\u2028\u2029]")  # espacios y controles: no caben en una URL


# ---------------------------------------------------------------------------
# Rutas
# ---------------------------------------------------------------------------

def raiz_repositorio() -> Path:
    """Raíz del repositorio. Las pruebas y las CLI inyectan otra con el argumento `raiz=` de cada función."""
    return RAIZ


def dir_barrido(raiz: Path | None = None) -> Path:
    """`<raíz>/empresa/barrido`: carpeta de datos del barrido."""
    return (Path(raiz) if raiz is not None else RAIZ) / "empresa" / "barrido"


def dir_crudo(corrida_id: str, raiz: Path | None = None) -> Path:
    """`<raíz>/empresa/barrido/crudo/<corrida_id>`. Valida el id (evita rutas como `../x`)."""
    if not corrida_id_valido(corrida_id):
        raise ErrorUso(f"corrida_id inválido {_ver(corrida_id)}: se espera AAAA-MM-DD-<letra> (p. ej. 2026-11-06-a)")
    return dir_barrido(raiz) / "crudo" / corrida_id


# ---------------------------------------------------------------------------
# Identificadores
# ---------------------------------------------------------------------------

def corrida_id_valido(s: Any) -> bool:
    """`AAAA-MM-DD-<letra minúscula>` con fecha real de calendario (p. ej. «2026-11-06-a»)."""
    if not isinstance(s, str) or _RE_CORRIDA.fullmatch(s) is None:
        return False
    try:
        date(int(s[0:4]), int(s[5:7]), int(s[8:10]))
    except ValueError:
        return False
    return True


def qid_valido(s: Any) -> bool:
    """kebab-case ASCII (minúsculas, dígitos y guiones sueltos), no vacío, apto como nombre de archivo."""
    return isinstance(s, str) and len(s) <= QID_MAX_LARGO and _RE_QID.fullmatch(s) is not None


# ---------------------------------------------------------------------------
# Reloj
# ---------------------------------------------------------------------------

def ahora_utc() -> datetime:
    """Instante actual en UTC con zona, truncado a segundos (así `iso_z`/`parsear_z` son inversas exactas).

    Los módulos reciben `ahora=` para inyectar un reloj fijo en pruebas; esta función es solo el valor por defecto.
    """
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso_z(d: datetime) -> str:
    """datetime con zona -> `AAAA-MM-DDTHH:MM:SSZ` en UTC (descarta microsegundos). Sin zona = ErrorUso."""
    if not isinstance(d, datetime) or d.tzinfo is None or d.utcoffset() is None:
        raise ErrorUso("iso_z: se espera un datetime con zona horaria (UTC)")
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parsear_z(s: Any) -> datetime:
    """Inversa estricta de `iso_z`: solo `AAAA-MM-DDTHH:MM:SSZ`. Cualquier otra forma = ErrorValidacion."""
    if not isinstance(s, str) or _RE_ZULU.fullmatch(s) is None:
        raise ErrorValidacion(f"instante inválido {_ver(s)}: se espera UTC ISO-8601 con Z, p. ej. 2026-11-06T05:50:12Z")
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ErrorValidacion(f"instante inválido {_ver(s)}: {exc}") from exc


# ---------------------------------------------------------------------------
# Lectura y escritura de JSON
# ---------------------------------------------------------------------------

def _ver(valor: Any, largo: int = 60) -> str:
    """Representación corta y segura de un dato no confiable para mensajes de error."""
    texto = repr(valor)
    return texto if len(texto) <= largo else texto[: largo - 1] + "…"


def _rechazar_constante(nombre: str) -> Any:
    raise ErrorValidacion(f"JSON con constante no permitida: {nombre}")


def _sin_claves_repetidas(pares: list[tuple[str, Any]]) -> dict[str, Any]:
    objeto: dict[str, Any] = {}
    for clave, valor in pares:
        if clave in objeto:
            raise ErrorValidacion(f"JSON con clave repetida: {_ver(clave)}")
        objeto[clave] = valor
    return objeto


def leer_json(ruta: Path) -> Any:
    """Lee un JSON estricto: UTF-8 válido, sin NaN/Infinity, sin claves repetidas.

    Los decimales con punto llegan como `Decimal` (exactos); los validadores de cada módulo los rechazan donde
    el contrato pide entero o cadena. Errores: ErrorUso si no se puede leer; ErrorValidacion si no es JSON válido.
    """
    ruta = Path(ruta)
    try:
        crudo = ruta.read_bytes()
    except OSError as exc:
        raise ErrorUso(f"no se pudo leer {ruta}: {exc}") from exc
    try:
        texto = crudo.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ErrorValidacion(f"{ruta}: no es UTF-8 válido ({exc})") from exc
    try:
        return json.loads(texto, parse_float=Decimal, parse_constant=_rechazar_constante,
                          object_pairs_hook=_sin_claves_repetidas)
    except json.JSONDecodeError as exc:
        raise ErrorValidacion(f"{ruta}: JSON inválido ({exc})") from exc
    except ErrorFabrica as exc:
        raise type(exc)(f"{ruta}: {exc}") from exc
    except (RecursionError, ValueError) as exc:
        raise ErrorValidacion(f"{ruta}: JSON no procesable ({type(exc).__name__})") from exc


def _limpiar(valor: Any, camino: str, profundidad: int = 0) -> Any:
    """Copia de `valor` apta para persistir (dict/list/str/int/bool/None) o ErrorValidacion con el camino exacto."""
    if profundidad > PROFUNDIDAD_MAX:
        raise ErrorValidacion(f"{camino}: anidación excesiva o estructura cíclica")
    if valor is None or isinstance(valor, (bool, int)):
        return valor
    if isinstance(valor, (float, Decimal)):
        raise ErrorValidacion(
            f"{camino}: {type(valor).__name__} no se persiste (incluye NaN/Infinity): use entero o cadena decimal")
    if isinstance(valor, str):
        try:
            valor.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ErrorValidacion(f"{camino}: texto con sustitutos sueltos (no es UTF-8 válido)") from exc
        return valor
    if isinstance(valor, (list, tuple)):
        return [_limpiar(v, f"{camino}[{i}]", profundidad + 1) for i, v in enumerate(valor)]
    if isinstance(valor, Mapping):
        salida: dict[str, Any] = {}
        for clave, v in valor.items():
            if not isinstance(clave, str):
                raise ErrorValidacion(f"{camino}: clave no textual {_ver(clave)} ({type(clave).__name__})")
            salida[clave] = _limpiar(v, f"{camino}.{clave}", profundidad + 1)
        return salida
    raise ErrorValidacion(f"{camino}: tipo no serializable {type(valor).__name__}")


def _serializar(doc: Any, *, compacto: bool) -> str:
    limpio = _limpiar(doc, "$")
    try:
        if compacto:
            return json.dumps(limpio, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        return json.dumps(limpio, ensure_ascii=False, indent=2, allow_nan=False)
    except (ValueError, RecursionError) as exc:
        raise ErrorValidacion(f"no se pudo serializar a JSON: {exc}") from exc


def _sincronizar_directorio(carpeta: Path) -> None:
    """Best effort: hace durable la entrada de directorio (no todas las plataformas lo permiten)."""
    try:
        fd = os.open(carpeta, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)  # no seguir un enlace simbólico en el último componente (POSIX)


def _base_de_confianza(carpeta: Path, raiz: Path | None) -> Path:
    """Raíz desde la que se vigilan los enlaces simbólicos (lo que cuelga de ella; lo de arriba no se juzga).

    Prioridad: `raiz` explícita (la ruta debe colgar de ella) > la raíz del repositorio si la ruta cuelga de ella >
    el padre del `empresa` más externo del camino (todo dato del barrido vive en `<raíz>/empresa/barrido/...`) >
    la carpeta misma (solo se comprueba el padre inmediato). Así `/var -> /private/var` (macOS) o una raíz que sea
    un enlace no dan falsos positivos, y una carpeta de corrida enlazada fuera de la raíz sí se detecta.
    """
    if raiz is not None:
        base = Path(os.path.abspath(raiz))
        if carpeta != base and base not in carpeta.parents:
            raise ErrorUso(f"{carpeta} queda fuera de la raíz {base}")
        return base
    if carpeta == RAIZ or RAIZ in carpeta.parents:
        return RAIZ
    for ancestro in (*reversed(carpeta.parents), carpeta):
        if ancestro.name == "empresa":
            return ancestro.parent
    return carpeta.parent


def _rechazar_enlaces(carpeta: Path, raiz: Path | None = None) -> None:
    """ErrorUso si algún componente de `carpeta` por debajo de la raíz de confianza es un enlace simbólico (m8).

    Un enlace puede sacar una escritura (o una lectura) fuera de `empresa/barrido`: p. ej. `crudo/2026-11-06-b`
    apuntando a otra carpeta. Comprueba también enlaces colgantes. `carpeta` ya debe venir normalizada (sin `..`).
    """
    carpeta = Path(os.path.abspath(carpeta))
    base = _base_de_confianza(carpeta, raiz)
    actual = base
    for parte in carpeta.relative_to(base).parts:
        actual = actual / parte
        if actual.is_symlink():
            raise ErrorUso(f"{actual} es un enlace simbólico: no se lee ni se escribe a través de enlaces "
                           "(podrían sacar el dato de la raíz del barrido)")


def escribir_json_nuevo(ruta: Path, doc: Any, *, raiz: Path | None = None) -> None:
    """Escribe `doc` como JSON (UTF-8, `ensure_ascii=False`, `indent=2`, salto de línea final), atómico y SIN sobrescribir.

    Se serializa y valida ANTES de tocar el disco (float/Decimal/NaN/claves no textuales = ErrorValidacion y no se crea
    nada). Luego: archivo temporal en la misma carpeta (`O_CREAT|O_EXCL|O_NOFOLLOW`) + fsync + publicación exclusiva
    (`os.link`, que falla si el destino existe aunque aparezca en medio de la operación; si el sistema de archivos no
    admite enlaces duros, cae a `os.replace` tras volver a comprobar). Crea las carpetas que falten. Existente = ErrorUso.

    Enlaces simbólicos (m8): antes de escribir se recorren los componentes de la carpeta destino por debajo de la raíz
    de confianza (`raiz`, o la del repositorio, o el padre de `empresa`; ver `_base_de_confianza`) y cualquier enlace
    simbólico es ErrorUso. La ruta se normaliza antes (`..` resuelto en el texto) y eso es lo que se comprueba y escribe.
    Limitación conocida: entre la comprobación y la escritura otro proceso con permiso de escritura podría cambiar un
    componente por un enlace (carrera); el temporal con `O_NOFOLLOW|O_EXCL` y la publicación con `os.link` la acotan.
    """
    ruta = Path(os.path.abspath(ruta))
    datos = (_serializar(doc, compacto=False) + "\n").encode("utf-8")
    _rechazar_enlaces(ruta.parent, raiz)
    if os.path.lexists(ruta):
        raise ErrorUso(f"{ruta} ya existe: no se sobrescriben artefactos (use otro nombre)")
    temporal = ruta.parent / f".{ruta.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp"
    existe = False
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        # respeta la umask del usuario; no sigue enlaces en el último componente
        fd = os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW, 0o666)
        with os.fdopen(fd, "wb") as f:
            f.write(datos)
            f.flush()
            os.fsync(f.fileno())
        try:
            os.link(temporal, ruta)
        except FileExistsError:
            existe = True
        except OSError:  # sin enlaces duros en este sistema de archivos
            if os.path.lexists(ruta):
                existe = True
            else:
                os.replace(temporal, ruta)
        if not existe:
            _sincronizar_directorio(ruta.parent)
    except OSError as exc:
        raise ErrorUso(f"no se pudo escribir {ruta}: {exc}") from exc
    finally:
        try:
            os.unlink(temporal)
        except OSError:
            pass
    if existe:
        raise ErrorUso(f"{ruta} ya existe: no se sobrescriben artefactos (use otro nombre)")


def anexar_jsonl(ruta: Path, obj: Mapping, *, raiz: Path | None = None) -> None:
    """Anexa `obj` como UNA línea JSON compacta a `ruta` (la crea si falta, con sus carpetas).

    Mismas reglas de contenido que `escribir_json_nuevo`. Los separadores de línea de Unicode (U+0085, U+2028,
    U+2029) se escapan para que ningún lector con `splitlines()` parta un registro. Si el archivo no termina en
    salto de línea (escritura anterior truncada), se agrega uno antes: el registro nuevo nunca se pega a uno roto.
    Enlaces simbólicos (m8): mismas reglas que `escribir_json_nuevo` para la carpeta, y el archivo se abre con
    `O_NOFOLLOW` (si `ruta` es un enlace, ErrorUso y no se toca el destino del enlace).
    """
    ruta = Path(os.path.abspath(ruta))
    if not isinstance(obj, Mapping):
        raise ErrorValidacion(f"anexar_jsonl: se espera un objeto, llegó {type(obj).__name__}")
    linea = _serializar(obj, compacto=True)
    for raro, escape in (("\u0085", "\\u0085"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        linea = linea.replace(raro, escape)
    carga = (linea + "\n").encode("utf-8")
    _rechazar_enlaces(ruta.parent, raiz)
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(ruta, os.O_RDWR | os.O_APPEND | os.O_CREAT | _O_NOFOLLOW, 0o666)
        try:
            f = os.fdopen(fd, "a+b")
        except BaseException:
            os.close(fd)
            raise
        with f:
            f.seek(0, os.SEEK_END)
            if f.tell() > 0:
                f.seek(-1, os.SEEK_END)
                if f.read(1) != b"\n":
                    carga = b"\n" + carga
            f.write(carga)  # O_APPEND: escribe siempre al final
            f.flush()
            os.fsync(f.fileno())
    except OSError as exc:
        pista = " (es un enlace simbólico)" if exc.errno == errno.ELOOP else ""
        raise ErrorUso(f"no se pudo anexar a {ruta}: {exc}{pista}") from exc


# ---------------------------------------------------------------------------
# Parámetros (YAML -> valores tipados; falla cerrado)
# ---------------------------------------------------------------------------

CLAVES_BARRIDO = (
    "barrido_limite_por_consulta",
    "barrido_paises_origen",
    "barrido_pasadas_max",
    "barrido_titulos_por_pagina_max",
    "barrido_paginas_por_lote_etiquetado",
    "barrido_partir_si_total_supera",
    "memoria_ventana_min_dias",
    "barrido_agentes_paralelos_max",
    "barrido_exportador_monedas_pais",
    "barrido_consultas_por_agente_max",
)  # CONTRATO §6: el mínimo exigido; el YAML puede traer más y se devuelven igual (validadas contra su `rango`)

CLAVES_TEXTO_CRUDO = ("barrido_texto_max_caracteres", "barrido_hosts_snapshot")
"""Revisión de seguridad m7: las exige `validar_crudo` (ErrorLimite si faltan). NO están en `CLAVES_BARRIDO` a propósito:
así un YAML anterior con solo las 10 claves del contrato sigue cargando (p. ej. el fixture de ingesta) y el fallo cerrado
ocurre justo al aceptar un crudo, que es donde importan."""

CLAVE_TOPE_CONSULTAS = "modelado_max_consultas_por_corrida"  # vive en parametros_modelado.propuesta.yaml

_RE_HOST = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?")
HOST_MAX_LARGO = 253  # largo máximo de un nombre DNS (RFC 1035): hecho del protocolo, no un umbral calibrable


def _cargar_entradas(ruta: Path) -> dict[str, Mapping[str, Any]]:
    """Lee el YAML y devuelve {clave: entrada} con las entradas que tienen `valor`.

    Acepta el estilo de `empresa/parametros.yaml` (`grupos.<grupo>.<clave>`, se juntan todos los grupos) y el plano
    (`<clave>` en la raíz). Errores: ErrorLimite si no se puede leer; ErrorValidacion si el YAML es inválido.
    """
    import yaml  # PyYAML está en requirements.txt de la raíz

    try:
        datos = yaml.safe_load(Path(ruta).read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErrorLimite(f"no se pudo leer el archivo de parámetros {ruta}: {exc} "
                          "(falla cerrado: sin parámetros aprobados no se asume ningún valor)") from exc
    except (yaml.YAMLError, UnicodeDecodeError) as exc:
        raise ErrorValidacion(f"{ruta}: YAML inválido ({exc})") from exc
    if not isinstance(datos, dict):
        raise ErrorValidacion(f"{ruta}: se esperaba un mapa de parámetros")
    if "grupos" in datos:
        grupos = datos["grupos"]
        if not isinstance(grupos, dict):
            raise ErrorValidacion(f"{ruta}: «grupos» debe ser un mapa")
        origenes: list[Mapping[str, Any]] = [g for g in grupos.values() if isinstance(g, dict)]
    else:
        origenes = [datos]
    entradas: dict[str, Mapping[str, Any]] = {}
    for grupo in origenes:
        for clave, entrada in grupo.items():
            if isinstance(entrada, dict) and "valor" in entrada:
                if clave in entradas:
                    raise ErrorValidacion(f"{ruta}: parámetro repetido en dos grupos: {clave}")
                entradas[str(clave)] = entrada
    return entradas


def _tipo_entero(clave: str, valor: Any, minimo: int, maximo: int | None = None) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErrorValidacion(f"{clave}: se esperaba un entero, llegó {type(valor).__name__} {_ver(valor)}")
    if valor < minimo or (maximo is not None and valor > maximo):
        permitido = f"≥ {minimo}" if maximo is None else f"[{minimo}, {maximo}]"
        raise ErrorLimite(f"{clave}: {valor} fuera de lo permitido ({permitido})")
    return valor


def _tipo_paises(clave: str, valor: Any) -> list[str]:
    if not isinstance(valor, list) or not valor:
        raise ErrorValidacion(f"{clave}: se esperaba una lista no vacía de países ISO-2")
    for p in valor:
        if not (isinstance(p, str) and _RE_PAIS.fullmatch(p)):
            pista = " (entrecomille los códigos: en YAML «NO» se lee como falso)" if isinstance(p, bool) else ""
            raise ErrorValidacion(f"{clave}: país ISO-2 en mayúsculas esperado, llegó {_ver(p)}{pista}")
    if len(set(valor)) != len(valor):
        raise ErrorValidacion(f"{clave}: países repetidos")
    return list(valor)


def _tipo_monedas(clave: str, valor: Any) -> dict[str, str]:
    if not isinstance(valor, dict) or not valor:
        raise ErrorValidacion(f"{clave}: se esperaba un mapa moneda->país no vacío (p. ej. BRL: BR)")
    salida: dict[str, str] = {}
    for moneda, pais in valor.items():
        if not (isinstance(moneda, str) and _RE_MONEDA.fullmatch(moneda)):
            raise ErrorValidacion(f"{clave}: moneda de 3 letras mayúsculas esperada, llegó {_ver(moneda)}")
        if not (isinstance(pais, str) and _RE_PAIS.fullmatch(pais)):
            pista = " (entrecomille los códigos: en YAML «NO» se lee como falso)" if isinstance(pais, bool) else ""
            raise ErrorValidacion(f"{clave}[{moneda}]: país ISO-2 en mayúsculas esperado, llegó {_ver(pais)}{pista}")
        salida[moneda] = pais
    return salida


def _tipo_hosts(clave: str, valor: Any) -> list[str]:
    """Lista no vacía de nombres de host DNS en minúsculas ASCII, sin esquema, puerto, ruta ni repetidos."""
    if isinstance(valor, tuple):
        valor = list(valor)
    if not isinstance(valor, list) or not valor:
        raise ErrorValidacion(f"{clave}: se esperaba una lista no vacía de hosts (p. ej. www.facebook.com)")
    for h in valor:
        if not (isinstance(h, str) and h.isascii() and len(h) <= HOST_MAX_LARGO and _RE_HOST.fullmatch(h)):
            raise ErrorValidacion(f"{clave}: host inválido {_ver(h)}: solo nombre DNS en minúsculas "
                                  "(sin esquema, puerto, ruta ni mayúsculas)")
    if len(set(valor)) != len(valor):
        raise ErrorValidacion(f"{clave}: hosts repetidos")
    return list(valor)


def _sin_float(clave: str, valor: Any) -> None:
    if isinstance(valor, float):
        raise ErrorValidacion(f"{clave}: use entero o cadena decimal, no float ({_ver(valor)})")
    if isinstance(valor, list):
        for v in valor:
            _sin_float(clave, v)
    elif isinstance(valor, dict):
        for v in valor.values():
            _sin_float(clave, v)


def _par_rango(clave: str, rango: Any) -> tuple[Decimal, Decimal] | None:
    if rango is None:
        return None
    if not (isinstance(rango, (list, tuple)) and len(rango) == 2):
        raise ErrorValidacion(f"{clave}: «rango» debe ser [mínimo, máximo]")
    extremos = []
    for e in rango:
        if isinstance(e, bool) or isinstance(e, float) or not isinstance(e, (int, str)):
            raise ErrorValidacion(f"{clave}: extremo de «rango» inválido {_ver(e)} (entero o cadena decimal)")
        try:
            extremos.append(Decimal(e if isinstance(e, int) else e.strip()))
        except InvalidOperation as exc:
            raise ErrorValidacion(f"{clave}: extremo de «rango» inválido {_ver(e)}") from exc
    if not all(e.is_finite() for e in extremos) or extremos[0] > extremos[1]:
        raise ErrorValidacion(f"{clave}: «rango» inconsistente {rango!r}")
    return extremos[0], extremos[1]


def _tipo_generico(clave: str, valor: Any, numerico: bool) -> Any:
    """Parámetros que el contrato permite agregar: se conservan tal cual (sin float); decimales como `Decimal`."""
    _sin_float(clave, valor)
    if numerico and isinstance(valor, str):
        try:
            d = Decimal(valor.strip())
        except InvalidOperation as exc:
            raise ErrorValidacion(f"{clave}: «{valor}» no es un decimal") from exc
        if not d.is_finite():
            raise ErrorValidacion(f"{clave}: valor no finito")
        return d
    return valor


def _comprobar_rango(clave: str, valor: Any, rango: Any) -> None:
    """Falla cerrado (ErrorLimite) si un valor numérico sale de su `rango`. Colecciones y textos no se comparan."""
    par = _par_rango(clave, rango)
    if par is None or isinstance(valor, bool) or not isinstance(valor, (int, Decimal)):
        return
    lo, hi = par
    if not lo <= Decimal(valor) <= hi:
        raise ErrorLimite(f"{clave}: {valor} fuera del rango aprobado [{lo}, {hi}] (falla cerrado)")


def _tipar_barrido(clave: str, valor: Any, rango: Any) -> Any:
    if clave == "barrido_limite_por_consulta":
        return _tipo_entero(clave, valor, 1, LIMITE_MAX_CONECTOR)
    if clave == "barrido_pasadas_max":
        return _tipo_entero(clave, valor, 1, 3)  # pasadas 1, 2 y 3 (CONTRATO §3)
    if clave in ("barrido_titulos_por_pagina_max", "barrido_paginas_por_lote_etiquetado",
                 "barrido_partir_si_total_supera", "memoria_ventana_min_dias",
                 "barrido_agentes_paralelos_max", "barrido_consultas_por_agente_max"):
        return _tipo_entero(clave, valor, 1)
    if clave == "barrido_texto_max_caracteres":
        return _tipo_entero(clave, valor, 1)
    if clave == "barrido_paises_origen":
        return _tipo_paises(clave, valor)
    if clave == "barrido_exportador_monedas_pais":
        return _tipo_monedas(clave, valor)
    if clave == "barrido_hosts_snapshot":
        return _tipo_hosts(clave, valor)
    return _tipo_generico(clave, valor, _par_rango(clave, rango) is not None)


def cargar_parametros_barrido(ruta: Path | None = None) -> dict[str, Any]:
    """Carga `parametros_barrido.propuesta.yaml` (o `ruta`) y devuelve {clave: valor ya tipado}.

    Formato de cada entrada: {valor, unidad, hipotesis, fuente, ultima_calibracion, rango}. Falla cerrado:
    ErrorLimite (5) si no se puede leer el archivo, falta alguna de `CLAVES_BARRIDO`, un valor es nulo o sale de su
    `rango`; ErrorValidacion (3) si un valor tiene tipo inválido (float, país mal escrito, ...). Las claves extra
    que traiga el YAML también se validan contra su `rango` y se devuelven. Enteros -> `int`, decimales en cadena
    -> `Decimal`, países -> lista ISO-2, monedas -> {moneda: país}. El `rango` solo se compara en valores numéricos.
    """
    ruta = Path(ruta) if ruta is not None else RUTA_PARAMETROS_BARRIDO
    entradas = _cargar_entradas(ruta)
    faltan = [c for c in CLAVES_BARRIDO if c not in entradas or entradas[c].get("valor") is None]
    if faltan:
        raise ErrorLimite(f"faltan parámetros del barrido en {ruta}: {', '.join(faltan)} "
                          "(falla cerrado: no se asume ningún valor)")
    parametros: dict[str, Any] = {}
    for clave, entrada in entradas.items():
        if entrada["valor"] is None:
            raise ErrorLimite(f"{clave}: sin valor en {ruta} (falla cerrado)")
        valor = _tipar_barrido(clave, entrada["valor"], entrada.get("rango"))
        _comprobar_rango(clave, valor, entrada.get("rango"))
        parametros[clave] = valor
    return parametros


_CACHE_PARAMETROS: dict[tuple[str, str], dict[str, Any]] = {}  # una sola entrada: (ruta, sha256 del contenido)


def _parametros_por_defecto() -> dict[str, Any]:
    """Parámetros del barrido en `RUTA_PARAMETROS_BARRIDO` para `validar_crudo(par=None)`; ErrorLimite si no se leen.

    Se cachean por contenido (SHA-256), no por fecha: si el YAML cambia entre dos llamadas, la segunda lo ve.
    """
    ruta = Path(RUTA_PARAMETROS_BARRIDO)
    try:
        contenido = ruta.read_bytes()
    except OSError as exc:
        raise ErrorLimite(f"no se pudo leer el archivo de parámetros {ruta}: {exc} "
                          "(falla cerrado: sin parámetros aprobados no se valida ningún crudo)") from exc
    clave = (str(ruta), hashlib.sha256(contenido).hexdigest())
    if clave not in _CACHE_PARAMETROS:
        parametros = cargar_parametros_barrido(ruta)
        _CACHE_PARAMETROS.clear()
        _CACHE_PARAMETROS[clave] = parametros
    return _CACHE_PARAMETROS[clave]


def _limites_de_texto(par: Mapping[str, Any] | None) -> tuple[int, frozenset[str]]:
    """(tope de caracteres por texto, hosts permitidos de `ad_snapshot_url`) desde `par` o, sin `par`, desde el YAML por defecto.

    Falla cerrado: ErrorLimite si falta o es nulo algún parámetro de `CLAVES_TEXTO_CRUDO`; ErrorUso si `par` no es un mapa.
    """
    if par is None:
        par = _parametros_por_defecto()
    elif not isinstance(par, Mapping):
        raise ErrorUso(f"par: se esperaba el dict de cargar_parametros_barrido, llegó {type(par).__name__}")
    faltan = [c for c in CLAVES_TEXTO_CRUDO if par.get(c) is None]
    if faltan:
        raise ErrorLimite(f"faltan parámetros para validar el crudo: {', '.join(faltan)} "
                          "(falla cerrado: no se asume ningún tope ni host)")
    maximo = _tipo_entero(CLAVES_TEXTO_CRUDO[0], par[CLAVES_TEXTO_CRUDO[0]], 1)
    hosts = _tipo_hosts(CLAVES_TEXTO_CRUDO[1], par[CLAVES_TEXTO_CRUDO[1]])
    return maximo, frozenset(hosts)


def cargar_parametros_modelado(ruta: Path | None = None) -> dict[str, Any]:
    """Parámetros `modelado_*`: reusa `puntaje_modelar.cargar_parametros` (35 claves, int/Decimal) y agrega
    `modelado_max_consultas_por_corrida` (int; es el tope de consultas del plan y no lo normaliza puntaje_modelar).

    Por defecto lee `scripts/modelado/parametros_modelado.propuesta.yaml` (la propuesta aún no está integrada en
    `empresa/parametros.yaml`). ErrorLimite si falta cualquier clave o el archivo; ErrorValidacion si un valor es inválido.
    """
    ruta = Path(ruta) if ruta is not None else RUTA_PARAMETROS_MODELADO
    parametros = _pm.cargar_parametros(ruta)
    entradas = _cargar_entradas(ruta)
    entrada = entradas.get(CLAVE_TOPE_CONSULTAS)
    if entrada is None or entrada.get("valor") is None:
        raise ErrorLimite(f"falta el parámetro {CLAVE_TOPE_CONSULTAS} en {ruta} (falla cerrado)")
    tope = _tipo_entero(CLAVE_TOPE_CONSULTAS, entrada["valor"], 1)
    _comprobar_rango(CLAVE_TOPE_CONSULTAS, tope, entrada.get("rango"))
    parametros[CLAVE_TOPE_CONSULTAS] = tope
    return parametros


# ---------------------------------------------------------------------------
# Validación del archivo crudo (CONTRATO §2). Todas las reglas son fatales (ErrorValidacion, código 3).
# ---------------------------------------------------------------------------

def _fallo(origen: str, campo: str, mensaje: str) -> ErrorValidacion:
    prefijo = f"{origen}: " if origen else ""
    return ErrorValidacion(f"{prefijo}{campo}: {mensaje}")


def _claves_exactas(valor: Any, campo: str, obligatorias: tuple[str, ...], origen: str,
                    opcionales: tuple[str, ...] = ()) -> dict[str, Any]:
    if not isinstance(valor, dict):
        raise _fallo(origen, campo, f"se esperaba un objeto, llegó {type(valor).__name__}")
    faltan = [k for k in obligatorias if k not in valor]
    sobran = sorted(str(k) for k in valor if k not in obligatorias and k not in opcionales)
    if faltan:
        raise _fallo(origen, campo, f"faltan campos {faltan}")
    if sobran:
        raise _fallo(origen, campo, f"campos no reconocidos {sobran}")
    return valor


def _entero_crudo(valor: Any, campo: str, origen: str, *, minimo: int = 0, maximo: int | None = None) -> int:
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise _fallo(origen, campo, f"se esperaba un entero, llegó {type(valor).__name__} {_ver(valor)}")
    if valor < minimo or (maximo is not None and valor > maximo):
        rango = f"≥ {minimo}" if maximo is None else f"[{minimo}, {maximo}]"
        raise _fallo(origen, campo, f"{valor} fuera de {rango}")
    return valor


def _texto_crudo(valor: Any, campo: str, origen: str, maximo: int) -> str:
    """Cadena UTF-8 válida de a lo sumo `maximo` caracteres (`barrido_texto_max_caracteres`); el mensaje no repite el texto."""
    if not isinstance(valor, str):
        raise _fallo(origen, campo, f"se esperaba una cadena, llegó {type(valor).__name__} {_ver(valor)}")
    if len(valor) > maximo:
        raise _fallo(origen, campo, f"{len(valor)} caracteres exceden el tope de {maximo} (barrido_texto_max_caracteres)")
    try:
        valor.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise _fallo(origen, campo, "texto con sustitutos sueltos (no es UTF-8 válido)") from exc
    return valor


def _digitos_crudo(valor: Any, campo: str, origen: str, *, admite_entero: bool) -> str:
    """Cadena de dígitos ASCII (o entero >= 0 si `admite_entero`); devuelve la cadena canónica."""
    if admite_entero and isinstance(valor, int) and not isinstance(valor, bool):
        if valor < 0:
            raise _fallo(origen, campo, f"{valor} es negativo")
        valor = str(valor)
    if not (isinstance(valor, str) and _RE_DIGITOS.fullmatch(valor) and len(valor) <= DIGITOS_MAX):
        esperado = "entero o cadena de dígitos" if admite_entero else "cadena de dígitos"
        raise _fallo(origen, campo, f"se esperaba {esperado} (máx. {DIGITOS_MAX}), llegó {_ver(valor)}")
    return valor


def _validar_consulta(c: Any, origen: str, maximo: int) -> dict[str, Any]:
    _claves_exactas(c, "consulta", CAMPOS_CONSULTA, origen)
    limite = _entero_crudo(c["limit"], "consulta.limit", origen, minimo=1, maximo=LIMITE_MAX_CONECTOR)
    paises = c["countries"]
    if not isinstance(paises, list) or len(paises) != 1:
        raise _fallo(origen, "consulta.countries",
                     f"se esperaba una lista con UN país ISO-2 (un país por consulta), llegó {_ver(paises)}")
    if not (isinstance(paises[0], str) and _RE_PAIS.fullmatch(paises[0])):
        raise _fallo(origen, "consulta.countries[0]", f"país ISO-2 en mayúsculas esperado, llegó {_ver(paises[0])}")
    estado = c["ad_active_status"]
    if estado not in ESTADOS_ANUNCIO:
        raise _fallo(origen, "consulta.ad_active_status", f"{_ver(estado)} no está en {ESTADOS_ANUNCIO}")
    page_ids = c["page_ids"]
    if page_ids is not None:
        if not isinstance(page_ids, list) or not page_ids:
            raise _fallo(origen, "consulta.page_ids", "se esperaba null o una lista no vacía")
        page_ids = [_digitos_crudo(p, f"consulta.page_ids[{i}]", origen, admite_entero=True)
                    for i, p in enumerate(page_ids)]
        if len(set(page_ids)) != len(page_ids):
            raise _fallo(origen, "consulta.page_ids", "page_ids repetidos")
    terminos = c["search_terms"]
    if terminos is not None:
        _texto_crudo(terminos, "consulta.search_terms", origen, maximo)
    if (terminos is None or not terminos.strip()) and page_ids is None:
        raise _fallo(origen, "consulta.search_terms", "vacío y sin page_ids: la consulta no buscaría nada")
    return {"search_terms": terminos, "countries": [paises[0]], "ad_active_status": estado,
            "limit": limite, "page_ids": page_ids}


def _validar_anuncio(a: Any, i: int, origen: str, maximo: int, hosts: frozenset[str]) -> dict[str, Any]:
    campo = f"ads[{i}]"
    _claves_exactas(a, campo, CAMPOS_ANUNCIO, origen, CAMPOS_ANUNCIO_OPCIONALES)
    ad_id = _digitos_crudo(a["id"], f"{campo}.id", origen, admite_entero=False)
    page_id = _digitos_crudo(a["page_id"], f"{campo}.page_id", origen, admite_entero=True)
    nombre = _texto_crudo(a["page_name"], f"{campo}.page_name", origen, maximo)
    titulo = _texto_crudo(a["ad_creative_link_title"], f"{campo}.ad_creative_link_title", origen, maximo)
    inicio = _entero_crudo(a["ad_delivery_start_time"], f"{campo}.ad_delivery_start_time", origen,
                           minimo=1, maximo=EPOCH_S_MAX_EXCLUSIVO - 1)
    moneda = a["currency"]
    if not (isinstance(moneda, str) and _RE_MONEDA.fullmatch(moneda)):
        raise _fallo(origen, f"{campo}.currency", f"se esperaban 3 letras mayúsculas (ISO-4217), llegó {_ver(moneda)}")
    url = _texto_crudo(a["ad_snapshot_url"], f"{campo}.ad_snapshot_url", origen, maximo)
    sufijo = f"?id={ad_id}"
    if not url.endswith(sufijo):
        raise _fallo(origen, f"{campo}.ad_snapshot_url",
                     f"integridad: la URL debe terminar en «{sufijo}» (id y URL no coinciden: ¿error de transcripción?), "
                     f"llegó {_ver(url, 100)}")
    try:
        partes = urlsplit(url)
    except ValueError as exc:
        raise _fallo(origen, f"{campo}.ad_snapshot_url", f"URL malformada ({exc})") from exc
    if (_RE_CONTROL.search(url) or partes.scheme != "https" or not partes.netloc
            or partes.query != f"id={ad_id}" or partes.fragment):
        raise _fallo(origen, f"{campo}.ad_snapshot_url",
                     f"se esperaba una URL https://<host>/...?id={ad_id} sin espacios ni fragmento, llegó {_ver(url, 100)}")
    # m7: el host (netloc entero: sin usuario@ ni :puerto) debe estar en barrido_hosts_snapshot; ASCII para que ninguna
    # minúscula Unicode (p. ej. la K de Kelvin) se convierta en una letra ASCII al comparar
    if not (partes.netloc.isascii() and partes.netloc.lower() in hosts):
        raise _fallo(origen, f"{campo}.ad_snapshot_url",
                     f"host {_ver(partes.netloc)} fuera de barrido_hosts_snapshot {sorted(hosts)}")
    ok = {"id": ad_id, "page_id": page_id, "page_name": nombre, "ad_creative_link_title": titulo,
          "ad_delivery_start_time": inicio, "currency": moneda, "ad_snapshot_url": url}
    if "ad_creation_time" in a:
        ok["ad_creation_time"] = _entero_crudo(a["ad_creation_time"], f"{campo}.ad_creation_time", origen,
                                               minimo=1, maximo=EPOCH_S_MAX_EXCLUSIVO - 1)
    return ok


def validar_crudo(doc: Any, *, origen: str = "", par: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Valida un archivo crudo (CONTRATO §2) y devuelve una COPIA normalizada; cualquier violación = ErrorValidacion.

    Reglas fatales: campos exactos (ni faltan ni sobran, tampoco en cada anuncio); `schema_version` "1.0.0";
    `corrida_id`/`qid` válidos; `consulta` con `limit` en [1, 50], UN país ISO-2, estado de la Biblioteca y
    `page_ids` null o lista; `capturado_en` UTC con Z; `ruta` ∈ A|B|C|D; `estimated_total_count` entero ≥ len(ads) o
    null; `len(ads) <= limit <= 50`; por anuncio: `id` cadena de dígitos, `page_id` entero o cadena de dígitos,
    `ad_delivery_start_time` entero (epoch en segundos), `currency` 3 letras, título cadena (puede ser «»),
    **integridad** (`ad_snapshot_url` https que termina en `?id=<id>`, detecta transcripción corrupta) e `id` sin repetir.
    Una consulta sin resultados (`ads: []`, `estimated_total_count: 0`) es válida.

    Normalización: copia profunda con el orden del contrato; `page_id` y `consulta.page_ids` salen como cadenas de
    dígitos (así 123 y "123" son la misma página). Los textos NO se tocan (ni NFC ni espacios): son copia textual.
    `origen` (p. ej. la ruta del archivo) encabeza los mensajes de error.

    Revisión de seguridad m7 (parámetros, no números en el código): todo texto de la Biblioteca (`page_name`, título,
    `search_terms`, URL) tiene a lo sumo `barrido_texto_max_caracteres` caracteres, y el host de `ad_snapshot_url`
    debe estar en `barrido_hosts_snapshot` (solo https, sin `usuario@` ni `:puerto`). `par` es el dict de
    `cargar_parametros_barrido`; sin `par` se leen de `RUTA_PARAMETROS_BARRIDO` (con caché por contenido). Si faltan:
    ErrorLimite (5), falla cerrado. Pasar `par` evita releer el YAML y respeta un `--parametros` propio del llamador.
    """
    maximo, hosts = _limites_de_texto(par)
    doc = _claves_exactas(doc, "crudo", CAMPOS_CRUDO, origen)
    if doc["schema_version"] != VERSION_ESQUEMA:
        raise _fallo(origen, "schema_version", f"se esperaba «{VERSION_ESQUEMA}», llegó {_ver(doc['schema_version'])}")
    if not corrida_id_valido(doc["corrida_id"]):
        raise _fallo(origen, "corrida_id", f"se esperaba AAAA-MM-DD-<letra>, llegó {_ver(doc['corrida_id'])}")
    if not qid_valido(doc["qid"]):
        raise _fallo(origen, "qid", f"se esperaba kebab-case ASCII (máx. {QID_MAX_LARGO}), llegó {_ver(doc['qid'])}")
    consulta = _validar_consulta(doc["consulta"], origen, maximo)
    if not isinstance(doc["capturado_en"], str):
        raise _fallo(origen, "capturado_en", f"se esperaba una cadena, llegó {_ver(doc['capturado_en'])}")
    try:
        parsear_z(doc["capturado_en"])
    except ErrorValidacion as exc:
        raise _fallo(origen, "capturado_en", str(exc)) from exc
    if doc["ruta"] not in RUTAS_VALIDAS:
        raise _fallo(origen, "ruta", f"se esperaba una de {RUTAS_VALIDAS}, llegó {_ver(doc['ruta'])}")
    anuncios = doc["ads"]
    if not isinstance(anuncios, list):
        raise _fallo(origen, "ads", f"se esperaba una lista, llegó {type(anuncios).__name__}")
    if len(anuncios) > consulta["limit"]:
        raise _fallo(origen, "ads",
                     f"{len(anuncios)} anuncios exceden consulta.limit={consulta['limit']} (tope del conector: "
                     f"{LIMITE_MAX_CONECTOR}): ¿anuncios de más o limit mal copiado?")
    total = doc["estimated_total_count"]
    if total is not None:
        total = _entero_crudo(total, "estimated_total_count", origen)
        if total < len(anuncios):
            raise _fallo(origen, "estimated_total_count",
                         f"{total} es menor que los {len(anuncios)} anuncios del archivo (se espera ≥ len(ads) o null)")
    normalizados: list[dict[str, Any]] = []
    vistos: dict[str, int] = {}
    for i, a in enumerate(anuncios):
        ok = _validar_anuncio(a, i, origen, maximo, hosts)
        if ok["id"] in vistos:
            raise _fallo(origen, f"ads[{i}].id", f"id {ok['id']} repetido (ya está en ads[{vistos[ok['id']]}])")
        vistos[ok["id"]] = i
        normalizados.append(ok)
    return {"schema_version": VERSION_ESQUEMA, "corrida_id": doc["corrida_id"], "qid": doc["qid"],
            "consulta": consulta, "capturado_en": doc["capturado_en"], "ruta": doc["ruta"],
            "estimated_total_count": total, "ads": normalizados}


def advertencias_crudo(doc: Mapping[str, Any]) -> list[str]:
    """Avisos NO fatales sobre un crudo ya validado (resultado de `validar_crudo`).

    Útiles para sospechar transcripción incompleta sin rechazar el archivo: el conteo estimado es una estimación
    y el contrato no exige `len(ads) == min(limit, total)`.
    """
    avisos: list[str] = []
    n = len(doc["ads"])
    total = doc["estimated_total_count"]
    limite = doc["consulta"]["limit"]
    if total is None:
        avisos.append("sin estimated_total_count: no se puede saber si la muestra está truncada")
    else:
        esperados = min(limite, total)
        if n == 0 and total > 0:
            avisos.append(f"ads vacío pero estimated_total_count={total}: ¿transcripción omitida?")
        elif n < esperados:
            avisos.append(f"{n} anuncios y se esperaban {esperados} (min(limit={limite}, total={total})): "
                          "¿transcripción incompleta?")
    return avisos


def leer_crudo(ruta: Path, *, par: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """`leer_json` + `validar_crudo` + coherencia con la ubicación: `.../<corrida_id>/<qid>.json`.

    Enlaces simbólicos (m8): un archivo que es enlace simbólico es ErrorValidacion (crudo inválido, no se lee); una carpeta
    del camino por debajo de la raíz de confianza que sea enlace es ErrorUso. `par`: ver `validar_crudo`.
    """
    ruta = Path(os.path.abspath(ruta))
    _rechazar_enlaces(ruta.parent)
    if ruta.is_symlink():
        raise _fallo(str(ruta), "archivo", "es un enlace simbólico: los crudos deben ser archivos regulares")
    doc = validar_crudo(leer_json(ruta), origen=str(ruta), par=par)
    if ruta.parent.name != doc["corrida_id"]:
        raise _fallo(str(ruta), "corrida_id",
                     f"{doc['corrida_id']} no coincide con la carpeta «{ruta.parent.name}»")
    if ruta.name != f"{doc['qid']}.json":
        raise _fallo(str(ruta), "qid", f"{doc['qid']} no coincide con el nombre del archivo «{ruta.name}»")
    return doc


def listar_crudos(corrida_id: str, raiz: Path | None = None) -> list[Path]:
    """`empresa/barrido/crudo/<corrida_id>/*.json` sin los `*.error.json`, ordenados por nombre.

    Carpeta inexistente = ErrorUso (corrida desconocida); carpeta vacía = lista vacía. Ignora subcarpetas y temporales.
    """
    carpeta = dir_crudo(corrida_id, raiz)
    _rechazar_enlaces(carpeta, raiz)  # m8: una carpeta de corrida enlazada (o colgante) no es «inexistente»: es un ataque
    if not carpeta.is_dir():
        raise ErrorUso(f"no existe la carpeta de crudos de la corrida {corrida_id}: {carpeta}")
    try:
        entradas = list(carpeta.iterdir())
    except OSError as exc:
        raise ErrorUso(f"no se pudo listar {carpeta}: {exc}") from exc
    return sorted((p for p in entradas
                   if p.name.endswith(".json") and not p.name.endswith(".error.json")
                   and not p.name.endswith(".extra.json") and p.is_file()),
                  key=lambda p: p.name)
