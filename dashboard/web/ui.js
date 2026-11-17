// ui.js — componentes de interfaz del panel (CONTRATO §5 + rediseño U0). Cero dependencias, cero innerHTML.
//
// REGLA DE ORO: todo texto que venga de datos entra por `textContent` / `createTextNode` (lo hace `el`). `el` RECHAZA
// `innerHTML`, `outerHTML`, `srcdoc`, `on*` que no sean funciones y URLs `javascript:`. Los caracteres de control
// bidireccional (U+202E…) y los de control C0 se muestran visibles en vez de interpretarse.
//
// Firmas del contrato original (NO se rompen):  el · chip · estadoChip · tarjeta · seccion · tabla · tabs · visorJson · visorTexto · vacio ·
//   cargando · errorBox · copiar · toast · modal · fmt.{fecha,relativo,dinero,bytes,pct}
// Añadidos antes del rediseño: cerrarModales() · instalarEstilos(id, css) · icono · kv · comando · sparkline · barraApilada · enlace · encabezado · fuenteInfo ·
//   confirmar · fmt.{num,duracion,texto} · y las partes puras (ordenarFilas, filtrarFilas, valorDe, neutralizarTexto, infoEstado…).
// Piezas comunes del REDISEÑO (U0; las usan todas las pantallas):
//   encabezadoPagina · atencion · metrica · detalleTecnico · soloTecnico · termino · ayuda · popover · comando (ahora bloque cerrado «Cómo hacerlo») ·
//   fuente · pasos · vacioConPasos · esqueleto · icono(nombre,{tamano}) · estadoIcono · tiempo · interruptor · segmentado · barraPestanas · kbd · fmt.numero
// Estado global (estado.js): modoTecnico (abre todo lo técnico) y densidad ('comoda'|'compacta'); `instalarPreferencias()` los refleja en <html data-tecnico data-densidad>.
// Todo se exporta con nombre y también agrupado en `ui` (lo que reciben las páginas en `ctx.ui`).

import { estado } from './estado.js';
import { trazosDe, TRAZO, NOMBRES_ICONOS as NOMBRES_ICONOS_BASE } from './lib/iconos.js';
import { buscarTermino, humanizarClave } from './lib/glosario-indice.js';
import { posicionarPopover, transicionPopover, cierraConTecla } from './lib/popover.js';

const NS_SVG = 'http://www.w3.org/2000/svg';
const ETIQUETAS_SVG = new Set(['svg', 'path', 'circle', 'line', 'polyline', 'polygon', 'rect', 'g', 'title', 'ellipse', 'text', 'defs', 'linearGradient', 'stop']);
/** Tonos de color con significado único. ok=bien · aviso · grave (naranja) · error/critico (rojo) · info · neutro · acento (lo que espera al dueño). */
export const TONOS = ['ok', 'aviso', 'error', 'info', 'neutro', 'grave', 'critico', 'acento'];
const ALIAS_TONO = { bien: 'ok', good: 'ok', warning: 'aviso', serious: 'grave', critical: 'critico', danger: 'error', peligro: 'error' };
/** Nombre de tono válido (resuelve alias: bien→ok); desconocido → `defecto`. */
export function normalizarTono(t, defecto = 'neutro') {
  if (typeof t !== 'string') return defecto;
  const k = ALIAS_TONO[t] || t;
  return TONOS.includes(k) ? k : defecto;
}
const ICONO_TONO = { ok: 'ok', aviso: 'alerta', error: 'x-circulo', grave: 'rombo-alerta', critico: 'octogono', info: 'info', acento: 'usuario', neutro: null };
/** Icono que acompaña SIEMPRE a un tono de estado (el color nunca va solo). neutro → null. */
export function iconoDeTono(t) { return ICONO_TONO[normalizarTono(t)] || null; }

const doc = () => {
  if (typeof globalThis.document === 'undefined') throw new Error('ui.js necesita `document` (solo se llama desde el navegador)');
  return globalThis.document;
};

// ───────────────────────── texto seguro ─────────────────────────

const RE_PELIGROSOS = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F‎‏‪-‮⁦-⁩﻿]/g;

/** Hace visibles los controles bidi y C0 (anti-spoofing U+202E): U+202E → «⟦U+202E⟧». No toca letras ni saltos de línea. */
export function neutralizarTexto(s) {
  const t = String(s);
  return t.replace(RE_PELIGROSOS, (c) => `⟦U+${c.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0')}⟧`);
}

const ATRIBUTOS_PROHIBIDOS = new Set(['innerhtml', 'outerhtml', 'srcdoc', 'html', 'insertadjacenthtml']);
const ATRIBUTOS_URL = new Set(['href', 'src', 'action', 'formaction', 'xlink:href', 'poster', 'data']);

/** true si la URL es segura para href/src (relativa, #, /, http(s), mailto). `javascript:`, `data:`, `vbscript:` → false. */
export function urlSegura(valor) {
  const v = String(valor).replace(/[\u0000- \u007F-\u009F]/g, '').toLowerCase();
  if (v === '' || v.startsWith('#') || v.startsWith('/') || v.startsWith('?') || v.startsWith('./') || v.startsWith('../')) return true;
  const m = /^([a-z][a-z0-9+.-]*):/.exec(v);
  if (!m) return true; // relativa sin esquema
  return ['http', 'https', 'mailto'].includes(m[1]);
}

const esNodo = (x) => x !== null && typeof x === 'object' && typeof x.nodeType === 'number';

function nombreClases(c) {
  if (!c) return '';
  if (typeof c === 'string') return c;
  if (Array.isArray(c)) return c.map(nombreClases).filter(Boolean).join(' ');
  if (typeof c === 'object') return Object.entries(c).filter(([, v]) => v).map(([k]) => k).join(' ');
  return String(c);
}

function agregarHijos(padre, hijos) {
  for (const h of hijos) {
    if (h === null || h === undefined || h === false || h === true) continue;
    if (Array.isArray(h)) { agregarHijos(padre, h); continue; }
    if (esNodo(h)) { padre.appendChild(h); continue; }
    padre.appendChild(doc().createTextNode(neutralizarTexto(h)));
  }
}

/** Crea un elemento. `el('div', {class:'x', onclick: fn}, 'texto', otroNodo, [lista])`. Los datos van SIEMPRE como texto. */
export function el(tag, attrs, ...hijos) {
  const d = doc();
  const esSvg = ETIQUETAS_SVG.has(tag);
  const nodo = esSvg ? d.createElementNS(NS_SVG, tag) : d.createElement(tag);
  let atributos = null;
  if (attrs !== null && attrs !== undefined) {
    if (typeof attrs === 'object' && !Array.isArray(attrs) && !esNodo(attrs)) atributos = attrs;
    else hijos.unshift(attrs);
  }
  if (atributos) {
    for (const [k, v] of Object.entries(atributos)) {
      const clave = k;
      const baja = k.toLowerCase();
      if (ATRIBUTOS_PROHIBIDOS.has(baja)) throw new Error(`ui.el: atributo prohibido «${k}» (los datos entran como texto)`);
      if (v === null || v === undefined || v === false) continue;
      if (baja === 'class' || baja === 'clase' || baja === 'classname') {
        const c = nombreClases(v);
        if (c) { if (esSvg) nodo.setAttribute('class', c); else nodo.className = c; }
      } else if (baja === 'dataset') {
        for (const [dk, dv] of Object.entries(v)) if (dv !== null && dv !== undefined) nodo.dataset[dk] = String(dv);
      } else if (baja === 'style') {
        if (typeof v === 'string') nodo.style.cssText = v;
        else for (const [sk, sv] of Object.entries(v)) {
          if (sk.startsWith('--')) nodo.style.setProperty(sk, String(sv)); else nodo.style[sk] = String(sv);
        }
      } else if (baja.startsWith('on')) {
        if (typeof v !== 'function') throw new Error(`ui.el: «${k}» debe ser una función`);
        nodo.addEventListener(baja.slice(2), v);
      } else if (ATRIBUTOS_URL.has(baja)) {
        if (!urlSegura(v)) throw new Error(`ui.el: URL no permitida en «${k}»`);
        nodo.setAttribute(clave, String(v));
      } else if (v === true) {
        nodo.setAttribute(clave, '');
        if (baja === 'checked' || baja === 'selected') nodo[baja] = true;
      } else if ((baja === 'value') && !esSvg) {
        nodo.value = String(v);
        nodo.setAttribute('value', String(v));
      } else {
        nodo.setAttribute(clave, neutralizarTexto(v));
      }
    }
  }
  agregarHijos(nodo, hijos);
  return nodo;
}

/** Vacía un contenedor sin innerHTML. */
export function limpiar(nodo) {
  while (nodo.firstChild) nodo.removeChild(nodo.firstChild);
  return nodo;
}

/** Sustituye el contenido de `nodo` por `hijos`. */
export function reemplazar(nodo, ...hijos) {
  limpiar(nodo);
  agregarHijos(nodo, hijos);
  return nodo;
}

// ───────────────────────── estilos de página (CSP) ─────────────────────────

const hojasInstaladas = new Set();

/**
 * Instala una vez (por `id`) una hoja de estilos propia de una página. La CSP del panel (`style-src 'self'`) prohíbe `<style>` y `style="…"`
 * en línea, pero NO las hojas construidas por CSSOM: esta función usa `new CSSStyleSheet()` + `document.adoptedStyleSheets`.
 * Las clases compartidas viven en styles.css; esto es para estilos específicos de una pantalla (p. ej. `.p3-*`).
 * Devuelve true si quedó instalada (o ya lo estaba); false si el navegador no soporta hojas construidas (la pantalla debe seguir siendo legible).
 */
export function instalarEstilos(id, css) {
  if (hojasInstaladas.has(id)) return true;
  const d = typeof globalThis.document === 'undefined' ? null : globalThis.document;
  const Hoja = globalThis.CSSStyleSheet;
  if (!d || !('adoptedStyleSheets' in d) || typeof Hoja !== 'function' || typeof Hoja.prototype.replaceSync !== 'function') return false;
  try {
    const hoja = new Hoja();
    hoja.replaceSync(String(css));
    d.adoptedStyleSheets = [...d.adoptedStyleSheets, hoja];
    hojasInstaladas.add(id);
    return true;
  } catch (_) { return false; }
}

// ───────────────────────── iconos (SVG propio, trazo 1,75 px; los trazos viven en lib/iconos.js) ─────────────────────────

export const NOMBRES_ICONOS = NOMBRES_ICONOS_BASE;

/** Elementos SVG (sin el <svg> contenedor) de un icono 24×24: sirve para componer ilustraciones. */
export function trazosSvg(nombre) {
  return trazosDe(nombre).map(([tag, a]) => el(tag, a));
}

/** Icono SVG de 24×24 (nombres y alias: lib/iconos.js). `tamano`/`tam` en px. Decorativo (aria-hidden) salvo que se pase `etiqueta`. */
export function icono(nombre, { tam, tamano, clase = '', etiqueta } = {}) {
  const t = tamano ?? tam ?? 16;
  const svg = el('svg', {
    viewBox: '0 0 24 24', width: t, height: t, fill: 'none', stroke: 'currentColor', 'stroke-width': TRAZO, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
    focusable: 'false', class: ['icono', clase], ...(etiqueta ? { role: 'img', 'aria-label': etiqueta } : { 'aria-hidden': 'true' }),
  });
  for (const [tag, a] of trazosDe(nombre)) svg.appendChild(el(tag, a));
  return svg;
}

// ───────────────────────── formato (puro) ─────────────────────────

const ISO = /^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?$/;
const MONEDAS_0 = new Set(['JPY', 'CLP', 'KRW', 'VND', 'ISK', 'UGX', 'PYG', 'XAF', 'XOF', 'XPF', 'RWF', 'KMF', 'GNF', 'DJF', 'BIF', 'VUV']);
const MONEDAS_3 = new Set(['BHD', 'KWD', 'OMR', 'JOD', 'TND', 'LYD', 'IQD']);
const SIMBOLOS = { EUR: '€', USD: 'US$', GBP: '£', JPY: '¥' };
const NBSP = ' ';

function aFecha(valor) {
  if (valor instanceof Date) return Number.isNaN(valor.getTime()) ? null : valor;
  if (typeof valor === 'number') { const d = new Date(valor); return Number.isNaN(d.getTime()) ? null : d; }
  if (typeof valor !== 'string' || !ISO.test(valor.trim())) return null;
  const s = valor.trim();
  const d = new Date(/^\d{4}-\d{2}-\d{2}$/.test(s) ? s + 'T00:00:00Z' : s);
  return Number.isNaN(d.getTime()) ? null : d;
}

function agrupar(enteroTexto) { return enteroTexto.replace(/\B(?=(\d{3})+(?!\d))/g, '.'); }

function aBigInt(v) {
  if (typeof v === 'bigint') return v;
  if (typeof v === 'number' && Number.isSafeInteger(v)) return BigInt(v);
  if (typeof v === 'string' && /^-?\d{1,18}$/.test(v.trim())) return BigInt(v.trim());
  return null;
}

