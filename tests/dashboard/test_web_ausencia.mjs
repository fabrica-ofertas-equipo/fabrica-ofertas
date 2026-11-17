// Pruebas de «¿Me puedo ausentar?» (Resumen), de las alertas con filtros y del informe de las 08:30 (Avisos):
// lib/ausencia.js (puro), lib/ausencia-vista.js (DOM falso) y las dos páginas con la API falsa. Los sobres de ejemplo salen de la API real
// (dashboard/api_alertas.py) sobre una raíz temporal: tests/fixtures/dashboard/ausencia/{alertas,informe}_{hoy,verde,amarillo}.json.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { instalar, buscar, buscarTodos } from '../fixtures/dashboard/shell/dom_falso.mjs';
import { crearApiFalsa, crearCtx, ErrorApiFalso } from '../fixtures/dashboard/shell/ctx_falso.mjs';

instalar();
const A = await import('../../dashboard/web/lib/ausencia.js');
const V = await import('../../dashboard/web/lib/ausencia-vista.js');
const LA = await import('../../dashboard/web/lib/avisos.js');
const { ui } = await import('../../dashboard/web/ui.js');
const { buscarTermino } = await import('../../dashboard/web/lib/glosario-indice.js');
const resumen = await import('../../dashboard/web/pages/resumen.js');
const avisos = await import('../../dashboard/web/pages/avisos.js');

const fx = (n) => JSON.parse(readFileSync(fileURLToPath(new URL(`../fixtures/dashboard/ausencia/${n}.json`, import.meta.url)), 'utf8'));
const AHORA = Date.parse('2026-11-07T08:35:00Z');
async function conReloj(fn) {
  const real = Date.now; Date.now = () => AHORA;
  try { return await fn(); } finally { Date.now = real; }
}
const DINERO = /\d[\d.,]*\s?(?:USD|EUR|PLN|€|\$|zł)/;
const seccion = (raiz, titulo) => buscarTodos(raiz, '.seccion').find((s) => buscar(s, '.seccion__titulo').textContent === titulo);

// ───────────────────────── lib: semáforo ─────────────────────────

test('modeloSemaforo (hoy): rojo, con lo que falta en orden, a quién le toca y los conteos del servidor', () => {
  const m = A.modeloSemaforo(fx('alertas_hoy').datos);
  assert.equal(m.nivel, 'rojo');
  assert.equal(m.titulo, 'Todavía no te puedes ausentar');
  assert.deepEqual(m.conteos, { rojo: 4, amarillo: 4, verde: 2 });
  assert.deepEqual(m.pasos.map((p) => p.id), ['limites', 'chequeo', 'canal', 'planificador', 'pausa', 'meta', 'correo', 'saldo']);
  assert.deepEqual(m.pasos.map((p) => p.paso), [1, 2, 3, 4, 5, 6, 7, 8]);
  assert.deepEqual(m.pasos.slice(0, 4).map((p) => p.nivel), ['rojo', 'rojo', 'rojo', 'rojo']);
  assert.equal(m.pasos[0].responsable, 'S-B', 'sin propuesta de límites, le toca al equipo técnico');
  assert.equal(m.pasos[2].quien.largo, 'Te toca a ti');
  assert.equal(m.paraTi, m.pasos.filter((p) => p.responsable === 'dueno').length);
  assert.deepEqual(m.listos.map((p) => p.id), ['firmas', 'vigilancia']);
  assert.ok(m.pasos.every((p) => p.enlace && p.enlace.startsWith('#/') && p.estado && p.queHacer));
  assert.equal(A.fraseCorta(m), 'Todavía no');
});

test('modeloSemaforo (verde y amarillo)', () => {
  const v = A.modeloSemaforo(fx('alertas_verde').datos);
  assert.deepEqual([v.nivel, v.faltan, v.pasos.length, v.listos.length], ['verde', 0, 0, 10]);
  assert.equal(v.titulo, 'Sí, te puedes ausentar');
  const a = A.modeloSemaforo(fx('alertas_amarillo').datos);
  assert.deepEqual([a.nivel, a.pasos.map((p) => p.id)], ['amarillo', ['firmas']]);
  assert.match(a.pasos[0].comando, /engine\.orq firmar --oferta OF-202611-91 --etapa D2/);
});

