// test_web_agentes.mjs — lógica pura y render (DOM falso) de #/agentes. Ejecutar: node --test tests/dashboard/test_web_agentes.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import * as A from '../../dashboard/web/lib/agentes.js';
import { ui, fmt, cerrarModales } from '../../dashboard/web/ui.js';
import { instalarDomFalso, porClase, porTag, texto, todos } from '../fixtures/dashboard/operacion/dom_falso.mjs';

const fx = (n) => JSON.parse(readFileSync(fileURLToPath(new URL(`../fixtures/dashboard/agentes/${n}`, import.meta.url)), 'utf8'));
const agrup = fx('agentes_agrupados.json');
const ofertas = [{ oferta_id: 'OF-202611-01', demo: true }, { oferta_id: 'OF-202611-02', demo: false }];
const limitesTope = fx('limites_con_tope.json');
const limitesNull = fx('limites_sin_tope.json');

test('normalizarModo / modoVisible: la oferta demo se anota como fixture, live nunca se disfraza', () => {
  assert.equal(A.normalizarModo('dry-run'), 'dry_run');
  assert.equal(A.normalizarModo('dry_run'), 'dry_run');
  assert.equal(A.normalizarModo('FIXTURE'), 'fixture');
  assert.equal(A.normalizarModo('live'), 'live');
  assert.equal(A.normalizarModo('otro'), null);
  assert.equal(A.normalizarModo(undefined), null);
  assert.equal(A.modoVisible('dry_run', { demo: true }), 'fixture');
  assert.equal(A.modoVisible('dry_run', { demo: false }), 'dry_run');
  assert.equal(A.modoVisible('live', { demo: true }), 'live');
  assert.equal(A.modoVisible(null, { demo: true }), null);
});

test('esAgenteQa', () => {
  for (const x of ['d5-qa', 'x1-qa', 'qa', 'qa-d3', 'd5:qa']) assert.equal(A.esAgenteQa(x), true, x);
  for (const x of ['d5-maker', 'motor', 'script:activar', 'aqua', null, 5]) assert.equal(A.esAgenteQa(x), false, String(x));
});

test('agruparRegistro: agrupa líneas crudas por ejecución con todas sus etapas y agentes; estado = el peor; duración medida', () => {
  const crudo = fx('registro_demo.json');
  const g = A.agruparRegistro(crudo.lineas);
  assert.equal(g.length, 1);
  const e = g[0];
  assert.equal(e.ejecucion_id, 'RUN-20261106-01');
  assert.deepEqual(e.etapas, ['D1', 'D7']);
  assert.deepEqual(e.agentes, ['d1-maker', 'motor', 'script:activar']);
  assert.equal(e.estado, 'bloqueado'); // una línea bloqueada vuelve bloqueada la ejecución
  assert.equal(e.eventos.length, 3);
  assert.equal(e.inicio, '2026-11-06T11:00:00Z');
  assert.equal(e.fin, '2026-11-09T10:30:00Z');
  assert.equal(e.modo, 'dry_run');
  assert.deepEqual(e.costo, { monto: 0, moneda: 'EUR' });
  assert.deepEqual(A.agruparRegistro(undefined), []);
  assert.deepEqual(A.agruparRegistro([{ ejecucion_id: 5 }, null, { evento: 'x' }]), []);
});

test('agruparRegistro: varias ejecuciones ordenadas por inicio descendente; monedas distintas no se suman', () => {
  const lineas = [
    { ejecucion_id: 'RUN-20261101-01', ts: '2026-11-01T10:00:00Z', etapa: 'D1', agente: 'a', evento: 'accion', resultado: { estado: 'ok', codigo: 0 }, costo_estimado: { monto: 100, moneda: 'EUR' }, modo: 'live', oferta_id: null },
    { ejecucion_id: 'RUN-20261101-01', ts: '2026-11-01T10:01:00Z', etapa: 'D1', agente: 'a', evento: 'accion', resultado: { estado: 'ok', codigo: 0 }, costo_estimado: { monto: 5, moneda: 'USD' }, modo: 'live', oferta_id: null },
    { ejecucion_id: 'RUN-20261102-01', ts: '2026-11-02T10:00:00Z', etapa: 'D2', agente: 'b', evento: 'accion', resultado: { estado: 'error', codigo: 3 }, costo_estimado: { monto: 7, moneda: 'EUR' }, modo: 'dry_run', oferta_id: 'OF-202611-01' },
  ];
  const g = A.agruparRegistro(lineas);
  assert.deepEqual(g.map((x) => x.ejecucion_id), ['RUN-20261102-01', 'RUN-20261101-01']);
  assert.equal(g[1].costo, null); // dos monedas: no hay un costo único
  assert.deepEqual(g[1].costos, [{ moneda: 'EUR', monto: 100 }, { moneda: 'USD', monto: 5 }]);
  assert.equal(g[0].estado, 'error');
});

