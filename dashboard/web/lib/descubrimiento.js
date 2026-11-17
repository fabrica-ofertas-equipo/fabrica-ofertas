// lib/descubrimiento.js — lógica PURA (datos → modelo de vista) del radar de ofertas (#/descubrimiento).
// Sin DOM, sin red: la prueba `tests/dashboard/test_web_descubrimiento.mjs` la ejercita con node --test.
//
// Fuentes (empresa/barrido/**, formatos de scripts/modelado/barrido/CONTRATO.md):
//   candidatos/<corrida>.json            temas, sin_tema, resumen, matriz_tema_pais, exportadores, descartadas
//   candidatos/<corrida>/fichas_borrador.json   fichas 2.0.0 (PM incompleto)
//   paginas/<corrida>.json               una entrada por página (títulos, medición por país…)
//   etiquetas/<corrida>/consolidado.json  etiquetas aceptadas, señales de riesgo, sin etiquetar
//   planes/<corrida>[.pasada-3].json      plan de consultas
//
// REGLAS QUE ESTE MÓDULO HACE CUMPLIR
//  - Todo texto que viene de la Biblioteca de Anuncios (títulos, nombres de página, frases de búsqueda) es NO
//    CONFIABLE: `neutralizar` quita controles bidi (U+202A–202E, 2066–2069…), de formato y de control, y acota el largo.
//  - Un conteo sobre muestra truncada es un PISO, nunca un total (`anunciosEsPiso`, `edadEsPiso`).
//  - La ausencia de un tema en un país es una HIPÓTESIS hasta medirla (pasada 3), nunca un hecho.
//  - `null` significa «sin dato / sin evaluar»: jamás se convierte en 0 ni en «no».

export const UMBRAL_DEFECTO = Object.freeze({ anuncios: 15, edad: 10 });

/** Umbral de tracción {anuncios, edad} (números) a partir de `umbrales_traccion` del ranking ({anuncios_activos, edad_oferta_dias}). */
export function normalizarUmbral(u) {
  const o = u && typeof u === 'object' ? u : {};
  const a = aNumero(o.anuncios_activos ?? o.anuncios);
  const e = aNumero(o.edad_oferta_dias ?? o.edad);
  return { anuncios: a ?? UMBRAL_DEFECTO.anuncios, edad: e ?? UMBRAL_DEFECTO.edad, declarado: a !== null && e !== null };
}

export const ESTADOS_TRACCION = Object.freeze({
  pasa: { texto: 'Pasa la tracción', tono: 'ok' },
  indeterminada_por_muestra: { texto: 'Por medir', tono: 'aviso' },
  no_pasa: { texto: 'No alcanza', tono: 'error' },
});

/** «al menos 15 anuncios activos y 10 días de antigüedad»: el mínimo exigido para la tracción, en palabras. */
export function textoMinimo(umbral) {
  const u = umbral || UMBRAL_DEFECTO;
  return `al menos ${num(u.anuncios)} anuncios activos y ${num(u.edad)} días de antigüedad`;
}

export const URL_FICHA_ANUNCIO = /^https:\/\/www\.facebook\.com\/ads\/library\/\?id=(\d{1,25})$/;

// ───────────────────────── texto no confiable ─────────────────────────

// Caracteres que cambian el orden visual u ocultan texto: controles bidi (LRE/RLE/PDF/LRO/RLO, LRI/RLI/FSI/PDI, LRM/RLM, ALM), espacios de ancho
// nulo y anotaciones. Se dejan pasar U+200C/U+200D (ZWNJ/ZWJ: emojis compuestos y escrituras que los necesitan) y el guion blando.
// No se borran en silencio: se MUESTRAN como «⟦U+202E⟧» (igual que ui.js) para que un título tramposo se note.
// eslint-disable-next-line no-misleading-character-class
const RE_BIDI = /[\u061C\u200B\u200E\u200F\u202A-\u202E\u2060\u2066-\u2069\uFEFF\u180E\uFFF9-\uFFFB]/g;
// eslint-disable-next-line no-control-regex
const RE_CONTROL = /[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F-\u009F]/g;
const RE_SEPARADORES = /[\u2028\u2029]/g;

function marcador(c) { return `⟦U+${c.charCodeAt(0).toString(16).toUpperCase().padStart(4, '0')}⟧`; }

export function tieneControlBidi(texto) {
  const s = String(texto ?? '');
  RE_BIDI.lastIndex = 0;
  const r = RE_BIDI.test(s);
  RE_BIDI.lastIndex = 0;
  return r;
}

/**
 * Texto de datos → texto seguro para MOSTRAR (siempre vía textContent; esto no es un escapado HTML, es higiene visual):
 * los controles bidi/de formato/C0 se hacen visibles («⟦U+202E⟧»), sin saltos de línea, espacios colapsados y,
 * si `max`, acotado con «…» (sin partir un par sustituto).
 */
export function neutralizar(texto, { max = 0 } = {}) {
  if (texto === null || texto === undefined) return '';
  let s = typeof texto === 'string' ? texto : String(texto);
  s = s.normalize('NFC').replace(RE_SEPARADORES, ' ').replace(RE_BIDI, marcador).replace(RE_CONTROL, marcador).replace(/\s+/g, ' ').trim();
  if (max > 0 && Array.from(s).length > max) {
    s = Array.from(s).slice(0, max - 1).join('').trimEnd() + '…';
  }
  return s;
}

/** URL de la ficha del anuncio en la Biblioteca (solo texto; el panel NUNCA la convierte en enlace). null si no es la forma esperada. */
export function urlFichaAnuncio(url) {
  if (typeof url !== 'string') return null;
  const m = URL_FICHA_ANUNCIO.exec(url.trim());
  return m ? `https://www.facebook.com/ads/library/?id=${m[1]}` : null;
}

// ───────────────────────── números y fechas ─────────────────────────

const FORMATO_ENTERO = (() => {
  try { return new Intl.NumberFormat('es-ES', { maximumFractionDigits: 0 }); } catch (_) { return null; }
})();

export function esNumero(n) { return typeof n === 'number' && Number.isFinite(n); }

/** Entero legible («1.980»); '—' si no es un número. */
export function num(n) {
  if (!esNumero(n)) return '—';
  return FORMATO_ENTERO ? FORMATO_ENTERO.format(n) : String(Math.round(n));
}

/** Convierte un decimal en cadena («36.0489…») o número en Number; null si no es finito. */
export function aNumero(v) {
  if (v === null || v === undefined || v === '') return null;
  const n = typeof v === 'number' ? v : Number(String(v).trim());
  return Number.isFinite(n) ? n : null;
}

/** «≥ 36 d» (piso) o «36 d». Los días son un dato medido, no dinero: un decimal de presentación basta. */
export function diasTexto(v, piso = false) {
  const n = aNumero(v);
  if (n === null) return '—';
  const t = n >= 100 ? String(Math.round(n)) : (Math.round(n * 10) / 10).toFixed(1).replace(/\.0$/, '').replace('.', ',');
  return `${piso ? '≥ ' : ''}${t} d`;
}

/** «0.9586» → «95,9 %». */
export function tasaTexto(v) {
  const n = aNumero(v);
  if (n === null) return '—';
  return `${(Math.round(n * 1000) / 10).toFixed(1).replace('.', ',')} %`;
}

export function conPiso(n, piso) {
  if (!esNumero(n)) return '—';
  return `${piso ? '≥ ' : ''}${num(n)}`;
}

// ───────────────────────── corridas ─────────────────────────

/** Corridas más recientes primero (por corrida_id, que es AAAA-MM-DD-<letra>). */
export function ordenarCorridas(lista) {
  const l = Array.isArray(lista) ? lista.filter((c) => c && typeof c.corrida_id === 'string') : [];
  return [...l].sort((a, b) => (a.corrida_id < b.corrida_id ? 1 : a.corrida_id > b.corrida_id ? -1 : 0));
}

/** Corrida a mostrar: la pedida si existe; si no, la más reciente. null si no hay ninguna. */
export function elegirCorrida(lista, pedida) {
  const ord = ordenarCorridas(lista);
  if (!ord.length) return null;
  return ord.find((c) => c.corrida_id === pedida) || ord[0];
}

// ───────────────────────── estado del barrido (dos formas) ─────────────────────────

function entero(v) { return esNumero(v) ? v : null; }
function qids(v) { return Array.isArray(v) ? v.map(String) : null; }

/**
 * Forma única del estado de una corrida. Acepta el de GET /descubrimiento/<c>/estado del panel
 * ({plan:{existe,consultas,tope_consultas}, crudo:{ok,error}, paginas:{existe,total}, etiquetas:{existe,cobertura}, memoria:{existe,ts},
 * candidatos:{existe,resumen}, fichas:{existe,total}, freno}) y el de `barrido estado --json`
 * ({plan:{consultas,tope}, crudos:{ok,con_error,sin_crudo,truncadas,…}, paginas:{existe,total,medicion}, etiquetado:{consolidado},
 * memoria:{instantanea,instantaneas,problemas}, candidatos:{existe}, fichas:{existe,ofertas}, freno_captura}). null si no hay estado.
 * Lo que no viene queda en null (nunca 0).
 */
export function normalizarEstado(e) {
  if (!e || typeof e !== 'object' || Array.isArray(e)) return null;
  const plan = e.plan && typeof e.plan === 'object' ? e.plan : {};
  const cr = (e.crudos && typeof e.crudos === 'object' ? e.crudos : null) || (e.crudo && typeof e.crudo === 'object' ? e.crudo : {});
  const cob = e.cobertura && typeof e.cobertura === 'object' ? e.cobertura : {};
  const pag = e.paginas && typeof e.paginas === 'object' ? e.paginas : {};
  const eti = e.etiquetas && typeof e.etiquetas === 'object' ? e.etiquetas : null;
  const eti2 = e.etiquetado && typeof e.etiquetado === 'object' ? e.etiquetado : null;
  const mem = e.memoria && typeof e.memoria === 'object' ? e.memoria : {};
  const cand = e.candidatos && typeof e.candidatos === 'object' ? e.candidatos : {};
  const fic = e.fichas && typeof e.fichas === 'object' ? e.fichas : {};
  const consolidado = (eti && eti.cobertura) || (eti2 && eti2.consolidado) || null;
  const ok = entero(cr.ok);
  const conError = entero(cr.con_error) ?? entero(cr.error);
  const consultas = entero(plan.consultas);
  let sinCrudo = entero(cr.sin_crudo);
  if (sinCrudo === null && consultas !== null && ok !== null) sinCrudo = Math.max(0, consultas - ok - (conError || 0));
  return {
    plan: { existe: plan.existe === true || consultas !== null, consultas, tope: entero(plan.tope_consultas) ?? entero(plan.tope), pasadas: Array.isArray(plan.pasadas) ? plan.pasadas : null },
    crudos: {
      ok, conError, sinCrudo, truncadas: entero(cr.truncadas), anunciosDistintos: entero(cr.anuncios_distintos),
      listas: { ok: qids(cob.consultas_ok) ?? qids(cr.consultas_ok), conError: qids(cob.con_error) ?? qids(cr.con_error_qids), sinCrudo: qids(cob.sin_crudo) ?? qids(cr.sin_crudo_qids), truncadas: qids(cob.truncadas) ?? qids(cr.truncadas_qids) },
    },
    paginas: { existe: pag.existe === true, total: entero(pag.total), medicion: pag.medicion && typeof pag.medicion === 'object' ? pag.medicion : null },
    etiquetado: { existe: !!(eti && eti.existe) || !!consolidado, cobertura: consolidado },
    memoria: { existe: mem.existe === true || mem.instantanea === true, instantaneas: entero(mem.instantaneas) ?? (mem.existe === true || mem.instantanea === true ? 1 : null), ts: typeof mem.ts === 'string' ? mem.ts : null, problemas: Array.isArray(mem.problemas) ? mem.problemas : [] },
    candidatos: { existe: cand.existe === true, resumen: cand.resumen && typeof cand.resumen === 'object' ? cand.resumen : null },
    fichas: { existe: fic.existe === true, total: entero(fic.total) ?? entero(fic.ofertas) },
    freno: e.freno !== undefined ? e.freno : (e.freno_captura !== undefined ? e.freno_captura : undefined),
  };
}

