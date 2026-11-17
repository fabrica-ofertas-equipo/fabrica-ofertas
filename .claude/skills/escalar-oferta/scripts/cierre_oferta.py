#!/usr/bin/env python3
"""Cierre de una oferta apagada: cuándo se cierra y qué tiendas de Impultienda se archivan (regla R15, sin red, solo el libro).

Pedido del dueño (2026-11-14): «agregar a la skill sistema o criterio de cuándo se apaga la campaña y la oferta en sí, también
archivar la tienda en Impultienda, para que solo queden las que están activas». Respuestas: «72 h después» y «cortes por regla y
a mano». Números en `ofertas/_funnels/reglas.json` → `cierre`.

Apagar y cerrar son dos pasos:
  1. APAGAR = pausar la campaña en Meta (R1 en el test, R4 y R4b después, o el dueño a mano). Lo hace la vigilancia en el momento.
  2. CERRAR = 72 h después del apagado, si nada lo frena: la oferta pasa a `estado: "cerrado"` y cada una de sus tiendas se
     archiva en Impultienda (Configuración → Zona de peligro → «Eliminar tienda», que archiva y se puede restaurar). Así en
     Impultienda y en el panel solo quedan las ofertas vivas, y el cupo de tiendas del plan se libera.

Qué apagados cierran (dueño, 14-nov): los cortes por regla (R1, R1b agotada, R4, R4b) y los apagados a mano del dueño.
NO cierran las pausas técnicas (anuncios rechazados, anunciante sin verificar, página caída, píxel): se anotan en `pausa_tecnica`
o con `apagado.tecnico: true` y la oferta queda pausada. Tampoco cierra una oferta con `cierre.no_archivar: true` (el dueño
pidió conservarla) ni una con una venta posterior al apagado (se avisa al dueño: reactivar es suyo, R12).

Si la fila del test no tiene `apagado` pero está pausada, se busca el último APAGAR de ese test en `vigilancia.jsonl`
(pasó con Oferta E el 14-nov). Sin ninguno de los dos, la decisión es SIN_MOTIVO: no se archiva y se avisa.

Una tienda que también figura en otro test que no está cerrado no se archiva (queda en `compartidas`).

Decisiones por test: CERRAR (tiendas a archivar) · ESPERA (hasta cuándo) · RETENER (venta tardía, no_archivar) ·
TECNICA · SIN_MOTIVO · ACTIVA (no está apagada) · CERRADA (ya cerrada).

Uso (desde la raíz; C=.claude/skills/escalar-oferta/scripts/cierre_oferta.py):
  python3 $C                             una línea por test apagado; código 0
  python3 $C --json                      detalle
  python3 $C --ahora 2026-11-17T12:00-03:00   para pruebas
  python3 $C --registrar "<test>" --archivadas '[{"slug": "...", "store_id": "...", "subdominio_archivo": "...", "archivada": "<ISO>"}]'
                                         deja el test en «cerrado» con su `cierre` (por libro.py, con candado)
  python3 $C --probar                    casos de prueba
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reglas import valor  # noqa: E402

RAIZ = Path(__file__).resolve().parents[4]
LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
HORAS_ESPERA = float(valor("cierre.horas_espera", 72))
APAGADOS = ("pausado", "pausada", "apagado", "apagada")
CERRADOS = ("cerrado", "cerrada")


def _fecha(x):
    if not isinstance(x, str) or not x:
        return None
    try:
        d = dt.datetime.fromisoformat(x.replace("Z", "+00:00"))
    except ValueError:
        try:
            d = dt.datetime.fromisoformat(x[:10])
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)


def _nombre(t: dict) -> str:
    return str(t.get("nombre") or t.get("oferta") or "?")


def tiendas_del_test(t: dict) -> list[dict]:
    """Slugs (y store_id si la ficha lo tiene) de todas las tiendas del test: principal, niveles y subida previa."""
    out: dict[str, dict] = {}
    for x in (t.get("ficha") or {}).get("tiendas") or []:
        if isinstance(x, dict) and x.get("slug"):
            out[x["slug"]] = {"slug": x["slug"], "store_id": x.get("store_id"), "nombre": x.get("nombre")}
    tienda = t.get("tienda")
    for s in (tienda if isinstance(tienda, list) else [tienda] if tienda else []):
        if isinstance(s, str):
            out.setdefault(s, {"slug": s, "store_id": None, "nombre": None})
    return list(out.values())


def apagados_en_vigilancia(carpeta: Path) -> dict[str, dict]:
    """Último APAGAR de cada test en vigilancia.jsonl: {test: {cuando, regla, gasto_usd, ventas, corte_usd}}."""
    out: dict[str, dict] = {}
    try:
        lineas = (carpeta / "vigilancia.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        return out
    for ln in lineas:
        try:
            v = json.loads(ln)
        except ValueError:
            continue
        for r in v.get("tests") or [] if isinstance(v, dict) else []:
            if isinstance(r, dict) and r.get("decision") == "APAGAR":
                out[str(r.get("test"))] = {"cuando": v.get("leido"), "regla": "R1: corte del test (vigilancia.jsonl)",
                                           "gasto_usd": r.get("gasto_usd"), "ventas": r.get("ventas"), "corte_usd": r.get("corte_usd"),
                                           "fuente": "vigilancia.jsonl"}
    return out


def es_tecnica(t: dict, apagado: dict | None) -> bool:
    if t.get("pausa_tecnica"):
        return True
    if isinstance(apagado, dict) and (apagado.get("tecnico") is True or str(apagado.get("tipo", "")).lower() == "tecnica"):
        return True
    return False


def ventas_tardias(t: dict, cuando: dt.datetime) -> list[dict]:
    """Ventas con fecha posterior al apagado. Las ventas del libro traen solo el día: el mismo día del apagado no cuenta como
    tardía (la vigilancia ya la confirmó en Impul Pay antes de apagar); el agente mira la hora exacta en Impultienda."""
    out = []
    dia = cuando.date()
    for v in t.get("ventas") or []:
        if not isinstance(v, dict):
            continue
        f = _fecha(v.get("hora") or v.get("fecha"))
        if f is None:
            continue
        tardia = f > cuando if (v.get("hora") or "T" in str(v.get("fecha") or "")) else f.date() > dia
        if tardia:
            out.append({"orden": v.get("orden"), "fecha": v.get("hora") or v.get("fecha"), "tienda": v.get("tienda"), "tipo": v.get("tipo")})
    return out


def evaluar(libro: dict, ahora: dt.datetime, carpeta: Path) -> list[dict]:
    tests = [t for t in libro.get("tests") or [] if isinstance(t, dict)]
    vig = apagados_en_vigilancia(carpeta)
    # tiendas usadas por tests que siguen vivos (no cerrados): esas no se archivan
    vivas: dict[str, list[str]] = {}
    for t in tests:
        if str(t.get("estado") or "").lower() not in CERRADOS:
            for x in tiendas_del_test(t):
                vivas.setdefault(x["slug"], []).append(_nombre(t))
    out = []
    for t in tests:
        n = _nombre(t)
        estado = str(t.get("estado") or "").lower()
        cierre = t.get("cierre") if isinstance(t.get("cierre"), dict) else {}
        r = {"test": n, "estado": estado, "tiendas": tiendas_del_test(t)}
        if estado in CERRADOS:
            out.append({**r, "decision": "CERRADA", "porque": f"cerrada el {cierre.get('cuando') or '?'}"})
            continue
        apagado = t.get("apagado") if isinstance(t.get("apagado"), dict) else None
        if estado not in APAGADOS and not apagado:
            out.append({**r, "decision": "ACTIVA", "porque": "la campaña no está apagada"})
            continue
        if apagado is None and n in vig:
            apagado = vig[n]
        if es_tecnica(t, apagado):
            out.append({**r, "decision": "TECNICA", "porque": "pausa técnica: no se cierra (se arregla y se reactiva)", "apagado": apagado})
            continue
        cuando = _fecha((apagado or {}).get("cuando"))
        if apagado is None or cuando is None:
            out.append({**r, "decision": "SIN_MOTIVO", "porque": "pausada sin apagado registrado (ni en el libro ni en vigilancia.jsonl): "
                        "anotar el motivo con libro.py o avisar al dueño; no se archiva", "apagado": apagado})
            continue
        r["apagado"] = {**apagado, "cuando": apagado.get("cuando")}
        if cierre.get("no_archivar"):
            out.append({**r, "decision": "RETENER", "porque": f"el dueño pidió conservarla ({cierre.get('no_archivar')})"})
            continue
        tard = ventas_tardias(t, cuando)
        if tard:
            out.append({**r, "decision": "RETENER", "ventas_tardias": tard,
                        "porque": f"{len(tard)} venta(s) después del apagado: avisar al dueño (reactivar es suyo, R12); no se archiva"})
            continue
        listo = cuando + dt.timedelta(hours=HORAS_ESPERA)
        if ahora < listo:
            out.append({**r, "decision": "ESPERA", "hasta": listo.isoformat(timespec="minutes"),
                        "porque": f"apagada el {cuando.isoformat(timespec='minutes')}; se cierra a las {HORAS_ESPERA:g} h"})
            continue
        ya = {x.get("slug") for x in cierre.get("tiendas_archivadas") or [] if isinstance(x, dict)}
        compartidas = [x["slug"] for x in r["tiendas"] if any(o != n for o in vivas.get(x["slug"], []))]
        archivar = [x for x in r["tiendas"] if x["slug"] not in ya and x["slug"] not in compartidas]
        out.append({**r, "decision": "CERRAR", "archivar": archivar, "compartidas": compartidas, "ya_archivadas": sorted(ya - {None}),
                    "porque": f"apagada hace {(ahora - cuando).total_seconds() / 3600:.0f} h ({apagado.get('regla') or apagado.get('por') or 'corte'}); "
                              f"archivar {len(archivar)} tienda(s)"})
    return out


def registrar(test: str, archivadas: list[dict], ahora: dt.datetime) -> None:
    import libro as L  # noqa: PLC0415  (mismo directorio; escribe con candado)

    def cambio(lib):
        t = L._test(lib, test)
        if str(t.get("estado") or "").lower() in CERRADOS:
            raise SystemExit(f"«{test}» ya está cerrada.")
        cierre = t.get("cierre") if isinstance(t.get("cierre"), dict) else {}
        previas = [x for x in cierre.get("tiendas_archivadas") or [] if isinstance(x, dict)]
        slugs = {x.get("slug") for x in previas}
        previas += [x for x in archivadas if x.get("slug") not in slugs]
        t["cierre"] = {**cierre, "cuando": ahora.isoformat(timespec="minutes"), "regla": "R15: cierre 72 h después del apagado",
                       "tiendas_archivadas": previas}
        t["estado"] = "cerrado"
        t["estado_desde"] = ahora.isoformat(timespec="minutes")
        t["programado"] = None
    L.modificar(cambio)


def linea(r: dict) -> str:
    d = r["decision"]
    if d == "CERRAR":
        extra = f" · compartidas (no se tocan): {', '.join(r['compartidas'])}" if r["compartidas"] else ""
        ya = f" · ya archivadas: {', '.join(r['ya_archivadas'])}" if r["ya_archivadas"] else ""
        return f"CERRAR {r['test']}: archivar {', '.join(x['slug'] for x in r['archivar']) or '(ninguna)'}{ya}{extra} · {r['porque']}"
    if d == "ESPERA":
        return f"ESPERA {r['test']}: se cierra desde {r['hasta']}"
    return f"{d} {r['test']}: {r['porque']}"


def _probar() -> int:
    ahora = _fecha("2026-11-17T12:00-03:00")
    base = {"ficha": {"tiendas": [{"slug": "a"}, {"slug": "a-nivel"}]}, "tienda": ["a"]}
    casos = [
        ("corte R1 hace 74 h", {**base, "nombre": "T1", "estado": "pausado", "apagado": {"cuando": "2026-11-14T10:00-03:00", "regla": "R1"}}, "CERRAR"),
        ("corte hace 10 h", {**base, "nombre": "T2", "estado": "pausado", "apagado": {"cuando": "2026-11-17T02:00-03:00"}}, "ESPERA"),
        ("pausa técnica", {**base, "nombre": "T3", "estado": "pausado", "pausa_tecnica": {"motivo": "anunciante sin verificar"}}, "TECNICA"),
        ("venta tardía", {**base, "nombre": "T4", "estado": "pausado", "apagado": {"cuando": "2026-11-13T10:00-03:00"},
                          "ventas": [{"orden": "1", "fecha": "2026-11-15"}]}, "RETENER"),
        ("venta del mismo día", {**base, "nombre": "T5", "estado": "pausado", "apagado": {"cuando": "2026-11-13T10:00-03:00"},
                                 "ventas": [{"orden": "1", "fecha": "2026-11-13"}]}, "CERRAR"),
        ("sin motivo", {**base, "nombre": "T6", "estado": "pausado"}, "SIN_MOTIVO"),
        ("activa", {**base, "nombre": "T7", "estado": "activo"}, "ACTIVA"),
        ("ya cerrada", {**base, "nombre": "T8", "estado": "cerrado", "cierre": {"cuando": "2026-11-16"}}, "CERRADA"),
        ("no archivar", {**base, "nombre": "T9", "estado": "pausado", "apagado": {"cuando": "2026-11-13T10:00-03:00"},
                         "cierre": {"no_archivar": "dueño 15-nov"}}, "RETENER"),
        ("a mano del dueño", {**base, "nombre": "T10", "estado": "pausado", "apagado": {"cuando": "2026-11-14T08:00-03:00", "por": "dueño (a mano)"}}, "CERRAR"),
    ]
    fallas = 0
    for desc, t, esperado in casos:
        r = evaluar({"tests": [t]}, ahora, Path("/nonexistent"))[0]
        ok = r["decision"] == esperado
        fallas += not ok
        print(f"{'ok ' if ok else 'MAL'} {desc}: {r['decision']} (esperado {esperado})")
    # tienda compartida con un test vivo
    vivo = {"nombre": "Vivo", "estado": "activo", "ficha": {"tiendas": [{"slug": "a-nivel"}]}}
    r = evaluar({"tests": [{**base, "nombre": "T11", "estado": "pausado", "apagado": {"cuando": "2026-11-13T10:00-03:00"}}, vivo]}, ahora, Path("/x"))[0]
    ok = r["decision"] == "CERRAR" and r["compartidas"] == ["a-nivel"] and [x["slug"] for x in r["archivar"]] == ["a"]
    fallas += not ok
    print(f"{'ok ' if ok else 'MAL'} tienda compartida con un test vivo: archivar {[x['slug'] for x in r['archivar']]}, compartidas {r['compartidas']}")
    print("TODO OK" if not fallas else f"{fallas} FALLA(S)")
    return 1 if fallas else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--libro", default=str(LIBRO))
    ap.add_argument("--ahora")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--todas", action="store_true", help="incluir ACTIVA y CERRADA en la salida")
    ap.add_argument("--registrar", metavar="TEST")
    ap.add_argument("--archivadas", default="[]", help="JSON: tiendas archivadas en Impultienda (con --registrar)")
    ap.add_argument("--probar", action="store_true")
    a = ap.parse_args(argv)
    if a.probar:
        return _probar()
    ahora = _fecha(a.ahora) if a.ahora else dt.datetime.now(dt.timezone.utc).astimezone()
    if a.registrar:
        arch = json.loads(a.archivadas)
        if not isinstance(arch, list):
            raise SystemExit("--archivadas tiene que ser una lista JSON.")
        registrar(a.registrar, arch, ahora)
        print(f"CERRADA {a.registrar}: {len(arch)} tienda(s) archivada(s) registradas")
        return 0
    ruta = Path(a.libro)
    res = evaluar(json.loads(ruta.read_text(encoding="utf-8")), ahora, ruta.parent)
    if not a.todas:
        res = [r for r in res if r["decision"] not in ("ACTIVA", "CERRADA")]
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        print("\n".join(linea(r) for r in res) or "NADA: ninguna oferta apagada por cerrar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
