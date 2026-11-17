"""Lint de contenido de D4: matriz de promesas, placeholders, formato, tamaño, sin datos personales.

Promueve a ``scripts/`` una porción ACOTADA (hito B0, genérica) de la lógica de
``.claude/skills/d4-producto/scripts/lint_contenido.py``: esa skill trae un léxico extenso por idioma
(palabras vetadas, diagnóstico, testimonios, credenciales falsas…) que hoy vive SOLO en los recursos de la
skill (``.claude/skills/d4-producto/scripts/_patrones.py``) y en reglas de X1 (``compliance/reglas_sensibles.yaml``,
dueño B6); replicarlo aquí sería duplicarlo a ciegas sin dueño claro de su mantenimiento. Este módulo cubre lo
que ``departamentos/05-producto.md`` exige con datos deterministas y sin lista de palabras: marcas pendientes
([VERIFICAR]/[SUPUESTO]/TODO/lorem ipsum), coherencia de ``matriz_promesas`` contra los ``items`` reales,
tamaño de archivo contra los parámetros oficiales ``producto.peso_max_mb_pdf``/``producto.peso_max_mb_paquete``,
y datos personales obvios (correo electrónico, teléfono). El léxico completo por idioma y las reglas de X1
siguen siendo trabajo de X1/QA L2 (ver README «Decisiones»).

CLI::

    .venv/bin/python -m scripts.producto.lint PRODUCTO.json --fuente DIR [DIR ...] [--parametros P.yaml] [--json]

Salida: 0 si el veredicto es PASS o PASS_CON_NOTAS · 3 si hay un hallazgo BLOQUEANTE (FAIL) o la entrada no
tiene forma válida · 5 si falta un parámetro oficial de tamaño.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion, ParametroFaltante
from engine.parametros import Parametros, cargar_parametros

__all__ = ["lintear", "main"]

VERSION_SCRIPT = "1.0.0"
EXTENSIONES = (".md", ".txt", ".html", ".htm")
RANGO_SEVERIDAD = {"MEJORA": 0, "MENOR": 1, "MAYOR": 2, "BLOQUEANTE": 3}

_RX_MARCA_PENDIENTE = re.compile(r"\[(VERIFICAR|SUPUESTO|TODO|PENDIENTE)\]", re.I)
_RX_LOREM = re.compile(r"\blorem\s+ipsum\b", re.I)
_RX_PLACEHOLDER_LLAVES = re.compile(r"\{\{[^}]+\}\}|\{[a-z_]+\}")
_RX_CORREO = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+")
_RX_TELEFONO = re.compile(r"(?<![\d])\+?[0-9][0-9 \-]{7,15}[0-9](?![\d])")
_BYTES_POR_MB = 1_000_000


def _valor_parametro(parametros: Any, clave: str) -> Any:
    """Valor de ``producto.<clave>``, de un ``Parametros`` o de un mapa ``{grupos: {...}}`` ya cargado.

    Falla cerrado (``ParametroFaltante``, código 5) si el parámetro no existe o está en ``null``.
    """
    if isinstance(parametros, Parametros):
        return parametros.valor(f"producto.{clave}")
    if not isinstance(parametros, Mapping):
        raise ParametroFaltante(f"producto.{clave}", "no se proporcionó ningún parámetro")
    try:
        entrada = parametros["grupos"]["producto"][clave]
        valor = entrada["valor"] if isinstance(entrada, Mapping) else entrada
    except (KeyError, TypeError) as exc:
        raise ParametroFaltante(f"producto.{clave}", "no existe en parametros.yaml") from exc
    if valor is None:
        raise ParametroFaltante(f"producto.{clave}", "sin valor (null): pendiente de calibrar por el dueño")
    return valor


def _hallazgo(check_id: str, severidad: str, mensaje: str, ubicacion: str) -> dict[str, str]:
    return {"check_id": check_id, "severidad": severidad, "mensaje": mensaje, "ubicacion": ubicacion}


def _peor_severidad(hallazgos: Iterable[Mapping[str, str]]) -> str | None:
    peor = None
    for h in hallazgos:
        if peor is None or RANGO_SEVERIDAD[h["severidad"]] > RANGO_SEVERIDAD[peor]:
            peor = h["severidad"]
    return peor


def _veredicto_de(peor: str | None) -> str:
    if peor == "BLOQUEANTE":
        return "FAIL"
    if peor in ("MAYOR", "MENOR"):
        return "PASS_CON_NOTAS"
    return "PASS"


# ----------------------------------------------------------------------------------------------
# Reglas
# ----------------------------------------------------------------------------------------------
def lint_marcas_pendientes(ruta: Path, texto: str) -> list[dict[str, str]]:
    """L1-09 (marca pendiente, Anexo B D4): ``[VERIFICAR]``/``[SUPUESTO]``/``[TODO]``/``{{placeholder}}``/lorem ipsum."""
    hallazgos = []
    for rx, nombre in ((_RX_MARCA_PENDIENTE, "marca-pendiente"), (_RX_LOREM, "texto-de-relleno"),
                       (_RX_PLACEHOLDER_LLAVES, "placeholder-sin-completar")):
        for m in rx.finditer(texto):
            linea = texto.count("\n", 0, m.start()) + 1
            hallazgos.append(_hallazgo("L1-09", "BLOQUEANTE", f"{nombre}: «{m.group(0)[:60]}»", f"{ruta}:{linea}"))
    return hallazgos


def lint_datos_personales(ruta: Path, texto: str) -> list[dict[str, str]]:
    """L1-09 (dato personal): el producto no lleva correos ni teléfonos de personas (convenciones §10)."""
    hallazgos = []
    for m in _RX_CORREO.finditer(texto):
        linea = texto.count("\n", 0, m.start()) + 1
        hallazgos.append(_hallazgo("L1-09", "BLOQUEANTE", "correo electrónico en el entregable", f"{ruta}:{linea}"))
    for m in _RX_TELEFONO.finditer(texto):
        linea = texto.count("\n", 0, m.start()) + 1
        hallazgos.append(_hallazgo("L1-09", "MAYOR", "posible número de teléfono en el entregable (revisar)", f"{ruta}:{linea}"))
    return hallazgos


def lint_matriz_promesas(matriz: Iterable[Mapping[str, Any]], ids_items: set[str]) -> list[dict[str, str]]:
    """Cada promesa referencia un entregable real, tiene texto y prueba; ``pendiente`` es una nota, no bloquea."""
    hallazgos = []
    for p in matriz:
        pid = p.get("promesa_id", "?")
        if not str(p.get("texto") or "").strip():
            hallazgos.append(_hallazgo("D4-promesa", "BLOQUEANTE", f"promesa «{pid}» sin texto", pid))
        if not str(p.get("prueba") or "").strip():
            hallazgos.append(_hallazgo("D4-promesa", "BLOQUEANTE", f"promesa «{pid}» sin prueba de cumplimiento", pid))
        entregable = p.get("entregable_id")
        if entregable not in ids_items:
            hallazgos.append(_hallazgo("D4-promesa", "BLOQUEANTE",
                                        f"promesa «{pid}» referencia el entregable «{entregable}», que no está en items", pid))
        if p.get("estado") == "pendiente":
            hallazgos.append(_hallazgo("D4-promesa", "MAYOR", f"promesa «{pid}» sigue «pendiente»", pid))
    return hallazgos


def lint_tamanos(rutas: Iterable[Path], peso_max_mb_pdf: Any, peso_max_mb_paquete: Any) -> list[dict[str, str]]:
    """Cada archivo .pdf <= ``producto.peso_max_mb_pdf``; el total <= ``producto.peso_max_mb_paquete`` (ambos oficiales)."""
    from decimal import Decimal

    hallazgos: list[dict[str, str]] = []
    tope_pdf = Decimal(str(peso_max_mb_pdf)) * _BYTES_POR_MB
    tope_total = Decimal(str(peso_max_mb_paquete)) * _BYTES_POR_MB
    total = Decimal(0)
    for ruta in rutas:
        tam = Decimal(ruta.stat().st_size)
        total += tam
        if ruta.suffix.lower() == ".pdf" and tam > tope_pdf:
            hallazgos.append(_hallazgo("D4-peso", "BLOQUEANTE",
                                        f"{ruta.name}: {tam} B supera producto.peso_max_mb_pdf ({peso_max_mb_pdf} MB)", str(ruta)))
    if total > tope_total:
        hallazgos.append(_hallazgo("D4-peso", "BLOQUEANTE",
                                    f"paquete: {total} B supera producto.peso_max_mb_paquete ({peso_max_mb_paquete} MB)", "paquete"))
    return hallazgos


def _leer_texto(ruta: Path) -> str:
    try:
        return ruta.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ErrorValidacion(f"no se pudo leer {ruta}: {exc}") from exc


def _expandir_rutas(fuentes: Iterable[str]) -> list[Path]:
    archivos: list[Path] = []
    for f in fuentes:
        ruta = Path(f)
        if ruta.is_dir():
            archivos.extend(sorted(p for p in ruta.rglob("*") if p.is_file()))
        elif ruta.is_file():
            archivos.append(ruta)
        else:
            raise ErrorUso(f"no existe: {f}")
    return archivos


def lintear(producto: Mapping[str, Any], archivos: Iterable[Path], parametros: Any) -> dict[str, Any]:
    """Lint completo: devuelve ``{veredicto, hallazgos, script_version}``. Errores: ``ParametroFaltante`` (5)."""
    if not isinstance(producto, Mapping) or "items" not in producto or "matriz_promesas" not in producto:
        raise ErrorValidacion("producto.json inválido: faltan «items» o «matriz_promesas»")
    archivos = list(archivos)
    ids_items = {i["id"] for i in producto["items"]}
    hallazgos: list[dict[str, str]] = []
    hallazgos += lint_matriz_promesas(producto["matriz_promesas"], ids_items)
    for ruta in archivos:
        if ruta.suffix.lower() in EXTENSIONES:
            texto = _leer_texto(ruta)
            hallazgos += lint_marcas_pendientes(ruta, texto)
            hallazgos += lint_datos_personales(ruta, texto)
    peso_pdf = _valor_parametro(parametros, "peso_max_mb_pdf")
    peso_paquete = _valor_parametro(parametros, "peso_max_mb_paquete")
    hallazgos += lint_tamanos(archivos, peso_pdf, peso_paquete)
    veredicto = _veredicto_de(_peor_severidad(hallazgos))
    return {"veredicto": veredicto, "hallazgos": hallazgos, "script_version": VERSION_SCRIPT,
            "archivos_revisados": len(archivos)}


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def _cargar_json(ruta: str) -> Any:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ErrorUso(f"no existe {ruta}") from exc
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErrorValidacion(f"{ruta} ilegible: {exc}") from exc


def _principal(argv: list[str] | None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.producto.lint", description="Lint de contenido de D4")
    ap.add_argument("producto")
    ap.add_argument("--fuente", nargs="+", required=True)
    ap.add_argument("--parametros")
    try:
        a = ap.parse_args(argv)
    except SystemExit as exc:
        if exc.code in (0, None):
            return 0
        raise ErrorUso("argumentos inválidos (ver --help)") from None
    producto = _cargar_json(a.producto)
    archivos = _expandir_rutas(a.fuente)
    parametros = cargar_parametros(a.parametros) if a.parametros else cargar_parametros()
    resultado = lintear(producto, archivos, parametros)
    print(json.dumps(resultado, ensure_ascii=False, indent=2, sort_keys=True))
    return ErrorValidacion.codigo_salida if resultado["veredicto"] == "FAIL" else 0


def main(argv: list[str] | None = None) -> int:
    return comun.ejecutar_cli(lambda: _principal(argv))


if __name__ == "__main__":
    raise SystemExit(main())