// ───────────────────────── freno de captura ─────────────────────────

/** Lo que de verdad significa el freno para el barrido (frase para el operador). */
export const CONSECUENCIA_FRENO = Object.freeze({
  libre: 'Nada detiene la captura. Aunque se pusiera, no afectaría al barrido con la herramienta de consulta (ruta A).',
  puesto: 'Detiene la captura con el navegador Chrome (ruta D). No afecta al barrido con la herramienta de consulta (ruta A): ese sigue corriendo.',
  sinDato: 'No se pudo leer el freno. Recuerda que nunca afecta al barrido con la herramienta de consulta (ruta A).',
});

/**
 * Estado del freno compartido (empresa/captura/freno.json). El panel lo MUESTRA; nunca lo borra: solo dice qué hacer a una persona.
 * `freno` = {activo, ts, motivo} | null (de GET /sistema o del estado del barrido).
 */
export function modeloFreno(freno) {
  if (freno === undefined) {
    return { conocido: false, activo: null, tono: 'neutro', titulo: 'Freno de la captura de anuncios: sin dato', motivo: null, ts: null, instruccion: null, alcance: null, consecuencia: CONSECUENCIA_FRENO.sinDato };
  }
  if (freno === null || freno.activo === false) {
    return { conocido: true, activo: false, tono: 'ok', titulo: 'Freno de la captura de anuncios: libre', motivo: null, ts: null, instruccion: null, alcance: null, consecuencia: CONSECUENCIA_FRENO.libre };
  }
  return {
    conocido: true,
    activo: true,
    tono: 'error',
    titulo: 'Freno de la captura de anuncios: puesto',
    motivo: neutralizar(freno.motivo, { max: 160 }) || 'sin motivo registrado',
    ts: typeof freno.ts === 'string' ? freno.ts : null,
    consecuencia: CONSECUENCIA_FRENO.puesto,
    alcance: 'No afecta a los agentes que usan la herramienta de consulta (ruta A); sí a toda captura hecha con Chrome (ruta D). Mientras esté puesto, la captura con Chrome no corre.',
    instruccion: 'Solo una persona lo levanta, a mano, después de revisar si fue una falsa alarma (se borra el archivo empresa/captura/freno.json). Ningún agente ni este panel lo borra ni se lo salta.',
  };
}

// ───────────────────────── resumen de la corrida ─────────────────────────

function tonoCupo(ok, tope) {
  if (!esNumero(ok) || !esNumero(tope) || tope <= 0) return 'neutro';
  if (ok > tope) return 'error';
  return ok / tope >= 0.9 ? 'aviso' : 'neutro';
}

function porc(a, b) {
  return esNumero(a) && esNumero(b) && b > 0 ? `${(Math.round((a / b) * 1000) / 10).toFixed(1).replace('.', ',')} %` : null;
}

/**
 * Tarjetas de resumen + avisos de «esto es un piso». `corrida` = elemento de GET /descubrimiento/corridas;
 * `candidatos` y `estado` pueden ser null. `freno` = {activo,ts,motivo}|null|undefined (undefined = desconocido).
 */
export function resumenCorrida({ corrida, candidatos = null, estado = null, freno }) {
  const c = corrida || {};
  const res = (candidatos && candidatos.resumen) || {};
  const est = normalizarEstado(estado);
  const med = res.paginas_por_medicion || (est && est.paginas.medicion) || null;
  const umbral = normalizarUmbral(candidatos && candidatos.umbrales_traccion);
  const cons = est ? est.etiquetado.cobertura : null;
  const f = modeloFreno(freno !== undefined ? freno : est ? est.freno : undefined);

  const detPaginas = med
    ? `Mínimo visto: ${num(med.completa)} medidas completas · ${num(med.parcial)} parciales · ${num(med.muestra)} solo muestra`
    : 'mínimo visto: solo las páginas que aparecen en las consultas hechas';
  const nTemasPasan = res.temas_pasan_traccion;
  const nSinTemaPasan = res.sin_tema_pasan_traccion;
  // `pasan_traccion` de la lista de corridas cuenta solo temas; con el resumen del ranking se suman las páginas sin tema que también pasan
  const pasan = esNumero(nTemasPasan) ? nTemasPasan + (nSinTemaPasan || 0) : (esNumero(c.pasan_traccion) ? c.pasan_traccion : null);
  const detPasan = esNumero(nTemasPasan)
    ? `${num(nTemasPasan)} temas + ${num(nSinTemaPasan || 0)} páginas sin tema · se pide ${textoMinimo(umbral)}`
    : `se pide ${textoMinimo(umbral)}`;

  const tarjetas = [
    {
      id: 'consultas', titulo: 'Consultas usadas',
      valor: esNumero(c.consultas_ok) && esNumero(c.consultas_tope) ? `${num(c.consultas_ok)} / ${num(c.consultas_tope)}` : num(c.consultas_ok),
      detalle: esNumero(c.consultas_tope) && esNumero(c.consultas_ok)
        ? `quedan ${num(Math.max(0, c.consultas_tope - c.consultas_ok))} (máximo por corrida, las 3 pasadas juntas)` : 'máximo por corrida sin dato',
      tono: tonoCupo(c.consultas_ok, c.consultas_tope),
    },
    { id: 'paginas', titulo: 'Páginas vistas', valor: conPiso(c.paginas, true), detalle: detPaginas, tono: 'neutro', piso: true },
    {
      id: 'etiquetadas', titulo: 'Clasificadas por IA', valor: num(c.etiquetadas),
      detalle: cons
        ? `${porc(c.etiquetadas, c.paginas) || ''} · en disputa ${num(cons.en_disputa)} · sin clasificar ${num(cons.sin_etiquetar)}`
        : (porc(c.etiquetadas, c.paginas) || 'sin detalle'),
      tono: 'neutro',
    },
    {
      id: 'candidatas', titulo: 'Candidatas', valor: num(c.candidatas),
      detalle: esNumero(res.paginas_descartadas)
        ? `${num(res.paginas_descartadas)} descartadas · ${num(res.paginas_por_verificar)} por verificar` : 'páginas que avanzan a medirse',
      tono: 'neutro',
    },
    { id: 'traccion', titulo: 'Pasan tracción', valor: num(pasan), detalle: detPasan, tono: esNumero(pasan) && pasan > 0 ? 'ok' : 'neutro' },
    { id: 'fichas', titulo: 'Fichas en borrador', valor: num(c.fichas), detalle: esNumero(c.fichas) && c.fichas > 0 ? 'Incompletas: faltan evaluar las puertas y la transferibilidad' : 'aún no hay fichas', tono: 'neutro' },
    { id: 'freno', titulo: 'Freno de captura', valor: !f.conocido ? '—' : f.activo ? 'Puesto' : 'Libre', detalle: f.activo ? f.motivo : f.conocido ? 'sin freno' : 'sin dato', tono: f.tono },
  ];

  const avisos = [];
  if (candidatos && Array.isArray(candidatos.advertencias)) {
    for (const a of candidatos.advertencias) {
      const t = neutralizar(a, { max: 400 });
      if (t) avisos.push(t);
    }
  }
  const pisos = [];
  if (med && esNumero(res.paginas_total)) {
    const noCompletas = (med.parcial || 0) + (med.muestra || 0);
    pisos.push(`${num(noCompletas)} de ${num(res.paginas_total)} páginas NO están medidas por completo: su cantidad de anuncios y su edad son un mínimo (al menos esa cifra), no el total. La herramienta de consulta entrega como mucho 50 anuncios por consulta.`);
  }
  return { tarjetas, avisos, pisos, freno: f, umbral };
}

// ───────────────────────── candidatos (tabla principal) ─────────────────────────

function lista(v) { return Array.isArray(v) ? v : []; }
function texto(v, max = 160) { return neutralizar(v, { max }); }

function exportadorDeTema(e) {
  if (!e || typeof e !== 'object') return { conSenal: null, evaluadas: null, monedas: [], paisesAnuncio: [], texto: '—', hay: false };
  const conteo = (clave, n) => (n === 1 ? clave : `${clave}×${n}`);
  const monedas = Object.entries(e.monedas || {}).map(([m, n]) => conteo(m, n));
  const paises = Object.entries(e.paises_anuncio || {}).map(([p, n]) => conteo(p, n));
  const hay = esNumero(e.con_senal) && e.con_senal > 0;
  return {
    conSenal: esNumero(e.con_senal) ? e.con_senal : null,
    evaluadas: esNumero(e.paginas_evaluadas) ? e.paginas_evaluadas : null,
    monedas, paisesAnuncio: paises,
    texto: hay ? `${monedas.join(' ')}${paises.length ? '→' + paises.join(' ') : ''} (${e.con_senal}/${e.paginas_evaluadas})` : (esNumero(e.sin_dato) && e.sin_dato > 0 ? 'sin dato' : 'sin indicio'),
    hay,
  };
}

function exportadorDePagina(e) {
  if (!e || typeof e !== 'object') return { conSenal: null, evaluadas: null, monedas: [], paisesAnuncio: [], texto: '—', hay: false, motivo: null };
  const senal = e.senal ?? e['señal'];
  const hay = senal === true;
  const moneda = typeof e.moneda === 'string' ? e.moneda : null;
  const pais = typeof e.pais_anuncio === 'string' ? e.pais_anuncio : null;
  return {
    conSenal: hay ? 1 : 0, evaluadas: 1,
    monedas: moneda ? [moneda] : [], paisesAnuncio: pais ? [pais] : [],
    texto: hay ? `${moneda || '?'}${pais ? ' → ' + pais : ''}` : senal === false ? 'sin indicio' : 'sin dato',
    hay, motivo: texto(e.motivo, 220) || null,
  };
}

/** Motivo legible (corto) del estado de tracción de un TEMA; todo sale de los campos del ranking, nada se inventa. El umbral va aparte. */
export function motivoTemaTraccion(t, umbral = normalizarUmbral(null)) {
  const con = esNumero(t.paginas_con_traccion) ? t.paginas_con_traccion : 0;
  const ind = esNumero(t.paginas_indeterminadas) ? t.paginas_indeterminadas : 0;
  const tot = esNumero(t.paginas_total) ? t.paginas_total : 0;
  switch (t.estado_traccion) {
    case 'pasa': return `${con}/${tot} páginas cumplen${ind ? ` · ${ind} indeterminada${ind === 1 ? '' : 's'}` : ''}`;
    case 'indeterminada_por_muestra': return `Lo visto no llega a ${num(umbral.anuncios)} anuncios y ${num(umbral.edad)} días: falta medir (pasada 3)`;
    case 'no_pasa': return `Medido y no alcanza ${num(umbral.anuncios)} anuncios y ${num(umbral.edad)} días`;
    default: return 'sin estado de tracción';
  }
}

/** Motivo legible (corto) de una PÁGINA (traccion_detalle {anuncios, edad}: cumple|no_cumple|indeterminada). */
export function motivoPaginaTraccion(p, umbral = normalizarUmbral(null)) {
  void umbral;
  const d = p.traccion_detalle || {};
  const t = (v) => (v === 'cumple' ? 'cumple' : v === 'no_cumple' ? 'no cumple' : v === 'indeterminada' ? 'por medir' : 'sin dato');
  return `anuncios: ${t(d.anuncios)} · edad: ${t(d.edad)}`;
}

