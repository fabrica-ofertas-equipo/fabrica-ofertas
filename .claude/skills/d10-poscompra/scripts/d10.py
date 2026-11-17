#!/usr/bin/env python3
"""d10.py — utilidades deterministas de la skill d10-poscompra (v0.1 sin pulir). Solo biblioteca estándar: sin red, sin claves, sin Stripe, sin Meta.

La IA redacta y el código ejecuta: este script NO envía correos, NO cobra, NO reembolsa y NO publica nada. Solo valida y construye archivos locales.

Subcomandos (todos con ``--json``; código de salida 0 correcto, 2 uso, 3 validación):

* ``validar-prueba-social``  — ``05-landing/prueba_social_real.json`` contra lo que espera la landing (esquema ``prueba_social_real`` 0.x de D5, ``landing.contenido.cargar_prueba_social``
  y ``landing.validar`` L1-PRUEBA-SOCIAL): claves cerradas, tipos exactos, fechas reales, ``oferta_id``, texto no hostil y ninguna marca de demostración.
* ``construir-prueba-social`` — agrega reseñas REALES (``resenas.jsonl``) en la valoración de ``prueba_social_real.json`` y separa las reseñas con permiso de texto. Una reseña sin permiso
  explícito NO entra; una reseña negativa NO se omite; nada se redondea hacia arriba por gusto (mitad hacia arriba, en décimas).
* ``correo``                  — expande una plantilla de ``templates/`` con datos validados y escapados (texto y HTML). Solo campos de la lista cerrada ``CAMPOS`` (datos personales mínimos).
* ``lint-plantilla``          — revisa una plantilla: campos, identidad del vendedor, asunto neutro, incentivos, urgencia, promoción en correo transaccional.
* ``plan-entrega``            — qué archivos corresponden a las líneas pagadas de una sesión (principal, bump…). Simula el contrato propuesto de entrega por línea; el código real es de S-B.
* ``validar-orden``           — una orden del Maker al código (``reembolsar``, ``reenviar_entrega``…): nunca lleva montos, destinatarios ni «forzar».
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import unicodedata
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import urlsplit

# ----------------------------------------------------------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------------------------------------------------------
RX_OFERTA = re.compile(r"^OF-[0-9]{6}-[0-9]{2}$")
RX_FECHA = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
RX_TS = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")
RX_SCHEMA_VER = re.compile(r"^0\.[0-9]+\.[0-9]+$")
RX_SESION = re.compile(r"^cs_[A-Za-z0-9_]+$")
RX_REF = re.compile(r"^[A-Za-z0-9_-]{4,40}$")
RX_HTML = re.compile(r"<\s*/?\s*[A-Za-z!?]")
RX_ESQUEMA_ACTIVO = re.compile(r"(?i)\b(?:javascript|vbscript)\s*:|data\s*:\s*text/html")
RX_PLACEHOLDER = re.compile(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}")
RX_MARCA_DEMO = re.compile(r"(?i)\b(demo|test|ejemplo|example|sint[eé]tic\w*|simulad\w*|lorem|placeholder|de prueba|przyk[łl]ad\w*|pr[óo]bn\w*|esempio|beispiel)\b")
_PERMITIDOS_CF = {0x200C, 0x200D}

SECRETOS_PROHIBIDOS_EN_ORDEN = re.compile(
    r"(?i)(monto|importe|amount|moneda|currency|forz|force|ignor|tope|override|destinatari|email|correo|iban|tarjeta|card|cuenta|token|clave|secret)")


class ErrorD10(Exception):
    """Entrada inválida (código de salida 3)."""


# ----------------------------------------------------------------------------------------------------------------------
# Utilidades de texto
# ----------------------------------------------------------------------------------------------------------------------
def texto_hostil(texto: str) -> str | None:
    """Motivo por el que ``texto`` no es admisible como texto publicable (``None`` si lo es). Espejo de ``landing.contenido.texto_hostil``."""
    for ch in texto:
        cat = unicodedata.category(ch)
        if cat == "Cc" and ch not in "\n\t":
            return f"carácter de control U+{ord(ch):04X}"
        if cat in ("Zl", "Zp"):
            return f"separador de línea o párrafo U+{ord(ch):04X}"
        if cat == "Cf" and ord(ch) not in _PERMITIDOS_CF:
            return f"carácter de formato o de dirección de texto U+{ord(ch):04X}"
    if RX_HTML.search(texto):
        return "marcado HTML"
    if RX_ESQUEMA_ACTIVO.search(texto):
        return "enlace con esquema activo (javascript:, vbscript: o data:)"
    return None


def _limpiar(texto: str, *, multilinea: bool) -> str:
    """Quita controles y marcas de dirección; en una sola línea convierte saltos en espacios (anti inyección de cabeceras)."""
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    salida = []
    for ch in texto:
        cat = unicodedata.category(ch)
        if ch == "\n":
            salida.append("\n" if multilinea else " ")
        elif ch == "\t":
            salida.append(" ")
        elif cat == "Cc" or cat in ("Zl", "Zp") or (cat == "Cf" and ord(ch) not in _PERMITIDOS_CF):
            continue
        else:
            salida.append(ch)
    resultado = "".join(salida)
    if multilinea:
        resultado = re.sub(r"[ ]{2,}", " ", resultado)
        resultado = re.sub(r"\n{3,}", "\n\n", resultado)
        return resultado.strip()
    return re.sub(r"\s+", " ", resultado).strip()


def _es_entero(v: Any) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _fecha_valida(texto: Any) -> date | None:
    if not isinstance(texto, str) or not RX_FECHA.match(texto):
        return None
    try:
        return date.fromisoformat(texto)
    except ValueError:
        return None


def _parse_hoy(valor: str | None) -> date:
    if valor is None:
        return date.today()
    d = _fecha_valida(valor)
    if d is None:
        raise ErrorD10(f"--hoy {valor!r} no es una fecha AAAA-MM-DD válida")
    return d


# ----------------------------------------------------------------------------------------------------------------------
# prueba_social_real.json
# ----------------------------------------------------------------------------------------------------------------------
def validar_prueba_social(doc: Any, *, oferta_id: str | None = None, hoy: date | None = None,
                          resenas_informe: Mapping[str, Any] | None = None) -> tuple[list[str], list[str]]:
    """``(errores, avisos)``. Sin errores = la landing lo acepta. ``resenas_informe`` (de ``construir``) permite cruzar ``valoracion`` con las reseñas que cuentan."""
    hoy = hoy or date.today()
    errores: list[str] = []
    avisos: list[str] = []
    if not isinstance(doc, dict):
        return ["la raíz debe ser un objeto JSON"], avisos
    permitidas = {"schema_version", "oferta_id", "generado_en", "ventas", "descargas_muestra", "valoracion"}
    for k in sorted(set(doc) - permitidas):
        errores.append(f"clave no admitida {k!r} (el esquema es cerrado: additionalProperties=false)")
    for k in ("schema_version", "oferta_id", "generado_en"):
        if k not in doc:
            errores.append(f"falta {k!r}")
    if "schema_version" in doc and not (isinstance(doc["schema_version"], str) and RX_SCHEMA_VER.match(doc["schema_version"])):
        errores.append("schema_version debe ser 0.x.y")
    if "oferta_id" in doc:
        if not (isinstance(doc["oferta_id"], str) and RX_OFERTA.match(doc["oferta_id"])):
            errores.append("oferta_id con formato inválido (OF-AAAAMM-NN)")
        elif oferta_id and doc["oferta_id"] != oferta_id:
            errores.append(f"oferta_id {doc['oferta_id']!r} distinto de la oferta {oferta_id!r} (la landing lo rechaza)")
    generado = None
    if "generado_en" in doc:
        if not (isinstance(doc["generado_en"], str) and RX_TS.match(doc["generado_en"])):
            errores.append("generado_en debe ser AAAA-MM-DDThh:mm:ssZ")
        else:
            generado = _fecha_valida(doc["generado_en"][:10])
            if generado is None:
                errores.append("generado_en no es una fecha real")
            elif generado > hoy:
                errores.append(f"generado_en {doc['generado_en']} está en el futuro (hoy {hoy})")

    def fuente_ok(ruta: str, b: Mapping[str, Any]) -> None:
        f = b.get("fuente")
        if not (isinstance(f, str) and 3 <= len(f) <= 120):
            errores.append(f"{ruta}.fuente debe ser texto de 3 a 120 caracteres")
            return
        motivo = texto_hostil(f)
        if motivo:
            errores.append(f"{ruta}.fuente no admisible: {motivo}")
        if RX_MARCA_DEMO.search(f):
            errores.append(f"{ruta}.fuente parece de demostración o de prueba ({f!r}): solo se publica lo medido (L1-DEMO)")
        al = _fecha_valida(b.get("al"))
        if al is None:
            errores.append(f"{ruta}.al debe ser una fecha real AAAA-MM-DD")
        else:
            if al > hoy:
                errores.append(f"{ruta}.al {b['al']} está en el futuro (hoy {hoy})")
            if generado and al > generado:
                errores.append(f"{ruta}.al {b['al']} es posterior a generado_en")

    for nombre in ("ventas", "descargas_muestra"):
        if nombre not in doc:
            continue
        b = doc[nombre]
        if not isinstance(b, dict):
            errores.append(f"{nombre} debe ser un objeto")
            continue
        for k in sorted(set(b) - {"total", "fuente", "al"}):
            errores.append(f"{nombre}: clave no admitida {k!r}")
        for k in ("total", "fuente", "al"):
            if k not in b:
                errores.append(f"{nombre}: falta {k!r}")
        if "total" in b and not (_es_entero(b["total"]) and b["total"] >= 0):
            errores.append(f"{nombre}.total debe ser un entero ≥ 0 (nunca texto, decimal ni booleano)")
        elif b.get("total") == 0:
            avisos.append(f"{nombre}.total = 0: la landing no mostrará ese bloque")
        fuente_ok(nombre, b)

    if "valoracion" in doc:
        v = doc["valoracion"]
        if not isinstance(v, dict):
            errores.append("valoracion debe ser un objeto")
        else:
            for k in sorted(set(v) - {"media_decimas", "n", "fuente", "al"}):
                errores.append(f"valoracion: clave no admitida {k!r}")
            for k in ("media_decimas", "n", "fuente", "al"):
                if k not in v:
                    errores.append(f"valoracion: falta {k!r}")
            if "media_decimas" in v and not (_es_entero(v["media_decimas"]) and 10 <= v["media_decimas"] <= 50):
                errores.append("valoracion.media_decimas debe ser un entero entre 10 y 50 (48 = 4,8 de 5)")
            if "n" in v and not (_es_entero(v["n"]) and v["n"] >= 1):
                errores.append("valoracion.n debe ser un entero ≥ 1 (sin valoraciones reales no hay bloque)")
            fuente_ok("valoracion", v)
            if resenas_informe is not None and not errores:
                esperado = resenas_informe.get("valoracion")
                if not esperado:
                    errores.append("valoracion presente pero ninguna reseña con permiso la respalda")
                elif (esperado["n"], esperado["media_decimas"]) != (v["n"], v["media_decimas"]):
                    errores.append(f"valoracion (n={v['n']}, media_decimas={v['media_decimas']}) no coincide con las reseñas que cuentan "
                                   f"(n={esperado['n']}, media_decimas={esperado['media_decimas']})")
    return errores, avisos


_SENALES_TEXTO = (
    ("html", RX_HTML),
    ("url", re.compile(r"(?i)(https?://|www\.|\b[a-z0-9-]+\.(com|pl|es|it|net|org|io|eu)\b)")),
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    ("telefono", re.compile(r"(?<!\d)(?:\+?\d[\s().-]?){8,}(?!\d)")),
    ("cifra_de_resultado", re.compile(r"(?i)\d[\d.,]*\s?(%|kg|kilos?|zł|pln|eur|€|\$|usd|£|gbp)|(%|€|\$|£)\s?\d")),
    ("antes_y_despues", re.compile(r"(?i)antes y despu[eé]s|before and after|przed i po|prima e dopo")),
)


def senales_de_riesgo(texto: str) -> list[str]:
    """Motivos por los que un texto de cliente NO se publica sin revisión humana (cifras de resultado, datos personales, enlaces, marcado)."""
    senales = [codigo for codigo, rx in _SENALES_TEXTO if rx.search(texto)]
    if texto_hostil(texto) and "html" not in senales:
        senales.append("caracteres_no_admisibles")
    if len(texto) > 600:
        senales.append("demasiado_largo")
    return senales


def evaluar_resenas(resenas: Sequence[Mapping[str, Any]], *, oferta_id: str, hoy: date, n_min: int = 1,
                    fuente_valoracion: str = "Reseñas de compradores verificados, con su permiso", permitir_sinteticos: bool = False) -> dict[str, Any]:
    """Decide qué reseñas cuentan y cuáles se pueden publicar. Función pura.

    Cuenta en la valoración solo una reseña con compra verificada, estrellas 1-5, **permiso explícito** de valoración (``permiso.valoracion is True`` con ``version_texto`` y
    ``dado_en``), no retirada, sin incentivo y vigente (la última por sesión). Las negativas cuentan igual: nunca se filtra por sentimiento.
    """
    descartadas: list[dict[str, str]] = []
    validas: dict[str, Mapping[str, Any]] = {}
    for r in sorted(resenas, key=lambda x: (str(x.get("recibida_en", "")), str(x.get("resena_id", "")))):
        rid = str(r.get("resena_id", "?"))
        sesion = r.get("checkout_session_id")
        if r.get("sintetico") is True and not permitir_sinteticos:
            descartadas.append({"resena_id": rid, "motivo": "sintetica_nunca_se_publica"})
            continue
        if not (isinstance(sesion, str) and RX_SESION.match(sesion)):
            descartadas.append({"resena_id": rid, "motivo": "sin_sesion"})
            continue
        if r.get("oferta_id") not in (None, oferta_id):
            descartadas.append({"resena_id": rid, "motivo": "otra_oferta"})
            continue
        recibida = _fecha_valida(str(r.get("recibida_en", ""))[:10])
        if recibida is None or recibida > hoy:
            descartadas.append({"resena_id": rid, "motivo": "fecha_invalida_o_futura"})
            continue
        if sesion in validas:
            descartadas.append({"resena_id": str(validas[sesion].get("resena_id", "?")), "motivo": "reemplazada_por_una_posterior"})
        validas[sesion] = r
    contadas: list[Mapping[str, Any]] = []
    autorizadas_o_no: list[Mapping[str, Any]] = []
    for sesion, r in validas.items():
        rid = str(r.get("resena_id", "?"))
        if r.get("retirada") is True:
            descartadas.append({"resena_id": rid, "motivo": "retirada_por_su_autor"})
            continue
        if r.get("compra_verificada") is not True:
            descartadas.append({"resena_id": rid, "motivo": "no_verificada"})
            continue
        e = r.get("estrellas")
        if not (_es_entero(e) and 1 <= e <= 5):
            descartadas.append({"resena_id": rid, "motivo": "estrellas_invalidas"})
            continue
        if r.get("incentivo") is not False:
            descartadas.append({"resena_id": rid, "motivo": "incentivo_o_incentivo_no_declarado"})
            continue
        autorizadas_o_no.append(r)
        p = r.get("permiso")
        if not (isinstance(p, dict) and p.get("valoracion") is True and p.get("version_texto") and p.get("dado_en")):
            descartadas.append({"resena_id": rid, "motivo": "sin_permiso_de_valoracion"})
            continue
        contadas.append(r)

    def dist(rs: Iterable[Mapping[str, Any]]) -> dict[str, int]:
        d = {str(i): 0 for i in range(1, 6)}
        for x in rs:
            d[str(x["estrellas"])] += 1
        return d

    def media_decimas(rs: Sequence[Mapping[str, Any]]) -> int | None:
        if not rs:
            return None
        m = (Decimal(sum(int(x["estrellas"]) for x in rs)) / Decimal(len(rs)) * 10).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        return int(m)

    valoracion = None
    if len(contadas) >= max(1, n_min):
        valoracion = {"media_decimas": media_decimas(contadas), "n": len(contadas), "fuente": fuente_valoracion[:120], "al": hoy.isoformat()}
    publicables: list[dict[str, Any]] = []
    revision: list[dict[str, Any]] = []
    for r in autorizadas_o_no:
        p = r.get("permiso") if isinstance(r.get("permiso"), dict) else {}
        texto = r.get("texto")
        if not (p.get("texto") is True and p.get("version_texto") and p.get("dado_en") and isinstance(texto, str) and texto.strip()):
            continue
        normal = re.sub(r"[ \t]+", " ", texto.replace("\r\n", "\n")).strip()
        base = {"resena_id": r.get("resena_id"), "compra_id": r["checkout_session_id"], "estrellas": r["estrellas"], "locale": r.get("locale"),
                "recibida_en": r.get("recibida_en"), "autor": (r.get("autor_visible") if p.get("nombre") is True else None),
                "texto": normal, "consentimiento_ref": f"permiso:{r.get('resena_id')}:{p['version_texto']}"}
        riesgos = senales_de_riesgo(normal)
        if riesgos:
            revision.append({**base, "senales": riesgos})
        else:
            publicables.append(base)
    todas = [r for r in autorizadas_o_no]
    m_todas, m_contadas = media_decimas(todas), media_decimas(contadas)
    return {
        "oferta_id": oferta_id,
        "al": hoy.isoformat(),
        "recibidas": len(resenas),
        "verificadas_y_vigentes": len(autorizadas_o_no),
        "cuentan": len(contadas),
        "valoracion": valoracion,
        "descartadas": descartadas,
        "publicables": publicables,
        "requieren_revision_humana": revision,
        "distribucion_todas_las_verificadas": dist(todas),
        "distribucion_que_cuentan": dist(contadas),
        "distribucion_publicables": dist([{"estrellas": p["estrellas"]} for p in publicables]),
        "media_decimas_todas_las_verificadas": m_todas,
        "brecha_de_autorizacion_decimas": (m_contadas - m_todas) if (m_todas is not None and m_contadas is not None) else None,
    }


def cargar_jsonl(ruta: Path) -> list[dict[str, Any]]:
    filas: list[dict[str, Any]] = []
    for i, linea in enumerate(ruta.read_text(encoding="utf-8").splitlines(), 1):
        if not linea.strip():
            continue
        try:
            fila = json.loads(linea)
        except json.JSONDecodeError as exc:
            raise ErrorD10(f"{ruta.name}:{i}: JSON inválido ({exc.msg})") from exc
        if not isinstance(fila, dict):
            raise ErrorD10(f"{ruta.name}:{i}: cada línea debe ser un objeto")
        filas.append(fila)
    return filas


def construir_prueba_social(resenas: Sequence[Mapping[str, Any]], *, oferta_id: str, hoy: date, ahora: str | None = None,
                            ventas: tuple[int, str] | None = None, descargas: tuple[int, str] | None = None, n_min: int = 1,
                            fuente_valoracion: str = "Reseñas de compradores verificados, con su permiso",
                            permitir_sinteticos: bool = False) -> tuple[dict[str, Any], dict[str, Any]]:
    """``(prueba_social_real, informe)``. ``ventas``/``descargas`` son ``(total, fuente)`` que entrega el código (Stripe, registro de descargas): este script no los inventa."""
    informe = evaluar_resenas(resenas, oferta_id=oferta_id, hoy=hoy, n_min=n_min, fuente_valoracion=fuente_valoracion, permitir_sinteticos=permitir_sinteticos)
    doc: dict[str, Any] = {"schema_version": "0.1.0", "oferta_id": oferta_id, "generado_en": ahora or f"{hoy.isoformat()}T00:00:00Z"}
    if ventas is not None:
        doc["ventas"] = {"total": ventas[0], "fuente": ventas[1], "al": hoy.isoformat()}
    if descargas is not None:
        doc["descargas_muestra"] = {"total": descargas[0], "fuente": descargas[1], "al": hoy.isoformat()}
    if informe["valoracion"]:
        doc["valoracion"] = informe["valoracion"]
    errores, _ = validar_prueba_social(doc, oferta_id=oferta_id, hoy=hoy, resenas_informe=informe)
    if errores:
        raise ErrorD10("el resultado no pasa la validación: " + " | ".join(errores))
    return doc, informe


# ----------------------------------------------------------------------------------------------------------------------
# Correos desde plantillas, con escape
# ----------------------------------------------------------------------------------------------------------------------
CAMPOS: dict[str, tuple[str, int]] = {
    "marca": ("linea", 80), "producto": ("linea", 120), "pedido_ref": ("ref", 40), "vendedor": ("linea", 300), "soporte_email": ("email", 120),
    "politica_url": ("url", 300), "enlace_descarga": ("url", 600), "baja_url": ("url", 600), "lista_enlaces": ("lista", 4000),
    "vence_dias": ("int", 0), "max_descargas": ("int", 0), "garantia_dias": ("int", 0), "primer_paso": ("linea", 240),
    "aviso_ia": ("parrafo", 400), "bloque_renuncia": ("parrafo", 900), "garantia_texto": ("parrafo", 700), "ayuda_pais": ("parrafo", 500), "descriptor": ("linea", 40), "monto_texto": ("linea", 40), "tiempo_reembolso": ("linea", 160),
    "resena_url_1": ("url", 600), "resena_url_2": ("url", 600), "resena_url_3": ("url", 600), "resena_url_4": ("url", 600), "resena_url_5": ("url", 600),
}
OPCIONALES = {"bloque_renuncia", "aviso_ia"}  # pueden faltar o ir vacíos; el resto de los campos de la plantilla son obligatorios
TIPOS = ("entrega", "resena", "reembolso", "soporte")
REQUERIDOS_POR_TIPO: dict[str, set[str]] = {
    "entrega": {"pedido_ref", "vence_dias", "max_descargas", "garantia_dias", "garantia_texto", "primer_paso", "bloque_renuncia"},
    "resena": {"baja_url", "resena_url_1", "resena_url_2", "resena_url_3", "resena_url_4", "resena_url_5"},
    "reembolso": {"pedido_ref", "monto_texto", "tiempo_reembolso"},
    "soporte": set(),
}
IDENTIDAD = {"vendedor", "soporte_email", "politica_url"}

# Presión para opinar bien (aplica a TODO correo) e incentivos materiales (aplican a la petición de reseña y al soporte). Minúsculas; lista cerrada por idioma,
# ampliar con X1 al abrir un idioma.
PRESION_NOTA = (
    "5 estrellas", "cinco estrellas", "five stars", "5 stars", "5 gwiazdek", "pięć gwiazdek", "5 stelle",
    "solo opiniones positivas", "only positive", "tylko pozytywn", "ayúdanos con una buena", "help us with a good", "pomóż nam dobrą",
)
INCENTIVO_MATERIAL = (
    "descuento", "cupón", "cupon", "regalo", "gratis", "sorteo", "bonus", "recompensa", "a cambio de",
    "discount", "coupon", "free gift", "reward", "giveaway", "in exchange for",
    "rabat", "zniżk", "kupon", "prezent", "nagrod", "w zamian za", "darmow", "konkurs",
    "sconto", "omaggio", "premio", "in cambio di",
)
URGENCIA = ("solo hoy", "últimas horas", "ahora mismo", "date prisa", "hurry", "last chance", "limited time", "tylko dzisiaj", "tylko dziś", "pilne", "ostatnia szansa", "affrettati")
PROMOCION = ("oferta especial", "special offer", "oferta specjalna", "nuevo producto", "new product", "nowy produkt", "compra ahora", "buy now", "kup teraz", "upgrade", "cross-sell")


def parsear_plantilla(texto: str) -> dict[str, Any]:
    """``{"meta": {...}, "asunto": str, "cuerpo": str}``. Formato: líneas ``# clave: valor``, luego ``Asunto: …``, una línea en blanco y el cuerpo."""
    lineas = texto.replace("\r\n", "\n").split("\n")
    meta: dict[str, str] = {}
    i = 0
    while i < len(lineas) and lineas[i].startswith("#"):
        m = re.match(r"^#\s*([a-z_]+)\s*:\s*(.*)$", lineas[i])
        if m:
            meta[m.group(1)] = m.group(2).strip()
        i += 1
    if i >= len(lineas) or not lineas[i].startswith("Asunto:"):
        raise ErrorD10("la plantilla debe tener una línea «Asunto: …» tras los metadatos")
    asunto = lineas[i][len("Asunto:"):].strip()
    i += 1
    if i < len(lineas) and lineas[i].strip() == "":
        i += 1
    return {"meta": meta, "asunto": asunto, "cuerpo": "\n".join(lineas[i:]).strip("\n")}


