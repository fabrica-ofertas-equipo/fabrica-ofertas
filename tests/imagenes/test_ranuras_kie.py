"""Pruebas de scripts/imagenes/ranuras_kie.py y portadas_planas.py. Sin red ni credenciales: Kie se simula con un doble.

Ejecutar: .venv/bin/python -m unittest discover -s tests/imagenes -t .
"""
from __future__ import annotations

import io
import json
import os
import random
import re
import struct
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from pathlib import Path

from scripts.imagenes import portadas_planas as pp
from scripts.imagenes import ranuras_kie as rk


def png_falso(ruta: Path, ancho: int = 150, alto: int = 200, ruido: bool = True) -> None:
    """PNG RGB válido (con ruido para pesar más que MIN_BYTES y no estar vacío)."""
    rnd = random.Random(7)
    filas = b"".join(b"\x00" + (bytes(rnd.randrange(256) for _ in range(ancho * 3)) if ruido else b"\x10" * ancho * 3) for _ in range(alto))

    def trozo(tipo: bytes, datos: bytes) -> bytes:
        return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)

    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0)) +
                     trozo(b"IDAT", zlib.compress(filas)) + trozo(b"IEND", b""))


class KieFalso:
    """Doble de rk.Kie: no hace red. Anota las llamadas."""

    def __init__(self, creditos_por_tarea: float = 18.0, fallar: bool = False):
        self.crear_llamadas: list[tuple] = []
        self.subidas: list[str] = []
        self.creditos_por_tarea = creditos_por_tarea
        self.fallar = fallar

    def subir(self, ruta):
        self.subidas.append(str(ruta))
        return "https://falso.invalid/" + Path(ruta).name

    def crear(self, modelo, entrada, etiqueta="", dur=None):
        self.crear_llamadas.append((modelo, entrada, etiqueta))
        return f"tarea-{len(self.crear_llamadas)}"

    def recuperar(self, tid, destino, etiqueta="", max_seg=0):
        if self.fallar:
            raise RuntimeError("falla simulada")
        png_falso(Path(destino))
        return {"taskId": tid, "creditsConsumed": self.creditos_por_tarea, "state": "success"}

    def creditos(self):
        return 1000.0


def estimar_falso(modelo, entrada):
    return {"nano-banana-pro": 18, "nano-banana-2": 8, "gpt-image-2-image-to-image": 6}[modelo]


def comprobar_sin_externos(png, slot):
    return rk.comprobar_candidato(png, slot, ocr=None, usar_externos=False)


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.assets = Path(self._td.name)
        png_falso(self.assets / "referencias" / "pack.png", 30, 40)
        self.slot = {
            "slot_id": "demo", "ratio": "3:4", "prompt": "prompt exacto de prueba", "referencias": ["referencias/pack.png"],
            "textos_esperados": ["SŁOWOMAPA", "520"], "dimensiones_requeridas": {"ancho": 100, "alto": 133, "peso_max_kb": 90},
            "intentos": [{"modelo": "nano-banana-pro", "n": 1}], "estricto": True,
        }
        self.plan = {"oferta_id": "OF-TEST", "resolution": "2K", "slots": [self.slot], "no_debe_aparecer_global": ["rostros"],
                     "pendientes": [{"slot_id": "x", "razon": "y"}]}

    def tearDown(self):
        self._td.cleanup()


class TestEntradaYTope(Base):
    def test_formatos_de_entrada(self):
        e = rk.construir_entrada("nano-banana-pro", "p", ["u1", "u2"], "1:1", "2K")
        self.assertEqual(e["image_input"], ["u1", "u2"])
        self.assertEqual(e["output_format"], "png")
        e = rk.construir_entrada("gpt-image-2-image-to-image", "p", ["u1"], "3:4", "2K")
        self.assertEqual(e["input_urls"], ["u1"])
        self.assertNotIn("image_input", e)
        e = rk.construir_entrada("nano-banana-pro", "p", [f"u{i}" for i in range(12)], "1:1", "2K")
        self.assertEqual(len(e["image_input"]), 8)                  # tope de referencias del modelo

    def test_modelo_desconocido_y_gpt_sin_refs(self):
        with self.assertRaises(rk.PlanInvalido):
            rk.construir_entrada("otro", "p", ["u"], "1:1", "2K")
        with self.assertRaises(rk.PlanInvalido):
            rk.construir_entrada("gpt-image-2-image-to-image", "p", [], "1:1", "2K")

    def test_estimacion_prudente(self):
        est = rk.estimar_prudente(lambda m, e: 6)
        self.assertEqual(est("gpt-image-2-image-to-image", {}), 10)     # medido > estimado
        self.assertEqual(est("nano-banana-2", {}), 12)
        self.assertEqual(est("otro-modelo", {}), 6)

    def test_tope(self):
        rk.comprobar_tope(800, 100, 900)                            # justo en el tope: pasa
        with self.assertRaises(rk.TopeExcedido):
            rk.comprobar_tope(800, 101, 900)

    def test_plan_invalido(self):
        ruta = self.assets / "plan.json"
        ruta.write_text(json.dumps({"slots": []}), encoding="utf-8")
        with self.assertRaises(rk.PlanInvalido):
            rk.cargar_plan(ruta)
        ruta.write_text(json.dumps({"slots": [{"slot_id": "a", "ratio": "1:1", "prompt": "p", "intentos": [{"modelo": "x"}]}]}), encoding="utf-8")
        with self.assertRaises(rk.PlanInvalido):
            rk.cargar_plan(ruta)


