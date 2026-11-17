"""Servidor HTTP real (wsgiref + hilos) en 127.0.0.1 con puerto efímero: la ÚNICA prueba del panel que abre un socket."""
from __future__ import annotations

import http.client
import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
import unittest
from urllib.parse import quote

from dashboard.__main__ import main
from dashboard.seguridad import CSP_SITIO
from dashboard.servidor import crear_servidor
from tests.dashboard.test_servidor_apoyo import OFERTA, PruebaBase, RAIZ_REPO


class PruebaHttpReal(PruebaBase):
    bloquear_sockets = False

    def setUp(self) -> None:
        super().setUp()
        self.app = self.panel(puerto=0, ping_s=0.2, sondeo_sse_s=0.05)
        self.servidor = crear_servidor(self.app, 0)
        self.puerto = self.servidor.server_port
        self.assertEqual(self.servidor.server_address[0], "127.0.0.1", "solo escucha en loopback")
        hilo = threading.Thread(target=self.servidor.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
        hilo.start()
        self.addCleanup(hilo.join, 5)
        self.addCleanup(self.servidor.server_close)
        self.addCleanup(self.servidor.shutdown)

    def pedir(self, metodo: str, ruta: str, *, cuerpo: dict | None = None, token: bool = True, host: str | None = None,
              cabeceras: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
        con = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=15)
        try:
            h = dict(cabeceras or {})
            if token:
                h["X-Panel-Token"] = self.app.token
            datos = None
            if cuerpo is not None:
                datos = json.dumps(cuerpo).encode()
                h["Content-Type"] = "application/json"
                h.setdefault("Origin", f"http://127.0.0.1:{self.puerto}")
            con.putrequest(metodo, ruta, skip_host=True, skip_accept_encoding=True)
            con.putheader("Host", host if host is not None else f"127.0.0.1:{self.puerto}")
            for k, v in h.items():
                con.putheader(k, v)
            if datos is not None:
                con.putheader("Content-Length", str(len(datos)))
            con.endheaders(datos)
            r = con.getresponse()
            return r.status, {k.lower(): v for k, v in r.getheaders()}, r.read()
        finally:
            con.close()

    def test_estaticos_api_y_cabeceras_por_http(self) -> None:
        est, cab, cuerpo = self.pedir("GET", "/", token=False)
        self.assertEqual(est, 200)
        self.assertIn(b"Panel de prueba", cuerpo)
        self.assertEqual(cab["content-type"], "text/html; charset=utf-8")
        self.assertIn("script-src 'self'", cab["content-security-policy"])
        est, cab, cuerpo = self.pedir("GET", "/api/sistema")
        self.assertEqual(est, 200)
        self.assertEqual(json.loads(cuerpo)["datos"]["panel"]["puerto"], self.puerto)
        self.assertEqual(self.pedir("GET", "/api/sistema", token=False)[0], 403)
        self.assertEqual(self.pedir("GET", "/api/sistema", host="evil.example.com")[0], 403)
        self.assertEqual(self.pedir("GET", "/api/sistema", host=f"127.0.0.1:{self.puerto + 1}")[0], 403)
        self.assertEqual(self.pedir("GET", "/api/sistema", host=f"localhost:{self.puerto}")[0], 200)
        est, cab, cuerpo = self.pedir("GET", f"/sitio/{OFERTA}/index.html", token=False)
        self.assertEqual((est, cab["content-security-policy"]), (200, CSP_SITIO))

    def test_post_por_http_exige_origen_y_token(self) -> None:
        est, _, cuerpo = self.pedir("POST", "/api/pulido", cuerpo={"etapa": "D1", "titulo": "por http"})
        self.assertEqual(est, 200)
        self.assertEqual(json.loads(cuerpo)["datos"]["id"], "PUL-0001")
        self.assertEqual(self.pedir("POST", "/api/pulido", cuerpo={"etapa": "D1", "titulo": "x"}, cabeceras={"Origin": "http://evil.com"})[0], 403)
        self.assertEqual(self.pedir("POST", "/api/pulido", cuerpo={"etapa": "D1", "titulo": "x"}, token=False)[0], 403)
        est, _, _ = self.pedir("POST", "/api/pausa", cuerpo={"motivo": "http"})
        self.assertEqual(est, 200)
        self.assertTrue((self.raiz / "empresa" / "PAUSA").is_file())

    def test_rutas_con_caracteres_no_ascii_llegan_bien_decodificadas(self) -> None:
        self.escribir(f"ofertas/{OFERTA}/05-landing/sitio/ñandú.html", "<p>ñandú</p>")
        self.escribir(f"ofertas/{OFERTA}/informe-ñandú.md", "# ñandú\n")
        est, _, cuerpo = self.pedir("GET", f"/sitio/{OFERTA}/" + quote("ñandú.html"), token=False)
        self.assertEqual((est, cuerpo), (200, "<p>ñandú</p>".encode()))
        est, _, cuerpo = self.pedir("GET", f"/api/oferta/{OFERTA}/archivo?ruta=" + quote("informe-ñandú.md"))
        self.assertEqual(json.loads(cuerpo)["datos"]["contenido"], "# ñandú\n")

    def test_traversal_por_http(self) -> None:
        for ruta in ("/../../etc/passwd", "/%2e%2e/%2e%2e/etc/passwd", f"/sitio/{OFERTA}/%2e%2e/%2e%2e/estado.json", "/pages/..%2f..%2frepo", "/.env"):
            est, _, cuerpo = self.pedir("GET", ruta, token=False)
            self.assertIn(est, (400, 403, 404), ruta)
            self.assertNotIn(b"root:", cuerpo)
            self.assertNotIn(b"oferta_id", cuerpo)

    def test_sse_llega_en_vivo_con_ping_y_cambio(self) -> None:
        con = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=10)
        self.addCleanup(con.close)
        con.request("GET", "/api/eventos", headers={"X-Panel-Token": self.app.token, "Accept": "text/event-stream"})
        r = con.getresponse()
        self.assertEqual((r.status, r.getheader("Content-Type")), (200, "text/event-stream; charset=utf-8"))
        self.assertEqual(r.fp.readline(), b"retry: 3000\n")
        self.assertEqual(r.fp.readline(), b": conectado\n")
        r.fp.readline()
        t0 = time.monotonic()
        self.app.difusor.publicar({"tipo": "registro", "ruta": "empresa/registro.jsonl", "ts": "2026-11-09T12:00:00Z"})
        lineas = []
        while time.monotonic() - t0 < 5:
            linea = r.fp.readline()
            if linea.startswith(b"data:"):
                lineas.append(linea)
                break
        self.assertTrue(lineas, "el evento llegó sin esperar al cierre de la conexión (se vacía el búfer en cada bloque)")
        self.assertEqual(json.loads(lineas[0][5:])["tipo"], "registro")
        r.fp.readline()
        bloque = [r.fp.readline() for _ in range(3)]
        self.assertIn(b"event: ping\n", bloque)

    def test_main_valida_argumentos(self) -> None:
        self.assertEqual(main(["--puerto", "70000"]), 2)
        self.assertEqual(main(["--raiz", str(self.tmp / "no-existe")]), 2)
        ocupado = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.addCleanup(ocupado.close)
        ocupado.bind(("127.0.0.1", 0))
        ocupado.listen(1)
        self.assertEqual(main(["--puerto", str(ocupado.getsockname()[1]), "--raiz", str(self.raiz)]), 2)


