"""Pruebas de `guardar_pendiente.py` (solo escribe en una raíz temporal; nunca toca empresa/ ni ofertas/ reales).

Correr (desde la raíz del repositorio): .venv/bin/python .claude/skills/cerebro-cerrar/scripts/test_guardar_pendiente.py
"""
from __future__ import annotations

import datetime as dt
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ_CODIGO = next(p for p in AQUI.parents if (p / "dashboard").is_dir() and (p / "empresa").is_dir())
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(RAIZ_CODIGO))
import guardar_pendiente as gp  # noqa: E402

SCRIPT = AQUI / "guardar_pendiente.py"
AHORA = dt.datetime(2026, 11, 9, 12, 0, 0, tzinfo=dt.timezone.utc)
HOSTIL = "<script>alert('x')</script> <img src=x onerror=alert(1)> ‮gnp.exe"

# Falsos secretos armados por partes: este archivo no debe parecer él mismo una fuga.
FALSOS_SECRETOS = {
    "sk": "sk" + "-" + "A1b2C3d4E5f6G7h8I9j0K1l2",
    "aws": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
    "github": "gh" + "p_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8",
    "slack": "xo" + "xb-" + "1234567890-abcdefghij",
    "stripe": "sk" + "_live_" + "A1b2C3d4E5f6G7h8I9j0K1",
    "jwt": "ey" + "JhbGciOiJIUzI1NiJ9" + "." + "ey" + "JzdWIiOiIxMjM0NTY3ODkwIn0" + "." + "abcDEF123456xyz",
    "pem": "-----BEGIN " + "RSA PRIVATE KEY-----",
    "bearer": "Bear" + "er " + "abcdefghijklmnopqrstuvwxyz012345",
    "telegram": "123456789" + ":" + "AAH" + "x" * 32,
    "asignacion": "pass" + "word" + "=" + "hunter2hunter2hunter2",
    "token": "api" + "_" + "key: " + "abcd1234efgh5678",
    "url": "post" + "gres://admin:" + "s3cr3tpass@db.example.com/x",
    "larga": "Zx9" + "Qw8Er7Ty6Ui5Op4As3Df2Gh1Jk0LmNbVcXzAbCd",
}
NO_SON_SECRETOS = [
    "sha256:" + hashlib.sha256(b"x").hexdigest(),
    "commit " + "a" * 40,
    "Ruta de la clave: <RUTA_DE_TU_CLAVE_PRIVADA>",
    "variable STRIPE_SECRET_KEY en el entorno",
    "clave: ofertas/OF-202611-01/qa/d3-v1.json",
    "la clave privada de firma vive solo en el equipo del dueño",
    "token: STRIPE_TOKEN_DE_PRUEBA_X",
    "OF-202611-01-Elegir-Proveedor-De-Correo-Transaccional-Y-Bandeja",
    "docs/00-decisiones-y-tareas-del-dueno.md §0.B",
    "Fijar y firmar los límites de gasto (techo 300 USD/día, pausa a 3.000 USD perdidos)",
]


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="cerebro-prueba-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.raiz = self.tmp / "repo"
        (self.raiz / "empresa" / "panel").mkdir(parents=True)
        (self.raiz / "ofertas" / "_ejemplo" / "qa").mkdir(parents=True)
        (self.raiz / "ofertas" / "_ejemplo" / "qa" / "d4-v1.json").write_text('{"veredicto":"PASS"}', encoding="utf-8")
        self.pulido = self.raiz / "empresa" / "panel" / "pulido.jsonl"
        self.memoria = self.raiz / "empresa" / "memoria"

    def guardar(self, clase, cuerpo, **kw):
        kw.setdefault("ahora", AHORA)
        return gp.guardar(clase, cuerpo, raiz=self.raiz, **kw)

    def escribir(self, clase, cuerpo, **kw):
        return self.guardar(clase, cuerpo, escribir=True, **kw)

    def lineas(self, ruta: Path) -> list[dict]:
        return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines()]

    def codigo(self, clase, cuerpo, **kw) -> int:
        with self.assertRaises(gp.ErrorCerebro) as cm:
            self.guardar(clase, cuerpo, **kw)
        return cm.exception.salida

    def prueba_ok(self) -> dict:
        return {"ruta": "ofertas/_ejemplo/qa/d4-v1.json"}

    @staticmethod
    def arbol(carpeta: Path) -> dict[str, str]:
        salida = {}
        for d, _, fs in os.walk(carpeta):
            for f in fs:
                p = Path(d) / f
                salida[str(p.relative_to(carpeta))] = hashlib.sha256(p.read_bytes()).hexdigest()
        return salida


