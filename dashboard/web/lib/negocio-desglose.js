// lib/negocio-desglose.js — «De dónde sale la ganancia» en #/negocio (cartera), debajo de los KPIs de arriba.
//
// Pedido del dueño (2026-11-15): «que aparezca ahí arriba un detalle de esa ganancia, oferta por oferta, cuáles ganaron, cuáles
// perdieron y todas las métricas y la información necesaria para tener noción de qué es lo que está haciendo que perdamos, que ganemos,
// qué está tirando para abajo, para arriba».
// Los números y el diagnóstico llegan hechos del servidor (dashboard/negocio.py → desglose): aquí solo se pintan. Respeta el período.
// Una celda lleva color SOLO si es una «palanca» (se sale de su referencia) y siempre con flecha ▲/▼: el color nunca es la única señal.

import { usd, pct, roas, numero } from './negocio.js';
import { banderas } from './negocio-visual.js';
import { chipEtapa } from './negocio-etapas.js';

export const CSS_DESGLOSE = `
.ngd { display: grid; gap: var(--e-4); }
.ngd-resumen { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--e-3); }
.ngd-tarjeta { display: grid; gap: 4px; align-content: start; padding: var(--e-3) var(--e-4); border-radius: var(--r-3); border: 1px solid var(--neutro-borde); background: var(--neutro-bg); min-width: 0; }
.ngd-tarjeta--ok { background: var(--ok-bg); border-color: var(--ok-borde); }
.ngd-tarjeta--error { background: var(--error-bg); border-color: var(--error-borde); }
.ngd-tarjeta__rot { display: flex; align-items: center; gap: 6px; color: var(--txt-2); font-size: var(--t-xs); font-weight: 650; text-transform: uppercase; letter-spacing: .03em; }
.ngd-tarjeta__valor { font-size: var(--t-xl, 1.6rem); font-weight: 750; font-variant-numeric: tabular-nums; white-space: nowrap; }
.ngd-tarjeta--ok .ngd-tarjeta__valor { color: var(--ok); } .ngd-tarjeta--error .ngd-tarjeta__valor { color: var(--error); }
.ngd-tarjeta__sub { color: var(--txt-2); font-size: var(--t-sm); }
.ngd-grupos { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.ngd-grupos li { display: flex; justify-content: space-between; gap: var(--e-3); font-size: var(--t-sm); }
.ngd-grupos li span:first-child { color: var(--txt-2); }
.ngd-grupos strong { font-variant-numeric: tabular-nums; white-space: nowrap; }

.ngd-dos { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: var(--e-4); align-items: start; }
.ngd-caja { padding: var(--e-3) var(--e-4); border: 1px solid var(--borde); border-radius: var(--r-3); background: var(--sup); display: grid; gap: var(--e-2); min-width: 0; }
.ngd-caja__tit { margin: 0; font-size: var(--t-sm); font-weight: 700; display: flex; align-items: center; gap: 6px; }
.ngd-cascada { display: grid; gap: 6px; }
.ngd-paso { display: grid; grid-template-columns: minmax(110px, 12em) minmax(90px, 1fr) minmax(9.5em, auto); align-items: center; gap: var(--e-3); font-size: var(--t-sm); }
.ngd-paso__pista { position: relative; height: 14px; border-radius: 4px; background: var(--neutro-bg); }
.ngd-paso__barra { position: absolute; top: 0; bottom: 0; border-radius: 4px; min-width: 2px; }
.ngd-paso--entra .ngd-paso__barra { background: var(--info); }
.ngd-paso--sale .ngd-paso__barra { background: var(--txt-3); opacity: .55; }
.ngd-paso--total.ngd-pos .ngd-paso__barra { background: var(--ok); } .ngd-paso--total.ngd-neg .ngd-paso__barra { background: var(--error); }
.ngd-paso--total { font-weight: 750; padding-top: 6px; border-top: 1px solid var(--borde); }
.ngd-paso__valor { font-variant-numeric: tabular-nums; white-space: nowrap; text-align: right; }
.ngd-paso__pct { color: var(--txt-3); font-size: var(--t-xs); margin-left: 4px; }
.ngd-paso__det { grid-column: 1 / -1; margin: -2px 0 4px; display: flex; flex-wrap: wrap; gap: 2px 14px; color: var(--txt-3); font-size: var(--t-xs); line-height: 1.45; font-variant-numeric: tabular-nums; }
.ngd-paso__item { white-space: nowrap; }
.ngd-paso__item::before { content: "↳ "; opacity: .6; }
.ngd-paso__regla { flex-basis: 100%; font-style: italic; opacity: .85; }
.ngd-paso .ayuda-btn { margin-left: 4px; vertical-align: middle; }
.ngd-patrones { display: grid; gap: var(--e-2); margin: 0; padding: 0; list-style: none; }
.ngd-patron { display: grid; gap: 2px; padding-left: 10px; border-left: 3px solid var(--error-borde); }
.ngd-patron strong { font-size: var(--t-sm); }
.ngd-patron span { color: var(--txt-2); font-size: var(--t-xs); }

.ngd-scroll { overflow-x: auto; border: 1px solid var(--borde); border-radius: var(--r-3); background: var(--sup); -webkit-overflow-scrolling: touch; }
.ngd-tabla { border-collapse: separate; border-spacing: 0; width: 100%; font-size: var(--t-sm); font-variant-numeric: tabular-nums; }
.ngd-tabla th, .ngd-tabla td { padding: 7px 10px; text-align: right; white-space: nowrap; border-bottom: 1px solid var(--borde); vertical-align: middle; }
.ngd-tabla thead th { position: sticky; top: 0; background: var(--sup-2); color: var(--txt-2); font-size: var(--t-xs); font-weight: 650; z-index: 1; }
.ngd-tabla thead tr.ngd-grupo th { text-align: center; text-transform: uppercase; letter-spacing: .04em; color: var(--txt-3); border-bottom: 0; padding-bottom: 0; }
.ngd-tabla th.ngd-sep, .ngd-tabla td.ngd-sep { border-left: 1px solid var(--borde); }
.ngd-tabla .ngd-of { position: sticky; left: 0; z-index: 2; background: var(--sup); text-align: left; min-width: 190px; max-width: 240px; white-space: normal; }
.ngd-tabla thead .ngd-of { background: var(--sup-2); z-index: 3; }
.ngd-tabla tbody tr:hover td { background: var(--sup-2); }
.ngd-tabla tr.ngd-subcab td { text-align: left; background: var(--sup-2); color: var(--txt-2); font-size: var(--t-xs); font-weight: 650; text-transform: uppercase; letter-spacing: .04em; }
.ngd-tabla tr.ngd-subcab td.ngd-of { background: var(--sup-2); }
.ngd-tabla tr.ngd-sinpauta td { color: var(--txt-2); padding-top: 4px; padding-bottom: 4px; }
.ngd-of__nombre { display: flex; align-items: center; gap: 6px; font-weight: 700; }
.ngd-of__nombre a { color: inherit; text-decoration: none; } .ngd-of__nombre a:hover { text-decoration: underline; }
.ngd-of .ng-etapa { margin-top: 3px; }
.ngd-res { display: grid; grid-template-columns: 70px auto; align-items: center; gap: 8px; justify-content: end; }
.ngd-div { position: relative; height: 10px; background: var(--neutro-bg); border-radius: 3px; }
.ngd-div::after { content: ''; position: absolute; left: 50%; top: -2px; bottom: -2px; width: 1px; background: var(--borde-fuerte); }
.ngd-div__b { position: absolute; top: 0; bottom: 0; border-radius: 3px; min-width: 2px; }
.ngd-div__b--pos { left: 50%; background: var(--ok); } .ngd-div__b--neg { right: 50%; background: var(--error); }
.ngd-pos { color: var(--ok); } .ngd-neg { color: var(--error); }
.ngd-sub { display: block; color: var(--txt-3); font-size: var(--t-xs); font-weight: 400; }
.ngd-motivo { text-align: left !important; white-space: normal !important; min-width: 300px; max-width: 420px; }
.ngd-motivo p { margin: 0 0 4px; }
.ngd-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.ngd-chip { display: inline-flex; align-items: center; gap: 3px; padding: 1px 7px; border-radius: var(--r-pill); font-size: var(--t-xs); font-weight: 650; border: 1px solid; cursor: help; }
.ngd-chip--sube { color: var(--ok); background: var(--ok-bg); border-color: var(--ok-borde); }
.ngd-chip--baja { color: var(--error); background: var(--error-bg); border-color: var(--error-borde); }
.ngd-tabla tfoot td { font-weight: 750; background: var(--sup-2); border-bottom: 0; }
.ngd-tabla tfoot .ngd-of { background: var(--sup-2); }
.ngd-pie { color: var(--txt-2); font-size: var(--t-xs); margin: 0; max-width: 110ch; }
@media (max-width: 1250px) { .ngd-dos { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 900px) { .ngd-resumen { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 560px) { .ngd-paso { grid-template-columns: minmax(0, 1fr) auto; } .ngd-paso__pista { grid-column: 1 / -1; grid-row: 2; } .ngd-tabla .ngd-of { min-width: 150px; } }
`;

