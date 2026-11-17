"""SSE (``/api/eventos``), vigía de cambios y difusor."""
from __future__ import annotations

import json
import os
import time
import unittest

from dashboard.vigia import Difusor, Vigia, clasificar
from tests.dashboard.test_servidor_apoyo import Cliente, OFERTA, PruebaBase


def tocar(ruta, contenido: str) -> None:
    """Escribe y fuerza un mtime nuevo (algunos sistemas de archivos tienen resolución gruesa)."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    antes = ruta.stat().st_mtime_ns if ruta.exists() else 0
    ruta.write_text(contenido, encoding="utf-8")
    os.utime(ruta, ns=(antes + 5_000_000_000, antes + 5_000_000_000))


def parsear(bloque: bytes) -> dict[str, str]:
    campos: dict[str, str] = {}
    for linea in bloque.decode("utf-8").split("\n"):
        if linea and not linea.startswith(":") and ":" in linea:
            k, _, v = linea.partition(":")
            campos[k] = v.lstrip(" ")
    return campos


class PruebaClasificar(unittest.TestCase):
    def test_tipos_por_ruta(self) -> None:
        casos = {
            "ofertas/OF-202611-01/estado.json": "oferta", "ofertas/_ejemplo/05-landing/sitio/index.html": "oferta",
            "empresa/registro.jsonl": "registro", "empresa/costos.jsonl": "registro", "empresa/registro.anclas.jsonl": "registro",
            "empresa/barrido/planes/x.json": "barrido", ".claude/skills/f2/SKILL.md": "skills", ".claude/agents/f2-maker.md": "skills",
            "empresa/PAUSA": "empresa", "empresa/panel/pulido.jsonl": "empresa", "empresa/finanzas/ledger.jsonl": "empresa",
            "empresa/captura/freno.json": "empresa",
        }
        for ruta, tipo in casos.items():
            self.assertEqual(clasificar(ruta), tipo, ruta)


class PruebaDifusor(unittest.TestCase):
    def test_publicar_esperar_y_buffer_circular(self) -> None:
        d = Difusor(capacidad=3)
        self.assertEqual(d.esperar(0, 0.01), [], "sin eventos: vuelve al agotar el tiempo")
        for k in range(5):
            d.publicar({"k": k})
        self.assertEqual([i for i, _ in d.esperar(0, 0.01)], [3, 4, 5], "solo los últimos 3")
        self.assertEqual([e["k"] for _, e in d.esperar(3, 0.01)], [3, 4])
        self.assertEqual(d.ultimo_id, 5)
        d.cerrar()
        self.assertTrue(d.cerrado)
        self.assertEqual(d.esperar(5, 5.0), [], "cerrado: no bloquea")


class PruebaVigia(PruebaBase):
    def vigia(self) -> tuple[Vigia, Difusor]:
        d = Difusor()
        return Vigia(self.raiz, d, intervalo=0.05), d

    def test_la_primera_pasada_es_linea_base_y_sin_cambios_no_hay_eventos(self) -> None:
        v, d = self.vigia()
        self.assertEqual(v.sondear(), [])
        self.assertEqual(v.sondear(), [])
        self.assertEqual(d.ultimo_id, 0)

    def test_detecta_creado_modificado_borrado_con_su_tipo(self) -> None:
        v, d = self.vigia()
        v.sondear()
        tocar(self.raiz / "ofertas" / OFERTA / "estado.json", '{"oferta_id": "OF-202611-77", "fase": "en_test"}')
        tocar(self.raiz / "empresa" / "registro.jsonl", "{}\n")
        tocar(self.raiz / "empresa" / "barrido" / "planes" / "nuevo.json", "{}")
        tocar(self.raiz / ".claude" / "skills" / "f9" / "SKILL.md", "# s")
        tocar(self.raiz / "empresa" / "PAUSA", "{}")
        (self.raiz / "empresa" / "captura" / "freno.json").unlink()
        eventos = {(e["ruta"]): e for e in v.sondear()}
        self.assertEqual(eventos[f"ofertas/{OFERTA}/estado.json"]["tipo"], "oferta")
        self.assertEqual(eventos[f"ofertas/{OFERTA}/estado.json"]["accion"], "modificado")
        self.assertEqual((eventos["empresa/registro.jsonl"]["tipo"], eventos["empresa/registro.jsonl"]["accion"]), ("registro", "creado"))
        self.assertEqual(eventos["empresa/barrido/planes/nuevo.json"]["tipo"], "barrido")
        self.assertEqual(eventos[".claude/skills/f9/SKILL.md"]["tipo"], "skills")
        self.assertEqual(eventos["empresa/PAUSA"]["tipo"], "empresa")
        self.assertEqual((eventos["empresa/captura/freno.json"]["tipo"], eventos["empresa/captura/freno.json"]["accion"]), ("empresa", "borrado"))
        for e in eventos.values():
            self.assertRegex(e["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        self.assertEqual(d.ultimo_id, len(eventos))
        self.assertEqual(v.sondear(), [], "ya consumido: sin cambios no hay eventos")

    def test_no_sigue_enlaces_ni_mira_fuera_de_lo_observado(self) -> None:
        v, _ = self.vigia()
        fuera = self.tmp / "fuera"
        fuera.mkdir()
        (fuera / "a.txt").write_text("a")
        os.symlink(fuera, self.raiz / "empresa" / "enlace")
        v.sondear()
        tocar(fuera / "a.txt", "cambiado")
        tocar(self.raiz / "docs" / "nota.md", "no observado")
        tocar(self.raiz / "dashboard" / "x.py", "no observado")
        self.assertEqual(v.sondear(), [])

    def test_tope_de_archivos_y_colapso_de_avalanchas(self) -> None:
        v, d = self.vigia()
        v.sondear()
        for k in range(250):
            (self.raiz / "empresa" / "barrido" / "crudo").mkdir(parents=True, exist_ok=True)
            (self.raiz / "empresa" / "barrido" / "crudo" / f"q{k}.json").write_text("{}")
        eventos = v.sondear()
        self.assertEqual({e["tipo"] for e in eventos}, {"barrido"})
        self.assertLessEqual(len(eventos), 5, "una avalancha se colapsa en un evento por tipo")
        w = Vigia(self.raiz, Difusor(), tope_archivos=3)
        self.assertEqual(len(w.instantanea()), 3)
        self.assertTrue(w.truncada)

    def test_hilo_publica_en_menos_de_un_par_de_intervalos(self) -> None:
        d = Difusor()
        v = Vigia(self.raiz, d, intervalo=0.05)
        v.iniciar()
        self.addCleanup(v.detener)
        tocar(self.raiz / "empresa" / "registro.jsonl", "{}\n")
        recibidos = []
        limite = time.monotonic() + 5
        while time.monotonic() < limite and not recibidos:
            recibidos = d.esperar(0, 0.1)
        self.assertEqual(recibidos[0][1]["tipo"], "registro")


class PruebaSSE(PruebaBase):
    def abrir(self, **kw):
        app = self.panel(sondeo_sse_s=0.01, **kw)
        c = Cliente(app)
        estado, cab, flujo = c.flujo("/api/eventos")
        self.addCleanup(flujo.close)
        return app, c, estado, cab, flujo

    def test_cabeceras_y_saludo(self) -> None:
        app, c, estado, cab, flujo = self.abrir()
        self.assertEqual(estado, 200)
        self.assertEqual(cab["content-type"], "text/event-stream; charset=utf-8")
        self.assertEqual(cab["cache-control"], "no-store")
        self.assertEqual(cab["x-content-type-options"], "nosniff")
        self.assertNotIn("content-length", cab)
        self.assertEqual(next(flujo), b"retry: 3000\n: conectado\n\n")

    def test_evento_cambio_con_el_formato_del_contrato(self) -> None:
        app, c, estado, cab, flujo = self.abrir()
        next(flujo)
        app.difusor.publicar({"tipo": "oferta", "ruta": "ofertas/OF-202611-77/estado.json", "ts": "2026-11-09T12:00:00Z", "accion": "modificado"})
        campos = parsear(next(flujo))
        self.assertEqual(campos["event"], "cambio")
        self.assertEqual(campos["id"], "1")
        self.assertEqual(json.loads(campos["data"]), {"tipo": "oferta", "ruta": "ofertas/OF-202611-77/estado.json", "ts": "2026-11-09T12:00:00Z"})

    def test_ping_periodico(self) -> None:
        _, _, _, _, flujo = self.abrir(ping_s=0.05)
        next(flujo)
        bloque = next(flujo)
        campos = parsear(bloque)
        self.assertEqual(campos["event"], "ping")
        self.assertRegex(json.loads(campos["data"])["ts"], r"^\d{4}-\d\d-\d\dT")

    def test_ping_por_defecto_es_cada_15_segundos(self) -> None:
        from dashboard import servidor
        self.assertEqual(servidor.PING_S, 15.0)
        self.assertEqual(self.panel().ping_s, 15.0)

    def test_texto_hostil_en_la_ruta_viaja_como_dato_en_una_sola_linea(self) -> None:
        app, c, _, _, flujo = self.abrir()
        next(flujo)
        ruta = "ofertas/x/<script>\nevent: inyectado\ndata: {}\u202e.json"
        app.difusor.publicar({"tipo": "oferta", "ruta": ruta, "ts": "2026-11-09T12:00:00Z"})
        bloque = next(flujo)
        self.assertTrue(bloque.isascii())
        self.assertEqual(bloque.count(b"\n\n"), 1, "un salto de línea en el dato no puede abrir otro evento")
        lineas = [l for l in bloque.decode().split("\n") if l]
        self.assertEqual([l.split(":", 1)[0] for l in lineas], ["id", "event", "data"], "ninguna línea inyectada")
        self.assertEqual(json.loads(parsear(bloque)["data"])["ruta"], ruta)

    def test_last_event_id_reanuda(self) -> None:
        app = self.panel(sondeo_sse_s=0.01)
        for k in range(3):
            app.difusor.publicar({"tipo": "empresa", "ruta": f"empresa/{k}", "ts": "2026-11-09T12:00:00Z"})
        c = Cliente(app)
        _, _, flujo = c.flujo("/api/eventos", cabeceras={"Last-Event-ID": "1"})
        self.addCleanup(flujo.close)
        next(flujo)
        self.assertEqual([parsear(next(flujo))["id"] for _ in range(2)], ["2", "3"])
        _, _, nuevo = c.flujo("/api/eventos")
        self.addCleanup(nuevo.close)
        next(nuevo)
        app.difusor.publicar({"tipo": "empresa", "ruta": "empresa/3", "ts": "2026-11-09T12:00:00Z"})
        self.assertEqual(parsear(next(nuevo))["id"], "4", "una conexión nueva solo ve lo posterior")
        _, _, malo = c.flujo("/api/eventos", cabeceras={"Last-Event-ID": "abc;drop"})
        self.addCleanup(malo.close)
        next(malo)

    def test_limite_de_conexiones_y_liberacion_al_cerrar(self) -> None:
        app = self.panel(sondeo_sse_s=0.01, max_sse=1)
        c = Cliente(app)
        _, _, uno = c.flujo("/api/eventos")
        next(uno)
        r = c.get("/api/eventos")
        self.assertEqual((r.estado, r.json()["error"]["codigo"]), (503, "demasiadas_conexiones"))
        uno.close()
        _, _, dos = c.flujo("/api/eventos")
        self.addCleanup(dos.close)
        self.assertEqual(next(dos), b"retry: 3000\n: conectado\n\n")

    def test_solo_get_y_con_token(self) -> None:
        c = Cliente(self.panel())
        self.assertEqual(c.llamar("POST", "/api/eventos", json_={}).estado, 405)
        self.assertEqual(c.get("/api/eventos", token=False).estado, 403)
        self.assertEqual(c.get("/api/eventos", host="evil.com").estado, 403)

    def test_cerrar_el_panel_termina_los_flujos(self) -> None:
        app, c, _, _, flujo = self.abrir()
        next(flujo)
        app.cerrar()
        with self.assertRaises(StopIteration):
            for _ in range(10):
                next(flujo)

    def test_el_vigia_alimenta_el_flujo(self) -> None:
        app, c, _, _, flujo = self.abrir()
        next(flujo)
        app.vigia.sondear()
        tocar(self.raiz / "ofertas" / OFERTA / "estado.json", "{}")
        app.vigia.sondear()
        campos = parsear(next(flujo))
        self.assertEqual(json.loads(campos["data"])["tipo"], "oferta")
        self.assertEqual(json.loads(campos["data"])["ruta"], f"ofertas/{OFERTA}/estado.json")


if __name__ == "__main__":
    unittest.main()
