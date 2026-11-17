// pages/ofertas.js — #/ofertas: todas las ofertas, escaneables de un vistazo (tarjetas o tabla), con su mini-pipeline, lo que espera de ti,
// filtros, orden y densidad (CONTRATO §2, §4 GET /ofertas). Lo que pide tu atención va primero. La lógica está en lib/ofertas.js (probada sin DOM).
// El nombre legible y el mercado de cada oferta salen de su detalle (GET /oferta/<id>), que se pide en segundo plano y se pinta al llegar.

import { ui, el, icono, fmt, limpiar } from '../ui.js';
import * as O from '../lib/ofertas.js';
import * as V from '../lib/oferta.js';
import * as W from '../lib/vistas-ofertas.js';
import { mercadoLargo } from '../lib/negocio-visual.js';

export const meta = { ruta: 'ofertas', titulo: 'Ofertas', grupo: 'Testeo y escala', icono: 'caja', escucha: ['oferta'] };

// Los filtros, la vista y los datos aprendidos sobreviven a los re-render del router (eventos en vivo).
let filtros = { ...O.FILTROS_VACIOS };
let orden = 'actualizado';
let vista = leerVista();
let ultimaFirma = null;
const extras = new Map(); // id → {clave, extra}

function leerVista() {
  try { const v = globalThis.localStorage && globalThis.localStorage.getItem('fab.ofertas.vista'); return v === 'tabla' ? 'tabla' : 'tarjetas'; } catch (_) { return 'tarjetas'; }
}
function guardarVista(v) { try { if (globalThis.localStorage) globalThis.localStorage.setItem('fab.ofertas.vista', v); } catch (_) { /* sin almacén */ } }

const dinero = (d) => (d ? fmt.dinero(d.monto, d.moneda) : null);
const porMoneda = (mapa) => {
  const e = Object.entries(mapa);
  return e.length ? e.map(([m, n]) => fmt.dinero(n, m)).join(' · ') : null;
};
const enlaceOferta = (id, extra = '') => `#/oferta/${encodeURIComponent(id)}${extra}`;

function firmaLista(datos) {
  return JSON.stringify(O.listaDeOfertas(datos).map((o) => [o.oferta_id, o.fase, o.nivel, o.pausa, o.etapas, o.gates_pendientes, o.gasto, o.costo_ia, o.actualizado_en]));
}

