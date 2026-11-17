// Pruebas del shell web (P2): estado.js, api.js, ui.js y las partes puras de app.js. Sin navegador: `node --test`.
// Para el DOM usa el DOM mínimo (y estricto: innerHTML lanza) de tests/fixtures/dashboard/shell/dom_falso.mjs.
import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { instalar, buscar, buscarTodos } from '../fixtures/dashboard/shell/dom_falso.mjs';

const AQUI = dirname(fileURLToPath(import.meta.url));
const WEB = join(AQUI, '..', '..', 'dashboard', 'web');
const doc = instalar();

const estadoMod = await import('../../dashboard/web/estado.js');
const apiMod = await import('../../dashboard/web/api.js');
const ui = await import('../../dashboard/web/ui.js');
const app = await import('../../dashboard/web/app.js');

const { fmt } = ui;
const NBSP = '\u00A0';

// ───────────────────────── estado.js ─────────────────────────

function almacenFalso(inicial = {}) {
  const m = new Map(Object.entries(inicial));
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), _m: m };
}

test('estado: valores por defecto y notificación solo si algo cambia', () => {
  const e = estadoMod.crearEstado(almacenFalso());
  assert.equal(e.ofertaActiva, null);
  assert.equal(e.tema, 'auto');
  assert.equal(e.sidebarColapsada, false);
  assert.equal(e.conectado, 'sin_conexion');
  const llamadas = [];
  const baja = e.suscribir((_s, cambios) => llamadas.push(cambios));
  assert.deepEqual(e.fijar({ tema: 'oscuro' }), ['tema']);
  assert.deepEqual(e.fijar({ tema: 'oscuro' }), []);
  assert.deepEqual(llamadas, [['tema']]);
  baja();
  e.fijar({ tema: 'claro' });
  assert.equal(llamadas.length, 1);
  assert.equal(e.tema, 'claro');
});

test('estado: persiste ofertaActiva, tema y sidebar; no persiste la conexión', () => {
  const al = almacenFalso();
  const e = estadoMod.crearEstado(al);
  e.fijar({ ofertaActiva: 'OF-202611-01', sidebarColapsada: true, conectado: 'sse', tema: 'oscuro' });
  assert.equal(al._m.get('panel.ofertaActiva'), '"OF-202611-01"');
  assert.equal(al._m.has('panel.conectado'), false);
  const e2 = estadoMod.crearEstado(al);
  assert.equal(e2.ofertaActiva, 'OF-202611-01');
  assert.equal(e2.sidebarColapsada, true);
  assert.equal(e2.tema, 'oscuro');
  assert.equal(e2.conectado, 'sin_conexion');
});

test('estado: valores corruptos o fuera de dominio se descartan (nunca lanza)', () => {
  const e = estadoMod.crearEstado(almacenFalso({ 'panel.tema': '{roto', 'panel.ofertaActiva': '123', 'panel.sidebarColapsada': '"si"' }));
  assert.equal(e.tema, 'auto');
  assert.equal(e.ofertaActiva, null);
  assert.equal(e.sidebarColapsada, true); // Boolean("si")
  assert.deepEqual(e.fijar({ tema: 'rosa', conectado: 'raro', inventado: 1, ofertas: 'no' }), []);
  assert.throws(() => e.suscribir('no es función'), TypeError);
});

test('estado: un suscriptor que falla no impide notificar a los demás', () => {
  const e = estadoMod.crearEstado(null);
  let visto = 0;
  const original = console.error; console.error = () => {};
  e.suscribir(() => { throw new Error('boom'); });
  e.suscribir(() => { visto += 1; });
  e.fijar({ tema: 'claro' });
  console.error = original;
  assert.equal(visto, 1);
});

// ───────────────────────── api.js ─────────────────────────

test('api: tokenDeHash y hashSinToken', () => {
  assert.equal(apiMod.tokenDeHash('#t=abcdef0123456789'), 'abcdef0123456789');
  assert.equal(apiMod.tokenDeHash('#/resumen&t=abcdef0123456789'), 'abcdef0123456789');
  assert.equal(apiMod.tokenDeHash('#/resumen?x=1&t=abcdef0123456789'), 'abcdef0123456789');
  assert.equal(apiMod.tokenDeHash('#t=corto'), null);
  assert.equal(apiMod.tokenDeHash('#/resumen'), null);
  assert.equal(apiMod.tokenDeHash(''), null);
  assert.equal(apiMod.hashSinToken('#t=abcdef0123456789'), '');
  assert.equal(apiMod.hashSinToken('#t=abcdef0123456789&/registro'), '#/registro');
  assert.equal(apiMod.hashSinToken('#/registro?x=1&t=abcdef0123456789'), '#/registro?x=1');
  assert.equal(apiMod.hashSinToken('#/ofertas'), '#/ofertas');
});

test('api: construirUrl codifica y omite vacíos', () => {
  assert.equal(apiMod.construirUrl('/sistema'), '/api/sistema');
  assert.equal(apiMod.construirUrl('registro', { limite: 5, oferta: '', etapa: null, agente: 'd3 qa&x=1' }), '/api/registro?limite=5&agente=d3%20qa%26x%3D1');
  assert.equal(apiMod.construirUrl('/x', {}), '/api/x');
});

test('api: ParserSSE junta trozos, ignora comentarios y entiende \\r\\n', () => {
  const p = new apiMod.ParserSSE();
  assert.deepEqual(p.push('event: ping\nda'), []);
  const evs = p.push('ta: {}\n\n: comentario\nevent: cambio\r\ndata: {"tipo":"registro"}\r\ndata: segunda\r\n\r\n');
  assert.equal(evs.length, 2);
  assert.deepEqual(evs[0], { evento: 'ping', datos: '{}', id: null });
  assert.equal(evs[1].evento, 'cambio');
  assert.equal(evs[1].datos, '{"tipo":"registro"}\nsegunda');
  assert.deepEqual(p.push('data: sin evento\n\n')[0], { evento: 'message', datos: 'sin evento', id: null });
});

function respuesta(estado, cuerpo) {
  return { ok: estado >= 200 && estado < 300, status: estado, json: async () => { if (cuerpo === undefined) throw new Error('no json'); return cuerpo; } };
}
const sobreOk = (datos, extra = {}) => ({ ok: true, datos, fuente: ['empresa/x.json'], generado_en: '2026-11-06T14:00:00Z', vacio: false, avisos: [], ...extra });

test('api.get devuelve datos, manda el token y no cachea', async () => {
  const llamadas = [];
  const api = apiMod.crearApi({ almacen: null, fetchFn: async (url, init) => { llamadas.push({ url, init }); return respuesta(200, sobreOk({ a: 1 })); } });
  api.fijarToken('tok-secreto-0123456789');
  assert.deepEqual(await api.get('/sistema', { x: 'y' }), { a: 1 });
  assert.equal(llamadas[0].url, '/api/sistema?x=y');
  assert.equal(llamadas[0].init.headers['X-Panel-Token'], 'tok-secreto-0123456789');
  assert.equal(llamadas[0].init.cache, 'no-store');
  assert.equal(llamadas[0].init.method, 'GET');
});

test('api.sobre expone fuente, generado_en, vacio y avisos', async () => {
  const api = apiMod.crearApi({ almacen: null, fetchFn: async () => respuesta(200, sobreOk([], { vacio: true, avisos: ['falta el archivo'], fuente: ['empresa/registro.jsonl'] })) });
  const s = await api.sobre('/registro');
  assert.equal(s.vacio, true);
  assert.deepEqual(s.datos, []);
  assert.deepEqual(s.fuente, ['empresa/registro.jsonl']);
  assert.deepEqual(s.avisos, ['falta el archivo']);
  assert.equal(s.generado_en, '2026-11-06T14:00:00Z');
});

test('api.getSobre (alias de sobre): datos, demo, fuente, avisos, vacio y generado_en; api.get sigue devolviendo solo los datos', async () => {
  const api = apiMod.crearApi({ almacen: null, fetchFn: async (url) => respuesta(200, url.includes('demo')
    ? sobreOk([{ n: 1 }], { demo: true, avisos: ['Datos de DEMOSTRACIÓN (ofertas/_ejemplo/)'], fuente: ['ofertas/_ejemplo/empresa/registro.jsonl'] })
    : sobreOk({ a: 1 })) });
  assert.equal(api.getSobre, api.sobre, 'mismo método, sin cambiar la firma existente');
  const d = await api.getSobre('/registro-demo');
  assert.deepEqual(Object.keys(d).sort(), ['avisos', 'datos', 'demo', 'fuente', 'generado_en', 'vacio']);
  assert.equal(d.demo, true);
  assert.deepEqual(d.datos, [{ n: 1 }]);
  assert.deepEqual(d.avisos, ['Datos de DEMOSTRACIÓN (ofertas/_ejemplo/)']);
  assert.deepEqual(d.fuente, ['ofertas/_ejemplo/empresa/registro.jsonl']);
  assert.equal(d.generado_en, '2026-11-06T14:00:00Z');
  const normal = await api.getSobre('/otra');
  assert.equal(normal.demo, false, 'sin clave demo en el sobre: false (nunca undefined)');
  assert.equal(normal.vacio, false);
  assert.deepEqual(await api.get('/registro-demo'), [{ n: 1 }], 'get conserva su contrato: solo datos');
  const raros = apiMod.crearApi({ almacen: null, fetchFn: async () => respuesta(200, { ok: true, datos: 1, demo: 'si', fuente: 'x', avisos: 'y' }) });
  const r = await raros.getSobre('/x');
  assert.deepEqual([r.demo, r.fuente, r.avisos, r.vacio], [false, [], [], false], 'tipos inesperados se normalizan sin lanzar');
});

