"""Pruebas de scripts/modelado/barrido/ruta_c.py: cliente de `ads_archive` y conversor al crudo de CONTRATO §2.

Sin red: `socket.socket` está bloqueado en cada prueba y el transporte es un doble (`TransporteFalso`) con respuestas
SIMULADAS que imitan la forma documentada de la API (campos de ArchivedAd, `paging.cursors`, `paging.next` con
`access_token` incrustado, `error.code` 190/613/100/10). No son respuestas reales: la API no se ha consultado con un
token (eso solo lo puede hacer el dueño; ver docs/_historial/barrido-ruta-c.md).
"""

from __future__ import annotations

import json
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from scripts.modelado.barrido import comun
from scripts.modelado.barrido import ruta_c as rc

TOKEN = "EAABsbCS1iHgBO" + "x" * 48 + "ZDZD"   # forma de un token de usuario; es de mentira
ENTORNO = {rc.VARIABLE_TOKEN: TOKEN}
CORRIDA = "2026-11-06-a"
CAPTURA = "2026-11-06T05:50:12Z"
CONSULTA = {"search_terms": "Acceso inmediato en PDF", "countries": ["ES"], "ad_active_status": "ACTIVE",
            "limit": 50, "page_ids": None}


def parametros(**cambios) -> rc.ParametrosRutaC:
    base = dict(version_api="v27.0", limite_pagina=50, max_paginas=20, pausa_ms=1500, tiempo_max_seg=30,
                max_bytes_respuesta=8_000_000, reintentos_tasa=0, max_solicitudes_por_corrida=50,
                max_solicitudes_por_dia=100, anuncios_por_archivo=50,
                tipo_busqueda="KEYWORD_UNORDERED",
                campos=("id", "page_id", "page_name", "ad_creation_time", "ad_delivery_start_time",
                        "ad_snapshot_url", "ad_creative_bodies", "ad_creative_link_titles", "currency",
                        "eu_total_reach", "publisher_platforms"),
                paises_cobertura=("ES", "IT", "PL", "DE", "GB"))
    base.update(cambios)
    return rc.ParametrosRutaC(**base)


def anuncio(n: int = 1, **cambios) -> dict:
    """Un anuncio como lo entrega ads_archive para un anuncio comercial de la UE (sin `currency`, sin spend)."""
    ident = str(1000000000000000 + n)
    a = {
        "id": ident,
        "ad_creation_time": "2026-11-04",
        "ad_creative_bodies": [f"Descarga ahora la guía {n}. Acceso inmediato en PDF, pago único."],
        "ad_creative_link_titles": [f"Guía práctica {n}"],
        "ad_delivery_start_time": "2026-11-05",
        "ad_snapshot_url": f"https://www.facebook.com/ads/archive/render_ad/?id={ident}&access_token={TOKEN}",
        "page_id": str(1431294770063492 + n % 3),
        "page_name": f"Página {n % 3}",
        "publisher_platforms": ["facebook", "instagram"],
        "eu_total_reach": 12000 + n,
    }
    a.update(cambios)
    return {k: v for k, v in a.items() if v is not None}


def pagina(anuncios: list[dict], siguiente: str | None = None) -> bytes:
    doc: dict = {"data": anuncios}
    if siguiente is not None:
        doc["paging"] = {
            "cursors": {"after": siguiente, "before": "QVFIUmFiZW"},
            "next": f"https://graph.facebook.com/v27.0/ads_archive?access_token={TOKEN}&after={siguiente}&limit=50",
        }
    else:
        doc["paging"] = {"cursors": {"after": "QVFIUlast", "before": "QVFIUmFiZW"}}
    return json.dumps(doc).encode("utf-8")


def error_api(codigo: int, mensaje: str = "Mensaje de Meta", tipo: str = "OAuthException", estado: int = 400):
    cuerpo = {"error": {"message": mensaje, "type": tipo, "code": codigo, "fbtrace_id": "AbCdEf"}}
    return rc.Respuesta(estado, json.dumps(cuerpo).encode("utf-8"))


def ok(cuerpo: bytes) -> rc.Respuesta:
    return rc.Respuesta(200, cuerpo)


class TransporteFalso(rc.Transporte):
    """Responde en orden con lo que se le dé (Respuesta o excepción) y registra cada solicitud."""

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.llamadas: list[dict] = []

    def solicitar(self, url, parametros, *, tiempo_max_seg, max_bytes):
        self.llamadas.append({"url": url, "parametros": dict(parametros),
                              "tiempo_max_seg": tiempo_max_seg, "max_bytes": max_bytes})
        if not self.respuestas:
            raise AssertionError("el transporte falso se quedó sin respuestas: se hizo una solicitud de más")
        r = self.respuestas.pop(0)
        if isinstance(r, BaseException):
            raise r
        return r


class Dormir:
    def __init__(self):
        self.pausas: list[float] = []
        self.efecto = None  # función opcional que se ejecuta en cada pausa

    def __call__(self, seg):
        self.pausas.append(seg)
        if self.efecto is not None:
            self.efecto()


class FrenosFalsos:
    """Doble de `Frenos` para probar el cliente solo: anota qué se le pidió y en qué orden."""

    def __init__(self, eventos=None, falla_en=None):
        self.eventos = [] if eventos is None else eventos
        self.falla_en = falla_en  # número de página en la que `antes_de_solicitar` dice no

    def antes_de_solicitar(self, pagina):
        if self.falla_en == pagina:
            raise rc.ErrorTope("tope de prueba")
        self.eventos.append(("antes", pagina))

    def despues_de_solicitar(self, estado):
        self.eventos.append(("despues", estado))

    def frenar(self, motivo):
        self.eventos.append(("frenar", motivo))


class Base(unittest.TestCase):
    def setUp(self):
        parche = mock.patch("socket.socket", side_effect=AssertionError("las pruebas no usan red"))
        parche.start()
        self.addCleanup(parche.stop)
        self.dormir = Dormir()

    def cliente(self, transporte, frenos=None, **cambios):
        return rc.ClienteBiblioteca(transporte, rc.leer_token(ENTORNO), parametros(**cambios),
                                    frenos or FrenosFalsos(), dormir=self.dormir)


# ---------------------------------------------------------------------------
# Token
# ---------------------------------------------------------------------------

class PruebasToken(Base):
    def test_se_lee_solo_del_entorno_y_no_se_muestra(self):
        t = rc.leer_token(ENTORNO)
        self.assertEqual(t.revelar(), TOKEN)
        self.assertNotIn(TOKEN, repr(t))
        self.assertNotIn(TOKEN, str(t))
        self.assertNotIn(TOKEN, f"{t}")
        with self.assertRaises(TypeError):
            import pickle
            pickle.dumps(t)

    def test_lee_del_entorno_real_del_proceso(self):
        with mock.patch.dict("os.environ", {rc.VARIABLE_TOKEN: TOKEN}):
            self.assertEqual(rc.leer_token().revelar(), TOKEN)

    def test_falta_falla_cerrado(self):
        for entorno in ({}, {rc.VARIABLE_TOKEN: ""}, {rc.VARIABLE_TOKEN: "   "}):
            with self.assertRaises(rc.ErrorBloqueado) as cm:
                rc.leer_token(entorno)
            self.assertIn(rc.VARIABLE_TOKEN, str(cm.exception))
        with mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(rc.ErrorBloqueado):
                rc.leer_token()

    def test_formato_inusable_se_rechaza_sin_mostrarlo(self):
        for malo in ("corto", "con espacio dentro del token valido", "token\nsalto-de-linea-aaaa", "ñ" * 20):
            with self.assertRaises(rc.ErrorBloqueado) as cm:
                rc.leer_token({rc.VARIABLE_TOKEN: malo})
            self.assertNotIn(malo, str(cm.exception))

    def test_el_cliente_exige_secreto(self):
        with self.assertRaises(rc.ErrorUso):
            rc.ClienteBiblioteca(TransporteFalso(), TOKEN, parametros(), FrenosFalsos())  # type: ignore[arg-type]

    def test_cliente_no_muestra_el_token_en_repr(self):
        self.assertNotIn(TOKEN, repr(self.cliente(TransporteFalso())))

    def test_sin_token_no_hay_ninguna_solicitud(self):
        transporte = TransporteFalso()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(rc.ErrorBloqueado):
                rc.barrer_consulta(CONSULTA, corrida_id=CORRIDA, qid="es-acceso", transporte=transporte,
                                   parametros=parametros(), entorno={}, raiz=Path(d), dormir=self.dormir)
            self.assertFalse((Path(d) / "empresa").exists())
        self.assertEqual(transporte.llamadas, [])

    def test_sanear_quita_cada_forma_del_token_por_separado(self):
        raro = rc.Secreto("appid123|secretoSinForma")  # no se parece a un token de usuario ni a access_token=
        self.assertEqual(rc._sanear("clave appid123|secretoSinForma fin", raro), "clave *** fin")
        self.assertNotIn("secretoSinForma", rc._sanear("x appid123|secretoSinForma", raro))
        # `access_token=<otro valor>` se tacha aunque no sea el token cargado
        self.assertEqual(rc._sanear("?a=1&access_token=OTRO_VALOR_123&b=2"), "?a=1&access_token=***&b=2")
        # un token con forma de Facebook (EAA...) se tacha aunque no sea el cargado ni venga en access_token=
        ajeno = "EAA" + "B" * 60
        self.assertNotIn(ajeno, rc._sanear(f"el token {ajeno} apareció"))
        # controles y largo
        self.assertNotIn("\n", rc._sanear("a\nb\x00c"))
        self.assertLessEqual(len(rc._sanear("z" * 1000)), 200)

    def test_quitar_token_de_url(self):
        url = f"https://www.facebook.com/ads/archive/render_ad/?id=5&access_token={TOKEN}"
        self.assertEqual(rc.quitar_token_de_url(url), "https://www.facebook.com/ads/archive/render_ad/?id=5")
        self.assertEqual(rc.quitar_token_de_url("https://x.com/a"), "https://x.com/a")
        self.assertEqual(rc.quitar_token_de_url("https://x.com/?a=1&ACCESS_TOKEN=zz&b=2"), "https://x.com/?a=1&b=2")


# ---------------------------------------------------------------------------
# Parámetros
# ---------------------------------------------------------------------------

