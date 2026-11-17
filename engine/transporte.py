"""Transporte HTTP inyectable: nada del proyecto abre una conexión por su cuenta.

Todo cliente de un servicio externo (Meta, Stripe, Cloudflare, correo) recibe un objeto que cumple
el protocolo :class:`Transporte`. En producción lo implementa un cliente HTTP real (lo aporta el
componente que lo necesita); en pruebas y en el modo ``fixture`` se usa :class:`TransporteFixture`,
que responde con datos de ``tests/fixtures/`` y NUNCA abre un socket.

``TransporteFixture`` registra cada llamada (con las cabeceras de credenciales ocultas) para que las
pruebas comprueben qué se habría enviado, y permite secuencias como «falla el segundo POST».
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol, Sequence, runtime_checkable

from engine import comun
from engine.errores import ErrorExterno, ErrorValidacion

__all__ = ["LlamadaRegistrada", "Respuesta", "Transporte", "TransporteFixture"]

_ESTADO_POR_DEFECTO = 200
_ESTADO_OK_DESDE, _ESTADO_OK_HASTA = 200, 300  # [desde, hasta)
_CABECERAS_SECRETAS = re.compile(r"authorization|token|secret|signature|api[-_]?key|cookie|proof", re.IGNORECASE)


@dataclass(frozen=True)
class Respuesta:
    """Respuesta HTTP: código ``estado``, ``cabeceras`` y ``cuerpo`` en bytes."""

    estado: int
    cabeceras: Mapping[str, str] = field(default_factory=dict)
    cuerpo: bytes = b""

    @property
    def texto(self) -> str:
        """Cuerpo como texto UTF-8."""
        return self.cuerpo.decode("utf-8")

    def json(self) -> Any:
        """Cuerpo interpretado como JSON; ``ErrorExterno`` si no lo es."""
        try:
            return json.loads(self.cuerpo.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise ErrorExterno("la respuesta no es JSON válido") from exc

    @property
    def ok(self) -> bool:
        """``True`` si el código está en 200-299."""
        return _ESTADO_OK_DESDE <= self.estado < _ESTADO_OK_HASTA


@runtime_checkable
class Transporte(Protocol):
    """Contrato mínimo de un cliente HTTP inyectable.

    ``solicitar`` envía una petición y devuelve la :class:`Respuesta`. Un fallo de red o un tiempo
    de espera agotado se informa con ``ErrorExterno`` (código 6). ``timeout_s`` es en segundos enteros.
    """

    def solicitar(self, metodo: str, url: str, *, cabeceras: Mapping[str, str], cuerpo: bytes | None,
                  timeout_s: int) -> Respuesta:
        """Envía la petición y devuelve la respuesta; ``ErrorExterno`` ante falla de red o tiempo agotado."""
        ...


@dataclass(frozen=True)
class LlamadaRegistrada:
    """Una llamada recibida por :class:`TransporteFixture` (cabeceras de credenciales ya ocultas)."""

    metodo: str
    url: str
    cabeceras: Mapping[str, str]
    cuerpo: bytes | None
    timeout_s: int

    def json(self) -> Any:
        """Cuerpo enviado interpretado como JSON (``None`` si no había cuerpo)."""
        return None if self.cuerpo is None else json.loads(self.cuerpo.decode("utf-8"))


class TransporteFixture:
    """Transporte de pruebas: responde según reglas en orden y registra las llamadas. No usa red.

    Cada regla es un mapa con:

    * ``metodo`` (``GET``, ``POST``…) y ``url`` (exacta) o ``url_prefijo``;
    * ``estado`` (por defecto 200), ``cabeceras`` y ``cuerpo`` (objeto JSON, texto o bytes), o
      ``cuerpo_archivo`` (ruta relativa a la carpeta de fixtures) para respuestas grabadas;
    * ``veces`` (cuántas llamadas atiende; por defecto una; ``0`` = ilimitadas);
    * ``error`` = ``"tiempo_agotado"`` o ``"red"`` para simular una falla (lanza ``ErrorExterno``).

    Las reglas se prueban en el orden dado y una regla agotada se salta: así «el primer POST va bien
    y el segundo falla» se escribe con dos reglas de una vez cada una. Sin regla aplicable lanza
    ``ErrorExterno`` (una prueba nunca recibe una respuesta inventada).
    """

    def __init__(self, reglas: Iterable[Mapping[str, Any]] = (), *, carpeta: Path | None = None) -> None:
        self._reglas: list[dict[str, Any]] = []
        self._carpeta = Path(carpeta) if carpeta is not None else None
        self.llamadas: list[LlamadaRegistrada] = []
        for regla in reglas:
            self.agregar(regla)

    @classmethod
    def desde_archivo(cls, ruta: Path | str) -> "TransporteFixture":
        """Carga las reglas de un JSON/YAML (lista de reglas o ``{"reglas": [...]}``) bajo ``tests/fixtures/``."""
        ruta = Path(ruta)
        datos = comun.cargar_yaml(ruta) if ruta.suffix in (".yaml", ".yml") else comun.cargar_json(ruta)
        reglas = datos.get("reglas") if isinstance(datos, dict) else datos
        if not isinstance(reglas, list):
            raise ErrorValidacion(f"{ruta.name}: se esperaba una lista de reglas")
        return cls(reglas, carpeta=ruta.parent)

    def agregar(self, regla: Mapping[str, Any]) -> None:
        """Agrega una regla al final (ver la clase para los campos)."""
        if not isinstance(regla, Mapping) or "metodo" not in regla or not ("url" in regla or "url_prefijo" in regla):
            raise ErrorValidacion("regla de fixture: exige «metodo» y «url» o «url_prefijo»")
        copia = dict(regla)
        copia["metodo"] = str(copia["metodo"]).upper()
        veces = copia.get("veces", 1)
        if isinstance(veces, bool) or not isinstance(veces, int) or veces < 0:
            raise ErrorValidacion("regla de fixture: «veces» debe ser un entero >= 0")
        copia["_restantes"] = veces
        copia["_ilimitada"] = veces == 0
        self._reglas.append(copia)

    def _cuerpo(self, regla: Mapping[str, Any]) -> bytes:
        """Cuerpo de la respuesta de una regla, en bytes."""
        if "cuerpo_archivo" in regla:
            if self._carpeta is None:
                raise ErrorValidacion("«cuerpo_archivo» exige construir el fixture con una carpeta")
            destino = (self._carpeta / str(regla["cuerpo_archivo"])).resolve()
            if self._carpeta.resolve() not in destino.parents:
                raise ErrorValidacion("«cuerpo_archivo» sale de la carpeta de fixtures")
            return destino.read_bytes()
        cuerpo = regla.get("cuerpo", b"")
        if isinstance(cuerpo, (bytes, bytearray)):
            return bytes(cuerpo)
        if isinstance(cuerpo, str):
            return cuerpo.encode("utf-8")
        return comun.json_canonico(cuerpo)

    def solicitar(self, metodo: str, url: str, *, cabeceras: Mapping[str, str], cuerpo: bytes | None,
                  timeout_s: int) -> Respuesta:
        """Registra la llamada y devuelve la respuesta de la primera regla aplicable (sin tocar la red)."""
        visibles = {k: ("****" if _CABECERAS_SECRETAS.search(k) else v) for k, v in (cabeceras or {}).items()}
        self.llamadas.append(LlamadaRegistrada(metodo.upper(), url, visibles, cuerpo, timeout_s))
        for regla in self._reglas:
            if regla["metodo"] != metodo.upper() or (not regla["_ilimitada"] and regla["_restantes"] <= 0):
                continue
            if "url" in regla and regla["url"] != url:
                continue
            if "url_prefijo" in regla and not url.startswith(str(regla["url_prefijo"])):
                continue
            if not regla["_ilimitada"]:
                regla["_restantes"] -= 1
            falla = regla.get("error")
            if falla == "tiempo_agotado":
                raise ErrorExterno("tiempo de espera agotado (simulado por el fixture)")
            if falla == "red":
                raise ErrorExterno("falla de red (simulada por el fixture)")
            if falla is not None:
                raise ErrorValidacion(f"regla de fixture: error desconocido {falla!r}")
            return Respuesta(int(regla.get("estado", _ESTADO_POR_DEFECTO)), dict(regla.get("cabeceras", {})), self._cuerpo(regla))
        raise ErrorExterno(f"TransporteFixture: sin respuesta grabada para {metodo.upper()} {url}")

    def llamadas_a(self, metodo: str | None = None, url_prefijo: str = "") -> Sequence[LlamadaRegistrada]:
        """Llamadas recibidas filtradas por método y prefijo de URL (para las aserciones de las pruebas)."""
        return [c for c in self.llamadas if (metodo is None or c.metodo == metodo.upper()) and c.url.startswith(url_prefijo)]

    def pendientes(self) -> list[dict[str, Any]]:
        """Reglas con llamadas sin consumir (una prueba estricta puede exigir que no queden)."""
        return [r for r in self._reglas if not r["_ilimitada"] and r["_restantes"] > 0]
