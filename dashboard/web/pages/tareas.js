// pages/tareas.js — #/tareas «Mis tareas»: la tanda completa del negocio en 6 momentos, con el estado REAL de cada tarea (nunca inventado), un panel lateral
// «Cómo hacerla» (pasos, enlaces, comandos copiables y, solo donde existe una acción segura de la lista blanca, «Ejecutar ahora») y dos formas de verla:
// «Lista por momentos» y «Mapa del negocio». Arriba: «Tu siguiente paso» y «X de Y hechas».
//
// SOLO LECTURA. Ningún botón firma, publica, activa, gasta, envía ni toca la PAUSA o el freno: eso se muestra como pasos y comando copiable (`ui.comando`).
// La única escritura es una marca personal en el navegador (localStorage), rotulada «solo para ti: no cambia el sistema».
// Todo texto que viene de archivos es dato no confiable: entra siempre por textContent (ui.el). La lógica pura vive en ../lib/tareas.js.

import * as T from '../lib/tareas.js';
import { ESTILOS_T1 } from '../lib/estilos-t1.js';

export const meta = { ruta: 'tareas', titulo: 'Mis tareas', grupo: 'El sistema', icono: 'tareas', escucha: ['empresa', 'oferta'] };

const RUTAS = {
  sistema: '/sistema', parametros: '/parametros', ofertas: '/ofertas', pulido: '/pulido', gates: '/gates', robots: '/robots', cumplimiento: '/cumplimiento', cerebro: '/cerebro', acciones: '/acciones',
};
const ETIQUETA_LECTURA = {
  sistema: 'el estado del sistema', parametros: 'los límites', ofertas: 'las ofertas', pulido: 'la lista de pendientes', gates: 'los puntos de control', robots: 'el registro de robots',
  cumplimiento: 'las revisiones de cumplimiento', cerebro: 'la memoria', acciones: 'las comprobaciones disponibles', oferta: 'la oferta elegida',
};
const INTERVALO_JOB_MS = 800;
const MAX_FALLOS_JOB = 4;
const MAX_SALIDA = 200000;

// Estado que sobrevive a los re-render del router (filtros, vista y tarea abierta).
const sesion = { vista: null, filtros: { ...T.FILTROS_VACIOS }, abierta: null };
let panelActual = null;

const almacen = () => { try { return globalThis.localStorage || null; } catch (_) { return null; } };

async function pedir(ctx, ruta, params) {
  try { const r = await ctx.api.sobre(ruta, params); return { ok: true, vacio: Boolean(r.vacio), datos: r.datos, fuente: Array.isArray(r.fuente) ? r.fuente : [], generado_en: r.generado_en || null, avisos: r.avisos || [] }; } catch (err) { return { ok: false, vacio: false, datos: null, fuente: [], generado_en: null, avisos: [], err }; }
}

async function cargar(ctx) {
  const nombres = Object.keys(RUTAS);
  const res = await Promise.all(nombres.map((n) => pedir(ctx, RUTAS[n])));
  const lecturas = Object.fromEntries(nombres.map((n, i) => [n, res[i]]));
  const elegida = T.elegirOferta(lecturas.ofertas.ok ? lecturas.ofertas.datos : [], ctx.estado.ofertaActiva);
  let oferta = null;
  if (elegida.id) {
    const det = await pedir(ctx, `/oferta/${encodeURIComponent(elegida.id)}`);
    oferta = { id: elegida.id, demo: elegida.demo, motivo: elegida.motivo, lectura: det };
    lecturas.oferta = det;
  }
  return { lecturas, oferta };
}

// ───────────────────────── piezas pequeñas ─────────────────────────

function chipEstado(U, clave, { marca = false } = {}) {
  const e = T.ESTADOS[clave];
  const c = U.chip(e.texto, e.tono, { icono: e.icono });
  c.classList.add(`t1-chip-estado--${clave}`);
  c.dataset.estado = clave;
  return marca ? U.el('span', { class: 't1-fila' }, c, U.chip('Marcada por ti', 'neutro', { icono: 'usuario' })) : c;
}
function chipQuien(U, q) {
  const d = T.QUIENES[q];
  const c = U.chip(d.texto, 'neutro', { icono: d.icono });
  c.classList.add('t1-chip-quien');
  if (q === 'dueno') c.classList.add('t1-chip-quien--dueno');
  c.title = d.frase;
  return c;
}
function chipDemo(U) {
  const c = U.chip('Demo', 'neutro', { icono: 'caja' });
  c.classList.add('t1-chip-demo');
  c.title = 'Está calculada con la oferta de demostración: no cuenta en tu avance.';
  return c;
}
function barra(U, { datos = 0, marca = 0, total = 0, etiqueta = '' }) {
  const pc = (n) => (total ? `${((n / total) * 100).toFixed(2)}%` : '0%');
  return U.el('div', { class: 't1-barra', role: 'img', 'aria-label': etiqueta, 'data-total': String(total) },
    U.el('i', { class: 't1-barra__datos', style: { '--p': pc(datos) } }), U.el('i', { class: 't1-barra__marca', style: { '--p': pc(marca) } }));
}
function aviso(U, tono, nombreIcono, ...hijos) {
  return U.el('div', { class: ['t1-aviso', tono && `t1-aviso--${tono}`], role: tono === 'error' ? 'alert' : null }, U.icono(nombreIcono, { tam: 16 }), U.el('div', { class: 't1-aviso__texto' }, ...hijos));
}
const momentoDe = (id) => T.MOMENTOS[id];
const textoPeriodo = (p) => (p === 'dia' ? 'Vale solo por hoy: mañana vuelve a quedar pendiente.' : p === 'semana' ? 'Vale solo por esta semana: la próxima vuelve a quedar pendiente.' : 'Queda guardada en este navegador.');