class PruebasParametros(unittest.TestCase):
    def mapa(self):
        p = parametros()
        return {"ruta_c_version_api": p.version_api, "ruta_c_limite_pagina": p.limite_pagina,
                "ruta_c_max_paginas": p.max_paginas, "ruta_c_pausa_ms": p.pausa_ms,
                "ruta_c_tiempo_max_seg": p.tiempo_max_seg, "ruta_c_max_bytes_respuesta": p.max_bytes_respuesta,
                "ruta_c_reintentos_tasa": p.reintentos_tasa,
                "ruta_c_max_solicitudes_por_corrida": p.max_solicitudes_por_corrida,
                "ruta_c_max_solicitudes_por_dia": p.max_solicitudes_por_dia,
                "ruta_c_anuncios_por_archivo": p.anuncios_por_archivo, "ruta_c_tipo_busqueda": p.tipo_busqueda,
                "ruta_c_campos": list(p.campos), "ruta_c_paises_cobertura": list(p.paises_cobertura)}

    def test_el_yaml_propuesto_carga_y_es_coherente(self):
        p = rc.cargar_parametros_ruta_c()
        self.assertTrue(p.version_api.startswith("v"))
        self.assertLessEqual(p.anuncios_por_archivo, comun.LIMITE_MAX_CONECTOR)
        self.assertIn("ES", p.paises_cobertura)
        self.assertIn("PL", p.paises_cobertura)
        self.assertNotIn("US", p.paises_cobertura)
        for campo in rc.CAMPOS_OBLIGATORIOS:
            self.assertIn(campo, p.campos)

    def test_todas_las_claves_del_codigo_estan_en_el_yaml(self):
        import yaml
        datos = yaml.safe_load(rc.RUTA_PARAMETROS_RUTA_C.read_text(encoding="utf-8"))
        self.assertEqual(set(datos["grupos"]["descubrimiento"]), set(rc.CLAVES_RUTA_C))

    def test_mapa_valido(self):
        self.assertEqual(rc.parametros_desde_mapa(self.mapa()), parametros())

    def test_falta_una_clave_es_codigo_5(self):
        for clave in rc.CLAVES_RUTA_C:
            m = self.mapa()
            del m[clave]
            with self.assertRaises(rc.ErrorLimite, msg=clave):
                rc.parametros_desde_mapa(m)
        m = self.mapa()
        m["ruta_c_pausa_ms"] = None
        with self.assertRaises(rc.ErrorLimite):
            rc.parametros_desde_mapa(m)

    def test_valores_invalidos(self):
        casos = {
            "ruta_c_pausa_ms": [1.5, True, "2000", -1],
            "ruta_c_max_paginas": [0, 2.0],
            "ruta_c_anuncios_por_archivo": [0, comun.LIMITE_MAX_CONECTOR + 1],
            "ruta_c_version_api": ["27", "v27", 27],
            "ruta_c_tipo_busqueda": ["EXACT", None, 3],
            "ruta_c_campos": [[], ["Id"], ["id", "id"], "id"],
            "ruta_c_paises_cobertura": [[], ["es"], [False], ["ES", "ES"]],
        }
        for clave, malos in casos.items():
            for malo in malos:
                m = self.mapa()
                m[clave] = malo
                with self.assertRaises((rc.ErrorValidacion, rc.ErrorLimite), msg=f"{clave}={malo!r}"):
                    rc.parametros_desde_mapa(m)

    def test_campos_sin_los_obligatorios(self):
        m = self.mapa()
        m["ruta_c_campos"] = ["id", "page_id"]
        with self.assertRaises(rc.ErrorLimite) as cm:
            rc.parametros_desde_mapa(m)
        self.assertIn("ad_snapshot_url", str(cm.exception))

    def test_yaml_fuera_de_rango_o_ausente(self):
        with tempfile.TemporaryDirectory() as d:
            yaml_ok = rc.RUTA_PARAMETROS_RUTA_C.read_text(encoding="utf-8")
            roto = Path(d) / "roto.yaml"
            roto.write_text(yaml_ok.replace("valor: 2000", "valor: 1"), encoding="utf-8")
            with self.assertRaises(rc.ErrorLimite):
                rc.cargar_parametros_ruta_c(roto)
            sin_clave = Path(d) / "sin.yaml"
            sin_clave.write_text(yaml_ok.replace("ruta_c_pausa_ms:", "ruta_c_otra:"), encoding="utf-8")
            with self.assertRaises(rc.ErrorLimite):
                rc.cargar_parametros_ruta_c(sin_clave)
            with self.assertRaises(rc.ErrorLimite):
                rc.cargar_parametros_ruta_c(Path(d) / "no-existe.yaml")
            sin_rango = Path(d) / "sin_rango.yaml"
            sin_rango.write_text(yaml_ok.replace("rango: [500, 60000]", "rango: null"), encoding="utf-8")
            with self.assertRaises(rc.ErrorLimite) as cm:
                rc.cargar_parametros_ruta_c(sin_rango)
            self.assertIn("rango", str(cm.exception))
            malo = Path(d) / "malo.yaml"
            malo.write_text("grupos: [", encoding="utf-8")
            with self.assertRaises(rc.ErrorValidacion):
                rc.cargar_parametros_ruta_c(malo)


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------

class PruebasConsulta(unittest.TestCase):
    def norm(self, **cambios):
        c = dict(CONSULTA)
        c.update(cambios)
        return rc.normalizar_consulta(c, parametros())

    def test_normaliza(self):
        q = self.norm()
        self.assertEqual(q["countries"], ["ES"])
        self.assertEqual(q["limit"], 50)
        self.assertIsNone(q["page_ids"])

    def test_limit_nunca_supera_el_parametro(self):
        self.assertEqual(self.norm(limit=20)["limit"], 20)
        self.assertEqual(rc.normalizar_consulta({**CONSULTA, "limit": 50}, parametros(anuncios_por_archivo=30))["limit"], 30)
        with self.assertRaises((rc.ErrorUso, rc.ErrorLimite, rc.ErrorValidacion)):
            self.norm(limit=51)

    def test_un_solo_pais_y_en_cobertura(self):
        for malo in (["ES", "IT"], [], "ES", ["es"], [None]):
            with self.assertRaises(rc.ErrorUso, msg=repr(malo)):
                self.norm(countries=malo)
        with self.assertRaises(rc.ErrorUso) as cm:
            self.norm(countries=["US"])
        self.assertIn("política", str(cm.exception))
        with self.assertRaises(rc.ErrorUso):
            self.norm(countries=["BR"])
        self.assertEqual(self.norm(countries=["PL"])["countries"], ["PL"])

    def test_terminos(self):
        self.assertEqual(self.norm(search_terms="x" * rc.TERMINOS_MAX)["search_terms"], "x" * rc.TERMINOS_MAX)
        with self.assertRaises(rc.ErrorUso):
            self.norm(search_terms="x" * (rc.TERMINOS_MAX + 1))
        with self.assertRaises(rc.ErrorUso):
            self.norm(search_terms="   ")
        with self.assertRaises(rc.ErrorUso):
            self.norm(search_terms=None)
        self.assertIsNone(self.norm(search_terms=None, page_ids=[5])["search_terms"])

    def test_page_ids(self):
        self.assertEqual(self.norm(page_ids=[123, "456"])["page_ids"], ["123", "456"])
        self.assertEqual(len(self.norm(page_ids=list(range(1, rc.PAGE_IDS_MAX + 1)))["page_ids"]), rc.PAGE_IDS_MAX)
        for malo in (list(range(1, rc.PAGE_IDS_MAX + 2)), [], ["abc"], [1, 1], [True], 5):
            with self.assertRaises(rc.ErrorUso, msg=repr(malo)):
                self.norm(page_ids=malo)

    def test_estado_claves_y_tipo(self):
        with self.assertRaises(rc.ErrorUso):
            self.norm(ad_active_status="TODOS")
        with self.assertRaises(rc.ErrorUso):
            self.norm(extra=1)
        with self.assertRaises(rc.ErrorUso):
            rc.normalizar_consulta({"search_terms": "a"}, parametros())
        with self.assertRaises(rc.ErrorUso):
            rc.normalizar_consulta("texto", parametros())


# ---------------------------------------------------------------------------
# Cliente: paginación, pausas, errores
# ---------------------------------------------------------------------------