def _validar_url(valor: Any, dominios: Sequence[str] | None, campo: str) -> str:
    if not isinstance(valor, str) or not valor:
        raise ErrorD10(f"{campo}: debe ser una URL (texto)")
    if re.search(r"[\s<>\"'`\\]", valor) or any(unicodedata.category(c) in ("Cc", "Cf", "Zl", "Zp") for c in valor):
        raise ErrorD10(f"{campo}: la URL contiene espacios, comillas, controles o marcas de dirección")
    partes = urlsplit(valor)
    if partes.scheme != "https" or not partes.hostname:
        raise ErrorD10(f"{campo}: solo https con host (se recibió {valor[:40]!r})")
    if "@" in partes.netloc:
        raise ErrorD10(f"{campo}: la URL no puede llevar usuario ni contraseña")
    host = partes.hostname.lower()
    if dominios and not any(host == d.lower() or host.endswith("." + d.lower()) for d in dominios):
        raise ErrorD10(f"{campo}: el host {host!r} no está entre los dominios permitidos {list(dominios)}")
    return valor


def normalizar_valores(datos: Mapping[str, Any], *, dominios: Sequence[str] | None = None) -> dict[str, Any]:
    """Valida y sanea los datos de un correo. Devuelve el valor ya limpio de cada campo (listas de enlaces como lista de pares). Campo fuera de ``CAMPOS`` = error."""
    desconocidos = sorted(set(datos) - set(CAMPOS))
    if desconocidos:
        raise ErrorD10(f"campos no admitidos {desconocidos}: el correo usa datos personales mínimos (solo {sorted(CAMPOS)})")
    limpio: dict[str, Any] = {}
    for campo, valor in datos.items():
        tipo, tope = CAMPOS[campo]
        if tipo == "int":
            if not (_es_entero(valor) and 1 <= valor <= 9999):
                raise ErrorD10(f"{campo}: debe ser un entero entre 1 y 9999")
            limpio[campo] = valor
        elif tipo == "ref":
            if not (isinstance(valor, str) and RX_REF.match(valor)):
                raise ErrorD10(f"{campo}: referencia inválida (4-40 caracteres A-Z a-z 0-9 _ -)")
            limpio[campo] = valor
        elif tipo == "email":
            if not (isinstance(valor, str) and re.match(r"^[^@\s<>\"',;]+@[^@\s<>\"',;]+\.[^@\s<>\"',;]+$", valor) and len(valor) <= tope):
                raise ErrorD10(f"{campo}: correo inválido")
            limpio[campo] = valor
        elif tipo == "url":
            limpio[campo] = _validar_url(valor, dominios, campo)
        elif tipo in ("linea", "parrafo"):
            if not isinstance(valor, str):
                raise ErrorD10(f"{campo}: debe ser texto")
            texto = _limpiar(valor, multilinea=(tipo == "parrafo"))
            if len(texto) > tope:
                raise ErrorD10(f"{campo}: supera {tope} caracteres")
            limpio[campo] = texto
        elif tipo == "lista":
            if not (isinstance(valor, list) and 1 <= len(valor) <= 8):
                raise ErrorD10(f"{campo}: debe ser una lista de 1 a 8 {{nombre, enlace}}")
            items = []
            for i, it in enumerate(valor):
                if not (isinstance(it, dict) and set(it) == {"nombre", "enlace"}):
                    raise ErrorD10(f"{campo}[{i}]: debe tener exactamente nombre y enlace")
                nombre = _limpiar(str(it["nombre"]), multilinea=False)
                if not nombre or len(nombre) > 120:
                    raise ErrorD10(f"{campo}[{i}].nombre vacío o de más de 120 caracteres")
                items.append((nombre, _validar_url(it["enlace"], dominios, f"{campo}[{i}].enlace")))
            limpio[campo] = items
    return limpio


