"""Pruebas de ``proponer.py``: tabla de verdad de la regla J3 del día 1 y alarma de cansancio 3 d contra 7 d."""
from __future__ import annotations

import copy
import json
import re
import unittest

from tests.skills_d8._comun import cargar_modulo, no_hay_floats, umbrales_prueba

P = cargar_modulo("proponer")
RX_CODIGO = re.compile(r"^[A-Z][A-Z0-9_]*$")  # decision.schema.json: codigo
ACCIONES_CONTRATO = {"MATAR", "SEGUIR", "ESCALAR", "INCONCLUSO", "BLOQUEADO"}


def entrada_dia1(**cambios) -> dict:
    """Día 1 completo, sin venta, con el presupuesto gastado y todo sano: debe dar APAGAR."""
    e = {
        "schema_version": "0.1.0", "tipo": "entrada_d8", "oferta_id": "OF-202611-02", "fecha_cuenta": "2026-11-08",
        "tz": "Europe/Warsaw", "ahora": "2026-11-09T09:00:00Z", "solo_lectura": True, "moneda_meta": "USD", "monedas_pedido": [],
        "presupuesto": {"diario_minor": 7500, "moneda": "USD", "fuente": "ofertas/OF-202611-02/07-campana/campana.json:presupuesto.diario"},
        "contexto": {"pausa_activa": False, "infra_semaforo": "VERDE", "traspaso_lanzamiento_estable": True, "pedidos_creativos_abiertos": 0},
        "frescura": {"ultima_ingesta_meta_ts": "2026-11-09T08:30:00Z", "edad_ingesta_meta_min": 30,
                     "ultima_ingesta_pedidos_ts": None, "edad_ingesta_pedidos_min": None},
        "campaign_ids": ["120000000000001"], "primer_dia_con_gasto": "2026-11-08", "dias_cerrados_desde_primer_gasto": 1,
        "dia": {"fecha": "2026-11-08", "cerrado": True, "gasto_minor": 7400, "impresiones": 18000, "clics_enlace": 160, "compras_meta": 0,
                "ventas_stripe_total": 0, "ventas_stripe_atribuidas": 0, "ventas_stripe_sin_atribucion": 0, "pedidos_pendientes": 0,
                "ventas_con_reembolso": 0, "vistas_landing": 130, "vistas_landing_con_adid": 125, "initiate_checkout": 4,
                "ingesta_meta_posterior_al_cierre": True, "minutos_desde_cierre": 600},
        "acumulado": {"desde": "2026-11-08", "gasto_minor": 7400, "ventas_stripe_total": 0, "ventas_stripe_atribuidas": 0,
                      "ventas_stripe_sin_atribucion": 0, "pedidos_pendientes": 0},
        "cobertura_adid_bp": None, "disputas_abiertas": 0,
        "serie_oferta": [{"fecha": "2026-11-08", "gasto_minor": 7400, "impresiones": 18000, "clics_enlace": 160, "compras_meta": 0,
                          "ventas_stripe_total": 0, "ventas_stripe_atribuidas": 0, "ventas_stripe_sin_atribucion": 0, "pedidos_pendientes": 0}],
        "anuncios": [], "avisos": [],
    }
    for k, v in cambios.items():
        if "." in k:
            a, b = k.split(".", 1)
            e[a][b] = v
        else:
            e[k] = v
    return e


