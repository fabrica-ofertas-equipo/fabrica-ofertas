"""Lints de HTML de X1 (docs/06 §4.5, B0-11): casillas premarcadas, píxel antes del consentimiento,
enlaces legales y temporizadores sin fecha límite verificable; además, términos sensibles en
``<title>``/``og:*`` (D01, :mod:`compliance.reglas`).

**Alcance de esta entrega** (B6, ola 1): cubre 4 de las 8 mutaciones de B0-11 — ``legal ausente``,
``enlace roto``, ``píxel en <head> sin condición`` y ``casilla premarcada`` — más ``og:*``/``title``
(D01). Precio, moneda y garantía distintos entre ``oferta``/``checkout``/HTML, y datos de salud en
``tracking.json``, son del L1 de ``landing.generar/validar`` (B4): no se duplica aquí su esquema
(ver «Decisiones» y «Pedidos» en ``compliance/README.md``). Nunca hace una petición de red: no
comprueba que un enlace responda 200 (eso es B4/B0-11 con el sitio servido de verdad).
"""
from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Mapping

from engine import comun
from engine.errores import ErrorUso, ErrorValidacion

from compliance.hallazgos import Hallazgo, peor_nivel
from compliance.reglas import Reglas, cargar_reglas, categorias_de_locale

__all__ = ["LEGALES_REQUERIDAS", "main", "verificar_html", "verificar_metadatos"]

# Las siete páginas legales (docs/07 §"Legal"): clave corta -> fragmento de ruta que debe aparecer
# en algún href. No se exige que sea exactamente esta ruta (un dominio puede montarlas distinto),
# solo que el fragmento canónico esté presente (B0-11: "legal ausente (1 de 7)").
LEGALES_REQUERIDAS: Mapping[str, str] = {
    "vendedor": "/legal/vendedor",
    "terminos": "/legal/terminos",
    "privacidad": "/legal/privacidad",
    "reembolsos": "/legal/reembolsos",
    "cookies": "/legal/cookies",
    "aviso": "/legal/aviso",
    "entrega": "/legal/entrega",
}
_HREFS_ROTOS = {"", "#", "javascript:void(0)", "javascript:void(0);"}
_MARCADORES_PIXEL = ("fbq(", "connect.facebook.net", "pixel.js", "fbevents.js")
_MARCADORES_CONSENTIMIENTO = ("consentimiento.js", "consentimiento", "cookieconsent", "data-consent")
_MARCADORES_COUNTDOWN = ("countdown", "cuenta-atras", "cuenta_regresiva", "cuenta atrás")
_RX_DEADLINE = re.compile(r'data-deadline=["\']([^"\']+)["\']', re.IGNORECASE)
_RX_INSTANTE_Z = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
# Escasez/urgencia fija (L1-PUB a): "quedan N cupos/plazas/lugares/unidades" en texto estático, sin
# un marcador que diga que ese número lo calcula el servidor (no hay petición de red aquí: es una
# heurística sobre el HTML, igual que el resto de este módulo).
_RX_ESCASEZ_FIJA = re.compile(
    r"\b([uú]ltim[oa]s?|solo\s+quedan?|quedan(\s+solo)?)\s+\d+\s*(cupos?|plazas?|lugares?|unidades?)\b",
    re.IGNORECASE,
)
_MARCADORES_CUPO_VERIFICABLE = ("data-cupos-verificable", "data-stock-verificable")
# Texto de plantilla olvidado (L1-PUB a): "EJEMPLO"/"TODO" en mayúsculas estrictas (si no, "ejemplo"
# y "todo" son palabras comunes del español) o "[NOMBRE]"/"Lorem" (poco probable en copy real).
_MARCADORES_PLANTILLA: tuple[re.Pattern[str], ...] = (
    re.compile(r"\[EJEMPLO\]"),
    re.compile(r"\bEJEMPLO\b"),
    re.compile(r"\bLorem\b", re.IGNORECASE),
    re.compile(r"\[NOMBRE\]"),
    re.compile(r"\bTODO\b"),
)


@dataclass
class _Etiqueta:
    """Una etiqueta vista por el parser con su posición de inicio en el HTML original."""

    nombre: str
    atributos: dict[str, str | None]
    inicio: int


