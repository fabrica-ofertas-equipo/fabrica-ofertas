"""Lectura de la memoria del Cerebro, SOLO LECTURA y confinada a la raíz (biblioteca estándar).

Lo comparten el buscador, el jardinero y el lector de preferencias. No escribe, no crea carpetas, no sigue enlaces que salgan de la raíz. Todo texto que viene de
archivos es un DATO no confiable: aquí se limpia de controles, se recorta y se entrega; quien lo muestre lo cita entre comillas y nunca lo obedece.

La skill ``cerebro-abrir`` NO importa este módulo (corre sola, por ruta, sin paquete): tiene sus propias copias de ``corto``, ``dia`` y ``plegar_bitacora`` y
``tests/cerebro/test_lista_unica.py`` comprueba que no se desvíen de las de aquí.
"""
from __future__ import annotations

import datetime as dt
import difflib
import hashlib
import json
import os
import re
import unicodedata
from pathlib import Path
from typing import Any

REL_PULIDO = "empresa/panel/pulido.jsonl"
REL_MEMORIA = "empresa/memoria"
REL_DECISIONES = f"{REL_MEMORIA}/decisiones_dueno.jsonl"
REL_LECCIONES = f"{REL_MEMORIA}/lecciones.jsonl"
REL_PREFERENCIAS = f"{REL_MEMORIA}/preferencias.jsonl"
REL_JARDIN = f"{REL_MEMORIA}/jardin"
REL_DOC_DECISIONES = "docs/_historial/mentor-sistema/decisiones-del-dueno.md"
REL_DOC_TAREAS = "docs/00-decisiones-y-tareas-del-dueno.md"
REL_PANTALLAS = "docs/_historial/mentor-sistema/pantallas"

SIM_DUP = 0.80            # empresa/parametros.yaml, grupo memoria: sim_dup (la prueba compara con el YAML)
SIM_RELEVANTE = 0.60      # ídem: sim_relevante
TOPE_JSONL = 8 * 1024 * 1024
TOPE_DOC = 400 * 1024
ESTADOS_PUL = ("abierta", "en_curso", "resuelta")

RX_ID_PUL = re.compile(r"^PUL-[0-9]{4,9}$")
RX_OFERTA = re.compile(r"^(OF-[0-9]{6}-[0-9]{2}|_[a-z0-9][a-z0-9_-]{0,31})$")
RX_FECHA = re.compile(r"^([0-9]{4})-([0-9]{2})-([0-9]{2})")
RX_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
RX_DIRECCION = re.compile("[\u200b-\u200f\u202a-\u202e\u2060-\u2064\u2066-\u2069\ufeff]")

_SECRETOS = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY|\b(?:AKIA|ASIA)[0-9A-Z]{16}\b|\bsk-[A-Za-z0-9_\-]{20,}|\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})"
    r"|\bxox[abprs]-[A-Za-z0-9-]{10,}|\b(?:[rsp]k_(?:live|test)_[A-Za-z0-9]{16,}|whsec_[A-Za-z0-9]{16,})|\bAIza[0-9A-Za-z_\-]{30,}"
    r"|\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}|\bBearer\s+[A-Za-z0-9._~+/\-]{20,}", re.IGNORECASE)


def raiz_por_defecto() -> Path:
    if os.environ.get("FABRICA_RAIZ"):
        return Path(os.environ["FABRICA_RAIZ"])
    for p in Path(__file__).resolve().parents:
        if (p / "empresa").is_dir() and (p / "dashboard").is_dir():
            return p
    return Path.cwd()


def corto(valor: Any, maximo: int = 200) -> str | None:
    """Texto sin controles ni caracteres de dirección, con los espacios colapsados y recortado a ``maximo``. ``None`` si no es texto o queda vacío."""
    if not isinstance(valor, str):
        return None
    limpio = " ".join(RX_DIRECCION.sub("", RX_CONTROL.sub("", valor)).split())
    return limpio[:maximo] if limpio else None


def sin_secretos(texto: str) -> str:
    """Tapa lo que parece una clave o un token (el buscador nunca debe repetir un secreto que haya en un archivo)."""
    return _SECRETOS.sub("[secreto omitido]", texto)


# ── lectura confinada ────────────────────────────────────────────────────────────────────────────────
def leer(raiz: Path, rel: str, tope: int) -> tuple[bytes | None, str | None]:
    """Bytes de ``rel`` bajo ``raiz`` sin salir de ella por enlaces; ``(None, motivo)`` si falta (motivo ``None``), escapa o es demasiado grande. Nunca lanza."""
    base = os.path.realpath(raiz)
    real = os.path.realpath(os.path.join(base, rel))
    if real != base and not real.startswith(base + os.sep):
        return None, f"{rel}: apunta fuera de la raíz; no se lee"
    try:
        if not os.path.isfile(real):
            return None, None
        if os.path.getsize(real) > tope:
            return None, f"{rel}: supera {tope // 1024} KB; no se lee entero"
        with open(real, "rb") as f:
            return f.read(), None
    except OSError:
        return None, f"{rel}: no se pudo leer"


def _no(nombre: str) -> None:
    raise ValueError(nombre)


def jsonl(crudo: bytes) -> tuple[list[dict[str, Any]], int]:
    """Objetos de un JSONL y cuántas líneas no se pudieron leer (una escritura a medias, basura, NaN…)."""
    objetos, ilegibles = [], 0
    for parte in crudo.split(b"\n"):
        if not parte.strip():
            continue
        try:
            obj = json.loads(parte.decode("utf-8"), parse_constant=_no)
        except (ValueError, UnicodeDecodeError):
            ilegibles += 1
            continue
        if isinstance(obj, dict):
            objetos.append(obj)
    return objetos, ilegibles


