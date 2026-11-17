// test_web_negocio.mjs — lógica pura y render (DOM falso) de #/negocio. Ejecutar: node --test tests/dashboard/test_web_negocio.mjs
// El fixture negocio.json sale de dashboard/negocio.py con el libro de prueba de test_servidor_negocio.py.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import * as N from '../../dashboard/web/lib/negocio.js';
import * as V from '../../dashboard/web/lib/negocio-visual.js';
import * as E from '../../dashboard/web/lib/negocio-etapas.js';
import { ui, fmt } from '../../dashboard/web/ui.js';
import { instalarDomFalso, porTag, texto, todos } from '../fixtures/dashboard/operacion/dom_falso.mjs';

const datos = JSON.parse(readFileSync(fileURLToPath(new URL('../fixtures/dashboard/negocio/negocio.json', import.meta.url)), 'utf8'));

test('formatos: dólares, monedas, porcentajes y retorno con coma decimal y signo menos tipográfico', () => {
  assert.equal(N.usd(29.2), 'US$ 29,20');
  assert.equal(N.usd(-54.93), '−US$ 54,93');
  assert.equal(N.usd(1234.5), 'US$ 1.234,50');
  assert.equal(N.usd(6.64, { signo: true }), '+US$ 6,64');
  assert.equal(N.usd(-0.001), 'US$ 0,00', 'un redondeo a cero no lleva signo');
  assert.equal(N.usd(null), '—');
  assert.equal(N.moneda(319, 'MXN'), 'MX$ 319,00');
  assert.equal(N.moneda(69, 'BRL'), 'R$ 69,00');
  assert.equal(N.pct(15.94), '15,9 %');
  assert.equal(N.roas(1.73), '1,73 ×');
  assert.equal(N.roas(undefined), '—');
});

test('palabras: estados, veredicto, mercado y tipo de funnel sin jerga', () => {
  assert.equal(N.estadoOferta('activa').texto, 'Activa');
  assert.equal(N.estadoOferta('programada').tono, 'info');
  assert.equal(N.veredicto('perdiendo').tono, 'error');
  assert.equal(N.mercado('MX'), 'México');
  assert.equal(N.mercado('MX/BR'), 'México y Brasil');
  assert.equal(N.tipoFunnel('tsl + niveles + subida-previa'), 'Página de venta larga · dos niveles de precio · oferta mejor antes de pagar');
  assert.equal(N.tipoFunnel('quiz+vsl'), 'Cuestionario · video de venta');
  assert.equal(N.tipoFunnel('tsl-video'), 'Página de venta larga · con video');
});

test('urlExterna: solo https; javascript:, http y textos raros no se vuelven enlace', () => {
  assert.deepEqual(N.urlExterna('https://www.ejemplo.com/a'), { url: 'https://www.ejemplo.com/a', dominio: 'ejemplo.com' });
  for (const malo of ['http://x.com', 'javascript:alert(1)', 'https://x.com/"onmouseover', '', null, 'https://a b.com']) assert.equal(N.urlExterna(malo), null, String(malo));
});

test('orden, serie diaria, uso del freno y posición del costo por venta', () => {
  const o = N.ordenarOfertas([{ estado: 'programada', ganancia_neta: 5 }, { estado: 'activa', ganancia_neta: -3 }, { estado: 'activa', ganancia_neta: 9 }]);
  assert.deepEqual(o.map((x) => [x.estado, x.ganancia_neta]), [['activa', 9], ['activa', -3], ['programada', 5]]);
  assert.deepEqual(N.serieDiaria([{ fecha: '2026-11-12', resultado: 5 }, { fecha: '2026-11-13', resultado: null }], 'resultado'), [{ x: '2026-11-12', y: 5 }, { x: '2026-11-13', y: null }]);
  assert.equal(N.usoFreno(240, 300).zona, 'aviso');
  assert.equal(N.usoFreno(320, 300).zona, 'error');
  assert.equal(N.usoFreno(100, 300).zona, 'ok');
  assert.equal(N.usoFreno(null, 300), null);
  const p = N.posicionCpa(10, 10);
  assert.equal(Math.round(p.equilibrio), Math.round(p.marca), 'CPA igual al equilibrio: marca sobre la raya');
  assert.equal(N.posicionCpa(null, 10), null);
});

