// iconos.js — set de iconos propio del panel (SVG en línea, 24×24, trazo de 1,75 px, `currentColor`). Cero dependencias, sin DOM:
// aquí solo hay DATOS (nombre → lista de trazos). `ui.icono(nombre, {tam})` los convierte en SVG con `textContent`-seguro (createElementNS).
//
// Convención: nombres en español, minúsculas, con guion. Un trazo es [etiquetaSvg, atributos]; etiquetas admitidas por `ui.el`:
// svg path circle line polyline polygon rect ellipse g. Todo lo que no sea contorno (relleno) lleva `fill: 'currentColor'` en su trazo.
// Alias: ALIAS mapea nombres sinónimos al nombre canónico (p. ej. «buscar» → «lupa»).

export const TRAZO = 1.75;

const p = (d, extra) => ['path', { d, ...(extra || {}) }];
const c = (cx, cy, r, extra) => ['circle', { cx, cy, r, ...(extra || {}) }];
const r = (x, y, width, height, rx, extra) => ['rect', { x, y, width, height, rx, ...(extra || {}) }];
const l = (x1, y1, x2, y2) => ['line', { x1, y1, x2, y2 }];
const punto = (x, y) => ['line', { x1: x, y1: y, x2: x + 0.01, y2: y }];
const relleno = (d) => ['path', { d, fill: 'currentColor', stroke: 'none' }];

