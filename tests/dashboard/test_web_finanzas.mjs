// test_web_finanzas.mjs — lógica pura y render (DOM falso) de #/finanzas. Ejecutar: node --test tests/dashboard/test_web_finanzas.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import * as F from '../../dashboard/web/lib/finanzas.js';
import { ui, fmt } from '../../dashboard/web/ui.js';
import { instalarDomFalso, porClase, porTag, texto, todos } from '../fixtures/dashboard/operacion/dom_falso.mjs';

const fx = (n) => JSON.parse(readFileSync(fileURLToPath(new URL(`../fixtures/dashboard/finanzas/${n}`, import.meta.url)), 'utf8'));
const parametros = { grupos: { dashboard: { costo_ia_max_pct: { valor: 15 } } } };
const sano = fx('finanzas_sano.json');

test('vigentesLedger: gana la última por clave natural; descarta líneas que no cumplen el contrato', () => {
  const r = F.vigentesLedger(sano.ledger);
  assert.equal(r.vigentes.length, 9);
  assert.equal(r.reemplazadas, 1);
  assert.equal(r.invalidas, 1);
  const meta13 = r.vigentes.find((l) => l.clave_natural === 'meta:ad_120000000000003_20261113');
  assert.equal(meta13.importe.monto, 3050); // el upsert posterior manda
  assert.ok(r.vigentes[0].fecha >= r.vigentes[r.vigentes.length - 1].fecha, 'orden por fecha descendente');
  assert.deepEqual(F.vigentesLedger(undefined), { vigentes: [], reemplazadas: 0, invalidas: 0 });
  assert.equal(F.vigentesLedger([{ clave_natural: 'stripe:abc', tipo: 'pedido', fecha: '2026-11-12', sentido: 'entrada', importe: { monto: 1.5, moneda: 'EUR' } }]).invalidas, 1); // float: no entra
});

test('totalesLedger: entradas − salidas por moneda, sin pruebas y sin mezclar monedas', () => {
  const { vigentes } = F.vigentesLedger(sano.ledger);
  const t = F.totalesLedger(vigentes);
  assert.equal(t.pruebasExcluidas, 1);
  assert.equal(t.monedas.length, 1);
  assert.deepEqual([t.monedas[0].moneda, t.monedas[0].entradas, t.monedas[0].salidas, t.monedas[0].neto, t.monedas[0].lineas], ['EUR', 4059, 8712, -4653, 8]);
  assert.equal(t.monedas[0].porTipo.pedido, 4059);
  assert.equal(t.monedas[0].porTipo.reembolso, -1990);
  const mixto = F.totalesLedger([...vigentes, { ...vigentes[0], clave_natural: 'stripe:usd1', importe: { monto: 100, moneda: 'USD' } }]);
  assert.equal(mixto.monedas.length, 2); // EUR y USD por separado
  assert.deepEqual(F.totalesLedger([]), { monedas: [], pruebasExcluidas: 0 }); // sin líneas: sin totales (no un 0)
});

test('filtrarLedger y totalesPorOferta', () => {
  const { vigentes } = F.vigentesLedger(sano.ledger);
  assert.equal(F.filtrarLedger(vigentes, {}).length, 8); // sin pruebas
  assert.equal(F.filtrarLedger(vigentes, { incluirPruebas: true }).length, 9);
  assert.equal(F.filtrarLedger(vigentes, { tipo: 'costo' }).length, 3);
  assert.equal(F.filtrarLedger(vigentes, { oferta: 'empresa' }).length, 1);
  assert.equal(F.filtrarLedger(vigentes, { desde: '2026-11-13', hasta: '2026-11-13' }).length, 2);
  const po = F.totalesPorOferta(vigentes);
  assert.deepEqual(po.map((x) => [x.oferta_id, x.entradas, x.salidas, x.neto, x.lineas]), [['empresa', 0, 500, -500, 1], ['OF-202611-01', 4059, 8212, -4153, 7]]);
});