test('normalizarEjecucion: duración, costo, estado y rondas; una sola línea no tiene duración (null, no 0)', () => {
  const e = A.normalizarEjecucion(agrup[0]);
  assert.equal(e.duracionMs, 450000);
  assert.deepEqual(e.costo, { monto: 300, moneda: 'EUR' });
  assert.equal(e.tono, 'ok');
  assert.equal(e.nEventos, 3);
  assert.equal(e.eventos, null); // el listado no trae los eventos: llegan con el detalle
  const sola = A.normalizarEjecucion(agrup[4]);
  assert.equal(sola.duracionMs, null);
  assert.equal(sola.unSoloEvento, true);
  assert.equal(sola.costo, null); // sin costo registrado: null, no 0
  assert.equal(sola.oferta_id, null);
  assert.equal(A.normalizarEjecucion({ ejecucion_id: 'x', rondas_qa: 2 }).rondas_qa, 2);
  assert.equal(A.normalizarEjecucion({ ejecucion_id: 'x', estado: 'dry-run' }).estado, 'dry_run');
  assert.equal(A.normalizarEjecucion(null), null);
  assert.equal(A.normalizarEjecucion({ oferta_id: 'OF-202611-01' }), null);
  assert.equal(A.normalizarEjecucion({ ejecucion_id: 'x', costo: { monto: 1.5, moneda: 'EUR' } }).costo, null); // float: no es dinero
  const demo = A.normalizarEjecucion(agrup[0], { ofertasDemo: new Set(['OF-202611-01']) });
  assert.equal(demo.modo, 'fixture');
});

test('ejecucionesDeDatos acepta array, {ejecuciones}, {lineas} y líneas crudas', () => {
  assert.equal(A.ejecucionesDeDatos(agrup).length, 7);
  assert.equal(A.ejecucionesDeDatos({ ejecuciones: agrup }).length, 7);
  assert.equal(A.ejecucionesDeDatos(fx('registro_demo.json')).length, 1);
  assert.equal(A.ejecucionesDeDatos(fx('registro_demo.json').lineas).length, 1);
  assert.deepEqual(A.ejecucionesDeDatos(null), []);
  assert.deepEqual(A.ejecucionesDeDatos('x'), []);
  assert.deepEqual(A.ejecucionesDeDatos({}), []);
  const orden = A.ejecucionesDeDatos(agrup);
  assert.ok(orden[0].inicio >= orden[1].inicio, 'más reciente primero');
});

test('rondas de QA: se derivan de las ejecuciones de agentes QA por oferta y etapa; sin QA = sin dato', () => {
  const ej = A.ejecucionesDeDatos(agrup);
  const rondas = A.rondasQaPorEtapa(ej);
  assert.equal(rondas.get('OF-202611-01|D5'), 2);
  assert.equal(rondas.has('OF-202611-02|D6'), false);
  assert.equal(A.rondaDe(ej.find((e) => e.ejecucion_id === 'RUN-20261110-01'), rondas), 2);
  assert.equal(A.rondaDe(ej.find((e) => e.ejecucion_id === 'RUN-20261112-01'), rondas), null);
  assert.equal(A.rondaDe({ rondas_qa: 1, etapas: [], agentes: [], oferta_id: null }, rondas), 1);
});

test('topeCorrida y usoCorrida: null = sin tope; moneda distinta no se compara; tope exacto no excede, tope+1 sí', () => {
  assert.deepEqual(A.topeCorrida(limitesNull), { tope: null, moneda: null, estado: 'sin_tope' });
  assert.equal(A.topeCorrida(null).estado, 'sin_limites');
  assert.deepEqual(A.topeCorrida(limitesTope), { tope: 1500, moneda: 'EUR', estado: 'ok' });
  assert.equal(A.topeCorrida({ valores: { max_budget_por_corrida_agente: 0 } }).tope, null); // 0 = null o PAUSA
  const t = A.topeCorrida(limitesTope);
  assert.equal(A.usoCorrida({ costo: { monto: 1500, moneda: 'EUR' } }, t).excede, false);
  assert.equal(A.usoCorrida({ costo: { monto: 1501, moneda: 'EUR' } }, t).excede, true);
  assert.equal(A.usoCorrida({ costo: { monto: 750, moneda: 'EUR' } }, t).bp, 5000);
  assert.equal(A.usoCorrida({ costo: { monto: 999999, moneda: 'USD' } }, t).estado, 'moneda_distinta');
  assert.equal(A.usoCorrida({ costo: null }, t).estado, 'sin_costo');
  assert.equal(A.usoCorrida({ costo: { monto: 5, moneda: 'EUR' } }, A.topeCorrida(limitesNull)).estado, 'sin_tope');
});

