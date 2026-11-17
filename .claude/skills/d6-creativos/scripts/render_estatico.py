#!/usr/bin/env python3
"""Render HTML -> PNG de un estático de D6 (Ruta A, 0 créditos) con Chrome/Chromium/Brave headless.

Qué hace (determinista, sin red, sin secretos, solo lee/escribe las rutas que se le dan):
  1. Rellena ``templates/estatico.html`` con el texto de ``copies.json`` (``anuncios[].texto_en_pieza`` y
     ``marca``): el texto de la pieza **es** el congelado, no se retoca a mano. Cada valor se escapa;
     un marcador sin resolver es un error (falla cerrado). Si ``marca.fuentes[]`` declara las fuentes WOFF2 de
     D5 (``05-landing/fonts/*.woff2``), las incrusta como ``@font-face`` con ``data:`` URI (HTML autocontenido,
     sin red); cada una exige su ``licencia_ref`` en ``licencias.json`` (lo verifica ``validar_d6.py assets``).
  2. Comprueba el contraste texto/fondo (>= 4,5:1) y los colores/fuente antes de renderizar.
  3. Renderiza con el navegador headless (perfil temporal, ``--host-resolver-rules`` bloquea toda la red),
     lee ``data-ajuste`` con ``--dump-dom`` (rechaza si el texto desborda la zona segura) y verifica que el PNG
     tiene las dimensiones exactas del ratio.

Es el reemplazo probado de ``render_estatico`` con Playwright mientras Playwright no esté instalado
(references/dependencias.md); el motor es intercambiable. Salida: 0 ok · 2 uso · 3 validación (contraste, desborda,
marcador sin resolver, dimensiones) · 5 sin navegador.

Uso:
  python3 render_estatico.py --plantilla templates/estatico.html --copies ofertas/<id>/06-creativos/copies.json \\
      --ad-name c01-hueco_img_h1_v1 --ratio 4:5 --html-salida ofertas/<id>/06-creativos/assets/src/c01-hueco_img_h1_v1.html \\
      --png-salida ofertas/<id>/06-creativos/assets/c01-hueco_img_h1_v1.png
  python3 render_estatico.py ... --oferta-dir ofertas/<id>   # con marca.fuentes[]: resuelve 05-landing/fonts/ bajo la oferta
  python3 render_estatico.py --html assets/src/x.html --ratio 9:16 --png-salida assets/x-9x16.png   # HTML ya generado
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

RATIOS = {"4:5": (1080, 1350), "1:1": (1080, 1080), "9:16": (1080, 1920), "3:4": (1080, 1440)}
CLASE_RATIO = {"4:5": "r-4x5", "1:1": "r-1x1", "9:16": "r-9x16", "3:4": "r-3x4"}
MARCADOR = re.compile(r"\{\{([A-Z_]+)\}\}")
RX_COLOR = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")
RX_FUENTE = re.compile(r"^[A-Za-z0-9 ,'\"-]{1,80}$")
RX_ARCHIVO_FUENTE = re.compile(r"^05-landing/fonts/[a-z0-9-]+\.woff2$")  # los WOFF2 autoalojados de D5
PESOS_FUENTE = (100, 200, 300, 400, 500, 600, 700, 800, 900)
PESO_MAX_FUENTE_KB = 400
CONTRASTE_MIN = 4.5  # WCAG AA para texto normal (references/specs-formatos.md §5)
CANDIDATOS_MAC = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
)
CANDIDATOS_PATH = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "brave-browser")


class ErrorRender(Exception):
    def __init__(self, mensaje: str, codigo: int = 3) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


def buscar_navegador(env: dict[str, str] | None = None) -> str:
    env = os.environ if env is None else env
    forzado = env.get("D6_NAVEGADOR", "").strip()
    if forzado:
        if not Path(forzado).is_file():
            raise ErrorRender(f"D6_NAVEGADOR no existe: {forzado}", 5)
        return forzado
    for ruta in CANDIDATOS_MAC:
        if Path(ruta).is_file():
            return ruta
    for nombre in CANDIDATOS_PATH:
        hallado = shutil.which(nombre)
        if hallado:
            return hallado
    raise ErrorRender("no hay Chrome/Chromium/Brave: instala uno o define D6_NAVEGADOR (o instala Playwright, dependencias.md)", 5)


def dimensiones_png(ruta: Path) -> tuple[int, int]:
    cab = ruta.read_bytes()[:24]
    if cab[:8] != b"\x89PNG\r\n\x1a\n" or cab[12:16] != b"IHDR":
        raise ErrorRender(f"no es un PNG válido: {ruta}")
    return struct.unpack(">II", cab[16:24])


def _luminancia(color: str) -> float:
    c = color.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    canales = [int(c[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in canales]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def contraste(color_a: str, color_b: str) -> float:
    la, lb = sorted((_luminancia(color_a), _luminancia(color_b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def fuentes_css(marca: dict, oferta_dir: Path | None) -> str:
    """``@font-face`` con los WOFF2 de D5 incrustados como ``data:`` URI (vacío si la marca no declara ``fuentes``).

    ``marca.fuentes[]`` = ``[{"familia", "peso", "archivo": "05-landing/fonts/<x>.woff2", "licencia_ref"}]``. Falla cerrado:
    sin ``--oferta-dir``, con una ruta fuera de ``05-landing/fonts/``, un archivo ausente, que no sea WOFF2 (firma ``wOF2``),
    sobre el peso máximo, o sin ``licencia_ref``.
    """
    fuentes = marca.get("fuentes") or []
    if not fuentes:
        return ""
    if oferta_dir is None:
        raise ErrorRender("marca.fuentes declara WOFF2 de D5: falta --oferta-dir para resolver 05-landing/fonts/", 2)
    reglas: list[str] = []
    for i, f in enumerate(fuentes):
        familia, archivo, peso = str(f.get("familia", "")), str(f.get("archivo", "")), f.get("peso", 400)
        if not RX_FUENTE.match(familia):
            raise ErrorRender(f"marca.fuentes[{i}].familia no es un nombre de fuente simple: {familia!r}")
        if not RX_ARCHIVO_FUENTE.match(archivo):
            raise ErrorRender(f"marca.fuentes[{i}].archivo debe ser 05-landing/fonts/<nombre>.woff2: {archivo!r}")
        if peso not in PESOS_FUENTE:
            raise ErrorRender(f"marca.fuentes[{i}].peso no válido: {peso!r}")
        if not str(f.get("licencia_ref", "")).strip():
            raise ErrorRender(f"marca.fuentes[{i}] sin licencia_ref (la licencia va en licencias.json)")
        ruta = oferta_dir / archivo
        if not ruta.is_file():
            raise ErrorRender(f"no existe {ruta} (las WOFF2 las autoaloja D5 en 05-landing/fonts/)")
        datos = ruta.read_bytes()
        if datos[:4] != b"wOF2":
            raise ErrorRender(f"{archivo} no es un WOFF2 (firma wOF2 ausente)")
        if len(datos) > PESO_MAX_FUENTE_KB * 1024:
            raise ErrorRender(f"{archivo} pesa {len(datos)} bytes > {PESO_MAX_FUENTE_KB} kB")
        b64 = base64.b64encode(datos).decode("ascii")
        reglas.append(f'@font-face{{font-family:"{familia}";src:url(data:font/woff2;base64,{b64}) format("woff2");'
                      f"font-weight:{peso};font-style:normal;font-display:block}}")
    return "\n  ".join(reglas)


def valores_de_pieza(copies: dict, ad_name: str, ratio: str, oferta_dir: Path | None = None) -> dict[str, str]:
    """Valores de los marcadores de la plantilla para ``ad_name`` (de copies.json)."""
    anuncio = next((a for a in copies.get("anuncios", []) if a.get("ad_name") == ad_name), None)
    if anuncio is None:
        raise ErrorRender(f"{ad_name} no está en copies.json")
    texto = anuncio.get("texto_en_pieza") or {}
    marca = copies.get("marca") or {}
    faltan = [k for k in ("gancho",) if not str(texto.get(k, "")).strip()]
    faltan += [k for k in ("nombre", "color_fondo", "color_texto", "color_acento", "fuente") if not str(marca.get(k, "")).strip()]
    if faltan:
        raise ErrorRender(f"faltan en copies.json: {', '.join(faltan)}")
    for k in ("color_fondo", "color_texto", "color_acento"):
        if not RX_COLOR.match(str(marca[k])):
            raise ErrorRender(f"marca.{k} no es un color hexadecimal: {marca[k]!r}")
    if not RX_FUENTE.match(str(marca["fuente"])):
        raise ErrorRender(f"marca.fuente no es un nombre de fuente simple: {marca['fuente']!r}")
    ratio_c = contraste(marca["color_texto"], marca["color_fondo"])
    if ratio_c < CONTRASTE_MIN:
        raise ErrorRender(f"contraste texto/fondo {ratio_c:.2f}:1 < {CONTRASTE_MIN}:1")
    idioma = (copies.get("idioma") or "").strip()
    if not re.fullmatch(r"[a-z]{2,3}-[A-Z]{2}", idioma):
        raise ErrorRender(f"copies.json.idioma no es un locale BCP-47: {idioma!r}")
    return {
        "LANG": idioma, "AD_NAME": ad_name, "RATIO_CLASS": CLASE_RATIO[ratio],
        "COLOR_FONDO": marca["color_fondo"], "COLOR_TEXTO": marca["color_texto"], "COLOR_ACENTO": marca["color_acento"],
        "FUENTE": marca["fuente"], "MARCA": marca["nombre"], "GANCHO": texto["gancho"],
        "APOYO": texto.get("apoyo", ""), "ROTULO": texto.get("rotulo", ""), "AVISO": texto.get("aviso", ""),
        "FUENTES_CSS": fuentes_css(marca, oferta_dir),
    }


# Marcadores que van dentro de CSS o atributos: valor ya validado (color/fuente/clase/locale/ad_name); el resto es texto visible.
_SIN_ESCAPAR_COMILLAS = {"COLOR_FONDO", "COLOR_TEXTO", "COLOR_ACENTO", "FUENTE", "RATIO_CLASS", "FUENTES_CSS"}


def rellenar(plantilla: str, valores: dict[str, str]) -> str:
    def reemplazo(m: re.Match[str]) -> str:
        clave = m.group(1)
        if clave not in valores:
            raise ErrorRender(f"marcador sin resolver en la plantilla: {{{{{clave}}}}}")
        valor = str(valores[clave])
        return valor if clave in _SIN_ESCAPAR_COMILLAS else html.escape(valor, quote=True)
    salida = MARCADOR.sub(reemplazo, plantilla)
    resto = MARCADOR.findall(salida)
    if resto:
        raise ErrorRender(f"marcadores sin resolver tras rellenar: {resto}")
    return salida


def _banderas(navegador: str, perfil: str, ancho: int, alto: int) -> list[str]:
    return [navegador, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--disable-extensions",
            "--disable-background-networking", "--force-device-scale-factor=1", f"--user-data-dir={perfil}",
            f"--window-size={ancho},{alto}", "--virtual-time-budget=3000",
            "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE localhost"]


def renderizar(html_ruta: Path, ratio: str, png_salida: Path, navegador: str, plazo_s: int = 90) -> tuple[int, int]:
    if ratio not in RATIOS:
        raise ErrorRender(f"ratio no admitido: {ratio} (use {', '.join(RATIOS)})", 2)
    ancho, alto = RATIOS[ratio]
    url = html_ruta.resolve().as_uri()
    png_salida.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="d6-render-") as perfil:
        try:
            dom = subprocess.run(_banderas(navegador, perfil, ancho, alto) + ["--dump-dom", url], capture_output=True,
                                 text=True, timeout=plazo_s, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ErrorRender(f"el navegador excedió {plazo_s} s", 3) from exc
        ajuste = re.search(r'data-ajuste="([a-z]+)"', dom.stdout or "")
        if not ajuste or ajuste.group(1) != "ok":
            estado = ajuste.group(1) if ajuste else "sin dato"
            raise ErrorRender(f"el texto no cabe en la zona segura o la plantilla no ajustó (data-ajuste={estado})")
        if png_salida.exists():
            png_salida.unlink()
        try:
            subprocess.run(_banderas(navegador, perfil, ancho, alto) + [f"--screenshot={png_salida.resolve()}", url],
                           capture_output=True, text=True, timeout=plazo_s, check=False)
        except subprocess.TimeoutExpired as exc:
            raise ErrorRender(f"el navegador excedió {plazo_s} s", 3) from exc
    if not png_salida.is_file():
        raise ErrorRender("el navegador no produjo el PNG")
    dims = dimensiones_png(png_salida)
    if dims != (ancho, alto):
        png_salida.unlink()
        raise ErrorRender(f"dimensiones {dims} != {(ancho, alto)} para {ratio}")
    return dims


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="HTML -> PNG de un estático de D6 (Chrome headless)")
    p.add_argument("--plantilla", type=Path)
    p.add_argument("--copies", type=Path)
    p.add_argument("--ad-name")
    p.add_argument("--html", type=Path, help="HTML ya generado (sin plantilla)")
    p.add_argument("--oferta-dir", type=Path, help="ofertas/<id>: resuelve marca.fuentes[] en 05-landing/fonts/ (WOFF2 de D5)")
    p.add_argument("--html-salida", type=Path)
    p.add_argument("--ratio", required=True, choices=sorted(RATIOS))
    p.add_argument("--png-salida", type=Path, required=True)
    p.add_argument("--json", action="store_true")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    try:
        if args.html:
            origen = args.html
        else:
            if not (args.plantilla and args.copies and args.ad_name and args.html_salida):
                raise ErrorRender("sin --html exige --plantilla, --copies, --ad-name y --html-salida", 2)
            copies = json.loads(args.copies.read_text(encoding="utf-8"))
            texto = rellenar(args.plantilla.read_text(encoding="utf-8"), valores_de_pieza(copies, args.ad_name, args.ratio, args.oferta_dir))
            args.html_salida.parent.mkdir(parents=True, exist_ok=True)
            args.html_salida.write_text(texto, encoding="utf-8")
            origen = args.html_salida
        dims = renderizar(origen, args.ratio, args.png_salida, buscar_navegador())
    except ErrorRender as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return exc.codigo
    except (OSError, ValueError) as exc:
        print(f"ERROR de entrada: {exc}", file=sys.stderr)
        return 2
    salida = {"ok": True, "png": str(args.png_salida), "ancho": dims[0], "alto": dims[1], "ratio": args.ratio}
    print(json.dumps(salida, ensure_ascii=False) if args.json else f"OK {args.png_salida} {dims[0]}x{dims[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
