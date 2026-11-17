"""Validador de `nichos.yaml` (interfaces d1-v2 §3.4, §8.2 n.2): árbol macro -> nicho -> microsegmento.

**No** escribe ni aprueba nada: solo valida la forma de un archivo ya existente (la semilla de
`docs/_historial/d1-v2-semillas/nichos.yaml`, 92 hojas, es una PROPUESTA pendiente de aprobación del
dueño; este módulo la trata como un fixture de prueba, nunca la copia a `empresa/descubrimiento/`).

Forma esperada (de la semilla real, más rica que el resumen de interfaces §3.4)::

    arbol:
      - macro_nicho: salud | relaciones | dinero
        nichos:
          - nicho_id: <kebab>
            microsegmentos:
              - id: <kebab>                 # único en TODO el árbol
                macro_secundario: <macro>|null   # nunca igual al macro_nicho de su rama
                tanda: <entero >= 1>
                estado: <texto>
                ...                         # prior_riesgo, dsp, idiomas, formatos... (no se valida su interior)
    semillas_fuera_de_marco:                # opcional; ninguna se siembra (decisión 13)
      - id: <kebab>
        motivo_macro: <texto>
        estado: registrada_no_sembrada

Uso::

    python -m scripts.descubrimiento.nichos validar RUTA.yaml [--macro-nichos-permitidos salud,relaciones,dinero] [--json]

Códigos de salida (convenciones §8): 0 sin errores · 2 uso · 3 validación (errores de forma).
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine import comun
from engine.comun import ejecutar_cli
from engine.errores import ErrorUso, ErrorValidacion

MACROS = ("salud", "relaciones", "dinero")
_RX_KEBAB = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def _es_kebab(valor: Any) -> bool:
    return isinstance(valor, str) and bool(_RX_KEBAB.fullmatch(valor))


def validar_nichos(doc: Any, *, macro_nichos_permitidos: Sequence[str] = MACROS) -> list[str]:
    """Lista de errores (vacía = válido). Nunca lanza por un dato de negocio, solo por forma del documento."""
    errores: list[str] = []
    if not isinstance(doc, Mapping) or not isinstance(doc.get("arbol"), list):
        raise ErrorValidacion("nichos.yaml: se esperaba {arbol: [...]}")
    ids_microsegmento: dict[str, str] = {}  # id -> "macro/nicho" donde ya apareció (detecta duplicados)
    for i, rama in enumerate(doc["arbol"]):
        ruta_rama = f"arbol[{i}]"
        if not isinstance(rama, Mapping):
            errores.append(f"{ruta_rama}: debe ser un objeto")
            continue
        macro = rama.get("macro_nicho")
        if macro not in MACROS:
            errores.append(f"{ruta_rama}.macro_nicho: {macro!r} no está en {MACROS}")
        elif macro not in macro_nichos_permitidos:
            errores.append(f"{ruta_rama}.macro_nicho: {macro!r} no está en macro_nichos_permitidos")
        nichos = rama.get("nichos")
        if not isinstance(nichos, list) or not nichos:
            errores.append(f"{ruta_rama}.nichos: lista no vacía")
            continue
        for j, nicho in enumerate(nichos):
            ruta_nicho = f"{ruta_rama}.nichos[{j}]"
            if not isinstance(nicho, Mapping):
                errores.append(f"{ruta_nicho}: debe ser un objeto")
                continue
            nicho_id = nicho.get("nicho_id")
            if not _es_kebab(nicho_id):
                errores.append(f"{ruta_nicho}.nicho_id: {nicho_id!r} debe ser kebab-case ASCII")
            micros = nicho.get("microsegmentos")
            if not isinstance(micros, list) or not micros:
                errores.append(f"{ruta_nicho}.microsegmentos: lista no vacía")
                continue
            for k, hoja in enumerate(micros):
                ruta_hoja = f"{ruta_nicho}.microsegmentos[{k}]"
                if not isinstance(hoja, Mapping):
                    errores.append(f"{ruta_hoja}: debe ser un objeto")
                    continue
                hoja_id = hoja.get("id")
                if not _es_kebab(hoja_id):
                    errores.append(f"{ruta_hoja}.id: {hoja_id!r} debe ser kebab-case ASCII")
                elif hoja_id in ids_microsegmento:
                    errores.append(f"{ruta_hoja}.id: {hoja_id!r} repetido (ya en {ids_microsegmento[hoja_id]})")
                else:
                    ids_microsegmento[hoja_id] = f"{macro}/{nicho_id}"
                secundario = hoja.get("macro_secundario")
                if secundario is not None:
                    if secundario not in MACROS:
                        errores.append(f"{ruta_hoja}.macro_secundario: {secundario!r} no está en {MACROS}")
                    elif secundario == macro:
                        errores.append(f"{ruta_hoja}.macro_secundario: no puede igualar al macro_nicho primario")
                tanda = hoja.get("tanda")
                if not isinstance(tanda, int) or isinstance(tanda, bool) or tanda < 1:
                    errores.append(f"{ruta_hoja}.tanda: debe ser un entero >= 1")
                if not hoja.get("estado"):
                    errores.append(f"{ruta_hoja}.estado: obligatorio")

    fuera = doc.get("semillas_fuera_de_marco") or []
    if not isinstance(fuera, list):
        errores.append("semillas_fuera_de_marco: debe ser una lista")
    else:
        for i, f in enumerate(fuera):
            ruta_f = f"semillas_fuera_de_marco[{i}]"
            if not isinstance(f, Mapping):
                errores.append(f"{ruta_f}: debe ser un objeto")
                continue
            if not _es_kebab(f.get("id")):
                errores.append(f"{ruta_f}.id: debe ser kebab-case ASCII")
            elif f["id"] in ids_microsegmento:
                errores.append(f"{ruta_f}.id: {f['id']!r} también aparece sembrada en el árbol (decisión 13: nunca se siembra)")
            if f.get("estado") != "registrada_no_sembrada":
                errores.append(f"{ruta_f}.estado: debe ser 'registrada_no_sembrada' (nunca se siembra, interfaces §1.4)")
            if not f.get("motivo_macro"):
                errores.append(f"{ruta_f}.motivo_macro: obligatorio")
    return errores


def hojas(doc: Mapping[str, Any]) -> list[tuple[str, str]]:
    """``[(nicho_id, microsegmento_id), ...]`` de un árbol YA VALIDADO (para `ficha_a_candidato` regla 3)."""
    salida: list[tuple[str, str]] = []
    for rama in doc.get("arbol", []):
        for nicho in rama.get("nichos", []):
            for hoja in nicho.get("microsegmentos", []):
                salida.append((nicho["nicho_id"], hoja["id"]))
    return salida


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.descubrimiento.nichos",
                                description="Validador de nichos.yaml (interfaces §3.4)")
    sub = p.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validar")
    v.add_argument("ruta", type=Path)
    v.add_argument("--macro-nichos-permitidos", default=",".join(MACROS))
    v.add_argument("--json", action="store_true")
    return p


def _principal(argv: list[str] | None) -> int:
    try:
        a = _parser().parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None):
            return 0
        raise ErrorUso("argumentos inválidos (ver --help)") from None
    try:
        doc = comun.cargar_yaml(a.ruta)
    except FileNotFoundError as exc:
        raise ErrorUso(f"no se encontró {a.ruta}") from exc
    permitidos = [m.strip() for m in a.macro_nichos_permitidos.split(",") if m.strip()]
    errores = validar_nichos(doc, macro_nichos_permitidos=permitidos)
    if a.json:
        print(json.dumps({"errores": errores, "n_hojas": len(hojas(doc)) if not errores else None},
                         ensure_ascii=False, sort_keys=True))
    else:
        print("\n".join(errores) if errores else f"nichos.yaml: 0 errores ({len(hojas(doc))} hojas)")
    return 3 if errores else 0


def main(argv: list[str] | None = None) -> int:
    return ejecutar_cli(lambda: _principal(argv))


if __name__ == "__main__":
    raise SystemExit(main())
