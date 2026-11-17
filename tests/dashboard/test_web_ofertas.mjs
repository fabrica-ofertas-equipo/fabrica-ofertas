// Pruebas de la lógica pura de #/ofertas (dashboard/web/lib/ofertas.js). Sin DOM, sin red.
// Ejecutar: node --test tests/dashboard/test_web_ofertas.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import * as L from '../../dashboard/web/lib/ofertas.js';

const AQUI = dirname(fileURLToPath(import.meta.url));
const FIX = join(AQUI, '..', 'fixtures', 'dashboard', 'ofertas');
const leer = (n) => JSON.parse(readFileSync(join(FIX, n), 'utf8'));
const lista = leer('ofertas.json').datos;
const filas = L.filasOfertas(lista);
const por = (id) => filas.find((f) => f.id === id);

test('filasOfertas: una fila por oferta, la demo marcada y al final aunque sea la más antigua o reciente', () => {
  assert.equal(filas.length, 4);
  assert.equal(filas[filas.length - 1].id, '_ejemplo');
  assert.equal(filas[filas.length - 1].demo, true);
  // resto por actualización descendente
  assert.deepEqual(filas.slice(0, 3).map((f) => f.id), ['OF-202611-03', 'OF-202611-04', 'OF-202611-02']);
});

test('fila de la demo: fase, nivel, avance, gate pendiente y dinero', () => {
  const d = por('_ejemplo');
  assert.equal(d.faseRotulo, 'en construcción');
  assert.equal(d.faseTono, 'info');
  assert.equal(d.nivel, 'N2');
  assert.equal(d.resumen.aprobadas, 7);
  assert.equal(d.resumen.total, 10);
  assert.deepEqual(d.gatesPendientes, ['D7']);
  assert.deepEqual(d.gastoAcumulado, { monto: 0, moneda: 'EUR' });
  assert.deepEqual(d.costoIa, { monto: 412, moneda: 'EUR' });
  assert.equal(d.pipeline.length, 11);
  assert.equal(d.pipeline.find((e) => e.id === 'D7').estado, 'en_QA');
});

test('oferta sin etapas: «sin datos», no 0 % inventado como avance real', () => {
  const o = por('OF-202611-02');
  assert.equal(o.resumen.sinDatos, true);
  assert.match(L.descripcionBarra(o), /Sin estado por etapa/);
});

test('dinero no utilizable queda en null, nunca en 0', () => {
  const o = por('OF-202611-04');
  assert.equal(o.gastoHoy, null);
  assert.equal(o.costoIa, null);
  assert.deepEqual(o.gastoAcumulado, { monto: 0, moneda: 'PLN' });
  assert.equal(L.dineroValido({ monto: 1.5, moneda: 'EUR' }), null); // nada de float
  assert.equal(L.dineroValido({ monto: 5, moneda: '' }), null);
  assert.equal(L.dineroValido({ monto: '5', moneda: 'EUR' }), null);
  assert.equal(L.dineroValido(null), null);
  assert.deepEqual(L.dineroValido({ monto: 0, moneda: 'EUR' }), { monto: 0, moneda: 'EUR' });
});

test('sumarPorMoneda nunca mezcla monedas y salta lo inválido', () => {
  const s = L.sumarPorMoneda([{ monto: 100, moneda: 'EUR' }, { monto: 50, moneda: 'EUR' }, { monto: 7, moneda: 'USD' }, null, { monto: 1.2, moneda: 'EUR' }, { moneda: 'EUR' }]);
  assert.deepEqual(s, { EUR: 150, USD: 7 });
  assert.deepEqual(L.sumarPorMoneda([]), {});
});

test('listaDeOfertas acepta array, {ofertas} y basura', () => {
  assert.equal(L.listaDeOfertas([{ oferta_id: 'a' }, null, 3]).length, 1);
  assert.equal(L.listaDeOfertas({ ofertas: [{ oferta_id: 'a' }] }).length, 1);
  assert.deepEqual(L.listaDeOfertas(null), []);
  assert.deepEqual(L.listaDeOfertas('x'), []);
  assert.deepEqual(L.filasOfertas(leer('ofertas_vacio.json').datos), []);
});

