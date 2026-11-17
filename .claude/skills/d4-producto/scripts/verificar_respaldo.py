#!/usr/bin/env python3
"""L1-12 · L1-13 (mitad sin red) · Respaldo de hechos: ``respaldo/afirmaciones.jsonl`` + ``respaldo/fuentes/*.txt``.

NO usa red: comprueba lo verificable sobre los archivos. Que la URL responda y esté en ``fuentes_autorizadas.yaml`` (L1-S02) y la lectura de
``robots.txt`` son de ``scripts/producto/verificar_respaldo`` [PENDIENTE: references/dependencias.md]. Aquí:

 A. Cada afirmación tiene los campos obligatorios, ``fuente_url`` https, ``nivel_fuente`` T1-T4, fechas coherentes y (si existe) ``vigencia_hasta`` vigente.
 B. El snapshot ``fuentes/<fuente_id>.txt`` existe y su sha256 es el registrado (L1-S03); ``cita_literal`` figura en él, búsqueda exacta normalizada (L1-S04).
 C. Nivel de la fuente según el tipo: cifra, dosis, umbral y ley solo T1; causal ≥ T2; definición ≥ T3; T4 nunca como hecho.
 D. ``fecha_consulta`` no futura y de ≤ ``producto.hechos_fuente_max_dias`` días respecto de ``--hoy``; ``fecha_fuente`` ≤ ``fecha_consulta``.
 E. ``texto_en_producto`` figura en el producto; el número que contiene, leído con los separadores del locale, es ``valor_normalizado``; ``unidad`` figura
    en el texto y equivale a ``unidad_fuente`` (cucharada ≠ cucharadita) → un decimal desplazado, un separador de miles de otro locale o una cuchara
    cambiada son BLOQUEANTES (L1-13).
 F. Toda «cifra de hecho» del producto (unidad de hecho, decimal o ≥ 100 y no año) figura en alguna afirmación o en ``respaldo/numeros_no_factuales.txt`` (L1-S06).
 G. Por tema: ≥ ``producto.min_fuentes_por_tema`` fuentes distintas y ≥ 1 T1 (L1-12). Fuente del país del lector (``pais_fuente`` ∈ ``--paises`` o ``internacional: true``).

Uso: python3 verificar_respaldo.py --respaldo-dir 04-producto/respaldo --producto 04-producto/entregables/fuente [más rutas] --locale it-IT \\
        --paises IT --hoy 2026-11-06 [--parametros empresa/parametros.yaml] [--max-dias N] [--min-fuentes N] [--salida X]
Si no hay afirmaciones y el producto no tiene cifras de hecho: pasa con la nota «sin hechos externos» (productos P0/C0).
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun as c  # noqa: E402

OBLIGATORIOS = ["afirmacion_id", "tema", "texto_en_producto", "tipo", "fuente_id", "cita_literal", "valor_normalizado", "unidad",
                "fuente_url", "nivel_fuente", "fecha_fuente", "fecha_consulta", "sha256"]
TIPOS = {"cifra", "dosis", "umbral", "ley", "causal", "definicion"}
SOLO_T1 = {"cifra", "dosis", "umbral", "ley"}
RX_FECHA = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")
GRUPOS_UNIDAD = [  # equivalencias entre idiomas que NO se pueden confundir entre sí
    {"cucchiaio", "cucchiai", "cucharada", "cucharadas", "tablespoon", "tablespoons", "tbsp", "łyżka", "łyżki", "łyżek", "lingura", "linguri", "cuillère à soupe", "cuillères à soupe", "el", "esslöffel"},
    {"cucchiaino", "cucchiaini", "cucharadita", "cucharaditas", "teaspoon", "teaspoons", "tsp", "łyżeczka", "łyżeczki", "łyżeczek", "linguriță", "lingurițe", "cuillère à café", "cuillères à café", "tl", "teelöffel"},
]


def fecha(s: str) -> date | None:
    if not isinstance(s, str) or not RX_FECHA.match(s):
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def grupo_unidad(u: str) -> int | None:
    u = u.casefold().strip()
    for i, g in enumerate(GRUPOS_UNIDAD):
        if u in g:
            return i
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--respaldo-dir", required=True)
    ap.add_argument("--producto", nargs="+", required=True)
    ap.add_argument("--locale", required=True)
    ap.add_argument("--paises", default="", help="países de segmentación (ISO), separados por coma")
    ap.add_argument("--hoy", help="AAAA-MM-DD (por determinismo; por defecto, hoy)")
    ap.add_argument("--parametros")
    ap.add_argument("--max-dias", type=int)
    ap.add_argument("--min-fuentes", type=int)
    ap.add_argument("--salida")
    a = ap.parse_args(argv)
    try:
        par = c.parametros_por_defecto(a.parametros)
        max_dias = int(c.parametro(par, "producto", "hechos_fuente_max_dias", a.max_dias))
        min_fuentes = int(c.parametro(par, "producto", "min_fuentes_por_tema", a.min_fuentes))
    except c.ParametroFaltante as e:
        return c.error_uso(str(e), 5)
    hoy = fecha(a.hoy) if a.hoy else date.today()
    if hoy is None:
        return c.error_uso("--hoy debe ser AAAA-MM-DD", 2)
    rd = Path(a.respaldo_dir)
    try:
        texto_producto = "\n".join(c.leer_texto(p) for p in c.expandir_rutas(a.producto, {".md", ".txt", ".html", ".htm"}))
        filas = c.cargar_jsonl(rd / "afirmaciones.jsonl") if (rd / "afirmaciones.jsonl").is_file() else []
    except (OSError, ValueError) as e:
        return c.error_uso(f"entrada inválida: {e}", 3)
    paises = {p.strip().upper() for p in a.paises.split(",") if p.strip()}
    prod_norm = c.normalizar_busqueda(texto_producto)
    h: list[dict] = []
    por_tema: dict[str, dict] = {}
    valores_respaldados: set[Decimal] = set()
    textos_afirmados: list[str] = []

    for k, f in enumerate(filas, 1):
        aid = f.get("afirmacion_id", f"linea-{k}")
        ev = f"afirmaciones.jsonl:{k} ({aid})"
        faltan = [x for x in OBLIGATORIOS if x not in f or f[x] in (None, "") and x not in ("valor_normalizado", "unidad")]
        if faltan:
            h.append(c.hallazgo("L1-12", "BLOQUEANTE", f"campos obligatorios ausentes: {faltan}", ev, "respaldo-incompleto"))
            continue
        # A
        if not str(f["fuente_url"]).startswith("https://"):
            h.append(c.hallazgo("L1-12", "BLOQUEANTE", "fuente_url debe ser https://", ev, "url-invalida"))
        if f["nivel_fuente"] not in {"T1", "T2", "T3", "T4"} or f["tipo"] not in TIPOS:
            h.append(c.hallazgo("L1-12", "BLOQUEANTE", f"nivel_fuente «{f['nivel_fuente']}» o tipo «{f['tipo']}» fuera de catálogo", ev))
            continue
        # C
        if f["nivel_fuente"] == "T4":
            h.append(c.hallazgo("L1-12", "BLOQUEANTE", "una fuente T4 nunca sostiene un hecho", ev, "fuente-t4"))
        elif f["tipo"] in SOLO_T1 and f["nivel_fuente"] != "T1":
            h.append(c.hallazgo("L1-12", "BLOQUEANTE", f"{f['tipo']} solo con T1 (aquí {f['nivel_fuente']})", ev, "nivel-insuficiente"))
        elif f["tipo"] == "causal" and f["nivel_fuente"] not in ("T1", "T2"):
            h.append(c.hallazgo("L1-12", "BLOQUEANTE", "una causalidad exige T1/T2 y atribución", ev, "causalidad-sin-fuente"))
        # D
        fc, ff = fecha(f["fecha_consulta"]), fecha(f["fecha_fuente"])
        if fc is None or ff is None:
            h.append(c.hallazgo("L1-12", "BLOQUEANTE", "fecha_consulta o fecha_fuente no son AAAA-MM-DD válidas", ev))
        else:
            if fc > hoy or ff > fc:
                h.append(c.hallazgo("L1-12", "BLOQUEANTE", "fechas incoherentes (consulta futura o fuente posterior a la consulta): «verificado el» falso", ev, "fecha-falsa"))
            elif (hoy - fc).days > max_dias:
                h.append(c.hallazgo("L1-08", "MAYOR", f"fecha_consulta de hace {(hoy - fc).days} días (> {max_dias}): repetir la consulta de la fuente", ev, "fuente-vieja"))
        if f.get("vigencia_hasta") and (fecha(f["vigencia_hasta"]) is None or fecha(f["vigencia_hasta"]) < hoy):
            h.append(c.hallazgo("L1-12", "MAYOR", f"vigencia_hasta {f['vigencia_hasta']} vencida o inválida", ev, "vigencia"))
        # G
        if not f.get("internacional") and paises and f.get("pais_fuente", "").upper() not in paises:
            sev = "BLOQUEANTE" if f["tipo"] in ("umbral", "ley", "dosis") else "MAYOR"
            h.append(c.hallazgo("L1-12", sev, f"fuente del país «{f.get('pais_fuente', '?')}» para un lector de {sorted(paises)}: usar la fuente del país del lector o declarar internacional:true", ev, "fuente-de-otro-pais"))
        t = por_tema.setdefault(f["tema"], {"fuentes": set(), "t1": False})
        t["fuentes"].add(f["fuente_id"])
        t["t1"] = t["t1"] or f["nivel_fuente"] == "T1"
        # B
        snap = rd / "fuentes" / f"{f['fuente_id']}.txt"
        if not snap.is_file():
            h.append(c.hallazgo("L1-12", "BLOQUEANTE", f"falta el snapshot fuentes/{f['fuente_id']}.txt", ev, "snapshot-ausente"))
        else:
            if c.hash_archivo(snap) != f["sha256"]:
                h.append(c.hallazgo("L1-12", "BLOQUEANTE", f"sha256 del snapshot ≠ registrado (esperado {f['sha256'][:19]}…, real {c.hash_archivo(snap)[:19]}…)", ev, "snapshot-alterado"))
            if c.normalizar_busqueda(f["cita_literal"]) not in c.normalizar_busqueda(snap.read_text(encoding="utf-8")):
                h.append(c.hallazgo("L1-12", "BLOQUEANTE", "la cita_literal no figura en el snapshot (cita inventada o parafraseada)", ev, "cita-no-esta-en-fuente"))
        # E
        tp = f["texto_en_producto"]
        textos_afirmados.append(c.normalizar_busqueda(tp))
        if c.normalizar_busqueda(tp) not in prod_norm:
            h.append(c.hallazgo("L1-12", "MAYOR", "texto_en_producto no figura en el producto (afirmación huérfana o texto cambiado sin actualizar el respaldo)", ev, "afirmacion-huerfana"))
        vn = f.get("valor_normalizado")
        if vn not in (None, ""):
            try:
                vdec = Decimal(str(vn))
            except InvalidOperation:
                h.append(c.hallazgo("L1-13", "BLOQUEANTE", f"valor_normalizado «{vn}» no es numérico", ev))
                continue
            valores_respaldados.add(vdec)
            nums = c.numeros_en_texto(tp, a.locale)
            if not any(n["valor"] == vdec for n in nums):
                leidos = [str(n["valor"]) for n in nums]
                h.append(c.hallazgo("L1-13", "BLOQUEANTE", f"el producto dice {tp!r}: leído con los separadores de {a.locale} da {leidos or 'ningún número'}, y la fuente dice {vdec} (decimal desplazado o separador de otro locale)", ev, "cifra-distinta-de-fuente"))
            for n in nums:
                if n["valor"] == vdec and n["banderas"]:
                    h.append(c.hallazgo("L1-13", "MAYOR", f"«{n['token']}» usa un formato que no es el de {a.locale}: {n['banderas']}", ev, "separador-ajeno"))
            u, uf = str(f.get("unidad") or ""), str(f.get("unidad_fuente") or "")
            if u and u.casefold() not in tp.casefold():
                h.append(c.hallazgo("L1-13", "BLOQUEANTE", f"la unidad «{u}» no figura en el texto del producto", ev, "unidad-distinta"))
            if u and uf and u.casefold() != uf.casefold():
                gu, gf = grupo_unidad(u), grupo_unidad(uf)
                if gu is None or gf is None or gu != gf:
                    h.append(c.hallazgo("L1-13", "BLOQUEANTE", f"unidad del producto «{u}» ≠ unidad de la fuente «{uf}» sin equivalencia declarada (cucharada y cucharadita no son intercambiables)", ev, "unidad-distinta"))
            if uf and uf.casefold() not in f["cita_literal"].casefold():
                h.append(c.hallazgo("L1-13", "MAYOR", f"unidad_fuente «{uf}» no figura en la cita literal", ev))

    # G por tema
    for tema, t in sorted(por_tema.items()):
        if len(t["fuentes"]) < min_fuentes or not t["t1"]:
            h.append(c.hallazgo("L1-12", "MAYOR", f"tema «{tema}»: {len(t['fuentes'])} fuente(s) distintas (mínimo {min_fuentes}) y {'con' if t['t1'] else 'SIN'} T1", "afirmaciones.jsonl", "fuentes-insuficientes"))
    # F cifras del producto
    permitidas: set[Decimal] = set()
    nf = rd / "numeros_no_factuales.txt"
    if nf.is_file():
        for linea in nf.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*(\d+(?:[.,]\d+)*)\s*(?:#.*)?$", linea)
            if m:
                v, _ = c.interpretar_numero(m.group(1), a.locale)
                if v is not None:
                    permitidas.add(v)
    sin_respaldo, total_cifras = [], 0
    for n in c.numeros_en_texto(texto_producto, a.locale):
        if not n["cifra_de_hecho"]:
            continue
        total_cifras += 1
        if n["valor"] in valores_respaldados or n["valor"] in permitidas:
            continue
        sin_respaldo.append(n)
    for n in sin_respaldo:
        h.append(c.hallazgo("L1-12", "BLOQUEANTE", f"la cifra «{n['token']}»{' ' + n['unidad'] if n['unidad'] else ''} (línea {n['linea']}) no figura en afirmaciones.jsonl ni en numeros_no_factuales.txt", f"producto:línea {n['linea']}", "cifra-sin-respaldo"))
    if len(permitidas) > max(3, total_cifras // 3):
        h.append(c.hallazgo("L1-12", "MENOR", "numeros_no_factuales.txt cubre una parte grande de las cifras: el QA debe revisar que no sea una puerta trasera", "respaldo/numeros_no_factuales.txt"))
    nota = "sin hechos externos: producto sin cifras de hecho ni afirmaciones (válido solo para P0/C0)" if not filas and not total_cifras else None
    return c.emitir("verificar_respaldo", ["L1-12", "L1-13", "L1-08"], h, {
        "afirmaciones": len(filas), "temas": {t: {"fuentes": len(v["fuentes"]), "t1": v["t1"]} for t, v in por_tema.items()},
        "cifras_de_hecho_en_producto": total_cifras, "cifras_sin_respaldo": len(sin_respaldo), "hoy": hoy.isoformat(), "nota": nota,
    }, a.salida)


if __name__ == "__main__":
    sys.exit(main())
