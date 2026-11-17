"""Cargador autosellado de ``compliance/reglas_sensibles.yaml`` (docs/06 §4.5, N09, G-13, D01).

El archivo lleva su propio ``reglas_version`` y un ``hash_contenido`` (sha256 del JSON canónico del
resto del archivo, igual que un sello). Si alguien edita un patrón sin recalcular el hash,
:func:`cargar_reglas` lo detecta y **el lint no corre**: "``reglas_claims.yaml`` ≠ ``reglas_version``
firmada → el lint no corre" (docs/06 N09). Esta es la única puerta de entrada a las reglas: nada en
``compliance`` lee el YAML directamente.

Decisión (fail-closed, ver ``compliance/README.md``): archivo ausente, ilegible o con el hash
alterado son ``ErrorValidacion`` (código 3): dato de entrada inconsistente para esta ejecución,
nunca un fallo interno ni un gasto/activación bloqueados (que serían 4/5).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from engine import comun
from engine.errores import ErrorValidacion

__all__ = [
    "MACRO_A_CATEGORIA", "NIVELES_VALIDOS", "Reglas", "cargar_reglas", "cargar_terminos_adicionales",
    "categorias_de_locale", "combinar_categorias", "resellar",
]

RUTA_POR_DEFECTO = Path(__file__).resolve().parent / "reglas_sensibles.yaml"
RUTA_TERMINOS_ADICIONALES = Path("empresa") / "compliance" / "terminos_sensibles"
CAMPO_HASH = "hash_contenido"
NIVELES_VALIDOS = ("verde", "amarillo", "rojo")
# macro_nicho del backbone (salud, relaciones, dinero) -> categoría de este archivo. "relaciones" ya
# tiene léxico propio desde la ola 2 (B6b); se mapea igual que las demás.
MACRO_A_CATEGORIA = {"salud": "salud", "dinero": "finanzas", "relaciones": "relaciones"}
_RX_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


@dataclass(frozen=True)
class Reglas:
    """Reglas cargadas y autenticadas; de solo lectura desde fuera."""

    reglas_version: str
    hash_contenido: str
    aplicado_a: tuple[str, ...]
    generales: Mapping[str, Mapping[str, list[str]]]
    locales: Mapping[str, Mapping[str, Mapping[str, list[str]]]]
    ruta: Path
    claves_lista_negra: tuple[str, ...] = ()
    revision_nativa: Mapping[str, bool] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.revision_nativa is None:
            object.__setattr__(self, "revision_nativa", {})


def _validar_patrones(patrones: object, contexto: str) -> list[str]:
    if not isinstance(patrones, list) or not all(isinstance(p, str) for p in patrones):
        raise ErrorValidacion(f"reglas_sensibles.yaml: {contexto} debe ser una lista de patrones (cadenas)")
    for patron in patrones:
        try:
            re.compile(patron)
        except re.error as exc:
            raise ErrorValidacion(f"reglas_sensibles.yaml: patrón inválido en {contexto}: {patron!r} ({exc})") from exc
    return patrones


def _validar_categoria(cuerpo: object, contexto: str) -> None:
    if not isinstance(cuerpo, Mapping):
        raise ErrorValidacion(f"reglas_sensibles.yaml: {contexto} debe ser un mapa nivel -> patrones")
    for nivel, patrones in cuerpo.items():
        if nivel not in NIVELES_VALIDOS:
            raise ErrorValidacion(f"reglas_sensibles.yaml: nivel desconocido {nivel!r} en {contexto}")
        _validar_patrones(patrones, f"{contexto}.{nivel}")


def cargar_reglas(ruta: Path | str | None = None) -> Reglas:
    """Carga, autentica y valida ``reglas_sensibles.yaml``.

    Errores: ``ErrorValidacion`` (3) si el archivo falta, es ilegible, el ``hash_contenido`` no
    coincide con el contenido (reglas alteradas: el lint no corre) o la forma no es la esperada.
    """
    destino = Path(ruta) if ruta is not None else RUTA_POR_DEFECTO
    try:
        datos = comun.cargar_yaml(destino)
    except FileNotFoundError as exc:
        raise ErrorValidacion(f"faltan las reglas de cumplimiento: {destino}") from exc
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ErrorValidacion(f"{destino.name} ilegible: {exc}") from exc
    if not isinstance(datos, dict):
        raise ErrorValidacion(f"{destino.name}: se esperaba un mapa")
    hash_declarado = datos.get(CAMPO_HASH)
    if not isinstance(hash_declarado, str) or not hash_declarado:
        raise ErrorValidacion(f"{destino.name}: falta {CAMPO_HASH} (reglas sin autosellar no corren)")
    hash_real = comun.hash_objeto(datos, excluir=(CAMPO_HASH,))
    if not comun.comparar_hash(hash_declarado, hash_real):
        raise ErrorValidacion(f"{destino.name}: {CAMPO_HASH} no coincide con el contenido (reglas alteradas): el lint NO corre")
    version = datos.get("reglas_version")
    if not isinstance(version, str) or not _RX_SEMVER.fullmatch(version):
        raise ErrorValidacion(f"{destino.name}: reglas_version inválida (se espera SemVer)")
    aplicado_a_raw = datos.get("aplicado_a") or []
    if not isinstance(aplicado_a_raw, list) or not all(isinstance(x, str) for x in aplicado_a_raw):
        raise ErrorValidacion(f"{destino.name}: aplicado_a debe ser una lista de cadenas")
    generales = datos.get("generales") or {}
    if not isinstance(generales, Mapping):
        raise ErrorValidacion(f"{destino.name}: generales debe ser un mapa")
    for categoria, cuerpo in generales.items():
        _validar_categoria(cuerpo, f"generales.{categoria}")
    locales = datos.get("locales") or {}
    if not isinstance(locales, Mapping):
        raise ErrorValidacion(f"{destino.name}: locales debe ser un mapa")
    for locale, macro in locales.items():
        if not isinstance(macro, Mapping):
            raise ErrorValidacion(f"{destino.name}: locales.{locale} debe ser un mapa")
        for categoria, cuerpo in macro.items():
            _validar_categoria(cuerpo, f"locales.{locale}.{categoria}")
    claves_lista_negra_raw = datos.get("claves_lista_negra") or []
    if not isinstance(claves_lista_negra_raw, list) or not all(isinstance(c, str) for c in claves_lista_negra_raw):
        raise ErrorValidacion(f"{destino.name}: claves_lista_negra debe ser una lista de cadenas")
    revision_nativa_raw = datos.get("revision_nativa") or {}
    if not isinstance(revision_nativa_raw, Mapping) or not all(isinstance(v, bool) for v in revision_nativa_raw.values()):
        raise ErrorValidacion(f"{destino.name}: revision_nativa debe ser un mapa locale -> booleano")
    return Reglas(reglas_version=version, hash_contenido=hash_declarado, aplicado_a=tuple(aplicado_a_raw),
                  generales=generales, locales=locales, ruta=destino,
                  claves_lista_negra=tuple(claves_lista_negra_raw), revision_nativa=dict(revision_nativa_raw))


def categorias_de_locale(reglas: Reglas, locale: str, macro_nicho: str | None, *,
                         incluir_adicionales: bool = False, raiz: Path | None = None) -> dict[str, Mapping[str, list[str]]]:
    """Categorías de ``reglas.locales[locale]`` a mirar: solo la de ``macro_nicho`` si se conoce, todas si no.

    Con ``incluir_adicionales=True`` (D-02b), suma —sin poder debilitar— el léxico que el Maker de
    X1 proponga en ``empresa/compliance/terminos_sensibles/<locale>.yaml`` (:func:`cargar_terminos_adicionales`,
    :func:`combinar_categorias`). Por defecto ``False``: esta función sigue siendo pura para quien
    solo quiere inspeccionar las reglas base (p. ej. las pruebas de este módulo).

    Errores: ``ErrorValidacion`` si el ``locale`` no tiene reglas (fail-closed: no se asume un
    locale por defecto, convenciones §4 y backbone «ningún mercado es prior»).
    """
    mapa = reglas.locales.get(locale)
    if mapa is None:
        raise ErrorValidacion(f"locale sin reglas de cumplimiento: {locale!r}; agrégalo a compliance/reglas_sensibles.yaml")
    categoria = MACRO_A_CATEGORIA.get(macro_nicho) if macro_nicho else None
    if categoria is not None:
        base = {categoria: mapa[categoria]} if categoria in mapa else {}
    else:
        base = dict(mapa)
    if not incluir_adicionales:
        return base
    extra, _avisos = cargar_terminos_adicionales(locale, raiz=raiz)
    if categoria is not None:
        extra = {categoria: extra[categoria]} if categoria in extra else {}
    combinado, _avisos_combinar = combinar_categorias(base, extra)
    return combinado


def cargar_terminos_adicionales(locale: str, *, raiz: Path | None = None) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
    """Léxico opcional del Maker de X1 en ``empresa/compliance/terminos_sensibles/<locale>.yaml`` (D-02b).

    Nunca falla: el archivo es opcional (quien lo escribe no puede editar ``compliance/`` ni
    resellar). Ausente, ilegible o con forma inválida se ignora por completo (lista vacía) y se
    informa en el segundo elemento de la tupla; nunca bloquea el lint (no es la fuente de verdad,
    solo un aporte aditivo).
    """
    destino = (raiz or comun.raiz()) / RUTA_TERMINOS_ADICIONALES / f"{locale}.yaml"
    if not destino.is_file():
        return {}, []
    try:
        datos = comun.cargar_yaml(destino)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return {}, [f"{destino}: ilegible, se ignora ({exc})"]
    if not isinstance(datos, Mapping):
        return {}, [f"{destino}: se esperaba un mapa categoria -> nivel -> patrones, se ignora"]
    extra: dict[str, dict[str, list[str]]] = {}
    avisos: list[str] = []
    for categoria, cuerpo in datos.items():
        if not isinstance(cuerpo, Mapping):
            avisos.append(f"{destino}: {categoria!r} no es un mapa nivel -> patrones, se ignora")
            continue
        for nivel, patrones in cuerpo.items():
            if nivel not in NIVELES_VALIDOS:
                avisos.append(f"{destino}: nivel desconocido {nivel!r} en {categoria!r}, se ignora")
                continue
            if not isinstance(patrones, list) or not all(isinstance(p, str) for p in patrones):
                avisos.append(f"{destino}: {categoria}.{nivel} debe ser una lista de patrones (cadenas), se ignora")
                continue
            validos: list[str] = []
            for patron in patrones:
                try:
                    re.compile(patron)
                except re.error as exc:
                    avisos.append(f"{destino}: patrón inválido en {categoria}.{nivel}: {patron!r} ({exc}), se ignora")
                    continue
                validos.append(patron)
            if validos:
                extra.setdefault(categoria, {}).setdefault(nivel, []).extend(validos)
    return extra, avisos


def combinar_categorias(base: Mapping[str, Mapping[str, list[str]]],
                        extra: Mapping[str, Mapping[str, list[str]]]) -> tuple[dict[str, dict[str, list[str]]], list[str]]:
    """Suma ``extra`` sobre ``base`` sin poder debilitarla (D-02b): solo añade patrones nuevos.

    Un patrón de ``extra`` que ya existe en ``base`` bajo OTRO nivel se ignora e informa (no se
    puede mover una regla base a un nivel más débil); un patrón que ya existe en el MISMO nivel es
    un duplicado silencioso (no aporta nada, no es una contradicción). Nunca se elimina ni se
    reemplaza un patrón de ``base``.
    """
    combinado: dict[str, dict[str, list[str]]] = {
        categoria: {nivel: list(patrones) for nivel, patrones in cuerpo.items()} for categoria, cuerpo in base.items()
    }
    avisos: list[str] = []
    for categoria, cuerpo in extra.items():
        for nivel, patrones in cuerpo.items():
            for patron in patrones:
                otro_nivel = next(
                    (n for n, ps in combinado.get(categoria, {}).items() if n != nivel and patron in ps), None,
                )
                if otro_nivel is not None:
                    avisos.append(
                        f"término adicional {patron!r} ya existe en {categoria}.{otro_nivel} de la base: "
                        f"se ignora el nivel {nivel!r} propuesto (no se puede debilitar una regla base)"
                    )
                    continue
                destino_lista = combinado.setdefault(categoria, {}).setdefault(nivel, [])
                if patron not in destino_lista:
                    destino_lista.append(patron)
    return combinado, avisos


def resellar(ruta: Path | str | None = None) -> str:
    """Herramienta de mantenimiento (no una CLI pública): recalcula ``hash_contenido`` y reescribe el
    archivo. Solo la usa el dueño/X1 a mano tras editar una regla; ningún agente la invoca (no está
    en ``herramientas.yaml`` de B9). Devuelve el hash nuevo.
    """
    destino = Path(ruta) if ruta is not None else RUTA_POR_DEFECTO
    datos = comun.cargar_yaml(destino)
    if not isinstance(datos, dict):
        raise ErrorValidacion(f"{destino.name}: se esperaba un mapa")
    datos[CAMPO_HASH] = comun.hash_objeto(datos, excluir=(CAMPO_HASH,))
    import yaml  # import local: solo esta herramienta de mantenimiento escribe YAML

    destino.write_text(yaml.safe_dump(datos, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return datos[CAMPO_HASH]


if __name__ == "__main__":  # pragma: no cover - herramienta manual, no forma parte de la CLI pública
    import sys

    print(resellar(sys.argv[1] if len(sys.argv) > 1 else None))
