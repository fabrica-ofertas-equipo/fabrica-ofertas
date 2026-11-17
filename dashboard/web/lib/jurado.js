// lib/jurado.js — lógica pura de #/jurado («Jurado: los 10 clientes que votan antes de gastar»). Sin DOM, sin red; probada con node --test.
//
// El esquema de ofertas/<id>/06-creativos/jurado.json AÚN NO está definido (mapeo.md §6, analisis/creativos-jurado.md P3-04): este módulo lo lee con
// TOLERANCIA (ausente, vacío, de forma distinta, campos que faltan) y nunca inventa un voto, una posición ni una cifra de precisión. Lo que el archivo no
// trae sale como «sin dato». Los textos de los jurados son dato no confiable (se pintan con textContent) y su salida es SOLO INTERNA: nunca se cita
// en un anuncio («7 de 10 comprarían» sería una cifra de clientes inventada).

import { esObj, lista, texto, numero, entero, sino } from './n2-comun.js';

export const PARAMETROS = Object.freeze({
  jurados_por_mercado: 10, // [HIPÓTESIS] su número; con un mercado a la vez son 10, no 250
  etiquetas_min: 150, // por mercado, antes de ponderar o decidir
  auc_min: 0.6, // [HIPÓTESIS] AUC mínimo para usar el orden del jurado
  auc_azar: 0.5,
  brier_azar: 0.25, // Brier de apostar siempre 50 %
});

export const PASOS_JURADO = Object.freeze([
  { n: 1, id: 'ciegas', titulo: 'Mira a ciegas', icono: 'ojo', texto: 'Cada jurado ve la pieza sin saber cuál ganó antes ni cuál es nueva.' },
  { n: 2, id: 'vota', titulo: 'Vota y explica', icono: 'lapiz', texto: 'Dice sí o no, con una frase de por qué, y puntúa el gancho, la claridad y el llamado.' },
  { n: 3, id: 'ordena', titulo: 'Se ordena la tanda', icono: 'lista', texto: 'Los anuncios más votados salen primero a la prueba.' },
  { n: 4, id: 'verdad', titulo: 'A los 3 días, la verdad', icono: 'reloj', texto: 'Cada voto se cruza con lo que pasó de verdad. A los 3 días casi no hay compras: primero cuentan los clics y los pagos iniciados, y las compras cobradas cuando haya suficientes.' },
  { n: 5, id: 'pesa', titulo: 'El que acierta pesa más', icono: 'diana', texto: 'El jurado aprende quién predice mejor en cada mercado. Hasta reunir votos comprobados suficientes, todos pesan igual.' },
]);

export const REGLA = Object.freeze({
  titulo: 'Se apaga solo si no supera al azar',
  texto: 'El jurado se apaga solo si, con 150 votos comprobados o más (votos ya comparados con lo que pasó de verdad), no acierta mejor que tirar una moneda.',
  sombra: 'Mientras tanto trabaja «en sombra»: predice y se compara con lo cobrado, pero no decide nada. Es una señal, nunca un paso obligatorio: va después del control de promesas y de la revisión de calidad.',
});

// ───────────────────────── lectura tolerante de jurado.json ─────────────────────────

const CLAVES_VOTOS = ['votos', 'votes', 'votaciones', 'resultados', 'evaluaciones'];
const CLAVES_ORDEN = ['orden', 'orden_tanda', 'tanda', 'ranking', 'orden_de_tanda'];
const CLAVES_PRECISION = ['precision', 'calibracion', 'metricas', 'medicion', 'contra_cobrado', 'jurado_vs_resultado'];

function voto(v, adPorDefecto = null) {
  if (!esObj(v)) return null;
  const ad = texto([v.ad_name, v.anuncio, v.pieza, v.ad, adPorDefecto].find((x) => typeof x === 'string' && x.trim() !== ''), 120);
  if (!ad) return null;
  return {
    ad,
    avatar: texto(v.avatar_id ?? v.avatar ?? v.jurado_id ?? v.jurado, 60),
    voto: sino(v.voto ?? v.vota ?? v.decision ?? v.compraria ?? v.comprarian ?? v.aprueba),
    motivo: texto(v.motivo ?? v.razon ?? v.por_que ?? v.explicacion, 300),
    puntaje: numero(v.puntaje_general ?? v.puntaje ?? v.score ?? v.puntuacion),
    gancho: numero(v.puntaje_gancho),
    claridad: numero(v.puntaje_claridad),
    llamado: numero(v.puntaje_cta ?? v.puntaje_llamado),
  };
}

function extraerVotos(doc) {
  if (Array.isArray(doc)) return doc.map((v) => voto(v)).filter(Boolean);
  if (!esObj(doc)) return [];
  for (const k of CLAVES_VOTOS) {
    if (Array.isArray(doc[k])) return doc[k].map((v) => voto(v)).filter(Boolean);
  }
  // forma por pieza: {piezas|anuncios: [{ad_name, votos:[…]}]}
  const grupos = lista(doc.piezas).length ? doc.piezas : lista(doc.anuncios);
  const salida = [];
  for (const g of grupos) {
    if (!esObj(g)) continue;
    const ad = g.ad_name ?? g.anuncio ?? g.pieza;
    for (const k of CLAVES_VOTOS) if (Array.isArray(g[k])) salida.push(...g[k].map((v) => voto(v, ad)).filter(Boolean));
  }
  return salida;
}

