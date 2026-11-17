"""Catálogo de los 10 robots del método (``dashboard/web/lib/robots.js``, ``mapeo.md`` §2, brechas 02 §A.3) más 2 trabajos de apoyo.

Los ids y los números de los 10 robots son EXACTAMENTE los del panel (``ROBOTS`` en ``lib/robots.js``), para que ``#/robots`` pueda unirlos con el
registro real. Los dos de apoyo (``alertas`` y ``baja_j3``) no son robots del método: son programas que ya existen en sombra y necesitan su latido.

``ejecutor_hoy``: ``sombra`` = lo corre ``scripts.robots.sombra`` (S-C, solo lectura y propuesta) · ``ninguno`` = todavía no existe en sombra.
``ejecutor_manana`` = quién lo hará de verdad (S-B, con planificador, guard y reintentos). Las horas son HIPÓTESIS hasta calibrarlas (E-14).
"""
from __future__ import annotations

from typing import Any

__all__ = ["CATALOGO", "ORDEN_EJECUCION", "VERSION", "GRACIA_MIN", "por_id", "ids_en_sombra", "latido_max_min", "horas_programadas", "RESULTADOS"]

VERSION = "0.1.0"
GRACIA_MIN = 90                 # tolerancia sobre la hora programada (la Mac puede estar durmiendo y recuperar al despertar)
RESULTADOS = ("ok", "parcial", "sin_datos", "sin_decidir", "alerta", "error")


def _robot(id_: str, numero: int | None, nombre: str, *, tipo: str = "robot", pieza: str, horario: str, programacion: dict[str, Any],
           reloj: str = "mercado", lee: list[str], produce: str, accion_real: str, nivel_objetivo: str, ejecutor_hoy: str,
           ejecutor_manana: str, brechas: list[str], limite: str) -> dict[str, Any]:
    return {
        "id": id_, "numero": numero, "nombre": nombre, "tipo": tipo, "pieza": pieza, "horario": horario, "programacion": programacion,
        "reloj": reloj, "lee": lee, "produce": produce, "accion_real": accion_real, "nivel_actual": "N0", "nivel_objetivo": nivel_objetivo,
        "ejecutor_hoy": ejecutor_hoy, "ejecutor_manana": ejecutor_manana, "brechas": brechas, "limite": limite,
    }


