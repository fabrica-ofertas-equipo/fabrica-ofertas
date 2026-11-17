// pages/pulido.js — #/pulido: tu bitácora de pulido como TABLERO (Abierta · En curso · Resuelta) o lista, con alta rápida, mapa por etapa y
// contadores por gravedad (CONTRATO §6, empresa/panel/pulido.jsonl). Es la herramienta con la que vas puliendo cada paso hasta que corra solo:
// anotas lo que corriges mientras armas una oferta a mano; cuando una etapa no tiene pendientes, está lista para automatizarse.
// La lógica vive en lib/pulido.js (probada sin DOM). Se actualiza en el sitio (sin re-render del router) para no perder filtros, foco ni scroll.

import { ui, el, icono, fmt, limpiar, toast } from '../ui.js';
import * as P from '../lib/pulido.js';
import * as V from '../lib/oferta.js';
import * as W from '../lib/vistas-ofertas.js';

export const meta = { ruta: 'pulido', titulo: 'Mejoras pendientes', grupo: 'Cerebro', icono: 'lapiz', escucha: ['empresa'] };

let filtros = { ...P.FILTROS_VACIOS };
let vista = leerVista();
let sevRapida = 'media';
let activa = null; // {host, recargar} de la instancia montada
let ultimaFirma = null;

function leerVista() {
  try { const v = globalThis.localStorage && globalThis.localStorage.getItem('fab.pulido.vista'); return v === 'lista' ? 'lista' : 'tablero'; } catch (_) { return 'tablero'; }
}
function guardarVista(v) { try { if (globalThis.localStorage) globalThis.localStorage.setItem('fab.pulido.vista', v); } catch (_) { /* sin almacén */ } }

const firma = (datos) => JSON.stringify(P.listaCruda(datos).map((l) => [l && l.id, l && l.ts, l && l.estado]));

