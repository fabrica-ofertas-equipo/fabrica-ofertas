"""Semáforo «¿me puedo ausentar?» (brechas/04 B4-26): un veredicto verde/amarillo/rojo y la lista «qué falta, en orden, y a quién le toca».

Se calcula SOLO de archivos locales (los ``hechos`` de ``scripts.alertas.hechos``). Regla del veredicto:

* **Rojo** (todavía no): falta algo de la *red de seguridad* o del *trabajo solo* (pausa y frenos, límites firmados, chequeo de cuentas, avisos por dos
  canales, planificador con señales de vida). Sin eso, si te ausentas nadie frena ni te avisa, o el sistema no corre solo.
* **Amarillo** (con cuidado): lo anterior está, pero faltan cosas *para vender* (cuenta de Meta, correo, saldo), hay firmas esperándote o un freno de
  captura puesto. Si ya hay ofertas vendiendo, lo que falte para vender pasa a rojo.
* **Verde**: todo en orden.

Un dato que no existe es «sin dato» y cuenta como falta (fail-closed): nunca se da por bueno lo que no se pudo comprobar. El orden de la lista es el de
importancia: primero lo que protege tu dinero, después los avisos, después el trabajo y por último la venta.
"""
from __future__ import annotations

from typing import Any

from scripts.alertas.reglas import CANALES_MIN, COMANDO_FIRMAR_LIMITES, RESPONSABLE_CORTO, RESPONSABLE_TEXTO, comando_firmar

__all__ = ["calcular_semaforo", "NIVELES", "PANTALLAS", "COMANDO_CHEQUEO"]

COMANDO_CHEQUEO = ".venv/bin/python -m infra.preflight ejecutar --modo completo"
NIVELES = ("rojo", "amarillo", "verde")
_ORDEN_NIVEL = {"rojo": 0, "amarillo": 1, "verde": 2}
PANTALLAS = {
    "#/sistema": "Salud del sistema", "#/parametros": "Límites y reglas", "#/avisos": "Avisos", "#/robots": "Robots", "#/pagos": "Pagos",
    "#/poscompra": "Después de la venta", "#/resumen": "Resumen", "#/pulido": "Mejoras pendientes", "#/ofertas": "Ofertas", "#/tareas": "Mis tareas",
}
J4_GASTO_DIARIO_MENOR = 30000          # 300 USD por día (decisión J4 del dueño), en centavos
J4_PERDIDA_ACUMULADA_MENOR = 300000    # pausa a −3.000 USD perdidos, en centavos


def _c(orden: int, id_: str, titulo: str, grupo: str, nivel: str, estado: str, que_hacer: str, responsable: str, enlace: str, *,
       comando: str | None = None, nota: str | None = None) -> dict[str, Any]:
    return {
        "orden": orden, "id": id_, "titulo": titulo, "grupo": grupo, "nivel": nivel, "estado": estado, "que_hacer": que_hacer,
        "responsable": responsable, "responsable_texto": RESPONSABLE_TEXTO[responsable], "quien": RESPONSABLE_CORTO[responsable],
        "enlace": enlace, "enlace_texto": PANTALLAS.get(enlace, "Abrir"), "comando": comando, "nota": nota,
    }


def _pausa(h: dict[str, Any]) -> dict[str, Any]:
    p, f = h["pausa"], h["freno_captura"]
    if p.get("ilegible"):
        return _c(1, "pausa", "PAUSA y frenos", "seguridad", "rojo", "No se pudo comprobar si la PAUSA está puesta.", "Tiene que revisar ese archivo; por seguridad se toma como puesta.", "S-B", "#/sistema")
    if p.get("activa"):
        extra = " También está puesto el freno de la captura de anuncios." if f and f.get("activo") else ""
        return _c(1, "pausa", "PAUSA y frenos", "seguridad", "rojo", "La PAUSA (freno de emergencia) está puesta: nada gasta y nada avanza." + extra,
                  "Revisa por qué se puso y, si ya no hace falta, levántala tú a mano. El panel nunca la levanta.", "dueno", "#/sistema", comando="rm empresa/PAUSA")
    if f and f.get("activo"):
        return _c(1, "pausa", "PAUSA y frenos", "seguridad", "amarillo", "No hay PAUSA, pero el freno de la captura de anuncios está puesto (Meta bloqueó una visita).",
                  "Revísalo y, si corresponde, levántalo tú. No afecta al gasto: solo frena el radar de ofertas.", "dueno", "#/sistema", comando="rm empresa/captura/freno.json")
    return _c(1, "pausa", "PAUSA y frenos", "seguridad", "verde", "Sin PAUSA y sin freno puesto.", "Nada que hacer.", "dueno", "#/sistema")


