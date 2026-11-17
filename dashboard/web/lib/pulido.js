// Lógica pura de la pantalla «Pulido» (#/pulido) y de la bitácora filtrada por etapa en #/oferta/<id>.
// Bitácora = empresa/panel/pulido.jsonl (append-only; CONTRATO §6). Sin DOM ni red.
// Se prueba con `node --test` (tests/dashboard/test_web_pulido.mjs).

import { ORDEN_ETAPAS, nombreEtapa, compararEtapas, plano } from './oferta.js';

function esObjeto(x) { return x !== null && typeof x === 'object' && !Array.isArray(x); }
function cad(x) { return typeof x === 'string' ? x : (x == null ? '' : String(x)); }

export const SEVERIDADES = ['alta', 'media', 'baja'];
export const ESTADOS = ['abierta', 'en_curso', 'resuelta'];
export const TIPOS = ['observacion', 'nota', 'decision'];
// Lista única de pendientes (Cerebro v0): tipos y campos opcionales que acepta el servidor (dashboard/pulido.py). `TIPOS` sigue siendo
// lo que ofrecen los formularios de Pulido; `TIPOS_LISTA` es todo lo que puede llegar en una línea.
export const TIPOS_LISTA = ['pulido', 'observacion', 'nota', 'decision', 'pendiente', 'leccion', 'regla_propuesta'];
export const RESPONSABLES = ['dueno', 'ia', 'robot', 'otro'];
export const PRIORIDADES = ['P0', 'P1', 'P2', 'P3'];
export const CATEGORIAS = ['error', 'regla', 'pref', 'riesgo', 'contexto'];

/** Etapas válidas para anotar: el flujo por oferta y las de empresa (enum `etapa` de contratos/comunes). */
export const ETAPAS_EMPRESA = ['O0', 'D0', 'F1', 'F2', 'X1', 'X2'];
export const ETAPAS_PULIDO = [...ORDEN_ETAPAS, ...ETAPAS_EMPRESA];

const NOMBRES_EMPRESA = {
  O0: 'Coordinador general', D0: 'Cuentas y servicios base', F1: 'Finanzas', F2: 'Panel y números', X1: 'Cumplimiento', X2: 'Aprendizaje',
};
export function nombreEtapaPulido(id) { return NOMBRES_EMPRESA[id] || nombreEtapa(id); }

export const ROTULO_SEVERIDAD = { alta: 'alta', media: 'media', baja: 'baja' };
export const TONO_SEVERIDAD = { alta: 'error', media: 'aviso', baja: 'neutro' };
export const ROTULO_ESTADO = { abierta: 'abierta', en_curso: 'en curso', resuelta: 'resuelta' };
export const TONO_ESTADO = { abierta: 'aviso', en_curso: 'info', resuelta: 'ok' };
export const ROTULO_TIPO = { observacion: 'observación', nota: 'nota', decision: 'decisión', pulido: 'pulido', pendiente: 'pendiente', leccion: 'lección', regla_propuesta: 'regla propuesta' };

const PESO_SEVERIDAD = { alta: 0, media: 1, baja: 2 };

export const LIMITES = { titulo: 140, detalle: 4000 };

/** La bitácora puede llegar como array, {entradas}, {items} o {lineas}. */
export function listaCruda(datos) {
  if (Array.isArray(datos)) return datos;
  if (esObjeto(datos)) {
    for (const k of ['entradas', 'items', 'lineas', 'bitacora']) if (Array.isArray(datos[k])) return datos[k];
  }
  return [];
}

/**
 * Líneas (o entradas ya plegadas) -> entradas únicas por id. Las líneas de cambio de estado ({id, estado} sin título)
 * se pliegan sobre la entrada original; gana la última por `ts`/posición. Entradas sin id válido se descartan.
 */
