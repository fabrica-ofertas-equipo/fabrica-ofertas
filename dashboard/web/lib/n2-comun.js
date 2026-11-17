// lib/n2-comun.js — piezas puras compartidas por Fábrica, Jurado, Países y Poscompra (sin DOM, sin red propia: la API entra por parámetro).
//
// REGLA: todo lo que sale de un archivo (ofertas/<id>/…) es DATO NO CONFIABLE. Aquí solo se normaliza (tipos, longitudes, listas); la pantalla lo
// pinta siempre con textContent (ui.el). Nada de lo que se lee se interpreta como HTML ni se ejecuta.

export const RE_OFERTA_ID = /^(OF-\d{6}-\d{2}|_[a-z0-9][a-z0-9_-]{0,31})$/;
/** Tope de ofertas que una pantalla lee a la vez (cada una cuesta 2-4 peticiones locales). */
export const MAX_OFERTAS = 10;
export const MAX_TEXTO = 400;
const RE_CONTROL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g;

export const esObj = (x) => x !== null && typeof x === 'object' && !Array.isArray(x);
export const lista = (x) => (Array.isArray(x) ? x : []);

/** Texto corto y limpio (sin controles) de un string o número; cualquier otra cosa → null. */
export function texto(x, max = MAX_TEXTO) {
  if (typeof x === 'number' && Number.isFinite(x)) return String(x);
  if (typeof x !== 'string') return null;
  const t = x.replace(RE_CONTROL, '').trim();
  if (!t) return null;
  return t.length > max ? `${t.slice(0, max - 1)}…` : t;
}

/** Número finito de un número o de un string numérico («0.61», «0,61»); si no, null. */
export function numero(x) {
  if (typeof x === 'number') return Number.isFinite(x) ? x : null;
  if (typeof x === 'string' && /^-?\d+([.,]\d+)?$/.test(x.trim())) return Number(x.trim().replace(',', '.'));
  return null;
}

/** Entero ≥ 0 o null. */
export function entero(x) {
  const n = numero(x);
  return n !== null && Number.isInteger(n) && n >= 0 ? n : null;
}

/** Sí/no tolerante: true/false, 1/0, «sí/si/yes/true», «no/false». Otra cosa → null. */
export function sino(x) {
  if (typeof x === 'boolean') return x;
  if (x === 1 || x === 0) return x === 1;
  if (typeof x !== 'string') return null;
  const t = x.trim().toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  if (['si', 'yes', 'true', 'y', 'compra', 'comprarian', 'aprueba', 'aprobado'].includes(t)) return true;
  if (['no', 'false', 'n', 'no compra', 'rechaza', 'rechazado'].includes(t)) return false;
  return null;
}

/** Normaliza un texto para comparar (minúsculas, sin tildes). */
export const plano = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

/** Filas de /ofertas con identificador válido, sin repetir y con tope. → [{id, familia, demo, fase, nivel, interno}] */
export function ofertasValidas(filas, max = MAX_OFERTAS) {
  const vistas = new Set();
  const salida = [];
  for (const f of lista(filas)) {
    if (!esObj(f) || typeof f.oferta_id !== 'string' || !RE_OFERTA_ID.test(f.oferta_id) || vistas.has(f.oferta_id)) continue;
    vistas.add(f.oferta_id);
    salida.push({
      id: f.oferta_id,
      interno: texto(f.oferta_id_estado, 40),
      familia: texto(f.familia_id, 40),
      demo: f.demo === true || f.oferta_id.startsWith('_'),
      fase: texto(f.fase, 40),
      nivel: texto(f.nivel, 8),
    });
    if (salida.length >= max) break;
  }
  return salida;
}

/** Oferta en foco: la elegida en esta pantalla, si no la activa del panel, si no la primera real, si no la primera. */
export function elegirFoco(ofertas, { previa = null, activa = null } = {}) {
  const ids = lista(ofertas).map((o) => (esObj(o) ? o.id : o)).filter((x) => typeof x === 'string');
  for (const c of [previa, activa]) if (typeof c === 'string' && ids.includes(c)) return c;
  const real = lista(ofertas).find((o) => esObj(o) && !o.demo);
  return real ? real.id : (ids[0] || null);
}

/** «OF-202611-01 (demo)». */
export function etiquetaOferta(o) {
  if (!esObj(o)) return '';
  return `${o.id}${o.demo ? ' (demo)' : ''}`;
}

