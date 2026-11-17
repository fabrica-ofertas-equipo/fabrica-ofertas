"""Generador determinista de insights de Meta y eventos de Stripe para B0-15 y la mitad de B0-16
que me toca (I1, ola 2, docs/06 §6.3).

Produce, con una semilla fija (``random.Random(semilla)``, nunca ``random`` global), el documento
de insights que consume ``datos.etl_meta.aplicar_insights`` (``{"sintetico": true, "cuenta":…,
"filas":[...]}``) y el lote de eventos que consume ``datos.etl_stripe.aplicar_lote`` (``{"sintetico":
true, "eventos":[...]}``), para una ventana de 14 días y tres escenarios (A perdedor severo, B
ganador fuerte, C intermedio con cobertura de ``adid`` al 95 % y retraso de atribución). La
evaluación de MATAR/SEGUIR/VALIDADA sobre estos datos es de ``engine.d8`` (I1a, no la hago yo: B0-16
queda «pendiente» salvo esta mitad).
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any

__all__ = ["ESCENARIOS", "generar_escenario", "generar_insights_meta", "generar_eventos_stripe"]

_CUENTA = {"account_id": "123456789012399", "timezone_name": "Europe/Madrid", "currency": "EUR"}
_CAMPAIGN_ID = "120210000090001"
_ADSET_ID = "120210000090011"
_AD_IDS = ("120210000090101", "120210000090102", "120210000090103", "120210000090104", "120210000090105")
_DIA_0 = "2026-11-10"  # primer día de la ventana de 14 días (coherente con ofertas/_ejemplo)
_N_DIAS = 14


def _dias() -> list[str]:
    base = datetime.strptime(_DIA_0, "%Y-%m-%d")
    return [(base + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(_N_DIAS)]


def generar_insights_meta(*, oferta_id: str, semilla: int, gasto_diario_centavos: int,
                          jitter_pct: int = 15) -> dict[str, Any]:
    """14 días x 5 anuncios; ``gasto_diario_centavos`` se reparte entre los 5 con un jitter determinista."""
    rng = random.Random(semilla)
    filas: list[dict[str, Any]] = []
    for fecha in _dias():
        pesos = [rng.randint(100 - jitter_pct, 100 + jitter_pct) for _ in _AD_IDS]
        total_peso = sum(pesos)
        for ad_id, peso in zip(_AD_IDS, pesos):
            gasto = max(1, round(gasto_diario_centavos * peso / total_peso))
            impresiones = gasto * rng.randint(18, 24)
            clics = max(1, round(impresiones * rng.uniform(0.02, 0.035)))
            clics_enlace = max(1, round(clics * rng.uniform(0.55, 0.75)))
            filas.append({
                "date_start": fecha, "date_stop": fecha, "ad_id": ad_id, "adset_id": _ADSET_ID,
                "campaign_id": _CAMPAIGN_ID, "spend": f"{gasto / 100:.2f}", "impressions": str(impresiones),
                "clicks": str(clics), "inline_link_clicks": str(clics_enlace),
            })
    return {
        "sintetico": True,
        "fuente": f"generado por scripts.b0.generador (semilla={semilla}, I1, B0-15/B0-16) para {oferta_id}; "
                  "sin captura real, forma modelada sobre docs/06 §4.4 (ver tests/fixtures/datos/README.md)",
        "cuenta": dict(_CUENTA), "filas": filas,
    }


def _ts(fecha: str, horas: int = 15) -> int:
    dt = datetime.strptime(fecha, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(hours=horas)
    return int(dt.timestamp())


def generar_eventos_stripe(*, oferta_id: str, semilla: int, compras: list[tuple[str, str | None]],
                           retraso_horas: int = 0, precio_minor: int = 1990, moneda: str = "EUR",
                           con_duplicado: bool = True, con_reembolso: bool = False,
                           con_disputa: bool = False, con_compra_prueba: bool = True) -> dict[str, Any]:
    """``compras``: lista de ``(fecha_del_click, adid_o_None)`` (``None`` -> adid desconocido, no viaja en metadata).

    ``retraso_horas`` simula el retraso de atribución (docs/08 §5.3): el evento de Stripe se crea
    ``retraso_horas`` después del día del clic, no el mismo día (sigue dentro de la ventana de 14
    días + margen si el llamador deja hueco).
    """
    rng = random.Random(semilla)
    eventos: list[dict[str, Any]] = []
    sesiones: list[str] = []
    for i, (fecha, adid) in enumerate(compras):
        session_id = f"cs_test_b0gen_{semilla}_{i:03d}"
        sesiones.append(session_id)
        metadata = {"oferta_id": oferta_id, "visitor_id": f"v_b0gen{semilla:04d}{i:04d}abcd1234", "consent_marketing": "1"}
        if adid is not None:
            metadata["adid"] = adid
        eventos.append({
            "id": f"evt_cs_b0gen_{semilla}_{i:03d}", "type": "checkout.session.completed",
            "created": _ts(fecha, horas=9) + retraso_horas * 3600 + rng.randint(0, 3599),
            "data": {"object": {
                "id": session_id, "payment_intent": f"pi_b0gen_{semilla}_{i:03d}", "amount_total": precio_minor,
                "currency": moneda.lower(), "livemode": True, "payment_status": "paid", "metadata": metadata,
            }},
        })
    if con_duplicado and compras:
        primero = dict(eventos[0])
        primero["id"] = eventos[0]["id"] + "_duplicado"
        primero["created"] = eventos[0]["created"] + 1
        eventos.append(primero)
    if con_compra_prueba:
        fecha_prueba = compras[0][0] if compras else _DIA_0
        eventos.append({
            "id": f"evt_cs_b0gen_{semilla}_prueba", "type": "checkout.session.completed",
            "created": _ts(fecha_prueba, horas=8),
            "data": {"object": {
                "id": f"cs_test_b0gen_{semilla}_prueba", "payment_intent": f"pi_b0gen_{semilla}_prueba",
                "amount_total": precio_minor, "currency": moneda.lower(), "livemode": False, "payment_status": "paid",
                "metadata": {"oferta_id": oferta_id, "verificacion": "1", "visitor_id": f"v_b0genprueba{semilla:04d}", "consent_marketing": "0"},
            }},
        })
    if con_reembolso and sesiones:
        objetivo = sesiones[0]
        pi = next(e["data"]["object"]["payment_intent"] for e in eventos if e["data"]["object"]["id"] == objetivo)
        ts_reembolso = max(e["created"] for e in eventos) + 3600
        eventos.append({
            "id": f"evt_charge_refunded_b0gen_{semilla}", "type": "charge.refunded", "created": ts_reembolso,
            "data": {"object": {"id": f"ch_b0gen_{semilla}", "payment_intent": pi, "currency": moneda.lower(),
                                "amount_refunded": precio_minor,
                                "refunds": {"data": [{"id": f"re_b0gen_{semilla}", "amount": precio_minor,
                                                      "status": "succeeded", "reason": "requested_by_customer",
                                                      "created": ts_reembolso}]}}},
        })
    if con_disputa and len(sesiones) > 1:
        objetivo = sesiones[1]
        pi = next(e["data"]["object"]["payment_intent"] for e in eventos if e["data"]["object"]["id"] == objetivo)
        ts_disputa = max(e["created"] for e in eventos) + 7200
        eventos.append({
            "id": f"evt_dispute_b0gen_{semilla}", "type": "charge.dispute.created", "created": ts_disputa,
            "data": {"object": {"id": f"dp_b0gen_{semilla}", "charge": f"ch_disputa_b0gen_{semilla}",
                                "payment_intent": pi, "amount": precio_minor, "currency": moneda.lower(),
                                "status": "warning_needs_response", "created": ts_disputa}},
        })
    return {
        "sintetico": True,
        "fuente": f"generado por scripts.b0.generador (semilla={semilla}, I1, B0-15/B0-16) para {oferta_id}; "
                  "sin captura real, forma modelada sobre docs/06 §4.4 (ver tests/fixtures/datos/README.md)",
        "eventos": eventos,
    }


def generar_escenario(nombre: str, *, oferta_id: str = "OF-202611-01") -> dict[str, Any]:
    """Uno de ``ESCENARIOS``: ``{"meta": documento, "stripe": documento, "descripcion": str}``."""
    dias = _dias()
    if nombre == "A_perdedor_severo":
        # Gasto alto, casi sin compras: 14 días x ~18 EUR/día = 252 EUR, 1 sola compra (muy por
        # encima del CPA de equilibrio de cualquier oferta de bajo ticket) -> candidato a MATAR.
        meta = generar_insights_meta(oferta_id=oferta_id, semilla=101, gasto_diario_centavos=1800)
        stripe = generar_eventos_stripe(oferta_id=oferta_id, semilla=101, compras=[(dias[9], _AD_IDS[0])])
        return {"meta": meta, "stripe": stripe, "descripcion": "14 días, ~252 EUR de gasto, 1 compra: perdedor severo"}
    if nombre == "B_ganador_fuerte":
        # Gasto moderado, 10 compras repartidas, 1 con adid desconocido (cobertura 90%) -> candidato
        # a ESCALAR/PROMETEDORA.
        meta = generar_insights_meta(oferta_id=oferta_id, semilla=202, gasto_diario_centavos=900)
        compras = [(dias[i], _AD_IDS[i % len(_AD_IDS)]) for i in range(2, 12)]
        compras[3] = (compras[3][0], None)  # 1/10 sin adid conocido
        stripe = generar_eventos_stripe(oferta_id=oferta_id, semilla=202, compras=compras, con_reembolso=True)
        return {"meta": meta, "stripe": stripe, "descripcion": "14 días, ~126 EUR de gasto, 10 compras (90% cobertura): ganador fuerte"}
    if nombre == "C_intermedio_95_retraso":
        # 20 compras, 19 con adid conocido (cobertura exacta 95%), con 36h de retraso de atribución
        # (docs/08 §5.3): el evento de Stripe llega más de un día después del clic que lo originó.
        meta = generar_insights_meta(oferta_id=oferta_id, semilla=303, gasto_diario_centavos=1100)
        compras = [(dias[i % _N_DIAS], _AD_IDS[i % len(_AD_IDS)]) for i in range(20)]
        compras[7] = (compras[7][0], None)  # exactamente 1/20 sin adid conocido -> 95,00%
        stripe = generar_eventos_stripe(oferta_id=oferta_id, semilla=303, compras=compras, retraso_horas=36, con_disputa=True)
        return {"meta": meta, "stripe": stripe, "descripcion": "14 días, ~154 EUR, 20 compras (95% cobertura), retraso de atribución 36h: intermedio"}
    raise ValueError(f"escenario desconocido: {nombre!r} (se esperaba uno de {sorted(ESCENARIOS)})")


ESCENARIOS: tuple[str, ...] = ("A_perdedor_severo", "B_ganador_fuerte", "C_intermedio_95_retraso")
