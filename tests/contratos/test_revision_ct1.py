"""Revisión adversarial independiente de CT-1 (ola 0b-1). Informe: docs/_historial/ct1-revision.md.

Cada prueba afirma el comportamiento CORRECTO. Las marcadas ROJA fallan hoy porque el defecto existe (id del hallazgo en el
nombre del método); al aplicar la corrección del informe pasan. Las marcadas CONTROL pasan hoy y vigilan que una corrección
no rompa lo que ya funciona. Sin red ni credenciales: solo ``ssh-keygen`` local, y se omite si falta.
"""
from __future__ import annotations

import base64
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path

from scripts import validar_esquemas as V
from tests.contratos.test_ola_0b1 import _ej, _resellar, _sin_red

CLAVE = V.CLAVE_DE_PRUEBA
# ids_meta se agregó (CT1-18): su regla de coherencia (ids únicos entre tipos) vive en problemas_artefacto y la lista original la omitía.
COHERENCIA = ("aprobacion", "preflight", "sello", "orden_firmada", "decision", "conciliacion", "tipo_cambio", "traspaso", "postmortem", "ids_meta")


def _problemas(nombre: str, d: dict, tcs: list | None = None) -> list:
    """Esquema + float + coherencia interna. Si el código LANZA en vez de rechazar, la prueba falla con ese motivo."""
    out: list = [("ESQUEMA", e.message) for e in V.errores_de_esquema(nombre, d)]
    out += [("FLOAT", x) for x in V.buscar_floats(d)]
    if out:
        return out
    try:
        if nombre == "ledger":
            out += V.problemas_ledger([d], tcs)
        elif nombre in COHERENCIA:
            out += V.problemas_artefacto(nombre, d, clave=CLAVE, entorno="prueba")
    except Exception as exc:  # noqa: BLE001 - un dato hostil no debe tumbar al llamador
        raise AssertionError(f"{nombre}: lanzó {type(exc).__name__} ({exc}) en vez de rechazar con un código") from exc
    return out


def _mut(nombre: str, fn) -> list:
    d = copy.deepcopy(_ej(nombre))
    fn(d)
    return _problemas(nombre, d)


class PruebaPatronesYTiempo(unittest.TestCase):
    """CT1-01/02: `$` de Python tolera un `\\n` final; fechas imposibles pasan el esquema."""

    def test_CT1_01_id_meta_con_salto_de_linea_final(self) -> None:  # ROJA
        self.assertTrue(_mut("ids_meta", lambda d: d.update(campaign_id=d["campaign_id"] + "\n")))

    def test_CT1_01_nonce_con_salto_de_linea_final(self) -> None:  # ROJA
        self.assertTrue(_mut("orden_firmada", lambda d: d.update(nonce=d["nonce"] + "\n")))

    def test_CT1_01_par_de_tipo_cambio_con_salto_de_linea_final(self) -> None:  # ROJA
        d = copy.deepcopy(_ej("tipo_cambio"))
        d["par"] = "USD/EUR\n"
        self.assertTrue(V.errores_de_esquema("tipo_cambio", d))  # solo esquema: la coherencia interna lo atrapa por casualidad

    def test_CT1_01_hash_con_salto_de_linea_final(self) -> None:  # ROJA
        self.assertTrue(_mut("sello", lambda d: d.update(artefacto_sha256=d["artefacto_sha256"] + "\n")))

    def test_CT1_02_timestamp_con_mes_13_y_hora_99(self) -> None:  # ROJA (esquema acepta; problemas_artefacto LANZA)
        self.assertTrue(_mut("aprobacion", lambda d: d.update(vigencia_hasta="2026-13-45T99:99:99Z")))

    def test_CT1_02_fecha_inexistente_2026_02_31(self) -> None:  # ROJA
        def f(d):
            d["fecha"] = "2026-02-31"
            d["tipo_cambio_id"] = V.tipo_cambio_id_esperado(d["par"], d["fecha"])
        self.assertTrue(_mut("tipo_cambio", f))


