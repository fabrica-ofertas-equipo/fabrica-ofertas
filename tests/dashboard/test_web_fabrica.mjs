// test_web_fabrica.mjs — lógica pura (lib/fabrica.js, lib/n2-comun.js, glosario de piezas) y render con DOM falso de #/fabrica.
// Ejecutar: node --test tests/dashboard/test_web_fabrica.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import * as F from '../../dashboard/web/lib/fabrica.js';
import * as C from '../../dashboard/web/lib/n2-comun.js';
import { TERMINOS } from '../../dashboard/web/lib/glosario-piezas.js';
import { FRAGMENTOS, GLOSARIO_TOTAL, CONFLICTOS, ORIGENES } from '../../dashboard/web/lib/glosario-indice.js';
import { ui, fmt } from '../../dashboard/web/ui.js';
import { instalarDomFalso, porClase, porTag, texto, todos } from '../fixtures/dashboard/operacion/dom_falso.mjs';
import { apiFalsa, ctxDe, detalleDemo, fx, OFERTA_DEMO, OFERTA_REAL } from '../fixtures/dashboard/n2/api_falsa.mjs';

const paquete = fx('paquete.json');
const qaD6 = fx('qa-d6-v1.json');
const qaX1 = fx('qa-x1-d6-v1.json');
const ofertaDemo = C.ofertasValidas([OFERTA_DEMO])[0];
const modeloDemo = (extra = {}) => F.modeloCreativos(ofertaDemo, { detalle: detalleDemo(), paquete, qaDoc: qaD6, x1Doc: qaX1, ...extra });
const fuente = (ruta) => readFileSync(fileURLToPath(new URL(`../../dashboard/web/${ruta}`, import.meta.url)), 'utf8');

// ───────────────────────── n2-comun ─────────────────────────

test('texto/numero/entero/sino: solo tipos válidos, sin controles ni tamaños absurdos', () => {
  assert.equal(C.texto('  hola\u0007 '), 'hola');
  assert.equal(C.texto(42), '42');
  assert.equal(C.texto({}), null);
  assert.equal(C.texto('   '), null);
  assert.equal(C.texto('x'.repeat(1000), 20).length, 20);
  assert.equal(C.numero('0,61'), 0.61);
  assert.equal(C.numero('abc'), null);
  assert.equal(C.numero(NaN), null);
  assert.equal(C.entero('150'), 150);
  assert.equal(C.entero('1.5'), null);
  assert.equal(C.entero(-1), null);
  assert.equal(C.sino('Sí'), true);
  assert.equal(C.sino('no'), false);
  assert.equal(C.sino(1), true);
  assert.equal(C.sino('quizá'), null);
});

test('ofertasValidas: descarta ids hostiles y repetidos, marca demo y respeta el tope', () => {
  const filas = [OFERTA_DEMO, OFERTA_DEMO, { oferta_id: '../etc/passwd' }, { oferta_id: 'OF-1' }, null, OFERTA_REAL];
  const v = C.ofertasValidas(filas);
  assert.deepEqual(v.map((o) => o.id), ['_ejemplo', 'OF-202701-02']);
  assert.equal(v[0].demo, true);
  assert.equal(v[1].demo, false);
  assert.equal(C.ofertasValidas(Array.from({ length: 30 }, (_, i) => ({ oferta_id: `OF-202611-${String(i).padStart(2, '0')}` })), 4).length, 4);
  assert.deepEqual(C.ofertasValidas('no es lista'), []);
});

test('elegirFoco: la elegida, luego la activa, luego la primera real, luego la primera', () => {
  const os = C.ofertasValidas([OFERTA_DEMO, OFERTA_REAL]);
  assert.equal(C.elegirFoco(os, { previa: '_ejemplo' }), '_ejemplo');
  assert.equal(C.elegirFoco(os, { previa: 'otra', activa: '_ejemplo' }), '_ejemplo');
  assert.equal(C.elegirFoco(os, {}), 'OF-202701-02');
  assert.equal(C.elegirFoco(C.ofertasValidas([OFERTA_DEMO]), {}), '_ejemplo');
  assert.equal(C.elegirFoco([], {}), null);
});