def _a_texto(campo: str, valor: Any) -> str:
    if CAMPOS[campo][0] == "lista":
        return "\n".join(f"· {n} — {u}" for n, u in valor)
    return str(valor)


def _a_html(campo: str, valor: Any) -> str:
    tipo = CAMPOS[campo][0]
    if tipo == "lista":
        return "\n".join(f'· {html.escape(n)} — <a href="{html.escape(u, quote=True)}">{html.escape(u)}</a>' for n, u in valor)
    if tipo == "url":
        return f'<a href="{html.escape(valor, quote=True)}">{html.escape(valor)}</a>'
    return html.escape(str(valor), quote=True)  # los saltos de línea se convierten en <br> y <p> una sola vez, al armar el cuerpo


def renderizar(plantilla: str, datos: Mapping[str, Any], *, dominios: Sequence[str] | None = None, formato: str = "texto") -> dict[str, str]:
    """Expande una plantilla en una sola pasada (un valor nunca se vuelve a expandir). ``formato``: ``texto``, ``html`` o ``ambos``. Lanza ``ErrorD10`` si falta un dato o sobra un campo."""
    if formato not in ("texto", "html", "ambos"):
        raise ErrorD10("formato debe ser texto, html o ambos")
    p = parsear_plantilla(plantilla)
    valores = normalizar_valores(datos, dominios=dominios)
    usados = set(RX_PLACEHOLDER.findall(p["asunto"] + "\n" + p["cuerpo"]))
    for u in sorted(usados):
        if u not in CAMPOS:
            raise ErrorD10(f"la plantilla usa {{{{{u}}}}}, que no es un campo admitido")
        if u not in valores and u not in OPCIONALES:
            raise ErrorD10(f"falta el dato {u!r} que pide la plantilla")
    for u in set(re.findall(r"\{\{\s*([a-z][a-z0-9_]*)\s*\}\}", p["asunto"])):
        if CAMPOS[u][0] in ("url", "lista", "parrafo", "email"):
            raise ErrorD10(f"el asunto no puede llevar {u!r} (enlaces y bloques van en el cuerpo)")

    def sustituir(conv):
        def f(m: re.Match[str]) -> str:
            campo = m.group(1)
            return conv(campo, valores[campo]) if campo in valores else ""
        return f

    asunto = _limpiar(RX_PLACEHOLDER.sub(sustituir(lambda c, v: _a_texto(c, v)), p["asunto"]), multilinea=False)
    if len(asunto) > 90:
        raise ErrorD10(f"el asunto resuelto mide {len(asunto)} caracteres (máximo 90)")
    cuerpo_texto = RX_PLACEHOLDER.sub(sustituir(lambda c, v: _a_texto(c, v)), p["cuerpo"])
    cuerpo_texto = re.sub(r"\n{3,}", "\n\n", cuerpo_texto).strip() + "\n"
    salida = {"asunto": asunto}
    if formato in ("texto", "ambos"):
        salida["texto"] = cuerpo_texto
    if formato in ("html", "ambos"):
        # Se escapa también el texto fijo de la plantilla; los valores se escapan por campo y se sustituyen en una sola pasada.
        marcadores: dict[str, str] = {}

        def marcar(m: re.Match[str]) -> str:
            campo = m.group(1)
            clave = f"\u0000{len(marcadores)}\u0000"
            marcadores[clave] = _a_html(campo, valores[campo]) if campo in valores else ""
            return clave

        esqueleto = RX_PLACEHOLDER.sub(marcar, p["cuerpo"])
        esqueleto = html.escape(esqueleto, quote=False)
        for clave, frag in marcadores.items():
            esqueleto = esqueleto.replace(clave, frag)
        parrafos = [x for x in re.split(r"\n{2,}", esqueleto) if x.strip()]
        cuerpo_html = "\n".join("<p>" + x.strip().replace("\n", "<br>\n") + "</p>" for x in parrafos)
        salida["html"] = f'<!doctype html><html><body>{cuerpo_html}</body></html>\n'
    return salida


