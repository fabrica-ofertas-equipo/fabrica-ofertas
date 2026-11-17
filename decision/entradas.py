"""``decision/entradas.py`` (B1b): puente entre el almacén del motor y ``decision.reglas``.

Construye las entradas tipadas de ``decision.reglas`` a partir de lo que el motor puede leer por sí
mismo (``empresa/parametros.yaml``, ``economia.json`` y el almacén de ``datos``), sin inventar ningún
umbral: todo número que no sale de ahí es, literalmente, un bug.

Funciones (firmas de docs/06 §4.2):

* :func:`parametros_decision` -- ``(par, economia) -> ParametrosDecision``. Lee la economía YA
  calculada (``engine.factibilidad.documento_economia``, única fuente) y aplana los parámetros de
  ``estadistica.*`` y ``testeo.*`` (el esquema de parámetros reparte los umbrales de D8 entre esos dos
  grupos; ver Decisión 1 del README/NOTAS). Nunca asume un valor: si falta, ``ParametroFaltante``
  (código 5) se propaga sin tocar.
* :func:`evidencia_celda` -- ``(conn, oferta_id, nivel, celda_id, ahora, *, par) -> EvidenciaCelda``.
  Agrega gasto, clics y compras desde ``conn`` (SQLite/Postgres portable, esquema de docs/06 §4.8),
  excluye los últimos ``estadistica.dias_madurez_compra`` días (datos inmaduros) y corrige las compras
  por cobertura de ``adid`` del mismo periodo (``compras_corregidas``, docs/08 §5.3). Es el **único**
  sitio que hace esa corrección: ``engine.d8`` no la repite.
* :func:`tracking_sano` -- ``cobertura_bp >= testeo.cobertura_adid_min_pct*100`` **y** (sin muestra
  suficiente de la razón Meta/Stripe, o razón dentro de ``[razon_meta_stripe_min, razon_meta_stripe_max]``).
* :func:`serializar` -- ``Decision -> dict`` sin ningún ``float`` (decimales como cadena).
* :func:`fraccion_desde_pct` -- **único** conversor de un ``*_pct`` de ``limites.yaml`` (unidades de
  porcentaje, 0-100) a fracción (0-1); lo usa :func:`limites_meta_desde` para construir
  ``decision.reglas.LimitesMeta`` (D9/escalado, fuera de B0, pero la conversión vive aquí para que no
  se repita en ningún otro módulo, docs/06 §4.2).

``conn`` es ``engine.estado.abrir_base(raiz)`` (el mismo archivo que pueblan ``datos.etl_meta``/
``datos.etl_stripe``): este módulo SOLO consulta las vistas ``v_d8_*`` de
``datos/migraciones/0003_vistas_d8.sql`` (``v_d8_anuncio``, ``v_d8_gasto_dia``, ``v_d8_conv_meta``,
``v_d8_pedido``), nunca el nombre de una tabla real (sus columnas no coinciden, docs/06 §4.8).

Sin red: ``conn`` es una conexión ya abierta (inyectada); este módulo nunca abre un socket.
"""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from engine import comun
from engine.errores import ErrorValidacion, ParametroFaltante
from engine.parametros import Parametros
from decision.reglas import Accion, Decision, EvidenciaCelda, LimitesMeta, ParametrosDecision

__all__ = [
    "CeldaDesconocida", "evidencia_celda", "fraccion_desde_pct", "limites_meta_desde",
    "parametros_decision", "serializar", "tracking_sano",
]


class CeldaDesconocida(ErrorValidacion):
    """``celda_id``/``nivel`` no resuelve a ningún anuncio conocido de la oferta (código 3)."""


# ------------------------------------------------------------------------------------------------
# parametros_decision: economia.json + parametros.yaml -> ParametrosDecision
# ------------------------------------------------------------------------------------------------
def _monto(valor: Any) -> int:
    """Entero de un campo dinero ``{"monto": int, "moneda": str}`` o un entero ya en esa unidad."""
    if isinstance(valor, Mapping):
        return comun.exigir_importe(valor.get("monto"), "monto")
    return comun.exigir_importe(valor, "monto")


def _moneda_de(valor: Any) -> str | None:
    return valor.get("moneda") if isinstance(valor, Mapping) else None


