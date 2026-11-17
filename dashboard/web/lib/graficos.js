// lib/graficos.js — gráficos SVG propios de las pantallas de operación (U4). Sin librerías: todo texto de datos entra como nodo de texto (textContent).
// Reglas de la guía dataviz que cumple: línea de 2 px, marcadores de ≥ 8 px con anillo del color de la superficie, barras ≤ 24 px redondeadas
// solo en el extremo de datos, cuadrícula de 1 px recesiva, un solo eje, rótulo directo solo del último valor, banda en lugar de ruido,
// tooltip con cruz que sigue al puntero y al teclado, y una vista de tabla gemela de cada gráfico. Un hueco (sin dato) corta la línea
// y una cifra tachada se dibuja como marcador hueco con su causa (criterio B0-17).
//
// Dos capas: geometría PURA (`geometriaGrafico`, `ticksAgradables`, `geometriaMargen`, `geometriaMadurez`; se prueban con node --test)
// y render DOM (`graficoSerie`, `barraMargen`, `lineaMadurez`) que recibe `ui` por inyección.

const NS = 'http://www.w3.org/2000/svg';
const r2 = (n) => Math.round(n * 100) / 100;
const num = (x) => typeof x === 'number' && Number.isFinite(x);

// ───────────────────────── geometría pura ─────────────────────────

/** Marcas «agradables» (1·2·2,5·5 × 10^k) de 0 a un máximo redondeado: ticksAgradables(2760) → {ticks:[0,1000,2000,3000], max:3000}. */
export function ticksAgradables(maximo, objetivo = 4) {
  const m = num(maximo) && maximo > 0 ? maximo : 1;
  const bruto = m / Math.max(1, objetivo);
  const exp = Math.floor(Math.log10(bruto));
  const base = 10 ** exp;
  const f = bruto / base;
  const paso = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * base;
  const n = Math.max(1, Math.ceil(m / paso - 1e-9));
  const ticks = [];
  for (let i = 0; i <= n; i += 1) ticks.push(r2(i * paso));
  return { ticks, max: ticks[ticks.length - 1], paso };
}

/** «2026-11-11» → «11/11» (para el eje X). Cualquier otra cosa se devuelve tal cual (recortada). */
export function fechaCorta(x) {
  const m = /^\d{4}-(\d{2})-(\d{2})/.exec(String(x ?? ''));
  return m ? `${m[2]}/${m[1]}` : String(x ?? '').slice(0, 8);
}

/** Índices del eje X que llevan rótulo: el primero, el último y los intermedios que quepan (≈ cada 74 px). */
export function indicesEjeX(n, anchoPlot, separacion = 74) {
  if (n <= 0) return [];
  if (n === 1) return [0];
  const caben = Math.max(2, Math.floor(anchoPlot / separacion) + 1);
  if (n <= caben) return [...Array(n).keys()];
  const salida = new Set([0, n - 1]);
  const huecos = caben - 1;
  for (let k = 1; k < huecos; k += 1) salida.add(Math.round((k * (n - 1)) / huecos));
  return [...salida].sort((a, b) => a - b);
}

/**
 * Geometría de un gráfico de una sola serie sobre un solo eje.
 * @param serie  [{x:'2026-11-11', y:number|null, estado?:'ok'|'gris'|'provisional'|'tachada'|'ausente', causa?}]
 * @param o      {tipo:'linea'|'barras', ancho, alto, banda?:{desde,hasta}, referencias?:[{valor}], formatoEje?}
 */
