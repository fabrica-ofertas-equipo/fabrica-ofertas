// test_web_paises.mjs — lógica pura (lib/paises.js) y render con DOM falso de #/paises.
// Ejecutar: node --test tests/dashboard/test_web_paises.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import * as P from '../../dashboard/web/lib/paises.js';
import * as C from '../../dashboard/web/lib/n2-comun.js';
import { ui, fmt } from '../../dashboard/web/ui.js';
import { instalarDomFalso, porClase, porTag, texto, todos } from '../fixtures/dashboard/operacion/dom_falso.mjs';
import { apiFalsa, ctxDe, detalleDemo, fx, OFERTA_DEMO, OFERTA_REAL } from '../fixtures/dashboard/n2/api_falsa.mjs';

const AHORA = Date.parse('2026-11-14T10:00:00Z');
const lectura = (dato, estado = 'ok') => ({ estado, dato });
const fuente = (ruta) => readFileSync(fileURLToPath(new URL(`../../dashboard/web/${ruta}`, import.meta.url)), 'utf8');
const mercadoDemo = () => C.mercadoDe(detalleDemo());
const tarjeta = (m, id) => m.tarjetas.find((t) => t.id === id);

// ───────────────────────── la plantilla: 6 columnas y 25 tarjetas ─────────────────────────

test('las 6 columnas del tablero, en el orden del método', () => {
  assert.deepEqual(P.COLUMNAS.map((c) => c.id), ['TIENDA', 'DOMINIO', 'META', 'COBRO', 'CREATIVOS', 'LISTO']);
  assert.deepEqual(P.COLUMNAS.map((c) => c.nombre), ['Tienda', 'Dominio', 'Meta', 'Cobro', 'Anuncios', 'Listo para lanzar']);
});

