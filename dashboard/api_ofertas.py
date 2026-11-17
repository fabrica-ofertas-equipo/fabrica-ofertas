"""Lectores de ofertas: ``/api/ofertas``, ``/api/oferta/<id>`` (+ ``/archivo``), ``/api/campanas/<id>`` y ``/api/operacion/<id>``.

Todo sale de ``ofertas/<id>/`` (solo lectura). Estado ausente o corrupto → fila/sección vacía con aviso, nunca
una excepción hacia el cliente. El texto de los archivos (títulos, copy, nombres) es DATO no confiable: se
entrega tal cual dentro de JSON y el frontend lo muestra con ``textContent``.
"""
from __future__ import annotations

import base64
import os
import re
from pathlib import Path
from typing import Any

from dashboard.api_base import (
    ARTEFACTOS, Ctx, ETAPAS, NOMBRES_ETAPA, RX_OFERTA, Sobre, exigir_oferta, ids_de_ofertas, motor_disponible,
)
from dashboard.archivos import (
    Raiz, TOPE_IMAGEN, TOPE_TEXTO, extension_legible, iso_mtime, mime_imagen, tipo_de,
)
from dashboard.seguridad import ErrorHttp
from scripts.referentes.landing import REL_REGISTRO, validar_url

__all__ = ["archivo", "campanas", "leer_archivo", "oferta", "ofertas", "operacion", "proximo_paso", "referente"]

_RX_FECHA = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
_MAX_KPI_DIAS = 60
_MAX_LINEAS = 200
_MAX_RESUMEN = 300


def _es_dinero(valor: Any) -> bool:
    return (isinstance(valor, dict) and isinstance(valor.get("monto"), int) and not isinstance(valor.get("monto"), bool)
            and isinstance(valor.get("moneda"), str))


def _dinero(valor: Any) -> dict[str, Any] | None:
    return {"monto": valor["monto"], "moneda": valor["moneda"]} if _es_dinero(valor) else None


def _etapas_estado(estado: Any) -> dict[str, Any]:
    etapas = estado.get("etapas") if isinstance(estado, dict) else None
    return etapas if isinstance(etapas, dict) else {}


def _resumen_estado(oferta_id: str, estado: Any) -> dict[str, Any]:
    est = estado if isinstance(estado, dict) else {}
    etapas = _etapas_estado(est)
    gasto = est.get("gasto") if isinstance(est.get("gasto"), dict) else {}
    return {
        "oferta_id": oferta_id,
        "oferta_id_estado": est.get("oferta_id") if isinstance(est.get("oferta_id"), str) else None,
        "familia_id": est.get("familia_id") if isinstance(est.get("familia_id"), str) else None,
        "demo": oferta_id.startswith("_"),
        "fase": est.get("fase") if isinstance(est.get("fase"), str) else None,
        "nivel": est.get("nivel") if isinstance(est.get("nivel"), str) else None,
        "pausa": est.get("pausa") if isinstance(est.get("pausa"), bool) else None,
        "etapas": {e: etapas[e].get("estado") for e in ETAPAS
                   if isinstance(etapas.get(e), dict) and isinstance(etapas[e].get("estado"), str)},
        "gates_pendientes": [e for e in ETAPAS if isinstance(etapas.get(e), dict) and etapas[e].get("gate_pendiente") is True],
        "gasto": {"hoy": _dinero(gasto.get("hoy")), "acumulado": _dinero(gasto.get("acumulado"))},
        "costo_ia": _dinero(est.get("costo_ia")),
        "actualizado_en": est.get("actualizado_en") if isinstance(est.get("actualizado_en"), str) else None,
    }


