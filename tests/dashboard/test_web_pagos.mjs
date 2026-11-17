// Pruebas de #/pagos (N1): lib/pagos.js (preguntas del preflight, veredicto por cuenta, saldo sin cifra, conciliación) y pages/pagos.js (DOM y API falsos).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { instalar, buscar, buscarTodos } from '../fixtures/dashboard/shell/dom_falso.mjs';
import { cargarSobre, crearApiFalsa, crearCtx, ErrorApiFalso } from '../fixtures/dashboard/shell/ctx_falso.mjs';

instalar();
const L = await import('../../dashboard/web/lib/pagos.js');
const { ui } = await import('../../dashboard/web/ui.js');
const { buscarTermino } = await import('../../dashboard/web/lib/glosario-indice.js');
const pagina = await import('../../dashboard/web/pages/pagos.js');

const fx = (n) => JSON.parse(readFileSync(fileURLToPath(new URL(`../fixtures/dashboard/finanzas/${n}`, import.meta.url)), 'utf8'));
const NBSP = '\u00a0';
const AHORA = Date.parse('2026-11-06T14:30:00Z');
async function conReloj(fn) {
  const real = Date.now; Date.now = () => AHORA;
  try { return await fn(); } finally { Date.now = real; }
}

const item = (id, estado = 'VERDE', extra = {}) => ({ id, bloque: id.startsWith('M') ? 'meta' : 'stripe', estado, critico: true, mensaje: null, evidencia_ruta: 'empresa/infra/evidencia.json', medido_en: '2026-11-06T14:00:00Z', expira_en: '2026-11-06T20:00:00Z', latencia_ms: 80, ...extra });
const TODOS = ['M-01', 'M-02', 'M-03', 'S-01', 'S-02', 'S-03', 'S-04', 'S-05', 'S-06', 'S-07', 'S-08'];
const infra = (items, extra = {}) => ({ semaforo: 'VERDE', modo: 'vivo', generado_en: '2026-11-06T14:00:00Z', valido_hasta: '2026-11-06T20:00:00Z', items, items_total: items.length, ...extra });
const sistemaDe = (inf) => ({ ...cargarSobre('sistema'), datos: { ...cargarSobre('sistema').datos, infra: inf } });
const sobreFin = (datos) => ({ datos, fuente: ['empresa/finanzas/ledger.jsonl'], generado_en: '2026-11-06T14:20:00Z', avisos: [], vacio: false });
const verde = () => TODOS.map((id) => item(id));

// ───────────────────────── lib ─────────────────────────

test('preguntas: cada ítem de Meta y Stripe en lenguaje de negocio; lo que frena un pago va primero', () => {
  assert.deepEqual(L.PREGUNTAS.map((p) => p.id), ['M-02', 'M-03', 'M-01', 'S-02', 'S-07', 'S-01', 'S-03', 'S-04', 'S-05', 'S-06', 'S-08']);
  assert.deepEqual(L.PREGUNTAS.filter((p) => p.pago).map((p) => p.id), ['M-02', 'M-03', 'S-02', 'S-07']);
  assert.ok(L.PREGUNTAS.every((p) => /^¿.*\?$/.test(p.pregunta) && p.explica.length > 20), 'preguntas de negocio, con explicación');
  for (const p of L.PREGUNTAS) assert.doesNotMatch(p.pregunta, /\.py|\.json|account_status|funding_source|charges_enabled/, p.id);
  assert.deepEqual(L.CUENTAS.map((c) => c.id), ['meta', 'stripe']);
  for (const c of L.CUENTAS) assert.ok(buscarTermino(c.glosario), c.glosario);
});

