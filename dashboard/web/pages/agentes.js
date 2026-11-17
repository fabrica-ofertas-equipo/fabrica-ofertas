// pages/agentes.js — #/agentes: qué agentes corrieron, en qué etapa y oferta, cuánto costaron frente al tope por corrida y cómo terminaron
// (CONTRATO §4 `GET /agentes[/<ejecucion_id>]`; rediseño U4). Fuente: empresa/registro.jsonl (+ costos.jsonl) agrupado por ejecución.
// Solo lectura. Sin dato ⇒ «—» o «sin dato» (nunca 0): una ejecución de una sola línea no tiene duración medible; sin costo registrado no es costo 0.

import { ayudasVista, instalarEstilos } from '../lib/operacion.js';
import { rotuloEvento } from '../lib/registro.js';
import { graficoSerie, barrasRanking } from '../lib/graficos.js';
import {
  modeloAgentes, filtrarEjecuciones, normalizarEjecucion, normalizarEvento, fuenteEsDemo, comandosAgentes, usoCorrida,
  MODOS_HUMANOS, estadoEjecucion, nombreAgente, nombreAgenteCorto, nombreEtapa, puntosRonda, serieCostoPorCorrida, atencionAgentes,
} from '../lib/agentes.js';

export const meta = { ruta: 'agentes', titulo: 'Equipo de IA', grupo: 'Robots', icono: 'robot', escucha: ['registro'] };

const enc = encodeURIComponent;
// Estado de la interfaz que sobrevive a una actualización en vivo.
const UI = { filtros: { oferta: '', etapa: '', agente: '', modo: '', estado: '' } };

function hayEdicion() {
  const d = globalThis.document;
  const a = d && d.activeElement;
  return Boolean(a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) || Boolean(d && d.querySelector('.modal-fondo'));
}

async function leerOpcional(api, ruta, params) { try { return await api.sobre(ruta, params); } catch (_) { return null; } }

const botonActualizar = (ctx) => ctx.ui.el('button', { type: 'button', class: 'btn btn--chico', onclick: () => ctx.recargar() }, ctx.ui.icono('refrescar', { tam: 14 }), 'Actualizar');
const sumaTexto = (fmt, lista) => (lista.length ? lista.map((c) => fmt.dinero(c.monto, c.moneda)).join(' + ') : null);

function chipEstado(ui, e) {
  const info = estadoEjecucion(e);
  return ui.chip(info.texto, info.tono, { icono: info.icono });
}

function chipModo(ui, modo) {
  const info = MODOS_HUMANOS[modo];
  return info ? ui.termino(info.clave, { texto: info.texto }) : null;
}

// ───────────────────────── métricas ─────────────────────────

function metricas(ctx, m) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const c = m.costos;
  const malas = m.ejecuciones.filter((e) => e.estado === 'error' || e.estado === 'bloqueado').length;
  const t = m.tope;
  return el('div', { class: 'p5-metricas' },
    ui.metrica({ etiqueta: 'Ejecuciones', valor: fmt.num(m.ejecuciones.length), ayuda: 'ejecucion_agente', contexto: el('span', { class: 'p5-sub' }, `${m.filtros.agentes.length} agentes · ${m.filtros.etapas.length} etapas`) }),
    ui.metrica({
      etiqueta: 'Costo acumulado', valor: sumaTexto(fmt, c.total), ayuda: 'costo_ia', tono: c.sinCosto ? 'aviso' : null,
      contexto: el('span', { class: 'p5-sub' }, c.sinCosto ? `${c.sinCosto} ejecución(es) sin costo registrado: no cuentan como 0` : 'Todas con costo registrado'),
    }),
    ui.metrica({ etiqueta: 'Con error o bloqueo', valor: fmt.num(malas), tono: malas ? 'critico' : 'ok', contexto: el('span', { class: 'p5-sub' }, malas ? 'Revisa la línea de eventos de cada una' : 'Ninguna ejecución falló') }),
    ui.metrica({
      etiqueta: 'Tope por ejecución', ayuda: 'tope_corrida', valor: t.tope === null ? el('span', { class: 'cifra-sin-dato' }, t.estado === 'sin_limites' ? 'sin dato' : 'sin fijar') : fmt.dinero(t.tope, t.moneda || 'EUR'),
      tono: t.tope === null ? 'aviso' : c.excedidas ? 'critico' : 'ok',
      contexto: el('span', { class: 'p5-sub' }, t.estado === 'sin_limites' ? 'No se pudieron leer los límites' : t.tope === null ? 'Sin tope fijado, ningún agente puede gastar' : `${c.excedidas} ejecución(es) lo superan`),
    }));
}