test('costosAcumulados: por agente y etapa, por moneda, con excedidas y sin costo', () => {
  const ej = A.ejecucionesDeDatos(agrup);
  const c = A.costosAcumulados(ej, A.topeCorrida(limitesTope));
  assert.deepEqual(c.total, [{ moneda: 'EUR', monto: 2330 }, { moneda: 'USD', monto: 250 }]);
  assert.equal(c.sinCosto, 1);
  assert.equal(c.excedidas, 1);
  assert.equal(c.porAgente[0].clave, 'd5-qa');
  assert.equal(c.porAgente[0].ejecuciones, 2);
  assert.deepEqual(c.porAgente[0].total, [{ moneda: 'EUR', monto: 230 }]);
  const d5 = c.porEtapa.find((g) => g.clave === 'D5');
  assert.deepEqual([d5.ejecuciones, d5.total[0].monto, d5.maximo.monto], [3, 530, 300]);
  const f1 = c.porEtapa.find((g) => g.clave === 'F1');
  assert.equal(f1.sinCosto, 1);
  assert.deepEqual(f1.total, []); // sin costo registrado: lista vacía, no «0»
  assert.equal(c.porEtapa.find((g) => g.clave === 'D6').excedidas, 1);
  assert.equal(c.porEtapa.find((g) => g.clave === 'D8').excedidas, 0); // USD sin tipo de cambio: no se compara
  const sinTope = A.costosAcumulados(ej, A.topeCorrida(limitesNull));
  assert.equal(sinTope.excedidas, 0);
  assert.deepEqual(A.costosAcumulados([], A.topeCorrida(limitesNull)).total, []);
});

test('costosDeArchivo suma costos.jsonl por origen y moneda; ignora importes inválidos', () => {
  const r = A.costosDeArchivo(fx('registro_demo.json').costos);
  assert.deepEqual(r, [{ origen: 'ia', moneda: 'EUR', monto: 412 }]);
  assert.deepEqual(A.costosDeArchivo([{ monto: { monto: 1.5, moneda: 'EUR' }, origen: 'ia' }, null, 'x']), []);
  assert.deepEqual(A.costosDeArchivo(undefined), []);
});

test('filtrarEjecuciones y opcionesDeFiltro', () => {
  const m = A.modeloAgentes(agrup, { limites: limitesTope, ofertas });
  assert.equal(m.ejecuciones.length, 7);
  assert.equal(A.filtrarEjecuciones(m.ejecuciones, { oferta: 'OF-202611-01' }).length, 5);
  assert.equal(A.filtrarEjecuciones(m.ejecuciones, { etapa: 'D5', agente: 'd5-qa' }).length, 2);
  assert.equal(A.filtrarEjecuciones(m.ejecuciones, { modo: 'live' }).length, 2);
  assert.equal(A.filtrarEjecuciones(m.ejecuciones, { modo: 'fixture' }).length, 4); // las dry_run de la oferta demo
  assert.equal(A.filtrarEjecuciones(m.ejecuciones, { estado: 'error' }).length, 1);
  assert.equal(A.filtrarEjecuciones(m.ejecuciones, {}).length, 7);
  assert.deepEqual(m.filtros.etapas, ['D5', 'D6', 'D7', 'D8', 'F1']);
  assert.ok(m.filtros.modos.includes('fixture') && m.filtros.modos.includes('live') && m.filtros.modos.includes('dry_run'));
  assert.equal(m.tope.tope, 1500);
  assert.equal(m.hayDatos, true);
  assert.equal(A.modeloAgentes([], {}).hayDatos, false);
  assert.equal(A.modeloAgentes(undefined, {}).hayDatos, false);
});

test('normalizarEvento es idempotente (línea cruda o ya normalizada)', () => {
  const crudo = fx('detalle_RUN-20261110-01.json').eventos[1];
  const a = A.normalizarEvento(crudo);
  const b = A.normalizarEvento(a);
  assert.deepEqual(a, b);
  assert.equal(a.estado, 'ok');
  assert.equal(a.herramienta, 'Bash');
  assert.equal(A.normalizarEvento(null), null);
  assert.equal(A.normalizarEvento({ resultado: 'x' }).estado, null);
});

// ───────────── render con DOM falso ─────────────