test('modeloSemaforo: tolera basura y no inventa un semáforo', () => {
  for (const x of [null, undefined, {}, { semaforo: null }, { semaforo: { nivel: 'azul' } }, 5, 'x', []]) assert.equal(A.modeloSemaforo(x), null, JSON.stringify(x));
  const m = A.modeloSemaforo({ semaforo: { nivel: 'rojo', pasos: [null, 3, { nivel: 'raro' }, { nivel: 'rojo', id: 'x', titulo: 'T', responsable: 'robot', enlace: 'javascript:alert(1)', comando: 'a\nb' }], conteos: 'x', comprobaciones: 7 } });
  assert.equal(m.pasos.length, 1);
  assert.equal(m.pasos[0].responsable, null, 'un responsable desconocido no se acepta');
  assert.equal(m.pasos[0].enlace, null, 'un enlace que no es una pantalla del panel se descarta');
  assert.equal(m.pasos[0].comando, null, 'un comando con saltos de línea se descarta');
  assert.equal(m.conteos.rojo, 1);
});

test('enlaceSeguro y comandoSeguro: solo pantallas del panel y comandos de una línea', () => {
  for (const ok of ['#/avisos', '#/quien-decide', '#/oferta/OF-202611-91', '#/resumen']) assert.equal(A.enlaceSeguro(ok), ok);
  for (const mal of ['avisos', '#/', '#/evil', '#/oferta/otra', '#/oferta/OF-1', 'javascript:alert(1)', 'http://x.com', '#/avisos?x=1', '#/../x', null, 5, '#/' + 'a'.repeat(80)]) assert.equal(A.enlaceSeguro(mal), null, String(mal));
  assert.equal(A.comandoSeguro('.venv/bin/python -m x'), '.venv/bin/python -m x');
  for (const mal of ['', 'a\nb', 'a‮b', 'x'.repeat(401), null, 5]) assert.equal(A.comandoSeguro(mal), null);
  assert.equal(A.nombrePantalla('#/sistema'), 'Salud del sistema');
  assert.equal(A.nombrePantalla('#/oferta/OF-202611-91'), 'la oferta');
  assert.equal(A.nombrePantalla('#/evil'), null);
  assert.equal(A.responsableDe('dueno').corto, 'Tú');
  for (const x of ['__proto__', 'constructor', 'ia', null]) assert.equal(A.responsableDe(x), null);
});

test('canalDesdeSemaforo: elegido solo si el semáforo lo da por verde', () => {
  assert.equal(A.canalDesdeSemaforo(null), null);
  assert.deepEqual(A.canalDesdeSemaforo(A.modeloSemaforo(fx('alertas_verde').datos)), { elegido: true, tono: 'ok', texto: 'Elegido', titulo: 'Dos canales, probados' });
  const hoy = A.canalDesdeSemaforo(A.modeloSemaforo(fx('alertas_hoy').datos));
  assert.deepEqual([hoy.elegido, hoy.texto], [false, 'Sin elegir']);
});

// ───────────────────────── lib: alertas ─────────────────────────