class PruebaFirmas(unittest.TestCase):
    """CT1-03/04/05/06: formato Ed25519 real (SSHSIG), producción sin HMAC, payload que cubre el gate."""

    def test_CT1_03_ed25519_de_20_caracteres(self) -> None:  # ROJA
        self.assertTrue(_mut("sello", lambda d: d.update(firma="ed25519:AAAAAAAAAAAAAAAAAAAA")))

    def test_CT1_03_ed25519_de_solo_iguales(self) -> None:  # ROJA
        self.assertTrue(_mut("sello", lambda d: d.update(firma="ed25519:" + "=" * 40)))

    def test_CT1_03_ed25519_de_300_caracteres_sin_estructura(self) -> None:  # ROJA
        self.assertTrue(_mut("sello", lambda d: d.update(firma="ed25519:" + "A" * 300)))

    def test_CT1_04_los_ejemplos_validos_llevan_firmas_sshsig_verificables_por_el_motor(self) -> None:  # ROJA
        """engine.comun._armar_firma exige que el blob empiece por b'SSHSIG'; los ejemplos traen 64 bytes crudos."""
        malas = []
        for p in sorted(V.DIR_EJEMPLOS.glob("*.valido.json")):
            txt = p.read_text(encoding="utf-8")
            for m in __import__("re").findall(r'"(ed25519:[A-Za-z0-9+/=]+)"', txt):
                if not base64.b64decode(m[len("ed25519:"):]).startswith(b"SSHSIG"):
                    malas.append(p.name)
        self.assertEqual([], sorted(set(malas)))

    @unittest.skipUnless(shutil.which("ssh-keygen"), "ssh-keygen no disponible")
    def test_CONTROL_una_firma_real_de_ssh_keygen_pasa_el_esquema_del_sello(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            clave = Path(t) / "k"
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(clave)], check=True, capture_output=True)
            r = subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(clave), "-n", "fabrica-ofertas"], input=b"x", capture_output=True, check=True)
        lineas = r.stdout.decode().splitlines()
        firma = "ed25519:" + "".join(lineas[1:-1])
        self.assertEqual([], _mut("sello", lambda d: d.update(firma=firma)))

    def test_CT1_05_produccion_rechaza_sello_de_limites_con_hmac(self) -> None:  # ROJA
        lim = copy.deepcopy(V.limites_de_prueba())
        lim["sello"]["firma"] = "hmac-sha256:" + "a" * 64
        self.assertFalse(V.evaluar_limites(lim, "activar", entorno="produccion"))

    def test_CT1_05_produccion_rechaza_sello_de_limites_con_ed25519_basura(self) -> None:  # ROJA
        lim = copy.deepcopy(V.limites_de_prueba())
        lim["sello"]["firma"] = "ed25519:" + "A" * 20
        self.assertFalse(V.evaluar_limites(lim, "activar", entorno="produccion"))

    def test_CT1_05_produccion_sin_verificador_una_ed25519_de_buen_formato_no_es_aprobacion(self) -> None:  # ROJA
        """Hoy `problemas_firma` solo mira el formato: en producción cualquier cadena con forma de SSHSIG 'firma'."""
        firma = "ed25519:U1NIU0lH" + "A" * 240
        self.assertTrue(V.problemas_firma(firma, {"x": 1}, None, entorno="produccion"))

    def test_CT1_06_la_firma_de_la_aprobacion_cubre_nivel_y_gate(self) -> None:  # ROJA
        d = copy.deepcopy(_ej("aprobacion"))
        e = copy.deepcopy(d)
        e.update(nivel="N3", gate="S")
        self.assertNotEqual(V.payload_firma("aprobacion", d), V.payload_firma("aprobacion", e))

    def test_CT1_06_la_firma_de_la_aprobacion_cubre_tipo_y_creado_en(self) -> None:  # ROJA
        d = copy.deepcopy(_ej("aprobacion"))
        e = copy.deepcopy(d)
        e["creado_en"] = "2026-11-10T08:00:00Z"
        f = copy.deepcopy(d)
        f["aprobado_por"]["tipo"] = "regla"
        self.assertNotEqual(V.payload_firma("aprobacion", d), V.payload_firma("aprobacion", e))
        self.assertNotEqual(V.payload_firma("aprobacion", d), V.payload_firma("aprobacion", f))