def ofertas(ctx: Ctx) -> Sobre:
    """Una fila por carpeta de ``ofertas/`` (la demo ``_ejemplo`` lleva ``demo: true``)."""
    filas: list[dict[str, Any]] = []
    fuente: list[str] = []
    avisos: list[str] = []
    for oferta_id in ids_de_ofertas(ctx):
        rel = f"ofertas/{oferta_id}/estado.json"
        fuente.append(rel)
        lectura = ctx.oferta(oferta_id).json("estado.json")
        fila = _resumen_estado(oferta_id, lectura.dato if lectura.ok else None)
        if lectura.estado == "ausente":
            fila["aviso"] = ("Esta oferta todavía no tiene su registro de avance. Lo crea el sistema automático con el comando "
                             "`python -m engine.orq crear` (archivo estado.json).")
        elif not lectura.ok:
            fila["aviso"] = lectura.aviso
            avisos.append(lectura.aviso or rel)
        else:
            fila["aviso"] = None
        filas.append(fila)
    if not filas:
        return Sobre([], ["ofertas/*/estado.json"], vacio=True,
                     avisos=["Todavía no hay ofertas (carpeta ofertas/). Crea la primera con el comando "
                             "`python -m engine.orq crear --brief <ruta>`, donde <ruta> es el archivo con la descripción de la oferta (el brief)."])
    return Sobre(filas, fuente, vacio=False, avisos=avisos)


# ----------------------------------------------------------------------------------------------
# Oferta
# ----------------------------------------------------------------------------------------------
def _artefactos(r: Raiz, etapa: str) -> list[dict[str, Any]]:
    destino = ARTEFACTOS[etapa]
    if destino.endswith(".json"):
        archivos = [(destino, st) for st in [r.stat(destino)] if st is not None]
    else:
        archivos = r.recorrer(destino, maximo=300, profundidad=6)  # rutas ya relativas a ofertas/<id>/
    return [{"ruta": rel.replace(os.sep, "/"), "tipo": tipo_de(rel), "bytes": st.st_size, "mtime": iso_mtime(st)}
            for rel, st in archivos]


def _resumen_qa(d: dict[str, Any]) -> str:
    partes: list[str] = []
    for clave in ("etapa", "version"):
        if isinstance(d.get(clave), str):
            partes.append(d[clave])
    if isinstance(d.get("ronda"), int):
        partes.append(f"ronda {d['ronda']}")
    if d.get("puntaje_global") is not None and d.get("umbral") is not None:
        partes.append(f"puntaje {d['puntaje_global']} / umbral {d['umbral']}")
    hallazgos = d.get("hallazgos")
    if isinstance(hallazgos, list):
        partes.append(f"{len(hallazgos)} hallazgo(s)")
    return " · ".join(partes)[:_MAX_RESUMEN]


def _qa_de(r: Raiz, etapa: str, avisos: list[str]) -> list[dict[str, Any]]:
    prefijos = (f"{etapa.lower()}-", f"x1-{etapa.lower()}-")
    salida: list[dict[str, Any]] = []
    for nombre in r.listar("qa", solo="archivo"):
        if not nombre.endswith(".json") or not nombre.startswith(prefijos):
            continue
        lectura = r.json(f"qa/{nombre}")
        if lectura.ok and isinstance(lectura.dato, dict):
            veredicto = lectura.dato.get("veredicto")
            salida.append({"archivo": f"qa/{nombre}", "veredicto": veredicto if isinstance(veredicto, str) else None,
                           "resumen": _resumen_qa(lectura.dato)})
        else:
            salida.append({"archivo": f"qa/{nombre}", "veredicto": None, "resumen": "archivo ilegible"})
            if lectura.aviso:
                avisos.append(lectura.aviso)
    return salida


_RX_HUELLA = re.compile(r"^sha256:[0-9a-f]{64}$")


def _huella_o_marcador(info: Any) -> str:
    """La huella de lo que se firma si la etapa la trae (``hash_salida``); si no, un marcador visible (nunca se inventa)."""
    h = info.get("hash_salida") if isinstance(info, dict) else None
    return h if isinstance(h, str) and _RX_HUELLA.fullmatch(h) else "<HUELLA_DE_LO_QUE_FIRMAS>"


