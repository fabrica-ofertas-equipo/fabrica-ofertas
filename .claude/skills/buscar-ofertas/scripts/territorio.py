"""Territorio de esta instalación: que dos fábricas no modelen la misma oferta ni busquen en el mismo orden.

Pedido del dueño (2026-11-14): compartir la fábrica con otra persona sin que las dos se topen con las mismas ofertas.
Dos piezas:

  1. Registro compartido de ofertas tomadas (worker «fabrica-registro», infra/workers/registro/). Antes de que una
     oferta entre al banco se reserva; antes de modelarla se confirma. El primero que la reserva se la queda; la otra
     instalación la ve «tomada» y la saltea. Solo viajan huellas sha256 de la clave de la oferta y del page_id del
     anunciante: el servidor no ve dominios, nombres ni páginas, y ninguna instalación ve qué tomó la otra.
  2. Orden propio del radar: con una «semilla» en empresa/instalacion.json, cada instalación recorre la cola de
     búsquedas en otro orden (factor 0,5-1,5 por búsqueda). Sin semilla el orden es el de siempre.

Sin empresa/instalacion.json (o sin registro_url) todo esto se apaga y el resto del sistema funciona igual.

empresa/instalacion.json:
  {"id": "principal", "semilla": null, "registro_url": "https://registro.<dominio>", "si_no_responde": "seguir"}
  si_no_responde: «seguir» (modela aunque el registro no conteste) o «esperar» (no modela sin confirmación).
Token: variable REGISTRO_TOKEN (entorno o .env) o ~/.config/fabrica/registro_token.

Uso (desde la raíz del proyecto; T=.claude/skills/buscar-ofertas/scripts/territorio.py):
  python3 $T estado                                  config, registro alcanzable y cuántas reservas propias hay en el banco
  python3 $T consultar --landing URL [--page-id N]   LIBRE | TOMADA (de otra instalación)
  python3 $T reservar --landing URL [--page-id N] --estado banco|modelando|lanzada
        imprime OK o TOMADA (código 2) o SIN_REGISTRO (código 3 si si_no_responde = esperar; 0 si seguir)
  python3 $T liberar --landing URL [--page-id N]     suelta una reserva propia (oferta descartada)
  python3 $T sincronizar                             reserva todo lo del banco y del historial de modelado (una vez al
                                                     instalar el registro, y cuando haga falta)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[3]
CONFIG = RAIZ / "empresa" / "instalacion.json"
BANCO = RAIZ / "empresa" / "barrido" / "banco" / "ofertas.json"
HISTORIAL = RAIZ / "ofertas" / "historial-modelado.json"
SCRIPTS_LANZAR = RAIZ / ".claude" / "skills" / "modelar-y-lanzar-oferta" / "scripts"
TIMEOUT = 12
LOTE = 200


# ── configuración ───────────────────────────────────────────────────────────
_CONFIG: dict | None = None


def config() -> dict:
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG
    try:
        c = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        c = {}
    c.setdefault("id", "principal")
    c.setdefault("semilla", None)
    c.setdefault("registro_url", None)
    c.setdefault("si_no_responde", "seguir")
    _CONFIG = c
    return c


def _token() -> str | None:
    if os.environ.get("REGISTRO_TOKEN"):
        return os.environ["REGISTRO_TOKEN"].strip()
    env = RAIZ / ".env"
    if env.is_file():
        for linea in env.read_text(encoding="utf-8").splitlines():
            if linea.startswith("REGISTRO_TOKEN=") and linea.split("=", 1)[1].strip():
                return linea.split("=", 1)[1].strip().strip('"').strip("'")
    archivo = Path.home() / ".config" / "fabrica" / "registro_token"
    if archivo.is_file():
        return archivo.read_text(encoding="utf-8").strip() or None
    return None


def activo() -> bool:
    return bool(config().get("registro_url")) and bool(_token())


# ── orden propio del radar ──────────────────────────────────────────────────
def factor(busqueda_id: str) -> float:
    """0,5-1,5 estable por (semilla, búsqueda). Sin semilla: 1 (el orden de siempre)."""
    semilla = config().get("semilla")
    if not semilla:
        return 1.0
    h = hashlib.sha256(f"{semilla}:{busqueda_id}".encode()).digest()
    return 0.5 + int.from_bytes(h[:4], "big") / 0xFFFFFFFF


# ── huellas ─────────────────────────────────────────────────────────────────
def huellas(clave: str | None, page_id: str | None = None) -> list[str]:
    """Huella de la oferta (clave del banco) y del anunciante (page_id). Cualquiera de las dos tomada bloquea."""
    out = []
    if clave:
        out.append(hashlib.sha256(f"fabrica-oferta:v1:{clave}".encode()).hexdigest())
    if page_id and str(page_id).isdigit():
        out.append(hashlib.sha256(f"fabrica-pagina:v1:{page_id}".encode()).hexdigest())
    return out


def clave_de_landing(landing: str, pagina: str = "") -> str:
    sys.path.insert(0, str(SCRIPTS_LANZAR))
    import banco_candidatos as bc  # noqa: E402  (misma clave que el banco)
    return bc.clave_de_landing(landing, pagina)


# ── red ─────────────────────────────────────────────────────────────────────
def _post(ruta: str, cuerpo: dict) -> dict | None:
    c, tok = config(), _token()
    if not c.get("registro_url") or not tok:
        return None
    req = urllib.request.Request(c["registro_url"].rstrip("/") + ruta, data=json.dumps(cuerpo).encode(), method="POST",
                                 headers={"content-type": "application/json", "authorization": f"Bearer {tok}",
                                          "user-agent": "fabrica-territorio/1"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            return json.loads(r.read().decode())
    except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:
        print(f"aviso: el registro no respondió ({e})", file=sys.stderr)
        return None


def consultar(hs: list[str]) -> set[str] | None:
    """Huellas tomadas por otra instalación; None si el registro está apagado o no respondió."""
    tomadas: set[str] = set()
    for i in range(0, len(hs), LOTE):
        r = _post("/consultar", {"huellas": hs[i:i + LOTE]})
        if r is None or "tomadas" not in r:
            return None
        tomadas.update(r["tomadas"])
    return tomadas


def reservar(items: list[tuple[str, str]]) -> dict[str, str] | None:
    """items: (huella, estado). Devuelve {huella: "ok"|"tomada"}; None si no respondió."""
    out: dict[str, str] = {}
    for i in range(0, len(items), LOTE):
        r = _post("/reservar", {"items": [{"huella": h, "estado": e} for h, e in items[i:i + LOTE]]})
        if r is None or "resultado" not in r:
            return None
        out.update(r["resultado"])
    return out


def filtrar_y_reservar(ofertas: list[dict]) -> set[str]:
    """Para el banco: ofertas = [{"clave", "page_id", "estado_banco"}]. Reserva las libres (banco, o lanzada si ya se usó)
    y devuelve las claves tomadas por otra instalación. Si el registro no está o no responde, no bloquea nada."""
    if not activo() or not ofertas:
        return set()
    items, de_quien = [], {}
    for o in ofertas:
        estado = "lanzada" if o.get("estado_banco") == "usada" else "banco"
        for h in huellas(o["clave"], o.get("page_id")):
            items.append((h, estado))
            de_quien[h] = o["clave"]
    res = reservar(items)
    if res is None:
        return set()
    tomadas = {de_quien[h] for h, r in res.items() if r == "tomada"}
    # si una de las dos huellas quedó tomada, la otra (que sí se reservó) se suelta para no acaparar
    sueltas = [h for h, r in res.items() if r == "ok" and de_quien[h] in tomadas]
    if sueltas:
        _post("/liberar", {"huellas": sueltas})
    return tomadas


# ── CLI ─────────────────────────────────────────────────────────────────────
def _hs_de_args(a) -> list[str]:
    clave = a.clave or (clave_de_landing(a.landing) if a.landing else None)
    hs = huellas(clave, a.page_id)
    if not hs:
        raise SystemExit("falta --landing, --clave o --page-id")
    return hs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("estado")
    for nombre in ("consultar", "reservar", "liberar"):
        p = sub.add_parser(nombre)
        p.add_argument("--landing"); p.add_argument("--clave"); p.add_argument("--page-id")
        if nombre == "reservar":
            p.add_argument("--estado", choices=["banco", "modelando", "lanzada"], required=True)
    sub.add_parser("sincronizar")
    a = ap.parse_args(argv)
    c = config()

    if a.cmd == "estado":
        print(f"instalación: {c['id']} · semilla: {'sí' if c.get('semilla') else 'no (orden de siempre)'} · "
              f"registro: {c.get('registro_url') or 'apagado'} · token: {'sí' if _token() else 'no'} · si no responde: {c['si_no_responde']}")
        if activo():
            print("registro:", "responde" if consultar([huellas("prueba-de-salud")[0]]) is not None else "NO responde")
        return 0

    if not activo():
        print("SIN_REGISTRO (no configurado)")
        return 0

    if a.cmd == "consultar":
        t = consultar(_hs_de_args(a))
        print("SIN_REGISTRO" if t is None else ("TOMADA" if t else "LIBRE"))
        return 0
    if a.cmd == "reservar":
        hs = _hs_de_args(a)
        res = reservar([(h, a.estado) for h in hs])
        if res is None:
            print("SIN_REGISTRO")
            return 3 if c["si_no_responde"] == "esperar" else 0
        if any(r == "tomada" for r in res.values()):
            sueltas = [h for h, r in res.items() if r == "ok"]
            if sueltas:
                _post("/liberar", {"huellas": sueltas})
            print("TOMADA: otra instalación ya tiene esta oferta; elegí la siguiente del banco")
            return 2
        print("OK")
        return 0
    if a.cmd == "liberar":
        r = _post("/liberar", {"huellas": _hs_de_args(a)})
        print("SIN_REGISTRO" if r is None else f"liberadas: {r.get('liberadas', 0)}")
        return 0
    if a.cmd == "sincronizar":
        banco = json.loads(BANCO.read_text(encoding="utf-8")) if BANCO.is_file() else {"ofertas": {}}
        filas = [{"clave": k, "page_id": o.get("page_id"), "estado_banco": o.get("estado")}
                 for k, o in banco.get("ofertas", {}).items() if o.get("estado") in ("disponible", "usada")]
        historial = json.loads(HISTORIAL.read_text(encoding="utf-8")) if HISTORIAL.is_file() else []
        extra = []
        for h in historial if isinstance(historial, list) else []:
            ref = str(h.get("referente") or "")
            m = re.search(r"\d{9,}", ref)
            pid = m.group(0) if m else None
            landing = h.get("landing_referente") or h.get("landing")
            if not landing:
                dom = re.search(r"\b([a-z0-9-]+\.)+[a-z]{2,}\b", ref.lower())
                landing = dom.group(0) if dom else None
            clave = clave_de_landing(landing) if landing else None
            if clave or pid:
                extra.append({"clave": clave, "page_id": pid, "estado_banco": "usada"})
        tomadas = filtrar_y_reservar([f for f in filas + extra if f["clave"]]) if filas or extra else set()
        sin_clave = [f for f in extra if not f["clave"] and f["page_id"]]
        if sin_clave:
            reservar([(huellas(None, f["page_id"])[0], "lanzada") for f in sin_clave])
        print(f"reservadas {len(filas)} del banco y {len(extra)} del historial; tomadas por otra instalación: {len(tomadas)}")
        for k in sorted(tomadas):
            print("  tomada:", k)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