class _RecolectorHTML(HTMLParser):
    """Recoge ``<a>``, ``<script>``, ``<input>``, ``<meta>``, ``<title>`` con su posición, sin ejecutar nada."""

    def __init__(self, html: str) -> None:
        super().__init__(convert_charrefs=True)
        self._html = html
        self.etiquetas: list[_Etiqueta] = []
        self.titulo: str | None = None
        self._en_title = False
        self._title_buffer: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        inicio = self.getpos()
        offset = self._html.find("<" + tag, self._indice_lineal(inicio))
        self.etiquetas.append(_Etiqueta(tag.lower(), dict(attrs), offset if offset >= 0 else 0))
        if tag.lower() == "title":
            self._en_title = True

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._en_title = False
            self.titulo = "".join(self._title_buffer).strip()

    def handle_data(self, data: str) -> None:
        if self._en_title:
            self._title_buffer.append(data)

    def _indice_lineal(self, pos: tuple[int, int]) -> int:
        linea, columna = pos
        indice = 0
        for _ in range(linea - 1):
            indice = self._html.find("\n", indice) + 1
        return indice + columna


def _parsear(html: str) -> _RecolectorHTML:
    parser = _RecolectorHTML(html)
    parser.feed(html)
    parser.close()
    return parser


def _casillas_premarcadas(parser: _RecolectorHTML) -> list[Hallazgo]:
    hallazgos = []
    for et in parser.etiquetas:
        if et.nombre != "input":
            continue
        tipo = (et.atributos.get("type") or "").lower()
        if tipo == "checkbox" and "checked" in et.atributos:
            nombre = et.atributos.get("name") or et.atributos.get("id") or "(sin nombre)"
            hallazgos.append(Hallazgo(
                patron_clave="html:casilla-premarcada", nivel="rojo", categoria="html",
                descripcion=f"casilla de consentimiento premarcada ({nombre}): debe nacer sin marcar",
                evidencia=f"<input type=\"checkbox\" checked ...> ({nombre})",
            ))
    return hallazgos


def _enlaces_legales(parser: _RecolectorHTML) -> list[Hallazgo]:
    anclas = [et for et in parser.etiquetas if et.nombre == "a"]
    hallazgos: list[Hallazgo] = []
    for clave, fragmento in LEGALES_REQUERIDAS.items():
        # ``data-legal="<clave>"`` identifica el enlace aunque su href esté roto (si no, un href
        # vacío/# es indistinguible de "no hay enlace"); sin ese atributo, se busca por fragmento.
        propios = [et for et in anclas if et.atributos.get("data-legal") == clave]
        candidatos = [str((et.atributos.get("href") or "")) for et in propios] or \
            [str(et.atributos.get("href") or "") for et in anclas if fragmento in str(et.atributos.get("href") or "")]
        if not candidatos:
            hallazgos.append(Hallazgo(
                patron_clave=f"html:legal-ausente-{clave}", nivel="rojo", categoria="html",
                descripcion=f"falta el enlace a la página legal «{clave}» ({fragmento})", evidencia=fragmento,
            ))
        elif all(h.strip() in _HREFS_ROTOS for h in candidatos):
            hallazgos.append(Hallazgo(
                patron_clave=f"html:enlace-roto-{clave}", nivel="rojo", categoria="html",
                descripcion=f"el enlace a «{clave}» está roto (href vacío, # o javascript:void(0))", evidencia=candidatos[0] or "(vacío)",
            ))
    return hallazgos


def _texto_script(html: str, et: _Etiqueta) -> str:
    cierre = html.lower().find("</script>", et.inicio)
    return html[et.inicio:cierre if cierre != -1 else et.inicio + 400]


def _referencia_pixel(texto: str, src: str) -> bool:
    t = (texto + " " + src).lower()
    return any(marca in t for marca in _MARCADORES_PIXEL)


def _referencia_consentimiento(texto: str, src: str) -> bool:
    t = (texto + " " + src).lower()
    return any(marca in t for marca in _MARCADORES_CONSENTIMIENTO)


def _pixel_antes_del_consentimiento(html: str, parser: _RecolectorHTML) -> list[Hallazgo]:
    scripts = [et for et in parser.etiquetas if et.nombre == "script"]
    indices_consentimiento = [et.inicio for et in scripts if _referencia_consentimiento(_texto_script(html, et), str(et.atributos.get("src") or ""))]
    primer_consentimiento = min(indices_consentimiento) if indices_consentimiento else None
    hallazgos: list[Hallazgo] = []
    fin_head = html.lower().find("</head>")
    for et in scripts:
        src = str(et.atributos.get("src") or "")
        cuerpo = _texto_script(html, et)
        if not _referencia_pixel(cuerpo, src):
            continue
        guardado = (
            (et.atributos.get("type") or "").lower() == "text/plain"
            or "data-consent" in et.atributos
            or _referencia_consentimiento(cuerpo, "")  # el propio script condiciona su carga al consentimiento (patrón habitual)
        )
        if primer_consentimiento is None or et.inicio < primer_consentimiento:
            if not guardado:
                hallazgos.append(Hallazgo(
                    patron_clave="html:pixel-antes-de-consentir", nivel="rojo", categoria="html",
                    descripcion="el píxel se carga antes de (o sin) el script de consentimiento",
                    evidencia=cuerpo[:120] or src,
                ))
        if fin_head != -1 and et.inicio < fin_head and not guardado:
            hallazgos.append(Hallazgo(
                patron_clave="html:pixel-en-head-sin-condicion", nivel="rojo", categoria="html",
                descripcion="píxel cargado en <head> sin una condición de consentimiento (type=text/plain o data-consent)",
                evidencia=cuerpo[:120] or src,
            ))
    return hallazgos


