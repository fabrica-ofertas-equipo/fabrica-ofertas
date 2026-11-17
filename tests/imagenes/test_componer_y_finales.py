"""Pruebas de componer_portadas.py, guia_escena.py y finales_ranuras.py. Sin red; lo que necesita ffmpeg se omite si no está."""
from __future__ import annotations

import json
import math
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.imagenes import componer_portadas as cp
from scripts.imagenes import finales_ranuras as fr
from scripts.imagenes import guia_escena as ge
from tests.imagenes.test_ranuras_kie import png_falso


def rgb_con_rectangulos(dw: int, dh: int, rects: list[tuple[int, int, int, int, tuple[int, int, int]]]) -> bytes:
    buf = bytearray(b"\xe6\xec\xf0" * (dw * dh))                  # fondo gris azulado claro
    for x0, y0, x1, y1, col in rects:
        for y in range(y0, y1):
            for x in range(x0, x1):
                buf[3 * (y * dw + x):3 * (y * dw + x) + 3] = bytes(col)
    return bytes(buf)


class TestGeometria(unittest.TestCase):
    def test_homografia_lleva_las_esquinas(self):
        src = [(0, 0), (100, 0), (100, 200), (0, 200)]
        dst = [(10, 20), (310, 5), (330, 480), (15, 500)]
        H = cp.homografia(src, dst)
        for (x, y), (X, Y) in zip(src, dst):
            w = H[2][0] * x + H[2][1] * y + H[2][2]
            self.assertAlmostEqual((H[0][0] * x + H[0][1] * y + H[0][2]) / w, X, places=6)
            self.assertAlmostEqual((H[1][0] * x + H[1][1] * y + H[1][2]) / w, Y, places=6)
        m = cp.css_matrix3d(H)
        self.assertTrue(m.startswith("matrix3d(") and len(m[9:-1].split(",")) == 16)

    def test_aspecto_real_con_perspectiva(self):
        # rectángulo 2:1 girado 30° sobre Y y 20° sobre X (perspectiva general) y proyectado con f = 1500
        f, ay, ax = 1500.0, math.radians(30), math.radians(20)
        def proy(x, y):
            X, Z = x * math.cos(ay), x * math.sin(ay)
            Y, Z = y * math.cos(ax) - Z * math.sin(ax), y * math.sin(ax) + Z * math.cos(ax)
            Z += 4000
            return (f * X / Z, f * Y / Z)
        q = [proy(-1000, -500), proy(1000, -500), proy(1000, 500), proy(-1000, 500)]
        self.assertAlmostEqual(cp.aspecto_real(q, 0, 0), 2.0, delta=0.1)

    def test_aspecto_real_sin_punto_de_fuga_doble_devuelve_none(self):
        q = [(0, 0), (100, 0), (100, 200), (0, 200)]                  # vista frontal: Zhang y He no aplica y se usa la razón de bordes
        self.assertIsNone(cp.aspecto_real(q, 50, 100))
        self.assertAlmostEqual(cp.aspecto_aproximado(q), 0.5)

    def test_recorte_para_aspecto_no_estira(self):
        x, y, cw, ch = cp.recorte_para_aspecto(1920, 1200, 16 / 9)
        self.assertAlmostEqual(cw / ch, 16 / 9, places=3)
        self.assertEqual(x, 0.0)
        x, y, cw, ch = cp.recorte_para_aspecto(1200, 1600, 0.6)
        self.assertAlmostEqual(cw / ch, 0.6, places=3)
        self.assertEqual(y, 0.0)

    def test_expandir_quad(self):
        q = cp.expandir_quad([(0, 0), (10, 0), (10, 10), (0, 10)], 0.1)
        self.assertAlmostEqual(q[0][0], -0.5)
        self.assertAlmostEqual(q[2][1], 10.5)


