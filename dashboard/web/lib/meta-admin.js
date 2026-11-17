// lib/meta-admin.js — lógica pura de #/meta («Campañas en Meta»): agrupa las filas por día en campañas, conjuntos o anuncios, filtra y
// calcula las métricas como el Administrador de anuncios. Sin DOM ni red; se prueba con node --test (tests/dashboard/test_web_meta.mjs).

export const METRICAS = ['gasto_usd', 'impresiones', 'alcance', 'clics_enlace', 'visitas_landing_meta', 'inicios_pago_meta', 'compras_meta',
  'valor_compras_meta_usd', 'vistas_3s', 'video_p25', 'video_p50', 'video_p75', 'video_p100', 'thruplay'];
export const NIVELES = [
  { clave: 'campanas', texto: 'Campañas', singular: 'campaña' },
  { clave: 'conjuntos', texto: 'Conjuntos de anuncios', singular: 'conjunto' },
  { clave: 'anuncios', texto: 'Anuncios', singular: 'anuncio' },
];
const ACTIVOS = new Set(['ACTIVE', 'IN_PROCESS', 'WITH_ISSUES', 'PENDING_REVIEW']);
export const esActivo = (estado) => ACTIVOS.has(String(estado || ''));

const div = (a, b, k = 1) => (b ? (k * a) / b : null);

/** Métricas derivadas de una suma (las mismas fórmulas que Meta). */
export function derivar(s) {
  const g = s.gasto_usd || 0;
  return {
    ...s,
    cpm: div(g, s.impresiones, 1000),
    ctr: div(s.clics_enlace, s.impresiones, 100),
    cpc: div(g, s.clics_enlace),
    costo_visita: div(g, s.visitas_landing_meta),
    tasa_pago: div(s.inicios_pago_meta, s.visitas_landing_meta, 100),
    costo_pago: div(g, s.inicios_pago_meta),
    tasa_compra: div(s.compras_meta, s.inicios_pago_meta, 100),
    cpa: div(g, s.compras_meta),
    roas: div(s.valor_compras_meta_usd, g),
    hook: s.vistas_3s ? div(s.vistas_3s, s.impresiones, 100) : null,
    retencion: s.vistas_3s ? div(s.video_p100, s.vistas_3s, 100) : null,
  };
}

const vacia = () => Object.fromEntries(METRICAS.map((k) => [k, 0]));
function sumar(acc, f) { for (const k of METRICAS) acc[k] += Number(f[k]) || 0; return acc; }

/** Índices de entidades por id. */
export function indices(d) {
  const camp = new Map((d.campanas || []).map((c) => [c.id, c]));
  const conj = new Map((d.conjuntos || []).map((s) => [s.id, s]));
  const anun = new Map((d.anuncios || []).map((a) => [a.id, a]));
  return { camp, conj, anun };
}

/** ¿Pasa la entidad los filtros? (país, oferta, estado, búsqueda y selección de la jerarquía) */
function pasa(ent, nivel, f, ix) {
  const campId = nivel === 'campanas' ? ent.id : ent.campana;
  const camp = ix.camp.get(campId) || {};
  if (f.paises && f.paises.length && !f.paises.includes(camp.mercado || '—')) return false;
  if (f.oferta && camp.oferta_id !== f.oferta) return false;
  if (f.campana && campId !== f.campana) return false;
  if (f.conjunto && nivel === 'anuncios' && ent.conjunto !== f.conjunto) return false;
  if (f.conjunto && nivel === 'conjuntos' && ent.id !== f.conjunto) return false;
  if (f.busqueda) {
    const q = f.busqueda.toLowerCase();
    if (!String(ent.nombre || '').toLowerCase().includes(q)) return false;
  }
  return true;
}

/**
 * Filas de la tabla para un nivel: una por entidad con sus métricas sumadas en el período.
 * f = {paises: [...], oferta, soloActivos, conGasto, busqueda, campana, conjunto}
 */