/** «modelo_de_cobro» → frase humana de lo que falta confirmar (los ids viajan en `porVerificar`; esto es solo para mostrar). */
const POR_VERIFICAR_HUMANO = Object.freeze({
  modelo_de_cobro: 'Confirmar que cobra un pago único',
  tema: 'Confirmar de qué trata la oferta',
  original: 'Confirmar quién es el original',
});
export function porVerificarHumano(clave) {
  const k = String(clave ?? '');
  return POR_VERIFICAR_HUMANO[k] || texto(k.replace(/_/g, ' '), 60);
}

/**
 * Frase humana, en una línea, de POR QUÉ un candidato está en su estado de tracción. Todo sale de los campos del ranking:
 * nada se inventa. `tipo`: 'tema' | 'pagina'.
 */
export function explicacionTraccion(tipo, d, umbral = normalizarUmbral(null)) {
  const u = textoMinimo(umbral);
  const estado = d && d.estado_traccion;
  if (tipo === 'tema') {
    const con = esNumero(d.paginas_con_traccion) ? d.paginas_con_traccion : 0;
    const ind = esNumero(d.paginas_indeterminadas) ? d.paginas_indeterminadas : 0;
    const tot = esNumero(d.paginas_total) ? d.paginas_total : 0;
    if (estado === 'pasa') return `${con} de ${tot} página${tot === 1 ? '' : 's'} cumple${con === 1 ? '' : 'n'} el mínimo exigido (${u})${ind ? `; ${ind} sin medir del todo` : ''}.`;
    if (estado === 'indeterminada_por_muestra') return `Lo visto no llega al mínimo exigido (${u}), pero es solo una muestra: falta medirlo.`;
    if (estado === 'no_pasa') return `Medido y no alcanza el mínimo exigido (${u}).`;
    return 'Sin estado de tracción.';
  }
  const det = (d && d.traccion_detalle) || {};
  const parte = (v, que) => (v === 'cumple' ? `${que}: cumple` : v === 'no_cumple' ? `${que}: no cumple` : v === 'indeterminada' ? `${que}: solo se vio una parte (al menos esa cifra)` : `${que}: sin dato`);
  if (estado === 'pasa') return `Cumple el mínimo exigido (${u}).`;
  if (estado === 'indeterminada_por_muestra') return `${parte(det.anuncios, 'anuncios')} · ${parte(det.edad, 'edad')}. Falta medirla.`;
  if (estado === 'no_pasa') return `Medida y no alcanza el mínimo exigido (${u}): ${parte(det.anuncios, 'anuncios')} · ${parte(det.edad, 'edad')}.`;
  return 'Sin estado de tracción.';
}

/**
 * Progreso hacia el umbral de tracción para una barra: valor medido (o piso) frente al mínimo.
 * → {pct 0–100 (tope visual), supera: true|false|null, texto, piso}. `valor` null = sin dato (nunca 0).
 */
export function progresoUmbral(valor, minimo, { piso = false, unidad = '' } = {}) {
  const v = aNumero(valor);
  const m = aNumero(minimo);
  if (v === null || m === null || m <= 0) return { pct: 0, supera: null, texto: '—', piso: !!piso, sinDato: true };
  const redondeado = v >= 100 ? Math.round(v) : Math.round(v * 10) / 10;
  const t = (Math.round(v * 10) / 10 === Math.round(v) ? String(Math.round(v)) : String(redondeado).replace('.', ','));
  return {
    pct: Math.max(0, Math.min(100, Math.round((v / m) * 100))),
    supera: v >= m,
    texto: `${piso ? '≥ ' : ''}${t}${unidad ? ` ${unidad}` : ''}`,
    piso: !!piso,
    sinDato: false,
  };
}

function macroEtiqueta(m) {
  return typeof m === 'string' && m ? m : null;
}

/** Filas de TEMAS para la tabla principal. */
export function filasTemas(candidatos) {
  const umbral = normalizarUmbral(candidatos && candidatos.umbrales_traccion);
  return lista(candidatos && candidatos.temas).map((t, i) => {
    const pags = lista(t.paginas);
    const anunciosEsPiso = pags.length ? pags.some((p) => p.anuncios_activos_medidos_es_piso !== false && p.medicion_estado !== 'completa') : t.hay_muestra_truncada === true;
    const edadEsPiso = pags.length ? pags.some((p) => p.edad_es_piso === true) : t.hay_muestra_truncada === true;
    const ex = exportadorDeTema(t.exportadores);
    return {
      tipo: 'tema',
      id: String(t.tema_slug ?? `tema-${i}`),
      rank: esNumero(t.rank) ? t.rank : i + 1,
      nombre: texto(t.tema, 120) || texto(t.tema_slug, 120),
      slug: texto(t.tema_slug, 120),
      publicos: lista(t.publicos).map((x) => texto(x, 100)),
      estado: t.estado_traccion ?? null,
      estadoTexto: (ESTADOS_TRACCION[t.estado_traccion] || { texto: 'Sin estado' }).texto,
      estadoTono: (ESTADOS_TRACCION[t.estado_traccion] || { tono: 'neutro' }).tono,
      motivo: motivoTemaTraccion(t, umbral),
      explicacion: explicacionTraccion('tema', t, umbral),
      anunciantes: esNumero(t.anunciantes_independientes) ? t.anunciantes_independientes : null,
      paginas: esNumero(t.paginas_total) ? t.paginas_total : pags.length,
      anuncios: esNumero(t.anuncios_activos_traccion) ? t.anuncios_activos_traccion : (esNumero(t.anuncios_activos_en_muestra) ? t.anuncios_activos_en_muestra : null),
      anunciosEsPiso,
      edad: aNumero(t.edad_oferta_dias),
      edadEsPiso,
      paises: lista(t.paises).map(String),
      huecos: lista(t.huecos).map(String),
      macro: macroEtiqueta(t.macro_nicho),
      macroConteo: t.macro_nicho_conteo || null,
      exportador: ex,
      porVerificar: lista(t.por_verificar).map((x) => texto(x, 60)),
      porVerificarTexto: lista(t.por_verificar).map((x) => porVerificarHumano(x)),
      paginasPorVerificar: esNumero(t.paginas_por_verificar) ? t.paginas_por_verificar : null,
      mismoOperador: esNumero(t.paginas_posible_mismo_operador) ? t.paginas_posible_mismo_operador : 0,
      formatos: t.formatos && typeof t.formatos === 'object' ? t.formatos : {},
      entrantes: t.entrantes_30d && typeof t.entrantes_30d === 'object' ? t.entrantes_30d : null,
      novedad: t.novedad || null,
      nombresPaginas: pags.map((p) => texto(p.page_name, 80)),
      raw: t,
    };
  });
}

/** Filas de páginas «sin tema» (tema indeterminado con tracción): cada una es su propio candidato. */
export function filasSinTema(candidatos) {
  const umbral = normalizarUmbral(candidatos && candidatos.umbrales_traccion);
  return lista(candidatos && candidatos.sin_tema).map((p, i) => {
    const ex = exportadorDePagina(p.exportador);
    return {
      tipo: 'sin_tema',
      id: String(p.page_id ?? `sin-tema-${i}`),
      rank: esNumero(p.rank) ? p.rank : i + 1,
      nombre: texto(p.page_name, 120) || `página ${texto(p.page_id, 30)}`,
      slug: 'indeterminado',
      publicos: [],
      estado: p.estado_traccion ?? null,
      estadoTexto: (ESTADOS_TRACCION[p.estado_traccion] || { texto: 'Sin estado' }).texto,
      estadoTono: (ESTADOS_TRACCION[p.estado_traccion] || { tono: 'neutro' }).tono,
      motivo: motivoPaginaTraccion(p, umbral),
      explicacion: explicacionTraccion('pagina', p, umbral),
      anunciantes: p.cuenta_como_independiente === false ? 0 : 1,
      paginas: 1,
      anuncios: esNumero(p.anuncios_activos_traccion) ? p.anuncios_activos_traccion : (esNumero(p.anuncios_activos_medidos) ? p.anuncios_activos_medidos : null),
      anunciosEsPiso: p.anuncios_activos_medidos_es_piso !== false,
      edad: aNumero(p.edad_oferta_dias),
      edadEsPiso: p.edad_es_piso !== false,
      paises: lista(p.paises).map(String),
      huecos: lista(p.huecos).map(String),
      macro: macroEtiqueta(p.macro_nicho),
      macroConteo: null,
      exportador: ex,
      porVerificar: lista(p.por_verificar).map((x) => texto(x, 60)),
      porVerificarTexto: lista(p.por_verificar).map((x) => porVerificarHumano(x)),
      paginasPorVerificar: lista(p.por_verificar).length ? 1 : 0,
      mismoOperador: p.posible_mismo_operador ? 1 : 0,
      formatos: p.formato ? { [texto(p.formato, 40)]: 1 } : {},
      entrantes: p.entrantes_30d && typeof p.entrantes_30d === 'object' ? p.entrantes_30d : null,
      novedad: null,
      nombresPaginas: [texto(p.page_name, 80)],
      raw: p,
    };
  });
}

export const ORDENES = Object.freeze([
  { clave: 'rank', titulo: 'Ranking del barrido', dir: 'asc' },
  { clave: 'anunciantes', titulo: 'Anunciantes independientes', dir: 'desc' },
  { clave: 'anuncios', titulo: 'Anuncios medidos', dir: 'desc' },
  { clave: 'edad', titulo: 'Edad de la oferta', dir: 'desc' },
  { clave: 'paises', titulo: 'Nº de países', dir: 'desc' },
  { clave: 'nombre', titulo: 'Tema (A–Z)', dir: 'asc' },
]);

function valorOrden(f, clave) {
  switch (clave) {
    case 'rank': return f.rank;
    case 'anunciantes': return f.anunciantes;
    case 'anuncios': return f.anuncios;
    case 'edad': return f.edad;
    case 'paises': return f.paises.length;
    case 'nombre': return f.nombre.toLocaleLowerCase('es');
    default: return f.rank;
  }
}

/** Orden estable; los null/«sin dato» van SIEMPRE al final (nunca se tratan como 0). */
export function ordenarFilas(filas, { clave = 'rank', dir } = {}) {
  const def = ORDENES.find((o) => o.clave === clave) || ORDENES[0];
  const d = dir === 'asc' || dir === 'desc' ? dir : def.dir;
  const signo = d === 'asc' ? 1 : -1;
  return filas
    .map((f, i) => ({ f, i }))
    .sort((a, b) => {
      const va = valorOrden(a.f, def.clave);
      const vb = valorOrden(b.f, def.clave);
      const na = va === null || va === undefined || (typeof va === 'number' && !Number.isFinite(va));
      const nb = vb === null || vb === undefined || (typeof vb === 'number' && !Number.isFinite(vb));
      if (na && nb) return a.i - b.i;
      if (na) return 1;
      if (nb) return -1;
      if (va < vb) return -1 * signo;
      if (va > vb) return 1 * signo;
      return a.i - b.i;
    })
    .map((x) => x.f);
}

function normalizarBusqueda(s) {
  return String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLocaleLowerCase('es').trim();
}

/**
 * Filtros de vista (no descartan nada del barrido: son solo vista).
 *  q: texto en tema/slug/nombres de página · estado: clave de tracción · macro: 'salud'|'relaciones'|'dinero'|'ninguno'
 *  pais + paisModo ('presente'|'hueco') · exportador: true = con indicio · verificar: true = con por_verificar, false = sin
 *  tipo: 'tema'|'sin_tema'
 */
