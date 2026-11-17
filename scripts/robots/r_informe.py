"""Robot 9 · Informe del día (08:30, reloj del dueño), EN SOMBRA: compone el informe (correo y celular) y lo guarda como archivo. NO lo envía."""
from __future__ import annotations

from scripts.informe.informe_diario import HORA_INFORME, componer
from scripts.robots.nucleo import Contexto, Resultado

ID = "informe"


def correr(c: Contexto) -> Resultado:
    inf = componer(c.ctx(), hechos=c.hechos())
    sem, al = inf["semaforo"], inf["alertas"]
    sin_medir = list(inf["sin_datos"])
    salida = c.guardar(ID, inf)
    resumen = [
        f"Semáforo «¿me puedo ausentar?»: {sem['nivel'].upper()} — {sem['titulo']}",
        f"Alertas abiertas: {al['abiertas']} ({al['roja'] + al['naranja']} rojas o naranjas).",
        f"Bloques todavía sin medir: {len(sin_medir)}.",
        f"Compuesto para las {HORA_INFORME}; NO se envió (no hay canal de avisos conectado a esta sombra).",
    ]
    razon = f"informe compuesto (semáforo {sem['nivel']}); {len(sin_medir)} bloque(s) sin medir; no se envió"
    return Resultado("parcial" if sin_medir else "ok", razon, resumen,
                     datos={"semaforo": sem["nivel"], "alertas": al, "sin_medir": len(sin_medir), "dia_medido": inf["dia_medido"],
                            "enviado": False},
                     salidas=[salida] if salida else [])
