// Pruebas de la pantalla Registro (P2): lib/registro.js (puro) y pages/registro.js (DOM y API falsos).
import test from 'node:test';
import assert from 'node:assert/strict';
import { instalar, buscar, buscarTodos } from '../fixtures/dashboard/shell/dom_falso.mjs';
import { cargarSobre, crearApiFalsa, crearCtx, dormir, ErrorApiFalso } from '../fixtures/dashboard/shell/ctx_falso.mjs';

const doc = instalar();
const L = await import('../../dashboard/web/lib/registro.js');
const { ui } = await import('../../dashboard/web/ui.js');
const pagina = await import('../../dashboard/web/pages/registro.js');

const reg = cargarSobre('registro');
const lineasFx = reg.datos.lineas;
const ofertas = cargarSobre('ofertas').datos;
const NBSP = ' ';

// ───────────────────────── lib ─────────────────────────

test('paramsConsulta: solo valores no vacíos', () => {
  assert.deepEqual(L.paramsConsulta(), { limite: 200 });
  assert.deepEqual(L.paramsConsulta({ desde: 1, limite: 50, oferta: 'OF-202611-01', etapa: '', agente: 'd3-qa' }), { limite: 50, desde: 1, oferta: 'OF-202611-01', agente: 'd3-qa' });
  assert.deepEqual(L.paramsConsulta({ desde: 0 }), { limite: 200 }, 'el servidor numera desde 1: desde=0 sería un 400');
  assert.deepEqual(L.paramsConsulta({ desde: -1 }), { limite: 200 });
  assert.deepEqual(L.paramsConsulta({ desde: '5' }), { limite: 200 }, 'desde debe ser entero');
});

test('normalizarLinea descarta lo que no es una línea del registro', () => {
  assert.equal(L.normalizarLinea(null), null);
  assert.equal(L.normalizarLinea('x'), null);
  assert.equal(L.normalizarLinea({ ts: 'x' }), null);
  assert.equal(L.normalizarLinea({ n: 1.5 }), null);
  assert.deepEqual(L.normalizarLinea({ n: 3 }).resultado, { estado: null, codigo: null });
  assert.deepEqual(L.normalizarLinea({ n: 3, resultado: { estado: 'ok', codigo: 0 } }).resultado, { estado: 'ok', codigo: 0 });
});

test('fusionarLineas: sin duplicados, orden por n, tope de memoria y avisa cuáles son nuevas', () => {
  const a = [{ n: 3 }, { n: 1 }];
  const r = L.fusionarLineas(a, [{ n: 3, x: 'actualizada' }, { n: 4 }, { n: 2 }, null, { sin_n: 1 }]);
  assert.deepEqual(r.lineas.map((l) => l.n), [1, 2, 3, 4]);
  assert.deepEqual(r.agregadas.sort(), [2, 4]);
  assert.equal(r.lineas.find((l) => l.n === 3).x, 'actualizada');
  const tope = L.fusionarLineas(Array.from({ length: 10 }, (_, i) => ({ n: i + 1 })), [{ n: 11 }, { n: 12 }], 5);
  assert.deepEqual(tope.lineas.map((l) => l.n), [8, 9, 10, 11, 12], 'se descartan las más viejas');
  assert.deepEqual(L.fusionarLineas(null, null), { lineas: [], agregadas: [] });
  assert.equal(L.MAX_LINEAS_MEMORIA, 2000);
});

test('estadoCadena: íntegra, ROTA, sin verificar y sin registro', () => {
  assert.deepEqual([L.estadoCadena(true).tono, L.estadoCadena(true).texto], ['ok', 'Historial sin alteraciones']);
  const rota = L.estadoCadena(false);
  assert.deepEqual([rota.tono, rota.texto], ['error', 'Historial alterado']);
  assert.match(rota.detalle, /No uses estos datos para decidir/);
  assert.equal(L.estadoCadena(null).texto, 'Sin verificar');
  assert.equal(L.estadoCadena(undefined).tono, 'neutro');
  assert.equal(L.estadoCadena(true, { vacio: true }).texto, 'Sin historial aún', 'si el archivo no existe no se afirma que la cadena es íntegra');
});

