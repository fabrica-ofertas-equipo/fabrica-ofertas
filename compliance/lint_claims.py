"""Lint determinista de claims (X1, docs/06 N09 y §4.5; G-13 P01/P07/P08).

Busca, en un texto o en cualquier artefacto JSON/YAML, léxico de cura y plazo (salud), verbos de
cambio sobre el cuerpo o el dinero (finanzas), garantías absolutas, urgencia falsa y prueba social
fabricada, usando ``compliance/reglas_sensibles.yaml`` (:mod:`compliance.reglas`). El resultado es
un semáforo (verde/amarillo/rojo, el peor hallazgo manda) y la lista de hallazgos con evidencia
citada. La CLI sale con **3** (validación) si el semáforo es ``rojo`` — "precio (3 si hay ROJO)"
de docs/06 §4.5 — y nunca inventa un locale por defecto (fail-closed).

No decide nada por sí solo: ``compliance.sellar`` exige que este lint no haya dado ``rojo`` antes
de sellar una etapa (docs/06 N09).
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion

from compliance.hallazgos import Hallazgo, peor_nivel
from compliance.reglas import Reglas, cargar_reglas, categorias_de_locale

__all__ = ["ResultadoLint", "extraer_textos", "lint_artefacto", "lint_claims", "lint_texto", "main"]

_SUFIJOS_ESTRUCTURADOS = (".json", ".yaml", ".yml")
_EVIDENCIA_CONTEXTO = 20  # caracteres de contexto alrededor de la coincidencia (cita corta, no el texto completo)


@dataclass(frozen=True)
class ResultadoLint:
    """Semáforo y hallazgos de una corrida de lint, con la versión de reglas usada (para el sello)."""

    reglas_version: str
    semaforo: str
    hallazgos: tuple[Hallazgo, ...]

    def asdict(self) -> dict[str, Any]:
        return {"reglas_version": self.reglas_version, "semaforo": self.semaforo, "hallazgos": [h.asdict() for h in self.hallazgos]}


def _normalizar(texto: str) -> str:
    return unicodedata.normalize("NFC", texto)


def _evidencia(texto: str, inicio: int, fin: int) -> str:
    desde = max(0, inicio - _EVIDENCIA_CONTEXTO)
    hasta = min(len(texto), fin + _EVIDENCIA_CONTEXTO)
    return texto[desde:hasta].strip()


def _buscar_categoria(texto: str, categoria: str, cuerpo: Mapping[str, Sequence[str]], locale: str | None,
                      origen: str) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for nivel, patrones in (cuerpo or {}).items():
        for patron in patrones:
            m = re.search(patron, texto, re.IGNORECASE)
            if m:
                hallazgos.append(Hallazgo(
                    patron_clave=f"{categoria}:{comun.hash_bytes(patron.encode('utf-8'))[7:19]}",
                    nivel=nivel,
                    categoria=categoria,
                    descripcion=f"{origen}: coincide con {categoria}/{nivel}",
                    evidencia=_evidencia(texto, m.start(), m.end()),
                    locale=locale,
                ))
    return hallazgos


def lint_texto(texto: str, reglas: Reglas, *, locale: str, macro_nicho: str | None = None, origen: str = "texto") -> list[Hallazgo]:
    """Hallazgos de UN texto frente a ``reglas`` (generales + salud/finanzas del ``locale``/``macro_nicho``).

    Errores: ``ErrorValidacion`` si ``texto`` no es una cadena o si ``locale`` no tiene reglas
    cargadas (fail-closed: ningún mercado es prior, no se asume un locale por defecto).
    """
    if not isinstance(texto, str):
        raise ErrorValidacion("lint_texto exige una cadena")
    if not texto.strip():
        return []
    t = _normalizar(texto)
    hallazgos: list[Hallazgo] = []
    for categoria, cuerpo in (reglas.generales or {}).items():
        hallazgos += _buscar_categoria(t, f"general-{categoria}", cuerpo, None, origen)
    # incluir_adicionales=True (D-02b): suma, sin poder debilitar, el léxico que el Maker de X1
    # proponga en empresa/compliance/terminos_sensibles/<locale>.yaml.
    for categoria, cuerpo in categorias_de_locale(reglas, locale, macro_nicho, incluir_adicionales=True).items():
        hallazgos += _buscar_categoria(t, categoria, cuerpo, locale, origen)
    return hallazgos


def extraer_textos(datos: Any, prefijo: str = "$", *, excluir_claves: frozenset[str] = frozenset()) -> list[tuple[str, str]]:
    """Recorre cualquier estructura JSON/YAML y devuelve ``[(ruta, texto)]`` de cada cadena no vacía.

    No conoce el esquema de ningún artefacto en particular (oferta, creativos...): es deliberadamente
    genérico para no duplicar la forma de cada contrato (los dueños de esos esquemas son otros
    componentes). Ver «Decisiones» en ``compliance/README.md``.

    ``excluir_claves``: nombres de clave (coincidencia EXACTA, cualquier profundidad) cuyo subárbol
    no se incluye (docs/06 N09 + Decisión 1b: ``claims_prohibidos``/``claims_a_evitar`` de un
    ``oferta.json`` describen a propósito las frases prohibidas; no son una afirmación propia).
    """
    salida: list[tuple[str, str]] = []
    if isinstance(datos, str):
        if datos.strip():
            salida.append((prefijo, datos))
    elif isinstance(datos, Mapping):
        for clave, valor in datos.items():
            if clave in excluir_claves:
                continue
            salida += extraer_textos(valor, f"{prefijo}.{clave}", excluir_claves=excluir_claves)
    elif isinstance(datos, (list, tuple)):
        for indice, valor in enumerate(datos):
            salida += extraer_textos(valor, f"{prefijo}[{indice}]", excluir_claves=excluir_claves)
    return salida


def _textos_bajo_claves(datos: Any, claves: frozenset[str]) -> list[tuple[str, str]]:
    """Todas las cadenas que SÍ viven bajo alguna de ``claves`` (cualquier profundidad).

    Lo inverso de ``excluir_claves`` en :func:`extraer_textos`: sirve para comprobar que esas
    frases (justamente las prohibidas) no se filtran a ningún OTRO campo del mismo artefacto.
    """
    encontrados: list[tuple[str, str]] = []
    if isinstance(datos, Mapping):
        for clave, valor in datos.items():
            if clave in claves:
                encontrados += extraer_textos(valor, f"$.{clave}")
            else:
                encontrados += _textos_bajo_claves(valor, claves)
    elif isinstance(datos, (list, tuple)):
        for valor in datos:
            encontrados += _textos_bajo_claves(valor, claves)
    return encontrados


def lint_artefacto(datos: Any, reglas: Reglas, *, locale: str, macro_nicho: str | None = None) -> list[Hallazgo]:
    """Hallazgos de TODAS las cadenas de ``datos`` (un artefacto JSON/YAML ya cargado).

    Decisión 1b (``compliance/README.md``): las cadenas que viven exactamente bajo
    ``reglas.claves_lista_negra`` (p. ej. ``claims_prohibidos``/``claims_a_evitar`` de
    ``oferta.json``) no se lintean como afirmación propia. Pero si alguna de esas frases EXACTAS
    aparece en cualquier OTRO campo del mismo artefacto, sigue siendo ROJO (no es una exclusión que
    se pueda usar para blanquear un claim real escribiéndolo en una clave con nombre parecido).
    """
    excluidas = frozenset(reglas.claves_lista_negra)
    hallazgos: list[Hallazgo] = []
    for ruta, texto in extraer_textos(datos, excluir_claves=excluidas):
        hallazgos += lint_texto(texto, reglas, locale=locale, macro_nicho=macro_nicho, origen=ruta)
    if excluidas:
        frases_prohibidas = sorted({t.strip().lower() for _, t in _textos_bajo_claves(datos, excluidas) if t.strip()})
        if frases_prohibidas:
            for ruta, texto in extraer_textos(datos, excluir_claves=excluidas):
                t = texto.lower()
                for frase in frases_prohibidas:
                    indice = t.find(frase)
                    if indice == -1:
                        continue
                    hallazgos.append(Hallazgo(
                        patron_clave="lista_negra:fuga",
                        nivel="rojo",
                        categoria="lista_negra",
                        descripcion=f"{ruta}: contiene una frase de {sorted(excluidas)} fuera de esa clave",
                        evidencia=_evidencia(texto, indice, indice + len(frase)),
                    ))
    return hallazgos


def lint_claims(ruta: Path | str, *, locale: str, macro_nicho: str | None = None, reglas: Reglas | None = None) -> ResultadoLint:
    """Lintea un archivo (JSON/YAML: todas sus cadenas; texto/HTML plano: el contenido completo).

    Errores: ``ErrorUso`` si el archivo no existe; ``ErrorValidacion`` si no se puede leer o
    parsear, o si ``locale`` no tiene reglas.
    """
    ruta = Path(ruta)
    if not ruta.is_file():
        raise ErrorUso(f"no existe el archivo a lintear: {ruta}")
    reglas = reglas or cargar_reglas()
    if ruta.suffix.lower() in _SUFIJOS_ESTRUCTURADOS:
        try:
            datos = comun.cargar_yaml(ruta) if ruta.suffix.lower() != ".json" else comun.cargar_json(ruta)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            raise ErrorValidacion(f"{ruta.name}: ilegible ({exc})") from exc
        hallazgos = lint_artefacto(datos, reglas, locale=locale, macro_nicho=macro_nicho)
    else:
        try:
            texto = ruta.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise ErrorValidacion(f"{ruta.name}: ilegible ({exc})") from exc
        hallazgos = lint_texto(texto, reglas, locale=locale, macro_nicho=macro_nicho, origen=ruta.name)
    return ResultadoLint(reglas_version=reglas.reglas_version, semaforo=peor_nivel(hallazgos), hallazgos=tuple(hallazgos))


def _ruta_oferta_etapa(oferta_id: str, etapa: str, *, raiz: Path) -> list[Path]:
    """Archivo(s) sellados de ``etapa`` para ``oferta_id`` (reutiliza el mapa de CT, no lo redefine).

    D-02c: para ``D5`` suma también el HTML servido bajo ``DIRECTORIOS_SELLADOS`` (``05-landing/sitio``):
    el copy real de la landing vive ahí, no solo en los JSON de assets/checkout/tracking/rutas.
    """
    from scripts.validar_esquemas import ARCHIVOS_SELLADOS, DIRECTORIOS_SELLADOS  # import local: evita un ciclo

    rutas = list(ARCHIVOS_SELLADOS.get(etapa) or [])
    for carpeta in DIRECTORIOS_SELLADOS.get(etapa, []):
        base = raiz / "ofertas" / oferta_id / carpeta
        if base.is_dir():
            rutas += [p.relative_to(raiz / "ofertas" / oferta_id).as_posix() for p in sorted(base.rglob("*.html"))]
    if not rutas:
        raise ErrorUso(f"etapa sin archivos sellados conocidos para lintear: {etapa!r}")
    return [raiz / "ofertas" / oferta_id / rel for rel in rutas]


def _construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m compliance.lint_claims", description=__doc__.splitlines()[0])
    origen = p.add_mutually_exclusive_group(required=True)
    origen.add_argument("--archivo", type=Path, help="archivo a lintear (JSON/YAML: todas sus cadenas; texto/HTML: completo)")
    origen.add_argument("--oferta", help="OF-AAAAMM-NN; requiere --etapa")
    p.add_argument("--etapa", help="Dn de la oferta (junto con --oferta)")
    p.add_argument("--locale", required=True, help="BCP-47 con región (es-ES, en-US...); sin default: fail-closed")
    p.add_argument("--macro-nicho", choices=("salud", "relaciones", "dinero"), default=None)
    p.add_argument("--reglas", type=Path, default=None, help="ruta alternativa de reglas_sensibles.yaml (pruebas)")
    p.add_argument("--raiz", type=Path, default=None)
    p.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    """``python -m compliance.lint_claims (--archivo F | --oferta OF --etapa E) --locale L [--macro-nicho]``.

    Sale 0 (verde/amarillo) o 3 (rojo: "precio (3 si hay ROJO)", docs/06 §4.5); 2 de uso; 3 también
    si las reglas están alteradas o el archivo es ilegible (:mod:`compliance.reglas`).
    """
    try:
        args = _construir_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if args.oferta and not args.etapa:
        raise ErrorUso("--oferta exige --etapa")

    def cuerpo() -> int:
        raiz = args.raiz or comun.raiz()
        reglas = cargar_reglas(args.reglas)
        if args.archivo:
            resultado = lint_claims(args.archivo, locale=args.locale, macro_nicho=args.macro_nicho, reglas=reglas)
        else:
            hallazgos: list[Hallazgo] = []
            for ruta in _ruta_oferta_etapa(args.oferta, args.etapa, raiz=raiz):
                hallazgos += lint_claims(ruta, locale=args.locale, macro_nicho=args.macro_nicho, reglas=reglas).hallazgos
            resultado = ResultadoLint(reglas_version=reglas.reglas_version, semaforo=peor_nivel(hallazgos), hallazgos=tuple(hallazgos))
        codigo = 3 if resultado.semaforo == "rojo" else 0
        avisos: list[str] = []
        if reglas.revision_nativa.get(args.locale) is False:
            avisos.append(f"reglas de {args.locale} SIN revisión nativa (HIPÓTESIS): confirmar con hablante nativo antes de bloquear sin revisión humana")
        salida = {"ok": codigo == 0, "modo": "dry_run", "codigo": codigo, "datos": resultado.asdict(), "avisos": avisos}
        if args.json:
            print(comun.json_canonico(salida).decode("utf-8"))
        else:
            print(f"semáforo={resultado.semaforo} reglas_version={resultado.reglas_version} hallazgos={len(resultado.hallazgos)}")
            for h in resultado.hallazgos:
                print(f"  [{h.nivel}] {h.patron_clave}: {h.descripcion} — «{h.evidencia}»")
        return codigo

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    import sys

    sys.exit(main())