export async function render(ctx) {
  W.estilos();
  let sobre;
  try { sobre = await ctx.api.sobre('/ofertas'); } catch (err) {
    return el('div', { class: 'pagina' }, ui.encabezadoPagina({ titulo: 'Ofertas', descripcion: 'No se pudo leer la lista de ofertas.' }), ui.errorBox(err, { reintentar: () => ctx.recargar() }));
  }
  ultimaFirma = firmaLista(sobre.datos);
  const base = O.filasOfertas(sobre.datos);
  const cab = (acciones = []) => ui.encabezadoPagina({
    titulo: 'Ofertas',
    descripcion: 'Todas tus ofertas de un vistazo: en qué etapa están, qué espera de ti y cuánto llevan gastado. Abre una para armarla paso a paso.',
    acciones: [ui.fuente(sobre.fuente, { leido: sobre.generado_en }), ...acciones],
  });

  if (!base.length) {
    return el('div', { class: 'pagina' }, cab(),
      ui.vacioConPasos({
        titulo: 'Todavía no hay ofertas',
        explicacion: 'Una oferta nace de una ficha inicial (el «brief») que tú firmas: después el sistema crea la oferta y esta pantalla se llena sola. La oferta de demostración también aparece aquí cuando existe.',
        icono: 'caja',
        pasos: [
          { texto: 'Escribe la ficha inicial de la oferta: idioma, países, precio y presupuesto de la prueba.' },
          { texto: 'Crea la oferta a partir de esa ficha con este comando:', comando: '.venv/bin/python -m engine.orq crear --brief RUTA_AL_BRIEF' },
          { texto: 'Vuelve aquí: la oferta aparece sola, con sus etapas y lo que espera de ti.' },
        ],
      }));
  }

  const resumen = O.resumenFlota(base);
  const hostAtencion = el('div');
  const hostContenido = el('div');
  const conteo = el('span', { class: 'u2-nota', 'aria-live': 'polite' });
  const filasVista = () => base.map((f) => O.conExtra(f, (extras.get(f.id) || {}).extra));
  const ordenadas = () => O.ordenarOfertas(O.filtrarOfertas(filasVista(), filtros), orden, O.direccionDeOrden(orden));

  // ── métricas ──
  const M = (o) => ui.metrica(o);
  const metricas = el('div', { class: 'u2-metricas' },
    M({
      etiqueta: 'Ofertas', valor: String(resumen.reales || (resumen.soloDemo ? 0 : resumen.total)),
      contexto: resumen.demos ? `más ${resumen.demos} de demostración` : 'reales', tono: resumen.soloDemo ? 'info' : undefined,
    }),
    M({
      etiqueta: 'Esperan tu firma', valor: String(resumen.gatesPendientes.length), tono: resumen.gatesPendientes.length ? 'aviso' : 'ok', ayuda: 'gate_pendiente',
      contexto: resumen.gatesPendientes.length ? resumen.gatesPendientes.slice(0, 3).map((g) => `${V.nombreHumano(g.etapa)}${g.demo ? ' (demo)' : ''}`).join(' · ') + (resumen.gatesPendientes.length > 3 ? ' …' : '') : 'Nada pendiente de ti',
    }),
    M({ etiqueta: 'Bloqueadas o en pausa', valor: String(resumen.conBloqueo + resumen.enPausa), tono: resumen.conBloqueo + resumen.enPausa ? 'grave' : 'ok', contexto: `${resumen.conBloqueo} con etapas bloqueadas · ${resumen.enPausa} en pausa` }),
    M({ etiqueta: 'Gasto acumulado', valor: porMoneda(resumen.gastoAcumulado), contexto: porMoneda(resumen.gastoHoy) ? `hoy ${porMoneda(resumen.gastoHoy)}` : 'sin lectura de hoy' }),
    M({ etiqueta: 'Costo de IA', valor: porMoneda(resumen.costoIa), contexto: 'suma por moneda; nunca se mezclan' }));

  const avisoDemo = resumen.soloDemo
    ? el('div', { class: 'u2-bloque u2-bloque--suave u2-fila' }, W.tag('Solo demostración', 'info'),
      el('span', { class: 'u2-nota' }, 'La única oferta es de demostración (ficticia, en español de España): sirve para ver todas las pantallas llenas. Las ofertas reales aparecerán aquí cuando el sistema las cree.'))
    : null;

  // ── contenido (tarjetas o tabla) ──
  function pintarAtencion() {
    limpiar(hostAtencion);
    hostAtencion.appendChild(ui.atencion({ items: O.avisosDeAtencion(filasVista()).map(({ oferta, ...resto }) => resto), vacio: 'Todo en orden: ninguna oferta espera tu firma ni está bloqueada.' }));
  }

  function tarjetaOferta(f) {
    const p = O.proximoDeFila(f);
    const firma = f.gatesPendientes.length > 0;
    const grave = f.pausa || f.resumen.bloqueadas > 0;
    const boton = p.accion && p.accion.modo === 'firmar'
      ? el('a', { class: 'btn btn--chico btn--primario u2-btn-in', href: enlaceOferta(f.id, `?etapa=${p.etapa}&panel=firmar`) }, icono('firma', { tam: 13 }), p.accion.texto)
      : null;
    return el('article', { class: ['u2-of', firma && 'u2-of--firma', !firma && grave && 'u2-of--grave'] },
      el('div', { class: 'u2-of__cab' },
        el('div', null,
          el('h3', { class: 'u2-of__titulo' }, el('a', { href: enlaceOferta(f.id), title: `Abrir ${f.titulo}` }, f.titulo)),
          el('div', { class: 'u2-of__sub' }, f.mercado ? `${mercadoLargo(f.mercado)}${f.moneda ? ` · ${f.moneda}` : ''}` : (f.tieneExtra ? 'Mercado sin definir' : '…'))),
        f.demo ? el('span', { class: 'chip chip--info' }, ui.termino('oferta_demo', { texto: 'Demo' })) : null),
      el('div', { class: 'u2-fila' },
        ui.estadoIcono(f.fase), f.nivel ? ui.termino('nivel_autonomia', { texto: O.rotuloNivel(f.nivel) }) : null,
        f.pausa ? W.tag('En pausa', 'grave', { icono: 'pausa' }) : null),
      el('div', { class: 'u2-of__etapas', title: O.descripcionBarra(f) },
        W.miniPipeline(f.pipeline, { etiqueta: O.descripcionBarra(f) }),
        el('span', { class: 'u2-nota' }, f.resumen.sinDatos ? 'sin etapas' : `${f.resumen.aprobadas} de ${f.resumen.total}`)),
      el('div', { class: ['u2-of__proximo', `u2-of__proximo--${p.tono}`] },
        icono({ firmar_gate: 'firma', en_qa: 'ojo', en_progreso: 'progreso', bloqueado: 'octogono', escalado: 'escalar', rehacer: 'reloj-alerta', siguiente: 'play', completa: 'ok', sin_estado: 'info' }[p.tipo] || 'flecha-derecha', { tam: 16 }),
        el('div', null, el('span', { class: 'u2-rotulo' }, 'Próximo paso'), el('strong', null, p.titulo), boton)),
      el('div', { class: 'u2-of__cifras' },
        el('div', { class: 'u2-of__cifra' }, el('span', { class: 'u2-rotulo' }, 'Gasto'), el('b', null, dinero(f.gastoAcumulado) || '—')),
        el('div', { class: 'u2-of__cifra' }, el('span', { class: 'u2-rotulo' }, 'Costo de IA'), el('b', null, dinero(f.costoIa) || '—')),
        el('div', { class: 'u2-of__cifra' }, el('span', { class: 'u2-rotulo' }, 'Actividad'), el('b', null, f.actualizadoEn ? W.cuando(f.actualizadoEn) : '—'))));
  }

  function tablaOfertas(filas) {
    return ui.tabla({
      etiqueta: 'Ofertas', filas, alClick: (f) => ctx.navegar(enlaceOferta(f.id)), vacio: 'Ninguna oferta coincide con los filtros.',
      claseFila: (f) => (f.pausa || f.resumen.bloqueadas ? 'fila-error' : (f.gatesPendientes.length ? 'fila-aviso' : '')),
      columnas: [
        { clave: 'titulo', titulo: 'Oferta', flex: true, formato: (t, f) => el('div', { class: 'u2-celda-titulo' },
          el('a', { class: 'enlace', href: enlaceOferta(f.id), onclick: (ev) => ev.stopPropagation() }, t), el('span', null, (f.mercado && mercadoLargo(f.mercado)) || (f.demo ? 'Demostración' : f.id))) },
        { clave: 'fase', titulo: 'Fase', ancho: '190px', formato: (_t, f) => el('span', { class: 'u2-fila', style: { flexWrap: 'nowrap', gap: '6px' } }, ui.estadoIcono(f.fase), f.nivel ? ui.termino('nivel_autonomia', { texto: O.rotuloNivel(f.nivel) }) : null, f.pausa ? W.tag('Pausa', 'grave', { icono: 'pausa' }) : null), orden: (f) => V.FASES.indexOf(f.fase) },
        { clave: 'resumen.bp', titulo: 'Etapas', ancho: '185px', formato: (_b, f) => el('span', { class: 'u2-fila', style: { flexWrap: 'nowrap', gap: '8px' }, title: O.descripcionBarra(f) }, W.miniPipeline(f.pipeline, { etiqueta: O.descripcionBarra(f), compacta: true }), el('span', { class: 'u2-tenue' }, f.resumen.sinDatos ? '—' : `${f.resumen.aprobadas}/${f.resumen.total}`)) },
        { clave: 'proximo', titulo: 'Próximo paso', ancho: '250px', orden: (f) => f.gatesPendientes.length, formato: (_t, f) => { const p = O.proximoDeFila(f); return el('span', { class: p.tono === 'acento' ? 'u2-ic--info' : null, title: p.detalle || null }, p.titulo); } },
        { clave: 'gastoAcumulado', titulo: 'Gasto', ancho: '100px', alinear: 'der', formato: (d) => (d ? dinero(d) : el('span', { class: 'texto-tenue' }, '—')) },
        { clave: 'costoIa', titulo: 'Costo de IA', ancho: '95px', alinear: 'der', formato: (d) => (d ? dinero(d) : el('span', { class: 'texto-tenue' }, '—')) },
        { clave: 'actualizadoEn', titulo: 'Actividad', ancho: '90px', formato: (t) => W.cuando(t) },
      ],
    });
  }

  function pintarContenido() {
    const filas = ordenadas();
    limpiar(hostContenido);
    conteo.textContent = O.hayFiltros(filtros) ? `${filas.length} de ${base.length} ofertas` : `${base.length} ofertas`;
    limpiarBoton.disabled = !O.hayFiltros(filtros);
    if (!filas.length) {
      hostContenido.appendChild(ui.vacioConPasos({ titulo: 'Ninguna oferta coincide con los filtros', explicacion: 'Prueba a quitar algún filtro o a buscar por otra palabra.', icono: 'filtro', pasos: [{ texto: 'Pulsa «Limpiar filtros» para ver todas.' }] }));
      return;
    }
    hostContenido.appendChild(vista === 'tabla' ? tablaOfertas(filas) : el('div', { class: 'u2-tarjetas' }, filas.map(tarjetaOferta)));
  }

  // ── barra de herramientas ──
  const opc = O.opcionesFiltro(base);
  const campoSel = (etiqueta, valor, opciones, alCambiar) => {
    const s = el('select', { class: 'campo campo--chico', 'aria-label': etiqueta, onchange: (ev) => { alCambiar(ev.target.value); pintarContenido(); } }, opciones.map((o) => el('option', { value: o.valor }, o.texto)));
    s.value = valor;
    return el('label', { class: 'u2-herr__campo' }, etiqueta, s);
  };
  const interruptor = (texto, clave) => ui.interruptor({ etiqueta: texto, activo: Boolean(filtros[clave]), onCambio: (v) => { filtros = { ...filtros, [clave]: v }; pintarContenido(); } });
  const texto = el('input', { class: 'campo campo--chico', type: 'search', placeholder: 'Nombre, código o familia…', 'aria-label': 'Buscar oferta', oninput: (ev) => { filtros = { ...filtros, texto: ev.target.value }; pintarContenido(); } });
  texto.value = filtros.texto;
  const limpiarBoton = el('button', { type: 'button', class: 'btn btn--chico', onclick: () => { filtros = { ...O.FILTROS_VACIOS }; ctx.recargar(); } }, 'Limpiar filtros');
  const segVista = W.segmentado([{ valor: 'tarjetas', texto: 'Tarjetas', icono: 'caja' }, { valor: 'tabla', texto: 'Tabla', icono: 'lista' }], vista, (v) => { vista = v; guardarVista(v); pintarContenido(); }, { etiqueta: 'Vista' });
  const barra = el('div', { class: 'u2-herr' },
    el('label', { class: 'u2-herr__campo u2-herr__campo--busca' }, 'Buscar', texto),
    campoSel('Fase', filtros.fase, [{ valor: '', texto: 'Todas' }, ...opc.fases.map((f) => ({ valor: f, texto: W.mayus(V.rotuloFase(f)) }))], (v) => { filtros = { ...filtros, fase: v }; }),
    campoSel('Autonomía', filtros.nivel, [{ valor: '', texto: 'Todas' }, ...opc.niveles.map((n) => ({ valor: n, texto: O.rotuloNivel(n) }))], (v) => { filtros = { ...filtros, nivel: v }; }),
    campoSel('Origen', filtros.demo, [{ valor: 'todas', texto: 'Reales y de demostración' }, { valor: 'reales', texto: 'Solo reales' }, { valor: 'demo', texto: 'Solo de demostración' }], (v) => { filtros = { ...filtros, demo: v }; }),
    campoSel('Ordenar por', orden, O.OPCIONES_ORDEN.map((o) => ({ valor: o.valor, texto: o.texto })), (v) => { orden = v; }),
    el('div', { class: 'u2-herr__fin' }, segVista));
  const interruptores = el('div', { class: 'u2-interruptores' },
    interruptor('Espera mi firma', 'soloGates'), interruptor('En pausa', 'soloPausa'), interruptor('Con bloqueo', 'soloBloqueadas'), limpiarBoton, conteo);

  pintarAtencion();
  pintarContenido();
  enriquecer(ctx, base, () => { if (hostContenido.isConnected) { pintarAtencion(); pintarContenido(); } });

  return el('div', { class: 'pagina' }, cab(), hostAtencion, metricas, avisoDemo, barra, interruptores, hostContenido,
    el('p', { class: 'u2-nota' }, 'Cada cuadrito de la barra es una etapa, en orden: ',
      V.ORDEN_ETAPAS.map((id) => V.nombreHumano(id)).join(' › '), '. Verde aprobada · azul en marcha o revisión · ámbar con anillo, espera tu firma · rojo bloqueada · gris pendiente · punteado sin datos.'));
}

