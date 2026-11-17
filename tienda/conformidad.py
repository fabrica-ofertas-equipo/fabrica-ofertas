"""Pruebas de conformidad de un adaptador de tienda: si pasan, la fábrica funciona con esa plataforma.

    python3 -m tienda.conformidad              # la plataforma activa
    python3 -m tienda.conformidad hotmart      # una en particular
    python3 -m tienda.conformidad --todas

Comprueba, sin red: que cubra las 15 operaciones del contrato, que las direcciones sean coherentes (la landing de una tienda
se reconoce como suya, una dirección ajena no), y que las respuestas reales guardadas en tienda/muestras/<plataforma>/ se
conviertan exactamente en la forma normal esperada. Sale con 0 si todo pasa.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import tienda
from tienda.contrato import OPERACIONES, VIAS, problemas_cobro, problemas_embudo, problemas_venta

MUESTRAS = Path(__file__).resolve().parent / "muestras"


def revisar(nombre: str) -> list[str]:
    fallas: list[str] = []
    try:
        t = tienda.cargar(nombre)
    except Exception as e:  # noqa: BLE001
        return [f"no carga el adaptador: {e}"]
    for op in OPERACIONES:
        try:
            c = t.como(op)
        except Exception as e:  # noqa: BLE001
            fallas.append(f"como({op}) falla: {e}")
            continue
        if not isinstance(c, dict) or c.get("via") not in VIAS:
            fallas.append(f"como({op}): «via» tiene que ser una de {sorted(VIAS)}")
        elif c["via"] != "no_aplica" and not (c.get("herramienta") or c.get("ruta") or c.get("pantalla")):
            fallas.append(f"como({op}): falta herramienta, ruta o pantalla")
    if not 0.5 <= t.neto_estimado() <= 1:
        fallas.append("neto_estimado fuera de 0,5-1")
    carpeta = MUESTRAS / nombre
    if not carpeta.is_dir():
        return fallas + [f"faltan muestras reales en tienda/muestras/{nombre}/"]
    urls = carpeta / "urls.json"
    if urls.is_file():
        u = json.loads(urls.read_text(encoding="utf-8"))
        try:
            if t.tienda_de_url(u["landing"]) != u["tienda"]:
                fallas.append(f"tienda_de_url no reconoce su propia landing ({u['landing']})")
            if t.tienda_de_url(t.url_landing(u["tienda"])) != u["tienda"]:
                fallas.append("url_landing y tienda_de_url no se corresponden")
            if t.tienda_de_url("https://ejemplo-ajeno.com/x") is not None:
                fallas.append("tienda_de_url acepta una dirección ajena")
            if not t.url_checkout(u["tienda"]).startswith("https://"):
                fallas.append("url_checkout no es https")
        except Exception as e:  # noqa: BLE001
            fallas.append(f"direcciones: {e}")
    else:
        fallas.append("falta urls.json")
    for archivo, metodo, validar in (("ventas", "ventas", None), ("estadisticas", "embudo", problemas_embudo), ("cobro", "cobro", problemas_cobro)):
        crudo, esperado = carpeta / f"{archivo}.json", carpeta / f"{archivo}.esperado.json"
        if not crudo.is_file():
            if archivo != "cobro":
                fallas.append(f"falta {archivo}.json")
            continue
        try:
            sale = getattr(t, metodo)(json.loads(crudo.read_text(encoding="utf-8")))
        except Exception as e:  # noqa: BLE001
            fallas.append(f"{metodo}() falla con la muestra: {e}")
            continue
        if metodo == "ventas":
            if not sale:
                fallas.append("ventas() no devolvió ninguna venta de la muestra")
            for v in sale:
                fallas += [f"venta {v.get('orden')}: {p}" for p in problemas_venta(v)]
        else:
            fallas += [f"{metodo}: {p}" for p in validar(sale)]
        if esperado.is_file() and sale != json.loads(esperado.read_text(encoding="utf-8")):
            fallas.append(f"{metodo}() no da lo esperado:\n    sale     {json.dumps(sale, ensure_ascii=False)[:300]}\n    esperado {esperado.read_text(encoding='utf-8')[:300]}")
    return fallas


def main(argv: list[str]) -> int:
    nombres = sorted(p.stem for p in (Path(__file__).parent / "adaptadores").glob("*.py") if p.stem not in ("__init__", "plantilla")) \
        if "--todas" in argv else [a for a in argv if not a.startswith("-")] or [tienda.configurada()]
    malo = 0
    for n in nombres:
        f = revisar(n)
        print(f"{'✔' if not f else '✖'} {n}" + ("" if not f else f": {len(f)} falla(s)"))
        for x in f:
            print("   -", x)
        malo += bool(f)
    return 1 if malo else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
