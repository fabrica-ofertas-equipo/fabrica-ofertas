"""Pruebas de la escala por campaña con el AOV de la tienda (dueño, 16-nov) y de las fotos de campañas."""
from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / ".claude" / "skills" / "escalar-oferta" / "scripts"))
import escalar_presupuesto as E  # noqa: E402
import fotos_campanas as FC  # noqa: E402

AHORA = dt.datetime(2026, 11, 16, 15, 0, tzinfo=dt.timezone.utc)   # 12:00 ART, 16:00 en Madrid (+1)


def camp(compras: int, *, gasto: float = 100.0, aov: float | None = 50.0, horas: float = 4, pres: float = 200.0, inicial=None,
         valor_meta=None, ticket=54.0, g6=None, offset=1.0, fase="post", congelada=None, cpa_previo=None):
    return {"oferta": "X", "campana": "1", "rol": "pocket", "presupuesto_usd": pres, "presupuesto_inicial_usd": inicial,
            "ultimo_cambio": (AHORA - dt.timedelta(hours=horas)).isoformat(),
            "desde_cambio": {"gasto_usd": gasto, "compras": compras, "valor_meta_usd": valor_meta if valor_meta is not None else compras * 30.0},
            "aov_usd": aov, "ticket_usd": ticket, "gasto_ultimas_horas": g6, "utc_offset_mercado_h": offset, "fase": fase, "congelada": congelada,
            "cpa_previo_usd": cpa_previo, "cpa_previo_fuente": "sus 3 días anteriores" if cpa_previo else None}