/** Pide en segundo plano el detalle de cada oferta (nombre legible y mercado). Máximo 3 a la vez; `alLlegar` repinta cuando hay algo nuevo. */
async function enriquecer(ctx, filas, alLlegar) {
  const pendientes = filas.filter((f) => { const e = extras.get(f.id); return !e || e.clave !== `${f.actualizadoEn}`; });
  let nuevos = 0;
  let siguiente = 0;
  const trabajador = async () => {
    while (siguiente < pendientes.length) {
      const f = pendientes[siguiente]; siguiente += 1;
      try {
        const d = await ctx.api.get(`/oferta/${encodeURIComponent(f.id)}`);
        extras.set(f.id, { clave: `${f.actualizadoEn}`, extra: O.extraDeDetalle(f.id, d) });
        nuevos += 1;
        if (nuevos % 2 === 0) alLlegar();
      } catch (_) { /* sin detalle: la tarjeta queda con su id */ }
    }
  };
  await Promise.all([trabajador(), trabajador(), trabajador()]);
  if (nuevos) alLlegar();
}

/** Recarga solo si cambió alguna oferta (o, sin SSE, si cambió la firma de la lista). */
export async function alCambio(ctx, evento) {
  const lote = Array.isArray(evento && evento.lote) && evento.lote.length ? evento.lote : [evento];
  if (lote.some((e) => e && e.tipo === 'oferta')) { ctx.recargar(); return undefined; }
  if (lote.some((e) => e && e.tipo === 'sondeo')) {
    try {
      const d = await ctx.api.get('/ofertas');
      if (firmaLista(d) !== ultimaFirma) ctx.recargar();
    } catch (_) { /* sin conexión: lo muestra el indicador EN VIVO */ }
  }
  return undefined;
}