test('modeloConciliacion: diferencia ≠ 0 tacha con la causa; INCOMPLETO tacha todo; sin archivo = null', () => {
  const ok = F.modeloConciliacion(sano.conciliacion);
  assert.equal(ok.estado, 'CONCILIADO');
  assert.equal(ok.tono, 'ok');
  assert.equal(ok.stripe.cuadra, true);
  assert.equal(ok.cifrasTachadas, false);
  assert.deepEqual(ok.tachadas, { stripe: null, meta: null, todo: null });
  assert.equal(ok.coberturaBp, 9800);
  assert.equal(ok.compras.razon, 1);
  const d = F.modeloConciliacion(fx('finanzas_descuadre.json').conciliacion);
  assert.equal(d.estado, 'DESCUADRE');
  assert.equal(d.stripe.cuadra, false);
  assert.match(d.tachadas.stripe, /Stripe 199,00\s€ ≠ libro de movimientos 179,10\s€: diferencia 19,90\s€/);
  assert.equal(d.tachadas.meta, null);
  assert.equal(d.cifrasTachadas, true);
  const inc = F.modeloConciliacion(fx('finanzas_incompleto.json').conciliacion);
  assert.match(inc.tachadas.todo, /INCOMPLETA/);
  assert.equal(inc.pendientesAsincronos, 2);
  assert.equal(F.modeloConciliacion(null), null);
  assert.equal(F.modeloConciliacion({}), null);
  // un cotejo al que le falta una pata no se da por «cuadrado»
  const cojo = F.modeloConciliacion({ ...sano.conciliacion, stripe_vs_ledger: { izquierda: { monto: 1, moneda: 'EUR' } } });
  assert.equal(cojo.stripe.cuadra, null);
});

test('verificarResultado: la fórmula del P&L cuadra o se marca', () => {
  const b = sano.pnl.consolidado;
  const v = F.verificarResultado(b);
  assert.equal(v.coincide, true);
  assert.deepEqual(v.esperado, { monto: -5844, moneda: 'EUR' });
  const roto = { ...b, resultado_operativo: { monto: -5000, moneda: 'EUR' } };
  assert.equal(F.verificarResultado(roto).coincide, false);
  assert.equal(F.verificarResultado({}).coincide, null);
  assert.equal(F.verificarResultado({ ...b, lineas: { ...b.lineas, gasto_meta: { monto: 1, moneda: 'USD' } } }).coincide, null); // moneda distinta: no se compara
});

test('modeloPnl: tachado por conciliación, por frescura y por fórmula; avisos sin conciliación', () => {
  const sanoM = F.modeloPnl(sano.pnl, F.modeloConciliacion(sano.conciliacion));
  assert.deepEqual(sanoM.causas, {});
  assert.deepEqual(sanoM.avisos, []);
  assert.deepEqual(sanoM.bloques.map((b) => b.id), ['consolidado', 'OF-202611-01']);
  assert.equal(sanoM.bloques[0].kpis.roas_neto, 0.85);
  assert.equal(sanoM.bloques[0].kpis.mc, null); // sin dato, no 0

  const d = fx('finanzas_descuadre.json');
  const m = F.modeloPnl(d.pnl, F.modeloConciliacion(d.conciliacion));
  const cons = m.bloques[0];
  assert.ok(F.causasDeCelda(m, cons, 'ingresos_brutos').some((c) => /diferencia 19,90/.test(c)));
  assert.ok(F.causasDeCelda(m, cons, 'comisiones').length >= 1); // origen Stripe
  assert.equal(F.causasDeCelda(m, cons, 'gasto_meta').length, 0); // Meta sí cuadra
  assert.equal(F.causasDeCelda(m, cons, 'costo_ia').length, 0);
  const res = F.causasDeCelda(m, cons, 'resultado_operativo');
  assert.equal(res.length, 2); // conciliación + la fórmula propia no cuadra
  assert.ok(res.some((c) => /las líneas suman/.test(c)));
  assert.equal(F.causasDeCelda(m, m.bloques[1], 'resultado_operativo').length, 1); // la oferta sí cuadra con sus líneas

  const i = fx('finanzas_incompleto.json');
  const mi = F.modeloPnl(i.pnl, F.modeloConciliacion(i.conciliacion));
  const causas = F.causasDeCelda(mi, mi.bloques[0], 'gasto_meta');
  assert.ok(causas.some((c) => /desactualizada/.test(c)));
  assert.ok(causas.some((c) => /INCOMPLETA/.test(c)));

  const sinConc = F.modeloPnl(sano.pnl, null);
  assert.match(sinConc.avisos[0], /Sin conciliación/);
  const otro = F.modeloConciliacion({ ...sano.conciliacion, periodo: { desde: '2026-10-01', hasta: '2026-10-31' } });
  assert.match(F.modeloPnl(sano.pnl, otro).avisos[0], /otro periodo/);
  assert.equal(F.modeloPnl(null, null), null);
  assert.equal(F.modeloPnl({}, null), null);
});

