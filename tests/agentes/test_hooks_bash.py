"""Pruebas de ``agentes.hooks.pretooluse_bash`` (crítica M12, docs/09 §14.5b)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agentes.hooks import pretooluse_bash as hook


class PruebaPretoolUseBash(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()
        parche = mock.patch("socket.socket", side_effect=AssertionError("prueba sin red"))
        parche.start()
        self.addCleanup(parche.stop)
        self._tmp = tempfile.TemporaryDirectory(prefix="hook-bash-")
        self.addCleanup(self._tmp.cleanup)
        self.raiz = Path(self._tmp.name)
        (self.raiz / "ofertas" / "OF-202611-01").mkdir(parents=True)

    def _env(self, **extra: str) -> dict[str, str]:
        base = {"AGENT_RAIZ": str(self.raiz), "AGENT_OFERTA_ID": "OF-202611-01"}
        base.update(extra)
        return base

    def _manejar(self, comando: str, env: dict) -> str | None:
        with mock.patch.dict(os.environ, env, clear=True):
            return hook.manejar({"tool_name": "Bash", "tool_input": {"command": comando}})

    def test_herramienta_distinta_de_bash_no_opina(self) -> None:
        with mock.patch.dict(os.environ, self._env(), clear=True):
            self.assertIsNone(hook.manejar({"tool_name": "Read", "tool_input": {"file_path": "/x"}}))

    def test_script_desconocido_no_opina_aqui(self) -> None:
        """Un comando sin ningún script de la lista blanca lo evalúa pretooluse_gasto, no este hook."""
        motivo = self._manejar("ls -la", self._env())
        self.assertIsNone(motivo)

    def test_ruta_dentro_de_la_oferta_pasa(self) -> None:
        ruta = self.raiz / "ofertas" / "OF-202611-01" / "02-validacion" / "validacion.json"
        ruta.parent.mkdir(parents=True)
        ruta.write_text("{}", encoding="utf-8")
        motivo = self._manejar(f"python3 scripts/validar_esquemas.py oferta ofertas/OF-202611-01", self._env())
        self.assertIsNone(motivo)

    def test_flag_fuera_de_lista_blanca_deniega(self) -> None:
        motivo = self._manejar("python3 scripts/validar_esquemas.py --forzar", self._env())
        self.assertIsNotNone(motivo)

    def test_punto_y_coma_deniega(self) -> None:
        motivo = self._manejar("python3 scripts/validar_esquemas.py oferta ofertas/_ejemplo; echo hola", self._env())
        self.assertIsNotNone(motivo)

    def test_subshell_deniega(self) -> None:
        motivo = self._manejar("python3 scripts/validar_esquemas.py $(cat /etc/passwd)", self._env())
        self.assertIsNotNone(motivo)

    def test_ruta_absoluta_fuera_de_la_oferta_deniega(self) -> None:
        motivo = self._manejar("python3 scripts/validar_esquemas.py oferta /etc/passwd", self._env())
        self.assertIsNotNone(motivo)

    def test_traversal_relativo_deniega(self) -> None:
        motivo = self._manejar("python3 scripts/validar_esquemas.py oferta ../../empresa/limites.yaml", self._env())
        self.assertIsNotNone(motivo)

    def test_sin_agent_oferta_id_con_ruta_deniega(self) -> None:
        motivo = self._manejar("python3 scripts/lint_claims.py --archivo ofertas/OF-202611-01/x.json",
                               {"AGENT_RAIZ": str(self.raiz)})
        self.assertIsNotNone(motivo)


if __name__ == "__main__":
    unittest.main()


class PruebaFormaModuloYRutasDeLectura(PruebaPretoolUseBash):
    """SB-4: ``python -m <modulo>`` se comprueba igual que ``scripts/<x>.py``; ``--parametros``/``--limites`` pueden leer
    SOLO ``empresa/parametros.yaml``/``empresa/limites.yaml``; el resto de rutas sigue sujeto a ``ofertas/<id>/``."""

    def test_forma_modulo_comprueba_las_banderas(self) -> None:
        self.assertIsNone(self._manejar("python -m scripts.nivel_riesgo --P P1 --C C1 --E E0 --N N1 --json", self._env()))
        motivo = self._manejar("python -m scripts.nivel_riesgo --live", self._env())
        self.assertIn("flag no permitido", motivo)

    def test_forma_modulo_comprueba_las_rutas(self) -> None:
        motivo = self._manejar("python -m scripts.nivel_riesgo --suite /etc/passwd", self._env())
        self.assertIn("fuera de AGENT_RAIZ", motivo)
        ok = self._manejar("python -m scripts.nivel_riesgo --suite ofertas/OF-202611-01/casos.yaml", self._env())
        self.assertIsNone(ok)

    def test_la_forma_modulo_no_se_confunde_con_otros_argumentos(self) -> None:
        # «scripts.nivel_riesgo» como texto suelto (no tras -m) no activa el script ni lo desactiva.
        self.assertIsNone(self._manejar("echo scripts.nivel_riesgo", self._env()))

    def test_factibilidad_lee_parametros_y_limites_de_empresa_y_nada_mas(self) -> None:
        base = "python -m engine.factibilidad calcular --entradas ofertas/OF-202611-01/03-oferta/entradas.json "
        self.assertIsNone(self._manejar(base + "--parametros empresa/parametros.yaml --limites empresa/limites.yaml", self._env()))
        self.assertIn("fuera de AGENT_RAIZ", self._manejar(base + "--parametros empresa/otro.yaml", self._env()))
        self.assertIn("fuera de AGENT_RAIZ", self._manejar(base + "--parametros ../../empresa/parametros.yaml", self._env()))
        self.assertIn("fuera de AGENT_RAIZ", self._manejar(base + "--parametros /etc/passwd", self._env()))

    def test_la_excepcion_de_lectura_vale_solo_para_su_bandera(self) -> None:
        # empresa/parametros.yaml como valor de OTRA bandera (--entradas) NO está permitido.
        motivo = self._manejar("python -m engine.factibilidad calcular --entradas empresa/parametros.yaml", self._env())
        self.assertIn("fuera de AGENT_RAIZ", motivo)

    def test_la_excepcion_no_se_arrastra_a_un_argumento_posterior(self) -> None:
        motivo = self._manejar("python -m engine.factibilidad calcular --parametros empresa/parametros.yaml empresa/limites.yaml", self._env())
        self.assertIn("fuera de AGENT_RAIZ", motivo)
