"""CT-3, lote B, sub-lote B1 (interfaces entre componentes ya construidos): B-01 (`catalogo` 1.0.0, B0-09) y B-13 (`alertas` 1.0.0).
Backlog: ``docs/_historial/ct3-backlog.md`` §4.2. Sin red; solo lectura del repositorio y copias en memoria o temporales."""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import validar_esquemas as V

RAIZ = Path(__file__).resolve().parents[2]
EJ = RAIZ / "ofertas" / "_ejemplo"
CLAVE = V.CLAVE_DE_PRUEBA


def _sin_red(caso: unittest.TestCase) -> None:
    original = socket.socket

    def bloqueado(*a, **k):
        raise AssertionError("las pruebas no pueden abrir sockets")

    socket.socket = bloqueado  # type: ignore[assignment]
    caso.addCleanup(setattr, socket, "socket", original)


def ejemplo(nombre: str) -> dict:
    return json.loads((V.DIR_EJEMPLOS / nombre).read_text(encoding="utf-8"))


def firmado(cat: dict, clave: bytes = CLAVE) -> dict:
    cat = {k: v for k, v in cat.items() if k != "firma"}
    cat["firma"] = V.firma_hmac(V.payload_firma("catalogo", cat), clave)
    return cat


def contexto(datos: dict, clave_catalogo: bytes | None = CLAVE) -> V.Contexto:
    inf = V.Informe("prueba")
    return V.Contexto(EJ, datos, None, None, None, V.cargar_gates(), inf, None, None, clave_catalogo)


def codigos_regla(cat: dict, *, checkout: dict | None = None, ids: dict | None = None, clave: bytes | None = CLAVE) -> list[str]:
    datos = {"05-landing/catalogo.json": cat, "05-landing/checkout.json": checkout if checkout is not None else V.cargar_json(EJ / "05-landing/checkout.json")}
    if ids is not None:
        datos["07-campana/ids_meta.json"] = ids
    c = contexto(datos, clave)
    V.regla_catalogo(c)
    return [h.codigo for h in c.informe.errores]


