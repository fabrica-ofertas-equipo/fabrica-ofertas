// pages/campanas.js — #/campanas: la campaña de test de la oferta activa (D7: Meta Ads).
// Ciclo borrador → preflight OK → aprobada → activa como pasos; siguiente paso con sus bloqueos; preflight P01–P25 como cuadrícula de
// semáforos por grupo; detalle de campana.json legible (URL con macros resaltadas, presupuesto, anuncios, reglas de parada) con el JSON
// crudo en «detalle técnico»; aprobación pendiente con el comando de firma (se copia; el panel NO firma).
//
// SOLO LECTURA. Sin botones que activen, publiquen o gasten: el panel nunca firma ni llama a Meta. Lo único que ofrece son comandos
// para copiar y ejecutar en la terminal del dueño. Todo texto de los archivos pasa por textContent (lib/campanas.js lo neutraliza).

import * as C from '../lib/campanas.js';
import { RE_OFERTA_ID, RE_OFERTA_REAL } from '../lib/landing.js';
import { CSS_COMUN, CSS_CAMPANAS } from '../lib/estilos-u3.js';

export const meta = { ruta: 'campanas', titulo: 'Campañas', grupo: 'Testeo y escala', icono: 'diana', escucha: ['oferta'] };

let U = null;
let el; let chip; let seccion; let tabla; let tabs; let kv; let errorBox; let comando; let reemplazar; let visorJson;
let fmt = null;

function usar(ctx) {
  U = ctx.ui;
  ({ el, chip, seccion, tabla, tabs, kv, errorBox, comando, reemplazar, visorJson } = U);
  fmt = ctx.fmt || U.fmt;
  if (U.instalarEstilos) { U.instalarEstilos('u3-comun', CSS_COMUN); U.instalarEstilos('u3-campanas', CSS_CAMPANAS); }
}

const vista = { tab: 'preflight' };
let activo = null; // {ctx, raiz, ofertaId}
let enRefresco = false;

const ic = (nombre, tam = 16) => U.icono(nombre, { tam, tamano: tam });
const pila = (...hijos) => el('div', { class: 'u3-pila' }, ...hijos);
const t = (v) => (v === null || v === undefined || v === '' ? '—' : String(v));
const tag = (texto, variante, { titulo, icono } = {}) => el('span', { class: ['u3-tag', variante && `u3-tag--${variante}`], title: titulo || null }, icono ? ic(icono, 12) : null, texto);
const tecnico = (titulo, ...contenido) => U.detalleTecnico(titulo, contenido.flat().filter(Boolean));

function nota(contenido, { tono = 'info', icono = 'info' } = {}) {
  return el('div', { class: ['u3-nota', tono !== 'info' && `u3-nota--${tono}`], role: tono === 'error' ? 'alert' : 'note' }, ic(icono, 18), el('div', null, contenido));
}

async function leer(ctx, ruta, params) {
  try {
    const s = await ctx.api.sobre(ruta, params);
    return { ok: true, datos: s.datos, fuente: s.fuente || [], generado_en: s.generado_en || null, vacio: s.vacio === true, avisos: s.avisos || [], error: null };
  } catch (error) {
    return { ok: false, datos: null, fuente: [], generado_en: null, vacio: false, avisos: [], error };
  }
}

// ───────────────────────── render ─────────────────────────

export async function render(ctx) {
  usar(ctx);
  const raiz = el('div', { class: 'pagina' }, U.esqueleto ? U.esqueleto('pagina') : U.cargando('Leyendo la información de la campaña…'));
  activo = { ctx, raiz, ofertaId: null };
  await construir(ctx, raiz);
  return raiz;
}

export function alSalir() { activo = null; }

export function alCambio(ctx, ev) {
  if (!activo || enRefresco) return undefined;
  const lote = (ev && ev.lote) || (ev ? [ev] : []);
  const id = activo.ofertaId;
  const propios = lote.filter((e) => e && e.tipo !== 'sondeo' && (typeof e.ruta !== 'string' || e.ruta === '' || !id || e.ruta.includes(id)));
  if (!propios.length) return undefined;
  enRefresco = true;
  construir(activo.ctx, activo.raiz).catch((e) => console.error('refresco de campañas falló', e)).finally(() => { enRefresco = false; });
  return undefined;
}

function cabecera(id) {
  return U.encabezadoPagina({
    titulo: 'Campañas',
    descripcion: 'La campaña de prueba de la oferta activa: en qué punto del ciclo va, qué la bloquea y qué falta para activarla. El panel no activa, no publica y no gasta.',
    acciones: id ? [tag(id, 'acento', { titulo: 'Oferta activa' })] : [],
  });
}