test('veredicto por cuenta: el peor tono de lo medido; sin medir no es verde; una medición caducada no es verde', () => {
  const m = (sis) => L.modeloPagos({ sistema: sis, finanzas: null, ahoraMs: AHORA });
  const meta = (mod) => mod.cuentas[0].veredicto;
  assert.deepEqual([meta(m(null)).clave, meta(m(null)).etiqueta], ['sin_medir', 'Sin medir']);
  assert.deepEqual([meta(m({ infra: infra(verde()) })).clave, meta(m({ infra: infra(verde()) })).tono], ['verde', 'ok']);
  assert.equal(meta(m({ infra: infra([item('M-02'), item('M-03', 'AMARILLO')]) })).clave, 'amarillo');
  assert.deepEqual([meta(m({ infra: infra([item('M-02', 'ROJO'), item('M-03')]) })).clave, meta(m({ infra: infra([item('M-02', 'ROJO'), item('M-03')]) })).tono], ['rojo', 'error']);
  const parcial = meta(m({ infra: infra([item('M-02')]) }));
  assert.deepEqual([parcial.clave, parcial.etiqueta], ['parcial', 'Medido en parte']);
  assert.match(parcial.frase, /tope de gasto/, 'dice qué falta medir');
  const vencida = m({ infra: infra([item('M-02', 'VERDE', { expira_en: '2026-11-06T10:00:00Z' }), item('M-03')]) });
  assert.equal(meta(vencida).etiqueta, 'Vencido');
  assert.equal(vencida.cuentas[0].preguntas[0].tono, 'aviso');
  assert.equal(vencida.cuentas[0].preguntas[0].vencido, true);
  const pend = m({ infra: infra([item('M-02', 'PENDIENTE_EXTERNO'), item('M-03')]) });
  assert.equal(meta(pend).clave, 'pendiente');
});

test('saldo de Meta: nunca disponible como cifra; solo el veredicto de M-03 y su texto breve', () => {
  const con = L.modeloPagos({ sistema: { infra: infra([item('M-03', 'AMARILLO', { mensaje: 'restante bajo el umbral' })]) }, ahoraMs: AHORA });
  assert.equal(con.saldo.disponible, false);
  assert.equal(con.saldo.veredicto.etiqueta, 'Amarillo');
  assert.equal(con.saldo.mensaje, 'restante bajo el umbral');
  const sin = L.modeloPagos({ sistema: null, ahoraMs: AHORA });
  assert.deepEqual([sin.saldo.disponible, sin.saldo.veredicto, sin.saldo.mensaje], [false, null, null]);
  assert.match(L.SIN_SALDO.produce, /vigía de pagos/);
  assert.match(L.SIN_SALDO.porque, /no guarda el número/);
  assert.equal(L.SIN_SALDO.falta.length, 3);
});

test('medición simulada o vencida: no se presenta como lectura real de las cuentas', () => {
  const sim = L.modeloPagos({ sistema: { infra: infra(verde(), { modo: 'simulado' }) }, ahoraMs: AHORA });
  assert.deepEqual([sim.simulada, sim.real, sim.modo], [true, false, 'simulado']);
  assert.match(L.atencionPagos(sim)[0].titulo, /no es de las cuentas reales/);
  const vieja = L.modeloPagos({ sistema: { infra: infra(verde(), { generado_en: '2026-11-06T05:00:00Z' }) }, ahoraMs: AHORA });
  assert.equal(vieja.real, false);
  assert.ok(L.atencionPagos(vieja).some((a) => /ya caducó/.test(a.titulo)));
  const real = L.modeloPagos({ sistema: { infra: infra(verde()) }, ahoraMs: AHORA });
  assert.equal(real.real, true);
  assert.equal(L.atencionPagos(real).length, 0, 'todo verde, vigente y sin libro: nada que atender');
});

test('atención: rojo en un ítem que frena pagos es crítico; amarillo es aviso; desconocidos entran como extras', () => {
  const m = L.modeloPagos({ sistema: { infra: infra([...verde().filter((i) => !['M-02', 'M-03', 'S-02', 'S-08'].includes(i.id)), item('M-02', 'ROJO', { mensaje: 'cuenta deshabilitada' }), item('M-03', 'AMARILLO'), item('S-02', 'ROJO'), item('S-08', 'ROJO'), item('M-99', 'ROJO')]) }, ahoraMs: AHORA });
  const a = L.atencionPagos(m);
  const tonos = Object.fromEntries(a.map((x) => [x.titulo.replace(/ → en (rojo|amarillo)/, ''), x.tono]));
  assert.equal(tonos['Cuenta publicitaria de Meta: La cuenta publicitaria está activa y sin bloqueo'], 'critico');
  assert.equal(tonos['Cobros con Stripe: Stripe puede cobrar a tus clientes y pagarte a ti'], 'critico');
  assert.equal(tonos['Cuenta publicitaria de Meta: Queda tope de gasto y la forma de pago es la permitida'], 'aviso');
  assert.equal(tonos['Cobros con Stripe: Stripe muestra bien tu negocio al cliente'], 'grave', 'rojo que no frena pagos: grave, no crítico');
  assert.equal(tonos['Cuenta publicitaria de Meta: Comprobación M-99'], 'grave');
  assert.match(a.find((x) => /activa y sin bloqueo/.test(x.titulo)).detalle, /cuenta deshabilitada/);
  assert.deepEqual(m.cuentas[0].extras.map((e) => e.id), ['M-99']);
});