def lint_plantilla(plantilla: str, *, neutro: bool = True) -> list[dict[str, str]]:
    """Hallazgos ``{codigo, severidad, detalle}`` de una plantilla (vacío = limpia)."""
    h: list[dict[str, str]] = []

    def add(codigo: str, sev: str, detalle: str) -> None:
        h.append({"codigo": codigo, "severidad": sev, "detalle": detalle})

    try:
        p = parsear_plantilla(plantilla)
    except ErrorD10 as exc:
        return [{"codigo": "formato", "severidad": "BLOQUEANTE", "detalle": str(exc)}]
    tipo = p["meta"].get("tipo")
    if tipo not in TIPOS:
        add("tipo_invalido", "BLOQUEANTE", f"# tipo: debe ser uno de {list(TIPOS)} (hay {tipo!r})")
        tipo = None
    if "locale" not in p["meta"]:
        add("locale_ausente", "MAYOR", "falta «# locale: xx-XX»")
    usados = set(RX_PLACEHOLDER.findall(p["asunto"] + "\n" + p["cuerpo"]))
    for u in sorted(usados - set(CAMPOS)):
        add("campo_desconocido", "BLOQUEANTE", f"{{{{{u}}}}} no es un campo admitido")
    for faltante in sorted(IDENTIDAD - usados):
        add("identidad_del_vendedor", "BLOQUEANTE", f"falta {{{{{faltante}}}}} (vendedor identificable, soporte y política en todo correo)")
    if tipo:
        for faltante in sorted(REQUERIDOS_POR_TIPO[tipo] - usados):
            add("campo_requerido", "BLOQUEANTE", f"un correo de tipo {tipo} debe usar {{{{{faltante}}}}}")
        if tipo == "entrega" and not ({"lista_enlaces", "enlace_descarga"} & usados):
            add("campo_requerido", "BLOQUEANTE", "el correo de entrega debe llevar {{lista_enlaces}} o {{enlace_descarga}}")
    asunto_campos = set(RX_PLACEHOLDER.findall(p["asunto"]))
    if len(p["asunto"]) > 120:
        add("asunto_largo", "MENOR", "el asunto sin expandir supera 120 caracteres")
    if neutro and ({"producto", "primer_paso"} & asunto_campos):
        add("asunto_no_neutro", "BLOQUEANTE", "el asunto no debe nombrar el producto ni describir al lector (salud, relaciones, dinero): usa la marca y el pedido")
    if asunto_campos & {c for c, (t, _) in CAMPOS.items() if t in ("url", "lista", "parrafo", "email")}:
        add("asunto_con_bloque", "BLOQUEANTE", "el asunto no puede llevar enlaces ni bloques")
    completo = (p["asunto"] + "\n" + p["cuerpo"]).lower()
    for termino in PRESION_NOTA:
        if termino in completo:
            add("incentivo", "BLOQUEANTE", f"«{termino}»: nada de pedir una nota concreta ni solo opiniones positivas (reseñas reales y neutrales)")
    if tipo in ("resena", "soporte"):
        for termino in INCENTIVO_MATERIAL:
            if termino in completo:
                add("incentivo", "BLOQUEANTE", f"«{termino}»: nada de recompensas, descuentos ni regalos a cambio de opinar (reseñas reales y neutrales)")
    for termino in URGENCIA:
        if termino in completo:
            add("urgencia", "MAYOR", f"«{termino}»: sin urgencia ni escasez en correos de poscompra")
    if tipo in ("entrega", "resena", "reembolso", "soporte"):
        for termino in PROMOCION:
            if termino in completo:
                add("promocion_en_transaccional", "BLOQUEANTE", f"«{termino}»: el correo transaccional y la petición de reseña no llevan promoción")
    if any(ord(c) > 0x1F000 or unicodedata.category(c) == "So" for c in completo):
        add("emoji", "MENOR", "sin emoji en el correo de marca (convención del mercado)")
    if "!!" in completo:
        add("exclamaciones", "MENOR", "sin exclamaciones repetidas")
    if tipo == "resena":
        estrellas = {u for u in usados if u.startswith("resena_url_")}
        if len(estrellas) != 5:
            add("resena_cinco_enlaces", "BLOQUEANTE", "la petición de reseña lleva los cinco enlaces de estrellas, sin privilegiar ninguno")
        if re.search(r"(?i)(si te (ha )?gust[óo]|if you (liked|enjoyed)|jeśli (ci się )?spodoba[łl]o|se ti [èe] piaciut)", completo):
            add("resena_condicionada", "MAYOR", "no condiciones la petición a que le haya gustado: se pide a todos igual")
    if tipo == "entrega" and "bloque_renuncia" not in usados:
        add("renuncia_sin_confirmar", "BLOQUEANTE", "E0 debe confirmar la renuncia (UE/UK) con {{bloque_renuncia}}")
    return h


