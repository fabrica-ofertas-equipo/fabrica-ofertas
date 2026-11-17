"""Ordena los candidatos a modelar combinando complejidad del funnel, antigüedad y anuncios encendidos, y premia variar.

Uso (desde la raíz del repositorio):
  python3 .claude/skills/modelar-y-lanzar-oferta/scripts/ordenar_candidatos.py CANDIDATOS.json [--historial ofertas/historial-modelado.json] [--json]

CANDIDATOS.json: lista de objetos
  {"pagina": "...", "page_id": "...", "pais": "IT", "anuncios": 62, "dias": 41,
   "funnel": "quiz+vsl", "extras": ["bump", "upsell", "niveles"], "tema": "...", "producible": true}

`funnel` es un tipo de la taxonomía (`scripts/taxonomia_funnels.json`, explicada en `references/taxonomia-funnels.md`):
un componente de núcleo (`quiz`, `tsl`, `vsl`…) o varios en orden unidos con «+» (`quiz+vsl`, `advertorial+tsl`).
También vale dar `"componentes": ["quiz", "vsl", "bump"]` en lugar de `funnel`. Los nombres anteriores siguen
funcionando: `tsl-basica` (= `tsl`), `tsl-video` (= `tsl` con el extra `video-apoyo`) y `varios-pasos`.
Un nombre compuesto que todavía no existe como tipo se acepta, se puntúa por sus componentes y sale marcado
«tipo nuevo, a confirmar por el dueño» (se registra con `barrido_por_forma.py encuadrar --registrar`).
`anuncios` y `dias` son los de ESA oferta, medidos sobre anuncios activos.
Opcionales (señales de joya, 2026-11-13): `"hueco": 0-1` (1 = validada en pocos países; lo da el radar) y
`"escalando": true` (el banco la ve subir tres días seguidos). Suben el puntaje hasta un 10 % cada una, sin tocar los pesos.

Veto por países del referente (2026-11-14, tras Oferta D: se lanzó en México con el original pautando ahí 127-170
anuncios, porque el referente corría en los 57 países y no había ningún mercado libre). Campo `referente_paises`:
la medición de `buscar-ofertas/scripts/paises_referente.py` ({"paises": {"US": 147, ...}, "sin_anuncios": [...]}).
Con ella, si el referente corre en TODOS los países donde podemos lanzar (los de `elegir_mercado.py`), el candidato
queda fuera: no hay mercado libre. Si quedan menos de 3 libres, se avisa. Sin medición, el candidato sigue en la
tabla con la nota «medir países del referente» y NO se toma hasta medirlo (el primero se mide antes de elegirlo).

Historial: lista de ofertas ya lanzadas, la más reciente al final: {"fecha", "oferta", "funnel", "tema", "pais_destino"}.

Regla del dueño (2026-11-11): apuntar a funnels complejos, con peso para los anuncios encendidos y, sobre todo, la antigüedad,
e ir variando de tipo para probar cosas distintas en vez de hacer siempre el mismo. Los pesos de abajo son la lectura del
asistente de esa regla; se cambian aquí, en un solo sitio. La complejidad ya no es un valor fijo por nombre: sale de los
componentes (regla en la taxonomía). Sin red y sin efectos: solo lee y calcula.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import taxonomia_funnels as tx  # noqa: E402


def _paises_lanzables() -> list[str]:
    try:
        import elegir_mercado as em  # noqa: E402
        bloq = em.bloqueados_por_meta()   # 14-nov: SG/TW/TH/MY/AU/IN sin anunciante verificado no son lanzables
        return [f[0] for f in em.PAISES if f[0] not in bloq]
    except Exception:
        return []


LANZABLES = _paises_lanzables()
POCOS_LIBRES = 3                              # menos de esto: aviso (poco lugar; un rival que exporta lo cierra)

# ── Parámetros (un solo sitio) ─────────────────────────────────────────────
PISO_ANUNCIOS, PISO_DIAS = 15, 10            # por debajo no se modela
TOPE_ANUNCIOS, TOPE_DIAS = 100, 90           # a partir de aquí la señal ya no suma más
PESOS = {"complejidad": 0.40, "antiguedad": 0.35, "anuncios": 0.25}
# La complejidad de cada funnel sale de taxonomia_funnels.json: pesos por componente y regla de combinación.
REPITE_ULTIMO = 0.85                          # mismo tipo de funnel que la última oferta lanzada
REPITE_DOS = 0.70                             # mismo tipo que las dos últimas
REPITE_TEMA = 0.90                            # mismo tema que alguna de las tres últimas
# Señales de joya (dueño, 2026-11-13: «super buscador»). No cambian los pesos de arriba: suben el puntaje un poco.
JOYA_HUECO_MAX = 0.10          # hasta +10 % según el hueco de mercado (1 = validada en pocos países: mucho lugar para modelar)
JOYA_ESCALANDO = 0.10          # +10 % si el banco la marca «ESCALANDO» (tres días seguidos de suba)
EMPATE = 0.05                                 # diferencia de puntaje que se considera empate técnico
UMBRAL_COMPLEJO = 0.60                        # a partir de aquí el funnel cuenta como «complejo» (§1.5: hacen falta 3)


def _escala(valor: float, piso: float, tope: float) -> float:
    """0 en el piso, 1 en el tope, logarítmica: pasar de 15 a 30 pesa más que de 85 a 100."""
    if valor <= piso:
        return 0.0
    return min(1.0, math.log(valor / piso) / math.log(tope / piso))


def puntuar(c: dict, historial: list[dict], tax: dict | None = None) -> dict:
    tax = tax or tx.cargar()
    try:
        r = tx.resolver(tax, c.get("funnel"), c.get("componentes"), c.get("extras"))
    except tx.ErrorTaxonomia as e:
        raise SystemExit(f"{c.get('pagina')}: {e}")
    tipo = r["tipo"]
    comp = tx.complejidad(tax, r["nucleo"], r["extras"], r["piso_complejidad"])
    anti = _escala(float(c["dias"]), PISO_DIAS, TOPE_DIAS)
    anun = _escala(float(c["anuncios"]), PISO_ANUNCIOS, TOPE_ANUNCIOS)
    base = PESOS["complejidad"] * comp + PESOS["antiguedad"] * anti + PESOS["anuncios"] * anun
    # Variación: se compara el tipo canónico (el núcleo en orden), así `tsl-video` y `tsl-basica` son el mismo tipo
    # y `quiz+vsl` solo repite a otro `quiz+vsl`.
    ultimos = [tx.tipo_canonico(tax, h.get("funnel")) for h in historial][-2:]
    factor, notas = 1.0, []
    if len(ultimos) == 2 and ultimos[0] == ultimos[1] == tipo:
        factor *= REPITE_DOS
        notas.append("mismo tipo que las dos últimas")
    elif ultimos and ultimos[-1] == tipo:
        factor *= REPITE_ULTIMO
        notas.append("mismo tipo que la última")
    if c.get("tema") and c["tema"] in [h.get("tema") for h in historial][-3:]:
        factor *= REPITE_TEMA
        notas.append("tema ya probado hace poco")
    hueco = c.get("hueco")
    if isinstance(hueco, (int, float)) and hueco > 0:
        factor *= 1 + JOYA_HUECO_MAX * min(1.0, float(hueco))
        notas.append(f"hueco de mercado {hueco:.2f}")
    if c.get("escalando"):
        factor *= 1 + JOYA_ESCALANDO
        notas.append("escalando")
    if r["estado"] in ("sin-registrar", "nuevo-a-confirmar"):
        notas.append("tipo nuevo, a confirmar por el dueño")
    if tipo == tx.SIN_CLASIFICAR:
        notas.append("funnel sin clasificar")
    pasa = c["anuncios"] >= PISO_ANUNCIOS and c["dias"] >= PISO_DIAS
    if not pasa:
        notas.append("no pasa el piso")
    if c.get("producible") is False:
        notas.append("no producible con este recorrido")
    libres, parcial = _libres(c)
    sin_mercado, a_medir = False, False
    if libres is None:
        a_medir = True
        notas.append("medir países del referente antes de tomarla")
    elif not libres and not parcial:
        sin_mercado = True
        notas.append(f"VETO: el referente corre en los {len(LANZABLES)} países de nuestra lista (elegir_mercado.PAISES)")
    elif not libres:
        a_medir = True
        notas.append("el referente corre en todos los países mirados: medir el resto antes de tomarla")
    elif parcial:
        notas.append(f"libres (medición parcial): {', '.join(libres)}")
    elif len(libres) < POCOS_LIBRES:
        notas.append(f"solo {len(libres)} país(es) libre(s): {', '.join(libres)}")
    return {**c, "funnel": r["escrito_como"], "tipo": tipo, "nucleo": r["nucleo"], "extras": r["extras"],
            "estado_tipo": r["estado"], "complejidad": round(comp, 2), "complejo": comp >= UMBRAL_COMPLEJO,
            "antiguedad": round(anti, 2), "senal_anuncios": round(anun, 2),
            "base": round(base, 3), "factor_variacion": round(factor, 2), "puntaje": round(base * factor, 3),
            "pasa_piso": pasa, "notas": notas, "paises_libres": libres, "sin_mercado": sin_mercado, "medir_paises": a_medir}


def _libres(c: dict) -> tuple[list[str] | None, bool]:
    """(países lanzables con 0 anuncios activos del referente, ¿medición parcial?); (None, False) si no se midió."""
    m = c.get("referente_paises")
    if not isinstance(m, dict) or not (m.get("paises") or m.get("sin_anuncios")):
        return None, False
    con = {str(k).upper() for k, v in (m.get("paises") or {}).items() if isinstance(v, (int, float)) and v > 0}
    sin = {str(k).upper() for k, v in (m.get("paises") or {}).items() if v == 0} | {str(x).upper() for x in m.get("sin_anuncios") or []}
    base = LANZABLES or sorted(con | sin)
    return [x for x in base if x in sin], any(x not in con | sin for x in base)


def ordenar(candidatos: list[dict], historial: list[dict], tax: dict | None = None) -> dict:
    """Devuelve {"elegibles", "fuera", "historial", "complejos_que_pasan", "tipos_nuevos"}; lo usa también barrido_por_forma.py."""
    tax = tax or tx.cargar()
    filas = [puntuar(c, historial, tax) for c in candidatos]
    elegibles = sorted([f for f in filas if f["pasa_piso"] and f.get("producible") is not False and not f["sin_mercado"]],
                       key=lambda f: -f["puntaje"])
    fuera = [f for f in filas if f not in elegibles]
    nuevos = sorted({f["tipo"] for f in filas if f["estado_tipo"] in ("sin-registrar", "nuevo-a-confirmar")})
    return {"elegibles": elegibles, "fuera": fuera, "historial": historial,
            "complejos_que_pasan": sum(1 for f in elegibles if f["complejo"]),
            "complejos_no_producibles": sum(1 for f in fuera if f["complejo"] and f["pasa_piso"] and not f["sin_mercado"]),
            "sin_mercado": sum(1 for f in fuera if f["sin_mercado"]), "tipos_nuevos": nuevos}


def main() -> int:
    resto = sys.argv[1:]
    ruta_hist = Path("ofertas/historial-modelado.json")
    if "--historial" in resto:
        i = resto.index("--historial")
        if i + 1 >= len(resto):
            print(__doc__)
            return 2
        ruta_hist = Path(resto[i + 1])
        resto = resto[:i] + resto[i + 2:]
    args = [a for a in resto if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    historial = json.loads(ruta_hist.read_text(encoding="utf-8")) if ruta_hist.is_file() else []
    res = ordenar(json.loads(Path(args[0]).read_text(encoding="utf-8")), historial)
    elegibles, fuera = res["elegibles"], res["fuera"]
    if "--json" in sys.argv:
        print(json.dumps(res, ensure_ascii=False, indent=1))
        return 0
    if historial:
        print("Últimas lanzadas: " + " · ".join(f"{h.get('oferta')} ({h.get('funnel')})" for h in historial[-3:]))
    ancho = max([14] + [len(f["tipo"]) + 2 for f in elegibles + fuera])
    print(f"{'#':>2}  {'página':<26}{'tipo':<{ancho}}{'anun.':>6}{'días':>6}{'compl.':>8}{'antig.':>8}{'anun.':>7}{'var.':>6}{'puntaje':>9}  extras · notas")
    for i, f in enumerate(elegibles, 1):
        detalle = "; ".join(([", ".join(f["extras"])] if f["extras"] else []) + f["notas"])
        print(f"{i:>2}  {str(f['pagina'])[:25]:<26}{f['tipo']:<{ancho}}{f['anuncios']:>6}{f['dias']:>6}{f['complejidad']:>8}{f['antiguedad']:>8}"
              f"{f['senal_anuncios']:>7}{f['factor_variacion']:>6}{f['puntaje']:>9}  {detalle}")
    if len(elegibles) > 1 and elegibles[0]["puntaje"] - elegibles[1]["puntaje"] < EMPATE:
        cerca = [f["pagina"] for f in elegibles if elegibles[0]["puntaje"] - f["puntaje"] < EMPATE]
        print(f"\nEmpate técnico (menos de {EMPATE} de diferencia): {', '.join(map(str, cerca))}. Presentar todos al dueño.")
    if elegibles and elegibles[0]["medir_paises"]:
        print(f"\nAntes de tomar «{elegibles[0]['pagina']}»: medir en qué países corre su referente (paises_referente.py, por mitades) "
              "y volver a ordenar con `referente_paises`. Si corre en todos, queda fuera y se toma el siguiente.")
    for f in fuera:
        print(f"--  {str(f['pagina'])[:25]:<26}{f['tipo']:<{ancho}}{f['anuncios']:>6}{f['dias']:>6}  fuera: {'; '.join(f['notas'])}")
    print(f"\nFunnels complejos (complejidad ≥ {UMBRAL_COMPLEJO}) que pasan el piso: {res['complejos_que_pasan']}"
          + ("" if res["complejos_que_pasan"] >= 3 else " · faltan para llegar a 3: seguir buscando por forma antes de elegir (01 §1.5)."))
    if res["complejos_no_producibles"]:
        print(f"Complejos que pasan el piso pero no se pueden producir con este recorrido: {res['complejos_no_producibles']} (sirven de ejemplo de estructura).")
    if res["sin_mercado"]:
        print(f"Vetados porque el referente corre en todos los países donde podemos lanzar: {res['sin_mercado']} (marcarlos descartados en el banco).")
    if res["tipos_nuevos"]:
        print("Tipos nuevos, a confirmar por el dueño: " + ", ".join(res["tipos_nuevos"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