test('jsonDeLectura: ausente, ilegible, truncado, error y ok', () => {
  const ok = { ok: true, vacio: false, datos: { contenido: '{"a":1}', truncado: false }, fuente: ['x'] };
  assert.deepEqual(C.jsonDeLectura(ok).dato, { a: 1 });
  assert.equal(C.jsonDeLectura({ ok: true, vacio: true, datos: null }).estado, 'ausente');
  assert.equal(C.jsonDeLectura({ ok: true, vacio: false, datos: { contenido: '{roto', truncado: false } }).estado, 'ilegible');
  assert.equal(C.jsonDeLectura({ ok: true, vacio: false, datos: { contenido: '{"a":', truncado: true } }).estado, 'truncado');
  assert.equal(C.jsonDeLectura({ ok: false, error: new Error('x') }).estado, 'error');
  assert.equal(C.jsonDeLectura({ ok: true, vacio: false, datos: 'texto' }).estado, 'ilegible');
});

test('rutaQaSegura y ultimoQa: solo qa/<nombre>.json y la versión numérica mayor', () => {
  assert.equal(C.rutaQaSegura('qa/d6-v1.json'), 'qa/d6-v1.json');
  assert.equal(C.rutaQaSegura('qa/../estado.json'), null);
  assert.equal(C.rutaQaSegura('/etc/passwd'), null);
  assert.equal(C.rutaQaSegura('qa/a/b.json'), null);
  assert.equal(C.ultimoQa([{ archivo: 'qa/d6-v2.json' }, { archivo: 'qa/d6-v10.json' }, { archivo: 'qa/x1-d6-v3.json' }], 'd6-'), 'qa/d6-v10.json');
  assert.equal(C.ultimoQa([{ archivo: 'qa/x1-d6-v3.json' }], 'd6-'), null);
});

test('dataImagenSegura: png/jpeg/webp/gif en base64; ni svg ni javascript', () => {
  assert.equal(C.dataImagenSegura('data:image/png;base64,iVBORw0KGgo='), true);
  assert.equal(C.dataImagenSegura('data:image/svg+xml;base64,PHN2Zz4='), false);
  assert.equal(C.dataImagenSegura('javascript:alert(1)'), false);
  assert.equal(C.dataImagenSegura(null), false);
});

test('mercadoDe: normaliza el mercado.json de la oferta demo', () => {
  const m = C.mercadoDe(detalleDemo());
  assert.equal(m.locale, 'es-ES');
  assert.deepEqual(m.paises, ['ES']);
  assert.equal(m.fiscal.regimen, 'diferido');
  assert.equal(m.consumo.desistimientoDias, 14);
  assert.equal(m.idiomaLegal.revisorNativo, false);
  assert.equal(C.mercadoDe({}), null);
});

// ───────────────────────── guía estática ─────────────────────────

test('el turno de noche va de 00:00 a 07:00, con 7 pasos y la regla de horario', () => {
  assert.equal(F.TURNO_NOCHE.length, 7);
  assert.equal(F.TURNO_NOCHE[0].hora, '00:00');
  assert.equal(F.TURNO_NOCHE[F.TURNO_NOCHE.length - 1].hora, '07:00');
  assert.deepEqual(F.TURNO_NOCHE.map((p) => p.id), ['arranque', 'guion', 'imagen', 'voz', 'montaje', 'control', 'lista']);
  for (const p of F.TURNO_NOCHE) assert.ok(F.ESTADO_PASO[p.hoy.estado], p.id);
  assert.match(F.REGLA_HORARIO, /de noche se produce y a la tarde se carga/i);
});

test('los 6 puntos del control son los del método, con sus comprobaciones', () => {
  assert.deepEqual(F.PUNTOS_CONTROL.map((p) => p.id), ['audio', 'idioma', 'texto', 'caras', 'ajeno', 'promesas']);
  assert.match(F.PUNTOS_CONTROL[0].titulo, /audio sin cortes/i);
  assert.match(F.PUNTOS_CONTROL[5].titulo, /sin precios ni promesas prohibidas/i);
});