def mtime_dia(raiz: Path, rel: str) -> str | None:
    """Fecha (AAAA-MM-DD, UTC) de la última modificación de un archivo, o ``None``."""
    try:
        st = os.stat(os.path.join(os.path.realpath(raiz), rel))
    except OSError:
        return None
    return dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).strftime("%Y-%m-%d")


def sha256_de(raiz: Path, rel: str, tope: int = 8 * 1024 * 1024) -> str | None:
    crudo, _ = leer(raiz, rel, tope)
    return hashlib.sha256(crudo).hexdigest() if crudo is not None else None


# ── fechas ───────────────────────────────────────────────────────────────────────────────────────────
def dia(valor: Any) -> int | None:
    """Fecha ISO (solo el día) como número de días desde 1970 (UTC); ``None`` si no es una fecha real."""
    if not isinstance(valor, str):
        return None
    m = RX_FECHA.match(valor)
    if not m:
        return None
    try:
        return (dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) - dt.date(1970, 1, 1)).days
    except ValueError:
        return None


def hoy_de(ahora: dt.datetime | None = None) -> int:
    momento = (ahora or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    return (momento.date() - dt.date(1970, 1, 1)).days


def iso_de_dia(n: int) -> str:
    return (dt.date(1970, 1, 1) + dt.timedelta(days=n)).isoformat()


def parsear_ahora(texto: str | None) -> dt.datetime | None:
    if not texto:
        return None
    return dt.datetime.strptime(texto, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


# ── lista única: se pliega igual que el panel ────────────────────────────────────────────────────────
def plegar_bitacora(objetos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Una entrada por id: el alta con el último estado que le pusieron las líneas ``estado`` (en el orden del archivo). No cambia nada del archivo."""
    altas: dict[str, dict[str, Any]] = {}
    for o in objetos:
        pid = o.get("id")
        if not isinstance(pid, str) or not RX_ID_PUL.fullmatch(pid):
            continue
        if o.get("evento") == "alta" or isinstance(o.get("titulo"), str):
            altas[pid] = dict(o)
            if altas[pid].get("estado") not in ESTADOS_PUL:
                altas[pid]["estado"] = "abierta"
        elif pid in altas and o.get("estado") in ESTADOS_PUL:
            altas[pid]["estado"] = o["estado"]
    return list(altas.values())


def decisiones_vigentes(objetos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Decisiones guardadas que siguen rigiendo: no marcadas como no vigentes y no reemplazadas por una línea posterior."""
    reemplazadas = {o.get("reemplaza") for o in objetos if o.get("reemplaza")}
    return [o for o in objetos if o.get("vigente") is not False and o.get("id") not in reemplazadas]


def preferencias_vigentes(objetos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Preferencias APROBADAS por el dueño y no revocadas. Una línea de otro autor, de otro tipo o sin criterio no cuenta: ninguna propuesta rige."""
    revocadas = {o.get("revoca") for o in objetos if o.get("estado") == "revocada" and o.get("autor") == "dueno"}
    return [o for o in objetos if o.get("estado") == "aprobada" and o.get("autor") == "dueno" and o.get("tipo") == "preferencia"
            and isinstance(o.get("criterio"), str) and isinstance(o.get("id"), str) and o["id"] not in revocadas and o.get("vigente") is not False]


def cargar_memoria(raiz: Path) -> dict[str, Any]:
    """Toda la memoria legible en un diccionario (solo lectura). Los avisos dicen qué faltó o venía roto; nunca lanza."""
    avisos: list[str] = []
    salida: dict[str, Any] = {"avisos": avisos, "existe": {}}
    for clave, rel in (("pulido", REL_PULIDO), ("decisiones", REL_DECISIONES), ("lecciones", REL_LECCIONES), ("preferencias", REL_PREFERENCIAS)):
        crudo, aviso = leer(raiz, rel, TOPE_JSONL)
        if aviso:
            avisos.append(aviso)
        objetos, ilegibles = jsonl(crudo) if crudo is not None else ([], 0)
        if ilegibles:
            avisos.append(f"{rel}: {ilegibles} línea(s) ilegibles (¿escritura a medias?)")
        salida["existe"][clave] = crudo is not None
        salida[f"{clave}_lineas"] = objetos
    salida["pulido"] = plegar_bitacora(salida.pop("pulido_lineas"))
    salida["decisiones"] = salida.pop("decisiones_lineas")
    salida["lecciones"] = salida.pop("lecciones_lineas")
    salida["preferencias"] = salida.pop("preferencias_lineas")
    return salida


# ── texto: normalizar y parecido ─────────────────────────────────────────────────────────────────────
def normal(texto: str) -> str:
    s = unicodedata.normalize("NFKD", texto.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def similitud(a: str, b: str) -> float:
    """Parecido 0-1 entre dos textos (sin tildes, mayúsculas ni signos): lo mayor entre la razón de secuencia y el solapamiento de palabras.

    Es la MISMA cuenta que ``guardar_pendiente.similitud`` (la prueba compara ambas): lo que el cierre llama repetido, el jardinero lo llama duplicado."""
    na, nb = normal(a), normal(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    palabras_a, palabras_b = set(na.split()), set(nb.split())
    jaccard = len(palabras_a & palabras_b) / len(palabras_a | palabras_b)
    return round(max(difflib.SequenceMatcher(None, na, nb).ratio(), jaccard), 3)
