"""B0-09: sesión con metadata completa, firma falsa -> 400, duplicado -> una entrega, event_id en CAPI."""
from __future__ import annotations

import unittest

from scripts.b0 import tracking as T


class PruebaB0_09(unittest.TestCase):
    def test_evaluar_b0_09_es_verde(self) -> None:
        r = T.evaluar_b0_09()
        self.assertEqual("verde", r.estado, r.motivo)


class PruebaNegativaSembrada(unittest.TestCase):
    def _base(self) -> dict:
        return {
            "sesion_status": 200, "metadata_adid": "a", "metadata_asid": "b", "metadata_cid": "c",
            "metadata_consent": "1", "metadata_visitor_id": "v", "firma_falsa_status": 400,
            "firma_falsa_codigo": "firma_no_coincide", "ok_status": 200, "ok_codigo": "encolado",
            "duplicada_status": 200, "duplicada_codigo": "duplicado", "llamadas_graph": 1,
            "event_id_capi": "purchase_cs_1", "event_id_esperado": "purchase_cs_1",
        }

    def test_detecta_reenvio_a_graph_en_el_duplicado(self) -> None:
        salida = self._base()
        salida["llamadas_graph"] = 2  # debería ser 1: el duplicado no debe reenviar a CAPI
        ok, motivo = T._interpretar(salida)
        self.assertFalse(ok)
        self.assertIn("llamadas_graph", motivo)

    def test_detecta_event_id_incorrecto(self) -> None:
        salida = self._base()
        salida["event_id_capi"] = "purchase_otra_sesion"
        ok, motivo = T._interpretar(salida)
        self.assertFalse(ok)
        self.assertIn("event_id_capi", motivo)

    def test_detecta_metadata_incompleta(self) -> None:
        salida = self._base()
        salida["metadata_adid"] = None
        ok, motivo = T._interpretar(salida)
        self.assertFalse(ok)
        self.assertIn("metadata incompleta", motivo)


if __name__ == "__main__":
    unittest.main()
