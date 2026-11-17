// test_web_operacion.mjs — lógica pura y render (con DOM falso) de #/operacion. Ejecutar: node --test tests/dashboard/test_web_operacion.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import * as L from '../../dashboard/web/lib/operacion.js';
import * as G from '../../dashboard/web/lib/graficos.js';
import { TERMINOS } from '../../dashboard/web/lib/glosario-operacion.js';
import { ui, fmt } from '../../dashboard/web/ui.js';
import { instalarDomFalso, porClase, porTag, texto } from '../fixtures/dashboard/operacion/dom_falso.mjs';

const fx = (n) => JSON.parse(readFileSync(fileURLToPath(new URL(`../fixtures/dashboard/operacion/${n}`, import.meta.url)), 'utf8'));
const AHORA = Date.parse('2026-11-13T10:00:00Z');
const AHORA_DEMO = Date.parse('2026-11-12T10:00:00Z'); // la demo se generó el 2026-11-12T09:05Z
const parametros = fx('parametros_min.json');
const economia = fx('economia.json');

// ───────────── aritmética sin float ─────────────

test('proporcionBp y dividirRedondeado: half-even, enteros, null ante datos inválidos', () => {
  assert.equal(L.proporcionBp(2880, 1830), 15738);
  assert.equal(L.proporcionBp(1, 3), 3333);
  assert.equal(L.proporcionBp(0, 100), 0); // un cero legítimo no es «sin dato»
  assert.equal(L.proporcionBp(5, 0), null);
  assert.equal(L.proporcionBp(-1, 5), null);
  assert.equal(L.proporcionBp(1.5, 5), null);
  assert.equal(L.dividirRedondeado(5, 2), 2); // 2,5 → 2 (half-even)
  assert.equal(L.dividirRedondeado(7, 2), 4); // 3,5 → 4
  assert.equal(L.dividirRedondeado(9007199254740991, 3), 3002399751580330);
});

test('cpaAcumulado: sin compras NO hay CPA (null, nunca 0)', () => {
  assert.equal(L.cpaAcumulado({ monto: 2760, moneda: 'EUR' }, 0), null);
  assert.equal(L.cpaAcumulado(null, 3), null);
  assert.deepEqual(L.cpaAcumulado({ monto: 5760, moneda: 'EUR' }, 2), { monto: 2880, moneda: 'EUR' });
  assert.deepEqual(L.cpaAcumulado({ monto: 100, moneda: 'EUR' }, 3), { monto: 33, moneda: 'EUR' });
  assert.equal(L.cpaAcumulado({ monto: 1.5, moneda: 'EUR' }, 1), null);
});

test('dineroValido / monedaDeUnidad / aNumero / textoDuracionH', () => {
  assert.deepEqual(L.dineroValido({ monto: 5, moneda: 'EUR' }), { monto: 5, moneda: 'EUR' });
  assert.equal(L.dineroValido({ monto: 5.5, moneda: 'EUR' }), null);
  assert.equal(L.dineroValido({ monto: 5, moneda: 'eur' }), null);
  assert.equal(L.monedaDeUnidad('EUR_minor'), 'EUR');
  assert.equal(L.monedaDeUnidad('porcentaje'), null);
  assert.equal(L.aNumero('1.60'), 1.6);
  assert.equal(L.aNumero('abc'), null);
  assert.equal(L.aNumero(NaN), null);
  assert.equal(L.textoDuracionH(0.25), '15 min');
  assert.equal(L.textoDuracionH(1.5), '1,5 h');
  assert.equal(L.textoDuracionH(72), '3 d');
  assert.equal(L.textoDuracionH(-1), '—');
});

// ───────────── frescura (B0-17) ─────────────

const U = L.umbralesDeFrescura(parametros);

test('umbralesDeFrescura lee parametros.dashboard.frescura_*', () => {
  assert.deepEqual(U.meta, { amarillo: 6, rojo: 12 });
  assert.deepEqual(U.stripe_eventos, { amarillo: 2, rojo: 6 });
  assert.deepEqual(U.stripe_balance, { amarillo: 26, rojo: 36 });
  assert.deepEqual(L.umbralesDeFrescura(null), {});
});

test('evaluarFuente: rojo por horas con causa; la peor señal manda; sin dato no es verde', () => {
  const r = L.evaluarFuente('meta', { frescura_h: '14.0', estado: 'verde' }, { umbrales: U });
  assert.equal(r.estado, 'rojo'); // el archivo decía verde pero 14 h ≥ 12 h
  assert.match(r.causa, /Meta con 14 h sin actualizar \(rojo desde 12 h\)/);
  assert.equal(L.evaluarFuente('meta', { frescura_h: '7', estado: 'verde' }, { umbrales: U }).estado, 'amarillo');
  assert.equal(L.evaluarFuente('meta', { frescura_h: '1', estado: 'rojo' }, { umbrales: U }).estado, 'rojo');
  const sin = L.evaluarFuente('stripe_balance', undefined);
  assert.equal(sin.estado, 'desconocido');
  assert.match(sin.causa, /no informa de esta fuente/);
  const nula = L.evaluarFuente('meta', { frescura_h: null, estado: 'rojo' });
  assert.match(nula.causa, /sin lectura registrada/);
  assert.equal(L.evaluarFuente('meta', { frescura_h: '1', estado: 'verde' }, { umbrales: U, horasExtra: 13 }).estado, 'rojo'); // el reloj envejece el snapshot
});

