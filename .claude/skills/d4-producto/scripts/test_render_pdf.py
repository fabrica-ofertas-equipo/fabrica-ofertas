#!/usr/bin/env python3
"""Pruebas de render_pdf.py (unittest, biblioteca estándar; HTML y navegadores falsos en carpetas temporales; sin red).

Ejecutar desde la raíz del proyecto:
  .venv/bin/python -m unittest discover -s .claude/skills/d4-producto/scripts -p "test_render_pdf.py" -v

Tres bloques: entrada y salida (no necesitan navegador), navegador falso (un script de shell que imita a Chrome: timeout,
salida inválida, banderas, entorno, JSON) y Chrome/Brave/Chromium real (se omite limpiamente si no hay ninguno).
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import shlex
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import render_pdf as rp  # noqa: E402

TITULO = "Próba á é ñ ¿ ł ą"
HTML = f"""<!DOCTYPE html>
<html lang="pl-PL"><head><meta charset="utf-8"><title>{TITULO}</title>
<style>body{{font-family:Georgia,serif;font-size:14pt}} h1{{font-family:Helvetica,Arial,sans-serif}}</style></head>
<body><h1>Próba: á é ñ ¿ ł ą</h1><p>Zażółć gęślą jaźń. ¿Qué tal? Texto seleccionable.</p></body></html>
"""
# PDF mínimo que imita lo que escribe Chrome: 2 páginas (y un nodo /Pages que no cuenta), 1 fuente, /ToUnicode, /Title UTF-16BE, /Lang.
PDF_FALSO = (b"%PDF-1.4\n1 0 obj\n<< /Type /Pages /Count 2 >>\nendobj\n2 0 obj\n<< /Type /Page >>\nendobj\n"
             b"3 0 obj\n<< /Type /Page >>\nendobj\n4 0 obj\n<< /FontFile2 9 0 R /ToUnicode 8 0 R >>\nendobj\n"
             b"5 0 obj\n<< /Title <FEFF0050007200F300620061> /Producer (Falso) >>\nendobj\n6 0 obj\n<< /Lang (es-ES) >>\nendobj\n"
             b"trailer\n<< /Root 6 0 R >>\n%%EOF\n")
CABECERA_FALSO = """#!/bin/sh
SALIDA=""; PERFIL=""
for a in "$@"; do
  case "$a" in
    --version) echo "FalsoChrome 1.2.3"; exit 0;;
    --print-to-pdf=*) SALIDA="${a#--print-to-pdf=}";;
    --user-data-dir=*) PERFIL="${a#--user-data-dir=}";;
  esac
done
"""


def correr(args: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        codigo = rp.main(args)
    return codigo, out.getvalue(), err.getvalue()


def hay_navegador() -> bool:
    try:
        rp.buscar_navegador()
        return True
    except rp.ErrorRender:
        return False


class Base(unittest.TestCase):
    """Carpeta temporal con espacio y ñ; los perfiles del navegador se crean en ``self.perfiles`` para comprobar que se borran."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name) / "carpeta con ñ y espacio"
        self.dir.mkdir()
        self.perfiles = Path(self.tmp.name) / "perfiles"
        self.perfiles.mkdir()
        parche = mock.patch.object(tempfile, "tempdir", str(self.perfiles))
        parche.start()
        self.addCleanup(parche.stop)
        self.html = self.dir / "guía.html"
        self.html.write_text(HTML, encoding="utf-8")
        self.salida = self.dir / "salida.pdf"
        self.registro = Path(self.tmp.name) / "registro"
        self.registro.mkdir()

    def sin_perfiles(self) -> None:
        self.assertEqual(sorted(p.name for p in self.perfiles.iterdir()), [], "el perfil temporal debe borrarse siempre")

    def navegador_falso(self, cuerpo: str) -> str:
        ruta = Path(self.tmp.name) / "falso-chrome"
        ruta.write_text(CABECERA_FALSO + cuerpo, encoding="utf-8")
        ruta.chmod(0o755)
        return str(ruta)

    def pdf_falso(self) -> Path:
        ruta = self.registro / "falso.pdf"
        ruta.write_bytes(PDF_FALSO)
        return ruta

    def args(self, *extra: str, chrome: str | None = None) -> list[str]:
        base = ["--html", str(self.html), "--salida", str(self.salida)]
        return base + (["--chrome", chrome] if chrome else []) + list(extra)


