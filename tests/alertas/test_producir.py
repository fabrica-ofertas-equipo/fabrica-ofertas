"""Productor de alertas: ``--simular`` no escribe, ``--escribir`` es atómico e idempotente, cierra solo lo que dejó de cumplirse y no pisa lo ajeno."""
from __future__ import annotations

import contextlib
import io
import json
import os
import unittest

from scripts.alertas import producir as P
from scripts.alertas.hechos import REL_ALERTAS
from scripts.validar_esquemas import errores_de_esquema, problemas_alertas, problemas_artefacto
from tests.alertas.ayudas import AHORA, Base, LIMITES_COMPLETOS, LIMITES_VACIOS, PARAMETROS

OTRA_HORA = AHORA.replace(hour=9, minute=15)


def correr(*args: str) -> tuple[int, str, str]:
    salida, error = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(error):
        try:
            rc = P.main(list(args))
        except SystemExit as e:        # argparse
            rc = int(e.code or 0)
    return rc, salida.getvalue(), error.getvalue()


def lineas(base: Base) -> list[dict]:
    return [json.loads(x) for x in (base.raiz / REL_ALERTAS).read_text(encoding="utf-8").splitlines() if x.strip()]


class PruebaProducir(Base):
    def setUp(self) -> None:
        super().setUp()
        self.poner("empresa/parametros.yaml", PARAMETROS)
        self.poner("empresa/limites.yaml", LIMITES_VACIOS)

    def test_simular_no_escribe_nada_ni_siquiera_la_carpeta(self) -> None:
        antes = self.hash_arbol()
        arbol = self.arbol()
        r = P.producir(self.ctx())
        self.assertEqual(r["modo"], "simulado")
        self.assertEqual(self.hash_arbol(), antes)
        self.assertEqual(self.arbol(), arbol)
        self.assertFalse((self.raiz / "empresa" / "datos").exists())
        self.assertGreater(r["abiertas"], 0)

    def test_la_linea_de_comandos_por_defecto_solo_simula(self) -> None:
        rc, salida, _ = correr("--raiz", str(self.raiz), "--ahora", "2026-11-07T08:30:00Z")
        self.assertEqual(rc, 0)
        self.assertIn("SIMULACRO (no se escribió nada)", salida)
        self.assertFalse((self.raiz / REL_ALERTAS).exists())
        rc, salida, _ = correr("--raiz", str(self.raiz), "--ahora", "2026-11-07T08:30:00Z", "--simular", "--json")
        self.assertEqual((rc, json.loads(salida)["modo"]), (0, "simulado"))
        rc, _, error = correr("--raiz", str(self.raiz), "--simular", "--escribir")
        self.assertEqual(rc, 2, "no se puede pedir las dos cosas a la vez")
        rc, _, error = correr("--raiz", str(self.raiz), "--ahora", "ayer")
        self.assertEqual(rc, 2)
        self.assertIn("2026-11-07T08:30:00Z", error)
        rc, _, error = correr("--raiz", str(self.raiz / "no-existe"))
        self.assertEqual(rc, 2)

    def test_escribir_deja_un_archivo_valido_y_es_lo_unico_que_cambia(self) -> None:
        antes = self.arbol()
        r = P.producir(self.ctx(), escribir=True)
        self.assertEqual(r["modo"], "escrito")
        self.assertEqual(self.arbol() - antes, {REL_ALERTAS}, "la única escritura de todo el programa")
        filas = lineas(self)
        self.assertEqual(len(filas), r["lineas"])
        for f in filas:
            self.assertEqual(list(errores_de_esquema("alertas", f)), [], f["id"])
            self.assertEqual(problemas_artefacto("alertas", f), [])
            self.assertEqual(list(f), ["schema_version", "id", "ts", "severidad", "regla_id", "origen", "oferta_id", "macro_nicho", "nivel", "valor", "umbral", "accion_sugerida", "estado"])
        self.assertEqual(problemas_alertas(filas), [])
        self.assertEqual({f["estado"] for f in filas}, {"abierta"})
        self.assertEqual({f["ts"] for f in filas}, {"2026-11-07T08:30:00Z"})
        self.assertEqual(os.listdir(self.raiz / "empresa" / "datos"), ["alertas.jsonl"], "sin restos de archivos temporales")

    def test_idempotente_mismo_instante_mismo_archivo_byte_a_byte(self) -> None:
        P.producir(self.ctx(), escribir=True)
        primero = (self.raiz / REL_ALERTAS).read_bytes()
        r = P.producir(self.ctx(), escribir=True)
        self.assertIs(r["sin_cambios"], True)
        self.assertEqual((self.raiz / REL_ALERTAS).read_bytes(), primero)
        self.assertEqual((r["ids_nuevas"], r["ids_cerradas"]), ([], []))

    def test_repetir_mas_tarde_solo_actualiza_la_hora_no_duplica_ni_cambia_estados(self) -> None:
        P.producir(self.ctx(), escribir=True)
        antes = lineas(self)
        r = P.producir(self.ctx(OTRA_HORA), escribir=True)
        despues = lineas(self)
        self.assertEqual(len(despues), len(antes))
        self.assertEqual([{k: v for k, v in f.items() if k != "ts"} for f in despues], [{k: v for k, v in f.items() if k != "ts"} for f in antes])
        self.assertEqual({f["ts"] for f in despues}, {"2026-11-07T09:15:00Z"})
        self.assertEqual(r["ids_nuevas"], [])

    def test_lo_que_ya_no_se_cumple_se_cierra_una_sola_vez_y_si_vuelve_se_reabre(self) -> None:
        self.poner("empresa/captura/freno.json", {"ts": "2026-11-06T06:03:43Z", "motivo": "HTTP 403"})
        P.producir(self.ctx(), escribir=True)
        self.assertEqual({f["id"]: f["estado"] for f in lineas(self)}["F2-AUS-FRENO:captura"], "abierta")
        (self.raiz / "empresa" / "captura" / "freno.json").unlink()            # el dueño levantó el freno
        r = P.producir(self.ctx(OTRA_HORA), escribir=True)
        freno = [f for f in lineas(self) if f["id"] == "F2-AUS-FRENO:captura"]
        self.assertEqual((len(freno), freno[0]["estado"], freno[0]["ts"]), (1, "cerrada", "2026-11-07T09:15:00Z"))
        self.assertEqual(r["ids_cerradas"], ["F2-AUS-FRENO:captura"])
        r = P.producir(self.ctx(OTRA_HORA.replace(hour=10)), escribir=True)
        freno = [f for f in lineas(self) if f["id"] == "F2-AUS-FRENO:captura"]
        self.assertEqual((freno[0]["estado"], freno[0]["ts"]), ("cerrada", "2026-11-07T09:15:00Z"), "una cerrada no se vuelve a tocar")
        self.assertEqual(r["ids_cerradas"], [])
        self.poner("empresa/captura/freno.json", {"ts": "2026-11-07T10:30:00Z", "motivo": "otra vez"})
        r = P.producir(self.ctx(OTRA_HORA.replace(hour=11)), escribir=True)
        freno = [f for f in lineas(self) if f["id"] == "F2-AUS-FRENO:captura"]
        self.assertEqual((len(freno), freno[0]["estado"]), (1, "abierta"))
        self.assertEqual(r["ids_nuevas"], ["F2-AUS-FRENO:captura"])
        self.assertEqual(problemas_alertas(lineas(self)), [])

    def test_una_alerta_reconocida_que_sigue_viva_sigue_reconocida(self) -> None:
        P.producir(self.ctx(), escribir=True)
        filas = lineas(self)
        for f in filas:
            if f["id"] == "F2-AUS-CANAL:empresa":
                f["estado"] = "reconocida"
        self.jsonl(REL_ALERTAS, filas)
        P.producir(self.ctx(OTRA_HORA), escribir=True)
        self.assertEqual({f["id"]: f["estado"] for f in lineas(self)}["F2-AUS-CANAL:empresa"], "reconocida")

    def test_las_lineas_ajenas_y_las_ilegibles_se_conservan_byte_a_byte(self) -> None:
        ajena = '{"schema_version":"1.0.0","id":"F1-A02:OF-202611-01","ts":"2026-11-06T10:00:00Z","severidad":"naranja","regla_id":"F1-A02","origen":"F1","oferta_id":"OF-202611-01","macro_nicho":null,"nivel":null,"valor":"1.4","umbral":"1.0","accion_sugerida":"Pausar la oferta","estado":"abierta"}'
        otra = '{"estado":"abierta","id":"F2-A06:x","regla_id":"F2-A06","origen":"F2","severidad":"amarilla"}'      # orden de claves raro: se respeta tal cual
        basura = "esto no es json"
        self.poner(REL_ALERTAS, f"{ajena}\n{basura}\n{otra}\n")
        P.producir(self.ctx(), escribir=True)
        texto = (self.raiz / REL_ALERTAS).read_text(encoding="utf-8").splitlines()
        for esperado in (ajena, otra, basura):
            self.assertIn(esperado, texto)
        self.assertEqual(texto[0], basura, "lo ilegible va primero y sin tocar")
        P.producir(self.ctx(), escribir=True)
        self.assertEqual((self.raiz / REL_ALERTAS).read_text(encoding="utf-8").splitlines().count(ajena), 1, "sin duplicar lo ajeno")

    def test_id_repetido_en_el_archivo_no_se_duplica(self) -> None:
        P.producir(self.ctx(), escribir=True)
        filas = lineas(self)
        self.jsonl(REL_ALERTAS, filas + [filas[0]])
        P.producir(self.ctx(), escribir=True)
        ids = [f["id"] for f in lineas(self)]
        self.assertEqual(len(ids), len(set(ids)))

    def test_se_guardan_como_mucho_las_ultimas_cerradas(self) -> None:
        cerradas = [{"schema_version": "1.0.0", "id": f"F2-AUS-GATE:OF-202611-91:D{i}", "ts": f"2026-10-{(i % 28) + 1:02d}T00:00:00Z", "severidad": "amarilla", "regla_id": "F2-AUS-GATE", "origen": "F2",
                     "oferta_id": None, "macro_nicho": None, "nivel": None, "valor": 1, "umbral": None, "accion_sugerida": "x", "estado": "cerrada"} for i in range(150)]
        self.jsonl(REL_ALERTAS, cerradas)
        P.producir(self.ctx(), escribir=True)
        self.assertEqual(sum(1 for f in lineas(self) if f["estado"] == "cerrada"), P.MAX_CERRADAS)

    def test_si_el_archivo_no_se_puede_leer_entero_no_se_escribe_y_se_dice(self) -> None:
        self.poner(REL_ALERTAS, b"x" * (P.TOPE_ARCHIVO + 10))
        antes = self.hash_arbol()
        with self.assertRaises(P.ErrorArchivo):
            P.producir(self.ctx(), escribir=True)
        self.assertEqual(self.hash_arbol(), antes)
        rc, _, error = correr("--raiz", str(self.raiz), "--escribir")
        self.assertEqual(rc, 3)
        self.assertIn("demasiado grande", error)
        r = P.producir(self.ctx())                       # simular sí funciona y avisa
        self.assertTrue(any("demasiado grande" in a for a in r["avisos"]))

    def test_no_escribe_a_traves_de_un_enlace_que_sale_de_la_raiz(self) -> None:
        fuera = self.raiz.parent / (self.raiz.name + "-fuera")
        fuera.mkdir()
        self.addCleanup(lambda: __import__("shutil").rmtree(fuera, True))
        os.symlink(fuera, self.raiz / "empresa" / "datos")
        rc, _, error = correr("--raiz", str(self.raiz), "--escribir")
        self.assertEqual(rc, 3)
        self.assertEqual(os.listdir(fuera), [], "nada se escribió fuera de la raíz")

    def test_sin_estado_cambia_y_con_estado_cambia_el_archivo(self) -> None:
        r1 = P.producir(self.ctx(), escribir=True)
        self.assertIs(r1["sin_cambios"], False)
        self.poner("empresa/limites.yaml", LIMITES_COMPLETOS)
        r2 = P.producir(self.ctx(), escribir=True)
        self.assertIn("F2-AUS-LIM:empresa", r2["ids_cerradas"])
        self.assertIs(r2["sin_cambios"], False)

    def test_el_resultado_trae_el_semaforo_las_pendientes_y_es_json(self) -> None:
        r = P.producir(self.ctx())
        self.assertEqual(r["semaforo"]["nivel"], "rojo")
        self.assertEqual(len(r["reglas_pendientes"]), 15)
        json.dumps(r)
        _, salida, _ = correr("--raiz", str(self.raiz), "--ahora", "2026-11-07T08:30:00Z", "--semaforo")
        self.assertIn("¿Me puedo ausentar? ROJO", salida)
        self.assertIn("1. [ROJO]", salida)

    def test_el_atajo_dashboard_alertas_es_el_mismo_programa(self) -> None:
        import dashboard.alertas as atajo
        self.assertIs(atajo.main, P.main)


if __name__ == "__main__":
    unittest.main()
