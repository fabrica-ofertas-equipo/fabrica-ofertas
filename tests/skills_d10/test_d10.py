"""Pruebas de los scripts de la skill d10-poscompra (sin red, sin claves, stdlib). Desde la raíz del repositorio:

    .venv/bin/python -m unittest discover -s tests/skills_d10 -t . -p "test_*.py"

Cubren: validación de prueba_social_real.json contra lo que espera la landing, agregación de reseñas (con permiso entra, sin permiso no entra, las negativas no se omiten,
nada de incentivos ni sintéticas), correos con escape (texto y HTML, inyección de cabecera, dominios), lint de plantillas (las 12 plantillas entregadas deben salir limpias),
plan de entrega por línea, órdenes del Maker al código y los evals automatizables de la skill.
"""
from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SKILL = RAIZ / ".claude" / "skills" / "d10-poscompra"


def _cargar(nombre: str):
    spec = importlib.util.spec_from_file_location(f"_d10_{nombre}", SKILL / "scripts" / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


d10 = _cargar("d10")
evals = _cargar("probar_evals")
HOY = date(2026, 11, 22)
OFERTA = "OF-000000-00"
PERMISO = {"valoracion": True, "texto": True, "nombre": False, "version_texto": "v1", "dado_en": "2026-11-20T10:00:00Z"}


def cli(argv: list[str]) -> int:
    """Corre ``d10.main`` sin ensuciar la salida de las pruebas."""
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return d10.main(argv)


def resena(n: int, estrellas: int = 5, permiso=PERMISO, **kw):
    base = {"resena_id": f"RS-{n:012d}", "checkout_session_id": f"cs_test_{n:04d}", "compra_verificada": True, "estrellas": estrellas, "texto": "Dobre.", "locale": "pl-PL",
            "recibida_en": "2026-11-20T10:00:00Z", "autor_visible": None, "permiso": permiso, "retirada": False, "incentivo": False, "sintetico": False}
    base.update(kw)
    return base


def datos_correo() -> dict:
    return json.loads((SKILL / "templates" / "correo-datos.ejemplo.json").read_text(encoding="utf-8"))


PS_OK = {"schema_version": "0.1.0", "oferta_id": OFERTA, "generado_en": "2026-11-22T12:00:00Z",
         "ventas": {"total": 3, "fuente": "Stripe, pagos completados", "al": "2026-11-22"},
         "valoracion": {"media_decimas": 35, "n": 2, "fuente": "Reseñas de compradores verificados, con su permiso", "al": "2026-11-22"}}


class PruebaSocialReal(unittest.TestCase):
    def errores(self, doc, **kw):
        return d10.validar_prueba_social(doc, oferta_id=OFERTA, hoy=HOY, **kw)[0]

    def test_documento_valido_y_ejemplo_entregado(self):
        self.assertEqual(self.errores(PS_OK), [])
        ejemplo = json.loads((SKILL / "templates" / "prueba_social_real.ejemplo.json").read_text(encoding="utf-8"))
        self.assertEqual(self.errores(ejemplo), [])

    def test_solo_las_tres_claves_obligatorias_es_valido(self):
        self.assertEqual(self.errores({k: PS_OK[k] for k in ("schema_version", "oferta_id", "generado_en")}), [])

    def test_clave_no_admitida_se_rechaza(self):
        doc = {**PS_OK, "resenas": [{"texto": "x"}]}
        self.assertTrue(any("resenas" in e for e in self.errores(doc)))

    def test_tipos_exactos(self):
        for campo, valor in (("total", "3"), ("total", 3.0), ("total", True), ("total", -1)):
            doc = copy.deepcopy(PS_OK)
            doc["ventas"][campo] = valor
            self.assertTrue(self.errores(doc), f"{campo}={valor!r} debía rechazarse")
        for media in (9, 51, 4.5, "48", True):
            doc = copy.deepcopy(PS_OK)
            doc["valoracion"]["media_decimas"] = media
            self.assertTrue(self.errores(doc), f"media_decimas={media!r} debía rechazarse")
        doc = copy.deepcopy(PS_OK)
        doc["valoracion"]["n"] = 0
        self.assertTrue(self.errores(doc))

    def test_fechas(self):
        futura = copy.deepcopy(PS_OK)
        futura["ventas"]["al"] = "2026-12-01"
        self.assertTrue(any("futuro" in e for e in self.errores(futura)))
        falsa = copy.deepcopy(PS_OK)
        falsa["ventas"]["al"] = "2026-02-30"
        self.assertTrue(self.errores(falsa))
        posterior = copy.deepcopy(PS_OK)
        posterior["generado_en"] = "2026-11-21T00:00:00Z"
        self.assertTrue(any("posterior a generado_en" in e for e in self.errores(posterior)))

    def test_oferta_distinta_y_formato(self):
        self.assertTrue(any("distinto" in e for e in d10.validar_prueba_social(PS_OK, oferta_id="OF-202611-91", hoy=HOY)[0]))
        self.assertTrue(self.errores({**PS_OK, "oferta_id": "oferta-1"}))

    def test_fuente_de_demostracion_u_hostil(self):
        for fuente in ("DEMO", "Pagos de ejemplo", "Stripe test", "<b>Stripe</b>", "javascript:alert(1)"):
            doc = copy.deepcopy(PS_OK)
            doc["ventas"]["fuente"] = fuente
            self.assertTrue(self.errores(doc), fuente)
        corta = copy.deepcopy(PS_OK)
        corta["ventas"]["fuente"] = "ab"
        self.assertTrue(self.errores(corta))

    def test_total_cero_avisa_pero_es_valido(self):
        doc = copy.deepcopy(PS_OK)
        doc["ventas"]["total"] = 0
        errores, avisos = d10.validar_prueba_social(doc, oferta_id=OFERTA, hoy=HOY)
        self.assertEqual(errores, [])
        self.assertTrue(any("no mostrará" in a for a in avisos))

    def test_la_raiz_debe_ser_objeto(self):
        self.assertTrue(d10.validar_prueba_social([], hoy=HOY)[0])


class Resenas(unittest.TestCase):
    def evaluar(self, resenas, **kw):
        return d10.evaluar_resenas(resenas, oferta_id=OFERTA, hoy=HOY, permitir_sinteticos=kw.pop("permitir_sinteticos", True), **kw)

    def test_con_permiso_entra(self):
        inf = self.evaluar([resena(1, 5)])
        self.assertEqual(inf["valoracion"]["n"], 1)
        self.assertEqual(inf["valoracion"]["media_decimas"], 50)
        self.assertEqual(len(inf["publicables"]), 1)

    def test_sin_permiso_no_entra(self):
        for permiso in (None, {}, {"valoracion": False, "version_texto": "v1", "dado_en": "x"}, {"valoracion": "si", "version_texto": "v1", "dado_en": "x"},
                        {"valoracion": True, "dado_en": "x"}, {"valoracion": True, "version_texto": "v1"}):
            inf = self.evaluar([resena(1, 5, permiso=permiso)])
            self.assertIsNone(inf["valoracion"], permiso)
            self.assertEqual(inf["cuentan"], 0, permiso)

    def test_texto_sin_permiso_de_texto_no_se_publica(self):
        inf = self.evaluar([resena(1, 5, permiso={**PERMISO, "texto": False})])
        self.assertEqual(inf["cuentan"], 1)
        self.assertEqual(inf["publicables"], [])

    def test_las_negativas_cuentan_y_se_publican(self):
        inf = self.evaluar([resena(1, 5), resena(2, 5), resena(3, 1, texto="Nie dla mnie.")])
        self.assertEqual((inf["valoracion"]["n"], inf["valoracion"]["media_decimas"]), (3, 37))
        self.assertEqual({p["estrellas"] for p in inf["publicables"]}, {1, 5})

    def test_redondeo_mitad_hacia_arriba_en_decimas(self):
        inf = self.evaluar([resena(1, 5), resena(2, 4), resena(3, 4)])  # 4,333 -> 4,3
        self.assertEqual(inf["valoracion"]["media_decimas"], 43)
        inf = self.evaluar([resena(i, e) for i, e in enumerate([5] * 3 + [4] * 17, 1)])  # 4,15 -> 4,2
        self.assertEqual(inf["valoracion"]["media_decimas"], 42)
        inf = self.evaluar([resena(i, e) for i, e in enumerate([5] * 5 + [4] * 15, 1)])  # 4,25 -> 4,3 (el redondeo bancario daría 4,2)
        self.assertEqual(inf["valoracion"]["media_decimas"], 43)

    def test_incentivo_o_incentivo_no_declarado_excluye(self):
        inf = self.evaluar([resena(1, 5, incentivo=True), resena(2, 5, incentivo=None), resena(3, 5)])
        self.assertEqual(inf["cuentan"], 1)
        self.assertEqual({d["motivo"] for d in inf["descartadas"]}, {"incentivo_o_incentivo_no_declarado"})
        sin_campo = resena(4, 5)
        del sin_campo["incentivo"]
        self.assertEqual(self.evaluar([sin_campo])["cuentan"], 0)

    def test_sintetica_no_cuenta_sin_el_permiso_de_pruebas(self):
        inf = self.evaluar([resena(1, 5, sintetico=True)], permitir_sinteticos=False)
        self.assertEqual(inf["cuentan"], 0)
        self.assertEqual(inf["descartadas"][0]["motivo"], "sintetica_nunca_se_publica")

    def test_no_verificada_retirada_y_sesion_invalida(self):
        inf = self.evaluar([resena(1, 5, compra_verificada=False), resena(2, 5, retirada=True), resena(3, 5, checkout_session_id="pi_123"), resena(4, 6), resena(5, True)])
        self.assertEqual(inf["cuentan"], 0)
        self.assertEqual({d["motivo"] for d in inf["descartadas"]}, {"no_verificada", "retirada_por_su_autor", "sin_sesion", "estrellas_invalidas"})

    def test_una_por_sesion_vale_la_ultima(self):
        a = resena(1, 5, recibida_en="2026-11-20T10:00:00Z")
        b = {**resena(2, 2), "checkout_session_id": a["checkout_session_id"], "recibida_en": "2026-11-21T10:00:00Z"}
        inf = self.evaluar([a, b])
        self.assertEqual((inf["valoracion"]["n"], inf["valoracion"]["media_decimas"]), (1, 20))
        retirada = {**resena(3, 5), "checkout_session_id": a["checkout_session_id"], "recibida_en": "2026-11-22T10:00:00Z", "retirada": True}
        self.assertEqual(self.evaluar([a, b, retirada])["cuentan"], 0)

    def test_fecha_futura_u_otra_oferta(self):
        inf = self.evaluar([resena(1, 5, recibida_en="2026-12-01T10:00:00Z"), resena(2, 5, oferta_id="OF-202611-91")])
        self.assertEqual(inf["cuentan"], 0)

    def test_texto_de_riesgo_va_a_revision_humana_no_se_publica(self):
        textos = ["Schudłem 8 kg", "Zarobiłem 2000 zł", "napisz: ania@example.com", "dzwoń +48 600 700 800", "zobacz https://x.example", "<b>super</b>", "x" * 700,
                  "before and after fotos", "Ahorré 30 %"]
        inf = self.evaluar([resena(i, 5, texto=t) for i, t in enumerate(textos, 1)])
        self.assertEqual(inf["publicables"], [])
        self.assertEqual(len(inf["requieren_revision_humana"]), len(textos))
        self.assertEqual(inf["cuentan"], len(textos))  # la valoración no se pierde por un texto raro

    def test_el_texto_no_se_edita(self):
        inf = self.evaluar([resena(1, 5, texto="  Dobre   mapy,\t polecam.  ")])
        self.assertEqual(inf["publicables"][0]["texto"], "Dobre mapy, polecam.")
        self.assertEqual(inf["publicables"][0]["consentimiento_ref"], "permiso:RS-000000000001:v1")

    def test_nombre_solo_con_permiso_de_nombre(self):
        con = self.evaluar([resena(1, 5, autor_visible="Anna K.", permiso={**PERMISO, "nombre": True})])
        sin = self.evaluar([resena(1, 5, autor_visible="Anna K.")])
        self.assertEqual(con["publicables"][0]["autor"], "Anna K.")
        self.assertIsNone(sin["publicables"][0]["autor"])

    def test_n_min(self):
        self.assertIsNone(self.evaluar([resena(1, 5)], n_min=3)["valoracion"])
        self.assertIsNotNone(self.evaluar([resena(i, 5) for i in (1, 2, 3)], n_min=3)["valoracion"])

    def test_brecha_de_autorizacion(self):
        inf = self.evaluar([resena(1, 5), resena(2, 1, permiso=None)])
        self.assertEqual(inf["media_decimas_todas_las_verificadas"], 30)
        self.assertEqual(inf["valoracion"]["media_decimas"], 50)
        self.assertEqual(inf["brecha_de_autorizacion_decimas"], 20)

    def test_construir_genera_un_archivo_que_la_landing_acepta(self):
        doc, inf = d10.construir_prueba_social([resena(1, 4), resena(2, 5)], oferta_id=OFERTA, hoy=HOY, ventas=(2, "Stripe, pagos completados"), permitir_sinteticos=True)
        self.assertEqual(d10.validar_prueba_social(doc, oferta_id=OFERTA, hoy=HOY, resenas_informe=inf)[0], [])
        self.assertEqual(doc["valoracion"]["n"], 2)
        self.assertNotIn("resenas", doc)

    def test_valoracion_inventada_no_coincide_con_las_resenas(self):
        inf = self.evaluar([resena(1, 3)])
        doc = {"schema_version": "0.1.0", "oferta_id": OFERTA, "generado_en": "2026-11-22T12:00:00Z",
               "valoracion": {"media_decimas": 48, "n": 50, "fuente": "Reseñas verificadas", "al": "2026-11-22"}}
        self.assertTrue(any("no coincide" in e for e in d10.validar_prueba_social(doc, oferta_id=OFERTA, hoy=HOY, resenas_informe=inf)[0]))
        sin = self.evaluar([resena(1, 3, permiso=None)])
        self.assertTrue(any("ninguna reseña" in e for e in d10.validar_prueba_social(doc, oferta_id=OFERTA, hoy=HOY, resenas_informe=sin)[0]))

    def test_cli_construir_y_validar_archivos(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "r.jsonl").write_text("\n".join(json.dumps(resena(i, 5)) for i in (1, 2)) + "\n", encoding="utf-8")
            code = cli(["construir-prueba-social", "--resenas", str(t / "r.jsonl"), "--oferta-id", OFERTA, "--hoy", "2026-11-22", "--permitir-sinteticos",
                             "--salida", str(t / "ps.json"), "--informe", str(t / "inf.json"), "--json"])
            self.assertEqual(code, 0)
            self.assertEqual(cli(["validar-prueba-social", "--archivo", str(t / "ps.json"), "--oferta-id", OFERTA, "--hoy", "2026-11-22",
                                       "--resenas", str(t / "r.jsonl"), "--permitir-sinteticos", "--json"]), 0)
            self.assertEqual(cli(["construir-prueba-social", "--resenas", str(t / "r.jsonl"), "--oferta-id", OFERTA, "--hoy", "2026-11-22",
                                       "--ventas", "3", "--json"]), 3)  # ventas sin fuente
            (t / "mala.jsonl").write_text("{no es json\n", encoding="utf-8")
            self.assertEqual(cli(["construir-prueba-social", "--resenas", str(t / "mala.jsonl"), "--oferta-id", OFERTA, "--hoy", "2026-11-22", "--json"]), 3)


class Correos(unittest.TestCase):
    def render(self, nombre, **kw):
        plantilla = (SKILL / "templates" / nombre).read_text(encoding="utf-8")
        return d10.renderizar(plantilla, kw.pop("datos", datos_correo()), dominios=kw.pop("dominios", ["mapymysli-angielski.example"]), **kw)

    def test_las_doce_plantillas_entregadas_se_expanden_en_texto_y_html(self):
        archivos = sorted((SKILL / "templates").glob("correo-*.txt"))
        self.assertEqual(len(archivos), 12)
        for a in archivos:
            out = self.render(a.name, formato="ambos")
            self.assertNotIn("{{", out["texto"], a.name)
            self.assertNotIn("{{", out["asunto"], a.name)
            self.assertLessEqual(len(out["asunto"]), 90, a.name)
            self.assertTrue(out["html"].startswith("<!doctype html>"), a.name)

    def test_las_doce_plantillas_pasan_el_lint(self):
        for a in sorted((SKILL / "templates").glob("correo-*.txt")):
            bloqueos = [h for h in d10.lint_plantilla(a.read_text(encoding="utf-8")) if h["severidad"] in ("BLOQUEANTE", "MAYOR")]
            self.assertEqual(bloqueos, [], a.name)

    def test_la_entrega_lleva_ambos_enlaces_y_el_procedimiento_de_garantia_literal(self):
        out = self.render("correo-entrega.pl.txt")
        d = datos_correo()
        self.assertIn(d["garantia_texto"], out["texto"])
        for item in d["lista_enlaces"]:
            self.assertIn(item["enlace"], out["texto"])
            self.assertIn(item["nombre"], out["texto"])

    def test_las_cinco_estrellas_van_en_orden_y_sin_resaltar_ninguna(self):
        out = self.render("correo-resena.pl.txt")
        posiciones = [out["texto"].index(f"e={n}") for n in range(1, 6)]
        self.assertEqual(posiciones, sorted(posiciones))

    def test_html_escapa_valores_y_texto_fijo(self):
        datos = datos_correo()
        datos["primer_paso"] = "<script>alert(1)</script> & \"comillas\""
        datos["producto"] = "<img src=x onerror=alert(1)>"
        out = self.render("correo-entrega.es.txt", datos=datos, formato="ambos")
        self.assertNotIn("<script>", out["html"])
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt; &amp; &quot;comillas&quot;", out["html"])
        self.assertEqual(out["html"].count("<br><br>"), 0)

    def test_un_valor_con_llaves_no_se_vuelve_a_expandir(self):
        datos = datos_correo()
        datos["primer_paso"] = "{{soporte_email}} {{vendedor}}"
        out = self.render("correo-entrega.es.txt", datos=datos)
        self.assertIn("{{soporte_email}} {{vendedor}}", out["texto"])

    def test_inyeccion_de_cabecera_en_el_asunto(self):
        plantilla = "# tipo: soporte\n# locale: es\nAsunto: Hola {{marca}}\n\n{{vendedor}} {{soporte_email}} {{politica_url}}\n"
        datos = {"marca": "Slowo\r\nBcc: robo@malo.example\nX: y", "vendedor": "V", "soporte_email": "a@b.example", "politica_url": "https://b.example/p"}
        out = d10.renderizar(plantilla, datos)
        self.assertNotIn("\n", out["asunto"])
        self.assertNotIn("\r", out["asunto"])

    def test_caracteres_de_control_y_direccion_se_eliminan(self):
        datos = datos_correo()
        datos["marca"] = "Slow‮o\u0000map​a"
        out = self.render("correo-entrega.es.txt", datos=datos)
        for ch in ("‮", "\u0000", "​"):
            self.assertNotIn(ch, out["texto"])

    def test_dominio_ajeno_http_y_credenciales_se_rechazan(self):
        casos = ["https://malo.example/x", "http://mapymysli-angielski.example/x", "https://usuario:clave@mapymysli-angielski.example/x", "https://mapymysli-angielski.example/x y",
                 "javascript:alert(1)", "https://mapymysli-angielski.example.malo.example/x", "https://mapymysli-angielski.example/\"onclick=1"]
        for url in casos:
            datos = datos_correo()
            datos["politica_url"] = url
            with self.assertRaises(d10.ErrorD10, msg=url):
                self.render("correo-entrega.es.txt", datos=datos)
        datos = datos_correo()
        datos["politica_url"] = "https://www.mapymysli-angielski.example/p"  # subdominio permitido
        self.render("correo-entrega.es.txt", datos=datos)

    def test_datos_personales_fuera_de_la_lista_cerrada(self):
        for clave in ("email_comprador", "nombre", "telefono", "ip"):
            datos = datos_correo()
            datos[clave] = "x"
            with self.assertRaises(d10.ErrorD10, msg=clave):
                self.render("correo-entrega.es.txt", datos=datos)

    def test_falta_un_dato_o_la_plantilla_usa_un_campo_desconocido(self):
        datos = datos_correo()
        del datos["pedido_ref"]
        with self.assertRaises(d10.ErrorD10):
            self.render("correo-entrega.es.txt", datos=datos)
        with self.assertRaises(d10.ErrorD10):
            d10.renderizar("# tipo: soporte\nAsunto: x {{nombre_comprador}}\n\ncuerpo", {})

    def test_el_asunto_no_admite_enlaces_ni_bloques(self):
        with self.assertRaises(d10.ErrorD10):
            d10.renderizar("# tipo: soporte\nAsunto: ver {{politica_url}}\n\ncuerpo", {"politica_url": "https://b.example/p"})

    def test_bloque_de_renuncia_vacio_colapsa_y_lleno_aparece(self):
        datos = datos_correo()
        datos["bloque_renuncia"] = ""
        sin = self.render("correo-entrega.es.txt", datos=datos)["texto"]
        self.assertNotIn("\n\n\n", sin)
        self.assertNotIn("PLANTILLA", sin)
        datos["bloque_renuncia"] = "Confirmamos la renuncia (texto sellado)."
        self.assertIn("Confirmamos la renuncia", self.render("correo-entrega.es.txt", datos=datos)["texto"])

    def test_enteros_estrictos(self):
        for valor in ("7", 7.0, True, 0, 10000):
            datos = datos_correo()
            datos["vence_dias"] = valor
            with self.assertRaises(d10.ErrorD10, msg=repr(valor)):
                self.render("correo-entrega.es.txt", datos=datos)

    def test_cli_correo_y_lint(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            (t / "d.json").write_text(json.dumps(datos_correo(), ensure_ascii=False), encoding="utf-8")
            plantilla = str(SKILL / "templates" / "correo-entrega.pl.txt")
            self.assertEqual(cli(["correo", "--plantilla", plantilla, "--datos", str(t / "d.json"), "--dominios", "mapymysli-angielski.example", "--formato", "ambos", "--json"]), 0)
            self.assertEqual(cli(["correo", "--plantilla", plantilla, "--datos", str(t / "d.json"), "--dominios", "otro.example", "--json"]), 3)
            self.assertEqual(cli(["lint-plantilla", "--plantilla", plantilla, "--json"]), 0)


class LintPlantillas(unittest.TestCase):
    def codigos(self, texto, **kw):
        return {h["codigo"] for h in d10.lint_plantilla(texto, **kw)}

    ID = " {{vendedor}} {{soporte_email}} {{politica_url}}"
    RES = " {{baja_url}} {{resena_url_1}} {{resena_url_2}} {{resena_url_3}} {{resena_url_4}} {{resena_url_5}}"

    def test_formato(self):
        self.assertIn("formato", self.codigos("sin asunto"))
        self.assertIn("tipo_invalido", self.codigos("# tipo: spam\nAsunto: x\n\n" + self.ID))

    def test_incentivos_y_presion_de_nota(self):
        base = "# tipo: resena\n# locale: es\nAsunto: Tu valoración\n\n"
        for frase in ("Danos 5 estrellas", "te damos un descuento", "participa en el sorteo", "Give us five stars", "w zamian za opinię", "tylko pozytywne opinie", "te regalamos un bonus"):
            self.assertIn("incentivo", self.codigos(base + frase + self.ID + self.RES), frase)

    def test_urgencia_y_promocion(self):
        base = "# tipo: entrega\n# locale: es\nAsunto: Pedido\n\n"
        self.assertIn("urgencia", self.codigos(base + "Solo hoy" + self.ID))
        self.assertIn("promocion_en_transaccional", self.codigos(base + "Compra ahora el nuevo producto" + self.ID))

    def test_resena_debe_llevar_cinco_estrellas_y_baja(self):
        c = self.codigos("# tipo: resena\n# locale: es\nAsunto: x\n\n{{resena_url_5}}" + self.ID)
        self.assertIn("campo_requerido", c)
        self.assertIn("resena_cinco_enlaces", c)

    def test_resena_condicionada_a_que_le_haya_gustado(self):
        self.assertIn("resena_condicionada", self.codigos("# tipo: resena\n# locale: es\nAsunto: x\n\nSi te gustó, valora" + self.ID + self.RES))

    def test_asunto_no_neutro_solo_con_flag(self):
        t = "# tipo: soporte\n# locale: es\nAsunto: Tu guía {{producto}}\n\ncuerpo" + self.ID
        self.assertIn("asunto_no_neutro", self.codigos(t))
        self.assertNotIn("asunto_no_neutro", self.codigos(t, neutro=False))

    def test_identidad_del_vendedor(self):
        self.assertIn("identidad_del_vendedor", self.codigos("# tipo: soporte\n# locale: es\nAsunto: x\n\ncuerpo"))

    def test_emoji(self):
        self.assertIn("emoji", self.codigos("# tipo: soporte\n# locale: es\nAsunto: x\n\n🎉" + self.ID))


class PlanDeEntrega(unittest.TestCase):
    OFERTA = {"bump": {"id": "bump-fichas"}}

    def producto(self, **extra):
        items = [{"id": "guia", "archivo": "a.pdf", "sha256": "sha256:" + "a" * 64, "en_paquete": True},
                 {"id": "bump-fichas", "archivo": "b.zip", "sha256": "sha256:" + "b" * 64, "en_paquete": True},
                 {"id": "muestra", "archivo": "m.pdf", "sha256": "sha256:" + "c" * 64, "en_paquete": False}]
        items += extra.get("mas", [])
        return {"items": items}

    def test_con_bump_se_entregan_ambos_archivos(self):
        r = d10.plan_entrega(self.OFERTA, self.producto(), ["principal", "bump"])
        self.assertEqual([x["id"] for x in r["entregar"]], ["guia", "bump-fichas"])
        self.assertEqual(r["no_entregar"], [])

    def test_sin_bump_no_se_entrega_el_archivo_del_bump(self):
        r = d10.plan_entrega(self.OFERTA, self.producto(), ["principal"])
        self.assertEqual([x["id"] for x in r["entregar"]], ["guia"])
        self.assertEqual([x["id"] for x in r["no_entregar"]], ["bump-fichas"])

    def test_la_muestra_nunca_se_entrega(self):
        r = d10.plan_entrega(self.OFERTA, self.producto(), ["principal", "bump"])
        self.assertNotIn("muestra", [x["id"] for x in r["entregar"] + r["no_entregar"]])

    def test_campo_linea_propuesto_manda_sobre_el_id(self):
        extra = {"id": "extra-upsell", "archivo": "u.pdf", "sha256": "sha256:" + "d" * 64, "en_paquete": True, "linea": "upsell"}
        r = d10.plan_entrega(self.OFERTA, self.producto(mas=[extra]), ["principal"])
        self.assertIn("extra-upsell", [x["id"] for x in r["no_entregar"]])
        r = d10.plan_entrega(self.OFERTA, self.producto(mas=[extra]), ["principal", "upsell"])
        self.assertIn("extra-upsell", [x["id"] for x in r["entregar"]])

    def test_linea_pagada_sin_archivos_o_item_sin_hash_se_rechaza(self):
        with self.assertRaises(d10.ErrorD10):
            d10.plan_entrega(self.OFERTA, self.producto(), ["principal", "upsell"])
        malo = self.producto()
        malo["items"][0]["sha256"] = ""
        with self.assertRaises(d10.ErrorD10):
            d10.plan_entrega(self.OFERTA, malo, ["principal"])

    def test_toda_sesion_paga_el_principal_y_las_lineas_son_conocidas(self):
        with self.assertRaises(d10.ErrorD10):
            d10.plan_entrega(self.OFERTA, self.producto(), ["bump"])
        with self.assertRaises(d10.ErrorD10):
            d10.plan_entrega(self.OFERTA, self.producto(), ["principal", "regalo"])


class Ordenes(unittest.TestCase):
    OK = {"accion": "reembolsar", "checkout_session_id": "cs_test_0001", "motivo": "dentro_de_garantia", "categoria": "C5", "mensaje_ref": "MSG-1234"}

    def test_orden_valida_y_ejemplo(self):
        self.assertEqual(d10.validar_orden(self.OK), [])
        self.assertEqual(d10.validar_orden(json.loads((SKILL / "templates" / "orden.ejemplo.json").read_text(encoding="utf-8"))), [])

    def test_el_maker_no_fija_importes_destinatarios_ni_excepciones(self):
        for clave, valor in (("monto", 500), ("importe", "500"), ("amount", 5), ("moneda", "USD"), ("forzar", True), ("ignorar_tope", True), ("destinatario", "a@b.c"), ("email", "a@b.c"),
                             ("iban", "PL00"), ("token", "x"), ("override", 1)):
            self.assertTrue(d10.validar_orden({**self.OK, clave: valor}), clave)

    def test_acciones_y_motivos(self):
        self.assertTrue(d10.validar_orden({**self.OK, "accion": "transferir"}))
        self.assertTrue(d10.validar_orden({**self.OK, "motivo": "me_cae_mal"}))
        self.assertTrue(d10.validar_orden({**self.OK, "checkout_session_id": "pi_123"}))
        self.assertTrue(d10.validar_orden({**self.OK, "mensaje_ref": None}))
        self.assertTrue(d10.validar_orden({k: v for k, v in self.OK.items() if k != "mensaje_ref"}))

    def test_escalar_y_descartar_exigen_su_categoria(self):
        self.assertEqual(d10.validar_orden({"accion": "escalar_humano", "categoria": "C7", "mensaje_ref": "MSG-1234"}), [])
        self.assertTrue(d10.validar_orden({"accion": "escalar_humano", "categoria": "C1", "mensaje_ref": "MSG-1234"}))
        self.assertEqual(d10.validar_orden({"accion": "descartar", "categoria": "C10", "mensaje_ref": "MSG-1234"}), [])
        self.assertTrue(d10.validar_orden({"accion": "descartar", "categoria": "C3", "mensaje_ref": "MSG-1234"}))

    def test_la_nota_no_lleva_marcado(self):
        self.assertTrue(d10.validar_orden({**self.OK, "nota": "<script>"}))
        self.assertTrue(d10.validar_orden({**self.OK, "nota": "x" * 201}))
        self.assertTrue(d10.validar_orden("reembolsa"))


class Coherencia(unittest.TestCase):
    def test_las_respuestas_tipo_solo_usan_campos_de_la_lista_cerrada(self):
        texto = (SKILL / "templates" / "respuestas-soporte.md").read_text(encoding="utf-8")
        usados = set(d10.RX_PLACEHOLDER.findall(texto))
        self.assertTrue(usados)
        self.assertEqual(sorted(usados - set(d10.CAMPOS)), [])
        for macro in range(1, 13):
            self.assertIn(f"## M{macro:02d} ", texto)

    def test_el_informe_y_los_demas_archivos_de_apoyo_existen_y_los_json_parsean(self):
        for rel in ("templates/informe-de-poscompra.md", "PEDIDOS.md", "CHANGELOG.md", "rubric.md", "SKILL.md", "evals/README.md"):
            self.assertTrue((SKILL / rel).is_file(), rel)
        for ruta in list((SKILL / "templates").glob("*.json")) + list((SKILL / "evals").rglob("*.json")):
            json.loads(ruta.read_text(encoding="utf-8"))
        for ruta in (SKILL / "templates").glob("*.jsonl"):
            self.assertTrue(d10.cargar_jsonl(ruta))
        referencias = {p.name for p in (SKILL / "references").glob("*.md")}
        self.assertEqual(referencias, {"entrega-y-correo.md", "oferta-tras-el-pago.md", "soporte-y-bandeja.md", "resenas-reales.md", "disputas-y-vigia.md",
                                       "impulstienda-pendiente.md", "conflictos-con-la-spec-vieja.md", "pedidos.md"})

    def test_las_resenas_de_ejemplo_estan_marcadas_como_sinteticas(self):
        filas = d10.cargar_jsonl(SKILL / "templates" / "resenas.ejemplo.jsonl")
        self.assertTrue(all(f["sintetico"] is True for f in filas))
        inf = d10.evaluar_resenas(filas, oferta_id=OFERTA, hoy=HOY)  # sin el permiso de pruebas, ninguna cuenta
        self.assertEqual((inf["cuentan"], inf["publicables"]), (0, []))

    def test_los_agentes_existen_y_el_qa_es_solo_lectura(self):
        agentes = RAIZ / ".claude" / "agents"
        maker = (agentes / "d10-maker.md").read_text(encoding="utf-8")
        qa = (agentes / "d10-qa.md").read_text(encoding="utf-8")
        self.assertIn("tools: Read, Grep, Glob\n", qa)
        self.assertIn("disallowedTools: Agent, Bash, Write, Edit", qa)
        self.assertIn("mcp__*", maker.split("---")[1])
        self.assertNotIn("WebFetch\ntools", maker)
        self.assertIn("skills: [d10-poscompra]", maker)
        self.assertIn("skills: [d10-poscompra]", qa)


class Evals(unittest.TestCase):
    def test_todos_los_automatizables_pasan(self):
        res = evals.ejecutar_todos()
        fallidos = [r for r in res["resultados"] if not r["ok"]]
        self.assertEqual(fallidos, [], fallidos)
        self.assertGreaterEqual(len(res["resultados"]), 14)
        self.assertEqual([c["id"] for c in res["para_qa_l3"]], ["S12", "S13", "S14", "S15"])

    def test_los_tres_casos_pedidos_existen(self):
        ids = {c["id"]: c for c in evals.cargar_casos()}
        self.assertIn("D01", ids)  # compra con bump
        self.assertIn("D02", ids)  # reembolso dentro de plazo
        self.assertIn("D03", ids)  # reseña con permiso
        self.assertIn("S01", ids)  # reseña sin permiso

    def test_un_eval_roto_se_ve_como_fallo(self):
        caso = copy.deepcopy(next(c for c in evals.cargar_casos() if c["id"] == "S03"))
        caso["esperado"]["valoracion"] = {"n": 2, "media_decimas": 50}  # lo que daría un productor que filtra por sentimiento
        self.assertTrue(evals.COMPROBACIONES["construir"](caso))

    def test_sin_el_filtro_de_sentimiento_hay_una_resena_publicable_de_una_estrella(self):
        caso = next(c for c in evals.cargar_casos() if c["id"] == "S03")
        self.assertIn("RS-000000000033", caso["esperado"]["publicables_ids"])


if __name__ == "__main__":
    unittest.main()
