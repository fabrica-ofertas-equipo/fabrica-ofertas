// Pruebas de la lógica pura de #/landing (dashboard/web/lib/landing.js) con fixtures propios (copias de ofertas/_ejemplo).
// Sin DOM, sin red, sin tocar ofertas/ ni empresa/ reales:  node --test tests/dashboard/test_web_landing.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import * as L from '../../dashboard/web/lib/landing.js';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const FX = path.join(AQUI, '..', 'fixtures', 'dashboard', 'landing');
const json = (n) => JSON.parse(readFileSync(path.join(FX, n), 'utf8'));
const texto = (n) => readFileSync(path.join(FX, n), 'utf8');
const clon = (o) => JSON.parse(JSON.stringify(o));

const oferta = json('oferta.json');
const checkout = json('checkout.json');
const assets = json('assets.json');
const tracking = json('tracking.json');
const rutas = json('rutas.json');
const html = texto('index.html');
const htmlMalo = texto('index_incoherente.html');
const detalle = json('oferta_detalle.json');

// ───────────── dinero ─────────────

test('dinero: solo aritmética entera, símbolo y separadores es-ES', () => {
  assert.equal(L.dinero(1990, 'EUR'), '19,90 €');
  assert.equal(L.dinero(790, 'EUR'), '7,90 €');
  assert.equal(L.dinero(5, 'EUR'), '0,05 €');
  assert.equal(L.dinero(0, 'USD'), '0,00 US$');
  assert.equal(L.dinero(123456789, 'GBP'), '1.234.567,89 £');
  assert.equal(L.dinero(-1990, 'EUR'), '-19,90 €');
  assert.equal(L.dinero(1990, 'PLN'), '19,90 PLN');
  assert.equal(L.dinero(5000, 'JPY'), '5.000 JPY', 'JPY no tiene decimales');
  assert.equal(L.dinero(1990, 'EUR', 3), '1,990 €', 'los decimales explícitos mandan');
  assert.equal(L.dinero(1990, undefined), '19,90');
  assert.equal(L.dinero(19.9, 'EUR'), '—', 'un float no es dinero');
  assert.equal(L.dinero('1990', 'EUR'), '—');
  assert.equal(L.dinero(null, 'EUR'), '—');
  assert.equal(L.dinero(Number.MAX_SAFE_INTEGER + 2, 'EUR'), '—');
  assert.equal(L.dinero(1990, 'eur'), '19,90', 'una moneda mal formada no se muestra como código');
});

test('importeAMenor: «19,90» → 1990 con cadenas', () => {
  assert.equal(L.importeAMenor('19,90'), 1990);
  assert.equal(L.importeAMenor('19.9'), 1990);
  assert.equal(L.importeAMenor('19'), 1900);
  assert.equal(L.importeAMenor('7,90'), 790);
  assert.equal(L.importeAMenor('1.234,56'), 123456);
  assert.equal(L.importeAMenor(' 5 '), 500);
  for (const mala of ['', 'abc', '1,234', '19,9,9', '-5', '1e3', null, undefined]) assert.equal(L.importeAMenor(mala), null, String(mala));
});

// ───────────── checks C01–C17 ─────────────

test('catálogo C01–C17 completo y con su falla', () => {
  assert.equal(L.CHECKS_C.length, 17);
  assert.deepEqual(L.CHECKS_C.map((c) => c.id), Array.from({ length: 17 }, (_, i) => `C${String(i + 1).padStart(2, '0')}`));
  assert.ok(L.CHECKS_C.every((c) => c.titulo.length > 10 && /BLOQ|MAYOR/.test(c.falla)));
  assert.equal(L.LEGALES.length, 7);
});

test('idCheckC reconoce C01–C17 y nada más', () => {
  assert.equal(L.idCheckC('C03'), 'C03');
  assert.equal(L.idCheckC('D5-C05'), 'C05');
  assert.equal(L.idCheckC('QA-C17-x'), 'C17');
  for (const no of ['C00', 'C18', 'C1', 'C100', 'L1-CONSENT-PIXEL', 'L1-ESQUEMA', 'D5-H1', '', null, undefined, 'XC03', 'C031']) assert.equal(L.idCheckC(no), null, String(no));
});

test('estadoChecks: sin QA, todo «sin resultado» (nunca ok)', () => {
  const r = L.estadoChecks({});
  assert.equal(r.filas.length, 17);
  assert.ok(r.filas.every((f) => f.estado === 'sin_resultado'));
  assert.equal(r.hayResultadosC, false);
  assert.equal(r.resumen.sinResultado, 17);
  assert.equal(r.resumen.ok, 0);
  assert.deepEqual(r.otros, []);
});

