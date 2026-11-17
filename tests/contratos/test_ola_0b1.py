"""Pruebas de la ola 0b-1 de contratos: parametros 1.1.0, economia 1.1.0, los once esquemas nuevos (C13),
brief, mercado 1.1.0, campana 1.2.0 y checkout 1.2.0. Cada prueba rompe UNA cosa y exige el código de la regla.
Sin red ni credenciales (convenciones 11).
"""
from __future__ import annotations

import contextlib
import copy
import io
import json
import os
import shutil
import socket
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from scripts import validar_esquemas as V

CLAVE = V.CLAVE_DE_PRUEBA
# MINOR posteriores a la ola 0b-1, por la revisión CT1 (docs/_historial/ct1-registro.md).
VERSION_NUEVOS_CT1 = {"decision": "1.1.0", "conciliacion": "1.1.0", "orden_firmada": "1.1.0", "traspaso": "1.1.0"}
NUEVOS = ["aprobacion", "ids_meta", "preflight", "sello", "decision", "ledger", "conciliacion", "tipo_cambio", "postmortem", "orden_firmada", "traspaso"]


def _sin_red(caso: unittest.TestCase) -> None:
    original = socket.socket

    def bloqueado(*a, **k):
        raise AssertionError("las pruebas no pueden abrir sockets")

    socket.socket = bloqueado  # type: ignore[assignment]
    caso.addCleanup(setattr, socket, "socket", original)


