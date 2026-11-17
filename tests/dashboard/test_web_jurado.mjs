// test_web_jurado.mjs — lógica pura (lib/jurado.js) y render con DOM falso de #/jurado.
// Ejecutar: node --test tests/dashboard/test_web_jurado.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import * as J from '../../dashboard/web/lib/jurado.js';
import * as C from '../../dashboard/web/lib/n2-comun.js';
import { ui, fmt } from '../../dashboard/web/ui.js';
import { instalarDomFalso, porClase, porTag, texto, todos } from '../fixtures/dashboard/operacion/dom_falso.mjs';
import { apiFalsa, ctxDe, detalleDemo, OFERTA_DEMO, OFERTA_REAL } from '../fixtures/dashboard/n2/api_falsa.mjs';

const lectura = (dato, estado = 'ok') => ({ estado, dato });
const fuente = (ruta) => readFileSync(fileURLToPath(new URL(`../../dashboard/web/${ruta}`, import.meta.url)), 'utf8');
const AVATARES = ['esceptico', 'impulsivo', 'analitico', 'afin'];
const votos = (ad, si, total, extra = {}) => Array.from({ length: total }, (_, i) => ({ ad_name: ad, avatar_id: AVATARES[i % 4] + (i >= 4 ? i : ''), voto: i < si ? 'sí' : 'no', motivo: i === 0 ? 'Me frena el dedo' : null, puntaje_general: 5 + (i % 3), ...extra }));

// ───────────────────────── los 5 pasos y la regla ─────────────────────────

test('los 5 pasos del jurado son los del método, en orden', () => {
  assert.equal(J.PASOS_JURADO.length, 5);
  assert.deepEqual(J.PASOS_JURADO.map((p) => p.n), [1, 2, 3, 4, 5]);
  assert.match(J.PASOS_JURADO[0].titulo, /a ciegas/i);
  assert.match(J.PASOS_JURADO[1].titulo, /vota y explica/i);
  assert.match(J.PASOS_JURADO[2].titulo, /ordena la tanda/i);
  assert.match(J.PASOS_JURADO[3].titulo, /a los 3 días, la verdad/i);
  assert.match(J.PASOS_JURADO[4].titulo, /acierta pesa más/i);
});

test('la regla de apagado: 150 etiquetas, AUC mínimo 0,60 y modo sombra; son hipótesis', () => {
  assert.equal(J.PARAMETROS.etiquetas_min, 150);
  assert.equal(J.PARAMETROS.jurados_por_mercado, 10);
  assert.equal(J.PARAMETROS.auc_min, 0.6);
  assert.match(J.REGLA.texto, /150 votos comprobados/);
  assert.match(J.REGLA.titulo, /se apaga solo si no supera al azar/i);
  assert.match(J.REGLA.sombra, /sombra/);
});

// ───────────────────────── lectura tolerante de jurado.json ─────────────────────────

test('modeloJurado: ausente → sin_archivo; error o ilegible → sin inventar nada', () => {
  for (const l of [lectura(null, 'ausente'), null, undefined]) {
    const m = J.modeloJurado(l);
    assert.equal(m.estado, 'sin_archivo');
    assert.deepEqual([m.votos, m.piezas, m.orden, m.avatares], [[], [], [], []]);
    assert.equal(m.precision, null);
  }
  assert.equal(J.modeloJurado(lectura(null, 'ilegible')).estado, 'ilegible');
  assert.equal(J.modeloJurado(lectura(null, 'truncado')).estado, 'ilegible');
  assert.equal(J.modeloJurado(lectura(null, 'error')).estado, 'error');
});

test('modeloJurado: archivo vacío o con forma desconocida → «vacio», sin votos ni medición', () => {
  for (const dato of [{}, [], { otra: 'cosa' }, 'texto', 7, { votos: [] }]) {
    const m = J.modeloJurado(lectura(dato));
    assert.equal(m.estado, 'vacio', JSON.stringify(dato));
    assert.equal(m.votos.length, 0);
  }
});

test('modeloJurado: lista de votos a secas, con campos con otros nombres y votos sin ad_name descartados', () => {
  const m = J.modeloJurado(lectura([
    { anuncio: 'a1', jurado: 'j1', decision: 'si', razon: 'claro', score: 7 },
    { pieza: 'a1', avatar: 'j2', vota: false },
    { avatar: 'sin-anuncio', voto: true },
    null, 'basura', 5,
  ]));
  assert.equal(m.estado, 'ok');
  assert.equal(m.votos.length, 2);
  assert.deepEqual(m.avatares, ['j1', 'j2']);
  assert.equal(m.piezas.length, 1);
  assert.deepEqual([m.piezas[0].si, m.piezas[0].no, m.piezas[0].total], [1, 1, 2]);
  assert.equal(m.votos[0].motivo, 'claro');
  assert.equal(m.votos[0].puntaje, 7);
});