def proximo_paso(ctx: Ctx, oferta_id: str, estado: Any) -> dict[str, Any]:
    """Qué sigue y el comando EXACTO para hacerlo (el panel no firma ni ejecuta: solo lo muestra copiable)."""
    base = {"motor_disponible": motor_disponible(ctx)}
    # Los comandos usan el id de oferta del estado (la carpeta demo se llama `_ejemplo`, su oferta es OF-AAAAMM-NN).
    interno = estado.get("oferta_id") if isinstance(estado, dict) else None
    if isinstance(interno, str) and RX_OFERTA.fullmatch(interno):
        oferta_id = interno
    if not isinstance(estado, dict):
        return {**base, "tipo": "sin_estado", "etapa": None,
                "texto": "Esta oferta todavía no se registró en el sistema automático. El comando de abajo la registra.",
                "comando": f"python -m engine.orq crear --brief ofertas/{oferta_id}/00-brief.yaml"}
    etapas = _etapas_estado(estado)
    if estado.get("pausa") is True:
        return {**base, "tipo": "pausada", "etapa": None, "texto": "Esta oferta está en pausa. Revisa el motivo antes de reanudarla.",
                "comando": f"python -m engine.orq estado --oferta {oferta_id}"}
    for e in ETAPAS:
        info = etapas.get(e)
        if isinstance(info, dict) and info.get("gate_pendiente") is True:
            gate = info.get("gate") if isinstance(info.get("gate"), str) else "H"
            return {**base, "tipo": "firmar_gate", "etapa": e,
                    "texto": f"{e} ({NOMBRES_ETAPA[e]}) espera tu firma (punto de control {gate}).",
                    "comando": (f"python -m engine.orq firmar --oferta {oferta_id} --etapa {e} --hash-objetivo {_huella_o_marcador(info)} "
                                "--clave-privada <RUTA_A_TU_CLAVE> --como dueno")}
    for e in ETAPAS:
        info = etapas.get(e)
        est = info.get("estado") if isinstance(info, dict) else None
        if est in ("bloqueado", "escalado"):
            texto = (f"{e} ({NOMBRES_ETAPA[e]}) está bloqueada: el sistema se frenó. Mira el motivo del bloqueo."
                     if est == "bloqueado" else
                     f"{e} ({NOMBRES_ETAPA[e]}) necesita que intervengas: el sistema no pudo seguir solo. Mira el motivo.")
            return {**base, "tipo": est, "etapa": e, "texto": texto,
                    "comando": f"python -m engine.orq estado --oferta {oferta_id}"}
    for e in ETAPAS:
        info = etapas.get(e)
        est = info.get("estado") if isinstance(info, dict) else None
        if est in ("en_progreso", "en_QA"):
            estado_txt = "en marcha" if est == "en_progreso" else "en revisión de calidad"
            return {**base, "tipo": "en_curso", "etapa": e, "texto": f"{e} ({NOMBRES_ETAPA[e]}) está {estado_txt}.",
                    "comando": f"python -m engine.orq estado --oferta {oferta_id}"}
        if est != "aprobado":
            return {**base, "tipo": "siguiente", "etapa": e, "texto": f"La siguiente etapa es {e} ({NOMBRES_ETAPA[e]}).",
                    "comando": f"python -m engine.orq siguiente --oferta {oferta_id}"}
    return {**base, "tipo": "completa", "etapa": None,
            "texto": f"Todas las etapas están aprobadas (fase: {estado.get('fase')}).",
            "comando": f"python -m engine.orq estado --oferta {oferta_id}"}