test('la plantilla tiene las 25 tarjetas de analisis/paises-mercados-tiendas.md §2.3, con dueño, evidencia y columna válida', () => {
  assert.equal(P.TARJETAS.length, 25);
  const ids = P.TARJETAS.map((t) => t.id);
  assert.equal(new Set(ids).size, 25);
  assert.deepEqual(ids, ['T1', 'T2', 'T3', 'T4', 'D1', 'D2', 'D3', 'M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'C1', 'C2', 'C3', 'C4', 'C5', 'K1', 'K2', 'K3', 'K4', 'L1', 'L2', 'L3']);
  const cols = new Set(P.COLUMNAS.map((c) => c.id));
  const cuenta = {};
  for (const t of P.TARJETAS) {
    assert.ok(cols.has(t.col), t.id);
    assert.ok(t.titulo.length > 8, t.id);
    assert.ok(t.evidencia && t.evidencia.length > 20, `${t.id} sin evidencia`);
    assert.ok(t.gate, `${t.id} sin gate`);
    assert.ok(t.tecnica && t.tecnica.length > 20, `${t.id}: el detalle técnico conserva el texto con archivos y comandos`);
    assert.doesNotMatch(t.evidencia, /\.json|\.yaml|preflight|checkout|\bUTM\b|\bdataset\b|\bhash\b|landing\.validar|Ed25519|\bDNS\b|\bDKIM\b/i, `${t.id}: la evidencia no lleva jerga ni nombres de archivo`);
    assert.ok(t.duenio.length >= 1 && t.duenio.every((d) => P.DUENIOS[d]), `${t.id} dueño`);
    assert.ok(['suya', 'nueva'].includes(t.origen), t.id);
    cuenta[t.col] = (cuenta[t.col] || 0) + 1;
  }
  assert.deepEqual(cuenta, { TIENDA: 4, DOMINIO: 3, META: 6, COBRO: 5, CREATIVOS: 4, LISTO: 3 });
  // las añadidas por nosotros (obligaciones que su método no trae)
  assert.deepEqual(P.TARJETAS.filter((t) => t.origen === 'nueva').map((t) => t.id), ['T4', 'M5', 'C4', 'C5', 'L2']);
  assert.equal(P.TARJETAS.filter((t) => t.poscondicion).map((t) => t.id).join(), 'L3');
  assert.match(P.REGLA_SALIDA, /un idioma no se lanza hasta que todas las tarjetas pasan a Listo/i);
});

// ───────────────────────── estado de las tarjetas ─────────────────────────

test('claveEstado: alias, desconocidos como pendiente y vacío como «sin evidencia»', () => {
  assert.equal(P.claveEstado('verificada'), 'verificada');
  assert.equal(P.claveEstado('VERDE'), 'verificada');
  assert.equal(P.claveEstado('no_aplica_firmada'), 'no_aplica_firmada');
  assert.equal(P.claveEstado('no_aplica'), 'no_aplica_sin_firma');
  assert.equal(P.claveEstado('bloqueada'), 'bloqueada');
  assert.equal(P.claveEstado('en curso'), 'en_curso');
  assert.equal(P.claveEstado('¿qué es esto?'), 'pendiente');
  assert.equal(P.claveEstado(null), 'sin_evidencia');
  assert.equal(P.claveEstado(''), 'sin_evidencia');
  assert.equal(P.ESTADO_TARJETA.verificada.texto, 'Listo');
  assert.equal(P.ESTADO_TARJETA.no_aplica_sin_firma.listo, false);
});

test('modeloTablero sin archivo: las 25 tarjetas «sin evidencia todavía», ninguna lista, no se puede lanzar', () => {
  for (const l of [null, undefined, lectura(null, 'ausente'), lectura(null, 'ilegible'), lectura('texto', 'ok'), lectura([], 'ok')]) {
    const m = P.modeloTablero(l, { ahora: AHORA });
    assert.equal(m.hayArchivo, false);
    assert.equal(m.total, 25);
    assert.equal(m.listas, 0);
    assert.equal(m.requisitosTotal, 24);
    assert.equal(m.listoParaLanzar, false);
    assert.ok(m.tarjetas.every((t) => t.estado === 'sin_evidencia'));
    assert.equal(m.columnas.length, 6);
    assert.deepEqual(m.columnas.map((c) => c.total), [4, 3, 6, 5, 4, 3]);
    assert.equal(m.pendientes.length, 24);
  }
  assert.equal(P.modeloTablero(lectura(null, 'ilegible')).estadoLectura, 'ilegible');
});

test('modeloTablero con archivo: estados reales, no_aplica sin firma no cuenta, vigencia vencida, tarjetas desconocidas', () => {
  const doc = { semaforo: 'ROJO', locale: 'it-IT', paises_segmentacion: ['IT'], generado_en: '2026-11-14T09:00:00Z', tarjetas: [
    { id: 'T1', estado: 'verificada', evidencia: [{ tipo: 'comando', ref: 'landing.validar --json', resultado: '0 hallazgos' }, 'texto suelto', 5] },
    { id: 't2', estado: 'en_curso' },
    { id: 'D1', estado: 'pendiente' },
    { id: 'M5', estado: 'bloqueada' },
    { id: 'C4', estado: 'no_aplica_firmada' },
    { id: 'C5', estado: 'no_aplica' },
    { id: 'K1', estado: 'verificada', valido_hasta: '2026-11-01T00:00:00Z' },
    { id: 'K2', estado: 'verificada', valido_hasta: '2027-01-01T00:00:00Z' },
    { id: 'X9', columna: 'cobro', titulo: 'Tarjeta nueva', estado: 'verde' },
    { id: 'Z1', columna: 'inventada', estado: 'verificada' },
    { titulo: 'sin id' }, null, 'basura',
  ] };
  const m = P.modeloTablero(lectura(doc), { ahora: AHORA });
  assert.equal(m.hayArchivo, true);
  assert.equal(tarjeta(m, 'T1').estado, 'verificada');
  assert.equal(tarjeta(m, 'T1').evidenciaReal.length, 2);
  assert.equal(tarjeta(m, 'T2').estado, 'en_curso'); // id en minúsculas
  assert.equal(tarjeta(m, 'D1').estado, 'pendiente');
  assert.equal(tarjeta(m, 'M5').estado, 'bloqueada');
  assert.equal(tarjeta(m, 'C4').info.listo, true);
  assert.equal(tarjeta(m, 'C5').estado, 'no_aplica_sin_firma');
  assert.equal(tarjeta(m, 'C5').info.listo, false);
  assert.equal(tarjeta(m, 'K1').estado, 'vencida', 'una evidencia vencida deja de ser Listo');
  assert.equal(tarjeta(m, 'K2').estado, 'verificada');
  assert.equal(tarjeta(m, 'T3').estado, 'sin_evidencia', 'lo que el archivo no menciona sigue sin evidencia');
  assert.equal(tarjeta(m, 'X9').col, 'COBRO');
  assert.equal(tarjeta(m, 'X9').origen, 'archivo');
  assert.equal(tarjeta(m, 'Z1').col, 'LISTO');
  assert.equal(m.total, 27);
  assert.equal(m.listas, 5); // T1, C4, K2 y las dos tarjetas desconocidas (X9, Z1)
  assert.equal(m.locale, 'it-IT');
  assert.deepEqual(m.paises, ['IT']);
  assert.equal(m.listoParaLanzar, false);
  assert.ok(m.pendientes.includes('K1'));
  assert.ok(!m.pendientes.includes('L3'), 'la poscondición no es un requisito');
});

test('modeloTablero: todas las tarjetas en Listo (salvo la poscondición) → puede lanzarse; un VERDE incoherente se marca', () => {
  const todas = P.TARJETAS.map((t) => ({ id: t.id, estado: t.id === 'C4' ? 'no_aplica_firmada' : 'verificada' }));
  const m = P.modeloTablero(lectura({ semaforo: 'VERDE', tarjetas: todas.filter((t) => t.id !== 'L3') }), { ahora: AHORA });
  assert.equal(m.listoParaLanzar, true);
  assert.equal(m.requisitosListos, 24);
  assert.equal(m.incoherente, false);
  assert.equal(tarjeta(m, 'L3').estado, 'sin_evidencia');
  const roto = P.modeloTablero(lectura({ semaforo: 'verde', tarjetas: todas.filter((t) => t.id !== 'L3' && t.id !== 'T1') }), { ahora: AHORA });
  assert.equal(roto.listoParaLanzar, false);
  assert.equal(roto.incoherente, true);
  assert.deepEqual(roto.pendientes, ['T1']);
});

// ───────────────────────── obligaciones por país ─────────────────────────

test('obligaciones: las 14 del análisis, con la tarjeta que las cubre y a qué países aplican', () => {
  assert.equal(P.OBLIGACIONES.length, 14);
  assert.deepEqual(P.OBLIGACIONES.map((o) => o.id), Array.from({ length: 14 }, (_, i) => `B${String(i + 1).padStart(2, '0')}`));
  const por = Object.fromEntries(P.OBLIGACIONES.map((o) => [o.id, o]));
  assert.match(por.B01.nombre, /IVA de la UE/);
  assert.equal(por.B01.tarjeta, 'C4');
  assert.equal(por.B04.tarjeta, 'C5');
  assert.equal(por.B05.tarjeta, 'M3');
  assert.equal(por.B06.tarjeta, 'M5');
  const tarjetas = new Set(P.TARJETAS.map((t) => t.id));
  for (const o of P.OBLIGACIONES) assert.ok(o.tarjeta === null || tarjetas.has(o.tarjeta), o.id);
  assert.equal(por.B01.aplica(['ES']), true);
  assert.equal(por.B01.aplica(['US']), false);
  assert.equal(por.B02.aplica(['GB']), true);
  assert.equal(por.B02.aplica(['ES']), false);
  assert.equal(por.B07.aplica(['PL']), true);
  assert.equal(por.B07.aplica(['ES']), false);
  assert.equal(por.B10.aplica(['ES']), null);
  assert.equal(por.B12.aplica([]), true);
});

test('declaradoPorMercado (demo es-ES): régimen diferido firmado, desistimiento y cookies declarados', () => {
  const d = P.declaradoPorMercado(mercadoDemo());
  assert.match(d.B01.texto, /diferido; exposición firmada para ES/);
  assert.equal(d.B01.tono, 'aviso');
  assert.match(d.B04.texto, /14 días/);
  assert.match(d.B04.texto, /botón de arrepentimiento/);
  assert.match(d.B05.texto, /RGPD/);
  assert.equal(d.B07.tono, 'neutro');
  assert.equal(d.B06, undefined, 'lo que la oferta no declara no se inventa');
  assert.deepEqual(P.declaradoPorMercado(null), {});
});

test('declaradoPorMercado: obligación de idioma sin revisor nativo es un error; diferido sin firma también', () => {
  const m = fx('mercado.json');
  m.revision_linguistica = { obligacion_legal_idioma: true, revisor_nativo: false };
  m.fiscal = { regimen: 'diferido' };
  const d = P.declaradoPorMercado(C.mercadoDe({ mercado: m }));
  assert.equal(d.B07.tono, 'error');
  assert.match(d.B07.texto, /no se puede dar el visto bueno/);
  assert.equal(d.B01.tono, 'error');
  m.revision_linguistica.revisor_nativo = true;
  m.fiscal = { regimen: 'stripe_tax' };
  const e = P.declaradoPorMercado(C.mercadoDe({ mercado: m }));
  assert.equal(e.B07.tono, 'ok');
  assert.equal(e.B01.tono, 'ok');
});

test('filasObligaciones: «aplica» depende de los países de la oferta', () => {
  const filas = P.filasObligaciones(['ES'], mercadoDemo());
  assert.equal(filas.length, 14);
  assert.equal(filas.find((f) => f.id === 'B01').aplica, true);
  assert.equal(filas.find((f) => f.id === 'B02').aplica, false);
  assert.equal(P.filasObligaciones([], null).find((f) => f.id === 'B01').aplica, null);
});

// ───────────────────────── mercado y familias ─────────────────────────

test('filaMercado y resumenPaises: sin tablero «sin evidencia»; sin mercado.json no se inventa idioma', () => {
  const ofertas = C.ofertasValidas([OFERTA_DEMO, OFERTA_REAL]);
  const demo = P.filaMercado(ofertas[0], detalleDemo(), P.modeloTablero(null));
  assert.equal(demo.locale, 'es-ES');
  assert.deepEqual(demo.paises, ['ES']);
  assert.equal(demo.moneda, 'EUR');
  assert.equal(demo.decision, 'hipotesis');
  assert.equal(demo.tablero.hayArchivo, false);
  assert.equal(demo.tablero.total, 25);
  const sin = P.filaMercado(ofertas[1], { etapas: [] }, null);
  assert.equal(sin.hayMercado, false);
  assert.equal(sin.locale, null);
  const r = P.resumenPaises([demo, sin], [P.modeloTablero(null), P.modeloTablero(null)]);
  assert.deepEqual(r, { ofertas: 2, conMercado: 1, idiomas: 1, tablerosConEvidencia: 0, idiomasListos: 0 });
});

test('agruparFamilias: la madre es la que nadie apunta como variante; la hija solo se crea con la madre validada', () => {
  const madre = { id: '_ejemplo', interno: 'OF-202611-01', familia: 'FAM-1', fase: 'en_construccion', locale: 'es-ES', varianteDe: null };
  const hija = { id: 'OF-202701-02', interno: 'OF-202701-02', familia: 'FAM-1', fase: 'borrador', locale: 'it-IT', varianteDe: 'OF-202611-01' };
  const [fam] = P.agruparFamilias([hija, madre]);
  assert.equal(fam.familia, 'FAM-1');
  assert.equal(fam.madre.id, '_ejemplo');
  assert.deepEqual(fam.hijas.map((h) => h.id), ['OF-202701-02']);
  assert.equal(fam.madreValidada, false);
  assert.equal(fam.puedeCrearHijas, false);
  assert.deepEqual(fam.idiomas.sort(), ['es-ES', 'it-IT']);
  assert.equal(P.agruparFamilias([{ ...madre, fase: 'validada' }, hija])[0].puedeCrearHijas, true);
  assert.equal(P.agruparFamilias([{ ...madre, fase: 'escalando' }])[0].madreValidada, true);
  const sueltas = P.agruparFamilias([{ id: 'a', familia: null, fase: null }, { id: 'b', familia: null, fase: null }]);
  assert.equal(sueltas.length, 2);
  assert.equal(sueltas[0].familia, null);
  assert.deepEqual(P.agruparFamilias([]), []);
});

// ───────────────────────── render ─────────────────────────

function ctxPaises({ ofertas = [OFERTA_DEMO], detalles, archivos = {}, falla = {} } = {}) {
  const det = detalles || Object.fromEntries(ofertas.map((o) => [o.oferta_id, detalleDemo()]));
  const { api, llamadas } = apiFalsa({ ofertas, detalles: det, archivos, falla });
  return { ctx: ctxDe(ui, fmt, api), llamadas };
}

test('render sin tablero (hoy): mercado, familia, 6 columnas con 25 tarjetas «sin evidencia», regla de salida y obligaciones', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/paises.js');
    assert.equal(pagina.meta.ruta, 'paises');
    assert.equal(pagina.meta.grupo, 'Países');
    assert.equal(pagina.meta.icono, 'mundo');
    const { ctx, llamadas } = ctxPaises();
    const raiz = await pagina.render(ctx);
    const t = texto(raiz);
    assert.match(t, /Países: del idioma base a todos los idiomas/);
    assert.match(t, /Estás viendo datos de demostración/);
    assert.match(t, /Mercado e idioma de cada oferta/);
    assert.match(t, /es-ES/);
    assert.match(t, /Hipótesis: aún sin ventas propias/);
    assert.match(t, /Familia FAM-202611-01/);
    assert.match(t, /La original todavía no está validada: no se puede crear ninguna/);
    assert.match(t, /Un idioma no se lanza hasta que todas las tarjetas pasan a Listo\./);
    assert.match(t, /Todas las tarjetas salen «sin evidencia todavía»/);
    assert.ok(!/scripts\.lanzamiento_idioma/.test(t), 'el comando va en el detalle técnico (cerrado), no en el primer nivel');
    assert.ok(fuente('pages/paises.js').includes('python -m scripts.lanzamiento_idioma --oferta OF-AAAAMM-NN'));
    assert.match(t, /0 de 24 listas/);
    assert.match(t, /No puede lanzarse todavía/);
    for (const c of P.COLUMNAS) assert.ok(t.includes(c.nombre), c.nombre);
    assert.equal(porClase(raiz, 'n2-col').length, 6);
    assert.equal(porClase(raiz, 'n2-tj').length, 25);
    assert.equal(todos(raiz, (n) => n.className.includes('n2-tj--neutro')).length, 25);
    assert.equal(porClase(raiz, 'n2-tj--ok').length, 0, 'ninguna tarjeta figura como Listo');
    assert.match(t, /IVA de la UE \(régimen OSS\)/);
    assert.match(t, /Desistimiento \(14 días\)/);
    assert.match(t, /Consentimiento y medición/);
    assert.match(t, /no es asesoría legal ni fiscal/);
    assert.ok(llamadas.some((l) => l.includes('lanzamiento_idioma.json')));
    for (const b of porTag(raiz, 'button')) assert.doesNotMatch(b.textContent, /marcar|aprobar|firmar|lanzar ahora|activar/i);
  } finally { restaurar(); }
});