test('api.post envía JSON con cabecera de contenido y token', async () => {
  let visto;
  const api = apiMod.crearApi({ almacen: null, fetchFn: async (url, init) => { visto = { url, init }; return respuesta(200, sobreOk({ job_id: 'abc' })); } });
  api.fijarToken('tok-secreto-0123456789');
  assert.deepEqual(await api.post('/accion', { id: 'x', args: { oferta: 'OF-202611-01' } }), { job_id: 'abc' });
  assert.equal(visto.init.method, 'POST');
  assert.equal(visto.init.headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(visto.init.body), { id: 'x', args: { oferta: 'OF-202611-01' } });
});

test('api: errores del servidor, token inválido, red caída y respuesta no JSON', async () => {
  const hacer = (fn) => apiMod.crearApi({ almacen: null, fetchFn: fn });
  await assert.rejects(hacer(async () => respuesta(404, { ok: false, error: { codigo: 'no_existe', mensaje: 'No existe esa oferta.' } })).get('/oferta/x'),
    (e) => e instanceof apiMod.ErrorApi && e.codigo === 'no_existe' && e.mensaje === 'No existe esa oferta.' && e.estado === 404);
  await assert.rejects(hacer(async () => respuesta(403, { ok: false, error: { mensaje: 'no' } })).get('/x'), (e) => e.codigo === 'token_invalido');
  await assert.rejects(hacer(async () => respuesta(403, undefined)).get('/x'), (e) => e.codigo === 'token_invalido');
  await assert.rejects(hacer(async () => respuesta(500, undefined)).get('/x'), (e) => e.codigo === 'respuesta_invalida' && e.estado === 500);
  await assert.rejects(hacer(async () => { throw new TypeError('Failed to fetch'); }).get('/x'), (e) => e.codigo === 'sin_conexion');
  await assert.rejects(hacer(async () => respuesta(200, { ok: false, error: { codigo: 'x', mensaje: 'y' } })).get('/x'), (e) => e.codigo === 'x');
});