test('estadoChecks: checks_l1 y hallazgos con id C## se mapean; el resto se lista aparte', () => {
  const qa = json('qa_d5_con_c.json');
  const r = L.estadoChecks({ qa });
  const por = Object.fromEntries(r.filas.map((f) => [f.id, f]));
  assert.equal(por.C01.estado, 'ok');
  assert.equal(por.C02.estado, 'error');
  assert.ok(por.C02.detalle.includes('bump'));
  assert.equal(por.C03.estado, 'ok');
  assert.equal(por.C04.estado, 'no_aplica');
  assert.equal(por.C05.estado, 'ok', 'D5-C05 cuenta como C05');
  assert.equal(por.C10.estado, 'error', 'hallazgo BLOQUEANTE abierto');
  assert.equal(por.C12.estado, 'aviso', 'hallazgo MAYOR abierto');
  assert.equal(por.C11.estado, 'ok', 'hallazgo cerrado por el QA no es una falla');
  assert.equal(por.C06.estado, 'sin_resultado');
  assert.equal(por.C17.estado, 'sin_resultado');
  assert.equal(r.hayResultadosC, true);
  assert.deepEqual(r.otros.map((o) => o.id), ['L1-ESQUEMA']);
  assert.equal(r.otrosHallazgos.length, 1);
  assert.equal(r.otrosHallazgos[0].id, 'D5-H9');
  assert.ok(r.otrosHallazgos[0].descripcion.includes('⟦U+202E⟧'), 'texto del QA neutralizado');
  assert.equal(r.resumen.total, 17);
  assert.equal(r.resumen.error + r.resumen.aviso + r.resumen.ok + r.resumen.noAplica + r.resumen.sinResultado, 17);
});

test('estadoChecks: el QA del ejemplo usa L1-* y no inventa C##', () => {
  const r = L.estadoChecks({ qa: json('qa_d5_ejemplo.json'), x1: json('qa_x1_d5_ejemplo.json') });
  assert.equal(r.hayResultadosC, false);
  assert.ok(r.filas.every((f) => f.estado === 'sin_resultado'));
  assert.ok(r.otros.length >= 2, 'los L1-* se listan tal cual');
  assert.ok(r.otros.some((o) => o.id === 'L1-ESQUEMA' && o.resultado === 'ok'));
});

test('estadoChecks: un fail gana a un pass del mismo check (dos fuentes)', () => {
  const qa = { checks_l1: [{ check_id: 'C07', resultado: 'pass', detalle: 'ok' }] };
  const x1 = { checks_l1: [{ check_id: 'C07', resultado: 'fail', detalle: 'webhook sin firma' }] };
  const r = L.estadoChecks({ qa, x1 });
  assert.equal(r.filas.find((f) => f.id === 'C07').estado, 'error');
  assert.ok(r.filas.find((f) => f.id === 'C07').detalle.includes('Cumplimiento'));
  assert.equal(L.estadoChecks({ qa: 'x', x1: [] }).resumen.sinResultado, 17);
  assert.equal(L.estadoChecks({ qa: { checks_l1: 'x', hallazgos: 5 } }).resumen.sinResultado, 17);
});

test('elegirQaD5: el último d5-v<n> y x1-d5-v<n> (comparación numérica, no de texto)', () => {
  const q = L.elegirQaD5(detalle.etapas[0].qa);
  assert.equal(q.d5.archivo, 'qa/d5-v2.json');
  assert.equal(q.x1.archivo, 'qa/x1-d5-v10.json');
  assert.deepEqual(L.elegirQaD5([]), { d5: null, x1: null });
  assert.deepEqual(L.elegirQaD5(null), { d5: null, x1: null });
  assert.equal(L.elegirQaD5([{ archivo: 'qa/d6-v1.json' }]).d5, null, 'otros dictámenes no son de D5');
});

test('resumenQa y tonoVeredicto', () => {
  const r = L.resumenQa(json('qa_d5_ejemplo.json'));
  assert.equal(r.veredicto, 'PASS');
  assert.equal(r.puntaje, '4.40');
  assert.equal(r.x1.veredicto, 'PASS');
  assert.equal(L.resumenQa(null), null);
  assert.equal(L.resumenQa({}), null);
  assert.deepEqual(['PASS', 'PASS_CON_NOTAS', 'FAIL', 'ESCALAR', 'otro'].map(L.tonoVeredicto), ['ok', 'aviso', 'error', 'error', 'neutro']);
});

// ───────────── HTML ─────────────

