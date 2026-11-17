"""Pruebas de ``engine.limites``: fail-closed, sello, ancla, firma Ed25519, topes, agregados y ritmo."""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import unittest
from datetime import datetime, timezone
from unittest import mock

import yaml

from engine import comun, limites
from engine.errores import ErrorLimite, ErrorUso, ErrorValidacion
from engine.limites import CampanaActiva, Limites
from scripts.validar_esquemas import CLAVES_CRITICAS, sello_de_limites
from tests.engine.apoyo import EMPRESA_PRUEBA, FIXTURES, PruebaBase, crear_empresa, par_de_claves

AHORA = datetime(2026, 11, 9, 12, 0, 0, tzinfo=timezone.utc)


def _datos() -> dict:
    with open(EMPRESA_PRUEBA / "limites.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _sellar(datos: dict) -> dict:
    datos["sello"] = {"hash": sello_de_limites(datos), "firmado_por": "prueba", "firmado_en": "2026-11-06T12:00:00Z"}
    return datos


def _lim(**cambios) -> Limites:
    """Límites en memoria con ``cambios`` (sin tocar disco); sellados para que ``exigir_operacion`` sea realista."""
    datos = _datos()
    datos.update(cambios)
    return Limites(datos=_sellar(datos), entorno="prueba")


def _camp(oferta="OF-202611-01", camp="c1", max_diario=1000, restante=0, perdida=0, moneda="EUR") -> CampanaActiva:
    return CampanaActiva(oferta_id=oferta, campaign_id=camp, max_teorico_diario_minor=max_diario, spend_cap_restante_minor=restante,
                         moneda=moneda, perdida_acumulada_minor=perdida)


class PruebaCargarLimites(PruebaBase):
    """La plantilla del dueño (todo ``null``) carga pero NO alcanza para nada."""

    def test_carga_la_fixture_completa(self) -> None:
        lim = limites.cargar_limites(EMPRESA_PRUEBA / "limites.yaml", env={"FABRICA_ENTORNO": "prueba"})
        self.assertEqual(lim.moneda, "EUR")
        self.assertEqual(lim.valor("gasto_diario_por_oferta"), 5000)
        self.assertEqual(lim.hash_calculado, lim["sello"]["hash"])
        self.assertEqual(limites.hash_limites(lim), lim.hash_calculado)
        self.assertEqual(lim.entorno, "prueba")
        self.assertIsNone(lim.ancla_hash)

    def test_lee_el_ancla_de_la_variable_inyectada(self) -> None:
        lim = limites.cargar_limites(EMPRESA_PRUEBA / "limites.yaml", env={"LIMITES_HASH_ANCLA": " sha256:" + "a" * 64 + " "})
        self.assertEqual(lim.ancla_hash, "sha256:" + "a" * 64)

    def test_plantilla_con_null_carga_pero_ninguna_operacion_alcanza(self) -> None:
        lim = limites.cargar_limites(FIXTURES / "limites_plantilla.yaml", env={})
        for operacion in CLAVES_CRITICAS:
            with self.subTest(operacion=operacion), self.assertRaises(ErrorLimite) as cm:
                limites.exigir_operacion(lim, operacion)
            self.assertEqual(cm.exception.codigo_salida, 5)
            self.assertTrue(cm.exception.detalle["faltantes"], "debe listar lo que falta")
        with self.assertRaises(ErrorLimite):
            lim.valor("capital_en_riesgo_total")

    def test_archivo_inexistente_o_ilegible_es_error_de_limite(self) -> None:
        with self.assertRaises(ErrorLimite):
            limites.cargar_limites(self.tmp / "no-existe.yaml", env={})
        for contenido in ("a: [1, 2", "moneda_limites: EUR\nmoneda_limites: USD\n", "- 1\n"):
            ruta = self.tmp / "l.yaml"
            ruta.write_text(contenido, encoding="utf-8")
            with self.subTest(contenido=contenido), self.assertRaises(ErrorLimite):
                limites.cargar_limites(ruta, env={})

    def test_esquema_invalido_es_error_de_validacion(self) -> None:
        datos = _datos()
        datos["macro_nichos_permitidos"] = ["salud", "relaciones", "dinero", "cripto"]
        ruta = self.tmp / "l.yaml"
        ruta.write_text(yaml.safe_dump(datos), encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            limites.cargar_limites(ruta, env={})

    def test_ruta_por_defecto_sale_de_fabrica_raiz(self) -> None:
        emp = crear_empresa(self.tmp)
        lim = limites.cargar_limites(env=emp.env)
        self.assertEqual(lim.ruta.resolve(), emp.ruta("limites.yaml").resolve())
        self.assertEqual(lim.entorno, "produccion")

    def test_exigir_operacion_exige_un_objeto_limites(self) -> None:
        with self.assertRaises(ErrorUso):
            limites.exigir_operacion(_datos(), "gastar")  # type: ignore[arg-type]


class PruebaExigirOperacion(PruebaBase):
    """Claves críticas, sello por hash, ancla y coherencia (todo vía ``evaluar_limites``)."""

    def test_la_fixture_alcanza_para_todas_las_operaciones(self) -> None:
        for operacion in CLAVES_CRITICAS:
            with self.subTest(operacion=operacion):
                limites.exigir_operacion(_lim(), operacion)

    def test_cada_clave_critica_en_null_o_vacia_bloquea_con_cinco(self) -> None:
        for operacion in ("gastar", "activar", "reembolsar_auto", "aumentar_presupuesto"):
            for clave in CLAVES_CRITICAS[operacion]:
                with self.subTest(operacion=operacion, clave=clave):
                    datos = _datos()
                    datos[clave] = [] if isinstance(datos[clave], list) else None
                    lim = Limites(datos=_sellar(datos), entorno="prueba")
                    with self.assertRaises(ErrorLimite) as cm:
                        limites.exigir_operacion(lim, operacion)
                    self.assertEqual(cm.exception.codigo_salida, 5)
                    self.assertIn(clave, cm.exception.detalle["faltantes"])

    def test_sello_alterado_bloquea(self) -> None:
        datos = _datos()
        datos["gasto_diario_global"] = 999999  # cambia el contenido sin volver a sellar
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_operacion(Limites(datos=datos, entorno="prueba"), "gastar")
        self.assertTrue(any("sello" in f for f in cm.exception.detalle["faltantes"]))

    def test_sin_sello_bloquea(self) -> None:
        datos = _datos()
        datos["sello"] = None
        with self.assertRaises(ErrorLimite):
            limites.exigir_operacion(Limites(datos=datos, entorno="prueba"), "gastar")

    def test_ancla_distinta_bloquea_y_ancla_igual_pasa(self) -> None:
        datos = _sellar(_datos())
        bueno = Limites(datos=datos, entorno="prueba", ancla_hash=datos["sello"]["hash"])
        limites.exigir_operacion(bueno, "gastar", exigir_ancla=True)
        malo = Limites(datos=datos, entorno="prueba", ancla_hash="sha256:" + "0" * 64)
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_operacion(malo, "gastar")
        self.assertTrue(any("ANCLA" in f for f in cm.exception.detalle["faltantes"]))

    def test_ancla_ausente_solo_bloquea_si_se_exige(self) -> None:
        lim = _lim()
        limites.exigir_operacion(lim, "gastar")
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_operacion(lim, "gastar", exigir_ancla=True)
        self.assertEqual(cm.exception.detalle["faltantes"], ["LIMITES_HASH_ANCLA"])

    def test_limites_incoherentes_bloquean(self) -> None:
        casos = {
            "por oferta mayor que el global": {"gasto_diario_por_oferta": 10001},
            "pérdida mayor que el gasto total": {"perdida_max_test_por_oferta": 33001},
            "límite de cuenta mayor que el capital": {"limite_gasto_cuenta_meta": 100001},
            "importe negativo": {"capital_en_riesgo_total": -1},
            "importe como texto": {"gasto_diario_global": "10000"},
        }
        for nombre, cambios in casos.items():
            with self.subTest(nombre=nombre), self.assertRaises(ErrorLimite):
                limites.exigir_operacion(_lim(**cambios), "gastar")

    def test_produccion_exige_firma_en_el_sello(self) -> None:
        datos = _sellar(_datos())
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_operacion(Limites(datos=datos, entorno="produccion"), "gastar")
        self.assertTrue(any("firma" in f for f in cm.exception.detalle["faltantes"]))
        # Firma Ed25519 SSHSIG REAL (clave de prueba efímera, sin red): el validador de esquemas exige
        # desde CT 1.1.0 un formato SSHSIG estructural, así que una cadena de relleno ya no sirve.
        datos["sello"]["firma"] = comun.firmar_ed25519(datos["sello"]["hash"].encode("utf-8"), par_de_claves().privada)
        limites.exigir_operacion(Limites(datos=datos, entorno="produccion"), "gastar")
        # Una firma de relleno (formato inválido) se sigue rechazando: falla cerrado.
        datos["sello"]["firma"] = "ed25519:" + "A" * 30
        with self.assertRaises(ErrorLimite) as cm2:
            limites.exigir_operacion(Limites(datos=datos, entorno="produccion"), "gastar")
        self.assertTrue(any("firma" in f for f in cm2.exception.detalle["faltantes"]))

    def test_operacion_desconocida_bloquea(self) -> None:
        with self.assertRaises(ErrorLimite):
            limites.exigir_operacion(_lim(), "inventada")


class PruebaFirmaDelSello(PruebaBase):
    """La firma Ed25519 del sello se verifica con la clave PÚBLICA."""

    def _con_firma(self, firmante=None, hash_firmado=None) -> tuple[Limites, str]:
        par = par_de_claves()
        datos = _sellar(_datos())
        a_firmar = hash_firmado or datos["sello"]["hash"]
        datos["sello"]["firma"] = comun.firmar_ed25519(a_firmar.encode("utf-8"), (firmante or par).privada)
        return Limites(datos=datos, entorno="produccion"), par.publica

    def test_firma_valida(self) -> None:
        lim, publica = self._con_firma()
        limites.verificar_firma_sello(lim, publica)

    def test_firma_de_otra_clave_o_sobre_otro_hash_falla(self) -> None:
        lim, publica = self._con_firma(firmante=par_de_claves("intruso"))
        with self.assertRaises(ErrorLimite):
            limites.verificar_firma_sello(lim, publica)
        lim, publica = self._con_firma(hash_firmado="sha256:" + "1" * 64)
        with self.assertRaises(ErrorLimite):
            limites.verificar_firma_sello(lim, publica)

    def test_sin_firma_o_firma_hmac_falla(self) -> None:
        par = par_de_claves()
        datos = _sellar(_datos())
        with self.assertRaises(ErrorLimite):
            limites.verificar_firma_sello(Limites(datos=datos), par.publica)
        datos["sello"]["firma"] = "hmac-sha256:" + "ab" * 32
        with self.assertRaises(ErrorLimite):
            limites.verificar_firma_sello(Limites(datos=datos), par.publica)

    def test_sin_clave_publica_o_ilegible_falla_cerrado(self) -> None:
        lim, _ = self._con_firma()
        for clave in (None, "", "   ", "ssh-ed25519 basura"):
            with self.subTest(clave=clave), self.assertRaises(ErrorLimite):
                limites.verificar_firma_sello(lim, clave)

    def test_sin_sello_falla(self) -> None:
        datos = _datos()
        datos["sello"] = None
        with self.assertRaises(ErrorLimite):
            limites.verificar_firma_sello(Limites(datos=datos), par_de_claves().publica)


class PruebaTope(PruebaBase):
    """Moneda primero, importe después; tope exacto pasa, tope + 1 no."""

    def test_tope_exacto_pasa_y_tope_mas_uno_falla(self) -> None:
        lim = _lim()
        limites.exigir_tope(lim, "gasto_diario_por_oferta", 5000, "EUR")
        limites.exigir_tope(lim, "gasto_diario_por_oferta", 0, "EUR")
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_tope(lim, "gasto_diario_por_oferta", 5001, "EUR")
        self.assertEqual(cm.exception.codigo_salida, 5)
        self.assertEqual(cm.exception.detalle["tope"], 5000)

    def test_moneda_distinta_es_validacion_aunque_el_importe_quepa(self) -> None:
        lim = _lim()
        with self.assertRaises(ErrorValidacion) as cm:
            limites.exigir_tope(lim, "gasto_diario_por_oferta", 1, "USD")
        self.assertEqual(cm.exception.codigo_salida, 3)

    def test_la_moneda_se_comprueba_antes_que_el_importe(self) -> None:
        with self.assertRaises(ErrorValidacion):
            limites.exigir_tope(_lim(), "gasto_diario_por_oferta", 10 ** 9, "USD")

    def test_importes_invalidos(self) -> None:
        for malo in (-1, True, 1.0, "5", None):
            with self.subTest(malo=malo), self.assertRaises(ErrorValidacion):
                limites.exigir_tope(_lim(), "gasto_diario_por_oferta", malo, "EUR")  # type: ignore[arg-type]

    def test_tope_en_null_es_error_de_limite(self) -> None:
        with self.assertRaises(ErrorLimite):
            limites.exigir_tope(_lim(reembolso_auto_max=None), "reembolso_auto_max", 1, "EUR")


class PruebaMaxTeorico(PruebaBase):
    """Peor caso diario = presupuesto × factor de Meta, redondeado hacia arriba, con ``Decimal``."""

    def test_valores(self) -> None:
        lim = _lim()
        self.assertEqual(limites.max_teorico_diario(lim, 100), 175)
        self.assertEqual(limites.max_teorico_diario(lim, 3), 6)  # 5,25 sube a 6
        self.assertEqual(limites.max_teorico_diario(lim, 0), 0)
        self.assertEqual(limites.max_teorico_diario(lim, 2857), 5000)  # 4999,75 sube a 5000
        self.assertEqual(limites.max_teorico_diario(lim, 2858), 5002)  # 5001,5 sube a 5002

    def test_factor_ausente_o_ilegible(self) -> None:
        with self.assertRaises(ErrorLimite):
            limites.max_teorico_diario(_lim(factor_techo_teorico_diario=None), 100)
        with self.assertRaises(ErrorLimite):
            limites.max_teorico_diario(_lim(factor_techo_teorico_diario="uno coma cinco"), 100)
        with self.assertRaises(ErrorValidacion):
            limites.max_teorico_diario(_lim(), -5)


class PruebaAgregados(PruebaBase):
    """Topes sobre TODAS las campañas activas: suma = tope pasa, tope + 1 falla."""

    def _lim_amplio(self, **cambios) -> Limites:
        base = dict(ofertas_en_test_simultaneas_max=3, gasto_diario_por_oferta=5000, gasto_diario_global=10000)
        base.update(cambios)
        return _lim(**base)

    def test_suma_diaria_igual_al_tope_global_pasa_y_mas_uno_falla(self) -> None:
        lim = self._lim_amplio()
        tres = [_camp("OF-202611-01", "c1", 3333), _camp("OF-202611-02", "c2", 3333), _camp("OF-202611-03", "c3", 3334)]
        limites.exigir_agregados(lim, tres, gasto_vitalicio_minor=0)
        tres[2] = _camp("OF-202611-03", "c3", 3335)
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_agregados(lim, tres, gasto_vitalicio_minor=0)
        self.assertEqual(cm.exception.detalle["clave"], "gasto_diario_global")

    def test_nueva_se_suma_y_reemplaza_a_la_misma_campana(self) -> None:
        lim = self._lim_amplio()
        activas = [_camp("OF-202611-01", "c1", 5000), _camp("OF-202611-02", "c2", 4000)]
        limites.exigir_agregados(lim, activas, nueva=_camp("OF-202611-03", "c3", 1000), gasto_vitalicio_minor=0)
        with self.assertRaises(ErrorLimite):
            limites.exigir_agregados(lim, activas, nueva=_camp("OF-202611-03", "c3", 1001), gasto_vitalicio_minor=0)
        # Subir el presupuesto de c2 la reemplaza (no la duplica): 5000 + 5000 = tope.
        limites.exigir_agregados(lim, activas, nueva=_camp("OF-202611-02", "c2", 5000), gasto_vitalicio_minor=0)

    def test_exigir_nueva_bloquea_si_falta_y_la_suma_si_esta(self) -> None:
        lim = self._lim_amplio()
        activas = [_camp("OF-202611-01", "c1", 5000), _camp("OF-202611-02", "c2", 5000)]
        limites.exigir_agregados(lim, activas, gasto_vitalicio_minor=0)  # auditoría del estado actual: sin efecto, «nueva» opcional
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_agregados(lim, activas, gasto_vitalicio_minor=0, exigir_nueva=True)
        self.assertEqual(cm.exception.detalle["faltantes"], ["nueva"])
        with self.assertRaises(ErrorLimite) as cm:  # el efecto (5000 más) rompe el tope global: 15000 > 10000
            limites.exigir_agregados(lim, activas, nueva=_camp("OF-202611-03", "c3", 5000), gasto_vitalicio_minor=0, exigir_nueva=True)
        self.assertEqual(cm.exception.detalle["clave"], "gasto_diario_global")
        limites.exigir_agregados(lim, activas[:1], nueva=_camp("OF-202611-02", "c2", 5000), gasto_vitalicio_minor=0, exigir_nueva=True)

    def test_campaign_id_duplicado_en_activas_es_dato_incoherente(self) -> None:
        # Dos entradas de «activas» con el MISMO campaign_id (no puede venir así de Meta): antes la
        # segunda se pisaba en silencio con la primera y una oferta desaparecía del conteo (observación 2).
        lim = self._lim_amplio()
        duplicadas = [_camp("OF-202611-01", "c1", 1000), _camp("OF-202611-02", "c1", 2000)]
        with self.assertRaises(ErrorValidacion) as cm:
            limites.exigir_agregados(lim, duplicadas, gasto_vitalicio_minor=0)
        self.assertIn("campaign_id", str(cm.exception))

    def test_nueva_no_puede_robar_el_campaign_id_de_otra_oferta(self) -> None:
        # activas=[c1(OF-02), c2(OF-03)] + nueva c1(OF-01): antes la nueva reemplazaba sin más la
        # entrada de c1 y OF-02 desaparecía del conteo de simultáneas (observación 2, exploit verificado).
        lim = self._lim_amplio()
        activas = [_camp("OF-202611-02", "c1", 1000), _camp("OF-202611-03", "c2", 1000)]
        with self.assertRaises(ErrorValidacion) as cm:
            limites.exigir_agregados(lim, activas, nueva=_camp("OF-202611-01", "c1", 1000), gasto_vitalicio_minor=0, exigir_nueva=True)
        self.assertEqual(cm.exception.detalle["campaign_id"], "c1")
        self.assertEqual(cm.exception.detalle["oferta_activa"], "OF-202611-02")
        self.assertEqual(cm.exception.detalle["oferta_nueva"], "OF-202611-01")
        # La misma oferta SÍ puede reusar su propio campaign_id (es la reposición inocua de M05).
        limites.exigir_agregados(lim, activas, nueva=_camp("OF-202611-02", "c1", 1000), gasto_vitalicio_minor=0, exigir_nueva=True)

    def test_falta_perdida_declarada_en_una_campana_construida_directamente_bloquea(self) -> None:
        # Defensa en profundidad: una CampanaActiva construida directamente en Python (sin pasar por
        # .desde) con perdida_acumulada_minor=None (el default) también debe bloquear al sumarse,
        # no solo cuando viene de un mapa (observación 1).
        lim = self._lim_amplio()
        sin_perdida = CampanaActiva(oferta_id="OF-202611-01", campaign_id="c1", max_teorico_diario_minor=1000,
                                    spend_cap_restante_minor=0, moneda="EUR")
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_agregados(lim, [sin_perdida], gasto_vitalicio_minor=0)
        self.assertEqual(cm.exception.detalle["faltantes"], ["perdida_acumulada_minor"])

    def test_exigir_agregados_del_efecto_siempre_exige_nueva(self) -> None:
        # La variante de auditoría (exigir_agregados con exigir_nueva=False, el default) sigue
        # permitiendo omitir «nueva»; esta variante estricta no acepta ese olvido (observación 3).
        lim = self._lim_amplio()
        activas = [_camp("OF-202611-01", "c1", 5000), _camp("OF-202611-02", "c2", 5000)]
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_agregados_del_efecto(lim, activas, None, gasto_vitalicio_minor=0)  # type: ignore[arg-type]
        self.assertEqual(cm.exception.detalle["faltantes"], ["nueva"])
        with self.assertRaises(ErrorLimite) as cm:  # mismo comportamiento que exigir_nueva=True: el efecto rompe el tope
            limites.exigir_agregados_del_efecto(lim, activas, _camp("OF-202611-03", "c3", 5000), gasto_vitalicio_minor=0)
        self.assertEqual(cm.exception.detalle["clave"], "gasto_diario_global")
        limites.exigir_agregados_del_efecto(lim, activas[:1], _camp("OF-202611-02", "c2", 5000), gasto_vitalicio_minor=0)

    def test_exigir_nueva_se_comprueba_antes_que_el_resto(self) -> None:
        # Aunque falte también el gasto vitalicio, lo primero que se reclama es la campaña del efecto.
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_agregados(self._lim_amplio(), [], exigir_nueva=True)
        self.assertEqual(cm.exception.detalle["faltantes"], ["nueva"])

    def test_tope_por_oferta(self) -> None:
        lim = self._lim_amplio()
        limites.exigir_agregados(lim, [_camp(camp="c1", max_diario=2500), _camp(camp="c2", max_diario=2500)], gasto_vitalicio_minor=0)
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_agregados(lim, [_camp(camp="c1", max_diario=2500), _camp(camp="c2", max_diario=2501)], gasto_vitalicio_minor=0)
        self.assertEqual(cm.exception.detalle["clave"], "gasto_diario_por_oferta")

    def test_ofertas_simultaneas_en_el_maximo_pasa_y_una_mas_falla(self) -> None:
        lim = _lim()  # máximo 2
        dos = [_camp("OF-202611-01", "c1", 100), _camp("OF-202611-02", "c2", 100)]
        limites.exigir_agregados(lim, dos, gasto_vitalicio_minor=0)
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_agregados(lim, dos, nueva=_camp("OF-202611-03", "c3", 100), gasto_vitalicio_minor=0)
        self.assertEqual(cm.exception.detalle["clave"], "ofertas_en_test_simultaneas_max")
        # Una segunda campaña de una oferta ya activa no cuenta como oferta nueva.
        limites.exigir_agregados(lim, dos, nueva=_camp("OF-202611-02", "c9", 100), gasto_vitalicio_minor=0)

    def test_perdida_acumulada_mas_spend_cap_restante(self) -> None:
        lim = _lim()  # perdida_neta_acumulada_max = 60000
        limites.exigir_agregados(lim, [_camp(restante=10, perdida=59990)], gasto_vitalicio_minor=0)
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_agregados(lim, [_camp(restante=11, perdida=59990)], gasto_vitalicio_minor=0)
        self.assertEqual(cm.exception.detalle["clave"], "perdida_neta_acumulada_max")

    def test_la_perdida_de_una_oferta_no_se_cuenta_dos_veces(self) -> None:
        lim = _lim()
        dos_de_la_misma = [_camp(camp="c1", perdida=30000), _camp(camp="c2", perdida=30000)]
        limites.exigir_agregados(lim, dos_de_la_misma, gasto_vitalicio_minor=0)  # 30000, no 60000 + algo

    def test_gasto_vitalicio_mas_restante_contra_el_limite_de_cuenta(self) -> None:
        lim = _lim()  # limite_gasto_cuenta_meta = 40000
        limites.exigir_agregados(lim, [_camp(restante=10)], gasto_vitalicio_minor=39990)
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_agregados(lim, [_camp(restante=11)], gasto_vitalicio_minor=39990)
        self.assertEqual(cm.exception.detalle["clave"], "limite_gasto_cuenta_meta")

    def test_sin_gasto_vitalicio_no_se_puede_comprobar_y_bloquea(self) -> None:
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_agregados(_lim(), [_camp()])
        self.assertEqual(cm.exception.detalle["faltantes"], ["gasto_vitalicio_minor"])

    def test_sin_campanas_activas_pasa_con_gasto_vitalicio(self) -> None:
        limites.exigir_agregados(_lim(), [], gasto_vitalicio_minor=0)

    def test_moneda_distinta_es_validacion(self) -> None:
        with self.assertRaises(ErrorValidacion):
            limites.exigir_agregados(_lim(), [_camp(moneda="USD")], gasto_vitalicio_minor=0)

    def test_acepta_mapas_y_rechaza_mapas_incompletos(self) -> None:
        # perdida_acumulada_minor explícito (0): la ronda de endurecimiento lo exige en el mapa (ver
        # CampanaActiva.desde, observación 1); antes se asumía 0 si faltaba (fail-open silencioso).
        mapa = {"oferta_id": "OF-202611-01", "campaign_id": "c1", "max_teorico_diario_minor": 100, "spend_cap_restante_minor": 0,
               "moneda": "EUR", "perdida_acumulada_minor": 0}
        limites.exigir_agregados(_lim(), [mapa], gasto_vitalicio_minor=0)
        incompleto = {k: v for k, v in mapa.items() if k != "moneda"}
        with self.assertRaises(ErrorValidacion):
            limites.exigir_agregados(_lim(), [incompleto], gasto_vitalicio_minor=0)
        with self.assertRaises(ErrorValidacion):
            limites.exigir_agregados(_lim(), ["no es un mapa"], gasto_vitalicio_minor=0)  # type: ignore[list-item]
        sin_perdida = {k: v for k, v in mapa.items() if k != "perdida_acumulada_minor"}
        with self.assertRaises(ErrorValidacion):
            limites.exigir_agregados(_lim(), [sin_perdida], gasto_vitalicio_minor=0)


class PruebaRitmo(PruebaBase):
    """Hora y rate limit: cambios por hora, segundos entre ediciones y horas entre aumentos."""

    def test_cambios_por_hora(self) -> None:
        lim = _lim()  # máximo 4 por hora
        tres = ["2026-11-09T11:10:00Z", "2026-11-09T11:20:00Z", "2026-11-09T11:40:00Z"]
        limites.exigir_ritmo(lim, AHORA, ediciones_recientes=tres)
        cuatro = tres + ["2026-11-09T11:50:00Z"]
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_ritmo(lim, AHORA, ediciones_recientes=cuatro)
        self.assertEqual(cm.exception.detalle["clave"], "max_cambios_presupuesto_por_hora_por_conjunto")

    def test_un_cambio_de_hace_exactamente_una_hora_ya_no_cuenta(self) -> None:
        lim = _lim()
        casi = ["2026-11-09T11:00:00Z", "2026-11-09T11:00:01Z", "2026-11-09T11:30:00Z", "2026-11-09T11:40:00Z"]
        limites.exigir_ritmo(lim, AHORA, ediciones_recientes=casi)  # la de las 11:00:00 salió de la ventana
        with self.assertRaises(ErrorLimite):
            limites.exigir_ritmo(lim, AHORA, ediciones_recientes=["2026-11-09T11:00:01Z"] + casi[1:])

    def test_segundos_minimos_entre_ediciones(self) -> None:
        lim = _lim()  # 30 s
        limites.exigir_ritmo(lim, AHORA, ediciones_recientes=["2026-11-09T11:59:30Z"])  # justo 30 s
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_ritmo(lim, AHORA, ediciones_recientes=["2026-11-09T11:59:31Z"])  # 29 s
        self.assertEqual(cm.exception.detalle["clave"], "segundos_min_entre_ediciones")

    def test_horas_minimas_entre_aumentos(self) -> None:
        lim = _lim()  # 72 h
        limites.exigir_ritmo(lim, AHORA, ultimo_aumento="2026-11-06T12:00:00Z")  # justo 72 h
        with self.assertRaises(ErrorLimite) as cm:
            limites.exigir_ritmo(lim, AHORA, ultimo_aumento="2026-11-06T12:00:01Z")
        self.assertEqual(cm.exception.detalle["clave"], "horas_min_entre_aumentos")
        limites.exigir_ritmo(lim, AHORA)  # nunca hubo un aumento

    def test_historial_con_instante_futuro_es_dato_inconsistente(self) -> None:
        with self.assertRaises(ErrorValidacion):
            limites.exigir_ritmo(_lim(), AHORA, ediciones_recientes=["2026-11-09T12:00:01Z"])
        with self.assertRaises(ErrorValidacion):
            limites.exigir_ritmo(_lim(), AHORA, ultimo_aumento="2026-11-10T00:00:00Z")

    def test_instantes_sin_z_o_reloj_sin_zona_se_rechazan(self) -> None:
        with self.assertRaises(ErrorValidacion):
            limites.exigir_ritmo(_lim(), AHORA, ediciones_recientes=["2026-11-09T11:00:00"])
        with self.assertRaises(ErrorValidacion):
            limites.exigir_ritmo(_lim(), datetime(2026, 11, 9, 12, 0, 0))

    def test_limite_en_null_bloquea(self) -> None:
        with self.assertRaises(ErrorLimite):
            limites.exigir_ritmo(_lim(segundos_min_entre_ediciones=None), AHORA)


class PruebaCliEstado(PruebaBase):
    """``python -m engine.limites estado``: solo lectura, 0 suficientes y 5 insuficientes."""

    def _correr(self, *args: str, entorno: str = "prueba") -> tuple[int, str]:
        salida = io.StringIO()
        with mock.patch.dict(os.environ, {"FABRICA_ENTORNO": entorno}), contextlib.redirect_stdout(salida):
            codigo = limites.main(list(args))
        return codigo, salida.getvalue()

    def test_limites_suficientes(self) -> None:
        emp = crear_empresa(self.tmp, entorno="prueba")
        codigo, texto = self._correr("estado", "--operacion", "activar", "--raiz", str(emp.raiz), "--json")
        self.assertEqual(codigo, 0)
        datos = json.loads(texto)
        self.assertTrue(datos["ok"])
        self.assertEqual(datos["modo"], "dry_run")

    def test_limites_insuficientes_con_plantilla(self) -> None:
        (self.tmp / "empresa").mkdir()
        (self.tmp / "empresa" / "limites.yaml").write_bytes((FIXTURES / "limites_plantilla.yaml").read_bytes())
        codigo, texto = self._correr("estado", "--raiz", str(self.tmp), "--json")
        self.assertEqual(codigo, 5)
        self.assertIn("moneda_limites", json.loads(texto)["datos"]["faltantes"])

    def test_raiz_alternativa_no_existe_en_produccion(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            codigo, _ = self._correr("estado", "--raiz", str(self.tmp), entorno="produccion")
        self.assertEqual(codigo, 2)

    def test_argumentos_invalidos_dan_dos(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(limites.main(["estado", "--operacion", "inventada"]), 2)


if __name__ == "__main__":
    unittest.main()
