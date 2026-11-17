"""Ayudas compartidas por las pruebas de ``postcompra``.

Reutiliza :mod:`tests.engine.apoyo` (``PruebaBase``, ``crear_empresa``) para no reinventar la raíz
temporal firmada que exige ``engine.guard``: ``postcompra.reembolsar``/``reembolso_manual`` en modo
``fixture`` pasan por los MISMOS 7 pasos que cualquier otra operación con efecto.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from engine import comun
from engine.transporte import TransporteFixture
from tests.engine.apoyo import EmpresaPrueba, PruebaBase, crear_empresa  # noqa: F401  (reexportado para las pruebas)

__all__ = ["PruebaBase", "crear_empresa", "crear_oferta_producto", "dormir_sin_esperar", "refrescar_infra", "reglas_stripe"]

OFERTA = "OF-202611-01"


def dormir_sin_esperar(_segundos: float) -> None:
    """Sustituto de ``time.sleep`` para pruebas: no bloquea de verdad (convenciones §11, sin sleep real)."""
    return None


def refrescar_infra(emp: EmpresaPrueba, ahora: datetime) -> None:
    """Re-firma ``estado.json`` para que quede VERDE y fresco en ``ahora`` (las pruebas de ``postcompra``
    usan instantes muy distintos entre sí; ``crear_empresa`` solo deja fresco el instante fijo de la
    fixture de B1, ``apoyo.GENERADO_EN``)."""
    emp.reescribir_estado(generado_en=comun.iso_z(ahora - timedelta(hours=1)), valido_hasta=comun.iso_z(ahora + timedelta(hours=5)))


def reglas_stripe(session_id: str, *, monto_pagado: int, moneda: str, pagado_en: datetime, payment_intent: str = "pi_test_0001",
                  disputa: bool = False, adid: str | None = "120000000000003", monto_reembolsado_previo: int = 0,
                  reembolsos_existentes: list[dict[str, Any]] | None = None, refund_id: str = "re_test_0001",
                  veces_post_refund: int = 1) -> list[dict[str, Any]]:
    """Reglas de :class:`TransporteFixture` para un cargo de Stripe completo (sesión + payment_intent + refunds)."""
    epoch = int(pagado_en.astimezone(timezone.utc).timestamp())
    reembolsos_existentes = reembolsos_existentes or []
    return [
        {"metodo": "GET", "url": f"https://api.stripe.com/v1/checkout/sessions/{session_id}",
         "cuerpo": {"id": session_id, "payment_intent": payment_intent, "metadata": ({"adid": adid} if adid else {})},
         "veces": 0},
        {"metodo": "GET", "url": f"https://api.stripe.com/v1/payment_intents/{payment_intent}",
         "cuerpo": {"id": payment_intent, "latest_charge": {
             "amount": monto_pagado, "amount_refunded": monto_reembolsado_previo, "currency": moneda.lower(),
             "created": epoch, "dispute": ({"id": "dp_test_0001"} if disputa else None),
         }},
         "veces": 0},
        {"metodo": "GET", "url": f"https://api.stripe.com/v1/refunds?payment_intent={payment_intent}",
         "cuerpo": {"data": reembolsos_existentes}, "veces": 0},
        {"metodo": "POST", "url": "https://api.stripe.com/v1/refunds",
         "cuerpo": {"id": refund_id, "amount": monto_pagado - monto_reembolsado_previo, "currency": moneda.lower(),
                   "metadata": {}},
         "veces": veces_post_refund},
    ]


def crear_oferta_producto(raiz: Path, oferta_id: str = OFERTA) -> dict[str, Any]:
    """Crea ``ofertas/<id>/04-producto/producto.json`` (aprobado, dos ítems en_paquete) y sus archivos.

    Devuelve el ``dict`` del ``producto.json`` escrito (con los ``sha256`` reales de los archivos).
    """
    dir_producto = raiz / "ofertas" / oferta_id / "04-producto"
    dir_entregables = dir_producto / "entregables"
    dir_entregables.mkdir(parents=True, exist_ok=True)
    (dir_entregables / "guia.md").write_text("# Guía de prueba\n\nContenido sintético.\n", encoding="utf-8")
    (dir_entregables / "plantilla.md").write_text("# Plantilla de prueba\n", encoding="utf-8")
    sha_guia = comun.hash_archivo(dir_entregables / "guia.md")
    sha_plantilla = comun.hash_archivo(dir_entregables / "plantilla.md")
    producto = {
        "schema_version": "1.0.0", "producto_id": f"PROD-{oferta_id}", "oferta_id": oferta_id, "version": "v1",
        "origen_version": "qa", "estado": "aprobado",
        "items": [
            {"id": "guia", "tipo": "guia_md", "archivo": "entregables/guia.md", "paginas": None, "peso_mb": "0.01",
             "formato": "markdown", "idioma": "es-ES", "en_paquete": True, "sha256": sha_guia},
            {"id": "plantilla", "tipo": "plantilla_md", "archivo": "entregables/plantilla.md", "paginas": None,
             "peso_mb": "0.01", "formato": "markdown", "idioma": "es-ES", "en_paquete": True, "sha256": sha_plantilla},
        ],
        "matriz_promesas": [{"promesa_id": "p1", "texto": "promesa de prueba", "entregable_id": "guia",
                             "prueba": "sección 1", "estado": "cumplida"}],
        "tiempos": {"lectura_min": 10, "ejecucion_min": 10, "total_min": 20, "prometido_min": 20, "base": "estimado"},
        "pasos": [{"id": "paso-1", "ejecutable_por_agente": False, "t_humano_min": 10}],
        "vigencia": {"verificado_el": "2026-11-06", "revisar_antes_de": "2027-05-06", "items_volatiles": []},
        "entrega": {"estrategia": "enlace_firmado_email", "vence_dias": 7, "max_descargas": 5},
        "ia_divulgacion": "Contenido generado con asistencia de IA, revisado por humano.",
        "changelog": [{"version": "v1", "fecha": "2026-11-06", "cambio": "versión inicial"}],
    }
    comun.escribir_atomico(dir_producto / "producto.json", comun.json_canonico(producto))
    return producto