# ----------------------------------------------------------------------------------------------------------------------------
# B-01 · catalogo 1.0.0
# ----------------------------------------------------------------------------------------------------------------------------
class PruebaCatalogoEsquema(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)
        _, self.esq = V.cargar_esquemas()
        self.cat = ejemplo("catalogo.valido.json")

    def test_version_y_campos(self) -> None:
        e = self.esq["catalogo"]
        self.assertEqual("1.0.0", e["x-version"])
        self.assertFalse(e["additionalProperties"])
        self.assertEqual({"schema_version", "oferta_id", "version", "moneda", "price_ids", "ids_meta", "generado_en", "firma"}, set(e["required"]))
        self.assertEqual({"campaign_id", "adset_ids", "ad_ids"}, set(e["properties"]["ids_meta"]["properties"]))

    def test_ids_meta_usa_los_nombres_de_ids_meta_schema(self) -> None:
        """Crítica C-11: `campaign_id` escalar, `adset_ids[]`, `ad_ids[]`: los mismos nombres que `ids_meta.schema.json` y que lee el Worker."""
        im = self.esq["ids_meta"]["properties"]
        for k in ("campaign_id", "adset_ids", "ad_ids"):
            self.assertIn(k, im)
        self.assertEqual([], V.errores_de_esquema("catalogo", self.cat))

    def test_ejemplo_valido_firma_con_la_clave_de_prueba_y_sin_la_de_otro(self) -> None:
        self.assertEqual([], V.problemas_artefacto("catalogo", self.cat, clave=CLAVE, entorno="prueba"))
        mal = V.problemas_artefacto("catalogo", self.cat, clave=b"otra-clave", entorno="prueba")
        self.assertEqual(["X40_FIRMA"], [c for c, _ in mal])

    def test_el_ejemplo_coincide_con_el_checkout_y_los_ids_de_los_ejemplos(self) -> None:
        self.assertEqual([], codigos_regla(self.cat, ids=ejemplo("ids_meta.valido.json")))

    def test_sin_ids_meta_json_el_catalogo_va_vacio(self) -> None:
        vacio = firmado({**self.cat, "ids_meta": {"campaign_id": None, "adset_ids": [], "ad_ids": []}})
        self.assertEqual([], V.errores_de_esquema("catalogo", vacio))
        self.assertEqual([], codigos_regla(vacio))                      # lo que emite landing.catalogo antes de meta.crear
        self.assertEqual(["X48_CATALOGO"], codigos_regla(self.cat))   # ids firmados sin 07-campana/ids_meta.json

    def test_campana_null_exige_listas_vacias_y_campana_con_id_exige_listas_llenas(self) -> None:
        a = copy.deepcopy(self.cat); a["ids_meta"]["campaign_id"] = None
        self.assertTrue(V.errores_de_esquema("catalogo", a))
        b = copy.deepcopy(self.cat); b["ids_meta"]["adset_ids"] = []
        self.assertTrue(V.errores_de_esquema("catalogo", b))

    def test_los_nombres_viejos_de_b4_no_validan(self) -> None:
        """`landing/catalogo.py` emite hoy `campaign[]`, `adset[]`, `ad[]`: debe migrar (aviso a S-C)."""
        viejo = copy.deepcopy(self.cat); viejo["ids_meta"] = {"campaign": ["120000000000001"], "adset": [], "ad": []}
        self.assertTrue(V.errores_de_esquema("catalogo", viejo))

    def test_campos_opcionales_y_extra(self) -> None:
        minimo = {k: v for k, v in self.cat.items() if k not in ("success_url", "return_url", "landing_version", "renuncia")}
        self.assertEqual([], V.errores_de_esquema("catalogo", minimo))
        self.assertTrue(V.errores_de_esquema("catalogo", {**self.cat, "campaign_ids": []}))
        self.assertTrue(V.errores_de_esquema("catalogo", {**self.cat, "price_ids": {"principal": "price_a", "extra": "price_b"}}))
        self.assertTrue(V.errores_de_esquema("catalogo", {**self.cat, "firma": "hmac-sha256:xyz"}))
        self.assertTrue(V.errores_de_esquema("catalogo", {**self.cat, "schema_version": "2.0.0"}))

    def test_id_de_meta_no_numerico_y_floats(self) -> None:
        mal = copy.deepcopy(self.cat); mal["ids_meta"]["ad_ids"][0] = "ad-1"
        self.assertTrue(V.errores_de_esquema("catalogo", mal))

    def test_no_es_un_archivo_sellado(self) -> None:
        """El catálogo no entra en `hash_salida` de D5 (ruta protegida, regla 7): ni en ARCHIVOS_SELLADOS ni en `_ejemplo`."""
        self.assertNotIn("05-landing/catalogo.json", [r for rels in V.ARCHIVOS_SELLADOS.values() for r in rels])
        self.assertEqual("catalogo", V.ESQUEMA_DE_ARCHIVO["05-landing/catalogo.json"])
        self.assertIn("05-landing/catalogo.json", V.ARCHIVOS_POSTERIORES_AL_BORRADOR)
        self.assertFalse((EJ / "05-landing" / "catalogo.json").exists())

    def test_payload_de_firma_es_el_cuerpo_sin_firma(self) -> None:
        self.assertEqual({k: v for k, v in self.cat.items() if k != "firma"}, V.payload_firma("catalogo", self.cat))

    def test_la_firma_coincide_con_la_de_landing_catalogo(self) -> None:
        """`landing.catalogo` firma `engine.comun.firma_hmac(cuerpo sin firma)`: el mismo JSON canónico que `payload_firma`."""
        from engine import comun
        sin = {k: v for k, v in self.cat.items() if k != "firma"}
        self.assertEqual(comun.firma_hmac(sin, CLAVE), self.cat["firma"])