class PruebasEspejoDelPanel(Base):
    def test_las_constantes_no_se_desvian_de_dashboard_pulido(self) -> None:
        from dashboard import pulido as panel
        self.assertEqual(gp.ETAPAS_PULIDO, panel.ETAPAS_PULIDO)
        for nombre in ("SEVERIDADES", "RESPONSABLES", "PRIORIDADES", "CATEGORIAS", "LIMITE_TITULO", "LIMITE_DETALLE", "LIMITE_ORIGEN", "LIMITE_BLOQUEA", "LIMITE_ITEM_BLOQUEA"):
            self.assertEqual(getattr(gp, nombre), getattr(panel, nombre), nombre)
        for t in ("pendiente", "regla_propuesta", "decision", "leccion"):
            self.assertIn(t, panel.TIPOS)
        for rx_mio, rx_panel in ((gp.RX_ORIGEN, panel._RX_ORIGEN), (gp.RX_ITEM_BLOQUEA, panel._RX_ITEM_BLOQUEA), (gp.RX_FECHA, panel._RX_FECHA), (gp.RX_FECHA_HORA, panel._RX_FECHA_HORA)):
            self.assertEqual(rx_mio.pattern, rx_panel.pattern)

    def test_la_linea_es_la_que_escribiria_el_panel(self) -> None:
        from dashboard.api_base import Ctx
        from dashboard.pulido import Pulido
        cuerpo = {"oferta_id": "_ejemplo", "etapa": "D3", "titulo": "Elegir canal de avisos", "detalle": "Telegram u otro.", "severidad": "alta", "tipo": "pendiente",
                  "responsable": "dueno", "prioridad": "P1", "origen": "sesión 2026-11-09 /cerebro-cerrar", "categoria": "contexto", "bloquea": ["D7", "gasto"], "vence": "2026-11-20"}
        panel_raiz = self.tmp / "otra"
        (panel_raiz / "empresa").mkdir(parents=True)
        de_panel = Pulido(Ctx(panel_raiz), ahora=lambda: AHORA).crear(cuerpo)
        mio = self.escribir("pendiente", {k: v for k, v in cuerpo.items() if k != "tipo"})["linea"]
        self.assertEqual(mio, de_panel)
        self.assertEqual(list(mio), list(de_panel), "mismo orden de claves")
        self.assertEqual(self.pulido.read_bytes(), (panel_raiz / "empresa" / "panel" / "pulido.jsonl").read_bytes(), "byte a byte")

    def test_el_panel_lee_lo_que_escribe_el_script_y_continua_la_numeracion(self) -> None:
        from dashboard.api_base import Ctx
        from dashboard.pulido import Pulido
        self.escribir("pendiente", {"titulo": "Uno", "prioridad": "P0", "responsable": "dueno"})
        panel = Pulido(Ctx(self.raiz), ahora=lambda: AHORA)
        self.assertEqual([e["id"] for e in panel.listar().datos["entradas"]], ["PUL-0001"])
        self.assertEqual(panel.crear({"etapa": "D1", "titulo": "Dos del panel"})["id"], "PUL-0002")
        self.assertEqual(self.escribir("pendiente", {"titulo": "Tres del script, otra cosa distinta"})["linea"]["id"], "PUL-0003")
        self.assertEqual(panel.cambiar_estado({"id": "PUL-0003", "estado": "resuelta"})["estado"], "resuelta")