test('modeloAlertasCalculadas: filas del esquema + extras por id; filtros por gravedad y por a quién le toca', () => {
  const calc = A.modeloAlertasCalculadas(fx('alertas_hoy').datos);
  assert.equal(calc.crudas.length, 8);
  assert.equal(calc.resumen.abiertas, 8);
  assert.deepEqual([calc.resumen.rojas, calc.resumen.amarillas], [3, 5]);
  assert.equal(calc.extras['F2-AUS-CANAL:empresa'].responsable, 'dueno');
  assert.equal(calc.extras['F2-AUS-LIM:empresa'].responsable, 'S-B');
  assert.equal(calc.archivo.existe, false);
  assert.match(calc.archivo.comandoEscribir, /scripts\.alertas\.producir --escribir/);
  assert.equal(calc.pendientes.length, 15);
  assert.equal(calc.semaforo.nivel, 'rojo');
  const modelo = LA.modeloAlertas({ alertas: calc.crudas });
  const filas = A.enriquecerAlertas(modelo.abiertas, calc.extras);
  assert.equal(filas.length, 8);
  const canal = filas.find((a) => a.id === 'F2-AUS-CANAL:empresa');
  assert.equal(canal.medida, '0 de 2 canales elegidos');
  assert.equal(canal.calculada, true);
  assert.equal(canal.titulo, 'Los avisos al celular no tienen dos canales', 'el título específico gana al nombre genérico de la regla');
  assert.equal(canal.clave, 'roja');
  const cuentas = A.contarPorGravedad(filas);
  assert.deepEqual(cuentas, { todas: 8, graves: 3, amarilla: 5, info: 0 });
  assert.equal(A.filtrarAlertas(filas, { gravedad: 'graves' }).length, 3);
  assert.equal(A.filtrarAlertas(filas, { gravedad: 'amarilla' }).length, 5);
  assert.equal(A.filtrarAlertas(filas, { gravedad: 'info' }).length, 0);
  const mias = A.filtrarAlertas(filas, { quien: 'mias' });
  const equipo = A.filtrarAlertas(filas, { quien: 'equipo' });
  assert.equal(mias.length + equipo.length, 8);
  assert.ok(equipo.every((a) => a.responsable && a.responsable !== 'dueno'));
  assert.equal(A.filtrarAlertas(filas, { gravedad: 'graves', quien: 'mias' }).every((a) => a.clave === 'roja' && a.responsable === 'dueno'), true);
  assert.equal(A.filtrarAlertas(filas, { gravedad: 'rara', quien: 'rara' }).length, 8, 'filtro desconocido = todas');
  assert.deepEqual(A.filtrarAlertas(null), []);
});

test('modeloAlertasCalculadas: sin datos devuelve null; las reglas nuevas tienen nombre en lenguaje simple', () => {
  for (const x of [null, {}, { alertas: 'x' }, 7]) assert.equal(A.modeloAlertasCalculadas(x), null);
  assert.equal(LA.nombreRegla('F2-AUS-CANAL'), 'Avisos al celular sin dos canales');
  assert.equal(LA.nombreRegla('F2-A17'), 'El panel no recibe señales de vida: datos sin actualizar', 'las de docs/04 siguen igual');
  assert.equal(LA.nombreRegla('F2-AUS-NO-EXISTE'), null);
  assert.equal(Object.keys(LA.NOMBRE_REGLA).length, 25);
});

test('estadoArchivoAlertas: sin guardar, al día, desactualizado o ilegible', () => {
  assert.equal(A.estadoArchivoAlertas({ existe: false }).texto, 'Sin guardar');
  assert.equal(A.estadoArchivoAlertas({ existe: true, alDia: true }).texto, 'Al día');
  assert.equal(A.estadoArchivoAlertas({ existe: true, alDia: false }).texto, 'Desactualizado');
  assert.equal(A.estadoArchivoAlertas({ existe: true, ilegible: true }).tono, 'error');
  assert.equal(A.estadoArchivoAlertas(null).texto, 'Sin guardar');
});

// ───────────────────────── lib: informe ─────────────────────────

