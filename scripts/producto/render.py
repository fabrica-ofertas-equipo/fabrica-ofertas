"""Render de un entregable de D4: HTML local -> PDF con Chrome/Brave/Chromium sin pantalla, SOLO contra ``file://``.

Versión acotada (hito B0) de ``.claude/skills/d4-producto/scripts/render_pdf.py``: conserva la regla de
seguridad central (solo archivos locales, nunca una URL remota) y la verificación del PDF sin librerías, pero
simplifica la detección de recursos remotos dentro del HTML (eso queda para X1/QA, que ya lo revisa con el
léxico completo) para mantener el código acotado al hito. El **binario es inyectable**: ``ejecutar`` recibe
la función que lanza el proceso (por defecto ``subprocess.run`` con las banderas sin pantalla); las pruebas
pasan un doble que escribe un PDF mínimo en vez de abrir un navegador real.

CLI::

    .venv/bin/python -m scripts.producto.render --html FUENTE.html --salida SALIDA.pdf [--chrome RUTA] [--timeout 60] [--json]

Salida: 0 ok · 2 uso (URL remota, salida ya existe, salida no termina en .pdf) · 3 el HTML no existe, el
navegador no produjo un PDF válido o se agotó el tiempo · 5 no hay navegador disponible (nunca verde falso).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Protocol

from engine import comun
from engine.errores import ErrorExterno, ErrorLimite, ErrorUso, ErrorValidacion

__all__ = ["buscar_navegador", "renderizar", "verificar_pdf", "main"]

VERSION_SCRIPT = "1.0.0"
CANDIDATOS_MAC = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)
CANDIDATOS_PATH = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
EXT_HTML = {".html", ".htm"}
_RX_URL = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://")
_RX_PAGINA = re.compile(rb"/Type\s*/Page(?![A-Za-z])")
_TIMEOUT_DEFECTO_S = 60


class EjecutorProceso(Protocol):
    def __call__(self, argv: list[str], *, env: dict[str, str], timeout_s: float) -> subprocess.CompletedProcess: ...


def _ejecutor_real(argv: list[str], *, env: dict[str, str], timeout_s: float) -> subprocess.CompletedProcess:
    return subprocess.run(argv, env=env, capture_output=True, timeout=timeout_s, stdin=subprocess.DEVNULL, check=False)


def buscar_navegador(chrome: str | None = None) -> str:
    """Ruta del navegador: ``chrome`` si se da (debe existir y ser ejecutable) o el primero hallado.

    Sin ninguno disponible: ``ErrorLimite`` (5), nunca se asume uno ni se sigue sin verificar (falla cerrado,
    nunca verde falso).
    """
    if chrome:
        ruta = Path(chrome).expanduser()
        if not (ruta.is_file() and os.access(ruta, os.X_OK)):
            raise ErrorLimite(f"--chrome no existe o no es ejecutable: {chrome}")
        return str(ruta)
    for candidato in CANDIDATOS_MAC:
        if Path(candidato).is_file() and os.access(candidato, os.X_OK):
            return candidato
    for nombre in CANDIDATOS_PATH:
        hallado = shutil.which(nombre)
        if hallado:
            return hallado
    raise ErrorLimite("no hay Chrome, Brave ni Chromium disponible: instala uno o indica --chrome RUTA")


def validar_html(html_arg: str) -> Path:
    """Ruta local del HTML; rechaza cualquier URL y cualquier archivo que no exista o no sea .html/.htm."""
    if _RX_URL.match(html_arg):
        raise ErrorUso(f"solo archivos locales: {html_arg!r} es una URL (la URL file:// la calcula el script)")
    ruta = Path(html_arg).expanduser()
    if not ruta.is_file():
        raise ErrorValidacion(f"el HTML no existe: {html_arg}")
    if ruta.suffix.lower() not in EXT_HTML:
        raise ErrorValidacion(f"se esperaba un archivo .html o .htm: {html_arg}")
    return ruta.resolve()


def validar_salida(salida_arg: str) -> Path:
    """Ruta de salida: ``.pdf``, carpeta existente y sin archivo previo (no se sobrescribe nada)."""
    ruta = Path(salida_arg).expanduser()
    if ruta.suffix.lower() != ".pdf":
        raise ErrorUso(f"--salida debe terminar en .pdf: {salida_arg}")
    if not ruta.parent.is_dir():
        raise ErrorUso(f"la carpeta de --salida no existe: {ruta.parent}")
    if ruta.exists():
        raise ErrorUso(f"la salida ya existe y no se sobrescribe: {salida_arg}")
    return ruta.parent.resolve() / ruta.name


def verificar_pdf(datos: bytes) -> dict[str, Any]:
    """Comprueba que ``datos`` es un PDF usable (sin librerías). Inválido -> ``ErrorValidacion`` (3)."""
    if not datos:
        raise ErrorValidacion("el PDF está vacío (0 bytes)")
    if not datos.startswith(b"%PDF-"):
        raise ErrorValidacion("la salida no es un PDF (falta la cabecera %PDF-)")
    if b"%%EOF" not in datos[-2048:]:
        raise ErrorValidacion("el PDF está truncado (falta %%EOF al final)")
    paginas = len(_RX_PAGINA.findall(datos))
    if paginas < 1:
        raise ErrorValidacion("el PDF no tiene páginas (/Type /Page)")
    return {"paginas": paginas, "bytes": len(datos)}


def _entorno(base: Path) -> dict[str, str]:
    return {"HOME": str(base), "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "en_US.UTF-8", "TMPDIR": str(base)}


def _banderas(navegador: str, base: Path, pdf_tmp: Path, url: str) -> list[str]:
    return [navegador, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--no-first-run",
            "--disable-extensions", f"--user-data-dir={base / 'perfil'}",
            "--host-resolver-rules=MAP * ~NOTFOUND", f"--print-to-pdf={pdf_tmp}", url]


def renderizar(html: Path, salida: Path, navegador: str, *, ejecutar: EjecutorProceso = _ejecutor_real,
               timeout_s: float = _TIMEOUT_DEFECTO_S) -> dict[str, Any]:
    """Renderiza ``html`` a ``salida`` con un perfil nuevo del navegador. Devuelve la descripción del PDF.

    ``ejecutar`` (inyectable) es quien lanza el proceso del navegador: en producción, ``subprocess.run`` real;
    en pruebas, un doble que escribe un PDF de muestra sin abrir ningún navegador. Errores: ``ErrorExterno``
    (6) si el proceso agota el tiempo o no produce un PDF; ``ErrorValidacion`` (3) si el PDF es inválido.
    """
    url = html.resolve().as_uri()
    base = Path(tempfile.mkdtemp(prefix="d4-render-pdf-"))
    try:
        pdf_tmp = base / "render.pdf"
        try:
            resultado = ejecutar(_banderas(navegador, base, pdf_tmp, url), env=_entorno(base), timeout_s=timeout_s)
        except subprocess.TimeoutExpired as exc:
            raise ErrorExterno(f"el navegador excedió {timeout_s:g} s y se terminó") from exc
        if resultado.returncode != 0 or not pdf_tmp.is_file():
            raise ErrorExterno(f"el navegador no produjo el PDF (código {resultado.returncode})")
        info = verificar_pdf(pdf_tmp.read_bytes())
        with pdf_tmp.open("rb") as fi, salida.open("xb") as fo:
            shutil.copyfileobj(fi, fo)
        return {"ok": True, "pdf": str(salida), "navegador": navegador, **info}
    finally:
        shutil.rmtree(base, ignore_errors=True)


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def _principal(argv: list[str] | None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.producto.render", description="HTML -> PDF de un entregable de D4")
    ap.add_argument("--html", required=True)
    ap.add_argument("--salida", required=True)
    ap.add_argument("--chrome")
    ap.add_argument("--timeout", type=float, default=_TIMEOUT_DEFECTO_S)
    ap.add_argument("--json", action="store_true")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None):
            return 0
        raise ErrorUso("argumentos inválidos (ver --help)") from None
    if a.timeout <= 0:
        raise ErrorUso("--timeout debe ser mayor que 0")
    salida = validar_salida(a.salida)
    html = validar_html(a.html)
    navegador = buscar_navegador(a.chrome)
    resultado = renderizar(html, salida, navegador, timeout_s=a.timeout)
    print(json.dumps(resultado, ensure_ascii=False, sort_keys=True) if a.json
          else f"OK {resultado['pdf']} ({resultado['paginas']} págs, {resultado['bytes']} B)")
    return 0


def main(argv: list[str] | None = None) -> int:
    return comun.ejecutar_cli(lambda: _principal(argv))


if __name__ == "__main__":
    raise SystemExit(main())