class TestDeteccion(unittest.TestCase):
    def test_colores_incluyen_verde_en_sombra(self):
        self.assertEqual(cp.codigo_color(255, 0, 255), 1)
        self.assertEqual(cp.codigo_color(0, 255, 0), 2)
        self.assertEqual(cp.codigo_color(20, 110, 25), 2)         # verde oscuro: sombra sobre el marcador
        self.assertEqual(cp.codigo_color(230, 236, 240), 0)       # fondo
        self.assertEqual(cp.codigo_color(18, 38, 63), 0)          # azul marino del lomo
        self.assertEqual(cp.codigo_color(40, 40, 40), 0)          # marco del dispositivo

    def test_componentes_y_esquinas(self):
        dw, dh = 160, 120
        rgb = rgb_con_rectangulos(dw, dh, [(10, 10, 70, 50, (255, 0, 255)), (90, 20, 130, 100, (0, 255, 0)), (140, 5, 143, 8, (0, 255, 0))])
        comps = cp.componentes(rgb, dw, dh)
        self.assertEqual(sorted(c["color"] for c in comps), ["green", "magenta"])        # el cuadradito de 9 px es ruido
        verde = next(c for c in comps if c["color"] == "green")
        self.assertEqual(cp.esquinas(verde["pix"], dw), [(90.0, 20.0), (129.0, 20.0), (129.0, 99.0), (90.0, 99.0)])

    def test_orden_por_posicion_y_area(self):
        regs = [{"color": "green", "cx": 50, "cy": 5, "area": 10}, {"color": "green", "cx": 10, "cy": 9, "area": 30}, {"color": "magenta", "cx": 1, "cy": 1, "area": 99}]
        self.assertEqual([r["cx"] for r in cp.ordenar(regs, "green", "x_asc")], [10, 50])
        self.assertEqual([r["area"] for r in cp.ordenar(regs, "green", "area_desc")], [30, 10])
        self.assertEqual(len(cp.ordenar(regs, "magenta", "x_asc")), 1)

    @unittest.skipUnless(shutil.which("ffmpeg"), "falta ffmpeg")
    def test_detectar_escena_real(self):
        with tempfile.TemporaryDirectory() as td:
            ruta = Path(td) / "escena.png"
            dw, dh = 256, 256
            rgb = rgb_con_rectangulos(dw, dh, [(20, 20, 140, 100, (255, 0, 255)), (30, 140, 90, 240, (0, 255, 0)), (120, 140, 180, 240, (0, 255, 0))])
            cp.escribir_png(ruta, dw, dh, [rgb[3 * dw * y:3 * dw * (y + 1)] for y in range(dh)], 3)
            det = cp.detectar(ruta)
            self.assertEqual(sum(1 for r in det["regiones"] if r["color"] == "green"), 2)
            self.assertEqual(sum(1 for r in det["regiones"] if r["color"] == "magenta"), 1)
            izq = cp.ordenar(det["regiones"], "green", "x_asc")[0]
            self.assertLess(izq["cx"], 80)
            self.assertAlmostEqual(izq["aspecto_real"], 60 / 100, delta=0.05)

    def test_png_ida_y_vuelta(self):
        with tempfile.TemporaryDirectory() as td:
            ruta = Path(td) / "a.png"
            cp.escribir_png(ruta, 7, 3, [b"\x00\x00\x00\xff" * 7] * 3, 4)
            self.assertEqual(cp.dims_png(ruta), (7, 3))