test('conciliación y libro: descuadre es crítico, incompleta aviso, sin conciliación (con libro) informa; solo alertas no cuentan como libro', () => {
  const real = { infra: infra(verde()) };
  const m = (f) => L.modeloPagos({ sistema: real, finanzas: f, ahoraMs: AHORA });
  assert.deepEqual(L.atencionPagos(m(fx('finanzas_descuadre.json'))).map((a) => a.tono), ['critico']);
  assert.match(L.atencionPagos(m(fx('finanzas_descuadre.json')))[0].detalle, /Stripe 199,00.*≠ libro de movimientos 179,10/);
  assert.deepEqual(L.atencionPagos(m(fx('finanzas_incompleto.json'))).map((a) => a.tono), ['aviso']);
  assert.deepEqual(L.atencionPagos(m(fx('finanzas_sano.json'))).map((a) => a.tono), []);
  assert.deepEqual(L.atencionPagos(m({ ledger: fx('finanzas_sano.json').ledger, pnl: null, conciliacion: null, alertas: [] })).map((a) => a.tono), ['info']);
  const soloAlertas = m({ ledger: [], pnl: null, conciliacion: null, alertas: [{ id: 'a', estado: 'abierta', severidad: 'roja' }] });
  assert.equal(soloAlertas.hayLibro, false);
  assert.equal(L.atencionPagos(soloAlertas).length, 0, 'las alertas son de Avisos, no de Pagos');
  assert.equal(m(null).hayLibro, false);
});

test('cobros: por moneda, sin mezclar; un tipo sin movimientos queda en null («sin movimientos»), no en 0', () => {
  const sano = L.modeloPagos({ finanzas: fx('finanzas_sano.json'), ahoraMs: AHORA });
  assert.deepEqual(sano.cobrado, [{ moneda: 'EUR', lineas: 8, cobrado: 4059, gastado: 5810, reembolsos: 1990, disputas: null }]);
  assert.deepEqual(L.modeloPagos({ finanzas: fx('finanzas_incompleto.json'), ahoraMs: AHORA }).cobrado, []);
  assert.deepEqual(L.resumenCobros(null), []);
});

test('métricas: «—» cuando no hay dato; el saldo siempre «—» con la razón; nada inventado', () => {
  const sin = Object.fromEntries(L.metricasPagos(L.modeloPagos({ ahoraMs: AHORA }), AHORA).map((x) => [x.id, x]));
  assert.deepEqual(['meta', 'saldo', 'stripe', 'conciliacion', 'medicion'].map((k) => sin[k].valor), [null, null, null, null, null]);
  assert.match(sin.saldo.contexto, /vigía de pagos/);
  assert.match(sin.meta.contexto, /falta el chequeo antes de lanzar/);
  const m = Object.fromEntries(L.metricasPagos(L.modeloPagos({ sistema: { infra: infra(verde()) }, finanzas: fx('finanzas_sano.json'), ahoraMs: AHORA }), AHORA).map((x) => [x.id, x]));
  assert.deepEqual([m.meta.valor, m.meta.tono, m.stripe.valor, m.conciliacion.valor, m.conciliacion.tono, m.medicion.valor], ['Verde', 'ok', 'Verde', 'Cuadra', 'ok', 'hace 30 min']);
  assert.equal(m.saldo.valor, null);
  const desc = Object.fromEntries(L.metricasPagos(L.modeloPagos({ sistema: { infra: infra(verde()) }, finanzas: fx('finanzas_descuadre.json'), ahoraMs: AHORA }), AHORA).map((x) => [x.id, x]));
  assert.deepEqual([desc.conciliacion.valor, desc.conciliacion.tono], ['No cuadra', 'critico']);
});

// ───────────────────────── página ─────────────────────────

