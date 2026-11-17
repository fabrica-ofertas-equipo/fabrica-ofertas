"""Arranque de pago (docs/_historial/decision-arranque-de-pago.md): ``/comprar`` estática con UN formulario hacia ``/api/sesion``.

* ``landing.generar`` emite el formulario en el locale de la oferta, con la casilla de renuncia solo cuando ``checkout.compra.renuncia.requerido``
  (o, sin él, el criterio provisional por locale) la exige, el bump solo con ``bump_modo = oferta_previa`` y nunca nada premarcado.
* ``landing.validar`` admite EXACTAMENTE ese formulario (``L1-FORMULARIO``) y la CSP con ``form-action 'self' https://checkout.stripe.com`` (``L1-CSP``).
* Mutaciones del formulario (numeración de S-A): MF-01 action ajena · MF-02 campo de texto/email/tel/password/number, textarea o select · MF-03
  ``method=get`` · MF-04 casilla de renuncia ausente en UE/UK · MF-05 ``formaction``/``target`` · MF-06 formulario fuera de ``/comprar`` · MC-04p casilla
  premarcada (la MC-04 del oráculo de CT). Deben fallar el 100 %; las 8 de siempre se prueban en ``test_validar.py``.
* Cookies ``fab_vid`` y ``fab_attr`` de ``consentimiento.js``: solo tras el consentimiento de marketing (arnés de Node con DOM simulado).

Sin red: ``socket.socket`` se bloquea en ``setUp``. Comando: ``.venv/bin/python -m unittest tests.landing.test_formulario_pago``
"""
from __future__ import annotations

import json
import re
import shutil
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from engine.errores import ErrorValidacion
from landing import comun as lcomun
from landing import generar as G
from landing import plantillas as P
from landing import validar as Val

RAIZ = Path(__file__).resolve().parents[2]
FIX = RAIZ / "tests" / "fixtures" / "landing"
OFERTAS = {"es": ("oferta_es_dinero", "OF-202611-01"), "pl": ("oferta_pl_relaciones", "OF-202611-02")}
def urllib_decode(texto: str) -> str:
    from urllib.parse import unquote
    return unquote(texto)


SITEKEY = "0x4AAAAAAAfixtureSITEKEY"
# CSP CANÓNICA de S-A (LT-38), literal: la comparación del validador es por directiva, pero lo que se genera es exactamente esto.
CSP_CANONICA = ("default-src 'self'; script-src 'self' https://connect.facebook.net; connect-src 'self' https://www.facebook.com https://connect.facebook.net; "
                "img-src 'self' data: https://www.facebook.com; frame-src https://www.facebook.com https://connect.facebook.net; style-src 'self'; font-src 'self'; "
                "object-src 'none'; base-uri 'self'; frame-ancestors 'none'; "
                "form-action 'self' https://checkout.stripe.com")


def _sin_red(*_a, **_k):  # pragma: no cover
    raise AssertionError("las pruebas de landing no abren sockets")


