"""Líneas de ``alertas.jsonl`` que NO son de este productor (las de F1, las de ventas y gasto que escriba S-B): se muestran y se cuentan, pero siempre SANEADAS.

El contenido de un archivo es DATO no confiable: solo pasan las claves del esquema, con su tipo y su largo acotados; el texto se limpia de controles y enlaces.
Lo usan el panel (``GET /api/alertas``) y el informe de las 08:30.
"""
from __future__ import annotations

from typing import Any

from scripts.alertas.hechos import limpiar_texto

__all__ = ["SEVERIDADES", "ESTADOS", "medida", "sanear_ajena"]

SEVERIDADES = ("info", "amarilla", "naranja", "roja")
ESTADOS = ("abierta", "reconocida", "cerrada")


def medida(v: Any) -> Any:
    """Valor o umbral de una alerta ajena: entero, cadena decimal corta, dinero {monto, moneda} o ``None`` (nunca float)."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        return v[:40]
    if isinstance(v, dict) and isinstance(v.get("monto"), int) and not isinstance(v.get("monto"), bool) and isinstance(v.get("moneda"), str):
        return {"monto": v["monto"], "moneda": v["moneda"][:3]}
    return None


def sanear_ajena(o: dict[str, Any]) -> dict[str, Any] | None:
    """Una línea de otra regla con solo lo que el esquema permite; ``None`` si no se puede mostrar con seguridad."""
    if not isinstance(o.get("id"), str) or o.get("severidad") not in SEVERIDADES or o.get("estado") not in ESTADOS or not isinstance(o.get("regla_id"), str):
        return None
    texto = lambda k, n: o[k][:n] if isinstance(o.get(k), str) else None  # noqa: E731
    return {
        "schema_version": texto("schema_version", 10), "id": o["id"][:100], "ts": texto("ts", 30), "severidad": o["severidad"], "regla_id": o["regla_id"][:40],
        "origen": o.get("origen") if o.get("origen") in ("F1", "F2") else None, "oferta_id": texto("oferta_id", 20), "macro_nicho": texto("macro_nicho", 40),
        "nivel": texto("nivel", 20), "valor": medida(o.get("valor")), "umbral": medida(o.get("umbral")),
        "accion_sugerida": limpiar_texto(o.get("accion_sugerida"), 300), "estado": o["estado"],
        "titulo": None, "responsable": None, "responsable_texto": None, "area": None, "enlace": None, "comando": None, "detalle": None, "medida": None, "fuente": "archivo",
    }