class TestMascaraYBordes(unittest.TestCase):
    @staticmethod
    def _decodificar_rgba(datos: bytes, ancho: int, alto: int) -> list[bytes]:
        import struct as _st
        import zlib as _zl
        pos, idat = 8, b""
        while pos < len(datos):
            n = _st.unpack(">I", datos[pos:pos + 4])[0]
            tipo = datos[pos + 4:pos + 8]
            if tipo == b"IDAT":
                idat += datos[pos + 8:pos + 8 + n]
            pos += 12 + n
        crudo = _zl.decompress(idat)
        paso = 1 + 4 * ancho
        return [crudo[i * paso + 1:(i + 1) * paso] for i in range(alto)]

    def test_dilatar_filas(self):
        self.assertEqual(cp._dilatar_filas([0b00100], 5, 1), [0b01110])
        self.assertEqual(cp._dilatar_filas([0, 0b00100, 0], 5, 1), [0b01110, 0b01110, 0b01110])
        self.assertEqual(cp._dilatar_filas([0b00001], 5, 2), [0b00111])       # no se sale de los bits del recorte

    def test_suavizar_da_degradado_en_el_borde(self):
        filas = [bytes([0, 0, 255, 255])] * 4
        s = cp._suavizar(filas)
        self.assertTrue(0 < s[1][1] < 255 and 0 < s[1][2] < 255)               # el escalón pasa a degradado
        self.assertEqual(s[1][0], 0)
        self.assertEqual(s[1][3], 255)

    def test_mascara_y_sombra_geometria_y_alfa(self):
        dw, dh = 60, 50
        rgb = rgb_con_rectangulos(dw, dh, [(20, 15, 40, 35, (255, 0, 255))])
        comps = cp.componentes(rgb, dw, dh)
        ms = cp.mascara_y_sombra(rgb, dw, dh, comps[0]["pix"], dilatar=2)
        self.assertEqual((ms["x0"], ms["y0"]), (15, 10))                         # 20 - (2 + 3), 15 - (2 + 3)
        filas = self._decodificar_rgba(ms["mascara"], ms["bw"], ms["bh"])
        centro = filas[ms["bh"] // 2][4 * (ms["bw"] // 2) + 3]
        esquina = filas[0][3]
        self.assertEqual(centro, 255)
        self.assertEqual(esquina, 0)
        # el borde de la región dilatada está suavizado: hay valores intermedios en la fila central
        valores = {filas[ms["bh"] // 2][4 * x + 3] for x in range(ms["bw"])}
        self.assertTrue(any(0 < v < 255 for v in valores))

    @unittest.skipUnless(shutil.which("ffmpeg"), "falta ffmpeg")
    def test_borde_quad_usa_clip_path_y_pantalla_usa_mascara(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            png_falso(base / "ref.png", 60, 80)
            esc = base / "esc.png"
            dw, dh = 200, 200
            rgb = rgb_con_rectangulos(dw, dh, [(20, 20, 100, 100, (255, 0, 255)), (120, 40, 180, 180, (0, 255, 0))])
            cp.escribir_png(esc, dw, dh, [rgb[3 * dw * y:3 * dw * (y + 1)] for y in range(dh)], 3)
            det = cp.detectar(esc, 200)
            asign = [{"nombre": "p", "color": "magenta", "orden": "area_desc", "idx": 0, "ref": "ref.png", "recortar": True},
                     {"nombre": "b", "color": "green", "orden": "x_asc", "idx": 0, "ref": "ref.png", "recortar": True, "borde": "quad", "expandir": 0.01}]
            for a in asign:
                a["_region"] = cp.ordenar(det["regiones"], a["color"], a["orden"])[0]
            html, informe = cp.html_composicion(det, esc, asign, base, 0.02, 0.8, base, 2, 2)
            self.assertEqual(html.count("clip-path:polygon"), 2 * 1)                 # estándar + prefijo -webkit- (una superficie)
            self.assertEqual(html.count("mask-image:url(data:image/png"), 2)         # solo la pantalla (estándar + -webkit-)
            self.assertEqual(len(informe), 2)


class TestGuia(unittest.TestCase):
    def test_svg_lleva_marcadores_lomo_y_canto(self):
        esp = {"ancho": 400, "alto": 400, "desk": [[0, 200], [400, 190]], "superficies": [
            {"id": "m", "tipo": "pantalla", "quad": [[20, 20], [200, 15], [205, 120], [25, 125]]},
            {"id": "b", "tipo": "broszura", "quad": [[50, 220], [150, 210], [155, 380], [55, 390]]}]}
        svg = ge.svg_guia(esp)
        self.assertIn("#FF00FF", svg)
        self.assertIn("#00FF00", svg)
        self.assertIn("#12263F", svg)                              # lomo azul marino
        self.assertEqual(svg.count("<polygon"), 7)


class TestFinales(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.assets = Path(self._td.name)
        for slot, cand, ronda in (("hero", "r2-gpt2-01", 2), ("og", "compuesta-01", 1), ("muestra-6", "gpt2-01", 1)):
            d = self.assets / "candidatos" / slot
            png_falso(d / f"{cand}.png", 60, 60)
            (d / f"{cand}.json").write_text(json.dumps({"slot_id": slot, "candidato": cand, "modelo": "m", "ronda": ronda, "tipo": "directo", "creditos_reales": 10.0, "task_id": "t",
                                                        "estado": "ok"}), encoding="utf-8")
        # un candidato anterior y una escena en el hero, para contar intentos y créditos
        (self.assets / "candidatos/hero/gpt2-r01.json").write_text(json.dumps({"slot_id": "hero", "candidato": "gpt2-r01", "ronda": 1, "tipo": "directo", "creditos_reales": 10.0, "estado": "ok"}), encoding="utf-8")
        self.plan = {"oferta_id": "OF-T", "slots": [
            {"slot_id": "hero", "asset_slot": "hero", "dimensiones_requeridas": {"ancho": 50, "alto": 50, "formato_final": "webp", "peso_max_kb": 150}, "alt_propuesto": "alt hero",
             "seleccion_maker": {"candidato": "r2-gpt2-01"}, "estado_revision": "rehecho_pendiente_de_revision"},
            {"slot_id": "og", "asset_slot": "og", "dimensiones_requeridas": {"ancho": 1200, "alto": 630, "formato_final": "jpg", "peso_max_kb": 150}, "seleccion_maker": {"candidato": "compuesta-01"}},
            {"slot_id": "muestra-6", "asset_slot": "muestra-6", "ilustrativa": True, "reemplazar_con_real_cuando_exista_producto": True,
             "dimensiones_requeridas": {"ancho": 720, "alto": 960, "formato_final": "webp", "peso_max_kb": 90}, "seleccion_maker": {"candidato": "gpt2-01"}}]}
        self.assets_json = {"slots": [
            {"slot_id": "hero", "ancho_px": 1120, "alto_px": 1120, "formato": "webp", "peso_max_kb": 150},
            {"slot_id": "og", "ancho_px": 1200, "alto_px": 675, "formato": "jpg", "peso_max_kb": 150},
            {"slot_id": "muestra-6", "ancho_px": 720, "alto_px": 960, "formato": "webp", "peso_max_kb": 90}]}
        self.revision = {"estrictas": {"PASA": {"og": "compuesta-01"}}, "ilustrativas": {"PASA": {"muestra-6": "gpt2-01"}}}

    def tearDown(self):
        self._td.cleanup()

    def falso(self, origen, destino, ancho, alto, formato, peso):
        Path(destino).parent.mkdir(parents=True, exist_ok=True)
        Path(destino).write_bytes(b"x" * 2048)
        self.convertido = getattr(self, "convertido", []) + [(Path(origen).name, ancho, alto, formato)]
        return {"calidad": 80, "peso_kb": 2.0, "peso_ok": True}

    def test_manifiesto_final(self):
        man = fr.generar_finales(self.plan, self.assets, self.assets_json, self.revision, convertir_fn=self.falso, medir_fn=lambda p: (1120, 1120) if "hero" in p.name else (0, 0))
        por = {e["slot"]: e for e in man["ranuras"]}
        self.assertEqual(por["hero"]["creditos_slot"], 20.0)                        # r2-gpt2-01 + gpt2-r01
        self.assertEqual(por["hero"]["intentos_por_ronda"], {"ronda2": 1, "ronda1": 1})
        self.assertFalse(por["hero"]["aprobado_por_revision"])                      # rehecho: pendiente de la revisión de la ronda 2
        self.assertTrue(por["og"]["aprobado_por_revision"])
        self.assertTrue(por["muestra-6"]["ilustrativa"] and por["muestra-6"]["reemplazar_con_real_cuando_exista_producto"])
        self.assertTrue(por["hero"]["medida_ok"])
        self.assertIn(("compuesta-01.png", 1200, 630, "jpg"), self.convertido)       # el og usa la medida del plan, no la de assets.json
        self.assertIn(("r2-gpt2-01.png", 1120, 1120, "webp"), self.convertido)       # el hero usa la de assets.json
        self.assertEqual(len(por["hero"]["sha256"]), 64)
        self.assertTrue((self.assets / "final/manifiesto-final.json").is_file())

    def test_propuesta_assets_json(self):
        man = fr.generar_finales(self.plan, self.assets, self.assets_json, self.revision, convertir_fn=self.falso, medir_fn=lambda p: (1, 1))
        p = {x["slot_id"]: x for x in man["propuesta_assets_json"]}
        self.assertEqual(p["og"]["campos"]["estado"], "aprobado")
        self.assertEqual(p["hero"]["campos"]["estado"], "asignado")
        self.assertTrue(p["og"]["campos"]["sha256"].startswith("sha256:"))
        self.assertTrue(p["muestra-6"]["campos"]["ilustrativa"])
        self.assertEqual(p["hero"]["accion"], "actualizar")
        sin = fr.propuesta_assets({"slot": "bump", "ancho": 1, "alto": 1, "formato": "webp", "peso_max_kb": 1, "aprobado_por_revision": True, "archivo": "final/bump.webp", "sha256": "a" * 64,
                                   "etiqueta_ia_visible": True}, {"slot_id": "bump", "asset_slot": None}, self.assets_json)
        self.assertEqual(sin["accion"], "crear")

    def test_sin_candidato_elegido_falla(self):
        self.plan["slots"][0]["seleccion_maker"] = None
        with self.assertRaises(SystemExit):
            fr.generar_finales(self.plan, self.assets, self.assets_json, self.revision, convertir_fn=self.falso, medir_fn=lambda p: (1, 1))

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("cwebp") and shutil.which("sips"), "faltan ffmpeg, cwebp o sips")
    def test_conversion_real_webp(self):
        origen = self.assets / "o.png"
        png_falso(origen, 200, 200)
        destino = self.assets / "f" / "o.webp"
        r = fr.convertir(origen, destino, 100, 100, "webp", 150)
        self.assertTrue(destino.is_file() and r["peso_ok"])
        self.assertEqual(fr.medir(destino), (100, 100))


if __name__ == "__main__":
    unittest.main()
