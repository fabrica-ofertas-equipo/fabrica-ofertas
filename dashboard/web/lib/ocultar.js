// lib/ocultar.js — «Ocultar info»: difumina en todo el panel lo que el dueño elija, para grabar la pantalla sin mostrarlo.
//
// Pedido del dueño (2026-11-13): «estoy grabando mi recorrido para YouTube, no quiero dar a conocer el nombre de las ofertas pero sí que se
// vea la bandera para reconocerla; así lo hace esta app (Impultienda: botón «Ocultar info» que difumina clientes y tiendas)».
//
// Cómo funciona, sin tocar cada pantalla:
//  1. El panel registra los textos sensibles de cada categoría (nombres de ofertas, productos, anuncios, referentes) a partir de /negocio.
//  2. Un observador del DOM envuelve cada aparición de esos textos (y de los montos de dinero) en <span class="oc oc--<categoría>">;
//     en SVG marca el <text> entero. Lo hace siempre, oculto o no: así, prender o apagar una categoría es instantáneo (solo CSS).
//  3. `<html data-ocultar="nombres dinero …">` decide qué se difumina. Los `title` (lo que aparece al pasar el cursor) y el título de la
//     pestaña se tapan con «•••» mientras la categoría esté oculta, y vuelven al apagarla.
//  4. Con los nombres ocultos, la dirección de la ficha usa el número de la oferta (#/negocio/~2) en vez de su nombre.
//  5. «Imágenes y creativos» (dueño, 15-nov): difumina toda imagen, video, iframe o lienzo del panel (miniaturas de anuncios, piezas,
//     vistas previas) con CSS, sin depender de una lista de términos. Los íconos son SVG propios y no se tocan.
//  6. Los enlaces que nombran algo oculto (la tienda, la landing original) muestran «•••» en la barra de estado al pasar el cursor;
//     el destino real queda en data-oc-href y el clic lo sigue abriendo.
// Las banderas, los colores y los íconos nunca se ocultan. Lo elegido se recuerda en este navegador.

export const CATEGORIAS = [
  { clave: 'nombres', texto: 'Nombres de ofertas', ayuda: 'Ofertas, tiendas, fan page y píxel. La bandera y el color quedan a la vista.' },
  { clave: 'productos', texto: 'Productos y upsells', ayuda: 'Qué vende cada oferta y los nombres de sus upsells.' },
  { clave: 'anuncios', texto: 'Anuncios y campañas', ayuda: 'Nombres de anuncios, conjuntos y campañas.' },
  { clave: 'referentes', texto: 'Referentes', ayuda: 'La oferta original que se modeló y su landing.' },
  { clave: 'imagenes', texto: 'Imágenes y creativos', ayuda: 'Miniaturas de anuncios, piezas y toda foto o video del panel.' },
  { clave: 'dinero', texto: 'Montos de dinero', ayuda: 'Todo lo que lleva US$, MX$, R$ o USD. Los ROAS y porcentajes quedan.' },
];
// categorías que no salen de una lista de términos (las resuelve el CSS o el patrón de montos)
const SIN_TERMINOS = new Set(['dinero', 'imagenes']);
const CLAVES = CATEGORIAS.map((c) => c.clave);
export const CLAVE_ALMACEN = 'panel.ocultar';
const POR_DEFECTO = ['nombres', 'productos', 'anuncios', 'referentes', 'imagenes'];
// versión de lo recordado: al sumar una categoría que el dueño pidió prendida, se agrega a lo que ya tenía elegido
const VERSION = 2;
const NUEVAS_POR_VERSION = { 2: ['imagenes'] };
const MASCARA = '•••';
const LARGO_MINIMO = 3;

// ───────────────────────── estado ─────────────────────────

let activo = false;          // ¿está prendido «Ocultar info»?
let elegidas = new Set(POR_DEFECTO);
const escuchas = new Set();

function almacen() { try { return globalThis.localStorage || null; } catch (_) { return null; } }

