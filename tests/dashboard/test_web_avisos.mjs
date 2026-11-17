// Pruebas de #/avisos (N1): lib/avisos.js (severidad, reglas en lenguaje de negocio, canal, avisadores) y pages/avisos.js (DOM y API falsos).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { instalar, buscar, buscarTodos } from '../fixtures/dashboard/shell/dom_falso.mjs';
import { cargarSobre, crearApiFalsa, crearCtx, ErrorApiFalso } from '../fixtures/dashboard/shell/ctx_falso.mjs';

instalar();
const L = await import('../../dashboard/web/lib/avisos.js');
const { ui } = await import('../../dashboard/web/ui.js');
const { buscarTermino } = await import('../../dashboard/web/lib/glosario-indice.js');
const pagina = await import('../../dashboard/web/pages/avisos.js');

const fx = (n) => JSON.parse(readFileSync(fileURLToPath(new URL(`../fixtures/dashboard/finanzas/${n}`, import.meta.url)), 'utf8'));
const AHORA = Date.parse('2026-11-14T10:00:00Z');
const sobreFin = (datos, extra = {}) => ({ datos, fuente: ['empresa/finanzas/ledger.jsonl', 'empresa/finanzas/pnl.json', 'empresa/finanzas/conciliacion.json', 'empresa/datos/alertas.jsonl'], generado_en: '2026-11-14T09:59:00Z', avisos: [], vacio: false, ...extra });
const alerta = (extra) => ({ schema_version: '1.0.0', id: 'A1', ts: '2026-11-14T08:00:00Z', severidad: 'amarilla', regla_id: 'F2-A09', origen: 'F2', oferta_id: 'OF-202611-02', macro_nicho: null, nivel: null, valor: '82', umbral: '80', accion_sugerida: 'Revisar el gasto', estado: 'abierta', ...extra });
async function conReloj(fn) {
  const real = Date.now; Date.now = () => AHORA;
  try { return await fn(); } finally { Date.now = real; }
}

// ───────────────────────── lib ─────────────────────────

test('severidades: cuatro niveles, cada uno con forma (icono), color (tono) y destino propuesto; naranja usa el tono «grave» de Finanzas', () => {
  assert.deepEqual(L.SEVERIDADES.map((s) => s.clave), ['roja', 'naranja', 'amarilla', 'info']);
  assert.deepEqual(L.SEVERIDADES.map((s) => s.tono), ['error', 'grave', 'aviso', 'info']);
  assert.equal(new Set(L.SEVERIDADES.map((s) => s.icono)).size, 4, 'cada gravedad tiene un icono distinto: el color no va solo');
  assert.ok(L.SEVERIDADES.every((s) => s.significa && s.donde));
  assert.match(L.SEVERIDADES[0].donde, /sin silencio nocturno/);
  assert.match(L.SEVERIDADES[3].donde, /Solo el panel/);
});

test('reglas en lenguaje de negocio: las 8 de F1 y las 17 de F2; las desconocidas devuelven null (se muestra su código)', () => {
  assert.equal(Object.keys(L.NOMBRE_REGLA).length, 25);
  assert.equal(L.nombreRegla('F1-A02'), 'Demasiadas disputas (la oferta debería pausarse)');
  assert.equal(L.nombreRegla('F2-A17'), 'El panel no recibe señales de vida: datos sin actualizar');
  for (const x of ['F9-A99', '', null, undefined, '__proto__', 'constructor']) assert.equal(L.nombreRegla(x), null, String(x));
});

