"""``landing.contenido``: de ``copy.json`` + ``oferta/checkout/producto`` a las secciones que se renderizan.

Responsabilidades (todas deterministas y sin red):

* cargar y **validar** ``copy.json``, ``paleta.json`` y ``assets.json`` contra sus esquemas (falla
  cerrado: ``ErrorValidacion``, código 3) y rechazar texto hostil (marcado HTML, ``javascript:``,
  caracteres de control o de dirección bidireccional como U+202E);
* **expandir** los placeholders (``{precio}``, ``{garantia_dias}``, ``{n:<id>}``…) desde el contrato:
  el Maker no escribe importes, plazos ni cantidades;
* cruzar el copy con el contrato (ids, CTA, ranuras, bump, testimonios con permiso);
* construir el contexto de cada sección del plano (``secciones.json`` de la plantilla), **omitiendo**
  las opcionales que no tengan material real, y repartir los tonos de fondo.

El texto del Maker nunca se concatena como HTML: pasa por :func:`landing.motor.md` (escapa y solo
entonces reconoce ``**negrita**`` y ``*énfasis*``).
"""
from __future__ import annotations

import copy as _copy
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Mapping

from referencing import Registry
from scripts import validar_esquemas as V

from engine import comun
from engine.errores import ErrorValidacion
from landing import motor, textos
from landing.imagenes import Imagen
from landing.plantillas import LEGALES

__all__ = ["DIR_PLANTILLA", "Entradas", "cargar_entradas", "expandir", "contexto_secciones", "contexto_pie", "meta_de_pagina", "texto_hostil", "plano_de",
           "ICONOS", "RX_FECHA", "cargar_fuentes_mercado", "fuente_respalda_cifra", "VIGENCIA_MERCADO_DIAS"]
VIGENCIA_MERCADO_DIAS = 30        # una cifra de mercado leída hace más de 30 días no se publica en producción (F-65)

RAIZ_CODIGO = Path(__file__).resolve().parents[1]
DIR_SKILL = RAIZ_CODIGO / ".claude" / "skills" / "d5-landing-checkout"
DIR_PLANTILLA = DIR_SKILL / "templates" / "sitio-base"
SECCIONES_OPCIONALES = ("S02", "S04", "S08", "S09", "S13", "S15", "S16")
# Íconos admitidos en copy.json (campo `icono`): cada uno es un <symbol id="i-<nombre>"> de sitio-base/sprite.html. Lista cerrada: el Maker no inyecta ids.
ICONOS = ("semilla", "reloj", "cohete", "diana", "libro", "mapa", "movil", "imprimir", "descarga", "corazon", "rayo", "bombilla", "grafico", "usuarios",
          "calendario", "chat", "ruta", "niveles", "persona", "hoja", "lupa", "escudo", "regalo", "sobre", "candado", "estrella", "pregunta", "balanza",
          "etiqueta", "pluma", "megafono", "insignia", "play")
RX_FECHA = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
_ICONOS_NIVEL = ("semilla", "libro", "ruta", "chat", "diana", "insignia")
_ICONOS_PERFIL = ("semilla", "reloj", "cohete", "diana", "libro", "bombilla")
_ICONOS_BENEFICIO = ("chat", "reloj", "niveles", "mapa")
_ICONOS_PASO = ("rayo", "sobre", "imprimir", "movil")
_ICONOS_CONFIANZA = ("i-lupa", "i-hoja", "i-escudo")
_DEMO_VALORACION = (48, 128)          # DEMO de vista previa: 4,8 · 128 opiniones (nunca se publica)
_DEMO_CONTADOR = 1234
CLAVES_NO_TEXTO = {"usos", "id", "tipo", "modo", "version_texto", "orden", "primero", "unidad", "traza", "motivo", "hook_original", "fecha", "icono", "estructura",
                   "angulo_id", "seccion", "premarcado", "premarcada", "obligatoria", "persona", "registro", "nota", "glosario_ref",
                   "schema_version", "oferta_id", "version", "origen_version", "locale", "moneda", "macro_nicho", "nivel", "compra_id"}
RX_PLACEHOLDER = re.compile(r"\{([a-z_]+)(?::([a-z0-9_-]+))?\}")
RX_HTML = re.compile(r"<\s*/?\s*[A-Za-z!?]")
RX_ESQUEMA_ACTIVO = re.compile(r"(?i)\b(?:javascript|vbscript)\s*:|data\s*:\s*text/html")
_PERMITIDOS_CF = {0x200C, 0x200D}


# ----------------------------------------------------------------------------------------------
# Texto hostil
# ----------------------------------------------------------------------------------------------
def texto_hostil(texto: str) -> str | None:
    """Motivo por el que ``texto`` no es admisible como copy (``None`` si lo es)."""
    for ch in texto:
        cat = unicodedata.category(ch)
        if cat == "Cc" and ch not in "\n\t":
            return f"carácter de control U+{ord(ch):04X}"
        if cat in ("Zl", "Zp"):
            return f"separador de línea o párrafo U+{ord(ch):04X}"
        if cat == "Cf" and ord(ch) not in _PERMITIDOS_CF:
            return f"carácter de formato o de dirección de texto U+{ord(ch):04X}"
    if RX_HTML.search(texto):
        return "marcado HTML (el copy es texto plano: solo **negrita** y *énfasis*)"
    if RX_ESQUEMA_ACTIVO.search(texto):
        return "enlace con esquema activo (javascript:, vbscript: o data:)"
    return None


def _recorrer(nodo: Any, ruta: str = "") -> list[tuple[str, str]]:
    """(ruta, texto) de cada cadena del JSON que se publica (omite metadatos)."""
    salida: list[tuple[str, str]] = []
    if isinstance(nodo, str):
        salida.append((ruta, nodo))
    elif isinstance(nodo, dict):
        for k, v in nodo.items():
            if k in CLAVES_NO_TEXTO or k.endswith("_ref"):
                continue
            salida += _recorrer(v, f"{ruta}.{k}" if ruta else k)
    elif isinstance(nodo, list):
        for i, v in enumerate(nodo):
            salida += _recorrer(v, f"{ruta}[{i}]")
    return salida


def _mapear(nodo: Any, f: Any, clave: str = "") -> Any:
    if isinstance(nodo, str):
        return nodo if clave in CLAVES_NO_TEXTO or clave.endswith("_ref") else f(nodo)
    if isinstance(nodo, dict):
        return {k: _mapear(v, f, k) for k, v in nodo.items()}
    if isinstance(nodo, list):
        return [_mapear(v, f, clave) for v in nodo]
    return nodo


# ----------------------------------------------------------------------------------------------
# Esquemas
# ----------------------------------------------------------------------------------------------
def _esquema(nombre: str, *, solo_skill: bool = False) -> dict[str, Any]:
    """``contratos/<nombre>.schema.json`` si ya existe (A0 lo integró); si no, la propuesta de la skill (``solo_skill`` la fuerza)."""
    for base in ((DIR_SKILL / "templates",) if solo_skill else (RAIZ_CODIGO / "contratos", DIR_SKILL / "templates")):
        ruta = base / f"{nombre}.schema.json"
        if ruta.is_file():
            return comun.cargar_json(ruta)
    raise ErrorValidacion(f"no existe el esquema {nombre}.schema.json (ni en contratos/ ni en la skill d5-landing-checkout)")


def _errores(nombre: str, esquema: Mapping[str, Any], instancia: Any) -> list[str]:
    v = V.Validador(dict(esquema), registry=Registry())   # registro vacío: una referencia sin resolver falla, nunca sale a la red
    errores = sorted(v.iter_errors(instancia), key=lambda e: list(map(str, e.absolute_path)))
    return [f"{nombre}{V.ruta_json(e)}: {e.message[:200]}" for e in errores[:12]]


