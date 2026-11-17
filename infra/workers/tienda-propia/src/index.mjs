// Worker «fabrica-tienda»: rutas de la tienda propia. La lógica está en logica.mjs (probada sin red).
//   GET  /<slug>/            landing            GET  /<slug>/checkout   checkout con bump
//   POST /<slug>/pagar       → sesión de Stripe  GET  /<slug>/gracias    página de gracias
//   POST /_m/<slug>/<tipo>   medición (landing | checkout); una prueba automática la bloquea
//   POST /stripe/webhook     ventas y carritos
//   API (Bearer API_TOKEN): GET /api/tiendas · PUT /api/tiendas/<slug> · GET /api/ventas · GET /api/estadisticas
//                           GET /api/cobro · GET /api/carritos · POST /api/repesca
import {
  SLUG, autorizado, correoEntrega, cuerpoSesionStripe, fechaDia, firmaStripeValida, interpretarEvento, renderCheckout, renderLanding,
} from "./logica.mjs";

const json = (d, status = 200) => new Response(JSON.stringify(d), { status, headers: { "content-type": "application/json" } });
const html = (h, status = 200) => new Response(h, { status, headers: { "content-type": "text/html; charset=utf-8" } });

async function tienda(env, slug) {
  if (!SLUG.test(slug)) return null;
  return env.DB.prepare("SELECT * FROM tiendas WHERE slug = ? AND archivada = 0").bind(slug).first();
}

async function evento(env, slug, tipo) {
  const ahora = new Date();
  await env.DB.prepare("INSERT INTO eventos (tienda, tipo, fecha, cuando) VALUES (?, ?, ?, ?)")
    .bind(slug, tipo, fechaDia(ahora, env.ZONA || "UTC"), ahora.toISOString()).run();
}

async function enviarCorreo(env, para, { asunto, html: cuerpo }) {
  if (!env.RESEND_KEY || !para) return false;
  const r = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: { authorization: `Bearer ${env.RESEND_KEY}`, "content-type": "application/json" },
    body: JSON.stringify({ from: env.REMITENTE, to: [para], subject: asunto, html: cuerpo }),
  });
  return r.ok;
}

async function webhook(req, env) {
  const cuerpo = await req.text();
  const ok = await firmaStripeValida(cuerpo, req.headers.get("stripe-signature"), env.STRIPE_WEBHOOK_SECRET, Math.floor(Date.now() / 1000));
  if (!ok) return json({ ok: false, codigo: "firma_invalida" }, 400);
  const e = interpretarEvento(JSON.parse(cuerpo));
  if (e.tipo === "venta") {
    const nueva = await env.DB.prepare(
      "INSERT OR IGNORE INTO ventas (orden, tienda, total, moneda, con_bump, fecha) VALUES (?, ?, ?, ?, ?, ?)",
    ).bind(e.orden, e.tienda, e.total, e.moneda, e.con_bump, e.fecha).run();
    if (nueva.meta?.changes) {
      const t = await env.DB.prepare("SELECT * FROM tiendas WHERE slug = ?").bind(e.tienda).first();
      if (t && (await enviarCorreo(env, e.email, correoEntrega(t, e, t.bump ? JSON.parse(t.bump) : null)))) {
        await env.DB.prepare("UPDATE ventas SET entregada = 1 WHERE orden = ?").bind(e.orden).run();
      }
    }
  } else if (e.tipo === "carrito" && e.email) {
    await env.DB.prepare("INSERT OR IGNORE INTO carritos (sesion, tienda, email, recuperar_url, fecha) VALUES (?, ?, ?, ?, ?)")
      .bind(e.sesion, e.tienda, e.email, e.recuperar_url, e.fecha).run();
  }
  return json({ ok: true });
}

const CAMPOS = ["nombre", "html", "precio", "precio_original", "moneda", "idioma", "entregable_url", "bump", "pixel", "correo_soporte", "archivada"];