export function geometriaGrafico(serie, o = {}) {
  const tipo = o.tipo === 'barras' ? 'barras' : 'linea';
  const ancho = Math.max(240, Math.round(o.ancho || 620));
  const alto = Math.max(120, Math.round(o.alto || 190));
  const estrecho = ancho < 440;
  const m = { izq: estrecho ? 44 : 52, der: estrecho ? 58 : 70, arr: 16, aba: 26 };
  const plot = { x0: m.izq, x1: ancho - m.der, y0: m.arr, y1: alto - m.aba };
  const lista = Array.isArray(serie) ? serie : [];
  const n = lista.length;
  const validos = lista.filter((s) => num(s.y));
  const refs = (o.referencias || []).filter((r) => num(r.valor));
  const candidatos = [...validos.map((s) => s.y), ...refs.map((r) => r.valor), ...(o.banda && num(o.banda.hasta) ? [o.banda.hasta] : [])];
  const maximoDatos = candidatos.length ? Math.max(...candidatos) : 1;
  const { ticks, max } = ticksAgradables(maximoDatos > 0 ? maximoDatos * 1.08 : 1, estrecho ? 3 : 4);
  const yDe = (v) => r2(plot.y1 - (Math.max(0, v) / max) * (plot.y1 - plot.y0));
  const paso = n > 1 ? (plot.x1 - plot.x0) / (tipo === 'barras' ? n : n - 1) : 0;
  const xDe = (i) => r2(n <= 1 ? (plot.x0 + plot.x1) / 2 : tipo === 'barras' ? plot.x0 + paso * (i + 0.5) : plot.x0 + paso * i);
  const grosor = tipo === 'barras' ? Math.max(4, Math.min(24, (n > 1 ? paso : plot.x1 - plot.x0) * 0.58)) : 0;
  const puntos = lista.map((s, i) => {
    const hay = num(s.y);
    const estado = s.estado || (hay ? 'ok' : 'ausente');
    return {
      i, etiqueta: s.x, valor: hay ? s.y : null, estado, causa: s.causa || null,
      x: xDe(i), y: hay ? yDe(s.y) : null, yBase: plot.y1,
      alto: hay ? r2(plot.y1 - yDe(s.y)) : 0, xBarra: r2(xDe(i) - grosor / 2), ancho: r2(grosor),
    };
  });
  // segmentos de la línea: corta con huecos y con cifras tachadas
  const segmentos = [];
  let actual = [];
  for (const p of puntos) {
    if (p.valor !== null && p.estado !== 'tachada') actual.push(p); else if (actual.length) { segmentos.push(actual); actual = []; }
  }
  if (actual.length) segmentos.push(actual);
  const trazos = segmentos.filter((s) => s.length > 1).map((s) => `M${s.map((p) => `${p.x} ${p.y}`).join(' L')}`);
  const ultimo = [...puntos].reverse().find((p) => p.valor !== null && p.estado !== 'tachada') || null;
  const banda = o.banda && num(o.banda.hasta) ? { desde: yDe(num(o.banda.desde) ? o.banda.desde : 0), hasta: yDe(o.banda.hasta) } : null;
  return {
    tipo, ancho, alto, margen: m, plot, max, n,
    ticksY: ticks.map((v) => ({ valor: v, y: yDe(v) })),
    ticksX: indicesEjeX(n, plot.x1 - plot.x0).map((i) => ({ i, x: puntos[i].x, texto: fechaCorta(puntos[i].etiqueta) })),
    puntos, trazos, ultimo, banda,
    referencias: refs.map((r) => ({ ...r, y: yDe(r.valor) })),
    soloUnPunto: validos.length === 1, sinDatos: validos.length === 0,
    paso: r2(paso),
  };
}

/** Margen operativo en puntos básicos → posición de una barra divergente (cero a 1/3 del ancho: lo negativo a la izquierda, lo positivo a la derecha). */
export function geometriaMargen(bp, { negativoMax = 10000, positivoMax = 10000 } = {}) {
  if (!Number.isSafeInteger(bp)) return null;
  const cero = 100 / 3;
  const zonaNeg = cero;
  const zonaPos = 100 - cero;
  if (bp >= 0) {
    const ancho = Math.min(zonaPos, (Math.min(bp, positivoMax) / positivoMax) * zonaPos);
    return { signo: 1, izquierda: r2(cero), ancho: r2(ancho), cero: r2(cero), recortado: bp > positivoMax };
  }
  const ancho = Math.min(zonaNeg, (Math.min(-bp, negativoMax) / negativoMax) * zonaNeg);
  return { signo: -1, izquierda: r2(cero - ancho), ancho: r2(ancho), cero: r2(cero), recortado: -bp > negativoMax };
}

/** Tramos de la ventana de madurez de la cohorte: garantía + margen = madurez total. null si faltan días. */
export function geometriaMadurez({ garantia, margen, total } = {}) {
  const g = Number.isSafeInteger(garantia) && garantia >= 0 ? garantia : null;
  const t = Number.isSafeInteger(total) && total > 0 ? total : (g !== null && Number.isSafeInteger(margen) ? g + margen : null);
  if (g === null || t === null || t <= 0) return null;
  const mar = Math.max(0, t - g);
  return {
    total: t,
    tramos: [
      { id: 'garantia', dias: g, pct: r2((g / t) * 100), texto: 'Garantía' },
      { id: 'margen', dias: mar, pct: r2((mar / t) * 100), texto: 'Margen de seguridad' },
    ].filter((x) => x.dias > 0),
  };
}

