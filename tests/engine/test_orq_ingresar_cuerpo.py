"""Pruebas de ``engine.orq.ingresar_desde_cuerpo`` (``POST /ingresar``, docs/06 §4.7): el mismo ingreso que
``orq ingresar`` pero con el contenido en el cuerpo de la petición, y fallando CERRADO ante todo lo raro."""
from __future__ import annotations

import base64
import json
from pathlib import Path

import yaml

from engine import estado, orq
from engine.errores import ErrorValidacion, ParametroFaltante
from tests.engine import apoyo
from tests.engine.apoyo_orq import candidatos_ejemplo, escribir_arbol, pre_brief

_REL_D1 = "01-descubrimiento/candidatos.json"


def _b64(datos: bytes) -> str:
    return base64.b64encode(datos).decode("ascii")


class PruebaIngresarDesdeCuerpo(apoyo.PruebaBase):
    def setUp(self) -> None:
        super().setUp()
        self.emp = apoyo.crear_empresa(self.tmp, entorno="desarrollo", modo_infra="prueba")
        self.raiz = self.emp.raiz
        self.ahora = self.emp.reloj
        (self.raiz / "empresa" / "autonomia.yaml").unlink(missing_ok=True)
        self._n = 0
        self.contenido = json.dumps(candidatos_ejemplo(), ensure_ascii=False, sort_keys=True).encode("utf-8")

    # ---------------------------------------------------------------- ayudas
    def _con_parametro_ingesta(self, cuerpo_max_bytes: int | None = 1_000_000) -> None:
        ruta = self.raiz / "empresa" / "parametros.yaml"
        datos = yaml.safe_load(ruta.read_text(encoding="utf-8"))

        def entrada(valor, unidad):
            return {"valor": valor, "unidad": unidad, "hipotesis": True, "fuente": "prueba", "ultima_calibracion": None}

        datos["grupos"]["ingesta"] = {"tolerancia_seg": entrada(120, "segundos"), "cuerpo_max_bytes": entrada(cuerpo_max_bytes, "bytes"),
                                      "contexto_ttl_seg": entrada(3600, "segundos")}
        ruta.write_text(yaml.safe_dump(datos, sort_keys=False, allow_unicode=True), encoding="utf-8")

    def _crear(self) -> str:
        self._n += 1
        datos = pre_brief(nivel_autonomia="N4", slug=f"prueba-cuerpo-{self._n}")
        ruta = self.tmp / f"pre-brief-{self._n}.yaml"
        ruta.write_text(yaml.safe_dump(datos, sort_keys=False, allow_unicode=True), encoding="utf-8")
        return orq.crear(ruta_brief=ruta, raiz=self.raiz, ahora=self.ahora)["oferta_id"]

    def _cuerpo(self, oferta_id: str, *, etapa: str = "D1", archivos=None, **extra) -> bytes:
        if archivos is None:
            archivos = [{"ruta": _REL_D1, "contenido_b64": _b64(self.contenido)}]
        return json.dumps({"oferta_id": oferta_id, "etapa": etapa, "archivos": archivos, **extra}).encode("utf-8")

    def _ingresar(self, cuerpo: bytes | str) -> dict:
        return orq.ingresar_desde_cuerpo(cuerpo, raiz=self.raiz, ahora=self.ahora, env=self.emp.env)

    # ---------------------------------------------------------------- camino feliz y paridad
    def test_da_el_mismo_hash_salida_y_gate_que_ingresar_desde_una_carpeta(self) -> None:
        self._con_parametro_ingesta()
        por_carpeta_id, por_cuerpo_id = self._crear(), self._crear()
        desde = self.tmp / "desde"
        escribir_arbol(desde, archivos={_REL_D1: candidatos_ejemplo()})
        esperado = orq.ingresar(por_carpeta_id, "D1", desde=desde, raiz=self.raiz, ahora=self.ahora, env=self.emp.env)
        # Mismo contenido, mismos bytes: el cuerpo lleva los bytes que escribe ``escribir_arbol``.
        bytes_en_disco = (desde / _REL_D1).read_bytes()
        cuerpo = self._cuerpo(por_cuerpo_id, archivos=[{"ruta": _REL_D1, "contenido_b64": _b64(bytes_en_disco)}])
        obtenido = self._ingresar(cuerpo)
        self.assertEqual(esperado["hash_salida"], obtenido["hash_salida"])
        self.assertEqual((esperado["resultado"], esperado["version"]), (obtenido["resultado"], obtenido["version"]))
        self.assertEqual(estado.cargar(por_cuerpo_id, raiz=self.raiz)["etapas"]["D1"]["aprobado_por"]["tipo"], "humano")

    def test_acepta_texto_y_bytes_y_deja_el_staging_limpio(self) -> None:
        self._con_parametro_ingesta()
        oferta_id = self._crear()
        cuerpo = self._cuerpo(oferta_id)
        self._ingresar(cuerpo.decode("utf-8"))
        self.assertEqual("reutilizado", self._ingresar(cuerpo)["resultado"])
        restos = [p.name for p in (self.raiz / "ofertas" / oferta_id / ".staging").iterdir() if p.name.startswith("_ingreso-")]
        self.assertEqual([], restos)

    def test_el_temporal_se_borra_tambien_si_falla(self) -> None:
        self._con_parametro_ingesta()
        oferta_id = self._crear()
        # Archivo sellado de D1 pero contenido que no produce un hash válido: ingresar lanza y el temporal no debe quedar.
        cuerpo = self._cuerpo(oferta_id, archivos=[{"ruta": "01-descubrimiento/otro.json", "contenido_b64": _b64(b"{}")}])
        with self.assertRaises(ErrorValidacion):
            self._ingresar(cuerpo)
        staging = self.raiz / "ofertas" / oferta_id / ".staging"
        self.assertEqual([], [p.name for p in staging.iterdir() if p.name.startswith("_ingreso-")] if staging.exists() else [])

    # ---------------------------------------------------------------- parámetro y tamaño
    def test_sin_el_parametro_de_ingesta_falla_cerrado_con_parametro_faltante(self) -> None:
        oferta_id = self._crear()  # la raíz de prueba no trae el grupo opcional `ingesta`
        with self.assertRaises(ParametroFaltante):
            self._ingresar(self._cuerpo(oferta_id))

    def test_parametro_en_null_tambien_falla_cerrado(self) -> None:
        self._con_parametro_ingesta(cuerpo_max_bytes=None)
        oferta_id = self._crear()
        # El esquema de parámetros no admite null en este grupo: cargar_parametros falla cerrado (3); sin grupo, 5.
        with self.assertRaises((ParametroFaltante, ErrorValidacion)):
            self._ingresar(self._cuerpo(oferta_id))

    def test_cuerpo_sobre_el_maximo_se_rechaza_sin_escribir_nada(self) -> None:
        oferta_id = self._crear()
        cuerpo = self._cuerpo(oferta_id)
        self._con_parametro_ingesta(cuerpo_max_bytes=len(cuerpo) - 1)
        with self.assertRaises(ErrorValidacion):
            self._ingresar(cuerpo)
        self.assertFalse((self.raiz / "ofertas" / oferta_id / "01-descubrimiento").exists())

    def test_cuerpo_justo_en_el_maximo_pasa(self) -> None:
        oferta_id = self._crear()
        cuerpo = self._cuerpo(oferta_id)
        self._con_parametro_ingesta(cuerpo_max_bytes=len(cuerpo))
        self.assertEqual("aprobado", self._ingresar(cuerpo)["resultado"])

    # ---------------------------------------------------------------- forma del cuerpo
    def test_json_invalido_o_no_utf8(self) -> None:
        self._con_parametro_ingesta()
        for malo in (b"", b"{", b"\xff\xfe\x00", b"[]", b"5", b'"x"', b"null"):
            with self.subTest(malo=malo), self.assertRaises(ErrorValidacion):
                self._ingresar(malo)

    def test_claves_de_mas_o_de_menos(self) -> None:
        self._con_parametro_ingesta()
        oferta_id = self._crear()
        base = {"oferta_id": oferta_id, "etapa": "D1", "archivos": [{"ruta": _REL_D1, "contenido_b64": _b64(self.contenido)}]}
        for variante in ({**base, "extra": 1}, {k: v for k, v in base.items() if k != "etapa"}, {k: v for k, v in base.items() if k != "archivos"}):
            with self.subTest(claves=sorted(variante)), self.assertRaises(ErrorValidacion):
                self._ingresar(json.dumps(variante).encode())

    def test_oferta_y_etapa_invalidas(self) -> None:
        self._con_parametro_ingesta()
        oferta_id = self._crear()
        for oid, etapa in (("OF-1", "D1"), (None, "D1"), ("../x", "D1"), (oferta_id, "ZZ"), (oferta_id, None), (oferta_id, "")):
            with self.subTest(oid=oid, etapa=etapa), self.assertRaises(ErrorValidacion):
                self._ingresar(self._cuerpo(oid, etapa=etapa))

    def test_oferta_inexistente_no_crea_carpeta(self) -> None:
        self._con_parametro_ingesta()
        antes = sorted(p.name for p in (self.raiz / "ofertas").iterdir()) if (self.raiz / "ofertas").exists() else []
        with self.assertRaises(Exception) as cm:
            self._ingresar(self._cuerpo("OF-209912-99"))
        self.assertNotIsInstance(cm.exception, AttributeError)
        despues = sorted(p.name for p in (self.raiz / "ofertas").iterdir()) if (self.raiz / "ofertas").exists() else []
        self.assertEqual(antes, despues)

    # ---------------------------------------------------------------- rutas y base64: nada fuera de lo sellado
    def test_rutas_peligrosas_se_rechazan(self) -> None:
        self._con_parametro_ingesta()
        oferta_id = self._crear()
        malas = ["../escape.json", "/etc/passwd", "01-descubrimiento/../../x", "01-descubrimiento//candidatos.json", "./01-descubrimiento/candidatos.json",
                 "01-descubrimiento\\candidatos.json", "01-descubrimiento/candidatos.json\x00.png", "", "estado.json", "00-brief.yaml", "empresa/limites.yaml",
                 "01-descubrimiento/" + "a" * 300]
        for ruta in malas:
            with self.subTest(ruta=ruta), self.assertRaises(ErrorValidacion):
                self._ingresar(self._cuerpo(oferta_id, archivos=[{"ruta": ruta, "contenido_b64": _b64(b"{}")}]))
        # y no escribió nada fuera de la oferta
        self.assertFalse((self.raiz / "escape.json").exists())

    def test_rutas_repetidas_base64_invalido_y_items_mal_formados(self) -> None:
        self._con_parametro_ingesta()
        oferta_id = self._crear()
        ok = {"ruta": _REL_D1, "contenido_b64": _b64(self.contenido)}
        casos = {
            "repetida": [ok, ok],
            "b64 con basura": [{"ruta": _REL_D1, "contenido_b64": "###"}],
            "b64 con salto": [{"ruta": _REL_D1, "contenido_b64": _b64(self.contenido)[:10] + "\n" + _b64(self.contenido)[10:]}],
            "b64 no ascii": [{"ruta": _REL_D1, "contenido_b64": "ñandú"}],
            "sin clave": [{"ruta": _REL_D1}],
            "clave de más": [{**ok, "modo": "0777"}],
            "no es lista": {"ruta": _REL_D1},
            "lista vacía": [],
            "item no objeto": ["01-descubrimiento/candidatos.json"],
            "ruta no texto": [{"ruta": 5, "contenido_b64": _b64(b"{}")}],
        }
        for nombre, archivos in casos.items():
            with self.subTest(nombre), self.assertRaises(ErrorValidacion):
                self._ingresar(self._cuerpo(oferta_id, archivos=archivos))

    def test_un_symlink_previo_en_la_oferta_no_deja_escribir_fuera(self) -> None:
        self._con_parametro_ingesta()
        oferta_id = self._crear()
        fuera = self.tmp / "fuera"
        fuera.mkdir()
        staging = self.raiz / "ofertas" / oferta_id / ".staging"
        staging.mkdir(parents=True, exist_ok=True)
        # Aunque exista un enlace en .staging, el temporal es una carpeta nueva con nombre aleatorio.
        (staging / "D1").symlink_to(fuera)
        try:
            self._ingresar(self._cuerpo(oferta_id))
        except ErrorValidacion:
            pass
        self.assertEqual([], list(fuera.iterdir()), "no debe escribirse a través de un enlace")

    def test_los_bytes_no_pasan_por_ninguna_interpretacion(self) -> None:
        # El contenido llega y se promueve byte a byte: CRLF del cliente se conserva (el hash lo ve tal cual).
        self._con_parametro_ingesta()
        oferta_id = self._crear()
        crlf = json.dumps(candidatos_ejemplo(), ensure_ascii=False, indent=2).replace("\n", "\r\n").encode("utf-8")
        resultado = self._ingresar(self._cuerpo(oferta_id, archivos=[{"ruta": _REL_D1, "contenido_b64": _b64(crlf)}]))
        self.assertEqual((self.raiz / "ofertas" / oferta_id / _REL_D1).read_bytes(), crlf)
        self.assertTrue(resultado["hash_salida"].startswith("sha256:"))

    def test_un_json_ilegible_es_error_de_validacion_no_un_fallo_interno(self) -> None:
        # BOM, UTF-8 roto o JSON truncado en un artefacto: dato inválido (3), nunca una excepción sin tipo (1).
        self._con_parametro_ingesta()
        oferta_id = self._crear()
        for malo in (b"\xef\xbb\xbf" + self.contenido, b"\xff\xfe{}", self.contenido[:20], b""):
            with self.subTest(malo=malo[:12]), self.assertRaises(ErrorValidacion):
                self._ingresar(self._cuerpo(oferta_id, archivos=[{"ruta": _REL_D1, "contenido_b64": _b64(malo)}]))
        self.assertFalse((self.raiz / "ofertas" / oferta_id / _REL_D1).exists(), "nada se promueve si el contenido es ilegible")


if __name__ == "__main__":
    import unittest

    unittest.main()
