"""Pruebas de ``engine.cerrar``: fase final y post-mortem mínimo (N17)."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

from engine import cerrar, comun, estado
from engine.errores import ErrorBloqueado
from tests.engine import apoyo
from tests.engine.apoyo_orq import EJEMPLO

BRIEF_MINIMO = {"mercado_objetivo": {"moneda_cobro": "EUR"}}
VEREDICTO_BASE = json.loads((EJEMPLO / "08-operacion" / "veredicto_oferta.json").read_text(encoding="utf-8"))


class PruebaCerrar(apoyo.PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.raiz = self.tmp
        self.ahora = lambda: datetime(2026, 11, 25, 9, 0, 0, tzinfo=timezone.utc)
        self.est = estado.crear(BRIEF_MINIMO, oferta_id="OF-202611-01", familia_id="FAM-202611-01", nivel="N2",
                                raiz=self.raiz, ahora=self.ahora)
        for de, a in (("borrador", "en_construccion"), ("en_construccion", "listo_para_activar"), ("listo_para_activar", "en_test")):
            estado.transicionar_fase(self.est["oferta_id"], a, actor="prueba", causa="avance", raiz=self.raiz, ahora=self.ahora)

    def _escribir_veredicto(self, estado_v: str) -> None:
        datos = copy.deepcopy(VEREDICTO_BASE)
        datos["estado"] = estado_v
        ruta = self.raiz / "ofertas" / self.est["oferta_id"] / "08-operacion" / "veredicto_oferta.json"
        comun.escribir_atomico(ruta, comun.json_canonico(datos))

    def test_sin_veredicto_no_se_puede_cerrar(self) -> None:
        with self.assertRaises(ErrorBloqueado):
            cerrar.cerrar_oferta(self.est["oferta_id"], raiz=self.raiz, ahora=self.ahora)

    def test_prometedora_no_cierra_la_oferta(self) -> None:
        self._escribir_veredicto("PROMETEDORA")
        with self.assertRaises(ErrorBloqueado):
            cerrar.cerrar_oferta(self.est["oferta_id"], raiz=self.raiz, ahora=self.ahora)
        self.assertEqual(estado.cargar(self.est["oferta_id"], raiz=self.raiz)["fase"], "en_test")

    def test_fallida_mueve_la_fase_y_escribe_postmortem(self) -> None:
        self._escribir_veredicto("FALLIDA")
        resultado = cerrar.cerrar_oferta(self.est["oferta_id"], raiz=self.raiz, ahora=self.ahora)
        self.assertEqual(resultado["fase"], "fallida")
        self.assertFalse(resultado["reutilizado"])
        self.assertEqual(estado.cargar(self.est["oferta_id"], raiz=self.raiz)["fase"], "fallida")
        ruta_post = self.raiz / "ofertas" / self.est["oferta_id"] / "08-operacion" / "postmortem.json"
        self.assertTrue(ruta_post.is_file())
        post = json.loads(ruta_post.read_text(encoding="utf-8"))
        self.assertEqual(comun.errores_de_esquema("postmortem", post), [])
        self.assertEqual(post["retraso_clic_compra"], {"n_compras": 0, "mediana_h": None, "p90_h": None, "fuente": "no_medible"})

    def test_validada_deja_nota_para_d9_sin_ejecutar_nada(self) -> None:
        self._escribir_veredicto("VALIDADA")
        cerrar.cerrar_oferta(self.est["oferta_id"], raiz=self.raiz, ahora=self.ahora)
        ruta_nota = self.raiz / "ofertas" / self.est["oferta_id"] / "09-escalado" / "propuesta-d9.md"
        self.assertTrue(ruta_nota.is_file())
        self.assertIn("VALIDADA", ruta_nota.read_text(encoding="utf-8"))

    def test_cerrar_de_nuevo_es_idempotente_la_fase_final_no_se_reescribe(self) -> None:
        self._escribir_veredicto("INCONCLUSA")
        primero = cerrar.cerrar_oferta(self.est["oferta_id"], raiz=self.raiz, ahora=self.ahora)
        segundo = cerrar.cerrar_oferta(self.est["oferta_id"], raiz=self.raiz, ahora=self.ahora)
        self.assertFalse(primero["reutilizado"])
        self.assertTrue(segundo["reutilizado"])
        self.assertEqual(segundo["postmortem"], primero["postmortem"])


if __name__ == "__main__":
    import unittest
    unittest.main()
