// Lógica pura de la pantalla «Cerebro» (#/cerebro): lo que el sistema recuerda. Sin DOM ni red; se prueba con `node --test`
// (tests/dashboard/test_web_cerebro.mjs).
//
// Datos: la lista única de pendientes sale de GET /api/pulido (empresa/panel/pulido.jsonl, ampliada con tipo, responsable, prioridad, origen,
// categoría, bloquea y vence) y lo demás de GET /api/cerebro (memoria, decisiones, reglas, lecciones, jardín; solo lectura).
// El panel NUNCA escribe una regla: una regla propuesta es un pendiente que el dueño aprueba a mano.

import { plano } from './oferta.js';
import * as P from './pulido.js';
import { ETAPAS_PULIDO, normalizarEntradas, cuerpoCambioEstado, LIMITES } from './pulido.js';

function esObjeto(x) { return x !== null && typeof x === 'object' && !Array.isArray(x); }
function cad(x) { return typeof x === 'string' ? x : (x == null ? '' : String(x)); }
function lista(x) { return Array.isArray(x) ? x : []; }
function entero(x) { return Number.isInteger(x) ? x : null; }
function objetos(x) { return lista(x).filter(esObjeto); }

export { normalizarEntradas, cuerpoCambioEstado, ETAPAS_PULIDO, LIMITES };

// ───────────────────────── cabecera: el ciclo de sesión ─────────────────────────

export const TITULO = 'Cerebro: lo que el sistema recuerda';
export const PRINCIPIO = 'Una IA sin memoria arranca de cero cada vez. El Cerebro guarda lo que decidiste, lo que salió mal y lo que queda por hacer, para que la próxima sesión no empiece de cero.';

/** Los 4 pasos del ciclo de cada sesión. `comando`: skill manual que lo hace; `ancla`: bloque de esta pantalla; `estado: 'sin_construir'` si aún no existe. */
export const CICLO = Object.freeze([
  { id: 'abrir', numero: 1, titulo: 'Al abrir', texto: 'Lee tus recordatorios y pendientes antes de empezar.', comando: '/cerebro-abrir', icono: 'play' },
  { id: 'trabajar', numero: 2, titulo: 'Al trabajar', texto: 'Anota en el momento lo que decides, cierras o descubres.', ancla: 'pendientes', rotuloAncla: 'Anotar un pendiente', icono: 'lapiz' },
  { id: 'cerrar', numero: 3, titulo: 'Al cerrar', texto: 'Guarda solo lo nuevo, sin repetir lo que ya estaba guardado. Tú confirmas antes de escribir.', comando: '/cerebro-cerrar', icono: 'archivar' },
  { id: 'domingo', numero: 4, titulo: 'El domingo', texto: 'Un jardinero ordena, une y archiva lo viejo: propone y tú haces clic. Nada se borra.', estado: 'sin_construir', icono: 'refrescar' },
]);

// ───────────────────────── pendientes: la lista única ─────────────────────────

export const PRIORIDADES = P.PRIORIDADES;
export const RESPONSABLES = P.RESPONSABLES;
export const ROTULO_PRIORIDAD = { P0: 'P0', P1: 'P1', P2: 'P2', P3: 'P3' };
export const AYUDA_PRIORIDAD = {
  P0: 'Bloquea gastar o activar algo.',
  P1: 'Bloquea una etapa.',
  P2: 'Mejora, no bloquea.',
  P3: 'Idea para más adelante.',
};
/** Versión corta para los desplegables («P1 · Bloquea etapa»). */
export const CORTO_PRIORIDAD = { P0: 'Bloquea gasto', P1: 'Bloquea etapa', P2: 'Mejora', P3: 'Idea' };
export const TONO_PRIORIDAD = { P0: 'critico', P1: 'grave', P2: 'aviso', P3: 'neutro' };
export const ROTULO_RESPONSABLE = { dueno: 'Tú', ia: 'IA', robot: 'Robot', otro: 'Otro' };
export const ROTULO_TIPO = { pulido: 'Mejora pendiente', observacion: 'Mejora pendiente', nota: 'Nota', pendiente: 'Pendiente', decision: 'Decisión', leccion: 'Lección', regla_propuesta: 'Regla propuesta' };
export const ROTULO_CATEGORIA = { error: 'Error', regla: 'Regla', pref: 'Preferencia', riesgo: 'Riesgo', contexto: 'Solo este caso' };

