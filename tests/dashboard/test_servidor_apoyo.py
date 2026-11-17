"""Ayudas de las pruebas del servidor del panel (P1): cliente WSGI directo, raíces temporales y fixtures.

Las pruebas llaman a la aplicación WSGI con ``environ`` (sin sockets: ``socket.socket`` queda bloqueado salvo en
``test_servidor_http_real``) y SIEMPRE sobre una copia temporal de ``tests/fixtures/dashboard/servidor/raiz/``: nunca
tocan ``empresa/`` ni ``ofertas/`` reales.
"""
from __future__ import annotations

import datetime as _dt
import io
import json
import os
import shutil
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest import mock

from dashboard.servidor import Panel

RAIZ_REPO = Path(__file__).resolve().parents[2]
FIXTURES = RAIZ_REPO / "tests" / "fixtures" / "dashboard" / "servidor"
RAIZ_FIXTURE = FIXTURES / "raiz"
PUERTO = 8765
AHORA = _dt.datetime(2026, 11, 9, 12, 0, 0, tzinfo=_dt.timezone.utc)
OFERTA = "OF-202611-77"
CORRIDA = "2026-11-06-z"
HOSTIL = "<script>alert('x')</script> <img src=x onerror=alert(1)> ‮gnp.exe"


def reloj_fijo(momento: _dt.datetime = AHORA):
    return lambda: momento


@dataclass
class Respuesta:
    estado: int
    cabeceras: dict[str, str]
    cuerpo: bytes

    def json(self) -> Any:
        return json.loads(self.cuerpo.decode("utf-8"))

    @property
    def datos(self) -> Any:
        return self.json()["datos"]


class Cliente:
    """Arma el ``environ`` de PEP 3333 y llama a la aplicación WSGI directamente."""

    def __init__(self, app: Any, puerto: int = PUERTO, token: str | None = None) -> None:
        self.app = app
        self.puerto = puerto
        self.token = token if token is not None else getattr(app, "token", None)

    def environ(self, metodo: str, ruta: str, *, consulta: str = "", cuerpo: bytes | None = None, json_: Any = None,
                cabeceras: dict[str, str] | None = None, token: bool | str = True, origen: bool | str | None = None,
                host: str | None = None, tipo: str | None = None) -> dict[str, Any]:
        if json_ is not None:
            cuerpo = json.dumps(json_).encode("utf-8")
            tipo = tipo or "application/json"
        env: dict[str, Any] = {
            "REQUEST_METHOD": metodo, "PATH_INFO": ruta.encode("utf-8").decode("latin-1"), "QUERY_STRING": consulta, "SERVER_NAME": "127.0.0.1",
            "SERVER_PORT": str(self.puerto), "SERVER_PROTOCOL": "HTTP/1.1", "HTTP_HOST": host if host is not None else f"127.0.0.1:{self.puerto}",
            "wsgi.input": io.BytesIO(cuerpo or b""), "wsgi.url_scheme": "http", "REMOTE_ADDR": "127.0.0.1",
        }
        if cuerpo is not None:
            env["CONTENT_LENGTH"] = str(len(cuerpo))
        if tipo:
            env["CONTENT_TYPE"] = tipo
        if token is True and self.token:
            env["HTTP_X_PANEL_TOKEN"] = self.token
        elif isinstance(token, str):
            env["HTTP_X_PANEL_TOKEN"] = token
        if origen is True or (origen is None and metodo == "POST"):
            env["HTTP_ORIGIN"] = f"http://127.0.0.1:{self.puerto}"
        elif isinstance(origen, str):
            env["HTTP_ORIGIN"] = origen
        for k, v in (cabeceras or {}).items():
            env["HTTP_" + k.upper().replace("-", "_")] = v
        return env

    def llamar(self, metodo: str, ruta: str, **kw: Any) -> Respuesta:
        estado: list[Any] = []

        def start_response(linea: str, cab: list[tuple[str, str]], exc_info: Any = None) -> None:
            estado.append((int(linea.split(" ", 1)[0]), {k.lower(): v for k, v in cab}))

        iterable = self.app(self.environ(metodo, ruta, **kw), start_response)
        try:
            cuerpo = b"".join(iterable)
        finally:
            if hasattr(iterable, "close"):
                iterable.close()
        return Respuesta(estado[0][0], estado[0][1], cuerpo)

    def flujo(self, ruta: str, **kw: Any) -> tuple[int, dict[str, str], Any]:
        """Para SSE: ``(estado, cabeceras, iterador)`` SIN consumir el cuerpo."""
        estado: list[Any] = []

        def start_response(linea: str, cab: list[tuple[str, str]], exc_info: Any = None) -> None:
            estado.append((int(linea.split(" ", 1)[0]), {k.lower(): v for k, v in cab}))

        iterable = self.app(self.environ("GET", ruta, **kw), start_response)
        return estado[0][0], estado[0][1], iterable

    def get(self, ruta: str, **kw: Any) -> Respuesta:
        return self.llamar("GET", ruta, **kw)

    def post(self, ruta: str, json_: Any = None, **kw: Any) -> Respuesta:
        return self.llamar("POST", ruta, json_=json_ if json_ is not None else {}, **kw)


class PruebaBase(unittest.TestCase):
    """Raíz temporal con los fixtures, panel sin vigía y sockets bloqueados."""

    bloquear_sockets = True

    def setUp(self) -> None:
        super().setUp()
        if self.bloquear_sockets:
            p = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red: socket.socket está bloqueado"))
            p.start()
            self.addCleanup(p.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="panel-prueba-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.raiz = self.tmp / "repo"
        shutil.copytree(RAIZ_FIXTURE, self.raiz)
        self.web = self.tmp / "web"
        shutil.copytree(FIXTURES / "web", self.web)

    def panel(self, **kw: Any) -> Panel:
        kw.setdefault("ahora", reloj_fijo())
        kw.setdefault("web_dir", self.web)
        kw.setdefault("acciones_yaml", FIXTURES / "acciones_prueba.yaml")
        kw.setdefault("puerto", PUERTO)
        kw.setdefault("entorno", "prueba")
        app = Panel(self.raiz, **kw)
        self.addCleanup(app.cerrar)
        return app

    def cliente(self, **kw: Any) -> Cliente:
        return Cliente(self.panel(**kw))

    def poner_registro(self, nombre: str = "registro_valido.jsonl", costos: bool = True) -> None:
        (self.raiz / "empresa").mkdir(parents=True, exist_ok=True)
        shutil.copy(FIXTURES / nombre, self.raiz / "empresa" / "registro.jsonl")
        if costos:
            shutil.copy(FIXTURES / "costos_valido.jsonl", self.raiz / "empresa" / "costos.jsonl")

    def escribir(self, rel: str, contenido: str | bytes) -> Path:
        destino = self.raiz / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(contenido, bytes):
            destino.write_bytes(contenido)
        else:
            destino.write_text(contenido, encoding="utf-8")
        return destino

    @staticmethod
    def hash_arbol(carpeta: Path) -> str:
        import hashlib
        h = hashlib.sha256()
        for d, ds, fs in os.walk(carpeta):
            ds.sort()
            for f in sorted(fs):
                p = Path(d) / f
                h.update(str(p.relative_to(carpeta)).encode())
                try:
                    h.update(p.read_bytes())
                except OSError:
                    h.update(b"?")
        return h.hexdigest()
