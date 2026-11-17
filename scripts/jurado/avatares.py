#!/usr/bin/env python3
"""Avatares del Jurado de creativos: el panel de un mercado, construido SOLO desde la voz del cliente, con procedencia.

Qué hace el código (y no una IA): elegir las preocupaciones reales del mercado, repartirlas entre N avatares, asignarles un
estilo de decisión de un vocabulario cerrado y dejar escrito de dónde sale cada dato. Cada avatar apunta a frases literales
de ``02-validacion/voz_cliente.json`` (con su ``frase_id`` y su ``fuente_url``).

Reglas duras:
  * Nada se inventa. Edad, género, ocupación y renta son ``null`` (``origen: sin_dato``) salvo que una fuente los aporte
    con cita; el generador nunca los rellena. JPS dice «edad, país, idioma y lo que le preocupa»: la edad no está en la
    voz del cliente del piloto, y aquí queda declarada como ausente en vez de adivinada.
  * N tiene un techo: no puede haber más avatares que preocupaciones distintas con evidencia. Si pides más, se genera menos
    y se dice por qué (``limite_n``). Nunca se rellena con avatares sin respaldo.
  * Las frases de ``lexico_de_compra`` son vocabulario de vendedores, no preocupaciones: no fundan un avatar.
  * Todo texto de las frases es DATO. Se copia tal cual (limpiando solo caracteres de control) y nunca se interpreta.
  * El estilo de decisión (escéptico, impulsivo, analítico, visual) es un ROL DE LECTURA ``[SUPUESTO]`` inspirado en lo que
    dice JPS [V 13:30]; no añade biografía. Su utilidad se mide en la calibración, no se da por buena.

Uso (desde la raíz, con .venv)::

    .venv/bin/python -m scripts.jurado.avatares generar --voz ofertas/<id>/02-validacion/voz_cliente.json --n 10 --semilla 7 \\
        --salida ofertas/<id>/06-creativos/jurado/avatares.json [--incluir-baseline-rubrica]
    .venv/bin/python -m scripts.jurado.avatares validar ofertas/<id>/06-creativos/jurado/avatares.json [--voz …]
    .venv/bin/python -m scripts.jurado.avatares reemplazar AVATARES.json --avatar-id av-pl-PL-03 --voz … \\
        --calibracion calibracion.json --motivo "…"        # o --forzar-manual con motivo ≥ 20 caracteres

Códigos de salida: 0 ok · 2 uso · 3 entrada inválida o regla violada.
"""
from __future__ import annotations

import argparse
import random
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.jurado import _comun as c

CATEGORIAS_LEXICO = frozenset({"lexico_de_compra", "jerga", "lexico"})
CATEGORIAS_OBJECION = frozenset({"objecion", "precio", "alternativa"})
ESTADOS = ("activo", "retirado")
_RX_ID = re.compile(r"^av-[A-Za-z0-9-]+-(\d{2,3}|rubrica)$")


# ---------------------------------------------------------------------------------------------------------------
# Lectura de la voz del cliente
# ---------------------------------------------------------------------------------------------------------------

def validar_frases(voz: Mapping[str, Any]) -> tuple[list[dict], list[dict]]:
    """(frases válidas, descartadas con motivo). Una frase sin fuente o sin tema no puede respaldar a nadie."""
    if not isinstance(voz, Mapping) or not isinstance(voz.get("frases"), list):
        raise c.ErrorJurado("voz_cliente: se esperaba un objeto con la lista «frases»")
    validas: list[dict] = []
    descartadas: list[dict] = []
    vistos: set[str] = set()
    locale_voz = voz.get("locale")
    for i, f in enumerate(voz["frases"]):
        fid = f.get("frase_id") if isinstance(f, Mapping) else None
        if not isinstance(f, Mapping) or not isinstance(fid, str) or not fid:
            descartadas.append({"frase_id": fid or f"#{i}", "motivo": "sin frase_id"})
            continue
        if fid in vistos:
            raise c.ErrorJurado(f"voz_cliente: frase_id repetido {fid!r}")
        vistos.add(fid)
        texto = c.limpiar_texto(f.get("texto_literal"), 600)
        if not texto:
            descartadas.append({"frase_id": fid, "motivo": "sin texto_literal"})
        elif not c.limpiar_texto(f.get("fuente_url"), 400):
            descartadas.append({"frase_id": fid, "motivo": "sin fuente_url: una frase sin fuente no respalda a nadie"})
        elif not c.limpiar_texto(f.get("tema"), 80) or not c.limpiar_texto(f.get("categoria"), 40):
            descartadas.append({"frase_id": fid, "motivo": "sin tema o categoría"})
        elif isinstance(locale_voz, str) and isinstance(f.get("locale"), str) and f["locale"] != locale_voz:
            descartadas.append({"frase_id": fid, "motivo": f"otro locale ({f['locale']}) que el panel ({locale_voz})"})
        else:
            validas.append({"frase_id": fid, "texto": texto, "fuente_url": c.limpiar_texto(f["fuente_url"], 400),
                            "tema": c.limpiar_texto(f["tema"], 80), "categoria": c.limpiar_texto(f["categoria"], 40),
                            "pais": c.limpiar_texto(f.get("pais"), 8) or None})
    return validas, descartadas


