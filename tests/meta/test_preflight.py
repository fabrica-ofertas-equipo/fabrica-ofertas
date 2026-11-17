"""Pruebas de meta.preflight: el caso todo-verde y que cada P detecta su propio rojo (B0-12)."""
import unittest
from datetime import datetime, timezone

from engine.limites import Limites
from engine.parametros import Parametros
from meta import preflight


def _limites() -> Limites:
    return Limites(datos={
        "moneda_limites": "EUR", "factor_techo_teorico_diario": "1.75", "gasto_diario_por_oferta": 2000,
        "gasto_total_test_por_oferta": 20000, "ofertas_en_test_simultaneas_max": 5,
    }, entorno="prueba")


def _parametros() -> Parametros:
    return Parametros({"schema_version": "1.1.0", "version": 1, "grupos": {"campana": {"preflight_vigencia_h": {"valor": 24}}}})


def _campana(special_ad_categories: list | None = None) -> dict:
    return {
        "presupuesto": {"diario": 1000, "max_teorico_diario": 1750, "total_test": 10000, "spend_cap": 11000, "moneda": "EUR"},
        "special_ad_categories": special_ad_categories or [],
    }


_HASH = "sha256:" + "a" * 64


def _entradas_base() -> dict:
    return {
        "pausa": False,
        "cuenta": {"estado": "ACTIVE", "metodo_pago": True, "saludable": True, "limite_diario_minor": 10000,
                   "limite_gasto_cuenta_minor": 500000, "tipo_pago": "tarjeta", "pagina_vinculada": True},
        "dataset": {"activo": True, "eventos_recientes": True},
        "emq": {"valor": "7.0", "objetivo": "6.0"},
        "evento_prueba": {"navegador_event_id": "ev1", "servidor_event_id": "ev1"},
        "dominio_verificado": True,
        "landing": {"status_code": 200, "redirecciones": 0},
        "url": {"vacios": False, "macros_presentes": True},
        "paquete": {"landing_hash": _HASH, "precio_minor": 1900, "moneda": "EUR", "textos_iguales": True},
        "checkout": {"landing_hash": _HASH, "precio_minor": 1900, "moneda": "EUR"},
        "lint_claims_ok": True, "mejoras_meta_opt_out": True, "self_ai_disclosure_ok": True,
        "mercado": {"locale_ok": True, "paises_ok": True}, "nombres_ok": True,
        "active_errors": (), "objetos_ajenos": (), "vistas_previas_ok": True, "ofertas_en_test": 1,
        "hash_config_sellado": True, "categoria_especial_coincide_x1": None,
    }


def _entradas(**mutaciones: object) -> preflight.Entradas:
    datos = _entradas_base()
    for ruta, valor in mutaciones.items():
        partes = ruta.split(".")
        destino = datos
        for p in partes[:-1]:
            destino[p] = dict(destino[p])
            destino = destino[p]
        destino[partes[-1]] = valor
    return preflight.Entradas(**datos)


def _ahora() -> datetime:
    return datetime(2026, 11, 6, 12, 0, 0, tzinfo=timezone.utc)


def _generar(entradas: preflight.Entradas, campana: dict | None = None) -> dict:
    return preflight.generar(
        oferta_id="OF-202611-01", campana=campana or _campana(), limites=_limites(), parametros=_parametros(),
        entradas=entradas, hash_config="sha256:" + "b" * 64, ahora=_ahora,
    )


class PruebaCasoTodoVerde(unittest.TestCase):
    def test_los_24_checks_estan_presentes_y_semaforo_verde(self) -> None:
        resultado = _generar(_entradas())
        self.assertEqual(resultado["semaforo"], "VERDE")
        self.assertEqual(set(resultado["checks"]), set(preflight.CHECKS))
        for clave in preflight.CHECKS:
            self.assertEqual(resultado["checks"][clave]["estado"], "VERDE", clave)

    def test_valido_hasta_usa_la_vigencia_del_parametro(self) -> None:
        resultado = _generar(_entradas())
        self.assertEqual(resultado["generado_en"], "2026-11-06T12:00:00Z")
        self.assertEqual(resultado["valido_hasta"], "2026-11-07T12:00:00Z")

    def test_p25_no_aplica_sin_categoria_especial(self) -> None:
        resultado = _generar(_entradas())
        self.assertNotIn("P25", resultado["checks"])

    def test_p25_rojo_sin_dictamen_de_x1_con_categoria_especial(self) -> None:
        resultado = _generar(_entradas(), campana=_campana(["FINANCIAL_PRODUCTS_SERVICES"]))
        self.assertEqual(resultado["checks"]["P25"]["estado"], "ROJO")
        self.assertEqual(resultado["semaforo"], "ROJO")

    def test_p25_verde_con_dictamen_de_x1(self) -> None:
        resultado = _generar(_entradas(**{"categoria_especial_coincide_x1": True}), campana=_campana(["FINANCIAL_PRODUCTS_SERVICES"]))
        self.assertEqual(resultado["checks"]["P25"]["estado"], "VERDE")