# ----------------------------------------------------------------------------------------------------------------------
# Entrega por línea
# ----------------------------------------------------------------------------------------------------------------------
LINEAS = ("principal", "bump", "upsell", "postpago")


def linea_de_item(item: Mapping[str, Any], oferta: Mapping[str, Any]) -> str:
    """Línea a la que pertenece un ítem de ``producto.json``: ``item.linea`` (campo PROPUESTO) o, si no existe, ``bump`` cuando su id es el de ``oferta.bump``; si no, ``principal``."""
    if "linea" in item:
        if item["linea"] not in LINEAS:
            raise ErrorD10(f"ítem {item.get('id')!r}: linea {item['linea']!r} desconocida")
        return str(item["linea"])
    bump = oferta.get("bump") or {}
    return "bump" if bump and item.get("id") == bump.get("id") else "principal"


def plan_entrega(oferta: Mapping[str, Any], producto: Mapping[str, Any], lineas_pagadas: Sequence[str]) -> dict[str, Any]:
    """Qué archivos se entregan según las líneas realmente pagadas de la sesión. Nunca entrega un ítem de una línea no pagada."""
    pagadas = list(dict.fromkeys(lineas_pagadas))
    for ln in pagadas:
        if ln not in LINEAS:
            raise ErrorD10(f"línea desconocida {ln!r}")
    if "principal" not in pagadas:
        raise ErrorD10("toda sesión paga la línea principal")
    por_linea: dict[str, list[dict[str, str]]] = {ln: [] for ln in LINEAS}
    for item in producto.get("items", []):
        if item.get("en_paquete") is not True:
            continue
        if not item.get("sha256"):
            raise ErrorD10(f"ítem {item.get('id')!r} sin sha256: no se entrega algo que QA no vio")
        por_linea[linea_de_item(item, oferta)].append({"id": item["id"], "archivo": item["archivo"], "sha256": item["sha256"]})
    entregar: list[dict[str, str]] = []
    for ln in pagadas:
        if not por_linea[ln]:
            raise ErrorD10(f"la línea {ln!r} está pagada pero no tiene archivos en producto.json (en_paquete=true): se rechaza la entrega y se avisa")
        entregar += [{**f, "linea": ln} for f in por_linea[ln]]
    no_entregar = [{**f, "linea": ln} for ln in LINEAS if ln not in pagadas for f in por_linea[ln]]
    return {"lineas_pagadas": pagadas, "entregar": entregar, "no_entregar": no_entregar}