// ───────────────────────── render ─────────────────────────

export async function render(ctx) {
  const U = ctx.ui;
  const { el, icono, encabezadoPagina, segmentado } = U;
  U.instalarEstilos('t1-tareas', ESTILOS_T1);
  if (sesion.vista === null) sesion.vista = T.leerVista(almacen());

  const { lecturas, oferta } = await cargar(ctx);
  const critico = ['sistema', 'parametros', 'ofertas'].every((n) => !lecturas[n].ok);
  if (critico) {
    return el('div', { class: 'pagina' }, encabezadoPagina({ titulo: 'Mis tareas', descripcion: 'Todo lo que hay que hacer para que el negocio funcione, paso a paso.' }),
      U.errorBox(lecturas.sistema.err, { reintentar: () => ctx.recargar() }));
  }

  let modelo = null;
  const evaluar = () => T.evaluarTareas(lecturas, { oferta, marcas: T.leerMarcas(almacen()), ahora: Date.now(), fmt: ctx.fmt || U.fmt });
  modelo = evaluar();
  const accionesServidor = T.normalizarAccionesServidor(lecturas.acciones.ok ? lecturas.acciones.datos : []);

  const cuerpo = { arriba: el('div', { class: 't1-arriba' }), oferta: el('div'), avisos: el('div', { class: 't1-pila' }), resultados: el('div'), cuenta: el('span', { class: 't1-herr__fin', 'aria-live': 'polite' }) };

  // ── abrir y cerrar el panel «Cómo hacerla» ──
  const tareaPorId = (id) => modelo.tareas.find((t) => t.id === id) || null;
  function cerrarPanelYa() { if (panelActual) { const p = panelActual; panelActual = null; p.cerrar({ silencioso: true }); } }
  function marcarAbierta() {
    for (const n of cuerpo.resultados.querySelectorAll('[data-abierta]')) n.setAttribute('data-abierta', n.getAttribute('data-id') === sesion.abierta ? '1' : '0');
  }
  function origenDeFoco(id) {
    const n = cuerpo.resultados.querySelector(`[data-id="${id}"]`);
    if (!n) return null;
    return n.tagName === 'BUTTON' ? n : (n.querySelector('button') || null);
  }
  function abrir(id) {
    const t = tareaPorId(id);
    if (!t) return;
    if (panelActual && panelActual.id === id) { panelActual.enfocar(); return; }
    cerrarPanelYa();
    sesion.abierta = id;
    panelActual = crearPanel(ctx, {
      tarea: t, accionesServidor, contexto: () => ({ oferta: modelo.oferta }),
      abrirOtra: abrir, alternarMarca, enfocarOrigen: () => origenDeFoco(id),
      alCerrar: () => { sesion.abierta = null; panelActual = null; try { history.replaceState(null, '', '#/tareas'); } catch (_) { /* sin history */ } marcarAbierta(); },
    });
    try { history.replaceState(null, '', `#/tareas?tarea=${encodeURIComponent(id)}`); } catch (_) { /* sin history */ }
    marcarAbierta();
  }

  function alternarMarca(t) {
    const alm = almacen();
    const ok = t.estado.origen === 'marca' ? T.quitarMarca(alm, t.id) : T.guardarMarca(alm, t.id, new Date().toISOString());
    if (!ok) U.toast('No se pudo guardar tu marca: este navegador no deja guardar datos.', 'aviso');
    refrescar();
  }

  function refrescar() {
    modelo = evaluar();
    repintar();
    if (panelActual) { const t = tareaPorId(panelActual.id); if (t) panelActual.actualizar(t); }
  }

  // ── partes de la pantalla ──
  function pintarArriba() {
    const { siguiente, resumen } = modelo;
    const sig = siguiente ? (() => {
      const m = momentoDe(siguiente.momento);
      const est = T.ESTADOS[siguiente.estado.clave];
      return el('section', { class: 't1-sig', 'aria-labelledby': 't1-sig-t', 'data-tarea': siguiente.id },
        el('p', { class: 't1-sig__rotulo', id: 't1-sig-t' }, 'Tu siguiente paso'),
        el('h2', { class: 't1-sig__titulo' }, siguiente.titulo),
        el('div', { class: 't1-fila' }, U.chip(`Momento ${m.id} · ${m.corto}`, 'neutro', { icono: m.icono }), chipQuien(U, siguiente.quien), chipEstado(U, siguiente.estado.clave)),
        el('p', { class: 't1-sig__texto' }, siguiente.porQue),
        siguiente.estado.evidencia ? el('p', { class: 't1-sub' }, icono(est.icono, { tam: 13 }), ' ', siguiente.estado.evidencia) : null,
        el('div', { class: 't1-sig__acciones' },
          el('button', { type: 'button', class: 'btn btn--primario', onclick: () => abrir(siguiente.id) }, 'Cómo hacerla', icono('flecha-derecha', { tam: 14 })),
          siguiente.estado.marcable ? el('button', { type: 'button', class: 'btn', title: 'Solo para ti: no cambia el sistema', onclick: () => alternarMarca(siguiente) }, icono('check', { tam: 14 }), 'Marcar como hecha') : null,
          siguiente.estado.marcable ? el('span', { class: 't1-tenue t1-sub' }, 'Solo para ti: no cambia el sistema') : null));
    })() : (() => {
      const todoTuyoHecho = resumen.tuyas > 0 && resumen.tuyasHechas === resumen.tuyas;
      return el('section', { class: 't1-sig t1-sig--calma', 'aria-labelledby': 't1-sig-t' },
        el('p', { class: 't1-sig__rotulo', id: 't1-sig-t' }, 'Tu siguiente paso'),
        el('h2', { class: 't1-sig__titulo' }, 'Por ahora no te toca nada'),
        el('p', { class: 't1-sig__texto' }, todoTuyoHecho ? 'Hiciste todo lo que te toca. Lo que sigue lo hace el sistema o una IA.' : 'Lo que te toca está esperando a otras tareas, o todavía no existe. Mira las tareas bloqueadas para ver qué falta primero.'));
    })();
    const noExisten = resumen.noExisten;
    const cuenta = el('section', { class: 't1-cuenta', 'aria-labelledby': 't1-cuenta-t' },
      el('p', { class: 't1-cuenta__rotulo', id: 't1-cuenta-t' }, 'Tareas hechas'),
      el('div', { class: 't1-cuenta__num' }, el('span', { class: 't1-cuenta__valor' }, `${resumen.hechas} de ${resumen.total}`), el('span', { class: 't1-cuenta__de' }, 'hechas')),
      barra(U, { datos: resumen.porComprobacion, marca: resumen.porMarca, total: resumen.total, etiqueta: `${resumen.hechas} de ${resumen.total} tareas hechas` }),
      el('p', { class: 't1-cuenta__nota' }, resumen.hechas
        ? `${resumen.porComprobacion} comprobadas por el sistema${resumen.porMarca ? ` · ${resumen.porMarca} marcadas por ti` : ''}.`
        : 'Ninguna está hecha todavía. Solo cuentan las comprobadas o las que marques tú.'),
      el('p', { class: 't1-cuenta__nota' }, `Tuyas: ${resumen.tuyasHechas} de ${resumen.tuyas} hechas.${noExisten ? ` ${noExisten} todavía no existen (falta construirlas).` : ''}`),
      resumen.noCuentan ? el('p', { class: 't1-cuenta__nota' }, `No cuentan ${resumen.noCuentan} tareas calculadas con la oferta de demostración.`) : null);
    U.reemplazar(cuerpo.arriba, sig, cuenta);
  }

  function pintarOferta() {
    const ofs = lecturas.ofertas.ok && Array.isArray(lecturas.ofertas.datos) ? lecturas.ofertas.datos.filter((o) => o && typeof o.oferta_id === 'string') : [];
    if (!lecturas.ofertas.ok) { U.reemplazar(cuerpo.oferta, aviso(U, 'aviso', 'alerta', el('strong', null, 'No se pudo leer la lista de ofertas.'), el('span', null, 'Las tareas de los momentos 1 y 2 salen como «No se puede comprobar sola».'))); return; }
    if (!ofs.length) { U.reemplazar(cuerpo.oferta, aviso(U, 'info', 'info', el('strong', null, 'Todavía no hay ninguna oferta.'), el('span', null, 'Los momentos 1 y 2 empiezan cuando crees la primera: el primer paso explica cómo.'))); return; }
    const sel = el('select', {
      class: 'campo campo--chico', 'aria-label': 'Oferta que se muestra en los momentos 1 y 2',
      onchange: (ev) => { if (typeof ctx.estado.fijar === 'function') ctx.estado.fijar({ ofertaActiva: ev.target.value || null }); else { ctx.estado.ofertaActiva = ev.target.value || null; ctx.recargar(); } },
    }, ofs.map((o) => el('option', { value: o.oferta_id }, o.demo ? `${o.oferta_id} (demostración)` : o.oferta_id)));
    sel.value = oferta ? oferta.id : '';
    U.reemplazar(cuerpo.oferta, aviso(U, oferta && oferta.demo ? 'info' : null, oferta && oferta.demo ? 'caja' : 'info',
      el('span', null, oferta && oferta.demo
        ? el('span', null, el('strong', null, 'Estás viendo la oferta de demostración. '), 'Sirve para ver cómo se ve todo lleno; sus tareas no cuentan en tu avance. Elige otra oferta cuando tengas una real.')
        : el('span', null, 'Los momentos 1 y 2 muestran el estado real de esta oferta: ')),
      el('label', { class: 't1-herr__campo' }, 'Oferta', sel)));
  }

  function pintarAvisos() {
    const fallan = Object.keys(RUTAS).filter((n) => !lecturas[n].ok && n !== 'acciones');
    if (oferta && !lecturas.oferta.ok) fallan.push('oferta');
    U.reemplazar(cuerpo.avisos, fallan.length ? aviso(U, 'aviso', 'alerta', el('strong', null, 'Hay datos que no se pudieron leer.'), el('span', null, `No se pudo leer ${fallan.map((n) => ETIQUETA_LECTURA[n]).join(', ')}. Las tareas que dependen de eso salen como «No se puede comprobar sola»: no se inventa nada.`)) : null);
  }

  function filtradas() { return T.filtrarTareas(modelo.tareas, sesion.filtros); }

  function pintarResultados() {
    const fs = filtradas();
    cuerpo.cuenta.textContent = fs.length === modelo.tareas.length ? `${fs.length} tareas` : `${fs.length} de ${modelo.tareas.length} tareas`;
    if (!fs.length) {
      U.reemplazar(cuerpo.resultados, U.vacioConPasos({ titulo: 'Ninguna tarea coincide con lo que buscas', explicacion: 'Prueba con otra palabra o quita algún filtro.', icono: 'filtro', compacto: true, pasos: [{ texto: 'Borra el texto de búsqueda o elige «Todas» y «Todos los estados».' }] }));
      return;
    }
    U.reemplazar(cuerpo.resultados, sesion.vista === 'mapa' ? vistaMapa(U, modelo, fs, abrir) : vistaLista(U, modelo, fs, abrir));
  }

  function repintar() { pintarArriba(); pintarOferta(); pintarAvisos(); pintarResultados(); }

  // ── cabecera y herramientas (se crean una vez: así el buscador no pierde el foco al escribir) ──
  const seg = segmentado({
    opciones: [{ valor: 'lista', etiqueta: 'Lista por momentos', titulo: 'Las tareas agrupadas por momento' }, { valor: 'mapa', etiqueta: 'Mapa del negocio', titulo: 'El recorrido completo, de izquierda a derecha' }],
    valor: sesion.vista, etiqueta: 'Forma de ver las tareas',
    onCambio: (v) => { sesion.vista = v; T.guardarVista(almacen(), v); pintarResultados(); },
  });
  seg.classList.add('t1-vista');
  const cab = encabezadoPagina({
    titulo: 'Mis tareas',
    descripcion: 'Todo lo que hay que hacer para que el negocio funcione, en el orden en que se hace: qué te toca a ti, qué hace el sistema solo y qué prepara una IA.',
    acciones: [seg, U.fuente([...new Set(Object.values(lecturas).flatMap((l) => l.fuente || []))], { leido: lecturas.sistema.generado_en || lecturas.ofertas.generado_en }),
      el('button', { type: 'button', class: 'btn', onclick: () => ctx.recargar() }, icono('refrescar', { tam: 14 }), 'Actualizar')],
  });
  const buscar = el('input', {
    type: 'search', class: 'campo campo--chico t1-herr__busca', placeholder: 'Buscar una tarea…', 'aria-label': 'Buscar una tarea',
    oninput: (ev) => { sesion.filtros = { ...sesion.filtros, texto: ev.target.value }; pintarResultados(); },
  });
  buscar.value = sesion.filtros.texto;
  const segQuien = segmentado({
    opciones: T.OPCIONES_QUIEN.map((o) => ({ valor: o.valor, etiqueta: o.texto, titulo: o.valor === 'todas' ? 'Todas las tareas' : T.QUIENES[o.valor].frase })), valor: sesion.filtros.quien, etiqueta: 'Quién la hace',
    onCambio: (v) => { sesion.filtros = { ...sesion.filtros, quien: v }; pintarResultados(); },
  });
  const selEstado = el('select', {
    class: 'campo campo--chico', 'aria-label': 'Filtrar por estado',
    onchange: (ev) => { sesion.filtros = { ...sesion.filtros, estado: ev.target.value }; pintarResultados(); },
  }, T.OPCIONES_ESTADO.map((o) => el('option', { value: o.valor }, o.texto)));
  selEstado.value = sesion.filtros.estado;
  const herramientas = el('div', { class: 't1-herr', role: 'search', 'aria-label': 'Buscar y filtrar tareas' },
    buscar, el('div', { class: 't1-herr__campo' }, 'Quién', segQuien), el('label', { class: 't1-herr__campo' }, 'Estado', selEstado), cuerpo.cuenta);

  // ── pie con lo técnico ──
  const pie = el('div', { class: 't1-pie' }, U.detalleTecnico('Detalle técnico: de dónde sale cada estado', () => detalleGeneral(U, lecturas, oferta, modelo)));

  repintar();
  ctx.alSalir(() => {
    cerrarPanelYa();
    const sigueAqui = typeof location !== 'undefined' && /^#\/tareas(\?|$)/.test(location.hash || '');
    if (!sigueAqui) sesion.abierta = null; // se fue a otra pantalla: al volver no se reabre solo
  });
  if (ctx.params && typeof ctx.params.tarea === 'string' && modelo.tareas.some((t) => t.id === ctx.params.tarea)) setTimeout(() => abrir(ctx.params.tarea), 0);
  else if (sesion.abierta && modelo.tareas.some((t) => t.id === sesion.abierta)) { const id = sesion.abierta; sesion.abierta = null; setTimeout(() => abrir(id), 0); }

  return el('div', { class: 'pagina' }, el('div', { class: 't1' }, cab, cuerpo.arriba, cuerpo.oferta, cuerpo.avisos, herramientas, cuerpo.resultados, pie));
}