test('itemsAtencion: botón a la ficha; en la ficha solo los de esa oferta y los de la cuenta', () => {
  let abierto = null;
  const items = N.itemsAtencion(datos.atencion, { abrir: (id) => { abierto = id; } });
  assert.equal(items.length, datos.atencion.length);
  const conBoton = items.find((i) => i.accion);
  conBoton.accion.onClick();
  assert.ok(abierto);
  const soloKit = N.itemsAtencion(datos.atencion, { soloOferta: 'kit-uno' });
  assert.ok(soloKit.length < items.length);
  assert.ok(soloKit.every((i) => !i.accion), 'dentro de la ficha no se ofrece abrir la misma ficha');
});

test('corte: fecha en la zona del libro y aviso de datos viejos', () => {
  assert.equal(N.textoCorte('2026-11-12T20:00:00-03:00'), '12/11/2026 20:00 (hora de Argentina y Brasil)');
  assert.equal(N.textoCorte('2026-11-12T00:00:00-06:00'), '12/11/2026 00:00 (hora del centro de México)');
  assert.equal(N.estadoCorte({ horas: 0.3, viejo: false }).tono, 'ok');
  assert.match(N.estadoCorte({ horas: 40, viejo: true }).texto, /40 horas/);
});

function ctxDe(d, { params = {}, vacio = false } = {}) {
  const navegado = [];
  const api = {
    sobre: async (ruta) => {
      if (ruta === '/negocio') return { datos: d, fuente: ['ofertas/_funnels/libro-de-tests.json'], generado_en: '2026-11-13T00:00:00Z', vacio, avisos: [] };
      if (ruta === '/negocio/documento') return { datos: { tipo: 'markdown', contenido: '# Expediente' }, fuente: [], vacio: false, avisos: [] };
      throw Object.assign(new Error('x'), { codigo: 'no_encontrado', mensaje: 'x' });
    },
  };
  return { api, ui, fmt, estado: {}, params, ruta: 'negocio', recargar() {}, navegar(h) { navegado.push(h); }, alSalir() {}, navegado };
}

test('definiciones del dueño: nombres, fórmulas y tono contra el equilibrio de 1,00 ×', () => {
  assert.equal(N.DEFINICIONES.roas_meta.titulo, 'ROAS Meta');
  assert.match(N.DEFINICIONES.roas_real.texto, /Meta \+ producción \+ fijos/);
  assert.match(N.DEFINICIONES.roas_neto.texto, /No incluye la producción/);
  assert.match(N.PRODUCCION_Y_ROAS, /no entra en el ROAS/);
  assert.equal(N.tonoRoas(1), 'ok');
  assert.equal(N.tonoRoas(0.99), 'error');
  assert.equal(N.tonoRoas(null), null);
});

test('visuales: medidor contra el equilibrio, tasa contra su referencia, banderas e identidad', () => {
  const m = V.geoMedidor(1.56, 1);
  assert.equal(m.tono, 'ok');
  assert.equal(m.marca, 50, 'escala 0-2 ×: el equilibrio en la mitad');
  assert.equal(m.relleno, 78);
  assert.equal(V.geoMedidor(0.5, 1).tono, 'error');
  assert.equal(V.geoMedidor(null, 1).sinDato, true);
  assert.equal(V.geoMedidor(3, 1).relleno, 89.3, 'la escala crece con el valor');
  assert.equal(V.geoMedidor(8.47, 13.22, { mayorEsMejor: false }).tono, 'ok', 'CPA: menor es mejor');
  assert.equal(V.geoMedidor(31.36, 15.74, { mayorEsMejor: false }).tono, 'error');
  assert.equal(V.tonoTasa(15.9, [8, 12]), 'ok');
  assert.equal(V.tonoTasa(5, [8, 12]), 'aviso');
  assert.equal(V.tonoTasa(3, [8, 12]), 'error');
  assert.equal(V.tonoTasa(9.5, [25, 30]), 'error');
  assert.equal(V.bandera('MX'), '\u{1F1F2}\u{1F1FD}');
  assert.equal(V.bandera('x'), '');
  assert.equal(V.nombrePais('BR'), 'Brasil');
  assert.equal(V.claseIdentidad(0), 'ng-id-1');
  assert.deepEqual(V.codigosPais('MX/BR'), ['MX', 'BR'], 'varios países: una bandera por cada uno');
  assert.deepEqual(V.codigosPais(null), []);
  assert.equal(V.nombresPais('MX, BR'), 'México y Brasil');
  assert.equal(V.claseIdentidad(7), 'ng-id-2');
});

