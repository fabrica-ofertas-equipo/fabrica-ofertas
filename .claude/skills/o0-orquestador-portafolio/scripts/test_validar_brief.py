"""Pruebas de `validar_brief.py` (sin red, sin tocar `empresa/` ni `ofertas/` reales: solo lee la oferta de ejemplo y trabaja en memoria).

Correr (desde la raíz): .venv/bin/python .claude/skills/o0-orquestador-portafolio/scripts/test_validar_brief.py
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validar_brief as vb  # noqa: E402

ve = vb.ve
EJ = vb.RAIZ / "ofertas" / "_ejemplo"


def brief_base(**cambios) -> dict:
    """Brief del ejemplo con diario <= tope / 1,75, borrador sin firma y hash recalculado."""
    b = ve.cargar_yaml(EJ / "00-brief.yaml")
    b["presupuesto"]["test_diario_max"]["monto"] = 2857
    b["aprobado_por"]["firma"] = None
    for k, v in cambios.items():
        b[k] = v
    b["hash"] = ve.hash_objeto(b, excluir=("hash", "aprobado_por"))
    return b


def rehash(b: dict) -> dict:
    b["hash"] = ve.hash_objeto(b, excluir=("hash", "aprobado_por"))
    return b


def correr(b, lim="prueba", cands=None, cand=None, minimo=None, aut=None):
    inf = vb.Informe()
    limites = ve.limites_de_prueba() if lim == "prueba" else lim
    vb.validar(b, limites, aut, cands, cand, minimo, inf)
    return inf


def codigos(inf) -> set[str]:
    return {e["codigo"] for e in inf.errores}


class PruebasBrief(unittest.TestCase):
    def test_borrador_valido_sale_0_con_aviso_de_firma(self):
        inf = correr(brief_base())
        self.assertEqual((inf.salida(), inf.errores), (0, []))
        self.assertIn("B03_SIN_FIRMA", {w["codigo"] for w in inf.avisos})

    def test_s1_total_sobre_el_tope_sale_5(self):
        b = brief_base()
        b["presupuesto"]["test_total_max"]["monto"] = ve.limites_de_prueba()["gasto_total_test_por_oferta"] + 1
        inf = correr(rehash(b))
        self.assertEqual(inf.salida(), 5)
        self.assertIn("B11_TOPES", codigos(inf))

    def test_tope_exacto_pasa(self):
        b = brief_base()
        b["presupuesto"]["test_total_max"]["monto"] = ve.limites_de_prueba()["gasto_total_test_por_oferta"]
        self.assertEqual(correr(rehash(b)).salida(), 0)

    def test_s12_diario_igual_al_tope_sale_5(self):
        b = brief_base()
        b["presupuesto"]["test_diario_max"]["monto"] = ve.limites_de_prueba()["gasto_diario_por_oferta"]
        inf = correr(rehash(b))
        self.assertEqual(inf.salida(), 5)
        self.assertTrue(any("techo teórico" in e["mensaje"] for e in inf.errores))

    def test_s10_moneda_distinta_a_moneda_limites_sale_3_y_no_crea_nada(self):
        b = brief_base()
        for k in ("test_total_max", "test_diario_max", "ia_max"):
            b["presupuesto"][k]["moneda"] = "USD"
        inf = correr(rehash(b))
        self.assertEqual(inf.salida(), 3)
        self.assertIn("B10_MONEDA", codigos(inf))

    def test_s15_locale_no_permitido_sale_5(self):
        b = brief_base()
        b["mercado_objetivo"]["locale"] = "it-IT"
        b["mercado_objetivo"]["paises_segmentacion"] = ["IT"]
        inf = correr(rehash(b))
        self.assertEqual(inf.salida(), 5)
        self.assertTrue({"B13_LOCALE", "B13_PAIS"} <= codigos(inf))

    def test_cuenta_fuera_de_limites_sale_5(self):
        b = brief_base(cuenta_meta_id="act_999999999999999")
        self.assertIn("B13_CUENTA", codigos(correr(rehash(b))))

    def test_limites_ausentes_o_con_null_fallan_cerrado(self):
        self.assertEqual(correr(brief_base(), lim=None).salida(), 5)
        lim = ve.limites_de_prueba()
        lim["moneda_limites"] = None
        self.assertEqual(correr(brief_base(), lim=lim).salida(), 5)
        lim = ve.limites_de_prueba()
        lim["locales_permitidos"] = []
        self.assertEqual(correr(brief_base(), lim=lim).salida(), 5)

    def test_hash_que_no_coincide_sale_3(self):
        b = brief_base()
        b["precio_rango"]["max"]["monto"] += 100  # contenido cambiado sin recalcular el hash
        inf = correr(b)
        self.assertEqual(inf.salida(), 3)
        self.assertIn("B02_HASH", codigos(inf))

    def test_esquema_invalido_sale_3(self):
        b = brief_base()
        del b["presupuesto"]["ia_max"]
        self.assertIn("B01_ESQUEMA", codigos(correr(b)))

    def test_nicho_fuera_del_marco_o_subnicho_quitado_sale_3(self):
        lim = ve.limites_de_prueba()
        lim["macro_nichos_permitidos"] = ["salud", "relaciones"]
        self.assertIn("B12_NICHOS", codigos(correr(brief_base(), lim=lim)))
        lim = ve.limites_de_prueba()
        lim["subnichos_prohibidos"] = ["x-prohibido"]
        self.assertIn("B12_NICHOS", codigos(correr(brief_base(), lim=lim)))

    def test_nivel_del_brief_no_supera_a_autonomia(self):
        aut = {"nivel_por_etapa": {"O0": {"nivel": "N1"}}}
        inf = correr(brief_base(), aut=aut)  # el ejemplo declara N2
        self.assertIn("B14_NIVEL", codigos(inf))

    def test_firma_con_formato_invalido_sale_3(self):
        b = brief_base()
        b["aprobado_por"]["firma"] = "ed25519:AAAA"
        self.assertIn("B01_ESQUEMA", codigos(correr(b)))

    def test_presupuesto_minimo_del_mercado(self):
        b = brief_base()
        self.assertEqual(correr(b, minimo=b["presupuesto"]["test_total_max"]["monto"]).salida(), 0)
        self.assertEqual(correr(b, minimo=b["presupuesto"]["test_total_max"]["monto"] + 1).salida(), 5)

    def candidatos(self):
        return ve.cargar_json(EJ / "01-descubrimiento" / "candidatos.json")

    def test_candidato_verde_en_su_macro_nicho_pasa(self):
        inf = correr(brief_base(), cands=self.candidatos(), cand="CAND-01")
        self.assertEqual((inf.salida(), inf.errores), (0, []))

    def test_candidato_rojo_sale_3(self):
        c = copy.deepcopy(self.candidatos())
        r = c["candidatos"][0]["riesgo"]
        r.update({"P": "rojo", "nivel": "rojo"})
        r["reencuadre_aplicado"] = {"aplicado": False}
        self.assertIn("B21_ROJO", codigos(correr(brief_base(), cands=c, cand="CAND-01")))

    def test_amarillo_con_dos_ejes_amarillos_es_b_y_con_uno_es_a(self):
        for amarillos, esperado in ((1, "AMARILLO-A"), (2, "AMARILLO-B")):
            c = copy.deepcopy(self.candidatos())
            r = c["candidatos"][0]["riesgo"]
            for eje in ("P", "C", "E", "N"):
                r[eje] = "verde"
            for eje in ("P", "C", "E", "N")[:amarillos]:
                r[eje] = "amarillo"
            r.update({"nivel": "amarillo"})
            r["reencuadre_aplicado"] = {"aplicado": False}
            inf = correr(brief_base(), cands=c, cand="CAND-01")
            avisos = [w["mensaje"] for w in inf.avisos if w["codigo"] == "B21_AMARILLO"]
            self.assertEqual(len(avisos), 1, inf.errores)
            self.assertIn(esperado, avisos[0])
            self.assertNotIn("PENDIENTE", avisos[0])

    def test_candidato_fuera_de_macro_nicho_del_brief_sale_3(self):
        b = brief_base()
        b["nichos"]["permitidos"] = ["salud"]
        self.assertIn("B22_MACRO_NICHO", codigos(correr(rehash(b), cands=self.candidatos(), cand="CAND-01")))

    def test_evidencia_de_otro_locale_sale_3(self):
        c = copy.deepcopy(self.candidatos())
        c["mercado"]["locale"] = "pl-PL"
        self.assertIn("B23_LOCALE", codigos(correr(brief_base(), cands=c, cand="CAND-01")))

    def test_candidato_inexistente_sale_3(self):
        self.assertIn("B20_CANDIDATO", codigos(correr(brief_base(), cands=self.candidatos(), cand="CAND-99")))


if __name__ == "__main__":
    unittest.main()