export function normalizarEntradas(datos) {
  const crudas = listaCruda(datos).filter(esObjeto);
  const porId = new Map();
  const orden = [];
  for (const l of crudas) {
    const id = l.id != null ? cad(l.id) : '';
    if (!id) continue;
    const previa = porId.get(id);
    const esCambio = l.evento === 'estado' || (l.titulo == null && l.estado != null);
    if (!previa) {
      if (esCambio) { // cambio de estado cuya creación no se ve (bitácora recortada): se conserva como huérfano
        porId.set(id, { id, ts: cad(l.ts) || null, oferta_id: null, etapa: null, titulo: null, detalle: null, severidad: null, tipo: null, autor: l.autor ?? null, estado: l.estado, actualizado_en: l.ts ?? null, huerfana: true });
        orden.push(id);
      } else {
        porId.set(id, entradaBase(l));
        orden.push(id);
      }
      continue;
    }
    if (esCambio) {
      if (ESTADOS.includes(l.estado)) { previa.estado = l.estado; previa.actualizado_en = l.ts ?? previa.actualizado_en; }
    } else {
      const nueva = entradaBase(l);
      porId.set(id, { ...previa, ...nueva, estado: l.estado != null ? nueva.estado : previa.estado });
    }
  }
  return orden.map((id) => porId.get(id)).filter((e) => !e.huerfana);
}

function entradaBase(l) {
  return {
    id: cad(l.id),
    ts: typeof l.ts === 'string' ? l.ts : null,
    oferta_id: typeof l.oferta_id === 'string' && l.oferta_id !== '' ? l.oferta_id : null,
    etapa: typeof l.etapa === 'string' ? l.etapa : null,
    titulo: cad(l.titulo),
    detalle: cad(l.detalle),
    severidad: SEVERIDADES.includes(l.severidad) ? l.severidad : 'media',
    tipo: TIPOS_LISTA.includes(l.tipo) ? l.tipo : 'observacion',
    autor: typeof l.autor === 'string' ? l.autor : null,
    estado: ESTADOS.includes(l.estado) ? l.estado : 'abierta',
    actualizado_en: typeof l.ts === 'string' ? l.ts : null,
    ...camposLista(l),
  };
}

const RX_FECHA_ISO = /^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2}Z)?$/;
/** Campos opcionales de la lista única, siempre presentes en la entrada (null/[] si no vinieron o no son válidos): lo desconocido no pasa. */
export function camposLista(l) {
  const lista = (v, validos) => (typeof v === 'string' && validos.includes(v) ? v : null);
  return {
    responsable: lista(l.responsable, RESPONSABLES),
    prioridad: lista(l.prioridad, PRIORIDADES),
    categoria: lista(l.categoria, CATEGORIAS),
    origen: typeof l.origen === 'string' && l.origen !== '' ? l.origen.slice(0, 80) : null,
    bloquea: Array.isArray(l.bloquea) ? l.bloquea.filter((x) => typeof x === 'string' && x !== '').slice(0, 8).map((x) => x.slice(0, 40)) : [],
    vence: typeof l.vence === 'string' && RX_FECHA_ISO.test(l.vence) ? l.vence : null,
  };
}

/** Orden de lectura: abiertas antes que resueltas, luego severidad y luego lo más reciente. */
export function ordenarEntradas(entradas) {
  const pesoEstado = { abierta: 0, en_curso: 1, resuelta: 2 };
  return entradas
    .map((e, i) => ({ e, i }))
    .sort((a, b) => {
      const pe = (pesoEstado[a.e.estado] ?? 3) - (pesoEstado[b.e.estado] ?? 3);
      if (pe) return pe;
      const ps = (PESO_SEVERIDAD[a.e.severidad] ?? 3) - (PESO_SEVERIDAD[b.e.severidad] ?? 3);
      if (ps) return ps;
      const ta = a.e.ts || '';
      const tb = b.e.ts || '';
      if (ta !== tb) return ta < tb ? 1 : -1;
      return b.i - a.i;
    })
    .map((p) => p.e);
}

export const FILTROS_VACIOS = Object.freeze({ texto: '', oferta: '', etapa: '', severidad: '', estado: '', tipo: '', ocultarResueltas: false });

