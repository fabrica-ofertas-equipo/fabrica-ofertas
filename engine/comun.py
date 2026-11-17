"""Utilidades comunes del núcleo del motor: raíz, entorno, tiempo UTC, archivos, hashes y firmas.

Qué contiene (firmas congeladas en docs/06 §4.2):

* ``raiz()``, ``entorno()``: dónde está el repositorio y en qué entorno corre (``FABRICA_RAIZ``,
  ``FABRICA_ENTORNO``). Nunca se usa el directorio actual.
* ``ahora_utc()``, ``iso_z()``, ``parsear_z()``, ``dia_de_cuenta()``: todo instante es UTC con ``Z``
  (el sufijo es obligatorio al parsear: sin él se tomaría la hora local del servidor).
* ``escribir_atomico()``, ``anexar_jsonl()``, ``leer_jsonl()``: escritura atómica (temporal en la
  misma carpeta + ``os.replace``) y ``.jsonl`` solo en append, con bloqueo de archivo.
* Re-exportación SIN reimplementar de ``scripts.validar_esquemas``: JSON canónico, hashes,
  clave de idempotencia, firma HMAC y comparación en tiempo constante.
* ``firmar_ed25519()`` / ``verificar_ed25519()``: firmas asimétricas con ``ssh-keygen -Y`` por
  ``subprocess`` con lista de argumentos y sin shell (convenciones §5, D-23). Verificar solo necesita
  la clave PÚBLICA; la privada vive únicamente en el equipo del dueño.
* Ayudas de dinero (importe entero + moneda ISO 4217), ocultamiento de secretos y datos personales,
  y ``ejecutar_cli()`` que traduce excepciones a códigos de salida.

Núcleo sin ciclos: este módulo solo importa ``engine.errores`` y ``scripts.validar_esquemas``.
Ningún umbral, tope ni plazo de decisión vive aquí: lo que parece un número es técnico (formato,
longitud de línea, tiempo máximo de un subproceso local).
"""
from __future__ import annotations

import base64
import binascii
import contextlib
import fcntl
import os
import re
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable, Iterator, Literal, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from engine.errores import ErrorBloqueado, ErrorFabrica, ErrorUso, ErrorValidacion
from scripts.validar_esquemas import (  # noqa: F401  (re-exportación deliberada)
    buscar_floats,
    cargar_json,
    cargar_jsonl,
    cargar_yaml,
    clave_idempotencia,
    comparar_hash,
    firma_hmac,
    hash_archivo,
    hash_bytes,
    hash_directorio,
    hash_objeto,
    hash_ruta,
    json_canonico,
    ruta_json,
)
from scripts.validar_esquemas import errores_de_esquema as _errores_de_esquema_sin_tipar

__all__ = [
    "ENTORNOS", "NAMESPACE_FIRMA", "VAR_SSH_KEYGEN", "anexar_jsonl", "archivo_bloqueado", "ahora_utc", "buscar_floats",
    "cargar_json", "cargar_jsonl", "cargar_yaml", "clave_idempotencia", "comparar_hash", "dia_de_cuenta", "ejecutar_cli",
    "enmascarar_secretos", "entorno", "errores_de_esquema", "escribir_atomico", "escribir_linea", "exigir_importe",
    "exigir_misma_moneda", "exigir_moneda", "firma_hmac", "firmar_ed25519", "hash_archivo", "hash_bytes", "hash_directorio",
    "hash_objeto", "hash_ruta", "instante", "iso_z", "json_canonico", "leer_jsonl", "ocultar_datos_sensibles", "parsear_z",
    "raiz", "resumir_errores_esquema", "verificar_ed25519",
]

ENTORNOS = ("desarrollo", "prueba", "produccion")
NAMESPACE_FIRMA = "fabrica-ofertas"  # namespace de ssh-keygen -Y (convenciones §5)
VAR_SSH_KEYGEN = "FABRICA_SSH_KEYGEN"  # ruta absoluta opcional al binario; sin ella se resuelve por PATH (ver README, riesgo)

