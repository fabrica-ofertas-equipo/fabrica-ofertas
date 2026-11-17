#!/usr/bin/env python3
"""validar_propuesta.py: autocomprobación determinista de la ``propuesta-de-decision.json`` que redacta el Maker de D8.

v0.1 sin pulir (skill d8-optimizacion 0.1.0). Comprueba tres cosas, sin juicio y sin red:
  1. FORMA: campos, vocabulario de acciones, mapeo al contrato ``decision`` (MATAR|SEGUIR|ESCALAR|INCONCLUSO|BLOQUEADO),
     patrones de ``codigo`` y ``regla``, ``explicacion`` <= 600, sin ``float``, nada marcado como ejecutado.
  2. RESPALDO DEL CÓDIGO: una propuesta de regla J3 o de fatiga solo es válida si coincide con lo que calculó
     ``proponer.py`` (acción y código); el Maker no puede apagar ni relevar «por criterio».
  3. CIFRAS COPIADAS: cada ``evidencia[].valor`` debe ser idéntico al dato citado en ``fuente`` (``archivo:ruta.punteada``)
     dentro de la entrada, las reglas o los umbrales que se pasen con --entrada, --regla y --umbrales.

Uso: ``validar_propuesta.py --propuesta p.json [--entrada entrada.json] [--regla regla_lanzamiento.json]... [--umbrales u.json]``.
Salida: 0 sin errores · 3 con errores (se listan en stdout como JSON) · 2 uso.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ACCION_CONTRATO = {
    "APAGAR": "MATAR", "MANTENER": "SEGUIR", "GRADUAR": "ESCALAR", "RELEVAR": "SEGUIR", "AVISAR_FATIGA": "SEGUIR",
    "PAUSAR_Y_ESCALAR": "INCONCLUSO", "NO_DECIDIR": "BLOQUEADO",
}
OBJETOS = ("oferta", "campana", "conjunto", "anuncio")
RX_OFERTA = re.compile(r"^OF-[0-9]{6}-[0-9]{2}$")
RX_FECHA = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
RX_CODIGO = re.compile(r"^[A-Z][A-Z0-9_]*$")
RX_REGLA = re.compile(r"^[A-Za-z0-9_.-]{1,40}$")
RX_OBJETO_ID = re.compile(r"^[A-Za-z0-9_.:-]{1,64}$")
RX_FUENTE = re.compile(r"^(?P<archivo>[A-Za-z0-9_.-]+):(?P<ruta>[A-Za-z0-9_.\[\]-]+)$")
RX_META_ID = re.compile(r"^[0-9]{10,25}$")
ARCHIVOS_FUENTE = ("entrada.json", "regla_lanzamiento.json", "regla_fatiga.json", "umbrales.json")


def hay_floats(valor, ruta: str = "$") -> list[str]:
    if isinstance(valor, float):
        return [ruta]
    if isinstance(valor, dict):
        return [r for k, v in valor.items() for r in hay_floats(v, f"{ruta}.{k}")]
    if isinstance(valor, list):
        return [r for i, v in enumerate(valor) for r in hay_floats(v, f"{ruta}[{i}]")]
    return []


def resolver(doc, ruta: str):
    """Valor de ``doc`` en la ruta punteada ``a.b[0].c``; una clave puede llevar puntos (``lanzamiento.baja_dias``).

    Lanza ``KeyError``/``IndexError``/``TypeError`` si no existe.
    """
    if ruta == "":
        return doc
    if isinstance(doc, list):
        m = re.match(r"^\[(\d+)\](?:\.)?(.*)$", ruta)
        if not m:
            raise KeyError(ruta)
        return resolver(doc[int(m.group(1))], m.group(2))
    if isinstance(doc, dict):
        for clave in sorted(doc, key=len, reverse=True):
            if ruta == clave:
                return doc[clave]
            for sep in (".", "["):
                if ruta.startswith(clave + sep):
                    resto = ruta[len(clave) + (1 if sep == "." else 0):]
                    return resolver(doc[clave], resto)
        raise KeyError(ruta)
    raise TypeError(ruta)


def como_texto(valor) -> str:
    return valor if isinstance(valor, str) else json.dumps(valor, ensure_ascii=False)


def validar(propuesta: dict, *, fuentes: dict[str, dict] | None = None, reglas: list[dict] | None = None) -> list[str]:
    """Lista de errores (vacía = válida). ``fuentes``: archivo -> documento; ``reglas``: salidas de ``proponer.py``."""
    errores: list[str] = []
    fuentes, reglas = fuentes or {}, reglas or []
    if not isinstance(propuesta, dict):
        return ["la propuesta debe ser un objeto JSON"]
    if propuesta.get("tipo") != "propuesta_d8":
        errores.append("tipo debe ser 'propuesta_d8'")
    if not RX_OFERTA.match(str(propuesta.get("oferta_id", ""))):
        errores.append("oferta_id inválido")
    if not RX_FECHA.match(str(propuesta.get("fecha_cuenta", ""))):
        errores.append("fecha_cuenta inválida")
    if propuesta.get("modo") not in ("LANZAMIENTO", "CONTINUO", "FATIGA", "CIERRE"):
        errores.append("modo debe ser LANZAMIENTO, CONTINUO, FATIGA o CIERRE")
    for ruta in hay_floats(propuesta):
        errores.append(f"float en {ruta}: usa enteros en unidad menor o cadenas decimales")
    lista = propuesta.get("propuestas")
    if not isinstance(lista, list):
        return errores + ["propuestas debe ser una lista"]
    for i, p in enumerate(lista):
        t = f"propuestas[{i}]"
        if not isinstance(p, dict):
            errores.append(f"{t}: debe ser un objeto")
            continue
        accion = p.get("accion_negocio")
        if accion not in ACCION_CONTRATO:
            errores.append(f"{t}: accion_negocio desconocida {accion!r}")
        elif p.get("accion_contrato") != ACCION_CONTRATO[accion]:
            errores.append(f"{t}: accion_contrato debe ser {ACCION_CONTRATO[accion]} para {accion}")
        if p.get("objeto_tipo") not in OBJETOS:
            errores.append(f"{t}: objeto_tipo fuera de {OBJETOS}")
        oid = str(p.get("objeto_id", ""))
        if not RX_OBJETO_ID.match(oid):
            errores.append(f"{t}: objeto_id inválido")
        elif p.get("objeto_tipo") == "oferta" and oid != propuesta.get("oferta_id"):
            errores.append(f"{t}: para objeto_tipo oferta, objeto_id debe ser el oferta_id")
        elif p.get("objeto_tipo") in ("campana", "conjunto", "anuncio") and not RX_META_ID.match(oid):
            errores.append(f"{t}: el objeto_id de un objeto de Meta debe ser su id numérico")
        if not RX_CODIGO.match(str(p.get("codigo", ""))):
            errores.append(f"{t}: codigo debe cumplir ^[A-Z][A-Z0-9_]*$")
        if not RX_REGLA.match(str(p.get("regla", ""))):
            errores.append(f"{t}: regla inválida")
        expl = p.get("explicacion")
        if not isinstance(expl, str) or not expl.strip() or len(expl) > 600:
            errores.append(f"{t}: explicacion obligatoria y de hasta 600 caracteres")
        if p.get("ejecuta") not in ("codigo", "humano", "ninguno"):
            errores.append(f"{t}: ejecuta debe ser codigo, humano o ninguno (el Maker nunca ejecuta)")
        if not isinstance(p.get("requiere_humano"), bool):
            errores.append(f"{t}: requiere_humano debe ser booleano")
        if p.get("gate_efectivo") not in ("A", "S", "H", "NA"):
            errores.append(f"{t}: gate_efectivo debe ser A, S, H o NA")
        if p.get("ejecutada") is True or p.get("ejecutada_por_maker") is True:
            errores.append(f"{t}: una propuesta no puede marcarse como ejecutada por el Maker")
        evidencia = p.get("evidencia")
        if not isinstance(evidencia, list) or not evidencia:
            errores.append(f"{t}: evidencia obligatoria (lista de {{fuente, valor}})")
            evidencia = []
        for j, ev in enumerate(evidencia):
            te = f"{t}.evidencia[{j}]"
            m = RX_FUENTE.match(str(ev.get("fuente", ""))) if isinstance(ev, dict) else None
            if not m or not isinstance(ev.get("valor"), str):
                errores.append(f"{te}: debe ser {{fuente: 'archivo:ruta', valor: <cadena>}}")
                continue
            if m["archivo"] not in ARCHIVOS_FUENTE:
                errores.append(f"{te}: archivo de fuente desconocido {m['archivo']!r} (válidos: {', '.join(ARCHIVOS_FUENTE)})")
            elif m["archivo"] in fuentes:
                try:
                    real = como_texto(resolver(fuentes[m["archivo"]], m["ruta"]))
                except (KeyError, IndexError, TypeError):
                    errores.append(f"{te}: la ruta {m['ruta']} no existe en {m['archivo']}")
                    continue
                if real != ev["valor"]:
                    errores.append(f"{te}: la cifra citada ({ev['valor']}) no es la del archivo ({real}): se copia, no se calcula")
        # --- respaldo del código ---
        regla = str(p.get("regla", ""))
        if reglas and (regla.startswith("J3") or regla == "FT"):
            if not _respaldada(p, reglas):
                errores.append(f"{t}: {accion}/{p.get('codigo')} no coincide con lo que calculó proponer.py (regla {regla}): el Maker no decide por criterio")
    return errores


def _respaldada(p: dict, reglas: list[dict]) -> bool:
    """¿Coincide la propuesta con alguna salida de ``proponer.py``? (J3: acción y código; FT: objeto, acción y código)."""
    regla = str(p.get("regla", ""))
    for r in reglas:
        if regla.startswith("J3") and r.get("regla") == "J3-BAJA-LANZAMIENTO":
            if (r.get("accion_negocio"), r.get("codigo")) == (p.get("accion_negocio"), p.get("codigo")):
                return True
        if regla == "FT" and r.get("regla") == "FT-CANSANCIO-3V7":
            for q in r.get("propuestas", []):
                if (q.get("objeto_id"), q.get("accion_negocio"), q.get("codigo")) == (p.get("objeto_id"), p.get("accion_negocio"), p.get("codigo")):
                    return True
    return False


def _cargar(ruta: str) -> dict:
    return json.loads(Path(ruta).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Autocomprobación de la propuesta de decisión de D8.")
    ap.add_argument("--propuesta", required=True)
    ap.add_argument("--entrada", default=None, help="entrada.json de preparar_expediente.py")
    ap.add_argument("--regla", action="append", default=[], help="salida de proponer.py (lanzamiento o fatiga); repetible")
    ap.add_argument("--umbrales", default=None)
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    try:
        propuesta = _cargar(args.propuesta)
        fuentes: dict[str, dict] = {}
        if args.entrada:
            fuentes["entrada.json"] = _cargar(args.entrada)
        if args.umbrales:
            doc = _cargar(args.umbrales)
            fuentes["umbrales.json"] = doc.get("umbrales", doc) if isinstance(doc, dict) else doc
        reglas = [_cargar(r) for r in args.regla]
        for r in reglas:
            if r.get("regla") == "J3-BAJA-LANZAMIENTO":
                fuentes["regla_lanzamiento.json"] = r
            elif r.get("regla") == "FT-CANSANCIO-3V7":
                fuentes["regla_fatiga.json"] = r
    except (OSError, ValueError) as exc:
        print(f"ERROR: no se pudo leer un archivo: {exc}", file=sys.stderr)
        return 3
    errores = validar(propuesta, fuentes=fuentes, reglas=reglas)
    print(json.dumps({"valida": not errores, "errores": errores}, ensure_ascii=False, indent=2))
    return 0 if not errores else 3


if __name__ == "__main__":
    raise SystemExit(main())
