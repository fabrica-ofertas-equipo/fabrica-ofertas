// Lógica pura de la tienda propia (sin red, probada con node --test).

export const SLUG = /^[a-z0-9][a-z0-9-]{0,58}[a-z0-9]$/;

export function fechaDia(d, zona = "UTC") {
  return new Intl.DateTimeFormat("en-CA", { timeZone: zona, year: "numeric", month: "2-digit", day: "2-digit" }).format(d);
}

export function formatoPrecio(valor, moneda, idioma = "es") {
  if (valor === null || valor === undefined || Number.isNaN(Number(valor))) return "";
  try {
    return new Intl.NumberFormat(idioma, { style: "currency", currency: moneda, maximumFractionDigits: Number(valor) % 1 ? 2 : 0 }).format(Number(valor));
  } catch {
    return `${valor} ${moneda}`;
  }
}

function escapar(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
}

// Medición: un pedido aparte (/_m/...) para que una prueba automática pueda bloquearlo y no ensuciar el embudo.
export function scriptMedicion(slug, tipo, pixel) {
  const px = pixel && /^\d{5,20}$/.test(pixel)
    ? `!function(f,b,e,v,n,t,s){if(f.fbq)return;n=f.fbq=function(){n.callMethod?n.callMethod.apply(n,arguments):n.queue.push(arguments)};if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';n.queue=[];t=b.createElement(e);t.async=!0;t.src=v;s=b.getElementsByTagName(e)[0];s.parentNode.insertBefore(t,s)}(window,document,'script','https://connect.facebook.net/en_US/fbevents.js');fbq('init','${pixel}');fbq('track','${tipo === "checkout" ? "InitiateCheckout" : "PageView"}');`
    : "";
  return `<script>${px}try{navigator.sendBeacon("/_m/${slug}/${tipo}")}catch(e){}</script>`;
}

export function renderLanding(t) {
  const html = String(t.html || "")
    .replaceAll("{{price}}", escapar(formatoPrecio(t.precio, t.moneda, t.idioma)))
    .replaceAll("{{original_price}}", escapar(formatoPrecio(t.precio_original, t.moneda, t.idioma)))
    .replaceAll("{{checkout_url}}", `/${t.slug}/checkout`);
  const med = scriptMedicion(t.slug, "landing", t.pixel);
  return html.includes("</body>") ? html.replace("</body>", `${med}</body>`) : html + med;
}

export function renderCheckout(t) {
  const bump = t.bump ? JSON.parse(t.bump) : null;
  const precio = formatoPrecio(t.precio, t.moneda, t.idioma);
  const caja = bump
    ? `<label class="bump"><input type="checkbox" name="bump" value="1"> <b>${escapar(bump.nombre)}</b> · +${escapar(formatoPrecio(bump.precio, t.moneda, t.idioma))}</label>`
    : "";
  return `<!doctype html><html lang="${escapar(t.idioma)}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escapar(t.nombre)}</title><style>body{font-family:system-ui,sans-serif;max-width:480px;margin:40px auto;padding:0 16px}
.bump{display:block;border:2px dashed #e0a800;background:#fff8e1;padding:14px;border-radius:8px;margin:18px 0}
button{width:100%;padding:16px;font-size:18px;border:0;border-radius:8px;background:#16a34a;color:#fff;cursor:pointer}</style></head>
<body><h1>${escapar(t.nombre)}</h1><p class="precio">${escapar(precio)}</p>
<form method="post" action="/${t.slug}/pagar">${caja}<button type="submit">Pagar ${escapar(precio)}</button></form>
${scriptMedicion(t.slug, "checkout", t.pixel)}</body></html>`;
}

const CENTAVOS_CERO = new Set(["BIF", "CLP", "DJF", "GNF", "JPY", "KMF", "KRW", "MGA", "PYG", "RWF", "UGX", "VND", "VUV", "XAF", "XOF", "XPF"]);

export function aCentavos(valor, moneda) {
  return CENTAVOS_CERO.has(moneda.toUpperCase()) ? Math.round(Number(valor)) : Math.round(Number(valor) * 100);
}

