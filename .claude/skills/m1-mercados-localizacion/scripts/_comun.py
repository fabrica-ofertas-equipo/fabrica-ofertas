"""Utilidades comunes de los scripts de M1 (solo biblioteca estandar; PyYAML opcional). Sin red, sin secretos.

Codigos de salida (docs/convenciones-de-codigo.md §8): 0 correcto · 2 uso · 3 validacion/hallazgos bloqueantes ·
5 dato o parametro faltante (fail-closed: sin dato, nada se decide).
"""
from __future__ import annotations

import datetime as _dt
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
# .claude/skills/<slug>/scripts -> raiz del repositorio (4 niveles); FABRICA_RAIZ permite una raiz de datos distinta.
RAIZ = os.environ.get("FABRICA_RAIZ") or os.path.abspath(os.path.join(AQUI, "..", "..", "..", ".."))
SALIDA_OK, SALIDA_USO, SALIDA_VALIDACION, SALIDA_FALTA_DATO = 0, 2, 3, 5

# Orden verde < amarillo-a < amarillo-b < rojo. Escritura canonica en MINUSCULAS con guion (contratos/comunes#nivel_lanzable; limites.nivel_max_lanzable);
# el SUBNIVEL de candidatos.riesgo (A | B | null) es otro campo y no usa este enum.
NIVELES = ["verde", "amarillo-a", "amarillo-b", "rojo"]


class DatoFaltante(Exception):
    """Falta un parametro o un dato obligatorio: el llamador sale con 5 (fail-closed)."""


def cargar_json(ruta):
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def cargar_datos(ruta):
    """JSON siempre; YAML si PyYAML esta disponible (usar .venv/bin/python)."""
    ruta = str(ruta)
    if ruta.endswith((".yaml", ".yml")):
        try:
            import yaml  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise DatoFaltante(f"{ruta}: hace falta PyYAML (usar .venv/bin/python -I)") from e
        with open(ruta, encoding="utf-8") as f:
            return yaml.safe_load(f)
    return cargar_json(ruta)


def escribir_json(obj, ruta=None):
    texto = json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=False)
    if ruta:
        with open(ruta, "w", encoding="utf-8") as f:
            f.write(texto + "\n")
    else:
        print(texto)


def hay_float(obj, ruta=""):
    """Rutas con float nativo (convenciones §5: sin float; dinero entero, decimales como cadena)."""
    out = []
    if isinstance(obj, float):
        out.append(ruta or "/")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            out += hay_float(v, f"{ruta}/{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            out += hay_float(v, f"{ruta}/{i}")
    return out


def fecha(s):
    """AAAA-MM-DD (o timestamp ISO con Z) -> date. ValueError si no es fecha valida."""
    if isinstance(s, _dt.date):
        return s
    return _dt.date.fromisoformat(str(s)[:10])


def valor(nodo, *camino, defecto=None):
    """Lee un campo de una ficha de pais: baja por `camino` y desenvuelve {valor, fuente_url, fecha_lectura, confianza}."""
    for c in camino:
        if isinstance(nodo, dict) and c in nodo:
            nodo = nodo[c]
        else:
            return defecto
    if isinstance(nodo, dict) and "valor" in nodo:
        return nodo["valor"]
    return nodo


def cargar_parametros(ruta_parametros=None, fallback=None):
    """Devuelve (params, origen). Primero el fallback [SUPUESTO] de la skill; despues empresa/parametros.yaml
    (grupos.mercados.<clave>.valor) SOBRESCRIBE cada clave que exista. Las claves que solo existen en parametros.yaml
    (clics_min_decidir_mercado, mercados_test_paralelos_max...) faltan si no hay PyYAML: se piden con `pedir`."""
    fallback = fallback or os.path.join(AQUI, "parametros_m1.fallback.json")
    fb = cargar_json(fallback)
    params, origen = {}, {}
    for k, v in fb.items():
        if not k.startswith("_"):
            params[k], origen[k] = v, "[SUPUESTO] parametros_m1.fallback.json"
    ruta = ruta_parametros or os.path.join(RAIZ, "empresa", "parametros.yaml")
    if os.path.exists(ruta):
        try:
            import yaml  # type: ignore
        except ImportError:
            yaml = None
        if yaml is not None:
            with open(ruta, encoding="utf-8") as f:
                grupos = (yaml.safe_load(f) or {}).get("grupos", {}) or {}
            for k, e in (grupos.get("mercados", {}) or {}).items():
                if isinstance(e, dict) and "valor" in e:
                    params[k], origen[k] = e["valor"], "empresa/parametros.yaml"
            # Hogar unico del muestreo nativo posterior (C-05 / R-08): grupo `producto`; M1 lo LEE, no lo duplica en `mercados`.
            e = (grupos.get("producto", {}) or {}).get("linguistica_muestreo_nativo_posterior")
            if isinstance(e, dict) and "valor" in e:
                params["producto"] = dict(params.get("producto", {}), linguistica_muestreo_nativo_posterior=e["valor"])
                origen["producto.linguistica_muestreo_nativo_posterior"] = "empresa/parametros.yaml"
    return params, origen


def pedir(params, clave):
    if clave not in params or params[clave] is None:
        raise DatoFaltante(f"parametro mercados.{clave} ausente (usar .venv/bin/python para leer empresa/parametros.yaml): sin dato no se decide")
    return params[clave]


def imprimir_error(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
