// test_web_poscompra.mjs — lógica pura (lib/poscompra.js) y render con DOM falso de #/poscompra.
// Ejecutar: node --test tests/dashboard/test_web_poscompra.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import * as K from '../../dashboard/web/lib/poscompra.js';
import { ui, fmt } from '../../dashboard/web/ui.js';
import { instalarDomFalso, porClase, porTag, texto, todos } from '../fixtures/dashboard/operacion/dom_falso.mjs';
import { apiFalsa, ctxDe, detalleDemo, fx, OFERTA_DEMO, OFERTA_REAL } from '../fixtures/dashboard/n2/api_falsa.mjs';

const fuente = (ruta) => readFileSync(fileURLToPath(new URL(`../../dashboard/web/${ruta}`, import.meta.url)), 'utf8');
const kpi = fx('kpi_oferta_dia.json');
const pc = fx('postcompra.json');
const senal = fx('senal_pausa.json');
const economia = fx('economia.json');
const dia = (fecha, valores, extra = {}) => ({ fecha, filas: Object.entries(valores).map(([kpi_id, valor]) => ({ kpi_id, valor, unidad: 'n', n: 1, estado: 'ok', rango: null, ventana: '24h' })), ...extra });
const etapa = (em, id) => em.etapas.find((e) => e.id === id);

// ───────────────────────── embudo ─────────────────────────

test('el embudo tiene las 6 etapas del método, en orden: clic, página, comprar, pago, oferta, entrega', () => {
  assert.deepEqual(K.ETAPAS_EMBUDO.map((e) => e.id), ['clic', 'pagina', 'comprar', 'pago', 'oferta', 'entrega']);
  assert.equal(K.ETAPAS_EMBUDO.find((e) => e.id === 'oferta').kpi, null);
});

test('sumarKpi: suma por días, prefiere el primer id, ignora stale, null y textos', () => {
  const dias = [dia('2026-11-10', { clics_enlace: 40, compras: 9, compras_stripe: 2 }), dia('2026-11-11', { clics_enlace: '60', compras: 1 }), dia('2026-11-12', { clics_enlace: null }), { fecha: 'x', filas: [{ kpi_id: 'clics_enlace', valor: 5, estado: 'stale' }] }, null, 'basura'];
  assert.deepEqual(K.sumarKpi(dias, ['clics_enlace']), { valor: 100, dias: 2, fechas: ['2026-11-10', '2026-11-11'] });
  assert.equal(K.sumarKpi(dias, ['compras_stripe', 'compras']).valor, 3); // 2 (stripe) + 1 (compras, ese día no hay stripe)
  assert.equal(K.sumarKpi(dias, ['inicios_pago']), null);
  assert.equal(K.sumarKpi([], ['x']), null);
  assert.equal(K.sumarKpi(null, ['x']), null);
});

test('modeloEmbudo (demo): solo clics, compras y entregas tienen dato; la oferta tras el pago está planeada; sin tasas entre pasos no adyacentes', () => {
  const em = K.modeloEmbudo({ kpiDia: [kpi], entregas: pc.entregas });
  assert.equal(etapa(em, 'clic').valor, 98);
  assert.equal(etapa(em, 'pagina').estado, 'sin_dato');
  assert.equal(etapa(em, 'comprar').estado, 'sin_dato');
  assert.equal(etapa(em, 'pago').valor, 1);
  assert.equal(etapa(em, 'pago').convPrevio, null, 'el paso anterior no tiene dato: no hay tasa');
  assert.equal(etapa(em, 'oferta').estado, 'planeado');
  assert.match(etapa(em, 'oferta').planeado, /paso 4/);
  assert.equal(etapa(em, 'entrega').valor, 1);
  assert.equal(etapa(em, 'entrega').convPrevio, 1, 'la entrega se compara con el pago (la oferta planeada no cuenta como paso)');
  assert.equal(etapa(em, 'entrega').muestraPequena, true);
  assert.equal(em.conDato, 3);
  assert.equal(em.hayDatos, true);
  assert.equal(em.sintetico, true);
  assert.equal(em.ultimoDia, '2026-11-11');
  assert.deepEqual(em.anomalias, []);
});