class PruebaLanzamientoJ3(unittest.TestCase):
    def setUp(self) -> None:
        self.u = umbrales_prueba()

    def evaluar(self, e=None, **u_cambios) -> dict:
        u = {**self.u, **u_cambios}
        r = P.evaluar_lanzamiento(e or entrada_dia1(), u)
        self.assertEqual(no_hay_floats(r), [], "la salida no puede llevar float")
        self.assertIn(r["accion_contrato"], ACCIONES_CONTRATO)
        self.assertRegex(r["codigo"], RX_CODIGO)
        self.assertEqual(r["accion_contrato"], P.ACCION_CONTRATO[r["accion_negocio"]])
        self.assertTrue(r["es_propuesta"])
        return r

    def test_dia1_sin_venta_con_gasto_cumplido_propone_baja(self) -> None:
        r = self.evaluar()
        self.assertEqual((r["accion_negocio"], r["codigo"]), ("APAGAR", "LANZAMIENTO_SIN_VENTA_J3"))
        self.assertEqual(r["accion_contrato"], "MATAR")
        self.assertEqual(r["evidencia"]["gasto_dia_bp"], 9866)  # 7400 de 7500
        self.assertEqual(r["evidencia"]["tasa_conexion_bp"], 8125)  # 130 vistas / 160 clics

    def test_salvaguarda_sin_gasto_cumplido_mantiene(self) -> None:
        e = entrada_dia1(**{"dia.gasto_minor": 3100})
        e["serie_oferta"][0]["gasto_minor"] = 3100
        r = self.evaluar(e)
        self.assertEqual((r["accion_negocio"], r["codigo"]), ("MANTENER", "ENTREGA_INCOMPLETA"))
        self.assertEqual(r["evidencia"]["dias_sin_entrega_consecutivos"], 1)

    def test_borde_del_gasto_cumplido(self) -> None:
        for gasto, esperado in ((6750, "APAGAR"), (6749, "MANTENER")):  # 90 % exacto de 7500 cuenta; 1 menos no
            e = entrada_dia1()
            e["dia"]["gasto_minor"] = e["serie_oferta"][0]["gasto_minor"] = gasto
            self.assertEqual(self.evaluar(e)["accion_negocio"], esperado, gasto)

    def test_dos_dias_seguidos_sin_entrega_escala_a_d7_y_pausa(self) -> None:
        e = entrada_dia1(primer_dia_con_gasto="2026-11-07", dias_cerrados_desde_primer_gasto=2)
        e["serie_oferta"] = [
            {"fecha": "2026-11-07", "gasto_minor": 1200, "impresiones": 3000, "clics_enlace": 30},
            {"fecha": "2026-11-08", "gasto_minor": 2000, "impresiones": 5000, "clics_enlace": 50},
        ]
        e["dia"]["gasto_minor"] = 2000
        r = self.evaluar(e)
        self.assertEqual((r["accion_negocio"], r["codigo"], r["escalar_a"]), ("PAUSAR_Y_ESCALAR", "ENTREGA_INSUFICIENTE_PERSISTENTE", "D7"))
        self.assertEqual(r["accion_contrato"], "INCONCLUSO")

    def test_primer_dia_parcial_no_cuenta_y_el_segundo_si(self) -> None:
        e = entrada_dia1(primer_dia_con_gasto="2026-11-07", dias_cerrados_desde_primer_gasto=2)
        e["serie_oferta"] = [
            {"fecha": "2026-11-07", "gasto_minor": 1200, "impresiones": 3000, "clics_enlace": 30},
            {"fecha": "2026-11-08", "gasto_minor": 7400, "impresiones": 18000, "clics_enlace": 160},
        ]
        self.assertEqual(self.evaluar(e)["accion_negocio"], "APAGAR")

    def test_con_una_venta_nunca_se_baja(self) -> None:
        e = entrada_dia1()
        e["acumulado"].update(ventas_stripe_total=1, ventas_stripe_atribuidas=1)
        r = self.evaluar(e)
        self.assertEqual((r["accion_negocio"], r["codigo"]), ("MANTENER", "LANZAMIENTO_CON_VENTA"))

    def test_venta_sin_atribucion_tampoco_baja(self) -> None:
        e = entrada_dia1()
        e["acumulado"].update(ventas_stripe_total=1, ventas_stripe_atribuidas=0, ventas_stripe_sin_atribucion=1)
        r = self.evaluar(e)
        self.assertEqual((r["accion_negocio"], r["codigo"], r["escalar_a"]), ("MANTENER", "VENTA_SIN_ATRIBUCION", "D5"))

    def test_pago_asincrono_pendiente_espera(self) -> None:
        e = entrada_dia1()
        e["acumulado"]["pedidos_pendientes"] = 1
        self.assertEqual(self.evaluar(e)["codigo"], "PENDIENTES_ASINCRONOS")

    def test_garantia_nunca_baja_con_ventas_en_una_malla_de_casos(self) -> None:
        for ventas in (1, 2, 5):
            for gasto in (0, 3000, 6749, 6750, 9000, 13000):
                e = entrada_dia1()
                e["dia"]["gasto_minor"] = e["serie_oferta"][0]["gasto_minor"] = gasto
                e["acumulado"].update(ventas_stripe_total=ventas, ventas_stripe_atribuidas=ventas)
                self.assertNotEqual(self.evaluar(e)["accion_negocio"], "APAGAR", (ventas, gasto))

    def test_umbral_faltante_no_decide(self) -> None:
        r = self.evaluar(**{"lanzamiento.gasto_cumplido_min_pct": None})
        self.assertEqual((r["accion_negocio"], r["codigo"], r["accion_contrato"]), ("NO_DECIDIR", "UMBRAL_FALTANTE", "BLOQUEADO"))
        self.assertEqual(r["umbrales_faltantes"], ["lanzamiento.gasto_cumplido_min_pct"])

    def test_j3_exige_la_salvaguarda_de_presupuesto_gastado(self) -> None:
        r = self.evaluar(**{"lanzamiento.baja_requiere_presupuesto_gastado": False})
        self.assertEqual(r["codigo"], "UMBRAL_INCOHERENTE_J3")

    def test_pausa_manda(self) -> None:
        r = self.evaluar(entrada_dia1(**{"contexto": {**entrada_dia1()["contexto"], "pausa_activa": True}}))
        self.assertEqual((r["accion_negocio"], r["codigo"]), ("NO_DECIDIR", "PAUSA_ACTIVA"))

    def test_contexto_desconocido_es_fail_closed(self) -> None:
        e = entrada_dia1()
        e["contexto"].update(pausa_activa=None)
        self.assertEqual(self.evaluar(e)["codigo"], "CONTEXTO_DESCONOCIDO")
        e = entrada_dia1()
        e["contexto"].update(infra_semaforo=None)
        self.assertEqual(self.evaluar(e)["codigo"], "CONTEXTO_DESCONOCIDO")

    def test_infra_no_verde(self) -> None:
        e = entrada_dia1()
        e["contexto"]["infra_semaforo"] = "AMARILLO"
        self.assertEqual(self.evaluar(e)["codigo"], "INFRA_NO_VERDE")

    def test_sin_presupuesto_y_moneda_incoherente(self) -> None:
        self.assertEqual(self.evaluar(entrada_dia1(presupuesto=None))["codigo"], "SIN_PRESUPUESTO")
        e = entrada_dia1()
        e["avisos"] = ["moneda_presupuesto_distinta: campana.json EUR vs Meta USD"]
        self.assertEqual(self.evaluar(e)["codigo"], "MONEDA_INCOHERENTE")

    def test_datos_obsoletos_o_sin_ingesta(self) -> None:
        e = entrada_dia1()
        e["frescura"]["edad_ingesta_meta_min"] = 361
        self.assertEqual(self.evaluar(e)["codigo"], "DATOS_OBSOLETOS")
        e = entrada_dia1()
        e["frescura"].update(ultima_ingesta_meta_ts=None, edad_ingesta_meta_min=None)
        self.assertEqual(self.evaluar(e)["codigo"], "SIN_INGESTA_META")

    def test_aun_sin_gasto_dia_abierto_y_espera_de_compras_tardias(self) -> None:
        self.assertEqual(self.evaluar(entrada_dia1(primer_dia_con_gasto=None))["codigo"], "SIN_GASTO_AUN")
        e = entrada_dia1()
        e["dia"]["cerrado"] = False
        self.assertEqual(self.evaluar(e)["codigo"], "DIA_NO_CERRADO")
        e = entrada_dia1()
        e["dia"]["minutos_desde_cierre"] = 539
        self.assertEqual(self.evaluar(e)["codigo"], "ESPERA_COMPRAS_TARDIAS")

    def test_dia_ingerido_antes_del_cierre_no_se_decide(self) -> None:
        e = entrada_dia1()
        e["dia"]["ingesta_meta_posterior_al_cierre"] = False
        self.assertEqual(self.evaluar(e)["codigo"], "DIA_INCOMPLETO")

    def test_mas_dias_que_los_cumplidos_espera(self) -> None:
        r = self.evaluar(**{"lanzamiento.baja_dias": 2})
        self.assertEqual((r["accion_negocio"], r["codigo"]), ("MANTENER", "DIAS_INSUFICIENTES"))

    def test_clics_que_no_llegan_a_la_landing_no_es_culpa_de_la_oferta(self) -> None:
        e = entrada_dia1()
        e["dia"]["vistas_landing"] = 40  # 25 % de 160 clics
        r = self.evaluar(e)
        self.assertEqual((r["accion_negocio"], r["codigo"], r["escalar_a"]), ("NO_DECIDIR", "ETAPA_2_CONEXION_BAJA", "D5"))
        e["dia"]["vistas_landing"] = 112  # justo 70 % de 160: alcanza
        self.assertEqual(self.evaluar(e)["accion_negocio"], "APAGAR")

    def test_pocos_clics_no_evaluan_la_conexion_pero_si_se_baja(self) -> None:
        e = entrada_dia1()
        e["dia"].update(clics_enlace=60, vistas_landing=10)
        r = self.evaluar(e)
        self.assertEqual(r["accion_negocio"], "APAGAR")
        self.assertIsNone([c for c in r["condiciones"] if c["id"] == "C1"][0]["cumple"])

    def test_sin_eventos_de_landing_no_se_baja(self) -> None:
        e = entrada_dia1()
        e["dia"]["vistas_landing"] = None
        self.assertEqual(self.evaluar(e)["codigo"], "SIN_EVENTOS_LANDING")

    def test_entrada_invalida(self) -> None:
        with self.assertRaises(P.ErrorProponer):
            P.evaluar_lanzamiento({"tipo": "otra_cosa"}, self.u)
        with self.assertRaises(P.ErrorProponer):
            P.evaluar_lanzamiento(entrada_dia1(), {**self.u, "testeo.tasa_conexion_min": "abc"})

    def test_no_modifica_la_entrada(self) -> None:
        e = entrada_dia1()
        copia = copy.deepcopy(e)
        self.evaluar(e)
        self.assertEqual(e, copia)


