#!/usr/bin/env python3
"""Juicio por IA con las reglas intactas (D1, Modo D).

La IA propone, el código dispone. Dos jueces independientes (A y B) llenan lo que solo se puede
juzgar mirando una oferta: las puertas, los componentes de transferibilidad y los reencuadres.
Cada opinión lleva su evidencia. Este módulo las consolida con reglas FIJAS que ninguna IA puede aflojar:

  - Una opinión sin evidencia suficiente no cuenta (queda «sin evaluar», nunca se asume).
  - Puerta: SOLO se libera (false) si los dos jueces dicen false con evidencia. Si cualquiera veta
    (true) con evidencia, el veto prevalece y se marca para revisión. Una sola opinión no alcanza.
  - Transferibilidad: si los dos jueces están dentro de la tolerancia se toma el valor MÁS BAJO;
    si discrepan más, queda sin evaluar.
  - Reencuadre: cuenta solo si lo sustentan los dos jueces.
  - Toda cita se VERIFICA contra el material: si no aparece literalmente, la opinión no cuenta (una IA no puede
    inventar evidencia). Un veto o un número exigen una cita real; solo liberar una puerta puede apoyarse en
    «AUSENCIA: …», que no se puede citar.
  - La IA solo completa lo que está en `null`: no pisa lo que ya puso una persona. Si discrepa, se informa.
  - La IA NO puede completar un dato medido (p. ej. `entrantes_30d`): no hay campo de juicio para eso.

Además `medir_acuerdo` compara la ficha llenada por la IA con la de una persona: la automatización solo
sube de nivel («humano en todo» → «muestreo») con casos suficientes, acuerdo alto y CERO «falsos libres»
(la IA liberó una puerta que la persona había vetado).

Uso (desde la raíz, con .venv):
    .venv/bin/python -m scripts.modelado.juicio consolidar FICHAS.json A.json B.json --parametros P.yaml --salida NUEVA.json
    .venv/bin/python -m scripts.modelado.juicio acuerdo FICHA_IA.json FICHA_HUMANA.json --parametros P.yaml
Códigos de salida: los de puntaje_modelar (0, 2, 3, 5).
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
import unicodedata
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from scripts.modelado import puntaje_modelar as pm
from scripts.modelado.puntaje_modelar import PUERTAS, REENCUADRES, TRANSFERIBILIDAD, ErrorValidacion


# ---------------------------------------------------------------------------
# Opiniones individuales
# ---------------------------------------------------------------------------

def _evidencia_ok(evidencia: Any, minimo: int) -> bool:
    return isinstance(evidencia, str) and len(evidencia.strip()) >= minimo


def opinion_puerta(entrada: Any, campo: str, minimo: int) -> tuple[bool | None, str | None]:
    """(valor, nota) de una puerta. Sin evidencia suficiente el valor es None y la nota lo explica."""
    if entrada is None:
        return None, None
    e = pm._mapa(entrada, campo, ("valor", "evidencia"))
    if e["valor"] is None:
        return None, None
    if not isinstance(e["valor"], bool):
        raise ErrorValidacion(f"{campo}.valor: true, false o null")
    if not _evidencia_ok(e["evidencia"], minimo):
        return None, f"{campo}: opinión sin evidencia suficiente (mín. {minimo} caracteres); no cuenta"
    return e["valor"], None


def opinion_ratio(entrada: Any, campo: str, minimo: int) -> tuple[Decimal | None, str | None]:
    """(valor 0-1, nota) de un componente de transferibilidad."""
    if entrada is None:
        return None, None
    e = pm._mapa(entrada, campo, ("valor", "evidencia"))
    if e["valor"] is None:
        return None, None
    valor = pm._ratio(e["valor"], f"{campo}.valor")
    if not _evidencia_ok(e["evidencia"], minimo):
        return None, f"{campo}: opinión sin evidencia suficiente (mín. {minimo} caracteres); no cuenta"
    return valor, None


def opinion_reencuadres(lista: Any, campo: str, minimo: int) -> tuple[list[str], list[str]]:
    """(ids con evidencia, notas) de los reencuadres que propone un juez."""
    if lista is None:
        return [], []
    if not isinstance(lista, list):
        raise ErrorValidacion(f"{campo}: se esperaba una lista")
    validos, notas = [], []
    for i, item in enumerate(lista):
        e = pm._mapa(item, f"{campo}[{i}]", ("id", "evidencia"))
        if e["id"] not in REENCUADRES:
            raise ErrorValidacion(f"{campo}[{i}].id: {e['id']!r} desconocido; válidos: {REENCUADRES}")
        if _evidencia_ok(e["evidencia"], minimo):
            validos.append(e["id"])
        else:
            notas.append(f"{campo}: reencuadre {e['id']} sin evidencia suficiente; no cuenta")
    return validos, notas


# ---------------------------------------------------------------------------
# Verificación de citas contra el material
# ---------------------------------------------------------------------------

def _normalizar_cita(texto: Any) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", str(texto))).casefold().strip()


def pajar_de_material(material: Mapping[str, Any]) -> str:
    """Todo el texto del material (anuncios y páginas de venta), normalizado, para buscar citas."""
    partes = [a.get("texto", "") for a in material.get("anuncios", [])]
    for pagina in material.get("paginas", []):
        partes += [pagina.get("titulo", ""), pagina.get("texto", "")]
    return _normalizar_cita(" ".join(partes))


def _revisar_cita(entrada: Any, etiqueta: str, pajar: str, permite_ausencia: bool, notas: list[str]) -> None:
    """Si la cita no está en el material, vacía la evidencia (la opinión dejará de contar)."""
    if not isinstance(entrada, dict) or entrada.get("valor", True) is None:
        return
    evidencia = entrada.get("evidencia")
    if isinstance(evidencia, str) and evidencia.strip().upper().startswith("AUSENCIA:") and permite_ausencia:
        return
    if isinstance(evidencia, str) and evidencia.strip() and _normalizar_cita(evidencia) in pajar:
        return
    entrada["evidencia"] = ""
    notas.append(f"{etiqueta}: la cita no aparece en el material"
                 + ("" if permite_ausencia else " (un veto, un número o un reencuadre exigen cita literal)")
                 + "; la opinión no cuenta")


def verificar_citas(doc: Any, pajar: str) -> tuple[Any, dict[str, list[str]]]:
    """Copia del juicio donde toda evidencia no verificable queda vacía, y las notas por `modelo_id`.

    Una puerta en `false` puede apoyarse en «AUSENCIA: …»; un veto (`true`), un número y un reencuadre
    necesitan una cita literal del material (normalizada en mayúsculas, espacios y acentos compuestos).
    """
    nuevo = copy.deepcopy(doc)
    notas: dict[str, list[str]] = {}
    if not isinstance(nuevo, dict) or not isinstance(nuevo.get("ofertas"), list):
        return nuevo, notas
    for oferta in nuevo["ofertas"]:
        if not isinstance(oferta, dict):
            continue
        mid = str(oferta.get("modelo_id"))
        lista = notas.setdefault(mid, [])
        for nombre, entrada in (oferta.get("puertas") or {}).items():
            _revisar_cita(entrada, f"puerta {nombre}", pajar,
                          isinstance(entrada, dict) and entrada.get("valor") is False, lista)
        for r in oferta.get("reencuadres") or []:
            _revisar_cita(r, f"reencuadre {r.get('id') if isinstance(r, dict) else '?'}", pajar, False, lista)
        for m in oferta.get("mercados") or []:
            if not isinstance(m, dict):
                continue
            pais = m.get("mercado")
            for nombre, entrada in (m.get("transferibilidad") or {}).items():
                _revisar_cita(entrada, f"{pais} {nombre}", pajar, False, lista)
            for r in m.get("reencuadres_mercado") or []:
                _revisar_cita(r, f"{pais} reencuadre {r.get('id') if isinstance(r, dict) else '?'}", pajar, False, lista)
    return nuevo, notas


# ---------------------------------------------------------------------------
# Consolidación de dos jueces
# ---------------------------------------------------------------------------

def consolidar_puerta(a: bool | None, b: bool | None) -> tuple[bool | None, str | None]:
    """Regla asimétrica: el veto prevalece; liberar exige a los dos jueces."""
    if a is True or b is True:
        if a is not None and b is not None and a != b:
            return True, "un juez veta y el otro libera: el veto prevalece; revisar"
        if a is None or b is None:
            return True, "veto de un solo juez (el otro sin opinión válida); revisar"
        return True, None
    if a is False and b is False:
        return False, None
    if (a is None) != (b is None):
        return None, "solo un juez opinó: no alcanza para liberar la puerta"
    return None, None


def consolidar_ratio(a: Decimal | None, b: Decimal | None, tolerancia: Decimal) -> tuple[Decimal | None, str | None]:
    """Dentro de la tolerancia: el valor más bajo. Fuera, o con un solo juez: sin evaluar."""
    if a is None or b is None:
        return None, ("solo un juez opinó: queda sin evaluar" if (a is None) != (b is None) else None)
    if abs(a - b) <= tolerancia:
        return min(a, b), None
    return None, f"los jueces discrepan ({format(a, 'f')} vs {format(b, 'f')}) más que la tolerancia: queda sin evaluar"


def _normalizar_juicio(doc: Any, p: Mapping[str, Any], nombre: str) -> dict[str, dict[str, Any]]:
    minimo = p["modelado_evidencia_min_caracteres"]
    raiz = pm._mapa(doc, nombre, ("schema_version", "juez", "ofertas"))
    if raiz["schema_version"] != "2.0.0":
        raise ErrorValidacion(f"{nombre}.schema_version: {raiz['schema_version']!r} no soportada (MAJOR 1)")
    if not isinstance(raiz["ofertas"], list):
        raise ErrorValidacion(f"{nombre}.ofertas: se esperaba una lista")
    salida: dict[str, dict[str, Any]] = {}
    for i, o in enumerate(raiz["ofertas"]):
        ruta = f"{nombre}.ofertas[{i}]"
        o = pm._mapa(o, ruta, ("modelo_id", "mercados"), ("puertas", "reencuadres"))
        if o["modelo_id"] in salida:
            raise ErrorValidacion(f"{ruta}.modelo_id: «{o['modelo_id']}» repetido")
        puertas_crudas = pm._mapa(o.get("puertas") or {}, f"{ruta}.puertas", (), PUERTAS)
        notas: list[str] = []
        puertas = {}
        for g in PUERTAS:
            puertas[g], nota = opinion_puerta(puertas_crudas.get(g), f"{ruta}.puertas.{g}", minimo)
            notas += [nota] if nota else []
        reen, n2 = opinion_reencuadres(o.get("reencuadres"), f"{ruta}.reencuadres", minimo)
        mercados: dict[str, dict[str, Any]] = {}
        if not isinstance(o["mercados"], list):
            raise ErrorValidacion(f"{ruta}.mercados: se esperaba una lista")
        for j, m in enumerate(o["mercados"]):
            rm = f"{ruta}.mercados[{j}]"
            m = pm._mapa(m, rm, ("mercado",), ("transferibilidad", "reencuadres_mercado"))
            pm._pais(m["mercado"], f"{rm}.mercado")
            trans_crudas = pm._mapa(m.get("transferibilidad") or {}, f"{rm}.transferibilidad", (), TRANSFERIBILIDAD)
            trans = {}
            for k in TRANSFERIBILIDAD:
                trans[k], nota = opinion_ratio(trans_crudas.get(k), f"{rm}.transferibilidad.{k}", minimo)
                notas += [nota] if nota else []
            rme, n3 = opinion_reencuadres(m.get("reencuadres_mercado"), f"{rm}.reencuadres_mercado", minimo)
            mercados[m["mercado"]] = {"transferibilidad": trans, "reencuadres_mercado": rme}
            notas += n3
        salida[o["modelo_id"]] = {"puertas": puertas, "reencuadres": reen, "mercados": mercados,
                                  "notas": notas + n2}
    return salida


def consolidar(juicio_a: Any, juicio_b: Any, p: Mapping[str, Any],
               material: Mapping[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Consolida dos juicios independientes. Devuelve, por `modelo_id`, lo que SÍ puede pasar a la ficha.

    Con `material`, cada cita se verifica antes de consolidar (recomendado siempre; la CLI lo exige).

    Errores: ErrorValidacion si algún juicio no cumple el formato (campo desconocido, id inválido, valor fuera de rango).
    """
    notas_citas: dict[str, list[str]] = {}
    if material is not None:
        pajar = pajar_de_material(material)
        juicio_a, na = verificar_citas(juicio_a, pajar)
        juicio_b, nb = verificar_citas(juicio_b, pajar)
        for origen in (na, nb):
            for mid, lista in origen.items():
                notas_citas.setdefault(mid, []).extend(lista)
    a = _normalizar_juicio(juicio_a, p, "juicio_a")
    b = _normalizar_juicio(juicio_b, p, "juicio_b")
    vacio = {"puertas": {g: None for g in PUERTAS}, "reencuadres": [], "mercados": {}, "notas": []}
    tolerancia = p["modelado_juicio_tolerancia"]
    resultado: dict[str, dict[str, Any]] = {}
    for modelo_id in sorted(set(a) | set(b)):
        ja, jb = a.get(modelo_id, vacio), b.get(modelo_id, vacio)
        notas = [f"juicio IA {modelo_id}: {n}" for n in notas_citas.get(modelo_id, []) + ja["notas"] + jb["notas"]]
        puertas = {}
        for g in PUERTAS:
            puertas[g], nota = consolidar_puerta(ja["puertas"][g], jb["puertas"][g])
            notas += [f"juicio IA {modelo_id}: puerta {g}: {nota}"] if nota else []
        reencuadres = sorted(set(ja["reencuadres"]) & set(jb["reencuadres"]))
        notas += [f"juicio IA {modelo_id}: reencuadre {r} lo sustenta un solo juez; no cuenta"
                  for r in sorted(set(ja["reencuadres"]) ^ set(jb["reencuadres"]))]
        mercados = {}
        for pais in sorted(set(ja["mercados"]) | set(jb["mercados"])):
            ma = ja["mercados"].get(pais, {"transferibilidad": {k: None for k in TRANSFERIBILIDAD}, "reencuadres_mercado": []})
            mb = jb["mercados"].get(pais, {"transferibilidad": {k: None for k in TRANSFERIBILIDAD}, "reencuadres_mercado": []})
            trans = {}
            for k in TRANSFERIBILIDAD:
                trans[k], nota = consolidar_ratio(ma["transferibilidad"][k], mb["transferibilidad"][k], tolerancia)
                notas += [f"juicio IA {modelo_id}/{pais}: {k}: {nota}"] if nota else []
            mercados[pais] = {"transferibilidad": trans,
                              "reencuadres_mercado": sorted(set(ma["reencuadres_mercado"]) & set(mb["reencuadres_mercado"]))}
        resultado[modelo_id] = {"puertas": puertas, "reencuadres": reencuadres, "mercados": mercados, "notas": notas}
    return resultado