const media = (xs) => { const v = xs.filter((x) => typeof x === 'number'); return v.length ? Math.round((v.reduce((a, b) => a + b, 0) / v.length) * 10) / 10 : null; };

/** Agrupa los votos por pieza: votos a favor/en contra, puntaje medio y los motivos de cada jurado. */
export function agruparPorPieza(votos) {
  const mapa = new Map();
  for (const v of lista(votos)) {
    if (!mapa.has(v.ad)) mapa.set(v.ad, []);
    mapa.get(v.ad).push(v);
  }
  return [...mapa.entries()].map(([ad, vs]) => {
    const si = vs.filter((v) => v.voto === true).length;
    const no = vs.filter((v) => v.voto === false).length;
    return { ad, si, no, sinVoto: vs.length - si - no, total: si + no, votantes: vs.length, puntaje: media(vs.map((v) => v.puntaje)), motivos: vs.map((v) => ({ avatar: v.avatar, voto: v.voto, motivo: v.motivo })) };
  });
}

function extraerOrden(doc) {
  if (!esObj(doc)) return null;
  for (const k of CLAVES_ORDEN) {
    if (!Array.isArray(doc[k])) continue;
    const filas = doc[k].map((x, i) => {
      if (typeof x === 'string') return { ad: texto(x, 120), posicion: i + 1, puntaje: null };
      if (!esObj(x)) return null;
      const ad = texto(x.ad_name ?? x.anuncio ?? x.pieza ?? x.ad, 120);
      return ad ? { ad, posicion: entero(x.posicion ?? x.rank ?? x.lugar) ?? i + 1, puntaje: numero(x.puntaje ?? x.puntaje_general ?? x.score) } : null;
    }).filter((f) => f && f.ad);
    if (filas.length) return filas.sort((a, b) => a.posicion - b.posicion);
  }
  return null;
}

function extraerPrecision(doc) {
  if (!esObj(doc)) return null;
  const fuentes = [doc, ...CLAVES_PRECISION.map((k) => doc[k]).filter(esObj)];
  let auc = null; let brier = null; let etiquetas = null; let baselines = [];
  for (const f of fuentes) {
    auc = auc ?? numero(f.auc ?? f.AUC);
    brier = brier ?? numero(f.brier ?? f.Brier);
    etiquetas = etiquetas ?? entero(f.etiquetas ?? f.n_etiquetas ?? f.n);
    const b = f.baselines ?? f.referencias ?? f.comparacion;
    if (!baselines.length && Array.isArray(b)) baselines = b.filter(esObj).map((x) => ({ nombre: texto(x.nombre ?? x.baseline, 60), auc: numero(x.auc) })).filter((x) => x.nombre);
    else if (!baselines.length && esObj(b)) baselines = Object.entries(b).map(([k, v]) => ({ nombre: texto(k, 60), auc: numero(esObj(v) ? v.auc : v) })).filter((x) => x.nombre && x.auc !== null);
  }
  if (auc === null && brier === null && etiquetas === null) return null;
  return { auc, brier, etiquetas, baselines };
}

/**
 * Lee jurado.json con tolerancia. `estado`: 'sin_archivo' (no existe) · 'ilegible' · 'vacio' (existe pero sin votos ni medición) · 'ok'.
 * @param {{estado:string, dato:any}} lectura resultado de jsonDeLectura (n2-comun)
 */
export function modeloJurado(lectura) {
  if (!lectura || lectura.estado === 'ausente') return { estado: 'sin_archivo', votos: [], piezas: [], orden: [], ordenOrigen: null, precision: null, avatares: [], ideas: [], modo: null, sello: null, generadoEn: null, mercado: null };
  if (lectura.estado !== 'ok') return { estado: lectura.estado === 'error' ? 'error' : 'ilegible', votos: [], piezas: [], orden: [], ordenOrigen: null, precision: null, avatares: [], ideas: [], modo: null, sello: null, generadoEn: null, mercado: null };
  const doc = lectura.dato;
  const votos = extraerVotos(doc);
  const piezas = agruparPorPieza(votos);
  let orden = extraerOrden(doc);
  let ordenOrigen = orden ? 'archivo' : null;
  if (!orden && piezas.length) {
    orden = piezas.slice().sort((a, b) => b.si - a.si || (b.puntaje ?? -1) - (a.puntaje ?? -1) || a.ad.localeCompare(b.ad)).map((p, i) => ({ ad: p.ad, posicion: i + 1, puntaje: p.puntaje }));
    ordenOrigen = 'calculado';
  }
  const precision = extraerPrecision(doc);
  const avatares = [...new Set(votos.map((v) => v.avatar).filter(Boolean))];
  const meta = esObj(doc) ? doc : {};
  const ideas = lista(meta.ideas).map((x) => texto(esObj(x) ? (x.idea ?? x.texto) : x, 200)).filter(Boolean).slice(0, 12);
  const hay = votos.length > 0 || (orden && orden.length) || precision;
  return {
    estado: hay ? 'ok' : 'vacio', votos, piezas, orden: orden || [], ordenOrigen, precision, avatares, ideas,
    modo: texto(meta.modo ?? meta.estado, 30), sello: texto(meta.sello ?? meta.hash ?? meta.sha256, 90), generadoEn: texto(meta.generado_en ?? meta.ts ?? meta.creado_en, 30),
    mercado: texto(meta.locale ?? meta.mercado, 16),
  };
}

