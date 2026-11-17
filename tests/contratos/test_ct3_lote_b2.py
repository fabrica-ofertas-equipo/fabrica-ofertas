"""CT-3, lote B, sub-lote B2: B-03 (`qa` 1.1.0, `categoria_especial_requerida`) y los adelantables de S-29 (`senal_pausa` 1.2.0 con
`incidente_seguridad`, `pnl` 1.1.0 con `fx_ref` `TC-`). Backlog: ``docs/_historial/ct3-backlog.md`` §4.2. Sin red; copias temporales."""
from __future__ import annotations

import copy
import json
import shutil
import socket
import tempfile
import unittest
from pathlib import Path

from scripts import validar_esquemas as V

RAIZ = Path(__file__).resolve().parents[2]
EJ = RAIZ / "ofertas" / "_ejemplo"
CLAVE = V.CLAVE_DE_PRUEBA
FIN = "FINANCIAL_PRODUCTS_SERVICES"


def _sin_red(caso: unittest.TestCase) -> None:
    original = socket.socket

    def bloqueado(*a, **k):
        raise AssertionError("las pruebas no pueden abrir sockets")

    socket.socket = bloqueado  # type: ignore[assignment]
    caso.addCleanup(setattr, socket, "socket", original)


def ejemplo(nombre: str) -> dict:
    return json.loads((V.DIR_EJEMPLOS / nombre).read_text(encoding="utf-8"))


def x1(version: str = "1.1.0", cat=None, objetivo: str = "D7") -> dict:
    d = ejemplo("qa.valido-x1-categoria-especial.json")
    d["schema_version"] = version
    d["etapa_objetivo"] = objetivo
    d.pop("categoria_especial_requerida", None)
    if cat is not None:
        d["categoria_especial_requerida"] = cat
    return d


def errs(nombre: str, d: dict) -> list:
    return V.errores_de_esquema(nombre, d)


class PruebaQaEsquema(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)
        _, self.esq = V.cargar_esquemas()

    def test_version_y_campo_opcional(self) -> None:
        e = self.esq["qa"]
        self.assertEqual("1.1.0", e["x-version"])
        self.assertIn("categoria_especial_requerida", e["properties"])
        self.assertNotIn("categoria_especial_requerida", e["required"])      # opcional: los 1.0.0 no lo tienen
        self.assertFalse(e["additionalProperties"])

    def test_mismo_enum_que_campana_special_ad_categories(self) -> None:
        """P25 en un solo sentido solo se cierra si ambos lados hablan del mismo enum (B-03)."""
        en_qa = self.esq["qa"]["properties"]["categoria_especial_requerida"]
        en_campana = self.esq["campana"]["properties"]["special_ad_categories"]
        self.assertEqual(en_campana["items"], en_qa["items"])
        self.assertTrue(en_qa["uniqueItems"])

    def test_los_dictamenes_1_0_0_siguen_validos(self) -> None:
        self.assertEqual([], errs("qa", ejemplo("qa.valido.json")))
        for f in sorted((EJ / "qa").glob("*.json")):
            self.assertEqual([], errs("qa", json.loads(f.read_text(encoding="utf-8"))), f.name)

    def test_x1_1_1_0_con_categoria(self) -> None:
        for cat in ([], [FIN], ["HOUSING", FIN]):
            self.assertEqual([], errs("qa", x1(cat=cat)), cat)

    def test_x1_1_1_0_sin_campo_valida_en_el_esquema(self) -> None:
        """El esquema NO lo exige (opcional): lo exige la regla X50 solo para X1 sobre D7 >= 1.1.0."""
        self.assertEqual([], errs("qa", x1()))

    def test_rechaza_categoria_inventada_repetida_o_mal_tipada(self) -> None:
        for cat in (["CRYPTO"], [FIN, FIN], FIN, [None], ["financial_products_services"]):
            self.assertTrue(errs("qa", x1(cat=cat)), cat)

    def test_solo_en_el_dictamen_de_x1(self) -> None:
        d3 = {**ejemplo("qa.valido.json"), "categoria_especial_requerida": []}
        self.assertTrue(errs("qa", d3))                                       # etapa D3
        self.assertTrue(errs("qa", {**d3, "schema_version": "1.1.0"}))        # ni con 1.1.0

    def test_el_dictamen_1_0_x_no_puede_traer_el_campo(self) -> None:
        for v in ("1.0.0", "1.0.7"):
            self.assertTrue(errs("qa", x1(version=v, cat=[FIN])), v)
        for v in ("1.1.0", "1.2.3", "1.10.0"):
            self.assertEqual([], errs("qa", x1(version=v, cat=[FIN])), v)


