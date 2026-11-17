"""``landing.motor``: motor de plantillas mínimo, sin lógica y escapado por defecto.

Sirve a ``landing.generar`` para rellenar las plantillas HTML de
``.claude/skills/d5-landing-checkout/templates/sitio-base/``. Reglas de seguridad (CSP,
convenciones §10): el texto del Maker es **dato**, nunca marcado.

* ``{{ruta}}``    escapa siempre (``& < > " '``).
* ``{{{ruta}}}``  inserta sin escapar **solo** si el valor es un :class:`Seguro` (HTML construido
  por este módulo o por ``landing.diseno``); cualquier otro tipo de valor se escapa igualmente,
  de modo que una cadena cruda jamás llega como marcado.
* Bloques: ``{{#si ruta}}…{{sino}}…{{/si}}``, ``{{#cada ruta}}…{{/cada}}`` (dentro: ``{{@n}}``
  contador desde 1, ``{{@i}}`` desde 0, ``{{@primero}}``, ``{{@ultimo}}``, ``{{.}}`` el elemento
  escalar) y comentarios ``{{! …}}``.
* Modo estricto: una variable inexistente es un error de plantilla (``ErrorPlantilla``, código 3).

:func:`md` convierte texto del Maker en HTML seguro: escapa todo y solo después reconoce el
mini-marcado ``**negrita**``, ``*énfasis*`` y ``==resaltado==`` (marcatextos: ``<mark class="marca">``); nunca admite HTML,
enlaces ni imágenes.
"""
from __future__ import annotations

import re
from html import escape as _escape
from typing import Any

from engine.errores import ErrorValidacion

__all__ = ["Seguro", "ErrorPlantilla", "escapar", "md", "texto_plano", "compilar", "renderizar", "renderizar_texto"]


class Seguro(str):
    """Cadena de HTML ya segura (producida por el código, nunca por el Maker)."""

    __slots__ = ()


class ErrorPlantilla(ErrorValidacion):
    """Plantilla mal formada o variable inexistente (código de salida 3)."""


def escapar(valor: Any) -> str:
    """Escapa HTML de ``valor`` (``None`` es cadena vacía); un :class:`Seguro` se conserva."""
    if isinstance(valor, Seguro):
        return str(valor)
    if valor is None:
        return ""
    return _escape(str(valor), quote=True)


_RX_NEGRITA = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*")
_RX_RESALTADO = re.compile(r"==(?=[^\s=])([^=\n]+?)(?<=[^\s=])==")
_RX_ENFASIS = re.compile(r"(?<![*\w])\*(?=[^\s*])([^*\n]+?)(?<=[^\s*])\*(?![*\w])")


def md(texto: Any) -> Seguro:
    """Texto del Maker -> HTML seguro con ``**negrita**``, ``*énfasis*`` y ``==resaltado==`` (todo lo demás, escapado).

    El resaltado se reconoce DESPUÉS de escapar (``==`` no se altera al escapar) y produce solo ``<mark class="marca">``: nunca atributos del Maker."""
    base = escapar(texto if not isinstance(texto, Seguro) else str(texto))
    base = _RX_NEGRITA.sub(r"<strong>\1</strong>", base)
    base = _RX_RESALTADO.sub(r'<mark class="marca">\1</mark>', base)
    base = _RX_ENFASIS.sub(r"<em>\1</em>", base)
    return Seguro(base)


def texto_plano(texto: Any) -> str:
    """Texto sin marcas ``*``/``**``/``==`` (para ``<title>``, ``meta`` y atributos), sin escapar."""
    t = _RX_RESALTADO.sub(r"\1", str(texto))
    t = _RX_NEGRITA.sub(r"\1", t)
    return _RX_ENFASIS.sub(r"\1", t)


# ----------------------------------------------------------------------------------------------
# Compilación
# ----------------------------------------------------------------------------------------------
_RX_ETIQUETA = re.compile(r"\{\{\{(.+?)\}\}\}|\{\{(.+?)\}\}", re.S)
# Una línea que solo contiene una etiqueta de bloque o un comentario no deja línea en blanco.
_RX_LINEA_BLOQUE = re.compile(r"^[ \t]*(\{\{(?:[#/!]|sino\b)[^{}]*\}\})[ \t]*\n", re.M)


def _tokens(fuente: str) -> list[tuple[str, str]]:
    salida: list[tuple[str, str]] = []
    pos = 0
    for m in _RX_ETIQUETA.finditer(fuente):
        if m.start() > pos:
            salida.append(("txt", fuente[pos:m.start()]))
        if m.group(1) is not None:
            salida.append(("raw", m.group(1).strip()))
        else:
            cuerpo = m.group(2).strip()
            if cuerpo.startswith("!"):
                pass
            elif cuerpo.startswith("#"):
                salida.append(("abre", cuerpo[1:].strip()))
            elif cuerpo.startswith("/"):
                salida.append(("cierra", cuerpo[1:].strip()))
            elif cuerpo == "sino":
                salida.append(("sino", ""))
            else:
                salida.append(("var", cuerpo))
        pos = m.end()
    if pos < len(fuente):
        salida.append(("txt", fuente[pos:]))
    return salida