test('modeloEmbudo: tasas entre pasos adyacentes con dato y marca de anomalía si un paso supera al anterior', () => {
  const ok = K.modeloEmbudo({ kpiDia: [dia('2026-11-10', { clics_enlace: 1000, vistas_landing: 800, inicios_pago: 80, compras_stripe: 16 })], entregas: [{ estado: 'entregado' }, { estado: 'fallido' }] });
  assert.ok(Math.abs(etapa(ok, 'pagina').convPrevio - 0.8) < 1e-9);
  assert.ok(Math.abs(etapa(ok, 'comprar').convPrevio - 0.1) < 1e-9);
  assert.ok(Math.abs(etapa(ok, 'pago').convPrevio - 0.2) < 1e-9);
  assert.equal(etapa(ok, 'pago').muestraPequena, false);
  assert.equal(etapa(ok, 'entrega').valor, 1);
  assert.equal(ok.sintetico, false);
  const mal = K.modeloEmbudo({ kpiDia: [dia('2026-11-10', { clics_enlace: 100, vistas_landing: 140, inicios_pago: 10, compras_stripe: 20 })] });
  assert.equal(etapa(mal, 'pagina').anomalia, true);
  assert.equal(etapa(mal, 'pago').anomalia, true);
  assert.deepEqual(mal.anomalias, ['Entra a la página', 'Paga']);
  const justo = K.modeloEmbudo({ kpiDia: [dia('2026-11-10', { clics_enlace: 100, vistas_landing: 105 })] });
  assert.equal(etapa(justo, 'pagina').anomalia, false, 'hasta un 5 % de margen');
});

test('modeloEmbudo sin nada: ninguna etapa con dato, sin inventar ceros', () => {
  for (const arg of [{}, { kpiDia: [], entregas: [] }, { kpiDia: [{}, null], entregas: [null] }]) {
    const em = K.modeloEmbudo(arg);
    assert.equal(em.hayDatos, false);
    assert.ok(em.etapas.every((e) => e.valor === null));
    assert.equal(etapa(em, 'oferta').estado, 'planeado');
  }
});

// ───────────────────────── automatismos ─────────────────────────

test('los 4 automatismos y su lugar en el plan de tienda (mapeo §7)', () => {
  assert.deepEqual(K.AUTOMATISMOS.map((a) => a.id), ['entrega', 'atencion', 'oferta_pago', 'carrito']);
  assert.equal(K.AUTOMATISMOS.find((a) => a.id === 'entrega').paso, 1);
  assert.equal(K.AUTOMATISMOS.find((a) => a.id === 'oferta_pago').paso, 4);
  assert.equal(K.AUTOMATISMOS.find((a) => a.id === 'carrito').paso, 5);
  assert.deepEqual(K.PLAN_TIENDA.map((p) => p.paso), [1, 2, 3, 4, 5, 6, 7]);
});

test('estadoAutomatismos: entrega según lo registrado; atención según la skill; el resto, planeado', () => {
  assert.equal(K.estadoAutomatismos({}).entrega.clave, 'disenada');
  assert.equal(K.estadoAutomatismos({ entregas: pc.entregas }).entrega.clave, 'prueba');
  assert.equal(K.estadoAutomatismos({ entregas: [{ estado: 'entregado' }, { estado: 'entregado', sintetico: true }] }).entrega.clave, 'en_marcha');
  const fallo = K.estadoAutomatismos({ entregas: [{ estado: 'entregado' }, { estado: 'fallido' }] }).entrega;
  assert.equal(fallo.clave, 'con_fallos');
  assert.match(fallo.evidencia, /1 de 2 entregadas; 1 falló/);
  assert.equal(K.estadoAutomatismos({}).atencion.clave, 'planeado');
  assert.equal(K.estadoAutomatismos({ skillD10: { existe: false } }).atencion.clave, 'planeado');
  assert.equal(K.estadoAutomatismos({ skillD10: { existe: true } }).atencion.clave, 'borrador');
  const e = K.estadoAutomatismos({});
  assert.equal(e.oferta_pago.clave, 'planeado');
  assert.equal(e.carrito.clave, 'planeado');
  for (const a of Object.values(e)) assert.ok(K.ESTADO_AUTOMATISMO[a.clave]);
});

