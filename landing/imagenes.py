"""``landing.imagenes``: de las ranuras de ``assets.json`` a las imágenes que se publican en ``sitio/``.

Una ranura solo se publica si está ``aprobado``, tiene ``archivo`` dentro de ``05-landing/``, el
archivo existe, su ``sha256`` coincide, cumple ``peso_max_kb`` y su extensión es de imagen. Un SVG
no puede llevar ``<script>``, manejadores ``on*``, ``javascript:`` ni referencias externas (se sirve
desde el dominio de la tienda). Ninguna ``<img>`` sale de otro sitio: sin ranura aprobada, la
sección usa su diseño sin imagen o se omite. Las dimensiones salen del propio archivo (PNG, JPEG,
WebP, SVG) y, si no se pueden leer, de ``ancho_px``/``alto_px`` o de la relación de aspecto.

Cada :class:`Imagen` trae ``ilustrativa`` y ``ia_visible`` (``ilustrativa`` y ``etiqueta_ia_visible`` de la ranura): las plantillas los convierten en el pie
«Ilustración orientativa» y en el rótulo de IA, y ``landing.validar`` (``L1-IMAGEN-ROTULO``) comprueba que cada imagen marcada lo lleve. El ``alt`` de una ranura
aprobada tiene que ser REAL (describe lo que se ve): se rechaza un alt corto, genérico o que lleve el id de la ranura.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from scripts import validar_esquemas as V

from engine.errores import ErrorValidacion

__all__ = ["Imagen", "resolver_imagenes"]

EXTENSIONES = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".svg"}
# Ancho base por relación de aspecto cuando el archivo no revela su tamaño (alto = ancho * h / w, entero).
_RATIOS = {"1:1": (1120, 1120), "4:5": (960, 1200), "9:16": (720, 1280), "16:9": (1280, 720), "3:4": (720, 960), "1.91:1": (1200, 630)}
ALT_MIN = 10
_ALT_GENERICOS = frozenset({"imagen", "image", "foto", "photo", "picture", "placeholder", "captura", "imagen del producto", "zdjęcie", "obraz", "obrazek", "immagine",
                            "bono", "bonus", "portada", "cover", "mockup", "hero", "ilustracion", "ilustración", "ilustracja", "illustration"})
_RX_SVG_PELIGROSO = re.compile(r"<\s*script|<\s*foreignObject|\son[a-z]+\s*=|javascript:|(?:href|src)\s*=\s*[\"']\s*(?:https?:)?//|@import|url\(\s*[\"']?\s*(?:https?:)?//", re.I)


@dataclass(frozen=True)
class Imagen:
    """Una imagen aprobada lista para publicar."""

    slot_id: str
    seccion: str
    url: str
    destino: str          # ruta relativa bajo sitio/ (= ``archivo`` de la ranura)
    origen: Path
    ancho: int
    alto: int
    alt: str
    carga: str            # eager | lazy
    ilustrativa: bool = False      # ranura `ilustrativa`: «base de cómo se vería», no la pieza real (J21): se publica con su pie
    ia_visible: bool = False       # ranura `etiqueta_ia_visible`: lleva el rótulo «imagen generada con ayuda de IA»


def _png(b: bytes) -> tuple[int, int] | None:
    if b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= 24:
        return struct.unpack(">II", b[16:24])
    return None


def _jpeg(b: bytes) -> tuple[int, int] | None:
    if b[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(b):
        if b[i] != 0xFF:
            i += 1
            continue
        marca = b[i + 1]
        if marca in (0xD8, 0x01) or 0xD0 <= marca <= 0xD7:
            i += 2
            continue
        largo = struct.unpack(">H", b[i + 2:i + 4])[0]
        if 0xC0 <= marca <= 0xCF and marca not in (0xC4, 0xC8, 0xCC):
            alto, ancho = struct.unpack(">HH", b[i + 5:i + 9])
            return ancho, alto
        i += 2 + largo
    return None


def _webp(b: bytes) -> tuple[int, int] | None:
    if b[:4] != b"RIFF" or b[8:12] != b"WEBP" or len(b) < 30:
        return None
    tipo = b[12:16]
    if tipo == b"VP8 " and b[23:26] == b"\x9d\x01\x2a":
        ancho, alto = struct.unpack("<HH", b[26:30])
        return ancho & 0x3FFF, alto & 0x3FFF
    if tipo == b"VP8L" and b[20] == 0x2F:
        bits = struct.unpack("<I", b[21:25])[0]
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if tipo == b"VP8X":
        return int.from_bytes(b[24:27], "little") + 1, int.from_bytes(b[27:30], "little") + 1
    return None


def _dimensiones(ruta: Path, slot: Mapping[str, Any]) -> tuple[int, int]:
    declarado = (slot.get("ancho_px"), slot.get("alto_px"))
    leido = None
    if ruta.suffix.lower() != ".svg":
        datos = ruta.read_bytes()[:65536]
        leido = _png(datos) or _jpeg(datos) or _webp(datos)
    if leido and leido[0] > 0 and leido[1] > 0:
        return int(leido[0]), int(leido[1])
    if all(isinstance(x, int) and x > 0 for x in declarado):
        return int(declarado[0]), int(declarado[1])
    return _RATIOS.get(slot.get("ratio", ""), (1280, 720))


def comprobar_alt(slot_id: str, alt: str) -> str | None:
    """Motivo por el que ``alt`` no es un texto alternativo real (``None`` si lo es): corto, genérico o con el id de la ranura (un marcador interno, no una descripción)."""
    t = " ".join(str(alt).split())
    if len(t) < ALT_MIN:
        return f"{t!r} tiene menos de {ALT_MIN} caracteres: describe lo que se ve"
    if t.lower().strip(" .:") in _ALT_GENERICOS:
        return f"{t!r} es genérico: describe lo que se ve"
    if re.search(r"(?<![a-z0-9-])" + re.escape(slot_id.lower()) + r"(?![a-z0-9-])", t.lower()):
        return f"contiene el id de la ranura ({slot_id}): es un marcador interno, no una descripción"
    return None


def resolver_imagenes(assets: Mapping[str, Any], dir_landing: Path) -> tuple[dict[str, Imagen], list[str]]:
    """``slot_id -> Imagen`` de las ranuras aprobadas y avisos de las que no se publican.

    Errores (``ErrorValidacion``): archivo ausente o fuera de ``05-landing/``, ``sha256`` distinto,
    peso mayor que ``peso_max_kb``, extensión no admitida o SVG con contenido activo.
    """
    salida: dict[str, Imagen] = {}
    avisos: list[str] = []
    base = dir_landing.resolve()
    for s in assets.get("slots", []):
        sid, estado = s["slot_id"], s.get("estado")
        if estado != "aprobado":
            if estado == "asignado":
                avisos.append(f"ranura {sid}: asignada pero no aprobada; no se publica")
            continue
        archivo = s.get("archivo")
        if not archivo:
            raise ErrorValidacion(f"assets.json: la ranura {sid} está aprobada sin archivo")
        ruta = (base / archivo).resolve()
        if base not in ruta.parents or not ruta.is_file():
            raise ErrorValidacion(f"assets.json: la ranura {sid} apunta a un archivo inexistente o fuera de 05-landing/: {archivo}")
        if ruta.suffix.lower() not in EXTENSIONES:
            raise ErrorValidacion(f"assets.json: la ranura {sid} no es una imagen admitida ({ruta.suffix})")
        if not V.comparar_hash(s["sha256"], V.hash_archivo(ruta, servido=False)):
            raise ErrorValidacion(f"assets.json: el sha256 de la ranura {sid} no coincide con {archivo}")
        if ruta.stat().st_size > int(s["peso_max_kb"]) * 1024:
            raise ErrorValidacion(f"assets.json: {archivo} pesa {ruta.stat().st_size} B y la ranura {sid} admite {s['peso_max_kb']} KB")
        if ruta.suffix.lower() == ".svg" and _RX_SVG_PELIGROSO.search(ruta.read_text(encoding="utf-8", errors="replace")):
            raise ErrorValidacion(f"assets.json: el SVG {archivo} contiene contenido activo o referencias externas")
        motivo_alt = comprobar_alt(sid, s["alt"])
        if motivo_alt:
            raise ErrorValidacion(f"assets.json: el alt de la ranura {sid} no es un texto alternativo real: {motivo_alt}")
        ancho, alto = _dimensiones(ruta, s)
        salida[sid] = Imagen(
            slot_id=sid, seccion=s["seccion"], url="/" + archivo.lstrip("/"), destino=archivo, origen=ruta,
            ancho=ancho, alto=alto, alt=s["alt"], carga=s.get("carga") or ("eager" if s["seccion"] in ("hero", "og") else "lazy"),
            ilustrativa=s.get("ilustrativa") is True, ia_visible=s.get("etiqueta_ia_visible") is True,
        )
    return salida, avisos
