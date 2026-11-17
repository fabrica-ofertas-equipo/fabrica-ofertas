"""Reglas de alerta que se pueden calcular SOLO con archivos locales (sin datos de ventas ni de gasto).

Cada alerta sigue ``contratos/alertas.schema.json`` (una línea = el estado vigente de una alerta; ``id`` = regla × objeto × ventana):

* ``F2-A16`` y ``F2-A17`` son reglas que ya existen en ``docs/04`` §5 (conexión crítica caída o estado viejo; señal de vida ausente).
* ``F2-AUS-*`` («ausencia») son reglas NUEVAS de este productor para el objetivo «me puedo ausentar» (brechas/04 B4-23, B4-26). Se piden a S-A
  para que entren en ``docs/04`` §5 (ver ``coordinacion-sesiones.md``). El patrón de ``regla_id`` del esquema las admite sin cambios.

El texto de ``accion_sugerida`` es una PLANTILLA FIJA en tuteo, de ≤ 300 caracteres: empieza por QUIÉN lo hace («Te toca a ti», «Le toca al
equipo técnico (S-B)») y no copia texto de ningún archivo (ni títulos ni motivos): así no puede filtrar nada ni obedecer texto ajeno.
Los títulos y los enlaces para la persona viajan aparte (``Alerta.extra``): el archivo ``alertas.jsonl`` solo guarda el esquema.

Las reglas de ventas y gasto (F2-A01…A15) NO se calculan aquí: ver ``REGLAS_PENDIENTES`` (cada una con el dato que necesita).
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any

from dashboard.api_base import NOMBRES_ETAPA
from scripts.alertas.hechos import RX_OFERTA_REAL, horas_entre, limpiar_texto, parsear_z

__all__ = [
    "Alerta", "CANALES_MIN", "CATALOGO", "REGLAS_PENDIENTES", "REGLAS_PROPIAS", "RESPONSABLE_TEXTO", "SCHEMA_VERSION",
    "accion", "calcular_alertas", "comando_firmar",
]

SCHEMA_VERSION = "1.0.0"
CANALES_MIN = 2           # docs/04 §9 y D0: las alertas críticas van por al menos dos canales (regla del proyecto, no un parámetro afinable)
COMANDO_FIRMAR_LIMITES = ("FABRICA_ENTORNO=produccion .venv/bin/python -m engine.propuestas sellar --como dueno --live "
                          "--clave-privada <ruta_de_tu_clave_privada>")     # el mismo que muestra «Quién decide qué»; solo se MUESTRA
MAX_ACCION = 300          # contratos/alertas.schema.json: accion_sugerida ≤ 300
MAX_GATES = 20
MAX_VENCIDOS = 20

RESPONSABLE_TEXTO = {
    "dueno": "Te toca a ti",
    "S-A": "Le toca al equipo de contratos y documentos (S-A)",
    "S-B": "Le toca al equipo técnico (S-B)",
    "S-C": "Le toca al equipo del panel (S-C)",
}
RESPONSABLE_CORTO = {"dueno": "Tú", "S-A": "Equipo S-A", "S-B": "Equipo técnico (S-B)", "S-C": "Equipo del panel (S-C)"}

# regla_id → nombre en lenguaje simple y área (las reglas F2-A16/A17 conservan el nombre de docs/04 §5 en el panel)
CATALOGO: dict[str, dict[str, str]] = {
    "F2-A16": {"nombre": "Cuentas y servicios sin comprobar o en rojo", "area": "seguridad"},
    "F2-A17": {"nombre": "Trabajos sin señal de vida", "area": "trabajo"},
    "F2-AUS-PLAN": {"nombre": "Todavía no hay planificador", "area": "trabajo"},
    "F2-AUS-PAUSA": {"nombre": "PAUSA (freno de emergencia) puesta", "area": "seguridad"},
    "F2-AUS-FRENO": {"nombre": "Freno de la captura de anuncios puesto", "area": "seguridad"},
    "F2-AUS-LIM": {"nombre": "Límites de dinero sin fijar", "area": "seguridad"},
    "F2-AUS-SELLO": {"nombre": "Límites sin tu firma", "area": "seguridad"},
    "F2-AUS-CANAL": {"nombre": "Avisos al celular sin dos canales", "area": "avisos"},
    "F2-AUS-META": {"nombre": "Cuenta de Meta sin dejar lista", "area": "venta"},
    "F2-AUS-CORREO": {"nombre": "Correo para entregar el producto sin dejar listo", "area": "venta"},
    "F2-AUS-SALDO": {"nombre": "Saldo de la cuenta de anuncios bajo", "area": "venta"},
    "F2-AUS-GATE": {"nombre": "Firma que espera por ti", "area": "trabajo"},
    "F2-AUS-VENCE": {"nombre": "Pendiente tuyo vencido", "area": "trabajo"},
}
REGLAS_PROPIAS = frozenset(CATALOGO)

# Reglas de docs/04 §5 que este productor NO calcula todavía: qué dato necesitan y de dónde saldría. (TODO de S-B: el ETL y los KPI de ventas.)
REGLAS_PENDIENTES: list[dict[str, str]] = [
    {"regla_id": "F2-A01", "nombre": "Datos de Meta desactualizados", "requiere": "hora de la última lectura de Meta por oferta (ETL de Meta, cada 3 h)", "archivo": "empresa/datos/ (lo escribe el ETL de Meta; aún no existe)", "de": "S-B"},
    {"regla_id": "F2-A02", "nombre": "Eventos de Stripe desactualizados", "requiere": "señal de vida del receptor de eventos de Stripe", "archivo": "empresa/datos/ (webhook de Stripe sin desplegar)", "de": "S-B"},
    {"regla_id": "F2-A03", "nombre": "Movimientos de saldo de Stripe desactualizados", "requiere": "hora de la última carga de balance_transactions", "archivo": "empresa/datos/ (ETL de Stripe, 03:00 UTC)", "de": "S-B"},
    {"regla_id": "F2-A04", "nombre": "Pedidos que no coinciden con Stripe", "requiere": "pedidos y balance_transactions conciliados", "archivo": "empresa/finanzas/conciliacion.json", "de": "S-B"},
    {"regla_id": "F2-A05", "nombre": "Gasto distinto del que informa Meta", "requiere": "gasto guardado y reconsulta de Meta", "archivo": "empresa/finanzas/conciliacion.json", "de": "S-B"},
    {"regla_id": "F2-A06", "nombre": "Compras de Meta y de Stripe que no coinciden", "requiere": "razon_meta_stripe con ventas suficientes", "archivo": "ofertas/<id>/08-operacion/diario/<fecha>/kpi_oferta_dia.json", "de": "S-B"},
    {"regla_id": "F2-A07", "nombre": "Pocas ventas atribuidas a un anuncio", "requiere": "cobertura de adid de los pedidos", "archivo": "empresa/datos/ (pedidos con atribución)", "de": "S-B"},
    {"regla_id": "F2-A08", "nombre": "Gasto del día por encima de lo posible", "requiere": "gasto del día y presupuesto de la campaña", "archivo": "kpi_oferta_dia.json y ofertas/<id>/07-campana/campana.json", "de": "S-B"},
    {"regla_id": "F2-A09", "nombre": "Gasto cerca de su tope o pérdida acumulada alta", "requiere": "gasto del día, pérdida acumulada y los límites firmados (300 USD por día, −3.000 USD)", "archivo": "kpi_oferta_dia.json, empresa/finanzas/pnl.json y empresa/limites.yaml (hoy sin fijar)", "de": "S-B"},
    {"regla_id": "F2-A10", "nombre": "Costo de IA demasiado alto", "requiere": "costos de IA por corrida y por oferta", "archivo": "empresa/costos.jsonl (aún no existe)", "de": "S-B"},
    {"regla_id": "F2-A11", "nombre": "Reembolsos y disputas", "requiere": "reembolsos y disputas de los últimos días", "archivo": "ofertas/<id>/10-postcompra/ y el libro de movimientos", "de": "S-B"},
    {"regla_id": "F2-A12", "nombre": "Camino del comprador con números incoherentes", "requiere": "embudo del día (clics, visitas, pagos iniciados, compras)", "archivo": "kpi_oferta_dia.json", "de": "S-B"},
    {"regla_id": "F2-A13", "nombre": "Calidad de la señal de compra baja", "requiere": "calidad de coincidencia de eventos (EMQ) del medidor de Meta", "archivo": "empresa/infra/estado.json (ítem M-05, cuando haya chequeo real)", "de": "S-B"},
    {"regla_id": "F2-A14", "nombre": "Demasiado gasto en nichos de riesgo amarillo", "requiere": "gasto por nivel de riesgo y cuota del límite", "archivo": "kpi_oferta_dia.json y empresa/limites.yaml (cuota hoy sin fijar)", "de": "S-B"},
    {"regla_id": "F2-A15", "nombre": "Radar de ofertas descompensado", "requiere": "banco de evidencia por nicho y su caducidad", "archivo": "empresa/barrido/ (estados del banco: pedido a S-A, d1-v2-interfaces)", "de": "S-A"},
]


@dataclass
class Alerta:
    """``fila`` = la línea de ``alertas.jsonl`` (esquema); ``extra`` = lo que solo ve la persona (título, responsable, enlace, comando)."""

    fila: dict[str, Any]
    extra: dict[str, Any] = field(default_factory=dict)


def accion(responsable: str, texto: str) -> str:
    """«<Quién>: <texto>» recortado a 300 caracteres (el esquema)."""
    t = f"{RESPONSABLE_TEXTO[responsable]}: {texto}"
    return t if len(t) <= MAX_ACCION else t[: MAX_ACCION - 1].rstrip() + "…"


def comando_firmar(oferta_id: str, etapa: str) -> str | None:
    """Comando de firma de un gate (solo se MUESTRA; el panel nunca firma). ``None`` si el id o la etapa no tienen la forma esperada."""
    if not RX_OFERTA_REAL.fullmatch(oferta_id or "") or not isinstance(etapa, str) or not (1 <= len(etapa) <= 4) or not etapa.isalnum() or not etapa.isupper():
        return None
    return (f".venv/bin/python -m engine.orq firmar --oferta {oferta_id} --etapa {etapa} --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> "
            "--clave-privada <RUTA_A_TU_CLAVE> --como dueno")


def _a(regla: str, objeto: str, ahora: str, severidad: str, valor: Any, umbral: Any, responsable: str, texto: str, titulo: str, enlace: str | None, *,
       oferta_id: str | None = None, comando: str | None = None, detalle: str | None = None, medida: str | None = None) -> Alerta:
    fila = {
        "schema_version": SCHEMA_VERSION, "id": f"{regla}:{objeto}", "ts": ahora, "severidad": severidad, "regla_id": regla, "origen": "F2",
        "oferta_id": oferta_id if oferta_id and RX_OFERTA_REAL.fullmatch(oferta_id) else None, "macro_nicho": None, "nivel": None,
        "valor": valor, "umbral": umbral, "accion_sugerida": accion(responsable, texto), "estado": "abierta",
    }
    extra = {"titulo": titulo, "responsable": responsable, "responsable_texto": RESPONSABLE_TEXTO[responsable], "area": CATALOGO[regla]["area"],
             "enlace": enlace, "comando": comando, "detalle": detalle, "medida": medida}
    return Alerta(fila, extra)


def _es_verde(it: Any) -> bool:
    return isinstance(it, dict) and it.get("estado") == "VERDE"


def calcular_alertas(h: dict[str, Any]) -> list[Alerta]:
    """Las alertas que están ABIERTAS ahora, según los hechos (``scripts.alertas.hechos.leer_hechos``). Determinista: mismos hechos, mismas alertas."""
    ahora = h["ahora"]
    t_ahora = parsear_z(ahora) or _dt.datetime.now(_dt.timezone.utc)
    sal: list[Alerta] = []
    lim, pre, can, plan = h["limites"], h["preflight"], h["canales"], h["planificador"]
    hay_ventas = (h["ofertas"].get("con_venta_en_curso") or 0) > 0

    # ── seguridad: PAUSA y freno ──
    if h["pausa"].get("activa"):
        sal.append(_a("F2-AUS-PAUSA", "empresa", ahora, "roja", 1, 0, "dueno",
                      "la PAUSA (freno de emergencia) está puesta: nada gasta y nada avanza. Revisa por qué se puso y, si ya no hace falta, levántala tú a mano; el panel nunca lo hace.",
                      "La PAUSA (freno de emergencia) está puesta", "#/sistema", comando="rm empresa/PAUSA",
                      detalle=limpiar_texto(h["pausa"].get("motivo"), 120) or None))
    if h["freno_captura"] and h["freno_captura"].get("activo"):
        sal.append(_a("F2-AUS-FRENO", "captura", ahora, "amarilla", 1, 0, "dueno",
                      "el freno de la captura de anuncios está puesto (Meta bloqueó una visita). No afecta al gasto: solo frena el radar de ofertas. Revísalo y, si corresponde, levántalo tú.",
                      "La captura de anuncios está frenada", "#/sistema", comando="rm empresa/captura/freno.json",
                      detalle=limpiar_texto(h["freno_captura"].get("motivo"), 120) or None))

    # ── seguridad: límites (J4: 300 USD por día y pausa a −3.000 USD) ──
    if not lim["legible"]:
        sal.append(_a("F2-AUS-LIM", "empresa", ahora, "roja", None, 0, "S-A",
                      "no se pudo leer el archivo de límites (empresa/limites.yaml): por seguridad nada puede gastar. Hay que restaurarlo.",
                      "No se pueden leer los límites de dinero", "#/parametros"))
    else:
        j4 = [c for c in ("gasto_diario_global", "perdida_neta_acumulada_max") if c in lim["bloquean"]]
        if lim["n_bloquean"] > 0:
            responsable = "dueno" if lim["propuesta"] else "S-B"
            texto = ("revisa la propuesta de límites, completa lo que falte (incluye 300 USD por día y la pausa a −3.000 USD) y fírmala." if lim["propuesta"] else
                     "falta preparar la propuesta de límites con 300 USD por día y pausa a −3.000 USD; después tú la revisas y la firmas. Mientras tanto nada puede gastar.")
            sal.append(_a("F2-AUS-LIM", "empresa", ahora, "roja" if j4 else "amarilla", lim["n_bloquean"], 0, responsable, texto,
                          f"Faltan {lim['n_bloquean']} límite{'s' if lim['n_bloquean'] != 1 else ''} de dinero por fijar", "#/parametros",
                          medida=f"{lim['n_bloquean']} límite{'s' if lim['n_bloquean'] != 1 else ''} sin fijar"))
        if not lim["sello"]:
            sal.append(_a("F2-AUS-SELLO", "empresa", ahora, "roja" if lim["n_bloquean"] == 0 else "amarilla", 0, 1, "dueno",
                          "los límites no tienen tu firma: sin ella nada puede gastar ni activarse. Cuando estén completos, revísalos y fírmalos tú (el panel no firma).",
                          "Los límites de dinero no están firmados", "#/parametros",
                          comando=COMANDO_FIRMAR_LIMITES, medida="sin tu firma"))

    # ── seguridad: chequeo de cuentas y servicios (F2-A16) ──
    vig = h["umbrales"]["preflight_vigencia_h"]
    if not pre.get("existe"):
        sal.append(_a("F2-A16", "chequeo", ahora, "roja", None, vig, "dueno",
                      "todavía no se hizo el chequeo de cuentas y servicios, así que nada puede gastar ni activarse. Primero deja listas tus cuentas y claves; después el equipo técnico (S-B) corre el chequeo.",
                      "Falta el chequeo de cuentas y servicios", "#/sistema", comando=".venv/bin/python -m infra.preflight ejecutar --modo completo"))
    else:
        sem = str(pre.get("semaforo") or "").upper()
        edad = pre.get("edad_h")
        if sem == "ROJO":
            n = len(pre.get("criticos_rojos") or [])
            sal.append(_a("F2-A16", "chequeo", ahora, "roja", n, 0, "S-B",
                          f"el chequeo de cuentas y servicios salió en rojo ({n} punto{'s' if n != 1 else ''} crítico{'s' if n != 1 else ''} fallan). Mientras siga en rojo nadie gasta ni activa. Mira cuáles fallan en Salud del sistema.",
                          "Las cuentas y servicios están en rojo", "#/sistema", comando=".venv/bin/python -m infra.preflight ejecutar --modo completo",
                          medida=f"{n} punto{'s' if n != 1 else ''} crítico{'s' if n != 1 else ''} en rojo"))
        elif sem == "AMARILLO":
            sal.append(_a("F2-A16", "chequeo", ahora, "amarilla", None, vig, "S-B",
                          "el chequeo de cuentas y servicios salió en amarillo: algo está por vencer o no se pudo comprobar. Mira cuál en Salud del sistema.",
                          "Las cuentas y servicios están en amarillo", "#/sistema", comando=".venv/bin/python -m infra.preflight ejecutar --modo completo"))
        elif pre.get("modo") != "vivo":
            sal.append(_a("F2-A16", "chequeo", ahora, "amarilla", None, vig, "dueno",
                          "el último chequeo es de prueba o simulacro: no sirve para gastar ni activar de verdad. Hay que repetirlo con tus cuentas reales.",
                          "El chequeo de cuentas y servicios no es real", "#/sistema", comando=".venv/bin/python -m infra.preflight ejecutar --modo completo"))
        elif vig is None or edad is None or edad > vig:
            sal.append(_a("F2-A16", "chequeo", ahora, "amarilla", edad, vig, "S-B",
                          "el chequeo de cuentas y servicios está vencido o no se sabe de cuándo es: hay que volver a medirlo antes de gastar o activar.",
                          "El chequeo de cuentas y servicios está vencido", "#/sistema", comando=".venv/bin/python -m infra.preflight ejecutar --modo completo",
                          medida=(f"medido hace {edad} h (máximo {vig} h)" if edad is not None and vig is not None else "no se sabe de cuándo es")))

    # ── avisos: canal al celular con dos canales ──
    if can["n"] < CANALES_MIN:
        sal.append(_a("F2-AUS-CANAL", "empresa", ahora, "roja" if can["n"] == 0 else "amarilla", can["n"], CANALES_MIN, "dueno",
                      ("todavía no elegiste cómo te avisamos al celular: nadie te avisa fuera del panel. Elige un canal (por ejemplo Telegram, solo de salida) y un segundo canal (correo)."
                       if can["n"] == 0 else "falta el segundo canal de avisos: un aviso importante nunca debe depender de un solo camino. Elige el segundo (por ejemplo correo)."),
                      "Los avisos al celular no tienen dos canales", "#/avisos", medida=f"{can['n']} de {CANALES_MIN} canales elegidos"))
    elif can["n_probados"] < CANALES_MIN:
        sal.append(_a("F2-AUS-CANAL", "empresa", ahora, "amarilla", can["n_probados"], CANALES_MIN, "S-B",
                      "ya hay dos canales de avisos, pero falta probar que el aviso llega por los dos. Hasta probarlo no se puede confiar en que te avisen.",
                      "Falta probar que los avisos llegan por los dos canales", "#/avisos", medida=f"{can['n_probados']} de {CANALES_MIN} canales probados"))

    # ── trabajo: planificador y señales de vida ──
    if plan["trabajos"] and plan["vencidos"] > 0:
        edades = [t["edad_min"] for t in plan["trabajos"] if t.get("vencido") and isinstance(t.get("edad_min"), int)]
        peor = max(edades) if edades else None
        sal.append(_a("F2-A17", "latidos", ahora, "roja", peor, h["umbrales"]["latido_max_min"], "S-B",
                      f"{plan['vencidos']} trabajo{'s' if plan['vencidos'] != 1 else ''} no dieron señal de vida a tiempo. Si el planificador se cayó, nada corre solo. Revisa cuáles en Robots.",
                      "Hay trabajos sin señal de vida", "#/robots",
                      medida=f"{plan['vencidos']} de {plan['n']} sin señal" + (f"; el peor, hace {peor} min" if peor is not None else "")))
    elif not plan["existe"]:
        # Todavía no hay planificador REAL (el de S-B). Los robots en sombra (solo lectura) no lo reemplazan: solo cambia lo que se dice.
        sombra = plan.get("sombra")
        situacion = sombra["situacion"] if sombra else None
        if situacion == "corriendo":
            texto = ("hay robots en sombra corriendo (solo lectura), pero no son el sistema real: no vigilan ni frenan nada. Primero eliges dónde corre el sistema; "
                     "después el equipo técnico (S-B) construye el planificador.")
            titulo = "Robots en sombra corriendo (solo lectura): todavía no hay planificador real"
        elif situacion in ("sin_programar", "vencido"):
            texto = ("no hay un planificador real y los robots en sombra (solo lectura) no corren solos como debieran. Primero eliges dónde corre el sistema; "
                     "después el equipo técnico (S-B) lo construye.")
            titulo = "No hay nada programado de verdad: los robots en sombra no son el sistema real"
        else:
            texto = ("hoy nada se despierta solo: no hay planificador ni nada programado. Primero eliges dónde corre el sistema (lo recomendado es un servidor siempre encendido); "
                     "después el equipo técnico (S-B) lo construye.")
            titulo = "Nada corre solo: todavía no hay planificador (el programa que despierta cada tarea a su hora)"
        sal.append(_a("F2-AUS-PLAN", "planificador", ahora, "amarilla", None, None, "dueno", texto, titulo, "#/robots"))
        if situacion == "vencido":
            n = sombra["n_vencidos"]
            sal.append(_a("F2-A17", "sombra", ahora, "amarilla", n, None, "dueno",
                          f"{n} robot{'s' if n != 1 else ''} en sombra programado{'s' if n != 1 else ''} no dio{'eron' if n != 1 else ''} señal de vida a su hora. Revisa si tu Mac estaba dormida o si se quitó la programación; mira cuáles en Robots.",
                          "Hay robots en sombra con el latido vencido", "#/robots", comando=".venv/bin/python -m scripts.robots.sombra estado",
                          medida=f"{n} robot{'s' if n != 1 else ''} en sombra sin señal a tiempo"))
    elif not plan["trabajos"]:
        sal.append(_a("F2-AUS-PLAN", "planificador", ahora, "amarilla", 0, None, "S-B",
                      "el planificador existe pero ningún trabajo da señal de vida todavía. Sin señales no se puede saber si algo dejó de correr.",
                      "Ningún trabajo da señal de vida", "#/robots"))

    # ── venta: cuenta de Meta, correo y saldo ──
    if not lim["cuentas_permitidas"]:
        sal.append(_a("F2-AUS-META", "empresa", ahora, "amarilla", 0, 1, "dueno",
                      "no hay ninguna cuenta de Meta permitida en los límites: el sistema no puede lanzar nada. Deja una cuenta limpia (método de pago, moneda y zona) y anótala en los límites.",
                      "Falta una cuenta de Meta lista para lanzar", "#/pagos"))
    elif pre.get("existe") and pre.get("items", {}).get("M-02", {}).get("estado") not in (None, "VERDE"):
        sal.append(_a("F2-AUS-META", "empresa", ahora, "amarilla", None, None, "dueno",
                      "la cuenta de Meta no pasó el chequeo (estado de la cuenta, moneda o zona). Mira el detalle en Pagos.",
                      "La cuenta de Meta no pasa el chequeo", "#/pagos"))
    e01 = pre.get("items", {}).get("E-01") if pre.get("existe") else None
    if not _es_verde(e01):
        sal.append(_a("F2-AUS-CORREO", "empresa", ahora, "roja" if hay_ventas else "amarilla", None, None, "dueno",
                      ("el proveedor de correo no pasó el chequeo: sin correo no se entrega el producto." if e01 else
                       "todavía no hay un proveedor de correo elegido y comprobado: sin correo no se entrega el producto a quien compra. Elígelo y dónde llega el soporte."),
                      "Falta dejar listo el correo para entregar el producto", "#/poscompra"))
    m03 = pre.get("items", {}).get("M-03") if pre.get("existe") else None
    if m03 and m03.get("estado") in ("AMARILLO", "ROJO"):
        sal.append(_a("F2-AUS-SALDO", "meta", ahora, "roja" if (m03["estado"] == "ROJO" and hay_ventas) else "amarilla", None, None, "dueno",
                      "el tope de gasto o la forma de pago de la cuenta de anuncios no está en orden (queda poco, no hay tope o usa fondos prepagos). Revísalo en Pagos antes de ausentarte.",
                      "El saldo o el tope de la cuenta de anuncios no está en orden", "#/pagos"))

    # ── trabajo: firmas que esperan y pendientes vencidos ──
    for g in h["ofertas"]["gates"][:MAX_GATES]:
        nombre = NOMBRES_ETAPA.get(g["etapa"], g["etapa"]) if isinstance(g.get("etapa"), str) else "una etapa"
        horas = horas_entre(parsear_z(g.get("desde")), t_ahora)
        oid = g["oferta_id"]
        sal.append(_a("F2-AUS-GATE", f"{oid}:{g['etapa']}", ahora, "amarilla", horas, None, "dueno",
                      f"«{nombre}» de la oferta {oid} espera tu firma; mientras no la firmes esa oferta no avanza. El comando para firmar está en el Resumen.",
                      f"Espera tu firma: {nombre}", f"#/oferta/{oid}", oferta_id=oid, comando=comando_firmar(oid, g["etapa"]),
                      medida=(f"la oferta no cambia hace {horas} h" if horas is not None else None)))
    n_venc = 0
    for p in h["pulido"]["abiertos"]:
        if not p.get("vencido") or n_venc >= MAX_VENCIDOS:
            continue
        n_venc += 1
        dias = None
        v = p.get("vence")
        if isinstance(v, str):
            t = parsear_z(v if "T" in v else f"{v}T23:59:59Z")
            dias = max(0, (t_ahora - t).days) if t else None
        sal.append(_a("F2-AUS-VENCE", p["id"], ahora, "roja" if p.get("prioridad") == "P0" else "amarilla", dias, 0, "dueno",
                      f"el pendiente {p['id']} ya pasó su fecha de entrega. Resuélvelo o cambia su fecha en Mejoras pendientes.",
                      "Un pendiente tuyo está vencido", "#/pulido", detalle=p.get("titulo") or None,
                      medida=(f"venció hace {dias} día{'s' if dias != 1 else ''}" if dias is not None else "vencido")))
    return sal
