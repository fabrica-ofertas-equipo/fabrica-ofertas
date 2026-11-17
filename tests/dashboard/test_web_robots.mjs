// Pruebas de #/robots (N1): lib/robots.js (lógica pura: catálogo, reloj de 24 h, semana, reglas, registro tolerante) y pages/robots.js (DOM y API falsos).
import test from 'node:test';
import assert from 'node:assert/strict';
import { instalar, buscar, buscarTodos } from '../fixtures/dashboard/shell/dom_falso.mjs';
import { cargarSobre, crearApiFalsa, crearCtx, ErrorApiFalso } from '../fixtures/dashboard/shell/ctx_falso.mjs';

instalar();
const L = await import('../../dashboard/web/lib/robots.js');
const { ui } = await import('../../dashboard/web/ui.js');
const { buscarTermino } = await import('../../dashboard/web/lib/glosario-indice.js');
const pagina = await import('../../dashboard/web/pages/robots.js');

const AHORA = Date.parse('2026-11-06T14:30:00Z');
const sistemaCon = (extra = {}) => ({ ...cargarSobre('sistema'), datos: { ...cargarSobre('sistema').datos, motor_disponible: true, ...extra } });
/** Fija el reloj de la página (usa Date.now()) para que los latidos y «hace X» sean deterministas. */
async function conReloj(fn) {
  const real = Date.now;
  Date.now = () => AHORA;
  try { return await fn(); } finally { Date.now = real; }
}
const registro = (robots) => ({ datos: { robots }, fuente: ['empresa/robots.yaml'], generado_en: '2026-11-06T14:00:00Z', avisos: [], vacio: false });

// ───────────────────────── lib: catálogo ─────────────────────────

