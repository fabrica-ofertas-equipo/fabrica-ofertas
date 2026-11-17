"""``meta.insights``: lectura de resultados por anuncio y día para el ETL (``datos.etl_meta``, B3).

Solo lee (``GET …/insights``); no tiene efectos y por eso no pasa por ``engine.guard`` (convenciones
§9: "las lecturas puras de APIs… no necesitan ``--live``, pero se registran" — el registro lo hace
quien llama, igual que las demás lecturas del paquete).
"""
from __future__ import annotations

from typing import Any, Sequence

from meta.cliente import ClienteMeta

__all__ = ["CAMPOS_POR_DEFECTO", "insights_anuncios"]

# Campos mínimos que datos.etl_meta necesita para fact_meta_ad_dia (gasto, impresiones, clics, acciones).
CAMPOS_POR_DEFECTO = ("ad_id", "adset_id", "campaign_id", "date_start", "date_stop", "spend", "impressions", "clicks", "actions")


def insights_anuncios(cliente: ClienteMeta, campaign_id: str, *, desde: str, hasta: str,
                      campos: Sequence[str] = CAMPOS_POR_DEFECTO) -> list[dict[str, Any]]:
    """Insights por anuncio y día de ``campaign_id`` en ``[desde, hasta]`` (fechas ``AAAA-MM-DD``)."""
    return cliente.insights(campaign_id, desde=desde, hasta=hasta, campos=campos)