def _limites(h: dict[str, Any]) -> dict[str, Any]:
    t = "Límites de dinero firmados (300 USD por día y pausa a −3.000 USD)"
    lim = h["limites"]
    if not lim["legible"]:
        return _c(2, "limites", t, "seguridad", "rojo", "No se pudo leer el archivo de límites: por seguridad nada puede gastar.", "Tiene que restaurar empresa/limites.yaml.", "S-A", "#/parametros")
    n = lim["n_bloquean"]
    if n > 0:
        if lim["propuesta"]:
            return _c(2, "limites", t, "seguridad", "rojo", f"Faltan {n} límite{'s' if n != 1 else ''} por fijar y los límites no están firmados.",
                      "Revisa la propuesta, completa lo que falte (incluye los 300 USD por día y la pausa a −3.000 USD) y fírmala tú.", "dueno", "#/parametros")
        return _c(2, "limites", t, "seguridad", "rojo", f"Faltan {n} límite{'s' if n != 1 else ''} por fijar y los límites no están firmados. Mientras tanto nada puede gastar.",
                  "Tiene que preparar la propuesta con 300 USD por día y pausa a −3.000 USD; después tú la revisas y la firmas.", "S-B", "#/parametros")
    if not lim["sello"]:
        return _c(2, "limites", t, "seguridad", "rojo", "Los límites están completos pero sin tu firma: sin ella nada puede gastar ni activarse.",
                  "Revísalos y fírmalos tú. El panel no firma por ti.", "dueno", "#/parametros", comando=COMANDO_FIRMAR_LIMITES)
    g, p = lim.get("gasto_diario_global"), lim.get("perdida_neta_acumulada_max")
    if lim.get("moneda") == "USD" and (g != J4_GASTO_DIARIO_MENOR or p != J4_PERDIDA_ACUMULADA_MENOR):
        return _c(2, "limites", t, "seguridad", "amarillo", "Los límites están firmados, pero no coinciden con lo que decidiste (300 USD por día y pausa a −3.000 USD).",
                  "Confirma que los valores firmados son los que quieres; si no, prepara una propuesta nueva y fírmala.", "dueno", "#/parametros")
    return _c(2, "limites", t, "seguridad", "verde", "Límites completos y firmados.", "Nada que hacer.", "dueno", "#/parametros")


