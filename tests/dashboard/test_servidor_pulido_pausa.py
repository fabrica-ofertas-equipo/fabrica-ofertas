"""Bitácora de pulido (append-only, atómica, concurrente), su ampliación a lista única de pendientes y botón de PAUSA (crea; nunca borra ni sobrescribe)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import unittest

from tests.dashboard.test_servidor_apoyo import HOSTIL, OFERTA, RAIZ_REPO, Cliente, PruebaBase

ALTA = {"oferta_id": OFERTA, "etapa": "D3", "titulo": "El precio no cuadra", "detalle": "economia.json usa 1900", "severidad": "alta", "tipo": "observacion"}


class PruebaPulido(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.c = self.cliente()
        self.archivo = self.raiz / "empresa" / "panel" / "pulido.jsonl"

    def lineas(self) -> list[dict]:
        return [json.loads(l) for l in self.archivo.read_text(encoding="utf-8").splitlines()]

    def test_sin_bitacora_es_vacio_y_no_crea_nada(self) -> None:
        j = self.c.get("/api/pulido").json()
        self.assertTrue(j["vacio"])
        self.assertEqual(j["datos"], {"entradas": [], "total": 0})
        self.assertEqual(j["fuente"], ["empresa/panel/pulido.jsonl"])
        self.assertFalse((self.raiz / "empresa" / "panel").exists(), "leer no escribe")

    def test_alta_asigna_id_ts_autor_y_estado(self) -> None:
        r = self.c.post("/api/pulido", ALTA)
        self.assertEqual(r.estado, 200)
        d = r.datos
        self.assertEqual((d["id"], d["autor"], d["estado"], d["ts"]), ("PUL-0001", "dueno", "abierta", "2026-11-09T12:00:00Z"))
        for k, v in ALTA.items():
            self.assertEqual(d[k], v)
        self.assertEqual(self.c.post("/api/pulido", {**ALTA, "titulo": "otro"}).datos["id"], "PUL-0002")
        g = self.c.get("/api/pulido").json()
        self.assertFalse(g["vacio"])
        self.assertEqual([e["id"] for e in g["datos"]["entradas"]], ["PUL-0001", "PUL-0002"])
        self.assertEqual(g["datos"]["total"], 2)
        self.assertEqual(self.lineas(), g["datos"]["entradas"], "GET entrega las líneas tal cual")

    def test_defaults_y_oferta_opcional(self) -> None:
        d = self.c.post("/api/pulido", {"etapa": "D1", "titulo": "Regla general"}).datos
        self.assertEqual((d["oferta_id"], d["detalle"], d["severidad"], d["tipo"]), (None, "", "media", "pulido"), "el tipo por defecto es «pulido»")
        self.assertIsNone(self.c.post("/api/pulido", {"etapa": "O0", "titulo": "t", "oferta_id": ""}).datos["oferta_id"])
        self.assertEqual(self.c.post("/api/pulido", {"etapa": "F2", "titulo": "t", "oferta_id": "_ejemplo"}).estado, 200)

    def test_validacion_de_campos(self) -> None:
        malos = [
            {}, {"titulo": "t"}, {"etapa": "D1"}, {**ALTA, "etapa": "D99"}, {**ALTA, "etapa": None}, {**ALTA, "titulo": ""}, {**ALTA, "titulo": "   "},
            {**ALTA, "titulo": "x" * 141}, {**ALTA, "titulo": 5}, {**ALTA, "detalle": "x" * 4001}, {**ALTA, "detalle": ["a"]},
            {**ALTA, "severidad": "critica"}, {**ALTA, "severidad": 3}, {**ALTA, "tipo": "tarea"}, {**ALTA, "tipo": "Pendiente"}, {**ALTA, "oferta_id": "../x"},
            {**ALTA, "oferta_id": 5}, {**ALTA, "autor": "otro"}, {**ALTA, "id": "PUL-0009", "titulo": "t"}, {**ALTA, "ts": "2020-01-01T00:00:00Z"},
            {**ALTA, "estado": "resuelta"},
        ]
        for cuerpo in malos:
            r = self.c.post("/api/pulido", cuerpo)
            self.assertEqual(r.estado, 400, cuerpo)
        self.assertFalse(self.archivo.exists(), "ninguna entrada inválida deja rastro")
        maximo = self.c.post("/api/pulido", {**ALTA, "titulo": "x" * 140, "detalle": "y" * 4000})
        self.assertEqual(maximo.estado, 200)

    def test_texto_hostil_se_guarda_integro_como_dato(self) -> None:
        d = self.c.post("/api/pulido", {**ALTA, "titulo": HOSTIL, "detalle": HOSTIL + "\ncon salto\ty tab"}).datos
        self.assertEqual(d["titulo"], HOSTIL)
        crudo = self.archivo.read_bytes()
        self.assertTrue(crudo.isascii())
        self.assertEqual(len(crudo.splitlines()), 1, "el salto de línea del detalle no parte la línea JSONL")
        g = self.c.get("/api/pulido").datos["entradas"][0]
        self.assertEqual((g["titulo"], g["detalle"]), (HOSTIL, HOSTIL + "\ncon salto\ty tab"))
        sin_control = self.c.post("/api/pulido", {**ALTA, "titulo": "a\x00b\x07c"}).datos
        self.assertEqual(sin_control["titulo"], "abc")

    def test_cambio_de_estado(self) -> None:
        self.c.post("/api/pulido", ALTA)
        r = self.c.post("/api/pulido", {"id": "PUL-0001", "estado": "en_curso"})
        self.assertEqual(r.estado, 200)
        self.assertEqual((r.datos["id"], r.datos["estado"], r.datos["autor"], r.datos["evento"]), ("PUL-0001", "en_curso", "dueno", "estado"))
        antes = self.archivo.read_bytes()
        igual = self.c.post("/api/pulido", {"id": "PUL-0001", "estado": "en_curso"})
        self.assertEqual(igual.datos, {"id": "PUL-0001", "estado": "en_curso", "sin_cambios": True})
        self.assertEqual(self.archivo.read_bytes(), antes, "el mismo estado no agrega línea")
        self.c.post("/api/pulido", {"id": "PUL-0001", "estado": "resuelta"})
        self.c.post("/api/pulido", {"id": "PUL-0001", "estado": "abierta"})
        self.assertEqual([l.get("estado") for l in self.lineas()], ["abierta", "en_curso", "resuelta", "abierta"])
        self.assertEqual(self.c.post("/api/pulido", {"id": "PUL-0009", "estado": "resuelta"}).json()["error"]["codigo"], "entrada_no_encontrada")
        for malo in ({"id": "PUL-0001", "estado": "cerrada"}, {"id": "x", "estado": "resuelta"}, {"id": "PUL-0001"}, {"id": 1, "estado": "resuelta"},
                     {"id": "PUL-0001", "estado": "resuelta", "titulo2": "x"}):
            self.assertEqual(self.c.post("/api/pulido", malo).estado, 400, malo)

    def test_es_append_only_las_lineas_previas_no_cambian(self) -> None:
        previo = b""
        pasos = [ALTA, {**ALTA, "titulo": "segunda"}, {"id": "PUL-0001", "estado": "en_curso"}, {"id": "PUL-0002", "estado": "resuelta"},
                 {**ALTA, "titulo": "tercera", "detalle": HOSTIL}]
        for cuerpo in pasos:
            self.assertEqual(self.c.post("/api/pulido", cuerpo).estado, 200)
            actual = self.archivo.read_bytes()
            self.assertTrue(actual.startswith(previo), "lo ya escrito no se reescribe")
            self.assertGreater(len(actual), len(previo))
            self.assertTrue(actual.endswith(b"\n"))
            previo = actual
        self.assertEqual(len(self.lineas()), 5)
        self.assertEqual([l["id"] for l in self.lineas()], ["PUL-0001", "PUL-0002", "PUL-0001", "PUL-0002", "PUL-0003"])
        for metodo in ("DELETE", "PUT", "PATCH"):
            self.assertEqual(self.c.llamar(metodo, "/api/pulido", json_={}).estado, 405)

    def test_concurrencia_entre_hilos(self) -> None:
        errores = []

        def escribir(k: int) -> None:
            try:
                r = Cliente(self.c.app).post("/api/pulido", {**ALTA, "titulo": f"hilo {k}"})
                assert r.estado == 200, r.cuerpo
            except Exception as exc:  # noqa: BLE001
                errores.append(exc)

        hilos = [threading.Thread(target=escribir, args=(k,)) for k in range(24)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(errores, [])
        lineas = self.lineas()
        self.assertEqual(len(lineas), 24)
        self.assertEqual(sorted(l["id"] for l in lineas), [f"PUL-{k:04d}" for k in range(1, 25)], "ids únicos y correlativos")
        self.assertEqual(sorted(l["titulo"] for l in lineas), sorted(f"hilo {k}" for k in range(24)))

    def test_concurrencia_entre_procesos(self) -> None:
        codigo = (
            "import sys\nfrom pathlib import Path\nfrom dashboard.api_base import Ctx\nfrom dashboard.pulido import Pulido\n"
            "p = Pulido(Ctx(Path(sys.argv[1])))\n"
            "for k in range(12):\n    p.crear({'etapa': 'D1', 'titulo': f'proc {sys.argv[2]}-{k}', 'detalle': 'x' * 3000})\n")
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"}
        procesos = [subprocess.Popen([sys.executable, "-c", codigo, str(self.raiz), str(n)], cwd=RAIZ_REPO, env=env,
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE) for n in range(4)]
        salidas = [p.communicate(timeout=60) for p in procesos]
        for p, (_, err) in zip(procesos, salidas):
            self.assertEqual(p.returncode, 0, err.decode())
        lineas = self.lineas()
        self.assertEqual(len(lineas), 48, "ninguna línea intercalada ni perdida")
        self.assertEqual(len({l["id"] for l in lineas}), 48)
        self.assertEqual(len({l["titulo"] for l in lineas}), 48)

    def test_linea_a_medias_se_ignora_y_no_corrompe_la_siguiente(self) -> None:
        self.c.post("/api/pulido", ALTA)
        with open(self.archivo, "ab") as f:
            f.write(b'{"id": "PUL-0002", "ts": "2026')
        g = self.c.get("/api/pulido").json()
        self.assertEqual([e["id"] for e in g["datos"]["entradas"]], ["PUL-0001"])
        self.assertTrue(any("no se pudieron leer" in a for a in g["avisos"]))
        d = self.c.post("/api/pulido", {**ALTA, "titulo": "después"}).datos
        self.assertEqual(d["id"], "PUL-0002")
        g = self.c.get("/api/pulido").datos["entradas"]
        self.assertEqual([e["titulo"] for e in g], ["El precio no cuadra", "después"], "la línea nueva quedó entera")

    def test_tope_de_tamano_del_archivo(self) -> None:
        self.archivo.parent.mkdir(parents=True)
        self.archivo.write_bytes(b'{"id": "PUL-0001"}\n' * 1_200_000)
        r = self.c.post("/api/pulido", ALTA)
        self.assertEqual((r.estado, r.json()["error"]["codigo"]), (507, "archivo_lleno"))
        self.assertEqual(self.c.get("/api/pulido").estado, 200, "leer un archivo enorme solo toma la cola")

    def test_no_escapa_por_enlaces_simbolicos_y_solo_escribe_en_empresa_panel(self) -> None:
        fuera = self.tmp / "fuera"
        fuera.mkdir()
        os.symlink(fuera, self.raiz / "empresa" / "panel")
        r = self.c.post("/api/pulido", ALTA)
        self.assertEqual(r.estado, 403)
        self.assertEqual(list(fuera.iterdir()), [])
        os.unlink(self.raiz / "empresa" / "panel")
        (self.raiz / "empresa" / "panel").mkdir()
        (fuera / "x.jsonl").write_text("")
        os.symlink(fuera / "x.jsonl", self.raiz / "empresa" / "panel" / "pulido.jsonl")
        self.assertEqual(self.c.post("/api/pulido", ALTA).estado, 403)
        self.assertEqual((fuera / "x.jsonl").read_text(), "")
        os.unlink(self.raiz / "empresa" / "panel" / "pulido.jsonl")
        (self.raiz / "empresa" / "panel").rmdir()
        antes = self.hash_arbol(self.raiz / "ofertas"), self.hash_arbol(self.raiz / "empresa" / "barrido"), (self.raiz / "empresa" / "limites.yaml").read_bytes()
        self.c.post("/api/pulido", ALTA)
        self.c.post("/api/pulido", {"id": "PUL-0001", "estado": "resuelta"})
        despues = self.hash_arbol(self.raiz / "ofertas"), self.hash_arbol(self.raiz / "empresa" / "barrido"), (self.raiz / "empresa" / "limites.yaml").read_bytes()
        self.assertEqual(antes, despues)
        self.assertEqual(sorted(p.name for p in (self.raiz / "empresa" / "panel").iterdir()), ["pulido.jsonl"])


COMPLETA = {"oferta_id": OFERTA, "etapa": "O0", "titulo": "Elegir canal de avisos al celular", "detalle": "Telegram solo saliente u otro, siempre con dos canales.",
            "severidad": "alta", "tipo": "pendiente", "responsable": "dueno", "prioridad": "P1", "origen": "decisiones-del-dueno.md#J-pendientes",
            "categoria": "contexto", "bloquea": ["D7", "OF-202611-77", "activar_campana"], "vence": "2026-11-20"}
OPCIONALES = ("responsable", "prioridad", "origen", "categoria", "bloquea", "vence")


class PruebaListaUnica(PruebaBase):
    """Campos opcionales de la lista única de pendientes (Cerebro v0): aditivos, retrocompatibles y con lista blanca."""

    def setUp(self) -> None:
        super().setUp()
        self.c = self.cliente()
        self.archivo = self.raiz / "empresa" / "panel" / "pulido.jsonl"

    def lineas(self) -> list[dict]:
        return [json.loads(l) for l in self.archivo.read_text(encoding="utf-8").splitlines()]

    def test_alta_completa_guarda_cada_campo_tal_cual(self) -> None:
        r = self.c.post("/api/pulido", COMPLETA)
        self.assertEqual(r.estado, 200, r.cuerpo)
        for k, v in COMPLETA.items():
            self.assertEqual(r.datos[k], v, k)
        self.assertEqual((r.datos["id"], r.datos["autor"], r.datos["estado"]), ("PUL-0001", "dueno", "abierta"))
        self.assertEqual(self.lineas()[0], r.datos)
        self.assertEqual(self.c.get("/api/pulido").datos["entradas"], [r.datos], "GET entrega la línea tal cual, con los campos nuevos")

    def test_sin_campos_nuevos_no_los_escribe_y_las_lineas_viejas_siguen_validas(self) -> None:
        self.escribir("empresa/panel/pulido.jsonl",
                      '{"id":"PUL-0001","ts":"2026-11-01T10:00:00Z","autor":"dueno","evento":"alta","oferta_id":null,"etapa":"D3","titulo":"vieja","detalle":"","severidad":"media","tipo":"observacion","estado":"abierta"}\n'
                      '{"id":"PUL-0002","ts":"2026-11-01T11:00:00Z","autor":"dueno","evento":"alta","oferta_id":null,"etapa":"D1","titulo":"otra","detalle":"x","severidad":"baja","tipo":"decision","estado":"abierta"}\n')
        g = self.c.get("/api/pulido").json()
        self.assertEqual([e["id"] for e in g["datos"]["entradas"]], ["PUL-0001", "PUL-0002"])
        nueva = self.c.post("/api/pulido", {"etapa": "D1", "titulo": "t"}).datos
        self.assertEqual(nueva["id"], "PUL-0003", "el correlativo sigue sobre lo ya escrito")
        for k in OPCIONALES:
            self.assertNotIn(k, nueva, "lo que no se envía no se escribe")
        self.assertEqual(self.c.post("/api/pulido", {"id": "PUL-0001", "estado": "resuelta"}).estado, 200, "el cambio de estado de una línea vieja funciona")
        self.assertEqual(len(self.lineas()), 4)

    def test_tipos_nuevos_y_antiguos_son_validos(self) -> None:
        for tipo in ("pulido", "pendiente", "decision", "leccion", "regla_propuesta", "observacion", "nota"):
            r = self.c.post("/api/pulido", {"etapa": "X2", "titulo": f"tipo {tipo}", "tipo": tipo})
            self.assertEqual((r.estado, r.datos.get("tipo")), (200, tipo))
        self.assertEqual(self.c.post("/api/pulido", {"etapa": "X2", "titulo": "t", "tipo": "regla"}).estado, 400, "«regla» a secas no es un tipo")

    def test_una_regla_propuesta_es_solo_un_pendiente_no_toca_reglas(self) -> None:
        empresa = self.raiz / "empresa"
        antes = {p.name for p in empresa.iterdir()} - {"panel"}, (empresa / "limites.yaml").read_bytes()
        r = self.c.post("/api/pulido", {"etapa": "X2", "titulo": "Regla propuesta: nunca prometer plazos", "tipo": "regla_propuesta", "responsable": "dueno", "prioridad": "P2", "categoria": "regla"})
        self.assertEqual(r.estado, 200)
        self.assertEqual(r.datos["estado"], "abierta", "queda abierta hasta que el dueño la apruebe a mano")
        self.assertEqual(({p.name for p in empresa.iterdir()} - {"panel"}, (empresa / "limites.yaml").read_bytes()), antes, "solo cambia empresa/panel/")
        self.assertFalse((empresa / "memoria").exists(), "el panel no crea memoria ni reglas")

    def test_lista_blanca_de_cada_campo_nuevo(self) -> None:
        malos = [
            {"responsable": "juan"}, {"responsable": "Dueno"}, {"responsable": 1}, {"responsable": ["dueno"]},
            {"prioridad": "P4"}, {"prioridad": "p1"}, {"prioridad": 1}, {"prioridad": "P1 "}, {"prioridad": "alta"},
            {"categoria": "otro"}, {"categoria": "Error"}, {"categoria": 5},
            {"origen": "<script>alert(1)</script>"}, {"origen": "a`b"}, {"origen": "a$(x)"}, {"origen": "a\\b"}, {"origen": "a\"b"}, {"origen": "x" * 81},
            {"origen": "ab\u202ecd"}, {"origen": "a\u200bb"}, {"origen": 5}, {"origen": ["a"]}, {"origen": "-empieza con guion"},
            {"bloquea": "D3"}, {"bloquea": {"D3": 1}}, {"bloquea": [5]}, {"bloquea": ["a/b"]}, {"bloquea": ["a b"]}, {"bloquea": [""]}, {"bloquea": ["../x"]},
            {"bloquea": ["x" * 41]}, {"bloquea": [f"D{i}" for i in range(9)]}, {"bloquea": [["D3"]]},
            {"vence": "2026-13-01"}, {"vence": "2026-02-30"}, {"vence": "20261106"}, {"vence": "2026-W45-1"}, {"vence": "2026-11-06 10:00"}, {"vence": "2026-11-06T10:00:00"},
            {"vence": "2026-11-06T25:00:00Z"}, {"vence": "mañana"}, {"vence": 20261106}, {"vence": "2026-11-06\n"[:-1] + "x"},
        ]
        for extra in malos:
            r = self.c.post("/api/pulido", {**ALTA, **extra})
            self.assertEqual(r.estado, 400, extra)
            self.assertEqual(r.json()["error"]["codigo"], "campo_invalido", extra)
        self.assertFalse(self.archivo.exists(), "ninguna alta inválida deja rastro")

    def test_los_extras_no_permitidos_siguen_siendo_400(self) -> None:
        for extra in ({"autor": "ia"}, {"ts": "2020-01-01T00:00:00Z"}, {"id": "PUL-0001", "titulo": "t"}, {"estado": "resuelta"}, {"evento": "estado"}, {"Prioridad": "P1"}, {"prioridades": "P1"},
                      {"__proto__": "x"}, {"hash": "abc"}):
            self.assertEqual(self.c.post("/api/pulido", {**ALTA, **extra}).estado, 400, extra)
        self.assertFalse(self.archivo.exists())

    def test_valores_vacios_equivalen_a_no_enviado(self) -> None:
        d = self.c.post("/api/pulido", {**ALTA, "responsable": "", "prioridad": None, "origen": "  ", "categoria": "", "bloquea": [], "vence": ""}).datos
        for k in OPCIONALES:
            self.assertNotIn(k, d, k)

    def test_origen_se_sanea_y_los_limites_maximos_pasan(self) -> None:
        d = self.c.post("/api/pulido", {**ALTA, "origen": "  /cerebro-cerrar \t\n sesión 2026-11-06\x00\x07  "}).datos
        self.assertEqual(d["origen"], "/cerebro-cerrar sesión 2026-11-06", "controles fuera, espacios colapsados, letras con tilde válidas")
        self.assertEqual(self.c.post("/api/pulido", {**ALTA, "origen": "docs/00 §0.B, J4 (decisión)"}).datos["origen"], "docs/00 §0.B, J4 (decisión)", "citas de documentos")
        self.assertTrue(self.archivo.read_bytes().isascii(), "el archivo sigue siendo ASCII (JSON escapado)")
        d = self.c.post("/api/pulido", {**ALTA, "origen": "o" * 80, "bloquea": [f"{'b' * 39}{i}" for i in range(8)]}).datos
        self.assertEqual((len(d["origen"]), len(d["bloquea"])), (80, 8))
        d = self.c.post("/api/pulido", {**ALTA, "bloquea": ["D3", "D3", " D3 ", "D4"]}).datos
        self.assertEqual(d["bloquea"], ["D3", "D4"], "sin repetidos y en el orden dado")

    def test_vence_acepta_fecha_y_fecha_hora_z(self) -> None:
        self.assertEqual(self.c.post("/api/pulido", {**ALTA, "vence": "2026-11-20"}).datos["vence"], "2026-11-20")
        self.assertEqual(self.c.post("/api/pulido", {**ALTA, "vence": "2026-11-20T08:30:00Z"}).datos["vence"], "2026-11-20T08:30:00Z")
        self.assertEqual(self.c.post("/api/pulido", {**ALTA, "vence": "2028-02-29"}).estado, 200, "año bisiesto real")
        self.assertEqual(self.c.post("/api/pulido", {**ALTA, "vence": "2027-02-29"}).estado, 400)

    def test_todas_las_combinaciones_de_valores_validos(self) -> None:
        n = 0
        for resp in ("dueno", "ia", "robot", "otro"):
            for pri in ("P0", "P1", "P2", "P3"):
                for cat in ("error", "regla", "pref", "riesgo", "contexto"):
                    d = self.c.post("/api/pulido", {"etapa": "O0", "titulo": "t", "tipo": "pendiente", "responsable": resp, "prioridad": pri, "categoria": cat}).datos
                    self.assertEqual((d["responsable"], d["prioridad"], d["categoria"]), (resp, pri, cat))
                    n += 1
        self.assertEqual(n, 80)
        self.assertEqual(len(self.lineas()), 80)

    def test_texto_hostil_en_los_campos_viejos_sigue_intacto_con_los_nuevos(self) -> None:
        d = self.c.post("/api/pulido", {**COMPLETA, "titulo": HOSTIL, "detalle": HOSTIL}).datos
        self.assertEqual((d["titulo"], d["detalle"]), (HOSTIL, HOSTIL))
        self.assertEqual(len(self.archivo.read_bytes().splitlines()), 1)

    def test_cambio_de_estado_de_un_pendiente_no_agrega_campos_ni_los_pisa(self) -> None:
        self.c.post("/api/pulido", COMPLETA)
        r = self.c.post("/api/pulido", {"id": "PUL-0001", "estado": "en_curso"})
        self.assertEqual(r.datos, {"id": "PUL-0001", "ts": "2026-11-09T12:00:00Z", "autor": "dueno", "evento": "estado", "estado": "en_curso"})
        self.assertEqual(self.c.post("/api/pulido", {"id": "PUL-0001", "estado": "resuelta", "prioridad": "P0"}).estado, 400, "el estado no cambia prioridad ni responsable")
        lineas = self.lineas()
        self.assertEqual(len(lineas), 2)
        self.assertEqual(lineas[0]["prioridad"], "P1")

    def test_las_protecciones_de_hoy_siguen_igual(self) -> None:
        c = self.c
        self.assertEqual(c.post("/api/pulido", COMPLETA, token=False).estado, 403)
        self.assertEqual(c.post("/api/pulido", COMPLETA, token="x" * 43).estado, 403)
        self.assertEqual(c.post("/api/pulido", COMPLETA, origen="http://evil.example").estado, 403)
        self.assertEqual(c.post("/api/pulido", COMPLETA, origen=False).estado, 403)
        grande = json.dumps({**COMPLETA, "detalle": "a" * 70000}).encode()
        self.assertEqual(c.llamar("POST", "/api/pulido", cuerpo=grande, tipo="application/json").estado, 413)
        self.assertEqual(c.llamar("POST", "/api/pulido", cuerpo=b"[1]", tipo="application/json").estado, 400)
        self.assertEqual(c.llamar("DELETE", "/api/pulido").estado, 405)
        self.assertFalse(self.archivo.exists(), "ningún intento rechazado escribe")
        self.assertEqual(c.post("/api/pulido", COMPLETA).estado, 200)

    def test_concurrencia_con_campos_nuevos_ids_unicos(self) -> None:
        errores = []

        def escribir(k: int) -> None:
            try:
                r = Cliente(self.c.app).post("/api/pulido", {**COMPLETA, "titulo": f"hilo {k}", "prioridad": ("P0", "P1", "P2", "P3")[k % 4]})
                assert r.estado == 200, r.cuerpo
            except Exception as exc:  # noqa: BLE001
                errores.append(exc)

        hilos = [threading.Thread(target=escribir, args=(k,)) for k in range(16)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(errores, [])
        self.assertEqual(sorted(l["id"] for l in self.lineas()), [f"PUL-{k:04d}" for k in range(1, 17)])


class PruebaPausa(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.c = self.cliente()
        self.pausa = self.raiz / "empresa" / "PAUSA"

    def test_crea_empresa_pausa_con_ts_motivo_y_origen(self) -> None:
        self.assertFalse(self.pausa.exists())
        r = self.c.post("/api/pausa", {"motivo": "Gasto raro en Meta"})
        self.assertEqual(r.estado, 200)
        d = r.datos
        self.assertTrue(d["creada"])
        self.assertFalse(d["ya_existia"])
        self.assertEqual(d["pausa"], {"activa": True, "desde": "2026-11-09T12:00:00Z", "motivo": "Gasto raro en Meta"})
        self.assertIn("nunca borra", d["como_reanudar"])
        self.assertEqual(json.loads(self.pausa.read_text(encoding="utf-8")), {"ts": "2026-11-09T12:00:00Z", "motivo": "Gasto raro en Meta", "origen": "panel"})
        self.assertEqual(self.c.get("/api/sistema").datos["pausa"]["activa"], True)
        self.assertEqual([p.name for p in (self.raiz / "empresa").iterdir() if p.name.startswith(".")], [], "sin temporales residuales")

    def test_si_ya_existe_no_la_sobrescribe_ni_la_toca(self) -> None:
        self.c.post("/api/pausa", {"motivo": "primera"})
        antes = self.pausa.read_bytes()
        mtime = self.pausa.stat().st_mtime_ns
        r = self.c.post("/api/pausa", {"motivo": "segunda"})
        self.assertEqual((r.datos["creada"], r.datos["ya_existia"]), (False, True))
        self.assertEqual(r.datos["pausa"]["motivo"], "primera")
        self.assertEqual(self.pausa.read_bytes(), antes)
        self.assertEqual(self.pausa.stat().st_mtime_ns, mtime)

    def test_una_pausa_previa_del_motor_se_respeta(self) -> None:
        self.escribir("empresa/PAUSA", "pausa del motor\n")
        r = self.c.post("/api/pausa", {"motivo": "mía"})
        self.assertFalse(r.datos["creada"])
        self.assertEqual(self.pausa.read_text(), "pausa del motor\n")

    def test_nunca_borra_pausa_ni_freno(self) -> None:
        self.c.post("/api/pausa", {"motivo": "x"})
        freno = self.raiz / "empresa" / "captura" / "freno.json"
        antes = freno.read_bytes()
        intentos = [("DELETE", "/api/pausa", None), ("POST", "/api/pausa", {"borrar": True}), ("POST", "/api/pausa", {"accion": "reanudar", "motivo": ""}),
                    ("DELETE", "/api/sistema", None), ("PUT", "/api/pausa", {}), ("POST", "/api/freno", {}), ("DELETE", "/api/freno", None),
                    ("POST", "/api/reanudar", {}), ("POST", "/api/pausa/borrar", {})]
        for metodo, ruta, cuerpo in intentos:
            self.c.llamar(metodo, ruta, **({"json_": cuerpo} if cuerpo is not None else {}))
        self.assertTrue(self.pausa.exists())
        self.assertEqual(freno.read_bytes(), antes)
        for patron, metodos in self.c.app._rutas:
            self.assertFalse({"DELETE", "PUT", "PATCH"} & set(metodos), patron.pattern)
        self.assertEqual(self.c.llamar("DELETE", "/api/pausa").estado, 405)

    def test_motivo_ausente_largo_hostil_o_invalido(self) -> None:
        r = self.c.post("/api/pausa", {})
        self.assertTrue(r.datos["creada"], "un botón de pánico no se rechaza por falta de motivo")
        self.assertIn("sin motivo", r.datos["pausa"]["motivo"])
        self.pausa.unlink()
        self.c.post("/api/pausa", {"motivo": "m" * 900 + "\x00\x07"})
        self.assertEqual(len(json.loads(self.pausa.read_text())["motivo"]), 500)
        self.pausa.unlink()
        self.c.post("/api/pausa", {"motivo": HOSTIL})
        self.assertEqual(json.loads(self.pausa.read_text())["motivo"], HOSTIL)
        self.assertEqual(self.c.get("/api/sistema").datos["pausa"]["motivo"], HOSTIL)
        self.pausa.unlink()
        self.assertEqual(self.c.post("/api/pausa", {"motivo": 5}).estado, 400)
        self.assertFalse(self.pausa.exists())

    def test_crea_la_carpeta_empresa_si_no_existe(self) -> None:
        import shutil
        shutil.rmtree(self.raiz / "empresa")
        self.assertTrue(self.c.post("/api/pausa", {"motivo": "x"}).datos["creada"])
        self.assertTrue(self.pausa.is_file())

    def test_no_sigue_un_enlace_simbolico_en_el_destino(self) -> None:
        fuera = self.tmp / "fuera.txt"
        fuera.write_text("intacto")
        os.symlink(fuera, self.pausa)
        r = self.c.post("/api/pausa", {"motivo": "x"})
        self.assertEqual(r.estado, 403)
        self.assertEqual(fuera.read_text(), "intacto")

    def test_exactamente_una_creacion_con_peticiones_simultaneas(self) -> None:
        resultados = []

        def pausar(k: int) -> None:
            resultados.append(Cliente(self.c.app).post("/api/pausa", {"motivo": f"hilo {k}"}).datos["creada"])

        hilos = [threading.Thread(target=pausar, args=(k,)) for k in range(12)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(sum(resultados), 1)
        self.assertEqual(len(resultados), 12)
        contenido = json.loads(self.pausa.read_text())
        self.assertEqual(set(contenido), {"ts", "motivo", "origen"}, "el archivo está completo, no mezclado")

    def test_la_pausa_queda_en_la_auditoria_sin_tocar_otras_carpetas(self) -> None:
        antes = self.hash_arbol(self.raiz / "ofertas")
        self.c.post("/api/pausa", {"motivo": "x"})
        self.c.post("/api/pausa", {"motivo": "y"})
        lineas = (self.raiz / "empresa" / "panel" / "auditoria.jsonl").read_text().splitlines()
        self.assertEqual(len(lineas), 1, "solo se audita la creación")
        self.assertEqual(json.loads(lineas[0])["evento"], "pausa")
        self.assertEqual(self.hash_arbol(self.raiz / "ofertas"), antes)


if __name__ == "__main__":
    unittest.main()