// ───────────────────────── render DOM ─────────────────────────

function svgEl(tag, attrs, ...hijos) {
  const d = globalThis.document;
  const nodo = d.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined || v === false) continue;
    nodo.setAttribute(k, String(v));
  }
  for (const h of hijos) {
    if (h === null || h === undefined || h === false) continue;
    if (typeof h === 'object') nodo.appendChild(h); else nodo.appendChild(d.createTextNode(String(h)));
  }
  return nodo;
}

const TEXTO_ESTADO = { ok: null, gris: 'pocos datos: todavía no concluye', provisional: 'provisional: incluye compras recientes que todavía pueden reembolsarse', tachada: 'cifra tachada', ausente: 'sin dato' };

/**
 * Gráfico de una serie con título, tooltip, vista de tabla y (opcional) banda y líneas de referencia.
 * @param ui     el objeto `ui` (se usa `el`, `icono`)
 * @param o      {titulo, subtitulo?, serie, tipo?, formato(v)→texto, formatoEje?(v)→texto, banda?:{desde,hasta,etiqueta}, referencias?:[{valor, etiqueta}],
 *                columna?:'Valor', alto?, ancho?, vacio?:Node, resumen?:string}
 * @returns Element <figure class="p5-viz"> con `.repintar(anchoPx)` (para pruebas).
 */