def compilar(fuente: str, nombre: str = "plantilla") -> list[Any]:
    """Compila ``fuente`` a un árbol (lista de nodos); ``ErrorPlantilla`` si los bloques no cierran."""
    fuente = _RX_LINEA_BLOQUE.sub(r"\1", fuente)
    tokens = _tokens(fuente)
    pos = 0

    def bloque(fin: tuple[str, ...]) -> tuple[list[Any], str | None]:
        nonlocal pos
        nodos: list[Any] = []
        while pos < len(tokens):
            tipo, valor = tokens[pos]
            pos += 1
            if tipo == "txt":
                nodos.append(("txt", valor))
            elif tipo in ("var", "raw"):
                nodos.append((tipo, valor))
            elif tipo == "abre":
                partes = valor.split(None, 1)
                if len(partes) != 2 or partes[0] not in ("si", "cada"):
                    raise ErrorPlantilla(f"{nombre}: bloque desconocido «{valor}»")
                dentro, cierre = bloque(("cierra", "sino"))
                otro: list[Any] = []
                if cierre == "sino":
                    if partes[0] != "si":
                        raise ErrorPlantilla(f"{nombre}: «sino» solo en bloques «si»")
                    otro, cierre = bloque(("cierra",))
                if cierre != "cierra":
                    raise ErrorPlantilla(f"{nombre}: falta cerrar el bloque «{valor}»")
                nodos.append((partes[0], partes[1].strip(), dentro, otro))
            elif tipo in fin:
                return nodos, tipo
            else:
                raise ErrorPlantilla(f"{nombre}: «{tipo}» inesperado")
        return nodos, None

    arbol, resto = bloque(())
    if resto is not None:
        raise ErrorPlantilla(f"{nombre}: etiqueta de cierre sin apertura")
    return arbol


# ----------------------------------------------------------------------------------------------
# Renderizado
# ----------------------------------------------------------------------------------------------
_FALTA = object()


def _buscar(pila: list[Any], ruta: str, nombre: str) -> Any:
    if ruta == ".":
        return pila[-1].get(".", pila[-1]) if isinstance(pila[-1], dict) else pila[-1]
    partes = ruta.split(".")
    for marco in reversed(pila):
        actual: Any = marco
        for i, p in enumerate(partes):
            if isinstance(actual, dict) and p in actual:
                actual = actual[p]
            elif isinstance(actual, (list, tuple)) and p.isdigit() and int(p) < len(actual):
                actual = actual[int(p)]
            else:
                actual = _FALTA
                break
        if actual is not _FALTA:
            return actual
    raise ErrorPlantilla(f"{nombre}: variable «{ruta}» inexistente")


def _verdadero(valor: Any) -> bool:
    return bool(valor)


def _render(nodos: list[Any], pila: list[Any], nombre: str, salida: list[str]) -> None:
    for nodo in nodos:
        tipo = nodo[0]
        if tipo == "txt":
            salida.append(nodo[1])
        elif tipo == "var":
            salida.append(_escapar_var(_buscar(pila, nodo[1], nombre)))
        elif tipo == "raw":
            v = _buscar(pila, nodo[1], nombre)
            salida.append(str(v) if isinstance(v, Seguro) else escapar(v))
        elif tipo == "si":
            try:
                v = _buscar(pila, nodo[1], nombre)
            except ErrorPlantilla:
                v = None
            _render(nodo[2] if _verdadero(v) else nodo[3], pila, nombre, salida)
        elif tipo == "cada":
            lista = _buscar(pila, nodo[1], nombre)
            if lista is None:
                lista = []
            if not isinstance(lista, (list, tuple)):
                raise ErrorPlantilla(f"{nombre}: «{nodo[1]}» no es una lista")
            for i, item in enumerate(lista):
                marco: dict[str, Any] = dict(item) if isinstance(item, dict) else {}
                marco.update({"@i": i, "@n": i + 1, "@primero": i == 0, "@ultimo": i == len(lista) - 1, ".": item})
                _render(nodo[2], pila + [marco], nombre, salida)


def _escapar_var(valor: Any) -> str:
    """``{{x}}`` escapa siempre, incluso un :class:`Seguro` (para atributos)."""
    if valor is None:
        return ""
    return _escape(str(valor), quote=True)


def renderizar(arbol: list[Any], contexto: dict[str, Any], nombre: str = "plantilla") -> Seguro:
    """Renderiza un árbol compilado con ``contexto``; el resultado es HTML (:class:`Seguro`)."""
    salida: list[str] = []
    _render(arbol, [contexto], nombre, salida)
    return Seguro("".join(salida))


def renderizar_texto(fuente: str, contexto: dict[str, Any], nombre: str = "plantilla") -> Seguro:
    """Compila y renderiza de una vez (atajo para plantillas pequeñas)."""
    return renderizar(compilar(fuente, nombre), contexto, nombre)
