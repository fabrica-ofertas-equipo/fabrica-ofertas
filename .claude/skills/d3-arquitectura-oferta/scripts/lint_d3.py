"""Lint estructural L1 de la oferta de D3: lo determinista que ``validar_esquemas`` NO cubre (departamentos/04-oferta.md §6, tabla L1).

Complementa, no reemplaza: el esquema, X13 (riesgo), X14 (economía) y X15 (tiempo) los comprueba
``.venv/bin/python -m scripts.validar_esquemas oferta ofertas/<id>``; los claims con las reglas de X1 los comprueba ``compliance.lint_claims``
(que este script llama cuando el idioma tiene reglas). Aquí: coherencia de cifras entre ``oferta.json``, ``economia.json`` y la cabecera
de ``oferta.md`` (L1-02), garantía y mercado (L1-05), urgencia y prueba (L1-06), ángulos y citas (L1-07), copia de la competencia (L1-09),
ancla (L1-10), servicios, bonus y rango del bump (L1-12), nombre y ``marca_propuesta[]`` (L1-13); L1-04 llama a ``engine.factibilidad.verificar`` y compara escenarios y tasas con ``parametros.yaml``.

Uso (desde la raíz del repositorio)::

    .venv/bin/python .claude/skills/d3-arquitectura-oferta/scripts/lint_d3.py --oferta-dir ofertas/<id> \
        [--parametros empresa/parametros.yaml] [--limites empresa/limites.yaml] [--semilla-provisional] [--hoy AAAA-MM-DD] [--json]

Salida: 0 sin fallos · 3 al menos un check en ``fail`` · 2 uso. Cada check es ``{check_id, resultado (pass|fail|no_aplica), severidad_si_falla,
detalle}``; el QA copia ``check_id``, ``resultado`` y ``detalle`` a ``checks_l1[]`` (el esquema ``qa`` no admite más campos). Sin red, sin escritura.
Los términos salen de ``terminos_semilla.yaml`` [SUPUESTO hasta que X1 cargue ``terminos_sensibles/<locale>.yaml``].
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import yaml

RAIZ = Path(os.environ.get("D3_RAIZ_REPO") or Path(__file__).resolve().parents[4])
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
AQUI = Path(__file__).resolve().parent

# Método de pago local -> moneda local que exige (departamentos/04-oferta.md §3.4, «Comisión por método»; S20).
MONEDA_DE_METODO = {"blik": "PLN", "przelewy24": "PLN", "p24": "PLN", "satispay": "EUR", "bancontact": "EUR", "pix": "BRL"}
METODOS_ESTANDAR = {"card", "apple_pay", "google_pay", "link"}


def _res(check_id: str, ok: bool | None, detalle: str, sev: str) -> dict[str, str]:
    return {"check_id": check_id, "resultado": "no_aplica" if ok is None else ("pass" if ok else "fail"), "severidad_si_falla": sev,
            "detalle": detalle}


def _param(parametros: Any, clave: str, defecto: Any = None) -> Any:
    grupo, _, nombre = clave.partition(".")
    try:
        return parametros["grupos"][grupo][nombre]["valor"]
    except (TypeError, KeyError):
        return defecto


def _cargar(ruta: Path) -> Any:
    if not ruta.is_file():
        return None
    if ruta.suffix == ".json":
        return json.loads(ruta.read_text(encoding="utf-8"))
    return yaml.safe_load(ruta.read_text(encoding="utf-8"))


def cabecera_de_md(texto: str) -> dict[str, Any]:
    """Cabecera YAML (entre ``---`` y ``---``) de ``oferta.md``; ``{}`` si no hay."""
    m = re.match(r"\A---\n(.*?)\n---\n", texto, re.DOTALL)
    if not m:
        return {}
    datos = yaml.safe_load(m.group(1))
    return datos if isinstance(datos, dict) else {}


# Encabezado de la ficha de 12 puntos: «## Ficha de la oferta (12 puntos)» o su versión localizada («## Karta oferty (12 punktów)»).
RX_FICHA = re.compile(r"^## (?:Ficha.*|.*\(12 [^)\n]+\))\s*$", re.MULTILINE)


def marcas_propuestas(md: str | None) -> Any:
    """``marca_propuesta`` de la cabecera de ``oferta.md`` (hasta que CT admita el campo en ``oferta.json``); ``None`` si no está."""
    return cabecera_de_md(md).get("marca_propuesta") if md else None


def _patron(termino: str) -> re.Pattern[str]:
    if termino.startswith("re:"):
        return re.compile(termino[3:], re.IGNORECASE | re.UNICODE)
    return re.compile(r"(?<!\w)" + re.escape(termino) + r"(?!\w)", re.IGNORECASE | re.UNICODE)


def aciertos(texto: str, terminos: Iterable[str]) -> list[str]:
    """Términos de la lista que aparecen en ``texto`` (palabra o frase completa, sin distinguir mayúsculas)."""
    return [t for t in terminos if _patron(t).search(texto or "")]


def textos(datos: Any, prefijo: str = "$") -> list[tuple[str, str]]:
    """Todas las cadenas de una estructura JSON con su ruta."""
    if isinstance(datos, str):
        return [(prefijo, datos)] if datos.strip() else []
    if isinstance(datos, Mapping):
        return [x for k, v in datos.items() for x in textos(v, f"{prefijo}.{k}")]
    if isinstance(datos, (list, tuple)):
        return [x for i, v in enumerate(datos) for x in textos(v, f"{prefijo}[{i}]")]
    return []


def _ngramas(texto: str, n: int) -> set[tuple[str, ...]]:
    pal = re.findall(r"\w+", texto.casefold(), re.UNICODE)
    return {tuple(pal[i:i + n]) for i in range(len(pal) - n + 1)}


def _monto(d: Any) -> tuple[int | None, str | None]:
    return (d.get("monto"), d.get("moneda")) if isinstance(d, Mapping) else (None, None)


# ------------------------------------------------------------------------------------------------------------------
# Checks
# ------------------------------------------------------------------------------------------------------------------
def l1_02(oferta: Mapping, eco: Mapping | None, md: str | None, parametros: Any = None) -> list[dict]:
    """Precio, bump, moneda y garantía idénticos en oferta.json, economia.json y la cabecera de oferta.md; el tiempo de consumo cubre al menos la lectura."""
    fallos: list[str] = []
    wpm = _param(parametros, "economia.lectura_wpm_diseno")
    if isinstance(wpm, int) and wpm > 0 and oferta["vehiculo"]["palabras_max"] / wpm > oferta["vehiculo"]["tiempo_consumo_min"]:
        fallos.append(f"palabras_max {oferta['vehiculo']['palabras_max']} a {wpm} ppm = {oferta['vehiculo']['palabras_max'] / wpm:.0f} min de lectura > tiempo_consumo_min {oferta['vehiculo']['tiempo_consumo_min']} (S2)")
    e = (eco or {}).get("entradas_usadas", {})
    precio, mon = _monto(oferta["precio"]["lista"])
    if eco is None:
        return [_res("L1-02", False, "falta economia.json (solo puede venir de engine.factibilidad)", "BLOQUEANTE")]
    if _monto(e.get("precio")) != (precio, mon):
        fallos.append(f"precio oferta {precio} {mon} != economia {_monto(e.get('precio'))}")
    if oferta["moneda"] != e.get("moneda"):
        fallos.append(f"moneda oferta {oferta['moneda']} != economia {e.get('moneda')}")
    bump = oferta.get("bump")
    if bump:
        if _monto(bump["precio"])[0] != _monto(e.get("precio_bump"))[0]:
            fallos.append(f"precio del bump {bump['precio']['monto']} != economia {_monto(e.get('precio_bump'))[0]}")
    elif _monto(e.get("precio_bump"))[0] not in (0, None) and e.get("tasa_bump_bp"):
        fallos.append("economia cuenta un bump que la oferta no tiene")
    if md is None:
        fallos.append("falta oferta.md")
    else:
        h = cabecera_de_md(md)
        if not h:
            fallos.append("oferta.md sin cabecera YAML (---) con las cifras")
        else:
            pares = {"moneda": oferta["moneda"], "precio_lista": precio, "garantia_dias": oferta["garantia"]["dias"],
                     "veredicto": eco["veredicto"], "razon": eco["razon"], "oferta_id": oferta["oferta_id"], "version": oferta["version"],
                     "bump_precio": (bump or {}).get("precio", {}).get("monto") if bump else None}
            for clave, esperado in pares.items():
                if clave not in h:
                    fallos.append(f"cabecera de oferta.md sin {clave}")
                elif str(h[clave]) != str(esperado):
                    fallos.append(f"oferta.md {clave}={h[clave]!r} != {esperado!r}")
    return [_res("L1-02", not fallos, "; ".join(fallos) or "cifras idénticas en oferta.json, economia.json y oferta.md", "MAYOR")]


def l1_04(oferta: Mapping, eco: Mapping | None, mercado: Mapping | None, parametros: Any, limites: Mapping | None) -> list[dict]:
    """Recómputo de economia.json con el motor (mismo veredicto, diferencias 0), escenarios y tasas iguales a parametros.yaml o con override declarado (D2/M1), IVA y comisión fija modelados."""
    if eco is None:
        return [_res("L1-04", False, "falta economia.json", "BLOQUEANTE")]
    fallos: list[str] = []
    try:
        from engine import factibilidad as F  # noqa: PLC0415
        from engine.errores import ErrorFabrica  # noqa: PLC0415
        for d in F.verificar(eco, parametros, limites):
            fallos.append(f"motor: {d}")
    except ErrorFabrica as exc:
        fallos.append(f"motor: {exc.mensaje}")
    except ImportError as exc:  # pragma: no cover
        return [_res("L1-04", False, f"no se pudo importar engine.factibilidad: {exc}", "BLOQUEANTE")]
    e = eco["entradas_usadas"]
    declarado = any("override" in x.lower() and ("D2" in x or "M1" in x) for x in oferta.get("supuestos", []))
    desvios: list[str] = []
    for clave in ("tasa_bump_bp", "tasa_reembolso_bp", "tasa_disputa_bp"):
        esperado = _param(parametros, f"economia.{clave}")
        if esperado is not None and e.get(clave) != esperado:
            desvios.append(f"{clave}={e.get(clave)} != parametros {esperado}")
    factor = _param(parametros, "economia.factor_cpa_objetivo")
    if factor is not None and e.get("factor_cpa_objetivo_bp") != int(round(float(factor) * 10000)):
        desvios.append(f"factor_cpa_objetivo_bp={e.get('factor_cpa_objetivo_bp')} != parametros {factor}")
    embudo = _param(parametros, "economia.escenarios_embudo") or {}
    cpm = ((mercado or {}).get("cpm_esperado") or {}).get("monto")
    for nombre, datos in e.get("escenarios", {}).items():
        for clave in ("ctr_enlace_bp", "clic_compra_bp"):
            esperado = (embudo.get(nombre) or {}).get(clave)
            if esperado is not None and datos.get(clave) != esperado:
                desvios.append(f"escenarios.{nombre}.{clave}={datos.get(clave)} != parametros {esperado}")
        if cpm is not None and datos["cpm"]["monto"] != cpm:
            desvios.append(f"escenarios.{nombre}.cpm={datos['cpm']['monto']} != mercado.cpm_esperado {cpm}")
    if desvios and not declarado:
        fallos.append("override sin declarar (supuestos[] debe citar «override» y su fuente D2/M1): " + "; ".join(desvios))
    modelado = [x for x in oferta.get("supuestos", []) if "IVA" in x and ("0 %" in x or "no aplica" in x.lower())]
    if e.get("tasa_iva_bp") == 0 and not modelado:
        fallos.append("tasa_iva_bp = 0 sin declarar que no aplica: precio con IVA incluido sin modelar el IVA (S5)")
    if (e.get("comision_fija") or {}).get("monto") == 0:
        fallos.append("comision_fija = 0: falta la tarifa fija por transacción (S5)")
    det = "; ".join(fallos) or ("economia.json reproducible por el motor" + ("; override declarado: " + "; ".join(desvios) if desvios else "; escenarios y tasas = parametros.yaml"))
    return [_res("L1-04", not fallos, det, "BLOQUEANTE")]


def l1_05(oferta: Mapping, eco: Mapping | None, mercado: Mapping | None, parametros: Any, limites: Mapping | None, hoy: dt.date) -> list[dict]:
    """Garantía, IVA incluido, método local y moneda, vigencia de tarifas, locale/países permitidos, botón de arrepentimiento declarado."""
    fallos: list[str] = []
    notas: list[str] = []
    g = oferta["garantia"]
    if g["tipo"] != "reembolso_incondicional":
        fallos.append("la garantía debe ser reembolso_incondicional (nunca de resultado)")
    piso = _param(parametros, "landing.garantia_dias_min")
    politica = (limites or {}).get("politica_reembolso_dias")
    legal = ((mercado or {}).get("consumo") or {}).get("desistimiento_dias")
    candidatos = [x for x in (piso, politica, legal) if isinstance(x, int)]
    if piso is None:
        notas.append("sin parametros: piso landing.garantia_dias_min no verificable")
    if politica is None:
        notas.append("limites.politica_reembolso_dias en null (sin gasto autorizado)")
    if candidatos and g["dias"] < max(candidatos):
        fallos.append(f"garantía {g['dias']} d < max(piso {piso}, politica_reembolso_dias {politica}, mínimo legal {legal}) = {max(candidatos)}")
    if oferta["precio"]["tax_behavior"] != "inclusive":
        fallos.append("precio.tax_behavior debe ser inclusive (precio local con IVA incluido)")
    if mercado is not None:
        activos = {str(m).lower() for m in (mercado.get("metodos_pago") or {}).get("activos", [])}
        for metodo in activos - METODOS_ESTANDAR:
            exigida = MONEDA_DE_METODO.get(metodo)
            if exigida and oferta["moneda"] != exigida:
                fallos.append(f"método local {metodo} exige {exigida} y la oferta cobra en {oferta['moneda']}")
        fase = (mercado.get("metodos_pago") or {}).get("fase")
        if fase == "estandar_tarjeta_billeteras" and activos & set(MONEDA_DE_METODO):
            fallos.append("mercado.fase = estandar_tarjeta_billeteras pero hay métodos locales activos (S20)")
        if "boton_arrepentimiento" not in (mercado.get("consumo") or {}):
            fallos.append("mercado.consumo.boton_arrepentimiento no declarado para D5")
        if mercado.get("locale") != oferta["locale"] or mercado.get("moneda_cobro") != oferta["moneda"]:
            fallos.append("locale o moneda de la oferta distintos de mercado.json")
    if eco is not None:
        e = eco["entradas_usadas"]
        if e.get("tarifas_origen") == "supuesto":
            notas.append("tarifas_origen=supuesto: tarifas.json de F1 ausente; el QA lo marca como SUPUESTO")
        else:
            maxd = _param(parametros, "finanzas.tarifas_antiguedad_max_dias")
            try:
                edad = (hoy - dt.date.fromisoformat(e["tarifas_fecha"])).days
            except (KeyError, ValueError):
                edad = None
            if maxd is not None and (edad is None or edad > maxd):
                fallos.append(f"tarifas de {e.get('tarifas_fecha')} con más de {maxd} días")
    if limites is not None:
        for clave, valor in (("locales_permitidos", oferta["locale"]), ("paises_permitidos", None)):
            lista = limites.get(clave) or []
            if not lista:
                notas.append(f"limites.{clave} vacío (sin gasto autorizado)")
            elif clave == "locales_permitidos" and valor not in lista:
                fallos.append(f"locale {valor} fuera de limites.locales_permitidos")
            elif clave == "paises_permitidos" and not set(oferta["paises_segmentacion"]) <= set(lista):
                fallos.append(f"países {sorted(set(oferta['paises_segmentacion']) - set(lista))} fuera de limites.paises_permitidos")
    detalle = "; ".join(fallos) or ("garantía, IVA, método y vigencia correctos" + (f" (notas: {'; '.join(notas)})" if notas else ""))
    return [_res("L1-05", not fallos, detalle, "BLOQUEANTE")]


def l1_06(oferta: Mapping, entrevista: Mapping | None, semilla: Mapping, idioma: str) -> list[dict]:
    """Urgencia con verificable_por, prueba solo de los tipos del contrato, testimonio con consentimiento, sin cifras de personas si casos_previos_n = 0."""
    fallos: list[str] = []
    urg = oferta.get("urgencia")
    if urg is not None and not (urg or {}).get("verificable_por"):
        fallos.append("urgencia sin verificable_por")
    for i, p in enumerate(oferta.get("prueba") or []):
        if p["tipo"] == "testimonio_con_permiso" and not p.get("consentimiento_ref"):
            fallos.append(f"prueba[{i}] testimonio sin consentimiento_ref")
    casos = int(((entrevista or {}).get("casos_previos_n") or 0))
    if casos == 0:
        patron = re.compile(r"\b\d[\d.,]*\+?\s*(personas|clientes|alumnos|usuarios|compradores|people|customers|students|users|persone|clienti|studenti|"
                            r"osób|klientów|uczniów)\b", re.IGNORECASE | re.UNICODE)
        for ruta, t in textos(oferta):
            if patron.search(t):
                fallos.append(f"cifra de personas con casos_previos_n=0 en {ruta}: «{patron.search(t).group(0)}»")
    for i, p in enumerate(oferta.get("prueba") or []):
        if p["tipo"] == "testimonio_con_permiso" and casos == 0:
            fallos.append(f"prueba[{i}] testimonio con casos_previos_n=0: no hay clientes que lo den")
    return [_res("L1-06", not fallos, "; ".join(fallos) or "urgencia y prueba verificables", "BLOQUEANTE")]


def l1_07(oferta: Mapping, candidatos: Mapping | None, voz: Mapping | None) -> list[dict]:
    """Ángulos (≥5, ≥3 niveles, id kebab sin «_»), claims_ref ⊂ claims_permitidos, objeciones con respuesta_en, citas literales."""
    fallos: list[str] = []
    ang = oferta["angulos"]
    if len(ang) < 5:
        fallos.append(f"{len(ang)} ángulos (< 5)")
    if len({a["nivel_conciencia"] for a in ang}) < 3:
        fallos.append("menos de 3 niveles de conciencia")
    ids_claims = {c["claim_id"] for c in oferta["promesa"]["claims_permitidos"]}
    if len({a["angulo_id"] for a in ang}) != len(ang):
        fallos.append("angulo_id repetido")
    for a in ang:
        if "_" in a["angulo_id"] or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", a["angulo_id"]):
            fallos.append(f"angulo_id no kebab sin «_»: {a['angulo_id']}")
        fuera = set(a["claims_ref"]) - ids_claims
        if fuera:
            fallos.append(f"{a['angulo_id']}: claims_ref fuera de claims_permitidos {sorted(fuera)}")
        if not a["claims_ref"]:
            fallos.append(f"{a['angulo_id']}: sin claims_ref")
    for o in oferta["avatar"]["objeciones"]:
        if not o.get("respuesta_en"):
            fallos.append(f"objeción sin respuesta_en: {o.get('texto', '')[:40]}")
    if voz is not None or candidatos is not None:
        literales = {f["texto_literal"] for f in (voz or {}).get("frases", []) if isinstance(f, Mapping) and f.get("texto_literal")}
        for cand in (candidatos or {}).get("candidatos", []):
            literales |= {ev.get("cita") for ev in cand.get("evidencia", []) if ev.get("cita")}
        for frase in oferta["avatar"]["lo_dice"]:
            if frase not in literales:
                fallos.append(f"avatar.lo_dice no es literal de voz_cliente.json ni de la evidencia del candidato: «{frase[:50]}»")
        ev_ids = {ev.get("id") for cand in (candidatos or {}).get("candidatos", []) for ev in cand.get("evidencia", [])}
        ev_ids |= {f.get("frase_id") for f in (voz or {}).get("frases", []) if isinstance(f, Mapping) and f.get("frase_id")}
        for a in ang:
            ref = a.get("cita_voz_ref")
            limpio = str(ref).split("#", 1)[-1] if ref else None      # «voz_cliente.json#f-03» o «f-03» o «EV-01»
            if limpio and ev_ids and limpio not in ev_ids:
                fallos.append(f"{a['angulo_id']}: cita_voz_ref {ref!r} no existe en voz_cliente.json (frase_id) ni en la evidencia EV-xx del candidato")
    return [_res("L1-07", not fallos, "; ".join(fallos) or "ángulos, niveles, claims y citas coherentes", "MAYOR")]


def l1_09(oferta: Mapping, comp: Any, parametros: Any, semilla: Mapping) -> list[dict]:
    """Sin marcas de terceros en marca/título/subtítulo ni Venzio; sin ≥ N palabras consecutivas idénticas a anuncios_competencia.json."""
    fallos: list[str] = []
    cabeza = " ".join([oferta["marca"]["nombre"], oferta["promesa"]["titulo"], oferta["promesa"]["subtitulo"], oferta["slug"]])
    for m in aciertos(cabeza, semilla.get("marcas_terceros", [])):
        fallos.append(f"marca de terceros en marca/título/subtítulo: {m}")
    for ruta, t in textos({k: v for k, v in oferta.items() if k not in ("riesgo", "supuestos")}):
        if aciertos(t, ["Venzio"]):
            fallos.append(f"{ruta}: depende de Venzio (decisión 6 del backbone)")
    n_bloq = int(_param(parametros, "compliance.ngrama_copia_palabras", 8))
    n_alerta = int(_param(parametros, "compliance.ngrama_alerta_temprana_palabras", 6))
    alerta = ""
    if comp is not None:
        ajeno = " ".join(t for _, t in textos(comp))
        propio = [(r, t) for r, t in textos({k: oferta[k] for k in ("promesa", "angulos", "bonus", "bump", "garantia")})]
        for ruta, t in propio:
            if _ngramas(t, n_bloq) & _ngramas(ajeno, n_bloq):
                fallos.append(f"{ruta}: ≥ {n_bloq} palabras consecutivas idénticas a anuncios_competencia.json")
            elif _ngramas(t, n_alerta) & _ngramas(ajeno, n_alerta):
                alerta += f" alerta temprana (≥ {n_alerta} palabras) en {ruta};"
    return [_res("L1-09", not fallos, "; ".join(fallos) or ("sin marcas de terceros ni copia" + alerta), "MAYOR")]


def l1_10(oferta: Mapping, idioma: str, semilla: Mapping) -> list[dict]:
    """Ningún «precio normal/valor real» sin historial: anclaje nulo en v1 y sin esas frases en el texto."""
    fallos: list[str] = []
    if oferta["precio"].get("anclaje") is not None:
        fallos.append("precio.anclaje no nulo: el ancla exige historial real de 30 días (una oferta nueva no lo tiene)")
    frases = semilla.get("por_idioma", {}).get(idioma, {}).get("ancla_falsa", [])
    for ruta, t in textos({k: oferta[k] for k in ("promesa", "angulos", "bonus", "bump", "garantia", "avatar")}):
        for hit in aciertos(t, frases):
            fallos.append(f"{ruta}: «{hit}» sugiere precio de referencia")
    return [_res("L1-10", not fallos, "; ".join(fallos) or "sin ancla ni precio de referencia", "BLOQUEANTE")]


def l1_12(oferta: Mapping, parametros: Any, semilla: Mapping, idioma: str) -> list[dict]:
    """3-5 bonus; ni bonus, bump ni entregables con comunidad, soporte, mentoría, clases en vivo, certificado o suscripción; upsell nulo; bump en rango."""
    fallos: list[str] = []
    if not 3 <= len(oferta["bonus"]) <= 5:
        fallos.append(f"{len(oferta['bonus'])} bonus (deben ser 3-5)")
    if oferta.get("upsell") is not None:
        fallos.append("upsell no nulo (el upsell de un clic está desactivado)")
    prohibidos = semilla.get("por_idioma", {}).get(idioma, {}).get("servicios_prohibidos", [])
    zonas = {"bonus": oferta["bonus"], "bump": oferta.get("bump"), "entregables": oferta["entregables"]}
    for zona, contenido in zonas.items():
        for ruta, t in textos(contenido, zona):
            for hit in aciertos(t, prohibidos):
                fallos.append(f"{ruta}: «{hit}» (servicio, comunidad o mentoría)")
    bump = oferta.get("bump")
    nota = ""
    if bump:
        # Una sola fuente del rango: el parámetro (departamentos/04-oferta.md §3.2, D3-B2). El 40 % de la spec es una recomendación [HIPÓTESIS], no un tope.
        pct = 100 * bump["precio"]["monto"] / oferta["precio"]["lista"]["monto"]
        minimo, maximo = _param(parametros, "landing.bump_pct_precio_min"), _param(parametros, "landing.bump_pct_precio_max")
        if minimo is None or maximo is None:
            nota = "; rango del bump NO verificado: faltan landing.bump_pct_precio_min/max (pasa --parametros)"
        else:
            if pct < minimo:
                fallos.append(f"bump = {pct:.0f} % del precio (< landing.bump_pct_precio_min {minimo})")
            if pct > maximo:
                fallos.append(f"bump = {pct:.0f} % del precio (> landing.bump_pct_precio_max {maximo})")
    return [_res("L1-12", not fallos, "; ".join(fallos) or ("bonus, bump y entregables sin servicios; upsell nulo" + nota), "BLOQUEANTE")]


def _marcas_13(marcas: Any, prop: Mapping | None, semilla: Mapping, eco: Mapping | None) -> tuple[list[str], str]:
    """``marca_propuesta[]`` (cabecera de oferta.md): ≤ 3, cada una ``{nombre, dominio}``, neutra (mismas listas que el nombre + marcas de terceros)."""
    if marcas is None:
        if (eco or {}).get("veredicto") in ("FACTIBLE", "AJUSTADA"):
            return [], "; sin marca_propuesta[] en la cabecera de oferta.md: el dueño no podrá elegir marca en el gate H ni disparar el alta (N01b)"
        return [], ""
    if not isinstance(marcas, list):
        return ["marca_propuesta debe ser una lista de {nombre, dominio}"], ""
    fallos: list[str] = []
    if len(marcas) > 3:
        fallos.append(f"marca_propuesta[] trae {len(marcas)} candidatos (máximo 3)")
    for i, m in enumerate(marcas):
        if not isinstance(m, Mapping) or not m.get("nombre") or not m.get("dominio"):
            fallos.append(f"marca_propuesta[{i}] sin nombre o dominio")
            continue
        texto = f"{m['nombre']} {m['dominio']}"
        for s_ in aciertos(texto, semilla.get("sufijos_prohibidos_en_nombre", [])):
            fallos.append(f"marca_propuesta[{i}]: sufijo vedado «{s_}»")
        for s_ in aciertos(texto, semilla.get("marcas_terceros", [])):
            fallos.append(f"marca_propuesta[{i}]: marca de terceros «{s_}»")
        for clave in ("nombre_verbos_de_cambio", "nombre_estado_o_facilidad", "nombre_ganar", "autopercepcion"):
            for hit in aciertos(str(m["nombre"]), (prop or {}).get(clave, [])):
                fallos.append(f"marca_propuesta[{i}]: «{hit}» ({clave})")
    return fallos, ""


def l1_13(oferta: Mapping, semilla: Mapping, idioma: str, md: str | None = None, eco: Mapping | None = None) -> list[dict]:
    """Nombre y subtítulo sin sufijos de marca, verbo de cambio, nombre de estado, «ganar» ni «cura»; ``marca_propuesta[]`` ≤ 3 y neutra (detiene; decide una persona)."""
    fallos: list[str] = []
    prop = semilla.get("por_idioma", {}).get(idioma)
    nombre = f"{oferta['marca']['nombre']} | {oferta['promesa']['titulo']}"
    for s in aciertos(nombre, semilla.get("sufijos_prohibidos_en_nombre", [])):
        fallos.append(f"sufijo de marca «{s}» en el nombre")
    zonas = {"nombre": nombre, "subtítulo": oferta["promesa"]["subtitulo"]}
    if prop is None:
        fallos.append(f"sin semilla de términos para el idioma {idioma!r} (L1-13 no verificable: fail-closed)")
    else:
        for donde, t in zonas.items():
            for clave in ("nombre_verbos_de_cambio", "nombre_estado_o_facilidad", "nombre_ganar", "autopercepcion"):
                for hit in aciertos(t, prop.get(clave, [])):
                    fallos.append(f"{donde}: «{hit}» ({clave})")
    marcas, nota = _marcas_13(marcas_propuestas(md), prop, semilla, eco)
    fallos += marcas
    return [_res("L1-13", not fallos, "; ".join(fallos) or ("nombre y subtítulo descriptivos, sin sufijo ni verbo de cambio" + nota),
                 "BLOQUEANTE (detiene; decide una persona)")]


def l1_03(oferta: Mapping, md: str | None, idioma_locale: str, macro: str, provisional: bool, semilla: Mapping) -> list[dict]:
    """Linter de claims por idioma con las reglas de X1 (compliance.lint_claims). Sin reglas del locale: fail-closed salvo ``--semilla-provisional``."""
    try:
        from compliance.lint_claims import lint_artefacto, lint_texto  # noqa: PLC0415
        from compliance.reglas import cargar_reglas  # noqa: PLC0415
        from engine.errores import ErrorValidacion  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - el repo trae compliance/
        return [_res("L1-03", False, f"no se pudo importar compliance.lint_claims: {exc}", "BLOQUEANTE")]
    # Solo texto de cara al cliente (spec L1-03: nombre, subtítulo, ángulos, bump, bonus, garantía + claims permitidos y entregables).
    # NO se lintean `claims_prohibidos`, `riesgo.claims_a_evitar` ni `avatar` (listas negativas y citas del cliente: están «fuera de cita» a propósito)
    # ni las secciones A-F de oferta.md (análisis interno); de oferta.md solo la ficha de 12 puntos.
    publico = {"marca": oferta["marca"]["nombre"],
               "promesa": {"titulo": oferta["promesa"]["titulo"], "subtitulo": oferta["promesa"]["subtitulo"],
                           "claims_permitidos": [c["texto"] for c in oferta["promesa"]["claims_permitidos"]]},
               "angulos": [{k: a[k] for k in ("hook", "objecion", "prueba")} for a in oferta["angulos"]],
               "bonus": oferta["bonus"], "bump": oferta.get("bump"), "garantia": oferta["garantia"], "entregables": oferta["entregables"]}
    ficha = None
    if md:
        m = RX_FICHA.search(md)
        ficha = md[m.start():] if m else None
    marcas = marcas_propuestas(md)
    if isinstance(marcas, list):
        publico["marca_propuesta"] = [m["nombre"] for m in marcas if isinstance(m, Mapping) and m.get("nombre")]
    try:
        reglas = cargar_reglas()
        hall = lint_artefacto(publico, reglas, locale=idioma_locale, macro_nicho=macro)
        if ficha:
            hall += lint_texto(ficha, reglas, locale=idioma_locale, macro_nicho=macro, origen="oferta.md#ficha")
    except ErrorValidacion as exc:
        base = f"sin reglas de X1 para {idioma_locale} ({exc}) [PENDIENTE: X1 terminos_sensibles/<locale>]"
        if provisional:
            return [_res("L1-03", None, base + "; se acepta la semilla local SOLO en práctica (gate H del dueño revisa todo)", "BLOQUEANTE")]
        return [_res("L1-03", False, base + "; fail-closed", "BLOQUEANTE")]
    rojos = [h for h in hall if h.nivel == "rojo"]
    amar = [h for h in hall if h.nivel == "amarillo"]
    det = f"reglas_version {reglas.reglas_version}; ROJO={len(rojos)}, AMARILLO={len(amar)}" + ("" if ficha else "; oferta.md sin la ficha de 12 puntos (no se pudo lintear)")
    if reglas.revision_nativa.get(idioma_locale) is False:
        det += f"; reglas de {idioma_locale} SIN revisión nativa [HIPÓTESIS]: el QA lo declara y la revisión nativa sigue pendiente (L3-6)"
    if rojos:
        det += "; " + "; ".join(f"{h.patron_clave} «{h.evidencia[:60]}»" for h in rojos[:5])
    return [_res("L1-03", not rojos and bool(ficha), det, "BLOQUEANTE")]


def _hashes(dir_oferta: Path) -> dict[str, Any]:
    """``artefacto_sha256`` (oferta.json) y ``entradas`` (mapa ruta -> sha256) con el hash canónico del repositorio: el QA no tiene Bash y los copia al informe."""
    try:
        from scripts.validar_esquemas import hash_ruta  # noqa: PLC0415
    except ImportError:  # pragma: no cover
        return {"artefacto_sha256": None, "entradas": {}}
    rels = ["03-oferta/economia.json", "03-oferta/oferta.md", "mercado.json", "01-descubrimiento/candidatos.json", "02-validacion/validacion.json"]
    return {"artefacto_ref": "03-oferta/oferta.json", "artefacto_sha256": hash_ruta(dir_oferta / "03-oferta" / "oferta.json"),
            "entradas": {r: hash_ruta(dir_oferta / r) for r in rels if (dir_oferta / r).is_file()}}


def ejecutar(dir_oferta: Path, parametros: Any, limites: Mapping | None, provisional: bool, hoy: dt.date) -> dict[str, Any]:
    d = dir_oferta / "03-oferta"
    oferta = _cargar(d / "oferta.json")
    if oferta is None:
        raise FileNotFoundError(f"no existe {d / 'oferta.json'}")
    eco = _cargar(d / "economia.json")
    md = (d / "oferta.md").read_text(encoding="utf-8") if (d / "oferta.md").is_file() else None
    entrevista = _cargar(d / "entrevista.yaml")
    mercado = _cargar(dir_oferta / "mercado.json")
    candidatos = _cargar(dir_oferta / "01-descubrimiento" / "candidatos.json")
    voz = _cargar(dir_oferta / "02-validacion" / "voz_cliente.json")
    comp = _cargar(dir_oferta / "02-validacion" / "anuncios_competencia.json")
    semilla = yaml.safe_load((AQUI / "terminos_semilla.yaml").read_text(encoding="utf-8"))
    idioma = oferta["locale"].split("-")[0]
    checks: list[dict] = []
    checks += l1_02(oferta, eco, md, parametros)
    checks += l1_03(oferta, md, oferta["locale"], oferta["macro_nicho"], provisional, semilla)
    checks += l1_04(oferta, eco, mercado, parametros, limites)
    checks += l1_05(oferta, eco, mercado, parametros, limites, hoy)
    checks += l1_06(oferta, entrevista, semilla, idioma)
    checks += l1_07(oferta, candidatos, voz)
    checks += l1_09(oferta, comp, parametros, semilla)
    checks += l1_10(oferta, idioma, semilla)
    checks += l1_12(oferta, parametros, semilla, idioma)
    checks += l1_13(oferta, semilla, idioma, md, eco)
    fallos = [c for c in checks if c["resultado"] == "fail"]
    return {"oferta_id": oferta["oferta_id"], "version": oferta["version"], "locale": oferta["locale"], "checks": checks,
            "fallos": len(fallos), **_hashes(dir_oferta), "no_cubierto_aqui": ["L1-01 (validar_esquemas oferta)",
                                                        "L1-08 (validar_esquemas oferta --limites)",
                                                        "L1-11 (X13 + el QA: máximo por activo y limites.nivel_max_lanzable[macro]; null = SOLO VERDE)",
                                                        "L1-14", "L1-15"]}


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="lint_d3.py", description=__doc__.splitlines()[0])
    ap.add_argument("--oferta-dir", required=True)
    ap.add_argument("--parametros")
    ap.add_argument("--limites")
    ap.add_argument("--semilla-provisional", action="store_true", help="solo práctica: sin reglas de X1 para el locale, L1-03 queda no_aplica")
    ap.add_argument("--hoy", help="AAAA-MM-DD (por defecto, hoy UTC; fija la vigencia de tarifas)")
    ap.add_argument("--json", action="store_true")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code not in (0, None) else 0
    try:
        par = yaml.safe_load(Path(args.parametros).read_text(encoding="utf-8")) if args.parametros else None
        lim = yaml.safe_load(Path(args.limites).read_text(encoding="utf-8")) if args.limites else None
        hoy = dt.date.fromisoformat(args.hoy) if args.hoy else dt.datetime.now(dt.timezone.utc).date()
        r = ejecutar(Path(args.oferta_dir), par, lim, args.semilla_provisional, hoy)
    except (FileNotFoundError, ValueError, KeyError) as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        for c in r["checks"]:
            print(f"[{c['resultado'].upper():9}] {c['check_id']} ({c['severidad_si_falla']}): {c['detalle']}")
        print(f"fallos={r['fallos']}")
    return 3 if r["fallos"] else 0


if __name__ == "__main__":
    sys.exit(main())