def oferta(ctx: Ctx, oferta_id: str) -> Sobre:
    """Detalle de una oferta: estado crudo, las 11 etapas con artefactos y QA, próximo paso, brief y mercado."""
    r = exigir_oferta(ctx, oferta_id)
    avisos: list[str] = []
    fuente = [f"ofertas/{oferta_id}/estado.json"]
    lectura = r.json("estado.json")
    estado = lectura.dato if lectura.ok and isinstance(lectura.dato, dict) else None
    if not lectura.ok:
        if lectura.estado != "ausente" and lectura.aviso:
            avisos.append(lectura.aviso)
        else:
            avisos.append("Esta oferta todavía no tiene su registro de avance (estado.json), así que solo se ven los archivos que ya existen.")
    etapas_est = _etapas_estado(estado)
    etapas: list[dict[str, Any]] = []
    for e in ETAPAS:
        info = etapas_est.get(e) if isinstance(etapas_est.get(e), dict) else {}
        etapas.append({
            "id": e, "nombre": NOMBRES_ETAPA[e], "estado": info.get("estado"), "version": info.get("version_aprobada"),
            "gate": info.get("gate"), "gate_pendiente": info.get("gate_pendiente") is True,
            "ronda_qa": info.get("ronda_qa"), "intentos": info.get("intentos"), "hash": info.get("hash_salida"),
            "aprobado_por": info.get("aprobado_por"), "bloqueo": info.get("bloqueo"),
            "obsoleta": info.get("obsoleta") is True,
            "artefactos": _artefactos(r, e), "qa": _qa_de(r, e, avisos),
        })
    brief_l = r.yaml("00-brief.yaml")
    mercado_l = r.json("mercado.json")
    fuente += [f"ofertas/{oferta_id}/00-brief.yaml", f"ofertas/{oferta_id}/mercado.json"]
    for lec in (brief_l, mercado_l):
        if lec.estado not in ("ok", "ausente") and lec.aviso:
            avisos.append(lec.aviso)
    datos = {
        "estado": estado, "etapas": etapas, "proximo_paso": proximo_paso(ctx, oferta_id, estado),
        "brief": brief_l.dato if brief_l.ok else None, "mercado": mercado_l.dato if mercado_l.ok else None,
        "motor_disponible": motor_disponible(ctx),
    }
    return Sobre(datos, fuente, vacio=estado is None, avisos=avisos, extra={"demo": oferta_id.startswith("_")})


def leer_archivo(r: Raiz, ruta: str | None, etiqueta: str, *, permitir_imagen: bool = True) -> Sobre:
    """Un archivo bajo la base confinada ``r``: texto (tope 400 KB) o imagen como data-URL (≤ 1 MB). El contenido va crudo.

    ``etiqueta`` es el prefijo de ``fuente`` (``ofertas/<id>``, ``.claude/skills/<slug>``…). Comparte el resolvedor
    confinado: rutas hostiles → 403, ausente → ``vacio``, carpeta → 400, binario → 400.
    """
    if not ruta:
        raise ErrorHttp(400, "ruta_requerida", "Falta indicar qué archivo abrir.")
    real = r.real(ruta, debe_existir=False)  # 403 ante rutas hostiles aunque no existan
    rel = os.path.relpath(real, os.path.realpath(r.base)).replace(os.sep, "/")
    fuente = [f"{etiqueta}/{rel}"]
    if not real.is_dir() and not extension_legible(rel):   # lista BLANCA de extensiones (revisión m-2)
        raise ErrorHttp(403, "extension_no_permitida", "El panel no muestra ese tipo de archivo.")
    if not real.exists():
        return Sobre(None, fuente, vacio=True, avisos=[f"Ese archivo no existe ({etiqueta}/{rel})."])
    if real.is_dir():
        raise ErrorHttp(400, "no_es_archivo", "Eso es una carpeta, no un archivo. Elige un archivo para abrirlo.")
    tipo = tipo_de(rel)
    if tipo == "imagen":
        if not permitir_imagen:
            raise ErrorHttp(400, "solo_texto", "Aquí solo se pueden abrir archivos de texto, no imágenes.")
        datos, truncado, st = r.bytes(rel, TOPE_IMAGEN)
        if truncado:
            return Sobre({"ruta": rel, "tipo": "imagen", "contenido": None, "truncado": True, "bytes": st.st_size,
                          "mtime": iso_mtime(st)}, fuente, avisos=[f"La imagen pesa más de 1 MB y no se muestra en el panel ({rel})."])
        contenido = f"data:{mime_imagen(rel)};base64,{base64.b64encode(datos).decode('ascii')}"
        return Sobre({"ruta": rel, "tipo": "imagen", "contenido": contenido, "truncado": False,
                      "bytes": st.st_size, "mtime": iso_mtime(st)}, fuente)
    datos, truncado, st = r.bytes(rel, TOPE_TEXTO)
    if b"\x00" in datos[:8192]:
        raise ErrorHttp(400, "archivo_binario", "Este archivo no es de texto (es un archivo binario) y no se puede mostrar aquí.")
    return Sobre({"ruta": rel, "tipo": tipo, "contenido": datos.decode("utf-8", "replace"), "truncado": truncado,
                  "bytes": st.st_size, "mtime": iso_mtime(st)}, fuente,
                 avisos=[f"Archivo muy grande: se muestran solo los primeros 400 KB ({rel})."] if truncado else [])


