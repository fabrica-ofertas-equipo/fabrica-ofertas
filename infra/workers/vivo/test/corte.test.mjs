// node --test infra/workers/vivo/test/*.test.mjs — corte de respaldo en la nube (17-nov).
import test from "node:test";
import assert from "node:assert/strict";

import { decidirCortes, motivoParaNoActuar, ventasWebhook } from "../src/corte.mjs";
import { respaldoCorte } from "../src/index.mjs";

const AHORA = new Date("2026-11-17T08:00:00Z");   // 05:00 ART, en pleno hueco del 17-nov

// Oferta M (TR): día 1 desde el 17-nov 00:00 Estambul, ticket del completo 19,90 → corte 29,85 sin ventas.
const ZIHIN = {
  test: "Oferta M", inicio: "2026-11-16T21:00:00Z", fin: "2026-11-17T21:00:00Z", desde: "2026-11-16",
  ticket_usd: 19.9, veces: 1.5, segunda_usada: false, extra_tickets: 0.5, ventas_conocidas: 0, tiendas: ["zihinatlasi"],
  campanas: [{ id: "c1" }],
};
const plan = (tests, extra = {}) => ({ generado: "2026-11-17T04:40:00Z", recibido: "2026-11-17T04:40:00Z",
  latido_vigilancia: "2026-11-17T04:40:00Z", tests, ...extra });
const fila = (campana, fecha, gasto, x = {}) => ({ campana, fecha, gasto, compras: 0, impresiones: 1000, clics: 5, visitas: 5, pagos_iniciados: 0, ...x });

test("pausa Zihin al pasar el corte sin ventas", () => {
  const r = decidirCortes({ plan: plan([ZIHIN]), metaDia: [fila("c1", "2026-11-16", 6), fila("c1", "2026-11-17", 25)], ventas: [], estados: { c1: "ACTIVE" }, ahora: AHORA });
  assert.equal(r.length, 1);
  assert.equal(r[0].campana, "c1");
  assert.equal(r[0].corte_usd, 29.85);
});

test("no pausa por debajo del corte, ni antes del inicio ni después del día 1", () => {
  const meta = [fila("c1", "2026-11-17", 20)];
  assert.equal(decidirCortes({ plan: plan([ZIHIN]), metaDia: meta, ventas: [], estados: { c1: "ACTIVE" }, ahora: AHORA }).length, 0);
  const caro = [fila("c1", "2026-11-17", 99)];
  assert.equal(decidirCortes({ plan: plan([ZIHIN]), metaDia: caro, ventas: [], estados: { c1: "ACTIVE" }, ahora: new Date("2026-11-16T20:00:00Z") }).length, 0);
  assert.equal(decidirCortes({ plan: plan([ZIHIN]), metaDia: caro, ventas: [], estados: { c1: "ACTIVE" }, ahora: new Date("2026-11-17T21:00:00Z") }).length, 0);
});

test("no toca una campaña que ya no está activa", () => {
  assert.equal(decidirCortes({ plan: plan([ZIHIN]), metaDia: [fila("c1", "2026-11-17", 99)], ventas: [], estados: { c1: "PAUSED" }, ahora: AHORA }).length, 0);
});

test("las ventas del webhook suben el corte (sin upsells, sin otras tiendas, sin ventas de antes)", () => {
  const ventas = [
    { orden_id: "a", evento: "order.approved", tienda: "zihinatlasi", creada: "2026-11-17T03:00:00Z" },
    { orden_id: "b", evento: "order.approved", tienda: "zihinatlasi", creada: "2026-11-17T03:10:00Z", post_compra: 1 },
    { orden_id: "c", evento: "order.approved", tienda: "otra", creada: "2026-11-17T03:10:00Z" },
    { orden_id: "d", evento: "order.approved", tienda: "zihinatlasi", creada: "2026-11-15T03:10:00Z" },
  ];
  assert.equal(ventasWebhook(ventas, ["zihinatlasi"], ZIHIN.inicio), 1);
  // 1 venta → corte 29,85; con 2 ventas (Meta) → 59,70
  const meta = [fila("c1", "2026-11-17", 40, { compras: 2 })];
  assert.equal(decidirCortes({ plan: plan([ZIHIN]), metaDia: meta, ventas, estados: { c1: "ACTIVE" }, ahora: AHORA }).length, 0);
});

