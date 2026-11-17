#!/usr/bin/env python3
"""d7.py: ayudas deterministas de la skill D7 (armado de campaña en Meta). Sin red, sin escrituras en Meta.

Envuelve código que ya existe (``meta.nombres``, ``meta.payloads.calcular_presupuesto`` —única implementación del presupuesto—,
``meta.preflight``, ``scripts.validar_esquemas``) y agrega las comprobaciones L1 de D7 que ese código aún no hace (ver
``references/dependencias.md``). No decide dinero: calcula y compara contra ``limites.yaml`` y ``parametros.yaml``.

Uso (desde la raíz del repositorio, con el intérprete del proyecto)::

    .venv/bin/python .claude/skills/d7-campanas-meta/scripts/d7.py presupuesto --entrada e.json [--salida s.json]
    .venv/bin/python .../d7.py nombres campana|conjunto|anuncio|url|resolver ...
    .venv/bin/python .../d7.py sellar --campana ofertas/<id>/07-campana/campana.json
    .venv/bin/python .../d7.py validar --esquema campana --archivo ruta.json
    .venv/bin/python .../d7.py lint --dir ofertas/<id> [--limites L --parametros P --terminos T]
    .venv/bin/python .../d7.py preflight --entradas e.json --campana c.json [--salida preflight.json]

Códigos de salida (convenciones §8): 0 correcto · 2 uso · 3 validación · 4 bloqueado/hallazgos BLOQUEANTE o MAYOR · 5 límite o
parámetro ausente. Todo importe es entero en la unidad menor de la moneda; nunca ``float``.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import parse_qsl, urlparse

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))

import yaml  # noqa: E402

from engine import comun  # noqa: E402
from engine.errores import ErrorFabrica, ErrorLimite, ErrorUso, ErrorValidacion, ParametroFaltante  # noqa: E402
from engine.limites import Limites  # noqa: E402
from engine.parametros import Parametros  # noqa: E402
from meta import monedas, nombres, payloads  # noqa: E402
from meta import preflight as pf  # noqa: E402
from scripts import validar_esquemas as V  # noqa: E402

EU27 = frozenset("AT BE BG HR CY CZ DK EE FI FR DE GR HU IE IT LV LT LU MT NL PL PT RO SK SI ES SE".split())
UE_UK = EU27 | {"GB"}  # [VERIFICAR] si EEE (IS, LI, NO) entra en DSA; hoy no se incluye
EVENTO_META = {"Purchase": "PURCHASE", "InitiateCheckout": "INITIATE_CHECKOUT"}
MEJORAS_META = ("text_optimizations", "image_touchups", "image_animation", "inline_comment", "enhance_cta")
BLOQUEA = ("BLOQUEANTE", "MAYOR")


# ----------------------------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------------------------
def _leer(ruta: Path) -> Any:
    ruta = Path(ruta)
    if ruta.suffix in (".yaml", ".yml"):
        return yaml.safe_load(ruta.read_text(encoding="utf-8"))
    return json.loads(ruta.read_text(encoding="utf-8"))


def _salida(datos: Any, ruta: str | None) -> None:
    texto = json.dumps(datos, indent=2, sort_keys=True, ensure_ascii=False)
    if ruta:
        Path(ruta).write_text(texto + "\n", encoding="utf-8")
    print(texto)


def _techo(a: int, b: int) -> int:
    return -(-a // b)


def _con_tarifa(monto: int, bp: int) -> int:
    """``monto × (1 + tarifa)`` redondeado hacia arriba (peor caso facturado; la tarifa va en la factura, no en Ads Manager)."""
    return _techo(monto * (10000 + bp), 10000)


def _limites_de(obj: Mapping[str, Any]) -> Limites:
    return Limites(datos=dict(obj), entorno="prueba")


def _parametros_de(plano: Mapping[str, Any]) -> Parametros:
    grupos: dict[str, dict[str, Any]] = {}
    for clave, valor in plano.items():
        grupo, nombre = clave.split(".")
        grupos.setdefault(grupo, {})[nombre] = {"valor": valor}
    return Parametros({"schema_version": "1.1.0", "version": 1, "grupos": grupos})


def _cargar_limites_parametros(args: argparse.Namespace, entrada: Mapping[str, Any] | None = None) -> tuple[Limites, Parametros]:
    entrada = entrada or {}
    if "limites" in entrada:
        lim = _limites_de(entrada["limites"])
    else:
        lim = Limites(datos=_leer(Path(args.limites) if args.limites else RAIZ / "empresa" / "limites.yaml"), entorno="desarrollo")
    if "parametros" in entrada:
        par = _parametros_de(entrada["parametros"])
    else:
        par = Parametros(_leer(Path(args.parametros) if args.parametros else RAIZ / "empresa" / "parametros.yaml"))
    return lim, par


# ----------------------------------------------------------------------------------------------
# presupuesto: economía -> n_anuncios, total, diario, spend_cap, evento (departamentos/08 §3.4 y Anexo A3)
# ----------------------------------------------------------------------------------------------
def umbral_purchase(cpa_esperado: int, par: Parametros) -> Fraction:
    """Presupuesto diario mínimo para optimizar por PURCHASE: fracción × (eventos_semana / 7) × cpa_esperado."""
    eventos = Fraction(int(par.valor("estadistica.meta_eventos_aprendizaje_semana")))
    fraccion = Fraction(str(par.valor("estadistica.meta_fraccion_min_purchase")))
    return fraccion * eventos / 7 * cpa_esperado


def presupuesto(e: Mapping[str, Any], lim: Limites, par: Parametros) -> tuple[int, dict[str, Any]]:
    """Devuelve ``(código_de_salida, resultado)``. Todos los topes salen de ``lim`` y ``par``; sin dato, ``ErrorLimite`` (5)."""
    moneda, cpa_be, cpa_esp = e["moneda"], int(e["cpa_be"]), int(e["cpa_esperado"])
    t = int(e.get("tarifa_meta_bp", 0))
    avisos: list[str] = []
    if e.get("veredicto_economia") == "NO_FACTIBLE" or cpa_esp > cpa_be:
        return 4, {"estado": "NO_FACTIBLE", "avisos": ["el CPA esperado supera el CPA de equilibrio: el escenario central pierde dinero; "
                                                          "no se gasta; escalar al dueño (04 §8.3)"]}
    tope_diario = int(lim.valor("gasto_diario_por_oferta"))
    factor_techo = V.dec(lim.valor("factor_techo_teorico_diario"))
    techo_total = min(int(lim.valor("gasto_total_test_por_oferta")), int(lim.valor("perdida_max_test_por_oferta")))
    if lim.valor("moneda_limites") != moneda:
        raise ErrorValidacion(f"moneda de la campaña {moneda} distinta de moneda_limites: hace falta tipo de cambio registrado")
    dias = int(e.get("dias_test") or par.valor("campana.dias_test_defecto"))
    if not int(par.valor("campana.dias_test_min")) <= dias <= int(par.valor("campana.dias_test_max")):
        raise ErrorValidacion(f"dias_test {dias} fuera de [campana.dias_test_min, campana.dias_test_max]")
    # n_anuncios, corte/validar, total, diario, spend_cap o candado: una sola implementación (meta.payloads, A6 resuelto por S-B)
    completo = payloads.calcular_presupuesto(
        moneda=moneda, dias=dias, limites=lim, parametros=par, spend_cap_minimo_meta_minor=e.get("spend_cap_minimo_meta"),
        inicio=comun.parsear_z(e["inicio"]), tarifa_meta_bp=t, cpa_max_minor=cpa_be, cpa_esperado_minor=cpa_esp,
        n_anuncios_paquete=int(e["n_anuncios_paquete"]))
    pres = {c: completo[c] for c in payloads.CAMPOS_PRESUPUESTO_SCHEMA if c in completo}  # lo que admite campana.presupuesto
    n, k, corte, validar, solo_refuta = completo["n_anuncios"], completo["k_corte"], completo["corte"], completo["validar"], completo["solo_refuta"]
    total_plan = corte if solo_refuta else max(corte, validar)
    if solo_refuta:
        avisos.append("SOLO_REFUTA: el presupuesto cubre descartar (n × k × cpa_max) pero no validar (n_dec × cpa_esperado); declararlo en la tarjeta")
    if pres["max_teorico_diario"] > tope_diario:
        sugeridos = next((d for d in range(dias, int(par.valor("campana.dias_test_max")) + 1)
                          if _techo(int(factor_techo * 100) * (pres["total_test"] // d), 100) <= tope_diario), None)
        raise ErrorLimite(f"diario × {factor_techo} = {pres['max_teorico_diario']} supera gasto_diario_por_oferta {tope_diario}; "
                          f"aborta (dias que lo harían caber: {sugeridos})", detalle={"dias_sugeridos": sugeridos})
    if e.get("min_diario_cuenta") and pres["diario"] < int(e["min_diario_cuenta"]):
        raise ErrorLimite(f"diario {pres['diario']} < mínimo diario de la cuenta {e['min_diario_cuenta']}")
    cap = pres["spend_cap"] if pres["spend_cap"] is not None else pres["candado_alternativo"]["lifetime_budget"]
    peor_facturado = _con_tarifa(cap, t)
    if peor_facturado > techo_total:
        raise ErrorLimite(f"peor caso facturado {peor_facturado} > techo_total {techo_total} (S22)")
    # evento de optimización
    evento_eco = EVENTO_META[e["evento_economia"]]
    evento = {"economia": evento_eco, "campana": evento_eco, "recomendado": None, "umbral_diario": None, "falta_diario": None, "eventos_semana": None}
    try:
        umbral = umbral_purchase(cpa_esp, par)
        rec = "PURCHASE" if pres["diario"] >= umbral else "INITIATE_CHECKOUT"
        evento.update(recomendado=rec, umbral_diario=_techo(umbral.numerator, umbral.denominator),
                      falta_diario=max(0, _techo(umbral.numerator, umbral.denominator) - pres["diario"]) if rec == "INITIATE_CHECKOUT" else 0,
                      eventos_semana=str((Decimal(7 * pres["diario"]) / Decimal(cpa_esp)).quantize(Decimal("0.1"))))
    except ParametroFaltante as exc:
        avisos.append(f"evento recomendado no calculable: falta {exc}")
    estado = "OK"
    if evento_eco == "PURCHASE" and evento["recomendado"] is None:
        estado = "PARAMETRO_FALTANTE"
        avisos.append("PURCHASE no se puede confirmar sin estadistica.meta_*: no se arma con PURCHASE")
    elif evento_eco == "PURCHASE" and evento["recomendado"] == "INITIATE_CHECKOUT":
        estado = "EVENTO_INCOHERENTE"
        avisos.append(f"S7: economia pide PURCHASE pero el diario {pres['diario']} < umbral {evento['umbral_diario']} "
                      f"(faltan {evento['falta_diario']}/día): pedir a D3 reemitir economia con InitiateCheckout o decidir H")
    elif evento_eco == "INITIATE_CHECKOUT" and evento["recomendado"] == "PURCHASE":
        avisos.append("el presupuesto alcanzaría para PURCHASE; se mantiene INITIATE_CHECKOUT como pide economia (no se cambia en caliente)")
    resultado = {
        "estado": estado, "moneda": moneda, "n_anuncios": n, "k_corte": k, "cpa_max": cpa_be, "dias": dias,
        "corte": corte, "validar": validar, "total_plan": total_plan, "solo_refuta": solo_refuta,
        "techo_necesario_para_validar": completo["techo_necesario_para_validar"],
        "techo_total": techo_total, "facturado_plan": completo["facturado_plan"], "peor_caso_facturado": peor_facturado,
        "presupuesto": pres, "evento": evento,
        "monto_api": {"diario": monedas.a_unidad_meta(pres["diario"], moneda),
                      "spend_cap": monedas.a_unidad_meta(pres["spend_cap"], moneda) if pres["spend_cap"] is not None else None,
                      "offset_meta": monedas.offset_meta(moneda)},
        "avisos": avisos,
    }
    return (0 if estado == "OK" else 4), resultado


# ----------------------------------------------------------------------------------------------
# lint: comprobaciones L1 verificables sin leer Meta (C01, C03, C04, C05, C06, C09, C10, C11, C13, C14, C15)
# ----------------------------------------------------------------------------------------------
def _log(ruta: Path) -> list[dict[str, Any]]:
    if not ruta.is_file():
        return []
    return [json.loads(l) for l in ruta.read_text(encoding="utf-8").splitlines() if l.strip()]


def _query(url: str) -> dict[str, str]:
    return dict(parse_qsl(urlparse(url.replace("{{", "%7B%7B").replace("}}", "%7D%7D")).query, keep_blank_values=True))


def lint(d: Path, lim: Limites, par: Parametros, terminos: list[str] | None) -> list[dict[str, Any]]:
    R: list[dict[str, Any]] = []

    def f(check: str, sev: str, cod: str, msg: str) -> None:
        R.append({"check_id": check, "severidad": sev, "codigo": cod, "mensaje": msg[:300]})

    camp = _leer(d / "07-campana" / "campana.json")
    opt = lambda ruta: _leer(d / ruta) if (d / ruta).is_file() else None  # noqa: E731
    paq, chk, ofe, eco, mer = (opt("06-creativos/paquete.json"), opt("05-landing/checkout.json"), opt("03-oferta/oferta.json"),
                               opt("03-oferta/economia.json"), opt("mercado.json"))
    log = _log(d / "07-campana" / "lanzamiento.log")
    apro = opt("07-campana/aprobacion.json")
    # C01
    for e in V.errores_de_esquema("campana", camp)[:5]:
        f("C01", "BLOQUEANTE", "esquema_invalido", f"{V.ruta_json(e)}: {e.message[:160]}")
    h = V.hash_objeto(camp, ("hash_config",))
    if h != camp.get("hash_config"):
        f("C01", "BLOQUEANTE", "hash_config_no_coincide", f"recalculado {h[:19]} != declarado {str(camp.get('hash_config'))[:19]}")
    for nombre in ("preflight", "ids_meta", "lectura_viva"):
        otro = opt(f"07-campana/{nombre}.json")
        if otro and otro.get("hash_config") != camp.get("hash_config"):
            f("C01", "BLOQUEANTE", "hash_config_distinto", f"{nombre}.json sellado sobre otra versión de campana.json")
    if apro and apro.get("hash_objetivo") != camp.get("hash_config"):
        f("C01", "BLOQUEANTE", "aprobacion_de_version_anterior", "aprobacion.json aprueba un hash distinto del actual (S6)")
    # C03
    if not apro and any(str(x.get("effective_status", x.get("status"))) == "ACTIVE" for x in log if x.get("tipo", "").startswith("LECTURA")):
        f("C03", "BLOQUEANTE", "objeto_activo_antes_del_gate", "hay un objeto ACTIVE en el borrador y no existe aprobacion.json (S3)")
    errores = [x for x in log if x.get("tipo") == "ACTIVE_ERRORS"]
    if errores and errores[-1].get("errores"):
        f("C03", "BLOQUEANTE", "active_errors_no_vacio", f"última lectura de active_errors: {errores[-1]['errores'][:2]}")
    # C04
    try:
        p, ec = camp["presupuesto"], camp["economia"]
        t = int((eco or {}).get("entradas_usadas", {}).get("tarifa_meta_bp", -1)) if eco else -1
        if t < 0:
            f("C04", "BLOQUEANTE", "tarifa_meta_bp_ausente", "economia.entradas_usadas.tarifa_meta_bp ausente: no se puede fijar el techo facturado")
            t = 0
        techo_total = min(int(lim.valor("gasto_total_test_por_oferta")), int(lim.valor("perdida_max_test_por_oferta")))
        tope_diario = int(lim.valor("gasto_diario_por_oferta"))
        factor = V.dec(lim.valor("factor_techo_teorico_diario"))
        esperado_max = _techo(int(factor * 100) * p["diario"], 100)
        if p["max_teorico_diario"] != esperado_max:
            f("C04", "BLOQUEANTE", "max_teorico_mal_calculado", f"max_teorico_diario {p['max_teorico_diario']} != ceil(diario × {factor}) = {esperado_max}")
        if max(p["max_teorico_diario"], esperado_max) > tope_diario:
            f("C04", "BLOQUEANTE", "diario_x175_sobre_tope", f"diario {p['diario']} × {factor} = {esperado_max} > gasto_diario_por_oferta {tope_diario} (S2)")
        if p["diario"] * p["dias"] != p["total_test"]:
            f("C04", "BLOQUEANTE", "total_no_es_diario_por_dias", f"{p['diario']} × {p['dias']} != {p['total_test']}")
        cap = p["spend_cap"] if p["spend_cap"] is not None else (p["candado_alternativo"] or {}).get("lifetime_budget")
        if cap is None:
            f("C04", "BLOQUEANTE", "sin_spend_cap_ni_candado", "ni spend_cap ni candado_alternativo (stop_time + lifetime_budget) (S12)")
        elif _con_tarifa(cap, t) > techo_total or _con_tarifa(p["total_test"], t) > techo_total:
            f("C04", "BLOQUEANTE", "facturado_con_tarifa_sobre_techo", f"tope {cap} × (1 + {t} bp) > techo_total {techo_total} (S22)")
        exp = V.EXPONENTE_ISO4217.get(p["moneda"])
        if exp is None or p["decimales"] != exp:
            f("C04", "BLOQUEANTE", "decimales_no_iso", f"decimales {p['decimales']} != exponente ISO 4217 {exp} de {p['moneda']}: monto ×100 (S11)")
        if p["moneda"] != lim.valor("moneda_limites"):
            f("C04", "BLOQUEANTE", "moneda_distinta_de_limites", f"{p['moneda']} != moneda_limites: falta tipo de cambio registrado")
        for campo in ("diario", "spend_cap"):
            if p.get(campo) is not None:
                try:
                    monedas.a_unidad_meta(p[campo], p["moneda"])
                except ErrorValidacion as exc:
                    f("C04", "BLOQUEANTE", "monto_no_convierte_a_unidad_meta", exc.mensaje)
        n_min, n_tope = int(par.valor("campana.n_anuncios_min")), int(par.valor("campana.n_anuncios_tope"))
        if not n_min <= len(camp["anuncios"]) <= n_tope or ec["n_anuncios"] != len(camp["anuncios"]):
            f("C04", "BLOQUEANTE", "n_anuncios_fuera_de_rango", f"{len(camp['anuncios'])} anuncios; rango [{n_min}, {n_tope}]; economia.n_anuncios {ec['n_anuncios']}")
        if eco and (ec["cpa_max"] != eco["cpa_be"]["monto"] or ec["k_corte"] != int(par.valor("testeo.k_corte"))):
            f("C04", "BLOQUEANTE", "economia_desalineada", "cpa_max != economia.cpa_be o k_corte != testeo.k_corte")
        if eco and EVENTO_META.get(eco.get("evento_optimizacion_inicial")) != camp["evento_optimizacion"]:
            f("C04", "MAYOR", "evento_distinto_de_economia", f"campana {camp['evento_optimizacion']} != economia {eco.get('evento_optimizacion_inicial')}")
        if camp["evento_optimizacion"] == "PURCHASE" and eco:
            try:
                u = umbral_purchase(eco["cpa_real"]["central"]["monto"], par)
                if p["diario"] < u:
                    f("C04", "MAYOR", "purchase_sin_presupuesto_para_aprendizaje", f"diario {p['diario']} < umbral {_techo(u.numerator, u.denominator)} (S7)")
            except ParametroFaltante as exc:
                f("C04", "MAYOR", "parametro_ausente", f"no se puede verificar PURCHASE: {exc}")
    except ErrorFabrica as exc:
        f("C04", "BLOQUEANTE", "limite_ausente", exc.mensaje)
    # C05
    try:
        for tipo, valor in [("campana", camp["nombres"]["campana"]), ("conjunto", camp["nombres"]["conjunto"])] + \
                           [("anuncio", a) for a in camp["nombres"]["anuncios"]]:
            nombres.validar_nombre(tipo, valor)
    except ErrorValidacion as exc:
        f("C05", "BLOQUEANTE", "nombre_invalido", exc.mensaje)
    if sorted(camp["nombres"]["anuncios"]) != sorted(a["ad_name"] for a in camp["anuncios"]):
        f("C05", "BLOQUEANTE", "nombres_anuncios_desalineados", "nombres.anuncios != anuncios[].ad_name")
    for clave, valor in nombres.parametros_url_exigidos(camp["oferta_id"]).items():
        if _query(camp["url"]["plantilla"]).get(clave) != valor:
            f("C05", "BLOQUEANTE", "param_url_incorrecto", f"{clave} debe ser {valor!r} en la plantilla")
    for clave, valor in _query(camp["url"]["ejemplo_resuelto"]).items():
        if valor == "" or "{{" in valor:
            f("C05", "BLOQUEANTE", "param_url_vacio", f"ejemplo_resuelto: {clave} vacío o sin resolver (S1)")
    if paq and not camp["url"]["plantilla"].startswith(paq["destino"]["url_base"]):
        f("C05", "BLOQUEANTE", "url_fuera_de_destino", "la URL no parte de paquete.destino.url_base")
    # C06 (el 200 y las redirecciones se leen en vivo: P12)
    if paq and chk and paq["destino"]["precio"] != chk["precio"]:
        f("C06", "BLOQUEANTE", "precio_distinto_paquete_checkout", f"paquete {paq['destino']['precio']} != checkout {chk['precio']} (S4)")
    sitio = d / "05-landing" / "sitio"
    if paq and sitio.is_dir() and V.hash_directorio(sitio) != paq["destino"]["landing_hash"]:
        f("C06", "BLOQUEANTE", "landing_hash_cambio", "05-landing/sitio cambió después de crear los creativos")
    # C09
    if paq:
        if any(paq["politicas"]["meta_enhancements"].values()):
            f("C09", "MAYOR", "mejoras_meta_activas_en_paquete", "paquete.politicas.meta_enhancements tiene mejoras activas (S9)")
        pol = lim.get("politica_divulgacion_ia")
        if pol is None or paq["politicas"]["divulgacion_ia"] != pol:
            f("C09", "MAYOR", "divulgacion_ia_distinta_de_politica", f"paquete {paq['politicas']['divulgacion_ia']} != limites {pol}")
    for x in log:
        if x.get("tipo") == "LECTURA_ANUNCIO" and any(x.get("mejoras", {}).get(m, "OPT_OUT") != "OPT_OUT" for m in MEJORAS_META):
            f("C09", "MAYOR", "mejora_meta_activa_en_vivo", f"{x.get('ad_name')}: {x['mejoras']} (S9)")
    # C10 (el texto y los claims los compara el QA con lint_claims; aquí solo la recreación idéntica)
    rechazados = {x.get("asset_sha256") for x in log if x.get("tipo") == "RECHAZO"}
    for a in camp["anuncios"]:
        if a["asset_sha256"] in rechazados:
            f("C10", "BLOQUEANTE", "anuncio_rechazado_recreado_identico", f"{a['ad_name']} reutiliza el asset de un anuncio rechazado (S21)")
    # C11
    if mer:
        if camp["idioma"] != mer["locale"]:
            f("C11", "MAYOR", "idioma_distinto_de_mercado", f"campana {camp['idioma']} != mercado.json {mer['locale']} (S8)")
        if set(camp["paises"]) != set(mer["paises_segmentacion"]):
            f("C11", "MAYOR", "paises_distintos_de_mercado", f"{camp['paises']} != {mer['paises_segmentacion']}")
    for clave, valor in (("paises_permitidos", camp["paises"]), ("locales_permitidos", [camp["idioma"]])):
        permitidos = lim.get(clave) or []
        if not permitidos or not set(valor) <= set(permitidos):
            f("C13", "BLOQUEANTE", f"{clave}_no_incluye", f"{valor} no ⊆ limites.{clave} {permitidos} (S16)")
    # C13
    aud = camp["audiencia"]
    if aud["tipo"] in ("lookalike", "personalizada"):
        f("C13", "BLOQUEANTE", "audiencia_con_semilla", f"audiencia {aud['tipo']}: v0.1 solo amplia o intereses; sin semilla propia (S20)")
    if aud["genero"] != "todos" or aud["edad_min"] != ((lim.get("edad_minima_audiencia") or {}).get("defecto", 18)):
        f("C13", "MAYOR", "segmentacion_restringida_sin_gate", "género ≠ todos o edad_min ≠ edad_minima_audiencia: solo como prueba A/B con gate H")
    if camp["special_ad_categories"] and (aud["intereses"] or aud["edad_min"] != 18 or aud["edad_max"] != 65):
        f("C13", "BLOQUEANTE", "categoria_especial_con_segmentacion", "con categoría especial: sin intereses y edad 18-65")
    if ofe:
        riesgo = ofe["riesgo"]
        nivel = str(riesgo["nivel"]).lower()
        amarillos = [x for x in "PCN" if riesgo.get(x) == "amarillo"]
        # subnivel: el del snapshot si lo trae (lo emite scripts.nivel_riesgo; campo en el contrato = LT-04); si no, se deriva de los
        # colores de los ejes (>= 2 amarillos entre P, C, N = B) [SUPUESTO]. D7 no calcula el nivel: solo lo comprueba.
        sub = str(riesgo.get("subnivel") or ("B" if len(amarillos) >= 2 else "A")).upper()
        if nivel == "rojo" or (nivel == "amarillo" and sub == "B"):
            f("C13", "BLOQUEANTE", "nivel_no_se_arma", f"nivel {'rojo' if nivel == 'rojo' else 'amarillo-b'}: no se arma (S14)")
        elif nivel == "amarillo":
            claves = ("nivel_max_lanzable", "hojas_pausadas", "cuota_gasto_amarillo_max_pct", "envios_amarillo_a_semana")
            if any(lim.get(c) is None for c in claves):
                f("C13", "BLOQUEANTE", "amarillo_sin_claves_de_riesgo", "limites sin las claves de riesgo de 25 §10.1: solo verde (S15)")
            if not any(x.get("tipo") == "RHS" and x.get("estado") == "hecha" for x in log):
                f("C13", "BLOQUEANTE", "amarillo_a_sin_rhs", "falta la revisión humana de seguridad (RHS) registrada en lanzamiento.log")
        if nivel == "amarillo" and aud["tipo"] != "amplia" and set(camp["paises"]) & UE_UK:
            f("C13", "BLOQUEANTE", "amarillo_ue_uk_sin_audiencia_amplia", "amarillo en UE/UK solo con audiencia amplia")
    # Evidencia viva (C02, C03, C14): solo vale lo que genera código (07-campana/lectura_viva.json, meta.lectura_viva). Las LECTURA_* del
    # log las escribe el Maker: son bitácora y alerta (arriba, C03/C09/C14 pueden SUBIR un hallazgo con ellas), nunca prueba de que algo esté bien.
    ids = opt("07-campana/ids_meta.json")
    vivo = opt("07-campana/lectura_viva.json")
    if ids and vivo is None:
        f("C02", "MAYOR", "evidencia_viva_ausente", "hay ids_meta.json pero no 07-campana/lectura_viva.json generado por código: la entidad real no es verificable (las LECTURA_* del Maker no cuentan)")
    elif ids:
        objetos = [vivo.get("campana") or {}, vivo.get("conjunto") or {}, *(vivo.get("anuncios") or [])]
        if not apro and any(str(o.get("effective_status")) == "ACTIVE" for o in objetos):
            f("C03", "BLOQUEANTE", "objeto_activo_antes_del_gate", "lectura_viva.json: hay un objeto ACTIVE y no existe aprobacion.json (S3)")
        if any("effective_status" not in o for o in objetos):
            f("C03", "MAYOR", "evidencia_viva_incompleta", "lectura_viva.json no trae effective_status de todos los objetos: «todo PAUSED» no es verificable por código")
        if set(camp["paises"]) & EU27 and not all((vivo.get("conjunto") or {}).get(c) for c in ("dsa_beneficiary", "dsa_payor")):
            f("C14", "MAYOR", "evidencia_viva_incompleta", "lectura_viva.json no trae dsa_beneficiary y dsa_payor del conjunto: el DSA no es verificable por código")
    # C14
    if set(camp["paises"]) & EU27:
        if ids:
            # la prueba es la lectura viva de código; la línea LECTURA_CONJUNTO del Maker solo puede sumar una alerta, nunca sustituirla (SC-16)
            dsa_vivo = bool(vivo) and all((vivo.get("conjunto") or {}).get(c) for c in ("dsa_beneficiary", "dsa_payor"))
            con_dsa = {x.get("adset_id") for x in log if x.get("tipo") == "LECTURA_CONJUNTO" and x.get("dsa_beneficiary") and x.get("dsa_payor")}
            if dsa_vivo:
                con_dsa |= set(ids["adset_ids"])
            falta = [a for a in ids["adset_ids"] if a not in con_dsa]
            if falta:
                f("C14", "BLOQUEANTE", "dsa_ausente", f"conjuntos UE sin beneficiario y pagador DSA leídos de Meta: {falta} (S17)")
        else:
            f("C14", "MEJORA", "dsa_pendiente", "destino UE: el conjunto debe crearse con DSA (beneficiario y pagador = LLC); se comprueba al leer el borrador")
    # C15
    if terminos is None:
        f("C15", "BLOQUEANTE", "sin_lexico_terminos_sensibles", "no hay terminos_sensibles/<locale>.yaml (lo entrega X1): fail-closed")
    else:
        textos = [camp["nombres"]["campana"], camp["nombres"]["conjunto"], *camp["nombres"]["anuncios"], camp["url"]["plantilla"],
                  *(a["concepto_id"] for a in camp["anuncios"]), *([ofe["slug"]] if ofe else [])]
        for rx in terminos:
            for tx in textos:
                if re.search(rx, tx, re.IGNORECASE):
                    f("C15", "BLOQUEANTE", "termino_sensible_en_nombre_o_url", f"{rx!r} aparece en {tx[:60]!r}: viaja a la URL y a Meta (S18)")
    return R


# ----------------------------------------------------------------------------------------------
# preflight: envoltorio de meta.preflight.generar sobre hechos ya leídos (nunca llama a Meta)
# ----------------------------------------------------------------------------------------------
def preflight_cmd(args: argparse.Namespace) -> int:
    hechos, camp = _leer(Path(args.entradas)), _leer(Path(args.campana))
    modo = hechos.pop("modo", "fixture")
    for clave in ("active_errors", "objetos_ajenos"):
        if clave in hechos:
            hechos[clave] = tuple(hechos[clave])
    lim, par = _cargar_limites_parametros(args, hechos.pop("limites_parametros", None))
    ahora = comun.parsear_z(args.ahora) if args.ahora else None
    resultado = pf.generar(oferta_id=camp["oferta_id"], campana=camp, limites=lim, parametros=par, entradas=pf.Entradas(**hechos),
                           hash_config=camp["hash_config"], **({"ahora": (lambda: ahora)} if ahora else {}))
    errs = V.errores_de_esquema("preflight", resultado)
    if errs:
        raise ErrorValidacion("preflight inválido contra el esquema: " + "; ".join(e.message[:120] for e in errs[:3]))
    if args.salida:
        Path(args.salida).write_text(json.dumps(resultado, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"modo": modo, "semaforo": resultado["semaforo"], "preflight": resultado}, indent=2, sort_keys=True, ensure_ascii=False))
    if modo != "vivo":
        print("AVISO: modo fixture: este preflight nunca habilita activar (registrar modo en lanzamiento.log)", file=sys.stderr)
    return 0 if resultado["semaforo"] == "VERDE" else 4


# ----------------------------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="d7.py", description=__doc__.split("\n")[0])
    ap.add_argument("--limites"), ap.add_argument("--parametros")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("presupuesto"); s.add_argument("--entrada", required=True); s.add_argument("--salida")
    s = sub.add_parser("nombres"); s.add_argument("tipo", choices=("campana", "conjunto", "anuncio", "url", "resolver")); s.add_argument("campos", nargs="+")
    s = sub.add_parser("sellar"); s.add_argument("--campana", required=True)
    s = sub.add_parser("validar"); s.add_argument("--esquema", required=True); s.add_argument("--archivo", required=True)
    s = sub.add_parser("lint"); s.add_argument("--dir", required=True); s.add_argument("--terminos")
    s = sub.add_parser("preflight"); s.add_argument("--entradas", required=True); s.add_argument("--campana", required=True)
    s.add_argument("--salida"); s.add_argument("--ahora")
    try:
        args = ap.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2

    def cuerpo() -> int:
        if args.cmd == "presupuesto":
            entrada = _leer(Path(args.entrada))
            lim, par = _cargar_limites_parametros(args, entrada)
            codigo, res = presupuesto(entrada, lim, par)
            _salida(res, args.salida)
            return codigo
        if args.cmd == "nombres":
            c = args.campos
            fn = {"campana": lambda: nombres.nombre_campana(c[0], c[1], c[2], c[3], c[4]), "conjunto": lambda: nombres.nombre_conjunto(c[0], c[1], c[2]),
                  "anuncio": lambda: nombres.nombre_anuncio(c[0], c[1], c[2], int(c[3])), "url": lambda: nombres.url_anuncio(c[0], c[1]),
                  "resolver": lambda: nombres.resolver_url(c[0], campaign_name=c[1], campaign_id=c[2], adset_name=c[3], adset_id=c[4], ad_name=c[5], ad_id=c[6])}
            print(json.dumps({"resultado": fn[args.tipo]()}, ensure_ascii=False))
            return 0
        if args.cmd == "sellar":
            ruta = Path(args.campana)
            camp = _leer(ruta)
            camp["hash_config"] = V.hash_objeto(camp, ("hash_config",))
            comun.escribir_atomico(ruta, (json.dumps(camp, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
            print(json.dumps({"hash_config": camp["hash_config"]}))
            return 0
        if args.cmd == "validar":
            errs = V.errores_de_esquema(args.esquema, _leer(Path(args.archivo)))
            floats = V.buscar_floats(_leer(Path(args.archivo)))
            for e in errs[:10]:
                print(f"ESQUEMA {V.ruta_json(e)}: {e.message[:200]}")
            for r in floats[:5]:
                print(f"FLOAT {r}")
            return 3 if (errs or floats) else 0
        if args.cmd == "lint":
            d = Path(args.dir)
            lim, par = _cargar_limites_parametros(args)
            terminos = None
            ruta_t = Path(args.terminos) if args.terminos else None
            if ruta_t and ruta_t.is_file():
                datos = _leer(ruta_t)
                terminos = list(datos["terminos"] if isinstance(datos, dict) else datos)
            hallazgos = lint(d, lim, par, terminos)
            print(json.dumps({"hallazgos": hallazgos, "bloquea": any(x["severidad"] in BLOQUEA for x in hallazgos)}, indent=2, ensure_ascii=False))
            if any(x["codigo"] in ("limite_ausente", "parametro_ausente") for x in hallazgos):
                return 5
            return 4 if any(x["severidad"] in BLOQUEA for x in hallazgos) else 0
        return preflight_cmd(args)

    return comun.ejecutar_cli(cuerpo)


if __name__ == "__main__":
    sys.exit(main())