export function alCambio(ctx) {
  if (panelActual) return undefined; // no se pierde lo que estás leyendo ni una comprobación en marcha
  ctx.recargar();
  return undefined;
}

// ───────────────────────── lista por momentos ─────────────────────────

function filaTarea(U, t, abrir) {
  const { el, icono } = U;
  const est = T.ESTADOS[t.estado.clave];
  const marca = t.estado.origen === 'marca';
  const boton = el('button', {
    type: 'button', class: 'btn btn--chico', 'aria-label': `Cómo hacerla: ${t.titulo}`,
    onclick: (ev) => { ev.stopPropagation(); abrir(t.id); },
  }, 'Cómo hacerla', icono('flecha-derecha', { tam: 13 }));
  const li = el('li', {
    class: 't1-tarea', 'data-id': t.id, 'data-estado': t.estado.clave, 'data-abierta': sesion.abierta === t.id ? '1' : '0',
    onclick: () => abrir(t.id),
  },
  el('span', { class: 't1-tarea__ic', 'aria-hidden': 'true' }, icono(est.icono, { tam: 16 })),
  el('div', { class: 't1-tarea__cuerpo' },
    el('h3', { class: 't1-tarea__titulo' }, t.titulo),
    el('p', { class: 't1-tarea__porque' }, t.porQue),
    t.estado.evidencia ? el('p', { class: 't1-tarea__evid' }, icono(t.estado.origen === 'datos' ? 'ojo' : 'info', { tam: 13 }), el('span', null, t.estado.evidencia)) : null,
    t.estado.alerta ? el('p', { class: 't1-tarea__evid' }, icono('alerta', { tam: 13 }), el('span', null, t.estado.alerta)) : null),
  el('div', { class: 't1-tarea__lado' },
    el('div', { class: 't1-tarea__chips' }, chipQuien(U, t.quien), chipEstado(U, t.estado.clave, { marca }), t.demo ? chipDemo(U) : null),
    t.cuando ? el('span', { class: 't1-tarea__cuando' }, icono('reloj', { tam: 12 }), t.cuando) : null,
    boton));
  return li;
}

