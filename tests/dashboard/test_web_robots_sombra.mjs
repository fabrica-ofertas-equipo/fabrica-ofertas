// Pruebas de los robots EN SOMBRA en el panel: lib/robots.js (normalizarSombra, insignias, corridas, titular, métricas y atención), la pantalla #/robots (sección «Robots en sombra»
// e insignias por robot) y el paso 6/7 de la rueda del Resumen. Los sobres de ejemplo salen de la API REAL sobre una raíz temporal donde se corrieron de verdad los robots en
// sombra (`python -m scripts.robots.sombra ejecutar --todos --escribir`): tests/fixtures/dashboard/robots/robots_sombra_{corriendo,vencido,manual}.json (los regenera generar.py).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { instalar, buscar, buscarTodos } from '../fixtures/dashboard/shell/dom_falso.mjs';
import { crearApiFalsa, crearCtx, ErrorApiFalso, cargarSobre } from '../fixtures/dashboard/shell/ctx_falso.mjs';

instalar();
const L = await import('../../dashboard/web/lib/robots.js');
const R = await import('../../dashboard/web/lib/resumen.js');
const { ui } = await import('../../dashboard/web/ui.js');
const { buscarTermino } = await import('../../dashboard/web/lib/glosario-indice.js');
const pagina = await import('../../dashboard/web/pages/robots.js');
const resumen = await import('../../dashboard/web/pages/resumen.js');

const fx = (n) => JSON.parse(readFileSync(fileURLToPath(new URL(`../fixtures/dashboard/robots/robots_sombra_${n}.json`, import.meta.url)), 'utf8'));
const AHORA = Date.parse('2026-11-07T09:35:00Z');
async function conReloj(fn, ms = AHORA) {
  const real = Date.now; Date.now = () => ms;
  try { return await fn(); } finally { Date.now = real; }
}
const ctxDe = (api, params = {}) => crearCtx({ api, ui, ruta: 'robots', params });
const sistemaOk = () => ({ ...cargarSobre('sistema'), datos: { ...cargarSobre('sistema').datos, motor_disponible: true } });
const apiCon = (sobre) => crearApiFalsa({ '/robots': { datos: {}, fuente: ['empresa/robots.yaml'], vacio: true, avisos: [] }, '/robots/sombra': sobre, '/sistema': sistemaOk(), '/parametros': cargarSobre('parametros') });
const filaDe = (raiz, id) => buscarTodos(raiz, '.n1-rb__fila[data-robot]').find((f) => f.getAttribute('data-robot') === id);
const seccion = (raiz, titulo) => buscarTodos(raiz, '.seccion').find((s) => buscar(s, '.seccion__titulo').textContent === titulo);

// ───────────────────────── lib ─────────────────────────

test('normalizarSombra: la foto real de los robots en sombra, lista para pintar (3 situaciones)', () => {
  const c = L.normalizarSombra(fx('corriendo'));
  assert.equal(c.situacion, 'corriendo');
  assert.equal(c.deHoy, true);
  assert.equal(c.filas.length, 12, '10 robots del plan + 2 programas de apoyo');
  assert.deepEqual(c.resumen.conSombra, ['perfil', 'alarma', 'vigia', 'informe', 'auditor', 'alertas', 'baja_j3']);
  assert.deepEqual(c.resumen.sinVersion, ['escalera', 'salvavidas', 'guardia', 'cola', 'bandeja']);
  assert.equal(c.resumen.vencidos.length, 0);
  assert.equal(c.porId.perfil.estadoLatido, 'al_dia');
  assert.equal(c.porId.perfil.ultimoResultado.clave, 'sin_datos');
  assert.equal(c.porId.alertas.ultimoResultado.clave, 'alerta');
  assert.equal(c.porId.escalera.estadoLatido, 'no_aplica');
  const v = L.normalizarSombra(fx('vencido'));
  assert.deepEqual([v.situacion, v.deHoy, v.resumen.vencidos.length, v.resumen.faltanHoy.length], ['vencido', false, 7, 0], 'la foto de hace 3 días no dice «hoy» ni «al día»');
  assert.equal(v.porId.informe.vencido, true);
  const m = L.normalizarSombra(fx('manual'));
  assert.deepEqual([m.situacion, m.resumen.esperados.length, m.resumen.soloManual.length], ['sin_programar', 0, 7]);
  assert.equal(m.porId.perfil.estadoLatido, 'manual');
});