test('acción sugerida y tiempo hasta el próximo cambio', () => {
  assert.equal(N.accion({ clave: 'escalar', texto: 'Escalar', tono: 'ok' }).icono, 'tendencia-sube');
  assert.equal(N.accion({ clave: 'cortar', texto: 'Cortar', tono: 'error' }).icono, 'x-circulo');
  assert.equal(N.accion(null).texto, 'Sin dato');
  assert.equal(N.faltaPara(6.3), 'en 6 h');
  assert.equal(N.faltaPara(0.4), 'en menos de una hora');
  assert.equal(N.faltaPara(72), 'en 3 días');
});

test('render de la cartera: 3 cifras, datos al, una fila por oferta con bandera, veredicto, 3 números y frase', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/negocio.js');
    assert.equal(pagina.meta.ruta, 'negocio');
    assert.equal(pagina.meta.grupo, 'El sistema');
    const ctx = ctxDe(datos);
    const raiz = await pagina.render(ctx);
    const t = texto(raiz);
    for (const s of ['Ganancia neta', 'Gasto en anuncios', 'ROAS neto', 'Datos al', '12/11/2026 20:00', 'contra Meta', 'ventas', 'Apagar', 'Mirar', 'Pausada', '65 USD/día + conjunto R3', 'Cómo se calcula', '?modo=completo']) assert.ok(t.includes(s), s);
    const filas = todos(raiz, (n) => n.localName === 'article' && /\bng-fila\b/.test(n.className));
    assert.equal(filas.length, datos.ofertas.length, 'una fila por oferta, no tarjetas');
    for (const [i, o] of datos.ofertas.entries()) {
      const f = filas.find((x) => texto(x).includes(o.nombre));
      assert.ok(f, o.nombre);
      assert.ok(f.className.includes(V.claseIdentidad(i)), `${o.nombre}: su color de identidad`);
      assert.ok(texto(f).includes(o.frase), `${o.nombre}: la frase corta`);
      assert.ok(o.frase.length <= 80);
      const enlace = todos(f, (n) => n.localName === 'a')[0];
      assert.equal(enlace.getAttribute('href'), `#/negocio/${o.id}`, 'toda la fila abre la ficha');
    }
    assert.equal(pagina.pastillaDe({ clave: 'pausada', texto: 'Pausada' }).clase, 'pausada');
    assert.equal(pagina.pastillaDe({ clave: 'mirar', texto: 'Mirar un día más' }).texto, 'Mirar', 'texto corto en la pastilla');
    assert.equal(pagina.pastillaDe({ clave: 'cortar', texto: 'Apagar' }).clase, 'apagar');
    // fuera de Negocio: barras por oferta, medidores, embudo, anuncios, ROAS Meta y real, rótulos de firma
    const visible = todos(raiz, (n) => /\bng-(filas|tres)\b/.test(n.className)).map(texto).join(' ');   // lo que se ve sin abrir «Cómo se calcula»
    assert.doesNotMatch(visible, /Comparar ofertas|Requiere tu atención|Qué está vendiendo|ROAS Meta|ROAS real|regla firmada|regla sin firmar|Llegan a pagar|Ganancia contra Meta por oferta/);
    assert.equal(todos(raiz, (n) => /\bng-med\b/.test(n.className)).length, 0, 'sin medidores en la lista');
    const flags = todos(raiz, (n) => /\bng-bandera\b/.test(n.className));
    assert.ok(flags.some((f) => f.getAttribute('aria-label') === 'México' && f.textContent === V.bandera('MX')), 'bandera con su nombre accesible');
    assert.ok(flags.some((f) => f.getAttribute('aria-label') === 'Brasil'));
    assert.equal(porTag(raiz, 'img').length, 0);
  } finally { restaurar(); }
});

