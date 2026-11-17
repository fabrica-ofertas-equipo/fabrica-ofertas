"""GET /api/descubrimiento/<corrida>/referente/<page_id>: la landing original de una página (solo lectura, con la URL revalidada)."""
from __future__ import annotations

import json

from tests.dashboard.test_servidor_apoyo import CORRIDA, HOSTIL, PruebaBase

PID = "700000000000001"
RUTA = f"/api/descubrimiento/{CORRIDA}/referente/{PID}"
URL = "https://referentea.example/colora"


class PruebaReferente(PruebaBase):
    def preparar(self, *, registro: object | None = None) -> None:
        self.escribir(f"empresa/barrido/paginas/{CORRIDA}.json", json.dumps({"paginas": [
            {"page_id": PID, "page_name": "ReferenteA", "qids": ["it-a", "../malo", "it-b"]},
            {"page_id": "111111", "page_name": HOSTIL, "qids": []}]}))
        anuncio = lambda i, pagina, url=None: {"id": str(i), "page_id": int(pagina), "ad_creative_link_title": f"t{i}", "ad_delivery_start_time": 1793721064,  # noqa: E731
                                              "ad_snapshot_url": url or f"https://www.facebook.com/ads/library/?id={i}"}
        self.escribir(f"empresa/barrido/crudo/{CORRIDA}/it-a.json", json.dumps({"ads": [
            anuncio(2303787473801185, PID), anuncio(2303787473801185, PID), anuncio(5555555, "999999"), anuncio(7777777, PID, "https://evil.example/x")]}))
        self.escribir(f"empresa/barrido/crudo/{CORRIDA}/it-b.json", json.dumps({"ads": [anuncio(1456519616584586, PID), anuncio(1162523689835581, PID), anuncio(1862523689835581, PID)]}))
        if registro is not None:
            self.escribir("empresa/barrido/referentes/landings.json", json.dumps({"schema_version": "1.0.0", "referentes": registro}))

    def pedir(self, ruta: str = RUTA):
        return self.cliente().get(ruta)

    def test_sin_registro_da_los_enlaces_y_el_comando(self) -> None:
        self.preparar()
        r = self.pedir()
        self.assertEqual(r.estado, 200)
        d = r.datos
        self.assertIsNone(d["landing"])
        self.assertEqual(d["page_name"], "ReferenteA")
        self.assertEqual(d["meta"]["pagina"], f"https://www.facebook.com/{PID}")
        self.assertIn(f"view_all_page_id={PID}", d["meta"]["biblioteca_pagina"])
        self.assertEqual([a["id"] for a in d["anuncios"]], ["2303787473801185", "1456519616584586", "1162523689835581"], "máx. 3, sin repetir, solo de esa página y con ficha de Meta válida")
        self.assertEqual(d["anuncios"][0]["inicio"], "2026-11-03", "la fecha sale del epoch del anuncio, en UTC")
        self.assertIn(f"registrar {PID}", d["comando_registrar"])
        self.assertIn("--escribir", d["comando_registrar"])

    def test_con_registro_devuelve_la_landing(self) -> None:
        self.preparar(registro=[{"page_id": PID, "page_name": "ReferenteA", "url": URL, "dominio": "referentea.example", "registrada_en": "2026-11-08T10:00:00Z",
                                 "nota": "del botón del anuncio", "oferta_id": "OF-202611-91", "copia_local": None}])
        d = self.pedir().datos
        self.assertEqual(d["landing"]["url"], URL)
        self.assertEqual(d["landing"]["dominio"], "referentea.example")
        self.assertEqual(d["landing"]["oferta_id"], "OF-202611-91")

    def test_una_url_peligrosa_en_el_archivo_se_ignora_con_aviso(self) -> None:
        for mala in ("javascript:alert(1)", "http://a.example/x", "https://www.facebook.com/ads/library/?id=1", "https://127.0.0.1/x", "https://a.example/x y"):
            with self.subTest(mala=mala):
                self.preparar(registro=[{"page_id": PID, "url": mala}])
                r = self.pedir()
                self.assertEqual(r.estado, 200)
                self.assertIsNone(r.datos["landing"])
                self.assertTrue(any("no es válida" in a for a in r.json()["avisos"]), r.json()["avisos"])

    def test_registro_roto_no_rompe_y_avisa(self) -> None:
        self.preparar()
        self.escribir("empresa/barrido/referentes/landings.json", "{no json")
        r = self.pedir()
        self.assertEqual(r.estado, 200)
        self.assertIsNone(r.datos["landing"])
        self.assertTrue(r.json()["avisos"])

    def test_pagina_desconocida_y_nombre_hostil_viajan_como_dato(self) -> None:
        self.preparar()
        d = self.pedir(f"/api/descubrimiento/{CORRIDA}/referente/999999").datos
        self.assertIsNone(d["page_name"])
        self.assertEqual(d["anuncios"], [])
        self.assertEqual(self.pedir(f"/api/descubrimiento/{CORRIDA}/referente/111111").datos["page_name"], HOSTIL)

    def test_identificadores_invalidos_dan_400_y_no_tocan_nada(self) -> None:
        self.preparar()
        antes = self.hash_arbol(self.raiz)
        for malo in ("12ab", "1234", "..%2F..%2Fx", "1" * 25):
            self.assertEqual(self.pedir(f"/api/descubrimiento/{CORRIDA}/referente/{malo}").estado, 400, malo)
        self.assertEqual(self.pedir("/api/descubrimiento/no-es-corrida/referente/" + PID).estado, 400)
        self.pedir()
        self.assertEqual(self.hash_arbol(self.raiz), antes, "solo lectura")

    def test_exige_token_y_solo_acepta_get(self) -> None:
        self.preparar()
        c = self.cliente()
        self.assertEqual(c.get(RUTA, token=False).estado, 403)
        self.assertEqual(c.post(RUTA).estado, 405)