test('formatos y retorno: ninguna cifra del autor del método aparece en los datos de la guía', () => {
  const todo = JSON.stringify([F.FORMATOS, F.ANATOMIA, F.NO_SE_PRODUCE, F.NOTA_RETORNO, F.SE_MIDE]);
  for (const cifra of ['1,83', '1.83', '1,67', '1.67', '1,39', '1.39', '1,28', '1.28', '4.460', '4460']) assert.ok(!todo.includes(cifra), `no debe mostrar ${cifra}`);
  assert.equal(F.FORMATOS.length, 6);
  assert.ok(F.FORMATOS.find((f) => f.id === 'imagen_pregunta'));
  assert.ok(F.FORMATOS.find((f) => f.id === 'cancion'));
  assert.deepEqual(F.ANATOMIA.map((a) => a.id), ['gancho', 'promesa', 'prueba', 'llamado']);
  assert.match(F.SE_MIDE, /se medirá con nuestros datos/i);
  assert.match(F.NO_SE_PRODUCE[0].titulo, /testimonios inventados con ia/i);
});

// ───────────────────────── modelo de creativos ─────────────────────────

test('modeloCreativos (demo): 6 piezas listas, QA y X1 en PASS, última producción de paquete.json', () => {
  const m = modeloDemo();
  assert.equal(m.piezas.length, 6);
  assert.ok(m.piezas.every((p) => p.estado === 'lista'));
  assert.equal(m.qa.veredicto, 'PASS');
  assert.equal(m.x1.veredicto, 'PASS');
  assert.equal(m.qa.archivo, 'qa/d6-v1.json');
  assert.equal(m.estadoPaquete, 'listo_para_d7');
  assert.equal(m.locale, 'es-ES');
  assert.equal(m.ultimaProduccion, '2026-11-13T22:00:00Z');
  const p = m.piezas[0];
  assert.equal(p.concepto, 'hueco');
  assert.equal(p.hookTipo, 'promesa de claridad');
  assert.equal(p.formato, 'imagen');
  assert.equal(p.lint, 'PASS');
  assert.equal(p.archivo, 'assets/c01-hueco_img_h1_v1.png');
});

test('modeloCreativos sin paquete: sin piezas, sin inventar nada', () => {
  const m = F.modeloCreativos(ofertaDemo, { detalle: detalleDemo({ conPaquete: false, qa: [] }) });
  assert.equal(m.tienePaquete, false);
  assert.deepEqual(m.piezas, []);
  assert.equal(m.qa, null);
  assert.equal(m.ultimaProduccion, null);
  assert.ok(m.control.every((p) => p.estado === 'sin_resultado'));
  const nada = F.modeloCreativos(ofertaDemo, {});
  assert.equal(nada.etapa, null);
  assert.deepEqual(nada.piezas, []);
});

test('estadoDePieza: firma pendiente, lint FAIL, borrador y en revisión', () => {
  const base = modeloDemo();
  const pieza = { ...base.piezas[0] };
  assert.equal(F.estadoDePieza(pieza, base), 'lista');
  assert.equal(F.estadoDePieza({ ...pieza, lint: 'FAIL' }, base), 'rechazada');
  assert.equal(F.estadoDePieza(pieza, { ...base, etapa: { ...base.etapa, gatePendiente: true } }), 'espera_firma');
  assert.equal(F.estadoDePieza(pieza, { ...base, estadoPaquete: 'borrador' }), 'borrador');
  assert.equal(F.estadoDePieza(pieza, { ...base, qa: { veredicto: 'FAIL' } }), 'en_revision');
  assert.equal(F.estadoDePieza({ ...pieza, lint: 'FAIL' }, { ...base, etapa: { ...base.etapa, gatePendiente: true } }), 'rechazada');
});

test('paquete con texto hostil: la pieza guarda el texto crudo recortado, nunca HTML interpretado', () => {
  const p = JSON.parse(JSON.stringify(paquete));
  p.anuncios[0].copy.titular = '<img src=x onerror=alert(1)>‮Titular';
  p.anuncios[0].copy.texto_principal = 'a'.repeat(2000);
  const m = F.modeloCreativos(ofertaDemo, { detalle: detalleDemo(), paquete: p, qaDoc: qaD6, x1Doc: qaX1 });
  assert.ok(m.piezas[0].titular.includes('<img'));
  assert.ok(m.piezas[0].texto.length <= 360);
  assert.ok(!/[\u0000-\u0008]/.test(m.piezas[0].titular));
});