class PruebasPendientes(Base):
    def test_previsualizar_no_escribe_ni_crea_carpetas(self) -> None:
        antes = self.arbol(self.raiz)
        for clase, cuerpo in (("pendiente", {"titulo": "t"}), ("regla_propuesta", {"titulo": "r"}), ("decision", {"titulo": "d"}),
                              ("leccion", {"titulo": "l", "leccion": "x", "etapa": "D4", "evidencia": [self.prueba_ok()]})):
            r = self.guardar(clase, cuerpo)
            self.assertEqual(r["modo"], "previsualizacion")
        self.assertEqual(self.arbol(self.raiz), antes)
        self.assertFalse(self.pulido.exists())
        self.assertFalse(self.memoria.exists())

    def test_escribir_agrega_una_linea_con_id_ts_autor_y_estado(self) -> None:
        r = self.escribir("pendiente", {"titulo": "Elegir correo transaccional", "prioridad": "P1", "responsable": "dueno", "bloquea": ["D10", "primera_venta"], "vence": "2026-11-12", "etapa": "D10"})
        self.assertEqual(r["modo"], "escrito")
        linea = self.lineas(self.pulido)[0]
        self.assertEqual(linea, r["linea"])
        self.assertEqual((linea["id"], linea["ts"], linea["autor"], linea["evento"], linea["estado"], linea["tipo"]), ("PUL-0001", "2026-11-09T12:00:00Z", "dueno", "alta", "abierta", "pendiente"))
        self.assertEqual((linea["severidad"], linea["origen"]), ("alta", "sesión 2026-11-09 /cerebro-cerrar"))
        self.assertTrue(self.pulido.read_bytes().isascii() and self.pulido.read_bytes().endswith(b"\n"))
        self.assertEqual(self.escribir("pendiente", {"titulo": "Otra cosa totalmente distinta"})["linea"]["id"], "PUL-0002")

    def test_regla_propuesta_es_un_pendiente_para_el_dueno_nunca_una_regla(self) -> None:
        r = self.escribir("regla_propuesta", {"titulo": "Nunca prometer plazos de resultado", "categoria": "regla", "prioridad": "P2"})
        self.assertEqual((r["linea"]["tipo"], r["linea"]["responsable"], r["linea"]["estado"]), ("regla_propuesta", "dueno", "abierta"))
        self.assertEqual(self.codigo("regla_propuesta", {"titulo": "x propuesta", "responsable": "ia"}), 3, "solo el dueño aprueba reglas")
        self.assertEqual(self.codigo("regla_propuesta", {"titulo": "otra propuesta", "responsable": "robot"}), 3)
        antes = {p: (RAIZ_CODIGO / p).read_bytes() for p in ("empresa/parametros.yaml", "empresa/limites.yaml", "empresa/autonomia.yaml") if (RAIZ_CODIGO / p).exists()}
        self.assertEqual({p: (RAIZ_CODIGO / p).read_bytes() for p in antes}, antes)
        self.assertFalse((self.raiz / "empresa" / "parametros.yaml").exists(), "no crea ni toca archivos de reglas")

    def test_validacion_de_campos_igual_de_estricta_que_el_panel(self) -> None:
        base = {"titulo": "t"}
        malos = [
            {}, {"titulo": ""}, {"titulo": "   "}, {"titulo": "x" * 141}, {"titulo": 5}, {**base, "detalle": "x" * 4001}, {**base, "etapa": "D99"}, {**base, "oferta_id": "../x"},
            {**base, "severidad": "critica"}, {**base, "prioridad": "P4"}, {**base, "prioridad": "p1"}, {**base, "responsable": "juan"}, {**base, "categoria": "otro"},
            {**base, "origen": "<script>"}, {**base, "origen": "x" * 81}, {**base, "bloquea": "D3"}, {**base, "bloquea": ["a/b"]}, {**base, "bloquea": [f"D{i}" for i in range(9)]},
            {**base, "vence": "2026-02-30"}, {**base, "vence": "20261106"}, {**base, "vence": "2026-W45-1"},
            {**base, "autor": "ia"}, {**base, "id": "PUL-0001"}, {**base, "ts": "2020-01-01T00:00:00Z"}, {**base, "estado": "resuelta"}, {**base, "tipo": "pendiente"},
        ]
        for cuerpo in malos:
            self.assertEqual(self.codigo("pendiente", cuerpo), 3, cuerpo)
        self.assertEqual(self.codigo("pendiente", [1, 2]), 3)
        self.assertEqual(self.codigo("nada", {"titulo": "t"}), 2)
        self.assertFalse(self.pulido.exists(), "ninguna entrada inválida deja rastro")
        ok = self.escribir("pendiente", {"titulo": "x" * 140, "detalle": "y" * 4000, "origen": "docs/00 §0.B, J4 (decisión)", "bloquea": ["D3", " D3 ", "D4"], "vence": "2028-02-29T08:00:00Z"})
        self.assertEqual(ok["linea"]["bloquea"], ["D3", "D4"])

    def test_texto_hostil_se_guarda_como_dato_y_se_limpia_de_controles_y_direccion(self) -> None:
        r = self.escribir("pendiente", {"titulo": "A\x00B\x07C  D", "detalle": HOSTIL + "\ncon salto\n\n  y sangría"})
        self.assertEqual(r["linea"]["titulo"], "ABC D")
        self.assertEqual(r["linea"]["detalle"], "<script>alert('x')</script> <img src=x onerror=alert(1)> gnp.exe\ncon salto\n\ny sangría")
        self.assertNotIn("‮", self.pulido.read_text(encoding="ascii"))
        self.assertEqual(len(self.pulido.read_bytes().splitlines()), 1, "el salto del detalle no parte la línea JSONL")

    def test_es_solo_agregar_lo_previo_no_cambia_y_una_linea_a_medias_se_cierra_sin_tocarla(self) -> None:
        previo = b'{"id":"PUL-0001","ts":"2026-11-01T10:00:00Z","autor":"dueno","evento":"alta","oferta_id":null,"etapa":"D3","titulo":"vieja","detalle":"","severidad":"media","tipo":"observacion","estado":"abierta"}\n{"id":"PUL-0002","ts":"2026'
        self.pulido.write_bytes(previo)
        r = self.escribir("pendiente", {"titulo": "nueva y distinta"})
        actual = self.pulido.read_bytes()
        self.assertTrue(actual.startswith(previo), "lo ya escrito no se reescribe")
        self.assertEqual(actual[len(previo)], ord("\n"), "cierra la línea a medias antes de agregar")
        self.assertEqual(r["linea"]["id"], "PUL-0002", "una línea ilegible no ocupa número")
        self.assertEqual(json.loads(actual.splitlines()[-1])["titulo"], "nueva y distinta")

    def test_lineas_antiguas_sin_campos_nuevos_cuentan_para_los_repetidos_y_el_correlativo(self) -> None:
        self.pulido.write_text('{"id":"PUL-0007","ts":"2026-11-01T10:00:00Z","autor":"dueno","evento":"alta","oferta_id":null,"etapa":"D3","titulo":"El precio no cuadra con la economía","detalle":"","severidad":"alta","tipo":"observacion","estado":"abierta"}\n', encoding="utf-8")
        self.assertEqual(self.codigo("pendiente", {"titulo": "El precio no cuadra con la economia"}), 5)
        self.assertEqual(self.escribir("pendiente", {"titulo": "Algo bien distinto"})["linea"]["id"], "PUL-0008")


