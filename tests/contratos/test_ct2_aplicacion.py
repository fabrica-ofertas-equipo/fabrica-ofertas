"""Pruebas de la aplicación de la revisión independiente CT-2 (docs/_historial/ct2-registro.md): lo que se endureció y no cubre ya
``test_revision_ct2.py`` (que fija un hallazgo por prueba). Sin red; solo copias temporales de ``ofertas/_ejemplo``."""
from __future__ import annotations

import copy
import json
import random
import shutil
import subprocess
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from engine import factibilidad as F
from engine.errores import ErrorValidacion
from scripts import validar_esquemas as V
from tests.contratos.test_revision_ct2 import PARAM, EJ, codigos, copia_ejemplo, editar_economia, entradas_ejemplo, validar


class TestFactibilidadEndurecida(unittest.TestCase):
    def test_iva_y_tasas_acotadas(self) -> None:
        base = entradas_ejemplo()
        for clave, valor in (("tasa_iva_bp", 100001), ("tasa_upsell_bp", 10001), ("tarifa_meta_bp", 10001), ("recargos_bp", 10001)):
            with self.assertRaises(ErrorValidacion, msg=clave):
                F.calcular({**base, clave: valor}, PARAM, None)
        F.calcular({**base, "tasa_iva_bp": 2300}, PARAM, None)          # un IVA real sigue pasando

    def test_ctr_y_conversion_no_pueden_superar_el_cien_por_cien(self) -> None:
        base = entradas_ejemplo()
        esc = copy.deepcopy(base["escenarios"])
        esc["central"]["ctr_enlace_bp"] = 10001
        with self.assertRaises(ErrorValidacion):
            F.calcular({**base, "escenarios": esc}, PARAM, None)

    def test_el_signo_del_resultado_central_coincide_con_la_razon(self) -> None:
        rng = random.Random(20261106)
        for _ in range(300):
            meta = rng.choice((0, 300, 1000, 3000, 6000))
            ent = entradas_ejemplo(tarifa_meta_bp=meta)
            ent["escenarios"] = {**ent["escenarios"], "central": {"cpm": {"monto": rng.randint(150, 1500), "moneda": "EUR"},
                                                                "ctr_enlace_bp": 160, "clic_compra_bp": 220}}
            r = F.calcular(ent, PARAM, None)
            razon, res = Decimal(r["razon"]), r["resultado_esperado_central"]["monto"]
            if razon < Decimal("0.99"):
                self.assertLess(res, 0, (meta, r["razon"], res))
            if razon > Decimal("1.01"):
                self.assertGreater(res, 0, (meta, r["razon"], res))

    def test_sin_tarifa_de_meta_el_resultado_no_cambia_respecto_de_1_1_0(self) -> None:
        eco = V.cargar_json(EJ / "03-oferta" / "economia.json")
        r = F.calcular(entradas_ejemplo(), PARAM, None)
        self.assertEqual(11908, r["resultado_esperado_central"]["monto"])
        self.assertEqual(eco["resultado_esperado_central"], r["resultado_esperado_central"])

    def test_documento_normaliza_el_dinero_y_declara_costos_fijos(self) -> None:
        doc = F.documento_economia(entradas_ejemplo(costos_fijos_oferta=5000), PARAM, V.limites_de_prueba())
        self.assertEqual("1.2.0", doc["schema_version"])
        self.assertEqual({"monto": 5000, "moneda": "EUR"}, doc["entradas_usadas"]["costos_fijos_oferta"])
        self.assertEqual(doc["gasto_test_plan"]["monto"] + 5000, doc["perdida_max_test"]["monto"])
        self.assertEqual([], V.errores_de_esquema("economia", doc))

    def test_esquema_1_2_0_exige_costos_fijos_y_1_1_0_no(self) -> None:
        eco = V.cargar_json(EJ / "03-oferta" / "economia.json")
        sin = copy.deepcopy(eco)
        del sin["entradas_usadas"]["costos_fijos_oferta"]
        self.assertTrue(V.errores_de_esquema("economia", sin))
        sin["schema_version"] = "1.1.0"
        self.assertEqual([], V.errores_de_esquema("economia", sin))

    def test_verificar_compara_veredicto_perdida_y_limites(self) -> None:
        eco = V.cargar_json(EJ / "03-oferta" / "economia.json")
        lim = V.limites_de_prueba()
        self.assertEqual([], F.verificar(eco, PARAM, lim))
        for campo, valor in (("veredicto", "AJUSTADA"), ("perdida_max_test", {"monto": 99999, "moneda": "EUR"}), ("limites_pendientes", ["moneda_limites"])):
            malo = {**eco, campo: valor}
            self.assertTrue(any(d.startswith(campo) for d in F.verificar(malo, PARAM, lim)), campo)

    def test_verificar_sin_parametros_no_da_el_veredicto_por_bueno(self) -> None:
        eco = V.cargar_json(EJ / "03-oferta" / "economia.json")
        difs = F.verificar(eco, None, None)
        self.assertTrue(any("veredicto: no verificable" in d for d in difs), difs)

    def test_verificar_con_parametros_detecta_k_distinto(self) -> None:
        eco = V.cargar_json(EJ / "03-oferta" / "economia.json")
        malo = copy.deepcopy(eco)
        malo["criterios_corte"]["k"] -= 1
        self.assertTrue(any(d.startswith("criterios_corte.k") for d in F.verificar(malo, PARAM, None)))

    def test_cli_salida_atomica_y_sin_temporales(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="ct2-cli-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        ent = tmp / "e.json"
        ent.write_text(json.dumps(entradas_ejemplo(), ensure_ascii=False), encoding="utf-8")
        salida = tmp / "economia.json"
        par = tmp / "p.json"
        par.write_text(json.dumps({"grupos": {"economia": {"razon_min_factible": {"valor": "1.3"}}, "testeo": {"k_corte": {"valor": 3}, "n_dec": {"valor": 10}}}}))
        self.assertEqual(0, F.main(["calcular", "--entradas", str(ent), "--parametros", str(par), "--salida", str(salida)]))
        self.assertEqual(["economia.json"], sorted(p.name for p in tmp.glob("economia*")))
        self.assertEqual([], V.errores_de_esquema("economia", json.loads(salida.read_text(encoding="utf-8"))))


class TestValidadorEndurecido(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="ct2-val-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_la_aprobacion_de_d5_sella_el_sitio(self) -> None:
        d = copia_ejemplo(self.tmp)
        self.assertEqual("sha256", V.hash_salida_etapa(d, "D5").split(":")[0])
        antes = V.hash_salida_etapa(d, "D5")
        p = d / "05-landing" / "sitio" / "index.html"
        p.write_text(p.read_text(encoding="utf-8").replace("Pago único.", "Pago único!"), encoding="utf-8")
        self.assertNotEqual(antes, V.hash_salida_etapa(d, "D5"))
        self.assertIn("X02_HASH_ETAPA", codigos(validar(d)))

    def test_d5_sin_sitio_no_tiene_hash_de_salida(self) -> None:
        d = copia_ejemplo(self.tmp)
        shutil.rmtree(d / "05-landing" / "sitio")
        self.assertIsNone(V.hash_salida_etapa(d, "D5"))

    def test_archivos_sellados_siguen_siendo_solo_archivos(self) -> None:
        """compliance.lint_claims (S-B) recorre ``ARCHIVOS_SELLADOS`` como archivos: las carpetas van en ``DIRECTORIOS_SELLADOS``."""
        for etapa, rutas in V.ARCHIVOS_SELLADOS.items():
            for rel in rutas:
                self.assertTrue((EJ / rel).is_file() or not (EJ / rel).exists(), (etapa, rel))
        self.assertEqual(["05-landing/sitio"], V.DIRECTORIOS_SELLADOS["D5"])

    def test_hash_de_carpeta_igual_en_una_copia_fuera_de_sitio(self) -> None:
        copia = self.tmp / "historial" / "v1"
        shutil.copytree(EJ / "05-landing" / "sitio", copia)
        self.assertEqual(V.hash_directorio(EJ / "05-landing" / "sitio"), V.hash_directorio(copia))

    def test_ejemplo_del_repositorio_se_reconoce_por_ruta_no_por_nombre(self) -> None:
        self.assertTrue(V.es_ejemplo_del_repositorio(EJ))
        self.assertFalse(V.es_ejemplo_del_repositorio(copia_ejemplo(self.tmp)))

    def test_x14_veredicto_exacto_para_los_tres_estados(self) -> None:
        for cpm, esperado in ((496, "AJUSTADA"), (900, "NO_FACTIBLE")):
            (self.tmp / f"c{cpm}").mkdir()
            d = copia_ejemplo(self.tmp / f"c{cpm}")
            doc = F.documento_economia(entradas_ejemplo(escenarios={**entradas_ejemplo()["escenarios"], "central": {
                "cpm": {"monto": cpm, "moneda": "EUR"}, "ctr_enlace_bp": 160, "clic_compra_bp": 220}}), PARAM, V.limites_de_prueba())
            self.assertEqual(esperado, doc["veredicto"])
            (d / "03-oferta" / "economia.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
            self.assertNotIn("X14_ECONOMIA", codigos(validar(d)))          # lo declarado = lo recalculado: sin error de X14


class TestPixelYConsentimiento(unittest.TestCase):
    JS = EJ / "05-landing" / "sitio" / "js" / "pixel.js"

    def _viewcontent(self, atributos: dict) -> list:
        if not shutil.which("node"):
            self.skipTest("node no está instalado")
        arnes = r"""
const fs = require('fs'), vm = require('vm');
const [ruta, atributos] = process.argv.slice(-2);
const attrs = JSON.parse(atributos), llamadas = [];
const doc = {body: {getAttribute: k => (k in attrs ? attrs[k] : null)}, createElement: () => ({}), getElementsByTagName: () => [{parentNode: {insertBefore() {}}}]};
const win = {FabricaConsent: {marketing: () => true, visitorId: () => 'abc'}, document: doc}; win.window = win;
const ctx = vm.createContext({window: win, document: doc, Date, Number, llamadas});
vm.runInContext(fs.readFileSync(ruta, 'utf8').replace("window.fbq('init'", "window.fbq = function () { llamadas.push([].slice.call(arguments)); }; window.fbq('init'"), ctx);
console.log(JSON.stringify(llamadas.filter(c => c[0] === 'track' && c[1] === 'ViewContent').map(c => c[2])));
"""
        r = subprocess.run(["node", "-e", arnes, str(self.JS), json.dumps(atributos)], capture_output=True, text=True, timeout=30)
        self.assertEqual(0, r.returncode, r.stderr[-300:])
        return json.loads(r.stdout)

    def test_valor_con_enteros_segun_los_decimales_de_la_moneda(self) -> None:
        base = {"data-oferta-id": "OF-1", "data-moneda": "EUR"}
        self.assertEqual("19.90", self._viewcontent({**base, "data-precio-minor": "1990", "data-decimales": "2"})[0]["value"])
        self.assertEqual("0.05", self._viewcontent({**base, "data-precio-minor": "5", "data-decimales": "2"})[0]["value"])
        self.assertEqual("1990", self._viewcontent({**base, "data-moneda": "JPY", "data-precio-minor": "1990", "data-decimales": "0"})[0]["value"])

    def test_datos_invalidos_no_emiten_viewcontent(self) -> None:
        for attrs in ({"data-oferta-id": "OF-1", "data-moneda": "EUR", "data-precio-minor": "19.9", "data-decimales": "2"},
                      {"data-oferta-id": "OF-1", "data-moneda": "EUR", "data-precio-minor": "1990"},
                      {"data-moneda": "EUR", "data-precio-minor": "1990", "data-decimales": "2"}):
            self.assertEqual([], self._viewcontent(attrs), attrs)

    def test_el_ejemplo_solo_lleva_data_de_producto_en_paginas_de_angulo(self) -> None:
        sitio = EJ / "05-landing" / "sitio"
        con = sorted(p.relative_to(sitio).as_posix() for p in sitio.rglob("*.html") if "data-precio-minor" in p.read_text(encoding="utf-8"))
        self.assertEqual(["a/plan-en-una-tarde.html", "a/pregunta-de-entrevista.html", "index.html"], con)


if __name__ == "__main__":
    unittest.main()
