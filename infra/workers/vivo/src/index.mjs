// index.mjs — worker «fabrica-vivo»: capa en la nube del panel (opción 2 del dueño, 2026-11-14).
//
// Rutas:
//   POST /webhooks/impultienda   avisos de venta de Impultienda (firma HMAC; idempotente por payload.id; sin datos del comprador)
//   GET  /api/estado?desde=AAAA-MM-DD   ventas y gasto de Meta por día para el panel (Authorization: Bearer <LECTURA_TOKEN>)
//   POST /webhooks/impultienda-carritos   avisos order.abandoned / order.rejected (15-nov): solo la tienda y la orden, de pista
//                                para la tarea repesca-carritos. Con IMPULTIENDA_CARRITOS_SECRET cargado se exige la firma; sin él se
//                                guarda marcado verificado=0 (solo puede hacer que la tarea abra una tienda de más: la lista real es la del panel)
//   GET  /api/carritos?desde=ISO carritos recibidos desde esa hora y las órdenes ya aprobadas (Authorization: Bearer <LECTURA_TOKEN>)
//   GET  /salud                  público, sin datos: hora de la última lectura de Meta y del último aviso de venta
//   POST /api/plan-corte         la Mac sube el plan del corte de respaldo (Authorization: Bearer <LECTURA_TOKEN>)
// Cron (*/5): lee Meta (insights por campaña y por día, hoy y ayer en la zona de la cuenta, y el estado de las campañas).
// Corte de RESPALDO (dueño, 17-nov): si la vigilancia de la Mac no late hace más de 30 min, aplica el corte del test con
// esa lectura y PAUSA las campañas pasadas de corte (src/corte.mjs). Nunca activa ni cambia presupuestos. Sin
// META_GESTION_TOKEN solo anota lo que habría pausado.
//
// Secretos (wrangler secret put, los carga el dueño; NUNCA en wrangler.toml): META_ACCESS_TOKEN (ads_read),
// IMPULTIENDA_WEBHOOK_SECRET (clave de firma del endpoint), LECTURA_TOKEN (lo genera el agente para el panel),
// META_GESTION_TOKEN (usuario del sistema con ads_management, SOLO para pausar en el corte de respaldo).

import { decidirCortes, motivoParaNoActuar } from "./corte.mjs";
import { verificarFirma, ventaDePayload, carritoDePayload, filasMeta, diasCuenta, autorizado, filasAnuncio, datosAnuncios, porFecha, diaAtras } from "./logica.mjs";

const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });

// ───────────────────────── almacén (D1) ─────────────────────────