def _validar_artefacto(nombre: str, instancia: Any) -> None:
    if nombre == "assets":
        # 1.0.x = contrato vigente (contratos/assets.schema.json); 1.1.x = ampliación propuesta por la skill de D5.
        if str(instancia.get("schema_version", "")).startswith("1.0."):
            errores = [f"assets.json{V.ruta_json(e)}: {e.message[:200]}" for e in V.errores_de_esquema("assets", instancia)[:12]]
        else:
            errores = _errores("assets.json", _esquema("assets", solo_skill=True), instancia)
    else:
        errores = _errores(f"{nombre}.json", _esquema(nombre), instancia)
    if errores:
        raise ErrorValidacion(f"{nombre}.json no cumple su esquema: " + " | ".join(errores), detalle={"errores": errores})


# ----------------------------------------------------------------------------------------------
# Entradas
# ----------------------------------------------------------------------------------------------
@dataclass
class Entradas:
    """Todo lo que necesita el sitio diseñado (ya validado)."""

    oferta: dict[str, Any]
    checkout: dict[str, Any]
    tracking: dict[str, Any]
    producto: dict[str, Any] | None
    copy: dict[str, Any]
    paleta: dict[str, Any]
    assets: dict[str, Any]
    rutas: dict[str, str]
    dir_landing: Path
    ayuda: str | None
    avisos: list[str] = field(default_factory=list)
    prueba_social: dict[str, Any] | None = None     # 05-landing/prueba_social_real.json (dato REAL con fuente y fecha) o None
    fuentes_mercado: dict[str, Any] | None = None   # 05-landing/fuentes_mercado.json (fuentes declaradas de las cifras de S16: archivo/URL + fecha + cifra) o None
    hoy: date | None = None                         # fecha de generación: solo la usa la barra de lanzamiento (no se compara con el reloj en ningún otro sitio)
    vista_previa: bool = False                      # --vista-previa: marcadores, demos con cinta DEMO y barra fija; NUNCA en producción


def _ayuda_pais(dir_oferta: Path, locale: str, paises: list[str]) -> str | None:
    """Línea de ayuda del país desde ``empresa/compliance/ayuda_por_pais.yaml`` (formato PROVISIONAL: ``PL: {texto: …}`` o ``PL: …``)."""
    ruta = dir_oferta.parent.parent / "empresa" / "compliance" / "ayuda_por_pais.yaml"
    if not ruta.is_file():
        return None
    datos = V.cargar_yaml(ruta)
    if not isinstance(datos, dict):
        return None
    region = locale.split("-")[1].upper() if "-" in locale else ""
    for pais in [*(paises or []), region]:
        entrada = datos.get(pais)
        if isinstance(entrada, dict):
            entrada = entrada.get("texto") or entrada.get("linea") or entrada.get("ayuda")
        if isinstance(entrada, str) and entrada.strip():
            return entrada.strip()
    return None


def cargar_entradas(dir_oferta: Path, *, oferta: dict[str, Any], checkout: dict[str, Any], tracking: dict[str, Any],
                    rutas: dict[str, str], producto: dict[str, Any] | None, hoy: date | None = None, vista_previa: bool = False
                    ) -> tuple[Entradas | None, list[str]]:
    """Carga y valida ``copy.json``, ``paleta.json`` y ``assets.json``; ``(None, avisos)`` si falta alguno (sitio mínimo).

    Errores (``ErrorValidacion``): archivo ilegible o que no cumple el esquema, ids que no coinciden con la oferta, texto hostil.
    """
    land = dir_oferta / "05-landing"
    rutas_json = {n: land / f"{n}.json" for n in ("copy", "paleta", "assets")}
    faltan = [f"{n}.json" for n, r in rutas_json.items() if not r.is_file()]
    if faltan:
        return None, [f"faltan {', '.join(faltan)} en 05-landing/: se genera el sitio mínimo sin diseño"]
    datos = {n: comun.cargar_json(r) for n, r in rutas_json.items()}
    for nombre, doc in datos.items():
        _validar_artefacto(nombre, doc)
        if doc["oferta_id"] != oferta["oferta_id"]:
            raise ErrorValidacion(f"{nombre}.json: oferta_id {doc['oferta_id']!r} distinto de oferta.json ({oferta['oferta_id']!r})")
    cp = datos["copy"]
    if cp["locale"] != oferta["locale"]:
        raise ErrorValidacion(f"copy.json: locale {cp['locale']!r} distinto de oferta.json ({oferta['locale']!r})")
    if cp["moneda"] != oferta["moneda"]:
        raise ErrorValidacion(f"copy.json: moneda {cp['moneda']!r} distinta de oferta.json ({oferta['moneda']!r})")
    hostiles = [f"{r}: {m}" for r, t in _recorrer(cp) if (m := texto_hostil(t))]
    hostiles += [f"assets.json {s['slot_id']}.alt: {m}" for s in datos["assets"]["slots"] if (m := texto_hostil(s.get("alt", "")))]
    marca = oferta["marca"]
    hostiles += [f"oferta.json {k}: {m}" for k, t in (("marca.nombre", marca["nombre"]), ("marca.dominio", marca["dominio"]),
                                                     ("promesa.titulo", oferta["promesa"]["titulo"])) if (m := texto_hostil(t))]
    if hostiles:
        raise ErrorValidacion("texto no admisible en la landing: " + " | ".join(hostiles[:10]), detalle={"hallazgos": hostiles})
    ayuda = _ayuda_pais(dir_oferta, oferta["locale"], oferta.get("paises_segmentacion") or [])
    prueba = cargar_prueba_social(land, oferta)
    fuentes = cargar_fuentes_mercado(land, oferta)
    ent = Entradas(oferta=oferta, checkout=checkout, tracking=tracking, producto=producto, copy=cp, paleta=datos["paleta"],
                   assets=datos["assets"], rutas=rutas, dir_landing=land, ayuda=ayuda, prueba_social=prueba, fuentes_mercado=fuentes, hoy=hoy or date.today(), vista_previa=vista_previa)
    return ent, []


def cargar_prueba_social(land: Path, oferta: Mapping[str, Any]) -> dict[str, Any] | None:
    """``05-landing/prueba_social_real.json`` (ventas reales, descargas de la muestra y valoración, cada una con ``fuente`` y ``al``) o ``None``.

    Lo produce CÓDIGO a partir de datos reales (Stripe, registro de descargas, reseñas verificadas), no el Maker. Un bloque con total 0 o ausente no se muestra. El
    archivo se valida contra ``templates/prueba_social_real.schema.json``; ``oferta_id`` debe coincidir con ``oferta.json``.
    """
    ruta = land / "prueba_social_real.json"
    if not ruta.is_file():
        return None
    doc = comun.cargar_json(ruta)
    _validar_artefacto("prueba_social_real", doc)
    if doc["oferta_id"] != oferta["oferta_id"]:
        raise ErrorValidacion(f"prueba_social_real.json: oferta_id {doc['oferta_id']!r} distinto de oferta.json ({oferta['oferta_id']!r})")
    hostiles = [f"{r}: {m}" for r, t in _recorrer(doc) if (m := texto_hostil(t))]
    if hostiles:
        raise ErrorValidacion("texto no admisible en prueba_social_real.json: " + " | ".join(hostiles[:6]))
    return doc