class PruebasRepetidos(Base):
    def test_lo_ya_guardado_no_se_repite(self) -> None:
        self.escribir("pendiente", {"titulo": "Elegir el primer idioma y mercado"})
        for repetido in ("Elegir el primer idioma y mercado", "elegir el primer idioma y mercado.", "ELEGIR EL PRIMER IDIOMA Y MERCADO!!", "Elegir el primer idioma y el mercado"):
            self.assertEqual(self.codigo("pendiente", {"titulo": repetido}), 5, repetido)
        self.assertEqual(len(self.lineas(self.pulido)), 1)

    def test_el_mensaje_dice_con_que_se_parece_y_se_puede_forzar(self) -> None:
        self.escribir("pendiente", {"titulo": "Elegir el primer idioma y mercado"})
        with self.assertRaises(gp.ErrorCerebro) as cm:
            self.guardar("pendiente", {"titulo": "Elegir primer idioma y mercado"})
        self.assertIn("PUL-0001", cm.exception.mensaje)
        r = self.escribir("pendiente", {"titulo": "Elegir primer idioma y mercado"}, permitir_repetido=True)
        self.assertEqual(r["linea"]["id"], "PUL-0002")

    def test_algo_distinto_pasa_y_lo_parecido_a_medias_solo_avisa(self) -> None:
        self.escribir("pendiente", {"titulo": "Elegir el primer idioma y mercado para la oferta"})
        r = self.guardar("pendiente", {"titulo": "Elegir proveedor de correo transaccional"})
        self.assertEqual(r["similares"], [])
        parecido = self.guardar("pendiente", {"titulo": "Elegir idioma y mercado para la oferta"}, permitir_repetido=True)
        self.assertTrue(parecido["similares"], "lo parecido se muestra aunque se permita")
        self.assertEqual(parecido["similares"][0]["id"], "PUL-0001")

    def test_similitud_basica(self) -> None:
        self.assertEqual(gp.similitud("a", ""), 0.0)
        self.assertEqual(gp.similitud("Fijar límites", "fijar limites"), 1.0)
        self.assertLess(gp.similitud("Fijar límites de gasto", "Elegir proveedor de correo"), gp.SIM_RELEVANTE)
        self.assertGreaterEqual(gp.similitud("Fijar y firmar los límites de gasto", "Fijar los límites de gasto"), gp.SIM_DUP)

    def test_una_decision_reemplazada_deja_de_contar_como_vigente_y_la_bitacora_tambien_cuenta(self) -> None:
        self.escribir("decision", {"titulo": "Una baja al día sin venta"})
        self.assertEqual(self.codigo("decision", {"titulo": "Una baja al dia sin venta"}), 5)
        nueva = self.escribir("decision", {"titulo": "Tres días sin venta antes de bajar", "reemplaza": "DEC-0001"})
        self.assertEqual((nueva["linea"]["id"], nueva["linea"]["reemplaza"]), ("DEC-0002", "DEC-0001"))
        self.escribir("decision", {"titulo": "Una baja al día sin venta"}, permitir_repetido=False)  # ya no es vigente: se puede volver a decidir
        self.pulido.write_text(json.dumps({"id": "PUL-0001", "evento": "alta", "titulo": "Sin abogado para las páginas legales", "tipo": "decision", "estado": "abierta"}) + "\n", encoding="utf-8")
        self.assertEqual(self.codigo("decision", {"titulo": "Sin abogado para las paginas legales"}), 5, "una decisión anotada en la bitácora ya cuenta como guardada")