export function almacenD1(db) {
  return {
    async yaVisto(id) {
      return Boolean(await db.prepare("SELECT 1 FROM entregas WHERE id = ?").bind(id).first());
    },
    async guardarVenta(v) {
      const cols = Object.keys(v);
      await db.batch([
        db.prepare(`INSERT INTO ventas (${cols.join(",")}) VALUES (${cols.map(() => "?").join(",")})
                    ON CONFLICT(orden_id, evento) DO UPDATE SET ${cols.filter((c) => c !== "orden_id" && c !== "evento").map((c) => `${c}=excluded.${c}`).join(",")}`).bind(...cols.map((c) => v[c])),
        db.prepare("INSERT OR IGNORE INTO entregas (id, recibido) VALUES (?, ?)").bind(v.entrega_id, new Date().toISOString()),
      ]);
    },
    async guardarMeta(filas, campanas, leido, error) {
      const ops = filas.map((f) => db.prepare(`INSERT INTO meta_dia (fecha,campana,nombre,gasto,impresiones,clics,visitas,pagos_iniciados,compras,valor_compras,leido)
        VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(fecha,campana) DO UPDATE SET nombre=excluded.nombre,gasto=excluded.gasto,impresiones=excluded.impresiones,
        clics=excluded.clics,visitas=excluded.visitas,pagos_iniciados=excluded.pagos_iniciados,compras=excluded.compras,valor_compras=excluded.valor_compras,leido=excluded.leido`)
        .bind(f.fecha, f.campana, f.nombre, f.gasto, f.impresiones, f.clics, f.visitas, f.pagos_iniciados, f.compras, f.valor_compras, f.leido));
      ops.push(db.prepare("INSERT INTO estado (clave, valor) VALUES ('meta', ?) ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor")
        .bind(JSON.stringify({ leido, error: error || null, campanas })));
      await db.batch(ops);
    },
    async guardarAnuncios(dias, anuncios, leido, error) {
      const ops = Object.entries(dias).map(([fecha, filas]) => db.prepare(`INSERT INTO anuncio_dia (fecha, filas, leido) VALUES (?,?,?)
        ON CONFLICT(fecha) DO UPDATE SET filas=excluded.filas, leido=excluded.leido`).bind(fecha, JSON.stringify(filas), leido));
      ops.push(db.prepare("INSERT INTO estado (clave, valor) VALUES ('anuncios', ?) ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor")
        .bind(JSON.stringify({ leido, error: error || null, anuncios })));
      await db.batch(ops);
    },
    async leerAnuncios(desde) {
      const dias = (await db.prepare("SELECT fecha, filas FROM anuncio_dia WHERE fecha >= ? ORDER BY fecha").bind(desde).all()).results || [];
      const est = await db.prepare("SELECT valor FROM estado WHERE clave = 'anuncios'").first();
      const e = est ? JSON.parse(est.valor) : null;
      return { anuncio_dia: dias.flatMap((d) => JSON.parse(d.filas)), anuncio_dias: dias.map((d) => d.fecha), anuncios: e ? e.anuncios : [], anuncios_leido: e ? e.leido : null, anuncios_error: e ? e.error : null };
    },
    async guardarCarrito(c) {
      const cols = Object.keys(c);
      await db.batch([
        db.prepare(`INSERT INTO carritos (${cols.join(",")}) VALUES (${cols.map(() => "?").join(",")})
                    ON CONFLICT(orden_id, evento) DO UPDATE SET ${cols.filter((k) => k !== "orden_id" && k !== "evento").map((k) => `${k}=excluded.${k}`).join(",")}`).bind(...cols.map((k) => c[k])),
        db.prepare("INSERT OR IGNORE INTO entregas (id, recibido) VALUES (?, ?)").bind(c.entrega_id || `${c.orden_id}|${c.evento}`, new Date().toISOString()),
      ]);
    },
    async leerCarritos(desde) {
      const carritos = (await db.prepare("SELECT * FROM carritos WHERE prueba = 0 AND coalesce(recibido, creada) >= ? ORDER BY coalesce(recibido, creada)").bind(desde).all()).results || [];
      const aprobadas = (await db.prepare("SELECT DISTINCT orden_id FROM ventas WHERE evento = 'order.approved' AND coalesce(recibido, creada) >= ?").bind(desde.slice(0, 10)).all()).results || [];
      return { carritos, aprobadas: aprobadas.map((r) => r.orden_id) };
    },
    async guardarPlan(plan) {
      await db.prepare("INSERT INTO estado (clave, valor) VALUES ('plan_corte', ?) ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor").bind(JSON.stringify(plan)).run();
    },
    async leerPlan() {
      const r = await db.prepare("SELECT valor FROM estado WHERE clave = 'plan_corte'").first();
      return r ? JSON.parse(r.valor) : null;
    },
    async guardarRespaldo(info) {
      await db.prepare("INSERT INTO estado (clave, valor) VALUES ('respaldo', ?) ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor").bind(JSON.stringify(info)).run();
    },
    async leerRespaldo() {
      const r = await db.prepare("SELECT valor FROM estado WHERE clave = 'respaldo'").first();
      return r ? JSON.parse(r.valor) : null;
    },
    async cortada(campana, test) {
      const r = await db.prepare("SELECT resultado FROM cortes_nube WHERE campana = ? AND test = ?").bind(campana, test).first();
      return r ? r.resultado : null;
    },
    async guardarCorte(c) {
      await db.prepare(`INSERT INTO cortes_nube (campana, test, cuando, gasto_usd, corte_usd, ventas, resultado, porque) VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(campana, test) DO UPDATE SET cuando=excluded.cuando, gasto_usd=excluded.gasto_usd, corte_usd=excluded.corte_usd,
        ventas=excluded.ventas, resultado=excluded.resultado, porque=excluded.porque`)
        .bind(c.campana, c.test, c.cuando, c.gasto_usd, c.corte_usd, c.ventas, c.resultado, c.porque).run();
    },
    async leerCortes(desde) {
      return (await db.prepare("SELECT * FROM cortes_nube WHERE cuando >= ? ORDER BY cuando").bind(desde).all()).results || [];
    },
    async leer(desde) {
      const ventas = (await db.prepare("SELECT * FROM ventas WHERE prueba = 0 AND substr(coalesce(creada, recibido),1,10) >= ? ORDER BY coalesce(creada, recibido)").bind(desde).all()).results || [];
      const meta = (await db.prepare("SELECT * FROM meta_dia WHERE fecha >= ? ORDER BY fecha, campana").bind(desde).all()).results || [];
      const est = await db.prepare("SELECT valor FROM estado WHERE clave = 'meta'").first();
      const ult = await db.prepare("SELECT max(recibido) AS r FROM entregas").first();
      return { ventas, meta_dia: meta, meta_estado: est ? JSON.parse(est.valor) : null, ultimo_aviso: ult ? ult.r : null };
    },
  };
}

