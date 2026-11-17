"""Prueba de punta a punta de un funnel publicado en Impultienda, en un iPhone simulado y SIN ensuciar el píxel.

Uso:
  python3 probar_funnel.py <tienda> [<tienda>...] [--pais MX|BR|US|AR|ES|FR|IT|…] [--salida carpeta] [--con-pixel] [--contar-visitas]

Por tienda mide la landing (respuesta del servidor, pintado principal con 4G simulada, peso, imágenes rotas tras
recorrerla entera, enlaces al checkout y si conservan los UTM), recorre las vistas `?v=articulo` y `?v=ficha` si la
landing las tiene (advertorial + ficha), recorre el quiz si lo hay (pantallas `.tela` con `.op` / `.btn`, como el de
Oferta C, o cualquier quiz de tarjetas como el de Oferta G) hasta el resultado, y abre cada checkout
al que apunta la landing: campo de correo, botón de pagar, imagen del producto, formulario de tarjeta, textos `{{…}}`
sin reemplazar y tiempo de carga.

Devuelve por tienda `ok` y `fallas` (lista de textos cortos): es lo que usa verificar_funnel.py (escalar-oferta) a los
10-15 minutos de activar los anuncios. Falla = algo que impide o afea la compra (página caída, sin enlaces al checkout,
checkout sin correo o sin botón de pagar, imagen del producto rota, imágenes rotas en la landing, `{{…}}` a la vista).

Por defecto la prueba NO DEJA RASTRO (lista PIXEL + IMPULTIENDA + MEDICION, abajo):
- el píxel de Meta del navegador (facebook.com/tr, connect.facebook.net);
- las visitas de Impultienda (rest/v1/visits: estadísticas, landing→checkout, abandono real) y los «visitantes en vivo»;
- la API de conversiones de Impultienda (functions/v1/meta-track-event), que manda PageView, InitiateCheckout y los
  eventos del quiz a Meta DESDE EL SERVIDOR: hasta el 14-nov la prueba bloqueaba el píxel pero esto salía igual;
- Clarity y la medición de Whop.
El 12-nov las pruebas sin bloquear sumaron 6 inicios de pago; el 14-nov una revisión a mano con el navegador integrado
volvió a sumar visitas y un inicio de pago por tienda: las revisiones van con este script, nunca con el navegador.
Con --con-pixel deja salir el píxel y lista los eventos que habrían salido (solo para comprobar el píxel a propósito);
con --contar-visitas deja salir las visitas y la API de conversiones de Impultienda (para comprobar el tracking).
Cada resultado trae `bloqueadas` (cuántas peticiones se frenaron, por tipo): si `impultienda` da 0 en una landing, el
tracking de Impultienda cambió de dirección y hay que actualizar la lista.

El precio y el idioma del checkout los decide el servidor por el país de la IP: desde Argentina se ve en USD y en
español aunque el mercado sea otro (no es una falla). Para ver lo que ve el comprador usar la vista previa «Ver como
otro país» de Diseño de checkout en el panel (fragmentos-navegador.md).

Historial:
- 14-nov: las tiendas de Francia e Italia (Oferta H, Oferta I), duplicadas de las de España, salieron con la
  imagen del producto del checkout apuntando a un archivo que no existía (la copia no trae el archivo): el checkout
  mostraba el texto alternativo en vez de la foto. Ahora se comprueba cada imagen del checkout.
"""
import json, sys, time
from pathlib import Path
# Capa de tienda (tienda/): la plataforma donde se vende se elige en tienda/config.json; Impultienda por defecto.
_RAIZ_T = next(p for p in Path(__file__).resolve().parents if (p / "tienda" / "__init__.py").is_file())
if str(_RAIZ_T) not in sys.path:
    sys.path.insert(0, str(_RAIZ_T))
import tienda as _tienda  # noqa: E402
TIENDA = _tienda.activa()
from playwright.sync_api import sync_playwright

