"""Acceso confinado a archivos y lectores tolerantes (CONTRATO §7, puntos 2 y 4).

TODA lectura del panel pasa por :func:`resolver` / :class:`Raiz`:

* normaliza y rechaza ``..``, rutas absolutas, ``~``, barras invertidas, NUL y caracteres de control;
* rechaza archivos ocultos y de secretos (``.env*``, ``*.pem``, ``*.key``, ``secretos*``, ``id_rsa*``…);
* resuelve enlaces simbólicos y exige que el destino REAL siga dentro de la raíz (nunca sigue hacia fuera);
* solo abre archivos regulares (un FIFO bloquearía el servidor), con tope de tamaño, ``O_NOFOLLOW`` y
  una segunda comprobación sobre el descriptor abierto.

Los lectores devuelven una :class:`Lectura`: archivo ausente, corrupto, demasiado grande o prohibido NUNCA
lanzan hacia el cliente; el manejador decide ``vacio: true`` y ``avisos``. JSON estricto (sin ``NaN``/``Infinity``)
y YAML con ``safe_load`` sin alias (evita la expansión exponencial).
"""
from __future__ import annotations

import collections
import datetime as _dt
import fcntl
import json
import os
import re
import stat
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from dashboard.seguridad import ErrorHttp

__all__ = [
    "Lectura", "LecturaLineas", "Raiz", "TOPE_IMAGEN", "TOPE_JSON", "TOPE_TEXTO", "TOPE_YAML", "a_json_bytes",
    "anexar_calculado", "anexar_linea", "cargar_json_estricto", "cargar_yaml_seguro", "crear_exclusivo", "es_nombre_prohibido",
    "EXTENSIONES_LEGIBLES", "extension_legible", "iso_mtime", "iso_z", "preparar_destino", "resolver", "sanear", "tipo_de",
]

TOPE_TEXTO = 400 * 1024          # contrato §4: 400 KB por archivo de texto
TOPE_IMAGEN = 1024 * 1024        # contrato §4: imágenes ≤ 1 MB (como data-URL)
TOPE_JSON = 4 * 1024 * 1024      # JSON de los lectores (el mayor del barrido real pesa ~2,2 MB); más grande se omite con aviso
TOPE_YAML = 1024 * 1024
TOPE_VENTANA_JSONL = 8 * 1024 * 1024
TOPE_VERIFICACION = 64 * 1024 * 1024
_MAX_LARGO_RUTA = 400
_MAX_PROFUNDIDAD_SANEAR = 64
_PASO = 65536

_RX_PROHIBIDO = re.compile(
    r"""^(
        \..*                                              # ocultos: .env, .git, .DS_Store…
      | .*\.(pem|key|p8|p12|pfx|jks|keystore|priv|der|asc|gpg|env|secret|secrets|sqlite|sqlite3|db)
      | id_(rsa|dsa|ecdsa|ed25519)(\..*)?
      | (secretos?|secrets?|credenciales|credentials)([._-].*)?
    )$""",
    re.IGNORECASE | re.VERBOSE,
)
# Nombres SOSPECHOSOS (búsqueda, no coincidencia total): claves, tokens, credenciales… aunque lleven una extensión «inocente».
# «secretaria» (la palabra) no cuenta. Revisión de seguridad m-2.
_RX_SOSPECHOSO = re.compile(
    r"secret(?!ar[ií])|secreto|token|passw|clave|credencial|credential|private|api[_-]?key|service[_-]?account|llave",
    re.IGNORECASE)
