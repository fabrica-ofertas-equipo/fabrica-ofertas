#!/usr/bin/env python3
"""Lint determinista MÍNIMO del `copy.json` de D5. Sin red, solo biblioteca estándar.

Es una red de seguridad del Maker (antes de generar) y del QA (evals sembrados); NO sustituye a
`compliance.lint_claims` / `html_checks` (B6) ni a `landing.validar` (B4), que son la fuente de verdad en producción.

Uso:
    python3 lint_copy.py --copy COPY.json [--oferta OFERTA.json] [--mercado MERCADO.json] [--assets ASSETS.json] [--json]

Salida: `hallazgos[]` con {check_id, regla, severidad, ruta, texto, detalle}; código 0 si no hay BLOQUEANTE ni MAYOR,
3 si los hay, 2 por uso incorrecto. Severidades de backbone 5.4. Los límites de longitud son [HIPÓTESIS] a calibrar.
Reglas y su mapa a los checks C01-C17: references/checks-c01-c17.md.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any, Iterator

# ---------------------------------------------------------------------------------------------- estructura
SECCIONES_OBLIGATORIAS = ("S01", "S03", "S05", "S06", "S07", "S10", "S11", "S12", "S14")
SECCIONES_OMITIBLES = ("S02", "S04", "S08", "S09", "S13")
# Plano «referente» (copy ≥ 0.2.0 o `estructura: referente`): sin S02/S03/S05; S15 (cómo lo recibes) y S16 (comparación con el mercado) son opcionales y no exigen registro en `omitidas`.
SECCIONES_OBLIGATORIAS_REFERENTE = ("S01", "S06", "S07", "S10", "S11", "S12", "S14")
SECCIONES_OMITIBLES_REFERENTE = ("S04", "S08", "S09", "S13")
SECCIONES_FUERA_DEL_REFERENTE = ("S02", "S03", "S05")
RX_FECHA = re.compile(r"^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$")
BLOQUES_APARTE = ("banner", "comprar", "gracias")
PLACEHOLDERS = {
    "precio", "precio_bump", "moneda", "garantia_dias", "tiempo_min", "marca", "producto", "bump_nombre",
    "bump_descripcion", "vence_dias", "max_descargas", "n", "paginas", "formato", "ia_divulgacion", "ayuda_pais",
    "fecha_lanzamiento", "precio_despues",       # solo en barra_superior.lanzamiento.texto (el generador los expande si checkout.json trae precio_programado)
}
# Longitud típica (caracteres) con la que se mide un texto cuando lleva placeholder (los expande el generador).
LONGITUD_PLACEHOLDER = {
    "precio": 8, "precio_bump": 8, "moneda": 3, "garantia_dias": 2, "tiempo_min": 3, "marca": 20, "producto": 30,
    "bump_nombre": 50, "bump_descripcion": 70, "vence_dias": 2, "max_descargas": 2, "n": 2, "paginas": 3, "formato": 12,
    "ia_divulgacion": 110, "ayuda_pais": 90, "fecha_lanzamiento": 18, "precio_despues": 8,
}
RX_PLACEHOLDER = re.compile(r"\{([a-z_]+)(?::([a-z0-9_-]+))?\}")

# Límites de longitud en caracteres por clave (se aplican a cualquier ruta que termine en ella). [HIPÓTESIS]
LIMITES = {
    "S01.kicker": 40, "S01.h1": 70, "S01.h1_resaltado": 40, "S01.subtitulo": 160, "S01.microcopy": 90,
    "S03.titulo": 90, "S03.reencuadre": 120,
    "S05.nombre": 60, "S05.como_funciona": 200, "S05.de_a_b": 120,
    "S10.titulo": 70, "S10.texto": 220, "S10.nota_legal": 160,
    "S11.titulo": 80, "S11.descripcion": 120, "S11.linea_precio": 70,
    "S12.q": 90, "S12.a": 280, "S13.titulo": 90, "S14.descripcion": 120, "S14.aviso": 200,
    "banner.texto": 200, "cta.texto": 32, "meta.title": 65, "meta.description": 160,
}
# Claves de lista con límite por elemento.
LIMITES_ELEMENTO = {
    "S01.pills": 24, "S02.etiqueta": 20, "S02.titulo": 28, "S02.texto": 110, "S03.dolores": 140,
    "S04.texto": 90, "S05.etiquetas": 22, "S06.titulo": 50, "S06.temas": 30, "S06.etiqueta": 22, "S07.titulo": 50, "S07.texto": 150, "S15.titulo": 50, "S15.texto": 120, "S06.texto": 140, "S06.items": 80,
    "S07.si": 90, "S07.no": 90, "S09.nombre": 50, "S09.texto": 120, "S11.incluye": 70, "S11.pills": 24,
}

# ---------------------------------------------------------------------------------------------- patrones
# Se aplican sobre el texto «plano» (minúsculas, sin tildes, ł→l). Mínimo viable multi-idioma.
CONTADORES = [
    r"\bquedan?\s+\d+", r"\bultim[oa]s?\s+\d+", r"\d+\s+personas?\s+(viendo|comprando|mirando|han comprado|compraron)",
    r"viendo\s+ahora", r"cuenta\s+regresiva", r"\bcupos?\b", r"plazas?\s+limitadas", r"solo\s+(por\s+)?hoy",
    r"oferta\s+(termina|finaliza|vence)", r"stock\s+limitado", r"se\s+agota(n)?\s+(el\s+stock|las\s+unidades|rapido|pronto)",
    r"only\s+\d+\s+(left|remaining|spots)", r"\d+\s+(people|others)\s+(are\s+)?(viewing|watching|buying)", r"countdown",
    r"limited\s+(time|spots|stock|offer)", r"today\s+only", r"offer\s+ends", r"selling\s+fast", r"last\s+chance",
    r"solo\s+\d+\s+(posti|rimast)", r"ultimi\s+\d+", r"solo\s+oggi", r"offerta\s+limitata", r"posti\s+limitati",
    r"conto\s+alla\s+rovescia", r"zostalo\s+(tylko\s+)?\d+", r"ostatnie\s+(sztuki|miejsca)", r"tylko\s+dzis",
    r"ograniczona\s+(oferta|liczba)", r"odliczanie", r"il\s+reste\s+\d+", r"derni[eè]res?\s+places",
    r"offre\s+limit[ée]e", r"aujourd.hui\s+seulement", r"compte\s+a\s+rebours", r"nur\s+noch\s+\d+", r"nur\s+heute",
    r"begrenzte\s+(anzahl|plaetze|angebot)", r"letzte\s+chance",
]
PROMESAS_SALUD = [
    r"\bcura(r|rte|rse|n)?\b", r"\b(sana|sanar|sanarte|revierte|revertir)\b", r"\badelgaz\w+", r"bajar\s+de\s+peso",
    r"perder\s+\d+\s*(kg|kilos|libras|lbs)", r"\b\d+\s*(kg|kilos|lbs|libras|pounds)\b.{0,25}\b(dias|semanas|mes|days|weeks|month)",
    r"\bdetox\b", r"quema(r)?\s+grasa", r"sin\s+dieta", r"\bmetabolismo\b", r"\bcortisol\b",
    r"\b(cure|heal|reverse)s?\b", r"lose\s+\d+\s*(kg|lbs|pounds)", r"burn\s+fat", r"without\s+(a\s+)?diet",
    r"\bguarisc\w+", r"perdi\s+\d+\s*kg", r"senza\s+dieta", r"\bleczy\b", r"\bcud\b", r"schudnij", r"gu[eé]rir",
    r"soulag\w+\s+d[eé]finitivement", r"\bheilt\b|\bheilen\b",
]
PROMESAS_DINERO = [
    r"\bgan[aá](r|s|rte|ras)?\s+(dinero|\$|€|\d)", r"make\s+money", r"earn\s+(\$|€|£|\d|money)",
    r"guadagna\w*\s+(\d|soldi)", r"zarabi\w+\s+\d", r"\b(ahorr[aá]\w*|save|risparmia\w*|oszczedz\w*)\s+(\$|€|£|\d)",
    r"retorno\s+garantizado", r"ingresos?\s+(garantizados?|extra|pasivos?)", r"deuda\s+cero|cero\s+deudas",
    r"borra\s+tus\s+deudas|sali\s+de\s+deudas|sal\w+\s+de\s+(tus\s+)?deudas", r"hazte\s+rico", r"ricos?\s+rapido",
    r"passive\s+income", r"libertad\s+financiera|financial\s+freedom|liberta\s+finanziaria|wolnosc\s+finansowa",
]
PROMESAS_RELACIONES = [
    r"recupera\w*\s+a\s+tu\s+ex", r"hace(r)?\s+que\s+(te|se)\s+(ame|enamore)", r"descubre\s+si\s+te\s+(enganya|engana|miente)",
    r"narcisista", r"get\s+your\s+ex\s+back", r"make\s+(him|her|them)\s+(love|fall)", r"fai\s+in\s+modo\s+che\s+si\s+innamori",
    r"odzyskaj\s+bylego",
]
GARANTIA_RESULTADO = [
    r"si\s+no\s+(consigues|logras|ahorras|bajas|adelgazas|recuperas|ganas|encuentras|consegui)",
    r"if\s+you\s+(don.?t|do\s+not)\s+(get|lose|save|earn|find|land)", r"se\s+non\s+(ottieni|risparmi|perdi|guadagni)",
    r"jesli\s+nie\s+(schudniesz|zaoszczedzisz|zarobisz)", r"si\s+vous\s+ne\s+(perdez|gagnez|[eé]conomisez)",
]
ATRIBUTO_HERO = [
    r"\bsi\s+(eres|estas|tienes|sos|tenes)\b", r"\bif\s+you\s+(are|have|'re)\b", r"\bse\s+(sei|hai)\b", r"\bjesli\s+(jestes|masz)\b",
    r"\bsi\s+tu\s+(es|as)\b", r"\bwenn\s+du\b", r"\btu\s+ex\b", r"\byour\s+ex\b", r"\bmadres?\s+(solteras?|agotadas?)\b",
    r"\b(viud[oa]|divorciad[oa]|endeudad[oa]|obes[oa]|diabetic[oa]|ansios[oa]|deprimid[oa]|gord[oa])\b",
    r"\b(inutil|insuficiente|fracasad[oa]|not\s+good\s+enough)\b", r"\bmas\s+de\s+\d{2}\b", r"\btras\s+los\s+\d{2}\b",
]
IVA_INCLUIDO = [
    r"iva\s+incluido", r"impuestos\s+incluidos", r"(tax|vat)\s+(included|incl)", r"incl\.?\s+(vat|tax)", r"iva\s+inclus[ao]|iva\s+compres[ao]",
    r"zawiera\s+vat|z\s+vat|brutto", r"tva\s+incluse|\bttc\b", r"inkl\.?\s+mwst|inklusive\s+mehrwertsteuer",
    r"\+\s*iva\b", r"plus\s+(vat|tax)", r"\+\s*vat\b",
]
CREDENCIALES = [
    r"\bcertificad[oa]s?\b", r"\bcertified\b", r"\bavalad[oa]\b", r"aprobad[oa]\s+por", r"recomendad[oa]\s+por",
    r"\b(medic[oa]|doctor|doctora|psicolog[oa]|abogad[oa]|asesor\s+financiero)\b", r"\b(expert[oa]s?|experts?)\b",
]
TESTIMONIOS = [
    r"\btestimonios?\b", r"\btestimonials?\b", r"\bresenas?\b", r"\breviews?\b", r"\brecensioni\b", r"\bopinie\b",
    r"opiniones\s+de\s+(clientes|compradores)", r"\bavis\s+clients?\b", r"\bbewertungen?\b",
]
# F-63: una frase HONESTA sobre reseñas («aparecerán cuando sean reales», «no hay reseñas todavía») no es un testimonio. La regla D5-COPY-TESTIMONIO mira CADA FRASE que
# menciona reseñas/opiniones y solo la excusa si ESA frase dice que aún no existen (ausencia o futuro); la misma frase con una afirmación («opiniones de clientes: 4,8») se
# marca, y una frase honesta no protege a la de al lado.
AUSENCIA_RESENAS = [
    r"\b(no\s+hay|aun\s+no|todavia\s+no|ninguna|ningun|cuando\s+(haya|existan|sean|tengamos)|aparecer[ae]n?|se\s+mostrar[ae]n?|se\s+publicar[ae]n?|mostraremos|publicaremos|sin\s+resenas)\b",
    r"\b(brak|nie\s+ma|jeszcze\s+nie|dopiero|pojawi\w*|gdy\s+beda|kiedy\s+beda|gdy\s+sie\s+pojawia|bez\s+opinii)\b",
    r"\b(no\s+reviews|not\s+yet|none\s+yet|there\s+are\s+no|once\s+there\s+are|when\s+there\s+are|when\s+they\s+exist|will\s+(appear|be\s+shown|be\s+published)|we\s+will\s+show)\b",
    r"\b(non\s+ci\s+sono|ancora\s+nessun\w*|quando\s+ci\s+saranno|appariranno|senza\s+recensioni|mostreremo)\b",
]
RX_FRASE = re.compile(r"[.!?;\n]+")
ESTRELLAS = r"[★⭐]|\bestrellas?\b|\bstars?\b|\bstelle\b|\bgwiazdk"
SEL_EJEMPLO = r"\b(EJEMPLO|EXAMPLE|ESEMPIO|PRZYKŁAD|BEISPIEL|EXEMPLE)\b|TESTIMONIOS DE EJEMPLO"
PALABRA_EJEMPLO = r"\b(ejemplo|example|esempio|przyklad|beispiel|exemple)s?\b"
REFERENCIA = [r"clay\s+art", r"studio\s*™"]
SUFIJOS_MARCA = r"\b(studio|academy|master|pro|lab|creative)\b"
# Regiones con renuncia expresa a la entrega inmediata y función de desistimiento (UE + Reino Unido) [VERIFICAR con X1; spec D5 A3].
REGIONES_RENUNCIA = frozenset("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE GB".split())
GLIFOS = {
    "pl": "łąęśćńóźżŁĄĘŚĆŃÓŹŻ", "es": "ñáéíóúü¿¡", "it": "àèéìòù", "fr": "éèàçêâîôûœ", "de": "äöüß", "ro": "ăâîșț", "pt": "ãõçáéíóú",
}
# Copia de scripts/validar_esquemas.TERMINOS_SENSIBLES (la fuente es X1/B6; aquí solo para evals sin dependencias).
TERMINOS_SENSIBLES = (
    r"salud", r"diagnost", r"enfermedad", r"medic", r"health", r"patolog", r"ansiedad", r"insomni", r"depres", r"diabet", r"anxiety", r"sleep",
    r"deuda", r"prestamo", r"préstamo", r"credito", r"crédito", r"debt", r"loan", r"mortgage", r"hipoteca", r"invers",
    r"salute", r"ansia", r"debito", r"zdrow", r"dlug", r"dług", r"kredyt", r"gesundheit", r"schulden", r"sant[eé]", r"dette",
)


def plano(t: str) -> str:
    t = unicodedata.normalize("NFD", t.replace("ł", "l").replace("Ł", "L").replace("ß", "ss"))
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def _quitar_placeholders(t: str) -> str:
    return RX_PLACEHOLDER.sub(" ", t)


def _longitud_expandida(t: str) -> int:
    return len(RX_PLACEHOLDER.sub(lambda m: "x" * LONGITUD_PLACEHOLDER.get(m.group(1), 6), t))


# Claves cuyo valor es metadato (identificadores, referencias, trazas), no texto visible.
CLAVES_NO_TEXTO = {"usos", "id", "tipo", "modo", "version_texto", "orden", "primero", "unidad", "traza", "motivo", "hook_original",
                   "angulo_id", "seccion", "premarcado", "premarcada", "obligatoria", "persona", "registro", "nota", "glosario_ref",
                   "fecha", "icono", "estructura"}


def _es_metadato(clave: str) -> bool:
    return clave in CLAVES_NO_TEXTO or clave.endswith("_ref")


def textos(nodo: Any, ruta: str = "") -> Iterator[tuple[str, str]]:
    """Recorre el JSON y entrega (ruta, texto) de cada cadena."""
    if isinstance(nodo, str):
        yield ruta, nodo
    elif isinstance(nodo, dict):
        for k, v in nodo.items():
            if _es_metadato(k):
                continue
            yield from textos(v, f"{ruta}.{k}" if ruta else k)
    elif isinstance(nodo, list):
        for i, v in enumerate(nodo):
            yield from textos(v, f"{ruta}[{i}]")


def _clave(ruta: str) -> str:
    """`secciones.S12.preguntas[3].q` -> `S12.q`; `cta[0].texto` -> `cta.texto`."""
    sin_idx = re.sub(r"\[\d+\]", "", ruta)
    partes = sin_idx.split(".")
    if partes and partes[0] == "secciones":
        partes = partes[1:]
    if len(partes) >= 2 and partes[0] in ("S12",) and partes[-1] in ("q", "a"):
        return f"S12.{partes[-1]}"
    if len(partes) >= 2:
        return f"{partes[0]}.{partes[-1]}"
    return sin_idx


def plano_de(copy: dict[str, Any]) -> str:
    """Mismo criterio que `landing.contenido.plano_de`: `estructura` si existe; si no, `referente` para schema_version ≥ 0.2.0 y `clasica` para 0.1.x."""
    est = copy.get("estructura")
    if est in ("referente", "clasica"):
        return est
    m = re.match(r"^0\.(\d+)\.", str(copy.get("schema_version", "")))
    return "referente" if m and int(m.group(1)) >= 2 else "clasica"


def menciona_testimonio(p: str) -> str | None:
    """Patrón de TESTIMONIOS que dispara una frase de ``p`` (texto ya «plano») que NO dice que las reseñas aún no existen; ``None`` si ninguna frase lo hace (F-63)."""
    for frase in RX_FRASE.split(p):
        for rx in TESTIMONIOS:
            if re.search(rx, frase):
                if any(re.search(a, frase) for a in AUSENCIA_RESENAS):
                    break                                   # frase honesta: dice que no hay o que llegarán; se sigue con la siguiente
                return rx
    return None


def _importes(t: str) -> list[str]:
    ta = _quitar_placeholders(t)
    pat = r"(?:(?:€|\$|£)\s?\d[\d.,]*|\d[\d.,]*\s?(?:€|\$|£|zł|zl|PLN|EUR|USD|GBP|ARS|CAD|AUD|MXN|CHF|RON))"
    return re.findall(pat, ta)


def _a_minor(imp: str) -> int | None:
    """Importe en unidad menor a partir de «19,90 €», «€19.90», «1.990 zł» (separador decimal si hay 1-2 dígitos tras el último . o ,)."""
    m = re.search(r"\d[\d.,]*", imp)
    if not m:
        return None
    n = m.group(0).rstrip(".,")
    d = re.search(r"[.,](\d{1,2})$", n)
    if d:
        ent = re.sub(r"[.,]", "", n[: d.start()])
        return int(ent or "0") * 100 + int(d.group(1).ljust(2, "0"))
    return int(re.sub(r"[.,]", "", n)) * 100


def linter(copy: dict[str, Any], oferta: dict[str, Any] | None = None, mercado: dict[str, Any] | None = None,
           assets: dict[str, Any] | None = None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []

    def h(check: str, regla: str, sev: str, ruta: str, texto: str, detalle: str) -> None:
        out.append({"check_id": check, "regla": regla, "severidad": sev, "ruta": ruta, "texto": texto[:80], "detalle": detalle})

    secciones = copy.get("secciones") or {}
    omitidas = {o.get("seccion") for o in copy.get("omitidas", []) if isinstance(o, dict)}
    locale = str(copy.get("locale", ""))
    macro = (oferta or {}).get("macro_nicho") or (copy.get("contexto_riesgo") or {}).get("macro_nicho")
    garantia_dias = ((oferta or {}).get("garantia") or {}).get("dias")
    permitidos: set[int] = set()
    if oferta:
        permitidos.add(oferta["precio"]["lista"]["monto"])
        if (oferta.get("bump") or {}).get("precio"):
            permitidos.add(oferta["bump"]["precio"]["monto"])
    # Sin mercado.json se asume el régimen vigente por decisión del dueño (diferido).
    diferido = (((mercado or {}).get("fiscal") or {}).get("regimen", "diferido")) == "diferido"

    # 1. Estructura ---------------------------------------------------------------------------------------
    plano_copy = plano_de(copy)
    obligatorias = SECCIONES_OBLIGATORIAS_REFERENTE if plano_copy == "referente" else SECCIONES_OBLIGATORIAS
    omitibles = SECCIONES_OMITIBLES_REFERENTE if plano_copy == "referente" else SECCIONES_OMITIBLES
    for s in obligatorias:
        if s not in secciones:
            h("C03", "D5-COPY-SECCION", "MAYOR", f"secciones.{s}", "", f"falta la sección obligatoria {s}")
    for s in omitibles:
        if s not in secciones and s not in omitidas:
            h("C03", "D5-COPY-SECCION", "MAYOR", f"secciones.{s}", "", f"{s} ausente sin registro en `omitidas` con motivo")
    if plano_copy == "referente":
        for s in SECCIONES_FUERA_DEL_REFERENTE:
            if s in secciones:
                h("C03", "D5-COPY-SECCION-FUERA-DE-PLANO", "MENOR", f"secciones.{s}", "", f"{s} no forma parte del plano referente: su texto no se publica (usa `estructura: clasica` o llévalo al héroe y la FAQ)")
    else:
        for s in ("S15", "S16"):
            if s in secciones:
                h("C03", "D5-COPY-SECCION-FUERA-DE-PLANO", "MENOR", f"secciones.{s}", "", f"{s} solo existe en el plano referente: no se publica con `estructura: clasica`")
    # Comparación con el mercado (S16): cada cifra con fuente y fecha; las cifras van como enteros en unidad menor, NUNCA dentro de un texto (un importe escrito en un texto sigue siendo BLOQUEANTE).
    for i, f in enumerate((secciones.get("S16") or {}).get("filas", []) if isinstance(secciones.get("S16"), dict) else []):
        ruta_f = f"secciones.S16.filas[{i}]"
        if not isinstance(f, dict):
            continue
        if not str(f.get("fuente", "")).strip():
            h("C02", "D5-COPY-COMPARACION-SIN-FUENTE", "BLOQUEANTE", f"{ruta_f}.fuente", "", "cifra de mercado sin fuente: toda cifra ajena lleva su fuente (quién publica el precio)")
        if not RX_FECHA.match(str(f.get("fecha", ""))):
            h("C02", "D5-COPY-COMPARACION-SIN-FUENTE", "BLOQUEANTE", f"{ruta_f}.fecha", "", "cifra de mercado sin fecha de lectura válida (AAAA-MM-DD)")
        desde, hasta = f.get("desde"), f.get("hasta")
        if not isinstance(desde, int) or isinstance(desde, bool) or desde < 1:
            h("C02", "D5-COPY-COMPARACION-CIFRA", "MAYOR", f"{ruta_f}.desde", "", "`desde` debe ser un entero en unidad menor (1200 = 12,00)")
        elif hasta is not None and (not isinstance(hasta, int) or isinstance(hasta, bool) or hasta < desde):
            h("C02", "D5-COPY-COMPARACION-CIFRA", "MAYOR", f"{ruta_f}.hasta", "", "`hasta` debe ser un entero mayor o igual que `desde`")
    for b in BLOQUES_APARTE:
        if b not in secciones:
            h("C10", "D5-COPY-SECCION", "MAYOR", f"secciones.{b}", "", f"falta el bloque `{b}` (banner, /comprar o /gracias)")
    if "S08" in secciones and (secciones["S08"] or {}).get("modo") not in ("honesta", "real"):
        h("C03", "D5-COPY-S08-MODO", "MAYOR", "secciones.S08.modo", "", "S08 debe declarar modo `honesta` o `real` (o ir en `omitidas`)")
    if (secciones.get("S08") or {}).get("modo") == "real" and not all(r.get("compra_id") for r in (secciones["S08"].get("resenas") or [])):
        h("C03", "D5-COPY-RESENA-SIN-COMPRA", "BLOQUEANTE", "secciones.S08.resenas", "", "reseña sin `compra_id` (X1-P04/P08)")
    if (secciones.get("S08") or {}).get("modo") == "honesta" and (secciones["S08"].get("resenas")):
        h("C03", "D5-COPY-RESENA-SIN-COMPRA", "BLOQUEANTE", "secciones.S08.resenas", "", "modo `honesta` no admite reseñas")

    # 2. CTA variados ---------------------------------------------------------------------------------------
    cta = [c.get("texto", "").strip().lower() for c in copy.get("cta", []) if isinstance(c, dict)]
    if len(set(cta)) < 2:
        h("C03", "D5-COPY-CTA-IGUALES", "MAYOR", "cta", "", "se exigen ≥ 2 textos de CTA distintos (parámetro propuesto `landing.cta_distintos_min`)")
    for i, c in enumerate(cta):
        if re.search(r"\b(hoy|ahora|ya|today|now|oggi|teraz|dzis|heute)\b", plano(c)):
            h("C03", "D5-COPY-CTA-URGENTE", "MENOR", f"cta[{i}]", c, "«hoy/ahora/ya» en el CTA suena a urgencia; usa verbo + objeto")

    # 3. Recorrido de textos -------------------------------------------------------------------------------
    cifras_ok = {str(c.get("valor")) for c in copy.get("cifras_con_traza", []) if isinstance(c, dict)}
    textos_meta: list[tuple[str, str]] = []
    for ruta, t in textos({k: v for k, v in copy.items() if k not in ("cifras_con_traza", "omitidas", "contexto_riesgo", "tono")}):
        if not t.strip() or ruta in ("schema_version", "oferta_id", "version", "origen_version", "locale", "moneda"):
            continue
        p = plano(_quitar_placeholders(t))
        clave = _clave(ruta)
        # longitud
        limite = LIMITES.get(clave) or LIMITES_ELEMENTO.get(clave)
        if limite and _longitud_expandida(t) > limite:
            h("C03", "D5-COPY-LONGITUD", "MENOR", ruta, t, f"{_longitud_expandida(t)} > {limite} caracteres con placeholders expandidos (límite de {clave}, [HIPÓTESIS])")
        # placeholders
        for nombre, _arg in RX_PLACEHOLDER.findall(t):
            if nombre not in PLACEHOLDERS:
                h("C02", "D5-COPY-PLACEHOLDER", "MAYOR", ruta, t, f"placeholder desconocido {{{nombre}}}")
        # importes a mano
        for imp in _importes(t):
            minor = _a_minor(imp)
            if oferta and minor in permitidos:
                h("C02", "D5-COPY-IMPORTE-A-MANO", "MENOR", ruta, t, f"importe `{imp}` escrito a mano: usa {{precio}} o {{precio_bump}}")
            else:
                h("C02", "D5-COPY-IMPORTE", "BLOQUEANTE" if oferta else "MAYOR", ruta, t,
                  f"importe `{imp}` que no es el precio ni el bump de oferta.json (valor, ahorro o precio tachado no permitidos)")
        # garantía: días
        if re.search(r"garant|devol|reembols|refund|money.?back|garanzi|rimbors|gwarancj|zwrot|zwroc|garantie|rembours|ruckgabe|erstattung", p):
            for dias, _u in re.findall(r"(\d+)\s*(dias|days|giorni|dni|jours|tage)", p):
                sev = "MENOR" if garantia_dias and int(dias) == garantia_dias else "BLOQUEANTE"
                h("C02", "D5-COPY-GARANTIA-DIAS", sev, ruta, t,
                  f"«{dias} días» escrito a mano junto a una garantía (usa {{garantia_dias}}); " + ("coincide" if sev == "MENOR" else f"NO coincide con oferta.garantia.dias={garantia_dias}"))
        # contadores / urgencia
        for rx in CONTADORES:
            if re.search(rx, p):
                h("C03", "D5-COPY-URGENCIA", "BLOQUEANTE", ruta, t, f"contador, cupo, escasez o urgencia ({rx})")
                break
        # promesas rojas
        for nombre, lista in (("salud", PROMESAS_SALUD), ("dinero", PROMESAS_DINERO), ("relaciones", PROMESAS_RELACIONES)):
            for rx in lista:
                if re.search(rx, p):
                    h("C15", "D5-COPY-PROMESA-" + nombre.upper(), "BLOQUEANTE", ruta, t, f"promesa o patrón rojo de {nombre} ({rx}); ver references/claims-rojos.md")
                    break
        for rx in GARANTIA_RESULTADO:
            if re.search(rx, p):
                h("C15", "D5-COPY-GARANTIA-RESULTADO", "BLOQUEANTE", ruta, t, "garantía atada a un resultado (LP-03/LP-04)")
                break
        # IVA incluido con régimen diferido
        if diferido:
            for rx in IVA_INCLUIDO:
                if re.search(rx, p):
                    h("C02", "D5-COPY-IVA-INCLUIDO", "MAYOR", ruta, t, "con régimen fiscal diferido solo se dice «precio final» (sin «IVA incluido» ni «+ IVA»)")
                    break
        # sello EJEMPLO y palabra ejemplo
        if re.search(SEL_EJEMPLO, t):
            h("C03", "D5-COPY-EJEMPLO", "BLOQUEANTE", ruta, t, "sello o comentario EJEMPLO en el copy (SD5-17)")
        elif re.search(PALABRA_EJEMPLO, p):
            h("C03", "D5-COPY-PALABRA-EJEMPLO", "MENOR", ruta, t,
              "la palabra «ejemplo» en texto visible dispara L1-EJEMPLO-VISIBLE de landing.validar v0 (PEDIDO a B4); reescribe o espera el ajuste")
        # estrellas
        if re.search(ESTRELLAS, t, re.I):
            h("C03", "D5-COPY-ESTRELLAS", "BLOQUEANTE", ruta, t, "estrellas o puntuaciones escritas a mano (X1-P08)")
        # credenciales
        if clave.startswith("S08") or clave.startswith("S14") or clave.startswith("S07"):
            for rx in CREDENCIALES:
                if re.search(rx, p):
                    h("C15", "D5-COPY-CREDENCIAL", "MAYOR", ruta, t, "credencial, aval o autoridad: solo con prueba real (LP-08); revisión de X1")
                    break
        # testimonios fuera del modo real
        if (secciones.get("S08") or {}).get("modo") != "real" and not ruta.startswith("meta"):
            if menciona_testimonio(p):
                h("C03", "D5-COPY-TESTIMONIO", "MAYOR", ruta, t, "mención de testimonios/reseñas sin sección de opiniones reales (una frase que diga que aún no existen no cuenta)")
        # cifras sin traza (la fuente de una fila de S16 es un nombre de tienda o dominio: sus dígitos no son cifras del producto)
        es_fuente_s16 = bool(re.match(r"^secciones\.S16\.filas\[\d+\]\.fuente$", ruta))
        for num in ([] if es_fuente_s16 else re.findall(r"(?<![A-Za-z])\d+(?:[.,]\d+)?", _quitar_placeholders(t))):
            if num not in cifras_ok and not ruta.startswith(("meta",)):
                h("C03", "D5-COPY-CIFRA-SIN-TRAZA", "MAYOR", ruta, t, f"cifra «{num}» sin entrada en `cifras_con_traza` ni placeholder (X1-P08)")
        if ruta.startswith(("meta",)):
            textos_meta.append((ruta, t))

    # 4. Hero: sin pregunta ni atributo del lector (E <= E1) --------------------------------------------------
    hero = secciones.get("S01") or {}
    for campo in ("kicker", "h1", "h1_resaltado", "subtitulo"):
        t = hero.get(campo)
        if not isinstance(t, str):
            continue
        if re.search(r"[?¿]", t):
            h("C15", "D5-COPY-HERO-PREGUNTA", "BLOQUEANTE", f"secciones.S01.{campo}", t, "pregunta al espectador en la primera pantalla (E2)")
        else:
            p = plano(t)
            for rx in ATRIBUTO_HERO:
                if re.search(rx, p):
                    h("C15", "D5-COPY-HERO-ATRIBUTO", "BLOQUEANTE", f"secciones.S01.{campo}", t, f"atributo o «tú + situación» dirigido al lector en el hero ({rx})")
                    break

    # 5. Casillas y bump nunca premarcados ---------------------------------------------------------------------
    s09 = secciones.get("S09") or {}
    if (s09.get("bump") or {}).get("premarcado") is True:
        h("C03", "D5-COPY-BUMP-PREMARCADO", "BLOQUEANTE", "secciones.S09.bump.premarcado", "", "bump premarcado (SD5-15)")
    for i, c in enumerate((secciones.get("comprar") or {}).get("casillas", [])):
        if c.get("premarcada") is True:
            h("C10", "D5-COPY-CASILLA-PREMARCADA", "BLOQUEANTE", f"secciones.comprar.casillas[{i}]", c.get("texto", ""), "casilla premarcada (C10)")
    if not (secciones.get("S11") or {}).get("linea_precio"):
        h("C02", "D5-COPY-PRECIO-FINAL", "MAYOR", "secciones.S11.linea_precio", "", "falta la línea «precio final» (sin afirmar IVA incluido ni lo contrario)")

    # 5b. UE/UK: casilla separada de renuncia y enlace a /desistimiento (C11)
    region = locale.split("-")[-1].upper() if "-" in locale else ""
    if region in REGIONES_RENUNCIA:
        ids = {c.get("id") for c in (secciones.get("comprar") or {}).get("casillas", [])}
        if "renuncia-entrega-inmediata" not in ids:
            h("C11", "D5-COPY-RENUNCIA", "BLOQUEANTE", "secciones.comprar.casillas", "", f"región {region}: falta la casilla separada «renuncia-entrega-inmediata» (SD5-25)")
        if not (secciones.get("S14") or {}).get("enlaces", {}).get("desistimiento"):
            h("C11", "D5-COPY-DESISTIMIENTO", "BLOQUEANTE", "secciones.S14.enlaces.desistimiento", "", f"región {region}: falta el enlace a /desistimiento en el pie (SD5-25)")

    # 6. Riesgo: avisos y ayuda ---------------------------------------------------------------------------------
    ctx = copy.get("contexto_riesgo") or {}
    s14 = secciones.get("S14") or {}
    if not s14.get("aviso"):
        h("C15", "D5-COPY-AVISO", "MAYOR", "secciones.S14.aviso", "", "falta el aviso de alcance (/legal/aviso y pie)")
    if ctx.get("conflicto_pareja_familia") and not (s14.get("aviso_seguridad") or "").strip():
        h("C15", "D5-COPY-AVISO-SEGURIDAD", "BLOQUEANTE", "secciones.S14.aviso_seguridad", "", "producto de pareja/familia sin «Si temes por tu seguridad, no uses este material» + línea de ayuda")
    if ctx.get("nivel") == "amarillo-b" and not (s14.get("ayuda") or "").strip():
        h("C15", "D5-COPY-AYUDA", "BLOQUEANTE", "secciones.S14.ayuda", "", "amarillo-b sin bloque «Si necesitas ayuda ahora» (ayuda_por_pais)")
    if macro == "dinero" and not re.search(r"asesor|advice|consulen|doradz|conseil|beratung", plano(s14.get("aviso", ""))):
        h("C15", "D5-COPY-AVISO-DINERO", "MAYOR", "secciones.S14.aviso", s14.get("aviso", ""), "dinero: el aviso debe decir que no es asesoramiento financiero, fiscal ni legal")

    # 7. Neutralidad de datos públicos (C16) --------------------------------------------------------------------
    publicos = list(textos_meta)
    if assets:
        for i, s in enumerate(assets.get("slots", [])):
            publicos.append((f"assets.slots[{i}].alt", s.get("alt", "")))
            publicos.append((f"assets.slots[{i}].slot_id", s.get("slot_id", "")))
    for ruta, t in publicos:
        for rx in TERMINOS_SENSIBLES:
            if re.search(rx, unicodedata.normalize("NFC", t).lower()):
                h("C16", "D5-COPY-DATO-SENSIBLE", "BLOQUEANTE", ruta, t, f"término sensible en dato público (title/og/alt/slug) ({rx})")
                break

    # 8. Idioma, glifos, restos de la referencia, nombre ----------------------------------------------------------
    todo = " ".join(t for _r, t in textos(secciones))
    base_lang = locale.split("-")[0]
    if base_lang in GLIFOS and len(todo) > 400 and not any(c in todo for c in GLIFOS[base_lang]):
        h("C01", "D5-COPY-GLIFOS", "MAYOR", "secciones", "", f"ningún carácter propio de {base_lang} en {len(todo)} caracteres: ¿texto sin tildes o en otro idioma?")
    if oferta and "clay" not in json.dumps(oferta, ensure_ascii=False).lower():
        for rx in REFERENCIA:
            if re.search(rx, plano(todo)):
                h("C03", "D5-COPY-RESTO-REFERENCIA", "MAYOR", "secciones", "", f"resto de la landing de referencia ({rx})")
    if oferta:
        for campo, t in (("marca.nombre", oferta["marca"]["nombre"]), ("promesa.titulo", oferta["promesa"]["titulo"])):
            if re.search(SUFIJOS_MARCA, plano(t)):
                h("C15", "D5-NOMBRE-SUFIJO", "MENOR", campo, t, "sufijo de marca (Studio/Academy/Master/Pro/Lab/Creative): nombre descriptivo y local (Prompt 1 de la referencia)")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Lint mínimo de copy.json (D5).")
    ap.add_argument("--copy", required=True)
    ap.add_argument("--oferta")
    ap.add_argument("--mercado")
    ap.add_argument("--assets")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        cargar = lambda p: json.loads(Path(p).read_text(encoding="utf-8")) if p else None  # noqa: E731
        copy, oferta, mercado, assets = cargar(a.copy), cargar(a.oferta), cargar(a.mercado), cargar(a.assets)
    except (OSError, ValueError) as exc:
        print(f"entrada ilegible: {exc}", file=sys.stderr)
        return 2
    hall = linter(copy, oferta, mercado, assets)
    malos = [x for x in hall if x["severidad"] in ("BLOQUEANTE", "MAYOR")]
    if a.json:
        print(json.dumps({"ok": not malos, "hallazgos": hall}, ensure_ascii=False, sort_keys=True))
    else:
        for x in hall:
            print(f"{x['severidad']:<10} {x['check_id']} {x['regla']} [{x['ruta']}] {x['detalle']}")
        print("sin hallazgos bloqueantes ni mayores" if not malos else f"{len(malos)} hallazgo(s) bloqueante(s) o mayor(es)")
    return 0 if not malos else 3


if __name__ == "__main__":
    sys.exit(main())
