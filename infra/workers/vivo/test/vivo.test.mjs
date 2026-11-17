// node --test infra/workers/vivo/test/*.test.mjs
import test from "node:test";
import assert from "node:assert/strict";

import { hmacHex, verificarFirma, ventaDePayload, filasMeta, diasCuenta, autorizado, accion } from "../src/logica.mjs";
import { manejarPeticion, leerMeta } from "../src/index.mjs";

const SECRETO = "clave-de-prueba";
const AHORA = 1763130000;

class AlmacenMemoria {
  constructor() { this.ventas = new Map(); this.entregas = new Set(); this.meta = new Map(); this.estado = null; }
  async yaVisto(id) { return this.entregas.has(id); }
  async guardarVenta(v) { this.ventas.set(`${v.orden_id}|${v.evento}`, v); this.entregas.add(v.entrega_id); }
  async guardarMeta(filas, campanas, leido, error) { for (const f of filas) this.meta.set(`${f.fecha}|${f.campana}`, f); this.estado = { leido, error, campanas }; }
  async leer(desde) {
    return { ventas: [...this.ventas.values()].filter((v) => !v.prueba && (v.creada || v.recibido).slice(0, 10) >= desde),
      meta_dia: [...this.meta.values()].filter((f) => f.fecha >= desde), meta_estado: this.estado, ultimo_aviso: null };
  }
}

const PAYLOAD = {
  id: "entrega-1", event: "order.approved", created_at: "2026-11-14T14:22:05.310Z",
  data: {
    order_id: "ord-1", order_number: 3272738, status: "approved",
    customer: { email: "persona@ejemplo.com", name: "Juan", last_name: "Pérez", phone: "+5491122334455", tax_id: "123" },
    items: [{ product_id: "p1", name: "Biblioteca", price: 54.09, quantity: 1, type: "main" }],
    total: 54.09, currency: "USD", buyer_total: 49, buyer_currency: "EUR", buyer_country: "ES", payment_method: "whop",
    is_post_purchase: false, parent_order_id: null, order_created_at: "2026-11-14T13:17:04.000Z",
    tracking: { utm_campaign: "ES | Oferta F", utm_id: "100000000000000075", utm_adset: "abierto", utm_content: "A03", fbclid: "IwAR", referrer: "https://x/?fbclid=IwAR" },
    store: { id: "s1", name: "Oferta F", subdomain: "tu-tienda", language: "es" },
  },
};

async function pedido(cuerpoObj, { ts = AHORA, secreto = SECRETO, firma } = {}) {
  const cuerpo = JSON.stringify(cuerpoObj);
  const f = firma ?? await hmacHex(secreto, `${ts}.${cuerpo}`);
  return new Request("https://vivo.tu-dominio.com/webhooks/impultienda", {
    method: "POST", body: cuerpo, headers: { "content-type": "application/json", "x-impultienda-timestamp": String(ts), "x-impultienda-signature": f },
  });
}

test("firma: válida, inválida, vieja y sin secreto", async () => {
  const cuerpo = "{\"a\":1}";
  const firma = await hmacHex(SECRETO, `${AHORA}.${cuerpo}`);
  assert.deepEqual(await verificarFirma({ secreto: SECRETO, firma, timestamp: String(AHORA), cuerpo, ahoraSeg: AHORA + 10 }), { ok: true });
  assert.equal((await verificarFirma({ secreto: SECRETO, firma, timestamp: String(AHORA), cuerpo: "{\"a\":2}", ahoraSeg: AHORA })).motivo, "firma_invalida");
  assert.equal((await verificarFirma({ secreto: SECRETO, firma, timestamp: String(AHORA), cuerpo, ahoraSeg: AHORA + 301 })).motivo, "timestamp_viejo");
  assert.equal((await verificarFirma({ secreto: "", firma, timestamp: String(AHORA), cuerpo, ahoraSeg: AHORA })).motivo, "falta_secreto");
});

