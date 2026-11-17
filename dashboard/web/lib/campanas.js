// lib/campanas.js — lógica PURA (datos → modelo de vista) de la pantalla #/campanas (D7: campaña de test en Meta).
// Sin DOM ni red. Probada con tests/dashboard/test_web_campanas.mjs.
//
// Fuente: GET /campanas/<id> = {campana, preflight, ids_meta, aprobacion, estado} de ofertas/<id>/07-campana/
//   (campana.json 1.2.0 · preflight.json · ids_meta.json · aprobacion.json). Esquemas: contratos/{campana,preflight,ids_meta,aprobacion}.schema.json.
//
// REGLAS
//  - SOLO LECTURA: este módulo no arma ninguna acción que active, publique o gaste. Lo único que produce para una persona es
//    el TEXTO de un comando de firma que la persona ejecuta en su terminal (el panel no firma).
//  - Dinero en unidad menor entera + moneda + decimales (campana.presupuesto.decimales); jamás `float`.
//  - Un preflight que falta, venció o es de otro hash_config NO habilita nada: se dice «sin preflight válido».
//  - Todo texto de archivos pasa por `neutralizar` (nombres de campaña/anuncio pueden venir de un agente).

import { neutralizar } from './descubrimiento.js';
import { dinero, RE_OFERTA_ID, RE_OFERTA_REAL } from './landing.js';

export const CICLO = Object.freeze(['borrador', 'preflight_ok', 'aprobada', 'activa']);
export const OTROS_ESTADOS = Object.freeze(['pausada', 'cerrada']);

/** Semáforo de cada ítem → tono visual. `null`/ausente = sin dato (neutro). */
export const TONO_SEMAFORO = Object.freeze({ VERDE: 'ok', AMARILLO: 'aviso', ROJO: 'error', NO_APLICA: 'neutro' });

/** P01–P25 (departamentos/08 Anexo A1; P25 solo si special_ad_categories no está vacío). `req` = quién lo comprueba. */
export const PREFLIGHT = Object.freeze([
  { id: 'P01', titulo: 'Sin empresa/PAUSA', ambito: 'sistema' },
  { id: 'P02', titulo: 'Cuenta ACTIVE y consultable', ambito: 'meta' },
  { id: 'P03', titulo: 'Método de pago válido', ambito: 'meta' },
  { id: 'P04', titulo: 'Cuenta «saludable» (X1)', ambito: 'meta' },
  { id: 'P05', titulo: 'Límite diario de Meta ≥ 1,75 × presupuesto diario', ambito: 'meta' },
  { id: 'P06', titulo: 'Límite de gasto de cuenta fijado por el dueño', ambito: 'meta' },
  { id: 'P07', titulo: 'Página vinculada', ambito: 'meta' },
  { id: 'P08', titulo: 'Dataset activo con eventos recientes', ambito: 'tracking' },
  { id: 'P09', titulo: 'EMQ ≥ objetivo', ambito: 'tracking' },
  { id: 'P10', titulo: 'Evento de prueba navegador + servidor con el mismo event_id', ambito: 'tracking' },
  { id: 'P11', titulo: 'Dominio verificado', ambito: 'tracking' },
  { id: 'P12', titulo: 'Enlace 200 sin redirecciones', ambito: 'landing' },
  { id: 'P13', titulo: 'URL sin vacíos y con macros', ambito: 'landing' },
  { id: 'P14', titulo: 'landing_hash, precio y moneda = paquete y checkout', ambito: 'landing' },
  { id: 'P15', titulo: 'Copys = paquete y lint_claims OK', ambito: 'creativos' },
  { id: 'P16', titulo: 'Mejoras de Meta en OPT_OUT', ambito: 'creativos' },
  { id: 'P17', titulo: 'self_ai_disclosure = política', ambito: 'creativos' },
  { id: 'P18', titulo: 'locale y países = mercado.json ⊆ paises_permitidos', ambito: 'limites' },
  { id: 'P19', titulo: 'Nombres válidos (ASCII, «_», sin «|»)', ambito: 'campana' },
  { id: 'P20', titulo: 'Presupuesto y spend_cap ≤ límites (con offset de Meta)', ambito: 'limites' },
  { id: 'P21', titulo: 'active_errors vacío; 0 objetos ajenos', ambito: 'meta' },
  { id: 'P22', titulo: 'Vistas previas por anuncio y ubicación', ambito: 'meta' },
  { id: 'P23', titulo: 'Ofertas en test < máximo', ambito: 'limites' },
  { id: 'P24', titulo: 'hash_config sellado', ambito: 'campana' },
  { id: 'P25', titulo: 'special_ad_categories = informe de cumplimiento y visto bueno firmado vigente', ambito: 'compliance', condicional: true },
]);