def _temporizadores_falsos(html: str, parser: _RecolectorHTML) -> list[Hallazgo]:
    hallazgos: list[Hallazgo] = []
    vistos: set[int] = set()
    for et in parser.etiquetas:
        atributos_texto = " ".join(f"{k}={v}" for k, v in et.atributos.items())
        if not any(marca in atributos_texto.lower() for marca in _MARCADORES_COUNTDOWN):
            continue
        deadline = et.atributos.get("data-deadline")
        if not deadline or not _RX_INSTANTE_Z.fullmatch(deadline):
            if et.inicio not in vistos:
                vistos.add(et.inicio)
                hallazgos.append(Hallazgo(
                    patron_clave="html:temporizador-sin-fecha-verificable", nivel="rojo", categoria="html",
                    descripcion="temporizador de cuenta atrás sin data-deadline verificable (AAAA-MM-DDTHH:MM:SSZ): posible falso",
                    evidencia=atributos_texto[:120],
                ))
    return hallazgos


def _escasez_fija_sin_verificar(html: str) -> list[Hallazgo]:
    """«Quedan N cupos» fijo en el texto, sin un marcador de que el número es real (D-10b, L1-PUB a)."""
    if any(marca in html.lower() for marca in _MARCADORES_CUPO_VERIFICABLE):
        return []
    texto_visible = re.sub(r"<[^>]+>", " ", html)
    hallazgos: list[Hallazgo] = []
    vistos: set[str] = set()
    for m in _RX_ESCASEZ_FIJA.finditer(texto_visible):
        cita = m.group(0).strip()
        if cita in vistos:
            continue
        vistos.add(cita)
        hallazgos.append(Hallazgo(
            patron_clave="html:escasez-fija-sin-verificar", nivel="rojo", categoria="html",
            descripcion="escasez de cupos/plazas/lugares/unidades fija en el texto, sin data-cupos-verificable: posible falsa",
            evidencia=cita,
        ))
    return hallazgos


def _plantilla_sin_reemplazar(html: str) -> list[Hallazgo]:
    """«EJEMPLO», «Lorem», «[NOMBRE]», «TODO»: marcador de plantilla olvidado (L1-PUB a).

    Varios patrones pueden coincidir sobre el mismo marcador (p. ej. "[EJEMPLO]" matchea tanto
    ``\\[EJEMPLO\\]`` como ``\\bEJEMPLO\\b``): se deduplica por solapamiento de posiciones, no por
    patrón, para no repetir el mismo hallazgo.
    """
    hallazgos: list[Hallazgo] = []
    vistos: list[tuple[int, int]] = []
    for rx in _MARCADORES_PLANTILLA:
        for m in rx.finditer(html):
            if any(m.start() < fin and inicio < m.end() for inicio, fin in vistos):
                continue
            vistos.append((m.start(), m.end()))
            cita = html[max(0, m.start() - 20):m.end() + 20].strip()
            hallazgos.append(Hallazgo(
                patron_clave="html:plantilla-sin-reemplazar", nivel="rojo", categoria="html",
                descripcion="texto de plantilla sin reemplazar (marcador de ejemplo olvidado antes de publicar)",
                evidencia=cita,
            ))
    return hallazgos