def _decimal(valor: Any, nombre: str) -> Decimal:
    """Decimal exacto desde una cadena (o un mapa ``{"monto": "cadena", ...}``); ``float`` prohibido."""
    if isinstance(valor, Mapping):
        valor = valor.get("monto")
    if isinstance(valor, float) or isinstance(valor, bool):
        raise ErrorValidacion(f"{nombre}: los decimales van como cadena, nunca float")
    if valor is None:
        raise ErrorValidacion(f"{nombre}: ausente")
    try:
        return Decimal(str(valor))
    except InvalidOperation as exc:
        raise ErrorValidacion(f"{nombre}: decimal inválido {valor!r}") from exc


# Dónde vive cada umbral de ParametrosDecision en empresa/parametros.yaml. El esquema (ola 0b) reparte
# los umbrales de D8 entre "estadistica" (grupo OPCIONAL, D-02) y "testeo" (grupo histórico): esta tabla
# intenta cada candidato EN ORDEN y usa el primero que exista; "estadistica.alfa_descarte_tope" y
# "estadistica.n_min_escala" no tienen hogar en el esquema de hoy (ver NOTAS_B1b «Pedidos» a CT) y por
# eso solo tienen un candidato: sin él, ParametroFaltante (5) es el comportamiento correcto (fail-closed),
# no un error de este módulo.
_CANDIDATOS: dict[str, tuple[str, ...]] = {
    "prior_conv_fuerza_clics": ("estadistica.prior_conv_fuerza_clics",),
    "prior_cpc_fuerza_clics": ("estadistica.prior_cpc_fuerza_clics",),
    "alfa_descarte": ("estadistica.alfa_descarte",),
    "alfa_descarte_tope": ("estadistica.alfa_descarte_tope",),
    "p_escala": ("testeo.p_escala", "estadistica.p_escala"),
    "k_min_matar": ("estadistica.k_min_matar",),
    "n_min_escala": ("estadistica.n_min_escala",),
    "ventana_no_decidir_h": ("testeo.ventana_no_decidir_h", "estadistica.ventana_no_decidir_h"),
    "nodos_cpc": ("estadistica.nodos_cpc",),
}


def _parametro(par: Parametros, campo: str) -> Any:
    """Valor del campo ``campo`` de :class:`ParametrosDecision`, probando sus candidatos en orden."""
    candidatos = _CANDIDATOS[campo]
    ultimo: ParametroFaltante | None = None
    for clave in candidatos:
        try:
            return par.valor(clave)
        except ParametroFaltante as exc:
            ultimo = exc
            continue
    assert ultimo is not None  # _CANDIDATOS siempre tiene >= 1 candidato
    raise ultimo


def parametros_decision(par: Parametros, economia: Mapping[str, Any]) -> ParametrosDecision:
    """``ParametrosDecision`` desde ``empresa/parametros.yaml`` (``par``) y ``economia.json`` ya calculado.

    ``economia`` es el documento de ``engine.factibilidad.documento_economia`` (única fuente, D-01):
    usa ``cpa_be_visto``, ``cpa_obj``, ``cpc_esperado`` y ``conv_central`` tal como los emite ese
    módulo (acepta también los nombres antiguos ``cpa_equilibrio_visto_minor``/``cpa_objetivo_minor``/
    ``cpc_esperado_minor`` si algún llamador todavía los usa, D-02). Errores: ``ErrorValidacion`` (3) si
    la economía no trae estos campos; ``ParametroFaltante`` (5, subclase de ``ErrorLimite``) si falta
    un umbral de parámetros -- se propaga sin envolver: sin él, la operación no decide.
    """
    cpa_be_visto = economia.get("cpa_be_visto", economia.get("cpa_equilibrio_visto_minor"))
    cpa_obj = economia.get("cpa_obj", economia.get("cpa_objetivo_minor"))
    cpc_esperado = economia.get("cpc_esperado", economia.get("cpc_esperado_minor"))
    conv_central = economia.get("conv_central")
    if cpa_be_visto is None or cpa_obj is None or cpc_esperado is None or conv_central is None:
        raise ErrorValidacion(
            "economia incompleta para parametros_decision: faltan cpa_be_visto/cpa_obj/cpc_esperado/conv_central "
            "(¿se pasó el economia.json de engine.factibilidad?)"
        )
    moneda = _moneda_de(cpa_be_visto) or _moneda_de(cpa_obj) or _moneda_de(cpc_esperado) or economia.get("moneda")
    if not moneda:
        raise ErrorValidacion("economia incompleta: no se pudo determinar la moneda")
    return ParametrosDecision(
        moneda=str(moneda),
        cpa_equilibrio_minor=_monto(cpa_be_visto),
        cpa_objetivo_minor=_monto(cpa_obj),
        cpc_prior_minor=float(_decimal(cpc_esperado, "cpc_esperado")),
        prior_conv_media=float(_decimal(conv_central, "conv_central")),
        prior_conv_fuerza_clics=float(_parametro(par, "prior_conv_fuerza_clics")),
        prior_cpc_fuerza_clics=float(_parametro(par, "prior_cpc_fuerza_clics")),
        alfa_descarte=float(_decimal(_parametro(par, "alfa_descarte"), "estadistica.alfa_descarte")),
        alfa_descarte_tope=float(_decimal(_parametro(par, "alfa_descarte_tope"), "estadistica.alfa_descarte_tope")),
        p_escala=float(_decimal(_parametro(par, "p_escala"), "testeo.p_escala")),
        k_min_matar=float(_parametro(par, "k_min_matar")),
        n_min_escala=int(_parametro(par, "n_min_escala")),
        ventana_no_decidir_h=float(_parametro(par, "ventana_no_decidir_h")),
        nodos_cpc=int(_parametro(par, "nodos_cpc")),
    )