class TestGeneracion(Base):
    def generar(self, cliente, tope=900, **kw):
        return rk.ejecutar_plan(cliente, estimar_falso, self.plan, self.assets, tope, comprobar=comprobar_sin_externos, **kw)

    def test_escribe_candidato_y_trazabilidad(self):
        k = KieFalso()
        hechos = self.generar(k)
        self.assertEqual(len(hechos), 1)
        j = json.loads((self.assets / "candidatos/demo/nbp-01.json").read_text(encoding="utf-8"))
        self.assertTrue((self.assets / "candidatos/demo/nbp-01.png").is_file())
        self.assertEqual(j["estado"], "ok")
        self.assertEqual(j["prompt"], "prompt exacto de prueba")
        self.assertEqual(j["modelo"], "nano-banana-pro")
        self.assertEqual(j["task_id"], "tarea-1")
        self.assertEqual(j["creditos_cotizados"], 18)
        self.assertEqual(j["creditos_reales"], 18.0)
        self.assertEqual(len(j["sha256"]), 64)
        self.assertEqual(j["textos_esperados"], ["SŁOWOMAPA", "520"])
        self.assertTrue(j["comprobaciones"]["codigo_ok"])
        self.assertEqual((j["comprobaciones"]["ancho"], j["comprobaciones"]["alto"]), (150, 200))
        self.assertTrue(j["etiqueta_ia_visible"])
        self.assertEqual(k.crear_llamadas[0][1]["image_input"], ["https://falso.invalid/pack.png"])

    def test_idempotente_no_paga_dos_veces(self):
        k = KieFalso()
        self.generar(k)
        self.generar(k)
        self.assertEqual(len(k.crear_llamadas), 1)

    def test_tope_detiene_antes_de_enviar(self):
        self.slot["intentos"] = [{"modelo": "nano-banana-pro", "n": 3}]
        k = KieFalso()
        with self.assertRaises(rk.TopeExcedido):
            self.generar(k, tope=40)                                 # caben 2 de 18 (36); el tercero (54) no
        self.assertEqual(len(k.crear_llamadas), 2)
        self.assertEqual(rk.gasto_acumulado(self.assets / "candidatos"), 36.0)

    def test_modo_seco_no_envia(self):
        k = KieFalso()
        hechos = rk.ejecutar_plan(k, estimar_falso, self.plan, self.assets, 900, seco=True)
        self.assertEqual(hechos[0]["cotizado"], 18)
        self.assertEqual(k.crear_llamadas, [])
        self.assertFalse((self.assets / "candidatos").exists())

    def test_fallo_de_kie_queda_registrado(self):
        k = KieFalso(fallar=True)
        with self.assertRaises(RuntimeError):
            self.generar(k)
        j = json.loads((self.assets / "candidatos/demo/nbp-01.json").read_text(encoding="utf-8"))
        self.assertEqual(j["estado"], "fallo")
        self.assertEqual(j["task_id"], "tarea-1")                    # se puede retomar con recuperar()
        self.assertEqual(rk.gasto_acumulado(self.assets / "candidatos"), 18.0)   # prudente: cuenta lo cotizado

    def test_reintento_con_correccion(self):
        k = KieFalso()
        self.generar(k)
        reg = rk.generar_candidato(k, estimar_falso, self.plan, self.slot, "nano-banana-pro", self.assets, 900,
                                   correccion="la cifra 520 salió como 502", comprobar=comprobar_sin_externos)
        self.assertEqual(reg["candidato"], "nbp-r01")
        self.assertIn("CORRECCIÓN", reg["prompt"])
        self.assertIn("502", reg["prompt"])
        self.assertTrue(reg["prompt"].startswith("prompt exacto de prueba"))
        self.assertEqual(reg["correccion"], "la cifra 520 salió como 502")
        self.assertTrue((self.assets / "candidatos/demo/nbp-r01.png").exists() or (self.assets / "candidatos/demo/nbp-r01.png").is_file())


