"""``landing.diseno``: de ``paleta.json`` a las variables CSS de la landing, con contraste AA verificado.

La plantilla (``sitio-base/estilos.css``) no contiene ni un color: usa variables que genera este
módulo a partir de ``paleta.json``. Cuatro **tonos** de sección (``claro``, ``suave``, ``oscuro``,
``profundo``) llevan cada uno su juego de variables (fondo, texto, texto suave, superficie, borde,
acento, foco). Los colores que la paleta no declara (``texto_suave_*``, ``superficie_oscura``,
``acento_sobre_claro``, ``cta_hover``…) se **derivan** de forma determinista; los declarados nunca
se tocan: si no cumplen, se falla cerrado (``ErrorValidacion``, código 3).

Además de los tonos, deriva (sin campos nuevos en ``paleta.json``) el **color de resalte** del marcatextos y de la barra superior (el del
botón: ``cta_fondo`` con ``cta_texto``, par ya verificado) y **seis colores de ícono** por tono (acento, botón, éxito, foco y dos matices
derivados por rotación de tono), cada uno con su círculo teñido y el trazo acercado al texto hasta 3:1 (WCAG 1.4.11).

Contraste (WCAG 2.x): 4.5:1 para texto y botones, 3:1 para el anillo de foco, los íconos y para el botón
frente al fondo. Se comprueban TODOS los pares que el CSS usa, no solo los de ``pares_contraste``
(esos y la no reutilización de la base los revisa además ``scripts/contraste_paleta.py`` de la skill,
si existe). Sin red ni fuentes remotas: la tipografía es la pila de sistema más, opcionalmente,
fuentes autoalojadas declaradas en ``paleta.tipografia`` y presentes en disco.
"""
from __future__ import annotations

import importlib.util
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping

from engine.errores import ErrorValidacion

__all__ = ["Tono", "Diseno", "luminancia", "razon_contraste", "construir_diseno", "revisar_con_skill"]

RAIZ_CODIGO = Path(__file__).resolve().parents[1]
DIR_SKILL = RAIZ_CODIGO / ".claude" / "skills" / "d5-landing-checkout"
RX_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
RX_FAMILIA = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 \-]{0,59}$")
RX_ARCHIVO_FUENTE = re.compile(r"^fonts/[a-z0-9-]+\.woff2$")

PILA_SANS = 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif'
PILA_SERIF = '"Iowan Old Style", "Palatino Linotype", Palatino, Georgia, Cambria, "Times New Roman", serif'
_SERIF_CONOCIDAS = frozenset({
    "source serif 4", "source serif pro", "playfair display", "lora", "merriweather", "cormorant garamond", "libre baskerville",
    "crimson text", "crimson pro", "pt serif", "noto serif", "eb garamond", "dm serif display", "fraunces", "georgia", "literata",
    "newsreader", "spectral", "bitter", "roboto serif", "gelasio",
})

MIN_TEXTO = 4.5
MIN_UI = 3.0
NEGRO, BLANCO = "#000000", "#FFFFFF"


# ----------------------------------------------------------------------------------------------
# Color
# ----------------------------------------------------------------------------------------------
def _rgb(hexa: str) -> tuple[int, int, int]:
    return int(hexa[1:3], 16), int(hexa[3:5], 16), int(hexa[5:7], 16)


def _hex(r: int, g: int, b: int) -> str:
    return f"#{r:02X}{g:02X}{b:02X}"