test('analizarHtml: lee atributos, meta, scripts y bloques sin ejecutar nada', () => {
  const a = L.analizarHtml(html);
  assert.equal(a.vacio, false);
  assert.equal(a.lang, 'es-ES');
  assert.ok(a.title.includes('Puente de la Pausa'));
  assert.equal(a.body['data-precio-minor'], '1990');
  assert.equal(a.body['data-moneda'], 'EUR');
  assert.equal(a.body['data-garantia-dias'], '14');
  assert.ok(a.scripts.some((s) => s.src === '/js/consentimiento.js'));
  assert.ok(a.enlaces.some((e) => e.url === '/comprar'));
  assert.ok(a.meta.some((m) => m.clave === 'og:image'));
  assert.ok(a.comentarios.some((c) => c.includes('[EJEMPLO]')));
  assert.ok(a.texto.includes('19,90 €'));
  assert.ok(!a.texto.includes('<'), 'el texto visible no conserva etiquetas');
  assert.ok(a.texto.includes('soporte@miregresolaboral.example'), 'las entidades se decodifican');
});

test('analizarHtml: HTML vacío, roto o hostil no lanza', () => {
  for (const x of [null, undefined, '', '   ', 5, {}]) assert.equal(L.analizarHtml(x).vacio, true);
  const roto = L.analizarHtml('<p>sin cerrar <b>x<script>alert(1)</scr');
  assert.equal(roto.vacio, false);
  const hostil = L.analizarHtml('<script>document.write("x")</script><p>hola‮</p><!-- <script>evil()</script> -->');
  assert.equal(hostil.scripts.length, 1);
  assert.ok(hostil.texto.includes('hola'));
  assert.ok(!hostil.texto.includes('document.write'), 'el contenido de <script> no es texto visible');
  assert.ok(hostil.texto.includes('⟦U+202E⟧'));
  const grande = L.analizarHtml('<p>' + 'a'.repeat(900000) + '</p>');
  assert.ok(grande.texto.length <= 600, 'los bloques de texto se acotan');
});

test('analizarHtml: entradas hostiles de 400 KB terminan en < 200 ms (sin ReDoS cuadrático, revisión de seguridad m-1)', () => {
  const casos = {
    'comentarios sin cierre': '<!--'.repeat(100000),
    'script sin cierre': '<script>'.repeat(50000),
    'title sin cierre': '<title>'.repeat(57000),
    'style sin cierre': '<style>'.repeat(57000),
    '«<» sin «>»': '<'.repeat(400000),
    'etiquetas de bloque abiertas': '<p '.repeat(130000),
    'cierre de script falso': `<script>${'</script '.repeat(50000)}`,
    'comentarios vacíos cerrados': '<!---->'.repeat(57000),
  };
  for (const [nombre, h] of Object.entries(casos)) {
    const t0 = performance.now();
    const a = L.analizarHtml(h);
    L.indiciosHtml(a);
    L.coherencia({ html: a });
    const ms = performance.now() - t0;
    assert.ok(ms < 200, `${nombre}: ${ms.toFixed(0)} ms`);
  }
});

test('analizarHtml: la extracción lineal da lo mismo que el HTML bien formado (comentarios, scripts, title, estilos)', () => {
  const a = L.analizarHtml('<html lang="es"><head><TITLE>Mi  <b>título</b></TITLE><style>p{color:red}</style><script src="/js/consentimiento.js"></script><script>var x = 1;</script></head>'
    + '<body data-precio-minor="1990"><!-- nota --><p>Hola</p><!----><SCRIPT >alert(1)</SCRIPT ><scripts>no</scripts><p>Fin</p><!-- sin cierre');
  assert.equal(a.lang, 'es');
  assert.equal(a.title, 'Mi <b>título</b>');
  assert.deepEqual(a.comentarios, ['nota', '']);
  assert.equal(a.scripts.length, 3);
  assert.deepEqual(a.scripts.map((s) => s.enLinea), [false, true, true]);
  assert.ok(a.texto.includes('Hola') && a.texto.includes('Fin') && a.texto.includes('no'));
  assert.ok(!a.texto.includes('color:red') && !a.texto.includes('alert(1)') && !a.texto.includes('var x'));
});

test('importesEnTexto: igual que landing.validar (RX_IMPORTE)', () => {
  const i = L.importesEnTexto('Quiero la guía — 19,90 € y 7,90 € más; 12 USD o 5 $');
  assert.deepEqual(i.map((x) => [x.minor, x.moneda]), [[1990, 'EUR'], [790, 'EUR'], [1200, 'USD'], [500, 'USD']]);
  assert.deepEqual(L.importesEnTexto(''), []);
  assert.deepEqual(L.importesEnTexto(null), []);
  assert.deepEqual(L.importesEnTexto('sin importes 2026'), []);
});

