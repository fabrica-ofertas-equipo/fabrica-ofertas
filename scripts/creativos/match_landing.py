"""Message match (K01) de D6 (``departamentos/07-creativos.md`` §6 L1.5).

Compara precio, moneda, garantía, nombre (marca) y ``claim_ids`` de UNA pieza contra
``03-oferta/oferta.json`` y ``05-landing/sitio/`` de la misma oferta. Lee el precio, la moneda y los
días de garantía de los atributos ``data-precio-minor``, ``data-moneda`` y ``data-garantia-dias`` que
``landing.generar`` escribe en el ``<body>`` (``ofertas/_ejemplo/05-landing/sitio/index.html``): son
datos máquina-legibles, no se adivinan de un texto formateado por ``locale`` (que varía: «19,90 €»
en ``es-ES``, «19.90 €» en ``en-US``…). La diferencia exacta queda en la salida.

CLI::

    python -m scripts.creativos.match_landing --oferta OF-202611-01 --pieza PIEZA.json [--raiz RUTA] [--json]

``PIEZA.json`` (forma de un elemento de ``paquete.json#/anuncios``, sin el resto del paquete):
``{"ad_name": "...", "claim_ids": [...], "copy": {...}}`` (el ``precio``/``moneda``, si la pieza los
declara, también se comparan; si no los declara solo se comparan landing↔oferta).

Salida (convenciones §8): 0 sin diferencias · 3 alguna diferencia (esquema o message match) · 2 uso.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion

__all__ = ["Diferencia", "comparar", "main"]

_RX_ATRIBUTOS_BODY = re.compile(r"<body\b([^>]*)>", re.IGNORECASE)
_RX_DATA = re.compile(r'data-([a-z-]+)="([^"]*)"')
_RX_MARCA = re.compile(r'<p class="marca">(.*?)</p>', re.IGNORECASE | re.DOTALL)
_RX_ETIQUETA = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class Diferencia:
    campo: str
    esperado: Any
    encontrado: Any

    def asdict(self) -> dict[str, Any]:
        return {"campo": self.campo, "esperado": self.esperado, "encontrado": self.encontrado}


def _atributos_body(html: str) -> dict[str, str]:
    m = _RX_ATRIBUTOS_BODY.search(html)
    if not m:
        raise ErrorValidacion("sitio/index.html sin <body>: no se puede leer precio/moneda/garantía")
    return dict(_RX_DATA.findall(m.group(1)))


def _texto_marca(html: str) -> str | None:
    m = _RX_MARCA.search(html)
    if not m:
        return None
    return _RX_ETIQUETA.sub("", m.group(1)).strip()


def comparar(pieza: Mapping[str, Any], oferta: Mapping[str, Any], html_landing: str) -> list[Diferencia]:
    """Diferencias EXACTAS entre ``pieza``, ``oferta.json`` y ``05-landing/sitio/index.html``."""
    diferencias: list[Diferencia] = []
    atributos = _atributos_body(html_landing)
    precio_oferta = ((oferta.get("precio") or {}).get("lista")) or {}
    try:
        precio_landing_minor = int(atributos["precio-minor"])
    except (KeyError, ValueError):
        diferencias.append(Diferencia("precio.monto", precio_oferta.get("monto"), atributos.get("precio-minor")))
    else:
        if precio_landing_minor != precio_oferta.get("monto"):
            diferencias.append(Diferencia("precio.monto", precio_oferta.get("monto"), precio_landing_minor))
    moneda_landing = atributos.get("moneda")
    if moneda_landing != precio_oferta.get("moneda"):
        diferencias.append(Diferencia("precio.moneda", precio_oferta.get("moneda"), moneda_landing))

    precio_pieza = pieza.get("precio")
    if isinstance(precio_pieza, Mapping):
        if precio_pieza.get("monto") != precio_oferta.get("monto"):
            diferencias.append(Diferencia("pieza.precio.monto", precio_oferta.get("monto"), precio_pieza.get("monto")))
        if precio_pieza.get("moneda") != precio_oferta.get("moneda"):
            diferencias.append(Diferencia("pieza.precio.moneda", precio_oferta.get("moneda"), precio_pieza.get("moneda")))

    dias_garantia_oferta = (oferta.get("garantia") or {}).get("dias")
    try:
        dias_garantia_landing = int(atributos["garantia-dias"])
    except (KeyError, ValueError):
        diferencias.append(Diferencia("garantia.dias", dias_garantia_oferta, atributos.get("garantia-dias")))
    else:
        if dias_garantia_landing != dias_garantia_oferta:
            diferencias.append(Diferencia("garantia.dias", dias_garantia_oferta, dias_garantia_landing))

    nombre_oferta = (oferta.get("marca") or {}).get("nombre")
    nombre_landing = _texto_marca(html_landing)
    if nombre_landing != nombre_oferta:
        diferencias.append(Diferencia("marca.nombre", nombre_oferta, nombre_landing))

    permitidos = {c.get("claim_id") for c in ((oferta.get("promesa") or {}).get("claims_permitidos") or [])}
    claim_ids_pieza = pieza.get("claim_ids") or []
    no_permitidos = [c for c in claim_ids_pieza if c not in permitidos]
    if no_permitidos:
        diferencias.append(Diferencia("claim_ids", sorted(permitidos), no_permitidos))

    return diferencias


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.creativos.match_landing", description="K01: message match de una pieza contra oferta.json y la landing.")
    p.add_argument("--oferta", required=True, dest="oferta_id")
    p.add_argument("--pieza", required=True, type=Path)
    p.add_argument("--raiz", type=Path, default=None)
    p.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        a = _parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        entorno_actual = comun.entorno(env)
        if a.raiz and entorno_actual == "produccion":
            raise ErrorUso("--raiz no existe con FABRICA_ENTORNO=produccion")
        raiz = a.raiz.resolve() if a.raiz else comun.raiz(env)
        try:
            pieza = comun.cargar_json(a.pieza)
        except FileNotFoundError as exc:
            raise ErrorUso(f"--pieza no existe: {a.pieza}") from exc
        if not isinstance(pieza, Mapping):
            raise ErrorValidacion("--pieza debe ser un objeto JSON")
        try:
            oferta = comun.cargar_json(raiz / "ofertas" / a.oferta_id / "03-oferta" / "oferta.json")
        except FileNotFoundError as exc:
            raise ErrorValidacion(f"falta 03-oferta/oferta.json de {a.oferta_id}") from exc
        ruta_html = raiz / "ofertas" / a.oferta_id / "05-landing" / "sitio" / "index.html"
        try:
            html_landing = ruta_html.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ErrorValidacion("falta 05-landing/sitio/index.html") from exc

        diferencias = comparar(pieza, oferta, html_landing)
        codigo = 3 if diferencias else 0
        datos = {"diferencias": [d.asdict() for d in diferencias]}
        salida = {"ok": codigo == 0, "modo": "dry_run", "codigo": codigo, "datos": datos, "avisos": []}
        if a.json:
            print(json.dumps(salida, sort_keys=True, ensure_ascii=False))
        else:
            if diferencias:
                for d in diferencias:
                    print(f"DIFERENCIA {d.campo}: esperado={d.esperado!r} encontrado={d.encontrado!r}")
            else:
                print("MESSAGE MATCH: sin diferencias")
        return codigo

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    raise SystemExit(main())