test('normalizarSombra: sin estado guardado o con basura devuelve null (no se inventa nada) y lo hostil se acota', () => {
  for (const x of [null, undefined, {}, { datos: null }, { vacio: true, datos: { existe: false } }, { datos: { existe: false } }, { datos: { existe: true } }, { datos: { existe: true, robots: 'x' } }, 5]) assert.equal(L.normalizarSombra(x), null, JSON.stringify(x));
  const hostil = L.normalizarSombra({ datos: { existe: true, situacion: 'inventada', de_hoy: 'si', robots: [null, 3, { id: '../x' }, { id: 'Escalera' }, { id: 'perfil', nombre: '<img src=x onerror=alert(1)>'.repeat(20), estado_latido: 'raro', ultimo_latido: 'ayer', ultimo_resultado: 'genial', edad_min: 1.5, ultima_razon: 'x'.repeat(900) }] } });
  assert.equal(hostil.situacion, 'sin_programar', 'una situación desconocida cae en la más prudente');
  assert.equal(hostil.deHoy, false);
  assert.equal(hostil.filas.length, 1);
  const f = hostil.filas[0];
  assert.deepEqual([f.estadoLatido, f.ultimoLatido, f.ultimoResultado, f.edadMin], ['desconocido', null, null, null]);
  assert.ok(f.nombre.length <= 80 && f.ultimaRazon.length <= 200);
});

test('insignias por robot: «En sombra hoy» · «Sin versión en sombra» · «Solo S-B»; sin estado guardado no se afirma que ya corra', () => {
  const s = L.normalizarSombra(fx('corriendo'));
  const por = (id, sombra) => L.insigniaSombra(L.ROBOTS.find((r) => r.id === id), sombra ? sombra.porId[id] : null, Boolean(sombra));
  for (const id of ['perfil', 'alarma', 'vigia', 'informe', 'auditor']) assert.equal(por(id, s).texto, 'En sombra hoy', id);
  for (const id of ['escalera', 'salvavidas', 'guardia', 'cola']) assert.equal(por(id, s).texto, 'Solo S-B', id);
  assert.equal(por('bandeja', s).texto, 'Sin versión en sombra');
  for (const id of ['perfil', 'informe']) assert.equal(por(id, null).texto, 'Tiene versión en sombra', 'sin estado guardado: tiene versión, no «hoy»');
  assert.equal(por('escalera', null).texto, 'Solo S-B');
  assert.match(por('escalera', s).detalle, /no se puede ensayar/);
  // lo que el panel sabe del plan coincide con lo que dice el estado REAL de los robots en sombra (si cambia el catálogo, esta prueba avisa)
  for (const r of L.ROBOTS) assert.equal(L.SOMBRA_CATALOGO[r.id].version, s.porId[r.id].ejecutorHoy === 'sombra', r.id);
  assert.deepEqual(L.APOYO_SOMBRA.map((a) => a.id), s.filas.filter((f) => f.tipo === 'apoyo').map((f) => f.id));
});

test('corridaSombra y resultadoSombra: palabras simples, nunca un color solo', () => {
  const c = L.normalizarSombra(fx('corriendo'));
  assert.equal(L.corridaSombra(c.porId.perfil).texto, 'Al día · corrió hoy');
  assert.equal(L.corridaSombra(c.porId.escalera), null, 'sin versión en sombra no hay corrida');
  assert.match(L.corridaSombra(L.normalizarSombra(fx('vencido')).porId.perfil).texto, /Latido vencido/);
  assert.match(L.corridaSombra(L.normalizarSombra(fx('manual')).porId.perfil).texto, /solo a mano/);
  assert.equal(L.resultadoSombra('sin_decidir').texto, 'Sin decidir: faltan límites por fijar');
  assert.equal(L.resultadoSombra('alerta').tono, 'aviso');
  assert.equal(L.resultadoSombra('error').tono, 'error');
  for (const x of ['genial', '', null, '__proto__']) assert.equal(L.resultadoSombra(x), null);
  for (const r of ['ok', 'parcial', 'sin_datos', 'sin_decidir', 'alerta', 'error']) assert.ok(L.resultadoSombra(r).icono, r);
});