const PESO_PRIORIDAD = { P0: 0, P1: 1, P2: 2, P3: 3 };
const PESO_SEVERIDAD = { alta: 0, media: 1, baja: 2 };
/** Tipos que son «algo por hacer»; decisión y lección son conocimiento, y la regla propuesta se aprueba aparte (bloque Reglas). */
const TIPOS_TAREA = new Set(['pulido', 'observacion', 'nota', 'pendiente']);

/**
 * Reparte las entradas de la bitácora: `pendientes` (por hacer, todas las del tipo tarea, con su estado), `decisiones`, `lecciones` y
 * `reglasPropuestas`. No muta nada.
 */
export function clasificar(entradas) {
  const salida = { pendientes: [], decisiones: [], lecciones: [], reglasPropuestas: [] };
  for (const e of lista(entradas)) {
    if (!esObjeto(e)) continue;
    if (e.tipo === 'decision') salida.decisiones.push(e);
    else if (e.tipo === 'leccion') salida.lecciones.push(e);
    else if (e.tipo === 'regla_propuesta') salida.reglasPropuestas.push(e);
    else if (TIPOS_TAREA.has(e.tipo) || !e.tipo) salida.pendientes.push(e);
  }
  return salida;
}

export const esAbierta = (e) => Boolean(e) && e.estado !== 'resuelta';

export const FILTROS_VACIOS = Object.freeze({ prioridad: '', responsable: '', bloquea: '', texto: '', verResueltas: false });

export function hayFiltros(f = {}) {
  const x = { ...FILTROS_VACIOS, ...f };
  return Object.keys(FILTROS_VACIOS).some((k) => x[k] !== FILTROS_VACIOS[k]);
}

/**
 * Filtros: `prioridad` ('' todas · P0..P3 · 'sin' sin prioridad) · `responsable` ('' · dueno|ia|robot|otro · 'sin') ·
 * `bloquea` ('' · '*' bloquea algo · un id/etapa concreto) · `texto` · `verResueltas`.
 */
export function filtrarPendientes(entradas, filtros = {}) {
  const f = { ...FILTROS_VACIOS, ...filtros };
  const t = plano(f.texto || '').trim();
  return objetos(entradas).filter((e) => {
    if (!f.verResueltas && !esAbierta(e)) return false;
    if (f.prioridad === 'sin' ? e.prioridad : (f.prioridad && e.prioridad !== f.prioridad)) return false;
    if (f.responsable === 'sin' ? e.responsable : (f.responsable && e.responsable !== f.responsable)) return false;
    const bloquea = lista(e.bloquea);
    if (f.bloquea === '*' ? bloquea.length === 0 : (f.bloquea && !bloquea.includes(f.bloquea))) return false;
    if (t && !plano(`${e.titulo} ${e.detalle} ${e.id} ${e.origen || ''} ${e.oferta_id || ''} ${e.etapa || ''} ${bloquea.join(' ')}`).includes(t)) return false;
    return true;
  });
}

/** Valores distintos de `bloquea` en las entradas (para el filtro), ordenados. */
export function valoresBloquea(entradas) {
  const s = new Set();
  for (const e of objetos(entradas)) for (const b of lista(e.bloquea)) s.add(b);
  return [...s].sort((a, b) => a.localeCompare(b, 'es'));
}

function diaUtc(valor) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(cad(valor));
  if (!m) return null;
  const ms = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  return Number.isNaN(ms) ? null : Math.floor(ms / 86400000);
}

/**
 * Vencimiento de una entrada respecto de `ahoraMs`: `{estado: 'vencido'|'hoy'|'proximo'|'lejano'|'sin', dias, texto}`.
 * `dias` > 0 faltan; < 0 pasaron. «Próximo» = en 7 días o menos. Una entrada resuelta nunca figura como vencida.
 */
