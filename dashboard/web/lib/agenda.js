// lib/agenda.js — agenda de cada oferta (ficha) y «Lo que viene» del sistema (cartera) en el tablero Negocio.
//
// Pedido del dueño (14-nov): «que se agregue al dashboard en cada oferta los siguientes pasos (en tiempo real) de lo que está programado…
// para yo que estoy auditando y monitorizando tener un lugar para saber qué se programó, qué se está aplicando, qué se está por hacer,
// qué se hizo». El servidor arma los renglones (dashboard/agenda.py); acá solo se dibujan. En vivo: el tablero se vuelve a pintar cuando
// cambia un archivo de ofertas/_funnels/ (eventos del servidor), los «en 2 h» se actualizan cada 30 s y, cuando llega la hora de un
// renglón que viene, la página se recarga para que pase a «en curso» o «hecho».

const ZONA = 'America/Argentina/Buenos_Aires';
const DIAS = ['dom', 'lun', 'mar', 'mié', 'jue', 'vie', 'sáb'];

function partes(fecha) {
  const f = new Intl.DateTimeFormat('es-AR', { timeZone: ZONA, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false, weekday: 'short' });
  const o = {};
  for (const p of f.formatToParts(fecha)) o[p.type] = p.value;
  return { dia: `${o.year}-${o.month}-${o.day}`, dd: o.day, mm: o.month, hora: `${o.hour === '24' ? '00' : o.hour}:${o.minute}` };
}

/** «hoy 20:00», «mañana 08:35», «ayer 17:09», «sáb 16/11 09:02» (hora de Argentina). */
export function horaAgenda(iso, ahora = new Date()) {
  if (!iso) return '';
  const f = new Date(iso);
  if (Number.isNaN(f.getTime())) return '';
  const a = partes(f);
  const hoy = partes(ahora).dia;
  const dif = Math.round((Date.parse(`${a.dia}T00:00:00Z`) - Date.parse(`${hoy}T00:00:00Z`)) / 86400000);
  const dia = dif === 0 ? 'hoy' : dif === 1 ? 'mañana' : dif === -1 ? 'ayer' : `${DIAS[new Date(`${a.dia}T12:00:00Z`).getUTCDay()]} ${a.dd}/${a.mm}`;
  return `${dia} ${a.hora}`;
}

/** «en 2 h 35 min», «en 4 min», «hace 3 h», «ahora». */
export function relativo(iso, ahora = new Date()) {
  if (!iso) return '';
  const ms = new Date(iso).getTime() - ahora.getTime();
  if (Number.isNaN(ms)) return '';
  const min = Math.round(Math.abs(ms) / 60000);
  if (min < 1) return 'ahora';
  let t;
  if (min < 60) t = `${min} min`;
  else if (min < 48 * 60) { const h = Math.floor(min / 60); const m = min % 60; t = m && h < 10 ? `${h} h ${m} min` : `${h} h`; } else t = `${Math.round(min / 1440)} días`;
  return ms > 0 ? `en ${t}` : `hace ${t}`;
}

const TONO = { ok: 'ok', aviso: 'aviso', error: 'error', info: 'info' };
const GRUPOS = [
  { tipo: 'en_curso', titulo: 'Ahora', icono: 'progreso', vacio: null },
  { tipo: 'te_toca', titulo: 'Te toca a vos', icono: 'usuario', vacio: null },
  { tipo: 'proximo', titulo: 'Lo que viene', icono: 'reloj', vacio: 'Nada programado por ahora.' },
  { tipo: 'condicion', titulo: 'Lo que hoy no va a pasar', icono: 'info', vacio: null },
];

