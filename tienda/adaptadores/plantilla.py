"""PLANTILLA para conectar una plataforma nueva (Hotmart, Kiwify, Gumroad, Lemon Squeezy, Shopify, Mercado Pago…).

Pasos (los hace la skill conectar-tienda; no hace falta saber programar):
  1. Copiar este archivo a tienda/adaptadores/<plataforma>.py y cambiar `nombre`.
  2. Guardar en tienda/muestras/<plataforma>/ respuestas REALES de la plataforma (sin datos de compradores):
       ventas.json        lo que devuelve la lista de ventas, y ventas.esperado.json con la forma normal
       estadisticas.json  visitas / checkouts / compras de un día, y estadisticas.esperado.json
       urls.json          {"landing": "<url real de una landing>", "tienda": "<identificador de esa tienda>"}
  3. Completar cada método hasta que pase: python3 -m tienda.conformidad <plataforma>
  4. Poner {"plataforma": "<plataforma>"} en tienda/config.json.
Si la plataforma no mide visitas, `embudo` devuelve lo que tenga y `como("estadisticas")` lo explica en «notas».
"""
from __future__ import annotations

from typing import Any

from tienda.contrato import Tienda


class Adaptador(Tienda):
    nombre = "plantilla"
    bloqueos_medicion: tuple[str, ...] = ()   # fragmentos de URL de las peticiones que cuentan visitas o mandan eventos
    neto_por_defecto = 0.9

    def url_landing(self, tienda: str, vista: str = "") -> str:
        raise NotImplementedError("dirección pública de la landing")

    def url_checkout(self, tienda: str, tienda_id: str | None = None, pais: str | None = None, vista_previa: bool = False) -> str:
        raise NotImplementedError("dirección del checkout")

    def tienda_de_url(self, url: str) -> str | None:
        raise NotImplementedError("de qué tienda es una dirección")

    def ventas(self, crudo: Any) -> list[dict]:
        raise NotImplementedError("respuesta de ventas → [Venta]")

    def embudo(self, crudo: Any) -> dict:
        raise NotImplementedError("respuesta de estadísticas → Embudo")

    def como(self, op: str) -> dict:
        return {"via": "no_aplica", "notas": "completar"}