CATALOGO: list[dict[str, Any]] = [
    _robot("escalera", 1, "Escalera de escala", pieza="Testeo y escala", horario="Cada 30 min", programacion={"tipo": "cada", "cada_min": 30},
           lee=["retorno del día de cada campaña de escala, medido con lo cobrado (UTM)", "si Meta ya gastó el presupuesto anterior (H-01)"],
           produce="(sombra futura) paso propuesto de presupuesto, anotado sin llamar a Meta",
           accion_real="reducir 30 % si no rinde; subir ×2", nivel_objetivo="N2 reducir (−30 %) · N3 subir (×2; ×3 y ×5 solo con acierto medido por el auditor)",
           ejecutor_hoy="ninguno", ejecutor_manana="S-B (runtime real: planificador + guard + meta.subir_presupuesto)", brechas=["B2-08", "B2-09", "B2-10", "B2-11"],
           limite="no apaga nada dentro de la escala (regla 1); paso máximo, techo diario J4 (300 USD) y pérdida acumulada J4 (−3.000 USD)"),
    _robot("salvavidas", 2, "Salvavidas", pieza="Testeo y escala", horario="Cada 15 min", programacion={"tipo": "cada", "cada_min": 15},
           lee=["lo vendido neto del día"], produce="(no se hace en sombra: es el de más riesgo)",
           accion_real="suma al presupuesto lo vendido neto del día, con tope", nivel_objetivo="N3, tras 15 pasos buenos de la escalera [hipótesis]",
           ejecutor_hoy="ninguno", ejecutor_manana="S-B", brechas=["B2-19"], limite="la fuente no da ningún número (E-07): no se construye sin ellos"),
    _robot("guardia", 3, "Guardia nocturno", pieza="Testeo y escala", horario="01:30 – 07:30 · 4 vueltas",
           programacion={"tipo": "vueltas", "horas": ["01:30", "03:30", "05:30", "07:30"]},
           lee=["lo que hicieron los demás robots", "tope de costo vigente"], produce="(no se hace en sombra: depende del tope de costo)",
           accion_real="ajusta el tope de costo de a poco; primera versión posible: revisor nocturno que reduce o pausa", nivel_objetivo="N3",
           ejecutor_hoy="ninguno", ejecutor_manana="S-B", brechas=["B2-08", "B2-20"], limite="el tope de costo (cost cap) no existe todavía en el formato de campaña"),
    _robot("cola", 4, "Cola de testeo", pieza="Testeo y escala", horario="00:10", programacion={"tipo": "diaria", "horas": ["00:10"]},
           lee=["tanda del día (cargada en pausa por la tarde)", "sello de X1 vigente", "chequeo antes de lanzar", "frenos de empresa"],
           produce="(no se hace en sombra: prender es mover dinero)", accion_real="prende los conjuntos nuevos del día",
           nivel_objetivo="J2: sin clic, con sello de X1 + chequeo antes de lanzar en verde + frenos de empresa", ejecutor_hoy="ninguno", ejecutor_manana="S-B (guard + meta.activar)",
           brechas=["B2-03", "B2-16", "B4-19"], limite="solo con sello X1, chequeo en verde y frenos J4; sin eso no prende nada"),
    _robot("perfil", 5, "Perfil por idioma", pieza="Testeo y escala", horario="23:40", programacion={"tipo": "diaria", "horas": ["23:40"]},
           lee=["pedidos cobrados y gasto de Meta por oferta (base en solo lectura)", "idioma de cada oferta (mercado.json)", "KPI diarios si no hay base"],
           produce="resumen de lo vendido y gastado por idioma; la FASE no se calcula (faltan umbrales, E-09)", accion_real="ninguna (alimenta a los demás)",
           nivel_objetivo="N0, en sombra desde el inicio", ejecutor_hoy="sombra", ejecutor_manana="S-B (medición horaria por idioma)",
           brechas=["B2-17", "B2-11"], limite="solo lectura; no mezcla monedas; sin fase ni meta ni tope hasta tener umbrales (E-09)"),
    _robot("alarma", 6, "Alarma de cansancio", pieza="Fábrica de anuncios", horario="08:05", programacion={"tipo": "diaria", "horas": ["08:05"]},
           lee=["serie por anuncio y día (base en solo lectura)", "umbrales testeo.fatiga_* de parametros.yaml"],
           produce="detección de fatiga (últimos 3 días contra los 7 anteriores) y propuesta de relevo/aviso; sin los umbrales dice «sin decidir»",
           accion_real="pedido de relevo a D6 dentro de los topes", nivel_objetivo="N2 con revisión · N3 automático con tope de créditos",
           ejecutor_hoy="sombra", ejecutor_manana="S-B (engine.d8 FT) + S-C (pedido a D6)", brechas=["B2-18", "B2-12"],
           limite="propone; no pide nada a D6; alcance hoy = todos los anuncios de la oferta, no solo la escala (H-06)"),
    _robot("vigia", 7, "Vigía de pagos", pieza="Robots", horario="Siempre · revisión cada 15 min", programacion={"tipo": "cada", "cada_min": 15},
           lee=["empresa/infra/estado.json (M-02, M-03, S-01, S-02, S-07) y su frescura", "frescura de las lecturas de Meta en la base",
                "gasto de ayer en 0 con presupuesto > 0 en ofertas activas"],
           produce="mide si los estados de pago y de cuenta están frescos y en verde; no llama a Stripe ni a Meta; no avisa al celular",
           accion_real="avisa al celular y pausa", nivel_objetivo="N0 (la pausa es la única escritura sin firma)", ejecutor_hoy="sombra",
           ejecutor_manana="S-B (sondas M-02/M-03 reales + canal de avisos + watchdog que pausa)", brechas=["B2-21", "B4-12", "B4-22"],
           limite="solo lectura; sin canal de avisos elegido no hay aviso; N de horas sin gasto sin fijar (E-12)"),
    _robot("bandeja", 8, "Bandeja", pieza="Robots", horario="07:00 y 19:00", programacion={"tipo": "diaria", "horas": ["07:00", "19:00"]},
           lee=["comentarios, mensajes y correos"], produce="(no se hace en sombra: depende del correo transaccional y de plantillas X1)",
           accion_real="responde con plantillas aprobadas por X1; sin consejo médico ni financiero", nivel_objetivo="N2 o superior, con revisión",
           ejecutor_hoy="ninguno", ejecutor_manana="S-C (triaje y plantillas) + S-B (envío)", brechas=["B2-23", "B4-27", "B4-31"],
           limite="fase tardía: sin correo transaccional ni permisos de página no hay nada que leer"),
    _robot("informe", 9, "Informe del día", pieza="Cerebro y avisos", horario="08:30", programacion={"tipo": "diaria", "horas": ["08:30"]}, reloj="dueno",
           lee=["los mismos archivos que el semáforo «¿me puedo ausentar?» (scripts.alertas.hechos)"],
           produce="el informe compuesto en dos versiones (correo con importes, celular sin dinero), guardado como archivo; NO se envía",
           accion_real="enviar el correo y el mensaje por el canal que elija el dueño", nivel_objetivo="N0", ejecutor_hoy="sombra",
           ejecutor_manana="S-B (envío + registro de envíos)", brechas=["B2-22", "B4-24", "B4-22"],
           limite="no envía; la hora es la del dueño (avisos.resumen_diario_hora); sin canal elegido, queda en el archivo"),
    _robot("auditor", 10, "Auditor", pieza="Robots", horario="Cada hora", programacion={"tipo": "cada", "cada_min": 60},
           lee=["ofertas/*/08-operacion/decisiones.jsonl", "pedidos cobrados y gasto de Meta (base en solo lectura)", "economia.json (CPA de equilibrio)"],
           produce="acierto de cortes y de subas por separado, con la muestra; no degrada a nadie (propone)",
           accion_real="califica cada decisión con lo que pasó después y baja de nivel al robot que falla", nivel_objetivo="N1 en sombra, luego N2",
           ejecutor_hoy="sombra", ejecutor_manana="S-B (decisiones con resultado posterior + descenso de nivel)", brechas=["B2-24", "B2-25", "B4-14"],
           limite="la ventana de juicio (72 h) y la definición de acierto son HIPÓTESIS (E-11); un corte ejecutado no se puede contrastar sin grupo de control"),
    # ── Trabajos de apoyo: no son de los 10, pero ya existen en sombra y deben dar su señal de vida ──
    _robot("alertas", None, "Productor de alertas", tipo="apoyo", pieza="Cerebro y avisos", horario="Cada 15 min", programacion={"tipo": "cada", "cada_min": 15},
           lee=["los mismos archivos del semáforo"], produce="empresa/datos/alertas.jsonl (solo con --escribir; idempotente)",
           accion_real="igual: S-B solo lo programa y envía las graves por el canal", nivel_objetivo="N0", ejecutor_hoy="sombra",
           ejecutor_manana="S-B (programarlo en el host)", brechas=["B4-23"], limite="solo lectura de archivos; no envía"),
    _robot("baja_j3", None, "Baja del día 1 (J3)", tipo="apoyo", pieza="Testeo y escala", horario="09:00", programacion={"tipo": "diaria", "horas": ["09:00"]},
           lee=["base en solo lectura (preparar_expediente)", "umbrales lanzamiento.* de parametros.yaml"],
           produce="PROPUESTA de baja por oferta (regla J3 de proponer.py); sin los umbrales dice «sin decidir»",
           accion_real="engine.d8: pausar la campaña de lanzamiento que no vendió con el presupuesto gastado", nivel_objetivo="N2",
           ejecutor_hoy="sombra", ejecutor_manana="S-B (engine/d8.py, B2-01)", brechas=["B2-01", "B2-14"],
           limite="propone; no pausa nada; el grupo lanzamiento.* de parametros.yaml no existe todavía"),
]