export const fmt = {
  /** ISO Z → «06/11/2026 14:02» en la zona del navegador (o `{tz:'UTC'}`); `{segundos:true}` añade :SS. Inválido → «—». */
  fecha(valor, { tz, segundos = false } = {}) {
    const d = aFecha(valor);
    if (!d) return '—';
    const soloDia = typeof valor === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(valor.trim());
    const opc = { day: '2-digit', month: '2-digit', year: 'numeric', timeZone: soloDia ? 'UTC' : tz };
    if (!soloDia) Object.assign(opc, { hour: '2-digit', minute: '2-digit', hourCycle: 'h23', ...(segundos ? { second: '2-digit' } : {}) });
    const p = Object.fromEntries(new Intl.DateTimeFormat('es-ES', opc).formatToParts(d).map((x) => [x.type, x.value]));
    const dia = `${p.day}/${p.month}/${p.year}`;
    if (soloDia) return dia;
    return `${dia} ${p.hour}:${p.minute}${segundos ? ':' + p.second : ''}`;
  },
  /** «hace 5 min», «hace 2 h», «en 3 min», «ahora». `ahora` (ms) inyectable para pruebas. */
  relativo(valor, ahora = Date.now()) {
    const d = aFecha(valor);
    if (!d) return '—';
    const seg = Math.round((ahora - d.getTime()) / 1000);
    const abs = Math.abs(seg);
    const pre = seg >= 0 ? 'hace ' : 'en ';
    if (abs < 5) return 'ahora';
    if (abs < 60) return `${pre}${abs} s`;
    if (abs < 3600) return `${pre}${Math.floor(abs / 60)} min`;
    if (abs < 86400) return `${pre}${Math.floor(abs / 3600)} h`;
    if (abs < 86400 * 45) return `${pre}${Math.floor(abs / 86400)} d`;
    return fmt.fecha(valor, { tz: 'UTC' }).slice(0, 10);
  },
  /** Entero en unidad menor + moneda → «1.234,56 €». Sin float: aritmética BigInt. Sin moneda o no entero → «—». */
  dinero(monto, moneda) {
    const n = aBigInt(monto);
    if (n === null) return '—';
    const cod = typeof moneda === 'string' ? moneda.trim().toUpperCase() : '';
    if (!/^[A-Z]{3}$/.test(cod)) return `${n < 0n ? '-' : ''}${agrupar((n < 0n ? -n : n).toString())}${NBSP}(sin moneda)`;
    const dec = MONEDAS_0.has(cod) ? 0 : MONEDAS_3.has(cod) ? 3 : 2;
    const neg = n < 0n;
    const abs = neg ? -n : n;
    const factor = 10n ** BigInt(dec);
    const entero = abs / factor;
    const frac = abs % factor;
    const cuerpo = agrupar(entero.toString()) + (dec ? ',' + frac.toString().padStart(dec, '0') : '');
    return `${neg ? '-' : ''}${cuerpo}${NBSP}${SIMBOLOS[cod] || cod}`;
  },
  /** Puntos básicos (1234) → «12,34 %». Quita ceros finales: 1250 → «12,5 %», 1200 → «12 %». */
  pct(bp) {
    const n = aBigInt(bp);
    if (n === null) return '—';
    const neg = n < 0n;
    const abs = neg ? -n : n;
    const ent = abs / 100n;
    const fr = (abs % 100n).toString().padStart(2, '0').replace(/0+$/, '');
    return `${neg ? '-' : ''}${agrupar(ent.toString())}${fr ? ',' + fr : ''}${NBSP}%`;
  },
  /** 1536 → «1,5 KB». */
  bytes(n) {
    if (typeof n !== 'number' || !Number.isFinite(n) || n < 0) return '—';
    if (n < 1024) return `${Math.round(n)} B`;
    const u = ['KB', 'MB', 'GB', 'TB'];
    let v = n / 1024; let i = 0;
    while (v >= 1024 && i < u.length - 1) { v /= 1024; i += 1; }
    const t = v >= 100 ? Math.round(v).toString() : v.toFixed(1).replace('.', ',').replace(/,0$/, '');
    return `${t} ${u[i]}`;
  },
  /** Número entero o decimal con separador de miles es-ES (para recuentos, no dinero). */
  num(n, decimales = 0) {
    if (typeof n !== 'number' || !Number.isFinite(n)) return '—';
    const [e, f] = Math.abs(n).toFixed(decimales).split('.');
    return `${n < 0 ? '-' : ''}${agrupar(e)}${f ? ',' + f : ''}`;
  },
  /**
   * Número es-ES para recuentos y métricas: 1.234 · 1.234,5 (`decimales`) · `compacto` → «12,3 k» / «1,2 M» · `signo` añade «+» a los positivos.
   * No es dinero (usa fmt.dinero). Inválido → «—». El cero es un dato: «0».
   */
  numero(n, { decimales = 0, compacto = false, signo = false } = {}) {
    if (typeof n !== 'number' || !Number.isFinite(n)) return '—';
    let v = n; let sufijo = '';
    let dec = decimales;
    if (compacto) {
      const a = Math.abs(n);
      if (a >= 1e6) { v = n / 1e6; sufijo = '\u00A0M'; if (!decimales) dec = 1; }
      else if (a >= 1e3) { v = n / 1e3; sufijo = '\u00A0k'; if (!decimales) dec = 1; }
    }
    let t = fmt.num(v, dec);
    if (compacto && dec) t = t.replace(/,0+$/, '');
    return `${signo && n > 0 ? '+' : ''}${t}${sufijo}`;
  },
  /** milisegundos → «850 ms», «4,2 s», «3 min 05 s». */
  duracion(ms) {
    if (typeof ms !== 'number' || !Number.isFinite(ms) || ms < 0) return '—';
    if (ms < 1000) return `${Math.round(ms)} ms`;
    const s = ms / 1000;
    if (s < 60) return `${s.toFixed(1).replace('.', ',').replace(/,0$/, '')} s`;
    const m = Math.floor(s / 60);
    return `${m} min ${String(Math.round(s % 60)).padStart(2, '0')} s`;
  },
  /** Texto de dato con `null`/vacío → «—». */
  texto(v) { return v === null || v === undefined || v === '' ? '—' : String(v); },
};

// ───────────────────────── chips y estados ─────────────────────────

const ESTADOS = {
  // estados de etapa (docs/06 §5)
  aprobado: ['ok', 'Aprobado'], en_qa: ['info', 'En revisión'], en_progreso: ['info', 'En progreso'], pendiente: ['neutro', 'Pendiente'],
  bloqueado: ['error', 'Bloqueado'], escalado: ['aviso', 'Pasó a tu decisión'], obsoleta: ['aviso', 'Desactualizada'], obsoleto: ['aviso', 'Desactualizada'],
  espera_firma: ['acento', 'Espera tu firma'], esperando_firma: ['acento', 'Espera tu firma'], gate_pendiente: ['acento', 'Espera tu firma'],
  vigente: ['ok', 'Vigente'], vencido: ['error', 'Vencido'],
  // fases de oferta
  borrador: ['neutro', 'Borrador'], en_construccion: ['info', 'En construcción'], listo_para_activar: ['info', 'Listo para activar'],
  en_test: ['info', 'En prueba'], validada: ['ok', 'Validada'], fallida: ['error', 'Fallida'], inconclusa: ['aviso', 'Inconclusa'],
  escalando: ['ok', 'Escalando'], retirada: ['neutro', 'Retirada'], pausada: ['aviso', 'Pausada'],
  // semáforos y resultados
  verde: ['ok', 'Verde'], amarillo: ['aviso', 'Amarillo'], rojo: ['error', 'Rojo'], pendiente_externo: ['neutro', 'Espera algo de afuera'],
  ok: ['ok', 'OK'], error: ['error', 'Error'], fallo: ['error', 'Fallo'], parcial: ['aviso', 'Parcial'], simulado: ['info', 'Simulacro'],
  corriendo: ['info', 'En marcha'], terminado: ['ok', 'Terminado'],
};

/** Icono propio de cada estado conocido (el resto usa el del tono). */
const ICONO_ESTADO = {
  aprobado: 'check', en_qa: 'ojo', en_progreso: 'progreso', pendiente: 'circulo-punteado', bloqueado: 'candado', escalado: 'escalar', obsoleta: 'reloj-alerta', obsoleto: 'reloj-alerta',
  espera_firma: 'usuario', esperando_firma: 'usuario', gate_pendiente: 'usuario', vigente: 'ok', vencido: 'reloj-alerta',
  borrador: 'lapiz', en_construccion: 'progreso', listo_para_activar: 'ok', en_test: 'play', validada: 'ok', fallida: 'x-circulo', inconclusa: 'ayuda', escalando: 'tendencia-sube', retirada: 'archivar', pausada: 'pausa',
  verde: 'ok', amarillo: 'alerta', rojo: 'x-circulo', pendiente_externo: 'reloj', ok: 'ok', error: 'x-circulo', fallo: 'x-circulo', parcial: 'alerta', simulado: 'info', corriendo: 'progreso', terminado: 'check',
};

/** {tono, texto} para un estado/fase/semáforo conocido; desconocido → neutro con el texto original (neutralizado). */
export function infoEstado(estadoClave) {
  if (estadoClave === null || estadoClave === undefined || estadoClave === '') return { tono: 'neutro', texto: '—' };
  const crudo = String(estadoClave);
  const k = crudo.toLowerCase();
  const hit = ESTADOS[k];
  if (hit) return { tono: hit[0], texto: hit[1] };
  return { tono: 'neutro', texto: crudo.replace(/_/g, ' ') };
}

/** Nombre del icono de un estado: el suyo, o el de su tono; neutro desconocido → 'circulo'. */
export function iconoDeEstado(estadoClave) {
  const k = String(estadoClave ?? '').toLowerCase();
  if (ICONO_ESTADO[k]) return ICONO_ESTADO[k];
  return iconoDeTono(infoEstado(estadoClave).tono) || 'circulo';
}

/**
 * Chip: etiqueta con tono. Los tonos de estado (ok, aviso, grave, error/critico, acento) llevan SIEMPRE un icono (el color nunca va solo);
 * `info` lleva un punto y `neutro` nada. `{icono: 'nombre'}` fuerza uno; `{icono: false}` lo quita.
 */
export function chip(texto, tono = 'neutro', { icono: nombreIcono } = {}) {
  const t = normalizarTono(tono);
  const ic = nombreIcono === false ? null : (nombreIcono || (t === 'info' ? null : iconoDeTono(t)));
  return el('span', { class: ['chip', `chip--${t}`, ic && 'chip--con-icono'] }, ic ? icono(ic, { tam: 12 }) : null, texto);
}

/** Chip de estado con icono + etiqueta humana: aprobado, en_QA, en_progreso, pendiente, bloqueado, escalado, obsoleta, vigente, vencido, espera_firma… */
export function estadoIcono(estadoClave) {
  const { tono, texto } = infoEstado(estadoClave);
  const c = chip(texto, tono, { icono: iconoDeEstado(estadoClave) });
  c.dataset.estado = String(estadoClave ?? '');
  return c;
}

/** Igual que estadoIcono (se conserva el nombre del contrato original). */
export function estadoChip(estadoClave) { return estadoIcono(estadoClave); }

// ───────────────────────── gráficos mínimos (SVG propio) ─────────────────────────

/** Puntos de una sparkline (puro): valores → "x,y x,y …" en un lienzo ancho×alto con margen 2. null si <2 valores válidos. */
export function puntosSparkline(valores, ancho = 80, alto = 22) {
  const v = (Array.isArray(valores) ? valores : []).filter((x) => typeof x === 'number' && Number.isFinite(x));
  if (v.length < 2) return null;
  const min = Math.min(...v); const max = Math.max(...v);
  const rango = max - min || 1;
  const paso = (ancho - 4) / (v.length - 1);
  return v.map((x, i) => `${(2 + i * paso).toFixed(1)},${(alto - 2 - ((x - min) / rango) * (alto - 4)).toFixed(1)}`).join(' ');
}