test("segunda oportunidad: sin ventas pero con anuncio y página que funcionan, +0,5 ticket", () => {
  const meta = [fila("c1", "2026-11-17", 35, { impresiones: 1000, clics: 30, visitas: 25, pagos_iniciados: 4 })];
  assert.equal(decidirCortes({ plan: plan([ZIHIN]), metaDia: meta, ventas: [], estados: { c1: "ACTIVE" }, ahora: AHORA }).length, 0);  // corte 39,80
  const meta2 = [fila("c1", "2026-11-17", 40, { impresiones: 1000, clics: 30, visitas: 25, pagos_iniciados: 4 })];
  assert.equal(decidirCortes({ plan: plan([ZIHIN]), metaDia: meta2, ventas: [], estados: { c1: "ACTIVE" }, ahora: AHORA }).length, 1);
  // si ya la usó, no hay otra
  const usada = { ...ZIHIN, segunda_usada: true };
  assert.equal(decidirCortes({ plan: plan([usada]), metaDia: meta2, ventas: [], estados: { c1: "ACTIVE" }, ahora: AHORA }).length, 1);
});

test("réplica: corte por campaña (pocket 1 ticket, variaciones 1,5) y solo la que pasó", () => {
  const rep = { ...ZIHIN, test: "Oferta", ticket_usd: 38, tiendas: [], campanas: [{ id: "p", corte_tickets: 1 }, { id: "v", corte_tickets: 1.5 }] };
  const meta = [fila("p", "2026-11-17", 39), fila("v", "2026-11-17", 50)];
  const r = decidirCortes({ plan: plan([rep]), metaDia: meta, ventas: [], estados: { p: "ACTIVE", v: "ACTIVE" }, ahora: AHORA });
  assert.deepEqual(r.map((x) => x.campana), ["p"]);
});

test("la nube no actúa con la vigilancia viva, con Meta vieja o con el plan viejo", () => {
  const meta = { leido: "2026-11-17T07:58:00Z", error: null };
  assert.equal(motivoParaNoActuar(plan([ZIHIN], { latido_vigilancia: "2026-11-17T07:45:00Z" }), meta, AHORA), "vigilancia_viva");
  assert.equal(motivoParaNoActuar(plan([ZIHIN]), { leido: "2026-11-17T07:00:00Z" }, AHORA), "meta_vieja");
  assert.equal(motivoParaNoActuar(plan([ZIHIN]), { ...meta, error: "x" }, AHORA), "meta_con_error");
  assert.equal(motivoParaNoActuar(plan([ZIHIN], { recibido: "2026-11-15T00:00:00Z" }), meta, AHORA), "plan_viejo");
  assert.equal(motivoParaNoActuar(null, meta, AHORA), "sin_plan");
  assert.equal(motivoParaNoActuar(plan([ZIHIN]), meta, AHORA), null);
});

class Almacen {
  constructor() { this.plan = plan([ZIHIN]); this.cortes = new Map(); this.respaldo = null; }
  async leerPlan() { return this.plan; }
  async leer() { return { ventas: [], meta_dia: [fila("c1", "2026-11-17", 57.08)], meta_estado: { leido: "2026-11-17T07:58:00Z", error: null, campanas: [{ id: "c1", estado: "ACTIVE" }] } }; }
  async guardarRespaldo(i) { this.respaldo = i; }
  async cortada(c, t) { return (this.cortes.get(`${c}|${t}`) || {}).resultado || null; }
  async guardarCorte(c) { this.cortes.set(`${c.campana}|${c.test}`, c); }
}

test("sin token de gestión solo anota lo que habría pausado", async () => {
  const a = new Almacen();
  const r = await respaldoCorte({}, a, { ahora: AHORA, fetchFn: () => { throw new Error("no debería llamar a Meta"); } });
  assert.equal(r.cortes.length, 1);
  assert.equal(r.cortes[0].resultado, "sin_token");
});

