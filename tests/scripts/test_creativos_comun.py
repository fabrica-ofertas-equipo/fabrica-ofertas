# Ayudas compartidas de las pruebas de scripts.creativos (sin clases TestCase propias: unittest lo
# importa pero no aporta pruebas por si mismo).
# Reutiliza (solo lectura, sin editarlo) tests.engine.apoyo.crear_empresa y agrega encima la parte
# propia de una oferta de D6: mercado.json, 03-oferta/oferta.json (copiado de ofertas/_ejemplo, ya
# valido contra el esquema) y 05-landing/sitio/index.html.
from __future__ import annotations

import json
import shutil
from pathlib import Path

from tests.engine.apoyo import AHORA_BASE, GENERADO_EN, OFERTA, EmpresaPrueba, PruebaBase, crear_empresa  # noqa: F401

RAIZ_REPO = Path(__file__).resolve().parents[2]
EJEMPLO = RAIZ_REPO / 'ofertas' / '_ejemplo'

__all__ = ['AHORA_BASE', 'GENERADO_EN', 'OFERTA', 'EmpresaPrueba', 'PruebaBase', 'crear_empresa', 'crear_oferta_creativos']


def crear_oferta_creativos(emp: EmpresaPrueba, *, oferta_id: str = OFERTA, locale: str = 'es-ES', con_sitio: bool = True) -> Path:
    dir_oferta = emp.raiz / 'ofertas' / oferta_id
    (dir_oferta / '03-oferta').mkdir(parents=True, exist_ok=True)
    mercado = {'schema_version': '1.1.0', 'oferta_id': oferta_id, 'locale': locale}
    (dir_oferta / 'mercado.json').write_text(json.dumps(mercado), encoding='utf-8')
    shutil.copyfile(EJEMPLO / '03-oferta' / 'oferta.json', dir_oferta / '03-oferta' / 'oferta.json')
    if con_sitio:
        sitio = dir_oferta / '05-landing' / 'sitio'
        sitio.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(EJEMPLO / '05-landing' / 'sitio' / 'index.html', sitio / 'index.html')
    return dir_oferta
