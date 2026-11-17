// lib/negocio-periodo.js — selector de período del tablero Negocio: botones rápidos y un calendario propio (sin librerías).
// Pedido del dueño (2026-11-12): «filtrar por un día específico de manera fácil sin poner inicio y finalización del rango, por rango,
// y hoy, ayer, últimos 7, 14 y 30, mes anterior y este mes». Un clic en un día elige ese día; otro clic elige hasta ese día (rango).
// Los días son los de la zona horaria de la cuenta publicitaria: «hoy» lo da el servidor (periodo.hoy), no el reloj del navegador.
// El período viaja en la dirección (#/negocio?desde=…&hasta=…) y se recuerda en este navegador (localStorage) como comodidad.

export const CLAVE_PERIODO = 'negocio.periodo';
const RX_DIA = /^\d{4}-\d{2}-\d{2}$/;
const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
const MES_CORTO = ['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sept', 'oct', 'nov', 'dic'];

/** «2026-11-12» → Date en UTC (solo para aritmética de días, sin zonas). */
export function aFecha(dia) { const [a, m, d] = dia.split('-').map(Number); return new Date(Date.UTC(a, m - 1, d)); }
export function aDia(f) { return f.toISOString().slice(0, 10); }
export function sumarDias(dia, n) { const f = aFecha(dia); f.setUTCDate(f.getUTCDate() + n); return aDia(f); }
export function esDia(x) { return typeof x === 'string' && RX_DIA.test(x) && !Number.isNaN(aFecha(x).getTime()); }

/** Botones rápidos, en orden. «inicio» = sin filtro (por defecto). */
export const RAPIDOS = [
  { id: 'hoy', texto: 'Hoy' }, { id: 'ayer', texto: 'Ayer' }, { id: 'u7', texto: 'Últimos 7' }, { id: 'u14', texto: 'Últimos 14' },
  { id: 'u30', texto: 'Últimos 30' }, { id: 'mes', texto: 'Este mes' }, { id: 'mes_ant', texto: 'Mes anterior' }, { id: 'inicio', texto: 'Desde el inicio' },
];

/** Rango de un botón rápido a partir de «hoy» (zona de la cuenta). → {desde, hasta} o null («Desde el inicio»). */
export function rangoRapido(id, hoy) {
  const [a, m] = hoy.split('-').map(Number);
  switch (id) {
    case 'hoy': return { desde: hoy, hasta: hoy };
    case 'ayer': { const d = sumarDias(hoy, -1); return { desde: d, hasta: d }; }
    case 'u7': return { desde: sumarDias(hoy, -6), hasta: hoy };
    case 'u14': return { desde: sumarDias(hoy, -13), hasta: hoy };
    case 'u30': return { desde: sumarDias(hoy, -29), hasta: hoy };
    case 'mes': return { desde: `${hoy.slice(0, 8)}01`, hasta: hoy };
    case 'mes_ant': {
      const primero = aDia(new Date(Date.UTC(m === 1 ? a - 1 : a, m === 1 ? 11 : m - 2, 1)));
      return { desde: primero, hasta: sumarDias(`${hoy.slice(0, 8)}01`, -1) };
    }
    default: return null;
  }
}

/** ¿Qué botón rápido corresponde a este rango? (para marcarlo) */
export function rapidoDe(rango, hoy) {
  if (!rango) return 'inicio';
  for (const r of RAPIDOS) {
    const x = rangoRapido(r.id, hoy);
    if (x && x.desde === rango.desde && x.hasta === rango.hasta) return r.id;
  }
  return null;
}

const dm = (dia) => `${dia.slice(8, 10)}/${dia.slice(5, 7)}`;
/** «6-12 nov», «28 oct-3 nov», «30 dic 2025-2 ene 2026». */
export function textoRango(desde, hasta) {
  const [a1, m1, d1] = desde.split('-').map(Number);
  const [a2, m2, d2] = hasta.split('-').map(Number);
  if (a1 !== a2) return `${d1} ${MES_CORTO[m1 - 1]} ${a1}-${d2} ${MES_CORTO[m2 - 1]} ${a2}`;
  if (m1 !== m2) return `${d1} ${MES_CORTO[m1 - 1]}-${d2} ${MES_CORTO[m2 - 1]}`;
  return `${d1}-${d2} ${MES_CORTO[m2 - 1]}`;
}

