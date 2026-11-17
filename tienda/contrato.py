"""Contrato de tienda: lo que la fábrica necesita de cualquier plataforma donde se venda (Impultienda, Hotmart, Kiwify,
una tienda propia con Stripe, la que sea).

La fábrica nunca habla directo con una plataforma. Habla con este contrato, y un ADAPTADOR (tienda/adaptadores/<nombre>.py)
lo traduce a la plataforma real. Para sumar una plataforma nueva no se toca la fábrica: se escribe un adaptador y se
comprueba con `python3 -m tienda.conformidad <nombre>` (lo hace la skill conectar-tienda).

Dos tipos de operaciones:
  - LECTURAS: el agente pide el dato a la plataforma (conector MCP, API o navegador) y el adaptador convierte la respuesta
    cruda en la forma normal de abajo (Venta, Embudo, Cobro). Los scripts solo ven la forma normal.
  - ACCIONES: las hace el agente (crear tienda, subir la landing, cargar el PDF…). El adaptador dice CÓMO en `como(op)`:
    qué herramienta, endpoint o pantalla usar. Las skills consultan eso en vez de nombrar una plataforma.

Formas normales:
  Venta   {"orden": str, "fecha": ISO-8601, "total": float, "moneda": "USD", "post_compra": bool, "estado": "aprobada"}
  Embudo  {"landing": int, "checkout": int, "compras": int}       (visitas a la landing, inicios de pago, pagos aprobados)
  Cobro   {"puede_cobrar": bool, "metodos": [str]}
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

# id → (tipo, qué hace). Es la lista cerrada que todo adaptador tiene que cubrir en `como()`.
OPERACIONES: dict[str, tuple[str, str]] = {
    # lecturas (el adaptador normaliza la respuesta)
    "listar_tiendas": ("lectura", "tiendas de la cuenta con su identificador y su dirección pública"),
    "listar_ventas": ("lectura", "ventas aprobadas de una tienda en un rango de fechas → [Venta]"),
    "estadisticas": ("lectura", "visitas a la landing, inicios de pago y compras de una tienda en un día → Embudo"),
    "estado_cobro": ("lectura", "si la tienda puede cobrar y con qué medios → Cobro"),
    "carritos_abandonados": ("lectura", "pagos iniciados que no terminaron (para la repesca)"),
    # acciones (las hace el agente con lo que diga `como`)
    "crear_tienda": ("accion", "tienda nueva con su subdominio, idioma y moneda"),
    "crear_producto": ("accion", "producto principal con nombre, precio y precio original tachado"),
    "cargar_entregable": ("accion", "subir el PDF que recibe el comprador por correo"),
    "guardar_landing": ("accion", "publicar el HTML completo de la landing (con variables de precio)"),
    "configurar_checkout": ("accion", "diseño, campos, sellos e idioma del checkout"),
    "configurar_pixel": ("accion", "píxel de Meta y API de conversiones de la tienda"),
    "agregar_bump": ("accion", "oferta en el mismo checkout (order bump)"),
    "agregar_upsell": ("accion", "oferta después del pago, con su rebaja si la rechazan"),
    "repesca_carritos": ("accion", "mandar el correo de recuperación con descuento a los carritos abandonados"),
    "archivar_tienda": ("accion", "archivar o eliminar una tienda de una oferta cerrada"),
}

VIAS = {"mcp", "api", "navegador", "script", "no_aplica"}


class Tienda(ABC):
    """Lo que implementa cada adaptador. Todo es sin red salvo que el adaptador diga lo contrario."""

    nombre: str = ""
    # Peticiones que una prueba automática del funnel debe bloquear para no ensuciar las estadísticas de la plataforma
    # (visitas, inicios de pago, eventos que la plataforma manda a Meta desde su servidor).
    bloqueos_medicion: tuple[str, ...] = ()
    # Lo que se bloquea de terceros que la plataforma mete en sus páginas (grabaciones, medición de la pasarela).
    bloqueos_terceros: tuple[str, ...] = ()
    neto_por_defecto: float = 0.9   # fracción del bruto que llega después de comisiones e impuestos (estimado)

    # ── direcciones ──
    @abstractmethod
    def url_landing(self, tienda: str, vista: str = "") -> str:
        """Dirección pública de la landing de una tienda. `vista` es lo que va después de la barra (p. ej. «?v=ficha»)."""

    @abstractmethod
    def url_checkout(self, tienda: str, tienda_id: str | None = None, pais: str | None = None, vista_previa: bool = False) -> str:
        """Dirección del checkout. Con vista_previa y pais, la vista «como la ve un comprador de ese país» si existe."""

    def url_panel(self, tienda: str, seccion: str = "configuracion") -> str:
        """Pantalla del panel de la plataforma para que el dueño haga algo a mano."""
        return self.url_landing(tienda)

    @abstractmethod
    def tienda_de_url(self, url: str) -> str | None:
        """Qué tienda es la dueña de una dirección (None si la dirección no es de esta plataforma)."""

    # ── lecturas: crudo → forma normal ──
    @abstractmethod
    def ventas(self, crudo: Any) -> list[dict]:
        """Respuesta cruda de `listar_ventas` → [Venta]."""

    @abstractmethod
    def embudo(self, crudo: Any) -> dict:
        """Respuesta cruda de `estadisticas` → Embudo."""

    def cobro(self, crudo: Any) -> dict:
        """Respuesta cruda de `estado_cobro` → Cobro."""
        c = crudo if isinstance(crudo, dict) else {}
        return {"puede_cobrar": bool(c.get("puede_cobrar")), "metodos": [str(m) for m in c.get("metodos") or []]}

    # ── acciones ──
    @abstractmethod
    def como(self, op: str) -> dict:
        """Cómo se hace una operación en esta plataforma: {"via": mcp|api|navegador|script|no_aplica, "herramienta" o
        "ruta" o "pantalla", "notas"}. Las skills lo leen con `python3 -m tienda como <op>`."""

    def neto_estimado(self) -> float:
        """Fracción neta del bruto. Si el dueño la midió, manda reglas.json → `<nombre>.neto_estimado`."""
        return self.neto_por_defecto


# ── validación de formas normales (la usan los scripts y las pruebas de conformidad) ──
def _num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def problemas_venta(v: Any) -> list[str]:
    if not isinstance(v, dict):
        return ["la venta no es un objeto"]
    out = []
    if not isinstance(v.get("orden"), str) or not v["orden"]:
        out.append("falta «orden» (texto)")
    if not isinstance(v.get("fecha"), str) or len(v.get("fecha") or "") < 10:
        out.append("falta «fecha» ISO-8601")
    if not _num(v.get("total")) or v["total"] < 0:
        out.append("«total» tiene que ser un número ≥ 0")
    if not isinstance(v.get("moneda"), str) or len(v.get("moneda") or "") != 3:
        out.append("«moneda» tiene que ser un código de 3 letras")
    if not isinstance(v.get("post_compra"), bool):
        out.append("«post_compra» tiene que ser verdadero o falso")
    if v.get("estado") not in ("aprobada", "reembolsada", "pendiente", "rechazada"):
        out.append("«estado» tiene que ser aprobada, reembolsada, pendiente o rechazada")
    return out


def problemas_embudo(e: Any) -> list[str]:
    if not isinstance(e, dict):
        return ["el embudo no es un objeto"]
    return [f"«{k}» tiene que ser un entero ≥ 0" for k in ("landing", "checkout", "compras")
            if not isinstance(e.get(k), int) or isinstance(e.get(k), bool) or e[k] < 0]


def problemas_cobro(c: Any) -> list[str]:
    if not isinstance(c, dict):
        return ["el cobro no es un objeto"]
    out = []
    if not isinstance(c.get("puede_cobrar"), bool):
        out.append("«puede_cobrar» tiene que ser verdadero o falso")
    if not isinstance(c.get("metodos"), list):
        out.append("«metodos» tiene que ser una lista")
    return out