// ───────────────────────── precisión contra lo cobrado ─────────────────────────

/** Veredicto honesto sobre la medición: no se juzga antes de 150 etiquetas. */
export function evaluarPrecision(p, params = PARAMETROS) {
  const min = params.etiquetas_min;
  if (!p || (p.auc === null && p.brier === null && p.etiquetas === null)) {
    return { estado: 'sin_datos', tono: 'neutro', titulo: 'Todavía no hay medición', texto: `Se mide cuando haya votos comparados con lo que pasó de verdad. Hasta reunir ${min} votos comprobados no se juzga.`, progreso: 0, etiquetas: 0, falta: min };
  }
  const n = p.etiquetas ?? 0;
  if (n < min) {
    return { estado: 'acumulando', tono: 'info', titulo: `Reuniendo votos comprobados: ${n} de ${min}`, texto: 'Con menos de 150 votos comprobados, medir el acierto es medir ruido: el jurado solo predice y se compara, no decide nada.', progreso: Math.min(1, n / min), etiquetas: n, falta: min - n };
  }
  if (p.auc === null) return { estado: 'sin_auc', tono: 'aviso', titulo: 'Hay votos comprobados, pero falta medir el acierto al ordenar', texto: 'Sin esa medida (el AUC) no se puede saber si le gana al azar.', progreso: 1, etiquetas: n, falta: 0 };
  if (p.auc <= params.auc_azar) return { estado: 'apagar', tono: 'error', titulo: 'No supera al azar: se apaga', texto: 'Con 150 votos comprobados o más no acierta mejor que una moneda. Según la regla, el jurado se apaga solo.', progreso: 1, etiquetas: n, falta: 0 };
  if (p.auc < params.auc_min) return { estado: 'sombra', tono: 'aviso', titulo: 'Supera al azar, pero aún no basta para decidir', texto: `Sigue en sombra hasta llegar a ${params.auc_min.toFixed(2).replace('.', ',')} de acierto al ordenar (AUC).`, progreso: 1, etiquetas: n, falta: 0 };
  return { estado: 'util', tono: 'ok', titulo: 'Acierta lo suficiente para ordenar la tanda', texto: 'Su orden ya puede usarse para decidir qué anuncios salen primero.', progreso: 1, etiquetas: n, falta: 0 };
}

/** Texto de un voto: «sí», «no» o «sin voto». */
export const textoVoto = (v) => (v === true ? 'sí' : v === false ? 'no' : 'sin voto');

/** Resumen de la pantalla entre ofertas: cuántas tienen jurado y cuántos votos hay en total. */
export function resumenJurado(modelos) {
  const ms = lista(modelos);
  const conDatos = ms.filter((m) => m.jurado.estado === 'ok');
  const votos = conDatos.reduce((a, m) => a + m.jurado.votos.length, 0);
  const etiquetas = conDatos.reduce((a, m) => a + (m.jurado.precision && m.jurado.precision.etiquetas ? m.jurado.precision.etiquetas : 0), 0);
  return { ofertas: ms.length, conJurado: conDatos.length, votos, piezas: conDatos.reduce((a, m) => a + m.jurado.piezas.length, 0), etiquetas, ilegibles: ms.filter((m) => m.jurado.estado === 'ilegible' || m.jurado.estado === 'error').length };
}

/** Qué papel cumple el jurado hoy: sin archivo no existe; con archivo empieza «en sombra» hasta demostrar acierto. */
export function papelDelJurado(modelos) {
  const con = lista(modelos).filter((m) => m && m.jurado && m.jurado.estado === 'ok');
  if (!con.length) return { clave: 'sin_jurado', valor: 'Sin jurado todavía', contexto: 'cuando exista, empezará «en sombra»: predice y se compara, sin decidir', tono: 'aviso' };
  const estados = con.map((m) => evaluarPrecision(m.jurado.precision).estado);
  if (estados.includes('apagar')) return { clave: 'apagar', valor: 'Para apagar', contexto: 'no le gana al azar con 150 votos comprobados o más', tono: 'critico' };
  if (estados.every((e) => e === 'util')) return { clave: 'ordena', valor: 'Ordena la tanda', contexto: 'acierta lo suficiente para decidir el orden', tono: 'ok' };
  return { clave: 'sombra', valor: 'En sombra', contexto: 'predice y se compara; no decide nada', tono: undefined };
}