// ───────────────────────── Meta ─────────────────────────

async function graph(env, ruta, params, fetchFn) {
  const q = new URLSearchParams({ ...params, access_token: env.META_ACCESS_TOKEN });
  const r = await fetchFn(`https://graph.facebook.com/${env.GRAPH_VERSION || "v23.0"}/${ruta}?${q}`);
  const d = await r.json().catch(() => ({}));
  if (!r.ok || d.error) throw new Error((d.error && d.error.message) || `HTTP ${r.status}`);
  return d;
}

/** Todas las páginas de una lectura (tope de páginas para no pasar los límites del worker). */
async function graphTodo(env, ruta, params, fetchFn, maxPaginas = 8) {
  let d = await graph(env, ruta, params, fetchFn);
  const datos = [...(d.data || [])];
  for (let i = 1; i < maxPaginas && d.paging && d.paging.next && d.paging.cursors && d.paging.cursors.after; i++) {
    d = await graph(env, ruta, { ...params, after: d.paging.cursors.after }, fetchFn);
    datos.push(...(d.data || []));
  }
  return datos;
}

export const CAMPOS_ANUNCIO = "ad_id,ad_name,adset_id,adset_name,campaign_id,spend,impressions,reach,inline_link_clicks,actions,action_values,"
  + "video_p25_watched_actions,video_p50_watched_actions,video_p75_watched_actions,video_p100_watched_actions,video_thruplay_watched_actions";
export const DIAS_RELLENO = 14;

/** Meta por anuncio: ayer y hoy en cada vuelta; los últimos DIAS_RELLENO días una vez por hora (minuto < 5) o si la base está vacía. */
export async function leerAnunciosMeta(env, almacen, { ahora = new Date(), fetchFn = fetch, relleno = null } = {}) {
  const leido = ahora.toISOString();
  if (!env.META_ACCESS_TOKEN) return { ok: false, error: "falta_token" };
  const cuenta = `act_${env.CUENTA_META}`;
  const zona = env.CUENTA_TZ || "America/Argentina/Buenos_Aires";
  const { hoy, ayer } = diasCuenta(ahora, zona);
  const rellenar = relleno ?? (ahora.getUTCMinutes() < 5 || !(await almacen.leerAnuncios(ayer)).anuncio_dia.length);
  const desde = rellenar ? diaAtras(ahora, zona, DIAS_RELLENO) : ayer;
  try {
    const ins = await graphTodo(env, `${cuenta}/insights`, {
      level: "ad", time_increment: "1", limit: "500", time_range: JSON.stringify({ since: desde, until: hoy }), fields: CAMPOS_ANUNCIO,
    }, fetchFn);
    const filtro = JSON.stringify([{ field: "effective_status", operator: "IN", value: ["ACTIVE", "PAUSED", "ADSET_PAUSED", "CAMPAIGN_PAUSED", "IN_PROCESS", "WITH_ISSUES", "DISAPPROVED", "PENDING_REVIEW", "PREAPPROVED"] }]);
    let ads;
    try {
      ads = await graphTodo(env, `${cuenta}/ads`, { fields: "id,name,effective_status,adset_id,adset{name},campaign_id,created_time,creative.thumbnail_width(320).thumbnail_height(320){id,thumbnail_url,image_url,video_id}", filtering: filtro, limit: "200" }, fetchFn, 6);
    } catch (_) {
      ads = await graphTodo(env, `${cuenta}/ads`, { fields: "id,name,effective_status,adset_id,adset{name},campaign_id,created_time,creative{id,thumbnail_url,image_url,video_id}", filtering: filtro, limit: "200" }, fetchFn, 6);
    }
    const dias = porFecha(filasAnuncio(ins));
    // un día leído sin filas también se guarda (vacío), así no queda una lectura vieja de ese día
    for (let i = 0, d = desde; d <= hoy && i < 40; i++, d = new Date(Date.parse(`${d}T12:00:00Z`) + 86400000).toISOString().slice(0, 10)) dias[d] ||= [];
    await almacen.guardarAnuncios(dias, datosAnuncios(ads), leido, null);
    return { ok: true, filas: ins.length, anuncios: ads.length, desde };
  } catch (e) {
    const prev = await almacen.leerAnuncios("9999-12-31").catch(() => ({ anuncios: [] }));
    await almacen.guardarAnuncios({}, prev.anuncios || [], leido, String(e.message || e).slice(0, 300));
    return { ok: false, error: String(e.message || e) };
  }
}