test("con token pausa, comprueba y no repite", async () => {
  const a = new Almacen();
  const llamadas = [];
  const fetchFn = async (url, opts = {}) => {
    llamadas.push([opts.method || "GET", String(url).split("?")[0]]);
    const cuerpo = opts.method === "POST" ? { success: true } : { status: "PAUSED", effective_status: "PAUSED" };
    return new Response(JSON.stringify(cuerpo), { status: 200 });
  };
  const env = { META_GESTION_TOKEN: "t", GRAPH_VERSION: "v23.0" };
  const r = await respaldoCorte(env, a, { ahora: AHORA, fetchFn });
  assert.equal(r.cortes[0].resultado, "pausada");
  assert.deepEqual(llamadas, [["POST", "https://graph.facebook.com/v23.0/c1"], ["GET", "https://graph.facebook.com/v23.0/c1"]]);
  const r2 = await respaldoCorte(env, a, { ahora: AHORA, fetchFn });
  assert.equal(r2.cortes.length, 0);
});

// ---------- límites genéricos por campaña (17-nov, R9 v2) ----------
import { decidirLimites } from "../src/corte.mjs";

const LIM = { test: "Oferta F", campana: "n7", rol: "nuevos", tickets: 1.5, ticket_usd: 54, desde: "2026-11-17", inicio: "2026-11-17T23:00:00Z" };
const AHORA_18 = new Date("2026-11-18T12:00:00Z");

test("límite genérico: pausa una CBO de Nuevos que pasó 1,5 tickets sin ventas, en cualquier fase", () => {
  const r = decidirCortes({ plan: plan([], { limites: [LIM] }), metaDia: [fila("n7", "2026-11-18", 82)], ventas: [], estados: { n7: "ACTIVE" }, ahora: AHORA_18 });
  assert.equal(r.length, 1);
  assert.equal(r[0].campana, "n7");
  assert.equal(r[0].corte_usd, 81);
});

test("límite genérico: las compras de la campaña suben el corte; no actúa antes del inicio ni si está pausada", () => {
  const meta = [fila("n7", "2026-11-18", 150, { compras: 2 })];   // corte 1,5 × 54 × 2 = 162
  assert.equal(decidirLimites({ plan: { limites: [LIM] }, metaDia: meta, estados: { n7: "ACTIVE" }, ahora: AHORA_18 }).length, 0);
  const caro = [fila("n7", "2026-11-18", 500)];
  assert.equal(decidirLimites({ plan: { limites: [LIM] }, metaDia: caro, estados: { n7: "ACTIVE" }, ahora: new Date("2026-11-17T22:00:00Z") }).length, 0);
  assert.equal(decidirLimites({ plan: { limites: [LIM] }, metaDia: caro, estados: { n7: "PAUSED" }, ahora: AHORA_18 }).length, 0);
});

test("límite genérico: un rol que la nube no conoce entra igual (lo decide la Mac)", () => {
  const raro = { ...LIM, campana: "x1", rol: "cualquier_rol_futuro", tickets: 2 };
  const r = decidirLimites({ plan: { limites: [raro] }, metaDia: [fila("x1", "2026-11-18", 108)], estados: { x1: "ACTIVE" }, ahora: AHORA_18 });
  assert.equal(r.length, 1);
  assert.equal(r[0].corte_usd, 108);
});

test("un plan solo con límites no se descarta y se suma desde el día del límite", () => {
  const p = plan(undefined, { limites: [LIM], recibido: "2026-11-18T11:55:00Z", latido_vigilancia: "2026-11-18T11:50:00Z" });
  delete p.tests;
  assert.equal(motivoParaNoActuar(p, { leido: "2026-11-18T11:58:00Z" }, AHORA_18), "vigilancia_viva");
  const r = decidirCortes({ plan: p, metaDia: [fila("n7", "2026-11-16", 999), fila("n7", "2026-11-18", 10)], ventas: [], estados: { n7: "ACTIVE" }, ahora: AHORA_18 });
  assert.equal(r.length, 0);   // lo del 16 es de antes de `desde`
});