/** Nombre corto y humano de cada punto del preflight (el texto técnico completo sigue en PREFLIGHT[i].titulo). */
export const NOMBRE_PREFLIGHT = Object.freeze({
  P01: 'Sin PAUSA (freno de emergencia) activa', P02: 'Cuenta activa y consultable', P03: 'Método de pago válido', P04: 'Cuenta saludable (cumplimiento)', P05: 'Límite diario de Meta suficiente',
  P06: 'Tope de gasto fijado por ti', P07: 'Página de Facebook vinculada', P08: 'Medidor de Meta (dataset) activo con eventos recientes', P09: 'Calidad de coincidencia (EMQ)',
  P10: 'Evento de prueba en navegador y servidor', P11: 'Dominio verificado', P12: 'Enlace responde 200 sin redirecciones', P13: 'Dirección completa con marcadores (macros)',
  P14: 'Página de venta, precio y moneda iguales al paquete de anuncios', P15: 'Textos iguales al paquete y sin afirmaciones prohibidas', P16: 'Mejoras automáticas de Meta apagadas',
  P17: 'Aviso de uso de IA según la política', P18: 'Idioma y países permitidos', P19: 'Nombres válidos', P20: 'Presupuesto dentro de los límites',
  P21: 'Sin errores activos ni objetos ajenos', P22: 'Vistas previas por anuncio y ubicación', P23: 'Ofertas en prueba por debajo del máximo',
  P24: 'Huella de la configuración con visto bueno firmado', P25: 'Categorías especiales con visto bueno firmado de cumplimiento',
});

export const GRUPOS_PREFLIGHT = Object.freeze([
  { id: 'cuenta', titulo: 'Cuenta de Meta y pago', ids: Object.freeze(['P01', 'P02', 'P03', 'P04', 'P05', 'P06', 'P07', 'P21', 'P22']) },
  { id: 'medicion', titulo: 'Medición', ids: Object.freeze(['P08', 'P09', 'P10', 'P11']) },
  { id: 'landing', titulo: 'Página de venta y enlace', ids: Object.freeze(['P12', 'P13', 'P14']) },
  { id: 'creativos', titulo: 'Anuncios y políticas', ids: Object.freeze(['P15', 'P16', 'P17']) },
  { id: 'limites', titulo: 'Límites y mercado', ids: Object.freeze(['P18', 'P20', 'P23']) },
  { id: 'campana', titulo: 'Campaña y firma', ids: Object.freeze(['P19', 'P24']) },
  { id: 'cumplimiento', titulo: 'Cumplimiento', ids: Object.freeze(['P25']) },
]);

/** Agrupa `modeloPreflight().filas` para la cuadrícula de semáforos; cada grupo con su recuento (los ítems sin grupo van a «Otros»). */
export function agruparPreflight(filas) {
  const porId = new Map((Array.isArray(filas) ? filas : []).map((f) => [f.id, f]));
  const usados = new Set();
  const armar = (g, fs) => ({
    id: g.id, titulo: g.titulo,
    filas: fs.map((f) => ({ ...f, nombre: NOMBRE_PREFLIGHT[f.id] || f.titulo })),
    resumen: { total: fs.length, verde: fs.filter((f) => f.estado === 'VERDE').length, amarillo: fs.filter((f) => f.estado === 'AMARILLO').length, rojo: fs.filter((f) => f.estado === 'ROJO').length, sinDato: fs.filter((f) => f.estado === 'sin_dato').length, noAplica: fs.filter((f) => f.estado === 'NO_APLICA').length },
  });
  const grupos = GRUPOS_PREFLIGHT.map((g) => {
    const fs = g.ids.map((id) => porId.get(id)).filter(Boolean);
    fs.forEach((f) => usados.add(f.id));
    return armar(g, fs);
  }).filter((g) => g.filas.length);
  const resto = (Array.isArray(filas) ? filas : []).filter((f) => !usados.has(f.id));
  if (resto.length) grupos.push(armar({ id: 'otros', titulo: 'Otros' }, resto));
  return grupos;
}

const MACROS_URL = Object.freeze(['{{campaign.name}}', '{{ad.name}}', '{{adset.name}}', '{{campaign.id}}', '{{adset.id}}', '{{ad.id}}']);