test("venta: sin datos personales del comprador", () => {
  const v = ventaDePayload(PAYLOAD);
  const todo = JSON.stringify(v);
  for (const dato of ["persona@ejemplo.com", "Juan", "Pérez", "5491122334455", "IwAR"]) assert.ok(!todo.includes(dato), dato);
  assert.equal(v.orden, 3272738);
  assert.equal(v.tienda, "tu-tienda");
  assert.equal(v.utm_id, "100000000000000075");
  assert.equal(v.prueba, 0);
  assert.equal(ventaDePayload({ ...PAYLOAD, test: true }).prueba, 1, "el botón Probar de Impultienda no cuenta");
  assert.equal(ventaDePayload({ ...PAYLOAD, data: { ...PAYLOAD.data, order_id: "TEST-1" } }).prueba, 1);
  assert.equal(ventaDePayload({ nada: 1 }), null);
});

test("webhook: guarda una vez, repetido no duplica, firma mala 401", async () => {
  const al = new AlmacenMemoria();
  const env = { IMPULTIENDA_WEBHOOK_SECRET: SECRETO };
  let r = await manejarPeticion(await pedido(PAYLOAD), env, al, { ahoraSeg: AHORA });
  assert.equal(r.status, 200);
  r = await manejarPeticion(await pedido(PAYLOAD), env, al, { ahoraSeg: AHORA });
  assert.deepEqual(await r.json(), { ok: true, repetido: true });
  assert.equal(al.ventas.size, 1);
  r = await manejarPeticion(await pedido({ ...PAYLOAD, id: "entrega-2", event: "order.refunded", data: { ...PAYLOAD.data, status: "refunded" } }), env, al, { ahoraSeg: AHORA });
  assert.equal(al.ventas.size, 2, "el reembolso es otra fila de la misma orden");
  r = await manejarPeticion(await pedido(PAYLOAD, { firma: "00" }), env, al, { ahoraSeg: AHORA });
  assert.equal(r.status, 401);
  r = await manejarPeticion(new Request("https://vivo.tu-dominio.com/webhooks/impultienda"), env, al, { ahoraSeg: AHORA });
  assert.equal(r.status, 405);
});

test("lectura del panel: solo con la clave", async () => {
  const al = new AlmacenMemoria();
  await al.guardarVenta(ventaDePayload(PAYLOAD));
  const env = { LECTURA_TOKEN: "lectura-123" };
  let r = await manejarPeticion(new Request("https://vivo.tu-dominio.com/api/estado?desde=2026-11-14"), env, al, { ahoraSeg: AHORA });
  assert.equal(r.status, 401);
  r = await manejarPeticion(new Request("https://vivo.tu-dominio.com/api/estado?desde=2026-11-14", { headers: { authorization: "Bearer lectura-123" } }), env, al, { ahoraSeg: AHORA });
  const d = await r.json();
  assert.equal(d.ventas.length, 1);
  assert.equal(autorizado("Bearer otra", "lectura-123"), false);
  assert.equal(autorizado("Bearer x", ""), false, "sin clave configurada nadie lee");
  r = await manejarPeticion(new Request("https://vivo.tu-dominio.com/salud"), env, al, { ahoraSeg: AHORA });
  assert.equal(r.status, 200);
  r = await manejarPeticion(new Request("https://vivo.tu-dominio.com/otra"), env, al, { ahoraSeg: AHORA });
  assert.equal(r.status, 404);
});