export function filtrarFilas(filas, f = {}) {
  const q = normalizarBusqueda(f.q);
  return filas.filter((r) => {
    if (f.tipo && r.tipo !== f.tipo) return false;
    if (f.estado && r.estado !== f.estado) return false;
    if (f.macro) {
      if (f.macro === 'ninguno') { if (r.macro) return false; } else if (r.macro !== f.macro) return false;
    }
    if (f.pais) {
      const presente = r.paises.includes(f.pais);
      if ((f.paisModo || 'presente') === 'hueco') {
        // hueco = ausente en la MUESTRA: solo para filas con la lista de huecos del ranking (o, si no la hay, la ausencia)
        const esHueco = r.huecos.length ? r.huecos.includes(f.pais) : !presente;
        if (!esHueco) return false;
      } else if (!presente) return false;
    }
    if (f.exportador === true && !r.exportador.hay) return false;
    if (f.verificar === true && !r.porVerificar.length) return false;
    if (f.verificar === false && r.porVerificar.length) return false;
    if (q) {
      const pajar = normalizarBusqueda(`${r.nombre} ${r.slug} ${r.nombresPaginas.join(' ')}`);
      if (!pajar.includes(q)) return false;
    }
    return true;
  });
}

/** Valores para los selectores de filtro, calculados de los datos (nunca fijos). */
export function opcionesFiltro(filas) {
  const paises = new Set();
  const macros = new Set();
  for (const f of filas) {
    f.paises.forEach((p) => paises.add(p));
    f.huecos.forEach((p) => paises.add(p));
    if (f.macro) macros.add(f.macro);
  }
  return { paises: [...paises].sort(), macros: [...macros].sort() };
}

/** Recorta para renderizar: pagina (desde 0), por_pagina; devuelve {filas, total, pagina, paginas, desde, hasta}. */
export function paginar(filas, pagina = 0, porPagina = 50) {
  const pp = Math.max(1, Math.floor(porPagina) || 50);
  const total = filas.length;
  const paginas = Math.max(1, Math.ceil(total / pp));
  const p = Math.min(Math.max(0, Math.floor(pagina) || 0), paginas - 1);
  const desde = p * pp;
  const corte = filas.slice(desde, desde + pp);
  return { filas: corte, total, pagina: p, paginas, desde: total ? desde + 1 : 0, hasta: desde + corte.length };
}

const PRIORIDAD_ESTADO = { pasa: 0, indeterminada_por_muestra: 1, no_pasa: 2 };

/** Orden inicial de la tabla: primero los que pasan tracción, luego indeterminados, luego los que no; dentro, más anunciantes primero. */
export function ordenarPorDefecto(filas) {
  return filas
    .map((f, i) => ({ f, i }))
    .sort((a, b) => {
      const pa = PRIORIDAD_ESTADO[a.f.estado] ?? 3;
      const pb = PRIORIDAD_ESTADO[b.f.estado] ?? 3;
      if (pa !== pb) return pa - pb;
      const xa = a.f.anunciantes ?? -1;
      const xb = b.f.anunciantes ?? -1;
      if (xa !== xb) return xb - xa;
      const ra = a.f.anuncios ?? -1;
      const rb = b.f.anuncios ?? -1;
      if (ra !== rb) return rb - ra;
      return a.i - b.i;
    })
    .map((x) => x.f);
}

// ───────────────────────── detalle de un tema / página ─────────────────────────

/** Fila de página dentro del detalle de un tema (de temas[].paginas[]). */
export function filaPaginaDeTema(p, umbral = normalizarUmbral(null)) {
  const ex = exportadorDePagina(p.exportador);
  return {
    id: String(p.page_id ?? ''),
    nombre: texto(p.page_name, 100) || `página ${texto(p.page_id, 30)}`,
    paises: lista(p.paises).map(String),
    anuncios: esNumero(p.anuncios_activos_medidos) ? p.anuncios_activos_medidos : (esNumero(p.anuncios_activos_traccion) ? p.anuncios_activos_traccion : null),
    anunciosEsPiso: p.anuncios_activos_medidos_es_piso !== false,
    enMuestra: esNumero(p.anuncios_activos_en_muestra) ? p.anuncios_activos_en_muestra : null,
    edad: aNumero(p.edad_oferta_dias),
    edadEsPiso: p.edad_es_piso !== false,
    medicion: p.medicion_estado ?? null,
    estado: p.estado_traccion ?? null,
    estadoTexto: (ESTADOS_TRACCION[p.estado_traccion] || { texto: 'Sin estado' }).texto,
    estadoTono: (ESTADOS_TRACCION[p.estado_traccion] || { tono: 'neutro' }).tono,
    motivo: motivoPaginaTraccion(p, umbral),
    formato: texto(p.formato, 40) || null,
    macro: macroEtiqueta(p.macro_nicho),
    confianza: p.confianza === undefined || p.confianza === null ? null : aNumero(p.confianza),
    modeloCobro: p.es_oferta_digital_pago_unico === true ? 'pago único (IA)' : p.es_oferta_digital_pago_unico === false ? 'no es pago único' : 'sin verificar',
    porVerificar: lista(p.por_verificar).map((x) => texto(x, 60)),
    mismoOperador: p.posible_mismo_operador === true,
    grupoOperador: p.grupo_operador ? texto(p.grupo_operador, 60) : null,
    exportador: ex,
    ausenciaMedida: lista(p.paises_ausencia_medida).map(String),
    raw: p,
  };
}

export function textoMedicion(estado) {
  switch (estado) {
    case 'completa': return { texto: 'completa', tono: 'ok', ayuda: 'Se vieron todos los anuncios declarados: el conteo es exacto.' };
    case 'parcial': return { texto: 'parcial', tono: 'aviso', ayuda: 'Hay más anuncios declarados que los vistos: la cifra es de al menos esos.' };
    case 'muestra': return { texto: 'solo muestra', tono: 'aviso', ayuda: 'Visto solo al buscar por frases (hasta 50 anuncios por consulta): la cifra es de al menos esos; la pasada 3 la mide de verdad.' };
    default: return { texto: 'sin medición', tono: 'neutro', ayuda: '' };
  }
}

/** Medición por país de una entrada de paginas/<corrida>.json: piso vs medido. */
export function medicionPorPais(pagina) {
  const por = pagina && pagina.medicion && pagina.medicion.por_pais && typeof pagina.medicion.por_pais === 'object' ? pagina.medicion.por_pais : {};
  return Object.entries(por).map(([pais, m]) => {
    const vistos = esNumero(m.anuncios_vistos) ? m.anuncios_vistos : null;
    const total = esNumero(m.total_declarado) ? m.total_declarado : null;
    const pagina_ = m.fuente === 'pagina';
    let lectura;
    if (m.completa === true) lectura = `exacto: ${num(vistos)} de ${num(total ?? vistos)} anuncios`;
    else if (pagina_ && total !== null && vistos !== null) lectura = `parcial: se ven ${num(vistos)} de ${num(total)} declarados`;
    else lectura = `al menos ${num(vistos)} visto(s) por frases, total desconocido`;
    return { pais, fuente: pagina_ ? 'consulta por página' : 'muestra por frases', vistos, total, completa: m.completa === true, lectura, tono: m.completa === true ? 'ok' : 'aviso' };
  }).sort((a, b) => (a.pais < b.pais ? -1 : 1));
}

/**
 * Detalle de una página: une lo que dicen el ranking (`candidata`), la ingesta (`pagina`: títulos, medición) y el etiquetado
 * (`etiqueta`: tema, señales de riesgo, evidencia). Cualquiera puede faltar; lo que falta se dice, no se rellena.
 */
export function detallePagina({ candidata = null, pagina = null, etiqueta = null, corrida = null, umbral = normalizarUmbral(null) } = {}) {
  const base = candidata ? filaPaginaDeTema(candidata, umbral) : null;
  const nombre = texto((pagina && pagina.page_name) || (candidata && candidata.page_name) || (etiqueta && etiqueta.page_name), 120);
  const id = String((pagina && pagina.page_id) ?? (candidata && candidata.page_id) ?? (etiqueta && etiqueta.page_id) ?? '');
  const titulos = lista(pagina && pagina.titulos).map((t) => ({ texto: texto(t, 300), bidi: tieneControlBidi(t) }));
  const qids = lista(pagina && pagina.qids).map((q) => texto(q, 80));
  const senales = lista(etiqueta && etiqueta.senales_riesgo).map((s) => texto(s, 60));
  const avisosEtiqueta = lista(etiqueta && etiqueta.avisos).map((s) => texto(s, 200));
  const evidencia = lista(etiqueta && etiqueta.evidencia).map((e) => texto(e && e.titulo, 300)).filter(Boolean);
  const notas = [];
  const piso = pagina ? pagina.anuncios_activos_medidos_es_piso !== false : (base ? base.anunciosEsPiso : true);
  const medidos = pagina && esNumero(pagina.anuncios_activos_medidos) ? pagina.anuncios_activos_medidos : base ? base.anuncios : null;
  const enMuestra = pagina && esNumero(pagina.anuncios_activos_en_muestra) ? pagina.anuncios_activos_en_muestra : base ? base.enMuestra : null;
  if (!pagina) notas.push('No se pudieron leer los títulos ni la medición por país de esta página: solo se muestra lo que dice el ranking.');
  if (!etiqueta) notas.push('La IA no clasificó esta página (no se clasificó o no avanzó): tema, público y señales de riesgo sin dato.');
  if (etiqueta && etiqueta.avanza_a_candidata === false) notas.push('La clasificación la marcó como NO candidata (no avanza).');

  // Enlaces a la ficha del anuncio: SOLO texto (el panel nunca abre ni enlaza Meta). Si los datos traen ads con URL, se muestran;
  // si no, se dice dónde están (en el crudo de cada consulta).
  const fichas = [];
  for (const a of lista(pagina && (pagina.anuncios || pagina.ads))) {
    const u = urlFichaAnuncio(a && (a.ad_snapshot_url || a.url));
    if (u) fichas.push(u);
  }
  const fichasNota = fichas.length ? null
    : 'Al cargar los datos solo se guardan los títulos, no los anuncios completos: el enlace a la ficha de cada anuncio (campo ad_snapshot_url) está en los datos sin procesar de las consultas que vieron la página'
      + (corrida && qids.length ? `: empresa/barrido/crudo/${texto(corrida, 40)}/<consulta>.json` : '') + '.';

  return {
    id, nombre,
    paises: lista((pagina && pagina.paises) || (candidata && candidata.paises)).map(String),
    monedas: lista(pagina && pagina.monedas).map((m) => texto(m, 8)),
    medicionEstado: (pagina && pagina.medicion && pagina.medicion.estado) || (base && base.medicion) || null,
    medicionTexto: textoMedicion((pagina && pagina.medicion && pagina.medicion.estado) || (base && base.medicion) || null),
    porPais: medicionPorPais(pagina),
    anunciosMedidos: medidos,
    anunciosEnMuestra: enMuestra,
    anunciosEsPiso: piso,
    edad: aNumero((pagina && pagina.edad_oferta_dias) ?? (candidata && candidata.edad_oferta_dias)),
    edadMax: aNumero(pagina && pagina.edad_max_dias),
    edadEsPiso: pagina ? pagina.edad_es_piso !== false : (base ? base.edadEsPiso : true),
    conceptos: pagina && esNumero(pagina.conceptos_unicos) ? pagina.conceptos_unicos : (candidata && esNumero(candidata.conceptos_unicos) ? candidata.conceptos_unicos : null),
    estadoTraccion: base ? { estado: base.estado, texto: base.estadoTexto, tono: base.estadoTono, motivo: base.motivo, explicacion: explicacionTraccion('pagina', candidata, umbral) } : null,
    exportador: pagina ? exportadorDePagina(pagina.exportador) : (base ? base.exportador : null),
    etiqueta: etiqueta ? {
      tema: texto(etiqueta.tema, 160), temaSlug: texto(etiqueta.tema_slug, 100), publico: texto(etiqueta.publico, 160),
      formato: etiqueta.formato ? formatoHumano(etiqueta.formato) : '', macro: macroEtiqueta(etiqueta.macro_nicho), macroMotivo: texto(etiqueta.macro_nicho_motivo, 240),
      confianza: aNumero(etiqueta.confianza),
      modeloCobro: etiqueta.es_oferta_digital_pago_unico === true ? 'pago único (según la IA)' : etiqueta.es_oferta_digital_pago_unico === false ? 'no es pago único (según la IA)' : 'sin verificar (la IA no lo sabe)',
    } : null,
    senalesRiesgo: senales,
    avisosEtiqueta,
    evidencia,
    porVerificar: base ? base.porVerificar : [],
    mismoOperador: base ? base.mismoOperador : false,
    ausenciaMedida: base ? base.ausenciaMedida : [],
    titulos,
    qids,
    fichas,
    fichasNota,
    notas,
  };
}