function lista(v) { return Array.isArray(v) ? v : []; }
function objeto(v) { return v && typeof v === 'object' && !Array.isArray(v) ? v : {}; }
function txt(v, max = 200) { return neutralizar(v, { max }); }
function esEntero(n) { return typeof n === 'number' && Number.isSafeInteger(n); }
function tiempo(s) { const t = typeof s === 'string' ? Date.parse(s) : NaN; return Number.isFinite(t) ? t : null; }

/** `hash` sha256:<64 hex> → «sha256:2be24a1d…57ed». */
export function hashCorto(h) {
  const s = String(h ?? '');
  const m = /^(sha256:)([0-9a-f]{64})$/.exec(s);
  return m ? `${m[1]}${m[2].slice(0, 8)}…${m[2].slice(-4)}` : txt(s, 40);
}

// ───────────────────────── campana.json ─────────────────────────

/** Trozos de una URL con macros, marcando cuáles son macros ({{…}}) para pintarlas distinto (todo sigue siendo TEXTO). */
export function trozosUrlMacros(plantilla) {
  const s = String(plantilla ?? '');
  const out = [];
  const re = /\{\{[a-z][a-z0-9_.]{0,40}\}\}/g;
  let i = 0;
  let m;
  while ((m = re.exec(s)) !== null) {
    if (m.index > i) out.push({ texto: txt(s.slice(i, m.index), 400), macro: false });
    out.push({ texto: m[0], macro: true });
    i = m.index + m[0].length;
  }
  if (i < s.length) out.push({ texto: txt(s.slice(i), 400), macro: false });
  return out;
}

/** Comprobaciones de la URL: macros presentes, ejemplo resuelto sin vacíos ni llaves. (Indicios; la verdad es meta.preflight P13.) */
export function revisarUrl(url) {
  const u = objeto(url);
  const pl = typeof u.plantilla === 'string' ? u.plantilla : '';
  const ej = typeof u.ejemplo_resuelto === 'string' ? u.ejemplo_resuelto : '';
  const faltan = pl ? MACROS_URL.filter((m) => !pl.includes(m)) : [...MACROS_URL];
  const vaciosEnEjemplo = ej ? /[?&][A-Za-z_]+=(?:&|$)/.test(ej) || ej.includes('{{') : null;
  return {
    plantilla: pl,
    ejemplo: ej,
    trozos: trozosUrlMacros(pl),
    macrosFaltan: faltan,
    macrosOk: pl !== '' && faltan.length === 0,
    ejemploOk: ej === '' ? null : !vaciosEnEjemplo,
    https: pl ? pl.startsWith('https://') : null,
  };
}

const RE_NOMBRE_OK = /^[\x21-\x7B\x7D-\x7E]+$/; // ASCII visible, sin espacio ni «|»

/** Nombres de campaña/conjunto/anuncios (5.2: ASCII, «_», sin «|»). Indicio; la comprobación real es P19. */
export function revisarNombres(nombres) {
  const n = objeto(nombres);
  const items = [];
  const una = (rol, v) => {
    const s = typeof v === 'string' ? v : '';
    items.push({ rol, nombre: txt(s, 120), ok: s !== '' && RE_NOMBRE_OK.test(s) && !s.includes('|'), motivo: s === '' ? 'vacío' : !RE_NOMBRE_OK.test(s) || s.includes('|') ? 'caracteres no permitidos (sin tildes ni emojis, sin espacios ni «|»)' : null });
  };
  una('Campaña', n.campana);
  una('Conjunto', n.conjunto);
  lista(n.anuncios).forEach((a, i) => una(`Anuncio ${i + 1}`, a));
  return { items, ok: items.length > 0 && items.every((i) => i.ok) };
}

