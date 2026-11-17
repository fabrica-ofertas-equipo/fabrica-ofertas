#!/usr/bin/env python3
"""Render HTML -> PDF de un entregable de D4 (ruta A: Chrome/Brave/Chromium sin pantalla), con prueba en frío cronometrada.

Análogo a ``render_estatico.py`` de D6 (HTML -> PNG), pero para el PDF del producto. Solo biblioteca estándar.

Qué hace (determinista, sin red, sin secretos; solo escribe la salida pedida y un perfil temporal que borra al terminar):
  1. Acepta SOLO un archivo HTML local: la URL ``file://`` la calcula el script; rechaza ``http(s)://`` (y cualquier otra URL)
     y cualquier ruta que no exista. Rechaza también un HTML que pida recursos remotos (hojas de estilo, imágenes, scripts,
     ``url()``, ``@import``): el entregable es autocontenido (``formatos-de-producto.md §10``).
  2. Lanza el navegador con perfil NUEVO (``--user-data-dir`` en una carpeta temporal, sin caché), entorno mínimo (HOME, PATH,
     LANG, TMPDIR; no hereda claves), ``--headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf=…`` y toda la red
     bloqueada (``--host-resolver-rules``: ni siquiera 127.0.0.1 responde). Chrome escribe el PDF DENTRO del perfil temporal;
     solo si pasa la verificación se copia a ``--salida`` (con creación exclusiva: no sobrescribe nada).
  3. Timeout con terminación del proceso (SIGTERM y luego SIGKILL a todo el grupo de procesos del navegador).
  4. Verifica el PDF sin librerías: cabecera ``%PDF-``, tamaño > 0, ``%%EOF`` final, nº de páginas (``/Type /Page`` sin contar
     ``/Type /Pages``), fuentes embebidas (``/FontFile``, ``/FontFile2``, ``/FontFile3``), ``/ToUnicode`` (texto seleccionable),
     ``/Title`` y ``/Lang``. Cuenta objetos en claro: vale para Skia/PDF de Chrome (PDF 1.4, sin flujos de objetos); otro
     productor puede dar 0 y quedaría como advertencia, no como error.

Navegador: ``--chrome RUTA`` o, en este orden, ``/Applications/Google Chrome.app``, ``Brave Browser.app``, ``Chromium.app`` y
(solo Linux) ``google-chrome``/``chromium`` en el PATH. Sin navegador: falla cerrado con 5.

Salida: 0 ok · 2 uso (URL remota, salida existente, salida que no es ``.pdf`` o sin carpeta, timeout inválido) · 3 entrada o PDF
inválido (el HTML no existe o no es ``.html``/``.htm``, pide recursos remotos, el navegador falla o excede el timeout, el PDF no es
válido) · 5 sin navegador. Por stdout: una línea de texto o, con ``--json``/``--cronometrar``, un objeto JSON.

Prueba en frío cronometrada (``formatos-de-producto.md §10.1``; spec §4.4): ``--cronometrar`` añade ``segundos`` = tiempo de
pared desde que se lanza el navegador hasta que el proceso termina (perfil nuevo y sin caché SIEMPRE; no incluye la verificación del
PDF) e implica ``--json``. JSON: ``{"ok", "pdf", "segundos", "paginas", "bytes", "fuentes_embebidas", "navegador",
"texto_seleccionable", "titulo", "lang", "advertencias"}``.
Cómo lo lee el QA: ``segundos`` NO se compara con ``tiempo_prometido_min``. Ese número son los minutos del COMPRADOR (lectura +
ejecución; los mide ``tiempo_total.py`` y el novato en frío, ``tiempo-y-novato.md §5``) y esta prueba mide la ruta de PDF, no al
comprador: el render nunca suma a ``tiempos.total_min``. El QA registra las dos por separado: del render anota ``navegador``,
``segundos``, ``bytes``, ``paginas`` y ``fuentes_embebidas`` (el peso contra ``producto.peso_max_mb_pdf`` lo comprueba
``empaquetar.py``); del comprador, ``total_min`` frente a ``prometido_min``. No hay umbral de política para ``segundos``: se compara
con la referencia de ``dependencias.md`` (Chrome 156, 0,68 s) y con el ``--timeout`` usado.

Uso:
  python3 render_pdf.py --html ofertas/<id>/04-producto/entregables/fuente/guia.html \\
      --salida ofertas/<id>/04-producto/entregables/guia-v1.pdf [--chrome RUTA] [--timeout 60] [--json] [--cronometrar]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

CANDIDATOS_MAC = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
)
CANDIDATOS_PATH = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser")
EXT_HTML = {".html", ".htm"}
RX_URL = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*://")
ENV_PATH = "/usr/bin:/bin:/usr/sbin:/sbin"
ENV_LANG = "en_US.UTF-8"

# Recursos que el navegador DESCARGARÍA (un <a href="https://…"> es solo texto y se permite).
RX_ETIQUETA_REMOTA = re.compile(
    r"<(?:link|script|img|iframe|source|video|audio|embed|object|input|image|use|track)\b[^>]*?"
    r"\b(?:src|href|data|poster|srcset|xlink:href)\s*=\s*[\"']?\s*(?:https?:)?//", re.I | re.S)
RX_URL_CSS_REMOTA = re.compile(r"url\(\s*[\"']?\s*(?:https?:)?//", re.I)
RX_IMPORT_REMOTO = re.compile(r"@import\s+(?:url\(\s*)?[\"']?\s*(?:https?:)?//", re.I)
RX_CSS_LOCAL = re.compile(r"<link\b[^>]*?\brel\s*=\s*[\"']?stylesheet[\"']?[^>]*?\bhref\s*=\s*[\"']([^\"'#?]+)[\"']", re.I | re.S)

RX_PAGINA = re.compile(rb"/Type\s*/Page(?![A-Za-z])")
RX_FONTFILE = re.compile(rb"/FontFile\d?\b")
RX_TOUNICODE = re.compile(rb"/ToUnicode\b")
RX_TITULO = re.compile(rb"/Title\s*(?:<([0-9A-Fa-f\s]*)>|\(((?:\\.|[^\\)])*)\))")
RX_LANG = re.compile(rb"/Lang\s*\(((?:\\.|[^\\)])*)\)")
RUIDO_STDERR = ("CVDisplayLink", "task_policy_set", "allocator", "simple_version_upgrade", "simple_backend_impl", "disk_cache.cc")


class ErrorRender(Exception):
    def __init__(self, mensaje: str, codigo: int = 3) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


# --------------------------------------------------------------------------------------------------
# Navegador y entrada
# --------------------------------------------------------------------------------------------------
def buscar_navegador(chrome: str | None = None) -> str:
    """Ruta del navegador: ``chrome`` si se da (debe existir y ser ejecutable) o el primero hallado. Sin ninguno: error 5."""
    if chrome:
        ruta = Path(chrome).expanduser()
        if not (ruta.is_file() and os.access(ruta, os.X_OK)):
            raise ErrorRender(f"--chrome no existe o no es ejecutable: {chrome}", 5)
        return str(ruta)
    for candidato in CANDIDATOS_MAC:
        if Path(candidato).is_file() and os.access(candidato, os.X_OK):
            return candidato
    for nombre in CANDIDATOS_PATH:
        hallado = shutil.which(nombre)
        if hallado:
            return hallado
    raise ErrorRender("no hay Chrome, Brave ni Chromium: instala uno o indica --chrome RUTA (references/dependencias.md)", 5)


def validar_html(html_arg: str) -> Path:
    """Ruta local del HTML. URL (cualquier esquema) -> 2; no existe o no es .html/.htm -> 3."""
    if RX_URL.match(html_arg):
        raise ErrorRender(f"solo archivos locales: {html_arg!r} es una URL (la URL file:// la calcula el script a partir de la ruta)", 2)
    ruta = Path(html_arg).expanduser()
    if not ruta.is_file():
        raise ErrorRender(f"el HTML no existe: {html_arg}", 3)
    if ruta.suffix.lower() not in EXT_HTML:
        raise ErrorRender(f"se esperaba un archivo .html o .htm, no {ruta.suffix or 'sin extensión'}: {html_arg}", 3)
    return ruta.resolve()


def validar_salida(salida_arg: str) -> Path:
    """Ruta de salida: ``.pdf``, carpeta existente y sin archivo previo (no se sobrescribe nada). Todo -> 2."""
    ruta = Path(salida_arg).expanduser()
    if ruta.suffix.lower() != ".pdf":
        raise ErrorRender(f"--salida debe terminar en .pdf: {salida_arg}", 2)
    if not ruta.parent.is_dir():
        raise ErrorRender(f"la carpeta de --salida no existe: {ruta.parent}", 2)
    if os.path.lexists(ruta):
        raise ErrorRender(f"la salida ya existe y no se sobrescribe: {salida_arg} (usa otro nombre o versión)", 2)
    return ruta.parent.resolve() / ruta.name


def recursos_remotos(html: Path) -> list[str]:
    """Referencias a recursos remotos del HTML y de sus hojas de estilo locales (``<link rel=stylesheet href=local.css>``)."""
    hallazgos: list[str] = []

    def revisar(texto: str, nombre: str, css: bool) -> None:
        if not css and RX_ETIQUETA_REMOTA.search(texto):
            hallazgos.append(f"{nombre}: etiqueta con src/href remoto")
        if RX_URL_CSS_REMOTA.search(texto):
            hallazgos.append(f"{nombre}: url() remoto")
        if RX_IMPORT_REMOTO.search(texto):
            hallazgos.append(f"{nombre}: @import remoto")

    texto = html.read_text(encoding="utf-8", errors="replace")
    revisar(texto, html.name, css=False)
    for ref in RX_CSS_LOCAL.findall(texto):
        if RX_URL.match(ref) or ref.startswith("//"):
            continue
        hoja = (html.parent / ref).resolve()
        if hoja.is_file() and hoja.suffix.lower() == ".css":
            revisar(hoja.read_text(encoding="utf-8", errors="replace"), ref, css=True)
    return hallazgos


# --------------------------------------------------------------------------------------------------
# Verificación del PDF (sin librerías)
# --------------------------------------------------------------------------------------------------
def _texto_pdf(hex_: bytes | None, literal: bytes | None) -> str | None:
    if hex_ is not None:
        digitos = re.sub(rb"\s+", b"", hex_)
        crudo = bytes.fromhex((digitos + (b"0" if len(digitos) % 2 else b"")).decode("ascii"))
    elif literal is not None:
        crudo = re.sub(rb"\\(.)", lambda m: {b"n": b"\n", b"r": b"\r", b"t": b"\t"}.get(m.group(1), m.group(1)), literal)
    else:
        return None
    if crudo.startswith(b"\xfe\xff"):
        return crudo[2:].decode("utf-16-be", errors="replace")
    return crudo.decode("latin-1")


def verificar_pdf(datos: bytes) -> dict[str, Any]:
    """Comprueba que ``datos`` es un PDF utilizable y lo describe. Inválido -> ``ErrorRender`` (3)."""
    if not datos:
        raise ErrorRender("el PDF está vacío (0 bytes)")
    if not datos.startswith(b"%PDF-"):
        raise ErrorRender("la salida no es un PDF (falta la cabecera %PDF-)")
    if b"%%EOF" not in datos[-2048:]:
        raise ErrorRender("el PDF está truncado (falta %%EOF al final)")
    paginas = len(RX_PAGINA.findall(datos))
    if paginas < 1:
        raise ErrorRender("el PDF no tiene páginas (/Type /Page)")
    titulo = RX_TITULO.search(datos)
    lang = RX_LANG.search(datos)
    fuentes, tounicode = len(RX_FONTFILE.findall(datos)), len(RX_TOUNICODE.findall(datos))
    advertencias = []
    if fuentes == 0:
        advertencias.append("sin fuentes embebidas (/FontFile): revisa las @font-face y el texto de la fuente")
    if tounicode == 0:
        advertencias.append("sin /ToUnicode: el texto puede no ser seleccionable")
    return {
        "paginas": paginas, "bytes": len(datos), "fuentes_embebidas": fuentes, "texto_seleccionable": tounicode,
        "titulo": _texto_pdf(titulo.group(1), titulo.group(2)) if titulo else None,
        "lang": _texto_pdf(None, lang.group(1)) if lang else None,
        "advertencias": advertencias,
    }


# --------------------------------------------------------------------------------------------------
# Render
# --------------------------------------------------------------------------------------------------
def _entorno(base: Path) -> dict[str, str]:
    """Entorno mínimo: HOME y TMPDIR dentro del perfil temporal; nada heredado (ni claves ni rutas del usuario)."""
    return {"HOME": str(base), "PATH": ENV_PATH, "LANG": ENV_LANG, "TMPDIR": str(base / "tmp")}


def banderas(navegador: str, base: Path, pdf_tmp: Path, url: str) -> list[str]:
    return [
        navegador, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
        "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-background-networking",
        "--disable-component-update", "--disable-sync", "--disable-breakpad", "--use-mock-keychain", "--password-store=basic",
        f"--user-data-dir={base / 'perfil'}", f"--disk-cache-dir={base / 'cache'}", "--disk-cache-size=1", "--media-cache-size=1",
        "--host-resolver-rules=MAP * ~NOTFOUND",
        f"--print-to-pdf={pdf_tmp}", url,
    ]


def _grupo(proc: subprocess.Popen, senal: int) -> None:
    try:
        os.killpg(proc.pid, senal)
    except (ProcessLookupError, PermissionError):
        pass


def _terminar(proc: subprocess.Popen) -> None:
    """SIGTERM al grupo de procesos del navegador (hijos incluidos); SIGKILL si sigue vivo a los 3 s."""
    _grupo(proc, signal.SIGTERM)
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    _grupo(proc, signal.SIGKILL)
    proc.wait()


def version_navegador(navegador: str, env: dict[str, str]) -> str:
    try:
        r = subprocess.run([navegador, "--version"], capture_output=True, text=True, timeout=15, env=env, check=False,
                           stdin=subprocess.DEVNULL)
        linea = (r.stdout or "").strip().splitlines()
        return linea[0].strip() if r.returncode == 0 and linea else Path(navegador).name
    except (OSError, subprocess.TimeoutExpired):
        return Path(navegador).name


def _cola_stderr(ruta: Path) -> str:
    try:
        lineas = [ln.strip() for ln in ruta.read_text(encoding="utf-8", errors="replace").splitlines()]
    except OSError:
        return ""
    utiles = [ln for ln in lineas if ln and not any(r in ln for r in RUIDO_STDERR)]
    return " | ".join(utiles[-3:])[:400]


def _borrar_perfil(base: Path) -> None:
    for intento in range(6):
        shutil.rmtree(base, ignore_errors=True)
        if not base.exists():
            return
        time.sleep(0.2 * (intento + 1))
    print(f"AVISO: no se pudo borrar el perfil temporal {base}", file=sys.stderr)


def _publicar(origen: Path, destino: Path) -> None:
    """Copia ``origen`` a ``destino`` con creación exclusiva (``xb``): jamás sobrescribe."""
    try:
        with origen.open("rb") as fi, destino.open("xb") as fo:
            shutil.copyfileobj(fi, fo)
    except FileExistsError as exc:
        raise ErrorRender(f"la salida apareció mientras se renderizaba y no se sobrescribe: {destino}", 2) from exc
    except OSError as exc:
        destino.unlink(missing_ok=True)
        raise ErrorRender(f"no se pudo escribir la salida: {exc}", 3) from exc


def renderizar(html: Path, salida: Path, navegador: str, plazo_s: float = 60) -> dict[str, Any]:
    """Renderiza ``html`` a ``salida`` con perfil nuevo. Devuelve la descripción del PDF y ``segundos`` (render en frío)."""
    url = html.resolve().as_uri()
    base = Path(tempfile.mkdtemp(prefix="d4-render-pdf-"))
    try:
        (base / "tmp").mkdir()
        env = _entorno(base)
        pdf_tmp = base / "render.pdf"
        registro = base / "navegador.stderr"
        nombre_navegador = version_navegador(navegador, env)
        t0 = time.perf_counter()
        with registro.open("wb") as err:
            proc = subprocess.Popen(banderas(navegador, base, pdf_tmp, url), env=env, stdin=subprocess.DEVNULL,
                                    stdout=err, stderr=err, start_new_session=True)
            try:
                proc.wait(timeout=plazo_s)
            except subprocess.TimeoutExpired as exc:
                _terminar(proc)
                raise ErrorRender(f"el navegador excedió {plazo_s:g} s y se terminó", 3) from exc
            finally:
                _grupo(proc, signal.SIGKILL)  # barrido: ningún auxiliar sigue escribiendo en el perfil
        segundos = time.perf_counter() - t0
        if proc.returncode != 0 or not pdf_tmp.is_file():
            raise ErrorRender(f"el navegador no produjo el PDF (código {proc.returncode}): {_cola_stderr(registro) or 'sin mensaje'}")
        info = verificar_pdf(pdf_tmp.read_bytes())
        _publicar(pdf_tmp, salida)
        return {"ok": True, "pdf": str(salida), "segundos": round(segundos, 2), **info, "navegador": nombre_navegador}
    finally:
        _borrar_perfil(base)


# --------------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------------
def _linea(res: dict[str, Any]) -> str:
    partes = [f"OK {res['pdf']}", f"{res['paginas']} págs", f"{res['bytes']} B", f"{res['fuentes_embebidas']} fuentes embebidas", res["navegador"]]
    if "segundos" in res:
        partes.append(f"{res['segundos']:.2f} s en frío".replace(".", ","))
    return " · ".join(partes)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="HTML -> PDF de un entregable de D4 (Chrome sin pantalla, ruta A) con prueba en frío")
    p.add_argument("--html", required=True, help="archivo HTML local (no URL)")
    p.add_argument("--salida", required=True, help="PDF de salida (no se sobrescribe)")
    p.add_argument("--chrome", help="ruta del navegador (por defecto: Chrome, Brave, Chromium)")
    p.add_argument("--timeout", type=float, default=60, help="segundos máximos del navegador (por defecto 60)")
    p.add_argument("--json", action="store_true", help="salida en JSON")
    p.add_argument("--cronometrar", action="store_true", help="reporta el tiempo del render en frío (implica --json)")
    try:
        args = p.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    como_json = args.json or args.cronometrar
    try:
        if not args.timeout > 0:
            raise ErrorRender("--timeout debe ser mayor que 0", 2)
        salida = validar_salida(args.salida)
        html = validar_html(args.html)
        remotos = recursos_remotos(html)
        if remotos:
            raise ErrorRender("el HTML pide recursos remotos (solo archivos locales): " + "; ".join(remotos))
        navegador = buscar_navegador(args.chrome)
        res = renderizar(html, salida, navegador, args.timeout)
    except ErrorRender as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        if como_json:
            print(json.dumps({"ok": False, "codigo": exc.codigo, "error": str(exc)}, ensure_ascii=False))
        return exc.codigo
    except (OSError, ValueError) as exc:
        print(f"ERROR de entrada: {exc}", file=sys.stderr)
        if como_json:
            print(json.dumps({"ok": False, "codigo": 3, "error": str(exc)}, ensure_ascii=False))
        return 3
    for aviso in res["advertencias"]:
        print(f"AVISO: {aviso}", file=sys.stderr)
    if args.cronometrar:
        print(_linea(res), file=sys.stderr)  # lectura humana; el JSON de stdout es lo que consume el QA
    else:
        res.pop("segundos")
    print(json.dumps(res, ensure_ascii=False) if como_json else _linea(res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