class PruebaCatalogoReglaCruzada(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)
        self.cat = ejemplo("catalogo.valido.json")
        self.ids = ejemplo("ids_meta.valido.json")
        self.co = V.cargar_json(EJ / "05-landing/checkout.json")

    def test_base_limpia(self) -> None:
        self.assertEqual([], codigos_regla(self.cat, ids=self.ids))

    def test_campos_distintos_del_checkout(self) -> None:
        for campo, valor in (("oferta_id", "OF-202611-02"), ("version", "v2"), ("moneda", "USD")):
            with self.subTest(campo):
                self.assertEqual(["X48_CATALOGO"], codigos_regla(firmado({**self.cat, campo: valor}), ids=self.ids))

    def test_price_id_principal_solo_test_o_live_del_checkout(self) -> None:
        otro = firmado({**self.cat, "price_ids": {**self.cat["price_ids"], "principal": "price_otro"}})
        self.assertEqual(["X48_CATALOGO"], codigos_regla(otro, ids=self.ids))
        co = copy.deepcopy(self.co); co["price_ids"]["live"] = "price_ejemplo_live_principal"
        live = firmado({**self.cat, "price_ids": {**self.cat["price_ids"], "principal": "price_ejemplo_live_principal"}})
        self.assertEqual([], codigos_regla(live, checkout=co, ids=self.ids))
        # un live en null no es una alternativa válida
        self.assertEqual(["X48_CATALOGO"], codigos_regla(firmado({**self.cat, "price_ids": {"principal": "None", **{k: v for k, v in self.cat["price_ids"].items() if k == "bump"}}}), ids=self.ids))

    def test_bump_debe_coincidir_con_el_del_checkout(self) -> None:
        sin_bump = firmado({**self.cat, "price_ids": {"principal": self.cat["price_ids"]["principal"]}})
        self.assertEqual(["X48_CATALOGO"], codigos_regla(sin_bump, ids=self.ids))                    # el checkout trae bump
        co = copy.deepcopy(self.co); co["bump"] = None
        self.assertEqual(["X48_CATALOGO"], codigos_regla(self.cat, checkout=co, ids=self.ids))       # el catálogo vende un bump que no existe
        self.assertEqual([], codigos_regla(sin_bump, checkout=co, ids=self.ids))
        igual = firmado({**self.cat, "price_ids": {"principal": self.cat["price_ids"]["principal"], "bump": self.cat["price_ids"]["principal"]}})
        self.assertIn("X48_CATALOGO", codigos_regla(igual, ids=self.ids))

    def test_urls_si_estan_deben_ser_las_del_checkout(self) -> None:
        mal = firmado({**self.cat, "success_url": "https://otro.example/gracias"})
        self.assertEqual(["X48_CATALOGO"], codigos_regla(mal, ids=self.ids))
        sin = firmado({k: v for k, v in self.cat.items() if k not in ("success_url", "return_url")})
        self.assertEqual([], codigos_regla(sin, ids=self.ids))

    def test_ids_distintos_de_ids_meta_json(self) -> None:
        for campo, nuevo in (("campaign_id", "120000000099999"), ("adset_ids", ["120000000099999"]), ("ad_ids", self.ids["ad_ids"][:-1])):
            with self.subTest(campo):
                cat = copy.deepcopy(self.cat); cat["ids_meta"][campo] = nuevo
                self.assertEqual(["X48_CATALOGO"], codigos_regla(firmado(cat), ids=self.ids))
        # el orden de las listas no importa
        cat = copy.deepcopy(self.cat); cat["ids_meta"]["ad_ids"] = list(reversed(self.ids["ad_ids"]))
        self.assertEqual([], codigos_regla(firmado(cat), ids=self.ids))

    def test_un_mismo_id_no_puede_ser_campana_y_anuncio(self) -> None:
        cat = copy.deepcopy(self.cat); cat["ids_meta"]["ad_ids"][0] = cat["ids_meta"]["campaign_id"]
        self.assertIn("X48_CATALOGO", [c for c, _ in V.problemas_artefacto("catalogo", firmado(cat), clave=CLAVE, entorno="prueba")])

    def test_firma_alterada_o_clave_ajena(self) -> None:
        self.assertEqual(["X40_FIRMA"], codigos_regla({**self.cat, "moneda": "EUR", "generado_en": "2026-11-10T09:00:00Z"}, ids=self.ids))   # cuerpo cambiado sin refirmar
        self.assertEqual(["X40_FIRMA"], codigos_regla(self.cat, ids=self.ids, clave=b"otra"))

    def test_sin_clave_solo_se_comprueba_el_formato(self) -> None:
        c = contexto({"05-landing/catalogo.json": self.cat, "05-landing/checkout.json": self.co, "07-campana/ids_meta.json": self.ids}, None)
        V.regla_catalogo(c)
        self.assertEqual([], c.informe.errores)
        self.assertEqual(["X40_FIRMA"], [h.codigo for h in c.informe.hallazgos])   # AVISO: no se verificó

    def test_hmac_vale_en_produccion_y_ed25519_sin_verificador_no(self) -> None:
        """El catálogo es servicio a servicio: la HMAC (CATALOGO_HMAC) es válida en producción, a diferencia de aprobación/sello/orden."""
        self.assertEqual([], V.problemas_artefacto("catalogo", self.cat, clave=CLAVE, entorno="produccion"))
        ed = {**self.cat, "firma": "ed25519:U1NIU0lH" + "A" * 240}
        self.assertEqual([], V.problemas_artefacto("catalogo", ed, entorno="prueba"))
        self.assertEqual(["X40_FIRMA"], [c for c, _ in V.problemas_artefacto("catalogo", ed, entorno="produccion")])
        self.assertEqual(["X40_FIRMA"], [c for c, _ in V.problemas_artefacto("catalogo", ed, entorno="produccion", verificador=lambda d, f: False)])
        self.assertEqual([], V.problemas_artefacto("catalogo", ed, entorno="produccion", verificador=lambda d, f: True))