/** Presupuesto en unidad menor entera con su moneda y decimales; más comprobaciones aritméticas con enteros (indicios). */
export function modeloPresupuesto(presupuesto) {
  const p = objeto(presupuesto);
  if (!Object.keys(p).length) return null;
  const mon = typeof p.moneda === 'string' ? p.moneda : '';
  const dec = Number.isInteger(p.decimales) ? p.decimales : undefined;
  const d = (v) => (v === null || v === undefined ? 'sin dato' : dinero(v, mon, dec));
  const comprobaciones = [];
  if (esEntero(p.diario) && esEntero(p.dias) && esEntero(p.total_test)) {
    comprobaciones.push({ id: 'total', texto: `diario × días = ${d(p.diario * p.dias)} · total de la prueba ${d(p.total_test)}`, estado: p.diario * p.dias === p.total_test ? 'ok' : 'aviso', nota: p.diario * p.dias === p.total_test ? null : 'el total difiere de diario × días (puede ser redondeo: revisar)' });
  }
  if (p.spend_cap === null || p.spend_cap === undefined) {
    const c = objeto(p.candado_alternativo);
    comprobaciones.push({ id: 'cap', texto: 'sin tope de gasto → exige un freno alternativo (fecha de fin + presupuesto total)', estado: Object.keys(c).length ? 'ok' : 'error', nota: Object.keys(c).length ? null : 'sin freno alternativo: Meta no tendría un tope de gasto' });
  } else if (esEntero(p.spend_cap) && esEntero(p.total_test)) {
    comprobaciones.push({ id: 'cap', texto: `tope de gasto ${d(p.spend_cap)} ≥ total de la prueba ${d(p.total_test)}`, estado: p.spend_cap >= p.total_test ? 'ok' : 'error', nota: p.spend_cap >= p.total_test ? null : 'el tope de gasto es menor que el total de la prueba' });
    if (esEntero(p.spend_cap_minimo_meta)) {
      comprobaciones.push({ id: 'capmin', texto: `tope de gasto ${d(p.spend_cap)} ≥ mínimo de Meta ${d(p.spend_cap_minimo_meta)}`, estado: p.spend_cap >= p.spend_cap_minimo_meta ? 'ok' : 'aviso', nota: p.spend_cap >= p.spend_cap_minimo_meta ? null : 'bajo el mínimo de Meta: hace falta el freno alternativo' });
    }
  }
  if (esEntero(p.max_teorico_diario) && esEntero(p.diario)) {
    comprobaciones.push({ id: 'techo', texto: `techo teórico diario ${d(p.max_teorico_diario)} ≥ diario ${d(p.diario)}`, estado: p.max_teorico_diario >= p.diario ? 'ok' : 'error', nota: null });
  }
  return {
    moneda: mon, decimales: dec ?? null,
    diario: d(p.diario), total: d(p.total_test), dias: esEntero(p.dias) ? p.dias : null,
    spendCap: p.spend_cap === null || p.spend_cap === undefined ? 'sin tope' : d(p.spend_cap), spendCapMinimo: d(p.spend_cap_minimo_meta), maxTeoricoDiario: d(p.max_teorico_diario),
    candado: p.candado_alternativo ? Object.entries(objeto(p.candado_alternativo)).map(([k, v]) => [txt(k, 30), typeof v === 'object' ? txt(JSON.stringify(v), 120) : txt(v, 80)]) : null,
    comprobaciones,
  };
}

/** Estructura de la campaña en palabras: {texto, sigla}. CBO = el presupuesto se comparte entre todos los anuncios y Meta lo reparte. */
export function estructuraTexto(estructura) {
  const e = typeof estructura === 'string' ? estructura.toUpperCase() : '';
  if (e === 'CBO') return { texto: 'Campaña con presupuesto compartido', sigla: 'CBO' };
  if (e === 'ABO') return { texto: 'Presupuesto separado por conjunto de anuncios', sigla: 'ABO' };
  return { texto: txt(estructura, 20) || 'sin dato', sigla: null };
}

