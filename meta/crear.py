"""``meta.crear``: borrador de campaña en Meta, todo ``PAUSED`` (docs/06 N11, departamentos/08 §4).

Crea campaña → conjunto → creativos → anuncios por la Marketing API (vía :class:`meta.cliente.ClienteMeta`)
y nunca activa nada: cada objeto se crea con ``status=PAUSED`` (:mod:`meta.payloads`). Es **idempotente**
por nombre: antes de crear busca por el prefijo ``{oferta_id}_TEST_`` (campaña y conjunto) o por nombre
exacto (creativo y anuncio, donde el ``startswith`` de un prefijo colisionaría entre ``_v1`` y ``_v10``)
y reutiliza lo que ya existe en vez de duplicar (convenciones §7: "antes de crear algo en Meta… se busca
por ID o nombre canónico y se reutiliza lo existente").

``crear()`` es pura respecto de la red: toda llamada pasa por el ``ClienteMeta`` inyectado (que a su vez
recibe un ``Transporte``; en pruebas y en B0, :class:`engine.transporte.TransporteFixture`).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine import comun, limites as motor_limites
from engine.errores import ErrorUso, ErrorValidacion
from meta import _cli_comun, payloads
from meta.cliente import ClienteMeta

__all__ = ["ResultadoCrear", "crear", "main", "prefijo_test"]


def prefijo_test(oferta_id: str) -> str:
    """Prefijo de reutilización por nombre de D7: ``{oferta_id}_TEST_`` (docs/06 N11)."""
    return f"{oferta_id}_TEST_"


class ResultadoCrear:
    """``ids_meta.json`` (sin ``schema_version`` ni ``creado_en``: los agrega quien escribe el archivo) y el mapa ``ad_name -> ad_id`` para ``lanzamiento.log``."""

    def __init__(self, *, ad_account_id: str, campaign_id: str, adset_ids: list[str], ad_ids: list[str],
                 creative_ids: list[str], mapa_ad_name_a_id: dict[str, str]) -> None:
        self.ad_account_id = ad_account_id
        self.campaign_id = campaign_id
        self.adset_ids = adset_ids
        self.ad_ids = ad_ids
        self.creative_ids = creative_ids
        self.mapa_ad_name_a_id = mapa_ad_name_a_id

    def como_ids_meta(self, *, oferta_id: str, creado_en: str, hash_config: str) -> dict[str, Any]:
        """Objeto listo para validar y escribir contra ``contratos/ids_meta.schema.json``."""
        return {
            "schema_version": "1.0.0", "oferta_id": oferta_id, "ad_account_id": self.ad_account_id,
            "campaign_id": self.campaign_id, "adset_ids": self.adset_ids, "ad_ids": self.ad_ids,
            "creative_ids": self.creative_ids, "creado_en": creado_en, "hash_config": hash_config,
        }


def crear(*, oferta_id: str, campana: Mapping[str, Any], cliente: ClienteMeta, ad_account_id: str,
         pixel_id: str, payloads_creativo: Mapping[str, Mapping[str, Any]]) -> ResultadoCrear:
    """Crea (o reutiliza) campaña → conjunto → creativos → anuncios, todo ``PAUSED``.

    ``payloads_creativo`` mapea ``ad_name -> payload de POST act_<id>/adcreatives`` (el creativo en sí,
    con las referencias a los assets ya subidos por D6/D4; ese armado no es de este módulo). Errores:
    ``ErrorValidacion`` si falta el payload de un creativo o el anuncio no está en ``campana.anuncios``.
    """
    if campana.get("estado") not in ("borrador", "preflight_ok"):
        raise ErrorValidacion(f"meta.crear exige campana.estado en {{borrador, preflight_ok}}, es {campana.get('estado')!r}")
    prefijo = prefijo_test(oferta_id)

    existente_campana = cliente.buscar_por_prefijo(f"{ad_account_id}/campaigns", prefijo)
    campaign_id = existente_campana["id"] if existente_campana else cliente.crear(f"{ad_account_id}/campaigns", payloads.payload_campana(campana))["id"]

    existente_conjunto = cliente.buscar_por_prefijo(f"{ad_account_id}/adsets", prefijo)
    adset_id = existente_conjunto["id"] if existente_conjunto else cliente.crear(
        f"{ad_account_id}/adsets", payloads.payload_conjunto(campana, campaign_id=campaign_id, pixel_id=pixel_id)
    )["id"]

    creative_ids: list[str] = []
    ad_ids: list[str] = []
    mapa: dict[str, str] = {}
    for anuncio in campana["anuncios"]:
        ad_name = anuncio["ad_name"]
        payload_creativo = payloads_creativo.get(ad_name)
        if payload_creativo is None:
            raise ErrorValidacion(f"meta.crear: falta el payload de creativo para {ad_name!r}")
        existente_creativo = cliente.buscar_por_nombre_exacto(f"{ad_account_id}/adcreatives", ad_name)
        creative_id = existente_creativo["id"] if existente_creativo else cliente.crear(f"{ad_account_id}/adcreatives", payload_creativo)["id"]
        creative_ids.append(creative_id)

        existente_anuncio = cliente.buscar_por_nombre_exacto(f"{ad_account_id}/ads", ad_name)
        ad_id = existente_anuncio["id"] if existente_anuncio else cliente.crear(
            f"{ad_account_id}/ads", payloads.payload_anuncio(anuncio, adset_id=adset_id, creative_id=creative_id)
        )["id"]
        ad_ids.append(ad_id)
        mapa[ad_name] = ad_id

    return ResultadoCrear(
        ad_account_id=ad_account_id, campaign_id=campaign_id, adset_ids=[adset_id], ad_ids=ad_ids,
        creative_ids=creative_ids, mapa_ad_name_a_id=mapa,
    )


# ----------------------------------------------------------------------------------------------
# CLI (envoltorio en scripts/meta_crear.py)
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """``python -m meta.crear --oferta OF-… --campana campana.json --creativos creativos.json --ad-account act_… --pixel-id PX…``."""
    ap = argparse.ArgumentParser(prog="python -m meta.crear", description="Borrador de campaña en Meta (todo PAUSED), idempotente por nombre.")
    ap.add_argument("--campana", required=True, help="ruta a campana.json (estado borrador o preflight_ok)")
    ap.add_argument("--creativos", required=True, help="JSON {ad_name: payload de act_<id>/adcreatives}")
    ap.add_argument("--ad-account", required=True, dest="ad_account")
    ap.add_argument("--pixel-id", required=True, dest="pixel_id")
    ap.add_argument("--salida", help="ruta donde escribir ids_meta.json; si se omite, solo se imprime")
    _cli_comun.agregar_argumentos_comunes(ap)
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if (args.raiz or args.ahora) and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz y --ahora no existen con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz(env)
        reloj = (lambda: comun.parsear_z(args.ahora)) if args.ahora else comun.ahora_utc
        campana = comun.cargar_json(Path(args.campana))
        creativos = comun.cargar_json(Path(args.creativos))
        if campana.get("oferta_id") != args.oferta:
            raise ErrorUso(f"--oferta {args.oferta!r} no coincide con campana.oferta_id {campana.get('oferta_id')!r}")

        if args.modo == "dry-run":
            plan = {
                "campaign": payloads.payload_campana(campana),
                "anuncios": sorted((campana.get("anuncios") or []), key=lambda a: a["ad_name"]),
            }
            _cli_comun.imprimir(ok=True, modo="dry_run", codigo=0, datos=plan, avisos=[], as_json=args.json)
            return 0

        lim = motor_limites.cargar_limites(raiz / "empresa" / "limites.yaml", env=env)
        cliente, _ = _cli_comun.construir_cliente(
            args, env, segundos_min_entre_ediciones=lim.valor("segundos_min_entre_ediciones"),
            max_cambios_presupuesto_por_hora=lim.valor("max_cambios_presupuesto_por_hora_por_conjunto"),
        )
        resultado = crear(oferta_id=args.oferta, campana=campana, cliente=cliente, ad_account_id=args.ad_account,
                          pixel_id=args.pixel_id, payloads_creativo=creativos)
        ids_meta = resultado.como_ids_meta(
            oferta_id=args.oferta, creado_en=comun.iso_z(comun.instante(reloj)), hash_config=campana.get("hash_config") or ""
        )
        if args.salida:
            comun.escribir_atomico(Path(args.salida), comun.json_canonico(ids_meta))
        _cli_comun.imprimir(ok=True, modo=args.modo, codigo=0, datos=ids_meta, avisos=[], as_json=args.json)
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