test('modeloInforme: dos versiones, 5 avisos, ceros, lo que te toca; el celular sin dinero', () => {
  const m = A.modeloInforme(fx('informe_hoy').datos);
  assert.equal(m.hora, '08:30');
  assert.deepEqual(m.avisos.map((a) => a.id), ['pagos', 'importante', 'cansancio', 'mercado_nuevo', 'no_aprobado']);
  assert.equal(m.ceros.length, 5);
  assert.deepEqual(m.ceros.find((c) => c.id === 'pagos_sin_aviso').info.texto, 'Sin medir');
  assert.equal(m.ceros.find((c) => c.id === 'esperando_por_ti').valor, 0);
  assert.equal(m.ceros.find((c) => c.id === 'pagos_sin_aviso').valor, null, 'sin medir no es un 0');
  assert.match(m.versiones.correo.asunto, /^\[ROJO\] Informe del día/);
  assert.ok(m.versiones.correo.texto.includes('5. LO QUE TODAVÍA NO SE PUDO MEDIR'));
  assert.equal(DINERO.test(m.versiones.celular.texto), false);
  assert.ok(m.teToca.length > 0);
  assert.ok(m.sinDatos.length > 0);
  assert.equal(m.ventasGasto.hayDatos, false);
  for (const x of [null, {}, { tipo: 'otro', versiones: {} }, { tipo: 'informe_diario' }, { tipo: 'informe_diario', versiones: { correo: {} } }]) assert.equal(A.modeloInforme(x), null);
});

// ───────────────────────── vista del semáforo ─────────────────────────

test('bloqueSemaforo (hoy): la luz encendida es la roja, con palabra e icono; los pasos en orden con su responsable, enlace y comando', () => {
  V.instalar();
  const sec = V.bloqueSemaforo(A.modeloSemaforo(fx('alertas_hoy').datos), { ahoraMs: AHORA });
  assert.equal(buscar(sec, '.seccion__titulo').textContent, '¿Me puedo ausentar?');
  const bloque = buscar(sec, '.au-bloque');
  assert.equal(bloque.getAttribute('data-nivel'), 'rojo');
  const luces = buscarTodos(sec, '.au-luz');
  assert.deepEqual(luces.map((l) => l.getAttribute('data-encendida')), ['1', '0', '0']);
  assert.match(buscar(sec, '.au-luces').getAttribute('aria-label'), /rojo/);
  assert.equal(buscar(sec, '.au-veredicto').textContent, 'Todavía no te puedes ausentar');
  const pasos = buscarTodos(sec, '.au-paso');
  assert.equal(pasos.length, 8);
  assert.deepEqual(pasos.map((p) => p.getAttribute('data-paso')), ['limites', 'chequeo', 'canal', 'planificador', 'pausa', 'meta', 'correo', 'saldo']);
  assert.match(pasos[0].textContent, /Rojo/);
  assert.match(pasos[0].textContent, /Equipo técnico \(S-B\)/);
  assert.match(pasos[2].textContent, /Tú/);
  assert.match(pasos[2].textContent, /Qué hacer: Elige un canal/);
  assert.equal(buscarTodos(pasos[2], 'a')[0].getAttribute('href'), '#/avisos');
  assert.match(buscarTodos(pasos[2], 'a')[0].textContent, /Ir a Avisos/);
  assert.match(buscar(pasos[1], '.comando__texto').textContent, /infra\.preflight ejecutar --modo completo/);
  assert.match(sec.textContent, /Lo que ya está en orden \(2\)/);
  assert.match(sec.textContent, /Se calcula leyendo los archivos del proyecto/);
  const conNota = V.bloqueSemaforo(A.modeloSemaforo({ semaforo: { nivel: 'verde', comprobaciones: [{ nivel: 'verde', id: 'firmas', titulo: 'Firmas que esperan por ti', estado: 'Ninguna firma espera por ti.', responsable: 'dueno', nota: '1 oferta hecha a mano no tiene registro de avance' }] } }), { ahoraMs: AHORA });
  assert.match(conNota.textContent, /Ojo: 1 oferta hecha a mano no tiene registro de avance/, 'lo verde también avisa lo que el semáforo no puede ver');
  assert.equal(buscarTodos(sec, 'input, select, textarea').length, 0);
  assert.ok(buscarTermino('semaforo_ausencia') && buscarTermino('a_quien_le_toca') && buscarTermino('los_ceros') && buscarTermino('informe_diario') && buscarTermino('archivo_alertas'));
});