def verificar_metadatos(metadatos: Mapping[str, object], reglas: Reglas, *, locale: str, macro_nicho: str | None = None) -> list[Hallazgo]:
    """Términos sensibles de salud/finanzas filtrados a las superficies de ``reglas.aplicado_a`` (D01).

    ``metadatos`` es un mapa llano: ``{"dominio": str, "rutas": [str], "title": str,
    "og": {clave: valor}, "eventos": [str], "parametros": [str]}``. Cualquier coincidencia aquí es
    ``rojo`` sin importar el nivel declarado en ``reglas_sensibles.yaml``: en estas superficies
    públicas la sola presencia del término es la filtración, no una cuestión de severidad de copy
    (ver «Decisiones» en ``compliance/README.md``).
    """
    categorias = categorias_de_locale(reglas, locale, macro_nicho, incluir_adicionales=True)
    textos: list[tuple[str, str]] = []
    if isinstance(metadatos.get("dominio"), str) and "dominio" in reglas.aplicado_a:
        textos.append(("dominio", metadatos["dominio"]))
    if "rutas" in reglas.aplicado_a:
        for i, ruta in enumerate(metadatos.get("rutas") or []):
            textos.append((f"rutas[{i}]", str(ruta)))
    if isinstance(metadatos.get("title"), str) and "title" in reglas.aplicado_a:
        textos.append(("title", metadatos["title"]))
    if "og" in reglas.aplicado_a:
        for clave, valor in (metadatos.get("og") or {}).items():
            textos.append((f"og.{clave}", str(valor)))
    if "eventos" in reglas.aplicado_a:
        for i, evento in enumerate(metadatos.get("eventos") or []):
            textos.append((f"eventos[{i}]", str(evento)))
    if "parametros" in reglas.aplicado_a:
        for i, parametro in enumerate(metadatos.get("parametros") or []):
            textos.append((f"parametros[{i}]", str(parametro)))

    hallazgos: list[Hallazgo] = []
    for origen, texto in textos:
        t = texto.lower()
        for categoria, cuerpo in categorias.items():
            for _nivel, patrones in (cuerpo or {}).items():
                for patron in patrones:
                    if re.search(patron, t, re.IGNORECASE):
                        hallazgos.append(Hallazgo(
                            patron_clave=f"metadatos:{categoria}", nivel="rojo", categoria="metadatos",
                            descripcion=f"término sensible de {categoria} filtrado en {origen} (D01)",
                            evidencia=f"{origen}: {texto[:120]}", locale=locale,
                        ))
    return hallazgos


def verificar_html(html: str, *, reglas: Reglas | None = None, locale: str | None = None, macro_nicho: str | None = None) -> list[Hallazgo]:
    """Hallazgos de ``html`` (cadena completa de una página servida o de ``sitio/<pagina>.html``).

    Cubre casillas premarcadas, enlaces legales (ausentes o rotos), píxel antes/sin condición de
    consentimiento y temporizadores sin fecha verificable; si se da ``reglas``/``locale``, agrega
    términos sensibles en ``<title>`` y ``og:*`` (D01).
    """
    if not isinstance(html, str):
        raise ErrorValidacion("verificar_html exige una cadena")
    parser = _parsear(html)
    hallazgos = (
        _casillas_premarcadas(parser)
        + _enlaces_legales(parser)
        + _pixel_antes_del_consentimiento(html, parser)
        + _temporizadores_falsos(html, parser)
        + _escasez_fija_sin_verificar(html)
        + _plantilla_sin_reemplazar(html)
    )
    if reglas is not None and locale is not None:
        og = {str(et.atributos.get("property") or et.atributos.get("name")): str(et.atributos.get("content") or "")
              for et in parser.etiquetas if et.nombre == "meta" and str(et.atributos.get("property") or et.atributos.get("name") or "").startswith("og:")}
        hallazgos += verificar_metadatos({"title": parser.titulo or "", "og": og}, reglas, locale=locale, macro_nicho=macro_nicho)
    return hallazgos


def _construir_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m compliance.html_checks", description=__doc__.splitlines()[0])
    p.add_argument("--archivo", required=True, type=Path, help="archivo HTML a revisar")
    p.add_argument("--locale", default=None, help="si se da, también revisa title/og:* contra reglas_sensibles.yaml")
    p.add_argument("--macro-nicho", choices=("salud", "relaciones", "dinero"), default=None)
    p.add_argument("--reglas", type=Path, default=None)
    p.add_argument("--json", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    """``python -m compliance.html_checks --archivo sitio/index.html [--locale L]``. Sale 3 si hay ``rojo``."""
    try:
        args = _construir_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        if not args.archivo.is_file():
            raise ErrorUso(f"no existe el archivo HTML: {args.archivo}")
        html = args.archivo.read_text(encoding="utf-8")
        reglas = cargar_reglas(args.reglas) if args.locale else None
        hallazgos = verificar_html(html, reglas=reglas, locale=args.locale, macro_nicho=args.macro_nicho)
        semaforo = peor_nivel(hallazgos)
        codigo = 3 if semaforo == "rojo" else 0
        avisos: list[str] = []
        if reglas is not None and reglas.revision_nativa.get(args.locale) is False:
            avisos.append(f"reglas de {args.locale} SIN revisión nativa (HIPÓTESIS): confirmar con hablante nativo antes de bloquear sin revisión humana")
        salida = {"ok": codigo == 0, "modo": "dry_run", "codigo": codigo, "datos": {"semaforo": semaforo, "hallazgos": [h.asdict() for h in hallazgos]}, "avisos": avisos}
        if args.json:
            print(comun.json_canonico(salida).decode("utf-8"))
        else:
            print(f"semáforo={semaforo} hallazgos={len(hallazgos)}")
            for h in hallazgos:
                print(f"  [{h.nivel}] {h.patron_clave}: {h.descripcion}")
        return codigo

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    import sys

    sys.exit(main())