/** Lee lo recordado: {activo, elegidas[]}. Datos raros → por defecto (apagado, con las categorías de nombres e imágenes elegidas).
 *  Lo guardado antes de una categoría nueva la recibe prendida (p. ej. «imagenes» en la versión 2). */
export function leerPreferencia(alm = almacen()) {
  try {
    const p = JSON.parse((alm && alm.getItem(CLAVE_ALMACEN)) || 'null');
    if (p && typeof p === 'object') {
      const el = Array.isArray(p.elegidas) ? p.elegidas.filter((c) => CLAVES.includes(c)) : POR_DEFECTO.slice();
      const v = Number.isInteger(p.version) ? p.version : 1;
      for (let n = v + 1; n <= VERSION; n += 1) for (const c of NUEVAS_POR_VERSION[n] || []) if (!el.includes(c)) el.push(c);
      return { activo: p.activo === true, elegidas: CLAVES.filter((c) => el.includes(c)) };
    }
  } catch (_) { /* nada */ }
  return { activo: false, elegidas: POR_DEFECTO.slice() };
}
function guardar() { try { const a = almacen(); if (a) a.setItem(CLAVE_ALMACEN, JSON.stringify({ version: VERSION, activo, elegidas: [...elegidas] })); } catch (_) { /* sin almacenamiento */ } }

/** Categorías que se están difuminando ahora (vacío si «Ocultar info» está apagado). */
export function ocultas() { return activo ? CLAVES.filter((c) => elegidas.has(c)) : []; }
export function oculta(categoria) { return activo && elegidas.has(categoria); }
export function estado() { return { activo, elegidas: [...elegidas] }; }
export function alCambiar(fn) { escuchas.add(fn); return () => escuchas.delete(fn); }

export function fijar({ activo: a = activo, elegidas: e = [...elegidas] } = {}) {
  const antes = ocultas().join(' ');
  activo = Boolean(a);
  elegidas = new Set(e.filter((c) => CLAVES.includes(c)));
  guardar();
  aplicar();
  if (ocultas().join(' ') !== antes) for (const fn of escuchas) { try { fn(estado()); } catch (err) { console.error(err); } }
}

// ───────────────────────── direcciones sin nombre ─────────────────────────

/** Identificador de la oferta para la dirección: su número (~1, ~2…, orden del libro) si los nombres están ocultos; si no, su id. */
export function refOferta(id, ids, ocultarNombres = oculta('nombres')) {
  const i = Array.isArray(ids) ? ids.indexOf(id) : -1;
  return ocultarNombres && i >= 0 ? `~${i + 1}` : id;
}
/** Al revés: «~2» → id de la segunda oferta; cualquier otro texto se devuelve igual. */
export function resolverRef(ref, ids) {
  const m = /^~(\d{1,3})$/.exec(String(ref || ''));
  if (!m) return ref;
  const i = Number(m[1]) - 1;
  return Array.isArray(ids) && ids[i] ? ids[i] : ref;
}

// ───────────────────────── textos sensibles ─────────────────────────

const terminos = Object.fromEntries(CLAVES.filter((c) => !SIN_TERMINOS.has(c)).map((c) => [c, []]));
let patron = null;            // RegExp combinada con un grupo por categoría
let ordenGrupos = [];

