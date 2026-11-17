#!/usr/bin/env python3
"""Paso 0 de D5: prechequeo determinista de entradas y precondiciones. Sin red; solo lectura.

Uso (desde la raíz del repositorio, con `.venv/bin/python` para poder leer los YAML de empresa/):
    python3 prechequeo.py --oferta-dir ofertas/OF-202611-01 [--empresa-dir empresa] \
        [--datos-legales RUTA.json] [--ayuda-por-pais RUTA.json] [--alta-oferta ofertas/<id>/infra/alta.json] [--json]

`--alta-oferta` recibe el DATO del alta de oferta (`ofertas/<id>/infra/alta.json`, que escribe `infra.alta_oferta`), no la lista de
pasos `infra/plantillas/alta-oferta.yaml`. El nombre de la bandera se conserva por la lista blanca de `agentes/hooks/herramientas.yaml`;
sin ella, el script lee `<oferta-dir>/infra/alta.json` si existe.

Escribe en stdout el contenido de `prechequeo.json` (el Maker lo guarda en 05-landing/). Resultado:
  ok          todo lo exigido está; el Maker continúa con el paso 1
  preguntas   no hay bloqueo duro, pero falta un dato que solo da el dueño (pregunta bloqueante): el Maker se detiene y pregunta
  bloqueado   una precondición falla (riesgo rojo, promesa sin entregable, mercado incoherente...): no se construye nada
Código de salida: 0 ok · 4 preguntas o bloqueado · 2 uso. Los avisos no bloquean.
Códigos P-xx: references/proceso-landing.md §0. Parámetros leídos (solo lectura): `empresa/limites.yaml`, `empresa/parametros.yaml`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:  # los YAML de empresa/ solo se leen si PyYAML está disponible (.venv del repositorio)
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None


def _json(p: Path) -> Any:
    return json.loads(p.read_text(encoding="utf-8"))


def _yaml(p: Path) -> Any:
    if yaml is None or not p.is_file():
        return None
    return yaml.safe_load(p.read_text(encoding="utf-8"))


# Pasos de infra/alta.json de los que D5 toma sus IDs (dominio, dataset/píxel, Product/Price de prueba, correo de envío); forma real LT-36.
PASOS_ALTA_D5 = ("meta-dataset", "meta-dominio-verificado", "stripe-catalogo-prueba", "correo-envio")


def prechequeo(dir_oferta: Path, dir_empresa: Path, datos_legales: dict | None = None, ayuda: dict | None = None,
               alta: dict | None = None) -> dict[str, Any]:
    if alta is None and (dir_oferta / "infra" / "alta.json").is_file():
        alta = _json(dir_oferta / "infra" / "alta.json")
    bloqueos: list[dict[str, str]] = []
    preguntas: list[dict[str, str]] = []
    avisos: list[dict[str, str]] = []
    entradas: dict[str, str] = {}

    def bloquea(codigo: str, motivo: str, fuente: str) -> None:
        bloqueos.append({"codigo": codigo, "motivo": motivo, "fuente": fuente})

    def pregunta(codigo: str, texto: str, por_que: str) -> None:
        preguntas.append({"codigo": codigo, "pregunta": texto, "por_que": por_que})

    def aviso(codigo: str, texto: str) -> None:
        avisos.append({"codigo": codigo, "aviso": texto})

    rutas = {
        "oferta": dir_oferta / "03-oferta" / "oferta.json",
        "producto": dir_oferta / "04-producto" / "producto.json",
        "mercado": dir_oferta / "mercado.json",
        "validacion": dir_oferta / "02-validacion" / "validacion.json",
    }
    datos: dict[str, Any] = {}
    for nombre, p in rutas.items():
        if not p.is_file():
            bloquea("P-01", f"falta {p.relative_to(dir_oferta)}", str(p))
            continue
        try:
            datos[nombre] = _json(p)
            entradas[str(p.relative_to(dir_oferta))] = "sha256_bytes:" + hashlib.sha256(p.read_bytes()).hexdigest()
        except ValueError as exc:
            bloquea("P-01", f"{p.name} no es JSON válido: {exc}", str(p))
    if not (dir_oferta / "00-brief.yaml").is_file():
        aviso("P-01b", "no existe 00-brief.yaml (O0): sin brief firmado no hay nivel ni mercado objetivo")
    if bloqueos:
        return _salida(dir_oferta, bloqueos, preguntas, avisos, entradas)

    oferta, producto, mercado, validacion = datos["oferta"], datos["producto"], datos["mercado"], datos["validacion"]
    limites = _yaml(dir_empresa / "limites.yaml") or {}
    parametros = (_yaml(dir_empresa / "parametros.yaml") or {}).get("grupos", {}) if yaml else {}

    # P-02 riesgo
    riesgo = oferta.get("riesgo") or {}
    nivel = riesgo.get("nivel")
    # Colores por eje: `riesgo.colores` (salida de scripts.nivel_riesgo) o, en ofertas anteriores, P/C/E/N como color. `subnivel` manda si existe;
    # si no, 2 o más ejes amarillos = B [SUPUESTO] (la aritmética es de `python -m scripts.nivel_riesgo`, no de este script).
    colores = riesgo.get("colores") or {e: riesgo.get(e) for e in ("P", "C", "E", "N")}
    ejes = [colores.get(e) for e in ("P", "C", "E", "N")]
    subnivel = riesgo.get("subnivel") or ("B" if sum(1 for e in ejes if e == "amarillo") >= 2 else "A")
    if nivel == "rojo" or "rojo" in ejes:
        bloquea("P-02", "oferta.riesgo.nivel = rojo (o un eje rojo): un candidato ROJO no se lanza; vuelve a D3 con el reencuadre", "03-oferta/oferta.json#riesgo")
    elif nivel == "amarillo" and subnivel == "B" and not oferta.get("aprobada_por_dueno"):
        bloquea("P-02", "amarillo subnivel B (dos ejes amarillos) sin decisión H del dueño (aprobada_por_dueno)", "03-oferta/oferta.json#aprobada_por_dueno")
    elif nivel not in ("verde", "amarillo"):
        bloquea("P-02", f"riesgo.nivel ausente o desconocido ({nivel!r})", "03-oferta/oferta.json#riesgo")

    # P-03 etapas aprobadas (si hay estado.json)
    estado_p = dir_oferta / "estado.json"
    if estado_p.is_file():
        etapas = (_json(estado_p).get("etapas") or {})
        for e in ("D3", "D4"):
            st = (etapas.get(e) or {}).get("estado")
            if st != "aprobado":
                bloquea("P-03", f"la etapa {e} no está aprobada en estado.json (estado={st!r})", "estado.json")
            elif (etapas.get(e) or {}).get("obsoleta"):
                bloquea("P-03", f"la etapa {e} está obsoleta (una entrada cambió)", "estado.json")
    else:
        aviso("P-03", "no hay estado.json: no se pudo comprobar que D3 y D4 estén aprobadas")

    # P-04 promesas sin entregable
    for m in producto.get("matriz_promesas", []):
        if m.get("estado") != "cumplida":
            bloquea("P-04", f"promesa «{m.get('promesa_id')}» con estado {m.get('estado')!r}: no se puede afirmar en la landing", "04-producto/producto.json#matriz_promesas")
    textos_matriz = {m.get("texto") for m in producto.get("matriz_promesas", [])}
    cubiertos = {m.get("promesa_id") for m in producto.get("matriz_promesas", [])}
    for c in (oferta.get("promesa") or {}).get("claims_permitidos", []):
        de_producto = str(c.get("evidencia_ref", "")).startswith("04-producto/")
        if de_producto and c["claim_id"] not in cubiertos and c.get("texto") not in textos_matriz:
            aviso("P-04b", f"claim «{c['claim_id']}» sin fila en matriz_promesas (ni por id ni por texto): revisar la traza antes de usarlo")
        elif de_producto and c["claim_id"] not in cubiertos:
            aviso("P-04c", f"claim «{c['claim_id']}» coincide con matriz_promesas por texto pero no por id (D3 y D4 usan ids distintos): PEDIDO a D4")

    # P-05 dolor / objeciones
    objeciones = (validacion.get("handoff_d3") or {}).get("objeciones_top") or (oferta.get("avatar") or {}).get("objeciones")
    if not objeciones:
        bloquea("P-05", "sin objeciones_top ni avatar.objeciones: no hay investigación de dolor para S03 y S12 (no se omite: bloquea)", "02-validacion/validacion.json#handoff_d3")
    if not (oferta.get("avatar") or {}).get("vocabulario"):
        aviso("P-05b", "avatar.vocabulario vacío: el copy no tendrá lenguaje del cliente")

    # P-06 mercado
    if mercado.get("locale") != oferta.get("locale"):
        bloquea("P-06", f"locale distinto: mercado={mercado.get('locale')!r}, oferta={oferta.get('locale')!r}", "mercado.json")
    if mercado.get("moneda_cobro") != oferta.get("moneda"):
        bloquea("P-06", f"moneda distinta: mercado.moneda_cobro={mercado.get('moneda_cobro')!r}, oferta={oferta.get('moneda')!r}", "mercado.json")
    fiscal = mercado.get("fiscal") or {}
    if fiscal.get("regimen") == "diferido" and not fiscal.get("exposicion_aceptada"):
        bloquea("P-06", "régimen fiscal diferido sin exposicion_aceptada firmada por el dueño (X32_FISCAL)", "mercado.json#fiscal")
    rev = mercado.get("revision_linguistica") or {}
    if rev.get("obligacion_legal_idioma") and not rev.get("revisor_nativo"):
        # J11 (2026-11-06, el dueño): el revisor nativo humano ya no es requisito, bloqueo ni gate. La obligación legal de escribir en el idioma local se cumple
        # escribiendo en él; la calidad se asegura con la inmersión del mercado (J12), retraducción por otro modelo y segunda lectura de IA.
        aviso("P-06c", "idioma con obligación legal de documentación local y sin revisor nativo: NO bloquea (J11). Escribe en el locale con el glosario de M1 y deja "
                       "retraducción y segunda lectura de IA anotadas en `brief.md` (`tono.nota`); el revisor humano es opcional")
    if not mercado.get("glosario_ref"):
        aviso("P-06b", "sin glosario_ref: se usa el tono por defecto del locale y se marca [SUPUESTO]; retraducción y segunda lectura")

    # P-07 coherencia con límites (solo lectura; sin dato, no se compara)
    dias = (oferta.get("garantia") or {}).get("dias")
    minimo = limites.get("politica_reembolso_dias") if isinstance(limites, dict) else None
    if minimo is not None and dias is not None and dias < minimo:
        bloquea("P-07", f"garantía de {dias} días < limites.politica_reembolso_dias ({minimo})", "empresa/limites.yaml")
    if isinstance(limites, dict) and limites.get("precio_neto_minimo") is None:
        aviso("P-07b", "limites.precio_neto_minimo = null: C02 no puede comprobar el precio mínimo (nada gasta ni activa)")
    locales = limites.get("locales_permitidos") if isinstance(limites, dict) else None
    if locales and oferta.get("locale") not in locales:
        bloquea("P-07", f"locale {oferta.get('locale')!r} fuera de limites.locales_permitidos", "empresa/limites.yaml")
    elif not locales:
        aviso("P-07c", "limites.locales_permitidos vacío: D5 puede construir en preview, pero nada se lanza")

    # P-08 bump
    bump = oferta.get("bump")
    if bump:
        lista = oferta["precio"]["lista"]["monto"]
        pct = bump["precio"]["monto"] * 100 / lista
        g = parametros.get("landing", {}) if isinstance(parametros, dict) else {}
        lo = (g.get("bump_pct_precio_min") or {}).get("valor")
        hi = (g.get("bump_pct_precio_max") or {}).get("valor")
        if lo is not None and hi is not None and not (lo <= pct <= hi):
            aviso("P-08", f"el bump vale {pct:.0f} % del precio, fuera de landing.bump_pct_precio_min/max ({lo}-{hi})")
        ids = {i.get("id") for i in producto.get("items", [])}
        if bump.get("id") not in ids:
            aviso("P-08b", f"el bump «{bump.get('id')}» no tiene archivo en producto.items: no se puede ofrecer algo que D4 no produjo")
    if oferta.get("urgencia"):
        aviso("P-09", "oferta.urgencia no es null: solo se admite un cierre real con fecha vencida en servidor (X1-P05); si no, se omite")
    if not producto.get("ia_divulgacion"):
        aviso("P-10", "producto.ia_divulgacion vacío: S08 no podrá decir cómo está hecho el material")

    # Datos que solo da el dueño / X1 / D0
    claves_llc = ("razon_social", "direccion", "id_fiscal", "correo")
    if not datos_legales or any(not datos_legales.get(k) for k in claves_llc):
        faltan = [k for k in claves_llc if not (datos_legales or {}).get(k)]
        pregunta("Q-01", f"Datos legales públicos de la LLC que faltan: {', '.join(faltan)}", "/legal/vendedor y el pie los exigen (L-01); sin ellos no se generan las páginas legales")
    macro = oferta.get("macro_nicho")
    if (macro == "relaciones" or nivel == "amarillo") and not ayuda:
        pregunta("Q-02", f"ayuda_por_pais.yaml vigente para {', '.join(oferta.get('paises_segmentacion', []))} (macro {macro}, nivel {nivel})", "C15: aviso de seguridad y bloque «Si necesitas ayuda ahora»")
    if not alta:
        aviso("P-11", "sin ofertas/<id>/infra/alta.json (alta de oferta N01b: dominio, dataset/píxel, Product/Price de prueba): el Maker puede escribir copy, paleta y assets, pero no checkout.json ni tracking.json")
    elif "pasos" not in alta or (isinstance(alta.get("pasos"), list) and "completo" not in alta):
        aviso("P-11", "el archivo del alta no tiene la forma de infra/alta.json (completo, pasos[].estado): ¿es la plantilla infra/plantillas/alta-oferta.yaml?")
    else:
        por_id = {p.get("id"): p for p in alta.get("pasos") or [] if isinstance(p, dict)}
        sin_ok = [i for i in PASOS_ALTA_D5 if (por_id.get(i) or {}).get("estado") != "ok"]
        if sin_ok:
            aviso("P-11b", f"infra/alta.json: pasos sin estado ok ({', '.join(sin_ok)}); sin ellos no se cierran checkout.json ni tracking.json")
    return _salida(dir_oferta, bloqueos, preguntas, avisos, entradas)


def _salida(dir_oferta: Path, bloqueos: list, preguntas: list, avisos: list, entradas: dict) -> dict[str, Any]:
    resultado = "bloqueado" if bloqueos else ("preguntas" if preguntas else "ok")
    return {"oferta_id": dir_oferta.name, "resultado": resultado, "bloqueos": bloqueos, "preguntas": preguntas, "avisos": avisos, "entradas": entradas}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Prechequeo de D5 (paso 0).")
    ap.add_argument("--oferta-dir", required=True)
    ap.add_argument("--empresa-dir", default="empresa")
    ap.add_argument("--datos-legales")
    ap.add_argument("--ayuda-por-pais")
    ap.add_argument("--alta-oferta", help="ofertas/<id>/infra/alta.json (el dato del alta; no la plantilla alta-oferta.yaml)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    d = Path(a.oferta_dir)
    if not d.is_dir():
        print(f"no existe {d}", file=sys.stderr)
        return 2
    cargar = lambda p: (_yaml(Path(p)) if str(p).endswith((".yaml", ".yml")) else _json(Path(p))) if p else None  # noqa: E731
    try:
        res = prechequeo(d, Path(a.empresa_dir), cargar(a.datos_legales), cargar(a.ayuda_por_pais), cargar(a.alta_oferta))
    except (OSError, ValueError, KeyError) as exc:
        print(f"entrada ilegible: {exc}", file=sys.stderr)
        return 2
    if a.json:
        print(json.dumps(res, ensure_ascii=False, sort_keys=True))
    else:
        print(f"resultado: {res['resultado']}")
        for k in ("bloqueos", "preguntas", "avisos"):
            for x in res[k]:
                print(f"  {k[:-1].upper():<8} {x.get('codigo')}: {x.get('motivo') or x.get('pregunta') or x.get('aviso')}")
    return 0 if res["resultado"] == "ok" else 4


if __name__ == "__main__":
    sys.exit(main())
