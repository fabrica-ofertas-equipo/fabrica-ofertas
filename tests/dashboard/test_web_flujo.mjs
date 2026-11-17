// test_web_flujo.mjs — lógica pura de #/flujo «Cómo funciona». Ejecutar: node --test tests/dashboard/test_web_flujo.mjs
import test from 'node:test';
import assert from 'node:assert/strict';

import * as F from '../../dashboard/web/lib/flujo.js';
import { RUTAS_MODO_NEGOCIO, rutaPermitida, navDelModo } from '../../dashboard/web/app.js';

const oferta = (id, clave, extra = {}) => ({ id, nombre: id, mercado: 'MX', etapa: { clave, texto: clave, tono: 'info' }, accion_sugerida: { clave: 'mirar' }, ...extra });

test('la división del 13-nov: cada paso con su skill', () => {
  assert.deepEqual(['buscar', 'lanzar', 'test', 'backend', 'renovar'].map((k) => F.POR_CLAVE[k].skill),
    ['buscar-ofertas', 'modelar-y-lanzar-oferta', 'escalar-oferta', 'backend-ofensivo', 'escalar-oferta']);
  assert.equal(F.POR_CLAVE.backend.disparo.tipo, 'auto', 'el backend lo dispara la revisión diaria');
  assert.ok(!JSON.stringify(F.PROCESOS).includes('300 USD'), 'sin frenos de cuenta');
});

test('cada paso tiene skill, disparo, quién decide, qué hace, reglas y a dónde pasa; las flechas unen pasos que existen', () => {
  for (const p of F.PROCESOS) {
    assert.ok(p.skill && p.guia && p.resumen, p.clave);
    assert.ok(F.DISPARO[p.disparo.tipo], `disparo de ${p.clave}`);
    assert.ok(F.QUIEN[p.decide.quien], `quién decide en ${p.clave}`);
    assert.ok(p.hace.length && p.reglas.length, p.clave);
    for (const k of p.pasa_a) assert.ok(F.POR_CLAVE[k], `${p.clave} → ${k}`);
  }
  for (const f of F.FLECHAS) assert.ok(F.POR_CLAVE[f.de] && F.POR_CLAVE[f.a], `${f.de} → ${f.a}`);
  for (const b of F.BRECHAS) assert.ok(F.POR_CLAVE[b.paso] && ['alta', 'media', 'baja'].includes(b.gravedad) && b.cierre, b.id);
  for (const r of F.REGLAS) assert.ok(F.POR_CLAVE[r.paso] && ['firmada', 'propuesta', 'falta'].includes(r.estado) && r.situacion, r.id);
  assert.equal(new Set(F.REGLAS.map((r) => r.id)).size, F.REGLAS.length, 'ids de regla únicos');
  const c = F.contarReglas();
  assert.equal(c.firmada + c.propuesta + c.falta, F.REGLAS.length);
  assert.equal(F.REGLAS.find((r) => r.id === 'R1').estado, 'firmada', 'el corte del test está firmado');
  assert.equal(F.REGLAS.find((r) => r.id === 'R4').estado, 'firmada', 'el corte post-test lo firmó el dueño el 13-nov');
  assert.equal(F.REGLAS.find((r) => r.id === 'E2').estado, 'firmada', 'el surfeo lo firmó el dueño el 13-nov');
  assert.deepEqual(F.brechasOrdenadas().map((b) => b.gravedad).filter((g, i, a) => a.indexOf(g) === i), ['alta', 'media', 'baja']);
});

