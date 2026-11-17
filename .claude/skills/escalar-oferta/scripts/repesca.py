#!/usr/bin/env python3
"""Repesca de carritos abandonados: decide QUÉ tiendas abrir en el panel de Impultienda para mandar «Envío masivo».

Pedido del dueño (2026-11-15): «hacelo con un 33 % y automatizalo para que ocurra en todas las ofertas que lanzamos de ahora
en más y las que están corriendo». La repesca la manda Impultienda (Ventas → Carritos abandonados → «Envío masivo»: un mail
en el idioma del comprador con un link de pago con el descuento, una sola vez por carrito). El conector no tiene esa acción,
así que la tarea programada «repesca-carritos» la hace con el navegador integrado, y este script es su filtro previo:

  pendientes [--json]          ¿hay trabajo? Lee la nube (vivo.tu-dominio.com/api/carritos: avisos order.abandoned y
                               order.rejected, sin datos del comprador) y el estado en ofertas/_funnels/repesca.json.
                               Imprime «NADA: …» o «TRABAJO: <tiendas>» (con --json, el detalle).
  marcar <tienda> --enviados N [--nota "…"]
                               anota que se hizo el Envío masivo en esa tienda (N = emails que el panel dijo que salieron).
  barrido-hecho                anota que se recorrieron TODAS las tiendas (barrido diario de respaldo).
  estado                       muestra el estado guardado.

Reglas:
- Tiendas de la fábrica = las del libro (ofertas/_funnels/libro-de-tests.json) cuyo test no está «cerrado» (las cerradas
  están archivadas en Impultienda). Nunca Tienda ajena B ni TiendaajenaA (no son de la fábrica). Una tienda que no está en el
  libro pero manda carritos también se abre (puede ser una tienda nueva que todavía no se anotó), salvo esas dos.
- Un carrito cuenta si llegó después del último Envío masivo de su tienda, no tiene una venta aprobada con la misma orden y,
  si es un pago rechazado, pasaron 30 minutos (el comprador suele reintentar con otra tarjeta).
- Barrido de respaldo: una vez por día, desde las 09:00 de Argentina, se abren todas las tiendas del libro aunque la nube no
  avise nada (por si un aviso no llegó).
- El descuento es descuento_pct del estado (33 % por pedido del dueño).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

RAIZ = Path(__file__).resolve().parents[4]
FUNNELS = RAIZ / "ofertas" / "_funnels"
LIBRO = FUNNELS / "libro-de-tests.json"
ESTADO = FUNNELS / "repesca.json"
URL = "https://vivo.tu-dominio.com/api/carritos"
CLAVE = Path.home() / ".config" / "fabrica-panel" / "vivo_lectura"
ART = ZoneInfo("America/Argentina/Buenos_Aires")
EXCLUIDAS = {"tienda-ajena-b", "tienda-ajena-a"}
ESPERA_RECHAZO = dt.timedelta(minutes=30)
HORA_BARRIDO = 9
DESCUENTO = 33


def ahora() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def iso(x: dt.datetime) -> str:
    return x.astimezone(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    try:
        d = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def leer_estado() -> dict:
    if ESTADO.exists():
        e = json.loads(ESTADO.read_text(encoding="utf-8"))
    else:
        e = {}
    e.setdefault("_leeme", "Estado de la repesca de carritos (tarea repesca-carritos, scripts/repesca.py). Lo escribe el script.")
    e.setdefault("descuento_pct", DESCUENTO)
    e.setdefault("desde", iso(ahora()))
    e.setdefault("tiendas", {})
    e.setdefault("ultimo_barrido", None)
    e.setdefault("envios", [])
    return e


def guardar_estado(e: dict) -> None:
    ESTADO.write_text(json.dumps(e, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def tiendas_del_libro() -> list[str]:
    if not LIBRO.exists():
        return []
    libro = json.loads(LIBRO.read_text(encoding="utf-8"))
    vistas: list[str] = []
    for t in libro.get("tests") or []:
        if (t.get("estado") or "") == "cerrado":
            continue
        for s in t.get("tienda") or []:
            if isinstance(s, str) and s and s not in EXCLUIDAS and s not in vistas:
                vistas.append(s)
    return vistas


def leer_nube(desde: str) -> dict:
    clave = CLAVE.read_text(encoding="utf-8").strip()
    req = urllib.request.Request(f"{URL}?desde={desde}", headers={"authorization": f"Bearer {clave}", "user-agent": "fabrica-repesca"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def decidir(estado: dict, nube: dict | None, libro: list[str], momento: dt.datetime) -> dict:
    """Puro: qué tiendas abrir y por qué."""
    aprobadas = set((nube or {}).get("aprobadas") or [])
    por_tienda: dict[str, list[dict]] = {}
    for c in (nube or {}).get("carritos") or []:
        t = c.get("tienda")
        if not t or t in EXCLUIDAS or c.get("orden_id") in aprobadas:
            continue
        llegado = parse(c.get("recibido")) or parse(c.get("creada"))
        if not llegado:
            continue
        ult = parse((estado["tiendas"].get(t) or {}).get("ultimo_envio")) or parse(estado.get("desde"))
        if ult and llegado <= ult:
            continue
        if c.get("evento") == "order.rejected" and momento - llegado < ESPERA_RECHAZO:
            continue
        por_tienda.setdefault(t, []).append({"orden": c.get("orden_id"), "evento": c.get("evento"), "llegado": iso(llegado)})

    local = momento.astimezone(ART)
    ult_barrido = parse(estado.get("ultimo_barrido"))
    barrido = local.hour >= HORA_BARRIDO and (ult_barrido is None or ult_barrido.astimezone(ART).date() < local.date())

    tiendas = list(por_tienda)
    if barrido:
        tiendas += [t for t in libro if t not in tiendas]
    return {"hay_trabajo": bool(tiendas), "tiendas": tiendas, "por_aviso": por_tienda, "barrido_diario": barrido,
            "descuento_pct": estado.get("descuento_pct", DESCUENTO)}


def cmd_pendientes(a) -> int:
    estado = leer_estado()
    if not ESTADO.exists():
        guardar_estado(estado)
    momento = ahora()
    desde = min([parse(v.get("ultimo_envio")) for v in estado["tiendas"].values() if parse(v.get("ultimo_envio"))]
                + [parse(estado["desde"]), momento - dt.timedelta(days=2)])
    error = None
    try:
        nube = leer_nube(iso(desde - dt.timedelta(minutes=5)))
    except Exception as e:  # sin nube: solo el barrido diario decide
        nube, error = None, f"{type(e).__name__}: {e}"
    d = decidir(estado, nube, tiendas_del_libro(), momento)
    d["error_nube"] = error
    if a.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return 0
    if not d["hay_trabajo"]:
        print(f"NADA: sin carritos nuevos{' (la nube no respondió: ' + error + ')' if error else ''}")
        return 0
    partes = []
    if d["por_aviso"]:
        partes.append("con carritos nuevos: " + ", ".join(f"{t} ({len(v)})" for t, v in d["por_aviso"].items()))
    if d["barrido_diario"]:
        partes.append("barrido diario de todas las tiendas del libro")
    print(f"TRABAJO: {d['descuento_pct']} % · " + " · ".join(partes) + " → " + ", ".join(d["tiendas"]))
    return 0


def cmd_marcar(a) -> int:
    estado = leer_estado()
    momento = iso(ahora())
    t = estado["tiendas"].setdefault(a.tienda, {})
    t["ultimo_envio"] = momento
    t["enviados_total"] = int(t.get("enviados_total") or 0) + int(a.enviados)
    estado["envios"].append({"cuando": momento, "tienda": a.tienda, "enviados": int(a.enviados),
                             "descuento_pct": estado.get("descuento_pct", DESCUENTO), "nota": a.nota})
    estado["envios"] = estado["envios"][-500:]
    guardar_estado(estado)
    print(f"ok: {a.tienda} · {a.enviados} enviados")
    return 0


def cmd_barrido(_a) -> int:
    estado = leer_estado()
    estado["ultimo_barrido"] = iso(ahora())
    guardar_estado(estado)
    print("ok: barrido diario anotado")
    return 0


def cmd_estado(_a) -> int:
    print(json.dumps(leer_estado(), ensure_ascii=False, indent=1))
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)
    x = s.add_parser("pendientes"); x.add_argument("--json", action="store_true"); x.set_defaults(f=cmd_pendientes)
    x = s.add_parser("marcar"); x.add_argument("tienda"); x.add_argument("--enviados", type=int, default=0)
    x.add_argument("--nota", default=None); x.set_defaults(f=cmd_marcar)
    x = s.add_parser("barrido-hecho"); x.set_defaults(f=cmd_barrido)
    x = s.add_parser("estado"); x.set_defaults(f=cmd_estado)
    a = p.parse_args(argv)
    return a.f(a)


if __name__ == "__main__":
    sys.exit(main())
