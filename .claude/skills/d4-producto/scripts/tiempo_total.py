#!/usr/bin/env python3
"""L1-03 · Tiempo = lectura + pasos humanos, contra ``promesa.tiempo_prometido_min`` (única fuente: D3; reconciliación R10).

    total_min = palabras / (lectura_wpm * factor_locale) + Σ t_humano_min(pasos)   ≤   tiempo_prometido_min   (base «estimado»)
                                                                                   ≤   cold_run_tolerancia × prometido (base «cold_run_humano»)

Uso:
  python3 tiempo_total.py --producto 04-producto/producto.json --oferta 03-oferta/oferta.json \\
      --lectura 04-producto/entregables/fuente/guia.html [más archivos] [--ignorar-secciones "Fuentes,Colofón"] \\
      [--autoprueba 04-producto/autoprueba.json] [--medido-primer-paso-min N --estimado-primer-paso-min M] [--parametros empresa/parametros.yaml]

Umbrales (parametros.yaml#producto): lectura_wpm, cold_run_tolerancia, lectura_max_pct_prometido, t_paso_humano_min. Banderas
--wpm / --tolerancia / --lectura-max-pct / --desvio-max-pct los sobrescriben. ``--factor-locale`` (por defecto 1) es el factor de lectura por
idioma [PENDIENTE: parámetro por locale; ver references/dependencias.md]. Sin dato: salida 5 (fail-closed).
El reloj de un agente NO es el de un humano: este script no mide nada, calcula; el tiempo medido entra solo por --medido-primer-paso-min.
"""
from __future__ import annotations

import argparse
import math
import re
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun as c  # noqa: E402


def palabras_de(ruta: Path, ignorar: list[str]) -> int:
    texto = c.leer_texto(ruta, omitir_referencia=True)
    if ignorar and ruta.suffix.lower() in {".md", ".txt"}:
        texto = quitar_secciones_md(texto, ignorar)
    return c.contar_palabras(texto)


