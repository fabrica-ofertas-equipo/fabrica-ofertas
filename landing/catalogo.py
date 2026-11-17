"""``landing.catalogo``: catálogo firmado ``oferta_id -> price_id`` (con ``ids_meta`` si ya existen).

Lo consume el Worker ``crear-sesion`` (B2): el precio nunca lo manda el navegador, solo este
catálogo; ``cid``/``asid``/``adid`` solo se aceptan si figuran en ``ids_meta`` del catálogo
(docs/06 §4.3). No llama a Stripe: los ``price_id`` ya existen en ``checkout.json`` (los crea el
Maker de D5 o, cuando exista, ``infra.alta_oferta``); este módulo solo los empaqueta, firma y
escribe ``05-landing/catalogo.json``. Firma **HMAC** (pruebas y servicio a servicio, convenciones
§5); Ed25519 queda para cuando exista una clave de catálogo propia (ver README, «Pedidos»).

CLI::

    python -m landing.catalogo --oferta OF-202611-01 --raiz /tmp/prueba --clave-env CATALOGO_HMAC --json

Salida: 0 escrito · 2 falta ``--clave-env`` o la variable · 3 ``checkout.json``/``ids_meta.json`` inválido.
"""
from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Sequence

from engine import comun
from engine.errores import ErrorUso
from landing import comun as lcomun

__all__ = ["construir_catalogo", "main"]


def _ids_meta(dir_oferta: Path) -> dict[str, Any] | None:
    p = dir_oferta / "07-campana" / "ids_meta.json"
    return comun.cargar_json(p) if p.is_file() else None


def _renuncia(checkout: dict[str, Any]) -> dict[str, Any] | None:
    """``renuncia{requerido, texto_version}`` SOLO si ``checkout.compra.renuncia`` trae ambos con tipo válido; si no, se omite (decide el Worker)."""
    r = lcomun.compra_de(checkout).get("renuncia")
    if not isinstance(r, dict) or not isinstance(r.get("requerido"), bool):
        return None
    version = r.get("texto_version")
    if not isinstance(version, str) or not version:
        return None
    return {"requerido": r["requerido"], "texto_version": version}


def construir_catalogo(dir_oferta: Path, checkout: dict[str, Any], *, clave: bytes,
                       ahora: Callable[[], datetime] = comun.ahora_utc) -> dict[str, Any]:
    """Cuerpo firmado del catálogo (sin escribir), esquema ``contratos/catalogo.schema.json`` 1.0.0.

    ``price_ids`` y ``success_url``/``return_url`` vienen de ``checkout.json`` (el precio nunca lo manda el navegador); ``ids_meta`` usa los
    nombres de ``ids_meta.json`` (``campaign_id`` escalar o ``null``; ``adset_ids`` y ``ad_ids`` listas, vacías si la campaña aún no existe);
    ``landing_version`` y ``renuncia`` salen de ``checkout.compra`` y solo se emiten si existen (opcionales en el contrato). El bloque firmado
    es el cuerpo completo salvo ``firma`` (igual que un sello, convenciones §5).
    """
    ids = _ids_meta(dir_oferta)
    cuerpo: dict[str, Any] = {
        "schema_version": "1.0.0",
        "oferta_id": checkout["oferta_id"],
        "version": checkout["version"],
        "moneda": checkout["moneda"],
        "price_ids": {
            "principal": checkout["price_ids"]["test"],
            **({"bump": checkout["bump"]["price_id"]} if checkout.get("bump") else {}),
        },
        "ids_meta": {
            "campaign_id": ids["campaign_id"] if ids else None,
            "adset_ids": list(ids["adset_ids"]) if ids else [],
            "ad_ids": list(ids["ad_ids"]) if ids else [],
        },
        "generado_en": comun.iso_z(comun.instante(ahora)),
    }
    for campo in ("success_url", "return_url"):
        if checkout.get(campo):
            cuerpo[campo] = checkout[campo]
    version_landing = lcomun.landing_version(checkout)
    if version_landing:
        cuerpo["landing_version"] = version_landing
    renuncia = _renuncia(checkout)
    if renuncia:
        cuerpo["renuncia"] = renuncia
    cuerpo["firma"] = comun.firma_hmac(cuerpo, clave)
    return cuerpo


def main(argv: Sequence[str] | None = None) -> int:
    ap = lcomun.argparser_base("Construye y firma 05-landing/catalogo.json (oferta_id -> price_id, con ids_meta si existen).")
    ap.add_argument("--clave-env", default="CATALOGO_HMAC", help="variable de entorno con la clave HMAC (por defecto CATALOGO_HMAC)")
    args = ap.parse_args(argv)

    def cuerpo() -> int:
        env = lcomun.entorno_de_proceso()
        raiz = lcomun.raiz_de_argumentos(args, env)
        d = lcomun.dir_oferta(args.oferta, raiz=raiz)
        clave_texto = env.get(args.clave_env)
        if not clave_texto:
            raise ErrorUso(f"falta la variable de entorno {args.clave_env} con la clave HMAC del catálogo")
        checkout = lcomun.cargar_checkout(d)
        catalogo = construir_catalogo(d, checkout, clave=clave_texto.encode("utf-8"))
        if args.live:
            comun.escribir_atomico(d / "05-landing" / "catalogo.json", comun.json_canonico(catalogo))
        datos = {"oferta_id": args.oferta, "price_ids": catalogo["price_ids"], "ids_meta": catalogo["ids_meta"]}
        if args.json:
            import json as _json
            print(_json.dumps({"ok": True, "modo": "live" if args.live else "dry_run", "codigo": 0, "datos": datos, "avisos": []},
                              sort_keys=True, ensure_ascii=False))
        else:
            print(f"catálogo {'escrito' if args.live else '(plan)'}: {datos}")
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