// IDs de Meta (campaña, conjunto, anuncio, creativo, página, píxel, cuenta): 15 a 19 cifras seguidas, aunque no estén en el libro
const ID_META = String.raw`(?<!\d|\d[.,])\d{15,19}(?!\d|[.,]\d)`;   // sin tocar números con separador de miles
const DINERO = String.raw`(?:[−+\-]\s?)?(?:US|MX|R|AR|CO|CL)?\$\s?\d[\d.,]*|\d[\d.,]*\s?(?:USD|MXN|BRL|ARS)\b`;
const escapar = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Palabras del propio panel que nunca son un nombre aunque un dato las traiga como tal (una oferta con id «oferta» tapaba
// «Ofertas» en todo el menú, 15-nov).
const GENERICOS = new Set(['oferta', 'ofertas', 'tienda', 'tiendas', 'producto', 'productos', 'anuncio', 'anuncios', 'campaña', 'campañas',
  'conjunto', 'conjuntos', 'píxel', 'pixel', 'principal', 'completo', 'básico', 'basico', 'test', 'nueva', 'borrador', 'sin nombre', 'null', 'undefined']);

/** Textos de un dato: el texto, o el nombre y los identificadores de un objeto (id de la fan page, del píxel, del anuncio…). */
function textosDe(v, n = 0) {
  if (typeof v === 'string') return [v];
  if (typeof v === 'number' && Number.isFinite(v)) return [String(v)];
  if (!v || n > 3) return [];
  if (Array.isArray(v)) return v.flatMap((x) => textosDe(x, n + 1));
  if (typeof v === 'object') return [v.nombre, v.id, v.page_id, v.creativo_id].flatMap((x) => (x === undefined || x === null ? [] : textosDe(x, n + 1)));
  return [];
}

/** Variantes de una carpeta de trabajo que también delatan el tema: «ofertas/_borrador-oferta-a» → _borrador-oferta-a,
 *  mx-arte-colorear, arte-colorear y «arte colorear». Carpetas de sistema («_funnels», «_ejemplo»…) no cuentan. Pura. */
export function variantesCarpeta(ruta) {
  if (typeof ruta !== 'string') return [];
  const base = ruta.trim().replace(/\/+$/u, '').split('/').pop() || '';
  if (!base || (base.startsWith('_') && !base.startsWith('_borrador-'))) return [];
  const sinBorrador = base.replace(/^_borrador-/u, '');
  const sinPais = sinBorrador.replace(/^[a-z]{2}-(?=[a-z])/u, '');
  const out = [base, sinBorrador, sinPais];
  for (const x of [sinBorrador, sinPais]) if (x.includes('-')) out.push(x.replace(/-/gu, ' '));
  return [...new Set(out)];
}

/** Partes de un nombre de referente que también lo delatan solas: «ReferenteA · «Piccoli Maestri d'Arte» (Italia)» → ReferenteA, Piccoli Maestri d'Arte. */
function partesReferente(s) {
  if (typeof s !== 'string') return [];
  const sinPais = s.replace(/\s*\([^)]*\)\s*$/u, '');
  const partes = sinPais.split(/\s+[·|—–-]\s+/u).map((x) => x.replace(/^[«"“'‘]+|[»"”'’]+$/gu, '').trim());
  return [s, sinPais, ...partes];
}

/** Arma las listas de textos sensibles a partir de las ofertas de /negocio. Puro: devuelve {nombres, productos, anuncios, referentes}. */
export function terminosDeOfertas(ofertas) {
  const t = { nombres: [], productos: [], anuncios: [], referentes: [] };
  for (const o of Array.isArray(ofertas) ? ofertas : []) {
    if (!o || typeof o !== 'object') continue;
    const f = o.ficha || {};
    t.nombres.push(o.nombre, o.id, ...textosDe(f.fan_page), ...textosDe(f.pixel), ...textosDe(f.cuenta_publicitaria), f.expediente, f.carpeta_trabajo,
      ...variantesCarpeta(f.carpeta_trabajo));
    for (const x of Array.isArray(f.tiendas) ? f.tiendas : []) if (x) t.nombres.push(x.nombre, x.slug, x.url);
    for (const s of o.tiendas || []) t.nombres.push(s);
    t.productos.push(f.producto, o.backend && o.backend.nota, ...((o.backend && o.backend.upsells) || []).map((u) => u && u.nombre));   // la nota nombra los productos con otras palabras
    for (const c of Array.isArray(f.campanas) ? f.campanas : []) {
      if (!c) continue;
      t.anuncios.push(c.nombre, c.id, ...textosDe(c.conjuntos), ...textosDe(c.anuncios));
    }
    for (const a of [...((o.anuncios && o.anuncios.lista) || []), ...((o.anuncios && o.anuncios.top) || [])]) if (a) t.anuncios.push(...textosDe(a), a.conjunto, ...textosDe(a.conjuntos), ...textosDe(a.ids));
    for (const r of o.renovaciones || []) if (r) t.anuncios.push(r.conjunto);
    t.referentes.push(...textosDe(f.referente).flatMap(partesReferente), f.landing_original,
      ...textosDe(f.referente_paises && f.referente_paises.paginas).flatMap(partesReferente));
  }
  return depurar(t);
}

function depurar(t) {
  for (const k of Object.keys(t)) {
    t[k] = [...new Set(t[k].filter((s) => typeof s === 'string').map((s) => s.trim())
      .filter((s) => s.length >= LARGO_MINIMO && !GENERICOS.has(s.toLowerCase())))];
  }
  return t;
}

/** Términos de la lista de ofertas de /ofertas (el selector y las pantallas por etapa muestran la carpeta: «_borrador-oferta-f»). Pura. */
export function terminosDeCarpetas(ofertas) {
  const t = { nombres: [], productos: [], anuncios: [], referentes: [] };
  for (const o of Array.isArray(ofertas) ? ofertas : []) if (o && typeof o.oferta_id === 'string') t.nombres.push(...variantesCarpeta(o.oferta_id));
  return depurar(t);
}

// cada fuente (/negocio, /ofertas) registra lo suyo; el patrón usa la unión
const fuentes = new Map();

/** Registra los textos sensibles de una fuente («negocio» por defecto) y vuelve a pasar por todo el panel. */
export function fijarTerminos(t, fuente = 'negocio') {
  fuentes.set(fuente, t || {});
  for (const k of Object.keys(terminos)) terminos[k] = [...new Set([...fuentes.values()].flatMap((x) => (Array.isArray(x[k]) ? x[k] : [])))];
  patron = construirPatron(terminos);
  if (raiz) envolverTodo(raiz);
  aplicar();
}

/** RegExp con un grupo por categoría (lo más largo primero, sin distinguir mayúsculas). Pura, para las pruebas. */
export function construirPatron(t) {
  const grupos = [];
  ordenGrupos = [];
  const usados = new Set();
  // un grupo por término, el más largo primero entre TODAS las categorías: «MX | Oferta B | CBO» (anuncios) gana sobre
  // «Oferta B» (nombres); un texto repetido queda en la primera categoría que lo trae
  const todos = Object.entries(t || {}).flatMap(([k, l]) => (l || []).map((s) => [k, s])).sort((a, b) => b[1].length - a[1].length);
  // un término que contiene otro de otra categoría lleva las dos («MX | Oferta B | CBO» es anuncio Y nombre de oferta):
  // ocultar solo los nombres también lo difumina
  const minus = todos.map(([k, s]) => [k, s.toLowerCase()]);
  for (const [k, s] of todos) {
    const clave = s.toLowerCase();
    if (usados.has(clave)) continue;
    usados.add(clave);
    const cats = new Set([k]);
    for (const [k2, s2] of minus) if (k2 !== k && s2 !== clave && clave.includes(s2)) cats.add(k2);
    grupos.push(`(${escapar(s)})`);
    ordenGrupos.push([...cats]);
  }
  grupos.push(`(${ID_META})`); ordenGrupos.push(['anuncios']);
  grupos.push(`(${DINERO})`); ordenGrupos.push(['dinero']);
  return new RegExp(grupos.join('|'), 'giu');
}

/** Parte un texto en trozos [{texto, cats|null}] según el patrón (cats: categorías del trozo). Pura, para las pruebas. */
export function trocear(texto, re = patron) {
  const out = [];
  if (!re || typeof texto !== 'string' || !texto) return [{ texto, cats: null }];
  re.lastIndex = 0;
  let ult = 0; let m;
  while ((m = re.exec(texto)) !== null) {
    if (!m[0]) { re.lastIndex += 1; continue; }
    const g = m.slice(1).findIndex((x) => x !== undefined);
    if (m.index > ult) out.push({ texto: texto.slice(ult, m.index), cats: null });
    out.push({ texto: m[0], cats: ordenGrupos[g] || ['nombres'] });
    ult = m.index + m[0].length;
  }
  if (ult < texto.length) out.push({ texto: texto.slice(ult), cats: null });
  return out.length ? out : [{ texto, cats: null }];
}

/** Texto con «•••» en lugar de lo que está oculto (para `title` y el título de la pestaña). Pura. */
export function enmascarar(texto, cats = ocultas(), re = patron) {
  if (!cats.length || typeof texto !== 'string') return texto;
  return trocear(texto, re).map((p) => (p.cats && p.cats.some((c) => cats.includes(c)) ? MASCARA : p.texto)).join('');
}

// ───────────────────────── DOM ─────────────────────────

let raiz = null;
let observador = null;
let pendiente = false;
let tituloOriginal = null;
// <code> sí se recorre (15-nov): las rutas «ofertas/_borrador-…/estado.json» van en <code> y delataban el tema
const SALTAR = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'INPUT', 'SELECT', 'OPTION']);

function envolverTexto(nodo) {
  const padre = nodo.parentNode;
  if (!padre || !patron || SALTAR.has(padre.nodeName) || (padre.classList && padre.classList.contains('oc'))) return;
  const trozos = trocear(nodo.nodeValue);
  if (trozos.length === 1 && !trozos[0].cats) return;
  if (padre.namespaceURI === 'http://www.w3.org/2000/svg') {   // dentro de un gráfico no hay <span>: se marca el <text> entero
    const cats = [...new Set(trozos.flatMap((p) => p.cats || []))];
    for (const c of cats) padre.classList.add('oc-svg', `oc--${c}`);
    return;
  }
  const doc = nodo.ownerDocument;
  const frag = doc.createDocumentFragment();
  for (const p of trozos) {
    if (!p.cats) { frag.appendChild(doc.createTextNode(p.texto)); continue; }
    const s = doc.createElement('span');
    s.className = ['oc', ...p.cats.map((c) => `oc--${c}`)].join(' ');
    s.textContent = p.texto;
    frag.appendChild(s);
  }
  padre.replaceChild(frag, nodo);
}

function envolverTodo(n) {
  if (!n || !patron) return;
  if (n.nodeType === 3) { envolverTexto(n); return; }
  if (n.nodeType !== 1 && n.nodeType !== 11) return;
  if (SALTAR.has(n.nodeName) || (n.classList && n.classList.contains('oc'))) return;
  const doc = n.ownerDocument || n;
  const camino = doc.createTreeWalker(n, 4 /* NodeFilter.SHOW_TEXT */);
  const textos = [];
  while (camino.nextNode()) textos.push(camino.currentNode);
  for (const t of textos) envolverTexto(t);
}

/** `title` con «•••» mientras haya algo oculto; el original queda en data-oc-titulo y vuelve al apagar. */
function taparTitulos(base) {
  if (!base || !base.querySelectorAll) return;
  const cats = ocultas();
  for (const e of base.querySelectorAll('[title], [data-oc-titulo]')) {
    const original = e.getAttribute('data-oc-titulo') ?? e.getAttribute('title');
    const nuevo = enmascarar(original, cats);
    if (nuevo !== original) {
      e.setAttribute('data-oc-titulo', original);
      if (e.getAttribute('title') !== nuevo) e.setAttribute('title', nuevo);
    } else if (e.hasAttribute('data-oc-titulo')) {
      e.setAttribute('title', original);
      e.removeAttribute('data-oc-titulo');
    }
  }
}

/** Opciones de un <select> (no admiten <span> ni difuminado): su texto con «•••»; el original queda en data-oc-texto. */
function taparOpciones(base) {
  if (!base || !base.querySelectorAll) return;
  const cats = ocultas();
  for (const op of base.querySelectorAll('option')) {
    const original = op.getAttribute('data-oc-texto') ?? op.textContent;
    const nuevo = enmascarar(original, cats);
    if (nuevo !== original) {
      op.setAttribute('data-oc-texto', original);
      if (op.textContent !== nuevo) op.textContent = nuevo;
    } else if (op.hasAttribute('data-oc-texto')) {
      op.textContent = original;
      op.removeAttribute('data-oc-texto');
    }
  }
}

/** Enlaces cuya dirección nombra algo oculto: href con «•••» (la barra de estado no lo delata); el destino real queda en data-oc-href. */
function taparEnlaces(base) {
  if (!base || !base.querySelectorAll) return;
  const cats = ocultas();
  for (const a of base.querySelectorAll('a[href], a[data-oc-href]')) {
    const original = a.getAttribute('data-oc-href') ?? a.getAttribute('href');
    if (!original || original.startsWith('#')) continue;   // las direcciones internas ya usan ~N
    let legible = original;
    try { legible = decodeURIComponent(original); } catch (_) { /* queda como está */ }
    const nuevo = enmascarar(legible, cats);
    if (nuevo !== legible) {
      a.setAttribute('data-oc-href', original);
      const tapado = `#oculto:${nuevo.replace(/[^\w•.:/-]+/gu, '-')}`;
      if (a.getAttribute('href') !== tapado) a.setAttribute('href', tapado);
    } else if (a.hasAttribute('data-oc-href')) {
      a.setAttribute('href', original);
      a.removeAttribute('data-oc-href');
    }
  }
}

/** Clic en un enlace tapado: abre el destino real (igual que si no estuviera tapado). */
function alClicEnlace(ev) {
  const a = ev.target && ev.target.closest ? ev.target.closest('a[data-oc-href]') : null;
  if (!a) return;
  ev.preventDefault();
  const destino = a.getAttribute('data-oc-href');
  const nueva = a.getAttribute('target') === '_blank' || ev.metaKey || ev.ctrlKey || ev.button === 1;
  if (nueva) globalThis.open(destino, '_blank', 'noopener,noreferrer');
  else globalThis.location.assign(destino);
}

function taparPestana() {
  const doc = globalThis.document;
  if (!doc) return;
  const actual = doc.title;
  if (tituloOriginal !== null && actual === enmascarar(tituloOriginal)) return;
  tituloOriginal = actual;
  const nuevo = enmascarar(actual);
  if (nuevo !== actual) doc.title = nuevo;
}

/** Pone en <html> las categorías ocultas y tapa títulos y pestaña. */
export function aplicar() {
  const doc = globalThis.document;
  if (!doc || !doc.documentElement) return;
  const cats = ocultas();
  if (cats.length) doc.documentElement.setAttribute('data-ocultar', cats.join(' '));
  else doc.documentElement.removeAttribute('data-ocultar');
  taparTitulos(doc.body);
  taparEnlaces(doc.body);
  taparOpciones(doc.body);
  taparPestana();
}

/** Arranca el observador sobre el <body> (páginas, menú, ventanas y globos de ayuda). Una sola vez. */
export function instalar(ui) {
  const doc = globalThis.document;
  if (!doc || observador) return;
  if (ui && typeof ui.instalarEstilos === 'function') ui.instalarEstilos('ocultar', CSS_OCULTAR);
  const p = leerPreferencia();
  activo = p.activo;
  elegidas = new Set(p.elegidas);
  raiz = doc.body;
  const MO = globalThis.MutationObserver;
  if (typeof MO === 'function') {
    observador = new MO((cambios) => {
      for (const c of cambios) {
        if (c.type === 'characterData') envolverTexto(c.target);
        else for (const n of c.addedNodes) envolverTodo(n);
      }
      if (!pendiente) {   // títulos y pestaña: una vez por cuadro
        pendiente = true;
        // setTimeout y no requestAnimationFrame: en una pestaña de fondo el cuadro no llega y los títulos quedarían sin tapar
        setTimeout(() => { pendiente = false; taparTitulos(doc.body); taparEnlaces(doc.body); taparOpciones(doc.body); taparPestana(); }, 30);
      }
    });
    observador.observe(doc.body, { childList: true, subtree: true, characterData: true });
    const cab = doc.querySelector('head > title');
    if (cab) observador.observe(cab, { childList: true, characterData: true, subtree: true });
  }
  doc.addEventListener('click', alClicEnlace, true);
  doc.addEventListener('auxclick', alClicEnlace, true);
  envolverTodo(doc.body);
  aplicar();
}

// ───────────────────────── botón con casillas ─────────────────────────

/** Botón «Ocultar info» / «Info oculta» con su menú de casillas (como el de Impultienda). Recibe `ui`. */
export function botonOcultar(ui, { icono } = {}) {
  const { el } = ui;
  const ico = (n, t = 15) => (typeof icono === 'function' ? icono(n, { tam: t }) : ui.icono(n, { tam: t }));
  const texto = el('span', { class: 'oc-boton__texto' });
  const boton = el('button', { type: 'button', class: 'btn oc-boton', 'aria-haspopup': 'true', 'aria-expanded': 'false' });
  const menu = el('div', { class: 'oc-menu', role: 'menu', hidden: true });
  const caja = el('div', { class: 'oc-caja' }, boton, menu);

  function pintar() {
    const on = activo && elegidas.size > 0;
    caja.classList.toggle('oc-caja--on', on);
    ui.limpiar(boton);
    for (const n of [ico('ojo'), texto, ico('chevron-abajo', 13)]) boton.appendChild(n);
    texto.textContent = on ? 'Info oculta' : 'Ocultar info';
    boton.title = on ? `Ocultando: ${CATEGORIAS.filter((c) => elegidas.has(c.clave)).map((c) => c.texto.toLowerCase()).join(', ')}` : 'Difumina lo que elijas para grabar la pantalla';
    ui.limpiar(menu);
    const interruptor = el('label', { class: 'oc-menu__fila oc-menu__fila--principal' },
      el('input', { type: 'checkbox', checked: activo ? true : null, onchange: (ev) => fijar({ activo: ev.target.checked }) }),
      el('span', null, el('strong', null, 'Ocultar info'), el('span', { class: 'oc-menu__ayuda' }, 'Para grabar o compartir pantalla')));
    menu.appendChild(interruptor);
    menu.appendChild(el('div', { class: 'oc-menu__sep', role: 'separator' }));
    for (const c of CATEGORIAS) {
      menu.appendChild(el('label', { class: ['oc-menu__fila', !activo && 'oc-menu__fila--apagada'] },
        el('input', { type: 'checkbox', checked: elegidas.has(c.clave) ? true : null,
          onchange: (ev) => { const s = new Set(elegidas); if (ev.target.checked) s.add(c.clave); else s.delete(c.clave); fijar({ elegidas: [...s], activo: activo || ev.target.checked }); } }),
        el('span', null, c.texto, el('span', { class: 'oc-menu__ayuda' }, c.ayuda))));
    }
    menu.appendChild(el('p', { class: 'oc-menu__pie' }, 'Las banderas y los colores siempre se ven. Se recuerda en este navegador.'));
  }
  function abrir(si) {
    menu.hidden = !si;
    boton.setAttribute('aria-expanded', String(si));
  }
  boton.addEventListener('click', (ev) => { ev.stopPropagation(); abrir(menu.hidden); });
  menu.addEventListener('click', (ev) => ev.stopPropagation());
  // la página se repinta seguido: cada botón se da de baja solo cuando ya no está en la pantalla
  const doc = globalThis.document;
  let quitar = () => {};
  const vivo = () => { if (caja.isConnected === false && montado) { quitar(); return false; } return true; };
  let montado = false;
  const alClic = () => { if (vivo()) abrir(false); };
  const alTecla = (ev) => { if (vivo() && ev.key === 'Escape' && !menu.hidden) { abrir(false); boton.focus(); } };
  if (doc && doc.addEventListener) { doc.addEventListener('click', alClic); doc.addEventListener('keydown', alTecla); }
  const baja = alCambiar(() => { if (vivo()) pintar(); });
  quitar = () => { baja(); if (doc && doc.removeEventListener) { doc.removeEventListener('click', alClic); doc.removeEventListener('keydown', alTecla); } };
  setTimeout(() => { montado = true; }, 0);
  pintar();
  return caja;
}

export const CSS_OCULTAR = `
:root[data-ocultar~="nombres"] .oc--nombres, :root[data-ocultar~="productos"] .oc--productos, :root[data-ocultar~="anuncios"] .oc--anuncios,
:root[data-ocultar~="referentes"] .oc--referentes, :root[data-ocultar~="dinero"] .oc--dinero {
  filter: blur(6px); -webkit-user-select: none; user-select: none; border-radius: 4px; transition: filter .15s ease;
}
:root[data-ocultar~="nombres"] .oc-svg.oc--nombres, :root[data-ocultar~="dinero"] .oc-svg.oc--dinero, :root[data-ocultar~="anuncios"] .oc-svg.oc--anuncios,
:root[data-ocultar~="productos"] .oc-svg.oc--productos, :root[data-ocultar~="referentes"] .oc-svg.oc--referentes { filter: blur(4px); }
/* imágenes y creativos: toda foto, video, iframe o lienzo; clip-path recorta el difuminado para que no se derrame fuera de su caja */
:root[data-ocultar~="imagenes"] :is(img, video, iframe, canvas, picture, object, embed, svg image) { filter: blur(14px) saturate(.6); clip-path: inset(0); }
:root[data-ocultar~="imagenes"] .ng-img, :root[data-ocultar~="imagenes"] .modal img { filter: blur(32px) saturate(.5); }   /* la imagen grande: más fuerte */
.oc-caja { position: relative; }
.oc-boton { display: inline-flex; align-items: center; gap: 6px; }
.oc-caja--on .oc-boton { background: var(--aviso-bg); color: var(--aviso); border-color: var(--aviso); font-weight: 650; }
.oc-menu { position: absolute; right: 0; top: calc(100% + 6px); z-index: 60; width: 300px; max-width: calc(100vw - 24px); padding: 6px; border-radius: var(--r-3);
  border: 1px solid var(--borde-fuerte); background: var(--sup); box-shadow: 0 12px 32px rgba(0,0,0,.28); display: grid; gap: 2px; }
.oc-menu[hidden] { display: none; }
.oc-menu__fila { display: grid; grid-template-columns: auto 1fr; gap: 10px; align-items: start; padding: 8px 10px; border-radius: var(--r-2); cursor: pointer; font-size: var(--t-sm); }
.oc-menu__fila:hover { background: var(--sup-2); }
.oc-menu__fila input { margin-top: 2px; width: 16px; height: 16px; accent-color: var(--acento); }
.oc-menu__fila > span { display: grid; gap: 1px; }
.oc-menu__fila--apagada { opacity: .6; }
.oc-menu__ayuda { color: var(--txt-3); font-size: var(--t-xs); }
.oc-menu__sep { height: 1px; background: var(--borde); margin: 4px 6px; }
.oc-menu__pie { margin: 4px 10px 6px; color: var(--txt-3); font-size: var(--t-xs); }
@media (max-width: 640px) { .oc-boton__texto { display: none; } }
`;
