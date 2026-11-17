"""``compliance.sellar``: sello de X1 sobre un artefacto (docs/06 N09, §4.5; ``contratos/sello.schema.json``).

Solo sella si el lint no dio ``rojo`` y el dictamen de QA es ``PASS`` o ``PASS_CON_NOTAS`` (docs/06
§4.5: "sello solo con lint sin ROJO, QA PASS y firmas H"). El payload firmado es el sello **sin**
``firma``, en JSON canónico (igual que documenta ``contratos/sello.schema.json``); la firma la
calcula quien llama (``firmar``): Ed25519 en el equipo del dueño, HMAC solo en pruebas — este
módulo nunca tiene ni pide la clave privada.

Dry-run por defecto (convenciones §9): sin ``--live`` solo se valida y se imprime el sello que se
escribiría, sin tocar ``empresa/compliance/sellos/``.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac as _hmac_mod
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Mapping, Sequence

from engine import comun, parametros as motor_parametros
from engine.errores import ErrorBloqueado, ErrorUso, ErrorValidacion
from scripts.validar_esquemas import CLAVE_DE_PRUEBA, payload_firma

from compliance.lint_claims import ResultadoLint, lint_claims
from compliance.reglas import cargar_reglas

__all__ = ["main", "ruta_sello", "sellar"]

_VEREDICTOS_QUE_SELLAN = ("PASS", "PASS_CON_NOTAS")
VAR_CLAVE_HMAC_PRUEBA = "SELLO_X1_CLAVE"  # fuera del entorno de los agentes (A5 H7); solo pruebas/servicio a servicio


def _firmar_hmac(datos: bytes, clave: bytes) -> str:
    """``hmac-sha256:<hex>`` sobre ``datos`` (ya el JSON canónico del payload): equivalente a
    ``scripts.validar_esquemas.firma_hmac(payload, clave)`` pero sin recanonizar lo ya canónico."""
    return "hmac-sha256:" + _hmac_mod.new(clave, datos, hashlib.sha256).hexdigest()


def ruta_sello(artefacto_sha256: str, *, raiz: Path) -> Path:
    """``empresa/compliance/sellos/<hex>.json`` a partir de ``sha256:<hex>``."""
    if not artefacto_sha256.startswith("sha256:"):
        raise ErrorValidacion("artefacto_sha256 debe tener la forma sha256:<64 hex>")
    return raiz / "empresa" / "compliance" / "sellos" / f"{artefacto_sha256[len('sha256:'):]}.json"


def _ruta_relativa(ruta: Path, raiz: Path) -> str:
    """``ruta`` relativa a ``raiz``, en formato ``ruta_relativa`` (``sello.schema.json``: sin ``/`` inicial ni ``..``).

    Errores: ``ErrorUso`` si ``ruta`` no está bajo ``raiz``: ``dictamen_ref`` no puede expresarse
    como ruta relativa de la oferta (el dictamen debe vivir dentro de la raíz de la corrida).
    """
    try:
        return ruta.relative_to(raiz).as_posix()
    except ValueError as exc:
        raise ErrorUso(f"--dictamen debe estar dentro de --raiz ({raiz}) para poder citarlo como dictamen_ref") from exc


def sellar(*, oferta_id: str, etapa_objetivo: str, artefacto_sha256: str, dictamen: Mapping[str, object],
          dictamen_ref: str, dictamen_sha256: str, lint: ResultadoLint, vigencia_dias: int,
          object_ids: Sequence[str] = (), ahora: Callable[[], datetime] = comun.ahora_utc,
          firmar: Callable[[bytes], str]) -> dict:
    """Construye y firma un sello (no lo escribe: ver :func:`compliance.sellar.main` para eso).

    Errores: ``ErrorBloqueado`` si el lint tiene hallazgos ``rojo`` o el dictamen no es
    ``PASS``/``PASS_CON_NOTAS`` (nunca se sella con un veto activo); ``ErrorValidacion`` si el sello
    resultante no cumple ``sello.schema.json``.
    """
    if lint.semaforo == "rojo":
        rojos = [h.patron_clave for h in lint.hallazgos if h.nivel == "rojo"]
        raise ErrorBloqueado(f"no se sella: el lint dio ROJO ({', '.join(rojos[:5])})")
    veredicto = dictamen.get("veredicto")
    if veredicto not in _VEREDICTOS_QUE_SELLAN:
        raise ErrorBloqueado(f"no se sella: el QA dio {veredicto!r} (se exige PASS o PASS_CON_NOTAS)")
    momento = comun.instante(ahora)
    sello_sin_firma = {
        "schema_version": "1.0.0",
        "oferta_id": oferta_id,
        "etapa_objetivo": etapa_objetivo,
        "artefacto_sha256": artefacto_sha256,
        "reglas_version": lint.reglas_version,
        "emitido_en": comun.iso_z(momento),
        "vigencia_hasta": comun.iso_z(momento + timedelta(days=vigencia_dias)),
        "object_ids": sorted(object_ids),
        "dictamen_ref": dictamen_ref,
        "dictamen_sha256": dictamen_sha256,
    }
    payload = payload_firma("sello", sello_sin_firma)  # == sello_sin_firma (sin "firma", que todavía no existe)
    sello = dict(sello_sin_firma, firma=firmar(comun.json_canonico(payload)))
    errores = comun.errores_de_esquema("sello", sello)
    if errores:
        raise ErrorValidacion(f"sello resultante inválido: {comun.resumir_errores_esquema(errores)}")
    return sello


def _construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m compliance.sellar", description=__doc__.splitlines()[0])
    p.add_argument("--oferta", required=True, help="OF-AAAAMM-NN")
    p.add_argument("--etapa-objetivo", required=True, dest="etapa_objetivo", help="M1..D10 (etapa_oferta)")
    p.add_argument("--artefacto", required=True, type=Path, help="archivo o carpeta a sellar (se hashea con hash_ruta)")
    p.add_argument("--dictamen", required=True, type=Path, help="qa/x1-<etapa>-v<n>.json")
    p.add_argument("--lint-archivo", type=Path, default=None, help="qué lintear (por defecto, --artefacto si es un archivo)")
    p.add_argument("--locale", required=True)
    p.add_argument("--macro-nicho", choices=("salud", "relaciones", "dinero"), default=None)
    p.add_argument("--object-ids", default="", help="lista separada por comas (D7); vacío en las demás etapas")
    p.add_argument("--vigencia-dias", type=int, default=None, help="por defecto, compliance.vigencia_dictamen_dias")
    p.add_argument("--raiz", type=Path, default=None)
    p.add_argument("--clave-privada", type=Path, default=None, help="clave Ed25519 del dueño (ssh-keygen); produccion la exige")
    p.add_argument("--live", action="store_true")
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
        raiz = args.raiz.resolve() if args.raiz else comun.raiz(env)
        if not args.dictamen.is_file():
            raise ErrorUso(f"no existe el dictamen: {args.dictamen}")
        dictamen_ref = _ruta_relativa(args.dictamen.resolve(), raiz)
        dictamen = comun.cargar_json(args.dictamen)
        dictamen_sha256 = comun.hash_archivo(args.dictamen)
        if not args.artefacto.exists():
            raise ErrorUso(f"no existe el artefacto a sellar: {args.artefacto}")
        artefacto_sha256 = comun.hash_ruta(args.artefacto)
        lint_objetivo = args.lint_archivo or (args.artefacto if args.artefacto.is_file() else None)
        reglas = cargar_reglas()
        lint = (lint_claims(lint_objetivo, locale=args.locale, macro_nicho=args.macro_nicho, reglas=reglas)
                if lint_objetivo is not None else ResultadoLint(reglas.reglas_version, "verde", ()))
        vigencia_dias = args.vigencia_dias
        if vigencia_dias is None:
            vigencia_dias = motor_parametros.cargar_parametros().valor("compliance.vigencia_dictamen_dias")
        object_ids = [x for x in args.object_ids.split(",") if x]

        if args.live:
            if args.clave_privada:
                firmar = lambda datos: comun.firmar_ed25519(datos, args.clave_privada)  # noqa: E731
            elif entorno == "produccion":
                raise ErrorUso("--live en produccion exige --clave-privada (Ed25519 del dueño)")
            else:
                clave = env.get(VAR_CLAVE_HMAC_PRUEBA)
                if not clave:
                    raise ErrorUso(f"--live fuera de producción exige --clave-privada o {VAR_CLAVE_HMAC_PRUEBA}")
                firmar = lambda datos: _firmar_hmac(datos, clave.encode("utf-8"))  # noqa: E731
        else:
            firmar = lambda datos: _firmar_hmac(datos, CLAVE_DE_PRUEBA)  # noqa: E731

        sello = sellar(
            oferta_id=args.oferta, etapa_objetivo=args.etapa_objetivo, artefacto_sha256=artefacto_sha256,
            dictamen=dictamen, dictamen_ref=dictamen_ref, dictamen_sha256=dictamen_sha256, lint=lint,
            vigencia_dias=vigencia_dias, object_ids=object_ids, firmar=firmar,
        )
        escrito = False
        if args.live:
            destino = ruta_sello(artefacto_sha256, raiz=raiz)
            comun.escribir_atomico(destino, (comun.json_canonico(sello) + b"\n"))
            escrito = True
        salida = {"ok": True, "modo": "live" if args.live else "dry_run", "codigo": 0,
                  "datos": {"sello": sello, "escrito": escrito}, "avisos": [] if args.live else ["dry-run: no se escribió el sello"]}
        if args.json:
            print(comun.json_canonico(salida).decode("utf-8"))
        else:
            print(f"{'ESCRITO' if escrito else 'VISTA PREVIA (dry-run)'}: {sello['artefacto_sha256']} vigente hasta {sello['vigencia_hasta']}")
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    import sys

    sys.exit(main())
