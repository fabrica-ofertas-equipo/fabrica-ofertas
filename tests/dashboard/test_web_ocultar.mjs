// test_web_ocultar.mjs — «Ocultar info» (dueño, 13-nov: grabar la pantalla sin mostrar los nombres de las ofertas). node --test tests/dashboard/test_web_ocultar.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import * as O from '../../dashboard/web/lib/ocultar.js';

const datos = JSON.parse(readFileSync(fileURLToPath(new URL('../fixtures/dashboard/negocio/negocio.json', import.meta.url)), 'utf8'));

test('términos: nombres, tiendas, productos, anuncios y referentes salen de /negocio', () => {
  const t = O.terminosDeOfertas(datos.ofertas);
  assert.ok(t.nombres.includes('Kit Uno') && t.nombres.includes('kit-uno') && t.nombres.includes('Kit Uno Básico'));
  assert.ok(t.productos.includes('Extra Uno'), 'upsells');
  assert.ok(t.anuncios.some((s) => s.startsWith('A01 |')), 'anuncios');
  assert.ok(t.anuncios.includes('MX | Kit Uno'), 'campaña');
  assert.ok(Object.values(t).every((l) => l.every((s) => s.length >= 3)), 'nada de textos cortos');
  assert.deepEqual(O.terminosDeOfertas(null), { nombres: [], productos: [], anuncios: [], referentes: [] });
});

test('trocear: lo más largo primero, sin mayúsculas, y una campaña con el nombre adentro cuenta también como nombre', () => {
  const re = O.construirPatron({ nombres: ['Kit Uno', 'kit-uno'], anuncios: ['MX | Kit Uno'], productos: [], referentes: [] });
  const p = O.trocear('Campaña MX | Kit Uno y kit uno gastó US$ 28,46', re);
  assert.deepEqual(p.map((x) => [x.texto, x.cats]), [
    ['Campaña ', null], ['MX | Kit Uno', ['anuncios', 'nombres']], [' y ', null], ['kit uno', ['nombres']], [' gastó ', null], ['US$ 28,46', ['dinero']]]);
  assert.equal(O.trocear('−US$ 1.234,50 y 65 USD/día y MX$ 319', re).filter((x) => x.cats).length, 3, 'montos en sus formas');
  assert.equal(O.trocear('ROAS 1,56 × · 12,5 %', re).filter((x) => x.cats).length, 0, 'ROAS y porcentajes quedan');
  assert.equal(O.enmascarar('Kit Uno — Escalar — US$ 3', ['nombres'], re), '••• — Escalar — US$ 3');
  assert.equal(O.enmascarar('Kit Uno — US$ 3', ['nombres', 'dinero'], re), '••• — •••');
  assert.equal(O.enmascarar('Kit Uno', [], re), 'Kit Uno', 'apagado: igual');
  assert.equal(O.trocear('a.b*c (x)', O.construirPatron({ nombres: ['a.b*c (x)'] }))[0].cats[0], 'nombres', 'caracteres especiales escapados');
});

test('dirección sin nombre: ~N con los nombres ocultos y vuelta al id', () => {
  const ids = ['kit-uno', 'mapa-dos', 'camino-tres'];
  assert.equal(O.refOferta('mapa-dos', ids, true), '~2');
  assert.equal(O.refOferta('mapa-dos', ids, false), 'mapa-dos');
  assert.equal(O.refOferta('no-esta', ids, true), 'no-esta');
  assert.equal(O.resolverRef('~3', ids), 'camino-tres');
  assert.equal(O.resolverRef('~9', ids), '~9');
  assert.equal(O.resolverRef('mapa-dos', ids), 'mapa-dos');
});