export function sparkline(valores, { ancho = 80, alto = 22, etiqueta = 'Tendencia', ultimo = true } = {}) {
  const pts = puntosSparkline(valores, ancho, alto);
  const svg = el('svg', { viewBox: `0 0 ${ancho} ${alto}`, width: ancho, height: alto, class: 'sparkline', role: 'img', 'aria-label': etiqueta });
  if (pts) {
    const v = (Array.isArray(valores) ? valores : []).filter((x) => typeof x === 'number' && Number.isFinite(x));
    svg.appendChild(el('title', null, `${etiqueta}: de ${fmt.numero(v[0], { decimales: Number.isInteger(v[0]) ? 0 : 1 })} a ${fmt.numero(v[v.length - 1], { decimales: Number.isInteger(v[v.length - 1]) ? 0 : 1 })} (mín. ${fmt.numero(Math.min(...v), { decimales: 1 }).replace(/,0$/, '')}, máx. ${fmt.numero(Math.max(...v), { decimales: 1 }).replace(/,0$/, '')})`));
    svg.appendChild(el('polyline', { points: pts, fill: 'none', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round' }));
    if (ultimo) {
      const [x, y] = pts.split(' ').pop().split(',').map(Number);
      svg.appendChild(el('circle', { cx: x, cy: y, r: 2.5, fill: 'currentColor', stroke: 'none' }));
    }
  }
  return svg;
}

/** Barra apilada horizontal: segmentos [{valor, tono, titulo}] (solo CSS; ancho proporcional). */
export function barraApilada(segmentos, { etiqueta = '' } = {}) {
  const lista = (segmentos || []).filter((s) => s && typeof s.valor === 'number' && s.valor > 0);
  const total = lista.reduce((a, s) => a + s.valor, 0);
  const barra = el('div', { class: 'barra-apilada', role: 'img', 'aria-label': etiqueta || lista.map((s) => `${s.titulo || s.tono}: ${s.valor}`).join(', ') });
  for (const s of lista) {
    barra.appendChild(el('span', { class: ['barra-apilada__seg', `tono-${normalizarTono(s.tono)}`], title: `${s.titulo || ''} ${s.valor}`.trim(), style: { '--p': `${((s.valor / total) * 100).toFixed(2)}%` } }));
  }
  if (!lista.length) barra.classList.add('barra-apilada--vacia');
  return barra;
}

// ───────────────────────── tarjetas, secciones, bloques ─────────────────────────

/** Tarjeta de métrica. `tendencia`: array de números (sparkline) o texto («▲ 12 % vs ayer»). `valor` null → «—». */
export function tarjeta({ titulo, valor, detalle, tono, tendencia } = {}) {
  const t = tono ? normalizarTono(tono, null) : null;
  const sinValor = valor === null || valor === undefined || valor === '';
  const largo = typeof valor === 'string' && valor.length > 12;
  const muyLargo = typeof valor === 'string' && valor.length > 28;
  return el('article', { class: ['tarjeta', t && `tarjeta--${t}`, sinValor && 'tarjeta--sin-valor', largo && 'tarjeta--valor-largo', muyLargo && 'tarjeta--valor-muy-largo'] },
    el('h3', { class: 'tarjeta__titulo' }, titulo),
    el('div', { class: 'tarjeta__valor' }, sinValor ? '—' : valor),
    detalle ? el('div', { class: 'tarjeta__detalle' }, detalle) : null,
    Array.isArray(tendencia) ? el('div', { class: 'tarjeta__tendencia' }, sparkline(tendencia)) : (tendencia ? el('div', { class: 'tarjeta__tendencia' }, tendencia) : null));
}

let contadorId = 0;
const nuevoId = (pref) => `${pref}-${++contadorId}`;

/** Sección con título (h2), acciones a la derecha y ayuda («qué es esto») opcional. `glosario`: clave del glosario (o texto corto directo, como en `ayuda`) → botón «?» junto al título. */
export function seccion(titulo, cuerpo, { acciones, ayuda, id, clase, glosario } = {}) {
  const hid = id || nuevoId('sec');
  const h2 = el('h2', { id: hid, class: 'seccion__titulo' }, titulo);
  return el('section', { class: ['seccion', clase], 'aria-labelledby': hid },
    el('header', { class: 'seccion__cab' },
      glosario ? el('div', { class: 'seccion__tit' }, h2, ayudaTermino(glosario, { titulo })) : h2,
      acciones ? el('div', { class: 'seccion__acciones' }, acciones) : null),
    ayuda ? el('p', { class: 'seccion__ayuda' }, ayuda) : null,
    el('div', { class: 'seccion__cuerpo' }, cuerpo));
}

/** Lista clave/valor densa. `pares`: [[clave, valor]] u objeto. `valor` null → «—». */
export function kv(pares, { clase } = {}) {
  const lista = Array.isArray(pares) ? pares : Object.entries(pares || {});
  const dl = el('dl', { class: ['kv', clase] });
  for (const [k, v] of lista) {
    dl.appendChild(el('dt', null, k));
    dl.appendChild(el('dd', null, v === null || v === undefined || v === '' ? el('span', { class: 'texto-tenue' }, '—') : v));
  }
  return dl;
}

/** Enlace interno de hash: enlace('Ofertas', '#/ofertas'). */
export function enlace(texto, href, attrs = {}) {
  return el('a', { class: 'enlace', href, ...attrs }, texto);
}

/**
 * Comando copiable en un bloque CERRADO «Cómo hacerlo» con botón Copiar siempre visible (se copia sin abrirlo).
 * `abierto: true` lo deja abierto (úsalo solo si el comando ES la acción de la pantalla); con el modo técnico encendido se abre solo.
 * Compatible con la firma anterior `comando(texto, {etiqueta})`.
 */
export function comando(texto, { titulo = 'Cómo hacerlo', nota, abierto, etiqueta = 'Copiar comando' } = {}) {
  const cmd = String(texto);
  const fijo = abierto === true;
  const det = el('details', { class: 'comando', 'data-sigue-modo': '1', dataset: { fijo: fijo ? '1' : '0' } });
  if (fijo || estado.modoTecnico) det.open = true;
  det.appendChild(el('summary', { class: 'comando__cab' },
    icono('chevron-derecha', { tam: 14, clase: 'comando__chev' }),
    icono('terminal', { tam: 15, clase: 'comando__icono' }),
    el('span', { class: 'comando__titulo' }, titulo),
    el('button', {
      type: 'button', class: 'btn btn--chico comando__copiar', 'aria-label': `${etiqueta}: ${cmd.slice(0, 80)}`,
      onclick: (ev) => { ev.preventDefault(); ev.stopPropagation(); copiar(cmd); },
    }, icono('copiar', { tam: 14 }), 'Copiar')));
  det.appendChild(el('div', { class: 'comando__cuerpo' },
    el('code', { class: 'comando__texto', tabindex: '0' }, cmd),
    nota ? el('p', { class: 'comando__nota' }, nota) : null));
  return det;
}

/**
 * Pie de pantalla «leído hace …» con un icono «i» (popover con las rutas y la hora exacta). Las rutas en línea («Fuente: …») solo se ven con el
 * modo técnico. Se conserva el nombre y la firma del contrato (CONTRATO §5).
 */
export function fuenteInfo({ fuente: rutas, generado_en, vacio, avisos } = {}, ahora = Date.now()) {
  const lista = Array.isArray(rutas) ? rutas : (rutas ? [rutas] : []);
  return el('footer', { class: 'fuente-info' },
    fuente(lista, { leido: generado_en, ahora }),
    el('span', { class: 'fuente-info__rutas solo-tecnico' },
      el('span', null, 'Fuente: '),
      lista.length ? lista.map((f, i) => [i ? ', ' : '', el('code', null, f)]) : el('span', { class: 'texto-tenue' }, 'sin fuente declarada')),
    generado_en ? el('span', { class: 'fuente-info__hora', title: fmt.fecha(generado_en, { segundos: true }) }, el('span', { class: 'solo-tecnico' }, ' · '), `leído ${fmt.relativo(generado_en, ahora)}`) : null,
    vacio ? chip('Sin datos todavía: el archivo de origen aún no existe', 'aviso') : null,
    Array.isArray(avisos) && avisos.length ? avisos.map((a) => el('span', { class: 'fuente-info__aviso' }, ` · ${typeof a === 'string' ? a : JSON.stringify(a)}`)) : null);
}

/** Cabecera de pantalla: título, «qué es» y acciones. */
export function encabezado({ titulo, descripcion, acciones } = {}) {
  return el('header', { class: 'pagina-cab' },
    el('div', { class: 'pagina-cab__texto' },
      el('h1', { class: 'pagina-cab__titulo' }, titulo),
      descripcion ? el('p', { class: 'pagina-cab__desc' }, descripcion) : null),
    acciones ? el('div', { class: 'pagina-cab__acciones' }, acciones) : null);
}

// ───────────────────────── estados: vacío, cargando, error ─────────────────────────

/** Estado vacío útil. `pista`: qué hay que hacer; `comando`: texto copiable que lo llena; `fuente`: archivo esperado. */
export function vacio(texto, { pista, comando: cmd, fuente, icono: nombre = 'caja' } = {}) {
  return el('div', { class: 'vacio', role: 'status' },
    el('span', { class: 'vacio__icono' }, icono(nombre, { tam: 22 })),
    el('p', { class: 'vacio__texto' }, texto),
    pista ? el('p', { class: 'vacio__pista' }, pista) : null,
    cmd ? comando(cmd, { abierto: true }) : null,
    fuente ? el('p', { class: ['vacio__fuente', 'solo-tecnico'] }, 'Se esperaba: ', el('code', null, Array.isArray(fuente) ? fuente.join(', ') : fuente)) : null);
}

export function cargando(texto = 'Cargando…') {
  return el('div', { class: 'cargando', role: 'status', 'aria-live': 'polite' },
    el('span', { class: 'cargando__giro', 'aria-hidden': 'true' }),
    el('span', null, texto),
    el('div', { class: 'cargando__esqueleto', 'aria-hidden': 'true' }, el('i'), el('i'), el('i')));
}

const PISTAS_ERROR = {
  sin_conexion: 'El programa del panel no responde. Vuelve a arrancarlo con `.venv/bin/python -m dashboard` y recarga esta página.',
  token_invalido: 'Falta la clave de acceso de esta sesión: abre el enlace completo que muestra la terminal al arrancar el panel (termina en `#t=…`).',
  tiempo_agotado: 'La lectura tardó demasiado. Prueba de nuevo; si se repite, puede que algún archivo sea muy grande.',
};

/** Caja de error. Muestra código y mensaje; nunca trazas. `err` puede ser ErrorApi, Error o texto. */
export function errorBox(err, { reintentar } = {}) {
  const codigo = (err && err.codigo) || (err && err.name) || 'error';
  const mensaje = (err && (err.mensaje || err.message)) || (typeof err === 'string' ? err : 'Pasó algo inesperado.');
  return el('div', { class: 'error-box', role: 'alert' },
    el('div', { class: 'error-box__cab' }, icono('alerta', { tam: 16 }), el('strong', null, 'No se pudo cargar'), el('span', { class: 'error-box__codigo', title: 'Código del error, por si hay que consultarlo' }, chip(codigo, 'error'))),
    el('p', { class: 'error-box__msg' }, mensaje),
    PISTAS_ERROR[codigo] ? el('p', { class: 'error-box__pista' }, PISTAS_ERROR[codigo]) : null,
    reintentar ? el('button', { type: 'button', class: 'btn btn--chico', onclick: reintentar }, 'Reintentar') : null);
}

// ───────────────────────── portapapeles y avisos ─────────────────────────

/** Copia al portapapeles (API moderna, con respaldo `execCommand`). Devuelve Promise<boolean> y avisa con un toast. */
export async function copiar(texto, { silencioso = false } = {}) {
  const t = String(texto);
  let ok = false;
  try {
    if (globalThis.navigator && navigator.clipboard && globalThis.isSecureContext !== false) { await navigator.clipboard.writeText(t); ok = true; }
  } catch (_) { ok = false; }
  if (!ok) {
    try {
      const d = doc();
      const ta = el('textarea', { readonly: true, 'aria-hidden': 'true', class: 'oculto-copia' });
      ta.value = t;
      d.body.appendChild(ta);
      ta.select();
      ok = d.execCommand('copy');
      d.body.removeChild(ta);
    } catch (_) { ok = false; }
  }
  if (!silencioso) toast(ok ? 'Copiado: ya lo puedes pegar' : 'No se pudo copiar: selecciona el texto y cópialo a mano', ok ? 'ok' : 'error');
  return ok;
}

let contenedorToasts = null;

/** Aviso efímero (4 s; 7 s si es error). Devuelve el elemento. */
export function toast(texto, tono = 'info', { duracion } = {}) {
  const d = doc();
  if (!contenedorToasts || !contenedorToasts.isConnected) {
    contenedorToasts = el('div', { class: 'toasts', role: 'region', 'aria-label': 'Avisos', 'aria-live': 'polite' });
    d.body.appendChild(contenedorToasts);
  }
  const t = normalizarTono(tono, 'info');
  const nodo = el('div', { class: ['toast', `toast--${t}`], role: t === 'error' ? 'alert' : 'status' }, el('span', null, texto));
  const quitar = () => { if (nodo.parentNode) nodo.parentNode.removeChild(nodo); };
  nodo.addEventListener('click', quitar);
  contenedorToasts.appendChild(nodo);
  while (contenedorToasts.children.length > 5) contenedorToasts.removeChild(contenedorToasts.firstChild);
  setTimeout(quitar, duracion ?? (t === 'error' ? 7000 : 4000));
  return nodo;
}

// ───────────────────────── modal ─────────────────────────

const modalesAbiertos = new Set();

/** Cierra todos los modales abiertos (devuelve el foco como siempre). El router lo llama al cambiar de pantalla. Devuelve cuántos cerró. */
export function cerrarModales() {
  const n = modalesAbiertos.size;
  for (const cerrar of [...modalesAbiertos].reverse()) cerrar(); // el último abierto primero: el foco acaba en quien abrió el primero
  return n;
}

const FOCALIZABLES = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Diálogo modal accesible (foco atrapado, Esc cierra, devuelve el foco).
 * acciones: [{texto, tono:'primario'|'peligro'|'', alClick(cerrar), cierra=true, deshabilitado}]
 * Devuelve {cerrar, elemento, cuerpo}.
 */
export function modal({ titulo, cuerpo, acciones = [], ancho } = {}) {
  const d = doc();
  const previo = d.activeElement;
  const tid = nuevoId('modal-t');
  let cerrado = false;
  const cuerpoEl = el('div', { class: 'modal__cuerpo' }, cuerpo);
  const cerrar = () => {
    if (cerrado) return;
    cerrado = true;
    modalesAbiertos.delete(cerrar);
    d.removeEventListener('keydown', alTecla, true);
    if (fondo.parentNode) fondo.parentNode.removeChild(fondo);
    if (previo && typeof previo.focus === 'function') { try { previo.focus(); } catch (_) { /* nodo ya no existe */ } }
  };
  const botones = acciones.map((a) => el('button', {
    type: 'button',
    class: ['btn', a.tono === 'primario' && 'btn--primario', a.tono === 'peligro' && 'btn--peligro'],
    disabled: a.deshabilitado ? true : null,
    onclick: async () => {
      if (a.alClick) { const r = await a.alClick(cerrar); if (r === false) return; }
      if (a.cierra !== false) cerrar();
    },
  }, a.texto));
  const caja = el('div', { class: 'modal', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': tid, tabindex: '-1', style: ancho ? { '--modal-ancho': ancho } : null },
    el('header', { class: 'modal__cab' },
      el('h2', { id: tid, class: 'modal__titulo' }, titulo),
      el('button', { type: 'button', class: 'btn btn--icono', 'aria-label': 'Cerrar', onclick: cerrar }, icono('cerrar'))),
    cuerpoEl,
    botones.length ? el('footer', { class: 'modal__pie' }, botones) : null);
  const fondo = el('div', { class: 'modal-fondo', onmousedown: (ev) => { if (ev.target === fondo) cerrar(); } }, caja);
  function alTecla(ev) {
    if (ev.key === 'Escape') { ev.stopPropagation(); cerrar(); return; }
    if (ev.key !== 'Tab') return;
    const f = [...caja.querySelectorAll(FOCALIZABLES)];
    if (!f.length) { ev.preventDefault(); caja.focus(); return; }
    const primero = f[0]; const ultimo = f[f.length - 1];
    if (ev.shiftKey && (d.activeElement === primero || d.activeElement === caja)) { ev.preventDefault(); ultimo.focus(); }
    else if (!ev.shiftKey && d.activeElement === ultimo) { ev.preventDefault(); primero.focus(); }
  }
  d.addEventListener('keydown', alTecla, true);
  modalesAbiertos.add(cerrar);
  d.body.appendChild(fondo);
  const campo = caja.querySelector('input, select, textarea') || caja.querySelector('.modal__pie .btn--primario, .modal__pie .btn--peligro') || caja.querySelector('.modal__pie .btn') || caja;
  try { campo.focus(); } catch (_) { /* sin foco */ }
  return { cerrar, elemento: fondo, cuerpo: cuerpoEl };
}

/** Confirmación: Promise<boolean>. */
export function confirmar({ titulo, mensaje, textoOk = 'Confirmar', textoCancelar = 'Cancelar', tono = 'primario' } = {}) {
  return new Promise((resolver) => {
    let resuelto = false;
    const fin = (v) => { if (!resuelto) { resuelto = true; resolver(v); } };
    const m = modal({
      titulo, cuerpo: typeof mensaje === 'string' ? el('p', null, mensaje) : mensaje,
      acciones: [
        { texto: textoCancelar, alClick: () => fin(false) },
        { texto: textoOk, tono, alClick: () => fin(true) },
      ],
    });
    // cierre por Esc/fondo/✕ = cancelar
    const obs = setInterval(() => { if (!m.elemento.isConnected) { clearInterval(obs); fin(false); } }, 200);
  });
}

// ───────────────────────── tabla ─────────────────────────

/** Valor de `fila` en una ruta con puntos: valorDe({a:{b:1}}, 'a.b') → 1. */
export function valorDe(fila, clave) {
  if (fila === null || fila === undefined) return undefined;
  if (typeof clave === 'function') return clave(fila);
  if (typeof clave !== 'string' || clave === '') return undefined;
  if (Object.prototype.hasOwnProperty.call(fila, clave)) return fila[clave];
  let v = fila;
  for (const parte of clave.split('.')) {
    if (v === null || v === undefined || typeof v !== 'object') return undefined;
    v = v[parte];
  }
  return v;
}

/** Texto plano de un valor, para filtrar/ordenar: objetos se aplanan (dinero {monto,moneda} → «monto moneda»). */
export function textoDeValor(v, profundidad = 0) {
  if (v === null || v === undefined) return '';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean' || typeof v === 'bigint') return String(v);
  if (esNodo(v)) return v.textContent || '';
  if (profundidad > 2) return '';
  if (Array.isArray(v)) return v.map((x) => textoDeValor(x, profundidad + 1)).join(' ');
  if (typeof v === 'object') return Object.values(v).map((x) => textoDeValor(x, profundidad + 1)).join(' ');
  return '';
}

const quitarTildes = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/** Compara dos valores crudos: nulos al final; números numéricamente; fechas ISO como texto; texto con `localeCompare('es', {numeric})`. */
export function compararValores(a, b) {
  const na = a === null || a === undefined || a === '';
  const nb = b === null || b === undefined || b === '';
  if (na && nb) return 0;
  if (na) return 1;
  if (nb) return -1;
  if (typeof a === 'number' && typeof b === 'number') return a - b;
  if (typeof a === 'boolean' && typeof b === 'boolean') return Number(a) - Number(b);
  if (a && typeof a === 'object' && 'monto' in a && b && typeof b === 'object' && 'monto' in b) return Number(a.monto) - Number(b.monto);
  return textoDeValor(a).localeCompare(textoDeValor(b), 'es', { numeric: true, sensitivity: 'base' });
}

/** Ordena (estable, sin mutar). dir: 'asc'|'desc'. Los nulos van siempre al final. `columna.orden(fila)` anula el valor. */
export function ordenarFilas(filas, columna, dir = 'asc') {
  if (!columna) return [...filas];
  const sentido = dir === 'desc' ? -1 : 1;
  const extraer = (f) => (typeof columna.orden === 'function' ? columna.orden(f) : valorDe(f, columna.clave));
  return filas
    .map((f, i) => ({ f, i, v: extraer(f) }))
    .sort((x, y) => {
      const nx = x.v === null || x.v === undefined || x.v === '';
      const ny = y.v === null || y.v === undefined || y.v === '';
      if (nx || ny) return nx === ny ? x.i - y.i : (nx ? 1 : -1);
      return compararValores(x.v, y.v) * sentido || x.i - y.i;
    })
    .map((x) => x.f);
}

/** Filtra por texto: todas las palabras deben aparecer (sin tildes ni mayúsculas) en alguna columna. */
export function filtrarFilas(filas, columnas, consulta) {
  const q = quitarTildes(String(consulta || '').trim());
  if (!q) return [...filas];
  const palabras = q.split(/\s+/).filter(Boolean);
  return filas.filter((f) => {
    const pajar = quitarTildes(columnas.map((c) => textoDeValor(typeof c.orden === 'function' ? c.orden(f) : valorDe(f, c.clave))).join(' \u0001 '));
    return palabras.every((p) => pajar.includes(p));
  });
}

/**
 * Tabla densa, ordenable y filtrable.
 * columnas: [{clave, titulo, ancho?, formato?(valor, fila)→Node|string, ordenable? (por defecto sí), orden?(fila), alinear?:'der'|'centro', numerico?: true (= alinear a la derecha), clase?,
 *             flex?: true → la columna absorbe el ancho sobrante y recorta con «…» (úsalo en la columna de texto largo)}]
 * opciones extra: etiqueta (aria-label), ordenInicial {clave, dir}, maxFilas (500), altoMax ('420px'), claseFila(fila), filtro: true|{placeholder}
 * Devuelve un Element con `.actualizarFilas(filas)` y `.filas`.
 */
export function tabla({ columnas = [], filas = [], filtro, vacio: textoVacio, alClick, etiqueta, ordenInicial, maxFilas = 500, altoMax, claseFila } = {}) {
  columnas = columnas.map((c) => (c && c.numerico && !c.alinear ? { ...c, alinear: 'der' } : c)); // `numerico: true` = alinear a la derecha
  let datos = Array.isArray(filas) ? filas : [];
  let orden = ordenInicial ? { clave: ordenInicial.clave, dir: ordenInicial.dir === 'desc' ? 'desc' : 'asc' } : null;
  let consulta = '';
  let limite = maxFilas;

  const raiz = el('div', { class: 'tabla-wrap' });
  const conteo = el('span', { class: 'tabla-conteo texto-tenue', 'aria-live': 'polite' });
  const entrada = filtro ? el('input', {
    type: 'search', class: 'campo campo--chico', placeholder: (filtro && filtro.placeholder) || 'Filtrar…', 'aria-label': (filtro && filtro.etiqueta) || 'Filtrar filas',
    oninput: (ev) => { consulta = ev.target.value; limite = maxFilas; pintar(); },
  }) : null;
  const barra = (filtro) ? el('div', { class: 'tabla-barra' }, entrada, conteo) : null;
  const cuerpo = el('tbody');
  const thead = el('thead');
  const tablaEl = el('table', { class: 'tabla', 'aria-label': etiqueta || null }, thead, cuerpo);
  const scroll = el('div', { class: 'tabla-scroll', tabindex: '0', role: 'region', 'aria-label': etiqueta ? `${etiqueta} (desplazable)` : 'Tabla desplazable', style: altoMax ? { '--alto-max': altoMax } : null }, tablaEl);
  const zonaVacia = el('div', { class: 'tabla-vacio' });
  const mas = el('button', { type: 'button', class: 'btn btn--chico tabla-mas', onclick: () => { limite += maxFilas; pintar(); } });
  if (barra) raiz.appendChild(barra);
  raiz.appendChild(scroll);
  raiz.appendChild(zonaVacia);
  raiz.appendChild(mas);

  function cabecera() {
    limpiar(thead);
    const tr = el('tr');
    for (const c of columnas) {
      const ordenable = c.ordenable !== false && c.clave !== undefined;
      const activa = orden && orden.clave === c.clave;
      const th = el('th', { scope: 'col', class: [c.alinear && `alinea-${c.alinear}`, ordenable && 'ordenable', c.flex && 'col-flex'], 'aria-sort': activa ? (orden.dir === 'desc' ? 'descending' : 'ascending') : (ordenable ? 'none' : null), style: c.ancho ? { width: c.ancho } : null });
      if (ordenable) {
        th.appendChild(el('button', {
          type: 'button', class: 'th-boton', title: `Ordenar por ${c.titulo}`,
          onclick: () => {
            if (orden && orden.clave === c.clave) orden = orden.dir === 'asc' ? { clave: c.clave, dir: 'desc' } : null;
            else orden = { clave: c.clave, dir: 'asc' };
            cabecera(); pintar();
          },
        }, c.titulo, el('span', { class: 'th-flecha', 'aria-hidden': 'true' }, activa ? (orden.dir === 'desc' ? '▼' : '▲') : '')));
      } else th.appendChild(doc().createTextNode(neutralizarTexto(c.titulo ?? '')));
      tr.appendChild(th);
    }
    thead.appendChild(tr);
  }

  function celda(c, fila) {
    const v = valorDe(fila, c.clave);
    let contenido;
    if (typeof c.formato === 'function') contenido = c.formato(v, fila);
    else if (v === null || v === undefined || v === '') contenido = el('span', { class: 'texto-tenue' }, '—');
    else if (typeof v === 'object' && !esNodo(v)) contenido = ('monto' in v && 'moneda' in v) ? fmt.dinero(v.monto, v.moneda) : textoDeValor(v);
    else contenido = v;
    if (contenido === null || contenido === undefined || contenido === '') contenido = el('span', { class: 'texto-tenue' }, '—');
    return el('td', { class: [c.alinear && `alinea-${c.alinear}`, c.flex && 'col-flex', c.clase], title: c.flex && typeof v === 'string' ? v.slice(0, 400) : null }, contenido);
  }

  function pintar() {
    let vista = consulta ? filtrarFilas(datos, columnas, consulta) : datos;
    if (orden) vista = ordenarFilas(vista, columnas.find((c) => c.clave === orden.clave), orden.dir);
    limpiar(cuerpo);
    const visibles = vista.slice(0, limite);
    for (const fila of visibles) {
      const tr = el('tr', { class: [alClick && 'clicable', claseFila && claseFila(fila)], tabindex: alClick ? '0' : null });
      if (alClick) {
        tr.addEventListener('click', (ev) => alClick(fila, ev));
        tr.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); alClick(fila, ev); } });
      }
      for (const c of columnas) tr.appendChild(celda(c, fila));
      cuerpo.appendChild(tr);
    }
    conteo.textContent = datos.length === vista.length ? `${fmt.num(datos.length)} filas` : `${fmt.num(vista.length)} de ${fmt.num(datos.length)}`;
    limpiar(zonaVacia);
    scroll.hidden = vista.length === 0;
    if (vista.length === 0) {
      const base = textoVacio === undefined ? 'Sin filas.' : textoVacio;
      const contenido = esNodo(base) ? base : (base && typeof base === 'object' ? vacio(base.texto || 'Sin filas.', base) : vacio(consulta ? 'Ninguna fila coincide con el filtro.' : String(base)));
      zonaVacia.appendChild(consulta && datos.length ? vacio('Ninguna fila coincide con el filtro.', { pista: 'Borra o cambia el texto del filtro.' }) : contenido);
    }
    mas.hidden = vista.length <= limite;
    if (!mas.hidden) mas.textContent = `Mostrar ${fmt.num(Math.min(maxFilas, vista.length - limite))} más (${fmt.num(vista.length - limite)} sin mostrar)`;
  }

  cabecera();
  pintar();
  raiz.actualizarFilas = (nuevas) => { datos = Array.isArray(nuevas) ? nuevas : []; raiz.filas = datos; pintar(); };
  raiz.filas = datos;
  return raiz;
}