class PruebaP07SegundoAdministradorDiferido(unittest.TestCase):
    """Decisión 15 (dueño, 2026-11-06): un solo administrador no bloquea; la página vinculada sigue siendo obligatoria."""

    def _estado(self, **cuenta) -> dict:
        resultado = _generar(_entradas(**{f"cuenta.{k}": v for k, v in cuenta.items()}))
        return resultado["checks"]["P07"]

    def test_un_solo_administrador_es_verde(self) -> None:
        self.assertEqual(self._estado(administradores_humanos=1)["estado"], "VERDE")

    def test_sin_dato_de_administradores_es_verde(self) -> None:
        self.assertEqual(self._estado(administradores_humanos=None)["estado"], "VERDE")

    def test_cero_administradores_tampoco_bloquea_porque_es_solo_informativo(self) -> None:
        self.assertEqual(self._estado(administradores_humanos=0)["estado"], "VERDE")

    def test_sin_pagina_vinculada_sigue_en_rojo_con_cualquier_numero_de_administradores(self) -> None:
        for admins in (None, 1, 2, 5):
            with self.subTest(administradores=admins):
                self.assertEqual(self._estado(pagina_vinculada=False, administradores_humanos=admins)["estado"], "ROJO")

    def test_sin_dato_de_pagina_es_rojo_fail_closed(self) -> None:
        self.assertEqual(self._estado(pagina_vinculada=None)["estado"], "ROJO")


class PruebaCadaPDetectaSuRojo(unittest.TestCase):
    """B0-12: ``meta.preflight`` detecta cada P rojo; un escenario por check, uno a la vez."""

    CASOS = {
        "P01": {"pausa": True},
        "P02": {"cuenta.estado": "DISABLED"},
        "P03": {"cuenta.metodo_pago": False},
        "P04": {"cuenta.saludable": False},
        "P05": {"cuenta.limite_diario_minor": 100},
        "P06": {"cuenta.limite_gasto_cuenta_minor": None},
        "P07": {"cuenta.pagina_vinculada": False},
        "P08": {"dataset.activo": False},
        "P09": {"emq.valor": "3.0"},
        "P10": {"evento_prueba.servidor_event_id": "otro"},
        "P11": {"dominio_verificado": False},
        "P12": {"landing.status_code": 500},
        "P13": {"url.macros_presentes": False},
        "P14": {"checkout.precio_minor": 1234},
        "P15": {"lint_claims_ok": False},
        "P16": {"mejoras_meta_opt_out": False},
        "P17": {"self_ai_disclosure_ok": False},
        "P18": {"mercado.paises_ok": False},
        "P19": {"nombres_ok": False},
        "P21": {"active_errors": ("1234567890:budget_too_low",)},
        "P22": {"vistas_previas_ok": False},
        "P23": {"ofertas_en_test": 10},
        "P24": {"hash_config_sellado": False},
    }

    def test_cada_caso_marca_rojo_solo_su_check(self) -> None:
        for clave, mutacion in self.CASOS.items():
            with self.subTest(clave=clave):
                resultado = _generar(_entradas(**mutacion))
                self.assertEqual(resultado["checks"][clave]["estado"], "ROJO", f"{clave}: {resultado['checks'][clave]}")
                self.assertEqual(resultado["semaforo"], "ROJO")

    def test_p20_rojo_si_max_teorico_diario_supera_el_tope(self) -> None:
        campana = _campana()
        campana["presupuesto"]["max_teorico_diario"] = 999999
        resultado = _generar(_entradas(), campana=campana)
        self.assertEqual(resultado["checks"]["P20"]["estado"], "ROJO")

    def test_p20_rojo_si_spend_cap_no_convierte_a_unidad_meta(self) -> None:
        campana = _campana()
        campana["presupuesto"]["moneda"] = "COP"
        campana["presupuesto"]["spend_cap"] = 150050  # no múltiplo de 100: no convierte exacto con offset 1
        resultado = _generar(_entradas(), campana=campana)
        self.assertEqual(resultado["checks"]["P20"]["estado"], "ROJO")


