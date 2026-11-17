// Pruebas de la pantalla Resumen (P2): lib/resumen.js (puro) y pages/resumen.js (con DOM y API falsos).
import test from 'node:test';
import assert from 'node:assert/strict';
import { instalar, buscar, buscarTodos } from '../fixtures/dashboard/shell/dom_falso.mjs';
import { cargarSobre, crearApiFalsa, crearCtx, ErrorApiFalso } from '../fixtures/dashboard/shell/ctx_falso.mjs';

const doc = instalar();
const L = await import('../../dashboard/web/lib/resumen.js');
const { ui } = await import('../../dashboard/web/ui.js');
const pagina = await import('../../dashboard/web/pages/resumen.js');

const NBSP = ' ';
const ofertas = cargarSobre('ofertas').datos;

// ───────────────────────── lib ─────────────────────────

test('comandoFirmar: comando exacto y nunca con texto hostil', () => {
  assert.equal(L.comandoFirmar('OF-202611-01', 'D7'), '.venv/bin/python -m engine.orq firmar --oferta OF-202611-01 --etapa D7 --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno');
  for (const [o, e] of [['OF-1; rm -rf /', 'D7'], ['OF-202611-01', 'D7 && curl x'], ['OF-202611-01', ''], [null, 'D7'], ['OF-202611-01', undefined], ['OF-202611-01\n', 'D7'], ['$(id)', 'D7'], ['OF-202611-01', 'd7'], ['OF-202611-01', 'D7‮']]) {
    assert.equal(L.comandoFirmar(o, e), null, JSON.stringify([o, e]));
  }
  assert.equal(L.ofertaIdValido('OF-202611-01'), true);
  assert.equal(L.ofertaIdValido('OF-20261-01'), false);
});

test('agruparPorFase: orden de ciclo de vida, fases desconocidas al final, sin columnas vacías', () => {
  const g = L.agruparPorFase([{ oferta_id: 'B', fase: 'en_test' }, { oferta_id: 'A', fase: 'borrador' }, { oferta_id: 'C', fase: 'rara' }, { oferta_id: 'D' }, { oferta_id: 'A2', fase: 'borrador' }, null, 'x']);
  assert.deepEqual(g.map((x) => x.fase), ['borrador', 'en_test', 'rara', 'sin_fase']);
  assert.deepEqual(g[0].ofertas.map((o) => o.oferta_id), ['A', 'A2']);
  assert.deepEqual(L.agruparPorFase([]), []);
  assert.deepEqual(L.agruparPorFase(null), []);
});

test('gatesPendientes: uno por etapa, las reales antes que la demo, con su comando', () => {
  const g = L.gatesPendientes(ofertas);
  assert.deepEqual(g.map((x) => `${x.oferta_id}:${x.etapa}:${x.demo}`), ['OF-202611-03:D2:false', '_ejemplo:D7:true']);
  assert.equal(g[1].id_estado, 'OF-202611-01', 'la demo se llama como su carpeta; el comando usa el id de estado.json');
  assert.equal(g[1].comando, '.venv/bin/python -m engine.orq firmar --oferta OF-202611-01 --etapa D7 --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno');
  assert.equal(g[0].comando, '.venv/bin/python -m engine.orq firmar --oferta OF-202611-03 --etapa D2 --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno');
  assert.deepEqual(L.gatesPendientes([{ oferta_id: 'OF-1; x', gates_pendientes: ['D1'] }])[0].comando, null);
  assert.deepEqual(L.gatesPendientes(null), []);
  assert.deepEqual(L.gatesPendientes([{ oferta_id: 'OF-202611-01', gates_pendientes: 'D1' }]), []);
});

test('sumarPorMoneda: nunca mezcla monedas ni usa float; ignora lo inválido', () => {
  const r = L.sumarPorMoneda([{ monto: 100, moneda: 'EUR' }, { monto: 250, moneda: 'eur' }, { monto: 5, moneda: 'PLN' }, { monto: 1.5, moneda: 'EUR' }, { monto: 7 }, null, undefined, { monto: '5', moneda: 'EUR' }]);
  assert.deepEqual(r.filas, [{ moneda: 'EUR', monto: 350 }, { moneda: 'PLN', monto: 5 }]);
  assert.equal(r.ignorados, 3);
  const grande = L.sumarPorMoneda([{ monto: Number.MAX_SAFE_INTEGER, moneda: 'USD' }, { monto: Number.MAX_SAFE_INTEGER, moneda: 'USD' }]);
  assert.equal(grande.filas[0].monto, '18014398509481982', 'sin perder precisión: sale como texto entero');
  assert.deepEqual(L.sumarPorMoneda(null), { filas: [], ignorados: 0 });
});

test('totalesDia: la oferta demo no suma al gasto ni al costo de IA', () => {
  const t = L.totalesDia(ofertas);
  assert.deepEqual(t.gastoHoy, [{ moneda: 'EUR', monto: 4200 }, { moneda: 'PLN', monto: 0 }]);
  assert.deepEqual(t.gastoAcumulado, [{ moneda: 'EUR', monto: 18950 }, { moneda: 'PLN', monto: 0 }]);
  assert.deepEqual(t.costoIa, [{ moneda: 'EUR', monto: 903 }, { moneda: 'USD', monto: 188 }]);
  assert.equal(t.demo, 1);
  assert.equal(t.reales, 3);
  const hoy = L.totalesDia([{ gasto: { hoy: { monto: 9, moneda: 'EUR' } }, costo_ia: { monto: 100, moneda: 'EUR', hoy: { monto: 7, moneda: 'EUR' } } }]);
  assert.deepEqual(hoy.costoIa, [{ moneda: 'EUR', monto: 7 }], 'si hay costo_ia.hoy, manda sobre el acumulado');
  assert.deepEqual(L.totalesDia([]).gastoHoy, []);
});

test('avanceEtapas y etapaActual', () => {
  const av = L.avanceEtapas(ofertas[0].etapas);
  assert.equal(av.total, 11);
  assert.equal(av.aprobadas, 7);
  assert.deepEqual(av.segmentos.map((s) => [s.titulo, s.valor, s.tono]), [['aprobado', 7, 'ok'], ['en_QA', 1, 'info'], ['pendiente', 3, 'neutro']]);
  assert.deepEqual(L.etapaActual(ofertas[0].etapas), { etapa: 'D7', estado: 'en_QA' });
  assert.deepEqual(L.etapaActual({ M1: 'aprobado', D1: { estado: 'aprobado' } }), null);
  assert.deepEqual(L.etapaActual({ M1: { estado: 'bloqueado' } }), { etapa: 'M1', estado: 'bloqueado' });
  assert.equal(L.etapaActual(null), null);
  assert.deepEqual(L.avanceEtapas(null), { total: 0, aprobadas: 0, conteos: {}, segmentos: [] });
});

test('alertasUnificadas: alertas/bloqueos/errores del registro + finanzas abiertas, recientes primero', () => {
  const registro = cargarSobre('registro').datos;
  const fin = cargarSobre('finanzas').datos;
  const a = L.alertasUnificadas({ registro, finanzas: fin, limite: 50 });
  assert.ok(a.length >= 5);
  assert.deepEqual(a.map((x) => x.ts), [...a.map((x) => x.ts)].sort().reverse(), 'orden descendente por fecha');
  assert.ok(a.some((x) => x.fuente === 'finanzas' && /gasto_sobre_presupuesto/.test(x.titulo)));
  assert.ok(a.some((x) => x.tono === 'error'));
  assert.equal(L.alertasUnificadas({ registro, finanzas: fin, limite: 2 }).length, 2);
  const cerradas = L.alertasUnificadas({ finanzas: { alertas: [{ estado: 'cerrada', ts: 'x' }, { estado: 'resuelta' }, { estado: 'abierta', severidad: 'alta', regla_id: 'r' }] } });
  assert.equal(cerradas.length, 1);
  assert.equal(cerradas[0].tono, 'error');
  assert.deepEqual(L.alertasUnificadas({}), []);
  assert.deepEqual(L.alertasUnificadas({ registro: { lineas: [null, 5, { evento: 'accion', resultado: { estado: 'ok' } }] } }), []);
});