# ----------------------------------------------------------------------------------------------------------------------
# Órdenes del Maker al código
# ----------------------------------------------------------------------------------------------------------------------
ACCIONES_ORDEN = ("reembolsar", "reenviar_entrega", "escalar_humano", "descartar")
MOTIVOS_REEMBOLSO = ("dentro_de_garantia", "producto_no_recibido", "duplicado", "fraude", "otro")
CATEGORIAS = tuple(f"C{i}" for i in range(1, 11))


def validar_orden(orden: Any) -> list[str]:
    """Errores de una orden. La orden SOLICITA; el código decide, aplica los topes y ejecuta. Nunca lleva importes, destinatarios ni «forzar»."""
    if not isinstance(orden, dict):
        return ["la orden debe ser un objeto"]
    err: list[str] = []
    permitidas = {"accion", "checkout_session_id", "motivo", "categoria", "mensaje_ref", "nota"}
    for k in sorted(orden):
        if SECRETOS_PROHIBIDOS_EN_ORDEN.search(k):
            err.append(f"clave prohibida {k!r}: el Maker no fija importes, destinatarios, claves ni excepciones; lo decide y ejecuta el código")
        elif k not in permitidas:
            err.append(f"clave no admitida {k!r}")
    accion = orden.get("accion")
    if accion not in ACCIONES_ORDEN:
        err.append(f"accion debe ser una de {list(ACCIONES_ORDEN)}")
    if orden.get("categoria") is not None and orden.get("categoria") not in CATEGORIAS:
        err.append("categoria debe ser C1..C10")
    if accion in ("reembolsar", "reenviar_entrega"):
        if not (isinstance(orden.get("checkout_session_id"), str) and RX_SESION.match(orden["checkout_session_id"])):
            err.append("checkout_session_id debe tener la forma cs_…")
    if accion == "reembolsar" and orden.get("motivo") not in MOTIVOS_REEMBOLSO:
        err.append(f"reembolsar exige motivo en {list(MOTIVOS_REEMBOLSO)} (contrato reembolso)")
    if accion == "escalar_humano" and orden.get("categoria") not in ("C4", "C5", "C6", "C7", "C8"):
        err.append("escalar_humano exige categoria C4..C8")
    if accion == "descartar" and orden.get("categoria") != "C10":
        err.append("descartar solo vale para C10 (abuso o spam)")
    if "mensaje_ref" not in orden or not (isinstance(orden.get("mensaje_ref"), str) and RX_REF.match(orden["mensaje_ref"])):
        err.append("mensaje_ref obligatorio (identificador del mensaje en la bandeja; nunca su texto)")
    nota = orden.get("nota")
    if nota is not None and (not isinstance(nota, str) or len(nota) > 200 or texto_hostil(nota)):
        err.append("nota: texto de hasta 200 caracteres sin marcado ni controles")
    return err