async function construir(ctx, raiz) {
  const lista = ctx.estado && Array.isArray(ctx.estado.ofertas) ? ctx.estado.ofertas : [];
  const activa = ctx.estado ? ctx.estado.ofertaActiva : null;
  if (typeof activa !== 'string' || !RE_OFERTA_ID.test(activa)) {
    activo.ofertaId = null;
    const botones = lista.filter((o) => o && RE_OFERTA_ID.test(String(o.oferta_id))).slice(0, 12).map((o) => el('button', {
      type: 'button', class: 'btn btn--chico', onclick: () => ctx.estado.fijar({ ofertaActiva: o.oferta_id }),
    }, o.oferta_id + (o.demo ? ' (demostración)' : '')));
    reemplazar(raiz, cabecera(null),
      U.vacioConPasos({
        titulo: activa ? `La oferta activa «${String(activa).slice(0, 40)}» no es un código de oferta válido` : 'No hay una oferta activa',
        explicacion: 'Aquí se ve la campaña de prueba de una oferta: su ciclo, su chequeo antes de lanzar y su aprobación.',
        pasos: [{ texto: 'Elige una oferta en el selector de la barra superior' + (activa ? ' (el código de la oferta debe tener la forma OF-AAAAMM-NN).' : '.') }], icono: 'diana',
      }),
      botones.length ? el('div', { class: 'u3-fila' }, el('span', { class: 'u3-tenue' }, 'Ofertas disponibles:'), botones) : null);
    return;
  }
  const id = activa;
  activo.ofertaId = id;
  const [rc, det] = await Promise.all([leer(ctx, `/campanas/${id}`), leer(ctx, `/oferta/${id}`)]);
  if (!rc.ok) {
    reemplazar(raiz, cabecera(id), errorBox(rc.error, { reintentar: () => ctx.recargar() }));
    return;
  }
  const ahora = Date.now();
  const modelo = C.modeloCampanas(rc.datos, { ofertaId: id, ahora });
  const etapas = det.ok && det.datos && Array.isArray(det.datos.etapas) ? det.datos.etapas : [];
  // id real de la oferta (el que entiende engine.orq): el de estado.json que informa el panel, o el de campana.json
  const entrada = lista.find((o) => o && o.oferta_id === id) || null;
  const real = [entrada && entrada.oferta_id_estado, rc.datos && rc.datos.campana && rc.datos.campana.oferta_id, id].find((x) => typeof x === 'string' && RE_OFERTA_REAL.test(x)) || null;
  const d = { ctx, id, rc, det, modelo, etapas, ahora, bruto: rc.datos, real };
  if (!modelo.hayCampana) {
    reemplazar(raiz, cabecera(id), vacioSinCampana(d), pie(d));
    return;
  }
  reemplazar(raiz, cabecera(id), cicloYSiguiente(d), metricas(d), montarTabs(d), pie(d));
}

function pie(d) {
  const fuentes = [...(d.rc.fuente || [])];
  if (d.det.ok) for (const f of d.det.fuente || []) if (!fuentes.includes(f)) fuentes.push(f);
  if (!fuentes.length) fuentes.push(`ofertas/${d.id}/07-campana/`);
  return U.fuente(fuentes.slice(0, 10), { leido: d.rc.generado_en || undefined });
}

// ───────────────────────── sin campaña ─────────────────────────

function vacioSinCampana(d) {
  const etapa = (i) => d.etapas.find((e) => e && e.id === i) || null;
  const filas = [['D5', 'Página de venta, pago y medición'], ['D6', 'Anuncios'], ['D7', 'Campaña de prueba']].map(([i, n]) => {
    const e = etapa(i);
    return el('div', { class: 'u3-item', style: { gridTemplateColumns: 'minmax(0, 1fr) auto' } }, el('span', null, el('strong', null, n), el('span', { class: 'u3-tenue' }, ` · ${i}`)), e && e.estado ? U.estadoIcono(e.estado) : tag(d.det.ok ? 'sin iniciar' : 'sin dato', null));
  });
  return pila(
    U.vacioConPasos({
      titulo: `La oferta ${d.id} aún no tiene campaña armada`,
      explicacion: 'La campaña la arma la etapa de campañas cuando la página de venta y los anuncios (creativos) están aprobados: calcula el presupuesto a partir de la economía de la oferta, elige cómo se arma la campaña y qué evento optimiza, y deja el borrador en pausa. Este panel no la crea.',
      pasos: [
        { texto: 'Termina y aprueba la página de venta y los anuncios (mira su estado abajo).' },
        d.real ? { texto: 'Mira en qué punto va la oferta con este comando:', comando: `.venv/bin/python -m engine.orq estado --oferta ${d.real}` } : { texto: 'Cuando exista la campaña, aparecerá aquí.' },
      ],
      icono: 'diana',
    }),
    seccion('Requisitos: estado de las etapas previas', el('div', { class: 'u3-lista' }, filas), { ayuda: d.det.ok ? 'Salen del estado de la oferta.' : 'No se pudo leer el estado de la oferta.' }));
}

// ───────────────────────── ciclo, siguiente paso, firma ─────────────────────────