test('modeloAlertas: abiertas (y reconocidas) por gravedad primero, cerradas aparte, conteo por nivel', () => {
  const m = L.modeloAlertas({ alertas: fx('finanzas_alertas.json').alertas });
  assert.equal(m.hay, true);
  assert.equal(m.total, 4);
  assert.deepEqual(m.abiertas.map((a) => a.clave), ['roja', 'naranja', 'amarilla'], 'la roja (reconocida, sigue viva) va antes que la naranja');
  assert.deepEqual(m.abiertas.map((a) => a.estadoInfo.clave), ['reconocida', 'abierta', 'abierta']);
  assert.deepEqual(m.cerradas.map((a) => a.regla_id), ['F2-A03']);
  assert.deepEqual(m.conteo, { roja: 1, naranja: 1, amarilla: 1, info: 0, otra: 0 });
  assert.equal(m.abiertas[1].titulo, 'Demasiadas disputas (la oferta debería pausarse)');
  assert.equal(m.abiertas[1].tono, 'grave');
  assert.equal(m.abiertas[2].sinUmbral, true, 'límite null = «sin límite fijado»');
  assert.equal(L.fraseValor(m.abiertas[2]), 'Valor actual 4 · sin límite fijado');
  assert.match(L.fraseValor(m.abiertas[1]), /^Valor actual .* · límite .*/);
  assert.equal(L.fraseValor({ valor: null }), null);
  // sin archivo o con basura: ni lanza ni inventa
  for (const x of [null, undefined, {}, { alertas: 5 }, { alertas: [null, 3, 'x'] }]) {
    const v = L.modeloAlertas(x);
    assert.deepEqual([v.hay, v.abiertas.length], [Array.isArray(x && x.alertas) && x.alertas.length > 0, 0], JSON.stringify(x));
  }
  assert.equal(L.modeloAlertas({ alertas: [{ id: 'x', severidad: 'inventada', estado: 'abierta' }] }).abiertas[0].clave, 'otra');
  assert.equal(L.modeloAlertas({ alertas: [{ id: 'sin-regla', severidad: 'roja', estado: 'abierta' }] }).abiertas[0].titulo, 'Alerta sin regla');
});

test('canal al celular: hoy sin elegir (decisión pendiente del dueño); con un canal configurado pasa a «Elegido»', () => {
  const c = L.estadoCanal();
  assert.deepEqual([c.elegido, c.tono, c.texto], [false, 'aviso', 'Sin elegir']);
  assert.equal(L.estadoCanal({}).elegido, false);
  assert.deepEqual([L.estadoCanal({ canal: 'Telegram' }).elegido, L.estadoCanal({ canal: 'Telegram' }).titulo], [true, 'Telegram']);
  assert.deepEqual(L.EXPLICACION_CANAL.map((e) => e.id), ['dos', 'plantilla', 'importes', 'estado']);
  assert.match(L.EXPLICACION_CANAL[0].texto, /Telegram solo de salida/);
  assert.match(L.PLANTILLA.muestra, /<gravedad>/);
  assert.ok(L.PLANTILLA.prohibido.some((p) => /texto libre/i.test(p)));
  assert.match(L.DECISION_PENDIENTE.siguiente, /dos canales/);
  for (const e of L.EXPLICACION_CANAL) if (e.ayuda) assert.ok(buscarTermino(e.ayuda), `glosario: ${e.ayuda}`);
});

test('qué avisa cada robot: vigía, alarma, informe y watchdog, con el estado de su código comprobado', () => {
  const a = Object.fromEntries(L.avisadores({ motor_disponible: true }).map((x) => [x.id, x]));
  assert.deepEqual(Object.keys(a), ['vigia', 'alarma', 'informe', 'watchdog']);
  assert.equal(a.vigia.estado.clave, 'parcial');
  assert.equal(a.alarma.estado.clave, 'no_construido');
  assert.equal(a.informe.estado.clave, 'no_construido');
  assert.equal(a.watchdog.estado.clave, 'parcial');
  assert.match(a.watchdog.detalle, /direcciones reales/);
  assert.deepEqual([a.vigia.sev.clave, a.alarma.sev.clave, a.informe.sev.clave], ['roja', 'amarilla', 'info']);
  assert.match(a.alarma.cuando, /08:05/);
  assert.match(a.informe.cuando, /08:30/);
});

