"""B0-15 (``datos``, dueño B3) y la mitad de B0-16 que me toca (el generador listo y probado,
``scripts.b0.generador``; la evaluación MATAR/SEGUIR/VALIDADA es de ``engine.d8``, I1a).

B0-15: corre el ETL real (``datos.etl_meta``, ``datos.etl_stripe``, ``datos.ledger``) dos veces sobre
el escenario generado; las tablas deben quedar idénticas la segunda vez (upsert idempotente),
``cobertura_adid`` debe superar el mínimo que fijo para el escenario, y la conciliación
Stripe↔ledger debe dar diferencia 0 (``estado == "CONCILIADO"``).
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from scripts.b0 import generador

OFERTA = "OF-202611-01"
_DESDE, _HASTA = "2026-11-10", "2026-11-25"  # 14 días del generador + margen para el retraso de atribución (36h) del escenario C
_MONEDA = "EUR"
_COBERTURA_MINIMA_BP = 8000  # 80,00%: umbral propio de este escenario, no leído de parametros.yaml real


def _hash_tablas(conn) -> dict[str, int]:
    """Huella barata de cada tabla relevante (cuenta de filas + suma de un hash por fila) para
    comprobar «mismos datos» sin comparar fila por fila a mano."""
    tablas = ("raw_meta_insight", "fact_meta_ad_dia", "fact_pedido", "fact_reembolso", "fact_disputa", "stripe_evento")
    huella: dict[str, int] = {}
    for tabla in tablas:
        filas = conn.ejecutar(f"SELECT * FROM {tabla} ORDER BY rowid").fetchall()
        huella[tabla] = len(filas)
        huella[f"{tabla}__suma_hash"] = sum(hash(tuple(sorted(dict(f).items()))) for f in filas)
    return huella


def _correr_etl_una_vez(conn, raiz: Path, meta_doc: dict, stripe_doc: dict, *, ahora) -> dict[str, int]:
    from datos import etl_meta, etl_stripe, ledger

    # Mismo reloj en ambas corridas: la idempotencia que exige B0-15 es sobre los DATOS de negocio
    # (gasto, impresiones, pedidos…), no sobre `ingerido_en` (bookkeeping que cambia en cada lectura
    # real); congelarlo es lo que permite comparar las tablas byte a byte entre las dos corridas.
    etl_meta.aplicar_insights(conn, OFERTA, meta_doc, desde=_DESDE, hasta=_HASTA, ahora=ahora)
    conteo_stripe = etl_stripe.aplicar_lote(conn, stripe_doc["eventos"], ahora=ahora)
    lineas = ledger.generar_lineas(conn, raiz, OFERTA, _DESDE, _HASTA)
    resultado = ledger.escribir_ledger(ledger.ruta_ledger(raiz), lineas)
    return {"stripe": conteo_stripe, "ledger": resultado}


def _escenario_etl_doble(nombre_escenario: str) -> tuple[bool, str]:
    from datos.atribucion import cobertura_adid
    from datos.db import conectar, migrar
    from datos.ledger import conciliar

    escenario = generador.generar_escenario(nombre_escenario)
    with tempfile.TemporaryDirectory(prefix="b0-datos-") as tmp_str:
        raiz = Path(tmp_str)
        (raiz / "empresa" / "finanzas").mkdir(parents=True, exist_ok=True)
        (raiz / "empresa" / "costos.jsonl").touch()
        conn = conectar(f"sqlite:///{raiz}/empresa/datos/fabrica.db")
        migrar(conn)
        from datetime import datetime, timezone

        reloj = lambda: datetime(2026, 11, 24, 6, 0, 0, tzinfo=timezone.utc)
        try:
            resultado_1 = _correr_etl_una_vez(conn, raiz, escenario["meta"], escenario["stripe"], ahora=reloj)
            huella_1 = _hash_tablas(conn)
            resultado_2 = _correr_etl_una_vez(conn, raiz, escenario["meta"], escenario["stripe"], ahora=reloj)
            huella_2 = _hash_tablas(conn)

            problemas: list[str] = []
            if huella_1 != huella_2:
                diffs = {k: (huella_1[k], huella_2[k]) for k in huella_1 if huella_1[k] != huella_2[k]}
                problemas.append(f"las tablas NO quedaron idénticas tras correr el ETL dos veces: {diffs}")
            if resultado_2["stripe"]["nuevos"] != 0:
                problemas.append(f"la segunda corrida de etl_stripe reportó {resultado_2['stripe']['nuevos']} evento(s) nuevo(s) (debería ser 0, todo duplicado)")
            if resultado_2["ledger"]["nuevas"] != 0:
                problemas.append(f"la segunda corrida del ledger agregó {resultado_2['ledger']['nuevas']} línea(s) nueva(s) (debería ser 0)")

            cobertura = cobertura_adid(conn, OFERTA, _DESDE, _HASTA)
            if cobertura < _COBERTURA_MINIMA_BP:
                problemas.append(f"cobertura_adid={cobertura} bp < mínimo {_COBERTURA_MINIMA_BP} bp")

            conciliacion = conciliar(conn, raiz, OFERTA, _DESDE, _HASTA, _MONEDA)
            if conciliacion["stripe_vs_ledger"]["diferencia"]["monto"] != 0:
                problemas.append(f"Stripe vs ledger no da 0: {conciliacion['stripe_vs_ledger']}")
            if conciliacion["estado"] != "CONCILIADO":
                problemas.append(f"conciliacion.estado={conciliacion['estado']!r} != 'CONCILIADO'")

            if problemas:
                return False, "; ".join(problemas)
            return True, (
                f"ETL x2 (meta+stripe+ledger) sobre «{nombre_escenario}»: tablas idénticas, 0 eventos/líneas "
                f"nuevas en la 2da corrida, cobertura_adid={cobertura}bp (>= {_COBERTURA_MINIMA_BP}), "
                f"conciliacion.estado=CONCILIADO (Stripe↔ledger=0)"
            )
        finally:
            conn.cerrar()


def evaluar_b0_15():
    from scripts.b0_e2e import _con_captura_de_error, _rojo, _verde

    def cuerpo():
        resultados = {nombre: _escenario_etl_doble(nombre) for nombre in generador.ESCENARIOS}
        fallos = {n: m for n, (ok, m) in resultados.items() if not ok}
        if fallos:
            return _rojo("B0-15", "; ".join(f"{n}: {m}" for n, m in fallos.items()))
        return _verde("B0-15", " | ".join(resultados[n][1] for n in generador.ESCENARIOS))

    return _con_captura_de_error("B0-15", cuerpo)


# --------------------------------------------------------------------------------------------------------------------
# B0-16 (SOLO la mitad del generador; la evaluación de desenlace MATAR/ESCALAR/INCONCLUSA es de engine.d8, I1a)
# --------------------------------------------------------------------------------------------------------------------
def _verificar_generador_tres_escenarios() -> tuple[bool, str]:
    from datos.atribucion import cobertura_adid
    from datos.db import conectar, migrar

    problemas: list[str] = []
    for nombre in generador.ESCENARIOS:
        e1 = generador.generar_escenario(nombre)
        e2 = generador.generar_escenario(nombre)
        if e1 != e2:
            problemas.append(f"{nombre}: no es determinista (dos corridas con la misma semilla difieren)")
        for doc, clave in ((e1["meta"], "filas"), (e1["stripe"], "eventos")):
            if doc.get("sintetico") is not True:
                problemas.append(f"{nombre}: {clave} sin sintetico:true")
    # La cobertura EXACTA del escenario C debe ser 95,00% (9500 bp): es el caso explícito de docs/08 §5.3.
    with tempfile.TemporaryDirectory(prefix="b0-datos-gen-") as tmp_str:
        raiz = Path(tmp_str)
        conn = conectar(f"sqlite:///{raiz}/empresa/datos/fabrica.db")
        migrar(conn)
        try:
            from datos import etl_stripe

            escenario_c = generador.generar_escenario("C_intermedio_95_retraso")
            etl_stripe.aplicar_lote(conn, escenario_c["stripe"]["eventos"])
            cobertura_c = cobertura_adid(conn, OFERTA, _DESDE, _HASTA)
            if cobertura_c != 9500:
                problemas.append(f"escenario C: cobertura_adid={cobertura_c} bp != 9500 (95,00% exacto esperado)")
        finally:
            conn.cerrar()
    if problemas:
        return False, "; ".join(problemas)
    return True, "3 escenarios (A/B/C) deterministas y sintetico:true; cobertura del escenario C exactamente 95,00%"


def evaluar_b0_16():
    from scripts.b0_e2e import _con_captura_de_error, _pendiente

    def cuerpo():
        ok, motivo = _verificar_generador_tres_escenarios()
        detalle = motivo if ok else f"FALLO REAL en el generador: {motivo}"
        return _pendiente(
            "B0-16",
            f"{detalle} — mitad de B0-16 que me toca (scripts.b0.generador: 3 escenarios incl. 95% "
            "cobertura + retraso de atribución, listos y probados). Falta, y depende de engine.d8 (en "
            "construcción esta noche por B1a/B1b, no debo tocarlo): correr estos mismos datos a través "
            "del ciclo de decisión real y comprobar que el desenlace (MATAR/ESCALAR/INCONCLUSA) y las "
            "tasas caen dentro de docs/08 §5.3, y que una celda con «CPM alto» no mata por sí sola. Lo hace I1a.",
        )

    return _con_captura_de_error("B0-16", cuerpo)
