#!/usr/bin/env python3
"""Arma brief-sketch.json de un anuncio a partir de los artefactos aprobados de la oferta.

Uso (desde la raíz del proyecto):
  .venv/bin/python .claude/skills/d6-sketch-animado/scripts/brief_desde_oferta.py \
      --oferta OF-202611-01 --ad-name c01-hueco_vid_h1_v1 [--angulo hueco-como-relato]

Lee (solo lectura): ofertas/<id>/03-oferta/oferta.json, mercado.json, 05-landing/paleta.json (si existe),
05-landing/fonts/*.woff2, 02-validacion/voz_cliente.json (si existe), empresa/limites.yaml.
Escribe: ofertas/<id>/06-creativos/sketch/<ad_name>/brief-sketch.json
Salida: 0 ok · 2 falta una entrada obligatoria · 3 bloqueo de cumplimiento (macro-nicho o nivel no admitidos).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]          # raíz del proyecto
PROHIBIDO_MACRO = {"salud", "relaciones"}             # D6 §5.4: mini novela / video 100 % IA prohibidos


def leer(p: Path, obligatorio=True):
    if not p.exists():
        if obligatorio:
            print(f"FALTA {p.relative_to(RAIZ)}", file=sys.stderr)
            sys.exit(2)
        return None
    return json.loads(p.read_text())


def politica_ia() -> str | None:
    f = RAIZ / "empresa" / "limites.yaml"
    if not f.exists():
        return None
    for linea in f.read_text().splitlines():
        if linea.strip().startswith("politica_divulgacion_ia:"):
            v = linea.split(":", 1)[1].split("#")[0].strip().strip('"').strip("'")
            return None if v in ("", "null", "~") else v
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oferta", required=True)
    ap.add_argument("--ad-name", required=True)
    ap.add_argument("--angulo", help="angulo_id de oferta.angulos[] (por defecto, el primero)")
    a = ap.parse_args()

    od = RAIZ / "ofertas" / a.oferta
    oferta = leer(od / "03-oferta" / "oferta.json")
    mercado = leer(od / "mercado.json")
    paleta = leer(od / "05-landing" / "paleta.json", obligatorio=False)
    voz = leer(od / "02-validacion" / "voz_cliente.json", obligatorio=False)

    macro = oferta.get("macro_nicho")
    nivel = (oferta.get("riesgo") or {}).get("nivel")
    if macro in PROHIBIDO_MACRO:
        print(f"BLOQUEO: el sketch animado está prohibido en {macro} (D6 §5.4).", file=sys.stderr)
        sys.exit(3)
    if nivel not in ("verde",):
        print(f"BLOQUEO: oferta en nivel {nivel}; v0.1 del sketch solo admite verde (gate H del dueño y X1).", file=sys.stderr)
        sys.exit(3)

    angulos = oferta.get("angulos") or []
    ang = next((x for x in angulos if x.get("angulo_id") == a.angulo), angulos[0] if angulos else None)
    avatar = oferta.get("avatar") or {}
    objeciones = [o["texto"] if isinstance(o, dict) else o for o in avatar.get("objeciones", [])]
    objeciones += [x.get("objecion") for x in angulos if x.get("objecion")]

    fuentes = sorted(str(p.relative_to(od)) for p in (od / "05-landing" / "fonts").glob("*.woff2")) \
        if (od / "05-landing" / "fonts").exists() else []

    brief = {
        "schema": "brief-sketch/0.1",
        "oferta_id": oferta["oferta_id"],
        "ad_name": a.ad_name,
        "locale": oferta.get("locale") or mercado.get("locale"),
        "moneda": (oferta.get("precio") or {}).get("lista", {}).get("moneda") or mercado.get("moneda_cobro"),
        "macro_nicho": macro,
        "nivel_riesgo": nivel,
        "producto": {
            "marca": (oferta.get("marca") or {}).get("nombre"),
            "titulo": (oferta.get("promesa") or {}).get("titulo"),
            "mecanismo": oferta.get("mecanismo"),
            "entregables": oferta.get("entregables"),
            "una_frase": oferta.get("prueba_una_frase"),
        },
        "angulo": ang,
        "angulo_seguro": (oferta.get("riesgo") or {}).get("angulo_seguro"),
        "cliente_ideal": oferta.get("cliente_ideal"),
        "avatar": {k: avatar.get(k) for k in ("quiere", "cree", "siente", "lo_dice", "vocabulario")},
        "objeciones": [o for o in dict.fromkeys(objeciones) if o],
        "claims_permitidos": (oferta.get("promesa") or {}).get("claims_permitidos", []),
        "claims_prohibidos": (oferta.get("promesa") or {}).get("claims_prohibidos", []),
        "claims_a_evitar": (oferta.get("riesgo") or {}).get("claims_a_evitar", []),
        "garantia": (oferta.get("garantia") or {}).get("texto_visible"),
        "voz_cliente_vocabulario": [v.get("texto") for v in (voz or {}).get("frases", [])][:30] if voz else [],
        "marca_visual": paleta,
        "fuentes_woff2": fuentes,
        "politica_divulgacion_ia": politica_ia(),
        "supuestos": [] if paleta else ["[SUPUESTO] sin 05-landing/paleta.json: cierre con colores neutros"],
    }
    salida = od / "06-creativos" / "sketch" / a.ad_name / "brief-sketch.json"
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(json.dumps(brief, ensure_ascii=False, indent=1))
    print(salida.relative_to(RAIZ))


if __name__ == "__main__":
    main()