def _chequeo(h: dict[str, Any]) -> dict[str, Any]:
    t = "Chequeo de cuentas y servicios (antes de lanzar)"
    pre = h["preflight"]
    if not pre.get("existe"):
        return _c(3, "chequeo", t, "seguridad", "rojo", "Todavía no se hizo el chequeo: nada puede gastar ni activarse.",
                  "Primero deja listas tus cuentas y claves (Meta, Stripe, correo); después el equipo técnico (S-B) corre el chequeo.", "dueno", "#/sistema", comando=COMANDO_CHEQUEO)
    sem = str(pre.get("semaforo") or "").upper()
    if sem == "ROJO":
        n = len(pre.get("criticos_rojos") or [])
        return _c(3, "chequeo", t, "seguridad", "rojo", f"El chequeo salió en rojo ({n} punto{'s' if n != 1 else ''} crítico{'s' if n != 1 else ''} fallan).",
                  "Tiene que arreglar lo que falla (el detalle está en Salud del sistema); mientras siga en rojo nadie gasta ni activa.", "S-B", "#/sistema", comando=COMANDO_CHEQUEO)
    if sem == "AMARILLO":
        return _c(3, "chequeo", t, "seguridad", "amarillo", "El chequeo salió en amarillo: algo está por vencer o no se pudo comprobar.",
                  "Tiene que revisar cuál es (el detalle está en Salud del sistema).", "S-B", "#/sistema", comando=COMANDO_CHEQUEO)
    if pre.get("modo") != "vivo":
        return _c(3, "chequeo", t, "seguridad", "amarillo", "El último chequeo es de prueba o simulacro: no sirve para gastar de verdad.",
                  "Repítelo con tus cuentas reales.", "dueno", "#/sistema", comando=COMANDO_CHEQUEO)
    edad, vig = pre.get("edad_h"), h["umbrales"]["preflight_vigencia_h"]
    if vig is None or edad is None or edad > vig:
        return _c(3, "chequeo", t, "seguridad", "amarillo", "El chequeo está vencido o no se sabe de cuándo es.", "Tiene que volver a medirlo.", "S-B", "#/sistema", comando=COMANDO_CHEQUEO)
    return _c(3, "chequeo", t, "seguridad", "verde", f"Chequeo en verde, real y reciente (hace {edad} h).", "Nada que hacer.", "S-B", "#/sistema")


def _canal(h: dict[str, Any]) -> dict[str, Any]:
    t = "Avisos al celular por dos canales"
    c = h["canales"]
    if c["n"] == 0:
        return _c(4, "canal", t, "avisos", "rojo", "Todavía no elegiste cómo te avisamos: nadie te avisa fuera del panel.",
                  "Elige un canal para el celular (por ejemplo Telegram, solo de salida) y un segundo canal (correo).", "dueno", "#/avisos")
    if c["n"] < CANALES_MIN:
        return _c(4, "canal", t, "avisos", "amarillo", "Hay un solo canal de avisos.", "Elige el segundo canal: un aviso importante nunca debe depender de un solo camino.", "dueno", "#/avisos")
    if c["n_probados"] < CANALES_MIN:
        return _c(4, "canal", t, "avisos", "amarillo", "Hay dos canales, pero falta probar que el aviso llega por los dos.", "Tiene que probar que el aviso llega por los dos canales.", "S-B", "#/avisos")
    return _c(4, "canal", t, "avisos", "verde", "Dos canales de avisos, probados.", "Nada que hacer.", "S-B", "#/avisos")


COMANDO_SOMBRA_ESTADO = ".venv/bin/python -m scripts.robots.sombra estado"
COMANDO_SOMBRA_PROGRAMAR = ".venv/bin/python -m scripts.robots.sombra programar"


def _n(n: int, uno: str, varios: str) -> str:
    return f"{n} {uno if n == 1 else varios}"