// ───────────────────────── tabs ─────────────────────────

/**
 * ¿Hay pestañas ocultas a un lado? (puro). Devuelve {izq, der, valor: 'ninguno'|'izq'|'der'|'ambos'}. `izq`: hay contenido oculto a la izquierda
 * (ya se desplazó); `der`: lo hay a la derecha. Sin ancho medido o sin desbordamiento → ninguno. `tolerancia` en px (subpíxeles).
 */
export function estadoDesborde(scrollLeft, clientWidth, scrollWidth, tolerancia = 2) {
  const max = Number(scrollWidth) - Number(clientWidth);
  if (!(clientWidth > 0) || !(max > tolerancia)) return { izq: false, der: false, valor: 'ninguno' };
  const pos = Math.max(0, Number(scrollLeft) || 0);
  const izq = pos > tolerancia;
  const der = pos < max - tolerancia;
  return { izq, der, valor: izq && der ? 'ambos' : izq ? 'izq' : der ? 'der' : 'ninguno' };
}

/**
 * Marca `data-desborde` («ninguno|izq|der|ambos») en una lista de pestañas con scroll horizontal; el CSS pinta un degradado en el borde que oculta
 * pestañas (así se ve que hay más). Se actualiza al desplazar y al cambiar de tamaño (ResizeObserver; sin él, con `resize` y dos comprobaciones diferidas).
 * Devuelve la función `actualizar()`.
 */