// ───────────────────────── control de calidad ─────────────────────────

test('evaluarControl (demo): lo que el paquete deja deducir y lo demás «sin resultado»', () => {
  const m = modeloDemo();
  const e = Object.fromEntries(m.control.map((p) => [p.id, p]));
  assert.equal(e.audio.estado, 'no_aplica'); // todas son imágenes
  assert.equal(e.caras.estado, 'no_aplica'); // ninguna con IA
  assert.equal(e.idioma.estado, 'parcial'); // solo la etiqueta del texto
  assert.equal(e.promesas.estado, 'pasa');
  assert.equal(e.texto.estado, 'sin_resultado');
  assert.equal(e.ajeno.estado, 'sin_resultado');
  assert.match(e.texto.evidencia, /revisor de creativos aún no dejó/);
  assert.deepEqual(F.PUNTOS_CONTROL.find((p) => p.id === 'texto').checks, ['D6-L1-06', 'D6-L1-01'], 'los ids técnicos siguen disponibles para el detalle técnico');
  const r = F.resumenControl(m.control);
  assert.deepEqual(r, { pasa: 1, falla: 0, parcial: 1, no_aplica: 2, sin_resultado: 2, total: 6 });
});

test('evaluarControl: el resultado del revisor manda sobre la deducción', () => {
  const qa = F.modeloQa({ veredicto: 'FAIL', checks_l1: [
    { check_id: 'D6-L1-06', resultado: 'fail', detalle: 'caracteres corruptos' },
    { check_id: 'D6-L1-08', resultado: 'pass', detalle: 'sin copia' },
    { check_id: 'D6-L1-09', resultado: 'pass', detalle: 'licencias completas' },
    { check_id: 'D6-L1-07', resultado: 'no_aplica', detalle: 'sin video' },
  ] }, 'qa/d6-v1.json');
  const m = modeloDemo({ qaDoc: null });
  const e = Object.fromEntries(F.evaluarControl(m, qa).map((p) => [p.id, p]));
  assert.equal(e.idioma.estado, 'falla');
  assert.match(e.idioma.evidencia, /caracteres corruptos/);
  assert.equal(e.texto.estado, 'falla'); // D6-L1-06 también alimenta «texto»
  assert.equal(e.ajeno.estado, 'pasa');
  assert.equal(e.audio.estado, 'no_aplica');
  assert.equal(e.caras.estado, 'parcial'); // 07 no aplica + 09 pasa
  assert.equal(e.promesas.origen, 'Paquete de creativos');
});

test('evaluarControl: idioma distinto del mercado falla; lint FAIL o PASS_CON_NOTAS se distinguen; videos y piezas con IA piden resultado', () => {
  const p = JSON.parse(JSON.stringify(paquete));
  p.anuncios[0].copy.idioma = 'pl-PL';
  p.anuncios[1].lint_x1 = 'FAIL';
  p.anuncios[2].formato = 'video';
  p.anuncios[3].assets[0].ia_generado = true;
  const m = F.modeloCreativos(ofertaDemo, { detalle: detalleDemo(), paquete: p, qaDoc: null, x1Doc: null });
  const e = Object.fromEntries(m.control.map((x) => [x.id, x]));
  assert.equal(e.idioma.estado, 'falla');
  assert.match(e.idioma.evidencia, /pl-PL/);
  assert.equal(e.promesas.estado, 'falla');
  assert.equal(e.audio.estado, 'sin_resultado');
  assert.equal(e.caras.estado, 'sin_resultado');
  p.anuncios[1].lint_x1 = 'PASS_CON_NOTAS';
  assert.equal(F.modeloCreativos(ofertaDemo, { detalle: detalleDemo(), paquete: p }).control.find((x) => x.id === 'promesas').estado, 'parcial');
});