const esNum = (x) => typeof x === 'number' && Number.isFinite(x);
const tono = (x) => (esNum(x) && x !== 0 ? (x > 0 ? 'ngd-pos' : 'ngd-neg') : null);
const flecha = (sentido) => (sentido === 'sube' ? '▲' : '▼');

const PASOS = {
  anuncio: 'Anuncio', trafico: 'Tráfico', landing: 'Landing', checkout: 'Checkout', backend: 'Ticket', costos: 'Costos', venta: 'Venta',
};
const PATRON_TEXTO = {
  compra: 'Se caen en el checkout', checkout: 'La landing no lleva al pago', cr: 'Convierte poco la visita', llegada: 'Se pierden clics antes de la landing',
  ctr: 'Los anuncios enganchan poco', cpm: 'Tráfico caro (CPM alto)', costo_visita: 'Cada visita sale cara', aov: 'El ticket no sube (sin bump ni upsell)',
};

/** Modelo listo para pintar (también lo usan las pruebas): palanca por columna y totales. */
export function modeloDesglose(dg, cartera) {
  if (!dg || !Array.isArray(dg.filas)) return null;
  const filas = dg.filas.map((f) => {
    const por = Object.fromEntries((f.palancas || []).map((p) => [p.clave, p]));
    return { ...f, por };
  });
  const maxAbs = Math.max(1, ...filas.map((f) => Math.abs(f.ganancia_neta || 0)));
  const c = cartera || {};
  return { filas, maxAbs, total: {
    ganancia_neta: c.ganancia_neta, contra_meta: c.neto_menos_meta, gasto: c.gasto_meta, neto: c.neto, produccion: c.produccion,
    ventas: c.ventas, cpa: c.cpa_medio, equilibrio: c.equilibrio_medio, roas_neto: c.roas_neto, aov: c.aov,
  } };
}

