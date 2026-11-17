"""Pruebas de `datos.db`: conexión portable, traducción de marcadores, migraciones y `upsert`."""
from __future__ import annotations

from engine.errores import ErrorExterno, ErrorUso, ErrorValidacion

from datos.db import conectar, migraciones_aplicadas, migrar, traducir_marcadores
from tests.datos.apoyo import PruebaBase, reloj_fijo
from datetime import datetime, timezone


class PruebaTraducirMarcadores(PruebaBase):
    def test_sqlite_no_cambia(self) -> None:
        self.assertEqual(traducir_marcadores("SELECT * FROM t WHERE a = ? AND b = ?", "sqlite"),
                         "SELECT * FROM t WHERE a = ? AND b = ?")

    def test_postgresql_traduce_signos_de_interrogacion(self) -> None:
        self.assertEqual(traducir_marcadores("SELECT * FROM t WHERE a = ? AND b = ?", "postgresql"),
                         "SELECT * FROM t WHERE a = %s AND b = %s")

    def test_postgresql_no_toca_interrogaciones_dentro_de_cadenas(self) -> None:
        self.assertEqual(traducir_marcadores("SELECT '¿qué?' AS x WHERE a = ?", "postgresql"),
                         "SELECT '¿qué?' AS x WHERE a = %s")

    def test_dialecto_desconocido_es_error_de_uso(self) -> None:
        with self.assertRaises(ErrorUso):
            traducir_marcadores("SELECT 1", "mysql")


class PruebaConectar(PruebaBase):
    def test_sqlite_en_memoria(self) -> None:
        conn = conectar("sqlite:///:memory:")
        self.addCleanup(conn.cerrar)
        conn.ejecutar("CREATE TABLE t (a TEXT)")
        conn.commit()

    def test_sqlite_crea_el_archivo_y_las_carpetas(self) -> None:
        ruta = self.tmp / "sub" / "fabrica.db"
        conn = conectar(f"sqlite:///{ruta}")
        self.addCleanup(conn.cerrar)
        self.assertTrue(ruta.exists())

    def test_postgresql_sin_controlador_es_error_externo(self) -> None:
        with self.assertRaises(ErrorExterno):
            conectar("postgresql://usuario:clave@host/basededatos")

    def test_url_no_reconocida_es_error_de_uso(self) -> None:
        with self.assertRaises(ErrorUso):
            conectar("mysql://host/basededatos")

    def test_url_vacia_es_error_de_uso(self) -> None:
        with self.assertRaises(ErrorUso):
            conectar("")


class PruebaMigrar(PruebaBase):
    def test_aplica_la_migracion_inicial_y_crea_las_tablas(self) -> None:
        conn = self.conexion()
        aplicadas = migraciones_aplicadas(conn)
        self.assertIn("0001_inicial.sql", aplicadas)
        for tabla in ("stripe_evento", "fact_meta_ad_dia", "fact_pedido", "fact_reembolso", "fact_disputa", "fact_evento_tracking"):
            conn.ejecutar(f"SELECT COUNT(*) FROM {tabla}")  # no lanza: la tabla existe

    def test_reaplicar_es_idempotente(self) -> None:
        conn = self.conexion()
        nuevas = migrar(conn, ahora=reloj_fijo(datetime(2026, 11, 6, 0, 0, 0, tzinfo=timezone.utc)))
        self.assertEqual(nuevas, [])


class PruebaUpsert(PruebaBase):
    def test_inserta_y_luego_actualiza_la_misma_clave(self) -> None:
        conn = self.conexion()
        conn.upsert("fact_disputa", ["dispute_id"], {
            "dispute_id": "dp_1", "oferta_id": "OF-202611-01", "checkout_session_id": None,
            "monto_minor": 1990, "moneda": "EUR", "estado": "warning_needs_response",
            "creado_ts": "2026-11-12T08:00:00Z", "dia_utc": "2026-11-12", "ingerido_en": "2026-11-12T08:00:01Z",
        })
        conn.upsert("fact_disputa", ["dispute_id"], {
            "dispute_id": "dp_1", "oferta_id": "OF-202611-01", "checkout_session_id": "cs_1",
            "monto_minor": 1990, "moneda": "EUR", "estado": "lost",
            "creado_ts": "2026-11-12T08:00:00Z", "dia_utc": "2026-11-12", "ingerido_en": "2026-11-13T08:00:01Z",
        })
        conn.commit()
        filas = conn.ejecutar("SELECT estado, checkout_session_id FROM fact_disputa").fetchall()
        self.assertEqual(len(filas), 1)
        self.assertEqual(filas[0]["estado"], "lost")
        self.assertEqual(filas[0]["checkout_session_id"], "cs_1")

    def test_identificador_invalido_es_error_de_validacion(self) -> None:
        conn = self.conexion()
        with self.assertRaises(ErrorValidacion):
            conn.upsert("fact_disputa; DROP TABLE fact_disputa", ["dispute_id"], {"dispute_id": "x"})