test('costosIa: porcentaje solo con ingresos; contra el máximo; cuadre con el ledger', () => {
  const { vigentes } = F.vigentesLedger(sano.ledger);
  const c = F.costosIa(sano.pnl, vigentes, parametros);
  const cons = c.find((x) => x.id === 'consolidado');
  assert.equal(cons.pctBp, 166); // 412 / 24828
  assert.equal(cons.topePct, 15);
  assert.equal(cons.estado, 'ok');
  const of = c.find((x) => x.id === 'OF-202611-01');
  assert.deepEqual(of.ledger, { monto: 412, moneda: 'EUR' });
  assert.equal(of.descuadreConLedger, false);
  // sin ingresos: no hay porcentaje (no un 0 %)
  const pnl = JSON.parse(JSON.stringify(sano.pnl));
  pnl.consolidado.lineas.ingresos_brutos.monto = 0;
  assert.equal(F.costosIa(pnl, vigentes, parametros).find((x) => x.id === 'consolidado').pctBp, null);
  assert.equal(F.costosIa(pnl, vigentes, parametros).find((x) => x.id === 'consolidado').estado, 'sin_ingresos');
  // por encima del máximo
  const caro = JSON.parse(JSON.stringify(sano.pnl));
  caro.consolidado.lineas.costo_ia.monto = 9000;
  assert.equal(F.costosIa(caro, vigentes, parametros).find((x) => x.id === 'consolidado').estado, 'rojo');
  // sin parámetro: no se inventa el máximo
  assert.equal(F.costosIa(sano.pnl, vigentes, null)[0].topePct, null);
  // descuadre con el ledger
  const desc = vigentes.filter((l) => l.clave_natural !== 'costos:RUN-20261106-01:D1');
  assert.equal(F.costosIa(sano.pnl, desc, parametros).find((x) => x.id === 'OF-202611-01').descuadreConLedger, true);
  assert.deepEqual(F.costosIa(null, [], parametros), []);
});

test('alertas: abiertas primero y por gravedad; severidad libre → tono; valores sin float', () => {
  assert.equal(F.tonoSeveridad('roja'), 'error');
  assert.equal(F.tonoSeveridad('CRITICA'), 'error');
  assert.equal(F.tonoSeveridad('amarilla'), 'aviso');
  assert.equal(F.tonoSeveridad('info'), 'info');
  assert.equal(F.tonoSeveridad('???'), 'neutro');
  assert.equal(F.tonoSeveridad(null), 'neutro');
  const a = F.normalizarAlertas(sano.alertas);
  assert.deepEqual(a.map((x) => x.id), ['AL-1', 'AL-3', 'AL-2']);
  assert.equal(a[0].abierta, true);
  assert.equal(a[2].abierta, false);
  assert.match(a[0].valor, /19,90/);
  assert.equal(a[2].valor, '16');
  assert.deepEqual(F.normalizarAlertas([null, 5, 'x']), []);
});

test('modeloFinanzas: vacío total = hayAlgo false; todo junto = datos coherentes', () => {
  assert.equal(F.modeloFinanzas(fx('finanzas_vacio.json'), null).hayAlgo, false);
  assert.equal(F.modeloFinanzas(null, null).hayAlgo, false);
  assert.equal(F.modeloFinanzas('basura', null).hayAlgo, false);
  const m = F.modeloFinanzas(sano, parametros);
  assert.equal(m.hayAlgo, true);
  assert.equal(m.alertasAbiertas, 2);
  assert.deepEqual(m.ofertas, ['OF-202611-01', 'empresa']);
  assert.equal(m.conciliacion.estado, 'CONCILIADO');
  assert.equal(F.comandosFinanzas().ledger.startsWith('.venv/bin/python -m datos.ledger'), true);
});