test('bloqueSemaforo (verde): luz verde y ningún paso pendiente', () => {
  const sec = V.bloqueSemaforo(A.modeloSemaforo(fx('alertas_verde').datos), { ahoraMs: AHORA });
  assert.deepEqual(buscarTodos(sec, '.au-luz').map((l) => l.getAttribute('data-encendida')), ['0', '0', '1']);
  assert.equal(buscarTodos(sec, '.au-paso').length, 0);
  assert.match(sec.textContent, /No falta nada/);
  assert.match(sec.textContent, /Lo que ya está en orden \(10\)/);
});

test('bloqueSemaforo: el texto hostil se muestra como texto (sin nodos <script> ni <img>) y nada ejecuta acciones', () => {
  const hostil = '<img src=x onerror=alert(1)><script>alert(2)</script>';
  const m = A.modeloSemaforo({ semaforo: { nivel: 'amarillo', titulo: hostil, resumen: hostil, pasos: [{ nivel: 'amarillo', id: 'x', titulo: hostil, estado: hostil, que_hacer: hostil, responsable: 'dueno', enlace: '#/avisos', enlace_texto: hostil }] } });
  const sec = V.bloqueSemaforo(m, { ahoraMs: AHORA });
  assert.equal(buscarTodos(sec, 'script').length, 0);
  assert.equal(buscarTodos(sec, 'img').length, 0);
  assert.ok(sec.textContent.includes('<script>alert(2)</script>'));
  assert.equal(buscarTodos(sec, 'button').filter((b) => !b.classList.contains('comando__copiar') && !b.classList.contains('ayuda-btn')).length, 0, 'ningún botón de acción: solo enlaces, ayudas y copiar comandos');
});

// ───────────────────────── Resumen ─────────────────────────

const ctxResumen = (api) => crearCtx({ api, ui, ruta: 'resumen' });

test('Resumen: «¿Me puedo ausentar?» va primero, antes de «Requiere tu atención», con el semáforo de hoy', async () => {
  const api = crearApiFalsa({ '/alertas': fx('alertas_hoy') });
  const raiz = await conReloj(() => resumen.render(ctxResumen(api)));
  const titulos = buscarTodos(raiz, '.seccion__titulo, .atencion__titulo').map((t) => t.textContent);
  assert.equal(titulos[0], '¿Me puedo ausentar?');
  assert.ok(titulos.indexOf('Requiere tu atención') > 0);
  assert.ok(titulos.indexOf('La rueda: los 9 pasos de cada día') > titulos.indexOf('Requiere tu atención'));
  const sec = seccion(raiz, '¿Me puedo ausentar?');
  assert.equal(buscar(sec, '.au-bloque').getAttribute('data-nivel'), 'rojo');
  assert.equal(buscarTodos(sec, '.au-paso').length, 8);
  assert.deepEqual(api.llamadas.filter((l) => l.ruta === '/alertas').length, 1);
  assert.equal(api.llamadas.filter((l) => l.metodo === 'POST').length, 0, 'solo lectura');
});

test('Resumen con todo en orden: semáforo verde', async () => {
  const raiz = await conReloj(() => resumen.render(ctxResumen(crearApiFalsa({ '/alertas': fx('alertas_verde') }))));
  const sec = seccion(raiz, '¿Me puedo ausentar?');
  assert.equal(buscar(sec, '.au-bloque').getAttribute('data-nivel'), 'verde');
  assert.equal(buscar(sec, '.au-veredicto').textContent, 'Sí, te puedes ausentar');
});