def _planificador_sin_real(p: dict[str, Any]) -> dict[str, Any]:
    """Todavía no hay planificador REAL (el de S-B). Los robots en sombra son de solo lectura y NO lo reemplazan: la fila sigue en rojo en los tres casos,
    y lo que cambia es lo que se dice (nada programado · robots en sombra corriendo · latido vencido)."""
    t = "El sistema se despierta solo y da señales de vida"
    s = p.get("sombra")
    base = "Primero tú eliges dónde corre el sistema (lo recomendado es un servidor siempre encendido); después el equipo técnico (S-B) lo construye."
    if s is None:
        return _c(5, "planificador", t, "trabajo", "rojo", "Todavía no hay nada programado: nada se despierta solo y no hay señales de vida. Los robots en sombra (que solo miran y proponen) todavía no corrieron.",
                  base, "dueno", "#/robots", comando=COMANDO_SOMBRA_ESTADO)
    if s["situacion"] == "vencido":
        nombres = s.get("nombres_vencidos") or s["ids_vencidos"]
        ids = ", ".join(nombres[:4]) + ("…" if len(nombres) > 4 else "")
        return _c(5, "planificador", t, "trabajo", "rojo",
                  f"Latido vencido: {_n(s['n_vencidos'], 'robot en sombra programado dejó', 'robots en sombra programados dejaron')} de dar señal de vida a su hora ({ids}). Siguen siendo de solo lectura; no son el sistema real.",
                  "Revisa si tu Mac estaba dormida o si se quitó la programación (mira cuáles en Robots). Aun así, el sistema real todavía no existe: " + base[0].lower() + base[1:],
                  "dueno", "#/robots", comando=COMANDO_SOMBRA_ESTADO)
    if s["situacion"] == "corriendo":
        return _c(5, "planificador", t, "trabajo", "rojo",
                  f"Robots en sombra corriendo (solo lectura): {s['n_esperados']} programados y al día. Ensayan el trabajo, pero no son el sistema real: no vigilan ni frenan nada, y si tu Mac duerme se pierden vueltas.",
                  "Sigue igual: el verde llega cuando exista el planificador real. " + base, "dueno", "#/robots", comando=COMANDO_SOMBRA_ESTADO)
    corrida = ("Los robots en sombra solo corrieron a mano" if s["n_corrieron_hoy"] or s["n_solo_manual"] else "Los robots en sombra todavía no corrieron")
    return _c(5, "planificador", t, "trabajo", "rojo", f"No hay nada programado: nada se despierta solo y no hay señales de vida. {corrida} (a mano no crean ninguna expectativa).",
              base + " Si quieres ensayarlos en tu Mac, el comando solo muestra cómo se programarían: instalar es decisión tuya.", "dueno", "#/robots", comando=COMANDO_SOMBRA_PROGRAMAR)


def _planificador(h: dict[str, Any]) -> dict[str, Any]:
    t = "El sistema se despierta solo y da señales de vida"
    p = h["planificador"]
    if p["trabajos"] and p["vencidos"] > 0:
        return _c(5, "planificador", t, "trabajo", "rojo", f"{p['vencidos']} de {p['n']} trabajo{'s' if p['n'] != 1 else ''} no dieron señal de vida a tiempo.",
                  "Tiene que revisar cuáles se pararon y por qué (el detalle está en Robots).", "S-B", "#/robots")
    if not p["existe"]:
        return _planificador_sin_real(p)
    if not p["trabajos"]:
        return _c(5, "planificador", t, "trabajo", "amarillo", "El planificador (el programa que despierta las tareas) existe, pero ningún trabajo da señal de vida todavía.",
                  "Tiene que hacer que cada trabajo avise que corrió.", "S-B", "#/robots")
    return _c(5, "planificador", t, "trabajo", "verde", f"{p['n']} trabajo{'s' if p['n'] != 1 else ''} con señal de vida reciente.", "Nada que hacer.", "S-B", "#/robots")


def _firmas(h: dict[str, Any]) -> dict[str, Any]:
    t = "Firmas que esperan por ti"
    g = h["ofertas"]["gates"]
    nota = None
    sin = h["ofertas"].get("sin_estado") or []
    if sin:
        nota = (f"{len(sin)} oferta{'s' if len(sin) != 1 else ''} hecha{'s' if len(sin) != 1 else ''} a mano no tiene{'n' if len(sin) != 1 else ''} registro de avance en el sistema, "
                "así que sus firmas no se ven acá.")
    if g:
        primero = g[0]
        return _c(6, "firmas", t, "trabajo", "amarillo", f"{len(g)} firma{'s' if len(g) != 1 else ''} esperan por ti; mientras estés fuera esas ofertas no avanzan.",
                  "Revísalas y fírmalas si estás de acuerdo antes de ausentarte.", "dueno", "#/resumen", comando=comando_firmar(primero["oferta_id"], primero["etapa"]), nota=nota)
    return _c(6, "firmas", t, "trabajo", "verde", "Ninguna firma espera por ti.", "Nada que hacer.", "dueno", "#/resumen", nota=nota)