function vistaLista(U, modelo, fs, abrir) {
  const { el } = U;
  return el('div', { class: 't1-momentos' }, T.agruparPorMomento(fs).map((g) => {
    const m = modelo.momentos[g.id];
    const c = m.conteo;
    const hid = `t1-m${g.id}`;
    return el('section', { class: 't1-momento', 'aria-labelledby': hid, 'data-momento': String(g.id) },
      el('header', { class: 't1-mom__cab' },
        el('span', { class: 't1-mom__num', 'aria-hidden': 'true' }, String(g.id)),
        el('div', null, el('h2', { class: 't1-mom__titulo', id: hid }, g.titulo, m.demo ? [' ', chipDemo(U)] : null), el('p', { class: 't1-mom__resumen' }, g.resumen)),
        el('div', { class: 't1-mom__avance' },
          el('span', null, `${c.hechas} de ${c.total} hechas`),
          barra(U, { datos: m.tareas.filter((t) => t.estado.clave === 'hecha' && t.estado.origen !== 'marca').length, marca: m.tareas.filter((t) => t.estado.origen === 'marca').length, total: c.total, etiqueta: `Momento ${g.id}: ${c.hechas} de ${c.total} tareas hechas` }),
          c.porEstado.no_existe ? el('span', { class: 't1-tenue' }, `${c.porEstado.no_existe} todavía no existen`) : null)),
      el('ul', { class: 't1-lista' }, g.tareas.map((t) => filaTarea(U, t, abrir))));
  }));
}