class PruebaSelloYOrden(unittest.TestCase):
    def setUp(self) -> None:
        _sin_red(self)
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.emp = Path(self._t.name) / "empresa"

    def _sello(self, **cambios) -> Path:
        s = copy.deepcopy(_ej("sello"))
        s.update(cambios)
        carpeta = self.emp / "compliance" / "sellos"
        carpeta.mkdir(parents=True, exist_ok=True)
        ruta = carpeta / (s["artefacto_sha256"].split(":", 1)[1] + ".json")
        ruta.write_text(json.dumps(s), encoding="utf-8")
        return ruta

    def test_CT1_07_vigencia_del_sello_acotada_por_vigencia_dictamen_dias(self) -> None:  # ROJA
        self._sello(vigencia_hasta="9999-12-31T08:45:00Z")
        inf = V.Informe("t")
        V.validar_artefactos_de_empresa(self.emp, inf, clave=CLAVE)
        self.assertTrue(inf.errores)

    def test_CT1_08_sello_con_dictamen_de_otra_etapa(self) -> None:  # ROJA
        self.assertTrue(_mut("sello", lambda d: d.update(dictamen_ref="qa/x1-d5-v1.json")))

    def test_CT1_08_sello_con_dictamen_ref_que_no_es_un_dictamen(self) -> None:  # ROJA
        self.assertTrue(_mut("sello", lambda d: d.update(dictamen_ref="qa/x1-zzz.txt")))

    def test_CT1_09_nonce_repetido_en_el_export_de_ordenes(self) -> None:  # ROJA
        o = _ej("orden_firmada")
        o2 = dict(o, ts="2026-11-10T09:05:00Z")  # misma nonce, otro instante
        self.emp.mkdir(parents=True, exist_ok=True)
        (self.emp / "ordenes_firmadas.jsonl").write_text(json.dumps(o) + "\n" + json.dumps(o2) + "\n", encoding="utf-8")
        inf = V.Informe("t")
        V.validar_artefactos_de_empresa(self.emp, inf, clave=CLAVE)
        self.assertTrue(inf.errores)

    def test_CT1_09_nonce_con_mayusculas_colisiona_en_sistemas_de_archivos_insensibles(self) -> None:  # ROJA
        """guard lee empresa/ordenes/<nonce>.json: en APFS/NTFS `ABC...` y `abc...` son el mismo archivo."""
        self.assertTrue(_mut("orden_firmada", lambda d: d.update(nonce="N0NCE-EJEMPLO-0001-ABCDEF")))

    def test_CT1_10_object_ids_solo_con_activar_campana(self) -> None:  # ROJA
        self.assertTrue(_mut("orden_firmada", lambda d: d.update(accion="pausar")))

    def test_CT1_11_tipo_cambio_id_repetido_con_tasa_distinta(self) -> None:  # ROJA
        t = _ej("tipo_cambio")
        t2 = dict(t, tasa="0.5000")
        (self.emp / "finanzas").mkdir(parents=True, exist_ok=True)
        (self.emp / "finanzas" / "tipos_cambio.jsonl").write_text(json.dumps(t) + "\n" + json.dumps(t2) + "\n", encoding="utf-8")
        inf = V.Informe("t")
        V.validar_artefactos_de_empresa(self.emp, inf, clave=CLAVE)
        self.assertTrue(inf.errores)