test('evaluarCifra: tachada con causa si la fuente está roja; ausente/gris/provisional/ok', () => {
  const snap = fx('operacion_rojo.json').kpi_dia.find((s) => s.fecha === '2026-11-11');
  const gasto = L.evaluarCifra('gasto_meta', L.filaDe(snap, 'gasto_meta'), snap, { umbrales: U });
  assert.equal(gasto.estado, 'tachada');
  assert.equal(gasto.valor, 3100); // se conserva el valor para mostrarlo tachado
  assert.match(gasto.causa, /Meta/);
  // compras depende solo de Stripe (verde): no se tacha por Meta
  assert.equal(L.evaluarCifra('compras_stripe', L.filaDe(snap, 'compras_stripe'), snap, { umbrales: U }).estado, 'gris');
  // CPA depende de Meta y Stripe: se tacha
  assert.equal(L.evaluarCifra('cpa', L.filaDe(snap, 'cpa'), snap, { umbrales: U }).estado, 'tachada');
  // fila inexistente: ausente, jamás 0
  const aus = L.evaluarCifra('tasa_reembolso', null, snap, { umbrales: U });
  assert.equal(aus.estado, 'ausente');
  assert.equal(aus.valor, null);
  assert.match(aus.causa, /no incluye «tasa de reembolsos»/);
  // la razón Meta/Stripe depende de Meta: con Meta en rojo se tacha aunque no traiga valor (se mostrará «sin dato», no 0)
  const r = L.evaluarCifra('razon_meta_stripe', L.filaDe(snap, 'razon_meta_stripe'), snap, { umbrales: U });
  assert.equal(r.estado, 'tachada');
  assert.equal(r.valor, null);
  // valor nulo con estado gris y fuentes sanas
  const dia1 = fx('operacion_rojo.json').kpi_dia.find((s) => s.fecha === '2026-11-10');
  const g = L.evaluarCifra('razon_meta_stripe', L.filaDe(dia1, 'razon_meta_stripe'), dia1, { umbrales: U });
  assert.equal(g.estado, 'gris');
  assert.equal(g.valor, null);
  assert.match(g.causa, /datos insuficientes \(muestra de 0\)/);
  // stale en la propia fila
  const st = L.evaluarCifra('gasto_meta', { kpi_id: 'gasto_meta', valor: 10, unidad: 'EUR_minor', n: 1, estado: 'stale', rango: null, ventana: '24h' }, { fecha: 'x', fuentes: { meta: { frescura_h: '1', estado: 'verde' } } }, {});
  assert.equal(st.estado, 'tachada');
  assert.match(st.causa, /vieja/);
  const prov = L.evaluarCifra('cpa', { kpi_id: 'cpa', valor: 5, unidad: 'EUR_minor', n: 2, estado: 'provisional', rango: null, ventana: '24h' }, { fecha: 'x', fuentes: { meta: { frescura_h: '1', estado: 'verde' }, stripe_eventos: { frescura_h: '1', estado: 'verde' } } }, {});
  assert.equal(prov.estado, 'provisional');
  assert.equal(L.evaluarCifra('gasto_meta', undefined, null, {}).causa, 'no hay cifras guardadas para este día');
});

test('frescura por reloj: el último snapshot envejece (se tacha), los días pasados no', () => {
  const ops = fx('operacion_rojo.json').kpi_dia;
  const antes = L.filasDiarias(ops, { umbrales: U, ahora: AHORA });
  assert.equal(antes.at(-1).cifras.gasto_meta.estado, 'ok');
  const tarde = L.filasDiarias(ops, { umbrales: U, ahora: Date.parse('2026-11-14T09:00:00Z') }); // 24 h después
  assert.equal(tarde.at(-1).cifras.gasto_meta.estado, 'tachada');
  assert.match(tarde.at(-1).cifras.gasto_meta.causa, /25,5 h sin actualizar/);
  assert.equal(tarde[0].cifras.gasto_meta.estado, 'ok'); // día pasado: no se tacha por la edad del archivo
});

// ───────────── series y acumulados ─────────────

test('ordenarSnapshots: orden por fecha, descarta inválidos y repetidos', () => {
  const s = fx('operacion_rojo.json').kpi_dia;
  const o = L.ordenarSnapshots([...s, { fecha: 'mal', filas: [] }, null, { fecha: '2026-11-10', filas: [], generado_en: '2020-01-01T00:00:00Z' }]);
  assert.deepEqual(o.map((x) => x.fecha), ['2026-11-10', '2026-11-11', '2026-11-12']);
  assert.ok(o[0].filas.length > 0); // el duplicado viejo no pisa al reciente
  assert.deepEqual(L.ordenarSnapshots(undefined), []);
});

test('acumular: el día tachado no suma y el CPA solo usa días comparables', () => {
  const filas = L.filasDiarias(fx('operacion_rojo.json').kpi_dia, { umbrales: U, ahora: AHORA });
  const a = L.acumular(filas);
  assert.deepEqual(a.gasto, { monto: 5760, moneda: 'EUR' }); // 2760 + 3000; el 11-11 (3100) está tachado
  assert.equal(a.compras, 3);
  assert.equal(a.completo, false);
  assert.deepEqual(a.excluidos.map((x) => [x.fecha, x.kpi_id]), [['2026-11-11', 'gasto_meta']]);
  assert.deepEqual(a.comparables, { gasto: { monto: 5760, moneda: 'EUR' }, compras: 2, dias: 2 });
  assert.equal(L.acumular([]).gasto, null);
  assert.equal(L.acumular([]).compras, null);
});