function chipPalanca(ui, p) {
  return ui.el('span', { class: ['ngd-chip', `ngd-chip--${p.sentido}`], title: `${PASOS[p.paso] || p.paso}: ${p.detalle}` }, `${flecha(p.sentido)} ${p.corto}`);
}

/** Celda con valor que se colorea solo si la palanca de esa métrica existe. */
function celda(ui, texto, p, { sub, sep } = {}) {
  const { el } = ui;
  return el('td', { class: [sep && 'ngd-sep'], title: p ? p.detalle : null },
    p ? el('span', { class: p.sentido === 'sube' ? 'ngd-pos' : 'ngd-neg' }, `${flecha(p.sentido)} ${texto}`) : texto,
    sub ? el('span', { class: 'ngd-sub' }, sub) : null);
}

function barraDivergente(ui, x, maxAbs) {
  const { el } = ui;
  const b = el('span', { class: ['ngd-div__b', (x || 0) >= 0 ? 'ngd-div__b--pos' : 'ngd-div__b--neg'] });
  b.style.width = `${(50 * Math.min(1, Math.abs(x || 0) / maxAbs)).toFixed(2)}%`;
  return el('span', { class: 'ngd-div', 'aria-hidden': 'true' }, b);
}

function tarjetas(ui, dg) {
  const { el } = ui;
  const r = dg.resumen || {};
  const grupos = (dg.grupos || []).filter((g) => g.ofertas);
  return el('div', { class: 'ngd-resumen' },
    el('div', { class: ['ngd-tarjeta', r.ganan ? 'ngd-tarjeta--ok' : null] },
      el('span', { class: 'ngd-tarjeta__rot' }, ui.icono('tendencia-sube', { tam: 14 }), `Ganan · ${r.ganan || 0} ${r.ganan === 1 ? 'oferta' : 'ofertas'}`),
      el('span', { class: 'ngd-tarjeta__valor' }, usd(r.ganan_usd || 0, { signo: true })),
      el('span', { class: 'ngd-tarjeta__sub' }, r.mejor ? `La que más suma: ${r.mejor.nombre} (${usd(r.mejor.usd, { signo: true })})` : 'Ninguna oferta gana en este período')),
    el('div', { class: ['ngd-tarjeta', r.pierden ? 'ngd-tarjeta--error' : null] },
      el('span', { class: 'ngd-tarjeta__rot' }, ui.icono('tendencia-baja', { tam: 14 }), `Pierden · ${r.pierden || 0} ${r.pierden === 1 ? 'oferta' : 'ofertas'}`),
      el('span', { class: 'ngd-tarjeta__valor' }, usd(r.pierden_usd || 0, { signo: true })),
      el('span', { class: 'ngd-tarjeta__sub' }, r.peor ? `La que más resta: ${r.peor.nombre} (${usd(r.peor.usd, { signo: true })})` : 'Ninguna oferta pierde en este período')),
    el('div', { class: 'ngd-tarjeta' },
      el('span', { class: 'ngd-tarjeta__rot' }, ui.icono('lista', { tam: 14 }), 'Por etapa'),
      el('ul', { class: 'ngd-grupos' }, grupos.map((g) => el('li', { title: g.ayuda },
        el('span', null, `${g.texto} (${g.ofertas})`), el('strong', { class: tono(g.ganancia_neta) }, usd(g.ganancia_neta, { signo: true })))))));
}

