// popover.js — geometría y reglas puras de los popovers (sin DOM). `ui.popover` los usa; aquí se prueban con `node --test`.
//
// Un popover se ancla a un elemento («ancla») y se coloca debajo o encima, dentro de la ventana, con una flecha alineada al centro del ancla.

/** Rectángulo mínimo de un ancla/ventana: {left, top, width, height} (right/bottom se derivan). */
export function normalizarRect(r) {
  const left = Number(r && r.left) || 0;
  const top = Number(r && r.top) || 0;
  const width = Number(r && r.width) || (Number(r && r.right) - left) || 0;
  const height = Number(r && r.height) || (Number(r && r.bottom) - top) || 0;
  return { left, top, width, height, right: left + width, bottom: top + height };
}

/**
 * Posición de un popover de tamaño `pop` ({width, height}) junto a `ancla` dentro de la ventana `vista` ({width, height}).
 * Prefiere `preferido` ('abajo' | 'arriba'); si no cabe, usa el lado con más espacio. Siempre queda dentro de la ventana (margen `margen`).
 * Devuelve {left, top, lado: 'abajo'|'arriba', flecha} donde `flecha` es la x (px, relativa al popover) donde apunta la flecha.
 */
export function posicionarPopover(ancla, pop, vista, { separacion = 8, margen = 8, preferido = 'abajo' } = {}) {
  const a = normalizarRect(ancla);
  const w = Math.max(0, Number(pop && pop.width) || 0);
  const h = Math.max(0, Number(pop && pop.height) || 0);
  const vw = Math.max(0, Number(vista && vista.width) || 0);
  const vh = Math.max(0, Number(vista && vista.height) || 0);

  const espacioAbajo = vh - a.bottom - separacion - margen;
  const espacioArriba = a.top - separacion - margen;
  let lado = preferido === 'arriba' ? 'arriba' : 'abajo';
  if (lado === 'abajo' && h > espacioAbajo && espacioArriba > espacioAbajo) lado = 'arriba';
  else if (lado === 'arriba' && h > espacioArriba && espacioAbajo > espacioArriba) lado = 'abajo';

  let top = lado === 'abajo' ? a.bottom + separacion : a.top - separacion - h;
  top = Math.min(Math.max(top, margen), Math.max(margen, vh - h - margen));

  let left = a.left + a.width / 2 - w / 2;
  left = Math.min(Math.max(left, margen), Math.max(margen, vw - w - margen));

  const centro = a.left + a.width / 2;
  const flecha = Math.min(Math.max(centro - left, 12), Math.max(12, w - 12));
  return { left: Math.round(left), top: Math.round(top), lado, flecha: Math.round(flecha) };
}

/** ¿Debe cerrarse el popover con esta tecla? (Esc). */
export const cierraConTecla = (tecla) => tecla === 'Escape' || tecla === 'Esc';

/**
 * Máquina de estados mínima del popover: `fijo` (anclado por clic/teclado) frente a efímero (hover/foco).
 * eventos: 'entra' (ratón/foco sobre ancla o popover), 'sale' (ratón/foco fuera), 'clic' (clic en el ancla), 'fuera' (clic fuera), 'esc'.
 * Devuelve {abierto, fijo, accion: 'abrir'|'cerrar'|'programar_cierre'|'cancelar_cierre'|null}.
 */
export function transicionPopover(estado, evento) {
  const s = { abierto: Boolean(estado && estado.abierto), fijo: Boolean(estado && estado.fijo), accion: null };
  switch (evento) {
    case 'entra':
      if (!s.abierto) { s.abierto = true; s.accion = 'abrir'; } else s.accion = 'cancelar_cierre';
      break;
    case 'sale':
      if (s.abierto && !s.fijo) s.accion = 'programar_cierre';
      break;
    case 'clic':
      if (s.abierto && s.fijo) { s.abierto = false; s.fijo = false; s.accion = 'cerrar'; }
      else if (s.abierto) { s.fijo = true; s.accion = 'cancelar_cierre'; }
      else { s.abierto = true; s.fijo = true; s.accion = 'abrir'; }
      break;
    case 'fuera':
    case 'esc':
      if (s.abierto) { s.abierto = false; s.fijo = false; s.accion = 'cerrar'; }
      break;
    default: break;
  }
  return s;
}