test('zonaCpa: objetivo / equilibrio / sobre, gris por pocas compras o poco gasto, sin CPA no hay zona', () => {
  const be = { monto: 1830, moneda: 'EUR' };
  const ob = { monto: 1098, moneda: 'EUR' };
  assert.equal(L.zonaCpa({ monto: 1098, moneda: 'EUR' }, be, ob).zona, 'objetivo');
  assert.equal(L.zonaCpa({ monto: 1099, moneda: 'EUR' }, be, ob).zona, 'equilibrio');
  assert.equal(L.zonaCpa({ monto: 1830, moneda: 'EUR' }, be, ob).zona, 'equilibrio');
  assert.equal(L.zonaCpa({ monto: 1831, moneda: 'EUR' }, be, ob).zona, 'sobre');
  const g = L.zonaCpa({ monto: 2000, moneda: 'EUR' }, be, ob, { compras: 2, comprasMin: 5 });
  assert.equal(g.gris, true);
  assert.match(g.motivoGris, /2 compras: hacen falta al menos 5/);
  const g2 = L.zonaCpa({ monto: 900, moneda: 'EUR' }, be, ob, { compras: 9, comprasMin: 5, gastoMinX: '2.0', gasto: { monto: 2000, moneda: 'EUR' } });
  assert.equal(g2.gris, true);
  assert.equal(L.zonaCpa({ monto: 900, moneda: 'EUR' }, be, ob, { compras: 9, comprasMin: 5, gastoMinX: '2.0', gasto: { monto: 9000, moneda: 'EUR' } }).gris, false);
  assert.equal(L.zonaCpa(null, be, ob).zona, null);
  assert.match(L.zonaCpa(null, be, ob).causa, /sin costo por venta/);
  assert.match(L.zonaCpa({ monto: 1, moneda: 'EUR' }, null, null).causa, /equilibrio/);
  assert.match(L.zonaCpa({ monto: 1, moneda: 'USD' }, be, ob).causa, /monedas distintas/);
});

test('usoDeTope: sin tope, sin gasto, moneda distinta, zonas', () => {
  const g = { monto: 3000, moneda: 'EUR' };
  assert.equal(L.usoDeTope(g, null, 'EUR').estado, 'sin_tope');
  assert.equal(L.usoDeTope(g, 0, 'EUR').estado, 'sin_tope'); // tope 0 = null o PAUSA: nada gasta
  assert.equal(L.usoDeTope(null, 5000, 'EUR').estado, 'sin_gasto');
  assert.equal(L.usoDeTope(g, 5000, 'USD').estado, 'moneda_distinta');
  assert.deepEqual(L.usoDeTope(g, 5000, 'EUR', { amarillaPct: 80, rojaPct: 100 }), { estado: 'ok', bp: 6000, zona: 'ok' });
  assert.equal(L.usoDeTope({ monto: 4000, moneda: 'EUR' }, 5000, 'EUR', { amarillaPct: 80, rojaPct: 100 }).zona, 'aviso');
  assert.equal(L.usoDeTope({ monto: 5000, moneda: 'EUR' }, 5000, 'EUR', { amarillaPct: 80, rojaPct: 100 }).zona, 'rojo');
  assert.equal(L.usoDeTope({ monto: 5001, moneda: 'EUR' }, 5000, 'EUR').zona, 'rojo');
});

test('topesDeLimites: null = sin tope; acepta {valores} o el mapa plano', () => {
  const n = L.topesDeLimites(fx('limites_nulos.json'));
  assert.deepEqual(n, { moneda: null, diario: null, total: null, perdida: null });
  const ok = L.topesDeLimites(fx('limites_fijados.json'));
  assert.deepEqual(ok, { moneda: 'EUR', diario: 5000, total: 20000, perdida: 15000 });
  assert.equal(L.topesDeLimites(null), null);
  assert.equal(L.topesDeLimites({ gasto_diario_por_oferta: 7 }).diario, 7);
});

// ───────────── decisiones de D8: nombre exacto, familias, ejecución ─────────────

test('nombre exacto de la decisión de D8 coincide con contratos/decision.schema.json', () => {
  const ruta = fileURLToPath(new URL('../../contratos/decision.schema.json', import.meta.url));
  if (!existsSync(ruta)) return; // el contrato es de otro dueño; sin él no hay nada que comparar
  const esquema = JSON.parse(readFileSync(ruta, 'utf8'));
  assert.equal(esquema.title, NOMBRE_ESPERADO());
  assert.match(esquema.description, /08-operacion\/decisiones\.jsonl/);
  assert.ok(esquema.description.includes(L.ARCHIVO_DECISIONES.replace('08-operacion/', '08-operacion/')));
  assert.deepEqual([...esquema.properties.accion.enum].sort(), [...L.ACCIONES_DECISION].sort());
  for (const k of ['regla', 'codigo', 'ejecutada', 'objeto_tipo', 'objeto_id', 'evidencia']) assert.ok(esquema.properties[k], `falta ${k} en el esquema`);
});
function NOMBRE_ESPERADO() { return L.NOMBRE_DECISION; }

test('familiaDeRegla: letra de la regla; sin ella, la acción (docs/08 §4.1)', () => {
  assert.equal(L.familiaDeRegla('G1', 'BLOQUEADO'), 'G');
  assert.equal(L.familiaDeRegla('K3', 'MATAR'), 'K');
  assert.equal(L.familiaDeRegla('M2', 'SEGUIR'), 'M');
  assert.equal(L.familiaDeRegla('E1', 'ESCALAR'), 'E');
  assert.equal(L.familiaDeRegla('FT1', 'SEGUIR'), 'M');
  assert.equal(L.familiaDeRegla(null, 'MATAR'), 'K');
  assert.equal(L.familiaDeRegla(undefined, 'INCONCLUSO'), 'G');
  assert.equal(L.familiaDeRegla('X1', 'RARA'), null);
});

