// test_web_cumplimiento.mjs — lógica pura y render (DOM falso) de #/cumplimiento. Ejecutar: node --test tests/dashboard/test_web_cumplimiento.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import * as C from '../../dashboard/web/lib/cumplimiento.js';
import { ui, fmt } from '../../dashboard/web/ui.js';
import { instalarDomFalso, porClase, porTag, texto, todos } from '../fixtures/dashboard/operacion/dom_falso.mjs';

const fx = (n) => JSON.parse(readFileSync(fileURLToPath(new URL(`../fixtures/dashboard/cumplimiento/${n}`, import.meta.url)), 'utf8'));
const AHORA = Date.parse('2026-11-10T12:00:00Z');
const demo = fx('cumplimiento_demo.json');

test('ordenEtapa, abreviarHash, instanteVigencia y textoVigencia', () => {
  assert.ok(C.ordenEtapa('M1') < C.ordenEtapa('D1'));
  assert.ok(C.ordenEtapa('D2') < C.ordenEtapa('D10'));
  assert.equal(C.ordenEtapa('X1'), 99);
  assert.equal(C.abreviarHash(`sha256:${'ab'.repeat(32)}`), 'sha256:abababab…ababab');
  assert.equal(C.abreviarHash('raro'), 'raro');
  assert.equal(C.abreviarHash(null), '—');
  assert.equal(C.instanteVigencia('2026-12-05'), Date.parse('2026-12-05T23:59:59Z')); // una fecha vence al final de ese día
  assert.equal(C.instanteVigencia('2026-12-05T10:00:00Z'), Date.parse('2026-12-05T10:00:00Z'));
  assert.equal(C.instanteVigencia('mañana'), null);
  assert.equal(C.instanteVigencia(null), null);
  assert.equal(C.textoVigencia('2026-11-20T12:00:00Z', AHORA), 'vence en 10 días');
  assert.equal(C.textoVigencia('2026-11-10T09:00:00Z', AHORA), 'venció hace 3 horas');
  assert.equal(C.textoVigencia(undefined, AHORA), 'sin fecha de vigencia');
});

test('normalizarDictamen: plano o {archivo, contenido}; hallazgos por severidad; sin veredicto no hay dictamen', () => {
  const d = C.normalizarDictamen(demo.dictamenes[2]); // D6 v2 FAIL
  assert.equal(d.archivo, 'ofertas/OF-202611-01/qa/x1-d6-v2.json');
  assert.equal(d.etapa_objetivo, 'D6');
  assert.equal(d.veredicto, 'FAIL');
  assert.equal(d.veredictoInfo.tono, 'error');
  assert.deepEqual(d.hallazgos.map((h) => h.severidad), ['BLOQUEANTE', 'MAYOR', 'MENOR']);
  assert.equal(d.abiertos, 2);
  assert.equal(d.bloqueantes, 1);
  assert.match(d.hallazgos[0].cita, /Te cura en 7 días/);
  assert.equal(d.hallazgos[0].tono, 'error');
  assert.equal(d.hallazgos[2].abierto, false);
  const plano = C.normalizarDictamen(demo.dictamenes[3]);
  assert.equal(plano.etapa_objetivo, 'D7');
  assert.equal(C.normalizarDictamen(null), null);
  assert.equal(C.normalizarDictamen({ etapa: 'X1' }), null);
  assert.equal(C.normalizarDictamen({ veredicto: 'PASS', etapa: 'D5' }), null); // un QA de maker de otra etapa no es un dictamen de X1
  assert.equal(C.normalizarHallazgo(null), null);
  assert.equal(C.normalizarHallazgo({ severidad: 'RARA', descripcion: 'x' }).severidad, null); // severidad desconocida: neutra, no inventada
});

test('estadoDictamen: vigente, vencido y sin vigencia', () => {
  const d = C.normalizarDictamen(demo.dictamenes[0]);
  assert.equal(C.estadoDictamen(d, AHORA).estado, 'vigente');
  assert.equal(C.estadoDictamen(d, Date.parse('2026-12-06T00:00:00Z')).estado, 'vencido');
  assert.equal(C.estadoDictamen({ vigencia_hasta: null }, AHORA).estado, 'desconocido');
});

