"""En qué países corre la oferta ORIGINAL (el referente) de cada oferta nuestra: ahí no se pauta.

Pedido del dueño (2026-11-14): ver en el panel, con banderas, dónde corre el referente de cada oferta, para saber dónde
no hay que correrla (acompaña la réplica de las ganadoras a otros mercados e idiomas).

El dato vive en el libro de tests, por test: `ficha.referente_paises` =
  {"medido": "<fecha ISO con zona>", "metodo": "...", "paginas": [{"page_id": "...", "nombre": "..."}],
   "paises": {"GB": 47, "AU": 9}, "sin_anuncios": ["US", ...], "universo": <cuántos países se miraron>, "nota": "..."}
`paises` = anuncios ACTIVOS del referente que llegan a ese país (suma de sus páginas); `sin_anuncios` = países mirados
con 0. Un país que no está en ninguna de las dos listas no se midió. Lo leen el panel (Negocio), elegir_mercado.py
(`--oferta`) y la réplica (regla E6 de escalar-oferta).

Cómo se mide (conector `ads_library_search`, sin navegador): por cada página del referente,
`page_ids: [<page_id>]`, `ad_active_status: "ACTIVE"`, `limit: 1`, `countries: [...]` → `estimated_total_count`.
Se hace por mitades: se pregunta por todo el universo de una vez; si da 0, todos esos países quedan «sin anuncios»;
si no, se parte en dos (`mitades`) y se repite hasta llegar a países sueltos. Con 1-3 países con anuncios son
~10-20 consultas por página en vez de 93. (Un anuncio que apunta a varios países cuenta una vez por grupo: por eso el
número que vale es el del país suelto.)

Uso (desde la raíz; P=.claude/skills/buscar-ofertas/scripts/paises_referente.py):
  python3 $P plan                       ofertas con referente, sus páginas y la edad de la última medición
  python3 $P vencidas [--horas 20]      filtro previo: las que no se midieron nunca o hace más de N horas (fin en una línea si no hay)
  python3 $P universo [OFERTA]          los países a mirar, separados por coma (los 93 de elegir_mercado + país del referente + el nuestro)
  python3 $P mitades GB,AU,US,...       parte una lista en dos (una por renglón)
  python3 $P guardar OFERTA --archivo m.json   m = {"paginas": [...], "paises": {"GB": 47, "US": 0, ...}, "sin_anuncios": [...], "nota": ""}
  python3 $P excluir OFERTA             países donde corre el referente (uno por renglón); sale con 2 si nunca se midió
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
METODO = "Biblioteca de Anuncios (conector ads_library_search: page_ids + countries, solo activos, limit 1, por mitades)"
ZONA = dt.timezone(dt.timedelta(hours=-3))   # la de los informes del dueño (ART)


def _modulo(nombre: str, ruta: Path):
    spec = importlib.util.spec_from_file_location(nombre, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _libro_mod():
    return _modulo("libro", RAIZ / ".claude" / "skills" / "escalar-oferta" / "scripts" / "libro.py")


def paises_base() -> list[str]:
    """Los países donde podemos lanzar (los de elegir_mercado.py), en su orden."""
    try:
        em = _modulo("elegir_mercado", RAIZ / ".claude" / "skills" / "modelar-y-lanzar-oferta" / "scripts" / "elegir_mercado.py")
        return [p[0] for p in em.PAISES]
    except Exception:   # sin el archivo, al menos los mercados grandes
        return ["US", "GB", "CA", "AU", "MX", "BR", "ES", "FR", "DE", "IT", "PT", "PL", "NL", "BE", "AR", "CO", "CL", "PE"]


def leer_libro(ruta: Path = LIBRO) -> dict:
    return json.loads(ruta.read_text(encoding="utf-8"))


def paginas_de(ficha: dict) -> list[dict]:
    """Páginas del referente: las de la última medición y, si no hay, `ficha.referente.page_id(s)`."""
    rp = ficha.get("referente_paises") if isinstance(ficha.get("referente_paises"), dict) else {}
    pags = [p for p in rp.get("paginas") or [] if isinstance(p, dict) and str(p.get("page_id") or "").isdigit()]
    if pags:
        return pags
    ref = ficha.get("referente") if isinstance(ficha.get("referente"), dict) else {}
    ids = ref.get("page_ids") if isinstance(ref.get("page_ids"), list) else [ref.get("page_id")]
    return [{"page_id": str(i), "nombre": ref.get("nombre") or ""} for i in ids if str(i or "").isdigit()]


def ofertas(libro: dict) -> list[dict]:
    """Un renglón por oferta (no cerrada) del libro: nombre, mercado, páginas del referente y la medición guardada."""
    out, vistos = [], set()
    for t in libro.get("tests") or []:
        if not isinstance(t, dict) or str(t.get("estado", "")).lower() in ("cerrado", "cerrada"):
            continue
        nombre = t.get("oferta") or t.get("nombre")
        if not nombre or nombre in vistos:
            continue
        vistos.add(nombre)
        f = t.get("ficha") if isinstance(t.get("ficha"), dict) else {}
        ref = f.get("referente") if isinstance(f.get("referente"), dict) else {}
        out.append({"nombre": nombre, "mercado": t.get("mercado"), "estado": t.get("estado"), "pais_referente": ref.get("pais"),
                    "paginas": paginas_de(f), "medicion": f.get("referente_paises") if isinstance(f.get("referente_paises"), dict) else None})
    return out


def _fecha(s) -> dt.datetime | None:
    try:
        d = dt.datetime.fromisoformat(str(s))
        return d if d.tzinfo else d.replace(tzinfo=ZONA)
    except (TypeError, ValueError):
        return None


def horas_desde(medicion: dict | None, ahora: dt.datetime) -> float | None:
    d = _fecha((medicion or {}).get("medido"))
    return None if d is None else (ahora - d).total_seconds() / 3600


def universo(o: dict | None = None) -> list[str]:
    base = paises_base()
    extra = []
    if o:
        extra = [c for c in (o.get("pais_referente"), *re.split(r"[^A-Z]+", str(o.get("mercado") or "").upper())) if c]
    return list(dict.fromkeys([*base, *[c for c in extra if re.fullmatch(r"[A-Z]{2}", c)]]))


def normalizar(m: dict, ahora: dt.datetime) -> dict:
    """Valida y ordena una medición. Un país con 0 pasa a `sin_anuncios`; nada queda en las dos listas."""
    if not isinstance(m, dict):
        raise SystemExit("La medición tiene que ser un objeto JSON.")
    pags = [{"page_id": str(p.get("page_id")), "nombre": str(p.get("nombre") or "")[:120]}
            for p in m.get("paginas") or [] if isinstance(p, dict) and str(p.get("page_id") or "").isdigit()]
    if not pags:
        raise SystemExit("Falta al menos una página del referente con su page_id.")
    paises, sin = {}, set()
    for c, n in (m.get("paises") or {}).items():
        c = str(c).upper()
        if not re.fullmatch(r"[A-Z]{2}", c) or isinstance(n, bool) or not isinstance(n, (int, float)) or n < 0:
            raise SystemExit(f"País o conteo inválido: {c}={n!r}")
        if n > 0:
            paises[c] = int(n)
        else:
            sin.add(c)
    for c in m.get("sin_anuncios") or []:
        c = str(c).upper()
        if not re.fullmatch(r"[A-Z]{2}", c):
            raise SystemExit(f"País inválido en sin_anuncios: {c!r}")
        sin.add(c)
    sin -= set(paises)
    out = {"medido": m.get("medido") or ahora.isoformat(timespec="minutes"), "metodo": m.get("metodo") or METODO, "paginas": pags,
           "paises": dict(sorted(paises.items(), key=lambda kv: -kv[1])), "sin_anuncios": sorted(sin),
           "universo": len(paises) + len(sin)}
    if m.get("nota"):
        out["nota"] = str(m["nota"])[:300]
    return out


def excluir(o: dict) -> list[str] | None:
    med = o.get("medicion")
    if not med:
        return None
    return [c for c, n in (med.get("paises") or {}).items() if n]


def _buscar(libro: dict, nombre: str) -> dict:
    for o in ofertas(libro):
        if nombre == o["nombre"]:
            return o
    for t in libro.get("tests") or []:
        if nombre in (t.get("nombre"), t.get("oferta")):
            return next(o for o in ofertas(libro) if o["nombre"] == (t.get("oferta") or t.get("nombre")))
    raise SystemExit(f"No hay una oferta «{nombre}» en el libro.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    v = sub.add_parser("vencidas"); v.add_argument("--horas", type=float, default=20)
    u = sub.add_parser("universo"); u.add_argument("oferta", nargs="?")
    mi = sub.add_parser("mitades"); mi.add_argument("lista")
    g = sub.add_parser("guardar"); g.add_argument("oferta"); g.add_argument("--archivo", required=True)
    e = sub.add_parser("excluir"); e.add_argument("oferta")
    a = ap.parse_args(argv)
    ahora = dt.datetime.now(ZONA)

    if a.cmd == "mitades":
        cods = [c for c in re.split(r"[^A-Za-z]+", a.lista.upper()) if c]
        k = (len(cods) + 1) // 2
        print(",".join(cods[:k]))
        print(",".join(cods[k:]))
        return 0
    libro = leer_libro()
    if a.cmd == "plan":
        for o in ofertas(libro):
            h = horas_desde(o["medicion"], ahora)
            pags = ", ".join(f"{p['page_id']} ({p['nombre'] or 'sin nombre'})" for p in o["paginas"]) or "SIN PÁGINA: buscar el page_id del referente"
            corre = excluir(o)
            print(f"{o['nombre']} [{o['mercado']}, {o['estado']}] · páginas: {pags} · "
                  + ("sin medir" if h is None else f"medido hace {h:.0f} h · corre en {', '.join(corre) or 'ningún país mirado'}"))
        return 0
    if a.cmd == "vencidas":
        filas = [o for o in ofertas(libro) if o["paginas"] and ((h := horas_desde(o["medicion"], ahora)) is None or h > a.horas)]
        sin_pag = [o["nombre"] for o in ofertas(libro) if not o["paginas"]]
        if not filas:
            print(f"Países del referente al día (< {a.horas:.0f} h) en todas las ofertas." + (f" Sin página: {', '.join(sin_pag)}." if sin_pag else ""))
            return 0
        for o in filas:
            print(f"{o['nombre']}: {', '.join(p['page_id'] for p in o['paginas'])}")
        if sin_pag:
            print(f"Sin página del referente (no se puede medir): {', '.join(sin_pag)}")
        return 0
    if a.cmd == "universo":
        print(",".join(universo(_buscar(libro, a.oferta) if a.oferta else None)))
        return 0
    if a.cmd == "excluir":
        o = _buscar(libro, a.oferta)
        cods = excluir(o)
        if cods is None:
            print(f"«{o['nombre']}»: países del referente sin medir.", file=sys.stderr)
            return 2
        for c in cods:
            print(c)
        return 0
    if a.cmd == "guardar":
        o = _buscar(libro, a.oferta)
        med = normalizar(json.loads(Path(a.archivo).read_text(encoding="utf-8")), ahora)
        L = _libro_mod()

        def cambio(lb):
            for t in lb.get("tests") or []:
                if o["nombre"] in (t.get("oferta"), t.get("nombre")) and isinstance(t.get("ficha"), dict):
                    t["ficha"]["referente_paises"] = med
        L.modificar(cambio)
        corre = " · ".join(f"{c} {n}" for c, n in med["paises"].items()) or "ningún país mirado"
        print(f"«{o['nombre']}»: el referente corre en {corre}; {len(med['sin_anuncios'])} países sin anuncios. Guardado en el libro.")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
