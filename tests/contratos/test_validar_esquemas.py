"""Pruebas de los contratos de datos y del validador de reglas cruzadas (sin red, sin credenciales reales)."""
from __future__ import annotations

import copy
import datetime as dt
import io
import json
import shutil
import socket
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from scripts import validar_esquemas as V

CLAVE = V.CLAVE_DE_PRUEBA
ORDEN_GATE = {"A": 0, "S": 1, "H": 2}


def _sin_red(caso: unittest.TestCase) -> None:
    """Bloquea sockets: ninguna prueba puede salir a la red (convenciones 11)."""
    original = socket.socket

    def bloqueado(*a, **k):
        raise AssertionError("las pruebas no pueden abrir sockets")

    socket.socket = bloqueado  # type: ignore[assignment]
    caso.addCleanup(setattr, socket, "socket", original)


class PruebaEsquemas(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)

    def test_cargan_todos_los_esquemas_por_id(self) -> None:
        _, esquemas = V.cargar_esquemas()
        esperados = {"comunes", "brief", "estado", "mercado", "candidatos", "validacion", "oferta", "economia", "producto", "assets",
                     "checkout", "tracking_plan", "creativos", "campana", "orden_presupuesto", "veredicto_oferta", "senal_pausa",
                     "entrega", "reembolso", "qa", "registro", "costos", "infra_estado", "limites", "parametros", "autonomia",
                     "portafolio", "pnl", "kpi", "gates",
                     # ola 0b-1 (C13)
                     "aprobacion", "ids_meta", "preflight", "sello", "decision", "ledger", "conciliacion", "tipo_cambio", "postmortem",
                     "orden_firmada", "traspaso",
                     # CT-3 lote B, sub-lote B1
                     "catalogo", "alertas"}
        self.assertEqual(esperados, set(esquemas))
        ids = [d["$id"] for d in esquemas.values()]
        self.assertEqual(len(ids), len(set(ids)))
        for nombre, doc in esquemas.items():
            self.assertTrue(doc["$id"].endswith(f"/v1/{nombre}.schema.json"), nombre)
            self.assertEqual("https://json-schema.org/draft/2020-12/schema", doc["$schema"])
            self.assertTrue(doc["title"] and doc["description"])

    def test_informe_de_esquemas_sin_errores(self) -> None:
        inf = V.validar_esquemas_cargables()
        self.assertEqual([], [str(h) for h in inf.errores])

    def test_todo_objeto_cerrado_donde_corresponde(self) -> None:
        """Los artefactos de oferta no admiten propiedades extra en su nivel superior."""
        _, esquemas = V.cargar_esquemas()
        for nombre, doc in esquemas.items():
            if nombre == "comunes":
                continue
            self.assertIs(doc.get("additionalProperties", True), False, nombre)

    def test_dinero_rechaza_float_y_exige_moneda(self) -> None:
        reg, esquemas = V.cargar_esquemas()
        from jsonschema import Draft202012Validator
        v = Draft202012Validator({"$ref": "https://fabrica-ofertas.example/contratos/v1/comunes.schema.json#/$defs/dinero"}, registry=reg)
        self.assertTrue(v.is_valid({"monto": 1990, "moneda": "EUR"}))
        self.assertFalse(v.is_valid({"monto": 19.9, "moneda": "EUR"}))
        self.assertFalse(v.is_valid({"monto": 1990}))
        self.assertFalse(v.is_valid({"monto": 1990, "moneda": "eur"}))

    def test_patrones_de_ids_y_nombres_de_meta(self) -> None:
        reg, _ = V.cargar_esquemas()
        from jsonschema import Draft202012Validator

        def ok(nombre: str, valor: str) -> bool:
            return Draft202012Validator({"$ref": f"https://fabrica-ofertas.example/contratos/v1/comunes.schema.json#/$defs/{nombre}"}, registry=reg).is_valid(valor)

        self.assertTrue(ok("oferta_id", "OF-202611-01"))
        self.assertFalse(ok("oferta_id", "OF-2026-01"))
        self.assertTrue(ok("familia_id", "FAM-202611-01"))
        self.assertTrue(ok("problema_id", "PRB-202611-0007"))
        self.assertTrue(ok("nombre_meta_campana", "OF-202611-01_TEST_VENTAS_CBO_20261110"))
        self.assertFalse(ok("nombre_meta_campana", "OF-202611-01|TEST|VENTAS|CBO|20261110"))
        self.assertFalse(ok("nombre_meta_campana", "OF-202611-01_PRUEBA_VENTAS_CBO_20261110"))
        self.assertTrue(ok("nombre_meta_conjunto", "AmpliaES-28a55_Automaticas_es-ES"))
        self.assertTrue(ok("nombre_meta_anuncio", "c01-hueco_img_h1_v1"))
        self.assertFalse(ok("nombre_meta_anuncio", "c01-hueco|img|h1|v1"))
        self.assertFalse(ok("nombre_meta_anuncio", "c01_hueco_img_h1_v1"))
        self.assertTrue(ok("timestamp", "2026-11-06T14:30:00Z"))
        self.assertFalse(ok("timestamp", "2026-11-06T14:30:00+01:00"))
        self.assertTrue(ok("sha256", "sha256:" + "a" * 64))
        self.assertFalse(ok("sha256", "sha256:" + "A" * 64))

    def test_enumerados_unicos_de_backbone(self) -> None:
        _, esquemas = V.cargar_esquemas()
        d = esquemas["comunes"]["$defs"]
        self.assertEqual(["PASS", "PASS_CON_NOTAS", "FAIL", "ESCALAR"], d["veredicto_qa"]["enum"])
        self.assertEqual(["BLOQUEANTE", "MAYOR", "MENOR", "MEJORA"], d["severidad"]["enum"])
        self.assertEqual(["N0", "N1", "N2", "N3", "N4"], d["nivel_autonomia"]["enum"])
        self.assertEqual(["salud", "relaciones", "dinero"], d["macro_nicho"]["enum"])
        self.assertEqual(11, len(d["motivo_rechazo"]["enum"]))   # CT-3 A-01: += linea_roja_de_contenido_o_negocio
        self.assertIn("fuera_de_macro_nicho", d["motivo_rechazo"]["enum"])
        self.assertIn("linea_roja_de_contenido_o_negocio", d["motivo_rechazo"]["enum"])
        self.assertEqual(["E1", "E2", "E3", "E4"], d["tipo_evidencia"]["enum"])