# ----------------------------------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------------------------------
def _cargar_json(ruta: str) -> Any:
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ErrorD10(f"no existe {ruta}") from exc
    except json.JSONDecodeError as exc:
        raise ErrorD10(f"{ruta}: JSON inválido ({exc.msg}, línea {exc.lineno})") from exc


def _salida(args: argparse.Namespace, datos: Mapping[str, Any], texto: str) -> None:
    print(json.dumps(datos, ensure_ascii=False, indent=2, sort_keys=True) if args.json else texto)


def _escribir_json(ruta: str, doc: Mapping[str, Any]) -> None:
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="d10.py", description=__doc__.split("\n")[0])
    comun = argparse.ArgumentParser(add_help=False)
    comun.add_argument("--json", action="store_true", help="salida JSON")
    sub = ap.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validar-prueba-social", parents=[comun])
    v.add_argument("--archivo", required=True)
    v.add_argument("--oferta-id")
    v.add_argument("--hoy")
    v.add_argument("--resenas", help="resenas.jsonl para cruzar la valoración")
    v.add_argument("--permitir-sinteticos", action="store_true", help="SOLO para evals y pruebas")

    c = sub.add_parser("construir-prueba-social", parents=[comun])
    c.add_argument("--resenas", required=True)
    c.add_argument("--oferta-id", required=True)
    c.add_argument("--hoy", required=True)
    c.add_argument("--ahora", help="AAAA-MM-DDThh:mm:ssZ (por defecto hoy a las 00:00:00Z)")
    c.add_argument("--ventas", type=int)
    c.add_argument("--ventas-fuente")
    c.add_argument("--descargas", type=int)
    c.add_argument("--descargas-fuente")
    c.add_argument("--n-min", type=int, default=1)
    c.add_argument("--permitir-sinteticos", action="store_true", help="SOLO para evals y pruebas: acepta reseñas marcadas sintetico=true (nunca para producción)")
    c.add_argument("--salida", help="ruta de prueba_social_real.json")
    c.add_argument("--informe", help="ruta del informe de reseñas (publicables, revisión, descartes)")

    r = sub.add_parser("correo", parents=[comun])
    r.add_argument("--plantilla", required=True)
    r.add_argument("--datos", required=True)
    r.add_argument("--dominios", default="", help="dominios permitidos para los enlaces, separados por coma")
    r.add_argument("--formato", default="texto", choices=["texto", "html", "ambos"])

    lp = sub.add_parser("lint-plantilla", parents=[comun])
    lp.add_argument("--plantilla", required=True, nargs="+")
    lp.add_argument("--no-neutro", action="store_true", help="permite el producto en el asunto (solo macro-nichos sin tema sensible)")

    pe = sub.add_parser("plan-entrega", parents=[comun])
    pe.add_argument("--oferta", required=True)
    pe.add_argument("--producto", required=True)
    pe.add_argument("--lineas", required=True, help="líneas pagadas, separadas por coma (principal,bump)")

    vo = sub.add_parser("validar-orden", parents=[comun])
    vo.add_argument("--orden", required=True)

    args = ap.parse_args(argv)
    try:
        if args.cmd == "validar-prueba-social":
            doc = _cargar_json(args.archivo)
            hoy = _parse_hoy(args.hoy)
            informe = None
            if args.resenas:
                informe = evaluar_resenas(cargar_jsonl(Path(args.resenas)), oferta_id=args.oferta_id or doc.get("oferta_id", ""), hoy=hoy,
                                          permitir_sinteticos=args.permitir_sinteticos)
            errores, avisos = validar_prueba_social(doc, oferta_id=args.oferta_id, hoy=hoy, resenas_informe=informe)
            _salida(args, {"ok": not errores, "errores": errores, "avisos": avisos},
                    ("OK" if not errores else "ERRORES:\n- " + "\n- ".join(errores)) + ("\nAVISOS:\n- " + "\n- ".join(avisos) if avisos else ""))
            return 0 if not errores else 3
        if args.cmd == "construir-prueba-social":
            hoy = _parse_hoy(args.hoy)
            ventas = (args.ventas, args.ventas_fuente) if args.ventas is not None else None
            descargas = (args.descargas, args.descargas_fuente) if args.descargas is not None else None
            if (ventas and not ventas[1]) or (descargas and not descargas[1]):
                raise ErrorD10("ventas y descargas exigen su --…-fuente (de dónde sale el número)")
            doc, informe = construir_prueba_social(cargar_jsonl(Path(args.resenas)), oferta_id=args.oferta_id, hoy=hoy, ahora=args.ahora,
                                                   ventas=ventas, descargas=descargas, n_min=args.n_min,
                                                   permitir_sinteticos=args.permitir_sinteticos)
            if args.salida:
                _escribir_json(args.salida, doc)
            if args.informe:
                _escribir_json(args.informe, informe)
            _salida(args, {"ok": True, "prueba_social_real": doc, "informe": informe},
                    f"prueba_social_real: valoración {'sí' if 'valoracion' in doc else 'no'}; cuentan {informe['cuentan']}; publicables {len(informe['publicables'])}; "
                    f"a revisión humana {len(informe['requieren_revision_humana'])}; descartadas {len(informe['descartadas'])}")
            return 0
        if args.cmd == "correo":
            doms = [d.strip() for d in args.dominios.split(",") if d.strip()]
            res = renderizar(Path(args.plantilla).read_text(encoding="utf-8"), _cargar_json(args.datos), dominios=doms or None, formato=args.formato)
            _salida(args, res, "ASUNTO: " + res["asunto"] + "\n\n" + res.get("texto", res.get("html", "")))
            return 0
        if args.cmd == "lint-plantilla":
            todo: dict[str, list[dict[str, str]]] = {}
            for ruta in args.plantilla:
                todo[ruta] = lint_plantilla(Path(ruta).read_text(encoding="utf-8"), neutro=not args.no_neutro)
            hay = any(x["severidad"] in ("BLOQUEANTE", "MAYOR") for hs in todo.values() for x in hs)
            _salida(args, {"ok": not hay, "hallazgos": todo},
                    "\n".join(f"{ruta}: {'limpia' if not hs else ''}" + "".join(f"\n  [{x['severidad']}] {x['codigo']}: {x['detalle']}" for x in hs) for ruta, hs in todo.items()))
            return 0 if not hay else 3
        if args.cmd == "plan-entrega":
            res = plan_entrega(_cargar_json(args.oferta), _cargar_json(args.producto), [x.strip() for x in args.lineas.split(",") if x.strip()])
            _salida(args, res, "entregar: " + ", ".join(f"{x['linea']}:{x['id']}" for x in res["entregar"]) + "\nno entregar: " + (", ".join(f"{x['linea']}:{x['id']}" for x in res["no_entregar"]) or "—"))
            return 0
        if args.cmd == "validar-orden":
            errores = validar_orden(_cargar_json(args.orden))
            _salida(args, {"ok": not errores, "errores": errores}, "OK" if not errores else "ERRORES:\n- " + "\n- ".join(errores))
            return 0 if not errores else 3
    except ErrorD10 as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    return 2


if __name__ == "__main__":
    sys.exit(main())
