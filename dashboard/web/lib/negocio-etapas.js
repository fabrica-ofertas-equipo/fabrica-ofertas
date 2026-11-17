// lib/negocio-etapas.js — etapa de cada oferta y su backend ofensivo, para la lista, la ficha y el menú lateral del tablero Negocio.
//
// Pedido del dueño (2026-11-13): «cuando estemos testeando 15, 20 ofertas juntas será muy difícil ver si ya le pusimos backend a una…
// y en qué estado está: si sigue en testeo, si ya están programadas las renovaciones, si está aprobada para renovaciones, si está para
// pausarla y apagarla». La etapa y el backend los calcula el servidor (dashboard/negocio.py: etapa_de, backend_de); aquí solo se dibujan.
// Color con significado y nunca solo: cada marca lleva palabra o letra, y el detalle en `title`.

/** Etapas en el orden de la vida de una oferta (así se dibuja la tira de filtros). `orden` = urgencia (lo calcula el servidor). */
export const ETAPAS = [
  { clave: 'armada', texto: 'Armada, sin salir', corto: 'Armada', icono: 'circulo-punteado', ayuda: 'Tienda, landing y campaña listas, pero la campaña está en pausa y no gasta: falta un paso (casi siempre del dueño).' },
  { clave: 'programada', texto: 'Programada', icono: 'reloj', ayuda: 'La campaña está creada y sale a las 00:00 del mercado.' },
  { clave: 'test', texto: 'En test', icono: 'progreso', ayuda: 'Día 1 del mercado, o todavía sin ventas. Se apaga sola con 1,5 tickets del front gastados por venta.' },
  { clave: 'aprobada', texto: 'Aprobada para renovar', corto: 'Para renovar', icono: 'check', ayuda: 'Pasó el test y no tiene una ronda de creativos corriendo: toca renovar.' },
  { clave: 'renovacion_programada', texto: 'Renovación programada', icono: 'refrescar', ayuda: 'Hay una ronda de creativos nuevos creada que sale a las 00:00 del mercado.' },
  { clave: 'renovando', texto: 'Renovando', icono: 'chispa', ayuda: 'La ronda de creativos de hoy está corriendo. A las ofertas que pegan se les hace una ronda nueva por día (regla R9).' },
  { clave: 'apagar', texto: 'Para apagar', icono: 'x-circulo', ayuda: 'Llegó al corte (1,5 tickets del front por venta en test). La vigilancia de cada hora la apaga sola.' },
  { clave: 'apagada', texto: 'Apagada', icono: 'pausa', ayuda: 'La campaña está pausada o cerrada.' },
];
const POR_CLAVE = Object.fromEntries(ETAPAS.map((e) => [e.clave, e]));
export function etapaUi(clave) { return POR_CLAVE[clave] || { clave: 'sin_dato', texto: 'Sin etapa', icono: 'circulo-punteado' }; }

/** Clase de tono de la etapa (la manda el servidor; si falta, se deduce). */
const TONO_POR_CLAVE = { programada: 'info', test: 'aviso', aprobada: 'ok', renovacion_programada: 'info', renovando: 'info', apagar: 'error', apagada: 'pausada' };
export function tonoEtapa(e) { return (e && e.tono) || TONO_POR_CLAVE[e && e.clave] || 'neutro'; }

/** Estado del backend para dibujar: activo · falta (pasó el test y no tiene) · pausado · armando · no. */
export function claseBackend(b) {
  if (!b) return 'no';
  if (b.estado === 'activo') return 'activo';
  if (b.falta) return 'falta';
  return ['pausado', 'armando', 'listo'].includes(b.estado) ? b.estado : 'no';
}
export function textoBackend(b) {
  const c = claseBackend(b);
  if (c === 'falta') return b && b.estado === 'pausado' ? 'Backend en pausa' : 'Falta backend';
  return (b && b.texto) || 'Sin backend';
}
/** Línea larga para `title`: estado, upsells con precio y nota. */
export function detalleBackend(b) {
  if (!b || claseBackend(b) === 'no') return 'Sin backend: no tiene upsells post-compra. Se arman después del test.';
  const ups = (b.upsells || []).map((u) => `${u.nombre}${typeof u.precio_usd === 'number' ? ` (US$ ${u.precio_usd})` : ''}`).join(', ');
  const bumps = (b.bumps || []).map((u) => `${u.nombre}${typeof u.precio_usd === 'number' ? ` (US$ ${u.precio_usd})` : ''}`).join(', ');
  return [textoBackend(b), ups ? `Upsells: ${ups}.` : null, bumps ? `Order bump en el checkout: ${bumps}.` : null, b.tiendas && b.tiendas.length ? `En ${b.tiendas.length} ${b.tiendas.length === 1 ? 'tienda' : 'tiendas'}.` : null, b.nota || null]
    .filter(Boolean).join(' ');
}

