// Pruebas de «Mis tareas» (#/tareas): lib/tareas.js (lógica pura) y pages/tareas.js (con DOM y API falsos).
// Reglas que se prueban: el estado sale de datos reales (nunca «Hecha» sin evidencia o sin marca personal), la demo no cuenta, las dependencias bloquean,
// las marcas personales caducan (día/semana), solo hay acciones seguras de la lista blanca, ningún botón firma/publica/activa/gasta/envía/borra,
// y todo texto de archivos entra como texto (ni innerHTML ni elementos inventados).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { instalar, buscar, buscarTodos } from '../fixtures/dashboard/shell/dom_falso.mjs';
import { cargarSobre, crearApiFalsa, crearCtx, dormir } from '../fixtures/dashboard/shell/ctx_falso.mjs';

const doc = instalar();
const T = await import('../../dashboard/web/lib/tareas.js');
const { ui } = await import('../../dashboard/web/ui.js');
const pagina = await import('../../dashboard/web/pages/tareas.js');
const glosario = await import('../../dashboard/web/lib/glosario-indice.js');

const AHORA = Date.parse('2026-11-06T15:00:00Z');
const fixtureOferta = () => JSON.parse(readFileSync(new URL('../fixtures/dashboard/oferta/oferta_ejemplo.json', import.meta.url), 'utf8'));
const fixtureHostil = () => JSON.parse(readFileSync(new URL('../fixtures/dashboard/oferta/oferta_hostil.json', import.meta.url), 'utf8'));

// ───────────────────────── ayudas ─────────────────────────

