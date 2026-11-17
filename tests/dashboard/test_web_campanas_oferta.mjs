// Pruebas de dashboard/web/lib/campanas-oferta.js (Campañas en Meta y línea de tiempo del presupuesto, dueño 16-nov).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { arbol, series, carriles, veredicto, renglones, tonoRoasAov, resumenAutores, horaEn, medianoches } from '../../dashboard/web/lib/campanas-oferta.js';

const d = {
  campanas: [{ id: 'c1', nombre: 'CBO', rol: 'principal', estado: 'ACTIVE', presupuesto: 187, oferta_id: 'x' }, { id: 'c2', nombre: 'Pocket', rol: 'pocket', estado: 'ACTIVE', presupuesto: 500, oferta_id: 'x' }],
  conjuntos: [{ id: 's1', nombre: 'S1', campana: 'c1', estado: 'ACTIVE' }, { id: 's2', nombre: 'S2', campana: 'c2', estado: 'ACTIVE' }],
  anuncios: [{ id: 'a1', nombre: 'A1', conjunto: 's1', campana: 'c1', estado: 'ACTIVE' }, { id: 'a2', nombre: 'A2', conjunto: 's2', campana: 'c2', estado: 'ACTIVE' }],
  dias: [{ fecha: '2026-11-16', id: 'a1', gasto_usd: 100, compras_meta: 0, valor_compras_meta_usd: 0, impresiones: 1000, clics_enlace: 50 },
    { fecha: '2026-11-16', id: 'a2', gasto_usd: 100, compras_meta: 4, valor_compras_meta_usd: 300, impresiones: 1000, clics_enlace: 50 }],
  escala: {
    ultima: { c2: { decision: 'SURFEAR', texto: 'Surfeo', nuevo: 650 } },
    cambios: [
      { cuando: '2026-11-15T23:00:00Z', campana: 'c2', tipo: 'presupuesto', inicio: true, de: null, a: 324, autor: 'sistema' },
      { cuando: '2026-11-16T15:10:00Z', campana: 'c2', tipo: 'presupuesto', de: 324, a: 421, autor: 'a_mano' },
      { cuando: '2026-11-16T14:13:00Z', campana: 'c1', tipo: 'presupuesto', de: 268, a: 187, autor: 'a_mano' }],
    decisiones: [{ cuando: '2026-11-16T18:00:00Z', desde: '2026-11-16T16:00:00Z', hasta: '2026-11-16T18:00:00Z', veces: 3, campana: 'c1', decision: 'MANTENER', texto: 'Mantener', nuevo: null, porque: 'poca muestra' },
      { cuando: '2026-11-16T12:00:00Z', desde: '2026-11-16T12:00:00Z', hasta: '2026-11-16T12:00:00Z', veces: 1, campana: 'c2', decision: 'SURFEAR', texto: 'Surfeo', presupuesto: 324, nuevo: 421, aplicada: false }],
    a_mano: 2, del_sistema: 0, sin_aplicar: [{}],
  },
};

test('árbol con ROAS con AOV y última decisión', () => {
  const a = arbol(d, 50);
  assert.equal(a.length, 2);
  const p = a.find((c) => c.id === 'c2');
  assert.equal(p.roas_aov, 2);           // 4 × 50 ÷ 100
  assert.equal(p.roas, 3);               // valor de Meta 300 ÷ 100
  assert.equal(p.ultima.decision, 'SURFEAR');
  assert.equal(p.hijos[0].hijos[0].id, 'a2');
  assert.equal(tonoRoasAov(2), 'ok'); assert.equal(tonoRoasAov(1.6), 'aviso'); assert.equal(tonoRoasAov(1.2), 'error');
});

test('escalones de presupuesto y geometría', () => {
  const ahora = Date.parse('2026-11-16T20:00:00Z');
  const s = series(d.escala, d.campanas, ahora);
  const p = s.find((x) => x.id === 'c2');
  assert.deepEqual(p.puntos.map((x) => x.v), [324, 421, 500]);
  const c = s.find((x) => x.id === 'c1');
  assert.deepEqual(c.puntos.map((x) => x.v), [268, 187, 187]);     // arranca 6 h antes con el «de»
  const g = carriles(s);
  const cp = g.carriles.find((x) => x.id === 'c2');
  assert.deepEqual(cp.tramos.map((t) => t.v), [324, 421]);
  assert.equal(cp.actual, 500);
  assert.ok(cp.tramos.every((t) => t.izq >= 0 && t.izq + t.ancho <= 100.0001));
  assert.equal(g.carriles.flatMap((x) => x.marcas).length, 3);
  assert.ok(g.carriles.flatMap((x) => x.marcas).some((m) => m.sube && m.autor === 'a_mano'));
  assert.ok(g.ticks.length >= 2);
  // ventana recortada: arranca con el valor vigente
  const v = series(d.escala, d.campanas, ahora, Date.parse('2026-11-16T15:00:00Z'));
  assert.equal(v.find((x) => x.id === 'c2').puntos[0].v, 324);
});

