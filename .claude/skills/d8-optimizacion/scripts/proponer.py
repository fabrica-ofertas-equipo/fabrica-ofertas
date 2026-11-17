#!/usr/bin/env python3
"""proponer.py: implementación de REFERENCIA, en sombra, de las dos reglas de D8 que el motor todavía no tiene.

v0.1 sin pulir (skill d8-optimizacion 0.1.0). «La IA propone, el código dispone»: las cifras y los veredictos de
estas reglas los calcula este script (enteros y ``Fraction``, sin ``float``), no el modelo. Lo que sale es una
PROPUESTA: ni pausa, ni activa, ni gasta, ni toca Meta, Stripe, ``engine/`` ni ``empresa/``. La implementación oficial
será de S-B (``engine/d8.py``, brechas B2-01 y B2-12; ver ``PEDIDOS.md``); cuando exista, este script pasa a ser
solo un contraste.

Subcomandos:
  umbrales     lee ``parametros.yaml`` y ``limites.yaml`` (solo lectura) y arma el archivo de umbrales; lo que falta va
               en ``umbrales_faltantes`` y valdrá ``null`` (fail-closed: la regla que lo necesita devuelve NO_DECIDIR).
  lanzamiento  regla J3 del día 1 (sin venta con el presupuesto del día gastado -> baja).
  fatiga       alarma de cansancio: últimos 3 días contra los 7 anteriores, por anuncio.

La entrada es la que arma ``preparar_expediente.py`` (``tipo: entrada_d8``). Salida: 0 propuesta calculada (incluida
NO_DECIDIR) · 2 uso · 3 entrada o umbrales inválidos.
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from typing import Any

VERSION = "0.1.0"

CLAVES_LANZAMIENTO = (
    "lanzamiento.baja_dias", "lanzamiento.baja_requiere_presupuesto_gastado", "lanzamiento.gasto_cumplido_min_pct",
    "lanzamiento.espera_post_dia_h", "lanzamiento.dias_max_sin_entrega",
    "testeo.tasa_conexion_min", "testeo.clics_min_diag", "optimizacion.lectura_horas",
)
CLAVES_FATIGA = (
    "testeo.fatiga_ventana_reciente_dias", "testeo.fatiga_ventana_previa_dias", "testeo.fatiga_caida_ctr_pct",
    "testeo.fatiga_factor_cpa", "testeo.fatiga_senales_min", "testeo.fatiga_lecturas_seguidas", "testeo.fatiga_compras_min",
    "testeo.impr_min_diag", "testeo.k_corte",
)
CLAVES_OPCIONALES = ("testeo.freq_alerta_7d", "optimizacion.max_pedidos_abiertos", "optimizacion.cantidad_max_pedido")
CLAVES_LIMITES_J4 = ("moneda_limites", "gasto_diario_global", "perdida_neta_acumulada_max", "gasto_diario_por_oferta",
                     "gasto_total_test_por_oferta", "perdida_max_test_por_oferta")

# accion_negocio -> accion del contrato decision.schema.json (MATAR|SEGUIR|ESCALAR|INCONCLUSO|BLOQUEADO)
ACCION_CONTRATO = {
    "APAGAR": "MATAR", "MANTENER": "SEGUIR", "GRADUAR": "ESCALAR", "RELEVAR": "SEGUIR", "AVISAR_FATIGA": "SEGUIR",
    "PAUSAR_Y_ESCALAR": "INCONCLUSO", "NO_DECIDIR": "BLOQUEADO",
}


class ErrorProponer(Exception):
    """Entrada o umbrales inválidos (código de salida 3)."""


# ----------------------------------------------------------------------------------------------
# Umbrales
# ----------------------------------------------------------------------------------------------
def _dec(valor: Any, nombre: str) -> Decimal:
    if isinstance(valor, bool) or valor is None:
        raise ErrorProponer(f"umbral {nombre} no numérico: {valor!r}")
    try:
        return Decimal(str(valor))
    except InvalidOperation as exc:
        raise ErrorProponer(f"umbral {nombre} no numérico: {valor!r}") from exc


def _frac(valor: Any, nombre: str) -> Fraction:
    d = _dec(valor, nombre)
    return Fraction(d)


def leer_umbrales(ruta: Path) -> dict[str, Any]:
    try:
        doc = json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ErrorProponer(f"no se pudo leer el archivo de umbrales {ruta}: {exc}") from exc
    if isinstance(doc, dict) and isinstance(doc.get("umbrales"), dict):
        doc = doc["umbrales"]
    if not isinstance(doc, dict):
        raise ErrorProponer("el archivo de umbrales debe ser un objeto {clave: valor|null}")
    return doc


def umbrales_desde_yaml(ruta_parametros: Path, ruta_limites: Path | None) -> dict:
    """Junta los umbrales de ``parametros.yaml`` (``grupos.<g>.<k>.valor``) y los frenos de ``limites.yaml``.

    Solo lectura. Una clave ausente o ``null`` queda en ``null`` y se lista en ``umbrales_faltantes``.
    """
    import yaml  # PyYAML está en requirements; import diferido para que el resto del script no lo exija

    par = yaml.safe_load(Path(ruta_parametros).read_text(encoding="utf-8")) or {}
    grupos = par.get("grupos", {}) if isinstance(par, dict) else {}
    valores: dict[str, Any] = {}
    for clave in (*CLAVES_LANZAMIENTO, *CLAVES_FATIGA, *CLAVES_OPCIONALES):
        grupo, _, nombre = clave.partition(".")
        nodo = (grupos.get(grupo) or {}).get(nombre)
        valores[clave] = nodo.get("valor") if isinstance(nodo, dict) else None
    lim_doc: dict = {}
    if ruta_limites is not None:
        lim_doc = yaml.safe_load(Path(ruta_limites).read_text(encoding="utf-8")) or {}
    for clave in CLAVES_LIMITES_J4:
        valores[f"limites.{clave}"] = lim_doc.get(clave) if isinstance(lim_doc, dict) else None
    faltantes = sorted(k for k, v in valores.items() if v is None)
    return {"umbrales": valores, "umbrales_faltantes": faltantes, "generado_por": f"proponer.py {VERSION} umbrales"}


def _faltantes(u: dict, claves: tuple[str, ...]) -> list[str]:
    return [k for k in claves if u.get(k) is None]


# ----------------------------------------------------------------------------------------------
# Utilidades de salida
# ----------------------------------------------------------------------------------------------
def _base(tipo: str, regla: str, modo: str, entrada: dict) -> dict:
    return {
        "schema_version": VERSION, "tipo": tipo, "regla": regla, "modo": modo,
        "oferta_id": entrada.get("oferta_id"), "fecha_cuenta": entrada.get("fecha_cuenta"),
        "es_propuesta": True,
        "implementacion": "referencia en sombra (S-C); la oficial será engine/d8.py (B2-01/B2-12, ver PEDIDOS.md)",
    }


def _salida(base: dict, accion: str, codigo: str, explicacion: str, *, evidencia: dict, condiciones: list[dict],
            usados: dict, faltantes: list[str], escalar_a: str | None = None) -> dict:
    return {**base, "accion_negocio": accion, "accion_contrato": ACCION_CONTRATO[accion], "codigo": codigo,
            "explicacion": explicacion[:600], "escalar_a": escalar_a, "evidencia": evidencia, "condiciones": condiciones,
            "umbrales_usados": usados, "umbrales_faltantes": faltantes}


def _exigir_entrada(entrada: Any) -> None:
    if not isinstance(entrada, dict) or entrada.get("tipo") != "entrada_d8":
        raise ErrorProponer("la entrada debe ser la de preparar_expediente.py (tipo: entrada_d8)")
    for campo in ("oferta_id", "fecha_cuenta", "dia", "acumulado", "serie_oferta", "contexto", "frescura"):
        if campo not in entrada:
            raise ErrorProponer(f"a la entrada le falta el campo {campo}")


# ----------------------------------------------------------------------------------------------
# Regla J3: baja de lanzamiento
# ----------------------------------------------------------------------------------------------
def evaluar_lanzamiento(entrada: dict, u: dict) -> dict:
    """Tabla de verdad del día 1 (``references/protocolo-j3.md``). Manda la primera condición que se cumple.

    Orden: umbrales -> guardarraíles (PAUSA, infra, datos) -> ¿hubo venta? -> ¿pagos pendientes? -> ¿días cumplidos?
    -> ¿se gastó el presupuesto del día? (salvaguarda J3) -> ¿la landing recibió a los clics? -> BAJA.
    """
    _exigir_entrada(entrada)
    base = _base("propuesta_regla_d8", "J3-BAJA-LANZAMIENTO", "LANZAMIENTO", entrada)
    dia, acum, ctx, fr = entrada["dia"], entrada["acumulado"], entrada["contexto"], entrada["frescura"]
    pres = entrada.get("presupuesto")
    faltan = _faltantes(u, CLAVES_LANZAMIENTO)
    usados = {k: u.get(k) for k in CLAVES_LANZAMIENTO}
    cond: list[dict] = []
    evid: dict = {}

    def fin(accion: str, codigo: str, texto: str, escalar_a: str | None = None) -> dict:
        return _salida(base, accion, codigo, texto, evidencia=evid, condiciones=cond, usados=usados, faltantes=faltan, escalar_a=escalar_a)

    def paso(cid: str, descripcion: str, cumple: bool | None, valor: Any = None) -> bool | None:
        cond.append({"id": cid, "descripcion": descripcion, "cumple": cumple, "valor": valor})
        return cumple

    # 0. Umbrales: sin ellos no se decide (fail-closed)
    if faltan:
        paso("U0", "todos los umbrales de la regla están cargados", False, faltan)
        return fin("NO_DECIDIR", "UMBRAL_FALTANTE", "Faltan umbrales de la regla de lanzamiento: " + ", ".join(faltan) +
                   ". Sin ellos no se propone ninguna baja (ver references/decisiones-y-umbrales.md).", "dueño")
    try:
        baja_dias = int(u["lanzamiento.baja_dias"])
        pct_min = _frac(u["lanzamiento.gasto_cumplido_min_pct"], "lanzamiento.gasto_cumplido_min_pct")
        espera_min = int(_dec(u["lanzamiento.espera_post_dia_h"], "lanzamiento.espera_post_dia_h") * 60)
        max_sin_entrega = int(u["lanzamiento.dias_max_sin_entrega"])
        tasa_min = _frac(u["testeo.tasa_conexion_min"], "testeo.tasa_conexion_min")
        clics_min = int(u["testeo.clics_min_diag"])
        frescura_max_min = int(_dec(u["optimizacion.lectura_horas"], "optimizacion.lectura_horas") * 60)
    except (ValueError, TypeError) as exc:
        raise ErrorProponer(f"umbral con formato inválido: {exc}") from exc
    if baja_dias < 1 or u["lanzamiento.baja_requiere_presupuesto_gastado"] is not True or not (0 < pct_min <= 100):
        paso("U1", "umbrales coherentes con J3 (baja_dias >= 1, salvaguarda de presupuesto gastado = true, 0 < pct <= 100)", False)
        return fin("NO_DECIDIR", "UMBRAL_INCOHERENTE_J3", "Los umbrales no respetan J3: la salvaguarda de presupuesto gastado es obligatoria "
                   "y los días deben ser >= 1.", "dueño")
    paso("U0", "todos los umbrales de la regla están cargados", True)

    # 1. Guardarraíles
    if ctx.get("pausa_activa") is None or ctx.get("infra_semaforo") is None:
        paso("G0", "se conoce el estado de PAUSA y de la infraestructura", False, {"pausa_activa": ctx.get("pausa_activa"), "infra_semaforo": ctx.get("infra_semaforo")})
        return fin("NO_DECIDIR", "CONTEXTO_DESCONOCIDO", "No se sabe si existe empresa/PAUSA o si la infraestructura está en VERDE "
                   "(falta --raiz o empresa/infra/estado.json). Sin eso no se propone nada.", "dueño")
    if ctx["pausa_activa"] is True:
        paso("G1", "no existe empresa/PAUSA", False)
        return fin("NO_DECIDIR", "PAUSA_ACTIVA", "Existe empresa/PAUSA: manda la pausa; D8 no propone gasto ni baja. Reactivar es humano.", "dueño")
    paso("G1", "no existe empresa/PAUSA", True)
    if ctx["infra_semaforo"] != "VERDE":
        paso("G2", "infraestructura en VERDE", False, ctx["infra_semaforo"])
        return fin("NO_DECIDIR", "INFRA_NO_VERDE", f"La infraestructura está en {ctx['infra_semaforo']}: no se decide rendimiento (G7).", "D5")
    paso("G2", "infraestructura en VERDE", True)
    if pres is None or not isinstance(pres.get("diario_minor"), int) or pres["diario_minor"] <= 0:
        paso("G3", "hay presupuesto diario legible", False)
        return fin("NO_DECIDIR", "SIN_PRESUPUESTO", "No hay presupuesto diario legible en 07-campana/campana.json: no se puede evaluar el gasto cumplido.", "D7")
    diario = int(pres["diario_minor"])
    if any(str(a).startswith("monedas_meta_mezcladas") or str(a).startswith("moneda_presupuesto_distinta") for a in entrada.get("avisos", [])):
        paso("G4", "una sola moneda de gasto, igual a la del presupuesto", False)
        return fin("NO_DECIDIR", "MONEDA_INCOHERENTE", "El gasto de Meta y el presupuesto están en monedas distintas: sin tipo de cambio no se compara.", "D7")
    paso("G3", "hay presupuesto diario legible", True, diario)
    if fr.get("ultima_ingesta_meta_ts") is None:
        paso("G5", "hay lecturas de Meta ingeridas", False)
        return fin("NO_DECIDIR", "SIN_INGESTA_META", "La base no tiene ninguna lectura de Meta para la oferta: ¿corre el ETL? No se decide a ciegas.", "D7")
    edad_meta = fr.get("edad_ingesta_meta_min")
    if edad_meta is None or edad_meta > frescura_max_min:
        paso("G5", "la última lectura de Meta es reciente", False, edad_meta)
        return fin("NO_DECIDIR", "DATOS_OBSOLETOS", f"La última lectura de Meta tiene {edad_meta} min (máximo {frescura_max_min}): datos viejos, no se decide (G7).", "D7")
    paso("G5", "la última lectura de Meta es reciente", True, edad_meta)

    if entrada.get("primer_dia_con_gasto") is None:
        paso("L0", "la campaña ya gastó algo", False)
        return fin("MANTENER", "SIN_GASTO_AUN", "Todavía no hay gasto de la campaña en la base: no hay día que juzgar. Si pasó más de "
                   f"{max_sin_entrega} día(s) desde la activación, escalar a D7 (entrega).")
    if dia.get("cerrado") is not True:
        paso("L1", "el día evaluado está cerrado (zona de la cuenta)", False)
        return fin("MANTENER", "DIA_NO_CERRADO", "El día evaluado todavía no terminó en la zona horaria de la cuenta: se evalúa mañana.")
    minutos = dia.get("minutos_desde_cierre")
    if not isinstance(minutos, int) or minutos < espera_min:
        paso("L1", "pasó la espera de compras tardías tras el cierre", False, minutos)
        return fin("MANTENER", "ESPERA_COMPRAS_TARDIAS", f"Pasaron {minutos} min desde el cierre del día y la espera es de {espera_min}: "
                   "una compra tardía de ese día todavía puede llegar.")
    if dia.get("ingesta_meta_posterior_al_cierre") is False:
        paso("L2", "la lectura de Meta del día es posterior al cierre", False)
        return fin("NO_DECIDIR", "DIA_INCOMPLETO", "La lectura de Meta de ese día se ingirió antes de que el día terminara: el gasto está incompleto.", "D7")
    paso("L1", "el día está cerrado y pasó la espera de compras tardías", True, minutos)

    # 2. ¿Hubo venta? (cualquier compra pagada de la oferta, atribuida o no)
    ventas = int(acum.get("ventas_stripe_total", 0))
    atribuidas = int(acum.get("ventas_stripe_atribuidas", 0))
    pendientes = int(acum.get("pedidos_pendientes", 0))
    gasto_dia = int(dia.get("gasto_minor", 0))
    evid.update({
        "desde": acum.get("desde"), "dias_cerrados": entrada.get("dias_cerrados_desde_primer_gasto"),
        "gasto_dia_minor": gasto_dia, "presupuesto_diario_minor": diario,
        "gasto_dia_bp": gasto_dia * 10000 // diario, "ventas_stripe_total": ventas, "ventas_stripe_atribuidas": atribuidas,
        "pedidos_pendientes": pendientes, "clics_enlace": dia.get("clics_enlace"), "vistas_landing": dia.get("vistas_landing"),
        "moneda_gasto": entrada.get("moneda_meta"),
    })
    if ventas >= 1:
        paso("V1", "no hay ninguna venta desde el primer gasto", False, ventas)
        if atribuidas == 0:
            return fin("MANTENER", "VENTA_SIN_ATRIBUCION", f"Hay {ventas} venta(s) pagada(s) pero ninguna atribuida a un anuncio de la campaña: "
                       "no se baja (la oferta vendió). Revisar adid y UTM con D5.", "D5")
        return fin("MANTENER", "LANZAMIENTO_CON_VENTA", f"Hay {ventas} venta(s) pagada(s) desde el lanzamiento ({atribuidas} atribuida(s) a anuncios): "
                   "la oferta sigue viva y pasa al seguimiento continuo (tendencia de 3 días).")
    paso("V1", "no hay ninguna venta desde el primer gasto", True, ventas)
    if pendientes >= 1:
        paso("V2", "no hay pagos asíncronos pendientes", False, pendientes)
        return fin("MANTENER", "PENDIENTES_ASINCRONOS", f"Hay {pendientes} pedido(s) sin pagar todavía (pago asíncrono): no se baja hasta que se resuelvan.")
    paso("V2", "no hay pagos asíncronos pendientes", True)

    # 3. ¿Pasaron los días de J3?
    n_dias = int(entrada.get("dias_cerrados_desde_primer_gasto") or 0)
    if n_dias < baja_dias:
        paso("D1", f"hay al menos {baja_dias} día(s) cerrado(s) desde el primer gasto", False, n_dias)
        return fin("MANTENER", "DIAS_INSUFICIENTES", f"Van {n_dias} día(s) cerrado(s) y la regla pide {baja_dias}.")
    paso("D1", f"hay al menos {baja_dias} día(s) cerrado(s) desde el primer gasto", True, n_dias)

    # 4. Salvaguarda J3: ¿la campaña gastó su presupuesto del día?
    serie = [s for s in entrada["serie_oferta"] if s["fecha"] >= entrada["primer_dia_con_gasto"]]
    ultimos = serie[-baja_dias:]
    cumplido = [Fraction(s["gasto_minor"] * 100, diario) >= pct_min for s in ultimos]
    paso("S1", f"en cada uno de los últimos {baja_dias} día(s) el gasto fue >= {pct_min}% del presupuesto diario", all(cumplido) and len(ultimos) == baja_dias,
         [{"fecha": s["fecha"], "gasto_bp": s["gasto_minor"] * 10000 // diario} for s in ultimos])
    if not (all(cumplido) and len(ultimos) == baja_dias):
        sin_entrega = 0
        for s in reversed(serie):
            if Fraction(s["gasto_minor"] * 100, diario) >= pct_min:
                break
            sin_entrega += 1
        evid["dias_sin_entrega_consecutivos"] = sin_entrega
        if sin_entrega >= max_sin_entrega:
            return fin("PAUSAR_Y_ESCALAR", "ENTREGA_INSUFICIENTE_PERSISTENTE", f"La campaña no gastó su presupuesto del día en {sin_entrega} días seguidos "
                       f"(tope {max_sin_entrega}): no es la oferta, es la entrega. Pausar y pasar a D7 (cuenta, pago, rechazos, puja).", "D7")
        return fin("MANTENER", "ENTREGA_INCOMPLETA", "Salvaguarda J3: la campaña no gastó su presupuesto del día; si Meta no entregó, no es culpa de la oferta. "
                   f"Días seguidos sin entrega: {sin_entrega} (escala a {max_sin_entrega}).")

    # 5. ¿La landing recibió a los clics? (si no, el cero no es de la oferta)
    clics, vistas = dia.get("clics_enlace"), dia.get("vistas_landing")
    if vistas is None:
        paso("C1", "hay eventos de landing para verificar la conexión", False)
        return fin("NO_DECIDIR", "SIN_EVENTOS_LANDING", "No hay eventos de landing (fact_evento) para comprobar que los clics llegaron a la página.", "D5")
    if isinstance(clics, int) and clics >= clics_min:
        ok = Fraction(vistas) >= tasa_min * clics
        paso("C1", f"vistas de landing / clics >= {tasa_min}", ok, {"clics": clics, "vistas": vistas})
        evid["tasa_conexion_bp"] = vistas * 10000 // clics
        if not ok:
            return fin("NO_DECIDIR", "ETAPA_2_CONEXION_BAJA", f"Hubo {clics} clics pero solo {vistas} vistas de landing: puede ser una falla técnica (landing, píxel, "
                       "consentimiento), no de la oferta. No se baja; revisar con D5. Si se repite al día siguiente, proponer pausa.", "D5")
    else:
        paso("C1", f"hay clics suficientes (>= {clics_min}) para evaluar la conexión", None, clics)

    # 6. Baja
    return fin("APAGAR", "LANZAMIENTO_SIN_VENTA_J3", f"Regla J3: {n_dias} día(s) cerrado(s), presupuesto del día gastado ({evid['gasto_dia_bp']} bp del diario), "
               "0 ventas pagadas (ni atribuidas ni sin atribuir), sin pagos pendientes y con medición sana. Se propone dar de baja la campaña de lanzamiento.")


# ----------------------------------------------------------------------------------------------
# Alarma de cansancio: últimos R días contra los P anteriores
# ----------------------------------------------------------------------------------------------
def _sumas(por_dia: dict, fechas: list[str]) -> dict[str, int]:
    out = {"gasto_minor": 0, "impresiones": 0, "clics_enlace": 0, "ventas": 0, "ic": 0}
    for f in fechas:
        d = por_dia.get(f, {})
        out["gasto_minor"] += int(d.get("gasto_minor", 0))
        out["impresiones"] += int(d.get("impresiones", 0))
        out["clics_enlace"] += int(d.get("clics_enlace", 0))
        out["ventas"] += int(d.get("ventas_stripe", 0))
        out["ic"] += int(d.get("ic", 0))
    return out


def _lectura(por_dia: dict, fechas: list[str], k: int, r: int, p: int, prm: dict) -> dict | None:
    """Una lectura de fatiga que termina ``k`` días antes del último día. ``None`` si no alcanzan los días."""
    fin = len(fechas) - k
    ini = fin - (r + p)
    if ini < 0:
        return None
    rec, pre = _sumas(por_dia, fechas[fin - r:fin]), _sumas(por_dia, fechas[ini:fin - r])
    senales: dict[str, dict] = {}
    # --- CTR de enlace (clics / impresiones) ---
    if rec["impresiones"] >= prm["impr_min"] and pre["impresiones"] >= prm["impr_min"] and pre["clics_enlace"] > 0:
        ctr_r, ctr_p = Fraction(rec["clics_enlace"], rec["impresiones"]), Fraction(pre["clics_enlace"], pre["impresiones"])
        fatiga = ctr_r <= (1 - prm["caida"] / 100) * ctr_p
        senales["ctr"] = {"evaluable": True, "fatiga": fatiga, "ctr_reciente_bp": int(ctr_r * 10000), "ctr_previo_bp": int(ctr_p * 10000),
                          "caida_bp": int((1 - ctr_r / ctr_p) * 10000)}
    else:
        senales["ctr"] = {"evaluable": False, "fatiga": None}
    # --- Costo por venta (o, sin ventas suficientes, costo por IC) ---
    cm, k_corte = prm["compras_min"], prm["k_corte"]
    if pre["ventas"] >= cm:
        cpa_p = Fraction(pre["gasto_minor"], pre["ventas"])
        if rec["ventas"] >= cm or Fraction(rec["gasto_minor"]) >= k_corte * cpa_p:
            if rec["ventas"] == 0:
                fatiga, cpa_r_txt = True, None
            else:
                cpa_r = Fraction(rec["gasto_minor"], rec["ventas"])
                fatiga, cpa_r_txt = cpa_r >= prm["factor"] * cpa_p, int(cpa_r)
            senales["cpa"] = {"evaluable": True, "fatiga": fatiga, "cpa_reciente_minor": cpa_r_txt, "cpa_previo_minor": int(cpa_p),
                              "ventas_reciente": rec["ventas"], "ventas_previa": pre["ventas"]}
    if "cpa" not in senales:
        if pre["ic"] >= cm and rec["ic"] >= cm:
            cp_p, cp_r = Fraction(pre["gasto_minor"], pre["ic"]), Fraction(rec["gasto_minor"], rec["ic"])
            senales["cpa"] = {"evaluable": True, "fatiga": cp_r >= prm["factor"] * cp_p, "base": "costo_por_ic",
                              "cpic_reciente_minor": int(cp_r), "cpic_previo_minor": int(cp_p)}
        else:
            senales["cpa"] = {"evaluable": False, "fatiga": None}
    # --- Frecuencia 7 d (solo la lectura más reciente y solo si el ETL la trae) ---
    if k == 0 and prm.get("frecuencia") is not None and prm.get("freq_umbral") is not None:
        senales["frecuencia"] = {"evaluable": True, "fatiga": prm["frecuencia"] >= prm["freq_umbral"]}
    else:
        senales["frecuencia"] = {"evaluable": False, "fatiga": None}
    evaluables = [s for s in senales.values() if s["evaluable"]]
    verdaderas = [s for s in evaluables if s["fatiga"]]
    alerta: bool | None
    if len(evaluables) < prm["senales_min"]:
        alerta = None
    else:
        alerta = len(verdaderas) >= prm["senales_min"]
    return {"k": k, "hasta": fechas[fin - 1], "senales": senales, "alerta": alerta, "ventas_previa": pre["ventas"]}


def evaluar_fatiga(entrada: dict, u: dict) -> dict:
    """Alarma de cansancio por anuncio (``references/fatiga-relevo.md``): últimos R días contra los P anteriores."""
    _exigir_entrada(entrada)
    base = _base("propuesta_regla_d8", "FT-CANSANCIO-3V7", "FATIGA", entrada)
    faltan = _faltantes(u, CLAVES_FATIGA)
    usados = {k: u.get(k) for k in (*CLAVES_FATIGA, *CLAVES_OPCIONALES)}
    if faltan:
        return {**base, "propuestas": [], "anuncios": [], "umbrales_usados": usados, "umbrales_faltantes": faltan,
                "accion_negocio": "NO_DECIDIR", "accion_contrato": "BLOQUEADO", "codigo": "UMBRAL_FALTANTE",
                "explicacion": "Faltan umbrales de la alarma de cansancio: " + ", ".join(faltan) + ". No se propone ningún relevo.", "escalar_a": "dueño"}
    try:
        r, p = int(u["testeo.fatiga_ventana_reciente_dias"]), int(u["testeo.fatiga_ventana_previa_dias"])
        prm = {
            "caida": _frac(u["testeo.fatiga_caida_ctr_pct"], "testeo.fatiga_caida_ctr_pct"),
            "factor": _frac(u["testeo.fatiga_factor_cpa"], "testeo.fatiga_factor_cpa"),
            "senales_min": int(u["testeo.fatiga_senales_min"]), "compras_min": int(u["testeo.fatiga_compras_min"]),
            "impr_min": int(u["testeo.impr_min_diag"]), "k_corte": _frac(u["testeo.k_corte"], "testeo.k_corte"),
            "freq_umbral": _frac(u["testeo.freq_alerta_7d"], "testeo.freq_alerta_7d") if u.get("testeo.freq_alerta_7d") is not None else None,
        }
        lecturas_seguidas = int(u["testeo.fatiga_lecturas_seguidas"])
        max_abiertos = u.get("optimizacion.max_pedidos_abiertos")
        cantidad_max = u.get("optimizacion.cantidad_max_pedido")
    except (ValueError, TypeError) as exc:
        raise ErrorProponer(f"umbral con formato inválido: {exc}") from exc
    if r < 1 or p < 1 or lecturas_seguidas < 1:
        raise ErrorProponer("las ventanas y las lecturas seguidas deben ser >= 1")
    abiertos = entrada["contexto"].get("pedidos_creativos_abiertos")
    resultados, propuestas = [], []
    for an in entrada.get("anuncios", []):
        por_dia = an.get("por_dia", {})
        fechas = sorted(por_dia)
        if not fechas or fechas[-1] != entrada["fecha_cuenta"]:
            resultados.append({"ad_id": an.get("ad_id"), "estado": "DATOS_INSUFICIENTES", "motivo": "la serie no termina en fecha_cuenta"})
            continue
        prm_ad = dict(prm)
        try:
            prm_ad["frecuencia"] = _frac(an["frecuencia_7d"], "frecuencia_7d") if an.get("frecuencia_7d") is not None else None
        except ErrorProponer:
            prm_ad["frecuencia"] = None
        lecturas = [x for x in (_lectura(por_dia, fechas, k, r, p, prm_ad) for k in range(lecturas_seguidas)) if x is not None]
        primera = lecturas[0] if lecturas else None
        if primera is None:
            estado, codigo = "DATOS_INSUFICIENTES", "SERIE_CORTA"
        elif primera["ventas_previa"] < prm["compras_min"]:
            estado, codigo = "NO_APLICA", "SIN_HISTORIAL_DE_VENTAS"  # sin ventas previas no hay ganador que relevar: lo ve la regla de baja/continuo
        elif any(x["alerta"] is None for x in lecturas):
            estado, codigo = "DATOS_INSUFICIENTES", "SENALES_NO_EVALUABLES"
        elif len(lecturas) == lecturas_seguidas and all(x["alerta"] for x in lecturas):
            estado, codigo = "FATIGA_CONFIRMADA", "FATIGA_CONFIRMADA"
        elif lecturas[0]["alerta"]:
            estado, codigo = "FATIGA_UNA_LECTURA", "FATIGA_SIN_CONFIRMAR"
        else:
            estado, codigo = "SIN_FATIGA", "SIN_FATIGA"
        res = {"ad_id": an.get("ad_id"), "concepto_id": an.get("concepto_id"), "estado": estado, "codigo": codigo, "lecturas": lecturas}
        resultados.append(res)
        if estado == "FATIGA_CONFIRMADA":
            hay_cupo = isinstance(max_abiertos, int) and isinstance(cantidad_max, int) and isinstance(abiertos, int) and abiertos < max_abiertos
            accion = "RELEVAR" if hay_cupo else "AVISAR_FATIGA"
            cod = "FATIGA_RELEVO_PEDIDO" if hay_cupo else "FATIGA_SIN_CUPO_DE_PEDIDO"
            texto = (f"Fatiga confirmada en {lecturas_seguidas} lecturas seguidas (últimos {r} días contra los {p} anteriores). "
                     + ("Se propone pedir un relevo a D6 (una sola variable; el anuncio vivo no se toca)." if hay_cupo else
                        "No hay cupo para un pedido nuevo (pedidos abiertos desconocidos o en el máximo): solo se avisa."))
            propuestas.append({"objeto_tipo": "anuncio", "objeto_id": an.get("ad_id"), "accion_negocio": accion, "accion_contrato": ACCION_CONTRATO[accion],
                               "codigo": cod, "regla": "FT", "explicacion": texto, "cantidad_max_pedido": cantidad_max if hay_cupo else None,
                               "variable_a_variar": "hook" if hay_cupo else None})
        elif estado == "FATIGA_UNA_LECTURA":
            propuestas.append({"objeto_tipo": "anuncio", "objeto_id": an.get("ad_id"), "accion_negocio": "AVISAR_FATIGA", "accion_contrato": "SEGUIR",
                               "codigo": "FATIGA_SIN_CONFIRMAR", "regla": "FT", "cantidad_max_pedido": None, "variable_a_variar": None,
                               "explicacion": "Primera lectura con fatiga: se avisa y se vuelve a leer mañana antes de pedir un relevo."})
    return {**base, "propuestas": propuestas, "anuncios": resultados, "umbrales_usados": usados, "umbrales_faltantes": [],
            "ventanas": {"reciente_dias": r, "previa_dias": p, "lecturas_seguidas": lecturas_seguidas}}


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def _cargar_entrada(ruta: str) -> dict:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ErrorProponer(f"no se pudo leer la entrada {ruta}: {exc}") from exc


def _emitir(doc: dict, salida: str | None) -> None:
    texto = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if salida:
        Path(salida).write_text(texto, encoding="utf-8")
    else:
        sys.stdout.write(texto)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Reglas de referencia de D8 en sombra (propone; no ejecuta).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("umbrales", help="arma el archivo de umbrales desde parametros.yaml y limites.yaml (solo lectura)")
    s.add_argument("--parametros", required=True)
    s.add_argument("--limites", default=None)
    s.add_argument("--salida", default=None)
    for nombre in ("lanzamiento", "fatiga"):
        s = sub.add_parser(nombre)
        s.add_argument("--entrada", required=True)
        s.add_argument("--umbrales", required=True)
        s.add_argument("--salida", default=None)
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        if args.cmd == "umbrales":
            doc = umbrales_desde_yaml(Path(args.parametros), Path(args.limites) if args.limites else None)
        else:
            entrada, u = _cargar_entrada(args.entrada), leer_umbrales(Path(args.umbrales))
            doc = evaluar_lanzamiento(entrada, u) if args.cmd == "lanzamiento" else evaluar_fatiga(entrada, u)
    except ErrorProponer as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    _emitir(doc, args.salida)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
