"""Pruebas de validar_d6.py y render_estatico.py (sin red; el render se omite si no hay navegador).

Ejecutar desde la raíz del repositorio:
  .venv/bin/python -m unittest discover -s .claude/skills/d6-creativos/scripts -p "test_d6.py" -v
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import struct
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[3]
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(RAIZ))

import render_estatico as rr  # noqa: E402
import validar_d6 as v  # noqa: E402
from scripts import validar_esquemas as ve  # noqa: E402

PLANTILLAS = AQUI.parent / "templates"
EJEMPLO = RAIZ / "ofertas" / "_ejemplo"


def escribir_png(ruta: Path, ancho: int, alto: int) -> None:
    def chunk(tipo: bytes, datos: bytes) -> bytes:
        c = struct.pack(">I", len(datos)) + tipo + datos
        return c + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)
    fila = b"\x00" + b"\xff" * ancho
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 0, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(fila * alto, 1)) + chunk(b"IEND", b""))


def crear_oferta(destino: Path, con_assets: bool = False) -> Path:
    shutil.copytree(EJEMPLO, destino, ignore=shutil.ignore_patterns("06-creativos"))
    d6 = destino / "06-creativos"
    (d6 / "guiones").mkdir(parents=True)
    for n in ("matriz.json", "copies.json"):
        shutil.copy(PLANTILLAS / n, d6 / n)
    matriz = json.loads((d6 / "matriz.json").read_text(encoding="utf-8"))
    for a in matriz["anuncios"]:
        (d6 / "guiones" / f"{a['ad_name']}.md").write_text(f"## Gancho\n[claim: {a['claim_id_principal']}] texto\n", encoding="utf-8")
    if con_assets:
        paq = json.loads((PLANTILLAS / "paquete.json").read_text(encoding="utf-8"))
        (d6 / "assets" / "src").mkdir(parents=True)
        for a in paq["anuncios"]:
            for s in a["assets"]:
                escribir_png(d6 / s["archivo"], 1080, 1350)
                s["sha256"] = ve.hash_archivo(d6 / s["archivo"])
            (d6 / "assets" / "src" / f"{a['ad_name']}.html").write_text(f'<body data-ad-name="{a["ad_name"]}"></body>', encoding="utf-8")
        (d6 / "paquete.json").write_text(json.dumps(paq, ensure_ascii=False, indent=2), encoding="utf-8")
        (d6 / "costos.jsonl").write_text("", encoding="utf-8")
    return d6


class Base(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "oferta"
        self.d6 = crear_oferta(self.dir)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def patrones(self, hallazgos) -> set[str]:
        return {h["patron_clave"] for h in hallazgos}

    def editar(self, nombre: str, funcion) -> None:
        ruta = self.d6 / nombre
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        funcion(datos)
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    def matriz(self):
        return v.validar_matriz(RAIZ, self.dir)


class PruebasNmax(Base):
    def test_ejemplo_da_6(self) -> None:
        r = v.calcular_nmax(RAIZ, self.dir)
        # floor(27600 / (3 × 1098)) = 8; min(8, 6, 8) = 6
        self.assertEqual((r["por_presupuesto"], r["n_anuncios_max"], r["genera"]), (8, 6, True))

    def test_presupuesto_bajo_no_genera(self) -> None:
        eco = self.dir / "03-oferta" / "economia.json"
        datos = json.loads(eco.read_text(encoding="utf-8"))
        datos["gasto_test_plan"]["monto"] = 3 * 2 * datos["cpa_obj"]["monto"]  # alcanza para 2 anuncios
        eco.write_text(json.dumps(datos), encoding="utf-8")
        r = v.calcular_nmax(RAIZ, self.dir)
        self.assertEqual(r["n_anuncios_max"], 2)
        self.assertFalse(r["genera"])
        self.assertEqual(v.main(["nmax", "--oferta-dir", str(self.dir)]), 3)

    def test_monedas_distintas_es_error_de_entrada(self) -> None:
        eco = self.dir / "03-oferta" / "economia.json"
        datos = json.loads(eco.read_text(encoding="utf-8"))
        datos["cpa_obj"]["moneda"] = "USD"
        eco.write_text(json.dumps(datos), encoding="utf-8")
        self.assertEqual(v.main(["nmax", "--oferta-dir", str(self.dir)]), 2)


class PruebasMatriz(Base):
    def test_plantilla_dorada_pasa(self) -> None:
        self.assertEqual(self.matriz(), [])

    def test_hook_fuera_del_vocabulario(self) -> None:
        self.editar("matriz.json", lambda m: m["anuncios"][0].update(hook_tipo="promesa-de-claridad"))
        self.assertIn("hook-tipo-fuera-del-vocabulario", self.patrones(self.matriz()))

    def test_par_repetido_y_hooks_iguales(self) -> None:
        def f(m):
            m["anuncios"][1]["hook_tipo"] = m["anuncios"][0]["hook_tipo"]
        self.editar("matriz.json", f)
        p = self.patrones(self.matriz())
        self.assertIn("par-angulo-hook-formato-repetido", p)
        self.assertIn("hooks-del-concepto-con-igual-tipo", p)

    def _oferta_riesgo(self, **cambios) -> None:
        oferta = self.dir / "03-oferta" / "oferta.json"
        datos = json.loads(oferta.read_text(encoding="utf-8"))
        datos["riesgo"].update(cambios)
        oferta.write_text(json.dumps(datos), encoding="utf-8")

    def test_falso_verde_es_declarado_menor_que_el_recalculado(self) -> None:
        # SC-15: el nivel declarado se compara con el RECALCULADO (scripts.nivel_riesgo), no con el de la oferta.
        def f(m):
            m["anuncios"][0]["riesgo_pieza"]["ejes_codigo"]["P"] = "P2s"  # cifra reproducible: amarillo
        self.editar("matriz.json", f)
        p = self.patrones(self.matriz())
        self.assertIn("riesgo-pieza-falso-verde", p)

    def test_pieza_menor_que_la_oferta_no_es_bloqueante(self) -> None:
        # oferta amarilla, pieza solo-producto verde y sin repetir la promesa central: coherente, sin hallazgo grave
        self._oferta_riesgo(P="amarillo", nivel="amarillo")
        h = self.matriz()
        self.assertEqual([x for x in h if x["severidad"] in ("BLOQUEANTE", "MAYOR")], [])

    def test_promesa_central_hereda_el_eje_p_de_la_oferta(self) -> None:
        self._oferta_riesgo(P="amarillo", nivel="amarillo")
        self.editar("matriz.json", lambda m: m["anuncios"][0]["riesgo_pieza"].update(repite_promesa_central=True))
        self.assertIn("riesgo-pieza-promesa-central-con-p-menor", self.patrones(self.matriz()))
        # con el eje P heredado (P2s, amarillo) y nivel amarillo ya no es falso verde
        def g(m):
            r = m["anuncios"][0]["riesgo_pieza"]
            r.update(P="amarillo", nivel="amarillo")
            r["ejes_codigo"]["P"] = "P2s"
        self.editar("matriz.json", g)
        h = self.matriz()
        self.assertEqual([x for x in h if x["severidad"] in ("BLOQUEANTE", "MAYOR")], [])

    def test_recalculado_mayor_que_la_oferta_es_mayor(self) -> None:
        def f(m):
            r = m["anuncios"][0]["riesgo_pieza"]
            r.update(P="amarillo", nivel="amarillo")
            r["ejes_codigo"]["P"] = "P2s"
        self.editar("matriz.json", f)
        h = self.matriz()
        self.assertIn("pieza-mas-riesgosa-que-la-oferta", self.patrones(h))
        self.assertTrue(all(x["severidad"] == "MAYOR" for x in h if x["patron_clave"] == "pieza-mas-riesgosa-que-la-oferta"))

    def test_riesgo_pieza_sin_declarar_la_promesa_central_es_mayor(self) -> None:
        def f(m):
            del m["anuncios"][0]["riesgo_pieza"]["repite_promesa_central"]
        self.editar("matriz.json", f)
        self.assertIn("riesgo-pieza-sin-promesa-central-declarada", self.patrones(self.matriz()))

    def test_ejes_codigo_invalidos_o_ausentes(self) -> None:
        self.editar("matriz.json", lambda m: m["anuncios"][0]["riesgo_pieza"]["ejes_codigo"].update(P="P9"))
        self.assertIn("riesgo-pieza-ejes-codigo-invalidos", self.patrones(self.matriz()))
        self.editar("matriz.json", lambda m: m["anuncios"][0]["riesgo_pieza"].pop("ejes_codigo"))
        self.assertIn("riesgo-pieza-sin-ejes-codigo", self.patrones(self.matriz()))  # MENOR: se deriva de los colores [SUPUESTO]

    def test_riesgo_coincide_con_scripts_nivel_riesgo(self) -> None:
        # paridad: la skill no tiene tabla propia; los casos de la tabla única dan el mismo nivel y subnivel
        from scripts import nivel_riesgo as nr
        for codigos, nivel, sub in (({"P": "P1", "C": "C1", "E": "E0", "N": "N1"}, "verde", None),
                                    ({"P": "P2s", "C": "C1", "E": "E0", "N": "N1"}, "amarillo", "A"),
                                    ({"P": "P2s", "C": "C2", "E": "E0", "N": "N1"}, "amarillo", "B"),
                                    ({"P": "P1", "C": "C1", "E": "E2", "N": "N1"}, "rojo", None)):
            r, error = v.recalcular_riesgo_pieza({"ejes_codigo": codigos})
            self.assertIsNone(error)
            self.assertEqual((r["nivel"], r["subnivel"]), (nivel, sub))
            self.assertEqual(r["nivel"], nr.calcular(codigos)["nivel"])

    def test_nivel_no_es_el_maximo_y_pieza_roja(self) -> None:
        def f(m):
            m["anuncios"][0]["riesgo_pieza"].update(E="rojo", nivel="verde")
        self.editar("matriz.json", f)
        p = self.patrones(self.matriz())
        self.assertIn("nivel-no-es-el-maximo-de-los-ejes", p)
        self.assertIn("pieza-roja", p)

    def test_claim_no_permitido_y_prohibido_en_texto(self) -> None:
        self.editar("matriz.json", lambda m: m["anuncios"][0]["claim_ids"].append("ingresos-extra"))
        self.editar("copies.json", lambda c: c["anuncios"][0].update(texto_principal="Conseguirás trabajo con esta guía de 19,90 €"))
        p = self.patrones(self.matriz())
        self.assertIn("claim-no-permitido", p)
        self.assertIn("claim-prohibido-en-el-texto", p)

    def test_precio_distinto_y_formato_de_otro_pais(self) -> None:
        self.editar("copies.json", lambda c: c["anuncios"][0].update(texto_principal="Guía y plantilla por 24,90 €."))
        self.assertIn("precio-distinto-de-la-landing", self.patrones(self.matriz()))
        self.editar("copies.json", lambda c: c["anuncios"][0].update(texto_principal="Guía y plantilla por $19.90."))
        self.assertIn("moneda-distinta-de-la-landing", self.patrones(self.matriz()))
        self.editar("copies.json", lambda c: c["anuncios"][0].update(texto_principal="Guía y plantilla por 19.90 €."))
        self.assertIn("formato-de-precio-de-otro-pais", self.patrones(self.matriz()))

    def test_precio_visible_inconsistente(self) -> None:
        def f(c):
            c["anuncios"][0]["texto_principal"] = "Guía con guion de 30 segundos."
            c["anuncios"][0]["texto_en_pieza"]["apoyo"] = "Guía + plantilla"
        self.editar("copies.json", f)
        self.assertIn("precio-visible-sin-precio", self.patrones(self.matriz()))

    def test_ilustrativo_no_se_marca_como_precio_distinto(self) -> None:
        self.editar("copies.json", lambda c: c["anuncios"][0].update(texto_principal="Cifra ilustrativa: la tabla suma 1.378 € en 52 semanas; guía 19,90 €."))
        self.assertNotIn("precio-distinto-de-la-landing", self.patrones(self.matriz()))

    def test_caracteres_corruptos_e_idioma(self) -> None:
        self.editar("copies.json", lambda c: c["anuncios"][0].update(texto_principal="Una pausa laboral no es un hueco: es un relato que se puede contar. Guía por 19,90 € Ã± roto."))
        self.assertIn("caracteres-corruptos", self.patrones(self.matriz()))
        self.editar("copies.json", lambda c: c["anuncios"][1].update(texto_principal="The guide is for you and it is in the template with this price of 19,90 €"))
        self.assertIn("idioma-distinto-del-locale", self.patrones(self.matriz()))

    def test_limites_de_titular_y_descripcion(self) -> None:
        self.editar("copies.json", lambda c: c["anuncios"][0].update(titular="T" * 41, descripcion="D" * 31))
        p = self.patrones(self.matriz())
        self.assertIn("titular-excede-el-limite", p)
        self.assertIn("descripcion-excede-el-limite", p)

    def test_menos_de_3_angulos_y_sobre_el_maximo(self) -> None:
        def f(m):
            for c in m["conceptos"]:
                c["angulo_id"] = "hueco-como-relato"
        self.editar("matriz.json", f)
        self.assertIn("menos-de-3-angulos", self.patrones(self.matriz()))

        def g(m):
            extra = copy.deepcopy(m["anuncios"][0])
            extra.update(ad_name="c01-hueco_img_h3_v1", hook_id="h3", hook_tipo="mito")
            m["anuncios"].append(extra)
        self.editar("matriz.json", g)
        self.assertIn("anuncios-sobre-el-maximo", self.patrones(self.matriz()))

    def test_avatar_ia_solo_en_dinero_verde(self) -> None:
        self.editar("matriz.json", lambda m: m["anuncios"][0].update(presentador="avatar_ia"))
        self.assertNotIn("avatar-ia-fuera-de-dinero-verde", self.patrones(self.matriz()))
        oferta = self.dir / "03-oferta" / "oferta.json"
        datos = json.loads(oferta.read_text(encoding="utf-8"))
        datos["macro_nicho"] = "relaciones"
        oferta.write_text(json.dumps(datos), encoding="utf-8")
        p = self.patrones(self.matriz())
        self.assertIn("avatar-ia-fuera-de-dinero-verde", p)
        self.assertIn("avatar-en-salud-o-relaciones", p)

    def test_ad_name_no_conforme_y_locale_distinto(self) -> None:
        self.editar("matriz.json", lambda m: m["anuncios"][0].update(ad_name="c01-hueco|img|h1|v1"))
        self.assertIn("ad-name-no-conforme", self.patrones(self.matriz()))
        self.editar("copies.json", lambda c: c.update(idioma="it-IT"))
        self.assertIn("idioma-distinto", self.patrones(self.matriz()))

    def test_menos_de_3_fuentes(self) -> None:
        self.editar("matriz.json", lambda m: m["conceptos"][0]["fuentes_inspiracion"].pop())
        self.assertIn("menos-de-3-fuentes", self.patrones(self.matriz()))

    def test_guion_con_claim_inexistente(self) -> None:
        nombre = json.loads((self.d6 / "matriz.json").read_text(encoding="utf-8"))["anuncios"][0]["ad_name"]
        (self.d6 / "guiones" / f"{nombre}.md").write_text("[claim: ganancias-seguras] hola\n", encoding="utf-8")
        self.assertIn("claim-no-permitido-en-guion", self.patrones(self.matriz()))


class PruebasTextosYAssets(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "oferta"
        self.d6 = crear_oferta(self.dir, con_assets=True)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_hash_de_textos_detecta_cambios(self) -> None:
        r, h = v.verificar_textos(self.dir, None)
        qa_a = self.d6.parent / "qa" / "d6-v1-previo.json"
        qa_a.parent.mkdir(parents=True, exist_ok=True)
        qa_a.write_text(json.dumps({"entradas": r["entradas"]}), encoding="utf-8")
        _, h = v.verificar_textos(self.dir, qa_a)
        self.assertEqual(h, [])
        copies = json.loads((self.d6 / "copies.json").read_text(encoding="utf-8"))
        copies["anuncios"][0]["titular"] = "Otro titular"
        (self.d6 / "copies.json").write_text(json.dumps(copies, ensure_ascii=False), encoding="utf-8")
        _, h = v.verificar_textos(self.dir, qa_a)
        self.assertIn("texto-cambiado-tras-qa-a", {x["patron_clave"] for x in h})

    def test_assets_dorados_pasan_y_el_paquete_valida_contra_el_esquema(self) -> None:
        h, codigo = v.validar_assets(RAIZ, self.dir)
        self.assertEqual((h, codigo), ([], 0))
        self.assertEqual(v.validar_paquete_esquema(self.dir), [])

    def test_hash_dimensiones_y_enhancements(self) -> None:
        paq_ruta = self.d6 / "paquete.json"
        paq = json.loads(paq_ruta.read_text(encoding="utf-8"))
        paq["anuncios"][0]["assets"][0]["sha256"] = "sha256:" + "1" * 64
        paq["anuncios"][1]["assets"][0]["ratio"] = "9:16"
        paq["politicas"]["meta_enhancements"]["mejoras_creativas"] = True
        paq_ruta.write_text(json.dumps(paq, ensure_ascii=False), encoding="utf-8")
        h, _ = v.validar_assets(RAIZ, self.dir)
        p = {x["patron_clave"] for x in h}
        self.assertTrue({"asset-hash-no-coincide", "dimensiones-no-corresponden-al-ratio", "meta-enhancements-activos"} <= p)
        self.assertIn("paquete-fuera-del-esquema", {x["patron_clave"] for x in v.validar_paquete_esquema(self.dir)})

    def test_ia_sin_job_id_ni_licencia_ni_etiqueta(self) -> None:
        paq_ruta = self.d6 / "paquete.json"
        paq = json.loads(paq_ruta.read_text(encoding="utf-8"))
        s = paq["anuncios"][0]["assets"][0]
        s.update(ia_generado=True, job_id=None, modelo=None, licencia_ref=None, c2pa_final="no", etiqueta_ia_visible=False)
        paq_ruta.write_text(json.dumps(paq, ensure_ascii=False), encoding="utf-8")
        h, _ = v.validar_assets(RAIZ, self.dir)
        p = {x["patron_clave"] for x in h}
        self.assertTrue({"asset-sin-job-id", "asset-sin-licencia", "c2pa-perdido-sin-etiqueta-visible"} <= p)

    def test_creditos_con_topes_null_sale_5_y_costos_deben_sumar(self) -> None:
        paq_ruta = self.d6 / "paquete.json"
        paq = json.loads(paq_ruta.read_text(encoding="utf-8"))
        s = paq["anuncios"][0]["assets"][0]
        s.update(ia_generado=True, job_id="J-1", modelo="m", costo_creditos=10)
        paq["anuncios"][0]["costo_creditos"] = 10
        paq["costo_total_creditos"] = 10
        paq_ruta.write_text(json.dumps(paq, ensure_ascii=False), encoding="utf-8")
        (self.d6 / "costos.jsonl").write_text('{"concepto": "generate_image x job=J-1"}\n', encoding="utf-8")
        h, codigo = v.validar_assets(RAIZ, self.dir)  # limites.yaml real: topes en null
        self.assertEqual(codigo, 5)
        self.assertIn("topes-de-creditos-null", {x["patron_clave"] for x in h})
        paq["anuncios"][0]["costo_creditos"] = 3
        paq_ruta.write_text(json.dumps(paq, ensure_ascii=False), encoding="utf-8")
        h, _ = v.validar_assets(RAIZ, self.dir)
        self.assertIn("costo-del-anuncio-no-suma", {x["patron_clave"] for x in h})


class PruebasFuentes(unittest.TestCase):
    """SC-15: @font-face con los WOFF2 de D5 y su licencia en licencias.json."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "oferta"
        self.d6 = crear_oferta(self.dir, con_assets=True)
        self.src = next((self.d6 / "assets" / "src").glob("*.html"))
        self.src.write_text('<style>@font-face{font-family:"Source Sans 3";src:url(data:font/woff2;base64,AAAA) format("woff2")}</style><body data-ad-name="x"></body>', encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def patrones(self) -> set[str]:
        h, _ = v.validar_assets(RAIZ, self.dir)
        return {x["patron_clave"] for x in h}

    def test_familia_con_licencia_pasa_y_sin_licencia_bloquea(self) -> None:
        lic = json.loads((PLANTILLAS / "licencias.json").read_text(encoding="utf-8"))
        (self.d6 / "licencias.json").write_text(json.dumps(lic), encoding="utf-8")
        self.assertNotIn("fuente-sin-licencia", self.patrones())
        (self.d6 / "licencias.json").write_text(json.dumps({"licencias": []}), encoding="utf-8")
        self.assertIn("fuente-sin-licencia", self.patrones())

    def test_licencia_sin_evidencia_es_mayor(self) -> None:
        lic = json.loads((PLANTILLAS / "licencias.json").read_text(encoding="utf-8"))
        for x in lic["licencias"]:
            if x["licencia_ref"] == "lic-source-sans-3":
                x.update(licencia=None, url_licencia=None, evidencia_ref=None)
        (self.d6 / "licencias.json").write_text(json.dumps(lic), encoding="utf-8")
        self.assertIn("fuente-licencia-sin-evidencia", self.patrones())


class PruebasRanuras(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / "oferta"
        self.d6 = crear_oferta(self.dir)
        escribir_png(self.d6 / "ranuras" / "hero.png", 1920, 1080)
        r = json.loads((PLANTILLAS / "ranuras.json").read_text(encoding="utf-8"))
        r["ranuras"][0]["sha256"] = ve.hash_archivo(self.d6 / "ranuras" / "hero.png")
        self.escribir(r)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def escribir(self, datos: dict) -> None:
        (self.d6 / "ranuras.json").write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")

    def cargar(self) -> dict:
        return json.loads((self.d6 / "ranuras.json").read_text(encoding="utf-8"))

    def patrones(self) -> set[str]:
        h, _ = v.validar_ranuras(RAIZ, self.dir)
        return {x["patron_clave"] for x in h}

    def test_ranura_dorada_pasa(self) -> None:
        h, codigo = v.validar_ranuras(RAIZ, self.dir)
        self.assertEqual((h, codigo), ([], 0))

    def test_ratio_peso_alt_y_slot_inexistente(self) -> None:
        escribir_png(self.d6 / "ranuras" / "hero.png", 1080, 1080)
        r = self.cargar()
        r["ranuras"][0]["sha256"] = ve.hash_archivo(self.d6 / "ranuras" / "hero.png")
        r["ranuras"][0]["alt"] = ""
        r["ranuras"].append(dict(r["ranuras"][0], slot_id="no-existe", alt="x"))
        self.escribir(r)
        p = self.patrones()
        self.assertTrue({"ranura-ratio-no-corresponde", "ranura-sin-alt", "ranura-inexistente-en-d5"} <= p)
        assets = self.dir / "05-landing" / "assets.json"
        datos = json.loads(assets.read_text(encoding="utf-8"))
        datos["slots"][0]["peso_max_kb"] = 1
        assets.write_text(json.dumps(datos), encoding="utf-8")
        self.assertIn("ranura-sobre-el-peso", self.patrones())

    def test_ia_sin_job_licencia_etiqueta_y_hash(self) -> None:
        r = self.cargar()
        r["ranuras"][0].update(origen="ia", ia_generado=True, job_id=None, modelo=None, licencia_ref=None, etiqueta_ia_visible=False, sha256="sha256:" + "2" * 64)
        self.escribir(r)
        p = self.patrones()
        self.assertTrue({"asset-sin-job-id", "asset-sin-licencia", "ranura-ia-sin-etiqueta-ia", "ranura-hash-no-coincide"} <= p)

    def test_ranura_de_opinion_no_la_produce_d6(self) -> None:
        assets = self.dir / "05-landing" / "assets.json"
        datos = json.loads(assets.read_text(encoding="utf-8"))
        datos["slots"][0].update(seccion="prueba", proposito="Avatar de una opinión de cliente")
        assets.write_text(json.dumps(datos), encoding="utf-8")
        self.assertIn("ranura-de-opinion-o-avatar", self.patrones())

    def test_productor_de_la_ranura(self) -> None:
        r = self.cargar()
        r["ranuras"][0]["productor"] = "dueño"  # el enum es ASCII (LT-56)
        self.escribir(r)
        self.assertIn("ranura-productor-invalido", self.patrones())
        r["ranuras"][0]["productor"] = "html_png"
        self.escribir(r)
        self.assertIn("ranura-productor-invalido", self.patrones())
        r["ranuras"][0]["productor"] = "D4"  # el producto lo hace D4, no D6
        self.escribir(r)
        self.assertIn("ranura-de-otro-productor", self.patrones())
        r["ranuras"][0]["productor"] = "D6"
        self.escribir(r)
        self.assertEqual(self.patrones(), set())

    def test_campo_etiqueta_ia_obsoleto(self) -> None:
        r = self.cargar()
        r["ranuras"][0]["etiqueta_ia"] = True
        self.escribir(r)
        self.assertIn("campo-etiqueta-ia-obsoleto", self.patrones())

    def test_creditos_con_topes_null(self) -> None:
        r = self.cargar()
        r["ranuras"][0].update(origen="ia", ia_generado=True, job_id="J-9", modelo="m", licencia_ref="lic", etiqueta_ia_visible=True, costo_creditos=5)
        self.escribir(r)
        (self.d6 / "costos.jsonl").write_text('{"concepto": "generate_image hero job=J-9"}\n', encoding="utf-8")
        h, codigo = v.validar_ranuras(RAIZ, self.dir)
        self.assertEqual(codigo, 5)
        self.assertIn("topes-de-creditos-null", {x["patron_clave"] for x in h})


class PruebasUtilidades(unittest.TestCase):
    def test_formatos_de_precio_por_locale(self) -> None:
        self.assertIn("19,90 €", v.formatos_precio(1990, "EUR", "es-ES"))
        self.assertIn("19,90 zł", v.formatos_precio(1990, "PLN", "pl-PL"))
        self.assertIn("19 zł", v.formatos_precio(1900, "PLN", "pl-PL"))
        self.assertIn("$19.90", v.formatos_precio(1990, "USD", "en-US"))

    def test_valor_numerico(self) -> None:
        self.assertEqual(v.valor_numerico("19,90 €"), 19.9)
        self.assertEqual(v.valor_numerico("$19.90"), 19.9)
        self.assertEqual(v.valor_numerico("1.378 €"), 1378.0)
        self.assertEqual(v.valor_numerico("1 378 zł"), 1378.0)

    def test_plantillas_validan(self) -> None:
        paq = json.loads((PLANTILLAS / "paquete.json").read_text(encoding="utf-8"))
        self.assertEqual([e.message for e in ve.errores_de_esquema("creativos", paq)], [])
        linea = json.loads((PLANTILLAS / "costos.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual([e.message for e in ve.errores_de_esquema("costos", linea)], [])
        for p in PLANTILLAS.glob("*.json"):
            json.loads(p.read_text(encoding="utf-8"))

    def test_skill_y_agentes(self) -> None:
        import re
        import yaml
        skill = AQUI.parent / "SKILL.md"
        texto = skill.read_text(encoding="utf-8")
        self.assertLess(len(texto.splitlines()), 500)
        fm = yaml.safe_load(re.match(r"^---\n(.*?)\n---\n", texto, re.S).group(1))
        self.assertEqual(fm["name"], "d6-creativos")
        self.assertLess(len(fm["description"]), 1024)
        self.assertTrue(fm["disable-model-invocation"])
        for ag in ("d6-maker", "d6-qa"):
            t = (RAIZ / ".claude" / "agents" / f"{ag}.md").read_text(encoding="utf-8")
            f = yaml.safe_load(re.match(r"^---\n(.*?)\n---\n", t, re.S).group(1))
            self.assertEqual(f["name"], ag)
        qa = yaml.safe_load(re.match(r"^---\n(.*?)\n---\n", (RAIZ / ".claude" / "agents" / "d6-qa.md").read_text(encoding="utf-8"), re.S).group(1))
        self.assertNotIn("Write", qa["tools"])
        self.assertNotIn("Bash", qa["tools"])

    def test_archivos_citados_existen(self) -> None:
        import re
        base = AQUI.parent
        pendientes = {"lint_locale"}  # scripts/mercados/lint_locale.py: lo construye S-B (SB-13); los demás ya existen
        faltan = []
        for md in [base / "SKILL.md", base / "rubric.md", *sorted((base / "references").glob("*.md"))]:
            for ruta in set(re.findall(r"`((?:references|templates|scripts|evals)/[A-Za-z0-9_./-]+\.(?:md|json|jsonl|html|py))`", md.read_text(encoding="utf-8"))):
                if Path(ruta).stem in pendientes or "<" in ruta:
                    continue
                if not (base / ruta).exists() and not (RAIZ / ruta).exists():
                    faltan.append(f"{md.name}: {ruta}")
        self.assertEqual(faltan, [])


class PruebasEvals(unittest.TestCase):
    def test_evals_validos(self) -> None:
        h = v.validar_evals(RAIZ)
        self.assertEqual([x for x in h], [], msg=json.dumps(list(h), ensure_ascii=False, indent=1))


def hay_navegador() -> bool:
    try:
        rr.buscar_navegador()
        return True
    except rr.ErrorRender:
        return False


@unittest.skipUnless(hay_navegador(), "sin Chrome/Chromium/Brave")
class PruebasRender(unittest.TestCase):
    COPIES = {"idioma": "pl-PL", "marca": {"nombre": "Arkusz Studio", "color_fondo": "#fdf6ec", "color_texto": "#1f1a17",
                                            "color_acento": "#b5461f", "fuente": "Helvetica Neue, Arial"},
              "anuncios": [{"ad_name": "c01-koszt_img_h1_v1", "texto_en_pieza": {
                  "gancho": "Koszt, cena minimalna i marża – ąćęłńóśźż", "apoyo": "Arkusz z przykładem krok po kroku.",
                  "rotulo": "Przykład ilustracyjny", "aviso": "Materiał informacyjny."}}]}

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _render(self, copies: dict, ratio: str, nombre: str = "x") -> tuple[int, Path]:
        ruta_c = self.dir / "copies.json"
        ruta_c.write_text(json.dumps(copies, ensure_ascii=False), encoding="utf-8")
        png = self.dir / f"{nombre}.png"
        codigo = rr.main(["--plantilla", str(PLANTILLAS / "estatico.html"), "--copies", str(ruta_c), "--ad-name", "c01-koszt_img_h1_v1",
                          "--ratio", ratio, "--html-salida", str(self.dir / f"{nombre}.html"), "--png-salida", str(png)])
        return codigo, png

    def test_renderiza_los_tres_ratios_con_diacriticos(self) -> None:
        for ratio, dims in (("4:5", (1080, 1350)), ("1:1", (1080, 1080)), ("9:16", (1080, 1920))):
            codigo, png = self._render(self.COPIES, ratio, ratio.replace(":", "x"))
            self.assertEqual(codigo, 0, ratio)
            self.assertEqual(rr.dimensiones_png(png), dims)
        html = (self.dir / "4x5.html").read_text(encoding="utf-8")
        self.assertIn("ąćęłńóśźż", html)
        self.assertIn('lang="pl-PL"', html)

    def test_texto_que_desborda_se_rechaza(self) -> None:
        c = copy.deepcopy(self.COPIES)
        c["anuncios"][0]["texto_en_pieza"]["gancho"] = "palabra " * 400
        codigo, png = self._render(c, "9:16", "largo")
        self.assertEqual(codigo, 3)
        self.assertFalse(png.exists())

    def test_contraste_insuficiente_y_color_invalido(self) -> None:
        c = copy.deepcopy(self.COPIES)
        c["marca"]["color_texto"] = "#fdf0e0"
        self.assertEqual(self._render(c, "4:5", "c1")[0], 3)
        c["marca"]["color_texto"] = "red;}</style><script>"
        self.assertEqual(self._render(c, "4:5", "c2")[0], 3)

    def test_marcador_sin_resolver_y_escape_de_html(self) -> None:
        with self.assertRaises(rr.ErrorRender):
            rr.rellenar("{{NO_EXISTE}}", {"A": "x"})
        self.assertEqual(rr.rellenar("{{MARCA}}", {"MARCA": "<script>alert(1)</script>"}), "&lt;script&gt;alert(1)&lt;/script&gt;")
        with self.assertRaises(rr.ErrorRender):  # un valor que contiene un marcador no se re-expande
            rr.rellenar("{{MARCA}}", {"MARCA": "{{OTRO}}"})

    def test_fuentes_woff2_de_d5_se_incrustan_y_fallan_cerrado(self) -> None:
        oferta = self.dir / "oferta"
        (oferta / "05-landing" / "fonts").mkdir(parents=True)
        (oferta / "05-landing" / "fonts" / "source-sans-3-400.woff2").write_bytes(b"wOF2" + b"\x00" * 64)  # firma válida, glifos no
        c = copy.deepcopy(self.COPIES)
        c["marca"]["fuentes"] = [{"familia": "Source Sans 3", "peso": 400, "archivo": "05-landing/fonts/source-sans-3-400.woff2", "licencia_ref": "lic-source-sans-3"}]
        ruta_c = self.dir / "copies.json"
        ruta_c.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
        base = ["--plantilla", str(PLANTILLAS / "estatico.html"), "--copies", str(ruta_c), "--ad-name", "c01-koszt_img_h1_v1", "--ratio", "4:5",
                "--html-salida", str(self.dir / "f.html"), "--png-salida", str(self.dir / "f.png")]
        self.assertEqual(rr.main(base + ["--oferta-dir", str(oferta)]), 0)
        html = (self.dir / "f.html").read_text(encoding="utf-8")
        self.assertIn('@font-face{font-family:"Source Sans 3";src:url(data:font/woff2;base64,', html)
        self.assertNotIn("http", html.split("</style>")[0].split("@font-face", 1)[1].split("base64,", 1)[0])
        self.assertEqual(rr.main(base), 2)  # sin --oferta-dir no se resuelve
        for cambio in ({"archivo": "../fuera.woff2"}, {"archivo": "05-landing/fonts/no-existe.woff2"}, {"licencia_ref": ""}, {"peso": 450}):
            malo = copy.deepcopy(c)
            malo["marca"]["fuentes"][0].update(cambio)
            ruta_c.write_text(json.dumps(malo, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(rr.main(base + ["--oferta-dir", str(oferta)]), 3, cambio)
        (oferta / "05-landing" / "fonts" / "source-sans-3-400.woff2").write_bytes(b"NOPE" + b"\x00" * 64)
        ruta_c.write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
        self.assertEqual(rr.main(base + ["--oferta-dir", str(oferta)]), 3)  # no es WOFF2

    def test_contraste_wcag(self) -> None:
        self.assertAlmostEqual(rr.contraste("#000000", "#ffffff"), 21.0, places=1)
        self.assertLess(rr.contraste("#777777", "#888888"), 1.5)


if __name__ == "__main__":
    unittest.main()
