#!/usr/bin/env python3
"""Agregación de votos del Jurado de creativos: valida cada voto, desanonimiza con la llave y escribe ``jurado.json``.

Qué hace el código: rechaza los votos malformados, aparta los que delatan una fuga de ceguera, cuenta, ordena, mide la
dispersión, el acuerdo entre jueces y la banda de confianza, comprueba las anclas y sella el resultado con un hash. Nunca
llama a un LLM.

Reglas duras:
  * El jurado NUNCA decide gasto, ni apaga ni activa: solo ordena y avisa. ``modo`` nace en ``sombra`` y ``aplica_orden`` es
    ``false``. Solo pasa a ``asesor`` con una promoción firmada por el dueño que apunte a una calibración ``elegible_asesor``
    (``calibrar.py``); si esa calibración deja de serlo, el archivo vuelve a ``sombra`` y lo dice.
  * Un voto malformado (tipos, rangos, campos de más, ids que no están en el manifiesto, duplicado) NO cuenta y queda
    listado en ``rechazados``. Un voto con ``alerta_ceguera`` queda en ``cuarentena``: la ceguera es lo único que lo hace
    válido.
  * Los motivos e ideas de los votantes son DATO: se limpian y se guardan; nunca se interpretan ni se ejecutan.
  * Cero cifras inventadas: lo que no se puede calcular (muestra mínima) sale ``null`` o en ``sin_orden``, no relleno.
  * La salida es SOLO INTERNA: «7 de 10 comprarían» jamás va a un anuncio ni a una página (sería una cifra de clientes inventada).
  * Pesos iguales entre jueces hasta que la calibración permita otra cosa (no antes de ``n_min_etiquetas``).
  * El orden se desempata con la semilla, no con el nombre ni el orden de llegada.

Orden de las piezas: por proporción de «sí» y, solo para desempatar, por puntaje general medio (``score = share_si +
0,001 × puntaje_medio/10``). Las anclas NUNCA entran al orden.

Uso (desde la raíz, con .venv)::

    .venv/bin/python -m scripts.jurado.agregar agregar --tanda-dir DIR --avatares AV.json [--salida jurado.json]
    .venv/bin/python -m scripts.jurado.agregar verificar --tanda-dir DIR --jurado jurado.json

Códigos de salida: 0 ok · 2 uso · 3 entrada inválida o regla violada.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.jurado import _comun as c
from scripts.jurado import estadistica as est

CAMPOS_VOTO_OBLIGATORIOS = ("paquete_id", "avatar_id", "pieza_id", "voto", "motivo", "puntaje_gancho", "puntaje_claridad", "puntaje_general")
CAMPOS_VOTO_OPCIONALES = ("puntaje_cta", "puntaje_ritmo", "idea", "alerta_ceguera", "origen")
ORIGENES_VOTO = ("llm", "sintetico_demo")
SELLO_EXCLUYE = ("sello", "precision", "calibracion_ref")
AVISO_USO = ("SOLO USO INTERNO. Los votos son opiniones de una IA con perfiles simulados: sirven para ordenar la tanda y nunca se citan en un "
             "anuncio ni en una página («7 de 10 comprarían» sería una cifra de clientes inventada). El jurado no decide gasto, no apaga y no activa.")
_RX_VALLA = re.compile(r"^\s*```[a-zA-Z]*\s*\n(.*?)\n\s*```\s*$", re.DOTALL)


# ---------------------------------------------------------------------------------------------------------------
# Votos
# ---------------------------------------------------------------------------------------------------------------

def leer_voto_crudo(ruta: Path) -> Any:
    """JSON del voto. Tolera solo una valla de código alrededor (```json … ```); cualquier otro texto es voto malformado."""
    texto = ruta.read_text(encoding="utf-8")
    m = _RX_VALLA.match(texto)
    return json.loads(m.group(1) if m else texto)


def validar_voto(v: Any) -> list[str]:
    """Problemas de forma de UN voto (vacía = bien formado). No mira el manifiesto: eso es ``_contrastar``."""
    if not isinstance(v, Mapping):
        return ["el voto no es un objeto JSON"]
    err: list[str] = []
    for k in CAMPOS_VOTO_OBLIGATORIOS:
        if k not in v:
            err.append(f"falta «{k}»")
    extra = sorted(set(v) - set(CAMPOS_VOTO_OBLIGATORIOS) - set(CAMPOS_VOTO_OPCIONALES))
    if extra:
        err.append(f"campos no permitidos: {extra}")
    for k in ("paquete_id", "avatar_id", "pieza_id"):
        if k in v and not (isinstance(v[k], str) and v[k].strip()):
            err.append(f"«{k}» debe ser texto no vacío")
    if "voto" in v and not isinstance(v["voto"], bool):
        err.append("«voto» debe ser booleano (true/false), no texto ni número")
    for k in ("puntaje_gancho", "puntaje_claridad", "puntaje_general", "puntaje_cta", "puntaje_ritmo"):
        if k in v and v[k] is not None:
            if not c.es_entero(v[k]) or not 0 <= v[k] <= 10:
                err.append(f"«{k}» debe ser un entero de 0 a 10 (recibido {v[k]!r})")
        elif k in ("puntaje_gancho", "puntaje_claridad", "puntaje_general") and k in v:
            err.append(f"«{k}» no puede ser null")
    if "motivo" in v:
        if not isinstance(v["motivo"], str) or not c.limpiar_texto(v["motivo"]):
            err.append("«motivo» debe ser un texto no vacío")
        elif c.contar_palabras(c.limpiar_texto(v["motivo"], 2000)) > 25:
            err.append("«motivo» supera las 25 palabras")
    if v.get("idea") is not None:
        if not isinstance(v["idea"], str) or not c.limpiar_texto(v["idea"]):
            err.append("«idea» debe ser null o un texto no vacío")
        elif c.contar_palabras(c.limpiar_texto(v["idea"], 2000)) > 25:
            err.append("«idea» supera las 25 palabras")
    if v.get("alerta_ceguera") is not None and not (isinstance(v["alerta_ceguera"], str) and c.limpiar_texto(v["alerta_ceguera"])):
        err.append("«alerta_ceguera» debe ser null o un texto no vacío")
    if v.get("origen") is not None and v["origen"] not in ORIGENES_VOTO:
        err.append(f"«origen» debe ser uno de {ORIGENES_VOTO}")
    return err


def clasificar_votos(votos_crudos: Sequence[tuple[str, Any]], manifiesto: Mapping[str, Any], demo: bool) -> dict:
    """Separa los votos en aceptados, rechazados (con motivos) y en cuarentena (alerta de ceguera)."""
    por_paquete = {o["paquete_id"]: o for o in manifiesto["orden_llamadas"]}
    aceptados: dict[str, dict] = {}
    rechazados: list[dict] = []
    cuarentena: list[dict] = []
    for nombre, v in votos_crudos:
        if isinstance(v, Exception):
            rechazados.append({"archivo": nombre, "motivos": [f"JSON ilegible: {v}"]})
            continue
        motivos = validar_voto(v)
        if not motivos:
            llamada = por_paquete.get(v["paquete_id"])
            if llamada is None:
                motivos.append("paquete_id no está en el manifiesto de la tanda")
            else:
                if v["avatar_id"] != llamada["avatar_id"]:
                    motivos.append("avatar_id no coincide con el del paquete (¿voto de otra llamada?)")
                if v["pieza_id"] != llamada["pieza_id"]:
                    motivos.append("pieza_id no coincide con el del paquete")
            if v["paquete_id"] in aceptados:
                motivos.append("voto duplicado para el mismo paquete (una llamada = un voto)")
            origen = v.get("origen") or "llm"
            if origen == "sintetico_demo" and not demo:
                motivos.append("voto sintético en una tanda real: no se admite")
            if origen == "llm" and demo:
                motivos.append("voto «llm» en una tanda de demostración: mezcla de datos reales y de ejemplo")
        if motivos:
            rechazados.append({"archivo": nombre, "paquete_id": v.get("paquete_id") if isinstance(v, Mapping) else None, "motivos": motivos})
            continue
        limpio = {
            "paquete_id": v["paquete_id"], "avatar_id": v["avatar_id"], "pieza_id": v["pieza_id"], "voto": v["voto"],
            "motivo": c.limpiar_texto(v["motivo"], 300), "puntaje_gancho": v["puntaje_gancho"], "puntaje_claridad": v["puntaje_claridad"],
            "puntaje_cta": v.get("puntaje_cta"), "puntaje_general": v["puntaje_general"],
            "idea": c.limpiar_texto(v["idea"], 300) if v.get("idea") else None,
            "alerta_ceguera": c.limpiar_texto(v["alerta_ceguera"], 300) if v.get("alerta_ceguera") else None,
        }
        if limpio["alerta_ceguera"]:
            cuarentena.append({"archivo": nombre, "paquete_id": limpio["paquete_id"], "alerta": limpio["alerta_ceguera"]})
        else:
            aceptados[limpio["paquete_id"]] = limpio
    return {"aceptados": aceptados, "rechazados": rechazados, "cuarentena": cuarentena}


# ---------------------------------------------------------------------------------------------------------------
# Estadísticos
# ---------------------------------------------------------------------------------------------------------------

def _redondeo(x: float | None, d: int = 4) -> float | None:
    return None if x is None else round(x, d)


def _score(share: float, puntaje_medio: float) -> float:
    return share + 0.001 * puntaje_medio / 10.0


def _estadisticos_pieza(votos: Sequence[Mapping[str, Any]]) -> dict:
    n = len(votos)
    a_favor = sum(1 for v in votos if v["voto"])
    pg = [v["puntaje_general"] for v in votos]
    share = a_favor / n
    banda = est.wilson(a_favor, n)
    return {
        "n_votos": n, "a_favor": a_favor, "share_si": round(share, 4),
        "banda_confianza": {"metodo": "wilson95", "nivel": 0.95, "bajo": _redondeo(banda[0]), "alto": _redondeo(banda[1]),
                            "supuesto": "votos independientes; con jueces del mismo modelo la banda real es MÁS ancha"},
        "puntaje_medio": round(statistics.fmean(pg), 3), "puntaje_mediana": c.mediana(pg),
        "desvio_puntaje": round(statistics.pstdev(pg), 3) if n > 1 else 0.0,
        "acuerdo": round(max(share, 1 - share), 4),
        "puntaje_gancho_medio": round(statistics.fmean([v["puntaje_gancho"] for v in votos]), 3),
        "puntaje_claridad_medio": round(statistics.fmean([v["puntaje_claridad"] for v in votos]), 3),
        "puntaje_cta_medio": _redondeo(statistics.fmean([v["puntaje_cta"] for v in votos if v["puntaje_cta"] is not None]), 3)
        if any(v["puntaje_cta"] is not None for v in votos) else None,
        "score": round(_score(share, statistics.fmean(pg)), 6),
    }


def _confianza(ancho: float, p: Mapping[str, Any]) -> str:
    if ancho <= p["banda_confianza_alta_ancho"]:
        return "alta"
    if ancho <= p["banda_confianza_media_ancho"]:
        return "media"
    return "baja"


# ---------------------------------------------------------------------------------------------------------------
# Modo (sombra / asesor)
# ---------------------------------------------------------------------------------------------------------------

def resolver_modo(modo_pedido: str, promocion: Mapping[str, Any] | None, calibracion: Mapping[str, Any] | None,
                  calibracion_sha256: str | None, locale: str, hoy: str | None = None) -> tuple[str, bool, str]:
    """(modo efectivo, aplica_orden, motivo). Sombra por defecto; asesor solo con promoción válida y calibración vigente elegible."""
    if modo_pedido == "sombra":
        return "sombra", False, "modo por defecto: el jurado predice y se compara con lo cobrado; no decide nada"
    if calibracion is not None and calibracion.get("estado_global") == "apagar":
        return "apagado", False, "la última calibración dice «apagar»: no supera al azar; reactivarlo exige una decisión del dueño"
    if not promocion:
        return "sombra", False, "se pidió «asesor» sin promoción firmada por el dueño: se queda en sombra"
    for k in ("aprobado_por", "fecha", "calibracion_sha256", "revisar_en"):
        if not promocion.get(k):
            return "sombra", False, f"la promoción no trae «{k}»: se queda en sombra"
    if str(promocion["revisar_en"]) < (hoy or c.ahora_utc())[:10]:
        return "sombra", False, f"la promoción caducó el {c.limpiar_texto(promocion['revisar_en'], 20)}: hay que volver a firmarla con la calibración vigente"
    if calibracion is None or calibracion.get("estado_global") != "elegible_asesor":
        return "sombra", False, "la última calibración ya no es «elegible_asesor»: vuelve a sombra"
    if calibracion.get("locale") not in (None, locale):
        return "sombra", False, "la calibración es de otro mercado: se queda en sombra"
    if promocion["calibracion_sha256"] != calibracion_sha256:
        return "sombra", False, "la promoción apunta a otra calibración distinta de la vigente: se queda en sombra"
    return "asesor", True, f"promoción de {c.limpiar_texto(promocion['aprobado_por'], 80)} del {c.limpiar_texto(promocion['fecha'], 20)} y calibración vigente elegible"


# ---------------------------------------------------------------------------------------------------------------
# Agregación
# ---------------------------------------------------------------------------------------------------------------

def agregar(manifiesto: Mapping[str, Any], llave: Mapping[str, Any], avatares: Mapping[str, Any], votos_crudos: Sequence[tuple[str, Any]],
            parametros: Mapping[str, Any] | None = None, modo: str = "sombra", promocion: Mapping[str, Any] | None = None,
            calibracion: Mapping[str, Any] | None = None, calibracion_sha256: str | None = None, ahora: str | None = None) -> dict:
    p = dict(c.PARAMETROS_DEFECTO, **(parametros or {}))
    demo = bool(manifiesto.get("demostracion"))
    clas = clasificar_votos(votos_crudos, manifiesto, demo)
    aceptados = list(clas["aceptados"].values())
    c.exigir(bool(aceptados), "no hay ningún voto aceptado: no se escribe un jurado vacío")
    entero = manifiesto["semilla_entero"]
    baseline_id = manifiesto.get("avatar_baseline")
    jueces = [a for a in manifiesto["avatares"]]
    n_esperado = len(jueces)
    min_votos = max(2, math.ceil(p["min_votos_pieza_pct"] * n_esperado))
    estilos = {a["avatar_id"]: a for a in avatares["avatares"]}

    votos_pieza: dict[str, list[dict]] = {}
    votos_ancla: dict[str, list[dict]] = {}
    votos_base: dict[str, list[dict]] = {}
    for v in aceptados:
        if v["avatar_id"] == baseline_id:
            votos_base.setdefault(v["pieza_id"], []).append(v)
        elif v["pieza_id"] in llave["piezas"]:
            votos_pieza.setdefault(v["pieza_id"], []).append(v)
        elif v["pieza_id"] in llave["anclas"]:
            votos_ancla.setdefault(v["pieza_id"], []).append(v)

    # --- piezas
    piezas: list[dict] = []
    sin_orden: list[dict] = []
    for pid, info in llave["piezas"].items():
        vs = votos_pieza.get(pid, [])
        if len(vs) < min_votos:
            sin_orden.append({"ad_name": info["ad_name"], "n_votos": len(vs), "motivo": f"menos de {min_votos} votos válidos de {n_esperado} esperados: no se le da puesto (no se penaliza)"})
            continue
        piezas.append({"ad_name": info["ad_name"], "_pid": pid, **_estadisticos_pieza(vs)})

    # --- bootstrap de puestos (remuestreo de avatares)
    if len(piezas) >= 2:
        orden_av = sorted(jueces)
        matriz = []
        for aid in orden_av:
            fila = []
            for pz in piezas:
                v = next((x for x in votos_pieza[pz["_pid"]] if x["avatar_id"] == aid), None)
                fila.append((1 if v["voto"] else 0, v["puntaje_general"]) if v else None)
            matriz.append(fila)
        rangos = est.rangos_bootstrap(matriz, entero, p["bootstrap_replicas"])
    else:
        rangos = [{"p05": 1.0, "p50": 1.0, "p95": 1.0} for _ in piezas]

    # --- orden (desempate por semilla, no por nombre)
    def clave_desempate(pz: Mapping[str, Any]) -> str:
        return c.hash_corto(entero, "desempate", pz["_pid"], largo=12)

    for pz, r in zip(piezas, rangos):
        pz["rango_puestos"] = {"p05": r["p05"], "p50": r["p50"], "p95": r["p95"], "metodo": f"bootstrap de avatares, {p['bootstrap_replicas']} réplicas"}
        pz["confianza"] = _confianza(r["p95"] - r["p05"], p)
    ordenadas = sorted(piezas, key=lambda z: (-z["score"], clave_desempate(z)))
    orden = []
    for i, pz in enumerate(ordenadas, 1):
        empate = (i > 1 and ordenadas[i - 2]["score"] == pz["score"]) or (i < len(ordenadas) and ordenadas[i]["score"] == pz["score"])
        sig = ordenadas[i] if i < len(ordenadas) else None
        separable = None if sig is None else pz["banda_confianza"]["bajo"] > sig["banda_confianza"]["alto"]
        orden.append({"ad_name": pz["ad_name"], "posicion": i, "puntaje": pz["puntaje_medio"], "score": pz["score"], "share_si": pz["share_si"],
                      "empate": bool(empate), "separable_del_siguiente": separable, "confianza": pz["confianza"]})
        pz["posicion"] = i

    # --- acuerdo entre jueces
    n_modal = statistics.mode([pz["n_votos"] for pz in piezas]) if piezas else 0
    items_modal = [pz for pz in piezas if pz["n_votos"] == n_modal]
    kappa = est.kappa_fleiss_binario([pz["a_favor"] for pz in items_modal], n_modal) if n_modal >= 2 and items_modal else None
    shares = [pz["share_si"] for pz in piezas]
    total_si = sum(pz["a_favor"] for pz in piezas)
    total_votos = sum(pz["n_votos"] for pz in piezas)
    tasa_global = total_si / total_votos if total_votos else None
    dispersion = statistics.pstdev(shares) if len(shares) > 1 else None
    acuerdo = {
        "kappa_fleiss": _redondeo(kappa), "jueces_por_pieza": n_modal, "piezas_en_kappa": len(items_modal),
        "acuerdo_medio_por_pieza": _redondeo(statistics.fmean([pz["acuerdo"] for pz in piezas])) if piezas else None,
        "tasa_aprobacion_global": _redondeo(tasa_global), "dispersion_de_si_entre_piezas": _redondeo(dispersion),
        "lectura": ("kappa cerca de 0 = los perfiles votan distinto entre sí (lo esperable si son perfiles distintos); cerca de 1 = votan casi igual "
                    "(poca diversidad real). Ninguno de los dos prueba que acierten: eso solo lo mide la calibración con lo cobrado."),
    }

    # --- anclas
    anclas_out = []
    for pid, info in llave["anclas"].items():
        vs = votos_ancla.get(pid, [])
        anclas_out.append({"ancla_id": info["ancla_id"], "veredicto_conocido": info["veredicto_conocido"], "origen_resultado": info["origen_resultado"],
                           "n_votos": len(vs), "share_si": _redondeo(sum(1 for v in vs if v["voto"]) / len(vs)) if vs else None,
                           "puntaje_medio": _redondeo(statistics.fmean([v["puntaje_general"] for v in vs]), 3) if vs else None})
    sg = [a["share_si"] for a in anclas_out if a["veredicto_conocido"] == "ganadora" and a["share_si"] is not None]
    sp = [a["share_si"] for a in anclas_out if a["veredicto_conocido"] == "perdedora" and a["share_si"] is not None]
    discrimina = bool(sg and sp and statistics.fmean(sg) - statistics.fmean(sp) >= p["anclas_margen_min"])
    anclas = {
        "detalle": anclas_out, "medidas": sum(1 for a in anclas_out if a["origen_resultado"] == "medida"),
        "control_sintetico": sum(1 for a in anclas_out if a["origen_resultado"] == "control_sintetico"),
        "share_si_ganadoras": _redondeo(statistics.fmean(sg)) if sg else None, "share_si_perdedoras": _redondeo(statistics.fmean(sp)) if sp else None,
        "discrimina": discrimina, "margen_minimo": p["anclas_margen_min"],
        "sesgo_de_aprobacion": bool(sp and statistics.fmean(sp) >= 0.5),
        "nota": "Las anclas no entran al orden. Con anclas «control_sintetico» el chequeo solo prueba que el votante distingue lo grosero; no que coincida con el mercado.",
    }

    # --- línea base (juez sin perfil)
    base_rows = []
    for pid, info in llave["piezas"].items():
        for v in votos_base.get(pid, []):
            xs = [x for x in (v["puntaje_gancho"], v["puntaje_claridad"], v["puntaje_cta"]) if x is not None]
            base_rows.append({"ad_name": info["ad_name"], "score": round(statistics.fmean(xs), 3), "n_items": len(xs)})

    # --- ideas (hipótesis, nunca claims)
    ideas, vistas = [], set()
    for v in aceptados:
        if v["idea"] and v["avatar_id"] != baseline_id and v["idea"].casefold() not in vistas:
            vistas.add(v["idea"].casefold())
            ideas.append({"idea": v["idea"], "origen": "jurado", "avatar_id": v["avatar_id"]})
    ideas = ideas[: p["max_ideas"]]

    # --- esperado y faltantes
    esperadas = manifiesto["n_llamadas"]
    vistos_paquetes = set(clas["aceptados"]) | {x["paquete_id"] for x in clas["cuarentena"]} | {x.get("paquete_id") for x in clas["rechazados"]}
    faltantes = [o["paquete_id"] for o in manifiesto["orden_llamadas"] if o["paquete_id"] not in vistos_paquetes]

    # --- advertencias (el «avisa» del jurado)
    adv: list[str] = []
    if demo:
        adv.append("DEMOSTRACIÓN: votos sintéticos generados por código sin ningún LLM. Solo muestra el flujo; no es una opinión de nadie.")
    if clas["rechazados"]:
        adv.append(f"{len(clas['rechazados'])} voto(s) malformado(s) se rechazaron y no cuentan.")
    if clas["cuarentena"]:
        adv.append(f"{len(clas['cuarentena'])} voto(s) con alerta de ceguera quedaron en cuarentena y no cuentan: revisar si alguna pieza filtró datos.")
    if faltantes:
        adv.append(f"Faltan {len(faltantes)} de {esperadas} llamadas (sin voto).")
    if sin_orden:
        adv.append(f"{len(sin_orden)} pieza(s) sin votos suficientes: quedan fuera del orden.")
    if anclas["medidas"] == 0:
        adv.append("Ninguna ancla es «medida»: el chequeo de anclas no valida contra el mercado.")
    if not anclas["discrimina"]:
        adv.append("Las anclas NO discriminan: el jurado no separó a la ganadora conocida de la perdedora conocida. No uses este orden.")
    if anclas["sesgo_de_aprobacion"]:
        adv.append("Sesgo de aprobación: el jurado aprobó la pieza conocida-perdedora.")
    if tasa_global is not None and tasa_global >= p["rango_aprobacion_global_alerta"]:
        adv.append(f"El jurado aprobó casi todo ({tasa_global:.0%} de «sí»): no separa piezas.")
    if dispersion is not None and dispersion < p["dispersion_min_entre_piezas"]:
        adv.append("Los «sí» casi no varían entre piezas: el orden es ruido.")
    if piezas and sum(1 for pz in piezas if pz["confianza"] == "baja") > len(piezas) / 2:
        adv.append("Más de la mitad de las piezas tienen confianza baja de puesto: con 10 jueces solo se separan diferencias grandes.")
    adv.append("Los jueces son el mismo modelo con perfiles distintos: sus errores están correlacionados, no son N observaciones independientes.")

    modo_ef, aplica, motivo_modo = resolver_modo(modo, promocion, calibracion, calibracion_sha256, avatares["locale"], ahora)
    cuerpo = {
        "schema_version": c.ESQUEMA_VERSION, "tipo": "jurado_creativos", "demostracion": demo,
        "oferta_id": manifiesto.get("oferta_id"), "locale": avatares["locale"], "mercado": avatares["locale"], "tanda_id": manifiesto.get("tanda_id"),
        "generado_en": ahora or c.ahora_utc(), "sellado_en": ahora or c.ahora_utc(),
        "modo": modo_ef, "aplica_orden": aplica, "modo_motivo": motivo_modo,
        "semilla": manifiesto["semilla"], "semilla_origen": manifiesto["semilla_origen"], "hash_orden": manifiesto["hash_orden"],
        "consigna_version": manifiesto["consigna_version"], "consigna_sha256": manifiesto["consigna_sha256"],
        "entradas": manifiesto.get("entradas", {}),
        "avatares": [{"avatar_id": aid, "estilo_decision": estilos[aid]["estilo_decision"], "estado": estilos[aid]["estado"],
                      "preocupacion": (estilos[aid].get("preocupacion_principal") or {}).get("tema"),
                      "nivel_evidencia": estilos[aid].get("nivel_evidencia")} for aid in sorted(jueces)],
        "n_jueces": n_esperado,
        "completitud": {"llamadas_esperadas": esperadas, "votos_aceptados": len(aceptados), "rechazados": len(clas["rechazados"]),
                        "cuarentena": len(clas["cuarentena"]), "faltantes": len(faltantes), "proporcion": round(len(aceptados) / esperadas, 4)},
        "votos": [{"ad_name": llave["piezas"][v["pieza_id"]]["ad_name"], "avatar_id": v["avatar_id"], "voto": v["voto"], "motivo": v["motivo"],
                   "puntaje_general": v["puntaje_general"], "puntaje_gancho": v["puntaje_gancho"], "puntaje_claridad": v["puntaje_claridad"],
                   "puntaje_cta": v["puntaje_cta"]}
                  for v in aceptados if v["pieza_id"] in llave["piezas"] and v["avatar_id"] != baseline_id],
        "piezas": [{k: val for k, val in pz.items() if not k.startswith("_")} for pz in sorted(piezas, key=lambda z: z["posicion"])],
        "orden": orden, "sin_orden": sin_orden, "acuerdo": acuerdo, "anclas": anclas, "baseline_rubrica": base_rows,
        "ideas": ideas, "ideas_nota": "Hipótesis del jurado: entran como cualquier concepto (QA-A + lint + X1) y nunca crean claims.",
        "rechazados": clas["rechazados"], "cuarentena": clas["cuarentena"], "faltantes": faltantes,
        "advertencias": adv, "aviso_uso": AVISO_USO, "sello_alcance": f"sha256 del JSON canónico sin {list(SELLO_EXCLUYE)}",
        "precision": None,
    }
    cuerpo["sello"] = sellar(cuerpo)
    return cuerpo


def sellar(doc: Mapping[str, Any]) -> str:
    """Hash del contenido predictivo. ``precision`` queda fuera a propósito: la calibración se fusiona después sin romper el sello."""
    return c.sha256_json({k: v for k, v in doc.items() if k not in SELLO_EXCLUYE})


def sello_valido(doc: Mapping[str, Any]) -> bool:
    return isinstance(doc.get("sello"), str) and doc["sello"] == sellar(doc)


# ---------------------------------------------------------------------------------------------------------------
# Verificación (L1 de código para el QA)
# ---------------------------------------------------------------------------------------------------------------

def verificar(doc: Mapping[str, Any], manifiesto: Mapping[str, Any], llave: Mapping[str, Any]) -> dict:
    checks: list[dict] = []

    def chk(cid: str, ok: bool, detalle: str) -> None:
        checks.append({"check_id": cid, "resultado": "pass" if ok else "fail", "detalle": detalle})

    chk("J-L1-01", sello_valido(doc), "el sello coincide con el contenido")
    chk("J-L1-02", doc.get("modo") in ("sombra", "asesor", "apagado") and (doc.get("modo") != "sombra" or doc.get("aplica_orden") is False),
        f"modo={doc.get('modo')} aplica_orden={doc.get('aplica_orden')}: en sombra el orden NO se aplica")
    chk("J-L1-03", doc.get("demostracion") == bool(manifiesto.get("demostracion")), "la marca de demostración coincide con el manifiesto")
    chk("J-L1-04", doc.get("semilla") == manifiesto.get("semilla") and doc.get("hash_orden") == manifiesto.get("hash_orden"), "semilla y hash del orden coinciden con el manifiesto")
    ads = {i["ad_name"] for i in llave["piezas"].values()}
    anc = {i["ancla_id"] for i in llave["anclas"].values()}
    en_votos = {v["ad_name"] for v in doc.get("votos", [])} | {o["ad_name"] for o in doc.get("orden", [])}
    chk("J-L1-05", en_votos <= ads and not (en_votos & anc), "ninguna ancla aparece en los votos ni en el orden y todo ad_name existe en la llave")
    chk("J-L1-06", [o["posicion"] for o in doc.get("orden", [])] == list(range(1, len(doc.get("orden", [])) + 1)), "las posiciones son 1..k sin saltos")
    chk("J-L1-07", all(not isinstance(v.get("voto"), str) for v in doc.get("votos", [])), "los votos son booleanos")
    chk("J-L1-08", isinstance(doc.get("aviso_uso"), str) and "nunca se citan" in doc["aviso_uso"], "lleva el aviso de uso interno")
    comp = doc.get("completitud", {})
    chk("J-L1-09", comp.get("votos_aceptados", 0) + comp.get("cuarentena", 0) + comp.get("faltantes", 0) <= comp.get("llamadas_esperadas", 0),
        "aceptados + cuarentena + faltantes no superan las llamadas esperadas")
    chk("J-L1-10", not any(v.get("origen") == "sintetico_demo" for v in doc.get("votos", [])), "sin marcas de voto sintético dentro de los votos")
    return {"schema_version": c.ESQUEMA_VERSION, "tipo": "l1_jurado", "ok": all(x["resultado"] == "pass" for x in checks), "checks_l1": checks}


# ---------------------------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------------------------

def leer_votos_dir(directorio: Path) -> list[tuple[str, Any]]:
    salida: list[tuple[str, Any]] = []
    for ruta in sorted(directorio.glob("*.json")):
        try:
            salida.append((ruta.name, leer_voto_crudo(ruta)))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            salida.append((ruta.name, e))
    return salida


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.jurado.agregar", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("agregar", help="agrega los votos de una tanda en jurado.json")
    a.add_argument("--tanda-dir", required=True)
    a.add_argument("--avatares", required=True)
    a.add_argument("--votos", default=None, help="carpeta de votos (por defecto, <tanda>/votos)")
    a.add_argument("--salida", default=None, help="por defecto, <tanda>/jurado.json")
    a.add_argument("--parametros", default=None)
    a.add_argument("--modo", choices=("sombra", "asesor"), default="sombra")
    a.add_argument("--promocion", default=None, help="promoción firmada por el dueño (solo para --modo asesor)")
    a.add_argument("--calibracion", default=None, help="última calibracion.json (obligatoria para asesor)")
    a.add_argument("--ahora", default=None)
    v = sub.add_parser("verificar", help="L1 de código: sello, modo, anclas fuera del orden, cuentas")
    v.add_argument("--tanda-dir", required=True)
    v.add_argument("--jurado", default=None)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        tanda = Path(args.tanda_dir)
        man = c.leer_json(tanda / "privado" / "manifiesto.json")
        llave = c.leer_json(tanda / "privado" / "llave.json")
        if args.cmd == "agregar":
            params = c.cargar_parametros(args.parametros)
            votos = leer_votos_dir(Path(args.votos) if args.votos else tanda / "votos")
            promo = c.leer_json(args.promocion) if args.promocion else None
            cal = c.leer_json(args.calibracion) if args.calibracion else None
            cal_sha = c.sha256_archivo(args.calibracion) if args.calibracion else None
            doc = agregar(man, llave, c.leer_json(args.avatares), votos, params, args.modo, promo, cal, cal_sha, args.ahora)
            destino = Path(args.salida) if args.salida else tanda / "jurado.json"
            c.escribir_json(destino, doc)
            informe = verificar(doc, man, llave)
            c.escribir_json(tanda / "privado" / "l1.json", informe)
            print(f"jurado.json -> {destino} · modo {doc['modo']} · {len(doc['orden'])} piezas ordenadas · {doc['completitud']['votos_aceptados']} votos "
                  f"({doc['completitud']['rechazados']} rechazados, {doc['completitud']['cuarentena']} en cuarentena)")
            for adv in doc["advertencias"][:6]:
                print("  aviso:", adv)
            return c.SALIDA_OK if informe["ok"] else c.SALIDA_RECHAZO
        if args.cmd == "verificar":
            doc = c.leer_json(args.jurado or tanda / "jurado.json")
            informe = verificar(doc, man, llave)
            c.escribir_json(tanda / "privado" / "l1.json", informe)
            for x in informe["checks_l1"]:
                print(f"  {x['check_id']}: {x['resultado']} — {x['detalle']}")
            return c.SALIDA_OK if informe["ok"] else c.SALIDA_RECHAZO
    except c.ErrorJurado as e:
        print(f"error: {e}", file=sys.stderr)
        return c.SALIDA_RECHAZO
    return c.SALIDA_USO


if __name__ == "__main__":
    sys.exit(main())
