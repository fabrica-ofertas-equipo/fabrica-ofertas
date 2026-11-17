"""Pruebas ROJAS adversariales de la revisión independiente de CT-2 (docs/_historial/ct2-revision.md).

Cada prueba afirma el comportamiento CORRECTO y hoy FALLA (documenta un hallazgo del informe: id en el nombre). Cuando se aplique la corrección
del informe, la prueba pasa a verde. Las pruebas ``TestVerdes*`` fijan lo que SÍ funciona (evidencia de lo revisado) y deben seguir en verde.

Comando: ``.venv/bin/python -m unittest tests.contratos.test_revision_ct2`` (o ``pytest tests/contratos/test_revision_ct2.py``).
Solo opera sobre copias temporales de ``ofertas/_ejemplo``; nunca escribe en el repositorio.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from unittest import mock

from engine import factibilidad as F
from engine.errores import ErrorValidacion
from scripts import validar_esquemas as V
from tests.contratos import aplicar_mutacion_landing as A
from tests.contratos import lint_landing_referencia as L
from tests.contratos.test_factibilidad import con_escenarios, entradas

RAIZ = Path(__file__).resolve().parents[2]
EJ = RAIZ / "ofertas" / "_ejemplo"
PARAM = V.cargar_yaml(RAIZ / "empresa" / "parametros.yaml")


# --------------------------------------------------------------------------------------------------------------------
# Apoyo
# --------------------------------------------------------------------------------------------------------------------
class Temporal(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="rev-ct2-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)


class Landing(Temporal):
    """Copia temporal marcada del ejemplo + helpers para sembrar un defecto y leer las reglas que dispara el lint de referencia."""

    def setUp(self) -> None:
        super().setUp()
        self.copia = A.copiar_ejemplo(self.tmp)
        self.sitio = self.copia / "05-landing" / "sitio"

    def sub(self, rel: str, buscar: str, reemplazo: str) -> None:
        p = self.sitio / rel
        t = p.read_text(encoding="utf-8")
        self.assertIn(buscar, t, f"{rel}: el ancla ya no existe (¿cambió el ejemplo?)")
        p.write_text(t.replace(buscar, reemplazo, 1), encoding="utf-8")

    def reglas(self) -> set[str]:
        return L.reglas(L.lint(self.copia))

    def assertDispara(self, regla: str | None = None) -> None:
        r = self.reglas()
        self.assertTrue(r, "el lint de publicación NO detectó el defecto sembrado")
        if regla:
            self.assertIn(regla, r)


def copia_ejemplo(tmp: Path) -> Path:
    destino = tmp / "_ejemplo"
    shutil.copytree(EJ, destino)
    return destino


def validar(d: Path):
    return V.validar_oferta(d, limites=V.limites_de_prueba(), autonomia=V.cargar_yaml(V.DIR_EJEMPLOS / "autonomia.valido.yaml"),
                            clave_firma=V.CLAVE_DE_PRUEBA)


def codigos(inf, prefijo: str = "") -> set[str]:
    return {e.codigo for e in inf.errores if e.codigo.startswith(prefijo)}


def editar_economia(d: Path, fn) -> None:
    p = d / "03-oferta" / "economia.json"
    e = json.loads(p.read_text(encoding="utf-8"))
    fn(e)
    p.write_text(json.dumps(e, ensure_ascii=False, indent=2), encoding="utf-8")


def entradas_ejemplo(**cambios) -> dict:
    eco = V.cargar_json(EJ / "03-oferta" / "economia.json")
    e = {**copy.deepcopy(eco["entradas_usadas"]), "gasto_diario": 2760, "oferta_id": eco["oferta_id"]}
    e.update(cambios)
    return e


# --------------------------------------------------------------------------------------------------------------------
# A. Economía: fórmulas, validación de entradas, CLI y documento
# --------------------------------------------------------------------------------------------------------------------
class TestEconomiaRoja(Temporal):
    def test_R01_documento_economia_con_enteros_produce_un_json_valido_contra_el_esquema(self) -> None:
        """CT2-01: ``economia_unitaria`` admite dinero como entero, pero ``documento_economia`` lo copia tal cual y el JSON incumple el esquema."""
        ent = con_escenarios(oferta_id="OF-202611-01", tarifas_fecha="2026-11-05", tarifas_fuente="[SUPUESTO] prueba", tarifas_origen="supuesto")
        doc = F.documento_economia(ent, PARAM, None)
        errores = V.errores_de_esquema("economia", doc)
        self.assertEqual([], [e.message for e in errores][:3])

    def test_R02_verificar_detecta_un_veredicto_alterado(self) -> None:
        """CT2-02: ``verificar`` (B0-02) no compara ``veredicto``: un FACTIBLE cambiado a NO_FACTIBLE sale «reproducible»."""
        eco = V.cargar_json(EJ / "03-oferta" / "economia.json")
        eco["veredicto"] = "NO_FACTIBLE"
        self.assertTrue(F.verificar(eco, PARAM, None), "verificar no vio que el veredicto declarado contradice la razón 1,43")

    def test_R03_verificar_con_dias_test_cero_no_revienta_con_zerodivisionerror(self) -> None:
        """CT2-03: ``verificar`` hace ``plan % dias`` sin validar: ``dias_test`` 0 o ausente da traceback (exit 1) en lugar de salida 3."""
        eco = V.cargar_json(EJ / "03-oferta" / "economia.json")
        eco["dias_test"] = 0
        try:
            F.verificar(eco, PARAM, None)
        except ErrorValidacion:
            return
        except Exception as exc:                      # noqa: BLE001 - lo que se prueba es justamente el tipo
            self.fail(f"excepción no tipada {type(exc).__name__}: {exc}")

    def test_R04_cli_con_entradas_que_no_son_un_objeto_sale_con_3_sin_traceback(self) -> None:
        """CT2-03: ``entradas`` = ``[1,2]`` o ``null`` produce AttributeError (exit 1)."""
        for contenido in ("[1, 2]", "null", "7"):
            ruta = self.tmp / "e.json"
            ruta.write_text(contenido, encoding="utf-8")
            try:
                codigo = F.main(["calcular", "--entradas", str(ruta)])
            except Exception as exc:                  # noqa: BLE001
                self.fail(f"entradas {contenido!r}: traceback {type(exc).__name__} (debía salir con 3)")
            self.assertEqual(3, codigo, contenido)

    def test_R05_tasas_fuera_de_rango_se_rechazan_en_el_nucleo(self) -> None:
        """CT2-04: el núcleo acepta reembolso/disputa/bump/IVA > 100 % (el envoltorio sí los rechaza): la «única» fórmula debe validar."""
        for clave in ("tasa_reembolso_bp", "tasa_disputa_bp", "tasa_bump_bp"):
            with self.assertRaises(ErrorValidacion, msg=clave):
                F.economia_unitaria(entradas(**{clave: 20000}))

    def test_R06_moneda_debe_ser_iso_4217(self) -> None:
        """CT2-05: ``moneda`` solo se comprueba como ``str``: ``""``, ``"usd"`` o ``"US"`` pasan y llegan al JSON."""
        for m in ("", "usd", "US", "DOLAR"):
            with self.assertRaises(ErrorValidacion, msg=repr(m)):
                F.economia_unitaria(entradas(moneda=m))

    def test_R07_resultado_esperado_central_no_contradice_a_la_razon_con_tarifa_de_meta(self) -> None:
        """CT2-06: con ``tarifa_meta_bp`` > 0 la razón usa el CPA visto pero ``resultado_esperado_central`` usa ``cpa_be``: razón < 1 con ganancia esperada > 0."""
        ent = con_escenarios(tarifa_meta_bp=3000, oferta_id="X")
        ent["escenarios"]["central"]["cpm"] = 800          # cpa_real ≈ 2273: entre cpa_be/1,3 = 1878 y cpa_be = 2442
        r = F.calcular(ent, PARAM, None)
        razon, res = Decimal(r["razon"]), r["resultado_esperado_central"]["monto"]
        self.assertLess(razon, 1, "la prueba necesita razón < 1")
        self.assertLessEqual(res, 0, f"razón {razon} < 1 (pierde dinero) pero resultado_esperado_central = {res} > 0")

    def test_R08_documento_economia_no_escribe_dias_test_menor_al_minimo_de_d3(self) -> None:
        """CT2-07: con ``dias_test`` explícito se salta ``max(7, ⌈min/diario⌉)``: 1 día a 27 600/día se acepta."""
        ent = entradas_ejemplo(dias_test=1, gasto_diario=27600)
        with self.assertRaises(ErrorValidacion):
            F.calcular(ent, PARAM, None)

# --------------------------------------------------------------------------------------------------------------------
# B. X14 (validador): el veredicto, los pendientes y los días no están verificados
# --------------------------------------------------------------------------------------------------------------------
class TestX14Roja(Temporal):
    def _con_economia(self, **cambios):
        d = copia_ejemplo(self.tmp)
        doc = F.documento_economia(entradas_ejemplo(**cambios), PARAM, V.limites_de_prueba(), version="v1")
        (d / "03-oferta" / "economia.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        return d, doc

    def test_R10_x14_rechaza_ajustada_cuando_la_razon_es_suficiente(self) -> None:
        """CT2-09: X14 solo contrasta FACTIBLE y NO_FACTIBLE; ``AJUSTADA`` con razón 1,43 (≥ 1,3) pasa sin error."""
        d = copia_ejemplo(self.tmp)
        editar_economia(d, lambda e: e.update(veredicto="AJUSTADA"))
        self.assertIn("X14_ECONOMIA", codigos(validar(d)), "AJUSTADA con razón 1,43 debe ser FACTIBLE")

    def test_R11_x14_rechaza_ajustada_con_razon_menor_a_uno_que_es_no_factible(self) -> None:
        """CT2-09: una oferta que pierde dinero (razón < 1) disfrazada de AJUSTADA entra al flujo."""
        d, doc = self._con_economia(escenarios={**entradas_ejemplo()["escenarios"], "central": {"cpm": {"monto": 900, "moneda": "EUR"},
                                                                                                "ctr_enlace_bp": 160, "clic_compra_bp": 220}})
        self.assertLess(Decimal(doc["razon"]), 1)
        self.assertEqual("NO_FACTIBLE", doc["veredicto"])
        editar_economia(d, lambda e: e.update(veredicto="AJUSTADA"))
        self.assertIn("X14_ECONOMIA", codigos(validar(d)))

    def test_R12_x14_compara_el_veredicto_con_la_razon_sin_redondear(self) -> None:
        """CT2-10: X14 usa la razón YA redondeada a 2 decimales: razón real 1,2987 se muestra «1.30» y un FACTIBLE (≥ 1,3) pasa; ``calcular`` dice AJUSTADA."""
        d, doc = self._con_economia(escenarios={**entradas_ejemplo()["escenarios"], "central": {"cpm": {"monto": 496, "moneda": "EUR"},
                                                                                                "ctr_enlace_bp": 160, "clic_compra_bp": 220}})
        self.assertEqual("1.30", doc["razon"])
        self.assertEqual("AJUSTADA", doc["veredicto"], "razón real 1,2987 < 1,3")
        editar_economia(d, lambda e: e.update(veredicto="FACTIBLE"))
        self.assertIn("X14_ECONOMIA", codigos(validar(d)), "FACTIBLE con razón real 1,2987 < razon_min_factible 1,3 debe fallar")

    def test_R13_x14_rechaza_limites_pendientes_que_no_coinciden_con_limites(self) -> None:
        """CT2-11: ``limites_pendientes`` declarado ['moneda_limites'] con todos los límites cargados solo da un AVISO; debe ser error (la economía miente)."""
        d = copia_ejemplo(self.tmp)
        editar_economia(d, lambda e: e.update(limites_pendientes=["moneda_limites"]))
        self.assertIn("X14_LIMITES_PENDIENTES", codigos(validar(d)))

    def test_R14_x14_rechaza_dias_test_menores_al_minimo(self) -> None:
        """CT2-07: X14 acepta ``dias_test`` = 1 (D3 §3.4: al menos 7); además deja pasar un diario 10 veces mayor que el del plan."""
        d = copia_ejemplo(self.tmp)
        editar_economia(d, lambda e: e.update(dias_test=1))
        self.assertIn("X14_ECONOMIA", codigos(validar(d)))

    def test_R15_x14_no_se_deja_inflar_perdida_max_test(self) -> None:
        """CT2-12: ``costos_fijos_oferta`` se deduce de la propia ``perdida_max_test`` declarada (tautología): cualquier valor ≥ plan pasa."""
        d = copia_ejemplo(self.tmp)
        editar_economia(d, lambda e: e.update(perdida_max_test={"monto": 27600 + 5000, "moneda": "EUR"}))
        self.assertIn("X14_ECONOMIA", codigos(validar(d)), "perdida_max_test no es reproducible desde entradas_usadas")


# --------------------------------------------------------------------------------------------------------------------
# C. Raíz configurable y firmas de prueba
# --------------------------------------------------------------------------------------------------------------------
class TestRaizRoja(Temporal):
    def _con_raiz(self, valor: str):
        with mock.patch.dict(os.environ, {"FABRICA_RAIZ": valor}):
            return V.raiz_datos()

    def test_R16_raiz_datos_con_ruta_relativa_se_resuelve_a_absoluta(self) -> None:
        """CT2-13: ``FABRICA_RAIZ=relativo`` deja ``raiz_datos()`` relativa y la CLI valida ``relativo/relativo/ofertas/_ejemplo`` (doble prefijo)."""
        self.assertTrue(self._con_raiz("relativo").is_absolute(), "raiz_datos() debe resolver (engine.comun.raiz() sí lo hace)")

    def test_R17_cli_con_raiz_relativa_no_duplica_el_prefijo(self) -> None:
        """CT2-13: la oferta por defecto se busca en ``<raiz>/<raiz>/ofertas/_ejemplo`` si la raíz es relativa."""
        base = self.tmp / "base"
        (base / "r" / "ofertas").mkdir(parents=True)
        shutil.copytree(EJ, base / "r" / "ofertas" / "_ejemplo")
        env = {k: v for k, v in os.environ.items() if not k.startswith("FABRICA_")}
        env["FABRICA_RAIZ"] = "r"
        r = subprocess.run([sys.executable, "-m", "scripts.validar_esquemas"], cwd=base, env={**env, "PYTHONPATH": str(RAIZ)},
                           capture_output=True, text=True, timeout=120)
        self.assertNotIn("r/r/ofertas", r.stdout, r.stdout[-300:])

    def test_R18_guard_con_raiz_inexistente_falla_cerrado_con_4_o_5(self) -> None:
        """CT2-14: con ``FABRICA_RAIZ`` inexistente el guard sale BLOQUEADO en el paso «entorno» con 4 (infra) o 5 (límites), nunca con 2 ni con «paso «None»»."""
        env = {k: v for k, v in os.environ.items() if not k.startswith("FABRICA_")}
        env.update(FABRICA_RAIZ=str(self.tmp / "no-existe"), FABRICA_ENTORNO="produccion")
        r = subprocess.run([sys.executable, "-m", "engine.guard", "comprobar", "--operacion", "gastar", "--oferta", "OF-202611-01", "--monto", "100",
                            "--moneda", "EUR"], cwd=RAIZ, env=env, capture_output=True, text=True, timeout=120)
        # S-B aplicó CT2-14 en engine/guard.py (2026-11-06): ya sale con 4 y «paso «entorno»»; se vuelve a fijar (4, 5) y que no aparezca «None».
        self.assertIn(r.returncode, (4, 5), r.stdout[-200:] + r.stderr[-200:])
        self.assertNotIn("«None»", r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)

    def test_R19_la_clave_de_prueba_solo_vale_para_el_ejemplo_del_repositorio_no_para_cualquier_carpeta_llamada_ejemplo(self) -> None:
        """CT2-15: ``dir_o.name == "_ejemplo"`` activa límites ficticios y la clave pública de prueba para CUALQUIER carpeta con ese nombre."""
        d = copia_ejemplo(self.tmp)
        env = {k: v for k, v in os.environ.items() if not k.startswith("FABRICA_")}
        r = subprocess.run([sys.executable, "-m", "scripts.validar_esquemas", "oferta", str(d)], cwd=RAIZ, env=env, capture_output=True, text=True, timeout=120)
        self.assertNotEqual(0, r.returncode, "una copia fuera de ofertas/_ejemplo no debe validarse con la clave pública de prueba")

    def test_R20_hash_de_archivo_no_depende_de_la_ruta_absoluta_del_repositorio(self) -> None:
        """CT2-16: ``hash_archivo`` decide «lo servido, por bytes» con ``"sitio" in ruta.parts`` sobre la ruta ABSOLUTA: el mismo .html tiene otro hash si el clon vive en ``/…/sitio/…``."""
        a = self.tmp / "sitio" / "repo" / "04-producto"
        b = self.tmp / "otro" / "repo" / "04-producto"
        for d in (a, b):
            d.mkdir(parents=True)
            (d / "plantilla.html").write_bytes("<p>café</p>\r\n".encode())
        self.assertEqual(V.hash_archivo(a / "plantilla.html"), V.hash_archivo(b / "plantilla.html"))


class TestSellosRojo(Temporal):
    def test_R43_alterar_rutas_json_rompe_algun_sello(self) -> None:
        """CT2-33: ``rutas.json`` (la lista cerrada de rutas de la que dependen el lint y ``landing.validar``) no entra en ningún hash: se le agrega una ruta y el validador sigue en 0 errores de sello."""
        d = copia_ejemplo(self.tmp)
        p = d / "05-landing" / "rutas.json"
        r = json.loads(p.read_text(encoding="utf-8"))
        r["/oculta"] = "estatica:oculta"
        p.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
        self.assertTrue(codigos(validar(d)) & {"X02_HASH_ETAPA", "X06_HASH_LANDING", "X03_HASH_QA", "X05_HASH_ITEM"})

    def test_R44_la_aprobacion_de_d5_sella_el_sitio_y_las_rutas(self) -> None:
        """CT2-33: ``ARCHIVOS_SELLADOS['D5']`` = assets/checkout/tracking: editar ``sitio/`` o ``rutas.json`` NO invalida la aprobación de D5 (solo ``paquete.landing_hash`` de D6, que se recalcula al regenerar)."""
        self.assertIn("05-landing/rutas.json", V.ARCHIVOS_SELLADOS["D5"])



# --------------------------------------------------------------------------------------------------------------------
# D. Landing: el lint de referencia no cubre defectos de B0-11/B4 que el plan nombra
# --------------------------------------------------------------------------------------------------------------------
class TestLintLandingRojo(Landing):
    def test_R21_evento_de_pixel_con_termino_de_salud(self) -> None:
        """CT2-17: L1-SALUD solo mira ``tracking.json``; un ``trackCustom('Ansiedad')`` en ``pixel.js`` pasa."""
        self.sub("js/pixel.js", "window.fbq('track', 'PageView'", "window.fbq('trackCustom', 'Ansiedad', {});\n  window.fbq('track', 'PageView'")
        self.assertDispara("L1-SALUD")

    def test_R22_pixel_emite_solo_eventos_de_tracking_json(self) -> None:
        """CT2-17: un evento ``Lead`` en ``pixel.js`` que no está en ``tracking.json.eventos`` pasa."""
        self.sub("js/pixel.js", "window.fbq('track', 'PageView'", "window.fbq('track', 'Lead');\n  window.fbq('track', 'PageView'")
        self.assertDispara()

    def test_R23_formulario_que_pide_condiciones(self) -> None:
        """CT2-18: ningún ``<form>``/``<input>`` salvo la casilla premarcada se examina: un formulario «¿qué condición médica tienes?» pasa."""
        self.sub("index.html", "</main>", '<form action="/comprar"><label>¿Qué condición médica tienes? <input name="condicion_medica"></label></form></main>')
        self.assertDispara()

    def test_R24_cookie_de_marketing_escrita_antes_del_consentimiento(self) -> None:
        """CT2-19: ``document.cookie = '_fbp=…'`` al cargar ``consentimiento.js`` (antes de elegir) no dispara nada."""
        self.sub("js/consentimiento.js", "'use strict';", "'use strict';\n  document.cookie = '_fbp=fb.1.1.1; Path=/';")
        self.assertDispara("L1-CONSENT-PIXEL")

    def test_R25_testimonio_sin_fuente(self) -> None:
        """CT2-20: ``<blockquote>`` con una promesa de resultado y sin fuente ni consentimiento (oferta.prueba) pasa."""
        self.sub("index.html", "</main>", "<blockquote>«Conseguí trabajo en una semana» — María</blockquote></main>")
        self.assertDispara()

    def test_R26_urgencia_falsa_sin_numero(self) -> None:
        """CT2-21: RX_CONTADORES solo ve «quedan N»/«últimos N»: «La oferta termina hoy a medianoche» pasa (``oferta.urgencia`` es null)."""
        self.sub("index.html", "<p>Pago único.", "<p>La oferta termina hoy a medianoche. Pago único.")
        self.assertDispara("L1-CONTADORES")

    def test_R27_precio_sube_manana(self) -> None:
        """CT2-21: «El precio sube mañana» (urgencia falsa) pasa."""
        self.sub("index.html", "<p>Pago único.", "<p>El precio sube mañana. Pago único.")
        self.assertDispara("L1-CONTADORES")

    def test_R28_guarda_de_consentimiento_de_pixel_js_solo_en_un_comentario(self) -> None:
        """CT2-22: el lint busca la CADENA «FabricaConsent.marketing() !== true»: un comentario basta aunque el código ya no la ejecute."""
        self.sub("js/pixel.js", "if (!window.FabricaConsent || window.FabricaConsent.marketing() !== true) { return; }   // defensa en profundidad",
                 "/* FabricaConsent.marketing() !== true */")
        self.assertDispara("L1-CONSENT-PIXEL")

    def test_R29_precio_con_euro_delante(self) -> None:
        """CT2-23: RX_IMPORTE exige «N €»: «€17,90» no se reconoce como importe."""
        self.sub("index.html", "Quiero la guía — 19,90 €", "Quiero la guía — €17,90")
        self.assertDispara("L1-PRECIO")

    def test_R30_precio_escrito_en_euros_con_letras(self) -> None:
        """CT2-23: «17,90 euros» (sin símbolo) no se reconoce: precio distinto sin detectar."""
        self.sub("index.html", "Quiero la guía — 19,90 €", "Quiero la guía — 17,90 euros")
        self.assertDispara("L1-PRECIO")

    def test_R31_enlace_javascript(self) -> None:
        """CT2-24: ``href="javascript:…"`` se descarta como «no es navegación» y no es hallazgo."""
        self.sub("index.html", '<a class="cta" href="/comprar">', '<a class="cta" href="javascript:void(0)">')
        self.assertDispara()

    def test_R32_iframe_externo(self) -> None:
        """CT2-24: el parser no recoge ``<iframe src>``: un vídeo de YouTube embebido pasa."""
        self.sub("index.html", "</main>", '<iframe src="https://www.youtube.com/embed/xyz"></iframe></main>')
        self.assertDispara("L1-ENLACE-EXTERNO")

    def test_R33_css_con_import_externo(self) -> None:
        """CT2-24: el CSS no se examina: ``@import url(https://fonts.googleapis.com/…)`` carga un tercero sin consentimiento."""
        p = self.sitio / "css" / "estilos.css"
        p.write_text("@import url(https://fonts.googleapis.com/css2?family=X);\n" + p.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertDispara("L1-ENLACE-EXTERNO")

    def test_R34_meta_refresh_a_un_dominio_externo(self) -> None:
        """CT2-24: ``<meta http-equiv="refresh" content="0;url=https://…">`` (redirección) no es hallazgo."""
        self.sub("index.html", '<meta charset="utf-8">', '<meta charset="utf-8"><meta http-equiv="refresh" content="5;url=https://evil.invalid/">')
        self.assertDispara("L1-ENLACE-EXTERNO")

    def test_R35_imagen_sin_alt_y_con_alt_vacio(self) -> None:
        """CT2-25: el plan exige ``alt`` en el ejemplo, pero no hay regla: ni ``<img>`` sin alt ni ``alt=""`` se detectan."""
        self.sub("index.html", ' alt="Escritorio con un currículum y una taza"', "")
        self.assertDispara()

    def test_R36_la_palabra_ejemplo_corriente_no_es_un_falso_positivo(self) -> None:
        """CT2-26: ``RX_EJEMPLO = /ejemplo/i`` sobre el texto: «Por ejemplo, …» en una landing real dispara L1-EJEMPLO-VISIBLE (debe ser el marcador ``[EJEMPLO]``)."""
        self.sub("index.html", "<p>Pago único.", "<p>Por ejemplo, un guion de 30 segundos. Pago único.")
        self.assertNotIn("L1-EJEMPLO-VISIBLE", self.reglas())

    def test_R37_manejador_de_evento_en_linea_con_pixel(self) -> None:
        """CT2-27: ``onclick="fbq('track','Lead')"`` carga el píxel antes del consentimiento y no se ve (solo se miran ``<script>``)."""
        self.sub("index.html", '<a class="cta" href="/comprar">', '<a class="cta" href="/comprar" onclick="fbq(\'track\',\'Lead\')">')
        self.assertDispara("L1-CONSENT-PIXEL")

    def test_R38_html_huerfano_sin_ruta_en_rutas_json(self) -> None:
        """CT2-28: una página servida (``oculta.html``) que no figura en ``rutas.json`` no es hallazgo (rutas.json deja de ser la lista cerrada)."""
        (self.sitio / "oculta.html").write_text((self.sitio / "index.html").read_text(encoding="utf-8"), encoding="utf-8")
        self.assertDispara()

    def test_R39_pagina_de_angulo_sin_data_precio_minor(self) -> None:
        """CT2-29: ``pag.body.get(...) not in (None, ...)`` acepta que falte ``data-precio-minor``; el píxel leerá ``Number(null)/100 = 0``."""
        self.sub("index.html", ' data-precio-minor="1990"', "")
        self.assertDispara("L1-PRECIO")


# --------------------------------------------------------------------------------------------------------------------
# E. JavaScript del ejemplo (comportamiento real con node)
# --------------------------------------------------------------------------------------------------------------------
class TestPixelJsRojo(Temporal):
    JS = (EJ / "05-landing" / "sitio" / "js" / "pixel.js")

    def _eventos(self, atributos: dict[str, str]) -> list:
        if not shutil.which("node"):
            self.skipTest("node no está instalado")
        arnes = r"""
const fs = require('fs'), vm = require('vm');
const [ruta, atributos] = process.argv.slice(-2);   // con `node -e` los argumentos extra son los dos últimos (argv[0] = node)
const codigo = fs.readFileSync(ruta, 'utf8'), attrs = JSON.parse(atributos), llamadas = [];
const doc = {body: {getAttribute: k => (k in attrs ? attrs[k] : null)}, createElement: () => ({}),
             getElementsByTagName: () => [{parentNode: {insertBefore() {}}}]};
const win = {FabricaConsent: {marketing: () => true, visitorId: () => 'abc'}, document: doc};
win.window = win;
const ctx = vm.createContext({window: win, document: doc, Date, Number, llamadas});
vm.runInContext(codigo.replace("window.fbq('init'", "window.fbq = function () { llamadas.push([].slice.call(arguments)); }; window.fbq('init'"), ctx);
console.log(JSON.stringify(llamadas.filter(c => c[0] === 'track')));
"""
        r = subprocess.run(["node", "-e", arnes, str(self.JS), json.dumps(atributos)], capture_output=True, text=True, timeout=30)
        self.assertEqual(0, r.returncode, r.stderr[-300:])
        return json.loads(r.stdout)

    def test_R40_pagina_legal_sin_datos_de_oferta_no_dispara_viewcontent_nulo(self) -> None:
        """CT2-30: ``consentimiento.js`` va en las 7 legales y en /gracias, que no llevan ``data-*``: ``pixel.js`` emite ViewContent con ``content_ids:[null]``, ``value:0``, ``currency:null`` (contamina la optimización y la calidad de eventos)."""
        eventos = self._eventos({})
        vc = [e for e in eventos if e[1] == "ViewContent"]
        self.assertEqual([], vc, f"ViewContent sin datos de oferta: {vc}")

    def test_R41_el_valor_del_evento_no_se_calcula_con_division_decimal_de_dinero(self) -> None:
        """CT2-31: ``Number(minor)/100`` es aritmética de coma flotante sobre dinero (y falsa para monedas sin decimales: JPY 1990 → 19.9)."""
        texto = self.JS.read_text(encoding="utf-8")
        self.assertNotIn("/ 100", texto)

    def test_R42_revocar_el_consentimiento_borra_las_cookies_de_marketing_del_dominio(self) -> None:
        """CT2-32: ``borrarCookiesDeMarketing`` borra ``_fbp``/``_fbc`` sin ``Domain=``: el píxel las crea en el dominio raíz y no se eliminan."""
        js = (EJ / "05-landing" / "sitio" / "js" / "consentimiento.js").read_text(encoding="utf-8")
        inicio = js.index("function borrarCookiesDeMarketing")
        cuerpo = js[inicio: js.index("}", js.index("forEach", inicio)) + 1]
        self.assertIn("domain", cuerpo.lower())


# --------------------------------------------------------------------------------------------------------------------
# Verdes de control: lo revisado y correcto (no deben romperse al corregir)
# --------------------------------------------------------------------------------------------------------------------
class TestVerdesDeControl(unittest.TestCase):
    @staticmethod
    def _ref(e: dict) -> dict:
        """Reimplementación independiente con ``Decimal`` (30 dígitos) de la economía unitaria."""
        D = Decimal
        P, b, Pb = D(e["precio"]), D(e.get("tasa_bump_bp", 0)) / 10000, D(e.get("precio_bump", 0))
        aov = P + b * Pb
        neto = aov / (1 + D(e.get("tasa_iva_bp", 0)) / 10000)
        pct = D(e["comision_pct_bp"] + e.get("recargos_bp", 0) + e.get("conversion_bp", 0)) / 10000
        st = e.get("stripe_tax", {"pct_bp": 0, "fijo": 0})
        mc = (neto - pct * aov - D(e["comision_fija"]) - D(st["pct_bp"]) / 10000 * aov - D(st["fijo"])
              - D(e["tasa_reembolso_bp"]) / 10000 * neto - D(e["tasa_disputa_bp"]) / 10000 * (neto + D(e["tarifa_disputa"])) - D(e["costo_variable"]))
        return {"mc": int(mc.quantize(D(1), ROUND_HALF_EVEN)), "mc_exacto": mc}

    def test_V1_vectores_con_decimal_independiente(self) -> None:
        self.assertEqual(2442, self._ref(entradas())["mc"])
        self.assertEqual(1625, self._ref(entradas(precio=1700, precio_bump=700, tasa_bump_bp=3000, recargos_bp=150))["mc"])
        it = entradas(precio=1728, precio_bump=0, tasa_bump_bp=0, tasa_iva_bp=2200, recargos_bp=150, conversion_bp=100, stripe_tax={"pct_bp": 50, "fijo": 0},
                      tasa_reembolso_bp=800, tasa_disputa_bp=60, costo_variable=0)
        self.assertEqual(1154, self._ref(it)["mc"])
        for e in (entradas(), it):
            self.assertEqual(self._ref(e)["mc"], F.economia_unitaria(e)["mc_con_signo"])

    def test_V2_redondeo_half_even_en_el_empate_exacto(self) -> None:
        # precio 1001, sin comisión, reembolso 50 %: mc = 500,5 → 500 (par); precio 1003 → 501,5 → 502 (par).
        base = dict(moneda="USD", precio=1001, precio_bump=0, tasa_bump_bp=0, tasa_reembolso_bp=5000, tasa_disputa_bp=0, comision_pct_bp=0, comision_fija=0,
                    tarifa_disputa=0, costo_variable=0, factor_cpa_objetivo_bp=6000)
        self.assertEqual(500, F.economia_unitaria(base)["mc_con_signo"])
        self.assertEqual(502, F.economia_unitaria({**base, "precio": 1003})["mc_con_signo"])

    def test_V3_flotantes_y_negativos_se_rechazan(self) -> None:
        for malo in (dict(precio=19.9), dict(precio=-1), dict(precio=0), dict(comision_pct_bp=2.9), dict(tasa_reembolso_bp=True), dict(precio="1990")):
            with self.assertRaises(ErrorValidacion, msg=str(malo)):
                F.economia_unitaria(entradas(**malo))

    def test_V4_monedas_mezcladas_se_rechazan(self) -> None:
        with self.assertRaises(ErrorValidacion):
            F.economia_unitaria(entradas(precio_bump={"monto": 900, "moneda": "EUR"}))

    def test_V5_importes_enormes_no_pierden_precision(self) -> None:
        e = entradas(precio=10 ** 30, precio_bump=0, tasa_bump_bp=0, comision_pct_bp=0, comision_fija=0, tasa_reembolso_bp=0, tasa_disputa_bp=0,
                     tarifa_disputa=0, costo_variable=0)
        self.assertEqual(10 ** 30, F.economia_unitaria(e)["mc"])

    def test_V6_las_doce_mutaciones_disparan_su_regla(self) -> None:
        for m in A.mutaciones(True):
            with self.subTest(m["id"]):
                tmp = Path(tempfile.mkdtemp(prefix="rev-ct2-mut-"))
                try:
                    c = A.copiar_ejemplo(tmp)
                    A.aplicar(m["id"], c)
                    self.assertIn(m["regla_esperada"], L.reglas(L.lint(c)))
                finally:
                    shutil.rmtree(tmp, True)

    def test_V7_el_ejemplo_real_pasa_el_lint_y_regenerar_no_cambia_nada(self) -> None:
        self.assertEqual([], L.lint(EJ))
        from tests.contratos import regenerar_ejemplo as R
        self.assertEqual([], R.regenerar(EJ, solo_comprobar=True))

    def test_V8_una_sola_formula_el_envoltorio_delega(self) -> None:
        import inspect
        from decision import presupuesto as pre
        fuente = inspect.getsource(pre.economia_por_pedido)
        self.assertIn("fact.economia_unitaria", fuente)
        for trozo in ("neto -", "neto =", "* (neto +"):
            self.assertNotIn(trozo, fuente.split('"""')[2], trozo)

    def test_V9_sin_razon_min_factible_calcular_falla_cerrado_con_parametro_faltante(self) -> None:
        """Control: sin ``razon_min_factible`` sale ParametroFaltante (5); no es hallazgo, fija el contrato."""
        from engine.errores import ParametroFaltante
        ent = entradas_ejemplo()
        with self.assertRaises(ParametroFaltante):
            F.calcular(ent, None, None)

    def test_V10_los_esquemas_nunca_se_leen_de_la_raiz_de_datos(self) -> None:
        """Raíz de datos envenenada: un ``contratos/economia.schema.json`` permisivo bajo ``FABRICA_RAIZ`` no debe aceptar ``{}``."""
        tmp = Path(tempfile.mkdtemp(prefix="rev-ct2-raiz-"))
        try:
            (tmp / "contratos").mkdir()
            (tmp / "contratos" / "economia.schema.json").write_text('{"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}')
            env = {k: v for k, v in os.environ.items() if not k.startswith("FABRICA_")}
            env["FABRICA_RAIZ"] = str(tmp)
            r = subprocess.run([sys.executable, "-c", "from scripts import validar_esquemas as V; print(len(V.errores_de_esquema('economia', {})))"],
                               cwd=RAIZ, env=env, capture_output=True, text=True, timeout=60)
            self.assertEqual(0, r.returncode, r.stderr[-300:])
            self.assertGreater(int(r.stdout.strip()), 0)
        finally:
            shutil.rmtree(tmp, True)

    def test_V11_guard_con_raiz_vacia_o_sin_empresa_falla_cerrado(self) -> None:
        tmp = Path(tempfile.mkdtemp(prefix="rev-ct2-vacia-"))
        try:
            env = {k: v for k, v in os.environ.items() if not k.startswith("FABRICA_")}
            env.update(FABRICA_RAIZ=str(tmp), FABRICA_ENTORNO="produccion")
            r = subprocess.run([sys.executable, "-m", "engine.guard", "comprobar", "--operacion", "gastar", "--oferta", "OF-202611-01", "--monto", "100",
                                "--moneda", "EUR"], cwd=RAIZ, env=env, capture_output=True, text=True, timeout=120)
            self.assertIn(r.returncode, (4, 5), r.stdout[-200:] + r.stderr[-200:])
        finally:
            shutil.rmtree(tmp, True)


if __name__ == "__main__":
    unittest.main()