test('renglones: cambios, decisiones fundidas, sin aplicar y filtros', () => {
  const r = renglones(d.escala);
  assert.equal(r.length, 5);
  assert.equal(r[0].titulo, 'Mantener (3 vueltas)');
  assert.ok(r.some((x) => x.titulo === 'Subió de US$ 324 a US$ 421 (+30 %)' && x.quien === 'A mano'));
  assert.ok(r.some((x) => x.sin_aplicar && x.tono === 'error'));
  assert.equal(renglones(d.escala, { filtro: 'a_mano' }).length, 2);
  assert.equal(renglones(d.escala, { filtro: 'decisiones' }).length, 2);
  assert.equal(renglones(d.escala, { campana: 'c1' }).length, 2);
  assert.deepEqual(resumenAutores(d.escala), { a_mano: 2, sistema: 0, sin_aplicar: 1 });
});

test('veredicto de rentabilidad por fila', () => {
  assert.equal(veredicto({ gasto_usd: 1, compras_meta: 0, nivel: 'anuncio' }, 50).clave, 'sin_datos');
  assert.equal(veredicto({ gasto_usd: 30, compras_meta: 0 }, 50).clave, 'mirando');
  assert.equal(veredicto({ gasto_usd: 80, compras_meta: 0 }, 50).clave, 'pierde');
  assert.equal(veredicto({ gasto_usd: 100, compras_meta: 4, roas_aov: 2 }, 50).clave, 'rentable');
  assert.equal(veredicto({ gasto_usd: 100, compras_meta: 3, roas_aov: 1.6 }, 50).clave, 'justo');
  assert.equal(veredicto({ gasto_usd: 100, compras_meta: 2, roas_aov: 1 }, 50).clave, 'pierde');
});

test('eje por hora y media hora, y hora del mercado', () => {
  const ahora = Date.parse('2026-11-16T20:00:00Z');
  const g = carriles(series(d.escala, d.campanas, ahora, ahora - 24 * 3600e3));
  assert.equal(g.mayorH, 1);
  assert.equal(g.menorH, 0.5);
  assert.ok(g.ticks.some((t) => !t.mayor) && g.ticks.some((t) => t.mayor));
  assert.ok(Math.abs(g.ticks.filter((t) => t.mayor).length - g.ticks.filter((t) => !t.mayor).length) <= 1);   // una media hora entre cada hora
  // 15:55 en Argentina son las 19:55 en Madrid (UTC+1) y las 07:55 del día siguiente en Auckland (UTC+13)
  const t = Date.parse('2026-11-16T18:55:00Z');
  assert.equal(horaEn(t, 'America/Argentina/Buenos_Aires').texto, '15:55');
  assert.equal(horaEn(t, 'Europe/Madrid').texto, '19:55');
  assert.deepEqual([horaEn(t, 'Pacific/Auckland').texto, horaEn(t, 'Pacific/Auckland').dia], ['07:55', '17/11']);
  const m = medianoches(Date.parse('2026-11-16T12:00:00Z'), Date.parse('2026-11-17T12:00:00Z'), 'Europe/Madrid');
  assert.equal(m.length, 1);
  assert.equal(m[0].t, Date.parse('2026-11-16T23:00:00Z'));
});

test('estadoCampana: programada, activa, apagada y demás estados', async () => {
  const { estadoCampana } = await import('../../dashboard/web/lib/campanas-oferta.js');
  const ahora = Date.parse('2026-11-17T12:00:00Z');
  assert.equal(estadoCampana({ estado: 'ACTIVE', inicio: '2026-11-18T00:00:00+01:00' }, ahora).clave, 'programada');
  assert.equal(estadoCampana({ estado: 'ACTIVE', inicio: '2026-11-16T00:00:00+01:00' }, ahora).clave, 'activa');
  assert.equal(estadoCampana({ estado: 'ACTIVE' }, ahora).clave, 'activa');
  assert.equal(estadoCampana({ estado: 'PAUSED', inicio: '2026-11-18T00:00:00+01:00' }, ahora).clave, 'pausada');
  assert.equal(estadoCampana({ estado: 'PENDING_REVIEW' }, ahora).clave, 'revision');
  assert.equal(estadoCampana({ estado: 'WITH_ISSUES' }, ahora).clave, 'problemas');
  assert.equal(estadoCampana({}, ahora).clave, 'sin_dato');
});