PAISES = {"MX": ("es-MX", "America/Mexico_City"), "BR": ("pt-BR", "America/Sao_Paulo"),
          "US": ("en-US", "America/New_York"), "AR": ("es-AR", "America/Argentina/Buenos_Aires"),
          "ES": ("es-ES", "Europe/Madrid"), "FR": ("fr-FR", "Europe/Paris"), "IT": ("it-IT", "Europe/Rome"),
          "DE": ("de-DE", "Europe/Berlin"), "PT": ("pt-PT", "Europe/Lisbon"), "GB": ("en-GB", "Europe/London"),
          "NL": ("nl-NL", "Europe/Amsterdam"), "PL": ("pl-PL", "Europe/Warsaw"), "CO": ("es-CO", "America/Bogota"),
          "CL": ("es-CL", "America/Santiago"), "PE": ("es-PE", "America/Lima"), "CA": ("en-CA", "America/Toronto"),
          "AU": ("en-AU", "Australia/Sydney"), "SG": ("en-SG", "Asia/Singapore")}
UTM = "?utm_source=prueba&utm_medium=qa&utm_content=QA01"

# Lo que la prueba NO deja salir (dueño, 14-nov: «bloquear lo que detecta Impultienda para no cargar inicio de checkouts falsos»).
# Medido con las peticiones reales de una landing y un checkout de Impultienda (14-nov):
PIXEL = ("facebook.com/tr", "connect.facebook.net")                      # píxel de Meta en el navegador
# Visitas, inicios de pago y eventos que la PLATFORMA cuenta o manda a Meta desde su servidor: los define su adaptador
# (en Impultienda: rest/v1/visits, live_session_ping y functions/v1/meta-track-event; ver tienda/adaptadores/).
IMPULTIENDA = TIENDA.bloqueos_medicion   # nombre histórico: es la lista de la plataforma activa
MEDICION = TIENDA.bloqueos_terceros      # grabaciones y medición de terceros que la plataforma mete (Clarity, Whop…)
# No se bloquea lo que necesita el formulario de pago (api.whop.com, impulpay-prepare, Stripe, hCaptcha).

# Quiz de tarjetas genérico: botones visibles dentro de la página que no son enlaces al checkout.
JS_OPCIONES = """()=>[...document.querySelectorAll('button,[role=button],label,.op,.opcion,.option')]
  .filter(b=>b.offsetParent!==null && b.getBoundingClientRect().height>28 && (b.innerText||'').trim().length>1
    && !b.closest('a[href*="checkout"]') && !/cookie|accept|aceptar|refuser|rifiut/i.test(b.innerText))
  .map((b,i)=>i)"""
JS_HAY_CHECKOUT = "()=>[...document.querySelectorAll('a[href*=\"checkout\"]')].some(a=>a.offsetParent!==null)"


def args():
    a = sys.argv[1:]
    op = {"pais": "MX", "salida": ".", "pixel": False, "contar_visitas": False, "tiendas": []}
    i = 0
    while i < len(a):
        if a[i] == "--pais": op["pais"] = a[i + 1].upper(); i += 2
        elif a[i] == "--salida": op["salida"] = a[i + 1]; i += 2
        elif a[i] == "--con-pixel": op["pixel"] = True; i += 1
        elif a[i] == "--contar-visitas": op["contar_visitas"] = True; i += 1
        else: op["tiendas"].append(a[i]); i += 1
    return op


def recorrer_quiz(pg, maximo=80):
    """Quiz de pantallas `.tela` (Oferta C): hasta el video."""
    n = 0
    for _ in range(maximo):
        if pg.locator("video:visible").count():
            return n
        ops = pg.locator(".tela .op")
        if ops.count():
            ops.first.click(); n += 1; pg.wait_for_timeout(350)
            pr = pg.locator(".tela [data-prox]")
            if pr.count() and pr.first.is_enabled():
                pr.first.click(); pg.wait_for_timeout(350)
            continue
        bt = pg.locator(".tela .btn")
        if bt.count() and bt.first.is_visible():
            bt.first.click(); n += 1; pg.wait_for_timeout(350)
        else:
            pg.wait_for_timeout(600)
    return n