/** Pausa una campaña con el token de gestión y comprueba que quedó pausada. Devuelve "pausada" o "error: …". */
async function pausarCampana(env, id, fetchFn) {
  const v = env.GRAPH_VERSION || "v23.0";
  const cuerpo = new URLSearchParams({ status: "PAUSED", access_token: env.META_GESTION_TOKEN });
  const r = await fetchFn(`https://graph.facebook.com/${v}/${id}`, { method: "POST", body: cuerpo });
  const d = await r.json().catch(() => ({}));
  if (!r.ok || d.error) return `error: ${((d.error && d.error.message) || `HTTP ${r.status}`).slice(0, 200)}`;
  const q = new URLSearchParams({ fields: "status,effective_status", access_token: env.META_GESTION_TOKEN });
  const c = await (await fetchFn(`https://graph.facebook.com/${v}/${id}?${q}`)).json().catch(() => ({}));
  return c && c.status === "PAUSED" ? "pausada" : `error: quedó ${c && (c.status || (c.error && c.error.message)) || "sin confirmar"}`;
}

/** Corte de respaldo: solo actúa si la vigilancia no late (src/corte.mjs). Nunca prende ni cambia presupuestos. */
export async function respaldoCorte(env, almacen, { ahora = new Date(), fetchFn = fetch } = {}) {
  const plan = await almacen.leerPlan();
  const desde = (plan && [...(plan.tests || []), ...(plan.limites || [])].map((t) => t.desde).filter(Boolean).sort()[0]) || diasCuenta(ahora, env.CUENTA_TZ || "America/Argentina/Buenos_Aires").ayer;
  const d = await almacen.leer(desde);
  const motivo = motivoParaNoActuar(plan, d.meta_estado, ahora);
  const info = { revisado: ahora.toISOString(), actua: !motivo, motivo, con_token: Boolean(env.META_GESTION_TOKEN) };
  if (motivo) { await almacen.guardarRespaldo(info); return { ...info, cortes: [] }; }
  const estados = {};
  for (const c of (d.meta_estado && d.meta_estado.campanas) || []) if (c && c.id) estados[String(c.id)] = c.estado;
  const decisiones = decidirCortes({ plan, metaDia: d.meta_dia, ventas: d.ventas, estados, ahora });
  const hechos = [];
  for (const x of decisiones) {
    const previo = await almacen.cortada(x.campana, x.test);
    if (previo === "pausada") continue;
    const resultado = env.META_GESTION_TOKEN ? await pausarCampana(env, x.campana, fetchFn) : "sin_token";
    const fila = { ...x, cuando: ahora.toISOString(), resultado };
    await almacen.guardarCorte(fila);
    hechos.push(fila);
  }
  await almacen.guardarRespaldo({ ...info, cortes: hechos.length });
  return { ...info, cortes: hechos };
}