def _resellar(raiz: Path) -> None:
    """Re-sella una copia de ofertas/_ejemplo tras mutarla (hash de campaña, de etapas, firmas HMAC de prueba y QA)."""
    camp = V.cargar_json(raiz / "07-campana/campana.json")
    camp["hash_config"] = V.hash_objeto(camp, excluir=("hash_config",))
    (raiz / "07-campana/campana.json").write_text(json.dumps(camp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    est = V.cargar_json(raiz / "estado.json")
    for et, e in est["etapas"].items():
        if e["hash_salida"] is not None:
            e["hash_salida"] = V.hash_salida_etapa(raiz, et)
    for et, e in est["etapas"].items():
        for dep in list(e["entradas"]):
            e["entradas"][dep] = est["etapas"][dep]["hash_salida"]
        ap = e["aprobado_por"]
        if ap and ap.get("firma"):
            ap["firma"] = V.firma_hmac({"oferta_id": est["oferta_id"], "etapa": et, "hash_salida": e["hash_salida"], "aprobador": ap["id"], "fecha": ap["fecha"]}, CLAVE)
    (raiz / "estado.json").write_text(json.dumps(est, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for p in sorted((raiz / "qa").glob("*.json")):
        q = V.cargar_json(p)
        q["artefacto_sha256"] = V.hash_ruta(raiz / q["artefacto_ref"])
        for r in list(q["entradas"]):
            q["entradas"][r] = V.hash_ruta(raiz / r)
        if q.get("x1"):
            q["x1"]["artefacto_sha256"] = q["artefacto_sha256"]
        p.write_text(json.dumps(q, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _ej(nombre: str, tipo: str = "valido"):
    for ext in ("json", "yaml"):
        p = V.DIR_EJEMPLOS / f"{nombre}.{tipo}.{ext}"
        if p.exists():
            return V.cargar_datos(p)
    raise FileNotFoundError(nombre)


def _fusionar(base: dict, overlay: dict) -> dict:
    out = copy.deepcopy(base)
    out["schema_version"] = overlay.get("schema_version", out["schema_version"])
    for g, claves in overlay["grupos"].items():
        out["grupos"].setdefault(g, {}).update(copy.deepcopy(claves))
    return out


def _codigos(problemas) -> set[str]:
    return {c for c, _ in problemas}


class PruebaEsquemasNuevos(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)

    def test_cada_esquema_nuevo_tiene_valido_e_invalido_con_motivo(self) -> None:
        for n in NUEVOS:
            self.assertTrue(list(V.DIR_EJEMPLOS.glob(f"{n}.valido.*")), n)
            inv = [p for p in V.DIR_EJEMPLOS.glob(f"{n}.invalido-*.json") if ".motivo" not in p.name]
            self.assertTrue(inv, n)
            for p in inv:
                self.assertTrue(p.with_suffix(".motivo.txt").exists(), p.name)

    def test_esquemas_nuevos_cerrados_sin_float_y_con_version(self) -> None:
        _, esquemas = V.cargar_esquemas()

        def cerrados(nodo, ruta):
            if isinstance(nodo, dict):
                if "properties" in nodo and nodo.get("type") == "object":
                    self.assertIs(nodo.get("additionalProperties"), False, ruta)
                self.assertNotEqual("number", nodo.get("type"), f"{ruta}: float prohibido")
                for k, v in nodo.items():
                    cerrados(v, f"{ruta}/{k}")
            elif isinstance(nodo, list):
                for i, v in enumerate(nodo):
                    cerrados(v, f"{ruta}[{i}]")

        for n in NUEVOS:
            self.assertEqual(VERSION_NUEVOS_CT1.get(n, "1.0.0"), esquemas[n]["x-version"], n)
            self.assertIn("schema_version", esquemas[n]["required"], n)
            self.assertTrue(esquemas[n]["$id"].endswith(f"/v1/{n}.schema.json"))
            cerrados(esquemas[n], n)

    def test_los_ejemplos_validos_son_coherentes_por_dentro(self) -> None:
        for n in ("aprobacion", "preflight", "sello", "orden_firmada", "decision", "conciliacion", "tipo_cambio", "traspaso", "postmortem"):
            self.assertEqual([], V.problemas_artefacto(n, _ej(n), clave=CLAVE, entorno="prueba"), n)
        self.assertEqual([], V.problemas_ledger([_ej("ledger")]))

    def test_versiones_de_los_esquemas_tocados(self) -> None:
        _, e = V.cargar_esquemas()
        self.assertEqual({"parametros": "1.1.0", "economia": "1.2.0", "brief": "1.1.0", "mercado": "1.1.0", "campana": "1.2.0", "checkout": "1.2.0", "comunes": "1.4.0"},
                         {k: e[k]["x-version"] for k in ("parametros", "economia", "brief", "mercado", "campana", "checkout", "comunes")})


class PruebaFirmas(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)
        self.ap = _ej("aprobacion")

    def test_formato(self) -> None:
        self.assertEqual("hmac", V.tipo_firma("hmac-sha256:" + "a" * 64))
        self.assertEqual("ed25519", V.tipo_firma(_ej("orden_firmada")["firma"]))
        for malo in (None, "", "sha256:" + "a" * 64, "ed25519:corta", "hmac-sha256:" + "A" * 64, 5):
            self.assertIsNone(V.tipo_firma(malo))

    def test_hmac_verifica_y_se_rompe_al_cambiar_el_contenido(self) -> None:
        self.assertEqual([], V.problemas_artefacto("aprobacion", self.ap, clave=CLAVE, entorno="prueba"))
        ap = copy.deepcopy(self.ap); ap["hash_objetivo"] = "sha256:" + "1" * 64
        self.assertIn("X40_FIRMA", _codigos(V.problemas_artefacto("aprobacion", ap, clave=CLAVE, entorno="prueba")))

    def test_hmac_prohibido_en_produccion_y_ed25519_aceptado(self) -> None:
        self.assertIn("X40_FIRMA", _codigos(V.problemas_artefacto("aprobacion", self.ap, clave=CLAVE, entorno="produccion")))
        orden = _ej("orden_firmada")
        # CT1-04/05: en producción una Ed25519 solo cuenta si un verificador (la clave pública) la confirma; sin él, fail-closed.
        self.assertIn("X40_FIRMA", _codigos(V.problemas_artefacto("orden_firmada", orden, entorno="produccion")))
        self.assertIn("X40_FIRMA", _codigos(V.problemas_artefacto("orden_firmada", orden, entorno="produccion", verificador=lambda b, f: False)))
        self.assertEqual([], V.problemas_artefacto("orden_firmada", orden, entorno="produccion", verificador=lambda b, f: True))
        sello = _ej("sello")
        self.assertEqual([], V.problemas_artefacto("sello", sello, entorno="produccion", verificador=lambda b, f: True))
        sello["firma"] = "hmac-sha256:" + "a" * 64
        self.assertIn("X40_FIRMA", _codigos(V.problemas_artefacto("sello", sello, entorno="produccion")))

    def test_firma_del_sello_y_de_la_orden_cubre_todo_el_contenido(self) -> None:
        for nombre in ("sello", "orden_firmada"):
            d = _ej(nombre)
            d["firma"] = V.firmar_hmac_de_prueba(nombre, d)
            self.assertEqual([], V.problemas_artefacto(nombre, d, clave=CLAVE, entorno="prueba"), nombre)
            d["oferta_id"] = "OF-202611-02"
            self.assertIn("X40_FIRMA", _codigos(V.problemas_artefacto(nombre, d, clave=CLAVE, entorno="prueba")), nombre)

    def test_firma_ausente_es_problema(self) -> None:
        self.assertEqual([("X40_FIRMA", "firma ausente")], V.problemas_firma(None, {}, None))


class PruebaAprobacionYOrden(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)
        self.ap = _ej("aprobacion")

    def probl(self, d, **kw):
        return _codigos(V.problemas_artefacto("aprobacion", d, clave=CLAVE, entorno="prueba", **kw))

    def test_gate_distinto_de_la_tabla(self) -> None:
        ap = copy.deepcopy(self.ap); ap["gate"] = "S"
        self.assertIn("X40_GATE", self.probl(ap))

    def test_accion_inexistente(self) -> None:
        ap = copy.deepcopy(self.ap); ap["accion"] = "inventar_algo"
        self.assertIn("X40_ACCION", self.probl(ap))

    def test_activar_sin_object_ids(self) -> None:
        ap = copy.deepcopy(self.ap); ap["object_ids"] = []
        self.assertIn("X40_OBJETOS", self.probl(ap))

    def test_vigencia_anterior_a_la_creacion(self) -> None:
        ap = copy.deepcopy(self.ap); ap["vigencia_hasta"] = ap["creado_en"]
        self.assertIn("X40_VIGENCIA", self.probl(ap))

    def test_etapa_y_accion_a_la_vez_o_ninguna_es_invalido(self) -> None:
        a = copy.deepcopy(self.ap); a["etapa"] = "D7"
        self.assertTrue(V.errores_de_esquema("aprobacion", a))
        b = copy.deepcopy(self.ap); del b["accion"]
        self.assertTrue(V.errores_de_esquema("aprobacion", b))

    def test_aprobacion_de_etapa_h_nivel_n2(self) -> None:
        ap = copy.deepcopy(self.ap); del ap["accion"]; ap["etapa"] = "D3"
        ap["aprobado_por"]["firma"] = V.firmar_hmac_de_prueba("aprobacion", ap)
        self.assertEqual([], V.errores_de_esquema("aprobacion", ap))
        self.assertEqual(set(), self.probl(ap))   # etapa:D3 en N2 = H

    def test_gate_h_exige_humano_y_firma_en_el_esquema(self) -> None:
        ap = copy.deepcopy(self.ap); ap["aprobado_por"]["tipo"] = "regla"
        self.assertTrue(V.errores_de_esquema("aprobacion", ap))

    def test_orden_firmada(self) -> None:
        o = _ej("orden_firmada")
        self.assertEqual([], V.errores_de_esquema("orden_firmada", o))
        # aprobar_etapa exige etapa; las demás acciones la prohíben
        a = copy.deepcopy(o); a["accion"] = "aprobar_etapa"
        self.assertTrue(V.errores_de_esquema("orden_firmada", a))
        a["etapa"] = "D5"
        self.assertEqual([], V.errores_de_esquema("orden_firmada", a))
        b = copy.deepcopy(o); b["etapa"] = "D5"
        self.assertTrue(V.errores_de_esquema("orden_firmada", b))
        c = copy.deepcopy(o); c["accion"] = "cambiar_el_mundo"
        self.assertIn("X40_ACCION", _codigos(V.problemas_artefacto("orden_firmada", c, entorno="prueba")))
        d = copy.deepcopy(o); d["object_ids"] = []
        self.assertIn("X40_OBJETOS", _codigos(V.problemas_artefacto("orden_firmada", d, entorno="prueba")))


class PruebaSelloPreflightDecision(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)

    def test_sello(self) -> None:
        s = _ej("sello")
        s2 = copy.deepcopy(s); s2["etapa_objetivo"] = "D5"
        self.assertIn("X40_OBJETOS", _codigos(V.problemas_artefacto("sello", s2, entorno="prueba")))
        s3 = copy.deepcopy(s); s3["object_ids"] = []
        self.assertIn("X40_OBJETOS", _codigos(V.problemas_artefacto("sello", s3, entorno="prueba")))
        s4 = copy.deepcopy(s); s4["dictamen_ref"] = "qa/d7-v1.json"
        self.assertIn("X40_DICTAMEN", _codigos(V.problemas_artefacto("sello", s4, entorno="prueba")))
        s5 = copy.deepcopy(s); s5["vigencia_hasta"] = s5["emitido_en"]
        self.assertIn("X40_VIGENCIA", _codigos(V.problemas_artefacto("sello", s5, entorno="prueba")))

    def test_preflight(self) -> None:
        pf = _ej("preflight")
        self.assertEqual(25 - 1, len([k for k in pf["checks"] if k != "P25"]))
        pf["checks"]["P05"]["estado"] = "ROJO"
        self.assertIn("X41_PREFLIGHT", _codigos(V.problemas_artefacto("preflight", pf)))
        pf["semaforo"] = "ROJO"
        self.assertEqual(set(), _codigos(V.problemas_artefacto("preflight", pf)))
        pf2 = _ej("preflight"); pf2["checks"]["P25"] = {"estado": "VERDE", "evidencia": "categoría coincide"}
        self.assertEqual([], V.errores_de_esquema("preflight", pf2))
        pf3 = _ej("preflight"); pf3["checks"]["P26"] = pf2["checks"]["P25"]
        self.assertTrue(V.errores_de_esquema("preflight", pf3))

    def test_decision(self) -> None:
        d = _ej("decision")
        d1 = copy.deepcopy(d); d1["decision_id"] = "sha256:" + "0" * 64
        self.assertIn("X43_DECISION", _codigos(V.problemas_artefacto("decision", d1)))
        d2 = copy.deepcopy(d); d2["accion"] = "BLOQUEADO"
        self.assertIn("X43_DECISION", _codigos(V.problemas_artefacto("decision", d2)))
        d3 = copy.deepcopy(d); d3["ts"] = "2026-11-14T08:59:00Z"
        self.assertIn("X43_DECISION", _codigos(V.problemas_artefacto("decision", d3)))
        d4 = copy.deepcopy(d); d4["evidencia"]["p_cpa_menor_equilibrio"] = 0.04   # float
        self.assertTrue(V.errores_de_esquema("decision", d4) or V.buscar_floats(d4))
        # el id es determinista: la misma lectura no duplica
        self.assertEqual(V.decision_id_esperado("OF-202611-01", "x", "2026-11-14T09:00:00Z"), V.decision_id_esperado("OF-202611-01", "x", "2026-11-14T09:00:00Z"))


class PruebaFinanzas(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)

    def test_ledger(self) -> None:
        l = _ej("ledger")
        self.assertEqual([], V.problemas_ledger([l]))
        self.assertIn("X44_LEDGER", _codigos(V.problemas_ledger([l, copy.deepcopy(l)])))
        mal = copy.deepcopy(l); mal["fuente"] = "meta"
        self.assertIn("X44_LEDGER", _codigos(V.problemas_ledger([mal])))
        # importe_base y tipo_cambio_id van juntos
        c = copy.deepcopy(l); c["importe_base"] = {"monto": 1841, "moneda": "USD"}  # 1990 x 0.9250 = 1840.75 (CT1-21 verifica la aritmética)
        self.assertTrue(V.errores_de_esquema("ledger", c))
        c["tipo_cambio_id"] = "TC-EURUSD-20261106"
        self.assertEqual([], V.errores_de_esquema("ledger", c))
        self.assertIn("X44_LEDGER", _codigos(V.problemas_ledger([c], [_ej("tipo_cambio")])))   # no registrado
        tc = copy.deepcopy(_ej("tipo_cambio")); tc.update(tipo_cambio_id="TC-EURUSD-20261106", par="EUR/USD")
        self.assertEqual([], V.problemas_ledger([c], [tc]))
        c["importe_base"]["moneda"] = "EUR"
        self.assertIn("X44_LEDGER", _codigos(V.problemas_ledger([c], [tc])))

    def test_conciliacion(self) -> None:
        c = _ej("conciliacion")
        a = copy.deepcopy(c); a["stripe_vs_ledger"]["diferencia"]["monto"] = 100
        self.assertIn("X44_CONCILIACION", _codigos(V.problemas_artefacto("conciliacion", a)))
        b = copy.deepcopy(c); b["stripe_vs_ledger"]["derecha"]["monto"] = 19800; b["stripe_vs_ledger"]["diferencia"]["monto"] = 100
        self.assertIn("X44_CONCILIACION", _codigos(V.problemas_artefacto("conciliacion", b)))   # CONCILIADO con diferencia
        b["estado"] = "DESCUADRE"
        self.assertIn("X44_CONCILIACION", _codigos(V.problemas_artefacto("conciliacion", b)))   # cifras sin tachar
        b["cifras_tachadas"] = True
        self.assertEqual(set(), _codigos(V.problemas_artefacto("conciliacion", b)))
        m = copy.deepcopy(c); m["gasto_meta_vs_ledger"]["izquierda"]["moneda"] = "USD"
        self.assertIn("X44_CONCILIACION", _codigos(V.problemas_artefacto("conciliacion", m)))

    def test_tipo_cambio(self) -> None:
        t = _ej("tipo_cambio")
        self.assertEqual("TC-USDEUR-20261106", V.tipo_cambio_id_esperado("USD/EUR", "2026-11-06"))
        a = copy.deepcopy(t); a["tipo_cambio_id"] = "TC-USDEUR-20261107"
        self.assertIn("X45_TIPO_CAMBIO", _codigos(V.problemas_artefacto("tipo_cambio", a)))
        b = copy.deepcopy(t); b["tasa"] = "0"
        self.assertIn("X45_TIPO_CAMBIO", _codigos(V.problemas_artefacto("tipo_cambio", b)))
        c = copy.deepcopy(t); c["par"] = "USD/USD"; c["tipo_cambio_id"] = "TC-USDUSD-20261106"
        self.assertIn("X45_TIPO_CAMBIO", _codigos(V.problemas_artefacto("tipo_cambio", c)))
        d = copy.deepcopy(t); d["obtenido_en"] = "2026-11-05T07:00:00Z"
        self.assertIn("X45_TIPO_CAMBIO", _codigos(V.problemas_artefacto("tipo_cambio", d)))

    def test_artefactos_de_empresa_en_disco(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            emp = Path(t) / "empresa"
            (emp / "finanzas").mkdir(parents=True)
            (emp / "compliance" / "sellos").mkdir(parents=True)
            (emp / "finanzas" / "tipos_cambio.jsonl").write_text(json.dumps(_ej("tipo_cambio")) + "\n")
            (emp / "finanzas" / "ledger.jsonl").write_text(json.dumps(_ej("ledger")) + "\n")
            (emp / "finanzas" / "conciliacion.json").write_text(json.dumps(_ej("conciliacion")))
            sello = _ej("sello")
            (emp / "compliance" / "sellos" / (sello["artefacto_sha256"].split(":")[1] + ".json")).write_text(json.dumps(sello))
            inf = V.Informe("t")
            V.validar_artefactos_de_empresa(emp, inf)
            self.assertEqual([], [str(h) for h in inf.errores])
            (emp / "compliance" / "sellos" / ("0" * 64 + ".json")).write_text(json.dumps(sello))
            inf = V.Informe("t")
            V.validar_artefactos_de_empresa(emp, inf)
            self.assertIn("X40_SELLO", {h.codigo for h in inf.errores})


class PruebaTraspasoPostmortem(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)

    def test_traspaso(self) -> None:
        t = _ej("traspaso")
        a = copy.deepcopy(t); a["ventana_h"] = 24
        self.assertTrue(V.errores_de_esquema("traspaso", a))            # estable solo con 72 h
        b = copy.deepcopy(t); b["anuncios"][0]["rechazado"] = True; b["rechazos_7d"] = 1
        self.assertTrue(V.errores_de_esquema("traspaso", b))            # estable exige 0 rechazos
        c = copy.deepcopy(t); c["lanzamiento_estable"] = False; c["anuncios"][0]["rechazado"] = True
        self.assertIn("X42_TRASPASO", _codigos(V.problemas_artefacto("traspaso", c)))   # rechazos_7d < rechazados
        d = copy.deepcopy(t); d["anuncios"][1]["ad_id"] = d["anuncios"][0]["ad_id"]
        self.assertIn("X42_TRASPASO", _codigos(V.problemas_artefacto("traspaso", d)))
        e = copy.deepcopy(t); e["campana"]["effective_status"] = "PAUSED"
        self.assertIn("X42_TRASPASO", _codigos(V.problemas_artefacto("traspaso", e)))

    def test_postmortem_exige_retraso_clic_compra(self) -> None:
        p = _ej("postmortem")
        q = copy.deepcopy(p); del q["retraso_clic_compra"]
        self.assertTrue(V.errores_de_esquema("postmortem", q))
        for campo in ("n_compras", "mediana_h", "p90_h", "fuente"):
            r = copy.deepcopy(p); del r["retraso_clic_compra"][campo]
            self.assertTrue(V.errores_de_esquema("postmortem", r), campo)

    def test_postmortem_sin_compras_no_inventa_mediana(self) -> None:
        p = _ej("postmortem")
        p["retraso_clic_compra"] = {"n_compras": 0, "mediana_h": 20, "p90_h": None, "fuente": "no_medible"}
        self.assertTrue(V.errores_de_esquema("postmortem", p))
        p["retraso_clic_compra"] = {"n_compras": 0, "mediana_h": None, "p90_h": None, "fuente": "no_medible"}
        self.assertEqual([], V.errores_de_esquema("postmortem", p))
        p["retraso_clic_compra"] = {"n_compras": 3, "mediana_h": None, "p90_h": None, "fuente": "stripe_vs_evento_clic"}
        self.assertTrue(V.errores_de_esquema("postmortem", p))

    def test_postmortem_coherencia(self) -> None:
        p = _ej("postmortem")
        a = copy.deepcopy(p); a["retraso_clic_compra"]["p90_h"] = 5
        self.assertIn("X46_POSTMORTEM", _codigos(V.problemas_artefacto("postmortem", a)))
        b = copy.deepcopy(p); b["causa_principal"] = "otra-cosa"
        self.assertIn("X46_POSTMORTEM", _codigos(V.problemas_artefacto("postmortem", b)))


class PruebaParametros110(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)
        self.base = V.cargar_yaml(V.RAIZ / "empresa" / "parametros.yaml")
        self.prop = V.cargar_yaml(V.RAIZ / "empresa" / "propuestas" / "parametros-b0.yaml")
        self.todo = _fusionar(self.base, self.prop)

    def errores(self, par):
        return V.errores_de_esquema("parametros", par)

    def test_plantilla_con_los_cuatro_grupos_opcionales_sigue_valida(self) -> None:
        # CT-3 lote A (A-09, H-9): la plantilla trae estadistica, agentes, ingesta y watchdog SIN subir la versión del esquema (1.2.0 sigue reservada a modelado_*).
        self.assertEqual("1.1.0", self.base["schema_version"])
        self.assertEqual([], self.errores(self.base))
        self.assertTrue({"estadistica", "agentes", "ingesta", "watchdog"} <= set(self.base["grupos"]))
        for g in ("estadistica", "agentes", "ingesta", "watchdog"):
            self.assertEqual(self.prop["grupos"][g], self.base["grupos"][g], g)
        self.assertNotIn("hc_latido_max_horas", self.base["grupos"]["infra"])

    def test_propuesta_fusionada_valida_y_coherente(self) -> None:
        self.assertEqual([], [e.message for e in self.errores(self.todo)])
        self.assertEqual([], V.coherencia_parametros(self.todo))
        self.assertEqual([], V.buscar_floats(self.todo))
        self.assertEqual({}, V.claves_duplicadas(self.todo))

    def test_hc_latido_max_horas_ya_no_existe(self) -> None:
        par = copy.deepcopy(self.base)
        par["grupos"]["infra"]["hc_latido_max_horas"] = copy.deepcopy(par["grupos"]["infra"]["hc_hora_diaria"])
        self.assertTrue(self.errores(par))
        _, e = V.cargar_esquemas()
        self.assertNotIn("hc_latido_max_horas", e["parametros"]["properties"]["grupos"]["properties"]["infra"]["properties"])

    def test_grupo_opcional_presente_se_valida_completo(self) -> None:
        for g in ("estadistica", "agentes", "ingesta", "watchdog"):
            par = copy.deepcopy(self.todo)
            del par["grupos"][g][next(iter(par["grupos"][g]))]
            self.assertTrue(self.errores(par), g)
        par = copy.deepcopy(self.todo)
        par["grupos"]["watchdog"]["latido_cada_min"]["valor"] = "cinco"
        self.assertTrue(self.errores(par))

    def test_grupos_nuevos_no_son_obligatorios_y_las_claves_nuevas_tampoco(self) -> None:
        _, e = V.cargar_esquemas()
        g = e["parametros"]["properties"]["grupos"]
        self.assertTrue({"estadistica", "agentes", "ingesta", "watchdog"}.isdisjoint(g.get("required", [])))
        self.assertNotIn("max_sesiones_por_visitante", g["properties"]["landing"]["required"])
        self.assertNotIn("spend_cap_minimo_meta", g["properties"]["campana"]["required"])
        self.assertIn("max_sesiones_por_visitante", g["properties"]["landing"]["properties"])

    def test_dias_madurez_compra_y_ciclo_max_min_existen(self) -> None:
        self.assertEqual(3, self.todo["grupos"]["estadistica"]["dias_madurez_compra"]["valor"])
        self.assertEqual(480, self.todo["grupos"]["watchdog"]["ciclo_max_min"]["valor"])
        self.assertEqual(30, self.todo["grupos"]["watchdog"]["latido_max_min"]["valor"])

    def test_agentes_quedan_null_y_el_runner_en_vivo_falla_cerrado(self) -> None:
        self.assertTrue(all(p["valor"] is None for p in self.todo["grupos"]["agentes"].values()))
        falta = V.parametros_faltantes(self.todo, V.OPERACION_PARAMETROS["runner_vivo"])
        self.assertEqual(sorted(V.OPERACION_PARAMETROS["runner_vivo"]), sorted(falta))
        # CT-3 A-09: la plantilla ya trae los grupos (agentes en null: falla cerrado); sin el grupo (plantilla vieja) también
        self.assertEqual(len(V.OPERACION_PARAMETROS["runner_vivo"]), len(V.parametros_faltantes(self.base, V.OPERACION_PARAMETROS["runner_vivo"])))
        self.assertEqual([], V.parametros_faltantes(self.todo, V.OPERACION_PARAMETROS["watchdog"]))
        self.assertEqual([], V.parametros_faltantes(self.base, V.OPERACION_PARAMETROS["watchdog"]))
        sin_grupos = copy.deepcopy(self.base)
        for g in ("estadistica", "agentes", "ingesta", "watchdog"):
            del sin_grupos["grupos"][g]
        self.assertEqual(V.OPERACION_PARAMETROS["watchdog"], V.parametros_faltantes(sin_grupos, V.OPERACION_PARAMETROS["watchdog"]))

    def test_cli_parametros_sale_5_si_falta_y_0_si_esta(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            ruta = Path(t) / "parametros.yaml"
            ruta.write_text(yaml.safe_dump(self.todo, allow_unicode=True, sort_keys=False))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(V.SALIDA_LIMITE, V.main(["parametros", str(ruta), "--operacion", "runner_vivo"]))
                self.assertIn("ParametroFaltante", out.getvalue())
                self.assertEqual(V.SALIDA_OK, V.main(["parametros", str(ruta), "--operacion", "watchdog"]))
                # CT-3 A-09: la plantilla real ya trae watchdog (sale 0) y sigue fallando cerrado en agentes (todo null)
                self.assertEqual(V.SALIDA_OK, V.main(["parametros", str(V.RAIZ / "empresa" / "parametros.yaml"), "--operacion", "watchdog"]))
                self.assertEqual(V.SALIDA_LIMITE, V.main(["parametros", str(V.RAIZ / "empresa" / "parametros.yaml"), "--operacion", "runner_vivo"]))
                sin = copy.deepcopy(self.base)
                del sin["grupos"]["watchdog"]
                ruta.write_text(yaml.safe_dump(sin, allow_unicode=True, sort_keys=False))
                self.assertEqual(V.SALIDA_LIMITE, V.main(["parametros", str(ruta), "--operacion", "watchdog"]))

    def test_ninguna_clave_nueva_duplica_otro_grupo(self) -> None:
        nuevos = ("estadistica", "agentes", "ingesta", "watchdog")
        otros = {k for g, claves in self.base["grupos"].items() if g not in nuevos for k in claves}
        for g in nuevos:
            self.assertEqual(set(), set(self.prop["grupos"][g]) & otros, g)
        self.assertEqual({}, V.claves_duplicadas(self.todo))
        malo = copy.deepcopy(self.base)
        malo["grupos"]["landing"]["k_corte"] = malo["grupos"]["testeo"]["k_corte"]
        self.assertEqual({"k_corte": ["testeo", "landing"]}, {k: sorted(v, key=["testeo", "landing"].index) for k, v in V.claves_duplicadas(malo).items()})
        self.assertTrue(any("k_corte" in m for m in V.coherencia_parametros(malo)))

    def test_las_duplicadas_heredadas_estan_documentadas(self) -> None:
        donde = {}
        for g, claves in self.base["grupos"].items():
            for k in claves:
                donde.setdefault(k, []).append(g)
        self.assertEqual(V.DUPLICADAS_HEREDADAS, {k for k, gs in donde.items() if len(gs) > 1})

    def test_coherencia_entre_parametros(self) -> None:
        def con(cambio) -> list[str]:
            par = copy.deepcopy(self.todo)
            cambio(par["grupos"])
            return V.coherencia_parametros(par)
        self.assertTrue(con(lambda g: g["watchdog"]["latido_max_min"].update(valor=5)))          # <= latido_cada_min
        self.assertTrue(con(lambda g: g["watchdog"]["ciclo_max_min"].update(valor=360)))         # = lectura_horas x 60
        self.assertTrue(con(lambda g: g["estadistica"]["dias_madurez_compra"].update(valor=7)))  # >= veredicto.dias_min
        self.assertTrue(con(lambda g: g["estadistica"]["alfa_descarte"].update(valor="0.7")))
        self.assertTrue(con(lambda g: g["estadistica"]["k_min_fallida"].update(valor="1.0")))
        self.assertTrue(con(lambda g: (g["agentes"]["estado_max_edad_h"].update(valor=7))))
        self.assertTrue(con(lambda g: (g["agentes"]["bash_timeout_defecto_ms"].update(valor=9000), g["agentes"]["bash_timeout_max_ms"].update(valor=1000))))

    def test_estado_max_edad_h_tiene_tope_de_6_en_el_esquema(self) -> None:
        par = copy.deepcopy(self.todo)
        par["grupos"]["agentes"]["estado_max_edad_h"]["valor"] = 7
        self.assertTrue(self.errores(par))
        par["grupos"]["agentes"]["estado_max_edad_h"]["valor"] = 6
        self.assertEqual([], self.errores(par))

    def test_la_otra_sesion_no_esta_integrada(self) -> None:
        self.assertFalse(any(k.startswith("modelado_") for k in self.todo["grupos"]["descubrimiento"]))
        _, e = V.cargar_esquemas()
        self.assertEqual("1.1.0", e["parametros"]["x-version"])
        self.assertNotIn("patternProperties", e["parametros"]["properties"]["grupos"]["properties"]["descubrimiento"])

    def test_spend_cap_minimo_meta_es_dinero_o_null(self) -> None:
        par = copy.deepcopy(self.todo)
        par["grupos"]["campana"]["spend_cap_minimo_meta"]["valor"] = None
        self.assertEqual([], self.errores(par))
        par["grupos"]["campana"]["spend_cap_minimo_meta"]["valor"] = 100.5
        self.assertTrue(self.errores(par))


class PruebaEconomia110(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.dir = Path(self._t.name) / "_ejemplo"
        shutil.copytree(V.RAIZ / "ofertas" / "_ejemplo", self.dir)
        self.lim = V.limites_de_prueba()
        self.aut = V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml")
        self.eco = V.cargar_json(self.dir / "03-oferta/economia.json")

    def w(self, eco) -> None:
        (self.dir / "03-oferta/economia.json").write_text(json.dumps(eco, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def inf(self):
        _resellar(self.dir)
        return V.validar_oferta(self.dir, limites=self.lim, autonomia=self.aut, clave_firma=CLAVE)

    def codigos(self) -> set[str]:
        return {h.codigo for h in self.inf().errores}

    def test_base_limpia_y_campos_d02_presentes(self) -> None:
        self.assertEqual(set(), self.codigos())
        for k in ("conv_central", "cpc_esperado", "cpa_be_visto", "limites_pendientes", "resultado_esperado_central"):
            self.assertIn(k, self.eco)
        self.assertEqual("supuesto", self.eco["entradas_usadas"]["tarifas_origen"])
        self.assertIsInstance(self.eco["cpc_esperado"]["monto"], str)

    def test_1_1_0_exige_los_campos_nuevos_y_1_0_0_no(self) -> None:
        for k in ("conv_central", "resultado_esperado_central", "limites_pendientes"):
            e = copy.deepcopy(self.eco); del e[k]
            self.assertTrue(V.errores_de_esquema("economia", e), k)
        for k in ("tasa_iva_bp", "stripe_tax", "tarifa_meta_bp", "recargos_bp", "conversion_bp", "tarifas_origen"):
            e = copy.deepcopy(self.eco); del e["entradas_usadas"][k]
            self.assertTrue(V.errores_de_esquema("economia", e), k)
        viejo = copy.deepcopy(self.eco)
        viejo["schema_version"] = "1.0.0"
        for k in ("conv_central", "cpc_esperado", "cpa_be_visto", "limites_pendientes", "resultado_esperado_central"):
            del viejo[k]
        for k in ("tasa_iva_bp", "stripe_tax", "tarifa_meta_bp", "recargos_bp", "conversion_bp", "tarifas_origen"):
            del viejo["entradas_usadas"][k]
        self.assertEqual([], V.errores_de_esquema("economia", viejo))

    def test_resultado_esperado_central_se_recalcula(self) -> None:
        self.eco["resultado_esperado_central"]["monto"] += 1; self.w(self.eco)
        self.assertIn("X14_ECONOMIA", self.codigos())

    def regenerar(self) -> dict:
        """Regenera economia.json con la ÚNICA fórmula (``engine.factibilidad``) desde sus propias entradas y alinea ``campana.economia``."""
        from engine import factibilidad
        e = V.cargar_json(self.dir / "03-oferta/economia.json")
        entradas = {**e["entradas_usadas"], "gasto_diario": e["gasto_test_plan"]["monto"] // e["dias_test"]}
        doc = factibilidad.documento_economia(entradas, V.cargar_yaml(V.RAIZ / "empresa" / "parametros.yaml"), self.lim, oferta_id=e["oferta_id"])
        self.w(doc)
        camp = V.cargar_json(self.dir / "07-campana/campana.json")
        camp["economia"].update(cpa_equilibrio=doc["cpa_be"]["monto"], cpa_objetivo=doc["cpa_obj"]["monto"], cpa_max=doc["cpa_be"]["monto"])
        (self.dir / "07-campana/campana.json").write_text(json.dumps(camp, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        ver = V.cargar_json(self.dir / "08-operacion/veredicto_oferta.json")
        ver["evidencia"]["cpa_objetivo"]["monto"] = doc["cpa_obj"]["monto"]
        (self.dir / "08-operacion/veredicto_oferta.json").write_text(json.dumps(ver, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.eco = doc
        return doc

    def test_cpa_be_visto_con_tarifa_meta(self) -> None:
        self.eco["entradas_usadas"]["tarifa_meta_bp"] = 300; self.w(self.eco)
        self.assertIn("X14_ECONOMIA", self.codigos())               # los derivados declarados quedaron viejos
        doc = self.regenerar()
        self.assertEqual(set(), self.codigos())
        self.assertEqual(V.entero_redondeado(doc["cpa_be"]["monto"] * 10000, 10300), doc["cpa_be_visto"]["monto"])
        self.assertLess(doc["cpa_be_visto"]["monto"], doc["cpa_be"]["monto"])

    def test_conv_y_cpc_salen_del_escenario_central(self) -> None:
        self.eco["conv_central"] = "0.0300"; self.w(self.eco)
        self.assertIn("X14_ECONOMIA", self.codigos())
        self.eco["conv_central"] = "0.022"; self.eco["cpc_esperado"]["monto"] = "30"; self.w(self.eco)
        self.assertIn("X14_ECONOMIA", self.codigos())

    def test_tarifas_supuestas_llevan_la_marca(self) -> None:
        self.eco["entradas_usadas"]["tarifas_fuente"] = "tarifas.json de F1 (2026-11-05)"; self.w(self.eco)
        self.assertIn("X14_TARIFAS", self.codigos())
        self.eco["entradas_usadas"]["tarifas_origen"] = "tarifas_json_f1"; self.w(self.eco)
        self.assertNotIn("X14_TARIFAS", self.codigos())
        self.eco["entradas_usadas"]["tarifas_fuente"] = "[SUPUESTO] tarifa de LLC"; self.w(self.eco)
        self.assertIn("X14_TARIFAS", self.codigos())

    def test_iva_o_recargos_distintos_de_cero_se_recalculan_con_la_formula_unica(self) -> None:
        """CT-2: ya no hay aviso X14_FORMULA_PENDIENTE; X14 llama a engine.factibilidad.calcular con IVA, Stripe Tax y recargos."""
        mc_sin_iva = self.eco["mc"]["monto"]
        self.eco["entradas_usadas"]["tasa_iva_bp"] = 500; self.w(self.eco)
        inf = self.inf()
        self.assertIn("X14_ECONOMIA", {h.codigo for h in inf.errores})          # mc declarado sin IVA ya no cuadra
        self.assertNotIn("X14_FORMULA_PENDIENTE", {h.codigo for h in inf.hallazgos})
        doc = self.regenerar()
        self.assertLess(doc["mc"]["monto"], mc_sin_iva)
        self.assertEqual(set(), self.codigos())
        for entorno in ("produccion", "prueba"):
            with mock.patch.dict(os.environ, {"FABRICA_ENTORNO": entorno}):
                self.assertNotIn("X14_FORMULA_PENDIENTE", {h.codigo for h in V.validar_oferta(self.dir, limites=self.lim, autonomia=self.aut, clave_firma=CLAVE).hallazgos})

    def test_limites_pendientes(self) -> None:
        self.lim = {**self.lim, "perdida_max_test_por_oferta": None, "perdida_neta_acumulada_max": None}   # CT2-11: lo declarado debe ser null de verdad
        self.eco["limites_pendientes"] = ["perdida_max_test_por_oferta", "perdida_neta_acumulada_max"]; self.w(self.eco)
        self.assertEqual(set(), self.codigos())
        self.eco["limites_pendientes"] = ["inventado"]; self.w(self.eco)
        self.assertIn("X14_LIMITES_PENDIENTES", self.codigos())

    def test_moneda_mezclada_en_los_campos_nuevos(self) -> None:
        self.eco["entradas_usadas"]["stripe_tax"]["fijo"]["moneda"] = "USD"; self.w(self.eco)
        self.assertIn("X14_ECONOMIA", self.codigos())

    def test_tarifas_de_llc_son_supuesto_con_fuente(self) -> None:
        t = V.TARIFAS_LLC_US_SUPUESTO
        self.assertEqual((290, 30, "USD", 150, 100), (t["comision_pct_bp"], t["comision_fija"]["monto"], t["comision_fija"]["moneda"], t["recargos_bp"], t["conversion_bp"]))
        self.assertIn("[SUPUESTO]", t["fuente"]); self.assertIn("https://stripe.com/pricing", t["fuente"])
        self.assertEqual([], V.buscar_floats(t))


class PruebaBriefMercadoCampanaCheckout(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.dir = Path(self._t.name) / "_ejemplo"
        shutil.copytree(V.RAIZ / "ofertas" / "_ejemplo", self.dir)
        self.lim = V.limites_de_prueba()
        self.aut = V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml")

    def j(self, rel): return V.cargar_json(self.dir / rel)
    def w(self, rel, o): (self.dir / rel).write_text(json.dumps(o, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def wc(self, camp) -> None:
        camp["hash_config"] = V.hash_objeto(camp, excluir=("hash_config",))
        self.w("07-campana/campana.json", camp)

    def wb(self, mut) -> None:
        """Muta el brief, recalcula su hash y re-firma (HMAC de prueba)."""
        b = V.cargar_yaml(self.dir / "00-brief.yaml")
        mut(b)
        b["hash"] = V.hash_objeto(b, excluir=("hash", "aprobado_por"))
        b["aprobado_por"]["firma"] = V.firma_hmac({"hash": b["hash"], "aprobador": b["aprobado_por"]["id"], "fecha": b["aprobado_por"]["fecha"]}, CLAVE)
        (self.dir / "00-brief.yaml").write_text(yaml.safe_dump(b, allow_unicode=True, sort_keys=False), encoding="utf-8")

    def inf(self, lim=None, par=None):
        _resellar(self.dir)
        return V.validar_oferta(self.dir, limites=lim or self.lim, parametros=par, autonomia=self.aut, clave_firma=CLAVE)

    def codigos(self, **kw) -> set[str]:
        return {h.codigo for h in self.inf(**kw).errores}

    def test_base_limpia(self) -> None:
        inf = self.inf()
        self.assertEqual([], [str(h) for h in inf.hallazgos])

    # --- brief
    def test_brief_con_los_nombres_viejos_o_version_vieja(self) -> None:
        b = _ej("brief")
        viejo = copy.deepcopy(b)
        viejo["presupuesto"] = {"test_total": b["presupuesto"]["test_total_max"], "test_diario": b["presupuesto"]["test_diario_max"], "ia_max": b["presupuesto"]["ia_max"]}
        self.assertTrue(V.errores_de_esquema("brief", viejo))
        v = copy.deepcopy(b); v["schema_version"] = "1.0.0"
        self.assertTrue(V.errores_de_esquema("brief", v))

    def test_el_plan_no_puede_superar_el_techo_del_brief(self) -> None:
        self.wb(lambda b: b["presupuesto"]["test_total_max"].update(monto=27599))
        self.assertIn("X10_BRIEF", self.codigos())

    def test_techo_del_brief_sobre_los_limites(self) -> None:
        lim = copy.deepcopy(self.lim)
        lim["gasto_total_test_por_oferta"] = 29000; lim["perdida_max_test_por_oferta"] = 29000
        lim["sello"]["hash"] = V.sello_de_limites(lim)
        self.assertIn("X10_BRIEF", self.codigos(lim=lim))

    def test_diario_mayor_que_total_y_monedas_mezcladas(self) -> None:
        self.wb(lambda b: b["presupuesto"]["test_diario_max"].update(monto=40000))
        self.assertIn("X10_BRIEF", self.codigos())
        self.wb(lambda b: b["presupuesto"]["ia_max"].update(moneda="USD"))
        self.assertIn("X10_MONEDA", self.codigos())

    def test_brief_en_otra_moneda_que_los_limites(self) -> None:
        def usd(b):
            for k in ("test_total_max", "test_diario_max", "ia_max"):
                b["presupuesto"][k]["moneda"] = "USD"
        self.wb(usd)
        c = self.codigos()
        self.assertIn("X10_MONEDA", c)

    def test_precio_fuera_del_rango_del_brief(self) -> None:
        self.wb(lambda b: b["precio_rango"]["max"].update(monto=1500))
        self.assertIn("X10_BRIEF", self.codigos())

    def test_brief_y_mercado_deben_coincidir(self) -> None:
        self.wb(lambda b: b["mercado_objetivo"].update(locale="it-IT"))
        self.assertIn("X30_MERCADO", self.codigos())

    def test_cuenta_del_brief_igual_a_ids_meta(self) -> None:
        camp = self.j("07-campana/campana.json")
        ids = dict(_ej("ids_meta"), hash_config=camp["hash_config"], ad_account_id="act_100000000000009")
        self.w("07-campana/ids_meta.json", ids)
        self.assertIn("X41_IDS", self.codigos())

    # --- mercado
    def test_diferido_sin_exposicion_firmada_no_se_lanza(self) -> None:
        m = self.j("mercado.json"); m["fiscal"]["exposicion_aceptada"] = None; self.w("mercado.json", m)
        self.assertIn("ESQUEMA", self.codigos())
        m["fiscal"]["regimen"] = "stripe_tax"; self.w("mercado.json", m)
        self.assertNotIn("ESQUEMA", self.codigos())

    def test_exposicion_que_no_cubre_los_paises(self) -> None:
        m = self.j("mercado.json"); m["paises_segmentacion"] = ["ES", "IT"]; self.w("mercado.json", m)
        c = self.j("07-campana/campana.json")
        self.assertIn("X32_FISCAL", self.codigos())

    def test_exposicion_con_firma_alterada_o_no_humana(self) -> None:
        m = self.j("mercado.json"); m["fiscal"]["exposicion_aceptada"]["paises"] = ["ES", "FR"]; self.w("mercado.json", m)
        self.assertIn("X32_FISCAL", self.codigos())          # el payload cambió: la firma ya no verifica
        m = self.j("mercado.json"); m["fiscal"]["exposicion_aceptada"]["firmada_por"]["tipo"] = "regla"; self.w("mercado.json", m)
        self.assertIn("ESQUEMA", self.codigos())

    def test_exposicion_hmac_no_vale_en_produccion(self) -> None:
        m = V.cargar_json(self.dir / "mercado.json")
        inf = V.Informe("t")
        ctx = V.Contexto(self.dir, {"mercado.json": m}, self.lim, None, self.aut, V.cargar_gates(), inf, CLAVE)
        with mock.patch.dict(os.environ, {"FABRICA_ENTORNO": "produccion"}):
            V.regla_mercado(ctx)
        self.assertIn("X32_FISCAL", {h.codigo for h in inf.errores})

    def test_idioma_obligatorio_sin_revisor_nativo_es_rojo_de_x1(self) -> None:
        m = self.j("mercado.json"); m["revision_linguistica"]["obligacion_legal_idioma"] = True; self.w("mercado.json", m)
        self.assertIn("X32_REVISOR", self.codigos())
        m["revision_linguistica"]["revisor_nativo"] = True; self.w("mercado.json", m)
        self.assertNotIn("X32_REVISOR", self.codigos())

    def test_mercado_viejo_pide_migrar(self) -> None:
        m = self.j("mercado.json"); m["schema_version"] = "1.0.0"
        self.assertTrue(V.errores_de_esquema("mercado", m))

    # --- campana: spend_cap
    def test_spend_cap_null_con_candado_alternativo_valido(self) -> None:
        c = self.j("07-campana/campana.json")
        p = c["presupuesto"]
        p["spend_cap"] = None; p["spend_cap_minimo_meta"] = 40000
        p["candado_alternativo"] = {"tipo": "stop_time_lifetime_budget", "stop_time": "2026-11-21T00:00:00Z", "lifetime_budget": 30360}
        self.wc(c)
        self.assertEqual([], [str(h) for h in self.inf().errores])

    def test_spend_cap_null_sin_candado_o_candado_con_cap(self) -> None:
        c = self.j("07-campana/campana.json"); c["presupuesto"]["spend_cap"] = None; self.wc(c)
        self.assertIn("ESQUEMA", self.codigos())
        c["presupuesto"]["spend_cap"] = 30360
        c["presupuesto"]["candado_alternativo"] = {"tipo": "stop_time_lifetime_budget", "stop_time": "2026-11-21T00:00:00Z", "lifetime_budget": 30360}
        self.wc(c)
        self.assertIn("ESQUEMA", self.codigos())

    def test_spend_cap_bajo_el_minimo_de_meta(self) -> None:
        c = self.j("07-campana/campana.json"); c["presupuesto"]["spend_cap_minimo_meta"] = 40000; self.wc(c)
        self.assertIn("X10_SPEND_CAP", self.codigos())

    def test_candado_innecesario_si_el_calculado_alcanza_el_minimo(self) -> None:
        c = self.j("07-campana/campana.json"); p = c["presupuesto"]
        p["spend_cap"] = None; p["candado_alternativo"] = {"tipo": "stop_time_lifetime_budget", "stop_time": "2026-11-21T00:00:00Z", "lifetime_budget": 30360}
        self.wc(c)
        self.assertIn("X10_SPEND_CAP", self.codigos())          # minimo 9300 < 30360

    def test_lifetime_budget_fuera_de_banda_o_sobre_los_limites(self) -> None:
        c = self.j("07-campana/campana.json"); p = c["presupuesto"]
        p["spend_cap"] = None; p["spend_cap_minimo_meta"] = 40000
        p["candado_alternativo"] = {"tipo": "stop_time_lifetime_budget", "stop_time": "2026-11-21T00:00:00Z", "lifetime_budget": 27000}
        self.wc(c)
        self.assertIn("X10_SPEND_CAP", self.codigos())          # < total_test
        p["candado_alternativo"]["lifetime_budget"] = 31000; self.wc(c)
        self.assertIn("X10_SPEND_CAP", self.codigos())          # > factor x total
        lim = copy.deepcopy(self.lim); lim["perdida_max_test_por_oferta"] = 29000; lim["gasto_total_test_por_oferta"] = 33000
        lim["sello"]["hash"] = V.sello_de_limites(lim)
        p["candado_alternativo"]["lifetime_budget"] = 30360; self.wc(c)
        self.assertIn("X10_LIMITES", self.codigos(lim=lim))     # el candado cuenta como tope de pérdida

    def test_minimo_sin_convertir_es_aviso_en_borrador_y_error_despues(self) -> None:
        c = self.j("07-campana/campana.json"); c["presupuesto"]["spend_cap_minimo_meta"] = None; self.wc(c)
        inf = self.inf()
        self.assertEqual(set(), {h.codigo for h in inf.errores})
        self.assertIn("X10_SPEND_CAP", {h.codigo for h in inf.hallazgos if h.nivel == "AVISO"})
        c["estado"] = "preflight_ok"; self.wc(c)
        self.assertIn("X10_SPEND_CAP", self.codigos())

    def test_minimo_igual_al_parametro_de_meta(self) -> None:
        par = _fusionar(V.cargar_yaml(V.RAIZ / "empresa" / "parametros.yaml"), V.cargar_yaml(V.RAIZ / "empresa" / "propuestas" / "parametros-b0.yaml"))
        par["grupos"]["campana"]["spend_cap_minimo_meta"]["valor"] = {"monto": 8000, "moneda": "EUR"}
        self.assertIn("X10_SPEND_CAP", self.codigos(par=par))     # el ejemplo declara 9300

    def test_edad_dura_y_sugerida_no_se_agregan_sin_verificacion(self) -> None:
        _, e = V.cargar_esquemas()
        aud = e["campana"]["properties"]["audiencia"]["properties"]
        self.assertNotIn("edad_sugerida", aud); self.assertNotIn("edad_dura", aud)
        self.assertIn("[VERIFICAR]", e["campana"]["description"])

    # --- checkout
    def test_checkout_sin_webhook_eventos(self) -> None:
        co = self.j("05-landing/checkout.json")
        self.assertNotIn("webhook_eventos", co)
        co["webhook_eventos"] = ["checkout.session.completed"]
        self.assertTrue(V.errores_de_esquema("checkout", co))
        co2 = self.j("05-landing/checkout.json"); co2["schema_version"] = "1.1.0"
        self.assertTrue(V.errores_de_esquema("checkout", co2))

    def test_ui_mode_sigue_marcado_verificar(self) -> None:
        _, e = V.cargar_esquemas()
        self.assertIn("[VERIFICAR]", e["checkout"]["properties"]["ui_mode"]["description"])
        self.assertEqual(["hosted", "embedded", "custom"], e["checkout"]["properties"]["ui_mode"]["enum"])


class PruebaArtefactosNuevosEnLaOferta(unittest.TestCase):
    """Reglas cruzadas X40-X46 con los archivos nuevos dentro de una copia de ofertas/_ejemplo."""

    def setUp(self) -> None:
        _sin_red(self)
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.dir = Path(self._t.name) / "_ejemplo"
        shutil.copytree(V.RAIZ / "ofertas" / "_ejemplo", self.dir)
        self.lim = V.limites_de_prueba()
        self.aut = V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml")
        self.camp = V.cargar_json(self.dir / "07-campana/campana.json")
        self.hc = self.camp["hash_config"]

    def w(self, rel, o): (self.dir / rel).write_text(json.dumps(o, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def wc(self, camp) -> None:
        camp["hash_config"] = V.hash_objeto(camp, excluir=("hash_config",))
        self.w("07-campana/campana.json", camp)
        self.hc = camp["hash_config"]

    def codigos(self) -> set[str]:
        return {h.codigo for h in V.validar_oferta(self.dir, limites=self.lim, autonomia=self.aut, clave_firma=CLAVE).errores}

    def poner(self, ids=True, ap=True, pf=True):
        i = dict(_ej("ids_meta"), hash_config=self.hc)
        if ids: self.w("07-campana/ids_meta.json", i)
        if ap:
            a = dict(_ej("aprobacion"), hash_objetivo=self.hc)
            a["aprobado_por"]["firma"] = V.firmar_hmac_de_prueba("aprobacion", a)
            self.w("07-campana/aprobacion.json", a)
        if pf: self.w("07-campana/preflight.json", dict(_ej("preflight"), hash_config=self.hc))

    def test_base_con_los_tres_archivos_coherentes(self) -> None:
        self.poner()
        self.assertEqual(set(), self.codigos())

    def test_ids_meta_de_otra_configuracion(self) -> None:
        self.poner(); self.w("07-campana/ids_meta.json", dict(_ej("ids_meta"), hash_config="sha256:" + "1" * 64))
        self.assertIn("X41_IDS", self.codigos())

    def test_ids_meta_con_otro_numero_de_anuncios(self) -> None:
        self.poner(); i = dict(_ej("ids_meta"), hash_config=self.hc); i["ad_ids"] = i["ad_ids"][:3]; self.w("07-campana/ids_meta.json", i)
        self.assertIn("X41_IDS", self.codigos())

    def test_aprobacion_de_otro_hash(self) -> None:
        self.poner()
        a = dict(_ej("aprobacion"), hash_objetivo="sha256:" + "2" * 64); a["aprobado_por"]["firma"] = V.firmar_hmac_de_prueba("aprobacion", a)
        self.w("07-campana/aprobacion.json", a)
        self.assertIn("X40_HASH", self.codigos())

    def test_aprobacion_con_object_ids_distintos(self) -> None:
        self.poner()
        a = dict(_ej("aprobacion"), hash_objetivo=self.hc); a["object_ids"] = a["object_ids"] + ["120000000000099"]
        a["aprobado_por"]["firma"] = V.firmar_hmac_de_prueba("aprobacion", a)
        self.w("07-campana/aprobacion.json", a)
        self.assertIn("X40_OBJETOS", self.codigos())

    def test_aprobacion_con_firma_hmac_falsa(self) -> None:
        self.poner()
        a = V.cargar_json(self.dir / "07-campana/aprobacion.json"); a["aprobado_por"]["firma"] = "hmac-sha256:" + "0" * 64
        self.w("07-campana/aprobacion.json", a)
        self.assertIn("X40_FIRMA", self.codigos())

    def test_campana_aprobada_sin_aprobacion_o_sin_preflight(self) -> None:
        c = self.camp; c["estado"] = "aprobada"; self.wc(c)
        self.assertIn("X40_HASH", self.codigos())
        self.assertIn("X41_PREFLIGHT", self.codigos())

    def test_preflight_rojo_bloquea_el_estado(self) -> None:
        c = self.camp; c["estado"] = "preflight_ok"; self.wc(c)
        pf = dict(_ej("preflight"), hash_config=self.hc); pf["checks"]["P20"]["estado"] = "ROJO"; pf["semaforo"] = "ROJO"
        self.w("07-campana/preflight.json", pf)
        self.assertIn("X41_PREFLIGHT", self.codigos())

    def test_preflight_de_otro_hash_y_vigencia_excesiva(self) -> None:
        self.w("07-campana/preflight.json", dict(_ej("preflight"), hash_config="sha256:" + "3" * 64))
        self.assertIn("X41_PREFLIGHT", self.codigos())
        pf = dict(_ej("preflight"), hash_config=self.hc, valido_hasta="2026-11-12T08:30:00Z")
        self.w("07-campana/preflight.json", pf)
        self.assertIn("X41_PREFLIGHT", self.codigos())            # > campana.preflight_vigencia_h (24 h)

    def test_categoria_especial_exige_p25(self) -> None:
        c = self.camp; c["special_ad_categories"] = ["FINANCIAL_PRODUCTS_SERVICES"]; self.wc(c)
        self.w("07-campana/preflight.json", dict(_ej("preflight"), hash_config=self.hc))
        self.assertIn("X41_PREFLIGHT", self.codigos())

    def test_traspaso_fuera_de_ids_meta(self) -> None:
        self.poner()
        t = _ej("traspaso"); t["anuncios"][0]["ad_id"] = "120000000000099"
        self.w("07-campana/traspaso.json", t)
        self.assertIn("X42_TRASPASO", self.codigos())

    def test_postmortem_contra_el_veredicto_y_los_parametros(self) -> None:
        self.w("08-operacion/postmortem.json", _ej("postmortem"))
        self.assertEqual(set(), self.codigos())
        p = _ej("postmortem"); p["veredicto"] = "VALIDADA"; self.w("08-operacion/postmortem.json", p)
        self.assertIn("X46_POSTMORTEM", self.codigos())
        p = _ej("postmortem"); p["veredicto_sha256"] = "sha256:" + "4" * 64; self.w("08-operacion/postmortem.json", p)
        self.assertIn("X46_POSTMORTEM", self.codigos())
        p = _ej("postmortem"); p["parametros_a_calibrar"][0]["parametro"] = "grupo.inexistente"; self.w("08-operacion/postmortem.json", p)
        self.assertIn("X46_POSTMORTEM", self.codigos())

    def test_decisiones_jsonl_se_validan_linea_a_linea(self) -> None:
        d = _ej("decision")
        (self.dir / "08-operacion/decisiones.jsonl").write_text(json.dumps(d) + "\n", encoding="utf-8")
        self.assertEqual(set(), self.codigos())
        d["decision_id"] = "sha256:" + "5" * 64
        (self.dir / "08-operacion/decisiones.jsonl").write_text(json.dumps(d) + "\n", encoding="utf-8")
        self.assertIn("X43_DECISION", self.codigos())

    def test_oferta_id_distinto_en_un_artefacto_nuevo(self) -> None:
        self.w("07-campana/ids_meta.json", dict(_ej("ids_meta"), hash_config=self.hc, oferta_id="OF-202611-02"))
        self.assertIn("X01_ID", self.codigos())


if __name__ == "__main__":
    unittest.main()