function cicloYSiguiente(d) {
  const { ciclo, paso, firma: f, aprobacion: ap, preflight: pf } = d.modelo;
  const idxActual = ciclo.pasos.findIndex((p) => p.estado === 'actual');
  const siguienteIdx = idxActual >= 0 && idxActual < ciclo.pasos.length - 1 ? idxActual + 1 : (idxActual === -1 && ciclo.conocido ? -1 : 0);
  const etapas = ciclo.pasos.map((p, i) => ({
    id: p.id, nombre: p.texto,
    estado: p.estado === 'pendiente' ? 'pendiente' : 'terminado',
    seleccionada: p.estado === 'actual',
    // el paso que espera una acción humana (la firma) se destaca con el acento
    destacada: i === siguienteIdx && p.id === 'aprobada' && f.pendiente,
  }));
  const e7 = d.modelo.etapaD7;
  const puedeFirmar = f.pendiente && f.comando && pf && pf.habilita;
  return el('section', { class: 'u3-tarjeta u3-siguiente', 'aria-label': 'Ciclo y siguiente paso' },
    el('div', { class: 'u3-fila u3-fila--entre' },
      el('p', { class: 'u3-sobretitulo' }, 'Ciclo de la campaña ', U.termino('ciclo_campana', { texto: 'qué es' })),
      el('div', { class: 'u3-fila' },
        ciclo.fueraDeCiclo ? tag(ciclo.fueraDeCiclo === 'cerrada' ? 'Cerrada' : 'Pausada', ciclo.fueraDeCiclo === 'cerrada' ? null : 'aviso') : null,
        e7 && e7.estado ? el('span', { class: 'u3-fila', title: 'Estado de la etapa de campañas en el estado de la oferta' }, el('span', { class: 'u3-tenue u3-peq' }, 'Etapa D7:'), U.estadoIcono(e7.estado)) : null,
        e7 && e7.gatePendiente === true ? tag('Espera tu firma', 'acento') : null,
        !ciclo.conocido ? tag(`estado desconocido: ${t(ciclo.actual)}`, 'error') : null)),
    U.pasos({ etapas, etiqueta: 'Ciclo de la campaña' }),
    el('div', { class: 'u3-pila u3-pila--chica' },
      el('p', { class: 'u3-sobretitulo' }, 'Siguiente paso'),
      el('p', { class: 'u3-siguiente__texto' }, paso.texto),
      paso.bloqueos.length ? el('div', { class: 'u3-pila u3-pila--chica' }, el('div', { class: 'u3-tenue u3-peq' }, 'Lo que lo bloquea ahora:'), el('ul', { class: 'u3-bloqueos' }, paso.bloqueos.map((b) => el('li', null, ic('alerta', 16), el('span', null, b))))) : null),
    ...d.modelo.avisos.map((a) => nota(el('p', null, a), { tono: 'error', icono: 'octogono' })),
    bloqueFirma(d, { puedeFirmar, ap }));
}

function bloqueFirma(d, { puedeFirmar, ap }) {
  const f = d.modelo.firma;
  if (ap && ap.valida) {
    return nota(el('p', null, el('strong', null, 'Aprobación firmada y vigente. '), `Firmó ${ap.aprobadoPor.tipo === 'humano' ? 'una persona' : t(ap.aprobadoPor.tipo)} (${t(ap.aprobadoPor.id)}; vale hasta ${fmt.fecha(ap.vigenciaHasta)}). La activación la hace el sistema automático, no este panel.`), { tono: 'ok', icono: 'ok' });
  }
  if (!f.pendiente) return null;
  return el('div', { class: 'u3-firma' },
    ap && ap.problemas.length ? nota(el('p', null, el('strong', null, 'La aprobación existente no es válida: hay que firmar de nuevo. '), ap.problemas.join(' ')), { tono: 'error', icono: 'octogono' }) : null,
    nota(el('p', null, el('strong', null, ap ? 'Hay que firmar de nuevo. ' : 'Aprobación pendiente: la activación requiere tu firma. '),
      'La haces tú, en tu terminal, solo cuando el chequeo antes de lanzar esté verde y vigente. Ninguna IA ni este panel puede firmar por ti (', U.termino('gate_h', { texto: 'qué es esta firma' }), ').'), { tono: puedeFirmar ? 'info' : 'neutra', icono: 'firma' }),
    f.comando
      ? comando(f.comando, { titulo: 'Cómo firmar la activación', abierto: Boolean(puedeFirmar), nota: 'Estás firmando la huella exacta de la configuración que ves abajo. Lo ejecutas tú en la terminal; el panel no firma, no activa y no gasta.' })
      : el('p', { class: 'u3-tenue' }, 'No se puede armar el comando: el código de la oferta no es el real (OF-AAAAMM-NN).'),
    tecnico('Qué estás firmando',
      kv([
        [U.termino('hash_config', { texto: 'Huella de la configuración' }), f.hashObjetivo ? el('code', null, f.hashObjetivo) : null],
        ['Objetos de Meta que se activarían', f.objectIds.length ? el('span', { class: 'u3-tags' }, f.objectIds.map((x) => el('code', null, x))) : 'aún no existen: no hay borrador en Meta'],
      ]),
      el('p', { class: 'u3-tenue u3-peq' }, f.nota)));
}

// ───────────────────────── métricas ─────────────────────────

