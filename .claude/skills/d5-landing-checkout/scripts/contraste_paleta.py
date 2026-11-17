#!/usr/bin/env python3
"""Comprobación determinista de `paleta.json` de D5 (check C12). Sin red, solo biblioteca estándar.

Uso:
    python3 contraste_paleta.py --paleta ofertas/<id>/05-landing/paleta.json [--json]

Qué verifica (todo reproducible):
  1. Cada color de `colores` tiene HEX válido (#RRGGBB) y un `motivo` con contenido.
  2. Existen los tokens mínimos (TOKENS_MIN).
  3. Cada par de `pares_contraste` cumple la razón de contraste WCAG 2.x (fórmula de luminancia relativa).
     Mínimo exigido: 4.5 para texto normal y botones; 3.0 para texto grande, líneas y foco.
     La clave de parámetros propuesta es `landing.contraste_min` [PENDIENTE: no existe en empresa/parametros.yaml].
  4. La paleta NO reutiliza los HEX de la landing de referencia (exactos o casi iguales) y no cae toda en su
     familia cromática (calidez terracota/arena). Referencia: docs/fuente/landing-ganadora-base.html.

Salida: JSON con `hallazgos[]` ({check_id, regla, severidad, detalle}); código 0 sin MAYOR/BLOQUEANTE,
3 con ellos, 2 por uso incorrecto. Las severidades siguen backbone 5.4.
"""
from __future__ import annotations

import argparse
import colorsys
import json
import re
import sys
from pathlib import Path
from typing import Any

TOKENS_MIN = (
    "fondo_claro", "fondo_oscuro", "superficie", "texto_sobre_claro", "texto_sobre_oscuro",
    "acento", "cta_fondo", "cta_texto", "linea", "foco",
)
USOS_4_5 = {"cuerpo", "boton", "enlace", "etiqueta"}
RX_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Todos los HEX de seis dígitos de docs/fuente/landing-ganadora-base.html (217, en mayúsculas, sin '#').
_BASE = (
    "0B0B0C 110F0D 14120F 15120F 171411 171512 1B120F 1C1713 1D1411 1D1814 1F1A16 201511 211713 "
    "211E19 22C55E 241914 241E18 261F19 291C17 2A1C17 2A251F 2B1E18 2B211C 2B2721 2E2922 2F211B "
    "2F241E 30251F 30271F 33231C 33251E 332822 342820 342821 34291F 352F27 3A281F 3B281F 3D332D "
    "46513D 4A382E 4A392F 4B3026 4D4038 4E4139 4F5D45 514137 59493F 5E6B50 5F6C52 63554B 65564D "
    "66584E 665C4F 667455 6B4636 6B4A3A 6F513E 6F6056 6F625A 6F6354 6F8060 716553 71805F 74665D "
    "75655A 756858 76675D 77665A 77675C 7A675A 7C5A43 7C896A 7C8B65 806F63 829177 837267 857469 "
    "877468 887568 8A6F5C 8A7466 8A786B 8B786B 8E4F37 8E806F 8F4F34 8F5137 907B69 98573E 9A4C31 "
    "9A887B 9B897C 9C593C 9D5A40 9E8A7D 9F5B3F 9F8A7B A15F43 A85E41 A88B6A A95637 A95738 A99384 "
    "A99582 AF9A8B B5D7B9 B66D4C B85C55 B86643 B86F4B B8A28F BBAE9C BDA99A BDA99B C97550 C97852 "
    "C97853 CDB9AA CDB9AC CDBCB0 CDBEAE CEB99A CEBCAF CF8460 D28A61 D2C1B5 D58A64 D58B62 D58C68 "
    "D5BE9A D5C5B9 D6BEA8 D8C5B4 D98F67 D99A72 E0D4C6 E3A17B E4A07A E4AF88 E4D4C5 E5A27C E5D7CD "
    "E5D8CF E7A27A E7D9CB E7DCCE E8D8C9 E8D8CB E9D8C8 E9D9C4 E9DCCB E9DDD2 EADCCD EADCCE EADDD3 "
    "EADFCE EADFD1 EBC47F EBDDD3 EEE2D5 EF4444 EFE2CF EFE3D6 EFE3D8 EFE4D9 EFE5DB F0B18A F0C6A6 "
    "F0E4D7 F0E5DA F0E7DC F0E7DE F1B48D F1C5AA F1E6D9 F1E6DC F1E7DB F1E7DF F2C7A6 F2E4D8 F2E8DE "
    "F3E8DC F3E9DF F4D7CF F4E9D8 F5C2C2 F5ECE3 F6ECE3 F6ECE4 F6EEE7 F7ECDD F7EFE7 F7F0E8 F7F2EB "
    "F7F2EC F8F1E7 F8F1E9 F8F2EA F8F2EC F8F3EC F8F3ED F8F4EE F9F4EE F9F5EF F9F5F0 FAF6F0 FAF6F1 "
    "FBF7F1 FBF7F2 FBF8F4 FFF1DE FFF8ED FFF9F4 FFFCF8 FFFDF9 FFFFFF "
)
HEX_BASE = frozenset("#" + h for h in _BASE.split())
NEUTROS_PUROS = frozenset({"#FFFFFF", "#000000"})  # blanco y negro puros no cuentan como «color de la base»
DIST_CASI_IGUAL = 6  # distancia euclídea RGB (0-255) por debajo de la cual se considera «casi igual» [HIPÓTESIS]