test('preferencia: lo recordado o, si falta o es raro, apagado con las categorías de nombres', () => {
  const alm = (v) => ({ getItem: () => v });
  assert.deepEqual(O.leerPreferencia(alm(null)), { activo: false, elegidas: ['nombres', 'productos', 'anuncios', 'referentes', 'imagenes'] });
  // lo guardado antes de «imagenes» (sin versión) la recibe prendida; con versión 2 se respeta lo elegido
  assert.deepEqual(O.leerPreferencia(alm('{"activo":true,"elegidas":["nombres","dinero","raro"]}')), { activo: true, elegidas: ['nombres', 'imagenes', 'dinero'] });
  assert.deepEqual(O.leerPreferencia(alm('{"version":2,"activo":true,"elegidas":["nombres","dinero"]}')), { activo: true, elegidas: ['nombres', 'dinero'] });
  assert.equal(O.leerPreferencia(alm('{roto')).activo, false);
});

test('términos (15-nov): sin palabras del panel, con los IDs y con las partes del referente', () => {
  const t = O.terminosDeOfertas([{
    id: 'oferta', nombre: 'Kit Cinco',
    ficha: {
      fan_page: { id: '1000000000000012', nombre: 'Kit Cinco' }, pixel: { id: '1000000000000013', nombre: 'Píxel de Kit Cinco' }, cuenta_publicitaria: 'TU_CUENTA_META',
      referente: { nombre: 'ReferenteA · «Piccoli Maestri d\'Arte» (Italia)', page_id: '700000000000001' },
      campanas: [{ id: '100000000000000014', nombre: 'MX | Kit Cinco | CBO', conjuntos: [{ id: '100000000000000015', nombre: 'MX | Abierto' }] }],
    },
    anuncios: { lista: [{ id: '100000000000000017', creativo_id: '1000000000000505', nombre: 'A08 | Clase lista | P3', conjunto: 'MX | Abierto' }] },
  }]);
  assert.ok(!t.nombres.includes('oferta'), 'una oferta con id «oferta» no tapa la palabra en todo el panel');
  assert.ok(t.nombres.includes('1000000000000012') && t.nombres.includes('1000000000000013') && t.nombres.includes('TU_CUENTA_META'), 'fan page, píxel y cuenta');
  assert.ok(t.referentes.includes('ReferenteA') && t.referentes.includes("Piccoli Maestri d'Arte") && t.referentes.includes('700000000000001'), 'referente por partes y su página');
  assert.ok(!t.referentes.includes('Italia'), 'el país queda a la vista');
  assert.ok(['100000000000000014', '100000000000000015', '100000000000000017', '1000000000000505'].every((x) => t.anuncios.includes(x)), 'IDs de campaña, conjunto, anuncio y creativo');
});

test('carpetas de trabajo (15-nov): el selector y las pantallas por etapa muestran «_borrador-…», que delata el tema', () => {
  assert.deepEqual(O.variantesCarpeta('ofertas/_borrador-oferta-a/'), ['_borrador-oferta-a', 'mx-arte-colorear', 'arte-colorear', 'mx arte colorear', 'arte colorear']);
  assert.deepEqual(O.variantesCarpeta('_funnels'), [], 'carpetas de sistema no');
  assert.deepEqual(O.variantesCarpeta(null), []);
  const t = O.terminosDeCarpetas([{ oferta_id: '_borrador-oferta-h' }, { oferta_id: '_ejemplo' }, { oferta_id: 'OF-202611-91' }, null]);
  assert.ok(t.nombres.includes('_borrador-oferta-h') && t.nombres.includes('kit herencia fr') && t.nombres.includes('OF-202611-91'));
  assert.ok(!t.nombres.includes('_ejemplo'));
  assert.deepEqual(O.trocear('Fuente: ofertas/_borrador-oferta-h (demo)', O.construirPatron(t)).filter((x) => x.cats).map((x) => x.texto), ['_borrador-oferta-h']);
});

test('IDs de Meta sueltos (15-nov): 15-19 cifras cuentan como anuncios aunque no estén en el libro; los montos no', () => {
  const re = O.construirPatron({ nombres: [], productos: [], anuncios: [], referentes: [] });
  assert.deepEqual(O.trocear('R3 anticipada: conjunto 100000000000000872, 10 anuncios', re).filter((x) => x.cats).map((x) => [x.texto, x.cats]), [['100000000000000872', ['anuncios']]]);
  assert.equal(O.trocear('1.234.567.890.123 impresiones y 12345 clics', re).filter((x) => x.cats).length, 0);
});