function metricas(d) {
  const m = d.modelo;
  const c = m.campana;
  const p = m.preflight;
  const ids = m.idsMeta;
  const ap = m.aprobacion;
  const pres = c.presupuesto;
  const estado = U.infoEstado(c.estado).texto;
  return el('div', { class: 'u3-metricas' },
    U.metrica({ etiqueta: 'Estado de la campaña', valor: estado, contexto: [c.fase, c.estructuraTexto.texto, c.objetivo && c.evento ? `${c.objetivo} → ${c.evento}` : null].filter(Boolean).join(' · ') || undefined, tono: c.estado === 'activa' ? 'ok' : undefined }),
    U.metrica({
      etiqueta: 'Chequeo antes de lanzar', valor: p ? (p.habilita ? 'En verde y vigente' : p.semaforo === 'VERDE' ? 'Verde, pero no vale' : ({ VERDE: 'Verde', AMARILLO: 'Amarillo', ROJO: 'Rojo' }[p.semaforo] || 'Sin semáforo')) : 'Sin chequeo',
      contexto: p ? `${p.resumen.verde} en verde · ${p.resumen.amarillo} amarillo · ${p.resumen.rojo} rojo${p.resumen.sinDato ? ` · ${p.resumen.sinDato} sin dato` : ''}` : 'todavía no existe el chequeo',
      tono: p ? (p.habilita ? 'ok' : p.tono === 'error' ? 'grave' : 'aviso') : 'aviso', ayuda: 'preflight',
    }),
    U.metrica({ etiqueta: 'Vigencia del chequeo', valor: p ? (p.vigente === true ? 'Vigente' : p.vigente === false ? 'Vencido' : 'Sin fecha') : '—', contexto: p && p.validoHasta ? `hasta ${fmt.fecha(p.validoHasta)} (${fmt.relativo(p.validoHasta)})` : 'se repite si cambia algo o pasan 24 h', tono: p ? (p.vigente === true ? 'ok' : p.vigente === false ? 'grave' : 'aviso') : undefined }),
    U.metrica({ etiqueta: 'Gasto máximo de la prueba', valor: pres ? pres.total : '—', contexto: pres ? `${pres.diario} por día · ${t(pres.dias)} días · tope teórico ${pres.maxTeoricoDiario} por día` : 'sin presupuesto' }),
    U.metrica({ etiqueta: 'Borrador en Meta', valor: ids ? 'Creado' : 'Sin crear', contexto: ids ? `${ids.objetosActivables} objetos que se activarían` : 'todo se crea en pausa', tono: ids ? (ids.hashCoincide === false ? 'grave' : 'ok') : undefined, ayuda: 'ids_meta' }),
    U.metrica({ etiqueta: 'Tu firma', valor: ap ? (ap.valida ? 'Firmada' : 'No válida') : 'Pendiente', contexto: ap ? `aprobó ${ap.aprobadoPor.tipo === 'humano' ? 'una persona' : t(ap.aprobadoPor.tipo)}` : 'sin aprobación firmada', tono: ap ? (ap.valida ? 'ok' : 'grave') : 'acento', ayuda: 'gate_h' }));
}

// ───────────────────────── pestañas ─────────────────────────

function montarTabs(d) {
  const items = [
    { id: 'preflight', titulo: 'Chequeo antes de lanzar', render: () => tabPreflight(d) },
    { id: 'campana', titulo: 'Campaña', render: () => tabCampana(d) },
    { id: 'meta', titulo: 'Meta y aprobación', render: () => tabMeta(d) },
  ];
  const activa = items.some((i) => i.id === vista.tab) ? vista.tab : 'preflight';
  const tb = tabs(items, activa);
  const sincronizar = () => setTimeout(() => { const x = tb.activo && tb.activo(); if (x) vista.tab = x; }, 0);
  tb.addEventListener('click', sincronizar);
  tb.addEventListener('keydown', sincronizar);
  return tb;
}

const SEMAFORO = {
  VERDE: { icono: 'ok', texto: 'Verde', tono: 'ok' },
  AMARILLO: { icono: 'alerta', texto: 'Amarillo', tono: 'aviso' },
  ROJO: { icono: 'octogono', texto: 'Rojo', tono: 'error' },
  NO_APLICA: { icono: 'menos', texto: 'No aplica', tono: 'neutro' },
  sin_dato: { icono: 'circulo', texto: 'Sin dato', tono: 'neutro' },
};