export function vencimiento(entrada, ahoraMs = Date.now()) {
  const dv = diaUtc(entrada && entrada.vence);
  if (dv === null || !esAbierta(entrada)) return { estado: 'sin', dias: null, texto: '' };
  const dias = dv - Math.floor(ahoraMs / 86400000);
  if (dias < 0) return { estado: 'vencido', dias, texto: dias === -1 ? 'venció ayer' : `venció hace ${-dias} días` };
  if (dias === 0) return { estado: 'hoy', dias, texto: 'vence hoy' };
  if (dias <= 7) return { estado: 'proximo', dias, texto: dias === 1 ? 'vence mañana' : `vence en ${dias} días` };
  return { estado: 'lejano', dias, texto: `vence el ${cad(entrada.vence).slice(0, 10)}` };
}

export const TONO_VENCIMIENTO = { vencido: 'critico', hoy: 'grave', proximo: 'aviso', lejano: 'neutro' };

/** Orden de lectura: abiertas primero; prioridad (P0 antes; sin prioridad al final); gravedad; vencimiento más cercano; lo más reciente. */
export function ordenarPendientes(entradas, ahoraMs = Date.now()) {
  const pesoEstado = { abierta: 1, en_curso: 0, resuelta: 2 };
  const dias = (e) => { const v = vencimiento(e, ahoraMs); return v.dias === null ? Infinity : v.dias; };
  return objetos(entradas)
    .map((e, i) => ({ e, i }))
    .sort((a, b) => {
      const pe = (pesoEstado[a.e.estado] ?? 3) - (pesoEstado[b.e.estado] ?? 3);
      if (pe) return pe;
      const pp = (PESO_PRIORIDAD[a.e.prioridad] ?? 4) - (PESO_PRIORIDAD[b.e.prioridad] ?? 4);
      if (pp) return pp;
      const ps = (PESO_SEVERIDAD[a.e.severidad] ?? 3) - (PESO_SEVERIDAD[b.e.severidad] ?? 3);
      if (ps) return ps;
      const da = dias(a.e);
      const db = dias(b.e);
      if (da !== db) return da < db ? -1 : 1;
      const ta = a.e.ts || '';
      const tb = b.e.ts || '';
      if (ta !== tb) return ta < tb ? 1 : -1;
      return b.i - a.i;
    })
    .map((p) => p.e);
}

/** Botones de estado de una entrada: `{texto, a, primario?}`; «a» es el estado al que pasa (POST /pulido {id, estado}). */
export function accionesEstado(estado) {
  if (estado === 'abierta') return [{ texto: 'Empezar', a: 'en_curso' }, { texto: 'Resolver', a: 'resuelta', primario: true }];
  if (estado === 'en_curso') return [{ texto: 'Resolver', a: 'resuelta', primario: true }, { texto: 'Soltar', a: 'abierta' }];
  return [{ texto: 'Reabrir', a: 'abierta' }];
}

/** «1 vencido» / «3 vencidos»: concordancia para los textos de las cifras. */
export function plural(n, singular, plural_) { return `${n} ${n === 1 ? singular : plural_}`; }

/** Cifras de cabecera sobre los pendientes (todas las abiertas, sin filtros). */
export function resumenPendientes(entradas, ahoraMs = Date.now()) {
  const abiertas = objetos(entradas).filter(esAbierta);
  const r = { abiertos: abiertas.length, enCurso: 0, p0: 0, p1: 0, esperanTuDecision: 0, sinResponsable: 0, vencidos: 0, porVencer: 0, bloqueantes: 0, sinPrioridad: 0 };
  for (const e of abiertas) {
    if (e.estado === 'en_curso') r.enCurso += 1;
    if (e.prioridad === 'P0') r.p0 += 1;
    if (e.prioridad === 'P1') r.p1 += 1;
    if (!e.prioridad) r.sinPrioridad += 1;
    if (e.responsable === 'dueno') r.esperanTuDecision += 1;
    if (!e.responsable) r.sinResponsable += 1;
    if (lista(e.bloquea).length) r.bloqueantes += 1;
    const v = vencimiento(e, ahoraMs);
    if (v.estado === 'vencido') r.vencidos += 1;
    else if (v.estado === 'hoy' || v.estado === 'proximo') r.porVencer += 1;
  }
  return r;
}

// ───────────────────────── alta rápida ─────────────────────────

