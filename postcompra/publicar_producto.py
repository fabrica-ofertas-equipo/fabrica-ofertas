"""``postcompra.publicar_producto``: empaqueta un ``producto.json`` aprobado para la entrega (D4 → D10).

``python -m postcompra.publicar_producto --oferta OF-... [--raiz R]``

Lee ``ofertas/<id>/04-producto/producto.json`` (propiedad de D4/maker; aquí solo se LEE), exige
``estado == "aprobado"`` y que cada ítem con ``en_paquete: true`` siga teniendo el ``sha256`` que D4
aprobó (si el archivo cambió desde entonces, se rechaza: una entrega no puede mandar algo distinto de
lo que QA vio). Con eso arma un ``.zip`` determinista (fecha fija, sin metadatos del sistema de
archivos) y ``paquete.json`` con el ``producto_sha256`` que ``entrega.schema.json`` espera: el hash del
MAPA ``item_id -> sha256`` (no de los bytes del zip, que no son deterministas por compresión). El
Worker ``fulfill`` y ``postcompra.reembolsar``/``evidencia`` leen ``paquete.json``, no el zip, para
saber qué versión y qué hash corresponden a la entrega vigente.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion
from postcompra import _comun

__all__ = ["ResultadoPublicacion", "main", "publicar_producto"]

_FECHA_ZIP_FIJA = (2026, 1, 1, 0, 0, 0)  # determinismo del .zip: ningún metadato del sistema de archivos


@dataclass(frozen=True)
class ResultadoPublicacion:
    """Lo que quedó escrito: la ruta del paquete y el ``producto_sha256`` vigente."""

    ruta_paquete_json: Path
    ruta_zip: Path
    producto_sha256: str
    version: str


def _ruta_producto(raiz: Path, oferta_id: str) -> Path:
    return raiz / "ofertas" / _comun.exigir_oferta_id(oferta_id) / "04-producto" / "producto.json"


def _dir_paquete(raiz: Path, oferta_id: str) -> Path:
    return _comun.dir_postcompra(raiz, oferta_id) / "paquete"


def publicar_producto(*, oferta_id: str, raiz: Path) -> ResultadoPublicacion:
    """Valida y empaqueta el producto aprobado de ``oferta_id``; devuelve dónde quedó."""
    oferta_id = _comun.exigir_oferta_id(oferta_id)
    ruta_producto = _ruta_producto(raiz, oferta_id)
    try:
        producto = comun.cargar_json(ruta_producto)
    except FileNotFoundError as exc:
        raise ErrorValidacion(f"falta {ruta_producto}: D4 todavía no entregó un producto.json") from exc
    errores = comun.errores_de_esquema("producto", producto)
    if errores:
        raise ErrorValidacion(f"{ruta_producto.name} no cumple producto.schema.json: {comun.resumir_errores_esquema(errores)}")
    if producto.get("oferta_id") != oferta_id:
        raise ErrorValidacion(f"producto.json es de la oferta {producto.get('oferta_id')}, se pidió {oferta_id}")
    if producto.get("estado") != "aprobado":
        raise ErrorValidacion(f"producto.json está en estado {producto.get('estado')!r}: solo se publica lo aprobado")

    items_paquete: list[dict[str, Any]] = [it for it in producto["items"] if it.get("en_paquete")]
    if not items_paquete:
        raise ErrorValidacion("producto.json no tiene ningún ítem con en_paquete=true")

    dir_producto = ruta_producto.parent
    manifiesto: dict[str, str] = {}
    rutas_reales: dict[str, Path] = {}
    for item in sorted(items_paquete, key=lambda it: it["id"]):
        ruta_item = dir_producto / item["archivo"]
        if not ruta_item.is_file():
            raise ErrorValidacion(f"falta el archivo del ítem {item['id']}: {ruta_item}")
        actual = comun.hash_archivo(ruta_item)
        if actual != item["sha256"]:
            raise ErrorValidacion(
                f"el ítem {item['id']} cambió desde que se aprobó (hash {item['sha256']}, ahora {actual}): "
                "no se publica lo que QA no vio",
            )
        manifiesto[item["id"]] = actual
        rutas_reales[item["id"]] = ruta_item

    archivo_por_id = {it["id"]: it["archivo"] for it in items_paquete}
    producto_sha256 = comun.hash_objeto(manifiesto)
    version = str(producto["version"])
    dir_paquete = _dir_paquete(raiz, oferta_id)
    dir_paquete.mkdir(parents=True, exist_ok=True)
    ruta_zip = dir_paquete / f"producto-{version}.zip"
    _escribir_zip_determinista(ruta_zip, rutas_reales)

    datos_paquete = {
        "producto_id": producto["producto_id"],
        "oferta_id": oferta_id,
        "version": version,
        "producto_sha256": producto_sha256,
        "zip_sha256": comun.hash_archivo(ruta_zip),
        "items": [{"id": i, "archivo": archivo_por_id[i], "sha256": h} for i, h in sorted(manifiesto.items())],
    }
    ruta_paquete_json = dir_paquete / f"paquete-{version}.json"
    comun.escribir_atomico(ruta_paquete_json, comun.json_canonico(datos_paquete))
    return ResultadoPublicacion(ruta_paquete_json=ruta_paquete_json, ruta_zip=ruta_zip, producto_sha256=producto_sha256,
                                version=version)


def _escribir_zip_determinista(ruta_zip: Path, rutas_por_id: dict[str, Path]) -> None:
    """Escribe un ``.zip`` con fecha fija y orden estable: mismos ítems => mismos bytes."""
    temporal = ruta_zip.with_suffix(ruta_zip.suffix + ".tmp")
    with zipfile.ZipFile(temporal, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item_id in sorted(rutas_por_id):
            ruta = rutas_por_id[item_id]
            info = zipfile.ZipInfo(filename=ruta.name, date_time=_FECHA_ZIP_FIJA)
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, ruta.read_bytes())
    os.replace(temporal, ruta_zip)


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """CLI: ``python -m postcompra.publicar_producto --oferta OF-... [--raiz R] [--json]``. Sin efectos externos."""
    ap = argparse.ArgumentParser(prog="python -m postcompra.publicar_producto", description="Empaqueta el producto aprobado para la entrega.")
    ap.add_argument("--oferta", required=True)
    ap.add_argument("--raiz")
    ap.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if args.raiz and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz no existe con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz(env)
        resultado = publicar_producto(oferta_id=args.oferta, raiz=raiz)
        datos = {"paquete_json": str(resultado.ruta_paquete_json), "zip": str(resultado.ruta_zip),
                "producto_sha256": resultado.producto_sha256, "version": resultado.version}
        if args.json:
            print(json.dumps({"ok": True, "modo": "dry_run", "codigo": 0, "datos": datos, "avisos": []}, sort_keys=True, ensure_ascii=False))
        else:
            print(f"PRODUCTO PUBLICADO {resultado.version}: {json.dumps(datos, ensure_ascii=False, sort_keys=True)}")
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