class Base(unittest.TestCase):
    clave = "es"

    def setUp(self) -> None:
        patcher = mock.patch.object(socket, "socket", _sin_red)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.tmp = Path(tempfile.mkdtemp(prefix="landing-pago-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.d = self.preparar(self.tmp, self.clave)
        self.land, self.sitio = self.d / "05-landing", self.d / "05-landing" / "sitio"

    @staticmethod
    def preparar(raiz: Path, clave: str) -> Path:
        carpeta, oid = OFERTAS[clave]
        d = raiz / "ofertas" / oid
        shutil.copytree(FIX / carpeta, d)
        shutil.copytree(FIX / "empresa", raiz / "empresa", dirs_exist_ok=True)
        return d

    def editar(self, rel: str, f) -> None:
        ruta = self.d / rel
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        f(datos)
        ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")

    def generar(self) -> list[str]:
        return G.generar_sitio_con_avisos(self.d)[1]

    def leer(self, rel: str) -> str:
        return (self.sitio / rel).read_text(encoding="utf-8")

    def escribir(self, rel: str, texto: str) -> None:
        (self.sitio / rel).write_text(texto, encoding="utf-8")

    def hallazgos(self, d: Path | None = None) -> list[tuple[str, str, str]]:
        return [(h.regla, h.archivo, h.detalle) for h in Val.validar_sitio(d or self.d)]

    def reglas(self) -> set[str]:
        return {r for r, _, _ in self.hallazgos()}

    def pagina(self, rel: str = "comprar.html") -> Val._Pagina:
        p = Val._Pagina()
        p.feed(self.leer(rel))
        return p


class PruebaFormularioGenerado(Base):
    def test_el_formulario_es_exactamente_el_permitido(self) -> None:
        for clave in OFERTAS:
            with self.subTest(clave), tempfile.TemporaryDirectory() as t:
                d = self.preparar(Path(t), clave)
                G.generar_sitio(d)
                p = Val._Pagina()
                p.feed((d / "05-landing" / "sitio" / "comprar.html").read_text(encoding="utf-8"))
                oferta = json.loads((d / "03-oferta" / "oferta.json").read_text(encoding="utf-8"))
                self.assertEqual(1, len(p.formas))
                self.assertEqual({"class": "comprar__form", "method": "post", "action": "/api/sesion"}, p.formas[0])
                campos = [(t_, a.get("type"), a.get("name")) for t_, a, f in p.controles if t_ == "input"]
                self.assertEqual([("input", "hidden", "oferta_id"), ("input", "hidden", "locale"), ("input", "checkbox", "renuncia_desistimiento")], campos)
                ocultos = {a["name"]: a["value"] for t_, a, f in p.controles if a.get("type") == "hidden"}
                self.assertEqual({"oferta_id": oferta["oferta_id"], "locale": oferta["locale"]}, ocultos)
                self.assertEqual(1, sum(1 for t_, a, f in p.controles if t_ == "button" and a.get("type") == "submit"))
                self.assertEqual(0, p.casillas_marcadas)
                self.assertEqual([], [x for x in p.peligrosos])
                self.assertEqual([], self.hallazgos(d))

    def test_no_lleva_visitor_ni_parametros_en_el_html(self) -> None:
        self.generar()
        html = self.leer("comprar.html")
        for prohibido in ("visitor_id", "fab_vid", "fab_attr", "utm_", 'name="fbp"', 'name="fbc"', 'name="cid"', 'name="asid"', 'name="adid"', 'name="email"', 'type="text"',
                          "<textarea", "<select", "formaction", "target="):
            self.assertNotIn(prohibido, html, prohibido)

    def test_textos_en_el_locale_y_desde_el_copy(self) -> None:
        for clave in OFERTAS:
            with self.subTest(clave), tempfile.TemporaryDirectory() as t:
                d = self.preparar(Path(t), clave)
                G.generar_sitio(d)
                copy = json.loads((d / "05-landing" / "copy.json").read_text(encoding="utf-8"))
                html = (d / "05-landing" / "sitio" / "comprar.html").read_text(encoding="utf-8")
                self.assertIn(copy["secciones"]["comprar"]["titulo"], html)
                self.assertIn(copy["secciones"]["comprar"]["boton"], html)
                self.assertIn('<html lang="' + ("es-ES" if clave == "es" else "pl-PL") + '">', html)
                self.assertIn("Sprawdź przed zapłatą" if clave == "pl" else "Consulta antes de pagar", html)

    def test_renuncia_desde_el_contrato_lleva_la_version_del_texto(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            d = self.preparar(Path(t), "pl")                       # su checkout trae compra.renuncia{requerido, texto_version} y landing_version
            av = G.generar_sitio_con_avisos(d)[1]
            self.assertIn('data-texto-version="v1"', (d / "05-landing" / "sitio" / "comprar.html").read_text(encoding="utf-8"))
            self.assertFalse(any("renuncia.requerido ausente" in a for a in av))

    def test_sin_el_campo_del_contrato_cae_al_locale_con_aviso_explicito(self) -> None:
        av = self.generar()                                          # es: sin checkout.compra
        self.assertTrue(any("compra.renuncia.requerido ausente" in a and "criterio provisional" in a for a in av))
        self.assertIn('name="renuncia_desistimiento"', self.leer("comprar.html"))
        self.assertNotIn("data-texto-version", self.leer("comprar.html"))
        self.assertEqual([], self.hallazgos())


    def test_los_nombres_planos_anteriores_ya_no_se_leen(self) -> None:
        self.editar("05-landing/checkout.json", lambda c: c.update(compra={"renuncia_requerida": False, "renuncia_texto_version": "v9"}))
        av = self.generar()
        self.assertTrue(any("compra.renuncia.requerido ausente" in a for a in av))              # cae al locale (es-ES: UE) con aviso
        html = self.leer("comprar.html")
        self.assertIn('name="renuncia_desistimiento"', html)
        self.assertNotIn("data-texto-version", html)
        self.assertEqual([], self.hallazgos())

    def test_renuncia_con_requerido_pero_sin_texto_version_no_lleva_el_atributo(self) -> None:
        self.editar("05-landing/checkout.json", lambda c: c.update(compra={"renuncia": {"requerido": True}}))
        av = self.generar()
        self.assertFalse(any("renuncia.requerido ausente" in a for a in av))
        self.assertNotIn("data-texto-version", self.leer("comprar.html"))
        self.assertEqual([], self.hallazgos())

    def test_landing_version_sale_en_el_informe_de_simular_y_de_generar(self) -> None:
        import io
        from contextlib import redirect_stdout
        for bandera, clave in (("--simular", "pl"), ("--json", "pl")):
            with tempfile.TemporaryDirectory() as t:
                d = self.preparar(Path(t), clave)
                buf = io.StringIO()
                args = ["--oferta", "OF-202611-02", "--raiz", t, "--json"] + (["--simular"] if bandera == "--simular" else [])
                with redirect_stdout(buf):
                    self.assertEqual(0, G.main(args))
                self.assertEqual("v1", json.loads(buf.getvalue())["datos"]["landing_version"])
        buf = io.StringIO()                                                                    # es: sin compra.landing_version -> null
        with redirect_stdout(buf):
            G.main(["--oferta", "OF-202611-01", "--raiz", str(self.tmp), "--simular", "--json"])
        self.assertIsNone(json.loads(buf.getvalue())["datos"]["landing_version"])

    def test_el_aviso_aparece_en_la_simulacion(self) -> None:
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(0, G.main(["--oferta", "OF-202611-01", "--raiz", str(self.tmp), "--simular", "--json"]))
        salida = json.loads(buf.getvalue())
        self.assertTrue(any("renuncia.requerido ausente" in a for a in salida["avisos"]))
        self.assertTrue({"sitio/comprar.html", "sitio/_headers"} <= set(salida["datos"]["archivos"]))

    def test_el_contrato_manda_sobre_el_locale_en_los_dos_sentidos(self) -> None:
        # locale NO UE (es-AR) pero el contrato exige la casilla -> se muestra
        def ar(o):
            o.update(locale="es-AR", paises_segmentacion=["AR"])
        self.editar("03-oferta/oferta.json", ar)
        self.editar("05-landing/copy.json", lambda c: c.update(locale="es-AR"))
        self.editar("05-landing/checkout.json", lambda c: c.update(compra={"renuncia": {"requerido": True, "texto_version": "v3"}}))
        av = self.generar()
        self.assertIn('name="renuncia_desistimiento"', self.leer("comprar.html"))
        self.assertIn('data-texto-version="v3"', self.leer("comprar.html"))
        self.assertFalse(any("renuncia.requerido ausente" in a for a in av))
        self.assertEqual([], self.hallazgos())
        # locale UE (es-ES) pero el contrato dice que no se exige -> no se muestra
        self.editar("03-oferta/oferta.json", lambda o: o.update(locale="es-ES", paises_segmentacion=["ES"]))
        self.editar("05-landing/copy.json", lambda c: c.update(locale="es-ES"))
        self.editar("05-landing/checkout.json", lambda c: c.update(compra={"renuncia": {"requerido": False}}))
        self.generar()
        self.assertNotIn("renuncia_desistimiento", self.leer("comprar.html"))
        self.assertEqual([], self.hallazgos())

    def test_locale_fuera_de_ue_uk_sin_contrato_no_lleva_la_casilla(self) -> None:
        self.editar("03-oferta/oferta.json", lambda o: o.update(locale="es-AR", paises_segmentacion=["AR"]))
        self.editar("05-landing/copy.json", lambda c: c.update(locale="es-AR"))
        av = self.generar()
        self.assertNotIn("renuncia_desistimiento", self.leer("comprar.html"))
        self.assertTrue(any("no se muestra" in a and "renuncia" in a for a in av))
        self.assertEqual([], self.hallazgos())

    def test_gb_y_los_27_cuentan_como_ue_uk(self) -> None:
        for region in ("GB", "DE", "FR", "IT", "PL", "ES", "IE", "SE"):
            self.assertTrue(lcomun.renuncia({"locale": f"xx-{region}"}, {})[0], region)
        for region in ("AR", "US", "CA", "MX", "CH", "NO"):
            self.assertFalse(lcomun.renuncia({"locale": f"xx-{region}"}, {})[0], region)
        self.assertTrue(lcomun.renuncia({"locale": "es"}, {})[0])                         # sin región ni países: ante la duda, se exige

    def test_exigida_sin_texto_en_el_copy_falla_cerrado(self) -> None:
        self.editar("05-landing/copy.json", lambda c: c["secciones"]["comprar"].update(casillas=[x for x in c["secciones"]["comprar"]["casillas"] if x["id"] != "renuncia-entrega-inmediata"]))
        with self.assertRaises(ErrorValidacion) as cm:
            self.generar()
        self.assertIn("renuncia", cm.exception.mensaje)

    def test_bump_solo_con_oferta_previa_y_nunca_premarcado(self) -> None:
        self.generar()
        self.assertNotIn('name="bump"', self.leer("comprar.html"))                           # casilla_en_checkout: el bump va en Stripe
        self.editar("05-landing/checkout.json", lambda c: c["bump"].update(modo="oferta_previa"))
        self.generar()
        html = self.leer("comprar.html")
        self.assertIn('<input type="checkbox" id="bump" name="bump">', html)
        self.assertNotIn("checked", html)
        self.assertEqual([], self.hallazgos())
        self.editar("05-landing/checkout.json", lambda c: c.update(compra={"bump_modo": "casilla_en_checkout"}))   # compra.bump_modo manda
        self.generar()
        self.assertNotIn('name="bump"', self.leer("comprar.html"))
        self.assertEqual([], self.hallazgos())

    def test_oferta_previa_sin_texto_de_bump_falla_cerrado(self) -> None:
        self.editar("05-landing/checkout.json", lambda c: c["bump"].update(modo="oferta_previa"))
        self.editar("05-landing/copy.json", lambda c: c["secciones"]["S09"].update(bump=None))
        with self.assertRaises(ErrorValidacion):
            self.generar()


class PruebaRutas(Base):
    def test_sin_rutas_json_el_sitio_diseñado_declara_comprar_estatica_y_sesion_dinamica(self) -> None:
        (self.land / "rutas.json").unlink()
        self.generar()
        rutas = json.loads((self.land / "rutas.json").read_text(encoding="utf-8"))
        self.assertEqual("estatica:comprar", rutas["/comprar"])
        self.assertEqual("dinamica:crear-sesion", rutas["/api/sesion"])
        self.assertEqual([], self.hallazgos())

    def test_el_sitio_minimo_conserva_el_modo_anterior(self) -> None:
        (self.land / "rutas.json").unlink()
        (self.land / "copy.json").unlink()
        self.generar()
        rutas = json.loads((self.land / "rutas.json").read_text(encoding="utf-8"))
        self.assertEqual("dinamica:crear-sesion", rutas["/comprar"])
        self.assertNotIn("/api/sesion", rutas)

    def test_rutas_existentes_no_se_tocan_y_se_avisa_si_comprar_es_dinamica(self) -> None:
        def legado(r):
            r["/comprar"] = "dinamica:crear-sesion"
            r.pop("/api/sesion")
        self.editar("05-landing/rutas.json", legado)
        antes = (self.land / "rutas.json").read_bytes()
        av = self.generar()
        self.assertEqual(antes, (self.land / "rutas.json").read_bytes())
        self.assertFalse((self.sitio / "comprar.html").exists())
        self.assertTrue(any("estatica:comprar" in a for a in av))

    def test_comprar_sin_api_sesion_en_rutas_se_avisa_y_validar_lo_detecta(self) -> None:
        self.editar("05-landing/rutas.json", lambda r: r.pop("/api/sesion"))
        av = self.generar()
        self.assertTrue(any("/api/sesion" in a for a in av))
        self.assertIn("L1-FORMULARIO", self.reglas())


# ----------------------------------------------------------------------------------------------
# Mutaciones del formulario
# ----------------------------------------------------------------------------------------------
def _sub(patron: str, reemplazo: str):
    return lambda t: re.subn(patron, reemplazo, t, count=1, flags=re.S)


def _antes_del_boton(texto: str):
    return _sub(r'(<button type="submit")', texto + r"\1")


class PruebaMutacionesDelFormulario(Base):
    """Cada variante debe disparar ``L1-FORMULARIO`` (100 %), sobre las dos ofertas."""

    MUTACIONES: dict[str, list[tuple[str, str, object]]] = {
        "MF-01": [  # action distinta de /api/sesion o externa
            ("action externa", "comprar.html", _sub(r'action="/api/sesion"', 'action="https://pagos.terceros.invalid/api/sesion"')),
            ("action otra ruta", "comprar.html", _sub(r'action="/api/sesion"', 'action="/api/otra"')),
            ("action con consulta", "comprar.html", _sub(r'action="/api/sesion"', 'action="/api/sesion?x=1"')),
            ("action con barra final", "comprar.html", _sub(r'action="/api/sesion"', 'action="/api/sesion/"')),
            ("action vacía", "comprar.html", _sub(r'action="/api/sesion"', 'action=""')),
            ("action hacia Stripe", "comprar.html", _sub(r'action="/api/sesion"', 'action="https://checkout.stripe.com/c/pay"')),
            ("sin action", "comprar.html", _sub(r' action="/api/sesion"', "")),
            ("enctype multipart", "comprar.html", _sub(r'method="post"', 'method="post" enctype="multipart/form-data"')),
        ],
        "MF-02": [  # campos de texto/email/tel/password/number, textarea, select
            ("text", "comprar.html", _antes_del_boton('<input type="text" name="nombre">')),
            ("email", "comprar.html", _antes_del_boton('<input type="email" name="email">')),
            ("tel", "comprar.html", _antes_del_boton('<input type="tel" name="telefono">')),
            ("password", "comprar.html", _antes_del_boton('<input type="password" name="clave">')),
            ("number", "comprar.html", _antes_del_boton('<input type="number" name="edad">')),
            ("sin type (text)", "comprar.html", _antes_del_boton('<input name="nota">')),
            ("textarea", "comprar.html", _antes_del_boton('<textarea name="nota"></textarea>')),
            ("select", "comprar.html", _antes_del_boton('<select name="pais"><option>ES</option></select>')),
            ("oculto visitor_id", "comprar.html", _antes_del_boton('<input type="hidden" name="visitor_id" value="abcdefabcdefabcd">')),
            ("oculto con otro valor", "comprar.html", _sub(r'(name="oferta_id" value=")[^"]+', r"\1OF-209912-99")),
            ("oculto locale distinto", "comprar.html", _sub(r'(name="locale" value=")[^"]+', r"\1xx-XX")),
            ("campo en una página de contenido", "index.html", _sub(r"(<footer)", '<p><input type="email" name="email"></p>\\1')),
        ],
        "MF-03": [  # method=get
            ("method get", "comprar.html", _sub(r'method="post"', 'method="get"')),
            ("method GET en mayúsculas", "comprar.html", _sub(r'method="post"', 'method="GET"')),
            ("sin method", "comprar.html", _sub(r' method="post"', "")),
        ],
        "MF-04": [  # casilla de renuncia ausente (la compra la exige)
            ("sin la casilla", "comprar.html", _sub(r'<label class="casillas__fila" for="renuncia_desistimiento">.*?</label>', "")),
            ("sin required", "comprar.html", _sub(r' required>', ">")),
            ("renombrada", "comprar.html", _sub(r'name="renuncia_desistimiento"', 'name="renuncia"')),
        ],
        "MF-05": [  # formaction / target en el form o en el botón
            ("target en el form", "comprar.html", _sub(r'method="post"', 'method="post" target="_blank"')),
            ("formaction en el botón", "comprar.html", _sub(r'<button type="submit"', '<button type="submit" formaction="https://x.invalid/p"')),
            ("formtarget en el botón", "comprar.html", _sub(r'<button type="submit"', '<button type="submit" formtarget="_blank"')),
            ("formmethod en el botón", "comprar.html", _sub(r'<button type="submit"', '<button type="submit" formmethod="get"')),
            ("formenctype en el botón", "comprar.html", _sub(r'<button type="submit"', '<button type="submit" formenctype="multipart/form-data"')),
            ("target en un enlace", "index.html", _sub(r'(<a class="boton boton--mini")', '\\1 target="_blank"')),
        ],
        "MF-06": [  # formulario fuera de /comprar
            ("form en la portada", "index.html", _sub(r"(<footer)", '<form method="post" action="/api/sesion"><button type="submit">Pagar</button></form>\\1')),
            ("form con hidden en /gracias", "gracias.html", _sub(r"(<footer)", '<form method="post" action="/api/sesion"><input type="hidden" name="oferta_id" value="x"><button type="submit">Pagar</button></form>\\1')),
            ("form en una legal", "legal/privacidad.html", _sub(r"(<footer)", '<form method="post" action="/api/sesion"><button type="submit">Pagar</button></form>\\1')),
            ("segundo form en /comprar", "comprar.html", _sub(r"(</section>)", '<form method="post" action="/api/sesion"><button type="submit">Otro</button></form>\\1')),
            ("form en la portada con action ajena", "index.html", _sub(r"(<footer)", '<form action="https://x.invalid/"><button>Ir</button></form>\\1')),
        ],
        "MC-04p": [  # casilla premarcada (MC-04 del oráculo de CT, prueba propia)
            ("renuncia premarcada", "comprar.html", _sub(r'name="renuncia_desistimiento"', 'name="renuncia_desistimiento" checked')),
        ],
    }
    ESPERADA = {"MC-04p": {"L1-CASILLA-PREMARCADA"}}

    def _aplicar(self, d: Path, rel: str, f) -> None:
        ruta = d / "05-landing" / "sitio" / rel
        nuevo, n = f(ruta.read_text(encoding="utf-8"))
        self.assertEqual(1, n, f"la mutación no encontró su ancla en {rel}")
        ruta.write_text(nuevo, encoding="utf-8")

    def test_cada_mutacion_falla_en_las_dos_ofertas(self) -> None:
        total = fallan = 0
        for clave in OFERTAS:
            for mid, variantes in self.MUTACIONES.items():
                for nombre, rel, f in variantes:
                    with self.subTest(f"{clave} {mid} {nombre}"), tempfile.TemporaryDirectory() as t:
                        d = self.preparar(Path(t), clave)
                        G.generar_sitio(d)
                        self.assertEqual([], [(h.regla, h.detalle) for h in Val.validar_sitio(d)], "la base debe pasar limpia")
                        if rel == "index.html" and nombre == "target en un enlace" and clave == "pl":
                            pass
                        self._aplicar(d, rel, f)
                        reglas = {h.regla for h in Val.validar_sitio(d)}
                        total += 1
                        esperada = self.ESPERADA.get(mid, set()) | {"L1-FORMULARIO"}
                        self.assertTrue(esperada <= reglas, (mid, nombre, reglas))
                        fallan += 1
        self.assertEqual(total, fallan)
        self.assertGreaterEqual(total, 2 * 37)

    def test_mf04_con_el_contrato_usa_renuncia_requerido_y_no_el_locale(self) -> None:
        # contrato: compra.renuncia.requerido = true en un locale NO UE -> quitar la casilla falla; contrato false en UE -> ponerla falla
        self.editar("03-oferta/oferta.json", lambda o: o.update(locale="es-AR", paises_segmentacion=["AR"]))
        self.editar("05-landing/copy.json", lambda c: c.update(locale="es-AR"))
        self.editar("05-landing/checkout.json", lambda c: c.update(compra={"renuncia": {"requerido": True, "texto_version": "v1"}}))
        self.generar()
        self.assertEqual([], self.hallazgos())
        self._aplicar(self.d, "comprar.html", _sub(r'<label class="casillas__fila" for="renuncia_desistimiento">.*?</label>', ""))
        self.assertIn("L1-FORMULARIO", self.reglas())
        self.editar("05-landing/checkout.json", lambda c: c.update(compra={"renuncia": {"requerido": False}}))
        self.generar()
        self.assertEqual([], self.hallazgos())
        self._aplicar(self.d, "comprar.html", _antes_del_boton('<label for="renuncia_desistimiento"><input type="checkbox" id="renuncia_desistimiento" name="renuncia_desistimiento" required> x</label>'))
        self.assertIn("L1-FORMULARIO", self.reglas())

    def test_version_del_texto_distinta_de_la_del_contrato(self) -> None:
        self.generar()                                             # pl no; es sin contrato
        self.editar("05-landing/checkout.json", lambda c: c.update(compra={"renuncia": {"requerido": True, "texto_version": "v2"}}))
        self.generar()
        self.assertEqual([], self.hallazgos())
        self._aplicar(self.d, "comprar.html", _sub(r'data-texto-version="v2"', 'data-texto-version="v1"'))
        self.assertIn("L1-FORMULARIO", self.reglas())

    def test_el_bump_sin_oferta_previa_falla_y_con_oferta_previa_es_obligatorio(self) -> None:
        self.generar()
        self._aplicar(self.d, "comprar.html", _antes_del_boton('<label for="bump"><input type="checkbox" id="bump" name="bump"> x</label>'))
        self.assertIn("L1-FORMULARIO", self.reglas())
        self.editar("05-landing/checkout.json", lambda c: c["bump"].update(modo="oferta_previa"))
        self.generar()
        self.assertEqual([], self.hallazgos())
        self._aplicar(self.d, "comprar.html", _sub(r'<label class="casillas__fila" for="bump">.*?</label>', ""))
        self.assertIn("L1-FORMULARIO", self.reglas())
        self.generar()
        self._aplicar(self.d, "comprar.html", _sub(r'name="bump"', 'name="bump" checked'))
        self.assertTrue({"L1-FORMULARIO", "L1-CASILLA-PREMARCADA"} <= self.reglas())

    def test_los_controles_sueltos_no_cambian_las_mutaciones_de_siempre(self) -> None:
        # Una casilla suelta fuera de /comprar no es L1-FORMULARIO (solo L1-CASILLA-PREMARCADA si está premarcada): como la MC-04 de CT.
        self.generar()
        self._aplicar(self.d, "index.html", _sub(r"(<footer)", '<p><label><input type="checkbox" name="bump" checked> Añadir</label></p>\\1'))
        self.assertEqual({"L1-CASILLA-PREMARCADA"}, self.reglas())

    def test_un_boton_de_tipo_button_sigue_permitido_fuera_del_formulario(self) -> None:
        self.generar()
        self.assertIn('data-consent-abrir', self.leer("index.html"))
        self.assertEqual([], self.hallazgos())


class PruebaCsp(Base):
    def test_la_csp_generada_es_exactamente_la_canonica(self) -> None:
        self.generar()
        h = self.leer("_headers")
        self.assertIn(f"  Content-Security-Policy: {CSP_CANONICA}\n", h)
        self.assertEqual(1, h.count("Content-Security-Policy"))
        self.assertNotIn("unsafe", h)
        self.assertNotIn("challenges.cloudflare.com", h)
        self.assertEqual([], self.hallazgos())

    def test_el_validador_acepta_el_orden_distinto_de_directivas_y_tokens(self) -> None:
        self.generar()
        partes = CSP_CANONICA.split("; ")
        self.escribir("_headers", "/*\n  Content-Security-Policy: " + "; ".join(reversed(partes)) + "\n")
        self.assertEqual([], self.hallazgos())
        self.escribir("_headers", "/*\n  Content-Security-Policy: " + CSP_CANONICA.replace("form-action 'self' https://checkout.stripe.com", "form-action https://checkout.stripe.com 'self'") + "\n")
        self.assertEqual([], self.hallazgos())

    def test_ausente_falla_si_el_sitio_tiene_comprar(self) -> None:
        self.generar()
        (self.sitio / "_headers").unlink()
        self.assertIn("L1-CSP", self.reglas())

    def test_ausente_se_tolera_sin_comprar_html_sitios_anteriores(self) -> None:
        (self.land / "copy.json").unlink()
        self.editar("05-landing/rutas.json", lambda r: (r.pop("/desistimiento"), r.pop("/api/sesion"), r.update({"/comprar": "dinamica:crear-sesion"})))
        self.generar()
        (self.sitio / "_headers").unlink()
        self.assertEqual([], self.hallazgos())

    def test_el_sitio_minimo_tambien_lleva_la_csp_canonica(self) -> None:
        (self.land / "copy.json").unlink()
        self.generar()
        self.assertIn(CSP_CANONICA, self.leer("_headers"))

    def test_otras_cabeceras_no_cuentan_pero_dos_csp_si(self) -> None:
        self.generar()
        original = self.leer("_headers")
        self.escribir("_headers", original + "  Permissions-Policy: camera=()\n")
        self.assertEqual([], self.hallazgos())
        self.escribir("_headers", original + "  Content-Security-Policy: default-src 'self'\n")
        self.assertIn("L1-CSP", self.reglas())


class PruebaMutacionesDeLaCsp(Base):
    """MS-01 sin form-action · MS-02 con 'unsafe-inline' · MS-03 origen fuera de la lista · MS-04 frame-src ausente o con origen fuera de lista · MS-05 data: fuera de img-src:
    L1-CSP al 100 %, en las dos ofertas."""

    @staticmethod
    def _con(original: str, antes: str, despues: str) -> str:
        assert antes in original, antes
        return original.replace(antes, despues, 1)

    def mutaciones(self) -> dict[str, list[tuple[str, str]]]:
        c = CSP_CANONICA
        return {
            "MS-01": [  # sin form-action
                ("sin la directiva", c.replace("; form-action 'self' https://checkout.stripe.com", "")),
                ("form-action solo self (Chrome bloquea el 303)", c.replace("form-action 'self' https://checkout.stripe.com", "form-action 'self'")),
                ("form-action sin self", c.replace("form-action 'self' https://checkout.stripe.com", "form-action https://checkout.stripe.com")),
                ("form-action vacío", c.replace("form-action 'self' https://checkout.stripe.com", "form-action 'none'")),
                ("form-action repetido", c + "; form-action 'self'"),
                ("form-action en mayúsculas pero con otro valor", c.replace("form-action 'self' https://checkout.stripe.com", "FORM-ACTION *")),
            ],
            "MS-02": [  # 'unsafe-inline' (y su pariente 'unsafe-eval')
                ("unsafe-inline en script-src", c.replace("script-src 'self'", "script-src 'self' 'unsafe-inline'")),
                ("unsafe-inline en style-src", c.replace("style-src 'self'", "style-src 'self' 'unsafe-inline'")),
                ("unsafe-inline en default-src", c.replace("default-src 'self'", "default-src 'self' 'unsafe-inline'")),
                ("unsafe-eval en script-src", c.replace("script-src 'self'", "script-src 'self' 'unsafe-eval'")),
                ("unsafe-inline con comillas dobles de más", c.replace("style-src 'self'", "style-src 'self' 'unsafe-inline' 'unsafe-hashes'")),
            ],
            "MS-03": [  # un origen fuera de la lista
                ("origen extra en script-src", c.replace("script-src 'self' https://connect.facebook.net", "script-src 'self' https://connect.facebook.net https://cdn.terceros.invalid")),
                ("origen extra en connect-src", c.replace("connect-src 'self'", "connect-src 'self' https://api.terceros.invalid")),
                ("origen extra en img-src", c.replace("img-src 'self'", "img-src 'self' https://img.terceros.invalid")),
                ("origen extra en form-action", c.replace("https://checkout.stripe.com", "https://checkout.stripe.com https://pagos.terceros.invalid")),
                ("origen extra en default-src", c.replace("default-src 'self'", "default-src 'self' https://cdn.terceros.invalid")),
                ("comodín", c.replace("script-src 'self'", "script-src * 'self'")),
                ("esquema https:", c.replace("img-src 'self'", "img-src 'self' https:")),
                ("origen de Meta en http", c.replace("https://connect.facebook.net;", "http://connect.facebook.net;", 1)),
                ("subdominio comodín de Meta", c.replace("https://www.facebook.com", "https://*.facebook.com", 1)),
                ("falta un origen de la lista", c.replace("script-src 'self' https://connect.facebook.net", "script-src 'self'")),
                ("directiva de más (script-src-elem)", c + "; script-src-elem 'self' https://cdn.terceros.invalid"),
            ],
            "MS-04": [  # frame-src ausente o con un origen fuera de la lista
                ("frame-src ausente", c.replace("frame-src https://www.facebook.com https://connect.facebook.net; ", "")),
                ("frame-src con origen extra", c.replace("frame-src https://www.facebook.com", "frame-src https://www.facebook.com https://marcos.terceros.invalid")),
                ("frame-src solo con uno de los dos", c.replace("frame-src https://www.facebook.com https://connect.facebook.net", "frame-src https://www.facebook.com")),
                ("frame-src con origen ajeno", c.replace("frame-src https://www.facebook.com https://connect.facebook.net", "frame-src https://marcos.terceros.invalid")),
                ("frame-src con self", c.replace("frame-src https://www.facebook.com", "frame-src 'self' https://www.facebook.com")),
                ("frame-src con comodín de Meta", c.replace("frame-src https://www.facebook.com", "frame-src https://*.facebook.com")),
                ("frame-src con Turnstile fuera de /comprar", c.replace("frame-src https://www.facebook.com", "frame-src https://challenges.cloudflare.com https://www.facebook.com")),
                ("frame-src repetido", c + "; frame-src https://www.facebook.com"),
            ],
            "MS-05": [  # data: en cualquier directiva que no sea img-src (o ausente de img-src)
                ("data: en script-src", c.replace("script-src 'self'", "script-src 'self' data:")),
                ("data: en default-src", c.replace("default-src 'self'", "default-src 'self' data:")),
                ("data: en connect-src", c.replace("connect-src 'self'", "connect-src 'self' data:")),
                ("data: en frame-src", c.replace("frame-src https://www.facebook.com", "frame-src data: https://www.facebook.com")),
                ("data: en style-src", c.replace("style-src 'self'", "style-src 'self' data:")),
                ("data: en font-src", c.replace("font-src 'self'", "font-src 'self' data:")),
                ("sin data: en img-src", c.replace("img-src 'self' data:", "img-src 'self'")),
            ],
        }

    def test_cada_mutacion_de_la_csp_falla_en_las_dos_ofertas(self) -> None:
        total = 0
        for clave in OFERTAS:
            with tempfile.TemporaryDirectory() as t:
                d = self.preparar(Path(t), clave)
                G.generar_sitio(d)
                ruta = d / "05-landing" / "sitio" / "_headers"
                original = ruta.read_text(encoding="utf-8")
                self.assertEqual([], [(h.regla, h.detalle) for h in Val.validar_sitio(d)], "la base debe pasar limpia")
                for mid, variantes in self.mutaciones().items():
                    for nombre, csp in variantes:
                        with self.subTest(f"{clave} {mid} {nombre}"):
                            self.assertNotEqual(CSP_CANONICA, csp)
                            ruta.write_text(f"/*\n  Content-Security-Policy: {csp}\n", encoding="utf-8")
                            reglas = {h.regla for h in Val.validar_sitio(d)}
                            self.assertIn("L1-CSP", reglas, (mid, nombre))
                            total += 1
                ruta.write_text(original, encoding="utf-8")
                self.assertEqual([], [(h.regla, h.detalle) for h in Val.validar_sitio(d)])
        self.assertEqual(2 * (6 + 5 + 11 + 8 + 7), total)

    def test_con_turnstile_el_origen_va_solo_en_el_bloque_de_comprar(self) -> None:
        self.editar("05-landing/checkout.json", lambda c: c.update(turnstile={"habilitado": True, "sitekey": SITEKEY}))
        self.generar()
        original = self.leer("_headers")
        general, comprar = original.split("/comprar\n")
        self.assertIn(f"Content-Security-Policy: {CSP_CANONICA}\n", general)
        self.assertEqual(1, comprar.count("script-src 'self' https://connect.facebook.net https://challenges.cloudflare.com;"))
        self.assertEqual(1, comprar.count("frame-src https://www.facebook.com https://connect.facebook.net https://challenges.cloudflare.com;"))
        self.assertEqual(1, general.count("frame-src https://www.facebook.com https://connect.facebook.net;"))
        self.assertEqual([], self.hallazgos())
        # el origen de Turnstile en la CSP general (todas las páginas) falla
        self.escribir("_headers", original.replace(f"Content-Security-Policy: {CSP_CANONICA}\n", f"Content-Security-Policy: {CSP_CANONICA.replace('https://connect.facebook.net;', 'https://connect.facebook.net https://challenges.cloudflare.com;', 1)}\n", 1))
        self.assertIn("L1-CSP", self.reglas())


class PruebaTurnstile(Base):
    """Apagado por defecto; con ``checkout.turnstile.habilitado = true``: UN script externo exacto, solo en /comprar."""

    URL = "https://challenges.cloudflare.com/turnstile/v0/api.js"

    def habilitar(self) -> None:
        self.editar("05-landing/checkout.json", lambda c: c.update(turnstile={"habilitado": True, "sitekey": SITEKEY}))

    def test_por_defecto_no_hay_turnstile_en_ninguna_parte(self) -> None:
        self.generar()
        for p in self.sitio.rglob("*"):
            if p.is_file():
                self.assertNotIn("challenges.cloudflare.com", p.read_text(encoding="utf-8", errors="ignore"), p.name)

    def test_habilitado_solo_comprar_lleva_el_script_y_la_csp_aparte(self) -> None:
        self.habilitar()
        av = self.generar()
        comprar = self.leer("comprar.html")
        self.assertEqual(1, comprar.count(self.URL))
        self.assertIn(f'<div class="cf-turnstile" data-sitekey="{SITEKEY}"></div>', comprar)
        self.assertEqual(['src="/js/consentimiento.js"', f'src="{self.URL}"'], re.findall(r'<script[^>]*?(src="[^"]+")', comprar))
        for rel in ("index.html", "gracias.html", "legal/privacidad.html", "a/pregunta-de-entrevista.html"):
            self.assertNotIn("challenges.cloudflare.com", self.leer(rel), rel)
        h = self.leer("_headers")
        self.assertIn("/comprar\n  ! Content-Security-Policy\n", h)
        self.assertIn("script-src 'self' https://connect.facebook.net https://challenges.cloudflare.com", h)
        self.assertEqual(2, h.count("form-action 'self' https://checkout.stripe.com"))       # una en /* y otra en /comprar
        self.assertTrue(any("Turnstile habilitado" in a for a in av))
        self.assertEqual([], self.hallazgos())

    def test_habilitado_sin_sitekey_falla_cerrado(self) -> None:
        self.editar("05-landing/checkout.json", lambda c: c.update(turnstile={"habilitado": True}))
        with self.assertRaises(ErrorValidacion):
            self.generar()


    def test_la_clave_secreta_jamas_va_en_checkout_ni_en_el_sitio(self) -> None:
        for clave in ("secret", "secret_key", "clave_secreta", "turnstile_secret", "secreto", "otra"):
            with self.subTest(clave):
                self.editar("05-landing/checkout.json", lambda c, k=clave: c.update(turnstile={"habilitado": True, "sitekey": SITEKEY, k: "0x4AAAAAAAsecretoDePrueba"}))
                with self.assertRaises(ErrorValidacion) as cm:
                    self.generar()
                self.assertIn("SECRETA", cm.exception.mensaje)
        self.habilitar()
        self.generar()
        for p in self.sitio.rglob("*"):
            if p.is_file():
                texto = p.read_text(encoding="utf-8", errors="ignore").lower()
                self.assertNotIn("secret", texto.replace("secretaría", ""), p.name)
        self.assertIn(SITEKEY, self.leer("comprar.html"))                    # la clave pública sí

    def test_el_codigo_de_landing_no_conoce_la_clave_secreta(self) -> None:
        for p in (RAIZ / "landing").glob("*.py"):
            self.assertNotIn("TURNSTILE_SECRET", p.read_text(encoding="utf-8"), p.name)

    def test_turnstile_false_o_ausente_es_lo_mismo(self) -> None:
        self.editar("05-landing/checkout.json", lambda c: c.update(turnstile={"habilitado": False, "sitekey": SITEKEY}))
        self.generar()
        self.assertNotIn("challenges.cloudflare.com", self.leer("comprar.html"))

    def test_mutaciones_del_script_externo(self) -> None:
        pie = '<script src="' + self.URL + '" async defer></script></head>'
        # 1) sin el flag, el script exacto en /comprar sigue prohibido
        self.generar()
        ruta = self.sitio / "comprar.html"
        ruta.write_text(ruta.read_text(encoding="utf-8").replace("</head>", pie, 1), encoding="utf-8")
        self.assertIn("L1-SCRIPT-EXTERNO", self.reglas())
        # 2) con el flag: en otra página, repetido o con otra URL, también
        self.habilitar()
        self.generar()
        base = ruta.read_text(encoding="utf-8")
        self.assertEqual([], self.hallazgos())
        casos = (
            ("en la portada", "index.html", lambda t: t.replace("</head>", pie, 1)),
            ("repetido en /comprar", "comprar.html", lambda t: t.replace("</head>", pie, 1)),
            ("otra versión", "comprar.html", lambda t: t.replace("/turnstile/v0/api.js", "/turnstile/v1/api.js")),
            ("otro origen", "comprar.html", lambda t: t.replace("challenges.cloudflare.com", "cdn.invalid")),
            ("script de otro tercero", "comprar.html", lambda t: t.replace("</head>", '<script src="https://cdn.terceros.invalid/x.js"></script></head>', 1)),
        )
        for nombre, rel, f in casos:
            with self.subTest(nombre):
                self.generar()
                p = self.sitio / rel
                p.write_text(f(p.read_text(encoding="utf-8")), encoding="utf-8")
                self.assertTrue(self.reglas() & {"L1-SCRIPT-EXTERNO", "L1-SCRIPT-NO-PERMITIDO"}, nombre)
        self.generar()
        self.assertEqual(base, ruta.read_text(encoding="utf-8"))

    def test_csp_de_comprar_con_turnstile_mal_formada_falla(self) -> None:
        self.habilitar()
        self.generar()
        original = self.leer("_headers")
        for nombre, nuevo in (
            ("sin el bloque /comprar", original.split("/comprar")[0]),
            ("sin quitar la CSP general", original.replace("  ! Content-Security-Policy\n", "")),
            ("sin Turnstile en frame-src", original.replace("frame-src https://www.facebook.com https://connect.facebook.net https://challenges.cloudflare.com", "frame-src https://www.facebook.com https://connect.facebook.net")),
            ("script-src sin Turnstile", original.replace("script-src 'self' https://connect.facebook.net https://challenges.cloudflare.com", "script-src 'self' https://connect.facebook.net")),
        ):
            with self.subTest(nombre):
                self.escribir("_headers", nuevo)
                self.assertIn("L1-CSP", self.reglas(), nombre)

    def test_header_de_turnstile_sin_el_flag_falla(self) -> None:
        self.generar()
        self.escribir("_headers", self.leer("_headers") + "/comprar\n  ! Content-Security-Policy\n  Content-Security-Policy: script-src 'self' https://challenges.cloudflare.com; form-action 'self' https://checkout.stripe.com\n")
        self.assertIn("L1-CSP", self.reglas())


class PruebaCookiesDeConsentimiento(unittest.TestCase):
    """``consentimiento.js`` en Node con un DOM simulado: ``fab_vid`` y ``fab_attr`` SOLO tras el consentimiento de marketing."""

    ARNES = r"""
const fs = require('fs'), vm = require('vm');
const codigo = fs.readFileSync(process.argv[2], 'utf8');
const caso = JSON.parse(process.argv[3]);
const escrituras = [];
const jarra = {};
const oyentes = {};
function elemento(tag) {
  const e = { tag, hijos: [], attrs: {}, listeners: {}, setAttribute(k, v) { this.attrs[k] = v; if (k === 'id') { registro[v] = this; } },
    removeAttribute(k) { delete this.attrs[k]; }, appendChild(h) { this.hijos.push(h); return h; }, prepend(h) { this.hijos.unshift(h); },
    addEventListener(t, f) { this.listeners[t] = f; }, get parentNode() { return {removeChild() {}}; }, checked: false };
  return e;
}
const registro = {};
const documento = {
  readyState: 'complete', documentElement: elemento('html'), head: elemento('head'), body: elemento('body'),
  createElement: elemento, createTextNode: (t) => ({ texto: t }), querySelectorAll: () => [],
  getElementById: (id) => registro[id] || null, addEventListener() {}, dispatchEvent() {},
  get cookie() { return Object.entries(jarra).map(([k, v]) => k + '=' + v).join('; '); },
  set cookie(v) {
    escrituras.push(v);
    const [par, ...atr] = v.split('; ');
    const i = par.indexOf('=');
    const k = par.slice(0, i), val = par.slice(i + 1);
    if (atr.some((a) => a === 'Max-Age=0')) { delete jarra[k]; } else { jarra[k] = val; }
  },
};
if (caso.cookieConsent) { jarra['fabrica_consent'] = caso.cookieConsent; }
const ventana = { crypto: { getRandomValues(b) { for (let i = 0; i < b.length; i++) { b[i] = (i * 37 + 11) & 255; } return b; } } };
const contexto = { document: documento, window: ventana, location: { protocol: caso.protocolo || 'https:', search: caso.search || '', hostname: 'tienda.invalid', reload() {} },
  URLSearchParams, CustomEvent: class { constructor(t, o) { this.type = t; this.detail = o && o.detail; } }, Date, JSON, Uint8Array, encodeURIComponent, decodeURIComponent, Object, Array };
contexto.window.document = documento;
vm.createContext(contexto);
vm.runInContext(codigo, contexto);
for (const id of caso.clics || []) { registro[id].listeners.click(); }
console.log(JSON.stringify({ escrituras, jarra, banner: !!registro['fabrica-consent'] || Object.keys(registro).length > 0 }));
"""

    @classmethod
    def setUpClass(cls) -> None:
        cls.node = shutil.which("node")
        cls.dir = Path(tempfile.mkdtemp(prefix="landing-js-"))
        (cls.dir / "arnes.js").write_text(cls.ARNES, encoding="utf-8")
        (cls.dir / "c.js").write_text(P.consentimiento_js(duracion_vid_s=7776000, duracion_attr_s=2592000), encoding="utf-8")

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.dir, True)

    def correr(self, **caso) -> dict:
        if not self.node:
            self.skipTest("node no está instalado")
        r = subprocess.run([self.node, str(self.dir / "arnes.js"), str(self.dir / "c.js"), json.dumps(caso)], capture_output=True, text=True, timeout=30)
        self.assertEqual(0, r.returncode, r.stderr)
        return json.loads(r.stdout.strip().splitlines()[-1])

    def propias(self, salida: dict) -> list[str]:
        """Escrituras (no borrados) de fab_vid y fab_attr."""
        return [e for e in salida["escrituras"] if e.startswith(("fab_vid=", "fab_attr=")) and "Max-Age=0" not in e]

    URL = "?utm_source=meta&utm_campaign=cam%7Cuno&cid=123456&asid=234567&adid=345678&email=a@b.invalid&evil=1"

    def test_sin_eleccion_no_hay_cookies_propias_y_se_borran_las_de_marketing(self) -> None:
        s = self.correr(search=self.URL)
        self.assertEqual([], self.propias(s))
        borradas = [e.split("=")[0] for e in s["escrituras"] if "Max-Age=0" in e]
        self.assertTrue({"_fbp", "_fbc", "fab_vid", "fab_attr"} <= set(borradas))
        self.assertNotIn("fab_vid", s["jarra"])

    def test_rechazar_no_escribe_cookies_propias(self) -> None:
        s = self.correr(search=self.URL, clics=["fc-rechazar"])
        self.assertEqual([], self.propias(s))
        self.assertNotIn("fab_attr", s["jarra"])
        self.assertIn("fabrica_consent", s["jarra"])                                    # solo la cookie de la elección

    def test_aceptar_escribe_fab_vid_y_fab_attr_con_sus_atributos(self) -> None:
        s = self.correr(search=self.URL, clics=["fc-aceptar"])
        vid = next(e for e in self.propias(s) if e.startswith("fab_vid="))
        attr = next(e for e in self.propias(s) if e.startswith("fab_attr="))
        self.assertRegex(vid, r"^fab_vid=[0-9a-f]{32}; Path=/; Max-Age=7776000; SameSite=Lax; Secure$")
        self.assertRegex(attr, r"; Path=/; Max-Age=2592000; SameSite=Lax; Secure$")
        valor = attr.split("; ")[0].split("=", 1)[1]
        pares = dict(p.split("=") for p in valor.split("&"))
        self.assertEqual({"utm_source", "utm_campaign", "cid", "asid", "adid"}, set(pares))   # lista cerrada: sin email ni «evil»
        self.assertEqual("cam%7Cuno", pares["utm_campaign"])                                  # el %7C se decodifica y se vuelve a codificar
        self.assertNotIn("@", attr)
        self.assertEqual("fab_vid=" + vid.split("=")[1].split(";")[0], "fab_vid=" + s["jarra"]["fab_vid"])

    def test_el_visitor_id_cumple_el_formato_del_worker(self) -> None:
        s = self.correr(clics=["fc-aceptar"])
        self.assertRegex(s["jarra"]["fab_vid"], r"^[A-Za-z0-9_-]{16,64}$")

    def test_sin_parametros_de_anuncio_solo_se_escribe_fab_vid(self) -> None:
        s = self.correr(clics=["fc-aceptar"])
        self.assertEqual(1, len(self.propias(s)))
        self.assertNotIn("fab_attr", s["jarra"])

    def test_http_local_no_pone_secure(self) -> None:
        s = self.correr(protocolo="http:", clics=["fc-aceptar"])
        self.assertTrue(all("Secure" not in e for e in self.propias(s)))

    def test_valores_largos_o_con_control_se_acotan(self) -> None:
        s = self.correr(search="?utm_source=" + "a" * 500 + "&utm_medium=x%00y%1Fz", clics=["fc-aceptar"])
        attr = next(e for e in self.propias(s) if e.startswith("fab_attr=")).split("; ")[0]
        self.assertLessEqual(len(attr.split("=", 1)[1]), 400)
        self.assertNotIn("%00", attr)

    def test_con_consentimiento_vigente_se_refresca_la_atribucion(self) -> None:
        consent = '%7B%22v%22%3A%22v1%22%2C%22m%22%3A1%2C%22t%22%3A%222026-11-06T10%3A00%3A00.000Z%22%2C%22id%22%3A%22aabbccddeeff0011%22%7D'
        s = self.correr(cookieConsent=consent, search="?cid=123456&adid=345678")
        self.assertIn("fab_vid=aabbccddeeff0011; Path=/; Max-Age=7776000; SameSite=Lax; Secure", s["escrituras"])
        self.assertTrue(any(e.startswith("fab_attr=cid=123456&adid=345678;") for e in s["escrituras"]))

    def test_con_rechazo_vigente_no_se_escribe_nada(self) -> None:
        consent = '%7B%22v%22%3A%22v1%22%2C%22m%22%3A0%2C%22t%22%3A%222026-11-06T10%3A00%3A00.000Z%22%2C%22id%22%3Anull%7D'
        s = self.correr(cookieConsent=consent, search=self.URL)
        self.assertEqual([], self.propias(s))

    def test_texto_de_otra_version_vuelve_a_preguntar_y_no_escribe(self) -> None:
        consent = '%7B%22v%22%3A%22v0%22%2C%22m%22%3A1%2C%22t%22%3A%22x%22%2C%22id%22%3A%22aabbccddeeff0011%22%7D'
        s = self.correr(cookieConsent=consent, search=self.URL)
        self.assertEqual([], self.propias(s))
        self.assertNotIn("fab_vid", s["jarra"])

    def test_la_duracion_es_parametro_y_se_valida(self) -> None:
        js = P.consentimiento_js(duracion_vid_s=111, duracion_attr_s=222)
        self.assertIn("duracion_vid_segundos: 111", js)
        self.assertIn("duracion_attr_segundos: 222", js)
        for malo in (0, -5, True, "90"):
            with self.assertRaises(ValueError):
                P.consentimiento_js(duracion_vid_s=malo)

    def test_las_duraciones_salen_de_parametros_yaml_si_existen(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            d = Base.preparar(Path(t), "es")
            (Path(t) / "empresa").mkdir(exist_ok=True)
            (Path(t) / "empresa" / "parametros.yaml").write_text("grupos:\n  landing:\n    cookie_vid_dias:\n      valor: 7\n    cookie_attr_dias:\n      valor: 2\n", encoding="utf-8")
            av = G.generar_sitio_con_avisos(d)[1]
            js = (d / "05-landing" / "sitio" / "js" / "consentimiento.js").read_text(encoding="utf-8")
            self.assertIn(f"duracion_vid_segundos: {7 * 86400}", js)
            self.assertIn(f"duracion_attr_segundos: {2 * 86400}", js)
            self.assertFalse(any("cookie_vid_dias" in a for a in av))


    def test_el_tope_de_395_dias_y_el_respaldo_aprobado(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            d = Base.preparar(Path(t), "es")
            ruta = Path(t) / "empresa" / "parametros.yaml"
            ruta.parent.mkdir(exist_ok=True)
            for vid, attr, ok in ((395, 395, True), (396, 30, False), (90, 400, False)):
                ruta.write_text(f"grupos:\n  landing:\n    cookie_vid_dias:\n      valor: {vid}\n    cookie_attr_dias:\n      valor: {attr}\n", encoding="utf-8")
                if ok:
                    G.generar_sitio_con_avisos(d)
                    self.assertIn(f"duracion_vid_segundos: {395 * 86400}", (d / "05-landing" / "sitio" / "js" / "consentimiento.js").read_text(encoding="utf-8"))
                else:
                    with self.assertRaises(ErrorValidacion) as cm:
                        G.generar_sitio_con_avisos(d)
                    self.assertIn("tope", cm.exception.mensaje)
            ruta.unlink()
            av = G.generar_sitio_con_avisos(d)[1]
            js = (d / "05-landing" / "sitio" / "js" / "consentimiento.js").read_text(encoding="utf-8")
            self.assertIn(f"duracion_vid_segundos: {90 * 86400}", js)                 # respaldo aprobado: 90 y 30 días
            self.assertIn(f"duracion_attr_segundos: {30 * 86400}", js)
            self.assertTrue(any("respaldo aprobado por S-A" in a for a in av))

    def test_sin_parametros_se_usa_el_defecto_con_aviso(self) -> None:
        with tempfile.TemporaryDirectory() as t:
            d = Base.preparar(Path(t), "es")
            av = G.generar_sitio_con_avisos(d)[1]
            self.assertTrue(any("cookie_vid_dias" in a and "HIPÓTESIS" in a for a in av))

    def test_el_js_no_lleva_datos_personales_ni_tocan_cookies_de_otros(self) -> None:
        js = (self.dir / "c.js").read_text(encoding="utf-8")
        self.assertNotIn("email", js)
        escrituras = re.findall(r"document\.cookie = (\S+)", js)
        self.assertTrue(all(e.startswith(("CONFIG.cookie", "n")) for e in escrituras), escrituras)

    # ---- fab_attr: serialización y recorte (decisión de S-A, LT-38) ----
    def attr(self, search: str) -> str | None:
        s = self.correr(search=search, clics=["fc-aceptar"])
        escrito = [e for e in self.propias(s) if e.startswith("fab_attr=")]
        return escrito[0].split("; ")[0].split("=", 1)[1] if escrito else None

    def pares(self, valor: str) -> list[tuple[str, str]]:
        from urllib.parse import unquote
        return [(k, unquote(v)) for k, v in (p.split("=", 1) for p in valor.split("&"))]

    def test_solo_las_claves_admitidas_en_orden_canonico(self) -> None:
        v = self.attr("?fbclid=IwAR0abc&utm_term=t&utm_content=c&utm_campaign=ca&utm_medium=m&utm_source=s&adid=345678&asid=234567&cid=123456&email=a%40b.invalid&evil=1&ref=x")
        self.assertEqual(["cid", "asid", "adid", "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "fbclid"], [k for k, _ in self.pares(v)])
        self.assertNotRegex(v, r"email|evil|ref=")

    def test_los_ids_exigen_6_a_20_digitos(self) -> None:
        for malo in ("12345", "123456789012345678901", "12345a", "abcdef", "12 3456", "-123456", "123456.7", ""):
            with self.subTest(malo):
                self.assertIsNone(self.attr(f"?cid={malo}&asid={malo}&adid={malo}"))
        v = self.attr("?cid=123456&asid=12345678901234567890&adid=99999999")
        self.assertEqual([("cid", "123456"), ("asid", "12345678901234567890"), ("adid", "99999999")], self.pares(v))

    def test_un_id_invalido_no_arrastra_a_los_validos(self) -> None:
        v = self.attr("?cid=abc&asid=234567&adid=1&utm_source=meta")
        self.assertEqual([("asid", "234567"), ("utm_source", "meta")], self.pares(v))

    def test_nunca_pasa_de_400_bytes(self) -> None:
        largo = "x" * 900
        for search in (f"?utm_source={largo}&utm_campaign={largo}&utm_content={largo}&fbclid={largo}&cid=123456&asid=234567&adid=345678",
                       "?" + "&".join(f"{k}={'ł' * 300}" for k in ("utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "fbclid")),
                       f"?utm_source={'%7C' * 400}", f"?cid=123456&utm_medium={'ñ' * 5000}&utm_campaign=ok"):
            with self.subTest(search[:40]):
                v = self.attr(search)
                self.assertIsNotNone(v)
                self.assertLessEqual(len(v.encode("utf-8")), 400)
                self.assertRegex(v, r"^[A-Za-z0-9_.!~*'()%=&-]+$")           # solo ASCII percent-encoded

    def test_los_ids_siempre_caben_aunque_el_resto_llene_el_tope(self) -> None:
        v = self.attr(f"?utm_source={'a' * 900}&utm_campaign={'b' * 900}&cid=123456&asid=234567&adid=345678")
        d = dict(self.pares(v))
        self.assertEqual(("123456", "234567", "345678"), (d["cid"], d["asid"], d["adid"]))
        self.assertLessEqual(len(v), 400)

    def test_el_recorte_no_corta_secuencias_de_escape_ni_caracteres(self) -> None:
        from urllib.parse import unquote
        v = self.attr(f"?cid=123456&utm_campaign={'€' * 500}")                # cada € = %E2%82%AC (9 bytes)
        self.assertLessEqual(len(v), 400)
        self.assertNotRegex(v, r"%[0-9A-Fa-f]?(?![0-9A-Fa-f])")               # ningún % a medias
        valor = dict(self.pares(v))["utm_campaign"]
        self.assertTrue(valor and set(valor) == {"€"})                          # cada carácter completo, ninguno partido
        unquote(v, errors="strict")                                           # decodifica sin errores

    def test_percent_encoding_ida_y_vuelta(self) -> None:
        v = self.attr("?utm_campaign=cam%7Cuno%20dos%26tres%3Dcuatro&utm_source=a+b")
        d = dict(self.pares(v))
        self.assertEqual("cam|uno dos&tres=cuatro", d["utm_campaign"])
        self.assertEqual("a b", d["utm_source"])                                # URLSearchParams decodifica + como espacio
        self.assertEqual(2, v.count("&") + 1)                                  # los & del valor van codificados: solo hay 2 pares
        self.assertNotIn(" ", v)
        self.assertNotIn("|", v)

    def test_sin_claves_admitidas_no_hay_cookie_attr(self) -> None:
        self.assertIsNone(self.attr("?foo=bar&email=a%40b.invalid&gclid=abc"))
        self.assertIsNone(self.attr(""))

    def test_valor_vacio_no_se_escribe(self) -> None:
        v = self.attr("?utm_source=&utm_medium=m")
        self.assertEqual([("utm_medium", "m")], self.pares(v))

    def test_fab_vid_son_128_bits_aleatorios_en_hexadecimal(self) -> None:
        js = (self.dir / "c.js").read_text(encoding="utf-8")
        self.assertIn("getRandomValues", js)
        self.assertIn("new Uint8Array(16)", js)
        s = self.correr(clics=["fc-aceptar"])
        self.assertRegex(s["jarra"]["fab_vid"], r"^[0-9a-f]{32}$")
        self.assertRegex(s["jarra"]["fab_vid"], r"^[A-Za-z0-9_-]{16,64}$")     # formato que acepta el Worker
        self.assertEqual(s["jarra"]["fab_vid"], json.loads(urllib_decode(s["jarra"]["fabrica_consent"]))["id"])   # el mismo id del píxel

    def test_el_script_no_usa_math_random(self) -> None:
        self.assertNotIn("Math.random", (self.dir / "c.js").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