/** El período en palabras: «Desde el inicio», «Hoy, 12/11», «Ayer, 11/11», «12/11», «Últimos 7 días (6-12 nov)», «Mes anterior (octubre)». */
export function etiquetaPeriodo(rango, hoy) {
  if (!rango) return 'Desde el inicio';
  const { desde, hasta } = rango;
  if (desde === hasta) {
    if (desde === hoy) return `Hoy, ${dm(desde)}`;
    if (desde === sumarDias(hoy, -1)) return `Ayer, ${dm(desde)}`;
    return dm(desde);
  }
  const r = rapidoDe(rango, hoy);
  if (r === 'u7' || r === 'u14' || r === 'u30') return `Últimos ${r.slice(1)} días (${textoRango(desde, hasta)})`;
  if (r === 'mes') return `Este mes (${textoRango(desde, hasta)})`;
  if (r === 'mes_ant') return `Mes anterior (${MESES[Number(desde.slice(5, 7)) - 1]})`;
  return textoRango(desde, hasta);
}

/** Período pedido: primero la dirección (?desde&hasta, o ?periodo=inicio), después lo recordado. → {desde, hasta} o null. */
export function periodoPedido(params, almacen) {
  const p = params || {};
  if (p.periodo === 'inicio') return null;
  if (esDia(p.desde) && esDia(p.hasta)) return p.desde <= p.hasta ? { desde: p.desde, hasta: p.hasta } : { desde: p.hasta, hasta: p.desde };
  try {
    const g = almacen && almacen.getItem(CLAVE_PERIODO);
    if (g) { const x = JSON.parse(g); if (x && esDia(x.desde) && esDia(x.hasta)) return { desde: x.desde, hasta: x.hasta }; }
  } catch (_) { /* sin almacenamiento */ }
  return null;
}

export function recordarPeriodo(rango, almacen) {
  try { if (almacen) { if (rango) almacen.setItem(CLAVE_PERIODO, JSON.stringify(rango)); else almacen.removeItem(CLAVE_PERIODO); } } catch (_) { /* sin almacenamiento */ }
}

/** Parte de la dirección con el período: «?desde=…&hasta=…» o «?periodo=inicio». */
export function consultaPeriodo(rango) { return rango ? `?desde=${rango.desde}&hasta=${rango.hasta}` : '?periodo=inicio'; }

/** Semanas (lunes a domingo) de un mes «AAAA-MM» para el calendario: [[dia|null × 7]]. */
export function semanasDelMes(mes) {
  const primero = `${mes}-01`;
  const f = aFecha(primero);
  const desplazar = (f.getUTCDay() + 6) % 7;   // lunes = 0
  const dias = [];
  for (let i = 0; i < desplazar; i += 1) dias.push(null);
  for (let d = primero; d.slice(0, 7) === mes; d = sumarDias(d, 1)) dias.push(d);
  while (dias.length % 7) dias.push(null);
  const sem = [];
  for (let i = 0; i < dias.length; i += 7) sem.push(dias.slice(i, i + 7));
  return sem;
}
export function mesVecino(mes, n) { const [a, m] = mes.split('-').map(Number); const f = new Date(Date.UTC(a, m - 1 + n, 1)); return aDia(f).slice(0, 7); }
export function nombreMes(mes) { return `${MESES[Number(mes.slice(5, 7)) - 1]} ${mes.slice(0, 4)}`; }

/** Un clic en el calendario: sin día pendiente elige ese día (y lo deja pendiente); con día pendiente arma el rango. */
export function clicEnDia(dia, pendiente) {
  if (!pendiente) return { rango: { desde: dia, hasta: dia }, pendiente: dia };
  return { rango: dia < pendiente ? { desde: dia, hasta: pendiente } : { desde: pendiente, hasta: dia }, pendiente: null };
}