test('ultimosDictamenes: el más reciente por oferta y etapa (versión, ronda, fecha)', () => {
  const todos = demo.dictamenes.map(C.normalizarDictamen);
  const u = C.ultimosDictamenes(todos);
  assert.deepEqual(u.map((d) => `${d.etapa_objetivo}:${d.version}`), ['D5:v1', 'D6:v2', 'D7:v1']);
  const r2 = { ...todos[0], ronda: 2, version: 'v1' };
  assert.equal(C.ultimosDictamenes([todos[0], r2]).length, 1);
  assert.equal(C.ultimosDictamenes([todos[0], r2])[0].ronda, 2);
  assert.deepEqual(C.ultimosDictamenes([]), []);
});

test('estadoSello: vigente / vencido / alterado (hash actual, firma inválida, dictamen que cita otro artefacto)', () => {
  const m = C.modeloCumplimiento(demo, { ahora: AHORA });
  const por = Object.fromEntries(m.sellos.map((s) => [s.etapa_objetivo, s]));
  assert.equal(por.D5.vigencia.estado, 'vigente');
  assert.equal(por.D5.vigencia.causa, null);
  assert.equal(por.D6.vigencia.estado, 'vencido');
  assert.match(por.D6.vigencia.causa, /venció hace 10 días/);
  assert.match(por.D6.vigencia.causa, /se renueva firmando de nuevo/);
  assert.equal(por.D7.vigencia.estado, 'alterado');
  assert.match(por.D7.vigencia.causa, /lo revisado cambió/);
  // la alteración manda sobre el vencimiento
  const base = C.normalizarSello({ ...demo.sellos[1], hash_actual: `sha256:${'ee'.repeat(32)}` });
  assert.equal(C.estadoSello(base, { ahora: AHORA }).estado, 'alterado');
  assert.equal(C.estadoSello(C.normalizarSello({ ...demo.sellos[0], firma_valida: false }), { ahora: AHORA }).estado, 'alterado');
  assert.equal(C.estadoSello(C.normalizarSello({ ...demo.sellos[0], estado: 'alterado' }), { ahora: AHORA }).estado, 'alterado');
  assert.equal(C.estadoSello(C.normalizarSello({ ...demo.sellos[0], vigencia_hasta: 'pronto' }), { ahora: AHORA }).estado, 'desconocido');
  // cruce con el dictamen citado
  const cruce = C.modeloCumplimiento(fx('cumplimiento_cruce.json'), { ahora: AHORA });
  assert.equal(cruce.sellos[0].vigencia.estado, 'alterado');
  assert.match(cruce.sellos[0].vigencia.causa, /informe de cumplimiento citado se hizo sobre otra versión/);
});

test('normalizarSello: firma Ed25519 vs HMAC; sin hash no hay sello', () => {
  assert.equal(C.normalizarSello(demo.sellos[0]).firma, 'ed25519');
  assert.equal(C.normalizarSello(demo.sellos[1]).firma, 'hmac');
  assert.equal(C.normalizarSello(demo.sellos[2]).object_ids.length, 2);
  assert.equal(C.normalizarSello({ oferta_id: 'x' }), null);
  assert.equal(C.normalizarSello(null), null);
  assert.equal(C.normalizarSello({ artefacto_sha256: 'x', firma: 5 }).firma, null);
});

test('modeloCumplimiento: conteos, PASS sin sello y lint por oferta', () => {
  const m = C.modeloCumplimiento(demo, { ahora: AHORA });
  assert.equal(m.hay, true);
  assert.equal(m.dictamenes.length, 4);
  assert.equal(m.ultimos.length, 3);
  assert.deepEqual(m.conteoSellos, { vigente: 1, vencido: 1, alterado: 1, ilegible: 0, desconocido: 0 });
  assert.deepEqual(m.dictamenesPorVeredicto, { PASS: 2, FAIL: 1 });
  assert.deepEqual(m.sinSello, []);
  assert.equal(m.lint.length, 1);
  const o = m.lint[0];
  assert.equal(o.oferta_id, 'OF-202611-01');
  assert.equal(o.semaforo, 'rojo'); // el peor de los últimos dictámenes (D6 v2)
  assert.equal(o.porSeveridad.BLOQUEANTE, 1);
  assert.equal(o.porSeveridad.MAYOR, 1);
  assert.ok(o.sinTrazar.includes('D6')); // v2 sin claims trazados
  assert.ok(o.claims.some((c) => c.claim_id === 'garantia-14-dias'));
  const cruce = C.modeloCumplimiento(fx('cumplimiento_cruce.json'), { ahora: AHORA });
  assert.equal(cruce.sinSello.length, 1); // el dictamen PASS no tiene un sello con su hash
  const vacio = C.modeloCumplimiento(fx('cumplimiento_vacio.json'), { ahora: AHORA });
  assert.equal(vacio.hay, false);
  assert.deepEqual(vacio.lint, []);
  for (const x of [null, undefined, 'x', 5, []]) assert.equal(C.modeloCumplimiento(x, { ahora: AHORA }).hay, false);
});

