#!/usr/bin/env python3
"""Prueba en frío cronometrada del render de estáticos de D6 (departamentos/07-creativos.md §4, «Render de estáticos»).

Renderiza un estático por ratio (4:5, 1:1, 9:16) en un directorio temporal, con perfil de navegador temporal y
sin caché (cada render crea y borra su propio perfil), mide los segundos por pieza, anota la versión del
navegador y comprueba dimensiones exactas y que los caracteres del locale están en el HTML renderizado.
La comprobación por OCR contra ``copies.json`` queda **[PENDIENTE]** (no hay OCR instalado: ``references/dependencias.md``);
el PNG se revisa con lectura visual (``Read``).

Es repetible: ``python3 .claude/skills/d6-creativos/scripts/prueba_en_frio.py [--locale pl-PL|it-IT|es-ES|ro-RO] [--json] [--conservar DIR]``.
Salida: 0 todo bien · 3 alguna comprobación falló · 5 sin navegador. Sin red, sin secretos, no toca el repositorio.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

import render_estatico as rr  # noqa: E402

MUESTRAS = {
    "pl-PL": ("ąćęłńóśźż", "Koszt, cena minimalna i marża w jednej tabeli ąćęłńóśźż", "Arkusz z przykładem krok po kroku.", "Przykład ilustracyjny"),
    "it-IT": ("àèéìòù", "Modello Excel per costi, prezzo e margine àèéìòù", "Un modello con esempio passo dopo passo.", "Esempio illustrativo"),
    "es-ES": ("ñáéíóúü¿", "Costo por vela, precio mínimo y margen ñáéíóúü ¿cómo?", "Una hoja con ejemplo resuelto.", "Ejemplo ilustrativo"),
    "ro-RO": ("ăâîșț", "Tabel pentru costuri, preț minim și marjă ăâîșț", "Un tabel cu exemplu pas cu pas.", "Exemplu ilustrativ"),
}


def version_navegador(navegador: str) -> str:
    try:
        r = subprocess.run([navegador, "--version"], capture_output=True, text=True, timeout=30, check=False)
        return (r.stdout or r.stderr).strip().splitlines()[0] if (r.stdout or r.stderr).strip() else "desconocida"
    except (OSError, subprocess.TimeoutExpired):
        return "desconocida"


def ejecutar(locale: str, destino: Path) -> dict:
    caracteres, gancho, apoyo, rotulo = MUESTRAS[locale]
    navegador = rr.buscar_navegador()
    copies = {"idioma": locale,
              "marca": {"nombre": "Prueba D6", "color_fondo": "#fdf6ec", "color_texto": "#1f1a17", "color_acento": "#b5461f",
                        "fuente": "Helvetica Neue, Arial"},
              "anuncios": [{"ad_name": "p01-prueba_img_h1_v1", "texto_en_pieza": {
                  "gancho": gancho, "apoyo": apoyo, "rotulo": rotulo, "aviso": "Contenido informativo."}}]}
    ruta_copies = destino / "copies.json"
    ruta_copies.write_text(json.dumps(copies, ensure_ascii=False), encoding="utf-8")
    plantilla = AQUI.parent / "templates" / "estatico.html"
    piezas, ok = [], True
    for ratio, (ancho, alto) in rr.RATIOS.items():
        if ratio == "3:4":
            continue
        nombre = ratio.replace(":", "x")
        html = destino / f"{nombre}.html"
        png = destino / f"{nombre}.png"
        t0 = time.perf_counter()
        detalle, dims = "ok", None
        try:
            html.write_text(rr.rellenar(plantilla.read_text(encoding="utf-8"), rr.valores_de_pieza(copies, "p01-prueba_img_h1_v1", ratio)), encoding="utf-8")
            dims = rr.renderizar(html, ratio, png, navegador)
        except rr.ErrorRender as exc:
            detalle, ok = str(exc), False
        segundos = round(time.perf_counter() - t0, 2)
        caracteres_ok = all(c in html.read_text(encoding="utf-8") for c in caracteres) if html.exists() else False
        if not caracteres_ok:
            ok = False
        piezas.append({"ratio": ratio, "esperado": [ancho, alto], "obtenido": list(dims) if dims else None, "segundos": segundos,
                       "bytes": png.stat().st_size if png.exists() else 0, "caracteres_del_locale_en_html": caracteres_ok, "detalle": detalle})
        if dims != (ancho, alto):
            ok = False
    return {"ok": ok, "locale": locale, "navegador": navegador, "version_navegador": version_navegador(navegador),
            "perfil": "temporal por render (--user-data-dir), sin caché, red bloqueada", "piezas": piezas,
            "ocr_contra_copies": "[PENDIENTE] sin OCR instalado: revisar el PNG con lectura visual"}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Prueba en frío cronometrada del render de estáticos")
    p.add_argument("--locale", default="pl-PL", choices=sorted(MUESTRAS))
    p.add_argument("--json", action="store_true")
    p.add_argument("--conservar", type=Path, help="carpeta donde dejar HTML y PNG (por defecto, temporal y se borra)")
    try:
        a = p.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    try:
        if a.conservar:
            a.conservar.mkdir(parents=True, exist_ok=True)
            r = ejecutar(a.locale, a.conservar)
        else:
            with tempfile.TemporaryDirectory(prefix="d6-frio-") as tmp:
                r = ejecutar(a.locale, Path(tmp))
    except rr.ErrorRender as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.codigo
    if a.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"navegador: {r['version_navegador']} ({r['navegador']})")
        for x in r["piezas"]:
            print(f"  {x['ratio']}: {x['obtenido']} (esperado {x['esperado']}) {x['segundos']} s {x['bytes']} bytes; caracteres={x['caracteres_del_locale_en_html']}; {x['detalle']}")
        print("OK" if r["ok"] else "FALLA")
    return 0 if r["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
