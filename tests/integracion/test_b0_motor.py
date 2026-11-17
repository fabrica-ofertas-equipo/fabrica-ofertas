"""B0-05, 06, 07, 16, 19, 22, 23, 25 (I1a, ola 2): ``scripts.b0.motor`` sobre ``engine.estado``/
``engine.orq``/``engine.d8``/``engine.cerrar`` REALES. Un ``setUpClass`` corre el recorrido D1..D7
UNA vez (es costoso: crea 6 ofertas reales) y cada prueba positiva lee su propio resultado; las
negativas (siembran el fallo) corren aparte, sobre funciones puras o escenarios mínimos propios.
"""
from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from engine.ejecutor import EjecutorMotor
from scripts.b0 import motor as M


class PruebaPositivaRecorrido(unittest.TestCase):
    """B0-05/06/07/23/25: una sola corrida real de :func:`scripts.b0.motor.recorrido_m1_d7` (+ B0-25 aparte)."""

    _tmp_dir: tempfile.TemporaryDirectory | None = None
    _tmp: Path | None = None

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._tmp_dir = tempfile.TemporaryDirectory(prefix="test-b0-motor-")
        cls._tmp = Path(cls._tmp_dir.name)

    @classmethod
    def tearDownClass(cls) -> None:
        assert cls._tmp_dir is not None
        cls._tmp_dir.cleanup()
        super().tearDownClass()

    def test_b0_05(self) -> None:
        r = M.evaluar_b0_05(self._tmp)
        self.assertEqual("verde", r.estado, r.motivo)

    def test_b0_06(self) -> None:
        r = M.evaluar_b0_06(self._tmp)
        self.assertEqual("verde", r.estado, r.motivo)

    def test_b0_07(self) -> None:
        r = M.evaluar_b0_07(self._tmp)
        self.assertEqual("verde", r.estado, r.motivo)

    def test_b0_23(self) -> None:
        r = M.evaluar_b0_23(self._tmp)
        self.assertEqual("verde", r.estado, r.motivo)

    def test_b0_25(self) -> None:
        r = M.evaluar_b0_25(self._tmp)
        self.assertEqual("verde", r.estado, r.motivo)


class PruebaPositivaD8(unittest.TestCase):
    """B0-16/19/22: cada una abre su propia raíz temporal (no comparten estado con el recorrido D1..D7)."""

    def test_b0_16(self) -> None:
        r = M.evaluar_b0_16()
        self.assertEqual("verde", r.estado, r.motivo)

    def test_b0_19(self) -> None:
        r = M.evaluar_b0_19()
        self.assertEqual("verde", r.estado, r.motivo)

    def test_b0_22(self) -> None:
        r = M.evaluar_b0_22()
        self.assertEqual("verde", r.estado, r.motivo)


