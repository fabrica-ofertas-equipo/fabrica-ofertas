"""Pruebas de ``infra.dominio``: verificación de solo lectura (DNS/TXT, portfolio de Meta); nunca
escribe DNS ni compra nada; sin transporte inyectado queda «pendiente», nunca verde falso."""
from __future__ import annotations

from engine.errores import ErrorUso
from engine.transporte import TransporteFixture
from infra import dominio
from tests.infra.apoyo import PruebaBase

DOMINIO = "ejemplo.com"


class ClienteMetaFalso:
    """Doble mínimo: solo implementa ``listar`` (lo único que ``dominio_verificado_en_meta`` usa)."""

    def __init__(self, items: list[dict]) -> None:
        self._items = items

    def listar(self, ruta_padre: str, *, campos, limite: int = 200) -> list[dict]:
        return self._items


class PruebaConsultarTxt(PruebaBase):
    def test_extrae_los_valores_txt_sin_comillas(self) -> None:
        t = TransporteFixture([
            {"metodo": "GET", "url_prefijo": "https://cloudflare-dns.com/dns-query", "cuerpo": {
                "Answer": [{"type": 16, "data": '"meta-domain-verification=abc123"'}, {"type": 1, "data": "1.2.3.4"}],
            }},
        ])
        valores = dominio.consultar_txt(t, DOMINIO)
        self.assertEqual(valores, ["meta-domain-verification=abc123"])

    def test_sin_registros_txt_devuelve_lista_vacia(self) -> None:
        t = TransporteFixture([{"metodo": "GET", "url_prefijo": "https://cloudflare-dns.com/dns-query", "cuerpo": {"Answer": []}}])
        self.assertEqual(dominio.consultar_txt(t, DOMINIO), [])


class PruebaDominioVerificadoEnMeta(PruebaBase):
    def test_verificado_true(self) -> None:
        cliente = ClienteMetaFalso([{"domain": DOMINIO, "verification_status": "verified"}])
        self.assertTrue(dominio.dominio_verificado_en_meta(cliente, "biz1", DOMINIO))

    def test_dado_de_alta_pero_no_verificado(self) -> None:
        cliente = ClienteMetaFalso([{"domain": DOMINIO, "verification_status": "pending"}])
        self.assertFalse(dominio.dominio_verificado_en_meta(cliente, "biz1", DOMINIO))

    def test_dominio_ausente_es_desconocido_no_falso(self) -> None:
        cliente = ClienteMetaFalso([{"domain": "otro.com", "verification_status": "verified"}])
        self.assertIsNone(dominio.dominio_verificado_en_meta(cliente, "biz1", DOMINIO))


class PruebaVerificar(PruebaBase):
    def test_dominio_vacio_es_error_de_uso(self) -> None:
        with self.assertRaises(ErrorUso):
            dominio.verificar("")

    def test_sin_ningun_transporte_todo_queda_pendiente_y_falta(self) -> None:
        resultado = dominio.verificar(DOMINIO)
        self.assertFalse(resultado.completo)
        self.assertEqual(resultado.dns_txt["estado"], "pendiente")
        self.assertEqual(resultado.meta_portfolio["estado"], "pendiente")
        self.assertEqual(len(resultado.faltan), 2)

    def test_txt_presente_y_coincide_con_lo_esperado(self) -> None:
        t = TransporteFixture([
            {"metodo": "GET", "url_prefijo": "https://cloudflare-dns.com/dns-query",
             "cuerpo": {"Answer": [{"type": 16, "data": '"meta-domain-verification=abc123"'}]}},
        ])
        resultado = dominio.verificar(DOMINIO, transporte_dns=t, txt_esperado="meta-domain-verification=abc123")
        self.assertEqual(resultado.dns_txt["estado"], "ok")
        self.assertTrue(resultado.dns_txt["coincide_esperado"])
        self.assertNotIn("dns_txt: sin ningún registro TXT", resultado.faltan)

    def test_txt_presente_pero_no_coincide(self) -> None:
        t = TransporteFixture([
            {"metodo": "GET", "url_prefijo": "https://cloudflare-dns.com/dns-query",
             "cuerpo": {"Answer": [{"type": 16, "data": '"otro-valor"'}]}},
        ])
        resultado = dominio.verificar(DOMINIO, transporte_dns=t, txt_esperado="meta-domain-verification=abc123")
        self.assertFalse(resultado.dns_txt["coincide_esperado"])
        self.assertIn("dns_txt: ninguno coincide con --txt-esperado", resultado.faltan)

    def test_meta_verificado_y_dns_ok_da_completo(self) -> None:
        t = TransporteFixture([
            {"metodo": "GET", "url_prefijo": "https://cloudflare-dns.com/dns-query",
             "cuerpo": {"Answer": [{"type": 16, "data": '"x"'}]}},
        ])
        cliente = ClienteMetaFalso([{"domain": DOMINIO, "verification_status": "verified"}])
        resultado = dominio.verificar(DOMINIO, transporte_dns=t, cliente_meta=cliente, business_id="biz1")
        self.assertTrue(resultado.completo)
        self.assertEqual(resultado.faltan, ())


class PruebaCLI(PruebaBase):
    def test_sin_fixtures_sale_4_nunca_0_por_omision(self) -> None:
        codigo = dominio.main(["verificar", "--dominio", DOMINIO, "--json"])
        self.assertEqual(codigo, 4)

    def test_con_fixture_dns_completo_pero_sin_meta_sigue_en_4(self) -> None:
        ruta = self.tmp / "dns.yaml"
        ruta.write_text(
            'reglas:\n  - {metodo: GET, url_prefijo: "https://cloudflare-dns.com/dns-query", '
            'cuerpo: {Answer: [{type: 16, data: \'"x"\'}]}}\n',
            encoding="utf-8",
        )
        codigo = dominio.main(["verificar", "--dominio", DOMINIO, "--fixture-dns", str(ruta), "--json"])
        self.assertEqual(codigo, 4)