function tabPreflight(d) {
  const p = d.modelo.preflight;
  if (!p) {
    return U.vacioConPasos({
      titulo: 'Esta campaña aún no tiene el chequeo antes de lanzar',
      explicacion: 'El chequeo revisa 25 puntos (P01–P25; el P25 solo si hay categorías especiales) leyendo datos de Meta, sin cambiar nada allí, y deja firmada la huella de la configuración. Es obligatorio y vale 24 horas: sin uno verde y vigente para esta configuración no se puede activar.',
      pasos: [{ texto: 'Hazlo con este comando en tu terminal (solo lee datos de Meta; no cambia nada):', comando: C.comandoPreflight(d.id) || undefined }], icono: 'lista',
    });
  }
  const grupos = C.agruparPreflight(p.filas);
  const resumen = [['VERDE', p.resumen.verde], ['AMARILLO', p.resumen.amarillo], ['ROJO', p.resumen.rojo], ['sin_dato', p.resumen.sinDato], ['NO_APLICA', p.resumen.noAplica]].filter(([, n]) => n > 0);
  return pila(
    p.problemas.length ? nota(el('p', null, el('strong', null, 'No habilita la activación: '), p.problemas.join(' ')), { tono: 'error', icono: 'octogono' }) : null,
    el('div', { class: 'u3-fila u3-fila--entre' },
      el('div', { class: 'u3-fila', role: 'group', 'aria-label': 'Resumen del chequeo antes de lanzar' }, resumen.map(([e, n]) => el('span', { class: ['u3-estado', `u3-estado--${SEMAFORO[e].tono}`] }, ic(SEMAFORO[e].icono, 18), el('b', null, String(n)), SEMAFORO[e].texto.toLowerCase()))),
      el('div', { class: 'u3-fila' },
        tag(p.vigente === true ? 'vigente' : p.vigente === false ? 'vencido' : 'vigencia desconocida', p.vigente === true ? 'ok' : p.vigente === false ? 'error' : 'aviso', { icono: p.vigente === true ? 'ok' : p.vigente === false ? 'octogono' : 'alerta' }),
        tag(p.hashCoincide === true ? 'misma configuración que la campaña' : p.hashCoincide === false ? 'de otra versión de la campaña' : 'configuración no comparable', p.hashCoincide === true ? 'ok' : p.hashCoincide === false ? 'error' : null, { icono: p.hashCoincide === false ? 'octogono' : p.hashCoincide === true ? 'ok' : undefined }),
        p.generadoEn ? el('span', { class: 'u3-tenue u3-peq', title: fmt.fecha(p.generadoEn) }, `generado ${fmt.relativo(p.generadoEn)}`) : null)),
    el('div', { class: 'u3-grupos' }, grupos.map((g) => el('section', { 'aria-label': g.titulo },
      el('div', { class: 'u3-grupo__cab' }, el('h3', { class: 'u3-titulo u3-titulo--chico' }, g.titulo),
        el('span', { class: 'u3-tenue u3-peq' }, `${g.resumen.verde} de ${g.resumen.total} en verde${g.resumen.rojo ? ` · ${g.resumen.rojo} en rojo` : ''}${g.resumen.amarillo ? ` · ${g.resumen.amarillo} en amarillo` : ''}${g.resumen.sinDato ? ` · ${g.resumen.sinDato} sin dato` : ''}`)),
      el('div', { class: 'u3-semaforos' }, g.filas.map((f) => {
        const s = SEMAFORO[f.estado] || SEMAFORO.sin_dato;
        return el('div', { class: ['u3-sema', `u3-sema--${f.estado}`], title: f.titulo },
          el('span', { class: 'u3-sema__icono', role: 'img', 'aria-label': s.texto }, ic(s.icono, 20)),
          el('div', { class: 'u3-sema__titulo' }, el('span', { class: 'u3-sema__id' }, f.id), f.nombre, f.condicional ? el('span', { class: 'u3-tenue', title: 'obligatorio solo si la campaña tiene categorías especiales de anuncios' }, ' *') : null),
          f.estado !== 'VERDE' ? el('div', { class: 'u3-sema__evidencia' }, `${s.texto}${f.evidencia ? ` · ${f.evidencia}` : (f.estado === 'sin_dato' ? ' · el archivo no trae este punto' : '')}`) : (f.evidencia ? el('div', { class: 'u3-sema__evidencia' }, f.evidencia) : null));
      })))),
    ),
    nota(el('p', null, 'Cualquier punto en rojo bloquea; uno sin dato también. El punto marcado con * (P25) es obligatorio solo con categorías especiales. ', U.termino('preflight', { texto: 'Qué es el chequeo antes de lanzar' }), '.'), { tono: 'neutra' }),
    comando(C.comandoPreflight(d.id) || '', { titulo: 'Cómo hacerlo: repetir el chequeo', nota: 'Solo lee datos de Meta; no cambia nada. Lo ejecutas tú en la terminal.' }),
    tecnico('Detalle técnico del chequeo', kv([
      [U.termino('hash_config', { texto: 'Huella de la configuración' }), p.hashConfig ? el('code', { title: p.hashConfig }, C.hashCorto(p.hashConfig)) : null],
      ['Generado', p.generadoEn ? `${fmt.fecha(p.generadoEn)} (${p.horasGenerado} h)` : null], ['Válido hasta', p.validoHasta ? fmt.fecha(p.validoHasta) : null],
      ['Extensiones PX1–PX4', 'DSA, tarifa de ubicación, riesgo y términos sensibles: no caben en el formato esperado 1.0.0; se evalúan en meta.preflight y quedan en lanzamiento.log'],
      ['Modo', p.nota],
    ]),
    tabla({
      etiqueta: 'Los 25 puntos del chequeo', filas: p.filas, maxFilas: 30,
      columnas: [
        { clave: 'id', titulo: 'Id', ancho: '56px', formato: (v) => el('code', null, v) },
        { clave: 'titulo', titulo: 'Comprobación (nombre técnico)', clase: 'cel-larga' },
        { clave: 'estado', titulo: 'Semáforo', formato: (v, r) => chip((SEMAFORO[v] || SEMAFORO.sin_dato).texto, r.tono) },
        { clave: 'ambito', titulo: 'Ámbito', formato: (v) => el('span', { class: 'u3-tenue' }, v) },
        { clave: 'evidencia', titulo: 'Evidencia', clase: 'cel-larga', formato: (v) => (v || el('span', { class: 'u3-tenue' }, 'sin evidencia')) },
      ],
    })));
}