export function graficoSerie(ui, o = {}) {
  const { el } = ui;
  const formato = o.formato || ((v) => String(v));
  const formatoEje = o.formatoEje || formato;
  const serie = Array.isArray(o.serie) ? o.serie : [];
  const alto = o.alto || 190;
  let anchoActual = o.ancho || 620;
  let indiceActivo = null;
  let g = geometriaGrafico(serie, { tipo: o.tipo, ancho: anchoActual, alto, banda: o.banda, referencias: o.referencias });

  const lienzo = el('div', { class: 'p5-viz__lienzo' });
  const tip = el('div', { class: 'p5-viz__tip', role: 'status', 'aria-live': 'polite', hidden: true });
  const tabla = vistaTabla(ui, serie, formato, o.columna || 'Valor');
  tabla.hidden = true;
  const interruptor = el('button', {
    type: 'button', class: 'btn btn--chico p5-viz__vista', 'aria-pressed': 'false', title: 'Alterna entre el gráfico y sus datos en una tabla',
    onclick: () => {
      const verTabla = interruptor.getAttribute('aria-pressed') !== 'true';
      interruptor.setAttribute('aria-pressed', String(verTabla));
      interruptor.textContent = verTabla ? 'Ver gráfico' : 'Ver tabla';
      tabla.hidden = !verTabla;
      lienzo.hidden = verTabla;
    },
  }, 'Ver tabla');

  const resumen = o.resumen || (g.sinDatos ? `${o.titulo}: sin datos.` : `${o.titulo}: ${g.puntos.filter((p) => p.valor !== null).length} valores${g.ultimo ? `, el último ${formato(g.ultimo.valor)}` : ''}. Usa «Ver tabla» para todos los valores.`);

  function ocultarTip() { indiceActivo = null; tip.hidden = true; const c = lienzo.querySelector('.p5-viz__cruz'); if (c) c.setAttribute('visibility', 'hidden'); for (const d of lienzo.querySelectorAll('.p5-viz__sel')) d.classList.remove('p5-viz__sel'); }

  function mostrarTip(i) {
    const p = g.puntos[i];
    if (!p) return;
    indiceActivo = i;
    const cruz = lienzo.querySelector('.p5-viz__cruz');
    if (cruz) { cruz.setAttribute('x1', p.x); cruz.setAttribute('x2', p.x); cruz.setAttribute('visibility', 'visible'); }
    for (const d of lienzo.querySelectorAll('.p5-viz__sel')) d.classList.remove('p5-viz__sel');
    const marca = lienzo.querySelector(`[data-i="${i}"]`);
    if (marca) marca.classList.add('p5-viz__sel');
    const aviso = TEXTO_ESTADO[p.estado];
    ui.reemplazar(tip,
      el('div', { class: 'p5-viz__tip-valor' }, p.valor === null ? el('span', { class: 'cifra-sin-dato' }, 'sin dato') : (p.estado === 'tachada' ? el('s', null, formato(p.valor)) : formato(p.valor))),
      el('div', { class: 'p5-viz__tip-fila' }, el('span', { class: 'p5-viz__llave', 'aria-hidden': 'true' }), el('span', null, ui.fmt.fecha(p.etiqueta))),
      aviso ? el('div', { class: `p5-viz__tip-aviso${p.estado === 'tachada' ? ' p5-viz__tip-aviso--error' : ''}` }, p.estado === 'tachada' && p.causa ? p.causa : aviso) : null);
    tip.hidden = false;
    const w = lienzo.clientWidth || g.ancho;
    const mitad = 90;
    tip.style.left = `${Math.round(Math.max(mitad, Math.min(w - mitad, p.x)))}px`;
  }

  function indiceMasCercano(ev) {
    const svg = lienzo.querySelector('svg');
    const caja = svg && svg.getBoundingClientRect ? svg.getBoundingClientRect() : null;
    const ancho = caja && caja.width ? caja.width : g.ancho;
    const px = ((ev.clientX - (caja ? caja.left : 0)) * g.ancho) / ancho;
    let mejor = 0; let d = Infinity;
    g.puntos.forEach((p, i) => { const dd = Math.abs(p.x - px); if (dd < d) { d = dd; mejor = i; } });
    return mejor;
  }

  function pintar() {
    const { plot } = g;
    const hijos = [];
    // cuadrícula + eje Y (1 px, recesivo) y rótulos de ticks
    for (const t of g.ticksY) {
      hijos.push(svgEl('line', { class: t.valor === 0 ? 'p5-viz__eje' : 'p5-viz__rejilla', x1: plot.x0, x2: plot.x1, y1: t.y, y2: t.y }));
      hijos.push(svgEl('text', { class: 'p5-viz__tick', x: plot.x0 - 8, y: t.y + 4, 'text-anchor': 'end' }, formatoEje(t.valor)));
    }
    for (const t of g.ticksX) hijos.push(svgEl('text', { class: 'p5-viz__tick', x: t.x, y: plot.y1 + 17, 'text-anchor': g.n > 1 && t.i === 0 && g.tipo === 'linea' ? 'start' : g.n > 1 && t.i === g.n - 1 && g.tipo === 'linea' ? 'end' : 'middle' }, t.texto));
    // banda del objetivo
    if (g.banda) hijos.push(svgEl('rect', { class: 'p5-viz__banda', x: plot.x0, width: plot.x1 - plot.x0, y: g.banda.hasta, height: Math.max(0, g.banda.desde - g.banda.hasta) }));
    for (const r of g.referencias) {
      hijos.push(svgEl('line', { class: 'p5-viz__ref', x1: plot.x0, x2: plot.x1, y1: r.y, y2: r.y }));
      // con banda, los rótulos van en la leyenda (dentro del gráfico chocarían con la línea); sin banda, junto a la línea
      if (r.etiqueta && !g.banda) hijos.push(svgEl('text', { class: 'p5-viz__rotulo-ref', x: plot.x1, y: r.y - 5, 'text-anchor': 'end' }, r.etiqueta));
    }
    if (g.tipo === 'barras') {
      for (const p of g.puntos) {
        if (p.valor === null || p.alto <= 0) continue;
        const rad = Math.min(4, p.ancho / 2, p.alto);
        const d = `M${p.xBarra} ${p.yBase} V${r2(p.y + rad)} Q${p.xBarra} ${p.y} ${r2(p.xBarra + rad)} ${p.y} H${r2(p.xBarra + p.ancho - rad)} Q${r2(p.xBarra + p.ancho)} ${p.y} ${r2(p.xBarra + p.ancho)} ${r2(p.y + rad)} V${p.yBase} Z`;
        hijos.push(svgEl('path', { class: `p5-viz__barra${p.estado === 'tachada' ? ' p5-viz__barra--tachada' : p.estado === 'gris' ? ' p5-viz__barra--gris' : ''}`, d, 'data-i': p.i }));
      }
    } else {
      for (const d of g.trazos) hijos.push(svgEl('path', { class: 'p5-viz__linea', d }));
      const conMarcas = g.n <= 14;
      for (const p of g.puntos) {
        if (p.valor === null) continue;
        const esUltimo = g.ultimo && p.i === g.ultimo.i;
        if (!conMarcas && !esUltimo && p.estado !== 'tachada') continue;
        hijos.push(svgEl('circle', { class: `p5-viz__punto${p.estado === 'tachada' ? ' p5-viz__punto--tachada' : p.estado === 'gris' ? ' p5-viz__punto--gris' : ''}${esUltimo ? ' p5-viz__punto--ultimo' : ''}`, cx: p.x, cy: p.y, r: 4, 'data-i': p.i }));
      }
    }
    // rótulo directo: solo el último valor (nunca un número en cada punto)
    if (g.ultimo) {
      const u = g.ultimo;
      if (g.tipo === 'barras') hijos.push(svgEl('text', { class: 'p5-viz__rotulo', x: u.x, y: u.y - 6, 'text-anchor': 'middle' }, formato(u.valor)));
      else hijos.push(svgEl('text', { class: 'p5-viz__rotulo', x: u.x + 9, y: u.y + 4, 'text-anchor': 'start' }, formato(u.valor)));
    }
    hijos.push(svgEl('line', { class: 'p5-viz__cruz', x1: 0, x2: 0, y1: plot.y0, y2: plot.y1, visibility: 'hidden' }));
    // capa de entrada: ancha, mayor que la marca (guía de interacción)
    const capa = svgEl('rect', { class: 'p5-viz__capa', x: plot.x0 - 4, y: 0, width: plot.x1 - plot.x0 + 8, height: g.alto, fill: 'transparent' });
    capa.addEventListener('pointermove', (ev) => mostrarTip(indiceMasCercano(ev)));
    capa.addEventListener('pointerleave', ocultarTip);
    hijos.push(capa);
    const svg = svgEl('svg', { viewBox: `0 0 ${g.ancho} ${g.alto}`, width: g.ancho, height: g.alto, class: 'p5-viz__svg', role: 'img', 'aria-label': resumen, focusable: 'false' }, ...hijos);
    const vacio = g.sinDatos ? el('div', { class: 'p5-viz__vacio' }, o.vacio || 'Sin datos todavía: no se dibuja ningún cero.') : null;
    ui.reemplazar(lienzo, svg, vacio, tip);
    if (indiceActivo !== null) mostrarTip(indiceActivo);
  }

  const itemsLeyenda = [];
  if (g.banda && o.banda && o.banda.etiqueta) itemsLeyenda.push(el('span', { class: 'p5-viz__ley' }, el('span', { class: 'p5-viz__ley-banda', 'aria-hidden': 'true' }), o.banda.etiqueta));
  if (g.banda) for (const r of g.referencias) if (r.etiqueta) itemsLeyenda.push(el('span', { class: 'p5-viz__ley' }, el('span', { class: 'p5-viz__ley-linea', 'aria-hidden': 'true' }), r.etiqueta));
  const leyenda = itemsLeyenda.length && !g.sinDatos ? el('div', { class: 'p5-viz__leyenda' }, itemsLeyenda) : null;
  const raiz = el('figure', { class: 'p5-viz', tabindex: g.sinDatos ? null : '0', 'aria-label': `${o.titulo}. Flechas izquierda y derecha recorren los valores.` },
    el('figcaption', { class: 'p5-viz__cab' },
      el('div', { class: 'p5-viz__titulos' }, el('h3', { class: 'p5-viz__titulo' }, o.titulo), o.subtitulo ? el('span', { class: 'p5-viz__sub' }, o.subtitulo) : null),
      g.sinDatos ? null : interruptor),
    lienzo, tabla,
    leyenda,
    g.soloUnPunto ? el('p', { class: 'p5-viz__nota' }, 'Un solo día con dato: aún no hay tendencia que dibujar.') : null);
  raiz.addEventListener('keydown', (ev) => {
    if (g.sinDatos) return;
    const validos = g.puntos.filter((p) => p.valor !== null).map((p) => p.i);
    if (!validos.length) return;
    const pos = indiceActivo === null ? validos.length : validos.indexOf(indiceActivo);
    if (ev.key === 'ArrowLeft') { ev.preventDefault(); mostrarTip(validos[Math.max(0, (pos === validos.length ? validos.length : pos) - 1)]); }
    else if (ev.key === 'ArrowRight') { ev.preventDefault(); mostrarTip(validos[Math.min(validos.length - 1, pos + 1)]); }
    else if (ev.key === 'Escape') ocultarTip();
  });
  raiz.addEventListener('focusout', ocultarTip);
  pintar();

  raiz.repintar = (anchoPx) => { anchoActual = anchoPx; g = geometriaGrafico(serie, { tipo: o.tipo, ancho: anchoPx, alto, banda: o.banda, referencias: o.referencias }); pintar(); };
  if (typeof globalThis.ResizeObserver === 'function' && !g.sinDatos) {
    const ro = new globalThis.ResizeObserver((entradas) => {
      if (!raiz.isConnected) { ro.disconnect(); return; }
      const w = Math.round(entradas[0].contentRect.width);
      if (w >= 240 && Math.abs(w - anchoActual) > 6) raiz.repintar(w);
    });
    ro.observe(lienzo);
  }
  return raiz;
}

