// lib/cumplimiento.js — lógica pura de #/cumplimiento (CONTRATO §4 `GET /cumplimiento`).
// Fuentes: ofertas/<id>/qa/x1-*.json (dictámenes de X1: contrato qa con etapa=X1 y etapa_objetivo) y empresa/compliance/sellos/<sha256>.json
// (contrato sello). X1 es veto transversal: aquí solo se LEE; sellar y verificar son `python -m compliance.sellar|verificar`.
// Sin DOM ni red. Sin dato ⇒ «sin dato» (nunca un PASS por defecto).

import { aNumero } from './operacion.js';
import { NOMBRE_ETAPA } from './parametros.js';

export const VEREDICTOS_QA = {
  PASS: { tono: 'ok', texto: 'Aprobado' }, PASS_CON_NOTAS: { tono: 'info', texto: 'Aprobado con notas' },
  FAIL: { tono: 'error', texto: 'Bloqueado' }, ESCALAR: { tono: 'aviso', texto: 'Espera tu decisión' },
};
export const SEMAFOROS = { verde: 'ok', amarillo: 'aviso', rojo: 'error' };
export const SEVERIDADES = {
  BLOQUEANTE: { tono: 'error', peso: 0 }, MAYOR: { tono: 'aviso', peso: 1 }, MENOR: { tono: 'info', peso: 2 }, MEJORA: { tono: 'neutro', peso: 3 },
};
export const ESTADOS_SELLO = {
  vigente: { tono: 'ok', texto: 'vigente' }, vencido: { tono: 'aviso', texto: 'vencido' }, alterado: { tono: 'error', texto: 'alterado' }, ilegible: { tono: 'error', texto: 'ilegible' },
  desconocido: { tono: 'neutro', texto: 'sin vigencia' },
};
const ORDEN_SEMAFORO = { verde: 0, amarillo: 1, rojo: 2 };

/** 'D10' → 10, 'M1' → 0.5 (M1 va antes de D1), resto al final: orden de lectura de las etapas de una oferta. */
export function ordenEtapa(e) {
  const m = /^D(\d+)$/.exec(e || '');
  if (m) return Number(m[1]);
  if (e === 'M1') return 0.5;
  return 99;
}

/** 'sha256:' + 64 hex → «sha256:1a2b3c4d…9f0e» (para tablas; el completo va en el title). */
export function abreviarHash(h) {
  const s = typeof h === 'string' ? h : '';
  const m = /^(sha256:)?([0-9a-f]{64})$/i.exec(s);
  if (!m) return s ? s.slice(0, 24) : '—';
  return `sha256:${m[2].slice(0, 8)}…${m[2].slice(-6)}`;
}

/** Instante de vencimiento: timestamp ISO Z, o fecha AAAA-MM-DD (vence al final de ese día UTC). null si no es válido. */
export function instanteVigencia(v) {
  if (typeof v !== 'string') return null;
  if (/^\d{4}-\d{2}-\d{2}$/.test(v)) { const t = Date.parse(`${v}T23:59:59Z`); return Number.isFinite(t) ? t : null; }
  const t = Date.parse(v);
  return Number.isFinite(t) ? t : null;
}

const alMs = (ahora) => (ahora instanceof Date ? ahora.getTime() : (Number.isFinite(Number(ahora)) ? Number(ahora) : Date.now()));

/** «vence en 12 d», «venció hace 3 h», «sin fecha de vigencia». */
export function textoVigencia(vigenciaHasta, ahora) {
  const t = instanteVigencia(vigenciaHasta);
  if (t === null) return 'sin fecha de vigencia';
  const dif = t - alMs(ahora);
  const abs = Math.abs(dif);
  const n = abs >= 86400000 ? Math.floor(abs / 86400000) : abs >= 3600000 ? Math.floor(abs / 3600000) : Math.max(1, Math.floor(abs / 60000));
  const u = `${n} ${abs >= 86400000 ? (n === 1 ? 'día' : 'días') : abs >= 3600000 ? (n === 1 ? 'hora' : 'horas') : (n === 1 ? 'minuto' : 'minutos')}`;
  return dif >= 0 ? `vence en ${u}` : `venció hace ${u}`;
}

// ----------------------------------------------------------------------------------------------------------------
// Dictámenes
// ----------------------------------------------------------------------------------------------------------------