export function vigilarDesborde(nodo) {
  const actualizar = () => {
    const e = estadoDesborde(nodo.scrollLeft, nodo.clientWidth, nodo.scrollWidth);
    if (nodo.dataset.desborde !== e.valor) nodo.dataset.desborde = e.valor;
    return e;
  };
  nodo.dataset.desborde = 'ninguno';
  nodo.addEventListener('scroll', actualizar);
  if (typeof globalThis.ResizeObserver === 'function') new globalThis.ResizeObserver(actualizar).observe(nodo);
  else {
    if (typeof globalThis.addEventListener === 'function') globalThis.addEventListener('resize', actualizar);
    setTimeout(actualizar, 50); setTimeout(actualizar, 400);
  }
  return actualizar;
}

/** Trae a la vista la pestaña elegida (por si estaba a medias en el borde de la lista que se desplaza). */
function traerAVista(boton) {
  if (boton && typeof boton.scrollIntoView === 'function') { try { boton.scrollIntoView({ block: 'nearest', inline: 'nearest' }); } catch (_) { /* sin soporte */ } }
}

/**
 * Pestañas accesibles (flechas, Inicio, Fin). items: [{id, titulo, render() → Node|Promise<Node>}]. El panel se renderiza al abrirse
 * (una vez). Devuelve un Element con `.activar(id)`.
 */
export function tabs(items, activo) {
  const lista = (items || []).filter(Boolean);
  const base = nuevoId('tabs');
  const raiz = el('div', { class: 'tabs' });
  const barra = el('div', { class: 'tabs__lista', role: 'tablist' });
  vigilarDesborde(barra);
  const paneles = new Map();
  const botones = new Map();
  let actual = null;

  async function activar(id, { foco = false } = {}) {
    const item = lista.find((i) => i.id === id) || lista[0];
    if (!item) return;
    actual = item.id;
    for (const i of lista) {
      const sel = i.id === item.id;
      botones.get(i.id).setAttribute('aria-selected', sel ? 'true' : 'false');
      botones.get(i.id).setAttribute('tabindex', sel ? '0' : '-1');
      paneles.get(i.id).hidden = !sel;
    }
    if (foco) botones.get(item.id).focus();
    const panel = paneles.get(item.id);
    if (!panel.dataset.listo) {
      panel.dataset.listo = '1';
      panel.appendChild(cargando());
      try {
        const nodo = await item.render();
        limpiar(panel);
        if (nodo) agregarHijos(panel, [nodo]);
      } catch (err) { limpiar(panel); panel.appendChild(errorBox(err)); }
    }
  }

  lista.forEach((item, idx) => {
    const b = el('button', {
      type: 'button', role: 'tab', id: `${base}-t-${item.id}`, class: 'tabs__tab', 'aria-controls': `${base}-p-${item.id}`, 'aria-selected': 'false', tabindex: '-1',
      onclick: () => { activar(item.id); traerAVista(botones.get(item.id)); },
      onkeydown: (ev) => {
        const n = lista.length; let j = null;
        if (ev.key === 'ArrowRight') j = (idx + 1) % n; else if (ev.key === 'ArrowLeft') j = (idx - 1 + n) % n;
        else if (ev.key === 'Home') j = 0; else if (ev.key === 'End') j = n - 1;
        if (j !== null) { ev.preventDefault(); activar(lista[j].id, { foco: true }); }
      },
    }, item.titulo);
    botones.set(item.id, b);
    barra.appendChild(b);
    const p = el('div', { class: 'tabs__panel', role: 'tabpanel', id: `${base}-p-${item.id}`, 'aria-labelledby': `${base}-t-${item.id}`, tabindex: '0', hidden: true });
    paneles.set(item.id, p);
  });
  raiz.appendChild(barra);
  for (const p of paneles.values()) raiz.appendChild(p);
  raiz.activar = activar;
  raiz.activo = () => actual;
  if (lista.length) activar(activo || lista[0].id);
  return raiz;
}

// ───────────────────────── visores ─────────────────────────

const MAX_HIJOS_JSON = 100;
const MAX_PROFUNDIDAD_JSON = 14;
const MAX_TEXTO_JSON = 600;

/** Resumen de un valor JSON compuesto: «{…} 5 claves» / «[…] 12 elementos». */
export function resumenJson(v) {
  if (Array.isArray(v)) return `[…] ${v.length} ${v.length === 1 ? 'elemento' : 'elementos'}`;
  if (v && typeof v === 'object') { const n = Object.keys(v).length; return `{…} ${n} ${n === 1 ? 'clave' : 'claves'}`; }
  return '';
}

function hojaJson(v) {
  if (v === null) return el('span', { class: 'json-nulo' }, 'null');
  if (typeof v === 'string') {
    const largo = v.length > MAX_TEXTO_JSON;
    const s = neutralizarTexto(largo ? v.slice(0, MAX_TEXTO_JSON) : v);
    return el('span', { class: 'json-cad', title: largo ? `${v.length} caracteres (recortado)` : null }, `"${s}"`, largo ? el('span', { class: 'texto-tenue' }, `… (+${v.length - MAX_TEXTO_JSON})`) : null);
  }
  if (typeof v === 'number') return el('span', { class: 'json-num' }, String(v));
  if (typeof v === 'boolean') return el('span', { class: 'json-bool' }, String(v));
  return el('span', { class: 'json-nulo' }, String(v));
}

function nodoJson(clave, v, nivel, abrirHasta, vistos) {
  const etiqueta = clave === null ? null : el('span', { class: 'json-clave' }, String(clave), el('span', { class: 'json-sep' }, ': '));
  const compuesto = v !== null && typeof v === 'object';
  if (!compuesto) return el('div', { class: 'json-fila' }, etiqueta, hojaJson(v));
  if (vistos.has(v)) return el('div', { class: 'json-fila' }, etiqueta, el('span', { class: 'json-nulo' }, '[circular]'));
  if (nivel >= MAX_PROFUNDIDAD_JSON) return el('div', { class: 'json-fila' }, etiqueta, el('span', { class: 'json-nulo' }, resumenJson(v)));
  vistos.add(v);
  const entradas = Array.isArray(v) ? v.map((x, i) => [i, x]) : Object.entries(v);
  const det = el('details', { class: 'json-nodo' });
  if (nivel < abrirHasta) det.open = true, det.setAttribute('open', '');
  det.appendChild(el('summary', null, etiqueta, el('span', { class: 'json-resumen' }, resumenJson(v))));
  const hijos = el('div', { class: 'json-hijos' });
  let mostrados = 0;
  const botonMas = el('button', { type: 'button', class: 'btn btn--chico json-mas' });
  const pintarMas = () => {
    const fin = Math.min(mostrados + MAX_HIJOS_JSON, entradas.length);
    for (; mostrados < fin; mostrados += 1) hijos.insertBefore(nodoJson(entradas[mostrados][0], entradas[mostrados][1], nivel + 1, abrirHasta, vistos), botonMas);
    if (mostrados >= entradas.length) botonMas.remove(); else botonMas.textContent = `… mostrar ${Math.min(MAX_HIJOS_JSON, entradas.length - mostrados)} más (${entradas.length - mostrados} restantes)`;
  };
  botonMas.addEventListener('click', pintarMas);
  hijos.appendChild(botonMas);
  // render diferido: los hijos se crean al abrir (árboles grandes no cuestan nada colapsados)
  const montar = () => { if (!det.dataset.montado) { det.dataset.montado = '1'; pintarMas(); } };
  if (det.open) montar(); else det.addEventListener('toggle', () => { if (det.open) montar(); });
  det.appendChild(hijos);
  vistos.delete(v);
  return det;
}

/** Visor JSON colapsable (`<details>`), recorta cadenas largas y listas enormes. colapsado:true → solo la raíz abierta. */
export function visorJson(obj, { colapsado = true, titulo = 'Datos en bruto' } = {}) {
  let texto = '';
  try { texto = JSON.stringify(obj, null, 2); } catch (_) { texto = String(obj); }
  const raiz = el('div', { class: 'visor-json' });
  const arbol = el('div', { class: 'visor-json__arbol', role: 'tree', 'aria-label': titulo });
  const pintar = (hasta) => { limpiar(arbol); arbol.appendChild(nodoJson(null, obj, 0, hasta, new WeakSet())); };
  pintar(colapsado ? 1 : 3);
  const barra = el('div', { class: 'visor-barra' },
    el('button', { type: 'button', class: 'btn btn--chico', onclick: () => pintar(MAX_PROFUNDIDAD_JSON) }, 'Abrir todo'),
    el('button', { type: 'button', class: 'btn btn--chico', onclick: () => pintar(0) }, 'Cerrar todo'),
    el('button', { type: 'button', class: 'btn btn--chico', onclick: () => copiar(texto ?? '') }, icono('copiar', { tam: 13 }), 'Copiar datos'),
    el('span', { class: 'texto-tenue' }, texto ? fmt.bytes(texto.length) : ''));
  raiz.appendChild(barra);
  raiz.appendChild(arbol);
  return raiz;
}

/** Visor de texto plano (md, yaml, json, texto…): SIEMPRE `<pre>` con textContent; nunca interpreta Markdown ni HTML. */
export function visorTexto(texto, { tipo = 'texto', maxChars = 200000 } = {}) {
  let t = texto === null || texto === undefined ? '' : String(texto);
  if (tipo === 'json') { try { t = JSON.stringify(JSON.parse(t), null, 2); } catch (_) { /* se muestra como llegó */ } }
  const recortado = t.length > maxChars;
  const visible = recortado ? t.slice(0, maxChars) : t;
  return el('div', { class: 'visor-texto' },
    el('div', { class: 'visor-barra' },
      chip(tipo, 'neutro'),
      el('span', { class: 'texto-tenue' }, `${fmt.num(visible.length)} caracteres${recortado ? ` de ${fmt.num(t.length)} (recortado)` : ''}`),
      el('button', { type: 'button', class: 'btn btn--chico', onclick: () => copiar(t) }, icono('copiar', { tam: 13 }), 'Copiar')),
    el('pre', { class: 'visor-texto__pre', tabindex: '0' }, el('code', null, visible)));
}

// ───────────────────────── rediseño: rutas y contexto de navegación ─────────────────────────

/** 'ofertas' → '#/ofertas' · '/ofertas' → '#/ofertas' · '#/x' queda igual · vacío → '#/resumen'. */
export function hrefDeRuta(ruta) {
  const r = String(ruta ?? '').trim();
  if (!r) return '#/resumen';
  if (r.startsWith('#')) return r;
  return r.startsWith('/') ? `#${r}` : `#/${r}`;
}

let contextoMigas = null;
/** El shell (app.js) fija aquí las migas de la pantalla actual; `encabezadoPagina` las usa si la página no pasa `migas`. */
export function fijarContexto({ migas } = {}) { contextoMigas = Array.isArray(migas) ? migas : null; }

// ───────────────────────── rediseño: preferencias globales (modo técnico y densidad) ─────────────────────────

/** Refleja `modoTecnico` y `densidad` en <html data-tecnico data-densidad> y abre/cierra todos los bloques que siguen al modo técnico. Devuelve cuántos cambió. */
export function sincronizarModoTecnico(est = estado) {
  const d = typeof globalThis.document === 'undefined' ? null : globalThis.document;
  if (!d) return 0;
  const raiz = d.documentElement;
  if (raiz && raiz.dataset) { raiz.dataset.tecnico = String(Boolean(est.modoTecnico)); raiz.dataset.densidad = est.densidad; }
  let n = 0;
  for (const det of d.querySelectorAll('details[data-sigue-modo]')) {
    const abrir = Boolean(est.modoTecnico) || (det.dataset && det.dataset.fijo === '1');
    if (det.open !== abrir) {
      det.open = abrir;
      n += 1;
      if (abrir && typeof det.montar === 'function') det.montar();
    }
  }
  return n;
}

let preferenciasInstaladas = false;
/** Engancha el estado global al DOM (una sola vez): cada cambio de modoTecnico/densidad se refleja en <html> y en los bloques técnicos. */
export function instalarPreferencias(est = estado) {
  if (preferenciasInstaladas) return false;
  preferenciasInstaladas = true;
  est.suscribir((_e, cambios) => { if (cambios.includes('modoTecnico') || cambios.includes('densidad')) sincronizarModoTecnico(est); });
  sincronizarModoTecnico(est);
  return true;
}

/** Contenido que solo se ve con el modo técnico encendido (rutas, ids internos…). Para bloques plegables usa `detalleTecnico`. */
export function soloTecnico(...hijos) {
  return el('span', { class: 'solo-tecnico' }, ...hijos);
}

/**
 * Bloque plegable de detalle técnico (rutas de archivo, hashes, ids, comandos, JSON crudo). Cerrado por defecto; con el modo técnico global
 * encendido se abre (y se cierra al apagarlo). `abierto: true` lo deja siempre abierto. `contenido` puede ser un Element, una lista o una función
 * que lo construye al abrir por primera vez (árboles grandes no cuestan nada cerrados).
 */
