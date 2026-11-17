"""Robot 7 · Vigía de pagos (siempre; revisión cada 15 min), EN SOMBRA: mide si los estados de pago y de cuenta están FRESCOS y en verde.

Lee ``empresa/infra/estado.json`` (ítems M-02, M-03, S-01, S-02, S-07 y su vigencia), la frescura de las lecturas de Meta en la base (solo lectura) y si una
oferta activa gastó ayer algo con presupuesto mayor que cero. NO llama a Stripe ni a Meta, NO avisa al celular, NO pausa: el aviso y la pausa son del
vigía real (S-B: sondas reales + canal de avisos + watchdog). Cada comprobación termina en ``ok``, ``falla``, ``no_medido`` (falta el dato o el umbral:
nunca se da por buena) o ``no_aplica``.
"""
from __future__ import annotations

from typing import Any

from scripts.robots.nucleo import RX_OFERTA_REAL, Contexto, Resultado, parsear_z, tabla_existe

ID = "vigia"
ITEMS_PAGO = (("M-02", "el estado de la cuenta de Meta"), ("M-03", "el tope de gasto y la forma de pago de la cuenta de anuncios"),
              ("S-01", "la lectura de Stripe"), ("S-02", "que Stripe pueda cobrar y pagar"), ("S-07", "las disputas y el fraude"))
FASES_ACTIVAS = ("en_test", "escalando")
FACTOR_FRESCURA_META = 2        # [HIPÓTESIS] una lectura de Meta es fresca si tiene menos de 2 × dashboard.etl_meta_cada_h horas


def _c(id_: str, texto: str, estado: str, detalle: str) -> dict[str, str]:
    return {"id": id_, "texto": texto, "estado": estado, "detalle": detalle}


def _chequeo_de_cuentas(c: Contexto) -> list[dict[str, str]]:
    pre = c.hechos()["preflight"]
    if not pre.get("existe"):
        return [_c("V01", "Hay un chequeo de cuentas y servicios", "no_medido", "No existe empresa/infra/estado.json: sin chequeo no se puede decir que los pagos están en orden.")]
    sal: list[dict[str, str]] = []
    modo = pre.get("modo")
    sal.append(_c("V01", "El chequeo es real (no de prueba)", "ok" if modo == "vivo" else "no_medido",
                  "Modo vivo." if modo == "vivo" else f"El chequeo es de modo «{modo}»: no vale para decir que los pagos están en orden."))
    vig, edad = pre.get("vigencia_h"), pre.get("edad_h")
    if vig is None:
        sal.append(_c("V02", "El chequeo está vigente", "no_medido", "Falta infra.hc_preflight_vigencia_horas en parametros.yaml."))
    elif edad is None:
        sal.append(_c("V02", "El chequeo está vigente", "no_medido", "El chequeo no trae una fecha legible."))
    else:
        sal.append(_c("V02", "El chequeo está vigente", "ok" if edad <= vig else "falla", f"Tiene {edad} h y vale {vig} h."))
    for id_, texto in ITEMS_PAGO:
        it = pre["items"].get(id_)
        if it is None:
            sal.append(_c(f"V03-{id_}", f"En verde: {texto}", "no_medido", f"El chequeo no incluye {id_}."))
        elif it.get("estado") == "VERDE":
            sal.append(_c(f"V03-{id_}", f"En verde: {texto}", "ok", f"{id_} en VERDE."))
        elif it.get("estado") in (None, "PENDIENTE", "PENDIENTE_EXTERNO"):
            sal.append(_c(f"V03-{id_}", f"En verde: {texto}", "no_medido", f"{id_} sin medir todavía ({it.get('estado')})."))
        else:
            sal.append(_c(f"V03-{id_}", f"En verde: {texto}", "falla", f"{id_} está en {it.get('estado')}."))
    return sal