/**
 * Respuesta de `GET /descubrimiento/<corrida>/referente/<page_id>` → lo que pinta la sección «Landing original» (puro).
 * La dirección de la landing solo se acepta si es https sin espacios (el servidor ya la validó; aquí se vuelve a comprobar):
 * es lo ÚNICO que el panel convierte en enlace. Las direcciones de Meta (Biblioteca, página, fichas) siguen siendo TEXTO para copiar.
 */
export function normalizarReferente(datos) {
  if (!datos || typeof datos !== 'object') return null;
  const l = datos.landing && typeof datos.landing === 'object' ? datos.landing : null;
  const urlOk = l && typeof l.url === 'string' && l.url.length <= 500 && /^https:\/\/[^\s\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]+$/i.test(l.url);
  const meta = datos.meta && typeof datos.meta === 'object' ? datos.meta : {};
  const soloMeta = (u) => (typeof u === 'string' && /^https:\/\/www\.facebook\.com\/[A-Za-z0-9_\-./?=&]+$/.test(u) ? u : null);
  return {
    pageId: texto(datos.page_id, 30),
    nombre: texto(datos.page_name, 120),
    landing: urlOk ? {
      url: l.url,
      dominio: texto(l.dominio, 120),
      registradaEn: texto(l.registrada_en, 40),
      nota: texto(l.nota, 300),
      ofertaId: texto(l.oferta_id, 40),
      copiaLocal: texto(l.copia_local, 300),
    } : null,
    meta: { biblioteca: soloMeta(meta.biblioteca_pagina), pagina: soloMeta(meta.pagina) },
    anuncios: lista(datos.anuncios).map((a) => (a && typeof a === 'object' ? { id: texto(a.id, 30), inicio: texto(a.inicio, 12), titulo: texto(a.titulo, 150), ficha: soloMeta(a.ficha) } : null)).filter((a) => a && a.ficha),
    comando: texto(datos.comando_registrar, 300),
  };
}

/** Índice page_id → etiqueta del consolidado (para no recorrerlo en cada detalle). */
export function indexarEtiquetas(consolidado) {
  const m = new Map();
  for (const e of lista(consolidado && consolidado.etiquetas)) {
    if (e && e.page_id !== undefined && e.page_id !== null) m.set(String(e.page_id), e);
  }
  return m;
}

/** Índice page_id → página candidata del ranking (temas[].paginas[] y sin_tema[]). */
export function indexarCandidatas(candidatos) {
  const m = new Map();
  for (const t of lista(candidatos && candidatos.temas)) {
    for (const p of lista(t.paginas)) if (p && p.page_id !== undefined) m.set(String(p.page_id), { pagina: p, temaSlug: t.tema_slug ?? null });
  }
  for (const p of lista(candidatos && candidatos.sin_tema)) if (p && p.page_id !== undefined) m.set(String(p.page_id), { pagina: p, temaSlug: null });
  return m;
}

/** Resumen de un tema para el panel de detalle. */
export function detalleTema(fila, umbral = normalizarUmbral(null)) {
  const t = fila.raw || {};
  const paginas = fila.tipo === 'tema' ? lista(t.paginas).map((p) => filaPaginaDeTema(p, umbral)) : [filaPaginaDeTema(t, umbral)];
  const formatos = Object.entries(fila.formatos || {}).map(([k, n]) => `${texto(k, 30)}×${n}`);
  const entr = fila.entrantes ? Object.entries(fila.entrantes) : [];
  const conBase = entr.filter(([, v]) => v !== null && v !== undefined);
  return {
    titulo: fila.nombre,
    slug: fila.slug,
    publicos: fila.publicos,
    kv: [
      ['Estado de tracción', fila.estadoTexto],
      ['Motivo', fila.motivo],
      ['Anunciantes independientes', num(fila.anunciantes)],
      ['Páginas', num(fila.paginas)],
      ['Anuncios medidos', conPiso(fila.anuncios, fila.anunciosEsPiso) + (fila.anunciosEsPiso ? ' (al menos)' : '')],
      ['Edad de la oferta', diasTexto(fila.edad, fila.edadEsPiso) + (fila.edadEsPiso ? ' (al menos)' : '')],
      ['Países con presencia', fila.paises.join(', ') || '—'],
      ['Países sin presencia en la muestra', (fila.huecos.join(', ') || '—') + (fila.huecos.length ? ' (hipótesis hasta medir)' : '')],
      ['Categoría general (macro-nicho)', fila.macro || 'fuera de marco / sin clasificar'],
      ['Formatos', formatos.join(' · ') || '—'],
      ['Exportador (indicio)', fila.exportador.texto],
      ['Por verificar', fila.porVerificar.join(', ') || '—'],
      ['Posible mismo operador', fila.mismoOperador ? `${fila.mismoOperador} página(s)` : 'no'],
      ['Anunciantes nuevos en 30 días', conBase.length ? conBase.map(([p, v]) => `${p}: ${v}`).join(' · ') : 'sin dato en ningún país (no hay corrida anterior para comparar; no es cero)'],
    ],
    paginas,
  };
}

// ───────────────────────── matriz tema × país ─────────────────────────

export const AVISO_MATRIZ_DEFECTO = 'Que algo no aparezca en la muestra del barrido no significa que no exista en ese mercado: cada hueco es solo una hipótesis hasta medirlo con la pasada 3 (una consulta por página y país). La herramienta de consulta entrega como máximo 50 anuncios por consulta.';

/** Intensidad del mapa de calor (0 = no visto; 1–4 = 1, 2, 3–4, 5 o más páginas): escala fija y discreta, nunca relativa a los datos. */
export function nivelCalor(paginas) {
  if (!esNumero(paginas) || paginas <= 1) return 1; // presente: al menos «visto»
  if (paginas === 2) return 2;
  if (paginas <= 4) return 3;
  return 4;
}

/**
 * Matriz tema × país: filas con celdas {presente, paginas}. Ausencia = HIPÓTESIS.
 * `filtro`: {soloPasan, q, minPaises, estado}. `max` acota las filas devueltas (el total sigue en `total`).
 */
export function modeloMatriz(candidatos, { soloPasan = false, estado = '', q = '', minPaises = 0, max = 0 } = {}) {
  const m = (candidatos && candidatos.matriz_tema_pais) || {};
  const paises = lista(m.paises).map(String);
  const temas = new Map(lista(candidatos && candidatos.temas).map((t) => [String(t.tema_slug), t]));
  const qn = normalizarBusqueda(q);
  const todas = lista(m.temas).map((fila) => {
    const slug = String(fila.tema_slug);
    const t = temas.get(slug) || {};
    const celdas = paises.map((p) => {
      const c = (fila.presencia && fila.presencia[p]) || {};
      const paginas = esNumero(c.paginas) ? c.paginas : 0;
      return { pais: p, presente: c.presente === true, paginas, nivel: c.presente === true ? nivelCalor(paginas) : 0 };
    });
    return {
      slug,
      nombre: texto(t.tema, 100) || texto(slug, 100),
      rank: esNumero(t.rank) ? t.rank : null,
      estado: t.estado_traccion ?? null,
      estadoTono: (ESTADOS_TRACCION[t.estado_traccion] || { tono: 'neutro' }).tono,
      celdas,
      presentes: celdas.filter((c) => c.presente).length,
      huecos: celdas.filter((c) => !c.presente).length,
    };
  });
  const filtradas = todas.filter((f) => {
    if (soloPasan && f.estado !== 'pasa') return false;
    if (estado && f.estado !== estado) return false;
    if (minPaises && f.presentes < minPaises) return false;
    if (qn && !normalizarBusqueda(`${f.nombre} ${f.slug}`).includes(qn)) return false;
    return true;
  }).sort((a, b) => (a.rank ?? 1e9) - (b.rank ?? 1e9));
  const porPais = paises.map((p, i) => ({
    pais: p,
    presentes: todas.filter((f) => f.celdas[i].presente).length,
    huecos: todas.filter((f) => !f.celdas[i].presente).length,
  }));
  return {
    paises,
    filas: max > 0 ? filtradas.slice(0, max) : filtradas,
    total: filtradas.length,
    totalTemas: todas.length,
    porPais,
    advertencia: texto(m.advertencia, 600) || AVISO_MATRIZ_DEFECTO,
    estadoAusencia: m.estado_ausencia || 'hipotesis_hasta_pasada_3',
    idiomas: (candidatos && candidatos.idiomas_por_pais) || {},
  };
}

// ───────────────────────── fichas borrador (PM incompleto) ─────────────────────────

const PUERTAS = ['marca_personal', 'sustituto_gratis_cubre', 'practica_vetada'];
const TRANSFER = ['dolor_universal', 'viabilidad_ticket', 'riesgo_politicas'];

/** ¿Falta evaluar? `null` = sin evaluar (no es «no»). */
function vacioEval(v) { return v === null || v === undefined; }

/**
 * Modelo de las fichas borrador: qué falta evaluar para poder puntuar con la fórmula PM (no se calcula ningún puntaje aquí).
 */