class PruebasCliente(Base):
    def test_una_pagina_arma_bien_la_solicitud(self):
        t = TransporteFalso(ok(pagina([anuncio(1), anuncio(2)])))
        res = self.cliente(t).buscar(CONSULTA)
        self.assertTrue(res.completo)
        self.assertIsNone(res.motivo_corte)
        self.assertEqual(res.paginas, 1)
        self.assertEqual([a["id"] for a in res.anuncios], ["1000000000000001", "1000000000000002"])
        self.assertEqual(len(t.llamadas), 1)
        ll = t.llamadas[0]
        self.assertEqual(ll["url"], "https://graph.facebook.com/v27.0/ads_archive")
        p = ll["parametros"]
        self.assertEqual(p["ad_type"], "ALL")
        self.assertEqual(json.loads(p["ad_reached_countries"]), ["ES"])
        self.assertEqual(p["ad_active_status"], "ACTIVE")
        self.assertEqual(p["search_terms"], "Acceso inmediato en PDF")
        self.assertEqual(p["search_type"], "KEYWORD_UNORDERED")
        self.assertEqual(p["limit"], "50")
        self.assertEqual(p["fields"], ",".join(parametros().campos))
        self.assertEqual(p["access_token"], TOKEN)
        self.assertNotIn("after", p)
        self.assertEqual((ll["tiempo_max_seg"], ll["max_bytes"]), (30, 8_000_000))
        self.assertEqual(self.dormir.pausas, [])  # una sola solicitud: ninguna pausa

    def test_page_ids_van_como_lista_json_de_enteros(self):
        t = TransporteFalso(ok(pagina([])))
        self.cliente(t).buscar({**CONSULTA, "search_terms": None, "page_ids": ["111", "222"]})
        p = t.llamadas[0]["parametros"]
        self.assertEqual(json.loads(p["search_page_ids"]), [111, 222])
        self.assertNotIn("search_terms", p)

    def test_pagina_por_cursor_con_pausas_entre_solicitudes(self):
        t = TransporteFalso(ok(pagina([anuncio(1), anuncio(2)], "CUR1")), ok(pagina([anuncio(3)], "CUR2")),
                            ok(pagina([anuncio(4)])))
        res = self.cliente(t, pausa_ms=1500).buscar(CONSULTA)
        self.assertTrue(res.completo)
        self.assertEqual(res.paginas, 3)
        self.assertEqual(len(res.anuncios), 4)
        self.assertEqual([c["parametros"].get("after") for c in t.llamadas], [None, "CUR1", "CUR2"])
        self.assertEqual(self.dormir.pausas, [1.5, 1.5])  # entre 3 solicitudes hay 2 pausas, de `pausa_ms`

    def test_la_pausa_sale_del_parametro(self):
        t = TransporteFalso(ok(pagina([anuncio(1)], "C1")), ok(pagina([anuncio(2)])))
        self.cliente(t, pausa_ms=250).buscar(CONSULTA)
        self.assertEqual(self.dormir.pausas, [0.25])

    def test_tope_de_paginas_marca_incompleto(self):
        t = TransporteFalso(ok(pagina([anuncio(1)], "C1")), ok(pagina([anuncio(2)], "C2")), ok(pagina([anuncio(3)], "C3")))
        res = self.cliente(t, max_paginas=2).buscar(CONSULTA)
        self.assertFalse(res.completo)
        self.assertEqual(res.motivo_corte, "tope_paginas")
        self.assertEqual(res.paginas, 2)
        self.assertEqual(len(t.llamadas), 2)  # no pide la tercera
        self.assertEqual(len(t.respuestas), 1)

    def test_tope_exacto_sin_pagina_siguiente_es_completo(self):
        t = TransporteFalso(ok(pagina([anuncio(1)], "C1")), ok(pagina([anuncio(2)])))
        res = self.cliente(t, max_paginas=2).buscar(CONSULTA)
        self.assertTrue(res.completo)
        self.assertEqual(res.paginas, 2)

    def test_tope_mas_uno(self):
        t = TransporteFalso(ok(pagina([anuncio(1)], "C1")), ok(pagina([anuncio(2)], "C2")), ok(pagina([anuncio(3)])))
        res = self.cliente(t, max_paginas=3).buscar(CONSULTA)
        self.assertTrue(res.completo)
        self.assertEqual(len(t.llamadas), 3)

    def test_respuesta_vacia(self):
        t = TransporteFalso(ok(pagina([])))
        res = self.cliente(t).buscar(CONSULTA)
        self.assertEqual(res.anuncios, [])
        self.assertTrue(res.completo)
        self.assertEqual(res.paginas, 1)

    def test_respuesta_sin_paging(self):
        t = TransporteFalso(ok(json.dumps({"data": [anuncio(1)]}).encode()))
        res = self.cliente(t).buscar(CONSULTA)
        self.assertTrue(res.completo)
        self.assertEqual(len(res.anuncios), 1)

    def test_pagina_vacia_con_siguiente_sigue(self):
        t = TransporteFalso(ok(pagina([], "C1")), ok(pagina([anuncio(1)])))
        res = self.cliente(t).buscar(CONSULTA)
        self.assertEqual((res.paginas, len(res.anuncios)), (2, 1))

    def test_duplicados_entre_paginas_se_omiten_y_se_cuentan(self):
        t = TransporteFalso(ok(pagina([anuncio(1), anuncio(2)], "C1")), ok(pagina([anuncio(2), anuncio(3)])))
        res = self.cliente(t).buscar(CONSULTA)
        self.assertEqual([a["id"][-1] for a in res.anuncios], ["1", "2", "3"])
        self.assertEqual(res.duplicados, 1)

    def test_el_token_no_queda_en_el_resultado(self):
        t = TransporteFalso(ok(pagina([anuncio(1)], "C1")), ok(pagina([anuncio(2)])))
        res = self.cliente(t).buscar(CONSULTA)
        self.assertNotIn(TOKEN, repr(res))
        self.assertNotIn(TOKEN, json.dumps(res.anuncios))
        self.assertIn("render_ad/?id=1000000000000001", res.anuncios[0]["ad_snapshot_url"])

    def test_next_sin_cursor_after(self):
        cuerpo = json.dumps({"data": [anuncio(1)], "paging": {"next": "https://graph.facebook.com/x"}}).encode()
        with self.assertRaises(rc.ErrorRespuesta):
            self.cliente(TransporteFalso(ok(cuerpo))).buscar(CONSULTA)

    def test_cursor_repetido_corta_con_parcial(self):
        t = TransporteFalso(ok(pagina([anuncio(1)], "C1")), ok(pagina([anuncio(2)], "C1")))
        with self.assertRaises(rc.ErrorRespuesta) as cm:
            self.cliente(t).buscar(CONSULTA)
        self.assertEqual(len(cm.exception.parcial.anuncios), 2)
        self.assertFalse(cm.exception.parcial.completo)

    def test_data_mal_formada(self):
        for cuerpo in (b'{"data": {"a": 1}}', b'{"data": [1, 2]}', b'{"otro": []}', b"[]", b"no es json", b"",
                       b'{"data": [], "x": NaN}', "{\"data\": \"\xff\"}".encode("latin-1")):
            with self.assertRaises(rc.ErrorRespuesta, msg=cuerpo):
                self.cliente(TransporteFalso(ok(cuerpo))).buscar(CONSULTA)

    def test_numeros_decimales_llegan_como_cadena(self):
        cuerpo = json.dumps({"data": [anuncio(1)]}).replace('"eu_total_reach": 12001', '"eu_total_reach": 12001, "ratio": 1.5')
        res = self.cliente(TransporteFalso(ok(cuerpo.encode()))).buscar(CONSULTA)
        self.assertEqual(res.anuncios[0]["ratio"], "1.5")

    # -- errores de la API ---------------------------------------------------
    def test_token_invalido_190_no_se_reintenta(self):
        t = TransporteFalso(error_api(190, f"Error validating access token: {TOKEN} expired"), ok(pagina([])))
        with self.assertRaises(rc.ErrorTokenInvalido) as cm:
            self.cliente(t).buscar(CONSULTA)
        self.assertEqual(len(t.llamadas), 1)
        self.assertEqual(cm.exception.codigo_salida, 4)
        self.assertNotIn(TOKEN, str(cm.exception))  # aunque Meta lo repita en su mensaje
        self.assertIn("190", str(cm.exception))
        self.assertIsNone(cm.exception.parcial)

    def test_token_invalido_con_http_401(self):
        t = TransporteFalso(error_api(190, estado=401))
        with self.assertRaises(rc.ErrorTokenInvalido):
            self.cliente(t).buscar(CONSULTA)

    def test_sin_acceso_es_error_de_acceso(self):
        for r in (error_api(10, "Application does not have permission for this action"), error_api(200, estado=403),
                  rc.Respuesta(403, b"")):
            with self.assertRaises(rc.ErrorAcceso, msg=repr(r)) as cm:
                self.cliente(TransporteFalso(r)).buscar(CONSULTA)
            self.assertIn("facebook.com/ID", str(cm.exception))

    def test_limite_de_tasa_613_sin_reintentos_se_detiene(self):
        t = TransporteFalso(error_api(613, "Calls to this api have exceeded the rate limit.", "OAuthException"),
                            ok(pagina([])))
        with self.assertRaises(rc.ErrorTasa) as cm:
            self.cliente(t, reintentos_tasa=0).buscar(CONSULTA)
        self.assertEqual(len(t.llamadas), 1)
        self.assertEqual(self.dormir.pausas, [])
        self.assertEqual(cm.exception.codigo_salida, 4)

    def test_el_cliente_pide_permiso_antes_de_enviar_y_anota_despues(self):
        eventos = []

        class T(TransporteFalso):
            def solicitar(self, *a, **k):
                eventos.append(("enviar",))
                return super().solicitar(*a, **k)

        t = T(ok(pagina([anuncio(1)], "C1")), ok(pagina([anuncio(2)])))
        self.cliente(t, FrenosFalsos(eventos)).buscar(CONSULTA)
        self.assertEqual(eventos, [("antes", 1), ("enviar",), ("despues", "ok"),
                                   ("antes", 2), ("enviar",), ("despues", "ok")])

    def test_si_los_frenos_dicen_no_no_se_envia_y_se_conserva_lo_recibido(self):
        t = TransporteFalso(ok(pagina([anuncio(1)], "C1")), ok(pagina([anuncio(2)])))
        with self.assertRaises(rc.ErrorTope) as cm:
            self.cliente(t, FrenosFalsos(falla_en=2)).buscar(CONSULTA)
        self.assertEqual(len(t.llamadas), 1)
        self.assertEqual(len(cm.exception.parcial.anuncios), 1)
        self.assertEqual(cm.exception.parcial.motivo_corte, "tope")

    def test_tasa_frena_y_no_reintenta(self):
        eventos = []
        t = TransporteFalso(error_api(613), ok(pagina([anuncio(1)])))
        with self.assertRaises(rc.ErrorTasa):
            self.cliente(t, FrenosFalsos(eventos)).buscar(CONSULTA)
        self.assertEqual(len(t.llamadas), 1)
        self.assertEqual([e[0] for e in eventos], ["antes", "despues", "frenar"])
        self.assertEqual(eventos[1], ("despues", "tasa"))
        self.assertEqual(self.dormir.pausas, [])

    def test_http_429_y_otros_codigos_de_tasa(self):
        for r in (rc.Respuesta(429, b"{}"), error_api(4), error_api(17), error_api(341)):
            with self.assertRaises(rc.ErrorTasa, msg=repr(r)):
                self.cliente(TransporteFalso(r), reintentos_tasa=0).buscar(CONSULTA)

    def test_tasa_a_mitad_de_camino_conserva_lo_recibido(self):
        t = TransporteFalso(ok(pagina([anuncio(1), anuncio(2)], "C1")), error_api(613))
        with self.assertRaises(rc.ErrorTasa) as cm:
            self.cliente(t, reintentos_tasa=0).buscar(CONSULTA)
        parcial = cm.exception.parcial
        self.assertEqual(len(parcial.anuncios), 2)
        self.assertFalse(parcial.completo)
        self.assertEqual(parcial.motivo_corte, "error_tasa")
        self.assertEqual(parcial.paginas, 1)

    def test_parametro_invalido_100(self):
        with self.assertRaises(rc.ErrorRespuesta) as cm:
            self.cliente(TransporteFalso(error_api(100, "Invalid parameter", "GraphMethodException"))).buscar(CONSULTA)
        self.assertIn("ruta_c_campos", str(cm.exception))

    def test_errores_de_servicio(self):
        for r in (rc.Respuesta(500, b"<html>boom</html>"), rc.Respuesta(503, b""), error_api(2, estado=500),
                  ErrorServicioDeRed()):
            with self.assertRaises(rc.ErrorServicio, msg=repr(r)):
                self.cliente(TransporteFalso(r)).buscar(CONSULTA)

    def test_estado_inesperado_sin_error_json(self):
        with self.assertRaises(rc.ErrorRespuesta):
            self.cliente(TransporteFalso(rc.Respuesta(302, b""))).buscar(CONSULTA)

    def test_error_sin_codigo_conocido(self):
        with self.assertRaises(rc.ErrorRespuesta):
            self.cliente(TransporteFalso(error_api(9999))).buscar(CONSULTA)

    def test_codigo_como_cadena(self):
        r = rc.Respuesta(400, json.dumps({"error": {"message": "x", "code": "190"}}).encode())
        with self.assertRaises(rc.ErrorTokenInvalido):
            self.cliente(TransporteFalso(r)).buscar(CONSULTA)

    def test_ningun_error_filtra_el_token(self):
        respuestas = [error_api(190, f"token {TOKEN}"), error_api(613, f"url ?access_token={TOKEN}&x=1"),
                      error_api(100, f"bad {TOKEN}"), error_api(10, f"{TOKEN}"), error_api(2, f"{TOKEN}", estado=500),
                      error_api(9999, f"{TOKEN}")]
        for r in respuestas:
            with self.assertRaises(rc.ErrorFabrica) as cm:
                self.cliente(TransporteFalso(r), reintentos_tasa=0).buscar(CONSULTA)
            self.assertNotIn(TOKEN, str(cm.exception))
            self.assertNotIn("access_token=" + TOKEN, str(cm.exception))