function cascada(ui, dg) {
  const { el } = ui;
  const pasos = dg.cascada || [];
  const bruto = Math.max(1, Math.abs((pasos[0] || {}).usd || 0));
  let acumulado = 0;
  const filas = pasos.map((p) => {
    const v = p.usd || 0;
    let ini;
    let fin;
    if (p.tipo === 'entra') { ini = 0; fin = v; acumulado = v; } else if (p.tipo === 'sale') { ini = acumulado + v; fin = acumulado; acumulado += v; } else { ini = Math.min(0, v); fin = Math.max(0, v); }
    // la escala va de min(0, lo más bajo) a bruto; con pérdida, la barra del total se dibuja hacia la izquierda del cero
    return { p, v, ini, fin };
  });
  const minimo = Math.min(0, ...filas.map((f) => f.ini));
  const rango = bruto - minimo || 1;
  const x = (n) => (100 * (n - minimo)) / rango;
  return el('div', { class: 'ngd-caja' },
    el('h3', { class: 'ngd-caja__tit' }, ui.icono('dinero', { tam: 15 }), 'De la facturación a la ganancia'),
    el('div', { class: 'ngd-cascada', role: 'table', 'aria-label': 'Cascada de la ganancia' }, filas.map(({ p, v, ini, fin }) => {
      const barra = el('span', { class: 'ngd-paso__barra' });
      barra.style.left = `${x(Math.min(ini, fin)).toFixed(2)}%`;
      barra.style.width = `${Math.max(0.4, x(Math.max(ini, fin)) - x(Math.min(ini, fin))).toFixed(2)}%`;
      const share = p.tipo === 'sale' && bruto > 1 ? `${numero((100 * Math.abs(v)) / bruto, 0)} %` : null;
      return el('div', { class: ['ngd-paso', `ngd-paso--${p.tipo}`, p.tipo === 'total' && tono(v), p.detalle && 'ngd-paso--con-det'], role: 'row' },
        el('span', { role: 'cell' }, p.texto, p.fuente ? ui.ayuda({ titulo: `De dónde sale: ${p.texto}`, texto: p.fuente }) : null),
        el('span', { class: 'ngd-paso__pista', role: 'presentation' }, barra),
        el('span', { class: 'ngd-paso__valor', role: 'cell' }, p.tipo === 'sale' ? usd(-Math.abs(v)) : usd(v, { signo: p.tipo === 'total' }),
          share ? el('span', { class: 'ngd-paso__pct' }, share) : null),
        p.detalle ? el('span', { class: 'ngd-paso__det', role: 'cell' },
          String(p.detalle).split(' — ')[0].split(' · ').map((x) => el('span', { class: 'ngd-paso__item' }, x)),
          String(p.detalle).includes(' — ') ? el('span', { class: 'ngd-paso__regla' }, String(p.detalle).split(' — ')[1]) : null) : null);
    })),
    el('p', { class: 'ngd-pie' }, 'El porcentaje es sobre la facturación bruta: de cada 100 que se cobran, cuánto se va en cada costo.'));
}