async function api(req, env, url, partes) {
  if (!autorizado(req, env.API_TOKEN)) return json({ ok: false, codigo: "sin_permiso" }, 401);
  const q = url.searchParams;
  const recurso = partes[1];
  if (recurso === "tiendas" && req.method === "GET") {
    const { results } = await env.DB.prepare("SELECT slug, nombre, precio, moneda, idioma, archivada FROM tiendas").all();
    return json({ tiendas: results });
  }
  if (recurso === "tiendas" && req.method === "PUT" && partes[2]) {
    const slug = partes[2];
    if (!SLUG.test(slug)) return json({ ok: false, codigo: "slug_invalido" }, 400);
    const d = await req.json();
    if (d.bump && typeof d.bump === "object") d.bump = JSON.stringify(d.bump);
    const previa = await env.DB.prepare("SELECT * FROM tiendas WHERE slug = ?").bind(slug).first();
    const fila = { ...(previa || { moneda: "USD", idioma: "es", html: "", archivada: 0 }), ...Object.fromEntries(CAMPOS.filter((k) => k in d).map((k) => [k, d[k]])) };
    if (!fila.nombre || fila.precio === undefined) return json({ ok: false, codigo: "faltan_nombre_o_precio" }, 400);
    await env.DB.prepare(
      `INSERT INTO tiendas (slug, ${CAMPOS.join(", ")}, creada) VALUES (?, ${CAMPOS.map(() => "?").join(", ")}, ?)
       ON CONFLICT(slug) DO UPDATE SET ${CAMPOS.map((k) => `${k} = excluded.${k}`).join(", ")}`,
    ).bind(slug, ...CAMPOS.map((k) => fila[k] ?? null), previa?.creada || new Date().toISOString()).run();
    return json({ ok: true, slug, url: `${url.origin}/${slug}/` });
  }
  if (recurso === "ventas") {
    const { results } = await env.DB.prepare(
      "SELECT orden, fecha, total, moneda, post_compra, estado, con_bump FROM ventas WHERE tienda = ? AND substr(fecha,1,10) BETWEEN ? AND ? ORDER BY fecha",
    ).bind(q.get("tienda"), q.get("desde") || "0000-00-00", q.get("hasta") || "9999-99-99").all();
    return json({ tienda: q.get("tienda"), ventas: results });
  }
  if (recurso === "estadisticas") {
    const t = q.get("tienda");
    const f = q.get("fecha");
    const { results } = await env.DB.prepare("SELECT tipo, COUNT(*) n FROM eventos WHERE tienda = ? AND fecha = ? GROUP BY tipo").bind(t, f).all();
    const c = await env.DB.prepare("SELECT COUNT(*) n FROM ventas WHERE tienda = ? AND substr(fecha,1,10) = ? AND estado = 'aprobada' AND post_compra = 0").bind(t, f).first();
    const por = Object.fromEntries(results.map((r) => [r.tipo, r.n]));
    return json({ tienda: t, fecha: f, landing: por.landing || 0, checkout: por.checkout || 0, compras: c?.n || 0 });
  }
  if (recurso === "cobro") return json({ puede_cobrar: Boolean(env.STRIPE_SECRET && env.STRIPE_WEBHOOK_SECRET), metodos: env.STRIPE_SECRET ? ["stripe"] : [] });
  if (recurso === "carritos") {
    const { results } = await env.DB.prepare("SELECT sesion, tienda, fecha, avisado FROM carritos WHERE tienda = ? ORDER BY fecha DESC LIMIT 200").bind(q.get("tienda")).all();
    return json({ carritos: results });
  }
  if (recurso === "repesca" && req.method === "POST") {
    const { results } = await env.DB.prepare("SELECT c.*, t.nombre, t.correo_soporte FROM carritos c JOIN tiendas t ON t.slug = c.tienda WHERE c.avisado = 0 AND c.recuperar_url IS NOT NULL AND (? IS NULL OR c.tienda = ?)")
      .bind(q.get("tienda"), q.get("tienda")).all();
    let enviados = 0;
    for (const c of results) {
      const ok = await enviarCorreo(env, c.email, { asunto: c.nombre, html: `<p>Tu compra quedó a mitad de camino.</p><p><a href="${c.recuperar_url}">Terminar la compra</a></p>` });
      if (ok) {
        enviados += 1;
        await env.DB.prepare("UPDATE carritos SET avisado = 1 WHERE sesion = ?").bind(c.sesion).run();
      }
    }
    return json({ ok: true, enviados });
  }
  return json({ ok: false, codigo: "no_existe" }, 404);
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    const partes = url.pathname.split("/").filter(Boolean);
    if (partes[0] === "api") return api(req, env, url, partes);
    if (partes[0] === "stripe" && partes[1] === "webhook" && req.method === "POST") return webhook(req, env);
    if (partes[0] === "_m" && req.method === "POST" && ["landing", "checkout"].includes(partes[2])) {
      if (await tienda(env, partes[1])) await evento(env, partes[1], partes[2]);
      return new Response(null, { status: 204 });
    }
    const t = partes[0] ? await tienda(env, partes[0]) : null;
    if (!t) return html("<h1>404</h1>", 404);
    const pagina = partes[1] || "";
    if (pagina === "" && req.method === "GET") {
      if (!url.pathname.endsWith("/")) return Response.redirect(`${url.origin}/${t.slug}/${url.search}`, 301);
      return html(renderLanding(t));
    }
    if (pagina === "checkout") return html(renderCheckout(t));
    if (pagina === "pagar" && req.method === "POST") {
      const form = await req.formData();
      const r = await fetch("https://api.stripe.com/v1/checkout/sessions", {
        method: "POST",
        headers: { authorization: `Bearer ${env.STRIPE_SECRET}`, "content-type": "application/x-www-form-urlencoded" },
        body: cuerpoSesionStripe(t, { conBump: form.get("bump") === "1", origen: url.origin }),
      });
      const s = await r.json();
      if (!r.ok || !s.url) return html("<p>No se pudo iniciar el pago. Probá de nuevo en un minuto.</p>", 502);
      return Response.redirect(s.url, 303);
    }
    if (pagina === "gracias") return html(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><h1>¡Gracias!</h1><p>Te mandamos ${t.nombre} a tu correo.</p>`);
    return html("<h1>404</h1>", 404);
  },
};