class PruebaDecisionTraspaso(unittest.TestCase):
    def test_CT1_12_probabilidad_fuera_de_0_1(self) -> None:  # ROJA (fraccion en decision, % en limites: unidades mezcladas)
        self.assertTrue(_mut("decision", lambda d: d["evidencia"].update(p_cpa_menor_equilibrio="95")))

    def test_CT1_12_probabilidad_mayor_que_uno_con_decimales(self) -> None:  # ROJA
        self.assertTrue(_mut("decision", lambda d: d["evidencia"].update(p_cpa_menor_equilibrio="1.5")))

    def test_CT1_13_matar_en_n1_con_gate_automatico(self) -> None:  # ROJA (tabla: accion:pausar H en N0-N1)
        self.assertTrue(_mut("decision", lambda d: d.update(nivel="N1", gate="A")))

    def test_CT1_14_objeto_meta_con_id_no_numerico(self) -> None:  # ROJA
        def f(d):
            d["objeto_id"] = "abc"
            d["decision_id"] = V.decision_id_esperado(d["oferta_id"], "abc", d["lectura_ts"])
        self.assertTrue(_mut("decision", f))

    def test_CT1_15_traspaso_disapproved_con_rechazado_false(self) -> None:  # ROJA
        self.assertTrue(_mut("traspaso", lambda d: d["anuncios"][0].update(effective_status="DISAPPROVED")))

    def test_CT1_15_traspaso_estable_con_todos_los_anuncios_pausados(self) -> None:  # ROJA
        def f(d):
            for a in d["anuncios"]:
                a["effective_status"] = "PAUSED"
        self.assertTrue(_mut("traspaso", f))

    def test_CT1_16_adid_capturado_sobre_100_por_ciento(self) -> None:  # ROJA
        self.assertTrue(_mut("traspaso", lambda d: d.update(adid_capturado_bp=15000)))

    def test_CT1_16_cobertura_adid_sobre_100_por_ciento(self) -> None:  # ROJA
        self.assertTrue(_mut("conciliacion", lambda d: d.update(cobertura_adid_bp=15000)))

    def test_CT1_17_senal_pausa_consumida_por_decision_id_mal_formado(self) -> None:  # ROJA
        self.assertTrue(_mut("senal_pausa", lambda d: d.update(consumida_por={"etapa": "D8", "decision_id": "x", "ts": "2026-11-12T10:00:00Z"})))

    def test_CT1_18_ids_de_meta_repetidos_entre_tipos(self) -> None:  # ROJA
        self.assertTrue(_mut("ids_meta", lambda d: d.update(adset_ids=[d["campaign_id"]])))


class PruebaFinanzas(unittest.TestCase):
    def test_CT1_19_ledger_gasto_como_entrada(self) -> None:  # ROJA
        self.assertTrue(_mut("ledger", lambda d: d.update(tipo="gasto", sentido="entrada")))

    def test_CT1_19_ledger_pedido_como_salida(self) -> None:  # ROJA
        self.assertTrue(_mut("ledger", lambda d: d.update(sentido="salida")))

    def test_CT1_19_ledger_reembolso_como_entrada(self) -> None:  # ROJA
        self.assertTrue(_mut("ledger", lambda d: d.update(tipo="reembolso", sentido="entrada", clave_natural="stripe:re_abc123")))

    def test_CT1_20_ledger_fecha_distinta_del_dia_de_ts(self) -> None:  # ROJA
        self.assertTrue(_mut("ledger", lambda d: d.update(fecha="2026-01-01")))

    def test_CT1_21_ledger_tipo_cambio_que_no_corresponde_a_las_monedas(self) -> None:  # ROJA
        tc = dict(_ej("tipo_cambio"), tipo_cambio_id="TC-GBPJPY-20261112", par="GBP/JPY", fecha="2026-11-12")
        d = dict(_ej("ledger"), tipo_cambio_id="TC-GBPJPY-20261112", importe_base={"monto": 1990, "moneda": "USD"})
        self.assertTrue(_problemas("ledger", d, tcs=[tc]))  # importe EUR, base USD, tasa GBP/JPY

    def test_CT1_21_ledger_importe_base_que_no_es_importe_por_tasa(self) -> None:  # ROJA
        tc = dict(_ej("tipo_cambio"), tipo_cambio_id="TC-EURUSD-20261112", par="EUR/USD", fecha="2026-11-12", tasa="1.0800")
        d = dict(_ej("ledger"), tipo_cambio_id="TC-EURUSD-20261112", importe_base={"monto": 5, "moneda": "USD"})  # 1990 x 1,08 = 2149
        self.assertTrue(_problemas("ledger", d, tcs=[tc]))

    def test_CT1_22_conciliado_con_cobertura_cero(self) -> None:  # ROJA (B0-15: cobertura >= minimo)
        self.assertTrue(_mut("conciliacion", lambda d: d.update(cobertura_adid_bp=0)))

    def test_CT1_22_razon_meta_stripe_incoherente_con_las_compras(self) -> None:  # ROJA
        self.assertTrue(_mut("conciliacion", lambda d: d["compras"].update(razon_meta_stripe="9.99")))

    def test_CT1_23_moneda_xxx_no_es_una_moneda_de_cobro(self) -> None:  # ROJA
        self.assertTrue(_mut("ledger", lambda d: d["importe"].update(moneda="XXX")))

    def test_CT1_24_importe_sobre_el_entero_seguro_de_js(self) -> None:  # ROJA (Workers de Cloudflare leen Number)
        self.assertTrue(_mut("ledger", lambda d: d["importe"].update(monto=2 ** 60)))


