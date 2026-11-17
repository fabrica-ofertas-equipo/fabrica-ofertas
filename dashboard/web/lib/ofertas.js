// Lógica pura de la pantalla «Ofertas» (#/ofertas): GET /ofertas -> filas, filtros, orden y resumen de la flota.
// Sin DOM ni red. Se prueba con `node --test` (tests/dashboard/test_web_ofertas.mjs).

import { FASES, rotuloNivel, pipelineDesdeMapa, resumenPipeline, rotuloFase, tonoFase, compararEtapas, plano, proximoPasoHumano, tituloDeOferta, fichaMercado, etiquetaEtapa } from './oferta.js';

function esObjeto(x) { return x !== null && typeof x === 'object' && !Array.isArray(x); }

export const NIVELES = ['N0', 'N1', 'N2', 'N3', 'N4'];
export { rotuloNivel };

/** Dinero de la API: {monto (entero en unidad menor), moneda}. Devuelve null si no es utilizable (nunca 0 inventado). */
export function dineroValido(d) {
  if (!esObjeto(d)) return null;
  if (!Number.isSafeInteger(d.monto) || typeof d.moneda !== 'string' || d.moneda === '') return null;
  return { monto: d.monto, moneda: d.moneda };
}

/** Suma por moneda (jamás mezcla monedas). {EUR: 1200, USD: 50}. Ignora valores no utilizables. */
export function sumarPorMoneda(lista) {
  const out = {};
  for (const d of lista) {
    const v = dineroValido(d);
    if (!v) continue;
    out[v.moneda] = (out[v.moneda] || 0) + v.monto;
  }
  return out;
}

export function listaDeOfertas(datos) {
  if (Array.isArray(datos)) return datos.filter(esObjeto);
  if (esObjeto(datos) && Array.isArray(datos.ofertas)) return datos.ofertas.filter(esObjeto);
  return [];
}

/** Un elemento de GET /ofertas -> fila de vista. */
export function filaOferta(o) {
  const gates = Array.isArray(o.gates_pendientes) ? o.gates_pendientes : null;
  const pipeline = pipelineDesdeMapa(o.etapas).map((v) => ({ ...v, gatePendiente: Boolean(gates && gates.includes(v.id) && !v.sinDatos) }));
  const resumen = resumenPipeline(pipeline, gates);
  const id = typeof o.oferta_id === 'string' ? o.oferta_id : '';
  const gastos = esObjeto(o.gasto) ? o.gasto : {};
  return {
    id,
    familia: typeof o.familia_id === 'string' ? o.familia_id : null,
    demo: o.demo === true,
    fase: o.fase ?? null,
    faseRotulo: rotuloFase(o.fase),
    faseTono: tonoFase(o.fase),
    nivel: o.nivel ?? null,
    pausa: o.pausa === true,
    pipeline,
    resumen,
    gatesPendientes: resumen.gatesPendientes,
    gastoHoy: dineroValido(gastos.hoy),
    gastoAcumulado: dineroValido(gastos.acumulado),
    costoIa: dineroValido(o.costo_ia),
    actualizadoEn: typeof o.actualizado_en === 'string' ? o.actualizado_en : null,
    busqueda: plano(`${id} ${typeof o.familia_id === 'string' ? o.familia_id : ''} ${o.demo === true ? 'demo' : ''}`),
  };
}

export function filasOfertas(datos) {
  return ordenarOfertas(listaDeOfertas(datos).map(filaOferta), 'actualizado', 'desc');
}

export const FILTROS_VACIOS = Object.freeze({ texto: '', fase: '', nivel: '', demo: 'todas', soloGates: false, soloPausa: false, soloBloqueadas: false });

/** Aplica filtros. `demo`: 'todas' | 'reales' | 'demo'. */
export function filtrarOfertas(filas, filtros = {}) {
  const f = { ...FILTROS_VACIOS, ...filtros };
  const t = plano(String(f.texto || '').trim());
  return filas.filter((r) => {
    if (t && !r.busqueda.includes(t)) return false;
    if (f.fase && r.fase !== f.fase) return false;
    if (f.nivel && r.nivel !== f.nivel) return false;
    if (f.demo === 'reales' && r.demo) return false;
    if (f.demo === 'demo' && !r.demo) return false;
    if (f.soloGates && r.gatesPendientes.length === 0) return false;
    if (f.soloPausa && !r.pausa) return false;
    if (f.soloBloqueadas && r.resumen.bloqueadas === 0) return false;
    return true;
  });
}

