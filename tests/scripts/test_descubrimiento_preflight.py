"""Pruebas de `scripts.modelado.preflight_descubrir`: freno de PAUSA, freno de captura, infra y límites
para la operación "descubrir" (interfaces d1-v2 §0 n.10, §8.2 n.3, §6.4).

Reusa, solo por LECTURA, los fixtures ya probados de `tests/fixtures/engine/empresa_prueba/` (otro
dueño: no se editan) para `limites.yaml` y `parametros.yaml`; `infra/estado.json` lo arma esta prueba
con `modo="vivo"` (el fixture de engine usa `modo="prueba"`, que este preflight no acepta).

Defecto D1d n.1 (medido contra el código real de D1c): `comprobar_descubrir` bloqueaba TODO con el
freno de captura puesto, aunque el barrido por el conector (`ads_library_search`) no usa Chrome. Las
pruebas marcadas "(defecto D1d n.1)" sembraban el comportamiento viejo (freno bloqueaba siempre, sin
`via`); ahora `via` es obligatoria y el freno solo aplica a `via="captura_web"`.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from engine.errores import ErrorBloqueado, ErrorLimite, ErrorUso
from scripts.modelado import preflight_descubrir as P

RAIZ = Path(__file__).resolve().parents[2]
FIXTURE_ENGINE = RAIZ / "tests" / "fixtures" / "engine" / "empresa_prueba"
AHORA = datetime(2026, 11, 9, 7, 0, 0, tzinfo=timezone.utc)  # 1 h después del fixture de infra


def _ahora() -> datetime:
    return AHORA


class _Raiz:
    """Arma una raíz temporal con limites.yaml/parametros.yaml de engine (solo lectura, copiados) +
    infra/estado.json propio en modo vivo."""

    def __enter__(self) -> Path:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        empresa = base / "empresa"
        empresa.mkdir()
        shutil.copy(FIXTURE_ENGINE / "limites.yaml", empresa / "limites.yaml")
        shutil.copy(FIXTURE_ENGINE / "parametros.yaml", empresa / "parametros.yaml")
        (empresa / "infra").mkdir()
        (empresa / "infra" / "estado.json").write_text(json.dumps(self._estado_vivo()), encoding="utf-8")
        self.base = base
        return base

    def __exit__(self, *exc) -> None:
        self._tmp.cleanup()

    @staticmethod
    def _estado_vivo() -> dict:
        return {
            "schema_version": "1.1.0", "modo": "vivo", "semaforo": "VERDE",
            "generado_en": "2026-11-09T06:30:00Z", "valido_hasta": "2026-11-09T12:00:00Z",
            "commit": "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
            "hash_scripts": "sha256:" + "a" * 64,
            "items": [
                {"id": "M-02", "bloque": "meta", "critico": True, "estado": "VERDE", "mensaje": "fixture",
                 "evidencia_ruta": "empresa/infra/healthcheck/x.json", "medido_en": "2026-11-09T06:30:00Z",
                 "expira_en": "2026-11-10T06:30:00Z", "latencia_ms": 0},
            ],
            "firma": "hmac-sha256:" + "b" * 64,
        }


class PruebaComprobarDescubrir(unittest.TestCase):
    def test_todo_en_orden_devuelve_ok_via_conector(self) -> None:
        with _Raiz() as raiz:
            r = P.comprobar_descubrir(raiz, ahora=_ahora, via="conector")
        self.assertTrue(r["ok"])
        self.assertEqual(r["via"], "conector")
        self.assertFalse(r["freno_aplica"])
        self.assertEqual(r["infra_generado_en"], "2026-11-09T06:30:00Z")

    def test_todo_en_orden_devuelve_ok_via_captura_web(self) -> None:
        with _Raiz() as raiz:
            r = P.comprobar_descubrir(raiz, ahora=_ahora, via="captura_web")
        self.assertTrue(r["ok"])
        self.assertTrue(r["freno_aplica"])

    def test_via_ausente_es_error_de_tipo(self) -> None:
        """`via` no tiene valor por defecto (interfaces §6.4, decisión de S-A): llamarla sin `via` es un
        error de programación, no un caso de negocio."""
        with _Raiz() as raiz:
            with self.assertRaises(TypeError):
                P.comprobar_descubrir(raiz, ahora=_ahora)  # type: ignore[call-arg]

    def test_via_invalida_sale_con_2(self) -> None:
        with _Raiz() as raiz:
            with self.assertRaises(ErrorUso) as cm:
                P.comprobar_descubrir(raiz, ahora=_ahora, via="chrome")
            self.assertEqual(cm.exception.codigo_salida, 2)

    def test_pausa_bloquea_con_4(self) -> None:
        with _Raiz() as raiz:
            (raiz / "empresa" / "PAUSA").write_text("", encoding="utf-8")
            with self.assertRaises(ErrorBloqueado) as cm:
                P.comprobar_descubrir(raiz, ahora=_ahora, via="conector")
            self.assertEqual(cm.exception.codigo_salida, 4)

    def test_freno_de_captura_bloquea_via_captura_web_con_4(self) -> None:
        """Defecto D1d n.1: antes el freno bloqueaba TODO, incluido el barrido por el conector."""
        with _Raiz() as raiz:
            (raiz / "empresa" / "captura").mkdir()
            (raiz / "empresa" / "captura" / "freno.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(ErrorBloqueado) as cm:
                P.comprobar_descubrir(raiz, ahora=_ahora, via="captura_web")
            self.assertEqual(cm.exception.codigo_salida, 4)

    def test_freno_de_captura_no_bloquea_via_conector_si_lo_demas_esta_verde(self) -> None:
        """Caso inverso del defecto D1d n.1: el freno (HTTP 403 a Chrome) no usa el conector."""
        with _Raiz() as raiz:
            (raiz / "empresa" / "captura").mkdir()
            (raiz / "empresa" / "captura" / "freno.json").write_text("{}", encoding="utf-8")
            r = P.comprobar_descubrir(raiz, ahora=_ahora, via="conector")
            self.assertTrue(r["ok"])
            self.assertFalse(r["freno_aplica"])

    def test_freno_de_captura_via_conector_pero_con_pausa_sigue_bloqueando(self) -> None:
        """El freno no aplica a `via="conector"`, pero PAUSA sí: no es una vía libre de todo candado."""
        with _Raiz() as raiz:
            (raiz / "empresa" / "captura").mkdir()
            (raiz / "empresa" / "captura" / "freno.json").write_text("{}", encoding="utf-8")
            (raiz / "empresa" / "PAUSA").write_text("", encoding="utf-8")
            with self.assertRaises(ErrorBloqueado) as cm:
                P.comprobar_descubrir(raiz, ahora=_ahora, via="conector")
            self.assertEqual(cm.exception.codigo_salida, 4)

    def test_sin_infra_estado_bloquea_con_4(self) -> None:
        with _Raiz() as raiz:
            (raiz / "empresa" / "infra" / "estado.json").unlink()
            with self.assertRaises(ErrorBloqueado):
                P.comprobar_descubrir(raiz, ahora=_ahora, via="conector")

    def test_infra_en_modo_prueba_no_vivo_bloquea(self) -> None:
        with _Raiz() as raiz:
            estado = json.loads((raiz / "empresa" / "infra" / "estado.json").read_text(encoding="utf-8"))
            estado["modo"] = "prueba"
            (raiz / "empresa" / "infra" / "estado.json").write_text(json.dumps(estado), encoding="utf-8")
            with self.assertRaises(ErrorBloqueado):
                P.comprobar_descubrir(raiz, ahora=_ahora, via="conector")

    def test_infra_vencida_mas_de_6h_bloquea(self) -> None:
        with _Raiz() as raiz:
            tarde = lambda: datetime(2026, 11, 9, 13, 0, 0, tzinfo=timezone.utc)  # > 6 h de generado_en
            with self.assertRaises(ErrorBloqueado):
                P.comprobar_descubrir(raiz, ahora=tarde, via="conector")

    def test_limites_sin_sello_es_archivo_invalido(self) -> None:
        """Sin el objeto `sello` el archivo ni siquiera cumple `limites.schema.json` (campo obligatorio);
        `cargar_limites` lo rechaza como dato inválido (3), antes de llegar a `exigir_operacion` (5)."""
        from engine.errores import ErrorValidacion

        with _Raiz() as raiz:
            import yaml

            lim = yaml.safe_load((raiz / "empresa" / "limites.yaml").read_text(encoding="utf-8"))
            del lim["sello"]
            (raiz / "empresa" / "limites.yaml").write_text(yaml.safe_dump(lim), encoding="utf-8")
            with self.assertRaises(ErrorValidacion) as cm:
                P.comprobar_descubrir(raiz, ahora=_ahora, via="conector")
            self.assertEqual(cm.exception.codigo_salida, 3)

    def test_limites_con_max_costo_por_barrido_en_null_sale_con_5(self) -> None:
        with _Raiz() as raiz:
            import yaml

            ruta = raiz / "empresa" / "limites.yaml"
            lim = yaml.safe_load(ruta.read_text(encoding="utf-8"))
            lim["max_costo_por_barrido"] = None  # el sello queda desactualizado a propósito: también falla cerrado
            ruta.write_text(yaml.safe_dump(lim), encoding="utf-8")
            with self.assertRaises(ErrorLimite) as cm:
                P.comprobar_descubrir(raiz, ahora=_ahora, via="conector")
            self.assertEqual(cm.exception.codigo_salida, 5)


class PruebaCli(unittest.TestCase):
    def test_cli_verde_sale_0(self) -> None:
        import contextlib
        import io

        with _Raiz() as raiz:
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                codigo = P.main(["--raiz", str(raiz), "--via", "conector", "--ahora", "2026-11-09T07:00:00Z", "--json"])
            self.assertEqual(codigo, 0, buf.getvalue())
            self.assertTrue(json.loads(buf.getvalue())["ok"])

    def test_cli_con_pausa_sale_4(self) -> None:
        import contextlib
        import io

        with _Raiz() as raiz:
            (raiz / "empresa" / "PAUSA").write_text("", encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                codigo = P.main(["--raiz", str(raiz), "--via", "conector", "--ahora", "2026-11-09T07:00:00Z"])
            self.assertEqual(codigo, 4)

    def test_cli_sin_via_sale_con_2_argparse(self) -> None:
        import contextlib
        import io

        with _Raiz() as raiz:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                codigo = P.main(["--raiz", str(raiz), "--ahora", "2026-11-09T07:00:00Z"])
            self.assertEqual(codigo, 2)


if __name__ == "__main__":
    unittest.main()
