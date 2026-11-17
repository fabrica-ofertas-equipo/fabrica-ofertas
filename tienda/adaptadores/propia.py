"""Adaptador de la tienda propia (infra/workers/tienda-propia): para quien no usa Impultienda ni otra plataforma.

Landing en https://<dominio>/<slug>/, checkout de Stripe con bump, entrega del PDF por correo. Las lecturas y la publicación
van por la API del worker con `python3 -m tienda.propia …` (usa FABRICA_TIENDA_URL y FABRICA_TIENDA_TOKEN del .env).
Lo que no tiene todavía: oferta después del pago (upsell de un clic). Se reemplaza con el bump.
"""
from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlparse

from tienda.contrato import Tienda


def base_url() -> str:
    return (os.environ.get("FABRICA_TIENDA_URL") or "https://tienda.tu-dominio.com").rstrip("/")


class Adaptador(Tienda):
    nombre = "propia"
    bloqueos_medicion = ("/_m/",)
    bloqueos_terceros = ()
    neto_por_defecto = 0.95   # Stripe ≈ 2,9 % + 0,30 USD; con 19 USD queda ≈ 0,955

    def url_landing(self, tienda: str, vista: str = "") -> str:
        return f"{base_url()}/{tienda}/{vista}"

    def url_checkout(self, tienda: str, tienda_id: str | None = None, pais: str | None = None, vista_previa: bool = False) -> str:
        return f"{base_url()}/{tienda}/checkout"

    def url_panel(self, tienda: str, seccion: str = "configuracion") -> str:
        return "https://dashboard.stripe.com/payments"

    def tienda_de_url(self, url: str) -> str | None:
        u, b = urlparse(url), urlparse(base_url())
        if (u.hostname or "").lower() != (b.hostname or "").lower():
            return None
        partes = [p for p in u.path.split("/") if p]
        return partes[0] if partes and partes[0] not in ("api", "_m", "stripe") else None

    def ventas(self, crudo: Any) -> list[dict]:
        filas = crudo.get("ventas") if isinstance(crudo, dict) else crudo
        return [{"orden": str(x["orden"]), "fecha": str(x.get("fecha") or ""), "total": round(float(x.get("total") or 0), 2),
                 "moneda": str(x.get("moneda") or "USD").upper(), "post_compra": bool(x.get("post_compra")),
                 "estado": str(x.get("estado") or "aprobada")}
                for x in filas or [] if isinstance(x, dict) and x.get("orden")]

    def embudo(self, crudo: Any) -> dict:
        c = crudo if isinstance(crudo, dict) else {}
        return {k: int(c.get(k) or 0) for k in ("landing", "checkout", "compras")}

    def como(self, op: str) -> dict:
        return COMO.get(op, {"via": "no_aplica", "notas": "operación desconocida"})


def _s(cmd: str, notas: str = "") -> dict:
    return {"via": "script", "ruta": f"python3 -m tienda.propia {cmd}", "notas": notas}


COMO = {
    "listar_tiendas": _s("tiendas"),
    "listar_ventas": _s("ventas --tienda <slug> --desde AAAA-MM-DD --hasta AAAA-MM-DD"),
    "estadisticas": _s("estadisticas --tienda <slug> --fecha AAAA-MM-DD"),
    "estado_cobro": _s("cobro"),
    "carritos_abandonados": _s("carritos --tienda <slug>"),
    "crear_tienda": _s("publicar --tienda <slug> --nombre <n> --precio <p> --moneda USD --idioma es", "crea o actualiza"),
    "crear_producto": _s("publicar --tienda <slug> --nombre <n> --precio <p> --precio-original <p2>", "producto = tienda (uno por tienda)"),
    "cargar_entregable": _s("publicar --tienda <slug> --entregable <url pública del PDF>", "subir el PDF a R2 o a cualquier almacenamiento con enlace"),
    "guardar_landing": _s("publicar --tienda <slug> --html <archivo.html>", "variables {{price}}, {{original_price}} y {{checkout_url}}"),
    "configurar_checkout": _s("publicar --tienda <slug> --idioma <xx>", "checkout simple; el pago lo muestra Stripe en el idioma del comprador"),
    "configurar_pixel": _s("publicar --tienda <slug> --pixel <id>", "PageView e InitiateCheckout desde el navegador; Purchase: activar la integración de Stripe con Meta"),
    "agregar_bump": _s("publicar --tienda <slug> --bump-nombre <n> --bump-precio <p> --bump-entregable <url>"),
    "agregar_upsell": {"via": "no_aplica", "notas": "la tienda propia no tiene oferta después del pago: usar el bump"},
    "repesca_carritos": _s("repesca [--tienda <slug>]", "manda el enlace de recuperación de Stripe a los carritos vencidos"),
    "archivar_tienda": _s("publicar --tienda <slug> --archivar"),
}
