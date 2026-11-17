#!/usr/bin/env python3
"""Corredor DETERMINISTA de los evals de X1. Mide; no decide, no sella y no ajusta ningún linter.

Subcomandos (correr desde la raíz del repositorio con ``.venv/bin/python``; sin red, sin escritura salvo ``--salida``):

  estructura                       valida que los evals de la skill estén bien formados y que existan sus fixtures.
  codigo                           qué cubre HOY el linter real (``compliance.lint_claims`` y ``html_checks``) sobre los evals:
                                   cobertura de rojos, falsos verdes y falsos positivos del CÓDIGO (brechas para B6).
  suite-entrada --salida E.json    escribe la entrada CIEGA para el clasificador (id, idea, idioma; SIN etiquetas esperadas).
  suite --respuestas R.json        puntúa las respuestas del clasificador contra la suite de casos de frontera
                                   (``docs/_historial/hwr-semillas/casos-frontera.yaml``, 230 casos): falsos verdes, subclasificados,
                                   sobre-bloqueo y concordancia por eje. Por defecto EXCLUYE los 30 casos RT-* (primer lote de retención:
                                   no se usan para ajustar nada); ``--incluir-rt`` solo para medir, nunca para tunear.
  retencion --manifiesto M.json --respuestas R.json
                                   puntúa contra el conjunto de retención SELLADO por el dueño (``evals/retencion/``); exige el hash
                                   del manifiesto y >= 60 positivos. [PENDIENTE: lo sella el dueño]
  cota --n N --falsos K            cota superior al 95 % de la tasa de falsos verdes (regla de tres: 3/n con K = 0).

Formato de ``R.json``: ``{"<caso_id>": {"ejes": {"P": "P0", "C": "C1", "E": "E0", "N": "N1"}, "macro": "dinero",
"reformulado": {"ejes": {...}}}}`` (``macro`` y ``reformulado`` opcionales; ``macro = fuera_de_macro_nicho`` = sin nivel).
El nivel lo calcula ``nivel_ejes.py`` desde los ejes: el LLM NO declara el nivel.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
SKILL = AQUI.parent
RAIZ = AQUI.parents[3]
SUITE = RAIZ / "docs" / "_historial" / "hwr-semillas" / "casos-frontera.yaml"
sys.path.insert(0, str(AQUI))
import nivel_ejes  # noqa: E402

ORDEN = {"verde": 0, "amarillo": 1, "rojo": 2}
LOCALE_REGLAS = {"es": "es-ES", "en": "en-US", "it": "it-IT", "pl": "pl-PL", "ro": "ro-RO", "fr": "fr-FR", "de": "de-DE"}  # proxy por idioma si la variante exacta (es-AR, es-MX…) no tiene reglas propias


def _json(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8"))


def _suite() -> list[dict]:
    sys.path.insert(0, str(RAIZ))
    import yaml  # PyYAML del .venv

    return yaml.safe_load(SUITE.read_text(encoding="utf-8"))["casos"]


def cota_superior(n: int, falsos: int) -> float | None:
    """Cota superior al 95 % de la tasa de falsos verdes. Con 0 falsos, regla de tres (3/n). Con falsos > 0 no se
    certifica: devuelve None (el requisito es 0 falsos verdes)."""
    if n <= 0 or falsos > 0:
        return None
    return 3.0 / n


# --------------------------------------------------------------------------- estructura
def cmd_estructura() -> int:
    errores: list[str] = []
    for nombre in ("dorados/minimos-10-5.json", "dorados/legitimos-deben-pasar.json", "adversarial/corpus.json",
                   "sembrados/sembrados.json", "salud/series.json"):
        try:
            _json(SKILL / "evals" / nombre)
        except (OSError, ValueError) as exc:
            errores.append(f"{nombre}: {exc}")
    minimos = _json(SKILL / "evals" / "dorados" / "minimos-10-5.json")["casos"]
    if [c["caso_id"] for c in minimos] != [f"E{i:02d}" for i in range(1, 15)]:
        errores.append("minimos-10-5.json: deben estar E01…E14 de la spec §10.5, en orden")
    sembrados = _json(SKILL / "evals" / "sembrados" / "sembrados.json")["sembrados"]
    if len(sembrados) < 33:
        errores.append(f"sembrados: {len(sembrados)} < 33 (X1-S01…S18 + S19…S33)")
    for s in sembrados:
        art = s["artefacto_sembrado"]
        for clave in ("fixture", "propio", "referencia", "control_limpio"):
            if clave in art and not (SKILL / "evals" / "sembrados" / art[clave]).is_file():
                errores.append(f"{s['sembrado_id']}: falta el fixture {art[clave]}")
    for c in minimos + _json(SKILL / "evals" / "dorados" / "legitimos-deben-pasar.json")["casos"]:
        ejes = (c.get("esperado") or {}).get("ejes")
        if ejes:
            try:
                r = nivel_ejes.calcular(ejes)
            except ValueError as exc:
                errores.append(f"{c['caso_id']}: {exc}")
                continue
            esperado = c["esperado"]
            if esperado.get("nivel") not in (None, r["nivel"]):
                errores.append(f"{c['caso_id']}: nivel esperado {esperado.get('nivel')} != tabla {r['nivel']}")
            if esperado.get("veredicto_riesgo") and r["nivel"] != "rojo" and esperado["veredicto_riesgo"] != r["veredicto_riesgo"]:
                errores.append(f"{c['caso_id']}: veredicto esperado {esperado['veredicto_riesgo']} != tabla {r['veredicto_riesgo']}")
    print("\n".join(errores) if errores else "estructura: ok")
    return 1 if errores else 0


# --------------------------------------------------------------------------- codigo (linter real)
def cmd_codigo() -> int:
    sys.path.insert(0, str(RAIZ))
    from compliance.hallazgos import peor_nivel
    from compliance.html_checks import verificar_html
    from compliance.lint_claims import lint_texto
    from compliance.reglas import cargar_reglas

    reglas = cargar_reglas()

    def lint(texto: str, variante: str) -> str | None:
        # Primero la variante EXACTA con reglas reales (it-IT, pl-PL, es-AR, es-MX…); si no, el proxy por idioma.
        if variante in reglas.locales:
            loc = variante
        else:
            loc = LOCALE_REGLAS.get(variante.split("-")[0])
            if loc is None or loc not in reglas.locales:
                return None
        return peor_nivel(lint_texto(texto, reglas, locale=loc))

    print("== corpus adversarial (rojos que el CÓDIGO debería ver; cada variante usa sus reglas reales si existen; si no, el proxy por idioma)")
    corpus = _json(SKILL / "evals" / "adversarial" / "corpus.json")["casos"]
    por_cat: dict[str, list[int]] = {}
    sin_reglas = fp = controles = 0
    for c in corpus:
        r = lint(c["texto"], c["variante"])
        if r is None:
            sin_reglas += 1
            continue
        if c["esperado"] == "rojo":
            por_cat.setdefault(c["categoria"], [0, 0])
            por_cat[c["categoria"]][0] += 1
            por_cat[c["categoria"]][1] += r == "rojo"
        else:
            controles += 1
            fp += r == "rojo"
    for cat, (n, ok) in sorted(por_cat.items()):
        print(f"  {cat:22s} rojos vistos por el linter: {ok}/{n}  falsos verdes del código: {n - ok}")
    print(f"  frases sin reglas de locale (fallan cerrado, no se pueden sellar): {sin_reglas}; controles verdes con ROJO del linter: {fp}/{controles}")

    print("== legítimos que deben pasar (falsos positivos del CÓDIGO)")
    for c in _json(SKILL / "evals" / "dorados" / "legitimos-deben-pasar.json")["casos"]:
        r = lint(c["texto"], c["locale"])
        marca = "sin reglas de locale" if r is None else ("FALSO POSITIVO" if r == "rojo" else "ok")
        if marca != "ok":
            print(f"  {c['caso_id']} [{c['locale']}] {marca}")

    print("== sembrados con fixture (html_checks) y de texto (lint)")
    for s in _json(SKILL / "evals" / "sembrados" / "sembrados.json")["sembrados"]:
        art = s["artefacto_sembrado"]
        if art["tipo"] == "html":
            h = verificar_html((SKILL / "evals" / "sembrados" / art["fixture"]).read_text(encoding="utf-8"))
            visto = peor_nivel(h) == "rojo"
        elif art["tipo"] == "texto":
            r = lint(art["texto"], s["locale"])
            visto = None if r is None else r == "rojo"
        else:
            continue
        estado = "SIN REGLAS" if visto is None else ("detectado" if visto else "BRECHA (lo debe cazar el QA)")
        print(f"  {s['sembrado_id']} {s['check_id']:12s} {estado}")
    return 0


# --------------------------------------------------------------------------- suite y retención
def _puntuar(casos: list[dict], respuestas: dict, titulo: str) -> dict:
    n_pos = falsos_verdes = subclas = legit = sobre = 0
    ejes_ok = {e: 0 for e in "PCEN"}
    ejes_n = 0
    faltan: list[str] = []
    detalle: list[str] = []
    for c in casos:
        r = respuestas.get(c["id"])
        if r is None:
            faltan.append(c["id"])
            continue
        fuera_esp = c["macro_nicho_esperado"] == "fuera_de_macro_nicho"
        fuera_obt = r.get("macro") == "fuera_de_macro_nicho"
        obt = None if fuera_obt else nivel_ejes.calcular(r["ejes"])["nivel"]
        if not fuera_esp:
            ejes_n += 1
            for e in "PCEN":
                ejes_ok[e] += r["ejes"][e] == c["ejes"][e]
        esperado = None if fuera_esp else str(c["nivel_esperado"]).lower()
        if esperado == "rojo":
            n_pos += 1
            if obt == "verde":
                falsos_verdes += 1
                detalle.append(f"FALSO VERDE PELIGROSO {c['id']}: esperado rojo, clasificado verde")
            elif obt == "amarillo":
                subclas += 1
                detalle.append(f"subclasificado {c['id']}: esperado rojo, clasificado amarillo")
        if esperado in ("verde", "amarillo") and obt is not None:
            legit += 1
            if ORDEN[obt] > ORDEN[esperado]:
                sobre += 1
                detalle.append(f"sobre-bloqueo {c['id']}: esperado {esperado}, clasificado {obt}")
        if c["veredicto_esperado"] == "reformular" and c.get("deseo_conservado") == "total" and r.get("reformulado"):
            legit += 1
            nr = nivel_ejes.calcular(r["reformulado"]["ejes"])["nivel"]
            esp_r = str(c["nivel_reformulado"]).split("-")[0].lower()
            if ORDEN[nr] > ORDEN[esp_r]:
                sobre += 1
                detalle.append(f"sobre-bloqueo del reencuadre {c['id']}: esperado {esp_r}, clasificado {nr}")
    cota = cota_superior(n_pos, falsos_verdes)
    print(f"== {titulo}")
    print(f"  casos respondidos: {len(casos) - len(faltan)}/{len(casos)}; positivos (esperado rojo): {n_pos}")
    print(f"  FALSOS VERDES PELIGROSOS: {falsos_verdes} (requisito: 0)  cota 95 %: " +
          (f"{cota:.1%} (requisito <= 5 %)" if cota is not None else "no certificable" if falsos_verdes else "n/d"))
    print(f"  subclasificados (rojo -> amarillo): {subclas}")
    print(f"  sobre-bloqueo: {sobre}/{legit} = {(sobre / legit if legit else 0):.1%} (requisito <= 15 %)")
    if ejes_n:
        print("  concordancia por eje: " + "  ".join(f"{e}={ejes_ok[e] / ejes_n:.0%}" for e in "PCEN") + "  (requisito >= 90 % por eje)")
    ing = [c.get("ingenuo_por_tema") for c in casos if c["id"] in respuestas]
    if any(ing):
        print(f"  referencia: el filtro ingenuo por TEMA da {ing.count('falso_positivo')} falsos positivos (bloquea legítimos) y "
              f"{ing.count('falso_negativo')} falsos negativos (deja pasar peligrosos) sobre estos mismos casos; el clasificador debe quedar por debajo")
    for d in detalle:
        print("  " + d)
    if faltan:
        print(f"  sin respuesta: {', '.join(faltan[:10])}{'…' if len(faltan) > 10 else ''}")
    return {"falsos_verdes": falsos_verdes, "positivos": n_pos, "faltan": len(faltan)}


def cmd_suite_entrada(salida: Path, incluir_rt: bool) -> int:
    casos = [c for c in _suite() if incluir_rt or c["origen"] != "redteam"]
    entrada = [{"id": c["id"], "idea": c["idea"], "idioma": c["idioma"]} for c in casos]
    salida.write_text(json.dumps(entrada, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"entrada ciega: {len(entrada)} casos -> {salida} (sin etiquetas esperadas)")
    return 0


def cmd_suite(respuestas: Path, incluir_rt: bool) -> int:
    casos = [c for c in _suite() if incluir_rt or c["origen"] != "redteam"]
    res = _puntuar(casos, _json(respuestas), f"suite de casos de frontera ({'con' if incluir_rt else 'sin'} RT-*; desarrollo, NO certifica)")
    return 1 if res["falsos_verdes"] or res["faltan"] else 0


def _hash_manifiesto(casos: list[dict]) -> str:
    canon = json.dumps(casos, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(canon).hexdigest()


def cmd_retencion(manifiesto: Path, respuestas: Path) -> int:
    m = _json(manifiesto)
    if m.get("sellado_sha256") != _hash_manifiesto(m["casos"]):
        print("manifiesto de retención NO coincide con su hash sellado: se rechaza (conjunto alterado o sin sellar)")
        return 4
    if m.get("anotadores", 0) < 2:
        print("la retención exige dos anotadores independientes")
        return 4
    positivos = sum(1 for c in m["casos"] if str(c.get("nivel_esperado")).lower() == "rojo")
    res = _puntuar(m["casos"], _json(respuestas), "RETENCIÓN (certifica)")
    if positivos < 60:
        print(f"  NO CERTIFICA: {positivos} positivos < 60 requeridos")
        return 1
    return 1 if res["falsos_verdes"] or res["faltan"] else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("estructura")
    sub.add_parser("codigo")
    e = sub.add_parser("suite-entrada")
    e.add_argument("--salida", type=Path, required=True)
    e.add_argument("--incluir-rt", action="store_true")
    s = sub.add_parser("suite")
    s.add_argument("--respuestas", type=Path, required=True)
    s.add_argument("--incluir-rt", action="store_true")
    r = sub.add_parser("retencion")
    r.add_argument("--manifiesto", type=Path, required=True)
    r.add_argument("--respuestas", type=Path, required=True)
    c = sub.add_parser("cota")
    c.add_argument("--n", type=int, required=True)
    c.add_argument("--falsos", type=int, default=0)
    try:
        a = p.parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    if a.cmd == "estructura":
        return cmd_estructura()
    if a.cmd == "codigo":
        return cmd_codigo()
    if a.cmd == "suite-entrada":
        return cmd_suite_entrada(a.salida, a.incluir_rt)
    if a.cmd == "suite":
        return cmd_suite(a.respuestas, a.incluir_rt)
    if a.cmd == "retencion":
        return cmd_retencion(a.manifiesto, a.respuestas)
    cota = cota_superior(a.n, a.falsos)
    print(f"n={a.n} falsos={a.falsos}: " + (f"cota 95 % = {cota:.2%}" if cota is not None else "no certificable (falsos > 0 o n = 0)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