// ───────────────────────── vista ─────────────────────────

// estado del calendario que sobrevive a la navegación (elegir un día recarga la pantalla con el período nuevo)
const CAL = { abierto: false, mes: null, pendiente: null };

/**
 * Selector de período: etiqueta en palabras, botones rápidos y el calendario («Elegir días»).
 * `alElegir(rango|null)` cambia el período (la página navega a la dirección nueva).
 */
export function selectorPeriodo(ui, { rango, hoy, primerDia, alElegir }) {
  const { el } = ui;
  const marcado = rapidoDe(rango, hoy);
  const elegir = (r) => { alElegir(r); };
  const botones = el('div', { class: 'ng-per__rapidos', role: 'group', 'aria-label': 'Períodos rápidos' },
    RAPIDOS.map((r) => el('button', { type: 'button', class: ['ng-per__btn', marcado === r.id && 'ng-per__btn--activo'], 'aria-pressed': String(marcado === r.id),
      onclick: () => { CAL.abierto = false; CAL.pendiente = null; elegir(rangoRapido(r.id, hoy)); } }, r.texto)));
  const cal = el('div', { class: 'ng-cal', hidden: !CAL.abierto, role: 'dialog', 'aria-label': 'Elegir días' });
  const pintarCal = () => {
    const mes = CAL.mes || (rango ? rango.hasta : hoy).slice(0, 7);
    CAL.mes = mes;
    const enRango = (d) => rango && d >= rango.desde && d <= rango.hasta;
    ui.reemplazar(cal,
      el('div', { class: 'ng-cal__cab' },
        el('button', { type: 'button', class: 'btn btn--chico btn--icono', 'aria-label': 'Mes anterior', onclick: () => { CAL.mes = mesVecino(mes, -1); pintarCal(); } }, ui.icono('chevron-izquierda', { tam: 14 })),
        el('strong', { class: 'ng-cal__mes' }, nombreMes(mes)),
        el('button', { type: 'button', class: 'btn btn--chico btn--icono', 'aria-label': 'Mes siguiente', disabled: mes >= hoy.slice(0, 7) ? true : null, onclick: () => { CAL.mes = mesVecino(mes, 1); pintarCal(); } }, ui.icono('chevron-derecha', { tam: 14 }))),
      el('div', { class: 'ng-cal__grilla', role: 'grid' },
        ['L', 'M', 'M', 'J', 'V', 'S', 'D'].map((x) => el('span', { class: 'ng-cal__dow', 'aria-hidden': 'true' }, x)),
        semanasDelMes(mes).flat().map((d) => (d === null ? el('span', { class: 'ng-cal__vacio' }) : el('button', {
          type: 'button', role: 'gridcell',
          class: ['ng-cal__dia', enRango(d) && 'ng-cal__dia--rango', rango && (d === rango.desde || d === rango.hasta) && 'ng-cal__dia--borde',
            d === CAL.pendiente && 'ng-cal__dia--pendiente', d === hoy && 'ng-cal__dia--hoy', primerDia && d < primerDia && 'ng-cal__dia--antes'],
          disabled: d > hoy ? true : null, 'aria-label': `${Number(d.slice(8))} de ${nombreMes(d.slice(0, 7))}${d === hoy ? ' (hoy)' : ''}`, 'aria-selected': enRango(d) ? 'true' : 'false',
          onclick: () => { const r = clicEnDia(d, CAL.pendiente); CAL.pendiente = r.pendiente; CAL.abierto = r.pendiente !== null; elegir(r.rango); },
        }, String(Number(d.slice(8))))))),
      el('p', { class: 'ng-cal__ayuda' }, CAL.pendiente ? `Elegido el ${dm(CAL.pendiente)}. Toca otro día para hacer un rango.` : 'Un clic: ese día. Otro clic: hasta ese día.'),
      el('div', { class: 'ng-cal__pie' }, el('button', { type: 'button', class: 'btn btn--chico', onclick: () => { CAL.abierto = false; CAL.pendiente = null; cal.hidden = true; abrir.setAttribute('aria-expanded', 'false'); } }, 'Cerrar')));
  };
  const abrir = el('button', { type: 'button', class: ['ng-per__btn', 'ng-per__cal', marcado === null && 'ng-per__btn--activo'], 'aria-expanded': String(CAL.abierto),
    onclick: () => { CAL.abierto = !CAL.abierto; CAL.pendiente = null; CAL.mes = null; if (CAL.abierto) pintarCal(); cal.hidden = !CAL.abierto; abrir.setAttribute('aria-expanded', String(CAL.abierto)); } },
  ui.icono('reloj', { tam: 14 }), 'Elegir días');
  if (CAL.abierto) pintarCal();
  return el('section', { class: 'ng-per', 'aria-label': 'Período' },
    el('div', { class: 'ng-per__fila' },
      el('span', { class: 'ng-per__rot' }, 'Período'),
      el('strong', { class: 'ng-per__etiqueta' }, etiquetaPeriodo(rango, hoy))),
    el('div', { class: 'ng-per__controles' }, botones, abrir),
    cal);
}