function versionNum(v) { const m = /^v(\d+)$/.exec(v || ''); return m ? Number(m[1]) : 0; }

/** Un dictamen puede llegar plano o como `{archivo, contenido}`. */
function contenidoDe(raw) {
  if (!raw || typeof raw !== 'object') return null;
  if (raw.contenido && typeof raw.contenido === 'object') return { ...raw.contenido, archivo: raw.archivo || raw.contenido.archivo || null };
  return raw;
}

export function normalizarHallazgo(h) {
  if (!h || typeof h !== 'object') return null;
  const sev = SEVERIDADES[h.severidad] ? h.severidad : null;
  return {
    check_id: h.check_id || null, patron_clave: h.patron_clave || null, severidad: sev, severidadCruda: h.severidad || null, tono: sev ? SEVERIDADES[sev].tono : 'neutro',
    descripcion: typeof h.descripcion === 'string' ? h.descripcion : '', cita: typeof h.evidencia === 'string' ? h.evidencia : (typeof h.evidencia_cita === 'string' ? h.evidencia_cita : ''),
    estado: h.estado || null, abierto: !h.estado || h.estado === 'abierto' || h.estado === 'devuelto_al_maker', correccion: typeof h.correccion === 'string' ? h.correccion : (typeof h.correccion_segura === 'string' ? h.correccion_segura : ''),
  };
}

export function normalizarDictamen(raw) {
  const d = contenidoDe(raw);
  if (!d || typeof d.veredicto !== 'string') return null;
  if (d.etapa && d.etapa !== 'X1' && !d.etapa_objetivo) return null;
  // GET /cumplimiento entrega RESÚMENES (sin hallazgos ni claims, con `n_hallazgos`); el detalle se pide aparte (aplicarDetalles).
  const soloResumen = !Array.isArray(d.hallazgos);
  const hallazgos = (soloResumen ? [] : d.hallazgos).map(normalizarHallazgo).filter(Boolean)
    .sort((a, b) => (SEVERIDADES[a.severidad] ? SEVERIDADES[a.severidad].peso : 9) - (SEVERIDADES[b.severidad] ? SEVERIDADES[b.severidad].peso : 9));
  const vig = typeof d.vigencia_hasta === 'string' ? d.vigencia_hasta : null;
  return {
    archivo: d.archivo || null, oferta_id: d.oferta_id || null, ambito: d.ambito || null, etapa_objetivo: d.etapa_objetivo || d.etapa || null, version: d.version || null, ronda: Number.isSafeInteger(d.ronda) ? d.ronda : null,
    creado_en: d.creado_en || null, veredicto: d.veredicto, veredictoInfo: VEREDICTOS_QA[d.veredicto] || { tono: 'neutro', texto: String(d.veredicto) }, semaforo: SEMAFOROS[d.semaforo] ? d.semaforo : null,
    puntaje: aNumero(d.puntaje_global), umbral: aNumero(d.umbral), soloResumen, nHallazgos: soloResumen ? (Number.isSafeInteger(d.n_hallazgos) ? d.n_hallazgos : null) : hallazgos.length,
    hallazgos, abiertos: soloResumen ? null : hallazgos.filter((h) => h.abierto).length,
    bloqueantes: soloResumen ? null : hallazgos.filter((h) => h.severidad === 'BLOQUEANTE' && h.abierto).length,
    claims: Array.isArray(d.claims_trazados) ? d.claims_trazados.filter((c) => c && typeof c.claim_id === 'string').map((c) => ({ claim_id: c.claim_id, evidencia_ref: typeof c.evidencia_ref === 'string' ? c.evidencia_ref : '' })) : null,
    vigencia_hasta: vig, artefacto_sha256: d.artefacto_sha256 || null, artefacto_ref: d.artefacto_ref || null, reglas_version: d.reglas_version || null, politicas_fecha_min: d.politicas_fecha_min || null,
    justificacion: typeof d.justificacion_sin_hallazgos === 'string' ? d.justificacion_sin_hallazgos : '', riesgos: Array.isArray(d.riesgos_residuales) ? d.riesgos_residuales.filter((r) => typeof r === 'string') : [],
    firmado: typeof d.firma_motor === 'string' && d.firma_motor.length > 0,
  };
}