export const TIPOS_ALTA_RAPIDA = Object.freeze([
  { valor: 'pendiente', texto: 'Pendiente' },
  { valor: 'decision', texto: 'Decisión mía' },
  { valor: 'regla_propuesta', texto: 'Propuesta de regla' },
]);
const SEVERIDAD_DE_PRIORIDAD = { P0: 'alta', P1: 'alta', P2: 'media', P3: 'baja' };
const RX_BLOQUEA = /^[A-Za-z0-9][A-Za-z0-9_.:-]{0,39}$/;
const RX_FECHA = /^\d{4}-\d{2}-\d{2}$/;
const RX_OFERTA = /^(OF-[0-9]{6}-[0-9]{2}|_[a-z0-9][a-z0-9_-]{0,31})$/;

/** «D7, activar_campana OF-202611-01» → ['D7','activar_campana','OF-202611-01'] (sin repetidos). Devuelve {items, invalidos}. */
export function partirBloquea(texto) {
  const items = [];
  const invalidos = [];
  for (const t of cad(texto).split(/[\s,;]+/).filter(Boolean)) {
    if (!RX_BLOQUEA.test(t)) invalidos.push(t);
    else if (!items.includes(t)) items.push(t);
  }
  return { items, invalidos };
}

function fechaReal(s) {
  if (!RX_FECHA.test(s)) return false;
  const d = new Date(`${s}T00:00:00Z`);
  return !Number.isNaN(d.getTime()) && d.toISOString().slice(0, 10) === s;
}

/**
 * Valida el alta rápida y arma el cuerpo del POST /pulido (solo los campos que el servidor admite; lo vacío no se envía).
 * `tipo`: pendiente (por defecto) · decision · regla_propuesta. Una regla propuesta nunca se aplica sola: queda abierta para que la apruebes a mano.
 */
export function validarAlta(f = {}) {
  const errores = {};
  const titulo = cad(f.titulo).trim();
  const detalle = cad(f.detalle).trim();
  const tipo = cad(f.tipo || 'pendiente');
  const etapa = cad(f.etapa || 'O0').trim();
  const prioridad = cad(f.prioridad);
  const responsable = cad(f.responsable);
  const oferta = cad(f.oferta_id).trim();
  const vence = cad(f.vence).trim();
  const bloquea = partirBloquea(f.bloquea);
  if (titulo === '') errores.titulo = 'Escribe en una línea qué queda por hacer.';
  else if ([...titulo].length > LIMITES.titulo) errores.titulo = `Máximo ${LIMITES.titulo} caracteres.`;
  if ([...detalle].length > LIMITES.detalle) errores.detalle = `Máximo ${LIMITES.detalle} caracteres.`;
  if (!TIPOS_ALTA_RAPIDA.some((t) => t.valor === tipo)) errores.tipo = 'Tipo no válido.';
  if (!ETAPAS_PULIDO.includes(etapa)) errores.etapa = 'Elige la etapa a la que se refiere.';
  if (prioridad !== '' && !PRIORIDADES.includes(prioridad)) errores.prioridad = 'Prioridad no válida.';
  if (responsable !== '' && !RESPONSABLES.includes(responsable)) errores.responsable = 'Responsable no válido.';
  if (oferta !== '' && !RX_OFERTA.test(oferta)) errores.oferta_id = 'El código de la oferta no es válido (ejemplo: OF-202611-01).';
  if (bloquea.invalidos.length) errores.bloquea = `Escribe etapas (D7) o códigos de oferta (OF-202611-01) válidos. No sirven: ${bloquea.invalidos.slice(0, 3).join(', ')}.`;
  else if (bloquea.items.length > 8) errores.bloquea = 'Hasta 8 elementos.';
  if (vence !== '' && !fechaReal(vence)) errores.vence = 'Usa una fecha real con el formato AAAA-MM-DD.';
  const cuerpo = { etapa, titulo, severidad: SEVERIDAD_DE_PRIORIDAD[prioridad] || 'media', tipo, origen: 'panel: Cerebro' };
  if (detalle !== '') cuerpo.detalle = detalle;
  if (prioridad !== '') cuerpo.prioridad = prioridad;
  if (responsable !== '') cuerpo.responsable = responsable;
  if (oferta !== '') cuerpo.oferta_id = oferta;
  if (bloquea.items.length) cuerpo.bloquea = bloquea.items;
  if (vence !== '') cuerpo.vence = vence;
  return { ok: Object.keys(errores).length === 0, errores, cuerpo };
}