test('render de la ficha: veredicto y 3 cifras, tabla de métricas con signos, embudo, anuncios, historial, ventas sin compradores y enlaces', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/negocio.js');
    const raiz = await pagina.render(ctxDe(datos, { params: { id: 'kit-uno' } }));
    const t = texto(raiz);
    for (const s of ['Mirar', 'Cada venta cuesta US$ 12,00 y deja US$ 11,67', 'Métricas del funnel', 'Facturación bruta', 'Comisiones e impuestos', 'Facturación neta', 'Meta', 'Producción', 'Fijos repartidos', 'Costos totales', 'Ganancia contra Meta (contribución)', 'Ganancia neta', 'ROAS Meta', 'ROAS bruto real', 'ROAS neto', 'ROAS real (retorno total)', '3 reales · 5 según Meta', 'Ticket medio', 'CPA real', 'CPA de equilibrio', 'La producción no entra en el ROAS', 'Embudo de la tienda', 'Visitas a la landing', 'Checkouts', 'llegan a pagar', 'CR de la tienda', 'Historial por día', 'Ventas (3)', 'Kit Uno Básico', 'Top 2 creativos', 'Todos los anuncios, conjunto por conjunto (3)', 'Gancho 3 s', 'Costo pago inic.', '1 ganador', 'el que más vende', 'ROAS neto est.', 'Clic → pago', 'Ven todo', 'Ganador', 'Flojo', 'Sin datos', 'conjunto en pausa', 'MX R3', 'Documentos y enlaces', 'Expediente del funnel', 'Programado mañana 00:00: 65 USD/día + conjunto R3']) assert.ok(t.includes(s), s);
    assert.equal(todos(raiz, (n) => /\bng-med\b/.test(n.className)).length, 1, 'un solo medidor: ROAS neto');
    assert.equal(todos(raiz, (n) => n.localName === 'table' && /ng-tabla-met/.test(n.className)).length, 1, 'métricas en una tabla de dos columnas');
    // regla de signo: lo que entra con «+», lo que sale con «−», resultados con su signo
    assert.ok(t.includes('+US$\u00a035,00'), 'facturación neta con +');
    assert.ok(t.includes('−US$\u00a011,00'), 'producción con −');
    assert.ok(t.includes('−US$\u00a01,00'), 'ganancia contra Meta negativa con −');
    assert.ok(t.includes('+US$\u00a014,00'), 'neto de una venta con +');
    assert.ok(t.includes('<img src=x onerror=alert(1)>'), 'el nombre hostil de un anuncio se ve como texto');
    const ganadoras = todos(raiz, (n) => n.localName === 'tr' && /ng-ad-ganador/.test(n.className));
    assert.equal(ganadoras.length, 2, 'la fila del ganador resaltada (en el top y en todos los anuncios)');
    assert.ok(texto(ganadoras[0]).includes('A01'));
    assert.ok(t.includes('−US$\u00a026,00'), 'gasto del anuncio con −');
    assert.equal(todos(raiz, (n) => /\bng-ad-tarjeta\b/.test(n.className)).length, 2, 'en móvil, una tarjeta por creativo del top');
    assert.doesNotMatch(t, /persona@ejemplo\.com|Persona Real/);
    const externos = todos(raiz, (n) => n.localName === 'a' && n.getAttribute('target') === '_blank');
    assert.equal(externos.length, 1, 'solo la tienda https; la landing http queda fuera');
    assert.equal(externos[0].getAttribute('href'), 'https://kit-uno.impultienda.ar/');
    assert.equal(externos[0].getAttribute('rel'), 'noopener noreferrer');
    const noEsta = await pagina.render(ctxDe(datos, { params: { id: 'no-existe' } }));
    assert.match(texto(noEsta), /Oferta no encontrada/);
  } finally { restaurar(); }
});

test('render vacío: explica de dónde salen los números', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/negocio.js');
    const raiz = await pagina.render(ctxDe({ ofertas: [], atencion: [] }, { vacio: true }));
    assert.match(texto(raiz), /Todavía no hay ofertas con números/);
    assert.match(texto(raiz), /revisión del funnel/);
  } finally { restaurar(); }
});

// ───────────────────────── filtro de período ─────────────────────────
import * as P from '../../dashboard/web/lib/negocio-periodo.js';