def ErrorServicioDeRed():
    return rc.ErrorServicio("fallo de red al llamar a la API (TimeoutError)")


# ---------------------------------------------------------------------------
# Fechas
# ---------------------------------------------------------------------------

class PruebasFechas(unittest.TestCase):
    def epoch(self, *a):
        return int(datetime(*a, tzinfo=timezone.utc).timestamp())

    def test_formatos_de_la_api(self):
        esperado = self.epoch(2026, 11, 5, 10, 30, 15)
        for texto in ("2026-11-05T10:30:15+0000", "2026-11-05T10:30:15Z", "2026-11-05T10:30:15+00:00",
                      "2026-11-05T10:30:15", "2026-11-05 10:30:15", "2026-11-05T10:30:15.000Z",
                      "2026-11-05T12:30:15+02:00", "2026-11-05T05:30:15-0500"):
            self.assertEqual(rc.iso_a_epoch(texto), esperado, texto)

    def test_solo_fecha_es_medianoche_utc(self):
        self.assertEqual(rc.iso_a_epoch("2026-11-05"), self.epoch(2026, 11, 5))
        self.assertEqual(rc.iso_a_epoch("2026-11-05T10:30"), self.epoch(2026, 11, 5, 10, 30))

    def test_es_entero_en_segundos(self):
        v = rc.iso_a_epoch("2026-11-05")
        self.assertIsInstance(v, int)
        self.assertLess(v, comun.EPOCH_S_MAX_EXCLUSIVO)

    def test_invalidas(self):
        for malo in ("", "ayer", "05/11/2026", "2026-13-01", "2026-02-30", "2026-11-05T25:00:00Z",
                     "2026-11-05T10:00:00+25:00", "1969-12-31", 1793942244, None, ["2026-11-05"], "2026-11-05Z"):
            with self.assertRaises(rc.ErrorValidacion, msg=repr(malo)):
                rc.iso_a_epoch(malo)


# ---------------------------------------------------------------------------
# Conversión al crudo
# ---------------------------------------------------------------------------

def resultado_de(anuncios: list[dict], **cambios) -> rc.Resultado:
    base = dict(consulta=rc.normalizar_consulta(CONSULTA, parametros()), anuncios=[_sin_token(a) for a in anuncios],
                paginas=1, completo=True, motivo_corte=None, duplicados=0)
    base.update(cambios)
    return rc.Resultado(**base)


def _sin_token(a: dict) -> dict:
    a = dict(a)
    if "ad_snapshot_url" in a:
        a["ad_snapshot_url"] = rc.quitar_token_de_url(a["ad_snapshot_url"])
    return a


def convertir(anuncios, **kw):
    r = kw.pop("resultado", None) or resultado_de(anuncios)
    return rc.convertir(r, corrida_id=CORRIDA, qid=kw.pop("qid", "es-acceso-inmediato-pdf"), capturado_en=CAPTURA,
                        parametros=kw.pop("parametros", parametros()), **kw)