test('estadoInfra: VERDE solo si es vivo y está vigente (≤ 6 h); lo demás avisa', () => {
  const ahora = Date.parse('2026-11-06T14:00:00Z');
  assert.equal(L.estadoInfra(null, ahora).texto, 'Sin chequeo');
  assert.equal(L.estadoInfra(null, ahora).ok, false);
  const ok = L.estadoInfra({ semaforo: 'VERDE', modo: 'vivo', generado_en: '2026-11-06T12:00:00Z' }, ahora);
  assert.deepEqual([ok.tono, ok.ok, ok.detalle], ['ok', true, 'vigente']);
  const simulado = L.estadoInfra({ semaforo: 'VERDE', modo: 'simulado', generado_en: '2026-11-06T12:00:00Z' }, ahora);
  assert.equal(simulado.tono, 'aviso');
  assert.match(simulado.detalle, /modo simulado: no sirve para gastar ni activar de verdad/);
  const viejo = L.estadoInfra({ semaforo: 'VERDE', modo: 'vivo', generado_en: '2026-11-06T05:00:00Z' }, ahora);
  assert.equal(viejo.tono, 'aviso');
  assert.match(viejo.detalle, /vencido \(medido hace 9 h; máximo 6 h\)/);
  assert.equal(L.estadoInfra({ semaforo: 'ROJO', modo: 'vivo', generado_en: '2026-11-06T13:00:00Z' }, ahora).tono, 'error');
  assert.equal(L.estadoInfra({ semaforo: 'AMARILLO', modo: 'vivo', generado_en: 'basura' }, ahora).edadH, null);
  assert.equal(L.estadoInfra({ semaforo: 'VERDE', modo: 'vivo', generado_en: '2026-11-06T15:00:00Z' }, ahora).edadH, 0, 'una fecha futura no da edad negativa');
});

const AHORA = Date.parse('2026-11-06T14:30:00Z');

test('itemsAtencion: solo lo vigente, priorizado (crítico → aviso → info), una acción por ítem y nunca lo descartado por el dueño', () => {
  const sistema = cargarSobre('sistema').datos;
  const parametros = cargarSobre('parametros').datos;
  const alertas = L.alertasUnificadas({ registro: cargarSobre('registro').datos, finanzas: cargarSobre('finanzas').datos, limite: 8, ventanaH: 72, ahoraMs: AHORA });
  const a = L.itemsAtencion({ sistema, ofertas, parametros, alertas, cadenaOk: true, ahoraMs: AHORA });
  assert.deepEqual(a.map((x) => x.id), ['gate:OF-202611-03:D2', 'bloqueo:OF-202611-04', 'freno', 'limites', 'preflight', 'alertas', 'gates-demo']);
  const rango = { critico: 0, aviso: 1, info: 2 };
  assert.deepEqual(a.map((x) => rango[x.tono]), a.map((x) => rango[x.tono]).slice().sort(), 'orden por tono');
  assert.ok(a.every((x) => x.accion && x.accion.texto), 'cada ítem trae su única acción');
  const gate = a.find((x) => x.id === 'gate:OF-202611-03:D2');
  assert.equal(gate.titulo, 'Espera tu firma: Validar (D2) de OF-202611-03');
  assert.equal(gate.accion.tipo, 'firmar');
  assert.equal(gate.accion.gate.comando, '.venv/bin/python -m engine.orq firmar --oferta OF-202611-03 --etapa D2 --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno');
  assert.equal(a.find((x) => x.id === 'gates-demo').tono, 'info', 'la firma de la demo no es urgente');
  assert.equal(a.find((x) => x.id === 'freno').accion.texto, 'Revisar el freno');
  assert.match(a.find((x) => x.id === 'freno').detalle, /HTTP 403/);
  assert.equal(a.find((x) => x.id === 'limites').accion.ruta, '#/parametros');
  assert.match(a.find((x) => x.id === 'limites').titulo, /Faltan por fijar 3 límites/);
  assert.equal(a.find((x) => x.id === 'preflight').accion.tipo, 'preflight');
  // PAUSA y registro roto pasan por delante de todo
  const grave = L.itemsAtencion({ sistema: { ...sistema, pausa: { activa: true, desde: '2026-11-06T10:00:00Z', motivo: 'prueba' } }, ofertas: [], parametros: null, cadenaOk: false, ahoraMs: AHORA });
  assert.deepEqual(grave.slice(0, 2).map((x) => [x.id, x.tono]), [['pausa', 'critico'], ['cadena', 'critico']]);
  assert.match(grave[0].detalle, /prueba/);
  // decisiones 14 y 15 del dueño: no se listan como pendientes suyos
  const todo = JSON.stringify(L.itemsAtencion({ sistema: { ...sistema, infra: null }, ofertas, parametros: { limites: { nulos: ['a'] } }, ahoraMs: 0 }));
  assert.doesNotMatch(todo, /contrase|password|llave|2FA|segundo administrador|abogado|legal/i);
  assert.deepEqual(L.itemsAtencion({}), []);
  const sinInfra = L.itemsAtencion({ sistema: { pausa: { activa: false }, freno_captura: null, infra: null }, ofertas: [], ahoraMs: 0 });
  assert.equal(sinInfra[0].titulo, 'Falta el chequeo de cuentas y servicios');
  const rojo = L.itemsAtencion({ sistema: { pausa: { activa: false }, freno_captura: null, infra: { semaforo: 'ROJO', modo: 'vivo', generado_en: '2026-11-06T14:00:00Z' } }, ofertas: [], ahoraMs: AHORA });
  assert.deepEqual([rojo[0].id, rojo[0].tono], ['infra', 'critico']);
  // más firmas de las que caben: se resume el resto
  const muchas = Array.from({ length: 9 }, (_, i) => ({ oferta_id: `OF-202611-${String(i + 10).padStart(2, '0')}`, gates_pendientes: ['D1'], demo: false }));
  const m = L.itemsAtencion({ ofertas: muchas, maxGates: 6 });
  assert.equal(m.filter((x) => x.id.startsWith('gate:')).length, 6);
  assert.match(m.find((x) => x.id === 'gates-mas').titulo, /3 firmas más/);
});

test('alertasUnificadas con ventana: las del registro viejas ya no cuentan, las de finanzas abiertas sí', () => {
  const registro = cargarSobre('registro').datos;
  const fin = cargarSobre('finanzas').datos;
  const todas = L.alertasUnificadas({ registro, finanzas: fin, limite: 50 });
  const recientes = L.alertasUnificadas({ registro, finanzas: fin, limite: 50, ventanaH: 72, ahoraMs: AHORA });
  assert.equal(recientes.length, todas.length, 'en el escenario del fixture todas son de hoy');
  const futuro = L.alertasUnificadas({ registro, finanzas: fin, limite: 50, ventanaH: 72, ahoraMs: Date.parse('2027-01-01T00:00:00Z') });
  assert.ok(futuro.every((x) => x.fuente === 'finanzas'), 'pasado el tiempo solo quedan las abiertas de finanzas');
  assert.ok(futuro.length < todas.length);
});