test('período: botones rápidos desde «hoy» de la cuenta (incluye mes anterior en enero y meses de 31)', () => {
  assert.deepEqual(P.rangoRapido('hoy', '2026-11-13'), { desde: '2026-11-13', hasta: '2026-11-13' });
  assert.deepEqual(P.rangoRapido('ayer', '2026-11-01'), { desde: '2026-10-31', hasta: '2026-10-31' });
  assert.deepEqual(P.rangoRapido('u7', '2026-11-13'), { desde: '2026-11-07', hasta: '2026-11-13' });
  assert.deepEqual(P.rangoRapido('u14', '2026-11-13'), { desde: '2026-10-31', hasta: '2026-11-13' });
  assert.deepEqual(P.rangoRapido('u30', '2026-11-13'), { desde: '2026-10-15', hasta: '2026-11-13' });
  assert.deepEqual(P.rangoRapido('mes', '2026-11-13'), { desde: '2026-11-01', hasta: '2026-11-13' });
  assert.deepEqual(P.rangoRapido('mes_ant', '2026-11-13'), { desde: '2026-10-01', hasta: '2026-10-31' });
  assert.deepEqual(P.rangoRapido('mes_ant', '2027-01-05'), { desde: '2026-12-01', hasta: '2026-12-31' });
  assert.deepEqual(P.rangoRapido('mes_ant', '2028-03-10'), { desde: '2028-02-01', hasta: '2028-02-29' }, 'año bisiesto');
  assert.equal(P.rangoRapido('inicio', '2026-11-13'), null);
  assert.equal(P.rapidoDe({ desde: '2026-11-07', hasta: '2026-11-13' }, '2026-11-13'), 'u7');
  assert.equal(P.rapidoDe(null, '2026-11-13'), 'inicio');
  assert.equal(P.rapidoDe({ desde: '2026-11-03', hasta: '2026-11-05' }, '2026-11-13'), null);
});

test('período en palabras', () => {
  const hoy = '2026-11-13';
  assert.equal(P.etiquetaPeriodo(null, hoy), 'Desde el inicio');
  assert.equal(P.etiquetaPeriodo({ desde: hoy, hasta: hoy }, hoy), 'Hoy, 13/11');
  assert.equal(P.etiquetaPeriodo({ desde: '2026-11-12', hasta: '2026-11-12' }, hoy), 'Ayer, 12/11');
  assert.equal(P.etiquetaPeriodo({ desde: '2026-11-05', hasta: '2026-11-05' }, hoy), '05/11');
  assert.equal(P.etiquetaPeriodo({ desde: '2026-11-06', hasta: '2026-11-12' }, hoy), '6-12 nov');
  assert.equal(P.etiquetaPeriodo({ desde: '2026-11-07', hasta: hoy }, hoy), 'Últimos 7 días (7-13 nov)');
  assert.equal(P.etiquetaPeriodo({ desde: '2026-10-28', hasta: '2026-11-03' }, hoy), '28 oct-3 nov');
  assert.equal(P.etiquetaPeriodo({ desde: '2026-10-01', hasta: '2026-10-31' }, hoy), 'Mes anterior (octubre)');
  assert.equal(P.etiquetaPeriodo({ desde: '2026-11-01', hasta: hoy }, hoy), 'Este mes (1-13 nov)');
});

test('período: la dirección manda, si no lo recordado; un clic elige un día y el segundo arma el rango', () => {
  const m = new Map();
  const almacen = { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v), removeItem: (k) => m.delete(k) };
  assert.equal(P.periodoPedido({}, almacen), null);
  P.recordarPeriodo({ desde: '2026-11-06', hasta: '2026-11-12' }, almacen);
  assert.deepEqual(P.periodoPedido({}, almacen), { desde: '2026-11-06', hasta: '2026-11-12' }, 'al navegar por el menú se mantiene');
  assert.deepEqual(P.periodoPedido({ desde: '2026-11-13', hasta: '2026-11-10' }, almacen), { desde: '2026-11-10', hasta: '2026-11-13' }, 'invertido se ordena');
  assert.equal(P.periodoPedido({ periodo: 'inicio' }, almacen), null);
  assert.deepEqual(P.periodoPedido({ desde: 'x', hasta: '2026-11-13' }, almacen), { desde: '2026-11-06', hasta: '2026-11-12' }, 'basura en la dirección: lo recordado');
  P.recordarPeriodo(null, almacen);
  assert.equal(P.periodoPedido({}, almacen), null);
  assert.equal(P.consultaPeriodo({ desde: '2026-11-12', hasta: '2026-11-13' }), '?desde=2026-11-12&hasta=2026-11-13');
  assert.equal(P.consultaPeriodo(null), '?periodo=inicio');
  const uno = P.clicEnDia('2026-11-10', null);
  assert.deepEqual(uno, { rango: { desde: '2026-11-10', hasta: '2026-11-10' }, pendiente: '2026-11-10' }, 'un clic: ese día');
  assert.deepEqual(P.clicEnDia('2026-11-05', '2026-11-10'), { rango: { desde: '2026-11-05', hasta: '2026-11-10' }, pendiente: null }, 'segundo clic antes: rango igual');
  const sem = P.semanasDelMes('2026-11');
  assert.equal(sem[0].indexOf('2026-11-01'), 6, 'noviembre 2026 empieza en domingo (semana de lunes a domingo)');
  assert.ok(sem.every((s) => s.length === 7));
  assert.equal(P.mesVecino('2026-01', -1), '2025-12');
});