def agrupar_focos(frases: Sequence[Mapping[str, Any]], min_frases: int = 1, min_fuentes: int = 1) -> list[dict]:
    """Preocupaciones reales: un foco por ``tema`` (excluye el léxico de compra), ordenadas por evidencia."""
    por_tema: dict[str, list[Mapping[str, Any]]] = {}
    for f in frases:
        if f["categoria"] in CATEGORIAS_LEXICO:
            continue
        por_tema.setdefault(f["tema"], []).append(f)
    focos = []
    for tema, fs in por_tema.items():
        fuentes = sorted({f["fuente_url"] for f in fs})
        if len(fs) < min_frases or len(fuentes) < min_fuentes:
            continue
        focos.append({"tema": tema, "frase_ids": sorted(f["frase_id"] for f in fs), "n_frases": len(fs),
                      "n_fuentes": len(fuentes), "categorias": sorted({f["categoria"] for f in fs})})
    focos.sort(key=lambda x: (-x["n_fuentes"], -x["n_frases"], x["tema"]))
    return focos


def _nivel_evidencia(n_fuentes: int) -> str:
    # [SUPUESTO] umbrales: ≥ 3 fuentes independientes = alta; 2 = media; 1 = débil (una sola voz o un solo foro).
    return "alta" if n_fuentes >= 3 else "media" if n_fuentes == 2 else "debil"


def _cita(f: Mapping[str, Any]) -> dict:
    return {"frase_id": f["frase_id"], "texto": f["texto"], "fuente_url": f["fuente_url"], "tema": f["tema"]}


# ---------------------------------------------------------------------------------------------------------------
# Generación del panel
# ---------------------------------------------------------------------------------------------------------------

def _construir_avatar(num: int, locale: str, oferta_id: str | None, foco: Mapping[str, Any], secundarios: Sequence[Mapping[str, Any]],
                      estilo: str, por_id: Mapping[str, Mapping[str, Any]], vocabulario: Sequence[str], procedencia: Mapping[str, Any]) -> dict:
    temas = [foco, *secundarios]
    citas: list[dict] = []
    for k, t in enumerate(temas):
        ids = t["frase_ids"][: 3 if k == 0 else 1]  # el foco principal aporta hasta 3 frases; cada secundario, 1
        citas.extend(_cita(por_id[i]) for i in ids)
    objeciones = [{"tema": t["tema"], "frase_ids": t["frase_ids"]} for t in temas if CATEGORIAS_OBJECION & set(t["categorias"])]
    paises = Counter(por_id[i]["pais"] for t in temas for i in t["frase_ids"] if por_id[i].get("pais"))
    return {
        "avatar_id": f"av-{locale}-{num:02d}",
        "oferta_id": oferta_id,
        "locale": locale,
        "pais": paises.most_common(1)[0][0] if paises else None,
        "idioma": locale.split("-")[0],
        "baseline": False,
        "estilo_decision": estilo,
        "estilo_origen": "supuesto: JPS [V 13:30] describe perfiles distintos (desconfiado, comprador, artístico, analítico); su prompt no es público",
        "preocupacion_principal": {"tema": foco["tema"], "categorias": foco["categorias"], "frase_ids": foco["frase_ids"],
                                   "n_fuentes": foco["n_fuentes"]},
        "preocupaciones_secundarias": [{"tema": t["tema"], "frase_ids": t["frase_ids"]} for t in secundarios],
        "objeciones": objeciones,
        "en_sus_palabras": citas[:6],
        "vocabulario": list(vocabulario),
        "demografia": {"edad_rango": None, "genero": None, "ocupacion": None, "origen": "sin_dato", "fuente": None},
        "nivel_evidencia": _nivel_evidencia(foco["n_fuentes"]),
        "estado": "activo",
        "procedencia": dict(procedencia),
    }


