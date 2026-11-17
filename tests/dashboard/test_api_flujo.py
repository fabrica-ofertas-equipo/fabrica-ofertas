"""Pruebas de ``GET /api/flujo`` (pantalla «Cómo funciona»): lectura de la vigilancia, versión de las skills y armado."""
from __future__ import annotations

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from dashboard import api_flujo
from dashboard.api_base import Ctx

AHORA = dt.datetime(2026, 11, 13, 12, 30, tzinfo=dt.timezone.utc)


def _vuelta(ahora: str, decision: str = "SIGUE") -> str:
    return json.dumps({"leido": ahora, "ahora": ahora, "regla": "día 1", "tests": [{"test": "T", "mercado": "MX", "decision": decision, "gasto_usd": 3.5, "ventas": 0, "campanas": ["1"]}]})


class TestVigilancia(unittest.TestCase):
    def test_ultima_vuelta_edad_y_salud(self) -> None:
        lineas = [_vuelta("2026-11-12T10:00+00:00"), "no es json", _vuelta("2026-11-13T12:05+00:00", "CERCA")]
        v = api_flujo.ultima_vigilancia(lineas, AHORA)
        self.assertTrue(v["existe"])
        self.assertEqual(v["edad_min"], 25)
        self.assertEqual(v["salud"], "ok")
        self.assertEqual(v["vueltas_24h"], 1)
        self.assertEqual(v["tests"][0]["decision"], "CERCA")
        self.assertNotIn("campanas", v["tests"][0], "solo los campos que muestra la pantalla")

    def test_vigilancia_atrasada_o_ausente(self) -> None:
        self.assertEqual(api_flujo.ultima_vigilancia([_vuelta("2026-11-13T10:30+00:00")], AHORA)["salud"], "aviso")
        self.assertEqual(api_flujo.ultima_vigilancia([_vuelta("2026-11-13T06:00+00:00")], AHORA)["salud"], "error")
        self.assertEqual(api_flujo.ultima_vigilancia([], AHORA), {"existe": False})


class TestSkills(unittest.TestCase):
    def test_version_y_estado_del_frontmatter(self) -> None:
        txt = '---\nname: x\ndescription: "y"\nmetadata:\n  version: "0.8.1"\n  estado: "en uso"\n---\n# cuerpo\nversion: 9.9.9\n'
        self.assertEqual(api_flujo.skill_info(txt), {"version": "0.8.1", "estado": "en uso"})
        self.assertEqual(api_flujo.skill_info("# sin frontmatter"), {"version": None, "estado": None})