test('textoPorFase, estadoPipeline y frasePipeline', () => {
  assert.equal(L.textoPorFase(ofertas), '1 en borrador · 1 en construcción · 1 en prueba', 'la demo no cuenta');
  assert.equal(L.textoPorFase([]), '');
  const p = L.estadoPipeline(ofertas[0]);
  assert.equal(p.etapas.length, 11);
  assert.deepEqual(p.actual, { etapa: 'D7', estado: 'en_QA' });
  assert.equal(p.espera, true);
  const d7 = p.etapas.find((e) => e.id === 'D7');
  assert.deepEqual([d7.nombre, d7.codigo, d7.estado, d7.seleccionada, d7.aviso], ['Campaña', 'D7', 'en_QA', true, 'Espera tu firma']);
  assert.equal(p.etapas.filter((e) => e.seleccionada).length, 1);
  assert.equal(L.frasePipeline(ofertas[0]), 'Campaña (D7) · en revisión de calidad — espera tu firma');
  assert.equal(L.frasePipeline(ofertas[1]), 'Operación (D8) · en progreso');
  assert.equal(L.frasePipeline(ofertas[3]), 'Mercado (M1) · bloqueada');
  assert.equal(L.frasePipeline({ etapas: { M1: 'aprobado' } }), 'Todas las etapas aprobadas');
  assert.equal(L.frasePipeline({}), 'Sin etapas todavía');
  assert.deepEqual(L.estadoPipeline(null).etapas, []);
});

test('dineroResumen y veredictoSistema', () => {
  assert.deepEqual(L.dineroResumen([]), { valor: null, extra: '' });
  assert.deepEqual(L.dineroResumen([{ moneda: 'EUR', monto: 4200 }, { moneda: 'PLN', monto: 0 }]), { valor: `42,00${NBSP}€`, extra: `0,00${NBSP}PLN` });
  const sis = cargarSobre('sistema').datos;
  assert.deepEqual([L.veredictoSistema({ sistema: null }).tono, L.veredictoSistema({ sistema: null }).texto], ['neutro', 'Sin datos']);
  assert.deepEqual([L.veredictoSistema({ sistema: sis, ahoraMs: AHORA }).tono, L.veredictoSistema({ sistema: sis, ahoraMs: AHORA }).texto], ['aviso', 'Revisar']);
  assert.equal(L.veredictoSistema({ sistema: { ...sis, pausa: { activa: true } }, ahoraMs: AHORA }).texto, 'En pausa');
  assert.equal(L.veredictoSistema({ sistema: { ...sis, freno_captura: null, infra: { semaforo: 'VERDE', modo: 'vivo', generado_en: '2026-11-06T14:00:00Z' } }, ahoraMs: AHORA }).texto, 'En orden');
  assert.equal(L.veredictoSistema({ sistema: { ...sis, freno_captura: null, infra: { semaforo: 'VERDE', modo: 'vivo', generado_en: '2026-11-06T14:00:00Z' } }, ahoraMs: AHORA, cadenaOk: false }).tono, 'error');
  assert.equal(L.veredictoSistema({ sistema: { ...sis, infra: { semaforo: 'ROJO', modo: 'vivo', generado_en: '2026-11-06T14:00:00Z' } }, ahoraMs: AHORA }).texto, 'En rojo');
});

test('metricasResumen: número grande con contexto; sin datos es «—» (null), nunca un 0 inventado', () => {
  const sistema = cargarSobre('sistema').datos;
  const alertas = L.alertasUnificadas({ registro: cargarSobre('registro').datos, finanzas: cargarSobre('finanzas').datos, limite: 8, ventanaH: 72, ahoraMs: AHORA });
  const m = Object.fromEntries(L.metricasResumen({ ofertas, sistema, alertas, ahoraMs: AHORA }).map((x) => [x.id, x]));
  assert.deepEqual(Object.keys(m), ['ofertas', 'firma', 'gasto', 'ia', 'alertas', 'sistema']);
  assert.equal(m.ofertas.valor, 3, 'la demo se aparta');
  assert.match(m.ofertas.contexto, /1 en borrador · 1 en construcción · 1 en prueba · más 1 de demostración/);
  assert.equal(m.firma.valor, 1);
  assert.equal(m.firma.tono, 'aviso');
  assert.match(m.firma.contexto, /Validar · OF-202611-03/);
  assert.equal(m.gasto.valor, `42,00${NBSP}€`);
  assert.match(m.gasto.contexto, new RegExp(`0,00${NBSP}PLN`));
  assert.match(m.gasto.contexto, /3 ofertas reales/);
  assert.equal(m.ia.valor, `9,03${NBSP}€`);
  assert.match(m.ia.contexto, new RegExp(`1,88${NBSP}US\\$`));
  assert.equal(m.alertas.valor, 5);
  assert.equal(m.alertas.tono, 'error');
  assert.deepEqual([m.sistema.valor, m.sistema.tono], ['Revisar', 'aviso']);
  const vacio = Object.fromEntries(L.metricasResumen({ ofertas: [], sistema: null, alertas: null, ahoraMs: AHORA }).map((x) => [x.id, x]));
  assert.equal(vacio.ofertas.valor, 0);
  assert.equal(vacio.ofertas.contexto, 'ninguna todavía');
  assert.equal(vacio.gasto.valor, null, 'sin ofertas: «—», nunca un 0 inventado');
  assert.equal(vacio.alertas.valor, null);
  assert.equal(vacio.sistema.valor, null);
  const caido = Object.fromEntries(L.metricasResumen({ ofertas: null, sistema, alertas: [], ahoraMs: AHORA }).map((x) => [x.id, x]));
  assert.equal(caido.ofertas.valor, null);
  assert.equal(caido.ofertas.contexto, 'sin datos');
  assert.equal(caido.alertas.tono, 'ok');
});

test('resumenDescubrimiento: toma la corrida más reciente y calcula el uso de consultas', () => {
  assert.equal(L.resumenDescubrimiento([]), null);
  assert.equal(L.resumenDescubrimiento(null), null);
  const r = L.resumenDescubrimiento([
    { corrida_id: '2026-11-05-a', consultas_ok: 10, consultas_tope: 120, actualizado_en: '2026-11-05T10:00:00Z', pasan_traccion: 1 },
    { corrida_id: '2026-11-06-a', consultas_ok: 98, consultas_tope: 120, paginas: 724, etiquetadas: 694, candidatas: 636, pasan_traccion: 13, pasan_traccion_temas: 11, pasan_traccion_sin_tema: 2, fichas: 13, actualizado_en: '2026-11-06T06:25:41Z' },
  ]);
  assert.equal(r.corrida_id, '2026-11-06-a');
  assert.equal(r.total, 2);
  assert.deepEqual([r.pasan_traccion, r.pasan_temas, r.pasan_sin_tema, r.fichas, r.pctConsultas], [13, 11, 2, 13, 82]);
  assert.equal(L.resumenDescubrimiento([{ corrida_id: 'x', consultas_ok: 5 }]).pctConsultas, null, 'sin tope no se inventa un porcentaje');
  assert.equal(L.resumenDescubrimiento([{ corrida_id: 'x', consultas_ok: 500, consultas_tope: 120 }]).pctConsultas, 100);
});

test('actividadReciente: los últimos eventos en lenguaje humano, el más reciente primero', () => {
  const lineas = cargarSobre('registro').datos.lineas;
  const a = L.actividadReciente(lineas, 3);
  assert.deepEqual(a.map((x) => x.linea.n), [21, 20, 19]);
  assert.match(a[2].vista.titulo, /^La etapa «Validar» pasó a «En /); // el nombre del estado lo define lib/registro.js (otro grupo)
  assert.equal(L.actividadReciente(null).length, 0);
  assert.equal(L.actividadReciente(lineas, 99).length, lineas.length);
});

test('faltantes: fuentes vacías y pantallas sin módulo', () => {
  const f = L.faltantes({ fuentes: { A: { vacio: true, fuente: ['x'], comando: 'c' }, B: { vacio: false }, C: null }, paginas: { landing: 'falta', registro: 'ok', skills: 'error' }, titulos: { landing: 'Página de venta' } });
  assert.deepEqual(f.datos, [{ tipo: 'dato', nombre: 'A', fuente: ['x'], comando: 'c' }]);
  assert.deepEqual(f.pantallas, [{ tipo: 'pantalla', nombre: 'Página de venta', ruta: 'landing' }]);
  assert.deepEqual(L.faltantes(), { datos: [], pantallas: [] });
});

// ───────────────────────── página ─────────────────────────