class PruebaCatalogoEnOferta(unittest.TestCase):
    """`validar_oferta` carga `05-landing/catalogo.json` si existe, sin tocar nada sellado."""

    def setUp(self) -> None:
        _sin_red(self)
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.dir = Path(self._t.name) / "_ejemplo"
        shutil.copytree(EJ, self.dir)
        self.cat = ejemplo("catalogo.valido.json")

    def inf(self, **kw):
        return V.validar_oferta(self.dir, limites=V.limites_de_prueba(), autonomia=V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml"), clave_firma=CLAVE, **kw)

    def escribir(self, cat: dict) -> None:
        (self.dir / "05-landing" / "catalogo.json").write_text(json.dumps(cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def test_sin_catalogo_la_oferta_sigue_limpia(self) -> None:
        self.assertEqual([], [str(h) for h in self.inf().errores])

    def test_catalogo_vacio_de_ids_valido_y_no_cambia_hashes_sellados(self) -> None:
        self.escribir(firmado({**self.cat, "ids_meta": {"campaign_id": None, "adset_ids": [], "ad_ids": []}}))
        inf = self.inf(clave_catalogo=CLAVE)
        self.assertEqual([], [str(h) for h in inf.errores])
        self.assertEqual([], [str(h) for h in inf.hallazgos])

    def test_catalogo_con_ids_sin_ids_meta_json_falla(self) -> None:
        self.escribir(self.cat)
        self.assertEqual({"X48_CATALOGO"}, {h.codigo for h in self.inf(clave_catalogo=CLAVE).errores})

    def test_precio_ajeno_al_checkout_falla(self) -> None:
        self.escribir(firmado({**self.cat, "ids_meta": {"campaign_id": None, "adset_ids": [], "ad_ids": []},
                               "price_ids": {"principal": "price_otro", "bump": self.cat["price_ids"]["bump"]}}))
        self.assertEqual({"X48_CATALOGO"}, {h.codigo for h in self.inf(clave_catalogo=CLAVE).errores})

    def test_oferta_id_de_otra_oferta_falla(self) -> None:
        self.escribir(firmado({**self.cat, "oferta_id": "OF-202611-02", "ids_meta": {"campaign_id": None, "adset_ids": [], "ad_ids": []}}))
        self.assertIn("X01_ID", {h.codigo for h in self.inf(clave_catalogo=CLAVE).errores})

    def test_la_clave_del_catalogo_sale_de_catalogo_hmac_y_no_de_la_de_aprobaciones(self) -> None:
        cat = firmado({**self.cat, "ids_meta": {"campaign_id": None, "adset_ids": [], "ad_ids": []}}, b"clave-del-catalogo")
        self.escribir(cat)
        with mock.patch.dict(os.environ, {"CATALOGO_HMAC": "clave-del-catalogo"}):
            self.assertEqual([], [str(h) for h in self.inf().errores])
        with mock.patch.dict(os.environ, {"CATALOGO_HMAC": "otra"}):
            self.assertEqual({"X40_FIRMA"}, {h.codigo for h in self.inf().errores})
        env = {k: v for k, v in os.environ.items() if k != "CATALOGO_HMAC"}
        with mock.patch.dict(os.environ, env, clear=True):
            inf = self.inf()   # sin CATALOGO_HMAC: la clave de aprobaciones NO se usa para el catálogo; solo formato y AVISO
            self.assertEqual([], [str(h) for h in inf.errores])
            self.assertEqual(["X40_FIRMA"], [h.codigo for h in inf.hallazgos])


# ----------------------------------------------------------------------------------------------------------------------------
# B-13 · alertas 1.0.0
# ----------------------------------------------------------------------------------------------------------------------------
class PruebaAlertasEsquema(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)
        _, self.esq = V.cargar_esquemas()
        self.al = ejemplo("alertas.valido.json")

    def test_version_y_campos_de_docs_04(self) -> None:
        e = self.esq["alertas"]
        self.assertEqual("1.0.0", e["x-version"])
        self.assertFalse(e["additionalProperties"])
        pedidos = {"id", "ts", "severidad", "regla_id", "origen", "oferta_id", "macro_nicho", "nivel", "valor", "umbral", "accion_sugerida", "estado"}
        self.assertEqual(pedidos | {"schema_version"}, set(e["required"]))
        self.assertEqual(pedidos | {"schema_version"}, set(e["properties"]))

    def test_enums(self) -> None:
        p = self.esq["alertas"]["properties"]
        self.assertEqual(["info", "amarilla", "naranja", "roja"], p["severidad"]["enum"])
        self.assertEqual(["F1", "F2"], p["origen"]["enum"])
        self.assertEqual(["abierta", "reconocida", "cerrada"], p["estado"]["enum"])

    def test_el_ejemplo_valida_y_las_severidades_entran_en_los_tonos_del_panel(self) -> None:
        self.assertEqual([], V.errores_de_esquema("alertas", self.al))
        for sev in ("info", "amarilla", "naranja", "roja"):
            self.assertEqual([], V.errores_de_esquema("alertas", {**self.al, "severidad": sev}), sev)
        for sev in ("critica", "amarillo", "ROJA", "media", ""):
            self.assertTrue(V.errores_de_esquema("alertas", {**self.al, "severidad": sev}), sev)

    def test_estados_y_origen(self) -> None:
        for est in ("abierta", "reconocida", "cerrada"):
            self.assertEqual([], V.errores_de_esquema("alertas", {**self.al, "estado": est}))
        for est in ("resuelta", "Abierta", None):
            self.assertTrue(V.errores_de_esquema("alertas", {**self.al, "estado": est}))
        self.assertTrue(V.errores_de_esquema("alertas", {**self.al, "origen": "F3"}))

    def test_valor_y_umbral_admiten_decimal_entero_dinero_y_null(self) -> None:
        for v in ("0.55", "-12", 3, -3, {"monto": 1990, "moneda": "EUR"}, None):
            self.assertEqual([], V.errores_de_esquema("alertas", {**self.al, "valor": v, "umbral": v if not isinstance(v, str) else "1"}), repr(v))
        for v in (0.55, "0,55", "abc", True, {"monto": 1.5, "moneda": "EUR"}, {"monto": 1}, [1], 2 ** 60):
            self.assertTrue(V.errores_de_esquema("alertas", {**self.al, "valor": v}), repr(v))

    def test_oferta_macro_y_nivel_pueden_ser_null(self) -> None:
        a = {**self.al, "oferta_id": None, "macro_nicho": None, "nivel": None}
        self.assertEqual([], V.errores_de_esquema("alertas", a))
        for k in ("oferta_id", "macro_nicho", "nivel"):
            sin = {x: y for x, y in self.al.items() if x != k}
            self.assertTrue(V.errores_de_esquema("alertas", sin), f"{k} debe estar presente (puede ser null)")
        for nivel in ("verde", "amarillo", "rojo", "amarillo-a", "amarillo-b"):
            self.assertEqual([], V.errores_de_esquema("alertas", {**self.al, "nivel": nivel}), nivel)
        self.assertTrue(V.errores_de_esquema("alertas", {**self.al, "nivel": "naranja"}))
        self.assertTrue(V.errores_de_esquema("alertas", {**self.al, "macro_nicho": "ocio"}))

    def test_id_regla_ts_y_accion(self) -> None:
        for k, v in (("regla_id", "A06"), ("regla_id", "f2-a06"), ("regla_id", "F3-A01"), ("id", ""), ("id", "con espacio"), ("ts", "2026-11-14T06:00:00"),
                     ("accion_sugerida", ""), ("accion_sugerida", "x" * 301), ("schema_version", "2.0.0")):
            with self.subTest(k=k, v=v[:12]):
                self.assertTrue(V.errores_de_esquema("alertas", {**self.al, k: v}))
        for rid in ("F1-A01", "F2-A17", "F1-CONCIL", "F1-IA"):   # los de las fixtures del panel entran
            self.assertEqual([], V.errores_de_esquema("alertas", {**self.al, "regla_id": rid, "origen": rid[:2]}), rid)

    def test_el_esquema_solo_usa_campos_que_lee_el_panel(self) -> None:
        """`normalizarAlertas` (dashboard/web/lib/finanzas.js) lee estos campos; un campo nuevo en el esquema sin lector sería un contrato mudo."""
        js = RAIZ / "dashboard" / "web" / "lib" / "finanzas.js"
        if not js.is_file():
            self.skipTest("el panel no está en este árbol")
        m = re.search(r"export function normalizarAlertas\(.*?\n}\n", js.read_text(encoding="utf-8"), re.S)
        self.assertIsNotNone(m)
        for campo in self.esq["alertas"]["properties"]:
            if campo != "schema_version":
                self.assertRegex(m.group(0), rf"\ba\.{campo}\b", campo)

    def test_las_alertas_de_las_fixtures_del_panel_son_casi_validas(self) -> None:
        """Documenta la distancia con lo que el panel ya prueba: faltan `schema_version` y llaves null, y `estado: resuelta` no es del ciclo."""
        ruta = RAIZ / "tests" / "fixtures" / "dashboard" / "finanzas" / "finanzas_sano.json"
        if not ruta.is_file():
            self.skipTest("sin fixture del panel")
        for a in json.loads(ruta.read_text(encoding="utf-8")).get("alertas", []):
            relleno = {"schema_version": "1.0.0", "oferta_id": None, "macro_nicho": None, "nivel": None, "valor": None, "umbral": None, **a}
            if relleno["estado"] == "resuelta":
                relleno["estado"] = "cerrada"
            self.assertEqual([], [e.message for e in V.errores_de_esquema("alertas", relleno)], a["id"])


class PruebaAlertasCoherencia(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)
        self.al = ejemplo("alertas.valido.json")

    def cods(self, a: dict) -> list[str]:
        return [c for c, _ in V.problemas_artefacto("alertas", a)]

    def test_base_limpia(self) -> None:
        self.assertEqual([], self.cods(self.al))

    def test_prefijo_de_la_regla_es_el_origen(self) -> None:
        self.assertEqual(["X49_ALERTAS"], self.cods({**self.al, "origen": "F1"}))   # F2-A06 con origen F1
        self.assertEqual([], self.cods({**self.al, "origen": "F1", "regla_id": "F1-A04"}))

    def test_monedas_y_tipos_de_valor_y_umbral(self) -> None:
        d = lambda m, c: {"monto": m, "moneda": c}   # noqa: E731
        self.assertEqual([], self.cods({**self.al, "valor": d(1990, "EUR"), "umbral": d(0, "EUR")}))
        self.assertEqual(["X49_ALERTAS"], self.cods({**self.al, "valor": d(1990, "EUR"), "umbral": d(0, "USD")}))
        self.assertEqual(["X49_ALERTAS"], self.cods({**self.al, "valor": d(1990, "EUR"), "umbral": "15"}))
        self.assertEqual([], self.cods({**self.al, "valor": d(1990, "EUR"), "umbral": None}))   # sin umbral fijado
        self.assertEqual([], self.cods({**self.al, "valor": "16", "umbral": 15}))

    def test_ids_unicos_por_archivo(self) -> None:
        otra = {**self.al, "id": "F2-A07-OF-202611-01-2026-11-14", "regla_id": "F2-A07"}
        self.assertEqual([], V.problemas_alertas([self.al, otra]))
        self.assertEqual(["X49_ALERTAS"], [c for c, _ in V.problemas_alertas([self.al, otra, copy.deepcopy(self.al)])])


class PruebaAlertasEnEmpresa(unittest.TestCase):
    """`validar_artefactos_de_empresa` recorre línea a línea SOLO `empresa/datos/alertas.jsonl` (la única que lee el panel)."""

    def setUp(self) -> None:
        _sin_red(self)
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.emp = Path(self._t.name) / "empresa"
        (self.emp / "datos").mkdir(parents=True)
        (self.emp / "finanzas").mkdir()
        self.al = ejemplo("alertas.valido.json")

    def jsonl(self, rel: str, lineas: list[dict]) -> None:
        (self.emp / rel).write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lineas), encoding="utf-8")

    def correr(self) -> V.Informe:
        inf = V.Informe("prueba")
        V.validar_artefactos_de_empresa(self.emp, inf, parametros={})
        return inf

    def test_lineas_validas(self) -> None:
        self.jsonl("datos/alertas.jsonl", [self.al, {**self.al, "id": "F2-A07-x", "regla_id": "F2-A07", "severidad": "info", "estado": "cerrada"}])
        self.assertEqual([], [str(h) for h in self.correr().errores])

    def test_linea_invalida_se_senala_con_su_indice(self) -> None:
        self.jsonl("datos/alertas.jsonl", [self.al, {**self.al, "id": "F2-A07-x", "severidad": "critica"}])
        errs = self.correr().errores
        self.assertEqual(1, len(errs))
        self.assertIn("alertas.jsonl[1]", str(errs[0]))

    def test_incoherencia_y_id_repetido(self) -> None:
        self.jsonl("datos/alertas.jsonl", [self.al, {**self.al, "origen": "F1"}])
        self.assertEqual({"X49_ALERTAS"}, {h.codigo for h in self.correr().errores})

    def test_no_valida_finanzas_alertas_jsonl(self) -> None:
        """B-13: `empresa/finanzas/alertas.jsonl` (F1) no tiene lector; el esquema vale, pero el validador no se engancha."""
        self.jsonl("finanzas/alertas.jsonl", [{"cualquier": "cosa"}])
        self.assertEqual([], self.correr().errores)

    def test_sin_archivo_no_hay_hallazgos(self) -> None:
        self.assertEqual([], self.correr().hallazgos)


class PruebaEjemplosB1(unittest.TestCase):
    def test_validar_ejemplos_en_verde_con_los_nuevos(self) -> None:
        inf = V.validar_ejemplos()
        self.assertEqual([], [str(h) for h in inf.errores])
        nombres = {p.name for p in V.DIR_EJEMPLOS.iterdir()}
        for esperado in ("catalogo.valido.json", "catalogo.invalido-ids-meta-con-nombres-de-b4.json", "catalogo.invalido-anuncios-sin-campana.json",
                         "alertas.valido.json", "alertas.invalido-severidad-inventada.json", "alertas.invalido-valor-float.json",
                         "alertas.invalido-estado-fuera-del-ciclo.json"):
            self.assertIn(esperado, nombres)
            if ".invalido" in esperado:
                self.assertIn(esperado.replace(".json", ".motivo.txt"), nombres)

    def test_el_ejemplo_de_catalogo_no_toca_ofertas_ejemplo(self) -> None:
        self.assertFalse((EJ / "05-landing" / "catalogo.json").exists())


if __name__ == "__main__":
    unittest.main()