# --------------------------------------------------------------------------------------------------
# Entrada y salida (no necesitan navegador)
# --------------------------------------------------------------------------------------------------
class PruebasEntrada(Base):
    def falso_que_no_debe_lanzarse(self) -> str:
        return self.navegador_falso(f'echo lanzado > {shlex.quote(str(self.registro / "lanzado"))}\ncp {shlex.quote(str(self.pdf_falso()))} "$SALIDA"\n')

    def test_url_remota_se_rechaza_con_2(self) -> None:
        chrome = self.falso_que_no_debe_lanzarse()
        for url in ("http://example.com/a.html", "https://example.com/a.html", "HTTPS://EXAMPLE.COM/A.HTML", "file:///etc/hosts", "ftp://x/y.html"):
            codigo, _, err = correr(["--html", url, "--salida", str(self.salida), "--chrome", chrome])
            self.assertEqual(codigo, 2, url)
            self.assertIn("solo archivos locales", err)
        self.assertFalse(self.salida.exists())
        self.assertFalse((self.registro / "lanzado").exists(), "no se lanza el navegador con una URL")
        self.sin_perfiles()

    def test_html_inexistente_o_que_no_es_html_da_3(self) -> None:
        chrome = self.falso_que_no_debe_lanzarse()
        (self.dir / "nota.txt").write_text("hola", encoding="utf-8")
        for ruta in (self.dir / "no-existe.html", self.dir, self.dir / "nota.txt"):
            codigo, _, err = correr(["--html", str(ruta), "--salida", str(self.salida), "--chrome", chrome])
            self.assertEqual(codigo, 3, str(ruta))
            self.assertIn("ERROR", err)
        self.assertFalse((self.registro / "lanzado").exists())
        self.assertFalse(self.salida.exists())

    def test_salida_existente_no_se_sobrescribe(self) -> None:
        chrome = self.falso_que_no_debe_lanzarse()
        self.salida.write_bytes(b"previo")
        codigo, _, err = correr(self.args(chrome=chrome))
        self.assertEqual(codigo, 2)
        self.assertIn("no se sobrescribe", err)
        self.assertEqual(self.salida.read_bytes(), b"previo")
        self.assertFalse((self.registro / "lanzado").exists(), "falla antes de lanzar el navegador")
        # un enlace simbólico (incluso roto) también cuenta como salida existente
        enlace = self.dir / "enlace.pdf"
        enlace.symlink_to(self.dir / "destino-que-no-existe.pdf")
        self.assertEqual(correr(["--html", str(self.html), "--salida", str(enlace), "--chrome", chrome])[0], 2)
        self.assertFalse((self.dir / "destino-que-no-existe.pdf").exists())

    def test_publicar_es_exclusivo_aunque_la_salida_aparezca_despues(self) -> None:
        origen = self.pdf_falso()
        self.salida.write_bytes("llegó antes".encode())
        with self.assertRaises(rp.ErrorRender) as cm:
            rp._publicar(origen, self.salida)
        self.assertEqual(cm.exception.codigo, 2)
        self.assertEqual(self.salida.read_bytes(), "llegó antes".encode())

    def test_errores_de_uso_dan_2(self) -> None:
        chrome = self.falso_que_no_debe_lanzarse()
        casos = (
            ["--html", str(self.html), "--salida", str(self.dir / "x.txt"), "--chrome", chrome],             # no termina en .pdf
            ["--html", str(self.html), "--salida", str(self.dir / "no" / "x.pdf"), "--chrome", chrome],       # carpeta inexistente
            self.args("--timeout", "0", chrome=chrome),
            self.args("--timeout", "-5", chrome=chrome),
            ["--html", str(self.html)],                                                                       # falta --salida
            [],
        )
        for caso in casos:
            self.assertEqual(correr(caso)[0], 2, caso)
        self.assertFalse((self.registro / "lanzado").exists())

    def test_navegador_ausente_da_5(self) -> None:
        sin_permiso = self.dir / "no-ejecutable"
        sin_permiso.write_text("x", encoding="utf-8")
        sin_permiso.chmod(0o644)
        for chrome in (str(self.dir / "chrome-inexistente"), str(self.dir), str(sin_permiso)):
            codigo, _, err = correr(self.args(chrome=chrome))
            self.assertEqual(codigo, 5, chrome)
            self.assertIn("--chrome", err)
        self.assertFalse(self.salida.exists())
        self.sin_perfiles()
        # sin --chrome y sin ningún navegador instalado: falla cerrado con 5 (no cae a otra cosa)
        with mock.patch.object(rp, "CANDIDATOS_MAC", ()), mock.patch.object(rp, "CANDIDATOS_PATH", ()):
            self.assertEqual(correr(self.args())[0], 5)

    def test_orden_de_busqueda_chrome_brave_chromium(self) -> None:
        nombres = [Path(c).parts[2] for c in rp.CANDIDATOS_MAC]
        self.assertEqual(nombres, ["Google Chrome.app", "Brave Browser.app", "Chromium.app"])
        rutas = []
        for nombre in ("chrome", "brave", "chromium"):
            r = self.dir / nombre
            r.write_text("#!/bin/sh\n", encoding="utf-8")
            r.chmod(0o755)
            rutas.append(r)
        with mock.patch.object(rp, "CANDIDATOS_MAC", tuple(str(r) for r in rutas)), mock.patch.object(rp, "CANDIDATOS_PATH", ()):
            self.assertEqual(rp.buscar_navegador(), str(rutas[0]))
            rutas[0].unlink()
            self.assertEqual(rp.buscar_navegador(), str(rutas[1]))
            rutas[1].unlink()
            self.assertEqual(rp.buscar_navegador(), str(rutas[2]))
            rutas[2].unlink()
            with self.assertRaises(rp.ErrorRender) as cm:
                rp.buscar_navegador()
            self.assertEqual(cm.exception.codigo, 5)

    def test_recursos_remotos_se_rechazan_con_3(self) -> None:
        chrome = self.falso_que_no_debe_lanzarse()
        (self.dir / "estilo.css").write_text('@import url("https://fonts.example/css?family=X");\nbody{color:#000}\n', encoding="utf-8")
        casos = {
            "hoja remota": '<link rel="stylesheet" href="https://fonts.example/css">',
            "hoja sin esquema": '<link rel="stylesheet" href="//cdn.example/x.css">',
            "imagen": '<img src="http://example.com/a.png" alt="">',
            "script": '<script src="https://cdn.example/x.js"></script>',
            "url() en estilo": '<style>body{background:url(https://example.com/a.png)}</style>',
            "@import en estilo": '<style>@import "http://example.com/a.css";</style>',
            "hoja local con @import remoto": '<link rel="stylesheet" href="estilo.css">',
        }
        for nombre, cuerpo in casos.items():
            self.html.write_text(f'<!DOCTYPE html><html lang="es-ES"><head><meta charset="utf-8"><title>t</title>{cuerpo}</head><body>x</body></html>',
                                 encoding="utf-8")
            codigo, _, err = correr(self.args(chrome=chrome))
            self.assertEqual(codigo, 3, nombre)
            self.assertIn("recursos remotos", err, nombre)
        self.assertFalse((self.registro / "lanzado").exists())
        self.assertFalse(self.salida.exists())

    def test_un_enlace_de_texto_no_es_un_recurso(self) -> None:
        (self.dir / "ok.css").write_text("body{font-family:Georgia}\n", encoding="utf-8")
        self.html.write_text('<!DOCTYPE html><html lang="es-ES"><head><meta charset="utf-8"><title>t</title>'
                             '<link rel="stylesheet" href="ok.css"></head><body><a href="https://www.boe.es/">BOE</a> '
                             '<img src="img/a.png" alt=""></body></html>', encoding="utf-8")
        self.assertEqual(rp.recursos_remotos(self.html), [])


