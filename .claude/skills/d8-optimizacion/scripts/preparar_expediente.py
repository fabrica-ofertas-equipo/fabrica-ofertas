#!/usr/bin/env python3
"""preparar_expediente.py: arma el JSON de ENTRADA de D8 (métricas del día) leyendo la base SOLO en lectura.

v0.1 sin pulir (skill d8-optimizacion 0.1.0). Es un script de AYUDA para el Maker de D8: junta en un solo archivo las
cifras que el código ya tiene (gasto y entrega de Meta, ventas de Stripe, eventos de la landing) para que el Maker
las cite y para que ``proponer.py`` las evalúe. Ni calcula veredictos ni propone nada: solo cuenta y suma enteros.

Garantías (probadas en ``tests/skills_d8/``):
  * La base se abre con ``file:...?mode=ro`` y ``PRAGMA query_only = ON``: cualquier escritura falla.
  * No lee archivos de secretos ni claves, no usa la red, no llama a Meta ni a Stripe.
  * Sin ``float`` en la salida: dinero en enteros de unidad menor, fechas ISO, razones como enteros (bp) o minutos.
  * Si falta un dato, lo deja en ``null`` y lo anota en ``avisos`` (el que decide trata ``null`` como «no sé», nunca como 0).

Uso (desde la raíz del repositorio; la base real es ``empresa/datos/fabrica.db``, ver ``datos.etl_stripe``):
  .venv/bin/python .claude/skills/d8-optimizacion/scripts/preparar_expediente.py \
      --db empresa/datos/fabrica.db --oferta OF-202611-91 --fecha 2026-11-08 --raiz . --salida entrada.json
Salida: 0 correcto · 2 uso · 3 validación (argumentos o datos) · 4 bloqueado (falta la base o una tabla).
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

VERSION = "0.1.0"
ESTADOS_PAGADO = ("paid", "pagado")
ESTADOS_PENDIENTE = ("unpaid", "pending", "pendiente")
SIN_ATRIBUCION = ("", "desconocido")
# Estados de fact_disputa que cuentan como «abierta» (estados crudos de Stripe; [VERIFICAR] contra la documentación vigente).
ESTADOS_DISPUTA_ABIERTA = ("needs_response", "under_review", "warning_needs_response", "warning_under_review")
RX_OFERTA = re.compile(r"^OF-[0-9]{6}-[0-9]{2}$")
RX_FECHA = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class ErrorEntrada(Exception):
    """Error con código de salida del repositorio (3 validación, 4 bloqueado)."""

    def __init__(self, mensaje: str, codigo: int = 3) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


# ----------------------------------------------------------------------------------------------
# Tiempo
# ----------------------------------------------------------------------------------------------
def parsear_z(texto: str) -> datetime:
    """``2026-11-08T09:00:00Z`` (con o sin fracción) -> datetime consciente en UTC."""
    try:
        d = datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except ValueError as exc:
        raise ErrorEntrada(f"instante inválido: {texto!r}") from exc
    if d.tzinfo is None:
        raise ErrorEntrada(f"el instante debe llevar zona (Z): {texto!r}")
    return d.astimezone(timezone.utc)


def iso_z(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def zona(nombre: str) -> ZoneInfo:
    try:
        return ZoneInfo(nombre)
    except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
        raise ErrorEntrada(f"zona horaria desconocida: {nombre!r}") from exc


def dia_de_cuenta(ts_utc: str, z: ZoneInfo) -> str:
    """Día calendario (AAAA-MM-DD) de un instante UTC en la zona de la cuenta."""
    return parsear_z(ts_utc).astimezone(z).date().isoformat()


def fin_de_dia_utc(fecha: str, z: ZoneInfo) -> datetime:
    """Instante UTC en que termina el día de cuenta ``fecha`` (medianoche local del día siguiente)."""
    d = date.fromisoformat(fecha) + timedelta(days=1)
    return datetime(d.year, d.month, d.day, tzinfo=z).astimezone(timezone.utc)


# ----------------------------------------------------------------------------------------------
# Base en solo lectura
# ----------------------------------------------------------------------------------------------
def abrir_ro(ruta: Path) -> sqlite3.Connection:
    """Abre SQLite en solo lectura (URI ``mode=ro`` + ``query_only``). Cualquier INSERT/UPDATE/DELETE falla."""
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ErrorEntrada(f"no existe la base: {ruta}", 4)
    conn = sqlite3.connect(ruta.resolve().as_uri() + "?mode=ro", uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def _tabla_existe(conn: sqlite3.Connection, nombre: str) -> bool:
    fila = conn.execute("SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name = ?", (nombre,)).fetchone()
    return fila is not None


def _json_de(ruta: Path) -> dict | None:
    try:
        doc = json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def _dias(desde: str, hasta: str) -> list[str]:
    a, b = date.fromisoformat(desde), date.fromisoformat(hasta)
    return [(a + timedelta(days=i)).isoformat() for i in range((b - a).days + 1)]


def _con_adid(adid: str | None) -> bool:
    return adid is not None and str(adid).strip().lower() not in SIN_ATRIBUCION


# ----------------------------------------------------------------------------------------------
# Armado de la entrada
# ----------------------------------------------------------------------------------------------
def armar_entrada(
    conn: sqlite3.Connection, oferta_id: str, fecha: str, *, ahora: datetime, tz: str | None = None, dias: int = 14,
    raiz: Path | None = None,
) -> dict:
    """Devuelve el documento ``entrada_d8`` (ver ``templates/`` y ``references/protocolo-j3.md``)."""
    if not RX_OFERTA.match(oferta_id):
        raise ErrorEntrada(f"oferta_id inválido: {oferta_id!r}")
    if not RX_FECHA.match(fecha):
        raise ErrorEntrada(f"fecha inválida (AAAA-MM-DD): {fecha!r}")
    if dias < 1 or dias > 60:
        raise ErrorEntrada("--dias debe estar entre 1 y 60")
    for tabla in ("dim_anuncio", "fact_meta_ad_dia", "fact_pedido"):
        if not _tabla_existe(conn, tabla):
            raise ErrorEntrada(f"falta la tabla {tabla}: la base no tiene aplicadas las migraciones de datos/", 4)
    avisos: list[str] = []

    anuncios = conn.execute("SELECT ad_id, concepto_id FROM dim_anuncio WHERE oferta_id = ? ORDER BY ad_id", (oferta_id,)).fetchall()
    if not anuncios:
        avisos.append("la oferta no tiene anuncios en dim_anuncio")
    ids_oferta = {str(a[0]) for a in anuncios}

    # --- Meta: filas por anuncio y día hasta la fecha pedida (inclusive) ---
    filas_meta = conn.execute(
        "SELECT ad_id, fecha, gasto_minor, moneda, impresiones, clics_enlace, compras_meta, tz, ingerido_en, campaign_id "
        "FROM fact_meta_ad_dia WHERE oferta_id = ? AND fecha <= ? ORDER BY fecha, ad_id",
        (oferta_id, fecha),
    ).fetchall()

    # --- Zona horaria de la cuenta ---
    if tz is None:
        zonas = sorted({str(f[7]) for f in filas_meta if f[7]})
        if len(zonas) == 1:
            tz = zonas[0]
        elif len(zonas) > 1:
            raise ErrorEntrada(f"la oferta tiene filas de Meta en varias zonas horarias {zonas}: pasa --tz")
        else:
            tz = "UTC"
            avisos.append("tz_asumida_utc: sin filas de Meta ni --tz; el día de cuenta se calculó en UTC")
    z = zona(tz)
    fin_dia = fin_de_dia_utc(fecha, z)
    cerrado = fin_dia <= ahora
    desde = (date.fromisoformat(fecha) - timedelta(days=dias - 1)).isoformat()
    ventana = _dias(desde, fecha)

    monedas_meta = sorted({str(f[3]) for f in filas_meta if f[3]})
    if len(monedas_meta) > 1:
        avisos.append(f"monedas_meta_mezcladas: {monedas_meta}")
    moneda_meta = monedas_meta[0] if len(monedas_meta) == 1 else None

    # --- Stripe: pedidos reales (sin pruebas ni internos), con su día de cuenta ---
    pedidos = conn.execute(
        "SELECT checkout_session_id, adid, monto_minor, moneda, creado_ts, estado, ingerido_en FROM fact_pedido "
        "WHERE oferta_id = ? AND es_prueba = 0 AND es_interna = 0",
        (oferta_id,),
    ).fetchall()
    monedas_pedido = sorted({str(p[3]) for p in pedidos if p[3]})
    pedidos_dia: list[dict] = []
    for sid, adid, monto, mon, creado, estado, _ing in pedidos:
        d = dia_de_cuenta(creado, z)
        if d > fecha:
            continue
        pedidos_dia.append({"sid": str(sid), "adid": adid, "dia": d, "estado": str(estado), "moneda": mon})
    reembolsados: set[str] = set()
    if _tabla_existe(conn, "fact_reembolso"):
        reembolsados = {str(r[0]) for r in conn.execute(
            "SELECT DISTINCT checkout_session_id FROM fact_reembolso WHERE oferta_id = ? AND monto_minor > 0", (oferta_id,))}
    else:
        avisos.append("sin tabla fact_reembolso: no se cuentan reembolsos")

    # --- Eventos de la landing (primera parte) ---
    eventos: list[tuple[str, str, str, str | None]] = []
    hay_tabla_eventos = _tabla_existe(conn, "fact_evento")
    if hay_tabla_eventos:
        for tipo, visitante, ts, adid in conn.execute(
            "SELECT tipo, visitor_id, ts, adid FROM fact_evento WHERE oferta_id = ? AND tipo IN ('PageView','InitiateCheckout')",
            (oferta_id,),
        ):
            eventos.append((str(tipo), str(visitante), dia_de_cuenta(ts, z), adid))
    else:
        avisos.append("sin tabla fact_evento: vistas de landing e InitiateCheckout quedan en null")

    # --- Disputas abiertas (columna real: checkout_session_id) ---
    disputas_abiertas: int | None = None
    if _tabla_existe(conn, "fact_disputa"):
        marcas = ",".join("?" * len(ESTADOS_DISPUTA_ABIERTA))
        disputas_abiertas = int(conn.execute(
            f"SELECT COUNT(*) FROM fact_disputa WHERE oferta_id = ? AND estado IN ({marcas})",
            (oferta_id, *ESTADOS_DISPUTA_ABIERTA)).fetchone()[0])

    # --- Serie por día de la oferta y por anuncio ---
    def vacio_dia() -> dict:
        return {"gasto_minor": 0, "impresiones": 0, "clics_enlace": 0, "compras_meta": 0}

    serie = {d: vacio_dia() for d in ventana}
    por_anuncio = {a: {d: {**vacio_dia(), "ventas_stripe": 0, "ic": 0} for d in ventana} for a in sorted(ids_oferta)}
    primer_dia = None
    gasto_acumulado = 0
    for ad_id, f, gasto, _mon, impr, clics, cmeta, _tz, _ing, _cid in filas_meta:
        if gasto and gasto > 0 and (primer_dia is None or f < primer_dia):
            primer_dia = f
        gasto_acumulado += int(gasto)
        if f in serie:
            s = serie[f]
            s["gasto_minor"] += int(gasto)
            s["impresiones"] += int(impr)
            s["clics_enlace"] += int(clics)
            s["compras_meta"] += int(cmeta)
            if str(ad_id) in por_anuncio:
                a = por_anuncio[str(ad_id)][f]
                a["gasto_minor"] += int(gasto)
                a["impresiones"] += int(impr)
                a["clics_enlace"] += int(clics)
                a["compras_meta"] += int(cmeta)

    def ventas_de(dia_ini: str, dia_fin: str) -> dict:
        tot = atr = pen = 0
        for p in pedidos_dia:
            if not (dia_ini <= p["dia"] <= dia_fin):
                continue
            if p["estado"] in ESTADOS_PAGADO:
                tot += 1
                if _con_adid(p["adid"]) and str(p["adid"]) in ids_oferta:
                    atr += 1
            elif p["estado"] in ESTADOS_PENDIENTE:
                pen += 1
        return {"ventas_stripe_total": tot, "ventas_stripe_atribuidas": atr, "ventas_stripe_sin_atribucion": tot - atr,
                "pedidos_pendientes": pen}

    for p in pedidos_dia:
        if p["estado"] in ESTADOS_PAGADO and p["dia"] in ventana and _con_adid(p["adid"]) and str(p["adid"]) in por_anuncio:
            por_anuncio[str(p["adid"])][p["dia"]]["ventas_stripe"] += 1
    for tipo, _vis, d, adid in eventos:
        if tipo == "InitiateCheckout" and d in ventana and _con_adid(adid) and str(adid) in por_anuncio:
            por_anuncio[str(adid)][d]["ic"] += 1

    for d in ventana:
        serie[d].update(ventas_de(d, d))
        serie[d]["fecha"] = d

    # --- Día evaluado ---
    dia = {**serie[fecha], "cerrado": cerrado}
    ventas_con_reembolso = sum(1 for p in pedidos_dia if p["dia"] == fecha and p["estado"] in ESTADOS_PAGADO and p["sid"] in reembolsados)
    dia["ventas_con_reembolso"] = ventas_con_reembolso
    if hay_tabla_eventos:
        vis = {v for t, v, d, _a in eventos if t == "PageView" and d == fecha}
        vis_adid = {v for t, v, d, a in eventos if t == "PageView" and d == fecha and _con_adid(a)}
        ics = {v for t, v, d, _a in eventos if t == "InitiateCheckout" and d == fecha}
        dia["vistas_landing"], dia["vistas_landing_con_adid"], dia["initiate_checkout"] = len(vis), len(vis_adid), len(ics)
    else:
        dia["vistas_landing"] = dia["vistas_landing_con_adid"] = dia["initiate_checkout"] = None
    ult_meta_dia = [f[8] for f in filas_meta if f[1] == fecha]
    dia["ingesta_meta_posterior_al_cierre"] = (max(parsear_z(t) for t in ult_meta_dia) >= fin_dia) if ult_meta_dia else None
    dia["minutos_desde_cierre"] = int((ahora - fin_dia).total_seconds() // 60)

    # --- Acumulado desde el primer día con gasto ---
    if primer_dia is not None:
        acumulado = {"desde": primer_dia, "gasto_minor": gasto_acumulado, **ventas_de(primer_dia, fecha)}
        n_dias = (date.fromisoformat(fecha) - date.fromisoformat(primer_dia)).days + (1 if cerrado else 0)
    else:
        acumulado = {"desde": None, "gasto_minor": 0, "ventas_stripe_total": 0, "ventas_stripe_atribuidas": 0,
                     "ventas_stripe_sin_atribucion": 0, "pedidos_pendientes": 0}
        n_dias = 0

    # --- Cobertura de adid (puntos básicos) sobre pedidos pagados hasta la fecha ---
    pagados = [p for p in pedidos_dia if p["estado"] in ESTADOS_PAGADO]
    cobertura_bp = (sum(1 for p in pagados if _con_adid(p["adid"])) * 10000 // len(pagados)) if pagados else None

    # --- Frescura de lo ingerido ---
    def edad_min(ts: str | None) -> int | None:
        return None if ts is None else int((ahora - parsear_z(ts)).total_seconds() // 60)

    ult_meta = max((f[8] for f in filas_meta), default=None)
    ult_ped = max((p[6] for p in pedidos), default=None)

    # --- Contexto de archivos (solo lectura; null si no se pasó --raiz) ---
    contexto: dict = {"pausa_activa": None, "infra_semaforo": None, "traspaso_lanzamiento_estable": None, "pedidos_creativos_abiertos": None}
    presupuesto = None
    if raiz is not None:
        raiz = Path(raiz)
        contexto["pausa_activa"] = (raiz / "empresa" / "PAUSA").exists()
        infra = _json_de(raiz / "empresa" / "infra" / "estado.json")
        contexto["infra_semaforo"] = infra.get("semaforo") if infra else None
        base = raiz / "ofertas" / oferta_id
        tras = _json_de(base / "07-campana" / "traspaso.json")
        contexto["traspaso_lanzamiento_estable"] = tras.get("lanzamiento_estable") if tras and isinstance(tras.get("lanzamiento_estable"), bool) else None
        ruta_ped = base / "08-operacion" / "pedidos_creativos.json"
        if not ruta_ped.exists():
            contexto["pedidos_creativos_abiertos"] = 0  # nunca se pidió nada a D6
        else:
            ped = _json_de(ruta_ped)
            if ped is not None and isinstance(ped.get("pedidos"), list):
                contexto["pedidos_creativos_abiertos"] = sum(
                    1 for x in ped["pedidos"] if isinstance(x, dict) and x.get("estado") in ("abierto", "pendiente"))
            else:
                avisos.append("08-operacion/pedidos_creativos.json ilegible: los pedidos abiertos quedan en null")
        camp = _json_de(base / "07-campana" / "campana.json")
        pres = camp.get("presupuesto") if camp else None
        if isinstance(pres, dict) and isinstance(pres.get("diario"), int) and not isinstance(pres.get("diario"), bool):
            presupuesto = {"diario_minor": pres["diario"], "moneda": pres.get("moneda"), "fuente": f"ofertas/{oferta_id}/07-campana/campana.json:presupuesto.diario"}
        else:
            avisos.append("sin presupuesto diario legible en 07-campana/campana.json: el gasto cumplido no se puede evaluar")
    else:
        avisos.append("sin --raiz: PAUSA, estado de infra, traspaso y presupuesto quedan en null")
    if presupuesto and moneda_meta and presupuesto.get("moneda") and presupuesto["moneda"] != moneda_meta:
        avisos.append(f"moneda_presupuesto_distinta: campana.json {presupuesto['moneda']} vs Meta {moneda_meta}")

    return {
        "schema_version": VERSION,
        "tipo": "entrada_d8",
        "oferta_id": oferta_id,
        "fecha_cuenta": fecha,
        "tz": tz,
        "ahora": iso_z(ahora),
        "solo_lectura": True,
        "generado_por": f"preparar_expediente.py {VERSION}",
        "moneda_meta": moneda_meta,
        "monedas_pedido": monedas_pedido,
        "presupuesto": presupuesto,
        "contexto": contexto,
        "frescura": {
            "ultima_ingesta_meta_ts": ult_meta, "edad_ingesta_meta_min": edad_min(ult_meta),
            "ultima_ingesta_pedidos_ts": ult_ped, "edad_ingesta_pedidos_min": edad_min(ult_ped),
        },
        "campaign_ids": sorted({str(f[9]) for f in filas_meta if f[9]}),
        "primer_dia_con_gasto": primer_dia,
        "dias_cerrados_desde_primer_gasto": n_dias,
        "dia": dia,
        "acumulado": acumulado,
        "cobertura_adid_bp": cobertura_bp,
        "disputas_abiertas": disputas_abiertas,
        "serie_oferta": [serie[d] for d in ventana],
        "anuncios": [
            {"ad_id": str(a[0]), "concepto_id": a[1], "por_dia": por_anuncio[str(a[0])]} for a in anuncios
        ],
        "avisos": avisos,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Arma la entrada de D8 (métricas del día) leyendo la base en solo lectura.")
    ap.add_argument("--db", required=True, help="ruta de la base SQLite (real: empresa/datos/fabrica.db)")
    ap.add_argument("--oferta", required=True, help="oferta_id (OF-AAAAMM-NN)")
    ap.add_argument("--fecha", required=True, help="día de cuenta a evaluar (AAAA-MM-DD)")
    ap.add_argument("--ahora", default=None, help="instante UTC con Z (por defecto, ahora); fíjalo para repetir una corrida")
    ap.add_argument("--tz", default=None, help="zona IANA de la cuenta (por defecto, la de fact_meta_ad_dia)")
    ap.add_argument("--dias", type=int, default=14, help="días de serie hacia atrás, incluido --fecha (14 alcanza para fatiga 3 vs 7)")
    ap.add_argument("--raiz", default=None, help="raíz del repositorio (para PAUSA, infra, traspaso y campana.json)")
    ap.add_argument("--salida", default=None, help="archivo de salida (por defecto, stdout)")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        ahora = parsear_z(args.ahora) if args.ahora else datetime.now(timezone.utc).replace(microsecond=0)
        conn = abrir_ro(Path(args.db))
        try:
            doc = armar_entrada(conn, args.oferta, args.fecha, ahora=ahora, tz=args.tz, dias=args.dias,
                                raiz=Path(args.raiz) if args.raiz else None)
        finally:
            conn.close()
    except ErrorEntrada as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.codigo
    except sqlite3.Error as exc:
        print(f"ERROR de base de datos: {exc}", file=sys.stderr)
        return 4
    texto = json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.salida:
        Path(args.salida).write_text(texto, encoding="utf-8")
    else:
        sys.stdout.write(texto)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
