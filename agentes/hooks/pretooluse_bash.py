#!/usr/bin/env python3
"""``pretooluse_bash.py`` — argumentos de ``Bash`` (crítica M12, docs/09 §14.5b).

Los comodines ``Bash(python3 scripts/<validador> *)`` aceptan argumentos arbitrarios
(``--archivo ../../.env``). Este hook: (1) rechaza metacaracteres de shell en el comando crudo
(``shlex.split`` no los separa: eso lo hace ``bash``, no Python); (2) exige que el script invocado
esté en la lista blanca de ``herramientas.yaml`` (``bash_scripts``); (3) exige que cada ``--flag``
esté en la lista blanca de ESE script; (4) exige que todo argumento con forma de ruta resuelva
(``Path.resolve()``) dentro de ``AGENT_RAIZ/ofertas/<AGENT_OFERTA_ID>/``.

Solo corre sobre ``tool_name == "Bash"``; para las demás herramientas no opina (``None``).
"""
from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import Mapping

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # bootstrap: ver agentes/hooks/_comun.py

from agentes.hooks import _comun as c  # noqa: E402

_METACARACTERES = (";", "&", "|", "`", "$(", ">", "<", "\n")


def _parece_ruta(valor: str) -> bool:
    return "/" in valor or valor in ("..", ".") or valor.endswith((".py", ".json", ".yaml", ".yml"))


def _forma_modulo(nombre: str) -> str | None:
    """``scripts/x/y.py`` -> ``scripts.x.y`` (la forma ``python -m``); ``None`` si no es un archivo ``.py`` con ruta."""
    if not nombre.endswith(".py") or nombre.startswith("."):
        return None
    return nombre[:-3].replace("/", ".")


def _script_de(partes: list[str], bash_scripts: Mapping[str, Mapping]) -> tuple[str, int] | None:
    """Script de la lista blanca invocado por archivo (``scripts/x.py``) o como módulo (``python -m scripts.x``).
    Las banderas y las rutas se comprueban IGUAL en las dos formas (antes la forma módulo no se reconocía y quedaba
    sin comprobar: SB-4)."""
    for i, p in enumerate(partes):
        for nombre in bash_scripts:
            if p == nombre or p.endswith("/" + nombre):
                return nombre, i
            modulo = _forma_modulo(nombre)
            if modulo is not None and p == modulo and i > 0 and partes[i - 1] == "-m":
                return nombre, i
    return None


def _ruta_de_lectura_permitida(bandera_previa: str | None, arg: str, rutas_por_bandera: Mapping[str, list], raiz: Path) -> bool:
    """``--parametros``/``--limites`` pueden apuntar SOLO a ``empresa/parametros.yaml``/``empresa/limites.yaml`` (lectura;
    lista en ``rutas_lectura_por_bandera`` de ``herramientas.yaml``). Cualquier otra ruta sigue sujeta a ``ofertas/<id>/``."""
    permitidas = rutas_por_bandera.get(bandera_previa or "")
    if not permitidas:
        return False
    destino = Path(arg) if Path(arg).is_absolute() else (raiz / arg)
    return any(c.ruta_dentro_de(destino, raiz / ruta) or destino.resolve() == (raiz / ruta).resolve() for ruta in permitidas)


def _comprobar(comando: str, env: Mapping[str, str]) -> str | None:
    if not comando.strip():
        return None
    encontrados = [m for m in _METACARACTERES if m in comando]
    if encontrados:
        return f"Bash: carácter de shell no permitido ({encontrados[0]!r})"
    try:
        partes = shlex.split(comando)
    except ValueError as exc:
        return f"Bash: comando ilegible para shlex ({exc})"
    if not partes:
        return None
    herramientas = c.cargar_herramientas()
    bash_scripts = herramientas.get("bash_scripts") or {}
    hallado = _script_de(partes, bash_scripts)
    if hallado is None:
        return None  # ningún script conocido: lo evalúa pretooluse_gasto (lectura/escritura genérica)
    nombre_script, indice = hallado
    permitidas = set(bash_scripts[nombre_script].get("flags") or ())
    raiz = c.raiz_agente(env)
    oferta_id = (env.get("AGENT_OFERTA_ID") or "").strip()
    base_ofertas = (raiz / "ofertas" / oferta_id) if oferta_id else None
    resto = partes[indice + 1:]
    rutas_por_bandera = herramientas.get("rutas_lectura_por_bandera") or {}
    i = 0
    bandera_previa: str | None = None
    while i < len(resto):
        arg = resto[i]
        if arg.startswith("--") or (arg.startswith("-") and len(arg) > 1 and not arg[1:2].isdigit()):
            if arg not in permitidas:
                return f"Bash: flag no permitido para {nombre_script}: {arg}"
            bandera_previa = arg
            i += 1
            continue
        if _parece_ruta(arg):
            if _ruta_de_lectura_permitida(bandera_previa, arg, rutas_por_bandera, raiz):
                bandera_previa = None
                i += 1
                continue
            if base_ofertas is None:
                return f"Bash: argumento con forma de ruta sin AGENT_OFERTA_ID para resolverla: {arg}"
            if not c.ruta_dentro_de(Path(arg) if Path(arg).is_absolute() else (raiz / arg), base_ofertas):
                return f"Bash: argumento fuera de AGENT_RAIZ/ofertas/{oferta_id}/: {arg}"
        bandera_previa = None
        i += 1
    return None


def manejar(datos: Mapping) -> str | None:
    import os

    if str(datos.get("tool_name") or "") != "Bash":
        return None
    tool_input = datos.get("tool_input") if isinstance(datos.get("tool_input"), Mapping) else {}
    comando = str(tool_input.get("command") or "")
    motivo = _comprobar(comando, os.environ)
    if motivo:
        c.anotar_spool(os.environ, c.construir_entrada_registro(
            os.environ, evento="PreToolUse", tool="Bash", tool_use_id=datos.get("tool_use_id"), entrada={}, resultado="deny",
        ))
    return motivo


if __name__ == "__main__":
    c.ejecutar(manejar)