test('lint del linter: se incorpora al semáforo de la oferta', () => {
  const m = C.modeloCumplimiento(fx('cumplimiento_con_lint.json'), { ahora: AHORA });
  assert.equal(m.lint[0].semaforo, 'amarillo');
  assert.equal(m.lint[0].lints.length, 1);
  assert.equal(m.lint[0].lints[0].hallazgos[0].categoria, 'garantias_absolutas');
  assert.equal(C.normalizarLint({ semaforo: 'rojo' }), null);
  assert.equal(C.normalizarLint(null), null);
  assert.equal(C.normalizarLint({ semaforo: 'raro', hallazgos: [] }).semaforo, null);
});

test('comandosCumplimiento: comandos documentados de compliance.*', () => {
  const c = C.comandosCumplimiento('OF-202611-01', 'D6', 'it-IT');
  assert.equal(c.lint, '.venv/bin/python -m compliance.lint_claims --oferta OF-202611-01 --etapa D6 --locale it-IT');
  assert.match(c.sellar, /^\.venv\/bin\/python -m compliance\.sellar --oferta OF-202611-01 --etapa-objetivo D6 --artefacto <ruta> --dictamen ofertas\/OF-202611-01\/qa\/x1-d6-v1\.json --locale it-IT$/);
  assert.match(c.verificar, /compliance\.verificar --hash/);
});

// ───────────── el panel entrega RESÚMENES de dictámenes: se piden los archivos completos ─────────────

const panel = fx('cumplimiento_panel.json');
const detalles = fx('cumplimiento_panel_detalles.json');

test('resumen del panel: sin hallazgos ni claims no se finge «0 hallazgos»; los sellos ilegibles se marcan', () => {
  const m = C.modeloCumplimiento(panel, { ahora: AHORA });
  const d6 = m.ultimos.find((d) => d.etapa_objetivo === 'D6');
  assert.equal(d6.version, 'v2');
  assert.equal(d6.soloResumen, true);
  assert.equal(d6.nHallazgos, 3);
  assert.equal(d6.abiertos, null); // desconocido, no 0
  assert.equal(d6.bloqueantes, null);
  assert.equal(d6.claims, null);
  assert.deepEqual(m.lint[0].sinTrazar, []); // sin detalle no se acusa «sin claims»
  assert.ok(m.lint[0].sinDetalle.includes('D6'));
  assert.equal(m.conteoSellos.ilegible, 1);
  const roto = m.sellos.find((s) => s.ilegible);
  assert.equal(roto.vigencia.estado, 'ilegible');
  assert.equal(roto.vigencia.tono, 'error');
  assert.equal(roto.archivo, 'roto.json');
  assert.deepEqual(m.sinSello, []); // los PASS tienen un sello de su oferta y etapa
});

test('dictamenesAEnriquecer: solo el último de cada etapa y solo resúmenes; aplicarDetalles los completa', () => {
  const a = C.dictamenesAEnriquecer(panel);
  assert.deepEqual(a.map((x) => `${x.oferta_id} ${x.ruta}`), ['_ejemplo qa/x1-d5-v1.json', '_ejemplo qa/x1-d6-v2.json', '_ejemplo qa/x1-d7-v1.json']);
  assert.deepEqual(C.dictamenesAEnriquecer(demo), []); // ya vienen completos
  assert.deepEqual(C.dictamenesAEnriquecer(null), []);
  assert.equal(C.dictamenesAEnriquecer(panel, 2).length, 2);
  const mapa = new Map(a.map((x) => [`${x.oferta_id}|${x.ruta}`, detalles[x.ruta]]));
  const m = C.modeloCumplimiento(C.aplicarDetalles(panel, mapa), { ahora: AHORA });
  const d6 = m.ultimos.find((d) => d.etapa_objetivo === 'D6');
  assert.equal(d6.soloResumen, false);
  assert.equal(d6.bloqueantes, 1);
  assert.equal(d6.hallazgos.length, 3);
  assert.equal(m.lint[0].semaforo, 'rojo');
  assert.ok(m.lint[0].sinTrazar.includes('D6'));
  assert.equal(C.aplicarDetalles(panel, new Map()), panel);
  assert.equal(C.rutaQa('ofertas/OF-202611-01/qa/x1-d5-v1.json'), 'qa/x1-d5-v1.json');
  assert.equal(C.rutaQa('qa/../../etc/passwd'), null);
  assert.equal(C.rutaQa('qa/x y.json'), null);
  assert.equal(C.rutaQa(null), null);
});