// ───────────────────────── lectura por la API (la API entra por parámetro) ─────────────────────────

/** Llama a `api.sobre` y devuelve SIEMPRE un objeto (nunca lanza): {ok, datos, fuente, generado_en, vacio, avisos, demo, error}. */
export async function leer(api, ruta, params) {
  try {
    const f = api && (api.sobre || api.getSobre);
    if (typeof f !== 'function') throw new Error('La conexión con el panel no está disponible.');
    const s = await f.call(api, ruta, params);
    return {
      ok: true, datos: s && s.datos !== undefined ? s.datos : null, fuente: Array.isArray(s && s.fuente) ? s.fuente : [], generado_en: (s && s.generado_en) || null,
      vacio: Boolean(s && s.vacio === true), avisos: Array.isArray(s && s.avisos) ? s.avisos : [], demo: Boolean(s && s.demo === true), error: null,
    };
  } catch (error) {
    return { ok: false, datos: null, fuente: [], generado_en: null, vacio: false, avisos: [], demo: false, error };
  }
}

/**
 * Convierte la respuesta de /oferta/<id>/archivo en un JSON: {estado:'ok'|'ausente'|'ilegible'|'truncado'|'error', dato, fuente, generado_en, error}.
 * Un archivo que falta es 'ausente' (no un error: es el estado normal mientras el motor no lo produce); uno cortado por el tope no se interpreta.
 */
export function jsonDeLectura(lec) {
  const base = { dato: null, fuente: (lec && lec.fuente) || [], generado_en: (lec && lec.generado_en) || null, error: (lec && lec.error) || null };
  if (!lec || !lec.ok) return { ...base, estado: 'error' };
  const d = lec.datos;
  if (lec.vacio || d === null || d === undefined) return { ...base, estado: 'ausente' };
  if (!esObj(d) || typeof d.contenido !== 'string') return { ...base, estado: 'ilegible' };
  if (d.truncado === true) return { ...base, estado: 'truncado' };
  try {
    const dato = JSON.parse(d.contenido);
    return { ...base, estado: 'ok', dato };
  } catch (_) {
    return { ...base, estado: 'ilegible' };
  }
}

/** Lee y parsea un JSON de ofertas/<id>/<ruta>. Nunca lanza. */
export async function leerJsonDeOferta(api, id, ruta) {
  if (!RE_OFERTA_ID.test(String(id))) return { estado: 'error', dato: null, fuente: [], generado_en: null, error: new Error('El identificador de la oferta no es válido.') };
  return jsonDeLectura(await leer(api, `/oferta/${encodeURIComponent(id)}/archivo`, { ruta }));
}

/** Ruta de un QA dentro de ofertas/<id>/ (solo qa/<nombre>.json con caracteres seguros) o null. */
export function rutaQaSegura(ruta) {
  return typeof ruta === 'string' && /^qa\/[A-Za-z0-9_.-]+\.json$/.test(ruta) && !ruta.includes('..') ? ruta : null;
}

/** El QA más reciente de una lista [{archivo}] que empiece por `prefijo` (qa/d6-v2.json gana a qa/d6-v10? No: gana la versión numérica mayor). */
export function ultimoQa(archivos, prefijo) {
  let mejor = null;
  let mejorN = -1;
  for (const a of lista(archivos)) {
    const ruta = rutaQaSegura(esObj(a) ? a.archivo : a);
    if (!ruta || !ruta.startsWith(`qa/${prefijo}`)) continue;
    const m = /-v(\d+)\.json$/.exec(ruta);
    const n = m ? Number(m[1]) : 0;
    if (n >= mejorN) { mejor = ruta; mejorN = n; }
  }
  return mejor;
}

// ───────────────────────── imágenes ─────────────────────────

export const DATA_IMG = /^data:image\/(png|jpeg|gif|webp);base64,[A-Za-z0-9+/=]+$/;
/** ¿Es una data-URL de imagen que se puede poner en un <img>? (SVG fuera: puede llevar scripts en otros contextos). */
export const dataImagenSegura = (s) => typeof s === 'string' && s.length < 1_500_000 && DATA_IMG.test(s);

// ───────────────────────── etapas de una oferta ─────────────────────────