/** Estado de vigencia de un dictamen respecto de `ahora`. */
export function estadoDictamen(d, ahora) {
  const t = instanteVigencia(d.vigencia_hasta);
  if (t === null) return { estado: 'desconocido', texto: 'sin vigencia declarada', tono: 'neutro' };
  return t >= alMs(ahora) ? { estado: 'vigente', texto: textoVigencia(d.vigencia_hasta, ahora), tono: 'ok' } : { estado: 'vencido', texto: textoVigencia(d.vigencia_hasta, ahora), tono: 'aviso' };
}

/** El dictamen más reciente por (oferta, etapa objetivo): mayor versión, luego ronda, luego fecha de creación. */
export function ultimosDictamenes(lista) {
  const mapa = new Map();
  for (const d of lista) {
    const k = `${d.oferta_id || '—'}|${d.etapa_objetivo || '—'}`;
    const p = mapa.get(k);
    const mejor = !p || versionNum(d.version) > versionNum(p.version)
      || (versionNum(d.version) === versionNum(p.version) && ((d.ronda || 0) > (p.ronda || 0) || ((d.ronda || 0) === (p.ronda || 0) && String(d.creado_en || '') >= String(p.creado_en || ''))));
    if (mejor) mapa.set(k, d);
  }
  return [...mapa.values()].sort((a, b) => String(a.oferta_id).localeCompare(String(b.oferta_id)) || ordenEtapa(a.etapa_objetivo) - ordenEtapa(b.etapa_objetivo));
}

/** Ruta relativa a la oferta de un dictamen (`qa/x1-d5-v1.json`) aunque el archivo venga como `ofertas/<id>/qa/…`. null si no es válida. */
export function rutaQa(archivo) {
  const m = /(?:^|\/)(qa\/[A-Za-z0-9_.-]+\.json)$/.exec(typeof archivo === 'string' ? archivo : '');
  return m ? m[1] : null;
}

/** Los últimos dictámenes (por oferta y etapa) que llegaron como resumen y cuyo detalle hay que pedir: [{oferta_id, ruta}]. */
export function dictamenesAEnriquecer(datos, maximo = 30) {
  const d = datos && typeof datos === 'object' ? datos : {};
  const normalizados = (Array.isArray(d.dictamenes) ? d.dictamenes : []).map(normalizarDictamen).filter(Boolean);
  return ultimosDictamenes(normalizados)
    .filter((x) => x.soloResumen && x.oferta_id && rutaQa(x.archivo))
    .slice(0, maximo).map((x) => ({ oferta_id: x.oferta_id, ruta: rutaQa(x.archivo) }));
}

/** Sustituye en `datos.dictamenes` el resumen por el dictamen completo cuando se pudo leer (`detalles`: Map `oferta|ruta` → objeto). */
export function aplicarDetalles(datos, detalles) {
  const d = datos && typeof datos === 'object' ? datos : {};
  if (!detalles || !detalles.size || !Array.isArray(d.dictamenes)) return d;
  const dictamenes = d.dictamenes.map((r) => {
    const c = contenidoDe(r);
    const det = c && c.oferta_id && rutaQa(c.archivo) ? detalles.get(`${c.oferta_id}|${rutaQa(c.archivo)}`) : null;
    return det && typeof det === 'object' ? { ...det, archivo: c.archivo, oferta_id: c.oferta_id } : r; // el id del panel manda (carpeta de la oferta)
  });
  return { ...d, dictamenes };
}

// ----------------------------------------------------------------------------------------------------------------
// Sellos
// ----------------------------------------------------------------------------------------------------------------

