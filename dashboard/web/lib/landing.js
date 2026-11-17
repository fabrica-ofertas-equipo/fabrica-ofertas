// lib/landing.js — lógica PURA (datos → modelo de vista) de la pantalla #/landing (D5: landing, checkout y tracking).
// Sin DOM ni red. Probada con tests/dashboard/test_web_landing.mjs.
//
// Fuentes (ofertas/<id>/…): 03-oferta/oferta.json · 05-landing/{checkout,assets,tracking,rutas,despliegue}.json · 05-landing/sitio/**
//   · qa/d5-v<n>.json y qa/x1-d5-v<n>.json (QA de D5 y dictamen de X1) · GET /oferta/<id> (etapa D5 y sus artefactos).
//
// REGLAS
//  - Dinero: enteros en unidad menor + moneda; jamás `float`. El HTML se compara por cadenas decimales convertidas con aritmética entera.
//  - El HTML de la landing es dato NO confiable: aquí solo se lee como TEXTO (regex), nunca se inserta en el DOM del panel;
//    la vista previa va en un iframe con sandbox (ver pages/landing.js).
//  - Lo que el panel deduce del HTML son INDICIOS (no sustituyen al QA ni a `landing.validar`); lo dice cada fila.
//  - Sin resultado de QA para un check → «sin resultado», nunca «ok».

import { neutralizar } from './descubrimiento.js';

/** Id de oferta del panel = nombre de su carpeta en ofertas/: «OF-AAAAMM-NN» o, para la demo, «_ejemplo» (igual que el servidor). */
export const RE_OFERTA_ID = /^(OF-\d{6}-\d{2}|_[a-z0-9][a-z0-9_-]{0,31})$/;
/** Id real de oferta (el de estado.json): el que entienden `engine.orq` y los CLI del motor. */
export const RE_OFERTA_REAL = /^OF-\d{6}-\d{2}$/;

/** Anchos de la vista previa (D5 §3.4: viewports 360×800, 390×844, 768×1024). null = ancho completo. */
export const ANCHOS_PREVIEW = Object.freeze([
  { id: 'movil', titulo: 'Móvil', ancho: 390, alto: 844 },
  { id: 'tablet', titulo: 'Tablet', ancho: 768, alto: 1024 },
  { id: 'escritorio', titulo: 'Escritorio', ancho: null, alto: 800 },
]);

// ───────────────────────── catálogo de comprobaciones C01–C17 (departamentos/06 §6.1) ─────────────────────────

export const CHECKS_C = Object.freeze([
  { id: 'C01', titulo: 'Sitio sin errores: enlaces y botón de compra responden bien (200), todo se carga por una conexión segura y no hay código ni enlaces de otros sitios', falla: 'MAYOR (BLOQ si CTA, legal o archivo interno)' },
  { id: 'C02', titulo: 'Coherencia: precio, moneda, impuestos, oferta extra al pagar, garantía, regalos extra y plazos iguales en la página de venta, la pantalla de pago, la oferta, el producto y el mercado', falla: 'BLOQ' },
  { id: 'C03', titulo: 'Control de promesas, urgencia y testimonios: sin contadores falsos, sin la palabra «EJEMPLO», sin la oferta extra premarcada y con botones de compra distintos entre sí', falla: 'BLOQ (ROJO) / MAYOR' },
  { id: 'C04', titulo: 'Velocidad en el celular (medida con Lighthouse, la herramienta de Google): tiempo de carga, estabilidad de la pantalla y peso de la página', falla: 'MAYOR' },
  { id: 'C05', titulo: 'Se ve bien en pantallas de 360, 390 y 768 px y dentro del navegador de Instagram y Facebook: sin desbordes, botón de compra arriba, y se puede comprar y descargar', falla: 'MAYOR (BLOQ si no se puede comprar o recibir)' },
  { id: 'C06', titulo: 'Enlace de anuncio simulado (con todos los marcadores): la compra guarda los datos completos y el código del anuncio', falla: 'BLOQ' },
  { id: 'C07', titulo: 'Aviso automático de Stripe (webhook): una firma inválida se rechaza (400); el mismo aviso dos veces entrega una sola vez; un pago no cobrado no entrega; se recupera si falla', falla: 'BLOQ' },
  { id: 'C08', titulo: 'Entrega: un solo email por compra, enlace de descarga con código que vence y tiene límite de usos, recibo neutro', falla: 'BLOQ' },
  { id: 'C09', titulo: 'Prueba de eventos de Meta: mismo identificador de evento en el navegador y en el servidor, sin duplicados, dominio verificado, buena calidad de coincidencia (EMQ) y sin datos personales', falla: 'BLOQ' },
  { id: 'C10', titulo: 'Nada se envía a Meta antes de que la persona acepte; casillas separadas y sin premarcar, con el texto versionado', falla: 'BLOQ' },
  { id: 'C11', titulo: 'Páginas legales completas para cada país, reembolso igual a la garantía, sin marcadores sin rellenar ({{}}) y desistimiento en dos pasos (/desistimiento)', falla: 'BLOQ' },
  { id: 'C12', titulo: 'Accesibilidad: sin fallas críticas (herramienta axe), foco visible, contraste suficiente (AA) en los colores nuevos y texto alternativo en las imágenes', falla: 'MAYOR' },
  { id: 'C13', titulo: 'Se puede volver atrás con un solo comando (rollback) y el precio anterior en Stripe sigue activo', falla: 'MAYOR' },
  { id: 'C14', titulo: 'Pantalla de pago segura: ignora los importes que mande el cliente y limita los intentos; un anuncio fuera del catálogo queda «desconocido»; sin claves expuestas; conexión segura (HTTPS/HSTS)', falla: 'BLOQ' },
  { id: 'C15', titulo: 'Riesgo por candidato: nivel dentro de lo permitido para cada país, aviso de alcance, y el mecanismo no promete resultados de salud ni de ingresos', falla: 'BLOQ' },
  { id: 'C16', titulo: 'Datos neutros: dirección, título, etiquetas para redes (og:*), texto alternativo, eventos y descriptor sin términos sensibles', falla: 'BLOQ' },
  { id: 'C17', titulo: 'Mismo sitio para todos (K03): la huella del texto visible es igual desde 3 países y 2 agentes, con y sin etiquetas del anuncio', falla: 'BLOQ' },
]);

/** Las siete legales obligatorias de D5 §3.3 y los eventos de la lista cerrada de §4.2. */
export const LEGALES = Object.freeze(['vendedor', 'terminos', 'privacidad', 'reembolsos', 'cookies', 'aviso', 'entrega']);
export const EVENTOS_CERRADOS = Object.freeze(['PageView', 'ViewContent', 'InitiateCheckout', 'Purchase']);

const RE_ID_C = /(?:^|[^A-Za-z0-9])C(0[1-9]|1[0-7])(?![0-9])/;

/** «C03», «D5-C03», «QA-C03-x» → 'C03'; null si no es un check C01–C17. */
export function idCheckC(checkId) {
  const m = RE_ID_C.exec(String(checkId ?? ''));
  return m ? `C${m[1]}` : null;
}

function lista(v) { return Array.isArray(v) ? v : []; }
function objeto(v) { return v && typeof v === 'object' && !Array.isArray(v) ? v : {}; }
function txt(v, max = 200) { return neutralizar(v, { max }); }
function esEntero(n) { return typeof n === 'number' && Number.isSafeInteger(n); }

