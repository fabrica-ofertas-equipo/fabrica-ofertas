"""¿Toca lanzar ahora? Ritmo de lanzamientos automáticos y réplicas (reglas L5 y E6 del dueño, firmadas el 2026-11-13).

L5: 2 ofertas nuevas por día, solas, mientras haya menos de 8 ofertas en test.
    Banco (14-nov, el dueño: «el sistema siempre tiene que tener preparadas ofertas… si no encontramos, sigue buscando»):
    los 3 listos son la RESERVA a reponer, no un freno. Con 1 listo se lanza; con 0, BUSCAR_Y_LANZAR: la misma vuelta
    trabaja el radar (verificar → medir → barrido) hasta conseguir una lista y la lanza. Nunca se espera por el banco.
E6: una oferta con 7 días o más desde su inicio y ROAS neto (neto de la tienda ÷ gasto en Meta) ≥ 1,30 en los últimos 7 días
    se replica en otro mercado. Desde el 14-nov (dueño: «dos ofertas por día sí o sí nuevas») la réplica NO ocupa los 2 lugares
    de ofertas nuevas: se suma aparte. Tampoco ocupa lugar una armada que quedó frenada sin salir.

Uso (desde la raíz): python3 .claude/skills/modelar-y-lanzar-oferta/scripts/cupo_lanzamiento.py [--json] [--ahora ISO]
Salida: LANZAR_REPLICA (con la oferta madre), LANZAR_NUEVA (con los listos del banco), BUSCAR_Y_LANZAR (banco vacío:
buscar en la misma vuelta y lanzar) o ESPERAR (solo por tope del día o de tests en curso). `reponer_banco` dice si el
banco está bajo la reserva.
Solo decide: el lanzamiento lo hace la tarea «lanzar-ofertas» con la skill modelar-y-lanzar-oferta.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / ".claude" / "skills" / "escalar-oferta" / "scripts"))
from reglas import valor  # noqa: E402
LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
HISTORIAL = RAIZ / "ofertas" / "historial-modelado.json"
BANCO = Path(__file__).resolve().parent / "banco_candidatos.py"
POR_DIA = valor("lanzamiento.por_dia", 2)
MAX_EN_TEST = valor("lanzamiento.max_en_test", 8)
MIN_LANZAR = valor("lanzamiento.banco_minimo_para_lanzar", 1)
OBJETIVO_LISTOS = valor("lanzamiento.banco_objetivo_listos", 3)
REPLICA_DIAS = valor("replica.dias", 7)
REPLICA_ROAS_NETO = valor("replica.roas_neto_minimo", 1.30)


def _leer(p: Path, defecto):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def en_test(libro: dict, ahora: dt.datetime) -> list[str]:
    """Tests programados o activos todavía en fase de test (día 1 o sin ventas)."""
    from dashboard import negocio as N
    d = N.calcular(libro, ahora)
    return [o["nombre"] for o in d["ofertas"] if o.get("estado") in ("activa", "programada") and o.get("fase") != "post-lanzamiento"]


def replicables(libro: dict, historial: list[dict], ahora: dt.datetime) -> list[dict]:
    from dashboard import negocio as N
    hoy = ahora.date()
    d = N.calcular_periodo(libro, ahora, hoy - dt.timedelta(days=REPLICA_DIAS), hoy - dt.timedelta(days=1))
    ya = {h.get("replica_de") for h in historial if h.get("replica_de")}
    out = []
    for o in d["ofertas"]:
        ini = N.parsear_fecha(o.get("inicio_texto"))
        if not ini or (ahora - ini).days < REPLICA_DIAS or o.get("estado") != "activa" or o["nombre"] in ya:
            continue
        rn = o.get("roas_neto")
        if isinstance(rn, (int, float)) and rn >= REPLICA_ROAS_NETO:
            out.append({"oferta": o["nombre"], "mercado": o.get("mercado"), "roas_neto_7d": rn})
    return sorted(out, key=lambda r: -r["roas_neto_7d"])


def banco_listos() -> dict:
    r = subprocess.run([sys.executable, str(BANCO), "estado", "--json"], cwd=RAIZ, capture_output=True, text=True, timeout=30, check=False)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"veredicto": "SIN_LECTURA", "listos": []}


def decidir(libro: dict, historial: list[dict], banco: dict, ahora: dt.datetime, zona_hoy: str = "America/Argentina/Buenos_Aires") -> dict:
    from zoneinfo import ZoneInfo
    hoy = ahora.astimezone(ZoneInfo(zona_hoy)).date().isoformat()
    # Solo cuenta la que SALE (programada o activa). Una armada que quedó frenada por algo del dueño (fan page, píxel) no ocupa
    # lugar (dueño, 14-nov: «tienen que salir dos ofertas por día sí o sí nuevas»): la vuelta sigue con otra.
    frenadas = {str(t.get("nombre") or t.get("oferta")) for t in libro.get("tests", []) if str(t.get("estado", "")).lower() == "armado"}
    # «Dos ofertas por día sí o sí NUEVAS» (dueño, 14-nov): las réplicas (replica_de) se suman aparte, no ocupan esos lugares.
    del_dia = [h for h in historial if str(h.get("fecha", ""))[:10] == hoy and not h.get("replica_de")]
    sin_salir = [h.get("oferta") for h in del_dia if h.get("oferta") in frenadas or "sin activar" in str(h.get("estado", "")).lower()]
    hoy_n = len(del_dia) - len(sin_salir)
    base = {"lanzadas_hoy": hoy_n, "por_dia": POR_DIA, "armadas_sin_salir": sin_salir}
    if hoy_n >= POR_DIA:
        return {**base, "decision": "ESPERAR", "porque": f"Ya salieron {hoy_n} hoy (tope {POR_DIA})."}
    rep = replicables(libro, historial, ahora)
    if rep:
        return {**base, "decision": "LANZAR_REPLICA", "replica": rep[0],
                "porque": f"{rep[0]['oferta']} lleva {REPLICA_DIAS}+ días con ROAS neto {rep[0]['roas_neto_7d']} (≥ {REPLICA_ROAS_NETO}): se replica en otro mercado."}
    tests = en_test(libro, ahora)
    base["en_test"] = len(tests)
    if len(tests) >= MAX_EN_TEST:
        return {**base, "decision": "ESPERAR", "porque": f"Hay {len(tests)} ofertas en test (tope {MAX_EN_TEST})."}
    complejos = banco.get("listos") or []
    simples = [c for c in (banco.get("listos_simples") or []) if c not in complejos]
    # Primero los complejos; si no hay, los simples verificados y sobre el piso (guía 12 §1b paso 5: «el mejor producible»).
    listos = complejos + simples
    base["listos"] = len(listos)
    base["listos_complejos"] = len(complejos)
    base["reponer_banco"] = len(complejos) < OBJETIVO_LISTOS
    if len(listos) < MIN_LANZAR:
        return {**base, "decision": "BUSCAR_Y_LANZAR",
                "porque": f"Hay lugar ({hoy_n}/{POR_DIA} hoy, {len(tests)}/{MAX_EN_TEST} en test) y el banco no tiene listos: "
                          "esta vuelta verifica lo que el radar tiene, mide y barre hasta conseguir uno, y lo lanza."}
    reserva = f" (complejos {len(complejos)}/{OBJETIVO_LISTOS}: el radar repone)" if base["reponer_banco"] else ""
    if not complejos:
        reserva += "; sin complejos: va el mejor simple verificado (guía 12 §1b paso 5)"
    return {**base, "decision": "LANZAR_NUEVA", "candidatos": listos,
            "porque": f"Hay lugar ({hoy_n}/{POR_DIA} hoy, {len(tests)}/{MAX_EN_TEST} en test) y {len(listos)} listos{reserva}: elegir con ordenar_candidatos.py y lanzar."}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ahora")
    a = ap.parse_args()
    ahora = dt.datetime.fromisoformat(a.ahora) if a.ahora else dt.datetime.now(dt.timezone.utc)
    r = decidir(_leer(LIBRO, {"tests": []}), _leer(HISTORIAL, []), banco_listos(), ahora)
    print(json.dumps(r, ensure_ascii=False, indent=1) if a.json else f"{r['decision']}: {r['porque']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