/** `oferta`: '' = todas; '_global' = sin oferta; otro valor = esa oferta. */
export function filtrarEntradas(entradas, filtros = {}) {
  const f = { ...FILTROS_VACIOS, ...filtros };
  const t = plano(String(f.texto || '').trim());
  return entradas.filter((e) => {
    if (f.oferta === '_global') { if (e.oferta_id) return false; } else if (f.oferta && e.oferta_id !== f.oferta) return false;
    if (f.etapa && e.etapa !== f.etapa) return false;
    if (f.severidad && e.severidad !== f.severidad) return false;
    if (f.estado && e.estado !== f.estado) return false;
    if (f.tipo && e.tipo !== f.tipo) return false;
    if (f.ocultarResueltas && e.estado === 'resuelta') return false;
    if (t && !plano(`${e.titulo} ${e.detalle} ${e.id} ${e.oferta_id || ''} ${e.etapa || ''}`).includes(t)) return false;
    return true;
  });
}

export function hayFiltros(filtros = {}) {
  const f = { ...FILTROS_VACIOS, ...filtros };
  return Object.keys(FILTROS_VACIOS).some((k) => f[k] !== FILTROS_VACIOS[k]);
}

/**
 * Conteos por etapa: [{etapa, nombre, abiertas, enCurso, resueltas, total, altaPendiente}], en orden del flujo.
 * Incluye siempre las 11 etapas del flujo (aunque estén en cero) y las demás solo si tienen entradas.
 */
export function conteosPorEtapa(entradas, { oferta = '' } = {}) {
  const base = oferta === '_global' ? entradas.filter((e) => !e.oferta_id) : (oferta ? entradas.filter((e) => e.oferta_id === oferta) : entradas);
  const mapa = new Map();
  const asegurar = (id) => {
    if (!mapa.has(id)) mapa.set(id, { etapa: id, nombre: nombreEtapaPulido(id), abiertas: 0, enCurso: 0, resueltas: 0, total: 0, altaPendiente: 0 });
    return mapa.get(id);
  };
  for (const id of ORDEN_ETAPAS) asegurar(id);
  for (const e of base) {
    if (!e.etapa) continue;
    const c = asegurar(e.etapa);
    c.total += 1;
    if (e.estado === 'abierta') c.abiertas += 1;
    else if (e.estado === 'en_curso') c.enCurso += 1;
    else if (e.estado === 'resuelta') c.resueltas += 1;
    if (e.severidad === 'alta' && e.estado !== 'resuelta') c.altaPendiente += 1;
  }
  return [...mapa.values()]
    .filter((c) => ORDEN_ETAPAS.includes(c.etapa) || c.total > 0)
    .sort((a, b) => compararEtapasPulido(a.etapa, b.etapa));
}

export function compararEtapasPulido(a, b) {
  const ia = ETAPAS_PULIDO.indexOf(a);
  const ib = ETAPAS_PULIDO.indexOf(b);
  if (ia >= 0 && ib >= 0) return ia - ib;
  if (ia >= 0) return -1;
  if (ib >= 0) return 1;
  return compararEtapas(a, b);
}

/** Resumen general: pendientes (abiertas + en curso), altas pendientes, resueltas. */
export function resumenBitacora(entradas) {
  let abiertas = 0; let enCurso = 0; let resueltas = 0; let altas = 0;
  for (const e of entradas) {
    if (e.estado === 'abierta') abiertas += 1;
    else if (e.estado === 'en_curso') enCurso += 1;
    else if (e.estado === 'resuelta') resueltas += 1;
    if (e.severidad === 'alta' && e.estado !== 'resuelta') altas += 1;
  }
  const total = entradas.length;
  return {
    total, abiertas, enCurso, resueltas, altasPendientes: altas, pendientes: abiertas + enCurso,
    bpResueltas: total === 0 ? 0 : Math.round((resueltas * 10000) / total),
  };
}

