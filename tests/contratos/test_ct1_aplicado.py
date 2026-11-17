"""Pruebas de lo aplicado tras la revisión CT1 (docs/_historial/ct1-registro.md) que `test_revision_ct1.py` no cubre."""
from __future__ import annotations

import copy
import datetime as dt
import shutil
import unittest
from pathlib import Path

from scripts import validar_esquemas as V
from tests.contratos.test_ola_0b1 import _ej

CLAVE = V.CLAVE_DE_PRUEBA


class PruebaPatronEcma(unittest.TestCase):
    def test_dolar_estricto_pero_patron_sin_ancla_sigue_parcial(self) -> None:
        self.assertTrue(V._patron_ecma(r"^[0-9]+$").search("12"))
        self.assertIsNone(V._patron_ecma(r"^[0-9]+$").search("12\n"))
        self.assertTrue(V._patron_ecma(r"^1\.[1-9]").search("1.1.0"))          # sin `$`: coincidencia parcial (fullmatch lo rompería)
        self.assertIsNone(V._patron_ecma(r"^[a$]+$").search("a$\n"))            # `$` dentro de una clase es literal
        self.assertTrue(V._patron_ecma(r"^[a$]+$").search("a$"))

    def test_economia_1_0_0_no_puede_traer_campos_1_1_0(self) -> None:
        eco = V.cargar_json(V.RAIZ / "ofertas" / "_ejemplo" / "03-oferta" / "economia.json")
        del eco["conv_central"]
        self.assertTrue(V.errores_de_esquema("economia", eco))


class PruebaFirmasReales(unittest.TestCase):
    PUB = (V.DIR_EJEMPLOS / "clave-publica-de-prueba.pub")

    @unittest.skipUnless(shutil.which("ssh-keygen"), "ssh-keygen no disponible")
    def test_los_ejemplos_ed25519_verifican_con_la_publica_de_prueba(self) -> None:
        from engine import comun
        pub = self.PUB.read_text(encoding="utf-8").strip()
        for nombre in ("sello", "orden_firmada"):
            d = _ej(nombre)
            datos = V.json_canonico(V.payload_firma(nombre, d))
            self.assertTrue(comun.verificar_ed25519(datos, d["firma"], pub), nombre)
            d["oferta_id"] = "OF-202611-02"
            self.assertFalse(comun.verificar_ed25519(V.json_canonico(V.payload_firma(nombre, d)), d["firma"], pub), nombre)

    def test_hook_verificador_decide_en_produccion_y_una_excepcion_no_aprueba(self) -> None:
        o = _ej("orden_firmada")
        p = V.payload_firma("orden_firmada", o)
        vistos = []
        ok = V.problemas_firma(o["firma"], p, None, entorno="produccion", verificador=lambda b, f: vistos.append(b) or True)
        self.assertEqual([], ok)
        self.assertEqual([V.json_canonico(p)], vistos)
        self.assertTrue(V.problemas_firma(o["firma"], p, None, entorno="produccion", verificador=lambda b, f: False))
        def roto(b, f): raise RuntimeError("x")
        self.assertTrue(V.problemas_firma(o["firma"], p, None, entorno="produccion", verificador=roto))
        # fuera de producción y sin verificador basta el formato
        self.assertEqual([], V.problemas_firma(o["firma"], p, None, entorno="prueba"))

    def test_evaluar_limites_produccion_con_verificador(self) -> None:
        lim = copy.deepcopy(V.limites_de_prueba())
        lim["sello"]["firma"] = _ej("sello")["firma"]
        self.assertTrue(V.evaluar_limites(lim, "activar", entorno="produccion"))
        self.assertTrue(V.evaluar_limites(lim, "activar", entorno="produccion", verificador=lambda b, f: b == lim["sello"]["hash"].encode()))
        self.assertFalse(V.evaluar_limites(lim, "activar", entorno="produccion", verificador=lambda b, f: False))

    def test_payload_de_aprobacion_conserva_la_version_anterior_como_v1(self) -> None:
        a = _ej("aprobacion")
        self.assertNotEqual(V.payload_firma("aprobacion", a), V.payload_firma_v1("aprobacion", a))
        self.assertEqual(V.payload_firma("sello", _ej("sello")), V.payload_firma_v1("sello", _ej("sello")))