export const CSS_PERIODO = `
.ng-per { display: grid; gap: var(--e-2); position: relative; }
.ng-per__fila { display: flex; align-items: baseline; gap: var(--e-2); flex-wrap: wrap; }
.ng-per__rot { color: var(--txt-2); font-size: var(--t-sm); }
.ng-per__etiqueta { font-size: var(--t-md); }
.ng-per__controles { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.ng-per__rapidos { display: flex; gap: 6px; flex-wrap: wrap; }
.ng-per__btn { display: inline-flex; align-items: center; gap: 5px; height: 30px; padding: 0 12px; border-radius: var(--r-pill); border: 1px solid var(--borde-fuerte); background: var(--sup); color: var(--txt); font: inherit; font-size: var(--t-sm); font-weight: 600; cursor: pointer; white-space: nowrap; }
.ng-per__btn:hover { background: var(--sup-2); }
.ng-per__btn--activo { background: var(--acento); border-color: var(--acento); color: var(--sobre-acento); }
.ng-per__btn--activo:hover { background: var(--acento-fuerte); }
.ng-cal { position: absolute; top: 100%; right: 0; z-index: 40; margin-top: 6px; width: 300px; max-width: calc(100vw - 32px); padding: var(--e-3); border-radius: var(--r-3); border: 1px solid var(--borde-fuerte); background: var(--elev); box-shadow: var(--sombra-2); display: grid; gap: var(--e-2); }
.ng-cal[hidden] { display: none; }
.ng-cal__cab { display: flex; align-items: center; justify-content: space-between; gap: var(--e-2); }
.ng-cal__mes { text-transform: capitalize; }
.ng-cal__grilla { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 2px; }
.ng-cal__dow { text-align: center; color: var(--txt-3); font-size: var(--t-xs); padding: 2px 0; }
.ng-cal__dia { height: 34px; border: 0; border-radius: var(--r-2); background: transparent; color: var(--txt); font: inherit; font-variant-numeric: tabular-nums; cursor: pointer; }
.ng-cal__dia:hover:not(:disabled) { background: var(--sup-3); }
.ng-cal__dia:disabled { color: var(--txt-3); opacity: .45; cursor: default; }
.ng-cal__dia--antes { color: var(--txt-3); }
.ng-cal__dia--hoy { box-shadow: inset 0 0 0 1px var(--acento); }
.ng-cal__dia--rango { background: var(--acento-bg); color: var(--txt); }
.ng-cal__dia--borde, .ng-cal__dia--pendiente { background: var(--acento); color: var(--sobre-acento); font-weight: 700; }
.ng-cal__ayuda { margin: 0; color: var(--txt-2); font-size: var(--t-xs); }
.ng-cal__pie { display: flex; justify-content: flex-end; }
@media (max-width: 640px) {
  .ng-per__controles { flex-wrap: nowrap; overflow-x: auto; padding-bottom: 2px; scrollbar-width: none; }
  .ng-per__rapidos { flex-wrap: nowrap; }
  .ng-cal { left: 0; right: auto; width: 100%; }
}
`;