test('catálogo: 10 programas, el último es el auditor, con el horario de know-how §5', () => {
  assert.equal(L.ROBOTS.length, 10);
  assert.deepEqual(L.ROBOTS.map((r) => r.numero), [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
  assert.equal(new Set(L.ROBOTS.map((r) => r.id)).size, 10, 'ids únicos');
  assert.equal(L.ROBOTS[9].id, 'auditor');
  const h = Object.fromEntries(L.ROBOTS.map((r) => [r.id, r.horario]));
  assert.equal(h.escalera, 'Cada 30 min');
  assert.equal(h.salvavidas, 'Cada 15 min');
  assert.match(h.guardia, /01:30 – 07:30/);
  assert.equal(h.cola, '00:10');
  assert.equal(h.perfil, '23:40');
  assert.equal(h.alarma, '08:05');
  assert.match(h.vigia, /Siempre/);
  assert.equal(h.bandeja, '07:00 y 19:00');
  assert.equal(h.informe, '08:30');
  assert.equal(h.auditor, 'Cada hora');
  for (const r of L.ROBOTS) {
    assert.ok(r.hace && r.mas && r.horario && r.tecnico && r.tecnico.accion, `${r.id}: negocio y técnico completos`);
    assert.ok(buscarTermino(r.termino), `${r.id}: el glosario define «${r.termino}»`);
    assert.ok(['no_construido', 'parcial'].includes(r.codigo));
  }
});

test('el lenguaje de negocio va primero: el «qué hace» no trae rutas ni archivos', () => {
  for (const r of L.ROBOTS) assert.doesNotMatch(`${r.hace} ${r.mas}`, /\.py|\.json|\.yaml|empresa\/|engine\.|meta\.|\/api\//, r.id);
});

// ───────────────────────── lib: reloj de 24 h ─────────────────────────

test('reloj: horas, porcentajes y segmentos por tipo', () => {
  assert.equal(L.horaAMin('01:30'), 90);
  assert.equal(L.horaAMin('23:40'), 1420);
  for (const mala of ['25:00', '8', 'a:b', '', null, '12:60']) assert.equal(L.horaAMin(mala), null, String(mala));
  assert.equal(L.minAPct(90), 6.25);
  assert.equal(L.minAPct(1440), 100);
  assert.equal(L.minAPct(NaN), null);
  const guardia = L.segmentosReloj(L.ROBOTS.find((r) => r.id === 'guardia').reloj);
  assert.deepEqual(guardia[0], { tipo: 'banda', izq: 6.25, ancho: 25, hora: '01:30–07:30' });
  assert.deepEqual(guardia.slice(1).map((s) => [s.tipo, s.hora, s.inferida]), [['marca', '01:30', true], ['marca', '03:30', true], ['marca', '05:30', true], ['marca', '07:30', true]]);
  assert.deepEqual(L.segmentosReloj({ tipo: 'puntos', horas: ['07:00', '19:00'] }).map((s) => s.izq), [29.167, 79.167]);
  assert.deepEqual(L.segmentosReloj({ tipo: 'cada', min: 30 }), [{ tipo: 'continuo', izq: 0, ancho: 100, cadaMin: 30 }]);
  assert.deepEqual(L.segmentosReloj({ tipo: 'siempre' }), [{ tipo: 'siempre', izq: 0, ancho: 100 }]);
  for (const mal of [null, undefined, {}, { tipo: 'cada', min: 0 }, { tipo: 'banda', desde: '08:00', hasta: '07:00' }, { tipo: 'puntos', horas: ['x'] }, 'texto']) {
    assert.ok(Array.isArray(L.segmentosReloj(mal)), 'nunca lanza');
  }
  assert.deepEqual(L.segmentosReloj({ tipo: 'banda', desde: '08:00', hasta: '07:00' }), []);
});

test('carriles del reloj: fábrica y jurado como contexto + los 10 robots', () => {
  const c = L.carrilesReloj();
  assert.equal(c.length, 12);
  assert.deepEqual(c.slice(0, 2).map((x) => [x.id, x.contexto]), [['fabrica', true], ['jurado', true]]);
  assert.equal(c.filter((x) => !x.contexto).length, 10);
  assert.ok(c.every((x) => x.segmentos.length >= 1));
  assert.equal(L.EJE_HORAS.length, 9);
  assert.equal(L.EJE_HORAS[8].izq, 100);
  assert.equal(L.descripcionCarril(c[2]), `${c[2].nombre}: ${c[2].texto}`);
});

// ───────────────────────── lib: semana, reglas ─────────────────────────

test('semana tipo: lunes a domingo, con su motor; el índice de hoy es el del reloj local', () => {
  assert.deepEqual(L.SEMANA.map((d) => d.corto), ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']);
  assert.deepEqual(L.SEMANA.map((d) => d.tema), ['Cierre semanal', 'Tanda nueva', 'Jurado', 'Países', 'Reglas', 'Piloto automático', 'Orden del cerebro']);
  assert.ok(L.SEMANA.every((d) => d.hace && d.resultado && d.motor));
  assert.equal(L.indiceDia(new Date(2026, 10, 2, 12).getTime()), 0, 'lunes');
  assert.equal(L.indiceDia(new Date(2026, 10, 6, 12).getTime()), 4, 'viernes');
  assert.equal(L.indiceDia(new Date(2026, 10, 8, 12).getTime()), 6, 'domingo');
  assert.equal(L.indiceDia(NaN), -1);
});

test('seis reglas de oro y el principio «todo robot se audita»', () => {
  assert.equal(L.REGLAS_DE_ORO.length, 6);
  assert.deepEqual(L.REGLAS_DE_ORO.map((r) => r.n), [1, 2, 3, 4, 5, 6]);
  assert.deepEqual(L.REGLAS_DE_ORO.map((r) => r.titulo), ['La escala no se toca por dentro', 'El ganador sigue en testeo', 'Un día sin ventas no dice nada', 'Ganancia antes que volumen', 'Todo robot se audita', 'Relevo antes del cansancio']);
  assert.ok(L.REGLAS_DE_ORO.every((r) => r.negocio && r.cumple));
  assert.match(L.REGLAS_DE_ORO[2].cumple, /decidiste tú.*J3|J3/, 'la excepción del lanzamiento está dicha');
  assert.match(L.PRINCIPIO_AUDITORIA.texto, /solo el dueño|tú apruebas/);
});

// ───────────────────────── lib: estado del código ─────────────────────────

test('estadoCodigo: no construido por defecto; parcial lo que existe; planeado si no se puede comprobar el motor', () => {
  const por = (id) => L.ROBOTS.find((r) => r.id === id);
  assert.deepEqual([L.estadoCodigo(por('salvavidas'), null).clave, L.estadoCodigo(por('salvavidas'), null).texto], ['no_construido', 'No construido']);
  assert.equal(L.estadoCodigo(por('escalera'), { motor_disponible: true }).clave, 'parcial');
  const planeado = L.estadoCodigo(por('escalera'), { motor_disponible: false });
  assert.deepEqual([planeado.clave, planeado.texto], ['planeado', 'Planeado']);
  assert.match(planeado.detalle, /no afirma/);
  assert.equal(L.estadoCodigo(por('escalera'), null).clave, 'parcial', 'sin sistema no se contradice lo que dice el catálogo');
  assert.equal(L.estadoCodigo(por('auditor'), {}).clave, 'no_construido');
  assert.match(L.estadoCodigo(por('auditor'), {}).detalle, /base sobre la que va a juzgar/);
  const infra = { items: [{ id: 'M-02', estado: 'VERDE', medido_en: '2026-11-06T14:00:00Z' }, { id: 'M-03', estado: 'AMARILLO', medido_en: '2026-11-06T14:00:00Z' }, { id: 'X-99', estado: 'ROJO' }] };
  const vigia = L.estadoCodigo(por('vigia'), { motor_disponible: false, infra });
  assert.equal(vigia.clave, 'parcial', 'el vigía no depende del motor');
  assert.deepEqual(vigia.medicion.items.map((i) => i.id), ['M-02', 'M-03']);
  assert.equal(vigia.medicion.peor, 'AMARILLO');
  assert.equal(L.estadoCodigo(por('vigia'), { infra: null }).medicion, null);
  assert.deepEqual(L.conteoCodigo({ motor_disponible: true }), { total: 10, parciales: 2, planeados: 0, sinConstruir: 8 });
  assert.deepEqual(L.conteoCodigo({ motor_disponible: false }), { total: 10, parciales: 1, planeados: 1, sinConstruir: 8 });
});

test('programas que ya existen: la cadencia sale de los parámetros; sin parámetro dice «sin dato», no inventa', () => {
  const parametros = { grupos: { watchdog: { latido_cada_min: { valor: 5 } }, infra: { hc_sonda_ligera_min: { valor: 15 } }, optimizacion: { lectura_horas: { valor: 6 }, hora_decision: { valor: '09:00' } }, dashboard: { etl_meta_cada_h: { valor: 3 }, etl_stripe_backfill_hora: { valor: '03:00' } } } };
  const p = Object.fromEntries(L.programasExistentes(parametros, {}).map((x) => [x.id, x]));
  assert.equal(p.watchdog.cadencia, 'Señal de vida cada 5 min');
  assert.equal(p.sonda.cadencia, 'Cada 15 min con campañas activas');
  assert.equal(p.d8.cadencia, 'Lectura cada 6 h · decisión a las 09:00');
  assert.equal(p.etl.cadencia, 'Meta cada 3 h · repaso de Stripe a las 03:00 (hora universal)');
  assert.match(p.monitor.cadencia, /1, 6, 24, 48 y 72 h/);
  const vacio = Object.fromEntries(L.programasExistentes(null, {}).map((x) => [x.id, x]));
  assert.equal(vacio.watchdog.sinDato, true);
  assert.match(vacio.watchdog.cadencia, /sin dato/);
  assert.equal(vacio.monitor.sinDato, false, 'meta.monitor tiene ventanas fijas en el código');
  assert.equal(L.valorParametro({ grupos: { a: { b: { valor: null } } } }, 'a.b'), undefined);
  assert.equal(L.valorParametro({ a: { b: 7 } }, 'a.b'), 7);
  assert.equal(L.valorParametro(null, 'a.b'), undefined);
  const conInfra = L.programasExistentes(parametros, { infra: { items: [{ id: 'C-09', estado: 'VERDE' }] } });
  assert.deepEqual(conInfra.find((x) => x.id === 'watchdog').medicion, [{ id: 'C-09', estado: 'VERDE', medido_en: null }]);
});

// ───────────────────────── lib: registro real tolerante ─────────────────────────

test('normalizarRegistro tolera listas, diccionarios, sinónimos y campos que faltan (null, nunca inventado)', () => {
  const dic = L.normalizarRegistro({ robots: { escalera: { nivel: 'n2', estado: 'live', horario: 'cada 30 min', ultimo_latido: '2026-11-06T14:20:00Z', latido_max_min: 45, acierto_pct: 62.5 }, auditor: {} } });
  assert.equal(dic.total, 2);
  assert.deepEqual(dic.robots[0], { id: 'escalera', nombre: null, cadencia: 'cada 30 min', nivel: 'N2', estado: 'vivo', ultimoLatido: '2026-11-06T14:20:00Z', latidoMaxMin: 45, aciertoBp: 6250, aciertoCortesBp: null, aciertoSubasBp: null });
  assert.deepEqual([dic.robots[1].nivel, dic.robots[1].estado, dic.robots[1].ultimoLatido, dic.robots[1].aciertoBp, dic.robots[1].cadencia], [null, null, null, null, null], 'campos que faltan = null');
  assert.deepEqual(dic.conteos, { vivo: 1, sombra: 0, apagado: 0, sinEstado: 1 });
  const lista = L.normalizarRegistro([{ id: 'R7', nombre: 'Vigía', estado: 'Sombra', nivel: 0, acierto: 0.75, latido: { ts: '2026-11-06T14:29:00Z', max_min: 20 } }, { robot_id: 'cola', estado: 'apagado', acierto_bp: 5000 }]);
  assert.deepEqual(lista.robots.map((r) => [r.id, r.estado, r.nivel, r.aciertoBp, r.latidoMaxMin]), [['R7', 'sombra', 'N0', 7500, 20], ['cola', 'apagado', null, 5000, null]]);
  assert.equal(lista.robots[0].ultimoLatido, '2026-11-06T14:29:00Z');
  // basura: ni lanza ni inventa
  for (const x of [null, undefined, 5, 'x', [], {}, { robots: 5 }, { robots: [null, 3, {}] }, [{ nivel: 'N9', estado: 'raro', acierto: 'mucho' }]]) {
    const n = L.normalizarRegistro(x);
    assert.ok(Array.isArray(n.robots), JSON.stringify(x));
  }
  const raro = L.normalizarRegistro([{ id: 'x', nivel: 'N9', estado: 'raro', acierto: 'mucho', acierto_bp: 99999 }]).robots[0];
  assert.deepEqual([raro.nivel, raro.estado, raro.aciertoBp], [null, null, null]);
  assert.equal(L.aciertoEnBp({ acierto: 0 }), 0, 'un 0 medido es un dato');
  assert.equal(L.aciertoEnBp({}), null, 'sin medir no es 0');
  assert.equal(L.normalizarNivel('N4'), 'N4');
  assert.equal(L.normalizarNivel(5), null);
  assert.equal(L.normalizarEstadoRobot('Encendido'), 'vivo');
});

test('estadoLatido: sin latido, al día, vencido (vivo = crítico, sombra = aviso) y sin límite', () => {
  const r = (extra) => ({ id: 'x', estado: 'vivo', latidoMaxMin: 30, ultimoLatido: '2026-11-06T14:20:00Z', ...extra });
  assert.equal(L.estadoLatido(r({ ultimoLatido: null }), AHORA).clave, 'sin_latido');
  const ok = L.estadoLatido(r(), AHORA);
  assert.deepEqual([ok.clave, ok.tono, ok.minutos], ['al_dia', 'ok', 10]);
  const viejo = L.estadoLatido(r({ ultimoLatido: '2026-11-06T13:00:00Z' }), AHORA);
  assert.deepEqual([viejo.clave, viejo.tono], ['vencido', 'critico']);
  assert.match(viejo.texto, /máximo 30 min/);
  assert.equal(L.estadoLatido(r({ ultimoLatido: '2026-11-06T13:00:00Z', estado: 'sombra' }), AHORA).tono, 'aviso');
  assert.equal(L.estadoLatido(r({ latidoMaxMin: null }), AHORA).clave, 'sin_limite');
  assert.equal(L.estadoLatido(r({ ultimoLatido: 'basura' }), AHORA).clave, 'sin_latido');
  assert.equal(L.estadoLatido(r({ ultimoLatido: '2026-11-06T15:00:00Z' }), AHORA).minutos, 0, 'una fecha futura no da edad negativa');
});

test('nombreVisible: el del registro, o el del catálogo si el id coincide, o el id', () => {
  assert.equal(L.nombreVisible({ id: 'x', nombre: 'Mío' }), 'Mío');
  assert.equal(L.nombreVisible({ id: 'cola_de_testeo' }), 'Cola de testeo');
  assert.equal(L.nombreVisible({ id: 'raro' }), 'raro');
  assert.equal(L.nombreVisible(null), '');
});

test('unirConRegistro: empareja por id, número o nombre y deja los sueltos aparte', () => {
  const reg = L.normalizarRegistro([{ id: 'escalera_de_escala' }, { id: 'R7' }, { nombre: 'Informe del día', id: 'abc' }, { id: 'otro_cosa' }]);
  const u = L.unirConRegistro(reg);
  assert.equal(u.filas.length, 10);
  const real = (id) => u.filas.find((f) => f.robot.id === id).real;
  assert.equal(real('escalera').id, 'escalera_de_escala');
  assert.equal(real('vigia').id, 'R7');
  assert.equal(real('informe').id, 'abc');
  assert.equal(real('salvavidas'), null);
  assert.deepEqual(u.sueltos.map((x) => x.id), ['otro_cosa']);
  assert.equal(L.unirConRegistro(null).filas.every((f) => f.real === null), true);
});

test('clasificarLecturaRegistro: ok · vacío · sin ruta (404) · error', () => {
  assert.equal(L.clasificarLecturaRegistro({ error: { estado: 404, codigo: 'ruta_no_encontrada' } }), 'sin_ruta');
  assert.equal(L.clasificarLecturaRegistro({ error: { codigo: 'no_existe' } }), 'sin_ruta');
  assert.equal(L.clasificarLecturaRegistro({ error: { codigo: 'sin_conexion' } }), 'error');
  assert.equal(L.clasificarLecturaRegistro({ sobre: { vacio: true, datos: null } }), 'vacio');
  assert.equal(L.clasificarLecturaRegistro({ sobre: { vacio: false, datos: { robots: [] } } }), 'vacio');
  assert.equal(L.clasificarLecturaRegistro({ sobre: { datos: [{ id: 'a' }] } }), 'ok');
  assert.equal(L.clasificarLecturaRegistro({}), 'vacio');
  assert.equal(L.vistaValida('registro'), 'registro');
  assert.equal(L.vistaValida('x'), 'plan');
});

test('métricas y atención: sin registro «—» y aviso informativo; con registro, robots sin latido y acierto bajo', () => {
  const sinReg = Object.fromEntries(L.metricasRobots({ sistema: { motor_disponible: true }, registro: null, estadoRegistro: 'sin_ruta', ahoraMs: AHORA }).map((m) => [m.id, m]));
  assert.equal(sinReg.plan.valor, 10);
  assert.equal(sinReg.codigo.valor, 2);
  assert.equal(sinReg.registrados.valor, null, 'sin registro: «—», nunca 0');
  assert.equal(sinReg.auditor.valor, null);
  const a = L.atencionRobots({ sistema: { motor_disponible: true }, registro: null, estadoRegistro: 'vacio', ahoraMs: AHORA });
  assert.equal(a.length, 1);
  assert.equal(a[0].tono, 'info');
  assert.match(a[0].detalle, /10 robots; 2 tienen una parte ya construida/);
  const reg = L.normalizarRegistro([
    { id: 'escalera', estado: 'vivo', nivel: 'N3', ultimo_latido: '2026-11-06T10:00:00Z', latido_max_min: 45 },
    { id: 'auditor', estado: 'sombra', acierto_bp: 7300, ultimo_latido: '2026-11-06T14:29:00Z', latido_max_min: 90 },
    { id: 'salvavidas', estado: 'apagado', acierto_cortes_bp: 4000 },
  ]);
  const m = Object.fromEntries(L.metricasRobots({ sistema: {}, registro: reg, estadoRegistro: 'ok', ahoraMs: AHORA }).map((x) => [x.id, x]));
  assert.equal(m.registrados.valor, 1);
  assert.match(m.registrados.contexto, /3 en el registro · 1 en sombra · 1 apagado · 1 sin señal de vida/);
  assert.equal(m.registrados.tono, 'aviso');
  assert.match(m.auditor.valor, /73/);
  const items = L.atencionRobots({ registro: reg, estadoRegistro: 'ok', ahoraMs: AHORA });
  assert.deepEqual(items.map((i) => i.tono), ['critico', 'aviso']);
  assert.match(items[0].titulo, /Escalera de escala no da señales de vida/);
  assert.match(items[1].titulo, /Salvavidas acierta menos de lo exigido/);
});

// ───────────────────────── página ─────────────────────────

const ctxDe = (api, params = {}, extra = {}) => crearCtx({ api, ui, ruta: 'robots', params, ...extra });
const apiBase = (extra = {}) => crearApiFalsa({ '/sistema': sistemaCon(), '/parametros': { ...cargarSobre('parametros'), datos: { parametros: { grupos: { watchdog: { latido_cada_min: { valor: 5 } }, optimizacion: { lectura_horas: { valor: 6 }, hora_decision: { valor: '09:00' } } } } } }, ...extra });
const filaDe = (raiz, id) => buscar(raiz, `[data-robot="${id}"]`);

test('Robots (sin registro): catálogo de 10, estados por lo que existe en código, reloj de 24 h y semana tipo', async () => {
  const api = apiBase();
  const raiz = await pagina.render(ctxDe(api, { vista: 'plan' }));
  assert.equal(buscar(raiz, 'h1').textContent, 'Los robots: qué corre y cuándo');
  assert.match(buscar(raiz, '.cab__desc').textContent, /no se enciende ni se apaga ninguno/);
  assert.deepEqual(buscarTodos(raiz, '[role="tab"]').map((t) => t.textContent.replace(/\d+$/, '')), ['Plan y horarios', 'Registro real', 'Reglas de oro']);
  // atención informativa + 5 métricas (la de robots en sombra sin estado guardado es «—»), ninguna con cifra inventada
  assert.match(buscar(raiz, '.atencion').textContent, /Todavía no hay ningún robot encendido/);
  const metricas = Object.fromEntries(buscarTodos(raiz, '.n1-metricas .metrica').map((m) => [buscar(m, '.metrica__etiqueta').textContent, buscar(m, '.metrica__valor').textContent]));
  assert.deepEqual(metricas, { 'Robots en el plan': '10', 'Con algo ya construido': '2', 'Registrados y vivos': '—', 'Acierto del auditor': '—', 'Robots en sombra': '—' });
  // catálogo
  const filas = buscarTodos(raiz, '.n1-rb__fila[data-robot]');
  assert.deepEqual(filas.map((f) => f.getAttribute('data-robot')), L.ROBOTS.map((r) => r.id));
  assert.match(filaDe(raiz, 'escalera').textContent, /Cada 30 min/);
  assert.match(filaDe(raiz, 'guardia').textContent, /01:30 – 07:30/);
  assert.match(filaDe(raiz, 'escalera').textContent, /Parcial/);
  assert.match(filaDe(raiz, 'escalera').textContent, /escalar. queda anotado pero no se ejecuta/);
  assert.match(filaDe(raiz, 'vigia').textContent, /Parcial/);
  assert.match(filaDe(raiz, 'salvavidas').textContent, /No construido/);
  assert.doesNotMatch(filaDe(raiz, 'salvavidas').textContent, /Parcial/);
  // detalle técnico cerrado: acción, gate y topes no están en primer plano
  const tec = buscar(filaDe(raiz, 'escalera'), '.detalle-tecnico');
  assert.equal(tec.hasAttribute('open'), false);
  tec.open = true; tec.montar();
  assert.match(tec.textContent, /reducir y aumentar_presupuesto/);
  // reloj de 24 h: 12 carriles, marcas con su posición
  assert.equal(buscarTodos(raiz, '.n1-reloj__pista').length, 12);
  assert.equal(buscarTodos(raiz, '.n1-reloj__eje span').length, 9);
  assert.equal(buscarTodos(raiz, '.n1-marca--inferida').length, 4, 'las 4 vueltas del guardia nocturno son inferidas');
  const carril = buscarTodos(raiz, '.n1-reloj__pista').find((p) => p.getAttribute('aria-label').startsWith('Cola de testeo'));
  assert.equal(buscar(carril, '.n1-marca').getAttribute('title'), '00:10');
  // semana tipo
  const dias = buscarTodos(raiz, '.n1-dia');
  assert.equal(dias.length, 7);
  assert.equal(buscarTodos(raiz, '.n1-dia[aria-current="date"]').length, 1, 'se marca el día de hoy');
  assert.equal(dias.findIndex((d) => d.getAttribute('aria-current') === 'date'), L.indiceDia(Date.now()));
  assert.match(dias[0].textContent, /Cierre semanal/);
  // programas que ya existen: la cadencia viene de los parámetros
  assert.match(buscar(raiz, '[data-programa="watchdog"]').textContent, /Señal de vida cada 5 min/);
  assert.match(buscar(raiz, '[data-programa="d8"]').textContent, /Lectura cada 6 h · decisión a las 09:00/);
  assert.match(buscar(raiz, '[data-programa="sonda"]').textContent, /sin dato/, 'el parámetro que falta se dice, no se inventa');
  assert.deepEqual(api.llamadas.map((l) => l.ruta).sort(), ['/parametros', '/robots', '/robots/sombra', '/sistema']);
});

test('Robots: si el panel no puede comprobar el motor, la escalera es «Planeado» (no se afirma código)', async () => {
  const raiz = await pagina.render(ctxDe(crearApiFalsa({ '/sistema': cargarSobre('sistema') }), { vista: 'plan' }));
  assert.match(filaDe(raiz, 'escalera').textContent, /Planeado/);
  assert.doesNotMatch(filaDe(raiz, 'escalera').textContent, /Parcial/);
  const metricas = Object.fromEntries(buscarTodos(raiz, '.n1-metricas .metrica').map((m) => [buscar(m, '.metrica__etiqueta').textContent, buscar(m, '.metrica__valor').textContent]));
  assert.equal(metricas['Con algo ya construido'], '1');
});

test('Robots: nunca hay botones que enciendan, apaguen o cambien un robot', async () => {
  const api = apiBase({ '/robots': registro([{ id: 'escalera', estado: 'vivo', nivel: 'N2' }]) });
  for (const vista of ['plan', 'registro', 'reglas']) {
    const raiz = await pagina.render(ctxDe(api, { vista }));
    for (const b of buscarTodos(raiz, 'button')) assert.doesNotMatch(`${b.textContent} ${b.getAttribute('aria-label') || ''}`, /encend|apag|activ|prender|pausar|reanudar|subir de nivel|bajar de nivel/i, `${vista}: «${b.textContent}»`);
    assert.equal(buscarTodos(raiz, 'input, select, textarea').length, 0, 'sin formularios');
  }
  assert.equal(api.llamadas.filter((l) => l.metodo === 'POST').length, 0, 'solo lectura');
});

test('Robots (pestaña registro) sin archivo: estado vacío con pasos y sin cifras inventadas', async () => {
  for (const [nombre, override] of [['ruta ausente', undefined], ['archivo ausente', { datos: null, vacio: true, fuente: ['empresa/robots.yaml'] }]]) {
    const raiz = await pagina.render(ctxDe(apiBase(override ? { '/robots': override } : {}), { vista: 'registro' }));
    const vacio = buscar(raiz, '.vacio-pasos');
    assert.ok(vacio, nombre);
    assert.match(vacio.textContent, /Todavía no hay registro de robots/);
    assert.match(vacio.textContent, /Todavía no hay un comando para generarlo/);
    assert.match(vacio.textContent, /sin dato/);
    assert.equal(buscarTodos(raiz, 'tbody tr').length, 0);
    assert.match(buscar(raiz, '.seccion').textContent, /Aquí nunca hay botones para encender/);
  }
  const sinRuta = await pagina.render(ctxDe(apiBase(), { vista: 'registro' }));
  const tec = buscarTodos(sinRuta, '.detalle-tecnico').find((d) => d.textContent.includes('Detalle técnico del registro'));
  tec.open = true; tec.montar();
  assert.match(tec.textContent, /empresa\/robots\.yaml/);
  assert.match(tec.textContent, /ruta \/api\/robots/);
  assert.equal(buscar(tec, '.comando__texto').textContent, 'cat empresa/robots.yaml');
});

test('Robots (pestaña registro) con archivo: tabla con nivel, estado, latido y acierto; los campos que faltan dicen «sin dato»', async () => {
  const datos = registro([
    { id: 'escalera', nivel: 'N2', estado: 'vivo', horario: 'cada 30 min', ultimo_latido: '2026-11-06T14:20:00Z', latido_max_min: 45, acierto_pct: 71 },
    { id: 'salvavidas', estado: 'sombra' },
    { id: 'auditor', nombre: 'Auditor de decisiones', nivel: 1, estado: 'apagado', ultimo_latido: '2026-11-05T01:00:00Z', latido_max_min: 90 },
  ]);
  const ctx = ctxDe(apiBase({ '/robots': datos }), { vista: 'registro' });
  const raiz = await conReloj(() => pagina.render(ctx));
  const filas = buscarTodos(raiz, 'tbody tr');
  assert.equal(filas.length, 3);
  const celdas = (i) => buscarTodos(filas[i], 'td').map((c) => c.textContent);
  assert.match(celdas(0)[0], /Escalera de escala/, 'el nombre del catálogo completa un id suelto');
  assert.match(celdas(0)[2], /N2/);
  assert.match(celdas(0)[3], /Vivo/);
  assert.match(celdas(0)[5], /71/);
  assert.match(celdas(1).join('|'), /sin dato/, 'sin nivel: «sin dato»');
  assert.match(celdas(1)[4], /Sin señal de vida todavía/);
  assert.match(celdas(1)[5], /sin medir/, 'sin acierto medido: nunca 0 %');
  assert.match(celdas(2)[0], /Auditor de decisiones/);
  assert.match(celdas(2)[3], /Apagado/);
  assert.match(celdas(2)[4], /Sin señal de vida .* \(máximo 90 min\)/, 'un robot que no late dentro de su límite se marca');
  assert.equal(buscar(raiz, '.vacio-pasos'), null);
  assert.match(raiz.textContent, /7 de los 10 robots del plan todavía no aparecen en el registro/);
  // la métrica y el catálogo reflejan el registro real
  const plan = await conReloj(() => pagina.render(ctxDe(apiBase({ '/robots': datos }), { vista: 'plan' })));
  assert.match(filaDe(plan, 'escalera').textContent, /Vivo/);
  assert.match(filaDe(plan, 'escalera').textContent, /N2/);
  assert.match(filaDe(plan, 'escalera').textContent, /Al día/);
  assert.match(filaDe(plan, 'auditor').textContent, /Apagado/);
  const m = Object.fromEntries(buscarTodos(plan, '.n1-metricas .metrica').map((x) => [buscar(x, '.metrica__etiqueta').textContent, buscar(x, '.metrica__valor').textContent]));
  assert.equal(m['Registrados y vivos'], '1');
  assert.equal(m['Acierto del auditor'], '—', 'el auditor está apagado y sin acierto');
});

test('Robots (registro): texto hostil del archivo se muestra como texto', async () => {
  const datos = registro([{ id: '<img src=x onerror=alert(1)>', nombre: '<script>alert(1)</script>‮', estado: 'vivo', horario: '<b>x</b>' }]);
  const raiz = await pagina.render(ctxDe(apiBase({ '/robots': datos }), { vista: 'registro' }));
  assert.equal(buscarTodos(raiz, 'script').length, 0);
  assert.equal(buscarTodos(raiz, 'img').length, 0);
  assert.ok(raiz.textContent.includes('<script>alert(1)</script>'));
  assert.ok(raiz.textContent.includes('⟦U+202E⟧'));
  assert.ok(!raiz.textContent.includes('‮'));
});

test('Robots (reglas): el principio y las seis reglas de oro, con el cómo-se-cumple como detalle', async () => {
  const raiz = await pagina.render(ctxDe(apiBase(), { vista: 'reglas' }));
  assert.match(buscar(raiz, '.n1-principio').textContent, /Todo robot se audita/);
  const reglas = buscarTodos(raiz, '.n1-regla');
  assert.equal(reglas.length, 6);
  assert.match(reglas[0].textContent, /La escala no se toca por dentro/);
  assert.match(reglas[2].textContent, /Un día sin ventas no dice nada/);
  const det = buscar(reglas[2], '.detalle-tecnico');
  assert.ok(det);
  det.open = true; det.montar();
  assert.match(det.textContent, /J3/);
  assert.ok(buscar(raiz, '.seccion__ayuda').textContent.includes('decisión tuya'));
});

test('Robots: cambiar de pestaña pinta su cuerpo; la vista inválida cae en «plan»', async () => {
  const raiz = await pagina.render(ctxDe(apiBase(), { vista: 'plan' }));
  assert.ok(buscar(raiz, '.n1-rb'));
  buscarTodos(raiz, '[role="tab"]').find((t) => t.textContent.startsWith('Reglas')).click();
  assert.equal(buscar(raiz, '.n1-rb'), null);
  assert.equal(buscarTodos(raiz, '.n1-regla').length, 6);
  buscarTodos(raiz, '[role="tab"]').find((t) => t.textContent.startsWith('Registro')).click();
  assert.ok(buscar(raiz, '.vacio-pasos'));
  const mala = await pagina.render(ctxDe(apiBase(), { vista: 'inventada' }));
  assert.ok(buscar(mala, '.n1-rb'), 'la vista inválida cae en plan');
});

test('Robots: error de red en el registro → errorBox en su pestaña; el catálogo sigue disponible', async () => {
  const caido = new ErrorApiFalso('sin_conexion', 'No se pudo conectar');
  const api = apiBase({ '/robots': caido });
  const registroTab = await pagina.render(ctxDe(api, { vista: 'registro' }));
  assert.ok(buscar(registroTab, '[role="alert"]'));
  const plan = await pagina.render(ctxDe(api, { vista: 'plan' }));
  assert.equal(buscarTodos(plan, '.n1-rb__fila[data-robot]').length, 10);
  const todoCaido = await pagina.render(ctxDe(crearApiFalsa({ '/sistema': caido, '/parametros': caido, '/robots': caido }), { vista: 'plan' }));
  assert.equal(buscarTodos(todoCaido, '.n1-rb__fila[data-robot]').length, 10, 'el catálogo no depende de la API');
});

test('Robots: meta de página y sin jerga cruda en primer plano', async () => {
  assert.deepEqual([pagina.meta.ruta, pagina.meta.grupo, pagina.meta.titulo, pagina.meta.icono], ['robots', 'Robots', 'Robots', 'rayo']);
  assert.ok(pagina.meta.escucha.includes('empresa'));
  const raiz = await pagina.render(ctxDe(apiBase(), { vista: 'plan' }));
  for (const c of buscarTodos(raiz, '.comando')) assert.ok(c.closest('details') === c);
  for (const nodo of buscarTodos(raiz, 'h1, h2, h3, strong')) assert.doesNotMatch(nodo.textContent, /\.json|\.jsonl|\.yaml|empresa\/|ofertas\//, nodo.textContent);
  assert.ok(buscarTodos(raiz, '.fuente').length >= 1);
});