def archivo(ctx: Ctx, oferta_id: str, ruta: str | None) -> Sobre:
    """``GET /api/oferta/<id>/archivo?ruta=…``: un archivo de ``ofertas/<id>/``."""
    r = exigir_oferta(ctx, oferta_id)
    return leer_archivo(r, ruta, f"ofertas/{oferta_id}")


# ----------------------------------------------------------------------------------------------
# Campaña y operación
# ----------------------------------------------------------------------------------------------
def campanas(ctx: Ctx, oferta_id: str) -> Sobre:
    """``{campana, preflight, ids_meta, aprobacion, estado}`` de ``ofertas/<id>/07-campana/``."""
    r = exigir_oferta(ctx, oferta_id)
    nombres = {"campana": "campana.json", "preflight": "preflight.json", "ids_meta": "ids_meta.json",
               "aprobacion": "aprobacion.json"}
    avisos: list[str] = []
    fuente: list[str] = []
    datos: dict[str, Any] = {}
    hubo = False
    for clave, nombre in nombres.items():
        rel = f"07-campana/{nombre}"
        fuente.append(f"ofertas/{oferta_id}/{rel}")
        lec = r.json(rel)
        datos[clave] = lec.dato if lec.ok else None
        hubo = hubo or lec.ok
        if lec.estado not in ("ok", "ausente") and lec.aviso:
            avisos.append(lec.aviso)
    est = r.json("estado.json")
    fuente.append(f"ofertas/{oferta_id}/estado.json")
    etapa_d7 = _etapas_estado(est.dato).get("D7") if est.ok else None
    campana = datos.get("campana") if isinstance(datos.get("campana"), dict) else {}
    datos["estado"] = {
        "etapa": etapa_d7.get("estado") if isinstance(etapa_d7, dict) else None,
        "gate_pendiente": etapa_d7.get("gate_pendiente") is True if isinstance(etapa_d7, dict) else None,
        "campana": campana.get("estado") if isinstance(campana.get("estado"), str) else None,
        "fase": est.dato.get("fase") if est.ok and isinstance(est.dato, dict) else None,
    }
    if not hubo:
        avisos.append("Todavía no hay una campaña armada para esta oferta. La prepara la etapa D7 (carpeta 07-campana/).")
    return Sobre(datos, fuente, vacio=not hubo, avisos=avisos)


def _lineas_jsonl(r: Raiz, rel: str, avisos: list[str], maximo: int = _MAX_LINEAS) -> tuple[list[dict[str, Any]], bool]:
    lec = r.jsonl_cola(rel, maximo=maximo)
    avisos.extend(lec.avisos)
    if lec.estado != "ok":
        return [], False
    return [obj for _, obj, _ in lec.lineas if isinstance(obj, dict)], True