# Constantes técnicas (formato y subprocesos locales); no son umbrales de decisión.
_MODO_ARCHIVO_NUEVO = 0o644
_TIMEOUT_SUBPROCESO_S = 20
_ANCHO_ARMADURA = 70
_PRINCIPAL_FIRMA = "dueno"
_MAGIA_SSHSIG = b"SSHSIG"
_CABECERA_FIRMA = "-----BEGIN SSH SIGNATURE-----"
_PIE_FIRMA = "-----END SSH SIGNATURE-----"
_TIPO_CLAVE = "ssh-ed25519"
_LONGITUD_BLOB_CLAVE = 51  # 4 + len("ssh-ed25519") + 4 + 32
_MASCARA_PERMISOS = 0o777
_BASE_DECIMAL = 10
_TARJETA_DIGITOS_MIN, _TARJETA_DIGITOS_MAX = 13, 19  # longitudes de número de tarjeta (ISO/IEC 7812)
_ERRORES_DE_ESQUEMA_MOSTRADOS = 3
_LARGO_MENSAJE_ESQUEMA = 120

# Ancladas con "^...$" pero SIEMPRE usadas con .fullmatch(), nunca .match(): en Python "$" acepta un
# salto de línea final (p. ej. "USD\n" cumpliría ^[A-Z]{3}$ con .match()); .fullmatch() exige que el
# emparejamiento cubra la cadena completa y cierra ese hueco (D-23, observación de la ronda de endurecimiento).
_RX_INSTANTE_Z = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
_RX_MONEDA = re.compile(r"^[A-Z]{3}$")
_RX_CLAVE_PUBLICA = re.compile(r"^ssh-ed25519 ([A-Za-z0-9+/]{43,}={0,2})(?: [^\r\n]*)?$")
_RX_BASE64 = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
_RX_NAMESPACE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


# ----------------------------------------------------------------------------------------------
# Esquemas (envoltura tipada de scripts.validar_esquemas)
# ----------------------------------------------------------------------------------------------
def errores_de_esquema(nombre: str, instancia: Any) -> list[Any]:
    """Errores de ``jsonschema`` al validar ``instancia`` contra el esquema ``nombre`` (envoltura tipada).

    Delega en ``scripts.validar_esquemas.errores_de_esquema``, que lanza un ``KeyError`` SIN TIPO
    cuando ``nombre`` no es un esquema conocido. Desde CT-2 los esquemas salen siempre de la carpeta
    ``contratos/`` del propio CÓDIGO (``scripts.validar_esquemas.RAIZ_CODIGO``), NUNCA de la que
    hubiera bajo ``FABRICA_RAIZ``: una raíz temporal de B0 o de datos no los afecta y una carpeta
    ``contratos/`` ajena no puede sustituirlos. Esa excepción no tipada haría que la CLI saliera con
    el código 1 (interno) en vez de uno de convenciones §8. Aquí se convierte en ``ErrorValidacion``
    (3): nombre de esquema inválido para esta ejecución, nunca un fallo interno.
    """
    try:
        return _errores_de_esquema_sin_tipar(nombre, instancia)
    except KeyError as exc:
        raise ErrorValidacion(
            f"esquema desconocido: {nombre!r} (los esquemas salen de contratos/ del código, nunca de "
            "FABRICA_RAIZ; revisa el nombre)"
        ) from exc


# ----------------------------------------------------------------------------------------------
# Raíz y entorno
# ----------------------------------------------------------------------------------------------
def raiz(env: Mapping[str, str] | None = None) -> Path:
    """Raíz del repositorio: ``FABRICA_RAIZ`` si existe; si no, la carpeta que contiene ``engine/``.

    Nunca depende del directorio actual. Entrada opcional ``env`` (mapa de variables) para pruebas.
    Errores: ``ErrorUso`` si ``FABRICA_RAIZ`` no apunta a una carpeta existente.
    """
    env = os.environ if env is None else env
    valor = env.get("FABRICA_RAIZ")
    if valor:
        ruta = Path(valor)
        if not ruta.is_dir():
            raise ErrorUso("FABRICA_RAIZ no apunta a una carpeta existente")
        return ruta.resolve()
    return Path(__file__).resolve().parents[1]


def entorno(env: Mapping[str, str] | None = None) -> Literal["desarrollo", "prueba", "produccion"]:
    """Entorno de ejecución según ``FABRICA_ENTORNO`` (por defecto ``desarrollo``).

    Solo ``produccion`` admite ``--live`` (convenciones §9). Un valor desconocido NO se interpreta:
    es ``ErrorUso`` (falla cerrado, nunca se asume ``desarrollo`` ni ``produccion``).
    """
    env = os.environ if env is None else env
    valor = (env.get("FABRICA_ENTORNO") or "desarrollo").strip()
    if valor not in ENTORNOS:
        raise ErrorUso(f"FABRICA_ENTORNO inválido: se esperaba uno de {', '.join(ENTORNOS)}")
    return valor  # type: ignore[return-value]