test('un PASS cuyo resumen no trae hash se cruza por oferta y etapa; con hash, por hash', () => {
  const sinSello = C.modeloCumplimiento({ dictamenes: [panel.dictamenes[0]], sellos: [] }, { ahora: AHORA });
  assert.equal(sinSello.sinSello.length, 1);
  const conSello = C.modeloCumplimiento({ dictamenes: [panel.dictamenes[0]], sellos: [panel.sellos[0]] }, { ahora: AHORA });
  assert.equal(conSello.sinSello.length, 0);
});

// ───────────── render con DOM falso ─────────────

function ctxDe(datos, { vacio = false, falla = false, archivos = null } = {}) {
  const api = {
    sobre: async (ruta, params) => {
      if (falla) throw Object.assign(new Error('x'), { codigo: 'sin_conexion', mensaje: 'x' });
      if (ruta.startsWith('/oferta/')) {
        const c = archivos && archivos[params.ruta];
        if (!c) throw Object.assign(new Error('x'), { codigo: 'no_encontrado', mensaje: 'x' });
        return { datos: { ruta: params.ruta, tipo: 'json', contenido: JSON.stringify(c) }, fuente: [`ofertas/${params.ruta}`], generado_en: null, vacio: false, avisos: [] };
      }
      return { datos, fuente: ['ofertas/OF-202611-01/qa/x1-d5-v1.json', 'empresa/compliance/sellos'], generado_en: '2026-11-10T12:00:00Z', vacio, avisos: [] };
    },
  };
  return { api, ui, fmt, estado: {}, params: {}, ruta: 'cumplimiento', recargar() {}, navegar() {}, alSalir() {} };
}

test('render: dictámenes con FAIL, sellos vigente/vencido/alterado con su causa y avisos', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/cumplimiento.js');
    assert.equal(pagina.meta.ruta, 'cumplimiento');
    const raiz = await pagina.render(ctxDe(demo));
    const t = texto(raiz);
    assert.match(t, /Revisión de cumplimiento por etapa/);
    assert.match(t, /FAIL/);
    assert.match(t, /Vistos buenos firmados/);
    assert.match(t, /alterado/i);
    assert.match(t, /vencido/i);
    assert.match(t, /vigente/i);
    assert.match(t, /lo revisado cambió desde que se firmó/);
    assert.match(t, /Firma de pruebas \(no vale en real\)/);
    assert.match(t, /Firma digital/); // el tipo de firma (Ed25519) queda en el detalle técnico, no en la tarjeta
    assert.match(t, /Revisión de afirmaciones por oferta/);
    assert.match(t, /Sin afirmaciones con prueba citada en Anuncios/);
    assert.match(t, /Bloqueado/);
    assert.ok(porClase(raiz, 'p5-dict--error').length >= 1 && porClase(raiz, 'p5-sello--error').length >= 1, 'el veto y el sello alterado se ven en rojo');
  } finally { restaurar(); }
});

test('clic en el dictamen FAIL: hallazgos con severidad y cita; el HTML y U+202E de la cita se ven como texto', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/cumplimiento.js');
    const raiz = await pagina.render(ctxDe(demo));
    for (const d of porClase(raiz, 'detalle-tecnico')) if (d.montar) d.montar(); // el detalle técnico se construye al abrirlo
    const t = texto(raiz);
    assert.match(t, /Hallazgos \(3\)/);
    assert.match(t, /Bloqueante/);
    assert.match(t, /X1-P01/);
    assert.match(t, /«Te cura en 7 días» \(06-creativos\/copy\.md:12\)/);
    assert.match(t, /Corrección segura: Reformular como experiencia/);
    assert.ok(t.includes('<img src=x onerror=alert(1)> Quedan 3 plazas'));
    assert.ok(t.includes('⟦U+202E⟧evil'));
    assert.equal(porTag(raiz, 'img').length, 0);
    assert.ok(porClase(raiz, 'p5-cita').length >= 2);
  } finally { restaurar(); }
});

test('render del cruce: PASS sin sello válido avisa con el comando de sellar', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/cumplimiento.js');
    const raiz = await pagina.render(ctxDe(fx('cumplimiento_cruce.json')));
    const t = texto(raiz);
    assert.match(t, /Aprobadas sin visto bueno firmado: OF-202611-01 · Página de venta, pago y medición \(v1\)/);
    assert.match(t, /compliance\.sellar --oferta OF-202611-01 --etapa-objetivo D5/);
    assert.match(t, /informe de cumplimiento citado se hizo sobre otra versión/);
  } finally { restaurar(); }
});