/** Ofertas que aparecen en la bitácora (para el filtro), más las conocidas por la lista de ofertas. */
export function ofertasEnBitacora(entradas, conocidas = []) {
  const s = new Set(conocidas.filter((x) => typeof x === 'string' && x !== ''));
  for (const e of entradas) if (e.oferta_id) s.add(e.oferta_id);
  return [...s].sort();
}

/** Entradas de una etapa de una oferta (más las globales de esa etapa si `incluirGlobales`). */
export function entradasDeEtapa(entradas, ofertaId, etapa, { incluirGlobales = true } = {}) {
  return ordenarEntradas(entradas.filter((e) => e.etapa === etapa && (e.oferta_id === ofertaId || (incluirGlobales && !e.oferta_id))));
}

// ---------------------------------------------------------------------------------------------
// Formularios: validación y cuerpo del POST (solo los campos que el contrato admite).

// Mismos formatos que valida el servidor (dashboard/api_base.RX_OFERTA y dashboard/pulido._RX_ID).
const RX_OFERTA = /^(OF-[0-9]{6}-[0-9]{2}|_[a-z0-9][a-z0-9_-]{0,31})$/;
const RX_ENTRADA = /^PUL-[0-9]{4,9}$/;

/** Valida el formulario de una observación nueva. Devuelve {ok, errores:{campo:mensaje}, cuerpo}. */
export function validarNueva(f = {}) {
  const errores = {};
  const etapa = cad(f.etapa).trim();
  const titulo = cad(f.titulo).trim();
  const detalle = cad(f.detalle).trim();
  const severidad = cad(f.severidad || 'media');
  const tipo = cad(f.tipo || 'observacion');
  const oferta = cad(f.oferta_id).trim();
  if (!ETAPAS_PULIDO.includes(etapa)) errores.etapa = 'Elige la etapa a la que se refiere.';
  if (titulo === '') errores.titulo = 'Escribe un título corto.';
  else if ([...titulo].length > LIMITES.titulo) errores.titulo = `Máximo ${LIMITES.titulo} caracteres.`;
  if ([...detalle].length > LIMITES.detalle) errores.detalle = `Máximo ${LIMITES.detalle} caracteres.`;
  if (!SEVERIDADES.includes(severidad)) errores.severidad = 'Elige una gravedad: alta, media o baja.';
  if (!TIPOS.includes(tipo)) errores.tipo = 'Elige un tipo de nota válido.';
  if (oferta !== '' && !RX_OFERTA.test(oferta)) errores.oferta_id = 'El código de la oferta no es válido (ejemplo: OF-202611-01).';
  const cuerpo = { etapa, titulo, detalle, severidad, tipo };
  if (oferta !== '') cuerpo.oferta_id = oferta;
  return { ok: Object.keys(errores).length === 0, errores, cuerpo };
}

/** Cuerpo del POST de cambio de estado. Lanza si el estado no es válido (no se envía nada inventado). */
export function cuerpoCambioEstado(id, estado) {
  if (!ESTADOS.includes(estado)) throw new RangeError(`estado no válido: ${estado}`);
  if (!RX_ENTRADA.test(cad(id))) throw new RangeError(`id de entrada no válido: ${cad(id)}`);
  return { id: cad(id), estado };
}

/** Siguiente estado «natural» al avanzar una entrada. */
export function siguienteEstado(estado) {
  if (estado === 'abierta') return 'en_curso';
  if (estado === 'en_curso') return 'resuelta';
  return 'abierta';
}

export function etiquetaSiguiente(estado) {
  if (estado === 'abierta') return 'Empezar';
  if (estado === 'en_curso') return 'Resolver';
  return 'Reabrir';
}

// ---------------------------------------------------------------------------------------------
// Tablero (rediseño UX): columnas Abierta / En curso / Resuelta, conteos por severidad y madurez por etapa.