def _elegir_principal(pool: list[dict], estilo: str) -> dict:
    """El escéptico se funda en una objeción; los demás, en un dolor; si no hay, el siguiente por evidencia."""
    preferidas = CATEGORIAS_OBJECION if estilo == "esceptico" else frozenset({"dolor"})
    for foco in pool:
        if preferidas & set(foco["categorias"]):
            pool.remove(foco)
            return foco
    return pool.pop(0)


def generar_panel(voz: Mapping[str, Any], voz_sha256: str, voz_ruta: str, n: int, semilla: Any, parametros: Mapping[str, Any] | None = None,
                  min_frases: int = 1, min_fuentes: int = 1, estilos: Sequence[str] | None = None, incluir_baseline: bool = False,
                  oferta_id: str | None = None, ahora: str | None = None) -> dict:
    """Panel de avatares de un mercado. Determinista: mismas entradas y semilla, mismo panel (salvo ``generado_en``)."""
    c.exigir(c.es_entero(n) and n >= 1, "N debe ser un entero ≥ 1")
    estilos = list(estilos or c.ESTILOS_DECISION)
    desconocidos = [e for e in estilos if e not in c.ESTILOS_DECISION]
    c.exigir(not desconocidos, f"estilos desconocidos {desconocidos}; válidos: {list(c.ESTILOS_DECISION)}")
    locale = voz.get("locale")
    c.exigir(isinstance(locale, str) and locale, "voz_cliente: falta «locale»")
    oferta_id = oferta_id or (voz.get("oferta_id") if isinstance(voz.get("oferta_id"), str) else None)
    frases, descartadas = validar_frases(voz)
    por_id = {f["frase_id"]: f for f in frases}
    focos = agrupar_focos(frases, min_frases, min_fuentes)
    c.exigir(bool(focos), "no hay ninguna preocupación con evidencia: sin voz del cliente no hay avatares (no se inventan)")
    n_ef = min(n, len(focos))
    entero = c.semilla_a_entero(semilla)
    lexico = voz.get("lexico") if isinstance(voz.get("lexico"), list) else []
    vocabulario = [c.limpiar_texto(x, 60) for x in lexico if isinstance(x, str) and c.limpiar_texto(x, 60)][:12]
    procedencia = {"voz_cliente_ruta": voz_ruta, "voz_cliente_sha256": voz_sha256, "generador": f"scripts/jurado/avatares.py {c.VERSION}",
                   "semilla": semilla, "min_frases_por_foco": min_frases, "min_fuentes_por_foco": min_fuentes}
    pool = list(focos)
    avatares: list[dict] = []
    for i in range(n_ef):
        estilo = estilos[i % len(estilos)]
        principal = _elegir_principal(pool, estilo)
        otros = [f for f in focos if f["tema"] != principal["tema"]]
        rng = random.Random(c.semilla_a_entero(f"{entero}|{i}"))
        secundarios = rng.sample(otros, min(2, len(otros)))
        avatares.append(_construir_avatar(i + 1, locale, oferta_id, principal, secundarios, estilo, por_id, vocabulario, procedencia))
    if incluir_baseline:
        avatares.append({
            "avatar_id": f"av-{locale}-rubrica", "oferta_id": oferta_id, "locale": locale, "pais": None, "idioma": locale.split("-")[0],
            "baseline": True, "estilo_decision": c.ESTILO_RUBRICA,
            "estilo_origen": "línea base: un juez sin perfil que aplica solo los criterios de gancho, claridad y CTA de la rúbrica del QA de D6 (R1-R3); "
                             "mide si los perfiles aportan algo sobre un único evaluador",
            "preocupacion_principal": None, "preocupaciones_secundarias": [], "objeciones": [], "en_sus_palabras": [], "vocabulario": [],
            "demografia": {"edad_rango": None, "genero": None, "ocupacion": None, "origen": "sin_dato", "fuente": None},
            "nivel_evidencia": "n/a", "estado": "activo", "procedencia": dict(procedencia),
        })
    fuentes_distintas = len({f["fuente_url"] for f in frases})
    debiles = sum(1 for a in avatares if a["nivel_evidencia"] == "debil")
    adv: list[str] = []
    if n_ef < n:
        adv.append(f"Se pidieron {n} avatares y solo hay evidencia para {n_ef}: no se rellena con avatares sin respaldo.")
    if fuentes_distintas < 3:
        adv.append(f"La voz del cliente viene de {fuentes_distintas} fuente(s) distintas: el panel hereda su sesgo.")
    if debiles:
        adv.append(f"{debiles} de {n_ef} avatares se apoyan en una sola fuente (nivel_evidencia «debil»).")
    if isinstance(voz.get("_nota"), str):
        adv.append("Nota de la fuente: " + c.limpiar_texto(voz["_nota"], 500))
    adv.append("Edad, género y ocupación están sin dato: ninguna fuente los aporta con cita y el generador no los inventa.")
    return {
        "schema_version": c.ESQUEMA_VERSION, "tipo": "panel_avatares", "oferta_id": oferta_id, "locale": locale,
        "generado_en": ahora or c.ahora_utc(), "semilla": semilla,
        "fuente": {"ruta": voz_ruta, "sha256": voz_sha256, "n_frases": len(voz["frases"]), "n_frases_validas": len(frases),
                   "fuentes_distintas": fuentes_distintas},
        "limite_n": {"pedido": n, "generado": n_ef, "focos_elegibles": len(focos),
                     "motivo": "N pedido ≤ focos con evidencia" if n_ef == n else "techo = preocupaciones distintas con evidencia"},
        "frases_descartadas": descartadas, "advertencias": adv, "registro_ref": "registro_avatares.jsonl", "avatares": avatares,
    }


