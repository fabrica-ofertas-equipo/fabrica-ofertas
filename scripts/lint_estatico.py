"""Búsqueda estática de cuatro invariantes que las pruebas por sí solas no cubren (MA-12,
docs/06 §3 invariante 3, §8 «Listo (común)», B0-18).

Reglas
------
(a) ``float`` o división (``/``) aplicados a un nombre que *parece* un importe, dentro de
    ``engine decision datos meta postcompra landing``. Convenciones §3 prohíbe ``float`` para
    dinero; D-05 solo exceptúa, dentro de ``decision/``, el uso de tasas en memoria (CPC,
    probabilidades) que nunca se persiste sin pasar por ``decision.entradas.serializar`` — esa
    excepción se declara línea por línea con el marcador de abajo, no por archivo completo.
(b) Literales numéricos de dos o más dígitos dentro de funciones cuyo nombre contiene «limite»
    o «umbral», fuera de ``tests/`` y ``contratos/``: todo tope viene de ``limites.yaml`` o
    ``parametros.yaml`` (convenciones §3), nunca de un número fijo en el código.
(c) Patrones de correo, IP y número de tarjeta (validado con Luhn) en ``ofertas/``,
    ``empresa/``, ``tests/fixtures/`` y cualquier ``logs/`` o archivo ``.log`` (convenciones
    §10, B0-18): nada de eso debería aparecer en artefactos ni fixtures.
(d) Prefijos de credencial (``EAA``, ``sk_``, ``rk_live_``, ``whsec_``, ``cfut_``) en todo el
    árbol: segunda defensa mientras no hay ``gitleaks`` instalado (docs/07 §8.4).

Falsos positivos justificados
------------------------------
Tres mecanismos, todos explícitos y comentados (nunca una excepción silenciosa):

1. Marcador en la MISMA línea del hallazgo: ``# lint-estatico: permitir=<regla>[,<regla>...]``
   (comentario de una línea citando la razón, por ejemplo ``# lint-estatico: permitir=a  # D-05:
   tasa en memoria, no se persiste``).
2. :data:`LISTA_BLANCA`, un diccionario por regla con rutas relativas completas que quedan
   exceptuadas por entero; cada entrada debe llevar su propio comentario de razón junto a ella.
   Deliberadamente vacío: una excepción de archivo completo es la salida de último recurso.
3. :data:`LISTA_BLANCA_SIMBOLOS`, un diccionario regla → ruta relativa → nombres: exceptúa SOLO
   los símbolos listados de ESE archivo (lo que pide D-05 para ``decision/``: las tasas que quedan
   en ``float`` por diseño, como CPC/CPM, sin abrir el archivo entero a la regla). Un importe de
   verdad en el mismo archivo, o el mismo nombre en otro archivo, se sigue detectando.

Esta regla NO se invoca todavía desde ``scripts/lint.sh`` (no es propiedad de esta entrega:
``lint.sh`` es de A0 y el árbol actual no pasa las cuatro reglas); se corre a mano o desde
``tests/integracion/test_lint_estatico.py``. El dueño decide cuándo engancharla.

CLI
---
::

    python -m scripts.lint_estatico                       # las cuatro reglas sobre la raíz real
    python -m scripts.lint_estatico --reglas a,d
    python -m scripts.lint_estatico --raiz RUTA --json

Salida (docs/convenciones-de-codigo.md §8): 0 limpio · 1 interno · 2 uso incorrecto ·
3 hay hallazgos. Sin red, sin efectos externos: solo lee el árbol de archivos indicado.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator, Mapping

from engine.comun import ejecutar_cli, raiz
from engine.errores import ErrorUso, ErrorValidacion

# Directorios que ninguna regla recorre (dependencias, control de versiones, cachés).
DIRS_EXCLUIDOS = {".git", ".venv", "node_modules", ".wrangler", "dist", "__pycache__", ".pytest_cache", ".ruff_cache"}

# El propio script queda fuera de su búsqueda: su código fuente declara, como literales de
# texto, los mismos patrones y prefijos que busca (no es un secreto real ni un número de
# dinero fijo, pero coincidiría igual).
_RUTA_PROPIA = Path(__file__).resolve()

# Lista blanca explícita y comentada de excepciones de ARCHIVO COMPLETO (mecanismo 2 de arriba).
# Cada clave es el identificador de regla ("a".."d"); el valor, rutas relativas a la raíz
# analizada. Vacía a propósito: toda excepción conocida hoy se resuelve con el marcador en
# línea (mecanismo 1), que es más quirúrgico y queda junto al código que lo necesita.
LISTA_BLANCA: dict[str, frozenset[str]] = {
    "a": frozenset(),
    "b": frozenset(),
    "c": frozenset(),
    "d": frozenset(),
}

# Excepciones por SÍMBOLO (mecanismo 3 de arriba): regla -> ruta relativa -> nombres que el archivo
# puede tener en ``float`` o dividir por diseño. Más fina que LISTA_BLANCA: el resto del archivo sigue
# bajo la regla. Cada entrada lleva su razón junto a ella (CT2-41; D-05, docs/06 §3 invariante 3).
LISTA_BLANCA_SIMBOLOS: dict[str, dict[str, frozenset[str]]] = {
    "a": {
        # D-05: «float solo como tasa en memoria dentro de decision/»; lo persistido sale por
        # decision.entradas.serializar (enteros / cadenas). El docstring del módulo declara estas tasas:
        # IVA/comisión/conversión/reembolso/tarifa de Meta son fracciones, y CPC/CPM/CPA son costos
        # unitarios medios («redondear a int destruiría el 10 % de precisión»), no saldos.
        "decision/presupuesto.py": frozenset({
            "comision_pct",           # suma de % de Stripe (fracción)
            "tasa_reembolso",         # fracción de pedidos reembolsados
            "tarifa_meta_pct",        # recargo de Meta sobre la entrega (fracción)
            "roas_bruto_equilibrio",  # razón AOV bruto / CPA de equilibrio
            "cpm_minor",              # CPM: tasa de costo por mil impresiones
            "cpc_minor",              # CPC: tasa de costo por clic
            "cpa",                    # CPA observado/esperado: costo unitario medio
            "cpa_esperado_minor",     # CPA esperado: costo unitario medio
        }),
    },
    "b": {},
    "c": {},
    "d": {},
}

MARCADOR_PERMITIR = re.compile(r"lint-estatico:\s*permitir=([a-d](?:,[a-d])*)")

SUBCADENAS_DINERO = (
    "monto", "importe", "precio", "presupuesto", "gasto", "spend", "pago", "reembolso",
    "comision", "ingreso", "costo", "cpa", "cpm", "cpc", "aov", "fee", "tarifa", "divisa",
    "moneda", "minor", "saldo", "balance", "neto", "bruto", "tope",
)

DIRS_REGLA_A = ("engine", "decision", "datos", "meta", "postcompra", "landing")
DIRS_EXCLUIDOS_REGLA_B = ("tests", "contratos")

PATRON_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_OCTETO = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
PATRON_IPV4 = re.compile(rf"\b{_OCTETO}\.{_OCTETO}\.{_OCTETO}\.{_OCTETO}\b")
PATRON_TARJETA_CANDIDATA = re.compile(r"(?:\d[ -]?){13,19}")

PREFIJOS_SECRETO = ("EAA", "sk_", "rk_live_", "whsec_", "cfut_")
PATRON_SECRETOS = re.compile(
    r"(?<![A-Za-z0-9_])(?:" + "|".join(re.escape(p) for p in PREFIJOS_SECRETO) + r")[A-Za-z0-9_\-]{6,}"
)


@dataclass(frozen=True)
class Hallazgo:
    """Un hallazgo de una regla: regla, ruta relativa, línea 1-based y mensaje sin secretos."""

    regla: str
    archivo: str
    linea: int
    mensaje: str

    def a_dict(self) -> dict[str, object]:
        return {"regla": self.regla, "archivo": self.archivo, "linea": self.linea, "mensaje": self.mensaje}


@dataclass(frozen=True)
class Informe:
    """Resultado de una corrida: hallazgos ordenados y el recuento por regla."""

    hallazgos: list[Hallazgo] = field(default_factory=list)
    resumen: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.hallazgos

    def a_dict(self) -> dict[str, object]:
        return {"ok": self.ok, "resumen": dict(self.resumen), "hallazgos": [h.a_dict() for h in self.hallazgos]}


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def _es_nombre_dinero(nombre: str) -> bool:
    plano = _sin_acentos(nombre).lower()
    return any(sub in plano for sub in SUBCADENAS_DINERO)


def _es_nombre_limite(nombre: str) -> bool:
    plano = _sin_acentos(nombre).lower()
    return "limite" in plano or "umbral" in plano


def _enmascarar(valor: str) -> str:
    """Oculta el valor hallado para que el propio informe no filtre un dato real (convenciones §10)."""
    if len(valor) <= 4:
        return "*" * len(valor)
    return valor[:2] + "*" * max(3, len(valor) - 4) + valor[-2:]


def _en_lista_blanca(regla: str, rel: Path) -> bool:
    return rel.as_posix() in LISTA_BLANCA.get(regla, frozenset())


def _simbolo_permitido(regla: str, rel: Path, nombre: str | None) -> bool:
    return nombre is not None and nombre in LISTA_BLANCA_SIMBOLOS.get(regla, {}).get(rel.as_posix(), frozenset())


def _tiene_permiso(lineas: list[str], linea_num: int, regla: str) -> bool:
    if linea_num < 1 or linea_num > len(lineas):
        return False
    m = MARCADOR_PERMITIR.search(lineas[linea_num - 1])
    return bool(m) and regla in m.group(1).split(",")


def _iter_archivos(base: Path) -> Iterator[Path]:
    """Recorre ``base`` sin los directorios de :data:`DIRS_EXCLUIDOS` ni el propio script."""
    for actual, dirs, archivos in os.walk(base):
        dirs[:] = [d for d in dirs if d not in DIRS_EXCLUIDOS]
        for nombre in archivos:
            ruta = Path(actual) / nombre
            if ruta.resolve() == _RUTA_PROPIA:
                continue
            yield ruta


def _leer_texto(ruta: Path) -> str | None:
    try:
        datos = ruta.read_bytes()
    except OSError:
        return None
    if b"\x00" in datos:
        return None
    try:
        return datos.decode("utf-8")
    except UnicodeDecodeError:
        return None


# ---------------------------------------------------------------------------------------------
# Regla (a): float o división sobre un importe aparente.
# ---------------------------------------------------------------------------------------------

def _nombre_de(nodo: ast.AST) -> str | None:
    if isinstance(nodo, ast.Name):
        return nodo.id
    if isinstance(nodo, ast.Attribute):
        return nodo.attr
    if isinstance(nodo, ast.Subscript):
        return _nombre_de(nodo.value)
    return None


def _buscar_float_o_division(arbol: ast.AST) -> Iterator[tuple[ast.AST, str, str]]:
    """Rinde ``(nodo, mensaje, nombre del símbolo)`` por cada float/división sobre un importe aparente."""
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name) and nodo.func.id == "float":
            for arg in nodo.args:
                nombre = _nombre_de(arg)
                if nombre and _es_nombre_dinero(nombre):
                    yield nodo, f"float() sobre el importe aparente '{nombre}'", nombre
                    break
        elif isinstance(nodo, ast.AnnAssign) and isinstance(nodo.annotation, ast.Name) and nodo.annotation.id == "float":
            nombre = _nombre_de(nodo.target)
            if nombre and _es_nombre_dinero(nombre):
                yield nodo, f"anotación float sobre el importe aparente '{nombre}'", nombre
        elif isinstance(nodo, ast.BinOp) and isinstance(nodo.op, ast.Div):
            izq, der = _nombre_de(nodo.left), _nombre_de(nodo.right)
            objetivo = izq if izq and _es_nombre_dinero(izq) else (der if der and _es_nombre_dinero(der) else None)
            if objetivo:
                yield nodo, f"división (/) sobre el importe aparente '{objetivo}' (usa Decimal/enteros con redondeo explícito)", objetivo


def regla_a_float_o_division_en_dinero(base: Path) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for ruta in _iter_archivos(base):
        if ruta.suffix != ".py":
            continue
        rel = ruta.relative_to(base)
        if not rel.parts or rel.parts[0] not in DIRS_REGLA_A:
            continue
        if _en_lista_blanca("a", rel):
            continue
        texto = _leer_texto(ruta)
        if texto is None:
            continue
        try:
            arbol = ast.parse(texto, filename=str(rel))
        except SyntaxError:
            continue
        lineas = texto.splitlines()
        for nodo, mensaje, nombre in _buscar_float_o_division(arbol):
            linea = getattr(nodo, "lineno", 0)
            if _tiene_permiso(lineas, linea, "a") or _simbolo_permitido("a", rel, nombre):
                continue
            hallazgos.append(Hallazgo("a", rel.as_posix(), linea, mensaje))
    return hallazgos


# ---------------------------------------------------------------------------------------------
# Regla (b): literal numérico fijo (≥ 2 dígitos) dentro de una función de límites/umbrales.
# ---------------------------------------------------------------------------------------------

def _funciones_de_limite(arbol: ast.AST) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    for nodo in ast.walk(arbol):
        if isinstance(nodo, (ast.FunctionDef, ast.AsyncFunctionDef)) and _es_nombre_limite(nodo.name):
            yield nodo


def _literales_fijos(func: ast.AST, texto: str) -> Iterator[tuple[ast.AST, str]]:
    for nodo in ast.walk(func):
        if not isinstance(nodo, ast.Constant):
            continue
        valor = nodo.value
        if isinstance(valor, bool) or not isinstance(valor, (int, float)):
            continue
        segmento = ast.get_source_segment(texto, nodo) or str(valor)
        if sum(c.isdigit() for c in segmento) >= 2:
            yield nodo, segmento


def regla_b_literal_fijo_en_limites(base: Path) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for ruta in _iter_archivos(base):
        if ruta.suffix != ".py":
            continue
        rel = ruta.relative_to(base)
        if rel.parts and rel.parts[0] in DIRS_EXCLUIDOS_REGLA_B:
            continue
        if _en_lista_blanca("b", rel):
            continue
        texto = _leer_texto(ruta)
        if texto is None:
            continue
        try:
            arbol = ast.parse(texto, filename=str(rel))
        except SyntaxError:
            continue
        lineas = texto.splitlines()
        for func in _funciones_de_limite(arbol):
            for nodo, segmento in _literales_fijos(func, texto):
                linea = getattr(nodo, "lineno", 0)
                if _tiene_permiso(lineas, linea, "b"):
                    continue
                hallazgos.append(Hallazgo(
                    "b", rel.as_posix(), linea,
                    f"literal numérico fijo '{segmento}' dentro de '{func.name}' "
                    f"(todo tope/umbral viene de limites.yaml o parametros.yaml)",
                ))
    return hallazgos


# ---------------------------------------------------------------------------------------------
# Regla (c): correo, IP y número de tarjeta (Luhn) en rutas de datos y fixtures.
# ---------------------------------------------------------------------------------------------

def _en_alcance_regla_c(rel: Path) -> bool:
    partes = rel.parts
    if not partes:
        return False
    if partes[0] in ("ofertas", "empresa"):
        return True
    if partes[0] == "tests" and len(partes) > 1 and partes[1] == "fixtures":
        return True
    if "logs" in partes:
        return True
    return rel.suffix == ".log"


def _luhn_valido(digitos: str) -> bool:
    total = 0
    for i, c in enumerate(reversed(digitos)):
        n = int(c)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


# Prefijos de emisor (IIN) y largos válidos de las redes de tarjetas más comunes. Un número que pasa Luhn pero no
# empieza así NO es una tarjeta (p. ej. un ID de página de Meta: el 10 % de los números largos pasa Luhn por azar).
_REDES_TARJETA = (
    (lambda d: d.startswith("4"), (13, 16, 19)),                                                # Visa
    (lambda d: 51 <= int(d[:2]) <= 55 or 2221 <= int(d[:4]) <= 2720, (16,)),                    # Mastercard
    (lambda d: d[:2] in ("34", "37"), (15,)),                                                   # American Express
    (lambda d: d.startswith("6011") or d.startswith("65") or 644 <= int(d[:3]) <= 649, (16, 17, 18, 19)),  # Discover
    (lambda d: 3528 <= int(d[:4]) <= 3589, (16, 17, 18, 19)),                                   # JCB
    (lambda d: d[:3] in ("300", "301", "302", "303", "304", "305") or d[:2] in ("36", "38", "39"), (14, 15, 16, 17, 18, 19)),  # Diners
    (lambda d: d.startswith("62"), (16, 17, 18, 19)),                                           # UnionPay
)
_CLAVE_DE_IDENTIFICADOR = re.compile(r"(?i)(?:^|[^a-z])(?:id|ids|uuid|hash|sha\w*|digest|ref|referencia|snapshot)[\"']?\s*[:=]\s*[\"']?$")


def _prefijo_de_emisor_valido(digitos: str) -> bool:
    return any(len(digitos) in largos and prueba(digitos) for prueba, largos in _REDES_TARJETA)


def _buscar_tarjeta(linea: str) -> str | None:
    for m in PATRON_TARJETA_CANDIDATA.finditer(linea):
        antes = linea[m.start() - 1] if m.start() > 0 else " "
        fin = m.start() + len(m.group(0).rstrip(" -"))   # el patrón arrastra un separador final: el borde es el último dígito
        despues = linea[fin] if fin < len(linea) else " "
        if antes.isalnum() or despues.isalnum():
            continue                                  # pegado a letras o dígitos: parte de un hash o de un token largo
        if _CLAVE_DE_IDENTIFICADOR.search(linea[:m.start()]):
            continue                                  # valor de una clave id/hash/ref: es un identificador, no una tarjeta
        digitos = re.sub(r"[ -]", "", m.group(0))
        if 13 <= len(digitos) <= 19 and _luhn_valido(digitos) and _prefijo_de_emisor_valido(digitos):
            return digitos
    return None


def regla_c_datos_personales(base: Path) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for ruta in _iter_archivos(base):
        rel = ruta.relative_to(base)
        if not _en_alcance_regla_c(rel) or _en_lista_blanca("c", rel):
            continue
        texto = _leer_texto(ruta)
        if texto is None:
            continue
        lineas = texto.splitlines()
        for i, linea_texto in enumerate(lineas, start=1):
            if _tiene_permiso(lineas, i, "c"):
                continue
            m = PATRON_EMAIL.search(linea_texto)
            if m:
                hallazgos.append(Hallazgo("c", rel.as_posix(), i, f"patrón de correo electrónico: '{_enmascarar(m.group(0))}'"))
                continue
            m = PATRON_IPV4.search(linea_texto)
            if m:
                hallazgos.append(Hallazgo("c", rel.as_posix(), i, f"patrón de dirección IP: '{_enmascarar(m.group(0))}'"))
                continue
            tarjeta = _buscar_tarjeta(linea_texto)
            if tarjeta:
                hallazgos.append(Hallazgo("c", rel.as_posix(), i, f"patrón de tarjeta con Luhn válido: '{_enmascarar(tarjeta)}'"))
    return hallazgos


# ---------------------------------------------------------------------------------------------
# Regla (d): prefijos de credencial en todo el árbol.
# ---------------------------------------------------------------------------------------------

def _prefijo_de(valor: str) -> str:
    for p in PREFIJOS_SECRETO:
        if valor.startswith(p):
            return p
    return ""


def regla_d_prefijos_de_secreto(base: Path) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    for ruta in _iter_archivos(base):
        rel = ruta.relative_to(base)
        if _en_lista_blanca("d", rel):
            continue
        texto = _leer_texto(ruta)
        if texto is None:
            continue
        lineas = texto.splitlines()
        for i, linea_texto in enumerate(lineas, start=1):
            if _tiene_permiso(lineas, i, "d"):
                continue
            m = PATRON_SECRETOS.search(linea_texto)
            if m:
                hallazgos.append(Hallazgo(
                    "d", rel.as_posix(), i,
                    f"prefijo de credencial '{_prefijo_de(m.group(0))}' con valor aparente '{_enmascarar(m.group(0))}'",
                ))
    return hallazgos


REGLAS: dict[str, Callable[[Path], list[Hallazgo]]] = {
    "a": regla_a_float_o_division_en_dinero,
    "b": regla_b_literal_fijo_en_limites,
    "c": regla_c_datos_personales,
    "d": regla_d_prefijos_de_secreto,
}


def ejecutar(base: Path, reglas: Iterable[str] | None = None) -> Informe:
    """Corre las reglas pedidas (todas por defecto) sobre ``base`` y devuelve el informe."""
    claves = list(reglas) if reglas is not None else sorted(REGLAS)
    desconocidas = sorted(set(claves) - set(REGLAS))
    if desconocidas:
        raise ErrorUso(f"regla(s) desconocida(s): {','.join(desconocidas)}")
    hallazgos: list[Hallazgo] = []
    for clave in claves:
        hallazgos.extend(REGLAS[clave](base))
    hallazgos.sort(key=lambda h: (h.regla, h.archivo, h.linea))
    resumen = {clave: sum(1 for h in hallazgos if h.regla == clave) for clave in claves}
    return Informe(hallazgos=hallazgos, resumen=resumen)


def _imprimir_informe(informe: Informe) -> None:
    for h in informe.hallazgos:
        print(f"[{h.regla}] {h.archivo}:{h.linea}: {h.mensaje}")
    resumen = ", ".join(f"{k}={v}" for k, v in sorted(informe.resumen.items()))
    print(f"TOTAL {len(informe.hallazgos)} hallazgo(s) ({resumen})")


def _parsear_argumentos(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="python -m scripts.lint_estatico",
        description="Búsqueda estática: dinero en float/división, literales fijos de límites, "
                    "datos personales y prefijos de credencial (MA-12, docs/06 §3).",
    )
    p.add_argument("--raiz", default=None, help="Raíz a analizar (por defecto, la raíz del repositorio)")
    p.add_argument("--reglas", default=None, help="Subconjunto separado por coma (a,b,c,d); por defecto las cuatro")
    p.add_argument("--json", action="store_true", help="Imprime un único objeto JSON en stdout")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    def _principal() -> int:
        ns = _parsear_argumentos(argv)
        base = Path(ns.raiz).resolve() if ns.raiz else raiz()
        if not base.is_dir():
            raise ErrorUso(f"la raíz no existe o no es un directorio: {base}")
        claves = None
        if ns.reglas:
            claves = [c.strip() for c in ns.reglas.split(",") if c.strip()]
        informe = ejecutar(base, reglas=claves)
        if ns.json:
            print(json.dumps(informe.a_dict(), sort_keys=True, ensure_ascii=False, separators=(",", ":")))
        else:
            _imprimir_informe(informe)
        if not informe.ok:
            raise ErrorValidacion(f"{len(informe.hallazgos)} hallazgo(s) de lint estático", detalle=informe.resumen)
        return 0

    return ejecutar_cli(_principal)


if __name__ == "__main__":
    sys.exit(main())