test('tonoDeLinea y chipResultado', () => {
  assert.equal(L.tonoDeLinea({ resultado: { estado: 'error' } }), 'error');
  assert.equal(L.tonoDeLinea({ resultado: { estado: 'bloqueado' }, evento: 'accion' }), 'aviso');
  assert.equal(L.tonoDeLinea({ resultado: { estado: 'ok' }, evento: 'bloqueo' }), 'aviso');
  assert.equal(L.tonoDeLinea({ resultado: { estado: 'ok' }, evento: 'alerta' }), 'aviso');
  assert.equal(L.tonoDeLinea({ resultado: { estado: 'ok' }, evento: 'accion' }), 'ok');
  assert.equal(L.tonoDeLinea({ resultado: { estado: 'dry_run' }, evento: 'accion' }), 'info');
  assert.equal(L.tonoDeLinea({ evento: 'accion' }), 'neutro');
  assert.deepEqual(L.chipResultado('ok'), { tono: 'ok', texto: 'OK' });
  assert.deepEqual(L.chipResultado('bloqueado'), { tono: 'aviso', texto: 'Bloqueado' });
  assert.deepEqual(L.chipResultado('dry_run'), { tono: 'info', texto: 'Simulado' });
  assert.deepEqual(L.chipResultado(null), { tono: 'neutro', texto: '—' });
  assert.deepEqual(L.chipResultado('raro'), { tono: 'neutro', texto: 'raro' });
});

test('filtrarLocal, valoresDistintos, siguienteDesde, desdeAnterior y paresDetalle', () => {
  assert.equal(L.filtrarLocal(lineasFx, {}).length, lineasFx.length);
  assert.ok(L.filtrarLocal(lineasFx, { evento: 'bloqueo' }).every((l) => l.evento === 'bloqueo'));
  assert.equal(L.filtrarLocal(lineasFx, { evento: 'bloqueo' }).length, 2);
  assert.equal(L.filtrarLocal(lineasFx, { resultado: 'error' }).length, 1);
  assert.equal(L.filtrarLocal(lineasFx, { texto: 'PRESUPUESTO' }).length, 3, 'texto sin distinguir mayúsculas');
  assert.equal(L.filtrarLocal(lineasFx, { oferta: 'OF-202611-03', etapa: 'D2' }).length, 2);
  assert.equal(L.filtrarLocal(lineasFx, { agente: 'motor', texto: 'guard' }).length, 1);
  assert.equal(L.filtrarLocal(lineasFx, { texto: '21' }).length >= 1, true, 'también por n');
  assert.deepEqual(L.filtrarLocal(null, {}), []);
  assert.deepEqual(L.valoresDistintos(lineasFx, 'etapa'), ['D1', 'D2', 'D5', 'D6', 'D7', 'D8']);
  assert.deepEqual(L.valoresDistintos(lineasFx, 'oferta_id'), ['OF-202611-01', 'OF-202611-02', 'OF-202611-03'], 'los null no cuentan');
  assert.equal(L.siguienteDesde([{ n: 5 }, { n: 9 }], 3), 10);
  assert.equal(L.siguienteDesde([{ n: 5 }], 20), 20);
  assert.equal(L.siguienteDesde([], undefined), 1);
  assert.equal(L.desdeAnterior([{ n: 450 }, { n: 500 }], 200), 250);
  assert.equal(L.desdeAnterior([{ n: 50 }], 200), 1, 'nunca pide desde=0');
  assert.equal(L.desdeAnterior([{ n: 1 }], 200), null);
  assert.equal(L.desdeAnterior([], 200), null);
  const pares = L.paresDetalle(lineasFx[0]);
  assert.deepEqual(pares.slice(0, 2).map((p) => p[0]), ['n', 'ts']);
  assert.deepEqual(pares.slice(-2).map((p) => p[0]), ['hash_previo', 'hash']);
  assert.deepEqual(L.paresDetalle(null), []);
  assert.equal(JSON.parse(L.lineaComoTexto(lineasFx[0])).n, 1);
});