# ------------------------------------------------------------------------------------------------
# evidencia_celda: agrega el almacén de datos (esquema portable, docs/06 §4.8) a EvidenciaCelda
# ------------------------------------------------------------------------------------------------
_NIVELES = ("anuncio", "angulo", "oferta_mercado")


def _ids_de_celda(conn: Any, oferta_id: str, nivel: str, celda_id: str) -> list[str]:
    """``ad_id`` de Meta que forman ``celda_id`` (``v_d8_anuncio`` sobre ``dim_anuncio``, docs/06 §4.8).

    Nunca vacío: ``datos.etl_meta.aplicar_fila`` da de alta ``dim_anuncio`` en cada corrida, así que
    cualquier anuncio con al menos un insight ingerido ya resuelve, también para ``oferta_mercado``.
    """
    if nivel == "anuncio":
        fila = conn.execute("SELECT ad_id FROM v_d8_anuncio WHERE oferta_id = ? AND ad_id = ?", (oferta_id, celda_id)).fetchone()
        ids = [str(fila[0])] if fila else []
    elif nivel == "angulo":
        filas = conn.execute(
            "SELECT ad_id FROM v_d8_anuncio WHERE oferta_id = ? AND concepto_id = ?", (oferta_id, celda_id)
        ).fetchall()
        ids = [str(f[0]) for f in filas]
    elif nivel == "oferta_mercado":
        filas = conn.execute("SELECT ad_id FROM v_d8_anuncio WHERE oferta_id = ?", (oferta_id,)).fetchall()
        ids = [str(f[0]) for f in filas]
    else:
        raise ErrorValidacion(f"nivel desconocido: {nivel!r} (se esperaba uno de {_NIVELES})")
    if not ids:
        raise CeldaDesconocida(f"sin anuncios para la celda {nivel}:{celda_id} de {oferta_id}")
    return ids


def _marcadores(n: int) -> str:
    return ",".join("?" * n)


def _gasto_y_clics(conn: Any, ad_ids: Sequence[str], antes_de_fecha: str) -> tuple[int, int]:
    fila = conn.execute(
        f"SELECT COALESCE(SUM(gasto_minor), 0), COALESCE(SUM(clics_enlace), 0) FROM v_d8_gasto_dia "
        f"WHERE ad_id IN ({_marcadores(len(ad_ids))}) AND fecha < ?",
        (*ad_ids, antes_de_fecha),
    ).fetchone()
    return int(fila[0]), int(fila[1])


def _compras_atribuidas(conn: Any, ad_ids: Sequence[str], hasta_ts: str) -> int:
    fila = conn.execute(
        f"SELECT COUNT(*) FROM v_d8_pedido WHERE adid IN ({_marcadores(len(ad_ids))}) AND pagado_en <= ? "
        f"AND estado = 'pagado' AND interno = 0 AND verificacion = 0",
        (*ad_ids, hasta_ts),
    ).fetchone()
    return int(fila[0])