test('normalizarDecisiones: orden por fecha desc, ejecución y acción desconocida', () => {
  const d = L.normalizarDecisiones(fx('operacion_rojo.json').decisiones);
  assert.equal(d.length, 6);
  assert.ok(d[0].ts >= d[1].ts && d[1].ts >= d[2].ts);
  const matar = d.find((x) => x.accion === 'MATAR');
  assert.equal(matar.familia, 'K');
  assert.equal(matar.ejecutada, true);
  assert.equal(matar.ejecucion.texto, 'ejecutada y verificada');
  assert.deepEqual(matar.evidencia.gasto, { monto: 5520, moneda: 'EUR' });
  assert.equal(matar.evidencia.p, 0.04);
  assert.equal(d.find((x) => x.accion === 'SEGUIR').ejecucion.texto, 'sin efecto (se mantiene)');
  assert.equal(d.find((x) => x.accion === 'ESCALAR').ejecucion.texto, 'propuesta: no ejecutada');
  assert.equal(d.find((x) => x.accion === 'BLOQUEADO').ejecucion.tono, 'error');
  const rara = d.find((x) => x.accion === 'RARA');
  assert.equal(rara.conocida, false);
  assert.equal(L.tonoAccion('RARA'), 'neutro');
  assert.deepEqual(L.normalizarDecisiones([null, {}, { accion: 5 }, 'x']), []);
  const r = L.resumenDecisiones(d);
  assert.deepEqual(r.porFamilia, { G: 2, K: 1, M: 1, E: 1 });
  assert.equal(r.total, 6);
  assert.equal(r.ejecutadas, 1);
  assert.equal(r.sinEjecutar, 5);
});

test('normalizarOrdenes: dinero entero, estado con tono, orden descendente', () => {
  const o = L.normalizarOrdenes(fx('operacion_rojo.json').ordenes);
  assert.equal(o.length, 1);
  assert.equal(o[0].estado, 'propuesta');
  assert.equal(o[0].tono, 'aviso');
  assert.equal(o[0].delta_pct, 20);
  assert.deepEqual(o[0].antes, { monto: 2760, moneda: 'EUR' });
  assert.deepEqual(o[0].despues, { monto: 3312, moneda: 'EUR' });
  assert.equal(o[0].gate.gate, 'H');
  const demo = L.normalizarOrdenes(fx('operacion_demo.json').ordenes);
  assert.equal(demo[0].tono, 'ok');
  assert.equal(demo[0].sintetico, true);
  assert.deepEqual(L.normalizarOrdenes([{ orden_id: 5 }, null]), []);
});

// ───────────── veredicto ─────────────

test('modeloVeredicto: estados, madurez y requisitos con parámetros; sin parámetros no inventa mínimos', () => {
  const v = L.modeloVeredicto(fx('operacion_rojo.json').veredicto, parametros);
  assert.equal(v.estado, 'PROMETEDORA');
  assert.equal(v.tono, 'info');
  assert.equal(v.recomendacionTexto, 'extender la prueba una vez');
  assert.deepEqual(v.madurez, { garantia: 14, margen: 7, madurezDias: 21, cohorteMaduraHasta: '2026-10-22', diasConDatos: 3 });
  const por = Object.fromEntries(v.requisitos.map((r) => [r.id, r]));
  assert.deepEqual([por.compras.actual, por.compras.minimo, por.compras.cumple], [2, 15, false]);
  assert.deepEqual([por.dias.actual, por.dias.minimo, por.dias.cumple], [3, 7, false]);
  assert.deepEqual([por.reembolsos.actual, por.reembolsos.minimo, por.reembolsos.cumple, por.reembolsos.sentido], [33.3, 8, false, 'max']);
  assert.equal(v.evidencia.mc_real, null);
  assert.deepEqual(L.modeloVeredicto(fx('operacion_rojo.json').veredicto, null).requisitos, []);
  const demo = L.modeloVeredicto(fx('operacion_demo.json').veredicto, parametros);
  assert.equal(demo.estado, 'INCONCLUSA');
  assert.equal(demo.tono, 'aviso');
  assert.equal(demo.p, null); // p nulo no se convierte en 0
  assert.equal(demo.evidencia.razon_ms, null);
  assert.equal(L.modeloVeredicto(null), null);
  assert.equal(L.modeloVeredicto({ estado: 'RARO' }).tono, 'neutro');
});

// ───────────── sparklines ─────────────

test('geometriaSparkline: los huecos y las cifras tachadas cortan la línea; solo un punto no inventa tendencia', () => {
  const g = L.geometriaSparkline([{ x: 'a', y: 1 }, { x: 'b', y: 3 }, { x: 'c', y: null }, { x: 'd', y: 2 }, { x: 'e', y: 4 }]);
  assert.equal(g.n, 4);
  assert.equal(g.segmentos.length, 2);
  assert.equal(g.puntos.length, 4);
  assert.deepEqual([g.min, g.max], [1, 4]);
  const t = L.geometriaSparkline([{ x: 'a', y: 1 }, { x: 'b', y: 2, estado: 'tachada' }, { x: 'c', y: 3 }]);
  assert.equal(t.segmentos.length, 0); // los tramos de un solo punto no son línea
  assert.equal(t.puntos.length, 3);
  assert.deepEqual(L.geometriaSparkline([{ x: 'a', y: null }]), { segmentos: [], puntos: [], min: null, max: null, n: 0 });
  const uno = L.geometriaSparkline([{ x: 'a', y: 5 }]);
  assert.equal(uno.puntos.length, 1);
  assert.equal(uno.segmentos.length, 0);
  const plana = L.geometriaSparkline([{ x: 'a', y: 5 }, { x: 'b', y: 5 }]);
  assert.equal(plana.segmentos.length, 1);
  assert.ok(plana.puntos.every((p) => Number.isFinite(p.x) && Number.isFinite(p.y)));
});

