"""Maqueta mínima de la API del panel (CONTRATO §4) SOLO para ver el frontend sin el servidor de P1.

Sirve ``dashboard/web/`` y responde ``/api/*`` con los JSON de ``api/`` (los mismos que usan las pruebas de Node).
Escucha únicamente en 127.0.0.1. No toca ``empresa/`` ni ``ofertas/``. No es el servidor real: no valida Host/Origin.

    python3 tests/fixtures/dashboard/shell/maqueta_api.py --puerto 8791 [--escenario vacio] [--eventos 4]
    → http://127.0.0.1:8791/#t=maqueta-token-0123456789
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[3]
WEB = RAIZ / "dashboard" / "web"
API = AQUI / "api"
TOKEN = "maqueta-token-0123456789"
TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
         ".json": "application/json", ".svg": "image/svg+xml"}

ESTADO = {"pausa": None, "jobs": {}, "escenario": "lleno", "eventos": 0, "extra": []}


def cargar(nombre: str) -> dict:
    return json.loads((API / f"{nombre}.json").read_text(encoding="utf-8"))


def respuesta_api(ruta: str, consulta: dict) -> tuple[int, dict]:
    vacio = ESTADO["escenario"] == "vacio"
    if ruta == "/sistema":
        sobre = cargar("sistema")
        if ESTADO["pausa"]:
            sobre["datos"]["pausa"] = ESTADO["pausa"]
        if vacio:
            sobre["datos"].update({"freno_captura": None, "infra": None, "modo_demo": False})
        return 200, sobre
    if ruta == "/ofertas":
        return 200, cargar("ofertas_vacio" if vacio else "ofertas")
    if ruta == "/parametros":
        return 200, cargar("parametros")
    if ruta == "/finanzas":
        return 200, cargar("finanzas_vacio" if vacio else "finanzas")
    if ruta == "/acciones":
        return 200, cargar("acciones")
    if ruta == "/registro":
        sobre = cargar("registro_vacio" if vacio else "registro")
        d = sobre["datos"]
        lineas = d["lineas"] + ESTADO["extra"]
        f = {k: (consulta.get(k) or [""])[0] for k in ("oferta", "etapa", "agente")}
        lineas = [l for l in lineas if all(not v or str(l.get(k)) == v for k, v in (("oferta_id", f["oferta"]), ("etapa", f["etapa"]), ("agente", f["agente"])))]
        desde = consulta.get("desde", [None])[0]
        limite = int((consulta.get("limite") or ["200"])[0])
        if desde is None:
            sel = lineas[-limite:]
        else:
            sel = [l for l in lineas if l["n"] >= int(desde)][:limite]
        d = {"lineas": sel, "total": len(lineas), "siguiente": (sel[-1]["n"] + 1) if sel else (int(desde) if desde else 1), "cadena_ok": d["cadena_ok"]}
        sobre["datos"] = d
        return 200, sobre
    if ruta.startswith("/job/"):
        job = ESTADO["jobs"].get(ruta.split("/")[2])
        if not job:
            return 404, {"ok": False, "error": {"codigo": "no_existe", "mensaje": "Ese job no existe."}}
        desde = int((consulta.get("desde") or ["0"])[0])
        t = time.time() - job["t0"]
        todas = job["lineas"]
        visibles = todas[: min(len(todas), int(t / 0.5) + 1)]
        terminado = len(visibles) >= len(todas)
        salida = "".join(visibles)[desde:]
        return 200, {"ok": True, "datos": {"job_id": ruta.split("/")[2], "estado": "ok" if terminado else "corriendo", "terminado": terminado, "codigo": 0 if terminado else None,
                                          "desde": desde, "salida": salida, "siguiente": len("".join(visibles)), "truncado": False}, "fuente": [], "generado_en": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "vacio": False, "avisos": []}
    return 404, {"ok": False, "error": {"codigo": "no_existe", "mensaje": "Ruta de API desconocida."}}


class Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):  # silencio
        return

    def _json(self, estado: int, cuerpo: dict):
        datos = json.dumps(cuerpo, ensure_ascii=False).encode()
        self.send_response(estado)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(datos)

    def _token_ok(self) -> bool:
        return self.headers.get("X-Panel-Token") == TOKEN

    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith("/api/"):
            if not self._token_ok():
                return self._json(403, {"ok": False, "error": {"codigo": "token_invalido", "mensaje": "Falta o no coincide X-Panel-Token."}})
            if u.path == "/api/eventos":
                return self._sse()
            estado, sobre = respuesta_api(u.path[4:], parse_qs(u.query))
            return self._json(estado, sobre)
        ruta = u.path.lstrip("/") or "index.html"
        destino = (WEB / ruta).resolve()
        if WEB.resolve() not in destino.parents and destino != WEB.resolve() or not destino.is_file():
            self.send_response(404)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", "9")
            self.end_headers()
            self.wfile.write(b"no existe")
            return
        datos = destino.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", TIPOS.get(destino.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(datos)

    def do_POST(self):
        u = urlparse(self.path)
        if not self._token_ok():
            return self._json(403, {"ok": False, "error": {"codigo": "token_invalido", "mensaje": "Falta o no coincide X-Panel-Token."}})
        n = int(self.headers.get("Content-Length") or 0)
        cuerpo = json.loads(self.rfile.read(n) or b"{}")
        env = {"fuente": [], "generado_en": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "vacio": False, "avisos": []}
        if u.path == "/api/pausa":
            ESTADO["pausa"] = {"activa": True, "desde": env["generado_en"], "motivo": str(cuerpo.get("motivo", ""))[:300]}
            return self._json(200, {"ok": True, "datos": ESTADO["pausa"], **env})
        if u.path == "/api/accion":
            jid = uuid.uuid4().hex[:12]
            ESTADO["jobs"][jid] = {"t0": time.time(), "lineas": [f"$ {cuerpo.get('id')} {json.dumps(cuerpo.get('args', {}), ensure_ascii=False)}\n", "leyendo contratos/ejemplos…\n", "ok  contratos/ejemplos/estado.json\n", "ok  contratos/ejemplos/registro.json\n", "2 archivos validados, 0 errores\n"]}
            return self._json(200, {"ok": True, "datos": {"job_id": jid, "accion": cuerpo.get("id"), "comando": f"python -m demo {cuerpo.get('id')}", "inicio": env["generado_en"]}, **env})
        return self._json(404, {"ok": False, "error": {"codigo": "no_existe", "mensaje": "Ruta desconocida."}})

    def _sse(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            self.wfile.write(b"event: ping\ndata: {}\n\n")
            self.wfile.flush()
            while True:
                time.sleep(1)
                if ESTADO["eventos"] and int(time.time()) % ESTADO["eventos"] == 0:
                    n = len(cargar("registro")["datos"]["lineas"]) + len(ESTADO["extra"]) + 1
                    ESTADO["extra"].append({"n": n, "schema_version": "1.0.0", "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "ejecucion_id": "RUN-20261106-99", "oferta_id": "OF-202611-02", "etapa": "D8", "agente": "motor", "skill_version": None, "evento": "accion", "herramienta": "demo.en_vivo", "entrada_resumen": f"evento en vivo simulado #{n}", "resultado": {"estado": "ok", "codigo": 0}, "costo_estimado": {"monto": 0, "moneda": "USD"}, "tokens": None, "modo": "dry_run", "hash_previo": None, "hash": "f" * 64})
                    self.wfile.write(b'event: cambio\ndata: {"tipo":"registro","ruta":"empresa/registro.jsonl","ts":"' + time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()).encode() + b'"}\n\n')
                else:
                    self.wfile.write(b"event: ping\ndata: {}\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            return


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--puerto", type=int, default=8791)
    ap.add_argument("--escenario", choices=["lleno", "vacio"], default="lleno")
    ap.add_argument("--eventos", type=int, default=0, help="cada N s emite un evento 'registro' de prueba (0 = ninguno)")
    a = ap.parse_args()
    ESTADO["escenario"] = a.escenario
    ESTADO["eventos"] = a.eventos
    srv = ThreadingHTTPServer(("127.0.0.1", a.puerto), Manejador)
    srv.daemon_threads = True
    print(f"http://127.0.0.1:{a.puerto}/#t={TOKEN}", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