// ───────────────────────── detalle de una ejecución (modal) ─────────────────────────

const TONO_EVENTO = { ok: 'ok', error: 'error', bloqueado: 'error', dry_run: 'aviso' };
/** Resultado de una revisión de calidad en palabras (el código crudo PASS/FAIL no se muestra). */
const VEREDICTO_REVISION = { PASS: 'Aprobado', PASS_CON_NOTAS: 'Aprobado con notas', FAIL: 'Rechazado', ESCALAR: 'Pasó a tu decisión', BLOCK: 'Bloqueado', REVISAR: 'Pidió revisar' };

function lineaEvento(ctx, e) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const tono = TONO_EVENTO[e.estado] || 'aviso';
  return el('li', { class: `p5-evento p5-evento--${tono}` },
    el('div', { class: 'p5-evento__cab' },
      e.ts ? ui.tiempo(e.ts) : el('span', { class: 'texto-tenue' }, '—'),
      e.evento ? ui.chip(rotuloEvento(e.evento), 'info', { icono: false }) : null,
      e.agente ? el('strong', null, nombreAgente(e.agente)) : null,
      e.etapa ? el('span', { class: 'p5-sub' }, nombreEtapa(e.etapa)) : null,
      e.estado ? chipEstado(ui, e.estado) : ui.chip('Sin resultado', 'neutro', { icono: false }),
      e.costo ? el('span', { class: 'p5-sub' }, fmt.dinero(e.costo.monto, e.costo.moneda)) : null,
      e.modo ? chipModo(ui, e.modo) : null),
    e.entrada_resumen ? el('div', { class: 'p5-evento__texto' }, e.entrada_resumen) : null,
    e.herramienta || e.hash || e.codigo !== null
      ? ui.detalleTecnico('Datos técnicos del paso', ui.kv([
        ['Número de línea del historial', el('span', { class: 'p5-mono' }, `#${e.n}`)], ['Herramienta usada', e.herramienta], ['Código de resultado', e.codigo === null ? null : String(e.codigo)],
        ['Hora exacta', e.ts ? fmt.fecha(e.ts, { segundos: true }) : null], ['Huella del historial', e.hash ? el('span', { class: 'p5-mono' }, e.hash) : null]]))
      : null);
}

