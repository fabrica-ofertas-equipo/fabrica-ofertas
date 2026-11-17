"""`similitud_memoria` determinista contra `descartes.jsonl` y candidatos previos (departamentos/02 §3.2;
interfaces d1-v2 §8.2 n.2). Alimenta la regla 7 de `ficha_a_candidato` (§3.8.1).

La especificación pide "un modelo de embeddings local fijado en `parametros.yaml` [VERIFICAR]"; no
existe ninguno sin red ni dependencias nuevas (convenciones §13), así que este módulo usa una
heurística determinista **sin red y sin LLM**: similitud de Jaccard sobre tokens normalizados de
``audiencia``, ``resultado``, ``obstaculo`` y ``formato`` (los cuatro campos de D1 §3.2), promediados.
Es [HIPÓTESIS] -- un sustituto explícito, no el modelo de embeddings pedido -- y queda documentado
como pedido abierto (ver README, «Decisiones»).

Un juicio categórico del Maker o del QA ("mismo problema, misma audiencia") vale `sim = 1` sin mirar
texto: se declara con ``mismo_problema_categorico: true`` en el ítem de memoria.

Uso::

    python -m scripts.descubrimiento.dedup calcular --candidato candidato.json --memoria memoria.json [--json]

``candidato.json``/cada ítem de ``memoria.json``: ``{"id": "...", "audiencia": "...", "resultado":
"...", "obstaculo": "...", "formato": "...", "mismo_problema_categorico": false}``.

Códigos de salida (convenciones §8): 0 ok · 2 uso · 3 validación.
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from decimal import ROUND_HALF_EVEN, Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine.comun import ejecutar_cli
from engine.errores import ErrorUso, ErrorValidacion

CAMPOS = ("audiencia", "resultado", "obstaculo", "formato")
CERO = Decimal(0)
UNO = Decimal(1)
_CUATRO_DECIMALES = Decimal("0.0001")


def _tokens(texto: Any) -> set[str]:
    if not isinstance(texto, str) or not texto.strip():
        return set()
    normal = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii").casefold()
    return set(re.findall(r"[a-z0-9]+", normal))


def similitud_texto(a: Any, b: Any) -> Decimal | None:
    """Jaccard de tokens de ``a`` y ``b``; ``None`` si alguno de los dos está vacío (campo sin dato)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return None
    interseccion = len(ta & tb)
    union = len(ta | tb)
    return (Decimal(interseccion) / Decimal(union)).quantize(_CUATRO_DECIMALES, rounding=ROUND_HALF_EVEN)


def similitud_par(candidato: Mapping[str, Any], memoria_item: Mapping[str, Any]) -> Decimal:
    """Similitud (0-1) entre un candidato y UN ítem de memoria: promedio de los campos con dato en ambos."""
    if memoria_item.get("mismo_problema_categorico"):
        return UNO
    valores = [similitud_texto(candidato.get(c), memoria_item.get(c)) for c in CAMPOS]
    conocidos = [v for v in valores if v is not None]
    if not conocidos:
        return CERO
    return (sum(conocidos) / Decimal(len(conocidos))).quantize(_CUATRO_DECIMALES, rounding=ROUND_HALF_EVEN)


def similitud_memoria(candidato: Mapping[str, Any], memoria: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """``{"max": "<decimal>", "con": id|None}`` -- la forma exacta de `candidatos.json#similitud_memoria`.

    Memoria vacía => ``max = "0"``, ``con = None`` (nunca se omite: interfaces §3.8.1 regla 7 exige el
    campo presente). Errores: ``ErrorValidacion`` si ``candidato`` no es un objeto.
    """
    if not isinstance(candidato, Mapping):
        raise ErrorValidacion("candidato: se esperaba un objeto con audiencia/resultado/obstaculo/formato")
    mejor_sim = CERO
    mejor_id: str | None = None
    for item in memoria:
        if not isinstance(item, Mapping):
            raise ErrorValidacion("memoria: cada ítem debe ser un objeto")
        sim = similitud_par(candidato, item)
        if sim > mejor_sim or (sim == mejor_sim and mejor_id is None):
            mejor_sim, mejor_id = sim, item.get("id")
    return {"max": str(mejor_sim), "con": mejor_id if mejor_sim > CERO else None}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.descubrimiento.dedup",
                                description="similitud_memoria determinista (D1 §3.2)")
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("calcular")
    c.add_argument("--candidato", type=Path, required=True)
    c.add_argument("--memoria", type=Path, required=True, help="JSON: lista de ítems de memoria")
    c.add_argument("--json", action="store_true")
    return p


def _leer_json(ruta: Path) -> Any:
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ErrorUso(f"no se encontró {ruta}") from exc
    except json.JSONDecodeError as exc:
        raise ErrorValidacion(f"{ruta}: JSON inválido ({exc})") from exc


def _principal(argv: list[str] | None) -> int:
    try:
        a = _parser().parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None):
            return 0
        raise ErrorUso("argumentos inválidos (ver --help)") from None
    candidato = _leer_json(a.candidato)
    memoria = _leer_json(a.memoria)
    if not isinstance(memoria, list):
        raise ErrorValidacion("--memoria debe ser una lista JSON")
    resultado = similitud_memoria(candidato, memoria)
    print(json.dumps(resultado, ensure_ascii=False, sort_keys=True) if a.json
          else f"max={resultado['max']} con={resultado['con']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return ejecutar_cli(lambda: _principal(argv))


if __name__ == "__main__":
    raise SystemExit(main())