test('titularSombra: los tres estados con texto simple (nada programado · robots en sombra corriendo · latido vencido)', () => {
  const t = (n) => L.titularSombra(L.normalizarSombra(fx(n)));
  assert.equal(t('manual').texto, 'No hay nada programado');
  assert.match(t('manual').detalle, /solo corrieron cuando alguien los ejecutó a mano/);
  assert.equal(t('corriendo').texto, 'Robots en sombra corriendo (solo lectura)');
  assert.match(t('corriendo').detalle, /no son el sistema real/);
  assert.equal(t('vencido').texto, 'Latido vencido');
  assert.match(t('vencido').detalle, /tu Mac estuviera dormida/);
  assert.equal(L.titularSombra(null), null);
  for (const n of ['manual', 'corriendo', 'vencido']) assert.doesNotMatch(`${t(n).texto} ${t(n).detalle}`, /\.py|\.json|schema|API|endpoint/i, n);
});

test('métricas y atención con robots en sombra: «—» sin estado, vencidos avisan y una foto vieja no cuenta como hoy', () => {
  const sin = L.metricasRobots({ sistema: null, registro: null, estadoRegistro: 'vacio', ahoraMs: AHORA, sombra: null });
  assert.equal(sin.length, 5);
  assert.deepEqual([sin[4].etiqueta, sin[4].valor], ['Robots en sombra', null]);
  assert.equal(L.metricasRobots({ sistema: null, registro: null, estadoRegistro: 'vacio', ahoraMs: AHORA }).length, 4, 'si la pantalla no lo pide, nada cambia');
  const ok = L.metricasRobots({ sistema: null, registro: null, estadoRegistro: 'vacio', ahoraMs: AHORA, sombra: L.normalizarSombra(fx('corriendo')) })[4];
  assert.deepEqual([ok.valor, ok.tono], [7, null]);
  assert.match(ok.contexto, /corrieron hoy, de 7 con versión en sombra · solo lectura/);
  const vieja = L.metricasRobots({ sistema: null, registro: null, estadoRegistro: 'vacio', ahoraMs: AHORA, sombra: L.normalizarSombra(fx('vencido')) })[4];
  assert.equal(vieja.valor, null, 'el estado de hace 3 días no cuenta como «hoy»');
  assert.match(vieja.contexto, /hace 3 d/);
  const at = L.atencionRobots({ sistema: null, registro: { robots: [] }, estadoRegistro: 'vacio', ahoraMs: AHORA, sombra: L.normalizarSombra(fx('vencido')) });
  assert.match(at[0].titulo, /7 robots en sombra no dieron señal de vida a su hora/);
  assert.match(at[0].detalle, /no vigilan ni frenan nada/);
  assert.ok(at.some((x) => /no es de hoy/.test(x.titulo)));
  assert.equal(L.atencionRobots({ sistema: null, registro: { robots: [] }, estadoRegistro: 'vacio', ahoraMs: AHORA, sombra: L.normalizarSombra(fx('corriendo')) }).some((x) => /en sombra/.test(x.titulo)), false);
  assert.equal(L.textoEdad(40), '40 min');
  assert.equal(L.textoEdad(180), '3 h');
  assert.equal(L.textoEdad(4320), '3 d');
  assert.equal(L.textoEdad(NaN), 'un tiempo desconocido');
});

// ───────────────────────── pantalla Robots ─────────────────────────