// ───────────── modelo completo ─────────────

test('modeloOperacion con la demo de _ejemplo: lo que hay se muestra y lo que no, queda vacío', () => {
  const m = L.modeloOperacion({ operacion: fx('operacion_demo.json'), economia, limites: fx('limites_nulos.json'), parametros }, { ahora: AHORA_DEMO });
  assert.equal(m.hayKpi, true);
  assert.equal(m.sintetico, true);
  assert.deepEqual(m.acumulado.gasto, { monto: 2760, moneda: 'EUR' });
  assert.equal(m.acumulado.compras, 1);
  assert.deepEqual(m.cpa, { monto: 2760, moneda: 'EUR' });
  assert.equal(m.zonaCpa.zona, 'sobre'); // 2760 > 1830
  assert.equal(m.zonaCpa.gris, true); // 1 compra < 5 mínimas
  assert.equal(m.usoDiario.estado, 'sin_tope'); // limites en null: «nada gasta hasta que se fijen»
  assert.equal(m.usoTotal.estado, 'sin_tope');
  assert.equal(m.cobertura, null);
  assert.equal(m.decisiones.length, 1);
  assert.equal(m.veredicto.estado, 'INCONCLUSA');
  assert.equal(m.ordenes.length, 1);
});

test('modeloOperacion: la demo vista un día después tacha el gasto por antigüedad (frescura por reloj)', () => {
  const m = L.modeloOperacion({ operacion: fx('operacion_demo.json'), economia, limites: fx('limites_fijados.json'), parametros }, { ahora: AHORA });
  assert.equal(m.ultima.cifras.gasto_meta.estado, 'tachada');
  assert.equal(m.acumulado.gasto, null); // no se suma una cifra tachada
  assert.equal(m.cpa, null);
  assert.equal(m.usoDiario.estado, 'sin_gasto');
});

test('modeloOperacion con límites fijados: usos de tope y parcialidad del CPA', () => {
  const m = L.modeloOperacion({ operacion: fx('operacion_rojo.json'), economia, limites: fx('limites_fijados.json'), parametros }, { ahora: AHORA });
  assert.deepEqual(m.gastoHoy, { monto: 3000, moneda: 'EUR' });
  assert.equal(m.usoDiario.bp, 6000);
  assert.equal(m.usoTotal.bp, 2880);
  assert.deepEqual(m.cpa, { monto: 2880, moneda: 'EUR' });
  assert.equal(m.cpaParcial, true);
  assert.equal(m.zonaCpa.zona, 'sobre');
  assert.equal(m.zonaCpa.bpEquilibrio, 15738);
  assert.equal(m.zonaCpa.gris, true);
  assert.equal(m.cobertura.valor, '85');
  assert.equal(m.umbralCoberturaPct, 90);
  assert.deepEqual(m.series.gasto.map((s) => [s.x, s.y, s.estado]), [['2026-11-10', 2760, 'ok'], ['2026-11-11', 3100, 'tachada'], ['2026-11-12', 3000, 'ok']]);
  assert.equal(m.series.cpa[0].y, null); // CPA sin compras: hueco, no 0
});

test('modeloOperacion sin nada: vacío explícito, jamás ceros', () => {
  const m = L.modeloOperacion({ operacion: fx('operacion_vacia.json') }, { ahora: AHORA });
  assert.equal(m.hayKpi, false);
  assert.equal(m.acumulado.gasto, null);
  assert.equal(m.acumulado.compras, null);
  assert.equal(m.cpa, null);
  assert.equal(m.gastoHoy, null);
  assert.equal(m.veredicto, null);
  assert.deepEqual(m.decisiones, []);
  const n = L.modeloOperacion({}, {});
  assert.equal(n.hayKpi, false);
  assert.equal(n.topes, null);
  const raro = L.modeloOperacion({ operacion: { kpi_dia: 'no', decisiones: 7, ordenes: null, veredicto: 'x' } }, {});
  assert.equal(raro.hayKpi, false);
});

test('economiaDe y comandosOperacion', () => {
  assert.deepEqual(L.economiaDe(economia).cpa_obj, { monto: 1098, moneda: 'EUR' });
  assert.equal(L.economiaDe({}), null);
  assert.equal(L.economiaDe(null), null);
  const c = L.comandosOperacion('OF-202611-01', '2026-11-11');
  assert.equal(c.kpi, '.venv/bin/python -m datos.kpi --oferta OF-202611-01 --fecha 2026-11-11');
  assert.match(L.comandosOperacion('x; rm -rf /', 'ayer').kpi, /OF-AAAAMM-NN --fecha AAAA-MM-DD$/); // un id hostil nunca entra en un comando
});

// ───────────── render con DOM falso ─────────────

function ctxDe(datosPorRuta, { ofertaActiva = 'OF-202611-01', ofertas = [] } = {}) {
  const llamadas = [];
  const api = {
    sobre: async (ruta, params) => {
      llamadas.push([ruta, params]);
      if (!(ruta in datosPorRuta)) throw Object.assign(new Error('no existe'), { codigo: 'no_encontrado', mensaje: 'no existe' });
      const d = datosPorRuta[ruta];
      return { datos: d.datos, fuente: d.fuente || [], generado_en: '2026-11-13T10:00:00Z', vacio: Boolean(d.vacio), avisos: [] };
    },
    get: async (ruta) => (await api.sobre(ruta)).datos,
  };
  const estado = { ofertaActiva, ofertas, fijar(p) { Object.assign(estado, p); } };
  return { ctx: { api, ui, fmt, estado, params: {}, ruta: 'operacion', recargar() {}, navegar() {}, alSalir() {} }, llamadas };
}

