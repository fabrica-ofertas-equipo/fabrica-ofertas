// pages/cerebro.js — #/cerebro: «Cerebro: lo que el sistema recuerda».
//
// Arriba, el ciclo de cada sesión (abrir → trabajar → cerrar → domingo) y por qué existe: una IA sin memoria arranca de cero cada vez.
// Luego la lista única de PENDIENTES (la misma bitácora de Pulido, ampliada: prioridad, responsable, bloquea, vence), las DECISIONES vigentes
// del dueño (solo se enlazan y se cuentan), las REGLAS (solo lectura: solo el dueño las cambia), las LECCIONES (hallazgos de QA y post-mortems)
// y el JARDÍN del domingo. Lo técnico (rutas y hashes) va en un bloque plegado al final.
//
// Única escritura de esta pantalla: POST /pulido (alta de un pendiente y cambio de estado). Nunca toca reglas, límites, PAUSA ni acciones.
// La lógica vive en lib/cerebro.js (probada sin DOM). Se actualiza en el sitio para no perder filtros, foco ni desplazamiento.

import { ui, el, icono, fmt, limpiar, toast, instalarEstilos } from '../ui.js';
import * as C from '../lib/cerebro.js';
import * as W from '../lib/vistas-ofertas.js';

export const meta = { ruta: 'cerebro', titulo: 'Cerebro', grupo: 'Cerebro', icono: 'cerebro', escucha: ['empresa', 'oferta'] };

const MAX_FILAS = 100;
const lista = (x) => (Array.isArray(x) ? x : []);
const P_TITULO = { abierta: 'abierto', en_curso: 'en curso', resuelta: 'resuelto' };
const ICONO_CEREBRO = ui.NOMBRES_ICONOS && ui.NOMBRES_ICONOS.includes('cerebro') ? 'cerebro' : 'libro';

export const CSS = `
.cb-principio { display: flex; gap: var(--e-3); align-items: flex-start; padding: var(--e-3) var(--e-4); border-radius: var(--r-3); background: var(--acento-bg); color: var(--txt); }
.cb-principio .icono { color: var(--acento-fuerte); flex: none; margin-top: 2px; }
.cb-principio p { margin: 0; line-height: 1.5; }
.cb-ciclo { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--e-3); margin: 0; padding: 0; list-style: none; }
.cb-paso { position: relative; display: grid; align-content: start; gap: var(--e-2); padding: var(--e-4); background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); box-shadow: var(--sombra); min-width: 0; }
.cb-paso--futuro { background: transparent; border-style: dashed; box-shadow: none; }
.cb-paso__cab { display: flex; align-items: center; gap: var(--e-2); }
.cb-paso__num { display: grid; place-items: center; flex: none; width: 26px; height: 26px; border-radius: 50%; background: var(--acento-bg); color: var(--acento-fuerte); font-weight: 700; font-size: .85rem; }
.cb-paso--futuro .cb-paso__num { background: var(--sup-3); color: var(--txt-2); }
.cb-paso__titulo { margin: 0; font-size: 1rem; font-weight: 650; }
.cb-paso__texto { margin: 0; color: var(--txt-2); font-size: .9rem; line-height: 1.45; }
.cb-paso__accion { margin-top: var(--e-1); display: flex; flex-wrap: wrap; gap: var(--e-2); align-items: center; }
.cb-paso:not(:last-child)::after { content: "›"; position: absolute; right: -13px; top: 50%; transform: translateY(-50%); font-size: 1.4rem; color: var(--txt-3); pointer-events: none; }
.cb-cmd { display: inline-flex; align-items: center; gap: 6px; height: 28px; padding: 0 10px; border-radius: var(--r-2); border: 1px solid var(--borde-fuerte); background: var(--sup-2); color: var(--txt); font-family: var(--mono); font-size: .82rem; cursor: pointer; }
.cb-cmd:hover { border-color: var(--acento); }
.cb-cmd:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }
.cb-rejilla { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--e-4); align-items: start; }
.cb-rejilla > * { min-width: 0; }
.cb-alta { display: grid; gap: var(--e-3); padding: var(--e-3) var(--e-4); border: 1px solid var(--borde); border-radius: var(--r-3); background: var(--sup-2); }
.cb-alta__fila { display: grid; grid-template-columns: minmax(0, 1fr) 170px 140px auto; gap: var(--e-2); align-items: center; }
.cb-alta__mas { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: var(--e-3); padding-top: var(--e-3); }
.cb-alta__mas label { display: grid; gap: 4px; font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; font-weight: 650; color: var(--txt-2); min-width: 0; }
.cb-alta__mas label .campo { text-transform: none; letter-spacing: 0; font-weight: 400; font-size: .9rem; width: 100%; }
.cb-alta__mas .cb-ancho { grid-column: 1 / -1; }
.cb-alta summary { cursor: pointer; color: var(--acento-fuerte); font-weight: 550; font-size: .9rem; }
.cb-lista { display: grid; gap: var(--e-2); margin: 0; padding: 0; list-style: none; }
.cb-item { display: grid; gap: var(--e-2); padding: var(--e-3) var(--e-4); background: var(--sup); border: 1px solid var(--borde); border-left: 4px solid var(--borde-fuerte); border-radius: var(--r-2); min-width: 0; }
.cb-item--P0 { border-left-color: var(--punto-error); }
.cb-item--P1 { border-left-color: var(--punto-aviso); }
.cb-item--P2 { border-left-color: var(--acento); }
.cb-item--resuelta { opacity: .65; }
.cb-item__cab { display: flex; flex-wrap: wrap; align-items: baseline; gap: var(--e-2); }
.cb-item__titulo { font-weight: 650; overflow-wrap: anywhere; }
.cb-item__detalle { margin: 0; color: var(--txt-2); font-size: .9rem; line-height: 1.45; overflow-wrap: anywhere; white-space: pre-line; }
.cb-item__pie { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e-2); }
.cb-item__acciones { display: flex; flex-wrap: wrap; gap: var(--e-2); margin-left: auto; }
.cb-mini { display: grid; gap: var(--e-2); padding: var(--e-3); border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup); min-width: 0; }
.cb-mini__valor { font-weight: 700; font-size: 1.05rem; overflow-wrap: anywhere; }
.cb-minis { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--e-3); }
.cb-aviso-regla { display: flex; gap: var(--e-3); align-items: flex-start; padding: var(--e-3); border-radius: var(--r-2); background: var(--sup-2); border: 1px solid var(--borde); font-size: .9rem; line-height: 1.45; }
.cb-aviso-regla .icono { flex: none; margin-top: 2px; color: var(--acento-fuerte); }
.cb-doc { display: grid; gap: var(--e-2); padding: var(--e-3); border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup); min-width: 0; }
.cb-ruta { display: inline-flex; align-items: center; gap: 6px; max-width: 100%; }
.cb-ruta code { overflow-wrap: anywhere; font-size: .82rem; }
.cb-ruta button { flex: none; }
.cb-hash { font-family: var(--mono); font-size: .8rem; color: var(--txt-2); }
.cb-barra { display: flex; align-items: center; gap: 8px; }
@media (max-width: 1099px) { .cb-ciclo { grid-template-columns: repeat(2, minmax(0, 1fr)); } .cb-paso:not(:last-child)::after { display: none; } }
@media (max-width: 899px) { .cb-rejilla { grid-template-columns: minmax(0, 1fr); } .cb-alta__fila { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); } .cb-alta__fila > :first-child { grid-column: 1 / -1; } .cb-alta__fila > :last-child { grid-column: 1 / -1; } }
@media (max-width: 599px) { .cb-ciclo { grid-template-columns: minmax(0, 1fr); } .cb-minis { grid-template-columns: minmax(0, 1fr); } .cb-item__acciones { margin-left: 0; width: 100%; } .cb-item { padding: var(--e-3); } }
`;