function bloqueUrl(url) {
  return pila(
    el('div', { class: 'u3-fila' },
      tag(url.macrosOk ? 'los 6 marcadores (macros) presentes' : `faltan marcadores: ${url.macrosFaltan.join(' ')}`, url.macrosOk ? 'ok' : 'error', { icono: url.macrosOk ? 'ok' : 'octogono' }),
      url.ejemploOk === null ? tag('sin ejemplo completado', null) : tag(url.ejemploOk ? 'el ejemplo completado no tiene huecos' : 'el ejemplo tiene huecos o llaves sin completar', url.ejemploOk ? 'ok' : 'error', { icono: url.ejemploOk ? 'ok' : 'octogono' }),
      url.https === false ? tag('no usa conexión segura (https)', 'error', { icono: 'octogono' }) : null,
      U.termino('macros_url', { texto: 'Qué son los marcadores (macros)' })),
    el('div', { class: 'u3-url', 'aria-label': 'Dirección del anuncio con los marcadores resaltados' }, url.trozos.length ? url.trozos.map((x) => (x.macro ? el('mark', null, x.texto) : el('span', null, x.texto))) : el('span', { class: 'u3-tenue' }, 'sin dirección')),
    url.ejemplo ? el('div', { class: 'u3-pila u3-pila--chica' }, el('div', { class: 'u3-tenue u3-peq' }, 'Ejemplo completado (cómo se vería ya en un anuncio)'), el('div', { class: 'u3-url' }, url.ejemplo)) : null);
}

