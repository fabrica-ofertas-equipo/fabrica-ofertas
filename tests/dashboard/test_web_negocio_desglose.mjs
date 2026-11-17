// Pruebas de lib/negocio-desglose.js (modelo de «De dónde sale la ganancia», 15-nov).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { modeloDesglose } from '../../dashboard/web/lib/negocio-desglose.js';

test('palancas por columna, escala de barras y totales de la cartera', () => {
  const dg = { filas: [
    { id: 'a', ganancia_neta: 200, palancas: [{ clave: 'aov', sentido: 'sube' }] },
    { id: 'b', ganancia_neta: -50, palancas: [{ clave: 'compra', sentido: 'baja' }, { clave: 'cpa', sentido: 'baja' }] },
  ] };
  const m = modeloDesglose(dg, { ganancia_neta: 150, neto_menos_meta: 170, gasto_meta: 300, ventas: 12, cpa_medio: 25, equilibrio_medio: 30 });
  assert.equal(m.maxAbs, 200);
  assert.equal(m.filas[1].por.compra.sentido, 'baja');
  assert.equal(m.filas[0].por.ctr, undefined);
  assert.equal(m.total.contra_meta, 170);
  assert.equal(modeloDesglose(null, {}), null);
});