// ───────────────────────── decisiones vigentes ─────────────────────────

/**
 * Decisiones del dueño: los documentos (solo enlazados y contados, con su ruta y hash), las guardadas al cerrar sesiones y las anotadas
 * en la bitácora con tipo «decisión».
 */
export function resumenDecisiones(cerebro, entradas = []) {
  const d = esObjeto(cerebro) && esObjeto(cerebro.decisiones) ? cerebro.decisiones : {};
  const fuentes = lista(d.fuentes).filter(esObjeto).map((f) => ({
    clave: cad(f.clave), titulo: cad(f.titulo), ruta: cad(f.ruta), existe: f.existe === true,
    decisiones: entero(f.decisiones), tareasAbiertas: entero(f.tareas_abiertas), tareasHechas: entero(f.tareas_hechas),
    bytes: entero(f.bytes), sha256: typeof f.sha256 === 'string' ? f.sha256 : null, modificado: typeof f.modificado === 'string' ? f.modificado : null,
  }));
  const m = esObjeto(d.memoria) ? d.memoria : {};
  const guardadas = lista(m.ultimas).filter(esObjeto).filter((x) => x.vigente !== false);
  const anotadas = lista(entradas).filter((e) => e && e.tipo === 'decision');
  const enDocumentos = fuentes.reduce((n, f) => n + (f.decisiones || 0), 0);
  return {
    fuentes, guardadas, anotadas, rutaMemoria: cad(m.ruta) || 'empresa/memoria/decisiones_dueno.jsonl', memoriaExiste: m.existe === true,
    enDocumentos, vigentesGuardadas: entero(m.vigentes) ?? guardadas.length, tareasAbiertasDocumentos: fuentes.reduce((n, f) => n + (f.tareasAbiertas || 0), 0),
    hayDocumentos: fuentes.some((f) => f.existe),
    sinDatos: !fuentes.some((f) => f.existe) && guardadas.length === 0 && anotadas.length === 0,
  };
}

// ───────────────────────── reglas (solo lectura) ─────────────────────────

/** Tarjetas de reglas de solo lectura y las propuestas que esperan que las apruebes a mano. */
export function resumenReglas(cerebro, entradas = []) {
  const r = esObjeto(cerebro) && esObjeto(cerebro.reglas) ? cerebro.reglas : {};
  const par = esObjeto(r.parametros) ? r.parametros : {};
  const lim = esObjeto(r.limites) ? r.limites : {};
  const aut = esObjeto(r.autonomia) ? r.autonomia : {};
  const sel = esObjeto(r.sellos_compliance) ? r.sellos_compliance : {};
  const niveles = esObjeto(aut.por_nivel) ? Object.entries(aut.por_nivel).sort(([a], [b]) => a.localeCompare(b)).map(([n, c]) => `${c} en el nivel ${String(n).replace(/^N/i, '')}`).join(' · ') : '';
  const tarjetas = [
    {
      clave: 'parametros', titulo: 'Valores ajustables del sistema', existe: par.existe === true,
      valor: par.existe ? `${entero(par.claves) ?? 0} valores` : null,
      detalle: par.existe ? `${entero(par.hipotesis) ?? 0} son hipótesis por ajustar con datos reales · ${entero(par.sin_valor) ?? 0} sin valor todavía` : 'No se encontró el archivo de valores ajustables.',
      tono: par.existe ? 'info' : 'aviso', ruta: cad(par.ruta) || 'empresa/parametros.yaml', sha256: typeof par.sha256 === 'string' ? par.sha256 : null,
    },
    {
      clave: 'limites', titulo: 'Límites del dueño (techos de dinero)', existe: lim.existe === true,
      valor: lim.existe ? (lim.sellado ? 'Firmados por ti' : 'Sin tu firma') : null,
      detalle: lim.existe ? `${entero(lim.sin_valor) ?? 0} de ${entero(lim.claves) ?? 0} datos sin fijar. Mientras falten, nada gasta ni se activa.` : 'No se encontró el archivo de límites.',
      tono: lim.existe ? (lim.sellado ? 'ok' : 'aviso') : 'aviso', ruta: cad(lim.ruta) || 'empresa/limites.yaml', sha256: typeof lim.sha256 === 'string' ? lim.sha256 : null,
    },
    {
      clave: 'autonomia', titulo: 'Cuánto hace solo cada etapa', existe: aut.existe === true,
      valor: aut.existe ? `${entero(aut.etapas) ?? 0} etapas` : null,
      detalle: aut.existe ? (niveles || 'Sin niveles definidos.') : 'No se encontró el archivo de niveles de autonomía.',
      tono: aut.existe ? 'neutro' : 'aviso', ruta: cad(aut.ruta) || 'empresa/autonomia.yaml', sha256: typeof aut.sha256 === 'string' ? aut.sha256 : null,
    },
    {
      clave: 'sellos', titulo: 'Vistos buenos de cumplimiento', existe: true,
      valor: `${entero(sel.archivos) ?? 0} firmados`,
      detalle: (entero(sel.archivos) ?? 0) === 0 ? 'Todavía ninguno: los firma el código de cumplimiento, nunca una IA.' : 'Los firma el código de cumplimiento; una IA no los firma.',
      tono: 'neutro', ruta: cad(sel.ruta) || 'empresa/compliance/sellos', sha256: null,
    },
  ];
  const propuestas = ordenarPendientes(lista(entradas).filter((e) => e && e.tipo === 'regla_propuesta' && esAbierta(e)));
  return { tarjetas, propuestas, hayArchivos: tarjetas.slice(0, 3).some((t) => t.existe) };
}

