"""Pruebas de salud.py, control_previo.py y avisos.py (escalar-oferta) y de cupo_lanzamiento.py (modelar-y-lanzar-oferta)."""
from __future__ import annotations

import datetime as dt
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / ".claude" / "skills" / "escalar-oferta" / "scripts"))
sys.path.insert(0, str(RAIZ / ".claude" / "skills" / "modelar-y-lanzar-oferta" / "scripts"))
sys.path.insert(0, str(RAIZ))
import avisos as A  # noqa: E402
import control_previo as CP  # noqa: E402
import cupo_lanzamiento as CL  # noqa: E402
import salud as SA  # noqa: E402

AHORA = dt.datetime(2026, 11, 13, 18, 0, tzinfo=dt.timezone.utc)


def test_libro(estado="activo", precios=(13, 19, 27), pixel="999"):
    return {"tests": [{"nombre": "Oferta", "estado": estado, "mercado": "MX",
                       "ficha": {"pixel": {"id": pixel}, "tiendas": [{"url": "https://t.example/", "precio": {"usd": p}} for p in precios]},
                       "backend": {"estado": "activo"}}]}


def ok_html(html="<script>fbq('init','999')</script>"):
    return lambda url: {"ok": True, "estado": 200, "ms": 100, "html": html}


def caida(url):
    return {"ok": False, "estado": 502, "ms": 100, "html": ""}


class TestSalud(unittest.TestCase):
    def test_caida_dos_vueltas_pausa_y_reactiva_solo_lo_suyo(self) -> None:
        lib = test_libro()
        lec = {"meta_ok": True, "tests": {"Oferta": {"campanas_activas": ["c1"]}}}
        acc, est = SA.evaluar(lec, lib, {}, caida)
        self.assertEqual([a["accion"] for a in acc], [], "una sola caída no pausa")
        acc, est = SA.evaluar(lec, lib, est, caida)
        self.assertEqual([a["accion"] for a in acc], ["PAUSAR_POR_CAIDA"])
        SA.aplicar_resultado(est, "PAUSAR_POR_CAIDA", "Oferta", ["c1"])
        acc, est = SA.evaluar({"meta_ok": True, "tests": {"Oferta": {}}}, lib, est, ok_html())
        self.assertEqual([(a["accion"], a["campanas"]) for a in acc], [("REACTIVAR_TRAS_CAIDA", ["c1"])])

    def test_pixel_checkout_rechazos_embudo_cuenta_conector(self) -> None:
        lib = test_libro()
        lec = {"meta_ok": True, "cuenta": {"account_status": 2, "spend_cap_usd": 1000, "amount_spent_usd": 850},
               "tests": {"Oferta": {"campanas_activas": ["c1"], "inicios_pago_hoy": 12, "compras_hoy": 0, "rechazados": [{"id": "a"}],
                                    "ventas_hoy": 3, "vistas_embudo_hoy": 0}}}
        acc, _ = SA.evaluar(lec, lib, {}, ok_html("<html>sin píxel</html>"))
        self.assertEqual(sorted(a["accion"] for a in acc), sorted(["AVISO_CUENTA", "AVISO_LIMITE", "AVISO_PIXEL", "PROBAR_CHECKOUT", "REVISAR_RECHAZOS", "EMBUDO_ROTO"]))
        est = {}
        for _ in range(3):
            acc, est = SA.evaluar({"meta_ok": False}, {"tests": []}, est, None)
        self.assertEqual([a["accion"] for a in acc], ["AVISO_CONECTOR"])