// ───────────────────────── mapa del negocio ─────────────────────────

function ficha(U, t, abrir) {
  const { el, icono } = U;
  const est = T.ESTADOS[t.estado.clave];
  const q = T.QUIENES[t.quien];
  return el('li', null, el('button', {
    type: 'button', class: 't1-ficha', 'data-id': t.id, 'data-estado': t.estado.clave, 'data-abierta': sesion.abierta === t.id ? '1' : '0',
    'aria-label': `${t.titulo}. ${est.texto}${t.estado.origen === 'marca' ? ' (marcada por ti)' : ''}. ${q.texto}. Ver cómo hacerla`,
    title: t.porQue, onclick: () => abrir(t.id),
  },
  el('span', { class: 't1-ficha__ic', 'aria-hidden': 'true' }, icono(est.icono, { tam: 16 })),
  el('span', { class: 't1-ficha__titulo' }, t.titulo),
  el('span', { class: 't1-ficha__pie' }, el('span', { class: 't1-ficha__estado' }, est.texto), el('span', { class: 't1-ficha__quien' }, icono(q.icono, { tam: 11 }), q.texto), t.demo ? el('span', { class: 't1-ficha__quien' }, 'Demo') : null)));
}

function vistaMapa(U, modelo, fs, abrir) {
  const { el, icono } = U;
  const ids = new Set(fs.map((t) => t.id));
  return el('div', { class: 't1-mapa', tabindex: '0', role: 'region', 'aria-label': 'Mapa del negocio: los 6 momentos de izquierda a derecha. Se desplaza hacia los costados.' },
    el('div', { class: 't1-camino' }, modelo.momentos.map((m, i) => {
      const visibles = m.tareas.filter((t) => ids.has(t.id));
      return el('section', { class: 't1-col', 'data-momento': String(m.id), 'aria-label': `Momento ${m.id}: ${m.titulo}` },
        el('header', { class: 't1-col__cab' },
          el('span', { class: 't1-col__num', 'aria-hidden': 'true' }, String(m.id)),
          el('h2', { class: 't1-col__titulo' }, m.titulo),
          i < modelo.momentos.length - 1 ? el('span', { class: 't1-col__flecha', 'aria-hidden': 'true' }, icono('flecha-derecha', { tam: 16 })) : null,
          el('div', { class: 't1-col__cuenta' }, el('span', null, `${m.conteo.hechas} de ${m.conteo.total} hechas`),
            barra(U, { datos: m.tareas.filter((t) => t.estado.clave === 'hecha' && t.estado.origen !== 'marca').length, marca: m.tareas.filter((t) => t.estado.origen === 'marca').length, total: m.conteo.total, etiqueta: `Momento ${m.id}: ${m.conteo.hechas} de ${m.conteo.total} hechas` }))),
        visibles.length ? el('ul', { class: 't1-col__lista' }, visibles.map((t) => ficha(U, t, abrir))) : el('p', { class: 't1-tenue t1-sub' }, 'Sin tareas con este filtro.'));
    })));
}

// ───────────────────────── detalle técnico general ─────────────────────────