export const ICONOS = {
  // ── navegación del panel (los nombres históricos se conservan) ──
  inicio: [p('M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z')],
  caja: [p('M21 8 12 3 3 8v8l9 5 9-5z'), p('M3 8l9 5 9-5M12 13v8')],
  lupa: [c(11, 11, 7), l(21, 21, 16.5, 16.5)],
  pagina: [r(3, 4, 18, 16, 2), l(3, 9, 21, 9), l(9, 9, 9, 20)],
  diana: [c(12, 12, 9), c(12, 12, 5), c(12, 12, 1)],
  pulso: [['polyline', { points: '22 12 18 12 15 21 9 3 6 12 2 12' }]],
  dinero: [l(12, 2, 12, 22), p('M17 6H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6')],
  robot: [r(4, 8, 16, 12, 2), l(12, 8, 12, 4), c(9, 14, 1), c(15, 14, 1)],
  escudo: [p('M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z')],
  ajustes: [l(4, 7, 20, 7), l(4, 17, 20, 17), c(9, 7, 2.2), c(15, 17, 2.2)],
  libro: [p('M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5z'), p('M20 17v4H6.5A2.5 2.5 0 0 1 4 18.5')],
  lapiz: [p('M12 20h9'), p('M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z')],
  lista: [l(8, 6, 21, 6), l(8, 12, 21, 12), l(8, 18, 21, 18), punto(3, 6), punto(3, 12), punto(3, 18)],
  servidor: [r(3, 3, 18, 7, 2), r(3, 14, 18, 7, 2), punto(7, 6.5), punto(7, 17.5)],
  menu: [l(4, 6, 20, 6), l(4, 12, 20, 12), l(4, 18, 20, 18)],
  panel: [r(3, 4, 18, 16, 2), l(9, 4, 9, 20)],
  sol: [c(12, 12, 4), p('M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4')],
  luna: [p('M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z')],
  pausa: [r(6, 4, 4, 16, 1), r(14, 4, 4, 16, 1)],
  copiar: [r(9, 9, 12, 12, 2), p('M5 15V5a2 2 0 0 1 2-2h10')],
  cerrar: [l(6, 6, 18, 18), l(18, 6, 6, 18)],
  flecha: [['polyline', { points: '9 6 15 12 9 18' }]],
  alerta: [p('M12 3 2 20h20z'), l(12, 10, 12, 14), punto(12, 17)],
  reloj: [c(12, 12, 9), ['polyline', { points: '12 7 12 12 15 14' }]],
  candado: [r(5, 11, 14, 10, 2), p('M8 11V8a4 4 0 0 1 8 0v3')],
  play: [['polygon', { points: '7 4 20 12 7 20' }]],

  // ── estados (forma distinta por gravedad: círculo, triángulo, rombo, octógono) ──
  check: [p('M5 12.5l4.5 4.5L19 7.5')],
  tareas: [p('M3.5 6l1.6 1.6L8 4.6'), l(11, 6, 21, 6), p('M3.5 12l1.6 1.6L8 10.6'), l(11, 12, 21, 12), p('M3.5 18l1.6 1.6L8 16.6'), l(11, 18, 21, 18)], // lista de tareas con casillas marcadas
  ok: [c(12, 12, 9), p('M8 12.5l3 3 5-6')],
  info: [c(12, 12, 9), l(12, 11, 12, 16.5), punto(12, 7.6)],
  ayuda: [c(12, 12, 9), p('M9.6 9.6a2.5 2.5 0 1 1 3.6 2.2c-.8.4-1.2 1-1.2 1.9'), punto(12, 17)],
  'rombo-alerta': [p('M12 2.8l9.2 9.2-9.2 9.2L2.8 12z'), l(12, 8, 12, 12.5), punto(12, 15.6)],
  octogono: [p('M8.2 3h7.6L21 8.2v7.6L15.8 21H8.2L3 15.8V8.2z'), p('M9.2 9.2l5.6 5.6M14.8 9.2l-5.6 5.6')],
  'x-circulo': [c(12, 12, 9), p('M9.2 9.2l5.6 5.6M14.8 9.2l-5.6 5.6')],
  circulo: [c(12, 12, 8.5)],
  'circulo-punteado': [c(12, 12, 8.5, { 'stroke-dasharray': '2.6 3.1' })],
  progreso: [c(12, 12, 9), relleno('M12 5.5a6.5 6.5 0 0 1 0 13z')],
  ojo: [p('M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z'), c(12, 12, 3)],
  escalar: [p('M7 17 17 7M8.5 7H17v8.5')],
  'reloj-alerta': [p('M12 7v5l3 2'), p('M20.5 12A8.5 8.5 0 1 1 12 3.5'), l(19.5, 3.5, 19.5, 7), punto(19.5, 9.6)],
  archivar: [r(3, 4, 18, 4, 1), p('M5 8v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8M10 12.5h4')],

  // ── acciones y objetos ──
  'enlace-externo': [p('M14 4h6v6M20 4l-9 9M18 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4')],
  filtro: [p('M3 5h18l-7 8.5V19l-4 2v-7.5z')],
  carpeta: [p('M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z')],
  archivo: [p('M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z'), p('M14 3v5h5')],
  chispa: [p('M11 3l1.9 5.1L18 10l-5.1 1.9L11 17l-1.9-5.1L4 10l5.1-1.9z'), p('M19 15.5l.7 1.8 1.8.7-1.8.7-.7 1.8-.7-1.8-1.8-.7 1.8-.7z')],
  usuario: [c(12, 8, 4), p('M4 20.5c0-3.9 3.6-6 8-6s8 2.1 8 6')],
  firma: [p('M3 17.5c2-3.5 3.6-8.5 5.6-8.5s.4 7.5 3 7.5 3-4.5 4-4.5 1.6 2.5 4.4 2.5'), l(3, 21, 21, 21)],
  grafico: [p('M3 3v17a1 1 0 0 0 1 1h17'), p('M8 16v-5M13 16V7M18 16v-8')],
  cartera: [r(3, 7, 18, 13, 2), p('M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 13h18')],
  globo: [c(12, 12, 9), ['ellipse', { cx: 12, cy: 12, rx: 4, ry: 9 }], l(3, 12, 21, 12)],
  pantalla: [r(3, 4, 18, 12, 2), p('M8 20h8M12 16v4')],
  megafono: [p('M4 10v4h3l7 4V6l-7 4z'), p('M17.5 9.2a4 4 0 0 1 0 5.6'), p('M7 14l1 5h2.5l-1-4.5')],
  cumplimiento: [p('M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z'), p('M8.5 12l2.5 2.5 4.5-5')],
  engranaje: [p('M10.3 3.2l-.5 2a7 7 0 0 0-1.6.9l-2-.6-1.7 3 1.5 1.4a7 7 0 0 0 0 1.9l-1.5 1.4 1.7 3 2-.6a7 7 0 0 0 1.6.9l.5 2h3.4l.5-2a7 7 0 0 0 1.6-.9l2 .6 1.7-3-1.5-1.4a7 7 0 0 0 0-1.9l1.5-1.4-1.7-3-2 .6a7 7 0 0 0-1.6-.9l-.5-2z'), c(12, 12, 2.8)],
  terminal: [r(3, 4, 18, 16, 2), p('M7 10l3 2.5L7 15M12.5 15.5H17')],
  refrescar: [p('M20 11a8 8 0 0 0-14.5-4M4 5v3.5h3.5M4 13a8 8 0 0 0 14.5 4M20 19v-3.5h-3.5')],
  teclado: [r(2, 6, 20, 12, 2), punto(6, 10), punto(10, 10), punto(14, 10), punto(18, 10), p('M7 14h10')],
  comando: [p('M9 6a3 3 0 1 0-3 3h12a3 3 0 1 0-3-3v12a3 3 0 1 0 3-3H6a3 3 0 1 0 3 3z')],
  densidad: [l(4, 5, 20, 5), l(4, 9.5, 20, 9.5), l(4, 14, 20, 14), l(4, 18.5, 20, 18.5)],
  rayo: [p('M13 2 4 14h7l-1 8 9-12h-7z')],
  mas: [p('M12 5v14M5 12h14')],
  menos: [p('M5 12h14')],
  descargar: [p('M12 4v11M7 11l5 5 5-5M5 20h14')],
  bandera: [p('M5 21V4M5 4h11l-2 4 2 4H5')],
  vacio: [r(3, 5, 18, 14, 2, { 'stroke-dasharray': '3 3' }), p('M8 12h8')],

  // ── las piezas del sistema (sidebar por piezas): mismo trazo de 1,75 px, 24×24, solo contorno ──
  cerebro: [
    p('M12 4.5C10.5 3 8 3.2 7 5 5 5.2 3.7 7 4 9 2.8 10 2.8 12 4 13 3.5 15 4.8 17 6.5 17 7.2 18.8 9.5 19.5 11 18.6 11.5 18.3 12 17.8 12 17.2z'),
    p('M12 4.5C13.5 3 16 3.2 17 5 19 5.2 20.3 7 20 9 21.2 10 21.2 12 20 13 20.5 15 19.2 17 17.5 17 16.8 18.8 14.5 19.5 13 18.6 12.5 18.3 12 17.8 12 17.2z'),
    p('M8.5 9.5c1 0 2 .8 2 2M15.5 9.5c-1 0-2 .8-2 2M7.5 13.5c1 0 1.8.6 2.2 1.5M16.5 13.5c-1 0-1.8.6-2.2 1.5'),
  ], // dos hemisferios con sus pliegues
  fabrica: [p('M3 21V11l6 4v-4l6 4V4h6v17z'), punto(7, 18), punto(12, 18), punto(18, 18)], // nave con techo en dientes de sierra y chimenea
  bolsa: [p('M5 8h14l1 13H4z'), p('M9 8V6.5a3 3 0 0 1 6 0V8')], // bolsa de compra con asa
  balanza: [l(12, 3, 12, 21), l(8, 21, 16, 21), l(5, 6, 19, 6), p('M5 6l-3 8a3.5 3.5 0 0 0 6 0z'), p('M19 6l-3 8a3.5 3.5 0 0 0 6 0z')], // dos platillos en equilibrio
  campana: [p('M6 16V11a6 6 0 0 1 12 0v5l2 2H4z'), l(12, 3, 12, 5), p('M10 20.5a2 2 0 0 0 4 0')], // campana de aviso (la de campañas es «megafono»)
  tarjeta: [r(2, 5, 20, 14, 2), l(2, 10, 22, 10), p('M6 15h4')], // tarjeta de pago con banda
  mundo: [c(12, 12, 9), ['ellipse', { cx: 12, cy: 12, rx: 4, ry: 9 }], p('M4 8.5h16M4 15.5h16')], // meridiano y dos paralelos (el «globo» lleva ecuador)

  // ── flechas, chevrones y tendencia ──
  'flecha-abajo': [p('M12 5v14M6 13l6 6 6-6')],
  'flecha-arriba': [p('M12 19V5M6 11l6-6 6 6')],
  'flecha-izquierda': [p('M19 12H5M11 6l-6 6 6 6')],
  'flecha-derecha': [p('M5 12h14M13 6l6 6-6 6')],
  'chevron-abajo': [p('M6 9l6 6 6-6')],
  'chevron-arriba': [p('M6 15l6-6 6 6')],
  'chevron-izquierda': [p('M15 6l-6 6 6 6')],
  'chevron-derecha': [p('M9 6l6 6-6 6')],
  'tendencia-sube': [p('M3 17l6-6 4 4 8-8M15 7h6v6')],
  'tendencia-baja': [p('M3 7l6 6 4-4 8 8M15 17h6v-6')],
  'tendencia-igual': [p('M5 9h14M5 15h14')],
};