# Orden de una corrida «--todos» (H4-03: cada trabajo mira insumos del día): primero lo que mide, al final lo que compone con todo lo anterior.
ORDEN_EJECUCION = ["perfil", "alertas", "vigia", "alarma", "baja_j3", "auditor", "informe"]


def por_id(id_: str) -> dict[str, Any] | None:
    return next((r for r in CATALOGO if r["id"] == id_), None)


def ids_en_sombra() -> list[str]:
    """Ids con versión en sombra, en el orden de ejecución."""
    en_sombra = {r["id"] for r in CATALOGO if r["ejecutor_hoy"] == "sombra"}
    return [i for i in ORDEN_EJECUCION if i in en_sombra]


def horas_programadas(robot: dict[str, Any]) -> list[str]:
    """«HH:MM» programadas de un robot diario o de vueltas; vacío si es periódico."""
    prog = robot["programacion"]
    return list(prog.get("horas", [])) if prog["tipo"] in ("diaria", "vueltas") else []


def _min(hora: str) -> int:
    h, m = hora.split(":")
    return int(h) * 60 + int(m)


def latido_max_min(robot: dict[str, Any]) -> int:
    """Edad máxima aceptable del último latido: periódico = 2 × período + 5; diario = mayor hueco entre ocurrencias + ``GRACIA_MIN``."""
    prog = robot["programacion"]
    if prog["tipo"] == "cada":
        return 2 * int(prog["cada_min"]) + 5
    horas = sorted(_min(h) for h in prog["horas"])
    huecos = [(horas[(i + 1) % len(horas)] - horas[i]) % 1440 or 1440 for i in range(len(horas))]
    return max(huecos) + GRACIA_MIN