test("Meta: filas por día, sin sumar tipos repetidos de compra, y errores anotados", async () => {
  const filas = filasMeta([{ campaign_id: "1", campaign_name: "ES | TeO", date_start: "2026-11-14", spend: "144.38", impressions: "3321", inline_link_clicks: "255",
    actions: [{ action_type: "omni_purchase", value: "9" }, { action_type: "purchase", value: "9" }, { action_type: "landing_page_view", value: "245" }, { action_type: "omni_initiated_checkout", value: "26" }],
    action_values: [{ action_type: "omni_purchase", value: "374.61" }] }], "L");
  assert.deepEqual(filas[0], { fecha: "2026-11-14", campana: "1", nombre: "ES | TeO", gasto: 144.38, impresiones: 3321, clics: 255, visitas: 245, pagos_iniciados: 26, compras: 9, valor_compras: 374.61, leido: "L" });
  assert.equal(accion(null, ["x"]), 0);
  assert.deepEqual(diasCuenta(new Date("2026-11-14T02:30:00Z"), "America/Argentina/Buenos_Aires"), { hoy: "2026-11-13", ayer: "2026-11-12" });

  const al = new AlmacenMemoria();
  assert.deepEqual(await leerMeta({}, al, { ahora: new Date("2026-11-14T15:00:00Z") }), { ok: false, error: "falta_token" });
  const pedidos = [];
  const fetchFalso = async (url) => {
    pedidos.push(url);
    const datos = url.includes("/insights") ? { data: [{ campaign_id: "1", date_start: "2026-11-14", spend: "10" }] } : { data: [{ id: "1", name: "c", effective_status: "ACTIVE", daily_budget: "6500" }] };
    return new Response(JSON.stringify(datos), { status: 200 });
  };
  const r = await leerMeta({ META_ACCESS_TOKEN: "t", CUENTA_META: "123" }, al, { ahora: new Date("2026-11-14T15:00:00Z"), fetchFn: fetchFalso });
  assert.equal(r.ok, true);
  assert.ok(pedidos[0].includes("act_123/insights") && pedidos[0].includes("time_increment=1"));
  assert.equal(al.estado.campanas[0].presupuesto_usd, 65);
  const malo = async () => new Response(JSON.stringify({ error: { message: "token vencido" } }), { status: 400 });
  assert.equal((await leerMeta({ META_ACCESS_TOKEN: "t", CUENTA_META: "123" }, al, { fetchFn: malo })).error, "token vencido");
  assert.equal(al.estado.error, "token vencido", "el error queda a la vista del panel");
});

// ───────────────────────── Meta por anuncio (15-nov) ─────────────────────────
import { filasAnuncio, datosAnuncios } from "../src/logica.mjs";
import { leerAnunciosMeta } from "../src/index.mjs";

test("filasAnuncio: compras, 3 s de video y retención; descarta días sin impresiones", () => {
  const f = filasAnuncio([
    { ad_id: "1", ad_name: "A01", adset_id: "9", adset_name: "abierto", campaign_id: "7", date_start: "2026-11-14", spend: "12.5", impressions: "1000", reach: "800",
      inline_link_clicks: "20", actions: [{ action_type: "video_view", value: "300" }, { action_type: "omni_purchase", value: "2" }, { action_type: "purchase", value: "2" }],
      action_values: [{ action_type: "omni_purchase", value: "38" }], video_p25_watched_actions: [{ action_type: "video_view", value: "200" }], video_p100_watched_actions: [{ action_type: "video_view", value: "40" }] },
    { ad_id: "2", date_start: "2026-11-14", spend: "0", impressions: "0" },
  ]);
  assert.equal(f.length, 1);
  assert.equal(f[0].compras, 2);
  assert.equal(f[0].valor_compras, 38);
  assert.equal(f[0].vistas_3s, 300);
  assert.equal(f[0].video_p100, 40);
  assert.equal(f[0].conjunto, "abierto");
});

test("datosAnuncios: estado, conjunto y miniatura", () => {
  const a = datosAnuncios([{ id: "1", name: "A01", effective_status: "ACTIVE", adset_id: "9", adset: { name: "R3" }, campaign_id: "7", creative: { id: "c", thumbnail_url: "https://x/t.jpg" } }]);
  assert.deepEqual([a[0].estado, a[0].conjunto, a[0].miniatura], ["ACTIVE", "R3", "https://x/t.jpg"]);
});

