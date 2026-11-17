"""Lectores de descubrimiento (``empresa/barrido/**``): corridas, candidatos, fichas, etiquetas, plan, estado y páginas.

Formato de ``empresa/barrido/`` en ``scripts/modelado/barrido/README.md`` §5. Aquí se LEE; nunca se escribe ni se
invoca el CLI del barrido (para eso está la consola de acciones). Los números que no se pueden calcular porque falta
el archivo van como ``null`` (jamás ``0``). Títulos y nombres de página los escriben anunciantes: son DATO hostil y
viajan sin interpretar. Los JSON grandes se cachean por (ruta, mtime, tamaño); los objetos son de solo lectura.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any

from dashboard.api_base import Ctx, RX_CORRIDA, Sobre, exigir_corrida
from dashboard.archivos import Lectura, Raiz
from dashboard.api_sistema import freno_captura
from dashboard.seguridad import ErrorHttp
from scripts.referentes.landing import REL_REGISTRO, validar_page_id, validar_url

__all__ = ["candidatos", "corridas", "estado", "etiquetas", "fichas", "paginas", "plan", "referente"]

_BASE = "barrido"
_RX_ARCHIVO_CORRIDA = re.compile(r"^([0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]{1,8})(\.[A-Za-z0-9._-]+)?\.json$")
_RX_PASADA = re.compile(r"\.pasada-([0-9]+)\.json$")
_MAX_POR_PAGINA = 200
_POR_PAGINA = 50
_MAX_TEXTO_Q = 100


def _bar(ctx: Ctx) -> Raiz:
    return ctx.empresa().sub(_BASE)


def _rel(*partes: str) -> str:
    return "empresa/" + _BASE + "/" + "/".join(partes)


def _ids_de_corridas(ctx: Ctx) -> list[str]:
    b = _bar(ctx)
    ids: set[str] = set()
    for sub in ("planes", "paginas", "candidatos", "memoria"):
        for n in b.listar(sub, solo="archivo"):
            m = _RX_ARCHIVO_CORRIDA.fullmatch(n)
            if m:
                ids.add(m.group(1))
    for sub in ("crudo", "etiquetas", "candidatos"):
        for n in b.listar(sub, solo="dir"):
            if RX_CORRIDA.fullmatch(n):
                ids.add(n)
    return sorted(ids, reverse=True)


def _planes_de(b: Raiz, corrida: str) -> list[tuple[int, str]]:
    """``[(pasada, archivo)]`` ascendente: la 1 es ``<c>.json``; el plan de la pasada N es ACUMULADO (incluye las previas)."""
    salida: list[tuple[int, str]] = []
    for n in b.listar("planes", solo="archivo"):
        if n == f"{corrida}.json":
            salida.append((1, n))
        elif n.startswith(f"{corrida}.") and (m := _RX_PASADA.search(n)):
            salida.append((int(m.group(1)), n))
    return sorted(salida)


def _plan_vigente(b: Raiz, corrida: str) -> tuple[Lectura | None, list[int], str | None]:
    planes = _planes_de(b, corrida)
    if not planes:
        return None, [], None
    pasada, nombre = planes[-1]
    return b.json(f"planes/{nombre}", cache=True), [p for p, _ in planes], nombre


def _json_final(b: Raiz, subruta: str, corrida: str, avisos: list[str], *, etapa_alt: str = "solo-pasada1") -> Lectura:
    """``<subruta>/<corrida>.json`` o, si falta, la variante ``.<etapa_alt>.json`` (con aviso)."""
    lec = b.json(f"{subruta}/{corrida}.json", cache=True)
    if lec.estado == "ausente":
        alt = b.json(f"{subruta}/{corrida}.{etapa_alt}.json", cache=True)
        if alt.ok:
            parcial = "la primera pasada" if etapa_alt == "solo-pasada1" else f"la etapa «{etapa_alt}»"
            avisos.append(f"Todavía no está el resultado completo del barrido, así que se muestra el de {parcial} (falta {_rel(subruta, corrida)}.json).")
            return alt
    if lec.estado not in ("ok", "ausente") and lec.aviso:
        avisos.append(lec.aviso)
    return lec


def _entero(valor: Any) -> int | None:
    return valor if isinstance(valor, int) and not isinstance(valor, bool) else None


def _suma(a: Any, b: Any) -> int | None:
    """Suma lo que exista (``None`` solo si no hay ninguno de los dos): temas que pasan + páginas sin tema que pasan."""
    valores = [v for v in (_entero(a), _entero(b)) if v is not None]
    return sum(valores) if valores else None


def _lista_len(doc: Any, clave: str) -> int | None:
    return len(doc[clave]) if isinstance(doc, dict) and isinstance(doc.get(clave), list) else None


def _fila_corrida(ctx: Ctx, corrida: str) -> dict[str, Any]:
    b = _bar(ctx)
    avisos: list[str] = []
    plan, _, _ = _plan_vigente(b, corrida)
    nombres = b.listar(f"crudo/{corrida}", solo="archivo") if b.es_directorio(f"crudo/{corrida}") else None
    ok = None if nombres is None else sum(1 for n in nombres if n.endswith(".json") and not n.endswith((".error.json", ".extra.json")))
    pag = _json_final(b, "paginas", corrida, avisos)
    cand = _json_final(b, "candidatos", corrida, avisos)
    eti = b.json(f"etiquetas/{corrida}/consolidado.json", cache=True)
    fic = b.json(f"candidatos/{corrida}/fichas_borrador.json", cache=True)
    resumen = cand.dato.get("resumen") if cand.ok and isinstance(cand.dato, dict) and isinstance(cand.dato.get("resumen"), dict) else {}
    cobertura = eti.dato.get("cobertura") if eti.ok and isinstance(eti.dato, dict) and isinstance(eti.dato.get("cobertura"), dict) else {}
    actualizado = None
    for lec in (cand, pag, eti, plan):
        if lec is not None and lec.ok and isinstance(lec.dato, dict):
            g = lec.dato.get("generado_en") or lec.dato.get("creado_en")
            if isinstance(g, str) and (actualizado is None or g > actualizado):
                actualizado = g
    return {
        "corrida_id": corrida,
        "consultas_ok": ok,
        "consultas_tope": _entero(plan.dato.get("tope_consultas")) if plan is not None and plan.ok and isinstance(plan.dato, dict) else None,
        "consultas_plan": _lista_len(plan.dato, "consultas") if plan is not None and plan.ok else None,
        "paginas": _lista_len(pag.dato, "paginas") if pag.ok else None,
        "etiquetadas": _entero(cobertura.get("etiquetadas")),
        "candidatas": _entero(resumen.get("paginas_candidatas")),
        "pasan_traccion": _suma(resumen.get("temas_pasan_traccion"), resumen.get("sin_tema_pasan_traccion")),
        "pasan_traccion_temas": _entero(resumen.get("temas_pasan_traccion")),
        "pasan_traccion_sin_tema": _entero(resumen.get("sin_tema_pasan_traccion")),
        "fichas": _lista_len(fic.dato, "ofertas") if fic.ok else None,
        "actualizado_en": actualizado,
        "avisos": avisos,
    }


def corridas(ctx: Ctx) -> Sobre:
    """Una fila por corrida con los conteos de cada artefacto (``null`` si ese artefacto no existe)."""
    ids = _ids_de_corridas(ctx)
    if not ids:
        return Sobre([], [_rel("planes/*.json")], vacio=True,
                     avisos=["Todavía no hay ningún barrido de anuncios. Para empezar uno, crea su plan con el comando "
                             "`python -m scripts.modelado.barrido plan generar <AAAA-MM-DD-a> --escribir` "
                             "(cambia <AAAA-MM-DD-a> por la fecha de hoy y una letra, por ejemplo 2026-11-06-a)."])
    filas = [_fila_corrida(ctx, c) for c in ids]
    avisos = [a for f in filas for a in f.pop("avisos")]
    return Sobre(filas, [_rel("planes"), _rel("paginas"), _rel("candidatos"), _rel("etiquetas"), _rel("crudo")], avisos=avisos)


def _documento(ctx: Ctx, corrida: str, subruta: str, nombre: str, *, con_etapa_alt: bool = False) -> Sobre:
    exigir_corrida(corrida)
    b = _bar(ctx)
    avisos: list[str] = []
    if con_etapa_alt:
        lec = _json_final(b, subruta, corrida, avisos)
    else:
        lec = b.json(f"{subruta}/{nombre}", cache=True)
        if lec.estado not in ("ok", "ausente") and lec.aviso:
            avisos.append(lec.aviso)
    ruta = _rel(subruta, nombre)
    if not lec.ok:
        if lec.estado == "ausente":
            avisos.append(f"Todavía no existe este resultado del barrido: aparece cuando el barrido avanza hasta ese paso ({ruta}).")
        return Sobre(None, [ruta], vacio=True, avisos=avisos)
    return Sobre(lec.dato, [ruta], avisos=avisos)


def candidatos(ctx: Ctx, corrida: str) -> Sobre:
    """``candidatos/<c>.json``: temas, sin_tema, resumen, matriz_tema_pais, exportadores, descartadas…"""
    return _documento(ctx, corrida, "candidatos", f"{corrida}.json", con_etapa_alt=True)


def fichas(ctx: Ctx, corrida: str) -> Sobre:
    """``candidatos/<c>/fichas_borrador.json`` (fichas 2.0.0 para ``puntaje_modelar``)."""
    return _documento(ctx, corrida, f"candidatos/{corrida}", "fichas_borrador.json")


def etiquetas(ctx: Ctx, corrida: str) -> Sobre:
    """``etiquetas/<c>/consolidado.json``."""
    return _documento(ctx, corrida, f"etiquetas/{corrida}", "consolidado.json")


def plan(ctx: Ctx, corrida: str) -> Sobre:
    """El plan VIGENTE (el de la última pasada; es acumulado) más ``plan_archivo`` y ``pasadas`` disponibles."""
    exigir_corrida(corrida)
    b = _bar(ctx)
    lec, pasadas, nombre = _plan_vigente(b, corrida)
    if lec is None:
        aviso = (f"Todavía no hay un plan de consultas para este barrido. Se crea con el comando "
                 f"`python -m scripts.modelado.barrido plan generar {corrida} --escribir` ({_rel('planes', corrida)}.json).")
        return Sobre(None, [_rel("planes", f"{corrida}.json")], vacio=True, avisos=[aviso])
    if not lec.ok or not isinstance(lec.dato, dict):
        return Sobre(None, [_rel("planes", nombre or "")], vacio=True, avisos=[lec.aviso or "No se pudo leer el plan de consultas de este barrido."])
    return Sobre({**lec.dato, "plan_archivo": nombre, "pasadas": pasadas}, [_rel("planes", nombre or "")])


def estado(ctx: Ctx, corrida: str) -> Sobre:
    """Panorama de solo lectura (equivalente liviano de ``barrido estado``): qué artefactos hay y sus conteos."""
    exigir_corrida(corrida)
    b = _bar(ctx)
    avisos: list[str] = []
    lec_plan, pasadas, nombre_plan = _plan_vigente(b, corrida)
    hay_crudo = b.es_directorio(f"crudo/{corrida}")
    nombres = b.listar(f"crudo/{corrida}", solo="archivo") if hay_crudo else []
    pag = _json_final(b, "paginas", corrida, avisos)
    cand = _json_final(b, "candidatos", corrida, avisos)
    eti = b.json(f"etiquetas/{corrida}/consolidado.json", cache=True)
    fic = b.json(f"candidatos/{corrida}/fichas_borrador.json", cache=True)
    mem = b.json(f"memoria/{corrida}.json", cache=True)
    for lec in (eti, fic, mem):
        if lec.estado not in ("ok", "ausente") and lec.aviso:
            avisos.append(lec.aviso)
    if lec_plan is None and not hay_crudo and not pag.ok and not cand.ok:
        return Sobre(None, [_rel("planes", f"{corrida}.json")], vacio=True,
                     avisos=[f"Todavía no hay nada del barrido {corrida}: ni plan, ni consultas, ni resultados."])
    plan_d = lec_plan.dato if lec_plan is not None and lec_plan.ok and isinstance(lec_plan.dato, dict) else {}
    freno, aviso_freno = freno_captura(ctx)
    if aviso_freno:
        avisos.append(aviso_freno)
    for texto in (cand.dato.get("advertencias") if cand.ok and isinstance(cand.dato, dict) and isinstance(cand.dato.get("advertencias"), list) else [])[:20]:
        if isinstance(texto, str):
            avisos.append(texto[:300])
    qids = _qids_de_consultas(b, corrida, hay_crudo, nombres, plan_d)
    datos = {
        "corrida_id": corrida,
        **qids,
        "plan": {"existe": lec_plan is not None, "archivo": nombre_plan, "pasadas": pasadas,
                 "consultas": _lista_len(plan_d, "consultas"), "tope_consultas": _entero(plan_d.get("tope_consultas")),
                 "creado_en": plan_d.get("creado_en") if isinstance(plan_d.get("creado_en"), str) else None},
        "crudo": {"existe": hay_crudo,
                  "ok": sum(1 for n in nombres if n.endswith(".json") and not n.endswith((".error.json", ".extra.json"))),
                  "error": sum(1 for n in nombres if n.endswith(".error.json"))},
        "paginas": {"existe": pag.ok, "total": _lista_len(pag.dato, "paginas") if pag.ok else None},
        "etiquetas": {"existe": eti.ok,
                      "cobertura": eti.dato.get("cobertura") if eti.ok and isinstance(eti.dato, dict) else None},
        "memoria": {"existe": mem.ok, "hash": mem.dato.get("hash") if mem.ok and isinstance(mem.dato, dict) else None,
                    "ts": mem.dato.get("ts") if mem.ok and isinstance(mem.dato, dict) else None},
        "candidatos": {"existe": cand.ok,
                       "resumen": cand.dato.get("resumen") if cand.ok and isinstance(cand.dato, dict) else None},
        "fichas": {"existe": fic.ok, "total": _lista_len(fic.dato, "ofertas") if fic.ok else None},
        "freno": freno,
        "comando_estado": f"python -m scripts.modelado.barrido estado {corrida}",
    }
    return Sobre(datos, [_rel("planes", nombre_plan or f"{corrida}.json"), _rel("crudo", corrida), _rel("paginas", f"{corrida}.json"),
                         _rel("etiquetas", corrida, "consolidado.json"), _rel("memoria", f"{corrida}.json"),
                         _rel("candidatos", f"{corrida}.json")], avisos=avisos)


_RX_QID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$")


def _qids_de_consultas(b: Raiz, corrida: str, hay_crudo: bool, nombres: list[str], plan: dict[str, Any]) -> dict[str, list[str]]:
    """Desglose exacto por consulta: ``consultas_ok``, ``con_error``, ``sin_crudo`` (planeadas sin crudo) y ``truncadas``.

    El qid sale del NOMBRE del archivo (``<qid>.json`` / ``<qid>.error.json``), no de su contenido (dato no confiable).
    Truncada = el conector declaró más anuncios (``estimated_total_count``) de los que devolvió (``ads``).
    """
    ok = sorted(n[:-5] for n in nombres if n.endswith(".json") and not n.endswith((".error.json", ".extra.json")) and _RX_QID.fullmatch(n[:-5]))
    con_error = sorted(n[:-11] for n in nombres if n.endswith(".error.json") and _RX_QID.fullmatch(n[:-11]))
    planeadas = [q["qid"] for q in plan.get("consultas", []) if isinstance(q, dict) and isinstance(q.get("qid"), str) and _RX_QID.fullmatch(q["qid"])] \
        if isinstance(plan.get("consultas"), list) else []
    vistas = set(ok) | set(con_error)
    sin_crudo = sorted({q for q in planeadas if q not in vistas})
    truncadas: list[str] = []
    if hay_crudo:
        for qid in ok:
            lec = b.json(f"crudo/{corrida}/{qid}.json")
            d = lec.dato if lec.ok and isinstance(lec.dato, dict) else None
            total = d.get("estimated_total_count") if d else None
            anuncios = d.get("ads") if d else None
            if isinstance(total, int) and not isinstance(total, bool) and isinstance(anuncios, list) and total > len(anuncios):
                truncadas.append(qid)
    return {"consultas_ok": ok, "con_error": con_error, "sin_crudo": sin_crudo, "truncadas": truncadas}


def _entero_param(consulta: dict[str, list[str]], nombre: str, defecto: int, minimo: int, maximo: int) -> int:
    crudo = (consulta.get(nombre) or [""])[0]
    if crudo == "":
        return defecto
    try:
        valor = int(crudo)
    except ValueError as exc:
        raise ErrorHttp(400, "parametro_invalido", f"El valor de «{nombre}» tiene que ser un número entero.") from exc
    return max(minimo, min(maximo, valor))


def paginas(ctx: Ctx, corrida: str, consulta: dict[str, list[str]]) -> Sobre:
    """Páginas de la corrida, filtradas por ``q`` (nombre/id/título), ``pais`` y ``estado`` (medición); paginadas."""
    exigir_corrida(corrida)
    b = _bar(ctx)
    avisos: list[str] = []
    lec = _json_final(b, "paginas", corrida, avisos)
    ruta = _rel("paginas", f"{corrida}.json")
    if not lec.ok or not isinstance(lec.dato, dict) or not isinstance(lec.dato.get("paginas"), list):
        if lec.estado == "ausente":
            avisos.append(f"Todavía no hay páginas para mostrar. Se generan con el comando "
                          f"`python -m scripts.modelado.barrido ingestar {corrida} --escribir` ({ruta}).")
        return Sobre({"paginas": [], "total": 0, "total_sin_filtrar": None, "pagina": 1, "por_pagina": _POR_PAGINA,
                      "total_paginas": 0, "filtros": {}}, [ruta], vacio=True, avisos=avisos)
    por_pagina = _entero_param(consulta, "por_pagina", _POR_PAGINA, 1, _MAX_POR_PAGINA)
    pagina = _entero_param(consulta, "pagina", 1, 1, 10**9)
    q = ((consulta.get("q") or [""])[0])[:_MAX_TEXTO_Q].casefold().strip()
    pais = ((consulta.get("pais") or [""])[0])[:8].upper().strip()
    est = ((consulta.get("estado") or [""])[0])[:32].strip()
    todas = [p for p in lec.dato["paginas"] if isinstance(p, dict)]
    filtradas = todas
    if pais:
        filtradas = [p for p in filtradas if isinstance(p.get("paises"), list) and pais in p["paises"]]
    if est:
        filtradas = [p for p in filtradas if isinstance(p.get("medicion"), dict) and p["medicion"].get("estado") == est]
    if q:
        def _coincide(p: dict[str, Any]) -> bool:
            if q in str(p.get("page_name", "")).casefold() or q in str(p.get("page_id", "")).casefold():
                return True
            titulos = p.get("titulos")
            return isinstance(titulos, list) and any(q in str(t).casefold() for t in titulos[:20])
        filtradas = [p for p in filtradas if _coincide(p)]
    total = len(filtradas)
    total_paginas = (total + por_pagina - 1) // por_pagina
    inicio = (pagina - 1) * por_pagina
    datos = {"paginas": filtradas[inicio:inicio + por_pagina], "total": total, "total_sin_filtrar": len(todas),
             "pagina": pagina, "por_pagina": por_pagina, "total_paginas": total_paginas,
             "filtros": {"q": q or None, "pais": pais or None, "estado": est or None}}
    return Sobre(datos, [ruta], avisos=avisos)


# ───────────────────────── landing original de una página (referente) ─────────────────────────

_RX_FICHA_META = re.compile(r"^https://www\.facebook\.com/ads/library/\?id=([0-9]{5,25})$")
_MAX_ANUNCIOS_MUESTRA = 3
_COMANDO_REGISTRAR = ".venv/bin/python -m scripts.referentes.landing registrar {pid} \"<URL de la landing>\" --escribir"


def _registro_de_landing(b: Raiz, pid: str, avisos: list[str]) -> dict[str, Any] | None:
    """El registro de la landing de la página (``referentes/landings.json``), con la URL revalidada: un archivo editado a mano no
    puede producir un enlace ``javascript:``, local o de Meta; si la URL no pasa, se ignora y se avisa."""
    lec = b.json("referentes/landings.json", cache=False)
    if lec.estado == "ausente":
        return None
    if not lec.ok or not isinstance(lec.dato, dict) or not isinstance(lec.dato.get("referentes"), list):
        avisos.append(lec.aviso or f"No se pudo leer el registro de landings originales ({REL_REGISTRO}).")
        return None
    fila = next((f for f in lec.dato["referentes"] if isinstance(f, dict) and str(f.get("page_id")) == pid), None)
    if fila is None:
        return None
    try:
        url, dominio = validar_url(fila.get("url"))
    except ValueError as exc:
        avisos.append(f"La landing registrada para esta página no es válida y se ignora: {exc}")
        return None
    texto = lambda v, n: v[:n] if isinstance(v, str) and v else None  # noqa: E731
    return {"url": url, "dominio": dominio, "registrada_en": texto(fila.get("registrada_en"), 40), "nota": texto(fila.get("nota"), 300),
            "oferta_id": texto(fila.get("oferta_id"), 40), "copia_local": texto(fila.get("copia_local"), 300)}


def _anuncios_de_muestra(b: Raiz, corrida: str, pagina: dict[str, Any] | None, pid: str) -> list[dict[str, Any]]:
    """Hasta 3 anuncios de la página sacados del crudo de las consultas que la vieron (``qids`` del archivo de páginas)."""
    qids = [q for q in (pagina or {}).get("qids", []) if isinstance(q, str) and _RX_QID.fullmatch(q)] if isinstance((pagina or {}).get("qids"), list) else []
    salida: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for qid in qids[:8]:
        lec = b.json(f"crudo/{corrida}/{qid}.json", cache=True)
        anuncios = lec.dato.get("ads") if lec.ok and isinstance(lec.dato, dict) and isinstance(lec.dato.get("ads"), list) else []
        for a in anuncios:
            if not isinstance(a, dict) or str(a.get("page_id")) != pid:
                continue
            m = _RX_FICHA_META.fullmatch(a.get("ad_snapshot_url")) if isinstance(a.get("ad_snapshot_url"), str) else None
            if not m or m.group(1) in vistos:
                continue
            vistos.add(m.group(1))
            inicio = a.get("ad_delivery_start_time")
            fecha = None
            if isinstance(inicio, int) and not isinstance(inicio, bool) and 0 < inicio < 4_102_444_800:
                fecha = _dt.datetime.fromtimestamp(inicio, _dt.timezone.utc).date().isoformat()
            titulo = a.get("ad_creative_link_title")
            salida.append({"id": m.group(1), "inicio": fecha, "titulo": titulo[:150] if isinstance(titulo, str) else None,
                           "ficha": f"https://www.facebook.com/ads/library/?id={m.group(1)}"})
            if len(salida) >= _MAX_ANUNCIOS_MUESTRA:
                return salida
    return salida


def referente(ctx: Ctx, corrida: str, page_id: str) -> Sobre:
    """Todo lo que el panel sabe para llegar a la landing original de una página anunciante.

    * ``landing``: la que registró una persona (``scripts.referentes.landing``), ya revalidada; ``null`` si todavía no hay.
    * ``meta``: dos direcciones armadas por código solo con el identificador numérico (Biblioteca de Anuncios de la página y la página).
    * ``anuncios``: hasta 3 fichas de anuncio de esa página (de dónde se llega a la landing con un clic en el botón del anuncio).
    El barrido NO trae la dirección de la landing (solo 7 campos por anuncio), por eso hace falta registrarla; el sobre trae el
    comando exacto. Solo lectura: no visita ninguna dirección.
    """
    exigir_corrida(corrida)
    try:
        pid = validar_page_id(page_id)
    except ValueError as exc:
        raise ErrorHttp(400, "parametro_invalido", str(exc)) from exc
    b = _bar(ctx)
    avisos: list[str] = []
    paginas_lec = _json_final(b, "paginas", corrida, avisos)
    pagina = next((p for p in paginas_lec.dato["paginas"] if isinstance(p, dict) and str(p.get("page_id")) == pid), None) \
        if paginas_lec.ok and isinstance(paginas_lec.dato, dict) and isinstance(paginas_lec.dato.get("paginas"), list) else None
    if pagina is None and paginas_lec.ok:
        avisos.append("Esta página no figura en las páginas de este barrido: se muestran solo los enlaces armados con su identificador.")
    landing = _registro_de_landing(b, pid, avisos)
    nombre = pagina.get("page_name") if isinstance(pagina, dict) and isinstance(pagina.get("page_name"), str) else None
    datos = {
        "page_id": pid,
        "page_name": nombre[:120] if nombre else None,
        "landing": landing,
        "meta": {"biblioteca_pagina": f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&view_all_page_id={pid}",
                 "pagina": f"https://www.facebook.com/{pid}"},
        "anuncios": _anuncios_de_muestra(b, corrida, pagina, pid),
        "comando_registrar": _COMANDO_REGISTRAR.format(pid=pid),
    }
    return Sobre(datos, [_rel("referentes", "landings.json"), _rel("paginas", f"{corrida}.json"), _rel("crudo", corrida)], avisos=avisos)