function detalleGeneral(U, lecturas, oferta, modelo) {
  const { el, kv } = U;
  const filas = Object.keys(RUTAS).map((n) => {
    const l = lecturas[n];
    return [ETIQUETA_LECTURA[n], l.ok ? (l.vacio ? 'respondió vacío (la fuente aún no existe)' : 'leído') : `no se pudo leer (${(l.err && (l.err.codigo || l.err.name)) || 'error'})`];
  });
  if (oferta) filas.push(['Oferta elegida', `${oferta.id}${oferta.demo ? ' (demostración)' : ''}: ${lecturas.oferta.ok ? 'leída' : 'no se pudo leer'}`]);
  return el('div', { class: 't1-pila' },
    el('p', { class: 't1-sub' }, `Cada tarea declara cómo se sabe su estado (función pura sobre estas lecturas). Lo que figura como «Todavía no existe» se comprobó contra el repositorio el ${T.FECHA_PLAN} y se actualiza cuando aparece el archivo que lo produce.`),
    kv(filas),
    el('p', { class: 't1-sub' }, `${modelo.tareas.length} tareas en el catálogo. Las marcas personales se guardan solo en este navegador (${T.CLAVE_MARCAS}).`));
}

// ───────────────────────── panel lateral «Cómo hacerla» ─────────────────────────