test('atención y métricas: roja → crítico, naranja → grave, amarilla → aviso, y el canal sin elegir como decisión pendiente', () => {
  const m = L.modeloAlertas({ alertas: fx('finanzas_alertas.json').alertas });
  const a = L.atencionAvisos(m);
  assert.deepEqual(a.map((i) => i.tono), ['critico', 'grave', 'aviso', 'aviso']);
  assert.match(a[0].titulo, /1 alerta roja abierta/);
  assert.match(a[1].titulo, /1 alerta naranja abierta: una oferta debería pausarse/);
  assert.match(a[3].titulo, /Elegir el canal de avisos al celular/);
  assert.equal(L.atencionAvisos(L.modeloAlertas(null), L.estadoCanal({ canal: 'x' })).length, 0, 'sin alertas y con canal: nada que atender');
  const met = Object.fromEntries(L.metricasAvisos(m).map((x) => [x.id, x]));
  assert.deepEqual([met.abiertas.valor, met.abiertas.tono, met.graves.valor, met.canal.valor, met.resumen.valor], [3, 'critico', 2, 'Sin elegir', 'No existe']);
  const sin = Object.fromEntries(L.metricasAvisos(L.modeloAlertas(null), L.estadoCanal(), true).map((x) => [x.id, x]));
  assert.equal(sin.abiertas.valor, 0);
  assert.match(sin.abiertas.contexto, /un cero no prueba que todo esté bien/);
  const caido = Object.fromEntries(L.metricasAvisos(null, L.estadoCanal(), false).map((x) => [x.id, x]));
  assert.equal(caido.abiertas.valor, null, 'API caída: «—», no 0');
  assert.equal(caido.graves.valor, null);
});

test('horaAlerta: relativa con la absoluta aparte; sin fecha, «—»', () => {
  assert.equal(L.horaAlerta({ ts: '2026-11-14T08:00:00Z' }, AHORA).relativa, 'hace 2 h');
  assert.deepEqual(L.horaAlerta({}, AHORA), { relativa: '—', absoluta: '—' });
});

// ───────────────────────── página ─────────────────────────

const ctxDe = (api) => crearCtx({ api, ui, ruta: 'avisos' });
const apiCon = (datos, extra = {}) => crearApiFalsa({ '/finanzas': sobreFin(datos), ...extra });
const seccion = (raiz, titulo) => buscarTodos(raiz, '.seccion').find((s) => buscar(s, '.seccion__titulo').textContent === titulo);

