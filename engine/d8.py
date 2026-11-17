"""``d8``: operación diaria (``ciclo``) y veredicto de oferta validada (``veredicto``) (docs/06 N13, §5).

Tres funciones separadas, como las tres subórdenes de ``engine.orq`` (docs/06 §4.2: ``ciclo-d8`` ·
``veredicto`` · ``cerrar``):

* :func:`ciclo` -- UNA lectura diaria: por cada celda (la oferta-mercado completa y cada anuncio),
  construye su ``EvidenciaCelda`` (``decision.entradas.evidencia_celda``), la evalúa
  (``decision.reglas.evaluar_celda``) con el **gasto efectivo** (nunca el leído, docs/06 §5) y aplica
  la única escritura viva sin gate: pausar (``engine.ejecutor.Ejecutor``). También lee
  ``10-postcompra/senal_pausa.json`` (G6) y la consume una sola vez. Devuelve la lista de decisiones
  (misma forma que una línea de ``decision.schema.json``) que el llamador (``orq ciclo-d8``) anexa a
  ``08-operacion/decisiones.jsonl`` con ``engine.comun.anexar_jsonl`` tras registrar cada una.
* :func:`veredicto` -- compara la cohorte de pedidos de Stripe contra la definición única de «oferta
  validada» (backbone 5.9, ``decision.reglas.evaluar_oferta_validada``) y escribe
  ``08-operacion/veredicto_oferta.json``. **No** toca ``fase``: eso es ``engine.cerrar`` (otra sesión)
  y la confirmación humana de ``accion:confirmar_validada``. ``ciclo`` sí mueve ``fase`` a
  ``inconclusa`` cuando el TOPE DE GASTO de la celda ``oferta_mercado`` se agota sin veredicto (docs/06
  §5, tabla de transiciones) -- un concepto distinto del veredicto de madurez de ``veredicto``.

Ambas funciones leen el almacén de ``datos`` (``conn``, el MISMO archivo que pueblan los ETL reales,
``engine.estado.abrir_base``) con SQL directo, pero SOLO contra las vistas ``v_d8_*`` de
``datos/migraciones/0003_vistas_d8.sql`` (nunca el nombre de una tabla real: sus columnas no coinciden
con lo que este módulo necesita, docs/06 §4.8). Cuando ``datos`` (B3) exponga sus propias funciones
(``datos.cobertura_adid``, ``datos.pedidos_cohorte``...) este módulo debería delegar en ellas en vez de
repetir la consulta (ver README, «Pedidos»).

Nunca gasta: ``ciclo`` solo decide y pausa (la única escritura viva sin gate); no activa, no sube
presupuesto, no publica. ``modo`` (``dry_run`` | ``fixture`` | ``live``) solo afecta si de verdad se
llama a ``ejecutor.pausar`` -- ``dry_run`` construye las decisiones pero NO pausa nada (para que el
dueño pueda ver qué haría D8 sin tocar la oferta).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import ROUND_CEILING, ROUND_HALF_EVEN, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from decision import entradas as ent
from decision.reglas import (
    Accion,
    DiaMedia,
    LimitesCelda,
    ParametrosValidacion,
    PedidoStripe,
    evaluar_celda,
    evaluar_oferta_validada,
)
from engine import comun, estado
from engine.ejecutor import Ejecutor
from engine.errores import ErrorBloqueado, ErrorLimite, ErrorValidacion
from engine.limites import Limites
from engine.limites import ruta_por_defecto as _ruta_limites_por_defecto
from engine.parametros import Parametros

__all__ = ["CODIGO_ENTREGA_INESTABLE", "VERSION_REGLAS", "ciclo", "gasto_efectivo", "veredicto"]

VERSION_REGLAS = "1.0.0"  # identifica el conjunto de reglas de este módulo (decision.schema.version_reglas); no es un umbral
_MODOS = ("dry_run", "fixture", "live")
# decision.schema.objeto_tipo solo admite oferta|campana|conjunto|anuncio: una celda "angulo" (varios
# anuncios) no es un objeto de Meta que se pueda pausar de un golpe, así que el ciclo diario decide
# sobre la oferta completa y cada anuncio por separado (ranking_hermanos, de solo lectura, compara
# ángulos sin matar por ellos). Ver NOTAS_B1b «Decisiones».
_REGLA_DE_ACCION = {Accion.MATAR: "K1", Accion.ESCALAR: "M1", Accion.INCONCLUSO: "G2", Accion.BLOQUEADO: "G1", Accion.SEGUIR: "M0"}


# --------------------------------------------------------------------------------------------------
# Utilidades comunes (SQL directo contra las vistas v_d8_* de docs/06 §4.8; ver README)
# --------------------------------------------------------------------------------------------------
def _marcadores(n: int) -> str:
    return ",".join("?" * n)


def _ad_ids_de_oferta(conn: Any, oferta_id: str) -> list[str]:
    filas = conn.execute("SELECT ad_id FROM v_d8_anuncio WHERE oferta_id = ?", (oferta_id,)).fetchall()
    return [str(f[0]) for f in filas]


def _cargar_economia(oferta_id: str, raiz: Path | None) -> dict:
    ruta = (raiz or comun.raiz()) / "ofertas" / oferta_id / "03-oferta" / "economia.json"
    try:
        return comun.cargar_json(ruta)
    except FileNotFoundError as exc:
        raise ErrorBloqueado(f"falta {ruta}: D3 debe correr antes de D8") from exc


def _sin_float(valor: Any) -> Any:
    if isinstance(valor, bool) or valor is None or isinstance(valor, (int, str)):
        return valor
    if isinstance(valor, float):
        if valor in (0.0, 1.0):
            return f"{valor:.0f}"
        texto = f"{round(valor, 6):.6f}".rstrip("0")
        return texto[:-1] if texto.endswith(".") else texto
    if isinstance(valor, Mapping):
        return {k: _sin_float(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_sin_float(v) for v in valor]
    return valor


def hash_parametros(par_decision: Any) -> str:
    """Hash de huella de los parámetros con que se decidió (``decision.schema.hash_parametros``)."""
    from dataclasses import asdict

    return comun.hash_objeto(_sin_float(asdict(par_decision)))


# --------------------------------------------------------------------------------------------------
# Gasto efectivo (docs/06 §5 y docs/08 §4): nunca el gasto leído
# --------------------------------------------------------------------------------------------------
def gasto_efectivo(gasto_leido_minor: int, *, diario_minor: int, horas_sin_lectura: float, factor: Any) -> int:
    """``gasto_leído + factor × diario × (horas_sin_lectura / 24)``, redondeado hacia arriba (conservador).

    ``factor`` es ``limites.factor_techo_teorico_diario`` (Meta puede gastar hasta ~1,75 × el diario en
    un día, docs/06 §5). Con ``horas_sin_lectura <= 0`` el resultado es exactamente ``gasto_leido_minor``.
    """
    if gasto_leido_minor < 0 or diario_minor < 0:
        raise ErrorValidacion("gasto_efectivo exige montos no negativos")
    try:
        f = Decimal(str(factor))
    except InvalidOperation as exc:
        raise ErrorValidacion(f"factor_techo_teorico_diario ilegible: {factor!r}") from exc
    horas = max(0.0, horas_sin_lectura)
    extra = (Decimal(diario_minor) * f * Decimal(str(horas))) / Decimal(24)
    total = Decimal(gasto_leido_minor) + extra
    return int(total.to_integral_value(rounding=ROUND_CEILING))


def _horas_sin_lectura(conn: Any, ad_ids: Sequence[str], ahora: datetime) -> float:
    if not ad_ids:
        return 0.0
    fila = conn.execute(
        f"SELECT MAX(pull_ts) FROM v_d8_gasto_dia WHERE ad_id IN ({_marcadores(len(ad_ids))})", tuple(ad_ids)
    ).fetchone()
    if not fila or not fila[0]:
        return 0.0
    return max(0.0, (ahora - comun.parsear_z(str(fila[0]))).total_seconds() / 3600.0)


# --------------------------------------------------------------------------------------------------
# senal_pausa.json (D10 -> D8, G6, docs/contratos.md R08)
# --------------------------------------------------------------------------------------------------
def _ruta_senal_pausa(oferta_id: str, raiz: Path | None) -> Path:
    return (raiz or comun.raiz()) / "ofertas" / oferta_id / "10-postcompra" / "senal_pausa.json"


def _decision_id(oferta_id: str, objeto_id: str, lectura_ts: str) -> str:
    return comun.hash_objeto({"oferta_id": oferta_id, "objeto_id": objeto_id, "lectura_ts": lectura_ts})


def _procesar_senal_pausa(
    oferta_id: str, est_actual: Mapping[str, Any], instante: datetime, *, ejecutor: Ejecutor, raiz: Path | None, modo: str,
) -> dict | None:
    """Lee ``senal_pausa.json`` (si existe), la consume UNA vez y pausa la oferta si corresponde (G6).

    Idempotente: si ``consumida_por`` ya está lleno, no hace nada (ni vuelve a pausar ni reescribe el
    archivo). Devuelve el registro de decisión (forma de ``decision.schema.json``) o ``None`` si no
    había nada que procesar.
    """
    ruta = _ruta_senal_pausa(oferta_id, raiz)
    try:
        senal = comun.cargar_json(ruta)
    except FileNotFoundError:
        return None
    if not senal.get("emitida") or senal.get("consumida_por") is not None:
        return None
    lectura_ts = comun.iso_z(instante)
    decision_id = _decision_id(oferta_id, oferta_id, lectura_ts)
    accion = Accion.INCONCLUSO if senal.get("accion_solicitada") == "pausar" else Accion.SEGUIR
    registro = {
        "schema_version": "1.1.0", "decision_id": decision_id, "oferta_id": oferta_id, "objeto_tipo": "oferta",
        "objeto_id": oferta_id, "lectura_ts": lectura_ts, "ts": lectura_ts, "nivel": est_actual.get("nivel", "N0"),
        "gate": "A", "accion": accion.value, "codigo": f"senal_pausa_{senal.get('motivo', 'otro')}",
        "regla": "G6", "version_reglas": VERSION_REGLAS, "hash_parametros": comun.hash_objeto({"senal": senal.get("umbrales_usados")}),
        "evidencia": {"gasto": {"monto": 0, "moneda": "EUR"}, "clics": 0, "compras": 0, "p_cpa_menor_equilibrio": None},
        "explicacion": f"Señal de D10 (nivel {senal.get('nivel')}, motivo {senal.get('motivo')}): "
                       f"{senal.get('accion_solicitada')}.",
        "ejecutada": False,
    }
    if accion == Accion.INCONCLUSO and est_actual.get("fase") == "en_test" and modo != "dry_run":
        resultado = ejecutor.pausar(oferta_id, motivo=f"senal_pausa: {senal.get('motivo')}")
        registro["ejecutada"] = bool(resultado.ok)
    senal_actualizada = dict(senal)
    senal_actualizada["consumida_por"] = {"etapa": "D8", "decision_id": decision_id, "ts": lectura_ts}
    if modo != "dry_run":
        comun.escribir_atomico(ruta, comun.json_canonico(senal_actualizada))
    return registro


# --------------------------------------------------------------------------------------------------
# traspaso de D7 (07-campana/traspaso.json, esquema traspaso 1.x): acta del lanzamiento. Sin archivo, D8 decide solo por
# tiempo (ventana_no_decidir_h) y por pausa, como siempre. Con un lanzamiento marcado INESTABLE (ventana de 72 h medida
# sin ser estable, o anomalías), D8 NO ESCALA (escalar gasta más sobre un lanzamiento dudoso); SÍ sigue pudiendo MATAR y
# cerrar por tope, porque eso limita la pérdida (no se frena una pausa para «esperar»).
# --------------------------------------------------------------------------------------------------
CODIGO_ENTREGA_INESTABLE = "ENTREGA_D7_INESTABLE"


def _traspaso_inestable(oferta_id: str, raiz: Path | None) -> str | None:
    """Motivo (texto) si ``07-campana/traspaso.json`` marca el lanzamiento como inestable; ``None`` si no hay
    archivo o es estable. Un archivo ilegible o con forma rara cuenta como inestable (falla cerrado: no escala)."""
    ruta = (raiz or comun.raiz()) / "ofertas" / oferta_id / "07-campana" / "traspaso.json"
    if not ruta.is_file():
        return None
    try:
        doc = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "07-campana/traspaso.json ilegible"
    if not isinstance(doc, dict) or not isinstance(doc.get("lanzamiento_estable"), bool):
        return "07-campana/traspaso.json sin lanzamiento_estable booleano"
    anomalias = doc.get("anomalias")
    if isinstance(anomalias, list) and anomalias:
        return "anomalías en el traspaso: " + ", ".join(str(a) for a in anomalias[:5])
    if doc.get("ventana_h") == 72 and doc["lanzamiento_estable"] is False:
        return "la ventana de 72 h terminó sin lanzamiento estable"
    return None


# --------------------------------------------------------------------------------------------------
# ciclo(): una lectura diaria
# --------------------------------------------------------------------------------------------------
def ciclo(
    oferta_id: str, *, conn: Any, ahora: Callable[[], datetime], par: Parametros, lim: Limites, ejecutor: Ejecutor,
    modo: str = "dry_run", raiz: Path | None = None,
) -> list[dict]:
    """Una lectura diaria de D8: lee, decide y pausa (nunca gasta, nunca activa).

    Devuelve la lista de registros (forma de ``decision.schema.json``, sin ``ejecutar_cli`` de por
    medio: el llamador decide si los anexa a ``decisiones.jsonl``). ``modo="dry_run"`` calcula las
    mismas decisiones pero NO llama a ``ejecutor.pausar`` ni consume ``senal_pausa.json`` (para que
    ``orq ciclo-d8`` sin ``--live`` pueda mostrar qué haría D8 sin tocar nada, convenciones §9).
    """
    if modo not in _MODOS:
        raise ErrorValidacion(f"modo desconocido: {modo!r} (se esperaba uno de {_MODOS})")
    instante = comun.instante(ahora)
    est_actual = estado.cargar(oferta_id, raiz=raiz)
    registros: list[dict] = []

    reg_senal = _procesar_senal_pausa(oferta_id, est_actual, instante, ejecutor=ejecutor, raiz=raiz, modo=modo)
    if reg_senal is not None:
        registros.append(reg_senal)
        if reg_senal["ejecutada"]:
            est_actual = estado.cargar(oferta_id, raiz=raiz)

    if est_actual["fase"] != "en_test":
        return registros  # pausada/cerrada/final: nada más que decidir hoy (el veredicto sigue aparte)

    economia = _cargar_economia(oferta_id, raiz)
    par_decision = ent.parametros_decision(par, economia)
    moneda = par_decision.moneda
    tope_celda_minor = int(lim.valor("gasto_total_test_por_oferta"))
    diario_minor = int(lim.valor("gasto_diario_por_oferta"))
    factor = lim.valor("factor_techo_teorico_diario")
    lim_celda = LimitesCelda(tope_gasto_celda_minor=tope_celda_minor)

    ad_ids = _ad_ids_de_oferta(conn, oferta_id)
    horas_sin_lectura = _horas_sin_lectura(conn, ad_ids, instante)
    celdas: list[tuple[str, str, str, str]] = [("oferta_mercado", oferta_id, "oferta", oferta_id)]
    celdas += [("anuncio", ad_id, "anuncio", ad_id) for ad_id in ad_ids]

    lectura_ts = comun.iso_z(instante)
    hp = hash_parametros(par_decision)
    motivo_inestable = _traspaso_inestable(oferta_id, raiz)
    for nivel, celda_id, objeto_tipo, objeto_id in celdas:
        ev = ent.evidencia_celda(conn, oferta_id, nivel, celda_id, instante, par=par, moneda=moneda)
        ev_efectiva = replace(ev, gasto_minor=gasto_efectivo(
            ev.gasto_minor, diario_minor=diario_minor, horas_sin_lectura=horas_sin_lectura, factor=factor,
        ))
        d = evaluar_celda(ev_efectiva, par_decision, lim_celda)
        if motivo_inestable is not None and d.accion == Accion.ESCALAR:
            d = replace(d, accion=Accion.SEGUIR, codigo=CODIGO_ENTREGA_INESTABLE,
                        explicacion=f"SEGUIR (no escalar): {motivo_inestable}. {d.explicacion}")
        ejecutada = False
        if modo != "dry_run":
            if d.accion == Accion.MATAR:
                resultado = ejecutor.pausar(objeto_id, motivo=f"D8 MATAR ({d.codigo}): {d.explicacion[:200]}")
                ejecutada = bool(resultado.ok)
            elif d.accion == Accion.INCONCLUSO and nivel == "oferta_mercado":
                # INCONCLUSO mueve la fase directo a "inconclusa" (docs/06 §5): NO pasa por
                # ejecutor.pausar(oferta_id) porque esa función solo sabe mover a "pausada" (el
                # genérico de PAUSA/kill switch), una transición distinta ("pausada" -> "inconclusa"
                # no existe en la máquina de estados). El "ejecutor" sigue siendo quien detendría el
                # gasto real en Meta si hiciera falta un pausador_meta (pedido pendiente a B5); aquí
                # ya no hay oferta "en_test" que pueda seguir gastando una vez cambiada la fase.
                try:
                    estado.transicionar_fase(oferta_id, "inconclusa", actor="motor", causa=d.codigo, raiz=raiz, ahora=ahora)
                    ejecutada = True
                except ErrorValidacion:
                    ejecutada = False  # otra celda de esta misma corrida ya movió la fase
        registro = {
            "schema_version": "1.1.0", "decision_id": _decision_id(oferta_id, objeto_id, lectura_ts),
            "oferta_id": oferta_id, "objeto_tipo": objeto_tipo, "objeto_id": objeto_id, "lectura_ts": lectura_ts,
            "ts": lectura_ts, "nivel": est_actual.get("nivel", "N0"), "gate": "A", "accion": d.accion.value,
            "codigo": d.codigo, "regla": _REGLA_DE_ACCION[d.accion], "version_reglas": VERSION_REGLAS,
            "hash_parametros": hp,
            "evidencia": {
                "gasto": {"monto": ev.gasto_minor, "moneda": moneda}, "clics": ev.clics, "compras": ev.compras,
                "p_cpa_menor_equilibrio": None if d.p_cpa_menor_equilibrio is None else _sin_float(d.p_cpa_menor_equilibrio),
            },
            "explicacion": d.explicacion[:600], "ejecutada": ejecutada,
        }
        registros.append(registro)
    return registros


# --------------------------------------------------------------------------------------------------
# veredicto(): definición única de "oferta validada" (backbone 5.9)
# --------------------------------------------------------------------------------------------------
# veredicto_oferta.schema.json no tiene "PROVISIONAL": una vista con cohortes inmaduras que ya cumple,
# pero sin madurez todavía, es información a medio camino, no un veredicto final; se reporta como
# INCONCLUSA (nunca se inventa una categoría nueva fuera del contrato). Ver NOTAS_B1b «Decisiones».
_ESTADO_A_RECOMENDACION = {
    "VALIDADA": "escalar", "FALLIDA": "cerrar", "PROMETEDORA": "seguir_test", "INCONCLUSA": "extender_test",
}


def _pedidos_y_dias(conn: Any, oferta_id: str, ad_ids: Sequence[str], moneda: str) -> tuple[list[PedidoStripe], list[DiaMedia]]:
    filas = conn.execute(
        "SELECT session_id, pagado_en, moneda, bruto_minor, impuesto_minor, fee_minor, adid FROM v_d8_pedido "
        "WHERE oferta_id = ? AND estado = 'pagado' AND interno = 0 AND verificacion = 0",
        (oferta_id,),
    ).fetchall()
    pedidos: list[PedidoStripe] = []
    for session_id, pagado_en, m, bruto, impuesto, fee, adid in filas:
        if m != moneda:
            continue
        reemb = conn.execute(
            "SELECT COALESCE(SUM(monto_minor), 0) FROM v_d8_reembolso WHERE session_id = ? AND estado = 'ejecutado'",
            (session_id,),
        ).fetchone()[0]
        disputa_abierta = conn.execute(
            "SELECT COALESCE(SUM(monto_minor), 0) FROM fact_disputa WHERE session_id = ? AND estado = 'abierta'",
            (session_id,),
        ).fetchone()[0] if _tabla_existe(conn, "fact_disputa") else 0
        pedidos.append(PedidoStripe(
            pedido_id=str(session_id), pagado_en=str(pagado_en), moneda=m, bruto_minor=int(bruto),
            impuesto_minor=int(impuesto), comision_minor=int(fee), reembolso_bruto_minor=int(reemb),
            disputa_abierta_minor=int(disputa_abierta), atribuido_a_anuncio=bool(adid and adid != "desconocido"),
        ))
    dias: list[DiaMedia] = []
    if ad_ids:
        filas_dia = conn.execute(
            f"SELECT fecha, SUM(gasto_minor), SUM(clics_enlace) FROM v_d8_gasto_dia "
            f"WHERE ad_id IN ({_marcadores(len(ad_ids))}) GROUP BY fecha",
            tuple(ad_ids),
        ).fetchall()
        dias = [DiaMedia(fecha=str(f), gasto_minor=int(g), clics=int(c)) for f, g, c in filas_dia]
    return pedidos, dias


def _tabla_existe(conn: Any, nombre: str) -> bool:
    try:
        conn.execute(f"SELECT 1 FROM {nombre} LIMIT 1")
        return True
    except Exception:  # noqa: BLE001 - sondeo de esquema, no decisión de negocio
        return False


def _parametros_validacion(par: Parametros, lim: Limites) -> ParametrosValidacion:
    return ParametrosValidacion(
        garantia_dias=int(lim.valor("politica_reembolso_dias")),
        margen_madurez_dias=int(par.valor("veredicto.madurez_dias_extra")),
        n_val=int(par.valor("veredicto.compras_min")),
        dias_con_compras_min=int(par.valor("veredicto.dias_min")),
        max_dia_pct=float(par.valor("veredicto.max_dia_pct")) / 100.0,
        reembolso_max=float(par.valor("veredicto.reembolso_max_pct")) / 100.0,
        p_validada=float(par.valor("testeo.p_escala")),
        p_fallida=float(par.valor("testeo.p_fallida")),
        k_min_fallida=float(par.valor("estadistica.k_min_fallida")),
        factor_objetivo=float(Decimal(str(par.valor("economia.factor_cpa_objetivo")))),
        costo_var_pedido_minor=0,
        tasa_reembolso_esperada=float(par.valor("salud_operativa.reembolsos_objetivo_pct")) / 100.0,
    )


def _siguiente_version(existente: dict | None) -> str:
    if not existente or not isinstance(existente.get("version"), str) or not existente["version"].startswith("v"):
        return "v1"
    try:
        return f"v{int(existente['version'][1:]) + 1}"
    except ValueError:
        return "v1"


def veredicto(oferta_id: str, *, conn: Any, ahora: Callable[[], datetime], par: Parametros, lim: Limites,
             raiz: Path | None = None, sintetico: bool = False) -> dict:
    """Veredicto de oferta validada (backbone 5.9) sobre la cohorte de Stripe; escribe ``veredicto_oferta.json``.

    No toca ``fase`` (eso es ``engine.cerrar`` + confirmación humana para ``VALIDADA``, y ``ciclo`` para
    la ``inconclusa`` por tope de gasto). Puede llamarse en cualquier fase posterior a la activación
    (incluida ``pausada``/``inconclusa`` durante ``espera_madurez``, docs/06 B0-22): sigue leyendo sin
    gastar. Errores: ``ErrorBloqueado`` (4) si falta ``economia.json``.
    """
    instante = comun.instante(ahora)
    economia = _cargar_economia(oferta_id, raiz)
    par_decision = ent.parametros_decision(par, economia)
    moneda = par_decision.moneda
    ad_ids = _ad_ids_de_oferta(conn, oferta_id)
    pedidos, dias = _pedidos_y_dias(conn, oferta_id, ad_ids, moneda)
    pv = _parametros_validacion(par, lim)
    resultado = evaluar_oferta_validada(pedidos, dias, comun.iso_z(instante), pv, par_decision)

    usar_madura = resultado.madura.compras_netas >= pv.n_val
    vista = resultado.madura if usar_madura else resultado.provisional
    estado_doc = {"VALIDADA": "VALIDADA", "FALLIDA": "FALLIDA", "PROMETEDORA": "PROMETEDORA"}.get(resultado.estado, "INCONCLUSA")

    compras_brutas = vista.pedidos_pagados
    reembolsos = round((vista.reembolso_pct or 0.0) * compras_brutas)
    compras_meta_ref = 0
    if ad_ids:
        fila = conn.execute(
            f"SELECT COALESCE(SUM(compras_meta), 0) FROM v_d8_conv_meta WHERE ad_id IN ({_marcadores(len(ad_ids))}) AND ventana = '1d_click'",
            tuple(ad_ids),
        ).fetchone()
        compras_meta_ref = int(fila[0])
    razon_ms = None
    if vista.compras_netas:
        razon_ms = str((Decimal(compras_meta_ref) / Decimal(vista.compras_netas)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))
    cpa_objetivo_minor = (
        int(round(pv.factor_objetivo * vista.mc_neta_minor)) if vista.mc_neta_minor is not None else par_decision.cpa_objetivo_minor
    )

    doc = {
        "schema_version": "1.0.0",
        "oferta_id": oferta_id,
        "ts": comun.iso_z(instante),
        "version": "v1",
        "estado": estado_doc,
        "regla": {"id": "evaluar_oferta_validada", "definicion": "backbone-5.9", "version_reglas": VERSION_REGLAS,
                  "hash_parametros": hash_parametros(par_decision)},
        "evidencia": {
            "fuente_compras": "stripe", "compras_brutas": compras_brutas, "reembolsos": reembolsos,
            "compras_netas": vista.compras_netas, "compras_meta_referencia": compras_meta_ref,
            "garantia_dias": pv.garantia_dias, "madurez_dias": pv.garantia_dias + pv.margen_madurez_dias,
            "cohorte_madura_hasta": resultado.fecha_corte_madurez_utc[:10],
            "dias_con_datos": vista.dias_con_compras, "gasto": {"monto": vista.gasto_minor, "moneda": moneda},
            "cpa_neto": None if vista.cpa_neto_minor is None else {"monto": int(round(vista.cpa_neto_minor)), "moneda": moneda},
            "cpa_objetivo": {"monto": cpa_objetivo_minor, "moneda": moneda},
            "mc_real": None if vista.mc_neta_minor is None else {"monto": int(round(vista.mc_neta_minor)), "moneda": moneda},
            "razon_ms": razon_ms,
            "reembolso_pct": _sin_float(round((vista.reembolso_pct or 0.0) * 100, 4)),
        },
        "p": None if vista.p_cpa_menor_equilibrio_real is None else _sin_float(vista.p_cpa_menor_equilibrio_real),
        "estabilidad": None,  # sin formula especificada todavia (ver NOTAS_B1b, fail-closed: no se inventa)
        "recomendacion": _ESTADO_A_RECOMENDACION[estado_doc],
        "gate": "A",
        "sintetico": sintetico,
    }
    errores = comun.errores_de_esquema("veredicto_oferta", doc)
    if errores:
        raise ErrorValidacion(f"veredicto_oferta.json generado no cumple su esquema: {comun.resumir_errores_esquema(errores)}")
    ruta = (raiz or comun.raiz()) / "ofertas" / oferta_id / "08-operacion" / "veredicto_oferta.json"
    try:
        previo = comun.cargar_json(ruta)
    except FileNotFoundError:
        previo = None
    doc["version"] = _siguiente_version(previo)
    comun.escribir_atomico(ruta, comun.json_canonico(doc))
    return doc