/** Etapa `id` ('D6') del detalle de /oferta/<id>, normalizada, o null. */
export function etapaDe(detalle, id) {
  const e = esObj(detalle) ? lista(detalle.etapas).find((x) => esObj(x) && x.id === id) : null;
  if (!e) return null;
  return {
    id,
    nombre: texto(e.nombre, 80),
    estado: texto(e.estado, 30),
    gate: texto(e.gate, 4),
    gatePendiente: e.gate_pendiente === true,
    obsoleta: e.obsoleta === true,
    artefactos: lista(e.artefactos).filter((a) => esObj(a) && typeof a.ruta === 'string'),
    qa: lista(e.qa).filter((q) => esObj(q) && typeof q.archivo === 'string'),
  };
}

/** Mercado normalizado de /oferta/<id> (`mercado.json`): idioma, países, moneda y lo que declara de impuestos/consumo/idioma legal. */
export function mercadoDe(detalle) {
  const m = esObj(detalle) && esObj(detalle.mercado) ? detalle.mercado : null;
  if (!m) return null;
  const fiscal = esObj(m.fiscal) ? m.fiscal : {};
  const expo = esObj(fiscal.exposicion_aceptada) ? fiscal.exposicion_aceptada : {};
  const consumo = esObj(m.consumo) ? m.consumo : {};
  const rev = esObj(m.revision_linguistica) ? m.revision_linguistica : {};
  const pagos = esObj(m.metodos_pago) ? m.metodos_pago : {};
  return {
    locale: texto(m.locale, 16),
    paises: lista(m.paises_segmentacion).map((p) => texto(p, 4)).filter(Boolean).slice(0, 40),
    moneda: texto(m.moneda_cobro, 4),
    decision: texto(m.estado_decision, 30),
    familia: texto(m.familia_id, 40),
    varianteDe: texto(m.variante_de, 40),
    aprobadoPor: m.aprobado_por ? (texto(esObj(m.aprobado_por) ? m.aprobado_por.id : m.aprobado_por, 40) || 'sí') : null,
    requiereGateH: sino(m.requiere_gate_h),
    primerLanzamiento: sino(m.primer_lanzamiento_en_locale),
    metodos: lista(pagos.activos).map((x) => texto(x, 30)).filter(Boolean),
    metodosFase: texto(pagos.fase, 60),
    fiscal: {
      regimen: texto(fiscal.regimen, 30),
      firmadaPor: esObj(expo.firmada_por) ? texto(expo.firmada_por.id, 40) : null,
      paisesFirmados: lista(expo.paises).map((p) => texto(p, 4)).filter(Boolean),
    },
    consumo: {
      desistimientoDias: entero(consumo.desistimiento_dias),
      botonArrepentimiento: sino(consumo.boton_arrepentimiento),
      consentimientoCookies: sino(consumo.consentimiento_cookies),
      leyPrivacidad: texto(consumo.ley_privacidad, 40),
    },
    idiomaLegal: { obligacion: sino(rev.obligacion_legal_idioma), revisorNativo: sino(rev.revisor_nativo) },
  };
}

/** Tono del estado de una fase de oferta (solo para elegir el chip). */
export const FASES_VALIDAS = Object.freeze(['validada', 'escalando']);
export const esMadreValidada = (fase) => FASES_VALIDAS.includes(String(fase || ''));

/** Lista de ofertas (GET /ofertas); si la API falla usa la que ya tiene el shell. → {lec, ofertas:[{id, interno, familia, demo, fase, nivel}]} */
export async function cargarOfertas(ctx) {
  const lec = await leer(ctx.api, '/ofertas');
  let filas = lec.ok && Array.isArray(lec.datos) ? lec.datos : null;
  if (!filas && ctx.estado && Array.isArray(ctx.estado.ofertas)) filas = ctx.estado.ofertas;
  return { lec, ofertas: ofertasValidas(filas) };
}

/** Detalle de una oferta (GET /oferta/<id>) → {lec, detalle|null}. */
export async function cargarDetalle(api, id) {
  const lec = await leer(api, `/oferta/${encodeURIComponent(id)}`);
  return { lec, detalle: lec.ok && esObj(lec.datos) ? lec.datos : null };
}

/** Une las rutas de `fuente` de varias lecturas, sin repetir. */
export function unirFuentes(...lecturas) {
  const vistas = new Set();
  for (const l of lecturas) for (const f of lista(l && l.fuente)) if (typeof f === 'string') vistas.add(f);
  return [...vistas];
}