# --------------------------------------------------------------------------------------------------
# Verificación del PDF sin librerías
# --------------------------------------------------------------------------------------------------
class PruebasVerificarPdf(unittest.TestCase):
    def test_describe_un_pdf_valido(self) -> None:
        info = rp.verificar_pdf(PDF_FALSO)
        self.assertEqual(info["paginas"], 2, "/Type /Pages no cuenta como página")
        self.assertEqual(info["fuentes_embebidas"], 1)
        self.assertEqual(info["texto_seleccionable"], 1)
        self.assertEqual(info["titulo"], "Próba")
        self.assertEqual(info["lang"], "es-ES")
        self.assertEqual(info["bytes"], len(PDF_FALSO))
        self.assertEqual(info["advertencias"], [])

    def test_cuenta_las_tres_variantes_de_fontfile_y_lee_titulo_literal(self) -> None:
        datos = (b"%PDF-1.4\n<< /Type /Page >>\n<< /FontFile 1 0 R >><< /FontFile2 2 0 R >><< /FontFile3 3 0 R >>\n"
                 b"<< /FontFileX 4 0 R /Title (a \\(b\\) \\\\ c) >>\n%%EOF\n")
        info = rp.verificar_pdf(datos)
        self.assertEqual(info["fuentes_embebidas"], 3, "/FontFileX no es una fuente embebida")
        self.assertEqual(info["titulo"], "a (b) \\ c")
        self.assertIsNone(info["lang"])

    def test_sin_fuentes_ni_tounicode_es_advertencia_no_error(self) -> None:
        info = rp.verificar_pdf(b"%PDF-1.4\n<< /Type /Page >>\n%%EOF\n")
        self.assertEqual(info["fuentes_embebidas"], 0)
        self.assertEqual(len(info["advertencias"]), 2)

    def test_pdf_invalido_da_3(self) -> None:
        for datos in (b"", b"no soy un pdf", b"<!DOCTYPE html><html></html>", b"%PDF-1.4\n<< /Type /Page >>\n",       # sin %%EOF
                      b"%PDF-1.4\n<< /Type /Pages /Count 0 >>\n%%EOF\n"):                                           # sin páginas
            with self.assertRaises(rp.ErrorRender) as cm:
                rp.verificar_pdf(datos)
            self.assertEqual(cm.exception.codigo, 3, datos)