const ctxDe = (api) => crearCtx({ api, ui, ruta: 'pagos' });
const apiCon = (inf, fin = fx('finanzas_sano.json')) => crearApiFalsa({ '/sistema': sistemaDe(inf), '/finanzas': sobreFin(fin) });
const seccion = (raiz, titulo) => buscarTodos(raiz, '.seccion').find((s) => buscar(s, '.seccion__titulo').textContent === titulo);
const tarjetaDe = (raiz, id) => buscar(raiz, `[data-cuenta="${id}"]`);

test('Pagos con preflight vivo y todo verde: dos cuentas con su veredicto, preguntas de negocio, saldo sin cifra y dinero que cuadra', async () => {
  const api = apiCon(infra(verde().map((i) => (i.id === 'M-03' ? { ...i, mensaje: 'tope 1.000 · gastado 120' } : i))));
  const raiz = await conReloj(() => pagina.render(ctxDe(api)));
  assert.equal(buscar(raiz, 'h1').textContent, 'Pagos: que ninguna cuenta se frene por un pago');
  assert.match(buscar(raiz, '.atencion').textContent, /Ninguna cuenta pide atención/);
  // métricas
  const m = Object.fromEntries(buscarTodos(raiz, '.n1-metricas .metrica').map((x) => [buscar(x, '.metrica__etiqueta').textContent, x]));
  assert.deepEqual(Object.keys(m), ['Cuenta de Meta', 'Saldo de la cuenta de Meta', 'Stripe cobra y paga', 'Conciliación', 'Última medición']);
  assert.equal(buscar(m['Cuenta de Meta'], '.metrica__valor').textContent, 'Verde');
  assert.equal(buscar(m['Saldo de la cuenta de Meta'], '.metrica__valor').textContent, '—');
  assert.match(m['Saldo de la cuenta de Meta'].textContent, /sin cifra: la dará el vigía de pagos/);
  assert.equal(buscar(m['Conciliación'], '.metrica__valor').textContent, 'Cuadra');
  assert.equal(buscar(m['Última medición'], '.metrica__valor').textContent, 'hace 30 min');
  // cuentas: preguntas en lenguaje de negocio, lo que frena pagos primero
  const meta = tarjetaDe(raiz, 'meta');
  assert.deepEqual(buscarTodos(meta, '.n1-pregunta').map((p) => p.getAttribute('data-item')), ['M-02', 'M-03', 'M-01']);
  assert.match(meta.textContent, /¿La cuenta publicitaria está activa y sin bloqueo\?/);
  assert.match(meta.textContent, /El chequeo dice: tope 1\.000 · gastado 120/);
  assert.match(buscar(meta, '.n1-cuenta__cab').textContent, /Verde/);
  const stripe = tarjetaDe(raiz, 'stripe');
  assert.equal(buscarTodos(stripe, '.n1-pregunta').length, 8);
  assert.match(stripe.textContent, /¿Stripe puede cobrar a tus clientes y pagarte a ti\?/);
  // los ids y evidencias son técnicos: cerrados
  const det = buscar(meta, '.detalle-tecnico');
  assert.equal(det.hasAttribute('open'), false);
  det.open = true; det.montar();
  assert.match(det.textContent, /M-02.*VERDE/);
  // saldo: sin cifra, con qué lo producirá
  const saldo = seccion(raiz, 'El saldo de la cuenta de Meta');
  assert.match(saldo.textContent, /no está disponible como cifra/);
  assert.match(saldo.textContent, /Lo producirá el vigía de pagos/);
  assert.match(saldo.textContent, /Lo único que hay hoy .* veredicto del chequeo antes de lanzar/);
  assert.match(saldo.textContent, /«tope 1\.000 · gastado 120»/);
  assert.ok(!/\d\s*(€|US\$|USD)/.test(saldo.textContent), 'ni una cifra de saldo');
  // dinero: cobrado, gastado y reembolsos por moneda; conciliación que cuadra
  const dinero = seccion(raiz, 'El dinero que entra y sale');
  const fila = buscar(dinero, 'tbody tr');
  assert.deepEqual(buscarTodos(fila, 'td').map((c) => c.textContent), ['EUR', `40,59${NBSP}€`, `58,10${NBSP}€`, `19,90${NBSP}€`, 'sin movimientos']);
  assert.equal(buscarTodos(dinero, '.n1-tachada').length, 0);
  assert.equal(buscarTodos(dinero, '.n1-cotejo').length, 2);
  assert.match(dinero.textContent, /Stripe y Meta coinciden con el libro de movimientos/);
  // vigilancia: el vigía de pagos explicado
  assert.match(seccion(raiz, 'Cómo se vigila').textContent, /avisa al celular por dos canales y pausa/);
  assert.equal(api.llamadas.filter((l) => l.metodo === 'POST').length, 0, 'solo lectura');
  assert.equal(buscarTodos(raiz, 'input, select, textarea').length, 0);
});