# ---------------------------------------------------------------------------------------------------------------
# Validación
# ---------------------------------------------------------------------------------------------------------------

def validar_panel(doc: Mapping[str, Any], voz: Mapping[str, Any] | None = None) -> list[str]:
    """Lista de problemas (vacía = válido). Con ``voz`` comprueba también que cada cita exista y no esté alterada."""
    err: list[str] = []
    if not isinstance(doc, Mapping) or doc.get("tipo") != "panel_avatares" or not isinstance(doc.get("avatares"), list):
        return ["no es un panel_avatares"]
    ids: set[str] = set()
    por_id: dict[str, str] = {}
    if voz is not None:
        frases, _ = validar_frases(voz)
        por_id = {f["frase_id"]: f["texto"] for f in frases}
    for a in doc["avatares"]:
        aid = a.get("avatar_id") if isinstance(a, Mapping) else None
        if not isinstance(aid, str) or not _RX_ID.match(aid):
            err.append(f"avatar_id inválido: {aid!r}")
            continue
        if aid in ids:
            err.append(f"{aid}: id repetido")
        ids.add(aid)
        if a.get("estado") not in ESTADOS:
            err.append(f"{aid}: estado inválido {a.get('estado')!r}")
        if a.get("estilo_decision") not in (*c.ESTILOS_DECISION, c.ESTILO_RUBRICA):
            err.append(f"{aid}: estilo_decision desconocido {a.get('estilo_decision')!r}")
        dem = a.get("demografia") or {}
        for campo in ("edad_rango", "genero", "ocupacion"):
            if dem.get(campo) is not None and not dem.get("fuente"):
                err.append(f"{aid}: demografia.{campo} tiene valor pero no cita (fuente): se inventó o falta la cita")
        if a.get("baseline"):
            continue
        princ = a.get("preocupacion_principal")
        if not isinstance(princ, Mapping) or not princ.get("frase_ids"):
            err.append(f"{aid}: sin preocupación principal respaldada por frases")
        if not a.get("en_sus_palabras"):
            err.append(f"{aid}: sin frases literales «en_sus_palabras»")
        for cita in a.get("en_sus_palabras", []):
            fid = cita.get("frase_id")
            if not cita.get("fuente_url"):
                err.append(f"{aid}/{fid}: cita sin fuente_url")
            if voz is not None:
                if fid not in por_id:
                    err.append(f"{aid}/{fid}: la frase no existe en la voz del cliente")
                elif por_id[fid] != cita.get("texto"):
                    err.append(f"{aid}/{fid}: el texto de la cita fue alterado respecto de la voz del cliente")
    if not any(a.get("estado") == "activo" and not a.get("baseline") for a in doc["avatares"] if isinstance(a, Mapping)):
        err.append("no hay ningún avatar activo (sin baseline)")
    return err


def activos(doc: Mapping[str, Any], con_baseline: bool = False) -> list[dict]:
    return [a for a in doc["avatares"] if a.get("estado") == "activo" and (con_baseline or not a.get("baseline"))]


# ---------------------------------------------------------------------------------------------------------------
# Reemplazo con registro
# ---------------------------------------------------------------------------------------------------------------