class PruebaLimitesUnidades(unittest.TestCase):
    def _lim(self, **cambios) -> dict:
        lim = copy.deepcopy(V.limites_de_prueba())
        lim.update(cambios)
        lim["sello"]["hash"] = V.sello_de_limites(lim)
        return lim

    def _rechaza(self, lim: dict, operacion: str) -> bool:
        return bool(V.errores_de_esquema("limites", lim)) or not V.evaluar_limites(lim, operacion, entorno="prueba")

    def test_CT1_25_aumento_por_paso_de_2000_por_ciento(self) -> None:  # ROJA
        self.assertTrue(self._rechaza(self._lim(aumento_presupuesto_max_pct_por_paso=2000), "aumentar_presupuesto"))

    def test_CT1_25_ratio_de_disputas_mayor_que_uno(self) -> None:  # ROJA (es fraccion: 6 = 600 %)
        self.assertTrue(self._rechaza(self._lim(ratio_disputas_pausa="6"), "gastar"))

    def test_CT1_25_reserva_no_publicitaria_de_250_por_ciento(self) -> None:  # ROJA
        self.assertTrue(self._rechaza(self._lim(reserva_no_publicitaria_pct=250), "gastar"))


class PruebaParametrosVersion(unittest.TestCase):
    def test_CT1_26_parametros_1_0_0_no_puede_traer_grupos_de_la_1_1_0(self) -> None:  # ROJA
        base = V.cargar_yaml(V.RAIZ / "empresa" / "parametros.yaml")
        prop = V.cargar_yaml(V.RAIZ / "empresa" / "propuestas" / "parametros-b0.yaml")
        par = copy.deepcopy(base)
        par["grupos"]["watchdog"] = copy.deepcopy(prop["grupos"]["watchdog"])
        par["schema_version"] = "1.0.0"
        self.assertTrue(V.errores_de_esquema("parametros", par))