class TestRegla(unittest.TestCase):
    # 17-nov: todo en NETO (aov_usd = valor neto por comprador), umbrales 1,65 / 1,4 / 2,75, ROAS acercado a lo previo y piso ≥ 1 para subir.
    def test_roas_con_valor_neto_y_no_con_el_valor_de_meta(self):
        # 8 compras × 50 ÷ 200 = 2,0 aunque Meta diga 1,2: surfea (sin previa, el piso de 8 compras pasa el empate)
        d = E.decidir(camp(8, gasto=200, valor_meta=240), AHORA)
        self.assertEqual((d["decision"], d["roas_aov"], d["roas_meta"]), ("SURFEAR", 2.0, 1.2))

    def test_umbral_1_65(self):
        self.assertEqual(E.decidir(camp(20, gasto=610), AHORA)["decision"], "MANTENER")    # 1000/610 = 1,64: no
        self.assertEqual(E.decidir(camp(20, gasto=606), AHORA)["decision"], "SURFEAR")     # 1,65
        self.assertEqual(E.decidir(camp(20, gasto=680), AHORA)["decision"], "MANTENER")    # 1,47: entre 1,4 y 1,65

    def test_piso_del_rango(self):
        # 2 compras con ROAS 2 en 4 h: el promedio pasa, pero con 2 compras puede ser suerte → se espera
        d = E.decidir(camp(2, gasto=50), AHORA)
        self.assertEqual(d["decision"], "MANTENER")
        self.assertIn("piso del rango", d["porque"])
        # las mismas 2 compras en una campaña que viene vendiendo a ROAS 2,5 (CPA 20): el previo respalda → sube
        d = E.decidir(camp(2, gasto=50, cpa_previo=20), AHORA)
        self.assertEqual(d["decision"], "SURFEAR")
        self.assertGreaterEqual(d["roas_piso"], 1.0)

    def test_acerca_a_lo_previo(self):
        # 3 compras con US$ 120 (crudo 1,25 → bajaría) en una campaña que venía a CPA 20 (ROAS 2,5): estimado 2,0 → no baja
        d = E.decidir(camp(3, gasto=120, pres=268, inicial=162, cpa_previo=20), AHORA)
        self.assertEqual((d["roas_crudo"], d["roas_aov"]), (1.25, 1.67))
        self.assertNotEqual(d["decision"], "BAJAR")
        # y al revés: 3 compras a ROAS crudo 1,25 en una campaña que venía a CPA 60 (0,83): baja
        self.assertEqual(E.decidir(camp(3, gasto=120, pres=268, inicial=162, cpa_previo=60), AHORA)["decision"], "BAJAR")

    def test_dosis_por_compras(self):
        self.assertEqual(E.decidir(camp(4, gasto=100, cpa_previo=25), AHORA)["cambio_pct"], 0.3)
        self.assertEqual(E.decidir(camp(8, gasto=200, cpa_previo=25), AHORA)["cambio_pct"], 0.4)
        self.assertEqual(E.decidir(camp(8, gasto=120, cpa_previo=15), AHORA)["cambio_pct"], 0.5)   # ROAS ≥ 2,75 → +10, tope 50

    def test_redondo(self):
        self.assertEqual(E.decidir(camp(8, gasto=200, pres=187, cpa_previo=25), AHORA)["presupuesto_nuevo_usd"], 262)   # 187 × 1,4

    def test_una_compra_no_alcanza(self):
        self.assertEqual(E.decidir(camp(1, gasto=20), AHORA)["decision"], "MANTENER")

    def test_tres_horas_entre_cambios(self):
        self.assertEqual(E.decidir(camp(4, horas=2), AHORA)["decision"], "MANTENER")

    def test_desde_500_cada_24h(self):
        self.assertEqual(E.decidir(camp(8, gasto=200, pres=500, horas=5), AHORA)["decision"], "MANTENER")
        d = E.decidir(camp(8, gasto=200, pres=500, horas=25), AHORA)
        self.assertEqual((d["decision"], d["presupuesto_nuevo_usd"]), ("SUBIR_24H", 650))

    def test_bajada_con_muestra_y_piso(self):
        d = E.decidir(camp(1, gasto=90, pres=268, inicial=162), AHORA)          # 50/90 = 0,56, 90 ≥ 1,5 × 54
        self.assertEqual((d["decision"], d["presupuesto_nuevo_usd"]), ("BAJAR", 188))
        self.assertEqual(E.decidir(camp(0, gasto=60, pres=268), AHORA)["decision"], "MANTENER")   # poca muestra
        d = E.decidir(camp(0, gasto=100, pres=200, inicial=162), AHORA)
        self.assertEqual(d["presupuesto_nuevo_usd"], 162)                                  # 140 < 162: piso
        self.assertEqual(E.decidir(camp(0, gasto=100, pres=162, inicial=162), AHORA)["decision"], "MANTENER")

    def test_no_gasta(self):
        # 200/día → 6 h son 50; gastó 15 (30 %) a las 16 en el mercado: no se sube
        self.assertEqual(E.decidir(camp(8, gasto=200, g6=15), AHORA)["decision"], "NO_GASTA")
        self.assertEqual(E.decidir(camp(8, gasto=200, g6=30), AHORA)["decision"], "SURFEAR")
        # de madrugada en el mercado el ritmo no se mira
        self.assertEqual(E.decidir(camp(8, gasto=200, g6=5, offset=-10), AHORA)["decision"], "SURFEAR")

    def test_tarde_en_el_mercado(self):
        self.assertEqual(E.decidir(camp(8, gasto=200, offset=7.5), AHORA)["decision"], "TARDE")      # 22:30 en el mercado

    def test_en_test_y_congelada(self):
        self.assertEqual(E.decidir(camp(4, fase="test"), AHORA)["decision"], "EN_TEST")
        self.assertEqual(E.decidir(camp(4, congelada={"hasta": "x", "motivo": "R16"}), AHORA)["decision"], "CONGELADA")

    def test_sin_valor_usa_valor_meta_en_neto(self):
        d = E.decidir(camp(8, gasto=200, aov=None, valor_meta=400), AHORA)   # 400 × 0,92 ÷ 200 = 1,84
        self.assertEqual((d["decision"], d["roas_aov"]), ("SURFEAR", 1.84))   # sin valor neto ni rango: el de Meta pasado a neto

    def test_sin_datos(self):
        self.assertEqual(E.decidir(camp(0, gasto=2), AHORA)["decision"], "SIN_DATOS")


