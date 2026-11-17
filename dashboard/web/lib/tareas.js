// lib/tareas.js — lógica pura de #/tareas («Mis tareas»): la tanda completa del negocio en 6 momentos, con el estado REAL de cada tarea.
// Sin imports, sin DOM y sin red: se prueba con `node --test` (tests/dashboard/test_web_tareas.mjs).
//
// Cómo funciona (reglas de oro de esta pantalla):
//  · Cada tarea declara CÓMO se sabe su estado (`comprobar(c)`: una función pura sobre lo que ya entregan las lecturas del panel: parámetros y límites,
//    sistema, ofertas, oferta elegida, pulido, puntos de control, robots, cumplimiento y cerebro). Si el dato no existe, la tarea queda «No se puede
//    comprobar sola» y se ofrece una MARCA PERSONAL (guardada solo en el navegador; no cambia el sistema).
//  · Una tarea NUNCA sale «Hecha» sin evidencia (una lectura que lo demuestra) o sin esa marca. Lo que todavía no se construyó sale «Todavía no existe»
//    (tabla CONSTRUCCION, comprobada contra el repositorio el 2026-11-06 y mejorada con datos cuando aparecen: p. ej. el registro de robots).
//  · Lo que se muestra es HOY o es OBJETIVO, nunca mezclado (`hoyObjetivo`).
//  · Todo texto que viene de archivos es dato no confiable: aquí solo se recorta y se devuelve como texto; la pantalla lo pinta con textContent.
//
// Lecturas (`lecturas`): { sistema, parametros, ofertas, pulido, gates, robots, cumplimiento, cerebro, acciones } y cada una es
// { ok: boolean, vacio?: boolean, datos: any }. `ok:false` = no se pudo leer; `vacio:true` = la fuente aún no existe.

export const FECHA_PLAN = '2026-11-06';

// ───────────────────────── vocabulario ─────────────────────────

export const MOMENTOS = [
  { id: 0, clave: 'arrancar', titulo: 'Dejar todo listo para arrancar', corto: 'Arrancar', icono: 'bandera', resumen: 'Decisiones y firmas que solo puedes dar tú, antes de gastar un peso.' },
  { id: 1, clave: 'preparar', titulo: 'Preparar la primera oferta', corto: 'Preparar la oferta', icono: 'caja', resumen: 'Del tema elegido a la oferta, el producto, la página de ventas y los anuncios, con la revisión de cumplimiento.' },
  { id: 2, clave: 'lanzar', titulo: 'Lanzar', corto: 'Lanzar', icono: 'play', resumen: 'Lo que tiene que estar en verde antes de prender la primera campaña, y cómo se decide al primer día.' },
  { id: 3, clave: 'dia', titulo: 'Cada día', corto: 'Cada día', icono: 'sol', resumen: 'Lo que el sistema hace solo todos los días y lo que te llega a ti.' },
  { id: 4, clave: 'semana', titulo: 'Cada semana', corto: 'Cada semana', icono: 'reloj', resumen: 'La semana tipo: un foco distinto cada día, de lunes a domingo.' },
  { id: 5, clave: 'crecer', titulo: 'Crecer', corto: 'Crecer', icono: 'tendencia-sube', resumen: 'Cuando una oferta vende: llevarla a otros idiomas y vender más por cada cliente.' },
];

export const QUIENES = {
  dueno: { texto: 'Tú', icono: 'usuario', frase: 'Te toca a ti' },
  sistema: { texto: 'El sistema', icono: 'engranaje', frase: 'Lo hace el sistema solo' },
  ia: { texto: 'Una IA', icono: 'chispa', frase: 'La prepara una IA' },
};
export const CLAVES_QUIEN = ['dueno', 'sistema', 'ia'];

export const ESTADOS = {
  hecha: { texto: 'Hecha', tono: 'ok', icono: 'check', frase: 'Ya está' },
  pendiente: { texto: 'Pendiente', tono: 'neutro', icono: 'circulo-punteado', frase: 'Falta hacerla' },
  en_curso: { texto: 'En curso', tono: 'info', icono: 'progreso', frase: 'Se está haciendo' },
  espera_firma: { texto: 'Espera tu firma', tono: 'acento', icono: 'firma', frase: 'Necesita tu aprobación' },
  bloqueada: { texto: 'Bloqueada por otra tarea', tono: 'aviso', icono: 'candado', frase: 'Primero hay que terminar otra' },
  no_existe: { texto: 'Todavía no existe', tono: 'neutro', icono: 'reloj', frase: 'Falta construirla' },
  no_comprobable: { texto: 'No se puede comprobar sola', tono: 'neutro', icono: 'ayuda', frase: 'El panel no puede saber si está hecha' },
};
export const CLAVES_ESTADO = Object.keys(ESTADOS);
/** Los estados en los que algo se puede hacer (o falta hacerlo): «para hacer». */
export const ESTADOS_PARA_HACER = ['pendiente', 'en_curso', 'espera_firma', 'bloqueada', 'no_comprobable'];

export const CLAVE_MARCAS = 'fab.tareas.marcas';
export const CLAVE_VISTA = 'fab.tareas.vista';
export const VISTAS = ['lista', 'mapa'];
export const FILTROS_VACIOS = { quien: 'todas', estado: 'todos', texto: '' };

// Objetivo J4 (decisiones-del-dueno.md): frenos de toda la empresa, en USD (unidad menor = centavos).
export const FRENOS_OBJETIVO = { gastoDiarioUsd: 300, perdidaMaxUsd: 3000 };
export const VIGENCIA_CHEQUEO_H = 6;

const RE_OFERTA = /^OF-\d{6}-\d{2}$/;
const RE_CARPETA = /^(OF-\d{6}-\d{2}|_ejemplo)$/;
const RE_ETAPA = /^[A-Z][A-Z0-9]{0,3}$/;
const RE_HUELLA = /^sha256:[0-9a-f]{64}$/;

export const ofertaIdValido = (id) => typeof id === 'string' && RE_OFERTA.test(id);
export const carpetaValida = (id) => typeof id === 'string' && RE_CARPETA.test(id);
export const etapaValida = (e) => typeof e === 'string' && RE_ETAPA.test(e);

/** Comando real para firmar una etapa (el panel nunca firma). Devuelve null si el id o la etapa no tienen la forma esperada. */
export function comandoFirmarEtapa(ofertaId, etapa, huella) {
  if (!ofertaIdValido(ofertaId) || !etapaValida(etapa)) return null;
  const h = typeof huella === 'string' && RE_HUELLA.test(huella) ? huella : '<HUELLA_DE_LO_QUE_FIRMAS>';
  return `.venv/bin/python -m engine.orq firmar --oferta ${ofertaId} --etapa ${etapa} --hash-objetivo ${h} --clave-privada <RUTA_A_TU_CLAVE> --como dueno`;
}

// ───────────────────────── utilidades ─────────────────────────

const esObj = (x) => x !== null && typeof x === 'object' && !Array.isArray(x);
const lista = (x) => (Array.isArray(x) ? x : []);
const corto = (s, n = 160) => { const t = typeof s === 'string' ? s.replace(/[\u0000-\u001F\u007F]+/g, ' ').trim() : ''; return t.length > n ? `${t.slice(0, n - 1)}…` : t; };
const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
const quitarTildes = (s) => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
const alMs = (v) => { if (typeof v === 'number' && Number.isFinite(v)) return v; if (typeof v === 'string') { const t = Date.parse(v); return Number.isFinite(t) ? t : null; } return null; };

/** Formato de respaldo (la pantalla pasa el de ui.js). */
export const FMT_BASICO = {
  dinero(monto, moneda) {
    if (!Number.isInteger(monto)) return '—';
    const ent = Math.trunc(Math.abs(monto) / 100).toString().replace(/\B(?=(\d{3})+(?!\d))/g, '.');
    const cen = String(Math.abs(monto) % 100).padStart(2, '0');
    return `${monto < 0 ? '-' : ''}${ent}${cen === '00' ? '' : `,${cen}`} ${typeof moneda === 'string' ? moneda : ''}`.trim();
  },
  relativo(iso, ahora = Date.now()) {
    const t = alMs(iso);
    if (t === null) return '—';
    const s = Math.round((ahora - t) / 1000); const a = Math.abs(s); const pre = s >= 0 ? 'hace ' : 'en ';
    if (a < 60) return 'ahora';
    if (a < 3600) return `${pre}${Math.floor(a / 60)} min`;
    if (a < 86400) return `${pre}${Math.floor(a / 3600)} h`;
    return `${pre}${Math.floor(a / 86400)} d`;
  },
};

const lec = (c, nombre) => (c.lec && c.lec[nombre]) || null;
const datosDe = (l) => (l && l.ok && !l.vacio && l.datos !== undefined && l.datos !== null ? l.datos : null);
const NOMBRE_LECTURA = {
  sistema: 'el estado del sistema', parametros: 'los límites y parámetros', ofertas: 'la lista de ofertas', pulido: 'la lista de pendientes', gates: 'la tabla de puntos de control',
  robots: 'el registro de robots', cumplimiento: 'las revisiones de cumplimiento', cerebro: 'la memoria del sistema', oferta: 'la oferta elegida',
};
const sinLectura = (nombre) => ({ clave: 'no_comprobable', evidencia: `No se pudo leer ${NOMBRE_LECTURA[nombre] || nombre} ahora, así que no se sabe si está hecha.`, origen: 'sin_datos' });

function limitesValores(c) {
  const p = datosDe(lec(c, 'parametros'));
  return p && esObj(p.limites) && esObj(p.limites.valores) ? p.limites.valores : null;
}

// ───────────────────────── marcas personales ─────────────────────────