test('render: cifras tachadas con causa visible, «sin dato», decisiones y veredicto sin innerHTML', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/operacion.js');
    assert.equal(pagina.meta.ruta, 'operacion');
    assert.ok(pagina.meta.escucha.includes('oferta'));
    const rutas = {
      '/operacion/OF-202611-01': { datos: fx('operacion_rojo.json'), fuente: ['ofertas/OF-202611-01/08-operacion'] },
      '/oferta/OF-202611-01/archivo': { datos: { ruta: '03-oferta/economia.json', tipo: 'json', contenido: JSON.stringify(economia) } },
      '/parametros': { datos: { limites: fx('limites_fijados.json'), parametros } },
      '/finanzas': { datos: { conciliacion: { cobertura_adid_bp: 9800 } } },
    };
    const { ctx } = ctxDe(rutas);
    const raiz = await pagina.render(ctx);
    const t = texto(raiz);
    assert.match(t, /Resultados/);
    assert.ok(porTag(raiz, 's').length >= 1, 'debe haber cifras tachadas (<s>) por la fuente de Meta en rojo');
    assert.ok(porClase(raiz, 'cifra-causa').some((n) => /Meta 14 h/.test(n.textContent)), 'la causa (corta) va visible junto a la cifra tachada');
    assert.match(t, /Cifras tachadas del 11\/11\/2026: Meta con 14 h sin actualizar \(rojo desde 12 h\)/); // y la completa, una vez, bajo la tabla
    assert.match(t, /Qué ha decidido el sistema/);
    assert.match(t, /Frenos de seguridad \(2\)/);
    assert.match(t, /Pausar \(1\)/);
    assert.match(t, /ejecutada y verificada/);
    assert.match(t, /PROMETEDORA/);
    assert.match(t, /Qué falta para validar/);
    assert.match(t, /Solo 2 de 3 días son comparables/);
    assert.match(t, /5\.760,00|57,60/); // gasto acumulado formateado desde enteros
    assert.equal(porTag(raiz, 'script').length, 0);
  } finally { restaurar(); }
});

test('render: demo con límites en null muestra «sin tope fijado» y estados vacíos con comando copiable', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/operacion.js');
    const { ctx } = ctxDe({
      '/operacion/OF-202611-01': { datos: { kpi_dia: [], decisiones: [], ordenes: [], veredicto: null }, vacio: true, fuente: ['ofertas/OF-202611-01/08-operacion/diario/<fecha>/kpi_oferta_dia.json'] },
      '/parametros': { datos: { limites: fx('limites_nulos.json'), parametros } },
    });
    const raiz = await pagina.render(ctx);
    const t = texto(raiz);
    assert.match(t, /Esta oferta aún no tiene cifras diarias/);
    assert.match(t, /El sistema todavía no ha registrado decisiones/);
    assert.match(t, /Todavía no hay veredicto/);
    assert.match(t, /\.venv\/bin\/python -m datos\.kpi --oferta OF-202611-01/);
    assert.match(t, /Los topes de gasto aún no están fijados/);
    assert.ok(porClase(raiz, 'comando').length >= 3);
    assert.doesNotMatch(t, /\b0,00\b/); // nada de ceros inventados
  } finally { restaurar(); }
});

test('render: texto hostil en datos se muestra como texto (HTML, U+202E) y no rompe nada', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/operacion.js');
    const hostil = fx('operacion_rojo.json');
    hostil.decisiones[0].explicacion = '<img src=x onerror=alert(1)>‮evil';
    hostil.decisiones[0].codigo = '<script>alert(1)</script>';
    const { ctx } = ctxDe({ '/operacion/OF-202611-01': { datos: hostil }, '/parametros': { datos: { limites: fx('limites_fijados.json'), parametros } } });
    const raiz = await pagina.render(ctx);
    for (const d of porClase(raiz, 'detalle-tecnico')) if (d.montar) d.montar(); // el detalle técnico se construye al abrirlo
    assert.equal(porTag(raiz, 'img').length, 0);
    assert.equal(porTag(raiz, 'script').length, 0);
    const t = texto(raiz);
    assert.ok(t.includes('<img src=x onerror=alert(1)>'));
    assert.ok(t.includes('⟦U+202E⟧'), 'los controles bidi se hacen visibles');
  } finally { restaurar(); }
});

test('render sin oferta activa: lista de ofertas para elegir; con error de la API: errorBox', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/operacion.js');
    const ofertas = [{ oferta_id: 'OF-202611-01', demo: true, fase: 'en_construccion', nivel: 'N2', gasto: { hoy: { monto: 2760, moneda: 'EUR' }, acumulado: { monto: 2760, moneda: 'EUR' } }, actualizado_en: '2026-11-12T09:00:00Z' }];
    const { ctx } = ctxDe({ '/ofertas': { datos: ofertas } }, { ofertaActiva: null, ofertas });
    const raiz = await pagina.render(ctx);
    assert.match(texto(raiz), /Elige una oferta/);
    assert.match(texto(raiz), /OF-202611-01/);
    const fila = porTag(raiz, 'tr').find((n) => (n.eventos.click || []).length);
    assert.ok(fila, 'la fila es clicable');
    fila.dispararEvento('click');
    assert.equal(ctx.estado.ofertaActiva, 'OF-202611-01');
    const { ctx: c2 } = ctxDe({}, { ofertaActiva: 'OF-202611-01' });
    const e = await pagina.render(c2);
    assert.ok(porClase(e, 'error-box').length === 1);
  } finally { restaurar(); }
});