def reemplazar_avatar(doc: Mapping[str, Any], voz: Mapping[str, Any], voz_sha256: str, avatar_id: str, motivo: str,
                      calibracion: Mapping[str, Any] | None = None, calibracion_sha256: str | None = None,
                      forzar_manual: bool = False, sin_reposicion: bool = False, ahora: str | None = None) -> tuple[dict, dict]:
    """(panel nuevo, evento de registro). El avatar retirado NO se borra; el nuevo recibe un id que nunca se reutiliza.

    Solo se reemplaza lo que la calibración propuso (``propuestas_reemplazo``) o, con ``forzar_manual``, con un motivo de
    al menos 20 caracteres. Así no se «cambian avatares hasta que el pasado coincida» sin dejar rastro.
    """
    ahora = ahora or c.ahora_utc()
    motivo = c.limpiar_texto(motivo, 400)
    c.exigir(bool(motivo), "falta el motivo del reemplazo")
    nuevo = {**doc, "avatares": [dict(a) for a in doc["avatares"]]}
    viejo = next((a for a in nuevo["avatares"] if a.get("avatar_id") == avatar_id), None)
    c.exigir(viejo is not None, f"no existe {avatar_id}")
    c.exigir(viejo["estado"] == "activo" and not viejo.get("baseline"), f"{avatar_id}: solo se reemplaza un avatar activo que no sea la línea base")
    if forzar_manual:
        c.exigir(len(motivo) >= 20, "el reemplazo manual exige un motivo de al menos 20 caracteres")
        origen = "manual"
    else:
        propuestas = (calibracion or {}).get("propuestas_reemplazo") or []
        c.exigir(any(p.get("avatar_id") == avatar_id for p in propuestas),
                 f"la calibración no propone reemplazar a {avatar_id}; sin propuesta solo vale --forzar-manual con motivo")
        origen = "calibracion"
    usados = {a["preocupacion_principal"]["tema"] for a in nuevo["avatares"] if a.get("estado") == "activo" and not a.get("baseline")}
    reponedor = None
    if not sin_reposicion:
        frases, _ = validar_frases(voz)
        por_id = {f["frase_id"]: f for f in frases}
        proc = viejo["procedencia"]
        libres = [f for f in agrupar_focos(frases, proc.get("min_frases_por_foco", 1), proc.get("min_fuentes_por_foco", 1)) if f["tema"] not in usados]
        c.exigir(bool(libres), "no quedan preocupaciones con evidencia sin usar: no se repone (el panel queda en N-1); usa --sin-reposicion para retirar solo")
        num = 1 + max(int(a["avatar_id"].rsplit("-", 1)[1]) for a in nuevo["avatares"] if a["avatar_id"].rsplit("-", 1)[1].isdigit())
        lexico = [x for x in (voz.get("lexico") or []) if isinstance(x, str)]
        vocab = [c.limpiar_texto(x, 60) for x in lexico][:12]
        todos = agrupar_focos(frases, proc.get("min_frases_por_foco", 1), proc.get("min_fuentes_por_foco", 1))
        otros = [f for f in todos if f["tema"] != libres[0]["tema"]]
        rng = random.Random(c.semilla_a_entero(f"{proc.get('semilla')}|rep|{num}"))
        reponedor = _construir_avatar(num, viejo["locale"], viejo.get("oferta_id"), libres[0], rng.sample(otros, min(2, len(otros))),
                                      viejo["estilo_decision"], por_id, vocab, {**proc, "voz_cliente_sha256": voz_sha256, "reemplaza": avatar_id})
        nuevo["avatares"].append(reponedor)
    viejo.update({"estado": "retirado", "retirado_en": ahora, "motivo_retiro": motivo,
                  "reemplazado_por": reponedor["avatar_id"] if reponedor else None})
    evento = {"evento": "reemplazo", "ts": ahora, "avatar_retirado": avatar_id, "avatar_nuevo": reponedor["avatar_id"] if reponedor else None,
              "tema_retirado": viejo["preocupacion_principal"]["tema"], "tema_nuevo": reponedor["preocupacion_principal"]["tema"] if reponedor else None,
              "origen": origen, "motivo": motivo, "calibracion_sha256": calibracion_sha256, "voz_cliente_sha256": voz_sha256}
    return nuevo, evento


# ---------------------------------------------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------------------------------------------