class PruebasConversion(unittest.TestCase):
    def test_anuncio_comercial_de_la_ue(self):
        (paq,) = convertir([anuncio(1)])
        crudo = paq.crudo
        self.assertEqual(crudo["ruta"], "C")
        self.assertEqual(crudo["qid"], "es-acceso-inmediato-pdf")
        self.assertEqual(crudo["capturado_en"], CAPTURA)
        self.assertEqual(crudo["consulta"], {"search_terms": "Acceso inmediato en PDF", "countries": ["ES"],
                                             "ad_active_status": "ACTIVE", "limit": 50, "page_ids": None})
        (ad,) = crudo["ads"]
        self.assertEqual(ad["id"], "1000000000000001")
        self.assertEqual(ad["page_id"], "1431294770063493")  # validar_crudo normaliza page_id a cadena de dígitos
        self.assertEqual(ad["page_name"], "Página 1")
        self.assertEqual(ad["ad_creative_link_title"], "Guía práctica 1")
        self.assertEqual(ad["ad_delivery_start_time"], int(datetime(2026, 11, 5, tzinfo=timezone.utc).timestamp()))
        self.assertEqual(ad["ad_creation_time"], int(datetime(2026, 11, 4, tzinfo=timezone.utc).timestamp()))
        self.assertIsInstance(ad["ad_delivery_start_time"], int)
        # id <-> ad_snapshot_url del contrato, no la URL de la API (que lleva el token)
        self.assertEqual(ad["ad_snapshot_url"], "https://www.facebook.com/ads/library/?id=1000000000000001")
        self.assertTrue(ad["ad_snapshot_url"].endswith(f"?id={ad['id']}"))
        # moneda: la API no la da en anuncios comerciales -> XXX, nunca una moneda inventada
        self.assertEqual(ad["currency"], rc.MONEDA_SIN_DATO)
        self.assertEqual(crudo["estimated_total_count"], 1)

    def test_pasa_el_validador_del_contrato(self):
        for paq in convertir([anuncio(n) for n in range(1, 8)]):
            self.assertEqual(comun.validar_crudo(paq.crudo), paq.crudo)

    def test_moneda_de_la_api_si_viene(self):
        (paq,) = convertir([anuncio(1, currency="EUR"), anuncio(2, currency="BRL")])
        self.assertEqual([a["currency"] for a in paq.crudo["ads"]], ["EUR", "BRL"])
        self.assertEqual([paq.extra["anuncios"][a["id"]]["moneda_origen"] for a in paq.crudo["ads"]], ["api", "api"])

    def test_moneda_invalida(self):
        with self.assertRaises(rc.ErrorValidacion):
            convertir([anuncio(1, currency="euro")])

    def test_sin_moneda_queda_marcado_en_el_extra(self):
        (paq,) = convertir([anuncio(1)])
        self.assertEqual(paq.extra["anuncios"]["1000000000000001"]["moneda_origen"], "sin_dato")

    def test_sin_titulo_de_enlace_es_cadena_vacia(self):
        (paq,) = convertir([anuncio(1, ad_creative_link_titles=None)])  # la API omite el campo
        self.assertEqual(paq.crudo["ads"][0]["ad_creative_link_title"], "")
        self.assertIsNone(paq.extra["anuncios"]["1000000000000001"]["titulos"])

    def test_varios_titulos_toma_el_primero_no_vacio_y_guarda_todos(self):
        (paq,) = convertir([anuncio(1, ad_creative_link_titles=["", "Segundo", "Tercero"])])
        self.assertEqual(paq.crudo["ads"][0]["ad_creative_link_title"], "Segundo")
        self.assertEqual(paq.extra["anuncios"]["1000000000000001"]["titulos"], ["", "Segundo", "Tercero"])

    def test_texto_se_copia_textual(self):
        raro = "  ⭐⭐ Guía «ñandú»  <script>alert(1)</script> "
        (paq,) = convertir([anuncio(1, ad_creative_link_titles=[raro], page_name=raro)])
        self.assertEqual(paq.crudo["ads"][0]["ad_creative_link_title"], raro)
        self.assertEqual(paq.crudo["ads"][0]["page_name"], raro)

    def test_el_extra_guarda_lo_que_el_contrato_no_tiene(self):
        a = anuncio(1, ad_delivery_stop_time="2026-12-01", languages=["es"],
                    ad_creative_link_descriptions=["desc"], ad_creative_link_captions=["cap"],
                    target_ages=["18", "65"], target_gender="All",
                    target_locations=[{"name": "Madrid", "type": "cities", "excluded": False}],
                    beneficiary_payers=[{"beneficiary": "Empresa SL", "payer": "Empresa SL"}],
                    total_reach_by_location=[{"key": "EU", "value": 12001}])
        (paq,) = convertir([a])
        e = paq.extra["anuncios"]["1000000000000001"]
        self.assertEqual(e["cuerpos"], ["Descarga ahora la guía 1. Acceso inmediato en PDF, pago único."])
        self.assertEqual(e["alcance_ue"], 12001)
        self.assertEqual(e["plataformas"], ["facebook", "instagram"])
        self.assertEqual(e["idiomas"], ["es"])
        self.assertEqual(e["inicio_original"], "2026-11-05")
        self.assertEqual(e["fin"], int(datetime(2026, 12, 1, tzinfo=timezone.utc).timestamp()))
        self.assertEqual(e["edades_objetivo"], ["18", "65"])
        self.assertEqual(e["genero_objetivo"], "All")
        self.assertEqual(e["ubicaciones_objetivo"][0]["name"], "Madrid")
        self.assertEqual(e["beneficiarios_pagadores"][0]["payer"], "Empresa SL")
        self.assertEqual(e["alcance_por_ubicacion"], [{"key": "EU", "value": 12001}])
        self.assertEqual(paq.extra["ruta"], "C")
        self.assertEqual(paq.extra["version_api"], "v27.0")
        self.assertEqual(paq.extra["qid"], paq.crudo["qid"])
        self.assertEqual(paq.extra["consulta_api"]["ad_type"], "ALL")
        self.assertEqual(set(paq.extra["anuncios"]), {a["id"] for a in paq.crudo["ads"]})

    def test_extra_no_cambia_el_esquema_del_crudo(self):
        (paq,) = convertir([anuncio(1)])
        self.assertEqual(set(paq.crudo), set(comun.CAMPOS_CRUDO))
        self.assertEqual(set(paq.crudo["ads"][0]), set(comun.CAMPOS_ANUNCIO) | {"ad_creation_time"})

    def test_alcance_ue_como_cadena_o_invalido(self):
        (paq,) = convertir([anuncio(1, eu_total_reach="5000")])
        self.assertEqual(paq.extra["anuncios"]["1000000000000001"]["alcance_ue"], 5000)
        for malo in (-1, 1.5, "mucho", True, [5]):
            with self.assertRaises(rc.ErrorValidacion, msg=repr(malo)):
                convertir([anuncio(1, eu_total_reach=malo)])

    def test_sin_flotantes_ni_token_en_lo_persistido(self):
        (paq,) = convertir([anuncio(1, total_reach_by_location=[{"key": "EU", "value": "1.5"}])])
        for doc in (paq.crudo, paq.extra):
            texto = json.dumps(doc, ensure_ascii=False)
            self.assertNotIn(TOKEN, texto)
            self.assertNotIn("access_token", texto)
            self.assertNotIn("render_ad", texto)
        with self.assertRaises(rc.ErrorValidacion):
            convertir([anuncio(1, total_reach_by_location=[{"key": "EU", "value": 1.5}])])

    def test_resultado_vacio_es_un_crudo_valido(self):
        (paq,) = convertir([])
        self.assertEqual(paq.crudo["ads"], [])
        self.assertEqual(paq.crudo["estimated_total_count"], 0)
        self.assertEqual(paq.extra["anuncios"], {})
        self.assertEqual(paq.extra["fragmento"], {"numero": 1, "de": 1})

    # -- campos faltantes / corruptos ---------------------------------------
    def test_campo_faltante_falla_cerrado(self):
        for campo in ("id", "page_id", "page_name", "ad_delivery_start_time", "ad_snapshot_url"):
            a = anuncio(1)
            del a[campo]
            with self.assertRaises(rc.ErrorValidacion, msg=campo) as cm:
                convertir([a])
            self.assertIn("anuncio #0", str(cm.exception))

    def test_campos_con_tipo_raro(self):
        casos = {"id": "12ab", "page_id": "x", "page_name": 5, "ad_delivery_start_time": "ayer",
                 "ad_creative_link_titles": "no-es-lista", "ad_creative_bodies": [1], "ad_creation_time": "mal",
                 "ad_delivery_stop_time": "mal", "publisher_platforms": "facebook"}
        for campo, valor in casos.items():
            with self.assertRaises(rc.ErrorValidacion, msg=campo):
                convertir([anuncio(1, **{campo: valor})])

    def test_id_y_url_de_la_api_no_coinciden(self):
        mal = anuncio(1, ad_snapshot_url="https://www.facebook.com/ads/archive/render_ad/?id=999")
        with self.assertRaises(rc.ErrorValidacion) as cm:
            convertir([mal])
        self.assertIn("integridad", str(cm.exception))
        sin_id = anuncio(1, ad_snapshot_url="https://www.facebook.com/ads/archive/render_ad/")
        with self.assertRaises(rc.ErrorValidacion):
            convertir([sin_id])

    def test_id_repetido_en_el_resultado_es_error_del_contrato(self):
        with self.assertRaises(rc.ErrorValidacion):
            convertir([anuncio(1), anuncio(1)])

    def test_descartar_invalidos_los_anota_sin_inventar(self):
        malo = anuncio(2)
        del malo["page_name"]
        (paq,) = convertir([anuncio(1), malo, anuncio(3)], descartar_invalidos=True)
        self.assertEqual([a["id"][-1] for a in paq.crudo["ads"]], ["1", "3"])
        desc = paq.extra["paginacion"]["descartados"]
        self.assertEqual([d["id"] for d in desc], ["1000000000000002"])
        self.assertIn("page_name", desc[0]["motivo"])

    def test_ids_y_qid_invalidos(self):
        with self.assertRaises(rc.ErrorUso):
            convertir([], qid="Con Espacios")
        with self.assertRaises(rc.ErrorUso):
            rc.convertir(resultado_de([]), corrida_id="ayer", qid="x", capturado_en=CAPTURA, parametros=parametros())

    # -- partición en archivos de <= 50 --------------------------------------
    def test_exactamente_el_tope_cabe_en_un_archivo(self):
        paquetes = convertir([anuncio(n) for n in range(1, 51)])
        self.assertEqual(len(paquetes), 1)
        self.assertEqual(len(paquetes[0].crudo["ads"]), 50)
        self.assertEqual(paquetes[0].crudo["qid"], "es-acceso-inmediato-pdf")

    def test_tope_mas_uno_parte_en_dos(self):
        paquetes = convertir([anuncio(n) for n in range(1, 52)])
        self.assertEqual([p.qid for p in paquetes], ["es-acceso-inmediato-pdf-c01", "es-acceso-inmediato-pdf-c02"])
        self.assertEqual([len(p.crudo["ads"]) for p in paquetes], [50, 1])

    def test_ciento_veinte_en_tres_archivos(self):
        paquetes = convertir([anuncio(n) for n in range(1, 121)])
        self.assertEqual([len(p.crudo["ads"]) for p in paquetes], [50, 50, 20])
        ids = [a["id"] for p in paquetes for a in p.crudo["ads"]]
        self.assertEqual(len(ids), 120)
        self.assertEqual(len(set(ids)), 120)
        for i, p in enumerate(paquetes, start=1):
            self.assertLessEqual(len(p.crudo["ads"]), p.crudo["consulta"]["limit"])
            self.assertLessEqual(p.crudo["consulta"]["limit"], comun.LIMITE_MAX_CONECTOR)
            self.assertEqual(p.extra["fragmento"], {"numero": i, "de": 3})
            self.assertEqual(p.extra["qid_origen"], "es-acceso-inmediato-pdf")
            self.assertEqual(set(p.extra["anuncios"]), {a["id"] for a in p.crudo["ads"]})
            comun.validar_crudo(p.crudo)

    def test_el_tamano_de_archivo_sale_del_parametro(self):
        r = resultado_de([anuncio(n) for n in range(1, 8)])
        r.consulta = rc.normalizar_consulta(CONSULTA, parametros(anuncios_por_archivo=3))
        paquetes = rc.convertir(r, corrida_id=CORRIDA, qid="es-x", capturado_en=CAPTURA,
                                parametros=parametros(anuncios_por_archivo=3))
        self.assertEqual([len(p.crudo["ads"]) for p in paquetes], [3, 3, 1])
        self.assertEqual({p.crudo["consulta"]["limit"] for p in paquetes}, {3})

    def test_total_estimado_segun_este_completo(self):
        completo = convertir([anuncio(n) for n in range(1, 4)])
        self.assertEqual(completo[0].crudo["estimated_total_count"], 3)
        self.assertTrue(completo[0].extra["paginacion"]["completo"])
        cortado = convertir([anuncio(n) for n in range(1, 4)],
                            resultado=resultado_de([anuncio(n) for n in range(1, 4)], completo=False,
                                                   motivo_corte="tope_paginas"))
        self.assertIsNone(cortado[0].crudo["estimated_total_count"])
        self.assertFalse(cortado[0].extra["paginacion"]["completo"])
        self.assertEqual(cortado[0].extra["paginacion"]["motivo_corte"], "tope_paginas")

    def test_incompleto_el_ultimo_archivo_se_ve_como_piso(self):
        """La ingesta marca «truncada» si len(ads) >= limit y el total es null: el último archivo de un resultado
        cortado lo declara así aunque tenga menos anuncios que el tamaño de archivo."""
        r = resultado_de([anuncio(n) for n in range(1, 73)], completo=False, motivo_corte="tope_paginas")
        paquetes = convertir([], resultado=r)
        self.assertEqual([len(p.crudo["ads"]) for p in paquetes], [50, 22])
        for p in paquetes:
            c = p.crudo
            self.assertIsNone(c["estimated_total_count"])
            self.assertGreaterEqual(len(c["ads"]), c["consulta"]["limit"])
        self.assertEqual(paquetes[-1].crudo["consulta"]["limit"], 22)
        # completo: nunca parece truncado
        for p in convertir([], resultado=resultado_de([anuncio(n) for n in range(1, 73)])):
            c = p.crudo
            self.assertEqual(c["estimated_total_count"], len(c["ads"]))

    def test_paginacion_en_el_extra(self):
        r = resultado_de([anuncio(1), anuncio(2)], paginas=4, duplicados=3)
        (paq,) = convertir([], resultado=r)
        self.assertEqual(paq.extra["paginacion"]["paginas_leidas"], 4)
        self.assertEqual(paq.extra["paginacion"]["duplicados_omitidos"], 3)
        self.assertEqual(paq.extra["paginacion"]["anuncios_recibidos"], 5)


# ---------------------------------------------------------------------------
# Escritura y orquestación (raíz temporal; sin tocar empresa/ real)
# ---------------------------------------------------------------------------

