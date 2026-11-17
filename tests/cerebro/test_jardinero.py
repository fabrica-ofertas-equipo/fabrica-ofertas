"""Jardinero del domingo en seco (B1-08): propone, no aplica; no toca lo protegido; solo escribe un archivo nuevo y solo con la confirmación del dueño."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from tests.cerebro._apoyo import AHORA, AHORA_TXT, RAIZ, Base, alta, cambio, comun, jardinero, jsonl, sin_escrituras

SCRIPT = Path(jardinero.__file__)
HOY = "2026-11-09"
DOC = """# Decisiones del dueño (2026-11-06)

## Decisiones tomadas

| # | Tema | Decisión | Consecuencia |
|---|---|---|---|
| **J1** | Encaje | Su ritmo. | S-A. |
| **J7** | Tienda y cobro | Landing propia más Stripe. | Se construye in-house. |

## Decisiones posteriores (2026-11-07)

| # | Tema | Decisión | Consecuencia |
|---|---|---|---|
| **J20** | Método de la landing | Diseñar en Impulstienda. | **Revierte parcialmente J7** (landing propia + Stripe in-house). |
"""


def dec(n: int, titulo: str, **extra) -> dict:
    return {"id": f"DEC-{n:04d}", "ts": "2026-11-07T21:28:28Z", "autor": "dueno", "tipo": "decision", "titulo": titulo, "detalle": f"detalle de {titulo}", "alcance": "sistema", "origen": "x",
            "vigente": True, "reemplaza": None, **extra}


class BaseJardin(Base):
    def p(self, **kw):
        return jardinero.proponer(self.raiz, AHORA, **kw)

    def tipos(self, r) -> list[str]:
        return [x["tipo"] for x in r["items"]]

    def items(self, r, tipo) -> list[dict]:
        return [x for x in r["items"] if x["tipo"] == tipo]


class PruebasLasPropuestas(BaseJardin):
    def test_memoria_vacia_no_propone_nada(self) -> None:
        r = self.p()
        self.assertEqual((r["items"], r["protegidos"]), ([], []))
        self.assertIn("Todo en orden", jardinero.a_texto(r))
        self.assertEqual(self.p(), r, "determinista")

    def test_duplicados_se_unen_dejando_el_mas_antiguo(self) -> None:
        self.poner("empresa/panel/pulido.jsonl", jsonl(
            alta(1, titulo="Elegir proveedor de correo transaccional", prioridad="P1", responsable="dueno", ts="2026-11-01T10:00:00Z"),
            alta(2, titulo="Elegir el proveedor de correo transaccional", prioridad="P1", responsable="dueno", ts="2026-11-02T10:00:00Z"),
            alta(3, titulo="Elegir proveedor de correo transaccional!", prioridad="P2", responsable="dueno", ts="2026-11-03T10:00:00Z"),
            alta(4, titulo="Algo completamente distinto sobre píxeles", prioridad="P2", responsable="dueno")))
        x = self.items(self.p(), "fusionar_duplicados")
        self.assertEqual(len(x), 1)
        self.assertEqual(x[0]["ids"], ["PUL-0001", "PUL-0002", "PUL-0003"])
        self.assertIn("Queda PUL-0001; se cierran PUL-0002, PUL-0003", x[0]["despues"])
        self.assertIn("#/cerebro", x[0]["como_aplicar"])
        self.assertTrue(x[0]["antes"] and x[0]["motivo"])

    def test_lo_ya_resuelto_no_cuenta_como_duplicado(self) -> None:
        self.poner("empresa/panel/pulido.jsonl", jsonl(alta(1, titulo="Elegir proveedor de correo", prioridad="P2", responsable="dueno"), alta(2, titulo="Elegir proveedor de correo", prioridad="P2", responsable="dueno"), cambio(2, "resuelta")))
        self.assertEqual(self.items(self.p(), "fusionar_duplicados"), [])

    def test_lo_protegido_nunca_se_propone_para_unir_ni_cerrar(self) -> None:
        self.poner("empresa/panel/pulido.jsonl", jsonl(
            alta(1, titulo="Fijar los límites de gasto", prioridad="P0", responsable="dueno"), alta(2, titulo="Fijar los límites de gasto", prioridad="P0", responsable="dueno"),
            alta(3, titulo="Respetar la línea roja de salud en los anuncios", prioridad="P2", responsable="dueno"), alta(4, titulo="Respetar la linea roja de salud en los anuncios", prioridad="P2", responsable="dueno"),
            alta(5, titulo="Revisar el veto del compliance sobre el claim", etapa="X1", prioridad="P2", responsable="dueno", ts="2026-01-01T10:00:00Z"),
            alta(6, titulo="Riesgo con el reembolso", categoria="riesgo", prioridad="P3", responsable="dueno", ts="2026-01-01T10:00:00Z"),
            alta(7, titulo="Idea vieja", prioridad="P3", responsable="dueno", ts="2026-01-01T10:00:00Z")))
        r = self.p()
        tocados = {i for x in r["items"] if x["tipo"] in ("fusionar_duplicados", "revisar_dormido", "cerrar_ya_resuelta") for i in x["ids"]}
        self.assertEqual(tocados, {"PUL-0007"}, "solo lo no protegido puede proponerse")
        protegidos = {p["id"] for p in r["protegidos"]}
        self.assertTrue({"PUL-0001", "PUL-0002", "PUL-0003", "PUL-0004", "PUL-0005", "PUL-0006"} <= protegidos, protegidos)
        self.assertTrue(all(p["motivo"] for p in r["protegidos"]))

    def test_vencidos_y_proximos_incluso_los_protegidos_se_avisan_pero_no_se_cierran(self) -> None:
        self.poner("empresa/panel/pulido.jsonl", jsonl(
            alta(1, titulo="Pagar el dominio", prioridad="P2", responsable="dueno", vence="2026-11-08"), alta(2, titulo="Firmar límites", prioridad="P0", responsable="dueno", vence="2026-11-01"),
            alta(3, titulo="Llamar al contador", prioridad="P1", responsable="dueno", vence="2026-11-12"), alta(4, titulo="Dentro de un mes", prioridad="P2", responsable="dueno", vence="2026-12-20"),
            alta(5, titulo="Ya vencido pero resuelto", prioridad="P2", vence="2026-11-01", estado="resuelta"), alta(6, titulo="Hoy mismo", prioridad="P2", vence="2026-11-09")))
        r = self.p()
        v = {x["ids"][0]: x for x in self.items(r, "vencido")}
        self.assertEqual(set(v), {"PUL-0001", "PUL-0002"})
        self.assertFalse(v["PUL-0001"]["protegido"])
        self.assertTrue(v["PUL-0002"]["protegido"])
        self.assertIn("solo tú decides", v["PUL-0002"]["como_aplicar"])
        self.assertEqual({x["ids"][0] for x in self.items(r, "proximo")}, {"PUL-0003", "PUL-0006"})
        self.assertEqual({x["ids"][0] for x in self.p(dias=60)["items"] if x["tipo"] == "proximo"}, {"PUL-0003", "PUL-0004", "PUL-0006"})

    def test_dormidos_segun_prioridad_y_sin_fecha(self) -> None:
        self.poner("empresa/panel/pulido.jsonl", jsonl(
            alta(1, titulo="Idea P3 vieja", prioridad="P3", responsable="dueno", ts="2026-07-01T10:00:00Z"), alta(2, titulo="Mejora P2 de hace cien días", prioridad="P2", responsable="dueno", ts="2026-07-31T10:00:00Z"),
            alta(3, titulo="Mejora P2 de hace un año", prioridad="P2", responsable="dueno", ts="2025-10-01T10:00:00Z"), alta(4, titulo="P1 de hace un año", prioridad="P1", responsable="dueno", ts="2025-10-01T10:00:00Z"),
            alta(5, titulo="Idea P3 con fecha", prioridad="P3", responsable="dueno", ts="2026-07-01T10:00:00Z", vence="2026-12-01"), alta(6, titulo="Idea P3 reciente", prioridad="P3", responsable="dueno")))
        self.assertEqual({x["ids"][0] for x in self.items(self.p(), "revisar_dormido")}, {"PUL-0001", "PUL-0003"})

    def test_sin_prioridad_o_sin_responsable(self) -> None:
        self.poner("empresa/panel/pulido.jsonl", jsonl(alta(1, titulo="Sin nada"), alta(2, titulo="Con todo", prioridad="P2", responsable="dueno"), alta(3, titulo="Falta responsable", prioridad="P2")))
        x = self.items(self.p(), "sin_prioridad")
        self.assertEqual(len(x), 1)
        self.assertEqual(x[0]["ids"], ["PUL-0001", "PUL-0003"])

    def test_decision_superada_se_detecta_en_la_memoria_y_en_el_documento(self) -> None:
        self.poner("docs/_historial/mentor-sistema/decisiones-del-dueno.md", DOC)
        self.poner("empresa/memoria/decisiones_dueno.jsonl", jsonl(dec(1, "J1 · Encaje"), dec(2, "J7 · Tienda y cobro"), dec(3, "J20 · Método de la landing", detalle="Diseñar en Impulstienda. Reemplaza lo de J1 para la landing.")))
        x = self.items(self.p(), "decision_superada")
        self.assertEqual({tuple(i["ids"]) for i in x}, {("DEC-0002",), ("DEC-0001",)}, "J20 revierte J7 (en el documento) y J20 reemplaza J1 (en la memoria)")
        j7 = [i for i in x if i["ids"] == ["DEC-0002"]][0]
        self.assertIn("Revierte parcialmente J7", " ".join(j7["antes"]))
        self.assertIn("reemplaza: DEC-0002", j7["como_aplicar"])
        self.assertIn("Tú decides", j7["como_aplicar"])

    def test_si_ya_esta_reemplazada_no_se_vuelve_a_proponer(self) -> None:
        self.poner("docs/_historial/mentor-sistema/decisiones-del-dueno.md", DOC)
        self.poner("empresa/memoria/decisiones_dueno.jsonl", jsonl(dec(1, "J1 · Encaje"), dec(2, "J7 · Tienda y cobro"), dec(3, "J20 · Método de la landing", reemplaza="DEC-0002")))
        self.assertEqual(self.items(self.p(), "decision_superada"), [])

    def test_cadena_rota(self) -> None:
        self.poner("empresa/memoria/decisiones_dueno.jsonl", jsonl(dec(1, "Una decisión"), dec(2, "Otra distinta", reemplaza="DEC-0099")))
        x = self.items(self.p(), "cadena_rota")
        self.assertEqual(x[0]["ids"], ["DEC-0002", "DEC-0099"])

    def test_decisiones_casi_iguales_se_proponen_como_reemplazo(self) -> None:
        self.poner("empresa/memoria/decisiones_dueno.jsonl", jsonl(dec(1, "Una baja al día sin venta"), dec(2, "Una baja al dia sin venta."), dec(3, "Algo muy distinto sobre idiomas y países")))
        x = self.items(self.p(), "fusionar_duplicados")
        self.assertEqual((len(x), x[0]["ids"]), (1, ["DEC-0001", "DEC-0002"]))
        self.assertIn("reemplaza: DEC-0001", x[0]["como_aplicar"])
        self.assertIn("no se editan ni se borran", x[0]["como_aplicar"])

    def test_lecciones_sin_prueba(self) -> None:
        self.poner("ofertas/_ejemplo/qa/d4.json", '{"ok": 1}')
        import hashlib
        h = hashlib.sha256((self.raiz / "ofertas/_ejemplo/qa/d4.json").read_bytes()).hexdigest()
        base = {"autor": "dueno", "tipo": "leccion", "leccion": "x", "etapa": "D4", "ts": "2026-11-08T10:00:00Z"}
        self.poner("empresa/memoria/lecciones.jsonl", jsonl(
            {"id": "LEC-0001", "titulo": "Con prueba buena", **base, "evidencia": [{"ruta": "ofertas/_ejemplo/qa/d4.json", "sha256": f"sha256:{h}"}]},
            {"id": "LEC-0002", "titulo": "Sin prueba", **base, "evidencia": []},
            {"id": "LEC-0003", "titulo": "Archivo desaparecido", **base, "evidencia": [{"ruta": "ofertas/_ejemplo/qa/no.json", "sha256": "sha256:" + "a" * 64}]},
            {"id": "LEC-0004", "titulo": "Archivo cambiado", **base, "evidencia": [{"ruta": "ofertas/_ejemplo/qa/d4.json", "sha256": "sha256:" + "b" * 64}]},
            {"id": "LEC-0005", "titulo": "Prueba fuera de la raíz", **base, "evidencia": [{"ruta": "../fuera.txt", "sha256": "sha256:" + "c" * 64}]}))
        x = {i["ids"][0]: i for i in self.items(self.p(), "leccion_sin_prueba")}
        self.assertEqual(set(x), {"LEC-0002", "LEC-0003", "LEC-0004", "LEC-0005"})
        self.assertIn("ningún archivo", x["LEC-0002"]["motivo"])
        self.assertIn("ya no existe", x["LEC-0003"]["motivo"])
        self.assertIn("cambió", x["LEC-0004"]["motivo"])

    def test_decisiones_del_documento_que_nunca_se_sembraron(self) -> None:
        self.poner("docs/_historial/mentor-sistema/decisiones-del-dueno.md", DOC)
        self.poner("empresa/memoria/decisiones_dueno.jsonl", jsonl(dec(1, "J1 · Encaje"), dec(2, "J7 · Tienda y cobro")))
        x = self.items(self.p(), "decision_sin_sembrar")
        self.assertEqual(x[0]["ids"], ["J20"])
        self.poner("empresa/memoria/decisiones_dueno.jsonl", jsonl(dec(1, "J1 · Encaje"), dec(2, "J7 · Tienda y cobro"), dec(3, "J20 · Método")))
        self.assertEqual(self.items(self.p(), "decision_sin_sembrar"), [])

    def test_si_el_documento_cambio_desde_la_siembra_se_avisa(self) -> None:
        self.poner("docs/_historial/mentor-sistema/decisiones-del-dueno.md", DOC)
        ev = [{"ruta": "docs/_historial/mentor-sistema/decisiones-del-dueno.md", "sha256": "sha256:" + "0" * 64}]
        self.poner("empresa/memoria/decisiones_dueno.jsonl", jsonl(dec(1, "J1 · Encaje", evidencia=ev), dec(2, "J7 · Tienda y cobro", evidencia=ev), dec(3, "J20 · Método", evidencia=ev)))
        x = self.items(self.p(), "decision_sin_sembrar")
        self.assertEqual(len(x), 1)
        self.assertIn("cambió desde", x[0]["motivo"])
        digest = comun.sha256_de(self.raiz, "docs/_historial/mentor-sistema/decisiones-del-dueno.md")
        ev_ok = [{"ruta": "docs/_historial/mentor-sistema/decisiones-del-dueno.md", "sha256": f"sha256:{digest}"}]
        self.poner("empresa/memoria/decisiones_dueno.jsonl", jsonl(dec(1, "J1 · Encaje", evidencia=ev_ok), dec(2, "J7 · Tienda y cobro", evidencia=ev_ok), dec(3, "J20 · Método", evidencia=ev_ok)))
        self.assertEqual(self.items(self.p(), "decision_sin_sembrar"), [])

    def test_preferencias_sin_resolver_y_ya_resueltas(self) -> None:
        pref = {"tipo": "regla_propuesta", "categoria": "pref", "responsable": "dueno", "prioridad": "P2"}
        self.poner("empresa/panel/pulido.jsonl", jsonl(
            alta(1, titulo="Fondos claros en los estáticos", ts="2026-10-01T10:00:00Z", **pref), alta(2, titulo="Titulares cortos en los anuncios", ts="2026-11-08T10:00:00Z", **pref),
            alta(3, titulo="Voz cálida en los correos", ts="2026-10-01T10:00:00Z", **pref)))
        self.poner("empresa/memoria/preferencias.jsonl", jsonl({"id": "PRF-0001", "ts": "2026-11-05T10:00:00Z", "autor": "dueno", "tipo": "preferencia", "estado": "aprobada", "pul_id": "PUL-0003",
                                                                "etapa": "D6", "criterio": "Voz cálida", "cita": "sí", "vigente": True}))
        r = self.p()
        self.assertEqual([x["ids"] for x in self.items(r, "preferencia_sin_resolver")], [["PUL-0001"]], "la de hace 39 días espera; la de ayer no")
        ya = self.items(r, "cerrar_ya_resuelta")
        self.assertEqual((len(ya), ya[0]["ids"]), (1, ["PUL-0003", "PRF-0001"]))

    def test_el_orden_es_estable_y_los_items_van_numerados(self) -> None:
        self.poner("empresa/panel/pulido.jsonl", jsonl(alta(1, titulo="Sin nada"), alta(2, titulo="Vencido", prioridad="P2", responsable="dueno", vence="2026-11-01"),
                                                         alta(3, titulo="Elegir proveedor de correo", prioridad="P2", responsable="dueno"), alta(4, titulo="Elegir proveedor de correo.", prioridad="P2", responsable="dueno")))
        r = self.p()
        self.assertEqual([x["n"] for x in r["items"]], list(range(1, len(r["items"]) + 1)))
        self.assertEqual(self.tipos(r), ["vencido", "fusionar_duplicados", "sin_prioridad"])


class PruebasNoAplicaNada(BaseJardin):
    def llenar(self) -> None:
        self.poner("empresa/panel/pulido.jsonl", jsonl(alta(1, titulo="Elegir proveedor de correo", prioridad="P2", responsable="dueno"), alta(2, titulo="Elegir proveedor de correo.", prioridad="P2", responsable="dueno"),
                                                         alta(3, titulo="Vencido", prioridad="P2", responsable="dueno", vence="2026-11-01")))
        self.poner("empresa/memoria/decisiones_dueno.jsonl", jsonl(dec(1, "Una baja al día sin venta"), dec(2, "Una baja al dia sin venta.")))

    def test_proponer_no_escribe_ni_cambia_nada(self) -> None:
        self.llenar()
        antes = self.arbol(self.raiz)
        with sin_escrituras() as eventos:
            r = self.p()
            jardinero.a_texto(r)
        self.assertEqual(eventos, [])
        self.assertEqual(self.arbol(self.raiz), antes)
        self.assertEqual(r["garantias"]["aplica_algo"], False)
        self.assertFalse((self.memoria / "jardin").exists())

    def test_por_linea_de_comandos_tampoco(self) -> None:
        self.llenar()
        antes = self.arbol(self.raiz)
        for args in ([], ["--json"], ["--dias", "30"]):
            r = self.correr(*args)
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.arbol(self.raiz), antes)

    def correr(self, *args: str):
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"}
        return subprocess.run([sys.executable, str(SCRIPT), "--raiz", str(self.raiz), "--ahora", AHORA_TXT, *args], capture_output=True, text=True, env=env, timeout=60)

    def test_texto_legible_para_decidir(self) -> None:
        self.llenar()
        t = jardinero.a_texto(self.p())
        for esperado in ("en seco: no cambié nada", "Tú decides cuáles hacer", "1. Pendiente vencido", "Antes:", "Después:", "Cómo:", "Unir duplicados"):
            self.assertIn(esperado, t)
        self.assertNotRegex(t, r"\b(tenés|querés|podés|mirá|hacé|vos)\b")

    def test_guardar_exige_la_confirmacion_del_dueno_en_los_dos_sentidos(self) -> None:
        self.llenar()
        antes = self.arbol(self.raiz)
        self.assertEqual(self.correr("--guardar-propuesta").returncode, 2)
        self.assertEqual(self.correr("--confirmo-dueno", "sí, guárdala").returncode, 2)
        self.assertEqual(self.correr("--guardar-propuesta", "--confirmo-dueno", "x").returncode, 6, "una sola letra no es una confirmación")
        self.assertEqual(self.correr("--guardar-propuesta", "--confirmo-dueno", "").returncode, 2)
        self.assertEqual(self.arbol(self.raiz), antes)
        with self.assertRaises(jardinero.ErrorGuardar):
            jardinero.guardar_propuesta(self.raiz, self.p(), "  ")
        self.assertEqual(self.arbol(self.raiz), antes)

    def test_guardar_escribe_un_solo_archivo_nuevo_y_nada_mas(self) -> None:
        self.llenar()
        antes = self.arbol(self.raiz)
        r = self.correr("--guardar-propuesta", "--confirmo-dueno", "sí, guárdala para el panel", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        despues = self.arbol(self.raiz)
        nuevos = sorted(set(despues) - set(antes))
        self.assertEqual(nuevos, ["empresa/memoria/jardin/2026-11-09.json"])
        self.assertTrue(all(despues[k] == antes[k] for k in antes), "ninguna línea de la memoria ni de la lista cambió")
        crudo = (self.raiz / nuevos[0]).read_bytes()
        self.assertTrue(crudo.isascii())
        d = json.loads(crudo)
        self.assertEqual((d["schema"], d["estado"], d["confirmada_por_dueno"]), ("jardin/1", "propuesta", "sí, guárdala para el panel"))
        self.assertEqual(json.loads(r.stdout)["guardada_en"], "empresa/memoria/jardin/2026-11-09.json")
        import hashlib
        self.assertEqual(d["sha256_items"], hashlib.sha256(json.dumps(d["items"], ensure_ascii=True, sort_keys=True).encode("ascii")).hexdigest())

    def test_nunca_sobrescribe_una_propuesta_existente(self) -> None:
        self.llenar()
        self.correr("--guardar-propuesta", "--confirmo-dueno", "sí")
        primero = (self.memoria / "jardin" / "2026-11-09.json").read_bytes()
        self.correr("--guardar-propuesta", "--confirmo-dueno", "otra vez")
        self.correr("--guardar-propuesta", "--confirmo-dueno", "y otra")
        self.assertEqual((self.memoria / "jardin" / "2026-11-09.json").read_bytes(), primero)
        self.assertEqual(sorted(p.name for p in (self.memoria / "jardin").iterdir()), ["2026-11-09-2.json", "2026-11-09-3.json", "2026-11-09.json"])

    def test_un_enlace_que_escapa_de_la_raiz_no_se_escribe(self) -> None:
        self.llenar()
        fuera = self.tmp / "fuera"
        fuera.mkdir()
        self.memoria.mkdir(exist_ok=True)
        os.symlink(fuera, self.memoria / "jardin")
        r = self.correr("--guardar-propuesta", "--confirmo-dueno", "sí")
        self.assertEqual(r.returncode, 6)
        self.assertEqual(list(fuera.iterdir()), [])

    def test_sin_carpeta_empresa_no_crea_nada(self) -> None:
        raiz = self.tmp / "vacia"
        raiz.mkdir()
        with self.assertRaises(jardinero.ErrorGuardar):
            jardinero.guardar_propuesta(raiz, jardinero.proponer(raiz, AHORA), "sí")
        self.assertEqual(list(raiz.iterdir()), [])

    def test_usos_invalidos(self) -> None:
        for args in (["--dias", "999"], ["--ahora", "ayer"], ["--no-existe"]):
            self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), "--raiz", str(self.raiz), *args], capture_output=True, text=True).returncode, 2, args)
        self.assertEqual(subprocess.run([sys.executable, str(SCRIPT), "--raiz", str(self.tmp / "no")], capture_output=True, text=True).returncode, 2)

    def test_el_codigo_no_tiene_ninguna_ruta_que_aplique(self) -> None:
        fuente = SCRIPT.read_text(encoding="utf-8")
        for prohibido in ("guardar_pendiente", "pulido.jsonl\", \"a", "os.remove", "os.unlink", "shutil", "subprocess", "os.rename", "O_APPEND", "eval(", "exec("):
            self.assertNotIn(prohibido, fuente, prohibido)
        self.assertEqual(fuente.count("os.open("), 1, "un único punto de escritura: el archivo nuevo de la propuesta")


class PruebasConLosDatosReales(unittest.TestCase):
    def test_en_seco_sobre_el_repositorio_real(self) -> None:
        with sin_escrituras() as eventos:
            r = jardinero.proponer(RAIZ, AHORA)
            texto = jardinero.a_texto(r)
        self.assertEqual(eventos, [])
        self.assertTrue(texto.startswith("JARDINERO"))
        tipos = set(jardinero.TITULOS)
        self.assertTrue({x["tipo"] for x in r["items"]} <= tipos)
        # lo protegido (los P0) nunca figura en una propuesta de unir, cerrar o dejar dormir
        memoria = comun.cargar_memoria(RAIZ)
        p0 = {e["id"] for e in memoria["pulido"] if e.get("prioridad") == "P0" and e.get("estado") != "resuelta"}
        tocados = {i for x in r["items"] if x["tipo"] in ("fusionar_duplicados", "revisar_dormido", "cerrar_ya_resuelta") for i in x["ids"]}
        self.assertEqual(p0 & tocados, set())


if __name__ == "__main__":
    unittest.main(verbosity=1)