function ctxDe({ lista = agrup, limites = limitesTope, detalle = null, vacio = false, falla = {} } = {}) {
  const llamadas = [];
  const api = {
    sobre: async (ruta) => {
      llamadas.push(ruta);
      if (falla[ruta]) throw Object.assign(new Error('x'), { codigo: 'no_encontrado', mensaje: 'no existe' });
      const env = (datos, fuente) => ({ datos, fuente, generado_en: '2026-11-14T10:00:00Z', vacio, avisos: [] });
      if (ruta === '/agentes') return env(lista, ['empresa/registro.jsonl', 'empresa/costos.jsonl']);
      if (ruta === '/parametros') return env({ limites }, ['empresa/limites.yaml']);
      if (ruta.startsWith('/agentes/') && detalle) return env(detalle, ['empresa/registro.jsonl']);
      if (ruta.startsWith('/oferta/')) return env(fx('oferta_OF-202611-01.json'), ['ofertas/OF-202611-01']);
      throw Object.assign(new Error('x'), { codigo: 'no_encontrado', mensaje: 'x' });
    },
  };
  const estado = { ofertas };
  return { ctx: { api, ui, fmt, estado, params: {}, ruta: 'agentes', recargar() {}, navegar() {}, alSalir() {} }, llamadas };
}

test('render: tarjetas, tabla de ejecuciones, costos y avisos del tope', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/agentes.js');
    assert.equal(pagina.meta.ruta, 'agentes');
    assert.ok(pagina.meta.escucha.includes('registro'));
    const { ctx } = ctxDe();
    const raiz = await pagina.render(ctx);
    const t = texto(raiz);
    assert.match(t, /Ejecuciones/);
    assert.match(t, /RUN-20261110-01/);
    assert.match(t, /IA que revisa: Página de venta, pago y medición/);
    assert.match(t, /Datos de prueba/);
    assert.match(t, /En real/);
    assert.match(t, /Excede el tope/);
    assert.match(t, /A dónde va el costo/);
    assert.match(t, /sin costo/); // la ejecución sin costo no se muestra como 0
    assert.equal(porTag(raiz, 'script').length, 0);
    // fila de error resaltada
    assert.ok(todos(raiz, (n) => n.localName === 'tr' && /fila-error/.test(n.className)).length >= 2);
  } finally { restaurar(); }
});

test('render sin tope en limites: avisa que nada gasta hasta fijarlo y no compara', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/agentes.js');
    const { ctx } = ctxDe({ limites: limitesNull });
    const raiz = await pagina.render(ctx);
    const t = texto(raiz);
    assert.match(t, /El tope de costo por ejecución está sin fijar/);
    assert.match(t, /sin tope fijado/);
    assert.doesNotMatch(t, /Excede el tope/);
  } finally { restaurar(); }
});

test('render del registro crudo (líneas) agrupa en el cliente; vacío → estado vacío con comando', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/agentes.js');
    const crudo = await pagina.render(ctxDe({ lista: fx('registro_demo.json') }).ctx);
    assert.match(texto(crudo), /RUN-20261106-01/);
    const vacio = await pagina.render(ctxDe({ lista: [], vacio: true }).ctx);
    const t = texto(vacio);
    assert.match(t, /Todavía no hay ejecuciones de agentes en el historial/);
    assert.match(t, /engine\.registro verificar/);
    assert.match(t, /empresa\/registro\.jsonl/);
    assert.ok(porClase(vacio, 'comando').length >= 1);
  } finally { restaurar(); }
});

test('clic en una fila abre el detalle con su línea de eventos y el QA de la etapa; el texto hostil queda como texto', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/agentes.js');
    const { ctx, llamadas } = ctxDe({ detalle: fx('detalle_RUN-20261110-01.json') });
    const raiz = await pagina.render(ctx);
    const fila = todos(raiz, (n) => n.localName === 'tr' && (n.eventos.click || []).length && /RUN-20261110-01/.test(n.textContent))[0];
    assert.ok(fila, 'hay una fila clicable de RUN-20261110-01');
    fila.dispararEvento('click');
    await new Promise((r) => setTimeout(r, 20));
    assert.ok(llamadas.includes('/agentes/RUN-20261110-01'));
    assert.ok(llamadas.includes('/oferta/OF-202611-01'));
    const t = texto(globalThis.document.body); // el detalle se abre en un diálogo
    assert.match(t, /Qué pasó, paso a paso \(3\)/);
    assert.match(t, /Escribe la landing en 05-landing\/sitio/);
    assert.ok(t.includes('validar_esquemas oferta <b>x</b>'), 'el HTML de un resumen se ve como texto');
    assert.equal(porTag(globalThis.document.body, 'b').length, 0);
    assert.match(t, /Revisión de calidad de la etapa .* en esta oferta/);
    assert.match(t, /Aprobado con notas/);
    assert.match(t, /Duración/);
    assert.match(t, /7 min 30 s/);
  } finally { restaurar(); }
});