class PruebasEscritura(Base):
    def barrer(self, transporte, raiz, **kw):
        return rc.barrer_consulta(kw.pop("consulta", CONSULTA), corrida_id=CORRIDA, qid=kw.pop("qid", "es-acceso-inmediato-pdf"),
                                  transporte=transporte, parametros=kw.pop("parametros", parametros()),
                                  entorno=ENTORNO, raiz=raiz,
                                  ahora=lambda: datetime(2026, 11, 6, 5, 50, 12, tzinfo=timezone.utc),
                                  dormir=self.dormir, **kw)

    def test_de_punta_a_punta(self):
        t = TransporteFalso(ok(pagina([anuncio(n) for n in range(1, 4)], "C1")),
                            ok(pagina([anuncio(n) for n in range(4, 6)])))
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d)
            rutas = self.barrer(t, raiz)
            carpeta = raiz / "empresa" / "barrido" / "crudo" / CORRIDA
            self.assertEqual(rutas, [carpeta / "es-acceso-inmediato-pdf.json",
                                     carpeta / "es-acceso-inmediato-pdf.extra.json"])
            crudo = comun.leer_crudo(rutas[0])  # valida contrato + ubicación + nombre
            self.assertEqual(crudo["ruta"], "C")
            self.assertEqual(crudo["capturado_en"], "2026-11-06T05:50:12Z")
            self.assertEqual(len(crudo["ads"]), 5)
            extra = json.loads(rutas[1].read_text(encoding="utf-8"))
            self.assertEqual(extra["paginacion"]["paginas_leidas"], 2)
            self.assertEqual(len(extra["anuncios"]), 5)
            # el token no está en NINGÚN archivo escrito
            for archivo in carpeta.iterdir():
                self.assertNotIn(TOKEN, archivo.read_text(encoding="utf-8"))
            self.assertEqual(len(t.llamadas), 2)
            self.assertEqual(self.dormir.pausas, [1.5])

    def test_no_sobrescribe(self):
        with tempfile.TemporaryDirectory() as d:
            self.barrer(TransporteFalso(ok(pagina([anuncio(1)]))), Path(d))
            antes = sorted(p.name for p in (Path(d) / "empresa" / "barrido" / "crudo" / CORRIDA).iterdir())
            with self.assertRaises(rc.ErrorUso):
                self.barrer(TransporteFalso(ok(pagina([anuncio(2)]))), Path(d))
            despues = sorted(p.name for p in (Path(d) / "empresa" / "barrido" / "crudo" / CORRIDA).iterdir())
            self.assertEqual(antes, despues)

    def test_si_un_destino_posterior_existe_no_se_escribe_ninguno(self):
        t = TransporteFalso(ok(pagina([anuncio(n) for n in range(1, 61)])))
        with tempfile.TemporaryDirectory() as d:
            carpeta = Path(d) / "empresa" / "barrido" / "crudo" / CORRIDA
            carpeta.mkdir(parents=True)
            (carpeta / "es-acceso-inmediato-pdf-c02.json").write_text("{}", encoding="utf-8")
            with self.assertRaises(rc.ErrorUso):
                self.barrer(t, Path(d))
            self.assertEqual([p.name for p in carpeta.iterdir()], ["es-acceso-inmediato-pdf-c02.json"])

    def test_varios_archivos_cuando_son_mas_de_50(self):
        t = TransporteFalso(ok(pagina([anuncio(n) for n in range(1, 61)])))
        with tempfile.TemporaryDirectory() as d:
            rutas = self.barrer(t, Path(d))
            self.assertEqual([r.name for r in rutas], ["es-acceso-inmediato-pdf-c01.json",
                                                       "es-acceso-inmediato-pdf-c01.extra.json",
                                                       "es-acceso-inmediato-pdf-c02.json",
                                                       "es-acceso-inmediato-pdf-c02.extra.json"])
            self.assertEqual([len(comun.leer_crudo(r)["ads"]) for r in rutas if not r.name.endswith(".extra.json")],
                             [50, 10])

    def test_respuesta_vacia_escribe_un_crudo_valido(self):
        with tempfile.TemporaryDirectory() as d:
            rutas = self.barrer(TransporteFalso(ok(pagina([]))), Path(d))
            crudo = comun.leer_crudo(rutas[0])
            self.assertEqual((crudo["ads"], crudo["estimated_total_count"]), ([], 0))

    def test_tasa_a_mitad_escribe_lo_recibido_y_relanza(self):
        t = TransporteFalso(ok(pagina([anuncio(1), anuncio(2)], "C1")), error_api(613))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(rc.ErrorTasa) as cm:
                self.barrer(t, Path(d), parametros=parametros(reintentos_tasa=0))
            archivos = cm.exception.archivos
            self.assertEqual(len(archivos), 2)
            crudo = comun.leer_crudo(archivos[0])
            self.assertEqual(len(crudo["ads"]), 2)
            self.assertIsNone(crudo["estimated_total_count"])
            extra = json.loads(archivos[1].read_text(encoding="utf-8"))
            self.assertFalse(extra["paginacion"]["completo"])
            self.assertEqual(extra["paginacion"]["motivo_corte"], "error_tasa")
            for a in archivos:
                self.assertNotIn(TOKEN, a.read_text(encoding="utf-8"))

    def test_error_en_la_primera_pagina_no_escribe_nada(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(rc.ErrorTokenInvalido) as cm:
                self.barrer(TransporteFalso(error_api(190)), Path(d))
            self.assertEqual(cm.exception.archivos, ())
            self.assertFalse((Path(d) / "empresa" / "barrido" / "crudo").exists())  # solo queda el registro de la solicitud

    def test_anuncio_invalido_aborta_antes_de_escribir(self):
        malo = anuncio(2)
        del malo["page_name"]
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(rc.ErrorValidacion):
                self.barrer(TransporteFalso(ok(pagina([anuncio(1), malo]))), Path(d))
            self.assertFalse((Path(d) / "empresa" / "barrido" / "crudo").exists())

    def test_consulta_invalida_o_ids_invalidos_no_hacen_solicitudes(self):
        t = TransporteFalso()
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(rc.ErrorUso):
                self.barrer(t, Path(d), consulta={**CONSULTA, "countries": ["US"]})
            with self.assertRaises(rc.ErrorUso):
                self.barrer(t, Path(d), qid="Mal Qid")
            with self.assertRaises(rc.ErrorUso):
                rc.barrer_consulta(CONSULTA, corrida_id="../x", qid="ok", transporte=t, parametros=parametros(),
                                   entorno=ENTORNO, raiz=Path(d))
        self.assertEqual(t.llamadas, [])

    def test_un_token_en_el_contenido_se_rechaza_antes_de_escribir(self):
        malo = anuncio(1, ad_creative_bodies=[f"mira https://x.com/?access_token={TOKEN}"])
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(rc.ErrorValidacion) as cm:
                self.barrer(TransporteFalso(ok(pagina([malo]))), Path(d))
            self.assertNotIn(TOKEN, str(cm.exception))
            carpeta = Path(d) / "empresa" / "barrido" / "crudo" / CORRIDA
            self.assertEqual(list(carpeta.glob("*")) if carpeta.exists() else [], [])

    def test_los_extra_no_se_confunden_con_crudos(self):
        """PEDIDO a B0: `listar_crudos` debe excluir `*.extra.json`. Si aún no lo hace, la prueba se salta y lo dice."""
        with tempfile.TemporaryDirectory() as d:
            self.barrer(TransporteFalso(ok(pagina([anuncio(1)]))), Path(d))
            nombres = [p.name for p in comun.listar_crudos(CORRIDA, Path(d))]
            if any(n.endswith(".extra.json") for n in nombres):
                self.skipTest("PEDIDO pendiente a B0: comun.listar_crudos devuelve los *.extra.json como si fueran crudos")
            self.assertEqual(nombres, ["es-acceso-inmediato-pdf.json"])


# ---------------------------------------------------------------------------
# Revisión de seguridad (m4): frenos, topes, registro, tasa = freno, secretos
# ---------------------------------------------------------------------------

AHORA = datetime(2026, 11, 6, 5, 50, 12, tzinfo=timezone.utc)


def poner(raiz: Path, relativo: str, contenido: str = "x") -> Path:
    ruta = Path(raiz) / relativo
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def lineas(ruta: Path) -> list:
    return [json.loads(x) for x in ruta.read_text(encoding="utf-8").splitlines() if x.strip()]


def sembrar(raiz: Path, corrida: str, *, hoy: int = 0, ayer: int = 0, ilegibles: int = 0, resultados: int = 0) -> Path:
    """Registro de otra corrida: `hoy` solicitudes de hoy (UTC), `ayer` de ayer, líneas rotas y líneas de resultado."""
    reg = Path(raiz) / "empresa" / "barrido" / "ruta_c" / f"{corrida}.jsonl"
    reg.parent.mkdir(parents=True, exist_ok=True)
    filas = [json.dumps({"ts": "2026-11-06T01:00:00Z", "tipo": "solicitud"}) for _ in range(hoy)]
    filas += [json.dumps({"ts": "2026-11-05T23:59:59Z", "tipo": "solicitud"}) for _ in range(ayer)]
    filas += ["esto no es json" for _ in range(ilegibles)]
    filas += [json.dumps({"ts": "2026-11-06T01:00:01Z", "tipo": "resultado", "estado": "ok"}) for _ in range(resultados)]
    reg.write_text("\n".join(filas) + "\n", encoding="utf-8")
    return reg


class PruebasFrenos(Base):
    def barrer(self, transporte, raiz, **kw):
        kw.setdefault("entorno", ENTORNO)
        return rc.barrer_consulta(
            kw.pop("consulta", CONSULTA), corrida_id=kw.pop("corrida_id", CORRIDA), qid=kw.pop("qid", "es-acceso"),
            transporte=transporte, parametros=kw.pop("parametros", parametros()), raiz=Path(raiz),
            ahora=kw.pop("ahora", lambda: AHORA), dormir=kw.pop("dormir", self.dormir), **kw)

    def registro(self, raiz, corrida=CORRIDA) -> Path:
        return Path(raiz) / "empresa" / "barrido" / "ruta_c" / f"{corrida}.jsonl"

    def paginas(self, n: int) -> list:
        """n páginas con `next` salvo la última."""
        return [ok(pagina([anuncio(k)], f"CUR{k}" if k < n else None)) for k in range(1, n + 1)]

    # -- empresa/PAUSA y freno compartido ------------------------------------
    def test_pausa_detiene_todo_antes_de_nada(self):
        t = TransporteFalso(ok(pagina([anuncio(1)])))
        with tempfile.TemporaryDirectory() as d:
            poner(d, "empresa/PAUSA")
            with self.assertRaises(rc.ErrorBloqueado) as cm:
                self.barrer(t, d, entorno={})  # ni siquiera llega a pedir el token
            self.assertIn("PAUSA", str(cm.exception))
            self.assertEqual(cm.exception.codigo_salida, 4)
            self.assertEqual(t.llamadas, [])
            self.assertFalse((Path(d) / "empresa" / "barrido").exists())

    def test_freno_compartido_existente_no_hace_nada(self):
        t = TransporteFalso(ok(pagina([anuncio(1)])))
        info = json.dumps({"ts": "2026-11-06T06:03:43Z", "ad_id": "busqueda:x", "motivo": "HTTP 403 (Document)"})
        for contenido in (info, "{{ no es json", ""):  # ilegible = sigue frenado (falla cerrado)
            with tempfile.TemporaryDirectory() as d:
                poner(d, "empresa/captura/freno.json", contenido)
                with self.assertRaises(rc.ErrorBloqueado) as cm:
                    self.barrer(t, d)
                self.assertEqual(cm.exception.codigo_salida, 4)
                self.assertIn("freno", str(cm.exception))
                self.assertEqual(t.llamadas, [])
                self.assertFalse((Path(d) / "empresa" / "barrido").exists())
                self.assertEqual((Path(d) / "empresa" / "captura" / "freno.json").read_text(encoding="utf-8"), contenido)

    def test_freno_que_aparece_a_mitad_conserva_lo_recibido(self):
        t = TransporteFalso(*self.paginas(3))
        with tempfile.TemporaryDirectory() as d:
            def al_dormir():
                poner(d, "empresa/captura/freno.json", json.dumps({"ts": "2026-11-06T05:51:00Z", "motivo": "web"}))
            dormir = Dormir()
            dormir.efecto = al_dormir
            with self.assertRaises(rc.ErrorBloqueado) as cm:
                self.barrer(t, d, dormir=dormir)
            self.assertEqual(len(t.llamadas), 1)  # la segunda página no se pidió
            self.assertEqual(len(cm.exception.parcial.anuncios), 1)
            self.assertEqual(len(cm.exception.archivos), 2)
            self.assertEqual(len(comun.leer_crudo(cm.exception.archivos[0])["ads"]), 1)

    # -- tasa = freno ---------------------------------------------------------
    def test_limite_de_tasa_es_freno_sin_reintento_ni_espera(self):
        t = TransporteFalso(error_api(613, "Calls to this api have exceeded the rate limit."), ok(pagina([anuncio(1)])))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(rc.ErrorTasa) as cm:
                self.barrer(t, d)
            self.assertEqual(len(t.llamadas), 1)
            self.assertEqual(self.dormir.pausas, [])  # ninguna espera de 120 s
            self.assertEqual(cm.exception.codigo_salida, 4)

    def test_limite_de_tasa_escribe_el_freno_compartido_y_la_siguiente_no_hace_nada(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(rc.ErrorTasa):
                self.barrer(TransporteFalso(error_api(613, f"url ?access_token={TOKEN}")), d)
            ruta = Path(d) / "empresa" / "captura" / "freno.json"
            freno = json.loads(ruta.read_text(encoding="utf-8"))
            self.assertEqual(set(freno), {"ts", "ad_id", "motivo"})
            self.assertEqual(freno["ts"], "2026-11-06T05:50:12Z")
            self.assertEqual(freno["ad_id"], "ruta_c:es-acceso")
            self.assertNotIn(TOKEN, ruta.read_text(encoding="utf-8"))
            antes = ruta.read_text(encoding="utf-8")
            t2 = TransporteFalso(ok(pagina([anuncio(1)])))
            with self.assertRaises(rc.ErrorBloqueado):
                self.barrer(t2, d, qid="otra")
            self.assertEqual(t2.llamadas, [])
            self.assertEqual(ruta.read_text(encoding="utf-8"), antes)

    def test_token_o_acceso_no_escriben_el_freno_compartido(self):
        for r in (error_api(190), error_api(10), rc.Respuesta(500, b"")):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(rc.ErrorFabrica):
                    self.barrer(TransporteFalso(r), d)
                self.assertFalse((Path(d) / "empresa" / "captura" / "freno.json").exists())

    def test_reintentos_de_tasa_solo_puede_ser_cero(self):
        base = PruebasParametros().mapa()
        for malo in (1, 2, 3):
            m = dict(base, ruta_c_reintentos_tasa=malo)
            with self.assertRaises(rc.ErrorLimite, msg=malo):
                rc.parametros_desde_mapa(m)
        self.assertEqual(rc.parametros_desde_mapa(dict(base, ruta_c_reintentos_tasa=0)).reintentos_tasa, 0)

    def test_el_yaml_fija_reintentos_de_tasa_en_rango_0_0(self):
        import yaml
        entrada = yaml.safe_load(rc.RUTA_PARAMETROS_RUTA_C.read_text(encoding="utf-8"))["grupos"]["descubrimiento"][
            "ruta_c_reintentos_tasa"]
        self.assertEqual((entrada["valor"], entrada["rango"]), (0, [0, 0]))
        self.assertNotIn("ruta_c_espera_tasa_seg", rc.CLAVES_RUTA_C)  # sin reintentos no hay espera que configurar
        with tempfile.TemporaryDirectory() as d:
            texto = rc.RUTA_PARAMETROS_RUTA_C.read_text(encoding="utf-8")
            alterado = Path(d) / "a.yaml"
            alterado.write_text(texto.replace("valor: 0\n      unidad: reintentos", "valor: 1\n      unidad: reintentos"),
                                encoding="utf-8")
            with self.assertRaises(rc.ErrorLimite):
                rc.cargar_parametros_ruta_c(alterado)
            sin_rango = Path(d) / "b.yaml"
            sin_rango.write_text(texto.replace("valor: 0\n      unidad: reintentos", "valor: 1\n      unidad: reintentos")
                                 .replace("rango: [0, 0]", "rango: null"), encoding="utf-8")
            with self.assertRaises(rc.ErrorLimite):  # M1: quitar el rango tampoco lo habilita
                rc.cargar_parametros_ruta_c(sin_rango)

    # -- topes y registro -------------------------------------------------------
    def test_tope_por_corrida_corta_con_lo_recibido(self):
        t = TransporteFalso(*self.paginas(5))
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(rc.ErrorLimite) as cm:
                self.barrer(t, d, parametros=parametros(max_solicitudes_por_corrida=3, max_solicitudes_por_dia=100))
            self.assertEqual(cm.exception.codigo_salida, 5)
            self.assertEqual(len(t.llamadas), 3)
            self.assertEqual(len(cm.exception.parcial.anuncios), 3)
            self.assertEqual(len(cm.exception.archivos), 2)
            solicitudes = [x for x in lineas(self.registro(d)) if x["tipo"] == "solicitud"]
            self.assertEqual(len(solicitudes), 3)

    def test_tope_por_corrida_exacto_y_mas_uno(self):
        with tempfile.TemporaryDirectory() as d:  # exacto: 2 páginas con tope 2 -> completo
            rutas = self.barrer(TransporteFalso(*self.paginas(2)), d,
                                parametros=parametros(max_solicitudes_por_corrida=2, max_solicitudes_por_dia=100))
            self.assertEqual(len(rutas), 2)
        with tempfile.TemporaryDirectory() as d:  # tope + 1: 3 páginas con tope 2 -> se corta
            t = TransporteFalso(*self.paginas(3))
            with self.assertRaises(rc.ErrorLimite):
                self.barrer(t, d, parametros=parametros(max_solicitudes_por_corrida=2, max_solicitudes_por_dia=100))
            self.assertEqual(len(t.llamadas), 2)

    def test_el_tope_por_corrida_suma_todas_las_consultas_de_la_corrida(self):
        p = parametros(max_solicitudes_por_corrida=3, max_solicitudes_por_dia=100)
        with tempfile.TemporaryDirectory() as d:
            self.barrer(TransporteFalso(*self.paginas(2)), d, parametros=p, qid="primera")
            t = TransporteFalso(*self.paginas(2))
            with self.assertRaises(rc.ErrorLimite) as cm:
                self.barrer(t, d, parametros=p, qid="segunda")
            self.assertEqual(len(t.llamadas), 1)  # solo quedaba 1 de las 3
            self.assertEqual(len(cm.exception.parcial.anuncios), 1)

    def test_tope_diario_suma_otras_corridas_de_hoy_y_no_las_de_ayer(self):
        p = parametros(max_solicitudes_por_dia=3, max_solicitudes_por_corrida=3)
        with tempfile.TemporaryDirectory() as d:
            sembrar(d, "2026-11-06-b", hoy=3, ayer=50, resultados=40)
            t = TransporteFalso(ok(pagina([anuncio(1)])))
            with self.assertRaises(rc.ErrorLimite) as cm:
                self.barrer(t, d, parametros=p)
            self.assertEqual(cm.exception.codigo_salida, 5)
            self.assertEqual(t.llamadas, [])
            self.assertIn("diario", str(cm.exception))
            self.assertFalse((Path(d) / "empresa" / "barrido" / "crudo").exists())
        with tempfile.TemporaryDirectory() as d:  # 2 de hoy + muchas de ayer: queda 1
            sembrar(d, "2026-11-05-a", ayer=500)
            sembrar(d, "2026-11-06-b", hoy=2)
            t = TransporteFalso(*self.paginas(2))
            with self.assertRaises(rc.ErrorLimite):
                self.barrer(t, d, parametros=p)
            self.assertEqual(len(t.llamadas), 1)

    def test_una_linea_ilegible_del_registro_cuenta_como_solicitud(self):
        with tempfile.TemporaryDirectory() as d:
            sembrar(d, "2026-11-06-b", ilegibles=1)
            with self.assertRaises(rc.ErrorLimite):
                self.barrer(TransporteFalso(ok(pagina([]))), d,
                            parametros=parametros(max_solicitudes_por_dia=1, max_solicitudes_por_corrida=1))

    def test_la_solicitud_se_anota_antes_de_enviarla_y_el_resultado_despues(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(rc.ErrorServicio):
                self.barrer(TransporteFalso(rc.ErrorServicio("fallo de red al llamar a la API (TimeoutError)")), d)
            filas = lineas(self.registro(d))
            self.assertEqual([x["tipo"] for x in filas], ["solicitud", "resultado"])
            self.assertEqual(filas[1]["estado"], "servicio")
        for respuesta, estado in ((error_api(190), "token"), (error_api(10), "acceso"), (error_api(613), "tasa"),
                                  (error_api(100), "respuesta")):
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(rc.ErrorFabrica):
                    self.barrer(TransporteFalso(respuesta), d)
                self.assertEqual(lineas(self.registro(d))[-1]["estado"], estado)

    def test_el_registro_no_guarda_secretos_ni_texto_ajeno(self):
        with tempfile.TemporaryDirectory() as d:
            self.barrer(TransporteFalso(*self.paginas(2)), d)
            texto = self.registro(d).read_text(encoding="utf-8")
            filas = lineas(self.registro(d))
            self.assertEqual([x["tipo"] for x in filas], ["solicitud", "resultado", "solicitud", "resultado"])
            self.assertEqual([x.get("pagina") for x in filas if x["tipo"] == "solicitud"], [1, 2])
            for x in filas:
                self.assertEqual(x["ts"], "2026-11-06T05:50:12Z")
                self.assertEqual((x["corrida_id"], x["qid"]), (CORRIDA, "es-acceso"))
            for prohibido in (TOKEN, "access_token", "graph.facebook.com", "Guía práctica", "Página"):
                self.assertNotIn(prohibido, texto)

    def test_frenar_no_pisa_un_freno_existente(self):
        with tempfile.TemporaryDirectory() as d:
            frenos = rc.Frenos(raiz=Path(d), corrida_id=CORRIDA, qid="es-x", parametros=parametros(), ahora=lambda: AHORA)
            ruta = poner(d, "empresa/captura/freno.json", '{"ts": "2026-11-06T00:00:00Z", "motivo": "de la web"}')
            frenos.frenar("límite de tasa")
            self.assertEqual(ruta.read_text(encoding="utf-8"), '{"ts": "2026-11-06T00:00:00Z", "motivo": "de la web"}')

    def test_el_tope_resiste_solicitudes_simultaneas(self):
        import threading
        for ronda in range(5):
            with tempfile.TemporaryDirectory() as d:
                p = parametros(max_solicitudes_por_corrida=5, max_solicitudes_por_dia=5)
                n = 24
                barrera = threading.Barrier(n)
                resultados: list = []

                def intento(k):
                    frenos = rc.Frenos(raiz=Path(d), corrida_id=CORRIDA, qid="es-x", parametros=p, ahora=lambda: AHORA)
                    barrera.wait()
                    try:
                        frenos.antes_de_solicitar(k)
                        resultados.append("ok")
                    except rc.ErrorTope:
                        resultados.append("tope")

                hilos = [threading.Thread(target=intento, args=(k,)) for k in range(n)]
                for h in hilos:
                    h.start()
                for h in hilos:
                    h.join()
                self.assertEqual((resultados.count("ok"), resultados.count("tope")), (5, n - 5), f"ronda {ronda}")
                self.assertEqual(sum(1 for x in lineas(self.registro(d)) if x["tipo"] == "solicitud"), 5)

    def test_los_topes_son_parametros_obligatorios(self):
        base = PruebasParametros().mapa()
        for clave in ("ruta_c_max_solicitudes_por_dia", "ruta_c_max_solicitudes_por_corrida"):
            self.assertIn(clave, rc.CLAVES_RUTA_C)
            sin = {k: v for k, v in base.items() if k != clave}
            with self.assertRaises(rc.ErrorLimite, msg=clave):
                rc.parametros_desde_mapa(sin)
            for malo in (0, -1, True, 1.5, "5"):
                with self.assertRaises((rc.ErrorLimite, rc.ErrorValidacion), msg=f"{clave}={malo!r}"):
                    rc.parametros_desde_mapa(dict(base, **{clave: malo}))
        with self.assertRaises(rc.ErrorLimite):  # el tope de una corrida no puede superar el diario
            rc.parametros_desde_mapa(dict(base, ruta_c_max_solicitudes_por_corrida=50, ruta_c_max_solicitudes_por_dia=10))

    # -- raíz en producción (mismo hueco que M1: otra raíz reinicia contadores y frenos) -----------------
    def test_en_produccion_no_se_acepta_otra_raiz(self):
        t = TransporteFalso(ok(pagina([anuncio(1)])))
        with tempfile.TemporaryDirectory() as d, mock.patch.dict("os.environ", {"FABRICA_ENTORNO": "produccion"}):
            with self.assertRaises(rc.ErrorUso) as cm:
                self.barrer(t, d)
            self.assertIn("produccion", str(cm.exception))
            self.assertEqual(t.llamadas, [])
        with tempfile.TemporaryDirectory() as d, mock.patch.dict("os.environ", {"FABRICA_ENTORNO": "produccion"}), \
                mock.patch.object(comun, "RAIZ", Path(d).resolve()):
            self.assertEqual(len(self.barrer(TransporteFalso(ok(pagina([anuncio(1)]))), d)), 2)  # la raíz oficial sí
        with tempfile.TemporaryDirectory() as d, mock.patch.dict("os.environ", {"FABRICA_ENTORNO": "desarrollo"}):
            self.assertEqual(len(self.barrer(TransporteFalso(ok(pagina([anuncio(1)]))), d)), 2)

    # -- detector de secretos: solo el valor EXACTO del token -------------------------------------------
    def test_texto_ajeno_con_access_token_no_hace_fallar_la_escritura(self):
        cuerpo = "Pega access_token=abc123 aquí, o ?access_token=zzz&x=1, o EAA" + "B" * 60
        a = anuncio(1, ad_creative_bodies=[cuerpo], ad_creative_link_titles=["access_token=abc"])
        with tempfile.TemporaryDirectory() as d:
            rutas = self.barrer(TransporteFalso(ok(pagina([a, anuncio(2)]))), d)
            crudo = comun.leer_crudo(rutas[0])
            self.assertEqual(len(crudo["ads"]), 2)  # la consulta no se pierde
            self.assertEqual(crudo["ads"][0]["ad_creative_link_title"], "access_token=abc")
            extra = json.loads(rutas[1].read_text(encoding="utf-8"))
            self.assertEqual(extra["anuncios"][a["id"]]["cuerpos"], [cuerpo])

    def test_el_valor_exacto_del_token_en_cualquier_campo_de_texto_se_rechaza(self):
        casos = [
            anuncio(1, ad_creative_bodies=[f"hola {TOKEN} adiós"]),
            anuncio(1, ad_creative_link_titles=[TOKEN]),
            anuncio(1, page_name=f"x{TOKEN}"),
            anuncio(1, target_locations=[{"name": f"lugar {TOKEN}"}]),
            anuncio(1, target_locations=[{TOKEN: "clave con el token"}]),
            anuncio(1, ad_creative_link_descriptions=["ok", f"y {TOKEN}"]),
        ]
        for a in casos:
            with tempfile.TemporaryDirectory() as d:
                with self.assertRaises(rc.ErrorValidacion) as cm:
                    self.barrer(TransporteFalso(ok(pagina([a]))), d)
                self.assertNotIn(TOKEN, str(cm.exception))
                carpeta = Path(d) / "empresa" / "barrido" / "crudo" / CORRIDA
                self.assertEqual(list(carpeta.glob("*")) if carpeta.exists() else [], [])


# ---------------------------------------------------------------------------
# Transporte HTTP real, con el abridor simulado (sin sockets)
# ---------------------------------------------------------------------------

class RespuestaHTTP:
    def __init__(self, status, cuerpo):
        self.status, self._cuerpo = status, cuerpo

    def read(self, n=-1):
        return self._cuerpo if n < 0 else self._cuerpo[:n]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class AbridorFalso:
    def __init__(self, resultado):
        self.resultado, self.peticiones, self.tiempos = resultado, [], []

    def open(self, peticion, timeout=None):
        self.peticiones.append(peticion)
        self.tiempos.append(timeout)
        if isinstance(self.resultado, BaseException):
            raise self.resultado
        return self.resultado


URL = "https://graph.facebook.com/v27.0/ads_archive"


class PruebasTransporteHTTP(Base):
    def llamar(self, abridor, url=URL, max_bytes=1000):
        return rc.TransporteHTTP(abridor).solicitar(url, {"fields": "id", "access_token": TOKEN},
                                                    tiempo_max_seg=7, max_bytes=max_bytes)

    def test_get_https_con_el_token_en_la_consulta(self):
        ab = AbridorFalso(RespuestaHTTP(200, b'{"data": []}'))
        r = self.llamar(ab)
        self.assertEqual((r.estado, r.cuerpo), (200, b'{"data": []}'))
        pet = ab.peticiones[0]
        self.assertEqual(pet.get_method(), "GET")
        self.assertTrue(pet.full_url.startswith(URL + "?"))
        self.assertIn("access_token=" + TOKEN, pet.full_url)
        self.assertEqual(ab.tiempos, [7])
        self.assertIn("digital-products", pet.get_header("User-agent"))

    def test_hosts_y_esquemas_ajenos_se_rechazan(self):
        for url in ("http://graph.facebook.com/v27.0/ads_archive", "https://evil.example.com/ads_archive",
                    "https://graph.facebook.com.evil.com/x", "https://user:pw@graph.facebook.com/x",
                    "https://graph.facebook.com:8443/x", "https://graph.facebook.com/x?access_token=z",
                    "file:///etc/passwd"):
            ab = AbridorFalso(RespuestaHTTP(200, b"{}"))
            with self.assertRaises(rc.ErrorUso, msg=url):
                self.llamar(ab, url=url)
            self.assertEqual(ab.peticiones, [])

    def test_error_http_devuelve_el_json_de_error(self):
        cuerpo = json.dumps({"error": {"code": 190, "message": "x"}}).encode()
        exc = urllib.error.HTTPError(URL, 400, "Bad Request", {}, mock.MagicMock(read=lambda n=-1: cuerpo))
        r = self.llamar(AbridorFalso(exc))
        self.assertEqual((r.estado, r.cuerpo), (400, cuerpo))

    def test_redireccion_se_informa_no_se_sigue(self):
        exc = urllib.error.HTTPError(URL, 302, "Found", {}, mock.MagicMock(read=lambda n=-1: b""))
        self.assertEqual(self.llamar(AbridorFalso(exc)).estado, 302)

    def test_fallo_de_red_no_filtra_url_ni_token(self):
        for causa in (urllib.error.URLError("fallo"), TimeoutError(f"timeout {TOKEN}"), ConnectionResetError()):
            with self.assertRaises(rc.ErrorServicio) as cm:
                self.llamar(AbridorFalso(causa))
            self.assertNotIn(TOKEN, str(cm.exception))
            self.assertNotIn("graph.facebook.com", str(cm.exception))

    def test_respuesta_mayor_que_el_tope(self):
        with self.assertRaises(rc.ErrorRespuesta):
            self.llamar(AbridorFalso(RespuestaHTTP(200, b"x" * 1001)), max_bytes=1000)
        self.assertEqual(len(self.llamar(AbridorFalso(RespuestaHTTP(200, b"x" * 1000)), max_bytes=1000).cuerpo), 1000)

    def test_el_cliente_funciona_con_el_transporte_http_simulado(self):
        ab = AbridorFalso(RespuestaHTTP(200, pagina([anuncio(1)])))
        res = rc.ClienteBiblioteca(rc.TransporteHTTP(ab), rc.leer_token(ENTORNO), parametros(), FrenosFalsos(),
                                   dormir=self.dormir).buscar(CONSULTA)
        self.assertEqual(len(res.anuncios), 1)
        self.assertIn("/v27.0/ads_archive?", ab.peticiones[0].full_url)


class PruebasSinRed(unittest.TestCase):
    def test_el_modulo_no_abre_sockets_al_importar_ni_al_construir(self):
        with mock.patch("socket.socket", side_effect=AssertionError("red")):
            rc.TransporteHTTP()
            rc.cargar_parametros_ruta_c()


if __name__ == "__main__":
    unittest.main()
