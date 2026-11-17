"""Avisos al dueño sin repetir y latido de cada tarea programada (escenarios S36, S39 y S40 del 2026-11-13).

Avisos: cada tarea, antes de mandar una notificación al celular (herramienta PushNotification), pregunta aquí si corresponde.
El mismo aviso (misma clave) no se repite dentro de su ventana: los urgentes cada 3 h, los normales cada 24 h. Todo queda en
ofertas/_funnels/avisos.jsonl, y el panel lo lee.

Latidos: cada tarea programada anota al terminar si le fue bien o mal. A la tercera falla seguida, el script pide un aviso
urgente; el panel pone la tarea en rojo si no late hace más del doble de su ritmo.

Uso (desde la raíz; A=.claude/skills/escalar-oferta/scripts/avisos.py):
  python3 $A avisar CLAVE --mensaje "…" [--urgente] [--oferta X]   → imprime ENVIAR o REPETIDO (y lo registra)
  python3 $A latido TAREA ok|error [--detalle "…"]                  → imprime OK, o AVISAR si van 3 fallas seguidas
  python3 $A no-llego CLAVE [--motivo "…"]                          → si PushNotification dice «not sent»: el próximo intento vuelve a salir
  python3 $A sin-entregar                                            → avisos de las últimas 24 h que no llegaron
  python3 $A estado [--json]
Tareas conocidas y su ritmo (minutos): ver RITMO.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reglas import valor  # noqa: E402
from paises import con_paises  # noqa: E402   (mercados con bandera y nombre: «IE (🇮🇪 Irlanda)», dueño 17-nov)

RAIZ = Path(__file__).resolve().parents[4]
AVISOS = RAIZ / "ofertas" / "_funnels" / "avisos.jsonl"
LATIDOS = RAIZ / "ofertas" / "_funnels" / "latidos.json"
VENTANA_H = {"urgente": valor("avisos.repetir_urgente_horas", 3), "normal": valor("avisos.repetir_normal_horas", 24)}
FALLAS_PARA_AVISAR = valor("avisos.fallas_para_avisar", 3)
RITMO = {"vigilancia-ofertas": 60, "radar-ofertas": 120, "renovacion-diaria": 1440, "buscar-ofertas": 1440,
         "lanzar-ofertas": 720, "revision-diaria": 1440, "soporte-clientes": 720,
         "repesca-carritos": 180}


def _ahora() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _lineas(p: Path) -> list[dict]:
    try:
        return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    except (OSError, ValueError):
        return []


def debe_avisar(clave: str, urgente: bool, historial: list[dict], ahora: dt.datetime) -> bool:
    ventana = dt.timedelta(hours=VENTANA_H["urgente" if urgente else "normal"])
    for a in reversed(historial):
        # «enviado» = se decidió mandar; si después la notificación no llegó («entregado»: false, ver `no-llego`),
        # no cuenta: el próximo intento vuelve a salir (14-nov: los avisos de Balloon y Mon Carnet no llegaron y se trabaron).
        if a.get("clave") == clave and a.get("enviado") and a.get("entregado") is not False:
            return ahora - dt.datetime.fromisoformat(a["cuando"]) >= ventana
    return True


def avisar(clave: str, mensaje: str, urgente: bool, oferta: str | None, ahora: dt.datetime) -> bool:
    enviar = debe_avisar(clave, urgente, _lineas(AVISOS), ahora)
    mensaje = con_paises(mensaje)
    AVISOS.parent.mkdir(parents=True, exist_ok=True)
    with AVISOS.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"cuando": ahora.isoformat(timespec="minutes"), "clave": clave, "mensaje": mensaje[:260],
                            "urgente": urgente, "oferta": oferta, "enviado": enviar}, ensure_ascii=False) + "\n")
    return enviar


def no_llego(clave: str, motivo: str | None) -> bool:
    """Marca el último aviso enviado de esa clave como no entregado (PushNotification devolvió «not sent»)."""
    filas = _lineas(AVISOS)
    for a in reversed(filas):
        if a.get("clave") == clave and a.get("enviado"):
            a["entregado"] = False
            a["motivo_no_entregado"] = (motivo or "")[:120]
            tmp = AVISOS.with_suffix(".tmp")
            tmp.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in filas), encoding="utf-8")
            os.replace(tmp, AVISOS)
            return True
    return False


def sin_entregar(ahora: dt.datetime, horas: int = 24) -> list[dict]:
    """Avisos de las últimas `horas` que no llegaron al celular y no se volvieron a mandar con éxito: el panel y la revisión los muestran."""
    filas = _lineas(AVISOS)
    out = {}
    for a in filas:
        if ahora - dt.datetime.fromisoformat(a["cuando"]) > dt.timedelta(hours=horas):
            continue
        if a.get("enviado") and a.get("entregado") is False:
            out[a["clave"]] = a
        elif a.get("enviado"):
            out.pop(a["clave"], None)
    return list(out.values())


def latido(tarea: str, resultado: str, detalle: str | None, ahora: dt.datetime) -> dict:
    try:
        lat = json.loads(LATIDOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        lat = {}
    t = lat.get(tarea) or {"fallas_seguidas": 0}
    t["ultimo"] = ahora.isoformat(timespec="minutes")
    t["resultado"] = resultado
    t["detalle"] = (detalle or "")[:200]
    t["fallas_seguidas"] = 0 if resultado == "ok" else t.get("fallas_seguidas", 0) + 1
    if resultado == "ok":
        t["ultimo_ok"] = t["ultimo"]
    lat[tarea] = t
    LATIDOS.parent.mkdir(parents=True, exist_ok=True)
    tmp = LATIDOS.with_suffix(".tmp")
    tmp.write_text(json.dumps(lat, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, LATIDOS)
    return t


def estado_latidos(lat: dict, ahora: dt.datetime) -> list[dict]:
    out = []
    for tarea, ritmo in RITMO.items():
        t = lat.get(tarea)
        if not t:
            out.append({"tarea": tarea, "salud": "sin_dato", "ritmo_min": ritmo})
            continue
        edad = int((ahora - dt.datetime.fromisoformat(t["ultimo"])).total_seconds() // 60)
        salud = "error" if t.get("fallas_seguidas", 0) >= FALLAS_PARA_AVISAR or edad > 2 * ritmo else ("aviso" if t.get("resultado") != "ok" else "ok")
        out.append({"tarea": tarea, "salud": salud, "edad_min": edad, "ritmo_min": ritmo, "fallas_seguidas": t.get("fallas_seguidas", 0),
                    "detalle": t.get("detalle")})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("avisar"); a.add_argument("clave"); a.add_argument("--mensaje", required=True); a.add_argument("--urgente", action="store_true"); a.add_argument("--oferta")
    l = sub.add_parser("latido"); l.add_argument("tarea"); l.add_argument("resultado", choices=["ok", "error"]); l.add_argument("--detalle")
    e = sub.add_parser("estado"); e.add_argument("--json", action="store_true")
    n = sub.add_parser("no-llego"); n.add_argument("clave"); n.add_argument("--motivo")
    sub.add_parser("sin-entregar")
    x = ap.parse_args(argv)
    ahora = _ahora()
    if x.cmd == "avisar":
        print("ENVIAR" if avisar(x.clave, x.mensaje, x.urgente, x.oferta, ahora) else "REPETIDO")
    elif x.cmd == "no-llego":
        print("MARCADO" if no_llego(x.clave, x.motivo) else "SIN_AVISO")
    elif x.cmd == "sin-entregar":
        print(json.dumps(sin_entregar(ahora), ensure_ascii=False, indent=1))
    elif x.cmd == "latido":
        t = latido(x.tarea, x.resultado, x.detalle, ahora)
        print("AVISAR" if t["fallas_seguidas"] >= FALLAS_PARA_AVISAR else "OK")
    else:
        try:
            lat = json.loads(LATIDOS.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            lat = {}
        r = estado_latidos(lat, ahora)
        print(json.dumps(r, ensure_ascii=False, indent=1) if x.json else "\n".join(f"{t['tarea']}: {t['salud']}" for t in r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
