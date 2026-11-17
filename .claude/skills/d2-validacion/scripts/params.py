"""Carga de parámetros de D2 (falla cerrado). Solo biblioteca estándar y PyYAML. Sin red.

Ningún umbral vive en los scripts de D2: salen de `empresa/parametros.yaml` (aprobado por el dueño) y, para las claves
que aún no existen allí (marcadas † en el Anexo A de la spec), de `references/parametros_d2.propuesta.yaml`.
Si una clave falta en las dos fuentes, se aborta con código 5 (como `barrido` y `puntaje_modelar`). Nunca se asume un valor.

Códigos de salida de los scripts de D2: 0 correcto · 2 uso · 3 validación (dato fuera de contrato, veredicto
incoherente, diferencia de recálculo) · 5 falta un parámetro.
"""
from __future__ import annotations

from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[4]  # .claude/skills/d2-validacion/scripts/params.py -> raíz del repositorio
PROPUESTA = Path(__file__).resolve().parents[1] / "references" / "parametros_d2.propuesta.yaml"
OFICIAL = RAIZ / "empresa" / "parametros.yaml"

# Claves que existen (o deben existir) en empresa/parametros.yaml: grupo -> claves. Las demás se leen de la propuesta.
OFICIALES = {
    "validacion": ["umbral_ss", "n_ind_sost_go", "is_go_max", "is_nogo_min", "umbral_hueco_ausencia", "min_frases_voz",
                   "min_fuentes_voz", "max_palabras_cita", "relectura_dias", "n_competidores_profundos", "sim_concepto"],
    "descubrimiento": ["anunciante_sostenido_dias_min", "anunciante_sostenido_conceptos_min"],
}


class ErrorD2(Exception):
    codigo = 1


class ErrorUso(ErrorD2):
    codigo = 2


class ErrorValidacion(ErrorD2):
    codigo = 3


class ErrorLimite(ErrorD2):
    """Falta un parámetro (falla cerrado)."""
    codigo = 5


def _leer_yaml(ruta: Path) -> dict:
    try:
        with open(ruta, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
    except OSError as e:
        raise ErrorUso(f"no se puede leer {ruta}: {e}") from e
    except yaml.YAMLError as e:
        raise ErrorValidacion(f"YAML inválido en {ruta}: {e}") from e
    if not isinstance(doc, dict) or not isinstance(doc.get("grupos"), dict):
        raise ErrorValidacion(f"{ruta}: se esperaba `grupos:` en la raíz")
    return doc["grupos"]


def _valor(entrada: Any) -> Any:
    if isinstance(entrada, dict) and "valor" in entrada:
        return entrada["valor"]
    return None


def cargar(oficial: Path | None = None, propuesta: Path | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    """Devuelve (valores, origenes). `valores` es plano: clave -> valor crudo (int o cadena decimal).

    Precedencia: el valor aprobado (empresa/parametros.yaml) manda sobre la propuesta. `origenes[clave]` es
    'parametros.yaml' o 'propuesta' para que el QA vea de dónde salió cada umbral.
    """
    g_of = _leer_yaml(oficial or OFICIAL)
    g_pr = _leer_yaml(propuesta or PROPUESTA)
    valores: dict[str, Any] = {}
    origenes: dict[str, str] = {}
    for grupo, claves in OFICIALES.items():
        for k in claves:
            v = _valor((g_of.get(grupo) or {}).get(k))
            if v is not None:
                valores[k] = v
                origenes[k] = "parametros.yaml"
    for grupo, claves in g_pr.items():
        for k, entrada in (claves or {}).items():
            v = _valor(entrada)
            if v is None:
                continue
            if k not in valores:
                valores[k] = v
                origenes[k] = "propuesta"
    return valores, origenes


def exigir(valores: dict[str, Any], claves: list[str]) -> None:
    faltan = [k for k in claves if valores.get(k) is None]
    if faltan:
        raise ErrorLimite("faltan parámetros (falla cerrado): " + ", ".join(faltan))


def dec(v: Any) -> Decimal:
    """Decimal exacto desde int o cadena decimal. Rechaza float nativo (regla del repositorio)."""
    if isinstance(v, float) or isinstance(v, bool):
        raise ErrorValidacion(f"valor numérico no permitido (float/bool): {v!r}; usa entero o cadena decimal")
    return Decimal(str(v))


def frac(v: Any) -> Fraction:
    if isinstance(v, float) or isinstance(v, bool):
        raise ErrorValidacion(f"valor numérico no permitido (float/bool): {v!r}; usa entero o cadena decimal")
    return Fraction(str(v))