// ───────────────────────── lecciones ─────────────────────────

/** Lecciones: hallazgos de QA por patrón, aprendizajes, post-mortems y las guardadas con su prueba. Todo vacío es vacío honesto, nunca un cero inventado. */
export function resumenLecciones(cerebro, entradas = []) {
  const l = esObjeto(cerebro) && esObjeto(cerebro.lecciones) ? cerebro.lecciones : {};
  const qa = esObjeto(l.qa) ? l.qa : {};
  const hallazgos = lista(qa.hallazgos).filter(esObjeto);
  const aprendizajes = lista(qa.aprendizajes).filter(esObjeto);
  const postmortems = lista(l.postmortems).filter(esObjeto);
  const guardadas = esObjeto(l.memoria) ? lista(l.memoria.ultimas).filter(esObjeto) : [];
  const anotadas = lista(entradas).filter((e) => e && e.tipo === 'leccion');
  const patrones = new Map();
  const porSeveridad = {};
  for (const h of hallazgos) {
    const clave = cad(h.patron_clave) || '(sin patrón)';
    const p = patrones.get(clave) || { patron: clave, n: 0, ofertas: new Set(), etapas: new Set(), ejemplo: null };
    p.n += 1;
    if (h.oferta_id) p.ofertas.add(h.oferta_id);
    if (h.etapa) p.etapas.add(h.etapa);
    if (!p.ejemplo && h.descripcion) p.ejemplo = h.descripcion;
    patrones.set(clave, p);
    const sev = cad(h.severidad) || 'sin severidad';
    porSeveridad[sev] = (porSeveridad[sev] || 0) + 1;
  }
  const top = [...patrones.values()].map((p) => ({ patron: p.patron, n: p.n, ofertas: p.ofertas.size, etapas: [...p.etapas].sort(), ejemplo: p.ejemplo }))
    .sort((a, b) => b.n - a.n || a.patron.localeCompare(b.patron, 'es')).slice(0, 6);
  const todosDemo = (hallazgos.length + aprendizajes.length + postmortems.length) > 0
    && [...hallazgos, ...aprendizajes, ...postmortems].every((x) => x.demo === true);
  const vacio = hallazgos.length === 0 && aprendizajes.length === 0 && postmortems.length === 0 && guardadas.length === 0 && anotadas.length === 0;
  return {
    hallazgos: hallazgos.length, archivosQa: entero(qa.archivos) ?? 0, aprendizajes, postmortems, guardadas, anotadas, top, porSeveridad,
    truncado: qa.truncado === true, todosDemo, vacio,
  };
}

