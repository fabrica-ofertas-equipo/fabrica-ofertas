"""Nombres y URL de objetos de Meta (backbone §5.2 y §5.3).

Construye y valida los tres nombres de Meta y la plantilla de URL con macros y parámetros de
atribución. Los patrones ASCII (sin ``|`` ni espacios en los campos) son los de
``contratos/comunes.schema.json`` (``nombre_meta_campana``, ``nombre_meta_conjunto``,
``nombre_meta_anuncio``): este módulo los lee de ahí (una sola fuente, convenciones §12) en vez de
repetirlos.

* Campaña: ``{oferta_id}_{fase}_{objetivo}_{estructura}_{AAAAMMDD}``.
* Conjunto: ``{audiencia}_{ubicaciones}_{idioma}``.
* Anuncio: ``{concepto_id}_{formato}_{hook_id}_v{n}``.

La URL de anuncio lleva, en este orden, los parámetros que ``scripts.validar_esquemas.regla_campana``
exige (UTM + IDs de atribución): ``utm_source=meta``, ``utm_medium=paid``,
``utm_campaign={{campaign.name}}``, ``utm_content={{ad.name}}``, ``utm_term={{adset.name}}``,
``oferta_id``, ``cid={{campaign.id}}``, ``asid={{adset.id}}``, ``adid={{ad.id}}``.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from typing import Literal, Mapping, Sequence
from urllib.parse import quote

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion
from scripts.validar_esquemas import DIR_CONTRATOS

__all__ = [
    "MACROS_URL", "main", "nombre_anuncio", "nombre_campana", "nombre_conjunto", "parametros_url_exigidos",
    "resolver_url", "url_anuncio", "validar_nombre",
]

TipoNombre = Literal["campana", "conjunto", "anuncio"]
_CLAVES_PATRON: Mapping[TipoNombre, str] = {
    "campana": "nombre_meta_campana", "conjunto": "nombre_meta_conjunto", "anuncio": "nombre_meta_anuncio",
}
# Macros de Meta que se expanden en la URL de clic (backbone §5.3); se escriben literales (sin
# urlencode) en la plantilla y se reemplazan por valores reales en resolver_url().
MACROS_URL = {
    "campaign.name": "{{campaign.name}}", "campaign.id": "{{campaign.id}}",
    "adset.name": "{{adset.name}}", "adset.id": "{{adset.id}}",
    "ad.name": "{{ad.name}}", "ad.id": "{{ad.id}}",
}


def _patrones() -> dict[str, str]:
    comunes = comun.cargar_json(DIR_CONTRATOS / "comunes.schema.json")
    return {k: comunes["$defs"][k]["pattern"] for k in _CLAVES_PATRON.values()}


def validar_nombre(tipo: TipoNombre, s: str) -> str:
    """Devuelve ``s`` si cumple el patrón de Meta de ``tipo`` y no lleva ``'|'``; si no, ``ErrorValidacion``.

    ``'|'`` está prohibido en nombres y URLs de Meta (se usa ``'_'`` o ``%7C`` en macros, backbone §5.2).
    """
    if tipo not in _CLAVES_PATRON:
        raise ErrorValidacion(f"validar_nombre: tipo desconocido {tipo!r}")
    if not isinstance(s, str) or "|" in s:
        raise ErrorValidacion(f"nombre de Meta ({tipo}) inválido: contiene '|' o no es texto: {s!r}")
    import re

    patron = _patrones()[_CLAVES_PATRON[tipo]]
    if not re.fullmatch(patron, s):
        raise ErrorValidacion(f"nombre de Meta ({tipo}) no cumple el patrón {_CLAVES_PATRON[tipo]}: {s!r}")
    return s


def nombre_campana(oferta_id: str, fase: str, objetivo: str, estructura: str, fecha: date | str) -> str:
    """``{oferta_id}_{fase}_{objetivo}_{estructura}_{AAAAMMDD}``; valida contra el patrón antes de devolver."""
    aaaammdd = fecha if isinstance(fecha, str) else fecha.strftime("%Y%m%d")
    return validar_nombre("campana", f"{oferta_id}_{fase}_{objetivo}_{estructura}_{aaaammdd}")


def nombre_conjunto(audiencia: str, ubicaciones: str, idioma: str) -> str:
    """``{audiencia}_{ubicaciones}_{idioma}``; valida contra el patrón antes de devolver."""
    return validar_nombre("conjunto", f"{audiencia}_{ubicaciones}_{idioma}")


def nombre_anuncio(concepto_id: str, formato: str, hook_id: str, version: int) -> str:
    """``{concepto_id}_{formato}_{hook_id}_v{n}``; valida contra el patrón antes de devolver."""
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise ErrorValidacion("nombre_anuncio: version debe ser un entero >= 1")
    return validar_nombre("anuncio", f"{concepto_id}_{formato}_{hook_id}_v{version}")


def parametros_url_exigidos(oferta_id: str) -> dict[str, str]:
    """Los parámetros (orden y valor) que ``regla_campana`` exige en la plantilla de URL de un anuncio."""
    return {
        "utm_source": "meta", "utm_medium": "paid", "utm_campaign": MACROS_URL["campaign.name"],
        "utm_content": MACROS_URL["ad.name"], "utm_term": MACROS_URL["adset.name"], "oferta_id": oferta_id,
        "cid": MACROS_URL["campaign.id"], "asid": MACROS_URL["adset.id"], "adid": MACROS_URL["ad.id"],
    }


def url_anuncio(base: str, oferta_id: str) -> str:
    """Plantilla de URL de clic: ``base`` + los parámetros de :func:`parametros_url_exigidos`, con macros literales.

    ``base`` debe ser ``https://…`` (``landing.catalogo``/``despliegue.json``, ``destino.url_base``);
    las macros ``{{…}}`` NO se codifican con porcentaje (Meta las expande antes de resolver la URL).
    """
    if not isinstance(base, str) or not base.startswith("https://"):
        raise ErrorValidacion("url_anuncio exige una base https://")
    separador = "&" if "?" in base else "?"
    cadena = "&".join(f"{quote(k, safe='')}={v if '{{' in v else quote(v, safe='')}" for k, v in parametros_url_exigidos(oferta_id).items())
    return f"{base}{separador}{cadena}"


def resolver_url(plantilla: str, *, campaign_name: str, campaign_id: str, adset_name: str, adset_id: str, ad_name: str, ad_id: str) -> str:
    """Reemplaza las seis macros de :data:`MACROS_URL` por valores reales (``ejemplo_resuelto`` de ``campana.json``).

    Errores: ``ErrorValidacion`` si queda alguna macro ``{{…}}`` sin resolver (dato incoherente).
    """
    valores = {
        MACROS_URL["campaign.name"]: campaign_name, MACROS_URL["campaign.id"]: campaign_id,
        MACROS_URL["adset.name"]: adset_name, MACROS_URL["adset.id"]: adset_id,
        MACROS_URL["ad.name"]: ad_name, MACROS_URL["ad.id"]: ad_id,
    }
    resultado = plantilla
    for macro, valor in valores.items():
        resultado = resultado.replace(macro, quote(str(valor), safe=""))
    if "{{" in resultado or "}}" in resultado:
        raise ErrorValidacion("resolver_url: quedó una macro sin resolver")
    return resultado


# ----------------------------------------------------------------------------------------------
# CLI (A3, ola 2 B5b): pura, sin red, sin --modo (ninguna función de arriba tiene efecto externo).
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """``python -m meta.nombres {campana,conjunto,anuncio,url,resolver} …``: una línea JSON con ``--json``.

    Cálculo puro (backbone §5.2-5.3): sin ``--modo``, sin red, sin ``--raiz``/``--ahora``. Salidas:
    0 correcto · 2 uso (subcomando desconocido) · 3 validación (nombre que no cumple el patrón de Meta).
    """
    # Dos "padres" para que --json funcione antes O después del subcomando sin que el default del
    # subparser pise lo que ya puso el parser de arriba: el de las subparsers usa SUPPRESS (no toca
    # "json" si no se repite ahí) y el de arriba sí fija el default real (False).
    padre_top = argparse.ArgumentParser(add_help=False)
    padre_top.add_argument("--json", action="store_true")
    padre_sub = argparse.ArgumentParser(add_help=False)
    padre_sub.add_argument("--json", action="store_true", default=argparse.SUPPRESS)

    ap = argparse.ArgumentParser(prog="python -m meta.nombres", parents=[padre_top],
                                 description="Nombres y URL de atribución de Meta (backbone §5.2-5.3).")
    sub = ap.add_subparsers(dest="cmd", required=True)
    padre = padre_sub

    s = sub.add_parser("campana", parents=[padre])
    s.add_argument("--oferta", required=True, dest="oferta_id")
    s.add_argument("--fase", required=True)
    s.add_argument("--objetivo", required=True)
    s.add_argument("--estructura", required=True)
    s.add_argument("--fecha", required=True, help="AAAAMMDD o AAAA-MM-DD")

    s = sub.add_parser("conjunto", parents=[padre])
    s.add_argument("--audiencia", required=True)
    s.add_argument("--ubicaciones", required=True)
    s.add_argument("--idioma", required=True)

    s = sub.add_parser("anuncio", parents=[padre])
    s.add_argument("--concepto", required=True, dest="concepto_id")
    s.add_argument("--formato", required=True)
    s.add_argument("--hook", required=True, dest="hook_id")
    s.add_argument("--version", required=True, type=int)

    s = sub.add_parser("url", parents=[padre])
    s.add_argument("--base", required=True)
    s.add_argument("--oferta", required=True, dest="oferta_id")

    s = sub.add_parser("resolver", parents=[padre])
    s.add_argument("--plantilla", required=True)
    s.add_argument("--campaign-name", required=True, dest="campaign_name")
    s.add_argument("--campaign-id", required=True, dest="campaign_id")
    s.add_argument("--adset-name", required=True, dest="adset_name")
    s.add_argument("--adset-id", required=True, dest="adset_id")
    s.add_argument("--ad-name", required=True, dest="ad_name")
    s.add_argument("--ad-id", required=True, dest="ad_id")

    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        if args.cmd == "campana":
            fecha = args.fecha.replace("-", "")
            valor = nombre_campana(args.oferta_id, args.fase, args.objetivo, args.estructura, fecha)
        elif args.cmd == "conjunto":
            valor = nombre_conjunto(args.audiencia, args.ubicaciones, args.idioma)
        elif args.cmd == "anuncio":
            valor = nombre_anuncio(args.concepto_id, args.formato, args.hook_id, args.version)
        elif args.cmd == "url":
            valor = url_anuncio(args.base, args.oferta_id)
        elif args.cmd == "resolver":
            valor = resolver_url(
                args.plantilla, campaign_name=args.campaign_name, campaign_id=args.campaign_id,
                adset_name=args.adset_name, adset_id=args.adset_id, ad_name=args.ad_name, ad_id=args.ad_id,
            )
        else:
            raise ErrorUso(f"subcomando desconocido: {args.cmd!r}")
        if args.json:
            print(comun.json_canonico({"ok": True, "modo": "dry_run", "codigo": 0, "datos": {"valor": valor}, "avisos": []}).decode("utf-8"))
        else:
            print(valor)
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