/** Modelo de campana.json. `null` si no hay campaña. */
export function modeloCampana(campana) {
  const c = objeto(campana);
  if (!Object.keys(c).length) return null;
  const eco = objeto(c.economia);
  const mon = objeto(c.presupuesto).moneda;
  const dec = objeto(c.presupuesto).decimales;
  const e = (v) => dinero(v, mon, Number.isInteger(dec) ? dec : undefined);
  const aud = objeto(c.audiencia);
  const rp = objeto(c.reglas_parada);
  const cv = objeto(c.criterio_validada);
  const anuncios = lista(c.anuncios).map((a) => ({
    nombre: txt(a.ad_name, 80), concepto: txt(a.concepto_id, 60),
    sha: typeof a.asset_sha256 === 'string' ? a.asset_sha256 : null, claims: lista(a.claim_ids).map((x) => txt(x, 60)),
  }));
  return {
    oferta: txt(c.oferta_id, 20), version: txt(c.version, 12), schema: txt(c.schema_version, 12),
    estado: typeof c.estado === 'string' ? c.estado : null,
    fase: txt(c.fase, 20), estructura: txt(c.estructura, 20), estructuraTexto: estructuraTexto(c.estructura), objetivo: txt(c.objetivo, 30), evento: txt(c.evento_optimizacion, 30),
    atribucion: Object.entries(objeto(c.atribucion)).map(([k, v]) => [txt(k, 40), txt(v, 60)]),
    paises: lista(c.paises).map((p) => txt(p, 4)), idioma: txt(c.idioma, 10),
    presupuesto: modeloPresupuesto(c.presupuesto),
    economia: Object.keys(eco).length ? {
      cpaEquilibrio: e(eco.cpa_equilibrio), cpaObjetivo: e(eco.cpa_objetivo), cpaMax: e(eco.cpa_max),
      kCorte: esEntero(eco.k_corte) ? eco.k_corte : null, nAnuncios: esEntero(eco.n_anuncios) ? eco.n_anuncios : null,
    } : null,
    specialAdCategories: lista(c.special_ad_categories).map((x) => txt(x, 40)),
    audiencia: Object.keys(aud).length ? {
      tipo: txt(aud.tipo, 20), edad: esEntero(aud.edad_min) && esEntero(aud.edad_max) ? `${aud.edad_min}–${aud.edad_max}` : null, genero: txt(aud.genero, 12),
      intereses: lista(aud.intereses).length, excluyeSensibles: aud.excluye_categorias_sensibles === true,
    } : null,
    ubicaciones: txt(c.ubicaciones, 30),
    nombres: { campana: txt(objeto(c.nombres).campana, 120), conjunto: txt(objeto(c.nombres).conjunto, 120), anuncios: lista(objeto(c.nombres).anuncios).map((a) => txt(a, 80)) },
    revisionNombres: revisarNombres(c.nombres),
    url: revisarUrl(c.url),
    anuncios,
    reglasParada: Object.keys(rp).length ? { kCorte: esEntero(rp.k_corte) ? rp.k_corte : null, hashParametros: typeof rp.hash_parametros === 'string' ? rp.hash_parametros : null, pausaGlobalSi: lista(rp.pausa_global_si).map((x) => txt(x, 160)) } : null,
    criterioValidada: Object.keys(cv).length ? [['definición', txt(cv.definicion, 40)], ['decisiones (n_dec)', esEntero(cv.n_dec) ? String(cv.n_dec) : '—'], ['días máx.', esEntero(cv.dias_max) ? String(cv.dias_max) : '—']] : null,
    hashConfig: typeof c.hash_config === 'string' ? c.hash_config : null,
    idsMetaEnCampana: c.ids_meta ? true : false,
  };
}

// ───────────────────────── preflight ─────────────────────────

/**
 * Modelo del preflight P01–P25: semáforo global, vigencia, coincidencia de hash con campana.json y una fila por ítem
 * (estado = VERDE|AMARILLO|ROJO|NO_APLICA|sin_dato). `ahora` es epoch ms (inyectable en pruebas).
 */
export function modeloPreflight({ preflight = null, campana = null, ahora = Date.now() } = {}) {
  const p = objeto(preflight);
  if (!Object.keys(p).length) return null;
  const checks = objeto(p.checks);
  const cats = lista(objeto(campana).special_ad_categories);
  const exigeP25 = cats.length > 0;
  const filas = PREFLIGHT.filter((x) => !x.condicional || exigeP25 || checks[x.id] !== undefined).map((x) => {
    const c = objeto(checks[x.id]);
    const estado = typeof c.estado === 'string' ? c.estado : null;
    return {
      id: x.id, titulo: x.titulo, ambito: x.ambito, condicional: x.condicional === true,
      estado: estado && TONO_SEMAFORO[estado] !== undefined ? estado : 'sin_dato',
      tono: estado && TONO_SEMAFORO[estado] !== undefined ? TONO_SEMAFORO[estado] : 'neutro',
      evidencia: txt(c.evidencia, 300) || null,
    };
  });
  const cuenta = (e) => filas.filter((f) => f.estado === e).length;
  const hasta = tiempo(p.valido_hasta);
  const generado = tiempo(p.generado_en);
  const vigente = hasta === null ? null : ahora <= hasta;
  const hashCoincide = typeof p.hash_config === 'string' && objeto(campana).hash_config ? p.hash_config === campana.hash_config : null;
  const semaforo = typeof p.semaforo === 'string' && TONO_SEMAFORO[p.semaforo] !== undefined ? p.semaforo : null;
  // El semáforo declarado se contrasta con los ítems: uno ROJO (o sin dato) impide el VERDE.
  const peor = cuenta('ROJO') ? 'ROJO' : cuenta('AMARILLO') ? 'AMARILLO' : cuenta('sin_dato') ? 'sin_dato' : 'VERDE';
  const incoherente = semaforo === 'VERDE' && peor !== 'VERDE';
  const problemas = [];
  if (vigente === false) problemas.push('El chequeo antes de lanzar venció (ya pasó su fecha de validez): hay que repetirlo antes de activar.');
  if (hashCoincide === false) problemas.push('El chequeo es de OTRA versión de la campaña (su huella no coincide): la campaña cambió después y por eso no vale.');
  if (incoherente) problemas.push('El semáforo general dice verde pero hay puntos que no lo son: no se confía en él.');
  if (cuenta('sin_dato')) problemas.push(`${cuenta('sin_dato')} punto(s) sin resultado en el archivo del chequeo.`);
  const habilita = semaforo === 'VERDE' && vigente === true && hashCoincide !== false && !incoherente && cuenta('sin_dato') === 0 && cuenta('ROJO') === 0;
  return {
    semaforo, tono: semaforo ? TONO_SEMAFORO[semaforo] : 'neutro',
    generadoEn: typeof p.generado_en === 'string' ? p.generado_en : null, validoHasta: typeof p.valido_hasta === 'string' ? p.valido_hasta : null,
    vigente, hashCoincide, hashConfig: typeof p.hash_config === 'string' ? p.hash_config : null,
    horasGenerado: generado === null ? null : Math.max(0, Math.round(((ahora - generado) / 3600000) * 10) / 10),
    filas,
    resumen: { verde: cuenta('VERDE'), amarillo: cuenta('AMARILLO'), rojo: cuenta('ROJO'), noAplica: cuenta('NO_APLICA'), sinDato: cuenta('sin_dato'), total: filas.length },
    problemas,
    habilita,
    nota: 'Un chequeo hecho en modo de ensayo («fixture», registrado en lanzamiento.log) nunca habilita activar; el modo no viaja en el archivo del chequeo.',
  };
}