test('el ledger del panel llega recortado a las últimas 500 líneas: el modelo avisa de posibles totales parciales', () => {
  const lineas = Array.from({ length: 500 }, (_, i) => ({ schema_version: '1.0.0', clave_natural: `stripe:cs_${String(i).padStart(4, '0')}`, tipo: 'pedido', oferta_id: 'OF-202611-01', fecha: '2026-11-12', ts: '2026-11-12T10:00:00Z', sentido: 'entrada', importe: { monto: 100, moneda: 'EUR' }, fuente: 'stripe', es_prueba: false }));
  assert.equal(F.modeloFinanzas({ ledger: lineas }, null).ledger.posibleTruncado, true);
  assert.equal(F.modeloFinanzas({ ledger: lineas.slice(0, 499) }, null).ledger.posibleTruncado, false);
  assert.equal(F.LIMITE_LEDGER_PANEL, 500);
});

// ───────────── render con DOM falso ─────────────

function ctxDe(finanzas, { fuente = ['empresa/finanzas/ledger.jsonl'], vacio = false, parametrosDatos = { parametros } } = {}) {
  const api = {
    sobre: async (ruta) => {
      if (ruta === '/finanzas') return { datos: finanzas, fuente, generado_en: '2026-11-14T10:00:00Z', vacio, avisos: [] };
      if (ruta === '/parametros') return { datos: parametrosDatos, fuente: ['empresa/parametros.yaml'], generado_en: null, vacio: false, avisos: [] };
      throw Object.assign(new Error('x'), { codigo: 'no_encontrado', mensaje: 'x' });
    },
  };
  return { api, ui, fmt, estado: {}, params: {}, ruta: 'finanzas', recargar() {}, navegar() {}, alSalir() {} };
}

test('render sano: secciones, totales del ledger, sin tachaduras y sin innerHTML con datos hostiles', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/finanzas.js');
    assert.equal(pagina.meta.ruta, 'finanzas');
    const raiz = await pagina.render(ctxDe(sano));
    const t = texto(raiz);
    assert.match(t, /¿Cuadran las cuentas\?/);
    assert.match(t, /Resultado por oferta/);
    assert.match(t, /Libro de movimientos/);
    assert.match(t, /Costos de IA/);
    assert.match(t, /Neto \(EUR\)/);
    assert.match(t, /-46,53\s€/);
    assert.equal(porTag(raiz, 's').length, 0, 'con todo conciliado no hay cifras tachadas');
    assert.equal(porTag(raiz, 'img').length, 0);
    assert.ok(t.includes('<img src=x onerror=alert(1)>'), 'el texto hostil de una alerta se ve como texto');
  } finally { restaurar(); }
});

test('render con descuadre: cifras tachadas con su causa visible y avisos de error', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/finanzas.js');
    const raiz = await pagina.render(ctxDe(fx('finanzas_descuadre.json')));
    assert.ok(porTag(raiz, 's').length >= 3, 'ingresos, comisiones, resultado… tachados');
    const t = texto(raiz);
    assert.match(t, /Cifras? tachadas?: Stripe 199,00\s€ ≠ libro de movimientos 179,10\s€/);
    assert.match(t, /las líneas suman -58,44\s€ pero el resultado informado es -50,00\s€/);
    assert.ok(porClase(raiz, 'p5-aviso--error').length >= 2);
    assert.ok(porClase(raiz, 'cifra-causa').length >= 1);
  } finally { restaurar(); }
});

test('render incompleto + stale: todo tachado y causas de frescura y conciliación', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/finanzas.js');
    const raiz = await pagina.render(ctxDe(fx('finanzas_incompleto.json')));
    const t = texto(raiz);
    assert.match(t, /cuenta de resultados con datos hasta .* \(desactualizada\)/);
    assert.match(t, /conciliación INCOMPLETA/);
    assert.match(t, /El libro de movimientos está vacío o aún no existe/); // ledger vacío: estado vacío con comando, no totales a 0
    assert.ok(porTag(raiz, 's').length >= 5);
  } finally { restaurar(); }
});