test('Avisos con alertas: abiertas con su gravedad, qué hacer y desde cuándo; cerradas aparte; el canal y el resumen, sin inventar', async () => {
  const api = apiCon(fx('finanzas_alertas.json'));
  const raiz = await conReloj(() => pagina.render(ctxDe(api)));
  assert.equal(buscar(raiz, 'h1').textContent, 'Avisos: lo que te llega al celular y por qué');
  // orden: atención → métricas → alertas → gravedad → canal → resumen → robots
  const orden = ['Requiere tu atención', 'Alertas abiertas', 'Cómo te avisarían según la gravedad', 'El canal al celular', 'El resumen diario', 'Qué avisa cada robot'].map((t) => raiz.textContent.indexOf(t));
  assert.ok(orden.every((n) => n >= 0), `faltan bloques: ${orden}`);
  assert.deepEqual(orden, [...orden].sort((a, b) => a - b));
  // atención: 4 avisos de más a menos graves
  const at = buscarTodos(raiz, '.atencion__item');
  assert.equal(at.length, 4);
  assert.match(at[0].className, /atencion__item--critico/);
  assert.match(at[1].className, /atencion__item--grave/);
  assert.match(at[3].textContent, /Elegir el canal de avisos al celular/);
  // alertas abiertas
  const abiertas = buscarTodos(seccion(raiz, 'Alertas abiertas'), '.n1-alerta[data-severidad]').filter((a) => a.closest('ul').getAttribute('aria-label') === 'Alertas abiertas');
  assert.deepEqual(abiertas.map((a) => a.getAttribute('data-severidad')), ['roja', 'naranja', 'amarilla']);
  assert.equal(abiertas[1].getAttribute('data-tono'), 'grave', 'naranja reutiliza el tono de Finanzas');
  assert.match(abiertas[1].textContent, /Naranja · pausa/);
  assert.match(abiertas[1].textContent, /Demasiadas disputas/);
  assert.match(abiertas[1].textContent, /Pausar la oferta OF-202611-01 y revisar la pérdida del test/);
  assert.match(abiertas[0].textContent, /Reconocida/);
  assert.match(abiertas[2].textContent, /sin límite fijado/);
  assert.match(abiertas[2].textContent, /Toda la empresa/);
  assert.match(abiertas[1].textContent, /hace 2 h/, 'lleva su hora');
  // cada gravedad tiene un icono propio dentro del chip (el color no va solo)
  const iconos = abiertas.map((a) => buscar(a, '.chip').textContent);
  assert.ok(iconos.every((t) => t.length > 0));
  // cerradas
  const cerradas = buscarTodos(seccion(raiz, 'Alertas abiertas'), 'ul').find((u) => u.getAttribute('aria-label') === 'Alertas cerradas');
  assert.equal(buscarTodos(cerradas, 'li.n1-alerta').length, 1);
  assert.equal(buscarTodos(cerradas, 'li.n1-alerta')[0].getAttribute('data-tono'), 'neutro', 'una cerrada no se pinta de color de alerta');
  // el detalle técnico queda cerrado
  const det = buscar(abiertas[1], '.detalle-tecnico');
  assert.equal(det.hasAttribute('open'), false);
  det.open = true; det.montar();
  assert.match(det.textContent, /F1-A02/);
  assert.match(det.textContent, /naranja/);
  // gravedad → destino
  const filas = buscarTodos(seccion(raiz, 'Cómo te avisarían según la gravedad'), 'tbody tr');
  assert.equal(filas.length, 4);
  assert.match(seccion(raiz, 'Cómo te avisarían según la gravedad').textContent, /Propuesta sin decidir/);
  // canal sin elegir, dos canales, plantilla fija
  const canal = seccion(raiz, 'El canal al celular');
  assert.match(canal.textContent, /Sin elegir/);
  assert.match(canal.textContent, /Siempre dos canales/);
  assert.match(canal.textContent, /Forma fija, sin texto libre/);
  assert.match(buscar(canal, '.n1-muestra').textContent, /<gravedad> · <código de la regla> · <oferta> · <hora>/);
  assert.match(canal.textContent, /la forma, no un aviso real/);
  // resumen diario: no existe, con pasos
  const res = seccion(raiz, 'El resumen diario');
  assert.match(res.textContent, /Todavía no hay resumen diario/);
  assert.match(res.textContent, /08:30/);
  assert.match(res.textContent, /Programar el informe para que se componga y se envíe cada día/);
  // qué avisa cada robot
  const robots = buscarTodos(raiz, '.n1-avisador');
  assert.deepEqual(robots.map((r) => r.getAttribute('data-aviso')), ['vigia', 'alarma', 'informe', 'watchdog']);
  assert.match(robots[0].textContent, /Vigía de pagos/);
  assert.match(robots[1].textContent, /No construido/);
  assert.equal(api.llamadas.filter((l) => l.metodo === 'POST').length, 0, 'solo lectura');
  assert.equal(buscarTodos(raiz, 'input, select, textarea').length, 0);
});

test('Avisos sin archivo de alertas: estado vacío honesto (un cero no prueba que todo esté bien) y nada de cifras inventadas', async () => {
  const raiz = await pagina.render(ctxDe(apiCon({ ledger: [], pnl: null, conciliacion: null, alertas: [] }, {})));
  const sec = seccion(raiz, 'Alertas abiertas');
  assert.ok(buscar(sec, '.vacio-pasos'));
  assert.match(sec.textContent, /Todavía no hay alertas registradas/);
  assert.match(sec.textContent, /nadie las está calculando/);
  assert.match(sec.textContent, /scripts\.alertas\.producir --escribir/, 'ahora hay un comando para calcularlas y guardarlas');
  const m = Object.fromEntries(buscarTodos(raiz, '.n1-metricas .metrica').map((x) => [buscar(x, '.metrica__etiqueta').textContent, x]));
  assert.equal(buscar(m['Alertas abiertas'], '.metrica__valor').textContent, '0');
  assert.match(m['Alertas abiertas'].textContent, /un cero no prueba que todo esté bien/);
  assert.equal(buscar(m['Canal al celular'], '.metrica__valor').textContent, 'Sin elegir');
  assert.equal(buscar(m['Resumen diario'], '.metrica__valor').textContent, 'No existe');
  // solo queda el aviso del canal pendiente
  assert.equal(buscarTodos(raiz, '.atencion__item').length, 1);
});