class TestControlPrevio(unittest.TestCase):
    def lectura(self, **k):
        base = {"oferta": "Oferta", "mercado": "MX", "presupuesto_usd": 81, "campana_nombre": "MX | Oferta | CBO test 10 videos",
                "conjuntos": [{"id": "s1", "start_time": "2026-11-14T00:00:00-0600"}], "anuncios": {"total": 10, "rechazados": 2}, "errores": [],
                "funnel": {"decision": "OK", "fallas": []}}
        base.update(k)
        return base

    def test_pasa_y_activa(self) -> None:
        r = CP.controlar(self.lectura(), test_libro("programado"), AHORA, ok_html())
        self.assertEqual(r["decision"], "ACTIVAR", r)

    def test_no_activa_por_cada_regla(self) -> None:
        lib = test_libro("programado")
        # rechazados (dueño, 16-nov): solo frena si no queda ninguno; pocket 1-1-1 con su único anuncio rechazado no sale
        self.assertEqual(CP.controlar(self.lectura(anuncios={"total": 10, "rechazados": 10}), lib, AHORA, ok_html())["decision"], "NO_ACTIVAR")
        self.assertEqual(CP.controlar(self.lectura(anuncios={"total": 1, "rechazados": 1, "previstos": 1}), lib, AHORA, ok_html())["decision"], "NO_ACTIVAR")
        self.assertEqual(CP.controlar(self.lectura(anuncios={"total": 2, "rechazados": 0}), lib, AHORA, ok_html())["decision"], "NO_ACTIVAR", "faltan anuncios cargados")
        self.assertEqual(CP.controlar(self.lectura(presupuesto_usd=50), lib, AHORA, ok_html())["decision"], "NO_ACTIVAR")
        self.assertEqual(CP.controlar(self.lectura(conjuntos=[{"id": "s1", "start_time": "2026-11-14T00:00:00-0300"}]), lib, AHORA, ok_html())["decision"], "NO_ACTIVAR", "00:00 de Argentina no es 00:00 de México")
        self.assertEqual(CP.controlar(self.lectura(conjuntos=[{"id": "s1", "start_time": "2026-11-13T00:00:00-0600"}]), lib, AHORA, ok_html())["decision"], "NO_ACTIVAR", "inicio pasado")
        self.assertEqual(CP.controlar(self.lectura(), test_libro("programado", precios=(13,)), AHORA, ok_html())["decision"], "NO_ACTIVAR", "precio bajo 19")
        self.assertEqual(CP.controlar(self.lectura(), lib, AHORA, caida)["decision"], "NO_ACTIVAR")
        # nombre «PAÍS | Oferta | tipo» (dueño, 16-nov): sin nombre, otro país u otra oferta no se activa
        self.assertEqual(CP.controlar(self.lectura(campana_nombre=None), lib, AHORA, ok_html())["decision"], "NO_ACTIVAR")
        self.assertEqual(CP.controlar(self.lectura(campana_nombre="BR | Oferta | CBO test"), lib, AHORA, ok_html())["decision"], "NO_ACTIVAR")
        self.assertEqual(CP.controlar(self.lectura(campana_nombre="Oferta CBO test MX"), lib, AHORA, ok_html())["decision"], "NO_ACTIVAR")
        self.assertTrue(all(z in CP.ZONA for z in ("MX", "BR", "PL", "JP", "AR")))

    def test_rechazados_no_frenan_si_quedan_otros(self) -> None:
        lib = test_libro("programado")
        self.assertEqual(CP.controlar(self.lectura(anuncios={"total": 10, "rechazados": 7}), lib, AHORA, ok_html())["decision"], "ACTIVAR")
        self.assertEqual(CP.controlar(self.lectura(anuncios={"total": 1, "rechazados": 0, "previstos": 1}), lib, AHORA, ok_html())["decision"], "ACTIVAR",
                         "pocket 1-1-1 con su anuncio aprobado sale")

    def test_pixel_de_otra_oferta_frena(self) -> None:
        lib = test_libro("programado")
        lib["tests"].append({"nombre": "Otra", "ficha": {"pixel": {"id": "999"}}})
        r = CP.controlar(self.lectura(), lib, AHORA, ok_html())
        self.assertEqual(r["decision"], "NO_ACTIVAR", "cada oferta tiene su público (dueño, 14-nov)")
        self.assertIn("Otra", r["avisar"])

    def test_replica_con_el_pixel_de_la_madre_tambien_frena(self) -> None:
        lib = test_libro("programado")
        lib["tests"].append({"nombre": "Oferta IT", "replica_de": "Oferta", "ficha": {"pixel": {"id": "999"}}})
        r = CP.controlar(self.lectura(), lib, AHORA, ok_html())
        self.assertEqual(r["decision"], "NO_ACTIVAR")
        self.assertIn("Oferta IT", r["avisar"])