// ───────────── rediseño U4: gráficos SVG propios (geometría pura) ─────────────

test('ticksAgradables: marcas de 1·2·2,5·5 × 10^k hasta un máximo que contiene los datos', () => {
  assert.deepEqual(G.ticksAgradables(2760).ticks, [0, 1000, 2000, 3000]);
  assert.equal(G.ticksAgradables(2760).max, 3000);
  assert.deepEqual(G.ticksAgradables(9).ticks, [0, 2.5, 5, 7.5, 10]);
  assert.ok(G.ticksAgradables(0).max > 0, 'un máximo 0 no rompe la escala');
  assert.ok(G.ticksAgradables(NaN).max > 0);
});

test('indicesEjeX: primero y último siempre; sin amontonar rótulos', () => {
  assert.deepEqual(G.indicesEjeX(1, 400), [0]);
  assert.deepEqual(G.indicesEjeX(3, 400), [0, 1, 2]);
  const i = G.indicesEjeX(30, 400);
  assert.equal(i[0], 0); assert.equal(i[i.length - 1], 29);
  assert.ok(i.length <= 6, `demasiados rótulos: ${i.length}`);
  assert.equal(G.fechaCorta('2026-11-11'), '11/11');
});

test('geometriaGrafico: la línea se corta con huecos y con cifras tachadas; el eje Y es único y parte de 0', () => {
  const serie = [{ x: '2026-11-10', y: 1000 }, { x: '2026-11-11', y: 2000 }, { x: '2026-11-12', y: 2500, estado: 'tachada', causa: 'Meta 14 h' }, { x: '2026-11-13', y: null }, { x: '2026-11-14', y: 1500 }, { x: '2026-11-15', y: 1800 }];
  const g = G.geometriaGrafico(serie, { tipo: 'linea', ancho: 620, alto: 190, banda: { desde: 0, hasta: 2200 } });
  assert.equal(g.trazos.length, 2, 'un trazo antes de la tachada y otro después del hueco');
  assert.equal(g.ticksY[0].valor, 0);
  assert.ok(g.max >= 2500);
  assert.equal(g.puntos[2].estado, 'tachada');
  assert.equal(g.puntos[3].y, null);
  assert.equal(g.ultimo.i, 5);
  assert.ok(g.banda && g.banda.hasta < g.banda.desde, 'la banda se dibuja de abajo (0) hacia arriba');
  assert.ok(g.puntos.every((p) => p.x >= g.plot.x0 && p.x <= g.plot.x1));
});

test('geometriaGrafico: barras ≤ 24 px; un solo día y sin datos se declaran, nunca se inventan', () => {
  const b = G.geometriaGrafico([{ x: '2026-11-10', y: 100 }, { x: '2026-11-11', y: 300 }], { tipo: 'barras', ancho: 900 });
  assert.ok(b.puntos.every((p) => p.ancho <= 24 && p.ancho >= 4));
  assert.ok(b.puntos[1].alto > b.puntos[0].alto);
  const uno = G.geometriaGrafico([{ x: '2026-11-11', y: 2760 }], { tipo: 'linea' });
  assert.equal(uno.soloUnPunto, true);
  assert.deepEqual(uno.trazos, []);
  const nada = G.geometriaGrafico([{ x: '2026-11-11', y: null }], {});
  assert.equal(nada.sinDatos, true);
  assert.equal(G.geometriaGrafico([], {}).n, 0);
});

test('geometriaMargen: cero a un tercio; negativo a la izquierda, positivo a la derecha; recorta con aviso', () => {
  const pos = G.geometriaMargen(2500);
  assert.equal(pos.signo, 1); assert.equal(pos.izquierda, pos.cero); assert.ok(pos.ancho > 0 && pos.ancho <= 100 - pos.cero);
  const neg = G.geometriaMargen(-5000);
  assert.equal(neg.signo, -1); assert.ok(neg.izquierda < neg.cero);
  assert.equal(G.geometriaMargen(-99999).recortado, true);
  assert.equal(G.geometriaMargen(null), null);
  assert.equal(G.geometriaMargen(1.5), null);
});

test('geometriaMadurez: garantía + margen = madurez total; sin días no se dibuja', () => {
  const m = G.geometriaMadurez({ garantia: 14, total: 21 });
  assert.deepEqual(m.tramos.map((t) => [t.id, t.dias]), [['garantia', 14], ['margen', 7]]);
  assert.equal(Math.round(m.tramos.reduce((a, t) => a + t.pct, 0)), 100);
  assert.equal(G.geometriaMadurez({}), null);
  assert.equal(G.geometriaMadurez({ garantia: 14, margen: 7 }).total, 21);
});

// ───────────── rediseño U4: lenguaje de negocio ─────────────

const DEC = (o) => ({ accion: 'SEGUIR', codigo: '', regla: 'M1', objeto_tipo: 'anuncio', objeto_id: '120000000000003', ejecutada: false, explicacion: '', evidencia: { gasto: null, clics: null, compras: null, p: null }, ...o });
const eur = (m, c) => `${m / 100} ${c}`;