export function detalleTecnico(titulo, contenido, { abierto = false, clase } = {}) {
  const fijo = abierto === true;
  const det = el('details', { class: ['detalle-tecnico', clase], 'data-sigue-modo': '1', dataset: { fijo: fijo ? '1' : '0' } });
  const cuerpo = el('div', { class: 'detalle-tecnico__cuerpo' });
  let montado = false;
  det.montar = () => {
    if (montado) return;
    montado = true;
    agregarHijos(cuerpo, [typeof contenido === 'function' ? contenido() : contenido]);
  };
  det.addEventListener('toggle', () => { if (det.open) det.montar(); });
  det.appendChild(el('summary', { class: 'detalle-tecnico__cab' },
    icono('chevron-derecha', { tam: 14, clase: 'detalle-tecnico__chev' }),
    el('span', { class: 'detalle-tecnico__titulo' }, titulo),
    el('span', { class: 'detalle-tecnico__marca' }, 'técnico')));
  det.appendChild(cuerpo);
  if (fijo || estado.modoTecnico) { det.open = true; det.montar(); }
  return det;
}

// ───────────────────────── rediseño: popovers, términos y ayuda ─────────────────────────

let contadorPop = 0;
let popNodo = null; // <div class="popover"> compartido por todos
let popActivo = null; // instancia abierta

function nodoPopover() {
  const d = doc();
  if (!popNodo) {
    popNodo = el('div', { class: 'popover', hidden: true, tabindex: '-1' });
    popNodo.addEventListener('mouseenter', () => { if (popActivo) popActivo.evento('entra'); });
    popNodo.addEventListener('mouseleave', () => { if (popActivo) popActivo.evento('sale'); });
  }
  if (!popNodo.isConnected) d.body.appendChild(popNodo);
  return popNodo;
}

/**
 * Popover accesible anclado a `ancla`: se abre con hover/foco (tras `retardo` ms), se fija con clic/Enter (segundo clic o Esc lo cierra; un clic fuera también)
 * y se coloca solo dentro de la ventana (flip arriba/abajo). `contenido`: Node o función que lo construye al abrir. `rol`: 'tooltip' (definiciones) o 'dialog' (interactivo).
 * Devuelve {abrir, cerrar, alternar, abierto}. Un único popover abierto a la vez.
 */
export function popover(ancla, contenido, { rol = 'tooltip', etiqueta, retardo = 140, retardoCierre = 120, preferido = 'abajo' } = {}) {
  const id = `popover-${++contadorPop}`;
  let est = { abierto: false, fijo: false };
  let tAbrir = null; let tCerrar = null;
  const parar = (t) => { if (t !== null) clearTimeout(t); return null; };
  const d = () => doc();

  const alTecla = (ev) => { if (cierraConTecla(ev.key)) evento('esc'); };
  const alRaton = (ev) => {
    const nodo = popNodo;
    const dentro = (nodo && nodo.contains && nodo.contains(ev.target)) || (ancla.contains && ancla.contains(ev.target));
    if (!dentro) evento('fuera');
  };

  function ubicar() {
    const nodo = nodoPopover();
    const ra = typeof ancla.getBoundingClientRect === 'function' ? ancla.getBoundingClientRect() : { left: 0, top: 0, width: 0, height: 0 };
    const rp = typeof nodo.getBoundingClientRect === 'function' ? nodo.getBoundingClientRect() : { width: 0, height: 0 };
    const vista = { width: globalThis.innerWidth || 1024, height: globalThis.innerHeight || 768 };
    const pos = posicionarPopover(ra, rp, vista, { preferido });
    nodo.style.setProperty('left', `${pos.left}px`);
    nodo.style.setProperty('top', `${pos.top}px`);
    nodo.style.setProperty('--flecha', `${pos.flecha}px`);
    nodo.dataset.lado = pos.lado;
  }

  function mostrar() {
    if (popActivo && popActivo !== inst) popActivo.cerrarYa();
    const nodo = nodoPopover();
    nodo.setAttribute('id', id);
    nodo.setAttribute('role', rol);
    if (etiqueta) nodo.setAttribute('aria-label', etiqueta); else nodo.removeAttribute('aria-label');
    reemplazar(nodo, typeof contenido === 'function' ? contenido() : contenido, el('span', { class: 'popover__flecha', 'aria-hidden': 'true' }));
    nodo.hidden = false;
    popActivo = inst;
    if (rol === 'dialog') { ancla.setAttribute('aria-haspopup', 'dialog'); ancla.setAttribute('aria-expanded', 'true'); ancla.setAttribute('aria-controls', id); }
    else ancla.setAttribute('aria-describedby', id);
    d().addEventListener('keydown', alTecla);
    d().addEventListener('mousedown', alRaton);
    ubicar();
  }

  function ocultar() {
    if (popActivo === inst) {
      popActivo = null;
      d().removeEventListener('keydown', alTecla);
      d().removeEventListener('mousedown', alRaton);
      if (popNodo) popNodo.hidden = true;
    }
    if (rol === 'dialog') ancla.setAttribute('aria-expanded', 'false'); else ancla.removeAttribute('aria-describedby');
  }

  function evento(nombre) {
    const r = transicionPopover(est, nombre);
    est = { abierto: r.abierto, fijo: r.fijo };
    if (r.accion === 'abrir') { tCerrar = parar(tCerrar); mostrar(); }
    else if (r.accion === 'cerrar') { tCerrar = parar(tCerrar); ocultar(); if (nombre === 'esc' && typeof ancla.focus === 'function') ancla.focus(); }
    else if (r.accion === 'programar_cierre') {
      tCerrar = parar(tCerrar);
      tCerrar = setTimeout(() => { tCerrar = null; if (!est.fijo) inst.cerrarYa(); }, retardoCierre);
    } else if (r.accion === 'cancelar_cierre') tCerrar = parar(tCerrar);
  }

  const inst = {
    id,
    evento,
    cerrarYa() { tAbrir = parar(tAbrir); tCerrar = parar(tCerrar); est = { abierto: false, fijo: false }; ocultar(); },
  };

  ancla.addEventListener('mouseenter', () => {
    tCerrar = parar(tCerrar);
    if (est.abierto) return;
    if (retardo <= 0) { evento('entra'); return; }
    tAbrir = parar(tAbrir);
    tAbrir = setTimeout(() => { tAbrir = null; evento('entra'); }, retardo);
  });
  ancla.addEventListener('mouseleave', () => { tAbrir = parar(tAbrir); evento('sale'); });
  ancla.addEventListener('focus', () => { tAbrir = parar(tAbrir); evento('entra'); });
  ancla.addEventListener('blur', () => { tAbrir = parar(tAbrir); evento('sale'); });
  ancla.addEventListener('click', () => { tAbrir = parar(tAbrir); evento('clic'); });

  return {
    abrir() { if (!est.abierto) evento('clic'); },
    cerrar() { inst.cerrarYa(); },
    alternar() { evento('clic'); },
    abierto: () => est.abierto,
    fijo: () => est.fijo,
  };
}

function contenidoTermino(clave) {
  const def = buscarTermino(clave);
  if (!def) {
    return el('div', { class: 'pop-termino' },
      el('p', { class: 'pop-termino__corto' }, 'Todavía no hay una explicación para este término.'),
      el('p', { class: 'pop-termino__tecnico' }, el('code', null, clave)));
  }
  return el('div', { class: 'pop-termino' },
    def.nombre ? el('strong', { class: 'pop-termino__nombre' }, def.nombre) : null,
    el('p', { class: 'pop-termino__corto' }, def.corto),
    def.largo ? el('p', { class: 'pop-termino__largo' }, def.largo) : null,
    def.tecnico ? el('p', { class: 'pop-termino__tecnico' }, el('span', null, 'Nombre técnico: '), el('code', null, def.tecnico)) : null);
}

/**
 * Término del glosario: muestra el nombre humano (o `texto`) con subrayado punteado y, al pasar el cursor o enfocarlo, la definición.
 * Con el modo técnico encendido añade el nombre técnico entre paréntesis. `clave` desconocida → el texto se ve igual y el popover lo dice.
 */
export function termino(clave, { texto, sinTecnico = false } = {}) {
  const def = buscarTermino(clave);
  const visible = texto ?? (def && def.nombre) ?? humanizarClave(clave);
  const span = el('span', { class: ['termino', !def && 'termino--sin-definicion'], tabindex: '0', 'data-termino': clave },
    visible,
    def && def.tecnico && !sinTecnico && def.tecnico !== visible ? el('span', { class: 'termino__tecnico solo-tecnico' }, ` (${def.tecnico})`) : null);
  popover(span, () => contenidoTermino(clave), { rol: 'tooltip' });
  return span;
}

/**
 * Resuelve el valor de `ayuda` (puro): {tipo:'glosario', clave} | {tipo:'texto', texto, titulo?, largo?} | null.
 *  · objeto `{texto, titulo?, largo?}` → texto directo; `{clave}` → glosario.
 *  · string que es clave del glosario → glosario. String con aspecto de clave (snake_case, sin espacios) que aún no existe → glosario (el popover avisa
 *    de que falta la definición: así un error de tecleo se nota). Cualquier otro string (con espacios, mayúsculas o puntuación) → texto directo.
 */
export function resolverAyuda(valor, glosario = undefined) {
  const hay = (k) => (glosario === undefined ? buscarTermino(k) : buscarTermino(k, glosario));
  if (valor && typeof valor === 'object' && !esNodo(valor)) {
    const texto = typeof valor.texto === 'string' ? valor.texto.trim() : '';
    if (texto) return { tipo: 'texto', texto, titulo: typeof valor.titulo === 'string' ? valor.titulo : undefined, largo: typeof valor.largo === 'string' ? valor.largo : undefined };
    if (typeof valor.clave === 'string' && valor.clave) return { tipo: 'glosario', clave: valor.clave };
    return null;
  }
  if (typeof valor !== 'string' || !valor.trim()) return null;
  if (hay(valor) || /^[a-z][a-z0-9_]*$/.test(valor)) return { tipo: 'glosario', clave: valor };
  return { tipo: 'texto', texto: valor.trim() };
}

function contenidoTexto(def) {
  return el('div', { class: 'pop-termino' },
    def.titulo ? el('strong', { class: 'pop-termino__nombre' }, def.titulo) : null,
    el('p', { class: 'pop-termino__corto' }, def.texto),
    def.largo ? el('p', { class: 'pop-termino__largo' }, def.largo) : null);
}

/**
 * Botón «?» con ayuda en popover. `valor`: clave del glosario (como siempre) o texto corto directo (`'Cuánto…'`) u objeto `{texto, titulo?, largo?}`
 * — ver `resolverAyuda`. `titulo` pone el nombre en el aria-label («Qué es: …») cuando la ayuda es un texto directo. Devuelve null si `valor` está vacío.
 */
export function ayuda(valor, { etiqueta, titulo } = {}) {
  const r = resolverAyuda(valor);
  if (!r) return null;
  if (r.tipo === 'texto') {
    const nombre = r.titulo || titulo;
    const b = el('button', { type: 'button', class: ['ayuda-btn', 'ayuda-btn--texto'], 'aria-label': etiqueta || (nombre ? `Qué es: ${nombre}` : 'Más información') }, icono('ayuda', { tam: 14 }));
    popover(b, () => contenidoTexto(r), { rol: 'tooltip' });
    return b;
  }
  const def = buscarTermino(r.clave);
  const nombre = (def && def.nombre) || humanizarClave(r.clave);
  const b = el('button', { type: 'button', class: 'ayuda-btn', 'aria-label': etiqueta || `Qué es: ${nombre}`, 'data-termino': r.clave }, icono('ayuda', { tam: 14 }));
  popover(b, () => contenidoTermino(r.clave), { rol: 'tooltip' });
  return b;
}
function ayudaTermino(valor, opciones) { return ayuda(valor, opciones); }

/**
 * Icono «i» con popover: «Leído de …» + hora relativa (y absoluta). `rutas`: string[]; `leido`: ISO. Sustituye a las líneas «Fuente: ruta · leído …».
 * Las rutas son datos técnicos: aquí viven en el popover (o en línea con el modo técnico, vía `fuenteInfo`).
 */
export function fuente(rutas, { leido, ahora } = {}) {
  const lista = (Array.isArray(rutas) ? rutas : (rutas ? [rutas] : [])).filter((x) => typeof x === 'string' && x);
  const boton = el('button', { type: 'button', class: 'fuente-btn', 'aria-label': 'Origen de los datos' }, icono('info', { tam: 14 }));
  popover(boton, () => el('div', { class: 'pop-fuente' },
    el('strong', { class: 'pop-fuente__titulo' }, 'Origen de los datos'),
    lista.length ? el('ul', { class: 'pop-fuente__lista' }, lista.map((r) => el('li', null, el('code', null, r)))) : el('p', { class: 'texto-tenue' }, 'No se indicó de dónde salen estos datos.'),
    leido ? el('p', { class: 'pop-fuente__hora' }, `Leído ${fmt.relativo(leido, ahora ?? Date.now())}`, el('span', { class: 'texto-tenue' }, ` · ${fmt.fecha(leido, { segundos: true })}`)) : null,
    lista.length ? el('button', { type: 'button', class: 'btn btn--chico', onclick: () => copiar(lista.join('\n')) }, icono('copiar', { tam: 13 }), 'Copiar los nombres de archivo') : null),
  { rol: 'dialog', etiqueta: 'Origen de los datos' });
  return el('span', { class: 'fuente' }, boton);
}

// ───────────────────────── rediseño: métrica, atención, cabecera ─────────────────────────

const ETIQUETA_TONO = { ok: 'En orden', aviso: 'Atención', grave: 'Grave', error: 'Error', critico: 'Crítico', info: 'Informativo', acento: 'Espera tu acción', neutro: '' };

function chipTendencia(t) {
  const sentido = ['sube', 'baja', 'igual'].includes(t && t.sentido) ? t.sentido : 'igual';
  const tono = t.bueno === true ? 'ok' : t.bueno === false ? 'error' : 'neutro';
  return el('span', { class: ['tendencia', `tendencia--${tono}`] },
    icono(`tendencia-${sentido}`, { tam: 13 }),
    el('span', { class: 'tendencia__valor' }, t.valor),
    el('span', { class: 'solo-lectores' }, ` (${{ sube: 'sube', baja: 'baja', igual: 'sin cambios' }[sentido]}${tono === 'ok' ? ', favorable' : tono === 'error' ? ', desfavorable' : ''})`));
}