def _cobertura_adid_bp(conn: Any, oferta_id: str, hasta_ts: str) -> tuple[int, bool]:
    """(cobertura en puntos básicos, ``con_muestra``) de ``oferta_id`` (hasta ``hasta_ts``).

    ``con_muestra=False`` cuando todavía no hay NINGÚN pedido pagado de la oferta: ahí la cobertura es
    indefinida, no «0 %» -- no hay nada que corrija ni que desconfíe (lo mismo que ``razón
    Meta/Stripe``: sin muestra, esa señal no puede bloquear por sí sola, docs/08 §5.3). Mismo cálculo
    que tendrá ``datos.cobertura_adid`` (B3): se implementa aquí, sin esperar a ese módulo, porque
    ``evidencia_celda`` lo necesita HOY para B0 (ver NOTAS_B1b «Pedidos»: cuando ``datos.cobertura_adid``
    exista, esta función delega en él en vez de repetir la consulta).
    """
    fila = conn.execute(
        "SELECT COUNT(*), COALESCE(SUM(CASE WHEN adid IS NOT NULL AND adid != 'desconocido' THEN 1 ELSE 0 END), 0) "
        "FROM v_d8_pedido WHERE oferta_id = ? AND pagado_en <= ? AND estado = 'pagado' AND interno = 0 AND verificacion = 0",
        (oferta_id, hasta_ts),
    ).fetchone()
    total, con_adid = int(fila[0]), int(fila[1])
    if total == 0:
        return 0, False
    return (con_adid * 10000) // total, True


def _razon_meta_stripe(
    conn: Any, ad_ids: Sequence[str], *, fin_ts: str, dias_ventana: int, n_min: int,
) -> tuple[Decimal | None, bool]:
    """(razón meta/stripe, muestra_suficiente) en ``[fin_ts - dias_ventana - 2d, fin_ts - 2d]`` (docs/04)."""
    fin = comun.parsear_z(fin_ts) - timedelta(days=2)
    ini = fin - timedelta(days=dias_ventana)
    fin_fecha, ini_fecha = fin.date().isoformat(), ini.date().isoformat()
    fin_iso, ini_iso = comun.iso_z(fin), comun.iso_z(ini)
    fila_meta = conn.execute(
        f"SELECT COALESCE(SUM(c.compras_meta), 0) FROM v_d8_conv_meta c WHERE c.ad_id IN ({_marcadores(len(ad_ids))}) "
        f"AND c.ventana = '1d_click' AND c.fecha >= ? AND c.fecha <= ?",
        (*ad_ids, ini_fecha, fin_fecha),
    ).fetchone()
    fila_stripe = conn.execute(
        f"SELECT COUNT(*) FROM v_d8_pedido WHERE adid IN ({_marcadores(len(ad_ids))}) AND pagado_en > ? "
        f"AND pagado_en <= ? AND estado = 'pagado' AND interno = 0 AND verificacion = 0",
        (*ad_ids, ini_iso, fin_iso),
    ).fetchone()
    compras_meta, compras_stripe = int(fila_meta[0]), int(fila_stripe[0])
    if compras_stripe < n_min:
        return None, False
    if compras_stripe == 0:
        return None, False
    razon = (Decimal(compras_meta) / Decimal(compras_stripe)).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN)
    return razon, True


def tracking_sano(
    cobertura_adid_bp: int, cobertura_con_muestra: bool, razon_meta_stripe: Decimal | None, muestra_suficiente: bool,
    *, par: Parametros,
) -> bool:
    """¿Cobertura de ``adid`` suficiente (si hay muestra) y (sin muestra para la razón, o razón en rango)?

    Única regla de salud de tracking que usa ``decision.reglas`` (vía ``EvidenciaCelda.tracking_sano``).
    Ni la cobertura ni la razón pueden bloquear sin una muestra mínima (mismo principio que
    ``senal_pausa.metricas.muestra_suficiente``): sin ningún pedido todavía no hay nada de qué
    desconfiar, y la regla K1 (matar sin compras) necesita poder actuar precisamente en ese momento.
    """
    if cobertura_con_muestra:
        minimo_bp = int(par.valor("testeo.cobertura_adid_min_pct")) * 100
        if cobertura_adid_bp < minimo_bp:
            return False
    if not muestra_suficiente or razon_meta_stripe is None:
        return True
    minimo = _decimal(par.valor("testeo.razon_meta_stripe_min"), "testeo.razon_meta_stripe_min")
    maximo = _decimal(par.valor("testeo.razon_meta_stripe_max"), "testeo.razon_meta_stripe_max")
    return minimo <= razon_meta_stripe <= maximo


