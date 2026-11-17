"""Pruebas de limpiar_oferta.py: qué se conserva y qué se borra de una oferta cerrada (regla del dueño, 15-nov)."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

RUTA = Path(__file__).resolve().parents[2] / ".claude/skills/escalar-oferta/scripts/limpiar_oferta.py"
spec = importlib.util.spec_from_file_location("limpiar_oferta", RUTA)
LO = importlib.util.module_from_spec(spec)
spec.loader.exec_module(LO)
GRANDE = 2_000_000


class TestConservar(unittest.TestCase):
    def test_reglas(self):
        c = LO.conservar
        P = Path
        self.assertTrue(c(P("estado.md"), GRANDE))
        self.assertTrue(c(P("05-landing/hero.png"), GRANDE))                      # fuera de producto/creativos
        self.assertTrue(c(P("04-producto/final/kit.pdf"), 50_000_000))            # PDF siempre
        self.assertTrue(c(P("06-creativos/videos/F01.mp4"), GRANDE))              # anuncio final
        self.assertTrue(c(P("06-creativos/videos-r3/R3-02.mp4"), GRANDE))
        self.assertTrue(c(P("06-creativos/hoja-contacto-F01.jpg"), GRANDE))
        self.assertTrue(c(P("06-creativos/keyframes/mini.png"), 100_000))        # chico
        self.assertTrue(c(P("06-creativos/guiones.json"), GRANDE))
        self.assertTrue(c(P("04-producto/entregable.zip"), GRANDE))
        self.assertFalse(c(P("06-creativos/videos/descartes/F01-v1.mp4"), GRANDE))
        self.assertFalse(c(P("06-creativos/keyframes/P1a.png"), GRANDE))
        self.assertFalse(c(P("06-creativos/audio/F01.wav"), GRANDE))
        self.assertFalse(c(P("06-creativos/subida-r3/F01.mp4"), GRANDE))
        self.assertFalse(c(P("04-producto/planas-r6/p012.png"), GRANDE))
        self.assertFalse(c(P("06-creativos/scripts/__pycache__/x.pyc"), 10))

    def test_plan_en_carpeta(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            for rel, tam in [("06-creativos/videos/F01.mp4", GRANDE), ("06-creativos/clips/c1.mp4", GRANDE),
                             ("04-producto/kit.pdf", GRANDE), ("06-creativos/audio/a.wav", GRANDE)]:
                p = raiz / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b"0" * tam)
            borrar = sorted(str(p.relative_to(raiz)) for p, _ in LO.plan_carpeta(raiz))
            self.assertEqual(borrar, ["06-creativos/audio/a.wav", "06-creativos/clips/c1.mp4"])


if __name__ == "__main__":
    unittest.main()