function renglon(ui, i, { href = null } = {}) {
  const { el } = ui;
  const cuando = i.tipo === 'en_curso' && i.hasta ? i.hasta : i.cuando;
  const rot = i.tipo === 'en_curso' && i.hasta ? 'hasta ' : '';
  return el('li', { class: ['ag-item', `ag-item--${TONO[i.tono] || 'info'}`, `ag-item--${i.tipo}`] },
    el('div', { class: 'ag-cuando' },
      cuando ? el('span', { class: 'ag-hora', 'data-ag-hora': cuando }, `${rot}${horaAgenda(cuando)}`) : el('span', { class: 'ag-hora ag-hora--sin' }, i.tipo === 'te_toca' ? 'cuando puedas' : '—'),
      cuando ? el('span', { class: 'ag-rel', 'data-ag-rel': cuando }, relativo(cuando)) : null),
    el('span', { class: 'ag-punto', 'aria-hidden': 'true' }),
    el('div', { class: 'ag-cuerpo' },
      el('div', { class: 'ag-tit' },
        href && i.oferta ? el('a', { class: 'ag-oferta', href: href(i.oferta_id) }, i.oferta) : null,
        el('span', null, i.titulo),
        i.recurrente ? el('span', { class: 'ag-chip', title: 'Se repite: es la próxima de una tarea periódica.' }, ui.icono('refrescar', { tam: 11 }), 'se repite') : null),
      i.detalle ? el('div', { class: 'ag-det' }, i.detalle) : null,
      i.quien ? el('div', { class: 'ag-quien' }, i.quien) : null));
}

/** Ficha: «Agenda» de la oferta: ahora, te toca, lo que viene, lo que hoy no pasa y lo que ya se hizo. */
export function seccionAgenda(ctx, o) {
  const { ui } = ctx;
  const { el } = ui;
  instalar(ctx);
  const ag = Array.isArray(o.agenda) ? o.agenda : [];
  const hechos = ag.filter((i) => i.tipo === 'hecho');
  const bloques = GRUPOS.map((g) => {
    const lista = ag.filter((i) => i.tipo === g.tipo);
    if (!lista.length && !g.vacio) return null;
    return el('div', { class: ['ag-grupo', `ag-grupo--${g.tipo}`] },
      el('h3', { class: 'ag-grupo__tit' }, ui.icono(g.icono, { tam: 14 }), g.titulo),
      lista.length ? el('ol', { class: 'ag-lista' }, lista.map((i) => renglon(ui, i))) : el('p', { class: 'ag-vacio' }, g.vacio));
  });
  const visibles = hechos.slice(0, 4);
  const resto = hechos.slice(4);
  bloques.push(el('div', { class: 'ag-grupo ag-grupo--hecho' },
    el('h3', { class: 'ag-grupo__tit' }, ui.icono('check', { tam: 14 }), 'Lo que ya se hizo'),
    hechos.length ? el('ol', { class: 'ag-lista' }, visibles.map((i) => renglon(ui, i))) : el('p', { class: 'ag-vacio' }, 'Todavía nada registrado.'),
    resto.length ? el('details', { class: 'ag-mas' }, el('summary', null, `Ver ${resto.length} más`), el('ol', { class: 'ag-lista' }, resto.map((i) => renglon(ui, i)))) : null));
  return ui.seccion('Agenda: qué está pasando y qué viene', el('div', { class: 'ag', 'data-ag-vivo': '1' },
    el('p', { class: 'ag-nota' }, 'Horas de Argentina. Se actualiza sola cuando una tarea escribe algo y cuando llega la hora de lo programado.'),
    ...bloques.filter(Boolean)));
}