def recorrer_quiz_generico(pg, maximo=20):
    """Quiz de tarjetas sin `.tela` (Oferta G): toca la primera opción hasta que aparece un enlace al checkout."""
    n = 0
    for _ in range(maximo):
        if pg.evaluate(JS_HAY_CHECKOUT):
            return n
        idx = pg.evaluate(JS_OPCIONES)
        if not idx:
            pg.wait_for_timeout(1500)  # «preparando tu resultado…»
            if pg.evaluate(JS_HAY_CHECKOUT) or not pg.evaluate(JS_OPCIONES):
                pg.wait_for_timeout(4000)
                return n
            continue
        pg.evaluate("""()=>{const b=[...document.querySelectorAll('button,[role=button],label,.op,.opcion,.option')]
          .filter(b=>b.offsetParent!==null && b.getBoundingClientRect().height>28 && (b.innerText||'').trim().length>1
            && !b.closest('a[href*="checkout"]') && !/cookie|accept|aceptar|refuser|rifiut/i.test(b.innerText));
          if(b[0]) b[0].click()}""")
        n += 1
        pg.wait_for_timeout(1300)
    return n


def recorrer_pagina(pg):
    """Baja la página entera para que carguen las imágenes diferidas (loading=lazy)."""
    pg.evaluate("()=>document.querySelectorAll('img[loading=lazy]').forEach(i=>i.loading='eager')")
    alto = pg.evaluate("document.body.scrollHeight") or 15000
    for y in range(0, int(alto) + 600, 500):
        pg.evaluate(f"scrollTo(0,{y})"); pg.wait_for_timeout(80)
    pg.wait_for_timeout(2500)


def estado_landing(pg):
    return pg.evaluate("""()=>{const im=[...document.images].filter(i=>i.currentSrc||i.src);
      const a=[...document.querySelectorAll('a[href]')].map(x=>x.href).filter(h=>/checkout/.test(h));
      const txt=document.body.innerText;
      return {imagenes:im.length, imagenes_rotas:im.filter(i=>!(i.complete&&i.naturalWidth>0)).map(i=>(i.currentSrc||i.src).split('/').pop().slice(0,80)).slice(0,8),
        enlaces_checkout:[...new Set(a)], utm_conservado:a.length>0&&a.every(h=>h.includes('utm_content=QA01')),
        llaves_a_la_vista:(txt.match(/\\{\\{[^}]{1,30}\\}\\}/g)||[]).slice(0,5),
        precios:(txt.match(/(MX\\$|R\\$|US\\$|\\$|€|£) ?[0-9][0-9.,]*|[0-9][0-9.,]* ?(€|zł|kr)/g)||[]).slice(0,8),
        texto_visible:txt.length}}""")