export function filasNivel(d, nivel, f = {}) {
  const ix = indices(d);
  const lista = nivel === 'campanas' ? d.campanas || [] : nivel === 'conjuntos' ? d.conjuntos || [] : d.anuncios || [];
  const sumas = new Map();
  for (const r of d.dias || []) {
    const a = ix.anun.get(r.id);
    if (!a) continue;
    const k = nivel === 'campanas' ? a.campana : nivel === 'conjuntos' ? a.conjunto : a.id;
    if (!k) continue;
    sumar(sumas.get(k) || sumas.set(k, vacia()).get(k), r);
  }
  const out = [];
  for (const ent of lista) {
    if (!pasa(ent, nivel, f, ix)) continue;
    const s = sumas.get(ent.id);
    const activo = esActivo(ent.estado);
    if (f.soloActivos && !activo && !(s && s.gasto_usd > 0)) continue;   // como Meta: lo que entregó en el período se ve aunque hoy esté pausado
    if (f.conGasto && !(s && s.gasto_usd > 0)) continue;
    const camp = ix.camp.get(nivel === 'campanas' ? ent.id : ent.campana) || {};
    out.push({
      ...derivar(s || vacia()), id: ent.id, nombre: ent.nombre, estado: ent.estado, activo,
      mercado: camp.mercado || null, oferta: camp.oferta || null, oferta_id: camp.oferta_id || null,
      presupuesto: nivel === 'campanas' ? ent.presupuesto ?? null : null, rol: nivel === 'campanas' ? ent.rol : null,
      inicio: nivel === 'campanas' ? ent.inicio ?? null : null,
      campana: nivel === 'campanas' ? ent.id : ent.campana, campana_nombre: camp.nombre || null,
      conjunto: nivel === 'anuncios' ? ent.conjunto : nivel === 'conjuntos' ? ent.id : null,
      conjunto_nombre: nivel === 'anuncios' ? (ix.conj.get(ent.conjunto) || {}).nombre || null : null,
      miniatura: ent.miniatura || null, video: Boolean(ent.video),
    });
  }
  return out.sort((x, y) => (y.gasto_usd || 0) - (x.gasto_usd || 0));
}

/** Total de las filas visibles (para la franja de arriba). */
export function total(filas) {
  return derivar(filas.reduce((acc, f) => sumar(acc, f), vacia()));
}

/** Países con cuántas campañas tiene cada uno (para los botones de filtro). */
export function paises(d) {
  const m = new Map();
  for (const c of d.campanas || []) {
    const k = c.mercado || '—';
    const x = m.get(k) || { codigo: k, campanas: 0, activas: 0 };
    x.campanas += 1;
    if (esActivo(c.estado)) x.activas += 1;
    m.set(k, x);
  }
  return [...m.values()].sort((a, b) => b.activas - a.activas || b.campanas - a.campanas || a.codigo.localeCompare(b.codigo));
}

/** Ofertas para el selector. */
export function ofertas(d) {
  const m = new Map();
  for (const c of d.campanas || []) if (c.oferta_id && !m.has(c.oferta_id)) m.set(c.oferta_id, { id: c.oferta_id, nombre: c.oferta, mercado: c.mercado });
  return [...m.values()].sort((a, b) => String(a.nombre).localeCompare(String(b.nombre)));
}

export const ESTADO_TEXTO = { ACTIVE: 'Activo', PAUSED: 'Pausado', CAMPAIGN_PAUSED: 'Campaña pausada', ADSET_PAUSED: 'Conjunto pausado', IN_PROCESS: 'En proceso',
  WITH_ISSUES: 'Con problemas', DISAPPROVED: 'Rechazado', PENDING_REVIEW: 'En revisión', ARCHIVED: 'Archivado', DELETED: 'Eliminado' };
export const estadoTexto = (e) => ESTADO_TEXTO[e] || (e ? String(e) : 'Sin dato');