test('api: el mensaje de error no filtra trazas ni rutas (solo lo que manda el servidor)', async () => {
  const api = apiMod.crearApi({ almacen: null, fetchFn: async () => respuesta(500, { ok: false, error: { codigo: 'interno', mensaje: 'Error interno.' } }) });
  await assert.rejects(api.get('/x'), (e) => !/Traceback|\/Users\//.test(e.message) && e.name === 'ErrorApi');
});

test('api.iniciarToken: lo guarda en sessionStorage y lo quita de la barra', () => {
  const al = almacenFalso();
  const api = apiMod.crearApi({ almacen: al, fetchFn: async () => {} });
  let reemplazado = null;
  const t = api.iniciarToken({ hash: '#t=abcdef0123456789', pathname: '/', search: '' }, { replaceState: (_a, _b, url) => { reemplazado = url; } });
  assert.equal(t, 'abcdef0123456789');
  assert.equal(al._m.get('panel.token'), 'abcdef0123456789');
  assert.equal(reemplazado, '/');
  // sin token en la URL: usa el guardado
  const api2 = apiMod.crearApi({ almacen: al, fetchFn: async () => {} });
  assert.equal(api2.iniciarToken({ hash: '#/resumen', pathname: '/', search: '' }, { replaceState: () => assert.fail('no debe tocar la URL') }), 'abcdef0123456789');
});

function flujo(texto) {
  const enc = new TextEncoder();
  return new ReadableStream({ start(c) { c.enqueue(enc.encode(texto)); } });
}
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

test('api.conectarEventos: SSE entrega `cambio`, ignora `ping` y marca EN VIVO', async () => {
  const eventos = []; const estados = [];
  const api = apiMod.crearApi({ almacen: null, silencioMaxMs: 60000, fetchFn: async (url, init) => {
    assert.equal(url, '/api/eventos');
    assert.equal(init.headers.Accept, 'text/event-stream');
    return { ok: true, status: 200, body: flujo('event: ping\ndata: {}\n\nevent: cambio\ndata: {"tipo":"registro","ruta":"empresa/registro.jsonl","ts":"2026-11-06T14:00:00Z"}\n\nevent: cambio\ndata: no-es-json\n\n') };
  } });
  const con = api.conectarEventos((e) => eventos.push(e), (m) => estados.push(m));
  await esperar(60);
  con.cerrar();
  assert.deepEqual(estados, ['sse']);
  assert.equal(eventos.length, 1);
  assert.equal(eventos[0].tipo, 'registro');
});

test('api.conectarEventos: si SSE falla cae a sondeo y emite pulsos; si el sondeo falla, sin conexión', async () => {
  const eventos = []; const estados = [];
  let sondeoOk = true;
  const api = apiMod.crearApi({ almacen: null, intervaloSondeoMs: 15, esperaBaseMs: 2, reintentoSseMs: 60000, fetchFn: async (url) => {
    if (url.endsWith('/eventos')) throw new TypeError('sin SSE');
    if (!sondeoOk) throw new TypeError('caído');
    return respuesta(200, sobreOk({}));
  } });
  const con = api.conectarEventos((e) => eventos.push(e), (m) => estados.push(m));
  await esperar(120);
  assert.ok(estados.includes('sondeo'), `estados: ${estados}`);
  assert.ok(eventos.some((e) => e.tipo === 'sondeo'));
  sondeoOk = false;
  await esperar(80);
  con.cerrar();
  assert.equal(estados.at(-1), 'sin_conexion');
  const n = eventos.length;
  await esperar(50);
  assert.equal(eventos.length, n, 'tras cerrar no llegan más eventos');
});

// ───────────────────────── ui.js: partes puras ─────────────────────────

test('fmt.dinero: entero en unidad menor + moneda, sin float', () => {
  assert.equal(fmt.dinero(123456, 'EUR'), `1.234,56${NBSP}€`);
  assert.equal(fmt.dinero(0, 'EUR'), `0,00${NBSP}€`);
  assert.equal(fmt.dinero(5, 'USD'), `0,05${NBSP}US$`);
  assert.equal(fmt.dinero(-5, 'USD'), `-0,05${NBSP}US$`);
  assert.equal(fmt.dinero(-123456789, 'EUR'), `-1.234.567,89${NBSP}€`);
  assert.equal(fmt.dinero(1500, 'JPY'), `1.500${NBSP}¥`, 'JPY no tiene decimales');
  assert.equal(fmt.dinero(1500, 'clp'), `1.500${NBSP}CLP`);
  assert.equal(fmt.dinero(1234, 'KWD'), `1,234${NBSP}KWD`, 'KWD tiene 3 decimales');
  assert.equal(fmt.dinero(9007199254740991, 'EUR'), `90.071.992.547.409,91${NBSP}€`, 'sin pérdida en el máximo seguro');
  assert.equal(fmt.dinero('12345', 'PLN'), `123,45${NBSP}PLN`);
});

test('fmt.dinero: entradas inválidas nunca inventan una cifra', () => {
  for (const malo of [null, undefined, NaN, Infinity, 1.5, '1.5', 'abc', {}, [], true]) assert.equal(fmt.dinero(malo, 'EUR'), '—', String(malo));
  assert.match(fmt.dinero(100, undefined), /sin moneda/);
  assert.match(fmt.dinero(100, 'EU'), /sin moneda/);
  assert.match(fmt.dinero(-100, ''), /^-1,00?|^-100/);
});

test('fmt.pct: puntos básicos', () => {
  assert.equal(fmt.pct(1234), `12,34${NBSP}%`);
  assert.equal(fmt.pct(1250), `12,5${NBSP}%`);
  assert.equal(fmt.pct(1200), `12${NBSP}%`);
  assert.equal(fmt.pct(5), `0,05${NBSP}%`);
  assert.equal(fmt.pct(0), `0${NBSP}%`);
  assert.equal(fmt.pct(-250), `-2,5${NBSP}%`);
  assert.equal(fmt.pct(1000000), `10.000${NBSP}%`);
  assert.equal(fmt.pct(null), '—');
  assert.equal(fmt.pct(1.5), '—');
});

test('fmt.bytes, fmt.num y fmt.duracion', () => {
  assert.equal(fmt.bytes(0), '0 B');
  assert.equal(fmt.bytes(1023), '1023 B');
  assert.equal(fmt.bytes(1536), '1,5 KB');
  assert.equal(fmt.bytes(1024), '1 KB');
  assert.equal(fmt.bytes(5 * 1024 * 1024), '5 MB');
  assert.equal(fmt.bytes(400 * 1024), '400 KB');
  assert.equal(fmt.bytes(-1), '—');
  assert.equal(fmt.bytes('x'), '—');
  assert.equal(fmt.num(1234567), '1.234.567');
  assert.equal(fmt.num(1234.5, 2), '1.234,50');
  assert.equal(fmt.num(-1000), '-1.000');
  assert.equal(fmt.num(NaN), '—');
  assert.equal(fmt.duracion(850), '850 ms');
  assert.equal(fmt.duracion(4200), '4,2 s');
  assert.equal(fmt.duracion(185000), '3 min 05 s');
  assert.equal(fmt.duracion(-1), '—');
});

test('fmt.fecha y fmt.relativo', () => {
  assert.equal(fmt.fecha('2026-11-06T14:02:00Z', { tz: 'UTC' }), '06/11/2026 14:02');
  assert.equal(fmt.fecha('2026-11-06T14:02:09Z', { tz: 'UTC', segundos: true }), '06/11/2026 14:02:09');
  assert.equal(fmt.fecha('2026-11-06T23:30:00Z', { tz: 'Europe/Madrid' }), '07/11/2026 00:30');
  assert.equal(fmt.fecha('2026-11-06'), '06/11/2026');
  assert.equal(fmt.fecha('2026-11-06T00:00:00Z', { tz: 'UTC' }), '06/11/2026 00:00', 'medianoche no es «24:00»');
  for (const malo of [null, undefined, '', 'ayer', '2026-13-45', 'DROP TABLE', 12.5 && {}, '2026-11-06T25:00:00Z']) assert.equal(fmt.fecha(malo), '—', String(malo));
  const t = Date.parse('2026-11-06T14:00:00Z');
  assert.equal(fmt.relativo('2026-11-06T14:00:00Z', t + 2000), 'ahora');
  assert.equal(fmt.relativo('2026-11-06T14:00:00Z', t + 30000), 'hace 30 s');
  assert.equal(fmt.relativo('2026-11-06T14:00:00Z', t + 5 * 60000), 'hace 5 min');
  assert.equal(fmt.relativo('2026-11-06T14:00:00Z', t + 3 * 3600000), 'hace 3 h');
  assert.equal(fmt.relativo('2026-11-06T14:00:00Z', t + 2 * 86400000), 'hace 2 d');
  assert.equal(fmt.relativo('2026-11-06T14:10:00Z', t), 'en 10 min');
  assert.equal(fmt.relativo('2026-09-01T00:00:00Z', t), '01/09/2026');
  assert.equal(fmt.relativo('basura', t), '—');
});

test('neutralizarTexto hace visibles los controles bidi y C0 (U+202E) y respeta tildes y saltos', () => {
  assert.equal(ui.neutralizarTexto('abc\u202Edef'), 'abc⟦U+202E⟧def');
  assert.equal(ui.neutralizarTexto('a\u2066b\u2069c'), 'a⟦U+2066⟧b⟦U+2069⟧c');
  assert.equal(ui.neutralizarTexto('x\u0000y\u001Bz'), 'x⟦U+0000⟧y⟦U+001B⟧z');
  assert.equal(ui.neutralizarTexto('Ñandú\n\tañejo — «ok»'), 'Ñandú\n\tañejo — «ok»');
  assert.equal(ui.neutralizarTexto(42), '42');
});

test('urlSegura rechaza javascript:, data: y trucos con espacios/control', () => {
  for (const ok of ['#/resumen', '/api/x', './a', 'https://127.0.0.1:8765/x', 'mailto:a@b.c', 'relativa/ruta']) assert.equal(ui.urlSegura(ok), true, ok);
  for (const mal of ['javascript:alert(1)', 'JaVaScRiPt:alert(1)', ' javascript:alert(1)', 'java\tscript:alert(1)', 'java\nscript:alert(1)', 'data:text/html,<script>', 'vbscript:x', '\u0001javascript:x']) assert.equal(ui.urlSegura(mal), false, JSON.stringify(mal));
});

test('infoEstado: mapa de estados, fases y desconocidos', () => {
  assert.deepEqual(ui.infoEstado('aprobado'), { tono: 'ok', texto: 'Aprobado' });
  assert.deepEqual(ui.infoEstado('en_QA'), { tono: 'info', texto: 'En revisión' });
  assert.deepEqual(ui.infoEstado('en_progreso'), { tono: 'info', texto: 'En progreso' });
  assert.deepEqual(ui.infoEstado('pendiente'), { tono: 'neutro', texto: 'Pendiente' });
  assert.deepEqual(ui.infoEstado('bloqueado'), { tono: 'error', texto: 'Bloqueado' });
  assert.deepEqual(ui.infoEstado('escalado'), { tono: 'aviso', texto: 'Pasó a tu decisión' });
  assert.deepEqual(ui.infoEstado('obsoleta'), { tono: 'aviso', texto: 'Desactualizada' });
  assert.deepEqual(ui.infoEstado('VERDE'), { tono: 'ok', texto: 'Verde' });
  assert.deepEqual(ui.infoEstado('en_test'), { tono: 'info', texto: 'En prueba' });
  assert.deepEqual(ui.infoEstado('algo_nuevo'), { tono: 'neutro', texto: 'algo nuevo' });
  assert.deepEqual(ui.infoEstado(null), { tono: 'neutro', texto: '—' });
});

test('tabla pura: valorDe, compararValores, ordenarFilas y filtrarFilas', () => {
  assert.equal(ui.valorDe({ a: { b: 3 } }, 'a.b'), 3);
  assert.equal(ui.valorDe({ 'a.b': 1, a: { b: 2 } }, 'a.b'), 1, 'la clave literal gana');
  assert.equal(ui.valorDe({ a: null }, 'a.b'), undefined);
  assert.equal(ui.valorDe(null, 'a'), undefined);
  assert.equal(ui.valorDe({ x: 1 }, (f) => f.x + 1), 2);

  const filas = [{ id: 'OF-10', n: 10, g: { monto: 5 } }, { id: 'OF-2', n: 2, g: { monto: 50 } }, { id: 'OF-33', n: null, g: null }, { id: 'of-1', n: 7, g: { monto: 1 } }];
  const orden = (col, dir) => ui.ordenarFilas(filas, col, dir).map((f) => f.id);
  assert.deepEqual(orden({ clave: 'n' }, 'asc'), ['OF-2', 'of-1', 'OF-10', 'OF-33']);
  assert.deepEqual(orden({ clave: 'n' }, 'desc'), ['OF-10', 'of-1', 'OF-2', 'OF-33'], 'los nulos van siempre al final');
  assert.deepEqual(orden({ clave: 'id' }, 'asc'), ['of-1', 'OF-2', 'OF-10', 'OF-33'], 'orden natural, sin distinguir mayúsculas');
  assert.deepEqual(orden({ clave: 'g' }, 'desc'), ['OF-2', 'OF-10', 'of-1', 'OF-33'], 'dinero {monto} se compara por monto');
  assert.deepEqual(orden({ clave: 'x', orden: (f) => -f.n }, 'asc'), ['OF-10', 'of-1', 'OF-2', 'OF-33']);
  assert.equal(ui.ordenarFilas(filas, { clave: 'n' }, 'asc') !== filas, true, 'no muta la entrada');
  assert.deepEqual(filas.map((f) => f.id), ['OF-10', 'OF-2', 'OF-33', 'of-1']);
  assert.deepEqual(ui.ordenarFilas([], { clave: 'n' }), []);

  const cols = [{ clave: 'id' }, { clave: 'g' }];
  assert.deepEqual(ui.filtrarFilas(filas, cols, '').length, 4);
  assert.deepEqual(ui.filtrarFilas(filas, cols, 'of-2').map((f) => f.id), ['OF-2']);
  assert.deepEqual(ui.filtrarFilas(filas, cols, '  OF  99 ').map((f) => f.id), [], 'todas las palabras deben aparecer');
  assert.deepEqual(ui.filtrarFilas([{ t: 'Campaña ÑANDÚ' }], [{ clave: 't' }], 'campana nandu').length, 1, 'sin tildes ni mayúsculas');
  assert.deepEqual(ui.filtrarFilas(filas, cols, '50').map((f) => f.id), ['OF-2'], 'busca dentro de objetos');
});

test('puntosSparkline y resumenJson', () => {
  assert.equal(ui.puntosSparkline([1]), null);
  assert.equal(ui.puntosSparkline('x'), null);
  assert.equal(ui.puntosSparkline([NaN, null, 3]), null);
  const p = ui.puntosSparkline([0, 10], 80, 22).split(' ');
  assert.deepEqual(p, ['2.0,20.0', '78.0,2.0']);
  assert.equal(ui.puntosSparkline([5, 5, 5]).split(' ').length, 3, 'serie plana no divide por cero');
  assert.equal(ui.resumenJson([1, 2]), '[…] 2 elementos');
  assert.equal(ui.resumenJson([1]), '[…] 1 elemento');
  assert.equal(ui.resumenJson({ a: 1 }), '{…} 1 clave');
  assert.equal(ui.resumenJson({}), '{…} 0 claves');
  assert.equal(ui.resumenJson(3), '');
});

// ───────────────────────── ui.js: DOM (falso, estricto) ─────────────────────────

test('el: los datos entran como texto (HTML hostil no crea nodos) y las URL peligrosas se rechazan', () => {
  const hostil = '<img src=x onerror=alert(1)><script>alert(2)</script>';
  const n = ui.el('div', { class: ['a', false, 'b'], 'data-x': hostil, dataset: { k: 'v' } }, hostil, 42, null, [ui.el('b', null, 'hijo')], false);
  assert.equal(n.className, 'a b');
  assert.equal(buscarTodos(n, 'img').length, 0);
  assert.equal(buscarTodos(n, 'script').length, 0);
  assert.ok(n.textContent.includes(hostil));
  assert.ok(n.html.includes('&lt;img src=x onerror=alert(1)&gt;'));
  assert.equal(n.dataset.k, 'v');
  assert.ok(n.textContent.includes('42'));
  assert.ok(buscar(n, 'b'));
  assert.throws(() => ui.el('div', { innerHTML: '<b>x</b>' }), /prohibido/);
  assert.throws(() => ui.el('div', { outerHTML: 'x' }), /prohibido/);
  assert.throws(() => ui.el('iframe', { srcdoc: '<script>' }), /prohibido/);
  assert.throws(() => ui.el('div', { onclick: 'alert(1)' }), /función/);
  assert.throws(() => ui.el('a', { href: 'javascript:alert(1)' }), /URL no permitida/);
  assert.doesNotThrow(() => ui.el('a', { href: '#/resumen' }));
  assert.throws(() => { const x = ui.el('div'); x.innerHTML = 'x'; }, /prohibido/, 'el DOM de pruebas confirma que nadie usa innerHTML');
});

test('el: atributos, listeners, style por CSSOM y nodos como segundo argumento', () => {
  let clics = 0;
  const b = ui.el('button', { type: 'button', onclick: () => { clics += 1; }, disabled: true, hidden: false, style: { '--p': '10%', color: 'red' } }, 'ok');
  b.click();
  assert.equal(clics, 1);
  assert.equal(b.hasAttribute('disabled'), true);
  assert.equal(b.hasAttribute('hidden'), false);
  assert.equal(b.style.getPropertyValue('--p'), '10%');
  assert.equal(b.style.color, 'red');
  const p = ui.el('p', ui.el('span', null, 'x'), 'y');
  assert.equal(p.textContent, 'xy');
  const bidi = ui.el('span', null, 'a\u202Eb');
  assert.equal(bidi.textContent, 'a⟦U+202E⟧b');
  const svg = ui.el('svg', { viewBox: '0 0 1 1', class: 'q' });
  assert.equal(svg.getAttribute('class'), 'q');
  assert.equal(svg.namespaceURI, 'http://www.w3.org/2000/svg');
});

test('chip, estadoChip, tarjeta, seccion, kv, vacio, errorBox', () => {
  assert.match(ui.chip('x', 'ok').className, /chip--ok/);
  assert.match(ui.chip('x', 'inventado').className, /chip--neutro/);
  const ec = ui.estadoChip('en_QA');
  assert.equal(ec.textContent, 'En revisión');
  assert.match(ec.className, /chip--info/);

  const t = ui.tarjeta({ titulo: 'Gasto', valor: '12,00 €', detalle: 'hoy', tono: 'ok', tendencia: [1, 2, 3] });
  assert.match(t.className, /tarjeta--ok/);
  assert.ok(buscar(t, '.tarjeta__tendencia svg'));
  const tv = ui.tarjeta({ titulo: 'Sin dato', valor: null });
  assert.equal(buscar(tv, '.tarjeta__valor').textContent, '—');
  assert.match(tv.className, /sin-valor/);
  assert.equal(buscar(ui.tarjeta({ titulo: 'x', valor: 0 }), '.tarjeta__valor').textContent, '0', 'el cero es un dato, no un vacío');

  const s = ui.seccion('Título', ui.el('p', null, 'cuerpo'), { acciones: ui.el('button', null, 'A'), ayuda: 'qué es' });
  assert.equal(buscar(s, 'h2').textContent, 'Título');
  assert.equal(s.getAttribute('aria-labelledby'), buscar(s, 'h2').id);
  assert.equal(buscar(s, '.seccion__ayuda').textContent, 'qué es');

  const k = ui.kv([['a', 'b'], ['c', null]]);
  assert.equal(buscarTodos(k, 'dt').length, 2);
  assert.equal(buscarTodos(k, 'dd')[1].textContent, '—');
  assert.equal(buscarTodos(ui.kv({ x: 1 }), 'dd')[0].textContent, '1');

  const v = ui.vacio('Nada aquí', { pista: 'Corre esto', comando: 'python -m x', fuente: ['empresa/a.json'] });
  assert.equal(v.getAttribute('role'), 'status');
  assert.equal(buscar(v, '.comando__texto').textContent, 'python -m x');
  assert.match(buscar(v, '.vacio__fuente').textContent, /empresa\/a\.json/);

  const e = ui.errorBox({ codigo: 'sin_conexion', mensaje: 'No hay conexión <b>' });
  assert.equal(e.getAttribute('role'), 'alert');
  assert.match(e.textContent, /sin_conexion/);
  assert.equal(buscarTodos(e, 'b').length, 0);
  assert.match(e.textContent, /python -m dashboard/, 'ofrece la pista de arranque');
  assert.match(ui.errorBox(new Error('boom')).textContent, /boom/);
  assert.doesNotMatch(ui.errorBox(new Error('boom')).textContent, /at .*\.js/, 'nunca muestra la traza');
  assert.match(ui.errorBox('texto plano').textContent, /texto plano/);
  assert.equal(ui.cargando().getAttribute('role'), 'status');
});

test('tabla: renderiza, ordena al hacer clic, filtra, formatea sin innerHTML y avisa si no hay filas', () => {
  const filas = [
    { id: 'OF-2', n: 2, gasto: { monto: 500, moneda: 'EUR' }, t: '<b>negrita</b>' },
    { id: 'OF-10', n: 10, gasto: { monto: 100, moneda: 'EUR' }, t: 'normal' },
    { id: 'OF-1', n: 1, gasto: null, t: null },
  ];
  const clicks = [];
  const tb = ui.tabla({
    etiqueta: 'prueba', filtro: true, ordenInicial: { clave: 'n', dir: 'asc' }, alClick: (f) => clicks.push(f.id),
    columnas: [{ clave: 'id', titulo: 'ID' }, { clave: 'n', titulo: 'N', alinear: 'der' }, { clave: 'gasto', titulo: 'Gasto' }, { clave: 't', titulo: 'Texto', ordenable: false }],
    filas,
  });
  const ids = () => buscarTodos(tb, 'tbody tr').map((tr) => tr.querySelectorAll('td')[0].textContent);
  assert.deepEqual(ids(), ['OF-1', 'OF-2', 'OF-10']);
  assert.equal(buscarTodos(tb, 'b').length, 0, 'el HTML de los datos no se interpreta');
  assert.ok(tb.textContent.includes('<b>negrita</b>'));
  assert.ok(tb.textContent.includes(`5,00${NBSP}€`), 'dinero {monto, moneda} se formatea solo');
  assert.equal(buscarTodos(tb, 'th')[3].querySelector('button'), null, 'columna no ordenable sin botón');
  assert.equal(buscarTodos(tb, 'th')[1].getAttribute('aria-sort'), 'ascending');
  // ordenar por ID: primero asc, luego desc, luego sin orden
  const btnId = buscarTodos(tb, 'th')[0].querySelector('button');
  btnId.click();
  assert.deepEqual(ids(), ['OF-1', 'OF-2', 'OF-10']);
  buscarTodos(tb, 'th')[0].querySelector('button').click();
  assert.deepEqual(ids(), ['OF-10', 'OF-2', 'OF-1']);
  assert.equal(buscarTodos(tb, 'th')[0].getAttribute('aria-sort'), 'descending');
  buscarTodos(tb, 'th')[0].querySelector('button').click();
  assert.equal(buscarTodos(tb, 'th')[0].getAttribute('aria-sort'), 'none');
  // filtrar
  const input = buscar(tb, 'input');
  input.value = 'of-10'; input.disparar('input');
  assert.deepEqual(ids(), ['OF-10']);
  assert.match(tb.textContent, /1 de 3/);
  input.value = 'zzz'; input.disparar('input');
  assert.deepEqual(ids(), []);
  assert.match(tb.textContent, /Ninguna fila coincide/);
  input.value = ''; input.disparar('input');
  // clic y teclado en fila
  buscarTodos(tb, 'tbody tr')[0].click();
  buscarTodos(tb, 'tbody tr')[1].disparar('keydown', { key: 'Enter' });
  assert.equal(clicks.length, 2);
  // actualizarFilas
  tb.actualizarFilas([{ id: 'NUEVA', n: 5 }]);
  assert.deepEqual(ids(), ['NUEVA']);
});

test('tabla: el encabezado se alinea igual que sus celdas (alinear der/centro), también en el CSS', () => {
  const tb = ui.tabla({
    columnas: [{ clave: 'a', titulo: 'Texto' }, { clave: 'b', titulo: 'Importe', alinear: 'der' }, { clave: 'c', titulo: 'Centro', alinear: 'centro', ordenable: false }],
    filas: [{ a: 'x', b: 5, c: 1 }],
  });
  const ths = buscarTodos(tb, 'th');
  const tds = buscarTodos(tb, 'tbody td');
  assert.deepEqual(ths.map((t) => t.classList.contains('alinea-der')), [false, true, false]);
  assert.deepEqual(ths.map((t) => t.classList.contains('alinea-centro')), [false, false, true]);
  for (const i of [1, 2]) assert.equal(ths[i].className.match(/alinea-\w+/)[0], tds[i].className.match(/alinea-\w+/)[0], 'misma alineación en th y td');
  assert.equal(ths[0].className.includes('alinea-'), false);
  const css = readFileSync(join(WEB, 'styles.css'), 'utf8');
  assert.match(css, /\.tabla thead th\.alinea-der\s*\{\s*text-align:\s*right/, 'la regla del th gana a `.tabla thead th { text-align: left }`');
  assert.match(css, /\.tabla thead th\.alinea-centro\s*\{\s*text-align:\s*center/);
  assert.match(css, /\.tabla thead th \{[^}]*text-align:\s*left/, 'el valor por defecto sigue siendo la izquierda');
});

test('instalarEstilos: hoja construida por CSSOM, una vez por id, sin <style> ni innerHTML; sin soporte devuelve false', () => {
  const previo = { hoja: globalThis.CSSStyleSheet, adoptadas: doc.adoptedStyleSheets };
  delete doc.adoptedStyleSheets;
  assert.equal(ui.instalarEstilos('sin-soporte', '.a{}'), false, 'sin adoptedStyleSheets no lanza');
  doc.adoptedStyleSheets = [];
  globalThis.CSSStyleSheet = class { replaceSync(c) { this.css = c; } };
  assert.equal(ui.instalarEstilos('p3', '.p3-x { color: red; }'), true);
  assert.equal(ui.instalarEstilos('p3', '.p3-otro {}'), true, 'segunda llamada con el mismo id: no duplica');
  assert.equal(doc.adoptedStyleSheets.length, 1);
  assert.equal(doc.adoptedStyleSheets[0].css, '.p3-x { color: red; }');
  assert.equal(ui.instalarEstilos('p5', '.p5-x {}'), true);
  assert.equal(doc.adoptedStyleSheets.length, 2);
  assert.equal(buscarTodos(doc.documentElement, 'style').length, 0, 'nunca crea un <style> en línea');
  globalThis.CSSStyleSheet = class { replaceSync() { throw new Error('css inválido'); } };
  assert.equal(ui.instalarEstilos('roto', 'x'), false, 'un error del navegador no rompe la pantalla');
  if (previo.hoja === undefined) delete globalThis.CSSStyleSheet; else globalThis.CSSStyleSheet = previo.hoja;
  if (previo.adoptadas === undefined) delete doc.adoptedStyleSheets; else doc.adoptedStyleSheets = previo.adoptadas;
});

test('tabla: vacío explícito, paginación «mostrar más» y celdas con null', () => {
  const vacia = ui.tabla({ columnas: [{ clave: 'a', titulo: 'A' }], filas: [], vacio: { texto: 'Aún no hay filas', pista: 'Corre esto', comando: 'python -m x' } });
  assert.match(vacia.textContent, /Aún no hay filas/);
  assert.equal(buscar(vacia, '.comando__texto').textContent, 'python -m x');
  assert.equal(buscar(vacia, '.tabla-scroll').hidden, true);

  const muchas = Array.from({ length: 1200 }, (_, i) => ({ a: i, b: null }));
  const t = ui.tabla({ columnas: [{ clave: 'a', titulo: 'A' }, { clave: 'b', titulo: 'B' }], filas: muchas, maxFilas: 500 });
  assert.equal(buscarTodos(t, 'tbody tr').length, 500);
  assert.equal(buscarTodos(t, 'tbody tr')[0].querySelectorAll('td')[1].textContent, '—', 'null se ve como «—», no como cero ni vacío');
  const mas = buscar(t, '.tabla-mas');
  assert.equal(mas.hidden, false);
  mas.click();
  assert.equal(buscarTodos(t, 'tbody tr').length, 1000);
  buscar(t, '.tabla-mas').click();
  assert.equal(buscarTodos(t, 'tbody tr').length, 1200);
  assert.equal(buscar(t, '.tabla-mas').hidden, true);
});

test('tabs: activa, navega con flechas y renderiza el panel una sola vez (también con Promise)', async () => {
  let n = 0;
  const t = ui.tabs([
    { id: 'a', titulo: 'A', render: () => { n += 1; return ui.el('p', null, 'panel A'); } },
    { id: 'b', titulo: 'B', render: async () => ui.el('p', null, 'panel B') },
    { id: 'c', titulo: 'C', render: () => { throw new Error('falla c'); } },
  ]);
  await esperar(5);
  const tabsEl = buscarTodos(t, '[role="tab"]');
  assert.equal(tabsEl.length, 3);
  assert.equal(tabsEl[0].getAttribute('aria-selected'), 'true');
  assert.equal(tabsEl[1].getAttribute('aria-selected'), 'false');
  assert.equal(tabsEl[1].getAttribute('tabindex'), '-1');
  assert.match(t.textContent, /panel A/);
  tabsEl[0].disparar('keydown', { key: 'ArrowRight' });
  await esperar(5);
  assert.equal(buscarTodos(t, '[role="tab"]')[1].getAttribute('aria-selected'), 'true');
  assert.match(t.textContent, /panel B/);
  buscarTodos(t, '[role="tab"]')[1].disparar('keydown', { key: 'End' });
  await esperar(5);
  assert.match(buscarTodos(t, '[role="tabpanel"]')[2].textContent, /falla c/, 'un panel que falla muestra errorBox, no rompe las pestañas');
  buscarTodos(t, '[role="tab"]')[2].disparar('keydown', { key: 'Home' });
  await esperar(5);
  t.activar('a');
  await esperar(5);
  assert.equal(n, 1, 'render se llama una vez');
  assert.equal(buscarTodos(t, '[role="tabpanel"]')[0].hidden, false);
  assert.equal(buscarTodos(t, '[role="tabpanel"]')[1].hidden, true);
});

test('visorJson: colapsable, recorta cadenas enormes y no interpreta HTML; visorTexto igual', () => {
  const obj = { a: { b: [1, 2, 3] }, hostil: '<script>alert(1)</script>', largo: 'x'.repeat(5000), nulo: null, lista: Array.from({ length: 250 }, (_, i) => i) };
  const v = ui.visorJson(obj, { colapsado: false });
  assert.equal(buscarTodos(v, 'script').length, 0);
  assert.ok(v.textContent.includes('<script>alert(1)</script>'));
  assert.ok(v.textContent.includes('(+4400)'), 'la cadena larga se recorta y dice cuánto');
  assert.ok(buscarTodos(v, 'details').length >= 2);
  const col = ui.visorJson(obj, { colapsado: true });
  assert.ok(buscarTodos(col, 'details').length >= 1);
  assert.equal(ui.visorJson(null).textContent.includes('null'), true);
  assert.ok(ui.visorJson([]).textContent.includes('0 elementos'));
  const circ = {}; circ.yo = circ;
  assert.doesNotThrow(() => ui.visorJson(circ), 'una referencia circular no cuelga el visor');

  const vt = ui.visorTexto('<h1>hola</h1>\n# md', { tipo: 'md' });
  assert.equal(buscarTodos(vt, 'h1').length, 0);
  assert.ok(buscar(vt, 'pre').textContent.includes('<h1>hola</h1>'));
  const largo = ui.visorTexto('y'.repeat(300000), { tipo: 'texto', maxChars: 1000 });
  assert.match(largo.textContent, /recortado/);
  assert.equal(buscar(largo, 'pre').textContent.length, 1000);
  assert.match(ui.visorTexto('{"a":1}', { tipo: 'json' }).textContent, /"a": 1/, 'json se formatea');
  assert.ok(ui.visorTexto(null).textContent !== undefined);
});

test('modal: foco, Esc cierra, devuelve el foco, acciones con alClick y confirmación', async () => {
  const abridor = ui.el('button', null, 'abrir'); doc.body.appendChild(abridor); abridor.focus();
  const llamadas = [];
  const m = ui.modal({ titulo: 'Pausar', cuerpo: ui.el('p', null, 'seguro'), acciones: [{ texto: 'No' }, { texto: 'Sí', tono: 'peligro', alClick: () => { llamadas.push('si'); } }] });
  assert.ok(doc.body.contains(m.elemento));
  const dlg = buscar(m.elemento, '[role="dialog"]');
  assert.equal(dlg.getAttribute('aria-modal'), 'true');
  assert.equal(buscar(dlg, 'h2').textContent, 'Pausar');
  assert.equal(dlg.getAttribute('aria-labelledby'), buscar(dlg, 'h2').id);
  assert.equal(doc.activeElement.textContent, 'Sí', 'el foco entra en la acción principal');
  doc.teclado('Escape');
  assert.equal(doc.body.contains(m.elemento), false);
  assert.equal(doc.activeElement, abridor, 'devuelve el foco a quien abrió');
  const m2 = ui.modal({ titulo: 'X', cuerpo: 'y', acciones: [{ texto: 'Sí', tono: 'peligro', alClick: () => { llamadas.push('si'); } }, { texto: 'Falla', alClick: () => false }] });
  buscarTodos(m2.elemento, '.modal__pie button')[1].click();
  await esperar(5);
  assert.equal(doc.body.contains(m2.elemento), true, 'alClick que devuelve false mantiene abierto el modal');
  buscarTodos(m2.elemento, '.modal__pie button')[0].click();
  await esperar(5);
  assert.deepEqual(llamadas, ['si']);
  assert.equal(doc.body.contains(m2.elemento), false);
  // confirmar → true/false
  const p = ui.confirmar({ titulo: '¿Seguro?', mensaje: 'x', textoOk: 'Hazlo' });
  const botones = buscarTodos(doc.body, '.modal__pie button');
  botones.find((b) => b.textContent === 'Hazlo').click();
  assert.equal(await p, true);
  const p2 = ui.confirmar({ titulo: '¿Seguro?', mensaje: 'x' });
  buscarTodos(doc.body, '.modal__pie button').find((b) => b.textContent === 'Cancelar').click();
  assert.equal(await p2, false);
});

test('cerrarModales: cierra todos los abiertos, devuelve el foco y desengancha el listener de Esc (lo usa el router al navegar)', () => {
  const abridor = ui.el('button', null, 'abrir'); doc.body.appendChild(abridor); abridor.focus();
  const m1 = ui.modal({ titulo: 'Uno', cuerpo: 'a', acciones: [{ texto: 'Ok' }] });
  const m2 = ui.modal({ titulo: 'Dos', cuerpo: 'b', acciones: [{ texto: 'Ok' }] });
  assert.equal(buscarTodos(doc.body, '.modal-fondo').length >= 2, true);
  assert.equal(ui.cerrarModales(), 2);
  assert.equal(doc.body.contains(m1.elemento) || doc.body.contains(m2.elemento), false);
  assert.equal(buscarTodos(doc.body, '.modal-fondo').length, 0);
  assert.equal(doc.activeElement, abridor);
  assert.equal(ui.cerrarModales(), 0, 'sin modales abiertos no hace nada');
  assert.equal((doc.escuchas.get('keydown') || []).length, 0, 'no quedan listeners de teclado colgados');
  m1.cerrar(); // cerrar de nuevo un modal ya cerrado no lanza
  assert.equal(typeof ui.ui.cerrarModales, 'function', 'también disponible en ctx.ui');
});

test('toast y copiar', async () => {
  const t = ui.toast('hecho <b>', 'ok');
  assert.equal(t.getAttribute('role'), 'status');
  assert.equal(buscarTodos(t, 'b').length, 0);
  assert.equal(ui.toast('mal', 'error', { duracion: 1 }).getAttribute('role'), 'alert');
  const cont = buscar(doc.body, '.toasts');
  assert.equal(cont.getAttribute('aria-live'), 'polite');
  for (let i = 0; i < 10; i += 1) ui.toast(`n${i}`, 'info', { duracion: 1 });
  assert.ok(cont.children.length <= 5, 'no se apilan más de 5 avisos');
  assert.equal(await ui.copiar('texto', { silencioso: true }), true);
  await esperar(10);
});

test('barraApilada, sparkline, kv, comando, encabezado y fuenteInfo', () => {
  const b = ui.barraApilada([{ valor: 3, tono: 'ok', titulo: 'a' }, { valor: 1, tono: 'error' }, { valor: 0, tono: 'ok' }]);
  const segs = buscarTodos(b, '.barra-apilada__seg');
  assert.equal(segs.length, 2);
  assert.equal(segs[0].style.getPropertyValue('--p'), '75.00%');
  assert.match(ui.barraApilada([]).className, /vacia/);
  assert.ok(ui.sparkline([1, 3, 2]).querySelector('polyline'));
  assert.equal(ui.sparkline([1]).querySelector('polyline'), null);
  assert.match(ui.comando('python -m x --y').html, /python -m x --y/);
  const e = ui.encabezado({ titulo: 'T', descripcion: 'qué es', acciones: ui.el('button', null, 'ok') });
  assert.equal(buscar(e, 'h1').textContent, 'T');
  const f = ui.fuenteInfo({ fuente: ['empresa/a.json', 'empresa/b.json'], generado_en: '2026-11-06T14:00:00Z', vacio: true, avisos: ['x <i>'] }, Date.parse('2026-11-06T14:05:00Z'));
  assert.match(f.textContent, /empresa\/a\.json, empresa\/b\.json/);
  assert.match(f.textContent, /leído hace 5 min/);
  assert.match(f.textContent, /Sin datos todavía/);
  assert.equal(buscarTodos(f, 'i').length, 0);
  assert.match(ui.fuenteInfo({}).textContent, /sin fuente declarada/);
  for (const nombre of ui.NOMBRES_ICONOS) assert.ok(ui.icono(nombre).querySelector('*'), nombre);
  assert.equal(ui.icono('no-existe').getAttribute('aria-hidden'), 'true');
});

// ───────────────────────── app.js (partes puras) ─────────────────────────

// El menú por piezas (mapeo.md §1 y §9; decisiones-del-dueno.md): «El sistema», las 6 piezas del sistema y «Dinero y reglas». Orden y literales fijados.
const MENU = [
  { grupo: 'El sistema', pieza: undefined, etiqueta: 'El sistema', rutas: ['resumen', 'negocio', 'tareas'] },
  { grupo: 'Cerebro', pieza: 1, etiqueta: '1 · Cerebro', rutas: ['cerebro', 'pulido', 'skills', 'registro'] },
  { grupo: 'Fábrica y tienda', pieza: 2, etiqueta: '2 · Fábrica y tienda', rutas: ['fabrica', 'landing', 'poscompra'] },
  { grupo: 'Jurado', pieza: 3, etiqueta: '3 · Jurado', rutas: ['jurado'] },
  { grupo: 'Testeo y escala', pieza: 4, etiqueta: '4 · Testeo y escala', rutas: ['descubrimiento', 'ofertas', 'campanas', 'operacion'] },
  { grupo: 'Robots', pieza: 5, etiqueta: '5 · Robots', rutas: ['robots', 'avisos', 'pagos', 'agentes', 'sistema'] },
  { grupo: 'Países', pieza: 6, etiqueta: '6 · Países', rutas: ['paises', 'cumplimiento'] },
  { grupo: 'Dinero y reglas', pieza: undefined, etiqueta: 'Dinero y reglas', rutas: ['finanzas', 'parametros', 'quien-decide'] },
];
/** Las 14 pantallas que ya existían antes del rediseño por piezas + el alias del detalle de una oferta: deben abrirse con la MISMA ruta. */
const RUTAS_VIEJAS = ['resumen', 'ofertas', 'descubrimiento', 'landing', 'campanas', 'operacion', 'finanzas', 'agentes', 'cumplimiento', 'parametros', 'skills', 'pulido', 'registro', 'sistema'];
const RUTAS_NUEVAS = ['cerebro', 'fabrica', 'poscompra', 'jurado', 'robots', 'avisos', 'pagos', 'paises', 'quien-decide', 'negocio'];
const ICONOS_ESPERADOS = {
  resumen: 'inicio', ofertas: 'caja', descubrimiento: 'lupa', landing: 'pantalla', campanas: 'megafono', operacion: 'pulso', finanzas: 'cartera', agentes: 'robot',
  cumplimiento: 'cumplimiento', parametros: 'ajustes', skills: 'chispa', pulido: 'lapiz', registro: 'lista', sistema: 'engranaje',
  cerebro: 'cerebro', fabrica: 'fabrica', poscompra: 'bolsa', jurado: 'balanza', robots: 'rayo', avisos: 'campana', pagos: 'tarjeta', paises: 'mundo', 'quien-decide': 'escudo', negocio: 'grafico',
};

test('app: el menú son 8 grupos (El sistema, las 6 piezas y Dinero y reglas) con sus pantallas, en este orden', () => {
  assert.deepEqual(app.NAV.map((g) => g.grupo), MENU.map((g) => g.grupo));
  assert.deepEqual(app.NAV.map((g) => g.pieza), MENU.map((g) => g.pieza), 'las piezas van de 1 a 6; «El sistema» y «Dinero y reglas» no llevan número');
  for (const [i, m] of MENU.entries()) assert.deepEqual(app.NAV[i].items.map((it) => it.ruta), m.rutas, m.grupo);
  assert.deepEqual(app.NAV.filter((g) => g.pieza).map((g) => g.pieza), [1, 2, 3, 4, 5, 6]);
  assert.equal(app.NAV.flatMap((g) => g.items).length, 25, '14 pantallas de antes + 11 nuevas: no se quitó ninguna');
  assert.equal(app.NAV.find((g) => g.grupo === 'Dinero y reglas').items.find((i) => i.ruta === 'parametros').titulo, 'Límites y reglas');
  assert.deepEqual(app.NAV.find((g) => g.grupo === 'Testeo y escala').items.find((i) => i.ruta === 'ofertas').alias, ['oferta'], 'el detalle de una oferta cuelga de Ofertas');
  assert.deepEqual(app.ENTRADAS.map((e) => e.ruta), MENU.flatMap((g) => g.rutas), 'ENTRADAS = el menú aplanado, en el mismo orden');
  for (const e of app.ENTRADAS) assert.equal(e.grupo, MENU.find((g) => g.rutas.includes(e.ruta)).grupo, `${e.ruta}: su entrada lleva el grupo literal`);
});

test('app: rutas únicas (25 pantallas + el alias oferta = 26), títulos únicos, icono y descripción de negocio en cada entrada', () => {
  const rutas = app.ENTRADAS.map((e) => e.ruta);
  assert.equal(new Set(rutas).size, rutas.length, 'ninguna ruta repetida entre grupos');
  assert.equal(rutas.length, 25);
  const alias = app.ENTRADAS.flatMap((e) => e.alias || []);
  assert.deepEqual(alias, ['oferta']);
  assert.equal(alias.filter((a) => rutas.includes(a)).length, 0, 'un alias no puede ser a la vez una ruta propia');
  assert.equal(app.RUTAS_MODULO.length, 26);
  assert.equal(new Set(app.RUTAS_MODULO).size, 26);
  assert.ok(app.RUTAS_MODULO.includes('oferta'), 'oferta (detalle) también carga módulo');
  for (const r of RUTAS_NUEVAS) assert.ok(app.RUTAS_MODULO.includes(r), `${r}: el router intenta cargar su módulo (y si no existe muestra «pronto»)`);
  const titulos = app.ENTRADAS.map((e) => ui.neutralizarTexto(e.titulo).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase());
  assert.equal(new Set(titulos).size, titulos.length, 'títulos distintos (la paleta y las migas los usan para distinguir)');
  for (const [ruta, icono] of Object.entries(ICONOS_ESPERADOS)) {
    const it = app.ENTRADAS.find((e) => e.ruta === ruta);
    assert.ok(it, `${ruta}: falta en el menú`);
    assert.equal(it.icono, icono, `${ruta}: icono ${icono}`);
  }
  for (const it of app.ENTRADAS) {
    assert.ok(ui.NOMBRES_ICONOS.includes(it.icono), `${it.ruta}: icono ${it.icono} existe`);
    assert.ok(it.desc.length > 20 && it.desc.length <= 140, `${it.ruta}: una frase, ni vacía ni larguísima (${it.desc.length})`);
    assert.match(it.desc, /[.!?]$/, `${it.ruta}: la descripción es una frase`);
    assert.doesNotMatch(it.desc, /[/_]|\.(json|jsonl|yaml|py|js)\b|\bAPI\b|\bSSE\b|--/i, `${it.ruta}: lenguaje de negocio, sin rutas ni nombres de archivo`);
  }
  for (const g of app.NAV) {
    assert.ok(g.ayuda.length > 30 && /[.]$/.test(g.ayuda), `${g.grupo}: una frase de ayuda para el tooltip`);
    assert.ok(Array.isArray(g.buscar) && g.buscar.length > 0, `${g.grupo}: palabras extra para la paleta`);
  }
});

test('app: las 14 rutas de antes (y el alias oferta) siguen abriéndose con la misma ruta y resuelven a su pantalla', () => {
  assert.equal(RUTAS_VIEJAS.length, 14);
  for (const r of RUTAS_VIEJAS) {
    assert.equal(app.parsearHash(`#/${r}`).ruta, r, r);
    assert.equal(app.parsearHash(`#/${r}`).valida, true, r);
    assert.equal(app.entradaDeRuta(r).ruta, r, `${r}: el sidebar resalta su propia entrada`);
    assert.ok(app.RUTAS_MODULO.includes(r), r);
    assert.ok(app.ENTRADAS.find((e) => e.ruta === r).atajo, `${r}: conserva su atajo g + letra`);
  }
  assert.equal(app.parsearHash('#/oferta/OF-202611-01').ruta, 'oferta');
  assert.equal(app.entradaDeRuta('oferta').ruta, 'ofertas', 'el detalle resalta Ofertas');
  assert.equal(app.entradaDeRuta('oferta').grupo, 'Testeo y escala');
  for (const r of RUTAS_NUEVAS) {
    assert.equal(app.parsearHash(`#/${r}`).ruta, r, `${r}: la ruta es válida para el router`);
    assert.equal(app.parsearHash(`#/${r}`).valida, true, r);
    assert.equal(app.entradaDeRuta(r).ruta, r, r);
  }
  assert.equal(app.parsearHash('#/quien-decide?x=1').ruta, 'quien-decide');
  assert.equal(app.entradaDeRuta('inventada'), null);
});

test('app: cada página que existe declara en meta.grupo el literal del grupo del menú donde está su ruta (ninguna quedó sin grupo)', async () => {
  const dirPaginas = join(WEB, 'pages');
  const archivos = readdirSync(dirPaginas).filter((f) => f.endsWith('.js') && !f.startsWith('_')).map((f) => f.slice(0, -3)).sort();
  for (const r of RUTAS_VIEJAS.concat('oferta')) assert.ok(archivos.includes(r), `pages/${r}.js existe: las pantallas de antes siguen`);
  assert.ok(archivos.length >= 15);
  const nombresGrupo = app.NAV.map((g) => g.grupo);
  for (const nombre of archivos) {
    const mod = await import(`../../dashboard/web/pages/${nombre}.js`);
    assert.ok(mod.meta && typeof mod.meta === 'object', `${nombre}: exporta meta`);
    assert.equal(mod.meta.ruta, nombre, `${nombre}: meta.ruta = nombre del archivo`);
    assert.equal(typeof mod.meta.grupo, 'string', `${nombre}: sin grupo`);
    assert.ok(mod.meta.grupo.length > 0, `${nombre}: sin grupo`);
    assert.ok(nombresGrupo.includes(mod.meta.grupo), `${nombre}: meta.grupo «${mod.meta.grupo}» no es un grupo del menú (${nombresGrupo.join(' · ')})`);
    const ent = app.entradaDeRuta(nombre);
    assert.ok(ent, `${nombre}: el menú no tiene su entrada`);
    assert.equal(ent.grupo, mod.meta.grupo, `${nombre}: el grupo del menú y meta.grupo coinciden`);
    assert.doesNotMatch(mod.meta.grupo, /^\d/, `${nombre}: meta.grupo es el literal, sin número de pieza`);
  }
  // las rutas nuevas aún sin página se ven como «pronto»: no hay stubs, y cuando exista la página se comprueba arriba
  const sinPagina = RUTAS_NUEVAS.filter((r) => !existsSync(join(dirPaginas, `${r}.js`)));
  for (const r of sinPagina) assert.ok(app.entradaDeRuta(r), `${r}: está en el menú aunque aún no tenga página`);
  assert.deepEqual(app.RUTAS_DEV, ['_diseno']);
  const dev = await import('../../dashboard/web/pages/_diseno.js');
  assert.equal(nombresGrupo.includes(dev.meta.grupo), false, 'la galería de desarrollo no figura en el menú');
});

test('app: etiquetaGrupo, ayudaDeGrupo e idGrupo (el número de pieza es solo del sidebar; el id es válido aunque el nombre tenga tildes y espacios)', () => {
  assert.deepEqual(app.NAV.map((g) => app.etiquetaGrupo(g)), MENU.map((g) => g.etiqueta));
  assert.equal(app.etiquetaGrupo({ grupo: 'X', pieza: 0 }), 'X');
  assert.equal(app.etiquetaGrupo({ grupo: 'X', pieza: 'a' }), 'X');
  assert.equal(app.etiquetaGrupo(null), '');
  assert.match(app.ayudaDeGrupo(app.NAV[3]), /^Pieza 3 de 6\. /);
  assert.doesNotMatch(app.ayudaDeGrupo(app.NAV[0]), /Pieza/);
  assert.equal(app.ayudaDeGrupo(null), '');
  assert.equal(app.idGrupo('Fábrica y tienda'), 'nav-g-fabrica-y-tienda');
  assert.equal(app.idGrupo('Países'), 'nav-g-paises');
  assert.equal(app.idGrupo('<b>"x"</b>'), 'nav-g-b-x-b');
  const ids = app.NAV.map((g) => app.idGrupo(g.grupo));
  assert.equal(new Set(ids).size, ids.length);
  for (const id of ids) assert.match(id, /^nav-g-[a-z0-9]+(-[a-z0-9]+)*$/);
});

test('app.construirNav: títulos «1 · Cerebro»…, tooltip por pieza, accesibilidad y un enlace por pantalla (con el DOM falso, sin innerHTML)', () => {
  const { nav, itemsNav } = app.construirNav();
  const h2 = buscarTodos(nav, 'h2');
  assert.deepEqual(h2.map((h) => h.textContent), MENU.map((g) => g.etiqueta), 'los seis grupos de pieza llevan su número; «El sistema» y «Dinero y reglas» no');
  assert.deepEqual(h2.slice(1, 7).map((h) => h.textContent.charAt(0)), ['1', '2', '3', '4', '5', '6']);
  for (const [i, h] of h2.entries()) {
    const ayuda = h.getAttribute('title');
    assert.ok(ayuda && ayuda.length > 30, `${h.textContent}: tooltip con la frase de la pieza`);
    if (MENU[i].pieza) assert.ok(ayuda.startsWith(`Pieza ${MENU[i].pieza} de 6. `), ayuda);
    else assert.ok(!ayuda.includes('Pieza'), ayuda);
    const lista = buscarTodos(nav, 'ul')[i];
    assert.equal(lista.getAttribute('aria-labelledby'), h.id, 'la lista se nombra con su título');
    const oculto = lista.getAttribute('aria-describedby');
    assert.equal(buscarTodos(nav, 'p').find((p) => p.id === oculto).textContent, ayuda, 'los lectores de pantalla oyen la misma frase');
    assert.deepEqual(buscarTodos(lista, 'a').map((a) => a.getAttribute('data-ruta')), MENU[i].rutas, `${h.textContent}: sus pantallas en orden`);
  }
  const ids = buscarTodos(nav, '[id]').map((n) => n.id);
  assert.equal(new Set(ids).size, ids.length, 'ids únicos');
  const enlaces = buscarTodos(nav, 'a');
  assert.equal(enlaces.length, 25);
  assert.equal(itemsNav.size, 25);
  for (const a of enlaces) {
    const ruta = a.getAttribute('data-ruta');
    const it = app.ENTRADAS.find((e) => e.ruta === ruta);
    assert.equal(a.getAttribute('href'), `#/${ruta}`);
    assert.ok(a.getAttribute('title').includes(it.desc), `${ruta}: el tooltip explica la pantalla`);
    assert.ok(a.getAttribute('title').includes(`(g ${it.atajo})`), `${ruta}: el tooltip dice su atajo`);
    assert.equal(a.querySelector('.nav__texto').textContent, it.titulo);
    assert.ok(a.querySelector('svg'), `${ruta}: lleva icono`);
    assert.equal(itemsNav.get(ruta).a, a);
    assert.equal(itemsNav.get(ruta).pronto.hidden, true, 'el marcador «pronto» nace oculto: lo enciende el shell si falta el módulo');
  }
  // texto hostil en un grupo: entra como texto, nunca como HTML, y el id sigue siendo válido
  const hostil = app.construirNav([{ grupo: '<img src=x onerror=alert(1)>', pieza: 7, ayuda: '<script>alert(2)</script>', items: [{ ruta: 'x', titulo: '<b>x</b>', icono: 'caja', desc: '<i>desc</i>', atajo: 'z' }] }]);
  assert.equal(buscarTodos(hostil.nav, 'img').length, 0);
  assert.equal(buscarTodos(hostil.nav, 'script').length, 0);
  assert.equal(buscarTodos(hostil.nav, 'b').length, 0);
  assert.equal(buscar(hostil.nav, 'h2').textContent, '7 · <img src=x onerror=alert(1)>');
  assert.match(buscar(hostil.nav, 'h2').id, /^nav-g-[a-z0-9-]+$/);
});

test('app.parsearHash: rutas, id, query y entradas hostiles', () => {
  const p = app.parsearHash;
  assert.deepEqual(p(''), { ruta: 'resumen', params: {}, segmentos: [], valida: true });
  assert.equal(p('#').ruta, 'resumen');
  assert.equal(p('#/').ruta, 'resumen');
  assert.deepEqual(p('#/registro').params, {});
  assert.deepEqual(p('#/oferta/OF-202611-01'), { ruta: 'oferta', params: { id: 'OF-202611-01' }, segmentos: ['OF-202611-01'], valida: true });
  assert.deepEqual(p('#/oferta/OF-202611-01/etapa/D3').params, { id: 'OF-202611-01', resto: ['etapa', 'D3'] });
  assert.deepEqual(p('#/registro?oferta=OF-1&etapa=D3').params, { oferta: 'OF-1', etapa: 'D3' });
  assert.deepEqual(p('#/registro?q=a+b%20c&solo').params, { q: 'a b c', solo: '' });
  assert.equal(p('#/oferta/OF%2F1').params.id, 'OF/1', 'decodifica el segmento');
  assert.equal(p('#/oferta/%E0%A4%A').params.id, '%E0%A4%A', 'percent-encoding roto no lanza');
  assert.equal(p('#/oferta/OF-1?id=otro').params.id, 'OF-1', 'la query no pisa el id');
  const sucio = p('#/registro?__proto__=x&constructor=y&prototype=z&ok=1').params;
  assert.deepEqual(sucio, { ok: '1' });
  assert.equal({}.x, undefined, 'sin contaminación de prototipo');
  for (const mala of ['#/<script>', '#/../etc/passwd', '#/JAVASCRIPT:alert(1)', '#/Resumen', '#/a b']) {
    const r = p(mala);
    assert.equal(r.valida, false, mala);
    assert.equal(r.ruta, 'invalida', mala);
  }
});

test('app.entradaDeRuta, contarGates, escuchaEvento', () => {
  assert.equal(app.entradaDeRuta('oferta').ruta, 'ofertas', 'oferta resalta Ofertas');
  assert.equal(app.entradaDeRuta('sistema').titulo, 'Salud del sistema');
  assert.equal(app.entradaDeRuta('nada'), null);
  assert.equal(app.contarGates([{ gates_pendientes: ['D2', 'D7'] }, { gates_pendientes: [] }, {}, null, { gates_pendientes: 'x' }]), 2);
  assert.equal(app.contarGates(null), 0);
  assert.equal(app.escuchaEvento({ escucha: ['registro'] }, { tipo: 'registro' }), true);
  assert.equal(app.escuchaEvento({ escucha: ['registro'] }, { tipo: 'oferta' }), false);
  assert.equal(app.escuchaEvento({ escucha: ['registro'] }, { tipo: 'sondeo' }), true, 'el sondeo siempre refresca');
  assert.equal(app.escuchaEvento({}, { tipo: 'cualquiera' }), true);
  assert.equal(app.escuchaEvento(undefined, { tipo: 'x' }), true);
});

test('app.crearRebote: junta eventos y llama una sola vez tras el silencio', () => {
  const pendientes = []; const llamadas = [];
  let id = 0;
  const r = app.crearRebote((lote) => llamadas.push(lote), 400, { poner: (f, ms) => { pendientes.push({ f, ms, id: ++id }); return id; }, quitar: (h) => { const i = pendientes.findIndex((p) => p.id === h); if (i !== -1) pendientes.splice(i, 1); } });
  r.empujar({ tipo: 'a' }); r.empujar({ tipo: 'b' }); r.empujar({ tipo: 'c' });
  assert.equal(pendientes.length, 1, 'solo queda el último temporizador');
  assert.equal(pendientes[0].ms, 400);
  assert.equal(r.pendiente(), 3);
  pendientes.shift().f();
  assert.deepEqual(llamadas, [[{ tipo: 'a' }, { tipo: 'b' }, { tipo: 'c' }]]);
  assert.equal(r.pendiente(), 0);
  r.empujar({ tipo: 'd' }); r.cancelar();
  assert.equal(pendientes.length, 0);
  assert.equal(r.pendiente(), 0);
});

// ───────────────────────── seguridad estática ─────────────────────────

function archivosJs(dir) {
  const out = [];
  for (const nombre of readdirSync(dir)) {
    const p = join(dir, nombre);
    if (statSync(p).isDirectory()) out.push(...archivosJs(p));
    else if (nombre.endsWith('.js')) out.push(p);
  }
  return out;
}
const sinComentarios = (src) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:\\'"`])\/\/.*$/gm, '$1');

test('seguridad estática: mis archivos no usan innerHTML, eval, document.write, new Function ni fetch externo', () => {
  const mios = ['index.html', 'app.js', 'api.js', 'ui.js', 'estado.js', 'styles.css', 'pages/resumen.js', 'pages/sistema.js', 'pages/registro.js', 'lib/resumen.js', 'lib/sistema.js', 'lib/registro.js'];
  const prohibido = /\.(innerHTML|outerHTML)\b|insertAdjacentHTML\s*\(|document\.write(ln)?\s*\(|\beval\s*\(|new\s+Function\s*\(|\bsetTimeout\s*\(\s*['"`]|\bimportScripts\s*\(/;
  for (const rel of mios) {
    const src = readFileSync(join(WEB, rel), 'utf8');
    const limpio = rel.endsWith('.js') ? sinComentarios(src) : src;
    assert.doesNotMatch(limpio, prohibido, `${rel} usa una API prohibida`);
    assert.doesNotMatch(limpio, /https?:\/\/(?!127\.0\.0\.1|localhost|www\.w3\.org)/, `${rel} referencia un origen externo`);
  }
});

test('index.html: CSP estricta, sin scripts ni estilos en línea, sin CDN', () => {
  const html = readFileSync(join(WEB, 'index.html'), 'utf8');
  assert.match(html, /Content-Security-Policy/);
  assert.match(html, /default-src 'none'/);
  assert.match(html, /script-src 'self'/);
  assert.doesNotMatch(html, /unsafe-inline|unsafe-eval/);
  assert.doesNotMatch(html, /<script(?![^>]*\bsrc=)/i, 'ningún <script> en línea');
  assert.doesNotMatch(html, /\sstyle=/i, 'ningún style en línea');
  assert.doesNotMatch(html, /\son[a-z]+\s*=/i, 'ningún manejador en línea');
  assert.doesNotMatch(html, /(src|href)=["']https?:/i, 'ningún recurso externo');
  assert.match(html, /lang="es"/);
  assert.match(html, /name="viewport"/);
});

test('styles.css: las rejillas de una columna usan minmax(0, 1fr) (una tabla ancha no estira la página) y cel-larga no fuerza más de 200 px', () => {
  const css = readFileSync(join(WEB, 'styles.css'), 'utf8');
  for (const sel of ['.pagina', '.pila', '.vacio', '.formulario', '.modal__cuerpo', '.instruccion']) {
    const m = new RegExp(`${sel.replace('.', '\\.')} \\{[^}]*grid-template-columns:\\s*minmax\\(0,\\s*1fr\\)`).exec(css);
    assert.ok(m, `${sel} debe declarar grid-template-columns: minmax(0, 1fr)`);
  }
  assert.match(css, /td\.cel-larga\s*\{[^}]*min-width:\s*200px/);
  assert.match(css, /max-width:\s*520px\)\s*\{[\s\S]*td\.cel-larga\s*\{\s*min-width:\s*150px/, 'en móvil el mínimo baja a 150 px');
});

test('styles.css: tokens de tema claro y oscuro, foco visible, sidebar 232/56 px y sin recursos remotos', () => {
  const css = readFileSync(join(WEB, 'styles.css'), 'utf8');
  assert.match(css, /--sidebar-w:\s*232px/);
  assert.match(css, /\[data-colapsada="true"\]\s*\{\s*--sidebar-w:\s*56px/);
  assert.match(css, /:root\[data-tema="oscuro"\]/);
  assert.match(css, /prefers-color-scheme:\s*dark\)\s*\{\s*:root\[data-tema="auto"\]/);
  assert.match(css, /:focus-visible/);
  assert.match(css, /prefers-reduced-motion/);
  assert.match(css, /max-width:\s*899px/, 'sidebar oculta por debajo de 900 px');
  assert.doesNotMatch(css, /@import|url\(\s*['"]?https?:|@font-face/);
});

function luminancia(hex) {
  const c = hex.replace('#', '').match(/../g).map((x) => parseInt(x, 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
const contraste = (a, b) => { const [x, y] = [luminancia(a), luminancia(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

test('contraste AA (≥ 4,5:1) de los pares texto/fondo del tema claro y oscuro', () => {
  const css = readFileSync(join(WEB, 'styles.css'), 'utf8');
  const bloque = (inicio) => { const i = css.indexOf(inicio); const f = css.indexOf('\n}', i); return css.slice(i, f); };
  const vars = (txt) => Object.fromEntries([...txt.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]));
  const claro = vars(bloque(':root {'));
  const oscuro = vars(bloque(':root[data-tema="oscuro"] {'));
  for (const [nombre, t] of [['claro', claro], ['oscuro', oscuro]]) {
    const pares = [['txt', 'bg'], ['txt', 'sup'], ['txt-2', 'sup'], ['txt-2', 'bg'], ['txt-3', 'sup'], ['txt-3', 'sup-2'], ['acento', 'sup'], ['acento-fuerte', 'acento-bg'], ['sobre-acento', 'acento'],
      ['ok', 'ok-bg'], ['aviso', 'aviso-bg'], ['error', 'error-bg'], ['info', 'info-bg'], ['neutro', 'neutro-bg'], ['ok', 'sup'], ['error', 'sup'], ['aviso', 'sup']];
    for (const [fg, bg] of pares) {
      if (!t[fg] || !t[bg]) continue;
      const r = contraste(t[fg], t[bg]);
      assert.ok(r >= 4.5, `${nombre}: --${fg} sobre --${bg} = ${r.toFixed(2)}:1 (< 4,5)`);
    }
  }
});

// ───────────────────────── modo «negocio» (por defecto) y modo «completo» ─────────────────────────

test('app: el panel abre en modo «negocio» y vuelve al completo con ?modo=completo (recordado en el navegador)', () => {
  const almacen = (() => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), m }; })();
  assert.equal(app.modoDelPanel('', almacen), 'negocio', 'sin nada: modo negocio');
  assert.equal(app.modoDelPanel('?modo=completo', almacen), 'completo');
  assert.equal(almacen.m.get(app.CLAVE_MODO), 'completo');
  assert.equal(app.modoDelPanel('', almacen), 'completo', 'queda recordado');
  assert.equal(app.modoDelPanel('?modo=negocio', almacen), 'negocio', 'y se vuelve al simple');
  assert.equal(app.modoDelPanel('', almacen), 'negocio');
  assert.equal(app.modoDelPanel('?modo=otro', null), 'negocio', 'valor raro o sin almacenamiento: negocio');
  const roto = { getItem() { throw new Error('bloqueado'); }, setItem() { throw new Error('bloqueado'); } };
  assert.equal(app.modoDelPanel('?modo=completo', roto), 'completo');
  assert.equal(app.modoDelPanel('', roto), 'negocio');
});

test('app: en modo «negocio» solo se abren Negocio y «Cómo funciona»; en el completo, todo (las rutas no se borraron)', () => {
  assert.equal(app.rutaPermitida('negocio', 'negocio'), true);
  assert.equal(app.rutaPermitida('negocio', 'flujo'), true);
  for (const r of ['resumen', 'finanzas', 'sistema', 'oferta', 'cerebro']) {
    assert.equal(app.rutaPermitida('negocio', r), false, r);
    assert.equal(app.rutaPermitida('completo', r), true, r);
    assert.ok(app.RUTAS_MODULO.includes(r), `${r}: sigue registrada`);
  }
  const simple = app.navDelModo('negocio');
  assert.equal(simple.length, 1);
  assert.deepEqual(simple[0].items.map((i) => i.ruta), ['negocio', 'flujo']);
  assert.equal(app.navDelModo('completo'), app.NAV);
  const { itemsNav } = app.construirNav(simple);
  assert.deepEqual([...itemsNav.keys()], ['negocio', 'flujo']);
  assert.equal(app.entradaDeRuta('flujo').titulo, 'Cómo funciona', 'la ruta tiene título aunque no esté en el menú completo');
  assert.ok(!app.NAV.flatMap((g) => g.items).some((i) => i.ruta === 'flujo'), 'no entra en las piezas ni en los atajos del panel completo');
});
