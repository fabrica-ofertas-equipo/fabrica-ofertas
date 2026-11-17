"""``compliance.verificar``: valida un sello de X1 justo antes de usarlo (docs/06 §4.2, §4.5, N12).

**Firma congelada que esperan otros componentes** (B5 ``meta.activar``, B4 ``landing.desplegar``,
docs/06 §4.5): ``verificar_sello(clave_sello: str, ahora: datetime) -> dict | None``.
``clave_sello`` es el ``artefacto_sha256`` (``sha256:<hex>``) a buscar en
``empresa/compliance/sellos/<hex>.json``; ``ahora`` es un instante YA resuelto (no un reloj
inyectable: quien llama ya lo sacó de ``engine.comun.instante``). **Nunca lanza**: cualquier
problema (archivo ausente, esquema inválido, firma que no verifica, vencido, ``artefacto_sha256``
que no coincide con la clave con la que se buscó) devuelve ``None`` — fail-closed, quien llama
trata ``None`` como «no activar, no publicar». Resuelve la raíz con ``engine.comun.raiz()`` (osea
``FABRICA_RAIZ`` si está fijada) y las claves de verificación desde el entorno
(``FABRICA_FIRMA_PUBLICA`` para Ed25519, ``SELLO_X1_CLAVE`` para HMAC fuera de producción — nunca en
el entorno de los agentes, A5 H7).

Esta función SOLO valida que el sello en sí sea legítimo y esté vigente: el re-chequeo de uso exacto
(re-hash del artefacto en ESE instante, ``object_ids`` exactos de ESA activación) lo hace quien llama
con ``scripts.validar_esquemas.problemas_uso_sello`` justo antes de usarlo (así lo hace ya
``meta.activar._sello_vigente``): dos capas, una no sustituye a la otra.

La CLI (``python -m compliance.verificar``) añade sobre esto, para uso humano/manual, la
comprobación de uso con un ``--artefacto-sha256``/``--object-ids`` explícitos y sale **4** si el
sello no es válido o no sirve para ese uso.
"""
from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path
from typing import Mapping

from engine import comun
from engine.errores import ErrorBloqueado, ErrorFabrica, ErrorUso
from scripts.validar_esquemas import payload_firma, problemas_firma, problemas_uso_sello

from compliance.sellar import VAR_CLAVE_HMAC_PRUEBA, ruta_sello

__all__ = ["VAR_CLAVE_HMAC_PRUEBA", "main", "verificar_sello", "verificar_sello_o_fallar"]


def _verificador_y_clave_hmac(env: Mapping[str, str]) -> tuple[object, bytes | None]:
    clave_publica = env.get("FABRICA_FIRMA_PUBLICA")
    verificador = (lambda datos, firma: comun.verificar_ed25519(datos, firma, clave_publica)) if clave_publica else None
    clave_hmac_env = env.get(VAR_CLAVE_HMAC_PRUEBA)
    return verificador, (clave_hmac_env.encode("utf-8") if clave_hmac_env else None)