def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m scripts.jurado.avatares", description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generar", help="genera el panel de avatares desde voz_cliente.json")
    g.add_argument("--voz", required=True)
    g.add_argument("--n", type=int, default=None, help="avatares (por defecto, parametros n_avatares = 10)")
    g.add_argument("--semilla", required=True, help="semilla registrada (número o texto)")
    g.add_argument("--salida", required=True)
    g.add_argument("--min-frases", type=int, default=1)
    g.add_argument("--min-fuentes", type=int, default=1)
    g.add_argument("--estilos", default=None, help="subconjunto separado por comas de: " + ",".join(c.ESTILOS_DECISION))
    g.add_argument("--incluir-baseline-rubrica", action="store_true", help="añade el juez sin perfil que sirve de línea base")
    g.add_argument("--oferta-id", default=None)
    g.add_argument("--parametros", default=None)
    g.add_argument("--ahora", default=None, help="marca de tiempo fija (pruebas y demostraciones reproducibles)")
    v = sub.add_parser("validar", help="valida un panel (y sus citas contra la voz del cliente si se pasa --voz)")
    v.add_argument("panel")
    v.add_argument("--voz", default=None)
    r = sub.add_parser("reemplazar", help="retira un avatar y repone otro con registro")
    r.add_argument("panel")
    r.add_argument("--avatar-id", required=True)
    r.add_argument("--voz", required=True)
    r.add_argument("--motivo", required=True)
    r.add_argument("--calibracion", default=None)
    r.add_argument("--forzar-manual", action="store_true")
    r.add_argument("--sin-reposicion", action="store_true")
    r.add_argument("--registro", default=None, help="por defecto, registro_avatares.jsonl junto al panel")
    r.add_argument("--ahora", default=None)
    return p


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.cmd == "generar":
            params = c.cargar_parametros(args.parametros)
            voz = c.leer_json(args.voz)
            n = args.n if args.n is not None else params["n_avatares"]
            estilos = [e.strip() for e in args.estilos.split(",") if e.strip()] if args.estilos else None
            doc = generar_panel(voz, c.sha256_archivo(args.voz), args.voz, n, c.parsear_semilla(args.semilla), params, args.min_frases, args.min_fuentes,
                                estilos, args.incluir_baseline_rubrica, args.oferta_id, args.ahora)
            problemas = validar_panel(doc, voz)
            c.exigir(not problemas, "panel generado inválido: " + "; ".join(problemas))
            c.escribir_json(args.salida, doc)
            reg = Path(args.salida).with_name("registro_avatares.jsonl")
            c.agregar_jsonl(reg, {"evento": "generado", "ts": doc["generado_en"], "n_pedido": n, "n_generado": doc["limite_n"]["generado"],
                                  "semilla": doc["semilla"], "voz_cliente_sha256": doc["fuente"]["sha256"], "avatares": [a["avatar_id"] for a in doc["avatares"]]})
            print(f"{len(doc['avatares'])} avatares ({doc['limite_n']['generado']} de {n} pedidos) -> {args.salida}")
            for adv in doc["advertencias"]:
                print("  aviso:", adv)
            return c.SALIDA_OK
        if args.cmd == "validar":
            doc = c.leer_json(args.panel)
            voz = c.leer_json(args.voz) if args.voz else None
            problemas = validar_panel(doc, voz)
            for p in problemas:
                print("  -", p)
            print("válido" if not problemas else f"{len(problemas)} problema(s)")
            return c.SALIDA_OK if not problemas else c.SALIDA_RECHAZO
        if args.cmd == "reemplazar":
            doc = c.leer_json(args.panel)
            voz = c.leer_json(args.voz)
            cal = c.leer_json(args.calibracion) if args.calibracion else None
            nuevo, evento = reemplazar_avatar(doc, voz, c.sha256_archivo(args.voz), args.avatar_id, args.motivo, cal,
                                              c.sha256_archivo(args.calibracion) if args.calibracion else None,
                                              args.forzar_manual, args.sin_reposicion, args.ahora)
            problemas = validar_panel(nuevo, voz)
            c.exigir(not problemas, "panel resultante inválido: " + "; ".join(problemas))
            c.escribir_json(args.panel, nuevo)
            c.agregar_jsonl(args.registro or Path(args.panel).with_name("registro_avatares.jsonl"), evento)
            print(f"{evento['avatar_retirado']} retirado; repuesto: {evento['avatar_nuevo']}")
            return c.SALIDA_OK
    except c.ErrorJurado as e:
        print(f"error: {e}", file=sys.stderr)
        return c.SALIDA_RECHAZO
    return c.SALIDA_USO


if __name__ == "__main__":
    sys.exit(main())