# ---------------------------------------------------------------------------
# Aplicar a la ficha (solo completa lo que está en null)
# ---------------------------------------------------------------------------

def aplicar(fichas: Any, consolidado: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], list[str], list[str]]:
    """Copia de las fichas con lo consolidado donde había `null`. Devuelve (fichas, cambios, conflictos).

    Nunca pisa un valor ya presente (puesto por una persona o por una corrida anterior): si la IA discrepa,
    el desacuerdo se informa en `conflictos` y la ficha queda como estaba. Los reencuadres solo se suman.
    """
    nuevo = copy.deepcopy(fichas)
    cambios: list[str] = []
    conflictos: list[str] = []
    for oferta in nuevo["ofertas"]:
        cons = consolidado.get(oferta["modelo_id"])
        if cons is None:
            continue
        mid = oferta["modelo_id"]
        for g in PUERTAS:
            ia, actual = cons["puertas"][g], oferta["puertas"][g]
            if ia is None:
                continue
            if actual is None:
                oferta["puertas"][g] = ia
                cambios.append(f"{mid}: puerta {g} = {str(ia).lower()}")
            elif actual != ia:
                conflictos.append(f"{mid}: puerta {g}: la ficha dice {str(actual).lower()} y la IA {str(ia).lower()}; no se cambia")
        for r in cons["reencuadres"]:
            if r not in oferta["reencuadres"]:
                oferta["reencuadres"].append(r)
                cambios.append(f"{mid}: reencuadre {r}")
        for mercado in oferta["mercados"]:
            mc = cons["mercados"].get(mercado["mercado"])
            if mc is None:
                continue
            for k in TRANSFERIBILIDAD:
                ia, actual = mc["transferibilidad"][k], mercado["transferibilidad"][k]
                if ia is None:
                    continue
                if actual is None:
                    mercado["transferibilidad"][k] = format(ia, "f")
                    cambios.append(f"{mid}/{mercado['mercado']}: {k} = {format(ia, 'f')}")
                elif pm._decimal(actual, k) != ia:
                    conflictos.append(f"{mid}/{mercado['mercado']}: {k}: la ficha dice {actual} y la IA {format(ia, 'f')}; no se cambia")
            extra = mercado.setdefault("reencuadres_mercado", [])
            for r in mc["reencuadres_mercado"]:
                if r not in extra:
                    extra.append(r)
                    cambios.append(f"{mid}/{mercado['mercado']}: reencuadre {r}")
        oferta.setdefault("pendiente", [])
        oferta["pendiente"] += [n for n in cons["notas"] if n not in oferta["pendiente"]]
    return nuevo, cambios, conflictos


