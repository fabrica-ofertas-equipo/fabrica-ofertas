// lib/n2-vista.js — pequeños constructores de DOM compartidos por Fábrica, Jurado, Países y Poscompra. Todo texto entra por ui.el (textContent):
// nunca como HTML interpretado. Los datos que vienen de archivos son no confiables; aquí solo se pintan.

import { ui, el, icono, limpiar } from '../ui.js';
import { CSS_N2 } from './estilos-n2.js';
import { leer, dataImagenSegura, etiquetaOferta } from './n2-comun.js';

/** Instala la hoja `n2` (una vez). */
export function instalar() { return ui.instalarEstilos('n2', CSS_N2); }

export const pila = (...hijos) => el('div', { class: 'n2-pila' }, ...hijos);
export const fila = (...hijos) => el('div', { class: 'n2-fila' }, ...hijos);
export const parrafo = (...hijos) => el('p', { class: 'n2-parrafo' }, ...hijos);

/** Etiqueta neutra pequeña. `demo`: borde discontinuo ámbar; `hipotesis`: borde discontinuo gris. */
export function etq(contenido, { demo = false, hipotesis = false, mono = false, titulo = null } = {}) {
  return el('span', { class: ['n2-etq', demo && 'n2-etq--demo', hipotesis && 'n2-etq--hipotesis', mono && 'n2-etq--mono'], title: titulo }, contenido);
}

/** Estado con icono y texto (el color nunca va solo). info = {tono, icono, texto}. */
export function estado(info, { tam = 16 } = {}) {
  const tono = ['ok', 'aviso', 'grave', 'error', 'info', 'acento', 'neutro'].includes(info.tono) ? info.tono : 'neutro';
  return el('span', { class: ['n2-estado', `n2-estado--${tono}`] }, icono(info.icono || 'circulo', { tam }), info.texto);
}

/** Nota con icono. tono: info | aviso | error | ok | neutra. */
export function nota(contenido, { tono = 'info', icono: nombre } = {}) {
  const ic = nombre || { info: 'info', aviso: 'alerta', error: 'x-circulo', ok: 'ok', neutra: 'info' }[tono] || 'info';
  return el('div', { class: ['n2-nota', tono !== 'info' && `n2-nota--${tono}`], role: tono === 'error' ? 'alert' : 'note' }, icono(ic, { tam: 18 }), el('div', null, contenido));
}

/** Detalle técnico plegable (rutas, comandos, JSON): cerrado salvo que el modo técnico global esté encendido. */
export function tecnico(titulo, ...contenido) { return ui.detalleTecnico(titulo, contenido.flat().filter(Boolean)); }

/** Lista de rutas de archivo (código, ajustable). */
export function listaRutas(rutas) {
  return el('ul', { class: 'n2-pila n2-pila--chica', style: { margin: 0, paddingLeft: '18px' } }, rutas.map((r) => el('li', null, el('code', { class: 'n2-mono' }, r))));
}

/** Selector de oferta (solo si hay más de una). */
export function selectorOferta(ofertas, foco, onCambio, { etiqueta = 'Oferta' } = {}) {
  if (!Array.isArray(ofertas) || ofertas.length < 2) return null;
  const id = `n2-sel-${Math.random().toString(36).slice(2, 8)}`;
  const sel = el('select', { id, class: 'campo campo--chico', 'aria-label': etiqueta, onchange: (ev) => onCambio(ev.target.value) },
    ofertas.map((o) => el('option', { value: o.id, selected: o.id === foco }, etiquetaOferta(o))));
  return el('div', { class: 'n2-selector' }, el('label', { for: id }, etiqueta), sel);
}