export function normalizarSello(raw) {
  const s = contenidoDe(raw);
  if (s && typeof s === 'object' && s.legible === false) {
    return { archivo: s.archivo || null, ilegible: true, oferta_id: null, etapa_objetivo: null, artefacto_sha256: '', reglas_version: null, emitido_en: null, vigencia_hasta: null, object_ids: [], dictamen_ref: null, dictamen_sha256: null, firma: null, alteradoPorPanel: false, hashActual: null, firmaValida: null };
  }
  if (!s || typeof s !== 'object' || typeof s.artefacto_sha256 !== 'string') return null;
  const firma = typeof s.firma === 'string' ? s.firma : '';
  return {
    archivo: s.archivo || null, oferta_id: s.oferta_id || null, etapa_objetivo: s.etapa_objetivo || null, artefacto_sha256: s.artefacto_sha256, reglas_version: s.reglas_version || null,
    emitido_en: s.emitido_en || null, vigencia_hasta: s.vigencia_hasta || null, object_ids: Array.isArray(s.object_ids) ? s.object_ids.filter((x) => typeof x === 'string') : [],
    dictamen_ref: s.dictamen_ref || null, dictamen_sha256: s.dictamen_sha256 || null,
    firma: /^ed25519/i.test(firma) ? 'ed25519' : /^hmac/i.test(firma) ? 'hmac' : (firma ? 'otra' : null),
    // banderas opcionales que puede calcular el panel (re-hash del artefacto, firma verificada)
    alteradoPorPanel: s.alterado === true || s.estado === 'alterado', hashActual: typeof s.hash_actual === 'string' ? s.hash_actual : (typeof s.artefacto_sha256_actual === 'string' ? s.artefacto_sha256_actual : null),
    firmaValida: typeof s.firma_valida === 'boolean' ? s.firma_valida : null,
  };
}

function baseDe(ruta) { return typeof ruta === 'string' ? ruta.split('/').pop() : ''; }

/**
 * Estado de un sello: 'alterado' (el artefacto o el dictamen ya no son los sellados, o la firma no verifica) > 'vencido' > 'vigente'.
 * @param ctx {ahora, dictamenes:[normalizados]} — con ellos se cruza el dictamen citado (misma versión de artefacto).
 */
export function estadoSello(sello, ctx = {}) {
  if (sello.ilegible) return { estado: 'ilegible', ...ESTADOS_SELLO.ilegible, causa: 'el archivo del visto bueno no se pudo leer o está dañado: no lo uses y vuelve a firmar la etapa' };
  const causas = [];
  if (sello.alteradoPorPanel) causas.push('el visto bueno aparece marcado como alterado');
  if (sello.hashActual && sello.hashActual !== sello.artefacto_sha256) causas.push('lo revisado cambió desde que se firmó (su huella actual es distinta de la firmada)');
  if (sello.firmaValida === false) causas.push('la firma no se pudo comprobar');
  const cita = baseDe(sello.dictamen_ref);
  if (cita && Array.isArray(ctx.dictamenes)) {
    const d = ctx.dictamenes.find((x) => x.archivo && baseDe(x.archivo) === cita && (!x.oferta_id || !sello.oferta_id || x.oferta_id === sello.oferta_id));
    if (d && d.artefacto_sha256 && d.artefacto_sha256 !== sello.artefacto_sha256) causas.push('el informe de cumplimiento citado se hizo sobre otra versión (huella distinta)');
  }
  if (causas.length) return { estado: 'alterado', ...ESTADOS_SELLO.alterado, causa: causas.join('; ') };
  const t = instanteVigencia(sello.vigencia_hasta);
  if (t === null) return { estado: 'desconocido', ...ESTADOS_SELLO.desconocido, causa: 'el visto bueno no trae una fecha de vencimiento válida' };
  if (t < alMs(ctx.ahora)) return { estado: 'vencido', ...ESTADOS_SELLO.vencido, causa: `${textoVigencia(sello.vigencia_hasta, ctx.ahora)}: se renueva firmando de nuevo la etapa, no editando el archivo` };
  return { estado: 'vigente', ...ESTADOS_SELLO.vigente, causa: null };
}

// ----------------------------------------------------------------------------------------------------------------
// Lint de claims
// ----------------------------------------------------------------------------------------------------------------

/** Resultado de compliance.lint_claims (si el panel lo entrega): {oferta_id, etapa, semaforo, reglas_version, hallazgos:[{nivel, categoria, descripcion, evidencia, locale}]}. */
export function normalizarLint(raw) {
  const l = contenidoDe(raw);
  if (!l || typeof l !== 'object' || !Array.isArray(l.hallazgos) || typeof l.semaforo !== 'string') return null;
  return {
    oferta_id: l.oferta_id || null, etapa: l.etapa || l.etapa_objetivo || null, semaforo: SEMAFOROS[l.semaforo] ? l.semaforo : null, reglas_version: l.reglas_version || null,
    hallazgos: l.hallazgos.filter((h) => h && typeof h === 'object').map((h) => ({ nivel: SEMAFOROS[h.nivel] ? h.nivel : null, categoria: h.categoria || null, patron_clave: h.patron_clave || null, descripcion: typeof h.descripcion === 'string' ? h.descripcion : '', evidencia: typeof h.evidencia === 'string' ? h.evidencia : '', locale: h.locale || null })),
  };
}

