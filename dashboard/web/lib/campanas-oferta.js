// lib/campanas-oferta.js — lógica PURA de «Campañas en Meta» y «Línea de tiempo del presupuesto» en la ficha de cada oferta (#/negocio/<oferta>).
// Pedido del dueño (16-nov): «ver cada campaña, conjunto y anuncios como en Meta, con todo lo que le podemos agregar desde el back office…
// y ver qué se subió, qué se bajó, un timeline del presupuesto… para monitorear al sistema: qué se está haciendo, qué se dejó de hacer, por qué».
// Datos: GET /api/meta?oferta=<id> (dashboard/meta_admin.py: armar + filtrar_oferta + escala_oferta). Sin DOM ni red; se prueba con
// node --test (tests/dashboard/test_web_campanas_oferta.mjs).

import { filasNivel, total } from './meta-admin.js';

export const ROLES = { principal: 'CBO test', pocket: 'Pocket 1-1-1', test_variaciones: 'Variaciones' };
export const rolTexto = (r) => ROLES[r] || (r ? String(r).replace(/_/g, ' ') : null);

/** Umbrales de la escala por campaña (reglas.json → escala.por_campana): para pintar el ROAS con AOV. */
export const UMBRAL = { surf: 1.8, bajar: 1.5 };
export function tonoRoasAov(x) {
  if (typeof x !== 'number' || !Number.isFinite(x)) return null;
  return x >= UMBRAL.surf ? 'ok' : x < UMBRAL.bajar ? 'error' : 'aviso';
}

const conAov = (f, aov) => ({ ...f, roas_aov: aov && f.gasto_usd > 0 ? (f.compras_meta * aov) / f.gasto_usd : null });

/** Campañas → conjuntos → anuncios con las métricas del período, el ROAS con AOV y la última decisión de la escala. */
export function arbol(d, aov) {
  const ultima = (d && d.escala && d.escala.ultima) || {};
  const conjs = filasNivel(d, 'conjuntos').map((f) => ({ ...conAov(f, aov), nivel: 'conjunto' }));
  const ads = filasNivel(d, 'anuncios').map((f) => ({ ...conAov(f, aov), nivel: 'anuncio' }));
  const camps = filasNivel(d, 'campanas').map((f) => ({ ...conAov(f, aov), nivel: 'campana' }));
  const orden = (a, b) => Number(b.activo) - Number(a.activo) || (b.gasto_usd || 0) - (a.gasto_usd || 0);
  return camps.map((c) => ({
    ...c,
    ultima: ultima[c.id] || null,
    hijos: conjs.filter((s) => s.campana === c.id).sort(orden).map((s) => ({ ...s, hijos: ads.filter((a) => a.conjunto === s.id).sort(orden) })),
  })).sort(orden);
}

/** Total de las campañas (fila de arriba). */
export function totalArbol(camps, aov) { return conAov(total(camps), aov); }

const ms = (iso) => Date.parse(iso);

/** Escalones de presupuesto por campaña: [{id, nombre, puntos: [{t, v, cambio}]}] para el gráfico; `desde` en ms recorta la ventana. */
export function series(escala, campanas, ahora, desde = null) {
  const cambios = ((escala && escala.cambios) || []).filter((c) => c.tipo === 'presupuesto' && typeof c.a === 'number');
  const out = [];
  for (const c of campanas || []) {
    const evs = cambios.filter((x) => x.campana === c.id).sort((a, b) => ms(a.cuando) - ms(b.cuando));
    const puntos = [];
    if (evs.length && !evs[0].inicio && typeof evs[0].de === 'number') puntos.push({ t: ms(evs[0].cuando) - 6 * 3600e3, v: evs[0].de, cambio: null });
    for (const e of evs) puntos.push({ t: ms(e.cuando), v: e.a, cambio: e });
    const actual = typeof c.presupuesto === 'number' ? c.presupuesto : (puntos.length ? puntos[puntos.length - 1].v : null);
    if (actual === null) continue;
    if (!puntos.length) puntos.push({ t: ahora - 24 * 3600e3, v: actual, cambio: null });
    puntos.push({ t: ahora, v: actual, cambio: null });
    let pts = puntos;
    if (desde !== null) {
      const antes = puntos.filter((p) => p.t <= desde);
      const base = antes.length ? antes[antes.length - 1] : null;
      pts = [...(base ? [{ t: desde, v: base.v, cambio: null }] : []), ...puntos.filter((p) => p.t > desde)];
    }
    if (pts.length) out.push({ id: c.id, nombre: c.nombre, rol: c.rol, activo: c.activo, estado: c.estado, inicio: c.inicio, puntos: pts });
  }
  return out;
}

/**
 * Carriles de presupuesto (uno por campaña, en %): tramos con su US$/día y marcas en cada cambio, para dibujar con HTML.
 * Reemplaza las líneas superpuestas (dueño, 16-nov: «no es óptimo»). Devuelve {t0, t1, carriles: [{id, nombre, rol, actual, tramos, marcas}], ticks}.
 */