test('diasDeGarantiaEnBloques solo mira bloques que hablan de garantía', () => {
  const d = L.diasDeGarantiaEnBloques(['Garantía de 14 días', 'Pensado para 90 días de uso', 'Reembolso en 30 days', 'Te devolvemos el importe durante 14 días']);
  assert.deepEqual(d.map((x) => x.dias), [14, 30, 14]);
  assert.deepEqual(L.diasDeGarantiaEnBloques(null), []);
});

// ───────────── coherencia ─────────────

test('coherencia: el ejemplo es coherente en precio, moneda, garantía, bump e idioma', () => {
  const c = L.coherencia({ oferta, checkout, html });
  assert.equal(c.htmlDisponible, true);
  const por = Object.fromEntries(c.filas.map((f) => [f.campo, f]));
  assert.equal(por['Precio de lista'].estado, 'ok');
  assert.equal(por['Precio de lista'].oferta.texto, '19,90 €');
  assert.equal(por['Precio de lista'].checkout.texto, '19,90 €');
  assert.equal(por['Precio de lista'].html.texto, '19,90 €');
  assert.equal(por['Importes escritos en la página'].estado, 'ok');
  assert.equal(por.Moneda.estado, 'ok');
  assert.equal(por['Garantía (días)'].estado, 'ok');
  assert.equal(por['Oferta extra al pagar (precio)'].estado, 'ok');
  assert.equal(por['Oferta extra al pagar (precio)'].oferta.texto, '7,90 €');
  assert.equal(por['Idioma y país'].estado, 'ok');
  assert.equal(por.Impuestos.checkout.texto, 'modo diferido');
  assert.equal(por.Impuestos.estado, 'ok');
  assert.equal(c.resumen.error, 0);
  assert.ok(c.resumen.ok >= 6);
});

test('coherencia: detecta precio, moneda y garantía distintos en el HTML', () => {
  const c = L.coherencia({ oferta, checkout, html: htmlMalo });
  const por = Object.fromEntries(c.filas.map((f) => [f.campo, f]));
  assert.equal(por['Precio de lista'].estado, 'error');
  assert.equal(por['Precio de lista'].html.texto, '24,90 €');
  assert.equal(por['Importes escritos en la página'].estado, 'error');
  assert.ok(por['Importes escritos en la página'].nota.includes('24,90'));
  assert.equal(por.Moneda.estado, 'error');
  assert.equal(por['Garantía (días)'].estado, 'error');
  assert.ok(c.resumen.error >= 4);
});

test('coherencia: oferta y checkout distintos entre sí', () => {
  const ch = clon(checkout);
  ch.precio.monto = 2290;
  ch.garantia_dias = 7;
  const c = L.coherencia({ oferta, checkout: ch, html });
  const por = Object.fromEntries(c.filas.map((f) => [f.campo, f]));
  assert.equal(por['Precio de lista'].estado, 'error');
  assert.equal(por['Garantía (días)'].estado, 'error');
});

test('coherencia: con «diferido» el HTML no puede decir «IVA incluido»', () => {
  const sucio = html.replace('Pago único.', 'Pago único. IVA incluido.');
  const c = L.coherencia({ oferta, checkout, html: sucio });
  assert.equal(c.filas.find((f) => f.campo === 'Impuestos').estado, 'error');
});

test('coherencia: sin fuentes no se inventa nada (sin dato, no ok)', () => {
  const c = L.coherencia({});
  assert.ok(c.filas.every((f) => f.estado === 'sin_dato' || f.estado === 'ok' === false));
  assert.equal(c.resumen.ok, 0);
  assert.equal(c.htmlDisponible, false);
  const solo = L.coherencia({ oferta });
  assert.equal(solo.filas.find((f) => f.campo === 'Precio de lista').estado, 'sin_dato', 'una sola fuente no es una comparación');
  assert.equal(solo.filas.find((f) => f.campo === 'Precio de lista').checkout.texto, 'sin dato');
  // checkout con float no se acepta como dinero
  const flot = clon(checkout); flot.precio.monto = 19.9;
  assert.equal(L.coherencia({ oferta, checkout: flot, html }).filas[0].checkout.texto, 'sin dato');
});

