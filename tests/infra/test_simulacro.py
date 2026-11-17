"""Pruebas de ``infra.simulacro``: el harness A-1…A-12 corre sin red, nunca da verde falso y
degrada a ROJO (nunca excepción sin capturar) si una pieza inyectada se porta mal."""
from __future__ import annotations

from datetime import datetime, timezone

from infra import simulacro
from tests.infra.apoyo import PruebaBase

AHORA = lambda: datetime(2026, 11, 9, 8, 0, 0, tzinfo=timezone.utc)  # noqa: E731


class PruebaInforme(PruebaBase):
    def test_ejecutar_simulacro_devuelve_los_12_ids_sin_rojo_y_sin_verde_falso(self) -> None:
        informe = simulacro.ejecutar_simulacro(raiz=self.tmp, ahora=AHORA)
        ids = [r.id for r in informe.resultados]
        self.assertEqual(ids, [f"A-{n}" for n in range(1, 13)])
        for r in informe.resultados:
            self.assertIn(r.estado, simulacro.ESTADOS)
            self.assertTrue(r.motivo)
        self.assertEqual(informe.resumen["ROJO"], 0)
        self.assertTrue(informe.ok)

    def test_pendientes_tienen_motivo_honesto_nunca_vacio(self) -> None:
        informe = simulacro.ejecutar_simulacro(raiz=self.tmp, ahora=AHORA)
        pendientes = [r for r in informe.resultados if r.estado == "PENDIENTE"]
        self.assertGreater(len(pendientes), 0)
        for r in pendientes:
            self.assertGreater(len(r.motivo), 20)

    def test_las_verdes_reales_estan_presentes(self) -> None:
        informe = simulacro.ejecutar_simulacro(raiz=self.tmp, ahora=AHORA)
        por_id = {r.id: r.estado for r in informe.resultados}
        for esperado_verde in ("A-1", "A-2", "A-3", "A-4", "A-8", "A-10", "A-12"):
            self.assertEqual(por_id[esperado_verde], "VERDE", esperado_verde)

    def test_raiz_real_del_repositorio_no_se_toca(self) -> None:
        from engine import comun
        real = comun.raiz()
        antes = (real / "empresa" / "PAUSA").is_file()
        simulacro.ejecutar_simulacro(raiz=self.tmp, ahora=AHORA)
        despues = (real / "empresa" / "PAUSA").is_file()
        self.assertEqual(antes, despues)


class PruebaA1A2PausaYLectura(PruebaBase):
    def test_a1_pausa_bloquea_exactamente_en_ese_paso(self) -> None:
        informe = simulacro.ejecutar_simulacro(raiz=self.tmp, ahora=AHORA)
        a1 = next(r for r in informe.resultados if r.id == "A-1")
        self.assertEqual(a1.estado, "VERDE")
        self.assertEqual(a1.evidencia["paso"], "pausa")

    def test_a2_sin_pausa_avanza_pero_sigue_bloqueado(self) -> None:
        informe = simulacro.ejecutar_simulacro(raiz=self.tmp, ahora=AHORA)
        a2 = next(r for r in informe.resultados if r.id == "A-2")
        self.assertEqual(a2.estado, "VERDE")
        self.assertNotEqual(a2.evidencia["paso"], "pausa")


class PruebaA3A4MetaPausar(PruebaBase):
    def test_pausa_exactamente_las_dos_activas(self) -> None:
        informe = simulacro.ejecutar_simulacro(raiz=self.tmp, ahora=AHORA)
        a3 = next(r for r in informe.resultados if r.id == "A-3")
        self.assertEqual(set(a3.evidencia["pausadas"]), {"c1", "c2"})


class PruebaA8Permisos(PruebaBase):
    def test_403_se_propaga_como_errorexterno(self) -> None:
        informe = simulacro.ejecutar_simulacro(raiz=self.tmp, ahora=AHORA)
        a8 = next(r for r in informe.resultados if r.id == "A-8")
        self.assertEqual(a8.estado, "VERDE")
        self.assertIn("excepcion", a8.evidencia)


class PruebaA12Reanudar(PruebaBase):
    def test_tres_combinaciones_incompletas_bloquean_y_la_completa_quita_pausa(self) -> None:
        informe = simulacro.ejecutar_simulacro(raiz=self.tmp, ahora=AHORA)
        a12 = next(r for r in informe.resultados if r.id == "A-12")
        self.assertEqual(a12.estado, "VERDE")
        self.assertEqual(len(a12.evidencia["intentos"]), 3)
        self.assertTrue(all(bloqueo for _, _, bloqueo in a12.evidencia["intentos"]))


class PruebaCLI(PruebaBase):
    def test_cli_ejecutar_sale_0_cuando_no_hay_rojo(self) -> None:
        codigo = simulacro.main(["ejecutar", "--raiz", str(self.tmp), "--ahora", "2026-11-09T08:00:00Z", "--json"])
        self.assertEqual(codigo, 0)

    def test_cli_rechaza_raiz_en_produccion(self) -> None:
        import os
        from unittest import mock

        with mock.patch.dict(os.environ, {"FABRICA_ENTORNO": "produccion"}, clear=False):
            codigo = simulacro.main(["ejecutar", "--raiz", str(self.tmp), "--json"])
        self.assertEqual(codigo, 2)