class PruebaProblemasCategoriaEspecial(unittest.TestCase):
    """La función pura reutilizable por quien emita P25 (`meta.preflight`)."""

    def setUp(self) -> None:
        _sin_red(self)

    def cods(self, d: dict, camp) -> list[str]:
        return [c for c, _ in V.problemas_categoria_especial(d, camp)]

    def test_iguales_sin_importar_el_orden(self) -> None:
        self.assertEqual([], self.cods(x1(cat=["HOUSING", FIN]), [FIN, "HOUSING"]))
        self.assertEqual([], self.cods(x1(cat=[]), []))

    def test_x1_exige_y_la_campana_no_declara(self) -> None:
        """El defecto S19: producto financiero con special_ad_categories [] pasaba porque P25 era NO_APLICA."""
        out = V.problemas_categoria_especial(x1(cat=[FIN]), [])
        self.assertEqual(["X50_QA_CATEGORIA"], [c for c, _ in out])
        self.assertIn(FIN, out[0][1])

    def test_la_campana_declara_y_x1_no_exigio(self) -> None:
        out = V.problemas_categoria_especial(x1(cat=[]), ["HOUSING"])
        self.assertEqual(["X50_QA_CATEGORIA"], [c for c, _ in out])
        self.assertIn("HOUSING", out[0][1])

    def test_diferencia_en_ambos_sentidos_da_dos_errores(self) -> None:
        self.assertEqual(["X50_QA_CATEGORIA"] * 2, self.cods(x1(cat=["HOUSING"]), [FIN]))

    def test_no_exige_el_campo_a_dictamenes_1_0_0(self) -> None:
        self.assertEqual([], self.cods(x1(version="1.0.0"), []))
        self.assertEqual([], self.cods(x1(version="1.0.0"), [FIN]))              # no se compara: no hay campo
        self.assertEqual([], self.cods(x1(version="1.0.9", objetivo="D7"), None))

    def test_exige_el_campo_solo_a_x1_d7_desde_1_1_0(self) -> None:
        self.assertEqual(["X50_QA_CATEGORIA"], self.cods(x1(), []))
        self.assertEqual(["X50_QA_CATEGORIA"], self.cods(x1(), None))            # sin campaña todavía: igual se exige la presencia
        self.assertEqual([], self.cods(x1(objetivo="D5"), []))
        self.assertEqual([], self.cods(x1(objetivo="D6"), [FIN]))

    def test_sin_campana_no_hay_con_que_comparar(self) -> None:
        self.assertEqual([], self.cods(x1(cat=[FIN]), None))

    def test_no_aplica_fuera_de_x1(self) -> None:
        self.assertEqual([], self.cods({**ejemplo("qa.valido.json"), "schema_version": "1.1.0"}, [FIN]))

    def test_version_ilegible_no_lanza(self) -> None:
        self.assertEqual([], self.cods({**x1(), "schema_version": "basura"}, []))