# --------------------------------------------------------------------------------------------------
# Navegador falso (script de shell): mismas rutas de código que con Chrome, sin Chrome
# --------------------------------------------------------------------------------------------------
@unittest.skipUnless(os.name == "posix", "navegador falso en shell POSIX")
class PruebasNavegadorFalso(Base):
    def test_timeout_termina_el_proceso_y_su_grupo_y_borra_el_perfil(self) -> None:
        pidfile = self.registro / "hijo.pid"
        chrome = self.navegador_falso(f"sleep 60 &\necho $! > {shlex.quote(str(pidfile))}\nwait\n")
        t0 = time.perf_counter()
        codigo, _, err = correr(self.args("--timeout", "1", chrome=chrome))
        self.assertEqual(codigo, 3)
        self.assertLess(time.perf_counter() - t0, 20)
        self.assertIn("excedió", err)
        self.assertFalse(self.salida.exists())
        hijo = int(pidfile.read_text().strip())
        limite = time.monotonic() + 5
        vivo = True
        while vivo and time.monotonic() < limite:
            try:
                os.kill(hijo, 0)
                time.sleep(0.1)
            except ProcessLookupError:
                vivo = False
        self.assertFalse(vivo, "el proceso hijo del navegador debe terminarse con el grupo")
        self.sin_perfiles()

    def test_salida_que_no_es_un_pdf_valido_da_3_y_no_deja_archivo(self) -> None:
        cuerpos = {
            "basura": 'printf "no soy un pdf" > "$SALIDA"\n',
            "vacio": ': > "$SALIDA"\n',
            "truncado": 'printf "%%PDF-1.4\\n<< /Type /Page >>\\n" > "$SALIDA"\n',
            "sin archivo": "exit 0\n",
            "falla": 'echo "boom fatal" >&2\nexit 1\n',
        }
        for nombre, cuerpo in cuerpos.items():
            codigo, _, err = correr(self.args(chrome=self.navegador_falso(cuerpo)))
            self.assertEqual(codigo, 3, nombre)
            self.assertIn("ERROR", err, nombre)
            self.assertFalse(self.salida.exists(), nombre)
            self.sin_perfiles()
        self.assertIn("boom fatal", correr(self.args(chrome=self.navegador_falso(cuerpos["falla"])))[2], "el mensaje del navegador llega al error")

    def test_banderas_url_perfil_nuevo_y_borrado(self) -> None:
        args_log, perfil_log = self.registro / "args.txt", self.registro / "perfil.txt"
        chrome = self.navegador_falso(
            f'printf "%s\\n" "$@" > {shlex.quote(str(args_log))}\n'
            f'echo "$PERFIL" >> {shlex.quote(str(perfil_log))}\n'
            f'echo "$SALIDA" >> {shlex.quote(str(self.registro / "salida_tmp.txt"))}\n'
            f'ls "$PERFIL" > /dev/null 2>&1 && echo existia >> {shlex.quote(str(self.registro / "existia.txt"))}\n'
            f'cp {shlex.quote(str(self.pdf_falso()))} "$SALIDA"\n')
        self.assertEqual(correr(self.args(chrome=chrome))[0], 0)
        lanzado = args_log.read_text(encoding="utf-8").splitlines()
        for bandera in ("--headless=new", "--disable-gpu", "--no-pdf-header-footer", "--disk-cache-size=1", "--media-cache-size=1",
                        "--host-resolver-rules=MAP * ~NOTFOUND"):
            self.assertIn(bandera, lanzado)
        self.assertEqual(lanzado[-1], self.html.resolve().as_uri(), "la URL file:// la calcula el script")
        self.assertTrue(lanzado[-1].startswith("file:///"))
        self.assertIn("%20", lanzado[-1])
        self.assertIn("%C3%B1", lanzado[-1])
        self.assertTrue(any(a.startswith("--user-data-dir=") for a in lanzado))
        pdf_tmp = (self.registro / "salida_tmp.txt").read_text().strip()
        perfil_1 = perfil_log.read_text().strip()
        self.assertTrue(pdf_tmp.startswith(str(Path(perfil_1).parent)), "Chrome escribe dentro de la carpeta temporal, no en --salida")
        self.assertNotEqual(pdf_tmp, str(self.salida))
        self.assertEqual(self.salida.read_bytes(), PDF_FALSO)
        self.sin_perfiles()
        self.assertFalse(Path(perfil_1).exists())
        # segunda corrida (otra salida): perfil distinto, nuevo (no existía) y también borrado
        self.assertEqual(correr(["--html", str(self.html), "--salida", str(self.dir / "otra.pdf"), "--chrome", chrome])[0], 0)
        perfiles = perfil_log.read_text().split()
        self.assertEqual(len(perfiles), 2)
        self.assertNotEqual(perfiles[0], perfiles[1])
        self.assertFalse((self.registro / "existia.txt").exists(), "el perfil es nuevo: no existe al lanzar el navegador")
        self.sin_perfiles()

    def test_no_sobrescribe_aunque_ya_haya_corrido_una_vez(self) -> None:
        chrome = self.navegador_falso(f'cp {shlex.quote(str(self.pdf_falso()))} "$SALIDA"\n')
        self.assertEqual(correr(self.args(chrome=chrome))[0], 0)
        primero = self.salida.read_bytes()
        self.assertEqual(correr(self.args(chrome=chrome))[0], 2)
        self.assertEqual(self.salida.read_bytes(), primero)

    def test_entorno_minimo_sin_claves(self) -> None:
        env_log = self.registro / "env.txt"
        chrome = self.navegador_falso(f'env > {shlex.quote(str(env_log))}\ncp {shlex.quote(str(self.pdf_falso()))} "$SALIDA"\n')
        secretos = {"ANTHROPIC_API_KEY": "sk-ant-secreto", "STRIPE_SECRET_KEY": "sk_live_secreto", "AWS_SECRET_ACCESS_KEY": "aws-secreto",
                    "GITHUB_TOKEN": "ghp_secreto", "HOME": "/Users/alguien-real"}
        with mock.patch.dict(os.environ, secretos):
            self.assertEqual(correr(self.args(chrome=chrome))[0], 0)
        texto = env_log.read_text(encoding="utf-8")
        entorno = dict(linea.split("=", 1) for linea in texto.splitlines() if "=" in linea)
        self.assertTrue({"HOME", "PATH", "LANG", "TMPDIR"} <= set(entorno))
        self.assertLessEqual(set(entorno), {"HOME", "PATH", "LANG", "TMPDIR", "PWD", "OLDPWD", "SHLVL", "_"})  # extras que añade el shell
        self.assertNotIn("secreto", texto)
        self.assertNotIn("alguien-real", texto)
        self.assertTrue(entorno["HOME"].startswith(str(self.perfiles)), "HOME apunta al perfil temporal")
        self.assertTrue(entorno["TMPDIR"].startswith(str(self.perfiles)))

    def test_json_con_cronometrar(self) -> None:
        chrome = self.navegador_falso(f'cp {shlex.quote(str(self.pdf_falso()))} "$SALIDA"\n')
        codigo, out, err = correr(self.args("--cronometrar", chrome=chrome))
        self.assertEqual(codigo, 0)
        res = json.loads(out)  # --cronometrar implica --json
        for clave in ("segundos", "paginas", "bytes", "fuentes_embebidas", "navegador"):
            self.assertIn(clave, res)
        self.assertTrue(res["ok"])
        self.assertEqual((res["paginas"], res["fuentes_embebidas"], res["bytes"]), (2, 1, len(PDF_FALSO)))
        self.assertEqual(res["navegador"], "FalsoChrome 1.2.3")
        self.assertIsInstance(res["segundos"], float)
        self.assertGreaterEqual(res["segundos"], 0)
        self.assertEqual(res["pdf"], str(self.salida.resolve()))
        self.assertIn(" s en frío", err)
        self.sin_perfiles()

    def test_json_sin_cronometrar_no_trae_segundos_y_el_texto_es_una_linea(self) -> None:
        chrome = self.navegador_falso(f'cp {shlex.quote(str(self.pdf_falso()))} "$SALIDA"\n')
        codigo, out, _ = correr(self.args("--json", chrome=chrome))
        self.assertEqual(codigo, 0)
        self.assertNotIn("segundos", json.loads(out))
        self.salida.unlink()
        codigo, out, _ = correr(self.args(chrome=chrome))
        self.assertEqual(codigo, 0)
        self.assertTrue(out.startswith("OK ") and out.count("\n") == 1)

    def test_error_en_json_lleva_el_codigo(self) -> None:
        codigo, out, _ = correr(["--html", "https://example.com/a.html", "--salida", str(self.salida), "--json"])
        self.assertEqual(codigo, 2)
        self.assertEqual(json.loads(out)["codigo"], 2)
        self.assertFalse(json.loads(out)["ok"])


