"""``GET /api/alertas`` y ``GET /api/informe`` (solo lectura): alertas, semáforo «¿me puedo ausentar?» e informe de las 08:30.

Todo se CALCULA al pedirlo, con los mismos módulos que el productor de línea de comandos (``scripts.alertas``, ``scripts.informe``), leyendo SOLO archivos
locales a través del resolvedor confinado de ``dashboard/archivos.py`` (sin red, sin claves, sin ``.env``). El panel no escribe nada acá: guardar
``empresa/datos/alertas.jsonl`` lo hace el productor con ``--escribir`` (``python -m scripts.alertas.producir --escribir``).

* ``alertas`` devuelve el estado vigente: las alertas calculadas AHORA + las ya cerradas del archivo + las líneas ajenas (F1, ventas) saneadas.
* El texto de todo archivo es DATO no confiable: las líneas ajenas pasan por una lista blanca de claves, de tipos y de largos.
* Topes: ≤ 200 alertas, ≤ 300 caracteres por acción, listas de semáforo e informe acotadas (los módulos de arriba ya las acotan).
"""
from __future__ import annotations

from typing import Any

from dashboard.api_base import Ctx, Sobre
from dashboard.archivos import iso_mtime
from scripts.alertas.ajenas import sanear_ajena
from scripts.alertas.hechos import REL_ALERTAS
from scripts.alertas.producir import COMANDO_ESCRIBIR, ajenas_de, es_nuestra, estado_vigente
from scripts.alertas.reglas import CATALOGO, REGLAS_PENDIENTES
from scripts.alertas.semaforo import calcular_semaforo
from scripts.informe import informe_diario

__all__ = ["alertas", "informe"]

MAX_ALERTAS = 200
FUENTE_ALERTAS = [
    "empresa/PAUSA", "empresa/captura/freno.json", "empresa/infra/estado.json", "empresa/limites.yaml", "empresa/parametros.yaml", "empresa/avisos.yaml",
    "empresa/infra/latidos.json", "empresa/robots.yaml", "ofertas/*/estado.json", "empresa/panel/pulido.jsonl", REL_ALERTAS,
]
FUENTE_INFORME = [*FUENTE_ALERTAS, "ofertas/*/08-operacion/diario/*/kpi_oferta_dia.json"]


def alertas(ctx: Ctx) -> Sobre:
    """``{alertas, resumen, semaforo, archivo, reglas}`` calculado ahora desde los archivos (nunca escribe)."""
    ev = estado_vigente(ctx)
    h = ev["hechos"]
    vivas = {a.fila["id"]: a for a in ev["alertas"]}
    filas: list[dict[str, Any]] = []
    for fila, cruda in ev["filas"]:
        if fila.get("_basura"):
            continue
        if cruda is not None:                         # ajena: saneada
            s = sanear_ajena(fila)
            if s is not None:
                filas.append(s)
            continue
        a = vivas.get(fila["id"])
        extra = a.extra if a is not None else {"titulo": CATALOGO.get(fila["regla_id"], {}).get("nombre"), "responsable": None, "responsable_texto": None,
                                              "area": CATALOGO.get(fila["regla_id"], {}).get("area"), "enlace": None, "comando": None, "detalle": None}
        filas.append({**fila, **extra, "fuente": "calculada"})
    filas = filas[-MAX_ALERTAS:]
    abiertas = [f for f in filas if f["estado"] != "cerrada"]
    resumen = {
        "abiertas": len(abiertas), "cerradas": len(filas) - len(abiertas),
        "rojas": sum(1 for f in abiertas if f["severidad"] == "roja"), "naranjas": sum(1 for f in abiertas if f["severidad"] == "naranja"),
        "amarillas": sum(1 for f in abiertas if f["severidad"] == "amarilla"), "info": sum(1 for f in abiertas if f["severidad"] == "info"),
        "para_ti": sum(1 for f in abiertas if f.get("responsable") == "dueno"),
    }
    st = ctx.raiz_confinada.stat(REL_ALERTAS)
    en_archivo = {(o["id"], o.get("severidad")) for o, _ in ev["previas"] if es_nuestra(o) and o.get("estado") != "cerrada"}
    en_vivo = {(a.fila["id"], a.fila["severidad"]) for a in ev["alertas"]}
    archivo = {
        "ruta": REL_ALERTAS, "existe": st is not None, "actualizado_en": iso_mtime(st) if st is not None else None, "lineas": len(ev["previas"]),
        "al_dia": st is not None and not ev["archivo_ilegible"] and en_archivo == en_vivo, "ilegible": bool(ev["archivo_ilegible"]), "comando_escribir": COMANDO_ESCRIBIR,
    }
    datos = {
        "alertas": filas, "resumen": resumen, "semaforo": calcular_semaforo(h, ajenas_de(ev)), "archivo": archivo,
        "reglas": {"calculadas": sorted(CATALOGO), "pendientes": REGLAS_PENDIENTES},
    }
    avisos = list(h["avisos"])
    if ev["archivo_ilegible"]:
        avisos.append("El archivo de alertas guardado no se pudo leer entero; se muestran solo las alertas calculadas ahora.")
    return Sobre(datos, FUENTE_ALERTAS, vacio=False, avisos=avisos)


def informe(ctx: Ctx) -> Sobre:
    """El informe de las 08:30 compuesto ahora (correo con importes y celular con porcentajes). El panel no lo envía: lo envía S-B con el canal."""
    inf = informe_diario.componer(ctx)
    return Sobre(inf, FUENTE_INFORME, vacio=False, avisos=list(inf.get("avisos_lectura") or []))