def cargar_fuentes_mercado(land: Path, oferta: Mapping[str, Any]) -> dict[str, Any] | None:
    """``05-landing/fuentes_mercado.json``: las fuentes DECLARADAS de las cifras de «comparación con el mercado» (``fuente``, ``url`` y/o ``archivo`` capturado con su
    ``sha256``, ``fecha`` y las ``cifras`` observadas). Con él, S16 se valida por código (:func:`fuente_respalda_cifra`) en vez de a mano (F-64). ``None`` si no existe."""
    ruta = land / "fuentes_mercado.json"
    if not ruta.is_file():
        return None
    doc = comun.cargar_json(ruta)
    _validar_artefacto("fuentes_mercado", doc)
    if doc["oferta_id"] != oferta["oferta_id"]:
        raise ErrorValidacion(f"fuentes_mercado.json: oferta_id {doc['oferta_id']!r} distinto de oferta.json ({oferta['oferta_id']!r})")
    hostiles = [f"{r}: {m}" for r, t in _recorrer(doc) if (m := texto_hostil(t))]
    if hostiles:
        raise ErrorValidacion("texto no admisible en fuentes_mercado.json: " + " | ".join(hostiles[:6]))
    return doc


def _monto_en_texto(monto: int, exponente: int, texto: str) -> bool:
    """¿Aparece ``monto`` (unidad menor) en ``texto`` capturado? Admite ``129``, ``129,00`` y ``129.00`` (enteros y decimales con coma o punto), como palabra entera."""
    entero, resto = divmod(int(monto), 10 ** exponente)
    variantes = [str(entero)] if resto == 0 else []
    if exponente:
        variantes += [f"{entero}{sep}{str(resto).zfill(exponente)}" for sep in (",", ".")]
    return any(re.search(r"(?<![0-9.,])" + re.escape(v) + r"(?![0-9])", texto) for v in variantes)


def fuente_respalda_cifra(doc: Mapping[str, Any] | None, land: Path, *, fuente: str, fecha: str, desde: int, hasta: int | None, moneda: str) -> list[str]:
    """Motivos (vacío = respaldada) por los que una fila de S16 no la respalda ``fuentes_mercado.json``.

    Cada nombre de ``fuente`` (separados por coma) debe estar declarado con LA MISMA ``fecha``; ``desde`` y ``hasta`` deben figurar entre las ``cifras`` de esas fuentes
    (en la moneda de la oferta); si la fuente trae ``archivo`` capturado se comprueba que exista dentro de ``05-landing/``, que su ``sha256`` coincida y que cada cifra
    aparezca en su texto. Sin ``doc`` no hay nada que contrastar (devuelve el motivo «sin fuentes_mercado.json»)."""
    if doc is None:
        return ["no hay 05-landing/fuentes_mercado.json con las fuentes declaradas"]
    problemas: list[str] = []
    nombres = [n.strip().lower() for n in fuente.split(",") if n.strip()]
    declaradas = {f["fuente"].strip().lower(): f for f in doc["fuentes"] if f["fecha"] == fecha}
    montos: set[int] = set()
    exponente = V.EXPONENTE_ISO4217.get(moneda, 2)
    base = land.resolve()
    for n in nombres:
        f = declaradas.get(n)
        if f is None:
            problemas.append(f"la fuente {n!r} no está declarada con fecha {fecha}")
            continue
        if f.get("moneda", moneda) != moneda:
            problemas.append(f"la fuente {n!r} declara {f.get('moneda')}, la oferta es {moneda}")
            continue
        cifras = {int(c["monto"]) for c in f["cifras"]}
        montos |= cifras
        if f.get("archivo"):
            ruta = (base / f["archivo"]).resolve()
            if base not in ruta.parents or not ruta.is_file():
                problemas.append(f"el archivo capturado de {n!r} no existe dentro de 05-landing/: {f['archivo']}")
                continue
            if "sha256:" + hashlib.sha256(ruta.read_bytes()).hexdigest() != f["sha256"]:
                problemas.append(f"el sha256 del archivo capturado de {n!r} no coincide")
                continue
            texto = ruta.read_text(encoding="utf-8", errors="replace")
            faltan = sorted(c for c in cifras if not _monto_en_texto(c, exponente, texto))
            if faltan:
                problemas.append(f"la cifra {faltan} declarada para {n!r} no aparece en su archivo capturado")
    if not nombres:
        problemas.append("la fila no nombra ninguna fuente")
    for etiqueta, v in (("desde", desde), ("hasta", hasta)):
        if v is not None and not problemas and int(v) not in montos:
            problemas.append(f"{etiqueta}={v} no figura entre las cifras de las fuentes declaradas ({sorted(montos)})")
    return problemas


def plano_de(copy: Mapping[str, Any]) -> str:
    """Plano de página: ``copy.estructura`` si existe; si no, ``referente`` para ``copy.schema_version`` ≥ 0.2.0 y ``clasica`` para 0.1.x (compatibilidad)."""
    est = copy.get("estructura")
    if est in ("referente", "clasica"):
        return str(est)
    m = re.match(r"^0\.(\d+)\.", str(copy.get("schema_version", "")))
    return "referente" if m and int(m.group(1)) >= 2 else "clasica"


# ----------------------------------------------------------------------------------------------
# Placeholders
# ----------------------------------------------------------------------------------------------
class _Fuente:
    """Resuelve cada placeholder desde el contrato; ``ErrorValidacion`` si su fuente no existe."""

    def __init__(self, e: Entradas, extra: Mapping[str, str] | None = None) -> None:
        self.e, self.locale, self.extra = e, e.oferta["locale"], dict(extra or {})

    def _exigir(self, valor: Any, nombre: str, origen: str) -> Any:
        if valor in (None, ""):
            raise ErrorValidacion(f"copy.json usa {{{nombre}}} pero falta {origen}")
        return valor

    def _entregable(self, ident: str) -> Mapping[str, Any] | None:
        return next((x for x in self.e.oferta.get("entregables") or [] if x.get("id") == ident), None)

    def _item(self, ident: str) -> Mapping[str, Any] | None:
        return next((x for x in (self.e.producto or {}).get("items") or [] if x.get("id") == ident), None)

    def valor(self, nombre: str, arg: str | None) -> str:  # noqa: C901 - tabla de placeholders, lineal
        o, c, p = self.e.oferta, self.e.checkout, self.e.producto
        if nombre in self.extra:
            return self.extra[nombre]
        if nombre == "precio":
            return textos.formatear_importe(c["precio"]["monto"], c["moneda"], self.locale)
        if nombre == "precio_bump":
            b = self._exigir((c.get("bump") or {}).get("precio"), nombre, "checkout.bump")
            return textos.formatear_importe(b["monto"], b["moneda"], self.locale)
        if nombre == "moneda":
            return c["moneda"]
        if nombre == "garantia_dias":
            return str(int(o["garantia"]["dias"]))
        if nombre == "tiempo_min":
            return str(int(self._exigir(o["promesa"].get("tiempo_prometido_min"), nombre, "oferta.promesa.tiempo_prometido_min")))
        if nombre == "marca":
            return o["marca"]["nombre"]
        if nombre == "producto":
            return o["promesa"]["titulo"]
        if nombre in ("bump_nombre", "bump_descripcion"):
            b = self._exigir(o.get("bump"), nombre, "oferta.bump")
            return str(self._exigir(b.get("nombre" if nombre == "bump_nombre" else "descripcion"), nombre, f"oferta.bump.{nombre[5:]}"))
        if nombre in ("vence_dias", "max_descargas"):
            ent = self._exigir((p or {}).get("entrega"), nombre, "04-producto/producto.json (entrega)")
            return str(int(ent[nombre]))
        if nombre == "ia_divulgacion":
            return str(self._exigir((p or {}).get("ia_divulgacion"), nombre, "producto.ia_divulgacion"))
        if nombre == "ayuda_pais":
            return str(self._exigir(self.e.ayuda, nombre, "empresa/compliance/ayuda_por_pais.yaml del país (X1; formato provisional)"))
        if nombre == "n" and arg == "paquete":
            items = [i for i in (p or {}).get("items") or [] if i.get("en_paquete")]
            if items:
                return str(len(items))
            return str(sum(int(x.get("cantidad", 1)) for x in o.get("entregables") or []) or self._exigir(None, "n:paquete", "producto.items"))
        if nombre == "n" and arg:
            ent = self._entregable(arg)
            return str(int(self._exigir((ent or {}).get("cantidad"), f"n:{arg}", f"oferta.entregables[{arg}].cantidad")))
        if nombre == "paginas" and arg:
            item = self._item(arg)
            return str(int(self._exigir((item or {}).get("paginas"), f"paginas:{arg}", f"producto.items[{arg}].paginas")))
        if nombre == "formato" and arg:
            ent, item = self._entregable(arg), self._item(arg)
            return str(self._exigir((ent or {}).get("formato") or (item or {}).get("formato"), f"formato:{arg}", f"oferta.entregables[{arg}].formato"))
        raise ErrorValidacion(f"copy.json: placeholder desconocido {{{nombre}{':' + arg if arg else ''}}}")