_RX_ABSOLUTA_WIN = re.compile(r"^[A-Za-z]:")
# Lista BLANCA de extensiones que los endpoints «archivo» devuelven (lo demás: 403). Sin extensión no se lee.
EXTENSIONES_LEGIBLES = frozenset({
    ".json", ".jsonl", ".md", ".markdown", ".yaml", ".yml", ".html", ".htm", ".txt", ".css", ".js", ".mjs", ".csv", ".tsv", ".xml",
    ".svg", ".py", ".sh", ".toml", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif"})

_TIPOS = {
    ".json": "json", ".md": "md", ".markdown": "md", ".yaml": "yaml", ".yml": "yaml", ".html": "html", ".htm": "html",
    ".png": "imagen", ".jpg": "imagen", ".jpeg": "imagen", ".gif": "imagen", ".webp": "imagen", ".avif": "imagen",
    ".bmp": "imagen", ".ico": "imagen",
}
_MIME_IMAGEN = {
    ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".avif": "image/avif", ".bmp": "image/bmp", ".ico": "image/x-icon",
}


# ----------------------------------------------------------------------------------------------
# Utilidades de tiempo y serialización
# ----------------------------------------------------------------------------------------------
def iso_z(momento: _dt.datetime) -> str:
    """``AAAA-MM-DDTHH:MM:SSZ`` (UTC, sin fracciones)."""
    return momento.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def iso_mtime(st: os.stat_result) -> str:
    """Fecha de modificación ISO Z de un ``stat``."""
    return iso_z(_dt.datetime.fromtimestamp(st.st_mtime, _dt.timezone.utc))


def sanear(valor: Any, _nivel: int = 0) -> Any:
    """Vuelve serializable (JSON estricto) cualquier estructura leída de YAML o de memoria.

    Fechas → ISO; ``NaN``/``Infinity`` → ``None``; claves no textuales → texto; tipos raros → ``None``;
    profundidad acotada (un documento hostil no agota la pila).
    """
    if _nivel > _MAX_PROFUNDIDAD_SANEAR:
        return None
    if valor is None or isinstance(valor, (bool, int, str)):
        return valor
    if isinstance(valor, float):
        return valor if valor == valor and valor not in (float("inf"), float("-inf")) else None
    if isinstance(valor, (_dt.datetime, _dt.date)):
        return valor.isoformat()
    if isinstance(valor, dict):
        return {(k if isinstance(k, str) else str(k)): sanear(v, _nivel + 1) for k, v in valor.items()}
    if isinstance(valor, (list, tuple, set, frozenset)):
        return [sanear(v, _nivel + 1) for v in valor]
    return None


def a_json_bytes(obj: Any) -> bytes:
    """JSON estricto y solo ASCII (U+202E y HTML pasan como DATO: ``\\u202e``, ``<`` dentro de cadenas)."""
    try:
        texto = json.dumps(obj, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    except (ValueError, TypeError, RecursionError):
        texto = json.dumps(sanear(obj), ensure_ascii=True, allow_nan=False, separators=(",", ":"))
    return texto.encode("ascii")


# ----------------------------------------------------------------------------------------------
# JSON y YAML estrictos
# ----------------------------------------------------------------------------------------------
def _rechazar_constante(nombre: str) -> Any:
    raise ValueError(f"constante no permitida en JSON: {nombre}")


def _numero_finito(texto: str) -> float:
    valor = float(texto)
    if valor != valor or valor in (float("inf"), float("-inf")):
        raise ValueError("número no finito en JSON")
    return valor


def cargar_json_estricto(contenido: bytes | str) -> Any:
    """``json.loads`` sin ``NaN``/``Infinity``/``1e999``; errores de forma → ``ValueError``."""
    try:
        return json.loads(contenido, parse_constant=_rechazar_constante, parse_float=_numero_finito)
    except RecursionError as exc:
        raise ValueError("JSON demasiado anidado") from exc


class _CargadorSeguro(yaml.SafeLoader):
    """``SafeLoader`` que rechaza alias y anclas (``&a``/``*a``)."""

    def compose_node(self, parent: Any, index: Any) -> Any:
        if self.check_event(yaml.AliasEvent):
            raise yaml.YAMLError("alias YAML no permitido")
        return super().compose_node(parent, index)


def cargar_yaml_seguro(contenido: bytes | str) -> Any:
    """``yaml.safe_load`` sin alias; errores → ``ValueError``. El resultado pasa por :func:`sanear`."""
    try:
        return sanear(yaml.load(contenido, Loader=_CargadorSeguro))
    except (yaml.YAMLError, RecursionError, ValueError) as exc:
        raise ValueError(f"YAML inválido: {type(exc).__name__}") from exc


# ----------------------------------------------------------------------------------------------
# Resolvedor confinado
# ----------------------------------------------------------------------------------------------
def es_nombre_prohibido(nombre: str) -> bool:
    """¿Es un nombre de archivo/carpeta oculto, de secretos o sospechoso? (se prueba por segmento)."""
    return _RX_PROHIBIDO.fullmatch(nombre) is not None or _RX_SOSPECHOSO.search(nombre) is not None


def extension_legible(nombre: str) -> bool:
    """¿La extensión está en la lista blanca de lo que el panel muestra como archivo?"""
    return Path(nombre).suffix.lower() in EXTENSIONES_LEGIBLES


def tipo_de(ruta: str | Path) -> str:
    """``json|md|yaml|html|imagen|texto`` por extensión (SVG se trata como texto: nunca como imagen activa)."""
    return _TIPOS.get(Path(str(ruta)).suffix.lower(), "texto")


def mime_imagen(ruta: str | Path) -> str:
    return _MIME_IMAGEN.get(Path(str(ruta)).suffix.lower(), "application/octet-stream")


def _dentro(real: str, base_real: str) -> bool:
    return real == base_real or real.startswith(base_real.rstrip(os.sep) + os.sep)


def _segmentos(ruta: str) -> list[str]:
    """Valida textualmente ``ruta`` y devuelve sus segmentos (sin vacíos ni ``.``). 403 si es hostil."""
    if not isinstance(ruta, str):
        raise ErrorHttp(403, "ruta_invalida", "La dirección del archivo no es válida.")
    if len(ruta) > _MAX_LARGO_RUTA:
        raise ErrorHttp(403, "ruta_invalida", "La dirección del archivo es demasiado larga.")
    if any(ord(c) < 32 or ord(c) == 127 for c in ruta):
        raise ErrorHttp(403, "ruta_invalida", "La dirección del archivo tiene caracteres que no se admiten.")
    if "\\" in ruta:
        raise ErrorHttp(403, "ruta_invalida", "La dirección del archivo no puede llevar barras invertidas.")
    if ruta.startswith("/") or ruta.startswith("~") or _RX_ABSOLUTA_WIN.match(ruta):
        raise ErrorHttp(403, "ruta_absoluta", "Solo se admiten direcciones relativas.")
    partes = [p for p in ruta.split("/") if p not in ("", ".")]
    if any(p == ".." for p in partes):
        raise ErrorHttp(403, "ruta_fuera_de_raiz", "La dirección intenta salir de su carpeta.")
    if any(es_nombre_prohibido(p) for p in partes):
        raise ErrorHttp(403, "ruta_prohibida", "Ese archivo no se puede leer desde el panel.")
    return partes


def resolver(base: str | Path, ruta: str, *, limite: str | Path | None = None, debe_existir: bool = True) -> Path:
    """Ruta REAL de ``ruta`` bajo ``base`` o ``ErrorHttp``.

    403 si la ruta es hostil, si un enlace simbólico escapa de ``base`` (o de ``limite``, la raíz exterior
    que ``base`` mismo no puede abandonar) o si el nombre real es de secretos; 404 si no existe.
    """
    partes = _segmentos(ruta)
    base_real = os.path.realpath(base)
    if limite is not None and not _dentro(base_real, os.path.realpath(limite)):
        raise ErrorHttp(403, "ruta_fuera_de_raiz", "La carpeta pedida queda fuera de la raíz del panel.")
    real = os.path.realpath(os.path.join(base_real, *partes))
    if not _dentro(real, base_real):
        raise ErrorHttp(403, "ruta_fuera_de_raiz", "La dirección termina fuera de su carpeta (puede ser un acceso directo).")
    relativa = os.path.relpath(real, base_real)
    if relativa != "." and any(es_nombre_prohibido(p) for p in relativa.split(os.sep)):
        raise ErrorHttp(403, "ruta_prohibida", "Ese archivo no se puede leer desde el panel.")
    if debe_existir and not os.path.lexists(real):
        raise ErrorHttp(404, "no_encontrado", "No existe ese archivo.")
    return Path(real)


def _ruta_de_fd(fd: int) -> str | None:
    """Ruta real del descriptor abierto (macOS ``F_GETPATH``; Linux ``/proc``); ``None`` si no se puede."""
    try:
        if hasattr(fcntl, "F_GETPATH"):
            buf = fcntl.fcntl(fd, fcntl.F_GETPATH, b"\0" * 1024)
            return os.fsdecode(buf.split(b"\0", 1)[0])
        return os.readlink(f"/proc/self/fd/{fd}")
    except (OSError, ValueError):
        return None


def _abrir_regular(real: Path, base_real: str) -> int:
    """Abre ``real`` solo lectura sin seguir el último enlace ni bloquear; exige archivo regular dentro de ``base``."""
    banderas = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        fd = os.open(real, banderas)
    except OSError as exc:
        raise ErrorHttp(404, "no_encontrado", "No existe ese archivo o no se puede abrir.") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise ErrorHttp(400, "no_es_archivo", "Esa dirección no es un archivo.")
        if st.st_nlink > 1:   # un enlace DURO puede apuntar a un archivo de fuera (p. ej. empresa/captura/freno.json)
            raise ErrorHttp(403, "enlace_duro", "Los archivos con enlaces duros no se leen desde el panel.")
        abierta = _ruta_de_fd(fd)
        if abierta is not None and not _dentro(os.path.realpath(abierta), base_real):
            raise ErrorHttp(403, "ruta_fuera_de_raiz", "El archivo abierto queda fuera de la raíz del panel.")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _leer_fd(fd: int, tope: int) -> bytes:
    trozos: list[bytes] = []
    total = 0
    while total < tope + 1:
        parte = os.read(fd, min(_PASO, tope + 1 - total))
        if not parte:
            break
        trozos.append(parte)
        total += len(parte)
    return b"".join(trozos)


# ----------------------------------------------------------------------------------------------
# Lecturas
# ----------------------------------------------------------------------------------------------
@dataclass
class Lectura:
    """Resultado de leer un archivo sin lanzar: ``estado`` ∈ ok|ausente|corrupto|grande|prohibido|error."""

    estado: str
    dato: Any = None
    aviso: str | None = None
    ruta: str = ""
    bytes: int = 0
    mtime: str | None = None
    truncado: bool = False

    @property
    def ok(self) -> bool:
        return self.estado == "ok"


@dataclass
class LecturaLineas:
    """Cola de un JSONL: ``lineas`` = ``[(n, objeto|None, texto_crudo)]`` con ``n`` físico (1 = primera línea)."""

    estado: str
    lineas: list[tuple[int, Any, str]] = field(default_factory=list)
    total: int | None = None
    avisos: list[str] = field(default_factory=list)
    ruta: str = ""
    mtime: str | None = None
    truncado: bool = False


AMPLIFICACION_JSON = 25            # un JSON parseado ocupa ~25 veces sus bytes en memoria (medido con listas de objetos pequeños)
_UMBRAL_PARSE_GRANDE = 1024 * 1024  # a partir de aquí, como mucho 2 parseos a la vez


class _CacheJson:
    """Caché pequeño de JSON por (ruta real, mtime_ns, tamaño). Cuenta el COSTE estimado en memoria (bytes × 25), no los bytes del
    archivo: 8 archivos de 7,6 MB llevaban el proceso a 1,2 GB (revisión m-10). Los objetos son de SOLO LECTURA."""

    def __init__(self, entradas: int = 3, costo_max: int = 160 * 1024 * 1024) -> None:
        self._d: collections.OrderedDict[tuple[str, int, int], tuple[Any, int]] = collections.OrderedDict()
        self._costo = 0
        self._entradas = entradas
        self._costo_max = costo_max
        self._cerrojo = threading.Lock()

    def obtener(self, clave: tuple[str, int, int]) -> Any | None:
        with self._cerrojo:
            if clave in self._d:
                self._d.move_to_end(clave)
                return self._d[clave][0]
        return None

    def guardar(self, clave: tuple[str, int, int], valor: Any, costo: int) -> None:
        with self._cerrojo:
            if clave in self._d or costo > self._costo_max:
                return
            self._d[clave] = (valor, costo)
            self._costo += costo
            while self._d and (len(self._d) > self._entradas or self._costo > self._costo_max):
                _, (_, c) = self._d.popitem(last=False)
                self._costo -= c

    def estadisticas(self) -> tuple[int, int]:
        """``(entradas, coste estimado en bytes)``."""
        with self._cerrojo:
            return len(self._d), self._costo


_PARSES_GRANDES = threading.BoundedSemaphore(2)


_CACHE = _CacheJson()


class Raiz:
    """Una carpeta base confinada. ``Raiz(raiz).sub('ofertas', id)`` hereda ``limite`` para no escapar de la raíz."""

    def __init__(self, base: str | Path, *, limite: str | Path | None = None) -> None:
        self.base = Path(base)
        self.limite = Path(limite) if limite is not None else None

    # -- navegación ---------------------------------------------------------------------------
    def sub(self, *partes: str) -> "Raiz":
        """Subcarpeta confinada (los nombres pasan por el mismo filtro que cualquier ruta)."""
        real = resolver(self.base, "/".join(partes), limite=self.limite, debe_existir=False)
        return Raiz(real, limite=self.limite if self.limite is not None else self.base)

    def real(self, ruta: str, *, debe_existir: bool = True) -> Path:
        return resolver(self.base, ruta, limite=self.limite, debe_existir=debe_existir)

    def existe(self, ruta: str) -> bool:
        try:
            self.real(ruta)
            return True
        except ErrorHttp:
            return False

    def es_directorio(self, ruta: str) -> bool:
        try:
            return self.real(ruta).is_dir()
        except (ErrorHttp, OSError):
            return False

    def listar(self, ruta: str = "", *, solo: str | None = None) -> list[str]:
        """Nombres (ordenados, sin los prohibidos ni ocultos) dentro de una carpeta; ``[]`` si no existe.

        ``solo`` ∈ {``"dir"``, ``"archivo"``}. No sigue enlaces simbólicos que salgan de la raíz.
        """
        try:
            carpeta = self.real(ruta) if ruta else Path(os.path.realpath(self.base))
            base_real = os.path.realpath(self.base)
            nombres: list[str] = []
            with os.scandir(carpeta) as it:
                for e in it:
                    if es_nombre_prohibido(e.name):
                        continue
                    destino = os.path.realpath(e.path)
                    if not _dentro(destino, base_real):
                        continue
                    if solo == "dir" and not os.path.isdir(destino):
                        continue
                    if solo == "archivo" and not os.path.isfile(destino):
                        continue
                    nombres.append(e.name)
            return sorted(nombres)
        except (ErrorHttp, OSError):
            return []

    def recorrer(self, ruta: str = "", *, maximo: int = 300, profundidad: int = 6) -> list[tuple[str, os.stat_result]]:
        """Archivos regulares bajo ``ruta`` (rutas relativas a ``base``, ordenadas), sin seguir enlaces y con tope."""
        salida: list[tuple[str, os.stat_result]] = []
        try:
            inicio = Path(os.path.realpath(self.base)) if not ruta else self.real(ruta)
        except ErrorHttp:
            return salida
        base_real = os.path.realpath(self.base)

        def _ir(carpeta: str, nivel: int) -> None:
            if len(salida) >= maximo or nivel > profundidad:
                return
            try:
                with os.scandir(carpeta) as it:
                    entradas = sorted(it, key=lambda e: e.name)
            except OSError:
                return
            for e in entradas:
                if len(salida) >= maximo:
                    return
                if es_nombre_prohibido(e.name) or e.name == "__pycache__":
                    continue
                try:
                    if e.is_symlink():
                        continue
                    if e.is_dir(follow_symlinks=False):
                        _ir(e.path, nivel + 1)
                    elif e.is_file(follow_symlinks=False):
                        salida.append((os.path.relpath(e.path, base_real), e.stat(follow_symlinks=False)))
                except OSError:
                    continue

        _ir(str(inicio), 0)
        return sorted(salida, key=lambda t: t[0])

    # -- lectura -------------------------------------------------------------------------------
    def bytes(self, ruta: str, tope: int) -> tuple[bytes, bool, os.stat_result]:
        """Hasta ``tope`` bytes (``truncado`` si había más). Lanza ``ErrorHttp`` ante rutas hostiles/ausentes."""
        real = self.real(ruta)
        fd = _abrir_regular(real, os.path.realpath(self.base))
        try:
            st = os.fstat(fd)
            datos = _leer_fd(fd, tope)
        finally:
            os.close(fd)
        return datos[:tope], len(datos) > tope, st

    def _lectura(self, ruta: str, tope: int) -> tuple[Lectura | None, bytes, os.stat_result | None]:
        try:
            datos, truncado, st = self.bytes(ruta, tope)
        except ErrorHttp as exc:
            if exc.estado == 404:
                return Lectura("ausente", ruta=ruta), b"", None
            if exc.estado == 403:
                return Lectura("prohibido", aviso=f"{ruta}: {exc.mensaje}", ruta=ruta), b"", None
            return Lectura("error", aviso=f"{ruta}: {exc.mensaje}", ruta=ruta), b"", None
        except OSError:
            return Lectura("error", aviso=f"No se pudo leer el archivo ({ruta}).", ruta=ruta), b"", None
        if truncado:
            return Lectura("grande", aviso=f"El archivo es demasiado grande (más de {tope // 1024} KB) y no se lee ({ruta}).",
                           ruta=ruta, bytes=st.st_size, mtime=iso_mtime(st), truncado=True), b"", st
        return None, datos, st

    def texto(self, ruta: str, tope: int = TOPE_TEXTO) -> Lectura:
        """Texto UTF-8 (reemplazando bytes inválidos). ``Lectura.truncado`` si se recortó (sin error)."""
        try:
            datos, truncado, st = self.bytes(ruta, tope)
        except ErrorHttp as exc:
            estado = {404: "ausente", 403: "prohibido"}.get(exc.estado, "error")
            return Lectura(estado, aviso=None if estado == "ausente" else f"{ruta}: {exc.mensaje}", ruta=ruta)
        except OSError:
            return Lectura("error", aviso=f"No se pudo leer el archivo ({ruta}).", ruta=ruta)
        return Lectura("ok", datos.decode("utf-8", "replace"), ruta=ruta, bytes=st.st_size,
                       mtime=iso_mtime(st), truncado=truncado)

    def json(self, ruta: str, tope: int = TOPE_JSON, *, cache: bool = False) -> Lectura:
        """JSON estricto. Con ``cache=True`` el objeto devuelto es compartido: NO lo modifiques."""
        clave = None
        if cache:
            try:
                real = self.real(ruta)
                st = real.stat()
                clave = (str(real), st.st_mtime_ns, st.st_size)
                hit = _CACHE.obtener(clave)
                if hit is not None:
                    return Lectura("ok", hit, ruta=ruta, bytes=st.st_size, mtime=iso_mtime(st))
            except (ErrorHttp, OSError):
                clave = None
        previa, datos, st = self._lectura(ruta, tope)
        if previa is not None:
            return previa
        grande = len(datos) > _UMBRAL_PARSE_GRANDE
        if grande:
            _PARSES_GRANDES.acquire()   # varios parseos de varios MB a la vez multiplican el pico de memoria
        try:
            dato = cargar_json_estricto(datos)
        except (ValueError, UnicodeDecodeError) as exc:
            return Lectura("corrupto", aviso=f"El archivo está dañado o mal escrito y no se pudo leer ({ruta}).",
                           ruta=ruta, bytes=st.st_size, mtime=iso_mtime(st))
        finally:
            if grande:
                _PARSES_GRANDES.release()
        if clave is not None and cache:
            _CACHE.guardar(clave, dato, len(datos) * AMPLIFICACION_JSON)
        return Lectura("ok", dato, ruta=ruta, bytes=st.st_size, mtime=iso_mtime(st))

    def yaml(self, ruta: str, tope: int = TOPE_YAML) -> Lectura:
        previa, datos, st = self._lectura(ruta, tope)
        if previa is not None:
            return previa
        try:
            dato = cargar_yaml_seguro(datos)
        except (ValueError, UnicodeDecodeError) as exc:
            return Lectura("corrupto", aviso=f"El archivo está dañado o mal escrito y no se pudo leer ({ruta}).", ruta=ruta, bytes=st.st_size, mtime=iso_mtime(st))
        return Lectura("ok", dato, ruta=ruta, bytes=st.st_size, mtime=iso_mtime(st))

    def jsonl_cola(self, ruta: str, maximo: int = 500, ventana: int = TOPE_VENTANA_JSONL) -> LecturaLineas:
        """Últimas ``maximo`` líneas físicas de un JSONL con su número ``n`` absoluto.

        Lee como mucho ``ventana`` bytes del final; las líneas ilegibles se devuelven con ``objeto=None``
        (el cliente las ve como corrupción) y se avisa. Nunca lanza.
        """
        try:
            real = self.real(ruta)
            fd = _abrir_regular(real, os.path.realpath(self.base))
        except ErrorHttp as exc:
            return LecturaLineas("ausente" if exc.estado == 404 else "prohibido",
                                 avisos=[] if exc.estado == 404 else [f"{ruta}: {exc.mensaje}"], ruta=ruta)
        try:
            st = os.fstat(fd)
            tamano = st.st_size
            inicio = max(0, tamano - ventana)
            # Número de línea absoluto: cuenta los saltos de línea anteriores a la ventana.
            antes = 0
            if inicio:
                os.lseek(fd, 0, os.SEEK_SET)
                restante = inicio
                while restante > 0:
                    parte = os.read(fd, min(1 << 20, restante))
                    if not parte:
                        break
                    antes += parte.count(b"\n")
                    restante -= len(parte)
            os.lseek(fd, inicio, os.SEEK_SET)
            datos = _leer_fd(fd, tamano - inicio)
        finally:
            os.close(fd)
        avisos: list[str] = []
        if inicio:
            salto = datos.find(b"\n")
            datos = b"" if salto < 0 else datos[salto + 1:]
            antes += 1
            avisos.append(f"El archivo es muy grande: se leen solo los últimos {ventana // 1024} KB ({ruta}).")
        crudas = datos.split(b"\n")
        if crudas and crudas[-1] == b"":
            crudas.pop()
        total = antes + len(crudas)
        elegidas = crudas[-maximo:] if maximo else []
        primera = total - len(elegidas) + 1
        lineas: list[tuple[int, Any, str]] = []
        corruptas = 0
        for k, cruda in enumerate(elegidas):
            texto = cruda.decode("utf-8", "replace")
            if not texto.strip():
                continue
            try:
                obj = cargar_json_estricto(texto)
                if not isinstance(obj, dict):
                    raise ValueError("no es un objeto")
            except ValueError:
                obj = None
                corruptas += 1
            lineas.append((primera + k, obj, texto[:200]))
        if corruptas:
            avisos.append(f"{ruta}: {corruptas} línea(s) no se pudieron leer (el archivo pudo dañarse o quedar a medias).")
        return LecturaLineas("ok", lineas, total, avisos, ruta, iso_mtime(st), truncado=bool(inicio))

    def jsonl_completo(self, ruta: str, tope: int = TOPE_VERIFICACION) -> tuple[list[dict[str, Any]] | None, str | None]:
        """Todas las líneas JSON (objetos) o ``(None, motivo)`` si no se puede/debe leer entero."""
        previa, datos, _ = self._lectura(ruta, tope)
        if previa is not None:
            return None, previa.aviso or "ausente"
        objetos: list[dict[str, Any]] = []
        for texto in datos.split(b"\n"):
            if not texto.strip():
                continue
            try:
                obj = cargar_json_estricto(texto)
            except (ValueError, UnicodeDecodeError):
                return None, "hay líneas ilegibles"
            if not isinstance(obj, dict):
                return None, "hay líneas que no son objetos"
            objetos.append(obj)
        return objetos, None

    def stat(self, ruta: str) -> os.stat_result | None:
        try:
            return os.stat(self.real(ruta))
        except (ErrorHttp, OSError):
            return None


# ----------------------------------------------------------------------------------------------
# Escritura confinada (solo ``empresa/panel/`` y ``empresa/PAUSA``; escritura atómica)
# ----------------------------------------------------------------------------------------------
def preparar_destino(raiz: str | Path, rel: str) -> Path:
    """Ruta absoluta de ``rel`` bajo ``raiz`` con sus carpetas creadas, sin escapar por enlaces simbólicos.

    ``rel`` es una constante del programa (``empresa/panel/pulido.jsonl``…), pero igualmente se valida.
    """
    partes = _segmentos(rel.replace("\\", "/"))
    if not partes:
        raise ErrorHttp(400, "ruta_invalida", "Falta la ruta de destino.")
    raiz_real = os.path.realpath(raiz)
    actual = raiz_real
    for p in partes[:-1]:
        siguiente = os.path.join(actual, p)
        if os.path.islink(siguiente):
            real = os.path.realpath(siguiente)
            if not _dentro(real, raiz_real):
                raise ErrorHttp(403, "ruta_fuera_de_raiz", "El destino escapa de la raíz del panel.")
            siguiente = real
        elif not os.path.isdir(siguiente):
            try:
                os.mkdir(siguiente, 0o755)
            except FileExistsError:
                pass
            except OSError as exc:
                raise ErrorHttp(500, "escritura_imposible", "No se pudo crear la carpeta de destino.") from exc
        actual = siguiente
    destino = os.path.join(actual, partes[-1])
    if os.path.islink(destino):
        raise ErrorHttp(403, "ruta_fuera_de_raiz", "El destino es un enlace simbólico.")
    return Path(destino)


def anexar_linea(destino: Path, linea: bytes, *, tope_archivo: int = 20 * 1024 * 1024) -> None:
    """Agrega UNA línea (``linea`` ya termina en ``\\n``) con ``O_APPEND`` + ``flock`` + ``fsync``.

    Una sola llamada ``write``: dos escritores concurrentes no intercalan bytes. Nunca reescribe lo anterior.
    """
    fd = os.open(destino, os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0), 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            if os.fstat(fd).st_size + len(linea) > tope_archivo:
                raise ErrorHttp(507, "archivo_lleno", "La bitácora está llena: no admite más anotaciones.")
            escrito = os.write(fd, linea)
            if escrito != len(linea):
                raise ErrorHttp(500, "escritura_incompleta", "No se pudo escribir la línea completa.")
            os.fsync(fd)
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def anexar_calculado(destino: Path, construir: "Callable[[bytes], bytes | None]", *,
                     tope_archivo: int = 20 * 1024 * 1024) -> bytes | None:
    """Lee el archivo y agrega la línea que devuelve ``construir(contenido_actual)`` BAJO UN MISMO ``flock``.

    Sirve para asignar identificadores correlativos o validar contra lo ya escrito sin carreras entre procesos o hilos.
    ``construir`` devuelve la línea (con ``\\n`` final) o ``None`` para no escribir nada; puede lanzar ``ErrorHttp``.
    Devuelve los bytes escritos (o ``None``). Nunca reescribe lo anterior.
    """
    fd = os.open(destino, os.O_RDWR | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0), 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        try:
            tamano = os.fstat(fd).st_size
            if tamano > tope_archivo:
                raise ErrorHttp(507, "archivo_lleno", "La bitácora está llena: no admite más anotaciones.")
            os.lseek(fd, 0, os.SEEK_SET)
            actual = _leer_fd(fd, tope_archivo)
            linea = construir(actual)
            if linea is None:
                return None
            if tamano + len(linea) > tope_archivo:
                raise ErrorHttp(507, "archivo_lleno", "La bitácora está llena: no admite más anotaciones.")
            if os.write(fd, linea) != len(linea):
                raise ErrorHttp(500, "escritura_incompleta", "No se pudo escribir la línea completa.")
            os.fsync(fd)
            return linea
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def crear_exclusivo(destino: Path, contenido: bytes) -> bool:
    """Crea ``destino`` con ``contenido`` solo si NO existe (atómico: escribe aparte y enlaza). ``False`` si ya existía.

    Un lector nunca ve el archivo a medias; nunca sobrescribe ni borra.
    """
    temporal = destino.with_name(f".{destino.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    fd = os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        try:
            os.write(fd, contenido)
            os.fsync(fd)
        finally:
            os.close(fd)
        try:
            os.link(temporal, destino)  # falla si ya existe: es el «crear si no existe» atómico
            return True
        except FileExistsError:
            return False
        except OSError:
            # Sistemas de archivos sin enlaces duros: O_EXCL directo (el archivo se ve vacío un instante).
            try:
                fd2 = os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
            except FileExistsError:
                return False
            try:
                os.write(fd2, contenido)
                os.fsync(fd2)
            finally:
                os.close(fd2)
            return True
    finally:
        try:
            os.unlink(temporal)
        except OSError:
            pass
