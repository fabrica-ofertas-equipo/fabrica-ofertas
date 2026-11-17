"""``compliance.sellar``/``compliance.verificar``: sello solo con lint sin ROJO y QA PASS; sello
vencido o alterado se rechaza (docs/06 N09, §4.5; B0-13 contribución de B6).

``verificar_sello(clave_sello, ahora)`` es la firma congelada que esperan ``meta.activar`` y
``landing.desplegar`` (ver «Pedidos» de sus README): nunca lanza, devuelve ``None`` ante cualquier
problema.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from engine import comun
from engine.errores import ErrorBloqueado

from compliance.hallazgos import Hallazgo
from compliance.lint_claims import ResultadoLint
from compliance.reglas import cargar_reglas
from compliance.sellar import VAR_CLAVE_HMAC_PRUEBA, _firmar_hmac, ruta_sello, sellar
from compliance.verificar import verificar_sello, verificar_sello_o_fallar

from tests.compliance.apoyo import PruebaBase

CLAVE_PRUEBA = b"clave-de-prueba-x1-no-real"
AHORA = datetime(2026, 11, 10, 8, 0, 0, tzinfo=timezone.utc)
RELOJ = lambda: AHORA  # noqa: E731


def _firmar(datos: bytes) -> str:
    return _firmar_hmac(datos, CLAVE_PRUEBA)


def _dictamen(veredicto: str = "PASS") -> dict:
    return {"veredicto": veredicto}


def _lint(semaforo: str = "verde") -> ResultadoLint:
    reglas_version = cargar_reglas().reglas_version
    hallazgos = () if semaforo == "verde" else (
        Hallazgo(patron_clave="salud:x", nivel="rojo", categoria="salud", descripcion="d", evidencia="e"),
    )
    return ResultadoLint(reglas_version=reglas_version, semaforo=semaforo, hallazgos=hallazgos)


class PruebaSellarPrecondiciones(PruebaBase):
    def test_no_sella_con_lint_rojo(self) -> None:
        with self.assertRaises(ErrorBloqueado):
            sellar(oferta_id="OF-202611-01", etapa_objetivo="D3", artefacto_sha256="sha256:" + "ab" * 32,
                  dictamen=_dictamen("PASS"), dictamen_ref="qa.json", dictamen_sha256="sha256:" + "cd" * 32,
                  lint=_lint("rojo"), vigencia_dias=30, ahora=RELOJ, firmar=_firmar)

    def test_no_sella_sin_qa_pass(self) -> None:
        with self.assertRaises(ErrorBloqueado):
            sellar(oferta_id="OF-202611-01", etapa_objetivo="D3", artefacto_sha256="sha256:" + "ab" * 32,
                  dictamen=_dictamen("FAIL"), dictamen_ref="qa.json", dictamen_sha256="sha256:" + "cd" * 32,
                  lint=_lint("verde"), vigencia_dias=30, ahora=RELOJ, firmar=_firmar)

    def test_sella_con_pass_con_notas(self) -> None:
        sello = sellar(oferta_id="OF-202611-01", etapa_objetivo="D3", artefacto_sha256="sha256:" + "ab" * 32,
                       dictamen=_dictamen("PASS_CON_NOTAS"), dictamen_ref="qa.json", dictamen_sha256="sha256:" + "cd" * 32,
                       lint=_lint("verde"), vigencia_dias=30, ahora=RELOJ, firmar=_firmar)
        self.assertEqual(sello["oferta_id"], "OF-202611-01")

    def test_sella_con_amarillo_no_rojo(self) -> None:
        lint_amarillo = ResultadoLint(reglas_version=cargar_reglas().reglas_version, semaforo="amarillo", hallazgos=(
            Hallazgo(patron_clave="general:x", nivel="amarillo", categoria="general", descripcion="d", evidencia="e"),
        ))
        sello = sellar(oferta_id="OF-202611-01", etapa_objetivo="D3", artefacto_sha256="sha256:" + "ab" * 32,
                       dictamen=_dictamen("PASS"), dictamen_ref="qa.json", dictamen_sha256="sha256:" + "cd" * 32,
                       lint=lint_amarillo, vigencia_dias=30, ahora=RELOJ, firmar=_firmar)
        self.assertEqual(sello["reglas_version"], lint_amarillo.reglas_version)


class PruebaVerificarSelloContratoCongelado(PruebaBase):
    """``verificar_sello(clave_sello, ahora) -> dict | None``: la firma que esperan B4/B5."""

    def setUp(self) -> None:
        super().setUp()
        self.raiz = self.tmp
        (self.raiz / "empresa" / "compliance" / "sellos").mkdir(parents=True)
        self.artefacto_sha256 = "sha256:" + "11" * 32
        self.env = {"FABRICA_ENTORNO": "prueba", VAR_CLAVE_HMAC_PRUEBA: CLAVE_PRUEBA.decode("utf-8")}

    def _sellar_y_escribir(self, **cambios) -> Path:
        base = dict(oferta_id="OF-202611-01", etapa_objetivo="D7", artefacto_sha256=self.artefacto_sha256,
                    dictamen=_dictamen("PASS"), dictamen_ref="qa/x1-d7-v1.json", dictamen_sha256="sha256:" + "22" * 32,
                    lint=_lint("verde"), vigencia_dias=1, object_ids=["120000000000001", "120000000000002", "120000000000003"], ahora=RELOJ, firmar=_firmar)
        base.update(cambios)
        sello = sellar(**base)
        destino = ruta_sello(self.artefacto_sha256, raiz=self.raiz)
        comun.escribir_atomico(destino, comun.json_canonico(sello) + b"\n")
        return destino

    def test_sello_vigente_se_devuelve(self) -> None:
        self._sellar_y_escribir()
        sello = verificar_sello(self.artefacto_sha256, AHORA, raiz=self.raiz, env=self.env)
        self.assertIsNotNone(sello)
        self.assertEqual(sello["artefacto_sha256"], self.artefacto_sha256)

    def test_clave_que_no_existe_da_none(self) -> None:
        self.assertIsNone(verificar_sello("sha256:" + "00" * 32, AHORA, raiz=self.raiz, env=self.env))

    def test_sello_vencido_da_none(self) -> None:
        self._sellar_y_escribir(vigencia_dias=1)
        despues_de_vencer = AHORA + timedelta(days=2)
        self.assertIsNone(verificar_sello(self.artefacto_sha256, despues_de_vencer, raiz=self.raiz, env=self.env))

    def test_artefacto_alterado_despues_de_sellar_da_none(self) -> None:
        """El artefacto cambió: el hash con el que se BUSCA ya no es el que el sello declara."""
        destino = self._sellar_y_escribir()
        sello = json.loads(destino.read_text(encoding="utf-8"))
        self.assertNotEqual(sello["artefacto_sha256"], "sha256:" + "99" * 32)
        self.assertIsNone(verificar_sello("sha256:" + "99" * 32, AHORA, raiz=self.raiz, env=self.env))

    def test_firma_alterada_da_none(self) -> None:
        destino = self._sellar_y_escribir()
        sello = json.loads(destino.read_text(encoding="utf-8"))
        sello["firma"] = sello["firma"][:-4] + "0000"
        destino.write_text(json.dumps(sello), encoding="utf-8")
        self.assertIsNone(verificar_sello(self.artefacto_sha256, AHORA, raiz=self.raiz, env=self.env))

    def test_contenido_alterado_sin_resellar_da_none(self) -> None:
        """Cambiar cualquier campo del sello (p. ej. ``object_ids``) invalida la firma sobre el resto."""
        destino = self._sellar_y_escribir()
        sello = json.loads(destino.read_text(encoding="utf-8"))
        sello["object_ids"] = ["120000000000001", "120000000000002", "120000000000003", "120000000000004"]
        destino.write_text(json.dumps(sello), encoding="utf-8")
        self.assertIsNone(verificar_sello(self.artefacto_sha256, AHORA, raiz=self.raiz, env=self.env))

    def test_sin_clave_para_contrastar_pasa_solo_por_formato_fuera_de_produccion(self) -> None:
        """``problemas_firma`` (CT, reusada tal cual) solo CONTRASTA el HMAC si tiene la clave; sin
        ella, fuera de producción, acepta por forma (documentado: HMAC es para pruebas/servicio a
        servicio, y producción exige Ed25519 de todos modos — ver test siguiente)."""
        self._sellar_y_escribir()
        env_sin_clave = {"FABRICA_ENTORNO": "prueba"}
        self.assertIsNotNone(verificar_sello(self.artefacto_sha256, AHORA, raiz=self.raiz, env=env_sin_clave))

    def test_en_produccion_una_firma_hmac_no_basta(self) -> None:
        """Convenciones §5: en producción las aprobaciones son Ed25519; HMAC solo prueba/servicio."""
        self._sellar_y_escribir()
        env_produccion = {"FABRICA_ENTORNO": "produccion", VAR_CLAVE_HMAC_PRUEBA: CLAVE_PRUEBA.decode("utf-8")}
        self.assertIsNone(verificar_sello(self.artefacto_sha256, AHORA, raiz=self.raiz, env=env_produccion))

    def test_jamas_lanza_ante_un_json_corrupto(self) -> None:
        destino = ruta_sello(self.artefacto_sha256, raiz=self.raiz)
        comun.escribir_atomico(destino, b"{no es json")
        self.assertIsNone(verificar_sello(self.artefacto_sha256, AHORA, raiz=self.raiz, env=self.env))


class PruebaVerificarSelloOFallarCLIyToctou(PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.raiz = self.tmp
        (self.raiz / "empresa" / "compliance" / "sellos").mkdir(parents=True)
        self.artefacto_sha256 = "sha256:" + "33" * 32
        self.env = {"FABRICA_ENTORNO": "prueba", VAR_CLAVE_HMAC_PRUEBA: CLAVE_PRUEBA.decode("utf-8")}
        sello = sellar(oferta_id="OF-202611-01", etapa_objetivo="D7", artefacto_sha256=self.artefacto_sha256,
                       dictamen=_dictamen("PASS"), dictamen_ref="qa/x1-d7-v1.json", dictamen_sha256="sha256:" + "44" * 32,
                       lint=_lint("verde"), vigencia_dias=1, object_ids=["120000000000010", "120000000000020"], ahora=RELOJ, firmar=_firmar)
        comun.escribir_atomico(ruta_sello(self.artefacto_sha256, raiz=self.raiz), comun.json_canonico(sello) + b"\n")

    def test_falla_con_hash_distinto_al_de_activacion(self) -> None:
        with self.assertRaises(ErrorBloqueado):
            verificar_sello_o_fallar(self.artefacto_sha256, AHORA, raiz=self.raiz, env=self.env,
                                     artefacto_sha256="sha256:" + "ff" * 32)

    def test_falla_con_object_ids_de_mas(self) -> None:
        with self.assertRaises(ErrorBloqueado):
            verificar_sello_o_fallar(self.artefacto_sha256, AHORA, raiz=self.raiz, env=self.env,
                                     object_ids=["120000000000010", "120000000000020", "120000000000030"])

    def test_acepta_el_caso_correcto(self) -> None:
        sello = verificar_sello_o_fallar(self.artefacto_sha256, AHORA, raiz=self.raiz, env=self.env,
                                         artefacto_sha256=self.artefacto_sha256, object_ids=["120000000000010", "120000000000020"])
        self.assertEqual(sello["artefacto_sha256"], self.artefacto_sha256)

    def test_sin_sello_falla(self) -> None:
        with self.assertRaises(ErrorBloqueado):
            verificar_sello_o_fallar("sha256:" + "00" * 32, AHORA, raiz=self.raiz, env=self.env)


class PruebaEd25519RealEnProduccion(PruebaBase):
    """Camino completo con Ed25519 real (``ssh-keygen -Y``), el único que vale en producción."""

    def setUp(self) -> None:
        super().setUp()
        try:
            from tests.engine.apoyo import par_de_claves
        except Exception as exc:  # pragma: no cover - entorno sin ssh-keygen
            self.skipTest(f"ssh-keygen no disponible: {exc}")
        self.claves = par_de_claves("x1-prueba")
        self.raiz = self.tmp
        (self.raiz / "empresa" / "compliance" / "sellos").mkdir(parents=True)
        self.artefacto_sha256 = "sha256:" + "55" * 32

    def _firmar_ed25519(self, datos: bytes) -> str:
        return comun.firmar_ed25519(datos, self.claves.privada)

    def _escribir_sello(self) -> Path:
        sello = sellar(oferta_id="OF-202611-01", etapa_objetivo="D7", artefacto_sha256=self.artefacto_sha256,
                       dictamen=_dictamen("PASS"), dictamen_ref="qa/x1-d7-v1.json", dictamen_sha256="sha256:" + "66" * 32,
                       lint=_lint("verde"), vigencia_dias=1, object_ids=["120000000000001"], ahora=RELOJ,
                       firmar=self._firmar_ed25519)
        destino = ruta_sello(self.artefacto_sha256, raiz=self.raiz)
        comun.escribir_atomico(destino, comun.json_canonico(sello) + b"\n")
        return destino

    def test_ed25519_valida_en_produccion_con_la_clave_publica_correcta(self) -> None:
        self._escribir_sello()
        env = {"FABRICA_ENTORNO": "produccion", "FABRICA_FIRMA_PUBLICA": self.claves.publica}
        sello = verificar_sello(self.artefacto_sha256, AHORA, raiz=self.raiz, env=env)
        self.assertIsNotNone(sello)

    def test_ed25519_con_clave_publica_equivocada_no_verifica(self) -> None:
        from tests.engine.apoyo import par_de_claves

        self._escribir_sello()
        otra = par_de_claves("x1-otra")
        env = {"FABRICA_ENTORNO": "produccion", "FABRICA_FIRMA_PUBLICA": otra.publica}
        self.assertIsNone(verificar_sello(self.artefacto_sha256, AHORA, raiz=self.raiz, env=env))

    def test_ed25519_sin_clave_publica_configurada_bloquea_en_produccion(self) -> None:
        self._escribir_sello()
        env = {"FABRICA_ENTORNO": "produccion"}
        self.assertIsNone(verificar_sello(self.artefacto_sha256, AHORA, raiz=self.raiz, env=env))


if __name__ == "__main__":
    import unittest

    unittest.main()