/** Cartera: lo próximo de todas las ofertas y las tareas automáticas (cuándo corren y cómo les fue la última vez). */
export function seccionLoQueViene(ctx, d, href) {
  const { ui } = ctx;
  const { el } = ui;
  instalar(ctx);
  const viene = Array.isArray(d.lo_que_viene) ? d.lo_que_viene : [];
  const sis = d.agenda_sistema || {};
  const tareas = Array.isArray(sis.tareas) ? sis.tareas : [];
  const RES = { ok: ['ok', 'Bien'], error: ['error', 'Falló'], aviso: ['aviso', 'Con aviso'] };
  return ui.seccion('Lo que viene', el('div', { class: 'ag', 'data-ag-vivo': '1' },
    viene.length ? el('ol', { class: 'ag-lista' }, viene.map((i) => renglon(ui, i, { href }))) : el('p', { class: 'ag-vacio' }, 'Ninguna oferta tiene pasos programados.'),
    tareas.length ? el('div', { class: 'ag-tareas' },
      el('h3', { class: 'ag-grupo__tit' }, ui.icono('robot', { tam: 14 }), 'Tareas automáticas'),
      el('ul', { class: 'ag-tlista' }, tareas.map((t) => {
        const [tono, txt] = RES[t.resultado] || ['info', t.resultado ? String(t.resultado) : 'Sin dato'];
        return el('li', { class: 'ag-tarea' },
          el('div', { class: 'ag-tarea__tit' }, el('b', null, t.titulo), el('span', { class: 'ag-tarea__que' }, t.que)),
          el('div', { class: 'ag-tarea__prox' }, t.activa === false ? 'Apagada' : t.proxima
            ? [el('span', { class: 'ag-hora', 'data-ag-hora': t.proxima }, horaAgenda(t.proxima)), ' ', el('span', { class: 'ag-rel', 'data-ag-rel': t.proxima }, relativo(t.proxima))]
            : 'Sin horario'),
          el('div', { class: 'ag-tarea__ult', title: t.detalle || '' },
            t.ultima ? [el('span', { class: ['ag-res', `ag-res--${tono}`] }, txt + (t.fallas_seguidas > 1 ? ` (${t.fallas_seguidas} seguidas)` : '')), ' ',
              el('span', { class: 'ag-rel', 'data-ag-rel': t.ultima }, relativo(t.ultima))] : 'Todavía no corrió',
            t.detalle ? el('div', { class: 'ag-det' }, t.detalle) : null));
      })),
      sis.tareas_leido ? el('p', { class: 'ag-nota' }, `Horarios leídos de la app de Claude ${relativo(sis.tareas_leido)}; la próxima corrida se calcula con su horario.`) : null) : null));
}

// ── en vivo: refresca los «en …» cada 30 s y recarga la página cuando llega la hora de algo que viene ──
let reloj = null;
function instalar(ctx) {
  const { ui } = ctx;
  if (typeof ui.instalarEstilos === 'function') ui.instalarEstilos('agenda', CSS);
  if (reloj || typeof globalThis.setInterval !== 'function' || !globalThis.document || typeof globalThis.document.querySelectorAll !== 'function') return;
  let ultimo = Date.now();
  reloj = globalThis.setInterval(() => {
    const nodos = globalThis.document.querySelectorAll('[data-ag-vivo] [data-ag-rel]');
    if (!nodos.length) { globalThis.clearInterval(reloj); reloj = null; return; }
    const ahora = Date.now();
    let cruzo = false;
    for (const n of nodos) {
      const iso = n.getAttribute('data-ag-rel');
      n.textContent = relativo(iso);
      const t = Date.parse(iso);
      if (t > ultimo && t <= ahora) cruzo = true;
    }
    for (const n of globalThis.document.querySelectorAll('[data-ag-vivo] [data-ag-hora]')) {
      const pre = n.textContent.startsWith('hasta ') ? 'hasta ' : '';
      n.textContent = pre + horaAgenda(n.getAttribute('data-ag-hora'));
    }
    ultimo = ahora;
    if (cruzo && typeof ctx.recargar === 'function' && !globalThis.document.querySelector('.modal-fondo')) ctx.recargar();
  }, 30000);
  if (reloj && typeof reloj.unref === 'function') reloj.unref();   // en Node (pruebas) no mantiene vivo el proceso
}

