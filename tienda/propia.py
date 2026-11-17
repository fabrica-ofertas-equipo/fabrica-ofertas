"""Comandos de la tienda propia (adaptador «propia»): hablan con la API del worker fabrica-tienda.

    python3 -m tienda.propia publicar --tienda mi-guia --nombre "Mi guía" --precio 19 --precio-original 55 --html landing.html
    python3 -m tienda.propia ventas --tienda mi-guia --desde 2026-11-17 --hasta 2026-11-17
    python3 -m tienda.propia estadisticas --tienda mi-guia --fecha 2026-11-17
    python3 -m tienda.propia tiendas | cobro | carritos --tienda x | repesca [--tienda x]

Lee FABRICA_TIENDA_URL y FABRICA_TIENDA_TOKEN del entorno o del .env de la raíz. Imprime JSON.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]


def _env(clave: str) -> str:
    if os.environ.get(clave):
        return os.environ[clave]
    f = RAIZ / ".env"
    if f.is_file():
        for linea in f.read_text(encoding="utf-8").splitlines():
            if linea.startswith(clave + "="):
                return linea.split("=", 1)[1].strip().strip('"')
    return ""


def llamar(metodo: str, ruta: str, cuerpo: dict | None = None, query: dict | None = None) -> dict:
    base, token = _env("FABRICA_TIENDA_URL").rstrip("/"), _env("FABRICA_TIENDA_TOKEN")
    if not base or not token:
        raise SystemExit("faltan FABRICA_TIENDA_URL y FABRICA_TIENDA_TOKEN (ver skill conectar-tienda)")
    url = f"{base}/api/{ruta}" + ("?" + urllib.parse.urlencode({k: v for k, v in (query or {}).items() if v is not None}) if query else "")
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    req = urllib.request.Request(url, data=datos, method=metodo, headers={"authorization": f"Bearer {token}", "content-type": "application/json",
                                                                         "user-agent": "fabrica-tienda"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"ok": False, "status": e.code, "detalle": e.read().decode(errors="replace")[:300]}


def cuerpo_publicar(a: argparse.Namespace) -> dict:
    d: dict = {}
    for campo, valor in (("nombre", a.nombre), ("precio", a.precio), ("precio_original", a.precio_original), ("moneda", a.moneda),
                         ("idioma", a.idioma), ("entregable_url", a.entregable), ("pixel", a.pixel), ("correo_soporte", a.soporte)):
        if valor is not None:
            d[campo] = valor
    if a.html:
        d["html"] = Path(a.html).read_text(encoding="utf-8")
    if a.bump_nombre:
        d["bump"] = {"nombre": a.bump_nombre, "precio": a.bump_precio, "entregable_url": a.bump_entregable}
    if a.archivar:
        d["archivada"] = 1
    return d


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("publicar")
    p.add_argument("--tienda", required=True)
    for k in ("--nombre", "--moneda", "--idioma", "--html", "--entregable", "--pixel", "--soporte", "--bump-nombre", "--bump-entregable"):
        p.add_argument(k)
    for k in ("--precio", "--precio-original", "--bump-precio"):
        p.add_argument(k, type=float)
    p.add_argument("--archivar", action="store_true")
    for nombre in ("ventas", "estadisticas", "carritos", "repesca"):
        s = sub.add_parser(nombre)
        s.add_argument("--tienda")
        s.add_argument("--desde")
        s.add_argument("--hasta")
        s.add_argument("--fecha")
    sub.add_parser("tiendas")
    sub.add_parser("cobro")
    a = ap.parse_args(argv)
    if a.cmd == "publicar":
        r = llamar("PUT", f"tiendas/{a.tienda}", cuerpo_publicar(a))
    elif a.cmd == "repesca":
        r = llamar("POST", "repesca", {}, {"tienda": a.tienda})
    elif a.cmd in ("tiendas", "cobro"):
        r = llamar("GET", a.cmd)
    else:
        r = llamar("GET", a.cmd, query={"tienda": a.tienda, "desde": a.desde, "hasta": a.hasta, "fecha": a.fecha})
    print(json.dumps(r, ensure_ascii=False, indent=1))
    return 0 if r.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