export function modeloFichas(doc) {
  const ofertas = lista(doc && doc.ofertas);
  const fichas = ofertas.map((o, i) => {
    const puertas = PUERTAS.map((k) => ({ id: k, valor: o.puertas ? o.puertas[k] : undefined }));
    const mercados = lista(o.mercados).map((m) => {
      const t = m.transferibilidad || {};
      const h = m.hueco || {};
      const transfer = TRANSFER.map((k) => ({ id: k, valor: t[k] }));
      return {
        mercado: texto(m.mercado, 8),
        idioma: texto(m.idioma, 8),
        originalPresente: h.original_presente,
        sostenidos: h.anunciantes_sostenidos,
        puntajeRival: h.puntaje_rival,
        entrantes: h.entrantes_30d,
        ventana: texto(m.ventana, 30),
        transfer,
        faltanTransfer: transfer.filter((x) => vacioEval(x.valor)).length,
        nota: texto(m._nota, 300),
      };
    });
    const faltanPuertas = puertas.filter((p) => vacioEval(p.valor)).length;
    const faltanTransfer = mercados.reduce((a, m) => a + m.faltanTransfer, 0);
    const faltanRival = mercados.filter((m) => vacioEval(m.puntajeRival)).length;
    const faltanEntrantes = mercados.filter((m) => vacioEval(m.entrantes)).length;
    const reencuadresVacios = lista(o.reencuadres).length === 0;
    const ventanaRelleno = mercados.length > 0 && mercados.every((m) => m.ventana === 'evergreen');
    const totalCampos = PUERTAS.length + mercados.length * (TRANSFER.length + 2) + 1;
    const faltan = faltanPuertas + faltanTransfer + faltanRival + faltanEntrantes + (reencuadresVacios ? 1 : 0);
    const faltantes = [];
    if (faltanPuertas) faltantes.push({ tema: 'Puertas', detalle: `${faltanPuertas} de ${PUERTAS.length} sin evaluar (${puertas.filter((p) => vacioEval(p.valor)).map((p) => p.id.replace(/_/g, ' ')).join(', ')})` });
    if (faltanTransfer) faltantes.push({ tema: 'Transferibilidad', detalle: `${faltanTransfer} de ${mercados.length * TRANSFER.length} valores sin evaluar (${TRANSFER.map((x) => x.replace(/_/g, ' ')).join(', ')} × ${mercados.length} mercados)` });
    if (faltanRival) faltantes.push({ tema: 'Puntaje del rival', detalle: `sin auditar en ${faltanRival} de ${mercados.length} mercados` });
    if (faltanEntrantes) faltantes.push({ tema: 'Anunciantes nuevos en 30 días', detalle: `sin dato en ${faltanEntrantes} de ${mercados.length} mercados (no hay corrida anterior para comparar; no es cero)` });
    if (reencuadresVacios) faltantes.push({ tema: 'Reencuadres', detalle: 'sin diseñar' });
    if (ventanaRelleno) faltantes.push({ tema: 'Ventana', detalle: '«evergreen» (sin fecha) es un valor de relleno: la ventana no está evaluada' });
    const t = o.traccion || {};
    return {
      id: texto(o.modelo_id, 140) || `ficha-${i + 1}`,
      nombre: texto(o.nombre, 160),
      idioma: texto(o.fuente && o.fuente.idioma, 8),
      pais: texto(o.fuente && o.fuente.pais, 8),
      macro: macroEtiqueta(o.macro_nicho),
      traccion: {
        anuncios: esNumero(t.anuncios_activos) ? t.anuncios_activos : null,
        edad: aNumero(t.edad_oferta_dias),
        conceptos: esNumero(t.conceptos_unicos) ? t.conceptos_unicos : null,
        paginasMismaLanding: esNumero(t.paginas_misma_landing) ? t.paginas_misma_landing : null,
        independientes: esNumero(t.anunciantes_independientes_mismo_angulo) ? t.anunciantes_independientes_mismo_angulo : null,
      },
      puertas,
      mercados,
      faltantes,
      faltan, totalCampos,
      evaluados: Math.max(0, totalCampos - faltan),
      pctEvaluado: totalCampos > 0 ? Math.max(0, Math.min(100, Math.round(((totalCampos - faltan) / totalCampos) * 100))) : 0,
      completo: faltan === 0,
      pendiente: lista(o.pendiente).map((p) => texto(p, 300)),
      reencuadres: lista(o.reencuadres).length,
    };
  });
  return {
    version: doc && typeof doc.schema_version === 'string' ? doc.schema_version : null,
    nota: texto(doc && doc._nota, 300),
    fichas,
    incompletas: fichas.filter((f) => !f.completo).length,
    total: fichas.length,
  };
}

// ───────────────────────── plan y cobertura ─────────────────────────

function listaQids(v) { return Array.isArray(v) ? v.map(String) : null; }

/**
 * Cobertura del plan por pasada. `plan` = planes/<corrida>*.json (acumulado); `estado` = estado del barrido, que puede traer
 * listas de qids (ingesta.cobertura: consultas_ok, con_error, sin_crudo, truncadas) o solo conteos (barrido estado --json).
 * Con conteos no se inventa un reparto por pasada: se dice que solo hay totales.
 */
export function modeloPlan(plan, estado) {
  const consultas = lista(plan && plan.consultas);
  const est = normalizarEstado(estado);
  const tope = esNumero(plan && plan.tope_consultas) ? plan.tope_consultas : (est ? est.plan.tope : null);
  const l = est ? est.crudos.listas : { ok: null, conError: null, sinCrudo: null, truncadas: null };
  let ok = l.ok;
  let err = l.conError;
  let sin = l.sinCrudo;
  const trunc = l.truncadas;
  let deducido = false;
  // Sin listas de qids solo hay totales. Se deduce el reparto SOLO en los dos extremos inequívocos (nada ejecutado / todo ejecutado).
  if (!ok && !err && !sin && est && est.crudos.ok !== null && consultas.length) {
    const tOk = est.crudos.ok;
    const tErr = est.crudos.conError || 0;
    if (tOk === 0 && tErr === 0) { ok = []; err = []; sin = consultas.map((c) => String(c.qid)); deducido = true; }
    else if (tOk >= consultas.length && tErr === 0) { ok = consultas.map((c) => String(c.qid)); err = []; sin = []; deducido = true; }
  }
  const hayListas = !!(ok || err || sin);
  const setOk = new Set(ok || []);
  const setErr = new Set(err || []);
  const setTr = new Set(trunc || []);

  const pasadas = new Map();
  for (const c of consultas) {
    const p = esNumero(c.pasada) ? c.pasada : 1;
    if (!pasadas.has(p)) pasadas.set(p, { pasada: p, planificadas: 0, ok: 0, conError: 0, sinEjecutar: 0, truncadas: 0, paises: {}, formas: new Set() });
    const g = pasadas.get(p);
    g.planificadas += 1;
    const pais = lista(c.countries)[0];
    if (pais) g.paises[pais] = (g.paises[pais] || 0) + 1;
    if (c.forma_id) g.formas.add(String(c.forma_id));
    if (hayListas) {
      if (setOk.has(c.qid)) { g.ok += 1; if (setTr.has(c.qid)) g.truncadas += 1; } else if (setErr.has(c.qid)) g.conError += 1; else g.sinEjecutar += 1;
    }
  }
  const NOMBRE = { 1: 'Pasada 1 — barrido por forma de oferta (país × frase)', 2: 'Pasada 2 — variantes de frase donde la muestra oculta mucho', 3: 'Pasada 3 — una consulta por página (mide de verdad)' };
  const filas = [...pasadas.values()].sort((a, b) => a.pasada - b.pasada).map((g) => ({
    pasada: g.pasada,
    nombre: NOMBRE[g.pasada] || `Pasada ${g.pasada}`,
    planificadas: g.planificadas,
    pctOk: hayListas && g.planificadas ? Math.round((g.ok / g.planificadas) * 100) : null,
    ok: hayListas ? g.ok : null,
    conError: hayListas ? g.conError : null,
    sinEjecutar: hayListas ? g.sinEjecutar : null,
    truncadas: hayListas && trunc ? g.truncadas : null,
    paises: Object.entries(g.paises).sort((a, b) => (a[0] < b[0] ? -1 : 1)).map(([p, n]) => `${p}×${n}`).join(' '),
    formas: g.formas.size,
  }));
  const totalesEstado = est && est.crudos.ok !== null ? {
    ok: est.crudos.ok, conError: est.crudos.conError, sinCrudo: est.crudos.sinCrudo, truncadas: est.crudos.truncadas, anunciosDistintos: est.crudos.anunciosDistintos,
  } : null;
  const planificadas = consultas.length;
  return {
    corrida: plan && plan.corrida_id ? texto(plan.corrida_id, 30) : null,
    creadoEn: plan && typeof plan.creado_en === 'string' ? plan.creado_en : null,
    tope,
    planificadas,
    cupoRestante: tope !== null ? tope - planificadas : null,
    pasadas: filas,
    porPasadaDisponible: hayListas,
    totalesEstado,
    avisoSinListas: !hayListas
      ? 'Solo hay los totales de lo ejecutado, no la lista de consultas: por eso no se puede repartir cuántas se ejecutaron o fallaron en cada pasada (y no se inventa).'
      : deducido ? 'El reparto por pasada se deduce de los totales (ninguna consulta ejecutada, o tantos resultados como consultas y ninguno con error); las «truncadas» solo se conocen en total.' : null,
    consultas: consultas.map((c) => ({
      qid: texto(c.qid, 80),
      pasada: esNumero(c.pasada) ? c.pasada : 1,
      pais: texto(lista(c.countries)[0], 6),
      idioma: texto(c.idioma, 6),
      forma: texto(c.forma_id, 60),
      // search_terms viene de un crudo/banco: dato no confiable, solo se muestra
      frase: texto(c.search_terms, 100),
      paginas: lista(c.page_ids).length,
      estado: !hayListas ? null : setOk.has(c.qid) ? (setTr.has(c.qid) ? 'truncada' : 'ok') : setErr.has(c.qid) ? 'con_error' : 'sin_ejecutar',
    })),
  };
}

/** Cobertura del etiquetado (etiquetas/<corrida>/consolidado.json). */
export function modeloEtiquetado(consolidado) {
  if (!consolidado || typeof consolidado !== 'object') return null;
  const c = consolidado.cobertura || {};
  return {
    total: esNumero(c.paginas_total) ? c.paginas_total : null,
    etiquetadas: esNumero(c.etiquetadas) ? c.etiquetadas : null,
    indeterminadas: esNumero(c.indeterminadas) ? c.indeterminadas : null,
    enDisputa: esNumero(c.en_disputa) ? c.en_disputa : (lista(consolidado.en_disputa).length),
    sinEtiquetar: esNumero(c.sin_etiquetar) ? c.sin_etiquetar : lista(consolidado.sin_etiquetar).length,
    rechazadas: esNumero(c.rechazadas) ? c.rechazadas : lista(consolidado.rechazadas).length,
    avanzan: esNumero(c.avanzan_a_candidata) ? c.avanzan_a_candidata : null,
    tasaEtiquetadas: tasaTexto(c.tasa_etiquetadas),
    tasaConTema: tasaTexto(c.tasa_con_tema),
    lotes: { total: esNumero(c.lotes_total) ? c.lotes_total : lista(consolidado.lotes).length, validados: esNumero(c.lotes_validados) ? c.lotes_validados : null, sinSalida: esNumero(c.lotes_sin_salida) ? c.lotes_sin_salida : null, invalidos: esNumero(c.lotes_salida_invalida) ? c.lotes_salida_invalida : null },
    sinEtiquetarLista: lista(consolidado.sin_etiquetar).map((s) => ({ id: String(s.page_id ?? ''), nombre: texto(s.page_name, 80), motivo: s.motivo ? motivoHumano(s.motivo) : '' })),
    riesgos: contarSenales(consolidado),
  };
}

function contarSenales(consolidado) {
  const m = new Map();
  for (const e of lista(consolidado && consolidado.etiquetas)) {
    for (const s of lista(e.senales_riesgo)) m.set(s, (m.get(s) || 0) + 1);
  }
  return [...m.entries()].sort((a, b) => b[1] - a[1]).map(([senal, n]) => ({ senal: texto(senal, 60), n }));
}

// ───────────────────────── memoria entre corridas ─────────────────────────

/**
 * Memoria de barridos: ¿hay base para `entrantes_30d`? (solo con una instantánea previa de 25–60 días; si no, null, nunca 0.)
 * `corridas` = GET /descubrimiento/corridas; `estado.memoria` = {instantanea, instantaneas, problemas}.
 */
