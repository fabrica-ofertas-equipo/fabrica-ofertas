"""Control previo para activar sola una campaña de lanzamiento (regla L3 del dueño, firmada el 2026-11-13).

Dueño: «si [se activa sola]; asegurate que siempre 00 del mercado que estamos lanzando por zona horaria».
Rechazados (dueño, 16-nov, reemplaza el «5 o más no se lanza»): un rechazado solo se apela, nunca se reemplaza; «si lo rechazan
esa campaña no sale (en este caso que era 1 1 1); si rechazan ads en otra campaña donde hay otros, sale igual la campaña».

Comprueba, y solo si TODO pasa dice ACTIVAR:
  1. landing y checkout responden (HTTP 2xx/3xx) y la landing tiene el píxel de la ficha;
  2. el producto completo cuesta 19 USD o más (regla 19/27);
  3. el presupuesto diario de la campaña es 3 × el ticket del producto completo (±5 %);
  4. cada conjunto empieza a las 00:00 en punto de la zona horaria del mercado, y en el futuro;
  5. el test está en el libro con estado «programado» y precio en USD (sin eso la vigilancia no puede cortar);
  6. al menos 1 anuncio no rechazado (una campaña de varios sale con los que quedan; una pocket 1-1-1 con su único anuncio
     rechazado no sale) y los anuncios cargados que pide la campaña (`anuncios.previstos`, o 3 si no viene), rechazados incluidos;
  7. sin errores de Meta en campaña, conjuntos ni anuncios;
  8. (dueño, 14-nov) el funnel entero probado en un iPhone simulado con el píxel bloqueado: landing, vistas, quiz y cada
     checkout con correo, botón de pagar e imagen del producto (`verificar_funnel.py correr --oferta … --antes`). Va en la
     lectura como "funnel": {"decision": "OK"|"FALLA", "fallas": […]}; sin esa prueba no se activa.
  9. (dueño, 16-nov) el nombre de la campaña (`campana_nombre`) es «PAÍS | Oferta | tipo» con el mercado y la oferta del libro, para que
     nube_sync la asigne sola a su oferta (fotos_campanas.oferta_de_campana).

Uso: python3 .claude/skills/escalar-oferta/scripts/control_previo.py --lectura <lectura.json> [--sin-http]
lectura.json: {"oferta": "<nombre en el libro>", "mercado": "MX", "presupuesto_usd": 57, "campana_nombre": "MX | <Oferta> | CBO test 10 videos",
               "conjuntos": [{"id": "…", "start_time": "2026-11-15T00:00:00-0600"}],
               "anuncios": {"total": 10, "rechazados": 1, "en_revision": 3, "previstos": 10}, "errores": [],
               "funnel": {"decision": "OK", "fallas": []}}
Salida: {"decision": "ACTIVAR" | "NO_ACTIVAR", "controles": [...], "avisar": "…"}.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fotos_campanas as FC  # noqa: E402
import salud  # noqa: E402
from reglas import valor  # noqa: E402

RAIZ = Path(__file__).resolve().parents[4]
LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
PRECIO_MIN_USD = valor("lanzamiento.precio_minimo_usd", 19)
TICKETS_PRESUPUESTO = valor("lanzamiento.presupuesto_test_tickets", 3)
TOLERANCIA = valor("lanzamiento.tolerancia_presupuesto", 0.05)
APROBADOS_MIN = valor("lanzamiento.rechazados.aprobados_minimos", 1)     # sin ninguno no rechazado, esa campaña no sale
ANUNCIOS_MIN = valor("lanzamiento.anuncios_minimos", 3)                  # cargados, rechazados incluidos

# Zona horaria del mercado (la de la capital o la del grueso del público). Cada país de elegir_mercado.py.
ZONA = {
    "MX": "America/Mexico_City", "BR": "America/Sao_Paulo", "CO": "America/Bogota", "CL": "America/Santiago", "PE": "America/Lima",
    "AR": "America/Argentina/Buenos_Aires", "EC": "America/Guayaquil", "UY": "America/Montevideo", "GT": "America/Guatemala",
    "DO": "America/Santo_Domingo", "CR": "America/Costa_Rica", "PA": "America/Panama", "BO": "America/La_Paz", "PY": "America/Asuncion",
    "US": "America/New_York", "CA": "America/Toronto", "AU": "Australia/Sydney", "NZ": "Pacific/Auckland", "GB": "Europe/London",
    "IE": "Europe/Dublin", "ES": "Europe/Madrid", "PT": "Europe/Lisbon", "IT": "Europe/Rome", "FR": "Europe/Paris", "BE": "Europe/Brussels",
    "NL": "Europe/Amsterdam", "DE": "Europe/Berlin", "AT": "Europe/Vienna", "CH": "Europe/Zurich", "SE": "Europe/Stockholm",
    "NO": "Europe/Oslo", "DK": "Europe/Copenhagen", "FI": "Europe/Helsinki", "PL": "Europe/Warsaw", "CZ": "Europe/Prague",
    "RO": "Europe/Bucharest", "HU": "Europe/Budapest", "GR": "Europe/Athens", "TR": "Europe/Istanbul", "MY": "Asia/Kuala_Lumpur",
    "SG": "Asia/Singapore", "PH": "Asia/Manila", "HK": "Asia/Hong_Kong", "KE": "Africa/Nairobi", "AE": "Asia/Dubai", "SA": "Asia/Riyadh",
    "IL": "Asia/Jerusalem", "ZA": "Africa/Johannesburg", "NG": "Africa/Lagos", "EG": "Africa/Cairo", "MA": "Africa/Casablanca",
    "JP": "Asia/Tokyo", "KR": "Asia/Seoul", "IN": "Asia/Kolkata", "ID": "Asia/Jakarta", "VN": "Asia/Ho_Chi_Minh", "TH": "Asia/Bangkok",
}


def _iso(s: str) -> dt.datetime:
    s = s.strip()
    if len(s) >= 5 and s[-5] in "+-" and s[-3] != ":":       # Meta: 2026-11-15T00:00:00-0600
        s = s[:-2] + ":" + s[-2:]
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def inicio_ok(start_time: str, mercado: str, ahora: dt.datetime) -> tuple[bool, str]:
    zona = ZONA.get(mercado)
    if not zona:
        return False, f"sin zona horaria para {mercado}: agregarla a ZONA"
    t = _iso(start_time).astimezone(ZoneInfo(zona))
    if (t.hour, t.minute, t.second) != (0, 0, 0):
        return False, f"empieza a las {t.strftime('%H:%M')} hora de {mercado}, no a las 00:00"
    if t <= ahora:
        return False, f"el inicio ({t.isoformat()}) ya pasó: saldría de inmediato"
    return True, f"00:00 del {t.strftime('%d/%m')} hora de {mercado} ({zona})"


def _pixel(t: dict) -> str:
    px = (t.get("ficha") or {}).get("pixel")
    return str((px.get("id") if isinstance(px, dict) else px) or "")


def pixel_compartido(t: dict, libro: dict) -> str | None:
    """Píxel propio por oferta, réplicas incluidas (dueño, 14-nov: «cada oferta tiene que tener su público»; antes las réplicas
    compartían el de la madre y eso mezclaba los públicos de Francia e Italia con los compradores de España). Un píxel que ya
    usa otra fila del libro (madre, réplica u otra oferta) FRENA la activación: se crea el píxel propio y se vuelve a controlar.
    Los niveles de una misma oferta viven en la misma fila (ficha.tiendas) y comparten su píxel."""
    px = _pixel(t)
    if not px:
        return None
    otras = sorted({x.get("nombre") or x.get("oferta") for x in libro.get("tests") or []
                    if x is not t and _pixel(x) == px})
    if not otras:
        return None
    return (f"usa el píxel {px}, que también usa {', '.join(otras)}: los públicos se mezclan. "
            "Crear el píxel propio, cargarlo en sus tiendas y en un conjunto nuevo (un conjunto publicado no cambia de píxel).")


def controlar(lectura: dict, libro: dict, ahora: dt.datetime, probar=salud.probar_url) -> dict:
    nombre = lectura.get("oferta")
    t = next((x for x in libro.get("tests") or [] if (x.get("nombre") or x.get("oferta")) == nombre), None)
    ctrl: list[dict] = []

    def c(clave: str, ok: bool, detalle: str) -> None:
        ctrl.append({"control": clave, "ok": bool(ok), "detalle": detalle})

    if t is None:
        c("libro", False, f"«{nombre}» no está en el libro de tests: la vigilancia no podría cortarla")
        return {"decision": "NO_ACTIVAR", "controles": ctrl, "avisar": f"{nombre}: no se activa, falta su fila en el libro de tests."}
    precios = [float(x["precio"]["usd"]) for x in (t.get("ficha") or {}).get("tiendas") or []
               if isinstance(x, dict) and isinstance(x.get("precio"), dict) and isinstance(x["precio"].get("usd"), (int, float))]
    ticket = max(precios) if precios else None
    c("libro", t.get("estado") == "programado" and bool(ticket), f"estado {t.get('estado')}, ticket del completo {ticket}")
    c("precio", bool(ticket) and ticket >= PRECIO_MIN_USD, f"producto completo US$ {ticket} (mínimo {PRECIO_MIN_USD})")
    pres = float(lectura.get("presupuesto_usd") or 0)
    esperado = TICKETS_PRESUPUESTO * (ticket or 0)
    c("presupuesto", bool(ticket) and abs(pres - esperado) <= TOLERANCIA * esperado, f"US$ {pres:g}/día; la regla da 3 × {ticket} = US$ {esperado:g}")
    conj = lectura.get("conjuntos") or []
    if not conj:
        c("inicio", False, "sin conjuntos en la lectura")
    for cj in conj:
        ok, det = inicio_ok(str(cj.get("start_time") or ""), lectura.get("mercado") or t.get("mercado") or "", ahora) if cj.get("start_time") else (False, "sin start_time")
        c(f"inicio {cj.get('id')}", ok, det)
    an = lectura.get("anuncios") or {}
    total, rech = int(an.get("total") or 0), int(an.get("rechazados") or 0)
    previstos = int(an.get("previstos") or ANUNCIOS_MIN)
    c("rechazados", total - rech >= APROBADOS_MIN,
      f"{total - rech} no rechazados de {total} ({rech} rechazados: se apelan, no se reemplazan; sin ninguno, esta campaña no sale)")
    c("anuncios", total >= previstos, f"{total} anuncios cargados (pide {previstos})")
    errs = lectura.get("errores") or []
    c("errores_meta", not errs, "sin errores" if not errs else "; ".join(str(e)[:80] for e in errs[:3]))
    cn = str(lectura.get("campana_nombre") or "").strip()
    if not cn:
        c("nombre", False, "falta campana_nombre en la lectura (el nombre exacto de la campaña en Meta)")
    else:
        dueno = FC.oferta_de_campana(cn, libro)
        c("nombre", dueno is t, f"«{cn}» → {('oferta ' + str(dueno.get('oferta'))) if dueno else 'ninguna oferta'}; tiene que ser «{t.get('mercado')} | {t.get('oferta') or t.get('nombre')} | tipo»")
    fn = lectura.get("funnel")
    if not isinstance(fn, dict):
        c("funnel", False, "falta la prueba del funnel (verificar_funnel.py correr --oferta … --antes)")
    else:
        fallas = fn.get("fallas") or []
        c("funnel", fn.get("decision") == "OK" and not fallas, "landing y checkouts probados" if not fallas else "; ".join(str(x)[:80] for x in fallas[:3]))
    if probar:
        urls = salud.urls_de(t)
        pixel = str(((t.get("ficha") or {}).get("pixel") or {}).get("id") or "")
        for k, u in urls.items():
            r = probar(u)
            c(f"responde {k}", r["ok"], f"{u} → {r.get('estado')} en {r.get('ms')} ms")
            if k in ("landing", "tienda") and r["ok"] and pixel:
                c(f"píxel {k}", pixel in r.get("html", ""), f"píxel {pixel} {'presente' if pixel in r.get('html', '') else 'NO está'}")
                break
    obs = pixel_compartido(t, libro)
    if obs:
        c("píxel propio", False, obs)
    falla = [x for x in ctrl if not x["ok"]]
    if falla:
        return {"decision": "NO_ACTIVAR", "controles": ctrl,
                "avisar": f"{nombre}: no se activó. " + " · ".join(f"{x['control']}: {x['detalle']}" for x in falla)[:190]}
    avisar = f"{nombre}: pasó el control previo y quedó activa; sale a las 00:00 del mercado."
    if obs:
        avisar += f" Ojo: {obs}"
    return {"decision": "ACTIVAR", "controles": ctrl, "observaciones": [obs] if obs else [], "avisar": avisar}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lectura", required=True)
    ap.add_argument("--sin-http", action="store_true")
    ap.add_argument("--ahora")
    a = ap.parse_args(argv)
    lectura = json.loads(Path(a.lectura).read_text(encoding="utf-8"))
    libro = json.loads(LIBRO.read_text(encoding="utf-8"))
    ahora = dt.datetime.fromisoformat(a.ahora) if a.ahora else dt.datetime.now(dt.timezone.utc)
    print(json.dumps(controlar(lectura, libro, ahora, None if a.sin_http else salud.probar_url), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