test('filaOferta tolera registros mínimos o corruptos', () => {
  const f = L.filaOferta({});
  assert.equal(f.id, '');
  assert.equal(f.demo, false);
  assert.equal(f.faseRotulo, 'sin dato');
  assert.equal(f.pipeline.length, 11);
  assert.deepEqual(f.gatesPendientes, []);
  assert.equal(f.actualizadoEn, null);
  const g = L.filaOferta({ oferta_id: 'X', etapas: 'no', gates_pendientes: 'no', gasto: 5, costo_ia: [], fase: 7 });
  assert.equal(g.gastoHoy, null);
  assert.equal(g.pipeline.length, 11);
});

test('filtrarOfertas: texto, fase, nivel, demo y atajos', () => {
  assert.equal(L.filtrarOfertas(filas, {}).length, 4);
  assert.deepEqual(L.filtrarOfertas(filas, { texto: '202611-03' }).map((f) => f.id), ['OF-202611-03']);
  assert.deepEqual(L.filtrarOfertas(filas, { texto: ' FAM-202611-04 ' }).map((f) => f.id), ['OF-202611-04']);
  assert.deepEqual(L.filtrarOfertas(filas, { fase: 'en_test' }).map((f) => f.id), ['OF-202611-03']);
  assert.deepEqual(L.filtrarOfertas(filas, { nivel: 'N1' }).map((f) => f.id), ['OF-202611-04']);
  assert.equal(L.filtrarOfertas(filas, { demo: 'reales' }).length, 3);
  assert.deepEqual(L.filtrarOfertas(filas, { demo: 'demo' }).map((f) => f.id), ['_ejemplo']);
  assert.deepEqual(L.filtrarOfertas(filas, { texto: 'demo' }).map((f) => f.id), ['_ejemplo']);
  assert.equal(L.filtrarOfertas(filas, { soloGates: true }).length, 2);
  assert.deepEqual(L.filtrarOfertas(filas, { soloPausa: true }).map((f) => f.id), ['OF-202611-03']);
  assert.deepEqual(L.filtrarOfertas(filas, { soloBloqueadas: true }).map((f) => f.id), ['OF-202611-03']);
  assert.deepEqual(L.filtrarOfertas(filas, { fase: 'en_test', nivel: 'N0' }), []);
  assert.deepEqual(L.filtrarOfertas([], { texto: 'x' }), []);
});

test('hayFiltros distingue el estado por defecto', () => {
  assert.equal(L.hayFiltros({}), false);
  assert.equal(L.hayFiltros({ demo: 'todas', texto: '' }), false);
  assert.equal(L.hayFiltros({ texto: 'a' }), true);
  assert.equal(L.hayFiltros({ soloGates: true }), true);
});

test('ordenarOfertas: claves, dirección y demo siempre al final', () => {
  assert.deepEqual(L.ordenarOfertas(filas, 'oferta', 'asc').map((f) => f.id), ['OF-202611-02', 'OF-202611-03', 'OF-202611-04', '_ejemplo']);
  assert.deepEqual(L.ordenarOfertas(filas, 'oferta', 'desc').map((f) => f.id), ['OF-202611-04', 'OF-202611-03', 'OF-202611-02', '_ejemplo']);
  assert.equal(L.ordenarOfertas(filas, 'avance', 'desc')[0].id, 'OF-202611-03'); // 8 de 10
  assert.equal(L.ordenarOfertas(filas, 'gasto', 'desc')[0].id, 'OF-202611-03');
  assert.equal(L.ordenarOfertas(filas, 'gates', 'desc')[0].id, 'OF-202611-04');
  assert.equal(L.ordenarOfertas(filas, 'clave_inexistente', 'desc')[0].id, 'OF-202611-03'); // cae a «actualizado»
  const copia = filas.slice();
  L.ordenarOfertas(filas, 'oferta', 'asc');
  assert.deepEqual(filas, copia); // no muta
});