test('modeloJurado: forma por piezas con votos anidados y voto sin valor reconocible', () => {
  const m = J.modeloJurado(lectura({ piezas: [{ ad_name: 'a1', votos: [{ avatar_id: 'x', voto: 'quizá' }, { avatar_id: 'y', voto: 'no' }] }, { ad_name: 'a2', votos: votos('', 3, 3) }] }));
  assert.equal(m.piezas.find((p) => p.ad === 'a1').sinVoto, 1);
  assert.equal(m.piezas.find((p) => p.ad === 'a1').total, 1);
  assert.equal(m.piezas.find((p) => p.ad === 'a2').si, 3);
});

test('modeloJurado: el orden del archivo manda; sin orden se calcula por votos a favor y se marca como calculado', () => {
  const conOrden = J.modeloJurado(lectura({ votos: votos('a1', 2, 4).concat(votos('a2', 4, 4)), orden: [{ ad_name: 'a1', posicion: 1 }, 'a2'] }));
  assert.equal(conOrden.ordenOrigen, 'archivo');
  assert.deepEqual(conOrden.orden.map((o) => o.ad), ['a1', 'a2']);
  const calculado = J.modeloJurado(lectura({ votos: votos('a1', 2, 4).concat(votos('a2', 4, 4), votos('a3', 4, 4, { puntaje_general: 9 })) }));
  assert.equal(calculado.ordenOrigen, 'calculado');
  assert.deepEqual(calculado.orden.map((o) => o.ad), ['a3', 'a2', 'a1']);
  assert.deepEqual(calculado.orden.map((o) => o.posicion), [1, 2, 3]);
  const otroNombre = J.modeloJurado(lectura({ tanda: ['x', 'y'], votos: [] }));
  assert.deepEqual(otroNombre.orden.map((o) => o.ad), ['x', 'y']);
  assert.equal(otroNombre.estado, 'ok');
});

test('modeloJurado: la medición se lee de varias formas y nunca se rellena', () => {
  const a = J.modeloJurado(lectura({ votos: votos('a1', 1, 2), precision: { auc: '0,61', brier: 0.2, n_etiquetas: 160, baselines: { azar: 0.5, rubrica: { auc: 0.57 } } } }));
  assert.deepEqual([a.precision.auc, a.precision.brier, a.precision.etiquetas], [0.61, 0.2, 160]);
  assert.deepEqual(a.precision.baselines, [{ nombre: 'azar', auc: 0.5 }, { nombre: 'rubrica', auc: 0.57 }]);
  const b = J.modeloJurado(lectura({ AUC: 0.52, etiquetas: 12 }));
  assert.equal(b.precision.auc, 0.52);
  assert.equal(b.precision.brier, null);
  assert.equal(J.modeloJurado(lectura({ votos: votos('a1', 1, 2) })).precision, null);
  const c = J.modeloJurado(lectura({ calibracion: { brier: 'mucho', auc: null, n: 'x' }, votos: votos('a1', 1, 2) }));
  assert.equal(c.precision, null, 'valores no numéricos no cuentan como medición');
});

test('modeloJurado: texto hostil recortado y sin controles; modo, sello e ideas se leen con tope', () => {
  const m = J.modeloJurado(lectura({ modo: 'sombra', sello: 'sha256:abc', generado_en: '2026-11-12T07:00:00Z', ideas: ['canción', { idea: 'demo en 3 pasos' }, 5, null], votos: [{ ad_name: 'a1', avatar_id: 'j1', voto: 'si', motivo: '<b>x</b>\u0007' + 'y'.repeat(900) }] }));
  assert.equal(m.modo, 'sombra');
  assert.equal(m.sello, 'sha256:abc');
  assert.deepEqual(m.ideas, ['canción', 'demo en 3 pasos', '5']);
  assert.ok(m.votos[0].motivo.length <= 300);
  assert.ok(m.votos[0].motivo.startsWith('<b>x</b>'));
  assert.ok(!/\u0007/.test(m.votos[0].motivo));
});

// ───────────────────────── precisión ─────────────────────────

test('evaluarPrecision: antes de 150 etiquetas no se juzga, ni con un AUC espléndido', () => {
  assert.equal(J.evaluarPrecision(null).estado, 'sin_datos');
  assert.equal(J.evaluarPrecision({ auc: null, brier: null, etiquetas: null, baselines: [] }).estado, 'sin_datos');
  const poco = J.evaluarPrecision({ auc: 0.95, brier: 0.1, etiquetas: 149, baselines: [] });
  assert.equal(poco.estado, 'acumulando');
  assert.equal(poco.falta, 1);
  assert.ok(poco.progreso < 1);
  assert.equal(J.evaluarPrecision({ auc: 0.3, brier: null, etiquetas: null, baselines: [] }).estado, 'acumulando');
});

