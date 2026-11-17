"""Plan del corte de RESPALDO en la nube (dueño, 17-nov: «Respaldo si cae la Mac»).

La noche del 16 al 17-nov la Mac quedó 8,5 h sin internet y nadie cortó Oferta M (US$ 57 con corte en 29,85).
Desde ahora la nube (vivo.tu-dominio.com, src/corte.mjs) puede PAUSAR una campaña pasada de corte, solo si la
vigilancia no late hace más de 30 min. Este script:

  armar()     arma el plan: `tests` (corte del test entero en el día 1) y `limites` (genérico: toda campaña con corte
              propio o con rol en reglas.json → cortes_por_rol, en cualquier fase), con las mismas reglas que
              vigilar_corte.py, y el latido de la vigilancia;
  subir()     lo sube a POST /api/plan-corte (lo llama nube_sync.py cada 5 min);
  avisar()    por cada corte nuevo que hizo la nube (cortes_nube de /api/estado): iMessage al dueño, aviso en
              avisos.jsonl y un pendiente en el libro para que la próxima vigilancia complete «Al apagar».

Uso manual: python3 plan_corte.py [--json]   (muestra el plan sin subirlo)
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vigilar_corte as VC  # noqa: E402

RAIZ = Path(__file__).resolve().parents[4]
FUNNELS = RAIZ / "ofertas" / "_funnels"
LATIDOS = FUNNELS / "latidos.json"
VISTOS = FUNNELS / "cortes_nube_vistos.json"
AVISOS = Path(__file__).resolve().parent / "avisos.py"
ZONA_CUENTA = ZoneInfo("America/Argentina/Buenos_Aires")   # zona de la cuenta de Meta (los días de meta_dia)


def latido_vigilancia() -> str | None:
    """Lo más reciente entre el latido de la vigilancia y el pulso que deja hay_trabajo.py al arrancar cada vuelta
    (las vueltas sin trabajo no dejan latido: sin el pulso, la nube creería caída una vigilancia sana)."""
    marcas = []
    try:
        lat = json.loads(LATIDOS.read_text())["vigilancia-ofertas"]
        marcas.append(lat.get("ultimo_ok") or lat.get("ultimo"))
    except (OSError, ValueError, KeyError):
        pass
    try:
        marcas.append(json.loads((FUNNELS / "pulso_vigilancia.json").read_text()).get("pulso"))
    except (OSError, ValueError):
        pass
    fechas = []
    for m in marcas:
        try:
            fechas.append(dt.datetime.fromisoformat(m))
        except (TypeError, ValueError):
            pass
    return max(fechas).astimezone(dt.timezone.utc).isoformat(timespec="seconds") if fechas else None


def _tiendas(t: dict) -> list[str]:
    x = t.get("tienda")
    lista = x if isinstance(x, list) else [x] if x else []
    lista += [s.get("slug") for s in ((t.get("ficha") or {}).get("tiendas") or []) if isinstance(s, dict) and s.get("slug")]
    return sorted({str(s) for s in lista if s})


def _dia_cuenta(iso: str | None, defecto: str) -> str:
    try:
        return dt.datetime.fromisoformat(str(iso)).astimezone(ZONA_CUENTA).date().isoformat()
    except (TypeError, ValueError):
        return defecto


def _utc(iso: str | None) -> str | None:
    try:
        return dt.datetime.fromisoformat(str(iso)).astimezone(dt.timezone.utc).isoformat()
    except (TypeError, ValueError):
        return None


def armar(libro: dict, ahora: dt.datetime, latido: str | None) -> dict:
    """Dos listas para la nube:
      tests    — el corte del TEST ENTERO en el día 1 (suma de sus campañas, ventas del webhook, segunda oportunidad);
      limites  — GENÉRICO, una entrada por campaña que se corta por su cuenta (réplicas en el día 1 y, desde el 17-nov, toda
                 campaña con corte propio o con rol en reglas.json → cortes_por_rol, en cualquier fase: Nuevos, Iteraciones,
                 pockets…). La nube no conoce roles ni metodología: suma gasto y compras de la campaña desde `desde` y pausa
                 si gasto ≥ tickets × ticket × máx(1, compras). Un tipo de campaña nuevo entra solo con su número en reglas.json.
    Mismas reglas que vigilar_corte.py (corte_tickets_de, limites_por_campana): la Mac y la nube deciden igual."""
    tests, limites = [], []
    for t in libro.get("tests") or []:
        if t.get("estado") not in ("activo", "programado") or not t.get("inicio"):
            continue
        ticket = VC.ticket_corte(t.get("ficha") or {})
        ids = VC.campanas_del_test(t)
        if not ticket or not ids:
            continue
        ini = dt.datetime.fromisoformat(t["inicio"])
        fin = VC.fin_dia1(t["inicio"])
        dia1 = ahora < fin
        propias = VC.limites_por_campana(t, ahora)
        conf = {str(c.get("id")): c for c in ((t.get("ficha") or {}).get("campanas") or []) if isinstance(c, dict) and c.get("id")}
        if dia1 and propias:
            # Día 1 con corte por campaña (réplicas): cada campaña por su lado; las que no tienen corte propio, a 1,5 tickets.
            con = {p["campana"] for p in propias}
            for i in ids:
                if i not in con and str((conf.get(i) or {}).get("estado") or "ACTIVE").split(" ")[0] in ("ACTIVE", ""):
                    propias.append({"campana": i, "rol": (conf.get(i) or {}).get("rol") or "principal", "tickets": float(VC.VECES_TICKET),
                                    "ticket_usd": float(ticket), "inicio": t["inicio"]})
        elif dia1:
            principales = [v for v in (t.get("ventas") or []) if str(v.get("tipo") or "").lower() not in ("upsell", "downsell", "bump", "rebaja")]
            tests.append({
                "test": t.get("nombre"), "inicio": ini.astimezone(dt.timezone.utc).isoformat(), "fin": fin.astimezone(dt.timezone.utc).isoformat(),
                "desde": ini.astimezone(ZONA_CUENTA).date().isoformat(), "ticket_usd": float(ticket), "veces": float(VC.VECES_TICKET),
                "segunda_usada": isinstance(t.get("segunda_oportunidad"), dict), "extra_tickets": float(VC.SEGUNDA.get("extra_tickets", 0.5)),
                "ventas_conocidas": len(principales), "tiendas": _tiendas(t), "campanas": [{"id": i} for i in ids],
            })
        defecto = ini.astimezone(ZONA_CUENTA).date().isoformat()
        for p in propias:
            limites.append({"test": t.get("nombre"), "campana": p["campana"], "rol": p.get("rol"), "tickets": p["tickets"],
                            "ticket_usd": p["ticket_usd"], "desde": _dia_cuenta(p.get("inicio"), defecto),
                            "inicio": _utc(p.get("inicio")) or ini.astimezone(dt.timezone.utc).isoformat()})
    return {"generado": ahora.isoformat(timespec="seconds"), "latido_vigilancia": latido,
            "segunda": {k: VC.SEGUNDA[k] for k in ("extra_tickets", "ctr_min_pct", "pagina_a_pago_min_pct", "checkouts_min") if k in VC.SEGUNDA},
            "tests": tests, "limites": limites}


def subir(plan: dict, url: str, token: str) -> str:
    req = urllib.request.Request(f"{url}/api/plan-corte", data=json.dumps(plan).encode(), method="POST",
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": "fabrica-panel"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 - URL fija propia
        return r.read().decode()[:200]


def _imessage(texto: str) -> bool:
    sys.path.insert(0, str(RAIZ / "infra" / "cuentas"))
    try:
        import guardian  # noqa: PLC0415
        return guardian.imessage(texto)
    except Exception:  # noqa: BLE001 - el aviso no puede tumbar la sincronización
        return False


def avisar(cortes: list[dict], modificar_libro) -> list[str]:
    """Avisa una sola vez cada corte de la nube. Devuelve líneas para el registro de nube_sync."""
    try:
        vistos = set(json.loads(VISTOS.read_text()))
    except (OSError, ValueError):
        vistos = set()
    nuevos = [c for c in cortes or [] if f"{c.get('campana')}|{c.get('test')}|{c.get('resultado')}" not in vistos]
    lineas = []
    for c in nuevos:
        hecho = c.get("resultado") == "pausada"
        texto = (f"🛑 Fábrica (corte en la nube, la vigilancia no corría): {'PAUSÉ' if hecho else 'HAY QUE PAUSAR'} {c.get('test')} "
                 f"· campaña {c.get('campana')}. {c.get('porque')}"
                 + ("" if hecho else f" No pude pausarla ({c.get('resultado')}): pausala en el Administrador."))
        subprocess.run([sys.executable, str(AVISOS), "avisar", f"corte-nube-{c.get('campana')}", "--mensaje", texto, "--urgente"],
                       capture_output=True, text=True, cwd=RAIZ)
        _imessage(texto)

        def _pend(lib: dict, c=c, hecho=hecho) -> None:
            for t in lib.get("tests") or []:
                if t.get("nombre") == c.get("test"):
                    t.setdefault("pendientes", []).append({
                        "que": ("La nube pausó" if hecho else "La nube NO pudo pausar") + f" la campaña {c.get('campana')} por corte de respaldo: "
                               "completar «Al apagar» (apagado con regla «corte (nube)», FUNNEL.md, estado.md) y confirmar ventas en Impultienda.",
                        "desde": c.get("cuando"), "porque": c.get("porque")})
        modificar_libro(_pend)
        vistos.add(f"{c.get('campana')}|{c.get('test')}|{c.get('resultado')}")
        lineas.append(f"corte en la nube: {c.get('test')} · {c.get('campana')} → {c.get('resultado')}")
    if nuevos:
        VISTOS.write_text(json.dumps(sorted(vistos), ensure_ascii=False, indent=1))
    return lineas


def main(argv=None) -> int:
    libro = json.loads((FUNNELS / "libro-de-tests.json").read_text())
    plan = armar(libro, dt.datetime.now(dt.timezone.utc), latido_vigilancia())
    print(json.dumps(plan, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