test('resumenFlota: cuenta reales, suma por moneda y lista los gates de las reales', () => {
  const r = L.resumenFlota(filas);
  assert.equal(r.total, 4);
  assert.equal(r.reales, 3);
  assert.equal(r.demos, 1);
  assert.equal(r.soloDemo, false);
  assert.equal(r.enPausa, 1);
  assert.equal(r.conBloqueo, 1);
  assert.deepEqual(r.gatesPendientes, [{ oferta: 'OF-202611-04', etapa: 'M1', demo: false }, { oferta: '_ejemplo', etapa: 'D7', demo: true }]); // como el contador de la barra lateral: cuenta también la demo, marcada
  assert.deepEqual(r.gastoAcumulado, { EUR: 8400, PLN: 0 });
  assert.deepEqual(r.gastoHoy, { EUR: 1250 });
  assert.deepEqual(r.costoIa, { USD: 1530, EUR: 0 }); // el 0 de OF-202611-02 es un dato real; el null de OF-202611-04 no suma
  assert.equal(r.porFase.en_test, 1);
});

test('resumenFlota con solo la demo: lo dice y usa la demo como base', () => {
  const soloDemo = filas.filter((f) => f.demo);
  const r = L.resumenFlota(soloDemo);
  assert.equal(r.soloDemo, true);
  assert.equal(r.reales, 0);
  assert.equal(r.gatesPendientes.length, 1);
  assert.equal(r.gatesPendientes[0].demo, true);
  const vacio = L.resumenFlota([]);
  assert.equal(vacio.total, 0);
  assert.equal(vacio.soloDemo, false);
  assert.deepEqual(vacio.gastoAcumulado, {});
});

test('opcionesFiltro solo ofrece fases y niveles presentes, en orden estable', () => {
  const o = L.opcionesFiltro(filas);
  assert.deepEqual(o.fases, ['borrador', 'en_construccion', 'en_test']);
  assert.deepEqual(o.niveles, ['N0', 'N1', 'N2']);
  assert.deepEqual(L.opcionesFiltro([]), { fases: [], niveles: [] });
  const extra = L.opcionesFiltro([L.filaOferta({ oferta_id: 'x', fase: 'nueva_fase' })]);
  assert.deepEqual(extra.fases, ['nueva_fase']);
});

test('descripcionBarra resume la barra de etapas en texto', () => {
  assert.equal(L.descripcionBarra(por('_ejemplo')), '7 de 10 etapas aprobadas · 1 en curso · espera tu firma en D7');
  const b = L.descripcionBarra(por('OF-202611-03'));
  assert.match(b, /8 de 10 etapas aprobadas/);
  assert.match(b, /1 en curso/);
  assert.match(b, /1 bloqueadas o esperando tu decisión/);
});

test('ids hostiles se conservan como texto en la fila (el render los escapa)', () => {
  const f = L.filaOferta({ oferta_id: '<img src=x onerror=1>', familia_id: 'F‮X', etapas: { D1: 'aprobado' } });
  assert.equal(f.id, '<img src=x onerror=1>');
  assert.equal(L.filtrarOfertas([f], { texto: 'onerror' }).length, 1);
});

test('el filtro de texto ignora tildes y mayúsculas', () => {
  const f = L.filaOferta({ oferta_id: 'OF-1', familia_id: 'FAM-ÁÉ' });
  assert.equal(L.filtrarOfertas([f], { texto: 'fam-ae' }).length, 1);
});

// ───────────────────────── rediseño UX: orden, próximo paso y avisos ─────────────────────────