def probar_checkout(pg, d, salida):
    t0 = time.time()
    try:
        resp = pg.goto(d + UTM, wait_until="load", timeout=60000)
        status = resp.status if resp else None
    except Exception as e:  # noqa: BLE001
        return {"url": d, "estado": None, "error": str(e)[:120], "fallas": [f"checkout {d} no carga"]}
    pg.wait_for_timeout(4000)
    carga = round(time.time() - t0 - 4, 1)
    recorrer_pagina(pg)
    ck = pg.evaluate("""()=>{const vis=e=>e&&e.offsetParent!==null;
      const correo=[...document.querySelectorAll('input[type=email],input[name*=mail i],input[autocomplete=email]')].some(vis);
      const botones=[...document.querySelectorAll('button,[role=button]')].filter(vis).map(b=>(b.innerText||'').trim()).filter(Boolean);
      const im=[...document.images].filter(i=>(i.currentSrc||i.src)&&!/visa|mastercard|amex|discover|elo|maestro/i.test(i.src));
      const txt=document.body.innerText;
      return {correo, boton_pagar:botones.find(t=>/^(pagar|pay|payer|paga|zahlen|betalen|zapłać|pagar com)/i.test(t)&&t.length<60)||botones.find(t=>/\\d/.test(t)&&t.length<40&&!/\\n/.test(t))||null,
        iframes_pago:document.querySelectorAll('iframe').length,
        imagenes_producto:im.length,
        imagenes_rotas:im.filter(i=>!(i.complete&&i.naturalWidth>0)).map(i=>({alt:(i.alt||'').slice(0,60),src:(i.currentSrc||i.src).split('/').pop().slice(0,80)})).slice(0,6),
        llaves_a_la_vista:(txt.match(/\\{\\{[^}]{1,30}\\}\\}/g)||[]).slice(0,5),
        error_visible:/(404|not found|página no encontrada|algo salió mal|something went wrong)/i.test(txt.slice(0,600)),
        texto:txt.replace(/\\n+/g,' | ').slice(0,500)}}""")
    ck.update(url=d, estado=status, carga_s=carga)
    try:
        pg.screenshot(path=f"{salida}/{d.split('//')[1].split('.')[0]}-checkout.png", full_page=True)
    except Exception:  # noqa: BLE001
        pass
    f = []
    nombre = d.split("//")[1].split(".")[0]
    if status is None or status >= 400 or ck["error_visible"]:
        f.append(f"checkout {nombre}: no carga (estado {status})")
    if not ck["correo"]:
        f.append(f"checkout {nombre}: sin campo de correo visible")
    if not ck["boton_pagar"]:
        f.append(f"checkout {nombre}: sin botón de pagar")
    if ck["imagenes_rotas"]:
        f.append(f"checkout {nombre}: imagen del producto rota ({ck['imagenes_rotas'][0]['alt'] or ck['imagenes_rotas'][0]['src']})")
    if ck["llaves_a_la_vista"]:
        f.append(f"checkout {nombre}: texto sin reemplazar {ck['llaves_a_la_vista']}")
    ck["fallas"] = f
    return ck


