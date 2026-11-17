"""``GET /api/negocio`` y ``GET /api/negocio/documento?ruta=…`` (pantalla «Negocio»): la cartera de ofertas con sus cuentas.

Solo lectura. Lee ``ofertas/_funnels/libro-de-tests.json`` (fuente de verdad de costos e ingresos por test). El cálculo vive en
``dashboard/negocio.py``. Los frenos de cuenta (300 USD/día, −3.000 USD) los eliminó el dueño el 2026-11-13: ya no se leen ni se avisan.

``/documento`` abre, como texto o imagen, un archivo de los expedientes (``ofertas/_funnels/…``) o la bitácora
``ofertas/_borrador-*/estado.md`` de una oferta, con el mismo resolvedor confinado del resto del panel.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any

from dashboard import agenda as _agenda
from dashboard import negocio as _negocio
from dashboard.api_base import Ctx, Sobre
from dashboard.api_ofertas import leer_archivo
from dashboard.archivos import Raiz
from dashboard.seguridad import ErrorHttp

__all__ = ["negocio", "documento", "REL_LIBRO"]

REL_LIBRO = "ofertas/_funnels/libro-de-tests.json"
_RX_DOC = re.compile(r"^(_funnels/[^\x00]{1,300}|_borrador-[a-z0-9-]{1,60}/estado\.md)$")


def _documentos(ctx: Ctx, oferta: dict[str, Any]) -> list[dict[str, Any]]:
    """Enlaces a los documentos de la oferta que EXISTEN (expediente, lo no modelado, revisiones, bitácora)."""
    f = oferta.get("ficha") or {}
    r = ctx.raiz_confinada
    docs: list[dict[str, Any]] = []
    exp = f.get("expediente") if isinstance(f.get("expediente"), str) else None
    candidatos = []
    if exp:
        candidatos += [("Expediente del funnel", f"{exp}/FUNNEL.md"), ("Lo que no se modeló", f"{exp}/no-modelado/LEEME.md"),
                       ("Lo que no se modeló (detalle)", f"{exp}/no-modelado/detalle.md")]
    for rev in f.get("revisiones") or []:
        if isinstance(rev, str):
            candidatos.append((f"Revisión {rev.rsplit('REVISION-', 1)[-1].removesuffix('.md')}" if "REVISION-" in rev else "Revisión", rev))
    if isinstance(f.get("carpeta_trabajo"), str):
        candidatos.append(("Bitácora de trabajo", f"{f['carpeta_trabajo']}/estado.md"))
    for titulo, rel in candidatos:
        try:
            ok = r.existe(rel)
        except ErrorHttp:
            ok = False
        if ok and rel.startswith("ofertas/"):
            docs.append({"titulo": titulo, "ruta": rel})
    return docs


_RX_DIA = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


def _dia(consulta: dict[str, list[str]] | None, clave: str) -> Any:
    import datetime as _dt
    v = ((consulta or {}).get(clave) or [""])[0].strip()
    if not v:
        return None
    try:
        if not _RX_DIA.fullmatch(v):
            raise ValueError(v)
        return _dt.date.fromisoformat(v)
    except ValueError:
        raise ErrorHttp(400, "periodo_invalido", "El período no es válido. Las fechas van así: 2026-11-12.") from None


REL_META_VIVO = "ofertas/_funnels/meta_vivo.json"
REL_EVENTOS = "ofertas/_funnels/presupuesto_eventos.jsonl"   # fotos_campanas.py (16-nov)
REL_ESCALA = "ofertas/_funnels/escala.jsonl"
_CAMPOS_VIVO = ("gasto", "impresiones", "cpm", "clics", "vistas", "checkouts", "compras", "valor", "roas_meta", "cpa")


def _num_vivo(x: object) -> float | None:
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def en_vivo(ctx: Ctx) -> tuple[dict, dict[str, dict]]:
    """Lo último de ``meta_vivo.py`` (Meta leído directo cada 10 min, sin Claude): total de hoy y por oferta."""
    lec = ctx.raiz_confinada.json(REL_META_VIVO)
    if not lec.ok or not isinstance(lec.dato, dict):
        return {"ok": False, "error": "sin_lector"}, {}
    d = lec.dato
    base = d if d.get("ok") else (d.get("ultima_buena") if isinstance(d.get("ultima_buena"), dict) else {})
    leido = str(base.get("leido") or d.get("leido") or "")[:25]
    try:
        edad = round((ctx.ahora() - _dt.datetime.fromisoformat(leido)).total_seconds() / 60) if leido else None
    except ValueError:
        edad = None
    limpio = lambda h: {k: _num_vivo(h.get(k)) for k in _CAMPOS_VIVO} if isinstance(h, dict) else None  # noqa: E731
    por_oferta = {}
    for nombre, o in (base.get("ofertas") or {}).items():
        if isinstance(o, dict):
            por_oferta[str(nombre)] = {"hoy": limpio(o.get("hoy")), "presupuesto": _num_vivo(o.get("presupuesto"))}
    cab = {"ok": bool(d.get("ok")), "error": str(d.get("error") or "")[:30] or None, "leido": leido or None, "edad_min": edad,
           "total": limpio(base.get("total")) if base else None}
    return cab, por_oferta


def negocio(ctx: Ctx, consulta: dict[str, list[str]] | None = None) -> Sobre:
    """``GET /api/negocio[?desde=AAAA-MM-DD&hasta=AAAA-MM-DD]``: sin período, «desde el inicio»; con período, todo recalculado con los días del rango."""
    fuente = [REL_LIBRO, _agenda.REL_TAREAS]
    lec = ctx.raiz_confinada.json(REL_LIBRO)
    if not lec.ok:
        avisos = [lec.aviso] if lec.aviso else []
        avisos.append("Todavía no hay libro de tests: lo crea el agente al lanzar la primera oferta (fase de revisión de la guía de modelar y lanzar).")
        return Sobre({"ofertas": [], "atencion": []}, fuente, vacio=True, avisos=avisos)
    desde, hasta = _dia(consulta, "desde"), _dia(consulta, "hasta")
    datos = _negocio.calcular_periodo(lec.dato, ctx.ahora(), desde, hasta)
    vivo, vivo_ofertas = en_vivo(ctx)
    datos["en_vivo"] = vivo
    for o in datos["ofertas"]:
        o["documentos"] = _documentos(ctx, o)
        o["en_vivo"] = vivo_ofertas.get(o.get("nombre"))
    _agenda.agregar_agendas(ctx, datos, lec.dato, ctx.ahora())
    datos["libro"] = {"ruta": REL_LIBRO, "modificado": lec.mtime, "version": lec.dato.get("version") if isinstance(lec.dato, dict) else None}
    avisos = list(datos.pop("avisos", []))
    return Sobre(datos, fuente, vacio=not datos["ofertas"], avisos=avisos)


def documento(ctx: Ctx, ruta: str | None) -> Sobre:
    """Un archivo de ``ofertas/_funnels/`` o la bitácora ``ofertas/_borrador-*/estado.md`` (``ruta`` relativa a la raíz, empieza por ``ofertas/``)."""
    rel = (ruta or "").strip()
    if rel.startswith("ofertas/"):
        rel = rel[len("ofertas/"):]
    if not _RX_DOC.fullmatch(rel) or ".." in rel.split("/"):
        raise ErrorHttp(403, "documento_no_permitido", "Desde esta pantalla solo se abren los expedientes de las ofertas y su bitácora.")
    return leer_archivo(Raiz(ctx.raiz / "ofertas", limite=ctx.raiz), rel, "ofertas")


def meta(ctx: Ctx, consulta: dict[str, list[str]] | None = None) -> Sobre:
    """``GET /api/meta[?desde=AAAA-MM-DD&hasta=AAAA-MM-DD]`` (pantalla «Campañas en Meta», dueño 16-nov): campañas, conjuntos y anuncios
    de todas las ofertas con sus filas por día del período, para filtrar y agrupar como en el Administrador de anuncios."""
    from dashboard import meta_admin as _meta
    lec = ctx.raiz_confinada.json(REL_LIBRO)
    if not lec.ok:
        return Sobre({"campanas": [], "conjuntos": [], "anuncios": [], "dias": []}, [REL_LIBRO], vacio=True, avisos=[lec.aviso] if lec.aviso else [])
    desde, hasta = _dia(consulta, "desde"), _dia(consulta, "hasta")
    vivo = ctx.raiz_confinada.json(REL_META_VIVO)
    datos = _meta.armar(lec.dato, desde, hasta, ctx.ahora(), _meta.vivo_por_campana(vivo.dato if vivo.ok else None))
    oferta = ((consulta or {}).get("oferta") or [""])[0].strip()
    if not oferta:
        for c in datos["campanas"]:
            c.pop("motivos_libro", None)
        return Sobre(datos, [REL_LIBRO, REL_META_VIVO], vacio=not datos["campanas"])
    # una sola oferta (ficha de Negocio, dueño 16-nov): sus campañas, conjuntos y anuncios + la escala y la línea de tiempo
    if not re.fullmatch(r"[a-z0-9-]{1,80}", oferta):
        raise ErrorHttp(400, "oferta_invalida", "La oferta no es válida.")
    from dashboard.agenda import _jsonl
    datos = _meta.filtrar_oferta(datos, oferta)
    # zona del mercado (la tabla ZONA de control_previo.py): la línea de tiempo muestra la hora de Argentina y la del mercado
    from dashboard.agenda import _zonas
    mercados = sorted({str(c.get("mercado") or "") for c in datos["campanas"] if c.get("mercado")})
    zonas = _zonas(ctx)
    zona = next((zonas.get(m) for m in mercados if zonas.get(m)), None)
    nombres = {"Dublin": "Dublín", "Paris": "París", "Rome": "Roma", "Amsterdam": "Ámsterdam", "Istanbul": "Estambul", "Tokyo": "Tokio",
               "Mexico_City": "Ciudad de México", "Sao_Paulo": "São Paulo", "New_York": "Nueva York", "Singapore": "Singapur",
               "London": "Londres", "Lisbon": "Lisboa", "Berlin": "Berlín", "Brussels": "Bruselas", "Athens": "Atenas", "Warsaw": "Varsovia"}
    ultimo = zona.split("/")[-1] if zona else None
    datos["mercado"] = {"codigos": mercados, "zona": zona, "ciudad": nombres.get(ultimo, ultimo.replace("_", " ")) if ultimo else None}
    datos["escala"] = _meta.escala_oferta(datos["campanas"], _jsonl(ctx, REL_EVENTOS, maximo=3000), _jsonl(ctx, REL_ESCALA, maximo=1500), ctx.ahora())
    _meta.motivos_estado(datos["campanas"], datos["escala"]["cambios"])
    datos["vivo_leido"] = (vivo.dato or {}).get("leido") if vivo.ok and isinstance(vivo.dato, dict) else None
    return Sobre(datos, [REL_LIBRO, REL_META_VIVO, REL_EVENTOS, REL_ESCALA], vacio=not datos["campanas"])