/** Filtros de la tira: «todas», una etapa, «con_backend» o «falta_backend». */
export function filtrarOfertas(ofertas, filtro) {
  const l = Array.isArray(ofertas) ? ofertas : [];
  if (!filtro || filtro === 'todas') return l;
  if (filtro === 'con_backend') return l.filter((o) => claseBackend(o.backend) === 'activo');
  if (filtro === 'falta_backend') return l.filter((o) => claseBackend(o.backend) === 'falta');
  return l.filter((o) => o.etapa && o.etapa.clave === filtro);
}
export function contarEtapas(ofertas) {
  const l = Array.isArray(ofertas) ? ofertas : [];
  const c = Object.fromEntries(ETAPAS.map((e) => [e.clave, 0]));
  for (const o of l) if (o.etapa && o.etapa.clave in c) c[o.etapa.clave] += 1;
  return { ...c, todas: l.length, con_backend: filtrarOfertas(l, 'con_backend').length, falta_backend: filtrarOfertas(l, 'falta_backend').length };
}

/** Grupos para el menú lateral: [{etapa, ofertas}] en orden de urgencia, solo los que tienen ofertas. */
export function gruposPorEtapa(ofertas) {
  const l = Array.isArray(ofertas) ? ofertas : [];
  const orden = (o) => (o.etapa && typeof o.etapa.orden === 'number' ? o.etapa.orden : 99);
  const claves = [...new Set(l.slice().sort((a, b) => orden(a) - orden(b)).map((o) => (o.etapa && o.etapa.clave) || 'sin_dato'))];
  return claves.map((k) => ({ etapa: k === 'sin_dato' ? { clave: k, texto: 'Sin etapa' } : { ...etapaUi(k), ...(l.find((o) => o.etapa && o.etapa.clave === k) || {}).etapa }, ofertas: l.filter((o) => ((o.etapa && o.etapa.clave) || 'sin_dato') === k) }));
}

// ───────────────────────── constructores (reciben `ui`; todo el texto entra por textContent) ─────────────────────────

/** Chip de etapa. `corto`: usa el texto corto del servidor («Test · día 1», «Renovando · R3»). */
export function chipEtapa(ui, etapa, { corto = true } = {}) {
  const e = etapa || {};
  const base = etapaUi(e.clave);
  return ui.el('span', { class: ['ng-etapa', `ng-etapa--${tonoEtapa(e)}`], title: e.detalle || base.ayuda || '' },
    ui.icono(base.icono, { tam: 13 }), (corto && e.corto) || e.texto || base.texto);
}

/** Chip de backend con palabras (lista y ficha). */
export function chipBackend(ui, b) {
  const c = claseBackend(b);
  const icono = { activo: 'check', falta: 'alerta', pausado: 'pausa', armando: 'progreso', listo: 'reloj', no: 'circulo-punteado' }[c];
  return ui.el('span', { class: ['ng-be', `ng-be--${c}`], title: detalleBackend(b) }, ui.icono(icono, { tam: 13 }), textoBackend(b));
}

/** Marca chica del backend para el menú lateral: «B» llena (activo), «B!» ámbar (falta), «B» punteada (todavía no hace falta). */
export function marcaBackend(ui, b) {
  const c = claseBackend(b);
  return ui.el('span', { class: ['ng-be-mini', `ng-be-mini--${c}`], role: 'img', 'aria-label': textoBackend(b), title: detalleBackend(b) }, c === 'falta' ? 'B!' : 'B');
}