# ---------------------------------------------------------------------------
# Acuerdo entre la IA y una persona (calibración)
# ---------------------------------------------------------------------------

def medir_acuerdo(ficha_ia: Any, ficha_humana: Any, p: Mapping[str, Any]) -> dict[str, Any]:
    """Compara las fichas de la IA y de una persona sobre las mismas ofertas.

    «Falso libre» = la IA liberó (false) una puerta que la persona vetó (true): es el error que no se tolera.
    Nivel «muestreo» solo con casos suficientes, acuerdo alto, 0 falsos libres y la IA nunca más optimista
    que la persona en transferibilidad; si no, «humano_en_todo».
    """
    humanas = {o["modelo_id"]: o for o in ficha_humana["ofertas"]}
    coincidencias = falsos_libres = falsos_vetos = sin_opinion = casos = optimista = comparados = 0
    tolerancia = p["modelado_juicio_tolerancia"]
    for oferta in ficha_ia["ofertas"]:
        h = humanas.get(oferta["modelo_id"])
        if h is None:
            continue
        evaluadas = [g for g in PUERTAS if h["puertas"][g] is not None]
        if evaluadas:
            casos += 1
        for g in evaluadas:
            ia = oferta["puertas"][g]
            if ia is None:
                sin_opinion += 1
            elif ia == h["puertas"][g]:
                coincidencias += 1
            elif h["puertas"][g] is True:
                falsos_libres += 1
            else:
                falsos_vetos += 1
        hm = {m["mercado"]: m for m in h["mercados"]}
        for m in oferta["mercados"]:
            if m["mercado"] not in hm:
                continue
            for k in TRANSFERIBILIDAD:
                ia, hu = m["transferibilidad"][k], hm[m["mercado"]]["transferibilidad"][k]
                if ia is None or hu is None:
                    continue
                comparados += 1
                if pm._decimal(ia, k) - pm._decimal(hu, k) > tolerancia:
                    optimista += 1
    decididas = coincidencias + falsos_libres + falsos_vetos
    acuerdo = Decimal(coincidencias) / Decimal(decididas) if decididas else None
    razones = []
    if casos < p["modelado_calibracion_min_casos"]:
        razones.append(f"faltan casos con etiqueta humana ({casos} de {p['modelado_calibracion_min_casos']})")
    if falsos_libres:
        razones.append(f"{falsos_libres} falso(s) libre(s): la IA liberó una puerta que la persona vetó")
    if acuerdo is None or acuerdo < p["modelado_acuerdo_min"]:
        razones.append("acuerdo en puertas menor al mínimo o sin datos")
    if optimista:
        razones.append(f"la IA fue más optimista que la persona en {optimista} componente(s) de transferibilidad")
    return {"casos": casos, "coincidencias": coincidencias, "falsos_libres": falsos_libres,
            "falsos_vetos": falsos_vetos, "sin_opinion": sin_opinion, "ia_mas_optimista": optimista,
            "componentes_comparados": comparados, "acuerdo_puertas": acuerdo,
            "nivel": "humano_en_todo" if razones else "muestreo", "razones": razones}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _json_estricto(obj: Any) -> str:
    def por_defecto(valor: Any) -> str:
        if isinstance(valor, Decimal):
            return format(valor, "f")
        raise TypeError(f"no serializable: {type(valor).__name__}")
    return json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True, default=por_defecto) + "\n"