test('render con lanzamiento_idioma.json: estado real por tarjeta, vencidas, bloqueadas e incoherencia', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/paises.js');
    const doc = { semaforo: 'VERDE', locale: 'es-ES', tarjetas: [
      { id: 'T1', estado: 'verificada', evidencia: [{ tipo: 'comando', ref: 'landing.validar --json', resultado: '0 hallazgos' }] },
      { id: 'M5', estado: 'bloqueada' }, { id: 'K1', estado: 'verificada', valido_hasta: '2020-01-01T00:00:00Z' }, { id: 'D1', estado: 'pendiente' },
    ] };
    const { ctx } = ctxPaises({ archivos: { '_ejemplo|lanzamiento_idioma.json': JSON.stringify(doc) } });
    const raiz = await pagina.render(ctx);
    const t = texto(raiz);
    assert.match(t, /Contradicción: el archivo dice «verde»/);
    assert.match(t, /1 de 24 listas/);
    assert.match(t, /Bloqueada/);
    assert.match(t, /Vencida/);
    assert.match(t, /Pendiente/);
    assert.match(t, /landing\.validar --json · 0 hallazgos/);
    assert.match(t, /1 tarjeta\(s\) bloqueada\(s\)/);
    assert.ok(!/Todas las tarjetas salen «sin evidencia todavía»/.test(t));
    assert.equal(todos(raiz, (n) => n.className.includes('n2-tj--ok')).length, 1);
    assert.equal(todos(raiz, (n) => n.className.includes('n2-tj--error')).length, 1);
  } finally { restaurar(); }
});