function peorSemaforo(lista) {
  let peor = null;
  for (const s of lista) if (s && (peor === null || ORDEN_SEMAFORO[s] > ORDEN_SEMAFORO[peor])) peor = s;
  return peor;
}

/** Lint de claims por oferta: semáforo (el peor), claims trazados con su evidencia, hallazgos abiertos por severidad y hallazgos del linter si los hay. */
export function lintPorOferta(ultimos, lints = []) {
  const mapa = new Map();
  const ofertaDe = (id) => { const k = id || '—'; if (!mapa.has(k)) mapa.set(k, { oferta_id: k, dictamenes: [], claims: new Map(), porSeveridad: { BLOQUEANTE: 0, MAYOR: 0, MENOR: 0, MEJORA: 0 }, lints: [] }); return mapa.get(k); };
  for (const d of ultimos) {
    const o = ofertaDe(d.oferta_id);
    o.dictamenes.push(d);
    for (const c of d.claims || []) if (!o.claims.has(c.claim_id)) o.claims.set(c.claim_id, { ...c, etapa: d.etapa_objetivo });
    for (const h of d.hallazgos) if (h.abierto && o.porSeveridad[h.severidad] !== undefined) o.porSeveridad[h.severidad] += 1;
  }
  for (const l of lints) ofertaDe(l.oferta_id).lints.push(l);
  return [...mapa.values()].map((o) => ({
    oferta_id: o.oferta_id, etapas: o.dictamenes.map((d) => d.etapa_objetivo), claims: [...o.claims.values()], porSeveridad: o.porSeveridad,
    semaforo: peorSemaforo([...o.dictamenes.map((d) => d.semaforo), ...o.lints.map((l) => l.semaforo)]), lints: o.lints,
    sinTrazar: o.dictamenes.filter((d) => d.claims && d.claims.length === 0).map((d) => d.etapa_objetivo),
    sinDetalle: o.dictamenes.filter((d) => d.soloResumen).map((d) => d.etapa_objetivo),
  })).sort((a, b) => a.oferta_id.localeCompare(b.oferta_id));
}

// ----------------------------------------------------------------------------------------------------------------
// Modelo completo
// ----------------------------------------------------------------------------------------------------------------

/** La oferta demo se llama `_ejemplo` en las carpetas y `OF-…` dentro de sus archivos: una carpeta `_…` casa con cualquier id. */
function mismaOferta(a, b) {
  return !a || !b || a === b || a.startsWith('_') || b.startsWith('_');
}

/** Normaliza lo que entrega GET /cumplimiento (tolera claves ausentes). */
export function modeloCumplimiento(datos, { ahora = Date.now() } = {}) {
  const d = datos && typeof datos === 'object' ? datos : {};
  const dictamenes = (Array.isArray(d.dictamenes) ? d.dictamenes : []).map(normalizarDictamen).filter(Boolean);
  const ultimos = ultimosDictamenes(dictamenes);
  const sellosBase = (Array.isArray(d.sellos) ? d.sellos : []).map(normalizarSello).filter(Boolean);
  const sellos = sellosBase.map((s) => ({ ...s, vigencia: estadoSello(s, { ahora, dictamenes }) }))
    .sort((a, b) => String(a.oferta_id).localeCompare(String(b.oferta_id)) || ordenEtapa(a.etapa_objetivo) - ordenEtapa(b.etapa_objetivo) || String(b.emitido_en || '').localeCompare(String(a.emitido_en || '')));
  const lints = (Array.isArray(d.lint) ? d.lint : (Array.isArray(d.lints) ? d.lints : [])).map(normalizarLint).filter(Boolean);
  // ¿qué dictámenes PASS no tienen sello? (X1 exige sello por hash para activar/publicar)
  const tieneSello = (x) => sellos.some((s) => !s.ilegible && (x.artefacto_sha256
    ? s.artefacto_sha256 === x.artefacto_sha256 // con el hash del dictamen: el sello debe ser de ESE artefacto
    : mismaOferta(s.oferta_id, x.oferta_id) && s.etapa_objetivo === x.etapa_objetivo)); // resumen sin hash: basta un sello de la misma oferta y etapa
  const sinSello = ultimos.filter((x) => (x.veredicto === 'PASS' || x.veredicto === 'PASS_CON_NOTAS') && !tieneSello(x));
  const conteo = { vigente: 0, vencido: 0, alterado: 0, ilegible: 0, desconocido: 0 };
  for (const s of sellos) conteo[s.vigencia.estado] += 1;
  return {
    dictamenes, ultimos, sellos, conteoSellos: conteo, sinSello,
    dictamenesPorVeredicto: ultimos.reduce((a, x) => { a[x.veredicto] = (a[x.veredicto] || 0) + 1; return a; }, {}),
    lint: lintPorOferta(ultimos, lints), hay: dictamenes.length > 0 || sellos.length > 0,
  };
}