async function cargarDetalle(ctx, fila, cont) {
  const { api, ui, fmt } = ctx;
  const { el } = ui;
  const ayudas = ayudasVista(ui, fmt);
  const [det, of] = await Promise.allSettled([
    api.sobre(`/agentes/${enc(fila.ejecucion_id)}`),
    fila.oferta_id ? leerOpcional(api, `/oferta/${enc(fila.oferta_id)}`) : Promise.resolve(null),
  ]);
  let eventos = fila.eventos;
  let sobre = null;
  let cabecera = fila;
  if (det.status === 'fulfilled') {
    sobre = det.value;
    const d = sobre.datos;
    const lista = d && Array.isArray(d.eventos) ? d.eventos : (Array.isArray(d) ? d : null);
    if (lista) eventos = lista.map(normalizarEvento).filter(Boolean);
    const norm = d && !Array.isArray(d) ? normalizarEjecucion({ ...d, eventos: lista || d.eventos }, { ofertasDemo: new Set((ctx.estado.ofertas || []).filter((o) => o && o.demo).map((o) => o.oferta_id)), demo: fuenteEsDemo(sobre.fuente) }) : null;
    if (norm) cabecera = { ...fila, ...norm, ronda: fila.ronda, uso: fila.uso };
  } else if (!eventos) {
    ui.reemplazar(cont, ui.errorBox(det.reason, { reintentar: () => { ui.reemplazar(cont, ui.esqueleto('texto')); cargarDetalle(ctx, fila, cont); } }));
    return;
  }
  const etapaDe = cabecera.etapa;
  const qa = of.status === 'fulfilled' && of.value && of.value.datos && Array.isArray(of.value.datos.etapas) ? of.value.datos.etapas.find((e) => e.id === etapaDe) : null;
  const eventosOrden = [...(eventos || [])].sort((a, b) => String(a.ts || '').localeCompare(String(b.ts || '')) || a.n - b.n);
  const sd = (t) => el('span', { class: 'cifra-sin-dato' }, t);
  const resumen = ui.kv([
    ['Oferta', cabecera.oferta_id || 'empresa (sin oferta)'],
    ['Etapa', cabecera.etapas.length ? cabecera.etapas.map(nombreEtapa).join(', ') : null],
    ['Agentes', cabecera.agentes.length ? cabecera.agentes.map(nombreAgente).join(', ') : null],
    ['Modo', cabecera.modo ? chipModo(ui, cabecera.modo) : null],
    ['Resultado', cabecera.estado ? chipEstado(ui, cabecera.estado) : null],
    ['Cuándo', cabecera.inicio ? `${fmt.fecha(cabecera.inicio, { segundos: true })} → ${cabecera.fin ? fmt.fecha(cabecera.fin, { segundos: true }) : 'sin fin'}` : null],
    ['Duración', cabecera.duracionMs === null ? sd('sin dato') : fmt.duracion(cabecera.duracionMs)],
    ['Costo', cabecera.costo ? fmt.dinero(cabecera.costo.monto, cabecera.costo.moneda) : sd('sin costo registrado')],
    ['Rondas de revisión', fila.ronda === null ? sd('sin dato') : String(fila.ronda)],
  ]);
  const bloqueQa = qa
    ? el('div', { class: 'p5-pila' }, el('h3', { class: 'p5-titulo-chico' }, `Revisión de calidad de la etapa ${nombreEtapa(etapaDe)} en esta oferta`),
      ui.kv([['Ronda', qa.ronda_qa === null || qa.ronda_qa === undefined ? null : String(qa.ronda_qa)], ['Intentos', qa.intentos === null || qa.intentos === undefined ? null : String(qa.intentos)], ['Estado de la etapa', qa.estado ? ui.estadoIcono(qa.estado) : null]]),
      Array.isArray(qa.qa) && qa.qa.length ? el('ul', { class: 'p5-checks' }, qa.qa.map((x) => el('li', null, ui.chip(VEREDICTO_REVISION[x.veredicto] || x.veredicto || '—', x.veredicto === 'PASS' ? 'ok' : x.veredicto === 'FAIL' ? 'error' : 'aviso'), ` ${x.archivo || ''}${x.resumen ? ` — ${x.resumen}` : ''}`))) : null)
    : null;
  ui.reemplazar(cont, el('div', { class: 'p5-pila' },
    el('div', { class: 'rejilla-2' },
      el('div', { class: 'p5-pila' }, el('h3', { class: 'p5-titulo-chico' }, 'Resumen'), resumen, bloqueQa),
      el('div', { class: 'p5-pila' }, el('h3', { class: 'p5-titulo-chico' }, `Qué pasó, paso a paso (${eventosOrden.length})`),
        eventosOrden.length ? el('ol', { class: 'p5-linea-tiempo' }, eventosOrden.map((e) => lineaEvento(ctx, e)))
          : ayudas.vacioConComandos('Esta ejecución no trae pasos.', { pista: 'El panel recibió solo el resumen; el detalle de cada paso está en el historial de todo lo que hace el sistema.', archivo: 'empresa/registro.jsonl' }))),
    ui.detalleTecnico('Identificadores internos', ui.kv([['Ejecución', el('span', { class: 'p5-mono' }, cabecera.ejecucion_id)], ['Agentes (nombres internos)', cabecera.agentes.join(', ') || null], ['Etapas (códigos)', cabecera.etapas.join(', ') || null]])),
    sobre ? ui.fuenteInfo(sobre) : null));
}