// ───────────────────────── dinero (enteros, sin float) ─────────────────────────

const SIN_DECIMALES = new Set(['JPY', 'KRW', 'CLP', 'PYG', 'VND', 'ISK', 'UGX', 'XAF', 'XOF', 'RWF', 'KMF', 'GNF', 'DJF', 'VUV', 'XPF', 'BIF']);
const SIMBOLO = { EUR: '€', USD: 'US$', GBP: '£' };

export function decimalesDe(moneda) { return SIN_DECIMALES.has(String(moneda).toUpperCase()) ? 0 : 2; }

/** Unidad menor entera → «19,90 €». Solo aritmética entera. '—' si no es un entero seguro. */
export function dinero(monto, moneda, decimales) {
  if (!esEntero(monto)) return '—';
  const m = typeof moneda === 'string' && /^[A-Z]{3}$/.test(moneda) ? moneda : '';
  const d = Number.isInteger(decimales) && decimales >= 0 && decimales <= 4 ? decimales : decimalesDe(m);
  const neg = monto < 0;
  const abs = String(Math.abs(monto)).padStart(d + 1, '0');
  const ent = d ? abs.slice(0, -d) : abs;
  const dec = d ? abs.slice(-d) : '';
  const miles = ent.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${neg ? '-' : ''}${miles}${d ? ',' + dec : ''}${m ? ' ' + (SIMBOLO[m] || m) : ''}`;
}

/** «19,90» / «19.9» / «19» → 1990 (unidad menor, 2 decimales), con cadenas; null si no encaja. */
export function importeAMenor(cadena) {
  const m = /^(\d{1,3}(?:\.\d{3})*|\d+)(?:[.,](\d{1,2}))?$/.exec(String(cadena).trim());
  if (!m) return null;
  const ent = m[1].replace(/\./g, '');
  const dec = (m[2] || '').padEnd(2, '0');
  const n = Number(ent + dec);
  return Number.isSafeInteger(n) ? n : null;
}

// ───────────────────────── lectura tolerante de archivos del API ─────────────────────────

/** `GET /oferta/<id>/archivo` → {contenido: string|objeto}. Devuelve el objeto JSON o null (nunca lanza). */
export function jsonDeArchivo(datos) {
  if (datos === null || datos === undefined) return null;
  let c = datos;
  if (typeof datos === 'object' && 'contenido' in datos) c = datos.contenido;
  if (c && typeof c === 'object') return c;
  if (typeof c === 'string') {
    try { const v = JSON.parse(c); return v && typeof v === 'object' ? v : null; } catch (_) { return null; }
  }
  return null;
}

/** `GET /oferta/<id>/archivo` de un HTML → texto (string) o null. */
export function textoDeArchivo(datos) {
  if (datos === null || datos === undefined) return null;
  if (typeof datos === 'string') return datos;
  if (typeof datos === 'object' && typeof datos.contenido === 'string') return datos.contenido;
  return null;
}

// ───────────────────────── análisis estático del HTML (solo texto; jamás al DOM) ─────────────────────────

const ENTIDADES = { amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ', euro: '€', pound: '£', dollar: '$' };

function decodificar(s) {
  return s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (m, e) => {
    if (e[0] === '#') {
      const n = e[1] === 'x' || e[1] === 'X' ? parseInt(e.slice(2), 16) : parseInt(e.slice(1), 10);
      return Number.isInteger(n) && n > 0 && n < 0x110000 ? String.fromCodePoint(n) : m;
    }
    const v = ENTIDADES[e.toLowerCase()];
    return v === undefined ? m : v;
  });
}

function atributos(cadena) {
  const a = {};
  const re = /([A-Za-z_:][-A-Za-z0-9_:.]*)(?:\s*=\s*("([^"]*)"|'([^']*)'|([^\s"'>]+)))?/g;
  let m;
  while ((m = re.exec(cadena)) !== null) {
    const v = m[3] ?? m[4] ?? m[5];
    a[m[1].toLowerCase()] = v === undefined ? '' : decodificar(v);
  }
  return a;
}

// `[^<>]*` (no `[^>]*`): una etiqueta sin cierre no puede arrastrar el resto del documento en cada intento (ReDoS cuadrático, revisión de seguridad m-1).
const BLOQUES = /<\/?(?:p|li|h[1-6]|summary|button|label|a|div|section|header|footer|main|details|ul|ol|nav|article|aside|td|th|tr|br)\b[^<>]*>/gi;

/** Tope del HTML que se analiza (el servidor ya entrega ≤ 400 KB; esto protege si cambia). */
export const MAX_HTML_ANALIZADO = 600000;

const esPalabra = (cod) => (cod >= 48 && cod <= 57) || (cod >= 65 && cod <= 90) || (cod >= 97 && cod <= 122) || cod === 95;
const esBlanco = (cod) => cod === 32 || (cod >= 9 && cod <= 13) || cod === 160 || cod === 0xFEFF || cod === 0x2028 || cod === 0x2029 || (cod >= 0x2000 && cod <= 0x200A) || cod === 0x1680 || cod === 0x202F || cod === 0x205F || cod === 0x3000;

/** minúsculas SOLO ASCII: conserva la longitud (toLowerCase de Unicode puede cambiarla y desalinear los índices). */
function bajoAscii(s) { return s.replace(/[A-Z]/g, (c) => String.fromCharCode(c.charCodeAt(0) + 32)); }

/**
 * Quita los comentarios HTML con búsquedas lineales (indexOf), sin regex con retroceso: `<!--` sin cierre no congela la pestaña.
 * Igual que /<!--[\s\S]*?-->/g: un `<!--` sin `-->` posterior se deja tal cual. Devuelve {limpio, comentarios}.
 */
function quitarComentarios(src) {
  const comentarios = [];
  let limpio = '';
  let i = 0;
  while (i < src.length) {
    const a = src.indexOf('<!--', i);
    if (a === -1) break;
    const c = src.indexOf('-->', a + 4);
    if (c === -1) break;
    limpio += src.slice(i, a) + ' ';
    comentarios.push(txt(src.slice(a + 4, c), 200));
    i = c + 3;
  }
  return { limpio: limpio + src.slice(i), comentarios };
}

/**
 * Elementos `<nombre …>…</nombre\s*>` CERRADOS, de izquierda a derecha y sin retroceso (cada indexOf avanza; coste lineal).
 * `conApertura`: la etiqueta de apertura debe cerrar con «>» (como /<script\b([^>]*)>(…)<\/script\s*>/); si no, el contenido va desde el nombre.
 * Devuelve [{inicio, fin, atributos, contenido}]. Un elemento sin cierre termina la búsqueda (los posteriores tampoco lo tendrían).
 */
function elementosCerrados(src, bajo, nombre, { conApertura = true, primero = false } = {}) {
  const res = [];
  const abre = `<${nombre}`;
  const cierra = `</${nombre}`;
  let i = 0;
  while (i < src.length) {
    const a = bajo.indexOf(abre, i);
    if (a === -1) break;
    const despues = a + abre.length;
    if (esPalabra(bajo.charCodeAt(despues))) { i = despues; continue; } // \b: «<scripts» no es «<script»
    let g = despues;
    if (conApertura) {
      g = bajo.indexOf('>', despues);
      if (g === -1) break;
    }
    let c = bajo.indexOf(cierra, g);
    let fin = -1;
    while (c !== -1) {
      let k = c + cierra.length;
      while (k < src.length && esBlanco(src.charCodeAt(k))) k += 1;
      if (src[k] === '>') { fin = k + 1; break; }
      c = bajo.indexOf(cierra, c + 1);
    }
    if (c === -1) break;
    res.push({ inicio: a, fin, atributos: conApertura ? src.slice(despues, g) : '', contenido: src.slice(conApertura ? g + 1 : despues, c) });
    if (primero) break;
    i = fin;
  }
  return res;
}

/** Quita los elementos `<nombre>…</nombre>` (cerrados) sustituyéndolos por un espacio. */
function quitarElementos(src, nombre) {
  const els = elementosCerrados(src, bajoAscii(src), nombre, { conApertura: false });
  if (!els.length) return src;
  let out = '';
  let i = 0;
  for (const e of els) { out += src.slice(i, e.inicio) + ' '; i = e.fin; }
  return out + src.slice(i);
}

/**
 * Extrae del HTML lo que miran las comprobaciones (como `landing.validar`): lang, title, meta, enlaces, scripts, comentarios,
 * bloques de texto visibles y atributos data-* de <body>. Tolerante: un HTML roto no lanza.
 */
export function analizarHtml(html) {
  const src = typeof html === 'string' ? html.slice(0, MAX_HTML_ANALIZADO) : '';
  const out = { lang: null, title: '', meta: [], enlaces: [], scripts: [], comentarios: [], bloques: [], alts: [], body: {}, casillasMarcadas: 0, texto: '', vacio: src.trim() === '' };
  if (out.vacio) return out;
  const sc = quitarComentarios(src);
  for (const c of sc.comentarios) out.comentarios.push(c);
  let limpio = sc.limpio;
  const tags = /<\s*([A-Za-z][A-Za-z0-9-]*)\b([^<>]*)>/g;
  let m;
  while ((m = tags.exec(limpio)) !== null) {
    const t = m[1].toLowerCase();
    const a = atributos(m[2]);
    if (t === 'html') out.lang = a.lang ?? null;
    else if (t === 'body') out.body = a;
    else if (t === 'meta' && a.content !== undefined) out.meta.push({ clave: a.property || a.name || '', contenido: a.content });
    else if (t === 'a' && a.href !== undefined) out.enlaces.push({ etiqueta: 'a', url: a.href });
    else if (t === 'img') { if (a.src !== undefined) out.enlaces.push({ etiqueta: 'img', url: a.src }); out.alts.push(a.alt ?? ''); }
    else if (t === 'link' && a.href !== undefined) out.enlaces.push({ etiqueta: 'link', url: a.href });
    else if (t === 'input' && (a.type || '').toLowerCase() === 'checkbox' && 'checked' in a) out.casillasMarcadas += 1;
  }
  const bajo = bajoAscii(limpio);
  for (const e of elementosCerrados(limpio, bajo, 'script')) {
    const a = atributos(e.atributos);
    out.scripts.push({ src: a.src ?? null, enLinea: a.src === undefined && e.contenido.trim() !== '' });
  }
  const tt = elementosCerrados(limpio, bajo, 'title', { primero: true })[0];
  out.title = tt ? txt(decodificar(tt.contenido), 200) : '';
  limpio = quitarElementos(quitarElementos(quitarElementos(limpio, 'script'), 'style'), 'title');
  const trozos = limpio.replace(BLOQUES, '\u0000').replace(/<[^<>]*>/g, ' ').split('\u0000');
  for (const z of trozos) {
    const s = txt(decodificar(z), 600);
    if (s) out.bloques.push(s);
  }
  out.texto = out.bloques.join(' ');
  return out;
}

const RE_IMPORTE = /(\d{1,3}(?:[.,]\d{1,2})?)\s*(€|\$|£|\b[A-Z]{3}\b)/g;
const SIMBOLO_A_MONEDA = { '€': 'EUR', '$': 'USD', '£': 'GBP' };

/** Importes escritos en el texto visible: [{texto, minor, moneda}] (misma regla que landing.validar: RX_IMPORTE). */
export function importesEnTexto(texto) {
  const res = [];
  const s = String(texto ?? '');
  RE_IMPORTE.lastIndex = 0;
  let m;
  while ((m = RE_IMPORTE.exec(s)) !== null) {
    const minor = importeAMenor(m[1]);
    if (minor === null) continue;
    res.push({ texto: `${m[1]} ${m[2]}`, minor, moneda: SIMBOLO_A_MONEDA[m[2]] || m[2] });
  }
  return res;
}

const RE_BLOQUE_GARANTIA = /garant|devol|reembols|guarantee|refund/i;

/** Días citados en bloques que hablan de garantía: [{dias, bloque}]. */
export function diasDeGarantiaEnBloques(bloques) {
  const res = [];
  for (const b of lista(bloques)) {
    if (!RE_BLOQUE_GARANTIA.test(b)) continue;
    const re = /(\d{1,3})\s*(?:d[ií]as|days)/gi;
    let m;
    while ((m = re.exec(b)) !== null) res.push({ dias: Number(m[1]), bloque: b.slice(0, 80) });
  }
  return res;
}

// ───────────────────────── coherencia precio / moneda / garantía (C02) ─────────────────────────

function celda(valor, mostrar) { return { valor: valor === undefined ? null : valor, texto: valor === null || valor === undefined ? 'sin dato' : mostrar }; }

function estadoFila(vals) {
  const presentes = vals.filter((v) => v !== null && v !== undefined);
  if (presentes.length < 2) return 'sin_dato'; // una sola fuente no es una comparación
  return presentes.every((v) => v === presentes[0]) ? 'ok' : 'error';
}

/**
 * Compara oferta.json, checkout.json y el HTML (index): precio, moneda, garantía, bump, idioma, impuestos.
 * Cada fila: {campo, oferta, checkout, html, estado: 'ok'|'error'|'aviso'|'sin_dato', nota}.
 */
export function coherencia({ oferta = null, checkout = null, html = null } = {}) {
  const o = objeto(oferta);
  const c = objeto(checkout);
  const h = html && typeof html === 'object' && 'bloques' in html ? html : analizarHtml(html);
  const filas = [];
  const moneda = (typeof o.moneda === 'string' ? o.moneda : null) ?? (typeof c.moneda === 'string' ? c.moneda : null);

  // Precio
  const pOferta = objeto(objeto(o.precio).lista).monto;
  const pCheckout = objeto(c.precio).monto;
  const pHtml = h.body && h.body['data-precio-minor'] !== undefined && /^\d+$/.test(h.body['data-precio-minor']) ? Number(h.body['data-precio-minor']) : null;
  const vP = [esEntero(pOferta) ? pOferta : null, esEntero(pCheckout) ? pCheckout : null, pHtml];
  filas.push({ campo: 'Precio de lista', oferta: celda(vP[0], dinero(vP[0], moneda)), checkout: celda(vP[1], dinero(vP[1], moneda)), html: celda(vP[2], dinero(vP[2], moneda)), estado: estadoFila(vP), nota: 'En la página: el dato de precio que declara (data-precio-minor)' });

  // Importes visibles
  // lo que el HTML puede escribir lo fijan oferta y checkout; el data-precio-minor del propio HTML no se legitima a sí mismo
  const permitidos = new Set([vP[0], vP[1]].filter((v) => v !== null));
  const bump = objeto(o.bump);
  const bumpC = objeto(c.bump);
  if (esEntero(objeto(bump.precio).monto)) permitidos.add(bump.precio.monto);
  if (esEntero(objeto(bumpC.precio).monto)) permitidos.add(bumpC.precio.monto);
  const visibles = importesEnTexto(h.texto);
  const fuera = visibles.filter((i) => !permitidos.has(i.minor));
  filas.push({
    campo: 'Importes escritos en la página',
    oferta: celda(permitidos.size ? [...permitidos].sort().join(',') : null, [...permitidos].map((m) => dinero(m, moneda)).join(' · ')),
    checkout: celda(null, '—'),
    html: celda(visibles.length ? 1 : null, visibles.map((i) => i.texto).join(' · ') || 'ninguno'),
    estado: !visibles.length ? 'sin_dato' : fuera.length ? 'error' : 'ok',
    nota: fuera.length ? `No coinciden con la oferta ni con la pantalla de pago: ${fuera.map((i) => i.texto).join(', ')}` : 'Cada importe visible es el precio de lista o el de la oferta extra al pagar',
  });

  // Moneda
  const mO = typeof o.moneda === 'string' ? o.moneda : null;
  const mC = typeof c.moneda === 'string' ? c.moneda : (typeof objeto(c.precio).moneda === 'string' ? c.precio.moneda : null);
  const mH = h.body && typeof h.body['data-moneda'] === 'string' ? h.body['data-moneda'] : null;
  const simbolos = new Set(visibles.map((i) => i.moneda));
  const mT = simbolos.size === 1 ? [...simbolos][0] : null;
  filas.push({
    campo: 'Moneda', oferta: celda(mO, mO), checkout: celda(mC, mC), html: celda(mH, mH ?? 'sin dato'),
    estado: simbolos.size > 1 ? 'error' : estadoFila([mO, mC, mH, mT]),
    nota: simbolos.size > 1 ? `Varias monedas en el texto: ${[...simbolos].join(', ')}` : mT && mH && mT !== mH ? 'El símbolo de moneda del texto no es el que declara la página (data-moneda)' : 'En la página: la moneda que declara (data-moneda) y los símbolos del texto',
  });

  // Garantía
  const gO = objeto(o.garantia).dias;
  const gC = c.garantia_dias;
  const gH = h.body && /^\d+$/.test(h.body['data-garantia-dias'] ?? '') ? Number(h.body['data-garantia-dias']) : null;
  const diasTexto = diasDeGarantiaEnBloques(h.bloques);
  const distintos = [...new Set(diasTexto.map((d) => d.dias))];
  const vG = [esEntero(gO) ? gO : null, esEntero(gC) ? gC : null, gH, distintos.length === 1 ? distintos[0] : null];
  filas.push({
    campo: 'Garantía (días)', oferta: celda(vG[0], `${vG[0]} d`), checkout: celda(vG[1], `${vG[1]} d`),
    html: celda(gH ?? (distintos.length ? distintos[0] : null), gH !== null ? `${gH} d${distintos.length ? ` · texto: ${distintos.join(', ')} d` : ''}` : distintos.length ? `texto: ${distintos.join(', ')} d` : 'sin dato'),
    estado: distintos.length > 1 ? 'error' : estadoFila(vG),
    nota: distintos.length > 1 ? 'El texto cita plazos de garantía distintos' : 'En la página: los días que declara (data-garantia-dias) y los «N días» del texto de garantía',
  });

  // Bump
  const bO = objeto(bump.precio).monto;
  const bC = objeto(bumpC.precio).monto;
  if (o.bump !== undefined || c.bump !== undefined) {
    const vB = [esEntero(bO) ? bO : null, esEntero(bC) ? bC : null];
    const sinBump = (o.bump === null || o.bump === undefined) && (c.bump === null || c.bump === undefined);
    filas.push({
      campo: 'Oferta extra al pagar (precio)', oferta: celda(vB[0], dinero(vB[0], moneda)), checkout: celda(vB[1], dinero(vB[1], moneda)),
      html: celda(visibles.find((i) => i.minor === (bO ?? bC))?.minor ?? null, visibles.find((i) => i.minor === (bO ?? bC))?.texto ?? 'sin dato'),
      estado: sinBump ? 'sin_dato' : estadoFila(vB), nota: sinBump ? 'La oferta no incluye una oferta extra al pagar' : `Modo: ${txt(bumpC.modo, 40) || 'sin dato'}; la casilla nunca viene marcada de antemano`,
    });
  }

  // Idioma
  const lO = typeof o.locale === 'string' ? o.locale : null;
  filas.push({ campo: 'Idioma y país', oferta: celda(lO, lO), checkout: celda(null, '—'), html: celda(h.lang, h.lang ?? 'sin dato'), estado: estadoFila([lO, h.lang]), nota: 'En la página: el idioma que declara (lang)' });

  // Impuestos: con régimen «diferido» no se puede decir «IVA incluido» (C02)
  const modoImp = objeto(c.impuestos).modo;
  if (typeof modoImp === 'string') {
    const dice = /iva\s+incluido|vat\s+included|tax\s+included|impuestos\s+incluidos/i.test(h.texto);
    filas.push({
      campo: 'Impuestos', oferta: celda(objeto(o.precio).tax_behavior ?? null, objeto(o.precio).tax_behavior ?? 'sin dato'), checkout: celda(modoImp, `modo ${modoImp}`),
      html: celda(h.texto ? (dice ? 'dice «incluido»' : 'no afirma «incluido»') : null, dice ? 'dice «incluido»' : h.texto ? 'no afirma «incluido»' : 'sin dato'),
      estado: !h.texto ? 'sin_dato' : modoImp === 'diferido' && dice ? 'error' : 'ok',
      nota: 'Con el régimen «diferido» la página no puede afirmar «IVA incluido»',
    });
  }

  const cuenta = (e) => filas.filter((f) => f.estado === e).length;
  return { filas, resumen: { ok: cuenta('ok'), error: cuenta('error'), sinDato: cuenta('sin_dato') }, htmlDisponible: !h.vacio };
}

// ───────────────────────── indicios en el HTML (C01, C03, C10) ─────────────────────────

const RE_CONTADORES = /quedan\s+\d+|[úu]ltim[oa]s?\s+\d+|\d+\s+personas?\s+(?:viendo|compr)|cuenta\s+regresiva|viendo\s+ahora|cupos?\b|plazas?\s+limitadas/i;
const SCRIPT_PERMITIDO = '/js/consentimiento.js';

function hostDe(url) {
  const m = /^(?:https?:)?\/\/([^/?#:]+)/i.exec(String(url));
  return m ? m[1].toLowerCase() : null;
}

/** Indicios que se leen del HTML. NO sustituyen al QA ni a `landing.validar`: cada fila lo dice. */
export function indiciosHtml(html, { dominio = null } = {}) {
  const h = html && typeof html === 'object' && 'bloques' in html ? html : analizarHtml(html);
  if (h.vacio) return [];
  const dom = typeof dominio === 'string' ? dominio.toLowerCase() : null;
  const filas = [];
  const externos = (url) => { const host = hostDe(url); return host !== null && host !== dom; };

  const scriptsExt = h.scripts.filter((s) => s.src && externos(s.src));
  const scriptsOtros = h.scripts.filter((s) => s.src && !externos(s.src) && s.src !== SCRIPT_PERMITIDO);
  const enLinea = h.scripts.filter((s) => s.enLinea);
  filas.push({ id: 'C01', titulo: 'Código de otros sitios', estado: scriptsExt.length ? 'error' : 'ok', detalle: scriptsExt.length ? scriptsExt.map((s) => txt(s.src, 80)).join(', ') : 'ninguno' });
  filas.push({ id: 'C01', titulo: 'Código propio no permitido', estado: scriptsOtros.length ? 'aviso' : 'ok', detalle: scriptsOtros.length ? scriptsOtros.map((s) => txt(s.src, 80)).join(', ') : `solo el programa de cookies (${SCRIPT_PERMITIDO}) o ninguno` });
  filas.push({ id: 'C01', titulo: 'Código escrito dentro de la página', estado: enLinea.length ? 'aviso' : 'ok', detalle: enLinea.length ? `${enLinea.length} bloque(s) de código dentro de la página` : 'ninguno' });
  const enlExt = h.enlaces.filter((e) => externos(e.url));
  filas.push({ id: 'C01', titulo: 'Enlaces, imágenes o estilos externos', estado: enlExt.length ? 'error' : 'ok', detalle: enlExt.length ? enlExt.slice(0, 4).map((e) => `${e.etiqueta} ${txt(e.url, 70)}`).join(' · ') : 'ninguno' });
  filas.push({ id: 'C10', titulo: 'Casillas premarcadas', estado: h.casillasMarcadas ? 'error' : 'ok', detalle: h.casillasMarcadas ? `${h.casillasMarcadas} casilla(s) marcada(s) de antemano (checked)` : 'ninguna' });
  const visibles = [h.texto, h.title, ...h.alts, ...h.meta.map((m) => m.contenido)];
  filas.push({ id: 'C03', titulo: 'Texto «ejemplo» visible', estado: visibles.some((x) => /ejemplo/i.test(x)) ? 'error' : 'ok', detalle: visibles.some((x) => /ejemplo/i.test(x)) ? 'aparece «ejemplo» en texto, título, alt o meta' : 'no aparece' });
  const marca = h.comentarios.some((c) => /\[?EJEMPLO\]?/i.test(c));
  filas.push({ id: 'C03', titulo: 'Comentario [EJEMPLO]', estado: marca ? 'aviso' : 'ok', detalle: marca ? 'solo vale en pruebas locales: nunca puede llegar a la tienda real' : 'no hay' });
  filas.push({ id: 'C03', titulo: 'Contadores, cupos o escasez', estado: RE_CONTADORES.test(h.texto) ? 'error' : 'ok', detalle: RE_CONTADORES.test(h.texto) ? 'hay un texto de escasez o de cuenta regresiva' : 'ninguno' });
  return filas;
}

// ───────────────────────── rutas y legales ─────────────────────────

/** Ruta de la landing → archivo estático dentro de sitio/ (misma regla que landing.validar: «/»→index.html, «/x»→x.html). */
export function archivoDeRuta(ruta) {
  const r = String(ruta ?? '');
  if (!r.startsWith('/') || r.includes('//') || r.includes('..') || r.includes('\\') || r.includes('\u0000')) return null;
  const limpia = r.replace(/\/+$/, '') || '/';
  if (limpia === '/') return 'index.html';
  if (!/^\/[A-Za-z0-9_\-./]+$/.test(limpia)) return null;
  return limpia.slice(1) + (/\.[A-Za-z0-9]+$/.test(limpia) ? '' : '.html');
}

/**
 * Tabla de rutas de rutas.json + sondas (estado HTTP leído por el panel al pedir /sitio/<id>/<archivo>) + artefactos de la etapa.
 * `sondas`: {archivo: número HTTP | 'error'}; `artefactos`: [{ruta,…}] (rutas relativas a ofertas/<id>/).
 */
export function modeloRutas({ rutas = null, sondas = {}, artefactos = null } = {}) {
  const r = objeto(rutas);
  const existe = Array.isArray(artefactos) ? new Set(artefactos.map((a) => String(a && a.ruta))) : null;
  const filas = Object.entries(r).map(([ruta, destino]) => {
    const d = typeof destino === 'string' ? destino : '';
    const dinamica = d.startsWith('dinamica:');
    const archivo = dinamica ? null : archivoDeRuta(ruta);
    const sonda = archivo !== null && archivo in sondas ? sondas[archivo] : null;
    const enDisco = archivo !== null && existe ? existe.has(`05-landing/sitio/${archivo}`) : null;
    const legal = /^\/legal\/([a-z]+)$/.exec(ruta);
    let estado;
    if (dinamica) estado = 'dinamica';
    else if (sonda === 200) estado = 'ok';
    else if (sonda !== null) estado = 'error';
    else if (enDisco === false) estado = 'error';
    else estado = 'sin_comprobar';
    return {
      ruta: txt(ruta, 80), destino: txt(d, 80), archivo, dinamica, legal: legal ? legal[1] : null,
      http: sonda, enDisco, estado,
      texto: dinamica ? 'dinámica (la atiende el servidor de la tienda; el panel no la muestra)' : sonda === 200 ? '200' : sonda !== null ? `HTTP ${sonda}` : enDisco === false ? 'falta el archivo' : 'sin comprobar',
    };
  });
  const presentes = new Set(filas.map((f) => f.legal).filter(Boolean));
  const legales = LEGALES.map((n) => {
    const f = filas.find((x) => x.legal === n) || null;
    return { id: n, enRutas: presentes.has(n), fila: f, estado: !f ? 'error' : f.estado, texto: !f ? 'falta la ruta en el mapa de rutas' : f.texto };
  });
  const legalesOk = legales.filter((l) => l.estado === 'ok').length;
  return { filas, legales, resumen: { total: filas.length, legalesOk, legalesTotal: LEGALES.length, errores: filas.filter((f) => f.estado === 'error').length, sinComprobar: filas.filter((f) => f.estado === 'sin_comprobar').length } };
}

/** Archivos que el panel va a sondear (GET /sitio/<id>/<archivo>): los estáticos de rutas.json, sin duplicados y acotados. */
export function archivosASondear(rutas, max = 24) {
  const out = [];
  for (const [ruta, destino] of Object.entries(objeto(rutas))) {
    if (String(destino).startsWith('dinamica:')) continue;
    const a = archivoDeRuta(ruta);
    if (a && !out.includes(a)) out.push(a);
    if (out.length >= max) break;
  }
  return out;
}

/** URL de la vista previa dentro del panel: siempre /sitio/<id>/<archivo> (solo GET; el iframe va con sandbox). null si el id no es válido. */
export function urlSitio(ofertaId, archivo = 'index.html') {
  if (!RE_OFERTA_ID.test(String(ofertaId))) return null;
  const a = String(archivo);
  if (a.includes('..') || a.startsWith('/') || !/^[A-Za-z0-9_\-./]+$/.test(a)) return null;
  return `/sitio/${ofertaId}/${a}`;
}

// ───────────────────────── assets ─────────────────────────

export function modeloAssets(assets) {
  const slots = lista(objeto(assets).slots).map((s) => {
    const estado = s.estado ?? null;
    const pendiente = estado !== 'aprobado';
    const placeholder = s.origen === 'placeholder_de_ejemplo';
    return {
      id: txt(s.slot_id, 60), seccion: txt(s.seccion, 30), tipo: txt(s.tipo, 30), ratio: txt(s.ratio, 10), proposito: txt(s.proposito, 160), alt: txt(s.alt, 160),
      estado: estado === 'aprobado' ? 'aprobado' : estado === 'asignado' ? 'asignado' : estado === 'vacio' ? 'vacio' : 'desconocido',
      pendiente, placeholder, archivo: s.archivo ? txt(s.archivo, 120) : null, origen: s.origen ? txt(s.origen, 40) : null, iaGenerado: s.ia_generado === true,
      pesoMaxKb: esEntero(s.peso_max_kb) ? s.peso_max_kb : null, sha: typeof s.sha256 === 'string' ? s.sha256 : null,
    };
  });
  return {
    existe: assets !== null && assets !== undefined && typeof assets === 'object',
    version: txt(objeto(assets).version, 20) || null,
    slots,
    resumen: { declaradas: slots.length, aprobadas: slots.filter((s) => s.estado === 'aprobado').length, pendientes: slots.filter((s) => s.pendiente).length, placeholders: slots.filter((s) => s.placeholder).length, ia: slots.filter((s) => s.iaGenerado).length },
  };
}

// ───────────────────────── checkout y tracking ─────────────────────────

export function modeloCheckout(checkout) {
  const c = objeto(checkout);
  if (!Object.keys(c).length) return null;
  const moneda = typeof c.moneda === 'string' ? c.moneda : objeto(c.precio).moneda;
  const live = objeto(c.price_ids).live;
  return {
    version: txt(c.version, 20) || null,
    schema: txt(c.schema_version, 12) || null,
    precio: dinero(objeto(c.precio).monto, moneda),
    moneda: txt(moneda, 4),
    priceTest: objeto(c.price_ids).test ? txt(c.price_ids.test, 80) : null,
    priceLive: live ? txt(live, 80) : null,
    bump: c.bump ? { modo: txt(c.bump.modo, 30), precio: dinero(objeto(c.bump.precio).monto, objeto(c.bump.precio).moneda ?? moneda), copy: txt(c.bump.copy, 200), priceId: txt(c.bump.price_id, 80) } : null,
    upsell: c.upsell ? { precio: dinero(objeto(c.upsell.precio).monto, objeto(c.upsell.precio).moneda ?? moneda) } : null,
    metodos: lista(c.metodos).map((m) => txt(m, 20)),
    descriptor: txt(c.descriptor, 40) || null,
    garantia: esEntero(c.garantia_dias) ? c.garantia_dias : null,
    impuestos: c.impuestos ? { modo: txt(c.impuestos.modo, 20), pais: c.impuestos.pais ? txt(c.impuestos.pais, 4) : null, tax_behavior: txt(c.impuestos.tax_behavior, 20) } : null,
    uiMode: txt(c.ui_mode, 20) || null,
    sesionEnServidor: c.sesion_en_servidor === true,
    expiraMin: esEntero(c.expires_at_min) ? c.expires_at_min : null,
    consentimientos: lista(c.consentimientos).map((x) => ({ id: txt(x.id, 60), version: txt(x.texto_version, 12), obligatorio: x.obligatorio === true })),
    metadata: lista(c.metadata_esquema).map((m) => txt(m, 40)),
    successUrl: c.success_url ? txt(c.success_url, 160) : null,
    returnUrl: c.return_url ? txt(c.return_url, 160) : null,
  };
}

export function modeloTracking(tracking, checkout) {
  const t = objeto(tracking);
  if (!Object.keys(t).length) return null;
  const meta = new Set(lista(objeto(checkout).metadata_esquema));
  const obligatorios = lista(objeto(t.utm_esquema).parametros_obligatorios).map(String);
  const faltanEnMetadata = Object.keys(objeto(checkout)).length ? obligatorios.filter((p) => !meta.has(p)) : null;
  const cg = objeto(t.consent_gating);
  const ds = objeto(t.datos_sensibles);
  const eventos = lista(t.eventos).map((e) => ({
    nombre: txt(e.nombre, 40), canal: txt(e.canal, 12), eventId: txt(e.event_id_regla, 80), parametros: lista(e.parametros_permitidos).map((p) => txt(p, 30)),
    enListaCerrada: EVENTOS_CERRADOS.includes(e.nombre),
  }));
  const faltantes = EVENTOS_CERRADOS.filter((n) => !eventos.some((e) => e.nombre === n));
  return {
    version: txt(t.version, 20) || null,
    pixelId: t.pixel_id ? txt(t.pixel_id, 30) : null,
    datasetId: t.dataset_id ? txt(t.dataset_id, 30) : null,
    dominio: t.dominio_verificado ? txt(t.dominio_verificado, 120) : null,
    eventos,
    eventosFueraDeLista: eventos.filter((e) => !e.enListaCerrada).map((e) => e.nombre),
    eventosFaltantes: faltantes,
    consentimiento: {
      plataforma: txt(cg.plataforma, 40) || null,
      requeridoUeUk: cg.requerido_ue_uk === true,
      toleraSinConsentimiento: cg.tolerar_trafico_sin_consentimiento === true,
      ok: cg.plataforma === 'banner_propio_v1',
    },
    utm: { plantilla: txt(objeto(t.utm_esquema).plantilla, 400), obligatorios, faltanEnMetadata },
    emq: t.emq_objetivo !== undefined ? txt(t.emq_objetivo, 10) : null,
    modoPrueba: t.modo_prueba === true,
    datosSensiblesPermitidos: ds.permitidos === true,
    camposProhibidos: lista(ds.campos_prohibidos).map((x) => txt(x, 40)),
  };
}

// ───────────────────────── QA de D5 (C01–C17 con estado) ─────────────────────────

function numVersion(nombre) {
  const m = /-v(\d+)\.json$/.exec(String(nombre));
  return m ? Number(m[1]) : -1;
}

/** De `etapas[D5].qa` ([{archivo, veredicto, resumen}]) elige el último dictamen del Maker/QA (d5-v<n>) y el del X1 (x1-d5-v<n>). */
export function elegirQaD5(qa) {
  const l = lista(qa).map((q) => ({ ...q, _archivo: String(q && (q.archivo ?? q.ruta ?? '')) }));
  const esX1 = (a) => /(^|\/)x1-d5-v\d+\.json$/.test(a);
  const esD5 = (a) => /(^|\/)d5-v\d+\.json$/.test(a);
  const mejor = (f) => l.filter((q) => f(q._archivo)).sort((a, b) => numVersion(b._archivo) - numVersion(a._archivo))[0] || null;
  return { d5: mejor(esD5), x1: mejor(esX1) };
}

const MAP_RESULTADO = { pass: 'ok', fail: 'error', no_aplica: 'no_aplica' };

/**
 * Estado de C01–C17 a partir del QA de D5 (checks_l1 con check_id «C##» y hallazgos de ese check) y, aparte, todo lo que el QA
 * registró con otros identificadores. Sin resultado = «sin_resultado» (nunca «ok»).
 */
export function estadoChecks({ qa = null, x1 = null } = {}) {
  const docs = [qa, x1].filter((d) => d && typeof d === 'object');
  const porId = new Map();
  const otros = [];
  for (const [i, d] of docs.entries()) {
    const quien = i === 0 && qa ? 'Revisión de calidad' : 'Cumplimiento';
    for (const c of lista(d.checks_l1)) {
      const id = idCheckC(c.check_id);
      const fila = { id: txt(c.check_id, 40), resultado: MAP_RESULTADO[c.resultado] ?? 'desconocido', detalle: txt(c.detalle, 240), quien };
      if (id) { porId.set(id, [...(porId.get(id) || []), fila]); } else otros.push(fila);
    }
  }
  const hallazgosPorId = new Map();
  const otrosHallazgos = [];
  for (const [i, d] of docs.entries()) {
    const quien = i === 0 && qa ? 'Revisión de calidad' : 'Cumplimiento';
    for (const h of lista(d.hallazgos)) {
      const f = { id: txt(h.check_id, 40), severidad: txt(h.severidad, 12), estado: txt(h.estado, 24), descripcion: txt(h.descripcion, 240), evidencia: txt(h.evidencia, 200), quien, abierto: h.estado === 'abierto' || h.estado === 'devuelto_al_maker' };
      const id = idCheckC(h.check_id);
      if (id) hallazgosPorId.set(id, [...(hallazgosPorId.get(id) || []), f]); else otrosHallazgos.push(f);
    }
  }
  const filas = CHECKS_C.map((c) => {
    const rs = porId.get(c.id) || [];
    const hs = hallazgosPorId.get(c.id) || [];
    const abiertos = hs.filter((h) => h.abierto);
    let estado;
    if (rs.some((r) => r.resultado === 'error')) estado = 'error';
    else if (abiertos.some((h) => h.severidad === 'BLOQUEANTE')) estado = 'error';
    else if (abiertos.length) estado = 'aviso';
    else if (rs.length && rs.every((r) => r.resultado === 'no_aplica')) estado = 'no_aplica';
    else if (rs.some((r) => r.resultado === 'ok')) estado = 'ok';
    else if (hs.length) estado = 'ok'; // hallazgos todos cerrados o aceptados
    else estado = 'sin_resultado';
    return {
      id: c.id, titulo: c.titulo, falla: c.falla, estado,
      detalle: [...rs.map((r) => `${r.quien}: ${r.detalle || r.resultado}`), ...hs.map((h) => `${h.quien}: ${h.severidad} ${h.estado} — ${h.descripcion}`)].join(' · '),
    };
  });
  const cuenta = (e) => filas.filter((f) => f.estado === e).length;
  return {
    filas,
    otros,
    otrosHallazgos,
    resumen: { ok: cuenta('ok'), error: cuenta('error'), aviso: cuenta('aviso'), noAplica: cuenta('no_aplica'), sinResultado: cuenta('sin_resultado'), total: filas.length },
    hayResultadosC: filas.some((f) => f.estado !== 'sin_resultado'),
  };
}

/** Cabecera de un dictamen QA/X1. */
export function resumenQa(doc) {
  const d = objeto(doc);
  if (!Object.keys(d).length) return null;
  return {
    etapa: txt(d.etapa, 8), version: txt(d.version, 12), ronda: esEntero(d.ronda) ? d.ronda : null,
    veredicto: txt(d.veredicto, 20), puntaje: d.puntaje_global !== undefined ? txt(d.puntaje_global, 8) : null, umbral: d.umbral !== undefined ? txt(d.umbral, 8) : null,
    creadoEn: typeof d.creado_en === 'string' ? d.creado_en : null,
    artefactoSha: typeof d.artefacto_sha256 === 'string' ? d.artefacto_sha256 : null,
    x1: d.x1 && typeof d.x1 === 'object' ? { veredicto: txt(d.x1.veredicto, 20), ref: txt(d.x1.dictamen_ref, 80) } : null,
    riesgos: lista(d.riesgos_residuales).map((r) => txt(r, 200)),
    hallazgos: lista(d.hallazgos).length,
  };
}

/** Veredicto de una revisión en palabras (PASS → «Aprobada»). Con `{ cumplimiento: true }` usa los términos del dictamen de cumplimiento. */
export function veredictoTexto(v, { cumplimiento = false } = {}) {
  const base = cumplimiento
    ? { PASS: 'Sin objeciones', PASS_CON_NOTAS: 'Con notas', FAIL: 'No pasa', ESCALAR: 'Lo decide una persona' }
    : { PASS: 'Aprobada', PASS_CON_NOTAS: 'Aprobada con notas', FAIL: 'Rechazada', ESCALAR: 'Pasó a tu decisión' };
  return base[v] || (v ? txt(v, 20) : 'Sin veredicto');
}

export function tonoVeredicto(v) {
  if (v === 'PASS') return 'ok';
  if (v === 'PASS_CON_NOTAS') return 'aviso';
  if (v === 'FAIL') return 'error';
  if (v === 'ESCALAR') return 'error';
  return 'neutro';
}

/** Despliegue (despliegue.json): lo que haya, acotado y neutralizado. */
export function modeloDespliegue(d) {
  const x = objeto(d);
  if (!Object.keys(x).length) return null;
  const kv = [];
  for (const [k, v] of Object.entries(x)) {
    if (v !== null && typeof v === 'object') continue;
    kv.push([txt(k, 40), txt(v, 160)]);
  }
  return { kv: kv.slice(0, 16), lighthouse: x.lighthouse && typeof x.lighthouse === 'object' ? Object.entries(x.lighthouse).filter(([, v]) => typeof v !== 'object').map(([k, v]) => [txt(k, 40), txt(v, 20)]) : [] };
}

/** Elige la oferta de la pantalla: la activa si existe en la lista; si no, null (se pide elegir). */
export function ofertaEfectiva(ofertaActiva, ofertas) {
  const ids = lista(ofertas).map((o) => o && o.oferta_id).filter((x) => typeof x === 'string');
  if (typeof ofertaActiva === 'string' && ids.includes(ofertaActiva)) return ofertaActiva;
  return null;
}

/** Etapa D5 de GET /oferta/<id>. */
export function etapaD5(detalle) {
  const e = lista(objeto(detalle).etapas).find((x) => x && x.id === 'D5');
  return e || null;
}

// ───────────────────────── comprobaciones por grupos (lenguaje humano) ─────────────────────────

/** Nombre corto y humano de cada comprobación (el texto técnico completo sigue en CHECKS_C[i].titulo). */
export const NOMBRE_CHECK = Object.freeze({
  C01: 'Sitio sin errores ni enlaces externos',
  C02: 'Precio, moneda y garantía coherentes',
  C03: 'Sin promesas falsas, urgencia ni testimonios inventados',
  C04: 'Velocidad de carga en móvil',
  C05: 'Se ve bien en móvil y tablet, y se puede comprar',
  C06: 'El enlace del anuncio llega completo a la página de venta',
  C07: 'El pago se confirma una sola vez y solo si se cobró',
  C08: 'La entrega llega al comprador una sola vez',
  C09: 'Medición sin duplicados ni datos personales',
  C10: 'Nada se envía a Meta antes de aceptar las cookies',
  C11: 'Páginas legales completas',
  C12: 'Accesibilidad',
  C13: 'Se puede volver atrás con un comando',
  C14: 'Pantalla de pago segura: el cliente no fija importes',
  C15: 'Riesgo dentro de lo permitido para cada país',
  C16: 'Datos neutros: sin términos sensibles',
  C17: 'Mismo sitio para todos, también para Meta',
});

export const GRUPOS_CHECKS = Object.freeze([
  { id: 'sitio', titulo: 'Sitio y experiencia', ids: Object.freeze(['C01', 'C04', 'C05', 'C12', 'C13']) },
  { id: 'contenido', titulo: 'Contenido y coherencia', ids: Object.freeze(['C02', 'C03', 'C15', 'C16', 'C17']) },
  { id: 'compra', titulo: 'Compra y entrega', ids: Object.freeze(['C07', 'C08', 'C14']) },
  { id: 'medicion', titulo: 'Medición y consentimiento', ids: Object.freeze(['C06', 'C09', 'C10']) },
  { id: 'legal', titulo: 'Páginas legales', ids: Object.freeze(['C11']) },
]);

const FALLA_HUMANA = Object.freeze({
  BLOQ: 'Bloqueante: si falla, la página de venta no puede avanzar',
  MAYOR: 'Mayor: hay que corregirlo',
  'MAYOR (BLOQ si CTA, legal o archivo interno)': 'Mayor; bloqueante si falla el botón de compra, una página legal o un archivo propio',
  'MAYOR (BLOQ si no se puede comprar o recibir)': 'Mayor; bloqueante si no se puede comprar o recibir el producto',
  'BLOQ (ROJO) / MAYOR': 'Bloqueante si el riesgo es rojo; si no, mayor',
});

/** Texto en palabras simples de lo que pasa si falla una comprobación (el valor crudo de `falla` sigue siendo la entrada de la lógica). */
export function fallaHumana(falla) {
  const f = String(falla ?? '');
  if (FALLA_HUMANA[f]) return FALLA_HUMANA[f];
  return f.replace(/\bBLOQ\b/g, 'bloqueante').replace(/\bMAYOR\b/g, 'mayor').replace(/\bCTA\b/g, 'el botón de compra');
}

/** «BLOQ…» → bloqueante; «MAYOR…» → mayor. `detalle` explica en palabras simples qué significa. */
export function severidadDeFalla(falla) {
  const f = String(falla ?? '');
  if (/^BLOQ/i.test(f)) return { id: 'bloqueante', texto: 'Bloqueante si falla', detalle: fallaHumana(f) };
  if (/^MAYOR/i.test(f)) return { id: 'mayor', texto: 'Mayor si falla', detalle: fallaHumana(f) };
  return { id: 'otra', texto: 'Si falla', detalle: fallaHumana(f) };
}

/** Agrupa las filas de `estadoChecks().filas` en los grupos de la pantalla, con el recuento de cada uno. Los C## sin grupo van a «Otras». */
export function agruparChecks(filas) {
  const porId = new Map(lista(filas).map((f) => [f.id, f]));
  const usados = new Set();
  const cuenta = (fs, e) => fs.filter((f) => f.estado === e).length;
  const armar = (g, fs) => ({
    id: g.id, titulo: g.titulo,
    filas: fs.map((f) => ({ ...f, nombre: NOMBRE_CHECK[f.id] || f.titulo, severidad: severidadDeFalla(f.falla) })),
    resumen: { total: fs.length, ok: cuenta(fs, 'ok'), error: cuenta(fs, 'error'), aviso: cuenta(fs, 'aviso'), noAplica: cuenta(fs, 'no_aplica'), sinResultado: cuenta(fs, 'sin_resultado') },
  });
  const grupos = GRUPOS_CHECKS.map((g) => {
    const fs = g.ids.map((id) => porId.get(id)).filter(Boolean);
    fs.forEach((f) => usados.add(f.id));
    return armar(g, fs);
  });
  const resto = lista(filas).filter((f) => !usados.has(f.id));
  if (resto.length) grupos.push(armar({ id: 'otras', titulo: 'Otras comprobaciones' }, resto));
  return grupos;
}

/** Lo que revisa el plan de tracking: frases de problema (mismas reglas que antes; ahora reutilizables por el panel de atención). */
export function problemasTracking(m) {
  if (!m) return [];
  const problemas = [];
  if (!m.consentimiento.ok) problemas.push(`La plataforma de consentimiento es «${m.consentimiento.plataforma}», y no el aviso de cookies propio que se espera.`);
  if (m.datosSensiblesPermitidos) problemas.push('El plan de medición permite enviar datos sensibles: debe prohibirlo.');
  if (m.eventosFueraDeLista.length) problemas.push(`Eventos que no están en la lista permitida: ${m.eventosFueraDeLista.join(', ')}.`);
  if (m.eventosFaltantes.length) problemas.push(`Faltan eventos de la lista permitida: ${m.eventosFaltantes.join(', ')}.`);
  if (m.utm.faltanEnMetadata && m.utm.faltanEnMetadata.length) problemas.push(`La pantalla de pago no guarda estas etiquetas del anuncio con la compra: ${m.utm.faltanEnMetadata.join(', ')}.`);
  return problemas;
}

/**
 * Avisos priorizados de la pantalla («Requiere tu atención»), calculados de lo leído. Cada uno lleva `tab` (pestaña donde se ve).
 * tono: grave (algo falla y bloquea o descuadra) · aviso (falta o hay que mirar) · info.
 */
export function avisosLanding({ checks = null, coherenciaR = null, assets = null, trackingProblemas = [], faltan = [], qaR = null, x1R = null, sitioExiste = false, placeholders = 0 } = {}) {
  const out = [];
  const cs = checks ? checks.resumen : null;
  if (cs && cs.error) {
    const ids = checks.filas.filter((f) => f.estado === 'error').map((f) => f.id);
    out.push({ tono: 'grave', titulo: `${cs.error} ${cs.error === 1 ? 'comprobación' : 'comprobaciones'} de la página de venta ${cs.error === 1 ? 'falla' : 'fallan'}`, detalle: ids.map((id) => `${id}: ${NOMBRE_CHECK[id] || id}`).slice(0, 4).join(' · '), tab: 'comprobaciones' });
  }
  if (coherenciaR && coherenciaR.error) out.push({ tono: 'grave', titulo: 'El precio, la moneda o la garantía no coinciden entre la oferta, la pantalla de pago y la página de venta', detalle: `${coherenciaR.error} campo${coherenciaR.error === 1 ? '' : 's'} difiere${coherenciaR.error === 1 ? '' : 'n'}.`, tab: 'coherencia' });
  for (const p of trackingProblemas.slice(0, 3)) out.push({ tono: 'grave', titulo: 'Medición y consentimiento: algo no cumple', detalle: p, tab: 'tracking' });
  if (faltan.length) out.push({ tono: 'aviso', titulo: `Faltan ${faltan.length} archivo${faltan.length === 1 ? '' : 's'} de la etapa de la página de venta`, detalle: faltan.join(', '), tab: null });
  if (cs && !checks.hayResultadosC && sitioExiste) out.push({ tono: 'aviso', titulo: 'Las comprobaciones C01–C17 aún no tienen resultados', detalle: 'Sin resultado no significa correcto: hay que correr la revisión de calidad de la etapa.', tab: 'comprobaciones' });
  if (assets && assets.existe && assets.resumen.pendientes) out.push({ tono: 'aviso', titulo: `${assets.resumen.pendientes} de ${assets.resumen.declaradas} ranuras de imagen sin aprobar`, detalle: placeholders ? `${placeholders} son marcadores de ejemplo que nunca pueden ir a producción.` : 'Ninguna imagen puede ir sin una ranura aprobada.', tab: 'assets' });
  if (!x1R && sitioExiste) out.push({ tono: 'info', titulo: 'Aún no hay informe de cumplimiento de la página de venta', detalle: 'Sin él no se publica.', tab: null });
  if (!qaR && sitioExiste) out.push({ tono: 'info', titulo: 'Aún no hay informe de la revisión de calidad de la página de venta', detalle: 'Se escribe al terminar la ronda de revisión.', tab: null });
  return out;
}