// Cuerpo application/x-www-form-urlencoded para POST /v1/checkout/sessions de Stripe.
export function cuerpoSesionStripe(t, { conBump, origen }) {
  const p = new URLSearchParams();
  const linea = (i, nombre, valor) => {
    p.set(`line_items[${i}][quantity]`, "1");
    p.set(`line_items[${i}][price_data][currency]`, t.moneda.toLowerCase());
    p.set(`line_items[${i}][price_data][unit_amount]`, String(aCentavos(valor, t.moneda)));
    p.set(`line_items[${i}][price_data][product_data][name]`, nombre);
  };
  linea(0, t.nombre, t.precio);
  const bump = conBump && t.bump ? JSON.parse(t.bump) : null;
  if (bump) linea(1, bump.nombre, bump.precio);
  p.set("mode", "payment");
  p.set("locale", "auto");
  p.set("success_url", `${origen}/${t.slug}/gracias?s={CHECKOUT_SESSION_ID}`);
  p.set("cancel_url", `${origen}/${t.slug}/`);
  p.set("metadata[tienda]", t.slug);
  p.set("metadata[bump]", bump ? "1" : "0");
  p.set("after_expiration[recovery][enabled]", "true");
  return p;
}

const enc = new TextEncoder();

async function hmacHex(secreto, texto) {
  const clave = await crypto.subtle.importKey("raw", enc.encode(secreto), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const firma = await crypto.subtle.sign("HMAC", clave, enc.encode(texto));
  return [...new Uint8Array(firma)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Firma de Stripe: cabecera «t=<ts>,v1=<hex>»; v1 = HMAC-SHA256(secreto, `${t}.${cuerpo}`). Tolerancia 5 min.
export async function firmaStripeValida(cuerpo, cabecera, secreto, ahoraSeg, tolerancia = 300) {
  if (!cabecera || !secreto) return false;
  const partes = Object.fromEntries(cabecera.split(",").map((x) => x.split("=", 2)).filter((x) => x.length === 2));
  const ts = Number(partes.t);
  if (!Number.isFinite(ts) || Math.abs(ahoraSeg - ts) > tolerancia) return false;
  const esperada = await hmacHex(secreto, `${ts}.${cuerpo}`);
  const v1s = cabecera.split(",").filter((x) => x.startsWith("v1=")).map((x) => x.slice(3));
  return v1s.some((v) => v.length === esperada.length && v === esperada);
}

// Evento de Stripe → qué guardar. Devuelve {tipo:"venta"|"carrito"|"ignorar", ...}.
export function interpretarEvento(ev) {
  const s = ev?.data?.object || {};
  const tienda = s.metadata?.tienda;
  if (!tienda || !SLUG.test(tienda)) return { tipo: "ignorar" };
  if (ev.type === "checkout.session.completed" && s.payment_status === "paid") {
    const moneda = String(s.currency || "usd").toUpperCase();
    const total = CENTAVOS_CERO.has(moneda) ? Number(s.amount_total || 0) : Number(s.amount_total || 0) / 100;
    return {
      tipo: "venta", orden: s.id, tienda, total, moneda, con_bump: s.metadata?.bump === "1" ? 1 : 0,
      email: s.customer_details?.email || s.customer_email || null, fecha: new Date((s.created || ev.created) * 1000).toISOString(),
    };
  }
  if (ev.type === "checkout.session.expired") {
    return {
      tipo: "carrito", sesion: s.id, tienda, email: s.customer_details?.email || s.customer_email || null,
      recuperar_url: s.after_expiration?.recovery?.url || null, fecha: new Date((ev.created || 0) * 1000).toISOString(),
    };
  }
  return { tipo: "ignorar" };
}

export function correoEntrega(t, venta, bump) {
  const enlaces = [`<p><a href="${escapar(t.entregable_url)}">${escapar(t.nombre)}</a></p>`];
  if (venta.con_bump && bump?.entregable_url) enlaces.push(`<p><a href="${escapar(bump.entregable_url)}">${escapar(bump.nombre)}</a></p>`);
  return {
    asunto: t.nombre,
    html: `<p>¡Gracias por tu compra!</p>${enlaces.join("")}<p>${t.correo_soporte ? `Soporte: ${escapar(t.correo_soporte)}` : ""}</p>`,
  };
}

export function autorizado(req, token) {
  const h = req.headers.get("authorization") || "";
  return Boolean(token) && h === `Bearer ${token}`;
}