test('describirEvento: cada línea en lenguaje de negocio (transición, aprobación, veredicto, bloqueo, alerta, error) sin perder el tono', () => {
  const d = (n) => L.describirEvento(lineasFx.find((l) => l.n === n));
  assert.equal(d(1).titulo, 'La etapa «Página de venta y pago» pasó a «En revisión»');
  assert.equal(d(1).detalle, 'antes: En progreso');
  assert.equal(d(1).categoria, 'cambios');
  assert.equal(d(1).etapa, 'Página de venta y pago (D5)');
  assert.equal(d(1).actor, 'IA que prepara (Página de venta y pago)');
  assert.equal(d(3).titulo, 'IA que revisa (Página de venta y pago) aprobó: tracking completo');
  assert.equal(d(4).titulo, 'Aprobaste la etapa «Página de venta y pago»');
  assert.equal(d(4).actor, 'Tú');
  assert.equal(d(7).titulo, 'IA que revisa (Anuncios) aprobó con notas: 2 hooks repetidos');
  assert.equal(d(8).titulo, 'La etapa «Anuncios» quedó aprobada');
  assert.match(d(8).detalle, /gate S/, 'la nota técnica del gate se conserva');
  assert.match(d(13).detalle, /espera tu firma/, '«gate H pendiente» se dice en humano');
  assert.deepEqual([d(11).tono, d(11).categoria, d(11).icono], ['aviso', 'atencion', 'candado']);
  assert.match(d(11).titulo, /^Se frenó una acción: guard/);
  assert.match(d(15).titulo, /^Alerta: gasto 1,8×/);
  assert.deepEqual([d(16).tono, d(16).fallo, d(16).categoria], ['error', true, 'atencion']);
  assert.equal(d(10).titulo, 'Crear campaña en seco (ABO, 3 conjuntos)', 'una acción conserva su texto');
  assert.equal(d(10).simulado, true);
  assert.equal(L.describirEvento({ n: 1, evento: 'accion', modo: 'live', entrada_resumen: 'x', resultado: { estado: 'ok' } }).live, true);
  assert.equal(L.describirEvento({ n: 1, _ilegible: true }).tono, 'error');
  assert.equal(L.describirEvento(null).titulo, 'Evento sin datos');
  assert.equal(L.describirEvento({ n: 2, evento: 'raro_nuevo' }).titulo, 'Raro nuevo', 'un tipo desconocido no rompe nada');
  assert.equal(L.actorHumano('script:subir_presupuesto'), 'Tarea automática: subir presupuesto');
  assert.equal(L.actorHumano('motor'), 'El sistema');
  assert.equal(L.actorHumano('x1-qa'), 'IA que revisa (Cumplimiento)');
  assert.equal(L.actorHumano(''), 'Alguien');
  assert.equal(L.etapaHumana('D7'), 'Campaña (D7)');
  assert.equal(L.etapaHumana('Z9'), 'Z9');
  assert.equal(L.rotuloEvento('llamada_herramienta'), 'Trabajo de IA');
});

test('categorías rápidas: conteo, filtro y «requieren revisión» = errores, bloqueos y alertas', () => {
  const c = L.contarCategorias(lineasFx);
  assert.equal(c.todo, 21);
  assert.equal(c.atencion + c.cambios + c.decisiones + c.trabajo + (c.otro || 0), 21, 'cada línea cae en una sola categoría');
  assert.deepEqual(L.filtrarCategoria(lineasFx, 'atencion').map((l) => l.n), [11, 15, 16, 18]);
  assert.equal(L.filtrarCategoria(lineasFx, 'todo').length, 21);
  assert.equal(L.filtrarCategoria(lineasFx, '').length, 21);
  assert.ok(L.filtrarCategoria(lineasFx, 'cambios').every((l) => l.evento === 'transicion'));
  assert.deepEqual(L.CATEGORIAS.map((x) => x.id), ['todo', 'atencion', 'cambios', 'decisiones', 'trabajo']);
});

test('agruparPorDia: «Hoy», «Ayer» y fechas largas, más reciente primero', () => {
  const ahora = Date.parse('2026-11-06T15:00:00Z');
  const g = L.agruparPorDia([
    { n: 1, ts: '2026-11-04T09:00:00Z' }, { n: 2, ts: '2026-11-06T10:00:00Z' }, { n: 3, ts: '2026-11-05T22:00:00Z' }, { n: 4, ts: '2026-11-06T12:00:00Z' }, { n: 5 }, { n: 6, ts: '2025-12-31T10:00:00Z' },
  ], { ahoraMs: ahora, tz: 'UTC' });
  assert.deepEqual(g.map((x) => x.rotulo), ['Hoy', 'Ayer', 'miércoles, 4 de noviembre', 'miércoles, 31 de diciembre de 2025', 'Sin fecha']);
  assert.deepEqual(g[0].lineas.map((l) => l.n), [4, 2], 'dentro del día, lo más reciente primero');
  assert.deepEqual(L.agruparPorDia(null), []);
});