test('modeloQa: tolera documentos raros y cuenta hallazgos abiertos', () => {
  assert.equal(F.modeloQa(null), null);
  assert.equal(F.modeloQa([]), null);
  const q = F.modeloQa(qaD6, 'qa/d6-v1.json');
  assert.equal(q.hallazgos, 3);
  assert.equal(q.abiertos, 0);
  assert.equal(q.checks.length, 2);
  const raro = F.modeloQa({ veredicto: 5, hallazgos: 'no', checks_l1: [{ check_id: 7 }, null, { resultado: 'pass' }] });
  assert.deepEqual(raro.checks.map((c) => c.id), ['7']);
  assert.equal(raro.hallazgos, 0);
});

test('avisosFabrica y resumenFabrica', () => {
  const lista = modeloDemo();
  const espera = modeloDemo({ detalle: detalleDemo({ gatePendiente: true }) });
  const rechazada = F.modeloCreativos(ofertaDemo, { detalle: detalleDemo(), paquete: { ...paquete, anuncios: paquete.anuncios.map((a, i) => (i === 0 ? { ...a, lint_x1: 'FAIL' } : a)) }, qaDoc: qaD6, x1Doc: qaX1 });
  assert.deepEqual(F.avisosFabrica([lista]), []);
  const a = F.avisosFabrica([espera]);
  assert.equal(a.length, 1);
  assert.match(a[0].titulo, /esperan tu aprobación/);
  assert.equal(a[0].accion.ruta, '/oferta/_ejemplo');
  const b = F.avisosFabrica([rechazada]);
  assert.ok(b.some((x) => /no pasa el control/.test(x.titulo)));
  assert.ok(b.some((x) => x.tono === 'grave'));
  const r = F.resumenFabrica([lista, espera]);
  assert.equal(r.piezas, 12);
  assert.equal(r.esperanFirma, 6);
  assert.equal(r.listas, 6);
  assert.equal(r.soloDemo, true);
  assert.equal(F.resumenFabrica([]).piezas, 0);
});

// ───────────────────────── glosario ─────────────────────────

test('glosario-piezas: registrado, sin colisiones, definiciones completas y cortas', () => {
  assert.ok(FRAGMENTOS.includes('piezas'), 'glosario-indice.js debe listar el fragmento «piezas»');
  const claves = Object.keys(TERMINOS);
  assert.ok(claves.length >= 20);
  for (const k of claves) {
    assert.match(k, /^[a-z0-9_]{1,60}$/);
    const t = TERMINOS[k];
    assert.ok(t.nombre && t.corto && t.corto.length <= 140, k);
    assert.ok(GLOSARIO_TOTAL[k], `${k} debe estar en el glosario total`);
    assert.equal(ORIGENES[k], 'piezas', `${k} lo aportó otro origen`);
  }
  assert.deepEqual(CONFLICTOS.filter((c) => c.origen === 'piezas' || c.ganador === 'piezas'), []);
  for (const clave of ['turno_noche', 'por_aprobar', 'control_seis_puntos', 'jurado_votacion', 'tablero_idioma', 'embudo_tienda', 'ticket_promedio', 'disputa_un_clic']) assert.ok(TERMINOS[clave], clave);
});

// ───────────────────────── render ─────────────────────────

function ctxDemo(extra = {}) {
  const detalle = detalleDemo(extra.detalle || {});
  const { api, llamadas } = apiFalsa({
    ofertas: extra.ofertas || [OFERTA_DEMO],
    detalles: extra.detalles || { _ejemplo: detalle },
    archivos: extra.archivos || { '_ejemplo|06-creativos/paquete.json': JSON.stringify(extra.paquete || paquete), '_ejemplo|qa/d6-v1.json': JSON.stringify(qaD6), '_ejemplo|qa/x1-d6-v1.json': JSON.stringify(qaX1) },
    imagen: extra.imagen === undefined ? 'data:image/png;base64,iVBORw0KGgo=' : extra.imagen,
    falla: extra.falla,
  });
  return { ctx: ctxDe(ui, fmt, api, { activa: extra.activa || null }), llamadas };
}