def _meta(h: dict[str, Any], hay_ventas: bool) -> dict[str, Any]:
    t = "Cuenta de Meta lista para lanzar"
    grave = "rojo" if hay_ventas else "amarillo"
    lim, pre = h["limites"], h["preflight"]
    if not lim["cuentas_permitidas"]:
        return _c(7, "meta", t, "venta", grave, "No hay ninguna cuenta de Meta permitida: el sistema no puede lanzar nada.",
                  "Deja una cuenta limpia (método de pago, moneda y zona) y anótala en los límites.", "dueno", "#/pagos")
    m02 = pre.get("items", {}).get("M-02") if pre.get("existe") else None
    if not m02:
        return _c(7, "meta", t, "venta", "amarillo", "Hay una cuenta permitida, pero falta comprobar que funciona.", "Tiene que correr el chequeo antes de lanzar.", "S-B", "#/pagos", comando=COMANDO_CHEQUEO)
    if m02.get("estado") != "VERDE":
        return _c(7, "meta", t, "venta", grave, "La cuenta de Meta no pasó el chequeo.", "Mira el detalle en Pagos.", "dueno", "#/pagos")
    return _c(7, "meta", t, "venta", "verde", "Cuenta de Meta permitida y comprobada.", "Nada que hacer.", "dueno", "#/pagos")


def _correo(h: dict[str, Any], hay_ventas: bool) -> dict[str, Any]:
    t = "Correo para entregar el producto"
    grave = "rojo" if hay_ventas else "amarillo"
    e01 = h["preflight"].get("items", {}).get("E-01") if h["preflight"].get("existe") else None
    if e01 and e01.get("estado") == "VERDE":
        return _c(8, "correo", t, "venta", "verde", "El proveedor de correo está verificado.", "Nada que hacer.", "dueno", "#/poscompra")
    if e01:
        return _c(8, "correo", t, "venta", grave, "El proveedor de correo no pasó el chequeo.", "Mira el detalle en Después de la venta.", "dueno", "#/poscompra")
    return _c(8, "correo", t, "venta", grave, "Sin dato: todavía no hay proveedor de correo elegido y comprobado. Sin correo no se entrega el producto.",
              "Elige el proveedor y dónde llega el soporte.", "dueno", "#/poscompra")


def _saldo(h: dict[str, Any], hay_ventas: bool) -> dict[str, Any]:
    t = "Saldo para gastar en anuncios"
    grave = "rojo" if hay_ventas else "amarillo"
    m03 = h["preflight"].get("items", {}).get("M-03") if h["preflight"].get("existe") else None
    if m03 and m03.get("estado") == "VERDE":
        return _c(9, "saldo", t, "venta", "verde", "Hay tope de gasto en la cuenta y no es prepago.", "Nada que hacer.", "dueno", "#/pagos")
    if m03:
        return _c(9, "saldo", t, "venta", grave if m03.get("estado") == "ROJO" else "amarillo", "El tope de gasto o la forma de pago de la cuenta no está en orden.",
                  "Revísalo en Pagos antes de ausentarte.", "dueno", "#/pagos")
    return _c(9, "saldo", t, "venta", "amarillo", "Sin dato: todavía no hay forma de ver el saldo ni el tope de la cuenta de anuncios.",
              "Hoy no hay forma de verlo: se verá con el chequeo de cuentas (tope de gasto) y con el vigía de pagos.", "S-B", "#/pagos")


def _vigilancia(h: dict[str, Any], ajenas: list[dict[str, Any]], hay_ventas: bool) -> dict[str, Any]:
    """Lo que vigila el gasto y las ventas (reglas F1 y F2-A04…A15 que escribe S-B en ``alertas.jsonl``): hoy no se calculan, así que solo importa si ya hay ofertas vendiendo."""
    t = "Vigilancia del gasto y de las ventas"
    graves = [a for a in ajenas if a["estado"] != "cerrada" and a["severidad"] in ("roja", "naranja")]
    if graves:
        return _c(10, "vigilancia", t, "seguridad", "rojo", f"Hay {len(graves)} alerta{'s' if len(graves) != 1 else ''} grave{'s' if len(graves) != 1 else ''} abierta{'s' if len(graves) != 1 else ''} de gasto, ventas o finanzas.",
                  "Míralas en Avisos y decide qué hacer antes de ausentarte.", "dueno", "#/avisos")
    if hay_ventas and not ajenas:
        return _c(10, "vigilancia", t, "seguridad", "amarillo", "Ya hay ofertas vendiendo, pero las reglas que vigilan el gasto y las ventas todavía no se calculan: nadie las mira de cerca.",
                  "Tiene que calcular esas reglas (necesitan los datos de ventas y gasto) y guardarlas junto con las demás alertas.", "S-B", "#/avisos")
    if not hay_ventas:
        return _c(10, "vigilancia", t, "seguridad", "verde", "No hay ofertas vendiendo todavía: no hay gasto ni ventas que vigilar.", "Cuando haya, las reglas de gasto y ventas tienen que estar calculándose.", "S-B", "#/avisos")
    return _c(10, "vigilancia", t, "seguridad", "verde", "Las reglas de gasto y ventas están corriendo y no hay alertas graves abiertas.", "Nada que hacer.", "S-B", "#/avisos")