test('render vacío: estado vacío con comandos copiables y ningún cero', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/finanzas.js');
    const raiz = await pagina.render(ctxDe(fx('finanzas_vacio.json'), { vacio: true, fuente: ['empresa/finanzas/ledger.jsonl'] }));
    const t = texto(raiz);
    assert.match(t, /Todavía no hay datos de finanzas/);
    assert.match(t, /\.venv\/bin\/python -m datos\.etl_stripe/);
    assert.match(t, /empresa\/finanzas\/ledger\.jsonl/);
    assert.ok(porClase(raiz, 'comando').length >= 2);
    assert.doesNotMatch(t, /0,00\s€/);
  } finally { restaurar(); }
});

test('render con error de API: errorBox (nunca pantalla en blanco)', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/finanzas.js');
    const ctx = ctxDe(sano);
    ctx.api = { sobre: async () => { throw Object.assign(new Error('caído'), { codigo: 'sin_conexion', mensaje: 'caído' }); } };
    const raiz = await pagina.render(ctx);
    assert.equal(porClase(raiz, 'error-box').length, 1);
  } finally { restaurar(); }
});


// ───────────── rediseño U4 ─────────────

test('margenBp: con signo, sin ingresos no hay margen (nunca 0 %) y las monedas no se mezclan', () => {
  assert.equal(F.margenBp({ monto: 2500, moneda: 'EUR' }, { monto: 10000, moneda: 'EUR' }), 2500);
  assert.equal(F.margenBp({ monto: -5000, moneda: 'EUR' }, { monto: 10000, moneda: 'EUR' }), -5000);
  assert.equal(F.margenBp({ monto: 100, moneda: 'EUR' }, { monto: 0, moneda: 'EUR' }), null);
  assert.equal(F.margenBp({ monto: 100, moneda: 'EUR' }, { monto: 100, moneda: 'USD' }), null);
  assert.equal(F.margenBp(null, { monto: 100, moneda: 'EUR' }), null);
});

test('sumaLineas: suma entera con signo de dato; si falta una línea no se suma como 0', () => {
  const b = { lineas: { comisiones: { monto: 100, moneda: 'EUR' }, tarifas_disputa: { monto: 50, moneda: 'EUR' }, disputas_perdidas: { monto: 0, moneda: 'EUR' } } };
  assert.deepEqual(F.sumaLineas(b, ['comisiones', 'tarifas_disputa', 'disputas_perdidas']), { monto: 150, moneda: 'EUR' });
  assert.equal(F.sumaLineas({ lineas: { comisiones: { monto: 100, moneda: 'EUR' }, tarifas_disputa: null } }, ['comisiones', 'tarifas_disputa']), null);
  assert.equal(F.sumaLineas(b, ['no_existe']), null);
});

test('atencionFinanzas: descuadre = crítico con su causa; sin conciliación = aviso; todo sano = vacío', () => {
  const d = F.atencionFinanzas(F.modeloFinanzas(fx('finanzas_descuadre.json'), null));
  assert.equal(d[0].tono, 'critico');
  assert.match(d[0].titulo, /no cuadran con el libro de movimientos/);
  assert.match(d[0].detalle, /Stripe|Meta/);
  const inc = F.atencionFinanzas(F.modeloFinanzas(fx('finanzas_incompleto.json'), null));
  assert.ok(inc.some((x) => /incompleta/.test(x.titulo)));
  assert.deepEqual(F.atencionFinanzas(F.modeloFinanzas(null, null)), [], 'sin datos no se inventa ningún aviso');
  const sinConc = F.atencionFinanzas(F.modeloFinanzas({ ledger: fx('finanzas_sano.json').ledger }, null));
  assert.ok(sinConc.some((x) => /no están verificadas/.test(x.titulo)));
});

test('render descuadre: esquema Stripe ↔ libro ↔ Meta con semáforo, diferencia tachada y causa humana', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/finanzas.js');
    const raiz = await pagina.render(ctxDe(fx('finanzas_descuadre.json')));
    const t = texto(raiz);
    assert.match(t, /No cuadra/);
    assert.match(t, /Por qué no cuadra:/);
    assert.match(t, /Requiere tu atención/);
    assert.ok(porClase(raiz, 'p5-conc__enlace').length === 2, 'dos enlaces: Stripe↔libro y libro↔Meta');
    assert.equal(porClase(raiz, 'p5-margen').length, 0, 'con la cifra tachada el margen no se dibuja: «no fiable»');
    assert.match(t, /no fiable/);
    assert.ok(porTag(raiz, 's').length >= 1);
    const ok = await pagina.render(ctxDe(sano));
    assert.ok(porClase(ok, 'p5-margen').length >= 1, 'con todo conciliado, barras de margen en el P&L');
  } finally { restaurar(); }
});