// ───────────────────────── ids de Meta y aprobación ─────────────────────────

/** ids_meta.json (o campana.ids_meta). */
export function modeloIdsMeta(ids, campana) {
  const i = objeto(ids);
  if (!Object.keys(i).length) return null;
  const adsets = lista(i.adset_ids).map(String);
  const ads = lista(i.ad_ids).map(String);
  const creativos = lista(i.creative_ids).map(String);
  const hash = typeof i.hash_config === 'string' ? i.hash_config : null;
  const hc = objeto(campana).hash_config;
  return {
    cuenta: txt(i.ad_account_id, 30) || null,
    campaignId: i.campaign_id ? txt(i.campaign_id, 30) : null,
    adsetIds: adsets.map((x) => txt(x, 30)), adIds: ads.map((x) => txt(x, 30)), creativeIds: creativos.map((x) => txt(x, 30)),
    creadoEn: typeof i.creado_en === 'string' ? i.creado_en : null,
    hashConfig: hash, hashCoincide: hash && hc ? hash === hc : null,
    objetosActivables: (i.campaign_id ? 1 : 0) + adsets.length + ads.length,
  };
}

/** Conjunto de IDs que `meta.activar` enciende: campaña + conjuntos + anuncios (no creativos). */
export function objectIdsDe(ids) {
  const i = objeto(ids);
  const s = new Set();
  if (i.campaign_id) s.add(String(i.campaign_id));
  lista(i.adset_ids).forEach((x) => s.add(String(x)));
  lista(i.ad_ids).forEach((x) => s.add(String(x)));
  return s;
}

function igualesConjuntos(a, b) {
  if (a.size !== b.size) return false;
  for (const x of a) if (!b.has(x)) return false;
  return true;
}