/** Barra de progreso con etiqueta. `valor`/`max` numéricos; `tono`: ok | aviso | error | (acento por defecto). */
export function barra({ valor, max, etiqueta, texto, tono = null }) {
  const p = max > 0 ? Math.max(0, Math.min(100, (valor / max) * 100)) : 0;
  return el('div', { class: ['n2-barra', tono && `n2-barra--${tono}`] },
    el('div', { class: 'n2-barra__cab' }, el('span', null, etiqueta), el('span', { class: 'n2-barra__valor' }, texto ?? `${valor} de ${max}`)),
    el('div', { class: 'n2-barra__pista', role: 'img', 'aria-label': `${etiqueta}: ${texto ?? `${valor} de ${max}`}` }, el('i', { class: 'n2-barra__relleno', style: { '--p': `${p.toFixed(1)}%` } })));
}

/** Tabla propia de texto largo, con scroll horizontal propio. columnas: [{titulo, clase?}]; filas: [[nodo|texto, …]]. */
export function tablaPropia(columnas, filas, { etiqueta, compacta = false } = {}) {
  return el('div', { class: 'n2-scroll', role: 'region', tabindex: '0', 'aria-label': etiqueta ? `${etiqueta} (desplazable)` : 'Tabla desplazable' },
    el('table', { class: ['n2-tabla', compacta && 'n2-tabla--compacta'], 'aria-label': etiqueta || null },
      el('thead', null, el('tr', null, columnas.map((c) => el('th', { scope: 'col', class: c.clase || null }, c.titulo)))),
      el('tbody', null, filas.map((f) => el('tr', null, f.map((celda, i) => el('td', { class: columnas[i] && columnas[i].clase ? columnas[i].clase : null }, celda === null || celda === undefined || celda === '' ? el('span', { class: 'n2-tenue' }, '—') : celda)))))));
}

/** Banner «datos de demostración» cuando TODAS las ofertas leídas son demo. */
export function bannerDemo(ofertas) {
  if (!Array.isArray(ofertas) || !ofertas.length || !ofertas.every((o) => o.demo)) return null;
  return nota(el('p', null, el('strong', null, 'Estás viendo datos de demostración. '), 'Ninguna oferta real está en marcha: lo que ves viene de una oferta de ejemplo, que sirve para recorrer las pantallas con datos. Nada de esto es una cifra de tu negocio.'), { tono: 'aviso' });
}

/** Aviso cuando una lectura falló (distinto de «no existe todavía»). */
export function avisoLectura(titulo, error) {
  return nota(el('p', null, el('strong', null, titulo), error && (error.mensaje || error.message) ? ` ${error.mensaje || error.message}` : ''), { tono: 'aviso' });
}

/** Casilla de imagen de una pieza; con `ruta` (bajo 06-creativos/) pide la imagen a la API y la pone si es una data-URL segura. */
export function miniatura(ctx, ofertaId, ruta) {
  const caja = el('div', { class: 'n2-pieza__img', 'aria-hidden': 'true' }, icono('pantalla', { tam: 22 }));
  if (ctx && ctx.api && typeof ruta === 'string' && /^[A-Za-z0-9_./-]+\.(png|jpe?g|webp|gif)$/i.test(ruta) && !ruta.includes('..') && !ruta.startsWith('/')) {
    leer(ctx.api, `/oferta/${encodeURIComponent(ofertaId)}/archivo`, { ruta: `06-creativos/${ruta}` }).then((lec) => {
      const c = lec.ok && lec.datos ? lec.datos.contenido : null;
      if (!dataImagenSegura(c)) return;
      const img = el('img', { alt: '', loading: 'lazy' });
      img.src = c; // data-URL de imagen ya validada (png/jpeg/webp/gif); ui.el no admite data: en src
      limpiar(caja);
      caja.appendChild(img);
    }).catch(() => {});
  }
  return caja;
}

/** Cabecera estándar con la fuente en el menú de acciones. */
export function cabecera({ titulo, descripcion, fuentes = [], leido = null, extra = null }) {
  return ui.encabezadoPagina({ titulo, descripcion, acciones: [extra, ui.fuente(fuentes, { leido })].filter(Boolean) });
}
