"""Adaptador de Impultienda (impultienda.ar): el de referencia, con el que corre la fábrica original.

Lecturas por el conector MCP de Impultienda; lo que el conector no tiene (archivar tienda, Envío masivo de carritos) va por
el panel con el navegador. Las respuestas crudas que entiende están en tienda/muestras/impultienda/.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from tienda.contrato import Tienda

DOMINIO = "impultienda.ar"


def _n(x: Any) -> int:
    try:
        return int(float(x)) if x not in (None, "") else 0
    except (TypeError, ValueError):
        return 0


class Adaptador(Tienda):
    nombre = "impultienda"
    # Medido con las peticiones reales de una landing y un checkout (14-nov).
    bloqueos_medicion = ("sb.impultienda.ar/rest/v1/visits",                 # visitas y checkouts de las estadísticas y del abandono
                         "sb.impultienda.ar/rest/v1/rpc/live_session_ping",  # «visitantes en vivo»
                         "sb.impultienda.ar/functions/v1/meta-track-event")  # API de conversiones desde el servidor
    bloqueos_terceros = ("clarity.ms", "t.whop.tw/conversions", "segapi.whop.com")
    neto_por_defecto = 0.919   # Impul Pay, medido el 13-nov

    def url_landing(self, tienda: str, vista: str = "") -> str:
        return f"https://{tienda}.{DOMINIO}/{vista}"

    def url_checkout(self, tienda: str, tienda_id: str | None = None, pais: str | None = None, vista_previa: bool = False) -> str:
        base = f"https://{tienda}.{DOMINIO}/checkout"
        if vista_previa and tienda_id:
            return f"{base}?store_id={tienda_id}&edit=1&tpl=default&extop=0&paylast=0" + (f"&preview_country={pais}" if pais else "")
        return base + (f"?store_id={tienda_id}" if tienda_id else "")

    def url_panel(self, tienda: str, seccion: str = "configuracion") -> str:
        return f"https://{DOMINIO}/dashboard/{tienda}/{seccion}"

    def tienda_de_url(self, url: str) -> str | None:
        host = (urlparse(url).hostname or "").lower()
        if host.endswith("." + DOMINIO):
            sub = host[: -len(DOMINIO) - 1]
            return sub if sub and sub not in ("sb", "www") else None
        return None

    def ventas(self, crudo: Any) -> list[dict]:
        v = crudo.get("ventas") if isinstance(crudo, dict) and "ventas" in crudo else crudo
        if isinstance(v, dict):
            v = (v.get("structuredContent") or v)
            v = (v.get("detalle") or {}).get("ventas") or v.get("ventas")
        out = []
        for x in v or []:
            if not isinstance(x, dict) or not str(x.get("orden") or "").strip():
                continue
            est = str(x.get("estado") or x.get("status") or "aprobada").lower()
            estado = ("reembolsada" if est in ("refunded", "reembolsada", "chargeback") else
                      "pendiente" if est in ("pending", "pendiente") else
                      "rechazada" if est in ("rejected", "rechazada", "failed") else "aprobada")
            try:
                total = round(float(x.get("total") or 0), 2)
            except (TypeError, ValueError):
                total = 0.0
            out.append({"orden": str(x["orden"]), "fecha": str(x.get("fecha") or x.get("creada") or ""), "total": total,
                        "moneda": str(x.get("moneda") or "USD").upper()[:3], "post_compra": bool(x.get("post_compra")),
                        "estado": estado})
        return out

    def embudo(self, crudo: Any) -> dict:
        st = crudo.get("structuredContent", crudo) if isinstance(crudo, dict) else {}
        v = st.get("visitas") or {}
        return {"landing": _n(v.get("landing")), "checkout": _n(v.get("checkout")), "compras": _n((st.get("ventas") or {}).get("cantidad"))}

    def cobro(self, crudo: Any) -> dict:
        c = crudo.get("structuredContent", crudo) if isinstance(crudo, dict) else {}
        metodos = [str(x.get("pasarela")) for x in c.get("pasarelas") or [] if isinstance(x, dict) and x.get("operativa")]
        return {"puede_cobrar": bool(c.get("puede_cobrar")), "metodos": metodos}

    def como(self, op: str) -> dict:
        return COMO.get(op, {"via": "no_aplica", "notas": "operación desconocida"})

    def neto_estimado(self) -> float:
        try:
            from tienda import regla
            return float(regla("impulpay.neto_estimado", self.neto_por_defecto))
        except Exception:  # noqa: BLE001
            return self.neto_por_defecto


def _m(herramienta: str, notas: str = "") -> dict:
    return {"via": "mcp", "herramienta": f"impultienda_{herramienta}", "notas": notas}


COMO = {
    "listar_tiendas": _m("listar_tiendas"),
    "listar_ventas": _m("listar_ventas", "por tienda; hoy y ayer en cada vuelta de la vigilancia"),
    "estadisticas": _m("estadisticas", "store_id, desde = hasta = AAAA-MM-DD, comparar_anterior=false"),
    "estado_cobro": _m("estado_pasarela"),
    "carritos_abandonados": _m("carritos_abandonados"),
    "crear_tienda": _m("crear_tienda"),
    "crear_producto": _m("crear_producto", "después impultienda_fijar_precio e impultienda_precio_por_pais"),
    "cargar_entregable": _m("cargar_entregable", "PDF por PUT firmado (impultienda_link_subida_recursos)"),
    "guardar_landing": _m("guardar_html", "editor «HTML completo»; variables {{price}} y {{original_price}}"),
    "configurar_checkout": _m("configurar_checkout", "y impultienda_disenar_checkout / impultienda_bloques_checkout"),
    "configurar_pixel": _m("configurar_tracking", "píxel propio de la oferta + token de la API de conversiones"),
    "agregar_bump": _m("agregar_item_embudo", "con «Agregar bono» si es un bono"),
    "agregar_upsell": _m("agregar_oferta_postcompra", "después impultienda_conectar_oferta_postcompra y configurar_downsell"),
    "repesca_carritos": {"via": "navegador", "pantalla": "Ventas → Carritos abandonados → «Envío masivo»",
                         "notas": "el conector no tiene la acción"},
    "archivar_tienda": {"via": "navegador", "pantalla": "Configuración → Zona de peligro → «Eliminar tienda» (archiva)",
                        "notas": "el conector no tiene la acción"},
}
