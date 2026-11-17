"""Informe del día de las 08:30 (brechas/04 B4-24; ``mapeo.md`` §9): COMPONE el texto en dos versiones y NO envía nada.

* **Correo**: lleva los importes (ventas, gasto, ingresos) y el detalle. **Celular**: solo porcentajes y recuentos, **cero cifras de dinero** (si una
  llegara a colarse, ``_sin_dinero`` la tapa). El envío es de S-B con el canal que elija el dueño (ver ``coordinacion-sesiones.md``).
* **Plantilla fija, sin texto libre**: cada línea sale de una frase fija con números y nombres cortos (etapas, ids de oferta). No lleva texto escrito por
  una IA ni por terceros: los títulos de pendientes (que sí son texto de archivo) van solo en el correo, limpios de enlaces y recortados.
* **Los 5 tipos de aviso** (H4-04): pagos, lo importante, cansancio de anuncios, mercado nuevo y lo que no aprobaste. Cada uno dice si hay novedades,
  si no hay NOVEDADES (solo cuando se pudo medir) o si todavía NO SE MIDE y por qué: un «cero» solo se escribe cuando se midió.
* **Los ceros** (H4-05): las metas que deben dar cero (pagos frenados sin aviso, trabajos sin señal de vida, alertas graves sin aviso, gasto sobre el tope,
  cosas tuyas esperando), cada una «cumple», «no cumple» o «sin medir».
* **Lo que te toca a ti**: el semáforo, las firmas y los pendientes tuyos, en orden.

Lee los mismos archivos que el semáforo (``scripts.alertas.hechos``); si no hay datos de ventas o de gasto dice «todavía no hay datos». Solo lectura.

Uso: ``python -m scripts.informe.informe_diario [--version correo|celular|ambas] [--json] [--ahora AAAA-MM-DDTHH:MM:SSZ] [--fecha AAAA-MM-DD] [--raiz RUTA]``
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from dashboard.api_base import NOMBRES_ETAPA, Ctx
from scripts.alertas.hechos import horas_entre, leer_hechos, limpiar_texto, parsear_z
from scripts.alertas.producir import ajenas_de, estado_vigente
from scripts.alertas.semaforo import calcular_semaforo

__all__ = ["HORA_INFORME", "componer", "formatear_dinero", "main", "renderizar"]

SCHEMA_VERSION = "1.0.0"
HORA_INFORME = "08:30"          # avisos.resumen_diario_hora (mapeo.md §12; propuesta del video, el dueño la puede cambiar)
MAX_LINEAS = 30
MAX_PENDIENTES_CORREO = 8
_RX_FECHA = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
# dinero en cualquiera de sus formas habituales: lo que NO puede aparecer en la versión del celular
_RX_DINERO = re.compile(r"(?:[$€£]\s?\d[\d.,]*|\b\d[\d.,]*\s?(?:USD|EUR|PLN|GBP|ARS|MXN|CLP|COP|BRL|US\$|zł|€|\$)\b|\b(?:USD|EUR|PLN|GBP)\s?\d[\d.,]*)")
_ESTADO_SECCION = {"con_novedades": "Hay novedades", "sin_novedades": "Sin novedades", "sin_medir": "Todavía no se mide"}
_ESTADO_CERO = {"cumple": "Cumple", "no_cumple": "No cumple", "sin_medir": "Sin medir"}


# ----------------------------------------------------------------------------------------------
# Formato
# ----------------------------------------------------------------------------------------------
def _exponentes(ctx: Ctx) -> dict[str, int]:
    lec = ctx.raiz_confinada.json("contratos/monedas_iso4217.json")
    d = lec.dato.get("exponentes") if lec.ok and isinstance(lec.dato, dict) else None
    return {k: v for k, v in d.items() if isinstance(k, str) and isinstance(v, int)} if isinstance(d, dict) else {}


def formatear_dinero(monto: int, moneda: str, exponentes: dict[str, int] | None = None) -> str:
    """Entero en unidad menor + moneda → «1.234,56 EUR» (aritmética entera; sin float). Moneda desconocida: 2 decimales."""
    exp = (exponentes or {}).get(moneda, 2)
    neg = monto < 0
    abs_ = -monto if neg else monto
    ent, frac = divmod(abs_, 10 ** exp) if exp else (abs_, 0)
    cuerpo = f"{ent:,}".replace(",", ".") + (f",{frac:0{exp}d}" if exp else "")
    return f"{'-' if neg else ''}{cuerpo} {moneda}"


def _fecha_es(iso: str) -> str:
    return f"{iso[8:10]}/{iso[5:7]}/{iso[0:4]}" if isinstance(iso, str) and _RX_FECHA.match(iso[:10]) else "—"


def _sin_dinero(texto: str) -> str:
    """Red de seguridad de la versión del celular: nada con forma de importe de dinero."""
    return _RX_DINERO.sub("[importe en el correo]", texto)


def _n(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


# ----------------------------------------------------------------------------------------------
# Secciones
# ----------------------------------------------------------------------------------------------
def _ventas_gasto(h: dict[str, Any], exp: dict[str, int]) -> dict[str, Any]:
    v, lim = h["ventas"], h["limites"]
    dia = _fecha_es(v["fecha"])
    if not v["hay_datos"]:
        por_que = ("no hay ninguna campaña en prueba ni en escala" if not h["ofertas"].get("con_venta_en_curso") else
                   "faltan los datos del día de las ofertas que ya venden")
        txt = f"Todavía no hay datos de ventas ni de gasto del {dia}: {por_que}."
        return {"id": "ventas_gasto", "titulo": "Ventas y gasto", "estado": "sin_medir", "hay_datos": False, "dia": v["fecha"], "correo": [txt], "celular": "sin datos todavía"}
    correo: list[str] = []
    celular: list[str] = []
    if v["compras"] is not None:
        correo.append(f"Ventas del {dia}: {_n(v['compras'], 'compra', 'compras')}.")
        celular.append(f"{_n(v['compras'], 'venta', 'ventas')}")
    else:
        correo.append(f"Ventas del {dia}: sin dato.")
        celular.append("ventas sin dato")
    if v["gasto"]:
        correo.append("Gasto en anuncios: " + " · ".join(formatear_dinero(m["monto"], m["moneda"], exp) for m in v["gasto"]) + ".")
        pct = _porcentaje_tope(v["gasto"], lim)
        celular.append(f"gasto {pct} del tope diario" if pct else "gasto: sin tope firmado para dar el porcentaje")
    else:
        correo.append("Gasto en anuncios: sin dato.")
        celular.append("gasto sin dato")
    if v["ingresos"]:
        correo.append("Ingresos cobrados: " + " · ".join(formatear_dinero(m["monto"], m["moneda"], exp) for m in v["ingresos"]) + ".")
    return {"id": "ventas_gasto", "titulo": "Ventas y gasto", "estado": "con_novedades", "hay_datos": True, "dia": v["fecha"], "correo": correo, "celular": " · ".join(celular)}


def _porcentaje_tope(gastos: list[dict[str, Any]], lim: dict[str, Any]) -> str | None:
    """«9 %» = gasto del día / tope diario (``limites.gasto_diario_global``) si hay UNA moneda, el tope existe y es de esa moneda. Entero (redondeo normal)."""
    tope, mon = lim.get("gasto_diario_global"), lim.get("moneda")
    if not isinstance(tope, int) or isinstance(tope, bool) or tope <= 0 or len(gastos) != 1 or gastos[0]["moneda"] != mon:
        return None
    return f"{(gastos[0]['monto'] * 100 + tope // 2) // tope} %"


def _sec(id_: str, titulo: str, estado: str, correo: list[str], celular: str) -> dict[str, Any]:
    return {"id": id_, "titulo": titulo, "estado": estado, "correo": correo[:MAX_LINEAS], "celular": celular}


def _aviso_pagos(h: dict[str, Any]) -> dict[str, Any]:
    pre = h["preflight"]
    if not pre.get("existe"):
        return _sec("pagos", "Pagos", "sin_medir", ["Todavía no se mide: no hay chequeo de cuentas ni vigía de pagos que avise si una cuenta deja de gastar por un pago."], "sin medir")
    nombres = {"M-02": "La cuenta de Meta no está en orden", "M-03": "El tope de gasto o la forma de pago de la cuenta de anuncios no está en orden",
               "S-01": "La conexión de lectura con Stripe falla", "S-02": "Stripe no puede cobrar o pagar con normalidad", "S-07": "Hay muchas disputas o fraude sospechado"}
    malos = [f"{nombres[i]} ({i})." for i in nombres if pre["items"].get(i, {}).get("estado") not in (None, "VERDE")]
    faltan = [i for i in nombres if i not in pre["items"]]
    if malos:
        return _sec("pagos", "Pagos", "con_novedades", malos, _n(len(malos), "aviso de pago", "avisos de pago"))
    if faltan:
        return _sec("pagos", "Pagos", "sin_medir", [f"El chequeo no incluye {', '.join(faltan)}: no se puede decir que los pagos están en orden."], "sin medir")
    return _sec("pagos", "Pagos", "sin_novedades", ["Cuenta de Meta y Stripe en orden según el último chequeo."], "sin novedades")


def _aviso_importante(alertas: list[Any], ajenas: list[dict[str, Any]]) -> dict[str, Any]:
    """Alertas graves abiertas: las calculadas acá más las que otras reglas (F1, ventas y gasto de S-B) dejaron en ``alertas.jsonl`` (saneadas)."""
    graves = [a for a in alertas if a.fila["severidad"] in ("roja", "naranja")]
    graves_ajenas = [a for a in ajenas if a["severidad"] in ("roja", "naranja")]
    if not graves and not graves_ajenas:
        return _sec("importante", "Lo importante", "sin_novedades", ["Ninguna alerta roja abierta."], "sin alertas rojas")
    lineas = [f"{a.extra['titulo']} ({a.fila['regla_id']})." for a in graves]
    for a in graves_ajenas:
        lineas.append(f"{a['regla_id']}" + (f" · {a['oferta_id']}" if a.get("oferta_id") else "") + (f": {limpiar_texto(a['accion_sugerida'], 120)}" if a.get("accion_sugerida") else "") + ".")
    n = len(graves) + len(graves_ajenas)
    return _sec("importante", "Lo importante", "con_novedades", lineas, _n(n, "alerta roja", "alertas rojas"))


def _aviso_cansancio() -> dict[str, Any]:
    return _sec("cansancio", "Cansancio de anuncios", "sin_medir",
                ["Todavía no se mide: la alarma de cansancio (08:05) no existe y no hay datos de anuncios por día para comparar los últimos 3 días con los 7 anteriores."], "sin medir")


def _aviso_mercado_nuevo() -> dict[str, Any]:
    return _sec("mercado_nuevo", "Mercado nuevo", "sin_medir",
                ["Todavía no se mide: no hay versiones de una oferta en otros idiomas con ventas, ni tablero de países que avise cuándo un mercado nuevo empieza a vender."], "sin medir")


def _aviso_no_aprobado(h: dict[str, Any], t_ahora: _dt.datetime) -> dict[str, Any]:
    lineas: list[str] = []
    for g in h["ofertas"]["gates"][:MAX_LINEAS]:
        horas = horas_entre(parsear_z(g.get("desde")), t_ahora)
        nombre = NOMBRES_ETAPA.get(g["etapa"], g["etapa"])
        lineas.append(f"Espera tu firma: {nombre} de {g['oferta_id']}" + (f" (la oferta no cambia hace {horas} h)." if horas is not None else "."))
    venc = [p for p in h["pulido"]["abiertos"] if p.get("vencido")]
    if venc:
        lineas.append(f"{_n(len(venc), 'pendiente tuyo vencido', 'pendientes tuyos vencidos')}: {', '.join(p['id'] for p in venc[:6])}.")
    n = len(h["ofertas"]["gates"]) + len(venc)
    if n:
        return _sec("no_aprobado", "Lo que no aprobaste", "con_novedades", lineas, _n(n, "cosa sin resolver", "cosas sin resolver"))
    return _sec("no_aprobado", "Lo que no aprobaste", "sin_novedades", ["Ninguna firma espera por ti ni hay pendientes tuyos vencidos. (Los anuncios por aprobar todavía no se miden: falta la fábrica nocturna.)"], "nada esperando")


# ----------------------------------------------------------------------------------------------
# Los ceros
# ----------------------------------------------------------------------------------------------
def _cero(id_: str, texto: str, estado: str, valor: int | None, detalle: str) -> dict[str, Any]:
    return {"id": id_, "texto": texto, "esperado": 0, "estado": estado, "valor": valor, "detalle": detalle}


def _ceros(h: dict[str, Any], alertas: list[Any], ajenas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    graves = sum(1 for a in alertas if a.fila["severidad"] in ("roja", "naranja")) + sum(1 for a in ajenas if a["severidad"] in ("roja", "naranja"))
    plan, can, lim, v = h["planificador"], h["canales"], h["limites"], h["ventas"]
    sal = [_cero("pagos_sin_aviso", "Pagos frenados sin aviso al celular", "sin_medir", None, "No se puede medir: todavía no hay vigía de pagos ni canal de avisos.")]
    if plan["trabajos"]:
        sal.append(_cero("trabajos_sin_latido", "Trabajos sin señal de vida", "cumple" if plan["vencidos"] == 0 else "no_cumple", plan["vencidos"],
                         f"{plan['vencidos']} de {plan['n']} trabajos no dieron señal a tiempo."))
    else:
        sombra = plan.get("sombra")
        extra = ""
        if sombra:
            extra = (f" Los robots en sombra (solo lectura, no son el sistema real): {sombra['n_esperados']} programados"
                     + (f", {sombra['n_vencidos']} con la señal de vida vencida." if sombra["n_vencidos"] else ", todos al día.") if sombra["n_esperados"]
                     else " Los robots en sombra no están programados todavía.")
        sal.append(_cero("trabajos_sin_latido", "Trabajos sin señal de vida", "sin_medir", None, "No se puede medir: todavía no hay planificador real ni señales de vida por trabajo." + extra))
    if graves == 0:
        sal.append(_cero("graves_sin_aviso", "Alertas graves que no llegaron al celular", "cumple", 0, "No hay alertas graves abiertas."))
    elif can["n_probados"] == 0:
        sal.append(_cero("graves_sin_aviso", "Alertas graves que no llegaron al celular", "no_cumple", graves, f"{_n(graves, 'alerta grave', 'alertas graves')}, y no hay ningún canal probado: ninguna salió del panel."))
    else:
        sal.append(_cero("graves_sin_aviso", "Alertas graves que no llegaron al celular", "sin_medir", None, "Hay canal, pero todavía no existe el registro de envíos para comprobarlo."))
    tope, mon = lim.get("gasto_diario_global"), lim.get("moneda")
    if v["hay_datos"] and v["gasto"] and isinstance(tope, int) and tope > 0 and all(g["moneda"] == mon for g in v["gasto"]):
        pasa = sum(g["monto"] for g in v["gasto"]) > tope
        sal.append(_cero("gasto_sobre_tope", "Gasto por encima del tope diario", "no_cumple" if pasa else "cumple", 1 if pasa else 0, "Comparado con el tope diario firmado."))
    else:
        sal.append(_cero("gasto_sobre_tope", "Gasto por encima del tope diario", "sin_medir", None,
                         "No se puede medir: " + ("no hay un tope diario firmado." if not isinstance(tope, int) or tope <= 0 else "no hay datos de gasto.")))
    esperando = len(h["ofertas"]["gates"]) + sum(1 for p in h["pulido"]["abiertos"] if p.get("vencido"))
    sal.append(_cero("esperando_por_ti", "Firmas y pendientes tuyos vencidos", "cumple" if esperando == 0 else "no_cumple", esperando,
                     "Nada espera por ti." if esperando == 0 else f"{_n(esperando, 'cosa espera', 'cosas esperan')} por ti."))
    return sal


# ----------------------------------------------------------------------------------------------
# Lo que te toca a ti
# ----------------------------------------------------------------------------------------------
def _te_toca(h: dict[str, Any], sem: dict[str, Any]) -> list[dict[str, Any]]:
    sal: list[dict[str, Any]] = []
    for p in sem["pasos"]:
        if p["responsable"] == "dueno" and p["id"] != "firmas":
            sal.append({"tipo": "semaforo", "titulo": p["titulo"], "que_hacer": p["que_hacer"], "enlace": p["enlace"], "enlace_texto": p["enlace_texto"], "comando": p.get("comando"), "nivel": p["nivel"]})
    from scripts.alertas.reglas import comando_firmar
    for g in h["ofertas"]["gates"][:10]:
        sal.append({"tipo": "firma", "titulo": f"Firmar {NOMBRES_ETAPA.get(g['etapa'], g['etapa'])} de {g['oferta_id']}", "que_hacer": "Revísala y fírmala si estás de acuerdo.",
                    "enlace": f"#/oferta/{g['oferta_id']}", "enlace_texto": "Abrir la oferta", "comando": comando_firmar(g["oferta_id"], g["etapa"]), "nivel": "amarillo"})
    for p in h["pulido"]["abiertos"]:
        if p.get("prioridad") in ("P0", "P1"):
            sal.append({"tipo": "pendiente", "id": p["id"], "prioridad": p["prioridad"], "titulo": p.get("titulo") or p["id"], "que_hacer": "Resolverlo o cambiar su fecha.",
                        "enlace": "#/pulido", "enlace_texto": "Mejoras pendientes", "comando": None, "nivel": "rojo" if p.get("vencido") else "amarillo", "vencido": bool(p.get("vencido"))})
    return sal[:MAX_LINEAS]


# ----------------------------------------------------------------------------------------------
# Composición y render
# ----------------------------------------------------------------------------------------------
def componer(ctx: Ctx, *, fecha: str | None = None, hechos: dict[str, Any] | None = None) -> dict[str, Any]:
    """El informe como datos (secciones, ceros, «te toca») y sus dos versiones de texto. Nunca envía nada."""
    h = hechos if hechos is not None else leer_hechos(ctx, fecha_ventas=fecha)
    t_ahora = parsear_z(h["ahora"]) or _dt.datetime.now(_dt.timezone.utc)
    ev = estado_vigente(ctx, h)
    alertas = ev["alertas"]
    todas_ajenas = ajenas_de(ev)
    ajenas = [f for f in todas_ajenas if f["estado"] != "cerrada"][:MAX_LINEAS]
    sem = calcular_semaforo(h, todas_ajenas)
    exp = _exponentes(ctx)
    vg = _ventas_gasto(h, exp)
    avisos = [_aviso_pagos(h), _aviso_importante(alertas, ajenas), _aviso_cansancio(), _aviso_mercado_nuevo(), _aviso_no_aprobado(h, t_ahora)]
    ceros = _ceros(h, alertas, ajenas)
    te_toca = _te_toca(h, sem)
    sin_datos = [x["texto"] for x in ceros if x["estado"] == "sin_medir"] + [f"{a['titulo']} (aviso)" for a in avisos if a["estado"] == "sin_medir"]
    if not vg["hay_datos"]:
        sin_datos.insert(0, f"Ventas y gasto del {_fecha_es(vg['dia'])}")
    conteo = {k: sum(1 for a in alertas if a.fila["severidad"] == k) + sum(1 for a in ajenas if a["severidad"] == k) for k in ("roja", "naranja", "amarilla", "info")}
    informe: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION, "tipo": "informe_diario", "generado_en": h["ahora"], "fecha": h["ahora"][:10], "hora_objetivo": HORA_INFORME, "dia_medido": h["fecha_ventas"],
        "semaforo": {k: sem[k] for k in ("nivel", "titulo", "resumen", "faltan", "para_ti")},
        "alertas": {"abiertas": len(alertas) + len(ajenas), **conteo}, "ventas_gasto": vg, "avisos": avisos, "ceros": ceros, "te_toca": te_toca, "sin_datos": sin_datos[:MAX_LINEAS],
        "plantilla": "fija: sin texto libre de IA ni de terceros; los títulos de pendientes (texto de archivo) solo van en el correo, recortados y sin enlaces",
        "avisos_lectura": h["avisos"],
    }
    informe["versiones"] = {"correo": renderizar(informe, "correo"), "celular": renderizar(informe, "celular")}
    return informe


def renderizar(inf: dict[str, Any], version: str) -> dict[str, str]:
    """Texto plano de una versión: ``correo`` (con importes y detalle) o ``celular`` (solo porcentajes y recuentos)."""
    if version not in ("correo", "celular"):
        raise ValueError("version debe ser 'correo' o 'celular'")
    s = inf["semaforo"]
    fecha, dia = _fecha_es(inf["fecha"]), _fecha_es(inf["dia_medido"])
    etiqueta = s["nivel"].upper()
    if version == "celular":
        n_cero = sum(1 for c in inf["ceros"] if c["estado"] == "cumple")
        n_no = sum(1 for c in inf["ceros"] if c["estado"] == "no_cumple")
        n_sm = sum(1 for c in inf["ceros"] if c["estado"] == "sin_medir")
        tc = inf["te_toca"]
        nfirmas = sum(1 for t in tc if t["tipo"] == "firma")
        npend = sum(1 for t in tc if t["tipo"] == "pendiente")
        nsem = sum(1 for t in tc if t["tipo"] == "semaforo")
        L = [f"INFORME {fecha[:5]} {inf['hora_objetivo']}", f"{etiqueta}: {s['titulo'].lower()}", f"Faltan {s['faltan']} ({s['para_ti']} son tuyas)",
             f"Ventas y gasto: {inf['ventas_gasto']['celular']}"]
        L += [f"{a['titulo']}: {a['celular']}" for a in inf["avisos"]]
        L.append(f"Ceros: {n_cero} de {len(inf['ceros'])} cumplen · {n_no} no cumple{'n' if n_no != 1 else ''} · {n_sm} sin medir")
        L.append(f"Te toca: {nsem} del semáforo · {_n(nfirmas, 'firma', 'firmas')} · {_n(npend, 'pendiente', 'pendientes')}. Abre el panel.")
        texto = _sin_dinero("\n".join(L))
        return {"texto": texto}
    al = inf["alertas"]
    L = [f"INFORME DEL DÍA — {fecha} · {inf['hora_objetivo']}", f"Estado: {etiqueta} — {s['titulo']}", s["resumen"],
         f"Alertas abiertas: {al['abiertas']} ({_n(al['roja'] + al['naranja'], 'roja o naranja', 'rojas o naranjas')} · {_n(al['amarilla'], 'amarilla', 'amarillas')} · {al['info']} de información)", ""]
    L += [f"1. VENTAS Y GASTO (día medido: {dia})"] + [f"   {x}" for x in inf["ventas_gasto"]["correo"]] + [""]
    L += ["2. LOS 5 AVISOS"]
    for i, a in enumerate(inf["avisos"], 1):
        L.append(f"   {chr(96 + i)}) {a['titulo']} — {_ESTADO_SECCION[a['estado']].lower()}")
        L += [f"      · {x}" for x in a["correo"]]
    L += ["", "3. LOS CEROS QUE IMPORTAN (la meta es 0)"]
    for c in inf["ceros"]:
        resultado = "sin medir" if c["valor"] is None else f"{c['valor']} ({_ESTADO_CERO[c['estado']].lower()})"
        L.append(f"   · {c['texto']}: {resultado}. {c['detalle']}")
    L += ["", "4. LO QUE TE TOCA A TI"]
    if not inf["te_toca"]:
        L.append("   Nada: no te toca nada ahora.")
    pend = 0
    for i, t in enumerate(inf["te_toca"], 1):
        if t["tipo"] == "pendiente":
            pend += 1
            if pend > MAX_PENDIENTES_CORREO:
                continue
            L.append(f"   {i}. [{t['prioridad']}] {t['id']} · {limpiar_texto(t['titulo'], 100)}")
        else:
            L.append(f"   {i}. {t['titulo']} — {t['que_hacer']} ({t['enlace_texto']})")
    if pend > MAX_PENDIENTES_CORREO:
        L.append(f"   … y {pend - MAX_PENDIENTES_CORREO} pendientes más en Mejoras pendientes.")
    L += ["", "5. LO QUE TODAVÍA NO SE PUDO MEDIR"]
    L += [f"   · {x}" for x in inf["sin_datos"]] or ["   Nada: todo se midió."]
    L += ["", "Este informe lo arma un programa con una plantilla fija y solo lee archivos de tu proyecto. No contiene texto escrito por una IA ni por terceros."]
    asunto = f"[{etiqueta}] Informe del día {fecha}: {s['titulo'].lower()}"
    return {"asunto": asunto, "texto": "\n".join(L)}


# ----------------------------------------------------------------------------------------------
# Línea de comandos
# ----------------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.informe.informe_diario", description="Compone el informe del día (correo y celular). No envía nada.")
    ap.add_argument("--version", choices=("correo", "celular", "ambas"), default="ambas")
    ap.add_argument("--json", action="store_true", help="salida en JSON (todo el informe, con las dos versiones)")
    ap.add_argument("--raiz", default=None, help="raíz del proyecto (defecto: FABRICA_RAIZ o la carpeta de este código)")
    ap.add_argument("--ahora", default=None, help="instante fijo AAAA-MM-DDTHH:MM:SSZ")
    ap.add_argument("--fecha", default=None, help="día de las ventas y el gasto AAAA-MM-DD (defecto: ayer)")
    args = ap.parse_args(argv)
    raiz = Path(args.raiz or os.environ.get("FABRICA_RAIZ") or Path(__file__).resolve().parent.parent.parent)
    if not raiz.is_dir():
        print("error: --raiz no es una carpeta", file=sys.stderr)
        return 2
    ahora = parsear_z(args.ahora) if args.ahora else None
    if args.ahora and ahora is None:
        print("error: --ahora debe verse así: 2026-11-07T08:30:00Z", file=sys.stderr)
        return 2
    if args.fecha and not _RX_FECHA.match(args.fecha):
        print("error: --fecha debe verse así: 2026-11-06", file=sys.stderr)
        return 2
    ctx = Ctx(raiz, ahora=(lambda: ahora) if ahora else (lambda: _dt.datetime.now(_dt.timezone.utc)))
    inf = componer(ctx, fecha=args.fecha)
    if args.json:
        print(json.dumps(inf, ensure_ascii=False, indent=2))
        return 0
    v = inf["versiones"]
    if args.version in ("correo", "ambas"):
        print("=== CORREO ===")
        print(f"Asunto: {v['correo']['asunto']}\n")
        print(v["correo"]["texto"])
    if args.version in ("celular", "ambas"):
        print("\n=== CELULAR ===" if args.version == "ambas" else "=== CELULAR ===")
        print(v["celular"]["texto"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
