"""``infra.variables``: manifiesto de variables de entorno y regeneración de ``.env.example``.

Lee ``infra/plantillas/variables-entorno.yaml`` (manifiesto normativo de TODAS las plataformas y
servicios: Railway, Cloudflare Workers, GitHub, equipo del dueño) y genera el contenido canónico de
``.env.example`` en la raíz del repositorio: **solo nombres y comentarios, nunca valores**
(convenciones §10). Determinista: la misma entrada produce los mismos bytes.

Los *bindings* de Cloudflare (nombre con un espacio, p. ej. ``"BUCKET_PRODUCTOS (binding R2)"``) no
son variables de entorno que se carguen por ``os.environ``: se configuran en ``wrangler.toml``. Se
documentan como comentario pero no generan una línea ``NOMBRE=``. Un ``nombre`` con un *placeholder*
entre ``<...>`` (``META_CAPI_TOKEN__<oferta_id>``) se normaliza a ``_EJEMPLO`` para el archivo de
ejemplo (igual convención que el ``.env.example`` anterior).

``--check``: no escribe nada; compara el ``.env.example`` actual contra lo que generaría el
manifiesto y sale con el código de desincronización si difiere (edición manual, variable agregada
al manifiesto sin regenerar, o variable borrada del manifiesto que seguía en el archivo).

CLI::

    python -m infra.variables generar [--manifiesto RUTA] [--salida RUTA] [--raiz RUTA] [--json]
    python -m infra.variables generar --check [--manifiesto RUTA] [--salida RUTA] [--raiz RUTA] [--json]

Salida (convenciones §8): 0 generado o sincronizado · 2 uso · 3 manifiesto inválido o (con
``--check``) archivo desincronizado.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion

__all__ = [
    "VariableManifiesto", "agrupar_por_nombre", "es_binding", "extraer_variables", "generar_env_example",
    "main", "nombre_normalizado", "ruta_env_example", "ruta_manifiesto",
]

_RX_PLACEHOLDER = re.compile(r"<[a-z_]+>")
_CABECERA = (
    "# =============================================================================\n"
    "# .env.example: TODAS las variables de entorno previstas, SIN valores.\n"
    "# GENERADO por `python -m infra.variables generar` desde\n"
    "# infra/plantillas/variables-entorno.yaml (docs/06 D-13). NO EDITAR A MANO:\n"
    "# cambiar el manifiesto y volver a generar (`infra.variables generar --check`\n"
    "# falla si quedan desincronizados).\n"
    "# Copiar a .env (ignorado por git) o cargar en Railway/Cloudflare. Nunca poner\n"
    "# credenciales en archivos versionados, argumentos de CLI, logs ni pruebas.\n"
    "# Los bindings de Cloudflare (nombre con un espacio, p. ej. «(binding R2)») se\n"
    "# configuran en wrangler.toml: se documentan pero no generan línea NOMBRE=.\n"
    "# =============================================================================\n"
)


@dataclass(frozen=True)
class VariableManifiesto:
    """Una entrada ``{nombre, tipo, origen, rotacion_dias, obligatoria}`` del manifiesto, con su contexto."""

    nombre_crudo: str
    tipo: str
    origen: str
    rotacion_dias: Any
    obligatoria: Any
    ruta: str  # contexto punteado, p. ej. "plataformas.railway.servicios.motor"


def es_binding(nombre_crudo: str) -> bool:
    """¿Es un *binding* de Cloudflare (no una variable de entorno que se cargue por nombre)?"""
    return " " in nombre_crudo.strip()


def nombre_normalizado(nombre_crudo: str) -> str:
    """Nombre de variable para ``.env.example``: el primer token (antes de un espacio) con el
    *placeholder* ``<...>`` reemplazado por ``EJEMPLO``."""
    base = nombre_crudo.strip().split(" ", 1)[0]
    return _RX_PLACEHOLDER.sub("EJEMPLO", base)


def ruta_manifiesto(raiz: Path | None = None) -> Path:
    """Ruta de ``infra/plantillas/variables-entorno.yaml`` (siempre bajo el CÓDIGO, no ``FABRICA_RAIZ``)."""
    base = raiz if raiz is not None else Path(__file__).resolve().parents[1]
    return base / "infra" / "plantillas" / "variables-entorno.yaml"


def ruta_env_example(raiz: Path | None = None) -> Path:
    """Ruta de ``.env.example`` en la raíz del repositorio (o de la raíz inyectada en pruebas)."""
    base = raiz if raiz is not None else Path(__file__).resolve().parents[1]
    return base / ".env.example"


# ----------------------------------------------------------------------------------------------
# Extracción recursiva (cualquier mapa que tenga una clave «variables» o «secretos» con lista de
# {nombre, ...} aporta entradas; así el manifiesto puede crecer de forma libre sin tocar este módulo)
# ----------------------------------------------------------------------------------------------
_CLAVES_LISTA_DE_VARIABLES = ("variables", "secretos")


def extraer_variables(datos: Mapping[str, Any]) -> list[VariableManifiesto]:
    """Recorre el manifiesto y devuelve TODAS las entradas de variable, con su ruta de contexto.

    Errores: ``ErrorValidacion`` (3) si el manifiesto no es un mapa o una entrada no tiene ``nombre``.
    """
    if not isinstance(datos, Mapping):
        raise ErrorValidacion("variables-entorno.yaml: se esperaba un mapa en la raíz")
    resultado: list[VariableManifiesto] = []

    def recorrer(nodo: Any, ruta: tuple[str, ...]) -> None:
        if isinstance(nodo, Mapping):
            for clave, valor in nodo.items():
                if clave in _CLAVES_LISTA_DE_VARIABLES and isinstance(valor, list):
                    for entrada in valor:
                        if not isinstance(entrada, Mapping) or not entrada.get("nombre"):
                            raise ErrorValidacion(f"{'.'.join(ruta) or '/'}.{clave}: entrada sin «nombre»")
                        resultado.append(VariableManifiesto(
                            nombre_crudo=str(entrada["nombre"]), tipo=str(entrada.get("tipo", "")),
                            origen=str(entrada.get("origen", "")), rotacion_dias=entrada.get("rotacion_dias"),
                            obligatoria=entrada.get("obligatoria"), ruta=".".join(ruta),
                        ))
                elif isinstance(valor, (Mapping, list)):
                    recorrer(valor, ruta + (str(clave),))
        elif isinstance(nodo, list):
            for item in nodo:
                recorrer(item, ruta)

    recorrer(datos, ())
    if not resultado:
        raise ErrorValidacion("variables-entorno.yaml: no se encontró ninguna variable")
    return resultado


def agrupar_por_nombre(variables: Sequence[VariableManifiesto]) -> dict[str, list[VariableManifiesto]]:
    """Agrupa por nombre normalizado, EXCLUYENDO los *bindings* de Cloudflare. Conserva el orden de aparición."""
    agrupado: dict[str, list[VariableManifiesto]] = {}
    for v in variables:
        if es_binding(v.nombre_crudo):
            continue
        agrupado.setdefault(nombre_normalizado(v.nombre_crudo), []).append(v)
    return agrupado


def generar_env_example(variables: Sequence[VariableManifiesto]) -> bytes:
    """Contenido determinista de ``.env.example`` (UTF-8) a partir de las variables extraídas."""
    agrupado = agrupar_por_nombre(variables)
    lineas = [_CABECERA.rstrip("\n")]
    for nombre, entradas in agrupado.items():
        primero = entradas[0]
        contextos = sorted({e.ruta for e in entradas if e.ruta})
        descripcion = f"{primero.tipo or 'config'}: {primero.origen}" if primero.origen else (primero.tipo or "config")
        lineas.append(f"\n# {descripcion}")
        if contextos:
            lineas.append(f"# usada por: {', '.join(contextos)}")
        lineas.append(f"{nombre}=")
    return ("\n".join(lineas) + "\n").encode("utf-8")


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m infra.variables",
                                 description="Manifiesto de variables de entorno y regeneración de .env.example.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    pg = sub.add_parser("generar")
    pg.add_argument("--manifiesto")
    pg.add_argument("--salida")
    pg.add_argument("--raiz")
    pg.add_argument("--check", action="store_true", help="no escribe; falla (3) si .env.example está desincronizado")
    pg.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        env = dict(os.environ)
        if args.raiz and comun.entorno(env) == "produccion":
            raise ErrorUso("--raiz no existe con FABRICA_ENTORNO=produccion")
        raiz = Path(args.raiz).resolve() if args.raiz else comun.raiz(env)
        ruta_man = Path(args.manifiesto).resolve() if args.manifiesto else ruta_manifiesto()
        ruta_salida = Path(args.salida).resolve() if args.salida else ruta_env_example(raiz)

        datos = comun.cargar_yaml(ruta_man)
        variables = extraer_variables(datos)
        contenido = generar_env_example(variables)
        cantidad = len(agrupar_por_nombre(variables))

        if args.check:
            actual = ruta_salida.read_bytes() if ruta_salida.is_file() else b""
            sincronizado = actual == contenido
            datos_salida = {"sincronizado": sincronizado, "ruta": str(ruta_salida), "variables": cantidad}
            codigo = 0 if sincronizado else 3
        else:
            comun.escribir_atomico(ruta_salida, contenido)
            datos_salida = {"ruta": str(ruta_salida), "variables": cantidad}
            codigo = 0

        if args.json:
            print(json.dumps({"ok": codigo == 0, "modo": "dry_run", "codigo": codigo, "datos": datos_salida, "avisos": []},
                             sort_keys=True, ensure_ascii=False))
        else:
            print(json.dumps(datos_salida, ensure_ascii=False, sort_keys=True))
        return codigo

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