def expandir(e: Entradas) -> dict[str, Any]:
    """Copia de ``copy.json`` con todos los placeholders expandidos desde el contrato."""
    fuente = _Fuente(e)

    def f(texto: str) -> str:
        return RX_PLACEHOLDER.sub(lambda m: fuente.valor(m.group(1), m.group(2)), texto)

    # La barra de lanzamiento usa {fecha_lanzamiento} y {precio_despues}, que solo existen si checkout.json trae el precio programado: se expande aparte.
    origen = _copy.deepcopy(e.copy)
    lanzamiento = (origen.get("barra_superior") or {}).pop("lanzamiento", None)
    cp = _mapear(origen, f)
    if lanzamiento is not None:
        cp["barra_superior"]["lanzamiento"] = lanzamiento
    residuos = [f"{r}: {t[:50]}" for r, t in _recorrer(cp) if ("{" in t or "}" in t) and not r.startswith("barra_superior.lanzamiento")]
    if residuos:
        raise ErrorValidacion("copy.json: llaves sin resolver tras expandir placeholders: " + " | ".join(residuos[:6]))
    hostiles = [f"{r}: {m}" for r, t in _recorrer(cp) if (m := texto_hostil(t))]
    if hostiles:
        raise ErrorValidacion("texto no admisible tras expandir placeholders: " + " | ".join(hostiles[:6]))
    return cp


# ----------------------------------------------------------------------------------------------
# Coherencia copy <-> contrato
# ----------------------------------------------------------------------------------------------
def comprobar_coherencia(e: Entradas, cp: Mapping[str, Any]) -> list[str]:
    """Errores duros (``ErrorValidacion``) y devuelve avisos: ids, CTA, ranuras, bump, testimonios, variantes, fechas."""
    avisos: list[str] = []
    s = cp["secciones"]
    cta_ids = {c["id"] for c in cp["cta"]}
    if len({c["texto"] for c in cp["cta"]}) < 2:
        raise ErrorValidacion("copy.json: cta[] necesita al menos 2 textos distintos")
    refs = [("S01", s["S01"]["cta_ref"]), ("S11", s["S11"]["cta_ref"])] + ([("S13", s["S13"]["cta_ref"])] if "S13" in s else [])
    refs += [(sec, s[sec]["cta_ref"]) for sec in ("S04", "S06", "S07", "S08", "S15") if isinstance(s.get(sec), dict) and s[sec].get("cta_ref")]
    for sec, ref in refs:
        if ref not in cta_ids:
            raise ErrorValidacion(f"copy.json: {sec}.cta_ref {ref!r} no existe en cta[]")
    slots = {x["slot_id"] for x in e.assets["slots"]}
    pedidos = [("S01.imagen_ref", s["S01"]["imagen_ref"])] + [(f"S04.pies[{i}].imagen_ref", p["imagen_ref"]) for i, p in enumerate((s.get("S04") or {}).get("pies", []))]
    for donde, ref in pedidos:
        if ref not in slots:
            raise ErrorValidacion(f"copy.json: {donde} {ref!r} no es una ranura de assets.json")
    ids_faq = [q["id"] for q in s["S12"]["preguntas"]]
    if len(set(ids_faq)) != len(ids_faq):
        raise ErrorValidacion("copy.json: ids repetidos en S12.preguntas")
    if "S09" in s and s["S09"].get("bump") is not None and not ((e.oferta.get("bump") or {}) and (e.checkout.get("bump") or {})):
        raise ErrorValidacion("copy.json: S09.bump presente pero oferta.bump o checkout.bump no existen (el bump solo se ofrece si es real)")
    if "S08" in s:
        s8 = s["S08"]
        if s8["modo"] == "honesta" and s8["resenas"]:
            raise ErrorValidacion("copy.json: S08 en modo honesta no puede traer reseñas")
        permiso = {x.get("fuente") for x in e.oferta.get("prueba") or [] if x.get("tipo") == "testimonio_con_permiso" and x.get("consentimiento_ref")}
        for r in s8["resenas"] if s8["modo"] == "real" else []:
            if r["compra_id"] not in permiso:
                raise ErrorValidacion(f"copy.json: la reseña {r['compra_id']!r} no tiene testimonio con permiso en oferta.prueba (no se publica prueba social inventada)")
    if e.checkout["garantia_dias"] != e.oferta["garantia"]["dias"]:
        raise ErrorValidacion("checkout.json: garantia_dias distinto de oferta.garantia.dias (C02)")
    ids_items = {i["id"] for i in (e.producto or {}).get("items") or []}
    for m in s["S06"]["modulos"]:
        if e.producto and m["item_ref"] not in ids_items:
            avisos.append(f"S06: item_ref {m['item_ref']!r} no existe en producto.items")
    for ang, var in cp["variantes_por_angulo"].items():
        if "S11" in var and var["S11"]["cta_ref"] not in cta_ids:
            raise ErrorValidacion(f"copy.json: variantes_por_angulo.{ang}.S11.cta_ref desconocido")
        if "S12" in var and var["S12"]["primero"] not in ids_faq:
            raise ErrorValidacion(f"copy.json: variantes_por_angulo.{ang}.S12.primero {var['S12']['primero']!r} no es una pregunta")
        if "S03" in var and "S03" in s and sorted(var["S03"]["orden"]) != list(range(len(s["S03"]["dolores"]))):
            raise ErrorValidacion(f"copy.json: variantes_por_angulo.{ang}.S03.orden debe ser una permutación de los dolores")
    omitidas = {x["seccion"] for x in cp["omitidas"]}
    for sec in omitidas & set(s):
        avisos.append(f"{sec} figura en omitidas[] pero tiene bloque en copy.json: se renderiza")
    for donde, f in [("S16.filas[%d].fecha" % i, r["fecha"]) for i, r in enumerate((s.get("S16") or {}).get("filas", []))] + \
                    ([("barra_superior.lanzamiento.fecha", cp["barra_superior"]["lanzamiento"]["fecha"])] if (cp.get("barra_superior") or {}).get("lanzamiento") else []):
        try:
            date.fromisoformat(f)
        except ValueError as exc:
            raise ErrorValidacion(f"copy.json: {donde} {f!r} no es una fecha AAAA-MM-DD válida") from exc
    plan = plano_de(cp)
    fuera = [sec for sec in (("S02", "S03", "S05") if plan == "referente" else ("S15", "S16")) if sec in s]
    for sec in fuera:
        avisos.append(f"{sec} no forma parte del plano {plan}: su texto no se publica" + (" (el gancho de dolor va en el héroe y la FAQ; usa estructura: clasica para publicarla)" if plan == "referente" else ""))
    return avisos


# ----------------------------------------------------------------------------------------------
# Secciones
# ----------------------------------------------------------------------------------------------
def _md_lista(items: list[str]) -> list[motor.Seguro]:
    return [motor.md(x) for x in items]