class TestFlujo(unittest.TestCase):
    def test_armado_y_respuesta_completa_en_una_raiz_minima(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            (raiz / "ofertas" / "_funnels").mkdir(parents=True)
            (raiz / "ofertas" / "_borrador-nueva").mkdir()
            (raiz / "ofertas" / "_borrador-nueva" / "estado.md").write_text("# Estado de «Nueva»\n- [x] 1. a\n- [x] 2. b\n- [ ] 3. c\n", encoding="utf-8")
            (raiz / "ofertas" / "_borrador-vieja").mkdir()
            (raiz / "ofertas" / "_funnels" / "libro-de-tests.json").write_text(json.dumps({"tests": [{"ficha": {"carpeta_trabajo": "ofertas/_borrador-vieja"}}]}), encoding="utf-8")
            (raiz / "ofertas" / "_funnels" / "vigilancia.jsonl").write_text(_vuelta("2026-11-13T12:00+00:00") + "\n", encoding="utf-8")
            s = api_flujo.flujo(Ctx(raiz=raiz, ahora=lambda: AHORA))
            datos = s.datos
            self.assertEqual([a["carpeta"] for a in datos["armado"]], ["_borrador-nueva"], "la que ya está en el libro no figura en armado")
            self.assertEqual((datos["armado"][0]["fases_hechas"], datos["armado"][0]["fases_total"]), (2, 3))
            self.assertEqual(datos["armado"][0]["titulo"], "Estado de «Nueva»")
            self.assertEqual(datos["vigilancia"]["edad_min"], 30)
            self.assertIn("error", datos["banco"], "sin el script del banco, el bloque lo dice en vez de romper")
            self.assertEqual(datos["skills"]["escalar-oferta"]["existe"], False)
            self.assertEqual(set(datos["skills"]), {"buscar-ofertas", "modelar-y-lanzar-oferta", "backend-ofensivo", "escalar-oferta"})
            self.assertEqual(datos["buscar_diario"], {"fecha": None})
            self.assertEqual(datos["radar"], {"existe": False}, "sin cola del radar, el bloque lo dice")
            d2 = raiz / "empresa" / "barrido" / "banco" / "diario"
            d2.mkdir(parents=True)
            (d2 / "2026-11-14.md").write_text("# Banco 14-nov\n\nBanco: ALCANZA (3 listos)\n", encoding="utf-8")
            (d2 / "notas.md").write_text("x", encoding="utf-8")
            bd = api_flujo.flujo(Ctx(raiz=raiz, ahora=lambda: AHORA)).datos["buscar_diario"]
            self.assertEqual((bd["fecha"], bd["resumen"], bd["dias"]), ("2026-11-14", "Banco: ALCANZA (3 listos)", 1))


if __name__ == "__main__":
    unittest.main()


class TestVerificacionCapi(unittest.TestCase):
    def test_pedido_verificando_y_verificado(self) -> None:
        import json as _j
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            (raiz / "ofertas" / "_funnels").mkdir(parents=True)
            libro = {"tests": [{"nombre": "X", "estado": "programado", "ficha": {"pixel": {"id": "1000000000000067"},
                     "tiendas": [{"slug": "x-1", "capi": {"ok": False, "revisado": "2026-11-13T12:00:00+00:00"}}]}}]}
            (raiz / "ofertas" / "_funnels" / "libro-de-tests.json").write_text(_j.dumps(libro), encoding="utf-8")
            ctx = Ctx(raiz=raiz, ahora=lambda: AHORA)
            m = api_flujo.flujo(ctx).datos["manos"]
            self.assertEqual((m[0]["estado"], m[0]["tiendas"][0]["url"]), ("pendiente", "https://impultienda.ar/dashboard/x-1/configuracion"))
            api_flujo.pedir_verificacion(ctx, {"tipo": "capi", "oferta": "X"})
            self.assertEqual(api_flujo.flujo(ctx).datos["manos"][0]["estado"], "verificando")
            libro["tests"][0]["ficha"]["tiendas"][0]["capi"] = {"ok": True, "revisado": (AHORA + dt.timedelta(minutes=5)).isoformat()}
            (raiz / "ofertas" / "_funnels" / "libro-de-tests.json").write_text(_j.dumps(libro), encoding="utf-8")
            ctx2 = Ctx(raiz=raiz, ahora=lambda: AHORA + dt.timedelta(minutes=10))
            self.assertEqual(api_flujo.flujo(ctx2).datos["manos"][0]["estado"], "verificado")
            from dashboard.seguridad import ErrorHttp
            with self.assertRaises(ErrorHttp):
                api_flujo.pedir_verificacion(ctx, {"tipo": "capi", "oferta": "No existe"})

    def test_tienda_sin_campo_capi_cuenta_como_pendiente(self) -> None:
        # Oferta E y Oferta F (13-nov): la ficha no traía `capi` y el aviso no salía.
        import json as _j
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            (raiz / "ofertas" / "_funnels").mkdir(parents=True)
            libro = {"tests": [
                {"nombre": "Activa", "estado": "activo", "ficha": {"pixel": {"id": "20000000000000074"}, "tiendas": [{"slug": "a-1"}, {"slug": "a-2"}]}},
                {"nombre": "Pausada", "estado": "pausado", "ficha": {"pixel": {"id": "1000000000000067"}, "tiendas": [{"slug": "p-1"}]}}]}
            (raiz / "ofertas" / "_funnels" / "libro-de-tests.json").write_text(_j.dumps(libro), encoding="utf-8")
            m = [x for x in api_flujo.flujo(Ctx(raiz=raiz, ahora=lambda: AHORA)).datos["manos"] if x["tipo"] == "capi"]
            self.assertEqual([(x["oferta"], x["estado"], [t["tienda"] for t in x["tiendas"]]) for x in m], [("Activa", "pendiente", ["a-1", "a-2"])])


class TestServicios(unittest.TestCase):
    def test_registro_con_estado_y_url_segura(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            f = raiz / "ofertas" / "_funnels"
            f.mkdir(parents=True)
            (f / "servicios.json").write_text(json.dumps({"servicios": [
                {"id": "kie", "nombre": "Kie", "para": "clips", "url": "https://kie.ai", "critico": True},
                {"id": "x", "nombre": "X", "para": "y", "url": "javascript:alert(1)"}]}), encoding="utf-8")
            (f / "servicios_estado.json").write_text(json.dumps({"kie": {"estado": "aviso", "detalle": "4.000 créditos", "cuando": "2026-11-13T10:00+00:00"}}), encoding="utf-8")
            s = api_flujo.flujo(Ctx(raiz=raiz, ahora=lambda: AHORA)).datos["servicios"]
            self.assertEqual((s[0]["estado"], s[0]["detalle"], s[0]["critico"]), ("aviso", "4.000 créditos", True))
            self.assertEqual((s[1]["estado"], s[1]["url"]), ("sin_dato", None), "una URL que no es https no se muestra")


class TestEmbudo(unittest.TestCase):
    def test_donde_se_pierde(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            f = raiz / "ofertas" / "_funnels"
            f.mkdir(parents=True)
            self.assertEqual(api_flujo.flujo(Ctx(raiz=raiz, ahora=lambda: AHORA)).datos["embudo"], [])
            (f / "embudo.json").write_text(json.dumps({"X": {
                "vuelta": {"carga_pct": 55.0, "costo_por_visita": 0.4, "cpm": {"estado": "OK"}, "acciones": [{"accion": "AVISO_CARGA", "mensaje": "baja"}], "cuando": "2026-11-13T12:00+00:00"},
                "periodos": {"lado": "anuncios", "cambio_costo_pct": 30, "clon": "poca_muestra", "acciones": []},
                "anuncios": {"resumen": {"NO_TOCAR": 2, "REHACER_CTA": 3}}}}), encoding="utf-8")
            e = api_flujo.flujo(Ctx(raiz=raiz, ahora=lambda: AHORA)).datos["embudo"][0]
            self.assertEqual((e["oferta"], e["carga_pct"], e["lado"], e["cpm_estado"], e["avisos"]), ("X", 55.0, "anuncios", "OK", ["baja"]))
            self.assertEqual(e["anuncios"], {"NO_TOCAR": 2, "REHACER_CTA": 3})