// ───────────── alertas 1.0.0: severidad «naranja» y estado «cerrada» ─────────────

test('tonoSeveridad / etiquetaSeveridad: naranja es grave (ni ámbar ni rojo), con etiqueta propia; los cuatro niveles son distintos', () => {
  assert.equal(F.tonoSeveridad('naranja'), 'grave');
  assert.equal(F.tonoSeveridad('NARANJA'), 'grave');
  const tonos = ['info', 'amarilla', 'naranja', 'roja'].map(F.tonoSeveridad);
  assert.deepEqual(tonos, ['info', 'aviso', 'grave', 'error']);
  assert.equal(new Set(tonos).size, 4, 'cuatro tonos distintos: cada nivel con su icono');
  assert.deepEqual(['info', 'amarilla', 'naranja', 'roja'].map(F.etiquetaSeveridad), ['Información', 'Amarilla', 'Naranja · pausa', 'Roja']);
  assert.equal(F.etiquetaSeveridad(null), 'Sin gravedad');
});

test('estadoAlerta: abierta, reconocida (sigue viva) y cerrada; «resuelta» antigua se lee como cerrada', () => {
  assert.deepEqual([F.estadoAlerta('abierta').abierta, F.estadoAlerta('reconocida').abierta, F.estadoAlerta('cerrada').abierta, F.estadoAlerta('resuelta').abierta], [true, true, false, false]);
  assert.equal(F.estadoAlerta('cerrada').texto, 'Cerrada');
  assert.equal(F.estadoAlerta(undefined).texto, 'Abierta');
});

test('normalizarAlertas con el esquema 1.0.0: orden roja → naranja → amarilla → info, abiertas antes que cerradas; umbral null = sin umbral', () => {
  const a = F.normalizarAlertas(fx('finanzas_alertas.json').alertas);
  assert.deepEqual(a.map((x) => x.tono), ['error', 'grave', 'aviso', 'info']);
  assert.deepEqual(a.map((x) => x.estadoInfo.clave), ['reconocida', 'abierta', 'abierta', 'cerrada']);
  assert.equal(a[2].sinUmbral, true);
  assert.equal(a[2].umbral, null);
  assert.equal(a[1].sinUmbral, false);
});

test('atencionFinanzas: la alerta naranja abierta es de gravedad «grave» (entre crítico y aviso) y pide pausar', () => {
  const m = F.modeloFinanzas(fx('finanzas_alertas.json'), null);
  const a = F.atencionFinanzas(m);
  const nar = a.find((x) => /naranja/.test(x.titulo));
  assert.ok(nar, 'hay un aviso para la alerta naranja');
  assert.equal(nar.tono, 'grave');
  assert.match(nar.detalle, /Pausar la oferta/);
  const orden = { critico: 0, grave: 1, aviso: 2, info: 3 };
  for (let i = 1; i < a.length; i += 1) assert.ok(orden[a[i - 1].tono] <= orden[a[i].tono]);
  assert.ok(a.some((x) => x.tono === 'critico' && /roja/.test(x.titulo)));
});

test('render alertas: cada gravedad con icono + etiqueta, naranja con su fila, sin umbral en gris, estados humanos', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/finanzas.js');
    const raiz = await pagina.render(ctxDe(fx('finanzas_alertas.json')));
    const t = texto(raiz);
    assert.match(t, /Naranja · pausa/);
    assert.match(t, /Roja/);
    assert.match(t, /Amarilla · sin límite/);
    assert.match(t, /sin límite fijado/);
    assert.match(t, /Reconocida/);
    assert.match(t, /Cerrada/);
    assert.ok(todos(raiz, (n) => n.localName === 'tr' && /fila-grave/.test(n.className)).length === 1, 'la alerta naranja abierta tiene su fila');
    assert.ok(porClase(raiz, 'chip--grave').length >= 1, 'chip con el tono grave');
    assert.match(t, /alerta naranja abierta/);
  } finally { restaurar(); }
});
