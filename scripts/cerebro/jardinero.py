#!/usr/bin/env python3
"""El jardinero del domingo, EN SECO (B1-08): revisa la memoria del Cerebro y PROPONE un orden; no cambia nada. Biblioteca estándar.

Qué propone (cada ítem trae «antes», «después» y «cómo aplicarlo»; lo aplicas tú en el panel o con /cerebro-cerrar):
  · unir duplicados (parecido ≥ ``sim_dup`` 0,80 entre pendientes, decisiones vigentes o lecciones)
  · pendientes vencidos y recordatorios que vencen pronto (revisar: cerrar o mover la fecha)
  · pendientes dormidos (P2/P3/sin prioridad sin movimiento desde hace meses) y propuestas de preferencia sin resolver
  · propuestas de preferencia que ya se aprobaron o rechazaron pero siguen abiertas en la lista
  · decisiones posiblemente superadas (una decisión nueva dice «revierte / reemplaza / sustituye» y nombra a otra que sigue vigente; cadenas ``reemplaza`` rotas)
  · lecciones sin prueba (sin archivo, archivo desaparecido o con el hash cambiado)
  · decisiones del documento de decisiones que nunca se sembraron en la memoria
  · pendientes sin prioridad o sin responsable

Lo que NUNCA hace: aplicar una propuesta, borrar, reescribir o resolver una línea; tocar lo protegido (P0, categoría «riesgo», etapa X1, líneas rojas, vetos, sellos,
compliance); usar un LLM. Por defecto no escribe NADA. Con ``--guardar-propuesta --confirmo-dueno "…"`` guarda la propuesta como UN archivo nuevo en
``empresa/memoria/jardin/AAAA-MM-DD.json`` (que el panel cuenta en su bloque «Jardín»); nunca sobrescribe uno existente y no toca nada más.

Uso (desde la raíz del repositorio):
    .venv/bin/python scripts/cerebro/jardinero.py [--raiz R] [--ahora AAAA-MM-DDTHH:MM:SSZ] [--dias 7] [--json]
        [--guardar-propuesta --confirmo-dueno "lo que dijo el dueño"]
Salida: texto legible (o JSON con ``--json``). 0 = ok · 2 = uso · 6 = no se pudo guardar la propuesta.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

try:
    from scripts.cerebro import comun
except ImportError:                                  # ejecutado por ruta, no como paquete
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from scripts.cerebro import comun

DIAS_PROXIMOS = 7
DIAS_DORMIDO = {"P3": 90, "P2": 180, None: 90}       # [SUPUESTO]: ajustarlos con el uso real; no son parámetros firmados
DIAS_PREFERENCIA_SIN_RESOLVER = 14                   # [SUPUESTO]
NO_SON_TAREA = ("decision", "leccion", "regla_propuesta")      # como el panel: todo lo demás (incluido un tipo desconocido) es algo por hacer
ORDEN = ("vencido", "fusionar_duplicados", "cerrar_ya_resuelta", "decision_superada", "cadena_rota", "leccion_sin_prueba", "decision_sin_sembrar", "preferencia_sin_resolver",
         "revisar_dormido", "proximo", "sin_prioridad")
TITULOS = {
    "vencido": "Pendiente vencido", "fusionar_duplicados": "Unir duplicados", "cerrar_ya_resuelta": "Cerrar algo que ya quedó resuelto", "decision_superada": "Decisión posiblemente superada",
    "cadena_rota": "Decisión que reemplaza a otra que no existe", "leccion_sin_prueba": "Lección sin prueba", "decision_sin_sembrar": "Decisión del documento sin guardar en la memoria",
    "preferencia_sin_resolver": "Preferencia propuesta sin resolver", "revisar_dormido": "Pendiente dormido", "proximo": "Vence pronto", "sin_prioridad": "Pendiente sin prioridad o sin responsable",
}
RX_PROTEGIDO = re.compile(r"l[ií]neas?[ _]rojas?|lineas_rojas|\bveto\b|\bvetos\b|invariante|\bsellos?\b|compliance", re.IGNORECASE)
RX_SUPERA = re.compile(r"\b(revierte|revertir|reemplaza|reemplazan|sustituye|sustituyen|deroga|anula|cancela|deja sin efecto|deja de valer|en vez de|en lugar de)\b", re.IGNORECASE)
RX_J = re.compile(r"\bJ(\d{1,2})\b")
RX_FILA_J = re.compile(r"^\|\s*\*\*J(\d{1,2})\*\*\s*\|(.*)$")
RX_TITULO_J = re.compile(r"^J(\d{1,2})\b")


# ── protegidos ───────────────────────────────────────────────────────────────────────────────────────
def motivo_proteccion(e: dict[str, Any]) -> str | None:
    """Por qué el jardinero no puede proponer tocar esta línea (``None`` si no está protegida)."""
    if e.get("prioridad") == "P0":
        return "es P0 (frena gastar o activar)"
    if e.get("categoria") == "riesgo":
        return "es de categoría riesgo"
    if e.get("etapa") == "X1":
        return "es de la etapa X1 (compliance)"
    texto = f"{e.get('titulo') or ''} {e.get('detalle') or ''}"
    m = RX_PROTEGIDO.search(texto)
    if m:
        return f"menciona «{m.group(0).lower()}» (líneas rojas, vetos, sellos o compliance)"
    return None


def _entre_palabras(texto: str, ini: int, fin: int) -> str:
    """Un trozo del texto sin cortar palabras por los extremos (con «…» donde se recortó)."""
    if ini > 0 and not texto[ini - 1].isspace():
        sig = texto.find(" ", ini)
        ini = sig + 1 if 0 <= sig < fin else ini
    if fin < len(texto) and not texto[fin].isspace():
        ant = texto.rfind(" ", ini, fin)
        fin = ant if ant > ini else fin
    return ("…" if ini > 0 else "") + (comun.corto(texto[ini:fin], 150) or "") + ("…" if fin < len(texto) else "")


def _cita(e: dict[str, Any], n: int = 110) -> str:
    return f"{e.get('id')} «{comun.corto(e.get('titulo'), n) or '(sin título)'}»"


def _item(tipo: str, ids: list[str], motivo: str, antes: list[str], despues: str, como: str, fuente: str, **extra: Any) -> dict[str, Any]:
    return {"tipo": tipo, "titulo": TITULOS[tipo], "ids": ids, "motivo": motivo, "antes": antes, "despues": despues, "como_aplicar": como, "fuente": fuente, **extra}


def _grupos_parecidos(filas: list[dict[str, Any]], campos: tuple[str, ...]) -> list[list[dict[str, Any]]]:
    """Grupos de filas con parecido ≥ sim_dup en alguno de los ``campos`` (unión transitiva). Cada grupo, de la más antigua a la más nueva."""
    padre = list(range(len(filas)))

    def raiz(i: int) -> int:
        while padre[i] != i:
            padre[i] = padre[padre[i]]
            i = padre[i]
        return i

    for i in range(len(filas)):
        for j in range(i + 1, len(filas)):
            if any(filas[i].get(c) and filas[j].get(c) and comun.similitud(str(filas[i][c]), str(filas[j][c])) >= comun.SIM_DUP for c in campos):
                padre[raiz(i)] = raiz(j)
    grupos: dict[int, list[dict[str, Any]]] = {}
    for i, f in enumerate(filas):
        grupos.setdefault(raiz(i), []).append(f)
    return [sorted(g, key=lambda f: (str(f.get("ts") or ""), str(f.get("id")))) for g in grupos.values() if len(g) > 1]


# ── las comprobaciones ───────────────────────────────────────────────────────────────────────────────
def _pendientes(memoria: dict[str, Any], hoy: int, dias: int, items: list[dict[str, Any]], protegidos: list[dict[str, Any]]) -> None:
    abiertas = [e for e in memoria["pulido"] if e.get("estado") != "resuelta"]
    tareas = [e for e in abiertas if e.get("tipo") not in NO_SON_TAREA]
    resueltas = {o.get("pul_id"): o for o in memoria["preferencias"] if o.get("estado") in ("aprobada", "rechazada") and o.get("autor") == "dueno"}

    def guardar_protegido(e: dict[str, Any], motivo: str) -> None:
        if not any(p["id"] == e.get("id") for p in protegidos):
            protegidos.append({"id": e.get("id"), "titulo": comun.corto(e.get("titulo"), 110), "motivo": motivo})

    # vencidos y próximos (los protegidos también se avisan: un aviso no cambia nada)
    for e in abiertas:
        dv = comun.dia(e.get("vence"))
        if dv is None:
            continue
        prot = motivo_proteccion(e)
        if dv < hoy:
            item = _item("vencido", [e["id"]], f"venció el {comun.corto(e.get('vence'), 10)}, hace {hoy - dv} día(s)", [f"{_cita(e)} · vence {comun.corto(e.get('vence'), 10)}"],
                         "Cerrado, o con una fecha nueva." if not prot else "Lo decides tú; no lo cierro ni lo muevo.",
                         "Si ya se hizo, márcalo como resuelto en #/cerebro. Si sigue, anota uno nuevo con la fecha correcta (/cerebro-cerrar) y cierra este." if not prot
                         else f"Protegido ({prot}): solo tú decides qué hacer con él.", comun.REL_PULIDO, protegido=bool(prot))
            items.append(item)
        elif dv - hoy <= dias:
            items.append(_item("proximo", [e["id"]], f"vence {'hoy' if dv == hoy else 'en ' + str(dv - hoy) + ' día(s)'} ({comun.corto(e.get('vence'), 10)})", [_cita(e)],
                               "Avisado a tiempo.", "Nada que cambiar en la memoria: es un recordatorio para que lo hagas.", comun.REL_PULIDO, protegido=bool(prot)))

    # duplicados (solo lo no protegido)
    for g in _grupos_parecidos(tareas + [e for e in abiertas if e.get("tipo") == "regla_propuesta"], ("titulo",)):
        bloqueados = [(e, motivo_proteccion(e)) for e in g if motivo_proteccion(e)]
        if bloqueados:
            for e, m in bloqueados:
                guardar_protegido(e, f"parece duplicado de otro, pero {m}")
            continue
        queda, sobran = g[0], g[1:]
        items.append(_item("fusionar_duplicados", [e["id"] for e in g], f"{len(g)} pendientes abiertos dicen casi lo mismo (parecido ≥ {comun.SIM_DUP})", [_cita(e) for e in g],
                           f"Queda {queda['id']}; se cierran {', '.join(e['id'] for e in sobran)}.",
                           f"En #/cerebro marca como resueltos: {', '.join(e['id'] for e in sobran)}. Si el detalle de alguno sobra en {queda['id']}, cópialo a mano antes.", comun.REL_PULIDO))

    # preferencias: ya resueltas pero abiertas · sin resolver hace mucho
    for e in abiertas:
        if e.get("tipo") != "regla_propuesta" or e.get("categoria") != "pref":
            continue
        ya = resueltas.get(e.get("id"))
        if ya:
            items.append(_item("cerrar_ya_resuelta", [e["id"], ya.get("id")], f"la preferencia ya quedó {ya.get('estado')} ({ya.get('id')}) pero la propuesta sigue abierta", [_cita(e)],
                               "Propuesta cerrada.", f"En #/cerebro marca {e['id']} como resuelta.", comun.REL_PULIDO))
            continue
        edad = hoy - (comun.dia(e.get("ts")) or hoy)
        if edad >= DIAS_PREFERENCIA_SIN_RESOLVER:
            items.append(_item("preferencia_sin_resolver", [e["id"]], f"lleva {edad} días esperando tu decisión", [_cita(e)], "Aprobada o rechazada.",
                               "Dilo en /cerebro-cerrar («apruebo» o «rechazo» con tus palabras): hasta entonces ninguna skill la lee.", comun.REL_PULIDO))

    # dormidos
    for e in tareas:
        if comun.dia(e.get("vence")) is not None:
            continue
        edad = hoy - (comun.dia(e.get("ts")) or hoy)
        limite = DIAS_DORMIDO.get(e.get("prioridad") if e.get("prioridad") in ("P2", "P3") else None)
        if e.get("prioridad") in ("P0", "P1") or edad < (limite or 10 ** 9):
            continue
        m = motivo_proteccion(e)
        if m:
            guardar_protegido(e, f"dormido hace {edad} días, pero {m}")
            continue
        items.append(_item("revisar_dormido", [e["id"]], f"lleva {edad} días sin moverse ({e.get('prioridad') or 'sin prioridad'})", [_cita(e)], "Retomado con una fecha, o cerrado.",
                           "¿La retomas? Ponle prioridad y fecha en #/cerebro. Si ya no importa, márcalo como resuelto.", comun.REL_PULIDO))

    # sin prioridad o sin responsable
    sin = [e for e in tareas if (not e.get("prioridad") or not e.get("responsable"))]
    if sin:
        items.append(_item("sin_prioridad", [e["id"] for e in sin][:12], f"{len(sin)} pendiente(s) abiertos sin prioridad o sin responsable", [_cita(e) for e in sin[:6]],
                           "Cada uno con responsable y prioridad (P0 frena gastar · P1 frena una etapa · P2 mejora · P3 idea).",
                           "Asígnalos en #/cerebro, o dímelos y los vuelvo a anotar completos con /cerebro-cerrar.", comun.REL_PULIDO))


def _decisiones(memoria: dict[str, Any], raiz: Path, items: list[dict[str, Any]], protegidos: list[dict[str, Any]]) -> None:
    objetos = memoria["decisiones"]
    ids = {o.get("id") for o in objetos}
    vigentes = comun.decisiones_vigentes(objetos)
    por_j: dict[int, dict[str, Any]] = {}
    for o in vigentes:
        m = RX_TITULO_J.match(str(o.get("titulo") or ""))
        if m:
            por_j[int(m.group(1))] = o

    for o in objetos:                                    # cadena rota
        if o.get("reemplaza") and o["reemplaza"] not in ids:
            items.append(_item("cadena_rota", [o.get("id"), o["reemplaza"]], f"{o.get('id')} dice reemplazar a {o['reemplaza']}, que no existe", [_cita(o)],
                               "La cadena queda clara.", "Revisa el id con /cerebro-cerrar: guarda la decisión de nuevo con el id correcto en «reemplaza».", comun.REL_DECISIONES))

    for g in _grupos_parecidos(vigentes, ("titulo", "detalle")):
        items.append(_item("fusionar_duplicados", [o.get("id") for o in g], f"{len(g)} decisiones vigentes dicen casi lo mismo (parecido ≥ {comun.SIM_DUP})", [_cita(o) for o in g],
                           f"Rige {g[-1].get('id')} (la última); las demás quedan como reemplazadas.",
                           f"Con /cerebro-cerrar guarda una decisión con «reemplaza: {g[0].get('id')}» (una por cada anterior). Las decisiones no se editan ni se borran.", comun.REL_DECISIONES))

    # superadas: la decisión nueva (en la memoria o en el documento de decisiones) dice «revierte / reemplaza…» y nombra a otra que sigue vigente
    fuentes: list[tuple[str, str, str]] = []             # (J que habla, texto, fuente)
    for o in vigentes:
        m = RX_TITULO_J.match(str(o.get("titulo") or ""))
        if m:
            fuentes.append((f"J{int(m.group(1))}", f"{o.get('titulo') or ''} {o.get('detalle') or ''}", comun.REL_DECISIONES))
    doc, _ = comun.leer(raiz, comun.REL_DOC_DECISIONES, comun.TOPE_DOC)
    if doc is not None:
        for linea in doc.decode("utf-8", "replace").splitlines():
            m = RX_FILA_J.match(linea)
            if m:
                fuentes.append((f"J{int(m.group(1))}", linea, comun.REL_DOC_DECISIONES))
    vistos: set[tuple[int, int]] = set()
    for quien, texto, fuente in fuentes:
        n_quien = int(quien[1:])
        for v in RX_SUPERA.finditer(texto):
            for ref in RX_J.finditer(texto[v.end(): v.end() + 80]):
                n_ref = int(ref.group(1))
                destino = por_j.get(n_ref)
                if n_ref == n_quien or destino is None or (n_quien, n_ref) in vistos:
                    continue
                vistos.add((n_quien, n_ref))
                frase = _entre_palabras(re.sub(r"[*`|]", "", texto), max(0, v.start() - 40), v.end() + 80)
                items.append(_item("decision_superada", [destino.get("id")], f"{quien} dice «{v.group(0).lower()}» y nombra a J{n_ref}, que sigue marcada como vigente ({destino.get('id')})",
                                   [f"{destino.get('id')} «{comun.corto(destino.get('titulo'), 90)}» (vigente)", f"{quien}: «{frase}»"],
                                   f"Si {quien} la reemplaza del todo: {destino.get('id')} deja de regir. Si solo la cambia en parte: ambas rigen y se anota qué parte.",
                                   f"Tú decides. Si la reemplaza, con /cerebro-cerrar guarda la decisión nueva con «reemplaza: {destino.get('id')}»; si es parcial, no hagas nada.", fuente))

    # decisiones del documento que nunca se sembraron
    if doc is not None:
        en_doc = sorted({int(m.group(1)) for linea in doc.decode("utf-8", "replace").splitlines() if (m := RX_FILA_J.match(linea))})
        sembradas = {int(m.group(1)) for o in objetos if (m := RX_TITULO_J.match(str(o.get("titulo") or "")))}
        faltan = [n for n in en_doc if n not in sembradas]
        if faltan:
            items.append(_item("decision_sin_sembrar", [f"J{n}" for n in faltan], f"el documento de decisiones trae {len(faltan)} decisión(es) que no están guardadas en la memoria",
                               [f"J{n}" for n in faltan], "Guardadas (cada una con sus palabras y el hash del documento como prueba).",
                               "Con /cerebro-cerrar, una por una y con tu confirmación: los agentes que corren solos solo ven la memoria, no el documento.", comun.REL_DOC_DECISIONES))
        hash_actual = comun.sha256_de(raiz, comun.REL_DOC_DECISIONES)
        cambiadas = [o for o in objetos if any(isinstance(e, dict) and e.get("ruta") == comun.REL_DOC_DECISIONES and str(e.get("sha256", "")).removeprefix("sha256:") != hash_actual
                                                for e in (o.get("evidencia") or []))]
        if cambiadas and not faltan:
            items.append(_item("decision_sin_sembrar", [o.get("id") for o in cambiadas][:12], "el documento de decisiones cambió desde que se guardaron estas decisiones",
                               [f"{len(cambiadas)} decisiones citan una versión anterior del documento"], "Comprobado que ninguna cambió de sentido.",
                               "Compara las decisiones guardadas con el documento; si alguna cambió, guárdala de nuevo con «reemplaza».", comun.REL_DOC_DECISIONES))


def _lecciones(memoria: dict[str, Any], raiz: Path, items: list[dict[str, Any]]) -> None:
    for o in memoria["lecciones"]:
        evidencia = o.get("evidencia") if isinstance(o.get("evidencia"), list) else []
        problemas = []
        if not evidencia:
            problemas.append("no trae ningún archivo de prueba")
        for e in evidencia:
            ruta = e.get("ruta") if isinstance(e, dict) else None
            if not isinstance(ruta, str):
                problemas.append("una prueba sin ruta")
                continue
            actual = comun.sha256_de(raiz, ruta)
            if actual is None:
                problemas.append(f"el archivo {ruta} ya no existe")
            elif str(e.get("sha256", "")).removeprefix("sha256:") != actual:
                problemas.append(f"el archivo {ruta} cambió desde que se guardó la lección")
        if problemas:
            items.append(_item("leccion_sin_prueba", [o.get("id")], "; ".join(problemas), [_cita(o)], "La lección con su prueba al día, o archivada.",
                               "Si el archivo cambió a propósito, guarda la lección de nuevo con la prueba actual (/cerebro-cerrar). Si no hay prueba, es una anécdota: pásala a pendiente o déjala.",
                               comun.REL_LECCIONES))


def proponer(raiz: Path, ahora: dt.datetime | None = None, dias: int = DIAS_PROXIMOS) -> dict[str, Any]:
    """La propuesta del jardinero: ``{generado_en, revisado, items, protegidos, avisos}``. No escribe ni cambia nada."""
    momento = (ahora or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc)
    hoy = comun.hoy_de(momento)
    memoria = comun.cargar_memoria(raiz)
    items: list[dict[str, Any]] = []
    protegidos: list[dict[str, Any]] = []
    _pendientes(memoria, hoy, dias, items, protegidos)
    _decisiones(memoria, raiz, items, protegidos)
    _lecciones(memoria, raiz, items)
    items.sort(key=lambda x: (ORDEN.index(x["tipo"]), str(x["ids"][0]) if x["ids"] else ""))
    for n, x in enumerate(items, 1):
        x["n"] = n
    abiertas = [e for e in memoria["pulido"] if e.get("estado") != "resuelta"]
    return {
        "generado_en": momento.strftime("%Y-%m-%dT%H:%M:%SZ"), "dias_proximos": dias,
        "revisado": {"pendientes_abiertos": sum(1 for e in abiertas if e.get("tipo") not in NO_SON_TAREA), "reglas_o_preferencias_propuestas": sum(1 for e in abiertas if e.get("tipo") == "regla_propuesta"),
                     "decisiones_vigentes": len(comun.decisiones_vigentes(memoria["decisiones"])), "lecciones": len(memoria["lecciones"]),
                     "preferencias_aprobadas": len(comun.preferencias_vigentes(memoria["preferencias"]))},
        "items": items, "protegidos": protegidos, "avisos": memoria["avisos"],
        "garantias": {"aplica_algo": False, "borra_algo": False, "texto": "El jardinero solo propone. Lo aplicas tú; las líneas de la memoria nunca se editan ni se borran."},
    }


def a_texto(r: dict[str, Any]) -> str:
    rv = r["revisado"]
    L = [f"JARDINERO · propuesta del {r['generado_en'][:10]} (en seco: no cambié nada)",
         f"Revisé {rv['pendientes_abiertos']} pendientes abiertos, {rv['reglas_o_preferencias_propuestas']} reglas o preferencias propuestas, {rv['decisiones_vigentes']} decisiones vigentes, "
         f"{rv['lecciones']} lecciones y {rv['preferencias_aprobadas']} preferencias aprobadas."]
    if not r["items"]:
        L.append("Todo en orden: no tengo nada que proponer esta semana.")
    else:
        L.append(f"Propongo {len(r['items'])} cosa(s). Tú decides cuáles hacer; yo no aplico ninguna por mi cuenta.")
    for x in r["items"]:
        L.append("")
        L.append(f"{x['n']}. {x['titulo']} · {', '.join(str(i) for i in x['ids'][:6])}" + ("…" if len(x["ids"]) > 6 else ""))
        L.append(f"   Por qué: {x['motivo']}.")
        for a in x["antes"][:6]:
            L.append(f"   Antes:   {a}")
        L.append(f"   Después: {x['despues']}")
        L.append(f"   Cómo:    {x['como_aplicar']}")
    if r["protegidos"]:
        L.append("")
        L.append(f"No toqué {len(r['protegidos'])} cosa(s) protegidas:")
        for p in r["protegidos"][:6]:
            L.append(f"   {p['id']} «{p['titulo']}» · {p['motivo']}")
    for a in r["avisos"][:3]:
        L.append(f"Aviso: {a}")
    L.append("")
    L.append("Para dejar esta propuesta guardada (el panel la cuenta en «Jardín»), corre de nuevo con --guardar-propuesta --confirmo-dueno \"…\".")
    return "\n".join(L)


# ── guardar la propuesta (único efecto posible; solo con la confirmación del dueño) ──────────────────
class ErrorGuardar(Exception):
    pass


def guardar_propuesta(raiz: Path, propuesta: dict[str, Any], confirmacion: str) -> str:
    """Escribe UN archivo nuevo ``empresa/memoria/jardin/AAAA-MM-DD[-N].json`` y devuelve su ruta relativa. Nunca sobrescribe y no toca nada más."""
    frase = comun.corto(confirmacion, 200)
    if not frase or len(frase) < 2:
        raise ErrorGuardar("Falta la confirmación del dueño (--confirmo-dueno con sus palabras).")
    base = os.path.realpath(raiz)
    actual = base
    for parte in ("empresa", "memoria", "jardin"):
        siguiente = os.path.join(actual, parte)
        if os.path.islink(siguiente):
            real = os.path.realpath(siguiente)
            if real != base and not real.startswith(base + os.sep):
                raise ErrorGuardar("La carpeta de destino escapa de la raíz por un enlace simbólico.")
            siguiente = real
        elif not os.path.isdir(siguiente):
            if parte == "empresa":
                raise ErrorGuardar("No existe la carpeta empresa/ en esta raíz.")
            try:
                os.mkdir(siguiente, 0o755)
            except OSError as exc:
                raise ErrorGuardar(f"No se pudo crear {parte}/: {exc.strerror}.") from exc
        actual = siguiente
    cuerpo = {"schema": "jardin/1", "generado_en": propuesta["generado_en"], "estado": "propuesta", "confirmada_por_dueno": frase, "revisado": propuesta["revisado"],
              "items": propuesta["items"], "protegidos": propuesta["protegidos"],
              "sha256_items": hashlib.sha256(json.dumps(propuesta["items"], ensure_ascii=True, sort_keys=True).encode("ascii")).hexdigest()}
    datos = (json.dumps(cuerpo, ensure_ascii=True, indent=2, allow_nan=False) + "\n").encode("ascii")
    dia = propuesta["generado_en"][:10]
    for k in range(1, 100):
        nombre = f"{dia}.json" if k == 1 else f"{dia}-{k}.json"
        try:
            fd = os.open(os.path.join(actual, nombre), os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o644)
        except FileExistsError:
            continue
        except OSError as exc:
            raise ErrorGuardar(f"No se pudo guardar: {exc.strerror}.") from exc
        try:
            os.write(fd, datos)
            os.fsync(fd)
        finally:
            os.close(fd)
        return f"{comun.REL_JARDIN}/{nombre}"
    raise ErrorGuardar("Hay demasiadas propuestas de hoy.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jardinero.py", description=__doc__.split("\n\n")[0])
    ap.add_argument("--raiz", default=None, help="raíz del repositorio (defecto: FABRICA_RAIZ o la carpeta del código)")
    ap.add_argument("--ahora", default=None, help="momento de referencia AAAA-MM-DDTHH:MM:SSZ (para pruebas)")
    ap.add_argument("--dias", type=int, default=DIAS_PROXIMOS, help="ventana de «vence pronto» en días")
    ap.add_argument("--json", action="store_true", help="salida JSON en lugar de texto")
    ap.add_argument("--guardar-propuesta", action="store_true", help="guarda la propuesta como un archivo nuevo en empresa/memoria/jardin/ (exige --confirmo-dueno)")
    ap.add_argument("--confirmo-dueno", default=None, help="las palabras del dueño que confirman guardar la propuesta")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code not in (0, None) else 0
    raiz = Path(args.raiz) if args.raiz else comun.raiz_por_defecto()
    ahora = None
    if args.ahora:
        try:
            ahora = comun.parsear_ahora(args.ahora)
        except ValueError:
            ahora = None
            args.dias = -1
    if not raiz.is_dir() or not 0 <= args.dias <= 365 or (args.guardar_propuesta and not args.confirmo_dueno) or (args.confirmo_dueno and not args.guardar_propuesta):
        print(json.dumps({"ok": False, "mensaje": "--raiz no es una carpeta, --dias / --ahora no son válidos, o --guardar-propuesta y --confirmo-dueno deben ir juntos."}, ensure_ascii=False), file=sys.stderr)
        return 2
    propuesta = proponer(raiz, ahora, args.dias)
    guardado = None
    if args.guardar_propuesta:
        try:
            guardado = guardar_propuesta(raiz, propuesta, args.confirmo_dueno)
        except ErrorGuardar as exc:
            print(json.dumps({"ok": False, "mensaje": str(exc)}, ensure_ascii=False), file=sys.stderr)
            return 6
    if args.json:
        print(json.dumps({**propuesta, "guardada_en": guardado}, ensure_ascii=False, indent=2))
    else:
        print(a_texto(propuesta) + (f"\n\nPropuesta guardada en {guardado}." if guardado else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
