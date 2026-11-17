"""Pedidos de P3 al backend: archivo de skills, registro propio de la oferta demo y ``motor_disponible``."""
from __future__ import annotations

import json
import os
import unittest
from urllib.parse import quote

from scripts.validar_esquemas import hash_objeto
from tests.dashboard.test_servidor_apoyo import HOSTIL, OFERTA, PruebaBase


def cadena_demo(ejecuciones: list[str]) -> str:
    lineas, prev = [], None
    for k, ejec in enumerate(ejecuciones):
        linea = {"schema_version": "1.0.0", "ts": f"2026-11-06T0{k}:00:00Z", "ejecucion_id": ejec, "oferta_id": "OF-202611-01", "etapa": "D1",
                 "agente": "d1-maker", "evento": "accion", "herramienta": "WebSearch", "entrada_resumen": f"demo {k}",
                 "resultado": {"estado": "ok", "codigo": 0}, "costo_estimado": {"monto": 10, "moneda": "EUR"}, "tokens": None,
                 "modo": "dry_run", "hash_previo": prev}
        linea["hash"] = hash_objeto(linea, excluir=("hash",))
        prev = linea["hash"]
        lineas.append(linea)
    return "".join(json.dumps(x) + "\n" for x in lineas)


class PruebaSkillArchivo(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.escribir(".claude/skills/f9-demo/SKILL.md", f"---\nname: f9-demo\n---\n# Demo\n\n{HOSTIL}\n")
        self.escribir(".claude/skills/f9-demo/references/glosario.md", "# glosario\n")
        self.escribir(".claude/skills/f9-demo/imagen.png", b"\x89PNG\r\n")
        self.escribir(".claude/agents/f9-maker.md", "# maker\n")
        self.escribir(".claude/agents/f9-qa.md", "# qa\n")
        self.escribir(".claude/agents/README.md", "# readme de agentes\n")
        self.escribir(".claude/agents/otro-agente.md", "no es maker ni qa\n")
        self.escribir(".claude/settings.json", '{"permissions": "no debe salir"}')

    def leer(self, slug: str, ruta: str | None, **kw):
        consulta = "" if ruta is None else f"ruta={quote(ruta, safe='')}"
        return self.cliente().get(f"/api/skills/{slug}/archivo", consulta=consulta, **kw)

    def test_lee_skill_md_con_la_forma_del_archivo_de_oferta(self) -> None:
        r = self.leer("f9-demo", "SKILL.md")
        self.assertEqual(r.estado, 200)
        d = r.datos
        self.assertEqual(set(d), {"ruta", "tipo", "contenido", "truncado", "bytes", "mtime"})
        self.assertEqual((d["ruta"], d["tipo"], d["truncado"]), ("SKILL.md", "md", False))
        self.assertIn(HOSTIL, d["contenido"], "texto con HTML y U+202E intacto")
        self.assertEqual(r.json()["fuente"], [".claude/skills/f9-demo/SKILL.md"])
        self.assertFalse(r.json()["vacio"])
        self.assertEqual(self.leer("f9-demo", "references/glosario.md").datos["contenido"], "# glosario\n")

    def test_agentes_maker_y_qa_pero_nada_mas_de_esa_carpeta(self) -> None:
        r = self.leer("f9-demo", "agentes/f9-maker.md")
        self.assertEqual(r.datos["contenido"], "# maker\n")
        self.assertEqual(r.datos["ruta"], "agentes/f9-maker.md")
        self.assertEqual(r.json()["fuente"], [".claude/agents/f9-maker.md"])
        self.assertEqual(self.leer("f9-demo", "agentes/f9-qa.md").estado, 200)
        for ruta in ("agentes/README.md", "agentes/otro-agente.md", "agentes/../settings.json", "agentes/../skills/f9-demo/SKILL.md",
                     "agentes/", "agentes/f9-maker.md/../README.md", "agentes/.env"):
            r = self.leer("f9-demo", ruta)
            self.assertEqual(r.estado, 403, ruta)
            self.assertNotIn("readme de agentes", r.cuerpo.decode())
        self.assertTrue(self.leer("f9-demo", "agentes/f9-zzz-maker.md").json()["vacio"], "agente ausente: vacío, no error")

    def test_rutas_hostiles(self) -> None:
        for ruta in ("../../../empresa/limites.yaml", "../SKILL.md", "/etc/passwd", "~/x", "..", ".env", "a\\b", "x\x00y", "../../settings.json"):
            r = self.leer("f9-demo", ruta)
            self.assertEqual(r.estado, 403, repr(ruta))
            self.assertNotIn("no debe salir", r.cuerpo.decode())
            self.assertNotIn(str(self.raiz), r.cuerpo.decode())
        fuera = self.tmp / "fuera"
        fuera.mkdir()
        (fuera / "s.md").write_text("secreto fuera")
        os.symlink(fuera / "s.md", self.raiz / ".claude" / "skills" / "f9-demo" / "enlace.md")
        os.symlink(fuera, self.raiz / ".claude" / "skills" / "f9-demo" / "carpeta")
        os.symlink(fuera, self.raiz / ".claude" / "skills" / "f9-robada")
        for slug, ruta in (("f9-demo", "enlace.md"), ("f9-demo", "carpeta/s.md"), ("f9-robada", "s.md")):
            r = self.leer(slug, ruta)
            self.assertEqual(r.estado, 403, (slug, ruta))
            self.assertNotIn("secreto fuera", r.cuerpo.decode())
        self.escribir(".claude/skills/f9-demo/secretos.md", "s")
        self.assertEqual(self.leer("f9-demo", "secretos.md").estado, 403)

    def test_errores_de_forma(self) -> None:
        self.assertEqual(self.leer("MALO_SLUG", "SKILL.md").json()["error"]["codigo"], "skill_invalida")
        self.assertEqual(self.leer("../x", "SKILL.md").estado, 404)
        self.assertEqual(self.leer("no-existe", "SKILL.md").json()["error"]["codigo"], "skill_no_encontrada")
        self.assertEqual(self.leer("f9-demo", None).json()["error"]["codigo"], "ruta_requerida")
        self.assertEqual(self.leer("f9-demo", "references").json()["error"]["codigo"], "no_es_archivo")
        self.assertEqual(self.leer("f9-demo", "imagen.png").json()["error"]["codigo"], "solo_texto")
        self.escribir(".claude/skills/f9-demo/binario.txt", bytes(range(256)) * 8)
        self.assertEqual(self.leer("f9-demo", "binario.txt").json()["error"]["codigo"], "archivo_binario")
        ausente = self.leer("f9-demo", "NO-EXISTE.md").json()
        self.assertTrue(ausente["vacio"])
        self.assertEqual(ausente["fuente"], [".claude/skills/f9-demo/NO-EXISTE.md"])

    def test_tope_de_400_kb_y_token(self) -> None:
        self.escribir(".claude/skills/f9-demo/grande.md", "a" * (400 * 1024 + 7))
        d = self.leer("f9-demo", "grande.md").datos
        self.assertEqual((len(d["contenido"]), d["truncado"], d["bytes"]), (400 * 1024, True, 400 * 1024 + 7))
        self.assertEqual(self.leer("f9-demo", "SKILL.md", token=False).estado, 403)


class PruebaRegistroDeLaDemo(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.poner_registro()  # empresa/registro.jsonl REAL: 6 líneas de OF-202611-77, ejecuciones RUN-20261106-01/02
        self.escribir("ofertas/_ejemplo/_empresa/registro.jsonl", cadena_demo(["DEMO-0000000001", "DEMO-0000000001", "DEMO-0000000002"]))
        self.escribir("ofertas/_ejemplo/_empresa/costos.jsonl", json.dumps(
            {"schema_version": "1.0.0", "ts": "2026-11-06T00:00:00Z", "oferta_id": "OF-202611-01", "etapa": "D1",
             "ejecucion_id": "DEMO-0000000001", "origen": "ia", "concepto": "x", "monto": {"monto": 77, "moneda": "EUR"}}) + "\n")

    def test_la_demo_lee_su_registro_propio_sin_mezclar(self) -> None:
        c = self.cliente()
        demo = c.get("/api/registro", consulta="oferta=_ejemplo").json()
        self.assertTrue(demo["demo"])
        self.assertEqual(demo["fuente"], ["ofertas/_ejemplo/_empresa/registro.jsonl"])
        self.assertEqual(demo["datos"]["total"], 3)
        self.assertEqual({x["oferta_id"] for x in demo["datos"]["lineas"]}, {"OF-202611-01"}, "ninguna línea del registro real")
        self.assertTrue(demo["datos"]["cadena_ok"])
        self.assertTrue(any("DEMOSTRACIÓN" in a for a in demo["avisos"]))
        real = c.get("/api/registro").json()
        self.assertFalse(real["demo"])
        self.assertEqual(real["fuente"], ["empresa/registro.jsonl"])
        self.assertEqual(real["datos"]["total"], 6)
        self.assertNotIn("OF-202611-01", {x["oferta_id"] for x in real["datos"]["lineas"]})
        self.assertEqual(c.get("/api/registro", consulta="oferta=OF-202611-01").datos["lineas"], [], "el filtro por id real no trae la demo")
        self.assertEqual(len(c.get("/api/registro", consulta=f"oferta={OFERTA}").datos["lineas"]), 6)
        filtrado = c.get("/api/registro", consulta="oferta=_ejemplo&etapa=D9").datos
        self.assertEqual(filtrado["lineas"], [])

    def test_agentes_de_la_demo(self) -> None:
        c = self.cliente()
        demo = c.get("/api/agentes", consulta="oferta=_ejemplo").json()
        self.assertEqual([f["ejecucion_id"] for f in demo["datos"]], ["DEMO-0000000002", "DEMO-0000000001"])
        self.assertEqual(demo["fuente"][0], "ofertas/_ejemplo/_empresa/registro.jsonl")
        self.assertTrue(demo["demo"])
        f1 = next(f for f in demo["datos"] if f["ejecucion_id"] == "DEMO-0000000001")
        self.assertEqual((f1["eventos"], f1["costo"]), (2, {"monto": 77, "moneda": "EUR"}))
        real = c.get("/api/agentes").json()
        self.assertFalse(real["demo"])
        self.assertEqual({f["ejecucion_id"] for f in real["datos"]}, {"RUN-20261106-01", "RUN-20261106-02"})
        det = c.get("/api/agentes/DEMO-0000000001", consulta="oferta=_ejemplo")
        self.assertEqual(len(det.datos["eventos"]), 2)
        self.assertEqual(c.get("/api/agentes/DEMO-0000000001").estado, 404, "sin oferta=_ejemplo se busca solo en el registro real")

    def test_demo_sin_registro_propio_queda_vacia_aunque_haya_registro_real(self) -> None:
        os.remove(self.raiz / "ofertas" / "_ejemplo" / "_empresa" / "registro.jsonl")
        j = self.cliente().get("/api/registro", consulta="oferta=_ejemplo").json()
        self.assertTrue(j["vacio"])
        self.assertEqual(j["datos"]["lineas"], [])
        self.assertEqual(j["fuente"], ["ofertas/_ejemplo/_empresa/registro.jsonl"])
        self.assertEqual(self.cliente().get("/api/agentes", consulta="oferta=_ejemplo").json()["vacio"], True)

    def test_hostil_en_oferta_no_sale_de_la_raiz(self) -> None:
        c = self.cliente()
        for valor in ("_../../empresa", "_/../../x", "..", "_%2e%2e"):
            r = c.get("/api/registro", consulta=f"oferta={quote(valor, safe='')}")
            self.assertEqual(r.estado, 200)
            self.assertEqual(r.datos["lineas"], [], valor)


class PruebaMotorDisponible(PruebaBase):
    def test_sistema_y_oferta_informan_si_existe_engine_orq(self) -> None:
        c = self.cliente()
        self.assertIs(c.get("/api/sistema").datos["motor_disponible"], False)
        d = c.get(f"/api/oferta/{OFERTA}").datos
        self.assertIs(d["motor_disponible"], False)
        self.assertIs(d["proximo_paso"]["motor_disponible"], False)
        self.escribir("engine/orq.py", "# motor\n")
        self.assertIs(c.get("/api/sistema").datos["motor_disponible"], True)
        d = c.get(f"/api/oferta/{OFERTA}").datos
        self.assertIs(d["motor_disponible"], True)
        self.assertIs(d["proximo_paso"]["motor_disponible"], True)

    def test_oferta_sin_estado_tambien_lo_informa(self) -> None:
        d = self.cliente().get("/api/oferta/OF-202611-79").datos
        self.assertIs(d["motor_disponible"], False)
        self.assertIs(d["proximo_paso"]["motor_disponible"], False)
        self.assertEqual(d["proximo_paso"]["tipo"], "sin_estado")

    def test_una_carpeta_engine_orq_no_cuenta(self) -> None:
        (self.raiz / "engine" / "orq.py").mkdir(parents=True)
        self.assertIs(self.cliente().get("/api/sistema").datos["motor_disponible"], False)


if __name__ == "__main__":
    unittest.main()