export function carriles(lista, { ticksObjetivo = 6 } = {}) {
  const pts = lista.flatMap((s) => s.puntos);
  if (!pts.length) return null;
  const t0 = Math.min(...pts.map((p) => p.t));
  const t1 = Math.max(...pts.map((p) => p.t));
  const span = Math.max(1, t1 - t0);
  const pos = (t) => Math.max(0, Math.min(100, ((t - t0) / span) * 100));
  const vmax = Math.max(...pts.map((p) => p.v)) || 1;
  const out = lista.map((s) => {
    const tramos = [];
    for (let i = 0; i < s.puntos.length - 1; i += 1) {
      const a = s.puntos[i];
      const b = s.puntos[i + 1];
      if (b.t <= a.t) continue;
      tramos.push({ izq: pos(a.t), ancho: pos(b.t) - pos(a.t), v: a.v, intensidad: 0.25 + 0.6 * (a.v / vmax) });
    }
    const marcas = s.puntos.filter((p) => p.cambio).map((p) => {
      const c = p.cambio;
      return { pos: pos(p.t), autor: c.autor === 'sistema' ? 'sistema' : 'a_mano', inicio: Boolean(c.inicio),
        sube: !c.inicio && typeof c.de === 'number' && c.a > c.de, baja: !c.inicio && typeof c.de === 'number' && c.a < c.de, de: c.de, a: c.a, cuando: c.cuando, motivo: c.motivo || null };
    });
    return { id: s.id, nombre: s.nombre, rol: s.rol, activo: s.activo, estado: s.estado, inicio: s.inicio, actual: s.puntos[s.puntos.length - 1].v, tramos, marcas };
  });
  // eje: horas enteras (mayores) y medias horas (menores) en ventanas cortas; más espaciado en las largas (dueño, 16-nov)
  const horas = span / 3600e3;
  const [mayorH, menorH] = horas <= 30 ? [1, 0.5] : horas <= 80 ? [3, 1] : horas <= 200 ? [12, 3] : [24, 6];
  const ticks = [];
  const pasoMs = menorH * 3600e3;
  for (let t = Math.ceil(t0 / pasoMs) * pasoMs; t <= t1; t += pasoMs) {
    const mayor = Math.abs((t / 3600e3) % mayorH) < 1e-6;
    ticks.push({ t, pos: pos(t), mayor });
  }
  return { t0, t1, carriles: out, ticks, mayorH, menorH };
}

/**
 * Estado de una campaña para el icono del carril (dueño, 17-nov: «saber qué está programado, qué está activo y demás estados»).
 * Programada = activa en Meta con su inicio (start_time de la ficha) todavía en el futuro. Devuelve {clave, texto, tono, titulo}.
 */
export function estadoCampana(c, ahora = Date.now()) {
  const e = (c && c.estado) || null;
  const t0 = c && c.inicio ? Date.parse(c.inicio) : NaN;
  const vivo = e === 'ACTIVE' || e === 'IN_PROCESS';
  if (vivo && Number.isFinite(t0) && t0 > ahora) return { clave: 'programada', texto: 'Programada', tono: 'info', titulo: 'Activa en Meta, todavía no arrancó', inicio: t0 };
  if (e === 'ACTIVE') return { clave: 'activa', texto: 'Activa', tono: 'ok', titulo: 'Activa y entregando' };
  if (e === 'IN_PROCESS') return { clave: 'proceso', texto: 'En proceso', tono: 'info', titulo: 'Meta la está procesando' };
  if (e === 'PENDING_REVIEW') return { clave: 'revision', texto: 'En revisión', tono: 'aviso', titulo: 'Meta la está revisando' };
  if (e === 'WITH_ISSUES') return { clave: 'problemas', texto: 'Con problemas', tono: 'error', titulo: 'Activa con problemas en Meta' };
  if (e === 'DISAPPROVED') return { clave: 'rechazada', texto: 'Rechazada', tono: 'error', titulo: 'Rechazada por Meta' };
  if (e === 'PAUSED' || e === 'CAMPAIGN_PAUSED' || e === 'ADSET_PAUSED') return { clave: 'pausada', texto: 'Apagada', tono: 'neutro', titulo: 'Pausada en Meta' };
  if (e === 'ARCHIVED' || e === 'DELETED') return { clave: 'archivada', texto: e === 'DELETED' ? 'Eliminada' : 'Archivada', tono: 'neutro', titulo: 'Fuera de Meta' };
  return { clave: 'sin_dato', texto: 'Sin dato', tono: 'neutro', titulo: 'Sin estado leído de Meta' };
}

/** Veredicto de rentabilidad de una fila (campaña, conjunto o anuncio) con el ROAS con AOV y la misma vara de la escala. */
export function veredicto(f, aov) {
  const g = f.gasto_usd || 0;
  const minimo = f.nivel === 'anuncio' ? 2 : 5;
  if (g < minimo) return { clave: 'sin_datos', texto: 'Sin datos', tono: 'neutro' };
  if (!f.compras_meta) {
    if (aov && g >= 1.5 * aov) return { clave: 'pierde', texto: 'Pierde', tono: 'error', porque: `Gastó ${Math.round(g)} US$ (1,5 veces el AOV) sin compras.` };
    return { clave: 'mirando', texto: 'Juntando datos', tono: 'neutro' };
  }
  const r = f.roas_aov;
  if (typeof r !== 'number') return { clave: 'sin_datos', texto: 'Sin datos', tono: 'neutro' };
  if (r >= UMBRAL.surf) return { clave: 'rentable', texto: 'Rentable', tono: 'ok' };
  if (r >= UMBRAL.bajar) return { clave: 'justo', texto: 'Justo', tono: 'aviso' };
  return { clave: 'pierde', texto: 'Pierde', tono: 'error' };
}