class TestComprobaciones(Base):
    def test_ratio_incorrecto_y_pequeno(self):
        png_falso(self.assets / "a.png", 200, 200)                   # 1:1 contra un slot 3:4
        r = rk.comprobar_candidato(self.assets / "a.png", self.slot, ocr=None, usar_externos=False)
        self.assertFalse(r["ratio_ok"])
        self.assertFalse(r["codigo_ok"])
        png_falso(self.assets / "b.png", 30, 40)                     # ratio ok pero menor que lo requerido
        r = rk.comprobar_candidato(self.assets / "b.png", self.slot, ocr=None, usar_externos=False)
        self.assertFalse(r["tamano_suficiente"])

    def test_ratio_de_la_medida_final_si_hay_recorte(self):
        png_falso(self.assets / "o.png", 191, 100)
        slot = {**self.slot, "ratio": "16:9", "dimensiones_requeridas": {"ancho": 190, "alto": 99}, "post": {"recorte_centrado": [191, 100]}}
        self.assertTrue(rk.comprobar_candidato(self.assets / "o.png", slot, ocr=None, usar_externos=False)["ratio_ok"])
        self.assertFalse(rk.comprobar_candidato(self.assets / "o.png", {**slot, "post": None}, ocr=None, usar_externos=False)["ratio_ok"])

    def test_recomprobar_actualiza_json(self):
        rk.ejecutar_plan(KieFalso(), estimar_falso, self.plan, self.assets, 900, comprobar=comprobar_sin_externos)
        j = self.assets / "candidatos/demo/nbp-01.json"
        reg = json.loads(j.read_text(encoding="utf-8"))
        reg["comprobaciones"]["codigo_ok"] = False
        j.write_text(json.dumps(reg), encoding="utf-8")
        self.assertEqual(rk.recomprobar(self.plan, self.assets, comprobar=comprobar_sin_externos), 1)
        self.assertTrue(json.loads(j.read_text(encoding="utf-8"))["comprobaciones"]["codigo_ok"])

    def test_vacia_y_no_png(self):
        png_falso(self.assets / "c.png", 150, 200, ruido=False)      # plano: pesa poco
        r = rk.comprobar_candidato(self.assets / "c.png", self.slot, ocr=None, usar_externos=False)
        self.assertFalse(r["no_pequeno"])
        self.assertFalse(r["codigo_ok"])
        (self.assets / "d.png").write_bytes(b"no soy un png")
        r = rk.comprobar_candidato(self.assets / "d.png", self.slot, ocr=None, usar_externos=False)
        self.assertFalse(r["codigo_ok"])
        self.assertFalse(rk.comprobar_candidato(self.assets / "no-existe.png", self.slot)["codigo_ok"])

    def test_ocr_exacto_y_sin_diacriticos(self):
        r = rk.evaluar_ocr(["SŁOWOMAPA", "520", "Slownictwo angielskie"], ["SŁOWOMAPA", "520", "Słownictwo angielskie", "w mapach myśli"])
        self.assertEqual(r["encontrados_exactos"], ["SŁOWOMAPA", "520"])
        self.assertEqual(r["encontrados_sin_diacriticos_o_dudosos"], ["Słownictwo angielskie"])
        self.assertEqual(r["no_encontrados"], ["w mapach myśli"])
        self.assertEqual(r["tasa_exacta"], 0.5)

    def test_ocr_se_inyecta(self):
        png_falso(self.assets / "e.png", 150, 200)
        r = rk.comprobar_candidato(self.assets / "e.png", self.slot, ocr=lambda p: ["SŁOWOMAPA", "520"], usar_externos=False)
        self.assertEqual(r["ocr"]["tasa_exacta"], 1.0)