export async function render(ctx) {
  W.estilos();
  let sobre;
  try { sobre = await ctx.api.sobre('/pulido'); } catch (err) {
    return el('div', { class: 'pagina' }, ui.encabezadoPagina({ titulo: 'Mejoras pendientes', descripcion: 'No se pudo leer la lista de mejoras pendientes.' }), ui.errorBox(err, { reintentar: () => ctx.recargar() }));
  }
  ultimaFirma = firma(sobre.datos);
  let entradas = P.normalizarEntradas(sobre.datos);
  let fuente = sobre;

  // filtros que llegan por el hash (p. ej. desde Skills: #/pulido?etapa=D3)
  if (ctx.params && (ctx.params.etapa || ctx.params.oferta)) {
    filtros = { ...filtros, ...(ctx.params.etapa && P.ETAPAS_PULIDO.includes(ctx.params.etapa) ? { etapa: ctx.params.etapa } : {}), ...(ctx.params.oferta ? { oferta: ctx.params.oferta } : {}) };
  }
  const ids = () => P.ofertasEnBitacora(entradas, (ctx.estado.ofertas || []).map((o) => o && o.oferta_id));

  const hostMetricas = el('div', { class: 'u2-metricas' });
  const hostMapa = el('div');
  const hostGravedad = el('div');
  const hostContenido = el('div');
  const conteoTxt = el('span', { class: 'u2-nota', 'aria-live': 'polite' });

  const anotar = () => W.abrirFormularioObservacion(ctx, {
    oferta_id: filtros.oferta && filtros.oferta !== '_global' ? filtros.oferta : '', etapa: filtros.etapa || '', ofertas: ids(), alGuardar: () => recargarDatos(),
  });

  async function cambiarEstado(id, estado) {
    try {
      await ctx.api.post('/pulido', P.cuerpoCambioEstado(id, estado));
      toast(`Nota marcada como ${P.TITULO_ESTADO[estado].toLowerCase()}.`, 'ok');
    } catch (err) { toast(`No se pudo cambiar el estado: ${err.mensaje || err.message}`, 'error'); }
    await recargarDatos();
  }

  // ── alta rápida ──
  const campoTitulo = el('input', { class: 'campo', type: 'text', maxlength: String(P.LIMITES.titulo), placeholder: 'Anota algo a corregir… (Enter para guardar)', 'aria-label': 'Qué hay que corregir' });
  const selEtapaRapida = W.selectDe([{ valor: '', texto: 'Etapa…' }, ...W.OPCIONES_ETAPA], filtros.etapa || '', { 'aria-label': 'Etapa de la nota' });
  const selOfertaRapida = el('select', { class: 'campo', 'aria-label': 'Oferta de la nota' });
  const segSev = W.segmentado([{ valor: 'alta', texto: 'Alta', icono: 'rombo-alerta' }, { valor: 'media', texto: 'Media', icono: 'alerta' }, { valor: 'baja', texto: 'Baja', icono: 'info' }], sevRapida, (v) => { sevRapida = v; }, { etiqueta: 'Gravedad' });
  async function altaRapida() {
    const r = P.validarRapida({ titulo: campoTitulo.value, etapa: selEtapaRapida.value, oferta_id: selOfertaRapida.value, severidad: sevRapida });
    if (!r.ok) { toast(Object.values(r.errores).join(' '), 'aviso'); (r.errores.titulo ? campoTitulo : selEtapaRapida).focus(); return; }
    try {
      await ctx.api.post('/pulido', r.cuerpo);
      toast('Anotado en la bitácora.', 'ok');
      campoTitulo.value = '';
      await recargarDatos();
      campoTitulo.focus();
    } catch (err) { toast(`No se pudo guardar: ${err.mensaje || err.message}`, 'error'); }
  }
  campoTitulo.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); altaRapida(); } });
  const rapida = el('section', { class: 'u2-rapida', 'aria-label': 'Alta rápida' },
    el('div', { class: 'u2-fila u2-fila--entre' },
      el('h2', { class: 'u2-subtitulo' }, 'Anotar algo ahora ', ui.ayuda('bitacora_pulido')),
      el('span', { class: 'u2-nota' }, 'Una línea basta; el detalle es opcional.')),
    el('div', { class: 'u2-rapida__fila' }, campoTitulo, selEtapaRapida, selOfertaRapida, segSev,
      el('button', { type: 'button', class: 'btn btn--primario', onclick: altaRapida }, icono('mas', { tam: 14 }), 'Anotar')),
    el('div', null, el('button', { type: 'button', class: 'u2-enlace-boton', onclick: anotar }, 'Anotar con detalle (qué viste, qué esperabas, en qué archivo)…')));

  // ── filtros ──
  const selOferta = el('select', { class: 'campo campo--chico', 'aria-label': 'Oferta', onchange: (ev) => { filtros = { ...filtros, oferta: ev.target.value }; pintar(); } });
  const selEtapa = W.selectDe([{ valor: '', texto: 'Todas' }, ...W.OPCIONES_ETAPA], filtros.etapa, { class: 'campo campo--chico', 'aria-label': 'Etapa', onchange: (ev) => { filtros = { ...filtros, etapa: ev.target.value }; pintar(); } });
  const campoSel = (etiqueta, clave, opciones) => {
    const s = W.selectDe(opciones, filtros[clave], { class: 'campo campo--chico', 'aria-label': etiqueta, onchange: (ev) => { filtros = { ...filtros, [clave]: ev.target.value }; pintar(); } });
    return el('label', { class: 'u2-herr__campo' }, etiqueta, s);
  };
  const texto = el('input', { class: 'campo campo--chico', type: 'search', placeholder: 'Palabra del título o del detalle…', 'aria-label': 'Buscar en la bitácora', oninput: (ev) => { filtros = { ...filtros, texto: ev.target.value }; pintar(); } });
  texto.value = filtros.texto;
  const limpiarBoton = el('button', { type: 'button', class: 'btn btn--chico', onclick: () => { filtros = { ...P.FILTROS_VACIOS }; sincronizarControles(); pintar(); } }, 'Limpiar filtros');
  const ocultar = ui.interruptor({ etiqueta: 'Ocultar resueltas', activo: filtros.ocultarResueltas, onCambio: (v) => { filtros = { ...filtros, ocultarResueltas: v }; pintar(); } });
  const segVista = W.segmentado([{ valor: 'tablero', texto: 'Tablero', icono: 'panel' }, { valor: 'lista', texto: 'Lista', icono: 'lista' }], vista, (v) => { vista = v; guardarVista(v); pintar(); }, { etiqueta: 'Vista' });
  const selSev = campoSel('Gravedad', 'severidad', [{ valor: '', texto: 'Todas' }, ...P.SEVERIDADES.map((s) => ({ valor: s, texto: P.TITULO_SEVERIDAD[s] }))]);
  const selTipo = campoSel('Tipo', 'tipo', [{ valor: '', texto: 'Todos' }, ...P.TIPOS.map((s) => ({ valor: s, texto: P.TITULO_TIPO[s] }))]);
  const barraFiltros = el('div', { class: 'u2-herr' },
    el('label', { class: 'u2-herr__campo u2-herr__campo--busca' }, 'Buscar', texto),
    el('label', { class: 'u2-herr__campo' }, 'Oferta', selOferta),
    el('label', { class: 'u2-herr__campo' }, 'Etapa', selEtapa),
    selSev, selTipo,
    el('div', { class: 'u2-herr__fin' }, ocultar, limpiarBoton, conteoTxt, segVista));

  function poblarOfertas() {
    for (const s of [selOferta, selOfertaRapida]) {
      const previo = s === selOferta ? filtros.oferta : s.value;
      limpiar(s);
      if (s === selOferta) { s.appendChild(el('option', { value: '' }, 'Todas')); s.appendChild(el('option', { value: '_global' }, 'Generales (sin oferta)')); }
      else s.appendChild(el('option', { value: '' }, 'General (sin oferta)'));
      for (const o of ids()) s.appendChild(el('option', { value: o }, o));
      if (previo && ![...s.options].some((x) => x.value === previo)) s.appendChild(el('option', { value: previo }, `${previo} (sin entradas)`));
      s.value = previo || '';
    }
  }
  function sincronizarControles() {
    poblarOfertas();
    selEtapa.value = filtros.etapa;
    texto.value = filtros.texto;
    ocultar.fijar(filtros.ocultarResueltas);
    for (const [lab, clave] of [[selSev, 'severidad'], [selTipo, 'tipo']]) lab.querySelector('select').value = filtros[clave];
  }

  // ── pintado ──
  function pintarMetricas() {
    const r = P.resumenBitacora(entradas);
    const mapa = P.mapaPulido(entradas);
    limpiar(hostMetricas);
    hostMetricas.append(
      ui.metrica({ etiqueta: 'Pendientes', valor: String(r.pendientes), contexto: `${r.abiertas} abiertas · ${r.enCurso} en curso`, tono: r.pendientes ? 'aviso' : 'ok' }),
      ui.metrica({ etiqueta: 'Gravedad alta sin resolver', valor: String(r.altasPendientes), contexto: 'lo que más frena que corra solo', tono: r.altasPendientes ? 'grave' : 'ok', ayuda: 'severidad_pulido' }),
      ui.metrica({ etiqueta: 'Resueltas', valor: String(r.resueltas), contexto: r.total ? `${fmt.pct(r.bpResueltas)} de ${r.total} notas` : 'todavía no hay notas' }),
      ui.metrica({ etiqueta: 'Etapas ya pulidas', valor: mapa.conNotas ? `${mapa.limpias} de ${mapa.conNotas}` : null, contexto: mapa.conNotas ? 'sin pendientes entre las que tienen notas' : 'aún sin notas por etapa', tono: mapa.conNotas && mapa.limpias === mapa.conNotas ? 'ok' : undefined }));
  }

  function pintarMapa() {
    limpiar(hostMapa);
    const m = P.mapaPulido(entradas, { oferta: filtros.oferta });
    const celdas = m.filas.filter((c) => V.ORDEN_ETAPAS.includes(c.etapa) || c.total > 0);
    hostMapa.appendChild(el('div', { class: 'u2-mapa' }, celdas.map((c) => {
      const rotulo = { sin_notas: 'Sin notas', pulir: `${c.pendientes} por pulir`, limpia: 'Pulida' }[c.madurez];
      const ic = { sin_notas: 'circulo-punteado', pulir: 'progreso', limpia: 'ok' }[c.madurez];
      return el('button', {
        type: 'button', class: ['u2-mapa__celda', `u2-mapa__celda--${c.madurez}`], 'aria-pressed': String(filtros.etapa === c.etapa),
        title: `${c.etapa} · ${c.nombre}: ${c.abiertas} abiertas, ${c.enCurso} en curso, ${c.resueltas} resueltas`,
        onclick: () => { filtros = { ...filtros, etapa: filtros.etapa === c.etapa ? '' : c.etapa }; selEtapa.value = filtros.etapa; pintar(); },
      },
      el('div', { class: 'u2-fila', style: { gap: '6px' } }, W.codigo(c.etapa), c.altaPendiente ? W.tag(String(c.altaPendiente), 'grave', { icono: 'rombo-alerta', titulo: `${c.altaPendiente} de gravedad alta sin resolver` }) : null),
      el('div', { class: 'u2-mapa__nombre' }, V.NOMBRES_HUMANOS[c.etapa] || c.nombre),
      c.total ? ui.barraApilada([{ valor: c.resueltas, tono: 'ok', titulo: 'resueltas' }, { valor: c.enCurso, tono: 'info', titulo: 'en curso' }, { valor: c.abiertas, tono: 'neutro', titulo: 'abiertas' }], { etiqueta: `${c.etapa}: ${c.resueltas} de ${c.total} resueltas` }) : el('div', { class: 'barra-apilada barra-apilada--vacia', 'aria-hidden': 'true' }),
      el('div', { class: 'u2-mapa__estado' }, icono(ic, { tam: 13 }), rotulo));
    })));
  }

  function pintarGravedad() {
    limpiar(hostGravedad);
    const c = P.conteosPorSeveridad(entradas);
    hostGravedad.appendChild(el('div', { class: 'u2-gravedad', role: 'group', 'aria-label': 'Pendientes por gravedad' },
      el('span', { class: 'u2-rotulo', style: { alignSelf: 'center' } }, 'Pendientes por gravedad'),
      P.SEVERIDADES.map((s) => el('button', {
        type: 'button', class: 'u2-gravedad__btn', 'aria-pressed': String(filtros.severidad === s), title: P.AYUDA_SEVERIDAD[s],
        onclick: () => { filtros = { ...filtros, severidad: filtros.severidad === s ? '' : s }; selSev.querySelector('select').value = filtros.severidad; pintar(); },
      }, icono({ alta: 'rombo-alerta', media: 'alerta', baja: 'info' }[s], { tam: 15 }), P.TITULO_SEVERIDAD[s], el('b', null, String(c[s].pendientes))))));
  }

  function tarjeta(e) {
    const sig = P.siguienteEstado(e.estado);
    const btn = (texto, estado, primario = false) => el('button', {
      type: 'button', class: ['btn btn--chico', primario && 'btn--primario'],
      onclick: async (ev) => { const b = ev.currentTarget; b.disabled = true; try { await cambiarEstado(e.id, estado); } finally { b.disabled = false; } },
    }, texto);
    const carta = el('article', {
      class: ['u2-nota-card', 'u2-carta', `u2-nota-card--${e.severidad}`, e.estado === 'resuelta' && 'u2-nota-card--resuelta'], draggable: 'true', 'aria-label': P.resumenEntrada(e),
      ondragstart: (ev) => { ev.dataTransfer.setData('text/plain', e.id); ev.dataTransfer.effectAllowed = 'move'; carta.classList.add('u2-carta--arrastrando'); },
      ondragend: () => carta.classList.remove('u2-carta--arrastrando'),
    },
    el('div', { class: 'u2-nota-card__titulo' }, e.titulo || '(sin título)'),
    e.detalle ? el('div', { class: 'u2-nota-card__detalle' }, e.detalle) : null,
    el('div', { class: 'u2-nota-card__pie' },
      W.tagSeveridadPulido(e.severidad),
      e.etapa ? W.tag(`${e.etapa} · ${V.nombreHumano(e.etapa) === e.etapa ? P.nombreEtapaPulido(e.etapa) : V.nombreHumano(e.etapa)}`, 'neutro', { suave: true, icono: 'flecha-derecha' }) : null,
      W.tagTipoPulido(e.tipo)),
    el('div', { class: 'u2-carta__meta' },
      e.oferta_id ? el('a', { class: 'enlace', href: `#/oferta/${encodeURIComponent(e.oferta_id)}${e.etapa && V.ORDEN_ETAPAS.includes(e.etapa) ? `?etapa=${e.etapa}&pestana=notas` : ''}` }, e.oferta_id) : W.tag('General', 'info', { suave: true, icono: 'globo' }),
      W.cuando(e.ts), el('span', { style: { flex: '1' } }),
      e.estado === 'en_curso' ? btn('Abrir', 'abierta') : null,
      btn(P.etiquetaSiguiente(e.estado), sig, e.estado === 'abierta')));
    return carta;
  }

  function columna(c) {
    const col = el('section', { class: 'u2-col', 'aria-label': `${c.titulo}: ${c.items.length}`, dataset: { estado: c.estado },
      ondragover: (ev) => { ev.preventDefault(); ev.dataTransfer.dropEffect = 'move'; col.classList.add('u2-col--sobre'); },
      ondragleave: (ev) => { if (!col.contains(ev.relatedTarget)) col.classList.remove('u2-col--sobre'); },
      ondrop: (ev) => {
        ev.preventDefault(); col.classList.remove('u2-col--sobre');
        const id = ev.dataTransfer.getData('text/plain');
        const e = entradas.find((x) => x.id === id);
        if (P.puedeMover(e, c.estado)) cambiarEstado(id, c.estado);
      },
    },
    el('div', { class: 'u2-col__cab' }, el('h3', { class: 'u2-col__titulo' }, W.tagEstadoPulido(c.estado), ' ', el('span', { class: 'u2-sr' }, c.titulo)), el('span', { class: 'u2-col__n' }, String(c.items.length))),
    el('div', { class: 'u2-col__sub' }, P.AYUDA_ESTADO[c.estado]),
    c.items.length ? c.items.map(tarjeta) : el('div', { class: 'u2-col__vacia' }, c.estado === 'resuelta' ? 'Aquí aparecen las que resuelvas.' : (c.estado === 'en_curso' ? 'Arrastra aquí lo que estés corrigiendo.' : 'Nada abierto: buen momento para anotar lo que veas.')));
    return col;
  }

  function tablaLista() {
    const vistaF = P.ordenarEntradas(P.filtrarEntradas(entradas, filtros));
    return ui.tabla({
      etiqueta: 'Mejoras pendientes', maxFilas: 200, filas: vistaF, vacio: 'Ninguna nota coincide con los filtros.',
      claseFila: (e) => (e.estado !== 'resuelta' && e.severidad === 'alta' ? 'fila-aviso' : ''),
      columnas: [
        { clave: 'estado', titulo: 'Estado', ancho: '200px', orden: (e) => P.ESTADOS.indexOf(e.estado), formato: (est, e) => {
          const sig = P.siguienteEstado(est);
          return el('span', { class: 'u2-fila', style: { flexWrap: 'nowrap', gap: '6px' } }, W.tagEstadoPulido(est),
            el('button', { type: 'button', class: ['btn btn--chico', est === 'abierta' && 'btn--primario'], title: `Pasar a «${P.TITULO_ESTADO[sig]}»`, onclick: (ev) => { ev.stopPropagation(); ev.currentTarget.disabled = true; cambiarEstado(e.id, sig); } }, P.etiquetaSiguiente(est)));
        } },
        { clave: 'severidad', titulo: 'Gravedad', ancho: '100px', orden: (e) => ({ alta: 0, media: 1, baja: 2 }[e.severidad] ?? 3), formato: (s) => W.tagSeveridadPulido(s) },
        { clave: 'etapa', titulo: 'Etapa', ancho: '170px', orden: (e) => V.posicionEtapa(e.etapa), formato: (id) => (id ? el('span', { class: 'u2-fila', style: { flexWrap: 'nowrap' } }, W.codigo(id), el('span', { class: 'u2-tenue' }, V.NOMBRES_HUMANOS[id] || P.nombreEtapaPulido(id))) : '—') },
        { clave: 'oferta_id', titulo: 'Oferta', ancho: '140px', formato: (o) => (o ? el('a', { class: 'enlace', href: `#/oferta/${encodeURIComponent(o)}`, onclick: (ev) => ev.stopPropagation() }, o) : W.tag('General', 'info', { suave: true, icono: 'globo' })) },
        { clave: 'titulo', titulo: 'Qué hay que corregir', clase: 'cel-larga', formato: (t, e) => el('div', { class: 'u2-celda-titulo' },
          el('strong', null, t || '(sin título)'), e.detalle ? el('span', { style: { whiteSpace: 'normal' } }, e.detalle) : null,
          el('span', { class: 'u2-fila', style: { gap: '8px', whiteSpace: 'normal' } }, W.tagTipoPulido(e.tipo), W.cuando(e.ts), ui.soloTecnico(el('code', null, e.id)))) },
      ],
    });
  }

  function pintarContenido() {
    limpiar(hostContenido);
    const filtradas = P.filtrarEntradas(entradas, { ...filtros, ocultarResueltas: vista === 'lista' ? filtros.ocultarResueltas : false });
    conteoTxt.textContent = P.hayFiltros(filtros) ? `${filtradas.length} de ${entradas.length} notas` : `${entradas.length} notas`;
    limpiarBoton.disabled = !P.hayFiltros(filtros);
    ocultar.hidden = vista !== 'lista';
    if (!entradas.length) {
      hostContenido.appendChild(ui.vacioConPasos({
        titulo: 'Tu bitácora está vacía: todavía no anotaste nada',
        explicacion: 'Aquí va todo lo que corriges mientras armas una oferta a mano. Esa lista, ordenada por etapa, se convierte en reglas de la guía de trabajo (skill) de cada etapa, hasta que cada paso corra solo.',
        icono: 'lapiz',
        pasos: [
          { texto: 'Abre una oferta y trabaja una etapa a mano (o revisa lo que produjo el sistema).' },
          { texto: 'Cada vez que corrijas algo, anótalo arriba en una línea: elige la etapa y la gravedad.' },
          { texto: 'Cuando lo corrijas del todo, muévelo a «Resuelta». Una etapa sin pendientes está lista para automatizarse.' },
        ],
      }));
      return;
    }
    if (vista === 'lista') { hostContenido.appendChild(tablaLista()); return; }
    if (!filtradas.length) {
      hostContenido.appendChild(ui.vacioConPasos({ titulo: 'Ninguna nota coincide con los filtros', explicacion: 'Prueba a quitar algún filtro o a buscar otra palabra.', icono: 'filtro', pasos: [{ texto: 'Pulsa «Limpiar filtros» para ver todo el tablero.' }] }));
      return;
    }
    hostContenido.appendChild(el('div', { class: 'u2-tablero' }, P.columnasTablero(entradas, filtros).map(columna)));
  }

  function pintar() { poblarOfertas(); pintarMetricas(); pintarMapa(); pintarGravedad(); pintarContenido(); }

  async function recargarDatos() {
    try {
      const r = await ctx.api.sobre('/pulido');
      fuente = r; entradas = P.normalizarEntradas(r.datos); ultimaFirma = firma(r.datos);
    } catch (err) { toast(`No se pudo releer la bitácora: ${err.mensaje || err.message}`, 'error'); }
    pintar();
  }

  const pagina = el('div', { class: 'pagina' },
    ui.encabezadoPagina({
      titulo: 'Mejoras pendientes',
      descripcion: 'Lo que corriges en cada paso hasta que la fábrica corra sola. Anótalo al verlo; cuando una etapa se queda sin pendientes, está lista para automatizarse.',
      acciones: [ui.fuente(sobre.fuente, { leido: sobre.generado_en }), el('button', { type: 'button', class: 'btn btn--primario', onclick: anotar }, icono('lapiz', { tam: 14 }), 'Anotar con detalle')],
    }),
    rapida, hostMetricas,
    el('section', { class: 'u2-bloque', 'aria-labelledby': 'u2-mapa-t' },
      el('div', { class: 'u2-bloque__cab' }, el('h2', { id: 'u2-mapa-t' }, 'Estado de pulido por etapa'), el('span', { class: 'u2-nota' }, 'Clic en una etapa para ver solo sus notas; otro clic la quita.')),
      el('div', { class: 'u2-pila' }, hostMapa, hostGravedad)),
    barraFiltros, hostContenido);

  sincronizarControles();
  pintar();

  activa = { host: pagina, recargar: recargarDatos };
  ctx.alSalir(() => { if (activa && activa.host === pagina) activa = null; });
  void fuente;
  return pagina;
}

/** Actualiza en el sitio: no se re-renderiza la pantalla (se conservan filtros, foco y desplazamiento). */
export async function alCambio(ctx, evento) {
  if (!activa || !activa.host.isConnected) return undefined;
  const lote = Array.isArray(evento && evento.lote) && evento.lote.length ? evento.lote : [evento];
  const toca = lote.some((e) => e && e.tipo === 'empresa' && String(e.ruta || '').includes('pulido'));
  if (toca) { await activa.recargar(); return undefined; }
  if (lote.some((e) => e && e.tipo === 'sondeo')) {
    try {
      const d = await ctx.api.get('/pulido');
      if (firma(d) !== ultimaFirma) await activa.recargar();
    } catch (_) { /* sin conexión */ }
  }
  return undefined;
}