class PruebaNivelDeLaAprobacion(unittest.TestCase):
    def _ap(self, nivel: str, gate: str, humano: bool = True) -> dict:
        a = copy.deepcopy(_ej("aprobacion"))
        a.update(nivel=nivel, gate=gate)
        if not humano:
            a["aprobado_por"].update(tipo="regla", firma=None)
        elif a["aprobado_por"]["firma"]:
            a["aprobado_por"]["firma"] = V.firmar_hmac_de_prueba("aprobacion", a)
        return a

    def cods(self, a: dict, ef: str) -> set[str]:
        return {c for c, _ in V.problemas_artefacto("aprobacion", a, clave=CLAVE, entorno="prueba", nivel_exigido=ef)}

    def test_declarar_un_nivel_mayor_al_efectivo_es_x40_nivel(self) -> None:
        self.assertIn("X40_NIVEL", self.cods(self._ap("N3", "S", humano=False), "N2"))

    def test_nivel_declarado_menor_al_efectivo_con_gate_acorde_pasa(self) -> None:
        self.assertEqual(set(), self.cods(self._ap("N2", "H"), "N3"))   # activar_campana: N3 = S, la aprobación humana más estricta vale

    def test_gate_h_efectivo_exige_humano_firmado_aunque_declare_s(self) -> None:
        c = self.cods(self._ap("N2", "S", humano=False), "N2")
        self.assertTrue({"X40_GATE", "X40_FIRMA"} <= c, c)

    def test_nivel_efectivo_desde_estado_y_autonomia(self) -> None:
        est = copy.deepcopy(V.cargar_json(V.RAIZ / "ofertas" / "_ejemplo" / "estado.json"))
        aut = V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml")
        self.assertEqual("N2", V._nivel_exigido_aprobacion({"accion": "activar_campana"}, est, aut))
        aut["nivel_por_etapa"]["D7"]["nivel"] = "N1"
        self.assertEqual("N1", V._nivel_exigido_aprobacion({"accion": "activar_campana"}, est, aut))
        self.assertEqual("N2", V._nivel_exigido_aprobacion({"accion": "cambiar_limites"}, est, aut))   # sin etapa asociada: nivel de la oferta