function crearPanel(ctx, { tarea, accionesServidor, contexto, abrirOtra, alternarMarca, enfocarOrigen, alCerrar }) {
  const U = ctx.ui;
  const { el, icono } = U;
  const d = document;
  const previo = d.activeElement;
  let cerrado = false;
  let actual = tarea;
  const corridas = new Map(); // idAccion → {jobId, desde, texto, terminado, codigo, estado, temporizador, fallos}
  const tid = `t1-pan-t-${Math.random().toString(36).slice(2, 8)}`;

  const hEstado = el('div', { class: 't1-pila' });
  const hPasos = el('div', { class: 't1-bloque' });
  const hAcciones = el('div', { class: 't1-bloque' });
  const cuerpoEl = el('div', { class: 't1-pan__cuerpo' });
  const chipsEl = el('div', { class: 't1-pan__chips' });
  const tituloEl = el('h2', { class: 't1-pan__titulo', id: tid });

  const caja = el('aside', { class: 't1-pan', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': tid, tabindex: '-1' },
    el('header', { class: 't1-pan__cab' },
      el('div', { class: 't1-pila' }, el('p', { class: 't1-pan__rotulo' }, 'Cómo hacerla'), tituloEl, chipsEl),
      el('button', { type: 'button', class: 'btn btn--icono', 'aria-label': 'Cerrar el panel', onclick: () => cerrar() }, icono('cerrar'))),
    cuerpoEl,
    el('footer', { class: 't1-pan__pie' }, el('button', { type: 'button', class: 'btn', onclick: () => cerrar() }, 'Cerrar')));
  const fondo = el('div', { class: 't1-pan-fondo', onmousedown: (ev) => { if (ev.target === fondo) cerrar(); } }, caja);

  const FOCALIZABLES = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';
  function alTecla(ev) {
    if (ev.key === 'Escape') {
      if (d.querySelector('.modal-fondo')) return;
      ev.stopPropagation(); cerrar(); return;
    }
    if (ev.key !== 'Tab' || d.querySelector('.modal-fondo')) return;
    const f = [...caja.querySelectorAll(FOCALIZABLES)].filter((x) => x.offsetParent !== null);
    if (!f.length) { ev.preventDefault(); caja.focus(); return; }
    const primero = f[0]; const ultimo = f[f.length - 1];
    if (ev.shiftKey && (d.activeElement === primero || d.activeElement === caja)) { ev.preventDefault(); ultimo.focus(); }
    else if (!ev.shiftKey && d.activeElement === ultimo) { ev.preventDefault(); primero.focus(); }
  }

  function cerrar({ silencioso = false } = {}) {
    if (cerrado) return;
    cerrado = true;
    for (const c of corridas.values()) clearTimeout(c.temporizador);
    d.removeEventListener('keydown', alTecla, true);
    if (fondo.parentNode) fondo.parentNode.removeChild(fondo);
    if (!silencioso) alCerrar();
    const destino = previo && previo.isConnected ? previo : (typeof enfocarOrigen === 'function' ? enfocarOrigen() : null);
    if (destino && typeof destino.focus === 'function') { try { destino.focus(); } catch (_) { /* el nodo ya no existe */ } }
  }

  // ── secciones ──
  function pintarEncabezado() {
    const t = actual; const m = momentoDe(t.momento);
    tituloEl.textContent = t.titulo;
    U.reemplazar(chipsEl, U.chip(`Momento ${m.id} · ${m.corto}`, 'neutro', { icono: m.icono }), chipQuien(U, t.quien), chipEstado(U, t.estado.clave, { marca: t.estado.origen === 'marca' }), t.demo ? chipDemo(U) : null);
  }

  function pintarEstado() {
    const t = actual; const e = t.estado; const def = T.ESTADOS[e.clave];
    const marca = e.origen === 'marca';
    const partes = [
      el('div', { class: 't1-estado-caja', 'data-estado': e.clave },
        el('p', { class: 't1-estado-caja__frase' }, icono(def.icono, { tam: 16 }), el('span', null, el('strong', null, `${def.texto}. `), e.evidencia || def.frase)),
        e.detalle ? el('p', { class: 't1-sub' }, el('strong', null, 'Qué falta: '), e.detalle) : null,
        t.cuando ? el('p', { class: 't1-sub' }, icono('reloj', { tam: 12 }), ' ', el('strong', null, 'Cuándo: '), t.cuando) : null,
        e.clave === 'bloqueada' && e.bloqueadaPor.length ? el('div', { class: 't1-fila' }, e.bloqueadaPor.map((b) => el('button', { type: 'button', class: 'btn btn--chico', onclick: () => abrirOtra(b.id) }, icono('candado', { tam: 12 }), `Primero: ${b.titulo}`))) : null,
        e.marcable ? el('div', { class: 't1-marca' },
          el('button', { type: 'button', class: 'btn', onclick: () => alternarMarca(t) }, icono(marca ? 'x-circulo' : 'check', { tam: 14 }), marca ? 'Quitar mi marca' : 'Marcar como hecha'),
          el('span', { class: 't1-marca__nota' }, marca ? `La marcaste el ${T.fechaCorta(e.marcadaEn)}. Solo para ti: no cambia el sistema.` : `Solo para ti: no cambia el sistema. ${textoPeriodo(t.periodo)}`)) : null),
      e.alerta ? aviso(U, 'aviso', 'alerta', e.alerta) : null,
    ];
    U.reemplazar(hEstado, partes);
  }

  function bloquePaso(p) {
    return el('li', { class: 't1-paso' }, el('div', { class: 't1-paso__cuerpo' },
      p.texto ? el('p', { class: 't1-paso__texto' }, p.texto) : null,
      p.enlace ? el('div', { class: 't1-fila' }, U.enlace(p.enlace.texto, p.enlace.ruta)) : null,
      p.comando ? U.comando(p.comando, { titulo: p.tituloComando || 'Copiar el comando', nota: p.nota }) : null));
  }

  function pintarPasos() {
    const t = actual;
    U.reemplazar(hPasos, el('h3', { class: 't1-bloque__titulo' }, 'Pasos'),
      t.pasos.length ? el('ol', { class: 't1-pasos' }, t.pasos.map(bloquePaso)) : el('p', { class: 't1-sub' }, 'Esta tarea todavía no tiene pasos para seguir.'));
  }

  // ── acciones seguras: «Ejecutar ahora» ──
  function pintarAcciones() {
    const lista = T.accionesDeTarea(actual, contexto(), accionesServidor);
    if (!lista.length) { U.limpiar(hAcciones); hAcciones.hidden = true; return; }
    hAcciones.hidden = false;
    U.reemplazar(hAcciones, el('h3', { class: 't1-bloque__titulo' }, 'Comprobar ahora'), lista.map((a) => tarjetaAccion(a)));
  }

  function tarjetaAccion(a) {
    const run = corridas.get(a.id) || null;
    const corriendo = Boolean(run && !run.terminado);
    const resHost = el('div'); const salidaHost = el('div');
    const btn = el('button', { type: 'button', class: 'btn', 'data-accion': a.id, disabled: !a.disponible || corriendo ? true : null, onclick: () => ejecutar(a) }, icono('play', { tam: 13 }), corriendo ? 'Ejecutando…' : 'Ejecutar ahora');
    const c = el('div', { class: 't1-accion', 'data-accion': a.id },
      el('strong', null, a.etiqueta), el('p', { class: 't1-accion__quehace' }, a.quehace),
      el('div', { class: 't1-accion__fila' }, btn, a.disponible ? el('span', { class: 't1-sub t1-tenue' }, 'Solo lee y te muestra el resultado.') : el('span', { class: 't1-sub' }, a.motivo)),
      resHost, salidaHost);
    c._res = resHost; c._salida = salidaHost; c._boton = btn;
    if (run) pintarCorrida(a.id, c);
    return c;
  }

  function nodoAccion(id) { return hAcciones.querySelector ? hAcciones.querySelector(`.t1-accion[data-accion="${id}"]`) : null; }

  function pintarCorrida(id, nodo) {
    const c = nodo || nodoAccion(id);
    const run = corridas.get(id);
    if (!c || !run) return;
    const r = T.resultadoEnSimple(id, run.terminado ? { terminado: true, codigo: run.codigo, estado: run.estado } : null);
    U.reemplazar(c._res, el('div', { class: 't1-res', 'data-clave': r.clave, role: 'status' }, icono(r.icono, { tam: 16 }), el('div', null, el('p', { class: 't1-res__titulo' }, r.titulo), el('p', { class: 't1-res__texto' }, r.texto))));
    const pre = el('pre', { class: 't1-salida', tabindex: '0', role: 'log', 'aria-label': 'Salida completa de la comprobación' });
    pre.textContent = run.texto || '(sin salida todavía)';
    U.reemplazar(c._salida, U.detalleTecnico('Detalle técnico: lo que respondió', pre));
    c._boton.disabled = !run.terminado;
    U.reemplazar(c._boton, icono('play', { tam: 13 }), run.terminado ? 'Volver a ejecutar' : 'Ejecutando…');
  }

  async function ejecutar(a) {
    const def = T.ACCIONES_SEGURAS[a.id];
    if (!def || !a.disponible || !a.args) return; // nada fuera de la lista blanca, y solo de solo lectura
    const previa = corridas.get(a.id);
    if (previa && !previa.terminado) return;
    const run = { jobId: null, desde: 0, texto: '', terminado: false, codigo: null, estado: null, temporizador: null, fallos: 0 };
    corridas.set(a.id, run);
    pintarCorrida(a.id);
    try {
      const resp = await ctx.api.post('/accion', { id: a.id, args: a.args });
      const id = resp && (resp.job_id || resp.id);
      if (!id) throw new Error('El servidor no devolvió el número de la ejecución.');
      run.jobId = String(id);
      if (resp.comando) run.texto = `$ ${resp.comando}\n`;
      pintarCorrida(a.id);
      run.temporizador = setTimeout(() => sondear(a.id), 250);
    } catch (err) {
      run.terminado = true; run.codigo = null; run.estado = 'error';
      run.texto = `No se pudo ejecutar: ${(err && (err.mensaje || err.message)) || 'error desconocido'}`;
      const c = nodoAccion(a.id);
      if (c) {
        U.reemplazar(c._res, el('div', { class: 't1-res', 'data-clave': 'error', role: 'alert' }, icono('alerta', { tam: 16 }), el('div', null, el('p', { class: 't1-res__titulo' }, 'No se pudo ejecutar'), el('p', { class: 't1-res__texto' }, err && err.codigo === 'accion_en_curso' ? 'Ya hay una ejecución de esto en marcha. Espera a que termine.' : 'El servidor no la aceptó. Prueba de nuevo en unos segundos.'))));
        const pre = el('pre', { class: 't1-salida', tabindex: '0' }); pre.textContent = run.texto;
        U.reemplazar(c._salida, U.detalleTecnico('Detalle técnico: lo que respondió', pre));
        c._boton.disabled = false; U.reemplazar(c._boton, icono('play', { tam: 13 }), 'Volver a ejecutar');
      }
    }
  }

  async function sondear(id) {
    const run = corridas.get(id);
    if (!run || cerrado || run.terminado) return;
    try {
      const resp = await ctx.api.get(`/job/${encodeURIComponent(run.jobId)}`, { desde: run.desde });
      run.fallos = 0;
      const j = T.normalizarJob(resp, run.desde);
      run.texto = (run.texto + j.texto).slice(-MAX_SALIDA);
      run.desde = j.siguiente;
      if (j.terminado) { run.terminado = true; run.codigo = j.codigo; run.estado = j.estado; }
    } catch (_) {
      run.fallos += 1;
      if (run.fallos >= MAX_FALLOS_JOB) { run.terminado = true; run.codigo = null; run.estado = 'error'; run.texto += '\n[el panel perdió el seguimiento de la ejecución]\n'; }
    }
    if (cerrado) return;
    pintarCorrida(id);
    if (!run.terminado) run.temporizador = setTimeout(() => sondear(id), INTERVALO_JOB_MS);
  }

  // ── cuerpo completo ──
  function armarCuerpo() {
    const t = actual;
    const bloques = [];
    bloques.push(el('div', { class: 't1-bloque' }, el('h3', { class: 't1-bloque__titulo' }, 'Por qué importa'), el('p', null, t.porQue),
      t.terminos.length ? el('p', { class: 't1-terminos' }, 'Palabras clave: ', t.terminos.map((x, i) => [i ? ' · ' : '', U.termino(x.clave, { texto: x.texto })])) : null));
    bloques.push(el('div', { class: 't1-bloque' }, el('h3', { class: 't1-bloque__titulo' }, 'Cómo se sabe'), hEstado));
    if (t.hoyObjetivo) {
      const h = t.hoyObjetivo;
      bloques.push(el('div', { class: 't1-bloque' }, el('h3', { class: 't1-bloque__titulo' }, 'Hoy y objetivo'), el('div', { class: 't1-ho' },
        el('div', { class: 't1-ho__caja' }, el('span', { class: 't1-ho__etiqueta t1-ho__etiqueta--hoy' }, icono('ok', { tam: 12 }), 'Hoy'), el('p', { class: 't1-ho__texto' }, h.hoy.texto), el('p', { class: 't1-ho__fuente' }, h.hoy.fuente)),
        el('div', { class: 't1-ho__caja t1-ho__caja--objetivo' }, el('span', { class: 't1-ho__etiqueta t1-ho__etiqueta--objetivo' }, icono('diana', { tam: 12 }), 'Objetivo'), el('p', { class: 't1-ho__texto' }, h.objetivo.texto), el('p', { class: 't1-ho__fuente' }, h.objetivo.fuente)))));
    }
    if (t.avisoPlan) bloques.push(aviso(U, 'aviso', 'alerta', t.avisoPlan));
    bloques.push(hPasos);
    bloques.push(hAcciones);
    if (t.donde.length) {
      bloques.push(el('div', { class: 't1-bloque' }, el('h3', { class: 't1-bloque__titulo' }, 'Dónde se ve'), el('ul', { class: 't1-donde' }, t.donde.map((x) => el('li', null, U.enlace(x.texto, x.ruta))))));
    }
    const tecnico = [['Identificador de la tarea', t.id], ['Quién la hace', T.QUIENES[t.quien].texto], ['De dónde sale el estado', { datos: 'Una lectura de datos reales', marca: 'Tu marca personal (solo en este navegador)', plan: 'El plan, comprobado contra el repositorio', dependencia: 'Otra tarea que falta', sin_datos: 'No hay dato que lo diga' }[t.estado.origen] || t.estado.origen], ...t.tecnico];
    if (T.CONSTRUCCION[t.id]) tecnico.push(['Según el plan', T.CONSTRUCCION[t.id].segun]);
    bloques.push(U.detalleTecnico('Detalle técnico', () => U.kv(tecnico.map(([k, v]) => [k, typeof v === 'string' ? el('span', null, v) : v]))));
    U.reemplazar(cuerpoEl, bloques);
  }

  function actualizar(nueva) {
    actual = nueva;
    pintarEncabezado(); pintarEstado(); pintarPasos(); pintarAcciones();
    // el cuerpo ya está armado: solo cambian estado, pasos y acciones
  }

  d.addEventListener('keydown', alTecla, true);
  d.body.appendChild(fondo);
  pintarEncabezado(); armarCuerpo(); pintarEstado(); pintarPasos(); pintarAcciones();
  try { caja.focus(); } catch (_) { /* sin foco */ }

  return { id: tarea.id, cerrar, actualizar, enfocar: () => { try { caja.focus(); } catch (_) { /* sin foco */ } }, elemento: fondo };
}