def _img(im: Imagen | None, rot: Mapping[str, str] | None = None, *, por_imagen: bool = True) -> dict[str, Any] | None:
    """Imagen lista para la plantilla. Trae ``slot``, ``ilustrativa`` e ``ia`` (se vuelcan a ``data-slot``/``data-ilustrativa``/``data-ia`` del ``<img>``: los lee
    ``landing.validar``) y, con ``por_imagen``, el ``rotulo`` de su insignia («Ilustración orientativa · Imagen generada con ayuda de IA») y los ``tipos`` que cubre.
    En modo ``grupo`` el rótulo de las imágenes de una sección sale UNA vez (``_rotulo_de_grupo``) y aquí ``rotulo`` queda en ``None``."""
    if im is None:
        return None
    partes = ([rot["ilustrativa"]] if im.ilustrativa else []) + ([rot["ia"]] if im.ia_visible else []) if rot else []
    tipos = " ".join(k for k, v in (("ilustrativa", im.ilustrativa), ("ia", im.ia_visible)) if v)
    return {"url": im.url, "ancho": im.ancho, "alto": im.alto, "alt": im.alt, "slot": im.slot_id, "ilustrativa": im.ilustrativa, "ia": im.ia_visible,
            "rotulo": " · ".join(partes) if (partes and por_imagen) else None, "tipos": tipos or None}


def _rotulo_de_grupo(ims: list[Imagen | None], rot: Mapping[str, str]) -> dict[str, str] | None:
    """Pie ÚNICO de un grupo de imágenes (modo ``grupo``): cubre lo que lleve alguna de ellas (ilustrativa y/o IA); ``None`` si ninguna lo lleva."""
    reales = [i for i in ims if i is not None]
    ilus, ia = any(i.ilustrativa for i in reales), any(i.ia_visible for i in reales)
    if not (ilus or ia):
        return None
    texto = " ".join(x for x in ((rot["ilustrativa_pie"] if ilus else ""), (rot["ia"] + "." if ia else "")) if x)
    return {"tipos": " ".join(k for k, v in (("ilustrativa", ilus), ("ia", ia)) if v), "texto": texto}


def _color(i: int) -> str:
    """Índice de color de ícono (1-6) que cicla por posición; la plantilla lo usa como ``icono-caja--c<N>`` / ``avatar--c<N>``."""
    return str(i % 6 + 1)


def _icono(token: str | None, por_defecto: str) -> str:
    return token if token in ICONOS else por_defecto


def _marcador(e: Entradas, que: str) -> str | None:
    """Etiqueta del marcador de vista previa de una imagen que falta (``None`` fuera de vista previa: entonces el bloque se omite o usa su diseño sin imagen)."""
    return textos.TEXTO_VISTA_PREVIA["marcador_imagen"].format(que=que) if e.vista_previa else None


def _variante(cp: dict[str, Any], angulo_id: str) -> dict[str, Any]:
    """Copia de ``copy`` con los cuatro bloques variables del ángulo aplicados."""
    var = (cp["variantes_por_angulo"] or {}).get(angulo_id) or {}
    s = _copy.deepcopy(cp["secciones"])
    if "S01" in var:
        s["S01"].update(var["S01"])
    if "S03" in var and "S03" in s:
        s["S03"]["dolores"] = [s["S03"]["dolores"][i] for i in var["S03"]["orden"]]
    if "S11" in var:
        s["S11"]["cta_ref"] = var["S11"]["cta_ref"]
    if "S12" in var:
        pregs = s["S12"]["preguntas"]
        s["S12"]["preguntas"] = sorted(pregs, key=lambda q: q["id"] != var["S12"]["primero"])
    return s


def _cta_de_bloque(cp: Mapping[str, Any], s: Mapping[str, Any], sec: str) -> str:
    """Texto del CTA repetido tras la sección ``sec``: su ``cta_ref``, o el CTA de ``cta[]`` cuyo ``usos`` la nombra, o el del héroe."""
    por_id = {c["id"]: c["texto"] for c in cp["cta"]}
    ref = (s.get(sec) or {}).get("cta_ref") if isinstance(s.get(sec), dict) else None
    if ref:
        return por_id[ref]
    for c in cp["cta"]:
        if sec in (c.get("usos") or []):
            return c["texto"]
    return por_id[s["S01"]["cta_ref"]]