class PruebaReferenteDeOferta(PruebaBase):
    """GET /api/oferta/<id>/referente: registro (por oferta_id) + competidores de D2 con landing_url."""

    def ruta(self, oferta: str) -> str:
        return f"/api/oferta/{oferta}/referente"

    def test_junta_el_registro_y_los_competidores_de_d2_sin_repetir(self) -> None:
        from tests.dashboard.test_servidor_apoyo import OFERTA
        self.escribir(f"ofertas/{OFERTA}/02-validacion/anuncios_competencia.json", json.dumps({"competidores": [
            {"page_id": "no_disponible", "page_name": "Axon", "landing_url": "https://axondigital.site/mapaspagnolo/"},
            {"page_id": "1230642616808822", "page_name": "Otro", "landing_url": "https://otro.example/x"},
            {"page_name": "Sin landing"}, {"landing_url": "javascript:alert(1)"}, {"landing_url": "https://www.facebook.com/ads/library/?id=1"}]}))
        self.escribir("empresa/barrido/referentes/landings.json", json.dumps({"referentes": [
            {"page_id": "700000000000001", "page_name": "ReferenteA", "url": "https://referentea.example/colora", "oferta_id": OFERTA, "copia_local": "docs/p.html"},
            {"page_id": "111111", "url": "https://de-otra-oferta.example/", "oferta_id": "OF-202611-01"},
            {"page_id": "222222", "url": "https://axondigital.site/mapaspagnolo/", "oferta_id": OFERTA}]}))
        r = self.cliente().get(self.ruta(OFERTA))
        self.assertEqual(r.estado, 200)
        d = r.datos
        self.assertEqual([(f["origen"], f["url"]) for f in d["referentes"]], [
            ("registro", "https://referentea.example/colora"), ("registro", "https://axondigital.site/mapaspagnolo/"), ("validacion", "https://otro.example/x")])
        self.assertEqual(d["referentes"][0]["copia_local"], "docs/p.html")
        avisos = r.json()["avisos"]
        self.assertEqual(sum("no es válida" in a for a in avisos), 2, avisos)       # javascript: y la ficha de Meta se ignoran con aviso
        self.assertFalse(r.json()["vacio"])

    def test_sin_nada_registrado_va_vacio_con_el_comando(self) -> None:
        from tests.dashboard.test_servidor_apoyo import OFERTA
        r = self.cliente().get(self.ruta(OFERTA))
        self.assertEqual(r.estado, 200)
        self.assertEqual(r.datos["referentes"], [])
        self.assertTrue(r.json()["vacio"])
        self.assertIn("--oferta", r.datos["comando_registrar"])

    def test_oferta_inexistente_404_y_solo_lectura(self) -> None:
        from tests.dashboard.test_servidor_apoyo import OFERTA
        antes = self.hash_arbol(self.raiz)
        c = self.cliente()
        self.assertEqual(c.get(self.ruta("OF-000000-00")).estado, 404)
        self.assertEqual(c.get(self.ruta("..")).estado, 400)      # un id con forma rara ni se busca
        c.get(self.ruta(OFERTA))
        self.assertEqual(self.hash_arbol(self.raiz), antes)
        self.assertEqual(c.post(self.ruta(OFERTA)).estado, 405)