export function modeloMemoria({ corridas = [], estado = null, candidatos = null, corridaId = null } = {}) {
  const mem = (candidatos && candidatos.memoria) || {};
  const est = normalizarEstado(estado);
  const emem = est ? est.memoria : { instantaneas: null, problemas: [], existe: false, ts: null };
  const temas = lista(candidatos && candidatos.temas);
  let conEntrantes = 0;
  let temasNuevos = 0;
  for (const t of temas) {
    if (t.entrantes_30d && Object.values(t.entrantes_30d).some((v) => v !== null && v !== undefined)) conEntrantes += 1;
    if (t.novedad && t.novedad.tema_nuevo === true) temasNuevos += 1;
  }
  const baseValida = mem.base_valida === true;
  const ord = ordenarCorridas(corridas);
  const filas = ord.map((c, i) => {
    const siguiente = ord[i + 1];
    return {
      corrida: texto(c.corrida_id, 30),
      actual: c.corrida_id === corridaId,
      paginas: esNumero(c.paginas) ? c.paginas : null,
      candidatas: esNumero(c.candidatas) ? c.candidatas : null,
      pasanTraccion: esNumero(c.pasan_traccion) ? c.pasan_traccion : null,
      fichas: esNumero(c.fichas) ? c.fichas : null,
      consultas: esNumero(c.consultas_ok) ? c.consultas_ok : null,
      actualizadoEn: typeof c.actualizado_en === 'string' ? c.actualizado_en : null,
      deltaPaginas: siguiente && esNumero(c.paginas) && esNumero(siguiente.paginas) ? c.paginas - siguiente.paginas : null,
    };
  });
  const instantaneas = esNumero(emem.instantaneas) ? emem.instantaneas : null;
  const problemas = lista(emem.problemas).map((p) => texto(typeof p === 'string' ? p : JSON.stringify(p), 240));
  return {
    baseValida,
    previa: mem.previa_corrida_id ? texto(mem.previa_corrida_id, 30) : null,
    instantaneaDeEstaCorrida: est ? emem.existe : null,
    instantaneaTs: emem.ts || null,
    instantaneas,
    problemas,
    temasConEntrantes: conEntrantes,
    temasNuevos,
    totalTemas: temas.length,
    explicacion: baseValida
      ? 'Hay una foto guardada de una corrida anterior: los anunciantes nuevos de los últimos 30 días y los «temas nuevos» se calculan comparando con ella.'
      : 'No hay con qué comparar: los anunciantes nuevos de los últimos 30 días quedan «sin dato» (no son cero) y no se pueden detectar «temas nuevos». Hace falta una corrida anterior con su foto guardada, de entre 25 y 60 días de antigüedad.',
    nota: 'Cada corrida guarda una foto de sus resultados que no se puede modificar; la próxima corrida la usa para comparar. Hay que guardarla después de la carga de datos FINAL.',
    filas,
  };
}

// ───────────────────────── páginas (tabla paginada por el servidor) ─────────────────────────

/** Entrada de GET /descubrimiento/<c>/paginas → fila de la tabla de páginas. Tolera el formato de paginas/<corrida>.json. */
export function filaPagina(p) {
  const med = (p.medicion && p.medicion.estado) || null;
  const ex = exportadorDePagina(p.exportador);
  return {
    id: String(p.page_id ?? ''),
    nombre: texto(p.page_name, 100) || `página ${texto(p.page_id, 30)}`,
    paises: lista(p.paises).map(String),
    monedas: lista(p.monedas).map((m) => texto(m, 8)),
    anuncios: esNumero(p.anuncios_activos_medidos) ? p.anuncios_activos_medidos : (esNumero(p.anuncios_activos_en_muestra) ? p.anuncios_activos_en_muestra : null),
    piso: p.anuncios_activos_medidos_es_piso !== false,
    edad: aNumero(p.edad_oferta_dias),
    edadPiso: p.edad_es_piso !== false,
    conceptos: esNumero(p.conceptos_unicos) ? p.conceptos_unicos : null,
    medicion: med,
    medicionTexto: textoMedicion(med),
    exportador: ex,
    tema: p.tema_slug ? texto(p.tema_slug, 80) : null,
    raw: p,
  };
}

/** Normaliza la respuesta paginada del servidor: acepta {paginas|items|filas, total, pagina, por_pagina} o un arreglo. */
export function normalizarPaginado(datos) {
  if (Array.isArray(datos)) return { filas: datos, total: datos.length, pagina: 1, porPagina: datos.length };
  const d = datos && typeof datos === 'object' ? datos : {};
  const filas = lista(d.paginas || d.items || d.filas || d.datos);
  return {
    filas,
    total: esNumero(d.total) ? d.total : filas.length,
    pagina: esNumero(d.pagina) ? d.pagina : 1,
    porPagina: esNumero(d.por_pagina) ? d.por_pagina : (filas.length || 50),
  };
}

// ───────────────────────── descartadas y exportadores ─────────────────────────

const MOTIVOS_HUMANOS = Object.freeze({
  no_es_oferta_digital_pago_unico: 'no es un producto digital de pago único',
  sin_titulos: 'sin títulos de anuncio',
  tema_indeterminado_sin_traccion_alta: 'tema sin determinar y sin tracción alta',
  'formato_excluido:servicio': 'formato excluido: servicio',
  'formato_excluido:comunidad_o_app': 'formato excluido: comunidad o app',
  'formato_excluido:producto_fisico': 'formato excluido: producto físico',
});
const FORMATOS_HUMANOS = Object.freeze({ servicio: 'servicio', comunidad_o_app: 'comunidad o app', producto_fisico: 'producto físico' });

/** Motivo de descarte o de «sin clasificar» en palabras («sin_titulos» → «sin títulos de anuncio»); lo desconocido pierde los guiones bajos. */
export function motivoHumano(clave) {
  const k = String(clave ?? '');
  return MOTIVOS_HUMANOS[k] || texto(k.replace(/_/g, ' ').replace(/:/g, ': '), 80);
}
/** Formato de la oferta en palabras («comunidad_o_app» → «comunidad o app»). */
export function formatoHumano(clave) {
  const k = String(clave ?? '');
  return FORMATOS_HUMANOS[k] || texto(k.replace(/_/g, ' '), 40);
}

export function modeloDescartadas(candidatos) {
  const porMotivo = new Map();
  const filas = lista(candidatos && candidatos.descartadas).map((d) => {
    const motivos = lista(d.motivos).map((m) => motivoHumano(m));
    for (const m of motivos) porMotivo.set(m, (porMotivo.get(m) || 0) + 1);
    return {
      id: String(d.page_id ?? ''),
      nombre: texto(d.page_name, 100),
      paises: lista(d.paises).map(String),
      enMuestra: esNumero(d.anuncios_activos_en_muestra) ? d.anuncios_activos_en_muestra : null,
      tema: texto(d.tema_slug, 80),
      formato: d.formato ? formatoHumano(d.formato) : '',
      motivos,
    };
  });
  return { filas, porMotivo: [...porMotivo.entries()].sort((a, b) => b[1] - a[1]).map(([motivo, n]) => ({ motivo, n })) };
}

export function modeloExportadores(candidatos) {
  const e = (candidatos && candidatos.exportadores) || null;
  if (!e) return null;
  const r = e.resumen || {};
  return {
    advertencia: texto(e.advertencia, 500),
    evaluadas: esNumero(r.paginas_evaluadas) ? r.paginas_evaluadas : null,
    conSenal: esNumero(r.con_senal) ? r.con_senal : null,
    sinDato: esNumero(r.sin_dato) ? r.sin_dato : null,
    monedas: Object.entries(r.monedas || {}).sort((a, b) => b[1] - a[1]).map(([m, n]) => ({ moneda: texto(m, 8), n })),
    temasConSenal: esNumero(e.temas_con_senal) ? e.temas_con_senal : null,
  };
}

// ───────────────────────── comandos (copiables) ─────────────────────────

const RE_CORRIDA = /^\d{4}-\d{2}-\d{2}-[a-z]$/;

export function corridaValida(id) { return typeof id === 'string' && RE_CORRIDA.test(id); }

/** Comando para producir lo que falta. Con una corrida inválida no se arma ningún comando (nunca se interpola texto no validado). */
export function comandoBarrido(subcomando, corridaId) {
  const c = corridaValida(corridaId) ? corridaId : '<CORRIDA>';
  const py = '.venv/bin/python -m scripts.modelado.barrido';
  switch (subcomando) {
    case 'estado': return `${py} estado ${c}`;
    case 'plan': return `${py} plan generar ${c} --escribir`;
    case 'ingestar': return `${py} ingestar ${c} --escribir`;
    case 'etiquetas': return `${py} etiquetas empaquetar ${c} --escribir`;
    case 'rankear': return `${py} rankear ${c} --sello-esperado <SELLO> --sello-limites-esperado <SELLO_LIMITES> --escribir`;
    case 'fichas': return `${py} fichas ${c} --sello-esperado <SELLO> --sello-limites-esperado <SELLO_LIMITES> --escribir`;
    case 'memoria': return `${py} memoria guardar ${c} --escribir`;
    default: return `${py} estado ${c}`;
  }
}


// ───────────────────────── pipeline de la corrida (qué falta correr) ─────────────────────────

/**
 * Pasos del flujo del barrido (README §3) con su estado según `estado` (barrido estado) y el comando que lo produce.
 * `hecho: null` = no se sabe (no hay estado). Sirve para el estado vacío: dice qué comando correr a continuación.
 */
export function modeloPipeline(estado, corridaId) {
  const e = normalizarEstado(estado);
  const c = corridaValida(corridaId) ? corridaId : '<CORRIDA>';
  const py = '.venv/bin/python -m scripts.modelado.barrido';
  const consultas = e ? e.plan.consultas : null;
  const nOk = e ? e.crudos.ok : null;
  const sinCrudo = e ? e.crudos.sinCrudo : null;
  const pasos = [
    { id: 'plan', corto: 'Plan', titulo: 'Plan de consultas', hecho: e ? (e.plan.existe && (consultas === null || consultas > 0)) : null, detalle: consultas !== null ? `${consultas} consulta${consultas === 1 ? '' : 's'}` : null, comando: `${py} plan generar ${c} --escribir` },
    { id: 'crudo', corto: 'Consultas', titulo: 'Datos sin procesar de los agentes (una consulta por archivo)', hecho: e ? (nOk !== null && nOk > 0 && (sinCrudo === null || sinCrudo === 0)) : null, detalle: nOk !== null ? `${nOk} ok${sinCrudo ? `, ${sinCrudo} sin ejecutar` : ''}${e && e.crudos.conError ? `, ${e.crudos.conError} con error` : ''}` : null, comando: `${py} plan agentes ${c} --salida-prompts /tmp/prompts-${c}-p1 --escribir` },
    { id: 'paginas', corto: 'Páginas', titulo: 'Carga de datos → páginas', hecho: e ? e.paginas.existe : null, detalle: e && e.paginas.total !== null ? `${e.paginas.total} páginas` : null, comando: `${py} ingestar ${c} --escribir` },
    { id: 'etiquetas', corto: 'Clasificación', titulo: 'Clasificación por IA (consolidada)', hecho: e ? e.etiquetado.existe : null, detalle: null, comando: `${py} etiquetas consolidar ${c} --escribir` },
    { id: 'memoria', corto: 'Foto', titulo: 'Foto guardada para comparar', hecho: e ? e.memoria.existe : null, detalle: null, comando: `${py} memoria guardar ${c} --escribir` },
    { id: 'candidatos', corto: 'Ranking', titulo: 'Candidatos (ranking)', hecho: e ? e.candidatos.existe : null, detalle: null, comando: comandoBarrido('rankear', c) },
    { id: 'fichas', corto: 'Fichas', titulo: 'Fichas en borrador', hecho: e ? e.fichas.existe : null, detalle: e && e.fichas.total !== null ? `${e.fichas.total} ficha${e.fichas.total === 1 ? '' : 's'}` : null, comando: comandoBarrido('fichas', c) },
  ];
  const siguiente = pasos.find((p) => p.hecho === false) || null;
  return { pasos, siguiente };
}