class PruebaQaReglaCruzada(unittest.TestCase):
    """X50 dentro de `validar_oferta` sobre una copia de `ofertas/_ejemplo/` (la campaña del ejemplo trae `special_ad_categories: []`)."""

    def setUp(self) -> None:
        _sin_red(self)
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dir = self.tmp / "OF-202611-01"
        shutil.copytree(EJ, self.dir)
        self.lim = V.limites_de_prueba()
        self.aut = V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml")

    def x50(self) -> list[str]:
        inf = V.validar_oferta(self.dir, limites=self.lim, autonomia=self.aut, clave_firma=CLAVE)
        return [h.codigo for h in inf.errores if h.codigo == "X50_QA_CATEGORIA"]

    def escribir(self, nombre: str, d: dict) -> None:
        (self.dir / "qa" / nombre).write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def dictamen(self, **cambios) -> dict:
        d = json.loads((self.dir / "qa" / "x1-d7-v1.json").read_text(encoding="utf-8"))
        d.update(cambios)
        return d

    def test_el_ejemplo_1_0_0_sigue_sin_x50_y_sin_resellar(self) -> None:
        self.assertEqual([], self.x50())

    def test_x1_d7_1_1_0_igual_a_la_campana(self) -> None:
        self.escribir("x1-d7-v1.json", self.dictamen(schema_version="1.1.0", categoria_especial_requerida=[]))
        self.assertEqual([], self.x50())

    def test_x1_exige_financiero_y_la_campana_dice_vacio(self) -> None:
        self.escribir("x1-d7-v1.json", self.dictamen(schema_version="1.1.0", categoria_especial_requerida=[FIN]))
        self.assertEqual(["X50_QA_CATEGORIA"], self.x50())

    def test_x1_d7_1_1_0_sin_el_campo(self) -> None:
        self.escribir("x1-d7-v1.json", self.dictamen(schema_version="1.1.0"))
        self.assertEqual(["X50_QA_CATEGORIA"], self.x50())

    def test_campana_con_categoria_y_dictamen_1_1_0_vacio(self) -> None:
        camp = V.cargar_json(self.dir / "07-campana/campana.json")
        camp["special_ad_categories"] = ["HOUSING"]
        (self.dir / "07-campana/campana.json").write_text(json.dumps(camp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.escribir("x1-d7-v1.json", self.dictamen(schema_version="1.1.0", categoria_especial_requerida=[]))
        self.assertEqual(["X50_QA_CATEGORIA"], self.x50())

    def test_solo_cuenta_el_dictamen_vigente_de_cada_etapa(self) -> None:
        """v1 con FIN y v2 con []: la campaña [] coincide con el vigente; el reemplazado no se compara."""
        self.escribir("x1-d7-v1.json", self.dictamen(schema_version="1.1.0", categoria_especial_requerida=[FIN]))
        self.escribir("x1-d7-v2.json", self.dictamen(schema_version="1.1.0", version="v2", categoria_especial_requerida=[]))
        self.assertEqual([], self.x50())
        self.escribir("x1-d7-v2.json", self.dictamen(schema_version="1.1.0", version="v2", categoria_especial_requerida=[FIN]))
        self.assertEqual(["X50_QA_CATEGORIA"], self.x50())

    def test_el_dictamen_de_x1_sobre_d5_con_campo_tambien_se_compara(self) -> None:
        d5 = json.loads((self.dir / "qa" / "x1-d5-v1.json").read_text(encoding="utf-8"))
        d5.update(schema_version="1.1.0", categoria_especial_requerida=[FIN])
        self.escribir("x1-d5-v1.json", d5)
        self.assertEqual(["X50_QA_CATEGORIA"], self.x50())


class PruebaSenalPausa(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)
        _, self.esq = V.cargar_esquemas()
        self.s = ejemplo("senal_pausa.valido.json")

    def test_version_y_enum(self) -> None:
        e = self.esq["senal_pausa"]
        self.assertEqual("1.2.0", e["x-version"])
        self.assertEqual(["ninguno", "disputas", "reembolsos", "caida_de_entrega", "queja_de_correo", "fraude", "incidente_seguridad", "otro"],
                         e["properties"]["motivo"]["enum"])

    def test_incidente_seguridad_y_los_motivos_previos(self) -> None:
        for m in ("ninguno", "disputas", "reembolsos", "caida_de_entrega", "queja_de_correo", "fraude", "otro", "incidente_seguridad"):
            self.assertEqual([], errs("senal_pausa", {**self.s, "motivo": m}), m)
        for m in ("seguridad", "incidente", "INCIDENTE_SEGURIDAD", "", None):
            self.assertTrue(errs("senal_pausa", {**self.s, "motivo": m}), repr(m))

    def test_el_ejemplo_de_incidente_valida_y_los_1_1_0_siguen_validos(self) -> None:
        self.assertEqual([], errs("senal_pausa", ejemplo("senal_pausa.valido-incidente-seguridad.json")))
        sp = json.loads((EJ / "10-postcompra/senal_pausa.json").read_text(encoding="utf-8"))
        self.assertEqual([], errs("senal_pausa", sp))

    def test_los_campos_no_cambian(self) -> None:
        d = self.esq["senal_pausa"]
        self.assertEqual({"schema_version", "oferta_id", "ts", "emitida", "nivel", "motivo", "metricas", "umbrales_usados", "accion_solicitada",
                          "consumida_por", "sintetico"}, set(d["properties"]))
        self.assertEqual(["ninguna", "alertar", "pausar"], d["properties"]["accion_solicitada"]["enum"])


class PruebaPnl(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)
        _, self.esq = V.cargar_esquemas()
        self.p = ejemplo("pnl.valido.json")

    def test_version(self) -> None:
        self.assertEqual("1.1.0", self.esq["pnl"]["x-version"])

    def test_fx_ref_es_el_tipo_cambio_id_de_comunes_o_null(self) -> None:
        self.assertEqual([{"$ref": "comunes.schema.json#/$defs/tipo_cambio_id"}, {"type": "null"}], self.esq["pnl"]["properties"]["fx_ref"]["anyOf"])
        self.assertEqual("^TC-[A-Z]{6}-[0-9]{8}$", self.esq["comunes"]["$defs"]["tipo_cambio_id"]["pattern"])   # el de ledger y tipo_cambio
        self.assertEqual("tipo_cambio_id", self.esq["tipo_cambio"]["properties"]["tipo_cambio_id"]["$ref"].rsplit("/", 1)[-1])

    def test_valores(self) -> None:
        for v in (None, "TC-USDEUR-20261120", "TC-EURGBP-20260101"):
            self.assertEqual([], errs("pnl", {**self.p, "fx_ref": v}), repr(v))
        for v in ("FX-20261120-USDEUR", "FX-USDEUR-20261120", "TC-USDEUR-2026112", "TC-USD-20261120", "tc-usdeur-20261120", "", 1):
            self.assertTrue(errs("pnl", {**self.p, "fx_ref": v}), repr(v))

    def test_los_ejemplos_validan_y_el_tc_id_es_el_de_tipo_cambio(self) -> None:
        d = ejemplo("pnl.valido-con-fx-ref.json")
        self.assertEqual([], errs("pnl", d))
        self.assertEqual(V.tipo_cambio_id_esperado("USDEUR", "2026-11-20"), d["fx_ref"])

    def test_la_formula_no_cambia(self) -> None:
        inf = V.Informe("t")
        V.reglas_de_artefacto("pnl", ejemplo("pnl.valido-con-fx-ref.json"), inf, "pnl")
        self.assertEqual([], [str(h) for h in inf.errores])

    def test_descripcion_aclara_impuesto_incluido(self) -> None:
        txt = json.dumps(self.esq["pnl"], ensure_ascii=False)
        self.assertIn("INCLUYE el impuesto", txt)

    def test_nadie_mas_usa_el_patron_fx(self) -> None:
        """Grep del patrón retirado: ningún esquema, ejemplo ni plantilla lo conserva."""
        for ruta in list((RAIZ / "contratos").glob("*.schema.json")) + list((RAIZ / "ofertas" / "_ejemplo").rglob("*.json")):
            self.assertNotIn("^FX-", ruta.read_text(encoding="utf-8"), ruta.name)
        for f in V.DIR_EJEMPLOS.glob("*"):
            if f.suffix in (".json", ".yaml") and "invalido" not in f.name and ".motivo" not in f.name:
                self.assertNotRegex(f.read_text(encoding="utf-8"), r'"FX-[0-9A-Z]', f.name)


class PruebaEjemplosDeB2(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)

    def test_cada_invalido_tiene_motivo_y_falla_por_esa_causa(self) -> None:
        nuevos = ["qa.invalido-categoria-en-dictamen-no-x1", "qa.invalido-categoria-en-dictamen-1-0-0", "qa.invalido-categoria-especial-inventada",
                  "senal_pausa.invalido-motivo-inventado", "pnl.invalido-fx-ref-formato-antiguo"]
        for n in nuevos:
            self.assertTrue((V.DIR_EJEMPLOS / f"{n}.motivo.txt").is_file(), n)
            nombre = n.split(".")[0]
            datos = json.loads((V.DIR_EJEMPLOS / f"{n}.json").read_text(encoding="utf-8"))
            self.assertTrue(V.coincide_motivo(V.errores_de_esquema(nombre, datos), V.leer_motivo(V.DIR_EJEMPLOS / f"{n}.motivo.txt")), n)

    def test_validar_ejemplos_en_verde(self) -> None:
        self.assertEqual([], [str(h) for h in V.validar_ejemplos().errores])

    def test_la_oferta_de_ejemplo_no_cambio_de_version_de_qa(self) -> None:
        """Sin re-sellado: los QA de `_ejemplo` siguen en 1.0.0 y la oferta valida completa."""
        for f in (EJ / "qa").glob("*.json"):
            self.assertEqual("1.0.0", json.loads(f.read_text(encoding="utf-8"))["schema_version"], f.name)
        inf = V.validar_oferta(EJ, limites=V.limites_de_prueba(), autonomia=V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml"), clave_firma=CLAVE)
        self.assertEqual([], [str(h) for h in inf.errores])


if __name__ == "__main__":
    unittest.main()