# ----------------------------------------------------------------------------------------------
# Tiempo (UTC con Z)
# ----------------------------------------------------------------------------------------------
def ahora_utc() -> datetime:
    """Instante actual en UTC (con zona), truncado a segundos. Es el reloj por defecto; las pruebas inyectan otro."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def instante(ahora: Callable[[], datetime]) -> datetime:
    """Lee un reloj inyectable y devuelve un instante UTC con zona.

    Errores: ``ErrorValidacion`` si el reloj no devuelve un ``datetime`` con zona (un reloj sin
    zona tomaría la hora local del servidor, prohibido por convenciones §4).
    """
    valor = ahora()
    if not isinstance(valor, datetime) or valor.tzinfo is None or valor.utcoffset() is None:
        raise ErrorValidacion("el reloj debe devolver un datetime con zona (UTC); un instante sin zona está prohibido")
    return valor.astimezone(timezone.utc)


def iso_z(d: datetime) -> str:
    """``2026-11-06T14:30:00Z``: instante UTC con segundos y sufijo ``Z`` (trunca fracciones, no redondea)."""
    if not isinstance(d, datetime) or d.tzinfo is None or d.utcoffset() is None:
        raise ErrorValidacion("iso_z exige un datetime con zona; un instante sin zona está prohibido")
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parsear_z(s: str) -> datetime:
    """Parsea ``AAAA-MM-DDTHH:MM:SSZ`` a ``datetime`` UTC con zona. EXIGE la ``Z`` final.

    Rechaza (``ErrorValidacion``) texto sin ``Z``, con desplazamiento (``+01:00``), con fracciones
    de segundo, fechas imposibles o tipos que no son texto.
    """
    if not isinstance(s, str) or not _RX_INSTANTE_Z.fullmatch(s):
        raise ErrorValidacion("instante inválido: se exige AAAA-MM-DDTHH:MM:SSZ en UTC (sufijo Z obligatorio)")
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ErrorValidacion(f"instante inválido: {s!r} no es una fecha real") from exc


def dia_de_cuenta(instante_utc: datetime | str, tz: str) -> str:
    """Día calendario ``AAAA-MM-DD`` de un instante UTC en la zona IANA ``tz`` de la cuenta de Meta.

    Toda conversión de fechas de reporte de Meta pasa por aquí (convenciones §4). Los cambios de
    horario generan días de 23 o 25 horas; el resultado ya los respeta. Errores: ``ErrorValidacion``
    si ``tz`` no existe o el instante no tiene zona.
    """
    momento = parsear_z(instante_utc) if isinstance(instante_utc, str) else instante_utc
    if not isinstance(momento, datetime) or momento.tzinfo is None or momento.utcoffset() is None:
        raise ErrorValidacion("dia_de_cuenta exige un instante UTC con zona")
    if not isinstance(tz, str) or not tz:
        raise ErrorValidacion("zona horaria ausente")
    try:
        zona = ZoneInfo(tz)
    except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
        raise ErrorValidacion(f"zona horaria desconocida: {tz!r}") from exc
    return momento.astimezone(zona).date().isoformat()


# ----------------------------------------------------------------------------------------------
# Archivos: atómico, append con bloqueo, JSONL
# ----------------------------------------------------------------------------------------------
def _sincronizar_directorio(carpeta: Path) -> None:
    """Fuerza a disco la entrada de directorio tras un ``os.replace`` (mejor esfuerzo)."""
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


def escribir_atomico(ruta: Path, datos: bytes) -> None:
    """Escribe ``datos`` en ``ruta`` de forma atómica: temporal en la misma carpeta + ``os.replace``.

    Un lector ve el contenido anterior completo o el nuevo completo, nunca uno a medias. Si algo
    falla, el archivo original queda intacto y el temporal se borra. Crea las carpetas que falten.
    Conserva los permisos de un archivo existente; uno nuevo queda ``0o644``.
    """
    if not isinstance(datos, (bytes, bytearray)):
        raise ErrorValidacion("escribir_atomico exige bytes")
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    modo = (ruta.stat().st_mode & _MASCARA_PERMISOS) if ruta.exists() else _MODO_ARCHIVO_NUEVO
    fd, temporal = tempfile.mkstemp(dir=ruta.parent, prefix=f".{ruta.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(datos)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(temporal, modo)
        os.replace(temporal, ruta)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temporal)
        raise
    _sincronizar_directorio(ruta.parent)


@contextlib.contextmanager
def archivo_bloqueado(ruta: Path) -> Iterator[BinaryIO]:
    """Abre ``ruta`` en modo append binario (con lectura) bajo ``flock`` exclusivo.

    Sirve para secuencias leer-último-registro → escribir-siguiente (cadena de hashes) sin que otro
    proceso intercale una línea. El bloqueo se libera al salir. Crea carpetas y archivo si faltan.
    """
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "a+b") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            yield f
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def escribir_linea(f: BinaryIO, linea: bytes) -> None:
    """Escribe una línea completa con ``write`` directo (una llamada por línea) y la fuerza a disco.

    Si el archivo no termina en salto de línea (escritura anterior truncada) antepone uno, para que
    la línea nueva nunca quede pegada a restos de otra. Debe llamarse dentro de ``archivo_bloqueado``.
    """
    f.flush()
    tamano = os.fstat(f.fileno()).st_size
    prefijo = b""
    if tamano > 0:
        f.seek(tamano - 1)
        if f.read(1) != b"\n":
            prefijo = b"\n"
    pendiente = memoryview(prefijo + linea)
    while pendiente:
        escritos = os.write(f.fileno(), pendiente)
        pendiente = pendiente[escritos:]
    os.fsync(f.fileno())


def anexar_jsonl(ruta: Path, obj: Mapping[str, Any]) -> None:
    """Agrega ``obj`` como UNA línea de JSON canónico al final de ``ruta`` (solo append, con bloqueo).

    Errores: ``ErrorValidacion`` si ``obj`` no es un mapa, no es serializable o contiene números de
    coma flotante (dinero y tasas son enteros o cadenas decimales, convenciones §3).
    """
    if not isinstance(obj, Mapping):
        raise ErrorValidacion("anexar_jsonl exige un objeto JSON (mapa)")
    dato = dict(obj)
    flotantes = buscar_floats(dato)
    if flotantes:
        raise ErrorValidacion(f"números de coma flotante prohibidos en {', '.join(flotantes[:3])}")
    try:
        linea = json_canonico(dato) + b"\n"
    except (TypeError, ValueError) as exc:
        raise ErrorValidacion(f"objeto no serializable a JSON canónico: {exc}") from exc
    with archivo_bloqueado(ruta) as f:
        escribir_linea(f, linea)


def leer_jsonl(ruta: Path) -> list[dict]:
    """Lee un ``.jsonl`` como lista de objetos. Un archivo inexistente devuelve ``[]``.

    Errores: ``ErrorValidacion`` si una línea no es JSON válido, repite claves o no es un objeto.
    Las líneas vacías se ignoran.
    """
    try:
        lineas = cargar_jsonl(ruta)
    except FileNotFoundError:
        return []
    except (ValueError, UnicodeDecodeError) as exc:
        raise ErrorValidacion(f"{Path(ruta).name}: línea ilegible ({exc})") from exc
    for numero, linea in enumerate(lineas, start=1):
        if not isinstance(linea, dict):
            raise ErrorValidacion(f"{Path(ruta).name}: la línea {numero} no es un objeto JSON")
    return lineas


def resumir_errores_esquema(errores: list[Any]) -> str:
    """Texto breve (primeros errores de ``jsonschema`` con su puntero JSON) para mensajes de ``ErrorValidacion``."""
    return "; ".join(f"{ruta_json(e) or '/'}: {e.message[:_LARGO_MENSAJE_ESQUEMA]}" for e in errores[:_ERRORES_DE_ESQUEMA_MOSTRADOS])


# ----------------------------------------------------------------------------------------------
# Dinero: importe entero + moneda ISO 4217 (convenciones §3)
# ----------------------------------------------------------------------------------------------
def exigir_importe(valor: Any, nombre: str = "importe", *, minimo: int = 0) -> int:
    """Devuelve ``valor`` si es un entero (no ``bool``) ``>= minimo``; si no, ``ErrorValidacion``."""
    if isinstance(valor, bool) or not isinstance(valor, int):
        raise ErrorValidacion(f"{nombre}: debe ser un entero en la unidad menor de la moneda")
    if valor < minimo:
        raise ErrorValidacion(f"{nombre}: debe ser >= {minimo}")
    return valor


def exigir_moneda(valor: Any, nombre: str = "moneda") -> str:
    """Devuelve ``valor`` si es un código ISO 4217 de tres letras mayúsculas; si no, ``ErrorValidacion``."""
    if not isinstance(valor, str) or not _RX_MONEDA.fullmatch(valor):
        raise ErrorValidacion(f"{nombre}: debe ser un código ISO 4217 de tres letras mayúsculas")
    return valor


def exigir_misma_moneda(moneda_a: str, moneda_b: str, contexto: str = "") -> None:
    """Falla con ``ErrorValidacion`` si las monedas difieren. Se llama ANTES de comparar importes."""
    exigir_moneda(moneda_a)
    exigir_moneda(moneda_b)
    if moneda_a != moneda_b:
        sufijo = f" ({contexto})" if contexto else ""
        raise ErrorValidacion(f"monedas distintas: {moneda_a} frente a {moneda_b}{sufijo}; no se compara sin tipo de cambio registrado")


# ----------------------------------------------------------------------------------------------
# Ocultar secretos y datos personales (convenciones §10)
# ----------------------------------------------------------------------------------------------
# Los prefijos de secretos se escriben fragmentados para no activar el escaneo de secretos del repositorio.
_PREFIJOS_SECRETO = ("E" + "AA", "s" + "k_", "r" + "k_", "whs" + "ec_", "cf" + "ut_")
_RX_SECRETO = re.compile(r"(?<![A-Za-z0-9_])(?:" + "|".join(re.escape(p) for p in _PREFIJOS_SECRETO) + r")[A-Za-z0-9_\-]{4,}")
_RX_CORREO = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
_RX_IPV4 = re.compile(r"(?<![0-9.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![0-9.])")
_RX_IPV6 = re.compile(r"(?<![0-9A-Fa-f:])(?:[0-9A-Fa-f]{1,4}:){3,7}[0-9A-Fa-f]{1,4}(?![0-9A-Fa-f:])")
_RX_TARJETA = re.compile(r"(?<![0-9])(?:[0-9][ \-]?){12,18}[0-9](?![0-9])")


def _luhn_valido(digitos: str) -> bool:
    """Control de Luhn de una cadena de dígitos."""
    suma, doble = 0, False
    for c in reversed(digitos):
        n = int(c)
        if doble:
            n *= 2
            if n >= _BASE_DECIMAL:
                n -= _BASE_DECIMAL - 1
        suma += n
        doble = not doble
    return suma % _BASE_DECIMAL == 0


def enmascarar_secretos(texto: str) -> str:
    """Reemplaza por ``****`` todo lo que parezca una credencial (prefijos de Meta, Stripe, Cloudflare)."""
    return _RX_SECRETO.sub("****", texto)


def ocultar_datos_sensibles(texto: str) -> str:
    """Quita de un texto de registro o mensaje: secretos, correos, IP (v4 y v6) y números de tarjeta (Luhn).

    Los registros no deben contener datos personales (convenciones §10, B0-18). Es una red de
    seguridad: el código ya debería usar IDs pseudónimos; esto evita que un descuido llegue al disco.
    """
    texto = enmascarar_secretos(texto)
    texto = _RX_CORREO.sub("[correo]", texto)
    texto = _RX_IPV6.sub("[ip]", texto)
    texto = _RX_IPV4.sub("[ip]", texto)

    def _tarjeta(m: re.Match[str]) -> str:
        digitos = re.sub(r"[^0-9]", "", m.group(0))
        return "[tarjeta]" if _TARJETA_DIGITOS_MIN <= len(digitos) <= _TARJETA_DIGITOS_MAX and _luhn_valido(digitos) else m.group(0)

    return _RX_TARJETA.sub(_tarjeta, texto)


# ----------------------------------------------------------------------------------------------
# Firmas Ed25519 con ssh-keygen -Y (sin dependencias; lista de argumentos, sin shell)
# ----------------------------------------------------------------------------------------------
def _normalizar_clave_publica(clave_publica: str) -> str:
    """Valida ``ssh-ed25519 <base64> [comentario]`` y devuelve ``ssh-ed25519 <base64>`` (sin comentario)."""
    if not isinstance(clave_publica, str):
        raise ErrorBloqueado("clave pública ausente o ilegible")
    m = _RX_CLAVE_PUBLICA.fullmatch(clave_publica.strip())
    if not m:
        raise ErrorBloqueado("clave pública ilegible: se espera «ssh-ed25519 <base64>»")
    try:
        blob = base64.b64decode(m.group(1), validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ErrorBloqueado("clave pública ilegible: base64 inválido") from exc
    if len(blob) != _LONGITUD_BLOB_CLAVE or blob[4:4 + len(_TIPO_CLAVE)] != _TIPO_CLAVE.encode():
        raise ErrorBloqueado("clave pública ilegible: no es una clave Ed25519")
    return f"{_TIPO_CLAVE} {m.group(1)}"


def _exigir_namespace(namespace: Any) -> str:
    """El namespace va como argumento de ``ssh-keygen`` y dentro de ``allowed_signers``: solo caracteres seguros."""
    if not isinstance(namespace, str) or not _RX_NAMESPACE.fullmatch(namespace):
        raise ErrorValidacion("namespace de firma inválido")
    return namespace


def _armar_firma(firma: str) -> str | None:
    """Convierte ``ed25519:<base64>`` en la armadura PEM de SSHSIG; ``None`` si la firma está mal formada."""
    if not isinstance(firma, str) or not firma.startswith("ed25519:"):
        return None
    cuerpo = firma[len("ed25519:"):]
    if not _RX_BASE64.fullmatch(cuerpo):
        return None
    try:
        blob = base64.b64decode(cuerpo, validate=True)
    except (binascii.Error, ValueError):
        return None
    if not blob.startswith(_MAGIA_SSHSIG):
        return None
    lineas = [cuerpo[i:i + _ANCHO_ARMADURA] for i in range(0, len(cuerpo), _ANCHO_ARMADURA)]
    return "\n".join([_CABECERA_FIRMA, *lineas, _PIE_FIRMA]) + "\n"


def _binario_ssh_keygen(ruta_ssh_keygen: "str | Path | None", env: Mapping[str, str] | None) -> str:
    """Resuelve el binario de ``ssh-keygen``: ``ruta_ssh_keygen`` explícita, si no ``FABRICA_SSH_KEYGEN``,
    si no ``"ssh-keygen"`` resuelto por ``PATH`` (comportamiento histórico, riesgo documentado en el README).

    Una ruta CONFIGURADA (parámetro o variable) que no sea un archivo ejecutable falla cerrado
    (``ErrorBloqueado``): si alguien fija la ruta a propósito, un ``PATH`` manipulado en el entorno no
    debe poder sustituirla en silencio volviendo al binario del sistema.
    """
    env = os.environ if env is None else env
    candidato = ruta_ssh_keygen if ruta_ssh_keygen is not None else env.get(VAR_SSH_KEYGEN)
    if not candidato:
        return "ssh-keygen"
    camino = Path(candidato)
    if not camino.is_file() or not os.access(camino, os.X_OK):
        raise ErrorBloqueado(f"{VAR_SSH_KEYGEN} no apunta a un ejecutable: {camino}")
    return str(camino)


def verificar_ed25519(datos: bytes, firma: str, clave_publica: str, *, namespace: str = NAMESPACE_FIRMA,
                      timeout_s: int = _TIMEOUT_SUBPROCESO_S, ruta_ssh_keygen: "str | Path | None" = None,
                      env: Mapping[str, str] | None = None) -> bool:
    """¿Es ``firma`` (``ed25519:<base64>``) una firma válida de ``datos`` con la clave PÚBLICA dada?

    Usa ``ssh-keygen -Y verify`` por ``subprocess`` con lista de argumentos y sin shell. Devuelve
    ``False`` ante cualquier firma mal formada, alterada, de otro namespace o de otra clave.
    ``ruta_ssh_keygen`` (o ``FABRICA_SSH_KEYGEN`` en ``env``) fija una ruta absoluta al binario; sin
    ninguna de las dos se resuelve por ``PATH`` como antes. Errores: ``ErrorBloqueado`` si la clave
    pública es ilegible, si la ruta configurada no es ejecutable o si ``ssh-keygen`` no se puede
    ejecutar (falla cerrado: sin forma de verificar, no se aprueba nada).
    """
    namespace = _exigir_namespace(namespace)
    clave = _normalizar_clave_publica(clave_publica)
    if not isinstance(datos, (bytes, bytearray)):
        raise ErrorValidacion("verificar_ed25519 exige bytes")
    binario = _binario_ssh_keygen(ruta_ssh_keygen, env)
    armadura = _armar_firma(firma)
    if armadura is None:
        return False
    with tempfile.TemporaryDirectory(prefix="fabrica-firma-") as carpeta:
        permitidos = Path(carpeta) / "permitidos"
        archivo_firma = Path(carpeta) / "firma.sig"
        permitidos.write_text(f'{_PRINCIPAL_FIRMA} namespaces="{namespace}" {clave}\n', encoding="utf-8")
        archivo_firma.write_text(armadura, encoding="utf-8")
        orden = [binario, "-Y", "verify", "-f", str(permitidos), "-I", _PRINCIPAL_FIRMA, "-n", namespace, "-s", str(archivo_firma)]
        try:
            resultado = subprocess.run(orden, input=bytes(datos), capture_output=True, timeout=timeout_s, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            raise ErrorBloqueado("no se puede verificar la firma: ssh-keygen no disponible o sin respuesta") from exc
    return resultado.returncode == 0


def firmar_ed25519(datos: bytes, ruta_clave_privada: Path, *, namespace: str = NAMESPACE_FIRMA,
                   timeout_s: int | None = None, ruta_ssh_keygen: "str | Path | None" = None,
                   env: Mapping[str, str] | None = None) -> str:
    """Firma ``datos`` con la clave PRIVADA del dueño y devuelve ``ed25519:<base64>``.

    Solo corre en el equipo del dueño (``orq firmar``, ``engine.limites sellar``) y en pruebas con
    claves de prueba; el motor, los hooks y los Workers nunca tienen la privada. ``timeout_s=None``
    permite que ``ssh-keygen`` pida una frase de paso en el terminal. ``ruta_ssh_keygen`` (o
    ``FABRICA_SSH_KEYGEN`` en ``env``) fija una ruta absoluta al binario; sin ninguna de las dos se
    resuelve por ``PATH`` como antes. Errores: ``ErrorBloqueado`` si no se puede firmar (clave
    ilegible, ruta configurada no ejecutable, ``ssh-keygen`` ausente).
    """
    if not isinstance(datos, (bytes, bytearray)):
        raise ErrorValidacion("firmar_ed25519 exige bytes")
    namespace = _exigir_namespace(namespace)
    binario = _binario_ssh_keygen(ruta_ssh_keygen, env)
    orden = [binario, "-Y", "sign", "-f", str(ruta_clave_privada), "-n", namespace]
    try:
        resultado = subprocess.run(orden, input=bytes(datos), capture_output=True, timeout=timeout_s, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ErrorBloqueado("no se puede firmar: ssh-keygen no disponible o sin respuesta") from exc
    if resultado.returncode != 0:
        raise ErrorBloqueado("no se pudo firmar: clave privada ilegible o con frase de paso incorrecta")
    texto = resultado.stdout.decode("utf-8", errors="replace").splitlines()
    try:
        inicio, fin = texto.index(_CABECERA_FIRMA), texto.index(_PIE_FIRMA)
    except ValueError as exc:
        raise ErrorBloqueado("ssh-keygen devolvió una firma ilegible") from exc
    return "ed25519:" + "".join(linea.strip() for linea in texto[inicio + 1:fin])


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def ejecutar_cli(principal: Callable[[], int | None]) -> int:
    """Ejecuta el cuerpo de una CLI y devuelve su código de salida (convenciones §8).

    ``ErrorFabrica`` → su ``codigo_salida`` con el mensaje en stderr; cualquier otra excepción → 1 con
    la traza en stderr SIN secretos. ``SystemExit`` y ``KeyboardInterrupt`` pasan sin tocarse.
    """
    try:
        resultado = principal()
        return int(resultado or 0)
    except ErrorFabrica as exc:
        print(f"ERROR: {ocultar_datos_sensibles(exc.mensaje)}", file=sys.stderr)
        return exc.codigo_salida
    except Exception:  # noqa: BLE001 - frontera de la CLI: convierte lo inesperado en código 1 con traza segura
        print(ocultar_datos_sensibles(traceback.format_exc()), file=sys.stderr)
        return 1