test('resumenEntregas: cuenta entregadas, fallidas y sintéticas', () => {
  assert.deepEqual(K.resumenEntregas(pc.entregas), { total: 1, entregadas: 1, fallidas: 0, sinteticas: 1 });
  assert.deepEqual(K.resumenEntregas(null), { total: 0, entregadas: 0, fallidas: 0, sinteticas: 0 });
  assert.equal(K.resumenEntregas([{ estado: 'Descargado' }, { estado: 'rebotado' }, 5]).entregadas, 1);
});

// ───────────────────────── disputas ─────────────────────────

test('modeloDisputas (demo): señal verde con muestra insuficiente, umbrales en porcentaje y reembolsos por moneda', () => {
  const d = K.modeloDisputas({ senal, reembolsos: pc.reembolsos });
  assert.equal(d.haySenal, true);
  assert.equal(d.senal.nivel, 'verde');
  assert.equal(d.senal.muestraSuficiente, false);
  assert.equal(d.senal.pagosVentana, 2);
  assert.equal(d.senal.casos, 0);
  assert.equal(d.senal.disputasPct, 0);
  assert.equal(d.senal.reembolsosPct, 50);
  assert.equal(d.senal.sintetico, true);
  assert.deepEqual(d.umbrales, { disputasAlertaPct: 0.3, disputasPausaPct: 0.6, reembolsosAlertaPct: 8, reembolsosPausaPct: 12 });
  assert.deepEqual(d.reembolsos, { total: 1, ejecutados: 1, porMoneda: { EUR: 1990 }, sinteticos: 1 });
  assert.match(d.comando, /^python -m postcompra\.evidencia /);
});

test('modeloDisputas sin datos o con basura: sin señal, sin inventar', () => {
  for (const arg of [{}, { senal: null, reembolsos: null }, { senal: 'x', reembolsos: [null, 5] }]) {
    const d = K.modeloDisputas(arg);
    assert.equal(d.haySenal, false);
    assert.equal(d.senal, null);
    assert.equal(d.umbrales, null);
    assert.equal(d.reembolsos.total, 0);
  }
  const raro = K.modeloDisputas({ senal: { nivel: 'rojo', metricas: { casos_disputa_efw: 'muchos', pagos_ventana: -3 }, umbrales_usados: { ratio_disputas_pausa: 'x' } }, reembolsos: [{ estado: 'ejecutado', monto: { monto: 'x', moneda: 'EUR' } }, { estado: 'pendiente', monto: { monto: 100, moneda: 'EUR' } }] });
  assert.equal(raro.senal.casos, null);
  assert.equal(raro.senal.pagosVentana, null);
  assert.equal(raro.umbrales.disputasPausaPct, null);
  assert.deepEqual(raro.reembolsos.porMoneda, {});
});

test('el flujo de disputa: el sistema prepara y el dueño envía (el panel no envía)', () => {
  assert.ok(K.FLUJO_DISPUTA.solo.some((x) => /paquete de evidencia/.test(x)));
  assert.ok(K.FLUJO_DISPUTA.tu.some((x) => /Enviarlo desde Stripe/.test(x)));
  assert.match(K.FLUJO_DISPUTA.porque, /clave de escritura/);
});

// ───────────────────────── ticket promedio ─────────────────────────

test('modeloTicket: el medido es null («se medirá»); solo existe el supuesto de la economía, rotulado', () => {
  const t = K.modeloTicket(economia);
  assert.equal(t.medido, null);
  assert.equal(t.haySupuesto, true);
  assert.deepEqual(t.aov, { monto: 2069, moneda: 'EUR' });
  assert.deepEqual(t.precio, { monto: 1990, moneda: 'EUR' });
  assert.equal(t.tasaBumpBp, 1000);
  assert.equal(t.origen, 'supuesto');
  const sin = K.modeloTicket(null);
  assert.equal(sin.medido, null);
  assert.equal(sin.haySupuesto, false);
  assert.equal(K.modeloTicket({ aov: { monto: 'x', moneda: 'EUR' } }).haySupuesto, false);
});

test('la cifra declarada por el autor del método (ticket de ≈ 31,37) no aparece en ninguna fuente de la pantalla', () => {
  for (const ruta of ['pages/poscompra.js', 'lib/poscompra.js']) {
    const src = fuente(ruta);
    for (const cifra of ['31,37', '31.37', '1,99', '100 USD', 'US$100']) assert.ok(!src.includes(cifra), `${ruta} no debe incluir ${cifra}`);
  }
});