class PruebasDecisionesYLecciones(Base):
    def test_decision_crea_la_carpeta_solo_al_escribir_con_su_formato(self) -> None:
        self.assertFalse(self.memoria.exists())
        r = self.escribir("decision", {"titulo": "El esqueleto pasa a ser el de Mentor", "detalle": "Se conservan las etapas.", "alcance": "sistema", "etapa": "O0"})
        self.assertTrue(self.memoria.is_dir())
        linea = self.lineas(self.memoria / "decisiones_dueno.jsonl")[0]
        self.assertEqual(linea, r["linea"])
        self.assertEqual((linea["id"], linea["tipo"], linea["autor"], linea["vigente"], linea["reemplaza"], linea["alcance"]), ("DEC-0001", "decision", "dueno", True, None, "sistema"))
        self.assertFalse(self.pulido.exists(), "una decisión no va a la bitácora")

    def test_decision_reemplaza_exige_que_exista_y_el_alcance_es_de_la_lista(self) -> None:
        self.assertEqual(self.codigo("decision", {"titulo": "x", "reemplaza": "DEC-0009"}), 3)
        self.assertEqual(self.codigo("decision", {"titulo": "x", "reemplaza": "malo"}), 3)
        self.assertEqual(self.codigo("decision", {"titulo": "x", "alcance": "galaxia"}), 3)
        self.assertEqual(self.codigo("decision", {"titulo": "x", "detalle": "d" * 1001}), 3)
        self.assertFalse(self.memoria.exists(), "ni una carpeta tras entradas rechazadas")

    def test_leccion_exige_prueba_y_el_script_calcula_el_hash(self) -> None:
        base = {"titulo": "Medir el tiempo con la corrida en frío", "leccion": "Sin medirlo con un novato la promesa de tiempo no se sostiene.", "etapa": "D4"}
        self.assertEqual(self.codigo("leccion", base), 3, "sin prueba no hay lección")
        self.assertEqual(self.codigo("leccion", {**base, "evidencia": []}), 3)
        self.assertEqual(self.codigo("leccion", {**base, "evidencia": [{"ruta": "ofertas/_ejemplo/qa/no-existe.json"}]}), 3)
        r = self.escribir("leccion", {**base, "evidencia": [self.prueba_ok()], "oferta_id": "_ejemplo", "confianza": "B"})
        esperado = "sha256:" + hashlib.sha256((self.raiz / "ofertas/_ejemplo/qa/d4-v1.json").read_bytes()).hexdigest()
        linea = self.lineas(self.memoria / "lecciones.jsonl")[0]
        self.assertEqual(linea["evidencia"], [{"ruta": "ofertas/_ejemplo/qa/d4-v1.json", "sha256": esperado}])
        self.assertEqual((linea["id"], linea["confianza"], linea["estado"], linea["alcance"]), ("LEC-0001", "B", "candidata", "solo_esta_vez"))
        self.assertEqual(r["linea"], linea)

    def test_hash_dado_debe_coincidir_y_se_acepta_con_o_sin_prefijo(self) -> None:
        digest = hashlib.sha256((self.raiz / "ofertas/_ejemplo/qa/d4-v1.json").read_bytes()).hexdigest()
        base = {"titulo": "t lección", "leccion": "l", "etapa": "D4"}
        self.assertEqual(self.codigo("leccion", {**base, "evidencia": [{"ruta": "ofertas/_ejemplo/qa/d4-v1.json", "sha256": "0" * 64}]}), 3)
        self.assertEqual(self.guardar("leccion", {**base, "evidencia": [{"ruta": "ofertas/_ejemplo/qa/d4-v1.json", "sha256": digest}]})["linea"]["evidencia"][0]["sha256"], f"sha256:{digest}")
        self.assertEqual(self.guardar("leccion", {**base, "evidencia": [{"ruta": "ofertas/_ejemplo/qa/d4-v1.json", "sha256": f"sha256:{digest}"}]})["modo"], "previsualizacion")
        self.assertEqual(self.guardar("leccion", {**base, "evidencia": ["ofertas/_ejemplo/qa/d4-v1.json"]})["linea"]["evidencia"][0]["sha256"], f"sha256:{digest}", "una ruta sola también vale")

    def test_rutas_de_prueba_hostiles_se_rechazan(self) -> None:
        (self.tmp / "fuera.txt").write_text("x", encoding="utf-8")
        (self.raiz / ".env").write_text("A=1", encoding="utf-8")
        (self.raiz / "secretos.txt").write_text("x", encoding="utf-8")
        (self.raiz / "clave_privada.pem").write_text("x", encoding="utf-8")
        os.symlink(self.tmp / "fuera.txt", self.raiz / "enlace.txt")
        base = {"titulo": "t lección", "leccion": "l", "etapa": "D4"}
        for ruta in ("../fuera.txt", "/etc/hosts", str(self.tmp / "fuera.txt"), ".env", "secretos.txt", "clave_privada.pem", "enlace.txt", "ofertas//x", "ofertas/_ejemplo/qa", "a" * 201, "ofertas\x00x"):
            self.assertEqual(self.codigo("leccion", {**base, "evidencia": [{"ruta": ruta}]}), 3, ruta)
        self.assertEqual(self.codigo("leccion", {**base, "evidencia": [self.prueba_ok()] * 6}), 3, "hasta 5 pruebas")
        self.assertEqual(self.codigo("leccion", {**base, "evidencia": [{"ruta": "ofertas/_ejemplo/qa/d4-v1.json", "extra": 1}]}), 3)

    def test_confianza_alcance_y_campos_de_la_leccion(self) -> None:
        base = {"titulo": "t lección", "leccion": "l", "etapa": "D4", "evidencia": [self.prueba_ok()]}
        self.assertEqual(self.codigo("leccion", {**base, "confianza": "A"}), 3, "A solo la asigna X2")
        self.assertEqual(self.codigo("leccion", {**base, "confianza": "B"}), 3, "B exige oferta_id")
        self.assertEqual(self.codigo("leccion", {**base, "confianza": "Z"}), 3)
        self.assertEqual(self.codigo("leccion", {**base, "alcance": "galaxia"}), 3)
        self.assertEqual(self.codigo("leccion", {**base, "leccion": "x" * 281}), 3)
        self.assertEqual(self.codigo("leccion", {k: v for k, v in base.items() if k != "etapa"}), 3)
        self.assertEqual(self.codigo("leccion", {**base, "autor": "ia"}), 3)
        self.assertEqual(self.guardar("leccion", {**base, "leccion": "x" * 280, "alcance": "nicho"})["linea"]["alcance"], "nicho")