test('Avisos con todas las alertas cerradas: lo dice y conserva las cerradas', async () => {
  const raiz = await pagina.render(ctxDe(apiCon({ ledger: [], alertas: [alerta({ estado: 'cerrada' })] })));
  const sec = seccion(raiz, 'Alertas abiertas');
  assert.match(sec.textContent, /No hay alertas abiertas: todas las registradas están cerradas/);
  assert.equal(buscarTodos(sec, 'li.n1-alerta').length, 1);
});

test('Avisos: finanzas caída → error en su bloque, métricas «—» y el resto de la pantalla sigue disponible', async () => {
  const caido = new ErrorApiFalso('sin_conexion', 'No se pudo conectar');
  const raiz = await pagina.render(ctxDe(crearApiFalsa({ '/finanzas': caido, '/sistema': cargarSobre('sistema') })));
  assert.ok(buscar(seccion(raiz, 'Alertas abiertas'), '[role="alert"]'));
  const m = Object.fromEntries(buscarTodos(raiz, '.n1-metricas .metrica').map((x) => [buscar(x, '.metrica__etiqueta').textContent, buscar(x, '.metrica__valor').textContent]));
  assert.equal(m['Alertas abiertas'], '—');
  assert.equal(m['Rojas y naranjas'], '—');
  assert.ok(seccion(raiz, 'El canal al celular'));
});

test('Avisos: más de 10 cerradas se resumen; el texto hostil de las alertas se muestra como texto', async () => {
  const muchas = Array.from({ length: 13 }, (_, i) => alerta({ id: `C${i}`, estado: 'cerrada', regla_id: 'F2-A01' }));
  const hostil = alerta({ id: 'H1', regla_id: '<img src=x onerror=alert(1)>', accion_sugerida: '<script>alert(1)</script>‮', oferta_id: null, valor: '<b>1</b>', umbral: null });
  const raiz = await pagina.render(ctxDe(apiCon({ ledger: [], alertas: [hostil, ...muchas] })));
  assert.match(raiz.textContent, /Cerradas \(13\)/);
  assert.match(raiz.textContent, /hay 3 más cerradas/);
  assert.equal(buscarTodos(raiz, 'script').length, 0);
  assert.equal(buscarTodos(raiz, 'img').length, 0);
  assert.ok(raiz.textContent.includes('<script>alert(1)</script>'));
  assert.ok(raiz.textContent.includes('⟦U+202E⟧'));
});

test('Avisos: meta, glosario definido y sin jerga cruda en primer plano', async () => {
  assert.deepEqual([pagina.meta.ruta, pagina.meta.grupo, pagina.meta.titulo, pagina.meta.icono], ['avisos', 'Robots', 'Avisos', 'campana']);
  for (const clave of ['severidad_alerta', 'estado_alerta', 'resumen_diario', 'canal_avisos', 'plantilla_fija', 'dos_canales', 'robot_vigia', 'robot_alarma', 'robot_informe']) assert.ok(buscarTermino(clave), clave);
  const raiz = await pagina.render(ctxDe(apiCon(fx('finanzas_alertas.json'))));
  for (const c of buscarTodos(raiz, '.comando')) assert.ok(c.closest('details') === c);
  for (const nodo of buscarTodos(raiz, 'h1, h2, strong')) assert.doesNotMatch(nodo.textContent, /\.json|\.jsonl|\.yaml|empresa\/|ofertas\//, nodo.textContent);
  assert.ok(buscarTodos(raiz, '.fuente').length >= 1);
});
