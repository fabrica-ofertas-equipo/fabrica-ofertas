"""Clasificador de macro-nicho por deseo central (árbol Q0-Q6, `docs/_investigacion/25-...` §1.2).

Clasifica la ``prueba_una_frase`` del PRODUCTO PROPIO (nunca el tema del barrido ni
``modelado.macro_etiqueta``) en salud / relaciones / dinero / fuera de marco. Es código determinista,
sin red, sin LLM: usa listas de palabras clave por idioma para reconocer la métrica de éxito que el
cliente reconocería (nota 25 §1.1). Es una heurística [HIPÓTESIS], no un modelo de lenguaje; su
calibración es la suite de retención de ``tests/fixtures/descubrimiento/macro_retencion.yaml``.

Árbol (nota 25 §1.2):
    Q0 ¿hay una frase "de [A] a [B]"?            no -> `sin_prueba_frase` (rechazo MU/EU, no de macro)
    Q1-Q3 ¿B es un eje de salud / relaciones / dinero?  -> banderas {S, R, D}
    Q4 ¿alguna bandera?                           no -> `fuera_de_macro_nicho` (motivo `ninguna_bandera`)
    Q5 ¿exactamente una?                          sí -> esa es el primario
    Q6 si hay más de una: la cita E3 desambigua; sin cita que resuelva, el primario es la bandera
       con el nivel de riesgo más estricto (salud > relaciones > dinero, orden fijo documentado).

Regla transversal (interfaces §3.8.1 regla 2): toda clasificación con al menos una bandera exige una
señal E3 del locale destino (``senal_id_e3``); sin ella el par queda `incompleta`, nunca se inventa.
Nunca se infiere el macro del tema (decisión 13): esta función solo mira la frase del producto propio.

Uso::

    python -m scripts.descubrimiento.macro clasificar --frase "de improvisar la cena a comer sano" \\
        --senal-id-e3 abc123abc123 [--cita "ahora como más sano"] [--json]
    python -m scripts.descubrimiento.macro verificar tests/fixtures/descubrimiento/macro_retencion.yaml

Códigos de salida (convenciones §8): 0 ok · 2 uso · 3 validación o discrepancias de la suite.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Mapping

from engine.comun import ejecutar_cli
from engine.errores import ErrorUso, ErrorValidacion

VERSION_ARBOL = "nota25-1.2-v1"

MACROS: tuple[str, ...] = ("salud", "relaciones", "dinero")
BANDERAS: tuple[str, ...] = ("S", "R", "D")
_BANDERA_A_MACRO: dict[str, str] = {"S": "salud", "R": "relaciones", "D": "dinero"}
MOTIVOS_FUERA: tuple[str, ...] = ("ninguna_bandera", "deseo_del_comprador_es_profesional", "hobby", "estetica")
# Orden fijo para Q6 cuando la cita no desambigua (el más estricto manda; documentado, no es el único
# criterio válido, pero es determinista): salud > relaciones > dinero.
_PRIORIDAD_BANDERA: tuple[str, ...] = ("S", "R", "D")

ESTADOS: tuple[str, ...] = ("clasificado", "incompleta", "fuera_de_macro_nicho", "sin_prueba_frase")

# ---------------------------------------------------------------------------
# Patrones "de [A] a [B]" por idioma (es/it comparten "de"/"da"; en "from...to"; pl "od...do").
# ---------------------------------------------------------------------------
_PATRONES_DE_A_B: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bde\s+(?P<a>.+?)\s+a\s+(?P<b>.+)$"),
    re.compile(r"\bfrom\s+(?P<a>.+?)\s+to\s+(?P<b>.+)$"),
    re.compile(r"\bda\s+(?P<a>.+?)\s+a\s+(?P<b>.+)$"),
    re.compile(r"\bod\s+(?P<a>.+?)\s+do\s+(?P<b>.+)$"),
)


def _normalizar(texto: str) -> str:
    """Minúsculas, sin tildes/diacríticos, espacios colapsados (para comparar con listas ASCII)."""
    sin_acentos = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(sin_acentos.casefold().split())


def _contiene_alguna(texto_normalizado: str, palabras: tuple[str, ...]) -> str | None:
    for p in palabras:
        if re.search(rf"\b{re.escape(p)}\w*", texto_normalizado):
            return p
    return None


# Cada entrada es un prefijo de palabra (coincide con sufijos: "ahorr" -> "ahorro", "ahorrar"...).
_HOBBY = (
    "crochet", "tejer", "tejido", "patron", "costura", "bricolaje", "manualidad", "pintura", "dibujo",
    "ceramica", "macrame", "hobby", "diy", "knitting", "sewing", "craft", "pattern", "drawing",
    "painting", "uncinetto", "maglia", "cucito", "disegno", "pittura", "szydelko", "szycie", "rysunek",
    "malowanie", "scrapbook", "origami",
)
_ESTETICA = (
    "maquillaje", "peinado", "moda", "decoracion", "belleza", "manicura", "makeup", "hairstyle",
    "fashion", "decor", "beauty", "manicure", "trucco", "acconciatura", "bellezza", "makijaz",
    "fryzura", "uroda", "decorazione",
)
_PROFESIONAL = (
    "para psicologos", "para psicologas", "para terapeutas", "para docentes", "para profesores",
    "para enfermeras", "para abogados", "para contadores", "kit profesional para", "fichas para",
    "for psychologists", "for therapists", "for teachers", "for lawyers", "for nurses", "for coaches",
    "per psicologi", "per terapisti", "per insegnanti", "dla psychologow", "dla terapeutow",
    "dla nauczycieli",
)

_SALUD = (
    "dolor", "dormir", "sueno", "ansied", "estres", "energia", "peso", "ejercici", "salud", "calma",
    "animo", "descans", "movilidad", "respir", "relaj", "pain", "sleep", "anxi", "stress",
    "energy", "weight", "health", "calm", "mood", "rest", "breath", "relax", "exercis",
    "sonn", "ansi", "salut", "umor", "ripos", "bol", "bezsenn", "lek", "stres", "waga",
    "zdrowi", "spokoj", "nastroj", "odpoczyn", "oddych",
)
_RELACIONES = (
    "pareja", "hijo", "hija", "familia", "comunicac", "relacion", "vinculo", "amistad", "matrimoni",
    "conflicto", "convivencia", "partner", "child", "family", "communicat", "relationship", "bond",
    "friendship", "marriage", "conflict", "figlio", "figlia", "famiglia", "comunicazion", "relazion",
    "legame", "amicizia", "conflitto", "dziecko", "rodzin", "komunikacj", "relacj",
    "wiez", "przyjazn", "malzenstw", "konflikt",
)
_DINERO = (
    "ahorr", "gast", "deuda", "ingreso", "precio", "empleo", "trabaj", "impuesto", "dinero", "cobr",
    "pag", "presupuesto", "factura", "coste", "sav", "spend", "debt", "incom", "price", "job",
    "employ", "tax", "money", "charg", "budget", "invoic", "risparmi", "debit",
    "reddit", "prezz", "lavor", "tass", "sold", "bilanci", "fattur", "oszcz",
    "wydat", "dlug", "dochod", "cena", "prac", "podatek", "pieniadz", "zaplac", "budzet", "faktur",
)


def extraer_b(frase: str) -> tuple[str, str] | None:
    """``(a, b)`` de la primera frase "de [A] a [B]" hallada (cualquiera de los 4 idiomas), o ``None`` (Q0 falla)."""
    normal = _normalizar(frase)
    for patron in _PATRONES_DE_A_B:
        m = patron.search(normal)
        if m:
            return m.group("a").strip(), m.group("b").strip()
    return None


def _flags(texto_normalizado: str) -> dict[str, bool]:
    return {
        "S": _contiene_alguna(texto_normalizado, _SALUD) is not None,
        "R": _contiene_alguna(texto_normalizado, _RELACIONES) is not None,
        "D": _contiene_alguna(texto_normalizado, _DINERO) is not None,
    }


def banderas_de_frase(frase: str) -> dict[str, bool]:
    """``{S, R, D}`` evaluadas sobre B (o sobre toda la frase si Q0 no pudo aislar B)."""
    partes = extraer_b(frase)
    texto = _normalizar(partes[1]) if partes else _normalizar(frase)
    return _flags(texto)


def clasificar(prueba_una_frase: Any, *, senal_id_e3: str | None, cita_e3: str | None = None) -> dict[str, Any]:
    """Clasifica una ``prueba_una_frase`` del producto propio; nunca infiere el macro del tema.

    Devuelve ``{estado, macro_nicho, macro_secundario, banderas, motivo_macro, senal_id_e3, version_arbol}``.
    ``estado``:
      * ``sin_prueba_frase`` -- Q0 falla (no hay "de [A] a [B]"); no es un rechazo de macro (es MU/EU).
      * ``fuera_de_macro_nicho`` -- Q4 falla (ninguna bandera) o A/B cae en hobby/estética/comprador
        profesional (detectado antes de Q1-Q3, nunca se redime cambiando el gancho del anuncio).
      * ``incompleta`` -- hay al menos una bandera pero falta ``senal_id_e3`` (interfaces §3.8.1 regla 2).
      * ``clasificado`` -- ``macro_nicho`` (primario) y, si corresponde, ``macro_secundario`` fijados.

    Errores: ``ErrorValidacion`` si ``prueba_una_frase`` no es texto no vacío.
    """
    if not isinstance(prueba_una_frase, str) or not prueba_una_frase.strip():
        raise ErrorValidacion("prueba_una_frase: texto no vacío requerido")
    normal_completa = _normalizar(prueba_una_frase)
    base: dict[str, Any] = {
        "banderas": {"S": False, "R": False, "D": False}, "macro_nicho": None, "macro_secundario": None,
        "motivo_macro": None, "senal_id_e3": senal_id_e3, "version_arbol": VERSION_ARBOL,
    }

    partes = extraer_b(prueba_una_frase)
    if partes is None:
        return {**base, "estado": "sin_prueba_frase"}
    a, b = partes

    if _contiene_alguna(normal_completa, _PROFESIONAL) is not None:
        return {**base, "estado": "fuera_de_macro_nicho", "motivo_macro": "deseo_del_comprador_es_profesional"}
    if _contiene_alguna(_normalizar(a), _HOBBY) is not None or _contiene_alguna(_normalizar(b), _HOBBY) is not None:
        return {**base, "estado": "fuera_de_macro_nicho", "motivo_macro": "hobby"}
    if _contiene_alguna(_normalizar(a), _ESTETICA) is not None or _contiene_alguna(_normalizar(b), _ESTETICA) is not None:
        return {**base, "estado": "fuera_de_macro_nicho", "motivo_macro": "estetica"}

    banderas = _flags(_normalizar(b))
    base["banderas"] = banderas
    activas = [f for f in BANDERAS if banderas[f]]
    if not activas:
        return {**base, "estado": "fuera_de_macro_nicho", "motivo_macro": "ninguna_bandera"}
    if senal_id_e3 is None or not str(senal_id_e3).strip():
        return {**base, "estado": "incompleta"}

    if len(activas) == 1:
        primario, secundario = activas[0], None
    else:
        resuelto = None
        if cita_e3:
            flags_cita = _flags(_normalizar(cita_e3))
            coincide = [f for f in activas if flags_cita[f]]
            if len(coincide) == 1:
                resuelto = coincide[0]
        if resuelto is None:
            resuelto = next(f for f in _PRIORIDAD_BANDERA if f in activas)
        primario = resuelto
        resto = [f for f in activas if f != primario]
        secundario = resto[0] if resto else None

    return {
        **base, "estado": "clasificado",
        "macro_nicho": _BANDERA_A_MACRO[primario],
        "macro_secundario": _BANDERA_A_MACRO[secundario] if secundario else None,
    }


# ---------------------------------------------------------------------------
# Suite de retención (tests/fixtures/descubrimiento/macro_retencion.yaml)
# ---------------------------------------------------------------------------
def _cargar_yaml(ruta: Path) -> Any:
    import yaml

    try:
        return yaml.safe_load(ruta.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ErrorUso(f"no se pudo leer la suite {ruta}: {exc.strerror}") from exc


def verificar_retencion(ruta: Path) -> dict[str, Any]:
    """Corre toda la suite de retención y devuelve conteos + discrepancias.

    Cada caso trae ``macro_nicho_esperado`` en ``{salud, relaciones, dinero, fuera_de_macro_nicho,
    sin_prueba_frase}`` y, si es ``fuera_de_macro_nicho``, opcionalmente ``motivo_macro_esperado``.

    Invariantes exigidos (scope D1c): **0 falsos verdes** (un caso negativo -- ``fuera_de_macro_nicho``
    o ``sin_prueba_frase`` -- nunca sale ``clasificado`` dentro de un macro) y **tasa de falsos rojos
    <= 5 %** sobre los casos positivos (un caso que debería caer en un macro y la heurística rechaza
    como ``fuera_de_macro_nicho``, ``incompleta`` o ``sin_prueba_frase``).
    """
    datos = _cargar_yaml(ruta)
    if not isinstance(datos, Mapping) or not isinstance(datos.get("casos"), list):
        raise ErrorValidacion("la suite no tiene la forma {casos: [...]}")
    falsos_verdes: list[str] = []
    falsos_rojos: list[str] = []
    otras_discrepancias: list[str] = []
    total_positivos = 0
    for caso in datos["casos"]:
        esperado = caso["macro_nicho_esperado"]
        r = clasificar(caso["prueba_una_frase"], senal_id_e3=caso.get("senal_id_e3", "abc123abc123"),
                       cita_e3=caso.get("cita_e3"))
        if esperado in MACROS:
            total_positivos += 1
            if r["estado"] == "clasificado" and r["macro_nicho"] == esperado:
                continue
            if r["estado"] == "clasificado":
                falsos_rojos.append(f"{caso['id']}: primario {r['macro_nicho']} != esperado {esperado}")
            else:
                falsos_rojos.append(f"{caso['id']}: esperado {esperado}, obtenido estado={r['estado']}")
        else:  # negativo: fuera_de_macro_nicho o sin_prueba_frase
            if r["estado"] == "clasificado":
                falsos_verdes.append(f"{caso['id']}: esperado {esperado}, clasificado como {r['macro_nicho']}")
            elif r["estado"] != esperado:
                otras_discrepancias.append(f"{caso['id']}: estado {r['estado']} != esperado {esperado}")
            elif esperado == "fuera_de_macro_nicho" and caso.get("motivo_macro_esperado") not in (None, r.get("motivo_macro")):
                otras_discrepancias.append(
                    f"{caso['id']}: motivo_macro {r.get('motivo_macro')} != esperado {caso['motivo_macro_esperado']}")
    tasa_falsos_rojos = (len(falsos_rojos) / total_positivos) if total_positivos else 0.0
    return {
        "total_casos": len(datos["casos"]), "total_positivos": total_positivos,
        "falsos_verdes": falsos_verdes, "falsos_rojos": falsos_rojos,
        "otras_discrepancias": otras_discrepancias, "tasa_falsos_rojos": tasa_falsos_rojos,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.descubrimiento.macro",
                                description="Clasificador de macro-nicho por deseo central (Q0-Q6)")
    sub = p.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("clasificar")
    pc.add_argument("--frase", required=True)
    pc.add_argument("--senal-id-e3")
    pc.add_argument("--cita")
    pc.add_argument("--json", action="store_true")
    pv = sub.add_parser("verificar")
    pv.add_argument("ruta", type=Path)
    pv.add_argument("--json", action="store_true")
    return p


def _principal(argv: list[str] | None) -> int:
    try:
        a = _parser().parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None):
            return 0
        raise ErrorUso("argumentos inválidos (ver --help)") from None
    if a.cmd == "clasificar":
        r = clasificar(a.frase, senal_id_e3=a.senal_id_e3, cita_e3=a.cita)
        print(json.dumps(r, ensure_ascii=False, sort_keys=True) if a.json
              else f"estado={r['estado']} macro_nicho={r['macro_nicho']} secundario={r['macro_secundario']} motivo={r['motivo_macro']}")
        return 0
    resultado = verificar_retencion(a.ruta)
    problemas = resultado["falsos_verdes"] + resultado["otras_discrepancias"]
    if a.json:
        print(json.dumps(resultado, ensure_ascii=False, sort_keys=True))
    else:
        print(f"casos={resultado['total_casos']} positivos={resultado['total_positivos']} "
              f"falsos_verdes={len(resultado['falsos_verdes'])} falsos_rojos={len(resultado['falsos_rojos'])} "
              f"tasa_falsos_rojos={resultado['tasa_falsos_rojos']:.3f}")
        for linea in problemas + resultado["falsos_rojos"]:
            print(f"  - {linea}")
    return 3 if (problemas or resultado["tasa_falsos_rojos"] > 0.05) else 0


def main(argv: list[str] | None = None) -> int:
    return ejecutar_cli(lambda: _principal(argv))


if __name__ == "__main__":
    raise SystemExit(main())