test('detalleTecnicoLinea: nada técnico se pierde (ids, herramienta, modo, hashes)', () => {
  const t = Object.fromEntries(L.detalleTecnicoLinea(lineasFx.find((l) => l.n === 2)));
  assert.equal(t.evento, 'llamada_herramienta');
  assert.equal(t.herramienta, 'claude -p');
  assert.equal(t.modo, 'dry_run');
  assert.match(t.resultado, /ok \(código 0\)/);
  assert.ok(t.hash && t.hash.length >= 32);
  assert.ok(t.hash_previo);
  assert.ok(t.ejecucion_id);
  assert.deepEqual(L.detalleTecnicoLinea(null), []);
});

// ───────────────────────── página ─────────────────────────

const ctxDe = (api, extra = {}) => crearCtx({ api, ui, ruta: 'registro', estado: { ofertas, conectado: 'sse' }, ...extra });
const filas = (raiz) => buscarTodos(raiz, 'tbody tr');
const eventos = (raiz) => buscarTodos(raiz, '.u1g-ev');
const porEtiqueta = (raiz, tag, etiqueta) => buscarTodos(raiz, tag).find((e) => e.getAttribute('aria-label') === etiqueta);
const cerrarModales = () => { for (let i = 0; i < 5; i += 1) doc.teclado('Escape'); };
/** Renderiza en la vista indicada (la preferencia vive en el módulo: cada prueba fija la suya). */
const abrir = (api, vista, extra = {}) => pagina.render(ctxDe(api, { params: { vista, ...(extra.params || {}) }, ...extra }));

test('Registro: sello de integridad visible, línea de tiempo con frases humanas por día y filtros claros', async () => {
  const api = crearApiFalsa();
  const raiz = await abrir(api, 'linea');
  assert.equal(buscar(raiz, 'h1').textContent, 'Historial');
  // sello
  const sello = buscar(raiz, '.u1g-sello');
  assert.equal(sello.getAttribute('data-tono'), 'ok');
  assert.match(sello.textContent, /Historial sin alteraciones/);
  assert.match(sello.textContent, /21 eventos en el historial · 21 cargados/);
  assert.ok(buscar(sello, '.u1g-sello__medalla svg'), 'la medalla lleva icono');
  // la verificación por comando está a un clic (detalle técnico) y el comando copiable
  const tec = buscar(sello, '.detalle-tecnico');
  assert.ok(tec);
  tec.montar();
  assert.ok(buscarTodos(sello, '.comando__texto').some((c) => c.textContent === '.venv/bin/python -m engine.registro verificar --json'));
  // línea de tiempo: 21 eventos, agrupados por día, el más reciente primero, con la frase humana
  const ev = eventos(raiz);
  assert.equal(ev.length, 21);
  assert.equal(ev[0].getAttribute('data-n'), '21');
  assert.equal(ev.at(-1).getAttribute('data-n'), '1');
  assert.match(ev[0].textContent, /Subir presupuesto 24 → 28 EUR \(dry-run\)/);
  assert.match(raiz.textContent, /La etapa «Página de venta y pago» pasó a «En revisión»/);
  assert.match(raiz.textContent, /Aprobaste la etapa «Página de venta y pago»/);
  assert.match(raiz.textContent, /IA que revisa \(Anuncios\) aprobó con notas/);
  assert.ok(buscarTodos(raiz, '.u1g-dia h3').length >= 1);
  assert.deepEqual(api.llamadas[0], { metodo: 'GET', ruta: '/registro', params: { limite: 200 } });
  // filtros rápidos con números
  const cats = buscarTodos(raiz, '.u1g-cat');
  assert.deepEqual(cats.map((c) => c.getAttribute('data-id')), ['todo', 'atencion', 'cambios', 'decisiones', 'trabajo']);
  assert.match(cats[0].textContent, /Todo21/);
  assert.match(cats[1].textContent, /Requieren revisión4/);
  assert.equal(cats[0].getAttribute('aria-pressed'), 'true');
  // selectores de filtro con lo que hay
  const selOferta = porEtiqueta(raiz, 'select', 'Filtrar por oferta');
  assert.deepEqual(buscarTodos(selOferta, 'option').map((o) => o.getAttribute('value')), ['', 'OF-202611-01', 'OF-202611-02', 'OF-202611-03', 'OF-202611-04', '_ejemplo']);
  assert.equal(buscarTodos(raiz, '#lista-agentes option').length >= 8, true);
  assert.equal(buscarTodos(raiz, 'datalist').length, 1);
  assert.doesNotMatch(raiz.textContent, /LIVE/);
  assert.ok(buscarTodos(raiz, '.fuente-info').length === 1, 'la fuente va en el pie, con su icono «i»');
});