test('render (demo): turno de noche, por aprobar, control de 6 puntos, formatos y avisos visibles; ninguna cifra ajena', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/fabrica.js');
    assert.equal(pagina.meta.ruta, 'fabrica');
    assert.equal(pagina.meta.grupo, 'Fábrica y tienda');
    assert.equal(pagina.meta.icono, 'fabrica');
    const { ctx, llamadas } = ctxDemo();
    const raiz = await pagina.render(ctx);
    const t = texto(raiz);
    assert.match(t, /Fábrica de anuncios: lo que se prepara de noche/);
    assert.match(t, /Estás viendo datos de demostración/);
    assert.match(t, /El turno de noche, de 00:00 a 07:00/);
    assert.match(t, /Arranca sola/);
    assert.match(t, /Por aprobar \(6\)/);
    assert.match(t, /Lista para la campaña/);
    assert.match(t, /Control de calidad: los 6 puntos/);
    for (const p of F.PUNTOS_CONTROL) assert.ok(t.includes(p.titulo), p.titulo);
    assert.match(t, /Sin resultado/);
    assert.match(t, /Qué anuncios venden: una guía/);
    assert.match(t, /Se medirá con nuestros datos/);
    assert.match(t, /Lo que esta fábrica NO produce/);
    assert.match(t, /Testimonios inventados con IA/);
    assert.match(t, /Se copia lo que gana\. Lo demás se apaga\./);
    for (const cifra of ['1,83', '1.83', '1,67', '1,39', '1,28']) assert.ok(!t.includes(cifra), `no debe mostrar ${cifra}`);
    assert.ok(llamadas.includes('/ofertas'));
    assert.ok(llamadas.includes('/oferta/_ejemplo'));
    assert.ok(llamadas.some((l) => l.includes('06-creativos/paquete.json')));
    assert.ok(llamadas.some((l) => l.includes('qa/d6-v1.json')));
    assert.equal(porClase(raiz, 'n2-pieza').length, 6);
    assert.equal(porClase(raiz, 'n2-punto').length, 6);
    assert.equal(porClase(raiz, 'n2-paso').length, 8); // 7 del turno + la carga a la tarde
    assert.equal(porClase(raiz, 'metrica').length, 4);
    // miniaturas: solo imágenes del paquete, bajo 06-creativos/, y una petición por pieza
    await new Promise((r) => setTimeout(r, 20));
    const imgs = llamadas.filter((l) => /archivo\?ruta=06-creativos\/assets\/.*\.png/.test(l));
    assert.equal(imgs.length, 6);
    assert.equal(porTag(raiz, 'img').length, 6);
    // nada de botones que aprueben, publiquen o activen
    for (const b of porTag(raiz, 'button')) assert.doesNotMatch(b.textContent, /aprobar ahora|publicar|activar|gastar|borrar/i);
  } finally { restaurar(); }
});

test('render: firma pendiente aparece en «Requiere tu atención» y en las métricas', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/fabrica.js');
    const { ctx } = ctxDemo({ detalle: { gatePendiente: true, d6Estado: 'en_QA' } });
    const t = texto(await pagina.render(ctx));
    assert.match(t, /Los creativos de _ejemplo \(demo\) esperan tu aprobación/);
    assert.match(t, /Espera tu aprobación/);
  } finally { restaurar(); }
});

test('render: sin paquete → estado vacío con pasos y comando; sin ofertas igual; control «sin resultado»', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/fabrica.js');
    const sin = ctxDemo({ detalle: { conPaquete: false, qa: [] }, archivos: {} });
    const raiz = await pagina.render(sin.ctx);
    const t = texto(raiz);
    assert.match(t, /Todavía no hay piezas por aprobar/);
    assert.match(t, /engine\.orq siguiente/);
    assert.match(t, /Esta oferta no tiene informe del revisor/);
    assert.ok(porClase(raiz, 'comando').length >= 1);
    assert.equal(porClase(raiz, 'n2-pieza').length, 0);
    assert.ok(!sin.llamadas.some((l) => l.includes('paquete.json')), 'no pide un paquete que no existe');
    const ninguna = ctxDemo({ ofertas: [], detalles: {}, archivos: {} });
    const raiz2 = await pagina.render(ninguna.ctx);
    assert.match(texto(raiz2), /Todavía no hay piezas por aprobar/);
    assert.match(texto(raiz2), /No hay ofertas todavía/);
  } finally { restaurar(); }
});

