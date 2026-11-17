// logica.mjs — lógica pura del worker «vivo» (sin red ni base: se prueba con node --test).
//
// Pedido del dueño (2026-11-14): «el dashboard no es en tiempo real en muchos lados… quiero algo que funcione robusto y lo más
// automático posible», opción 2: una capa en la nube que lee Meta cada 5 minutos y recibe las ventas de Impultienda las 24 horas,
// aunque la Mac esté apagada. El panel de la Mac la sincroniza cada 5 minutos.
//
// Ventas: webhooks salientes de Impultienda (https://impultienda.ar/docs/webhooks): POST firmado, cabecera
// X-Impultienda-Signature = HMAC-SHA256 hex de "{X-Impultienda-Timestamp}.{cuerpo crudo}", timestamps de más de 5 minutos se
// rechazan, los reintentos reenvían el mismo payload.id (idempotencia). NUNCA se guardan datos del comprador (correo, nombre,
// teléfono, documento): solo la orden, montos, país, medio de pago, tienda y UTMs.

const enc = new TextEncoder();
export const TOLERANCIA_SEG = 300;

export async function hmacHex(secreto, mensaje) {
  const clave = await crypto.subtle.importKey("raw", enc.encode(secreto), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const firma = await crypto.subtle.sign("HMAC", clave, enc.encode(mensaje));
  return Array.from(new Uint8Array(firma)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function igualesTiempoConstante(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

/** {ok, motivo}: firma correcta y timestamp dentro de la tolerancia. `ahoraSeg` se inyecta para las pruebas. */
export async function verificarFirma({ secreto, firma, timestamp, cuerpo, ahoraSeg }) {
  if (!secreto) return { ok: false, motivo: "falta_secreto" };
  const ts = Number(timestamp);
  if (!Number.isFinite(ts)) return { ok: false, motivo: "timestamp_invalido" };
  if (Math.abs(ahoraSeg - ts) > TOLERANCIA_SEG) return { ok: false, motivo: "timestamp_viejo" };
  const esperada = await hmacHex(secreto, `${timestamp}.${cuerpo}`);
  return igualesTiempoConstante(String(firma || "").toLowerCase(), esperada) ? { ok: true } : { ok: false, motivo: "firma_invalida" };
}

const txt = (x, n = 200) => (typeof x === "string" ? x.slice(0, n) : x == null ? null : String(x).slice(0, n));
const num = (x) => (typeof x === "number" && Number.isFinite(x) ? x : x != null && x !== "" && Number.isFinite(Number(x)) ? Number(x) : null);

/** Fila de venta SIN datos personales a partir del payload del webhook. null si no es un evento de venta. */
export function ventaDePayload(p) {
  if (!p || typeof p !== "object" || !p.data || typeof p.data !== "object") return null;
  const d = p.data;
  const t = d.tracking && typeof d.tracking === "object" ? d.tracking : {};
  const s = d.store && typeof d.store === "object" ? d.store : {};
  const prueba = p.test === true || d.test === true || String(d.order_id || "").startsWith("TEST-");
  return {
    entrega_id: txt(p.id, 80),
    evento: txt(p.event, 40),
    recibido: txt(p.created_at, 40),
    orden_id: txt(d.order_id, 80),
    orden: num(d.order_number),
    estado: txt(d.status, 30),
    total: num(d.total),
    moneda: txt(d.currency, 8),
    total_comprador: num(d.buyer_total),
    moneda_comprador: txt(d.buyer_currency, 8),
    pais: txt(d.buyer_country, 4),
    medio: txt(d.payment_method, 30),
    post_compra: d.is_post_purchase === true ? 1 : 0,
    orden_padre: txt(d.parent_order_id, 80),
    creada: txt(d.order_created_at, 40),
    tienda: txt(s.subdomain, 80),
    tienda_nombre: txt(s.name, 120),
    utm_campaign: txt(t.utm_campaign),
    utm_id: txt(t.utm_id, 40),
    utm_adset: txt(t.utm_adset),
    utm_content: txt(t.utm_content),
    items: JSON.stringify((Array.isArray(d.items) ? d.items : []).slice(0, 20).map((i) => ({ tipo: txt(i && i.type, 20), nombre: txt(i && i.name, 120), precio: num(i && i.price) }))),
    prueba: prueba ? 1 : 0,
  };
}

// ───────────────────────── Meta ─────────────────────────

const COMPRA = ["omni_purchase", "purchase", "offsite_conversion.fb_pixel_purchase"];
const CHECKOUT = ["omni_initiated_checkout", "initiate_checkout", "offsite_conversion.fb_pixel_initiate_checkout"];
const VISTA = ["omni_landing_page_view", "landing_page_view"];

/** Primer tipo de la lista que aparezca (Meta repite la misma compra en varios tipos: nunca se suman). */
export function accion(lista, tipos) {
  if (!Array.isArray(lista)) return 0;
  for (const t of tipos) {
    const a = lista.find((x) => x && x.action_type === t);
    if (a) return Number(a.value) || 0;
  }
  return 0;
}

/** Filas de meta_dia a partir de la respuesta de /insights (level=campaign, time_increment=1). */
export function filasMeta(datos, leido) {
  return (Array.isArray(datos) ? datos : []).filter((f) => f && f.campaign_id && f.date_start).map((f) => ({
    fecha: String(f.date_start).slice(0, 10),
    campana: String(f.campaign_id),
    nombre: txt(f.campaign_name),
    gasto: Number(f.spend) || 0,
    impresiones: Number(f.impressions) || 0,
    clics: Number(f.inline_link_clicks) || 0,
    visitas: accion(f.actions, VISTA),
    pagos_iniciados: accion(f.actions, CHECKOUT),
    compras: accion(f.actions, COMPRA),
    valor_compras: accion(f.action_values, COMPRA),
    leido,
  }));
}

/** «AAAA-MM-DD» de hoy y de ayer en la zona de la cuenta de Meta. */
export function diasCuenta(ahora, zona) {
  const fmt = (d) => new Intl.DateTimeFormat("en-CA", { timeZone: zona, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
  return { hoy: fmt(ahora), ayer: fmt(new Date(ahora.getTime() - 86400000)) };
}

/** Comparación del token de lectura del panel (Authorization: Bearer …). */
export function autorizado(cabecera, esperado) {
  if (!esperado) return false;
  const m = /^Bearer\s+(.+)$/.exec(String(cabecera || ""));
  return Boolean(m) && igualesTiempoConstante(m[1].trim(), esperado);
}

// ───────────────────────── Meta por anuncio (dueño, 15-nov: «el top 20 de creativos con todos sus KPIs») ─────────────────────────

const VIDEO_3S = ["video_view"];
const videoAccion = (lista) => (Array.isArray(lista) ? lista.reduce((s, x) => s + (Number(x && x.value) || 0), 0) : 0);

/** Filas por anuncio y día a partir de /insights (level=ad, time_increment=1). Solo los días con impresiones o gasto. */
export function filasAnuncio(datos) {
  return (Array.isArray(datos) ? datos : []).filter((f) => f && f.ad_id && f.date_start && (Number(f.spend) > 0 || Number(f.impressions) > 0)).map((f) => ({
    fecha: String(f.date_start).slice(0, 10),
    id: String(f.ad_id),
    nombre: txt(f.ad_name),
    conjunto_id: f.adset_id ? String(f.adset_id) : null,
    conjunto: txt(f.adset_name),
    campana: f.campaign_id ? String(f.campaign_id) : null,
    gasto: Number(f.spend) || 0,
    impresiones: Number(f.impressions) || 0,
    alcance: Number(f.reach) || 0,
    clics: Number(f.inline_link_clicks) || 0,
    visitas: accion(f.actions, VISTA),
    pagos_iniciados: accion(f.actions, CHECKOUT),
    compras: accion(f.actions, COMPRA),
    valor_compras: accion(f.action_values, COMPRA),
    vistas_3s: accion(f.actions, VIDEO_3S),
    video_p25: videoAccion(f.video_p25_watched_actions),
    video_p50: videoAccion(f.video_p50_watched_actions),
    video_p75: videoAccion(f.video_p75_watched_actions),
    video_p100: videoAccion(f.video_p100_watched_actions),
    thruplay: videoAccion(f.video_thruplay_watched_actions),
  }));
}

/** Datos fijos de cada anuncio (estado, conjunto, campaña y miniatura) a partir de /ads. */
export function datosAnuncios(datos) {
  return (Array.isArray(datos) ? datos : []).filter((a) => a && a.id).map((a) => {
    const c = a.creative && typeof a.creative === "object" ? a.creative : {};
    return {
      id: String(a.id), nombre: txt(a.name), estado: txt(a.effective_status, 40), conjunto_id: a.adset_id ? String(a.adset_id) : null,
      conjunto: txt(a.adset && a.adset.name), campana: a.campaign_id ? String(a.campaign_id) : null,
      creativo_id: c.id ? String(c.id) : null, video_id: c.video_id ? String(c.video_id) : null,
      miniatura: txt(c.thumbnail_url || c.image_url, 2000), creado: txt(a.created_time, 40),
    };
  });
}

/** Agrupa filas por fecha: {fecha: [filas]} (la base guarda un JSON por día para no hacer miles de escrituras). */
export function porFecha(filas) {
  const out = {};
  for (const f of filas) (out[f.fecha] ||= []).push(f);
  return out;
}

/** «AAAA-MM-DD» de hace `n` días en la zona de la cuenta. */
export function diaAtras(ahora, zona, n) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: zona, year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date(ahora.getTime() - n * 86400000));
}

// ───────────────────────── Carritos (15-nov) ─────────────────────────
// Pedido del dueño (2026-11-15): «hacelo con un 33 % y automatizalo para que ocurra en todas las ofertas». La repesca la manda
// Impultienda («Envío masivo» del panel, con el link de descuento); acá solo se anota QUÉ tienda tiene un carrito nuevo para que
// la tarea abra solo esas. Nunca se guarda el email ni otro dato del comprador.

export const EVENTOS_CARRITO = ["order.abandoned", "order.rejected"];

/** Fila de carrito SIN datos personales. null si no es un aviso de carrito. */
export function carritoDePayload(p, verificado) {
  if (!p || typeof p !== "object" || !EVENTOS_CARRITO.includes(p.event) || !p.data || typeof p.data !== "object") return null;
  const d = p.data;
  const s = d.store && typeof d.store === "object" ? d.store : {};
  if (!d.order_id || !s.subdomain) return null;
  const prueba = p.test === true || d.test === true || String(d.order_id).startsWith("TEST-");
  return {
    orden_id: txt(d.order_id, 80), evento: txt(p.event, 40), entrega_id: txt(p.id, 80), recibido: txt(p.created_at, 40),
    creada: txt(d.order_created_at, 40), estado: txt(d.status, 30), total: num(d.total), moneda: txt(d.currency, 8),
    tienda: txt(s.subdomain, 80), verificado: verificado ? 1 : 0, prueba: prueba ? 1 : 0,
  };
}