// ───────────────────────── jardín ─────────────────────────

export function estadoJardin(cerebro) {
  const j = esObjeto(cerebro) && esObjeto(cerebro.jardin) ? cerebro.jardin : {};
  const n = entero(j.propuestas) ?? 0;
  if (n > 0) return { propuestas: n, tono: 'acento', titulo: `${n} ${n === 1 ? 'propuesta espera' : 'propuestas esperan'} tu clic`, ultima: typeof j.ultima === 'string' ? j.ultima : null, ruta: cad(j.ruta) };
  return { propuestas: 0, tono: 'neutro', titulo: 'Sin datos: el jardinero todavía no corre', ultima: null, ruta: cad(j.ruta) || 'empresa/memoria/jardin' };
}

export const JARDIN_PASOS = Object.freeze([
  'Cada domingo revisa la memoria y propone: unir lo repetido, archivar lo vencido.',
  'Funciona como simulacro: te muestra qué cambiaría (el antes y el después) y no toca nada.',
  'Tú haces clic en lo que apruebas. Lo que archiva queda guardado con su huella: nada se borra.',
  'Nunca toca reglas, líneas rojas ni nada que cite un bloqueo de cumplimiento.',
]);

// ───────────────────────── detalle técnico: rutas y hashes ─────────────────────────

/** Filas `{etiqueta, ruta, existe, bytes, sha256}` de todo lo que lee esta pantalla. */
export function rutasTecnicas(cerebro, rutaPulido = 'empresa/panel/pulido.jsonl') {
  const filas = [{ etiqueta: 'Lista única de pendientes', ruta: rutaPulido, existe: null, bytes: null, sha256: null }];
  if (!esObjeto(cerebro)) return filas;
  const m = esObjeto(cerebro.memoria) ? cerebro.memoria : {};
  for (const f of lista(m.archivos).filter(esObjeto)) filas.push({ etiqueta: cad(f.titulo) || cad(f.clave), ruta: cad(f.ruta), existe: f.existe === true, bytes: entero(f.bytes), sha256: typeof f.sha256 === 'string' ? f.sha256 : null });
  const d = esObjeto(cerebro.decisiones) ? cerebro.decisiones : {};
  for (const f of lista(d.fuentes).filter(esObjeto)) filas.push({ etiqueta: cad(f.titulo), ruta: cad(f.ruta), existe: f.existe === true, bytes: entero(f.bytes), sha256: typeof f.sha256 === 'string' ? f.sha256 : null });
  const r = esObjeto(cerebro.reglas) ? cerebro.reglas : {};
  for (const k of ['parametros', 'limites', 'autonomia']) {
    const f = esObjeto(r[k]) ? r[k] : null;
    if (f) filas.push({ etiqueta: { parametros: 'Valores ajustables', limites: 'Tus límites', autonomia: 'Niveles de autonomía' }[k], ruta: cad(f.ruta), existe: f.existe === true, bytes: null, sha256: typeof f.sha256 === 'string' ? f.sha256 : null });
  }
  const j = esObjeto(cerebro.jardin) ? cerebro.jardin : {};
  filas.push({ etiqueta: 'Propuestas del jardinero', ruta: cad(j.ruta) || 'empresa/memoria/jardin', existe: j.existe === true, bytes: null, sha256: null });
  return filas.filter((f) => f.ruta);
}

/** Firma barata de lo que importa para repintar (el sondeo solo repinta si cambió). */
export function firmaDatos(pulido, cerebro) {
  return JSON.stringify([
    P.listaCruda(pulido).map((l) => [l && l.id, l && l.ts, l && l.estado]),
    esObjeto(cerebro) ? [cerebro.memoria && lista(cerebro.memoria.archivos).map((f) => [f.lineas, f.sha256]),
      cerebro.decisiones && lista(cerebro.decisiones.fuentes).map((f) => f.sha256), cerebro.lecciones && [lista(cerebro.lecciones.qa && cerebro.lecciones.qa.hallazgos).length, lista(cerebro.lecciones.postmortems).length],
      cerebro.jardin && cerebro.jardin.propuestas] : null,
  ]);
}
