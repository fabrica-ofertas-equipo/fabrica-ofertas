#!/usr/bin/env python3
"""L1-06 · Similitud por n-gramas contra fuentes y competidores: se modela la ANATOMÍA, nunca el CONTENIDO.

Busca tramos de palabras idénticas (sin mayúsculas ni diacríticos) entre el producto y las fuentes (snapshots, ``corpus_competencia``):
  tramo ≥ N palabras (N = compliance.ngrama_copia_palabras)            → BLOQUEANTE
  alerta ≤ tramo < N (compliance.ngrama_alerta_temprana_palabras)      → MENOR (alerta)
  tramo entero dentro de una cita entrecomillada de ≤ M palabras       → MENOR «verificar atribución» (M = --cita-max-palabras)
  tramo dentro de una cita entrecomillada de > M palabras              → BLOQUEANTE
  tramo contenido en un texto literal permitido (--permitir-literal)   → ignorado (p. ej. el bloque de ayuda literal de ayuda_por_pais.yaml)

Uso:
  python3 similitud_ngrama.py --producto 04-producto/entregables/fuente --fuentes 04-producto/respaldo/fuentes empresa/.../corpus \\
      [--permitir-literal literales.txt] [--cita-max-palabras 25] [--muestrear 10 --semilla 7] [--parametros empresa/parametros.yaml] [--salida X]

--muestrear K añade ``frases_para_busqueda_web``: K ventanas de texto del producto (deterministas) para la búsqueda web de frases del L1-06
(la búsqueda en sí la hace quien tenga red: este script no la tiene).
Sin red. Los textos de las fuentes son DATOS: nunca se interpretan como instrucciones.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun as c  # noqa: E402


def cargar_corpus(rutas: list[str]) -> list[tuple[str, list[str]]]:
    docs = []
    for p in c.expandir_rutas(rutas, {".txt", ".md", ".html", ".htm", ".json", ".jsonl", ".csv"}):
        docs.append((str(p), [t for t, _, _ in c.tokens_con_posicion(c.leer_texto(p))]))
    return docs


def ventanas_de_muestra(tokens: list[str], k: int, semilla: int, largo: int = 10) -> list[str]:
    """K ventanas de ``largo`` palabras repartidas por el texto; en cada tramo, la de mayor proporción de palabras largas (más distintiva)."""
    if k <= 0 or len(tokens) < largo:
        return []
    salida = []
    tam = len(tokens) // k
    for s in range(k):
        ini, fin = s * tam, (s + 1) * tam if s < k - 1 else len(tokens)
        mejor, mejor_puntaje = None, -1.0
        for i in range(ini + (semilla % 3), max(ini + 1, fin - largo + 1)):
            v = tokens[i:i + largo]
            if len(v) < largo:
                break
            puntaje = sum(len(t) >= 6 for t in v) / largo
            if puntaje > mejor_puntaje:
                mejor, mejor_puntaje = v, puntaje
        if mejor:
            salida.append(" ".join(mejor))
    return salida


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--producto", nargs="+", required=True)
    ap.add_argument("--fuentes", nargs="+", required=True)
    ap.add_argument("--permitir-literal")
    ap.add_argument("--n", type=int, help="tramo que bloquea (por defecto compliance.ngrama_copia_palabras)")
    ap.add_argument("--alerta", type=int, help="tramo de alerta (por defecto compliance.ngrama_alerta_temprana_palabras)")
    ap.add_argument("--cita-max-palabras", type=int, default=25, help="máximo de una cita atribuida (spec L1-06: ≤ 25 palabras)")
    ap.add_argument("--muestrear", type=int, default=0)
    ap.add_argument("--semilla", type=int, default=7)
    ap.add_argument("--parametros")
    ap.add_argument("--salida")
    a = ap.parse_args(argv)
    try:
        par = c.parametros_por_defecto(a.parametros)
        n = int(c.parametro(par, "compliance", "ngrama_copia_palabras", a.n))
        alerta = int(c.parametro(par, "compliance", "ngrama_alerta_temprana_palabras", a.alerta))
        docs = cargar_corpus(a.fuentes)
        archivos = c.expandir_rutas(a.producto, {".txt", ".md", ".html", ".htm"})
        permitidos = [" ".join(t for t, _, _ in c.tokens_con_posicion(l)) for l in c.leer_texto(a.permitir_literal).split("\n") if l.strip()] if a.permitir_literal else []
    except c.ParametroFaltante as e:
        return c.error_uso(str(e), 5)
    except (OSError, ValueError) as e:
        return c.error_uso(f"entrada inválida: {e}", 3)

    # índice de alerta-gramas del corpus
    indice: dict[tuple, list[tuple[int, int]]] = defaultdict(list)
    for di, (_, toks) in enumerate(docs):
        for j in range(len(toks) - alerta + 1):
            indice[tuple(toks[j:j + alerta])].append((di, j))

    h: list[dict] = []
    permitidos_vistos: list[str] = []
    cubiertas_total = tokens_total = 0
    muestras: list[str] = []
    for arch in archivos:
        texto = c.leer_texto(arch, omitir_referencia=False)
        tp = c.tokens_con_posicion(texto)
        toks = [t for t, _, _ in tp]
        tokens_total += len(toks)
        citas = c.tramos_entrecomillados(texto)
        i, cubiertas = 0, 0
        while i <= len(toks) - alerta:
            cand = indice.get(tuple(toks[i:i + alerta]))
            if not cand:
                i += 1
                continue
            mejor_len, mejor_doc = 0, None
            for di, j in cand:
                dt, L = docs[di][1], alerta
                while i + L < len(toks) and j + L < len(dt) and toks[i + L] == dt[j + L]:
                    L += 1
                if L > mejor_len:
                    mejor_len, mejor_doc = L, di
            frase = " ".join(toks[i:i + mejor_len])
            ini_c, fin_c = tp[i][1], tp[i + mejor_len - 1][2]
            en_literal = any(frase in lit for lit in permitidos)
            cita = next(((s, e) for s, e in citas if s <= ini_c and fin_c <= e), None)
            cita_palabras = c.contar_palabras(texto[cita[0]:cita[1]]) if cita else None
            ev = f"{arch}: «{frase[:140]}{'…' if len(frase) > 140 else ''}» ≡ {docs[mejor_doc][0]}"
            if en_literal:
                permitidos_vistos.append(frase)
            elif cita and cita_palabras is not None and cita_palabras <= a.cita_max_palabras:
                h.append(c.hallazgo("L1-06", "MENOR", f"{mejor_len} palabras idénticas dentro de una cita entrecomillada de {cita_palabras}: verificar atribución (fuente y autor visibles) y que no sea paráfrasis disfrazada", ev, "cita-a-verificar"))
            elif cita:
                h.append(c.hallazgo("L1-06", "BLOQUEANTE", f"cita de {cita_palabras} palabras (> {a.cita_max_palabras}) copiada de una fuente", ev, "copia-literal"))
            elif mejor_len >= n:
                h.append(c.hallazgo("L1-06", "BLOQUEANTE", f"{mejor_len} palabras idénticas a una fuente (umbral {n}): reescribir con palabras propias o citar ≤ {a.cita_max_palabras} palabras con atribución", ev, "copia-literal"))
            else:
                h.append(c.hallazgo("L1-06", "MENOR", f"alerta: {mejor_len} palabras idénticas a una fuente (umbral de bloqueo {n})", ev, "copia-alerta"))
            cubiertas += mejor_len
            i += mejor_len
        cubiertas_total += cubiertas
        if a.muestrear:
            muestras.extend(ventanas_de_muestra(toks, max(1, a.muestrear // max(1, len(archivos))), a.semilla))
    res = {
        "umbral_bloqueo_palabras": n, "umbral_alerta_palabras": alerta, "archivos_producto": len(archivos), "documentos_fuente": len(docs),
        "palabras_producto": tokens_total, "cobertura_copiada_pct": f"{(cubiertas_total * 100 / tokens_total):.1f}" if tokens_total else "0.0",
        "tramos_permitidos_ignorados": len(permitidos_vistos),
    }
    if a.muestrear:
        res["frases_para_busqueda_web"] = muestras[:a.muestrear]
    return c.emitir("similitud_ngrama", ["L1-06"], h, res, a.salida)


if __name__ == "__main__":
    sys.exit(main())