export function hayFiltros(filtros = {}) {
  const f = { ...FILTROS_VACIOS, ...filtros };
  return Object.keys(FILTROS_VACIOS).some((k) => f[k] !== FILTROS_VACIOS[k]);
}

const CLAVES_ORDEN = {
  oferta: (r) => String(r.titulo || r.id).toLowerCase(),
  fase: (r) => FASES.indexOf(r.fase),
  nivel: (r) => r.nivel || '',
  avance: (r) => r.resumen.bp,
  gates: (r) => r.gatesPendientes.length,
  gasto: (r) => (r.gastoAcumulado ? r.gastoAcumulado.monto : -1),
  costo: (r) => (r.costoIa ? r.costoIa.monto : -1),
  actualizado: (r) => r.actualizadoEn || '',
};

/** Orden estable. Las ofertas demo van siempre al final para no tapar a las reales. */
export function ordenarOfertas(filas, clave = 'actualizado', dir = 'desc') {
  const f = CLAVES_ORDEN[clave] || CLAVES_ORDEN.actualizado;
  const signo = dir === 'asc' ? 1 : -1;
  return filas
    .map((r, i) => ({ r, i }))
    .sort((a, b) => {
      if (a.r.demo !== b.r.demo) return a.r.demo ? 1 : -1;
      const x = f(a.r);
      const y = f(b.r);
      if (x < y) return -1 * signo;
      if (x > y) return 1 * signo;
      return a.i - b.i;
    })
    .map((p) => p.r);
}

/** Tarjetas de la cabecera: totales de la flota. El gasto y el costo se suman por moneda. */
export function resumenFlota(filas) {
  const reales = filas.filter((r) => !r.demo);
  const base = reales.length ? reales : filas;
  // Los gates se cuentan en TODAS las ofertas (como el contador de la barra lateral); cada uno lleva su marca de demo.
  const gatesEnLista = [];
  for (const r of filas) for (const e of r.gatesPendientes) gatesEnLista.push({ oferta: r.id, etapa: e, demo: r.demo });
  gatesEnLista.sort((a, b) => Number(a.demo) - Number(b.demo) || a.oferta.localeCompare(b.oferta) || compararEtapas(a.etapa, b.etapa)); // reales primero
  const porFase = {};
  for (const r of base) porFase[r.fase || 'sin_dato'] = (porFase[r.fase || 'sin_dato'] || 0) + 1;
  return {
    total: filas.length,
    reales: reales.length,
    demos: filas.length - reales.length,
    soloDemo: filas.length > 0 && reales.length === 0,
    enPausa: base.filter((r) => r.pausa).length,
    conBloqueo: base.filter((r) => r.resumen.bloqueadas > 0).length,
    gatesPendientes: gatesEnLista,
    porFase,
    gastoAcumulado: sumarPorMoneda(base.map((r) => r.gastoAcumulado)),
    gastoHoy: sumarPorMoneda(base.map((r) => r.gastoHoy)),
    costoIa: sumarPorMoneda(base.map((r) => r.costoIa)),
  };
}

/** Opciones de los selectores (solo valores que existen en los datos, en orden estable). */
export function opcionesFiltro(filas) {
  const fases = FASES.filter((f) => filas.some((r) => r.fase === f));
  for (const r of filas) if (r.fase && !fases.includes(r.fase)) fases.push(r.fase);
  const niveles = NIVELES.filter((n) => filas.some((r) => r.nivel === n));
  return { fases, niveles };
}

/** Descripción en una frase de la barra de etapas (texto accesible para el SVG/barra). */
export function descripcionBarra(fila) {
  const r = fila.resumen;
  if (r.sinDatos) return 'Sin estado por etapa todavía';
  const partes = [`${r.aprobadas} de ${r.total} etapas aprobadas`];
  if (r.enCurso) partes.push(`${r.enCurso} en curso`);
  if (r.bloqueadas) partes.push(`${r.bloqueadas} bloqueadas o esperando tu decisión`);
  if (r.obsoletas) partes.push(`${r.obsoletas} obsoletas`);
  if (r.gatesPendientes.length) partes.push(`espera tu firma en ${r.gatesPendientes.join(', ')}`);
  return partes.join(' · ');
}

// ---------------------------------------------------------------------------------------------
// Rediseño UX: orden, próximo paso por fila y enriquecimiento con el detalle de cada oferta.