test('indiciosHtml: el ejemplo solo trae el comentario [EJEMPLO]; el malo trae todo', () => {
  const buenos = L.indiciosHtml(html, { dominio: 'miregresolaboral.example' });
  assert.deepEqual(buenos.filter((x) => x.estado === 'error'), [], 'el ejemplo no tiene fallas duras');
  assert.deepEqual(buenos.filter((x) => x.estado === 'aviso').map((x) => x.titulo), ['Comentario [EJEMPLO]']);
  const m = L.indiciosHtml(htmlMalo, { dominio: 'miregresolaboral.example' });
  const por = (titulo) => m.find((x) => x.titulo === titulo);
  assert.equal(por('Código de otros sitios').estado, 'error');
  assert.ok(por('Código de otros sitios').detalle.includes('cdn.evil.example'));
  assert.equal(por('Código escrito dentro de la página').estado, 'aviso');
  assert.equal(por('Enlaces, imágenes o estilos externos').estado, 'error');
  assert.equal(por('Casillas premarcadas').estado, 'error');
  assert.equal(por('Contadores, cupos o escasez').estado, 'error');
  assert.equal(por('Texto «ejemplo» visible').estado, 'error');
  assert.ok(m.every((x) => /^C\d\d$/.test(x.id)));
  assert.deepEqual(L.indiciosHtml('', {}), []);
  assert.deepEqual(L.indiciosHtml(null, {}), []);
});

test('indiciosHtml: sin dominio todo enlace absoluto cuenta como externo', () => {
  const m = L.indiciosHtml('<a href="https://x.example/">x</a>', {});
  assert.equal(m.find((x) => x.titulo.startsWith('Enlaces')).estado, 'error');
});

// ───────────── rutas ─────────────

test('archivoDeRuta: misma regla que landing.validar y sin escapes', () => {
  assert.equal(L.archivoDeRuta('/'), 'index.html');
  assert.equal(L.archivoDeRuta('/gracias'), 'gracias.html');
  assert.equal(L.archivoDeRuta('/legal/terminos'), 'legal/terminos.html');
  assert.equal(L.archivoDeRuta('/a/plan-en-una-tarde/'), 'a/plan-en-una-tarde.html');
  assert.equal(L.archivoDeRuta('/css/estilos.css'), 'css/estilos.css');
  for (const mala of ['', 'gracias', '/../etc/passwd', '/a/../b', '/a\\b', '/x y', '/x?y=1', '/x%2e%2e', '//evil', 'http://x', null, undefined, '/a\u0000b']) assert.equal(L.archivoDeRuta(mala), null, String(mala));
});

test('ids de oferta: los del servidor (OF-AAAAMM-NN o carpeta demo _ejemplo) y nada más', () => {
  for (const ok of ['OF-202611-01', '_ejemplo', '_demo-2']) assert.equal(L.RE_OFERTA_ID.test(ok), true, ok);
  for (const mal of ['ejemplo', '_', '_Ejemplo', '../x', 'OF-1', 'OF-202611-01/x', '_a b', '_' + 'a'.repeat(40), '']) assert.equal(L.RE_OFERTA_ID.test(mal), false, mal);
  assert.equal(L.RE_OFERTA_REAL.test('OF-202611-01'), true);
  assert.equal(L.RE_OFERTA_REAL.test('_ejemplo'), false);
});

test('urlSitio: solo /sitio/<id>/<archivo>', () => {
  assert.equal(L.urlSitio('OF-202611-01'), '/sitio/OF-202611-01/index.html');
  assert.equal(L.urlSitio('_ejemplo'), '/sitio/_ejemplo/index.html');
  assert.equal(L.urlSitio('OF-202611-01', 'legal/terminos.html'), '/sitio/OF-202611-01/legal/terminos.html');
  for (const [id, a] of [['../x', 'index.html'], ['OF-202611-01', '../index.html'], ['OF-202611-01', '/etc/passwd'], ['OF-202611-01', 'a b.html'], ['', 'index.html'], [null, 'x'], ['OF-202611-01', 'x?y=1']]) {
    assert.equal(L.urlSitio(id, a), null, `${id} ${a}`);
  }
});

test('archivosASondear: solo estáticos, sin duplicados y acotado', () => {
  const a = L.archivosASondear(rutas);
  assert.ok(a.includes('index.html') && a.includes('legal/terminos.html') && a.includes('gracias.html'));
  assert.ok(!a.some((x) => x.includes('crear-sesion') || x.includes('comprar')), 'las rutas dinámicas no se sondean');
  assert.equal(new Set(a).size, a.length);
  assert.equal(L.archivosASondear(rutas, 3).length, 3);
  assert.deepEqual(L.archivosASondear(null), []);
});