test('Pagos con la conciliación descuadrada: cifra tachada con su causa y aviso crítico', async () => {
  const raiz = await conReloj(() => pagina.render(ctxDe(apiCon(infra(verde()), fx('finanzas_descuadre.json')))));
  const dinero = seccion(raiz, 'El dinero que entra y sale');
  assert.ok(buscarTodos(dinero, '.n1-tachada').length >= 1, 'lo cobrado en Stripe aparece tachado');
  assert.match(buscar(dinero, '.n1-tachada').getAttribute('title'), /Stripe 199,00.*≠ libro de movimientos 179,10/);
  assert.match(dinero.textContent, /No cuadra/);
  assert.match(buscar(raiz, '.atencion__item--critico').textContent, /Stripe o Meta no cuadran con el libro de movimientos/);
  const cuadra = buscarTodos(dinero, '.n1-cotejo').map((c) => c.getAttribute('data-cuadra'));
  assert.deepEqual(cuadra, ['no', 'si']);
});

test('Pagos con cuenta de Meta en rojo: crítico en la atención, rojo en la tarjeta y en la métrica', async () => {
  const items = verde().map((i) => (i.id === 'M-02' ? { ...i, estado: 'ROJO', mensaje: 'cuenta deshabilitada: pago fallido' } : i));
  const raiz = await conReloj(() => pagina.render(ctxDe(apiCon(infra(items, { semaforo: 'ROJO' })))));
  assert.match(buscar(raiz, '.atencion__item--critico').textContent, /La cuenta publicitaria está activa y sin bloqueo → en rojo/);
  assert.match(buscar(raiz, '.atencion__item--critico').textContent, /cuenta deshabilitada: pago fallido/);
  assert.match(buscar(tarjetaDe(raiz, 'meta'), '.n1-cuenta__cab').textContent, /Rojo/);
  const fila = buscar(tarjetaDe(raiz, 'meta'), '[data-item="M-02"]');
  assert.equal(fila.getAttribute('data-tono'), 'error');
  assert.match(fila.textContent, /Rojo/);
});

test('Pagos sin preflight: estado vacío con el comando exacto y las filas «sin medir»; sin cifras inventadas', async () => {
  const raiz = await pagina.render(ctxDe(crearApiFalsa({ '/sistema': sistemaDe(null), '/finanzas': sobreFin({ ledger: [], pnl: null, conciliacion: null, alertas: [] }) })));
  const vacio = buscar(raiz, '.vacio-pasos');
  assert.match(vacio.textContent, /Todavía no se han medido las cuentas/);
  assert.equal(buscar(vacio, '.comando__texto').textContent, L.COMANDO_PREFLIGHT);
  assert.match(buscar(raiz, '.atencion').textContent, /Falta medir las cuentas de Meta y Stripe/);
  assert.equal(buscarTodos(raiz, '.n1-pregunta').length, 11);
  assert.ok(buscarTodos(raiz, '.n1-pregunta').every((p) => /Sin medir/.test(p.textContent) && /nunca medido/.test(p.textContent)));
  const m = Object.fromEntries(buscarTodos(raiz, '.n1-metricas .metrica').map((x) => [buscar(x, '.metrica__etiqueta').textContent, buscar(x, '.metrica__valor').textContent]));
  assert.deepEqual(Object.values(m), ['—', '—', '—', '—', '—']);
  assert.match(seccion(raiz, 'El dinero que entra y sale').textContent, /Todavía no hay libro ni conciliación/);
  assert.match(seccion(raiz, 'El saldo de la cuenta de Meta').textContent, /esa comprobación no se midió/);
});

