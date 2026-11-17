// lib/agentes.js — lógica pura de #/agentes (CONTRATO §4 `GET /agentes` y `/agentes/<ejecucion_id>`, §7b).
// Fuentes: empresa/registro.jsonl (cadena de hashes, contrato registro) y empresa/costos.jsonl (contrato costos). Solo lectura.
// Sin DOM ni red. Dinero: enteros en unidad menor + moneda; las sumas nunca mezclan monedas; sin dato ⇒ «—», nunca 0.

import { dineroValido, proporcionBp } from './operacion.js';
import { NOMBRE_ETAPA } from './parametros.js';

export const MODOS = { fixture: { texto: 'Datos de prueba', tono: 'info' }, dry_run: { texto: 'Simulado', tono: 'neutro' }, live: { texto: 'En real', tono: 'aviso' } };
const TONO_ESTADO = { ok: 'ok', error: 'error', bloqueado: 'error', dry_run: 'neutro', en_curso: 'info', parcial: 'aviso' };
const RE_QA = /(^|[-:_])qa$|^qa[-:_]/i;
const PESO_ESTADO = { error: 3, bloqueado: 2, parcial: 1, ok: 0, dry_run: 0 };

/** 'dry-run'/'dry_run' → 'dry_run'; 'fixture'/'demo' → 'fixture'; 'live' → 'live'; otro → null. */
export function normalizarModo(modo) {
  const m = String(modo || '').toLowerCase().replace('-', '_');
  if (m === 'dry_run' || m === 'dryrun') return 'dry_run';
  if (m === 'fixture' || m === 'demo' || m === 'prueba') return 'fixture';
  if (m === 'live' || m === 'vivo') return 'live';
  return null;
}

/** Modo que se muestra: una oferta demo (`_ejemplo`) se anota como fixture aunque el registro diga dry_run (docs: lo hecho con fixture se anota dry_run). */
export function modoVisible(modo, { demo = false } = {}) {
  const m = normalizarModo(modo);
  if (!m) return null;
  if (demo && m === 'dry_run') return 'fixture';
  return m;
}

export function esAgenteQa(agente) { return typeof agente === 'string' && RE_QA.test(agente); }

function ms(iso) { const t = Date.parse(iso); return Number.isFinite(t) ? t : null; }

/** Un evento del registro (línea cruda con `resultado:{estado,codigo}`) o ya normalizado (idempotente). */
export function normalizarEvento(e, i = 0) {
  if (!e || typeof e !== 'object') return null;
  const r = e.resultado && typeof e.resultado === 'object' ? e.resultado : { estado: e.estado, codigo: e.codigo };
  return {
    n: Number.isSafeInteger(e.n) ? e.n : i + 1, ts: e.ts || null, evento: e.evento || null, etapa: e.etapa || null, agente: e.agente || null, herramienta: e.herramienta || null,
    entrada_resumen: typeof e.entrada_resumen === 'string' ? e.entrada_resumen : '', estado: typeof r.estado === 'string' ? r.estado : null, codigo: Number.isSafeInteger(r.codigo) ? r.codigo : null,
    costo: dineroValido(e.costo_estimado) || dineroValido(e.costo), modo: normalizarModo(e.modo), hash: typeof e.hash === 'string' ? e.hash : null,
    tokens: e.tokens && typeof e.tokens === 'object' ? { entrada: e.tokens.entrada ?? null, salida: e.tokens.salida ?? null } : null,
  };
}

function sumarDinero(lista) {
  const porMoneda = new Map();
  for (const d of lista) { const v = dineroValido(d); if (v) porMoneda.set(v.moneda, (porMoneda.get(v.moneda) || 0n) + BigInt(v.monto)); }
  return [...porMoneda.entries()].map(([moneda, monto]) => ({ moneda, monto: Number(monto) })).sort((a, b) => a.moneda.localeCompare(b.moneda));
}