def serie_anuncio(bueno: dict, malo: dict, n_malos: int, dias: int = 12, *, fin: str = "2026-11-20") -> tuple[dict, str]:
    """``dias`` días que terminan en ``fin``; los últimos ``n_malos`` usan ``malo``."""
    from datetime import date, timedelta
    f_fin = date.fromisoformat(fin)
    por_dia = {}
    for i in range(dias):
        f = (f_fin - timedelta(days=dias - 1 - i)).isoformat()
        por_dia[f] = dict(malo if i >= dias - n_malos else bueno)
    return por_dia, fin


BUENO = {"gasto_minor": 1000, "impresiones": 1000, "clics_enlace": 20, "compras_meta": 0, "ventas_stripe": 2, "ic": 0}
MALO = {"gasto_minor": 1000, "impresiones": 1000, "clics_enlace": 10, "compras_meta": 0, "ventas_stripe": 1, "ic": 0}


def entrada_fatiga(por_dia: dict, fin: str, *, abiertos: int | None = 0, frecuencia: str | None = None) -> dict:
    e = entrada_dia1(fecha_cuenta=fin)
    e["contexto"]["pedidos_creativos_abiertos"] = abiertos
    ad = {"ad_id": "120000000000100", "concepto_id": "c01-mapas", "por_dia": por_dia}
    if frecuencia is not None:
        ad["frecuencia_7d"] = frecuencia
    e["anuncios"] = [ad]
    return e


