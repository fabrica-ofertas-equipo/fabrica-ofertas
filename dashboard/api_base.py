"""Base común de los lectores de la API del panel (CONTRATO §4): contexto, sobre y constantes.

Cada lector es una función ``f(ctx, ...) -> Sobre``: nunca lanza por un archivo ausente o corrupto
(devuelve ``vacio=True`` y/o ``avisos``); solo lanza ``ErrorHttp`` ante una petición mal formada o un
recurso inexistente (p. ej. una oferta que no existe → 404).
"""
from __future__ import annotations

import datetime as _dt
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dashboard.archivos import Raiz, iso_z

__all__ = [
    "ARTEFACTOS", "Ctx", "ETAPAS", "NOMBRES_ETAPA", "RX_CORRIDA", "RX_EJECUCION", "RX_OFERTA", "Sobre",
    "VERSION", "ahora_utc", "carpetas_por_id_interno", "exigir_corrida", "exigir_oferta", "ids_de_ofertas", "motor_disponible",
]

VERSION = "1.0.0"

ETAPAS = ["M1", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10"]
NOMBRES_ETAPA = {
    "M1": "Mercados e idiomas", "D1": "Descubrimiento", "D2": "Validación de mercado",
    "D3": "Diseño de la oferta", "D4": "Producto digital", "D5": "Página de venta, pago y medición",
    "D6": "Anuncios (imágenes, videos y textos)", "D7": "Campañas en Meta", "D8": "Ajuste diario de las campañas",
    "D9": "Crecimiento (subir el presupuesto)", "D10": "Entrega y soporte al comprador",
}
# Carpeta (o archivo) de cada etapa dentro de ofertas/<id>/ (docs/_backbone.md, tabla de departamentos).
ARTEFACTOS = {
    "M1": "mercado.json", "D1": "01-descubrimiento", "D2": "02-validacion", "D3": "03-oferta", "D4": "04-producto",
    "D5": "05-landing", "D6": "06-creativos", "D7": "07-campana", "D8": "08-operacion", "D9": "09-escalado",
    "D10": "10-postcompra",
}

RX_OFERTA = re.compile(r"^(OF-[0-9]{6}-[0-9]{2}|_[a-z0-9][a-z0-9_-]{0,31})$")
RX_CORRIDA = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]{1,8}$")
RX_EJECUCION = re.compile(r"^[A-Za-z0-9-]{1,40}$")


def ahora_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


@dataclass
class Ctx:
    """Contexto de lectura: la raíz del repositorio (o una raíz temporal en pruebas) y el reloj."""

    raiz: Path
    ahora: Callable[[], _dt.datetime] = ahora_utc
    puerto: int = 0
    entorno: str = "desarrollo"
    version: str = VERSION
    estado_vigia: Callable[[], dict[str, Any] | None] = field(default=lambda: None, repr=False)
    raiz_confinada: Raiz = field(init=False)

    def __post_init__(self) -> None:
        self.raiz = Path(os.path.realpath(self.raiz))
        self.raiz_confinada = Raiz(self.raiz)

    def iso_ahora(self) -> str:
        return iso_z(self.ahora())

    def empresa(self) -> Raiz:
        return Raiz(self.raiz / "empresa", limite=self.raiz)

    def oferta(self, oferta_id: str) -> Raiz:
        """Carpeta ``ofertas/<id>/`` confinada (no puede ser un enlace que salga de la raíz)."""
        return Raiz(self.raiz / "ofertas" / oferta_id, limite=self.raiz)


@dataclass
class Sobre:
    """Contenido del sobre ``{ok, datos, fuente, generado_en, vacio, avisos}`` (+ claves extra opcionales)."""

    datos: Any
    fuente: list[str] = field(default_factory=list)
    vacio: bool = False
    avisos: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def a_dict(self, generado_en: str) -> dict[str, Any]:
        sobre: dict[str, Any] = {
            "ok": True, "datos": self.datos, "fuente": self.fuente, "generado_en": generado_en,
            "vacio": self.vacio, "avisos": self.avisos,
        }
        sobre.update(self.extra)
        return sobre


def carpetas_por_id_interno(ctx: Ctx) -> dict[str, str]:
    """``{id de oferta (carpeta o ``estado.oferta_id``): carpeta}``; si dos carpetas comparten id interno gana la real sobre la demo.

    Un solo identificador viaja por la API (el de la CARPETA: ``OF-…`` o ``_ejemplo``); el id interno del ``estado.json``
    se expone aparte (``oferta_id_interno``).
    """
    mapa: dict[str, str] = {}
    for carpeta in ids_de_ofertas(ctx):
        mapa.setdefault(carpeta, carpeta)
        lec = ctx.oferta(carpeta).json("estado.json")
        if lec.ok and isinstance(lec.dato, dict) and isinstance(lec.dato.get("oferta_id"), str):
            mapa.setdefault(lec.dato["oferta_id"], carpeta)
    return mapa


def motor_disponible(ctx: Ctx) -> bool:
    """¿Existe ``engine/orq.py``? Si no, los comandos ``python -m engine.orq …`` NO son operativos todavía."""
    return (ctx.raiz / "engine" / "orq.py").is_file()


def exigir_oferta(ctx: Ctx, oferta_id: str) -> Raiz:
    """``Raiz`` de una oferta existente o ``ErrorHttp`` (400 id inválido / 404 inexistente)."""
    from dashboard.seguridad import ErrorHttp  # import tardío: evita ciclo en pruebas aisladas

    if not RX_OFERTA.fullmatch(oferta_id or ""):
        raise ErrorHttp(400, "oferta_invalida", "El código de la oferta no es válido. Tiene que verse así: OF-202611-01.")
    r = ctx.oferta(oferta_id)
    if not Path(r.base).is_dir():
        raise ErrorHttp(404, "oferta_no_encontrada", "No encontramos esa oferta. Revisa el código o elígela desde la lista de ofertas.")
    return r


def exigir_corrida(corrida: str) -> str:
    from dashboard.seguridad import ErrorHttp

    if not RX_CORRIDA.fullmatch(corrida or ""):
        raise ErrorHttp(400, "corrida_invalida", "El código del barrido (corrida) no es válido. Tiene que ser la fecha y una letra, por ejemplo 2026-11-06-a.")
    return corrida


def ids_de_ofertas(ctx: Ctx) -> list[str]:
    """Identificadores de las carpetas de ``ofertas/`` (reales ordenadas primero; demo ``_…`` al final)."""
    nombres = [n for n in ctx.raiz_confinada.listar("ofertas", solo="dir") if RX_OFERTA.fullmatch(n)]
    return sorted(n for n in nombres if not n.startswith("_")) + sorted(n for n in nombres if n.startswith("_"))