function estadoDeEventos(eventos) {
  let peor = 'ok';
  for (const e of eventos) if (e.estado && (PESO_ESTADO[e.estado] || 0) > (PESO_ESTADO[peor] || 0)) peor = e.estado;
  return peor;
}

/**
 * Agrupa líneas del registro por `ejecucion_id` (una ejecución puede tocar varias etapas y agentes: se listan todos).
 * Devuelve ejecuciones ordenadas por inicio descendente. Fallback cuando el panel entrega líneas crudas.
 */
export function agruparRegistro(lineas) {
  const grupos = new Map();
  (Array.isArray(lineas) ? lineas : []).forEach((l, i) => {
    const e = normalizarEvento(l, i);
    if (!e || !l || typeof l.ejecucion_id !== 'string') return;
    const g = grupos.get(l.ejecucion_id) || { ejecucion_id: l.ejecucion_id, oferta_id: l.oferta_id || null, eventos: [] };
    if (!g.oferta_id && l.oferta_id) g.oferta_id = l.oferta_id;
    g.eventos.push(e);
    grupos.set(l.ejecucion_id, g);
  });
  const salida = [];
  for (const g of grupos.values()) {
    const ev = [...g.eventos].sort((a, b) => String(a.ts || '').localeCompare(String(b.ts || '')) || a.n - b.n);
    const etapas = [...new Set(ev.map((x) => x.etapa).filter(Boolean))];
    const agentes = [...new Set(ev.map((x) => x.agente).filter(Boolean))];
    const modos = [...new Set(ev.map((x) => x.modo).filter(Boolean))];
    const costos = sumarDinero(ev.map((x) => x.costo));
    salida.push({
      ejecucion_id: g.ejecucion_id, oferta_id: g.oferta_id, etapa: etapas[0] || null, etapas, agente: agentes[0] || null, agentes,
      inicio: ev[0].ts, fin: ev[ev.length - 1].ts, estado: estadoDeEventos(ev), costo: costos.length === 1 ? costos[0] : null,
      costos, modo: modos.length === 1 ? modos[0] : modos.includes('live') ? 'live' : modos[0] || null, eventos: ev,
    });
  }
  return salida.sort((a, b) => String(b.inicio || '').localeCompare(String(a.inicio || '')));
}

/** Costos por moneda de una ejecución: `costos` (lista), `costo_por_moneda` ({EUR: 300}) o el costo único. */
function costosDeRaw(raw, costo) {
  if (Array.isArray(raw.costos)) return sumarDinero(raw.costos);
  if (raw.costo_por_moneda && typeof raw.costo_por_moneda === 'object') return sumarDinero(Object.entries(raw.costo_por_moneda).map(([moneda, monto]) => ({ moneda, monto })));
  return costo ? [costo] : [];
}

