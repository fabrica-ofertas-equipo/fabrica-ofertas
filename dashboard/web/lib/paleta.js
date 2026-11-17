// paleta.js — lógica PURA de la paleta de comandos (Ctrl/⌘+K): normalización, puntuación, búsqueda, agrupado y navegación con teclado.
// Sin DOM, sin dependencias: se prueba con `node --test`. La vista (app.js) pinta lo que esto devuelve.
//
// Entrada de la paleta: {id, tipo: 'pantalla'|'oferta'|'skill'|'accion', grupo, titulo, detalle?, ruta?, accion?, icono?, atajo?: string[], palabras?: string[]}
//   ruta   hash al que saltar ('#/ofertas'); accion = clave de una acción del shell (la ejecuta app.js: 'tecnico', 'densidad', 'tema', 'atajos', 'pausar', …).
//   palabras  sinónimos de todos los días con los que también se encuentra («qué hago», «plata», «página de venta»): se buscan aunque no estén en el título.

/** Minúsculas y sin tildes: «Campañas» → «campanas». */
export function normalizar(s) {
  return String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

function esSubsecuencia(q, texto) {
  let i = 0;
  for (const c of texto) { if (c === q[i]) i += 1; if (i === q.length) return true; }
  return q.length === 0;
}

/** Puntos de una palabra de la consulta contra una entrada (0 = no coincide). Prefijo > inicio de palabra > contiene > alias/detalle > subsecuencia. */
function puntosPalabra(p, tit, resto, alias) {
  if (tit.startsWith(p)) return 100;
  if (tit.split(/[^a-z0-9]+/).some((w) => w.startsWith(p))) return 80;
  if (tit.includes(p)) return 60;
  if (alias.includes(p)) return 45;
  if (resto.includes(p)) return 35;
  if (p.length >= 2 && esSubsecuencia(p, tit)) return 15;
  return 0;
}

/** Puntuación de una entrada para una consulta: 0 (sin consulta: todas valen), -1 (no coincide) o > 0 (más alto = mejor). Todas las palabras deben coincidir. */
export function puntuar(consulta, entrada) {
  const q = normalizar(consulta).trim();
  if (!q) return 0;
  const tit = normalizar(entrada && entrada.titulo);
  const alias = normalizar(((entrada && entrada.palabras) || []).join(' '));
  const resto = normalizar(`${(entrada && entrada.detalle) || ''} ${(entrada && entrada.grupo) || ''}`);
  const palabras = q.split(/\s+/).filter(Boolean);
  let total = 0;
  for (const p of palabras) {
    const pts = puntosPalabra(p, tit, resto, alias);
    if (pts === 0) return -1;
    total += pts;
  }
  const media = total / palabras.length;
  const bonus = tit === q ? 40 : tit.startsWith(q) ? 15 : 0;
  return media + bonus - Math.min(tit.length, 60) / 200; // a igualdad, el título más corto primero
}

/** Filtra y ordena. Sin consulta devuelve las entradas en su orden (hasta `limite`). Estable. No muta. */
export function buscar(entradas, consulta, { limite = 40 } = {}) {
  const lista = Array.isArray(entradas) ? entradas : [];
  const q = normalizar(consulta).trim();
  if (!q) return lista.slice(0, limite);
  return lista
    .map((e, i) => ({ e, i, p: puntuar(q, e) }))
    .filter((x) => x.p > 0)
    .sort((a, b) => b.p - a.p || a.i - b.i)
    .slice(0, limite)
    .map((x) => x.e);
}

/** Agrupa preservando el orden de aparición: [{grupo, items:[{...entrada, indice}]}]; `indice` es la posición en la lista plana. */
export function agruparPorGrupo(resultados) {
  const grupos = [];
  const porNombre = new Map();
  (Array.isArray(resultados) ? resultados : []).forEach((e, indice) => {
    const nombre = (e && e.grupo) || 'Resultados';
    if (!porNombre.has(nombre)) { const g = { grupo: nombre, items: [] }; porNombre.set(nombre, g); grupos.push(g); }
    porNombre.get(nombre).items.push({ ...e, indice });
  });
  return grupos;
}

/** Selección tras una tecla: flechas (circular), Inicio, Fin, RePág/AvPág (±5, sin dar la vuelta). Otra tecla → `i`. n = 0 → -1. */
export function moverSeleccion(i, n, tecla) {
  if (!(n > 0)) return -1;
  switch (tecla) {
    case 'ArrowDown': return (i + 1) % n;
    case 'ArrowUp': return (i - 1 + n) % n;
    case 'Home': return 0;
    case 'End': return n - 1;
    case 'PageDown': return Math.min(i + 5, n - 1);
    case 'PageUp': return Math.max(i - 5, 0);
    default: return i;
  }
}

const recorta = (t, n) => { const s = String(t ?? ''); return s.length > n ? `${s.slice(0, n - 1)}…` : s; };

/**
 * Nombre de un grupo del menú tal como se ve en el sidebar: «3 · Jurado» si es una de las seis piezas del sistema (`pieza` = 1..6), o solo «El sistema».
 * Es la única fuente de ese rótulo (sidebar, detalle de la paleta, ayuda de atajos), así que el literal `meta.grupo` de las páginas no lleva número.
 */
export function etiquetaGrupo(g) {
  const nombre = String((g && g.grupo) ?? '');
  const n = Number(g && g.pieza);
  return Number.isInteger(n) && n > 0 ? `${n} · ${nombre}` : nombre;
}

/**
 * Construye las entradas de la paleta.
 *  nav      [{grupo, pieza?, buscar?, items:[{ruta, titulo, icono, desc, atajo?, buscar?}]}]   (app.NAV; se busca también por el nombre y el número de la pieza, y por los sinónimos del grupo y de la pantalla)
 *  ofertas  [{oferta_id, demo?, fase?, nivel?}]                        (estado.ofertas)
 *  skills   [{slug, version?, estado?, descripcion?}]                  (GET /skills, las guías de trabajo de cada IA; puede faltar)
 *  acciones [{id, titulo, detalle?, icono?, accion, palabras?}]        (las del shell)
 *  opciones {tecnico: bool}  → incluye la galería de componentes solo en modo técnico
 */
export function construirEntradas({ nav = [], ofertas = [], skills = [], acciones = [] } = {}, { tecnico = false } = {}) {
  const salida = [];
  for (const g of nav) {
    const etiqueta = etiquetaGrupo(g);
    const n = Number(g.pieza);
    // por qué se encuentra una pantalla: el nombre del grupo, «pieza 3», «3 · Jurado», las palabras del grupo y la ruta
    const delGrupo = [g.grupo, etiqueta, ...(Number.isInteger(n) && n > 0 ? [`pieza ${n}`] : []), ...(Array.isArray(g.buscar) ? g.buscar : [])];
    for (const it of g.items || []) {
      salida.push({ id: `pantalla:${it.ruta}`, tipo: 'pantalla', grupo: 'Pantallas', titulo: it.titulo, detalle: `${etiqueta} · ${recorta(it.desc, 90)}`, ruta: `#/${it.ruta}`, icono: it.icono, atajo: it.atajo ? ['g', it.atajo] : undefined, palabras: [...delGrupo, ...(Array.isArray(it.buscar) ? it.buscar : []), it.ruta] });
    }
  }
  for (const o of Array.isArray(ofertas) ? ofertas : []) {
    if (!o || !o.oferta_id) continue;
    // «en_test · N2» se lee «en test · nivel 2»
    const fase = o.fase ? String(o.fase).replace(/_/g, ' ') : null;
    const nivel = o.nivel ? String(o.nivel).replace(/^N([0-4])$/i, 'nivel $1') : null;
    const partes = [o.demo ? 'demo' : null, fase, nivel].filter(Boolean);
    salida.push({ id: `oferta:${o.oferta_id}`, tipo: 'oferta', grupo: 'Ofertas', titulo: String(o.oferta_id), detalle: partes.join(' · ') || 'Abrir la oferta', ruta: `#/oferta/${encodeURIComponent(o.oferta_id)}`, icono: 'caja', palabras: ['oferta', 'producto'] });
  }
  for (const s of Array.isArray(skills) ? skills : []) {
    if (!s || !s.slug) continue;
    salida.push({ id: `skill:${s.slug}`, tipo: 'skill', grupo: 'Guías de trabajo', titulo: String(s.slug), detalle: recorta(s.descripcion || [s.estado, s.version].filter(Boolean).join(' · ') || 'Abrir la guía de trabajo', 100), ruta: `#/skills?slug=${encodeURIComponent(s.slug)}`, icono: 'chispa', palabras: ['skill', 'skills', 'guía de trabajo', 'guias', 'agente', 'instrucciones'] });
  }
  for (const a of Array.isArray(acciones) ? acciones : []) {
    if (!a || !a.accion) continue;
    if (a.soloTecnico && !tecnico) continue;
    salida.push({ id: `accion:${a.id || a.accion}`, tipo: 'accion', grupo: 'Acciones', titulo: a.titulo, detalle: a.detalle, accion: a.accion, icono: a.icono || 'comando', atajo: a.atajo, palabras: a.palabras || [] });
  }
  return salida;
}