class TestFotos(unittest.TestCase):
    def setUp(self):
        self.libro = {"zona_horaria_cuenta": "America/Argentina/Buenos_Aires", "tests": [{"oferta": "X", "campana": "1",
                      "historial_diario": [{"fecha": "2026-11-15", "campana": "1", "gasto_usd": 100, "compras_meta": 3, "valor_compras_meta_usd": 150}]}]}

        def foto(hora_utc, g, n, p=200):
            return {"t": dt.datetime(2026, 11, 16, hora_utc, 0, tzinfo=dt.timezone.utc).isoformat(), "dia": "2026-11-16",
                    "c": {"1": {"p": p, "e": "ACTIVE", "g": g, "n": n, "v": n * 30, "ic": 0}}}
        self.fotos = [foto(4, 10, 0), foto(10, 40, 1), foto(14, 70, 3)]
        self.fotos[2]["t"] = "2026-11-16T14:50:00+00:00"   # 10 min antes de AHORA: lectura exacta

    def test_desde_cambio_de_hoy(self):
        d = FC.desde_cambio(self.libro, "1", dt.datetime(2026, 11, 16, 10, 5, tzinfo=dt.timezone.utc), AHORA, self.fotos)
        self.assertEqual((d["gasto_usd"], d["compras"], d["exacto"]), (30.0, 2, True))

    def test_desde_cambio_de_ayer(self):
        # cambio ayer sin fotos de ese día: cuenta el día entero (aproximado) + hoy
        d = FC.desde_cambio(self.libro, "1", dt.datetime(2026, 11, 15, 20, 0, tzinfo=dt.timezone.utc), AHORA, self.fotos)
        self.assertEqual((d["gasto_usd"], d["compras"], d["exacto"]), (170.0, 6, False))

    def test_eventos_y_autor(self):
        with tempfile.TemporaryDirectory() as tmp:
            viejos = (FC.FOTOS, FC.EVENTOS, FC.ESTADO, FC.ESCALA)
            FC.FOTOS, FC.EVENTOS, FC.ESTADO, FC.ESCALA = (Path(tmp) / n for n in ("f.jsonl", "e.jsonl", "s.json", "esc.jsonl"))
            try:
                FC.ESCALA.write_text(json.dumps({"ahora": "2026-11-16T13:30:00+00:00", "ofertas": [
                    {"campana": "1", "decision": "SURFEAR", "presupuesto_nuevo_usd": 260, "porque": "surfeo"}]}) + "\n")
                FC.registrar(self.fotos[0], self.libro)
                f2 = json.loads(json.dumps(self.fotos[1]))
                f2["c"]["1"]["p"] = 260
                ev = FC.registrar(f2, self.libro)
                self.assertEqual([(e["de"], e["a"], e["autor"]) for e in ev], [(200, 260, "a_mano")])   # la decisión fue después
                f3 = json.loads(json.dumps(self.fotos[2]))
                f3["c"]["1"]["p"] = 338
                FC.ESCALA.write_text(json.dumps({"ahora": "2026-11-16T13:50:00+00:00", "ofertas": [
                    {"campana": "1", "decision": "SURFEAR", "presupuesto_nuevo_usd": 338, "porque": "surfeo"}]}) + "\n")
                ev = FC.registrar(f3, self.libro)
                self.assertEqual([(e["a"], e["autor"]) for e in ev], [(338, "sistema")])
                self.assertEqual(len(FC.eventos()), 2)
            finally:
                FC.FOTOS, FC.EVENTOS, FC.ESTADO, FC.ESCALA = viejos


class TestCampanasNuevas(unittest.TestCase):
    def test_asigna_por_nombre_y_mercado(self):
        libro = {"tests": [{"oferta": "Oferta", "nombre": "Oferta", "mercado": "IE", "campana": "1", "ficha": {"campanas": [{"id": "1", "rol": "principal", "estado": "ACTIVE"}]}},
                           {"oferta": "Oferta F", "mercado": "ES", "campana": "2"}]}
        meta = [{"id": "9", "nombre": "IE | Oferta | CBO POCKET B09", "estado": "ACTIVE", "presupuesto_usd": 80},
                {"id": "8", "nombre": "ES | Oferta F | CBO variaciones B10", "estado": "ACTIVE", "presupuesto_usd": 162},
                {"id": "7", "nombre": "US | Oferta F | CBO test", "estado": "ACTIVE", "presupuesto_usd": 50},   # otro mercado: no se mezcla
                {"id": "6", "nombre": "CBO Test Videos 1", "estado": "ACTIVE", "presupuesto_usd": 40},
                {"id": "1", "nombre": "IE | Oferta | test", "estado": "PAUSED", "presupuesto_usd": 162}]
        cambios, sin = FC.asignar_campanas(libro, meta, AHORA)
        ie = libro["tests"][0]["ficha"]["campanas"]
        self.assertEqual([(x["id"], x["rol"]) for x in ie], [("1", "principal"), ("9", "pocket")])
        self.assertEqual(ie[0]["estado"], "PAUSED")
        self.assertIn("apagada_desde", ie[0])
        es = libro["tests"][1]["ficha"]["campanas"]
        self.assertEqual([(x["id"], x["rol"]) for x in es], [("2", "principal"), ("8", "test_variaciones")])
        self.assertEqual(sorted(x["id"] for x in sin), ["6", "7"])
        self.assertEqual(len(cambios), 3)

    def test_no_pisa_la_nota_del_estado(self):
        libro = {"tests": [{"oferta": "X", "mercado": "MX", "campana": "1", "ficha": {"campanas": [{"id": "1", "estado": "PAUSED (apagada por corte)"}]}}]}
        cambios, _ = FC.asignar_campanas(libro, [{"id": "1", "nombre": "MX | X | t", "estado": "PAUSED", "presupuesto_usd": 50}], AHORA)
        self.assertEqual((cambios, libro["tests"][0]["ficha"]["campanas"][0]["estado"]), ([], "PAUSED (apagada por corte)"))


if __name__ == "__main__":
    unittest.main()
