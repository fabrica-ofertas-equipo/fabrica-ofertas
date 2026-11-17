"""Pruebas de `datos.ingesta`: firma, tolerancia de tiempo, forma de evento/entrega e idempotencia."""
from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone

from engine.parametros import Parametros
from scripts.validar_esquemas import errores_de_esquema

from datos.ingesta import VISITOR_SIN_ATRIBUCION, manejar_ingesta_entrega, manejar_ingesta_evento, ruta_entregas
from tests.datos.apoyo import OFERTA, PruebaBase, reloj_fijo

SECRETO = b"secreto-de-prueba-ingesta"
AHORA_DT = datetime(2026, 11, 11, 12, 0, 0, tzinfo=timezone.utc)
AHORA = reloj_fijo(AHORA_DT)
PARAMETROS_OK = Parametros({"grupos": {
    "ingesta": {
        "tolerancia_seg": {"valor": 300, "unidad": "segundos", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None},
        "cuerpo_max_bytes": {"valor": 8192, "unidad": "bytes", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None},
    },
    "entrega": {
        "enlace_vence_dias": {"valor": 14, "unidad": "dias", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None},
        "enlace_max_descargas": {"valor": 5, "unidad": "descargas", "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None},
    },
}})
PARAMETROS_SIN_INGESTA = Parametros({"grupos": {}})


def _cuerpo_evento(**extra: object) -> bytes:
    base = {"event_id": "pv_" + "v" * 16 + "_2026-11-11T12:00:00Z", "oferta_id": OFERTA, "tipo": "PageView",
            "ts": "2026-11-11T12:00:00Z", "visitor_id": "v" * 16, "fuente": "pixel", "consentimiento": True}
    base.update(extra)
    return json.dumps(base, sort_keys=True).encode("utf-8")


def _cuerpo_entrega(**extra: object) -> bytes:
    base = {"checkout_session_id": "cs_test_a1b2c3", "oferta_id": OFERTA, "estado": "entregado", "intento": 1,
            "producto_sha256": "sha256:" + "a" * 64, "ts": "2026-11-11T12:00:00Z"}
    base.update(extra)
    return json.dumps(base, sort_keys=True).encode("utf-8")


def _firmar(cuerpo: bytes, ts: str, *, secreto: bytes = SECRETO) -> dict[str, str]:
    firma = hmac.new(secreto, ts.encode("utf-8") + b"." + cuerpo, hashlib.sha256).hexdigest()
    return {"X-Fabrica-Ts": ts, "X-Fabrica-Firma": f"hmac-sha256={firma}"}


class PruebaManejarIngestaEvento(PruebaBase):
    def test_evento_valido_se_acepta_y_se_puede_repetir_sin_duplicar(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_evento()
        cabeceras = _firmar(cuerpo, "2026-11-11T12:00:00Z")
        estado, respuesta = manejar_ingesta_evento(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO)
        self.assertEqual(estado, 200)
        self.assertEqual(respuesta["resultado"], "nuevo")
        estado2, respuesta2 = manejar_ingesta_evento(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO)
        self.assertEqual(estado2, 200)
        self.assertEqual(respuesta2["resultado"], "duplicado")
        self.assertEqual(conn.ejecutar("SELECT COUNT(*) FROM fact_evento").fetchone()[0], 1)

    def test_evento_con_atribucion_y_valor_se_persiste_completo(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_evento(tipo="Purchase", cid="123456", asid="654321", adid="120210000000103",
                                fuente="capi", valor_minor=1990, moneda="EUR")
        cabeceras = _firmar(cuerpo, "2026-11-11T12:00:00Z")
        estado, respuesta = manejar_ingesta_evento(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO)
        self.assertEqual((estado, respuesta["resultado"]), (200, "nuevo"))
        fila = conn.ejecutar("SELECT cid, asid, adid, fuente, valor_minor, moneda FROM fact_evento").fetchone()
        self.assertEqual(tuple(fila), ("123456", "654321", "120210000000103", "capi", 1990, "EUR"))

    def test_sin_consentimiento_se_guarda_sin_atribucion_ni_identificadores(self) -> None:
        # Criterio acordado con S-C/dashboard.api: 200 y ``atribuible: false``; el evento cuenta en los totales
        # agregados pero no guarda cid/asid/adid ni el visitor_id real (minimización).
        conn = self.conexion()
        cuerpo = _cuerpo_evento(consentimiento=False, cid="123456", asid="654321", adid="120210000000103", visitor_id="secreto-de-visitante-123")
        estado, respuesta = manejar_ingesta_evento(cuerpo, _firmar(cuerpo, "2026-11-11T12:00:00Z"), conn, AHORA,
                                                   parametros=PARAMETROS_OK, secreto=SECRETO)
        self.assertEqual((estado, respuesta["resultado"], respuesta["atribuible"]), (200, "nuevo", False))
        fila = conn.ejecutar("SELECT visitor_id, cid, asid, adid, consentimiento FROM fact_evento").fetchone()
        self.assertEqual(tuple(fila), (VISITOR_SIN_ATRIBUCION, None, None, None, 0))
        volcado = json.dumps([tuple(r) for r in conn.ejecutar("SELECT * FROM fact_evento").fetchall()])
        self.assertNotIn("secreto-de-visitante-123", volcado)
        self.assertNotIn("123456", volcado)

    def test_con_consentimiento_la_respuesta_marca_atribuible(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_evento(cid="123456")
        _, respuesta = manejar_ingesta_evento(cuerpo, _firmar(cuerpo, "2026-11-11T12:00:00Z"), conn, AHORA,
                                              parametros=PARAMETROS_OK, secreto=SECRETO)
        self.assertTrue(respuesta["atribuible"])

    def test_reenviar_el_mismo_evento_sin_consentimiento_es_duplicado_no_conflicto(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_evento(consentimiento=False, cid="123456")
        cab = _firmar(cuerpo, "2026-11-11T12:00:00Z")
        manejar_ingesta_evento(cuerpo, cab, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO)
        estado, respuesta = manejar_ingesta_evento(cuerpo, cab, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO)
        self.assertEqual((estado, respuesta["resultado"]), (200, "duplicado"))
        self.assertEqual(conn.ejecutar("SELECT COUNT(*) FROM fact_evento").fetchone()[0], 1)

    def test_mismo_event_id_con_otro_contenido_es_409(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_evento()
        cabeceras = _firmar(cuerpo, "2026-11-11T12:00:00Z")
        manejar_ingesta_evento(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO)
        otro = json.loads(cuerpo)
        otro["oferta_id"] = "OF-202611-02"
        otro_cuerpo = json.dumps(otro, sort_keys=True).encode("utf-8")
        otras_cabeceras = _firmar(otro_cuerpo, "2026-11-11T12:00:00Z")
        estado, respuesta = manejar_ingesta_evento(otro_cuerpo, otras_cabeceras, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO)
        self.assertEqual((estado, respuesta["motivo"]), (409, "event_id_con_otro_contenido"))

    def test_sin_parametros_de_ingesta_falla_cerrado_500(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_evento()
        cabeceras = _firmar(cuerpo, "2026-11-11T12:00:00Z")
        estado, respuesta = manejar_ingesta_evento(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_SIN_INGESTA, secreto=SECRETO)
        self.assertEqual(estado, 500)
        self.assertEqual(respuesta["motivo"], "parametros_ingesta_faltantes")

    def test_cuerpo_demasiado_grande_se_rechaza(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_evento(relleno="x" * 9000)
        cabeceras = _firmar(cuerpo, "2026-11-11T12:00:00Z")
        estado, respuesta = manejar_ingesta_evento(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO)
        self.assertEqual(estado, 413)

    def test_sin_cabeceras_de_firma_se_rechaza_401(self) -> None:
        conn = self.conexion()
        estado, respuesta = manejar_ingesta_evento(_cuerpo_evento(), {}, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO)
        self.assertEqual(estado, 401)
        self.assertEqual(respuesta["motivo"], "firma_ausente")

    def test_firma_invalida_se_rechaza_401(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_evento()
        cabeceras = _firmar(cuerpo, "2026-11-11T12:00:00Z", secreto=b"otro-secreto")
        estado, respuesta = manejar_ingesta_evento(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO)
        self.assertEqual(estado, 401)
        self.assertEqual(respuesta["motivo"], "firma_invalida")

    def test_marca_de_tiempo_fuera_de_tolerancia_se_rechaza(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_evento()
        ts_lejano = "2026-11-11T11:00:00Z"  # 1 h antes de AHORA, tolerancia = 300 s
        cabeceras = _firmar(cuerpo, ts_lejano)
        estado, respuesta = manejar_ingesta_evento(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO)
        self.assertEqual(estado, 400)
        self.assertEqual(respuesta["motivo"], "ts_fuera_de_tolerancia")

    def test_evento_mal_formado_se_rechaza_sin_lanzar(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_evento(tipo="Lead")  # no está en el enumerado
        cabeceras = _firmar(cuerpo, "2026-11-11T12:00:00Z")
        estado, respuesta = manejar_ingesta_evento(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO)
        self.assertEqual(estado, 400)
        self.assertEqual(respuesta["motivo"], "evento_invalido")

    def test_campo_no_permitido_se_rechaza(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_evento(email="a@b.c")
        cabeceras = _firmar(cuerpo, "2026-11-11T12:00:00Z")
        estado, respuesta = manejar_ingesta_evento(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO)
        self.assertEqual(estado, 400)
        self.assertIn("campo no permitido: email", respuesta["problemas"])

    def test_valor_minor_sin_moneda_se_rechaza(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_evento(valor_minor=1990)
        cabeceras = _firmar(cuerpo, "2026-11-11T12:00:00Z")
        estado, respuesta = manejar_ingesta_evento(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO)
        self.assertEqual(estado, 400)
        self.assertIn("valor_minor y moneda van juntos", respuesta["problemas"])

    def test_sin_secreto_configurado_falla_cerrado_500(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_evento()
        cabeceras = _firmar(cuerpo, "2026-11-11T12:00:00Z")
        estado, respuesta = manejar_ingesta_evento(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_OK, secreto=b"")
        self.assertEqual(estado, 500)
        self.assertEqual(respuesta["motivo"], "secreto_ausente")


class PruebaManejarIngestaEntrega(PruebaBase):
    def test_entrega_valida_upsert_fact_entrega_y_entregas_jsonl(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_entrega()
        cabeceras = _firmar(cuerpo, "2026-11-11T12:00:00Z")
        estado, respuesta = manejar_ingesta_entrega(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_OK,
                                                     secreto=SECRETO, raiz=self.tmp)
        self.assertEqual((estado, respuesta["resultado"]), (200, "nuevo"))
        fila = conn.ejecutar("SELECT session_id, oferta_id, estado, intentos, producto_sha256 FROM fact_entrega").fetchone()
        self.assertEqual(tuple(fila), ("cs_test_a1b2c3", OFERTA, "entregado", 1, "sha256:" + "a" * 64))
        ruta = ruta_entregas(self.tmp, OFERTA)
        self.assertTrue(ruta.is_file())
        lineas = [json.loads(l) for l in ruta.read_text("utf-8").splitlines()]
        self.assertEqual(len(lineas), 1)
        self.assertEqual(errores_de_esquema("entrega", lineas[0]), [])
        self.assertIsNone(lineas[0]["email_hmac"])
        self.assertEqual(lineas[0]["enlace"], {"vence_en": "2026-11-25T12:00:00Z", "max_descargas": 5, "descargas": 0})

    def test_misma_transicion_repetida_no_duplica_la_linea(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_entrega()
        cabeceras = _firmar(cuerpo, "2026-11-11T12:00:00Z")
        manejar_ingesta_entrega(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_OK, secreto=SECRETO, raiz=self.tmp)
        estado, respuesta = manejar_ingesta_entrega(cuerpo, cabeceras, conn, AHORA, parametros=PARAMETROS_OK,
                                                     secreto=SECRETO, raiz=self.tmp)
        self.assertEqual((estado, respuesta["resultado"]), (200, "duplicado"))
        ruta = ruta_entregas(self.tmp, OFERTA)
        self.assertEqual(len(ruta.read_text("utf-8").splitlines()), 1)

    def test_nueva_transicion_agrega_linea_y_actualiza_fact_entrega(self) -> None:
        conn = self.conexion()
        cuerpo1 = _cuerpo_entrega(estado="encolado", intento=0)
        manejar_ingesta_entrega(cuerpo1, _firmar(cuerpo1, "2026-11-11T12:00:00Z"), conn, AHORA,
                                parametros=PARAMETROS_OK, secreto=SECRETO, raiz=self.tmp)
        cuerpo2 = _cuerpo_entrega(estado="entregado", intento=1)
        estado, respuesta = manejar_ingesta_entrega(cuerpo2, _firmar(cuerpo2, "2026-11-11T12:00:00Z"), conn, AHORA,
                                                     parametros=PARAMETROS_OK, secreto=SECRETO, raiz=self.tmp)
        self.assertEqual((estado, respuesta["resultado"]), (200, "nuevo"))
        ruta = ruta_entregas(self.tmp, OFERTA)
        self.assertEqual(len(ruta.read_text("utf-8").splitlines()), 2)
        fila = conn.ejecutar("SELECT estado, intentos FROM fact_entrega WHERE session_id = ?", ("cs_test_a1b2c3",)).fetchone()
        self.assertEqual(tuple(fila), ("entregado", 1))

    def test_misma_transicion_con_otro_contenido_es_409(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_entrega()
        manejar_ingesta_entrega(cuerpo, _firmar(cuerpo, "2026-11-11T12:00:00Z"), conn, AHORA,
                                parametros=PARAMETROS_OK, secreto=SECRETO, raiz=self.tmp)
        otro = _cuerpo_entrega(producto_sha256="sha256:" + "b" * 64)
        estado, respuesta = manejar_ingesta_entrega(otro, _firmar(otro, "2026-11-11T12:00:00Z"), conn, AHORA,
                                                     parametros=PARAMETROS_OK, secreto=SECRETO, raiz=self.tmp)
        self.assertEqual((estado, respuesta["motivo"]), (409, "entrega_con_otro_contenido"))

    def test_estado_pagado_no_es_valido_para_este_endpoint(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_entrega(estado="pagado")
        estado, respuesta = manejar_ingesta_entrega(cuerpo, _firmar(cuerpo, "2026-11-11T12:00:00Z"), conn, AHORA,
                                                     parametros=PARAMETROS_OK, secreto=SECRETO, raiz=self.tmp)
        self.assertEqual((estado, respuesta["motivo"]), (400, "entrega_invalida"))

    def test_campo_email_no_permitido(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_entrega(email="a@b.c")
        estado, respuesta = manejar_ingesta_entrega(cuerpo, _firmar(cuerpo, "2026-11-11T12:00:00Z"), conn, AHORA,
                                                     parametros=PARAMETROS_OK, secreto=SECRETO, raiz=self.tmp)
        self.assertEqual(estado, 400)
        self.assertIn("campo no permitido: email", respuesta["problemas"])

    def test_intento_negativo_se_rechaza(self) -> None:
        conn = self.conexion()
        cuerpo = _cuerpo_entrega(intento=-1)
        estado, respuesta = manejar_ingesta_entrega(cuerpo, _firmar(cuerpo, "2026-11-11T12:00:00Z"), conn, AHORA,
                                                     parametros=PARAMETROS_OK, secreto=SECRETO, raiz=self.tmp)
        self.assertEqual((estado, respuesta["motivo"]), (400, "entrega_invalida"))

    def test_sin_parametros_de_entrega_falla_cerrado_500(self) -> None:
        conn = self.conexion()
        sin_entrega = Parametros({"grupos": {"ingesta": PARAMETROS_OK._datos["grupos"]["ingesta"]}})  # noqa: SLF001
        cuerpo = _cuerpo_entrega()
        cabeceras = _firmar(cuerpo, "2026-11-11T12:00:00Z")
        estado, respuesta = manejar_ingesta_entrega(cuerpo, cabeceras, conn, AHORA, parametros=sin_entrega,
                                                     secreto=SECRETO, raiz=self.tmp)
        self.assertEqual(estado, 500)
        self.assertEqual(respuesta["motivo"], "parametros_ingesta_faltantes")
