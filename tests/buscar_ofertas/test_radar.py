"""Pruebas del radar de ofertas (skill buscar-ofertas, scripts/radar.py) y de las señales de joya en ordenar_candidatos.py."""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCR = RAIZ / ".claude" / "skills" / "buscar-ofertas" / "scripts"
LANZAR = RAIZ / ".claude" / "skills" / "modelar-y-lanzar-oferta" / "scripts"
sys.path.insert(0, str(SCR))
sys.path.insert(0, str(LANZAR))
import radar as R  # noqa: E402

AHORA = dt.datetime(2026, 11, 13, 15, 0, tzinfo=dt.timezone.utc)
HOY = AHORA.date()


class TestCatalogoYCola(unittest.TestCase):
    def test_catalogo_cubre_todos_los_idiomas_de_los_mercados(self) -> None:
        cat = R.catalogo()
        faltan = sorted({i for _, i in R.mercados()} - set(cat["entrega"]))
        self.assertEqual(faltan, [], "cada idioma de elegir_mercado.py tiene frases de entrega")
        self.assertGreaterEqual(len(R.mercados()), 57)

    def test_cola_mundial_y_conserva_estadisticas(self) -> None:
        cat = R.catalogo()
        cola = R.generar_cola(cat, R.mercados())
        ids = [b["id"] for b in cola["busquedas"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreater(len(ids), 600)
        self.assertTrue(any(b["pais"] == "PL" and b["idioma"] == "pl" for b in cola["busquedas"]), "Polonia en polaco")
        self.assertTrue(any(b["pais"] == "PL" and b["idioma"] == "en" for b in cola["busquedas"]), "y en inglés")
        self.assertTrue(any(b["tipo"] == "plataforma" and b["termino"] == "hotmart.com" and b["pais"] == "MX" for b in cola["busquedas"]))
        b0 = cola["busquedas"][0]
        b0.update(corridas=3, ofertas_nuevas=5, ultima="2026-11-10T10:00+00:00")
        nueva = R.generar_cola(cat, R.mercados(), cola)
        self.assertEqual(next(b for b in nueva["busquedas"] if b["id"] == b0["id"])["ofertas_nuevas"], 5)

    def test_siguientes_prioriza_lo_nuevo_y_reparte_por_pais(self) -> None:
        cola = {"busquedas": [
            {"id": f"x:{p}:{i}", "tipo": "entrega", "pais": p, "idioma": "es", "termino": str(i), "prioridad": 1, "corridas": 0}
            for p in ("MX", "AR") for i in range(5)] + [
            {"id": "y:CO:1", "tipo": "entrega", "pais": "CO", "idioma": "es", "termino": "z", "prioridad": 1, "corridas": 2,
             "ofertas_nuevas": 0, "ultima": "2026-11-12T10:00+00:00"}]}
        sel = R.siguientes(cola, 10, HOY, max_por_mercado=3)
        self.assertLessEqual(sum(1 for b in sel if b["pais"] == "MX"), 3)
        self.assertEqual(sel[-1]["id"], "y:CO:1", "la ya corrida y sin rendimiento va al final")

    def test_url_de_busqueda(self) -> None:
        u = R.url_busqueda("descarga inmediata", "MX", HOY)
        self.assertIn("country=MX", u)
        self.assertIn("keyword_exact_phrase", u)
        self.assertIn("start_date[max]=2026-11-03", u)
        self.assertNotIn("start_date", R.url_busqueda("x.com", "ALL", HOY, tope_dias=None))


class TestClaves(unittest.TestCase):
    def test_productos_de_plataformas_compartidas_son_ofertas_distintas(self) -> None:
        c = R.dominios_compartidos()
        self.assertEqual(R.clave_de("https://hotmart.com/es/marketplace/productos/remind-recupera/S105337765X", c), "hotmart-com-s105337765x")
        self.assertEqual(R.clave_de("https://go.hotmart.com/M107497977L", c), "go-hotmart-com-m107497977l")
        self.assertEqual(R.clave_de("https://inlead.digital/mapa-relacional/", c), "inlead-digital-mapa-relacional")
        self.assertEqual(R.clave_de("https://www.referente262-com/x", c), "referente262-com")
        self.assertEqual(R.consulta_medir({"destino": "https://go.hotmart.com/M107497977L"}, c), "M107497977L")
        self.assertEqual(R.consulta_medir({"destino": "https://www.miebook.com/oferta"}, c), "miebook.com")


class TestRecorrido(unittest.TestCase):
    def setUp(self) -> None:
        self.cat = R.catalogo()
        self.umb = self.cat["umbrales"]
        self.cola = {"busquedas": [{"id": "plataforma:AR:-:hotmart-com", "tipo": "plataforma", "pais": "AR", "idioma": "-",
                                    "termino": "hotmart.com", "prioridad": 1.1, "corridas": 0}]}
        self.ofertas: dict = {}
        self.tmp = tempfile.TemporaryDirectory()
        self._dir = R.DIR
        R.DIR = Path(self.tmp.name)

    def tearDown(self) -> None:
        R.DIR = self._dir
        self.tmp.cleanup()

    def test_hallazgo_medir_verificar_exportar(self) -> None:
        lectura = {"total": "61", "tarjetas": 4, "grupos": [
            {"pagina": "Recetas", "destino": "https://go.hotmart.com/M1", "anuncios": 1, "max_dias": 68},
            {"pagina": "Joya", "destino": "https://mijoya.com/es/", "anuncios": 7, "max_dias": 40},
            {"pagina": "Nueva", "destino": "https://nueva.com", "anuncios": 2, "max_dias": 5},
            {"pagina": "Sin destino", "destino": ""}]}
        r = R.registrar(self.ofertas, self.cola, "plataforma:AR:-:hotmart-com", lectura, AHORA, self.umb, R.dominios_compartidos(), set())
        self.assertEqual(r, {"grupos": 3, "nuevas": 3})
        self.assertEqual(self.ofertas["go-hotmart-com-m1"]["estado"], "a_medir", "un anuncio activo hace 68 días: evergreen")
        self.assertEqual(self.ofertas["mijoya-com"]["estado"], "a_medir")
        self.assertEqual(self.ofertas["nueva-com"]["estado"], "nuevo")
        self.assertEqual(self.ofertas["mijoya-com"]["mercados_vistos"], ["AR"])
        self.assertTrue((R.DIR / "hallazgos.jsonl").is_file())
        self.assertEqual(self.cola["busquedas"][0]["ofertas_nuevas"], 3)
        o = self.ofertas["mijoya-com"]
        o.update(anuncios_total=40, estado="medida", paises_con_anuncios=["AR", "MX"])
        R._avanzar(o, self.umb)
        self.assertEqual(o["estado"], "a_verificar")
        o2 = self.ofertas["go-hotmart-com-m1"]
        o2.update(anuncios_total=1, estado="medida")
        R._avanzar(o2, self.umb)
        self.assertEqual(o2["estado"], "descartada", "bajo el piso al medir")
        o.update(estado="verificada", producible=True, funnel="quiz", producto="ebook")
        filas = R.exportables(self.ofertas, self.umb)
        self.assertEqual([f["clave_radar"] for f in filas], ["mijoya-com"])
        self.assertEqual(filas[0]["hueco"], 0.75)
        self.assertGreater(R.joya(o), R.joya({**o, "paises_con_anuncios": ["AR", "MX", "CO", "CL", "PE", "ES", "US", "BR"]}), "más hueco, más joya")

    def test_en_banco_no_se_cuenta_como_nueva(self) -> None:
        lectura = {"grupos": [{"pagina": "Ya", "destino": "https://referente128.com/", "anuncios": 9, "max_dias": 60}]}
        r = R.registrar(self.ofertas, self.cola, "plataforma:AR:-:hotmart-com", lectura, AHORA, self.umb, R.dominios_compartidos(), {"referente128-com"})
        self.assertEqual(r["nuevas"], 0)
        self.assertEqual(self.ofertas["referente128-com"]["estado"], "en_banco")

    def test_bloqueo_pausa_y_vence(self) -> None:
        (R.DIR / "bloqueo.json").write_text(json.dumps({"desde": "x", "hasta": (AHORA + dt.timedelta(hours=6)).isoformat(), "motivo": "403"}))
        self.assertIsNotNone(R.bloqueado(AHORA))
        self.assertIsNone(R.bloqueado(AHORA + dt.timedelta(hours=7)))

    def test_lectura_desde_api_agrupa_por_dominio(self) -> None:
        inicio = int(dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc).timestamp())
        pares = [({"id": "1", "page_name": "P", "ad_delivery_start_time": inicio}, {"captions": ["mijoya.com"], "alcance_ue": 100}),
                 ({"id": "2", "page_name": "P", "ad_delivery_start_time": inicio}, {"captions": ["mijoya.com"], "alcance_ue": 50}),
                 ({"id": "3", "page_name": "Q", "ad_delivery_start_time": inicio}, {"captions": []})]
        lec = R.lectura_desde_api(pares, HOY)
        self.assertEqual(len(lec["grupos"]), 1)
        self.assertEqual((lec["grupos"][0]["anuncios"], lec["grupos"][0]["max_dias"], lec["grupos"][0]["alcance_ue"]), (2, 43, 150))


class TestJoyaEnLaEleccion(unittest.TestCase):
    def test_hueco_y_escalando_suben_sin_tocar_los_pesos(self) -> None:
        spec = importlib.util.spec_from_file_location("ordenar_candidatos", LANZAR / "ordenar_candidatos.py")
        oc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oc)  # type: ignore[union-attr]
        self.assertEqual(oc.PESOS, {"complejidad": 0.40, "antiguedad": 0.35, "anuncios": 0.25})
        base = {"pagina": "x", "anuncios": 40, "dias": 60, "funnel": "quiz", "producible": True}
        p0 = oc.puntuar(base, [])["puntaje"]
        p1 = oc.puntuar({**base, "hueco": 1.0, "escalando": True}, [])["puntaje"]
        self.assertAlmostEqual(p1 / p0, 1.21, places=2)


if __name__ == "__main__":
    unittest.main()