class PruebaOrdenesSellosYFinanzas(unittest.TestCase):
    def test_nonce_se_compara_sin_mayusculas(self) -> None:
        a = {"nonce": "abcdefghijklmnop"}
        self.assertEqual([], V.problemas_ordenes([a, {"nonce": "otro-nonce-123456"}]))
        self.assertEqual("X40_NONCE", V.problemas_ordenes([a, {"nonce": "ABCDEFGHIJKLMNOP"}])[0][0])

    def test_uso_de_sello_rehash_vigencia_y_objetos(self) -> None:
        s = _ej("sello")
        ahora = dt.datetime(2026, 11, 10, 9, 0, tzinfo=dt.timezone.utc)
        base = dict(artefacto_sha256=s["artefacto_sha256"], object_ids=s["object_ids"], ahora=ahora)
        self.assertEqual([], V.problemas_uso_sello(s, **base))
        self.assertEqual("X40_SELLO", V.problemas_uso_sello(s, **{**base, "artefacto_sha256": "sha256:" + "0" * 64})[0][0])
        self.assertEqual("X40_VIGENCIA", V.problemas_uso_sello(s, **{**base, "ahora": ahora + dt.timedelta(days=2)})[0][0])
        self.assertEqual("X40_VIGENCIA", V.problemas_uso_sello(s, **{**base, "ahora": ahora - dt.timedelta(days=2)})[0][0])
        self.assertEqual("X40_OBJETOS", V.problemas_uso_sello(s, **{**base, "object_ids": s["object_ids"][:-1]})[0][0])

    def test_convertir_importe_exponentes_half_even(self) -> None:
        self.assertEqual(2149, V.convertir_importe(1990, "EUR", "USD", "1.0800"))        # 2149.2
        self.assertEqual(1841, V.convertir_importe(1990, "EUR", "USD", "0.9250"))        # 1840.75
        self.assertEqual(1620, V.convertir_importe(1000, "EUR", "JPY", "162.0"))         # 10,00 EUR -> 1620 JPY (exponente 0)
        self.assertEqual(50, V.convertir_importe(100, "EUR", "USD", "0.5"))
        self.assertEqual(2, V.convertir_importe(5, "EUR", "USD", "0.5"))                 # 2.5 -> 2 (half-even)
        with self.assertRaises(KeyError):
            V.convertir_importe(1, "EUR", "KWD", "0.3")                                   # exponente 3 no registrado: fail-closed

    def test_conciliacion_incompleto_admite_diferencias_nulas(self) -> None:
        c = copy.deepcopy(_ej("conciliacion"))
        c.update(estado="INCOMPLETO", cifras_tachadas=True)
        self.assertEqual([], V.problemas_artefacto("conciliacion", c))
        c["estado"], c["cifras_tachadas"] = "DESCUADRE", True
        self.assertTrue(V.problemas_artefacto("conciliacion", c))      # DESCUADRE con diferencias 0 sería CONCILIADO

    def test_cobertura_minima_sale_de_los_parametros(self) -> None:
        par = V.cargar_yaml(V.RAIZ / "empresa" / "parametros.yaml")
        c = copy.deepcopy(_ej("conciliacion"))
        c["cobertura_adid_bp"] = 8000   # 80 % < testeo.cobertura_adid_min_pct (90)
        self.assertEqual([], V.problemas_artefacto("conciliacion", c))
        self.assertTrue(V.problemas_artefacto("conciliacion", c, parametros=par))

    def test_tipo_cambio_hash_contenido(self) -> None:
        t = copy.deepcopy(_ej("tipo_cambio"))
        t["tasa"] = "0.9300"
        self.assertTrue(V.problemas_artefacto("tipo_cambio", t))

    def test_ratio_de_disputas_no_menor_que_la_alerta(self) -> None:
        par = V.cargar_yaml(V.RAIZ / "empresa" / "parametros.yaml")           # disputas_alerta_pct = 0.3 => 0.003
        self.assertEqual([], V.coherencia_limites_parametros({"ratio_disputas_pausa": "0.006"}, par))
        self.assertTrue(V.coherencia_limites_parametros({"ratio_disputas_pausa": "0.001"}, par))
        self.assertEqual([], V.coherencia_limites_parametros({"ratio_disputas_pausa": None}, par))

    def test_exponentes_cubren_las_monedas_del_marco(self) -> None:
        self.assertEqual(2, V.EXPONENTE_ISO4217["EUR"])
        self.assertEqual(0, V.EXPONENTE_ISO4217["JPY"])
        self.assertNotIn("XXX", V.EXPONENTE_ISO4217)


class PruebaEmpresaConParametros(unittest.TestCase):
    def test_ordenes_en_disco_con_nonce_repetido_en_mayusculas(self) -> None:
        import tempfile, json
        with tempfile.TemporaryDirectory() as t:
            emp = Path(t)
            o = _ej("orden_firmada")
            o2 = dict(o, ts="2026-11-10T09:05:00Z")
            (emp / "ordenes_firmadas.jsonl").write_text(json.dumps(o) + "\n" + json.dumps(o2) + "\n", encoding="utf-8")
            inf = V.Informe("t")
            V.validar_artefactos_de_empresa(emp, inf, clave=CLAVE)
            self.assertIn("X40_NONCE", {h.codigo for h in inf.errores})


if __name__ == "__main__":
    unittest.main()