test('evaluarPrecision: con 150 o más — apagar, sombra, útil o sin AUC', () => {
  const ev = (auc, n = 150) => J.evaluarPrecision({ auc, brier: null, etiquetas: n, baselines: [] });
  assert.equal(ev(0.5).estado, 'apagar');
  assert.equal(ev(0.42).estado, 'apagar');
  assert.equal(ev(0.55).estado, 'sombra');
  assert.equal(ev(0.5999).estado, 'sombra');
  assert.equal(ev(0.6).estado, 'util');
  assert.equal(ev(0.8, 400).estado, 'util');
  assert.equal(ev(null).estado, 'sin_auc');
  assert.equal(ev(0.5).tono, 'error');
  assert.match(ev(0.5).titulo, /se apaga/);
  assert.match(ev(0.55).texto, /0,60/);
});

test('papelDelJurado: sin archivo no existe; con archivo empieza en sombra', () => {
  const sin = J.papelDelJurado([{ jurado: J.modeloJurado(null) }]);
  assert.equal(sin.clave, 'sin_jurado');
  assert.match(sin.valor, /sin jurado todavía/i);
  const con = J.papelDelJurado([{ jurado: J.modeloJurado(lectura({ votos: votos('a', 2, 4) })) }]);
  assert.equal(con.clave, 'sombra');
  const apagar = J.papelDelJurado([{ jurado: J.modeloJurado(lectura({ votos: votos('a', 2, 4), precision: { auc: 0.4, etiquetas: 200 } })) }]);
  assert.equal(apagar.clave, 'apagar');
  const util = J.papelDelJurado([{ jurado: J.modeloJurado(lectura({ votos: votos('a', 2, 4), precision: { auc: 0.7, etiquetas: 200 } })) }]);
  assert.equal(util.clave, 'ordena');
  assert.equal(J.papelDelJurado([]).clave, 'sin_jurado');
});

test('resumenJurado y textoVoto', () => {
  const ms = [{ jurado: J.modeloJurado(lectura({ votos: votos('a', 2, 4).concat(votos('b', 1, 4)), precision: { etiquetas: 30 } })) }, { jurado: J.modeloJurado(null) }, { jurado: J.modeloJurado(lectura(null, 'ilegible')) }];
  const r = J.resumenJurado(ms);
  assert.deepEqual([r.ofertas, r.conJurado, r.votos, r.piezas, r.etiquetas, r.ilegibles], [3, 1, 8, 2, 30, 1]);
  assert.equal(J.textoVoto(true), 'sí');
  assert.equal(J.textoVoto(false), 'no');
  assert.equal(J.textoVoto(null), 'sin voto');
});

// ───────────────────────── render ─────────────────────────

function ctxJurado({ ofertas = [OFERTA_DEMO], archivos = {}, falla = {} } = {}) {
  const detalles = Object.fromEntries(ofertas.map((o) => [o.oferta_id, detalleDemo()]));
  const { api, llamadas } = apiFalsa({ ofertas, detalles, archivos, falla });
  return { ctx: ctxDe(ui, fmt, api), llamadas };
}

test('render sin jurado.json (el estado de hoy): pasos, regla, estado vacío con pasos y medición en cero', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/jurado.js');
    assert.equal(pagina.meta.ruta, 'jurado');
    assert.equal(pagina.meta.grupo, 'Jurado');
    assert.equal(pagina.meta.icono, 'balanza');
    const { ctx, llamadas } = ctxJurado();
    const raiz = await pagina.render(ctx);
    const t = texto(raiz);
    assert.match(t, /Jurado: los 10 clientes que votan antes de gastar/);
    assert.match(t, /Estás viendo datos de demostración/);
    for (const p of J.PASOS_JURADO) assert.ok(t.includes(p.titulo), p.titulo);
    assert.match(t, /Se apaga solo si no supera al azar/);
    assert.match(t, /150 votos comprobados o más/);
    assert.match(t, /El jurado todavía no votó nada/);
    assert.match(t, /Todavía no existe el programa que hace esto/);
    assert.match(t, /Sin jurado todavía/);
    assert.match(t, /0 de 150/);
    assert.match(t, /Todavía no hay medición/);
    assert.match(t, /nunca se citan en un anuncio/);
    assert.equal(porClase(raiz, 'n2-pasos5').length, 1);
    assert.equal(todos(raiz, (n) => n.localName === 'li' && n.parentNode && n.parentNode.className.includes('n2-pasos5')).length, 5);
    assert.ok(llamadas.some((l) => l.includes('06-creativos/jurado.json')));
    assert.equal(porClase(raiz, 'n2-tanda').length, 0);
  } finally { restaurar(); }
});

