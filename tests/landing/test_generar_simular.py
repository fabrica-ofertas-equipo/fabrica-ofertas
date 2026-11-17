"""``python -m landing.generar --simular`` (alias ``--dry-run``): no escribe nada y reporta lo que generaría.

El árbol queda idéntico tras simular (medido por hash de toda la raíz); el plan coincide, archivo por archivo
(tamaño y sha256), con lo que escribe una ejecución real; una entrada inválida sale con 3 sin tocar el disco.

Comando: ``.venv/bin/python -m unittest tests.landing.test_generar_simular``
"""
from __future__ import annotations

import io
import json
import shutil
import socket
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from landing import generar as G
from scripts import validar_esquemas as V

RAIZ = Path(__file__).resolve().parents[2]
FIX = RAIZ / "tests" / "fixtures" / "landing"
OFERTAS = {"es": ("oferta_es_dinero", "OF-202611-01"), "pl": ("oferta_pl_relaciones", "OF-202611-02")}


def _sin_red(*_a, **_k):  # pragma: no cover
    raise AssertionError("las pruebas de landing no abren sockets")


def _hash_arbol(raiz: Path) -> str:
    """Hash de TODOS los archivos de la raíz (nombres y bytes), sin interpretar nada."""
    import hashlib
    h = hashlib.sha256()
    for p in sorted(raiz.rglob("*")):
        h.update(str(p.relative_to(raiz)).encode())
        if p.is_file():
            h.update(p.read_bytes())
    return h.hexdigest()