class PruebaEjemplos(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)

    def test_ejemplos_validos_pasan_e_invalidos_fallan_con_su_motivo(self) -> None:
        inf = V.validar_ejemplos()
        self.assertEqual([], [str(h) for h in inf.errores])
        self.assertGreater(inf.verificados, 50)

    def test_cada_esquema_tiene_un_ejemplo_valido_y_uno_invalido_con_motivo(self) -> None:
        _, esquemas = V.cargar_esquemas()
        for nombre in esquemas:
            if nombre == "comunes":
                continue
            validos = list(V.DIR_EJEMPLOS.glob(f"{nombre}.valido.*"))
            invalidos = [p for p in V.DIR_EJEMPLOS.glob(f"{nombre}.invalido-*") if ".motivo" not in p.name]
            self.assertTrue(validos, f"falta ejemplo válido de {nombre}")
            self.assertTrue(invalidos, f"falta ejemplo inválido de {nombre}")
            for p in invalidos:
                self.assertTrue(p.with_name(p.stem + ".motivo.txt").exists(), p.name)

    def test_un_invalido_que_falla_por_otra_razon_se_detecta(self) -> None:
        """El validador de ejemplos no se conforma con que falle: exige el motivo declarado."""
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            shutil.copytree(V.DIR_EJEMPLOS, t / "ej")
            motivo = t / "ej" / "oferta.invalido-id-mal-formado.motivo.txt"
            motivo.write_text("validador=enum\nruta=/otro_campo\n", encoding="utf-8")
            inf = V.validar_ejemplos(t / "ej")
            self.assertIn("EJEMPLO_MOTIVO", {h.codigo for h in inf.errores})

    def test_un_invalido_que_pasa_se_detecta(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            shutil.copytree(V.DIR_EJEMPLOS, t / "ej")
            shutil.copy(t / "ej" / "oferta.valido.json", t / "ej" / "oferta.invalido-id-mal-formado.json")
            inf = V.validar_ejemplos(t / "ej")
            self.assertIn("EJEMPLO_INVALIDO_PASA", {h.codigo for h in inf.errores})


class PruebaHashes(unittest.TestCase):
    def test_json_canonico_es_estable_y_sin_espacios(self) -> None:
        a = V.json_canonico({"b": 1, "a": {"d": "é", "c": [1, 2]}})
        b = V.json_canonico({"a": {"c": [1, 2], "d": "é"}, "b": 1})
        self.assertEqual(a, b)
        self.assertEqual('{"a":{"c":[1,2],"d":"é"},"b":1}'.encode(), a)

    def test_hash_excluye_sellos(self) -> None:
        base = {"x": 1, "hash": "sha256:" + "0" * 64}
        self.assertEqual(V.hash_objeto(base, excluir=("hash",)), V.hash_objeto({"x": 1}))
        self.assertNotEqual(V.hash_objeto({"x": 1}), V.hash_objeto({"x": 2}))

    def test_texto_se_normaliza_a_nfc_y_lf(self) -> None:
        self.assertEqual(V.normalizar_texto("é\r\nx"), "é\nx")

    def test_buscar_floats(self) -> None:
        self.assertEqual(["/a/1/b"], V.buscar_floats({"a": [1, {"b": 1.5}], "c": "1.5"}))
        self.assertEqual([], V.buscar_floats({"a": 1}))

    def test_redondeo_explicito(self) -> None:
        self.assertEqual(118, V.entero_redondeado(1185, 10))        # half_even: 118.5 -> 118
        self.assertEqual(119, V.entero_redondeado(1185, 10, "half_up"))
        self.assertEqual(5, V.entero_redondeado(41, 10, "techo"))

    def test_firma_hmac_y_comparacion(self) -> None:
        f = V.firma_hmac({"a": 1}, CLAVE)
        self.assertTrue(f.startswith("hmac-sha256:"))
        self.assertTrue(V.comparar_hash(f, V.firma_hmac({"a": 1}, CLAVE)))
        self.assertFalse(V.comparar_hash(f, V.firma_hmac({"a": 2}, CLAVE)))

    def test_clave_de_idempotencia_determinista(self) -> None:
        a = V.clave_idempotencia("op", "OF-202611-01", {"x": 1, "y": 2})
        self.assertEqual(a, V.clave_idempotencia("op", "OF-202611-01", {"y": 2, "x": 1}))
        self.assertNotEqual(a, V.clave_idempotencia("op", "OF-202611-02", {"x": 1, "y": 2}))

    def test_yaml_no_convierte_fechas(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "a.yaml"
            p.write_text("f: 2026-11-06\nt: 2026-11-06T10:00:00Z\n", encoding="utf-8")
            self.assertEqual({"f": "2026-11-06", "t": "2026-11-06T10:00:00Z"}, V.cargar_yaml(p))


class PruebaLimitesFailClosed(unittest.TestCase):
    """Regla de diseño: una clave de límites necesaria en null bloquea gasto y activación."""

    def setUp(self) -> None:
        _sin_red(self)
        self.lim = V.cargar_yaml(V.DIR_EJEMPLOS / "limites.valido.yaml")
        self.plantilla = V.cargar_yaml(V.RAIZ / "empresa" / "limites.yaml")

    def _sellar(self, d: dict) -> dict:
        d = copy.deepcopy(d)
        d["sello"] = {"hash": V.sello_de_limites(d), "firmado_por": "t", "firmado_en": "2026-11-06T12:00:00Z"}
        return d

    def test_limites_completos_y_sellados_permiten_operar(self) -> None:
        for op in V.CLAVES_CRITICAS:
            if op in ("aumentar_presupuesto", "gastar", "activar", "escalar", "reembolsar_auto", "descubrir", "generar_creativos", "enviar_correo"):
                self.assertTrue(V.evaluar_limites(self.lim, op), op)

    def test_la_plantilla_canonica_bloquea_todo(self) -> None:
        for op in V.CLAVES_CRITICAS:
            res = V.evaluar_limites(self.plantilla, op)
            self.assertFalse(res, op)
            self.assertIn("sello", res.faltantes)
        res = V.evaluar_limites(self.plantilla, "gastar")
        for clave in ("perdida_max_test_por_oferta", "gasto_diario_global", "limite_gasto_cuenta_meta", "cuentas_permitidas", "paises_permitidos"):
            self.assertIn(clave, res.faltantes)

    def test_cada_clave_critica_en_null_bloquea(self) -> None:
        for op in ("gastar", "activar", "aumentar_presupuesto", "escalar", "reembolsar_auto", "descubrir"):
            for clave in V.CLAVES_CRITICAS[op]:
                d = copy.deepcopy(self.lim)
                d[clave] = None if not isinstance(d[clave], list) else []
                d = self._sellar(d)
                res = V.evaluar_limites(d, op)
                self.assertFalse(res, f"{op}: {clave} en null debía bloquear")
                self.assertIn(clave, res.faltantes)

    def test_perdida_max_null_bloquea_aunque_el_resto_este_completo(self) -> None:
        d = self._sellar({**self.lim, "perdida_max_test_por_oferta": None})
        self.assertFalse(V.evaluar_limites(d, "gastar"))
        self.assertFalse(V.evaluar_limites(d, "activar"))

    def test_sin_sello_o_sello_alterado_bloquea(self) -> None:
        d = copy.deepcopy(self.lim)
        d["sello"] = None
        self.assertIn("sello", V.evaluar_limites(d, "gastar").faltantes)
        d = copy.deepcopy(self.lim)
        d["gasto_diario_global"] += 1  # alterar sin volver a sellar
        self.assertFalse(V.evaluar_limites(d, "gastar"))

    def test_macro_nichos_alterados_bloquean(self) -> None:
        d = self._sellar({**self.lim, "macro_nichos_permitidos": ["salud"]})
        self.assertIn("macro_nichos_permitidos", V.evaluar_limites(d, "gastar").faltantes)

    def test_no_cargado_u_operacion_desconocida_bloquea(self) -> None:
        self.assertFalse(V.evaluar_limites(None, "gastar"))
        self.assertFalse(V.evaluar_limites({}, "gastar"))
        self.assertFalse(V.evaluar_limites(self.lim, "inventada"))

    def test_plantilla_sin_alias_antiguos_ni_sufijo_usd(self) -> None:
        for alias in ("gasto_diario_oferta", "gasto_test_oferta", "ofertas_test_simultaneas", "gasto_diario_por_oferta_usd", "mercados_permitidos", "nichos_prohibidos"):
            self.assertNotIn(alias, self.plantilla)
        self.assertEqual([], [k for k in self.plantilla if k.endswith("_usd")])
        self.assertEqual(["salud", "relaciones", "dinero"], self.plantilla["macro_nichos_permitidos"])
        self.assertEqual([], self.plantilla["subnichos_prohibidos"])
        self.assertEqual("1.75", self.plantilla["factor_techo_teorico_diario"])

    def test_cli_limites_de_la_plantilla_sale_con_5(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            codigo = V.main(["limites", str(V.RAIZ / "empresa" / "limites.yaml")])
        self.assertEqual(V.SALIDA_LIMITE, codigo)
        self.assertIn("LIMITES_FALTAN", buf.getvalue())

    def test_cli_limites_completos_sale_con_0(self) -> None:
        with redirect_stdout(io.StringIO()):
            self.assertEqual(0, V.main(["limites", str(V.DIR_EJEMPLOS / "limites.valido.yaml")]))


class PruebaParametrosYPlantillas(unittest.TestCase):
    def setUp(self) -> None:
        self.par = V.cargar_yaml(V.RAIZ / "empresa" / "parametros.yaml")

    def test_todo_parametro_es_hipotesis_con_fuente_y_sin_float(self) -> None:
        self.assertEqual([], V.buscar_floats(self.par))
        n = 0
        for g, claves in self.par["grupos"].items():
            for k, p in claves.items():
                n += 1
                # CT-3 lote A (A-09): un hecho de plataforma (HC-1) no es hipótesis; el grupo `agentes` va TODO en null hasta calibrar (el runner en vivo falla cerrado).
                if (g, k) != ("estadistica", "meta_eventos_aprendizaje_semana"):
                    self.assertTrue(p["hipotesis"], f"{g}.{k}")
                self.assertTrue(p["fuente"], f"{g}.{k}")
                self.assertIsNone(p["ultima_calibracion"])
                if g != "agentes":
                    self.assertIsNotNone(p["valor"], f"{g}.{k}")
                if p.get("rango"):
                    self.assertEqual(2, len(p["rango"]))
        self.assertGreater(n, 250)

    def test_umbrales_unificados_en_un_solo_hogar(self) -> None:
        g = self.par["grupos"]
        self.assertEqual(3, g["testeo"]["k_corte"]["valor"])
        self.assertEqual(15, g["testeo"]["n_dec"]["valor"])
        self.assertNotIn("horas_min_entre_aumentos", {k for grupo in g.values() for k in grupo})   # vive solo en limites
        self.assertEqual("0.3", g["salud_operativa"]["disputas_alerta_pct"]["valor"])
        self.assertEqual(8, g["compliance"]["ngrama_copia_palabras"]["valor"])
        self.assertEqual(7, g["veredicto"]["madurez_dias_extra"]["valor"])
        self.assertEqual("1.25", g["producto"]["cold_run_tolerancia"]["valor"])

    def test_autonomia_inicial_en_n0_para_todas_las_etapas(self) -> None:
        aut = V.cargar_yaml(V.RAIZ / "empresa" / "autonomia.yaml")
        self.assertEqual(set(V.cargar_json(V.DIR_CONTRATOS / "comunes.schema.json")["$defs"]["etapa"]["enum"]), set(aut["nivel_por_etapa"]))
        self.assertEqual({"N0"}, {e["nivel"] for e in aut["nivel_por_etapa"].values()})

    def test_plantillas_de_empresa_validan(self) -> None:
        self.assertEqual([], [str(h) for h in V.validar_cartera_de_empresa().errores])


class PruebaGatesYEstados(unittest.TestCase):
    def setUp(self) -> None:
        self.g = V.cargar_gates()

    def test_tabla_coherente_con_backbone_5_5(self) -> None:
        ge = lambda k, n: V.gate_esperado(k, n, self.g)
        self.assertEqual("H", ge("etapa:D3", "N2"))                        # oferta
        self.assertEqual("H", ge("accion:publicar_landing", "N2"))         # publicar landing
        self.assertEqual("H", ge("accion:activar_campana", "N2"))          # activar campaña
        self.assertEqual("H", ge("accion:subir_presupuesto_d9", "N2"))     # reconcilia a O0 (que ponía A)
        self.assertEqual("H", ge("accion:lanzamiento_pais_idioma_nuevo", "N2"))
        self.assertEqual("H", ge("etapa:M1", "N2"))
        self.assertEqual("H", ge("etapa:D1", "N3"))                        # elegir candidato: H hasta N3
        for n in ("N0", "N1", "N2"):
            self.assertEqual("NA", ge("accion:aumentar_presupuesto_d8", n))   # D8 aumenta solo desde N3
        self.assertEqual("A", ge("accion:aumentar_presupuesto_d8", "N3"))
        self.assertEqual("A", ge("accion:pausar", "N2"))                   # D8 puede pausar desde N2
        for n in V.NIVELES:
            self.assertEqual("H", ge("accion:reactivar_tras_pausa", n))    # nunca automático
            self.assertEqual("H", ge("accion:subir_presupuesto_sobre_tope", n))
            self.assertEqual("H", ge("accion:cambiar_limites", n))
        for n in V.NIVELES[:2]:
            self.assertEqual("H", ge("etapa:D4", n))                       # N0/N1: el dueño revisa todo

    def test_los_gates_nunca_se_endurecen_al_subir_de_nivel(self) -> None:
        for clave, e in self.g["entradas"].items():
            previos = [ORDEN_GATE[e["gate"][n]] for n in V.NIVELES if e["gate"][n] != "NA"]
            self.assertEqual(sorted(previos, reverse=True), previos, clave)

    def test_toda_etapa_tiene_gate_y_cinco_niveles(self) -> None:
        for et in ("O0", "D0", "M1", "D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9", "D10", "F1", "F2"):
            self.assertIn(f"etapa:{et}", self.g["entradas"])
        for e in self.g["entradas"].values():
            self.assertEqual(set(V.NIVELES), set(e["gate"]))

    def test_transiciones_de_estado(self) -> None:
        validas = [("pendiente", "en_progreso"), ("en_progreso", "en_QA"), ("en_QA", "aprobado"), ("en_QA", "en_progreso"), ("en_QA", "escalado"),
                   ("escalado", "aprobado"), ("aprobado", "pendiente"), ("bloqueado", "en_progreso")]
        for de, a in validas:
            self.assertTrue(V.transicion_valida(de, a), (de, a))
        invalidas = [("pendiente", "aprobado"), ("aprobado", "en_QA"), ("pendiente", "en_QA"), ("bloqueado", "aprobado"), ("en_progreso", "aprobado"), ("aprobado", "aprobado")]
        for de, a in invalidas:
            self.assertFalse(V.transicion_valida(de, a), (de, a))

    def test_transiciones_de_fase_de_la_oferta(self) -> None:
        self.assertTrue(V.transicion_fase_valida("listo_para_activar", "en_test"))
        self.assertTrue(V.transicion_fase_valida("pausada", "en_test"))
        self.assertFalse(V.transicion_fase_valida("borrador", "en_test"))        # no se salta la construcción
        self.assertFalse(V.transicion_fase_valida("fallida", "en_test"))        # una oferta fallida no se reactiva
        self.assertFalse(V.transicion_fase_valida("retirada", "en_test"))
        self.assertFalse(V.transicion_fase_valida("en_test", "escalando"))      # primero validada

    def test_infra_verde_con_reloj_inyectable(self) -> None:
        estado = V.cargar_json(V.DIR_EJEMPLOS / "infra_estado.valido.json")
        self.assertFalse(V.infra_verde(estado, lambda: dt.datetime(2026, 11, 9, 7, 0, tzinfo=dt.timezone.utc), 6)[0])  # sin modo vivo (B03)
        estado["modo"] = "vivo"
        t0 = dt.datetime(2026, 11, 9, 6, 0, 0, tzinfo=dt.timezone.utc)
        self.assertTrue(V.infra_verde(estado, lambda: t0 + dt.timedelta(hours=5), 6)[0])
        self.assertTrue(V.infra_verde(estado, lambda: t0 + dt.timedelta(hours=6), 6)[0])
        self.assertFalse(V.infra_verde(estado, lambda: t0 + dt.timedelta(hours=6, seconds=1), 6)[0])
        rojo = {**estado, "semaforo": "ROJO"}
        self.assertFalse(V.infra_verde(rojo, lambda: t0, 6)[0])
        # B03: modo simulado/prueba, ítem ROJO escondido, futuro, sin ítems y tope de 6 h fijo en código
        for malo in ({**estado, "modo": "simulado"}, {**estado, "modo": "prueba"},
                     {**estado, "items": [{**estado["items"][0], "estado": "ROJO"}, *estado["items"][1:]]},
                     {**estado, "generado_en": "2099-01-01T00:00:00Z", "valido_hasta": "2099-01-01T06:00:00Z"},
                     {**estado, "items": []}):
            self.assertFalse(V.infra_verde(malo, lambda: t0, 6)[0], malo.get("modo"))
        self.assertFalse(V.infra_verde(estado, lambda: t0 + dt.timedelta(hours=7), 24)[0])  # max_horas > 6 se recorta a 6
        self.assertTrue(V.semaforo_coherente(estado))
        estado2 = copy.deepcopy(estado)
        estado2["items"][0]["estado"] = "ROJO"
        self.assertFalse(V.semaforo_coherente(estado2))


class PruebaOfertaEjemplo(unittest.TestCase):
    """La oferta completa de ejemplo debe pasar esquema y TODAS las reglas cruzadas."""

    def setUp(self) -> None:
        _sin_red(self)

    def _validar(self, d: Path):
        return V.validar_oferta(d, limites=V.limites_de_prueba(), autonomia=V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml"), clave_firma=CLAVE)

    def test_oferta_de_ejemplo_valida(self) -> None:
        inf = self._validar(V.RAIZ / "ofertas" / "_ejemplo")
        self.assertEqual([], [str(h) for h in inf.errores])
        self.assertEqual([], [str(h) for h in inf.hallazgos])   # ni siquiera avisos
        self.assertGreaterEqual(inf.verificados, 40)

    def test_la_oferta_de_ejemplo_tiene_todos_los_artefactos(self) -> None:
        base = V.RAIZ / "ofertas" / "_ejemplo"
        for rel in (set(V.ESQUEMA_DE_ARCHIVO) | set(V.ESQUEMA_DE_JSONL)) - V.ARCHIVOS_POSTERIORES_AL_BORRADOR:
            self.assertTrue((base / rel).is_file(), rel)
        for e in ("m1", "d1", "d2", "d3", "d4", "d5", "d6", "d7", "x1-d5", "x1-d6", "x1-d7"):
            self.assertTrue((base / "qa" / f"{e}-v1.json").is_file(), e)
        self.assertTrue((base / "04-producto" / "entregables" / "muestras" / "muestra-guia-v1.md").is_file())

    def test_caso_verde_dinero_sin_claims(self) -> None:
        base = V.RAIZ / "ofertas" / "_ejemplo"
        of = V.cargar_json(base / "03-oferta" / "oferta.json")
        self.assertEqual("dinero", of["macro_nicho"])
        self.assertEqual("verde", of["riesgo"]["nivel"])
        self.assertEqual(("es-ES", "EUR"), (of["locale"], of["moneda"]))
        camp = V.cargar_json(base / "07-campana" / "campana.json")
        self.assertEqual("borrador", camp["estado"])
        self.assertIsNone(camp["ids_meta"])
        self.assertNotIn("|", json.dumps(camp))

    def test_cli_valida_la_oferta_de_ejemplo_con_codigo_0(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(0, V.main([]))
        self.assertIn("Oferta", buf.getvalue())

    def test_cli_uso_incorrecto_sale_con_2(self) -> None:
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(V.SALIDA_USO, V.main(["comando-inexistente"]))

    def test_sin_limites_el_borrador_pasa_con_aviso_y_no_se_puede_activar(self) -> None:
        plantilla = V.cargar_yaml(V.RAIZ / "empresa" / "limites.yaml")
        inf = V.validar_oferta(V.RAIZ / "ofertas" / "_ejemplo", limites=plantilla, autonomia=V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml"), clave_firma=CLAVE)
        self.assertEqual([], [str(h) for h in inf.errores])
        self.assertIn("X10_LIMITES", {h.codigo for h in inf.hallazgos if h.nivel == "AVISO"})


class PruebaReglasCruzadas(unittest.TestCase):
    """Cada prueba rompe UNA cosa en una copia de la oferta de ejemplo y exige el código de la regla."""

    def setUp(self) -> None:
        _sin_red(self)
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.dir = Path(self._t.name) / "_ejemplo"
        shutil.copytree(V.RAIZ / "ofertas" / "_ejemplo", self.dir)
        self.lim = V.limites_de_prueba()
        self.aut = V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml")

    # utilidades
    def j(self, rel: str):
        return V.cargar_json(self.dir / rel)

    def w(self, rel: str, obj) -> None:
        (self.dir / rel).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def codigos(self, limites=None, autonomia=None) -> set[str]:
        inf = V.validar_oferta(self.dir, limites=limites if limites is not None else self.lim, autonomia=autonomia or self.aut, clave_firma=CLAVE)
        return {h.codigo for h in inf.errores}

    def reseller_campana(self, camp: dict) -> dict:
        camp["hash_config"] = V.hash_objeto(camp, excluir=("hash_config",))
        return camp

    def assertDetecta(self, codigo: str, **kw) -> None:
        self.assertIn(codigo, self.codigos(**kw))

    # --- identidad
    def test_base_sin_errores(self) -> None:
        self.assertEqual(set(), self.codigos())

    def test_oferta_id_distinto_en_un_artefacto(self) -> None:
        m = self.j("mercado.json"); m["oferta_id"] = "OF-202611-02"; self.w("mercado.json", m)
        self.assertDetecta("X01_ID")

    def test_familia_id_distinta(self) -> None:
        m = self.j("03-oferta/oferta.json"); m["familia_id"] = "FAM-202611-09"; self.w("03-oferta/oferta.json", m)
        self.assertDetecta("X01_ID")

    # --- hashes
    def test_hash_del_brief_alterado(self) -> None:
        txt = (self.dir / "00-brief.yaml").read_text(encoding="utf-8").replace("tema_semilla: reincorporación laboral tras una pausa larga", "tema_semilla: otro tema")
        (self.dir / "00-brief.yaml").write_text(txt, encoding="utf-8")
        self.assertDetecta("X04_HASH_BRIEF")

    def test_producto_alterado_rompe_hash_de_item_y_de_etapa(self) -> None:
        p = self.dir / "04-producto/entregables/puente-de-la-pausa-v1-guia.md"
        p.write_text(p.read_text(encoding="utf-8") + "\nLínea añadida.\n", encoding="utf-8")
        c = self.codigos()
        self.assertIn("X05_HASH_ITEM", c)

    def test_oferta_alterada_invalida_el_hash_de_salida_de_d3(self) -> None:
        o = self.j("03-oferta/oferta.json"); o["supuestos"].append("otro"); self.w("03-oferta/oferta.json", o)
        c = self.codigos()
        self.assertIn("X02_HASH_ETAPA", c)
        self.assertIn("X03_HASH_QA", c)

    def test_hash_de_campana_alterado(self) -> None:
        camp = self.j("07-campana/campana.json"); camp["version"] = "v2"; self.w("07-campana/campana.json", camp)
        self.assertDetecta("X02_HASH_CAMPANA")

    def test_landing_modificada_tras_el_sello(self) -> None:
        p = self.dir / "05-landing/sitio/index.html"
        p.write_text(p.read_text(encoding="utf-8").replace("19,90", "9,90"), encoding="utf-8")
        self.assertDetecta("X06_HASH_LANDING")

    def test_asset_alterado(self) -> None:
        p = self.dir / "06-creativos/assets/c01-hueco_img_h1_v1.png"
        p.write_bytes(p.read_bytes() + b"0")
        self.assertDetecta("X06_HASH_ASSET")

    def test_texto_crudo_alterado(self) -> None:
        (self.dir / "01-descubrimiento/crudo/EV-01.txt").write_text("otro texto\n", encoding="utf-8")
        self.assertDetecta("X05_HASH_CRUDO")

    def test_firma_de_etapa_falsificada(self) -> None:
        e = self.j("estado.json"); e["etapas"]["D3"]["aprobado_por"]["firma"] = "hmac-sha256:" + "1" * 64; self.w("estado.json", e)
        self.assertDetecta("X02_FIRMA_ETAPA")

    # --- rutas
    def test_ruta_citada_inexistente(self) -> None:
        pr = self.j("04-producto/producto.json"); pr["items"][0]["archivo"] = "entregables/no-existe.md"; self.w("04-producto/producto.json", pr)
        self.assertDetecta("X07_RUTA")

    def test_qa_ref_inexistente_en_el_paquete(self) -> None:
        pq = self.j("06-creativos/paquete.json"); pq["qa_ref"] = "qa/no-existe.json"; self.w("06-creativos/paquete.json", pq)
        self.assertDetecta("X07_RUTA")

    # --- nombres y URL de Meta
    def test_nombre_de_campana_con_barra_vertical(self) -> None:
        camp = self.j("07-campana/campana.json"); camp["nombres"]["campana"] = camp["nombres"]["campana"].replace("_", "|"); self.w("07-campana/campana.json", self.reseller_campana(camp))
        self.assertDetecta("ESQUEMA")

    def test_estructura_del_nombre_distinta_de_la_campana(self) -> None:
        camp = self.j("07-campana/campana.json"); camp["estructura"] = "ABO"; self.w("07-campana/campana.json", self.reseller_campana(camp))
        self.assertDetecta("X08_NOMBRE")

    def test_anuncio_de_campana_ausente_en_el_paquete(self) -> None:
        camp = self.j("07-campana/campana.json")
        camp["anuncios"][0]["ad_name"] = "c09-otro_img_h1_v1"; camp["nombres"]["anuncios"][0] = "c09-otro_img_h1_v1"
        self.w("07-campana/campana.json", self.reseller_campana(camp))
        self.assertDetecta("X08_NOMBRE")

    def test_url_sin_adid(self) -> None:
        camp = self.j("07-campana/campana.json")
        camp["url"]["plantilla"] = camp["url"]["plantilla"].replace("&adid={{ad.id}}", "")
        self.w("07-campana/campana.json", self.reseller_campana(camp))
        self.assertDetecta("X09_URL")

    def test_url_con_utm_content_fijo_en_vez_de_macro(self) -> None:
        camp = self.j("07-campana/campana.json")
        camp["url"]["plantilla"] = camp["url"]["plantilla"].replace("{{ad.name}}", "fijo")
        self.w("07-campana/campana.json", self.reseller_campana(camp))
        self.assertDetecta("X09_URL")

    # --- presupuesto y límites
    def test_presupuesto_sobre_el_tope_de_gasto_total(self) -> None:
        camp = self.j("07-campana/campana.json"); p = camp["presupuesto"]
        p["diario"] += 100; p["total_test"] = p["diario"] * p["dias"]
        self.w("07-campana/campana.json", self.reseller_campana(camp))
        self.assertDetecta("X10_LIMITES")

    def test_tope_exacto_pasa_y_un_centavo_mas_falla(self) -> None:
        lim = copy.deepcopy(self.lim)
        total = self.j("07-campana/campana.json")["presupuesto"]["spend_cap"]  # el techo real de pérdida es el spend_cap (B05)
        lim["gasto_total_test_por_oferta"] = total
        lim["perdida_max_test_por_oferta"] = total
        lim["sello"]["hash"] = V.sello_de_limites(lim)
        self.assertNotIn("X10_LIMITES", self.codigos(limites=lim))
        lim["gasto_total_test_por_oferta"] = total - 1
        lim["perdida_max_test_por_oferta"] = total - 1
        lim["sello"]["hash"] = V.sello_de_limites(lim)
        self.assertDetecta("X10_LIMITES", limites=lim)

    def test_moneda_del_presupuesto_distinta_de_la_de_limites(self) -> None:
        lim = copy.deepcopy(self.lim); lim["moneda_limites"] = "USD"; lim["sello"]["hash"] = V.sello_de_limites(lim)
        self.assertDetecta("X10_LIMITES", limites=lim)

    def test_techo_teorico_incorrecto(self) -> None:
        camp = self.j("07-campana/campana.json"); camp["presupuesto"]["max_teorico_diario"] -= 1; self.w("07-campana/campana.json", self.reseller_campana(camp))
        self.assertDetecta("X10_LIMITES")

    def test_pais_fuera_de_los_permitidos(self) -> None:
        camp = self.j("07-campana/campana.json"); camp["paises"] = ["ES", "PL"]; self.w("07-campana/campana.json", self.reseller_campana(camp))
        self.assertDetecta("X10_LIMITES")

    def test_campana_activa_con_limites_sin_completar_sale_con_5(self) -> None:
        camp = self.j("07-campana/campana.json"); camp["estado"] = "activa"; self.w("07-campana/campana.json", self.reseller_campana(camp))
        plantilla = V.cargar_yaml(V.RAIZ / "empresa" / "limites.yaml")
        inf = V.validar_oferta(self.dir, limites=plantilla, autonomia=self.aut, clave_firma=CLAVE)
        errs = [h for h in inf.errores if h.codigo == "X10_LIMITES"]
        self.assertTrue(errs)
        self.assertTrue(all(h.salida == V.SALIDA_LIMITE for h in errs))

    def test_campana_activa_con_limites_completos_pasa_esta_regla(self) -> None:
        camp = self.j("07-campana/campana.json"); camp["estado"] = "activa"; self.w("07-campana/campana.json", self.reseller_campana(camp))
        self.assertNotIn("X10_LIMITES", self.codigos())

    def test_perdida_max_de_la_economia_supera_el_limite(self) -> None:
        lim = copy.deepcopy(self.lim); lim["perdida_max_test_por_oferta"] = 1000; lim["sello"]["hash"] = V.sello_de_limites(lim)
        self.assertDetecta("X10_LIMITES", limites=lim)

    def test_el_brief_no_puede_ampliar_los_limites(self) -> None:
        lim = copy.deepcopy(self.lim); lim["subnichos_prohibidos"] = ["empleo-y-carrera"]; lim["sello"]["hash"] = V.sello_de_limites(lim)
        self.assertDetecta("X12_NICHO", limites=lim)

    # --- gates y niveles
    def test_gate_distinto_de_la_tabla(self) -> None:
        e = self.j("estado.json"); e["etapas"]["D3"]["gate"] = "A"; self.w("estado.json", e)
        self.assertDetecta("X11_GATE")

    def test_nivel_por_encima_de_autonomia(self) -> None:
        aut = copy.deepcopy(self.aut); aut["nivel_por_etapa"]["D3"]["nivel"] = "N1"
        self.assertDetecta("X11_NIVEL", autonomia=aut)

    def test_gate_h_aprobado_sin_firma_humana(self) -> None:
        e = self.j("estado.json"); e["etapas"]["D3"]["aprobado_por"] = {"tipo": "qa_pass", "id": "d3-qa", "fecha": "2026-11-07T11:00:00Z", "firma": None}; self.w("estado.json", e)
        self.assertDetecta("X11_GATE")

    def test_etapa_aprobada_con_entrada_obsoleta(self) -> None:
        e = self.j("estado.json"); e["etapas"]["D4"]["entradas"]["D3"] = "sha256:" + "9" * 64; self.w("estado.json", e)
        self.assertDetecta("X24_DEP")

    def test_gate_pendiente_fuera_de_en_qa(self) -> None:
        e = self.j("estado.json"); e["etapas"]["D8"]["gate_pendiente"] = True; self.w("estado.json", e)
        self.assertDetecta("X11_ESTADO")

    # --- nichos y riesgo
    def test_riesgo_nivel_menor_que_el_maximo_de_los_ejes(self) -> None:
        o = self.j("03-oferta/oferta.json"); o["riesgo"]["E"] = "amarillo"; self.w("03-oferta/oferta.json", o)
        self.assertDetecta("X13_RIESGO")

    def test_candidato_rojo_no_avanza(self) -> None:
        c = self.j("01-descubrimiento/candidatos.json")
        r = c["candidatos"][1]["riesgo"]; r["P"] = "rojo"; r["nivel"] = "rojo"
        self.w("01-descubrimiento/candidatos.json", c)
        self.assertDetecta("X13_RIESGO")

    def test_reencuadre_sin_mejora(self) -> None:
        o = self.j("03-oferta/oferta.json"); o["riesgo"]["reencuadre_aplicado"]["nivel_original"] = "verde"; self.w("03-oferta/oferta.json", o)
        self.assertDetecta("X13_RIESGO")

    def test_amarillo_exige_gate_legal(self) -> None:
        o = self.j("03-oferta/oferta.json"); o["riesgo"].update({"E": "amarillo", "nivel": "amarillo"}); o["riesgo"]["reencuadre_aplicado"]["nivel_original"] = "rojo"
        self.w("03-oferta/oferta.json", o)
        self.assertDetecta("X13_RIESGO")

    def test_oferta_con_mas_riesgo_que_su_candidato(self) -> None:
        c = self.j("01-descubrimiento/candidatos.json"); c["candidatos"][0]["riesgo"].update({"P": "verde"}); self.w("01-descubrimiento/candidatos.json", c)
        o = self.j("03-oferta/oferta.json"); o["riesgo"].update({"E": "amarillo", "nivel": "amarillo"}); o["requiere_gate_humano_legal"] = True; o["riesgo"]["reencuadre_aplicado"]["nivel_original"] = "rojo"
        self.w("03-oferta/oferta.json", o)
        self.assertDetecta("X13_RIESGO")

    def test_macro_nicho_de_la_oferta_distinto_del_candidato(self) -> None:
        o = self.j("03-oferta/oferta.json"); o["macro_nicho"] = "relaciones"; self.w("03-oferta/oferta.json", o)
        self.assertDetecta("X12_NICHO")

    def test_macro_nicho_fuera_del_marco_no_pasa_el_esquema(self) -> None:
        o = self.j("03-oferta/oferta.json"); o["macro_nicho"] = "mascotas"; self.w("03-oferta/oferta.json", o)
        self.assertDetecta("ESQUEMA")

    # --- economía y tiempos
    def test_economia_recalculada_no_coincide(self) -> None:
        e = self.j("03-oferta/economia.json"); e["mc"]["monto"] += 1; self.w("03-oferta/economia.json", e)
        self.assertDetecta("X14_ECONOMIA")

    def test_veredicto_factible_con_razon_insuficiente(self) -> None:
        e = self.j("03-oferta/economia.json")
        e["entradas_usadas"]["escenarios"]["central"]["cpm"]["monto"] = 900
        e["cpa_real"]["central"]["monto"] = 2556
        e["razon"] = f"{e['mc']['monto'] / 2556:.2f}"
        self.w("03-oferta/economia.json", e)
        self.assertDetecta("X14_ECONOMIA")

    def test_precio_de_la_oferta_distinto_del_checkout(self) -> None:
        c = self.j("05-landing/checkout.json"); c["precio"]["monto"] = 1490; self.w("05-landing/checkout.json", c)
        self.assertDetecta("X16_CHECKOUT")

    def test_garantia_menor_que_el_minimo(self) -> None:
        o = self.j("03-oferta/oferta.json"); o["garantia"]["dias"] = 7; self.w("03-oferta/oferta.json", o)
        c = self.j("05-landing/checkout.json"); c["garantia_dias"] = 7; self.w("05-landing/checkout.json", c)
        self.assertDetecta("X16_CHECKOUT")

    def test_tiempo_prometido_distinto_entre_d3_y_d4(self) -> None:
        p = self.j("04-producto/producto.json"); p["tiempos"]["prometido_min"] = 60; self.w("04-producto/producto.json", p)
        self.assertDetecta("X15_TIEMPO")

    def test_tiempo_medido_supera_la_tolerancia(self) -> None:
        p = self.j("04-producto/producto.json"); p["tiempos"].update({"lectura_min": 60, "ejecucion_min": 60, "total_min": 120, "base": "cold_run_humano"}); self.w("04-producto/producto.json", p)
        self.assertDetecta("X15_TIEMPO")

    def test_tiempo_estimado_no_puede_superar_el_prometido_pero_el_medido_tiene_tolerancia(self) -> None:
        p = self.j("04-producto/producto.json"); p["tiempos"].update({"lectura_min": 30, "ejecucion_min": 70, "total_min": 100}); self.w("04-producto/producto.json", p)
        self.assertDetecta("X15_TIEMPO")                      # estimado: 100 > 90
        p["tiempos"]["base"] = "cold_run_humano"; self.w("04-producto/producto.json", p)
        self.assertNotIn("X15_TIEMPO", self.codigos())         # medido: 100 <= 1,25 x 90

    def test_tiempo_de_diseno_supera_el_factor(self) -> None:
        o = self.j("03-oferta/oferta.json"); o["vehiculo"]["tiempo_consumo_min"] = 120; self.w("03-oferta/oferta.json", o)
        self.assertDetecta("X15_TIEMPO")

    # --- tracking
    def test_purchase_sin_deduplicacion(self) -> None:
        t = self.j("05-landing/tracking.json")
        for ev in t["eventos"]:
            if ev["nombre"] == "Purchase":
                ev["canal"] = "pixel"
        self.w("05-landing/tracking.json", t)
        self.assertDetecta("X17_TRACKING")

    def test_event_id_distinto_de_la_regla(self) -> None:
        t = self.j("05-landing/tracking.json")
        for ev in t["eventos"]:
            if ev["nombre"] == "Purchase":
                ev["event_id_regla"] = "p_<visitor_id>"
        self.w("05-landing/tracking.json", t)
        self.assertDetecta("X17_TRACKING")

    def test_dato_de_salud_en_el_nombre_de_un_evento(self) -> None:
        t = self.j("05-landing/tracking.json"); t["eventos"][1]["parametros_permitidos"].append("diagnostico"); self.w("05-landing/tracking.json", t)
        self.assertDetecta("ESQUEMA")  # lista cerrada de parametros de evento (M10)

    def test_ruta_o_dominio_con_termino_sensible(self) -> None:
        r = self.j("05-landing/rutas.json"); r["/a/ansiedad-laboral"] = "x"; self.w("05-landing/rutas.json", r)
        self.assertDetecta("X17_SENSIBLE")

    # --- claims
    def test_claim_de_ingresos_en_un_copy(self) -> None:
        pq = self.j("06-creativos/paquete.json"); pq["anuncios"][0]["copy"]["texto_principal"] = "Aprende a ganar dinero desde casa"; self.w("06-creativos/paquete.json", pq)
        self.assertDetecta("X19_CLAIM")

    def test_claim_de_salud_en_la_promesa(self) -> None:
        o = self.j("03-oferta/oferta.json"); o["promesa"]["subtitulo"] = "Una guía para curar tu ansiedad"; self.w("03-oferta/oferta.json", o)
        self.assertDetecta("X19_CLAIM")

    def test_claim_id_no_permitido_por_la_oferta(self) -> None:
        pq = self.j("06-creativos/paquete.json"); pq["anuncios"][0]["claim_ids"].append("inventado"); self.w("06-creativos/paquete.json", pq)
        self.assertDetecta("X06_CLAIM")

    def test_anuncio_con_lint_x1_en_fail(self) -> None:
        pq = self.j("06-creativos/paquete.json"); pq["anuncios"][0]["lint_x1"] = "FAIL"; self.w("06-creativos/paquete.json", pq)
        self.assertDetecta("X06_X1")

    # --- órdenes, veredicto, señales
    def _orden(self) -> dict:
        return V.cargar_jsonl(self.dir / "08-operacion/ordenes_presupuesto.jsonl")[0]

    def _w_orden(self, o: dict) -> None:
        o["idempotency_key"] = V.clave_idempotencia("orden_presupuesto", o["oferta_id"], {"orden_id": o["orden_id"], "accion": o["accion"], "despues": o["despues"]["monto"]})
        (self.dir / "08-operacion/ordenes_presupuesto.jsonl").write_text(json.dumps(o, ensure_ascii=False) + "\n", encoding="utf-8")

    def test_d8_no_puede_emitir_con_plan_de_d9_vigente(self) -> None:
        o = self._orden(); o["plan_ref"] = "09-escalado/plan.json"; self._w_orden(o)
        self.assertDetecta("X21_ORDEN")

    def test_d9_sin_plan_no_puede_emitir(self) -> None:
        o = self._orden(); o["emisor"] = "D9"; self._w_orden(o)
        self.assertDetecta("X21_ORDEN")

    def test_d8_aumentando_presupuesto_en_n2_esta_prohibido(self) -> None:
        o = self._orden(); o.update({"accion": "aumentar", "despues": {"monto": 3312, "moneda": "EUR"}, "delta_pct": "20", "horas_desde_ultimo_aumento": 100}); self._w_orden(o)
        self.assertDetecta("X11_GATE")

    def test_aumento_mayor_que_el_maximo_por_paso(self) -> None:
        o = self._orden(); o.update({"emisor": "D9", "plan_ref": "09-escalado/plan.json", "accion": "aumentar", "despues": {"monto": 3588, "moneda": "EUR"}, "delta_pct": "30", "horas_desde_ultimo_aumento": 100,
                                    "gate": {"accion_gate": "accion:subir_presupuesto_d9", "nivel": "N3", "gate": "A"}}); self._w_orden(o)
        c = self.codigos()
        self.assertIn("X10_LIMITES", c)

    def test_aumento_antes_de_las_horas_minimas(self) -> None:
        o = self._orden(); o.update({"emisor": "D9", "plan_ref": "09-escalado/plan.json", "accion": "aumentar", "despues": {"monto": 3312, "moneda": "EUR"}, "delta_pct": "20", "horas_desde_ultimo_aumento": 48,
                                    "gate": {"accion_gate": "accion:subir_presupuesto_d9", "nivel": "N3", "gate": "A"}}); self._w_orden(o)
        self.assertDetecta("X10_LIMITES")

    def test_aumento_valido_de_d9_en_n3_con_limites_pasa(self) -> None:
        o = self._orden(); o.update({"emisor": "D9", "plan_ref": "09-escalado/plan.json", "accion": "aumentar", "despues": {"monto": 3312, "moneda": "EUR"}, "delta_pct": "20", "horas_desde_ultimo_aumento": 72,
                                    "gate": {"accion_gate": "accion:subir_presupuesto_d9", "nivel": "N3", "gate": "A"}}); self._w_orden(o)
        lim = copy.deepcopy(self.lim); lim["gasto_diario_por_oferta"] = 8000; lim["gasto_diario_global"] = 16000; lim["sello"]["hash"] = V.sello_de_limites(lim)
        c = self.codigos(limites=lim)
        self.assertNotIn("X10_LIMITES", c)
        self.assertNotIn("X11_GATE", c)
        self.assertNotIn("X21_ORDEN", c)

    def test_aumento_que_supera_el_techo_diario_por_oferta(self) -> None:
        o = self._orden(); o.update({"emisor": "D9", "plan_ref": "09-escalado/plan.json", "accion": "aumentar", "despues": {"monto": 3312, "moneda": "EUR"}, "delta_pct": "20", "horas_desde_ultimo_aumento": 72,
                                    "gate": {"accion_gate": "accion:subir_presupuesto_d9", "nivel": "N3", "gate": "A"}}); self._w_orden(o)
        self.assertDetecta("X10_LIMITES")   # 1,75 x 3312 = 5796 > gasto_diario_por_oferta (5000)

    def test_delta_de_la_orden_mal_calculado(self) -> None:
        o = self._orden(); o["delta_pct"] = "5"; self._w_orden(o)
        self.assertDetecta("X21_ORDEN")

    def test_idempotency_key_no_determinista(self) -> None:
        o = self._orden(); o["idempotency_key"] = "sha256:" + "5" * 64
        (self.dir / "08-operacion/ordenes_presupuesto.jsonl").write_text(json.dumps(o) + "\n", encoding="utf-8")
        self.assertDetecta("X21_ORDEN")

    def test_validada_sin_compras_suficientes(self) -> None:
        v = self.j("08-operacion/veredicto_oferta.json"); v["estado"] = "VALIDADA"; self.w("08-operacion/veredicto_oferta.json", v)
        self.assertDetecta("X20_VEREDICTO")

    def test_validada_con_cpa_sobre_el_objetivo(self) -> None:
        v = self.j("08-operacion/veredicto_oferta.json"); ev = v["evidencia"]
        v["estado"] = "VALIDADA"; ev.update({"compras_brutas": 20, "compras_netas": 18, "reembolsos": 2, "dias_con_datos": 8}); self.w("08-operacion/veredicto_oferta.json", v)
        self.assertDetecta("X20_VEREDICTO")

    def test_validada_correcta_pasa_esa_regla(self) -> None:
        v = self.j("08-operacion/veredicto_oferta.json"); ev = v["evidencia"]
        v["estado"] = "VALIDADA"; ev.update({"compras_brutas": 20, "compras_netas": 18, "reembolsos": 2, "dias_con_datos": 8, "cpa_neto": {"monto": 1000, "moneda": "EUR"}}); self.w("08-operacion/veredicto_oferta.json", v)
        self.assertNotIn("X20_VEREDICTO", self.codigos())

    def test_madurez_distinta_de_garantia_mas_extra(self) -> None:
        v = self.j("08-operacion/veredicto_oferta.json"); v["evidencia"]["madurez_dias"] = 14; self.w("08-operacion/veredicto_oferta.json", v)
        self.assertDetecta("X20_VEREDICTO")

    def test_compras_netas_mal_calculadas(self) -> None:
        v = self.j("08-operacion/veredicto_oferta.json"); v["evidencia"]["compras_netas"] = 5; self.w("08-operacion/veredicto_oferta.json", v)
        self.assertDetecta("X20_VEREDICTO")

    def test_senal_con_umbral_distinto_de_parametros(self) -> None:
        s = self.j("10-postcompra/senal_pausa.json"); s["umbrales_usados"]["disputas_alerta_pct"] = "0.5"; self.w("10-postcompra/senal_pausa.json", s)
        self.assertDetecta("X22_SENAL")

    def test_senal_con_pausa_distinta_de_limites(self) -> None:
        s = self.j("10-postcompra/senal_pausa.json"); s["umbrales_usados"]["ratio_disputas_pausa"] = "0.02"; self.w("10-postcompra/senal_pausa.json", s)
        self.assertDetecta("X22_SENAL")

    def test_reembolso_automatico_sobre_el_maximo(self) -> None:
        lim = copy.deepcopy(self.lim); lim["reembolso_auto_max"] = 1000; lim["sello"]["hash"] = V.sello_de_limites(lim)
        self.assertDetecta("X10_LIMITES", limites=lim)

    def test_reembolso_dentro_de_garantia_incoherente(self) -> None:
        r = V.cargar_jsonl(self.dir / "10-postcompra/reembolsos.jsonl")[0]; r["dias_desde_compra"] = 30
        (self.dir / "10-postcompra/reembolsos.jsonl").write_text(json.dumps(r) + "\n", encoding="utf-8")
        self.assertDetecta("X20_REEMBOLSO")

    # --- QA
    def test_pass_con_bloqueante_abierto(self) -> None:
        q = self.j("qa/d3-v1.json"); q["hallazgos"][0].update({"severidad": "BLOQUEANTE", "estado": "abierto"}); self.w("qa/d3-v1.json", q)
        self.assertDetecta("X18_QA")

    def test_pass_con_puntaje_bajo_el_umbral(self) -> None:
        q = self.j("qa/d3-v1.json"); q["umbral"] = "4.9"; self.w("qa/d3-v1.json", q)
        self.assertDetecta("X18_QA")

    def test_puntaje_global_no_coincide_con_los_items(self) -> None:
        q = self.j("qa/d3-v1.json"); q["puntaje_global"] = "2.00"; q["umbral"] = "1.00"; self.w("qa/d3-v1.json", q)
        self.assertDetecta("X18_QA")

    def test_qa_con_menos_de_tres_hallazgos_sin_justificar_no_pasa_el_esquema(self) -> None:
        q = self.j("qa/d3-v1.json"); q["hallazgos"] = q["hallazgos"][:1]; self.w("qa/d3-v1.json", q)
        self.assertDetecta("ESQUEMA")

    def test_qa_con_menos_de_tres_hallazgos_pero_justificado_pasa(self) -> None:
        q = self.j("qa/d3-v1.json"); q["hallazgos"] = q["hallazgos"][:1]; q["justificacion_sin_hallazgos"] = "Se revisaron los 12 campos contra el contrato y las 4 fuentes citadas; no hay más defectos."; self.w("qa/d3-v1.json", q)
        self.assertNotIn("ESQUEMA", self.codigos())

    def test_qa_con_nombre_de_archivo_incorrecto(self) -> None:
        shutil.move(self.dir / "qa/d3-v1.json", self.dir / "qa/oferta-v1.json")
        self.assertDetecta("X18_QA")

    def test_qa_sobre_artefacto_alterado(self) -> None:
        q = self.j("qa/d3-v1.json"); q["artefacto_sha256"] = "sha256:" + "7" * 64; self.w("qa/d3-v1.json", q)
        self.assertDetecta("X03_HASH_QA")

    def test_x1_fail_bloquea_aunque_el_qa_diga_pass(self) -> None:
        q = self.j("qa/d6-v1.json"); q["x1"]["veredicto"] = "FAIL"; self.w("qa/d6-v1.json", q)
        self.assertDetecta("X18_QA")

    # --- registro y floats
    def test_cadena_de_registro_rota(self) -> None:
        lineas = V.cargar_jsonl(self.dir / "_empresa/registro.jsonl")
        lineas[1]["entrada_resumen"] = "alterado"
        (self.dir / "_empresa/registro.jsonl").write_text("".join(json.dumps(l, ensure_ascii=False) + "\n" for l in lineas), encoding="utf-8")
        self.assertDetecta("X25_REGISTRO")
        self.assertEqual([], V.cadena_registro_valida(V.cargar_jsonl(V.RAIZ / "ofertas/_ejemplo/_empresa/registro.jsonl")))

    def test_float_en_cualquier_artefacto(self) -> None:
        e = self.j("03-oferta/economia.json"); e["aov"]["monto"] = 20.69; self.w("03-oferta/economia.json", e)
        self.assertDetecta("FLOAT")

    def test_artefacto_con_propiedad_extra_no_pasa_el_esquema(self) -> None:
        e = self.j("mercado.json"); e["pais_prior"] = "PL"; self.w("mercado.json", e)
        self.assertDetecta("ESQUEMA")

    def test_carpeta_inexistente(self) -> None:
        inf = V.validar_oferta(self.dir / "no-existe", limites=self.lim)
        self.assertIn("OFERTA", {h.codigo for h in inf.errores})


class PruebaArtefactosDeEmpresa(unittest.TestCase):
    def test_pnl_resultado_operativo(self) -> None:
        d = V.cargar_json(V.DIR_EJEMPLOS / "pnl.valido.json")
        inf = Informe_vacio()
        V.reglas_de_artefacto("pnl", d, inf, "pnl")
        self.assertEqual([], inf.errores)
        d["consolidado"]["resultado_operativo"]["monto"] += 1
        inf = Informe_vacio()
        V.reglas_de_artefacto("pnl", d, inf, "pnl")
        self.assertIn("PNL_FORMULA", {h.codigo for h in inf.errores})

    def test_registro_valido_de_ejemplo_encadena(self) -> None:
        lineas = V.cargar_jsonl(V.RAIZ / "ofertas/_ejemplo/_empresa/registro.jsonl")
        self.assertIsNone(lineas[0]["hash_previo"])
        self.assertEqual(lineas[0]["hash"], lineas[1]["hash_previo"])


def Informe_vacio() -> V.Informe:
    return V.Informe("t")


if __name__ == "__main__":
    unittest.main()