class PruebaArranque(unittest.TestCase):
    def test_python_m_dashboard_imprime_la_url_con_token_y_responde(self) -> None:
        import tempfile
        import shutil
        from tests.dashboard.test_servidor_apoyo import RAIZ_FIXTURE
        tmp = tempfile.mkdtemp(prefix="panel-arranque-")
        self.addCleanup(shutil.rmtree, tmp, True)
        raiz = os.path.join(tmp, "repo")
        shutil.copytree(RAIZ_FIXTURE, raiz)
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1", "FABRICA_ENTORNO": "prueba"}
        proc = subprocess.Popen([sys.executable, "-m", "dashboard", "--puerto", "0", "--raiz", raiz], cwd=RAIZ_REPO, env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.addCleanup(proc.stderr.close)   # los cleanups corren al revés: primero kill, luego wait, luego cerrar tuberías
        self.addCleanup(proc.stdout.close)
        self.addCleanup(proc.wait)
        self.addCleanup(proc.kill)
        url = ""
        t0 = time.monotonic()
        while time.monotonic() - t0 < 20 and not url:
            linea = proc.stdout.readline()
            if linea.startswith("http://"):
                url = linea.strip()
            elif not linea and proc.poll() is not None:
                break
        m = re.fullmatch(r"http://127\.0\.0\.1:(\d+)/#t=([A-Za-z0-9_-]{43,})", url)
        self.assertIsNotNone(m, url or proc.stderr.read())
        puerto, token = int(m.group(1)), m.group(2)
        con = http.client.HTTPConnection("127.0.0.1", puerto, timeout=10)
        con.request("GET", "/api/ofertas", headers={"X-Panel-Token": token})
        r = con.getresponse()
        self.assertEqual(r.status, 200)
        self.assertEqual(len(json.loads(r.read())["datos"]), 4)
        con.close()
        con = http.client.HTTPConnection("127.0.0.1", puerto, timeout=10)
        con.request("GET", "/api/ofertas")
        self.assertEqual(con.getresponse().status, 403)
        con.close()


if __name__ == "__main__":
    unittest.main()