def probar(p, tienda, op):
    loc, tz = PAISES.get(op["pais"], ("en-US", "UTC"))
    base = TIENDA.url_landing(tienda)
    salida = op["salida"]
    Path(salida).mkdir(parents=True, exist_ok=True)
    ctx = p.chromium.launch(channel="chrome", headless=True)
    c = ctx.new_context(**p.devices["iPhone 13"], locale=loc, timezone_id=tz)
    pix = []
    bloqueadas = {"pixel": 0, "tienda": 0, "medicion": 0}
    listas = {"medicion": MEDICION}
    if not op.get("pixel"):
        listas["pixel"] = PIXEL
    if not op.get("contar_visitas"):
        listas["tienda"] = IMPULTIENDA
    if op.get("pixel"):
        c.on("request", lambda r: pix.append(r.url.split("ev=")[1].split("&")[0]) if "facebook.com/tr" in r.url and "ev=" in r.url else None)

    def filtro(route):
        u = route.request.url
        for tipo, frag in listas.items():
            if any(f in u for f in frag):
                bloqueadas[tipo] += 1
                return route.abort()
        return route.continue_()
    c.route("**/*", filtro)
    pg = c.new_page()
    cdp = c.new_cdp_session(pg)
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 150, "downloadThroughput": 200_000, "uploadThroughput": 96_000})
    pg.add_init_script("window.__lcp=0;new PerformanceObserver(l=>{for(const e of l.getEntries())window.__lcp=e.startTime}).observe({type:'largest-contentful-paint',buffered:true});")
    fallas = []
    t0 = time.time()
    try:
        resp = pg.goto(base + UTM, wait_until="load", timeout=120000)
        status = resp.status if resp else None
    except Exception as e:  # noqa: BLE001
        ctx.close()
        return {"tienda": tienda, "pais": op["pais"], "ok": False, "bloqueadas": bloqueadas, "fallas": [f"landing {tienda} no carga ({str(e)[:80]})"]}
    r = {"tienda": tienda, "pais": op["pais"], "estado": status, "carga_s": round(time.time() - t0, 1)}
    if status is None or status >= 400:
        fallas.append(f"landing {tienda}: estado {status}")
    pg.wait_for_timeout(2500)
    r.update(pg.evaluate("""()=>{const n=performance.getEntriesByType('navigation')[0];
      return {respuesta_servidor_ms:Math.round(n.responseStart), pintado_principal_ms:Math.round(window.__lcp), alto_px:document.body.scrollHeight}}"""))
    cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
    html = pg.content()
    vistas = [v for v in ("articulo", "ficha") if f"v={v}" in html]
    if pg.locator(".tela").count():
        r["quiz_toques"] = recorrer_quiz(pg)
        pg.wait_for_timeout(3000)
        r["video"] = pg.evaluate("()=>{const v=document.querySelector('video');return v?{dur:Math.round(v.duration),listo:v.readyState,buffer_s:v.buffered.length?Math.round(v.buffered.end(0)):0}:null}")
        pg.evaluate("()=>{const o=document.querySelector('[data-oferta]'); if(o) o.hidden=false}")
    elif not vistas and not pg.evaluate(JS_HAY_CHECKOUT) and pg.evaluate(JS_OPCIONES):
        r["quiz_toques"] = recorrer_quiz_generico(pg)
        if not pg.evaluate(JS_HAY_CHECKOUT):
            fallas.append(f"quiz {tienda}: después de {r['quiz_toques']} respuestas no aparece el botón al checkout")
    recorrer_pagina(pg)
    r.update(estado_landing(pg))
    try:
        pg.screenshot(path=f"{salida}/{tienda}-landing.png", full_page=True)
    except Exception:  # noqa: BLE001
        pass
    enlaces = set(r["enlaces_checkout"])
    r["vistas"] = {}
    for v in vistas:
        pg.goto(base + UTM + f"&v={v}", wait_until="load", timeout=60000)
        pg.wait_for_timeout(1500)
        recorrer_pagina(pg)
        e = estado_landing(pg)
        r["vistas"][v] = {k: e[k] for k in ("imagenes", "imagenes_rotas", "llaves_a_la_vista", "precios", "texto_visible")}
        r["vistas"][v]["enlaces_checkout"] = len(e["enlaces_checkout"])
        enlaces |= set(e["enlaces_checkout"])
        if e["imagenes_rotas"]:
            fallas.append(f"landing {tienda} (v={v}): {len(e['imagenes_rotas'])} imagen(es) rota(s)")
        if e["llaves_a_la_vista"]:
            fallas.append(f"landing {tienda} (v={v}): texto sin reemplazar {e['llaves_a_la_vista']}")
    r["enlaces_checkout"] = sorted(enlaces)
    if r["imagenes_rotas"]:
        fallas.append(f"landing {tienda}: {len(r['imagenes_rotas'])} imagen(es) rota(s) ({', '.join(r['imagenes_rotas'][:3])})")
    if r["llaves_a_la_vista"]:
        fallas.append(f"landing {tienda}: texto sin reemplazar {r['llaves_a_la_vista']}")
    if not enlaces:
        fallas.append(f"landing {tienda}: ningún enlace al checkout")
    elif not all("utm_content=QA01" in h for h in enlaces):
        r["aviso_utm"] = "algún enlace al checkout no conserva los UTM"
    destinos = sorted({h.split('?')[0] for h in enlaces}) or [base + "checkout"]
    r["checkouts"] = [probar_checkout(pg, d, salida) for d in destinos]
    for ck in r["checkouts"]:
        fallas += ck.get("fallas") or []
    if op.get("pixel"):
        r["eventos_pixel"] = pix
    r["bloqueadas"] = bloqueadas
    r["fallas"] = fallas
    r["ok"] = not fallas
    ctx.close()
    return r


def probar_varias(tiendas, pais="MX", salida=".", pixel=False, contar_visitas=False):
    op = {"pais": pais.upper(), "salida": salida, "pixel": pixel, "contar_visitas": contar_visitas}
    with sync_playwright() as p:
        return [probar(p, t, op) for t in tiendas]


def main():
    op = args()
    if not op["tiendas"]:
        print(__doc__); sys.exit(1)
    print(json.dumps(probar_varias(op["tiendas"], op["pais"], op["salida"], op["pixel"], op["contar_visitas"]), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