export async function leerMeta(env, almacen, { ahora = new Date(), fetchFn = fetch } = {}) {
  const leido = ahora.toISOString();
  if (!env.META_ACCESS_TOKEN) {
    await almacen.guardarMeta([], [], leido, "falta_token");
    return { ok: false, error: "falta_token" };
  }
  const cuenta = `act_${env.CUENTA_META}`;
  const { hoy, ayer } = diasCuenta(ahora, env.CUENTA_TZ || "America/Argentina/Buenos_Aires");
  try {
    const ins = await graph(env, `${cuenta}/insights`, {
      level: "campaign", time_increment: "1", limit: "500", time_range: JSON.stringify({ since: ayer, until: hoy }),
      fields: "campaign_id,campaign_name,spend,impressions,inline_link_clicks,actions,action_values",
    }, fetchFn);
    const camp = await graph(env, `${cuenta}/campaigns`, { fields: "id,name,effective_status,daily_budget", limit: "500" }, fetchFn);
    const campanas = (camp.data || []).map((c) => ({ id: String(c.id), nombre: c.name, estado: c.effective_status, presupuesto_usd: c.daily_budget ? Number(c.daily_budget) / 100 : null }));
    await almacen.guardarMeta(filasMeta(ins.data, leido), campanas, leido, null);
    return { ok: true, filas: (ins.data || []).length };
  } catch (e) {
    // diagnóstico sin exponer el token: Meta dice de qué app es, si sigue vigente y qué permisos tiene
    let diag = null;
    try {
      const d = await graph(env, "debug_token", { input_token: env.META_ACCESS_TOKEN }, fetchFn);
      const x = d.data || {};
      diag = { app_id: x.app_id || null, app: x.application || null, tipo: x.type || null, vigente: x.is_valid ?? null, permisos: x.scopes || [], error: x.error ? x.error.message : null };
    } catch (e2) {
      diag = { error_diagnostico: String(e2.message || e2).slice(0, 200) };
    }
    await almacen.guardarMeta([], [{ diagnostico: diag }], leido, String(e.message || e).slice(0, 300));
    return { ok: false, error: String(e.message || e), diagnostico: diag };
  }
}

// ───────────────────────── HTTP ─────────────────────────