function patrones(ui, dg) {
  const { el } = ui;
  const ps = (dg.patrones || []).filter((p) => p.n);
  return el('div', { class: 'ngd-caja' },
    el('h3', { class: 'ngd-caja__tit' }, ui.icono('alerta', { tam: 15 }), 'Lo que se repite en las que pierden'),
    ps.length
      ? el('ul', { class: 'ngd-patrones' }, ps.map((p) => el('li', { class: 'ngd-patron' },
        el('strong', null, `${PATRON_TEXTO[p.clave] || p.clave} · ${p.n} ${p.n === 1 ? 'oferta' : 'ofertas'}`),
        el('span', null, `${p.ofertas.join(', ')} · juntas ${usd(p.usd, { signo: true })}`))))
      : el('p', { class: 'ngd-pie' }, 'Ninguna métrica del embudo se sale de su referencia en las ofertas que pierden: o no hay pérdidas, o falta volumen para verlo.'));
}

function tabla(ui, m, dg, hrefOferta) {
  const { el } = ui;
  const med = dg.medianas || {};
  const th = (t, { sub, sep, of } = {}) => el('th', { scope: 'col', class: [sep && 'ngd-sep', of && 'ngd-of'] }, t, sub ? el('span', { class: 'ngd-sub' }, sub) : null);
  const head = el('thead', null,
    el('tr', { class: 'ngd-grupo' },
      el('th', { class: 'ngd-of' }, ''), el('th', { colspan: '3' }, 'Resultado'), el('th', { colspan: '3', class: 'ngd-sep' }, 'Dinero'),
      el('th', { colspan: '4', class: 'ngd-sep' }, 'Venta'), el('th', { colspan: '7', class: 'ngd-sep' }, 'Del anuncio a la compra'), el('th', { class: 'ngd-sep' }, '')),
    el('tr', null,
      th('Oferta', { of: true }), th('Ganancia neta', { sub: 'con producción y fijos' }), th('Contra Meta', { sub: 'neto − anuncios' }), th('Peso', { sub: 'del total' }),
      th('Gasto Meta', { sep: true }), th('Fact. neta', { sub: 'tras comisiones' }), th('Producción'),
      th('Ventas', { sep: true }), th('CPA', { sub: 'vs equilibrio' }), th('ROAS neto'), th('AOV', { sub: '× principal (ref. 1,5)' }),
      th('CTR', { sep: true, sub: `mediana ${pct(med.ctr, 2)}` }), th('CPM', { sub: `mediana ${usd(med.cpm)}` }), th('Costo visita', { sub: `mediana ${usd(med.costo_visita)}` }),
      th('Llegada', { sub: 'visitas ÷ clics' }), th('Checkout', { sub: 'ref. 8-12 %' }), th('Compra', { sub: 'ref. 25-30 %' }), th('CR', { sub: 'ref. 2-3,6 %' }),
      th('Qué lo explica', { sep: true })));
  const fila = (f) => {
    const p = f.por;
    const chips = (f.palancas || []).filter((x) => x.clave !== 'cpa').slice(0, 4);
    return el('tr', null,
      el('td', { class: 'ngd-of' },
        el('div', { class: 'ngd-of__nombre' }, banderas(ui, f.mercado), el('a', { href: hrefOferta(f.id) }, f.nombre)),
        chipEtapa(ui, f.etapa)),
      el('td', null, el('span', { class: 'ngd-res' }, barraDivergente(ui, f.ganancia_neta, m.maxAbs), el('strong', { class: tono(f.ganancia_neta) }, usd(f.ganancia_neta, { signo: true })))),
      el('td', { class: tono(f.contra_meta) }, f.gasto ? usd(f.contra_meta, { signo: true }) : '—'),
      el('td', { class: tono(f.peso_pct) }, esNum(f.peso_pct) && f.peso_pct ? pct(f.peso_pct, 0) : '—'),
      el('td', { class: 'ngd-sep' }, f.gasto ? usd(-Math.abs(f.gasto)) : '—'),
      el('td', null, f.neto ? usd(f.neto) : '—'),
      el('td', null, f.produccion ? usd(-Math.abs(f.produccion)) : '—'),
      el('td', { class: 'ngd-sep' }, numero(f.ventas, 0)),
      celda(ui, esNum(f.cpa) ? usd(f.cpa) : (p.sin_ventas ? 'sin ventas' : '—'), p.cpa || p.sin_ventas, { sub: esNum(f.equilibrio) ? `eq. ${usd(f.equilibrio)}${f.equilibrio_fuente === 'estimado' ? ' (est.)' : ''}` : null }),
      el('td', { class: f.gasto ? tono((f.roas_neto || 0) - 1) : null }, f.gasto ? roas(f.roas_neto) : '—'),
      celda(ui, esNum(f.aov) ? usd(f.aov) : '—', p.aov, { sub: esNum(f.aov_veces) ? `${numero(f.aov_veces)} ×` : null }),
      celda(ui, esNum(f.ctr) ? pct(f.ctr, 2) : '—', p.ctr, { sep: true, sub: f.impresiones ? `${numero(f.impresiones, 0)} impr.` : null }),
      celda(ui, esNum(f.cpm) ? usd(f.cpm) : '—', p.cpm),
      celda(ui, esNum(f.costo_visita) ? usd(f.costo_visita) : '—', p.costo_visita),
      celda(ui, esNum(f.llegada) ? pct(100 * f.llegada, 0) : '—', p.llegada, { sub: f.clics ? `${numero(f.visitas || 0, 0)} de ${numero(f.clics, 0)}` : null }),
      celda(ui, esNum(f.pct_checkout) ? pct(f.pct_checkout) : '—', p.checkout, { sub: esNum(f.checkouts) ? `${numero(f.checkouts, 0)} checkouts` : null }),
      celda(ui, esNum(f.pct_compra) ? pct(f.pct_compra, 0) : '—', p.compra),
      celda(ui, esNum(f.cr) ? pct(f.cr, 2) : '—', p.cr),
      el('td', { class: ['ngd-motivo', 'ngd-sep'] }, el('p', null, f.motivo || ''), chips.length ? el('div', { class: 'ngd-chips' }, chips.map((x) => chipPalanca(ui, x))) : null));
  };
  // las que todavía no tienen pauta (solo pesa la producción) van al final, en un renglón compacto cada una
  const conPauta = m.filas.filter((f) => f.gasto || f.ventas);
  const sinPauta = m.filas.filter((f) => !f.gasto && !f.ventas);
  const prodSin = sinPauta.reduce((a, f) => a + (f.produccion || 0), 0);
  const filaSin = (f) => el('tr', { class: 'ngd-sinpauta' },
    el('td', { class: 'ngd-of' }, el('div', { class: 'ngd-of__nombre' }, banderas(ui, f.mercado), el('a', { href: hrefOferta(f.id) }, f.nombre)), chipEtapa(ui, f.etapa)),
    el('td', { class: tono(f.ganancia_neta) }, usd(f.ganancia_neta, { signo: true })), el('td', null, '—'), el('td', null, '—'),
    el('td', { class: 'ngd-sep' }, '—'), el('td', null, '—'), el('td', null, f.produccion ? usd(-Math.abs(f.produccion)) : '—'),
    el('td', { class: 'ngd-sep', colspan: '11' }, ''), el('td', { class: ['ngd-motivo', 'ngd-sep'] }, f.motivo || ''));
  const filas = [
    ...conPauta.map(fila),
    sinPauta.length ? el('tr', { class: 'ngd-subcab' }, el('td', { class: 'ngd-of' }, `Todavía sin pauta (${sinPauta.length})`),
      el('td', { colspan: '18' }, `Solo pesa la producción ya pagada: ${usd(-prodSin)} en total.`)) : null,
    ...sinPauta.map(filaSin),
  ].filter(Boolean);
  const t = m.total;
  const pie = el('tfoot', null, el('tr', null,
    el('td', { class: 'ngd-of' }, 'Toda la cartera'),
    el('td', { class: tono(t.ganancia_neta) }, usd(t.ganancia_neta, { signo: true })),
    el('td', { class: tono(t.contra_meta) }, usd(t.contra_meta, { signo: true })),
    el('td', null, ''),
    el('td', { class: 'ngd-sep' }, usd(-Math.abs(t.gasto || 0))), el('td', null, usd(t.neto)), el('td', null, usd(-Math.abs(t.produccion || 0))),
    el('td', { class: 'ngd-sep' }, numero(t.ventas || 0, 0)),
    el('td', { class: esNum(t.cpa) && esNum(t.equilibrio) ? (t.cpa <= t.equilibrio ? 'ngd-pos' : 'ngd-neg') : null }, esNum(t.cpa) ? usd(t.cpa) : '—', esNum(t.equilibrio) ? el('span', { class: 'ngd-sub' }, `eq. ${usd(t.equilibrio)}`) : null),
    el('td', { class: tono((t.roas_neto || 0) - 1) }, roas(t.roas_neto)),
    el('td', null, esNum(t.aov) ? usd(t.aov) : '—'),
    el('td', { class: 'ngd-sep', colspan: '7' }, ''), el('td', { class: 'ngd-sep' }, '')));
  return el('div', { class: 'ngd-scroll', tabindex: '0', role: 'region', 'aria-label': 'Desglose por oferta (se desliza de lado)' },
    el('table', { class: 'ngd-tabla' }, head, el('tbody', null, filas), pie));
}

