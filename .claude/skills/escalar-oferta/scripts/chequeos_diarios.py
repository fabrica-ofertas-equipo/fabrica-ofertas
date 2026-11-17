"""Chequeos de la revisión diaria (escenarios S10, S34 y S23 del 2026-11-13).

  kie         saldo de créditos de Kie (GET https://api.kie.ai/api/v1/chat/credit con KIE_API_KEY de .env, sin imprimirla),
              y prueba REAL de la voz de Gemini (una palabra con el modelo de los anuncios) más el último saldo anotado.
  gemini-saldo --usd N   anota el saldo que muestra AI Studio → Billing (Google no lo da por API); avisa si baja de
              gemini.saldo_minimo_usd (5) o si pasa una semana sin mirarlo.
              Bajo el costo de 2 rondas de renovación (5.400 créditos) → aviso: la recarga es del dueño.
  comisiones  por tienda y moneda, la proporción neto ÷ bruto de cada venta contra la mediana de las anteriores: si la última
              se aparta más de 1 punto → aviso (cambió la comisión de Impul Pay o el impuesto). Tipos de cambio del libro de
              más de 7 días → aviso para actualizarlos.
  cartera     las ofertas activas ordenadas por ROAS neto de los últimos 7 días, con la regla que les toca: para el resumen
              del día y para ver de un vistazo dónde rinde más la plata.

Uso: python3 .claude/skills/escalar-oferta/scripts/chequeos_diarios.py [kie|comisiones|cartera|todo] [--json] [--sin-red]
Salida: {"avisos": [{clave, mensaje, urgente}], "kie": …, "cartera": […]}. Los avisos pasan después por avisos.py.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import sys
import urllib.error
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from reglas import valor  # noqa: E402
LIBRO = RAIZ / "ofertas" / "_funnels" / "libro-de-tests.json"
KIE_MINIMO = valor("kie.saldo_minimo", 5400)          # ≈ 2 rondas de renovación (la más cara costó ~2.700 créditos)
DESVIO_COMISION = 0.01     # 1 punto
DIAS_TIPO_CAMBIO = 7
TIPOS_EXTRA = ("upsell", "downsell", "bump", "rebaja")


def _clave_kie() -> str | None:
    try:
        for ln in (RAIZ / ".env").read_text(encoding="utf-8").splitlines():
            k, _, v = ln.partition("=")
            if k.strip() == "KIE_API_KEY" and v.strip():
                return v.strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def saldo_kie() -> float | None:
    clave = _clave_kie()
    if not clave:
        return None
    req = urllib.request.Request("https://api.kie.ai/api/v1/chat/credit", headers={"Authorization": f"Bearer {clave}"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 - URL fija de Kie
            body = json.loads(r.read().decode("utf-8"))
    except (OSError, ValueError):
        return None
    return float(body["data"]) if body.get("code") == 200 and isinstance(body.get("data"), (int, float)) else None


ESTADO_SERVICIOS = LIBRO.parent / "servicios_estado.json"


def anotar_servicio(sid: str, datos: dict) -> None:
    """Guarda el estado de un servicio para el panel («Servicios y saldos»): {estado: ok|aviso|error, detalle, cuando, ...}."""
    try:
        est = json.loads(ESTADO_SERVICIOS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        est = {}
    est[sid] = {**datos, "cuando": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")}
    ESTADO_SERVICIOS.write_text(json.dumps(est, ensure_ascii=False, indent=1), encoding="utf-8")


GEMINI_MINIMO = valor("gemini.saldo_minimo_usd", 5)   # una voz de anuncio cuesta ~US$ 0,02; 5 USD ≈ 25 rondas de renovación
GEMINI_DIAS_SIN_MIRAR = 7
MODELO_VOZ = "gemini-2.5-flash-preview-tts"           # el mismo de todas las voces de los anuncios


def _clave_gemini() -> str | None:
    try:
        for ln in (RAIZ / ".env").read_text(encoding="utf-8").splitlines():
            k, _, v = ln.partition("=")
            if k.strip() == "GEMINI_API_KEY" and v.strip():
                return v.strip().strip('"').strip("'")
    except OSError:
        pass
    return None


def motivo_error_gemini(codigo: int, cuerpo: str) -> str:
    """Traduce el error de Google a lo que hay que hacer. Puro (probado)."""
    t = (cuerpo or "").lower()
    if "prepayment" in t or "credits are depleted" in t or codigo == 402:
        return "se acabó el saldo prepago de Gemini: recargar en AI Studio → Billing"
    if codigo == 429:
        return "cuota agotada (límite por minuto o por día): esperar o subir de nivel en AI Studio"
    if codigo in (401, 400) and ("api key" in t or "api_key" in t):
        return "clave inválida: generar otra en AI Studio y ponerla en .env"
    if codigo == 403:
        return "sin permiso o facturación suspendida: revisar la facturación en AI Studio"
    if codigo == 404:
        return f"el modelo de voz {MODELO_VOZ} ya no está disponible: cambiar el modelo en los scripts de voces"
    return f"HTTP {codigo}"


def gemini_ok() -> tuple[bool, str]:
    """Prueba REAL de la voz: una locución de una palabra con el modelo de los anuncios (cuesta una fracción de centavo).
    Pedido del dueño (13-nov): saber antes de que falle. La lista de modelos respondía aunque el saldo prepago estuviera en cero;
    esta llamada falla igual que fallaría una voz de verdad («prepayment credits are depleted», cuota, facturación)."""
    clave = _clave_gemini()
    if not clave:
        return False, "falta GEMINI_API_KEY en .env"
    cuerpo = {"contents": [{"parts": [{"text": "Listo."}]}],
              "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": "Aoede"}}}}}
    req = urllib.request.Request(f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO_VOZ}:generateContent",
                                 data=json.dumps(cuerpo).encode(), headers={"x-goog-api-key": clave, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 - URL fija de Google
            return r.status == 200, "la voz responde"
    except urllib.error.HTTPError as e:
        try:
            texto = e.read().decode("utf-8", "replace")[:800]
        except OSError:
            texto = ""
        return False, motivo_error_gemini(e.code, texto)
    except OSError as e:
        return False, f"sin conexión ({e})"


def estado_gemini(ok: bool, detalle: str, previo: dict, hoy: dt.date) -> tuple[dict, list[dict]]:
    """Estado para el panel y avisos. Combina la prueba de la voz con el último saldo anotado a mano (Google no lo da por API).
    Puro (probado). ``previo``: lo que había en servicios_estado.json (saldo_usd, saldo_leido)."""
    saldo = previo.get("saldo_usd") if isinstance(previo.get("saldo_usd"), (int, float)) else None
    leido = None
    try:
        leido = dt.date.fromisoformat(str(previo.get("saldo_leido"))[:10]) if previo.get("saldo_leido") else None
    except ValueError:
        leido = None
    extra = {k: previo[k] for k in ("saldo_usd", "saldo_leido") if k in previo}
    avisos: list[dict] = []
    if not ok:
        avisos.append({"clave": "gemini", "urgente": True, "mensaje": f"Gemini (voces) no responde: {detalle}. Sin voces no salen anuncios nuevos."})
        return {"estado": "error", "detalle": detalle, **extra}, avisos
    partes = [detalle]
    estado = "ok"
    if saldo is not None:
        partes.append(f"saldo US$ {saldo:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + (f" (mirado el {leido.strftime('%d/%m')})" if leido else ""))
        if saldo < GEMINI_MINIMO:
            estado = "aviso"
            avisos.append({"clave": "gemini-saldo", "urgente": saldo < GEMINI_MINIMO / 2,
                           "mensaje": f"Quedan US$ {saldo:.2f} en Gemini (voces), menos de US$ {GEMINI_MINIMO}. Recargar en AI Studio → Billing."})
    if leido is None or (hoy - leido).days > GEMINI_DIAS_SIN_MIRAR:
        estado = "aviso" if estado == "ok" else estado
        partes.append("saldo sin mirar" + (f" hace {(hoy - leido).days} días" if leido else ""))
        avisos.append({"clave": "gemini-saldo-sin-mirar", "urgente": False,
                       "mensaje": "Hace más de una semana que nadie mira el saldo de Gemini (Google no lo da por API). Mirarlo en AI Studio → Billing y decirlo, o anotarlo con chequeos_diarios.py gemini-saldo --usd N."})
    return {"estado": estado, "detalle": " · ".join(partes), **extra}, avisos


def chequear_kie(saldo: float | None) -> list[dict]:
    if saldo is None:
        return [{"clave": "kie-sin-lectura", "urgente": False, "mensaje": "No se pudo leer el saldo de Kie (clave o servicio): revisar antes de la renovación."}]
    if saldo < KIE_MINIMO:
        return [{"clave": "kie-saldo", "urgente": saldo < KIE_MINIMO / 2,
                 "mensaje": f"Quedan {saldo:,.0f} créditos de Kie: alcanza para menos de 2 rondas de renovación. Recargar.".replace(",", ".")}]
    return []


def chequear_comisiones(libro: dict, hoy: dt.date) -> list[dict]:
    avisos = []
    for t in libro.get("tests") or []:
        grupos: dict[tuple, list[tuple[str, float]]] = {}
        for v in t.get("ventas") or []:
            b, n = v.get("bruto"), v.get("neto")
            if isinstance(b, (int, float)) and isinstance(n, (int, float)) and b > 0 and str(v.get("tipo") or "") not in TIPOS_EXTRA:
                grupos.setdefault((v.get("tienda"), v.get("moneda")), []).append((str(v.get("fecha") or ""), n / b))
        for (tienda, moneda), filas in grupos.items():
            filas.sort()
            if len(filas) < 4:
                continue
            med = statistics.median(r for _, r in filas[:-1])
            ult = filas[-1][1]
            if abs(ult - med) > DESVIO_COMISION:
                avisos.append({"clave": f"comision-{tienda}", "urgente": False,
                               "mensaje": f"{t.get('nombre')}: en {tienda} ({moneda}) la última venta dejó el {ult * 100:.1f} % del bruto contra el {med * 100:.1f} % habitual. ¿Cambió la comisión de Impul Pay o el impuesto?"})
    tc = libro.get("tipos_de_cambio") or {}
    fecha = tc.get("fecha") or tc.get("actualizado")
    try:
        f = dt.date.fromisoformat(str(fecha)[:10]) if fecha else None
    except ValueError:
        f = None
    if f is None or (hoy - f).days > DIAS_TIPO_CAMBIO:
        avisos.append({"clave": "tipos-de-cambio", "urgente": False,
                       "mensaje": f"Los tipos de cambio del libro son del {fecha or 'sin fecha'}: actualizarlos con los que usa Impultienda."})
    return avisos


def cartera(libro: dict, ahora: dt.datetime) -> list[dict]:
    from dashboard import negocio as N
    hoy = ahora.date()
    d = N.calcular_periodo(libro, ahora, hoy - dt.timedelta(days=7), hoy - dt.timedelta(days=1))
    filas = []
    for o in d["ofertas"]:
        if o.get("estado") != "activa":
            continue
        rn, rm = o.get("roas_neto"), o.get("roas_meta")
        if o.get("fase") != "post-lanzamiento":
            regla = "test (corte a 1,5 tickets)"
        elif isinstance(rm, (int, float)) and rm > 2.5:
            regla = "surfeo cada 3 h"
        elif isinstance(rm, (int, float)) and rm >= 1.75:
            regla = "+30 % cada 24 h"
        else:
            regla = "mantener (R4 corta si pierde)"
        filas.append({"oferta": o["nombre"], "mercado": o.get("mercado"), "gasto_7d": o.get("gasto_meta"), "neto_7d": o.get("neto"),
                      "roas_neto_7d": rn, "roas_meta_7d": rm, "regla": regla})
    return sorted(filas, key=lambda f: -(f["roas_neto_7d"] or 0))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("que", nargs="?", default="todo", choices=["kie", "comisiones", "cartera", "todo", "anotar", "gemini-saldo"])
    ap.add_argument("--usd", type=float, help="gemini-saldo: saldo que muestra AI Studio → Billing, en USD")
    ap.add_argument("--servicio"); ap.add_argument("--estado", choices=["ok", "aviso", "error"]); ap.add_argument("--detalle")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sin-red", action="store_true")
    a = ap.parse_args(argv)
    ahora = dt.datetime.now(dt.timezone.utc)
    if a.que == "gemini-saldo":   # el dueño (o el agente con su sesión de AI Studio) lo mira y lo anota
        if a.usd is None or a.usd < 0:
            print("falta --usd con el saldo de AI Studio", file=sys.stderr)
            return 2
        try:
            previo = json.loads(ESTADO_SERVICIOS.read_text(encoding="utf-8")).get("gemini") or {}
        except (OSError, ValueError):
            previo = {}
        previo.update({"saldo_usd": round(a.usd, 2), "saldo_leido": ahora.date().isoformat()})
        est, avisos = estado_gemini(previo.get("estado") != "error", previo.get("detalle", "la voz responde").split(" · ")[0], previo, ahora.date())
        anotar_servicio("gemini", est)
        print(f"gemini: {est['estado']} · {est['detalle']}")
        for x in avisos:
            print(("URGENTE · " if x["urgente"] else "") + x["mensaje"])
        return 0
    if a.que == "anotar":
        anotar_servicio(a.servicio, {"estado": a.estado, "detalle": (a.detalle or "")[:200]})
        print(f"{a.servicio}: {a.estado}")
        return 0
    libro = json.loads(LIBRO.read_text(encoding="utf-8"))
    out: dict = {"avisos": []}
    if a.que in ("kie", "todo") and not a.sin_red:
        s = saldo_kie()
        out["kie"] = s
        anotar_servicio("kie", {"estado": "error" if s is None or s < KIE_MINIMO / 2 else ("aviso" if s < KIE_MINIMO else "ok"),
                                "detalle": "sin lectura" if s is None else f"{s:,.0f} créditos".replace(",", ".")})
        g_ok, g_det = gemini_ok()
        try:
            previo = json.loads(ESTADO_SERVICIOS.read_text(encoding="utf-8")).get("gemini") or {}
        except (OSError, ValueError):
            previo = {}
        g_est, g_avisos = estado_gemini(g_ok, g_det, previo, ahora.date())
        anotar_servicio("gemini", g_est)
        out["avisos"] += g_avisos
        if s is not None:   # el panel muestra el saldo en «Lo que espera tus manos»
            (LIBRO.parent / "kie.json").write_text(json.dumps({"saldo": s, "cuando": ahora.isoformat(timespec="minutes")}), encoding="utf-8")
            # historial de saldos (17-nov): el panel concilia la baja del saldo contra lo registrado en los gasto*.jsonl
            with (LIBRO.parent / "kie_saldos.jsonl").open("a", encoding="utf-8") as h:
                h.write(json.dumps({"cuando": ahora.isoformat(timespec="minutes"), "saldo": s}) + "\n")
        out["avisos"] += chequear_kie(s)
    if a.que == "todo":   # 17-nov: el barrido de costos de producción pone al día produccion.barrido del libro (Kie, Gemini, voces)
        import subprocess  # noqa: PLC0415
        r = subprocess.run([sys.executable, str(Path(__file__).with_name("barrido_costos.py")), "--aplicar", "--json"],
                           capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            out["avisos"].append({"clave": "barrido-costos", "urgente": False, "mensaje": "El barrido de costos de producción falló: " + (r.stderr or "")[-200:]})
        else:
            try:
                b = json.loads(r.stdout)
                faltan = [f["test"] for f in b["ofertas"] if f.get("libro_vacio")]
                out["costos"] = {"total_usd": b["totales"]["total_usd"], "kie_creditos": b["totales"]["kie_creditos"], "sin_carga_manual": faltan}
            except (ValueError, KeyError):
                pass
    if a.que in ("comisiones", "todo"):
        out["avisos"] += chequear_comisiones(libro, ahora.date())
    if a.que in ("cartera", "todo"):
        out["cartera"] = cartera(libro, ahora)
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        if "kie" in out:
            print(f"Kie: {out['kie']}")
        for x in out["avisos"]:
            print(("URGENTE · " if x["urgente"] else "") + x["mensaje"])
        for f in out.get("cartera", []):
            print(f"{f['oferta']}: ROAS neto 7 d {f['roas_neto_7d']} · {f['regla']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