def _cargar_y_validar_forma(ruta: Path) -> dict | None:
    """Carga ``ruta`` y exige que cumpla ``sello.schema.json``; ``None`` ante cualquier problema (fail-closed)."""
    try:
        sello = comun.cargar_json(ruta)
    except (FileNotFoundError, OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(sello, dict) or comun.errores_de_esquema("sello", sello):
        return None
    return sello


def verificar_sello(clave_sello: str, ahora: datetime, *, raiz: Path | None = None, env: Mapping[str, str] | None = None) -> dict | None:
    """Firma congelada (docs/06 §4.5): ``clave_sello`` = ``artefacto_sha256``; ``ahora`` = instante UTC.

    ``raiz``/``env`` son opcionales (por defecto, ``engine.comun.raiz()``/``os.environ``): existen
    para que las pruebas no dependan de variables de entorno globales, pero la llamada que esperan
    ``meta.activar``/``landing.desplegar`` es de solo dos argumentos posicionales.
    """
    env = os.environ if env is None else env
    try:
        raiz_efectiva = raiz if raiz is not None else comun.raiz(env)
        ruta = ruta_sello(clave_sello, raiz=raiz_efectiva)
        entorno = comun.entorno(env)
    except ErrorFabrica:
        # Resolver la raíz o el entorno puede fallar (FABRICA_RAIZ/FABRICA_ENTORNO mal puestos): no
        # es un bug de este módulo, es "no se puede confirmar que el sello sirva" (fail-closed, None).
        return None
    sello = _cargar_y_validar_forma(ruta)
    if sello is None or sello.get("artefacto_sha256") != clave_sello:
        return None
    if not isinstance(ahora, datetime) or ahora.tzinfo is None:
        return None
    verificador, clave_hmac = _verificador_y_clave_hmac(env)
    payload = payload_firma("sello", sello)
    if problemas_firma(sello.get("firma"), payload, clave_hmac, entorno=entorno, obligatoria=True, verificador=verificador):
        return None
    if problemas_uso_sello(sello, artefacto_sha256=clave_sello, object_ids=sello.get("object_ids") or [], ahora=ahora):
        return None
    return sello


def verificar_sello_o_fallar(clave_sello: str, ahora: datetime, *, raiz: Path | None = None, env: Mapping[str, str] | None = None,
                             artefacto_sha256: str | None = None, object_ids: list[str] | None = None) -> dict:
    """Como :func:`verificar_sello`, pero para uso humano/CLI: lanza ``ErrorBloqueado`` (4) en vez de
    devolver ``None``, y permite pedir el chequeo de uso (TOCTOU) contra un ``artefacto_sha256``/
    ``object_ids`` explícitos (distintos de ``clave_sello``, útil para probar "¿este sello sirve para
    ESTE otro artefacto?").
    """
    sello = verificar_sello(clave_sello, ahora, raiz=raiz, env=env)
    if sello is None:
        raise ErrorBloqueado(f"sin sello de X1 vigente y válido para {clave_sello}")
    if artefacto_sha256 is not None or object_ids is not None:
        objetivo_artefacto = artefacto_sha256 if artefacto_sha256 is not None else clave_sello
        objetivo_objetos = object_ids if object_ids is not None else (sello.get("object_ids") or [])
        problemas = problemas_uso_sello(sello, artefacto_sha256=objetivo_artefacto, object_ids=objetivo_objetos, ahora=ahora)
        if problemas:
            raise ErrorBloqueado("sello inválido para este uso: " + "; ".join(f"{c}: {m}" for c, m in problemas))
    return sello


def _construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m compliance.verificar", description="Imprime el sello vigente o sale 4.")
    p.add_argument("--hash", required=True, dest="clave_sello", help="artefacto_sha256 (sha256:<hex>) del sello a buscar")
    p.add_argument("--artefacto-sha256", default=None, help="re-hash recalculado del artefacto AHORA (TOCTOU); por defecto, --hash")
    p.add_argument("--object-ids", default=None, help="lista separada por comas que se va a usar; por defecto, la del sello")
    p.add_argument("--raiz", type=Path, default=None)
    p.add_argument("--ahora", default=None, help="instante UTC con Z (solo fuera de produccion); por defecto, ahora real")
    p.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    try:
        args = _construir_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        entorno = comun.entorno(env)
        if args.raiz and entorno == "produccion":
            raise ErrorUso("--raiz no existe con FABRICA_ENTORNO=produccion")
        if args.ahora and entorno == "produccion":
            raise ErrorUso("--ahora no existe con FABRICA_ENTORNO=produccion")
        raiz = args.raiz.resolve() if args.raiz else comun.raiz(env)
        momento = comun.parsear_z(args.ahora) if args.ahora else comun.ahora_utc()
        object_ids = [x for x in args.object_ids.split(",") if x] if args.object_ids is not None else None
        sello = verificar_sello_o_fallar(args.clave_sello, momento, raiz=raiz, env=env,
                                        artefacto_sha256=args.artefacto_sha256, object_ids=object_ids)
        salida = {"ok": True, "modo": "dry_run", "codigo": 0, "datos": sello, "avisos": []}
        if args.json:
            print(comun.json_canonico(salida).decode("utf-8"))
        else:
            print(f"VIGENTE: {sello['artefacto_sha256']} hasta {sello['vigencia_hasta']} ({sello['etapa_objetivo']})")
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    import sys

    sys.exit(main())