test('render: paquete ilegible o API caída no rompen la pantalla', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/fabrica.js');
    const roto = ctxDemo({ archivos: { '_ejemplo|06-creativos/paquete.json': '{roto' } });
    const t = texto(await pagina.render(roto.ctx));
    assert.match(t, /Todavía no hay piezas por aprobar/);
    const caida = ctxDemo({ falla: { '/oferta/_ejemplo': true } });
    const t2 = texto(await pagina.render(caida.ctx));
    assert.match(t2, /Fábrica de anuncios/);
    const todaCaida = ctxDemo({ falla: { '/ofertas': true, '/oferta/_ejemplo': true } });
    todaCaida.ctx.estado.ofertas = [];
    const raiz = await pagina.render(todaCaida.ctx);
    assert.ok(porClase(raiz, 'error-box').length >= 1);
  } finally { restaurar(); }
});

test('render: el texto hostil del paquete se ve como texto (sin etiquetas) y la imagen exige data-URL segura', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/fabrica.js');
    const p = JSON.parse(JSON.stringify(paquete));
    p.anuncios[0].copy.titular = '<script>alert(1)</script>‮';
    p.anuncios[0].assets[0].archivo = '../../empresa/limites.yaml';
    const { ctx, llamadas } = ctxDemo({ paquete: p, imagen: 'javascript:alert(1)' });
    const raiz = await pagina.render(ctx);
    await new Promise((r) => setTimeout(r, 20));
    const t = texto(raiz);
    assert.ok(t.includes('<script>alert(1)</script>'));
    assert.ok(t.includes('⟦U+202E⟧'));
    assert.equal(porTag(raiz, 'script').length, 0);
    assert.equal(porTag(raiz, 'img').length, 0, 'una data-URL no válida no se pone en un <img>');
    assert.ok(!llamadas.some((l) => l.includes('..')), 'una ruta con .. nunca se pide');
  } finally { restaurar(); }
});

test('render con varias ofertas: el selector cambia el control de calidad sin recargar', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/fabrica.js');
    const detalles = { _ejemplo: detalleDemo(), 'OF-202701-02': detalleDemo({ conPaquete: false, qa: [] }) };
    const archivos = { '_ejemplo|06-creativos/paquete.json': JSON.stringify(paquete), '_ejemplo|qa/d6-v1.json': JSON.stringify(qaD6), '_ejemplo|qa/x1-d6-v1.json': JSON.stringify(qaX1) };
    const { ctx } = ctxDemo({ ofertas: [OFERTA_DEMO, OFERTA_REAL], detalles, archivos });
    const raiz = await pagina.render(ctx);
    const sel = todos(raiz, (n) => n.localName === 'select')[0];
    assert.ok(sel, 'hay selector de oferta');
    assert.match(texto(raiz), /OF-202701-02/);
    assert.match(texto(raiz), /1 oferta más no tiene anuncios preparados todavía/);
    // la elección sobrevive entre renders (módulo con estado): se fija expresamente la oferta real, que no tiene paquete
    sel.dispararEvento('change', { target: { value: 'OF-202701-02' } });
    assert.match(texto(porClase(raiz, 'n2-control-wrap')[0]), /Todavía no hay piezas que revisar/);
    sel.dispararEvento('change', { target: { value: '_ejemplo' } });
    assert.match(texto(porClase(raiz, 'n2-control-wrap')[0]), /Ninguna pieza lleva audio/);
  } finally { restaurar(); }
});

// ───────────────────────── seguridad de las fuentes ─────────────────────────

test('ninguna fuente de la pantalla usa innerHTML, outerHTML, insertAdjacentHTML, document.write, eval ni srcdoc', () => {
  for (const ruta of ['pages/fabrica.js', 'lib/fabrica.js', 'lib/n2-comun.js', 'lib/n2-vista.js', 'lib/glosario-piezas.js']) {
    assert.ok(!/innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function|srcdoc/.test(fuente(ruta)), ruta);
  }
});

test('la pantalla solo lee: no hay POST ni llamadas que escriban', () => {
  const src = fuente('pages/fabrica.js') + fuente('lib/fabrica.js');
  assert.ok(!/api\.post|\.post\(|method:\s*['"]POST/.test(src));
});
