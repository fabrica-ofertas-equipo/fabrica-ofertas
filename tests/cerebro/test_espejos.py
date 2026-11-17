"""Las copias que el Cerebro mantiene a propósito (cada skill corre sola, sin paquete) no pueden desviarse unas de otras ni de los parámetros firmados."""
from __future__ import annotations

import json
import unittest

from tests.cerebro._apoyo import RAIZ, buscar, comun, gp, jardinero, jsonl, preferencias, ra

PARES = [("Fijar y firmar los límites de gasto", "Fijar los límites de gasto"), ("Elegir proveedor de correo", "elegir proveedor de correo."), ("Una baja al día sin venta", "Tres días sin venta"),
         ("", "algo"), ("a", "a"), ("Precio frontal: escalera", "Escalera de precio frontal"), ("Sin abogado para las páginas legales", "Sin abogado para las paginas legales")]
BITACORA = [
    {"id": "PUL-0001", "evento": "alta", "titulo": "a", "estado": "abierta"}, {"id": "PUL-0001", "evento": "estado", "estado": "en_curso"},
    {"id": "PUL-0002", "titulo": "b", "estado": "rara"}, {"id": "PUL-0003", "evento": "estado", "estado": "resuelta"}, {"id": "PUL-0002", "estado": "resuelta"},
    {"id": "malo", "titulo": "x"}, {"id": 5, "titulo": "y"}, {"id": "PUL-0004", "evento": "alta", "titulo": "d"}, {"id": "PUL-0004", "evento": "alta", "titulo": "d2", "estado": "resuelta"},
    {"id": "PUL-0004", "evento": "estado", "estado": "no_es_estado"},
]


class PruebasEspejos(unittest.TestCase):
    def test_la_similitud_es_la_misma_en_el_cierre_y_en_el_jardinero(self) -> None:
        for a, b in PARES:
            self.assertEqual(gp.similitud(a, b), comun.similitud(a, b), (a, b))

    def test_los_umbrales_son_los_del_yaml_firmado(self) -> None:
        import yaml
        memoria = yaml.safe_load((RAIZ / "empresa" / "parametros.yaml").read_text(encoding="utf-8"))["grupos"]["memoria"]
        self.assertEqual(float(memoria["sim_dup"]["valor"]), gp.SIM_DUP)
        self.assertEqual(float(memoria["sim_relevante"]["valor"]), gp.SIM_RELEVANTE)
        self.assertEqual((comun.SIM_DUP, comun.SIM_RELEVANTE), (gp.SIM_DUP, gp.SIM_RELEVANTE))

    def test_plegar_la_bitacora_da_lo_mismo_en_las_tres_copias(self) -> None:
        a, b = ra.plegar_bitacora(BITACORA), comun.plegar_bitacora(BITACORA)
        self.assertEqual(a, b)
        self.assertEqual([x["id"] for x in a], ["PUL-0001", "PUL-0002", "PUL-0004"])
        self.assertEqual([x["estado"] for x in a], ["en_curso", "resuelta", "resuelta"])
        # el cierre pliega igual el estado (cuenta como ya guardado lo resuelto también)
        c = gp.existentes_vigentes(gp.REL_PULIDO, ("\n".join(json.dumps(o) for o in BITACORA) + "\n").encode())
        self.assertEqual([x["id"] for x in c], [x["id"] for x in a])

    def test_limpieza_de_texto_y_fechas_iguales(self) -> None:
        sucio = "a\x00b\x07 ‮c  d\n\te" + "x" * 300
        for n in (10, 140, 200):
            self.assertEqual(ra.corto(sucio, n), comun.corto(sucio, n))
        for f in ("2026-11-09", "2026-11-09T12:00:00Z", "2026-02-30", "nada", None, 5):
            self.assertEqual(ra._dia(f), comun.dia(f))
        self.assertEqual(ra.RX_DIRECCION.pattern, comun.RX_DIRECCION.pattern)
        self.assertEqual(ra.RX_CONTROL.pattern, comun.RX_CONTROL.pattern)

    def test_preferencias_vigentes_igual_en_las_tres_copias(self) -> None:
        base = {"ts": "2026-11-09T10:00:00Z", "tipo": "preferencia", "etapa": "D6", "criterio": "c", "vigente": True, "autor": "dueno"}
        lineas = [{**base, "id": "PRF-0001", "estado": "aprobada"}, {**base, "id": "PRF-0002", "estado": "revocada", "revoca": "PRF-0001"}, {**base, "id": "PRF-0003", "estado": "aprobada"},
                  {**base, "id": "PRF-0004", "estado": "rechazada"}, {**base, "id": "PRF-0005", "estado": "aprobada", "autor": "ia"}]
        self.assertEqual(gp.preferencias_vigentes(lineas), comun.preferencias_vigentes(lineas))
        self.assertEqual([x["id"] for x in comun.preferencias_vigentes(lineas)], ["PRF-0003"])
        r = ra.resumir_preferencias([], lineas, 0)
        self.assertEqual(r["vigentes"], 1)

    def test_las_etapas_validas_del_lector_son_las_de_la_lista_unica(self) -> None:
        self.assertEqual(preferencias.ETAPAS_VALIDAS, gp.ETAPAS_PULIDO)

    def test_las_rutas_son_las_mismas(self) -> None:
        self.assertEqual((ra.REL_PULIDO, ra.REL_DECISIONES, ra.REL_LECCIONES, ra.REL_PREFERENCIAS, ra.REL_JARDIN), (gp.REL_PULIDO, gp.REL_DECISIONES, gp.REL_LECCIONES, gp.REL_PREFERENCIAS, comun.REL_JARDIN))
        self.assertEqual((comun.REL_PULIDO, comun.REL_DECISIONES, comun.REL_LECCIONES, comun.REL_PREFERENCIAS), (gp.REL_PULIDO, gp.REL_DECISIONES, gp.REL_LECCIONES, gp.REL_PREFERENCIAS))
        from dashboard import api_cerebro, pulido
        self.assertEqual(pulido.REL_PULIDO, gp.REL_PULIDO)
        self.assertEqual(api_cerebro.REL_JARDIN, comun.REL_JARDIN, "el panel cuenta las propuestas del jardinero en la misma carpeta donde el jardinero las deja")
        self.assertIn(gp.REL_DECISIONES, [rel for _, rel, _ in api_cerebro.ARCHIVOS_MEMORIA])
        self.assertIn(gp.REL_LECCIONES, [rel for _, rel, _ in api_cerebro.ARCHIVOS_MEMORIA])


if __name__ == "__main__":
    unittest.main(verbosity=1)