function abrirDetalle(ctx, fila) {
  const { ui } = ctx;
  const cont = ui.el('div', { class: 'p5-pila' }, ui.esqueleto('texto'));
  ui.modal({ titulo: `${nombreAgente(fila.agente)} · ${nombreEtapa(fila.etapa)}`, cuerpo: cont, ancho: '980px', acciones: [{ texto: 'Cerrar' }] });
  cargarDetalle(ctx, fila, cont);
}

// ───────────────────────── gráfico y lista de ejecuciones ─────────────────────────

function seccionGrafico(ctx, m) {
  const { ui, fmt } = ctx;
  if (!m.hayDatos) return null;
  const { serie, moneda } = serieCostoPorCorrida(m.ejecuciones, m.tope.moneda);
  if (!moneda) return null;
  const dinero = (v) => fmt.dinero(Math.round(v), moneda);
  const tope = m.tope.tope !== null && (!m.tope.moneda || m.tope.moneda === moneda) ? m.tope.tope : null;
  const otraMoneda = m.ejecuciones.filter((e) => e.costo && e.costo.moneda !== moneda).length;
  return ui.seccion('Costo de cada ejecución', graficoSerie(ui, {
    titulo: 'Lo que costó cada ejecución', subtitulo: `${tope !== null ? 'Una columna por ejecución, frente al tope por ejecución' : 'Una columna por ejecución · sin tope por ejecución fijado'}${otraMoneda ? ` · ${otraMoneda} en otra moneda no se dibuja` : ''}`, serie, tipo: 'barras',
    formato: dinero, formatoEje: (v) => dinero(v).replace(',00', ''), columna: 'Costo', referencias: tope !== null ? [{ valor: tope, etiqueta: `tope ${dinero(tope)}` }] : [], alto: 170,
  }), { glosario: 'tope_corrida', ayuda: 'Las ejecuciones sin costo registrado no se dibujan: no son un costo 0.' });
}

function ritmoRondas(ui, ronda) {
  const { el } = ui;
  const puntos = puntosRonda(ronda);
  if (!puntos) return el('span', { class: 'cifra-sin-dato', title: 'Ningún agente de revisión en esta etapa' }, '—');
  return el('span', { class: 'p5-rondas', title: `${ronda} ${ronda === 1 ? 'ronda' : 'rondas'} de revisión`, role: 'img', 'aria-label': `${ronda} rondas de revisión` }, puntos.map((p) => el('span', { class: p.llena ? 'p5-ronda' : 'p5-ronda p5-ronda--vacia' })), el('span', { class: 'p5-sub' }, ` ${ronda}`));
}