def operacion(ctx: Ctx, oferta_id: str) -> Sobre:
    """``{kpi_dia, decisiones, ordenes, veredicto}`` (+ ``postcompra`` y ``kpi_blended``) de ``08-operacion/``."""
    r = exigir_oferta(ctx, oferta_id)
    avisos: list[str] = []
    base = f"ofertas/{oferta_id}/08-operacion"
    fuente = [f"{base}/diario/<fecha>/kpi_oferta_dia.json", f"{base}/decisiones.jsonl",
              f"{base}/ordenes_presupuesto.jsonl", f"{base}/veredicto_oferta.json", "empresa/datos/kpi_blended_dia.json"]
    kpi: list[Any] = []
    fechas = [n for n in r.listar("08-operacion/diario", solo="dir") if _RX_FECHA.fullmatch(n)]
    if len(fechas) > _MAX_KPI_DIAS:
        avisos.append(f"Se muestran solo los últimos {_MAX_KPI_DIAS} días de indicadores (hay {len(fechas)} días en total).")
    for fecha in fechas[-_MAX_KPI_DIAS:]:
        lec = r.json(f"08-operacion/diario/{fecha}/kpi_oferta_dia.json")
        if lec.ok:
            kpi.append(lec.dato)
        elif lec.estado != "ausente" and lec.aviso:
            avisos.append(lec.aviso)
    decisiones, hay_dec = _lineas_jsonl(r, "08-operacion/decisiones.jsonl", avisos)
    ordenes, hay_ord = _lineas_jsonl(r, "08-operacion/ordenes_presupuesto.jsonl", avisos)
    veredicto = r.json("08-operacion/veredicto_oferta.json")
    if veredicto.estado not in ("ok", "ausente") and veredicto.aviso:
        avisos.append(veredicto.aviso)
    entregas, hay_ent = _lineas_jsonl(r, "10-postcompra/entregas.jsonl", avisos)
    reembolsos, hay_reem = _lineas_jsonl(r, "10-postcompra/reembolsos.jsonl", avisos)
    senal = r.json("10-postcompra/senal_pausa.json")
    blended = ctx.empresa().json("datos/kpi_blended_dia.json")
    datos = {
        "kpi_dia": kpi, "decisiones": decisiones, "ordenes": ordenes,
        "veredicto": veredicto.dato if veredicto.ok else None,
        "postcompra": {"entregas": entregas, "reembolsos": reembolsos, "senal_pausa": senal.dato if senal.ok else None},
        "kpi_blended": blended.dato if blended.ok else None,
    }
    vacio = not (kpi or hay_dec or hay_ord or veredicto.ok or hay_ent or hay_reem or senal.ok)
    if vacio:
        avisos.append("Todavía no hay datos de operación: ni indicadores diarios, ni decisiones de D8, ni órdenes de presupuesto, ni veredicto (carpeta 08-operacion/).")
    return Sobre(datos, fuente, vacio=vacio, avisos=avisos)


def es_oferta_valida(oferta_id: str) -> bool:
    return bool(RX_OFERTA.fullmatch(oferta_id or ""))


def carpeta_imagenes(ctx: Ctx, oferta_id: str) -> Raiz:
    """Base confinada de ``ofertas/<id>/05-landing/imagenes/`` (la landing las pide como ``/imagenes/…``; puede no existir)."""
    return exigir_oferta(ctx, oferta_id).sub("05-landing", "imagenes")


def carpeta_sitio(ctx: Ctx, oferta_id: str) -> Raiz:
    """Base confinada de ``/sitio/<id>/``: ``ofertas/<id>/05-landing/sitio/`` (404 si no existe)."""
    r = exigir_oferta(ctx, oferta_id)
    if not Path(os.path.realpath(r.base / "05-landing" / "sitio")).is_dir():
        raise ErrorHttp(404, "sitio_no_encontrado", "Esa oferta todavía no tiene su página de venta (landing) generada.")
    return r.sub("05-landing", "sitio")