def _prueba_social(e: Entradas, t: Mapping[str, str]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """``(pastilla de valoración, contador)`` del héroe: SOLO con ``prueba_social_real.json`` (total ≥ 1, con fuente y fecha); sin dato real no hay nada.

    En vista previa y sin dato real se pintan valores de DEMOSTRACIÓN con la cinta «DEMO» (``landing.validar`` los bloquea: L1-DEMO). Con dato real, el real sustituye al demo.
    """
    locale = e.oferta["locale"]
    ps = e.prueba_social or {}
    val, ventas, desc = ps.get("valoracion"), ps.get("ventas"), ps.get("descargas_muestra")
    prueba = contador = None
    if val and int(val["n"]) >= 1 and 10 <= int(val["media_decimas"]) <= 50:
        m = int(val["media_decimas"])
        prueba = {"valor": textos.formatear_decimal(m // 10, m % 10, locale), "n": textos.formatear_entero(int(val["n"]), locale), "demo": False,
                  "media": m, "n_num": int(val["n"])}
    if ventas and int(ventas["total"]) >= 1:
        contador = {"etiqueta": t["ventas"], "valor": textos.formatear_entero(int(ventas["total"]), locale), "icono": "usuarios", "demo": False, "avatares": None,
                    "dato_al": textos.formatear_fecha(ventas["al"], locale), "tipo": "ventas", "numero": int(ventas["total"])}
    elif desc and int(desc["total"]) >= 1:
        contador = {"etiqueta": t["descargas_muestra"], "valor": textos.formatear_entero(int(desc["total"]), locale), "icono": "descarga", "demo": False, "avatares": None,
                    "dato_al": textos.formatear_fecha(desc["al"], locale), "tipo": "descargas", "numero": int(desc["total"])}
    if e.vista_previa:
        if prueba is None:
            prueba = {"valor": textos.formatear_decimal(_DEMO_VALORACION[0] // 10, _DEMO_VALORACION[0] % 10, locale),
                      "n": textos.formatear_entero(_DEMO_VALORACION[1], locale), "demo": True}
        if contador is None:
            nombres = textos.demo_resenas(locale)
            contador = {"etiqueta": t["descargas_muestra"], "valor": textos.formatear_entero(_DEMO_CONTADOR, locale), "icono": "descarga", "demo": True, "dato_al": None,
                        "avatares": [{"inicial": n["inicial"], "color": _color(i)} for i, n in enumerate(nombres)]}
    return prueba, contador


def _barra_superior(e: Entradas, cp: Mapping[str, Any], avisos: list[str]) -> dict[str, Any] | None:
    """Barra superior: la de lanzamiento solo si ``checkout.precio_programado`` trae la MISMA fecha, esa fecha no ha pasado y el precio de después es mayor;
    si no, la informativa (siempre posible). Sin ninguna, ``None``. Nunca una cuenta atrás ni un «solo hoy» sin fecha real."""
    bloque = cp.get("barra_superior")
    if not bloque:
        return None
    locale = e.oferta["locale"]
    lanz = bloque.get("lanzamiento")
    if lanz:
        prog = e.checkout.get("precio_programado")
        motivo = None
        if not isinstance(prog, dict):
            motivo = "checkout.json no trae precio_programado"
        elif prog.get("fecha") != lanz["fecha"]:
            motivo = f"la fecha {lanz['fecha']} no coincide con checkout.precio_programado.fecha ({prog.get('fecha')!r})"
        elif not RX_FECHA.match(lanz["fecha"]) or (e.hoy is not None and date.fromisoformat(lanz["fecha"]) < e.hoy):
            motivo = f"la fecha {lanz['fecha']} ya pasó (hoy {e.hoy})"
        else:
            despues = (prog.get("precio") or {})
            if not isinstance(despues.get("monto"), int) or despues.get("moneda") != e.checkout["moneda"] or despues["monto"] <= e.checkout["precio"]["monto"]:
                motivo = "precio_programado.precio debe ser mayor que el precio actual y en la misma moneda (un «precio de lanzamiento» sube después)"
        if motivo is None:
            fuente = _Fuente(e, {"fecha_lanzamiento": textos.formatear_fecha(lanz["fecha"], locale),
                                 "precio_despues": textos.formatear_importe(prog["precio"]["monto"], prog["precio"]["moneda"], locale)})
            texto = RX_PLACEHOLDER.sub(lambda m: fuente.valor(m.group(1), m.group(2)), lanz["texto"])
            hostil = texto_hostil(texto)
            if hostil:
                raise ErrorValidacion(f"copy.json: barra_superior.lanzamiento.texto no admisible tras expandir: {hostil}")
            return {"texto": motor.md(texto), "lanzamiento": lanz["fecha"], "icono": _icono(bloque.get("icono"), "etiqueta")}
        avisos.append(f"barra_superior.lanzamiento omitida: {motivo}")
    if bloque.get("informativa"):
        return {"texto": motor.md(bloque["informativa"]), "lanzamiento": None, "icono": _icono(bloque.get("icono"), "escudo")}
    return None


def _comparacion(e: Entradas, s16: Mapping[str, Any], precio: str, avisos: list[str]) -> dict[str, Any] | None:
    """Comparación con el mercado (S16): cada fila exige ``fuente`` y ``fecha``; cifras como enteros en unidad menor (``desde``/``hasta``) formateadas por código."""
    locale, moneda = e.oferta["locale"], e.checkout["moneda"]
    filas = []
    for i, f in enumerate(s16["filas"]):
        fuente = (f.get("fuente") or "").strip()
        if not fuente:
            avisos.append(f"S16.filas[{i}] sin fuente: la cifra no se publica (toda cifra de mercado lleva su fuente)")
            continue
        hasta = f.get("hasta")
        if hasta is not None and hasta < f["desde"]:
            raise ErrorValidacion(f"copy.json: S16.filas[{i}].hasta ({hasta}) es menor que desde ({f['desde']})")
        if e.fuentes_mercado is not None:        # fuentes declaradas: cada cifra se contrasta por código; una que no coincide detiene la generación (no se publica a ojo)
            motivos = fuente_respalda_cifra(e.fuentes_mercado, e.dir_landing, fuente=fuente, fecha=f["fecha"], desde=f["desde"], hasta=hasta, moneda=moneda)
            if motivos:
                raise ErrorValidacion(f"copy.json: S16.filas[{i}] no la respalda fuentes_mercado.json: " + " | ".join(motivos))
        filas.append({"etiqueta": motor.md(f["etiqueta"]), "fuente": fuente, "fecha": textos.formatear_fecha(f["fecha"], locale), "fecha_iso": f["fecha"],
                      "desde": f["desde"], "hasta": hasta if hasta is not None else f["desde"], "rango": textos.formatear_rango(f["desde"], hasta, moneda, locale)})
    if filas and e.fuentes_mercado is None:
        avisos.append("S16: las cifras de mercado no se contrastaron con una fuente declarada (falta 05-landing/fuentes_mercado.json); se publican sin verificación automática [VERIFICAR]")
    if not filas:
        avisos.append("S16 omitida: ninguna fila trae fuente")
        return None
    return {"titulo": motor.md(s16["titulo"]), "intro": motor.md(s16["intro"]) if s16.get("intro") else None, "filas": filas, "precio": precio}


def _resenas_demo(e: Entradas) -> list[dict[str, Any]]:
    """Cuatro opiniones de DEMOSTRACIÓN (solo vista previa): estrellas, sin «compra verificada», una con estilo de chat. ``landing.validar`` las bloquea (L1-DEMO)."""
    return [{"fuente": "", "texto": motor.md(d["texto"]), "nombre": d["nombre"], "inicial": d["inicial"], "verificada": False, "estrellas": True, "chat": i == 2,
             "demo": True, "color": _color(i)} for i, d in enumerate(textos.demo_resenas(e.oferta["locale"]))]


def contexto_secciones(e: Entradas, cp: dict[str, Any], imagenes: Mapping[str, Imagen], angulo_id: str, diseno_alternos: Mapping[str, str],
                       manifiesto: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:  # noqa: C901 - tabla lineal por sección
    """Secciones a renderizar (``{spec, ctx}`` en el orden del plano), avisos de omisión y datos de la barra fija y de la barra superior.

    ``spec`` ya trae los ajustes del plano (plantilla, tono, ``cta``); ``ctx`` trae el tono repartido y ``cta_texto`` si la sección lleva CTA repetido.
    Devuelve también ``{"precio", "texto", "ultimo_tono", "primer_tono", "superior"}`` para la barra de compra móvil, la cabecera y la barra superior.
    """
    locale = e.oferta["locale"]
    t = textos.rotulos(locale)
    s = _variante(cp, angulo_id)
    cta = {c["id"]: c["texto"] for c in cp["cta"]}
    avisos: list[str] = []
    precio = textos.formatear_importe(e.checkout["precio"]["monto"], e.checkout["moneda"], locale)
    plan_nombre = plano_de(cp)
    plan = manifiesto["planos"][plan_nombre]
    ref = plan_nombre == "referente"
    ctx: dict[str, dict[str, Any] | None] = {}
    cfg_rot = cp.get("rotulos_imagen") or {}
    rot = textos.rotulos_de_imagen(locale, cfg_rot)
    por_imagen = cfg_rot.get("modo", "imagen") != "grupo"           # «grupo»: un solo pie por sección de varias imágenes (galería y bonus)
    declaradas = {x["slot_id"] for x in e.assets["slots"] if x["estado"] != "omitida"}

    s1 = s["S01"]
    prueba, contador = _prueba_social(e, t)
    im_hero = imagenes.get(s1["imagen_ref"])
    im_pack = imagenes.get("portada-pack")
    # Héroe sin mockup propio: la portada plana del pack (ranura `portada-pack`) antes que la portada tipográfica.
    hero_es_pack = im_hero is None and im_pack is not None
    if hero_es_pack:
        im_hero = im_pack
    ctx["S01"] = {
        "kicker": motor.md(s1["kicker"]), "h1": motor.md(s1["h1"]), "h1_resaltado": motor.md(s1["h1_resaltado"]) if s1.get("h1_resaltado") else None,
        "subtitulo": motor.md(s1["subtitulo"]), "pills": _md_lista(s1["pills"]), "cta": {"texto": cta[s1["cta_ref"]]},
        "microcopy": motor.md(s1["microcopy"]), "imagen": _img(im_hero, rot), "imagen_es_pack": hero_es_pack,
        "portada": {"marca": e.oferta["marca"]["nombre"], "titulo": e.oferta["promesa"]["titulo"], "kicker": motor.texto_plano(s1["kicker"])},
        "marcador": _marcador(e, "mockup del producto") if im_hero is None else None, "prueba": prueba, "contador": contador,
    }
    if hero_es_pack:
        avisos.append("S01: sin imagen de héroe aprobada; se usa la ranura portada-pack")
    if im_hero is None:
        avisos.append("S01: la ranura del hero no está aprobada; se usa la portada tipográfica (sin imagen)" if not e.vista_previa
                      else "S01: la ranura del hero no está aprobada; vista previa con marcador de mockup")

    if "S02" in s and not ref:
        traza = {x["valor"] for x in cp["cifras_con_traza"]}
        brutas = (e.copy["secciones"].get("S02") or {}).get("cifras", [])
        cifras = []
        for crudo, ya in zip(brutas, s["S02"]["cifras"]):
            if not RX_PLACEHOLDER.search(crudo["valor"]) and re.search(r"\d", crudo["valor"]) and crudo["valor"] not in traza:
                avisos.append(f"S02: cifra {crudo['valor']!r} sin traza en cifras_con_traza; se descarta")
                continue
            cifras.append({"valor": ya["valor"], "etiqueta": motor.md(ya["etiqueta"])})
        ctx["S02"] = {
            "cifras": cifras, "n_cifras": 4 if len(cifras) == 4 else 3,
            "beneficios": [{"num": f"{i + 1:02d}", "titulo": motor.md(b["titulo"]), "texto": motor.md(b["texto"]), "icono": _icono(b.get("icono"), _ICONOS_BENEFICIO[i % 4]),
                            "color": _color(i)} for i, b in enumerate(s["S02"]["beneficios"])],
        }
        if len(cifras) < 3:
            ctx["S02"]["cifras"] = []

    if "S03" in s and not ref:
        s3 = s["S03"]
        ctx["S03"] = {"titulo": motor.md(s3["titulo"]), "dolores": [{"texto": motor.md(d["texto"])} for d in s3["dolores"]], "reencuadre": motor.md(s3["reencuadre"])}

    if "S04" in s:
        figuras = []
        ims_s04 = [imagenes.get(p["imagen_ref"]) for p in s["S04"]["pies"]]
        for p in s["S04"]["pies"]:
            im = imagenes.get(p["imagen_ref"])
            if im is None:
                if e.vista_previa:
                    figuras.append({"imagen": None, "marcador": _marcador(e, "miniatura de un mapa"), "texto": motor.md(p["texto"]), "principal": not figuras, "horizontal": False})
                    continue
                avisos.append(f"S04: la ranura {p['imagen_ref']} no está aprobada; su captura no se muestra")
                continue
            figuras.append({"imagen": _img(im, rot, por_imagen=por_imagen), "marcador": None, "texto": motor.md(p["texto"]), "principal": not figuras,
                            "horizontal": im.ancho > im.alto})
        if figuras:
            ctx["S04"] = {"kicker": motor.md(s["S04"]["kicker"]), "titulo": motor.md(s["S04"]["titulo"]), "figuras": figuras,
                          "subtitulo": motor.md(s["S04"]["subtitulo"]) if s["S04"].get("subtitulo") else None,
                          "rotulo_grupo": None if por_imagen else _rotulo_de_grupo([i for i in ims_s04 if i is not None], rot),
                          "n_figuras": "1" if len(figuras) == 1 else "2" if len(figuras) == 2 else "n"}
        else:
            avisos.append("S04 omitida: ninguna captura real aprobada")

    if "S05" in s and not ref:
        s5 = s["S05"]
        ctx["S05"] = {"kicker": motor.md(s5["kicker"]), "nombre": motor.md(s5["nombre"]), "subtitulo": motor.md(s5["subtitulo"]) if s5.get("subtitulo") else None,
                      "como_funciona": motor.md(s5["como_funciona"]), "de_a_b": motor.md(s5["de_a_b"]), "etiquetas": _md_lista(s5["etiquetas"])}

    s6 = s["S06"]
    check = s6.get("checklist")
    ctx["S06"] = {
        "kicker": motor.md(s6["kicker"]) if s6.get("kicker") else None, "titulo": motor.md(s6["titulo"]),
        "subtitulo": motor.md(s6["subtitulo"]) if s6.get("subtitulo") else None,
        "modulos": [{"num": f"{i + 1:02d}", "titulo": motor.md(m["titulo"]), "texto": motor.md(m["texto"]), "color": _color(i),
                     "icono": _icono(m.get("icono"), _ICONOS_NIVEL[i % len(_ICONOS_NIVEL)]), "etiqueta": motor.md(m["etiqueta"]) if m.get("etiqueta") else None,
                     "temas": _md_lista(m["temas"]) if m.get("temas") else None,
                     "categorias": [{"titulo": motor.md(c["titulo"]), "texto": motor.md(c["texto"]) if c.get("texto") else None,
                                     "temas": _md_lista(c["temas"]) if c.get("temas") else None} for c in m["categorias"]] if m.get("categorias") else None}
                    for i, m in enumerate(s6["modulos"])],
        "n_modulos": str(min(len(s6["modulos"]), 8)),
        "checklist": {"titulo": motor.md(check["titulo"]), "items": _md_lista(check["items"])} if check and check.get("items") and not ref else None,
    }

    s7 = s["S07"]
    if s7.get("tarjetas"):
        tarjetas = [{"titulo": motor.md(x["titulo"]) if x.get("titulo") else None, "texto": motor.md(x["texto"]), "icono": _icono(x.get("icono"), _ICONOS_PERFIL[i % 6]),
                     "color": _color(i)} for i, x in enumerate(s7["tarjetas"])]
    else:
        tarjetas = [{"titulo": None, "texto": motor.md(x), "icono": _ICONOS_PERFIL[i % 6], "color": _color(i)} for i, x in enumerate(s7["si"])]
    ctx["S07"] = {"kicker": motor.md(s7["kicker"]) if s7.get("kicker") else None, "titulo": motor.md(s7["titulo"]),
                  "subtitulo": motor.md(s7["subtitulo"]) if s7.get("subtitulo") else None, "si": _md_lista(s7["si"]), "no": _md_lista(s7["no"]), "tarjetas": tarjetas}

    if "S08" in s:
        s8 = s["S08"]
        reales = [{"fuente": r["compra_id"], "texto": motor.md(r["texto"]), "nombre": r.get("autor"), "inicial": (r.get("autor") or "")[:1].upper() or None,
                   "verificada": True, "estrellas": False, "chat": False, "demo": False, "color": _color(i)}
                  for i, r in enumerate(s8["resenas"])] if s8["modo"] == "real" else []
        bloques = [{"icono": _ICONOS_CONFIANZA[i % 3], "titulo": motor.md(b["titulo"]), "texto": motor.md(b["texto"]), "color": _color(i)} for i, b in enumerate(s8["bloques"])]
        demo = False
        if not reales and e.vista_previa and ref:
            reales, demo = _resenas_demo(e), True
        if reales or bloques or not ref:
            ctx["S08"] = {"kicker": motor.md(s8["kicker"]) if s8.get("kicker") else None, "titulo": motor.md(s8["titulo"]),
                          "subtitulo": motor.md(s8["subtitulo"]) if s8.get("subtitulo") else None, "bloques": bloques, "resenas": reales,
                          "aviso_demo": textos.TEXTO_VISTA_PREVIA["aviso_opiniones"] if demo else None}
        else:
            avisos.append("S08 omitida: sin reseñas reales con compra verificada ni bloques comprobables")

    if "S09" in s:
        s9 = s["S09"]
        ids_pack = {i["id"] for i in (e.producto or {}).get("items") or [] if i.get("en_paquete")}
        bonos = []
        ims_s09: list[Imagen | None] = []
        por_img9 = por_imagen and ref        # bonus del plano clásico = miniaturas de 4,5 rem: su rótulo va por grupo
        for i, b in enumerate(s9["bonos"]):
            if e.producto is not None and b["archivo_ref"] not in ids_pack:
                avisos.append(f"S09: el bono {b['nombre'][:30]!r} no tiene archivo en producto.items; se omite")
                continue
            im = imagenes.get(f"bono-{i + 1}")
            ims_s09.append(im)
            bonos.append({"nombre": motor.md(b["nombre"]), "texto": motor.md(b["texto"]), "imagen": _img(im, rot, por_imagen=por_img9), "color": _color(len(bonos)),
                          "marcador": _marcador(e, "portada del bonus") if im is None else None})
        bump = s9.get("bump")
        im_bump = imagenes.get("bump") if bump else None
        if bump and im_bump is None and "bump" in declaradas and e.vista_previa:
            marcador_bump = _marcador(e, "portada del bump")
        else:
            marcador_bump = None
        if bonos or bump:
            ctx["S09"] = {
                "titulo": motor.md(s9["titulo"]), "bonos": bonos, "subtitulo": motor.md(s9["subtitulo"]) if s9.get("subtitulo") else None,
                "bump": {"nombre": motor.md(bump["nombre"]), "texto": motor.md(bump["texto"]), "etiqueta_casilla": motor.md(bump["etiqueta_casilla"]),
                         "imagen": _img(im_bump, rot, por_imagen=por_img9), "marcador": marcador_bump} if bump else None,
                "rotulo_grupo": None if por_img9 else _rotulo_de_grupo([*[x for x in ims_s09 if x is not None], im_bump], rot),
            }
        else:
            avisos.append("S09 omitida: sin bono con archivo ni bump")

    s10 = s["S10"]
    ctx["S10"] = {"titulo": motor.md(s10["titulo"]), "texto": motor.md(s10["texto"]), "nota_legal": motor.md(s10["nota_legal"]), "dias": str(int(e.oferta["garantia"]["dias"]))}

    s11 = s["S11"]
    metodos = " · ".join(textos.etiqueta_metodo(m, locale) for m in e.checkout.get("metodos") or [])
    im_compra = imagenes.get("compra")
    # La portada plana del pack (`portada-pack`): imagen principal de la tarjeta si no hay escena de compra; con escena, una miniatura junto a «qué recibes».
    pack_es_principal = im_compra is None and im_pack is not None
    im_principal = im_pack if pack_es_principal else im_compra
    im_mini = im_pack if (im_compra is not None and im_pack is not None and not hero_es_pack) else None
    ctx["S11"] = {
        "titulo": motor.md(s11["titulo"]), "descripcion": motor.md(s11["descripcion"]), "incluye": _md_lista(s11["incluye"]), "pills": _md_lista(s11["pills"]),
        "precio": precio, "linea_precio": motor.md(s11["linea_precio"]), "cta": {"texto": cta[s11["cta_ref"]]}, "metodos": metodos,
        "imagen": _img(im_principal, rot), "marcador": _marcador(e, "mockup del producto") if im_principal is None else None,
        "imagen_mini": _img(im_mini, rot),
    }

    s12 = s["S12"]
    ctx["S12"] = {"titulo": motor.md(s12["titulo"]), "preguntas": [{"id": f"faq-{q['id']}" if not q["id"].startswith("faq") else q["id"], "q": motor.md(q["q"]), "a": motor.md(q["a"])} for q in s12["preguntas"]]}

    if "S13" in s:
        s13 = s["S13"]
        ctx["S13"] = {"titulo": motor.md(s13["titulo"]), "filas": [{"sin": motor.md(f["sin"]), "con": motor.md(f["con"])} for f in s13["filas"]],
                      "cta": {"texto": cta[s13["cta_ref"]]}, "microcopy": motor.md(s13["microcopy"]),
                      # plano referente: lista de seguridad bajo el CTA final = `lista` del Maker o, sin ella, las diferencias verificables («con») de las filas
                      "lista": _md_lista(s13["lista"]) if s13.get("lista") else _md_lista([f["con"] for f in s13["filas"]])}

    if ref:
        s15 = s.get("S15")
        if s15:
            pasos = [{"titulo": motor.md(p["titulo"]), "texto": motor.md(p["texto"]) if p.get("texto") else None, "icono": _icono(p.get("icono"), _ICONOS_PASO[i % 4]),
                      "color": _color(i), "num": str(i + 1)} for i, p in enumerate(s15["pasos"])]
            ctx["S15"] = {"kicker": motor.md(s15["kicker"]) if s15.get("kicker") else None, "titulo": motor.md(s15["titulo"]), "pasos": pasos}
        elif check and check.get("items"):
            pasos = [{"titulo": motor.md(x), "texto": None, "icono": _ICONOS_PASO[i % 4], "color": _color(i), "num": str(i + 1)} for i, x in enumerate(check["items"][:4])]
            ctx["S15"] = {"kicker": None, "titulo": motor.md(check["titulo"]), "pasos": pasos}
        if s.get("S16"):
            comp = _comparacion(e, s["S16"], precio, avisos)
            if comp:
                ctx["S16"] = comp

    # Orden (el del plano), tonos y CTA repetido.
    specs = {x["id"]: x for x in manifiesto["secciones"]}
    salida: list[dict[str, Any]] = []
    previo: str | None = None
    primero: str | None = None
    for sec in plan["orden"]:
        c = ctx.get(sec)
        if c is None:
            continue
        spec = {**specs[sec], **plan["ajustes"].get(sec, {}), "variante": plan_nombre}
        if sec == "S06" and ref and s["S06"].get("selector") == "desplegable":
            spec["plantilla"] = "s06-niveles.html"          # selector con <details> en vez de pestañas con :target (ambos sin JavaScript)
        tono = spec["tono"]
        if previo is not None and tono == previo:
            tono = diseno_alternos.get(tono, tono)
        previo = tono
        primero = primero or tono
        extra = {"cta_texto": _cta_de_bloque(cp, s, sec)} if spec.get("cta") else {}
        salida.append({"spec": spec, "ctx": {**c, "tono": tono, "ancla": spec["ancla"], "t": t, "variante": plan_nombre, **extra}})
    barra = {"precio": precio, "texto": cta[s11["cta_ref"]], "superior": _barra_superior(e, cp, avisos), "primer_tono": primero or "oscuro"}
    return salida, avisos, {**barra, "ultimo_tono": previo or "oscuro"}


def contexto_pie(e: Entradas, cp: Mapping[str, Any], tono_previo: str, diseno_alternos: Mapping[str, str]) -> dict[str, Any]:
    """Contexto del pie (S14): avisos, enlaces legales (+ desistimiento si la ruta existe) y preferencias de cookies."""
    s14 = cp["secciones"]["S14"]
    locale = e.oferta["locale"]
    t = textos.rotulos(locale)
    avisos = [{"tipo": "alcance", "texto": motor.md(s14["aviso"])}]
    seg = (s14.get("aviso_seguridad") or "").strip()
    ayuda = (s14.get("ayuda") or "").strip()
    if seg:
        avisos.append({"tipo": "seguridad", "texto": motor.md(seg)})
    if ayuda and ayuda not in seg:
        avisos.append({"tipo": "ayuda", "texto": motor.md(ayuda)})
    enlaces = [{"href": f"/legal/{n}", "texto": s14["enlaces"][n]} for n in LEGALES]
    if "/desistimiento" in e.rutas:
        enlaces.append({"href": "/desistimiento", "texto": s14["enlaces"]["desistimiento"]})
    tono = "profundo"
    if tono_previo == tono:
        tono = diseno_alternos.get(tono, tono)
    return {"marca": e.oferta["marca"]["nombre"], "descripcion": motor.md(s14["descripcion"]), "avisos": avisos, "enlaces": enlaces,
            "preferencias": s14["enlaces"]["preferencias_cookies"], "t": t, "tono": tono}


def meta_de_pagina(e: Entradas, cp: Mapping[str, Any]) -> dict[str, str]:
    """``<title>``/descripción/``og:*`` (texto plano, sin marcas) de ``copy.meta``."""
    m = cp["meta"]
    return {k: motor.texto_plano(m[k]) for k in ("title", "description", "og_title", "og_description")}


def manifiesto() -> dict[str, Any]:
    """``secciones.json`` de la plantilla."""
    ruta = DIR_PLANTILLA / "secciones.json"
    if not ruta.is_file():
        raise ErrorValidacion(f"falta la plantilla sitio-base: {ruta}")
    return json.loads(ruta.read_text(encoding="utf-8"))