export const OPCIONES_ORDEN = [
  { valor: 'actualizado', dir: 'desc', texto: 'Más recientes' },
  { valor: 'gates', dir: 'desc', texto: 'Más firmas pendientes' },
  { valor: 'avance', dir: 'desc', texto: 'Más avanzadas' },
  { valor: 'gasto', dir: 'desc', texto: 'Mayor gasto' },
  { valor: 'costo', dir: 'desc', texto: 'Mayor costo de IA' },
  { valor: 'oferta', dir: 'asc', texto: 'Nombre (A-Z)' },
];

/** Dirección natural de cada orden (la que muestra primero lo más relevante). */
export function direccionDeOrden(clave) {
  const o = OPCIONES_ORDEN.find((x) => x.valor === clave);
  return o ? o.dir : 'desc';
}

/**
 * Próximo paso de una fila de la lista, sin pedir el detalle: reconstruye las etapas del mapa y marca las que esperan firma.
 * Devuelve lo mismo que `proximoPasoHumano` (titulo, tono, tipo, etapa, accion…).
 */
export function proximoDeFila(fila) {
  const vistas = fila.pipeline.map((v) => ({ ...v, gatePendiente: fila.gatesPendientes.includes(v.id) && !v.sinDatos }));
  const resumen = resumenPipeline(vistas, fila.gatesPendientes);
  return proximoPasoHumano(fila.id, vistas, resumen, null);
}

/** Lo que se aprende del detalle `GET /oferta/<id>` para pintar una tarjeta: nombre legible, mercado y próximo paso del servidor. */
export function extraDeDetalle(id, detalle) {
  const d = detalle && typeof detalle === 'object' ? detalle : {};
  const merc = fichaMercado(d);
  return {
    titulo: tituloDeOferta({ brief: d.brief, estado: d.estado, id }),
    idMotor: d.estado && typeof d.estado.oferta_id === 'string' ? d.estado.oferta_id : null,
    idioma: merc.idioma, locale: merc.locale, paises: merc.paises, moneda: merc.moneda,
    mercado: merc.idioma ? `${merc.idioma}${merc.paises.length ? ` · ${merc.paises.join(', ')}` : ''}` : null,
  };
}

/** Fila + lo aprendido del detalle (si ya llegó). El título cae al id si no hay brief. */
export function conExtra(fila, extra) {
  const e = extra || {};
  return {
    ...fila, titulo: e.titulo || fila.id, idMotor: e.idMotor || null, mercado: e.mercado || null, moneda: e.moneda || null, locale: e.locale || null, tieneExtra: Boolean(extra),
    busqueda: plano(`${fila.busqueda} ${e.titulo || ''} ${e.mercado || ''} ${e.idMotor || ''}`), // también se busca por nombre, mercado e id del motor
  };
}

/** Avisos para «Requiere tu atención»: pausa, bloqueos y firmas pendientes (en ese orden de gravedad). */
export function avisosDeAtencion(filas) {
  const items = [];
  for (const f of filas) {
    const nombre = f.titulo || f.id;
    if (f.pausa) items.push({ tono: 'grave', titulo: `${nombre} está en pausa`, detalle: 'Mientras dure la pausa, el sistema no gasta ni activa nada.', accion: { texto: 'Abrir la oferta', ruta: `#/oferta/${encodeURIComponent(f.id)}` }, oferta: f.id });
    const bloqueadas = f.pipeline.filter((v) => !v.sinDatos && (v.estado === 'bloqueado' || v.estado === 'escalado'));
    for (const v of bloqueadas) {
      items.push({
        tono: 'grave', titulo: `${etiquetaEtapa(v.id)} ${v.estado === 'escalado' ? 'necesita una decisión tuya' : 'está bloqueada'}`, detalle: nombre,
        accion: { texto: 'Ver por qué', ruta: `#/oferta/${encodeURIComponent(f.id)}?etapa=${v.id}` }, oferta: f.id,
      });
    }
    for (const g of f.gatesPendientes) {
      items.push({ tono: 'aviso', titulo: `${etiquetaEtapa(g)} espera tu firma`, detalle: nombre, accion: { texto: 'Ver cómo firmarlo', ruta: `#/oferta/${encodeURIComponent(f.id)}?etapa=${g}&panel=firmar` }, oferta: f.id });
    }
  }
  return items;
}