/** aprobacion.json (orden firmada): contra hash_config, ids_meta y vigencia. */
export function modeloAprobacion({ aprobacion = null, campana = null, idsMeta = null, ahora = Date.now() } = {}) {
  const a = objeto(aprobacion);
  if (!Object.keys(a).length) return null;
  const por = objeto(a.aprobado_por);
  const hasta = tiempo(a.vigencia_hasta);
  const hc = objeto(campana).hash_config;
  const oid = new Set(lista(a.object_ids).map(String));
  const ids = objectIdsDe(idsMeta);
  const problemas = [];
  const vigente = hasta === null ? null : ahora <= hasta;
  if (vigente === false) problemas.push('La aprobación venció (ya pasó su fecha de validez).');
  const hashCoincide = typeof a.hash_objetivo === 'string' && hc ? a.hash_objetivo === hc : null;
  if (hashCoincide === false) problemas.push('La aprobación es de OTRA versión de la campaña: la campaña cambió después de firmar.');
  const idsCoinciden = ids.size ? igualesConjuntos(oid, ids) : null;
  if (idsCoinciden === false) problemas.push('Los códigos aprobados no son exactamente los del borrador en Meta (campaña + conjuntos + anuncios).');
  const humano = por.tipo === 'humano';
  if (a.gate === 'H' && !humano) problemas.push('Falta el aprobador humano: esta orden necesita tu firma personal.');
  if (a.gate === 'H' && humano && !por.firma) problemas.push('La orden no trae firma.');
  return {
    accion: txt(a.accion, 40), gate: txt(a.gate, 4), nivel: txt(a.nivel, 4),
    aprobadoPor: { tipo: txt(por.tipo, 12), id: txt(por.id, 40), fecha: typeof por.fecha === 'string' ? por.fecha : null, firmada: !!por.firma, firmaCorta: typeof por.firma === 'string' ? `${por.firma.slice(0, 20)}…` : null },
    hashObjetivo: typeof a.hash_objetivo === 'string' ? a.hash_objetivo : null, hashCoincide,
    objectIds: [...oid].map((x) => txt(x, 30)), idsCoinciden,
    creadoEn: typeof a.creado_en === 'string' ? a.creado_en : null, vigenciaHasta: typeof a.vigencia_hasta === 'string' ? a.vigencia_hasta : null, vigente,
    problemas, valida: problemas.length === 0 && vigente === true,
  };
}

/** Comando para que UNA PERSONA firme la activación en su terminal. El panel no firma ni ejecuta nada. null si el id no es válido. */
export function comandoFirmar(ofertaId) {
  if (!RE_OFERTA_REAL.test(String(ofertaId))) return null; // la orden firmada lleva el id real (OF-AAAAMM-NN), no el nombre de una carpeta demo
  return `.venv/bin/python -m engine.orq firmar --oferta ${ofertaId} --accion activar_campana --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno`;
}

/** Comando de lectura que arma/actualiza el preflight (solo lectura en Meta). null si el id no es válido. */
export function comandoPreflight(ofertaId) {
  if (!RE_OFERTA_ID.test(String(ofertaId))) return null;
  return `.venv/bin/python -m meta.preflight --oferta ${ofertaId}`;
}

// ───────────────────────── ciclo de estado ─────────────────────────

/**
 * Estado declarado en campana.json y recorrido borrador → preflight_ok → aprobada → activa (pausada/cerrada aparte).
 * El estado se LEE de los archivos; este módulo no lo cambia.
 */
export function modeloCiclo(estado) {
  const e = typeof estado === 'string' ? estado : null;
  const idx = CICLO.indexOf(e);
  const pasos = CICLO.map((id, i) => ({
    id,
    texto: { borrador: 'Borrador', preflight_ok: 'Chequeo OK', aprobada: 'Aprobada', activa: 'Activa' }[id],
    detalle: { borrador: 'Armada, sin revisar', preflight_ok: 'Revisión previa en verde', aprobada: 'Con tu firma', activa: 'Emitiendo anuncios' }[id],
    estado: idx === -1 ? 'pendiente' : i < idx ? 'hecho' : i === idx ? 'actual' : 'pendiente',
  }));
  return { actual: e, conocido: e !== null && (idx !== -1 || OTROS_ESTADOS.includes(e)), pasos, fueraDeCiclo: OTROS_ESTADOS.includes(e) ? e : null };
}

/** Siguiente paso humano y lo que bloquea, a partir de todo lo leído. */
export function siguientePaso({ campana, preflight, idsMeta, aprobacion }) {
  const c = objeto(campana);
  if (!Object.keys(c).length) return { texto: 'Todavía no hay campaña armada: la prepara la etapa Campaña (D7) cuando están listas la página de venta (D5) y los anuncios (D6).', tono: 'neutro', bloqueos: [] };
  const bloqueos = [];
  if (!idsMeta) bloqueos.push('Aún no existe el borrador en Meta (todo se crea en pausa).');
  if (!preflight) bloqueos.push('Falta el chequeo antes de lanzar (la revisión previa de 25 puntos).');
  else {
    if (preflight.vigente === false) bloqueos.push('El chequeo antes de lanzar está vencido.');
    if (preflight.hashCoincide === false) bloqueos.push('El chequeo es de otra versión de la campaña: cambió después de revisarla.');
    if (preflight.resumen.rojo) bloqueos.push(`${preflight.resumen.rojo} punto${preflight.resumen.rojo === 1 ? '' : 's'} del chequeo en rojo.`);
  }
  if (idsMeta && idsMeta.hashCoincide === false) bloqueos.push('El borrador de Meta es de otra versión de la campaña.');
  if (!aprobacion) bloqueos.push('Falta tu firma de aprobación.');
  else if (!aprobacion.valida) bloqueos.push(...aprobacion.problemas);
  const est = c.estado;
  let texto;
  if (est === 'activa') texto = 'La campaña figura como activa: se vigila desde Resultados.';
  else if (est === 'pausada') texto = 'La campaña está pausada; reanudarla es una decisión humana aparte.';
  else if (est === 'cerrada') texto = 'La campaña está cerrada.';
  else if (!idsMeta) texto = 'Siguiente: crear el borrador en Meta (todo queda en pausa) y hacer el chequeo antes de lanzar.';
  else if (!preflight || !preflight.habilita) texto = 'Siguiente: dejar el chequeo antes de lanzar en verde y vigente para la configuración actual.';
  else if (!aprobacion) texto = 'Siguiente (tuyo): firmar la activación con el comando de abajo, en tu terminal.';
  else if (!aprobacion.valida) texto = 'La aprobación existente no es válida: hay que firmar de nuevo.';
  else texto = 'Aprobación vigente: la activación la hace el sistema automático, no este panel.';
  return { texto, tono: bloqueos.length ? 'aviso' : 'ok', bloqueos };
}