def main(argv: Sequence[str] | None = None, salida=None) -> int:
    """Punto de entrada. Devuelve el código de salida; los errores esperados no lanzan traza."""
    salida = salida or sys.stdout
    parser = argparse.ArgumentParser(prog="python -m scripts.modelado.juicio", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="orden", required=True)
    co = sub.add_parser("consolidar", help="consolida dos juicios de IA y completa solo los null de la ficha")
    for nombre in ("fichas", "juicio_a", "juicio_b"):
        co.add_argument(nombre, type=Path)
    co.add_argument("--material", type=Path, required=True,
                    help="material.json del que salieron los juicios: se verifica que cada cita exista en él")
    co.add_argument("--parametros", type=Path, default=None)
    co.add_argument("--salida", type=Path, default=None, help="escribe la ficha nueva aquí (no sobrescribe)")
    ac = sub.add_parser("acuerdo", help="mide el acuerdo entre la ficha de la IA y la de una persona")
    ac.add_argument("ficha_ia", type=Path)
    ac.add_argument("ficha_humana", type=Path)
    ac.add_argument("--parametros", type=Path, default=None)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code or 0)
    try:
        p = pm.cargar_parametros(args.parametros)
        if args.orden == "consolidar":
            fichas = pm.leer_json(args.fichas)
            nuevo, cambios, conflictos = aplicar(
                fichas, consolidar(pm.leer_json(args.juicio_a), pm.leer_json(args.juicio_b), p,
                                   material=pm.leer_json(args.material)))
            if args.salida:
                pm._escribir_nuevo(args.salida, _json_estricto(nuevo))
            print(_json_estricto({"cambios": cambios, "conflictos": conflictos}), end="", file=salida)
        else:
            resultado = medir_acuerdo(pm.leer_json(args.ficha_ia), pm.leer_json(args.ficha_humana), p)
            print(_json_estricto(resultado), end="", file=salida)
        return 0
    except pm.ErrorFabrica as exc:
        print(f"ERROR ({type(exc).__name__}): {exc}", file=sys.stderr)
        return exc.codigo_salida


if __name__ == "__main__":
    raise SystemExit(main())