function seccionEjecuciones(ctx, m, ayudas, sobre) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  if (!m.hayDatos) {
    return ui.seccion('Ejecuciones', ayudas.vacioConComandos('Todavía no hay ejecuciones de agentes en el historial.', {
      pista: 'Cada vez que un agente (un ayudante de IA) trabaja, queda anotado en el historial, con su costo. Aquí se agrupa por ejecución: quién fue, en qué etapa, cuánto costó y cómo terminó.',
      archivo: 'empresa/registro.jsonl',
      comandos: [{ etiqueta: 'Comprobar que el historial no fue alterado (solo mira, no cambia nada)', cmd: comandosAgentes().verificar }],
      fuente: sobre ? sobre.fuente : undefined,
    }), { glosario: 'ejecucion_agente' });
  }
  const opciones = (lista, actual, etiqueta, nombre) => [el('option', { value: '' }, etiqueta), ...lista.map((x) => el('option', { value: x, selected: x === actual ? true : null }, nombre ? nombre(x) : x))];
  const f = m.filtros;
  const aplicar = () => filtrarEjecuciones(m.ejecuciones, UI.filtros);
  const tabla = ui.tabla({
    etiqueta: 'Ejecuciones de agentes', filtro: { placeholder: 'Buscar por agente, etapa u oferta…' }, maxFilas: 200, filas: aplicar(), ordenInicial: { clave: 'inicio', dir: 'desc' },
    vacio: 'Ninguna ejecución con estos filtros.', claseFila: (x) => (x.estado === 'error' || x.estado === 'bloqueado' ? 'fila-error' : x.uso && x.uso.excede ? 'fila-aviso' : ''),
    alClick: (x) => abrirDetalle(ctx, x),
    columnas: [
      { clave: 'inicio', titulo: 'Cuándo', formato: (v) => (v ? ui.tiempo(v) : '—') },
      { clave: 'agentes', titulo: 'Agente', clase: 'cel-larga', orden: (x) => x.agentes.join(','), formato: (v, x) => el('span', { class: 'p5-pila p5-pila--chica' },
        x.agentes.length ? el('span', { title: x.agentes.map(nombreAgente).join(', ') }, [...new Set(x.agentes.map(nombreAgenteCorto))].join(', ')) : '—', ui.soloTecnico(el('span', { class: 'p5-mono' }, x.ejecucion_id))) },
      { clave: 'etapas', titulo: 'Etapa', orden: (x) => x.etapas.join(','), formato: (v, x) => (x.etapas.length ? el('span', { class: 'p5-fila p5-fila--junta' }, x.etapas.map((e) => el('span', null, nombreEtapa(e), ' ', el('span', { class: 'p5-dict__codigo' }, e)))) : '—') },
      { clave: 'oferta_id', titulo: 'Oferta', formato: (v) => v || el('span', { class: 'texto-tenue' }, 'empresa') },
      { clave: 'estado', titulo: 'Resultado', formato: (v) => (v ? chipEstado(ui, v) : el('span', { class: 'cifra-sin-dato' }, 'sin dato')) },
      { clave: 'costo', titulo: 'Costo frente al tope', alinear: 'der', orden: (x) => (x.costo ? x.costo.monto : null), ancho: '190px',
        formato: (v, x) => {
          if (!x.costo) return el('span', { class: 'cifra-sin-dato', title: 'El historial no trae costo de esta ejecución' }, 'sin costo');
          const u = x.uso;
          return el('span', { class: 'p5-mini' },
            el('span', { class: 'p5-num' }, fmt.dinero(x.costo.monto, x.costo.moneda), u && u.excede ? [' ', ui.chip('Excede el tope', 'error')] : null),
            u && u.estado === 'ok' ? ayudas.medidor({ bp: Math.min(10000, u.bp), zona: u.excede ? 'rojo' : u.bp >= 8000 ? 'aviso' : 'ok', texto: u.excede ? `${fmt.pct(u.bp)} del tope` : `${fmt.pct(u.bp)} del tope`, etiqueta: 'Costo frente al tope por ejecución' })
              : (u && u.estado === 'sin_tope' ? el('span', { class: 'p5-sub' }, 'sin tope fijado') : null));
        } },
      { clave: 'modo', titulo: 'Modo', formato: (v) => (v ? chipModo(ui, v) : el('span', { class: 'cifra-sin-dato' }, 'sin dato')) },
      { clave: 'duracionMs', titulo: 'Duración', alinear: 'der', formato: (v) => (v === null ? el('span', { class: 'cifra-sin-dato', title: 'Hay un solo paso en el historial: no se puede medir' }, '—') : fmt.duracion(v)) },
      { clave: 'ronda', titulo: 'Revisión', formato: (v) => ritmoRondas(ui, v) },
    ],
  });
  const refrescar = () => tabla.actualizarFilas(aplicar());
  const sel = (clave, lista, etiqueta, nombre, aria) => el('select', { class: 'campo campo--chico', 'aria-label': `Filtrar por ${aria}`, onchange: (ev) => { UI.filtros[clave] = ev.target.value; refrescar(); } }, opciones(lista, UI.filtros[clave], etiqueta, nombre));
  const fila = el('div', { class: 'p5-filtros' },
    el('span', { class: 'p5-filtros__etiqueta' }, ui.icono('filtro', { tam: 14 }), 'Filtrar'),
    sel('oferta', f.ofertas, 'Todas las ofertas', null, 'oferta'), sel('etapa', f.etapas, 'Todas las etapas', (x) => `${nombreEtapa(x)} (${x})`, 'etapa'), sel('agente', f.agentes, 'Todos los agentes', nombreAgente, 'agente'),
    sel('modo', f.modos, 'Todos los modos', (x) => (MODOS_HUMANOS[x] ? MODOS_HUMANOS[x].texto : x), 'modo'), sel('estado', f.estados, 'Todos los resultados', (x) => estadoEjecucion(x).texto, 'resultado'));
  return ui.seccion('Ejecuciones', el('div', { class: 'p5-pila' }, fila, tabla,
    el('p', { class: 'p5-sub' }, 'Haz clic en una fila para ver qué pasó paso a paso y cómo salió la revisión de su etapa. «Datos de prueba» = oferta de ejemplo; «Simulado» = no cambió nada; «En real» = con efectos reales.')),
  { glosario: 'ejecucion_agente', ayuda: 'Agrupadas desde el historial de actividad. La duración va del primer al último paso; el costo es una estimación.' });
}