// Estado que sobrevive a los re-render del router.
let filtros = { ...C.FILTROS_VACIOS };
let activa = null; // {host, recargar}
let ultimaFirma = null;
let titularAlta = '';

const rutasDe = (...sobres) => [...new Set(sobres.filter(Boolean).flatMap((s) => (Array.isArray(s.fuente) ? s.fuente : [])))];

export async function render(ctx) {
  W.estilos();
  instalarEstilos('cb-cerebro', CSS);
  const [rp, rc] = await Promise.allSettled([ctx.api.sobre('/pulido'), ctx.api.sobre('/cerebro')]);
  if (rp.status === 'rejected' && rc.status === 'rejected') {
    return el('div', { class: 'pagina' }, ui.encabezadoPagina({ titulo: C.TITULO, descripcion: C.PRINCIPIO }), ui.errorBox(rp.reason, { reintentar: () => ctx.recargar() }));
  }
  let sobrePulido = rp.status === 'fulfilled' ? rp.value : null;
  let sobreCerebro = rc.status === 'fulfilled' ? rc.value : null;
  let errorPulido = rp.status === 'rejected' ? rp.reason : null;
  let errorCerebro = rc.status === 'rejected' ? rc.reason : null;
  let entradas = sobrePulido ? C.normalizarEntradas(sobrePulido.datos) : [];
  const cerebro = () => (sobreCerebro ? sobreCerebro.datos : null);
  ultimaFirma = C.firmaDatos(sobrePulido && sobrePulido.datos, cerebro());

  const hostMetricas = el('div', { class: 'u2-metricas' });
  const hostPendientes = el('div', { class: 'u2-pila' });
  const hostLista = el('div');
  const hostDecisiones = el('div', { class: 'u2-pila' });
  const hostReglas = el('div', { class: 'u2-pila' });
  const hostLecciones = el('div', { class: 'u2-pila' });
  const hostJardin = el('div', { class: 'u2-pila' });
  const hostTecnico = el('div');
  const conteoTxt = el('span', { class: 'u2-nota', 'aria-live': 'polite' });

  // ── acciones (única escritura: la bitácora de pulido) ──
  async function cambiarEstado(id, estado) {
    try {
      await ctx.api.post('/pulido', C.cuerpoCambioEstado(id, estado));
      toast(`Marcado como ${P_TITULO[estado]}.`, 'ok');
    } catch (err) { toast(`No se pudo cambiar el estado: ${err.mensaje || err.message}`, 'error'); }
    await recargar();
  }

  // ── alta rápida ──
  const campoTitulo = el('input', { class: 'campo', type: 'text', maxlength: String(C.LIMITES.titulo), placeholder: 'Qué queda por hacer… (Enter para guardar)', 'aria-label': 'Qué queda por hacer' });
  campoTitulo.value = titularAlta;
  campoTitulo.addEventListener('input', () => { titularAlta = campoTitulo.value; });
  const selPrioridad = W.selectDe([{ valor: '', texto: 'Prioridad…' }, ...C.PRIORIDADES.map((p) => ({ valor: p, texto: `${p} · ${C.CORTO_PRIORIDAD[p]}` }))], 'P2', { 'aria-label': 'Prioridad' });
  const selResponsable = W.selectDe([{ valor: '', texto: 'Responsable…' }, ...C.RESPONSABLES.map((r) => ({ valor: r, texto: C.ROTULO_RESPONSABLE[r] }))], 'dueno', { 'aria-label': 'Responsable' });
  const campoBloquea = el('input', { class: 'campo', type: 'text', placeholder: 'D7, OF-202611-01', 'aria-label': 'Qué bloquea' });
  const campoVence = el('input', { class: 'campo', type: 'date', 'aria-label': 'Vence' });
  const selEtapa = W.selectDe(W.OPCIONES_ETAPA, 'O0', { 'aria-label': 'Etapa' });
  const selOferta = el('select', { class: 'campo', 'aria-label': 'Oferta' });
  const selTipo = W.selectDe(C.TIPOS_ALTA_RAPIDA.map((t) => ({ valor: t.valor, texto: t.texto })), 'pendiente', { 'aria-label': 'Tipo' });
  const campoDetalle = el('textarea', { class: 'campo', rows: '3', maxlength: String(C.LIMITES.detalle), placeholder: 'Detalle opcional: por qué, qué falta, dónde mirar.', 'aria-label': 'Detalle' });
  const etiqueta = (texto, control, clase) => el('label', { class: clase || null }, texto, control);
  function poblarOfertas() {
    const previo = selOferta.value;
    limpiar(selOferta);
    selOferta.appendChild(el('option', { value: '' }, 'General (sin oferta)'));
    for (const o of ofertasConocidas()) selOferta.appendChild(el('option', { value: o }, o));
    selOferta.value = previo || '';
  }
  const ofertasConocidas = () => [...new Set([...(ctx.estado.ofertas || []).map((o) => o && o.oferta_id), ...entradas.map((e) => e.oferta_id)].filter((x) => typeof x === 'string' && x))].sort();

  async function altaRapida() {
    const r = C.validarAlta({
      titulo: campoTitulo.value, prioridad: selPrioridad.value, responsable: selResponsable.value, bloquea: campoBloquea.value, vence: campoVence.value,
      etapa: selEtapa.value, oferta_id: selOferta.value, tipo: selTipo.value, detalle: campoDetalle.value,
    });
    if (!r.ok) { toast(Object.values(r.errores).join(' '), 'aviso'); (r.errores.titulo ? campoTitulo : campoBloquea).focus(); return; }
    try {
      await ctx.api.post('/pulido', r.cuerpo);
      toast(r.cuerpo.tipo === 'regla_propuesta' ? 'Propuesta anotada: queda esperando tu aprobación a mano.' : 'Anotado en la lista única.', 'ok');
      campoTitulo.value = ''; titularAlta = ''; campoDetalle.value = ''; campoBloquea.value = ''; campoVence.value = '';
      await recargar();
      campoTitulo.focus();
    } catch (err) { toast(`No se pudo guardar: ${err.mensaje || err.message}`, 'error'); }
  }
  campoTitulo.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); altaRapida(); } });
  const alta = el('section', { class: 'cb-alta', 'aria-label': 'Anotar un pendiente' },
    el('div', { class: 'cb-alta__fila' }, campoTitulo, selPrioridad, selResponsable,
      el('button', { type: 'button', class: 'btn btn--primario', onclick: altaRapida }, icono('mas', { tam: 14 }), 'Anotar')),
    el('details', null, el('summary', null, 'Más campos: qué bloquea, cuándo vence, etapa, oferta, detalle'),
      el('div', { class: 'cb-alta__mas' },
        etiqueta('Qué bloquea', campoBloquea), etiqueta('Vence', campoVence), etiqueta('Etapa', selEtapa), etiqueta('Oferta', selOferta), etiqueta('Tipo', selTipo),
        etiqueta('Detalle', campoDetalle, 'cb-ancho'))));

  // ── filtros ──
  const selPriFiltro = W.selectDe([{ valor: '', texto: 'Todas' }, ...C.PRIORIDADES.map((p) => ({ valor: p, texto: `${p} · ${C.CORTO_PRIORIDAD[p]}` })), { valor: 'sin', texto: 'Sin prioridad' }], filtros.prioridad,
    { class: 'campo campo--chico', 'aria-label': 'Prioridad', onchange: (ev) => { filtros = { ...filtros, prioridad: ev.target.value }; pintarLista(); } });
  const selRespFiltro = W.selectDe([{ valor: '', texto: 'Todos' }, ...C.RESPONSABLES.map((r) => ({ valor: r, texto: C.ROTULO_RESPONSABLE[r] })), { valor: 'sin', texto: 'Sin asignar' }], filtros.responsable,
    { class: 'campo campo--chico', 'aria-label': 'Responsable', onchange: (ev) => { filtros = { ...filtros, responsable: ev.target.value }; pintarLista(); } });
  const selBloqueaFiltro = el('select', { class: 'campo campo--chico', 'aria-label': 'Bloquea', onchange: (ev) => { filtros = { ...filtros, bloquea: ev.target.value }; pintarLista(); } });
  const texto = el('input', { class: 'campo campo--chico', type: 'search', placeholder: 'Palabra del título o del detalle…', 'aria-label': 'Buscar en los pendientes', oninput: (ev) => { filtros = { ...filtros, texto: ev.target.value }; pintarLista(); } });
  texto.value = filtros.texto;
  const verResueltas = ui.interruptor({ etiqueta: 'Ver resueltos', activo: filtros.verResueltas, onCambio: (v) => { filtros = { ...filtros, verResueltas: v }; pintarLista(); } });
  const limpiarBoton = el('button', { type: 'button', class: 'btn btn--chico', onclick: () => { filtros = { ...C.FILTROS_VACIOS }; sincronizarFiltros(); pintarLista(); } }, 'Limpiar filtros');
  const barraFiltros = el('div', { class: 'u2-herr' },
    el('label', { class: 'u2-herr__campo u2-herr__campo--busca' }, 'Buscar', texto),
    el('label', { class: 'u2-herr__campo' }, 'Prioridad', selPriFiltro),
    el('label', { class: 'u2-herr__campo' }, 'Responsable', selRespFiltro),
    el('label', { class: 'u2-herr__campo' }, 'Bloquea', selBloqueaFiltro),
    el('div', { class: 'u2-herr__fin' }, verResueltas, limpiarBoton, conteoTxt));

  function poblarBloquea() {
    limpiar(selBloqueaFiltro);
    selBloqueaFiltro.appendChild(el('option', { value: '' }, 'Todo'));
    selBloqueaFiltro.appendChild(el('option', { value: '*' }, 'Bloquea algo'));
    const valores = C.valoresBloquea(C.clasificar(entradas).pendientes);
    for (const v of valores) selBloqueaFiltro.appendChild(el('option', { value: v }, `Bloquea ${v}`));
    if (filtros.bloquea && ![...selBloqueaFiltro.options].some((o) => o.value === filtros.bloquea)) selBloqueaFiltro.appendChild(el('option', { value: filtros.bloquea }, `Bloquea ${filtros.bloquea}`));
    selBloqueaFiltro.value = filtros.bloquea;
  }
  function sincronizarFiltros() {
    selPriFiltro.value = filtros.prioridad; selRespFiltro.value = filtros.responsable; texto.value = filtros.texto; verResueltas.fijar(filtros.verResueltas);
    poblarBloquea();
  }

  // ── una fila de la lista ──
  function item(e, { compacto = false } = {}) {
    const venc = C.vencimiento(e);
    const cuando = e.ts ? W.cuando(e.ts) : null;
    const detalle = e.detalle ? (e.detalle.length > 260 && !compacto ? `${e.detalle.slice(0, 260)}…` : e.detalle) : '';
    return el('li', { class: ['cb-item', e.prioridad && `cb-item--${e.prioridad}`, e.estado === 'resuelta' && 'cb-item--resuelta'], 'aria-label': `${e.prioridad || 'Sin prioridad'}: ${e.titulo || 'sin título'}` },
      el('div', { class: 'cb-item__cab' },
        e.prioridad ? W.tag(`${e.prioridad} · ${C.CORTO_PRIORIDAD[e.prioridad]}`, C.TONO_PRIORIDAD[e.prioridad], { icono: e.prioridad === 'P0' ? 'octogono' : (e.prioridad === 'P1' ? 'rombo-alerta' : (e.prioridad === 'P2' ? 'alerta' : 'info')), titulo: C.AYUDA_PRIORIDAD[e.prioridad] }) : null,
        el('span', { class: 'cb-item__titulo' }, e.titulo || '(sin título)')),
      detalle ? el('p', { class: 'cb-item__detalle' }, detalle) : null,
      el('div', { class: 'cb-item__pie' },
        e.responsable ? W.tag(C.ROTULO_RESPONSABLE[e.responsable], e.responsable === 'dueno' ? 'acento' : 'neutro', { icono: e.responsable === 'dueno' ? 'usuario' : (e.responsable === 'robot' || e.responsable === 'ia' ? 'robot' : 'circulo'), suave: e.responsable !== 'dueno', titulo: 'Quién debe hacerlo' }) : null,
        lista(e.bloquea).length ? W.tag(`Bloquea ${e.bloquea.join(', ')}`, 'aviso', { icono: 'candado' }) : null,
        venc.estado !== 'sin' ? W.tag(venc.texto, C.TONO_VENCIMIENTO[venc.estado], { icono: venc.estado === 'vencido' ? 'reloj-alerta' : 'reloj' }) : null,
        e.estado === 'en_curso' ? W.tag('En curso', 'info', { icono: 'progreso' }) : null,
        e.tipo && e.tipo !== 'pendiente' && e.tipo !== 'pulido' && e.tipo !== 'observacion' ? W.tag(C.ROTULO_TIPO[e.tipo] || e.tipo, 'neutro', { suave: true }) : null,
        e.categoria ? W.tag(C.ROTULO_CATEGORIA[e.categoria], 'neutro', { suave: true }) : null,
        e.etapa ? W.codigo(e.etapa) : null,
        e.oferta_id ? el('a', { class: 'enlace', href: `#/oferta/${encodeURIComponent(e.oferta_id)}` }, e.oferta_id) : null,
        cuando,
        ui.soloTecnico ? ui.soloTecnico(el('code', null, e.id), e.origen ? el('span', { class: 'u2-tenue' }, ` · ${e.origen}`) : null) : null,
        el('div', { class: 'cb-item__acciones' }, C.accionesEstado(e.estado).map((a) => el('button', {
          type: 'button', class: ['btn btn--chico', a.primario && 'btn--primario'],
          onclick: async (ev) => { const b = ev.currentTarget; b.disabled = true; try { await cambiarEstado(e.id, a.a); } finally { b.disabled = false; } },
        }, a.texto)))));
  }

  // ── pintado ──
  function pintarMetricas() {
    limpiar(hostMetricas);
    const { pendientes, reglasPropuestas } = C.clasificar(entradas);
    const hay = entradas.length > 0;
    const r = C.resumenPendientes(pendientes);
    const reglas = reglasPropuestas.filter(C.esAbierta).length;
    hostMetricas.append(
      ui.metrica({ etiqueta: 'Pendientes abiertos', valor: hay ? r.abiertos : null, contexto: hay ? `${r.enCurso} en curso` : 'Aún no hay lista: anota el primero', tono: hay ? (r.abiertos ? 'aviso' : 'ok') : undefined }),
      ui.metrica({ etiqueta: 'Urgentes (P0 y P1)', valor: hay ? r.p0 + r.p1 : null, contexto: hay ? `${r.p0} bloquean gasto o activación (P0) · ${r.p1} bloquean una etapa (P1)` : 'Sin prioridades todavía', tono: hay ? (r.p0 ? 'critico' : (r.p1 ? 'grave' : 'ok')) : undefined, ayuda: 'P0 bloquea gastar o activar algo; P1 bloquea una etapa.' }),
      ui.metrica({ etiqueta: 'Esperan tu decisión', valor: hay ? r.esperanTuDecision + reglas : null, contexto: hay ? `${C.plural(r.esperanTuDecision, 'pendiente tuyo', 'pendientes tuyos')} · ${C.plural(reglas, 'regla por aprobar', 'reglas por aprobar')}` : 'Nada asignado todavía', tono: hay && r.esperanTuDecision + reglas ? 'acento' : undefined }),
      ui.metrica({ etiqueta: 'Vencidos o por vencer', valor: hay ? r.vencidos + r.porVencer : null, contexto: hay ? `${C.plural(r.vencidos, 'vencido', 'vencidos')} · ${r.porVencer} en los próximos 7 días` : 'Sin fechas todavía', tono: hay ? (r.vencidos ? 'grave' : (r.porVencer ? 'aviso' : 'ok')) : undefined }));
  }

  function pintarLista() {
    limpiar(hostLista);
    const { pendientes } = C.clasificar(entradas);
    const filtradas = C.ordenarPendientes(C.filtrarPendientes(pendientes, filtros));
    const abiertas = pendientes.filter(C.esAbierta).length;
    conteoTxt.textContent = C.hayFiltros(filtros) ? `${filtradas.length} de ${abiertas} abiertos` : `${abiertas} abiertos`;
    limpiarBoton.disabled = !C.hayFiltros(filtros);
    if (errorPulido) { hostLista.appendChild(ui.errorBox(errorPulido, { reintentar: () => recargar() })); return; }
    if (!pendientes.length) {
      hostLista.appendChild(ui.vacioConPasos({
        titulo: 'La lista está vacía: todavía no anotaste ningún pendiente',
        explicacion: 'Aquí va todo lo que queda por hacer, en una sola lista (antes había seis repartidas). Cada línea dice quién la hace, cuánta prioridad tiene y qué frena.',
        icono: 'lista',
        pasos: [
          { texto: 'Anota arriba lo próximo que tengas pendiente: con título, prioridad y responsable alcanza.' },
          { texto: 'Al terminar una sesión, corre /cerebro-cerrar: te propone los pendientes nuevos y los guarda solo si confirmas.', comando: '/cerebro-cerrar' },
          { texto: 'Al empezar la siguiente, corre /cerebro-abrir: te resume lo urgente y propone el orden del día.', comando: '/cerebro-abrir' },
        ],
      }));
      return;
    }
    if (!filtradas.length) {
      hostLista.appendChild(ui.vacioConPasos({ titulo: C.hayFiltros(filtros) ? 'Ningún pendiente coincide con los filtros' : 'No queda nada abierto', icono: 'filtro', compacto: true,
        explicacion: C.hayFiltros(filtros) ? 'Prueba a quitar algún filtro o a buscar otra palabra.' : 'Todo lo anotado está resuelto. Activa «Ver resueltos» para repasarlo.', pasos: C.hayFiltros(filtros) ? [{ texto: 'Pulsa «Limpiar filtros» para ver todo.' }] : [] }));
      return;
    }
    hostLista.appendChild(el('ul', { class: 'cb-lista', 'aria-label': 'Pendientes' }, filtradas.slice(0, MAX_FILAS).map((e) => item(e))));
    if (filtradas.length > MAX_FILAS) hostLista.appendChild(el('p', { class: 'u2-nota' }, `Se muestran los ${MAX_FILAS} más urgentes de ${filtradas.length}; usa los filtros para acotar.`));
  }

  function pintarPendientes() {
    limpiar(hostPendientes);
    const nota = el('p', { class: 'u2-nota' }, 'Una sola lista para lo que queda por hacer: tuyo, de la IA o de un robot. Es la misma lista que Mejoras pendientes, con prioridad, responsable y qué frena cada cosa. ',
      el('a', { class: 'enlace', href: '#/pulido' }, 'Ver como tablero en Mejoras pendientes'));
    hostPendientes.append(nota, alta, barraFiltros, hostLista);
    poblarOfertas();
    poblarBloquea();
    pintarLista();
  }

  function bloque(titulo, ayuda, hijos, { id, suave = false } = {}) {
    return el('section', { class: ['u2-bloque', suave && 'u2-bloque--suave'], 'aria-labelledby': id || null },
      el('div', { class: 'u2-bloque__cab' }, el('h2', { id: id || null }, titulo), ayuda ? el('span', { class: 'u2-nota' }, ayuda) : null), hijos);
  }

  function rutaCopiable(ruta) {
    return el('span', { class: 'cb-ruta' }, el('code', null, ruta),
      el('button', { type: 'button', class: 'btn btn--chico', 'aria-label': `Copiar la ruta ${ruta}`, onclick: () => ui.copiar(ruta) }, icono('copiar', { tam: 13 })));
  }

  function pintarDecisiones() {
    limpiar(hostDecisiones);
    if (errorCerebro) { hostDecisiones.appendChild(ui.errorBox(errorCerebro, { reintentar: () => recargar() })); return; }
    const d = C.resumenDecisiones(cerebro(), entradas);
    if (d.sinDatos) {
      hostDecisiones.appendChild(ui.vacioConPasos({
        titulo: 'Todavía no hay decisiones registradas', icono: 'bandera', compacto: true,
        explicacion: 'Las decisiones que tomas trabajando con Claude se guardan al cerrar la sesión; así la próxima no te las vuelve a preguntar.',
        pasos: [{ texto: 'Al terminar, corre /cerebro-cerrar y confirma las decisiones que propone.', comando: '/cerebro-cerrar' }],
      }));
      return;
    }
    hostDecisiones.appendChild(el('div', { class: 'u2-fila' },
      W.tag(`${d.enDocumentos} en los documentos`, 'info', { icono: 'libro' }),
      W.tag(`${d.vigentesGuardadas} guardadas al cerrar sesiones`, d.vigentesGuardadas ? 'ok' : 'neutro', { icono: 'archivar', suave: !d.vigentesGuardadas }),
      W.tag(`${d.anotadas.length} anotadas en la bitácora`, 'neutro', { icono: 'bandera', suave: true })));
    for (const f of d.fuentes) {
      hostDecisiones.appendChild(el('div', { class: 'cb-doc' },
        el('strong', null, f.titulo || f.clave),
        rutaCopiable(f.ruta),
        f.existe
          ? el('div', { class: 'u2-fila' },
            f.decisiones !== null ? W.tag(`${f.decisiones} decisiones`, 'info', { icono: 'bandera', suave: true }) : null,
            f.tareasAbiertas ? W.tag(`${f.tareasAbiertas} tareas abiertas · ${f.tareasHechas ?? 0} hechas`, 'aviso', { icono: 'lista', suave: true }) : null,
            f.modificado ? el('span', { class: 'u2-nota' }, 'cambió ', W.cuando(f.modificado)) : null)
          : el('p', { class: 'u2-aviso' }, 'No se encontró este documento.')));
    }
    hostDecisiones.appendChild(el('p', { class: 'u2-nota' }, 'El panel solo enlaza y cuenta estos documentos (no los muestra): ábrelos con tu editor desde la ruta. Una decisión nueva se guarda con /cerebro-cerrar solo cuando tú confirmas.'));
    const recientes = [...d.guardadas.slice(-5).reverse().map((g) => ({ clave: g.id, titulo: g.titulo, ts: g.ts, nota: g.detalle })), ...d.anotadas.slice(0, 5).map((a) => ({ clave: a.id, titulo: a.titulo, ts: a.ts, nota: a.detalle }))];
    if (recientes.length) {
      hostDecisiones.appendChild(el('h3', { class: 'u2-subtitulo' }, 'Últimas decisiones guardadas'));
      hostDecisiones.appendChild(el('ul', { class: 'cb-lista' }, recientes.map((r) => el('li', { class: 'cb-item' },
        el('div', { class: 'cb-item__cab' }, el('span', { class: 'cb-item__titulo' }, r.titulo || '(sin título)')),
        r.nota ? el('p', { class: 'cb-item__detalle' }, r.nota) : null,
        el('div', { class: 'cb-item__pie' }, r.ts ? W.cuando(r.ts) : null, ui.soloTecnico ? ui.soloTecnico(el('code', null, r.clave || '')) : null)))));
    }
  }

  function pintarReglas() {
    limpiar(hostReglas);
    hostReglas.appendChild(el('div', { class: 'cb-aviso-regla' }, icono('candado', { tam: 18 }),
      el('div', null, el('strong', null, 'Solo tú cambias las reglas. '), 'Ningún robot ni agente las escribe, y una corrección nunca se vuelve regla sola: queda como propuesta y tú la apruebas a mano, fuera de este panel.')));
    if (errorCerebro) { hostReglas.appendChild(ui.errorBox(errorCerebro, { reintentar: () => recargar() })); return; }
    const r = C.resumenReglas(cerebro(), entradas);
    if (!r.hayArchivos) {
      hostReglas.appendChild(ui.vacioConPasos({ titulo: 'No se encontraron los archivos de reglas', icono: 'candado', compacto: true,
        explicacion: 'Esperaba los archivos de valores ajustables, de límites y de niveles de autonomía en la carpeta empresa/ del proyecto.', pasos: [{ texto: 'Revisa que arrancaste el panel desde la carpeta del proyecto.', comando: '.venv/bin/python -m dashboard' }] }));
    } else {
      hostReglas.appendChild(el('div', { class: 'cb-minis' }, r.tarjetas.map((t) => el('div', { class: 'cb-mini' },
        el('div', { class: 'u2-rotulo' }, t.titulo),
        el('div', { class: 'cb-mini__valor' }, t.valor ?? '—'),
        el('p', { class: 'u2-nota', style: { margin: '0' } }, t.detalle),
        el('div', { class: 'u2-fila' }, W.tag(t.existe ? 'Solo lectura' : 'No encontrado', t.existe ? t.tono : 'aviso', { icono: t.existe ? 'ojo' : 'alerta', suave: t.tono === 'neutro' }))))));
      hostReglas.appendChild(el('p', { class: 'u2-nota' }, 'Detalle completo y valores en ', el('a', { class: 'enlace', href: '#/parametros' }, 'Límites y reglas'), '.'));
    }
    hostReglas.appendChild(el('h3', { class: 'u2-subtitulo' }, `Propuestas de regla esperando tu aprobación (${r.propuestas.length})`));
    hostReglas.appendChild(r.propuestas.length
      ? el('ul', { class: 'cb-lista' }, r.propuestas.map((e) => item(e)))
      : el('p', { class: 'u2-nota' }, 'Ninguna por ahora. Cuando una corrección se repita, aparecerá aquí como propuesta; no se aplica hasta que tú la apruebes.'));
  }

  function pintarLecciones() {
    limpiar(hostLecciones);
    if (errorCerebro) { hostLecciones.appendChild(ui.errorBox(errorCerebro, { reintentar: () => recargar() })); return; }
    const l = C.resumenLecciones(cerebro(), entradas);
    if (l.vacio) {
      hostLecciones.appendChild(ui.vacioConPasos({
        titulo: 'Todavía no hay lecciones', icono: 'libro', compacto: true,
        explicacion: 'Una lección es algo que funcionó o falló, con su prueba. Hoy no hay ninguna porque aún no se revisó ni se cerró ninguna oferta.',
        pasos: [{ texto: 'Aparecen solas cuando una revisión de calidad deja observaciones en una oferta o cuando una oferta se cierra con su análisis final (post-mortem).' }, { texto: 'También puedes guardar una al cerrar la sesión, con su prueba (un archivo y su huella).', comando: '/cerebro-cerrar' }],
      }));
      return;
    }
    hostLecciones.appendChild(el('div', { class: 'u2-fila' },
      W.tag(`${l.hallazgos} observaciones de revisión`, l.hallazgos ? 'info' : 'neutro', { icono: 'ojo', suave: !l.hallazgos }),
      W.tag(`${l.postmortems.length} análisis finales`, l.postmortems.length ? 'info' : 'neutro', { icono: 'archivo', suave: !l.postmortems.length }),
      W.tag(`${l.guardadas.length + l.anotadas.length} guardadas con prueba`, l.guardadas.length + l.anotadas.length ? 'ok' : 'neutro', { icono: 'archivar', suave: !(l.guardadas.length + l.anotadas.length) })));
    if (l.todosDemo) hostLecciones.appendChild(el('p', { class: 'u2-aviso' }, 'Estos datos vienen de la oferta de ejemplo (demostración): todavía no hay lecciones de una oferta real.'));
    if (l.top.length) {
      hostLecciones.appendChild(el('h3', { class: 'u2-subtitulo' }, 'Lo que más se repite en las revisiones de calidad'));
      hostLecciones.appendChild(el('ul', { class: 'cb-lista' }, l.top.map((t) => el('li', { class: 'cb-item' },
        el('div', { class: 'cb-item__cab' }, el('span', { class: 'cb-item__titulo' }, t.patron), W.tag(`${t.n} ${t.n === 1 ? 'vez' : 'veces'}`, 'neutro', { suave: true })),
        t.ejemplo ? el('p', { class: 'cb-item__detalle' }, t.ejemplo) : null,
        el('div', { class: 'cb-item__pie' }, t.etapas.map((s) => W.codigo(s)), el('span', { class: 'u2-nota' }, `${t.ofertas} ${t.ofertas === 1 ? 'oferta' : 'ofertas'}`))))));
    }
    if (l.aprendizajes.length) {
      hostLecciones.appendChild(el('h3', { class: 'u2-subtitulo' }, 'Qué debería aprender la guía de trabajo'));
      hostLecciones.appendChild(el('ul', { class: 'cb-lista' }, l.aprendizajes.slice(0, 5).map((a) => el('li', { class: 'cb-item' },
        el('div', { class: 'cb-item__cab' }, el('span', { class: 'cb-item__titulo' }, a.texto)),
        el('div', { class: 'cb-item__pie' }, a.etapa ? W.codigo(a.etapa) : null, el('a', { class: 'enlace', href: `#/oferta/${encodeURIComponent(a.oferta_id)}` }, a.oferta_id), a.demo ? W.tag('demo', 'neutro', { suave: true }) : null)))));
      if (l.aprendizajes.length > 5) hostLecciones.appendChild(el('p', { class: 'u2-nota' }, `y ${l.aprendizajes.length - 5} más en los archivos de revisión.`));
    }
    if (l.postmortems.length) {
      hostLecciones.appendChild(el('h3', { class: 'u2-subtitulo' }, 'Análisis final de ofertas cerradas'));
      hostLecciones.appendChild(el('ul', { class: 'cb-lista' }, l.postmortems.slice(0, 5).map((p) => el('li', { class: 'cb-item' },
        el('div', { class: 'cb-item__cab' }, p.veredicto ? W.tag(p.veredicto, p.veredicto === 'VALIDADA' ? 'ok' : (p.veredicto === 'FALLIDA' ? 'error' : 'neutro'), {}) : null,
          el('span', { class: 'cb-item__titulo' }, p.causa_principal || 'sin causa principal')),
        p.aprendizajes && p.aprendizajes.length ? el('p', { class: 'cb-item__detalle' }, p.aprendizajes.join('\n')) : null,
        el('div', { class: 'cb-item__pie' }, el('a', { class: 'enlace', href: `#/oferta/${encodeURIComponent(p.oferta_id)}` }, p.oferta_id), p.demo ? W.tag('demo', 'neutro', { suave: true }) : null)))));
    }
    const guardadas = [...l.guardadas].reverse().slice(0, 5);
    if (guardadas.length) {
      hostLecciones.appendChild(el('h3', { class: 'u2-subtitulo' }, 'Guardadas con su prueba'));
      hostLecciones.appendChild(el('ul', { class: 'cb-lista' }, guardadas.map((g) => el('li', { class: 'cb-item' },
        el('div', { class: 'cb-item__cab' }, g.confianza ? W.tag(`Confianza ${g.confianza}`, 'neutro', { suave: true, titulo: 'A replicada en 2 ofertas · B una oferta conclusiva · C anecdótica' }) : null, el('span', { class: 'cb-item__titulo' }, g.titulo || g.leccion || '(sin título)')),
        g.leccion && g.leccion !== g.titulo ? el('p', { class: 'cb-item__detalle' }, g.leccion) : null,
        el('div', { class: 'cb-item__pie' }, g.etapa ? W.codigo(g.etapa) : null, W.tag(`${(g.evidencia || []).length} ${(g.evidencia || []).length === 1 ? 'prueba' : 'pruebas'}`, (g.evidencia || []).length ? 'ok' : 'aviso', { icono: 'ok', suave: true }), g.ts ? W.cuando(g.ts) : null)))));
    }
    if (l.truncado) hostLecciones.appendChild(el('p', { class: 'u2-nota' }, 'Se muestran las primeras observaciones; hay más en los archivos de revisión de cada oferta.'));
  }

  function pintarJardin() {
    limpiar(hostJardin);
    const j = C.estadoJardin(cerebro());
    hostJardin.append(
      el('div', { class: 'u2-fila' }, W.tag(j.titulo, j.tono, { icono: j.propuestas ? 'refrescar' : 'circulo-punteado' }), W.tag('Domingo · simulacro + tu clic', 'neutro', { icono: 'reloj', suave: true })),
      el('ol', { class: 'u2-pasos' }, C.JARDIN_PASOS.map((p) => el('li', null, el('div', { class: 'u2-pasos__cuerpo' }, el('span', null, p))))),
      el('p', { class: 'u2-nota' }, 'Hoy no hay datos: el jardinero todavía no está construido. Se construye después de que la memoria tenga contenido que ordenar.'));
  }

  function pintarTecnico() {
    limpiar(hostTecnico);
    const filas = C.rutasTecnicas(cerebro());
    hostTecnico.appendChild(ui.detalleTecnico('Archivos y huellas de lo que lee esta pantalla', () => ui.tabla({
      etiqueta: 'Archivos y huellas', filas, maxFilas: 60, vacio: 'Sin datos.',
      columnas: [
        { clave: 'etiqueta', titulo: 'Qué es' },
        { clave: 'ruta', titulo: 'Ruta', formato: (r) => rutaCopiable(r) },
        { clave: 'existe', titulo: 'Existe', ancho: '80px', formato: (v) => (v === null ? '—' : (v ? 'sí' : 'no')) },
        { clave: 'bytes', titulo: 'Tamaño', ancho: '90px', formato: (b) => (b === null || b === undefined ? '—' : fmt.bytes(b)) },
        { clave: 'sha256', titulo: 'Huella', formato: (h) => (h ? el('span', { class: 'cb-hash', title: h }, `${h.slice(0, 16)}…`) : '—') },
      ],
    })));
  }

  function pintarTodo() { pintarMetricas(); pintarPendientes(); pintarDecisiones(); pintarReglas(); pintarLecciones(); pintarJardin(); pintarTecnico(); }

  async function recargar() {
    const [a, b] = await Promise.allSettled([ctx.api.sobre('/pulido'), ctx.api.sobre('/cerebro')]);
    if (a.status === 'fulfilled') { sobrePulido = a.value; errorPulido = null; entradas = C.normalizarEntradas(a.value.datos); } else errorPulido = a.reason;
    if (b.status === 'fulfilled') { sobreCerebro = b.value; errorCerebro = null; } else errorCerebro = b.reason;
    ultimaFirma = C.firmaDatos(sobrePulido && sobrePulido.datos, cerebro());
    pintarTodo();
  }

  // ── ciclo de sesión ──
  const botonCmd = (cmd) => el('button', { type: 'button', class: 'cb-cmd', 'aria-label': `Copiar ${cmd}`, title: 'Copiar para pegarlo en la sesión', onclick: () => ui.copiar(cmd) }, cmd, icono('copiar', { tam: 13 }));
  const ciclo = el('ol', { class: 'cb-ciclo', 'aria-label': 'Ciclo de cada sesión' }, C.CICLO.map((p) => el('li', { class: ['cb-paso', p.estado === 'sin_construir' && 'cb-paso--futuro'] },
    el('div', { class: 'cb-paso__cab' }, el('span', { class: 'cb-paso__num', 'aria-hidden': 'true' }, String(p.numero)), icono(p.icono, { tam: 16 }), el('h3', { class: 'cb-paso__titulo' }, p.titulo)),
    el('p', { class: 'cb-paso__texto' }, p.texto),
    el('div', { class: 'cb-paso__accion' },
      p.comando ? botonCmd(p.comando) : null,
      p.ancla ? el('button', { type: 'button', class: 'btn btn--chico', onclick: () => { alta.scrollIntoView({ behavior: 'smooth', block: 'center' }); campoTitulo.focus({ preventScroll: true }); } }, p.rotuloAncla) : null,
      p.estado === 'sin_construir' ? W.tag('Aún no existe', 'neutro', { icono: 'circulo-punteado', suave: true, titulo: 'Se construye después de /cerebro-cerrar' }) : null))));

  const pagina = el('div', { class: 'pagina' },
    ui.encabezadoPagina({
      titulo: C.TITULO,
      descripcion: 'Lo que el sistema decidió, aprendió y tiene pendiente, para que cada sesión nueva arranque sabiendo.',
      acciones: [ui.fuente(rutasDe(sobrePulido, sobreCerebro), { leido: (sobrePulido || sobreCerebro).generado_en })],
    }),
    el('div', { class: 'cb-principio' }, icono(ICONO_CEREBRO, { tam: 20 }), el('p', null, el('strong', null, 'Una IA sin memoria arranca de cero cada vez. '), 'El Cerebro guarda lo que decidiste, lo que salió mal y lo que queda por hacer, para que la próxima sesión no empiece de cero.')),
    ciclo,
    hostMetricas,
    bloque('Pendientes', 'La lista única: tuyos, de la IA y de los robots.', hostPendientes, { id: 'cb-pendientes-t' }),
    el('div', { class: 'cb-rejilla' },
      bloque('Tus decisiones vigentes', 'Lo que ya decidiste: no se vuelve a preguntar.', hostDecisiones, { id: 'cb-decisiones-t' }),
      bloque('Reglas', 'Solo lectura.', hostReglas, { id: 'cb-reglas-t' }),
      bloque('Lecciones', 'Qué funcionó y qué no, con la prueba.', hostLecciones, { id: 'cb-lecciones-t' }),
      bloque('Jardín del domingo', 'Ordena y archiva lo viejo.', hostJardin, { id: 'cb-jardin-t', suave: true })),
    hostTecnico);

  pintarTodo();

  activa = { host: pagina, recargar };
  ctx.alSalir(() => { if (activa && activa.host === pagina) activa = null; });
  return pagina;
}

/** Actualiza en el sitio: no se re-renderiza la pantalla (se conservan filtros, foco y desplazamiento). */
export async function alCambio(ctx, evento) {
  if (!activa || !activa.host.isConnected) return undefined;
  const lote = Array.isArray(evento && evento.lote) && evento.lote.length ? evento.lote : [evento];
  const toca = lote.some((e) => e && (e.tipo === 'empresa' || e.tipo === 'oferta'));
  if (toca) { await activa.recargar(); return undefined; }
  if (lote.some((e) => e && e.tipo === 'sondeo')) {
    try {
      const [p, c] = await Promise.all([ctx.api.get('/pulido'), ctx.api.get('/cerebro')]);
      if (C.firmaDatos(p, c) !== ultimaFirma) await activa.recargar();
    } catch (_) { /* sin conexión */ }
  }
  return undefined;
}