test('render con votos: tanda ordenada, puntos de voto con icono y texto, motivos como texto, AUC y Brier', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/jurado.js');
    const doc = { modo: 'sombra', locale: 'es-ES', generado_en: '2026-11-13T07:00:00Z',
      votos: votos('c01-hueco_img_h1_v1', 7, 10).concat(votos('c02-entrevista_img_h1_v1', 3, 10)), ideas: ['Probar una demostración'],
      precision: { auc: 0.58, brier: 0.23, etiquetas: 42, baselines: { azar: 0.5 } } };
    doc.votos[0].motivo = '<img src=x onerror=alert(1)> ‮ fin';
    const { ctx } = ctxJurado({ archivos: { '_ejemplo|06-creativos/jurado.json': JSON.stringify(doc) } });
    const raiz = await pagina.render(ctx);
    const t = texto(raiz);
    assert.match(t, /Orden de la tanda/);
    assert.match(t, /7 de 10 a favor/);
    assert.match(t, /3 de 10 a favor/);
    assert.match(t, /Por qué votaron así/);
    assert.match(t, /Ideas que propuso el jurado/);
    assert.match(t, /Probar una demostración/);
    assert.match(t, /0,58/);
    assert.match(t, /0,23/);
    assert.match(t, /Reuniendo votos comprobados: 42 de 150/);
    assert.match(t, /Con menos de 150 votos comprobados/);
    assert.match(t, /En sombra/);
    assert.ok(t.includes('<img src=x onerror=alert(1)>'), 'el HTML de un motivo se ve como texto');
    assert.ok(t.includes('⟦U+202E⟧'));
    assert.equal(porTag(raiz, 'img').length, 0);
    assert.equal(porClase(raiz, 'n2-voto').length, 20);
    assert.equal(porClase(raiz, 'n2-voto--si').length, 10);
    assert.equal(porClase(raiz, 'n2-voto--no').length, 10);
    const orden = porClase(raiz, 'n2-tanda__nombre').map((n) => n.textContent);
    assert.deepEqual(orden, ['c01-hueco_img_h1_v1', 'c02-entrevista_img_h1_v1']);
    assert.match(t, /el panel ordena por votos a favor/);
  } finally { restaurar(); }
});

test('render: AUC ≤ 0,5 con 150 etiquetas avisa de que el jurado se apaga', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/jurado.js');
    const doc = { votos: votos('a1', 5, 10), precision: { auc: 0.49, etiquetas: 180 } };
    const { ctx } = ctxJurado({ archivos: { '_ejemplo|06-creativos/jurado.json': JSON.stringify(doc) } });
    const t = texto(await pagina.render(ctx));
    assert.match(t, /no supera al azar: se apaga/i);
    assert.match(t, /El jurado de _ejemplo no supera al azar/);
    assert.match(t, /Para apagar/);
  } finally { restaurar(); }
});

test('render: archivo ilegible o API caída — la pantalla sigue y lo dice', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/jurado.js');
    const roto = ctxJurado({ archivos: { '_ejemplo|06-creativos/jurado.json': '{"votos": [' } });
    const t = texto(await pagina.render(roto.ctx));
    assert.match(t, /No se pudo leer el jurado de _ejemplo/);
    assert.match(t, /no se pudo leer/);
    const vacio = ctxJurado({ archivos: { '_ejemplo|06-creativos/jurado.json': '{}' } });
    const t2 = texto(await pagina.render(vacio.ctx));
    assert.match(t2, /todavía no trae votos ni orden/);
    const caida = ctxJurado({ falla: { '/ofertas': true } });
    caida.ctx.estado.ofertas = [];
    assert.ok(porClase(await pagina.render(caida.ctx), 'error-box').length >= 1);
  } finally { restaurar(); }
});

test('render con dos ofertas: solo una tiene jurado; la otra se cuenta aparte', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/jurado.js');
    const { ctx } = ctxJurado({ ofertas: [OFERTA_DEMO, OFERTA_REAL], archivos: { '_ejemplo|06-creativos/jurado.json': JSON.stringify({ votos: votos('a1', 3, 4) }) } });
    const raiz = await pagina.render(ctx);
    assert.match(texto(raiz), /1 oferta más no tiene jurado todavía/);
    assert.ok(todos(raiz, (n) => n.localName === 'select').length >= 1);
    assert.ok(!/Estás viendo datos de demostración/.test(texto(raiz)), 'hay una oferta real: no es solo demo');
  } finally { restaurar(); }
});

test('la pantalla solo lee y no usa APIs peligrosas', () => {
  for (const ruta of ['pages/jurado.js', 'lib/jurado.js']) {
    const src = fuente(ruta);
    assert.ok(!/innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function|srcdoc/.test(src), ruta);
    assert.ok(!/api\.post|\.post\(|method:\s*['"]POST/.test(src), ruta);
  }
});
