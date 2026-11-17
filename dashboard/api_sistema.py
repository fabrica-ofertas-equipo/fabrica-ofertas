"""``GET /api/sistema`` y la lectura de ``PAUSA``, del freno de captura y del semáforo de infraestructura."""
from __future__ import annotations

from typing import Any

from dashboard.api_base import Ctx, Sobre, ids_de_ofertas, motor_disponible
from dashboard.archivos import iso_mtime

__all__ = ["estado_infra", "estado_pausa", "freno_captura", "sistema"]

REL_PAUSA = "empresa/PAUSA"
REL_FRENO = "empresa/captura/freno.json"
REL_INFRA = "empresa/infra/estado.json"
_CMD_CHEQUEO = "python -m infra.preflight ejecutar --modo completo"
_MAX_MOTIVO = 300
_MAX_ITEMS_INFRA = 200          # tope de ítems que el panel muestra; el resto se cuenta en `items_total`


def _texto_corto(valor: Any) -> str | None:
    return valor[:_MAX_MOTIVO] if isinstance(valor, str) else None


def estado_pausa(ctx: Ctx) -> dict[str, Any]:
    """``{activa, desde, motivo}``: la presencia del archivo ``empresa/PAUSA`` ES la pausa (docs/06 §5)."""
    st = ctx.raiz_confinada.stat(REL_PAUSA)
    if st is None:
        return {"activa": False, "desde": None, "motivo": None}
    lectura = ctx.raiz_confinada.json(REL_PAUSA, tope=64 * 1024)
    desde = iso_mtime(st)
    motivo = None
    if lectura.ok and isinstance(lectura.dato, dict):
        desde = lectura.dato.get("ts") if isinstance(lectura.dato.get("ts"), str) else desde
        motivo = _texto_corto(lectura.dato.get("motivo"))
    elif lectura.estado == "corrupto":
        texto = ctx.raiz_confinada.texto(REL_PAUSA, tope=2048)
        motivo = _texto_corto(texto.dato.strip()) if texto.ok and isinstance(texto.dato, str) and texto.dato.strip() else None
    return {"activa": True, "desde": desde, "motivo": motivo}


def freno_captura(ctx: Ctx) -> tuple[dict[str, Any] | None, str | None]:
    """Freno compartido de captura (se MUESTRA, nunca se borra): ``(datos|None, aviso|None)``."""
    st = ctx.raiz_confinada.stat(REL_FRENO)
    if st is None:
        return None, None
    lectura = ctx.raiz_confinada.json(REL_FRENO, tope=64 * 1024)
    if lectura.ok and isinstance(lectura.dato, dict):
        ts = lectura.dato.get("ts") if isinstance(lectura.dato.get("ts"), str) else iso_mtime(st)
        return {"activo": True, "ts": ts, "motivo": _texto_corto(lectura.dato.get("motivo"))}, None
    # Un freno ilegible sigue contando como puesto: ante la duda, el panel lo muestra activo.
    return {"activo": True, "ts": iso_mtime(st), "motivo": None}, (
        "El freno de la captura de anuncios está puesto, pero no se pudo leer su motivo; por seguridad se muestra como activo "
        f"({lectura.aviso or REL_FRENO + ': contenido no interpretable'}).")


def _item_infra(crudo: Any) -> dict[str, Any] | None:
    """Un ítem del preflight saneado: solo claves conocidas, tipos verificados y textos cortos (el contenido es DATO no confiable)."""
    if not isinstance(crudo, dict) or not isinstance(crudo.get("id"), str):
        return None
    latencia = crudo.get("latencia_ms")
    return {
        "id": crudo["id"][:80],
        "bloque": _texto_corto(crudo.get("bloque")),
        "estado": _texto_corto(crudo.get("estado")),
        "critico": crudo["critico"] if isinstance(crudo.get("critico"), bool) else None,
        "mensaje": _texto_corto(crudo.get("mensaje")),
        "evidencia_ruta": _texto_corto(crudo.get("evidencia_ruta")),
        "medido_en": _texto_corto(crudo.get("medido_en")),
        "expira_en": _texto_corto(crudo.get("expira_en")),
        "latencia_ms": latencia if isinstance(latencia, int) and not isinstance(latencia, bool) and latencia >= 0 else None,
    }


def estado_infra(ctx: Ctx) -> tuple[dict[str, Any] | None, str | None]:
    """``{semaforo, modo, generado_en, valido_hasta, items, items_total}`` de ``empresa/infra/estado.json`` o ``None`` si falta.

    ``items`` es el detalle por ítem del preflight (aditivo; lista vacía si el archivo no lo trae), saneado y acotado a ``_MAX_ITEMS_INFRA``.
    """
    lectura = ctx.raiz_confinada.json(REL_INFRA, tope=1024 * 1024)
    if lectura.estado == "ausente":
        return None, ("Todavía no se hizo el chequeo antes de lanzar, así que no hay semáforo de infraestructura. "
                       f"Se hace con el comando `{_CMD_CHEQUEO}` (el resultado se guarda en {REL_INFRA}).")
    if not lectura.ok or not isinstance(lectura.dato, dict):
        return None, ("No se pudo leer el resultado del chequeo antes de lanzar; vuelve a hacerlo con "
                      f"`{_CMD_CHEQUEO}` ({lectura.aviso or REL_INFRA + ': contenido no interpretable'}).")
    d = lectura.dato
    crudos = d.get("items") if isinstance(d.get("items"), list) else []
    items = [it for it in (_item_infra(x) for x in crudos[:_MAX_ITEMS_INFRA]) if it is not None]
    return {
        "items": items,
        "items_total": len(crudos),
        "semaforo": d.get("semaforo") if isinstance(d.get("semaforo"), str) else None,
        "modo": d.get("modo") if isinstance(d.get("modo"), str) else None,
        "generado_en": d.get("generado_en") if isinstance(d.get("generado_en"), str) else None,
        "valido_hasta": d.get("valido_hasta") if isinstance(d.get("valido_hasta"), str) else None,
    }, None


def sistema(ctx: Ctx) -> Sobre:
    """Panorama del entorno: pausa, freno, infraestructura y si el panel muestra la oferta demo."""
    avisos: list[str] = []
    fuente = [REL_PAUSA, REL_FRENO, REL_INFRA]
    freno, aviso_freno = freno_captura(ctx)
    infra, aviso_infra = estado_infra(ctx)
    for aviso in (aviso_freno, aviso_infra):
        if aviso:
            avisos.append(aviso)
    vigia = ctx.estado_vigia()
    if vigia is not None and vigia.get("truncada"):
        avisos.append(f"El vigía alcanzó su límite de {vigia['tope']} archivos (el vigía es el que avisa al panel cuando algo cambia). "
                      "Los archivos nuevos o más allá del límite ya no se actualizan en vivo: si ves datos viejos, recarga la página. "
                      "Para solucionarlo, vigila menos archivos o sube el límite.")
    ids = ids_de_ofertas(ctx)
    datos = {
        "entorno": ctx.entorno,
        "raiz": str(ctx.raiz),
        "hora": ctx.iso_ahora(),
        "modo_demo": any(i.startswith("_") for i in ids),
        "ofertas_reales": sum(1 for i in ids if not i.startswith("_")),
        "pausa": estado_pausa(ctx),
        "freno_captura": freno,
        "infra": infra,
        "motor_disponible": motor_disponible(ctx),
        "vigia": vigia,
        "panel": {"version": ctx.version, "puerto": ctx.puerto},
    }
    return Sobre(datos, fuente, vacio=False, avisos=avisos)