const { estado: estadoGlobal } = await import('../../dashboard/web/estado.js');
const corridas = { datos: [{ corrida_id: '2026-11-06-a', consultas_ok: 98, consultas_tope: 120, paginas: 724, etiquetadas: 694, candidatas: 636, pasan_traccion: 13, pasan_traccion_temas: 11, pasan_traccion_sin_tema: 2, fichas: 13, actualizado_en: '2026-11-06T06:25:41Z' }], fuente: ['empresa/barrido/planes'], generado_en: '2026-11-06T14:00:00Z', avisos: [], vacio: false };
const ctxDe = (api, extra = {}) => crearCtx({ api, ui, ruta: 'resumen', ...extra });
const apiLlena = (extra = {}) => crearApiFalsa({ '/descubrimiento/corridas': corridas, ...extra });
const metricas = (raiz) => Object.fromEntries(buscarTodos(buscar(raiz, '.u1r-metricas'), '.metrica').map((m) => [buscar(m, '.metrica__etiqueta').textContent, m]));

test('Resumen con datos: atención primero, métricas con contexto, ofertas con mini-pipeline, descubrimiento y actividad humana', async () => {
  const api = apiLlena();
  const ctx = ctxDe(api, { paginas: { landing: 'falta', registro: 'ok' }, titulos: { landing: 'Página de venta' }, estado: { ofertaActiva: 'OF-202611-02' } });
  const raiz = await pagina.render(ctx);
  const texto = raiz.textContent;
  assert.equal(buscar(raiz, 'h1').textContent, 'Resumen');
  // orden de la pantalla: atención → métricas → ofertas → descubrimiento → actividad → lo que falta
  const orden = ['Requiere tu atención', 'Ofertas', 'Cómo van tus ofertas', 'Radar de ofertas', 'Actividad reciente', 'Lo que falta por construir'].map((t) => texto.indexOf(t));
  assert.ok(orden.every((n) => n >= 0), `faltan bloques: ${orden}`);
  assert.deepEqual(orden, [...orden].sort((a, b) => a - b), 'jerarquía: lo que requiere atención va primero');

  // 1) atención: una acción por ítem, la firma abre «cómo firmar» con el comando exacto
  const atencion = buscar(raiz, '.atencion');
  const items = buscarTodos(atencion, '.atencion__item');
  assert.equal(items.length, 7);
  assert.ok(items.every((i) => buscarTodos(i, '.atencion__boton').length === 1), 'exactamente un botón por ítem');
  assert.match(items[0].textContent, /Espera tu firma: Validar \(D2\) de OF-202611-03/);
  assert.match(atencion.textContent, /Revisar el freno/);
  assert.match(atencion.textContent, /Abrir límites/);
  assert.match(atencion.textContent, /Ver cómo hacer el chequeo/);
  assert.equal(buscarTodos(atencion, 'a').find((a) => a.textContent.includes('Abrir límites')).getAttribute('href'), '#/parametros');
  buscarTodos(items[0], 'button')[0].click();
  const modal = buscar(doc.body, '.modal');
  assert.ok(modal, 'se abre el modal «cómo firmar»');
  assert.match(modal.textContent, /Cómo firmar: Validar \(D2\) de OF-202611-03/);
  assert.equal(buscar(modal, '.comando__texto').textContent, '.venv/bin/python -m engine.orq firmar --oferta OF-202611-03 --etapa D2 --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno');
  assert.match(modal.textContent, /sistema automático todavía no está construido/, 'avisa si el sistema automático no está disponible');
  ui.cerrarModales();

  // 2) métricas
  const m = metricas(raiz);
  assert.deepEqual(Object.keys(m), ['Ofertas', 'Esperan tu firma', 'Gasto de hoy', 'Costo de IA', 'Alertas', 'Estado del sistema']);
  assert.equal(buscar(m['Ofertas'], '.metrica__valor').textContent, '3', 'cuenta solo las reales: la demo se aparta');
  assert.match(m['Ofertas'].textContent, /1 en borrador · 1 en construcción · 1 en prueba · más 1 de demostración/);
  assert.equal(buscar(m['Esperan tu firma'], '.metrica__valor').textContent, '1');
  assert.match(m['Gasto de hoy'].textContent, new RegExp(`42,00${NBSP}€`));
  assert.match(m['Gasto de hoy'].textContent, new RegExp(`0,00${NBSP}PLN`));
  assert.match(m['Costo de IA'].textContent, new RegExp(`9,03${NBSP}€`));
  assert.match(m['Costo de IA'].textContent, new RegExp(`1,88${NBSP}US\\$`));
  assert.equal(buscar(m['Estado del sistema'], '.metrica__valor').textContent, 'Revisar');
  assert.equal(m['Ofertas'].getAttribute('href'), '#/ofertas');

  // 3) ofertas: tarjeta con mini-pipeline de 11 etapas, la etapa actual y la que espera tu firma
  const tarj = buscarTodos(raiz, '.u1r-oferta');
  assert.equal(tarj.length, 4);
  const demo = tarj.find((t) => t.getAttribute('href') === '#/oferta/_ejemplo');
  assert.ok(demo, 'el enlace usa el nombre de carpeta');
  assert.equal(buscarTodos(demo, '.u1r-pipe li').length, 11);
  assert.equal(buscarTodos(demo, '.u1r-pipe li[data-actual="1"]').length, 1);
  assert.equal(buscar(demo, '.u1r-pipe li[data-firma="1"]').textContent, 'D7');
  assert.match(demo.textContent, /Campaña \(D7\) · en revisión de calidad — espera tu firma/);
  assert.match(demo.textContent, /7 de 11 etapas aprobadas/);
  assert.match(raiz.textContent, /estado\.json con 1 etapa sin versión aprobada/, 'el aviso del servidor por oferta se muestra');
  assert.equal(tarj.find((t) => t.textContent.includes('OF-202611-02')).getAttribute('aria-current'), 'true');
  assert.equal(buscar(tarj.find((t) => t.textContent.includes('OF-202611-04')), '.u1r-pipe li[data-estado="bloqueado"]').textContent, 'M1');
  assert.deepEqual(buscarTodos(raiz, '.u1r-fase__cab').map((f) => buscar(f, '.chip').dataset.estado), ['borrador', 'en_construccion', 'en_test']);

  // 4) descubrimiento
  const des = buscarTodos(raiz, '.seccion').find((x) => buscar(x, '.seccion__titulo').textContent === 'Radar de ofertas');
  assert.match(des.textContent, /Candidatos que pasan tracción/);
  assert.equal(buscar(buscarTodos(des, '.metrica')[0], '.metrica__valor').textContent, '13');
  assert.match(des.textContent, /98 \/ 120/);
  assert.match(des.textContent, /82 % del máximo/);
  assert.match(des.textContent, /La captura de anuncios está frenada/);
  assert.match(des.textContent, /2026-11-06-a/);

  // 5) actividad: frases humanas; el evento técnico queda en detalle técnico (21 líneas → 8 frases + tabla de 15)
  const act = buscarTodos(raiz, '.seccion').find((x) => buscar(x, '.seccion__titulo').textContent === 'Actividad reciente');
  const evs = buscarTodos(act, '.u1r-ev');
  assert.equal(evs.length, 8);
  assert.match(evs[0].textContent, /Subir presupuesto 24 → 28 EUR/);
  assert.match(act.textContent, /La etapa «Validar» pasó a «En /);
  assert.match(act.textContent, /Historial sin alteraciones/);
  const tec = buscar(act, '.detalle-tecnico');
  assert.ok(tec, 'el evento técnico va en detalle técnico');
  assert.equal(tec.hasAttribute('open'), false, 'cerrado con el modo técnico apagado');
  tec.open = true; tec.montar();
  assert.equal(buscarTodos(tec, 'tbody tr').length, 15);
  assert.equal(buscarTodos(tec, 'tbody tr')[0].querySelectorAll('td')[0].textContent, '21');

  // pantallas por construir y nunca firma ni pausa por sí mismo
  assert.ok(buscarTodos(raiz, '.seccion').some((x) => x.textContent.includes('Pantallas en construcción') && x.textContent.includes('Página de venta')));
  assert.equal(api.postsA('/pausa').length + api.postsA('/accion').length, 0);
  // nada descartado por el dueño
  assert.doesNotMatch(texto, /contrase|llave|2FA|segundo administrador|abogado/i);
});