class TestManifiestoYClave(Base):
    def test_manifiesto(self):
        rk.ejecutar_plan(KieFalso(), estimar_falso, self.plan, self.assets, 900, comprobar=comprobar_sin_externos)
        self.slot.update(funcion="función", ilustrativa=True, reemplazar_con_real_cuando_exista_producto=True, objetos_esperados=["hoja"],
                         no_debe_aparecer=["bandera"], criterios=["c1"], textos_estrictos=["520"])
        m = rk.construir_manifiesto(self.plan, self.assets, {"saldo_inicio": 10})
        s = m["slots"][0]
        self.assertEqual(s["funcion_en_pagina"], "función")
        self.assertEqual(s["textos_esperados"], ["SŁOWOMAPA", "520"])
        self.assertEqual(s["no_debe_aparecer"], ["rostros", "bandera"])
        self.assertEqual(s["dimensiones_requeridas"]["ancho"], 100)
        self.assertTrue(s["ilustrativa"] and s["reemplazar_con_real_cuando_exista_producto"])
        self.assertTrue(s["rubrica"]["estricto"])
        self.assertEqual(s["candidatos"][0]["ruta_png"], "candidatos/demo/nbp-01.png")
        self.assertEqual(len(s["candidatos"][0]["sha256"]), 64)
        self.assertEqual(m["pendientes"][0]["slot_id"], "x")
        self.assertEqual(m["gasto"]["saldo_inicio"], 10)

    def test_cli_manifiesto_y_elegir(self):
        ruta = self.assets / "plan.json"
        ruta.write_text(json.dumps(self.plan, ensure_ascii=False), encoding="utf-8")
        rk.ejecutar_plan(KieFalso(), estimar_falso, self.plan, self.assets, 900, comprobar=comprobar_sin_externos)
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(rk.main(["elegir", str(ruta), "--assets", str(self.assets), "--slot", "demo", "--candidato", "nbp-01", "--motivo", "texto exacto"]), 0)
            self.assertEqual(rk.main(["manifiesto", str(ruta), "--assets", str(self.assets)]), 0)
        man = json.loads((self.assets / "paquete-revision.json").read_text(encoding="utf-8"))
        self.assertEqual(man["slots"][0]["seleccion_maker"]["candidato"], "nbp-01")

    def test_clave_solo_en_proceso_y_sin_imprimir(self):
        env = self.assets / ".env"
        env.write_text("OTRA=secreto-ajeno\nKIE_API_KEY=clave-de-prueba\n", encoding="utf-8")
        previo = os.environ.pop("KIE_API_KEY", None)
        otra = os.environ.pop("OTRA", None)
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.assertTrue(rk.cargar_clave(env))
            self.assertEqual(os.environ["KIE_API_KEY"], "clave-de-prueba")
            self.assertNotIn("OTRA", os.environ)                    # solo se lee KIE_API_KEY
            self.assertEqual(buf.getvalue(), "")                    # nada impreso
        finally:
            os.environ.pop("KIE_API_KEY", None)
            if previo is not None:
                os.environ["KIE_API_KEY"] = previo
            if otra is not None:
                os.environ["OTRA"] = otra

    def test_ledger(self):
        led = rk.registrar_saldo(self.assets, "inicio", 2000.0, 900)
        led = rk.registrar_saldo(self.assets, "fin", 1950.5, 900)
        self.assertEqual(led["gastado_real_por_saldo"], 49.5)
        self.assertEqual(led["tope_creditos"], 900)


class TestPortadasPlanas(unittest.TestCase):
    def test_html_con_ortografia_polaca_exacta(self):
        spec = json.loads((Path(__file__).resolve().parents[2] / "ofertas/OF-202611-91/05-landing/assets/portadas-planas.json").read_text(encoding="utf-8"))
        c = {**pp.COLORES_DEFECTO, **spec["colores"]}
        for p in spec["portadas"]:
            if p["tipo"] == "og":
                p = {**p, "fondo": "/tmp/placa.png"}                  # el og necesita una placa de fondo
            cuerpo = pp.CONSTRUCTORES[p["tipo"]](p, c)
            cuerpo = re.sub(r'<span style="font-family:[^"]*">–</span>', "–", cuerpo)   # el guion largo va en un span serif
            for t in p["textos"]:
                self.assertIn(pp.esc(t), cuerpo, f"{p['id']}: falta «{t}»")
            self.assertIn("SŁOWOMAPA", cuerpo)

    def test_mapa_lleva_palabra_central(self):
        spec = json.loads((Path(__file__).resolve().parents[2] / "ofertas/OF-202611-91/05-landing/assets/mapas-ilustrativos.json").read_text(encoding="utf-8"))
        c = dict(pp.COLORES_DEFECTO)
        self.assertEqual(len(spec["mapas"]), 7)                    # 6 miniaturas + 1 para muestra-principal
        for m in spec["mapas"]:
            cuerpo = pp.html_mapa(m, c)
            self.assertIn(m["centro_en"], cuerpo)
            self.assertIn(pp.esc(m["tema"]), cuerpo)
            self.assertEqual(len(m["nodos"]), 6)


if __name__ == "__main__":
    unittest.main()