export const CSS_ETAPAS = `
.ng-etapa, .ng-be { display: inline-flex; align-items: center; gap: 5px; padding: 2px 9px; border-radius: var(--r-pill); font-size: var(--t-xs); font-weight: 700; white-space: nowrap; border: 1px solid transparent; line-height: 1.5; }
.ng-etapa--ok { background: var(--ok-bg); color: var(--ok); border-color: var(--ok-borde); }
.ng-etapa--aviso { background: var(--aviso-bg); color: var(--aviso); border-color: var(--aviso-borde); }
.ng-etapa--info { background: var(--info-bg); color: var(--info); border-color: var(--info-borde); }
.ng-etapa--error { background: var(--critico-solido); color: var(--sobre-critico); }
.ng-etapa--pausada, .ng-etapa--neutro { background: var(--neutro-bg); color: var(--txt-2); border-color: var(--neutro-borde); }
.ng-be--activo { background: var(--ok-bg); color: var(--ok); border-color: var(--ok-borde); }
.ng-be--falta { background: var(--aviso-bg); color: var(--aviso); border-color: var(--aviso-borde); }
.ng-be--pausado, .ng-be--armando, .ng-be--listo { background: var(--info-bg); color: var(--info); border-color: var(--info-borde); }
.ng-be--no { background: transparent; color: var(--txt-3); border: 1px dashed var(--borde-fuerte); }

/* tira de etapas (filtro) */
.ng-tira { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.ng-tira__sep { width: 1px; align-self: stretch; background: var(--borde-fuerte); margin: 2px 4px; }
.ng-tira__btn { display: inline-flex; align-items: center; gap: 6px; padding: 5px 11px; border-radius: var(--r-pill); border: 1px solid var(--borde); background: var(--sup); color: var(--txt-2); font: inherit; font-size: var(--t-sm); font-weight: 600; cursor: pointer; }
.ng-tira__btn:hover { background: var(--sup-2); color: var(--txt); }
.ng-tira__btn[aria-pressed="true"] { background: var(--acento-bg); color: var(--acento-fuerte); border-color: var(--acento); }
.ng-tira__btn--cero { opacity: .5; }
.ng-tira__n { font-variant-numeric: tabular-nums; font-weight: 800; color: var(--txt); }
.ng-tira__btn--error .ng-tira__n { color: var(--error); } .ng-tira__btn--aviso .ng-tira__n { color: var(--aviso); } .ng-tira__btn--ok .ng-tira__n { color: var(--ok); }
.ng-tira__vacio { color: var(--txt-2); font-size: var(--t-sm); margin: 0; }

/* ficha: etapa y backend */
.ng-eb { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: var(--e-3); }
.ng-eb__caja { display: grid; gap: 6px; align-content: start; padding: var(--e-3) var(--e-4); border: 1px solid var(--borde); border-radius: var(--r-3); background: var(--sup); }
.ng-eb__rot { color: var(--txt-2); font-size: var(--t-xs); text-transform: uppercase; letter-spacing: .05em; font-weight: 650; }
.ng-eb__det { color: var(--txt-2); font-size: var(--t-sm); margin: 0; }
.ng-eb__lista { margin: 0; padding-left: 1.1em; display: grid; gap: 2px; font-size: var(--t-sm); }

/* menú lateral */
.nav__sub { font-size: .714rem; color: var(--txt-3); font-weight: 650; padding: 6px var(--e-3) 2px; display: flex; align-items: center; gap: 6px; white-space: nowrap; }
.nav__sub-n { font-variant-numeric: tabular-nums; }
.nav__sub--apagadas { margin-top: 6px; padding-top: 10px; border-top: 1px solid var(--borde); color: var(--txt-3); }
.nav__plegar { margin-left: auto; display: inline-flex; align-items: center; gap: 3px; height: 20px; padding: 0 6px; border: 0; border-radius: 6px; background: transparent; color: var(--txt-3); font: inherit; font-size: .714rem; font-weight: 600; cursor: pointer; }
.nav__plegar:hover { background: var(--sup-2); color: var(--txt); }
.nav__item--apagada { color: var(--txt-3); min-height: 28px; }
.nav__item--apagada .nav__texto { font-weight: 450; }
.nav__item--apagada .ng-id-punto { opacity: .35; }
.nav__item--apagada .ng-paises { filter: grayscale(.7); opacity: .75; }
.nav__item--apagada:hover, .nav__item--apagada[aria-current="page"] { color: var(--txt); }
.nav__item--apagada:hover .ng-paises, .nav__item--apagada[aria-current="page"] .ng-paises { filter: none; opacity: 1; }
.nav__hace { flex: none; font-size: .714rem; color: var(--txt-3); font-variant-numeric: tabular-nums; opacity: .8; }
.nav__mas { display: block; width: 100%; padding: 4px var(--e-3) 4px calc(var(--e-3) + 18px); border: 0; background: transparent; color: var(--txt-3); font: inherit; font-size: .786rem; font-weight: 550; cursor: pointer; text-align: left; border-radius: 6px; }
.nav__mas:hover { color: var(--acento-fuerte); background: var(--sup-2); }
.app[data-colapsada="true"] .nav__mas, .app[data-colapsada="true"] .nav__plegar, .app[data-colapsada="true"] .nav__hace { display: none; }
.nav__sub--error { color: var(--error); } .nav__sub--aviso { color: var(--aviso); } .nav__sub--ok { color: var(--ok); } .nav__sub--info { color: var(--info); }
.nav__leyenda { font-size: .714rem; color: var(--txt-3); padding: 0 var(--e-3) 4px; display: flex; gap: 8px; flex-wrap: wrap; }
.ng-be-mini { flex: none; display: inline-grid; place-items: center; min-width: 18px; height: 18px; padding: 0 3px; border-radius: 5px; font-size: .68rem; font-weight: 800; line-height: 1; }
.ng-be-mini--activo { background: var(--punto-ok, var(--ok)); color: #fff; }
.ng-be-mini--falta { background: var(--aviso-bg); color: var(--aviso); border: 1px solid var(--aviso); }
.ng-be-mini--pausado, .ng-be-mini--armando, .ng-be-mini--listo { background: var(--info-bg); color: var(--info); border: 1px solid var(--info-borde); }
.ng-be-mini--no { color: var(--txt-3); border: 1px dashed var(--borde-fuerte); opacity: .7; }
.app[data-colapsada="true"] .nav__sub, .app[data-colapsada="true"] .nav__leyenda, .app[data-colapsada="true"] .nav__item--oferta .ng-be-mini { display: none; }
@media (max-width: 900px) { .app[data-colapsada="true"] .nav__sub, .app[data-colapsada="true"] .nav__leyenda { display: flex; } .app[data-colapsada="true"] .nav__item--oferta .ng-be-mini { display: inline-grid; } }
`;