class PruebaFatiga(unittest.TestCase):
    def setUp(self) -> None:
        self.u = umbrales_prueba()

    def evaluar(self, e: dict, **u_cambios) -> dict:
        r = P.evaluar_fatiga(e, {**self.u, **u_cambios})
        self.assertEqual(no_hay_floats(r), [])
        return r

    def test_fatiga_confirmada_en_dos_lecturas_pide_relevo(self) -> None:
        por_dia, fin = serie_anuncio(BUENO, MALO, n_malos=4)  # los últimos 4 días caen: las lecturas k=0 y k=1 alertan
        r = self.evaluar(entrada_fatiga(por_dia, fin))
        ad = r["anuncios"][0]
        self.assertEqual(ad["estado"], "FATIGA_CONFIRMADA")
        self.assertEqual(len(ad["lecturas"]), 2)
        p = r["propuestas"][0]
        self.assertEqual((p["accion_negocio"], p["accion_contrato"], p["codigo"]), ("RELEVAR", "SEGUIR", "FATIGA_RELEVO_PEDIDO"))
        self.assertEqual((p["variable_a_variar"], p["cantidad_max_pedido"]), ("hook", 5))
        senales = ad["lecturas"][0]["senales"]
        self.assertTrue(senales["ctr"]["fatiga"] and senales["cpa"]["fatiga"])

    def test_sin_cupo_de_pedidos_solo_avisa(self) -> None:
        por_dia, fin = serie_anuncio(BUENO, MALO, n_malos=4)
        for abiertos in (1, None):
            r = self.evaluar(entrada_fatiga(por_dia, fin, abiertos=abiertos))
            self.assertEqual((r["propuestas"][0]["accion_negocio"], r["propuestas"][0]["codigo"]), ("AVISAR_FATIGA", "FATIGA_SIN_CUPO_DE_PEDIDO"))

    def test_una_sola_lectura_avisa_y_no_pide(self) -> None:
        por_dia, fin = serie_anuncio(BUENO, MALO, n_malos=2)  # la lectura k=0 alerta (CTR -33 %, CPA x1,5) y la k=1 todavía no
        r = self.evaluar(entrada_fatiga(por_dia, fin))
        self.assertEqual(r["anuncios"][0]["estado"], "FATIGA_UNA_LECTURA")
        self.assertEqual(r["propuestas"][0]["accion_negocio"], "AVISAR_FATIGA")

    def test_estable_no_hay_fatiga(self) -> None:
        por_dia, fin = serie_anuncio(BUENO, BUENO, n_malos=0)
        r = self.evaluar(entrada_fatiga(por_dia, fin))
        self.assertEqual((r["anuncios"][0]["estado"], r["propuestas"]), ("SIN_FATIGA", []))

    def test_sin_historial_de_ventas_no_aplica(self) -> None:
        sin_ventas = {**BUENO, "ventas_stripe": 0}
        por_dia, fin = serie_anuncio(sin_ventas, {**MALO, "ventas_stripe": 0}, n_malos=4)
        r = self.evaluar(entrada_fatiga(por_dia, fin))
        self.assertEqual(r["anuncios"][0]["estado"], "NO_APLICA")

    def test_serie_corta_no_alcanza(self) -> None:
        por_dia, fin = serie_anuncio(BUENO, MALO, n_malos=3, dias=9)
        self.assertEqual(self.evaluar(entrada_fatiga(por_dia, fin))["anuncios"][0]["estado"], "DATOS_INSUFICIENTES")

    def test_poca_muestra_de_impresiones_no_evalua_el_ctr(self) -> None:
        chico = {**BUENO, "impresiones": 100, "clics_enlace": 2}
        por_dia, fin = serie_anuncio(chico, {**chico, "clics_enlace": 1}, n_malos=4)
        r = self.evaluar(entrada_fatiga(por_dia, fin))
        self.assertFalse(r["anuncios"][0]["lecturas"][0]["senales"]["ctr"]["evaluable"])
        self.assertEqual(r["anuncios"][0]["estado"], "DATOS_INSUFICIENTES")

    def test_el_borde_de_la_caida_del_ctr_cuenta(self) -> None:
        # 30 % exacto: de 2,0 % (20/1000) a 1,4 % (14/1000)
        malo = {**MALO, "clics_enlace": 14}
        por_dia, fin = serie_anuncio(BUENO, malo, n_malos=4)
        self.assertTrue(self.evaluar(entrada_fatiga(por_dia, fin))["anuncios"][0]["lecturas"][1]["senales"]["ctr"]["fatiga"])
        malo = {**MALO, "clics_enlace": 15}  # 25 %: no alcanza
        por_dia, fin = serie_anuncio(BUENO, malo, n_malos=4)
        self.assertFalse(self.evaluar(entrada_fatiga(por_dia, fin))["anuncios"][0]["lecturas"][1]["senales"]["ctr"]["fatiga"])

    def test_costo_por_ic_reemplaza_al_cpa_cuando_hay_pocas_ventas(self) -> None:
        bueno = {**BUENO, "ventas_stripe": 0, "ic": 4}
        malo = {**MALO, "ventas_stripe": 0, "ic": 2}
        por_dia, fin = serie_anuncio(bueno, malo, n_malos=4)
        e = entrada_fatiga(por_dia, fin)
        # sin ventas previas el anuncio no aplica; con ventas previas pero sin ventas recientes mide el costo por venta
        self.assertEqual(self.evaluar(e)["anuncios"][0]["estado"], "NO_APLICA")
        bueno = {**BUENO, "ventas_stripe": 1, "ic": 4}
        malo = {**MALO, "ventas_stripe": 0, "ic": 2}
        por_dia, fin = serie_anuncio(bueno, malo, n_malos=4)
        senal = self.evaluar(entrada_fatiga(por_dia, fin))["anuncios"][0]["lecturas"][0]["senales"]["cpa"]
        self.assertTrue(senal["evaluable"])  # 7 ventas previas, gasto reciente 3000 >= 3 x CPA previo (1000)
        self.assertTrue(senal["fatiga"])

    def test_frecuencia_opcional_cuenta_como_tercera_senal(self) -> None:
        por_dia, fin = serie_anuncio(BUENO, MALO, n_malos=3)
        r = self.evaluar(entrada_fatiga(por_dia, fin, frecuencia="3.1"))
        self.assertTrue(r["anuncios"][0]["lecturas"][0]["senales"]["frecuencia"]["fatiga"])

    def test_umbral_faltante_no_propone_relevo(self) -> None:
        por_dia, fin = serie_anuncio(BUENO, MALO, n_malos=4)
        r = self.evaluar(entrada_fatiga(por_dia, fin), **{"testeo.fatiga_compras_min": None})
        self.assertEqual((r["accion_negocio"], r["propuestas"], r["umbrales_faltantes"]), ("NO_DECIDIR", [], ["testeo.fatiga_compras_min"]))

    def test_la_serie_debe_terminar_en_la_fecha_evaluada(self) -> None:
        por_dia, fin = serie_anuncio(BUENO, MALO, n_malos=4)
        e = entrada_fatiga(por_dia, fin)
        e["fecha_cuenta"] = "2026-11-21"
        self.assertEqual(self.evaluar(e)["anuncios"][0]["estado"], "DATOS_INSUFICIENTES")

    def test_la_salida_es_json_serializable(self) -> None:
        por_dia, fin = serie_anuncio(BUENO, MALO, n_malos=4)
        json.dumps(self.evaluar(entrada_fatiga(por_dia, fin)))