def _rgb(hexa: str) -> tuple[int, int, int]:
    return int(hexa[1:3], 16), int(hexa[3:5], 16), int(hexa[5:7], 16)


def luminancia(hexa: str) -> float:
    def canal(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(c) for c in _rgb(hexa))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def razon_contraste(a: str, b: str) -> float:
    la, lb = luminancia(a), luminancia(b)
    claro, oscuro = max(la, lb), min(la, lb)
    return (claro + 0.05) / (oscuro + 0.05)


def _distancia(a: str, b: str) -> float:
    ra, rb = _rgb(a), _rgb(b)
    return sum((x - y) ** 2 for x, y in zip(ra, rb)) ** 0.5


def _matiz_sat(hexa: str) -> tuple[float, float]:
    r, g, b = (c / 255 for c in _rgb(hexa))
    h, _l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360, s


def revisar(paleta: dict[str, Any]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []

    def h(regla: str, sev: str, detalle: str) -> None:
        out.append({"check_id": "C12", "regla": regla, "severidad": sev, "detalle": detalle})

    colores = paleta.get("colores")
    if not isinstance(colores, dict) or not colores:
        h("D5-PALETA-VACIA", "BLOQUEANTE", "falta `colores`")
        return out
    for tok in TOKENS_MIN:
        if tok not in colores:
            h("D5-PALETA-TOKEN", "MAYOR", f"falta el token obligatorio `{tok}`")
    validos: dict[str, str] = {}
    for nombre, c in colores.items():
        hexa = (c or {}).get("hex") if isinstance(c, dict) else None
        if not isinstance(hexa, str) or not RX_HEX.match(hexa):
            h("D5-PALETA-HEX", "MAYOR", f"`{nombre}`: HEX inválido ({hexa!r}); se espera #RRGGBB")
            continue
        validos[nombre] = hexa.upper()
        motivo = (c.get("motivo") or "").strip()
        if len(motivo) < 15:
            h("D5-PALETA-MOTIVO", "MENOR", f"`{nombre}`: falta el motivo de la elección (≥ 15 caracteres)")
    pares = paleta.get("pares_contraste")
    if not isinstance(pares, list) or not pares:
        h("D5-PALETA-PARES", "MAYOR", "falta `pares_contraste` (texto/fondo, CTA, foco)")
        pares = []
    for p in pares:
        fg, bg, uso = p.get("fg"), p.get("bg"), p.get("uso", "")
        if fg not in validos or bg not in validos:
            h("D5-PALETA-PAR", "MAYOR", f"par {fg}/{bg}: token inexistente o con HEX inválido")
            continue
        try:
            minimo = float(p.get("minimo", "4.5"))
        except (TypeError, ValueError):
            h("D5-PALETA-PAR", "MAYOR", f"par {fg}/{bg}: `minimo` no numérico")
            continue
        if uso in USOS_4_5 and minimo < 4.5:
            h("D5-PALETA-MINIMO", "MAYOR", f"par {fg}/{bg} ({uso}): el mínimo para texto normal y botones es 4.5, no {minimo}")
        if minimo < 3.0:
            h("D5-PALETA-MINIMO", "MAYOR", f"par {fg}/{bg}: ningún mínimo puede ser menor que 3.0")
        r = razon_contraste(validos[fg], validos[bg])
        if r + 1e-9 < minimo:
            h("D5-CONTRASTE", "MAYOR", f"{fg} {validos[fg]} sobre {bg} {validos[bg]}: {r:.2f}:1 < {minimo:g}:1 ({uso or 's/uso'})")
    # No reutiliza la base.
    for nombre, hexa in validos.items():
        if hexa in NEUTROS_PUROS:
            continue
        if hexa in HEX_BASE:
            h("D5-PALETA-BASE", "MAYOR", f"`{nombre}` {hexa} es un HEX de la landing de referencia")
            continue
        cerca = [b for b in HEX_BASE if _distancia(hexa, b) <= DIST_CASI_IGUAL]
        if cerca:
            h("D5-PALETA-BASE", "MAYOR", f"`{nombre}` {hexa} es casi igual a {cerca[0]} de la landing de referencia")
    if validos:
        calidos = 0
        for hexa in validos.values():
            matiz, sat = _matiz_sat(hexa)
            if 5 <= matiz <= 45 and sat >= 0.20:
                calidos += 1
        if calidos / len(validos) >= 0.8:
            h("D5-PALETA-FAMILIA", "MENOR",
              "casi toda la paleta cae en la familia cromática de la referencia (marrones y terracotas); "
              "justifícalo en `concepto.familia_cromatica` o cambia el tono dominante")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Contraste AA y no reutilización de la base en paleta.json (C12).")
    ap.add_argument("--paleta", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    try:
        paleta = json.loads(Path(args.paleta).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"no se pudo leer la paleta: {exc}", file=sys.stderr)
        return 2
    hallazgos = revisar(paleta)
    malos = [x for x in hallazgos if x["severidad"] in ("BLOQUEANTE", "MAYOR")]
    if args.json:
        print(json.dumps({"ok": not malos, "hallazgos": hallazgos}, ensure_ascii=False, sort_keys=True))
    else:
        for x in hallazgos:
            print(f"{x['severidad']:<10} {x['regla']}: {x['detalle']}")
        print("sin hallazgos bloqueantes ni mayores" if not malos else f"{len(malos)} hallazgo(s) bloqueante(s) o mayor(es)")
    return 0 if not malos else 3


if __name__ == "__main__":
    sys.exit(main())