test('render con período: selector, «veredicto con todos los días» y «—» sin datos', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/negocio.js');
    const conPeriodo = JSON.parse(JSON.stringify(datos));
    conPeriodo.periodo = { todo: false, desde: '2026-11-13', hasta: '2026-11-13', hoy: '2026-11-13', primer_dia: '2026-11-12', con_datos: false, zona: 'America/Argentina/Buenos_Aires' };
    for (const o of conPeriodo.ofertas) o.con_datos_periodo = false;
    const raiz = await pagina.render(ctxDe(conPeriodo, { params: { desde: '2026-11-13', hasta: '2026-11-13' } }));
    const t = texto(raiz);
    for (const s of ['Período', 'Hoy, 13/11', 'Hoy', 'Ayer', 'Últimos 7', 'Últimos 14', 'Últimos 30', 'Este mes', 'Mes anterior', 'Desde el inicio', 'Elegir días', 'veredicto con todos los días', 'Sin datos en este período']) assert.ok(t.includes(s), s);
    const activo = todos(raiz, (n) => n.localName === 'button' && n.getAttribute('aria-pressed') === 'true' && !/ng-tira__btn/.test(n.className));
    assert.equal(activo.length, 1);
    assert.equal(texto(activo[0]), 'Hoy');
    const cifras = todos(raiz, (n) => /\bng-cifra__valor\b/.test(n.className)).map(texto);
    assert.deepEqual(cifras, ['—', '—', '—'], 'sin datos: «—», nunca 0');
    const enlace = todos(raiz, (n) => n.localName === 'a' && /ng-fila__enlace/.test(n.className))[0];
    assert.match(enlace.getAttribute('href'), /\?desde=2026-11-13&hasta=2026-11-13$/, 'la ficha conserva el período');
    const ficha = await pagina.render(ctxDe(conPeriodo, { params: { id: 'kit-uno', desde: '2026-11-13', hasta: '2026-11-13' } }));
    assert.match(texto(ficha), /Sin datos en este período/);
    assert.match(texto(ficha), /veredicto con todos los días/);
  } finally { restaurar(); }
});

// ───────── etapa y backend (pedido del dueño, 13-nov) ─────────

test('etapas: conteo, filtro, grupos del menú y marca de backend', () => {
  const ofs = datos.ofertas;
  const c = E.contarEtapas(ofs);
  assert.equal(c.todas, 3);
  assert.equal(c.test, 1); assert.equal(c.apagada, 1, 'Mapa Dos está pausada en el fixture'); assert.equal(c.apagar, 1);
  assert.equal(c.con_backend, 1); assert.equal(c.falta_backend, 0);
  assert.deepEqual(E.filtrarOfertas(ofs, 'apagada').map((o) => o.nombre), ['Mapa Dos']);
  assert.equal(E.filtrarOfertas(ofs, 'renovando').length, 0);
  assert.deepEqual(E.filtrarOfertas(ofs, 'con_backend').map((o) => o.nombre), ['Mapa Dos']);
  assert.equal(E.filtrarOfertas(ofs, 'todas').length, 3);
  const g = E.gruposPorEtapa(ofs);
  assert.deepEqual(g.map((x) => x.etapa.clave), ['apagar', 'test', 'apagada'], 'lo urgente arriba, las apagadas al final');
  assert.equal(g[0].etapa.texto, 'Para apagar');
  assert.equal(E.claseBackend({ estado: 'activo' }), 'activo');
  assert.equal(E.claseBackend({ estado: 'no', falta: true }), 'falta');
  assert.equal(E.claseBackend(undefined), 'no');
  assert.equal(E.textoBackend({ estado: 'pausado', falta: true }), 'Backend en pausa');
  assert.match(E.detalleBackend(ofs.find((o) => o.nombre === 'Mapa Dos').backend), /Extra Uno \(US\$ 21\)/);
  assert.deepEqual(N.ordenarOfertas(ofs).map((o) => o.nombre), ['Camino Tres', 'Kit Uno', 'Mapa Dos'], 'la lista va por urgencia de la etapa');
});