test('Registro: la tabla técnica sigue disponible con todas las columnas y el orden por número', async () => {
  const raiz = await abrir(crearApiFalsa(), 'tabla');
  const f = filas(raiz);
  assert.equal(f.length, 21);
  assert.equal(f[0].querySelectorAll('td')[0].textContent, '21', 'orden inicial: n descendente');
  assert.equal(f.at(-1).querySelectorAll('td')[0].textContent, '1');
  assert.deepEqual(buscarTodos(raiz, 'th').map((th) => th.textContent.trim()).filter(Boolean).slice(0, 8), ['#▼', 'Hora', 'Oferta · etapa', 'Agente', 'Evento', 'Resumen', 'Resultado', 'Costo']);
  assert.match(raiz.textContent, new RegExp(`0,57${NBSP}US\\$`));
  assert.equal(eventos(raiz).length, 0, 'en la tabla no hay línea de tiempo');
  // cambiar de vista con el selector
  buscarTodos(raiz, '.u1g-vista button').find((b) => b.textContent.includes('Línea de tiempo')).click();
  assert.equal(eventos(raiz).length, 21);
  assert.equal(filas(raiz).length, 0);
});

test('Registro: texto hostil (HTML, U+202E) se ve como texto y el detalle muestra la frase, lo técnico a un clic', async () => {
  const raiz = await abrir(crearApiFalsa(), 'linea');
  assert.equal(buscarTodos(raiz, 'script').length, 0);
  assert.ok(raiz.textContent.includes('<script>alert(1)</script>'));
  assert.ok(raiz.textContent.includes('⟦U+202E⟧'));
  eventos(raiz).find((e) => e.getAttribute('data-n') === '16').querySelector('.u1g-ev__cuerpo').click();
  const modal = buscarTodos(doc.body, '.modal').at(-1);
  assert.match(modal.querySelector('h2').textContent, /Evento #16 · Trabajo de IA/);
  assert.match(modal.querySelector('.u1g-detalle__frase').textContent, /Lectura de KPI del día/);
  assert.match(modal.textContent, /Error/);
  // lo técnico está en «Detalle técnico» (cerrado): hashes, ids, comando y JSON
  const tec = buscar(modal, '.detalle-tecnico');
  assert.equal(tec.hasAttribute('open'), false);
  tec.open = true; tec.montar();
  assert.match(modal.textContent, /hash_previo/);
  assert.match(modal.textContent, new RegExp(lineasFx[15].hash));
  assert.match(modal.textContent, new RegExp(lineasFx[15].hash_previo));
  assert.match(modal.textContent, /error \(código 3\)/);
  assert.ok(buscarTodos(modal, '.comando__texto').some((c) => /engine\.registro verificar/.test(c.textContent)));
  assert.equal(buscarTodos(modal, 'script').length, 0);
  assert.ok(buscarTodos(modal, 'details').length >= 2, 'incluye el visor JSON de la línea completa');
  cerrarModales();
  assert.equal(buscarTodos(doc.body, '.modal').length, 0);
});

test('Registro: filtrar por oferta/etapa/agente consulta al servidor; categoría, evento, resultado y texto filtran lo cargado', async () => {
  const api = crearApiFalsa();
  const raiz = await abrir(api, 'linea');
  const selOferta = porEtiqueta(raiz, 'select', 'Filtrar por oferta');
  selOferta.value = 'OF-202611-03'; selOferta.disparar('change');
  await dormir(10);
  assert.deepEqual(api.llamadas.at(-1).params, { limite: 200, oferta: 'OF-202611-03' });
  assert.equal(eventos(raiz).length, 2);
  const selEtapa = porEtiqueta(raiz, 'select', 'Filtrar por etapa');
  selEtapa.value = 'D2'; selEtapa.disparar('change');
  await dormir(10);
  assert.deepEqual(api.llamadas.at(-1).params, { limite: 200, oferta: 'OF-202611-03', etapa: 'D2' });
  // «Limpiar filtros» aparece y vuelve a pedir sin filtros
  const limpiar = buscarTodos(raiz, 'button').find((b) => b.textContent.includes('Limpiar filtros'));
  assert.equal(limpiar.hidden, false);
  limpiar.click();
  await dormir(10);
  assert.deepEqual(api.llamadas.at(-1).params, { limite: 200 });
  assert.equal(eventos(raiz).length, 21);
  assert.equal(limpiar.hidden, true);
  const inAg = porEtiqueta(raiz, 'input', 'Filtrar por agente');
  inAg.value = 'motor'; inAg.disparar('change');
  await dormir(10);
  assert.equal(api.llamadas.at(-1).params.agente, 'motor');
  assert.ok(eventos(raiz).length >= 6);
  inAg.value = ''; inAg.disparar('change');
  await dormir(10);
  // filtros locales: no llaman a la API
  const n = api.llamadas.length;
  const selEv = porEtiqueta(raiz, 'select', 'Filtrar por tipo de evento');
  selEv.value = 'bloqueo'; selEv.disparar('change');
  assert.equal(eventos(raiz).length, 2);
  selEv.value = ''; selEv.disparar('change');
  const txt = porEtiqueta(raiz, 'input', 'Buscar texto en las líneas cargadas');
  txt.value = 'presupuesto'; txt.disparar('input');
  assert.equal(eventos(raiz).length, 3);
  txt.value = 'zzzz'; txt.disparar('input');
  assert.match(raiz.textContent, /Ningún evento cargado coincide/);
  txt.value = ''; txt.disparar('input');
  // filtro rápido: «Requieren revisión» = errores, bloqueos y alertas
  buscarTodos(raiz, '.u1g-cat').find((c) => c.getAttribute('data-id') === 'atencion').click();
  assert.deepEqual(eventos(raiz).map((e) => e.getAttribute('data-n')), ['18', '16', '15', '11']);
  assert.equal(buscarTodos(raiz, '.u1g-cat').find((c) => c.getAttribute('data-id') === 'atencion').getAttribute('aria-pressed'), 'true');
  assert.match(raiz.textContent, /Mostrando 4 de 21 eventos cargados/);
  // resultado
  buscarTodos(raiz, '.u1g-cat').find((c) => c.getAttribute('data-id') === 'todo').click();
  const selRes = porEtiqueta(raiz, 'select', 'Filtrar por resultado');
  selRes.value = 'error'; selRes.disparar('change');
  assert.equal(eventos(raiz).length, 1);
  assert.equal(api.llamadas.length, n, 'los filtros locales no piden nada al servidor');
});

test('Registro: filtros iniciales desde la URL y la oferta activa', async () => {
  const api = crearApiFalsa();
  await abrir(api, 'linea', { params: { etapa: 'D8', agente: 'motor' } });
  assert.deepEqual(api.llamadas[0].params, { limite: 200, etapa: 'D8', agente: 'motor' });
  const api2 = crearApiFalsa();
  await abrir(api2, 'linea', { estado: { ofertas, ofertaActiva: 'OF-202611-02' } });
  assert.equal(api2.llamadas[0].params.oferta, 'OF-202611-02');
});

test('Registro en vivo: alCambio trae solo las líneas nuevas (desde=siguiente) y las resalta', async () => {
  const api = crearApiFalsa();
  const ctx = ctxDe(api, { params: { vista: 'linea' } });
  const raiz = await pagina.render(ctx);
  api.extraRegistro.push({ ...lineasFx[0], n: 22, entrada_resumen: 'evento nuevo 22', hash: 'a'.repeat(64) }, { ...lineasFx[0], n: 23, entrada_resumen: 'evento nuevo 23', hash: 'b'.repeat(64) });
  await pagina.alCambio(ctx, { tipo: 'registro', ruta: 'empresa/registro.jsonl' });
  assert.deepEqual(api.llamadas.at(-1).params, { limite: 200, desde: 22 });
  assert.equal(eventos(raiz).length, 23);
  assert.equal(eventos(raiz)[0].getAttribute('data-n'), '23');
  assert.equal(buscarTodos(raiz, '.fila-nueva').length, 2);
  assert.match(raiz.textContent, /23 eventos en el historial/);
  // sin novedades: no cambia nada ni lanza
  const antes = eventos(raiz).length;
  await pagina.alCambio(ctx, { tipo: 'sondeo' });
  assert.equal(eventos(raiz).length, antes);
  assert.equal(buscarTodos(raiz, '.fila-nueva').length, 0);
  // eventos de otro tipo se ignoran
  const llamadas = api.llamadas.length;
  await pagina.alCambio(ctx, { tipo: 'oferta' });
  assert.equal(api.llamadas.length, llamadas);
});

test('Registro en vivo (tabla): llegan líneas nuevas sin perder el orden que eligió el usuario', async () => {
  const api = crearApiFalsa();
  const ctx = ctxDe(api, { params: { vista: 'tabla' } });
  const raiz = await pagina.render(ctx);
  buscarTodos(raiz, 'th').find((th) => th.textContent.includes('Agente')).querySelector('button').click();
  const primeraAntes = filas(raiz)[0].querySelectorAll('td')[3].textContent;
  const tabla = buscar(raiz, '.tabla');
  api.extraRegistro.push({ ...lineasFx[0], n: 22, agente: 'zzz-ultimo', entrada_resumen: 'nueva' });
  await pagina.alCambio(ctx, { tipo: 'registro' });
  assert.equal(buscar(raiz, '.tabla'), tabla, 'se actualizan las filas, no se reconstruye la tabla');
  assert.equal(filas(raiz).length, 22);
  assert.equal(filas(raiz)[0].querySelectorAll('td')[3].textContent, primeraAntes, 'el orden por Agente sigue vigente');
  assert.equal(filas(raiz).at(-1).querySelectorAll('td')[3].textContent, 'zzz-ultimo');
});

test('Registro: con «Cola en vivo» apagada no se piden líneas; al volver a encenderla se ponen al día', async () => {
  const api = crearApiFalsa();
  const ctx = ctxDe(api, { params: { vista: 'linea' } });
  const raiz = await pagina.render(ctx);
  const interruptor = buscar(raiz, '[role="switch"]');
  assert.equal(interruptor.getAttribute('aria-checked'), 'true');
  interruptor.click();
  assert.equal(interruptor.getAttribute('aria-checked'), 'false');
  api.extraRegistro.push({ ...lineasFx[0], n: 22, entrada_resumen: 'pendiente' });
  const n = api.llamadas.length;
  await pagina.alCambio(ctx, { tipo: 'registro' });
  assert.equal(api.llamadas.length, n);
  assert.equal(eventos(raiz).length, 21);
  interruptor.click();
  await dormir(10);
  assert.equal(eventos(raiz).length, 22);
});

test('Registro: archivo truncado o rotado → recarga completa en vez de mezclar', async () => {
  const api = crearApiFalsa();
  const ctx = ctxDe(api, { params: { vista: 'linea' } });
  const raiz = await pagina.render(ctx);
  const corto = cargarSobre('registro');
  corto.datos.lineas = corto.datos.lineas.slice(0, 3);
  api.sobre = (async (orig) => async (ruta, params) => (ruta === '/registro' ? { datos: { lineas: corto.datos.lineas.filter((l) => params.desde === undefined || l.n >= params.desde), total: 3, siguiente: 4, cadena_ok: true }, fuente: ['empresa/registro.jsonl'], generado_en: null, vacio: false, avisos: [] } : orig(ruta, params)))(api.sobre.bind(api));
  api.sobre = await api.sobre;
  await pagina.alCambio(ctx, { tipo: 'registro' });
  assert.equal(eventos(raiz).length, 3, 'tras la rotación solo quedan las líneas nuevas del archivo');
});

test('Registro: una línea que el servidor no pudo interpretar se ve en rojo con su aviso (señal de integridad)', async () => {
  const sobre = cargarSobre('registro');
  sobre.datos.lineas.push({ n: 22, _ilegible: true, _texto: '{"roto": <script>x</script>' });
  const api = crearApiFalsa({ '/registro': sobre });
  const raiz = await abrir(api, 'linea');
  const ev = eventos(raiz).find((e) => e.getAttribute('data-n') === '22');
  assert.match(ev.textContent, /Una línea del historial no se pudo interpretar/);
  assert.equal(ev.getAttribute('data-tono'), 'error');
  assert.equal(buscarTodos(raiz, 'script').length, 0);
  assert.equal(L.tonoDeLinea({ n: 1, _ilegible: true }), 'error');
  // en la tabla técnica conserva el texto original (escapado)
  const t = await abrir(crearApiFalsa({ '/registro': sobre }), 'tabla');
  const fila = filas(t).find((tr) => tr.querySelectorAll('td')[0].textContent === '22');
  assert.match(fila.textContent, /línea ilegible/);
  assert.match(fila.textContent, /No se pudo interpretar/);
  assert.match(buscar(fila, '.chip').className, /chip--error/);
});

test('Registro: cadena ROTA es un sello rojo y grande con la advertencia', async () => {
  const rota = cargarSobre('registro'); rota.datos.cadena_ok = false;
  const raiz = await abrir(crearApiFalsa({ '/registro': rota }), 'linea');
  const sello = buscar(raiz, '.u1g-sello');
  assert.equal(sello.getAttribute('data-tono'), 'error');
  assert.match(buscar(sello, 'h2').textContent, /Historial alterado/);
  assert.match(sello.textContent, /No uses estos datos para decidir/);
});

test('Registro vacío: estado vacío con pasos y el comando; sin afirmar que la cadena es íntegra', async () => {
  const raiz = await abrir(crearApiFalsa({ '/registro': cargarSobre('registro_vacio') }), 'linea');
  assert.match(raiz.textContent, /Aún no hay historial/);
  assert.ok(buscar(raiz, '.vacio-pasos'));
  assert.ok(buscarTodos(raiz, '.comando__texto').some((c) => c.textContent.startsWith('.venv/bin/python -m engine.orq crear --brief')));
  assert.match(raiz.textContent, /Sin historial aún/);
  assert.doesNotMatch(raiz.textContent, /Historial sin alteraciones/);
  assert.equal(eventos(raiz).length, 0);
  assert.equal(buscar(raiz, '.u1g-sello').getAttribute('data-tono'), 'neutro');
});

test('Registro con error de API: errorBox con reintento y sin trazas', async () => {
  const api = crearApiFalsa({ '/registro': new ErrorApiFalso('sin_conexion', 'No se pudo conectar') });
  const raiz = await abrir(api, 'linea');
  const caja = buscar(raiz, '.error-box');
  assert.ok(caja);
  assert.match(caja.textContent, /sin_conexion/);
  assert.doesNotMatch(caja.textContent, /\.js:\d+/);
  api.sobre = crearApiFalsa().sobre;
  buscar(caja, 'button').click();
  await dormir(10);
  assert.equal(eventos(raiz).length, 21, 'tras reintentar se llena');
});

test('Registro: «Cargar anteriores» pide el tramo previo y «Mostrar más» amplía lo visible', async () => {
  // 450 líneas: la cola de 200 empieza en n=251
  const base = cargarSobre('registro');
  const grande = Array.from({ length: 450 }, (_, i) => ({ ...base.datos.lineas[i % 21], n: i + 1, entrada_resumen: `línea ${i + 1}` }));
  const api = crearApiFalsa({ '/registro': (p) => {
    const lineas = p.desde === undefined ? grande.slice(-Number(p.limite)) : grande.filter((l) => l.n >= Number(p.desde)).slice(0, Number(p.limite));
    return { ...base, datos: { lineas, total: 450, siguiente: lineas.at(-1).n + 1, cadena_ok: true } };
  } });
  const raiz = await abrir(api, 'linea');
  assert.equal(eventos(raiz).length, 120, 'la línea de tiempo pinta 120 y ofrece «mostrar más»');
  const mas = buscarTodos(raiz, 'button').find((b) => /Mostrar 80 más recientes/.test(b.textContent));
  assert.ok(mas);
  mas.click();
  assert.equal(eventos(raiz).length, 200);
  const boton = buscarTodos(raiz, 'button').find((b) => /Cargar anteriores/.test(b.textContent));
  assert.ok(boton, 'hay líneas anteriores');
  assert.match(boton.textContent, /250 más antiguas/);
  boton.click();
  await dormir(15);
  assert.deepEqual(api.llamadas.at(-1).params, { limite: 200, desde: 51 });
  assert.match(raiz.textContent, /450 eventos en el historial · 400 cargados/);
  assert.equal(eventos(raiz).length, 400);
  assert.equal(eventos(raiz).at(-1).getAttribute('data-n'), '51');
});

test('Registro: meta de página', () => {
  assert.deepEqual([pagina.meta.ruta, pagina.meta.grupo, pagina.meta.titulo], ['registro', 'Cerebro', 'Historial']);
  assert.ok(pagina.meta.escucha.includes('registro'));
});