test('render con una hija (pl-PL, obligación de idioma sin revisor): aviso, madre validada y selector de idioma', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/paises.js');
    const m = fx('mercado.json');
    m.locale = 'pl-PL'; m.paises_segmentacion = ['PL']; m.moneda_cobro = 'PLN'; m.variante_de = 'OF-202611-01';
    m.revision_linguistica = { obligacion_legal_idioma: true, revisor_nativo: false };
    const detalles = { _ejemplo: detalleDemo(), 'OF-202701-02': detalleDemo({ mercado: m }) };
    const ofertas = [{ ...OFERTA_DEMO, fase: 'validada' }, OFERTA_REAL];
    const { ctx } = ctxPaises({ ofertas, detalles });
    const raiz = await pagina.render(ctx);
    const t = texto(raiz);
    assert.match(t, /OF-202701-02: idioma con obligación legal y sin revisor nativo/);
    assert.match(t, /pl-PL/);
    assert.match(t, /PLN/);
    assert.match(t, /Versión en otro idioma/);
    assert.match(t, /Validada/);
    assert.ok(!/La original todavía no está validada/.test(t));
    const sel = todos(raiz, (n) => n.localName === 'select')[0];
    assert.ok(sel);
    // la elección persiste entre renders (módulo con estado): se fija expresamente la hija
    sel.dispararEvento('change', { target: { value: 'OF-202701-02' } });
    assert.match(texto(raiz), /¿Aplica a PL\?/);
    sel.dispararEvento('change', { target: { value: '_ejemplo' } });
    assert.match(texto(raiz), /¿Aplica a ES\?/);
  } finally { restaurar(); }
});