# ───────────────────────── landing original del referente de una oferta ─────────────────────────

_MAX_REFERENTES = 6
_COMANDO_REGISTRAR_OFERTA = ".venv/bin/python -m scripts.referentes.landing registrar <id de la página> \"<URL de la landing>\" --oferta {oferta} --escribir"


def referente(ctx: Ctx, oferta_id: str) -> Sobre:
    """Dónde está la landing ORIGINAL (la que ya vende) de la oferta que modelamos. Solo lectura; no visita ninguna dirección.

    Dos fuentes, ambas revalidadas con ``scripts.referentes.landing.validar_url`` (una dirección que no pasa se ignora y se avisa):
    1. el registro ``empresa/barrido/referentes/landings.json`` (entradas con ``oferta_id`` de esta oferta; ``origen = "registro"``);
    2. los competidores de ``02-validacion/anuncios_competencia.json`` que traen ``landing_url`` (``origen = "validacion"``).
    """
    r = exigir_oferta(ctx, oferta_id)
    avisos: list[str] = []
    estado = r.json("estado.json")
    interno = estado.dato.get("oferta_id") if estado.ok and isinstance(estado.dato, dict) and isinstance(estado.dato.get("oferta_id"), str) else None
    mios = {oferta_id, interno} - {None}
    texto = lambda v, n: v[:n] if isinstance(v, str) and v.strip() else None  # noqa: E731
    vistas: set[str] = set()
    filas: list[dict[str, Any]] = []

    def agregar(origen: str, url: Any, **extra: Any) -> None:
        try:
            direccion, dominio = validar_url(url)
        except ValueError as exc:
            avisos.append(f"Se ignoró una landing guardada ({origen}) porque no es válida: {exc}")
            return
        if direccion in vistas or len(filas) >= _MAX_REFERENTES:
            return
        vistas.add(direccion)
        filas.append({"origen": origen, "url": direccion, "dominio": dominio, **extra})

    reg = ctx.empresa().sub("barrido").json("referentes/landings.json")
    if reg.ok and isinstance(reg.dato, dict) and isinstance(reg.dato.get("referentes"), list):
        for f in reg.dato["referentes"]:
            if isinstance(f, dict) and f.get("oferta_id") in mios:
                agregar("registro", f.get("url"), nombre=texto(f.get("page_name"), 120), page_id=texto(str(f.get("page_id") or ""), 30),
                        nota=texto(f.get("nota"), 300), copia_local=texto(f.get("copia_local"), 300), registrada_en=texto(f.get("registrada_en"), 40))
    elif reg.estado != "ausente" and reg.aviso:
        avisos.append(reg.aviso)
    comp = r.json("02-validacion/anuncios_competencia.json")
    if comp.ok and isinstance(comp.dato, dict) and isinstance(comp.dato.get("competidores"), list):
        for c in comp.dato["competidores"]:
            if isinstance(c, dict) and c.get("landing_url"):
                pid = c.get("page_id") if isinstance(c.get("page_id"), str) and c.get("page_id").isdigit() else None
                agregar("validacion", c.get("landing_url"), nombre=texto(c.get("page_name"), 120), page_id=pid, nota=None, copia_local=None, registrada_en=None)
    elif comp.estado != "ausente" and comp.aviso:
        avisos.append(comp.aviso)
    datos = {"oferta_id": oferta_id, "referentes": filas, "comando_registrar": _COMANDO_REGISTRAR_OFERTA.format(oferta=interno or oferta_id)}
    return Sobre(datos, [REL_REGISTRO, f"ofertas/{oferta_id}/02-validacion/anuncios_competencia.json"], vacio=not filas, avisos=avisos)
