"""Trabajo de apoyo · Productor de alertas (cada 15 min), EN SOMBRA: calcula las alertas desde archivos y, solo con --escribir, deja empresa/datos/alertas.jsonl."""
from __future__ import annotations

from scripts.alertas.producir import ErrorArchivo, producir
from scripts.robots.nucleo import Contexto, Resultado

ID = "alertas"


def correr(c: Contexto) -> Resultado:
    try:
        res = producir(c.ctx(), escribir=c.escribir)
    except ErrorArchivo as exc:
        return Resultado("sin_decidir", f"no se pudo guardar con seguridad: {exc}"[:240],
                         ["El archivo de alertas no se puede tratar con seguridad; no se escribió nada."], datos={"escrito": False})
    graves = [a for a in res["alertas"] if a["severidad"] in ("roja", "naranja")]
    resumen = [f"{res['abiertas']} alertas abiertas ({len(graves)} rojas o naranjas) · {res['cerradas']} cerradas · "
               f"{'archivo ' + res['archivo'] + (' actualizado' if not res['sin_cambios'] else ' sin cambios') if res['modo'] == 'escrito' else 'SIMULACRO: no se escribió nada'}"]
    resumen += [f"  [{a['severidad'].upper()}] {a['id']}" for a in sorted(graves, key=lambda a: a["id"])[:8]]
    estado = "alerta" if graves else "ok"
    razon = f"{res['abiertas']} alertas abiertas, {len(graves)} graves; {res['modo']}"
    return Resultado(estado, razon, resumen,
                     datos={"abiertas": res["abiertas"], "graves": len(graves), "ids_graves": sorted(a["id"] for a in graves)[:20],
                            "semaforo": res["semaforo"]["nivel"], "modo": res["modo"], "escrito": res["modo"] == "escrito" and not res["sin_cambios"]},
                     salidas=[res["archivo"]] if res["modo"] == "escrito" and not res["sin_cambios"] else [])