test('modeloRutas: 200, error, archivo ausente, dinámicas y legales', () => {
  const sondas = { 'index.html': 200, 'gracias.html': 200, 'legal/vendedor.html': 200, 'legal/terminos.html': 404, 'legal/privacidad.html': 'error' };
  const artefactos = detalle.etapas[0].artefactos;
  const m = L.modeloRutas({ rutas, sondas, artefactos });
  const por = Object.fromEntries(m.filas.map((f) => [f.ruta, f]));
  assert.equal(por['/'].estado, 'ok');
  assert.equal(por['/'].texto, '200');
  assert.equal(por['/legal/terminos'].estado, 'error');
  assert.equal(por['/legal/terminos'].texto, 'HTTP 404');
  assert.equal(por['/legal/privacidad'].estado, 'error');
  assert.equal(por['/comprar'].estado, 'dinamica');
  assert.equal(por['/comprar'].archivo, null);
  assert.equal(por['/legal/cookies'].estado, 'error', 'no está entre los artefactos de la etapa');
  assert.equal(por['/legal/cookies'].texto, 'falta el archivo');
  assert.equal(m.legales.length, 7);
  assert.equal(m.legales.find((l) => l.id === 'vendedor').estado, 'ok');
  assert.equal(m.legales.find((l) => l.id === 'terminos').estado, 'error');
  assert.equal(m.resumen.legalesOk, 1);
  assert.equal(m.resumen.legalesTotal, 7);
});

test('modeloRutas: sin sondas ni artefactos todo queda «sin comprobar»; faltar una legal en rutas.json es error', () => {
  const m = L.modeloRutas({ rutas });
  assert.ok(m.filas.filter((f) => !f.dinamica).every((f) => f.estado === 'sin_comprobar'));
  assert.equal(m.resumen.legalesOk, 0);
  const r2 = clon(rutas); delete r2['/legal/entrega'];
  const m2 = L.modeloRutas({ rutas: r2 });
  assert.equal(m2.legales.find((l) => l.id === 'entrega').estado, 'error');
  assert.equal(m2.legales.find((l) => l.id === 'entrega').texto, 'falta la ruta en el mapa de rutas');
  assert.deepEqual(L.modeloRutas({}).filas, []);
  assert.equal(L.modeloRutas({ rutas: null }).legales.every((l) => l.estado === 'error'), true);
});

// ───────────── assets ─────────────

test('modeloAssets: ranuras pendientes y placeholders', () => {
  const m = L.modeloAssets(assets);
  assert.equal(m.existe, true);
  assert.equal(m.resumen.declaradas, 2);
  assert.equal(m.resumen.aprobadas, 2);
  assert.equal(m.resumen.pendientes, 0);
  assert.equal(m.resumen.placeholders, 2);
  const a = clon(assets);
  a.slots[1].estado = 'vacio'; a.slots[1].archivo = null; a.slots[0].estado = 'asignado';
  const m2 = L.modeloAssets(a);
  assert.equal(m2.resumen.pendientes, 2);
  assert.equal(m2.slots[1].pendiente, true);
  assert.equal(m2.slots[1].archivo, null);
  assert.equal(L.modeloAssets(null).existe, false);
  assert.equal(L.modeloAssets({}).slots.length, 0);
  assert.equal(L.modeloAssets({ slots: [{ estado: 'raro' }] }).slots[0].estado, 'desconocido');
});

// ───────────── checkout y tracking ─────────────

test('modeloCheckout: precio, price ids (live pendiente), bump y consentimientos', () => {
  const m = L.modeloCheckout(checkout);
  assert.equal(m.precio, '19,90 €');
  assert.equal(m.priceTest, 'price_ejemplo_test_principal');
  assert.equal(m.priceLive, null, 'live aún no existe: no se inventa');
  assert.equal(m.bump.precio, '7,90 €');
  assert.equal(m.bump.modo, 'casilla_en_checkout');
  assert.deepEqual(m.metodos, ['card', 'apple_pay', 'google_pay', 'link']);
  assert.equal(m.garantia, 14);
  assert.equal(m.impuestos.modo, 'diferido');
  assert.equal(m.sesionEnServidor, true);
  assert.equal(m.consentimientos[0].obligatorio, true);
  assert.equal(L.modeloCheckout(null), null);
  assert.equal(L.modeloCheckout({}), null);
  assert.equal(L.modeloCheckout({ precio: { monto: 1.5, moneda: 'EUR' }, moneda: 'EUR' }).precio, '—');
});

test('modeloTracking: eventos, consentimiento y coherencia con checkout.metadata', () => {
  const m = L.modeloTracking(tracking, checkout);
  assert.equal(m.pixelId, '999000000000001');
  assert.equal(m.eventos.length, 4);
  assert.deepEqual(m.eventosFaltantes, []);
  assert.deepEqual(m.eventosFueraDeLista, []);
  assert.equal(m.consentimiento.ok, true);
  assert.equal(m.consentimiento.requeridoUeUk, true);
  assert.equal(m.datosSensiblesPermitidos, false);
  assert.equal(m.modoPrueba, true);
  assert.deepEqual(m.utm.faltanEnMetadata, []);
  const t2 = clon(tracking);
  t2.eventos.push({ nombre: 'Lead', canal: 'pixel', event_id_regla: 'x', parametros_permitidos: [] });
  t2.eventos = t2.eventos.filter((e) => e.nombre !== 'Purchase');
  t2.consent_gating.plataforma = 'otra';
  t2.datos_sensibles.permitidos = true;
  const m2 = L.modeloTracking(t2, checkout);
  assert.deepEqual(m2.eventosFueraDeLista, ['Lead']);
  assert.deepEqual(m2.eventosFaltantes, ['Purchase']);
  assert.equal(m2.consentimiento.ok, false);
  assert.equal(m2.datosSensiblesPermitidos, true);
  const ch = clon(checkout); ch.metadata_esquema = ch.metadata_esquema.filter((x) => x !== 'adid');
  assert.deepEqual(L.modeloTracking(tracking, ch).utm.faltanEnMetadata, ['adid']);
  assert.equal(L.modeloTracking(tracking, null).utm.faltanEnMetadata, null, 'sin checkout no se compara');
  assert.equal(L.modeloTracking(null, checkout), null);
});