test('render vacío: ningún PASS por defecto y comandos copiables; error de API: errorBox', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/cumplimiento.js');
    const raiz = await pagina.render(ctxDe(fx('cumplimiento_vacio.json'), { vacio: true }));
    const t = texto(raiz);
    assert.match(t, /Todavía no hay informes ni vistos buenos de cumplimiento/);
    assert.match(t, /nunca se da nada por aprobado por defecto/);
    assert.match(t, /compliance\.lint_claims --oferta OF-AAAAMM-NN --etapa D5 --locale es-ES/);
    assert.ok(porClase(raiz, 'comando').length >= 2);
    assert.doesNotMatch(t, /\bPASS\b.*vigente/);
    const err = await pagina.render(ctxDe(null, { falla: true }));
    assert.equal(porClase(err, 'error-box').length, 1);
  } finally { restaurar(); }
});

test('render con resúmenes del panel: pide los dictámenes completos y muestra hallazgos con cita', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/cumplimiento.js');
    const raiz = await pagina.render(ctxDe(panel, { archivos: detalles }));
    const t = texto(raiz);
    assert.match(t, /ilegible/);
    assert.match(t, /roto\.json/);
    assert.match(t, /firma no informada/); // el panel no lee la firma del sello
    assert.doesNotMatch(t, /sin detalle\)/);
    assert.match(texto(raiz), /«Te cura en 7 días»/);
  } finally { restaurar(); }
});

test('render con resúmenes cuando no se puede leer el detalle: lo dice, no inventa hallazgos', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/cumplimiento.js');
    const raiz = await pagina.render(ctxDe(panel, { archivos: {} }));
    const t = texto(raiz);
    assert.match(t, /3 hallazgos \(sin detalle\)/);
    assert.match(t, /sin detalle cargado: el recuento puede estar incompleto/);
    assert.match(texto(raiz), /El panel solo recibió el resumen de este informe \(3 hallazgo\(s\)\)/);
    assert.match(texto(raiz), /Solo hay resumen \(sin afirmaciones\)/);
  } finally { restaurar(); }
});

test('render con lint del linter y sin sellos: muestra hallazgos del linter y el estado vacío de sellos', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/cumplimiento.js');
    const raiz = await pagina.render(ctxDe(fx('cumplimiento_con_lint.json')));
    const t = texto(raiz);
    assert.match(t, /Todavía no hay vistos buenos firmados/);
    assert.match(t, /garantias_absolutas/);
    assert.match(t, /Semáforo amarillo/);
  } finally { restaurar(); }
});


// ───────────── rediseño U4 ─────────────

test('veredictoHumano y geometriaPuntaje: nombres de negocio con la sigla aparte; el puntaje se compara con el mínimo sobre 5', () => {
  assert.equal(C.veredictoHumano('PASS').texto, 'Aprobado');
  assert.equal(C.veredictoHumano('FAIL').texto, 'Bloqueado');
  assert.equal(C.veredictoHumano('FAIL').tecnico, 'FAIL');
  assert.equal(C.veredictoHumano('ESCALAR').texto, 'Espera tu decisión');
  assert.equal(C.veredictoHumano('XYZ').tono, 'neutro');
  const g = C.geometriaPuntaje(4.4, 3.8);
  assert.equal(g.puntaje, 88); assert.equal(g.umbral, 76); assert.equal(g.aprueba, true);
  assert.equal(C.geometriaPuntaje(3, 3.8).aprueba, false);
  assert.equal(C.geometriaPuntaje(NaN, 3.8), null);
  assert.equal(C.estadoHallazgoHumano('corregido_por_qa'), 'Corregido en la revisión');
});

test('atencionCumplimiento: etapa bloqueada y visto bueno alterado = crítico; vencido y sin firma = aviso; nada = vacío', () => {
  const m = C.modeloCumplimiento(demo, { ahora: Date.parse('2026-11-14T10:00:00Z') });
  const a = C.atencionCumplimiento(m, Date.parse('2026-11-14T10:00:00Z'));
  assert.equal(a[0].tono, 'critico');
  assert.ok(a.some((x) => /Cumplimiento bloquea la etapa/.test(x.titulo)));
  assert.ok(a.some((x) => /visto bueno firmado alterado|vistos buenos firmados alterados/.test(x.titulo)));
  assert.deepEqual(C.atencionCumplimiento(C.modeloCumplimiento(null, {}), Date.now()), []);
});