class PruebasSecretos(Base):
    def test_se_reconocen_claves_y_tokens(self) -> None:
        for nombre, valor in FALSOS_SECRETOS.items():
            self.assertIsNotNone(gp.buscar_secreto(f"Usa esto: {valor} para entrar"), nombre)

    def test_lo_normal_no_se_confunde_con_un_secreto(self) -> None:
        for texto in NO_SON_SECRETOS:
            self.assertIsNone(gp.buscar_secreto(texto), texto)

    def test_un_secreto_en_cualquier_campo_rechaza_y_no_deja_rastro(self) -> None:
        falso = FALSOS_SECRETOS["sk"]
        casos = [("pendiente", {"titulo": f"Pegar {falso}"}), ("pendiente", {"titulo": "t", "detalle": f"clave {falso}"}), ("pendiente", {"titulo": "t", "origen": falso}),
                 ("pendiente", {"titulo": "t", "bloquea": [falso[:30]]}), ("decision", {"titulo": "t", "detalle": FALSOS_SECRETOS["jwt"]}),
                 ("leccion", {"titulo": "t", "leccion": FALSOS_SECRETOS["github"], "etapa": "D4", "evidencia": [self.prueba_ok()]}),
                 ("pendiente", {"titulo": "t", "campo_raro": FALSOS_SECRETOS["pem"]})]
        for clase, cuerpo in casos:
            with self.assertRaises(gp.ErrorCerebro) as cm:
                self.escribir(clase, cuerpo)
            self.assertIn(cm.exception.salida, (3, 4))
            self.assertNotIn(falso, cm.exception.mensaje)
        self.assertFalse(self.pulido.exists())
        self.assertFalse(self.memoria.exists())

    def test_el_error_nunca_repite_el_valor(self) -> None:
        for valor in FALSOS_SECRETOS.values():
            with self.assertRaises(gp.ErrorCerebro) as cm:
                self.guardar("pendiente", {"titulo": f"x {valor} y"})
            self.assertEqual(cm.exception.salida, 4)
            self.assertNotIn(valor, cm.exception.mensaje)