const lec = (datos, extra = {}) => ({ ok: true, vacio: false, datos, ...extra });
const vacia = () => ({ ok: true, vacio: true, datos: null });
const caida = () => ({ ok: false, vacio: false, datos: null, err: new Error('sin conexión') });
const par = (valores = {}) => lec({ limites: { valores: { moneda_limites: null, gasto_diario_global: null, perdida_neta_acumulada_max: null, paises_permitidos: [], locales_permitidos: [], macro_nichos_permitidos: ['salud', 'relaciones', 'dinero'], acciones_gate_humano: ['activar_campana'], sello: null, ...valores }, nulos: [] }, parametros: {}, autonomia: {}, propuestas: [] });
const sis = (extra = {}) => lec({ pausa: { activa: false }, freno_captura: null, infra: null, ...extra });
const infraVerde = (extra = {}) => ({ semaforo: 'VERDE', modo: 'vivo', generado_en: '2026-11-06T13:00:00Z', items: [], ...extra });
const ofertaDe = (id, demo, datos) => ({ id, demo, lectura: lec(datos) });
function detalleOferta({ id = 'OF-202611-02', fase = 'en_construccion', estados = {}, gatePendiente = [], extra = {}, mercado = null } = {}) {
  const orden = ['M1', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10'];
  return {
    estado: { oferta_id: id, fase, nivel: 'N2' },
    etapas: orden.map((e) => ({ id: e, nombre: e, estado: estados[e] || 'pendiente', version: 'v1', gate: 'H', gate_pendiente: gatePendiente.includes(e), hash: null, bloqueo: null, obsoleta: false, artefactos: [], qa: [], ...(extra[e] || {}) })),
    brief: null, mercado,
  };
}
const aprobadas = (...ids) => Object.fromEntries(ids.map((i) => [i, 'aprobado']));
const tareaDe = (r, id) => r.tareas.find((t) => t.id === id);
const claveDe = (r, id) => tareaDe(r, id).estado.clave;
const sello = (etapa, extra = {}) => ({ legible: true, oferta_id: 'OF-202611-02', etapa_objetivo: etapa, vigencia_hasta: '2026-12-01T00:00:00Z', alterado: false, ...extra });
const ev = (lecturas, opciones = {}) => T.evaluarTareas(lecturas, { ahora: AHORA, ...opciones });

const ESCENARIO_VERDE = () => ({
  sistema: sis({ infra: infraVerde() }),
  parametros: par({ moneda_limites: 'USD', gasto_diario_global: 30000, perdida_neta_acumulada_max: 300000, paises_permitidos: ['ES'], locales_permitidos: ['es-ES'], sello: { hash: 'sha256:x' } }),
  pulido: lec([]), robots: lec({ robots: [{ id: 'escalera', estado: 'vivo', ultimo_latido: '2026-11-06T14:55:00Z' }, { id: 'auditor', estado: 'sombra' }] }),
  cumplimiento: lec({ dictamenes: [], sellos: [sello('D5'), sello('D6'), sello('D7')] }),
  cerebro: lec({ jardin: { existe: false, propuestas: 0 } }), gates: vacia(),
});
const OFERTA_REAL_LISTA = () => ofertaDe('OF-202611-02', false, detalleOferta({ fase: 'en_test', estados: aprobadas('M1', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7'), mercado: { fiscal: { regimen: 'oss_ue' } } }));

// ───────────────────────── catálogo ─────────────────────────

test('catálogo: 44 tareas en 6 momentos, ids únicos, dependencias hacia atrás, todas con pasos', () => {
  assert.equal(T.CATALOGO.length, 44);
  assert.equal(new Set(T.CATALOGO.map((t) => t.id)).size, 44);
  assert.deepEqual(T.MOMENTOS.map((m) => T.CATALOGO.filter((t) => t.momento === m.id).length), [9, 8, 6, 8, 7, 6]);
  assert.deepEqual(T.MOMENTOS.map((m) => m.id), [0, 1, 2, 3, 4, 5]);
  const posicion = new Map(T.CATALOGO.map((t, i) => [t.id, i]));
  for (const t of T.CATALOGO) {
    assert.ok(T.CLAVES_QUIEN.includes(t.quien), `${t.id}: quién`);
    assert.ok(['unica', 'dia', 'semana', undefined].includes(t.periodo), `${t.id}: periodo`);
    for (const d of t.depende || []) assert.ok(posicion.has(d) && posicion.get(d) < posicion.get(t.id), `${t.id} depende de ${d} (debe existir y venir antes)`);
  }
  const r = ev({});
  for (const t of r.tareas) assert.ok(t.pasos.length >= 1 && t.pasos.every((p) => p.texto), `${t.id}: pasos`);
});

test('catálogo: lenguaje simple (guía de lenguaje): sin jerga en título, por qué importa ni evidencia; títulos con verbo en infinitivo', () => {
  const JERGA = /\b(gate|preflight|hash|sha256|payload|checkout|upsell|dry-run|json|yaml|api|endpoint|cbo|cpa|roas|ctr|cpm|utm|ledger|maker|qa|schema|token)\b/i;
  const casos = [ev({}), ev(ESCENARIO_VERDE(), { oferta: OFERTA_REAL_LISTA() })];
  for (const r of casos) {
    for (const t of r.tareas) {
      for (const [campo, txt] of [['título', t.titulo], ['por qué importa', t.porQue], ['evidencia', t.estado.evidencia || ''], ['detalle', t.estado.detalle || '']]) assert.ok(!JERGA.test(txt), `${t.id} (${campo}): «${txt}»`);
      assert.match(t.titulo, /^[A-ZÁÉÍÓÚ][a-záéíóúñ]*(ar|er|ir)\b/, `${t.id}: el título empieza con un verbo`);
    }
  }
});

test('catálogo: cada palabra clave existe en el glosario y el fragmento «tareas» está registrado', () => {
  assert.ok(glosario.FRAGMENTOS.includes('tareas'));
  assert.ok(glosario.CARGADOS.some((f) => f.nombre === 'tareas' && f.claves > 0), 'el glosario de tareas se cargó');
  for (const t of T.CATALOGO) for (const x of t.terminos || []) assert.ok(glosario.buscarTermino(x.clave), `${t.id}: falta el término «${x.clave}»`);
});

// ───────────────────────── estado real, nunca inventado ─────────────────────────

test('sin ninguna lectura: ninguna tarea queda «Hecha» y el siguiente paso es elegir el idioma', () => {
  const r = ev({});
  assert.equal(r.resumen.hechas, 0);
  assert.equal(r.siguiente.id, 'idioma-mercado');
  assert.equal(claveDe(r, 'idioma-mercado'), 'no_comprobable');
  assert.match(tareaDe(r, 'idioma-mercado').estado.evidencia, /No se pudo leer/);
});

test('invariante: «Hecha» siempre trae evidencia y origen datos o marca (en varios escenarios)', () => {
  const marcas = Object.fromEntries(T.IDS_TAREAS.map((id) => [id, new Date(AHORA).toISOString()]));
  const escenarios = [ev({}), ev(ESCENARIO_VERDE(), { oferta: OFERTA_REAL_LISTA() }), ev({}, { marcas }), ev(ESCENARIO_VERDE(), { oferta: ofertaDe('_ejemplo', true, fixtureOferta().datos), marcas }),
    ev({ sistema: caida(), parametros: caida(), ofertas: caida(), robots: caida(), cumplimiento: caida(), pulido: caida() })];
  for (const r of escenarios) for (const t of r.tareas) {
    if (t.estado.clave !== 'hecha') continue;
    assert.ok(t.estado.evidencia && t.estado.evidencia.length > 5, `${t.id}: «Hecha» sin evidencia`);
    assert.ok(['datos', 'marca'].includes(t.estado.origen), `${t.id}: origen ${t.estado.origen}`);
  }
});

test('lo que todavía no existe sale «Todavía no existe», con qué falta; nunca «Hecha» ni «Pendiente»', () => {
  const r = ev({ robots: vacia(), cerebro: lec({ jardin: { existe: false, propuestas: 0 } }), parametros: par() });
  for (const id of Object.keys(T.CONSTRUCCION)) {
    const t = tareaDe(r, id);
    if (id === 'cr-nicho4') continue; // este se comprueba con los límites
    assert.equal(t.estado.clave, 'no_existe', id);
    assert.match(t.estado.evidencia, /^Todavía no/, id);
    assert.equal(t.estado.marcable, false, `${id}: no se marca lo que no existe`);
  }
  assert.ok(r.resumen.noExisten >= 15);
});

test('frenos: sin fijar → Pendiente · uno solo → En curso · cargados sin firma → Espera tu firma · firmados → Hecha', () => {
  assert.equal(claveDe(ev({ parametros: par() }), 'frenos'), 'pendiente');
  assert.equal(claveDe(ev({ parametros: par({ moneda_limites: 'USD', gasto_diario_global: 30000 }) }), 'frenos'), 'en_curso');
  const sinFirma = ev({ parametros: par({ moneda_limites: 'USD', gasto_diario_global: 30000, perdida_neta_acumulada_max: 300000 }) });
  assert.equal(claveDe(sinFirma, 'frenos'), 'espera_firma');
  assert.equal(sinFirma.siguiente.id, 'idioma-mercado', 'el idioma sigue primero en el orden');
  const firmados = ev({ parametros: par({ moneda_limites: 'USD', gasto_diario_global: 30000, perdida_neta_acumulada_max: 300000, sello: { hash: 'h' } }) });
  const t = tareaDe(firmados, 'frenos');
  assert.equal(t.estado.clave, 'hecha');
  assert.equal(t.estado.alerta, null);
  assert.match(t.estado.evidencia, /300 USD por día/);
  assert.equal(claveDe(firmados, 'lz-frenos'), 'hecha', 'la condición de «Lanzar» usa los mismos datos');
});

test('frenos: si lo firmado no coincide con J4 (300 USD/día y −3.000) avisa; en otra moneda lo dice sin afirmar', () => {
  const otro = tareaDe(ev({ parametros: par({ moneda_limites: 'USD', gasto_diario_global: 25000, perdida_neta_acumulada_max: 300000, sello: { hash: 'h' } }) }), 'frenos');
  assert.equal(otro.estado.clave, 'hecha');
  assert.match(otro.estado.alerta, /no coinciden/);
  const eur = tareaDe(ev({ parametros: par({ moneda_limites: 'EUR', gasto_diario_global: 30000, perdida_neta_acumulada_max: 300000, sello: { hash: 'h' } }) }), 'frenos');
  assert.equal(eur.estado.alerta, null);
  assert.match(eur.estado.detalle, /EUR/);
});

test('idioma y mercado: solo «Hecha» con idioma Y países en los límites; a medias = En curso', () => {
  assert.equal(claveDe(ev({ parametros: par() }), 'idioma-mercado'), 'pendiente');
  assert.equal(claveDe(ev({ parametros: par({ paises_permitidos: ['PL'] }) }), 'idioma-mercado'), 'en_curso');
  assert.equal(claveDe(ev({ parametros: par({ locales_permitidos: ['pl-PL'] }) }), 'idioma-mercado'), 'en_curso');
  const r = ev({ parametros: par({ paises_permitidos: ['PL'], locales_permitidos: ['pl-PL'] }) });
  assert.equal(claveDe(r, 'idioma-mercado'), 'hecha');
  assert.equal(r.siguiente.id, 'frenos', 'el siguiente paso avanza a la tarea que sigue');
});

test('revisor nativo: bloqueado sin idioma; con español no hace falta; con polaco no se puede comprobar', () => {
  assert.equal(claveDe(ev({ parametros: par() }), 'hablante-nativo'), 'bloqueada');
  assert.equal(claveDe(ev({ parametros: par({ locales_permitidos: ['es-ES'], paises_permitidos: ['ES'] }) }), 'hablante-nativo'), 'hecha');
  const pl = ev({ parametros: par({ locales_permitidos: ['pl-PL'], paises_permitidos: ['PL'] }) });
  assert.equal(claveDe(pl, 'hablante-nativo'), 'no_comprobable');
  assert.equal(tareaDe(pl, 'hablante-nativo').estado.marcable, true);
});

test('chequeo antes de lanzar: verde y vivo → Hecha; viejo vale para la primera vez pero no para lanzar; simulacro y rojo → En curso', () => {
  const ok = ev({ sistema: sis({ infra: infraVerde() }) });
  assert.equal(claveDe(ok, 'chequeo-previo'), 'hecha');
  assert.equal(claveDe(ok, 'lz-chequeo'), 'hecha');
  const viejo = ev({ sistema: sis({ infra: infraVerde({ generado_en: '2026-11-05T01:00:00Z' }) }) });
  assert.equal(claveDe(viejo, 'chequeo-previo'), 'hecha');
  assert.match(tareaDe(viejo, 'chequeo-previo').estado.detalle, /repetirlo/);
  assert.equal(claveDe(viejo, 'lz-chequeo'), 'pendiente');
  assert.match(tareaDe(viejo, 'lz-chequeo').estado.evidencia, /venció/);
  const simulado = ev({ sistema: sis({ infra: infraVerde({ modo: 'simulado' }) }) });
  assert.equal(claveDe(simulado, 'chequeo-previo'), 'en_curso');
  assert.match(tareaDe(simulado, 'chequeo-previo').estado.evidencia, /simulacro/);
  const rojo = ev({ sistema: sis({ infra: infraVerde({ semaforo: 'ROJO', items: [{ id: 'a', estado: 'ROJO' }, { id: 'b', estado: 'ROJO' }, { id: 'c', estado: 'VERDE' }] }) }) });
  assert.equal(claveDe(rojo, 'chequeo-previo'), 'en_curso');
  assert.match(tareaDe(rojo, 'chequeo-previo').estado.evidencia, /2 puntos en rojo/);
  assert.equal(claveDe(ev({ sistema: sis() }), 'chequeo-previo'), 'pendiente');
  assert.equal(claveDe(ev({ sistema: caida() }), 'chequeo-previo'), 'no_comprobable');
});

test('freno de la captura: puesto → Pendiente con el motivo; libre → Hecha; PAUSA activa avisa pero no da por probada la prueba', () => {
  const puesto = ev({ sistema: sis({ freno_captura: { activo: true, ts: '2026-11-06T06:03:43Z', motivo: 'HTTP 403 (Document)' } }) });
  assert.equal(claveDe(puesto, 'freno-captura'), 'pendiente');
  assert.match(tareaDe(puesto, 'freno-captura').estado.evidencia, /HTTP 403/);
  assert.equal(claveDe(ev({ sistema: sis() }), 'freno-captura'), 'hecha');
  const pausa = ev({ sistema: sis({ pausa: { activa: true, desde: '2026-11-06T10:00:00Z', motivo: 'x' } }) });
  assert.equal(claveDe(pausa, 'probar-pausa'), 'no_comprobable');
  assert.match(tareaDe(pausa, 'probar-pausa').estado.alerta, /PAUSA está puesta/);
});

test('IVA: solo con una oferta real que declare un régimen; «diferido» sigue Pendiente; la demo no vale como evidencia', () => {
  const base = { parametros: par({ locales_permitidos: ['es-ES'], paises_permitidos: ['ES'] }) };
  assert.equal(claveDe(ev(base, { oferta: ofertaDe('OF-202611-02', false, detalleOferta({ mercado: { fiscal: { regimen: 'oss_ue' } } })) }), 'iva-contador'), 'hecha');
  assert.equal(claveDe(ev(base, { oferta: ofertaDe('OF-202611-02', false, detalleOferta({ mercado: { fiscal: { regimen: 'diferido' } } })) }), 'iva-contador'), 'pendiente');
  assert.equal(claveDe(ev(base, { oferta: ofertaDe('_ejemplo', true, detalleOferta({ mercado: { fiscal: { regimen: 'oss_ue' } } })) }), 'iva-contador'), 'no_comprobable');
  assert.equal(claveDe(ev({ parametros: par() }, { oferta: ofertaDe('OF-202611-02', false, detalleOferta({ mercado: { fiscal: { regimen: 'diferido' } } })) }), 'iva-contador'), 'bloqueada', 'sin idioma elegido, primero eso');
  assert.equal(claveDe(ev({ parametros: par() }, { oferta: OFERTA_REAL_LISTA() }), 'iva-contador'), 'hecha', 'si hay evidencia directa del régimen, la evidencia manda');
});

test('cuarto nicho: solo «Hecha» si los límites ya lo admiten; si no, todavía no existe', () => {
  assert.equal(claveDe(ev({ parametros: par() }), 'cr-nicho4'), 'no_existe');
  assert.equal(claveDe(ev({ parametros: par({ macro_nichos_permitidos: ['salud', 'relaciones', 'dinero', 'habilidades'] }) }), 'cr-nicho4'), 'hecha');
});

// ───────────────────────── dependencias ─────────────────────────

test('dependencias: una tarea pendiente cuyo requisito no está hecho sale «Bloqueada por otra tarea» y dice cuál', () => {
  const r = ev({ parametros: par() }, { oferta: ofertaDe('OF-202611-02', false, detalleOferta({ estados: aprobadas('D1') })) });
  assert.equal(claveDe(r, 'of-tema'), 'hecha');
  assert.equal(claveDe(r, 'of-mercado'), 'pendiente');
  const v = tareaDe(r, 'of-validar');
  assert.equal(v.estado.clave, 'bloqueada');
  assert.deepEqual(v.estado.bloqueadaPor.map((b) => b.id), ['of-mercado']);
  assert.match(v.estado.evidencia, /Primero hay que terminar: «Elegir el idioma y los países de la oferta»/);
  assert.equal(v.leToca, false);
  assert.equal(claveDe(r, 'of-oferta'), 'bloqueada');
  assert.equal(claveDe(r, 'lz-activar'), 'bloqueada');
});

test('dependencias: el resumen y el alerta de pago esperan al canal de avisos hasta que lo marcas', () => {
  assert.equal(claveDe(ev({}), 'dia-alertas'), 'bloqueada');
  const marcado = ev({}, { marcas: { 'avisos-celular': new Date(AHORA).toISOString() } });
  assert.equal(claveDe(marcado, 'avisos-celular'), 'hecha');
  assert.equal(claveDe(marcado, 'dia-alertas'), 'no_comprobable');
});

// ───────────────────────── marcas personales ─────────────────────────

test('marca personal: convierte «No se puede comprobar sola» en «Hecha» rotulada, y quitarla lo revierte', () => {
  const sin = ev({});
  assert.equal(claveDe(sin, 'correo-entrega'), 'no_comprobable');
  assert.equal(tareaDe(sin, 'correo-entrega').estado.marcable, true);
  const con = ev({}, { marcas: { 'correo-entrega': new Date(AHORA - 3600000).toISOString() } });
  const t = tareaDe(con, 'correo-entrega');
  assert.equal(t.estado.clave, 'hecha');
  assert.equal(t.estado.origen, 'marca');
  assert.match(t.estado.evidencia, /Es una marca solo tuya: no cambia el sistema/);
  assert.equal(con.resumen.hechas, 1);
  assert.equal(con.resumen.porMarca, 1);
  assert.equal(con.resumen.porComprobacion, 0);
});

test('marca personal: no se puede marcar lo que tiene datos (frenos) ni lo que no existe', () => {
  const marcas = { frenos: new Date(AHORA).toISOString(), 'dia-fabrica': new Date(AHORA).toISOString(), 'of-tema': new Date(AHORA).toISOString() };
  const r = ev({ parametros: par() }, { marcas });
  assert.equal(claveDe(r, 'frenos'), 'pendiente');
  assert.equal(claveDe(r, 'dia-fabrica'), 'no_existe');
  assert.equal(claveDe(r, 'of-tema'), 'pendiente');
});

test('marca personal: las de cada día caducan al día siguiente y las de cada semana a la semana siguiente', () => {
  const ahora = new Date(2026, 10, 6, 12, 0, 0).getTime(); // viernes
  const hoy = new Date(2026, 10, 6, 8, 0, 0).toISOString();
  const ayer = new Date(2026, 10, 5, 23, 0, 0).toISOString();
  assert.equal(T.marcaVigente(hoy, 'dia', ahora), true);
  assert.equal(T.marcaVigente(ayer, 'dia', ahora), false);
  assert.equal(T.marcaVigente(ayer, 'unica', ahora), true);
  const lunes = new Date(2026, 10, 2, 10, 0, 0).toISOString();
  const domingoAntes = new Date(2026, 10, 1, 22, 0, 0).toISOString();
  assert.equal(T.marcaVigente(lunes, 'semana', ahora), true);
  assert.equal(T.marcaVigente(domingoAntes, 'semana', ahora), false);
  assert.equal(T.marcaVigente('no es una fecha', 'unica', ahora), false);
  const lec_ = { pulido: lec([]) };
  assert.equal(claveDe(T.evaluarTareas(lec_, { ahora, marcas: { 'dia-atencion': hoy } }), 'dia-atencion'), 'hecha');
  assert.equal(claveDe(T.evaluarTareas(lec_, { ahora, marcas: { 'dia-atencion': ayer } }), 'dia-atencion'), 'no_comprobable');
  assert.equal(claveDe(T.evaluarTareas(lec_, { ahora, marcas: { 'sem-vie': lunes } }), 'sem-vie'), 'hecha');
  assert.equal(claveDe(T.evaluarTareas(lec_, { ahora, marcas: { 'sem-vie': domingoAntes } }), 'sem-vie'), 'no_comprobable');
});

function almacenFalso(inicial = {}) {
  const m = new Map(Object.entries(inicial));
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => { m.set(k, String(v)); }, removeItem: (k) => { m.delete(k); }, _m: m };
}

test('marcas: se guardan y leen del almacén; ignora ids desconocidos, valores raros y datos corruptos; nunca lanza', () => {
  const a = almacenFalso();
  assert.equal(T.guardarMarca(a, 'avisos-celular', '2026-11-06T10:00:00Z'), true);
  assert.equal(T.guardarMarca(a, 'no-existe', '2026-11-06T10:00:00Z'), false);
  assert.deepEqual(T.leerMarcas(a), { 'avisos-celular': '2026-11-06T10:00:00Z' });
  assert.equal(T.quitarMarca(a, 'avisos-celular'), true);
  assert.deepEqual(T.leerMarcas(a), {});
  const sucio = almacenFalso({ [T.CLAVE_MARCAS]: JSON.stringify({ 'avisos-celular': '2026-11-06T10:00:00Z', hack: '2026-11-06T10:00:00Z', 'correo-entrega': 123, 'sem-vie': 'x'.repeat(500), '__proto__': 'x' }) });
  assert.deepEqual(T.leerMarcas(sucio), { 'avisos-celular': '2026-11-06T10:00:00Z' });
  assert.deepEqual(T.leerMarcas(almacenFalso({ [T.CLAVE_MARCAS]: '{no es json' })), {});
  assert.deepEqual(T.leerMarcas(almacenFalso({ [T.CLAVE_MARCAS]: '[1,2]' })), {});
  const roto = { getItem() { throw new Error('bloqueado'); }, setItem() { throw new Error('bloqueado'); } };
  assert.deepEqual(T.leerMarcas(roto), {});
  assert.equal(T.guardarMarca(roto, 'avisos-celular'), false);
  assert.deepEqual(T.leerMarcas(null), {});
  assert.equal(T.guardarMarca(null, 'avisos-celular'), false);
  assert.equal(T.leerVista(almacenFalso({ [T.CLAVE_VISTA]: 'mapa' })), 'mapa');
  assert.equal(T.leerVista(almacenFalso({ [T.CLAVE_VISTA]: 'otra' })), 'lista');
});

// ───────────────────────── la oferta elegida ─────────────────────────

test('elegirOferta: la activa, si no la primera real, si no la demo', () => {
  const lista = [{ oferta_id: '_ejemplo', demo: true }, { oferta_id: 'OF-202611-02' }, { oferta_id: 'OF-202611-03' }];
  assert.deepEqual(T.elegirOferta(lista, 'OF-202611-03'), { id: 'OF-202611-03', demo: false, motivo: 'activa' });
  assert.deepEqual(T.elegirOferta(lista, null), { id: 'OF-202611-02', demo: false, motivo: 'primera_real' });
  assert.deepEqual(T.elegirOferta(lista, 'no-existe').motivo, 'primera_real');
  assert.deepEqual(T.elegirOferta([{ oferta_id: '_ejemplo', demo: true }], null), { id: '_ejemplo', demo: true, motivo: 'solo_demo' });
  assert.equal(T.elegirOferta([], null).id, null);
  assert.equal(T.elegirOferta(null, null).id, null);
});

test('oferta demo: sus tareas se muestran pero no cuentan ni son «tu siguiente paso»', () => {
  const r = ev({ parametros: par() }, { oferta: ofertaDe('_ejemplo', true, fixtureOferta().datos) });
  const demo = r.tareas.filter((t) => t.demo);
  assert.equal(demo.length, 11);
  assert.ok(demo.every((t) => t.cuenta === false && t.porOferta));
  assert.equal(claveDe(r, 'of-tema'), 'hecha');
  assert.equal(claveDe(r, 'of-anuncios'), 'hecha');
  assert.equal(claveDe(r, 'lz-campana'), 'espera_firma', 'la demo tiene una etapa que espera firma…');
  assert.equal(tareaDe(r, 'lz-campana').leToca, true);
  assert.equal(r.resumen.total, 33);
  assert.equal(r.resumen.noCuentan, 11);
  assert.equal(r.resumen.hechas, 0, 'lo hecho en la demo no suma');
  assert.equal(r.siguiente.id, 'idioma-mercado', '…pero no es tu siguiente paso');
  assert.equal(r.siguiente.cuenta, true);
  assert.equal(r.momentos[1].demo, true);
});

test('oferta real lista: etapas aprobadas → Hecha; cumplimiento con vistos buenos vigentes; campaña prendida', () => {
  const r = ev(ESCENARIO_VERDE(), { oferta: OFERTA_REAL_LISTA() });
  for (const id of ['of-tema', 'of-mercado', 'of-validar', 'of-oferta', 'of-producto', 'of-landing', 'of-anuncios', 'of-cumplimiento', 'lz-cumplimiento', 'lz-campana', 'lz-activar', 'lz-chequeo', 'lz-frenos', 'idioma-mercado', 'frenos', 'iva-contador', 'hablante-nativo', 'chequeo-previo', 'freno-captura']) assert.equal(claveDe(r, id), 'hecha', id);
  assert.equal(claveDe(r, 'lz-baja'), 'no_existe');
  assert.equal(claveDe(r, 'dia-robots'), 'hecha');
  assert.equal(claveDe(r, 'dia-auditor'), 'en_curso');
  assert.equal(claveDe(r, 'dia-resumen'), 'no_existe');
  assert.ok(r.tareas.filter((t) => t.demo).length === 0);
  assert.ok(r.resumen.hechas >= 20);
});

test('etapas: espera firma, en revisión, bloqueada (con motivo), obsoleta y sin estado', () => {
  const det = detalleOferta({
    estados: { ...aprobadas('M1', 'D1', 'D2'), D3: 'bloqueado', D4: 'aprobado', D5: 'en_QA', D6: 'en_progreso' }, gatePendiente: [],
    extra: { D3: { bloqueo: { motivo: 'Falta el precio' } }, D4: { obsoleta: true } },
  });
  const r = ev({}, { oferta: ofertaDe('OF-202611-02', false, det) });
  assert.equal(claveDe(r, 'of-oferta'), 'en_curso');
  assert.match(tareaDe(r, 'of-oferta').estado.evidencia, /Falta el precio/);
  assert.ok(tareaDe(r, 'of-oferta').estado.alerta);
  assert.equal(claveDe(r, 'of-producto'), 'en_curso');
  assert.match(tareaDe(r, 'of-producto').estado.alerta, /rehacerla/);
  assert.match(tareaDe(r, 'of-landing').estado.evidencia, /revisión de calidad/);
  assert.match(tareaDe(r, 'of-anuncios').estado.evidencia, /se está preparando/);
  const firma = ev({}, { oferta: ofertaDe('OF-202611-02', false, detalleOferta({ estados: { ...aprobadas('M1', 'D1'), D2: 'en_QA' }, gatePendiente: ['D2'] })) });
  assert.equal(claveDe(firma, 'of-validar'), 'espera_firma');
  assert.equal(tareaDe(firma, 'of-validar').leToca, true, 'una tarea de IA que espera tu firma pasa a ser tuya');
  const sinPendientesPrevios = ev({ parametros: par({ paises_permitidos: ['ES'], locales_permitidos: ['es-ES'], moneda_limites: 'USD', gasto_diario_global: 30000, perdida_neta_acumulada_max: 300000, sello: { h: 1 } }), sistema: sis({ infra: infraVerde() }) },
    { oferta: ofertaDe('OF-202611-02', false, detalleOferta({ estados: { ...aprobadas('M1', 'D1'), D2: 'en_QA' }, gatePendiente: ['D2'] })), marcas: Object.fromEntries(['avisos-celular', 'correo-entrega', 'probar-pausa'].map((i) => [i, new Date(AHORA).toISOString()])) });
  assert.equal(sinPendientesPrevios.siguiente.id, 'iva-contador');
  const sinEstado = ev({}, { oferta: ofertaDe('OF-202611-02', false, { estado: null, etapas: [{ id: 'D1', estado: null }], brief: null, mercado: null }) });
  assert.equal(claveDe(sinEstado, 'of-tema'), 'pendiente');
  assert.equal(claveDe(ev({}, { oferta: { id: 'OF-202611-02', demo: false, lectura: caida() } }), 'of-tema'), 'no_comprobable');
  assert.equal(claveDe(ev({}, { oferta: null }), 'of-tema'), 'pendiente');
});

test('cumplimiento: vistos buenos vigentes → Hecha; vencido, alterado o ausente → no; coincide por la carpeta de la oferta', () => {
  const oferta = ofertaDe('OF-202611-02', false, detalleOferta({ estados: aprobadas('M1', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6') }));
  const conSellos = (sellos) => ev({ cumplimiento: lec({ dictamenes: [], sellos }) }, { oferta });
  assert.equal(claveDe(conSellos([sello('D5'), sello('D6')]), 'of-cumplimiento'), 'hecha');
  const venc = conSellos([sello('D5'), sello('D6', { vigencia_hasta: '2026-11-01T00:00:00Z' })]);
  assert.equal(claveDe(venc, 'of-cumplimiento'), 'en_curso');
  assert.match(tareaDe(venc, 'of-cumplimiento').estado.evidencia, /venció/);
  const alt = conSellos([sello('D5'), sello('D6', { alterado: true })]);
  assert.equal(claveDe(alt, 'of-cumplimiento'), 'en_curso');
  assert.match(tareaDe(alt, 'of-cumplimiento').estado.alerta, /alterado/);
  assert.equal(claveDe(conSellos([]), 'of-cumplimiento'), 'pendiente');
  assert.equal(claveDe(conSellos([{ legible: false, archivo: 'x.json' }, sello('D5', { oferta_id: 'OF-202611-99' })]), 'of-cumplimiento'), 'pendiente', 'ilegible o de otra oferta: no vale');
  assert.equal(claveDe(ev({ cumplimiento: caida() }, { oferta }), 'of-cumplimiento'), 'no_comprobable');
  assert.equal(claveDe(conSellos([sello('D7')]), 'lz-cumplimiento'), 'hecha', 'solo depende de la campaña armada, no de que esté aprobada');
});

test('activar la campaña: Hoy pide tu firma (comprobado en los límites); Objetivo, el sistema solo, sin implementar', () => {
  const r = ev({ parametros: par() }, { oferta: ofertaDe('OF-202611-02', false, detalleOferta({ estados: aprobadas('M1', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6'), gatePendiente: ['D7'] })) });
  const t = tareaDe(r, 'lz-activar');
  assert.equal(t.estado.clave, 'espera_firma');
  assert.equal(t.hoyObjetivo.hoy.comprobado, true);
  assert.match(t.hoyObjetivo.hoy.texto, /exige tu firma/);
  assert.match(t.hoyObjetivo.objetivo.texto, /sistema solo/);
  assert.match(t.hoyObjetivo.objetivo.fuente, /Todavía no está implementado: no rige/);
  const sinDatos = tareaDe(ev({}), 'lz-activar');
  assert.equal(sinDatos.hoyObjetivo.hoy.comprobado, null, 'sin lectura de límites no se afirma como comprobado');
  const tabla = tareaDe(ev({ gates: lec({ gates: { entradas: { 'accion:activar_campana': { gate: { N2: 'H' } } } } }) }, { oferta: ofertaDe('OF-202611-02', false, detalleOferta()) }), 'lz-activar');
  assert.equal(tabla.hoyObjetivo.hoy.comprobado, true, 'también se comprueba con la tabla de puntos de control');
});

test('robots: registro ausente → Todavía no existe; vivo → Hecha; sombra → En curso; apagado → Pendiente; ilegible → No se puede comprobar', () => {
  const con = (robots) => ev({ robots });
  assert.equal(claveDe(con(vacia()), 'dia-robots'), 'no_existe');
  assert.equal(claveDe(con(caida()), 'dia-robots'), 'no_comprobable');
  assert.equal(claveDe(con(lec({ robots: [{ id: 'escalera', estado: 'vivo' }] })), 'dia-robots'), 'hecha');
  assert.equal(claveDe(con(lec({ robots: [{ id: 'escalera', estado: 'sombra' }] })), 'dia-robots'), 'en_curso');
  assert.equal(claveDe(con(lec({ robots: [{ id: 'escalera', estado: 'apagado' }] })), 'dia-robots'), 'pendiente');
  assert.equal(claveDe(con(lec({ robots: { auditor: { estado: 'vivo' } } })), 'dia-auditor'), 'hecha', 'también acepta un mapa');
  assert.equal(claveDe(con(lec({ robots: [{ id: 'escalera', estado: 'vivo' }] })), 'dia-auditor'), 'no_existe', 'hay registro pero sin auditor');
  assert.equal(T.registroRobots(vacia()).length, 0);
  assert.equal(T.registroRobots(caida()), null);
});

test('Requiere tu atención y reglas propuestas usan la lista única y las ofertas reales', () => {
  const sin = ev({ pulido: lec([]), ofertas: lec([{ oferta_id: '_ejemplo', demo: true, gates_pendientes: ['D7'] }]) });
  assert.equal(claveDe(sin, 'dia-atencion'), 'no_comprobable', 'la demo no cuenta');
  const con = ev({ ofertas: lec([{ oferta_id: 'OF-202611-02', gates_pendientes: ['D2', 'D3'] }]), pulido: lec([{ id: '1', titulo: 'a', tipo: 'pendiente', responsable: 'dueno', estado: 'abierta' }, { id: '1', estado: 'resuelta', evento: 'estado' }, { id: '2', titulo: 'b', responsable: 'dueno' }]) });
  assert.equal(claveDe(con, 'dia-atencion'), 'pendiente');
  assert.match(tareaDe(con, 'dia-atencion').estado.evidencia, /2 pasos esperan tu firma y 1 pendiente tuyo está abierto/);
  assert.equal(claveDe(ev({ pulido: lec([]) }), 'sem-vie'), 'no_comprobable');
  const reglas = ev({ pulido: lec({ entradas: [{ id: '9', titulo: 'regla', tipo: 'regla_propuesta', estado: 'abierta' }] }) });
  assert.equal(claveDe(reglas, 'sem-vie'), 'pendiente');
  assert.match(tareaDe(reglas, 'sem-vie').estado.evidencia, /1 regla propuesta espera tu aprobación/);
  assert.equal(claveDe(ev({ pulido: caida() }), 'sem-vie'), 'no_comprobable');
});

// ───────────────────────── siguiente paso, resumen y filtros ─────────────────────────

test('siguiente paso: el primero que te toca, en el orden del negocio; marcar o resolver hace avanzar', () => {
  const todo = { parametros: par({ paises_permitidos: ['ES'], locales_permitidos: ['es-ES'], moneda_limites: 'USD', gasto_diario_global: 30000, perdida_neta_acumulada_max: 300000, sello: { h: 1 } }), sistema: sis({ infra: infraVerde() }) };
  const r = ev(todo);
  assert.equal(r.siguiente.id, 'avisos-celular');
  const r2 = ev(todo, { marcas: { 'avisos-celular': new Date(AHORA).toISOString() } });
  assert.equal(r2.siguiente.id, 'correo-entrega');
  assert.equal(T.siguientePaso([]), null);
  assert.equal(T.siguientePaso(null), null);
  const resto = ev(todo, { marcas: Object.fromEntries(['avisos-celular', 'correo-entrega', 'probar-pausa'].map((i) => [i, new Date(AHORA).toISOString()])) });
  assert.ok(['iva-contador', 'of-tema'].includes(resto.siguiente.id), resto.siguiente.id);
});

test('resumen: cuenta hechas por comprobación y por marca, tuyas y las que todavía no existen', () => {
  const r = ev(ESCENARIO_VERDE(), { oferta: OFERTA_REAL_LISTA(), marcas: { 'correo-entrega': new Date(AHORA).toISOString() } });
  assert.equal(r.resumen.total, 44);
  assert.equal(r.resumen.porMarca, 1);
  assert.equal(r.resumen.hechas, r.resumen.porComprobacion + r.resumen.porMarca);
  assert.equal(r.resumen.porcentaje, Math.round((r.resumen.hechas / 44) * 100));
  assert.equal(r.momentos[0].conteo.total, 9);
  assert.equal(r.momentos[0].conteo.hechas, r.momentos[0].tareas.filter((t) => t.estado.clave === 'hecha').length);
  assert.equal(T.resumenTareas(null).total, 0);
});

test('filtros: por quién, por estado, «para hacer» y por texto sin tildes ni mayúsculas; conserva el orden', () => {
  const r = ev({});
  assert.ok(T.filtrarTareas(r.tareas, { quien: 'dueno' }).every((t) => t.quien === 'dueno'));
  assert.equal(T.filtrarTareas(r.tareas, { quien: 'dueno' }).length, r.resumen.tuyas);
  assert.ok(T.filtrarTareas(r.tareas, { estado: 'no_existe' }).every((t) => t.estado.clave === 'no_existe'));
  const paraHacer = T.filtrarTareas(r.tareas, { estado: 'para_hacer' });
  assert.ok(paraHacer.every((t) => T.ESTADOS_PARA_HACER.includes(t.estado.clave)) && paraHacer.length > 0);
  const rev = T.filtrarTareas(r.tareas, { texto: 'REVISION cumplimiento' });
  assert.ok(rev.some((t) => t.id === 'of-cumplimiento'));
  assert.deepEqual(T.filtrarTareas(r.tareas, { texto: 'zzzxxx' }), []);
  assert.deepEqual(T.filtrarTareas(r.tareas, { quien: 'ia', estado: 'no_existe', texto: 'jurado' }).map((t) => t.id), ['dia-jurado']);
  assert.deepEqual(T.filtrarTareas(r.tareas).map((t) => t.id), r.tareas.map((t) => t.id));
  assert.equal(T.filtrarTareas(r.tareas, { quien: 'otro', estado: 'rarisimo' }).length, 44, 'valores desconocidos no filtran');
  assert.deepEqual(T.agruparPorMomento(T.filtrarTareas(r.tareas, { quien: 'dueno' })).map((g) => g.id), [0, 1, 2, 3, 4, 5]);
  assert.deepEqual(T.agruparPorMomento(T.filtrarTareas(r.tareas, { texto: 'jurado' })).map((g) => g.id), [3, 4]);
});

// ───────────────────────── comandos y acciones seguras ─────────────────────────

test('comandoFirmarEtapa: solo con ids bien formados; la huella válida se incluye, si no un marcador', () => {
  const h = `sha256:${'a'.repeat(64)}`;
  assert.equal(T.comandoFirmarEtapa('OF-202611-01', 'D7', h), `.venv/bin/python -m engine.orq firmar --oferta OF-202611-01 --etapa D7 --hash-objetivo ${h} --clave-privada <RUTA_A_TU_CLAVE> --como dueno`);
  assert.match(T.comandoFirmarEtapa('OF-202611-01', 'D7', 'sha256:corto'), /--hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS>/);
  for (const [o, e] of [["OF-1'; rm -rf / #", 'D7'], ['OF-202611-01', 'D7 && curl x'], ['OF-202611-01', ''], [null, 'D7'], ['OF-202611-01\n', 'D7'], ['$(id)', 'D7'], ['OF-202611-01', 'd7'], ['_ejemplo', 'D7']]) assert.equal(T.comandoFirmarEtapa(o, e, h), null, JSON.stringify([o, e]));
});

test('ningún comando copiable contiene el texto hostil de una oferta ni borra nada fuera de PAUSA y freno', () => {
  const hostil = fixtureHostil().datos;
  assert.ok(!T.ofertaIdValido(hostil.estado.oferta_id), 'la fixture trae un id de oferta malicioso');
  const pendientes = { ...hostil, etapas: hostil.etapas.map((e) => ({ ...e, estado: 'pendiente', gate_pendiente: false })) };
  const r = ev({}, { oferta: ofertaDe('_ejemplo', true, pendientes) });
  const comandos = r.tareas.flatMap((t) => t.pasos.map((p) => p.comando).filter(Boolean));
  assert.ok(comandos.length > 20, `solo ${comandos.length} comandos`);
  for (const c of comandos) {
    assert.ok(!c.includes("rm -rf"), c);
    assert.ok(!c.includes("'; "), c);
    if (/\brm\b/.test(c)) assert.ok(['rm empresa/PAUSA', 'rm empresa/captura/freno.json'].includes(c), `borrado inesperado: ${c}`);
  }
  assert.ok(comandos.some((c) => /--oferta <ID_DE_LA_OFERTA>/.test(c)), 'con un id hostil se usa un marcador');
});

test('lista blanca: solo acciones de lectura de la consola de Sistema, y ninguna palabra peligrosa en su id', () => {
  const ids = Object.keys(T.ACCIONES_SEGURAS);
  assert.deepEqual(ids.sort(), ['landing_validar', 'pruebas_paquete', 'validar_esquemas', 'validar_oferta']);
  for (const id of ids) assert.ok(!/live|activ|public|reembols|gast|firm|borr|paus|freno|meta|enviar|escrib/i.test(id), id);
  const usadas = new Set(T.CATALOGO.flatMap((t) => (t.acciones || []).map((a) => a.id)));
  for (const id of usadas) assert.ok(ids.includes(id), `la tarea usa una acción fuera de la lista blanca: ${id}`);
});

test('accionesDeTarea: ofrece solo lo que el servidor declara de lectura y disponible, con los argumentos exactos', () => {
  const servidor = T.normalizarAccionesServidor(cargarSobre('acciones').datos);
  const r = ev({}, { oferta: ofertaDe('_ejemplo', true, fixtureOferta().datos) });
  const c = { oferta: r.oferta };
  const val = T.accionesDeTarea(tareaDe(r, 'of-oferta'), c, servidor);
  assert.equal(val.length, 1);
  assert.deepEqual([val[0].id, val[0].disponible, val[0].args], ['validar_oferta', true, { oferta: '_ejemplo' }]);
  const land = T.accionesDeTarea(tareaDe(r, 'of-landing'), c, servidor);
  assert.deepEqual(land.map((a) => [a.id, a.disponible]), [['landing_validar', false], ['validar_oferta', true]]);
  assert.match(land[0].motivo, /no ofrece/);
  const pausa = T.accionesDeTarea(tareaDe(r, 'probar-pausa'), c, servidor);
  assert.deepEqual([pausa[0].id, pausa[0].args, pausa[0].disponible], ['pruebas_paquete', { paquete: 'infra' }, true]);
  // lo que no es de solo lectura o es «próximamente» no se ofrece
  const raro = T.normalizarAccionesServidor([{ id: 'validar_oferta', riesgo: 'escribe_local', parametros: { oferta: { tipo: 'oferta', requerido: true } } }, { id: 'pruebas_paquete', riesgo: 'lectura', proximamente: true, motivo: 'Aún no', parametros: [{ nombre: 'paquete', requerido: true }] }]);
  assert.equal(T.accionesDeTarea(tareaDe(r, 'of-oferta'), c, raro)[0].disponible, false);
  assert.equal(T.accionesDeTarea(tareaDe(r, 'probar-pausa'), c, raro)[0].motivo, 'Aún no');
  // una acción peligrosa que alguien agregue a una tarea no sale
  assert.deepEqual(T.accionesDeTarea({ acciones: [{ id: 'activar_campana' }, { id: 'exportar_local' }] }, c, servidor), []);
  // sin oferta, validar una oferta no está disponible
  const sinOferta = ev({}, {});
  assert.equal(T.accionesDeTarea(tareaDe(sinOferta, 'of-oferta'), { oferta: sinOferta.oferta }, servidor)[0].disponible, false);
  assert.deepEqual(T.accionesDeTarea(tareaDe(r, 'of-oferta'), c, null).map((a) => a.disponible), [false]);
});

test('normalizarJob y resultadoEnSimple: dicen en palabras simples cómo salió', () => {
  assert.deepEqual(T.normalizarJob({ salida: 'hola\x1b[31m\r\n', siguiente: 7, terminado: true, codigo: 0, estado: 'terminado' }, 0), { terminado: true, codigo: 0, estado: 'terminado', texto: 'hola\n', siguiente: 7 });
  assert.equal(T.normalizarJob(null, 5).siguiente, 5);
  assert.equal(T.normalizarJob({ estado: 'corriendo', salida: 'x' }, 0).terminado, false);
  assert.equal(T.resultadoEnSimple('validar_oferta', null).clave, 'corriendo');
  const bien = T.resultadoEnSimple('validar_oferta', { terminado: true, codigo: 0, estado: 'terminado' });
  assert.deepEqual([bien.clave, bien.titulo], ['ok', 'Salió bien']);
  assert.match(bien.texto, /ningún problema/);
  const mal = T.resultadoEnSimple('pruebas_paquete', { terminado: true, codigo: 1, estado: 'error' });
  assert.deepEqual([mal.clave, mal.titulo], ['error', 'Encontró problemas']);
  assert.equal(T.resultadoEnSimple('x', { terminado: true, codigo: null, estado: 'timeout' }).titulo, 'Tardó demasiado y se cortó');
  assert.equal(T.resultadoEnSimple('x', { terminado: true, codigo: 0, estado: 'tope_salida' }).clave, 'aviso');
});

test('texto hostil de los archivos: la lógica lo recorta y lo deja como texto (sin controles)', () => {
  const motivo = `<img src=x onerror=alert(1)>${'A'.repeat(500)}\u0007\u0000`;
  const r = ev({ sistema: sis({ freno_captura: { activo: true, ts: '2026-11-06T06:00:00Z', motivo } }) });
  const e = tareaDe(r, 'freno-captura').estado.evidencia;
  assert.ok(e.length < 400);
  assert.ok(!/[\u0000-\u0008]/.test(e));
  assert.ok(e.includes('<img'), 'se conserva como texto; la pantalla lo escapa');
});

// ───────────────────────── la pantalla (DOM falso) ─────────────────────────

const sobre = (datos, extra = {}) => ({ ok: true, datos, fuente: ['x'], generado_en: '2026-11-06T15:00:00Z', vacio: false, avisos: [], ...extra });
function armarApi({ sistema, parametros, ofertas, oferta, pulido, robots, cumplimiento, extra = {} } = {}) {
  const lista = ofertas || [{ oferta_id: '_ejemplo', demo: true, fase: 'en_construccion', gates_pendientes: ['D7'] }];
  const datosOferta = oferta || fixtureOferta().datos;
  return crearApiFalsa({
    '/sistema': sobre(sistema || { pausa: { activa: false }, freno_captura: { activo: true, ts: '2026-11-06T06:03:43Z', motivo: 'HTTP 403 (Document)' }, infra: null }),
    '/parametros': sobre(parametros || { limites: { valores: { paises_permitidos: [], locales_permitidos: [], gasto_diario_global: null, perdida_neta_acumulada_max: null, sello: null, acciones_gate_humano: ['activar_campana'] }, nulos: [] } }),
    '/ofertas': sobre(lista), '/oferta/_ejemplo': sobre(datosOferta), '/oferta/OF-202611-02': sobre(datosOferta),
    '/pulido': sobre([]), '/gates': sobre({ gates: null }, { vacio: true }), '/robots': sobre({}, { vacio: true }),
    '/cumplimiento': sobre({ dictamenes: [], sellos: [] }, { vacio: true }), '/cerebro': sobre({ jardin: { existe: false, propuestas: 0 } }),
    '/acciones': cargarSobre('acciones'),
    'POST /accion': { job_id: 'job-1', comando: 'python -m scripts.validar_esquemas oferta ofertas/_ejemplo' },
    '/job': sobre({ salida: 'Todo bien\n', siguiente: 10, terminado: true, codigo: 0, estado: 'terminado' }),
    ...Object.fromEntries(Object.entries(extra)),
  });
}
const almacenGlobal = almacenFalso();
globalThis.localStorage = almacenGlobal;

async function montar({ api = armarApi(), estado = {}, params = {} } = {}) {
  const ctx = crearCtx({ api, ui, ruta: 'tareas', params, estado });
  const nodo = await pagina.render(ctx);
  doc.body.appendChild(nodo);
  return { ctx, nodo, api };
}
const liberar = ({ ctx, nodo }) => { ctx._salir(); nodo.remove(); almacenGlobal._m.clear(); };
const filaDe = (nodo, id) => buscar(nodo, `.t1-tarea[data-id="${id}"]`);
const abrirPanel = (nodo, id) => buscar(nodo, `.t1-tarea[data-id="${id}"] button`).click();
const panel = () => doc.body.querySelector('.t1-pan');
const porAria = (raiz, tag, nombre) => buscarTodos(raiz, tag).find((n) => n.getAttribute('aria-label') === nombre);
const botonPorTexto = (raiz, texto) => buscarTodos(raiz, 'button').find((b) => b.textContent.includes(texto));

test('página: arriba «Tu siguiente paso» y «X de Y hechas»; abajo los 6 momentos con sus tareas', async () => {
  const m = await montar();
  const sig = buscar(m.nodo, '.t1-sig');
  assert.match(sig.textContent, /Tu siguiente paso/);
  assert.match(sig.textContent, /Elegir el primer idioma y mercado/);
  assert.match(sig.textContent, /Pendiente/);
  assert.match(buscar(sig, 'button').textContent, /Cómo hacerla/);
  assert.equal(buscar(m.nodo, '.t1-cuenta__valor').textContent, '0 de 33', 'la demo no cuenta');
  assert.match(buscar(m.nodo, '.t1-cuenta').textContent, /No cuentan 11 tareas calculadas con la oferta de demostración/);
  assert.equal(buscarTodos(m.nodo, '.t1-momento').length, 6);
  assert.equal(buscarTodos(m.nodo, '.t1-tarea').length, 44);
  assert.match(buscar(m.nodo, '.t1-herr__fin').textContent, /44 tareas/);
  assert.match(buscar(m.nodo, '.t1-aviso').textContent, /oferta de demostración/);
  // cada fila: icono, título con verbo, por qué importa, quién, estado con palabra, «Cómo hacerla»
  const fila = filaDe(m.nodo, 'frenos');
  assert.ok(fila.querySelector('svg'));
  assert.match(fila.textContent, /Fijar y firmar los frenos de gasto/);
  assert.match(fila.textContent, /Tú/);
  assert.match(fila.textContent, /Pendiente/);
  assert.equal(fila.getAttribute('data-estado'), 'pendiente');
  assert.match(filaDe(m.nodo, 'of-tema').textContent, /Hecha/);
  assert.match(filaDe(m.nodo, 'of-tema').textContent, /Demo/);
  assert.match(filaDe(m.nodo, 'dia-jurado').textContent, /Todavía no existe/);
  assert.match(filaDe(m.nodo, 'avisos-celular').textContent, /No se puede comprobar sola/);
  liberar(m);
});

test('página: lenguaje simple en lo que se ve a primera vista (sin jerga de la guía de lenguaje)', async () => {
  const m = await montar();
  assert.ok(!/\b(gate|preflight|sha256|payload|checkout|upsell|dry-run|api|endpoint|yaml|json)\b/i.test(m.nodo.textContent), 'jerga en el primer render');
  assert.equal(buscarTodos(m.nodo, 'h1').length, 1);
  liberar(m);
});

test('página: el mapa del negocio muestra los 6 momentos de izquierda a derecha con fichas con icono y palabra', async () => {
  const m = await montar();
  const radios = buscarTodos(m.nodo, '.t1-vista [role="radio"]');
  assert.deepEqual(radios.map((r) => r.getAttribute('aria-label')), ['Lista por momentos', 'Mapa del negocio']);
  radios[1].click();
  assert.equal(buscarTodos(m.nodo, '.t1-col').length, 6);
  assert.equal(buscarTodos(m.nodo, '.t1-momento').length, 0);
  const fichas = buscarTodos(m.nodo, '.t1-ficha');
  assert.equal(fichas.length, 44);
  for (const f of fichas) {
    const est = T.ESTADOS[f.getAttribute('data-estado')];
    assert.ok(est, 'estado conocido');
    assert.ok(f.querySelector('svg'), 'icono');
    assert.ok(f.textContent.includes(est.texto), `palabra de estado «${est.texto}»`);
    assert.ok(f.getAttribute('aria-label').includes(est.texto));
  }
  assert.equal(almacenGlobal._m.get(T.CLAVE_VISTA), 'mapa', 'la vista elegida se recuerda');
  assert.deepEqual(buscarTodos(m.nodo, '.t1-col').map((c) => c.getAttribute('data-momento')), ['0', '1', '2', '3', '4', '5']);
  buscar(m.nodo, '.t1-ficha[data-id="frenos"]').click();
  assert.ok(panel(), 'una ficha abre el panel «Cómo hacerla»');
  doc.teclado('Escape');
  radios[0].click();
  assert.equal(buscarTodos(m.nodo, '.t1-momento').length, 6);
  liberar(m);
});

test('página: filtros por quién, por estado y por texto; sin resultados dice qué hacer', async () => {
  const m = await montar();
  const radios = buscarTodos(m.nodo, '.t1-herr [role="radio"]');
  assert.deepEqual(radios.map((r) => r.getAttribute('aria-label')), ['Todas', 'Tú', 'El sistema', 'Una IA']);
  radios[1].click();
  const filas = buscarTodos(m.nodo, '.t1-tarea');
  assert.equal(filas.length, 15);
  assert.ok(filas.every((f) => /Tú/.test(f.textContent)));
  assert.match(buscar(m.nodo, '.t1-herr__fin').textContent, /15 de 44 tareas/);
  radios[0].click();
  const sel = porAria(m.nodo, 'select', 'Filtrar por estado');
  sel.value = 'no_existe';
  sel.disparar('change');
  assert.ok(buscarTodos(m.nodo, '.t1-tarea').every((f) => f.getAttribute('data-estado') === 'no_existe'));
  sel.value = 'todos';
  sel.disparar('change');
  const q = buscar(m.nodo, '.t1-herr__busca');
  q.value = 'jurado';
  q.disparar('input');
  const ids = buscarTodos(m.nodo, '.t1-tarea').map((f) => f.getAttribute('data-id'));
  assert.deepEqual(ids, ['dia-jurado', 'sem-mie']);
  q.value = 'zzzz';
  q.disparar('input');
  assert.equal(buscarTodos(m.nodo, '.t1-tarea').length, 0);
  assert.match(buscar(m.nodo, '.vacio-pasos').textContent, /Ninguna tarea coincide/);
  q.value = '';
  q.disparar('input');
  assert.equal(buscarTodos(m.nodo, '.t1-tarea').length, 44);
  liberar(m);
});

test('página: «Cómo hacerla» abre un panel con por qué importa, cómo se sabe, pasos numerados, comandos copiables y Esc lo cierra', async () => {
  const m = await montar();
  abrirPanel(m.nodo, 'frenos');
  const p = panel();
  assert.ok(p);
  assert.equal(p.getAttribute('role'), 'dialog');
  assert.equal(p.getAttribute('aria-modal'), 'true');
  const txt = p.textContent;
  for (const s of ['Cómo hacerla', 'Fijar y firmar los frenos de gasto', 'Por qué importa', 'Cómo se sabe', 'Pasos', 'Dónde se ve', 'Palabras clave']) assert.ok(txt.includes(s), s);
  assert.match(txt, /hoy el comando «proponer» NO carga estos dos topes/, 'dice que proponer no carga los frenos');
  assert.ok(buscarTodos(p, '.t1-paso').length >= 5);
  const comandos = buscarTodos(p, '.comando__texto').map((c) => c.textContent);
  assert.ok(comandos.some((c) => c.includes('engine.propuestas proponer')));
  assert.ok(comandos.some((c) => c.includes('sellar --como dueno --live --clave-privada')));
  assert.ok(buscarTodos(p, 'details.comando').length >= 3, 'cada comando va en el bloque «Cómo hacerlo» con su frase');
  assert.ok(buscarTodos(p, '.comando__titulo').every((t) => t.textContent.length > 10), 'una frase que dice qué hace');
  assert.equal(filaDe(m.nodo, 'frenos').getAttribute('data-abierta'), '1');
  doc.teclado('Escape');
  assert.equal(panel(), null);
  assert.equal(filaDe(m.nodo, 'frenos').getAttribute('data-abierta'), '0');
  abrirPanel(m.nodo, 'frenos');
  porAria(panel(), 'button', 'Cerrar el panel').click();
  assert.equal(panel(), null);
  liberar(m);
});

test('página: en la tarea de activar se ven «Hoy» y «Objetivo» por separado', async () => {
  const m = await montar();
  abrirPanel(m.nodo, 'lz-activar');
  const p = panel();
  assert.match(p.textContent, /Hoy/);
  assert.match(p.textContent, /Objetivo/);
  assert.match(p.textContent, /exige tu firma/);
  assert.match(p.textContent, /Todavía no está implementado: no rige/);
  assert.ok(buscar(p, '.t1-ho__caja--objetivo'));
  doc.teclado('Escape');
  liberar(m);
});

test('página: una tarea bloqueada enlaza a la que falta primero', async () => {
  const m = await montar();
  abrirPanel(m.nodo, 'iva-contador');
  const b = botonPorTexto(panel(), 'Primero: Elegir el primer idioma y mercado');
  assert.ok(b);
  b.click();
  assert.match(buscar(panel(), '.t1-pan__titulo').textContent, /Elegir el primer idioma y mercado/);
  doc.teclado('Escape');
  liberar(m);
});

test('página: «Marcar como hecha» guarda una marca solo en el navegador, sube el contador y se puede quitar', async () => {
  const m = await montar();
  abrirPanel(m.nodo, 'correo-entrega');
  const p = panel();
  assert.match(p.textContent, /Solo para ti: no cambia el sistema/);
  const llamadasAntes = m.api.llamadas.length;
  botonPorTexto(p, 'Marcar como hecha').click();
  assert.ok(almacenGlobal._m.get(T.CLAVE_MARCAS).includes('correo-entrega'));
  assert.equal(buscar(m.nodo, '.t1-cuenta__valor').textContent, '1 de 33');
  assert.match(filaDe(m.nodo, 'correo-entrega').textContent, /Hecha/);
  assert.match(filaDe(m.nodo, 'correo-entrega').textContent, /Marcada por ti/);
  assert.match(buscar(m.nodo, '.t1-cuenta').textContent, /0 comprobadas por el sistema · 1 marcadas por ti/);
  assert.match(panel().textContent, /La marcaste el/);
  assert.equal(m.api.llamadas.slice(llamadasAntes).filter((l) => l.metodo === 'POST').length, 0, 'marcar no escribe en el servidor');
  botonPorTexto(panel(), 'Quitar mi marca').click();
  assert.equal(buscar(m.nodo, '.t1-cuenta__valor').textContent, '0 de 33');
  assert.match(filaDe(m.nodo, 'correo-entrega').textContent, /No se puede comprobar sola/);
  // desde «Tu siguiente paso» también se puede marcar
  doc.teclado('Escape');
  liberar(m);
});

test('página: «Ejecutar ahora» usa la consola segura (POST /accion con id y argumentos fijos) y muestra el resultado en simple', async () => {
  const m = await montar();
  abrirPanel(m.nodo, 'of-oferta');
  const b = buscar(panel(), 'button[data-accion="validar_oferta"]');
  assert.ok(b);
  assert.match(b.textContent, /Ejecutar ahora/);
  assert.match(panel().textContent, /Solo lee: no cambia nada/);
  b.click();
  await dormir(700);
  const posts = m.api.postsA('/accion');
  assert.equal(posts.length, 1);
  assert.deepEqual(posts[0].cuerpo, { id: 'validar_oferta', args: { oferta: '_ejemplo' } });
  assert.ok(m.api.llamadas.some((l) => l.metodo === 'GET' && l.ruta === '/job/job-1'));
  const res = buscar(panel(), '.t1-res');
  assert.equal(res.getAttribute('data-clave'), 'ok');
  assert.match(res.textContent, /Salió bien/);
  assert.match(res.textContent, /ningún problema/);
  assert.match(buscar(panel(), 'button[data-accion="validar_oferta"]').textContent, /Volver a ejecutar/);
  doc.teclado('Escape');
  liberar(m);
});

test('página: si la comprobación falla, lo dice en simple y deja el detalle técnico', async () => {
  const api = armarApi({ extra: { '/job': sobre({ salida: 'FALLO: precio ausente\n', siguiente: 22, terminado: true, codigo: 1, estado: 'error' }) } });
  const m = await montar({ api });
  abrirPanel(m.nodo, 'of-oferta');
  buscar(panel(), 'button[data-accion="validar_oferta"]').click();
  await dormir(700);
  const res = buscar(panel(), '.t1-res');
  assert.equal(res.getAttribute('data-clave'), 'error');
  assert.match(res.textContent, /Encontró problemas/);
  doc.teclado('Escape');
  liberar(m);
});

test('página: lo que el servidor no ofrece sale deshabilitado con su motivo y nunca se ejecuta', async () => {
  const m = await montar();
  abrirPanel(m.nodo, 'of-landing');
  const bl = buscar(panel(), 'button[data-accion="landing_validar"]');
  assert.ok(bl.hasAttribute('disabled'));
  assert.match(panel().textContent, /El servidor no ofrece esta comprobación/);
  bl.click();
  await dormir(50);
  assert.equal(m.api.postsA('/accion').filter((p) => p.cuerpo.id === 'landing_validar').length, 0);
  assert.equal(buscarTodos(doc.body, '[data-accion="exportar_local"]').length, 0, 'las acciones que escriben nunca se ofrecen');
  doc.teclado('Escape');
  liberar(m);
});

test('SEGURIDAD: abrir cada tarea y apretar todos sus botones nunca firma, publica, activa, gasta, envía ni toca PAUSA o freno', async () => {
  const m = await montar();
  const VERBOS_PELIGROSOS = /^(firmar|publicar|activar|prender|gastar|enviar|borrar|levantar|pausar|reembolsar|aprobar|subir)/i;
  for (const id of T.IDS_TAREAS) {
    abrirPanel(m.nodo, id);
    const p = panel();
    assert.ok(p, id);
    for (const b of buscarTodos(p, 'button')) {
      assert.ok(!VERBOS_PELIGROSOS.test(b.textContent.trim()), `${id}: botón «${b.textContent.trim()}»`);
      assert.ok(b.textContent.trim() || b.getAttribute('aria-label'), `${id}: botón sin nombre`);
      if (b.className.includes('comando__copiar')) continue; // copiar al portapapeles no cambia nada (y evita avisos con temporizador)
      b.click();
    }
    doc.teclado('Escape');
  }
  const posts = m.api.llamadas.filter((l) => l.metodo === 'POST');
  assert.ok(posts.length > 0, 'se probó al menos una acción segura');
  for (const p of posts) {
    assert.equal(p.ruta, '/accion', `POST inesperado a ${p.ruta}`);
    assert.ok(T.ACCIONES_SEGURAS[p.cuerpo.id], `acción fuera de la lista blanca: ${p.cuerpo.id}`);
  }
  assert.ok(!m.api.llamadas.some((l) => /pausa|freno|firmar|activar|publicar/i.test(l.ruta)), 'ninguna ruta de pausa, freno, firma, activación ni publicación');
  assert.deepEqual([...new Set(posts.map((p) => p.cuerpo.id))].sort(), ['pruebas_paquete', 'validar_oferta']);
  liberar(m);
});

test('SEGURIDAD: el texto de los archivos entra siempre como texto (sin elementos inventados) y los controles bidi se hacen visibles', async () => {
  const hostil = fixtureHostil().datos;
  const motivo = '<img src=x onerror=alert(1)><script>alert(2)</script>‮txt.exe';
  const api = armarApi({ oferta: hostil, sistema: { pausa: { activa: false }, freno_captura: { activo: true, ts: '2026-11-06T06:00:00Z', motivo }, infra: null } });
  const m = await montar({ api });
  assert.equal(buscarTodos(m.nodo, 'img').length, 0);
  assert.equal(buscarTodos(m.nodo, 'script').length, 0);
  const fila = filaDe(m.nodo, 'freno-captura');
  assert.match(fila.textContent, /⟦U\+202E⟧/);
  assert.ok(fila.html.includes('&lt;img src=x'), 'el HTML llega escapado');
  abrirPanel(m.nodo, 'of-landing');
  const comandos = buscarTodos(panel(), '.comando__texto').map((c) => c.textContent);
  assert.ok(comandos.every((c) => !c.includes('rm -rf')));
  doc.teclado('Escape');
  liberar(m);
});

test('página: con datos que no se pueden leer lo dice y no inventa nada; sin nada de nada muestra el error con reintento', async () => {
  const falla = armarApi({ extra: { '/parametros': new Error('caído'), '/robots': new Error('caído') } });
  const m = await montar({ api: falla });
  assert.match(buscar(m.nodo, '.t1-aviso--aviso').textContent, /No se pudo leer los límites, el registro de robots/);
  assert.match(filaDe(m.nodo, 'frenos').textContent, /No se pudo leer los límites y parámetros ahora/);
  assert.equal(buscar(m.nodo, '.t1-cuenta__valor').textContent, '0 de 33');
  liberar(m);
  const caidas = crearApiFalsa({ '/sistema': new Error('x'), '/parametros': new Error('x'), '/ofertas': new Error('x'), '/pulido': new Error('x'), '/gates': new Error('x'), '/robots': new Error('x'), '/cumplimiento': new Error('x'), '/cerebro': new Error('x'), '/acciones': new Error('x') });
  const ctx = crearCtx({ api: caidas, ui, ruta: 'tareas' });
  const nodo = await pagina.render(ctx);
  assert.ok(buscar(nodo, '.error-box'));
  assert.equal(buscarTodos(nodo, '.t1-tarea').length, 0);
});

test('página: sin ofertas lo dice y el primer paso explica cómo crear una; con una oferta real muestra su estado, no el de la demo', async () => {
  const api = armarApi({ ofertas: [] });
  const m = await montar({ api });
  assert.match(buscar(m.nodo, '.t1-aviso').textContent, /Todavía no hay ninguna oferta/);
  assert.equal(buscar(m.nodo, '.t1-cuenta__valor').textContent, '0 de 44', 'sin demo todo cuenta');
  abrirPanel(m.nodo, 'of-tema');
  assert.match(panel().textContent, /\/o0-lanzar-oferta/);
  doc.teclado('Escape');
  liberar(m);
  const real = armarApi({ ofertas: [{ oferta_id: '_ejemplo', demo: true }, { oferta_id: 'OF-202611-02', demo: false }], oferta: detalleOferta({ estados: aprobadas('M1', 'D1') }) });
  const r = await montar({ api: real });
  assert.ok(real.llamadas.some((l) => l.ruta === '/oferta/OF-202611-02'), 'elige la primera oferta real');
  assert.equal(buscarTodos(r.nodo, '.t1-chip-demo').length, 0);
  assert.equal(filaDe(r.nodo, 'of-tema').getAttribute('data-estado'), 'hecha');
  assert.equal(r.nodo.textContent.includes('oferta de demostración'), false);
  liberar(r);
});

test('página: enlace profundo (?tarea=) abre el panel; el selector de oferta cambia la oferta activa', async () => {
  const cambios = [];
  const m = await montar({ params: { tarea: 'frenos' }, estado: { fijar: (p) => cambios.push(p) } });
  await dormir(30);
  assert.ok(panel());
  assert.match(buscar(panel(), '.t1-pan__titulo').textContent, /frenos/);
  doc.teclado('Escape');
  const sel = porAria(m.nodo, 'select', 'Oferta que se muestra en los momentos 1 y 2');
  assert.ok(sel);
  sel.value = '_ejemplo';
  sel.disparar('change');
  assert.deepEqual(cambios, [{ ofertaActiva: '_ejemplo' }]);
  liberar(m);
  const m2 = await montar({ params: { tarea: 'no-existe' } });
  await dormir(30);
  assert.equal(panel(), null);
  liberar(m2);
});

test('página: con el panel abierto un cambio en vivo no recarga (no se pierde lo que lees); sin panel, sí', async () => {
  const m = await montar();
  pagina.alCambio(m.ctx);
  assert.deepEqual(m.ctx._navegaciones, ['recargar']);
  m.ctx._navegaciones.length = 0;
  abrirPanel(m.nodo, 'frenos');
  assert.equal(pagina.alCambio(m.ctx), undefined);
  assert.deepEqual(m.ctx._navegaciones, []);
  doc.teclado('Escape');
  liberar(m);
});

test('página: meta de la ruta registrada en el menú', () => {
  assert.deepEqual([pagina.meta.ruta, pagina.meta.titulo, pagina.meta.grupo, pagina.meta.icono], ['tareas', 'Mis tareas', 'El sistema', 'tareas']);
  assert.ok(pagina.meta.escucha.includes('oferta'));
  assert.ok(!pagina.meta.escucha.includes('registro'), 'no se recarga con cada línea del registro');
  assert.equal(typeof pagina.render, 'function');
});