function tabCampana(d) {
  const c = d.modelo.campana;
  const pres = c.presupuesto;
  const marca = { ok: 'ok', aviso: 'aviso', error: 'octogono' };
  return pila(
    seccion('Qué hace la campaña', kv([
      ['Objetivo', c.objetivo], ['Evento que optimiza', c.evento], ['Estructura', c.estructuraTexto.sigla === 'CBO' ? U.termino('campana_cbo', { texto: `${c.estructuraTexto.texto} (CBO)` }) : c.estructuraTexto.texto], ['Fase', c.fase],
      ['Países', c.paises.length ? el('span', { class: 'u3-tags' }, c.paises.map((x) => tag(x, 'mono'))) : null], ['Idioma', c.idioma], ['Ubicaciones', c.ubicaciones],
      ['Audiencia', c.audiencia ? `${c.audiencia.tipo} · ${t(c.audiencia.edad)} años · género ${c.audiencia.genero} · ${c.audiencia.intereses} intereses · ${c.audiencia.excluyeSensibles ? 'excluye categorías sensibles' : 'NO excluye categorías sensibles'}` : null],
      ['Categorías especiales', c.specialAdCategories.length ? el('span', { class: 'u3-tags' }, c.specialAdCategories.map((x) => tag(x, 'aviso'))) : 'ninguna'],
      ['Atribución', c.atribucion.length ? c.atribucion.map(([k, v]) => `${k}: ${v}`).join(' · ') : null],
    ])),
    seccion('Dirección del anuncio', bloqueUrl(c.url), { ayuda: 'Los marcadores (macros) los rellena Meta al mostrar el anuncio; el código del anuncio en la dirección es lo que une cada compra con su anuncio.' }),
    seccion('Presupuesto', pres ? pila(
      el('div', { class: 'u3-presupuesto' },
        U.metrica({ etiqueta: 'Por día', valor: pres.diario }), U.metrica({ etiqueta: 'Total de la prueba', valor: pres.total, contexto: `${t(pres.dias)} días` }),
        U.metrica({ etiqueta: 'Tope de gasto', valor: pres.spendCap, contexto: pres.spendCapMinimo !== 'sin dato' ? `mínimo de Meta ${pres.spendCapMinimo}` : undefined, ayuda: 'spend_cap' }), U.metrica({ etiqueta: 'Tope teórico por día', valor: pres.maxTeoricoDiario })),
      pres.comprobaciones.length ? el('div', { class: 'u3-lista' }, pres.comprobaciones.map((x) => el('div', { class: 'u3-item' },
        el('span', { class: ['u3-item__icono', 'u3-estado', `u3-estado--${x.estado}`] }, ic(marca[x.estado] || 'info', 18)),
        el('div', null, el('div', { class: 'u3-item__titulo' }, x.texto), x.nota ? el('div', { class: 'u3-item__detalle', style: { gridColumn: 'auto' } }, x.nota) : null),
        el('div', { class: 'u3-item__lado' }, tag(x.estado === 'ok' ? 'coherente' : x.estado === 'aviso' ? 'revisar' : 'incoherente', x.estado === 'ok' ? 'ok' : x.estado === 'aviso' ? 'aviso' : 'error'))))) : null,
      pres.candado ? el('div', { class: 'u3-tenue u3-peq' }, U.termino('candado_alternativo', { texto: 'Freno alternativo' }), `: ${pres.candado.map(([k, v]) => `${k}: ${v}`).join(' · ')}`) : null,
      el('p', { class: 'u3-tenue u3-peq' }, 'Cuentas simples que hace el panel (con números enteros). Los límites reales, con el margen que aplica Meta, los comprueba el chequeo antes de lanzar (punto P20).'))
      : el('p', { class: 'u3-tenue' }, 'Esta campaña no trae presupuesto.')),
    c.economia ? seccion('Economía de la campaña', el('div', { class: 'u3-presupuesto' },
      U.metrica({ etiqueta: 'Costo por venta de equilibrio', valor: c.economia.cpaEquilibrio, ayuda: 'cpa_equilibrio' }), U.metrica({ etiqueta: 'Costo por venta objetivo', valor: c.economia.cpaObjetivo }),
      U.metrica({ etiqueta: 'Costo por venta máximo', valor: c.economia.cpaMax }), U.metrica({ etiqueta: 'Anuncios', valor: t(c.economia.nAnuncios), contexto: c.economia.kCorte !== null ? `se corta a las ${c.economia.kCorte} veces el costo de equilibrio` : undefined }))) : null,
    seccion(`Anuncios (${c.anuncios.length})`, c.anuncios.length ? el('div', { class: 'u3-anuncios' }, c.anuncios.map((a) => el('div', { class: 'u3-anuncio' },
      el('b', null, a.nombre || 'sin nombre'),
      el('div', { class: 'u3-tenue u3-peq' }, `Concepto ${t(a.concepto)}`),
      a.claims.length ? el('div', { class: 'u3-tags' }, U.termino('afirmaciones_claims', { texto: 'Afirmaciones que usa:' }), a.claims.map((x) => tag(x, null))) : el('span', { class: 'u3-tenue u3-peq' }, 'sin afirmaciones declaradas')))) : el('p', { class: 'u3-tenue' }, 'Sin anuncios en la campaña.')),
    seccion('Cuándo se detiene y cuándo se da por validada', pila(
      c.reglasParada ? pila(
        el('div', { class: 'u3-tenue u3-peq' }, `Corte por gasto sin ventas: se corta al gastar ${t(c.reglasParada.kCorte)} veces el costo de equilibrio sin vender (k = ${t(c.reglasParada.kCorte)}). `, U.termino('costo_equilibrio_k', { texto: 'Qué es k' }), ' · ', U.termino('reglas_parada', { texto: 'Qué son las reglas de parada' }), '.'),
        c.reglasParada.pausaGlobalSi.length ? el('div', null, c.reglasParada.pausaGlobalSi.map((x) => el('div', { class: 'u3-regla' }, ic('pausa', 16), el('span', null, 'Pausa global si ', x)))) : el('p', { class: 'u3-tenue' }, 'Sin reglas de pausa global.'))
        : el('p', { class: 'u3-tenue' }, 'Sin reglas de parada.'),
      c.criterioValidada ? kv(c.criterioValidada) : null)),
    tecnico('Nombres en Meta y huellas', pila(
      tabla({
        etiqueta: 'Nombres de campaña, conjunto y anuncios', filas: c.revisionNombres.items, maxFilas: 20,
        columnas: [
          { clave: 'rol', titulo: 'Objeto', ancho: '110px' },
          { clave: 'nombre', titulo: 'Nombre', clase: 'cel-larga', formato: (v) => el('code', null, v || '—') },
          { clave: 'ok', titulo: 'Formato válido (sin tildes ni espacios; «_» sí, «|» no)', formato: (v, r) => (v ? chip('válido', 'ok') : chip(r.motivo || 'inválido', 'error')) },
        ],
      }),
      c.anuncios.length ? tabla({
        etiqueta: 'Huellas de los creativos', filas: c.anuncios, maxFilas: 30,
        columnas: [{ clave: 'nombre', titulo: 'Anuncio', clase: 'cel-larga', formato: (v) => el('code', null, v) }, { clave: 'sha', titulo: 'Huella del anuncio (creativo)', formato: (v) => (v ? el('code', { title: v }, C.hashCorto(v)) : '—') }],
      }) : null,
      kv([
        [U.termino('hash_config', { texto: 'Huella de la configuración' }), c.hashConfig ? comando(c.hashConfig, { titulo: 'Copiar la huella', etiqueta: 'Copiar la huella de la configuración' }) : null],
        ['Huella de los parámetros de parada', c.reglasParada && c.reglasParada.hashParametros ? el('code', { title: c.reglasParada.hashParametros }, C.hashCorto(c.reglasParada.hashParametros)) : null],
        ['Versión / formato esperado', `${t(c.version)} · formato ${t(c.schema)}`],
      ]),
      el('p', { class: 'u3-tenue u3-peq' }, 'La huella es una marca única (SHA-256) calculada sobre los datos de la campaña sin ese campo, más el estado real de cada objeto en Meta al activar. Es lo que se firma, y lo que el chequeo antes de lanzar, los códigos de Meta y la aprobación deben repetir idéntico.'))),
    tecnico('campana.json completo', d.bruto && d.bruto.campana ? visorJson(d.bruto.campana, { colapsado: true, titulo: 'campana.json' }) : el('p', { class: 'u3-tenue' }, 'Sin campana.json.')));
}

