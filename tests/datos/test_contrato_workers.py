"""Prueba de contrato de PUNTA A PUNTA (SOLO LECTURA de los Workers de B2/B7, docs/06 §4.9 «pedido 3»):
corre el firmador REAL de `tracking/workers/eventos` (B2) y el Worker REAL `infra/workers/fulfill`
(B7) en un arnés Node sin red (`tests/fixtures/datos/arnes_worker_*.mjs`) y valida lo que de verdad
firman y envían contra `datos.ingesta.manejar_ingesta_evento`/`manejar_ingesta_entrega`.

No se modifica ningún Worker (no son de B3): si uno firmara distinto al contrato de docs/06 §4.7, la
prueba correspondiente debe reflejarlo (ver `test_fulfill_no_firma_el_post_a_ingesta_entrega`, que
documenta una diferencia real encontrada esta noche — PEDIDO a B7, ver README «Pedidos»).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import unittest
from datetime import datetime, timezone
from pathlib import Path

from engine.parametros import Parametros

from datos.ingesta import manejar_ingesta_entrega, manejar_ingesta_evento
from tests.datos.apoyo import OFERTA, PruebaBase, reloj_fijo

RAIZ_REPO = Path(__file__).resolve().parents[2]
_FIXTURES = RAIZ_REPO / "tests" / "fixtures" / "datos"
ARNES_EVENTOS = _FIXTURES / "arnes_worker_eventos.mjs"
ARNES_FULFILL = _FIXTURES / "arnes_worker_fulfill.mjs"
NODE = shutil.which("node")

SECRETO_TXT = "secreto-arnes-workers-0123456789"
SECRETO = SECRETO_TXT.encode("utf-8")
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


def _correr_arnes(ruta: Path, entrada: dict) -> dict:
    resultado = subprocess.run([NODE, str(ruta)], input=json.dumps(entrada), capture_output=True, text=True,
                               timeout=20, check=False)
    if resultado.returncode != 0:
        raise AssertionError(f"arnés Node ({ruta.name}) falló: {resultado.stderr}")
    return json.loads(resultado.stdout)


@unittest.skipUnless(NODE, "node no disponible en este entorno")
class PruebaContratoWorkerEventos(PruebaBase):
    """`tracking/workers/eventos` (B2) firma con la MISMA fórmula que `datos.ingesta` espera."""

    def test_lo_que_firma_el_worker_eventos_lo_acepta_manejar_ingesta_evento(self) -> None:
        ahora_iso = "2026-11-11T12:00:00Z"
        cuerpo_entrante = {
            "event_id": "pv_arnes_contrato_0000001", "oferta_id": OFERTA, "tipo": "PageView", "ts": ahora_iso,
            "visitor_id": "v" * 16, "fuente": "pixel", "consentimiento": True,
        }
        salida = _correr_arnes(ARNES_EVENTOS, {"secreto": SECRETO_TXT, "ahora": ahora_iso, "cuerpo": cuerpo_entrante})
        self.assertEqual(salida["resultado"]["status"], 202, salida)
        capturado = salida["capturado"]
        self.assertEqual(capturado["url"], "http://local/ingesta/evento")
        conn = self.conexion()
        estado, respuesta = manejar_ingesta_evento(
            capturado["cuerpo"].encode("utf-8"), capturado["cabeceras"], conn, reloj_fijo(_parsear(ahora_iso)),
            parametros=PARAMETROS_OK, secreto=SECRETO,
        )
        self.assertEqual((estado, respuesta.get("resultado")), (200, "nuevo"), respuesta)


@unittest.skipUnless(NODE, "node no disponible en este entorno")
class PruebaContratoWorkerFulfill(PruebaBase):
    """`infra/workers/fulfill` (B7) hacia `POST /ingesta/entrega`."""

    def _cuerpo_webhook(self) -> dict:
        return {
            "session_id": "cs_test_arnes_contrato1", "oferta_id": OFERTA, "producto_version": "v2",
            "producto_sha256": "sha256:" + "a" * 64, "email": "cliente@example.com",
        }

    def test_fulfill_firma_el_post_a_ingesta_entrega_y_el_servicio_lo_acepta(self) -> None:
        """B3b encontró que `postEntregaApi` mandaba el POST SIN firma (401 `firma_ausente` en producción); el
        constructor principal lo corrigió en `infra/workers/fulfill/src/index.mjs`. Esta prueba corre el Worker REAL
        (sin red, `fetch` interceptado) y comprueba que las cabeceras que emite (`X-Fabrica-Ts` y
        `X-Fabrica-Firma: hmac-sha256=<hex>` de `ts + "." + cuerpo`) las ACEPTA `manejar_ingesta_entrega`.
        """
        ahora_real = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        salida = _correr_arnes(ARNES_FULFILL, {"secreto": SECRETO_TXT, "ahora": ahora_real, "cuerpoWebhook": self._cuerpo_webhook()})
        self.assertEqual(salida["status"], 200, salida)
        capturas_entrega = [c for c in salida["capturas"] if c["url"].endswith("/ingesta/entrega")]
        self.assertEqual(len(capturas_entrega), 1, salida)
        cabeceras_reales = capturas_entrega[0]["cabeceras"]
        self.assertIn("X-Fabrica-Ts", cabeceras_reales)
        self.assertRegex(cabeceras_reales["X-Fabrica-Firma"], r"^hmac-sha256=[0-9a-f]{64}$")
        cuerpo_real = capturas_entrega[0]["cuerpo"].encode("utf-8")
        conn = self.conexion()
        estado, respuesta = manejar_ingesta_entrega(
            cuerpo_real, cabeceras_reales, conn, reloj_fijo(_parsear(ahora_real)),
            parametros=PARAMETROS_OK, secreto=SECRETO, raiz=self.tmp,
        )
        self.assertEqual((estado, respuesta.get("resultado")), (200, "nuevo"), respuesta)

    def test_una_firma_con_otro_secreto_o_un_cuerpo_alterado_se_rechaza(self) -> None:
        ahora_real = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        salida = _correr_arnes(ARNES_FULFILL, {"secreto": SECRETO_TXT, "ahora": ahora_real, "cuerpoWebhook": self._cuerpo_webhook()})
        captura = [c for c in salida["capturas"] if c["url"].endswith("/ingesta/entrega")][0]
        cabeceras, cuerpo = captura["cabeceras"], captura["cuerpo"].encode("utf-8")
        conn = self.conexion()
        estado, _ = manejar_ingesta_entrega(cuerpo + b" ", cabeceras, conn, reloj_fijo(_parsear(ahora_real)),
                                            parametros=PARAMETROS_OK, secreto=SECRETO, raiz=self.tmp)
        self.assertEqual(estado, 401)
        estado, _ = manejar_ingesta_entrega(cuerpo, cabeceras, conn, reloj_fijo(_parsear(ahora_real)),
                                            parametros=PARAMETROS_OK, secreto=b"otro-secreto", raiz=self.tmp)
        self.assertEqual(estado, 401)

    def test_la_firma_manual_segun_el_contrato_tambien_la_acepta(self) -> None:
        """Mismo cuerpo que el Worker manda de verdad, pero firmado como exige docs/06 §4.7: confirma
        que la firma del contrato (calculada a mano) coincide con la que emite el Worker.
        """
        import hashlib
        import hmac as hmac_mod

        ahora_real = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        salida = _correr_arnes(ARNES_FULFILL, {"secreto": SECRETO_TXT, "ahora": ahora_real, "cuerpoWebhook": self._cuerpo_webhook()})
        capturas_entrega = [c for c in salida["capturas"] if c["url"].endswith("/ingesta/entrega")]
        cuerpo_real = capturas_entrega[0]["cuerpo"].encode("utf-8")
        firma = hmac_mod.new(SECRETO, ahora_real.encode("utf-8") + b"." + cuerpo_real, hashlib.sha256).hexdigest()
        cabeceras = {"X-Fabrica-Ts": ahora_real, "X-Fabrica-Firma": f"hmac-sha256={firma}"}
        conn = self.conexion()
        estado, respuesta = manejar_ingesta_entrega(
            cuerpo_real, cabeceras, conn, reloj_fijo(_parsear(ahora_real)),
            parametros=PARAMETROS_OK, secreto=SECRETO, raiz=self.tmp,
        )
        self.assertEqual((estado, respuesta.get("resultado")), (200, "nuevo"), respuesta)


def _parsear(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