/**
 * Sinónimos → nombre canónico (los componentes aceptan ambos).
 * Ojo: «campana» (sin ñ) es ahora el icono propio de la campana de aviso; la campaña de anuncios se pide como «campaña» o «megafono».
 */
export const ALIAS = {
  buscar: 'lupa', cerca: 'lupa', producto: 'caja', landing: 'pantalla', 'campaña': 'megafono', mercado: 'globo',
  skill: 'chispa', gate: 'firma', operacion: 'pulso', finanzas: 'cartera', error: 'x-circulo', alerta_grave: 'rombo-alerta', critico: 'octogono',
  atencion: 'alerta', verificado: 'ok', exito: 'ok', hecho: 'check', enlace: 'enlace-externo', ajustes_finos: 'ajustes', cog: 'engranaje',
  subir: 'flecha-arriba', bajar: 'flecha-abajo', mover: 'flecha-derecha', sube: 'tendencia-sube', baja: 'tendencia-baja', igual: 'tendencia-igual',
};

/** Nombre canónico (resuelve alias); null si no existe. */
export function resolverIcono(nombre) {
  const n = typeof nombre === 'string' ? nombre : '';
  if (Object.prototype.hasOwnProperty.call(ICONOS, n)) return n;
  if (Object.prototype.hasOwnProperty.call(ALIAS, n)) return ALIAS[n];
  return null;
}

/** Trazos de un icono ([] → icono de reserva «lista»). */
export function trazosDe(nombre) {
  const k = resolverIcono(nombre);
  return ICONOS[k || 'lista'];
}

export const NOMBRES_ICONOS = Object.keys(ICONOS);