test('render: sin ofertas → estado vacío con comando; archivo del tablero ilegible → lo dice; API caída → error con reintento', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/paises.js');
    const ninguna = ctxPaises({ ofertas: [], detalles: {} });
    const raiz = await pagina.render(ninguna.ctx);
    assert.match(texto(raiz), /Todavía no hay ofertas/);
    assert.match(texto(raiz), /engine\.orq crear/);
    const roto = ctxPaises({ archivos: { '_ejemplo|lanzamiento_idioma.json': '{"tarjetas": [' } });
    assert.match(texto(await pagina.render(roto.ctx)), /No se pudo leer la lista de control de este idioma/);
    const caida = ctxPaises({ falla: { '/ofertas': true } });
    caida.ctx.estado.ofertas = [];
    assert.ok(porClase(await pagina.render(caida.ctx), 'error-box').length >= 1);
    const sinDetalle = ctxPaises({ falla: { '/oferta/_ejemplo': true } });
    const t = texto(await pagina.render(sinDetalle.ctx));
    assert.match(t, /sin mercado definido/);
  } finally { restaurar(); }
});

test('render: el texto hostil del tablero y del mercado se ve como texto', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/paises.js');
    const doc = { tarjetas: [{ id: 'X1', columna: 'TIENDA', titulo: '<script>alert(1)</script>‮', estado: 'verificada', evidencia: [{ ref: '<b>negrita</b>' }] }] };
    const { ctx } = ctxPaises({ archivos: { '_ejemplo|lanzamiento_idioma.json': JSON.stringify(doc) } });
    const raiz = await pagina.render(ctx);
    const t = texto(raiz);
    assert.ok(t.includes('<script>alert(1)</script>'));
    assert.ok(t.includes('⟦U+202E⟧'));
    assert.ok(t.includes('<b>negrita</b>'));
    assert.equal(porTag(raiz, 'script').length, 0);
    assert.equal(porTag(raiz, 'b').length, 0);
  } finally { restaurar(); }
});

test('la pantalla solo lee y no usa APIs peligrosas', () => {
  for (const ruta of ['pages/paises.js', 'lib/paises.js']) {
    const src = fuente(ruta);
    assert.ok(!/innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function|srcdoc/.test(src), ruta);
    assert.ok(!/api\.post|\.post\(|method:\s*['"]POST/.test(src), ruta);
  }
});