// ───────────────────────── costos acumulados ─────────────────────────

function tablaCostos(ctx, lista, titulo, m, nombre) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  return ui.tabla({
    etiqueta: titulo, filas: lista, vacio: 'Sin datos.',
    columnas: [
      { clave: 'clave', titulo: titulo.includes('agente') ? 'Agente' : 'Etapa', formato: (v) => el('span', null, nombre(v)) },
      { clave: 'ejecuciones', titulo: 'Ejecuciones', alinear: 'der' },
      { clave: 'total', titulo: 'Costo acumulado', alinear: 'der', orden: (g) => (g.total[0] ? g.total[0].monto : null), formato: (v) => sumaTexto(fmt, v) || el('span', { class: 'cifra-sin-dato' }, 'sin costo') },
      { clave: 'maximo', titulo: 'Máx. por ejecución', alinear: 'der', formato: (v) => (v ? fmt.dinero(v.monto, v.moneda) : el('span', { class: 'cifra-sin-dato' }, 'sin dato')) },
      { titulo: 'Contra el tope', ordenable: false, formato: (v, g) => {
        if (m.tope.tope === null) return ui.chip('Sin tope fijado', 'aviso');
        if (!g.maximo) return el('span', { class: 'cifra-sin-dato' }, 'sin dato');
        const u = usoCorrida({ costo: g.maximo }, m.tope);
        if (u.estado === 'moneda_distinta') return el('span', { class: 'cifra-sin-dato' }, 'moneda distinta');
        return g.excedidas ? ui.chip(`${g.excedidas} superan el tope`, 'error') : ui.chip(`Máx. ${fmt.pct(u.bp)} del tope`, u.bp >= 8000 ? 'aviso' : 'ok');
      } },
      { clave: 'sinCosto', titulo: 'Sin costo', alinear: 'der', formato: (v) => (v ? String(v) : '—') },
      { clave: 'errores', titulo: 'Con error', alinear: 'der', formato: (v) => (v ? ui.chip(String(v), 'error') : '—') },
    ],
  });
}

function rankingDe(ctx, lista, nombre, titulo) {
  const { ui, fmt } = ctx;
  const items = lista.filter((g) => g.total.length === 1).map((g) => ({ nombre: nombre(g.clave), valor: g.total[0].monto, texto: fmt.dinero(g.total[0].monto, g.total[0].moneda) }));
  return ui.el('div', { class: 'p5-pila' }, ui.el('h3', { class: 'p5-titulo-chico' }, titulo), barrasRanking(ui, items, { etiqueta: titulo, vacio: 'Todavía no hay costos registrados.' }));
}