class PruebasArchivo(Base):
    def test_un_enlace_simbolico_como_destino_o_carpeta_que_escapa_no_se_escribe(self) -> None:
        fuera = self.tmp / "fuera"
        fuera.mkdir()
        (fuera / "x.jsonl").write_text("", encoding="utf-8")
        os.symlink(fuera / "x.jsonl", self.pulido)
        self.assertEqual(self.codigo("pendiente", {"titulo": "t"}, escribir=True), 6)
        self.assertEqual((fuera / "x.jsonl").read_text(), "")
        self.pulido.unlink()
        os.symlink(fuera, self.memoria)
        self.assertEqual(self.codigo("decision", {"titulo": "t"}, escribir=True), 6)
        self.assertEqual(list(fuera.iterdir()), [fuera / "x.jsonl"])

    def test_destino_que_es_una_carpeta_falla_limpio(self) -> None:
        self.pulido.mkdir()
        self.assertEqual(self.codigo("pendiente", {"titulo": "t"}, escribir=True), 6)

    def test_solo_toca_el_archivo_de_destino(self) -> None:
        (self.raiz / "empresa" / "limites.yaml").write_text("x: null\n", encoding="utf-8")
        antes = self.arbol(self.raiz)
        self.escribir("pendiente", {"titulo": "t"})
        despues = self.arbol(self.raiz)
        cambiados = {k for k in despues if despues[k] != antes.get(k)}
        self.assertEqual(cambiados, {"empresa/panel/pulido.jsonl"})
        self.escribir("decision", {"titulo": "d"})
        self.assertEqual({k for k in self.arbol(self.raiz) if k not in despues}, {"empresa/memoria/decisiones_dueno.jsonl"})

    def test_archivo_enorme_se_rechaza(self) -> None:
        self.pulido.write_bytes(b'{"id":"PUL-0001"}\n' * 1_200_000)
        self.assertEqual(self.codigo("pendiente", {"titulo": "t"}, escribir=True), 6)

    def test_concurrencia_entre_hilos_ids_unicos(self) -> None:
        errores = []

        def escribir(k: int) -> None:
            try:
                self.escribir("pendiente", {"titulo": f"hilo numero {k} con texto propio {'abcdefghijklmnopqrstuvwxyz'[k % 26]}{k * 7919}"}, permitir_repetido=True)
            except Exception as exc:  # noqa: BLE001
                errores.append(exc)

        hilos = [threading.Thread(target=escribir, args=(k,)) for k in range(20)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join()
        self.assertEqual(errores, [])
        self.assertEqual(sorted(l["id"] for l in self.lineas(self.pulido)), [f"PUL-{k:04d}" for k in range(1, 21)])

    def test_concurrencia_entre_procesos_ninguna_linea_intercalada(self) -> None:
        codigo = (
            "import sys\nfrom pathlib import Path\nsys.path.insert(0, sys.argv[1])\nimport guardar_pendiente as gp\n"
            "for k in range(8):\n    gp.guardar('pendiente', {'titulo': f'proceso {sys.argv[3]} paso {k}', 'detalle': 'x' * 3000 + f' {sys.argv[3]}{k}'}, raiz=Path(sys.argv[2]), escribir=True, permitir_repetido=True)\n")
        procesos = [subprocess.Popen([sys.executable, "-c", codigo, str(AQUI), str(self.raiz), str(n)], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for n in range(4)]
        for p in procesos:
            _, err = p.communicate(timeout=120)
            self.assertEqual(p.returncode, 0, err.decode())
        lineas = self.lineas(self.pulido)
        self.assertEqual(len(lineas), 32)
        self.assertEqual(len({l["id"] for l in lineas}), 32)

    def test_listar_es_solo_lectura_y_filtra(self) -> None:
        antes = self.arbol(self.raiz)
        self.assertEqual(gp.listar(self.raiz)["conteo"], {"pendiente": 0, "regla_propuesta": 0, "preferencia": 0, "decision": 0, "leccion": 0})
        self.assertEqual(self.arbol(self.raiz), antes)
        self.assertFalse(self.memoria.exists())
        self.escribir("pendiente", {"titulo": "Fijar los limites de gasto", "prioridad": "P0", "responsable": "dueno"})
        self.escribir("pendiente", {"titulo": "Cerrar los choques de valores", "prioridad": "P2"})
        self.escribir("regla_propuesta", {"titulo": "Nunca prometer plazos"})
        self.escribir("decision", {"titulo": "Sin abogado para las paginas legales"})
        with self.pulido.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"id": "PUL-0001", "ts": "2026-11-09T13:00:00Z", "autor": "dueno", "evento": "estado", "estado": "resuelta"}) + "\n")
        todo = gp.listar(self.raiz)
        self.assertEqual(todo["conteo"], {"pendiente": 2, "regla_propuesta": 1, "preferencia": 0, "decision": 1, "leccion": 0})
        self.assertEqual([x["estado"] for x in todo["guardado"]["pendiente"]], ["resuelta", "abierta"])
        self.assertEqual(gp.listar(self.raiz, "pendiente", solo_abiertas=True)["conteo"], {"pendiente": 1})
        with self.assertRaises(gp.ErrorCerebro):
            gp.listar(self.raiz, "inventada")