test('detalle: si falla la API del detalle usa los eventos de la lista; sin eventos → error con reintento', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/agentes.js');
    const conEventos = agrup.map((x, i) => (i === 0 ? { ...x, eventos: fx('detalle_RUN-20261110-01.json').eventos } : x));
    const a = ctxDe({ lista: conEventos, falla: { '/agentes/RUN-20261110-01': true } });
    const raiz = await pagina.render(a.ctx);
    todos(raiz, (n) => n.localName === 'tr' && (n.eventos.click || []).length && /RUN-20261110-01/.test(n.textContent))[0].dispararEvento('click');
    await new Promise((r) => setTimeout(r, 20));
    assert.match(texto(globalThis.document.body), /Qué pasó, paso a paso \(3\)/);
    cerrarModales();
    const b = ctxDe({ falla: { '/agentes/RUN-20261112-01': true } });
    const raiz2 = await pagina.render(b.ctx);
    todos(raiz2, (n) => n.localName === 'tr' && (n.eventos.click || []).length && /RUN-20261112-01/.test(n.textContent))[0].dispararEvento('click');
    await new Promise((r) => setTimeout(r, 20));
    assert.ok(porClase(globalThis.document.body, 'error-box').length >= 1);
    cerrarModales();
  } finally { restaurar(); }
});


// ───────────── rediseño U4 ─────────────

test('nombreAgente / nombreEtapa / estadoEjecucion / puntosRonda: lenguaje humano con el código aparte', () => {
  assert.equal(A.nombreAgente('d1-maker'), 'IA que prepara: Descubrimiento');
  assert.equal(A.nombreAgente('x1-qa'), 'IA que revisa: Cumplimiento');
  assert.equal(A.nombreAgente('motor'), 'El sistema automático');
  assert.equal(A.nombreAgente('script:activar'), 'Tarea automática: activar');
  assert.equal(A.nombreEtapa('D5'), 'Página de venta, pago y medición');
  assert.equal(A.nombreEtapa('ZZ'), 'ZZ');
  assert.deepEqual(A.estadoEjecucion('bloqueado'), { texto: 'Bloqueada', tono: 'error', icono: 'candado' });
  assert.equal(A.estadoEjecucion(null).tono, 'neutro');
  assert.deepEqual(A.puntosRonda(2).map((p) => p.llena), [true, true, false]);
  assert.equal(A.puntosRonda(null), null);
});

test('serieCostoPorCorrida: cronológica; sin costo = hueco (nunca 0)', () => {
  const m = A.modeloAgentes(agrup, { limites: limitesTope, ofertas, fuente: [] });
  const s = A.serieCostoPorCorrida(m.ejecuciones, m.tope.moneda);
  assert.equal(s.serie.length, m.ejecuciones.length);
  assert.ok(s.serie.every((p, i, a) => i === 0 || a[i - 1].x <= p.x), 'ordenada de más antigua a más reciente');
  assert.ok(s.serie.some((p) => p.y === null), 'la ejecución sin costo queda como hueco');
  assert.ok(s.serie.every((p) => p.y === null || p.y >= 0));
});

test('atencionAgentes: errores = crítico; tope sin fijar = aviso con acción; sin datos = vacío', () => {
  const m = A.modeloAgentes(agrup, { limites: limitesNull, ofertas, fuente: [] });
  const a = A.atencionAgentes(m);
  assert.equal(a[0].tono, 'critico');
  const tope = a.find((x) => /tope de costo por ejecución aún no está fijado/.test(x.titulo));
  assert.ok(tope && /parametros/.test(tope.accion.ruta));
  assert.deepEqual(A.atencionAgentes(A.modeloAgentes([], { limites: limitesNull })), []);
});

test('render: gráfico del costo por corrida con el tope y ranking por agente y por etapa', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/agentes.js');
    const raiz = await pagina.render(ctxDe().ctx);
    const t = texto(raiz);
    assert.match(t, /Lo que costó cada ejecución/);
    assert.match(t, /Requiere tu atención/);
    assert.ok(porClase(raiz, 'p5-ranking').length === 2, 'por agente y por etapa');
    assert.ok(porClase(raiz, 'p5-viz__svg').length >= 1);
  } finally { restaurar(); }
});