class PruebaNegativaSembrada(unittest.TestCase):
    """Siembra un defecto y confirma que el criterio sale ROJO (no se debilita ninguna aserción)."""

    def test_recorrido_roto_da_rojo_en_los_4_criterios(self) -> None:
        roto = {"fallo_en": "D3", "etapas": {"D3": {"resultado": "escalado"}}}
        criterios = M._criterios_desde_recorrido(roto)
        self.assertEqual(set(criterios), {"B0-05", "B0-06", "B0-07", "B0-23"})
        for id_, c in criterios.items():
            self.assertEqual("rojo", c.estado, id_)
            self.assertIn("D3", c.motivo)

    def test_obsolescencia_faltante_da_rojo_en_b0_07(self) -> None:
        r = {
            "oferta_id": "OF-X",
            "etapas": {e: {"resultado": "aprobado", "version": "v1", "rondas": 1 if e != "D2" else 2} for e in M._ORDEN_ETAPAS},
            "d1_reutilizado": {"resultado": "reutilizado", "hash_salida": "sha256:" + "a" * 64},
            "escalado": {"resultado": "escalado"},
            "escalado_estado": {"etapas": {"D1": {"estado": "escalado"}}},
            # D4 NO quedó obsoleta (defecto sembrado): propagar_obsolescencia debería haber tocado las 4.
            "estado_tras_v2": {
                "fase": "pausada",
                "etapas": {
                    "D4": {"obsoleta": False, "estado": "aprobado"},
                    "D5": {"obsoleta": True, "estado": "pendiente"},
                    "D6": {"obsoleta": True, "estado": "pendiente"},
                    "D7": {"obsoleta": True, "estado": "pendiente"},
                },
            },
            "d3_v2": {"resultado": "aprobado", "version": "v2"},
            "paridad": {"ejecutar": {"hash_salida": "h", "resultado": "aprobado"}, "ingresar": {"hash_salida": "h", "resultado": "aprobado"}},
            "symlink_codigo": 3,
        }
        r["etapas"]["D1"]["hash_salida"] = "sha256:" + "a" * 64
        r["d1_reutilizado"] = {"resultado": "reutilizado", "hash_salida": "sha256:" + "a" * 64}
        criterios = M._criterios_desde_recorrido(r)
        self.assertEqual("rojo", criterios["B0-07"].estado)
        self.assertIn("se esperaban 4", criterios["B0-07"].motivo)

    def test_sin_evidencia_el_ciclo_real_no_mata_ni_escala(self) -> None:
        """Control: con 0 EUR de gasto y 0 clics, engine.d8.ciclo debe dar SEGUIR, nunca MATAR/ESCALAR
        (si una regresión futura lo rompiera, esta prueba -no la del criterio- lo marcaría ROJO primero)."""
        with tempfile.TemporaryDirectory(prefix="test-b0-motor-d8-sin-evidencia-") as tmp_str:
            raiz, oferta_id, _ = M._preparar_oferta_en_test(Path(tmp_str), slug="sinevidencia")
            conn = M._conexion_d8_memoria()
            try:
                conn.execute("INSERT INTO dim_anuncio VALUES (?,?,?)", ("AD-00", oferta_id, None))
                par, lim = M._parametros_b0_motor(), M._limites_b0_motor()
                ahora = lambda: datetime(2026, 11, 24, 9, 0, 0, tzinfo=timezone.utc)
                from engine import d8 as engine_d8

                registros = engine_d8.ciclo(oferta_id, conn=conn, ahora=ahora, par=par, lim=lim,
                                            ejecutor=EjecutorMotor(raiz=raiz, ahora=ahora), modo="live", raiz=raiz)
            finally:
                conn.close()
            acciones = {r["objeto_id"]: r["accion"] for r in registros}
            self.assertEqual(acciones[oferta_id], "SEGUIR")

    def test_api_ordenes_rechaza_una_firma_alterada(self) -> None:
        """Siembra: altera el cuerpo DESPUÉS de firmarlo (misma cabecera HMAC) -> 401, nunca 200."""
        from dashboard.api import ApiServicio

        with tempfile.TemporaryDirectory(prefix="test-b0-motor-ordenes-neg-") as tmp_str:
            from tests.engine import apoyo

            tmp = Path(tmp_str)
            emp = apoyo.crear_empresa(tmp, modo_infra="prueba", entorno="prueba")
            from dashboard.api import firmar as firmar_api
            from engine import comun

            orden = {"schema_version": "1.1.0", "accion": "aprobar_etapa", "oferta_id": "OF-202611-01",
                    "hash_objetivo": "sha256:" + "aa" * 32, "ts": comun.iso_z(emp.reloj()), "nonce": "nonce-de-prueba-negativa-01",
                    "etapa": "D1"}
            orden["firma"] = comun.firmar_ed25519(comun.json_canonico(orden), emp.claves.privada)
            cuerpo_bueno = comun.json_canonico(orden)
            cuerpo_alterado = cuerpo_bueno.replace(b"D1", b"M1")  # altera DESPUÉS de firmar
            secreto = b"secreto-de-prueba-negativa"
            ts_cab = comun.iso_z(emp.reloj())
            firma_cab = firmar_api(secreto, cuerpo_bueno, ts_cab)  # firma del cuerpo BUENO, no del alterado
            app = ApiServicio(raiz=emp.raiz, secreto=secreto, parametros={"tolerancia_seg": 300, "cuerpo_max_bytes": 65536},
                              ahora=emp.reloj, env=emp.env)
            codigo, _ = M._llamar_wsgi(app, cuerpo=cuerpo_alterado, ts=ts_cab, firma=firma_cab)
            self.assertEqual(codigo, 401)


if __name__ == "__main__":
    unittest.main()