// ───────────────────────── render ─────────────────────────

function opDemo(extra = {}) {
  return { kpi_dia: [kpi], decisiones: [], ordenes: [], veredicto: null, postcompra: { entregas: pc.entregas, reembolsos: pc.reembolsos, senal_pausa: senal }, kpi_blended: null, ...extra };
}
function ctxPos({ ofertas = [OFERTA_DEMO], operacion, archivos, skills = [{ slug: 'd6-creativos' }], falla = {} } = {}) {
  const detalles = Object.fromEntries(ofertas.map((o) => [o.oferta_id, detalleDemo()]));
  const { api, llamadas } = apiFalsa({ ofertas, detalles, operacion: operacion || { _ejemplo: opDemo() }, archivos: archivos || { '_ejemplo|03-oferta/economia.json': JSON.stringify(economia) }, skills, falla });
  return { ctx: ctxDe(ui, fmt, api), llamadas };
}

test('render (demo): embudo con lo que existe, automatismos con su estado real, disputas, ticket «se medirá»', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/poscompra.js');
    assert.equal(pagina.meta.ruta, 'poscompra');
    assert.equal(pagina.meta.grupo, 'Fábrica y tienda');
    assert.equal(pagina.meta.icono, 'bolsa');
    const { ctx, llamadas } = ctxPos();
    const raiz = await pagina.render(ctx);
    const t = texto(raiz);
    assert.match(t, /Después de la venta/);
    assert.match(t, /Estás viendo datos de demostración/);
    assert.match(t, /El camino del comprador/);
    for (const e of K.ETAPAS_EMBUDO) assert.ok(t.includes(e.nombre), e.nombre);
    assert.match(t, /Datos de prueba\./);
    assert.match(t, /Planeado/);
    assert.match(t, /Lo mediría: Contador propio de la página/);
    assert.equal(porClase(raiz, 'n2-etapa').length, 6);
    assert.match(t, /Lo que corre solo después de la venta/);
    for (const a of K.AUTOMATISMOS) assert.ok(t.includes(a.nombre), a.nombre);
    assert.match(t, /Probada con datos de prueba/);
    assert.match(t, /Paso 1 de 7/);
    assert.match(t, /Paso 5 de 7/);
    assert.match(t, /Las instrucciones de la IA de poscompra aún no existen/);
    assert.match(t, /Disputas: el sistema prepara, tú envías/);
    assert.match(t, /Enviarlo desde Stripe con un clic/);
    assert.match(t, /muestra todavía insuficiente/i);
    assert.match(t, /postcompra\.evidencia/);
    assert.match(t, /Ticket promedio medido/);
    assert.match(t, /Se medirá con nuestras ventas/);
    assert.match(t, /Supuesto de las cuentas de la oferta/);
    assert.match(t, /20,69/);
    assert.match(t, /Supuesto, no medido/);
    assert.match(t, /No se usa la cifra del autor del método/);
    for (const cifra of ['31,37', '31.37']) assert.ok(!t.includes(cifra));
    assert.ok(llamadas.includes('/operacion/_ejemplo'));
    assert.ok(llamadas.some((l) => l.includes('03-oferta/economia.json')));
    assert.ok(porClase(raiz, 'comando').length >= 1);
    for (const b of porTag(raiz, 'button')) assert.doesNotMatch(b.textContent, /enviar|responder|reembolsar|publicar|activar|borrar/i);
  } finally { restaurar(); }
});

test('render sin ningún dato (oferta nueva): embudo vacío con pasos, automatismos «planeado», ticket «se medirá», sin cifras inventadas', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/poscompra.js');
    const { ctx } = ctxPos({ operacion: {}, archivos: {} });
    const raiz = await pagina.render(ctx);
    const t = texto(raiz);
    assert.match(t, /Todavía no se mide ningún paso del camino del comprador/);
    assert.match(t, /cierre diario deja las cifras del día/);
    assert.match(t, /engine\.orq estado/);
    assert.match(t, /Diseñada, sin probar en vivo/);
    assert.match(t, /Todavía no hay señal de pausa/);
    assert.match(t, /sin compras medidas todavía/);
    assert.match(t, /ninguna entrega registrada/);
    assert.match(t, /La oferta no tiene las cuentas hechas/);
    assert.equal(porClase(raiz, 'n2-etapa').length, 0);
    assert.ok(porClase(raiz, 'metrica--sin-valor').length >= 3, 'las métricas sin dato muestran «—», no cero');
  } finally { restaurar(); }
});