class PruebaOfertaCompleta(unittest.TestCase):
    """Reglas cruzadas sobre una copia de ofertas/_ejemplo."""

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
        self.hc = camp["hash_config"]

    def informe(self):
        _resellar(self.dir)
        return V.validar_oferta(self.dir, limites=self.lim, autonomia=self.aut, clave_firma=CLAVE)

    def codigos(self) -> set[str]:
        return {h.codigo for h in self.informe().errores}

    def poner_artefactos(self, mut_ap=None) -> None:
        camp = self.j("07-campana/campana.json")
        self.hc = camp["hash_config"]
        self.w("07-campana/ids_meta.json", dict(_ej("ids_meta"), hash_config=self.hc))
        a = copy.deepcopy(dict(_ej("aprobacion"), hash_objetivo=self.hc))
        if mut_ap:
            mut_ap(a)
        if a["aprobado_por"].get("firma") is not None:
            a["aprobado_por"]["firma"] = V.firmar_hmac_de_prueba("aprobacion", a)
        self.w("07-campana/aprobacion.json", a)
        self.w("07-campana/preflight.json", dict(_ej("preflight"), hash_config=self.hc))

    def test_CONTROL_base_con_los_tres_archivos_es_limpia(self) -> None:
        self.poner_artefactos()
        self.assertEqual(set(), self.codigos())

    def test_CT1_27_aprobacion_que_se_autodeclara_n3_sin_firma_en_una_oferta_n2(self) -> None:  # ROJA (BLOQUEANTE)
        def f(a):
            a.update(nivel="N3", gate="S")
            a["aprobado_por"].update(tipo="regla", firma=None)
        self.poner_artefactos(f)
        self.assertTrue(self.codigos(), "activar_campana sin firma humana en una oferta N2 pasa el validador")

    def test_CT1_28_vigencia_de_la_aprobacion_de_9999(self) -> None:  # ROJA
        self.poner_artefactos(lambda a: a.update(vigencia_hasta="9999-12-31T00:00:00Z"))
        self.assertTrue(self.codigos())

    def test_CT1_29_decision_id_repetido_en_decisiones_jsonl(self) -> None:  # ROJA
        d = _ej("decision")
        (self.dir / "08-operacion").mkdir(exist_ok=True)
        (self.dir / "08-operacion" / "decisiones.jsonl").write_text(json.dumps(d) + "\n" + json.dumps(d) + "\n", encoding="utf-8")
        self.assertTrue(self.codigos())

    def test_CT1_30_decimales_distintos_del_exponente_iso_de_la_moneda(self) -> None:  # ROJA (EUR = 2)
        c = self.j("07-campana/campana.json")
        c["presupuesto"]["decimales"] = 0
        self.wc(c)
        self.assertTrue(self.codigos())

    def _economia_con_iva(self, mc: int) -> None:
        e = self.j("03-oferta/economia.json")
        en = e["entradas_usadas"]
        ce = en["escenarios"]["central"]
        en["tasa_iva_bp"] = 2100
        e["mc"]["monto"] = e["cpa_be"]["monto"] = mc
        e["cpa_be_visto"]["monto"] = V.entero_redondeado(mc * 10000, 10000 + en["tarifa_meta_bp"])
        num = e["gasto_test_plan"]["monto"] * (mc * ce["ctr_enlace_bp"] * ce["clic_compra_bp"] - ce["cpm"]["monto"] * 100000)
        e["resultado_esperado_central"]["monto"] = V.entero_redondeado(num, ce["cpm"]["monto"] * 100000, "half_even")
        e["razon"] = str((Decimal(mc) / Decimal(e["cpa_real"]["central"]["monto"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_EVEN))
        self.w("03-oferta/economia.json", e)

    def test_CT1_31_economia_con_iva_se_recalcula_con_la_formula_unica(self) -> None:
        """CT1-31 (cerrado en CT-2): con IVA X14 ya no deja pasar un mc escrito a mano; lo recalcula con engine.factibilidad.calcular."""
        self._economia_con_iva(1500)
        self.assertIn("03-oferta/economia.json/mc", [h.ruta for h in self.informe().errores if h.codigo == "X14_ECONOMIA"])
        from engine import factibilidad
        e = self.j("03-oferta/economia.json")
        entradas = {**e["entradas_usadas"], "gasto_diario": e["gasto_test_plan"]["monto"] // e["dias_test"]}
        doc = factibilidad.documento_economia(entradas, V.cargar_yaml(V.RAIZ / "empresa" / "parametros.yaml"), V.limites_de_prueba(), oferta_id=e["oferta_id"])
        self.w("03-oferta/economia.json", doc)
        malos = [str(h) for h in self.informe().errores if h.codigo == "X14_ECONOMIA" and h.ruta.startswith("03-oferta/economia.json")]
        self.assertEqual([], malos)

    def test_CONTROL_31_economia_con_iva_y_mc_mayor_que_el_aov_se_rechaza(self) -> None:
        """Hoy lo rechaza solo por el error de CT1-31; al corregir `razon` debe seguir rechazándose (mc <= aov)."""
        self._economia_con_iva(999999)
        self.assertTrue(self.codigos())


if __name__ == "__main__":
    unittest.main()