test('Robots con robots en sombra corriendo: sección propia, insignia por robot, última señal y resultado, y los comandos copiables', async () => {
  const api = apiCon(fx('corriendo'));
  const raiz = await conReloj(() => pagina.render(ctxDe(api, { vista: 'plan' })));
  const sec = seccion(raiz, 'Robots en sombra: qué corrió hoy');
  assert.ok(sec, 'la sección va arriba de «Los 10 robots»');
  assert.ok(raiz.textContent.indexOf('Robots en sombra: qué corrió hoy') < raiz.textContent.indexOf('Los 10 robots y su horario'));
  assert.match(sec.textContent, /En sombra: el robot mira y propone, pero no actúa/);
  assert.match(sec.textContent, /No son el sistema real: no vigilan ni frenan nada/);
  assert.match(sec.textContent, /nunca pone en verde el semáforo/);
  assert.equal(buscar(sec, '.rs-titular').getAttribute('data-situacion'), 'corriendo');
  assert.equal(buscar(sec, '.rs-titular__titulo').textContent, 'Robots en sombra corriendo (solo lectura)');
  assert.match(sec.textContent, /7 con versión en sombra/);
  assert.match(sec.textContent, /7 corrieron hoy/);
  assert.match(sec.textContent, /5 sin versión en sombra/);
  assert.match(sec.textContent, /Estado guardado hace 35 min/);
  // programas de apoyo
  assert.deepEqual(buscarTodos(sec, '[data-apoyo]').map((x) => x.getAttribute('data-apoyo')), ['alertas', 'baja_j3']);
  assert.match(buscar(sec, '[data-apoyo="alertas"]').textContent, /Encontró una alerta/);
  assert.match(buscar(sec, '[data-apoyo="baja_j3"]').textContent, /Sin decidir: faltan límites por fijar/);
  // comandos copiables y la advertencia de que instalar es decisión del dueño
  const cmds = buscarTodos(sec, '.comando__texto').map((c) => c.textContent);
  assert.deepEqual(cmds, [L.COMANDOS_SOMBRA.simular, L.COMANDOS_SOMBRA.escribir, L.COMANDOS_SOMBRA.programar]);
  assert.match(sec.textContent, /Instalarlas es decisión tuya/);
  assert.match(sec.textContent, /esto no es una red de seguridad/);
  // insignias por robot (las 10 filas del catálogo)
  const ins = (id) => buscar(filaDe(raiz, id), '[data-sombra]').getAttribute('data-sombra');
  assert.deepEqual(['perfil', 'alarma', 'vigia', 'informe', 'auditor'].map(ins), Array(5).fill('en_sombra'));
  assert.deepEqual(['escalera', 'salvavidas', 'guardia', 'cola'].map(ins), Array(4).fill('solo_sb'));
  assert.equal(ins('bandeja'), 'sin_version');
  const perfil = filaDe(raiz, 'perfil').textContent;
  assert.match(perfil, /En sombra hoy/);
  assert.match(perfil, /Al día · corrió hoy/);
  assert.match(perfil, /Última señal de vida hace 35 min/);
  assert.match(perfil, /Sin datos todavía/);
  assert.doesNotMatch(perfil, /fabrica\.db|parametros\.yaml/, 'la razón técnica (archivos, claves) no va en el primer renglón');
  const razon = buscar(buscar(filaDe(raiz, 'perfil'), '.rs-estado'), '.detalle-tecnico');
  assert.equal(razon.hasAttribute('open'), false, 'cerrada por defecto');
  razon.open = true; razon.montar();
  assert.match(razon.textContent, /no hay base de datos/, 'la razón de su última corrida, un clic más allá');
  assert.match(filaDe(raiz, 'escalera').textContent, /Solo S-B/);
  assert.match(filaDe(raiz, 'bandeja').textContent, /Sin versión en sombra/);
  assert.doesNotMatch(filaDe(raiz, 'escalera').textContent, /Última señal de vida/, 'sin versión en sombra no hay señal que mostrar');
  // métricas y solo lectura
  const m = Object.fromEntries(buscarTodos(raiz, '.n1-metricas .metrica').map((x) => [buscar(x, '.metrica__etiqueta').textContent, buscar(x, '.metrica__valor').textContent]));
  assert.equal(m['Robots en sombra'], '7');
  assert.equal(api.postsA('/robots/sombra').length, 0);
  assert.equal(api.llamadas.filter((l) => l.metodo === 'POST').length, 0, 'solo lectura');
  const botones = buscarTodos(raiz, 'button').filter((b) => !b.classList.contains('comando__copiar') && !b.classList.contains('ayuda-btn') && !b.classList.contains('fuente-btn') && b.getAttribute('role') !== 'tab' && !/Actualizar/.test(b.textContent));
  assert.deepEqual(botones.map((b) => b.textContent), [], 'ningún botón ejecuta, programa ni instala: solo se copian comandos');
  assert.ok(buscarTermino('robots_en_sombra'));
});