/** ¿Algún archivo de origen es de la oferta demo (ofertas/_ejemplo/…)? Sus ejecuciones se anotan como fixture. */
export function fuenteEsDemo(fuente) {
  return (Array.isArray(fuente) ? fuente : []).some((f) => typeof f === 'string' && /(^|\/)ofertas\/_[^/]*\//.test(f));
}

/** Normaliza una ejecución ya agrupada por el panel (tolera campos ausentes). */
export function normalizarEjecucion(raw, { ofertasDemo = new Set(), demo = false } = {}) {
  if (!raw || typeof raw !== 'object' || typeof raw.ejecucion_id !== 'string') return null;
  const eventos = Array.isArray(raw.eventos) ? raw.eventos.map(normalizarEvento).filter(Boolean) : null;
  const nEventos = eventos ? eventos.length : (Number.isSafeInteger(raw.eventos) ? raw.eventos : (Number.isSafeInteger(raw.n_eventos) ? raw.n_eventos : null));
  const inicio = raw.inicio || (eventos && eventos[0] && eventos[0].ts) || null;
  const fin = raw.fin || (eventos && eventos.length && eventos[eventos.length - 1].ts) || null;
  const di = ms(inicio);
  const df = ms(fin);
  const duracionMs = di !== null && df !== null && df > di ? df - di : null;
  const costo = dineroValido(raw.costo) || dineroValido(raw.costo_estimado) || dineroValido(raw.costo_total);
  const estadoCrudo = typeof raw.estado === 'string' ? raw.estado : (eventos ? estadoDeEventos(eventos) : null);
  const estado = estadoCrudo === 'dry-run' ? 'dry_run' : estadoCrudo;
  const agentes = Array.isArray(raw.agentes) ? raw.agentes.filter((a) => typeof a === 'string') : (typeof raw.agente === 'string' ? [raw.agente] : (eventos ? [...new Set(eventos.map((e) => e.agente).filter(Boolean))] : []));
  const etapas = Array.isArray(raw.etapas) ? raw.etapas.filter((a) => typeof a === 'string') : (typeof raw.etapa === 'string' ? [raw.etapa] : (eventos ? [...new Set(eventos.map((e) => e.etapa).filter(Boolean))] : []));
  const modoCrudo = raw.modo || (eventos && eventos.find((e) => e.modo) && eventos.find((e) => e.modo).modo) || null;
  const rondas = [raw.ronda_qa, raw.rondas_qa, raw.ronda].find((x) => Number.isSafeInteger(x));
  return {
    ejecucion_id: raw.ejecucion_id, oferta_id: raw.oferta_id || null, etapa: etapas[0] || null, etapas, agente: agentes[0] || null, agentes,
    inicio, fin, duracionMs, unSoloEvento: nEventos === 1, estado, tono: TONO_ESTADO[estado] || 'neutro', costo, costos: costosDeRaw(raw, costo),
    modo: modoVisible(modoCrudo, { demo: demo || (!!raw.oferta_id && ofertasDemo.has(raw.oferta_id)) }), nEventos, eventos, rondas_qa: rondas ?? null,
    tokens: raw.tokens && typeof raw.tokens === 'object' ? raw.tokens : null,
  };
}

/** Lista de ejecuciones desde lo que entregue el panel: array de ejecuciones, `{ejecuciones}` o líneas crudas (`{lineas}` o con `evento`). */
export function ejecucionesDeDatos(datos, opc = {}) {
  let lista = [];
  if (Array.isArray(datos)) lista = datos;
  else if (datos && Array.isArray(datos.ejecuciones)) lista = datos.ejecuciones;
  else if (datos && Array.isArray(datos.lineas)) lista = agruparRegistro(datos.lineas);
  if (lista.length && lista.every((x) => x && typeof x === 'object' && typeof x.evento === 'string' && typeof x.ejecucion_id === 'string')) lista = agruparRegistro(lista);
  return lista.map((x) => normalizarEjecucion(x, opc)).filter(Boolean).sort((a, b) => String(b.inicio || '').localeCompare(String(a.inicio || '')));
}

/** Rondas de QA por (oferta, etapa): nº de ejecuciones distintas con un agente QA. Sin ninguna ⇒ no está en el mapa (sin dato, no 0). */
export function rondasQaPorEtapa(ejecuciones) {
  const mapa = new Map();
  for (const e of ejecuciones) {
    if (!e.agentes.some(esAgenteQa)) continue;
    for (const et of e.etapas.length ? e.etapas : ['—']) {
      const k = `${e.oferta_id || '—'}|${et}`;
      const s = mapa.get(k) || new Set();
      s.add(e.ejecucion_id);
      mapa.set(k, s);
    }
  }
  return new Map([...mapa.entries()].map(([k, s]) => [k, s.size]));
}

/** Ronda de QA de una ejecución: la que declara el panel, o la derivada del registro; null = sin dato. */
export function rondaDe(e, rondas) {
  if (Number.isSafeInteger(e.rondas_qa)) return e.rondas_qa;
  const claves = (e.etapas.length ? e.etapas : ['—']).map((et) => rondas.get(`${e.oferta_id || '—'}|${et}`)).filter((n) => Number.isSafeInteger(n));
  return claves.length ? Math.max(...claves) : null;
}

/** Tope por corrida de agente (limites.max_budget_por_corrida_agente). null = «nada gasta hasta que se fije». */
export function topeCorrida(limites) {
  const v = limites && typeof limites === 'object' ? (limites.valores && typeof limites.valores === 'object' ? limites.valores : limites) : null;
  if (!v) return { tope: null, moneda: null, estado: 'sin_limites' };
  const tope = Number.isSafeInteger(v.max_budget_por_corrida_agente) && v.max_budget_por_corrida_agente > 0 ? v.max_budget_por_corrida_agente : null;
  return { tope, moneda: typeof v.moneda_limites === 'string' ? v.moneda_limites : null, estado: tope === null ? 'sin_tope' : 'ok' };
}

/** Uso del tope por una ejecución: {estado:'sin_tope'|'sin_costo'|'moneda_distinta'|'ok', bp, excede}. */
export function usoCorrida(e, t) {
  if (!t || t.tope === null) return { estado: 'sin_tope', bp: null, excede: null };
  if (!e.costo) return { estado: 'sin_costo', bp: null, excede: null };
  if (t.moneda && e.costo.moneda !== t.moneda) return { estado: 'moneda_distinta', bp: null, excede: null };
  const bp = proporcionBp(e.costo.monto, t.tope);
  return { estado: 'ok', bp, excede: e.costo.monto > t.tope };
}

function acumularPor(ejecuciones, claveDe, t) {
  const mapa = new Map();
  for (const e of ejecuciones) {
    for (const k of claveDe(e)) {
      const g = mapa.get(k) || { clave: k, ejecuciones: 0, costos: [], sinCosto: 0, excedidas: 0, maximo: null, errores: 0 };
      g.ejecuciones += 1;
      if (e.costo) g.costos.push(e.costo); else g.sinCosto += 1;
      const u = usoCorrida(e, t);
      if (u.excede) g.excedidas += 1;
      if (e.costo && (!g.maximo || (g.maximo.moneda === e.costo.moneda && e.costo.monto > g.maximo.monto))) g.maximo = e.costo;
      if (e.estado === 'error' || e.estado === 'bloqueado') g.errores += 1;
      mapa.set(k, g);
    }
  }
  return [...mapa.values()].map((g) => ({ ...g, total: sumarDinero(g.costos) })).sort((a, b) => b.ejecuciones - a.ejecuciones || a.clave.localeCompare(b.clave));
}

/** Costos acumulados por agente y por etapa, con el tope por corrida. */
export function costosAcumulados(ejecuciones, t) {
  return {
    porAgente: acumularPor(ejecuciones, (e) => (e.agentes.length ? e.agentes : ['(sin agente)']), t),
    porEtapa: acumularPor(ejecuciones, (e) => (e.etapas.length ? e.etapas : ['(sin etapa)']), t),
    total: sumarDinero(ejecuciones.map((e) => e.costo)),
    sinCosto: ejecuciones.filter((e) => !e.costo).length,
    excedidas: ejecuciones.filter((e) => usoCorrida(e, t).excede).length,
  };
}

/** Líneas de costos.jsonl → total por origen y moneda (contrato costos: origen ia|creditos|herramienta). */
export function costosDeArchivo(lineas) {
  const mapa = new Map();
  for (const l of Array.isArray(lineas) ? lineas : []) {
    const m = dineroValido(l && l.monto);
    if (!m) continue;
    const k = `${l.origen || '—'}|${m.moneda}`;
    mapa.set(k, (mapa.get(k) || 0n) + BigInt(m.monto));
  }
  return [...mapa.entries()].map(([k, v]) => { const [origen, moneda] = k.split('|'); return { origen, moneda, monto: Number(v) }; }).sort((a, b) => a.origen.localeCompare(b.origen));
}

/** Filtros de la tabla de ejecuciones (valores = '' no filtra). */
export function filtrarEjecuciones(lista, { oferta = '', etapa = '', agente = '', modo = '', estado = '' } = {}) {
  return lista.filter((e) => (!oferta || e.oferta_id === oferta) && (!etapa || e.etapas.includes(etapa)) && (!agente || e.agentes.includes(agente))
    && (!modo || e.modo === modo) && (!estado || e.estado === estado));
}

export function opcionesDeFiltro(lista) {
  const u = (f) => [...new Set(lista.flatMap(f).filter(Boolean))].sort();
  return { ofertas: u((e) => [e.oferta_id]), etapas: u((e) => e.etapas), agentes: u((e) => e.agentes), modos: u((e) => [e.modo]), estados: u((e) => [e.estado]) };
}

export function modeloAgentes(datos, { limites, ofertas, fuente } = {}) {
  const demo = new Set((Array.isArray(ofertas) ? ofertas : []).filter((o) => o && o.demo === true).map((o) => o.oferta_id));
  const ejecuciones = ejecucionesDeDatos(datos, { ofertasDemo: demo, demo: fuenteEsDemo(fuente) });
  const t = topeCorrida(limites);
  const rondas = rondasQaPorEtapa(ejecuciones);
  const filas = ejecuciones.map((e) => ({ ...e, ronda: rondaDe(e, rondas), uso: usoCorrida(e, t) }));
  return { ejecuciones: filas, tope: t, costos: costosAcumulados(ejecuciones, t), filtros: opcionesDeFiltro(ejecuciones), costosArchivo: costosDeArchivo(datos && Array.isArray(datos.costos) ? datos.costos : []), hayDatos: filas.length > 0 };
}

// ----------------------------------------------------------------------------------------------------------------
// Rediseño U4: nombres humanos, estado y atención
// ----------------------------------------------------------------------------------------------------------------

export const MODOS_HUMANOS = {
  fixture: { texto: 'Datos de prueba', tono: 'info', clave: 'modo_fixture' },
  dry_run: { texto: 'Simulado', tono: 'neutro', clave: 'modo_dry_run' },
  live: { texto: 'En real', tono: 'aviso', clave: 'modo_live' },
};

const ESTADOS_EJEC = {
  ok: { texto: 'Correcta', tono: 'ok', icono: 'ok' }, error: { texto: 'Con error', tono: 'error', icono: 'x-circulo' }, bloqueado: { texto: 'Bloqueada', tono: 'error', icono: 'candado' },
  dry_run: { texto: 'Simulada', tono: 'neutro', icono: 'info' }, en_curso: { texto: 'En curso', tono: 'info', icono: 'progreso' }, parcial: { texto: 'Parcial', tono: 'aviso', icono: 'alerta' },
};
export function estadoEjecucion(estado) {
  return ESTADOS_EJEC[estado] || { texto: estado ? String(estado).replace(/_/g, ' ') : 'Sin dato', tono: 'neutro', icono: 'circulo-punteado' };
}

/** Nombre de la etapa en lenguaje humano: «D1» → «Descubrimiento» (el código va aparte, pequeño). */
export function nombreEtapa(codigo) { return NOMBRE_ETAPA[codigo] || codigo || '—'; }

/** «d1-maker» → «IA que prepara: Descubrimiento» · «x1-qa» → «IA que revisa: Cumplimiento» · «motor» → «El sistema automático» · «script:activar» → «Tarea automática: activar». */
export function nombreAgente(a) {
  const t = String(a ?? '');
  const m = /^([a-z]\d+)-(maker|qa)$/i.exec(t);
  if (m) return `${m[2].toLowerCase() === 'maker' ? 'IA que prepara' : 'IA que revisa'}: ${nombreEtapa(m[1].toUpperCase())}`;
  if (t === 'motor') return 'El sistema automático';
  if (/^script:/.test(t)) return `Tarea automática: ${t.slice(7).replace(/_/g, ' ')}`;
  return t || '—';
}

/** Nombre corto del agente cuando la etapa ya se ve en otra columna: «IA que prepara», «IA que revisa»; el resto igual que `nombreAgente`. */
export function nombreAgenteCorto(a) {
  const t = String(a ?? '');
  const m = /^([a-z]\d+)-(maker|qa)$/i.exec(t);
  return m ? (m[2].toLowerCase() === 'maker' ? 'IA que prepara' : 'IA que revisa') : nombreAgente(t);
}

/** Rondas de QA para dibujar: [{llena:true}…] hasta un máximo (por defecto 3, el de la etapa); null sin dato. */
export function puntosRonda(ronda, maximo = 3) {
  if (!Number.isSafeInteger(ronda) || ronda < 0) return null;
  const n = Math.max(ronda, maximo);
  return Array.from({ length: n }, (_, i) => ({ llena: i < ronda }));
}

/** Serie cronológica del costo por corrida (solo la moneda indicada o la primera); sin costo = hueco, nunca 0. */
export function serieCostoPorCorrida(ejecuciones, moneda) {
  const lista = [...ejecuciones].filter((e) => e.inicio).sort((a, b) => String(a.inicio).localeCompare(String(b.inicio)));
  const mon = moneda || (lista.find((e) => e.costo) || {}).costo?.moneda || null;
  return { moneda: mon, serie: lista.map((e) => ({ x: e.inicio, y: e.costo && e.costo.moneda === mon ? e.costo.monto : null, estado: e.costo && e.costo.moneda === mon ? 'ok' : 'ausente' })) };
}

/** Lo que requiere atención en Agentes, de más a menos urgente. */
export function atencionAgentes(m) {
  const items = [];
  if (!m.hayDatos) return items;
  const malas = m.ejecuciones.filter((e) => e.estado === 'error' || e.estado === 'bloqueado');
  if (malas.length) items.push({ tono: 'critico', titulo: `${malas.length} ${malas.length === 1 ? 'ejecución terminó con error o bloqueada' : 'ejecuciones terminaron con error o bloqueadas'}`, detalle: `La más reciente: ${nombreAgente(malas[0].agente)} en ${nombreEtapa(malas[0].etapa)}.` });
  if (m.costos.excedidas) items.push({ tono: 'aviso', titulo: `${m.costos.excedidas} ${m.costos.excedidas === 1 ? 'ejecución superó' : 'ejecuciones superaron'} el tope de costo por ejecución`, detalle: 'Un agente costó más de lo que permiten tus límites.' });
  if (m.tope.estado === 'sin_tope') items.push({ tono: 'aviso', titulo: 'El tope de costo por ejecución aún no está fijado', detalle: 'Mientras siga sin fijar, ningún agente puede gastar. Lo fijas tú en los límites.', accion: { texto: 'Abrir límites', ruta: '#/parametros' } });
  else if (m.tope.estado === 'sin_limites') items.push({ tono: 'info', titulo: 'No se pudieron leer los límites', detalle: 'Sin ellos no se compara ningún costo con el tope por ejecución.' });
  if (m.costos.sinCosto) items.push({ tono: 'info', titulo: `${m.costos.sinCosto} ${m.costos.sinCosto === 1 ? 'ejecución sin costo registrado' : 'ejecuciones sin costo registrado'}`, detalle: 'No cuentan como costo 0: simplemente no hay dato.' });
  const orden = { critico: 0, aviso: 1, info: 2 };
  return items.sort((a, b) => orden[a.tono] - orden[b.tono]);
}

export function comandosAgentes() {
  return {
    verificar: '.venv/bin/python -m engine.registro verificar --json',
  };
}