test('Pagos con medición simulada (como en el entorno de desarrollo): lo avisa y no la presenta como real', async () => {
  const raiz = await conReloj(() => pagina.render(ctxDe(apiCon(infra(verde(), { modo: 'simulado', semaforo: 'AMARILLO' })))));
  assert.match(raiz.textContent, /Medición simulada: la última revisión se hizo en modo simulado/);
  assert.match(buscar(raiz, '.atencion').textContent, /no es de las cuentas reales/);
  assert.match(tarjetaDe(raiz, 'meta').textContent, /\(medición simulada\)/);
});

test('Pagos con el preflight sin detalle por ítem (como el fixture del panel): lo dice en vez de inventar un veredicto', async () => {
  const raiz = await pagina.render(ctxDe(crearApiFalsa({ '/sistema': cargarSobre('sistema'), '/finanzas': cargarSobre('finanzas') })));
  assert.match(tarjetaDe(raiz, 'meta').textContent, /El último chequeo antes de lanzar no trae el detalle de esta cuenta/);
  assert.match(buscar(tarjetaDe(raiz, 'meta'), '.n1-cuenta__cab').textContent, /Sin medir/);
});

test('Pagos: errores de API → errorBox; si solo cae una fuente, la otra sigue', async () => {
  const caido = new ErrorApiFalso('sin_conexion', 'No se pudo conectar');
  const todo = await pagina.render(ctxDe(crearApiFalsa({ '/sistema': caido, '/finanzas': caido })));
  assert.ok(buscar(todo, '[role="alert"]'));
  const ctx = ctxDe(crearApiFalsa({ '/sistema': caido, '/finanzas': caido }));
  buscar(await pagina.render(ctx), '.error-box button').click();
  assert.deepEqual(ctx._navegaciones, ['recargar']);
  const sinFin = await pagina.render(ctxDe(crearApiFalsa({ '/sistema': sistemaDe(infra(verde())), '/finanzas': caido })));
  assert.equal(buscarTodos(sinFin, '.n1-pregunta').length, 11);
  assert.ok(buscar(seccion(sinFin, 'El dinero que entra y sale'), '[role="alert"]'));
  const sinSis = await pagina.render(ctxDe(crearApiFalsa({ '/sistema': caido, '/finanzas': sobreFin(fx('finanzas_sano.json')) })));
  assert.equal(buscarTodos(sinSis, 'tbody tr').length, 1);
});

test('Pagos: el texto del preflight es dato no confiable (se muestra como texto) y no hay jerga cruda en primer plano', async () => {
  const items = verde().map((i) => (i.id === 'M-03' ? { ...i, mensaje: '<script>alert(1)</script>‮ <img src=x onerror=alert(1)>' } : i));
  const raiz = await conReloj(() => pagina.render(ctxDe(apiCon(infra(items)))));
  assert.equal(buscarTodos(raiz, 'script').length, 0);
  assert.equal(buscarTodos(raiz, 'img').length, 0);
  assert.ok(raiz.textContent.includes('<script>alert(1)</script>'));
  assert.ok(raiz.textContent.includes('⟦U+202E⟧'));
  for (const c of buscarTodos(raiz, '.comando')) assert.ok(c.closest('details') === c, 'los comandos van en bloque cerrado');
  assert.equal(buscarTodos(raiz, '.comando[open]').length, 0);
  for (const nodo of buscarTodos(raiz, 'h1, h2, h3, h4, strong')) assert.doesNotMatch(nodo.textContent, /\.json|\.jsonl|\.yaml|empresa\/|ofertas\//, nodo.textContent);
  // los nombres técnicos del glosario (account_status…) solo asoman con el modo técnico: van dentro de .solo-tecnico
  for (const t of buscarTodos(raiz, '.termino')) { const tec = buscar(t, '.solo-tecnico'); if (tec) assert.match(tec.textContent, /^ \(.+\)$/); }
  assert.ok(buscarTodos(raiz, '.solo-tecnico').some((t) => /account_status/.test(t.textContent)));
  for (const clave of ['cuenta_publicitaria', 'cobros_stripe', 'saldo_cuenta', 'item_preflight', 'forma_de_pago', 'robot_vigia']) assert.ok(buscarTermino(clave), clave);
});

test('Pagos: meta de página', () => {
  assert.deepEqual([pagina.meta.ruta, pagina.meta.grupo, pagina.meta.titulo, pagina.meta.icono], ['pagos', 'Robots', 'Pagos', 'tarjeta']);
  assert.ok(pagina.meta.escucha.includes('empresa'));
});
