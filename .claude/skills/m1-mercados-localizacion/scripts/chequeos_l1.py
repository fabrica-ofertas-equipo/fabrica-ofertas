#!/usr/bin/env python3
"""M1 - chequeos_l1.py: checks deterministas MQ-01..MQ-22 (departamentos/16 §6) sobre mercado.json y mercado.seleccion.json.

Quien lo corre: el RUNNER (o el dueño en N0) ANTES del QA; el QA (solo Read/Grep/Glob) lee su salida en `ofertas/<id>/qa/.l1/m1-v<n>.json`
(SC-2) y la cita. El Maker lo corre solo como autoverificacion: el QA NO toma el L1 de lo que escriba el Maker; sin el archivo del runner
(o con un hash que no coincide) la evidencia esta ausente y cada check cuenta con la severidad que le da el contrato.
Sin red, sin reloj (--hoy obligatorio), sin escribir fuera de --salida.

Uso (desde la raiz del repo; .venv por PyYAML y jsonschema):
  .venv/bin/python -I .claude/skills/m1-mercados-localizacion/scripts/chequeos_l1.py \\
      --mercado ofertas/OF-xxx/mercado.json [--seleccion ofertas/OF-xxx/mercado.seleccion.json] [--brief ofertas/OF-xxx/00-brief.yaml] \\
      [--fichas DIR_con_pais-XX.json] [--limites empresa/limites.yaml] [--parametros empresa/parametros.yaml] [--modo borrador|sellado] \\
      --hoy AAAA-MM-DD [--ventana-test AAAA-MM-DD AAAA-MM-DD] [--emparejamiento RUTA] [--salida l1.json]

Salida: JSON {checks_l1[] (forma de contratos/qa.schema.json), severidad_por_check, bloqueantes, mayores}. Exit 0 sin bloqueantes, 3 con bloqueantes, 5 falta un dato (fail-closed), 2 uso.
Un check sin los insumos para evaluarse sale `no_aplica` con el motivo (nunca `pass` por omision) y el QA debe pedir el insumo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _comun as C  # noqa: E402
import puntaje as P  # noqa: E402
import vigencia as V  # noqa: E402

METODO_MONEDA = {"blik": "PLN", "satispay": "EUR", "bancontact": "EUR", "eps": "EUR", "mb_way": "EUR", "multibanco": "EUR", "pix": "BRL", "amazon_pay": "USD"}
METODO_PAIS = {"blik": "PL", "pix": "BR"}
NEGACION = re.compile(r"(ningun|ningún|sin|no |nunca|tampoco|hipotesis|hipótesis|refut|evitar|prohib)", re.I)
TEXTO_PRIOR = re.compile(r"(favorit[oa]s?|\bprior(es)?\b|mejor mercado|mercado ganador|sobre todo (?:en )?[A-ZÁÉÍÓÚ]\w+)")
MARCAS_DECISION = {"hipotesis"}


class Checks:
    def __init__(self):
        self.items, self.sev = [], {}

    def add(self, cid, resultado, sev, detalle):
        self.items.append({"check_id": cid, "resultado": resultado, "detalle": detalle})
        self.sev[cid] = sev

    def ok(self, cid, sev, detalle="ok"):
        self.add(cid, "pass", sev, detalle)

    def fail(self, cid, sev, detalle):
        self.add(cid, "fail", sev, detalle)

    def na(self, cid, sev, detalle):
        self.add(cid, "no_aplica", sev, detalle)

    def resumen(self):
        b = sum(1 for i in self.items if i["resultado"] == "fail" and self.sev[i["check_id"]] == "BLOQUEANTE")
        m = sum(1 for i in self.items if i["resultado"] == "fail" and self.sev[i["check_id"]] == "MAYOR")
        return b, m


def sha(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        h.update(f.read())
    return "sha256:" + h.hexdigest()


def cargar_fichas(dir_):
    out = {}
    if dir_ and os.path.isdir(dir_):
        for n in sorted(os.listdir(dir_)):
            m = re.match(r"^(?:pais-)?([A-Z]{2})\.json$", n)
            if m:
                out[m.group(1)] = C.cargar_json(os.path.join(dir_, n))
    return out


def validar_esquema_mercado(m, modo="borrador"):
    """Devuelve (errores, pendientes_de_firma). En `borrador` (v1 del Maker, antes del gate H) se toleran SOLO los errores de
    fiscal.exposicion_aceptada nula con regimen diferido: la firma la pone el dueño en el gate H (v2, origen humano) y en `sellado` cuenta todo."""
    sys.path.insert(0, C.RAIZ)
    try:
        from scripts import validar_esquemas as VE  # type: ignore
    except Exception as e:  # pragma: no cover
        raise C.DatoFaltante(f"no se pudo importar scripts.validar_esquemas ({e}); usar .venv/bin/python -I") from e
    errs, pend = [], []
    for e in VE.errores_de_esquema("mercado", m):
        ruta = VE.ruta_json(e)
        if modo == "borrador" and ruta.startswith("/fiscal/exposicion_aceptada") and m["fiscal"]["regimen"] == "diferido" and m["fiscal"].get("exposicion_aceptada") is None:
            pend.append(ruta)
        else:
            errs.append(f"{ruta}: {e.validator}: {e.message[:140]}")
    errs += [f"float en {r}" for r in VE.buscar_floats(m)]
    return errs, sorted(set(pend))


def validar_esquema_seleccion(s):
    try:
        import jsonschema  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise C.DatoFaltante("jsonschema no disponible; usar .venv/bin/python -I") from e
    esq = C.cargar_json(os.path.join(C.AQUI, "mercado_seleccion.schema.propuesta.json"))
    errs = [f"/{'/'.join(map(str, e.absolute_path))}: {e.message[:140]}" for e in jsonschema.Draft202012Validator(esq).iter_errors(s)]
    errs += [f"float en {r}" for r in C.hay_float(s)]
    return errs


def textos(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from textos(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from textos(v)


def dinero_ok(d):
    return isinstance(d, dict) and isinstance(d.get("monto"), int) and not isinstance(d.get("monto"), bool) and isinstance(d.get("moneda"), str)


def chequear(m, s, brief, limites, params, fichas, hoy, ventana, emparejamiento, modo="borrador"):
    k = Checks()
    # ---- MQ-01 esquema
    errs, pend = validar_esquema_mercado(m, modo)
    (k.fail("MQ-01", "BLOQUEANTE", "; ".join(errs[:5])) if errs else
     k.ok("MQ-01", "BLOQUEANTE", "mercado.json valido contra mercado.schema.json 1.1.x" + (f" (BORRADOR: pendiente la firma de exposicion fiscal del gate H en {pend})" if pend else "")))
    if s is not None:
        e2 = validar_esquema_seleccion(s)
        (k.fail("MQ-01S", "MAYOR", "mercado.seleccion.json no cumple la PROPUESTA de esquema: " + "; ".join(e2[:5])) if e2 else k.ok("MQ-01S", "MAYOR", "seleccion valida contra la propuesta"))
    else:
        k.na("MQ-01S", "MAYOR", "sin mercado.seleccion.json")
    # ---- MQ-02/03 fichas
    if fichas:
        tr, vig_b, vig_m = [], [], []
        pais_sel = set(m["paises_segmentacion"])
        for iso, f in fichas.items():
            if iso not in pais_sel and not (s and iso in {r["pais"] for r in s.get("ranking", [])}):
                continue
            ev = V.evaluar_ficha(f, hoy, params)
            for b in ev["bloqueantes"]:
                (tr if b.get("regla") == "MQ-02" else vig_b).append(f"{iso}{b.get('ruta')}: {b.get('motivo')}")
            vig_m += [f"{iso}{x['ruta']}: {x['motivo']}" for x in ev["mayores"]]
        (k.fail("MQ-02", "BLOQUEANTE", "; ".join(tr[:6])) if tr else k.ok("MQ-02", "BLOQUEANTE", f"{len(fichas)} ficha(s): toda hoja con fuente, fecha y confianza"))
        (k.fail("MQ-03", "BLOQUEANTE", "; ".join(vig_b[:6])) if vig_b else k.ok("MQ-03", "BLOQUEANTE", "tarifas y legal vigentes"))
        if vig_m:
            # MQ-03M (spec 16 §3.4, cerrada por S-A: M1-21 / SC-17): el CPM vencido NO bloquea ni excluye ningun mercado; se usa
            # mult_cpm.central (1,2) y el 1,5 (estres) es solo sensibilidad. MAYOR si falta la etiqueta [SUPUESTO] en cpm_fuente o,
            # habiendo seleccion, la bandera cpm_vencido (parametros_usados.cpm_vencido o ranking[].banderas).
            etiquetado = "[SUPUESTO]" in m.get("cpm_fuente", "")
            bandera = s is None or bool(s.get("parametros_usados", {}).get("cpm_vencido")) or any("cpm_vencido" in r.get("banderas", []) for r in s.get("ranking", []))
            if etiquetado and bandera:
                k.add("MQ-03M", "pass", "MAYOR", "CPM vencido con etiqueta [SUPUESTO] en cpm_fuente" + ("" if s is None else " y bandera cpm_vencido") + " (central; 1,5 solo sensibilidad)")
            else:
                falta = [x for x, ok in (("etiqueta [SUPUESTO] en cpm_fuente", etiquetado), ("bandera cpm_vencido en la seleccion", bandera)) if not ok]
                k.fail("MQ-03M", "MAYOR", "CPM vencido sin " + " ni ".join(falta) + ": " + "; ".join(vig_m[:3]))
    else:
        for c in ("MQ-02", "MQ-03"):
            k.na(c, "BLOQUEANTE", "sin fichas de pais (--fichas): el QA debe pedirlas; no se da por pasado")
    # ---- MQ-04 moneda <-> metodo
    if s is not None:
        malos = []
        prefs = {r["moneda"] for r in s.get("precio_referencia", [])}
        for r in s.get("metodos_locales_recomendados", []):
            mid, req = r["metodo"], r["moneda_requerida"]
            if mid in METODO_MONEDA and req != METODO_MONEDA[mid]:
                malos.append(f"{mid} exige {METODO_MONEDA[mid]} (declarado {req})")
            if mid in METODO_PAIS and r["pais"] != METODO_PAIS[mid]:
                malos.append(f"{mid} solo clientes de {METODO_PAIS[mid]} (declarado {r['pais']})")
            if mid == "klarna" and r["pais"] != "US":
                malos.append("klarna solo clientes de EE. UU.")
            if mid == "amazon_pay":
                malos.append("amazon_pay solo USD: no sirve para precios en moneda local")
            if req not in prefs:
                malos.append(f"{mid}: no hay precio_referencia en {req}")
        if m["moneda_cobro"] != "USD" and m["metodos_pago"]["activos"] and set(m["metodos_pago"]["activos"]) - {"card", "apple_pay", "google_pay", "link"}:
            malos.append("metodos_pago.activos con metodos fuera de la fase vigente")
        (k.fail("MQ-04", "BLOQUEANTE", "; ".join(malos)) if malos else k.ok("MQ-04", "BLOQUEANTE", "metodos recomendados coherentes con moneda y pais"))
    else:
        k.na("MQ-04", "BLOQUEANTE", "sin seleccion")
    # ---- MQ-05 / MQ-06
    pp, lp = limites.get("paises_permitidos"), limites.get("locales_permitidos")
    if not pp or not lp:
        raise C.DatoFaltante("limites.paises_permitidos o locales_permitidos vacios o null: fail-closed (5)")
    fuera = [x for x in m["paises_segmentacion"] if x not in pp]
    (k.fail("MQ-05", "BLOQUEANTE", f"paises fuera de paises_permitidos: {fuera}" if fuera else f"locale {m['locale']} fuera de locales_permitidos")
     if fuera or m["locale"] not in lp else k.ok("MQ-05", "BLOQUEANTE", "paises y locale dentro de limites"))
    if fichas and all(x in fichas for x in m["paises_segmentacion"]):
        malas = [x for x in m["paises_segmentacion"] if m["moneda_cobro"] not in (C.valor(fichas[x], "identidad", "monedas_cobro_posibles", defecto=[]) or [])]
        (k.fail("MQ-06", "MAYOR", f"moneda_cobro {m['moneda_cobro']} no valida para {malas}") if malas else k.ok("MQ-06", "MAYOR", "moneda valida para todo el cluster"))
        mons = {C.valor(fichas[x], "identidad", "moneda_local") for x in m["paises_segmentacion"]}
        if len(mons) > 1 and not m["monedas_precio_adicionales"] and m["moneda_cobro"] not in mons:
            k.fail("MQ-06C", "MAYOR", "cluster con monedas locales distintas: separar por moneda (un bloque = 1 locale + 1 moneda)")
    else:
        k.na("MQ-06", "MAYOR", "faltan fichas de los paises del cluster")
    # ---- MQ-07 fiscal
    f = m["fiscal"]
    prob, nota_firma = [], ""
    if f["regimen"] == "diferido":
        ex = f["exposicion_aceptada"]
        if not ex:
            if modo != "sellado":
                nota_firma = " (BORRADOR: exposicion_aceptada pendiente del gate H; modo sellado la exige)"
            else:
                prob.append("diferido sin exposicion_aceptada firmada")
        else:
            if not set(m["paises_segmentacion"]) <= set(ex["paises"]):
                prob.append("exposicion_aceptada no cubre todo el cluster")
            if ex["firmada_por"].get("tipo") != "humano" or not ex["firmada_por"].get("firma"):
                prob.append("la firma de exposicion debe ser humana y con firma")
        if re.search(r"iva incluido|vat included|iva inclusa|z vat", " ".join(textos(m)) + " " + " ".join(textos(s or {})), re.I):
            prob.append("texto de 'IVA incluido' con regimen diferido")
    if s and fichas:
        for fp in s.get("carga_fiscal", {}).get("paises", []):
            if fp["pais"] in fichas:
                t_f = C.valor(fichas[fp["pais"]], "fiscal", "tasa_bp")
                if t_f is not None and t_f != fp["tasa_bp"]:
                    prob.append(f"tasa {fp['pais']}: {fp['tasa_bp']} != ficha {t_f}")
    (k.fail("MQ-07", "BLOQUEANTE", "; ".join(prob)) if prob else k.ok("MQ-07", "BLOQUEANTE", "fiscal coherente" + (nota_firma or " (el sellado exige la firma humana real: X32_FISCAL)")))
    # ---- MQ-08 consumo
    if fichas and all(x in fichas for x in m["paises_segmentacion"]):
        dif = []
        for x in m["paises_segmentacion"]:
            d = C.valor(fichas[x], "consumo_y_datos", "desistimiento", "dias")
            if d is not None and d != m["consumo"]["desistimiento_dias"]:
                dif.append(f"{x}: desistimiento {m['consumo']['desistimiento_dias']} != ficha {d}")
            b = C.valor(fichas[x], "consumo_y_datos", "boton_arrepentimiento")
            if b is not None and b != m["consumo"]["boton_arrepentimiento"]:
                dif.append(f"{x}: boton_arrepentimiento != ficha")
        (k.fail("MQ-08", "MAYOR", "; ".join(dif)) if dif else k.ok("MQ-08", "MAYOR", "consumo coincide con la ficha"))
    else:
        k.na("MQ-08", "MAYOR", "faltan fichas")
    # ---- MQ-09 pesos y puntajes
    if s is not None:
        pesos = s["parametros_usados"]["pesos"]
        mal = []
        if sum(pesos.values()) != 100:
            mal.append(f"pesos suman {sum(pesos.values())}")
        if s["parametros_usados"]["peso_ajuste_creadores"] != 0:
            mal.append("peso de creadores != 0")
        for r in s["ranking"]:
            calc = sum(Decimal(pesos[c]) * Decimal(r["puntajes"][c]) / Decimal(5) for c in pesos if c in r["puntajes"]) * Decimal(100) / Decimal(sum(pesos.values()))
            if abs(calc - Decimal(r["total"])) > Decimal(str(C.pedir(params, "tolerancia_reproduccion_puntaje"))):
                mal.append(f"{r['pais']}: total {r['total']} != recalculado {calc.quantize(Decimal('0.1'))}")
        rep = P.reproducir()
        if not rep["ok"]:
            mal.append("rank.py ya no reproduce los 15 totales de 08 §2.2 / el escenario corregido")
        (k.fail("MQ-09", "BLOQUEANTE", "; ".join(mal)) if mal else k.ok("MQ-09", "BLOQUEANTE", "pesos=100, creadores=0, totales reproducidos y rank.py OK"))
    else:
        k.na("MQ-09", "BLOQUEANTE", "sin seleccion")
    # ---- MQ-10 hipotesis / sin prior
    mal = []
    if m["estado_decision"] != "hipotesis":
        mal.append("estado_decision != hipotesis")
    ev = m["evidencia_propia"]
    if m["estado_decision"] == "hipotesis" and any(ev[x] for x in ev):
        mal.append("evidencia_propia != 0 con estado hipotesis")
    for t in list(textos(m)) + list(textos(s or {})):
        for mt in TEXTO_PRIOR.finditer(t):
            ventana_txt = t[max(0, mt.start() - 45): mt.start()]
            if not NEGACION.search(ventana_txt) and not NEGACION.search(t[mt.end(): mt.end() + 25]):
                mal.append(f"texto con tono de prior/favorito: '{t[max(0, mt.start() - 20): mt.end() + 20]}'")
                break
    (k.fail("MQ-10", "BLOQUEANTE", "; ".join(mal[:4])) if mal else k.ok("MQ-10", "BLOQUEANTE", "hipotesis, evidencia propia 0, sin lenguaje de prior"))
    # ---- MQ-11 revisor
    rl = m["revision_linguistica"]
    (k.fail("MQ-11", "BLOQUEANTE", "obligacion_legal_idioma sin revisor_nativo: no sellar (X32_REVISOR)")
     if rl["obligacion_legal_idioma"] and not rl["revisor_nativo"] else k.ok("MQ-11", "BLOQUEANTE", "revisor coherente con la obligacion de idioma"))
    # ---- MQ-12 matriz X1
    if s is not None and s.get("matriz_ref"):
        mr = s["matriz_ref"]
        ruta = os.path.join(C.RAIZ, mr["archivo"]) if mr.get("archivo") else None
        if ruta and os.path.exists(ruta):
            (k.ok("MQ-12", "BLOQUEANTE", "hash de la matriz coincide") if mr.get("sha256") == sha(ruta) else k.fail("MQ-12", "BLOQUEANTE", "hash citado != hash de la matriz actual (rehacer EXPO y R3)"))
        elif mr.get("estado", "").startswith("[SUPUESTO]"):
            k.add("MQ-12", "pass", "BLOQUEANTE", "[SUPUESTO] sin matriz de X1 (no existe): se uso la semilla del Anexo D; el hallazgo queda como riesgo residual")
        else:
            k.fail("MQ-12", "BLOQUEANTE", "matriz_ref sin archivo existente ni marca [SUPUESTO]")
    else:
        k.na("MQ-12", "BLOQUEANTE", "sin matriz_ref en la seleccion")
    # ---- MQ-13 cobertura con metodos de la fase (+ recomputo con fichas)
    if s is not None:
        mal = []
        for r in s["ranking"]:
            suman = set(r["cobertura"].get("suman", []))
            if suman & P.NUNCA_SUMAN:
                mal.append(f"{r['pais']}: suma {sorted(suman & P.NUNCA_SUMAN)}")
            if s["fase_pagos"] == P.FASE_ESTANDAR and suman - P.ESTANDAR:
                mal.append(f"{r['pais']}: suma {sorted(suman - P.ESTANDAR)} fuera de la fase estandar")
            if r["pais"] in fichas:
                cob = P.cobertura_por_fase(fichas[r["pais"]], s["decision_managed_payments"])[s["fase_pagos"]]
                if abs(Decimal(cob["cobertura_pct"]) - Decimal(r["cobertura"]["fase_vigente_pct"])) > Decimal("0.5"):
                    mal.append(f"{r['pais']}: cobertura {r['cobertura']['fase_vigente_pct']} != recalculada {cob['cobertura_pct']}")
        (k.fail("MQ-13", "BLOQUEANTE", "; ".join(mal)) if mal else k.ok("MQ-13", "BLOQUEANTE", "cobertura con metodos de la fase"))
    else:
        k.na("MQ-13", "BLOQUEANTE", "sin seleccion")
    # ---- MQ-14 tarifa de Meta
    if s is not None and fichas:
        mal = []
        for r in s["ranking"]:
            if r["pais"] in fichas:
                tf = C.valor(fichas[r["pais"]], "meta", "recargo_meta_bp") or 0
                if tf > 0 and r.get("tarifa_meta_bp") != tf:
                    mal.append(f"{r['pais']}: tarifa_meta_bp {r.get('tarifa_meta_bp')} != ficha {tf}")
        (k.fail("MQ-14", "MAYOR", "; ".join(mal)) if mal else k.ok("MQ-14", "MAYOR", "tarifa de ubicacion de Meta incluida donde aplica"))
    else:
        k.na("MQ-14", "MAYOR", "faltan seleccion o fichas")
    # ---- MQ-15 gate H
    mal = []
    if m["primer_lanzamiento_en_locale"] and not m["requiere_gate_h"]:
        mal.append("primer lanzamiento sin requiere_gate_h")
    ap = m["aprobado_por"]
    if m["primer_lanzamiento_en_locale"] and ap is not None and (ap.get("tipo") != "humano" or not ap.get("firma")):
        mal.append("aprobado_por sin firma humana en un primer lanzamiento")
    (k.fail("MQ-15", "BLOQUEANTE", "; ".join(mal)) if mal else k.ok("MQ-15", "BLOQUEANTE", "gate H coherente (aprobado_por null hasta la firma)"))
    # ---- MQ-16 / MQ-19 presupuesto
    if s is not None:
        mx = C.pedir(params, "mercados_test_paralelos_max")
        pt = s["presupuesto_test_sugerido"]
        mal, mal19 = [], []
        if max(pt["mercados"], s["elegido"].get("n_mercados_test", 1)) > mx:
            mal.append(f"mercados {max(pt['mercados'], s['elegido'].get('n_mercados_test', 1))} > mercados_test_paralelos_max {mx}")
        if pt.get("tope_limites") is None and not pt["limites_pendientes"]:
            mal.append("sin tope de limites y sin limites_pendientes")
        if pt.get("tope_limites") and pt["total"]["monto"] > pt["tope_limites"]["monto"]:
            mal.append("presupuesto sugerido > tope de limites")
        (k.fail("MQ-16", "MAYOR", "; ".join(mal)) if mal else k.ok("MQ-16", "MAYOR", "mercados y presupuesto dentro de topes (o limites_pendientes)"))
        clics_min = C.pedir(params, "clics_min_decidir_mercado")
        if not dinero_ok(pt["cpc_central"]) or not dinero_ok(pt["por_mercado"]):
            mal19.append("cpc_central o por_mercado no son dinero entero")
        else:
            esperado = pt["clics_por_mercado"] * pt["cpc_central"]["monto"]
            if abs(esperado - pt["por_mercado"]["monto"]) > max(1, pt["clics_por_mercado"] // 1000):
                mal19.append(f"por_mercado {pt['por_mercado']['monto']} != clics x CPC {esperado} (¿f_meta aplicado dos veces?)")
        if pt.get("cpc_incluye_f_meta_una_vez") is not True:
            mal19.append("falta confirmar que el CPC incluye f_meta una sola vez")
        if (pt["clics_por_mercado"] < clics_min or (pt.get("tope_limites") and pt["total"]["monto"] < pt["mercados"] * pt["por_mercado"]["monto"])) and pt["etiqueta"] != "senal_de_proceso":
            mal19.append("presupuesto/clics bajo clics_min_decidir_mercado presentado como decision de mercado: debe decir señal de proceso")
        (k.fail("MQ-19", "MAYOR", "; ".join(mal19)) if mal19 else k.ok("MQ-19", "MAYOR", "presupuesto = K x clics_min x CPC y etiqueta honesta"))
    else:
        k.na("MQ-16", "MAYOR", "sin seleccion")
        k.na("MQ-19", "MAYOR", "sin seleccion")
    # ---- MQ-17 cpm
    mal = []
    cpm = m["cpm_esperado"]
    if cpm is not None and not dinero_ok(cpm):
        mal.append("cpm_esperado no es dinero entero en unidad menor")
    if not m["cpm_fuente"].strip():
        mal.append("cpm_fuente vacio")
    if s is not None and "contradicciones" not in s:
        mal.append("falta el campo contradicciones[] (puede ir vacio si se reviso)")
    (k.fail("MQ-17", "MAYOR", "; ".join(mal)) if mal else k.ok("MQ-17", "MAYOR", "cpm en unidad menor con fuente; contradicciones registradas"))
    # ---- MQ-18 neto completo y estacionalidad
    if s is not None:
        pu, mal = s["parametros_usados"], []
        for c in ("reembolso_bp", "disputa_bp", "stripe_tax"):
            if c not in pu:
                mal.append(f"falta {c} en parametros_usados (neto completo)")
        if ventana:
            ini, fin = C.fecha(ventana[0]), C.fecha(ventana[1])
            toca_q4 = any((d.month in (11, 12)) for d in (ini, fin))
            if toca_q4 and Decimal(str(pu["mult_cpm_efectivo"])) < Decimal(str(params["mult_cpm"]["central"])):
                mal.append("ventana nov-dic con mult_cpm_efectivo < central (CPM de julio sin ajuste)")
        else:
            k.na("MQ-18V", "MAYOR", "sin --ventana-test: no se comprobo el mult_cpm por estacionalidad")
        (k.fail("MQ-18", "BLOQUEANTE", "; ".join(mal)) if mal else k.ok("MQ-18", "BLOQUEANTE", "neto completo declarado y mult_cpm acorde a la ventana"))
    else:
        k.na("MQ-18", "BLOQUEANTE", "sin seleccion")
    # ---- MQ-20 managed payments
    if s is not None:
        rm, mal = s["rama_managed_payments"], []
        for rama in ("si", "no"):
            if rama not in rm:
                mal.append(f"falta la rama {rama}")
        if s["decision_managed_payments"] == "no_decidido" and rm.get("rama_estandar_resta_metodos") is True:
            mal.append("con no_decidido la rama estandar no resta metodos ni suma 3,5 %")
        (k.fail("MQ-20", "MAYOR", "; ".join(mal)) if mal else k.ok("MQ-20", "MAYOR", "ambas ramas informadas"))
    else:
        k.na("MQ-20", "MAYOR", "sin seleccion")
    # ---- MQ-21 brief
    if brief:
        mo = brief["mercado_objetivo"]
        dif = [c for c in ("locale", "moneda_cobro") if mo[c] != m[c]]
        if set(mo["paises_segmentacion"]) != set(m["paises_segmentacion"]):
            dif.append("paises_segmentacion")
        (k.fail("MQ-21", "MAYOR", f"mercado.json difiere de brief.mercado_objetivo en {dif}: M1 no cambia el brief, escala a O0") if dif else k.ok("MQ-21", "MAYOR", "coincide con brief.mercado_objetivo"))
    else:
        k.na("MQ-21", "MAYOR", "sin brief")
    # ---- MQ-22 transferencia
    if emparejamiento is not None:
        mal = []
        for e in emparejamiento.get("pares", []):
            if e.get("origen") == "transferencia" and not e.get("evidencia_local") and e.get("estado") not in ("hipotesis_de_transferencia", "bloqueado"):
                mal.append(f"{e.get('candidato_id')}/{e.get('locale')}: transferencia sin evidencia local declarada '{e.get('estado')}'")
        (k.fail("MQ-22", "BLOQUEANTE", "; ".join(mal)) if mal else k.ok("MQ-22", "BLOQUEANTE", "ninguna transferencia declarada valida sin barrido local"))
    else:
        k.na("MQ-22", "BLOQUEANTE", "sin emparejamiento")
    return k


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mercado", required=True)
    ap.add_argument("--seleccion")
    ap.add_argument("--brief")
    ap.add_argument("--fichas")
    ap.add_argument("--limites", default=os.path.join(C.RAIZ, "empresa", "limites.yaml"))
    ap.add_argument("--parametros")
    ap.add_argument("--modo", choices=["borrador", "sellado"], default="borrador", help="borrador tolera solo la firma de exposicion pendiente del gate H; sellado no tolera nada")
    ap.add_argument("--hoy", required=True)
    ap.add_argument("--ventana-test", nargs=2)
    ap.add_argument("--emparejamiento")
    ap.add_argument("--salida")
    a = ap.parse_args(argv)
    try:
        m = C.cargar_json(a.mercado)
        s = C.cargar_json(a.seleccion) if a.seleccion else None
        brief = C.cargar_datos(a.brief) if a.brief else None
        limites = C.cargar_datos(a.limites)
        params, _ = C.cargar_parametros(a.parametros)
        emp = C.cargar_json(a.emparejamiento) if a.emparejamiento else None
        k = chequear(m, s, brief, limites, params, cargar_fichas(a.fichas), a.hoy, a.ventana_test, emp, a.modo)
    except C.DatoFaltante as e:
        C.imprimir_error(e)
        return C.SALIDA_FALTA_DATO
    except (OSError, KeyError, ValueError, TypeError) as e:
        C.imprimir_error(f"{type(e).__name__}: {e}")
        return C.SALIDA_USO
    b, mm = k.resumen()
    out = {"checks_l1": k.items, "severidad_por_check": k.sev, "bloqueantes": b, "mayores": mm, "hoy": a.hoy,
           "sha256_mercado": sha(a.mercado), "sha256_seleccion": sha(a.seleccion) if a.seleccion else None}
    C.escribir_json(out, a.salida)
    return C.SALIDA_VALIDACION if b else C.SALIDA_OK


if __name__ == "__main__":
    sys.exit(main())