function seccionCostos(ctx, m, ayudas) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  if (!m.hayDatos) return null;
  const t = m.tope;
  const aviso = t.tope === null ? ayudas.aviso('aviso', t.estado === 'sin_limites' ? 'No se pudieron leer los límites: no se compara ningún costo con el tope por ejecución.' : 'El tope de costo por ejecución está sin fijar: ninguna ejecución de agente puede gastar hasta que lo fijes en los límites.') : null;
  const nombreEtapaCompleto = (c) => (c === '(sin etapa)' ? c : `${nombreEtapa(c)} (${c})`);
  return ui.seccion('A dónde va el costo', el('div', { class: 'p5-pila' }, aviso,
    el('div', { class: 'p5-graficos p5-graficos--2' },
      el('div', { class: 'p5-viz' }, rankingDe(ctx, m.costos.porAgente, nombreAgente, 'Por agente')),
      el('div', { class: 'p5-viz' }, rankingDe(ctx, m.costos.porEtapa, nombreEtapaCompleto, 'Por etapa'))),
    m.costosArchivo.length ? el('div', { class: 'p5-fila p5-fila--junta' }, el('span', { class: 'p5-sub' }, 'Según el registro de costos, por origen:'), ...m.costosArchivo.map((c) => ui.chip(`${{ ia: 'IA', creditos: 'Créditos', herramienta: 'Herramientas' }[c.origen] || c.origen}: ${fmt.dinero(c.monto, c.moneda)}`, 'neutro', { icono: false }))) : null,
    ui.detalleTecnico('Tablas completas por agente y por etapa', () => el('div', { class: 'p5-pila' },
      el('div', { class: 'p5-pila' }, el('h3', { class: 'p5-titulo-chico' }, 'Por agente'), tablaCostos(ctx, m.costos.porAgente, 'Costos por agente', m, nombreAgente)),
      el('div', { class: 'p5-pila' }, el('h3', { class: 'p5-titulo-chico' }, 'Por etapa'), tablaCostos(ctx, m.costos.porEtapa, 'Costos por etapa', m, nombreEtapaCompleto))))),
  { glosario: 'costo_ia', ayuda: 'Una ejecución que toca varias etapas o agentes suma su costo en cada uno. Las monedas distintas no se suman.' });
}

// ───────────────────────── página ─────────────────────────

export async function render(ctx) {
  const { api, ui, fmt, estado } = ctx;
  const { el } = ui;
  instalarEstilos(ui);
  const ayudas = ayudasVista(ui, fmt);
  const [ag, par] = await Promise.allSettled([api.sobre('/agentes'), leerOpcional(api, '/parametros')]);
  const cab = ui.encabezadoPagina({
    titulo: 'Equipo de IA',
    descripcion: 'Qué agentes (ayudantes de IA) trabajaron, en qué etapa y oferta, cuánto costaron frente a su tope y cómo terminaron. Todo sale del historial de actividad.',
    acciones: [botonActualizar(ctx)],
  });
  if (ag.status === 'rejected') return el('div', { class: 'pagina' }, cab, ui.errorBox(ag.reason, { reintentar: () => ctx.recargar() }));
  const sobre = ag.value;
  const limites = par.status === 'fulfilled' && par.value && par.value.datos ? par.value.datos.limites : null;
  const m = modeloAgentes(sobre.datos, { limites, ofertas: estado.ofertas || [], fuente: sobre.fuente });
  return el('div', { class: 'pagina' }, cab,
    m.hayDatos ? ui.atencion({ items: atencionAgentes(m), vacio: 'Todo en orden: ninguna ejecución falló ni superó su tope.' }) : null,
    m.hayDatos ? metricas(ctx, m) : null,
    seccionGrafico(ctx, m),
    seccionEjecuciones(ctx, m, ayudas, sobre),
    seccionCostos(ctx, m, ayudas),
    ui.fuenteInfo(sobre));
}

/** Actualización en vivo (evento «registro»): re-renderiza conservando filtros, salvo que se esté escribiendo. */
export async function alCambio(ctx) {
  if (hayEdicion()) return undefined;
  return render(ctx);
}