def calcular_semaforo(h: dict[str, Any], ajenas: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """``{nivel, titulo, resumen, conteos, pasos (lo que falta, en orden), comprobaciones (todas), para_ti, como_se_calcula, calculado_en}``.

    ``ajenas``: las líneas de otras reglas de ``alertas.jsonl`` ya saneadas (``scripts.alertas.producir.ajenas_de``); sin ellas se asume que no hay ninguna.
    """
    hay_ventas = (h["ofertas"].get("con_venta_en_curso") or 0) > 0
    comprobaciones = [_pausa(h), _limites(h), _chequeo(h), _canal(h), _planificador(h), _firmas(h), _meta(h, hay_ventas), _correo(h, hay_ventas), _saldo(h, hay_ventas),
                      _vigilancia(h, ajenas or [], hay_ventas)]
    conteos = {n: sum(1 for c in comprobaciones if c["nivel"] == n) for n in NIVELES}
    nivel = "rojo" if conteos["rojo"] else "amarillo" if conteos["amarillo"] else "verde"
    pasos = sorted((c for c in comprobaciones if c["nivel"] != "verde"), key=lambda c: (_ORDEN_NIVEL[c["nivel"]], c["orden"]))
    for i, p in enumerate(pasos, 1):
        p["paso"] = i
    faltan = len(pasos)
    tuyas = sum(1 for p in pasos if p["responsable"] == "dueno")
    if nivel == "rojo":
        titulo = "Todavía no te puedes ausentar"
        resumen = (f"Faltan {faltan} cosa{'s' if faltan != 1 else ''} ({conteos['rojo']} importante{'s' if conteos['rojo'] != 1 else ''}; "
                   f"{tuyas} te toca{'n' if tuyas != 1 else ''} a ti). Hasta que las {conteos['rojo']} importantes estén listas, "
                   "si te ausentas nadie te avisa de un problema o el sistema no puede trabajar solo.")
    elif nivel == "amarillo":
        titulo = "Te puedes ausentar, con cuidado"
        resumen = (f"Lo que protege tu dinero y te avisa está en orden, pero faltan {faltan} cosa{'s' if faltan != 1 else ''} "
                   f"({tuyas} te toca{'n' if tuyas != 1 else ''} a ti). Mientras estés fuera algunas cosas quedarán esperando.")
    else:
        titulo = "Sí, te puedes ausentar"
        resumen = "La red de seguridad, los avisos y el trabajo automático están en orden. Si algo falla, el sistema se frena y te avisa."
    return {
        "nivel": nivel, "titulo": titulo, "resumen": resumen, "conteos": conteos, "faltan": faltan, "para_ti": tuyas,
        "pasos": pasos, "comprobaciones": comprobaciones, "calculado_en": h["ahora"],
        "como_se_calcula": ("Rojo si falta algo de la red de seguridad o del trabajo solo (pausa y frenos, límites firmados, chequeo de cuentas, avisos por dos canales, "
                            "planificador con señales de vida) o hay una alerta grave de gasto o ventas abierta. Amarillo si falta algo para vender, hay firmas esperando o un freno de captura puesto. "
                            "Un dato que no existe cuenta como falta: nunca se da por bueno lo que no se pudo comprobar."),
    }