test("leerAnunciosMeta: pagina, guarda por día (con días vacíos) y no rompe si falla", async () => {
  const guardado = {};
  const alm = { async leerAnuncios() { return { anuncio_dia: [], anuncios: [] }; }, async guardarAnuncios(d, a, l, e) { Object.assign(guardado, { d, a, e }); } };
  const llamadas = [];
  const fetchFn = async (url) => {
    llamadas.push(url);
    if (url.includes("/insights")) {
      const pag2 = url.includes("after=");
      return new Response(JSON.stringify(pag2 ? { data: [{ ad_id: "2", date_start: "2026-11-14", spend: "1", impressions: "10" }] }
        : { data: [{ ad_id: "1", date_start: "2026-11-15", spend: "1", impressions: "10" }], paging: { next: "x", cursors: { after: "c1" } } }));
    }
    return new Response(JSON.stringify({ data: [{ id: "1", name: "A01", effective_status: "ACTIVE" }] }));
  };
  const r = await leerAnunciosMeta({ META_ACCESS_TOKEN: "t", CUENTA_META: "1" }, alm, { ahora: new Date("2026-11-15T15:00:00Z"), fetchFn, relleno: false });
  assert.equal(r.ok, true);
  assert.deepEqual(Object.keys(guardado.d).sort(), ["2026-11-14", "2026-11-15"]);
  assert.equal(guardado.a.length, 1);
  const r2 = await leerAnunciosMeta({ META_ACCESS_TOKEN: "t", CUENTA_META: "1" }, alm, { ahora: new Date("2026-11-15T15:00:00Z"), fetchFn: async () => new Response("{}", { status: 500 }), relleno: false });
  assert.equal(r2.ok, false);
  assert.ok(guardado.e);
});

test("carritos: solo abandonados y rechazados, sin datos del comprador; firma si hay clave", async () => {
  const al = new AlmacenMemoria();
  al.carritos = new Map();
  al.guardarCarrito = async (c) => { al.carritos.set(`${c.orden_id}|${c.evento}`, c); al.entregas.add(c.entrega_id); };
  al.leerCarritos = async () => ({ carritos: [...al.carritos.values()], aprobadas: [] });
  const ab = { ...PAYLOAD, id: "e-ab", event: "order.abandoned", data: { ...PAYLOAD.data, status: "pending" } };
  const url = "https://vivo.tu-dominio.com/webhooks/impultienda-carritos";
  const req = async (obj, opts = {}) => { const r = await pedido(obj, opts); return new Request(url, { method: "POST", body: await r.text(), headers: r.headers }); };
  let r = await manejarPeticion(await req(ab), {}, al, { ahoraSeg: AHORA });
  assert.equal(r.status, 200);
  const c = al.carritos.get("ord-1|order.abandoned");
  assert.equal(c.tienda, "tu-tienda");
  assert.equal(c.verificado, 0);
  assert.ok(!JSON.stringify(c).includes("persona@ejemplo.com"), "nunca el email");
  r = await manejarPeticion(await req({ ...PAYLOAD, id: "e-ap" }), {}, al, { ahoraSeg: AHORA });
  assert.deepEqual(await r.json(), { ok: true, ignorado: true }, "una venta por este endpoint no se guarda");
  const env = { IMPULTIENDA_CARRITOS_SECRET: SECRETO, LECTURA_TOKEN: "l" };
  r = await manejarPeticion(await req({ ...ab, id: "e-rj", event: "order.rejected" }, { firma: "00" }), env, al, { ahoraSeg: AHORA });
  assert.equal(r.status, 401);
  r = await manejarPeticion(await req({ ...ab, id: "e-rj", event: "order.rejected" }), env, al, { ahoraSeg: AHORA });
  assert.equal(al.carritos.get("ord-1|order.rejected").verificado, 1);
  r = await manejarPeticion(new Request("https://vivo.tu-dominio.com/api/carritos?desde=2026-11-14T00:00:00Z"), env, al, { ahoraSeg: AHORA });
  assert.equal(r.status, 401);
  r = await manejarPeticion(new Request("https://vivo.tu-dominio.com/api/carritos?desde=2026-11-14T00:00:00Z", { headers: { authorization: "Bearer l" } }), env, al, { ahoraSeg: AHORA });
  assert.equal((await r.json()).carritos.length, 2);
});