test('Resumen: sin jerga cruda en primer plano (rutas, comandos y hashes están cerrados o fuera de la vista)', async () => {
  const raiz = await pagina.render(ctxDe(apiLlena()));
  // todo comando está dentro de un bloque cerrado «Cómo hacerlo»/«detalle técnico» (o de un modal), nunca suelto
  for (const c of buscarTodos(raiz, '.comando')) assert.ok(c.closest('details') === c, 'el comando es un <details>');
  assert.equal(buscarTodos(raiz, '.comando[open]').length, 0);
  for (const nodo of buscarTodos(raiz, 'h2, h3, strong')) assert.doesNotMatch(nodo.textContent, /\.json|\.jsonl|\.yaml|empresa\/|ofertas\//, `ruta en un título: ${nodo.textContent}`);
  assert.ok(buscarTodos(raiz, '.fuente').length >= 3, 'las fuentes van en el icono «i», no en línea');
});

test('Resumen con el modo técnico encendido: todo lo técnico queda abierto y disponible', async () => {
  estadoGlobal.fijar({ modoTecnico: true });
  try {
    const raiz = await pagina.render(ctxDe(apiLlena()));
    const act = buscarTodos(raiz, '.seccion').find((x) => buscar(x, '.seccion__titulo').textContent === 'Actividad reciente');
    const tec = buscar(act, '.detalle-tecnico');
    assert.equal(tec.hasAttribute('open'), true);
    assert.equal(buscarTodos(tec, 'tbody tr').length, 15, 'la tabla técnica está montada y abierta');
  } finally { estadoGlobal.fijar({ modoTecnico: false }); }
});

test('Resumen: el texto hostil del registro se muestra como texto (sin nodos <script> ni <img>)', async () => {
  const raiz = await pagina.render(ctxDe(apiLlena()));
  assert.equal(buscarTodos(raiz, 'script').length, 0);
  assert.equal(buscarTodos(raiz, 'img').length, 0);
  assert.ok(raiz.textContent.includes('<script>alert(1)</script>'));
  assert.ok(raiz.textContent.includes('⟦U+202E⟧'), 'el carácter bidi se hace visible');
  assert.ok(!raiz.textContent.includes('‮'));
});

test('Resumen sin ofertas, registro ni barrido: estados vacíos con pasos y el comando exacto', async () => {
  const api = crearApiFalsa({
    '/ofertas': cargarSobre('ofertas_vacio'), '/registro': cargarSobre('registro_vacio'), '/finanzas': cargarSobre('finanzas_vacio'), '/descubrimiento/corridas': { datos: [] },
    '/sistema': { ...cargarSobre('sistema'), datos: { ...cargarSobre('sistema').datos, infra: null, freno_captura: null, modo_demo: false } },
  });
  const raiz = await pagina.render(ctxDe(api));
  const texto = raiz.textContent;
  assert.match(texto, /Todavía no hay ofertas/);
  assert.match(texto, /Todavía no hay ningún barrido/);
  assert.match(texto, /El historial aún no tiene actividad/);
  assert.ok(buscarTodos(raiz, '.vacio-pasos').length >= 3, 'estados vacíos con pasos');
  const cmds = buscarTodos(raiz, '.comando__texto').map((c) => c.textContent);
  assert.ok(cmds.some((c) => c.startsWith('.venv/bin/python -m engine.orq crear --brief')), cmds.join('|'));
  assert.ok(cmds.some((c) => c.includes('infra.preflight')));
  assert.ok(cmds.some((c) => c.includes('scripts.modelado.barrido plan generar')));
  assert.match(texto, /Falta el chequeo de cuentas y servicios/);
  const m = metricas(raiz);
  assert.equal(buscar(m['Ofertas'], '.metrica__valor').textContent, '0');
  assert.equal(buscar(m['Gasto de hoy'], '.metrica__valor').textContent, '—', 'sin ofertas: «—», nunca un 0 inventado');
  assert.deepEqual(buscarTodos(raiz, '.atencion__item').map((i) => i.textContent.replace(/\s+/g, ' ').slice(0, 30)), ['Faltan por fijar 3 límites de ', 'Falta el chequeo de cuentas y ']);
  // sin nada pendiente, la atención lo dice
  const limpia = await pagina.render(ctxDe(crearApiFalsa({ '/ofertas': cargarSobre('ofertas_vacio'), '/registro': cargarSobre('registro_vacio'), '/finanzas': cargarSobre('finanzas_vacio'), '/descubrimiento/corridas': { datos: [] },
    '/sistema': { ...cargarSobre('sistema'), datos: { ...cargarSobre('sistema').datos, freno_captura: null, infra: { semaforo: 'VERDE', modo: 'vivo', generado_en: new Date().toISOString() }, modo_demo: false } },
    '/parametros': { ...cargarSobre('parametros'), datos: { ...cargarSobre('parametros').datos, limites: { valores: {}, nulos: [] } } } })));
  assert.match(buscar(limpia, '.atencion').textContent, /Nada requiere tu atención ahora/);
});

test('Resumen: error de API → errorBox con reintento; un endpoint secundario caído no rompe la pantalla', async () => {
  const caido = new ErrorApiFalso('sin_conexion', 'No se pudo conectar');
  const raiz = await pagina.render(ctxDe(apiLlena({ '/sistema': caido, '/ofertas': caido })));
  assert.equal(buscarTodos(raiz, '[role="alert"]').length >= 1, true);
  assert.match(raiz.textContent, /sin_conexion/);
  const ctx = ctxDe(apiLlena({ '/sistema': caido, '/ofertas': caido }));
  const r2 = await pagina.render(ctx);
  buscar(r2, '.error-box button').click();
  assert.deepEqual(ctx._navegaciones, ['recargar']);
  // solo registro, finanzas, parámetros y barrido caídos
  const parcial = await pagina.render(ctxDe(apiLlena({ '/registro': caido, '/finanzas': caido, '/parametros': caido, '/descubrimiento/corridas': caido })));
  assert.match(parcial.textContent, /Cómo van tus ofertas/);
  assert.match(parcial.textContent, /sin_conexion/, 'el bloque afectado muestra su propio error');
  assert.ok(buscarTodos(parcial, '.u1r-oferta').length === 4);
  // sistema caído pero ofertas bien
  const sinSis = await pagina.render(ctxDe(apiLlena({ '/sistema': caido })));
  assert.equal(buscarTodos(sinSis, '.u1r-oferta').length, 4);
  assert.equal(buscar(metricas(sinSis)['Estado del sistema'], '.metrica__valor').textContent, '—');
});

test('Resumen: PAUSA activa es lo más urgente y se ve en la atención y en la métrica del sistema', async () => {
  const sis = cargarSobre('sistema');
  const api = apiLlena({ '/sistema': { ...sis, datos: { ...sis.datos, pausa: { activa: true, desde: '2026-11-06T10:00:00Z', motivo: 'revisar gasto' } } } });
  const raiz = await pagina.render(ctxDe(api));
  const primero = buscarTodos(raiz, '.atencion__item')[0];
  assert.match(primero.textContent, /La fábrica está en pausa/);
  assert.match(primero.textContent, /revisar gasto/);
  assert.match(primero.className, /atencion__item--critico/);
  const m = buscar(metricas(raiz)['Estado del sistema'], '.metrica__valor');
  assert.equal(m.textContent, 'En pausa');
  assert.match(metricas(raiz)['Estado del sistema'].className, /metrica--error/);
});

test('Resumen: «Ver cómo hacer el chequeo» abre el comando exacto', async () => {
  const raiz = await pagina.render(ctxDe(apiLlena()));
  const item = buscarTodos(raiz, '.atencion__item').find((i) => i.textContent.includes('Ver cómo hacer el chequeo'));
  buscarTodos(item, 'button')[0].click();
  const modal = buscar(doc.body, '.modal');
  assert.equal(buscar(modal, '.comando__texto').textContent, L.COMANDO_PREFLIGHT);
  ui.cerrarModales();
});

test('Resumen: meta de página (ruta, grupo, escucha)', () => {
  assert.deepEqual([pagina.meta.ruta, pagina.meta.grupo, pagina.meta.titulo], ['resumen', 'El sistema', 'Resumen']);
  assert.ok(pagina.meta.escucha.includes('registro'));
});

test('nulosQueBloquean: las claves de riesgo 1.3.0 en null («solo verde») no cuentan como límites que bloquean', () => {
  assert.equal(L.nulosQueBloquean(null), null);
  assert.equal(L.nulosQueBloquean({}), null);
  assert.deepEqual(L.nulosQueBloquean({ limites: { nulos: ['a', 'nivel_max_lanzable', 'sello'], nulos_solo_verde: ['nivel_max_lanzable'] } }), ['a', 'sello']);
  assert.deepEqual(L.nulosQueBloquean({ limites: { nulos: ['a', 'b'] } }), ['a', 'b'], 'sin la lista del servidor se cuentan todas (no se esconde nada)');
  const sistema = { pausa: { activa: false }, freno_captura: null, infra: { semaforo: 'VERDE', generado_en: '2026-11-09T11:00:00Z', valido_hasta: '2026-11-09T17:00:00Z' } };
  const solo = L.itemsAtencion({ sistema, ofertas: [], parametros: { limites: { nulos: ['nivel_max_lanzable'], nulos_solo_verde: ['nivel_max_lanzable'] } }, ahoraMs: Date.parse('2026-11-09T12:00:00Z') });
  assert.ok(!JSON.stringify(solo).includes('límites de seguridad'), 'solo claves «solo verde»: no se pide fijar límites');
  const con = L.itemsAtencion({ sistema, ofertas: [], parametros: { limites: { nulos: ['gasto_diario_global', 'nivel_max_lanzable'], nulos_solo_verde: ['nivel_max_lanzable'] } }, ahoraMs: Date.parse('2026-11-09T12:00:00Z') });
  assert.match(JSON.stringify(con), /Faltan por fijar 1 límite de seguridad/);
});

// ───────────────────────── N1: «La rueda: los 9 pasos de cada día» ─────────────────────────

const { readFileSync: leerArchivo } = await import('node:fs');
const { fileURLToPath: aRuta } = await import('node:url');
const PU = await import('../../dashboard/web/lib/pulido.js');
const RB = await import('../../dashboard/web/lib/robots.js');
const fxN1 = (carpeta, n) => JSON.parse(leerArchivo(aRuta(new URL(`../fixtures/dashboard/${carpeta}/${n}`, import.meta.url)), 'utf8'));
const bitacora = PU.normalizarEntradas(fxN1('pulido', 'bitacora.json').datos);
const detalleEjemplo = fxN1('oferta', 'oferta_ejemplo.json').datos;
const creativos = (n, estado = 'aprobado') => ({ etapas: [{ id: 'D6', estado, artefactos: [...Array.from({ length: n }, (_, i) => ({ ruta: `06-creativos/assets/c${i}.png`, tipo: 'imagen' })), { ruta: '06-creativos/paquete.json', tipo: 'json' }, { ruta: '07-campana/campana.json', tipo: 'json' }] }] });
const of = (id, fase, extra = {}) => ({ oferta_id: id, fase, demo: false, etapas: { D6: 'aprobado' }, ...extra });
const paso = (pasos, id) => pasos.find((p) => p.id === id);

test('rueda: los 9 pasos de know-how §0, en orden, con su pantalla; del 9 se vuelve al 1', () => {
  assert.deepEqual(L.PASOS_RUEDA.map((p) => [p.n, p.titulo]), [
    [1, 'El cerebro recuerda'], [2, 'La fábrica hace los anuncios'], [3, 'El jurado elige los mejores'], [4, 'Se prueban con poca plata'], [5, 'El que vende se agranda'],
    [6, 'Los robots trabajan 24 h'], [7, 'Un auditor controla'], [8, 'El ganador viaja a otro país'], [9, 'Lo aprendido vuelve al cerebro'],
  ]);
  assert.ok(L.PASOS_RUEDA.every((p) => /^#\//.test(p.ruta) && p.verbo));
  assert.equal(L.PASOS_RUEDA[3].ruta, '#/campanas');
  assert.equal(L.PASOS_RUEDA[5].ruta, '#/robots');
  const vacia = L.pasosRueda({});
  assert.equal(vacia.length, 9);
  assert.deepEqual(vacia.map((p) => p.n), [1, 2, 3, 4, 5, 6, 7, 8, 9]);
});

test('rueda: paso 1 (cerebro) y paso 9 (lo aprendido) salen de la lista de Mejoras pendientes', () => {
  const p = L.pasosRueda({ pulido: bitacora });
  assert.deepEqual([paso(p, 'cerebro').estado, paso(p, 'cerebro').tono, paso(p, 'cerebro').etiqueta], ['aviso', 'aviso', 'Requiere atención']);
  assert.equal(paso(p, 'cerebro').dato, '4 pendientes abiertos (2 de gravedad alta).');
  assert.match(paso(p, 'cerebro').nota, /cerebro completo .* aún no existe/);
  assert.deepEqual([paso(p, 'aprende').estado, paso(p, 'aprende').dato], ['ok', '1 lección o corrección ya resuelta de 5 en Mejoras pendientes.']);
  const sinAltas = L.pasosRueda({ pulido: PU.normalizarEntradas([{ id: 'PUL-0001', titulo: 'a', severidad: 'baja', estado: 'abierta' }]) });
  assert.deepEqual([paso(sinAltas, 'cerebro').estado, paso(sinAltas, 'cerebro').dato], ['ok', '1 pendiente abierto.']);
  assert.equal(paso(sinAltas, 'aprende').estado, 'sin_datos', 'sin nada resuelto no hay «lo aprendido»');
  const todoResuelto = L.pasosRueda({ pulido: PU.normalizarEntradas([{ id: 'PUL-0001', titulo: 'a', estado: 'resuelta' }]) });
  assert.match(paso(todoResuelto, 'cerebro').dato, /Sin pendientes abiertos \(1 resuelto\)/);
  const vacia = L.pasosRueda({ pulido: [] });
  assert.deepEqual([paso(vacia, 'cerebro').estado, paso(vacia, 'cerebro').dato], ['sin_datos', 'La lista de pendientes está vacía.']);
  assert.deepEqual([paso(L.pasosRueda({ pulido: null }), 'cerebro').estado, paso(L.pasosRueda({ pulido: null }), 'cerebro').dato], ['sin_datos', 'No se pudo leer la lista de pendientes.']);
});

test('rueda: paso 2 (fábrica) cuenta piezas por oferta REAL; la demo no cuenta y lo que no se pudo contar no se afirma como 0', () => {
  const ofertas = [of('OF-202611-02', 'en_test'), of('OF-202611-03', 'en_construccion'), of('OF-202611-04', 'borrador', { etapas: { D6: 'pendiente' } }), of('_ejemplo', 'en_construccion', { demo: true })];
  const p = paso(L.pasosRueda({ ofertas, detalles: { 'OF-202611-02': creativos(8), 'OF-202611-03': creativos(2), _ejemplo: creativos(6) } }), 'fabrica');
  assert.deepEqual([p.estado, p.dato], ['ok', 'OF-202611-02: 8 piezas · OF-202611-03: 2 piezas.']);
  assert.match(p.nota, /demostración tiene 6 piezas, pero no cuenta/);
  const una = paso(L.pasosRueda({ ofertas, detalles: { 'OF-202611-02': creativos(1), 'OF-202611-03': null } }), 'fabrica');
  assert.equal(una.dato, 'OF-202611-02: 1 pieza.');
  assert.match(una.nota, /No se pudieron contar las piezas de 1 oferta/);
  const solodemo = paso(L.pasosRueda({ ofertas, detalles: { _ejemplo: creativos(6), 'OF-202611-02': creativos(0), 'OF-202611-03': creativos(0) } }), 'fabrica');
  assert.deepEqual([solodemo.estado, solodemo.dato], ['sin_datos', 'Ninguna oferta real tiene piezas de anuncios todavía.']);
  assert.match(solodemo.nota, /demostración tiene 6 piezas/);
  const sinContar = paso(L.pasosRueda({ ofertas, detalles: {} }), 'fabrica');
  assert.equal(sinContar.estado, 'sin_datos');
  assert.match(sinContar.dato, /No se pudieron contar las piezas de 2 ofertas: OF-202611-02 · OF-202611-03/, 'D6 pendiente = 0 seguro; lo demás, no se sabe');
  assert.equal(paso(L.pasosRueda({ ofertas: [] }), 'fabrica').dato, 'Todavía no hay ofertas reales.');
  assert.equal(paso(L.pasosRueda({ ofertas: null }), 'fabrica').dato, 'No se pudo leer la lista de ofertas.');
  const bloqueada = paso(L.pasosRueda({ ofertas: [of('OF-202611-02', 'en_test')], detalles: { 'OF-202611-02': creativos(4, 'bloqueado') } }), 'fabrica');
  assert.equal(bloqueada.estado, 'aviso');
  assert.equal(L.piezasDeCreativos(detalleEjemplo).piezas, 6, 'el detalle real del fixture: 6 imágenes en assets');
  assert.deepEqual(L.piezasDeCreativos({ etapas: [{ id: 'D5' }] }), null);
  assert.equal(L.piezasDeCreativos(null), null);
  assert.deepEqual(L.ofertasConCreativos([of('A', 'x'), of('B', 'x', { etapas: { D6: 'pendiente' } }), of('C', 'x', { etapas: {} }), of('D', 'x', { etapas: { D6: { estado: 'en_QA' } } }), null]), ['A', 'D']);
  assert.equal(L.ofertasConCreativos(Array.from({ length: 30 }, (_, i) => of(`OF-${i}`, 'x'))).length, 12, 'tope para no saturar la API');
});

test('rueda: pasos 4 y 5 cuentan campañas en prueba y ofertas en escala (solo reales)', () => {
  const ofertas = [of('OF-202611-02', 'en_test'), of('OF-202611-03', 'escalando'), of('OF-202611-05', 'escalando'), of('OF-202611-06', 'listo_para_activar'), of('_ejemplo', 'en_test', { demo: true })];
  const p = L.pasosRueda({ ofertas });
  assert.deepEqual([paso(p, 'prueba').estado, paso(p, 'prueba').dato, paso(p, 'prueba').nota], ['ok', '1 campaña en prueba: OF-202611-02.', 'Además, 1 lista para activar.']);
  assert.deepEqual([paso(p, 'escala').estado, paso(p, 'escala').dato], ['ok', '2 ofertas en escala: OF-202611-03 · OF-202611-05.']);
  const nada = L.pasosRueda({ ofertas: [of('_ejemplo', 'en_test', { demo: true })] });
  assert.deepEqual([paso(nada, 'prueba').estado, paso(nada, 'prueba').dato], ['sin_datos', 'Ninguna campaña en prueba todavía.'], 'la demo no cuenta');
  assert.equal(paso(nada, 'escala').dato, 'Ninguna oferta en escala todavía.');
  const lista = paso(L.pasosRueda({ ofertas: [of('OF-202611-06', 'listo_para_activar')] }), 'prueba');
  assert.deepEqual([lista.estado, lista.dato], ['aviso', 'Ninguna campaña en prueba todavía. 1 oferta lista para activar: OF-202611-06.']);
  assert.equal(paso(L.pasosRueda({ ofertas: null }), 'prueba').estado, 'sin_datos');
});

test('rueda: pasos 6 y 7 salen del registro de robots; sin registro, «sin datos todavía» y qué lo producirá', () => {
  const sin = L.pasosRueda({});
  assert.deepEqual([paso(sin, 'robots').estado, paso(sin, 'robots').dato], ['sin_datos', 'Aún no hay registro de robots.']);
  assert.match(paso(sin, 'robots').nota, /sistema de robots/);
  assert.equal(paso(sin, 'auditor').estado, 'sin_datos');
  assert.match(paso(sin, 'auditor').nota, /Lo producirá el auditor de resultados/);
  const ahoraMs = Date.parse('2026-11-06T14:30:00Z');
  const reg = RB.normalizarRegistro([{ id: 'escalera', estado: 'vivo', ultimo_latido: '2026-11-06T14:20:00Z', latido_max_min: 45 }, { id: 'cola', estado: 'sombra' }, { id: 'auditor', estado: 'sombra', acierto_bp: 7300 }]);
  const con = L.pasosRueda({ robots: reg, ahoraMs });
  assert.deepEqual([paso(con, 'robots').estado, paso(con, 'robots').dato], ['ok', '3 robots registrados · 1 en vivo · 2 en sombra (miran sin actuar) · 0 apagados.']);
  assert.deepEqual([paso(con, 'auditor').estado, paso(con, 'auditor').dato], ['ok', `Acierto medido: 73${' '}%.`]);
  const caido = L.pasosRueda({ robots: RB.normalizarRegistro([{ id: 'escalera', estado: 'vivo', ultimo_latido: '2026-11-06T10:00:00Z', latido_max_min: 45 }]), ahoraMs });
  assert.deepEqual([paso(caido, 'robots').estado, paso(caido, 'robots').nota], ['aviso', '1 robot sin señal de vida reciente.']);
  const sinAcierto = L.pasosRueda({ robots: RB.normalizarRegistro([{ id: 'auditor', estado: 'vivo' }]), ahoraMs });
  assert.deepEqual([paso(sinAcierto, 'auditor').estado, paso(sinAcierto, 'auditor').dato], ['sin_datos', 'El auditor está registrado, pero aún no mide acierto.'], 'registrado sin acierto no es 0 %');
});

test('rueda: jurado (3) y país (8) siempre «sin datos todavía» hasta que existan sus archivos; ningún paso inventa un número', () => {
  const p = L.pasosRueda({ pulido: bitacora, ofertas: [of('OF-202611-02', 'escalando', { familia_id: 'F1' }), of('OF-202611-03', 'escalando', { familia_id: 'F1' })] });
  for (const id of ['jurado', 'pais']) {
    assert.equal(paso(p, id).estado, 'sin_datos', id);
    assert.equal(paso(p, id).etiqueta, 'Sin datos todavía');
    assert.match(paso(p, id).nota, /Lo producirá/);
    assert.doesNotMatch(paso(p, id).dato, /\d/, `${id}: sin cifras`);
  }
  assert.match(paso(p, 'jurado').dato, /todavía no existe/);
  const vacio = L.pasosRueda({});
  assert.ok(vacio.every((x) => ['ok', 'aviso', 'sin_datos'].includes(x.estado) && x.tono && x.icono && x.etiqueta && x.dato));
  assert.deepEqual(L.resumenRueda(p), { ok: 2, aviso: 1, sin_datos: 6, total: 9 });
  assert.deepEqual(L.resumenRueda(null), { ok: 0, aviso: 0, sin_datos: 0, total: 0 });
  assert.deepEqual(L.infoEstadoRueda('inventado'), L.infoEstadoRueda('sin_datos'));
});

test('rueda: cada paso enlaza a su pantalla; si el shell dice que aún no existe, a la alternativa de hoy', () => {
  const p = L.pasosRueda({});
  assert.deepEqual(p.map((x) => x.ruta), ['#/cerebro', '#/fabrica', '#/jurado', '#/campanas', '#/operacion', '#/robots', '#/robots?vista=reglas', '#/paises', '#/cerebro']);
  const falta = L.pasosRueda({ paginas: { cerebro: 'falta', fabrica: 'falta', jurado: 'error', paises: 'falta', robots: 'ok', campanas: 'ok' } });
  assert.deepEqual(falta.map((x) => x.ruta), ['#/pulido', '#/ofertas', '#/ofertas', '#/campanas', '#/operacion', '#/robots', '#/robots?vista=reglas', '#/ofertas', '#/pulido']);
  assert.equal(L.rutaDelPaso({ ruta: '#/x', alternativa: null }, { x: 'falta' }), '#/x', 'sin alternativa se mantiene (el shell avisa que está en construcción)');
  assert.equal(L.rutaDelPaso({ ruta: '#/robots?vista=reglas', alternativa: '#/sistema' }, { robots: 'falta' }), '#/sistema');
});

const apiRueda = (extra = {}) => apiLlena({
  '/pulido': fxN1('pulido', 'bitacora.json'),
  '/oferta/OF-202611-02': { datos: creativos(8), fuente: [], generado_en: null },
  '/oferta/OF-202611-03': { datos: creativos(0, 'pendiente'), fuente: [], generado_en: null },
  '/oferta/_ejemplo': { datos: detalleEjemplo, fuente: [], generado_en: null },
  '/robots': { datos: { robots: [{ id: 'escalera', estado: 'sombra', nivel: 'N1' }] }, fuente: ['empresa/robots.yaml'], generado_en: null, vacio: false },
  ...extra,
});

test('Resumen = «La rueda»: los 9 pasos justo debajo de «Requiere tu atención», cada uno con estado real, dato y enlace', async () => {
  const api = apiRueda();
  const ctx = ctxDe(api, { paginas: { cerebro: 'falta', robots: 'ok' } });
  const raiz = await pagina.render(ctx);
  const texto = raiz.textContent;
  // orden: atención → rueda → métricas → ofertas
  const orden = ['Requiere tu atención', 'La rueda: los 9 pasos de cada día', 'Estado del sistema', 'Cómo van tus ofertas'].map((t) => texto.indexOf(t));
  assert.ok(orden.every((n) => n >= 0), `faltan bloques: ${orden}`);
  assert.deepEqual(orden, [...orden].sort((a, b) => a - b), 'la rueda va justo debajo de lo que requiere tu atención');
  const hijos = raiz.children;
  const iAt = hijos.findIndex((h) => h.className.includes('atencion'));
  assert.match(hijos[iAt + 1].textContent, /La rueda: los 9 pasos de cada día/, 'inmediatamente debajo de la atención');
  // 9 tarjetas, en orden, con enlace y chip de estado
  const tarjetas = buscarTodos(raiz, 'a.n1-paso');
  assert.equal(tarjetas.length, 9);
  assert.deepEqual(tarjetas.map((t) => t.getAttribute('data-paso')), ['1', '2', '3', '4', '5', '6', '7', '8', '9']);
  assert.deepEqual(tarjetas.map((t) => t.getAttribute('href')), ['#/pulido', '#/fabrica', '#/jurado', '#/campanas', '#/operacion', '#/robots', '#/robots?vista=reglas', '#/paises', '#/pulido'], 'el cerebro aún no tiene pantalla: enlaza a Pulido');
  assert.ok(tarjetas.every((t) => buscar(t, '.chip') && buscarTodos(t, 'button').length === 0 && buscar(t, '.n1-paso__dato').textContent.length > 0));
  const por = (n) => tarjetas[n - 1];
  assert.deepEqual(['1', '2', '3', '4', '5', '6', '7', '8', '9'].map((n) => por(n).getAttribute('data-estado')), ['aviso', 'ok', 'sin_datos', 'ok', 'sin_datos', 'ok', 'sin_datos', 'sin_datos', 'ok']);
  assert.match(por(1).textContent, /4 pendientes abiertos \(2 de gravedad alta\)/);
  assert.match(por(2).textContent, /OF-202611-02: 8 piezas/);
  assert.doesNotMatch(buscar(por(2), '.n1-paso__dato').textContent, /OF-202611-03/, 'D6 pendiente = sin piezas, no se lista');
  assert.match(por(2).textContent, /demostración tiene 6 piezas, pero no cuenta/);
  assert.match(por(3).textContent, /Sin datos todavía/);
  assert.match(por(4).textContent, /1 campaña en prueba: OF-202611-02/);
  assert.match(por(5).textContent, /Ninguna oferta en escala todavía/);
  assert.match(por(6).textContent, /1 robot registrado · 0 en vivo · 1 en sombra \(miran sin actuar\) · 0 apagados/);
  assert.match(por(7).textContent, /El auditor está registrado|No hay ningún auditor/);
  assert.match(por(8).textContent, /Lo producirá la ruta de familia/);
  assert.match(por(9).textContent, /1 lección o corrección ya resuelta de 5/);
  // cabecera de la rueda: cuenta por estado y tira de 9 puntos
  assert.match(buscar(raiz, '.n1-rueda-cuenta').textContent, /4 en marcha.*1 requieren atención.*4 sin datos todavía/);
  assert.equal(buscarTodos(raiz, '.n1-tira li').length, 9);
  assert.match(raiz.textContent, /Del paso 9 se vuelve al paso 1, todos los días/);
  // las llamadas extra son de solo lectura y solo para lo que hace falta
  const rutas = api.llamadas.map((l) => l.ruta);
  assert.ok(rutas.includes('/pulido') && rutas.includes('/robots'));
  assert.deepEqual(rutas.filter((r) => r.startsWith('/oferta/')).sort(), ['/oferta/OF-202611-02', '/oferta/_ejemplo'], 'solo las ofertas cuya etapa de creativos ya avanzó');
  assert.equal(api.llamadas.filter((l) => l.metodo === 'POST').length, 0);
  assert.equal(api.postsA('/pausa').length + api.postsA('/accion').length, 0);
});

test('Resumen: la rueda sin datos extra (sin pulido, detalle ni robots) sigue mostrando los 9 pasos sin inventar nada', async () => {
  const raiz = await pagina.render(ctxDe(apiLlena()));
  const tarjetas = buscarTodos(raiz, 'a.n1-paso');
  assert.equal(tarjetas.length, 9);
  assert.match(tarjetas[0].textContent, /No se pudo leer la lista de pendientes/);
  assert.match(tarjetas[1].textContent, /No se pudieron contar las piezas de 1 oferta: OF-202611-02/);
  assert.match(tarjetas[5].textContent, /Aún no hay registro de robots/);
  assert.equal(buscarTodos(raiz, 'a.n1-paso[data-estado="ok"]').length, 1, 'solo el paso 4 tiene un dato real (la campaña en prueba)');
  // el resto de la pantalla no cambia: ofertas, descubrimiento, actividad
  assert.equal(buscarTodos(raiz, '.u1r-oferta').length, 4);
  assert.match(raiz.textContent, /Lo que falta por construir/);
});

test('Resumen: la rueda respeta el modo seguro (sin botones, sin comandos sueltos, texto hostil como texto)', async () => {
  const hostil = { ...fxN1('pulido', 'bitacora.json'), datos: { entradas: [{ id: 'PUL-0001', titulo: '<script>alert(1)</script>‮', detalle: '<img src=x>', severidad: 'alta', estado: 'abierta', etapa: 'D1' }] } };
  const raiz = await pagina.render(ctxDe(apiRueda({ '/pulido': hostil })));
  assert.equal(buscarTodos(raiz, 'script').length, 0);
  assert.equal(buscarTodos(raiz, 'img').length, 0);
  assert.match(buscarTodos(raiz, 'a.n1-paso')[0].textContent, /1 pendiente abierto \(1 de gravedad alta\)/);
  for (const t of buscarTodos(raiz, 'a.n1-paso')) assert.equal(buscarTodos(t, '.comando').length, 0);
  for (const c of buscarTodos(raiz, '.comando')) assert.ok(c.closest('details') === c);
});