/** Tabla gemela del gráfico: fecha, valor y estado (tachada con su causa, «sin dato»). Los datos entran por textContent. */
function vistaTabla(ui, serie, formato, columna) {
  const { el } = ui;
  const filas = serie.map((s) => {
    const hay = num(s.y);
    const estado = s.estado || (hay ? 'ok' : 'ausente');
    return el('tr', null,
      el('td', null, ui.fmt.fecha(s.x)),
      el('td', { class: 'alinea-der' }, hay ? (estado === 'tachada' ? el('s', null, formato(s.y)) : formato(s.y)) : el('span', { class: 'cifra-sin-dato' }, 'sin dato')),
      el('td', null, estado === 'ok' ? '' : (estado === 'tachada' && s.causa ? s.causa : (TEXTO_ESTADO[estado] || estado))));
  });
  return el('div', { class: 'tabla-scroll p5-viz__tabla', tabindex: '0', role: 'region', 'aria-label': `Datos de ${columna}` },
    el('table', { class: 'tabla' }, el('thead', null, el('tr', null, el('th', { scope: 'col' }, 'Día'), el('th', { scope: 'col', class: 'alinea-der' }, columna), el('th', { scope: 'col' }, 'Nota'))), el('tbody', null, filas)));
}

/** Barra de margen divergente (cero a un tercio): azul a la derecha, rojo (polo opuesto) a la izquierda; el número siempre va al lado. */
export function barraMargen(ui, bp, { etiqueta = 'Margen operativo' } = {}) {
  const { el } = ui;
  const g = geometriaMargen(bp);
  if (!g) return el('span', { class: 'cifra-sin-dato' }, 'sin dato');
  return el('span', { class: 'p5-margen', role: 'img', 'aria-label': `${etiqueta}: ${ui.fmt.pct(bp)}` },
    el('span', { class: 'p5-margen__pista' },
      el('span', { class: 'p5-margen__cero', style: { left: `${g.cero}%` } }),
      el('span', { class: `p5-margen__barra ${g.signo < 0 ? 'p5-margen__barra--neg' : 'p5-margen__barra--pos'}`, style: { left: `${g.izquierda}%`, width: `${Math.max(g.ancho, 0.8)}%` } })),
    el('span', { class: 'p5-margen__valor' }, ui.fmt.pct(bp)));
}