test('render: cada fila lleva etapa y backend; la tira filtra la lista', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/negocio.js');
    const raiz = await pagina.render(ctxDe(datos));
    const chips = todos(raiz, (n) => /\bng-fila__chips\b/.test(n.className)).map(texto);
    assert.equal(chips.length, 3);
    assert.ok(chips.some((t) => t.includes('Apagada') && t.includes('Backend activo · 2 upsells')));
    assert.ok(chips.some((t) => t.includes('Test · día 1') && t.includes('Sin backend')));
    const tira = todos(raiz, (n) => /\bng-tira__btn\b/.test(n.className));
    assert.deepEqual(tira.map(texto).slice(0, 3), ['3Todas', '0Armada', '0Programada']);
    const boton = tira.find((b) => texto(b) === '1Apagada');
    for (const f of boton.eventos.click || []) f({ preventDefault() {}, stopPropagation() {} });
    const filas = todos(raiz, (n) => /\bng-fila\b/.test(n.className) && n.localName === 'article');
    assert.deepEqual(filas.map((f) => f.getAttribute('aria-label').split(':')[0]), ['Mapa Dos']);
    const ficha = await pagina.render(ctxDe(datos, { params: { id: 'mapa-dos' } }));
    const t = texto(ficha);
    for (const s of ['Etapa', 'Backend ofensivo', 'Extra Uno', 'R2: 10 anuncios, corriendo desde el 12/11']) assert.ok(t.includes(s), s);
  } finally { restaurar(); try { globalThis.localStorage && globalThis.localStorage.removeItem('negocio.filtroEtapa'); } catch (_) { /* nada */ } }
});

// ── Dónde corre la oferta original (referente_paises, 14-nov) ──
test('modeloReferentePaises: ordena, marca el choque con nuestro país y separa lo no medido', () => {
  const ficha = { referente_paises: { medido: '2026-11-14T12:40-03:00', paginas: [{ page_id: '1', nombre: 'X' }], paises: { AU: 9, GB: 47, US: 0 }, sin_anuncios: ['US', 'ES', 'MX'] } };
  const m = V.modeloReferentePaises(ficha, 'ES');
  assert.equal(m.medido, true);
  assert.deepEqual(m.corre.map((x) => x.cod), ['GB', 'AU']);
  assert.deepEqual(m.choque, []);
  assert.equal(m.sinAnuncios, 3);
  assert.deepEqual(V.modeloReferentePaises(ficha, 'GB').choque, ['GB']);
  assert.deepEqual(V.modeloReferentePaises(ficha, 'FR').nuestrosSinMirar, ['FR']);
  assert.equal(V.modeloReferentePaises({}, 'ES').medido, false);
  assert.equal(V.modeloReferentePaises(null, 'ES').medido, false);
});
test('modeloReferentePaises: con tope, el país que choca siempre queda a la vista', () => {
  const paises = Object.fromEntries(['US', 'GB', 'CA', 'AU', 'DE', 'FR', 'MX'].map((c, i) => [c, 100 - i]));
  const m = V.modeloReferentePaises({ referente_paises: { paises } }, 'MX', { tope: 3 });
  assert.deepEqual(m.visibles.map((x) => x.cod), ['US', 'GB', 'CA', 'MX']);
  assert.equal(m.resto, 3);
  assert.deepEqual(m.choque, ['MX']);
});
test('fechaMedicion y nombrePais con respaldo del navegador', () => {
  assert.equal(V.fechaMedicion('2026-11-14T12:40-03:00'), '14/11 12:40');
  assert.equal(V.fechaMedicion('x'), '');
  assert.equal(V.nombrePais('MX'), 'México');
  assert.ok(V.nombrePais('GB').length > 2);
});
