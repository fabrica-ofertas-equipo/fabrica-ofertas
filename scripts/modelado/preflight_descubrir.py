"""Preflight de D1 ("descubrir"): lo que hoy falta en el CLI del barrido (interfaces d1-v2 §0 n.10, §8.2 n.3).

``comprobar_descubrir(raiz, env, via=...)`` es la función que el CLI del barrido (``scripts/modelado/barrido/``,
de otra sesión; este módulo NO lo edita) puede llamar antes de gastar una sola consulta. Replica, en
modo **solo lectura**, el paso 0 de `docs/_historial/d1-v2-interfaces.md` §6.1:

1. ``empresa/PAUSA`` ausente (``engine.guard.hay_pausa``, función pública).
2. ``empresa/captura/freno.json``: su alcance es **solo** lo que usa Chrome (captura de fichas y de
   páginas de venta, ruta D). El barrido por el conector (``ads_library_search``) no usa Chrome y no
   depende del freno. Por eso ``via`` es **obligatoria, sin valor por defecto** (decisión de S-A del
   2026-11-06 a pedido de S-C, interfaces §6.4): ``via="captura_web"`` exige el freno ausente;
   ``via="conector"`` ignora el freno (pero sigue exigiendo PAUSA, infra y límites). Nunca lo borres,
   evadas ni reintentes: solo el dueño lo levanta.
3. ``empresa/infra/estado.json`` válido, ``modo = vivo``, semáforo y TODOS los ítems VERDE, no futuro
   y con menos de ``min(infra.hc_preflight_vigencia_horas, 6)`` horas.
4. ``engine.limites.exigir_operacion(lim, "descubrir")``: límites completos, coherentes y sellados.

No verifica la firma HMAC de ``estado.json`` (eso es del paso 3 de `engine.guard.comprobar_live`, para
operaciones que SÍ gastan o activan; este preflight es de solo lectura y no reemplaza ese guard antes
de cualquier `--live`). Tampoco comprueba el sello de recolección de X1 (su emisor no existe todavía,
interfaces §4.4) ni ``locales_permitidos`` (lo hace el llamador con su propio locale). Códigos de
salida (convenciones §8): 0 verde · 2 uso (``via`` inválida) · 4 bloqueado (PAUSA, freno con
``via="captura_web"``, o infra no verde) · 5 límite (faltan o son incoherentes). Sin red, sin escritura.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from engine import comun, limites as motor_limites, parametros as motor_parametros
from engine.errores import ErrorBloqueado, ErrorFabrica, ErrorLimite, ErrorUso
from engine.guard import hay_pausa
from scripts.validar_esquemas import infra_verde

PARAMETRO_VIGENCIA_INFRA = "infra.hc_preflight_vigencia_horas"
_TOPE_HORAS_BACKBONE = 6  # fijo por el backbone (docs/06 §4.2); un parámetro no lo puede subir


def _hay_freno_captura(raiz: Path) -> bool:
    """¿Existe ``empresa/captura/freno.json``? Error al comprobarlo cuenta como «hay freno» (fail-closed)."""
    import os

    try:
        os.lstat(raiz / "empresa" / "captura" / "freno.json")
    except FileNotFoundError:
        return False
    except OSError:
        return True
    return True


def _comprobar_infra(raiz: Path, ahora: Any) -> str:
    ruta = raiz / "empresa" / "infra" / "estado.json"
    try:
        estado = comun.cargar_json(ruta)
    except FileNotFoundError as exc:
        raise ErrorBloqueado("falta empresa/infra/estado.json: sin infraestructura verde no corre el barrido") from exc
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise ErrorBloqueado("empresa/infra/estado.json ilegible") from exc
    if not isinstance(estado, dict):
        raise ErrorBloqueado("empresa/infra/estado.json ilegible: se esperaba un objeto")
    if comun.errores_de_esquema("infra_estado", estado):
        raise ErrorBloqueado("empresa/infra/estado.json no cumple infra_estado.schema.json")
    if estado.get("modo") != "vivo":
        raise ErrorBloqueado(f"infraestructura en modo {estado.get('modo')!r}: se exige «vivo»")
    try:
        maximo_h = motor_parametros.cargar_parametros(raiz / "empresa" / "parametros.yaml").valor(
            PARAMETRO_VIGENCIA_INFRA)
    except ErrorFabrica as exc:
        raise ErrorBloqueado(f"no se pudo leer {PARAMETRO_VIGENCIA_INFRA}: {exc.mensaje}") from exc
    if isinstance(maximo_h, bool) or not isinstance(maximo_h, int) or maximo_h < 1:
        raise ErrorBloqueado(f"{PARAMETRO_VIGENCIA_INFRA} inválido")
    verde, motivo = infra_verde(estado, ahora, min(maximo_h, _TOPE_HORAS_BACKBONE), exigir_modo="vivo")
    if not verde:
        raise ErrorBloqueado(f"infraestructura no verde: {motivo}")
    return str(estado["generado_en"])


VIAS_VALIDAS = ("conector", "captura_web")


def comprobar_descubrir(raiz: Path | None = None, env: Mapping[str, str] | None = None, *,
                        via: str, ahora=comun.ahora_utc) -> dict[str, Any]:
    """Preflight de solo lectura para `descubrir`. Devuelve un resumen si todo está en orden.

    ``via`` (obligatoria, sin valor por defecto; interfaces §6.4): ``"conector"`` (``ads_library_search``,
    no usa Chrome: el freno de captura NO lo bloquea) o ``"captura_web"`` (``captura.py``, ``enlaces.py``,
    rutas B/C/D: el freno SIGUE bloqueando). ``ErrorUso`` (2) si ``via`` no es una de las dos.
    ``ErrorBloqueado`` (4) ante PAUSA, freno de captura (solo con ``via="captura_web"``) o
    infraestructura no verde; ``ErrorLimite`` (5) si ``empresa/limites.yaml`` no alcanza para la
    operación «descubrir» (claves críticas, sello, coherencia -- ``engine.limites.exigir_operacion``,
    fail-closed).
    """
    if via not in VIAS_VALIDAS:
        raise ErrorUso(f"via inválida: {via!r} (se espera uno de {VIAS_VALIDAS})")
    base = raiz or comun.raiz(env)
    variables = env if env is not None else None
    if hay_pausa(base):
        raise ErrorBloqueado("existe empresa/PAUSA: se aborta y cancela todo barrido")
    freno_aplica = via == "captura_web"
    if freno_aplica and _hay_freno_captura(base):
        raise ErrorBloqueado("existe empresa/captura/freno.json: todo lo que use Chrome está detenido "
                             "(via=captura_web); el conector (ads_library_search) no usa Chrome y no "
                             "está bloqueado por este freno, pero sí por PAUSA, la infraestructura y los límites")
    infra_generado_en = _comprobar_infra(base, ahora)
    lim = motor_limites.cargar_limites(base / "empresa" / "limites.yaml", env=variables)
    motor_limites.exigir_operacion(lim, "descubrir")
    return {"ok": True, "via": via, "freno_aplica": freno_aplica, "infra_generado_en": infra_generado_en,
            "hash_limites": lim.hash_calculado}


# ---------------------------------------------------------------------------
# CLI de diagnóstico (no lo invoca el barrido; es para comprobar el estado a mano)
# ---------------------------------------------------------------------------
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.modelado.preflight_descubrir",
                                description="Preflight de solo lectura para la operación 'descubrir'")
    p.add_argument("--raiz", type=Path)
    p.add_argument("--via", required=True, choices=VIAS_VALIDAS,
                   help="'conector' (ads_library_search, sin freno) o 'captura_web' (con freno)")
    p.add_argument("--ahora", help="instante UTC ISO con Z, solo fuera de producción (pruebas)")
    p.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    def _principal() -> int:
        try:
            a = _parser().parse_args(argv)
        except SystemExit as exc:
            if exc.code in (0, None):
                return 0
            raise ErrorUso("argumentos inválidos (ver --help)") from None
        reloj = (lambda: comun.parsear_z(a.ahora)) if a.ahora else comun.ahora_utc
        resultado = comprobar_descubrir(a.raiz, ahora=reloj, via=a.via)
        if a.json:
            print(json.dumps(resultado, ensure_ascii=False, sort_keys=True))
        else:
            print(f"descubrir ({a.via}): VERDE (infra generado_en={resultado['infra_generado_en']})")
        return 0

    return comun.ejecutar_cli(_principal)


if __name__ == "__main__":
    raise SystemExit(main())