/** Línea de la ventana de madurez: tramos proporcionales (garantía + margen) y el rótulo del día en que la cohorte madura. */
export function lineaMadurez(ui, { garantia, margen, total, hasta } = {}) {
  const { el } = ui;
  const g = geometriaMadurez({ garantia, margen, total });
  if (!g) return el('p', { class: 'p5-sub' }, 'Sin los días de garantía y madurez no se puede dibujar la ventana.');
  return el('div', { class: 'p5-madurez', role: 'img', 'aria-label': `Una compra cuenta para el veredicto tras ${g.total} días: ${g.tramos.map((t) => `${t.texto} ${t.dias} días`).join(' y ')}` },
    el('div', { class: 'p5-madurez__tramos' }, g.tramos.map((t) => el('div', { class: `p5-madurez__tramo p5-madurez__tramo--${t.id}`, style: { flex: `${t.pct} 1 0` } }, el('strong', null, `${t.dias} d`), el('span', null, t.texto)))),
    el('div', { class: 'p5-madurez__pie' },
      el('span', null, 'Día de la compra'),
      el('span', { class: 'p5-madurez__fin' }, `Cuenta desde el día ${g.total}`)),
    hasta ? el('p', { class: 'p5-sub' }, `Hoy ya cuentan las compras hechas hasta el ${ui.fmt.fecha(hasta)}.`) : null);
}