test('Robots con latido vencido: el titular lo dice, aviso en «Requiere tu atención» y la foto de hace 3 días no dice «hoy»', async () => {
  const raiz = await conReloj(() => pagina.render(ctxDe(apiCon(fx('vencido')), { vista: 'plan' })), Date.parse('2026-11-10T09:35:00Z'));
  const sec = seccion(raiz, 'Robots en sombra: qué corrió hoy');
  assert.equal(buscar(sec, '.rs-titular__titulo').textContent, 'Latido vencido');
  assert.equal(buscar(sec, '.rs-titular').getAttribute('data-situacion'), 'vencido');
  assert.match(sec.textContent, /Ojo: este estado no es de hoy y no se actualiza solo/);
  assert.doesNotMatch(sec.textContent, /corrieron hoy/);
  assert.match(sec.textContent, /7 con latido vencido/);
  assert.match(buscar(raiz, '.atencion').textContent, /7 robots en sombra no dieron señal de vida a su hora/);
  assert.match(filaDe(raiz, 'vigia').textContent, /Latido vencido: no dio señal de vida a tiempo/);
});

test('Robots con robots que solo corrieron a mano: «No hay nada programado» y no hay alarma (una prueba a mano no se espera)', async () => {
  const raiz = await conReloj(() => pagina.render(ctxDe(apiCon(fx('manual')), { vista: 'plan' })));
  const sec = seccion(raiz, 'Robots en sombra: qué corrió hoy');
  assert.equal(buscar(sec, '.rs-titular__titulo').textContent, 'No hay nada programado');
  assert.match(sec.textContent, /7 solo a mano/);
  assert.match(filaDe(raiz, 'perfil').textContent, /Corrió solo a mano: no se espera su señal de vida/);
  assert.doesNotMatch(buscar(raiz, '.atencion').textContent, /no dieron señal de vida/);
});

test('Robots sin estado guardado (o servidor sin la ruta): explica cómo generarlo con comandos copiables y no inventa nada', async () => {
  for (const sobre of [{ datos: { existe: false }, vacio: true, fuente: ['empresa/robots/estado.json'], avisos: [] }, new ErrorApiFalso('no_existe', 'no')]) {
    const raiz = await conReloj(() => pagina.render(ctxDe(apiCon(sobre), { vista: 'plan' })));
    const sec = seccion(raiz, 'Robots en sombra: qué corrió hoy');
    assert.match(sec.textContent, /Todavía no corrió ningún robot en sombra/);
    assert.deepEqual(buscarTodos(sec, '.comando__texto').map((c) => c.textContent), [L.COMANDOS_SOMBRA.simular, L.COMANDOS_SOMBRA.escribir, L.COMANDOS_SOMBRA.programar]);
    assert.match(sec.textContent, /instalar es decisión tuya/);
    assert.equal(buscarTodos(sec, '.rs-titular').length, 0);
    assert.equal(buscar(filaDe(raiz, 'perfil'), '[data-sombra]').getAttribute('data-sombra'), 'con_version', 'sin estado no se afirma que corra hoy');
    assert.match(filaDe(raiz, 'perfil').textContent, /Todavía no corrió: falta guardar su estado/);
    assert.equal(buscar(filaDe(raiz, 'escalera'), '[data-sombra]').getAttribute('data-sombra'), 'solo_sb');
  }
});