export async function manejarPeticion(req, env, almacen, { ahoraSeg = Math.floor(Date.now() / 1000) } = {}) {
  const url = new URL(req.url);
  if (url.pathname === "/webhooks/impultienda") {
    if (req.method !== "POST") return json({ error: "metodo" }, 405);
    // sin la clave cargada todavía: 503 (no 401), así Impultienda reintenta ~32 h y no se pierde ninguna venta
    if (!env.IMPULTIENDA_WEBHOOK_SECRET) return json({ ok: false, motivo: "falta_secreto" }, 503);
    const cuerpo = await req.text();
    const v = await verificarFirma({ secreto: env.IMPULTIENDA_WEBHOOK_SECRET, firma: req.headers.get("x-impultienda-signature"),
      timestamp: req.headers.get("x-impultienda-timestamp"), cuerpo, ahoraSeg });
    if (!v.ok) return json({ ok: false, motivo: v.motivo }, 401);   // 4xx: Impultienda no reintenta una firma inválida
    let p;
    try { p = JSON.parse(cuerpo); } catch (_) { return json({ ok: false, motivo: "json" }, 400); }
    if (p.id && await almacen.yaVisto(String(p.id))) return json({ ok: true, repetido: true });
    const venta = ventaDePayload(p);
    if (!venta || !venta.orden_id) return json({ ok: true, ignorado: true });   // 2xx: no reintentar algo que no usamos
    await almacen.guardarVenta(venta);
    return json({ ok: true });
  }
  if (url.pathname === "/webhooks/impultienda-carritos") {
    if (req.method !== "POST") return json({ error: "metodo" }, 405);
    const cuerpo = await req.text();
    let verificado = false;
    if (env.IMPULTIENDA_CARRITOS_SECRET) {
      const v = await verificarFirma({ secreto: env.IMPULTIENDA_CARRITOS_SECRET, firma: req.headers.get("x-impultienda-signature"),
        timestamp: req.headers.get("x-impultienda-timestamp"), cuerpo, ahoraSeg });
      if (!v.ok) return json({ ok: false, motivo: v.motivo }, 401);
      verificado = true;
    }
    if (cuerpo.length > 100000) return json({ ok: false, motivo: "grande" }, 413);
    let p;
    try { p = JSON.parse(cuerpo); } catch (_) { return json({ ok: false, motivo: "json" }, 400); }
    if (p.id && await almacen.yaVisto(String(p.id))) return json({ ok: true, repetido: true });
    const c = carritoDePayload(p, verificado);
    if (!c) return json({ ok: true, ignorado: true });
    await almacen.guardarCarrito(c);
    return json({ ok: true });
  }
  if (url.pathname === "/api/plan-corte") {
    if (req.method !== "POST") return json({ error: "metodo" }, 405);
    if (!autorizado(req.headers.get("authorization"), env.LECTURA_TOKEN)) return json({ error: "no_autorizado" }, 401);
    const cuerpo = await req.text();
    if (cuerpo.length > 200000) return json({ ok: false, motivo: "grande" }, 413);
    let plan;
    try { plan = JSON.parse(cuerpo); } catch (_) { return json({ ok: false, motivo: "json" }, 400); }
    if (!plan || !Array.isArray(plan.tests) || (plan.limites != null && !Array.isArray(plan.limites))) return json({ ok: false, motivo: "forma" }, 400);
    plan.recibido = new Date(ahoraSeg * 1000).toISOString();
    await almacen.guardarPlan(plan);
    return json({ ok: true, tests: plan.tests.length, limites: (plan.limites || []).length });
  }
  if (url.pathname === "/api/carritos") {
    if (req.method !== "GET") return json({ error: "metodo" }, 405);
    if (!autorizado(req.headers.get("authorization"), env.LECTURA_TOKEN)) return json({ error: "no_autorizado" }, 401);
    const d = url.searchParams.get("desde") || "";
    const desde = /^\d{4}-\d{2}-\d{2}/.test(d) ? d : new Date((ahoraSeg - 86400) * 1000).toISOString();
    return json({ generado: new Date(ahoraSeg * 1000).toISOString(), desde, ...(await almacen.leerCarritos(desde)) });
  }
  if (url.pathname === "/api/estado") {
    if (req.method !== "GET") return json({ error: "metodo" }, 405);
    if (!autorizado(req.headers.get("authorization"), env.LECTURA_TOKEN)) return json({ error: "no_autorizado" }, 401);
    const desde = /^\d{4}-\d{2}-\d{2}$/.test(url.searchParams.get("desde") || "") ? url.searchParams.get("desde") : "2026-01-01";
    const dA = url.searchParams.get("desde_anuncios");
    const desdeAnuncios = /^\d{4}-\d{2}-\d{2}$/.test(dA || "") ? dA : desde;
    const anuncios = almacen.leerAnuncios ? await almacen.leerAnuncios(desdeAnuncios) : {};
    const respaldo = almacen.leerCortes ? { cortes_nube: await almacen.leerCortes(desde), respaldo: await almacen.leerRespaldo() } : {};
    return json({ generado: new Date(ahoraSeg * 1000).toISOString(), ...(await almacen.leer(desde)), ...anuncios, ...respaldo });
  }
  if (url.pathname === "/salud") {
    const d = await almacen.leer("9999-12-31");
    const diag = d.meta_estado && d.meta_estado.error && Array.isArray(d.meta_estado.campanas) && d.meta_estado.campanas[0] ? d.meta_estado.campanas[0].diagnostico || null : null;
    return json({ ok: true, meta_leido: d.meta_estado && d.meta_estado.leido, meta_error: d.meta_estado && d.meta_estado.error, diagnostico: diag, ultimo_aviso: d.ultimo_aviso });
  }
  return json({ error: "no_existe" }, 404);
}

export default {
  async fetch(req, env) {
    return manejarPeticion(req, env, almacenD1(env.DB));
  },
  async scheduled(_evento, env, ctx) {
    const almacen = almacenD1(env.DB);
    // la lectura por anuncio va aparte: si falla, la de campañas sigue igual
    // el corte de respaldo va justo después de la lectura de campañas (con datos frescos) y antes de la de anuncios
    ctx.waitUntil(leerMeta(env, almacen).then(() => respaldoCorte(env, almacen).catch(() => null)).then(() => leerAnunciosMeta(env, almacen)));
  },
};