class PruebaUmbralesYaml(unittest.TestCase):
    def test_lo_que_no_existe_queda_null_y_en_faltantes(self) -> None:
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            par, lim = Path(d, "p.yaml"), Path(d, "l.yaml")
            par.write_text("grupos:\n  testeo:\n    clics_min_diag:\n      valor: 100\n    tasa_conexion_min:\n      valor: '0.70'\n", encoding="utf-8")
            lim.write_text("gasto_diario_global: null\nperdida_neta_acumulada_max: 300000\n", encoding="utf-8")
            doc = P.umbrales_desde_yaml(par, lim)
        u = doc["umbrales"]
        self.assertEqual((u["testeo.clics_min_diag"], u["testeo.tasa_conexion_min"]), (100, "0.70"))
        self.assertIsNone(u["lanzamiento.baja_dias"])  # el grupo `lanzamiento` no existe: fail-closed
        self.assertIn("lanzamiento.baja_dias", doc["umbrales_faltantes"])
        self.assertIn("limites.gasto_diario_global", doc["umbrales_faltantes"])
        self.assertEqual(u["limites.perdida_neta_acumulada_max"], 300000)

    def test_con_los_parametros_reales_de_hoy_la_regla_j3_no_decide(self) -> None:
        from tests.skills_d8._comun import RAIZ
        doc = P.umbrales_desde_yaml(RAIZ / "empresa" / "parametros.yaml", RAIZ / "empresa" / "limites.yaml")
        if not [k for k in doc["umbrales_faltantes"] if k.startswith("lanzamiento.")]:
            self.skipTest("S-A ya cargó el grupo `lanzamiento` en parametros.yaml (PEDIDOS.md P-02): esta prueba documenta el estado de antes")
        r = P.evaluar_lanzamiento(entrada_dia1(), doc["umbrales"])
        self.assertEqual((r["accion_negocio"], r["codigo"]), ("NO_DECIDIR", "UMBRAL_FALTANTE"))


if __name__ == "__main__":
    unittest.main()