class PruebaSimular(unittest.TestCase):
    def setUp(self) -> None:
        patcher = mock.patch.object(socket, "socket", _sin_red)
        patcher.start()
        self.addCleanup(patcher.stop)

    def preparar(self, clave: str) -> tuple[Path, Path, str]:
        tmp = Path(tempfile.mkdtemp(prefix="landing-simular-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        carpeta, oid = OFERTAS[clave]
        shutil.copytree(FIX / carpeta, tmp / "ofertas" / oid)
        shutil.copytree(FIX / "empresa", tmp / "empresa")
        return tmp, tmp / "ofertas" / oid, oid

    def cli(self, tmp: Path, oid: str, *extra: str) -> tuple[int, dict | str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            codigo = G.main(["--oferta", oid, "--raiz", str(tmp), *extra])
        texto = out.getvalue()
        return codigo, (json.loads(texto) if "--json" in extra else texto), err.getvalue()

    def test_el_arbol_queda_identico_tras_simular(self) -> None:
        for clave in OFERTAS:
            with self.subTest(clave):
                tmp, d, oid = self.preparar(clave)
                antes = _hash_arbol(tmp)
                codigo, salida, _ = self.cli(tmp, oid, "--simular", "--json")
                self.assertEqual(0, codigo)
                self.assertEqual(antes, _hash_arbol(tmp))
                self.assertFalse((d / "05-landing" / "sitio").exists())

    def test_dry_run_es_alias_de_simular(self) -> None:
        tmp, d, oid = self.preparar("es")
        antes = _hash_arbol(tmp)
        c1, a, _ = self.cli(tmp, oid, "--simular", "--json")
        c2, b, _ = self.cli(tmp, oid, "--dry-run", "--json")
        self.assertEqual((0, 0), (c1, c2))
        self.assertEqual(a, b)
        self.assertEqual(antes, _hash_arbol(tmp))

    def test_el_json_trae_archivos_con_tamano_y_sha256_y_avisos(self) -> None:
        tmp, d, oid = self.preparar("pl")
        codigo, salida, _ = self.cli(tmp, oid, "--simular", "--json")
        self.assertEqual(0, codigo)
        self.assertEqual("simulacion", salida["modo"])
        self.assertTrue(salida["ok"] and salida["datos"]["simulacion"])
        detalle = salida["datos"]["detalle"]
        self.assertEqual(salida["datos"]["archivos"], [x["ruta"] for x in detalle])
        self.assertEqual(sum(x["bytes"] for x in detalle), salida["datos"]["total_bytes"])
        for x in detalle:
            self.assertRegex(x["sha256"], r"^sha256:[0-9a-f]{64}$")
            self.assertGreater(x["bytes"], 0)
        rutas = {x["ruta"] for x in detalle}
        self.assertTrue({"sitio/index.html", "sitio/comprar.html", "sitio/gracias.html", "sitio/desistimiento.html", "sitio/css/estilos.css",
                         "sitio/js/consentimiento.js", "sitio/js/pixel.js", "sitio/imagenes/muestra-principal.svg", "sitio/imagenes/og.png"} <= rutas)
        self.assertTrue(any("S01: la ranura del hero no está aprobada" in a for a in salida["avisos"]))      # ranura sin imagen

    def test_el_plan_coincide_con_lo_que_escribe_una_ejecucion_real(self) -> None:
        for clave in OFERTAS:
            with self.subTest(clave):
                tmp, d, oid = self.preparar(clave)
                _, plan, _ = self.cli(tmp, oid, "--simular", "--json")
                previos = {p.relative_to(d / "05-landing").as_posix() for p in (d / "05-landing").rglob("*") if p.is_file()}
                codigo, _, _ = self.cli(tmp, oid, "--json")
                self.assertEqual(0, codigo)
                nuevos = {p.relative_to(d / "05-landing").as_posix(): p for p in (d / "05-landing").rglob("*") if p.is_file()}
                escritos = {rel for rel in nuevos if rel not in previos or rel.startswith("sitio/")}
                self.assertEqual({x["ruta"] for x in plan["datos"]["detalle"]}, escritos & {x["ruta"] for x in plan["datos"]["detalle"]})
                for x in plan["datos"]["detalle"]:
                    real = nuevos[x["ruta"]].read_bytes()
                    self.assertEqual(x["bytes"], len(real), x["ruta"])
                    self.assertEqual(x["sha256"], V.hash_bytes(real), x["ruta"])

    def test_por_defecto_sigue_escribiendo(self) -> None:
        tmp, d, oid = self.preparar("es")
        codigo, salida, _ = self.cli(tmp, oid, "--json")
        self.assertEqual(0, codigo)
        self.assertEqual("dry_run", salida["modo"])               # valor histórico del campo
        self.assertTrue((d / "05-landing" / "sitio" / "index.html").is_file())
        self.assertNotIn("detalle", salida["datos"])

    def test_entrada_invalida_sale_3_y_no_escribe(self) -> None:
        tmp, d, oid = self.preparar("es")
        ruta = d / "05-landing" / "copy.json"
        copy = json.loads(ruta.read_text(encoding="utf-8"))
        copy["secciones"]["S01"]["h1"] = "Titular <script>alert(1)</script>"
        ruta.write_text(json.dumps(copy, ensure_ascii=False), encoding="utf-8")
        antes = _hash_arbol(tmp)
        for bandera in ("--simular", "--dry-run"):
            codigo, _, err = self.cli(tmp, oid, bandera, "--json")
            self.assertEqual(3, codigo)
            self.assertIn("marcado HTML", err)
            self.assertEqual(antes, _hash_arbol(tmp))

    def test_paleta_con_contraste_insuficiente_sale_3_al_simular(self) -> None:
        tmp, d, oid = self.preparar("es")
        ruta = d / "05-landing" / "paleta.json"
        paleta = json.loads(ruta.read_text(encoding="utf-8"))
        paleta["colores"]["texto_sobre_claro"]["hex"] = "#B8C4C8"
        ruta.write_text(json.dumps(paleta, ensure_ascii=False), encoding="utf-8")
        codigo, _, err = self.cli(tmp, oid, "--simular")
        self.assertEqual(3, codigo)
        self.assertIn("contraste", err)

    def test_simular_el_sitio_minimo_lista_marcadores_y_rutas_si_faltan(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="landing-simular-min-"))
        self.addCleanup(shutil.rmtree, tmp, True)
        d = tmp / "ofertas" / "OF-209901-01"
        shutil.copytree(FIX / "oferta_minima", d)
        antes = _hash_arbol(tmp)
        codigo, salida, _ = self.cli(tmp, "OF-209901-01", "--simular", "--json")
        self.assertEqual(0, codigo)
        rutas = {x["ruta"] for x in salida["datos"]["detalle"]}
        self.assertTrue({"rutas.json", "imagenes/hero-placeholder.png", "sitio/index.html"} <= rutas)
        self.assertTrue(any("faltan" in a for a in salida["avisos"]))
        self.assertEqual(antes, _hash_arbol(tmp))

    def test_salida_de_texto_lista_los_archivos(self) -> None:
        tmp, d, oid = self.preparar("es")
        codigo, texto, _ = self.cli(tmp, oid, "--simular")
        self.assertEqual(0, codigo)
        self.assertIn("simulación (no se escribió nada)", texto)
        self.assertIn("sitio/index.html", texto)


if __name__ == "__main__":
    unittest.main()