def evidencia_celda(
    conn: Any, oferta_id: str, nivel: str, celda_id: str, ahora: datetime, *, par: Parametros, moneda: str,
    horas_desde_edicion: float | None = None,
) -> EvidenciaCelda:
    """``EvidenciaCelda`` de ``celda_id`` (agregada desde ``conn``, esquema de docs/06 §4.8).

    * Excluye de gasto y clics los últimos ``estadistica.dias_madurez_compra`` días (datos inmaduros,
      docs/08 §5.3); por construcción, lo que queda ya es maduro (``datos_maduros=True``).
    * ``compras_corregidas = round(compras_atribuidas × 10000 / cobertura_adid_bp)`` del MISMO periodo
      (si la cobertura es 0, no hay corrección posible: se deja el valor observado, y ``tracking_sano``
      ya bloquea la decisión por esa misma cobertura).
    * ``tracking_sano`` combina esa cobertura con la razón Meta/Stripe de la ventana de ``testeo.*``.
    * ``horas_desde_edicion``: sin tabla de ediciones en el esquema de ``datos`` (pendiente de B5, ver
      NOTAS_B1b «Pedidos»), por defecto se usa el tiempo desde el primer día con gasto de la celda (el
      proxy más conservador disponible: una celda nunca editada lo tiene exactamente desde su activación).
      Un llamador que SÍ sabe la hora real de la última edición (p. ej. ``engine.d8`` leyendo
      ``07-campana/traspaso.json``) la pasa explícita.

    Errores: ``CeldaDesconocida`` (3) si ``celda_id``/``nivel`` no resuelve a ningún anuncio.
    """
    instante = comun.instante(lambda: ahora)
    ad_ids = _ids_de_celda(conn, oferta_id, nivel, celda_id)
    dias_madurez = int(par.valor("estadistica.dias_madurez_compra"))
    corte_fecha = (instante - timedelta(days=dias_madurez)).date().isoformat()
    corte_ts = comun.iso_z(instante - timedelta(days=dias_madurez))
    gasto_minor, clics = _gasto_y_clics(conn, ad_ids, corte_fecha)
    compras_atribuidas = _compras_atribuidas(conn, ad_ids, corte_ts)
    cobertura_bp, cobertura_con_muestra = _cobertura_adid_bp(conn, oferta_id, corte_ts)
    compras = round(compras_atribuidas * 10000 / cobertura_bp) if cobertura_bp > 0 else compras_atribuidas
    compras = min(compras, clics)  # la corrección nunca puede superar los clics (invariante de reglas.evaluar_celda)
    razon_ventana = int(par.valor("testeo.razon_ventana_dias"))
    razon_n_min = int(par.valor("testeo.razon_n_min"))
    razon, muestra_ok = _razon_meta_stripe(conn, ad_ids, fin_ts=comun.iso_z(instante), dias_ventana=razon_ventana, n_min=razon_n_min)
    sano = tracking_sano(cobertura_bp, cobertura_con_muestra, razon, muestra_ok, par=par)
    if horas_desde_edicion is None:
        fila = conn.execute(
            f"SELECT MIN(fecha) FROM v_d8_gasto_dia WHERE ad_id IN ({_marcadores(len(ad_ids))})", tuple(ad_ids)
        ).fetchone()
        inicio = fila[0]
        if inicio:
            horas_desde_edicion = (instante - comun.parsear_z(f"{inicio}T00:00:00Z")).total_seconds() / 3600.0
        else:
            horas_desde_edicion = 0.0
    return EvidenciaCelda(
        celda_id=celda_id, nivel=nivel, moneda=moneda, gasto_minor=gasto_minor, clics=clics, compras=compras,
        horas_desde_edicion=max(0.0, horas_desde_edicion), tracking_sano=sano, datos_maduros=True,
    )