def luminancia(hexa: str) -> float:
    """Luminancia relativa WCAG 2.x de ``#RRGGBB``."""
    def canal(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (canal(c) for c in _rgb(hexa))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def razon_contraste(a: str, b: str) -> float:
    """Razón de contraste WCAG 2.x entre dos ``#RRGGBB`` (1 a 21)."""
    la, lb = luminancia(a), luminancia(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def mezclar(a: str, b: str, pct_b: int) -> str:
    """Mezcla entera y determinista: ``pct_b`` % de ``b`` y el resto de ``a`` (redondeo al más cercano)."""
    ra, rb = _rgb(a), _rgb(b)
    return _hex(*((x * (100 - pct_b) + y * pct_b + 50) // 100 for x, y in zip(ra, rb)))


def _acercar(color: str, ancla: str, fondos: list[str], minimo: float) -> str | None:
    """Primer paso (de 2 en 2 %) de ``color`` hacia ``ancla`` que cumple ``minimo`` contra todos los ``fondos``."""
    for pct in range(0, 101, 2):
        candidato = mezclar(color, ancla, pct)
        if all(razon_contraste(candidato, f) >= minimo for f in fondos):
            return candidato
    return None


def _a_hsl(hexa: str) -> tuple[float, float, float]:
    r, g, b = (c / 255 for c in _rgb(hexa))
    mx, mn = max(r, g, b), min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        return 0.0, 0.0, l
    d = mx - mn
    s = d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)
    if mx == r:
        h = (g - b) / d + (6 if g < b else 0)
    elif mx == g:
        h = (b - r) / d + 2
    else:
        h = (r - g) / d + 4
    return h * 60, s, l


def _de_hsl(h: float, s: float, l: float) -> str:
    h = (h % 360) / 360

    def f(p: float, q: float, t: float) -> float:
        t %= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    if s == 0:
        r = g = b = l
    else:
        q = l * (1 + s) if l < 0.5 else l + s - l * s
        p = 2 * l - q
        r, g, b = f(p, q, h + 1 / 3), f(p, q, h), f(p, q, h - 1 / 3)
    return _hex(round(r * 255), round(g * 255), round(b * 255))


def rotar_tono(hexa: str, grados: int) -> str:
    """Mismo brillo y saturación, tono girado ``grados`` (determinista; entero)."""
    h, s, l = _a_hsl(hexa)
    return _de_hsl(h + grados, s, l)


def _rgba(hexa: str, alfa_pct: int) -> str:
    r, g, b = _rgb(hexa)
    return f"rgba({r},{g},{b},{alfa_pct / 100:.2f})"


# ----------------------------------------------------------------------------------------------
# Tonos
# ----------------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Tono:
    """Juego de colores de un tipo de sección (todos ``#RRGGBB``)."""

    nombre: str
    fondo: str
    texto: str
    suave: str
    superficie: str
    borde: str
    acento: str
    acento_deco: str
    chip: str
    foco: str
    iconos: tuple[tuple[str, str], ...] = ()      # (trazo, círculo) de los seis colores de ícono

    def pares(self) -> list[tuple[str, str, str, float]]:
        """Pares (etiqueta, primer plano, fondo, mínimo) que el CSS usa en este tono."""
        n = self.nombre
        return [
            (f"{n}: texto/fondo", self.texto, self.fondo, MIN_TEXTO),
            (f"{n}: texto suave/fondo", self.suave, self.fondo, MIN_TEXTO),
            (f"{n}: texto/superficie", self.texto, self.superficie, MIN_TEXTO),
            (f"{n}: texto suave/superficie", self.suave, self.superficie, MIN_TEXTO),
            (f"{n}: acento/fondo", self.acento, self.fondo, MIN_TEXTO),
            (f"{n}: acento/superficie", self.acento, self.superficie, MIN_TEXTO),
            (f"{n}: texto/etiqueta", self.texto, self.chip, MIN_TEXTO),
            (f"{n}: acento/etiqueta", self.acento, self.chip, MIN_TEXTO),
            (f"{n}: foco/fondo", self.foco, self.fondo, MIN_UI),
            (f"{n}: foco/superficie", self.foco, self.superficie, MIN_UI),
            *((f"{n}: ícono {i + 1}/círculo", fg, bg, MIN_UI) for i, (fg, bg) in enumerate(self.iconos)),
        ]

    def variables(self) -> str:
        iconos = "".join(f"--ic{i + 1}:{fg};--ic{i + 1}-bg:{bg};" for i, (fg, bg) in enumerate(self.iconos))
        return (
            f"--fondo:{self.fondo};--texto:{self.texto};--suave:{self.suave};--superficie:{self.superficie};"
            f"--borde:{self.borde};--acento:{self.acento};--acento-deco:{self.acento_deco};--chip:{self.chip};--foco:{self.foco};"
            f"{iconos}--sombra:0 1px 2px {_rgba(self.texto, 8)},0 10px 30px -12px {_rgba(self.texto, 22)}"
        )


@dataclass
class Diseno:
    """Resultado de :func:`construir_diseno`: CSS de variables y de fuentes, más lo que hay que copiar a ``sitio/``."""

    css_tokens: str
    css_fuentes: str
    tonos: dict[str, Tono]
    alternos: dict[str, str]
    fuentes: list[str] = field(default_factory=list)
    precargas: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)
    color_tema: str = "#000000"


def _hexes(paleta: Mapping[str, Any]) -> dict[str, str]:
    colores = paleta.get("colores") or {}
    salida: dict[str, str] = {}
    for nombre, c in colores.items():
        hexa = c.get("hex") if isinstance(c, dict) else None
        if not isinstance(hexa, str) or not RX_HEX.match(hexa):
            raise ErrorValidacion(f"paleta.json: colores.{nombre}.hex inválido ({hexa!r}); se espera #RRGGBB")
        salida[nombre] = hexa.upper()
    return salida


def _tonos_base(c: Mapping[str, str]) -> tuple[dict[str, Tono], list[str]]:
    """Cuatro tonos y la lista de fallos de los **tonos base** (``claro`` y ``oscuro``) y de los alternos."""
    avisos: list[str] = []
    claro_bg, texto_c, sup = c["fondo_claro"], c["texto_sobre_claro"], c["superficie"]
    acento_base = c.get("acento_sobre_claro") or c["acento"]
    foco_c = c["foco"]

    def claros(pct_suave: int) -> tuple[str, str, str, str, str]:
        suave_bg = mezclar(claro_bg, texto_c, pct_suave)
        fondos = [claro_bg, sup, suave_bg]
        suave = c.get("texto_suave_sobre_claro") or _acercar(mezclar(texto_c, claro_bg, 32), texto_c, fondos, MIN_TEXTO) or texto_c
        chip = mezclar(claro_bg, acento_base, 9)
        acento = c.get("acento_sobre_claro") or _acercar(c["acento"], texto_c, [*fondos, chip, mezclar(suave_bg, acento_base, 9)], MIN_TEXTO) or texto_c
        return suave_bg, suave, chip, acento, mezclar(suave_bg, acento_base, 9)

    # El fondo del tono «suave» es lo más marcado posible (5 %, 4 %, 3 %) mientras la paleta declarada cumpla AA sobre él.
    for pct in (5, 4, 3):
        suave_bg, suave_c, chip_c, acento_c, chip_s = claros(pct)
        probe = Tono("suave", suave_bg, texto_c, suave_c, sup, c["linea"], acento_c, c["acento"], chip_s, foco_c)
        if all(razon_contraste(fg, bg) + 1e-9 >= minimo for _, fg, bg, minimo in probe.pares()):
            break

    osc_bg, texto_o = c["fondo_oscuro"], c["texto_sobre_oscuro"]
    sup_o = c.get("superficie_oscura") or mezclar(osc_bg, texto_o, 8)
    prof_bg = mezclar(osc_bg, NEGRO, 38)
    sup_p = c.get("superficie_oscura") or mezclar(prof_bg, texto_o, 8)
    fondos_osc = [osc_bg, sup_o, prof_bg, sup_p]
    suave_o = c.get("texto_suave_sobre_oscuro") or _acercar(mezclar(texto_o, osc_bg, 35), texto_o, fondos_osc, MIN_TEXTO) or texto_o
    chip_o = mezclar(osc_bg, c["acento"], 16)
    chip_p = mezclar(prof_bg, c["acento"], 16)
    acento_o = c["acento"]
    if not all(razon_contraste(acento_o, f) >= MIN_TEXTO for f in [*fondos_osc, chip_o, chip_p]):
        derivado = _acercar(acento_o, texto_o, [*fondos_osc, chip_o, chip_p], MIN_TEXTO)
        if derivado is not None:
            avisos.append(f"paleta: acento {acento_o} aclarado a {derivado} para el texto sobre tonos oscuros (AA)")
            acento_o = derivado

    base_iconos = colores_de_icono(c)
    tonos = {
        "claro": Tono("claro", claro_bg, texto_c, suave_c, sup, c["linea"], acento_c, c["acento"], chip_c, foco_c, _iconos(base_iconos, sup, texto_c)),
        "suave": Tono("suave", suave_bg, texto_c, suave_c, sup, c["linea"], acento_c, c["acento"], chip_s, foco_c, _iconos(base_iconos, sup, texto_c)),
        "oscuro": Tono("oscuro", osc_bg, texto_o, suave_o, sup_o, mezclar(osc_bg, texto_o, 16), acento_o, c["acento"], chip_o, acento_o,
                       _iconos(base_iconos, sup_o, texto_o)),
        "profundo": Tono("profundo", prof_bg, texto_o, suave_o, sup_p, mezclar(prof_bg, texto_o, 16), acento_o, c["acento"], chip_p, acento_o,
                         _iconos(base_iconos, sup_p, texto_o)),
    }
    return tonos, avisos


def colores_de_icono(c: Mapping[str, str]) -> list[str]:
    """Seis colores de ícono derivados de la paleta (sin campos nuevos): acento, botón, éxito (o el acento girado 120°), foco y dos matices girados
    (botón −28°, foco +65°). Mismo brillo y saturación que su origen; determinista."""
    exito = c.get("exito") or rotar_tono(c["acento"], 120)
    return [c["acento"], c["cta_fondo"], exito, c["foco"], rotar_tono(c["cta_fondo"], -28), rotar_tono(c["foco"], 65)]


def _iconos(colores: list[str], superficie: str, texto: str) -> tuple[tuple[str, str], ...]:
    """(trazo, círculo) de cada color: círculo = 15 % del color sobre la superficie; trazo = el color acercado al texto hasta 3:1 contra el círculo y la superficie."""
    salida = []
    for col in colores:
        circulo = mezclar(superficie, col, 15)
        trazo = _acercar(col, texto, [circulo, superficie], MIN_UI) or texto
        salida.append((trazo, circulo))
    return tuple(salida)


def _cta(c: Mapping[str, str]) -> tuple[str, str, str]:
    fondo, texto = c["cta_fondo"], c["cta_texto"]
    hover = c.get("cta_hover")
    if not hover:
        for destino in (NEGRO, BLANCO):
            candidato = mezclar(fondo, destino, 12)
            if razon_contraste(texto, candidato) >= MIN_TEXTO:
                hover = candidato
                break
        hover = hover or fondo
    return fondo, texto, hover


def _verificar(tonos: dict[str, Tono], cta: tuple[str, str, str]) -> tuple[list[str], dict[str, str]]:
    """Fallos (mensajes) de los pares usados y mapa de tonos alternos disponibles (``suave``/``profundo`` o su base)."""
    fallos: list[str] = []
    alternos = {"claro": "suave", "suave": "claro", "oscuro": "profundo", "profundo": "oscuro"}

    def revisar(etiqueta: str, fg: str, bg: str, minimo: float) -> bool:
        r = razon_contraste(fg, bg)
        if r + 1e-9 < minimo:
            fallos.append(f"{etiqueta}: {fg} sobre {bg} = {r:.2f}:1 < {minimo:g}:1")
            return False
        return True

    for base in ("claro", "oscuro"):
        for etiqueta, fg, bg, minimo in tonos[base].pares():
            revisar(etiqueta, fg, bg, minimo)
    # Los alternos son opcionales: si la paleta declarada no aguanta su fondo derivado, no se usan (se queda el tono base).
    for alt, base in (("suave", "claro"), ("profundo", "oscuro")):
        if not all(razon_contraste(fg, bg) + 1e-9 >= minimo for _, fg, bg, minimo in tonos[alt].pares()):
            alternos[base] = base
            alternos[alt] = base
    fondo, texto, hover = cta
    revisar("botón: texto/fondo", texto, fondo, MIN_TEXTO)
    revisar("botón: texto/hover", texto, hover, MIN_TEXTO)
    revisar("botón/sección oscura", fondo, tonos["oscuro"].fondo, MIN_UI)
    if alternos["oscuro"] == "profundo":
        revisar("botón/sección profunda", fondo, tonos["profundo"].fondo, MIN_UI)
    return fallos, alternos


# ----------------------------------------------------------------------------------------------
# Tipografía
# ----------------------------------------------------------------------------------------------
def _pila(familia: str) -> str:
    if not RX_FAMILIA.match(familia):
        raise ErrorValidacion(f"paleta.json: nombre de familia tipográfica no admitido ({familia!r})")
    base = PILA_SERIF if familia.lower() in _SERIF_CONOCIDAS else PILA_SANS
    return f'"{familia}", {base}'


def _fuentes(tipografia: Mapping[str, Any], existe: Callable[[str], bool]) -> tuple[str, list[str], list[str], str, str, list[str]]:
    """(``@font-face``, archivos usados, precargas, pila de títulos, pila de texto, avisos)."""
    avisos: list[str] = []
    pila_titulos = _pila(tipografia["titulos"]["familia"])
    pila_texto = _pila(tipografia["texto"]["familia"])
    display = (tipografia.get("carga") or {}).get("font_display", "swap")
    reglas: list[str] = []
    usadas: list[str] = []
    for rol in ("titulos", "texto"):
        bloque = tipografia[rol]
        pesos = bloque.get("pesos") or []
        for i, archivo in enumerate(bloque.get("archivos") or []):
            if not RX_ARCHIVO_FUENTE.match(archivo):
                raise ErrorValidacion(f"paleta.json: archivo de fuente no admitido ({archivo!r})")
            if not existe(archivo):
                avisos.append(f"fuente {bloque['familia']}: no está {archivo}; se usa la pila de sistema")
                continue
            peso = pesos[i] if i < len(pesos) else 400
            reglas.append(
                f'@font-face{{font-family:"{bloque["familia"]}";src:url("/{archivo}") format("woff2");font-weight:{int(peso)};'
                f"font-style:normal;font-display:{display}}}"
            )
            usadas.append(archivo)
    precargas = [a for a in ((tipografia.get("carga") or {}).get("precarga") or []) if a in usadas]
    return "\n".join(reglas), usadas, precargas, pila_titulos, pila_texto, avisos


# ----------------------------------------------------------------------------------------------
# Punto de entrada
# ----------------------------------------------------------------------------------------------
def construir_diseno(paleta: Mapping[str, Any], *, existe_fuente: Callable[[str], bool] = lambda _a: False) -> Diseno:
    """Variables CSS de ``paleta.json``; ``ErrorValidacion`` si algún par usado no cumple AA."""
    colores = _hexes(paleta)
    faltan = [t for t in ("fondo_claro", "fondo_oscuro", "superficie", "texto_sobre_claro", "texto_sobre_oscuro", "acento", "cta_fondo", "cta_texto", "linea", "foco") if t not in colores]
    if faltan:
        raise ErrorValidacion(f"paleta.json: faltan los colores obligatorios {faltan}")
    tonos, avisos = _tonos_base(colores)
    cta = _cta(colores)
    fallos, alternos = _verificar(tonos, cta)
    if fallos:
        raise ErrorValidacion("paleta.json: contraste insuficiente (AA) en " + "; ".join(fallos), detalle={"fallos": fallos})
    css_fuentes, usadas, precargas, pila_t, pila_x, av_f = _fuentes(paleta["tipografia"], existe_fuente)
    avisos += av_f
    cuerpo = [
        ":root{"
        f"--cta-fondo:{cta[0]};--cta-texto:{cta[1]};--cta-hover:{cta[2]};"
        f"--marca-fondo:{cta[0]};--marca-texto:{cta[1]};--barra-fondo:{cta[0]};--barra-texto:{cta[1]};"
        f"--cta-brillo:{_rgba(cta[0], 45)};--halo:{_rgba(colores['acento'], 22)};--halo-2:{_rgba(colores['acento'], 12)};"
        f"--halo-marca:{_rgba(cta[0], 18)};"
        f"--halo-fuerte:{_rgba(colores['acento'], 38)};"
        f"--papel:{tonos['claro'].fondo};--tinta:{tonos['claro'].texto};--tinta-suave:{tonos['claro'].suave};"
        f"--tinta-acento:{tonos['claro'].acento};--f-titulos:{pila_t};--f-texto:{pila_x}}}",
    ]
    for nombre in ("claro", "suave", "oscuro", "profundo"):
        cuerpo.append(f".tono-{nombre}{{{tonos[nombre].variables()}}}")
    return Diseno(css_tokens="\n".join(cuerpo), css_fuentes=css_fuentes, tonos=tonos, alternos=alternos,
                  fuentes=usadas, precargas=precargas, avisos=avisos, color_tema=tonos["oscuro"].fondo)


def revisar_con_skill(paleta: Mapping[str, Any]) -> list[str]:
    """Mensajes MAYOR/BLOQUEANTE de ``scripts/contraste_paleta.py`` de la skill (vacío si pasa o si el script no existe)."""
    ruta = DIR_SKILL / "scripts" / "contraste_paleta.py"
    if not ruta.is_file():
        return []
    espec = importlib.util.spec_from_file_location("_d5_contraste_paleta", ruta)
    if espec is None or espec.loader is None:  # pragma: no cover - instalación rota
        return []
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)
    return [f"{h['regla']}: {h['detalle']}" for h in modulo.revisar(dict(paleta)) if h["severidad"] in ("BLOQUEANTE", "MAYOR")]
