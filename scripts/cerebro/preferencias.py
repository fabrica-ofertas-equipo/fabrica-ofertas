#!/usr/bin/env python3
"""Lo que D6 (y las demás skills) leen de las preferencias del dueño. SOLO LECTURA (biblioteca estándar).

Una preferencia nace como PROPUESTA (una regla propuesta de categoría «pref» en la lista única, con la prueba de cada corrección) y solo RIGE cuando el dueño la
aprueba con sus palabras (``guardar_pendiente.py preferencia_resolver``, que escribe ``empresa/memoria/preferencias.jsonl``). Este lector devuelve únicamente las
aprobadas y vigentes (no revocadas, de autor «dueno»): una propuesta, una rechazada o una revocada NO aparece nunca. De las propuestas solo da el conteo.

Una preferencia es un CRITERIO con fecha, no una regla ni un límite: no pisa el compliance (X1), los límites, la regla J13 ni lo que diga una rúbrica. Si choca con
alguno de ellos, manda el otro y quien la lee lo anota en su informe.

Uso (desde la raíz del repositorio):
    .venv/bin/python scripts/cerebro/preferencias.py --etapa D6 [--oferta OF-AAAAMM-NN] [--texto] [--raiz R]
Salida: JSON (o texto con ``--texto``, listo para pegar en el contexto de un Maker). Código 0 siempre que la raíz exista; 2 = uso.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.cerebro import comun
except ImportError:                                  # ejecutado por ruta, no como paquete
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.cerebro import comun

ETAPAS_VALIDAS = frozenset({"M1", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "O0", "D0", "F1", "F2", "X1", "X2"})
MAX_PREFERENCIAS = 12      # cabe holgado en memoria.max_tokens_ficha (1.500)
AVISO = ("Son criterios del dueño con fecha, no reglas ni límites. Si una choca con el compliance (X1), los límites, la regla J13 (la idea se hereda, la forma se "
         "transforma, la expresión no se toca) o tu rúbrica, mandan estos y lo anotas en tu informe. No cites una preferencia como si fuera un hecho del mercado.")


def _ficha(o: dict[str, Any]) -> dict[str, Any]:
    instancias = o.get("instancias") if isinstance(o.get("instancias"), list) else []
    return {
        "id": o["id"], "desde": comun.corto(o.get("ts"), 10), "etapa": comun.corto(o.get("etapa"), 6), "alcance": comun.corto(o.get("alcance"), 12) or "etapa",
        "oferta_id": o.get("oferta_id") if isinstance(o.get("oferta_id"), str) and comun.RX_OFERTA.fullmatch(o["oferta_id"]) else None,
        "criterio": comun.corto(o.get("criterio"), 280), "correcciones": o.get("n_instancias") if isinstance(o.get("n_instancias"), int) else len(instancias),
        "respaldo": comun.corto(o.get("respaldo"), 10), "aprobada_con": comun.corto(o.get("cita"), 200), "propuesta": comun.corto(o.get("pul_id"), 20),
    }


def leer_preferencias(raiz: Path, etapa: str | None = None, oferta_id: str | None = None) -> dict[str, Any]:
    """Preferencias aprobadas y vigentes que aplican a ``etapa`` (y a ``oferta_id``, si se da; las de alcance «oferta» solo valen para su oferta)."""
    memoria = comun.cargar_memoria(raiz)
    propuestas = [e for e in memoria["pulido"] if e.get("tipo") == "regla_propuesta" and e.get("categoria") == "pref" and e.get("estado") != "resuelta"]
    resueltas = {o.get("pul_id") for o in memoria["preferencias"] if o.get("estado") in ("aprobada", "rechazada") and o.get("autor") == "dueno"}
    activas = []
    for o in comun.preferencias_vigentes(memoria["preferencias"]):
        if etapa and o.get("etapa") != etapa:
            continue
        if o.get("alcance") == "oferta" and (oferta_id is None or o.get("oferta_id") != oferta_id):
            continue
        activas.append(o)
    activas.sort(key=lambda o: (str(o.get("ts") or ""), str(o.get("id"))), reverse=True)
    return {
        "etapa": etapa, "oferta_id": oferta_id, "preferencias": [_ficha(o) for o in activas[:MAX_PREFERENCIAS]], "n": len(activas), "recortadas": max(0, len(activas) - MAX_PREFERENCIAS),
        "propuestas_sin_aprobar": sum(1 for e in propuestas if e.get("id") not in resueltas),
        "aviso": AVISO, "avisos": memoria["avisos"], "solo_lectura": True,
    }


def a_texto(r: dict[str, Any]) -> str:
    cabecera = f"Preferencias del dueño para {r['etapa'] or 'todas las etapas'}" + (f" (oferta {r['oferta_id']})" if r["oferta_id"] else "")
    if not r["preferencias"]:
        return f"{cabecera}: todavía no hay ninguna aprobada. No inventes ninguna.\n{r['aviso']}"
    lineas = [f"{cabecera} — {r['n']} aprobada(s):"]
    for p in r["preferencias"]:
        lineas.append(f"- [{p['id']} · desde {p['desde']} · {p['correcciones']} correcciones tuyas · alcance {p['alcance']}] {p['criterio']}")
    if r["recortadas"]:
        lineas.append(f"(y {r['recortadas']} más; pide la lista completa en JSON)")
    lineas.append(r["aviso"])
    return "\n".join(lineas)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="preferencias.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--raiz", default=None, help="raíz del repositorio (defecto: FABRICA_RAIZ o la carpeta del código)")
    ap.add_argument("--etapa", default=None, help="etapa que lee (D6, D5…); sin ella, todas")
    ap.add_argument("--oferta", default=None, help="oferta (OF-AAAAMM-NN) para incluir lo de alcance «oferta»")
    ap.add_argument("--texto", action="store_true", help="salida en texto en lugar de JSON")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code not in (0, None) else 0
    raiz = Path(args.raiz) if args.raiz else comun.raiz_por_defecto()
    if not raiz.is_dir() or (args.etapa is not None and args.etapa not in ETAPAS_VALIDAS) or (args.oferta is not None and not comun.RX_OFERTA.fullmatch(args.oferta)):
        print(json.dumps({"ok": False, "mensaje": "--raiz no es una carpeta, o --etapa / --oferta no tienen un valor válido."}, ensure_ascii=False), file=sys.stderr)
        return 2
    r = leer_preferencias(raiz, args.etapa, args.oferta)
    print(a_texto(r) if args.texto else json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