# ------------------------------------------------------------------------------------------------
# serializar: Decision -> dict sin float
# ------------------------------------------------------------------------------------------------
def _fraccion_texto(x: float) -> str:
    """``float`` interno de una probabilidad/umbral a cadena decimal corta y determinista (docs/08 §5).

    A diferencia de :func:`_decimal` (que RECHAZA un ``float`` porque ahí el llamador externo debería
    haber mandado una cadena), aquí el ``float`` es justamente lo que hay que convertir: viene de
    ``decision.reglas.Decision``, que calcula en coma flotante a propósito (convenciones §3: "float
    solo como tasa en memoria dentro de decision/").
    """
    if x in (0.0, 1.0):
        return f"{x:.0f}"
    texto = f"{round(x, 6):.6f}".rstrip("0")
    return texto if not texto.endswith(".") else texto[:-1]


def _sin_float(valor: Any) -> Any:
    if isinstance(valor, bool) or valor is None or isinstance(valor, (int, str)):
        return valor
    if isinstance(valor, float):
        return _fraccion_texto(valor)
    if isinstance(valor, Mapping):
        return {k: _sin_float(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_sin_float(v) for v in valor]
    return valor


def serializar(d: Decision) -> dict:
    """``Decision`` (``decision.reglas``) a un ``dict`` JSON-seguro, sin ningún ``float``.

    Las probabilidades y umbrales salen como cadena decimal (convenciones §3); ``accion`` como su
    valor de cadena. No es el objeto completo de ``decision.schema.json`` (eso lo arma ``engine.d8``,
    que conoce ``objeto_tipo``, ``lectura_ts``, ``regla`` y el resto del sobre): esto es la foto fiel
    del cálculo de ``decision.reglas.evaluar_celda``.
    """
    if not isinstance(d, Decision):
        raise ErrorValidacion("serializar exige un objeto decision.reglas.Decision")
    bruto = asdict(d)
    bruto["accion"] = d.accion.value if isinstance(d.accion, Accion) else str(d.accion)
    return _sin_float(bruto)


# ------------------------------------------------------------------------------------------------
# Único conversor de *_pct de limites.yaml a fracción (docs/06 §4.2)
# ------------------------------------------------------------------------------------------------
def fraccion_desde_pct(valor_pct: Any) -> Decimal:
    """Convierte un ``*_pct`` de ``limites.yaml`` (unidades de porcentaje, 0-100) a fracción (0-1).

    Único sitio de la fábrica que hace esta conversión (docs/06 §4.2): ``decision.reglas.LimitesMeta``
    exige una fracción y rechaza (``ValueError``) cualquier valor > 1, precisamente para que nadie le
    pase un porcentaje crudo por error. Errores: ``ErrorValidacion`` (3) si no es un decimal en [0, 100].
    """
    try:
        d = Decimal(str(valor_pct))
    except InvalidOperation as exc:
        raise ErrorValidacion(f"porcentaje inválido: {valor_pct!r}") from exc
    if d < 0 or d > 100:
        raise ErrorValidacion(f"porcentaje fuera de rango [0,100]: {valor_pct!r}")
    return d / Decimal(100)


def limites_meta_desde(lim: Any) -> LimitesMeta:
    """``decision.reglas.LimitesMeta`` desde un ``engine.limites.Limites`` (D9/escalado, fuera de B0).

    ``aumento_presupuesto_max_pct_por_paso`` de ``limites.yaml`` está en unidades de porcentaje (20 =
    20 %); esta es la única conversión a fracción (ver :func:`fraccion_desde_pct`).
    """
    return LimitesMeta(
        paso_max_pct=float(fraccion_desde_pct(lim.valor("aumento_presupuesto_max_pct_por_paso"))),
        horas_min_entre_aumentos=float(lim.valor("horas_min_entre_aumentos")),
        max_teorico_factor=float(lim.valor("factor_techo_teorico_diario")),
        max_cambios_por_hora=int(lim.valor("max_cambios_presupuesto_por_hora_por_conjunto")),
        segundos_min_entre_ediciones=int(lim.valor("segundos_min_entre_ediciones")),
    )