# --------------------------------------------------------------------------------------------------
# Chrome / Brave / Chromium real (se omite si no hay)
# --------------------------------------------------------------------------------------------------
class _Contador(BaseHTTPRequestHandler):
    visitas: list[str] = []

    def do_GET(self) -> None:  # noqa: N802
        _Contador.visitas.append(self.path)
        self.send_response(404)
        self.end_headers()

    def log_message(self, *_: object) -> None:
        pass


@unittest.skipUnless(hay_navegador(), "sin Chrome, Brave ni Chromium")
class PruebasNavegadorReal(Base):
    def test_renderiza_con_diacriticos_y_verifica_la_salida(self) -> None:
        codigo, out, err = correr(self.args("--json"))
        self.assertEqual(codigo, 0, err)
        datos = self.salida.read_bytes()
        self.assertTrue(datos.startswith(b"%PDF-"))
        self.assertGreater(len(datos), 0)
        res = json.loads(out)
        self.assertGreaterEqual(res["paginas"], 1)
        self.assertGreater(res["fuentes_embebidas"], 0, "fuentes embebidas (/FontFile)")
        self.assertGreater(res["texto_seleccionable"], 0, "texto seleccionable (/ToUnicode)")
        self.assertEqual(res["titulo"], TITULO, "/Title sale de <title> con sus diacríticos")
        self.assertEqual(res["lang"], "pl-PL", "/Lang sale de <html lang>")
        self.assertEqual(res["bytes"], len(datos))
        self.assertEqual(res["advertencias"], [])
        self.assertNotIn("segundos", res)
        self.assertTrue(res["navegador"])
        self.sin_perfiles()

    def test_cronometrar_en_frio(self) -> None:
        codigo, out, err = correr(self.args("--cronometrar"))
        self.assertEqual(codigo, 0, err)
        res = json.loads(out)
        for clave in ("segundos", "paginas", "bytes", "fuentes_embebidas", "navegador"):
            self.assertIn(clave, res)
        self.assertGreater(res["segundos"], 0)
        self.assertLess(res["segundos"], 60)
        self.assertIn(" s en frío", err)
        self.sin_perfiles()

    def test_no_sobrescribe_con_el_navegador_real(self) -> None:
        self.assertEqual(correr(self.args())[0], 0)
        primero = self.salida.read_bytes()
        codigo, _, err = correr(self.args())
        self.assertEqual(codigo, 2)
        self.assertIn("no se sobrescribe", err)
        self.assertEqual(self.salida.read_bytes(), primero)

    def test_timeout_real_termina_el_navegador(self) -> None:
        codigo, _, err = correr(self.args("--timeout", "0.05"))
        self.assertEqual(codigo, 3)
        self.assertIn("excedió", err)
        self.assertFalse(self.salida.exists())
        self.sin_perfiles()

    def test_la_red_esta_bloqueada(self) -> None:
        _Contador.visitas = []
        servidor = HTTPServer(("127.0.0.1", 0), _Contador)
        hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
        hilo.start()
        self.addCleanup(servidor.server_close)
        self.addCleanup(servidor.shutdown)
        url = f"http://127.0.0.1:{servidor.server_address[1]}/x.png"
        with self.assertRaises(urllib.error.HTTPError) as control:  # control: el servidor responde 404 y cuenta la visita
            urllib.request.urlopen(url, timeout=5)
        control.exception.close()
        self.assertEqual(_Contador.visitas, ["/x.png"], "control: el servidor de la prueba sí recibe visitas")
        _Contador.visitas.clear()
        self.html.write_text(f'<!DOCTYPE html><html lang="es-ES"><head><meta charset="utf-8"><title>t</title></head>'
                             f'<body><p>x</p><img src="{url}" alt=""></body></html>', encoding="utf-8")
        # 1) por la CLI el HTML se rechaza antes de lanzar nada
        self.assertEqual(correr(self.args())[0], 3)
        self.assertEqual(_Contador.visitas, [])
        # 2) aun saltándose esa comprobación, el navegador no sale a la red (--host-resolver-rules)
        res = rp.renderizar(self.html, self.salida, rp.buscar_navegador(), 60)
        self.assertTrue(res["ok"])
        time.sleep(0.3)
        self.assertEqual(_Contador.visitas, [], "el navegador no debe tocar la red, ni siquiera 127.0.0.1")
        self.sin_perfiles()


if __name__ == "__main__":
    unittest.main()
