"""Pruebas de ``engine.guard.comprobar_live``: los 7 pasos de ``--live`` en orden fijo, con reloj y entorno INYECTADOS.

Cada prueba parte de una raíz temporal en estado verde (``apoyo.crear_empresa``) y rompe UNA cosa. Ninguna
usa variables de entorno del proceso para el entorno ni el reloj, y ninguna abre un socket.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from engine import comun, guard
from engine.errores import ErrorBloqueado, ErrorFabrica, ErrorLimite, ErrorUso, ErrorValidacion
from engine.guard import ContextoLive, EstadoCuenta, comprobar_live
from engine.limites import CampanaActiva
from engine.transporte import TransporteFixture
from tests.engine.apoyo import (
    AHORA_BASE, ELIMINAR, HASH_CONFIG, OFERTA, EmpresaPrueba, PruebaBase, crear_empresa, par_de_claves,
)


def _camp(oferta="OF-202611-02", camp="c9", max_diario=1000, restante=0, perdida=0, moneda="EUR") -> CampanaActiva:
    return CampanaActiva(oferta_id=oferta, campaign_id=camp, max_teorico_diario_minor=max_diario, spend_cap_restante_minor=restante,
                         moneda=moneda, perdida_acumulada_minor=perdida)


def _nueva(max_diario=5000, oferta=OFERTA, camp="c1", **kw) -> CampanaActiva:
    """La campaña del efecto: por defecto la de ``OFERTA`` con el mismo peor caso (5000) que ``monto_minor``."""
    return _camp(oferta, camp, max_diario, **kw)


# Cuenta sin otras campañas ACTIVE y con la campaña del efecto (lo mínimo que acepta el paso 5 para activar).
# ediciones_recientes=() y ultimo_aumento=None EXPLÍCITOS (no el default SIN_DECLARAR): se reutiliza esta
# cuenta también para aumentar_presupuesto/escalar (OPERACIONES_CON_AGREGADOS), que sí miran el ritmo, y
# el paso 5 ahora exige declarar el historial a propósito en vez de asumirlo (observación 1).
CUENTA_ACTIVAR = EstadoCuenta(gasto_vitalicio_minor=0, nueva=_nueva(), ediciones_recientes=(), ultimo_aumento=None)
# Cuenta SIN la campaña del efecto: ya no basta para ninguna operación con agregados (regresión del fail-open de M05).
CUENTA_SIN_NUEVA = EstadoCuenta(gasto_vitalicio_minor=0)
# Operaciones que suben gasto y por tanto comprueban los agregados.
OPERACIONES_CON_AGREGADOS = ("activar", "reactivar", "aumentar_presupuesto", "escalar")


class BaseGuard(PruebaBase):
    """Prepara una empresa verde y un atajo ``comprobar`` con reloj, entorno y raíz inyectados."""

    def setUp(self) -> None:
        super().setUp()
        self.emp: EmpresaPrueba = crear_empresa(self.tmp)

    def comprobar(self, operacion: str = "gastar", **kw) -> ContextoLive:
        kw.setdefault("ahora", self.emp.reloj)
        kw.setdefault("env", self.emp.env)
        kw.setdefault("raiz", self.emp.raiz)
        if operacion == "gastar":
            kw.setdefault("monto_minor", 5000)
            kw.setdefault("moneda", "EUR")
        return comprobar_live(operacion, **kw)

    def comprobar_activar(self, **kw) -> ContextoLive:
        kw.setdefault("oferta_id", OFERTA)
        kw.setdefault("monto_minor", 5000)
        kw.setdefault("moneda", "EUR")
        kw.setdefault("sello", HASH_CONFIG)
        kw.setdefault("cuenta", CUENTA_ACTIVAR)
        return comprobar_live("activar", **{"ahora": self.emp.reloj, "env": self.emp.env, "raiz": self.emp.raiz, **kw})

    def fallo(self, excepcion, paso: str, *args, **kw):
        """Afirma que ``comprobar`` lanza ``excepcion`` en el ``paso`` indicado y devuelve el error."""
        with self.assertRaises(excepcion) as cm:
            self.comprobar(*args, **kw)
        self.assertEqual(cm.exception.detalle.get("paso"), paso, f"debía fallar en «{paso}»: {cm.exception}")
        self.assertEqual(cm.exception.detalle["pasos_ok"], guard.PASOS[:guard.PASOS.index(paso)])
        return cm.exception


class PruebaCaminoFeliz(BaseGuard):
    """Con todo verde pasan los 7 pasos y el contexto no lleva credenciales."""

    def test_los_siete_pasos_pasan_en_orden(self) -> None:
        ctx = self.comprobar()
        self.assertEqual(ctx.pasos, guard.PASOS)
        self.assertEqual(guard.PASOS, ("entorno", "pausa", "infra", "limites", "topes", "credenciales", "aprobacion"))
        self.assertEqual(ctx.modo, "live")
        self.assertEqual(ctx.operacion, "gastar")
        self.assertEqual((ctx.monto_minor, ctx.moneda), (5000, "EUR"))
        self.assertEqual(ctx.instante, "2026-11-09T07:00:00Z")
        self.assertEqual(ctx.hash_limites, self.emp.hash_limites)
        self.assertIsNone(ctx.aprobacion)

    def test_activar_con_orden_firmada_pasa_y_devuelve_el_nonce(self) -> None:
        self.emp.firmar_orden("activar_campana", nonce="nonce-abc")
        ctx = self.comprobar_activar()
        self.assertEqual(ctx.pasos, guard.PASOS)
        self.assertEqual(ctx.aprobacion, "nonce-abc")
        self.assertEqual(ctx.sello, HASH_CONFIG)

    def test_el_contexto_no_expone_credenciales_ni_claves(self) -> None:
        self.emp.firmar_orden("activar_campana")
        texto = repr(self.comprobar_activar())
        for secreto in ("ficticio-operador", "ficticio-app", self.emp.env["PREFLIGHT_HMAC_KEY"], self.emp.claves.publica):
            self.assertNotIn(secreto, texto)

    def test_la_clave_de_idempotencia_es_determinista_y_depende_del_efecto(self) -> None:
        a, b = self.comprobar(), self.comprobar()
        self.assertEqual(a.clave_idempotencia, b.clave_idempotencia)
        self.assertNotEqual(a.clave_idempotencia, self.comprobar(monto_minor=4999).clave_idempotencia)
        self.assertRegex(a.clave_idempotencia, r"^sha256:[0-9a-f]{64}$")

    def test_comprobar_no_escribe_nada(self) -> None:
        antes = comun.hash_directorio(self.emp.raiz)
        self.comprobar()
        with self.assertRaises(ErrorBloqueado):
            self.comprobar_activar()  # falta la orden: falla
        self.assertEqual(comun.hash_directorio(self.emp.raiz), antes)

    def test_los_alias_de_operacion_se_normalizan(self) -> None:
        self.emp.firmar_orden("activar_campana")
        self.assertEqual(self.comprobar_activar().operacion, "activar")
        ctx = comprobar_live("activar_campana", oferta_id=OFERTA, monto_minor=5000, moneda="EUR", sello=HASH_CONFIG, ahora=self.emp.reloj,
                             env=self.emp.env, raiz=self.emp.raiz, cuenta=CUENTA_ACTIVAR)
        self.assertEqual(ctx.operacion, "activar")


class PruebaPaso1Entorno(BaseGuard):
    """Paso 1: solo ``produccion`` admite ``--live``."""

    def test_entornos_que_no_son_produccion_se_bloquean_con_cuatro(self) -> None:
        for entorno in ("desarrollo", "prueba"):
            with self.subTest(entorno=entorno):
                env = {**self.emp.env, "FABRICA_ENTORNO": entorno}
                err = self.fallo(ErrorBloqueado, "entorno", env=env)
                self.assertEqual(err.codigo_salida, 4)
                self.assertEqual(err.detalle["pasos_ok"], ())

    def test_entorno_inyectado_gana_sobre_la_variable(self) -> None:
        self.fallo(ErrorBloqueado, "entorno", entorno="prueba")  # la variable dice produccion
        self.assertEqual(self.comprobar(entorno="produccion").modo, "live")
        self.assertEqual(self.comprobar(entorno=lambda: "produccion").modo, "live")

    def test_entorno_desconocido_o_sin_variable_se_bloquea(self) -> None:
        env_sin = {k: v for k, v in self.emp.env.items() if k != "FABRICA_ENTORNO"}  # por defecto: desarrollo
        self.fallo(ErrorBloqueado, "entorno", env=env_sin)
        self.fallo(ErrorBloqueado, "entorno", env={**self.emp.env, "FABRICA_ENTORNO": "prod"})
        self.fallo(ErrorBloqueado, "entorno", entorno="live")

    def test_no_depende_del_entorno_del_proceso(self) -> None:
        with mock.patch.dict(os.environ, {"FABRICA_ENTORNO": "desarrollo"}):
            self.assertEqual(self.comprobar().modo, "live")

    def test_raiz_inexistente_bloquea_en_entorno_con_cuatro_no_escapa_como_uso(self) -> None:
        # CT2-14: ``comun.raiz`` lanza ErrorUso (2) con FABRICA_RAIZ inexistente; el guard debe fallar
        # CERRADO (BLOQUEADO, 4) en el paso «entorno», no dejar escapar un 2 sin paso asignado.
        env = {**self.emp.env, "FABRICA_RAIZ": str(self.tmp / "no-existe")}
        err = self.fallo(ErrorBloqueado, "entorno", env=env, raiz=None)
        self.assertEqual(err.codigo_salida, 4)
        self.assertEqual(err.detalle["pasos_ok"], ())
        self.assertIn("raíz", err.mensaje)

    def test_raiz_valida_por_variable_sigue_pasando(self) -> None:
        # Con la raíz tomada de FABRICA_RAIZ (sin ``raiz=`` inyectada) los 7 pasos siguen pasando.
        env = {**self.emp.env, "FABRICA_RAIZ": str(self.emp.raiz)}
        self.assertEqual(self.comprobar(env=env, raiz=None).pasos, guard.PASOS)


class PruebaPaso2Pausa(BaseGuard):
    """Paso 2: ``empresa/PAUSA`` detiene todo."""

    def test_pausa_presente_bloquea_con_cuatro(self) -> None:
        self.emp.ruta("PAUSA").write_text("", encoding="utf-8")
        err = self.fallo(ErrorBloqueado, "pausa")
        self.assertEqual(err.codigo_salida, 4)
        self.assertIn("PAUSA", err.mensaje)

    def test_pausa_como_carpeta_o_enlace_roto_tambien_cuenta(self) -> None:
        self.emp.ruta("PAUSA").mkdir()
        self.fallo(ErrorBloqueado, "pausa")
        self.emp.ruta("PAUSA").rmdir()
        os.symlink(self.tmp / "no-existe", self.emp.ruta("PAUSA"))
        self.fallo(ErrorBloqueado, "pausa")

    def test_borrar_pausa_vuelve_a_dejar_pasar(self) -> None:
        self.emp.ruta("PAUSA").write_text("", encoding="utf-8")
        self.fallo(ErrorBloqueado, "pausa")
        self.emp.ruta("PAUSA").unlink()
        self.assertEqual(self.comprobar().pasos, guard.PASOS)

    def test_error_al_comprobar_la_pausa_cuenta_como_pausa(self) -> None:
        with mock.patch("os.lstat", side_effect=PermissionError("sin permiso")):
            self.assertTrue(guard.hay_pausa(self.emp.raiz))
        self.assertFalse(guard.hay_pausa(self.emp.raiz))


class PruebaPaso3Infra(BaseGuard):
    """Paso 3: ``estado.json`` firmado, ``modo=vivo``, todo VERDE, no futuro y fresco."""

    def test_estado_ausente_o_ilegible(self) -> None:
        ruta = self.emp.ruta("infra", "estado.json")
        ruta.write_text("{no es json", encoding="utf-8")
        self.fallo(ErrorBloqueado, "infra")
        ruta.write_text("[1, 2]", encoding="utf-8")
        self.fallo(ErrorBloqueado, "infra")
        ruta.unlink()
        self.fallo(ErrorBloqueado, "infra")

    def test_firma_alterada_bloquea(self) -> None:
        ruta = self.emp.ruta("infra", "estado.json")
        estado = json.loads(ruta.read_text(encoding="utf-8"))
        estado["items"][0]["mensaje"] = "alterado a mano"  # sin volver a firmar
        ruta.write_text(json.dumps(estado), encoding="utf-8")
        err = self.fallo(ErrorBloqueado, "infra")
        self.assertIn("firma", err.mensaje)

    def test_firma_de_otra_clave_o_sin_clave_bloquea(self) -> None:
        self.fallo(ErrorBloqueado, "infra", env={**self.emp.env, "PREFLIGHT_HMAC_KEY": "otra-clave"})
        self.fallo(ErrorBloqueado, "infra", env={k: v for k, v in self.emp.env.items() if k != "PREFLIGHT_HMAC_KEY"})
        self.fallo(ErrorBloqueado, "infra", env={**self.emp.env, "PREFLIGHT_HMAC_KEY": ""})

    def test_modo_prueba_simulado_o_ausente_no_habilita_live(self) -> None:
        for modo in ("prueba", "simulado"):
            with self.subTest(modo=modo):
                self.emp.reescribir_estado(modo=modo)
                err = self.fallo(ErrorBloqueado, "infra")
                self.assertIn(modo, err.mensaje)
        self.emp.reescribir_estado(modo=ELIMINAR)
        self.fallo(ErrorBloqueado, "infra")

    def test_estado_de_siete_horas_bloquea(self) -> None:
        generado = comun.iso_z(AHORA_BASE - timedelta(hours=7))
        self.emp.reescribir_estado(generado_en=generado, valido_hasta=comun.iso_z(AHORA_BASE + timedelta(hours=1)))
        self.fallo(ErrorBloqueado, "infra")

    def test_seis_horas_exactas_pasan_y_seis_horas_y_un_segundo_no(self) -> None:
        hasta = comun.iso_z(AHORA_BASE + timedelta(hours=1))
        self.emp.reescribir_estado(generado_en=comun.iso_z(AHORA_BASE - timedelta(hours=6)), valido_hasta=hasta)
        self.assertEqual(self.comprobar().pasos, guard.PASOS)
        self.emp.reescribir_estado(generado_en=comun.iso_z(AHORA_BASE - timedelta(hours=6, seconds=1)), valido_hasta=hasta)
        self.fallo(ErrorBloqueado, "infra")

    def test_un_parametro_mas_estricto_que_seis_horas_manda(self) -> None:
        self.emp.reescribir_parametros("infra.hc_preflight_vigencia_horas", 2)
        hasta = comun.iso_z(AHORA_BASE + timedelta(hours=1))
        self.emp.reescribir_estado(generado_en=comun.iso_z(AHORA_BASE - timedelta(hours=2)), valido_hasta=hasta)
        self.assertEqual(self.comprobar().pasos, guard.PASOS)
        self.emp.reescribir_estado(generado_en=comun.iso_z(AHORA_BASE - timedelta(hours=3)), valido_hasta=hasta)
        self.fallo(ErrorBloqueado, "infra")

    def test_un_parametro_mayor_que_seis_horas_no_sube_el_tope_del_backbone(self) -> None:
        self.emp.reescribir_parametros("infra.hc_preflight_vigencia_horas", 12)
        self.emp.reescribir_estado(generado_en=comun.iso_z(AHORA_BASE - timedelta(hours=7)), valido_hasta=comun.iso_z(AHORA_BASE + timedelta(hours=1)))
        self.fallo(ErrorBloqueado, "infra")

    def test_estado_en_el_futuro_bloquea(self) -> None:
        self.emp.reescribir_estado(generado_en=comun.iso_z(AHORA_BASE + timedelta(hours=1)), valido_hasta=comun.iso_z(AHORA_BASE + timedelta(hours=7)))
        err = self.fallo(ErrorBloqueado, "infra")
        self.assertIn("futuro", err.mensaje)

    def test_valido_hasta_vencido_bloquea(self) -> None:
        self.emp.reescribir_estado(valido_hasta=comun.iso_z(AHORA_BASE - timedelta(seconds=1)))
        self.fallo(ErrorBloqueado, "infra")

    def test_rojo_escondido_bajo_semaforo_verde_bloquea(self) -> None:
        estado = json.loads(self.emp.ruta("infra", "estado.json").read_text(encoding="utf-8"))
        items = estado["items"]
        items[1]["estado"] = "ROJO"
        self.emp.reescribir_estado(semaforo="VERDE", items=items)
        err = self.fallo(ErrorBloqueado, "infra")
        self.assertIn("VERDE", err.mensaje)

    def test_amarillo_y_pendiente_externo_no_son_verde(self) -> None:
        estado = json.loads(self.emp.ruta("infra", "estado.json").read_text(encoding="utf-8"))
        self.emp.reescribir_estado(semaforo="AMARILLO")
        self.fallo(ErrorBloqueado, "infra")
        items = estado["items"]
        items[0]["estado"] = "PENDIENTE_EXTERNO"
        self.emp.reescribir_estado(semaforo="VERDE", items=items)
        self.fallo(ErrorBloqueado, "infra")

    def test_items_ausentes_o_vacios_bloquean(self) -> None:
        self.emp.reescribir_estado(items=ELIMINAR)
        self.fallo(ErrorBloqueado, "infra")
        self.emp.reescribir_estado(items=[])
        self.fallo(ErrorBloqueado, "infra")

    def test_campo_extra_en_el_estado_bloquea_porque_no_cumple_el_esquema(self) -> None:
        self.emp.reescribir_estado(resumen={"verde": 3})
        self.fallo(ErrorBloqueado, "infra")

    def test_sin_parametros_no_hay_ventana_de_vigencia_y_se_bloquea(self) -> None:
        self.emp.ruta("parametros.yaml").unlink()
        self.fallo(ErrorBloqueado, "infra")


class PruebaPaso4Limites(BaseGuard):
    """Paso 4: límites completos, coherentes, sellados, anclados y con firma Ed25519 válida."""

    def test_limite_en_null_bloquea_con_cinco(self) -> None:
        self.emp.reescribir_limites(lambda lim: lim.update(gasto_diario_global=None))
        err = self.fallo(ErrorLimite, "limites")
        self.assertEqual(err.codigo_salida, 5)
        self.assertIn("gasto_diario_global", err.detalle["faltantes"])

    def test_plantilla_del_dueno_con_todo_null_bloquea(self) -> None:
        from tests.engine.apoyo import FIXTURES
        self.emp.ruta("limites.yaml").write_bytes((FIXTURES / "limites_plantilla.yaml").read_bytes())
        self.fallo(ErrorLimite, "limites")

    def test_lista_exigida_vacia_bloquea(self) -> None:
        self.emp.reescribir_limites(lambda lim: lim.update(cuentas_permitidas=[]))
        self.fallo(ErrorLimite, "limites")

    def test_archivo_ausente_o_ilegible_bloquea_con_cinco(self) -> None:
        self.emp.ruta("limites.yaml").write_text("a: [", encoding="utf-8")
        self.assertEqual(self.fallo(ErrorLimite, "limites").codigo_salida, 5)
        self.emp.ruta("limites.yaml").unlink()
        self.fallo(ErrorLimite, "limites")

    def test_esquema_invalido_tambien_es_cinco_en_el_guard(self) -> None:
        self.emp.reescribir_limites(lambda lim: lim.update(macro_nichos_permitidos=["salud", "relaciones", "dinero", "cripto"]))
        self.assertEqual(self.fallo(ErrorLimite, "limites").codigo_salida, 5)

    def test_contenido_cambiado_sin_resellar_bloquea(self) -> None:
        texto = self.emp.ruta("limites.yaml").read_text(encoding="utf-8").replace("gasto_diario_global: 10000", "gasto_diario_global: 9999")
        self.emp.ruta("limites.yaml").write_text(texto, encoding="utf-8")
        self.fallo(ErrorLimite, "limites")

    def test_archivo_reescrito_junto_con_su_sello_pero_con_otro_hash_que_el_ancla_bloquea(self) -> None:
        ancla_vieja = self.emp.env["LIMITES_HASH_ANCLA"]
        self.emp.reescribir_limites(lambda lim: lim.update(gasto_diario_global=10001), anclar=False)  # un atacante resella
        self.emp.env["LIMITES_HASH_ANCLA"] = ancla_vieja
        err = self.fallo(ErrorLimite, "limites")
        self.assertIn("ANCLA", " ".join(err.detalle["faltantes"]))

    def test_sin_ancla_bloquea_en_live(self) -> None:
        env = {k: v for k, v in self.emp.env.items() if k != "LIMITES_HASH_ANCLA"}
        err = self.fallo(ErrorLimite, "limites", env=env)
        self.assertEqual(err.detalle["faltantes"], ["LIMITES_HASH_ANCLA"])

    def test_sello_sin_firma_o_con_firma_de_otra_clave_bloquea(self) -> None:
        self.emp.reescribir_limites(lambda lim: None, firmar=False)
        self.fallo(ErrorLimite, "limites")
        # Firma válida pero de una clave que no es la pública configurada.
        intruso = par_de_claves("intruso")
        env = {**self.emp.env, "FABRICA_FIRMA_PUBLICA": intruso.publica}
        self.emp.reescribir_limites(lambda lim: None)
        self.fallo(ErrorLimite, "limites", env=env)

    def test_sin_clave_publica_bloquea(self) -> None:
        env = {k: v for k, v in self.emp.env.items() if k != "FABRICA_FIRMA_PUBLICA"}
        self.fallo(ErrorLimite, "limites", env=env)
        self.fallo(ErrorLimite, "limites", env={**self.emp.env, "FABRICA_FIRMA_PUBLICA": "no-es-una-clave"})

    def test_limites_incoherentes_bloquean(self) -> None:
        self.emp.reescribir_limites(lambda lim: lim.update(gasto_diario_por_oferta=10001))
        err = self.fallo(ErrorLimite, "limites")
        self.assertIn("incoherentes", err.mensaje)

    def test_operacion_desconocida_se_niega(self) -> None:
        err = self.fallo(ErrorLimite, "limites", "inventada")
        self.assertIn("desconocida", err.mensaje)

    def test_solo_se_exigen_las_claves_de_la_operacion(self) -> None:
        # Sin límites de correo se puede gastar, pero no enviar correo no transaccional (D-15).
        self.emp.reescribir_limites(lambda lim: lim.update(correos_max_por_dia=None))
        self.assertEqual(self.comprobar().pasos, guard.PASOS)
        self.fallo(ErrorLimite, "limites", "enviar_correo")


class PruebaPaso5Topes(BaseGuard):
    """Paso 5: tope, agregados de la cuenta, hora y rate limit. Tope exacto pasa; tope + 1 no."""

    def test_tope_exacto_pasa_cero_pasa_y_tope_mas_uno_falla(self) -> None:
        self.assertEqual(self.comprobar(monto_minor=5000).pasos, guard.PASOS)
        self.assertEqual(self.comprobar(monto_minor=0).pasos, guard.PASOS)
        err = self.fallo(ErrorLimite, "topes", monto_minor=5001)
        self.assertEqual(err.codigo_salida, 5)

    def test_moneda_distinta_es_validacion_tres_aunque_el_importe_quepa(self) -> None:
        err = self.fallo(ErrorValidacion, "topes", moneda="USD", monto_minor=1)
        self.assertEqual(err.codigo_salida, 3)

    def test_faltan_monto_o_moneda(self) -> None:
        self.fallo(ErrorValidacion, "topes", monto_minor=None)
        self.fallo(ErrorValidacion, "topes", moneda=None)

    def test_importes_invalidos(self) -> None:
        for malo in (-1, 1.5, True, "5000"):
            with self.subTest(malo=malo):
                self.fallo(ErrorValidacion, "topes", monto_minor=malo)

    def test_tope_de_reembolso_automatico_y_de_descubrimiento(self) -> None:
        for op, tope in (("reembolsar_auto", 3000), ("descubrir", 1000)):
            with self.subTest(op=op):
                self.assertEqual(self.comprobar(op, monto_minor=tope, moneda="EUR").pasos, guard.PASOS)
                self.fallo(ErrorLimite, "topes", op, monto_minor=tope + 1, moneda="EUR")

    def test_operacion_sin_importe_no_lo_exige(self) -> None:
        self.assertEqual(self.comprobar("generar_creativos").pasos, guard.PASOS)

    def comprobar_con(self, operacion: str, cuenta: EstadoCuenta | None, **kw) -> ContextoLive:
        """``comprobar`` de una operación con agregados (``oferta_id``, importe y, si exige gate, sello) sobre ``cuenta``."""
        kw.setdefault("oferta_id", OFERTA)
        kw.setdefault("monto_minor", 5000)
        kw.setdefault("moneda", "EUR")
        kw.setdefault("sello", HASH_CONFIG)
        return self.comprobar(operacion, cuenta=cuenta, **kw)

    def bloqueado_en_topes(self, operacion: str, cuenta: EstadoCuenta | None, excepcion=ErrorLimite, **kw):
        """Afirma que la operación se bloquea en el paso 5 (``topes``) y devuelve el error."""
        with self.assertRaises(excepcion) as cm:
            self.comprobar_con(operacion, cuenta, **kw)
        self.assertEqual(cm.exception.detalle["paso"], "topes", str(cm.exception))
        self.assertEqual(cm.exception.detalle["pasos_ok"], guard.PASOS[:guard.PASOS.index("topes")])
        return cm.exception

    def test_agregados_exigen_el_estado_de_la_cuenta(self) -> None:
        self.emp.firmar_orden("activar_campana")
        with self.assertRaises(ErrorLimite) as cm:
            self.comprobar_activar(cuenta=None)
        self.assertEqual(cm.exception.detalle["paso"], "topes")
        self.assertEqual(cm.exception.detalle["faltantes"], ["cuenta"])

    def test_agregados_suma_igual_al_tope_pasa_y_mas_uno_falla(self) -> None:
        self.emp.firmar_orden("activar_campana")
        base = _camp(max_diario=5000)  # otra oferta con 5000 de máximo teórico diario; con la nueva (5000) suman 10000 = tope global
        cuenta = EstadoCuenta(activas=(base,), nueva=_nueva(5000), gasto_vitalicio_minor=0)
        self.assertEqual(self.comprobar_activar(cuenta=cuenta).pasos, guard.PASOS)
        # Con 5001 ya activos la suma es tope + 1 (el tope de la oferta ajena se rompería primero, pero el global se mira antes).
        err = self.bloqueado_en_topes("activar", EstadoCuenta(activas=(_camp(max_diario=5001),), nueva=_nueva(5000), gasto_vitalicio_minor=0))
        self.assertEqual(err.detalle["clave"], "gasto_diario_global")

    def test_el_gasto_del_propio_efecto_entra_siempre_en_la_suma(self) -> None:
        # Reproducción del bloqueante: dos ofertas ya ACTIVE con 5000 cada una (suma 10000 = tope global) y el efecto suma 5000 más.
        activas = (_camp("OF-202611-02", "c2", 5000), _camp("OF-202611-03", "c3", 5000))
        err = self.bloqueado_en_topes("activar", EstadoCuenta(activas=activas, nueva=_nueva(5000), gasto_vitalicio_minor=0))
        self.assertEqual(err.codigo_salida, 5)
        self.assertEqual(err.detalle["clave"], "gasto_diario_global")
        self.assertEqual(err.detalle["suma"], 15000)

    def test_sin_la_campana_del_efecto_se_bloquea_aunque_el_resto_quepa(self) -> None:
        # Mismo estado de la cuenta que el bloqueante, pero sin «nueva»: antes pasaba los 7 pasos; ahora se bloquea con 5 en «topes».
        self.emp.firmar_orden("activar_campana")
        activas = (_camp("OF-202611-02", "c2", 5000), _camp("OF-202611-03", "c3", 5000))
        err = self.bloqueado_en_topes("activar", EstadoCuenta(activas=activas, gasto_vitalicio_minor=0))
        self.assertEqual(err.codigo_salida, 5)
        self.assertEqual(err.detalle["faltantes"], ["cuenta.nueva"])
        # Y sin ninguna otra campaña activa tampoco: la «nueva» no es opcional.
        self.bloqueado_en_topes("activar", CUENTA_SIN_NUEVA)

    def test_toda_operacion_con_agregados_exige_la_campana_del_efecto(self) -> None:
        # Derivado de la tabla: si mañana otra operación declara ``agregados``, esta prueba la cubre sin tocarla.
        con_agregados = sorted(n for n, r in guard.OPERACIONES.items() if r.agregados)
        self.assertEqual(con_agregados, sorted(OPERACIONES_CON_AGREGADOS))
        for alias, destino in guard.ALIAS_OPERACION.items():
            if destino in con_agregados:
                con_agregados.append(alias)
        self.emp.firmar_orden("activar_campana", nonce="n-activar")
        self.emp.firmar_orden("reactivar_tras_pausa", nonce="n-reactivar")
        for operacion in con_agregados:
            with self.subTest(operacion=operacion):
                err = self.bloqueado_en_topes(operacion, CUENTA_SIN_NUEVA)
                self.assertEqual(err.codigo_salida, 5)
                self.assertEqual(err.detalle["faltantes"], ["cuenta.nueva"])
                # Con la campaña del efecto (y la orden firmada de las que exigen gate) la misma llamada pasa los 7 pasos.
                self.assertEqual(self.comprobar_con(operacion, CUENTA_ACTIVAR).pasos, guard.PASOS)

    def test_tercera_oferta_sin_la_campana_del_efecto_se_bloquea(self) -> None:
        # Fixture: ofertas_en_test_simultaneas_max = 2. Dos ofertas ya en test; la tercera, sin «nueva», no puede pasar «porque no se cuenta».
        dos = (_camp("OF-202611-02", "c2", 1), _camp("OF-202611-03", "c3", 1))
        err = self.bloqueado_en_topes("activar", EstadoCuenta(activas=dos, gasto_vitalicio_minor=0), monto_minor=1)
        self.assertEqual(err.detalle["faltantes"], ["cuenta.nueva"])
        # Con «nueva» sí se cuenta y la tercera oferta rompe el máximo.
        err = self.bloqueado_en_topes("activar", EstadoCuenta(activas=dos, nueva=_nueva(1), gasto_vitalicio_minor=0), monto_minor=1)
        self.assertEqual(err.detalle["clave"], "ofertas_en_test_simultaneas_max")

    def test_la_campana_del_efecto_debe_coincidir_con_monto_minor(self) -> None:
        # «nueva» de 1 con monto_minor 5000: el efecto aprobado (5000) no es el que se suma (1). Antes pasaba.
        for operacion in OPERACIONES_CON_AGREGADOS:
            for declarado in (1, 4999, 5001, 0):
                with self.subTest(operacion=operacion, declarado=declarado):
                    cuenta = EstadoCuenta(activas=(_camp("OF-202611-02", "c2", 5000),), nueva=_nueva(declarado), gasto_vitalicio_minor=0)
                    err = self.bloqueado_en_topes(operacion, cuenta)
                    self.assertEqual(err.codigo_salida, 5)
                    self.assertEqual(err.detalle["clave"], "cuenta.nueva")
                    self.assertEqual(err.detalle["nueva"], declarado)
                    self.assertEqual(err.detalle["monto_minor"], 5000)

    def test_la_campana_del_efecto_debe_ser_de_la_oferta_de_la_operacion(self) -> None:
        cuenta = EstadoCuenta(nueva=_nueva(5000, oferta="OF-202611-07"), gasto_vitalicio_minor=0)
        err = self.bloqueado_en_topes("activar", cuenta)
        self.assertEqual((err.codigo_salida, err.detalle["clave"]), (5, "cuenta.nueva"))

    def test_sin_oferta_id_o_sin_importe_no_se_puede_atar_la_campana_del_efecto(self) -> None:
        for operacion in OPERACIONES_CON_AGREGADOS:
            for malo in (None, "", "   "):
                with self.subTest(operacion=operacion, oferta_id=malo):
                    err = self.bloqueado_en_topes(operacion, CUENTA_ACTIVAR, ErrorValidacion, oferta_id=malo)
                    self.assertEqual(err.codigo_salida, 3)
            with self.subTest(operacion=operacion, monto="ausente"):
                self.bloqueado_en_topes(operacion, CUENTA_ACTIVAR, ErrorValidacion, monto_minor=None)

    def test_la_campana_del_efecto_acepta_un_mapa_y_rechaza_uno_incompleto(self) -> None:
        self.emp.firmar_orden("activar_campana")
        # perdida_acumulada_minor explícito (0): CampanaActiva.desde ya no lo asume si falta (observación 1).
        mapa = {"oferta_id": OFERTA, "campaign_id": "c1", "max_teorico_diario_minor": 5000, "spend_cap_restante_minor": 0,
               "moneda": "EUR", "perdida_acumulada_minor": 0}
        self.assertEqual(self.comprobar_con("activar", EstadoCuenta(nueva=mapa, gasto_vitalicio_minor=0)).pasos, guard.PASOS)
        incompleto = {k: v for k, v in mapa.items() if k != "campaign_id"}
        err = self.bloqueado_en_topes("activar", EstadoCuenta(nueva=incompleto, gasto_vitalicio_minor=0), ErrorValidacion)
        self.assertEqual(err.codigo_salida, 3)
        self.bloqueado_en_topes("activar", EstadoCuenta(nueva="no es un mapa", gasto_vitalicio_minor=0), ErrorValidacion)  # type: ignore[arg-type]
        sin_perdida = {k: v for k, v in mapa.items() if k != "perdida_acumulada_minor"}
        err = self.bloqueado_en_topes("activar", EstadoCuenta(nueva=sin_perdida, gasto_vitalicio_minor=0), ErrorValidacion)
        self.assertEqual(err.codigo_salida, 3)

    def test_la_campana_del_efecto_en_otra_moneda_se_bloquea(self) -> None:
        err = self.bloqueado_en_topes("activar", EstadoCuenta(nueva=_nueva(5000, moneda="USD"), gasto_vitalicio_minor=0), ErrorValidacion)
        self.assertEqual(err.codigo_salida, 3)

    def test_subir_el_presupuesto_reemplaza_a_la_campana_no_la_duplica(self) -> None:
        # c1 de OFERTA ya está ACTIVE con 2000; sube a 5000. Con la de otra oferta (5000) suman 10000 = tope global. Duplicarla sumaría 12000.
        activas = (_camp(OFERTA, "c1", 2000), _camp("OF-202611-02", "c2", 5000))
        # ediciones_recientes/ultimo_aumento explícitos: aumentar_presupuesto/escalar miran el ritmo (observación 1).
        cuenta = EstadoCuenta(activas=activas, nueva=_nueva(5000, camp="c1"), gasto_vitalicio_minor=0, ediciones_recientes=(), ultimo_aumento=None)
        for operacion in ("aumentar_presupuesto", "escalar"):
            with self.subTest(operacion=operacion):
                self.assertEqual(self.comprobar_con(operacion, cuenta).pasos, guard.PASOS)
        # Y subir una más (tope + 1 en el global) sí se bloquea, con la clave del tope.
        err = self.bloqueado_en_topes("aumentar_presupuesto", EstadoCuenta(activas=(_camp(OFERTA, "c1", 2000), _camp("OF-202611-02", "c2", 5001)),
                                                                          nueva=_nueva(5000, camp="c1"), gasto_vitalicio_minor=0,
                                                                          ediciones_recientes=(), ultimo_aumento=None))
        self.assertEqual(err.detalle["clave"], "gasto_diario_global")

    def test_ofertas_simultaneas_y_limite_de_cuenta(self) -> None:
        self.emp.firmar_orden("activar_campana")
        tres = EstadoCuenta(activas=(_camp("OF-202611-02", "c2", 1), _camp("OF-202611-03", "c3", 1)), nueva=_nueva(1),
                            gasto_vitalicio_minor=0)
        with self.assertRaises(ErrorLimite) as cm:
            self.comprobar_activar(cuenta=tres, monto_minor=1)
        self.assertEqual(cm.exception.detalle["clave"], "ofertas_en_test_simultaneas_max")
        cerca = EstadoCuenta(activas=(_camp(restante=10),), nueva=_nueva(), gasto_vitalicio_minor=39990)
        self.assertEqual(self.comprobar_activar(cuenta=cerca).pasos, guard.PASOS)
        with self.assertRaises(ErrorLimite) as cm:
            self.comprobar_activar(cuenta=EstadoCuenta(activas=(_camp(restante=11),), nueva=_nueva(), gasto_vitalicio_minor=39990))
        self.assertEqual(cm.exception.detalle["clave"], "limite_gasto_cuenta_meta")

    def test_el_spend_cap_restante_de_la_campana_del_efecto_cuenta_en_el_limite_de_cuenta(self) -> None:
        # El spend_cap que le queda a la campaña del efecto también compromete el límite de cuenta (39990 + 10 = 40000 pasa; + 11 no).
        self.emp.firmar_orden("activar_campana")
        self.assertEqual(self.comprobar_activar(cuenta=EstadoCuenta(nueva=_nueva(restante=10), gasto_vitalicio_minor=39990)).pasos, guard.PASOS)
        with self.assertRaises(ErrorLimite) as cm:
            self.comprobar_activar(cuenta=EstadoCuenta(nueva=_nueva(restante=11), gasto_vitalicio_minor=39990))
        self.assertEqual(cm.exception.detalle["clave"], "limite_gasto_cuenta_meta")

    def test_sin_gasto_vitalicio_se_bloquea(self) -> None:
        self.emp.firmar_orden("activar_campana")
        with self.assertRaises(ErrorLimite) as cm:
            self.comprobar_activar(cuenta=EstadoCuenta(nueva=_nueva()))
        self.assertEqual(cm.exception.detalle["faltantes"], ["gasto_vitalicio_minor"])
        with self.assertRaises(ErrorLimite):
            self.comprobar_activar(cuenta=EstadoCuenta())

    def test_ritmo_de_cambios_de_presupuesto(self) -> None:
        # ediciones_recientes y ultimo_aumento SIEMPRE explícitos: el paso 5 ya no asume «sin historial»
        # si se deja el default SIN_DECLARAR (observación 1).
        cuenta = EstadoCuenta(gasto_vitalicio_minor=0, nueva=_nueva(), ediciones_recientes=(), ultimo_aumento=None)
        self.assertEqual(self.comprobar_con("aumentar_presupuesto", cuenta, sello=None).pasos, guard.PASOS)
        cuatro = EstadoCuenta(gasto_vitalicio_minor=0, nueva=_nueva(), ultimo_aumento=None, ediciones_recientes=(
            "2026-11-09T06:10:00Z", "2026-11-09T06:20:00Z", "2026-11-09T06:30:00Z", "2026-11-09T06:40:00Z"))
        with self.assertRaises(ErrorLimite) as cm:
            self.comprobar_con("aumentar_presupuesto", cuatro)
        self.assertEqual(cm.exception.detalle["paso"], "topes")
        self.assertEqual(cm.exception.detalle["clave"], "max_cambios_presupuesto_por_hora_por_conjunto")
        reciente = EstadoCuenta(gasto_vitalicio_minor=0, nueva=_nueva(), ediciones_recientes=(),
                                ultimo_aumento="2026-11-08T07:00:00Z")  # hace 24 h < 72 h
        with self.assertRaises(ErrorLimite) as cm:
            self.comprobar_con("escalar", reciente)
        self.assertEqual(cm.exception.detalle["clave"], "horas_min_entre_aumentos")
        self.assertEqual(self.comprobar_con("subir_presupuesto", cuenta).operacion, "aumentar_presupuesto")

    def test_sin_declarar_el_historial_de_ritmo_bloquea(self) -> None:
        # Antes de la ronda de endurecimiento, dejar el default (en ese momento () y None) de
        # ediciones_recientes/ultimo_aumento se leía como "sin historial" y pasaba sin más. Ahora el
        # default es un centinela (SIN_DECLARAR) y bloquea con ErrorLimite (observación 1).
        cuenta = EstadoCuenta(gasto_vitalicio_minor=0, nueva=_nueva())
        with self.assertRaises(ErrorLimite) as cm:
            self.comprobar_con("aumentar_presupuesto", cuenta, sello=None)
        self.assertEqual(cm.exception.detalle["paso"], "topes")
        self.assertEqual(set(cm.exception.detalle["faltantes"]), {"ediciones_recientes", "ultimo_aumento"})
        # Las operaciones sin «ritmo» (p. ej. activar) no lo necesitan: CUENTA_ACTIVAR declara ambos
        # explícitamente, pero una cuenta sin declarar tampoco las bloquearía por esto.
        self.emp.firmar_orden("activar_campana")
        self.assertEqual(self.comprobar_activar(cuenta=EstadoCuenta(gasto_vitalicio_minor=0, nueva=_nueva())).pasos, guard.PASOS)


class PruebaPaso6Credenciales(BaseGuard):
    """Paso 6: faltan variables de credenciales → código 2."""

    def test_falta_cada_credencial_de_meta(self) -> None:
        for variable in ("META_TOKEN_OPERADOR", "META_AD_ACCOUNT_ID", "META_APP_SECRET"):
            with self.subTest(variable=variable):
                env = {k: v for k, v in self.emp.env.items() if k != variable}
                err = self.fallo(ErrorUso, "credenciales", env=env)
                self.assertEqual(err.codigo_salida, 2)
                self.assertEqual(err.detalle["faltantes"], [variable])
                self.assertNotIn("ficticio", err.mensaje, "el mensaje nombra la variable, nunca su valor")

    def test_credencial_vacia_o_en_blanco_cuenta_como_ausente(self) -> None:
        self.fallo(ErrorUso, "credenciales", env={**self.emp.env, "META_TOKEN_OPERADOR": "   "})
        self.fallo(ErrorUso, "credenciales", env={**self.emp.env, "META_TOKEN_OPERADOR": ""})

    def test_cada_operacion_pide_las_suyas(self) -> None:
        sin_stripe = {k: v for k, v in self.emp.env.items() if k != "STRIPE_RK_REEMBOLSO"}
        self.fallo(ErrorUso, "credenciales", "reembolsar_auto", monto_minor=1, moneda="EUR", env=sin_stripe)
        sin_correo = {k: v for k, v in self.emp.env.items() if k != "CORREO_API_KEY"}
        self.fallo(ErrorUso, "credenciales", "enviar_correo", env=sin_correo)
        solo_nada = {k: v for k, v in self.emp.env.items() if k.startswith("FABRICA_") or k in ("PREFLIGHT_HMAC_KEY", "LIMITES_HASH_ANCLA")}
        self.assertEqual(self.comprobar("generar_creativos", env=solo_nada).pasos, guard.PASOS)


class PruebaPaso7Aprobacion(BaseGuard):
    """Paso 7: activar exige una orden firmada Ed25519, vigente y exacta para ese hash."""

    def test_sin_sello_bloquea(self) -> None:
        with self.assertRaises(ErrorBloqueado) as cm:
            self.comprobar_activar(sello=None)
        self.assertEqual(cm.exception.detalle["paso"], "aprobacion")
        self.assertEqual(cm.exception.detalle["pasos_ok"], guard.PASOS[:6])
        with self.assertRaises(ErrorBloqueado):
            self.comprobar_activar(sello="no-es-un-hash")

    def test_sin_orden_firmada_bloquea_con_cuatro(self) -> None:
        with self.assertRaises(ErrorBloqueado) as cm:
            self.comprobar_activar()
        self.assertEqual(cm.exception.codigo_salida, 4)

    def test_orden_para_otra_oferta_otra_accion_u_otro_hash(self) -> None:
        self.emp.firmar_orden("activar_campana", oferta_id="OF-202611-02", nonce="n1")
        self.emp.firmar_orden("reactivar_tras_pausa", nonce="n2")
        self.emp.firmar_orden("activar_campana", hash_objetivo="sha256:" + "ef" * 32, nonce="n3")
        with self.assertRaises(ErrorBloqueado) as cm:
            self.comprobar_activar()
        self.assertIn("otro hash", cm.exception.mensaje)

    def test_orden_con_firma_alterada_o_de_otra_clave(self) -> None:
        self.emp.firmar_orden("activar_campana", alterar=True, nonce="n1")
        with self.assertRaises(ErrorBloqueado) as cm:
            self.comprobar_activar(sello="sha256:" + "cd" * 32)
        self.assertIn("firma", cm.exception.mensaje)
        intruso = par_de_claves("intruso")
        self.assertNotEqual(intruso.publica, self.emp.claves.publica)
        self.emp.firmar_orden("activar_campana", nonce="n2")
        env = {**self.emp.env, "FABRICA_FIRMA_PUBLICA": intruso.publica}
        # Con otra pública, el paso 4 ya falla (el sello de límites no verifica): la orden ni se mira.
        with self.assertRaises(ErrorLimite):
            self.comprobar_activar(env=env)

    def test_orden_vencida_futura_o_en_el_limite_de_vigencia(self) -> None:
        # campana.preflight_vigencia_h = 24 h en la fixture; ahora = 07:00Z del 2026-11-09.
        self.emp.firmar_orden("activar_campana", ts="2026-11-08T07:00:00Z", nonce="justa")  # 24 h exactas: vigente
        self.assertEqual(self.comprobar_activar().aprobacion, "justa")
        (self.emp.ruta("ordenes") / "justa.json").unlink()
        self.emp.firmar_orden("activar_campana", ts="2026-11-08T06:59:59Z", nonce="vencida")
        with self.assertRaises(ErrorBloqueado) as cm:
            self.comprobar_activar()
        self.assertIn("vencida", cm.exception.mensaje)
        (self.emp.ruta("ordenes") / "vencida.json").unlink()
        self.emp.firmar_orden("activar_campana", ts="2026-11-09T07:00:01Z", nonce="futura")
        with self.assertRaises(ErrorBloqueado) as cm:
            self.comprobar_activar()
        self.assertIn("futura", cm.exception.mensaje)

    def test_orden_ilegible_se_ignora_y_otra_valida_pasa(self) -> None:
        self.emp.firmar_orden("activar_campana", nonce="buena")
        (self.emp.ruta("ordenes") / "a-rota.json").write_text("{no", encoding="utf-8")
        self.assertEqual(self.comprobar_activar().aprobacion, "buena")

    def test_sin_clave_publica_bloquea_el_paso_siete_si_el_cuatro_no_la_exigiera(self) -> None:
        # La pública falta: el paso 4 (sello de límites) ya lo detecta primero.
        env = {k: v for k, v in self.emp.env.items() if k != "FABRICA_FIRMA_PUBLICA"}
        self.emp.firmar_orden("activar_campana")
        with self.assertRaises(ErrorLimite) as cm:
            self.comprobar_activar(env=env)
        self.assertEqual(cm.exception.detalle["paso"], "limites")

    def test_acciones_sin_gate_humano_no_piden_orden(self) -> None:
        for op, kw in (("gastar", {}), ("reembolsar_auto", {"monto_minor": 1, "moneda": "EUR"}), ("descubrir", {"monto_minor": 1, "moneda": "EUR"})):
            with self.subTest(op=op):
                self.assertIsNone(self.comprobar(op, **kw).aprobacion)

    def test_reactivar_exige_su_propia_accion(self) -> None:
        self.emp.firmar_orden("activar_campana", nonce="n1")  # no sirve para reactivar
        with self.assertRaises(ErrorBloqueado):
            comprobar_live("reactivar", oferta_id=OFERTA, monto_minor=5000, moneda="EUR", sello=HASH_CONFIG, ahora=self.emp.reloj,
                           env=self.emp.env, raiz=self.emp.raiz, cuenta=CUENTA_ACTIVAR)
        self.emp.firmar_orden("reactivar_tras_pausa", nonce="n2")
        ctx = comprobar_live("reactivar_tras_pausa", oferta_id=OFERTA, monto_minor=5000, moneda="EUR", sello=HASH_CONFIG, ahora=self.emp.reloj,
                             env=self.emp.env, raiz=self.emp.raiz, cuenta=CUENTA_ACTIVAR)
        self.assertEqual((ctx.operacion, ctx.aprobacion), ("reactivar", "n2"))

    def test_la_orden_no_se_consume_ni_se_modifica(self) -> None:
        self.emp.firmar_orden("activar_campana", nonce="n1")
        antes = (self.emp.ruta("ordenes") / "n1.json").read_bytes()
        self.comprobar_activar()
        self.comprobar_activar()
        self.assertEqual((self.emp.ruta("ordenes") / "n1.json").read_bytes(), antes)


class PruebaOrdenFijo(BaseGuard):
    """Con todo roto a la vez, cada arreglo deja ver el paso siguiente: el orden es fijo."""

    def test_los_siete_pasos_fallan_en_su_orden(self) -> None:
        emp = self.emp
        token = emp.env.pop("META_TOKEN_OPERADOR")                                 # rompe el paso 6
        emp.env["FABRICA_ENTORNO"] = "prueba"                                      # rompe el paso 1
        emp.ruta("PAUSA").write_text("", encoding="utf-8")                          # rompe el paso 2
        emp.reescribir_estado(modo="prueba")                                        # rompe el paso 3
        emp.reescribir_limites(lambda lim: lim.update(gasto_diario_global=None))    # rompe el paso 4
        monto = {"valor": 5001}                                                     # rompe el paso 5 (tope + 1); el 7 no tiene orden

        def intentar() -> ContextoLive:
            return comprobar_live("activar", oferta_id=OFERTA, monto_minor=monto["valor"], moneda="EUR", sello=HASH_CONFIG, ahora=emp.reloj,
                                  env=emp.env, raiz=emp.raiz, cuenta=CUENTA_ACTIVAR)

        arreglos = [
            ("entorno", lambda: emp.env.update(FABRICA_ENTORNO="produccion")),
            ("pausa", lambda: emp.ruta("PAUSA").unlink()),
            ("infra", lambda: emp.reescribir_estado(modo="vivo")),
            ("limites", lambda: emp.reescribir_limites(lambda lim: lim.update(gasto_diario_global=10000))),
            ("topes", lambda: monto.update(valor=5000)),
            ("credenciales", lambda: emp.env.update(META_TOKEN_OPERADOR=token)),
            ("aprobacion", lambda: emp.firmar_orden("activar_campana")),
        ]
        for indice, (paso, arreglar) in enumerate(arreglos):
            with self.subTest(paso=paso):
                with self.assertRaises(ErrorFabrica) as cm:
                    intentar()
                self.assertEqual(cm.exception.detalle["paso"], paso)
                self.assertEqual(cm.exception.detalle["pasos_ok"], guard.PASOS[:indice])
                arreglar()
        self.assertEqual(intentar().pasos, guard.PASOS)


class PruebaSimulacion(PruebaBase):
    """``simulacion=True`` (solo B0): reemplaza el paso 1 y el 3; los demás no cambian; se niega en producción."""

    def setUp(self) -> None:
        super().setUp()
        self.emp = crear_empresa(self.tmp, modo_infra="prueba", entorno="prueba")
        self.transporte = TransporteFixture()

    def simular(self, operacion: str = "activar", **kw) -> ContextoLive:
        base = {"oferta_id": OFERTA, "monto_minor": 5000, "moneda": "EUR", "sello": HASH_CONFIG, "ahora": self.emp.reloj, "env": self.emp.env,
                "raiz": self.emp.raiz, "cuenta": CUENTA_ACTIVAR, "simulacion": True, "transporte": self.transporte}
        base.update(kw)
        return comprobar_live(operacion, **base)

    def test_caso_positivo_devuelve_contexto_fixture(self) -> None:
        self.emp.firmar_orden("activar_campana")
        ctx = self.simular()
        self.assertEqual(ctx.modo, "fixture")
        self.assertEqual(ctx.pasos, guard.PASOS)

    def test_la_simulacion_tampoco_se_salta_la_campana_del_efecto(self) -> None:
        self.emp.firmar_orden("activar_campana")
        with self.assertRaises(ErrorLimite) as cm:
            self.simular(cuenta=CUENTA_SIN_NUEVA)
        self.assertEqual(cm.exception.detalle["paso"], "topes")
        self.assertEqual(cm.exception.detalle["faltantes"], ["cuenta.nueva"])
        with self.assertRaises(ErrorLimite):
            self.simular(cuenta=EstadoCuenta(gasto_vitalicio_minor=0, nueva=_nueva(1)))  # monto_minor 5000 ≠ 1

    def test_tambien_vale_el_entorno_desarrollo_y_el_modo_simulado(self) -> None:
        self.emp.firmar_orden("activar_campana")
        self.emp.reescribir_estado(modo="simulado")
        self.assertEqual(self.simular(env={**self.emp.env, "FABRICA_ENTORNO": "desarrollo"}).modo, "fixture")

    def test_se_niega_con_produccion(self) -> None:
        self.emp.firmar_orden("activar_campana")
        with self.assertRaises(ErrorBloqueado) as cm:
            self.simular(env={**self.emp.env, "FABRICA_ENTORNO": "produccion"})
        self.assertEqual(cm.exception.detalle["paso"], "entorno")
        with self.assertRaises(ErrorBloqueado):
            self.simular(entorno="produccion")

    def test_exige_un_transporte_fixture(self) -> None:
        class Real:
            def solicitar(self, *a, **k):
                raise AssertionError("no debe llamarse")

        for transporte in (None, Real()):
            with self.subTest(transporte=type(transporte).__name__), self.assertRaises(ErrorBloqueado) as cm:
                self.simular(transporte=transporte)
            self.assertEqual(cm.exception.detalle["paso"], "entorno")

    def test_sin_simulacion_prueba_sigue_bloqueado(self) -> None:
        with self.assertRaises(ErrorBloqueado) as cm:
            self.simular(simulacion=False)
        self.assertEqual(cm.exception.detalle["paso"], "entorno")

    def test_el_modo_vivo_no_vale_en_simulacion(self) -> None:
        self.emp.reescribir_estado(modo="vivo")
        with self.assertRaises(ErrorBloqueado) as cm:
            self.simular()
        self.assertEqual(cm.exception.detalle["paso"], "infra")

    def test_infra_vencida_o_modo_ausente_bloquean_en_simulacion(self) -> None:
        self.emp.reescribir_estado(valido_hasta=comun.iso_z(AHORA_BASE - timedelta(seconds=1)))
        with self.assertRaises(ErrorBloqueado):
            self.simular()
        self.emp.reescribir_estado(valido_hasta=comun.iso_z(AHORA_BASE + timedelta(hours=1)), modo=ELIMINAR)
        with self.assertRaises(ErrorBloqueado):
            self.simular()

    def test_pausa_limites_credenciales_y_aprobacion_no_cambian(self) -> None:
        self.emp.ruta("PAUSA").write_text("", encoding="utf-8")
        with self.assertRaises(ErrorBloqueado) as cm:
            self.simular()
        self.assertEqual(cm.exception.detalle["paso"], "pausa")
        self.emp.ruta("PAUSA").unlink()

        with self.assertRaises(ErrorBloqueado) as cm:
            self.simular()  # todavía sin orden firmada
        self.assertEqual(cm.exception.detalle["paso"], "aprobacion")

        self.emp.reescribir_limites(lambda lim: lim.update(gasto_diario_global=None))
        with self.assertRaises(ErrorLimite) as cm:
            self.simular()
        self.assertEqual(cm.exception.detalle["paso"], "limites")
        self.emp.reescribir_limites(lambda lim: lim.update(gasto_diario_global=10000), firmar=False)  # sin firma Ed25519: tampoco vale
        with self.assertRaises(ErrorLimite) as cm:
            self.simular()
        self.assertEqual(cm.exception.detalle["paso"], "limites")
        self.assertIn("firma", cm.exception.mensaje)
        self.emp.reescribir_limites(lambda lim: lim.update(gasto_diario_global=10000))

        sin = {k: v for k, v in self.emp.env.items() if k != "META_APP_SECRET"}
        with self.assertRaises(ErrorUso):
            self.simular(env=sin)

    def test_las_credenciales_deben_ser_ficticias(self) -> None:
        real = "r" + "k_live_" + "abcdef123456"
        env = {**self.emp.env, "META_TOKEN_OPERADOR": "E" + "AAGabcdef1234567890", "STRIPE_RK_REEMBOLSO": real}
        with self.assertRaises(ErrorBloqueado) as cm:
            self.simular(env=env)
        self.assertEqual(cm.exception.detalle["paso"], "credenciales")
        self.assertNotIn("abcdef", cm.exception.mensaje)
        self.assertNotIn(real, repr(cm.exception.detalle))

    def test_la_orden_firmada_tampoco_se_salta_en_simulacion(self) -> None:
        self.emp.firmar_orden("activar_campana", alterar=True)
        with self.assertRaises(ErrorBloqueado):
            self.simular(sello="sha256:" + "cd" * 32)


class PruebaRelojInyectado(BaseGuard):
    """El reloj es el único tiempo que existe para el guard."""

    def test_reloj_sin_zona_se_rechaza(self) -> None:
        with self.assertRaises(ErrorValidacion):
            self.comprobar(ahora=lambda: datetime(2026, 11, 9, 7, 0, 0))

    def test_el_mismo_estado_cambia_de_veredicto_con_el_reloj(self) -> None:
        self.assertEqual(self.comprobar().pasos, guard.PASOS)
        self.fallo(ErrorBloqueado, "infra", ahora=lambda: AHORA_BASE + timedelta(hours=6))  # ya pasó valido_hasta
        otro_huso = datetime(2026, 11, 9, 8, 0, 0, tzinfo=timezone(timedelta(hours=1)))  # = 07:00Z
        self.assertEqual(self.comprobar(ahora=lambda: otro_huso).instante, "2026-11-09T07:00:00Z")

    def test_la_orden_se_mide_con_el_reloj_inyectado(self) -> None:
        self.emp.firmar_orden("activar_campana", ts="2026-11-09T06:30:00Z")
        self.assertEqual(self.comprobar_activar().pasos, guard.PASOS)
        with self.assertRaises(ErrorBloqueado):
            self.comprobar_activar(ahora=lambda: AHORA_BASE - timedelta(hours=1))  # la orden queda en el futuro


class PruebaClaves(PruebaBase):
    """Las tablas del guard cubren todas las operaciones de ``evaluar_limites``."""

    def test_toda_operacion_de_limites_tiene_regla_y_las_reglas_apuntan_a_operaciones_reales(self) -> None:
        from scripts.validar_esquemas import CLAVES_CRITICAS
        usadas = {r.clave_limites for r in guard.OPERACIONES.values()}
        self.assertEqual(usadas, set(CLAVES_CRITICAS))
        for alias, destino in guard.ALIAS_OPERACION.items():
            self.assertIn(destino, guard.OPERACIONES, alias)

    def test_regla_de_operacion_desconocida(self) -> None:
        with self.assertRaises(ErrorLimite):
            guard.regla_de("inventada")
        with self.assertRaises(ErrorLimite):
            guard.regla_de(None)  # type: ignore[arg-type]


class PruebaCli(PruebaBase):
    """``python -m engine.guard comprobar``: diagnóstico sin efectos."""

    def _correr(self, emp: EmpresaPrueba, *args: str, entorno: str = "prueba") -> tuple[int, str]:
        env = {**emp.env, "FABRICA_ENTORNO": entorno, "PATH": os.environ.get("PATH", "")}  # PATH para encontrar ssh-keygen
        salida = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(salida), contextlib.redirect_stderr(io.StringIO()):
            codigo = guard.main(["comprobar", *args])
        return codigo, salida.getvalue()

    def test_modo_fixture_aprueba_y_lista_los_pasos(self) -> None:
        emp = crear_empresa(self.tmp, modo_infra="prueba", entorno="prueba")
        emp.firmar_orden("activar_campana")
        cuenta = self.tmp / "cuenta.json"
        # perdida_acumulada_minor explícito (0): el JSON de --cuenta también debe declararlo (observación 1).
        nueva = {"oferta_id": OFERTA, "campaign_id": "c1", "max_teorico_diario_minor": 5000, "spend_cap_restante_minor": 0,
                "moneda": "EUR", "perdida_acumulada_minor": 0}
        cuenta.write_text(json.dumps({"activas": [], "gasto_vitalicio_minor": 0, "nueva": nueva}), encoding="utf-8")
        codigo, texto = self._correr(emp, "--operacion", "activar", "--oferta", OFERTA, "--monto", "5000", "--moneda", "EUR", "--sello", HASH_CONFIG,
                                     "--cuenta", str(cuenta), "--modo", "fixture", "--raiz", str(emp.raiz), "--ahora", "2026-11-09T07:00:00Z", "--json")
        self.assertEqual(codigo, 0, texto)
        datos = json.loads(texto)
        self.assertEqual(datos["modo"], "fixture")
        self.assertEqual(datos["datos"]["pasos"], list(guard.PASOS))

    def test_modo_fixture_sin_la_campana_del_efecto_se_bloquea_en_topes(self) -> None:
        emp = crear_empresa(self.tmp, modo_infra="prueba", entorno="prueba")
        emp.firmar_orden("activar_campana")
        cuenta = self.tmp / "cuenta.json"
        cuenta.write_text(json.dumps({"activas": [], "gasto_vitalicio_minor": 0}), encoding="utf-8")
        codigo, texto = self._correr(emp, "--operacion", "activar", "--oferta", OFERTA, "--monto", "5000", "--moneda", "EUR", "--sello", HASH_CONFIG,
                                     "--cuenta", str(cuenta), "--modo", "fixture", "--raiz", str(emp.raiz), "--ahora", "2026-11-09T07:00:00Z", "--json")
        self.assertEqual(codigo, 5, texto)
        datos = json.loads(texto)
        self.assertFalse(datos["ok"])
        self.assertEqual(datos["datos"]["paso"], "topes")

    def test_live_fuera_de_produccion_dice_en_que_paso_se_bloquea(self) -> None:
        emp = crear_empresa(self.tmp, modo_infra="prueba", entorno="prueba")
        codigo, texto = self._correr(emp, "--operacion", "gastar", "--monto", "1", "--moneda", "EUR", "--raiz", str(emp.raiz), "--json")
        self.assertEqual(codigo, 4)
        datos = json.loads(texto)
        self.assertFalse(datos["ok"])
        self.assertEqual(datos["datos"]["paso"], "entorno")

    def test_raiz_inexistente_en_produccion_dice_paso_entorno_con_cuatro(self) -> None:
        # CT2-14: antes salía con 2 y «paso «None»»; ahora BLOQUEADO en el paso «entorno» (4).
        emp = crear_empresa(self.tmp)
        env = {**emp.env, "FABRICA_ENTORNO": "produccion", "FABRICA_RAIZ": str(self.tmp / "no-existe"), "PATH": os.environ.get("PATH", "")}
        salida, errores = io.StringIO(), io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
            codigo = guard.main(["comprobar", "--operacion", "gastar", "--monto", "100", "--moneda", "EUR", "--json"])
        self.assertEqual(codigo, 4, salida.getvalue() + errores.getvalue())
        datos = json.loads(salida.getvalue())
        self.assertFalse(datos["ok"])
        self.assertEqual(datos["datos"]["paso"], "entorno")
        self.assertNotIn("None", json.dumps(datos["datos"]["paso"]))

    def test_raiz_y_ahora_no_existen_en_produccion(self) -> None:
        emp = crear_empresa(self.tmp)
        codigo, _ = self._correr(emp, "--operacion", "gastar", "--raiz", str(emp.raiz), entorno="produccion")
        self.assertEqual(codigo, 2)

    def test_limites_en_null_dan_cinco(self) -> None:
        emp = crear_empresa(self.tmp, modo_infra="prueba", entorno="prueba")
        emp.reescribir_limites(lambda lim: lim.update(capital_en_riesgo_total=None))
        codigo, texto = self._correr(emp, "--operacion", "gastar", "--monto", "1", "--moneda", "EUR", "--modo", "fixture", "--raiz", str(emp.raiz),
                                     "--ahora", "2026-11-09T07:00:00Z", "--json")
        self.assertEqual(codigo, 5)
        self.assertEqual(json.loads(texto)["datos"]["paso"], "limites")

    def test_cuenta_inexistente_da_dos_no_uno(self) -> None:
        # Antes: Path(args.cuenta) se leía DENTRO de la llamada a comprobar_live, así que un archivo
        # inexistente era un FileNotFoundError sin tipo (código 1, con traza) en vez de 2 (observación 10).
        emp = crear_empresa(self.tmp, modo_infra="prueba", entorno="prueba")
        codigo, texto = self._correr(emp, "--operacion", "activar", "--oferta", OFERTA, "--monto", "5000", "--moneda", "EUR",
                                     "--sello", HASH_CONFIG, "--cuenta", str(self.tmp / "no-existe.json"), "--modo", "fixture",
                                     "--raiz", str(emp.raiz), "--ahora", "2026-11-09T07:00:00Z")
        self.assertEqual(codigo, 2, texto)

    def test_cuenta_ilegible_da_dos_no_paso_none(self) -> None:
        # Antes: un --cuenta con JSON inválido se leía como argumento de comprobar_live, y el
        # ErrorValidacion resultante no traía "paso" en su detalle (se evaluaba ANTES del try de los 7
        # pasos): el JSON de salida mostraba "paso": None en vez de un error de uso claro (observación 10).
        emp = crear_empresa(self.tmp, modo_infra="prueba", entorno="prueba")
        cuenta = self.tmp / "cuenta.json"
        cuenta.write_text("{esto no es json", encoding="utf-8")
        codigo, texto = self._correr(emp, "--operacion", "activar", "--oferta", OFERTA, "--monto", "5000", "--moneda", "EUR",
                                     "--sello", HASH_CONFIG, "--cuenta", str(cuenta), "--modo", "fixture", "--raiz", str(emp.raiz),
                                     "--ahora", "2026-11-09T07:00:00Z")
        self.assertEqual(codigo, 2, texto)
        self.assertNotIn("paso None", texto)
        self.assertNotIn("Traceback", texto)


if __name__ == "__main__":
    unittest.main()