/**
 * Métrica: número grande + etiqueta humana + contexto (+ tendencia, mini-serie y ayuda: clave del glosario O texto corto directo, `ayuda: 'Cuánto…'` /
 * `ayuda: {texto, titulo?}`, sin crear una clave por métrica; ver `resolverAyuda`). `tono` (ok|aviso|grave|critico|info|acento)
 * añade icono de estado; `ruta` convierte toda la tarjeta en un enlace. `valor` null → «—» (nunca un cero inventado). Sustituye a `tarjeta`.
 */
export function metrica({ etiqueta, valor, contexto, tono, tendencia, serie, ayuda: valorAyuda, ruta } = {}) {
  const t = tono ? normalizarTono(tono, null) : null;
  const sinValor = valor === null || valor === undefined || valor === '';
  const textoValor = typeof valor === 'number' ? fmt.numero(valor, { decimales: Number.isInteger(valor) ? 0 : 2 }) : valor;
  const largo = typeof valor === 'string' && valor.length > 12;
  const muyLargo = typeof valor === 'string' && valor.length > 28;
  const hayEstado = t && t !== 'neutro';
  const hayTendencia = tendencia && typeof tendencia === 'object' && !Array.isArray(tendencia) && tendencia.valor !== undefined;
  const hayContexto = contexto !== undefined && contexto !== null && contexto !== '';
  return el(ruta ? 'a' : 'article', {
    class: ['metrica', hayEstado && `metrica--${t}`, sinValor && 'metrica--sin-valor', largo && 'metrica--valor-largo', muyLargo && 'metrica--valor-muy-largo', ruta && 'metrica--enlace'],
    href: ruta ? hrefDeRuta(ruta) : null,
  },
  el('div', { class: 'metrica__cab' },
    el('h3', { class: 'metrica__etiqueta' }, etiqueta),
    valorAyuda ? ayudaTermino(valorAyuda, { titulo: etiqueta }) : null,
    hayEstado ? el('span', { class: ['metrica__estado', `metrica__estado--${t}`], role: 'img', 'aria-label': ETIQUETA_TONO[t] || t, title: ETIQUETA_TONO[t] || t }, icono(iconoDeTono(t) || 'info', { tam: 16 })) : null),
  el('div', { class: 'metrica__valor' }, sinValor ? '—' : textoValor),
  hayTendencia || hayContexto ? el('div', { class: 'metrica__pie' }, hayTendencia ? chipTendencia(tendencia) : null, hayContexto ? el('span', { class: 'metrica__contexto' }, contexto) : null) : null,
  Array.isArray(serie) && puntosSparkline(serie) ? el('div', { class: 'metrica__serie' }, sparkline(serie, { ancho: 96, alto: 28, etiqueta: `Tendencia de ${etiqueta}` })) : null);
}

const TONO_ATENCION = { critico: 'critico', error: 'critico', grave: 'grave', aviso: 'aviso', warning: 'aviso', info: 'info', ok: 'info' };
const ORDEN_ATENCION = { critico: 0, grave: 1, aviso: 2, info: 3 };
const ICONO_ATENCION = { critico: 'octogono', grave: 'rombo-alerta', aviso: 'alerta', info: 'info' };
const ROTULO_ATENCION = { critico: 'Crítico', grave: 'Grave', aviso: 'Aviso', info: 'Información' };

/** Normaliza y ordena los avisos: crítico → grave → aviso → información; estable dentro de cada tono. No muta la entrada. */
export function ordenarAtencion(items) {
  return (Array.isArray(items) ? items : [])
    .filter((x) => x && typeof x === 'object')
    .map((x, i) => ({ ...x, tono: TONO_ATENCION[x.tono] || 'info', _i: i }))
    .sort((a, b) => ORDEN_ATENCION[a.tono] - ORDEN_ATENCION[b.tono] || a._i - b._i)
    .map(({ _i, ...resto }) => resto);
}

function botonAccion(accion) {
  if (!accion || !accion.texto) return null;
  if (accion.ruta) return el('a', { class: 'btn btn--chico atencion__boton', href: hrefDeRuta(accion.ruta), onclick: typeof accion.onClick === 'function' ? accion.onClick : null }, accion.texto, icono('flecha-derecha', { tam: 13 }));
  return el('button', { type: 'button', class: 'btn btn--chico atencion__boton', onclick: typeof accion.onClick === 'function' ? accion.onClick : () => {} }, accion.texto, icono('flecha-derecha', { tam: 13 }));
}

/**
 * Panel «Requiere tu atención»: lista priorizada (crítico → grave → aviso → información) con icono de forma distinta por gravedad,
 * frase humana y UN botón de acción por aviso. Sin avisos muestra `vacio` («Todo en orden…»). Devuelve un <section> con `.cantidad`.
 */
export function atencion({ items = [], vacio: textoVacio = 'Todo en orden: nada espera tu decisión ahora.', titulo = 'Requiere tu atención' } = {}) {
  const lista = ordenarAtencion(items);
  const hid = nuevoId('atencion');
  const raiz = el('section', { class: ['atencion', lista.length === 0 && 'atencion--vacia', lista[0] && `atencion--${lista[0].tono}`], 'aria-labelledby': hid },
    el('header', { class: 'atencion__cab' },
      el('h2', { id: hid, class: 'atencion__titulo' }, titulo),
      lista.length ? el('span', { class: 'atencion__cuenta' }, fmt.num(lista.length)) : null),
    lista.length
      ? el('ul', { class: 'atencion__lista' }, lista.map((it) => el('li', { class: ['atencion__item', `atencion__item--${it.tono}`] },
        el('span', { class: 'atencion__icono', role: 'img', 'aria-label': ROTULO_ATENCION[it.tono], title: ROTULO_ATENCION[it.tono] }, icono(ICONO_ATENCION[it.tono], { tam: 18 })),
        el('div', { class: 'atencion__texto' },
          el('strong', { class: 'atencion__item-titulo' }, it.titulo),
          it.detalle ? el('p', { class: 'atencion__detalle' }, it.detalle) : null),
        botonAccion(it.accion))))
      : el('p', { class: 'atencion__vacio' }, icono('ok', { tam: 18 }), el('span', null, textoVacio)));
  raiz.cantidad = lista.length;
  return raiz;
}