// ───────────────────────── resumen ejecutivo (lo primero que se lee) ─────────────────────────

function plural(n, uno, varios) { return `${num(n)} ${n === 1 ? uno : varios}`; }

/**
 * Resumen ejecutivo de la corrida en lenguaje de negocio: qué se encontró, cuántas ofertas pasan la tracción, qué se midió de
 * verdad y qué es solo una muestra, estado del barrido y del freno (con su consecuencia real). Todo calculado; nada inventado:
 * lo que no se sabe queda en null y la frase lo dice.
 */
export function resumenEjecutivo({ corrida = null, candidatos = null, estado = null, freno } = {}) {
  const c = corrida || {};
  const base = resumenCorrida({ corrida: c, candidatos, estado, freno });
  const umbral = base.umbral;
  const res = (candidatos && candidatos.resumen) || {};
  const est = normalizarEstado(estado);
  const med = res.paginas_por_medicion || (est && est.paginas.medicion) || null;
  const filas = candidatos ? [...filasTemas(candidatos), ...filasSinTema(candidatos)] : [];
  const cuenta = (e) => filas.filter((f) => f.estado === e).length;
  const hayRanking = candidatos !== null && filas.length > 0;
  const nTemasPasan = esNumero(res.temas_pasan_traccion) ? res.temas_pasan_traccion : (hayRanking ? filas.filter((f) => f.tipo === 'tema' && f.estado === 'pasa').length : null);
  const nSinTemaPasan = esNumero(res.sin_tema_pasan_traccion) ? res.sin_tema_pasan_traccion : (hayRanking ? filas.filter((f) => f.tipo === 'sin_tema' && f.estado === 'pasa').length : null);
  const pasan = nTemasPasan !== null ? nTemasPasan + (nSinTemaPasan || 0) : (esNumero(c.pasan_traccion) ? c.pasan_traccion : null);
  // los recuentos del resumen del ranking mandan (el ranking puede traer solo una parte de las filas); sin ellos, se cuentan las filas
  const porMedir = esNumero(res.temas_indeterminados_por_muestra) ? res.temas_indeterminados_por_muestra + (esNumero(res.sin_tema_indeterminadas_por_muestra) ? res.sin_tema_indeterminadas_por_muestra : 0) : (hayRanking ? cuenta('indeterminada_por_muestra') : null);
  const noPasan = esNumero(res.temas_no_pasan_traccion) ? res.temas_no_pasan_traccion : (hayRanking ? cuenta('no_pasa') : null);
  const medidas = med && esNumero(med.completa) ? med.completa : null;
  const soloMuestra = med && esNumero(med.muestra) ? med.muestra : null;
  const parcial = med && esNumero(med.parcial) ? med.parcial : null;
  const textoUmbral = textoMinimo(umbral);

  let titular;
  if (pasan === null) titular = 'Esta corrida aún no tiene ranking de candidatos';
  else if (pasan === 0) titular = 'Ninguna oferta pasa todavía el mínimo de tracción';
  else titular = `${plural(pasan, 'oferta pasa', 'ofertas pasan')} el mínimo de tracción`;

  const lineas = [];
  if (esNumero(c.paginas)) {
    lineas.push({ id: 'vistas', texto: `Se vieron al menos ${num(c.paginas)} páginas de anunciantes${esNumero(c.consultas_ok) ? ` en ${plural(c.consultas_ok, 'consulta', 'consultas')}` : ''}${esNumero(res.paginas_candidatas) ? `; ${num(res.paginas_candidatas)} avanzan como candidatas` : ''}.` });
  }
  if (pasan !== null) {
    lineas.push({ id: 'pasan', texto: `${plural(pasan, 'oferta cumple', 'ofertas cumplen')}: ${textoUmbral}${nTemasPasan !== null ? ` (${plural(nTemasPasan, 'tema', 'temas')} y ${plural(nSinTemaPasan || 0, 'página sin tema', 'páginas sin tema')})` : ''}.` });
  }
  if (medidas !== null || soloMuestra !== null) {
    lineas.push({ id: 'medido', texto: `${medidas !== null ? `${plural(medidas, 'página está medida', 'páginas están medidas')} por completo` : 'Sin medición completa'}${parcial !== null ? `, ${num(parcial)} parcialmente` : ''}; ${soloMuestra !== null ? `${num(soloMuestra)} son solo una muestra` : 'el resto es solo una muestra'}: su conteo es un mínimo (al menos esa cifra), no el total.` });
  }
  if (porMedir !== null && porMedir > 0) {
    lineas.push({ id: 'por_medir', texto: `${plural(porMedir, 'candidato queda', 'candidatos quedan')} por medir: no se descartan por un conteo truncado.` });
  }

  const metricas = [
    { id: 'pasan', etiqueta: 'Pasan la tracción', valor: pasan === null ? null : num(pasan), contexto: nTemasPasan !== null ? `${num(nTemasPasan)} temas + ${num(nSinTemaPasan || 0)} páginas sin tema` : textoUmbral, tono: pasan > 0 ? 'ok' : 'neutro', ayuda: 'traccion' },
    { id: 'por_medir', etiqueta: 'Por medir', valor: porMedir === null ? null : num(porMedir), contexto: 'solo se vio una muestra: la pasada 3 los mide', tono: porMedir > 0 ? 'aviso' : 'neutro', ayuda: 'indeterminado_muestra' },
    { id: 'no_pasan', etiqueta: 'No alcanzan', valor: noPasan === null ? null : num(noPasan), contexto: 'medidos y por debajo del mínimo', tono: 'neutro', ayuda: 'traccion' },
    { id: 'medido', etiqueta: 'Medido de verdad', valor: medidas === null ? null : num(medidas), contexto: med ? `de ${esNumero(c.paginas) ? `≥ ${num(c.paginas)}` : 'las'} páginas; ${num(soloMuestra)} solo muestra` : 'sin detalle de medición', tono: 'neutro', ayuda: 'medido' },
    { id: 'consultas', etiqueta: 'Consultas usadas', valor: esNumero(c.consultas_ok) ? (esNumero(c.consultas_tope) ? `${num(c.consultas_ok)} / ${num(c.consultas_tope)}` : num(c.consultas_ok)) : null, contexto: esNumero(c.consultas_tope) && esNumero(c.consultas_ok) ? `quedan ${num(Math.max(0, c.consultas_tope - c.consultas_ok))}` : 'máximo por corrida sin dato', tono: tonoCupo(c.consultas_ok, c.consultas_tope), ayuda: 'cupo_consultas' },
  ];

  const pipeline = modeloPipeline(estado, c.corrida_id);
  const hechos = pipeline.pasos.filter((p) => p.hecho === true).length;
  const conocido = pipeline.pasos.some((p) => p.hecho !== null);
  return {
    hayRanking, titular, lineas, metricas, umbral, textoUmbral,
    barrido: {
      conocido,
      pasos: pipeline.pasos,
      siguiente: pipeline.siguiente,
      hechos,
      total: pipeline.pasos.length,
      texto: !conocido ? 'Sin estado del barrido.' : pipeline.siguiente ? `${hechos} de ${pipeline.pasos.length} pasos hechos. Siguiente: ${pipeline.siguiente.titulo}.` : 'Barrido completo: plan, consultas, páginas, clasificación, ranking y fichas.',
    },
    freno: base.freno,
    pisos: base.pisos,
    avisos: base.avisos,
  };
}

// ───────────────────────── vistas (filtros) guardadas ─────────────────────────

export const FILTROS_VACIOS = Object.freeze({ q: '', estado: '', macro: '', pais: '', paisModo: 'presente', exportador: false, verificar: '', tipo: '' });

/** Vistas incluidas siempre (no se pueden borrar): los filtros que más se usan al revisar un barrido. */
export const VISTAS_BASE = Object.freeze([
  { id: 'todos', titulo: 'Todos', filtros: {} },
  { id: 'pasan', titulo: 'Pasan tracción', filtros: { estado: 'pasa' } },
  { id: 'por_medir', titulo: 'Por medir', filtros: { estado: 'indeterminada_por_muestra' } },
  { id: 'exportadores', titulo: 'Indicio de exportador', filtros: { exportador: true } },
  { id: 'por_verificar', titulo: 'Con pendientes de verificar', filtros: { verificar: 'con' } },
  { id: 'sin_tema', titulo: 'Páginas sin tema', filtros: { tipo: 'sin_tema' } },
]);

const MAX_VISTAS = 12;

/** Filtros completos (con los vacíos por defecto) y limpios de tipos raros: lo que venga del almacenamiento local no es de fiar. */
export function normalizarFiltros(f) {
  const o = f && typeof f === 'object' && !Array.isArray(f) ? f : {};
  const cad = (v, max = 80) => (typeof v === 'string' ? v.slice(0, max) : '');
  return {
    q: cad(o.q, 120),
    estado: ['pasa', 'indeterminada_por_muestra', 'no_pasa'].includes(o.estado) ? o.estado : '',
    macro: cad(o.macro, 30),
    pais: /^[A-Z]{2}$/.test(o.pais) ? o.pais : '',
    paisModo: o.paisModo === 'hueco' ? 'hueco' : 'presente',
    exportador: o.exportador === true,
    verificar: o.verificar === 'con' || o.verificar === 'sin' ? o.verificar : '',
    tipo: o.tipo === 'tema' || o.tipo === 'sin_tema' ? o.tipo : '',
  };
}

/** Lista de vistas del usuario saneada (ids únicos, nombres cortos y neutralizados, tope). */
export function normalizarVistas(lista) {
  const out = [];
  const ids = new Set(VISTAS_BASE.map((v) => v.id));
  for (const v of Array.isArray(lista) ? lista : []) {
    if (!v || typeof v !== 'object') continue;
    const titulo = neutralizar(v.titulo, { max: 40 });
    const id = typeof v.id === 'string' && /^u-[a-z0-9]{3,24}$/.test(v.id) ? v.id : null;
    if (!titulo || !id || ids.has(id)) continue;
    ids.add(id);
    out.push({ id, titulo, filtros: normalizarFiltros(v.filtros) });
    if (out.length >= MAX_VISTAS) break;
  }
  return out;
}

/** Añade (o reemplaza por nombre) una vista del usuario. `azar` inyectable para pruebas. Devuelve la lista nueva. */
export function agregarVista(lista, titulo, filtros, azar = () => Math.random().toString(36).slice(2, 8)) {
  const t = neutralizar(titulo, { max: 40 });
  const actuales = normalizarVistas(lista);
  if (!t) return actuales;
  const existente = actuales.find((v) => v.titulo.toLocaleLowerCase('es') === t.toLocaleLowerCase('es'));
  const nueva = { id: existente ? existente.id : `u-${azar().replace(/[^a-z0-9]/g, '').padEnd(6, '0').slice(0, 8)}`, titulo: t, filtros: normalizarFiltros(filtros) };
  const sin = actuales.filter((v) => v.id !== nueva.id);
  return normalizarVistas([...sin, nueva].slice(-MAX_VISTAS));
}

export function quitarVista(lista, id) { return normalizarVistas(lista).filter((v) => v.id !== id); }

/** ¿Estos filtros son los de esta vista? (para marcar la vista activa). */
export function mismosFiltros(a, b) {
  const x = normalizarFiltros(a);
  const y = normalizarFiltros(b);
  return Object.keys(FILTROS_VACIOS).every((k) => x[k] === y[k]);
}

/** Cuántos filtros hay activos (para el indicador «n filtros»). */
export function filtrosActivos(f) {
  const x = normalizarFiltros(f);
  return Object.keys(FILTROS_VACIOS).filter((k) => k !== 'paisModo' && x[k] !== FILTROS_VACIOS[k]).length;
}
