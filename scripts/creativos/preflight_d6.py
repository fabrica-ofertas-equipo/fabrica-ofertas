"""Preflight de D6 (paso 1 de ``departamentos/07-creativos.md`` §4): ¿se puede generar algo?

Comprueba, SIN gastar ni llamar a Higgsfield/Meta, lo que el flujo exige antes de que el Maker
empiece a trabajar: entradas y sellos vigentes, ``locale`` permitido, ausencia de ``empresa/PAUSA``,
``evaluar_limites('generar_creativos')`` verde, infraestructura VERDE y fresca (<6 h), que la landing
responda 200 y que haya navegador sin interfaz y fuentes disponibles.

Reutiliza la ÚNICA función compartida de las comprobaciones de dry-run/``--live``
(``engine.guard.comprobar_live``, convenciones §9) para PAUSA, infraestructura y límites: no se
copian esas reglas acá. El resultado es una TABLA de comprobaciones con VERDE, ROJO o NO_DISPONIBLE
y el motivo de cada una; nunca se marca verde algo que no se comprobó.

CLI::

    python -m scripts.creativos.preflight_d6 --oferta OF-202611-01 [--raiz RUTA] [--ahora ISO]
        [--navegador RUTA ...] [--fuente RUTA ...] [--url-landing URL] [--salida RUTA] [--json]

Salida (convenciones §8): 0 todo VERDE · 4 algo ROJO o NO_DISPONIBLE (no se puede generar) ·
2 uso incorrecto · 3 argumentos de entrada inválidos.

Decisiones (ver README):
* El cliente HTTP de "landing responde 200" es un parámetro inyectable; sin uno inyectado el ítem
  queda NO_DISPONIBLE (nunca se inventa un 200). La implementación SSRF-safe para uso real
  (``https`` solo, resolución validada) queda pedida a quien integre D7/D0 en vivo (ver «Pedidos»):
  esta sesión no hace peticiones de red.
* El sello de X1 se verifica con ``compliance.verificar.verificar_sello`` (inyectable para pruebas).
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from engine import comun, guard
from engine import limites as motor_limites
from engine.errores import ErrorFabrica, ErrorUso
from engine.transporte import TransporteFixture

from compliance.verificar import verificar_sello as _verificar_sello_x1

__all__ = ["Item", "comprobar", "main"]

VerificadorSello = Callable[..., "dict[str, Any] | None"]
ClienteGet = Callable[[str], int]

# Pasos de ``engine.guard.comprobar_live`` que cubren PAUSA, infraestructura y límites de una sola vez
# (convenciones §9: "las comprobaciones viven en una sola función compartida, no se copian").
_PASOS_GUARD: tuple[str, ...] = guard.PASOS
_ETIQUETA_PASO: dict[str, str] = {
    "entorno": "entorno_valido",
    "pausa": "sin_pausa",
    "infra": "infra_verde",
    "limites": "limites_generar_creativos",
    "topes": "topes_generar_creativos",
    "credenciales": "credenciales_generar_creativos",
    "aprobacion": "aprobacion_generar_creativos",
}


@dataclass(frozen=True)
class Item:
    """Una fila de la tabla de preflight: ``estado`` ∈ VERDE, ROJO, NO_DISPONIBLE."""

    id: str
    estado: str
    motivo: str

    def asdict(self) -> dict[str, str]:
        return {"id": self.id, "estado": self.estado, "motivo": self.motivo}


def _items_de_guard(raiz: Path, env: Mapping[str, str], ahora: Callable[[], datetime]) -> list[Item]:
    """Traduce ``comprobar_live('generar_creativos')`` a ítems VERDE/ROJO/NO_DISPONIBLE, en orden."""
    try:
        entorno_actual = comun.entorno(env)
    except ErrorUso as exc:
        return [Item(_ETIQUETA_PASO[p], "ROJO" if p == "entorno" else "NO_DISPONIBLE",
                    exc.mensaje if p == "entorno" else "no comprobado: el entorno es ilegible") for p in _PASOS_GUARD]
    simulacion = entorno_actual != "produccion"
    try:
        ctx = guard.comprobar_live(
            "generar_creativos", ahora=ahora, simulacion=simulacion,
            transporte=TransporteFixture() if simulacion else None, env=env, raiz=raiz,
        )
        return [Item(_ETIQUETA_PASO[p], "VERDE", "ok") for p in ctx.pasos]
    except ErrorFabrica as exc:
        ok = tuple(exc.detalle.get("pasos_ok", ()))
        paso_fallido = exc.detalle.get("paso")
        items = [Item(_ETIQUETA_PASO[p], "VERDE", "ok") for p in ok]
        if paso_fallido in _ETIQUETA_PASO:
            items.append(Item(_ETIQUETA_PASO[paso_fallido], "ROJO", exc.mensaje))
        restantes = [p for p in _PASOS_GUARD if p not in ok and p != paso_fallido]
        items += [Item(_ETIQUETA_PASO[p], "NO_DISPONIBLE", "no comprobado: un paso anterior bloqueó") for p in restantes]
        return items


def _item_locale_permitido(raiz: Path, env: Mapping[str, str], oferta_id: str) -> Item:
    ruta_mercado = raiz / "ofertas" / oferta_id / "mercado.json"
    try:
        mercado = comun.cargar_json(ruta_mercado)
    except FileNotFoundError:
        return Item("locale_permitido", "ROJO", "falta mercado.json")
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        return Item("locale_permitido", "ROJO", f"mercado.json ilegible: {exc}")
    locale = mercado.get("locale") if isinstance(mercado, dict) else None
    if not isinstance(locale, str) or not locale:
        return Item("locale_permitido", "ROJO", "mercado.json sin locale")
    try:
        lim = motor_limites.cargar_limites(raiz / "empresa" / "limites.yaml", env=env)
        permitidos = lim.valor("locales_permitidos")
    except ErrorFabrica as exc:
        return Item("locale_permitido", "ROJO", f"no se pudo leer locales_permitidos: {exc.mensaje}")
    if locale not in permitidos:
        return Item("locale_permitido", "ROJO", f"{locale} no está en locales_permitidos")
    return Item("locale_permitido", "VERDE", locale)


def _item_entradas_sello(raiz: Path, env: Mapping[str, str], oferta_id: str, ahora: datetime,
                         verificador_sello: VerificadorSello) -> list[Item]:
    items: list[Item] = []
    ruta_oferta = raiz / "ofertas" / oferta_id / "03-oferta" / "oferta.json"
    try:
        datos_oferta = comun.cargar_json(ruta_oferta)
    except FileNotFoundError:
        items.append(Item("entradas_oferta_valida", "ROJO", "falta 03-oferta/oferta.json"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        items.append(Item("entradas_oferta_valida", "ROJO", f"oferta.json ilegible: {exc}"))
    else:
        errores = comun.errores_de_esquema("oferta", datos_oferta)
        if errores:
            items.append(Item("entradas_oferta_valida", "ROJO", comun.resumir_errores_esquema(errores)))
        else:
            items.append(Item("entradas_oferta_valida", "VERDE", "oferta.json válido"))

    sitio = raiz / "ofertas" / oferta_id / "05-landing" / "sitio"
    if not sitio.is_dir():
        items.append(Item("sello_landing_vigente", "ROJO", "falta 05-landing/sitio/"))
        return items
    try:
        clave_sello = comun.hash_directorio(sitio)
    except OSError as exc:
        items.append(Item("sello_landing_vigente", "ROJO", f"no se pudo hashear 05-landing/sitio/: {exc}"))
        return items
    sello = verificador_sello(clave_sello, ahora, raiz=raiz, env=env)
    if sello is None:
        items.append(Item("sello_landing_vigente", "ROJO", f"sin sello de X1 vigente para {clave_sello}"))
    else:
        items.append(Item("sello_landing_vigente", "VERDE", f"vigente hasta {sello.get('vigencia_hasta')}"))
    return items


def _item_landing_200(url_landing: str | None, cliente_get: ClienteGet | None) -> Item:
    if not url_landing:
        return Item("landing_responde_200", "NO_DISPONIBLE", "sin --url-landing declarada")
    if cliente_get is None:
        return Item("landing_responde_200", "NO_DISPONIBLE", "sin cliente HTTP inyectado")
    try:
        estado = cliente_get(url_landing)
    except Exception as exc:  # noqa: BLE001 - red de seguridad: un cliente inyectado no debería lanzar
        return Item("landing_responde_200", "ROJO", f"fallo del cliente HTTP: {exc}")
    if estado == 200:
        return Item("landing_responde_200", "VERDE", f"GET {url_landing} -> 200")
    return Item("landing_responde_200", "ROJO", f"GET {url_landing} -> {estado}")


def _item_navegador(rutas: Sequence[Path]) -> Item:
    if not rutas:
        return Item("navegador_sin_interfaz", "NO_DISPONIBLE", "sin rutas de navegador declaradas (--navegador)")
    for r in rutas:
        try:
            if r.is_file() and os.access(r, os.X_OK):
                return Item("navegador_sin_interfaz", "VERDE", str(r))
        except OSError:
            continue
    return Item("navegador_sin_interfaz", "ROJO", f"ninguna ruta declarada es un ejecutable: {', '.join(map(str, rutas))}")


def _item_fuentes(rutas: Sequence[Path]) -> Item:
    if not rutas:
        return Item("fuentes_disponibles", "NO_DISPONIBLE", "sin fuentes declaradas (--fuente)")
    faltantes = [str(r) for r in rutas if not r.is_file()]
    if faltantes:
        return Item("fuentes_disponibles", "ROJO", f"faltan: {', '.join(faltantes)}")
    return Item("fuentes_disponibles", "VERDE", f"{len(rutas)} fuente(s) disponible(s)")


def comprobar(raiz: Path, oferta_id: str, *, env: Mapping[str, str] | None = None,
             ahora: Callable[[], datetime] = comun.ahora_utc, url_landing: str | None = None,
             cliente_get: ClienteGet | None = None, rutas_navegador: Sequence[Path] = (),
             rutas_fuentes: Sequence[Path] = (), verificador_sello: VerificadorSello = _verificar_sello_x1) -> dict[str, Any]:
    """Tabla completa de preflight de D6. Nunca lanza por un ítem individual: cada fallo queda en la tabla.

    ``semaforo`` es VERDE solo si TODOS los ítems son VERDE (ROJO y NO_DISPONIBLE bloquean generar).
    """
    env = os.environ if env is None else env
    instante = comun.instante(ahora)
    items: list[Item] = []
    items += _items_de_guard(raiz, env, ahora)
    items.append(_item_locale_permitido(raiz, env, oferta_id))
    items += _item_entradas_sello(raiz, env, oferta_id, instante, verificador_sello)
    items.append(_item_landing_200(url_landing, cliente_get))
    items.append(_item_navegador(list(rutas_navegador)))
    items.append(_item_fuentes(list(rutas_fuentes)))
    semaforo = "VERDE" if all(i.estado == "VERDE" for i in items) else "ROJO"
    return {"oferta_id": oferta_id, "generado_en": comun.iso_z(instante), "items": [i.asdict() for i in items], "semaforo": semaforo}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.creativos.preflight_d6", description="Preflight de D6 (paso 1): tabla VERDE/ROJO/NO_DISPONIBLE.")
    p.add_argument("--oferta", required=True, dest="oferta_id")
    p.add_argument("--raiz", type=Path, default=None)
    p.add_argument("--ahora", default=None, help="instante UTC con Z (solo fuera de producción)")
    p.add_argument("--url-landing", default=None)
    p.add_argument("--navegador", action="append", default=[], type=Path)
    p.add_argument("--fuente", action="append", default=[], type=Path)
    p.add_argument("--salida", type=Path, default=None, help="si se pasa, escribe el reporte ahí (JSON canónico)")
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
        if (a.raiz or a.ahora) and entorno_actual == "produccion":
            raise ErrorUso("--raiz y --ahora no existen con FABRICA_ENTORNO=produccion")
        raiz = a.raiz.resolve() if a.raiz else comun.raiz(env)
        reloj = (lambda: comun.parsear_z(a.ahora)) if a.ahora else comun.ahora_utc
        reporte = comprobar(raiz, a.oferta_id, env=env, ahora=reloj, url_landing=a.url_landing,
                            rutas_navegador=a.navegador, rutas_fuentes=a.fuente)
        if a.salida:
            comun.escribir_atomico(a.salida, comun.json_canonico(reporte))
        codigo = 0 if reporte["semaforo"] == "VERDE" else 4
        salida = {"ok": codigo == 0, "modo": "dry_run", "codigo": codigo, "datos": reporte, "avisos": []}
        if a.json:
            print(json.dumps(salida, sort_keys=True, ensure_ascii=False))
        else:
            for item in reporte["items"]:
                print(f"{item['estado']:13} {item['id']:30} {item['motivo']}")
            print(f"SEMÁFORO: {reporte['semaforo']}")
        return codigo

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    raise SystemExit(main())