/** Todo junto: lo que pinta la pantalla. `datos` = GET /campanas/<id>. */
export function modeloCampanas(datos, { ofertaId = null, ahora = Date.now() } = {}) {
  const d = objeto(datos);
  const campanaRaw = d.campana && typeof d.campana === 'object' ? d.campana : null;
  const idsRaw = (d.ids_meta && typeof d.ids_meta === 'object' ? d.ids_meta : null) || (campanaRaw && campanaRaw.ids_meta && typeof campanaRaw.ids_meta === 'object' ? campanaRaw.ids_meta : null);
  const campana = modeloCampana(campanaRaw);
  const preflight = modeloPreflight({ preflight: d.preflight, campana: campanaRaw, ahora });
  const idsMeta = modeloIdsMeta(idsRaw, campanaRaw);
  const aprobacion = modeloAprobacion({ aprobacion: d.aprobacion, campana: campanaRaw, idsMeta: idsRaw, ahora });
  // `estado` puede ser la cadena del estado de la campaña o el objeto del panel {etapa, gate_pendiente, campana, fase}
  const est = d.estado && typeof d.estado === 'object' && !Array.isArray(d.estado) ? d.estado : null;
  const estadoDeclarado = typeof d.estado === 'string' ? d.estado
    : (est && typeof est.campana === 'string' ? est.campana : (est && typeof est.estado === 'string' ? est.estado : (campana ? campana.estado : null)));
  const etapaD7 = est ? {
    estado: typeof est.etapa === 'string' ? est.etapa : null,
    gatePendiente: est.gate_pendiente === true ? true : est.gate_pendiente === false ? false : null,
    fase: typeof est.fase === 'string' ? txt(est.fase, 30) : null,
  } : null;
  const ciclo = modeloCiclo(estadoDeclarado);
  // el comando de firma lleva el id REAL de la oferta: el de campana.json (o el del panel si ya es real); la carpeta demo «_ejemplo» no vale
  const oferta = campana && RE_OFERTA_REAL.test(campana.oferta) ? campana.oferta : (RE_OFERTA_REAL.test(String(ofertaId)) ? ofertaId : null);
  const paso = siguientePaso({ campana: campanaRaw, preflight, idsMeta, aprobacion });
  const hayDivergencia = campana && estadoDeclarado && campana.estado && estadoDeclarado !== campana.estado;
  return {
    hayCampana: campana !== null,
    campana, preflight, idsMeta, aprobacion, ciclo, paso, etapaD7,
    firma: {
      pendiente: campana !== null && !(aprobacion && aprobacion.valida) && !['activa', 'pausada', 'cerrada'].includes(estadoDeclarado),
      comando: oferta ? comandoFirmar(oferta) : null,
      hashObjetivo: campana ? campana.hashConfig : null,
      objectIds: idsMeta ? [...objectIdsDe(idsRaw)] : [],
      nota: 'El comando sigue el manual de pruebas (docs/10-runbook-testeo.md §1.3) y queda pendiente hasta que el sistema automático exista. Lo ejecuta una persona en su terminal; el panel no firma, no activa y no publica.',
    },
    avisos: hayDivergencia ? [`El estado que informa el sistema (${txt(estadoDeclarado, 20)}) no coincide con el que figura en la campaña (${txt(campana.estado, 20)}).`] : [],
  };
}