test('describirDecision: «Se pausó el anuncio X por 0 compras tras 3,4× el CPA de equilibrio» y la regla técnica queda aparte', () => {
  const d = L.describirDecision(DEC({ accion: 'MATAR', codigo: 'K1_SIN_COMPRAS_TRAS_K_CPA', regla: 'K1', ejecutada: true, evidencia: { gasto: { monto: 5520, moneda: 'EUR' }, clics: 210, compras: 0, p: 0.04 } }), { cpaBe: { monto: 1620, moneda: 'EUR' }, formatoDinero: eur });
  assert.match(d.frase, /^Se pausó el anuncio …000003 por 0 compras tras gastar 3,4× el máximo que se puede pagar por una venta\.$/);
  assert.equal(d.icono, 'pausa');
  assert.doesNotMatch(d.frase, /K1|sin_compras|SIN_COMPRAS/, 'la sigla técnica no va en la frase');
  const prop = L.describirDecision(DEC({ accion: 'MATAR', codigo: 'sin_compras', evidencia: { gasto: { monto: 5520, moneda: 'EUR' }, clics: 1, compras: 0, p: null } }), { formatoDinero: eur });
  assert.match(prop.frase, /^Se propone pausar el anuncio .* por 0 compras tras gastar 55.2 EUR\.$/);
});

test('describirDecision: seguir, escalar (pide firma), inconcluso y bloqueado; acción desconocida cae a la explicación', () => {
  assert.match(L.describirDecision(DEC({ codigo: 'M_VENTANA_NO_DECIDIR', objeto_tipo: 'campana' }), {}).frase, /^Se mantiene la campaña .*es muy pronto para juzgarlo/);
  const esc = L.describirDecision(DEC({ accion: 'ESCALAR', codigo: 'E_GANADOR_PROBABLE', regla: 'E1', objeto_tipo: 'campana', evidencia: { gasto: null, clics: null, compras: 16, p: 0.91 } }), {});
  assert.match(esc.frase, /propone escalar la campaña .*16 compras y 91 % de probabilidad.*Espera tu firma/);
  assert.equal(esc.pidePermiso, true);
  assert.match(L.describirDecision(DEC({ accion: 'INCONCLUSO', codigo: 'TOPE_SIN_VEREDICTO', objeto_tipo: 'oferta', objeto_id: 'OF-202611-01' }), {}).frase, /tope de gasto.*sin un veredicto claro/);
  const blq = L.describirDecision(DEC({ accion: 'BLOQUEADO', codigo: 'G7_PULL_INCOMPLETO', objeto_tipo: 'oferta' }), {});
  assert.match(blq.frase, /lectura de Meta llegó incompleta o con retraso/);
  assert.equal(blq.tono, 'error');
  const rara = L.describirDecision(DEC({ accion: 'RARA', explicacion: 'acción que el panel no conoce' }), {});
  assert.equal(rara.frase, 'acción que el panel no conoce');
});

test('describirOrden: subir, bajar y mantener con importes y estado en lenguaje humano', () => {
  const base = { objeto: { tipo: 'campana', nombre: 'OF-1_TEST' }, antes: { monto: 2760, moneda: 'EUR' }, despues: { monto: 3312, moneda: 'EUR' }, delta_pct: 20, estado: 'propuesta' };
  const sube = L.describirOrden({ ...base, accion: 'aumentar' }, eur);
  assert.equal(sube.frase, 'Subir el presupuesto de campaña OF-1_TEST de 27.6 EUR a 33.12 EUR (+20 %).');
  assert.equal(sube.estadoTexto, 'Propuesta: espera aprobación');
  assert.match(L.describirOrden({ ...base, accion: 'reducir', delta_pct: -10, estado: 'ejecutada' }, eur).frase, /^Bajar el presupuesto .* \(-10 %\)\.$/);
  assert.match(L.describirOrden({ ...base, accion: 'mantener', delta_pct: 0 }, eur).frase, /^Mantener el presupuesto de campaña OF-1_TEST en 33.12 EUR\.$/);
});

test('atencionOperacion: ordena crítico → aviso → info y dice qué hacer', () => {
  const m = L.modeloOperacion({ operacion: fx('operacion_rojo.json'), economia, limites: fx('limites_nulos.json'), parametros }, { ahora: AHORA });
  const a = L.atencionOperacion(m, { ofertaId: 'OF-202611-01', formatoDinero: eur });
  assert.ok(a.length >= 3);
  const orden = { critico: 0, aviso: 1, info: 2 };
  for (let i = 1; i < a.length; i += 1) assert.ok(orden[a[i - 1].tono] <= orden[a[i].tono], 'de más a menos urgente');
  assert.ok(a.some((x) => /tachadas/.test(x.titulo)), 'las cifras tachadas se avisan');
  const topes = a.find((x) => /topes de gasto/.test(x.titulo));
  assert.ok(topes && topes.accion && /parametros/.test(topes.accion.ruta), 'los topes sin fijar llevan a Parámetros y límites');
  const sano = L.modeloOperacion({ operacion: { kpi_dia: [], decisiones: [], ordenes: [], veredicto: null }, limites: fx('limites_fijados.json'), parametros }, { ahora: AHORA });
  assert.deepEqual(L.atencionOperacion(sano, {}), [], 'sin problemas no se inventa ningún aviso');
});

test('glosario-operacion: claves válidas para el índice, definiciones cortas y claves lim_ para cada límite del dueño', async () => {
  const { LIMITES_META } = await import('../../dashboard/web/lib/parametros.js');
  for (const [k, def] of Object.entries(TERMINOS)) {
    assert.match(k, /^[a-z0-9_]{1,60}$/, k);
    assert.ok(def.corto && def.corto.length <= 140, `«${k}»: corto ≤ 140 (${(def.corto || '').length})`);
    assert.ok(def.nombre, `«${k}» necesita nombre humano`);
  }
  for (const k of Object.keys(LIMITES_META)) assert.ok(TERMINOS[`lim_${k}`], `falta el término lim_${k}`);
  const { GLOSARIO } = await import('../../dashboard/web/lib/glosario.js');
  for (const k of Object.keys(TERMINOS)) assert.ok(!(k in GLOSARIO), `«${k}» ya está en el glosario base (el fragmento no pisa)`);
});