test('Robots: con registro oficial (robots.yaml) sigue como hoy y las insignias de sombra se suman sin pisarlo', async () => {
  const api = crearApiFalsa({ '/robots': { datos: { robots: { perfil: { nombre: 'Perfil por idioma', estado: 'sombra', nivel: 'N0', horario: '23:40', ultimo_latido: '2026-11-07T09:00:00Z', latido_max_min: 1530 } } }, fuente: ['empresa/robots.yaml'], vacio: false, avisos: [] }, '/robots/sombra': fx('corriendo'), '/sistema': sistemaOk(), '/parametros': cargarSobre('parametros') });
  const raiz = await conReloj(() => pagina.render(ctxDe(api, { vista: 'plan' })));
  assert.match(filaDe(raiz, 'perfil').textContent, /En sombra/);
  assert.match(filaDe(raiz, 'perfil').textContent, /Al día · hace 35 min/, 'la señal de vida del registro oficial sigue ahí');
  assert.match(filaDe(raiz, 'perfil').textContent, /En sombra hoy/);
});

test('Robots (registro real vacío) con estado en sombra: lo avisa en vez de decir que no hay nada', async () => {
  const raiz = await conReloj(() => pagina.render(ctxDe(apiCon(fx('corriendo')), { vista: 'registro' })));
  assert.match(raiz.textContent, /Todavía no hay registro de robots/);
  assert.match(raiz.textContent, /los robots en sombra dejan su propio estado guardado/);
});

test('Robots: el texto hostil del estado en sombra se muestra como texto', async () => {
  const hostil = '<img src=x onerror=alert(1)><script>alert(2)</script>';
  const sobre = fx('corriendo');
  sobre.datos.robots[4].ultima_razon = hostil;
  sobre.datos.robots[4].nombre = hostil;
  sobre.datos.avisos = [hostil];
  const raiz = await conReloj(() => pagina.render(ctxDe(apiCon(sobre), { vista: 'plan' })));
  assert.equal(buscarTodos(raiz, 'img').length, 0);
  assert.equal(buscarTodos(raiz, 'script').length, 0);
  assert.ok(raiz.textContent.includes(hostil.slice(0, 40)));
});

// ───────────────────────── Resumen: rueda ─────────────────────────

test('rueda del Resumen (paso 6 y 7): con robots en sombra lo dice con honestidad; sin ellos, igual que antes', () => {
  const pasos = (sombra) => Object.fromEntries(R.pasosRueda({ pulido: null, ofertas: [], robots: null, sombra, ahoraMs: AHORA }).map((p) => [p.id, p]));
  const sin = pasos(null);
  assert.match(sin.robots.dato, /Aún no hay registro de robots/);
  const c = pasos(L.normalizarSombra(fx('corriendo')));
  assert.equal(c.robots.estado, 'sin_datos', 'robots en sombra corriendo NUNCA es «En marcha»');
  assert.match(c.robots.dato, /Robots en sombra corriendo \(solo lectura\): 7 de 7 corrieron hoy/);
  assert.match(c.robots.nota, /no vigilan ni frenan nada/);
  assert.match(c.auditor.dato, /El auditor corre en sombra \(solo lectura\): sin datos todavía/);
  const v = pasos(L.normalizarSombra(fx('vencido')));
  assert.equal(v.robots.estado, 'aviso');
  assert.match(v.robots.dato, /Latido vencido: 7 robots en sombra no dieron señal de vida a su hora/);
  const m = pasos(L.normalizarSombra(fx('manual')));
  assert.match(m.robots.dato, /No hay nada programado: los robots en sombra solo corrieron a mano/);
});

test('Resumen: la rueda lee los robots en sombra y no cambia nada más', async () => {
  const api = crearApiFalsa({ '/robots/sombra': fx('corriendo') });
  const raiz = await conReloj(() => resumen.render(crearCtx({ api, ui, ruta: 'resumen' })));
  const paso6 = buscarTodos(raiz, '.n1-paso').find((p) => p.getAttribute('data-paso') === '6');
  assert.match(paso6.textContent, /Robots en sombra corriendo \(solo lectura\)/);
  assert.equal(paso6.getAttribute('data-estado'), 'sin_datos');
  assert.equal(api.llamadas.filter((l) => l.metodo === 'POST').length, 0);
});