/** Sección completa. `d`: respuesta de /api/negocio (con `desglose`). */
export function seccionDesglose(ctx, d, hrefOferta) {
  const { ui } = ctx;
  const { el } = ui;
  const dg = d && d.desglose;
  const m = modeloDesglose(dg, d && d.cartera);
  if (!m || !m.filas.length) return null;
  const p = d.periodo || {};
  const cuando = p.todo || !p.desde ? 'desde el inicio' : (p.desde === p.hasta ? `el ${p.desde.slice(8, 10)}/${p.desde.slice(5, 7)}` : `del ${p.desde.slice(8, 10)}/${p.desde.slice(5, 7)} al ${p.hasta.slice(8, 10)}/${p.hasta.slice(5, 7)}`);
  return ui.seccion('De dónde sale la ganancia', el('div', { class: 'ngd' },
    tarjetas(ui, dg),
    el('div', { class: 'ngd-dos' }, cascada(ui, dg), patrones(ui, dg)),
    tabla(ui, m, dg, hrefOferta),
    el('p', { class: 'ngd-pie' },
      `Ordenadas de la que más suma a la que más resta, ${cuando}. ▲ empuja para arriba y ▼ tira para abajo: una cifra lleva color solo cuando se sale de su referencia (las del dueño para checkout, compra, CR, AOV y CPA; la mediana de la cartera para CTR, CPM y costo por visita). `,
      'Pasá el mouse sobre una cifra o una etiqueta para leer la explicación.',
      dg.sin_movimiento ? ` ${dg.sin_movimiento} ${dg.sin_movimiento === 1 ? 'oferta no tuvo' : 'ofertas no tuvieron'} movimiento en el período.` : '')),
  { ayuda: `Oferta por oferta: cuánto gana o pierde, en qué se va la plata y en qué paso del embudo se gana o se pierde, ${cuando}.` });
}