def _lecturas_de_meta(c: Contexto, conn: Any) -> tuple[dict[str, str], bool | None]:
    """V04: la última lectura de Meta en la base es reciente. Devuelve (comprobación, fresca|None)."""
    etl = c.parametro("dashboard", "etl_meta_cada_h")
    if not isinstance(etl, int) or isinstance(etl, bool) or etl <= 0:
        return _c("V04", "Las lecturas de Meta en la base son recientes", "no_medido", "Falta dashboard.etl_meta_cada_h en parametros.yaml."), None
    if not tabla_existe(conn, "fact_meta_ad_dia"):
        return _c("V04", "Las lecturas de Meta en la base son recientes", "no_medido", "La base no tiene fact_meta_ad_dia."), None
    ultima = conn.execute("SELECT MAX(ingerido_en) FROM fact_meta_ad_dia").fetchone()[0]
    t = parsear_z(ultima) if isinstance(ultima, str) else None
    if t is None:
        return _c("V04", "Las lecturas de Meta en la base son recientes", "no_medido", "La base no tiene ninguna lectura de Meta (¿no hay campañas, o el ETL nunca corrió?)."), None
    edad_h = max(0, int((c.ahora() - t).total_seconds() // 3600))
    limite = FACTOR_FRESCURA_META * etl
    fresca = edad_h <= limite
    return _c("V04", "Las lecturas de Meta en la base son recientes", "ok" if fresca else "falla",
              f"La última tiene {edad_h} h; se acepta hasta {limite} h (2 × la carga cada {etl} h; HIPÓTESIS)."), fresca


def _presupuesto_diario(c: Contexto, oferta_id: str) -> int | None:
    lec = c.ctx().oferta(oferta_id).json("07-campana/campana.json")
    pres = lec.dato.get("presupuesto") if lec.ok and isinstance(lec.dato, dict) else None
    v = pres.get("diario") if isinstance(pres, dict) else None
    return v if isinstance(v, int) and not isinstance(v, bool) and v > 0 else None


def _gasto_ayer(c: Contexto, conn: Any, fresca: bool | None) -> dict[str, str]:
    """V06: una oferta activa con presupuesto > 0 no puede haber gastado 0 ayer (podría ser un pago frenado)."""
    texto = "Las ofertas activas gastaron algo ayer"
    activas: list[tuple[str, int]] = []
    for oid in c.hechos()["ofertas"]["ids_reales"]:
        if not RX_OFERTA_REAL.match(oid):
            continue
        est = c.ctx().oferta(oid).json("estado.json")
        d = est.dato if est.ok and isinstance(est.dato, dict) else {}
        if d.get("fase") in FASES_ACTIVAS and d.get("pausa") is not True:
            pres = _presupuesto_diario(c, oid)
            if pres is not None:
                activas.append((oid, pres))
    if not activas:
        return _c("V06", texto, "no_aplica", "No hay ofertas en test ni en escala con presupuesto diario legible: nada que vigilar.")
    if conn is None:
        return _c("V06", texto, "no_medido", "Hay ofertas activas pero no hay base de datos para ver el gasto.")
    if fresca is not True:
        return _c("V06", texto, "no_medido", "Las lecturas de Meta no son recientes o no se pudo medir su frescura: un gasto en 0 no probaría nada.")
    ayer = c.fecha_cuenta
    sin_gasto = []
    for oid, _pres in activas:
        g = conn.execute("SELECT COALESCE(SUM(gasto_minor), 0) FROM fact_meta_ad_dia WHERE oferta_id = ? AND fecha = ?", (oid, ayer)).fetchone()[0]
        if int(g) == 0:
            sin_gasto.append(oid)
    if sin_gasto:
        return _c("V06", texto, "falla", f"{', '.join(sorted(sin_gasto))}: gasto {ayer} en 0 con presupuesto diario mayor que 0 (¿pago frenado, cuenta o entrega?).")
    return _c("V06", texto, "ok", f"{len(activas)} oferta(s) activa(s) con gasto el {ayer}.")


def correr(c: Contexto) -> Resultado:
    checks = _chequeo_de_cuentas(c)
    with c.abrir_db() as conn:
        if conn is None:
            checks.append(_c("V04", "Las lecturas de Meta en la base son recientes", "no_medido", "No hay base de datos (empresa/datos/fabrica.db)."))
            fresca = None
        else:
            v04, fresca = _lecturas_de_meta(c, conn)
            checks.append(v04)
        checks.append(_c("V05", "Los pedidos de Stripe llegan a la base", "no_medido",
                         "No se puede medir: el ETL de Stripe no deja marca de su última corrida (solo la fecha de la última venta) y esta sombra no llama a Stripe."))
        checks.append(_gasto_ayer(c, conn, fresca))
        checks.append(_c("V07", "Gasto en 0 con presupuesto > 0 durante N horas (alerta de mapeo)", "no_medido",
                         "Falta fijar N (E-12) y la base solo trae el gasto por día, no por hora."))
    cuenta = {e: sum(1 for k in checks if k["estado"] == e) for e in ("ok", "falla", "no_medido", "no_aplica")}
    fallan = [k for k in checks if k["estado"] == "falla"]
    if fallan:
        estado = "alerta"
    elif cuenta["ok"] == 0:
        estado = "sin_datos"
    elif cuenta["no_medido"]:
        estado = "parcial"
    else:
        estado = "ok"
    doc = {"tipo": "vigia_pagos_sombra", "es_propuesta": True, "ahora": c.ahora().strftime("%Y-%m-%dT%H:%M:%SZ"), "comprobaciones": checks, "conteo": cuenta,
           "avisa_al_celular": False, "pausa": False,
           "nota": "Esta sombra solo mide; el aviso al celular y la pausa son del vigía real (S-B, B2-21 y B4-12)."}
    salida = c.guardar(ID, doc)
    resumen = [f"{cuenta['ok']} bien · {cuenta['falla']} fallan · {cuenta['no_medido']} sin medir · {cuenta['no_aplica']} no aplica(n)."]
    resumen += [f"  FALLA {k['id']}: {k['detalle']}" for k in fallan]
    resumen += [f"  sin medir {k['id']}: {k['texto']}" for k in checks if k["estado"] == "no_medido"][:6]
    resumen.append("No llamó a Stripe ni a Meta, no avisó al celular y no pausó nada.")
    razon = (f"{cuenta['falla']} comprobación(es) fallan: " + ", ".join(k["id"] for k in fallan)) if fallan else \
        f"{cuenta['ok']} bien, {cuenta['no_medido']} sin medir; no avisa ni pausa (solo mide)"
    return Resultado(estado, razon[:300], resumen, datos=doc, salidas=[salida] if salida else [])