export const TITULO_ESTADO = { abierta: 'Abierta', en_curso: 'En curso', resuelta: 'Resuelta' };
export const AYUDA_ESTADO = {
  abierta: 'Anotada, todavía sin empezar.',
  en_curso: 'La estás corrigiendo ahora.',
  resuelta: 'Corregida: ya es una regla de la guía de trabajo o un arreglo hecho.',
};
export const TITULO_SEVERIDAD = { alta: 'Alta', media: 'Media', baja: 'Baja' };
export const AYUDA_SEVERIDAD = {
  alta: 'Frena que la etapa corra sola.',
  media: 'Molesta, pero no frena.',
  baja: 'Mejora opcional.',
};
export const TITULO_TIPO = { observacion: 'Observación', nota: 'Nota', decision: 'Decisión', pulido: 'Mejora pendiente', pendiente: 'Pendiente', leccion: 'Lección', regla_propuesta: 'Regla propuesta' };

/** Tablero: una columna por estado con las entradas filtradas (alta primero, lo más reciente antes). */
export function columnasTablero(entradas, filtros = {}) {
  // el filtro de estado no aplica a un tablero (las columnas YA son los estados)
  const vista = ordenarEntradas(filtrarEntradas(entradas, { ...filtros, estado: '', ocultarResueltas: false }));
  return ESTADOS.map((estado) => ({ estado, titulo: TITULO_ESTADO[estado], items: vista.filter((e) => e.estado === estado) }));
}

/** Pendientes (abiertas + en curso) por severidad. */
export function conteosPorSeveridad(entradas) {
  const base = { alta: { pendientes: 0, resueltas: 0, total: 0 }, media: { pendientes: 0, resueltas: 0, total: 0 }, baja: { pendientes: 0, resueltas: 0, total: 0 } };
  for (const e of entradas) {
    const c = base[e.severidad];
    if (!c) continue;
    c.total += 1;
    if (e.estado === 'resuelta') c.resueltas += 1; else c.pendientes += 1;
  }
  return base;
}

/**
 * Madurez de pulido de una etapa: `sin_notas` (aún no se anotó nada), `pulir` (hay pendientes), `limpia` (todo resuelto).
 * Sirve para ver de un vistazo qué pasos ya están listos para correr solos.
 */
export function madurezEtapa(c) {
  if (!c || c.total === 0) return 'sin_notas';
  return c.abiertas + c.enCurso > 0 ? 'pulir' : 'limpia';
}

/** Conteos por etapa del flujo (las 11) listos para el mapa: añade `madurez`, `pendientes` y el máximo para escalar las barras. */
export function mapaPulido(entradas, { oferta = '' } = {}) {
  const filas = conteosPorEtapa(entradas, { oferta }).map((c) => ({ ...c, pendientes: c.abiertas + c.enCurso, madurez: madurezEtapa(c) }));
  const max = filas.reduce((m, c) => Math.max(m, c.pendientes), 0);
  return { filas, maxPendientes: max, conNotas: filas.filter((c) => c.total > 0).length, limpias: filas.filter((c) => c.madurez === 'limpia').length };
}

/** Alta rápida: solo título (y opcionalmente etapa, oferta y severidad). Devuelve lo mismo que `validarNueva`. */
export function validarRapida({ titulo = '', etapa = '', oferta_id = '', severidad = 'media' } = {}) {
  return validarNueva({ titulo, etapa, oferta_id, severidad, tipo: 'observacion', detalle: '' });
}

/** ¿Se puede mover una entrada a este estado? (arrastrar entre columnas). Mismo estado = no. */
export function puedeMover(entrada, estado) {
  return Boolean(entrada) && ESTADOS.includes(estado) && entrada.estado !== estado;
}

/** Entrada → texto corto para el título accesible de una tarjeta. */
export function resumenEntrada(e) {
  return `${TITULO_SEVERIDAD[e.severidad] || e.severidad}, ${(TITULO_ESTADO[e.estado] || e.estado).toLowerCase()}: ${e.titulo || 'sin título'}`;
}
