"""``landing.desplegar``: publica (o revierte) ``05-landing/sitio/``.

Dry-run por defecto: calcula el plan (re-hash de ``sitio/`` justo antes de "subir") y no toca nada.
Con ``--live``:

* ``--entorno preview`` siempre se permite (vista previa, sin gate): copia ``sitio/`` a un
  historial local (``05-landing/_despliegues/<tag>/``) y anota la entrada.
* ``--entorno produccion`` rechaza (``ErrorBloqueado``, código 4) un ``sitio/`` con CUALQUIER marca de demostración de la vista previa (``landing.validar.marcas_de_demo``:
  ``data-demo``, cinta «DEMO», «VISTA PREVIA», marcadores «[vista previa…]»), también en dry-run, y además exige, en este orden: ``FABRICA_ENTORNO=produccion`` · sin
  ``empresa/PAUSA`` · un sello de X1 vigente (``empresa/compliance/sellos/``) cuyo
  ``artefacto_sha256`` coincida con el hash **recién calculado** de ``sitio/`` (re-hash justo
  antes de subir, docs/contratos.md §1). La verificación criptográfica de la firma del sello es de
  ``compliance.verificar`` (B6, aún no construido): hasta entonces aquí solo se comprueba
  presencia, esquema, hash y vigencia (ver README, «Decisiones» y «Pedidos»).

``--rollback-a TAG`` restaura un despliegue anterior del historial (verifica su hash) en vez de
publicar el estado actual.

CLI::

    python -m landing.desplegar --oferta OF-202611-01 --entorno preview --raiz /tmp/prueba --json
    python -m landing.desplegar --oferta OF-202611-01 --entorno preview --live --raiz /tmp/prueba
    python -m landing.desplegar --oferta OF-202611-01 --entorno preview --rollback-a 2026-11-06T00-00-00Z --live --raiz /tmp/prueba

Salida: 0 (plan u operación realizada) · 2 uso · 3 artefacto o tag inválido · 4 bloqueado
(``PAUSA``, entorno, sin sello vigente).
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Any, Sequence

from engine import comun, guard
from engine.errores import ErrorBloqueado, ErrorUso, ErrorValidacion
from landing import comun as lcomun
from landing import validar as lvalidar

__all__ = ["desplegar", "rollback", "main"]

CARPETA_HISTORIAL = "_despliegues"


def _carpeta_historial(land: Path) -> Path:
    return land / CARPETA_HISTORIAL


def _historial(land: Path) -> list[dict[str, Any]]:
    return comun.leer_jsonl(_carpeta_historial(land) / "historial.jsonl")


def _rechazar_demo(carpeta: Path, *, donde: str) -> None:
    """Producción NUNCA publica contenido de demostración: ``ErrorBloqueado`` si algún HTML de ``carpeta`` lleva una marca de la vista previa."""
    for ruta in sorted(carpeta.rglob("*.html")):
        marcas = lvalidar.marcas_de_demo(ruta.read_text(encoding="utf-8"))
        if marcas:
            raise ErrorBloqueado(f"{donde}: {ruta.relative_to(carpeta).as_posix()} lleva contenido de demostración o de vista previa ({'; '.join(marcas)}): "
                                 "no se publica en producción (genera el sitio sin --vista-previa)")


def _sello_vigente_para(raiz: Path, hash_sitio: str, *, ahora) -> dict[str, Any]:
    """Un sello de X1 en ``empresa/compliance/sellos/`` para D5 con ``artefacto_sha256 == hash_sitio`` y vigente."""
    carpeta = raiz / "empresa" / "compliance" / "sellos"
    if not carpeta.is_dir():
        raise ErrorBloqueado("no hay sellos de X1 en empresa/compliance/sellos/: falta aprobación de cumplimiento")
    t = comun.instante(ahora)
    candidatos = []
    for p in sorted(carpeta.glob("*.json")):
        try:
            sello = comun.cargar_json(p)
        except (OSError, ValueError, UnicodeDecodeError):
            continue
        if comun.errores_de_esquema("sello", sello):
            continue
        candidatos.append(sello)
    for sello in candidatos:
        if sello.get("etapa_objetivo") != "D5" or sello.get("artefacto_sha256") != hash_sitio:
            continue
        try:
            vigencia = comun.parsear_z(sello["vigencia_hasta"])
        except ErrorValidacion:
            continue
        if vigencia >= t:
            return sello
    raise ErrorBloqueado(f"sin sello de X1 vigente para D5 cuyo artefacto_sha256 sea {hash_sitio}")


def desplegar(dir_oferta: Path, *, entorno: str, tag: str, live: bool, raiz: Path, ahora=comun.ahora_utc,
             env: dict[str, str] | None = None, carpeta: str = "sitio") -> dict[str, Any]:
    """Calcula el plan de publicación y, con ``live=True``, lo ejecuta (copia a un historial local).

    Devuelve ``{hash_sitio, entorno, tag, modo}``. Errores: ``ErrorBloqueado`` (4) si ``produccion``
    no tiene PAUSA despejada y sello vigente; ``ErrorValidacion`` (3) si ``sitio/`` no existe.
    """
    land = dir_oferta / "05-landing"
    if entorno == "produccion" and carpeta != "sitio":
        raise ErrorBloqueado(f"producción solo publica 05-landing/sitio (no {carpeta!r}): la vista previa nunca se publica en producción")
    sitio = land / carpeta
    if not sitio.is_dir():
        raise ErrorValidacion(f"05-landing/{carpeta} no existe: corre landing.generar primero")
    if entorno == "produccion":
        _rechazar_demo(sitio, donde=f"05-landing/{carpeta}")        # antes que nada, también en dry-run
    hash_sitio = comun.hash_directorio(sitio)  # re-hash justo antes de "subir" (docs/contratos.md §1)
    plan = {"hash_sitio": hash_sitio, "entorno": entorno, "tag": tag, "modo": "dry_run"}
    if not live:
        return plan

    if entorno == "produccion":
        if guard.hay_pausa(raiz):
            raise ErrorBloqueado("existe empresa/PAUSA: no se publica en producción")
        if comun.entorno(env) != "produccion":
            raise ErrorBloqueado("--live --entorno produccion exige FABRICA_ENTORNO=produccion")
        _sello_vigente_para(raiz, hash_sitio, ahora=ahora)
    elif entorno != "preview":
        raise ErrorUso(f"--entorno desconocido: {entorno!r} (se espera preview o produccion)")

    destino = _carpeta_historial(land) / tag
    if destino.exists():
        raise ErrorValidacion(f"ya existe un despliegue con tag {tag!r}: elige otro")
    shutil.copytree(sitio, destino)
    comun.anexar_jsonl(_carpeta_historial(land) / "historial.jsonl",
                       {"ts": comun.iso_z(comun.instante(ahora)), "entorno": entorno, "tag": tag, "hash_sitio": hash_sitio, "accion": "publicar"})
    plan["modo"] = "live"
    return plan


def rollback(dir_oferta: Path, *, tag: str, entorno: str, live: bool, ahora=comun.ahora_utc) -> dict[str, Any]:
    """Restaura ``sitio/`` al despliegue ``tag`` del historial (verifica su hash antes de copiar).

    Dry-run (``live=False``) solo informa qué haría. Errores: ``ErrorValidacion`` si el tag no
    existe en el historial o el hash no coincide con lo guardado (archivo alterado).
    """
    land = dir_oferta / "05-landing"
    entradas = [e for e in _historial(land) if e["tag"] == tag]
    if not entradas:
        raise ErrorValidacion(f"no hay un despliegue con tag {tag!r} en el historial")
    origen = _carpeta_historial(land) / tag
    if not origen.is_dir():
        raise ErrorValidacion(f"falta la carpeta del despliegue {tag!r}: historial incompleto")
    if entorno == "produccion":
        _rechazar_demo(origen, donde=f"despliegue {tag}")
    hash_guardado = comun.hash_directorio(origen)
    if hash_guardado != entradas[-1]["hash_sitio"]:
        raise ErrorValidacion(f"el despliegue {tag!r} fue alterado: el hash no coincide con el historial")
    plan = {"hash_sitio": hash_guardado, "entorno": entorno, "tag": tag, "modo": "dry_run", "accion": "rollback"}
    if not live:
        return plan
    sitio = land / "sitio"
    if sitio.exists():
        shutil.rmtree(sitio)
    shutil.copytree(origen, sitio)
    comun.anexar_jsonl(_carpeta_historial(land) / "historial.jsonl",
                       {"ts": comun.iso_z(comun.instante(ahora)), "entorno": entorno, "tag": tag, "hash_sitio": hash_guardado, "accion": "rollback"})
    plan["modo"] = "live"
    return plan


def main(argv: Sequence[str] | None = None) -> int:
    ap = lcomun.argparser_base("Publica (o revierte) 05-landing/sitio/.")
    ap.add_argument("--entorno", required=True, choices=("preview", "produccion"))
    ap.add_argument("--carpeta", default="sitio", help="carpeta de 05-landing/ a publicar (por defecto sitio; la vista previa de landing.generar está en sitio-vista-previa y solo va a preview)")
    ap.add_argument("--rollback-a", dest="rollback_a", help="tag del historial a restaurar, en vez de publicar el estado actual")
    ap.add_argument("--tag", help="tag del despliegue nuevo (por defecto, el instante actual)")
    args = ap.parse_args(argv)

    def cuerpo() -> int:
        env = lcomun.entorno_de_proceso()
        raiz = lcomun.raiz_de_argumentos(args, env)
        d = lcomun.dir_oferta(args.oferta, raiz=raiz)
        if args.rollback_a:
            plan = rollback(d, tag=args.rollback_a, entorno=args.entorno, live=args.live)
        else:
            tag = args.tag or comun.iso_z(comun.ahora_utc()).replace(":", "-")
            plan = desplegar(d, entorno=args.entorno, tag=tag, live=args.live, raiz=raiz, env=env, carpeta=args.carpeta)
        if args.json:
            import json as _json
            print(_json.dumps({"ok": True, "modo": plan["modo"], "codigo": 0, "datos": plan, "avisos": []}, sort_keys=True, ensure_ascii=False))
        else:
            print(plan)
        return 0

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