test('Resumen: si el cálculo falla no se inventa un semáforo y el resto de la pantalla sigue', async () => {
  const api = crearApiFalsa({ '/alertas': new ErrorApiFalso('error_interno', 'No se pudo calcular') });
  const raiz = await conReloj(() => resumen.render(ctxResumen(api)));
  const sec = seccion(raiz, '¿Me puedo ausentar?');
  assert.equal(buscarTodos(sec, '.au-bloque').length, 0);
  assert.ok(buscar(sec, '.caja-error, [role="alert"]') || /No se pudo calcular/.test(sec.textContent));
  assert.ok(seccion(raiz, 'La rueda: los 9 pasos de cada día'), 'la rueda sigue');
});

// ───────────────────────── Avisos ─────────────────────────

const ctxAvisos = (api) => crearCtx({ api, ui, ruta: 'avisos' });

test('Avisos con las alertas calculadas: filtros por gravedad y por a quién le toca, a quién le toca cada una, enlace y comando', async () => {
  const api = crearApiFalsa({ '/alertas': fx('alertas_hoy'), '/informe': fx('informe_hoy') });
  const raiz = await conReloj(() => avisos.render(ctxAvisos(api)));
  const sec = seccion(raiz, 'Alertas abiertas');
  assert.equal(buscarTodos(sec, '.n1-alerta').length, 8);
  assert.match(sec.textContent, /Archivo de alertas guardado.*: sin guardar\./);
  assert.match(sec.textContent, /scripts\.alertas\.producir --escribir/);
  assert.match(sec.textContent, /Reglas que todavía no se calculan \(15\)/);
  const filtros = buscar(sec, '.au-filtros');
  const botones = buscarTodos(filtros, '[role="radio"]');
  const por = (txt) => botones.find((b) => b.getAttribute('aria-label').startsWith(txt));
  assert.equal(buscar(sec, '.au-conteo').textContent, '8 alertas abiertas');
  por('Rojas y naranjas').click();
  assert.equal(buscarTodos(sec, '.n1-alerta').length, 3);
  assert.equal(buscar(sec, '.au-conteo').textContent, 'Se muestran 3 de 8 alertas abiertas');
  assert.ok(buscarTodos(sec, '.n1-alerta').every((a) => a.getAttribute('data-severidad') === 'roja'));
  por('Me tocan a mí').click();
  assert.ok(buscarTodos(sec, '.n1-alerta').length < 3);
  por('De todos').click();
  por('Todas').click();
  por('Información').click();
  assert.match(buscar(sec, '[data-lista="abiertas"]').textContent, /Ninguna alerta abierta con ese filtro/);
  por('Todas').click();
  assert.equal(buscarTodos(sec, '.n1-alerta').length, 8);
  const canal = buscarTodos(sec, '.n1-alerta').find((a) => /dos canales/.test(a.textContent));
  assert.match(canal.textContent, /Te toca a ti/);
  assert.match(canal.textContent, /Medida: 0 de 2 canales elegidos/);
  assert.doesNotMatch(canal.textContent, /Valor actual|sin límite fijado/, 'las calculadas no muestran el «1 contra 0» del esquema');
  assert.equal(buscarTodos(canal, 'a').some((x) => x.getAttribute('href') === '#/avisos' && x.textContent === 'Ir a Avisos'), true);
  assert.equal(api.llamadas.filter((l) => l.metodo === 'POST').length, 0);
});

test('Avisos: sin /alertas usa las guardadas (Finanzas), sin filtros y sin romperse', async () => {
  const api = crearApiFalsa({ '/alertas': new ErrorApiFalso('x', 'no'), '/informe': new ErrorApiFalso('x', 'no') });
  const raiz = await conReloj(() => avisos.render(ctxAvisos(api)));
  assert.equal(buscarTodos(raiz, '.au-filtros').length, 0);
  assert.match(seccion(raiz, 'El resumen diario').textContent, /Todavía no hay resumen diario/);
});