test('modeloDespliegue', () => {
  const m = L.modeloDespliegue(json('despliegue.json'));
  assert.ok(m.kv.some(([k, v]) => k === 'commit' && v === 'abc1234'));
  assert.ok(!m.kv.some(([k]) => k === 'obj'), 'los objetos anidados no se aplanan');
  assert.deepEqual(m.lighthouse.map(([k]) => k), ['rendimiento', 'accesibilidad']);
  assert.equal(L.modeloDespliegue(null), null);
});

// ───────────── utilidades de la pantalla ─────────────

test('ofertaEfectiva y etapaD5', () => {
  const lista = [{ oferta_id: 'OF-202611-01' }, { oferta_id: 'OF-202611-02' }, { oferta_id: '_ejemplo' }];
  assert.equal(L.ofertaEfectiva('OF-202611-02', lista), 'OF-202611-02');
  assert.equal(L.ofertaEfectiva('_ejemplo', lista), '_ejemplo');
  assert.equal(L.ofertaEfectiva('OF-999999-99', lista), null);
  assert.equal(L.ofertaEfectiva(null, lista), null);
  assert.equal(L.ofertaEfectiva('OF-202611-01', null), null);
  assert.equal(L.etapaD5(detalle).id, 'D5');
  assert.equal(L.etapaD5({}), null);
  assert.equal(L.etapaD5(null), null);
});

test('jsonDeArchivo / textoDeArchivo: aceptan objeto, cadena y sobre de /archivo', () => {
  assert.deepEqual(L.jsonDeArchivo({ contenido: '{"a":1}' }), { a: 1 });
  assert.deepEqual(L.jsonDeArchivo({ contenido: { a: 1 } }), { a: 1 });
  assert.deepEqual(L.jsonDeArchivo({ a: 1 }), { a: 1 });
  assert.equal(L.jsonDeArchivo({ contenido: 'no es json' }), null);
  assert.equal(L.jsonDeArchivo({ contenido: '5' }), null);
  assert.equal(L.jsonDeArchivo(null), null);
  assert.equal(L.textoDeArchivo({ contenido: '<p>x</p>' }), '<p>x</p>');
  assert.equal(L.textoDeArchivo('abc'), 'abc');
  assert.equal(L.textoDeArchivo({ contenido: 5 }), null);
  assert.equal(L.textoDeArchivo(null), null);
});

test('ANCHOS_PREVIEW: móvil, tablet y escritorio', () => {
  assert.deepEqual(L.ANCHOS_PREVIEW.map((a) => a.id), ['movil', 'tablet', 'escritorio']);
  assert.equal(L.ANCHOS_PREVIEW[0].ancho, 390);
  assert.equal(L.ANCHOS_PREVIEW[1].ancho, 768);
  assert.equal(L.ANCHOS_PREVIEW[2].ancho, null);
});

// ───────────── la página carga como módulo ─────────────

test('pages/landing.js: meta, render, iframe con sandbox y sin innerHTML', async () => {
  const ruta = path.join(AQUI, '..', '..', 'dashboard', 'web', 'pages', 'landing.js');
  const mod = await import(ruta);
  assert.equal(mod.meta.ruta, 'landing');
  assert.equal(mod.meta.grupo, 'Fábrica y tienda');
  assert.equal(typeof mod.render, 'function');
  assert.equal(typeof mod.alCambio, 'function');
  const fuente = readFileSync(ruta, 'utf8');
  assert.ok(!/innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function|srcdoc/.test(fuente));
  assert.ok(/sandbox:\s*'allow-scripts'/.test(fuente), 'el iframe va con sandbox="allow-scripts" exacto');
  assert.ok(!/sandbox:\s*'[^']*allow-same-origin/.test(fuente), 'nunca allow-same-origin en el sandbox');
  assert.ok(!/allow-(top-navigation|forms|popups|modals|downloads)/.test(fuente), 'solo allow-scripts');
  assert.ok(!/method:\s*'(POST|PUT|DELETE|PATCH)'/.test(fuente), 'la página no escribe nada');
});