const CSS = `
.ag { display: flex; flex-direction: column; gap: 14px; }
.ag-nota { margin: 0; font-size: var(--t-xs); color: var(--txt-3); }
.ag-grupo { display: flex; flex-direction: column; gap: 6px; }
.ag-grupo__tit { display: flex; align-items: center; gap: 6px; margin: 0; font-size: var(--t-sm); font-weight: 800; color: var(--txt-2); text-transform: none; }
.ag-lista { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.ag-item { display: grid; grid-template-columns: 128px 14px 1fr; gap: 10px; padding: 8px 0; border-top: 1px solid var(--borde); align-items: start; }
.ag-lista > .ag-item:first-child { border-top: 0; }
.ag-cuando { display: flex; flex-direction: column; gap: 1px; font-variant-numeric: tabular-nums; }
.ag-hora { font-weight: 700; font-size: var(--t-sm); color: var(--txt); white-space: nowrap; }
.ag-hora--sin { color: var(--txt-3); font-weight: 600; }
.ag-rel { font-size: var(--t-xs); color: var(--txt-3); white-space: nowrap; }
.ag-punto { width: 10px; height: 10px; border-radius: 50%; margin-top: 5px; background: var(--info); box-shadow: 0 0 0 3px var(--info-bg); }
.ag-item--ok .ag-punto { background: var(--ok); box-shadow: 0 0 0 3px var(--ok-bg); }
.ag-item--aviso .ag-punto { background: var(--aviso); box-shadow: 0 0 0 3px var(--aviso-bg); }
.ag-item--error .ag-punto { background: var(--critico-solido); box-shadow: 0 0 0 3px var(--neutro-bg); }
.ag-item--hecho .ag-punto { opacity: .55; }
.ag-item--en_curso .ag-punto { animation: ag-latido 1.6s ease-in-out infinite; }
@keyframes ag-latido { 50% { transform: scale(1.35); } }
@media (prefers-reduced-motion: reduce) { .ag-item--en_curso .ag-punto { animation: none; } }
.ag-cuerpo { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.ag-tit { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; font-weight: 700; color: var(--txt); font-size: var(--t-sm); }
.ag-item--hecho .ag-tit { font-weight: 600; color: var(--txt-2); }
.ag-oferta { font-weight: 800; color: var(--acento-fuerte); text-decoration: none; }
.ag-oferta::after { content: '·'; margin-left: 6px; color: var(--txt-3); }
.ag-chip { display: inline-flex; align-items: center; gap: 3px; padding: 0 7px; border-radius: var(--r-pill); font-size: var(--t-xs); font-weight: 600; color: var(--txt-3); border: 1px solid var(--borde); }
.ag-det { font-size: var(--t-xs); color: var(--txt-2); line-height: 1.45; overflow-wrap: anywhere; }
.ag-quien { font-size: var(--t-xs); color: var(--txt-3); }
.ag-vacio { margin: 0; font-size: var(--t-sm); color: var(--txt-3); }
.ag-mas summary { cursor: pointer; font-size: var(--t-xs); color: var(--txt-2); font-weight: 600; padding: 4px 0; }
.ag-grupo--te_toca { background: var(--aviso-bg); border: 1px solid var(--aviso-borde); border-radius: var(--r-md, 10px); padding: 8px 12px; }
.ag-tareas { display: flex; flex-direction: column; gap: 6px; border-top: 1px solid var(--borde); padding-top: 12px; }
.ag-tlista { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.ag-tarea { display: grid; grid-template-columns: minmax(0, 1.4fr) 150px minmax(0, 1.4fr); gap: 12px; padding: 8px 0; border-top: 1px solid var(--borde); align-items: start; }
.ag-tlista > .ag-tarea:first-child { border-top: 0; }
.ag-tarea__tit { display: flex; flex-direction: column; gap: 2px; font-size: var(--t-sm); min-width: 0; }
.ag-tarea__que { font-size: var(--t-xs); color: var(--txt-3); }
.ag-tarea__prox { display: flex; flex-direction: column; font-size: var(--t-sm); }
.ag-tarea__ult { font-size: var(--t-xs); min-width: 0; }
.ag-res { display: inline-block; padding: 0 8px; border-radius: var(--r-pill); font-weight: 700; }
.ag-res--ok { background: var(--ok-bg); color: var(--ok); }
.ag-res--error { background: var(--critico-solido); color: var(--sobre-critico); }
.ag-res--aviso, .ag-res--info { background: var(--aviso-bg); color: var(--aviso); }
@media (max-width: 640px) {
  .ag-item { grid-template-columns: 92px 12px 1fr; gap: 8px; }
  .ag-tarea { grid-template-columns: 1fr; gap: 4px; }
}
`;
