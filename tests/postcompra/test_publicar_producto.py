"""Pruebas de :mod:`postcompra.publicar_producto`: empaquetado determinista y rechazo si el archivo cambió."""
from __future__ import annotations

import unittest
import zipfile

from engine.errores import ErrorValidacion
from postcompra.publicar_producto import publicar_producto
from tests.postcompra.apoyo import PruebaBase, crear_oferta_producto

OFERTA = "OF-202611-01"


class PruebaPublicarProducto(PruebaBase):
    def test_publica_y_el_zip_es_determinista(self) -> None:
        crear_oferta_producto(self.tmp, OFERTA)
        r1 = publicar_producto(oferta_id=OFERTA, raiz=self.tmp)
        contenido_1 = r1.ruta_zip.read_bytes()
        r1.ruta_zip.unlink()
        r1.ruta_paquete_json.unlink()
        r2 = publicar_producto(oferta_id=OFERTA, raiz=self.tmp)
        contenido_2 = r2.ruta_zip.read_bytes()
        self.assertEqual(contenido_1, contenido_2)
        self.assertEqual(r1.producto_sha256, r2.producto_sha256)
        with zipfile.ZipFile(r2.ruta_zip) as zf:
            self.assertEqual(set(zf.namelist()), {"guia.md", "plantilla.md"})

    def test_rechaza_si_el_producto_no_esta_aprobado(self) -> None:
        producto = crear_oferta_producto(self.tmp, OFERTA)
        ruta = self.tmp / "ofertas" / OFERTA / "04-producto" / "producto.json"
        from engine import comun
        producto["estado"] = "en_QA"
        comun.escribir_atomico(ruta, comun.json_canonico(producto))
        with self.assertRaises(ErrorValidacion):
            publicar_producto(oferta_id=OFERTA, raiz=self.tmp)

    def test_rechaza_si_el_archivo_cambio_desde_la_aprobacion(self) -> None:
        crear_oferta_producto(self.tmp, OFERTA)
        ruta_item = self.tmp / "ofertas" / OFERTA / "04-producto" / "entregables" / "guia.md"
        ruta_item.write_text("contenido alterado después de aprobar\n", encoding="utf-8")
        with self.assertRaises(ErrorValidacion):
            publicar_producto(oferta_id=OFERTA, raiz=self.tmp)


if __name__ == "__main__":
    unittest.main()