test('render: embudo que no cuadra, entregas fallidas y señal de pausa en rojo suben a «Requiere tu atención»', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/poscompra.js');
    const operacion = { _ejemplo: opDemo({
      kpi_dia: [dia('2026-11-10', { clics_enlace: 100, vistas_landing: 150, compras_stripe: 5 })],
      postcompra: { entregas: [{ estado: 'entregado' }, { estado: 'fallido' }], reembolsos: [], senal_pausa: { ...senal, nivel: 'rojo', motivo: 'disputas altas', sintetico: false } },
    }) };
    const { ctx } = ctxPos({ operacion });
    const t = texto(await pagina.render(ctx));
    assert.match(t, /El camino del comprador de _ejemplo no cuadra en: Entra a la página/);
    assert.match(t, /1 entrega falló en _ejemplo/);
    assert.match(t, /La señal de pausa de _ejemplo está en rojo/);
    assert.match(t, /Motivo: disputas altas/);
    assert.match(t, /Con entregas fallidas/);
  } finally { restaurar(); }
});

test('render: con una skill de D10 la atención pasa a «instrucciones en borrador»; con la lista de skills caída sigue «planeado»', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/poscompra.js');
    const con = ctxPos({ skills: [{ slug: 'd10-postcompra' }] });
    assert.match(texto(await pagina.render(con.ctx)), /Instrucciones en borrador/);
    const caida = ctxPos({ skills: null });
    assert.match(texto(await pagina.render(caida.ctx)), /El panel no tiene lectura de la bandeja de soporte/);
  } finally { restaurar(); }
});

test('render: API caída, operación ilegible y selector entre ofertas', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/poscompra.js');
    const caida = ctxPos({ falla: { '/ofertas': true } });
    caida.ctx.estado.ofertas = [];
    assert.ok(porClase(await pagina.render(caida.ctx), 'error-box').length >= 1);
    const sinOp = ctxPos({ falla: { '/operacion/_ejemplo': true } });
    const t = texto(await pagina.render(sinOp.ctx));
    assert.match(t, /No se pudo leer la operación de esta oferta/);
    assert.match(t, /Todavía no se mide ningún paso del camino del comprador/);
    const dos = ctxPos({ ofertas: [OFERTA_DEMO, OFERTA_REAL], operacion: { _ejemplo: opDemo() } });
    const raiz = await pagina.render(dos.ctx);
    const sel = todos(raiz, (n) => n.localName === 'select')[0];
    assert.ok(sel);
    sel.dispararEvento('change', { target: { value: '_ejemplo' } });
    assert.match(texto(raiz), /Datos de prueba\./);
    sel.dispararEvento('change', { target: { value: 'OF-202701-02' } });
    assert.match(texto(raiz), /Todavía no se mide ningún paso del camino del comprador/);
  } finally { restaurar(); }
});

test('render: texto hostil de entregas y señal no se interpreta', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/poscompra.js');
    const operacion = { _ejemplo: opDemo({ postcompra: { entregas: [{ estado: 'entregado', sintetico: false }], reembolsos: [], senal_pausa: { ...senal, nivel: 'amarillo', motivo: '<script>alert(1)</script>‮', sintetico: false } } }) };
    const raiz = await pagina.render(ctxPos({ operacion }).ctx);
    const t = texto(raiz);
    assert.ok(t.includes('<script>alert(1)</script>'));
    assert.ok(t.includes('⟦U+202E⟧'));
    assert.equal(porTag(raiz, 'script').length, 0);
  } finally { restaurar(); }
});

test('la pantalla solo lee y no usa APIs peligrosas', () => {
  for (const ruta of ['pages/poscompra.js', 'lib/poscompra.js']) {
    const src = fuente(ruta);
    assert.ok(!/innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function|srcdoc/.test(src), ruta);
    assert.ok(!/api\.post|\.post\(|method:\s*['"]POST/.test(src), ruta);
  }
});