function claveDia(d) { return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`; }
function claveSemana(d) {
  const t = new Date(Date.UTC(d.getFullYear(), d.getMonth(), d.getDate()));
  const dia = t.getUTCDay() || 7;
  t.setUTCDate(t.getUTCDate() + 4 - dia);
  const ini = new Date(Date.UTC(t.getUTCFullYear(), 0, 1));
  return `${t.getUTCFullYear()}-S${Math.ceil(((t.getTime() - ini.getTime()) / 86400000 + 1) / 7)}`;
}

/** ¿Sigue valiendo una marca? `unica` siempre; `dia` el mismo día; `semana` la misma semana (hora local). */
export function marcaVigente(iso, periodo = 'unica', ahora = Date.now()) {
  const t = alMs(iso);
  if (t === null) return false;
  if (periodo === 'dia') return claveDia(new Date(t)) === claveDia(new Date(ahora));
  if (periodo === 'semana') return claveSemana(new Date(t)) === claveSemana(new Date(ahora));
  return true;
}

const almacenPorDefecto = () => { try { return typeof globalThis.localStorage !== 'undefined' ? globalThis.localStorage : null; } catch (_) { return null; } };

/** Lee las marcas {idTarea: ISO}. Nunca lanza: sin almacén o con datos corruptos devuelve {}. Solo acepta ids del catálogo. */
export function leerMarcas(almacen = almacenPorDefecto()) {
  try {
    if (!almacen) return {};
    const crudo = almacen.getItem(CLAVE_MARCAS);
    if (!crudo) return {};
    const o = JSON.parse(crudo);
    if (!esObj(o)) return {};
    const salida = {};
    for (const [k, v] of Object.entries(o)) if (IDS.has(k) && typeof v === 'string' && v.length <= 40 && alMs(v) !== null) salida[k] = v;
    return salida;
  } catch (_) { return {}; }
}
function escribirMarcas(almacen, marcas) {
  try { if (!almacen) return false; almacen.setItem(CLAVE_MARCAS, JSON.stringify(marcas)); return true; } catch (_) { return false; }
}
/** Guarda la marca de una tarea (solo en este navegador). Devuelve true si quedó guardada. */
export function guardarMarca(almacen, id, iso = new Date().toISOString()) {
  if (!IDS.has(id)) return false;
  return escribirMarcas(almacen, { ...leerMarcas(almacen), [id]: iso });
}
export function quitarMarca(almacen, id) {
  const m = { ...leerMarcas(almacen) };
  delete m[id];
  return escribirMarcas(almacen, m);
}
export function leerVista(almacen = almacenPorDefecto()) {
  try { const v = almacen && almacen.getItem(CLAVE_VISTA); return VISTAS.includes(v) ? v : 'lista'; } catch (_) { return 'lista'; }
}
export function guardarVista(almacen, vista) {
  try { if (almacen && VISTAS.includes(vista)) almacen.setItem(CLAVE_VISTA, vista); } catch (_) { /* sin almacén */ }
}

// ───────────────────────── la oferta elegida ─────────────────────────

/**
 * Qué oferta mira el momento 1: la activa (si existe), si no la primera real, si no la demo (rotulada). Devuelve {id, demo, motivo} o {id: null}.
 * `ofertas` = GET /ofertas.
 */
export function elegirOferta(ofertas, activa) {
  const l = lista(ofertas).filter((o) => esObj(o) && typeof o.oferta_id === 'string' && o.oferta_id);
  if (!l.length) return { id: null, demo: false, motivo: 'no_hay' };
  const a = typeof activa === 'string' ? l.find((o) => o.oferta_id === activa) : null;
  if (a) return { id: a.oferta_id, demo: Boolean(a.demo), motivo: 'activa' };
  const real = l.find((o) => !o.demo);
  if (real) return { id: real.oferta_id, demo: false, motivo: 'primera_real' };
  return { id: l[0].oferta_id, demo: true, motivo: 'solo_demo' };
}

/** Une la elección con el detalle `GET /oferta/<id>` ({lectura} o null). */
function normalizarOferta(o) {
  if (!esObj(o) || !o.id) return { id: null, idEstado: null, demo: false, detalle: null, leida: false, hay: false };
  const det = o.lectura && o.lectura.ok && esObj(o.lectura.datos) ? o.lectura.datos : null;
  const idEstado = det && esObj(det.estado) && ofertaIdValido(det.estado.oferta_id) ? det.estado.oferta_id : (ofertaIdValido(o.id) ? o.id : null);
  return { id: o.id, idEstado, demo: Boolean(o.demo), detalle: det, leida: Boolean(det), hay: true };
}
const idComando = (c) => (c.oferta.idEstado || '<ID_DE_LA_OFERTA>');
const etapaDe = (c, id) => (c.oferta.detalle ? lista(c.oferta.detalle.etapas).find((e) => esObj(e) && e.id === id) || null : null);
const estadoOferta = (c) => (c.oferta.detalle && esObj(c.oferta.detalle.estado) ? c.oferta.detalle.estado : null);

// ───────────────────────── comprobaciones (una por tarea; devuelven {clave, evidencia, detalle?, alerta?} o null) ─────────────────────────

const ok = (evidencia, extra = {}) => ({ clave: 'hecha', evidencia, origen: 'datos', ...extra });
const nok = (clave, evidencia, extra = {}) => ({ clave, evidencia, origen: 'datos', ...extra });
const juntar = (xs, n = 4) => { const a = lista(xs).filter((x) => typeof x === 'string' && x).map((x) => corto(x, 20)); return a.length > n ? `${a.slice(0, n).join(', ')} y ${a.length - n} más` : a.join(', '); };

function chkIdioma(c) {
  const v = limitesValores(c);
  if (!v) return sinLectura('parametros');
  const paises = lista(v.paises_permitidos).filter((x) => typeof x === 'string' && x);
  const locales = lista(v.locales_permitidos).filter((x) => typeof x === 'string' && x);
  if (paises.length && locales.length) return ok(`Los límites ya permiten el idioma ${juntar(locales)} en ${juntar(paises)}.`);
  if (paises.length || locales.length) return nok('en_curso', paises.length ? `Los límites ya tienen países (${juntar(paises)}) pero falta el idioma.` : `Los límites ya tienen idioma (${juntar(locales)}) pero faltan los países.`, { detalle: 'Hay que completar la otra mitad y firmar los límites.' });
  return nok('pendiente', 'Los límites todavía no permiten ningún idioma ni país: mientras tanto el sistema no puede lanzar en ninguno.');
}

function chkFrenos(c) {
  const v = limitesValores(c);
  if (!v) return sinLectura('parametros');
  const fijo = (x) => Number.isInteger(x) && x > 0;
  const g = v.gasto_diario_global; const p = v.perdida_neta_acumulada_max;
  const sello = Boolean(v.sello) && (esObj(v.sello) || typeof v.sello === 'string');
  const moneda = typeof v.moneda_limites === 'string' ? v.moneda_limites : null;
  const f = c.fmt || FMT_BASICO;
  const m = (x) => (moneda ? f.dinero(x, moneda) : String(x));
  if (!fijo(g) && !fijo(p)) return nok('pendiente', 'Los dos frenos siguen sin fijar: mientras tanto el sistema no gasta ni prende nada.');
  if (!fijo(g) || !fijo(p)) return nok('en_curso', fijo(g) ? `Ya está el tope diario (${m(g)}) pero falta la pausa por pérdida.` : `Ya está la pausa por pérdida (${m(p)}) pero falta el tope diario.`, { detalle: 'Faltan fijar los dos topes antes de firmar.' });
  if (!sello) return nok('espera_firma', `Los dos frenos están cargados (${m(g)} por día; pausa a ${m(p)} de pérdida) pero los límites todavía no tienen tu firma.`);
  const extra = {};
  if (moneda === 'USD' && (g !== FRENOS_OBJETIVO.gastoDiarioUsd * 100 || p !== FRENOS_OBJETIVO.perdidaMaxUsd * 100)) {
    extra.alerta = 'Los números firmados no coinciden con lo que decidiste (300 USD por día y pausa a 3.000 USD de pérdida): revísalos.';
  } else if (moneda && moneda !== 'USD') {
    extra.detalle = `Los límites están en ${moneda}: comprueba a mano que equivalgan a 300 USD por día y 3.000 USD de pérdida.`;
  }
  return ok(`Firmados: máximo ${m(g)} por día y pausa automática a ${m(p)} de pérdida acumulada.`, extra);
}

function infraDe(c) {
  const s = datosDe(lec(c, 'sistema'));
  if (!s) return { error: sinLectura('sistema') };
  const infra = esObj(s.infra) ? s.infra : null;
  if (!infra) return { sinMedicion: true };
  const sem = String(infra.semaforo || '').toUpperCase();
  const gen = alMs(infra.generado_en);
  const hasta = alMs(infra.valido_hasta);
  const edadH = gen === null ? null : (c.ahora - gen) / 3600000;
  const vigente = hasta !== null ? hasta > c.ahora : (edadH !== null && edadH < VIGENCIA_CHEQUEO_H);
  const rojos = lista(infra.items).filter((i) => esObj(i) && String(i.estado || '').toUpperCase() === 'ROJO').length;
  return { sem, vivo: infra.modo === 'vivo', modo: typeof infra.modo === 'string' ? infra.modo : null, vigente, rojos, cuando: infra.generado_en || null };
}

function chkChequeo(c, { exigirVigente }) {
  const i = infraDe(c);
  if (i.error) return i.error;
  const f = c.fmt || FMT_BASICO;
  if (i.sinMedicion) return nok('pendiente', 'Todavía no hay ninguna medición del chequeo antes de lanzar.');
  const cuando = i.cuando ? f.relativo(i.cuando, c.ahora) : null;
  const razones = [];
  if (i.sem !== 'VERDE') razones.push(i.sem === 'ROJO' ? `está en rojo${i.rojos ? ` (${plural(i.rojos, 'punto', 'puntos')} en rojo)` : ''}` : `está en ${i.sem === 'AMARILLO' ? 'amarillo' : 'un estado sin semáforo claro'}`);
  if (!i.vivo) razones.push(`se hizo en modo ${i.modo === 'simulado' ? 'simulacro' : (i.modo || 'desconocido')}, que no cuenta para lanzar`);
  if (razones.length) return nok('en_curso', `El último chequeo${cuando ? ` (${cuando})` : ''} ${razones.join(' y ')}.`, { detalle: 'Arregla lo que esté en rojo y vuelve a correrlo hasta que quede en verde y en modo vivo.' });
  if (exigirVigente && !i.vigente) return nok('pendiente', `El último chequeo salió en verde${cuando ? ` (${cuando})` : ''} pero ya venció: vale ${VIGENCIA_CHEQUEO_H} horas.`, { detalle: 'Hay que repetirlo justo antes de lanzar.' });
  return ok(`En verde y en modo vivo${cuando ? `, medido ${cuando}` : ''}.`, !exigirVigente && !i.vigente ? { detalle: `Venció (vale ${VIGENCIA_CHEQUEO_H} horas): antes de lanzar hay que repetirlo.` } : {});
}

function chkIva(c) {
  if (!c.oferta.hay || c.oferta.demo || !c.oferta.detalle) return null;
  const m = esObj(c.oferta.detalle.mercado) ? c.oferta.detalle.mercado : null;
  const fiscal = m && esObj(m.fiscal) ? m.fiscal : null;
  const reg = fiscal && typeof fiscal.regimen === 'string' ? fiscal.regimen : null;
  if (!reg) return null;
  if (reg === 'diferido') return nok('pendiente', 'El régimen de IVA está pospuesto en el mercado de la oferta: hace falta definirlo antes de cobrar en vivo.', { detalle: 'Se pospuso con tu firma, solo para los países de la prueba.' });
  return ok(`El mercado de la oferta declara el régimen «${corto(reg, 40)}».`);
}

function chkNativo(c) {
  const v = limitesValores(c);
  if (!v) return sinLectura('parametros');
  const locales = lista(v.locales_permitidos).filter((x) => typeof x === 'string' && x);
  if (!locales.length) return null; // todavía no hay idioma: queda bloqueada por «Elegir el primer idioma»
  const necesitan = locales.filter((l) => /^(pl|fr)(-|_|$)/i.test(l));
  if (!necesitan.length) return ok(`No hace falta: el idioma elegido (${juntar(locales)}) no es polaco ni francés.`);
  return { clave: 'no_comprobable', evidencia: `El idioma elegido (${juntar(necesitan)}) necesita revisión nativa y el panel no puede saber si ya tienes a la persona.`, origen: 'sin_datos' };
}

function chkFrenoCaptura(c) {
  const s = datosDe(lec(c, 'sistema'));
  if (!s) return sinLectura('sistema');
  const f = c.fmt || FMT_BASICO;
  const fr = esObj(s.freno_captura) ? s.freno_captura : null;
  if (!fr || fr.activo !== true) return ok('El freno de la captura de anuncios no está puesto.');
  return nok('pendiente', `El freno está puesto${fr.ts ? ` desde ${f.relativo(fr.ts, c.ahora)}` : ''}${fr.motivo ? `: Meta respondió «${corto(fr.motivo, 60)}»` : ''}.`, { detalle: 'Hay que decidir si se deja puesto (lo recomendado) o se levanta. Solo lo levantas tú.' });
}

function chkPausa(c) {
  const s = datosDe(lec(c, 'sistema'));
  if (s && esObj(s.pausa) && s.pausa.activa === true) {
    return { clave: 'no_comprobable', evidencia: 'La PAUSA está puesta ahora mismo, pero el panel no puede saber si ya probaste que funciona.', alerta: 'La PAUSA está puesta: el sistema no gasta ni activa nada hasta que alguien la levante.', origen: 'sin_datos' };
  }
  return null;
}

// ── oferta: una comprobación por etapa ──

function chkEtapa(idEtapa, { nombre }) {
  return (c) => {
    if (!c.oferta.hay) return nok('pendiente', 'Todavía no hay ninguna oferta: esta tarea empieza cuando exista una.');
    if (!c.oferta.leida) return sinLectura('oferta');
    const e = etapaDe(c, idEtapa);
    if (!e || typeof e.estado !== 'string') return nok('pendiente', 'La oferta todavía no tiene su estado creado con el sistema.');
    const gate = typeof e.gate === 'string' ? e.gate : null;
    if (e.gate_pendiente === true) return nok('espera_firma', `${nombre} ya está preparada y espera tu firma${gate ? ` (punto de control ${gate})` : ''}.`);
    if (e.estado === 'aprobado') {
      if (e.obsoleta === true) return nok('en_curso', `${nombre} estaba aprobada pero quedó vieja: cambió algo anterior.`, { alerta: 'Hay que rehacerla porque cambió algo de lo que depende.' });
      return ok(`${nombre} está aprobada${e.version ? ` (versión ${corto(e.version, 12)})` : ''}.`);
    }
    if (e.estado === 'en_progreso') return nok('en_curso', `${nombre} se está preparando.`);
    if (e.estado === 'en_QA') return nok('en_curso', `${nombre} está en revisión de calidad: un revisor independiente la mira.`);
    if (e.estado === 'bloqueado' || e.estado === 'escalado') {
      const b = e.bloqueo;
      const motivo = typeof b === 'string' ? b : (esObj(b) ? (b.motivo || b.mensaje || b.razon || b.tipo || '') : '');
      return nok('en_curso', `${nombre} se frenó y pide revisión${motivo ? `: ${corto(motivo, 120)}` : ''}.`, { alerta: e.estado === 'escalado' ? 'Se escaló a una persona: pide tu revisión.' : 'Se frenó por un bloqueo: hace falta revisarlo.' });
    }
    return nok('pendiente', `${nombre} todavía no empezó.`);
  };
}

function normSello(s) {
  if (!esObj(s) || s.legible === false) return null;
  return s;
}
function finDeVigencia(v) {
  if (typeof v !== 'string') return null;
  return alMs(/^\d{4}-\d{2}-\d{2}$/.test(v) ? `${v}T23:59:59Z` : v);
}
/** Sellos (vistos buenos firmados) de la oferta elegida para unas etapas: {etapa: {vigente, vencido, alterado, hasta}} o null si no se leyó. */
function sellosDe(c, etapas) {
  const cum = datosDe(lec(c, 'cumplimiento'));
  if (!cum && !(lec(c, 'cumplimiento') && lec(c, 'cumplimiento').ok)) return null;
  const todos = cum ? lista(cum.sellos).map(normSello).filter(Boolean) : [];
  const suyos = todos.filter((s) => s.oferta_id === c.oferta.id || (c.oferta.idEstado && (s.oferta_id === c.oferta.idEstado || s.oferta_id_interno === c.oferta.idEstado)));
  const salida = {};
  for (const e of etapas) {
    const delaEtapa = suyos.filter((s) => s.etapa_objetivo === e);
    let mejor = null;
    for (const s of delaEtapa) {
      const hasta = finDeVigencia(s.vigencia_hasta);
      const alterado = s.alterado === true;
      const vigente = !alterado && (hasta !== null ? hasta >= c.ahora : s.vigente === true);
      const item = { vigente, alterado, vencido: !alterado && !vigente, hasta: s.vigencia_hasta || null };
      if (!mejor || (item.vigente && !mejor.vigente)) mejor = item;
    }
    salida[e] = mejor;
  }
  return salida;
}

function chkCumplimientoPagAnuncios(c) {
  if (!c.oferta.hay) return nok('pendiente', 'Todavía no hay ninguna oferta.');
  const s = sellosDe(c, ['D5', 'D6']);
  if (!s) return sinLectura('cumplimiento');
  const f = c.fmt || FMT_BASICO;
  const nombres = { D5: 'la página de ventas', D6: 'los anuncios' };
  const bien = ['D5', 'D6'].filter((e) => s[e] && s[e].vigente);
  if (bien.length === 2) return ok('La página de ventas y los anuncios tienen su visto bueno de cumplimiento firmado y vigente.');
  const problemas = ['D5', 'D6'].filter((e) => !bien.includes(e)).map((e) => (s[e] ? (s[e].alterado ? `el de ${nombres[e]} está alterado` : `el de ${nombres[e]} venció`) : `falta el de ${nombres[e]}`));
  const alt = ['D5', 'D6'].some((e) => s[e] && s[e].alterado);
  return nok(bien.length ? 'en_curso' : 'pendiente', `${bien.length ? `Hay visto bueno de ${nombres[bien[0]]}, pero ` : 'Todavía no hay vistos buenos firmados: '}${problemas.join(' y ')}.`, alt ? { alerta: 'Un visto bueno quedó alterado: lo revisado cambió después de firmarse.' } : {});
}

function chkCumplimientoCampana(c) {
  if (!c.oferta.hay) return nok('pendiente', 'Todavía no hay ninguna oferta.');
  const s = sellosDe(c, ['D7']);
  if (!s) return sinLectura('cumplimiento');
  const x = s.D7;
  if (!x) return nok('pendiente', 'Todavía no hay visto bueno de cumplimiento firmado para la campaña.');
  if (x.alterado) return nok('en_curso', 'El visto bueno de la campaña está alterado: lo revisado cambió después de firmarse.', { alerta: 'Hay que pedir una revisión nueva.' });
  if (!x.vigente) return nok('pendiente', `El visto bueno de la campaña venció${x.hasta ? ` (${corto(x.hasta, 30)})` : ''}: hay que renovarlo con una revisión nueva.`);
  return ok(`La campaña tiene su visto bueno de cumplimiento firmado y vigente${x.hasta ? ` hasta ${corto(x.hasta, 30)}` : ''}.`);
}

const FASES_CAMPANA_ACTIVADA = ['en_test', 'escalando', 'validada', 'inconclusa', 'fallida'];
function chkActivar(c) {
  if (!c.oferta.hay) return nok('pendiente', 'Todavía no hay ninguna oferta.');
  if (!c.oferta.leida) return sinLectura('oferta');
  const est = estadoOferta(c);
  const fase = est && typeof est.fase === 'string' ? est.fase : null;
  if (fase && FASES_CAMPANA_ACTIVADA.includes(fase)) return ok(`La campaña ya se prendió: la oferta está en la fase «${corto(fase.replace(/_/g, ' '), 30)}».`);
  const d7 = etapaDe(c, 'D7');
  if ((d7 && d7.gate_pendiente === true) || fase === 'listo_para_activar') return nok('espera_firma', 'La campaña está armada y espera tu firma para prenderse.');
  return nok('pendiente', 'La campaña todavía no está lista para prenderse.');
}

// ── robots y sistema ──

const ESTADO_ROBOT = { vivo: 'vivo', live: 'vivo', activo: 'vivo', encendido: 'vivo', en_vivo: 'vivo', sombra: 'sombra', shadow: 'sombra', apagado: 'apagado', off: 'apagado', inactivo: 'apagado' };
/** Registro de robots tolerante: [{id, nombre, estado, ultimoLatido}] · [] si la fuente no existe o está vacía · null si no se pudo leer. */
export function registroRobots(l) {
  if (!l || !l.ok) return null;
  if (l.vacio || !l.datos) return [];
  let crudo = l.datos;
  if (esObj(crudo) && 'robots' in crudo) crudo = crudo.robots;
  let items = [];
  if (Array.isArray(crudo)) items = crudo.map((r, i) => (esObj(r) ? r : { id: String(i) }));
  else if (esObj(crudo)) items = Object.entries(crudo).filter(([, r]) => esObj(r)).map(([k, r]) => ({ id: k, ...r }));
  return items.map((r) => {
    const id = [r.id, r.robot_id, r.robot, r.clave, r.nombre].find((x) => typeof x === 'string' && x) || '';
    const crudoEstado = typeof (r.estado ?? r.modo) === 'string' ? String(r.estado ?? r.modo).toLowerCase() : '';
    const lat = r.ultimo_latido ?? r.ultimo_latido_en ?? r.latido_ts ?? (esObj(r.latido) ? (r.latido.ts ?? r.latido.ultimo) : null);
    return { id: corto(id, 60), nombre: typeof r.nombre === 'string' ? corto(r.nombre, 60) : null, estado: ESTADO_ROBOT[crudoEstado] || null, ultimoLatido: typeof lat === 'string' ? lat : null };
  }).filter((r) => r.id);
}
const plano = (s) => quitarTildes(s).replace(/[^a-z0-9]+/g, '');

function chkRobot(claves, { frase }) {
  return (c) => {
    const reg = registroRobots(lec(c, 'robots'));
    if (reg === null) return sinLectura('robots');
    if (!reg.length) return null;
    const r = reg.find((x) => claves.some((k) => plano(`${x.id} ${x.nombre || ''}`).includes(k)));
    if (!r) return null;
    const f = c.fmt || FMT_BASICO;
    const lat = r.ultimoLatido ? ` Última señal de vida ${f.relativo(r.ultimoLatido, c.ahora)}.` : ' Todavía sin señal de vida.';
    if (r.estado === 'vivo') return ok(`${frase} está en marcha.${lat}`);
    if (r.estado === 'sombra') return nok('en_curso', `${frase} está en «sombra»: mira y anota, pero todavía no actúa.${lat}`);
    if (r.estado === 'apagado') return nok('pendiente', `${frase} está registrado pero apagado.`);
    return { clave: 'no_comprobable', evidencia: `${frase} figura en el registro de robots, pero sin estado claro.`, origen: 'sin_datos' };
  };
}

function chkAtencion(c) {
  const of = datosDe(lec(c, 'ofertas'));
  const pul = datosDe(lec(c, 'pulido'));
  if (!of && !pul) return null;
  const firmas = of ? lista(of).filter((o) => esObj(o) && !o.demo).reduce((n, o) => n + lista(o.gates_pendientes).length, 0) : 0;
  const entradas = pul ? entradasPulido(pul) : [];
  const mios = entradas.filter((e) => e.estado !== 'resuelta' && e.responsable === 'dueno').length;
  if (!firmas && !mios) return null;
  const partes = [];
  if (firmas) partes.push(`${plural(firmas, 'paso espera', 'pasos esperan')} tu firma`);
  if (mios) partes.push(`${plural(mios, 'pendiente tuyo está abierto', 'pendientes tuyos están abiertos')} en la lista única`);
  return nok('pendiente', `Ahora mismo: ${partes.join(' y ')}.`);
}

/** Entradas de la lista única, con lo mínimo que usa esta pantalla. Tolera array / {entradas} y líneas de cambio de estado. */
export function entradasPulido(datos) {
  let crudas = [];
  if (Array.isArray(datos)) crudas = datos;
  else if (esObj(datos)) for (const k of ['entradas', 'items', 'lineas', 'bitacora']) if (Array.isArray(datos[k])) { crudas = datos[k]; break; }
  const mapa = new Map();
  for (const l of crudas) {
    if (!esObj(l) || l.id === undefined || l.id === null) continue;
    const id = String(l.id);
    const previa = mapa.get(id);
    const cambio = l.evento === 'estado' || (l.titulo == null && l.estado != null);
    if (previa && cambio) { if (['abierta', 'en_curso', 'resuelta'].includes(l.estado)) previa.estado = l.estado; continue; }
    if (!previa && cambio) continue;
    mapa.set(id, { id, tipo: typeof l.tipo === 'string' ? l.tipo : 'observacion', estado: ['abierta', 'en_curso', 'resuelta'].includes(l.estado) ? l.estado : 'abierta', responsable: typeof l.responsable === 'string' ? l.responsable : null, titulo: corto(l.titulo, 120) });
  }
  return [...mapa.values()];
}

function chkReglas(c) {
  const l = lec(c, 'pulido');
  if (!l || !l.ok) return sinLectura('pulido');
  const abiertas = entradasPulido(l.datos).filter((e) => e.tipo === 'regla_propuesta' && e.estado !== 'resuelta');
  if (!abiertas.length) return null;
  return nok('pendiente', `${plural(abiertas.length, 'regla propuesta espera', 'reglas propuestas esperan')} tu aprobación en la lista única.`);
}

function chkJurado(c) {
  const e = etapaDe(c, 'D6');
  const arts = e ? lista(e.artefactos) : [];
  const j = arts.find((a) => esObj(a) && typeof a.ruta === 'string' && /(^|\/)jurado\.json$/.test(a.ruta));
  if (!j || c.oferta.demo) return null;
  return nok('en_curso', 'La oferta ya tiene un resultado de jurado, pero todavía no corre solo cada día.');
}

function chkJardin(c) {
  const l = lec(c, 'cerebro');
  if (!l || !l.ok) return null;
  const j = esObj(l.datos) && esObj(l.datos.jardin) ? l.datos.jardin : null;
  if (!j || j.existe !== true) return null;
  const n = Number.isInteger(j.propuestas) ? j.propuestas : 0;
  return nok('en_curso', `El ordenador de la memoria existe${n ? ` y tiene ${plural(n, 'propuesta', 'propuestas')} esperando tu clic` : ''}.`);
}

function chkNicho4(c) {
  const v = limitesValores(c);
  if (!v) return sinLectura('parametros');
  const macros = lista(v.macro_nichos_permitidos).filter((x) => typeof x === 'string');
  if (macros.some((m) => /habilidad|hobb/i.test(m))) return ok('Los límites ya admiten el cuarto nicho (habilidades y hobbies).');
  return null;
}

// ───────────────────────── lo que todavía no existe (comprobado contra el repositorio el 2026-11-06) ─────────────────────────
// Cuando algo se construya, se cambia aquí (o, mejor, se agrega una comprobación con datos en la tarea). `falta`: frase simple de qué falta.
// `segun`: de dónde sale (para «Detalle técnico»).

export const CONSTRUCCION = {
  'lz-baja': { falta: 'Todavía no existe: el sistema hoy decide con una regla de varios días; la regla de baja al primer día todavía no está construida.', segun: 'mapeo.md §1 y §3.1 (J3); no hay `baja_dias` en engine/ ni decision/' },
  'dia-fabrica': { falta: 'Todavía no existe el turno de noche: hoy los anuncios se producen cuando se piden, no solos de madrugada.', segun: 'mapeo.md §1 (pieza 2): falta el modo tanda programada' },
  'dia-jurado': { falta: 'Todavía no existe el jurado: nadie ordena los anuncios a ciegas antes de gastar.', segun: 'mapeo.md §1 (pieza 3); no hay `jurado.json` ni código de jurado' },
  'dia-cola': { falta: 'Todavía no existe la cola que carga y prende los lanzamientos del día; hoy cada campaña se arma y se prende a mano.', segun: 'mapeo.md §2 (00:10) y §10 Fase 3' },
  'dia-robots': { falta: 'Todavía no existen los robots que suben, bajan, apagan y frenan anuncios solos: no hay registro de robots.', segun: 'mapeo.md §1 (pieza 5); no existe empresa/robots.yaml' },
  'dia-auditor': { falta: 'Todavía no existe el auditor que juzga cada decisión de los robots con lo que pasó después.', segun: 'mapeo.md §1 (pieza 5) y §11 (riesgo 1)' },
  'dia-resumen': { falta: 'Todavía no existe el resumen diario de las 08:30: falta el programa que arma los avisos y el canal al celular.', segun: 'mapeo.md §9: el productor de alertas aún no existe' },
  'sem-lun': { falta: 'Todavía no existe el cierre semanal: falta el tablero que mide qué ángulo ganó en cada idioma.', segun: 'mapeo.md §2 (lunes) y §6' },
  'sem-mar': { falta: 'Todavía no existe la tanda semanal: falta el modo de producción por tandas de los anuncios.', segun: 'mapeo.md §2 (martes) y §6' },
  'sem-mie': { falta: 'Todavía no existe el jurado, así que no hay nada que recalibrar con lo cobrado.', segun: 'mapeo.md §2 (miércoles) y §6' },
  'sem-jue': { falta: 'Todavía no existe el tablero de lanzamiento de idioma que avanza cada jueves.', segun: 'mapeo.md §8: `lanzamiento_idioma` no existe' },
  'sem-sab': { falta: 'Todavía no existe el piloto automático: faltan los robots y el auditor que lo harían seguro.', segun: 'mapeo.md §2 (sábado) y §10 Fase 3' },
  'sem-dom': { falta: 'Todavía no existe el ordenador automático de la memoria; hoy la memoria se ordena a mano al cerrar cada sesión de trabajo.', segun: 'mapeo.md §9: jardinero del domingo en simulacro + clic (aún no existe)' },
  'cr-idiomas': { falta: 'Todavía no existe la ruta de familia: faltan el tablero de lanzamiento de idioma y la traducción automática de los ganadores.', segun: 'mapeo.md §8 (J5)' },
  'cr-carrito': { falta: 'Todavía no existe el carrito con varios productos: hoy se vende un producto con una casilla extra.', segun: 'mapeo.md §7 paso 3' },
  'cr-post': { falta: 'Todavía no existe la oferta después de pagar: está apagada hasta medir disputas.', segun: 'mapeo.md §7 paso 4' },
  'cr-abandonado': { falta: 'Todavía no existe el correo de carrito abandonado.', segun: 'mapeo.md §7 paso 5' },
  'cr-organico': { falta: 'Todavía no existe el radar de contenido orgánico (cuentas secundarias que muestran qué formatos funcionan).', segun: 'decisiones-del-dueno.md J8' },
  'cr-nicho4': { falta: 'Todavía no está habilitado: los límites admiten solo salud, relaciones y dinero, y el cumplimiento tiene que cubrir el cuarto nicho antes de gastar en él.', segun: 'decisiones-del-dueno.md J6/J9; limites.yaml fija `macro_nichos_permitidos` en 3' },
};

// ───────────────────────── el catálogo ─────────────────────────

const paso = (texto, extra = {}) => ({ texto, ...extra });
const enlace = (texto, ruta) => ({ texto, ruta });
const cmd = (comando, titulo, nota) => ({ comando, titulo, nota });
const CMD = '.venv/bin/python -m engine.orq';
const CMD_PROPUESTAS = '.venv/bin/python -m engine.propuestas';
const CMD_CHEQUEO = '.venv/bin/python -m infra.preflight ejecutar --modo completo';

function pasosEtapa({ etapa, que, pantalla, antes }) {
  return (c, est) => {
    const o = idComando(c);
    const hash = etapaDe(c, etapa) && etapaDe(c, etapa).hash;
    const l = [];
    if (!c.oferta.hay) {
      l.push(paso('Todavía no hay ninguna oferta. Créala con el recorrido guiado «lanzar una oferta»: en la pestaña Code de Claude, corre la guía de trabajo (skill) /o0-lanzar-oferta.'));
      l.push(paso('También puedes crearla con un comando, si ya escribiste el brief (la ficha de la oferta).', { comando: `${CMD} crear --brief ofertas/<id>/00-brief.yaml`, tituloComando: 'Crear la oferta desde su ficha (brief)' }));
      return l;
    }
    if (est.clave === 'espera_firma') {
      l.push(paso(`Revisa lo que preparó la IA (${que}). Si te parece bien, fírmalo.`, { enlace: pantalla }));
      const f = comandoFirmarEtapa(c.oferta.idEstado, etapa, hash);
      l.push(paso('Fírmalo desde tu terminal, con tu clave privada. El panel no firma por ti.', f ? { comando: f, tituloComando: `Firmar ${que} (solo tú)`, nota: 'Reemplaza lo que está entre < > con tus datos.' } : {}));
      return l;
    }
    if (est.clave === 'hecha') {
      l.push(paso(`Ya está: ${que} quedó aprobada. Puedes mirar el resultado cuando quieras.`, { enlace: pantalla }));
      return l;
    }
    if (est.clave === 'bloqueada') l.push(paso('Primero termina las tareas anteriores (están marcadas arriba en esta pantalla).'));
    if (antes) l.push(paso(antes));
    l.push(paso(`Mira cómo va ${que} y qué le falta.`, { enlace: pantalla }));
    l.push(paso('Pídele al sistema que la prepare. Primero haz un ensayo: no gasta, no publica y no activa nada.', { comando: `${CMD} ejecutar --oferta ${o} --etapa ${etapa} --modo dry-run`, tituloComando: `Ensayar ${que} sin efectos` }));
    l.push(paso('Cuando el ensayo salga bien, haz la corrida real. Usa IA, así que tiene un costo, y exige límites firmados, chequeo en verde y que no haya PAUSA.', { comando: `${CMD} ejecutar --oferta ${o} --etapa ${etapa} --modo live`, tituloComando: `Preparar ${que} con IA (consume costo de IA)` }));
    return l;
  };
}

const ACC_VALIDAR_OFERTA = { id: 'validar_oferta' };

export const CATALOGO = [
  // ═════════════ 0 · Dejar todo listo para arrancar ═════════════
  {
    id: 'idioma-mercado', momento: 0, titulo: 'Elegir el primer idioma y mercado', quien: 'dueno', ruta: '#/paises',
    porQue: 'La oferta, la página y los anuncios se arman para un idioma y un país, y el sistema no lo elige por ti.',
    comprobar: chkIdioma,
    terminos: [{ clave: 'idioma_base', texto: 'idioma base' }],
    pasos: () => [
      paso('Mira las 5 opciones que dejó el estudio de mercados y cuánto cubre cada una con los medios de pago.', { enlace: enlace('Ver los países', '#/paises') }),
      paso('Compara también los impuestos (IVA) y si puedes conseguir a alguien nativo que revise los textos. Polonia fue tu ejemplo, pero es una hipótesis: se decide con datos propios, no por impresión.'),
      paso('Elige un solo mercado a la vez.', { comando: '.venv/bin/python -m scripts.mercados.rank_sin_pagos', tituloComando: 'Ver el ranking de mercados (solo mira, no cambia nada)' }),
      paso('Anota tu elección: los países y los idiomas permitidos quedan escritos en los límites del negocio, y se firman junto con los frenos de gasto (la tarea siguiente).', { enlace: enlace('Ver los límites', '#/parametros') }),
    ],
    donde: [enlace('Países', '#/paises'), enlace('Límites y reglas', '#/parametros')],
    tecnico: [['Cómo se sabe', '`paises_permitidos` y `locales_permitidos` de empresa/limites.yaml (ambas listas con algo)'], ['Fuente', 'decisiones-del-dueno.md J5 y «Pendientes del dueño» 1; docs/00 §0 punto 4']],
  },
  {
    id: 'frenos', momento: 0, titulo: 'Fijar y firmar los frenos de gasto', quien: 'dueno', ruta: '#/parametros',
    porQue: 'Sin estos dos topes el sistema no gasta ni prende nada: son tu red de seguridad.',
    comprobar: chkFrenos,
    terminos: [{ clave: 'frenos_empresa', texto: 'frenos de la empresa' }, { clave: 'pausa_por_perdida', texto: 'pausa por pérdida' }],
    avisoPlan: 'Ojo: hoy el comando «proponer» NO carga estos dos topes. Solo calcula el gasto del test y la pérdida máxima por oferta (a partir de la economía de una oferta), así que los dos números los tienes que escribir tú en el archivo de propuesta antes de firmar.',
    pasos: () => [
      paso('Tu objetivo (decisión J4): máximo 300 USD de gasto por día en toda la empresa y pausa automática al llegar a 3.000 USD de pérdida acumulada.'),
      paso('Pídele al sistema una propuesta de límites. Necesita una oferta con su economía calculada y crea el archivo de propuesta.', { comando: `${CMD_PROPUESTAS} proponer --oferta <ID_DE_UNA_OFERTA>`, tituloComando: 'Calcular una propuesta de límites (no cambia tus límites reales)' }),
      paso('Abre el archivo empresa/propuestas/limites.propuesta.yaml y escribe los dos topes. Los importes van en centavos: 300 USD son 30000 y 3.000 USD son 300000. Pon también la moneda de los límites en USD. Los campos se llaman gasto_diario_global, perdida_neta_acumulada_max y moneda_limites.'),
      paso('Haz un simulacro de la firma: revisa que la propuesta esté completa y no escribe nada. Si dice que faltan otros límites, complétalos: el mensaje te dice cuáles.', { comando: `${CMD_PROPUESTAS} sellar --como dueno`, tituloComando: 'Probar la firma sin firmar de verdad (simulacro)' }),
      paso('Firma de verdad, solo tú, desde tu terminal y con tu clave privada. El panel no firma por ti.', { comando: `FABRICA_ENTORNO=produccion ${CMD_PROPUESTAS} sellar --como dueno --live --clave-privada <RUTA_A_TU_CLAVE>`, tituloComando: 'Firmar los límites (solo tú)', nota: 'Reemplaza <RUTA_A_TU_CLAVE> con la ubicación de tu clave privada.' }),
    ],
    donde: [enlace('Límites y reglas', '#/parametros'), enlace('Quién decide qué', '#/quien-decide')],
    tecnico: [['Cómo se sabe', '`gasto_diario_global` y `perdida_neta_acumulada_max` de empresa/limites.yaml, y que el archivo tenga `sello`'], ['Unidad', 'enteros en la unidad menor (centavos) de `moneda_limites`'], ['Fuente', 'decisiones-del-dueno.md J4; engine/propuestas.py (`proponer_limites` solo calcula `gasto_total_test_por_oferta` y `perdida_max_test_por_oferta`)']],
  },
  {
    id: 'avisos-celular', momento: 0, titulo: 'Elegir cómo recibir avisos en el celular', quien: 'dueno', ruta: '#/avisos',
    porQue: 'Las alertas de pago y el resumen del día te llegan por ahí; sin un canal, un problema grave puede pasar de largo.',
    sinDato: 'Todavía no hay un lugar donde se guarde tu elección, así que el panel no puede saber si ya la hiciste.',
    terminos: [{ clave: 'canal_avisos', texto: 'canal de avisos' }, { clave: 'dos_canales', texto: 'dos canales' }],
    pasos: () => [
      paso('Elige un canal principal para las alertas (por ejemplo Telegram, solo para recibir). El plan pide siempre dos canales: elige también uno de respaldo, por ejemplo el correo.'),
      paso('Anota tu elección en la lista de pendientes para que no se pierda.', { enlace: enlace('Abrir Mejoras pendientes', '#/pulido') }),
      paso('Mira cómo se van a ver los avisos y por qué canal llegaría cada uno según su gravedad.', { enlace: enlace('Ver Avisos', '#/avisos') }),
    ],
    donde: [enlace('Avisos', '#/avisos'), enlace('Mejoras pendientes', '#/pulido')],
    tecnico: [['Cómo se sabe', 'No hay archivo que lo diga: el programa que manda los avisos (`dashboard.alertas`) todavía no existe'], ['Fuente', 'decisiones-del-dueno.md «Pendientes del dueño» 3; mapeo.md §9']],
  },
  {
    id: 'correo-entrega', momento: 0, titulo: 'Elegir el correo que entrega el producto', quien: 'dueno', ruta: '#/poscompra',
    porQue: 'Sin correo de entrega el comprador no recibe lo que pagó, y sin eso no se puede hacer la primera venta.',
    sinDato: 'Todavía no hay un lugar donde se guarde tu elección, así que el panel no puede saber si ya la hiciste.',
    pasos: () => [
      paso('Elige qué servicio manda el correo con el producto (el diseño prevé Resend, Postmark o SES; hay que verificar condiciones y precios antes de decidir).'),
      paso('Elige dónde llegan los mensajes de soporte. Lo recomendado es reenviar soporte@ de tu dominio a tu buzón de siempre.'),
      paso('Después, el sistema configura el dominio para que los correos no caigan en spam.'),
      paso('Mira qué pasa después del pago y qué falta de la entrega.', { enlace: enlace('Ver Después de la venta', '#/poscompra') }),
    ],
    donde: [enlace('Después de la venta', '#/poscompra')],
    tecnico: [['Cómo se sabe', 'No hay archivo que lo diga'], ['Fuente', 'docs/00 §0 punto 6 bis; docs/07 §6 (SPF, DKIM y DMARC del dominio de envío)']],
  },
  {
    id: 'chequeo-previo', momento: 0, titulo: 'Hacer el chequeo antes de lanzar (infraestructura)', quien: 'dueno', ruta: '#/sistema',
    porQue: 'Revisa de una vez que los pagos, las páginas y la medición estén bien, antes de gastar un peso.',
    comprobar: (c) => chkChequeo(c, { exigirVigente: false }),
    terminos: [{ clave: 'preflight_infra', texto: 'chequeo antes de lanzar' }],
    pasos: () => [
      paso('Haz primero el chequeo en modo simulacro: ejercita todo con datos de prueba y no toca cuentas reales.', { comando: `${CMD_CHEQUEO} --infra-modo simulado`, tituloComando: 'Hacer el chequeo en simulacro (práctica)' }),
      paso('Para que cuente de verdad, hazlo en modo vivo, con tus cuentas reales conectadas (Meta, Stripe, Cloudflare y el resto).', { comando: `${CMD_CHEQUEO} --infra-modo vivo`, tituloComando: 'Hacer el chequeo de verdad (modo vivo)', nota: 'Exige las claves reales en tu equipo, nunca en el repositorio.' }),
      paso('Mira el resultado: cada punto en rojo dice qué arreglar.', { enlace: enlace('Ver Salud del sistema', '#/sistema') }),
      paso('Arregla lo que esté en rojo y vuelve a correrlo hasta que todo quede en verde.'),
    ],
    donde: [enlace('Salud del sistema', '#/sistema')],
    tecnico: [['Cómo se sabe', '`infra.semaforo` = VERDE y `infra.modo` = vivo en GET /api/sistema (empresa/infra/estado.json)'], ['Vigencia', `El chequeo vale ${VIGENCIA_CHEQUEO_H} horas; esta tarea acepta uno viejo, la de «Lanzar» no`]],
  },
  {
    id: 'iva-contador', momento: 0, titulo: 'Definir el régimen de IVA con el contador', quien: 'dueno', ruta: '#/paises', depende: ['idioma-mercado'],
    porQue: 'Vender a la UE o al Reino Unido desde tu empresa de EE. UU. tiene impuestos propios; sin definirlos no se puede cobrar en vivo.',
    comprobar: chkIva,
    sinDato: 'El panel no tiene un registro de lo que acordaste con el contador, así que no puede saber si ya lo definiste.',
    terminos: [{ clave: 'oss_iva', texto: 'régimen de IVA de la UE (OSS)' }],
    pasos: () => [
      paso('Pide una consulta con tu contador. Es un paso previo a cobrar en vivo en la UE o el Reino Unido.'),
      paso('Lleva estas preguntas: ¿registro de IVA de la UE para empresas de fuera (OSS) o Stripe Managed Payments (Stripe cobra y declara los impuestos por ti, con un costo extra de 3,5 %)? ¿Qué IVA lleva un ebook: 5 %, 4 % o la tasa general? ¿Qué código fiscal tienen los PDF y las plantillas descargables? ¿Hace falta un representante para la protección de datos (GDPR)?'),
      paso('Con su respuesta, anota el régimen en el mercado de la oferta. Si eliges Managed Payments, ojo: no admite los medios de pago locales (por ejemplo BLIK) y Polonia perdería cobertura.', { enlace: enlace('Ver los países', '#/paises') }),
    ],
    donde: [enlace('Países', '#/paises')],
    tecnico: [['Cómo se sabe', '`mercado.fiscal.regimen` de una oferta real; si está en «diferido» o no hay oferta real, no se puede saber'], ['Fuente', 'docs/00 §4; decisiones-del-dueno.md «Pendientes del dueño» 4']],
  },
  {
    id: 'hablante-nativo', momento: 0, titulo: 'Conseguir a una persona nativa que revise el texto (polaco o francés)', quien: 'dueno', ruta: '#/paises', depende: ['idioma-mercado'],
    porQue: 'Si el idioma es polaco o francés, sin una persona nativa que revise no se pueden firmar los textos para lanzar.',
    comprobar: chkNativo,
    sinDato: 'El panel no puede saber si ya tienes a esa persona.',
    terminos: [{ clave: 'revisor_nativo', texto: 'revisor nativo' }],
    pasos: () => [
      paso('Esta tarea solo hace falta si elegiste polaco o francés. Si elegiste otro idioma, no tienes que hacer nada.'),
      paso('Busca a una persona nativa que revise la página y los anuncios. Se le paga por hora.'),
      paso('Hace falta en el primer lanzamiento de cada idioma. Hoy la revisión por muestreo es opcional, pero según tus pendientes sin esa persona los textos de esos idiomas no se pueden firmar.'),
    ],
    donde: [enlace('Países', '#/paises'), enlace('Cumplimiento', '#/cumplimiento')],
    tecnico: [['Cómo se sabe', 'Mira `locales_permitidos` de limites.yaml: si ninguno empieza con pl o fr, no hace falta'], ['Fuente', 'decisiones-del-dueno.md «Pendientes del dueño» 6; docs/00 §0 punto 6']],
  },
  {
    id: 'freno-captura', momento: 0, titulo: 'Decidir qué hacer con el freno de la captura de anuncios', quien: 'dueno', ruta: '#/sistema',
    porQue: 'El sistema se frenó solo cuando Meta bloqueó una visita; solo tú puedes levantar el freno, y hacerlo mal puede traer problemas con la cuenta.',
    comprobar: chkFrenoCaptura,
    terminos: [{ clave: 'freno_captura', texto: 'freno de la captura de anuncios' }],
    pasos: () => [
      paso('Lee por qué se puso el freno.', { comando: 'cat empresa/captura/freno.json', tituloComando: 'Mostrar el motivo del freno (solo lee)' }),
      paso('Lo recomendado: dejarlo puesto hasta entender la causa. El descubrimiento sigue avanzando con material que le pasas a mano.'),
      paso('Si decides levantarlo, lo haces tú desde tu terminal. El panel no tiene botón para esto, a propósito: la captura no se reintenta ni se evade cuando Meta pide un captcha o un límite.', { comando: 'rm empresa/captura/freno.json', tituloComando: 'Levantar el freno (solo tú, solo si ya entendiste la causa)' }),
    ],
    donde: [enlace('Salud del sistema', '#/sistema'), enlace('Radar de ofertas', '#/descubrimiento')],
    tecnico: [['Cómo se sabe', '`freno_captura.activo` en GET /api/sistema (empresa/captura/freno.json)'], ['Fuente', 'docs/00 §0 puntos 9 y 11']],
  },
  {
    id: 'probar-pausa', momento: 0, titulo: 'Probar el freno de emergencia PAUSA', quien: 'dueno', ruta: '#/sistema',
    porQue: 'Es el botón que detiene todo el gasto: conviene comprobar que funciona antes de necesitarlo de verdad.',
    comprobar: chkPausa,
    sinDato: 'El panel no guarda si ya probaste el freno de emergencia, así que no puede comprobarlo.',
    terminos: [{ clave: 'pausa', texto: 'PAUSA (freno de emergencia)' }],
    acciones: [{ id: 'pruebas_paquete', args: { paquete: 'infra' } }],
    pasos: () => [
      paso('Corre el simulacro del freno: prueba 12 situaciones de emergencia sin tocar cuentas reales. Algunas quedan «pendientes» porque necesitan cuentas reales.', { comando: '.venv/bin/python -m infra.simulacro ejecutar', tituloComando: 'Probar el freno de emergencia en simulacro' }),
      paso('Prueba el botón real: aprieta «Pausar todo» arriba a la derecha. Tiene que aparecer la PAUSA en la barra superior.'),
      paso('Levanta la PAUSA tú desde tu terminal. El panel no la borra, a propósito.', { comando: 'rm empresa/PAUSA', tituloComando: 'Levantar la PAUSA (solo tú)' }),
    ],
    donde: [enlace('Salud del sistema', '#/sistema')],
    tecnico: [['Cómo se sabe', 'No queda registro de la prueba; solo se ve si la PAUSA está puesta ahora (GET /api/sistema)'], ['Fuente', 'infra/simulacro.py (pruebas A-1 a A-12); mapeo.md §11 riesgo 4']],
  },

  // ═════════════ 1 · Preparar la primera oferta ═════════════
  {
    id: 'of-tema', momento: 1, titulo: 'Elegir el tema de la oferta', quien: 'dueno', porOferta: true, ruta: '#/descubrimiento',
    porQue: 'Todo lo demás se construye sobre este tema: el sistema propone candidatos con evidencia y eliges uno tú.',
    comprobar: chkEtapa('D1', { nombre: 'La elección del tema' }),
    acciones: [ACC_VALIDAR_OFERTA],
    pasos: pasosEtapa({ etapa: 'D1', que: 'la elección del tema', pantalla: enlace('Ver Radar de ofertas', '#/descubrimiento'), antes: 'Los candidatos tienen que caer en salud, relaciones o dinero, y no pueden prometer curas ni ingresos garantizados.' }),
    donde: [enlace('Radar de ofertas', '#/descubrimiento'), enlace('Ofertas', '#/ofertas')],
    tecnico: [['Etapa del sistema', 'D1 Descubrimiento (gate H)'], ['Cómo se sabe', 'Estado de la etapa D1 en GET /api/oferta/<id>']],
  },
  {
    id: 'of-mercado', momento: 1, titulo: 'Elegir el idioma y los países de la oferta', quien: 'dueno', porOferta: true, ruta: '#/paises', depende: ['of-tema'],
    porQue: 'Define en qué idioma se escribe todo, qué moneda se cobra y qué medios de pago hay.',
    comprobar: chkEtapa('M1', { nombre: 'La elección de idioma y países' }),
    acciones: [ACC_VALIDAR_OFERTA],
    pasos: pasosEtapa({ etapa: 'M1', que: 'la elección de idioma y países', pantalla: enlace('Ver Países', '#/paises') }),
    donde: [enlace('Países', '#/paises'), enlace('Ofertas', '#/ofertas')],
    tecnico: [['Etapa del sistema', 'M1 Mercado (gate H)'], ['Cómo se sabe', 'Estado de la etapa M1 en GET /api/oferta/<id>']],
  },
  {
    id: 'of-validar', momento: 1, titulo: 'Validar que hay demanda', quien: 'ia', porOferta: true, ruta: '#/ofertas', depende: ['of-tema', 'of-mercado'],
    porQue: 'Comprueba con evidencia que hay gente que quiere esto y que lo gratis no alcanza, antes de invertir en producirlo.',
    comprobar: chkEtapa('D2', { nombre: 'La validación' }),
    acciones: [ACC_VALIDAR_OFERTA],
    pasos: pasosEtapa({ etapa: 'D2', que: 'la validación', pantalla: enlace('Ver la oferta', '#/ofertas') }),
    donde: [enlace('Ofertas', '#/ofertas')],
    tecnico: [['Etapa del sistema', 'D2 Validación'], ['Cómo se sabe', 'Estado de la etapa D2 en GET /api/oferta/<id>']],
  },
  {
    id: 'of-oferta', momento: 1, titulo: 'Diseñar la oferta', quien: 'ia', porOferta: true, ruta: '#/ofertas', depende: ['of-validar'],
    porQue: 'Define qué se vende, a qué precio, con qué garantía y si los números dan para ganar plata.',
    comprobar: chkEtapa('D3', { nombre: 'El diseño de la oferta' }),
    acciones: [ACC_VALIDAR_OFERTA],
    pasos: pasosEtapa({ etapa: 'D3', que: 'el diseño de la oferta', pantalla: enlace('Ver la oferta', '#/ofertas') }),
    donde: [enlace('Ofertas', '#/ofertas'), enlace('Finanzas', '#/finanzas')],
    tecnico: [['Etapa del sistema', 'D3 Oferta'], ['Cómo se sabe', 'Estado de la etapa D3 en GET /api/oferta/<id>']],
  },
  {
    id: 'of-producto', momento: 1, titulo: 'Crear el producto', quien: 'ia', porOferta: true, ruta: '#/ofertas', depende: ['of-oferta'],
    porQue: 'Es lo que recibe quien paga: tiene que cumplir lo que promete la oferta, en su idioma.',
    comprobar: chkEtapa('D4', { nombre: 'El producto' }),
    acciones: [ACC_VALIDAR_OFERTA],
    pasos: pasosEtapa({ etapa: 'D4', que: 'el producto', pantalla: enlace('Ver la oferta', '#/ofertas') }),
    donde: [enlace('Ofertas', '#/ofertas')],
    tecnico: [['Etapa del sistema', 'D4 Producto'], ['Cómo se sabe', 'Estado de la etapa D4 en GET /api/oferta/<id>']],
  },
  {
    id: 'of-landing', momento: 1, titulo: 'Armar la página de ventas y de pago', quien: 'ia', porOferta: true, ruta: '#/landing', depende: ['of-oferta', 'of-producto'],
    porQue: 'Es donde llega quien hace clic en el anuncio: tiene que convencer, cumplir las reglas y cobrar bien.',
    comprobar: chkEtapa('D5', { nombre: 'La página de ventas y de pago' }),
    acciones: [{ id: 'landing_validar' }, ACC_VALIDAR_OFERTA],
    pasos: pasosEtapa({ etapa: 'D5', que: 'la página de ventas y de pago', pantalla: enlace('Ver Página de venta', '#/landing'), antes: 'Publicar la página es otra aprobación aparte, y no la hace el panel.' }),
    donde: [enlace('Página de venta', '#/landing')],
    tecnico: [['Etapa del sistema', 'D5 Página de venta y pago (publicar es otro gate H)'], ['Cómo se sabe', 'Estado de la etapa D5 en GET /api/oferta/<id>']],
  },
  {
    id: 'of-anuncios', momento: 1, titulo: 'Preparar los anuncios', quien: 'ia', porOferta: true, ruta: '#/fabrica', depende: ['of-oferta', 'of-landing'],
    porQue: 'Son los textos, imágenes y avisos de uso de IA que se van a probar: unos 10 por campaña.',
    comprobar: chkEtapa('D6', { nombre: 'Los anuncios' }),
    acciones: [ACC_VALIDAR_OFERTA],
    pasos: pasosEtapa({ etapa: 'D6', que: 'los anuncios', pantalla: enlace('Ver Fábrica', '#/fabrica') }),
    donde: [enlace('Fábrica', '#/fabrica')],
    tecnico: [['Etapa del sistema', 'D6 Creativos'], ['Cómo se sabe', 'Estado de la etapa D6 en GET /api/oferta/<id>']],
  },
  {
    id: 'of-cumplimiento', momento: 1, titulo: 'Pasar la revisión de cumplimiento con visto bueno firmado', quien: 'sistema', porOferta: true, ruta: '#/cumplimiento', depende: ['of-landing', 'of-anuncios'],
    porQue: 'Una revisión independiente verifica que la página y los anuncios no rompan las reglas de Meta ni de Stripe. Sin visto bueno firmado, no se publica ni se prende nada.',
    comprobar: chkCumplimientoPagAnuncios,
    terminos: [{ clave: 'sello_x1', texto: 'visto bueno firmado' }, { clave: 'vigencia_sello', texto: 'vigencia' }],
    pasos: (c) => {
      const o = idComando(c);
      return [
        paso('Pide la revisión de cumplimiento de la página (D5) y de los anuncios (D6). La hace una IA revisora; el visto bueno lo firma el código con una clave que la IA no tiene.', { enlace: enlace('Ver Cumplimiento', '#/cumplimiento') }),
        paso('Antes, el sistema revisa las frases de la página y los anuncios.', { comando: `.venv/bin/python -m compliance.lint_claims --oferta ${o} --etapa D5 --locale <IDIOMA_PAIS>`, tituloComando: 'Revisar las frases de la página (cambia a D6 para los anuncios)' }),
        paso('Cuando la revisión sale aprobada, se firma el visto bueno sobre esa versión exacta.', { comando: `.venv/bin/python -m compliance.sellar --oferta ${o} --etapa-objetivo D5 --artefacto <RUTA_DE_LO_REVISADO> --dictamen ofertas/<CARPETA>/qa/x1-d5-v1.json --locale <IDIOMA_PAIS>`, tituloComando: 'Firmar el visto bueno de la página (repetir con D6)', nota: 'Reemplaza lo que está entre < >. Si la página cambia después, el visto bueno deja de valer.' }),
        paso('Verifica en Cumplimiento que los vistos buenos figuren como vigentes.', { enlace: enlace('Ver Cumplimiento', '#/cumplimiento') }),
      ];
    },
    donde: [enlace('Cumplimiento', '#/cumplimiento')],
    tecnico: [['Cómo se sabe', 'Sellos de GET /api/cumplimiento con `etapa_objetivo` D5 y D6 de la oferta, no vencidos ni alterados'], ['Quién firma', 'El sello lo emite `compliance.sellar`; el panel solo lo lee']],
  },

  // ═════════════ 2 · Lanzar ═════════════
  {
    id: 'lz-chequeo', momento: 2, titulo: 'Tener el chequeo antes de lanzar en verde y al día', quien: 'sistema', ruta: '#/sistema',
    porQue: 'El sistema no prende nada si el último chequeo está en rojo, venció (más de 6 horas) o fue un simulacro.',
    comprobar: (c) => chkChequeo(c, { exigirVigente: true }),
    terminos: [{ clave: 'preflight_infra', texto: 'chequeo antes de lanzar' }],
    pasos: () => [
      paso('Repite el chequeo justo antes de lanzar, en modo vivo.', { comando: `${CMD_CHEQUEO} --infra-modo vivo`, tituloComando: 'Hacer el chequeo de verdad (modo vivo)' }),
      paso('Mira que todo esté en verde. Si algo está en rojo, arréglalo y repite.', { enlace: enlace('Ver Salud del sistema', '#/sistema') }),
    ],
    donde: [enlace('Salud del sistema', '#/sistema')],
    tecnico: [['Cómo se sabe', '`infra.semaforo` VERDE, `infra.modo` vivo y vigente (menos de 6 horas o `valido_hasta` futuro)']],
  },
  {
    id: 'lz-frenos', momento: 2, titulo: 'Tener los frenos de gasto firmados', quien: 'sistema', ruta: '#/parametros',
    porQue: 'Antes de gastar, el sistema comprueba que existan el tope diario y la pausa por pérdida. Son los mismos de la tarea «Fijar y firmar los frenos de gasto».',
    comprobar: chkFrenos,
    terminos: [{ clave: 'frenos_empresa', texto: 'frenos de la empresa' }],
    pasos: () => [
      paso('Si todavía no están firmados, sigue los pasos de la tarea «Fijar y firmar los frenos de gasto» del primer momento.', { enlace: enlace('Ver Límites y reglas', '#/parametros') }),
    ],
    donde: [enlace('Límites y reglas', '#/parametros')],
    tecnico: [['Cómo se sabe', 'Igual que «Fijar y firmar los frenos de gasto»']],
  },
  {
    id: 'lz-campana', momento: 2, titulo: 'Armar la campaña de prueba', quien: 'ia', porOferta: true, ruta: '#/campanas', depende: ['of-landing', 'of-anuncios'],
    porQue: 'Una sola campaña con unos 10 anuncios y entre 50 y 100 USD por día prueba el paquete completo a la vez: oferta, página y anuncios. El plan propone arrancar con 75 USD, pero es una hipótesis.',
    comprobar: chkEtapa('D7', { nombre: 'La campaña' }),
    terminos: [{ clave: 'campana_compartida', texto: 'campaña con presupuesto compartido' }],
    acciones: [ACC_VALIDAR_OFERTA],
    pasos: pasosEtapa({ etapa: 'D7', que: 'la campaña', pantalla: enlace('Ver Campañas', '#/campanas'), antes: 'Armarla no gasta nada: queda lista pero apagada.' }),
    donde: [enlace('Campañas', '#/campanas')],
    tecnico: [['Etapa del sistema', 'D7 Campaña'], ['Parámetros del plan', 'lanzamiento.presupuesto_cbo_usd 50-100 (arranque 75) y lanzamiento.creativos_por_cbo ≈ 10: todos [HIPÓTESIS] de mapeo.md §12']],
  },
  {
    id: 'lz-cumplimiento', momento: 2, titulo: 'Tener el visto bueno de cumplimiento vigente para la campaña', quien: 'sistema', porOferta: true, ruta: '#/cumplimiento', depende: ['lz-campana'],
    porQue: 'Sin un visto bueno firmado y vigente sobre lo que se va a prender, el sistema no activa nada. Es la protección contra los rechazos de Meta y Stripe.',
    comprobar: chkCumplimientoCampana,
    terminos: [{ clave: 'sello_x1', texto: 'visto bueno firmado' }],
    pasos: (c) => [
      paso('Pide la revisión de cumplimiento de la campaña armada (D7).', { enlace: enlace('Ver Cumplimiento', '#/cumplimiento') }),
      paso('Si sale aprobada, se firma el visto bueno sobre esa campaña exacta. Si cambia algo de la campaña, hay que pedirlo de nuevo.', { comando: `.venv/bin/python -m compliance.sellar --oferta ${idComando(c)} --etapa-objetivo D7 --artefacto <RUTA_DE_LA_CAMPANA> --dictamen ofertas/<CARPETA>/qa/x1-d7-v1.json --locale <IDIOMA_PAIS>`, tituloComando: 'Firmar el visto bueno de la campaña', nota: 'Reemplaza lo que está entre < >.' }),
    ],
    donde: [enlace('Cumplimiento', '#/cumplimiento'), enlace('Campañas', '#/campanas')],
    tecnico: [['Cómo se sabe', 'Sello de GET /api/cumplimiento con `etapa_objetivo` D7 de la oferta, no vencido ni alterado']],
  },
  {
    id: 'lz-activar', momento: 2, titulo: 'Prender la campaña', quien: 'dueno', porOferta: true, ruta: '#/campanas', depende: ['lz-campana', 'lz-chequeo', 'lz-cumplimiento', 'lz-frenos'],
    porQue: 'Es el momento en que empieza el gasto real: por eso se exige que todo lo anterior esté en verde.',
    comprobar: chkActivar,
    hoyObjetivo: (c) => {
      const lim = limitesValores(c);
      const g = datosDe(lec(c, 'gates'));
      let humano = null;
      if (lim && Array.isArray(lim.acciones_gate_humano)) humano = lim.acciones_gate_humano.includes('activar_campana') ? true : null;
      const est = estadoOferta(c);
      const nivel = est && typeof est.nivel === 'string' ? est.nivel : null;
      const fila = g && esObj(g.gates) && esObj(g.gates.entradas) ? g.gates.entradas['accion:activar_campana'] : null;
      const gateTabla = fila && esObj(fila.gate) && nivel ? fila.gate[nivel] : null;
      if (gateTabla === 'H') humano = true;
      const sabe = humano === true;
      return {
        hoy: { texto: 'Prender una campaña exige tu firma. Ni el sistema ni una IA pueden hacerlo solos.', comprobado: sabe ? true : null, fuente: sabe ? 'Comprobado en los límites firmados y en la tabla de puntos de control.' : 'Así lo dice el plan: el panel no pudo comprobarlo en este momento.' },
        objetivo: { texto: 'Lo hace el sistema solo, dentro de los frenos: con visto bueno de cumplimiento vigente, chequeo en verde, frenos de gasto firmados y la PAUSA a mano.', fuente: 'Decisión J2 (2026-11-06). Todavía no está implementado: no rige.' },
      };
    },
    terminos: [{ clave: 'activar_sin_clic', texto: 'prender sin tu clic' }, { clave: 'hoy_vigente', texto: 'Hoy' }, { clave: 'objetivo_j2', texto: 'Objetivo' }],
    pasos: (c, est) => {
      const l = [];
      if (est.clave === 'bloqueada') l.push(paso('Primero tienen que estar en verde las tareas anteriores de este momento (están marcadas en esta pantalla).'));
      l.push(paso('Mira la campaña armada: presupuesto, anuncios y a qué país va.', { enlace: enlace('Ver Campañas', '#/campanas') }));
      l.push(paso('Si todo está bien, firma la orden de prender la campaña. La firmas tú, desde tu terminal, con tu clave privada. El panel no prende campañas.', { comando: `${CMD} firmar --oferta ${idComando(c)} --accion activar_campana --hash-objetivo <HUELLA_DE_LA_CAMPANA> --clave-privada <RUTA_A_TU_CLAVE> --como dueno`, tituloComando: 'Firmar la orden de prender la campaña (solo tú)', nota: 'La huella de la campaña se ve en la pantalla de Campañas. Reemplaza lo que está entre < >.' }));
      l.push(paso('Mira cómo arranca el primer día en Resultados.', { enlace: enlace('Ver Resultados', '#/operacion') }));
      return l;
    },
    donde: [enlace('Campañas', '#/campanas'), enlace('Resultados', '#/operacion'), enlace('Quién decide qué', '#/quien-decide')],
    tecnico: [['Etapa del sistema', 'D7: acción `activar_campana` (siempre gate H hoy; las seis acciones mínimas no se pueden quitar)'], ['Cómo se sabe', 'Fase de la oferta (`en_test` o posterior = ya se prendió) y `gate_pendiente` de D7']],
  },
  {
    id: 'lz-baja', momento: 2, titulo: 'Dar de baja la oferta que no vende al primer día', quien: 'sistema', ruta: '#/operacion', depende: ['lz-activar'],
    porQue: 'Regla del plan: si pasó un día, se gastó el presupuesto del día y no hubo ninguna venta, la oferta se da de baja y se prueba otra. Si Meta no gastó el presupuesto, ese día no cuenta.',
    terminos: [{ clave: 'regla_baja_dia', texto: 'regla de baja del primer día' }],
    pasos: () => [
      paso('No tienes que hacer nada: cuando exista, el sistema aplicará esta regla solo, todos los días.'),
      paso('Un día sin ventas puede ser mala suerte. Por eso el plan pide medir cuántas ofertas se dieron de baja de más (que después habrían vendido) y ajustar la regla con esos datos.'),
      paso('Mientras no exista, mira a mano cómo va el primer día de la campaña.', { enlace: enlace('Ver Resultados', '#/operacion') }),
    ],
    donde: [enlace('Resultados', '#/operacion')],
    tecnico: [['Fuente', 'decisiones-del-dueno.md J3; mapeo.md §3.1. Parámetros propuestos: lanzamiento.baja_dias = 1 y lanzamiento.baja_requiere_presupuesto_gastado = true']],
  },

  // ═════════════ 3 · Cada día ═════════════
  {
    id: 'dia-fabrica', momento: 3, titulo: 'Producir los anuncios del día, de noche', quien: 'ia', cuando: 'Todos los días, de 00:00 a 07:00', ruta: '#/fabrica',
    porQue: 'Cada mañana tienes anuncios nuevos listos para aprobar, sin tener que pedirlos.',
    pasos: () => [
      paso('No tienes que hacer nada: cuando exista, cada mañana vas a encontrar los anuncios nuevos en «Por aprobar».'),
      paso('Mientras no exista, los anuncios se producen a pedido con la etapa de anuncios de cada oferta.', { enlace: enlace('Ver Fábrica', '#/fabrica') }),
    ],
    donde: [enlace('Fábrica', '#/fabrica')],
    tecnico: [['Fuente', 'mapeo.md §2 (franja 00:00-07:00) y §6']],
  },
  {
    id: 'dia-jurado', momento: 3, titulo: 'Ordenar los anuncios con el jurado antes de gastar', quien: 'ia', cuando: 'Todos los días a las 07:00', ruta: '#/jurado',
    porQue: 'Un jurado de clientes hechos con IA vota a ciegas qué anuncio conviene probar primero, así se gasta menos en lo que seguro no anda.',
    comprobar: chkJurado,
    terminos: [{ clave: 'jurado_sintetico', texto: 'jurado' }],
    pasos: () => [
      paso('No tienes que hacer nada: cuando exista, el jurado ordena la tanda del día antes de gastar.'),
      paso('Si el jurado no acierta más que el azar después de 150 ventas medidas, se apaga solo.'),
      paso('Mira cómo va a ser el jurado y qué le falta.', { enlace: enlace('Ver Jurado', '#/jurado') }),
    ],
    donde: [enlace('Jurado', '#/jurado')],
    tecnico: [['Cómo se sabe', 'Busca `06-creativos/jurado.json` en la etapa D6 de la oferta real elegida'], ['Fuente', 'mapeo.md §1 (pieza 3) y §5']],
  },
  {
    id: 'dia-cola', momento: 3, titulo: 'Cargar y prender los lanzamientos del día', quien: 'sistema', cuando: 'Todos los días a las 00:10', ruta: '#/campanas',
    porQue: 'Los anuncios nuevos entran a probarse todos los días, sin que nadie los suba uno por uno.',
    pasos: () => [
      paso('No tienes que hacer nada: cuando exista, el sistema carga los anuncios aprobados y los prende dentro de los frenos.'),
      paso('Mientras no exista, cada campaña se arma y se prende a mano.', { enlace: enlace('Ver Campañas', '#/campanas') }),
    ],
    donde: [enlace('Campañas', '#/campanas')],
    tecnico: [['Fuente', 'mapeo.md §2 (00:10 «cola de testeo») y §10 Fase 3']],
  },
  {
    id: 'dia-robots', momento: 3, titulo: 'Subir, bajar, apagar y frenar anuncios solos, dentro de tus topes', quien: 'sistema', cuando: 'Cada 15 y cada 30 minutos', ruta: '#/robots',
    porQue: 'Lo que vende recibe más presupuesto y lo que no rinde se frena rápido, a toda hora y sin que estés mirando.',
    comprobar: chkRobot(['escalera', 'salvavidas', 'guardia', 'cola'], { frase: 'Al menos un robot de anuncios' }),
    terminos: [{ clave: 'robot', texto: 'robots' }],
    pasos: () => [
      paso('No tienes que hacer nada: cuando existan, los robots trabajan solos dentro de los topes que firmaste.'),
      paso('Mira cuáles robots están planeados, cuáles existen y cuál es su horario.', { enlace: enlace('Ver Robots', '#/robots') }),
    ],
    donde: [enlace('Robots', '#/robots')],
    tecnico: [['Cómo se sabe', 'Registro de robots (empresa/robots.yaml): busca escalera, salvavidas, guardia o cola'], ['Fuente', 'mapeo.md §1 (pieza 5)']],
  },
  {
    id: 'dia-auditor', momento: 3, titulo: 'Controlar cada decisión de los robots (auditor)', quien: 'sistema', cuando: 'Cada hora', ruta: '#/robots?vista=reglas',
    porQue: 'Un auditor juzga cada decisión con lo que pasó después y baja de nivel al robot que falla. Es la pieza más valiosa y la más fácil de olvidar.',
    comprobar: chkRobot(['auditor'], { frase: 'El auditor' }),
    terminos: [{ clave: 'auditor_robots', texto: 'auditor' }],
    pasos: () => [
      paso('No tienes que hacer nada: cuando exista, el auditor mide el acierto de cada robot y te avisa si alguno falla.'),
      paso('Mira las reglas de oro y cómo se va a auditar.', { enlace: enlace('Ver las reglas de los robots', '#/robots?vista=reglas') }),
    ],
    donde: [enlace('Robots', '#/robots')],
    tecnico: [['Cómo se sabe', 'Registro de robots: busca un robot «auditor»'], ['Fuente', 'mapeo.md §11 riesgo 1']],
  },
  {
    id: 'dia-resumen', momento: 3, titulo: 'Recibir el resumen del día', quien: 'sistema', cuando: 'Todos los días a las 08:30', ruta: '#/avisos', depende: ['avisos-celular'],
    porQue: 'Un solo mensaje por mañana con las ventas, el gasto y las alertas, sin que tengas que abrir el panel.',
    comprobar: chkRobot(['informe', 'resumen'], { frase: 'El informe del día' }),
    terminos: [{ clave: 'resumen_diario', texto: 'resumen del día' }],
    pasos: () => [
      paso('Primero elige el canal de avisos en el celular (tarea del primer momento).', { enlace: enlace('Ver Avisos', '#/avisos') }),
      paso('Después no tienes que hacer nada: cuando exista, el resumen llega solo a las 08:30 (los importes por correo y los porcentajes por el celular).'),
    ],
    donde: [enlace('Avisos', '#/avisos')],
    tecnico: [['Cómo se sabe', 'Registro de robots: busca el robot «informe»'], ['Fuente', 'mapeo.md §9: el productor de alertas aún no existe']],
  },
  {
    id: 'dia-alertas', momento: 3, titulo: 'Recibir las alertas de pago en el celular', quien: 'sistema', cuando: 'Siempre, en el momento', ruta: '#/pagos', depende: ['avisos-celular'],
    porQue: 'Si hay un reembolso raro, una disputa o un cobro caído, te enterás enseguida y no al otro día.',
    sinDato: 'El vigía de pagos existe en el código, pero el panel no puede saber si ya llega a tu celular.',
    terminos: [{ clave: 'vigia_pagos', texto: 'vigía de pagos' }],
    pasos: () => [
      paso('Primero elige el canal de avisos en el celular (tarea del primer momento).', { enlace: enlace('Ver Avisos', '#/avisos') }),
      paso('Después, mira en Pagos que los cobros se vean en vivo.', { enlace: enlace('Ver Pagos', '#/pagos') }),
    ],
    donde: [enlace('Pagos', '#/pagos'), enlace('Avisos', '#/avisos')],
    tecnico: [['Cómo se sabe', 'No hay señal que lo diga: el vigía (infra/workers/watchdog) existe, el envío al celular depende del canal elegido'], ['Fuente', 'mapeo.md §2 (siempre: vigía de pagos)']],
  },
  {
    id: 'dia-atencion', momento: 3, titulo: 'Mirar «Requiere tu atención» en el Resumen', quien: 'dueno', periodo: 'dia', cuando: 'Una vez por día', ruta: '#/resumen',
    porQue: 'Ahí aparece, ordenado por gravedad, lo único que de verdad espera tu decisión ese día.',
    comprobar: chkAtencion,
    sinDato: 'No se puede saber si ya miraste hoy. Si no hay nada pendiente, alcanza con una mirada rápida.',
    pasos: () => [
      paso('Abre el Resumen y mira el bloque «Requiere tu atención».', { enlace: enlace('Ir al Resumen', '#/resumen') }),
      paso('Si hay algo, cada aviso trae un botón que te lleva a donde se resuelve. Si no hay nada, ya terminaste por hoy.'),
    ],
    donde: [enlace('Resumen', '#/resumen')],
    tecnico: [['Cómo se sabe', 'Cuenta pasos que esperan firma en ofertas reales y pendientes del dueño abiertos en la lista única; si no hay, no se puede saber si ya miraste']],
  },

  // ═════════════ 4 · Cada semana ═════════════
  {
    id: 'sem-lun', momento: 4, titulo: 'Cerrar la semana y ordenar los ángulos', quien: 'sistema', cuando: 'Lunes', ruta: '#/finanzas',
    porQue: 'Muestra qué ángulo (la idea del anuncio) ganó en cada idioma, y con eso se decide qué repetir.',
    pasos: () => [
      paso('No tienes que hacer nada: cuando exista, el lunes aparece el ranking de ángulos por idioma.'),
      paso('Mientras no exista, puedes mirar cómo viene la plata.', { enlace: enlace('Ver Finanzas', '#/finanzas') }),
    ],
    donde: [enlace('Finanzas', '#/finanzas')],
    tecnico: [['Fuente', 'mapeo.md §2 (lunes) y §6 (tablero de rendimiento por formato)']],
  },
  {
    id: 'sem-mar', momento: 4, titulo: 'Hacer la tanda nueva: variaciones de lo que ganó', quien: 'ia', cuando: 'Martes', ruta: '#/fabrica',
    porQue: 'Lo que ya vende se repite con otras aperturas, para renovar los anuncios antes de que se cansen.',
    pasos: () => [
      paso('No tienes que hacer nada: cuando exista, la IA prepara las variaciones y quedan en «Por aprobar».'),
      paso('Mientras no exista, se pueden pedir a mano desde la etapa de anuncios.', { enlace: enlace('Ver Fábrica', '#/fabrica') }),
    ],
    donde: [enlace('Fábrica', '#/fabrica')],
    tecnico: [['Fuente', 'mapeo.md §2 (martes) y §6']],
  },
  {
    id: 'sem-mie', momento: 4, titulo: 'Recalibrar el jurado con lo que de verdad se vendió', quien: 'sistema', cuando: 'Miércoles', ruta: '#/jurado',
    porQue: 'El jurado solo sirve si acierta: cada semana se compara lo que predijo con lo que se cobró.',
    terminos: [{ clave: 'jurado_sintetico', texto: 'jurado' }],
    pasos: () => [
      paso('No tienes que hacer nada: cuando exista, el jurado se ajusta solo con los resultados.'),
      paso('Mira cómo se va a medir su acierto.', { enlace: enlace('Ver Jurado', '#/jurado') }),
    ],
    donde: [enlace('Jurado', '#/jurado')],
    tecnico: [['Fuente', 'mapeo.md §2 (miércoles)']],
  },
  {
    id: 'sem-jue', momento: 4, titulo: 'Avanzar el idioma nuevo', quien: 'ia', cuando: 'Jueves', ruta: '#/paises',
    porQue: 'Cada semana el tablero del idioma nuevo avanza un poco: tienda, dominio, cobro, anuncios y lo legal de ese país.',
    terminos: [{ clave: 'tablero_idioma', texto: 'tablero de lanzamiento de idioma' }],
    pasos: () => [
      paso('No tienes que hacer nada: cuando exista, el tablero se va completando solo y te muestra cuánto falta.'),
      paso('Mira cómo es el tablero y qué tarjetas tendría.', { enlace: enlace('Ver Países', '#/paises') }),
    ],
    donde: [enlace('Países', '#/paises')],
    tecnico: [['Fuente', 'mapeo.md §8 (`lanzamiento_idioma.json`, ~26 tarjetas)']],
  },
  {
    id: 'sem-vie', momento: 4, titulo: 'Revisar las reglas nuevas que propone el sistema', quien: 'dueno', periodo: 'semana', cuando: 'Viernes', ruta: '#/cerebro',
    porQue: 'Lo aprendido con plata se vuelve regla. Solo tú puedes aprobar reglas nuevas: ni el sistema ni una IA las escriben solos.',
    comprobar: chkReglas,
    sinDato: 'Hoy no hay reglas propuestas esperando. El panel no puede saber si ya revisaste esta semana.',
    pasos: () => [
      paso('Abre el Cerebro y mira las reglas propuestas que esperan tu aprobación.', { enlace: enlace('Ir al Cerebro', '#/cerebro') }),
      paso('Aprueba, ajusta o descarta cada una. Las reglas las cambias tú, a mano.'),
    ],
    donde: [enlace('Cerebro', '#/cerebro'), enlace('Mejoras pendientes', '#/pulido')],
    tecnico: [['Cómo se sabe', 'Entradas de la lista única con tipo `regla_propuesta` sin resolver (GET /api/pulido)'], ['Fuente', 'mapeo.md §9: solo el dueño escribe reglas']],
  },
  {
    id: 'sem-sab', momento: 4, titulo: 'Dejar los robots solos, con techo de gasto (piloto automático)', quien: 'sistema', cuando: 'Sábado', ruta: '#/robots',
    porQue: 'El día de menos intervención: los robots trabajan solos dentro del techo que firmaste, para comprobar que no hace falta tocar nada.',
    pasos: () => [
      paso('No tienes que hacer nada: cuando existan los robots y el auditor, el sábado quedan solos con tu techo de gasto.'),
      paso('Mira cómo se sube un robot de nivel.', { enlace: enlace('Ver Robots', '#/robots') }),
    ],
    donde: [enlace('Robots', '#/robots'), enlace('Quién decide qué', '#/quien-decide')],
    tecnico: [['Fuente', 'mapeo.md §2 (sábado) y §10 Fase 3']],
  },
  {
    id: 'sem-dom', momento: 4, titulo: 'Ordenar el cerebro (limpiar y ordenar la memoria)', quien: 'ia', cuando: 'Domingo', ruta: '#/cerebro',
    porQue: 'La memoria del sistema se limpia y se ordena para que la semana arranque sabiendo lo importante.',
    comprobar: chkJardin,
    terminos: [{ clave: 'cerebro', texto: 'cerebro' }],
    pasos: () => [
      paso('Hoy se hace a mano: al cerrar cada sesión de trabajo, corre la guía de trabajo (skill) /cerebro-cerrar para guardar lo aprendido.'),
      paso('Cuando exista el ordenador automático, propondrá la limpieza y tú la apruebas con un clic.'),
      paso('Mira la memoria actual.', { enlace: enlace('Ver el Cerebro', '#/cerebro') }),
    ],
    donde: [enlace('Cerebro', '#/cerebro')],
    tecnico: [['Cómo se sabe', '`jardin.existe` en GET /api/cerebro'], ['Fuente', 'mapeo.md §9']],
  },

  // ═════════════ 5 · Crecer ═════════════
  {
    id: 'cr-idiomas', momento: 5, titulo: 'Llevar el ganador a otros idiomas', quien: 'ia', ruta: '#/paises',
    porQue: 'Si una oferta vende en un idioma, se traduce a los demás con el mismo método y se vende más sin empezar de cero.',
    terminos: [{ clave: 'ruta_familia', texto: 'ruta de familia' }, { clave: 'madre_validada', texto: 'oferta original validada' }],
    pasos: () => [
      paso('Hace falta una oferta original que ya haya vendido de verdad. Todavía no la hay.'),
      paso('Cuando exista la ruta, cada idioma nuevo pasa por su propio tablero de lanzamiento (con lo legal e impositivo de ese país).', { enlace: enlace('Ver Países', '#/paises') }),
    ],
    donde: [enlace('Países', '#/paises')],
    tecnico: [['Fuente', 'decisiones-del-dueno.md J5; mapeo.md §8']],
  },
  {
    id: 'cr-carrito', momento: 5, titulo: 'Armar el carrito con «añadir todo»', quien: 'ia', ruta: '#/poscompra',
    porQue: 'Quien compra puede llevarse varios productos juntos en un solo pago, y cada venta vale más.',
    terminos: [{ clave: 'ticket_promedio', texto: 'ticket promedio' }],
    pasos: () => [
      paso('No tienes que hacer nada todavía. Hoy se vende un producto con una casilla extra al pagar.'),
      paso('Mira cómo se ve hoy lo que pasa después del pago.', { enlace: enlace('Ver Después de la venta', '#/poscompra') }),
    ],
    donde: [enlace('Después de la venta', '#/poscompra')],
    tecnico: [['Fuente', 'mapeo.md §7 paso 3 (`oferta.complementos[]` y `checkout.items_extra[]`)']],
  },
  {
    id: 'cr-post', momento: 5, titulo: 'Ofrecer algo más después de pagar', quien: 'ia', ruta: '#/poscompra',
    porQue: 'Justo después de pagar es cuando más gente dice que sí a un producto extra.',
    terminos: [{ clave: 'oferta_tras_pago', texto: 'oferta después de pagar' }],
    pasos: () => [
      paso('No tienes que hacer nada todavía. Está apagada hasta medir cuántas disputas trae.'),
      paso('Mira qué se planea.', { enlace: enlace('Ver Después de la venta', '#/poscompra') }),
    ],
    donde: [enlace('Después de la venta', '#/poscompra')],
    tecnico: [['Fuente', 'mapeo.md §7 paso 4']],
  },
  {
    id: 'cr-abandonado', momento: 5, titulo: 'Recuperar carritos abandonados por correo', quien: 'sistema', ruta: '#/poscompra',
    porQue: 'Quien dejó el pago a medias recibe un recordatorio, y una parte vuelve a comprar.',
    terminos: [{ clave: 'carrito_abandonado', texto: 'carrito abandonado' }],
    pasos: () => [
      paso('No tienes que hacer nada todavía. Solo se mandará a quienes aceptaron recibir correos.'),
      paso('Mira qué se planea.', { enlace: enlace('Ver Después de la venta', '#/poscompra') }),
    ],
    donde: [enlace('Después de la venta', '#/poscompra')],
    tecnico: [['Fuente', 'mapeo.md §7 paso 5']],
  },
  {
    id: 'cr-organico', momento: 5, titulo: 'Usar el contenido orgánico como radar de formatos', quien: 'ia', ruta: '#/descubrimiento',
    porQue: 'Cuentas secundarias de videos cortos muestran qué formatos funcionan gratis, antes de pagar anuncios con ellos.',
    terminos: [{ clave: 'radar_organico', texto: 'radar orgánico' }],
    pasos: () => [
      paso('No tienes que hacer nada todavía. Esta idea revierte la decisión anterior de «sin Instagram»: la tomaste tú el 2026-11-06.'),
      paso('Sí quedan afuera los testimonios inventados con IA: no se construyen, porque engañan a quien compra.'),
    ],
    donde: [enlace('Radar de ofertas', '#/descubrimiento')],
    tecnico: [['Fuente', 'decisiones-del-dueno.md J8']],
  },
  {
    id: 'cr-nicho4', momento: 5, titulo: 'Abrir el cuarto nicho: habilidades y hobbies', quien: 'dueno', ruta: '#/cumplimiento',
    porQue: 'Instrumentos, cocina, plantas, manualidades y oficios: un cuarto mercado, sin prometer ingresos ni salud.',
    comprobar: chkNicho4,
    pasos: () => [
      paso('No hay que hacer nada todavía. Cuando llegue el momento, firmas el cambio de los límites (hoy admiten solo salud, relaciones y dinero).', { enlace: enlace('Ver Límites y reglas', '#/parametros') }),
      paso('Antes de gastar en este nicho, el revisor de cumplimiento tiene que cubrirlo.', { enlace: enlace('Ver Cumplimiento', '#/cumplimiento') }),
    ],
    donde: [enlace('Cumplimiento', '#/cumplimiento'), enlace('Límites y reglas', '#/parametros')],
    tecnico: [['Cómo se sabe', '`macro_nichos_permitidos` de limites.yaml (hoy el esquema solo admite tres)'], ['Fuente', 'decisiones-del-dueno.md J6 y J9']],
  },
];

for (const t of CATALOGO) { t.orden = CATALOGO.filter((x) => x.momento === t.momento).indexOf(t) + 1; }
const IDS = new Set(CATALOGO.map((t) => t.id));
export const IDS_TAREAS = [...IDS];

// ───────────────────────── acciones seguras (lista blanca de la consola de Sistema) ─────────────────────────

/**
 * Las ÚNICAS acciones que esta pantalla puede ejecutar (mismo mecanismo que la consola de Sistema: POST /accion con un id de dashboard/acciones.yaml).
 * Todas son de solo lectura. Nada de firmar, publicar, activar, gastar, enviar ni tocar la PAUSA o el freno.
 */
export const ACCIONES_SEGURAS = {
  validar_oferta: {
    etiqueta: 'Revisar los archivos de la oferta', args: (c) => (c.oferta.hay && carpetaValida(c.oferta.id) ? { oferta: c.oferta.id } : null), falta: 'Necesita una oferta existente.',
    quehace: 'Comprueba que los archivos de la oferta tengan el formato esperado y no se contradigan entre sí. Solo lee: no cambia nada.',
    bien: 'No se encontró ningún problema en los archivos de la oferta.',
  },
  landing_validar: {
    etiqueta: 'Revisar la página de ventas', args: (c) => (c.oferta.hay && carpetaValida(c.oferta.id) ? { oferta: c.oferta.id } : null), falta: 'Necesita una oferta con página de ventas.',
    quehace: 'Revisa la página de ventas antes de publicarla: precio, moneda, garantía, enlaces, textos legales y consentimiento. Solo lee: no cambia nada.',
    bien: 'La página de ventas pasó la revisión.',
  },
  pruebas_paquete: {
    etiqueta: 'Correr las pruebas automáticas', args: (c, fija) => (fija && typeof fija.paquete === 'string' ? { paquete: fija.paquete } : null), falta: 'Falta indicar qué paquete probar.',
    quehace: 'Corre las pruebas automáticas del código de infraestructura, que incluye el freno de emergencia. No toca cuentas reales ni crea la PAUSA.',
    bien: 'Las pruebas automáticas pasaron.',
  },
  validar_esquemas: {
    etiqueta: 'Validar los formatos de los contratos', args: () => ({}), falta: '',
    quehace: 'Comprueba que los formatos esperados de todos los archivos (los contratos) estén bien escritos. Solo lee: no cambia nada.',
    bien: 'Todos los formatos están bien escritos.',
  },
};

/** Lo que se ofrece en el panel de una tarea: [{id, etiqueta, quehace, args|null, disponible, motivo}]. `servidor` = GET /acciones normalizado a [{id, riesgo, proximamente, motivo, parametros:[{nombre, requerido}]}]. */
export function accionesDeTarea(tarea, c, servidor) {
  const lista_ = lista(servidor);
  return lista(tarea.acciones).map((a) => {
    const def = ACCIONES_SEGURAS[a.id];
    if (!def) return null;
    const args = def.args(c, a.args || null);
    const s = lista_.find((x) => esObj(x) && x.id === a.id);
    let disponible = true; let motivo = '';
    if (!s) { disponible = false; motivo = 'El servidor no ofrece esta comprobación.'; }
    else if (s.riesgo !== 'lectura') { disponible = false; motivo = 'No se ofrece desde aquí porque no es de solo lectura.'; }
    else if (s.proximamente) { disponible = false; motivo = corto(s.motivo || 'Todavía no está disponible.', 160); }
    else if (!args) { disponible = false; motivo = def.falta || 'Faltan datos para ejecutarla.'; }
    else {
      const requeridos = lista(s.parametros).filter((p) => esObj(p) && p.requerido).map((p) => p.nombre);
      if (requeridos.some((r) => !(r in args))) { disponible = false; motivo = 'Faltan datos para ejecutarla.'; }
    }
    return { id: a.id, etiqueta: def.etiqueta, quehace: def.quehace, bien: def.bien, args, disponible, motivo };
  }).filter(Boolean);
}

/** Normaliza GET /acciones a [{id, riesgo, proximamente, motivo, parametros:[{nombre, requerido}]}]. */
export function normalizarAccionesServidor(datos) {
  const l = Array.isArray(datos) ? datos : (esObj(datos) && Array.isArray(datos.acciones) ? datos.acciones : []);
  return l.filter((a) => esObj(a) && typeof a.id === 'string').map((a) => {
    const crudo = a.parametros ?? a.params ?? a.args ?? [];
    const pars = Array.isArray(crudo) ? crudo : Object.entries(esObj(crudo) ? crudo : {}).map(([k, p]) => ({ nombre: k, ...(esObj(p) ? p : {}) }));
    return {
      id: a.id, riesgo: a.riesgo || null, proximamente: a.proximamente === true || a.disponible === false, motivo: typeof a.motivo === 'string' ? a.motivo : null,
      parametros: pars.filter(esObj).map((p) => ({ nombre: String(p.nombre ?? p.clave ?? ''), requerido: p.requerido === true })).filter((p) => p.nombre),
    };
  });
}

/** Normaliza GET /job/<id>?desde=N a {terminado, codigo, estado, texto, siguiente}. */
export function normalizarJob(d, desde = 0) {
  if (!esObj(d)) return { terminado: false, codigo: null, estado: null, texto: '', siguiente: desde };
  const texto = [d.salida, d.texto, d.stdout].find((x) => typeof x === 'string') || (Array.isArray(d.lineas) ? d.lineas.map((x) => (typeof x === 'string' ? x : (x && x.texto) || '')).join('\n') : '');
  const estado = typeof d.estado === 'string' ? d.estado : null;
  const codigo = [d.codigo, d.codigo_salida, d.returncode, d.salio_con].find((x) => Number.isInteger(x));
  const terminado = d.terminado === true || d.finalizado === true || ['terminado', 'finalizado', 'ok', 'error', 'fallo', 'timeout', 'cancelado', 'completado', 'tope_salida'].includes(estado) || (codigo !== undefined && estado !== 'corriendo');
  const sig = [d.siguiente, d.hasta, d.offset, d.next].find((x) => Number.isInteger(x));
  return { terminado, codigo: codigo === undefined ? null : codigo, estado, texto: String(texto).replace(/\u001B\[[0-9;?]*[ -/]*[@-~]/g, '').replace(/\r\n?/g, '\n'), siguiente: sig !== undefined ? sig : desde + String(texto).length };
}

/** El resultado de una acción en palabras simples: {clave:'corriendo'|'ok'|'error'|'aviso', icono, titulo, texto}. */
export function resultadoEnSimple(accionId, job) {
  const def = ACCIONES_SEGURAS[accionId] || {};
  if (!job || !job.terminado) return { clave: 'corriendo', icono: 'progreso', titulo: 'Revisando…', texto: 'Esto puede tardar unos segundos. Puedes cerrar el panel: sigue corriendo.' };
  if (job.estado === 'timeout') return { clave: 'error', icono: 'alerta', titulo: 'Tardó demasiado y se cortó', texto: 'Se detuvo antes de terminar. Prueba de nuevo; si se repite, avisa en la lista de pendientes.' };
  if (job.estado === 'tope_salida') return { clave: 'aviso', icono: 'alerta', titulo: 'Se cortó la salida', texto: 'Produjo más texto del que el panel muestra. Corre el comando a mano para verlo completo.' };
  if (job.codigo === 0) return { clave: 'ok', icono: 'ok', titulo: 'Salió bien', texto: def.bien || 'Terminó sin problemas.' };
  if (job.codigo === null) return { clave: 'aviso', icono: 'info', titulo: 'Terminó', texto: 'El servidor no informó cómo salió. Mira el detalle de abajo.' };
  return { clave: 'error', icono: 'alerta', titulo: 'Encontró problemas', texto: 'Algo no pasó la revisión. Abajo, en el detalle técnico, está el mensaje que dice qué falló.' };
}

// ───────────────────────── evaluación ─────────────────────────

function normalizarBase(b) {
  if (!esObj(b) || !CLAVES_ESTADO.includes(b.clave)) return null;
  return { clave: b.clave, evidencia: corto(b.evidencia, 400) || null, detalle: b.detalle ? corto(b.detalle, 300) : null, alerta: b.alerta ? corto(b.alerta, 300) : null, origen: b.origen || 'datos' };
}

/**
 * Evalúa todo el catálogo. Devuelve {tareas, momentos, resumen, siguiente, oferta}.
 *  · lecturas: ver cabecera. · oferta: {id, demo, lectura:{ok, datos}} (la que mira el momento 1) o null. · marcas: {idTarea: ISO}. · ahora: ms. · fmt: {dinero, relativo}.
 */
export function evaluarTareas(lecturas = {}, { oferta = null, marcas = {}, ahora = Date.now(), fmt = FMT_BASICO } = {}) {
  const c = { lec: esObj(lecturas) ? lecturas : {}, oferta: normalizarOferta(oferta), marcas: esObj(marcas) ? marcas : {}, ahora, fmt: fmt || FMT_BASICO };
  const porId = new Map(CATALOGO.map((t) => [t.id, t]));
  const memo = new Map();

  function estadoDe(id, pila = []) {
    if (memo.has(id)) return memo.get(id);
    const t = porId.get(id);
    if (!t) return { clave: 'pendiente', evidencia: null, origen: 'datos' };
    if (pila.includes(id)) return { clave: 'pendiente', evidencia: null, origen: 'datos' }; // ciclo: defensa
    let base = null;
    try { base = normalizarBase(t.comprobar ? t.comprobar(c) : null); } catch (_) { base = { clave: 'no_comprobable', evidencia: 'No se pudo comprobar: los datos llegaron en un formato inesperado.', detalle: null, alerta: null, origen: 'sin_datos' }; }
    if (!base) {
      const k = CONSTRUCCION[id];
      base = k
        ? { clave: 'no_existe', evidencia: k.falta, detalle: null, alerta: null, origen: 'plan' }
        : { clave: 'no_comprobable', evidencia: t.sinDato || 'El panel no tiene de dónde leer si esto ya está hecho.', detalle: null, alerta: null, origen: 'sin_datos' };
    }
    const est = { ...base, marcable: false, marcadaEn: null, bloqueadaPor: [] };
    if (est.clave === 'no_comprobable') {
      const m = c.marcas[id];
      if (m && marcaVigente(m, t.periodo || 'unica', c.ahora)) {
        est.clave = 'hecha'; est.origen = 'marca'; est.marcadaEn = m; est.marcable = true;
        est.evidencia = 'La marcaste tú como hecha. Es una marca solo tuya: no cambia el sistema.';
      } else est.marcable = true;
    }
    if ((est.clave === 'pendiente' || est.clave === 'no_comprobable') && t.depende && t.depende.length) {
      const faltan = t.depende.map((d) => ({ d, e: estadoDe(d, [...pila, id]) })).filter((x) => x.e.clave !== 'hecha');
      if (faltan.length) {
        est.bloqueadaPor = faltan.map((x) => ({ id: x.d, titulo: porId.get(x.d) ? porId.get(x.d).titulo : x.d }));
        est.clave = 'bloqueada'; est.origen = 'dependencia'; est.marcable = false;
        est.evidencia = `Primero hay que terminar: ${est.bloqueadaPor.map((b) => `«${b.titulo}»`).join(' y ')}.`;
      }
    }
    memo.set(id, est);
    return est;
  }

  const tareas = CATALOGO.map((t) => {
    const estado = estadoDe(t.id);
    const demo = Boolean(t.porOferta && c.oferta.hay && c.oferta.demo);
    let pasos = [];
    try { pasos = lista(t.pasos ? t.pasos(c, estado) : []); } catch (_) { pasos = []; }
    return {
      id: t.id, momento: t.momento, orden: t.orden, titulo: t.titulo, porQue: t.porQue, quien: t.quien, periodo: t.periodo || 'unica', cuando: t.cuando || null, ruta: t.ruta || null,
      porOferta: Boolean(t.porOferta), terminos: lista(t.terminos), avisoPlan: t.avisoPlan || null,
      hoyObjetivo: t.hoyObjetivo ? (() => { try { return t.hoyObjetivo(c); } catch (_) { return null; } })() : null,
      estado, demo, cuenta: !demo, pasos, donde: lista(t.donde), tecnico: lista(t.tecnico),
      acciones: lista(t.acciones),
      leToca: (t.quien === 'dueno' || estado.clave === 'espera_firma') && ['pendiente', 'en_curso', 'espera_firma', 'no_comprobable'].includes(estado.clave),
    };
  });

  const momentos = MOMENTOS.map((m) => {
    const ts = tareas.filter((t) => t.momento === m.id);
    return { ...m, tareas: ts, conteo: contar(ts), demo: ts.some((t) => t.demo) };
  });
  return { tareas, momentos, resumen: resumenTareas(tareas), siguiente: siguientePaso(tareas), oferta: c.oferta };
}

function contar(ts) {
  const porEstado = Object.fromEntries(CLAVES_ESTADO.map((k) => [k, 0]));
  for (const t of ts) porEstado[t.estado.clave] += 1;
  return { total: ts.length, hechas: porEstado.hecha, porEstado };
}

/** Totales para «X de Y hechas». La demo no cuenta; las marcadas por ti sí, pero se muestran aparte. */
export function resumenTareas(tareas) {
  const l = lista(tareas);
  const cuentan = l.filter((t) => t.cuenta);
  const hechas = cuentan.filter((t) => t.estado.clave === 'hecha');
  const porMarca = hechas.filter((t) => t.estado.origen === 'marca').length;
  const total = cuentan.length;
  return {
    total, hechas: hechas.length, porMarca, porComprobacion: hechas.length - porMarca, noCuentan: l.length - cuentan.length,
    porcentaje: total ? Math.round((hechas.length / total) * 100) : 0,
    tuyas: cuentan.filter((t) => t.quien === 'dueno').length, tuyasHechas: cuentan.filter((t) => t.quien === 'dueno' && t.estado.clave === 'hecha').length,
    noExisten: cuentan.filter((t) => t.estado.clave === 'no_existe').length,
  };
}

/** La primera tarea (en el orden del negocio) que te toca a ti y se puede hacer ahora. La demo nunca cuenta. */
export function siguientePaso(tareas) {
  return lista(tareas).find((t) => t.leToca && t.cuenta) || null;
}

// ───────────────────────── filtros y orden ─────────────────────────

/** Filtra por quién la hace, por estado (clave, «todos» o «para_hacer») y por texto (sin tildes ni mayúsculas, todas las palabras). Conserva el orden. */
export function filtrarTareas(tareas, f = FILTROS_VACIOS) {
  const quien = CLAVES_QUIEN.includes(f.quien) ? f.quien : 'todas';
  const estado = f.estado === 'para_hacer' || CLAVES_ESTADO.includes(f.estado) ? f.estado : 'todos';
  const palabras = quitarTildes(f.texto || '').split(/\s+/).filter(Boolean);
  return lista(tareas).filter((t) => {
    if (quien !== 'todas' && t.quien !== quien) return false;
    if (estado === 'para_hacer' && !ESTADOS_PARA_HACER.includes(t.estado.clave)) return false;
    if (estado !== 'todos' && estado !== 'para_hacer' && t.estado.clave !== estado) return false;
    if (palabras.length) {
      const pajar = quitarTildes([t.titulo, t.porQue, t.estado.evidencia || '', QUIENES[t.quien].texto, ESTADOS[t.estado.clave].texto, t.cuando || '', MOMENTOS[t.momento].titulo].join(' '));
      return palabras.every((p) => pajar.includes(p));
    }
    return true;
  });
}

/** Agrupa tareas (ya filtradas) por momento, en orden, sin momentos vacíos. */
export function agruparPorMomento(tareas) {
  return MOMENTOS.map((m) => ({ ...m, tareas: lista(tareas).filter((t) => t.momento === m.id) })).filter((m) => m.tareas.length);
}

/** Opciones del filtro de estado, en orden de lectura. */
export const OPCIONES_ESTADO = [
  { valor: 'todos', texto: 'Todos los estados' }, { valor: 'para_hacer', texto: 'Para hacer' },
  ...CLAVES_ESTADO.map((k) => ({ valor: k, texto: ESTADOS[k].texto })),
];
export const OPCIONES_QUIEN = [{ valor: 'todas', texto: 'Todas' }, ...CLAVES_QUIEN.map((k) => ({ valor: k, texto: QUIENES[k].texto }))];

/** Fecha corta para «la marcaste el …» (sin dependencias). */
export function fechaCorta(iso) {
  const t = alMs(iso);
  if (t === null) return '';
  const d = new Date(t);
  return `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`;
}