class PruebaPX1aPX4(unittest.TestCase):
    """A4 (ola 2, B5b): PX1-PX4 viven en un informe APARTE (``items_px``), nunca en el objeto sellado."""

    def _entradas_px_verdes(self, **over: object) -> preflight.EntradasPX:
        base = dict(
            paises=("US",), dsa_beneficiario=None, dsa_pagador=None, beneficiario_esperado="Mi LLC",
            tarifa_en_techo=True, tarifa_en_tarjeta=True, riesgo_nivel="verde", riesgo_matriz_pais_nivel_ok=True,
            terminos_sensibles_hallados=(),
        )
        base.update(over)
        return preflight.EntradasPX(**base)

    def test_todo_verde_o_no_aplica(self) -> None:
        informe = preflight.items_px(self._entradas_px_verdes())
        self.assertEqual(informe["semaforo"], "VERDE")
        self.assertEqual(informe["checks"]["PX1"]["estado"], "NO_APLICA")  # EE.UU. no es UE ni "*"
        for clave in ("PX2", "PX3", "PX4"):
            self.assertEqual(informe["checks"][clave]["estado"], "VERDE")

    def test_px1_dsa_aplica_en_ue_y_detecta_beneficiario_distinto(self) -> None:
        informe = preflight.items_px(self._entradas_px_verdes(
            paises=("FR",), dsa_beneficiario="Otra Empresa", dsa_pagador="Mi LLC",
        ))
        self.assertEqual(informe["checks"]["PX1"]["estado"], "ROJO")

    def test_px1_dsa_aplica_en_mundial(self) -> None:
        informe = preflight.items_px(self._entradas_px_verdes(
            paises=("*",), dsa_beneficiario="Mi LLC", dsa_pagador="Mi LLC",
        ))
        self.assertEqual(informe["checks"]["PX1"]["estado"], "VERDE")

    def test_px1_sin_dato_es_rojo_fail_closed(self) -> None:
        informe = preflight.items_px(self._entradas_px_verdes(paises=("DE",), dsa_beneficiario=None))
        self.assertEqual(informe["checks"]["PX1"]["estado"], "ROJO")
        self.assertIn("ausente", informe["checks"]["PX1"]["evidencia"])

    def test_px2_rojo_si_la_tarifa_no_esta_en_el_techo(self) -> None:
        informe = preflight.items_px(self._entradas_px_verdes(tarifa_en_techo=False))
        self.assertEqual(informe["checks"]["PX2"]["estado"], "ROJO")

    def test_px2_rojo_si_la_tarifa_no_esta_en_la_tarjeta(self) -> None:
        informe = preflight.items_px(self._entradas_px_verdes(tarifa_en_tarjeta=False))
        self.assertEqual(informe["checks"]["PX2"]["estado"], "ROJO")

    def test_px3_rojo_sin_matriz_aunque_haya_nivel(self) -> None:
        informe = preflight.items_px(self._entradas_px_verdes(riesgo_matriz_pais_nivel_ok=None))
        self.assertEqual(informe["checks"]["PX3"]["estado"], "ROJO")

    def test_px3_rojo_fuera_de_la_matriz(self) -> None:
        informe = preflight.items_px(self._entradas_px_verdes(riesgo_matriz_pais_nivel_ok=False))
        self.assertEqual(informe["checks"]["PX3"]["estado"], "ROJO")

    def test_px4_rojo_con_termino_sensible(self) -> None:
        informe = preflight.items_px(self._entradas_px_verdes(terminos_sensibles_hallados=("diabetes",)))
        self.assertEqual(informe["checks"]["PX4"]["estado"], "ROJO")

    def test_items_px_nunca_aparece_en_generar(self) -> None:
        resultado = _generar(_entradas())
        for clave in preflight.PX_CHECKS:
            self.assertNotIn(clave, resultado["checks"])


if __name__ == "__main__":
    unittest.main()