test('Avisos: el informe de las 08:30 con sus dos versiones; el celular no tiene dinero y todo es texto', async () => {
  const api = crearApiFalsa({ '/alertas': fx('alertas_hoy'), '/informe': fx('informe_hoy') });
  const raiz = await conReloj(() => avisos.render(ctxAvisos(api)));
  const sec = seccion(raiz, 'El resumen diario');
  assert.ok(buscar(sec, '.au-informe'));
  assert.match(sec.textContent, /Todavía no se envía nada/);
  const pre = buscar(sec, '.au-texto');
  assert.match(pre.textContent, /^INFORME DEL DÍA — 07\/11\/2026 · 08:30/);
  assert.match(sec.textContent, /Asunto: \[ROJO\] Informe del día/);
  const pestanas = buscarTodos(sec, '[role="tab"]');
  assert.deepEqual(pestanas.map((p) => p.textContent), ['Versión para el correo', 'Versión para el celular']);
  pestanas[1].click();
  assert.match(pre.textContent, /^INFORME 07\/11 08:30/);
  assert.equal(DINERO.test(pre.textContent), false);
  assert.match(sec.textContent, /ninguna cifra de dinero/);
  pestanas[0].click();
  assert.match(pre.textContent, /1\. VENTAS Y GASTO/);
  assert.equal(buscarTodos(sec, '[data-aviso]').length, 5);
  assert.equal(buscarTodos(sec, '[data-cero]').length, 5);
  assert.match(sec.textContent, /Lo que te toca a ti \(/);
  assert.match(buscar(sec, '[data-cero="pagos_sin_aviso"]').textContent, /Sin medir/);
  assert.equal(buscar(sec, '[data-cero="pagos_sin_aviso"] .au-cero__valor').textContent, '—', 'sin medir se ve «—», nunca 0');
  assert.equal(buscar(sec, '[data-cero="esperando_por_ti"] .au-cero__valor').textContent, '0');
  const m = Object.fromEntries(buscarTodos(raiz, '.n1-metricas .metrica').map((x) => [buscar(x, '.metrica__etiqueta').textContent, x]));
  assert.equal(buscar(m['Resumen diario'], '.metrica__valor').textContent, 'Compuesto');
  assert.equal(buscar(m['Canal al celular'], '.metrica__valor').textContent, 'Sin elegir');
  assert.equal(buscarTodos(sec, 'script, img').length, 0);
});

test('Avisos con todo en orden: canal «Elegido» y sin alertas abiertas calculables', async () => {
  const api = crearApiFalsa({ '/alertas': fx('alertas_verde'), '/informe': fx('informe_verde') });
  const raiz = await conReloj(() => avisos.render(ctxAvisos(api)));
  const m = Object.fromEntries(buscarTodos(raiz, '.n1-metricas .metrica').map((x) => [buscar(x, '.metrica__etiqueta').textContent, x]));
  assert.equal(buscar(m['Canal al celular'], '.metrica__valor').textContent, 'Elegido');
  assert.match(seccion(raiz, 'Alertas abiertas').textContent, /un cero acá no prueba que todo esté bien/);
});

test('Avisos: el texto hostil de una alerta ajena se muestra como texto', async () => {
  const hostil = '<img src=x onerror=alert(1)>';
  const datos = fx('alertas_hoy');
  datos.datos.alertas.push({ schema_version: '1.0.0', id: 'F1-A09:x', ts: '2026-11-07T08:00:00Z', severidad: 'roja', regla_id: 'F1-A09', origen: 'F1', oferta_id: null, macro_nicho: null, nivel: null,
    valor: null, umbral: null, accion_sugerida: hostil, estado: 'abierta', titulo: hostil, responsable: null, enlace: 'javascript:alert(1)', comando: 'a\nb', detalle: hostil, fuente: 'archivo' });
  const raiz = await conReloj(() => avisos.render(ctxAvisos(crearApiFalsa({ '/alertas': datos, '/informe': fx('informe_hoy') }))));
  assert.equal(buscarTodos(raiz, 'img').length, 0);
  assert.ok(raiz.textContent.includes(hostil));
  assert.equal(buscarTodos(raiz, 'a').some((a) => String(a.getAttribute('href')).startsWith('javascript')), false);
});