const normMiga = (t) => String(t ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').trim().toLowerCase();

/**
 * Migas sin repeticiones (puro): quita las consecutivas con el mismo texto («Sistema › Sistema» → «Sistema», conservando la que lleva enlace) y,
 * si solo queda una y es el propio título de la pantalla, ninguna (no aporta ubicación).
 */
export function limpiarMigas(migas, titulo) {
  const salida = [];
  for (const m of Array.isArray(migas) ? migas : []) {
    if (!m || m.texto === undefined || m.texto === null || m.texto === '') continue;
    const previa = salida[salida.length - 1];
    if (previa && normMiga(previa.texto) === normMiga(m.texto)) { if (m.ruta && !previa.ruta) salida[salida.length - 1] = m; continue; }
    salida.push(m);
  }
  if (salida.length === 1 && titulo !== undefined && normMiga(salida[0].texto) === normMiga(titulo)) return [];
  return salida;
}

/**
 * Cabecera de pantalla: migas + título humano + una frase de para qué sirve + acciones a la derecha + pestañas pegadas debajo.
 * `migas`: [{texto, ruta?}] (la última es la actual); omitida → las del shell (Grupo › Pantalla [› id]); `[]` → sin migas.
 */
export function encabezadoPagina({ titulo, descripcion, migas, acciones, pestanas, etiquetaMigas = 'Ubicación' } = {}) {
  const lista = limpiarMigas(Array.isArray(migas) ? migas : (contextoMigas || []), titulo);
  const hayAcciones = Array.isArray(acciones) ? acciones.filter(Boolean).length > 0 : Boolean(acciones);
  return el('header', { class: ['cab', pestanas && 'cab--con-pestanas'] },
    lista.length ? el('nav', { class: 'migas', 'aria-label': etiquetaMigas }, el('ol', { class: 'migas__lista' }, lista.map((m, i) => {
      const ultima = i === lista.length - 1;
      return el('li', { class: ['migas__item', ultima && 'migas__item--actual'] },
        m.ruta && !ultima ? el('a', { class: 'migas__enlace', href: hrefDeRuta(m.ruta) }, m.texto) : el('span', { 'aria-current': ultima ? 'page' : null }, m.texto),
        ultima ? null : icono('chevron-derecha', { tam: 12, clase: 'migas__sep' }));
    }))) : null,
    el('div', { class: 'cab__fila' },
      el('div', { class: 'cab__texto' },
        el('h1', { class: 'cab__titulo' }, titulo),
        descripcion ? el('p', { class: 'cab__desc' }, descripcion) : null),
      hayAcciones ? el('div', { class: 'cab__acciones' }, acciones) : null),
    pestanas ? el('div', { class: 'cab__pestanas' }, pestanas) : null);
}

// ───────────────────────── rediseño: pasos (pipeline), vacío con pasos, esqueletos ─────────────────────────

/** Normaliza las etapas de `pasos`: {id, nombre, codigo, estado, tono, etiqueta, icono, seleccionada, destacada, aviso}. `destacada`: espera al dueño (acento). */
export function modeloPasos(etapas) {
  return (Array.isArray(etapas) ? etapas : []).filter((e) => e && typeof e === 'object').map((e, i) => {
    const info = infoEstado(e.estado);
    return {
      id: String(e.id ?? i),
      nombre: String(e.nombre ?? e.id ?? `Paso ${i + 1}`),
      codigo: e.codigo ? String(e.codigo) : '',
      estado: e.estado ?? null,
      tono: info.tono,
      etiqueta: info.texto,
      icono: e.icono || iconoDeEstado(e.estado),
      seleccionada: Boolean(e.seleccionada),
      destacada: Boolean(e.destacada) || info.tono === 'acento',
      aviso: e.aviso ? String(e.aviso) : '',
    };
  });
}

/** Índice al que mueve el foco una tecla de navegación (sin dar la vuelta): flechas, Inicio, Fin. Otra tecla → `actual`. */
export function indiceFoco(actual, tecla, n) {
  if (!(n > 0)) return -1;
  switch (tecla) {
    case 'ArrowRight': case 'ArrowDown': return Math.min(actual + 1, n - 1);
    case 'ArrowLeft': case 'ArrowUp': return Math.max(actual - 1, 0);
    case 'Home': return 0;
    case 'End': return n - 1;
    default: return actual;
  }
}

/** ¿Cabe el stepper en su contenedor sin compactar? Compacta si cada etapa tendría menos de `minimo` px (puro; lo usa el ResizeObserver de `pasos`). */
export function debeCompactar(anchoContenedor, nEtapas, minimo = 96) {
  if (!(anchoContenedor > 0) || !(nEtapas > 0)) return false;
  return anchoContenedor / nEtapas < minimo;
}

/**
 * Stepper horizontal de etapas accesible por teclado (una sola parada de Tab; flechas, Inicio y Fin mueven el foco; Enter/Espacio eligen).
 * etapas: [{id, nombre, codigo?, estado, icono?, seleccionada?, aviso?}]. El estado es icono + etiqueta; la etapa que espera al dueño
 * (`estado: 'espera_firma'` o `destacada: true`) va resaltada con el acento. `onElegir(id, etapa)` opcional.
 * `compacto`: 'auto' (por defecto: se compacta solo si las etapas no caben en su contenedor, con ResizeObserver) · true (siempre: nodos de 28 px,
 * sin la línea de estado —sigue en el aria-label y en el title—) · false (nunca). Para ponerlo dentro de una tarjeta estrecha no hace falta CSS propio.
 */
export function pasos({ etapas = [], onElegir, etiqueta = 'Etapas', compacto = 'auto' } = {}) {
  const modelo = modeloPasos(etapas);
  const lista = el('ol', { class: 'stepper__lista' });
  const botones = [];
  const ini = Math.max(0, modelo.findIndex((m) => m.seleccionada));
  const enfocar = (j) => {
    botones.forEach((b, k) => b.setAttribute('tabindex', k === j ? '0' : '-1'));
    if (botones[j]) botones[j].focus();
  };
  modelo.forEach((m, i) => {
    const b = el('button', {
      type: 'button',
      class: ['stepper__paso', !onElegir && 'stepper__paso--lectura'],
      tabindex: i === ini ? '0' : '-1',
      'aria-current': m.seleccionada ? 'step' : null,
      'aria-label': `${m.nombre}${m.codigo ? ` (${m.codigo})` : ''}: ${m.etiqueta}${m.aviso ? `. ${m.aviso}` : ''}`,
      title: `${m.nombre}: ${m.etiqueta}${m.aviso ? `. ${m.aviso}` : ''}`,
      onclick: () => { if (typeof onElegir === 'function') onElegir(m.id, m); },
      onkeydown: (ev) => {
        const j = indiceFoco(i, ev.key, modelo.length);
        if (j !== i) { ev.preventDefault(); enfocar(j); }
      },
    },
    el('span', { class: 'stepper__nodo' }, icono(m.icono, { tam: 16 })),
    el('span', { class: 'stepper__nombre' }, m.nombre),
    el('span', { class: 'stepper__meta' }, m.codigo ? el('span', { class: 'stepper__codigo' }, m.codigo) : null, el('span', { class: 'stepper__estado' }, m.etiqueta)),
    m.aviso ? el('span', { class: 'stepper__aviso', 'aria-hidden': 'true' }, icono('alerta', { tam: 12 })) : null);
    botones.push(b);
    lista.appendChild(el('li', { class: ['stepper__item', `stepper__item--${m.tono}`, m.seleccionada && 'es-seleccionada', m.destacada && 'es-destacada', !m.codigo && 'stepper__item--sin-codigo'], 'data-estado': String(m.estado ?? '') }, b));
  });
  const nav = el('nav', { class: ['stepper', compacto === true && 'stepper--compacto'], 'aria-label': etiqueta, 'data-compacto': compacto === 'auto' ? 'auto' : String(Boolean(compacto)) }, lista);
  if (compacto === 'auto' && typeof globalThis.ResizeObserver === 'function') {
    const observador = new globalThis.ResizeObserver(() => {
      const ancho = nav.clientWidth || (nav.getBoundingClientRect && nav.getBoundingClientRect().width) || 0;
      nav.classList.toggle('stepper--compacto', debeCompactar(ancho, modelo.length));
    });
    observador.observe(nav);
  }
  return nav;
}

/** Ilustración sobria del estado vacío: formas geométricas con el icono pedido en el centro (SVG propio, sin clip-art). */
function ilustracionVacia(nombreIcono) {
  const svg = el('svg', { viewBox: '0 0 200 120', width: 200, height: 120, class: 'ilus', role: 'presentation', 'aria-hidden': 'true', focusable: 'false' },
    el('rect', { x: 14, y: 14, width: 172, height: 92, rx: 14, class: 'ilus__fondo' }),
    el('rect', { x: 14, y: 14, width: 172, height: 20, rx: 10, class: 'ilus__cabecera' }),
    el('circle', { cx: 28, cy: 24, r: 3, class: 'ilus__punto' }),
    el('circle', { cx: 39, cy: 24, r: 3, class: 'ilus__punto' }),
    el('circle', { cx: 62, cy: 70, r: 22, class: 'ilus__disco' }),
    el('rect', { x: 96, y: 55, width: 70, height: 8, rx: 4, class: 'ilus__barra' }),
    el('rect', { x: 96, y: 73, width: 48, height: 8, rx: 4, class: 'ilus__barra ilus__barra--corta' }),
    el('rect', { x: 150, y: 73, width: 16, height: 8, rx: 4, class: 'ilus__barra ilus__barra--acento' }));
  const g = el('g', { transform: 'translate(50 58)', class: 'ilus__icono', fill: 'none', stroke: 'currentColor', 'stroke-width': TRAZO, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' });
  for (const t of trazosSvg(nombreIcono || 'caja')) g.appendChild(t);
  svg.appendChild(g);
  return svg;
}

/**
 * Estado vacío con pasos: ilustración + qué falta + lista numerada de pasos; cada paso puede traer su `comando` (se muestra en el bloque
 * `comando`, abierto porque ES la acción de la pantalla). pasos: [{texto, comando?, nota?}].
 * Se adapta al ANCHO DE SU CONTENEDOR (container queries): en una columna estrecha apila la ilustración sobre el texto. `compacto: true` fuerza esa versión
 * (ilustración pequeña, menos aire) para tarjetas y paneles laterales.
 */
export function vacioConPasos({ titulo, explicacion, pasos: lista = [], icono: nombreIcono = 'caja', compacto = false } = {}) {
  const pasosValidos = (Array.isArray(lista) ? lista : []).filter((p) => p && (p.texto || p.comando));
  return el('div', { class: ['vacio-pasos', compacto && 'vacio-pasos--compacto'], role: 'status' },
    el('div', { class: 'vacio-pasos__rejilla' },
      el('div', { class: 'vacio-pasos__ilus' }, ilustracionVacia(nombreIcono)),
      el('div', { class: 'vacio-pasos__cuerpo' },
        el('h3', { class: 'vacio-pasos__titulo' }, titulo),
        explicacion ? el('p', { class: 'vacio-pasos__texto' }, explicacion) : null,
        pasosValidos.length
          ? el('ol', { class: 'pasos-lista' }, pasosValidos.map((p) => el('li', { class: 'pasos-lista__item' },
            el('div', { class: 'pasos-lista__contenido' },
              p.texto ? el('p', { class: 'pasos-lista__texto' }, p.texto) : null,
              p.comando ? comando(p.comando, { abierto: true, nota: p.nota }) : null))))
          : null)));
}

const BARRAS = (n, clase) => Array.from({ length: n }, () => el('i', { class: clase }));

/**
 * Esqueleto de carga (no un «Cargando…» pelado): 'tarjetas' (n tarjetas), 'tabla' (n filas), 'texto' (n líneas) o 'pagina' (cabecera + tarjetas + tabla).
 * Es decorativo para lectores de pantalla (aria-hidden) salvo un aviso «Cargando…» oculto visualmente; respeta prefers-reduced-motion.
 */
export function esqueleto(tipo = 'pagina', n) {
  const tarjetas = (k) => el('div', { class: 'esq__tarjetas' }, Array.from({ length: k }, () => el('div', { class: 'esq__tarjeta' }, el('i', { class: 'esq__barra esq__barra--s' }), el('i', { class: 'esq__barra esq__barra--xl' }), el('i', { class: 'esq__barra esq__barra--m' }))));
  const tabla = (k) => el('div', { class: 'esq__tabla' },
    el('div', { class: 'esq__fila esq__fila--cab' }, BARRAS(4, 'esq__barra')),
    Array.from({ length: k }, () => el('div', { class: 'esq__fila' }, BARRAS(4, 'esq__barra'))));
  const texto = (k) => el('div', { class: 'esq__texto' }, BARRAS(k, 'esq__barra'));
  let cuerpo;
  switch (tipo) {
    case 'tarjetas': cuerpo = tarjetas(n ?? 4); break;
    case 'tabla': cuerpo = tabla(n ?? 6); break;
    case 'texto': cuerpo = texto(n ?? 4); break;
    default: cuerpo = [
      el('div', { class: 'esq__cab' }, el('i', { class: 'esq__barra esq__barra--s' }), el('i', { class: 'esq__barra esq__barra--titulo' }), el('i', { class: 'esq__barra esq__barra--l' })),
      tarjetas(4),
      el('div', { class: 'esq__bloque' }, el('i', { class: 'esq__barra esq__barra--m' }), tabla(5)),
    ];
  }
  return el('div', { class: ['esq', `esq--${['tarjetas', 'tabla', 'texto'].includes(tipo) ? tipo : 'pagina'}`], role: 'status', 'aria-busy': 'true', 'aria-live': 'polite' },
    el('span', { class: 'solo-lectores' }, 'Cargando…'),
    el('div', { class: 'esq__marco', 'aria-hidden': 'true' }, cuerpo));
}

// ───────────────────────── rediseño: tiempo, interruptor, segmentado, kbd ─────────────────────────

/** `<time>` con la fecha relativa («hace 3 h») y la absoluta en el `title`. Fecha inválida → «—». */
export function tiempo(valor, { ahora = Date.now(), clase } = {}) {
  const d = aFecha(valor);
  if (!d) return el('span', { class: ['texto-tenue', clase] }, '—');
  return el('time', { class: ['tiempo', clase], datetime: d.toISOString(), title: fmt.fecha(valor, { segundos: true }) }, fmt.relativo(valor, ahora));
}

/** Interruptor accesible (role=switch). Devuelve el botón con `.fijar(bool)`; `onCambio(nuevo)` se llama al pulsarlo. */
export function interruptor({ etiqueta, activo = false, onCambio, titulo, clase } = {}) {
  const btn = el('button', { type: 'button', class: ['sw', clase], role: 'switch', 'aria-checked': String(Boolean(activo)), 'aria-label': etiqueta, title: titulo || null,
    onclick: () => { const nuevo = btn.getAttribute('aria-checked') !== 'true'; btn.setAttribute('aria-checked', String(nuevo)); if (typeof onCambio === 'function') onCambio(nuevo); } },
  el('span', { class: 'sw__pista', 'aria-hidden': 'true' }, el('span', { class: 'sw__bola' })),
  el('span', { class: 'sw__texto' }, etiqueta));
  btn.fijar = (v) => btn.setAttribute('aria-checked', String(Boolean(v)));
  return btn;
}

/** Control segmentado (radiogroup): opciones [{valor, etiqueta, icono?, titulo?}]. Flechas cambian de opción. Devuelve el grupo con `.fijar(valor)`. */
export function segmentado({ opciones = [], valor, onCambio, etiqueta = 'Opciones', clase } = {}) {
  const raiz = el('div', { class: ['segmentado', clase], role: 'radiogroup', 'aria-label': etiqueta });
  const botones = [];
  const pintar = (v) => botones.forEach((b, i) => { const sel = opciones[i].valor === v; b.setAttribute('aria-checked', String(sel)); b.setAttribute('tabindex', sel ? '0' : '-1'); });
  opciones.forEach((o, i) => {
    const elegir = (j) => { const op = opciones[j]; pintar(op.valor); botones[j].focus(); if (typeof onCambio === 'function') onCambio(op.valor); };
    const b = el('button', {
      type: 'button', role: 'radio', class: 'segmentado__op', 'aria-label': o.etiqueta, title: o.titulo || o.etiqueta,
      onclick: () => elegir(i),
      onkeydown: (ev) => {
        const n = opciones.length; let j = null;
        if (ev.key === 'ArrowRight' || ev.key === 'ArrowDown') j = (i + 1) % n; else if (ev.key === 'ArrowLeft' || ev.key === 'ArrowUp') j = (i - 1 + n) % n;
        if (j !== null) { ev.preventDefault(); elegir(j); }
      },
    }, o.icono ? icono(o.icono, { tam: 15 }) : null, o.etiqueta && !o.icono ? el('span', null, o.etiqueta) : null);
    botones.push(b);
    raiz.appendChild(b);
  });
  raiz.fijar = pintar;
  pintar(valor);
  return raiz;
}

/**
 * Barra de pestañas SIN paneles (para `encabezadoPagina({pestanas})`): la página decide qué mostrar en `onCambio(id)`.
 * items: [{id, titulo, icono?, contador?}]. Flechas, Inicio y Fin cambian de pestaña. Devuelve el tablist con `.fijar(id)`.
 */
export function barraPestanas({ items = [], activo, onCambio, etiqueta = 'Secciones' } = {}) {
  const lista = (Array.isArray(items) ? items : []).filter(Boolean);
  const raiz = el('div', { class: 'tabs__lista tabs__lista--barra', role: 'tablist', 'aria-label': etiqueta });
  vigilarDesborde(raiz);
  const botones = [];
  const marcar = (id) => botones.forEach((b, i) => { const sel = lista[i].id === id; b.setAttribute('aria-selected', String(sel)); b.setAttribute('tabindex', sel ? '0' : '-1'); });
  const elegir = (j) => { const it = lista[j]; marcar(it.id); botones[j].focus(); traerAVista(botones[j]); if (typeof onCambio === 'function') onCambio(it.id, it); };
  lista.forEach((it, i) => {
    const b = el('button', {
      type: 'button', role: 'tab', class: 'tabs__tab', 'aria-selected': 'false', tabindex: '-1',
      onclick: () => { marcar(it.id); traerAVista(botones[i]); if (typeof onCambio === 'function') onCambio(it.id, it); },
      onkeydown: (ev) => {
        const n = lista.length; let j = null;
        if (ev.key === 'ArrowRight') j = (i + 1) % n; else if (ev.key === 'ArrowLeft') j = (i - 1 + n) % n; else if (ev.key === 'Home') j = 0; else if (ev.key === 'End') j = n - 1;
        if (j !== null) { ev.preventDefault(); elegir(j); }
      },
    }, it.icono ? icono(it.icono, { tam: 15 }) : null, it.titulo, it.contador !== undefined && it.contador !== null ? el('span', { class: 'tabs__contador' }, String(it.contador)) : null);
    botones.push(b);
    raiz.appendChild(b);
  });
  raiz.fijar = marcar;
  marcar(activo !== undefined ? activo : (lista[0] && lista[0].id));
  return raiz;
}

/** Tecla de teclado (`<kbd>`): kbd('⌘', 'K'). */
export function kbd(...teclas) {
  return el('span', { class: 'kbd-grupo' }, teclas.map((t) => el('kbd', { class: 'kbd' }, t)));
}

// ───────────────────────── agrupado ─────────────────────────

export const ui = {
  el, limpiar, reemplazar, chip, estadoChip, infoEstado, tarjeta, seccion, tabla, tabs, visorJson, visorTexto, vacio, cargando, errorBox,
  copiar, toast, modal, cerrarModales, confirmar, fmt, icono, instalarEstilos, kv, comando, sparkline, barraApilada, enlace, encabezado, fuenteInfo,
  ordenarFilas, filtrarFilas, valorDe, neutralizarTexto, urlSegura, TONOS,
  // rediseño (U0)
  encabezadoPagina, atencion, metrica, detalleTecnico, soloTecnico, termino, ayuda, popover, fuente, pasos, vacioConPasos, esqueleto, estadoIcono,
  tiempo, interruptor, segmentado, barraPestanas, kbd, trazosSvg, normalizarTono, iconoDeTono, iconoDeEstado, hrefDeRuta, fijarContexto, instalarPreferencias, sincronizarModoTecnico,
  ordenarAtencion, modeloPasos, indiceFoco, debeCompactar, limpiarMigas, resolverAyuda, estadoDesborde, vigilarDesborde, NOMBRES_ICONOS,
};
export default ui;

// El estado global (modo técnico, densidad) se refleja en <html> desde que carga el módulo (solo en el navegador / con `document`).
if (typeof globalThis.document !== 'undefined') instalarPreferencias();