class TestAvisos(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self._a, self._l = A.AVISOS, A.LATIDOS
        A.AVISOS, A.LATIDOS = Path(self.tmp.name) / "a.jsonl", Path(self.tmp.name) / "l.json"

    def tearDown(self) -> None:
        A.AVISOS, A.LATIDOS = self._a, self._l
        self.tmp.cleanup()

    def test_no_entregado_se_reintenta(self) -> None:
        self.assertTrue(A.avisar("x", "m", True, None, AHORA))
        self.assertTrue(A.no_llego("x", "Remote Control inactive"))
        self.assertEqual([a["clave"] for a in A.sin_entregar(AHORA)], ["x"])
        self.assertTrue(A.avisar("x", "m", True, None, AHORA + dt.timedelta(minutes=15)), "no llegó: vuelve a salir")
        self.assertEqual(A.sin_entregar(AHORA + dt.timedelta(minutes=16)), [])

    def test_no_repite_dentro_de_la_ventana(self) -> None:
        self.assertTrue(A.avisar("x", "m", True, None, AHORA))
        self.assertFalse(A.avisar("x", "m", True, None, AHORA + dt.timedelta(hours=1)))
        self.assertTrue(A.avisar("x", "m", True, None, AHORA + dt.timedelta(hours=4)))
        self.assertTrue(A.avisar("y", "m", False, None, AHORA))

    def test_latido_avisa_a_la_tercera_falla(self) -> None:
        for _ in range(2):
            self.assertLess(A.latido("radar-ofertas", "error", None, AHORA)["fallas_seguidas"], A.FALLAS_PARA_AVISAR)
        self.assertEqual(A.latido("radar-ofertas", "error", None, AHORA)["fallas_seguidas"], 3)
        self.assertEqual(A.latido("radar-ofertas", "ok", None, AHORA)["fallas_seguidas"], 0)


class TestCupo(unittest.TestCase):
    def test_ritmo_tope_banco_y_replica(self) -> None:
        lib = {"tests": []}
        hoy = AHORA.astimezone(dt.timezone(dt.timedelta(hours=-3))).date().isoformat()
        self.assertEqual(CL.decidir(lib, [{"fecha": hoy}, {"fecha": hoy}], {"listos": ["a", "b", "c"]}, AHORA)["decision"], "ESPERAR")
        r1 = CL.decidir(lib, [], {"listos": ["a"]}, AHORA)
        self.assertEqual(r1["decision"], "LANZAR_NUEVA")  # 14-nov: con 1 listo se lanza; la reserva de 3 se repone aparte
        self.assertTrue(r1["reponer_banco"])
        self.assertEqual(CL.decidir(lib, [], {"listos": []}, AHORA)["decision"], "BUSCAR_Y_LANZAR")  # nunca espera por el banco
        self.assertFalse(CL.decidir(lib, [], {"listos": ["a", "b", "c"]}, AHORA)["reponer_banco"])
        self.assertEqual(CL.decidir(lib, [{"fecha": hoy}], {"listos": ["a", "b", "c"]}, AHORA)["decision"], "LANZAR_NUEVA")


if __name__ == "__main__":
    unittest.main()


class TestUltimaTanda(unittest.TestCase):
    def test_libro_con_candado_respaldo_y_atomico(self) -> None:
        import json as _j
        import threading
        import libro as LB
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "libro-de-tests.json"
            p.write_text(_j.dumps({"tests": [{"nombre": "T", "ventas": []}]}), encoding="utf-8")
            hilos = [threading.Thread(target=LB.modificar, args=(lambda L, i=i: LB.poner(LB._test(L, "T"), "ventas", {"orden": i}, "append"), p)) for i in range(20)]
            for h in hilos:
                h.start()
            for h in hilos:
                h.join()
            self.assertEqual(len(_j.loads(p.read_text())["tests"][0]["ventas"]), 20, "ninguna escritura pisó a otra")
            self.assertTrue(any((Path(d) / ".respaldos").glob("libro-*.json")))
            LB.modificar(lambda L: LB.poner(LB._test(L, "T"), "ficha.campanas", [{"id": "1"}], "set"), p)
            self.assertEqual(_j.loads(p.read_text())["tests"][0]["ficha"]["campanas"][0]["id"], "1")

    def test_salud_activos_y_sesiones(self) -> None:
        lec = {"meta_ok": True, "activos": [{"tipo": "pagina", "nombre": "Oferta D Negocios", "oferta": "X", "ok": False, "motivo": "restringida"}],
               "sesiones": {"impultienda": False, "facebook": True}}
        acc, _ = SA.evaluar(lec, {"tests": []}, {}, None)
        self.assertEqual(sorted(a["accion"] for a in acc), ["AVISO_ACTIVO", "AVISO_SESION"])

    def test_chequeos_diarios(self) -> None:
        import chequeos_diarios as CD
        self.assertEqual(CD.chequear_kie(10000), [])
        self.assertTrue(CD.chequear_kie(3000)[0]["urgente"] is False and CD.chequear_kie(2000)[0]["urgente"])
        self.assertEqual(CD.chequear_kie(None)[0]["clave"], "kie-sin-lectura")
        ventas = [{"tienda": "t", "moneda": "MXN", "bruto": 100, "neto": 92, "fecha": f"2026-11-0{i}"} for i in range(1, 5)]
        lib = {"tipos_de_cambio": {"fecha": "2026-11-12"}, "tests": [{"nombre": "T", "ventas": ventas + [{"tienda": "t", "moneda": "MXN", "bruto": 100, "neto": 89, "fecha": "2026-11-09"}]}]}
        av = CD.chequear_comisiones(lib, dt.date(2026, 11, 13))
        self.assertEqual([a["clave"] for a in av], ["comision-t"])
        lib["tipos_de_cambio"]["fecha"] = "2026-11-01"
        self.assertIn("tipos-de-cambio", [a["clave"] for a in CD.chequear_comisiones(lib, dt.date(2026, 11, 13))])


class TestRadarReferentes(unittest.TestCase):
    def test_crece_y_hermanas(self) -> None:
        sys.path.insert(0, str(RAIZ / ".claude" / "skills" / "buscar-ofertas" / "scripts"))
        import radar as R
        serie: list = []
        hoy = dt.date(2026, 11, 13)
        for n in (40, 42, 41):
            self.assertFalse(R.medir_referente(serie, n, 0, hoy)["crece"])
        self.assertTrue(R.medir_referente(serie, 52, 0, hoy)["crece"], "1,2 × el promedio")
        self.assertTrue(R.medir_referente(serie, 41, 3, hoy)["crece"], "3 anuncios nuevos en 3 días")
        ofertas: dict = {}
        c = R.agregar_hermana(ofertas, "https://otraoferta.com/es", "Operador", "hermana-de:joya-com", AHORA, R.dominios_compartidos(), set())
        self.assertEqual((c, ofertas[c]["estado"], ofertas[c]["tipos"]), ("otraoferta-com", "a_medir", ["hermana"]))
        refs = R.referentes_activos({"tests": [{"nombre": "A", "estado": "activo", "ficha": {"landing_original": "https://ref.example/x"}}]}, hoy)
        self.assertEqual(refs[0]["dominio"], "ref.example")
        self.assertIn("start_date[min]=2026-11-10", refs[0]["url_nuevos"])


class TestReglasCentrales(unittest.TestCase):
    def test_los_scripts_leen_sus_numeros_de_reglas_json(self) -> None:
        import json as _j
        import escalar_presupuesto as EP
        import vigilar_corte as VC
        from dashboard import negocio as N
        r = _j.loads((RAIZ / "ofertas" / "_funnels" / "reglas.json").read_text(encoding="utf-8"))
        self.assertEqual(VC.VECES_TICKET, r["test"]["corte_tickets"])
        self.assertEqual(N.VECES_TICKET_PARA_CORTAR, r["test"]["corte_tickets"], "panel y vigilancia con el mismo corte")
        self.assertEqual((EP.ROAS_SURF, EP.BAJAR, EP.ROAS_BAJAR), (r["escala"]["por_campana"]["roas_surf"], r["escala"]["bajar"], r["escala"]["por_campana"]["roas_bajar"]))
        self.assertEqual((CP.PRECIO_MIN_USD, CP.APROBADOS_MIN), (r["lanzamiento"]["precio_minimo_usd"], r["lanzamiento"]["rechazados"]["aprobados_minimos"]))
        self.assertEqual((CL.POR_DIA, CL.MAX_EN_TEST, CL.REPLICA_ROAS_NETO), (r["lanzamiento"]["por_dia"], r["lanzamiento"]["max_en_test"], r["replica"]["roas_neto_minimo"]))
        self.assertEqual(SA.CAIDAS_PARA_PAUSAR, r["salud"]["caidas_para_pausar"])
        self.assertEqual(A.FALLAS_PARA_AVISAR, r["avisos"]["fallas_para_avisar"])


class TestSegundaOportunidad(unittest.TestCase):
    def test_solo_con_senales_buenas_y_una_vez(self) -> None:
        import vigilar_corte as VC
        t = {"nombre": "T", "mercado": "MX", "inicio": "2026-11-13T00:00:00-06:00", "campana": "c1", "ventas": [],
             "ficha": {"tiendas": [{"rol": "principal", "precio": {"usd": 19}}], "campanas": [{"id": "c1"}]}}
        ahora = dt.datetime(2026, 11, 13, 20, 0, tzinfo=dt.timezone.utc)
        lec = {"campanas": {"c1": {"gasto_usd": 29, "compras_meta": 0, "estado": "ACTIVE"}}}
        self.assertEqual(VC.decidir(t, lec, ahora)["decision"], "APAGAR", "sin datos del embudo, se apaga como siempre")
        lec["embudo"] = {"T": {"ctr_pct": 1.4, "pagina_a_pago_pct": 9.0, "checkouts": 4}}
        d = VC.decidir(t, lec, ahora)
        self.assertEqual((d["decision"], d["corte_nuevo_usd"]), ("SEGUNDA_OPORTUNIDAD", 38.0), "2 tickets de 19")
        lec["embudo"]["T"]["ctr_pct"] = 0.6
        self.assertEqual(VC.decidir(t, lec, ahora)["decision"], "APAGAR", "si el anuncio no funciona, más plata no lo arregla")
        lec["embudo"]["T"]["ctr_pct"] = 1.4
        t["segunda_oportunidad"] = {"desde": "x"}
        self.assertEqual(VC.decidir(t, lec, ahora)["decision"], "SIGUE", "con la segunda oportunidad el corte es 38")
        lec["campanas"]["c1"]["gasto_usd"] = 38.5
        self.assertEqual(VC.decidir(t, lec, ahora)["decision"], "APAGAR", "una sola vez")