def quitar_secciones_md(texto: str, ignorar: list[str]) -> str:
    """Elimina del texto Markdown las secciones cuyo encabezado contiene alguno de ``ignorar`` (hasta el siguiente encabezado de igual o mayor rango)."""
    salida, omitiendo, nivel = [], False, 0
    for linea in texto.splitlines():
        m = re.match(r"^(#{1,6})\s+(.*)$", linea)
        if m:
            n = len(m.group(1))
            if omitiendo and n <= nivel:
                omitiendo = False
            if not omitiendo and any(x.casefold() in m.group(2).casefold() for x in ignorar):
                omitiendo, nivel = True, n
        if not omitiendo:
            salida.append(linea)
    return "\n".join(salida)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--producto", required=True)
    ap.add_argument("--oferta", required=True)
    ap.add_argument("--lectura", nargs="*", default=[], help="archivos que el comprador debe LEER en su ruta de uso (no los anexos de consulta)")
    ap.add_argument("--palabras", type=int, help="en lugar de --lectura: palabras de la ruta de lectura")
    ap.add_argument("--ignorar-secciones", default="", help="encabezados Markdown a excluir, separados por coma")
    ap.add_argument("--autoprueba")
    ap.add_argument("--medido-primer-paso-min", type=Decimal)
    ap.add_argument("--estimado-primer-paso-min", type=Decimal)
    ap.add_argument("--factor-locale", type=Decimal, default=Decimal(1))
    ap.add_argument("--parametros")
    ap.add_argument("--wpm", type=Decimal)
    ap.add_argument("--tolerancia", type=Decimal)
    ap.add_argument("--lectura-max-pct", type=Decimal)
    ap.add_argument("--desvio-max-pct", type=Decimal, help="desvío máximo medido vs estimado del primer paso [PENDIENTE: parámetro producto.cold_run_desvio_max_pct; la spec 10.2 sugiere 25 por ciento]")
    ap.add_argument("--salida")
    a = ap.parse_args(argv)
    try:
        par = c.parametros_por_defecto(a.parametros)
        wpm = Decimal(str(c.parametro(par, "producto", "lectura_wpm", a.wpm)))
        tol = Decimal(str(c.parametro(par, "producto", "cold_run_tolerancia", a.tolerancia)))
        lmax = Decimal(str(c.parametro(par, "producto", "lectura_max_pct_prometido", a.lectura_max_pct)))
        t_tipo = c.parametro(par, "producto", "t_paso_humano_min") if a.autoprueba else {}
    except c.ParametroFaltante as e:
        return c.error_uso(str(e), 5)
    try:
        prod, oferta = c.cargar_json(a.producto), c.cargar_json(a.oferta)
        ignorar = [x.strip() for x in a.ignorar_secciones.split(",") if x.strip()]
        palabras = a.palabras if a.palabras is not None else sum(palabras_de(p, ignorar) for p in c.expandir_rutas(a.lectura)) if a.lectura else None
    except (OSError, ValueError) as e:
        return c.error_uso(f"entrada inválida: {e}", 3)
    if palabras is None:
        return c.error_uso("indicar --lectura o --palabras", 2)

    h: list[dict] = []
    t = prod["tiempos"]
    prom_oferta = oferta["promesa"]["tiempo_prometido_min"]
    prom = t["prometido_min"]
    if prom != prom_oferta:
        h.append(c.hallazgo("L1-03", "BLOQUEANTE", f"tiempos.prometido_min {prom} != oferta.promesa.tiempo_prometido_min {prom_oferta} (D4 nunca cambia la promesa: devolver a D3)", "producto.json#tiempos"))
    lectura_calc = int(math.ceil(Decimal(palabras) / (wpm * a.factor_locale)))
    ejec_calc = sum(p["t_humano_min"] for p in prod["pasos"])
    total_calc = lectura_calc + ejec_calc
    base = t["base"]
    factor = Decimal(1) if base == "estimado" else tol
    limite = Decimal(prom) * factor

    if Decimal(total_calc) > Decimal(prom) * tol:
        h.append(c.hallazgo("L1-03", "BLOQUEANTE", f"total recalculado {total_calc} min > tolerancia {tol} × prometido {prom} (lectura {lectura_calc} + pasos {ejec_calc}): no entra; volver a D3 (recortar alcance o prometer más tiempo)", "recalculo"))
    elif Decimal(total_calc) > limite:
        h.append(c.hallazgo("L1-03", "MAYOR", f"total recalculado {total_calc} min > {limite} (base «{base}»; prometido {prom})", "recalculo"))
    if lectura_calc > t["lectura_min"] + 1:
        h.append(c.hallazgo("L1-03", "MAYOR", f"lectura_min declarada {t['lectura_min']} < recalculada {lectura_calc} ({palabras} palabras a {wpm} wpm × {a.factor_locale})", "producto.json#tiempos.lectura_min"))
    if ejec_calc != t["ejecucion_min"]:
        h.append(c.hallazgo("L1-03", "MAYOR", f"ejecucion_min declarada {t['ejecucion_min']} != Σ pasos[].t_humano_min {ejec_calc}", "producto.json#pasos"))
    if t["lectura_min"] + t["ejecucion_min"] != t["total_min"]:
        h.append(c.hallazgo("L1-03", "MAYOR", "total_min != lectura_min + ejecucion_min", "producto.json#tiempos"))
    if Decimal(lectura_calc) * 100 > Decimal(prom) * lmax:
        h.append(c.hallazgo("L1-03", "MAYOR", f"la lectura ({lectura_calc} min) supera {lmax} % del tiempo prometido: recortar texto o mover texto a anexo de consulta", "recalculo"))

    detalle_tipos = None
    if a.autoprueba:
        try:
            ap_json = c.cargar_json(a.autoprueba)
        except (OSError, ValueError) as e:
            return c.error_uso(f"autoprueba inválida: {e}", 3)
        detalle_tipos, minutos_otro, minutos_total = [], 0, 0
        por_id = {p["id"]: p["t_humano_min"] for p in prod["pasos"]}
        for p in ap_json.get("pasos", []):
            total_p = 0
            for m in p.get("micro_acciones", []):
                if m["tipo"] == "otro":
                    mins = int(m.get("t_min", 0)) * int(m.get("n", 1))
                    minutos_otro += mins
                else:
                    if m["tipo"] not in t_tipo:
                        h.append(c.hallazgo("L1-03", "MAYOR", f"paso {p['id']}: tipo de micro-acción desconocido «{m['tipo']}» (válidos: {sorted(t_tipo)} u «otro» con t_min)", "autoprueba.json"))
                        continue
                    mins = int(t_tipo[m["tipo"]]) * int(m.get("n", 1))
                total_p += mins
            minutos_total += total_p
            declarado = por_id.get(p["id"])
            detalle_tipos.append({"paso": p["id"], "minutos_tipados": total_p, "t_humano_min_declarado": declarado})
            if declarado is not None and total_p != declarado:
                h.append(c.hallazgo("L1-03", "MENOR", f"paso {p['id']}: Σ micro-acciones {total_p} min != t_humano_min {declarado}", "autoprueba.json"))
        if minutos_total and Decimal(minutos_otro) * 2 > Decimal(minutos_total):
            h.append(c.hallazgo("L1-03", "MAYOR", "más de la mitad del tiempo de ejecución está en micro-acciones «otro» (no tipadas): la estimación no basta; exige corrida humana cronometrada (base cold_run_humano) antes de PASS [HIPÓTESIS]", "autoprueba.json"))

    desvio = None
    if a.medido_primer_paso_min is not None and a.estimado_primer_paso_min:
        if a.desvio_max_pct is None:
            return c.error_uso("falta --desvio-max-pct (parámetro producto.cold_run_desvio_max_pct aún no existe: ver references/dependencias.md)", 5)
        desvio = abs(a.medido_primer_paso_min - a.estimado_primer_paso_min) * 100 / a.estimado_primer_paso_min
        if desvio > a.desvio_max_pct:
            h.append(c.hallazgo("L1-03", "MAYOR", f"el primer paso medido ({a.medido_primer_paso_min} min) se desvía {desvio:.0f} % del estimado ({a.estimado_primer_paso_min} min): promete de más o de menos; recalibrar t_humano_min", "cronometraje"))
    return c.emitir("tiempo_total", ["L1-03"], h, {
        "palabras": palabras, "lectura_calc_min": lectura_calc, "ejecucion_calc_min": ejec_calc, "total_calc_min": total_calc,
        "prometido_min": prom, "base": base, "limite_min": str(limite), "desvio_primer_paso_pct": None if desvio is None else f"{desvio:.1f}",
        "autoprueba_por_paso": detalle_tipos,
    }, a.salida)


if __name__ == "__main__":
    sys.exit(main())