// ----------------------------------------------------------------------------------------------------------------
// Rediseño U4: lenguaje humano y atención
// ----------------------------------------------------------------------------------------------------------------

/** Veredicto de X1 con su nombre humano (la sigla técnica va aparte, pequeña). */
export const VEREDICTO_HUMANO = {
  PASS: { texto: 'Aprobado', tono: 'ok', icono: 'ok', tecnico: 'PASS' },
  PASS_CON_NOTAS: { texto: 'Aprobado con notas', tono: 'info', icono: 'ok', tecnico: 'PASS con notas' },
  FAIL: { texto: 'Bloqueado', tono: 'error', icono: 'octogono', tecnico: 'FAIL' },
  ESCALAR: { texto: 'Espera tu decisión', tono: 'aviso', icono: 'firma', tecnico: 'ESCALAR' },
};
export function veredictoHumano(v) { return VEREDICTO_HUMANO[v] || { texto: String(v || 'Sin dato'), tono: 'neutro', icono: 'circulo-punteado', tecnico: String(v || '') }; }

export const ESTADO_HALLAZGO_HUMANO = {
  abierto: 'Abierto', devuelto_al_maker: 'Devuelto a quien lo hizo', corregido_por_qa: 'Corregido en la revisión', aceptado_con_nota: 'Aceptado con nota', resuelto: 'Resuelto', descartado: 'Descartado',
};
export function estadoHallazgoHumano(e) { return e ? (ESTADO_HALLAZGO_HUMANO[e] || String(e).replace(/_/g, ' ')) : 'Abierto'; }

export const SEMAFORO_HUMANO = { verde: 'Sin riesgo relevante', amarillo: 'Con reservas', rojo: 'Bloqueado por riesgo' };
export const ICONO_SELLO = { vigente: 'ok', vencido: 'reloj-alerta', alterado: 'octogono', ilegible: 'octogono', desconocido: 'circulo-punteado' };

/** Nombre de la etapa («D5» → «Página de venta, pago y medición»). */
export function nombreEtapaX1(codigo) { return NOMBRE_ETAPA[codigo] || codigo || '—'; }

/** Posiciones (0-100) del puntaje y del umbral sobre una escala de 0 a `maximo` (5 por defecto: la rúbrica puntúa de 1 a 5). null sin puntaje. */
export function geometriaPuntaje(puntaje, umbral, maximo = 5) {
  if (!Number.isFinite(puntaje) || !(maximo > 0)) return null;
  const pos = (v) => Math.round(Math.min(100, Math.max(0, (v / maximo) * 100)) * 100) / 100;
  return { puntaje: pos(puntaje), umbral: Number.isFinite(umbral) ? pos(umbral) : null, aprueba: Number.isFinite(umbral) ? puntaje >= umbral : null };
}