// ───────────── rediseño UX (U3): checklist por grupos, avisos de atención, páginas ─────────────

test('agruparChecks: los 17 C## en cinco grupos, cada uno una sola vez, con nombre humano', () => {
  const e = L.estadoChecks({});
  const g = L.agruparChecks(e.filas);
  assert.deepEqual(g.map((x) => x.id), ['sitio', 'contenido', 'compra', 'medicion', 'legal']);
  const ids = g.flatMap((x) => x.filas.map((f) => f.id));
  assert.equal(ids.length, 17);
  assert.equal(new Set(ids).size, 17);
  assert.ok(g.every((x) => x.filas.every((f) => typeof f.nombre === 'string' && f.nombre && f.severidad)));
  assert.equal(g.find((x) => x.id === 'legal').filas[0].id, 'C11');
  // sin resultados: todo «sin resultado», nunca «ok»
  assert.ok(g.every((x) => x.resumen.ok === 0 && x.resumen.sinResultado === x.resumen.total));
});

test('agruparChecks: con resultados del QA cuenta ok/fallan por grupo y marca la severidad', () => {
  const e = L.estadoChecks({ qa: json('qa_d5_con_c.json') });
  const g = L.agruparChecks(e.filas);
  const total = g.reduce((a, x) => a + x.resumen.ok + x.resumen.error + x.resumen.aviso + x.resumen.noAplica + x.resumen.sinResultado, 0);
  assert.equal(total, 17);
  assert.equal(L.severidadDeFalla('BLOQ').id, 'bloqueante');
  assert.equal(L.severidadDeFalla('MAYOR (BLOQ si CTA)').id, 'mayor');
  assert.equal(L.severidadDeFalla('x').id, 'otra');
  assert.ok(Object.keys(L.NOMBRE_CHECK).length === 17);
});

test('avisosLanding: prioriza lo que falla, dice la pestaña y no inventa avisos', () => {
  const checks = L.estadoChecks({ qa: json('qa_d5_con_c.json') });
  const coh = L.coherencia({ oferta, checkout, html: htmlMalo });
  const m = L.modeloAssets(assets);
  const avisos = L.avisosLanding({ checks, coherenciaR: coh.resumen, assets: m, trackingProblemas: ['Falta un evento.'], faltan: ['el checkout'], qaR: null, x1R: null, sitioExiste: true, placeholders: m.resumen.placeholders });
  assert.ok(avisos.length >= 3);
  assert.ok(avisos.every((a) => ['grave', 'aviso', 'info'].includes(a.tono) && typeof a.titulo === 'string'));
  assert.ok(avisos.some((a) => a.tono === 'grave' && a.tab === 'coherencia'));
  assert.ok(avisos.some((a) => a.tab === 'tracking'));
  assert.deepEqual(L.avisosLanding({}), [], 'sin datos no hay avisos inventados');
  const limpio = L.avisosLanding({ checks: L.estadoChecks({}), coherenciaR: { error: 0 }, sitioExiste: false });
  assert.deepEqual(limpio, []);
});

test('problemasTracking: las mismas reglas que antes, ahora reutilizables', () => {
  assert.deepEqual(L.problemasTracking(null), []);
  const m = L.modeloTracking(tracking, checkout);
  assert.ok(Array.isArray(L.problemasTracking(m)));
  const malo = clon(tracking); malo.consent_gating.plataforma = 'otra'; malo.datos_sensibles.permitidos = true;
  const p = L.problemasTracking(L.modeloTracking(malo, checkout));
  assert.ok(p.some((x) => x.includes('consentimiento')) && p.some((x) => x.includes('sensibles')));
});

test('pages/landing.js: marco de dispositivo con iframe aislado y sin escritura', () => {
  const fuente = readFileSync(path.join(AQUI, '..', '..', 'dashboard', 'web', 'pages', 'landing.js'), 'utf8');
  assert.ok(fuente.includes("sandbox: 'allow-scripts'"), 'iframe con sandbox allow-scripts');
  assert.ok(!/sandbox:\s*'[^']*allow-same-origin/.test(fuente), 'el sandbox del iframe NO incluye allow-same-origin');
  assert.ok(fuente.includes('u3-dispositivo'), 'marco de dispositivo');
  assert.ok(fuente.includes('segmentado'), 'selector móvil/tablet/escritorio');
  assert.ok(!/api\.post|\.post\(/.test(fuente), 'solo lectura');
  assert.ok(!/innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function|srcdoc/.test(fuente));
});