test('repartir: cada etapa cae en su paso; las que pasaron el test aparecen también en backend; escalar pide tu OK', () => {
  const r = F.repartir([
    oferta('prog', 'programada'), oferta('t1', 'test'), oferta('cruzada', 'apagar'), oferta('off', 'apagada'),
    oferta('gana', 'renovando', { accion_sugerida: { clave: 'escalar' }, backend: { estado: 'activo' } }),
    oferta('sinbe', 'aprobada', { backend: { estado: 'no', falta: true } }),
    { id: 3 }, null,
  ], [{ carpeta: '_borrador-xx', titulo: 'Nueva', fases_hechas: 4, fases_total: 12 }]);
  assert.deepEqual(r.lanzar.map((o) => o.id), ['_borrador-xx', 'prog']);
  assert.equal(r.lanzar[0].etiqueta, 'armando · 4/12');
  assert.equal(r.lanzar[0].enlace, null, 'una oferta en armado no tiene ficha todavía');
  assert.deepEqual(r.test.map((o) => o.id), ['t1']);
  assert.deepEqual(r.apagar.map((o) => [o.id, o.urgente, o.tono]), [['cruzada', true, 'info'], ['off', false, 'pausada']]);
  assert.deepEqual(r.renovar.map((o) => o.id), ['gana', 'sinbe']);
  assert.equal(r.renovar[0].urgente, false);
  assert.equal(r.renovar[0].etiqueta, 'escalando sola', 'escalar ya es automático (E1-E3)');
  assert.deepEqual(r.backend.map((o) => [o.id, o.etiqueta, o.urgente]), [['gana', 'backend activo', false], ['sinbe', 'falta backend', true]]);
  assert.equal(r.test[0].enlace, '#/negocio/t1');
});

test('saludDe: vigilancia vieja en rojo, banco que no alcanza en ámbar, oferta cruzada sin apagar en rojo', () => {
  const r = F.repartir([oferta('cruzada', 'apagar'), oferta('sinbe', 'aprobada', { backend: { estado: 'no' } })]);
  const s = F.saludDe(r, { vigilancia: { existe: true, salud: 'error', edad_min: 300 }, banco: { veredicto: 'HAY QUE BARRER' }, lanzamientos: [{}, {}] });
  assert.equal(s.test.tono, 'error');
  assert.match(s.test.texto, /5 h/);
  assert.equal(s.buscar.tono, 'aviso');
  assert.equal(s.apagar.tono, 'error');
  assert.equal(s.backend.tono, 'aviso');
  assert.equal(s.renovar.tono, 'aviso');
  assert.match(s.aprender.texto, /2 lanzamientos/);
  assert.match(s.buscar.texto, /todavía no corrió/, 'sin informe diario del banco se dice');
  const ok = F.saludDe(F.repartir([]), { vigilancia: { existe: true, salud: 'ok', edad_min: 12 }, banco: { veredicto: 'ALCANZA', listos: ['a', 'b', 'c'] }, buscar_diario: { fecha: '2026-11-14' } });
  assert.equal(ok.test.tono, 'ok');
  assert.equal(ok.buscar.texto, 'Banco con 3 listos');
  assert.equal(F.saludDe(F.repartir([]), {}).test.tono, 'error', 'sin registro de la vigilancia es una alarma');
});

test('horas: minutos, horas y días', () => {
  assert.equal(F.horas(12), '12 min');
  assert.equal(F.horas(130), '2 h');
  assert.equal(F.horas(60 * 50), '2 días');
  assert.equal(F.horas(undefined), '—');
});

test('el modo «negocio» deja abrir «Cómo funciona» y lo pone en el menú', () => {
  assert.ok(RUTAS_MODO_NEGOCIO.includes('flujo'));
  assert.ok(rutaPermitida('negocio', 'flujo'));
  const items = navDelModo('negocio')[0].items.map((i) => i.ruta);
  assert.deepEqual(items, ['negocio', 'flujo']);
});

import * as E from '../../dashboard/web/lib/escenarios.js';

test('escenarios: ids únicos, estado, área y paso válidos; lo urgente sin cubrir va primero', () => {
  assert.equal(new Set(E.ESCENARIOS.map((e) => e.id)).size, E.ESCENARIOS.length);
  for (const e of E.ESCENARIOS) {
    assert.ok(E.ESTADOS_ESC[e.estado], `${e.id}: estado`);
    assert.ok(E.AREAS.includes(e.area), `${e.id}: área`);
    assert.ok(F.POR_CLAVE[e.paso], `${e.id}: paso`);
    assert.ok([1, 2, 3].includes(e.prioridad), `${e.id}: prioridad`);
    assert.ok(e.escenario && e.hoy && e.propuesta, `${e.id}: textos`);
  }
  const c = E.contarEscenarios();
  assert.equal(c.cubierto + c.propuesta + c.construir + c.decidir + c.manos, c.total);
  assert.equal(c.pct, Math.round((100 * c.cubierto) / c.total));
  const o = E.ordenarEscenarios();
  assert.equal(o[0].prioridad, 1);
  assert.notEqual(o[0].estado, 'cubierto');
});