/** Lo que requiere atención en Cumplimiento, de más a menos urgente. */
export function atencionCumplimiento(m, ahora = Date.now()) {
  const items = [];
  const vetos = m.ultimos.filter((d) => d.veredicto === 'FAIL' || d.veredicto === 'ESCALAR');
  for (const d of vetos.slice(0, 3)) {
    items.push({ tono: d.veredicto === 'FAIL' ? 'critico' : 'aviso', titulo: d.veredicto === 'FAIL' ? `Cumplimiento bloquea la etapa «${nombreEtapaX1(d.etapa_objetivo)}»${d.oferta_id ? ` de ${d.oferta_id}` : ''}` : `La etapa «${nombreEtapaX1(d.etapa_objetivo)}»${d.oferta_id ? ` de ${d.oferta_id}` : ''} espera tu decisión`, detalle: d.veredicto === 'FAIL' ? 'No avanza hasta corregir los hallazgos bloqueantes y repetir la revisión.' : 'Cumplimiento no pudo decidir solo: te lo pasa a ti.' });
  }
  if (vetos.length > 3) items.push({ tono: 'critico', titulo: `Hay ${vetos.length - 3} etapas más bloqueadas o a la espera de tu decisión` });
  const alterados = m.sellos.filter((s) => s.vigencia.estado === 'alterado' || s.vigencia.estado === 'ilegible');
  if (alterados.length) items.push({ tono: 'critico', titulo: `${alterados.length} ${alterados.length === 1 ? 'visto bueno firmado alterado o ilegible' : 'vistos buenos firmados alterados o ilegibles'}`, detalle: alterados[0].vigencia.causa || 'El contenido ya no es el que se firmó: no lo uses y vuelve a firmar la etapa.' });
  const bloq = m.ultimos.reduce((a, d) => a + (d.bloqueantes || 0), 0);
  if (bloq && !vetos.length) items.push({ tono: 'critico', titulo: `${bloq} ${bloq === 1 ? 'hallazgo bloqueante abierto' : 'hallazgos bloqueantes abiertos'}`, detalle: 'Un hallazgo bloqueante frena la etapa aunque el resultado diga otra cosa.' });
  const vencidos = m.sellos.filter((s) => s.vigencia.estado === 'vencido');
  if (vencidos.length) items.push({ tono: 'aviso', titulo: `${vencidos.length} ${vencidos.length === 1 ? 'visto bueno firmado vencido' : 'vistos buenos firmados vencidos'}`, detalle: 'Un visto bueno vencido no autoriza nada: se renueva firmando de nuevo la etapa, no editando el archivo.' });
  if (m.sinSello.length) items.push({ tono: 'aviso', titulo: `${m.sinSello.length} ${m.sinSello.length === 1 ? 'etapa aprobada sin visto bueno firmado' : 'etapas aprobadas sin visto bueno firmado'}`, detalle: 'Sin esa firma no se puede activar ni publicar. La emite el código con una clave que ninguna IA tiene.' });
  const caducados = m.ultimos.filter((d) => (d.veredicto === 'PASS' || d.veredicto === 'PASS_CON_NOTAS') && estadoDictamen(d, ahora).estado === 'vencido');
  if (caducados.length) items.push({ tono: 'aviso', titulo: `${caducados.length} ${caducados.length === 1 ? 'informe de cumplimiento vencido' : 'informes de cumplimiento vencidos'}`, detalle: 'Un informe vencido deja de valer aunque diga aprobado.' });
  const sinDetalle = m.ultimos.filter((d) => d.soloResumen).length;
  if (sinDetalle) items.push({ tono: 'info', titulo: `${sinDetalle} ${sinDetalle === 1 ? 'informe sin detalle cargado' : 'informes sin detalle cargado'}`, detalle: 'El panel solo recibió el resumen: el recuento de hallazgos puede estar incompleto.' });
  const orden = { critico: 0, aviso: 1, info: 2 };
  return items.sort((a, b) => orden[a.tono] - orden[b.tono]);
}

export function comandosCumplimiento(ofertaId = 'OF-AAAAMM-NN', etapa = 'D5', locale = 'es-ES') {
  return {
    lint: `.venv/bin/python -m compliance.lint_claims --oferta ${ofertaId} --etapa ${etapa} --locale ${locale}`,
    sellar: `.venv/bin/python -m compliance.sellar --oferta ${ofertaId} --etapa-objetivo ${etapa} --artefacto <ruta> --dictamen ofertas/${ofertaId}/qa/x1-${etapa.toLowerCase()}-v1.json --locale ${locale}`,
    verificar: '.venv/bin/python -m compliance.verificar --hash sha256:<hash del artefacto>',
  };
}