const pctCambio = (de, a) => (typeof de === 'number' && de > 0 && typeof a === 'number' ? Math.round(((a - de) / de) * 100) : null);

/** Renglones de la línea de tiempo (más nuevo primero): cambios aplicados y decisiones de la escala (los «no hacer nada» ya vienen fundidos). */
export function renglones(escala, { campana = null, filtro = 'todo' } = {}) {
  const e = escala || {};
  const out = [];
  for (const c of e.cambios || []) {
    if (campana && c.campana !== campana) continue;
    if (filtro === 'decisiones') continue;
    if (filtro === 'a_mano' && c.autor !== 'a_mano') continue;
    let titulo;
    if (c.tipo === 'estado') titulo = c.a === 'ACTIVE' ? 'Se activó' : c.a === 'PAUSED' ? 'Se pausó' : `Estado: ${c.a}`;
    else if (c.inicio) titulo = `Arranca con US$ ${c.a}/día`;
    else {
      const p = pctCambio(c.de, c.a);
      titulo = `${c.a > c.de ? 'Subió' : 'Bajó'} de US$ ${c.de} a US$ ${c.a}${p !== null ? ` (${p > 0 ? '+' : ''}${p} %)` : ''}`;
    }
    out.push({ clase: 'cambio', cuando: c.cuando, campana: c.campana, campana_nombre: c.campana_nombre, titulo,
      quien: c.autor === 'sistema' ? 'Sistema' : 'A mano', tono: c.autor === 'sistema' ? 'acento' : 'aviso',
      detalle: c.motivo || (c.autor === 'a_mano' ? 'Cambio hecho fuera del sistema (Administrador de anuncios). El sistema lo registró y decide desde acá.' : null),
      sube: c.tipo === 'presupuesto' && !c.inicio && c.a > c.de, baja: c.tipo === 'presupuesto' && !c.inicio && c.a < c.de });
  }
  if (filtro !== 'a_mano') {
    for (const d of e.decisiones || []) {
      if (campana && d.campana !== campana) continue;
      if (filtro === 'cambios') continue;
      const accion = d.nuevo !== null && d.nuevo !== undefined;
      const titulo = accion ? `${d.texto}: US$ ${d.presupuesto} → US$ ${d.nuevo}` : d.veces > 1 ? `${d.texto} (${d.veces} vueltas)` : d.texto;
      out.push({ clase: 'decision', cuando: d.hasta || d.cuando, desde: d.desde, hasta: d.hasta, veces: d.veces, campana: d.campana, campana_nombre: d.campana_nombre,
        titulo, quien: 'Escala', tono: accion ? (d.aplicada === false ? 'error' : 'ok') : 'neutro', sin_aplicar: accion && d.aplicada === false,
        detalle: d.porque, regla: d.regla, roas: d.roas, compras: d.compras });
    }
  }
  return out.sort((a, b) => ms(b.cuando) - ms(a.cuando));
}

/** Cuenta de quién movió el presupuesto (para el encabezado de la línea de tiempo). */
export function resumenAutores(escala) {
  const e = escala || {};
  return { a_mano: e.a_mano || 0, sistema: e.del_sistema || 0, sin_aplicar: (e.sin_aplicar || []).length };
}

/** Hora de un instante en una zona: {h, m, texto 'HH:MM', dia 'dd/mm', medianoche}. Sin zona válida → null. */
export function horaEn(t, zona) {
  if (!zona) return null;
  try {
    const p = Object.fromEntries(new Intl.DateTimeFormat('en-GB', { timeZone: zona, hour: '2-digit', minute: '2-digit', day: '2-digit', month: '2-digit', hourCycle: 'h23' })
      .formatToParts(new Date(t)).map((x) => [x.type, x.value]));
    const h = Number(p.hour) % 24;
    const m = Number(p.minute);
    return { h, m, texto: `${String(h).padStart(2, '0')}:${p.minute}`, dia: `${p.day}/${p.month}`, medianoche: h === 0 && m === 0 };
  } catch (_) { return null; }
}

/** Medianoches de una zona dentro de [t0, t1] (en % de la ventana): ahí arranca el día de esa zona. */
export function medianoches(t0, t1, zona) {
  const out = [];
  if (!zona || !(t1 > t0)) return out;
  for (let t = Math.ceil(t0 / 1800e3) * 1800e3; t <= t1; t += 1800e3) {
    const h = horaEn(t, zona);
    if (h && h.medianoche) out.push({ t, pos: ((t - t0) / (t1 - t0)) * 100, dia: h.dia });
  }
  return out;
}