class PruebasLineaDeComandos(Base):
    def correr(self, *args: str, entrada: str | None = None):
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"}
        return subprocess.run([sys.executable, str(SCRIPT), *args, "--raiz", str(self.raiz)], input=entrada, capture_output=True, text=True, env=env, timeout=60)

    def test_previsualiza_por_defecto_y_escribe_con_escribir(self) -> None:
        r = self.correr("pendiente", "--json", '{"titulo": "Elegir canal de avisos", "prioridad": "P1"}')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["modo"], "previsualizacion")
        self.assertFalse(self.pulido.exists())
        r = self.correr("pendiente", "--stdin", "--escribir", entrada=json.dumps({"titulo": "Elegir canal de avisos", "prioridad": "P1", "detalle": "con 'comillas' y \"dobles\""}))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["linea"]["id"], "PUL-0001")
        self.assertEqual(len(self.lineas(self.pulido)), 1)

    def test_codigos_de_salida(self) -> None:
        self.assertEqual(self.correr("pendiente").returncode, 2, "falta la entrada")
        self.assertEqual(self.correr("inventada", "--json", "{}").returncode, 2)
        self.assertEqual(self.correr("pendiente", "--json", "{}", "--stdin", entrada="{}").returncode, 2, "no los dos")
        self.assertEqual(self.correr("pendiente", "--json", "no es json").returncode, 3)
        self.assertEqual(self.correr("pendiente", "--json", '{"titulo": NaN}').returncode, 3)
        self.assertEqual(self.correr("pendiente", "--json", '{"titulo": ""}').returncode, 3)
        self.assertEqual(self.correr("pendiente", "--json", json.dumps({"titulo": f"clave {FALSOS_SECRETOS['aws']}"})).returncode, 4)
        self.correr("pendiente", "--json", '{"titulo": "Elegir el primer idioma"}', "--escribir")
        self.assertEqual(self.correr("pendiente", "--json", '{"titulo": "Elegir el primer idioma"}', "--escribir").returncode, 5)
        self.assertEqual(self.correr("pendiente", "--json", '{"titulo": "Elegir el primer idioma"}', "--escribir", "--permitir-repetido").returncode, 0)
        r = subprocess.run([sys.executable, str(SCRIPT), "pendiente", "--json", "{}", "--raiz", str(self.tmp / "no-existe")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)
        self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), "--no-existe"], capture_output=True, text=True).returncode, 2)

    def test_stderr_es_json_y_nunca_trae_el_secreto(self) -> None:
        r = self.correr("pendiente", "--json", json.dumps({"titulo": "t", "detalle": FALSOS_SECRETOS["stripe"]}))
        self.assertEqual(r.returncode, 4)
        error = json.loads(r.stderr)
        self.assertEqual((error["ok"], error["codigo"]), (False, "parece_secreto"))
        self.assertNotIn(FALSOS_SECRETOS["stripe"], r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")

    def test_listar_por_linea_de_comandos(self) -> None:
        self.correr("pendiente", "--json", '{"titulo": "Una cosa por hacer"}', "--escribir")
        r = self.correr("listar", "--clase", "pendiente", "--abiertas")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["conteo"], {"pendiente": 1})

    def test_main_en_proceso_devuelve_el_codigo(self) -> None:
        salida, error = io.StringIO(), io.StringIO()
        with redirect_stdout(salida), redirect_stderr(error):
            codigo = gp.main(["pendiente", "--json", '{"titulo": "t"}', "--raiz", str(self.raiz)])
        self.assertEqual(codigo, 0)
        self.assertEqual(json.loads(salida.getvalue())["modo"], "previsualizacion")


if __name__ == "__main__":
    unittest.main(verbosity=1)