// ───────────────────────── CPA frente a equilibrio y objetivo ─────────────────────────

/** Geometría de la «bala» del CPA: tres zonas (≤ objetivo · hasta el equilibrio · sobre el equilibrio) y la marca del CPA real. null sin CPA o sin equilibrio. */
export function geometriaBullet({ cpa, be, obj } = {}) {
  if (!num(cpa) || !num(be) || be <= 0 || cpa < 0) return null;
  const objV = num(obj) && obj > 0 && obj < be ? obj : null;
  const max = Math.max(be * 1.6, cpa * 1.12);
  const p = (v) => r2(Math.min(100, Math.max(0, (v / max) * 100)));
  const zonas = [];
  if (objV !== null) zonas.push({ id: 'objetivo', ancho: p(objV) });
  zonas.push({ id: 'equilibrio', ancho: r2(p(be) - (objV !== null ? p(objV) : 0)) });
  const ejes = [{ id: 'cero', pos: 0 }];
  if (objV !== null) ejes.push({ id: 'objetivo', pos: p(objV), valor: objV });
  ejes.push({ id: 'equilibrio', pos: p(be), valor: be });
  return { max, marca: p(cpa), zonas, ejes, zona: cpa <= (objV !== null ? objV : -1) ? 'objetivo' : cpa <= be ? 'equilibrio' : 'sobre' };
}

/** «Bala» del CPA: la marca negra es el CPA real; las zonas verde/ámbar/roja son objetivo, equilibrio y pérdida. El texto de al lado dice lo mismo (nunca solo color). */
export function bulletCpa(ui, { cpa, be, obj, formato = (v) => String(v) } = {}) {
  const { el } = ui;
  const g = geometriaBullet({ cpa, be, obj });
  if (!g) return null;
  return el('div', { class: 'p5-bullet', role: 'img', 'aria-label': `Costo por venta ${formato(cpa)} frente al punto de equilibrio ${formato(be)}${g.ejes.some((e) => e.id === 'objetivo') ? ` y al objetivo ${formato(obj)}` : ''}: ${{ objetivo: 'por debajo del objetivo', equilibrio: 'entre el objetivo y el punto de equilibrio', sobre: 'por encima del punto de equilibrio' }[g.zona] || g.zona}` },
    el('div', { class: 'p5-bullet__pista' },
      g.zonas.map((z) => el('span', { class: `p5-bullet__zona p5-bullet__zona--${z.id}`, style: { width: `${z.ancho}%` } })),
      el('span', { class: 'p5-bullet__zona p5-bullet__zona--sobre' }),
      el('span', { class: 'p5-bullet__marca', style: { left: `${g.marca}%` }, title: `Costo por venta real ${formato(cpa)}` })),
    null);
}

// ───────────────────────── barras horizontales ordenadas ─────────────────────────

/** Geometría de barras horizontales ordenadas de mayor a menor: ancho en % del máximo (mínimo visible 1,5 % si el valor > 0). */
export function geometriaRanking(items, { maximo } = {}) {
  const lista = (Array.isArray(items) ? items : []).filter((x) => x && num(x.valor) && x.valor >= 0);
  const tope = num(maximo) && maximo > 0 ? maximo : Math.max(0, ...lista.map((x) => x.valor));
  return [...lista].sort((a, b) => b.valor - a.valor).map((x) => ({ ...x, pct: tope > 0 ? Math.max(x.valor > 0 ? 1.5 : 0, r2((x.valor / tope) * 100)) : 0 }));
}

/** Barras horizontales de una sola serie (un matiz, ≤ 24 px de grosor, valor en la punta): «Por agente», «Por etapa». */
export function barrasRanking(ui, items, { etiqueta = 'Ranking', vacio = 'Sin datos', maximo } = {}) {
  const { el } = ui;
  const g = geometriaRanking(items, { maximo });
  if (!g.length) return el('p', { class: 'p5-sub' }, vacio);
  return el('ul', { class: 'p5-ranking', 'aria-label': etiqueta }, g.map((x) => el('li', { class: 'p5-ranking__fila', title: `${x.nombre}: ${x.texto}` },
    el('span', { class: 'p5-ranking__nombre' }, x.nombre),
    el('span', { class: 'p5-ranking__pista', 'aria-hidden': 'true' }, el('span', { class: 'p5-ranking__barra', style: { width: `${x.pct}%` } })),
    el('span', { class: 'p5-ranking__valor' }, x.texto))));
}