function tabMeta(d) {
  const m = d.modelo.idsMeta;
  const ap = d.modelo.aprobacion;
  const f = d.modelo.firma;
  const borrador = m
    ? pila(
      m.hashCoincide === false ? nota(el('p', null, 'El borrador de Meta es de otra versión de la campaña: la campaña cambió después de crearse el borrador.'), { tono: 'error', icono: 'octogono' }) : null,
      el('div', { class: 'u3-presupuesto' },
        U.metrica({ etiqueta: 'Campaña', valor: m.campaignId ? '1' : '0' }), U.metrica({ etiqueta: 'Conjuntos de anuncios', valor: String(m.adsetIds.length) }),
        U.metrica({ etiqueta: 'Anuncios', valor: String(m.adIds.length) }), U.metrica({ etiqueta: 'Piezas (creativos)', valor: String(m.creativeIds.length), contexto: 'no se activan' })),
      el('p', { class: 'u3-tenue u3-peq' }, `Todo se crea en pausa. En Meta, publicar es lo mismo que activar: por eso la activación exige tu firma y que la configuración real sea igual a la firmada. Creado ${m.creadoEn ? fmt.relativo(m.creadoEn) : '—'}.`),
      tecnico('Códigos de Meta', kv([
        ['Cuenta publicitaria', m.cuenta ? el('code', null, m.cuenta) : null], ['Campaña', m.campaignId ? el('code', null, m.campaignId) : null],
        [`Conjuntos (${m.adsetIds.length})`, m.adsetIds.length ? el('span', { class: 'u3-tags' }, m.adsetIds.map((x) => el('code', null, x))) : null],
        [`Anuncios (${m.adIds.length})`, m.adIds.length ? el('span', { class: 'u3-tags' }, m.adIds.map((x) => el('code', null, x))) : null],
        [`Piezas (${m.creativeIds.length})`, m.creativeIds.length ? el('span', { class: 'u3-tags' }, m.creativeIds.map((x) => el('code', null, x))) : null],
        ['Creado', m.creadoEn ? fmt.fecha(m.creadoEn) : null],
        ['Huella del borrador', m.hashConfig ? el('span', null, el('code', { title: m.hashConfig }, C.hashCorto(m.hashConfig)), ' ', m.hashCoincide === true ? tag('coincide', 'ok', { icono: 'ok' }) : m.hashCoincide === false ? tag('difiere', 'error', { icono: 'octogono' }) : tag('no comparable', null)) : null],
      ])))
    : U.vacioConPasos({
      titulo: 'Aún no existe el borrador de esta campaña en Meta',
      explicacion: 'Los códigos de Meta aparecen cuando se crean, en pausa, la campaña, los conjuntos, las piezas y los anuncios. Hasta entonces no hay nada que aprobar. Crear el borrador cambia datos en Meta, y eso no lo hace este panel.',
      pasos: [{ texto: 'Lo crea la IA de campañas durante una sesión tuya; aquí aparecerá en cuanto exista.' }], icono: 'diana',
    });
  const aprobacion = ap
    ? pila(
      ap.problemas.length ? nota(el('p', null, ap.problemas.join(' ')), { tono: 'error', icono: 'octogono' }) : null,
      kv([
        ['Quién aprobó', `${t(ap.aprobadoPor.tipo)} · ${t(ap.aprobadoPor.id)}${ap.aprobadoPor.fecha ? ` · ${fmt.fecha(ap.aprobadoPor.fecha)}` : ''}`],
        ['Acción aprobada', ap.accion || null], ['Tipo de aprobación', `${ap.gate === 'H' ? 'Con tu firma personal' : t(ap.gate)} · ${/^N[0-4]$/.test(String(ap.nivel)) ? `autonomía ${String(ap.nivel).slice(1)}` : t(ap.nivel)}`],
        ['Firma', ap.aprobadoPor.firmada ? tag('presente (el panel no la verifica)', 'info', { icono: 'firma' }) : tag('sin firma', 'error', { icono: 'octogono' })],
        ['Vigente hasta', ap.vigenciaHasta ? `${fmt.fecha(ap.vigenciaHasta)} (${fmt.relativo(ap.vigenciaHasta)})` : null],
        ['Es de esta configuración', ap.hashCoincide === true ? tag('sí', 'ok', { icono: 'ok' }) : ap.hashCoincide === false ? tag('NO: la campaña cambió', 'error', { icono: 'octogono' }) : tag('no comparable', null)],
        ['Cubre exactamente los objetos del borrador', ap.idsCoinciden === null ? 'no comparable (sin borrador)' : ap.idsCoinciden ? tag('sí', 'ok', { icono: 'ok' }) : tag('NO coinciden', 'error', { icono: 'octogono' })],
      ]),
      el('p', { class: 'u3-tenue u3-peq' }, 'La verificación de la firma y del visto bueno de cumplimiento la hace el sistema automático antes de activar, no este panel.'),
      tecnico('Detalle técnico de la aprobación', kv([
        ['Huella aprobada (hash_objetivo)', ap.hashObjetivo ? el('code', { title: ap.hashObjetivo }, C.hashCorto(ap.hashObjetivo)) : null],
        [`Objetos aprobados (${ap.objectIds.length})`, ap.objectIds.length ? el('span', { class: 'u3-tags' }, ap.objectIds.map((x) => el('code', null, x))) : null],
        ['Firma', ap.aprobadoPor.firmaCorta ? el('code', null, ap.aprobadoPor.firmaCorta) : null], ['Creada', ap.creadoEn ? fmt.fecha(ap.creadoEn) : null],
      ])))
    : pila(
      U.vacioConPasos({
        titulo: 'Aún no hay aprobación firmada',
        explicacion: 'La aprobación la registra el sistema automático después de verificar tu orden firmada; ninguna IA puede escribirla. Cuando el chequeo antes de lanzar esté en verde y vigente, firma con el comando de abajo.',
        pasos: [{ texto: 'Firma la activación en tu terminal.', comando: f.comando || undefined }], icono: 'candado',
      }));
  return pila(seccion('Borrador en Meta', borrador), seccion('Aprobación', aprobacion, { ayuda: 'aprobacion_firma' }));
}