test('opciones de orden: cada una existe en CLAVES_ORDEN y trae su dirección natural', () => {
  for (const o of L.OPCIONES_ORDEN) {
    const r = L.ordenarOfertas(filas, o.valor, L.direccionDeOrden(o.valor));
    assert.equal(r.length, filas.length, o.valor);
    assert.equal(r[r.length - 1].demo, true, `${o.valor}: la demo sigue al final`);
  }
  assert.equal(L.direccionDeOrden('oferta'), 'asc');
  assert.equal(L.direccionDeOrden('gasto'), 'desc');
  assert.equal(L.direccionDeOrden('no-existe'), 'desc');
  assert.deepEqual(L.ordenarOfertas(filas, 'oferta', 'asc').slice(0, 3).map((f) => f.id), ['OF-202611-02', 'OF-202611-03', 'OF-202611-04']);
});

test('proximoDeFila: la frase humana sale del mapa de etapas sin pedir el detalle', () => {
  const p = L.proximoDeFila(por('_ejemplo'));
  assert.equal(p.titulo, 'D7 · Campaña espera tu firma');
  assert.equal(p.tipo, 'firmar_gate');
  assert.equal(p.accion.modo, 'firmar');
  assert.equal(L.proximoDeFila(por('OF-202611-04')).titulo, 'M1 · Mercado espera tu firma');
  assert.equal(L.proximoDeFila(por('OF-202611-03')).tipo, 'bloqueado');
  assert.equal(L.proximoDeFila(por('OF-202611-02')).tipo, 'sin_estado'); // mapa vacío: no inventa etapas
});

test('extraDeDetalle y conExtra: título legible, mercado y respaldo al id', () => {
  const detalle = { brief: { tema_semilla: 'reincorporación laboral tras una pausa', mercado_objetivo: { locale: 'es-ES', paises_segmentacion: ['ES'], moneda_cobro: 'EUR' } }, mercado: { locale: 'es-ES', paises_segmentacion: ['ES'], moneda_cobro: 'EUR' }, estado: { oferta_id: 'OF-202611-01' } };
  const x = L.extraDeDetalle('_ejemplo', detalle);
  assert.equal(x.titulo, 'Reincorporación laboral tras una pausa');
  assert.equal(x.idMotor, 'OF-202611-01');
  assert.match(x.mercado, /España/);
  assert.equal(x.moneda, 'EUR');
  const f = L.conExtra(por('_ejemplo'), x);
  assert.equal(f.titulo, 'Reincorporación laboral tras una pausa');
  assert.equal(f.tieneExtra, true);
  assert.equal(f.id, '_ejemplo'); // el id de la carpeta no cambia (la ruta usa ese)
  assert.equal(L.filtrarOfertas([f], { texto: 'REINCORPORACIÓN' }).length, 1); // se busca por el nombre legible (sin tildes ni mayúsculas)
  assert.equal(L.filtrarOfertas([f], { texto: 'españa' }).length, 1);
  assert.equal(L.filtrarOfertas([f], { texto: 'OF-202611-01' }).length, 1);
  const sin = L.conExtra(por('_ejemplo'), null);
  assert.equal(sin.titulo, '_ejemplo');
  assert.equal(sin.mercado, null);
  assert.equal(L.extraDeDetalle('x', null).titulo, 'x');
});

test('avisosDeAtencion: pausa y bloqueos antes que firmas, con el destino de cada botón', () => {
  const a = L.avisosDeAtencion(filas);
  assert.ok(a.length >= 4);
  assert.deepEqual(a.map((x) => x.tono).slice(0, 2), ['grave', 'grave']); // lo grave primero para cada oferta
  const firma = a.find((x) => x.titulo === 'D7 · Campaña espera tu firma');
  assert.equal(firma.accion.texto, 'Ver cómo firmarlo');
  assert.equal(firma.accion.ruta, '#/oferta/_ejemplo?etapa=D7&panel=firmar');
  assert.equal(firma.tono, 'aviso');
  assert.ok(a.some((x) => /en pausa/.test(x.titulo)));
  assert.ok(a.some((x) => /está bloqueada/.test(x.titulo)));
  assert.deepEqual(L.avisosDeAtencion([]), []);
});
