// pages/registro.js — auditoría en vivo del registro: sello de integridad visible, filtros claros, línea de tiempo en lenguaje humano (o tabla técnica)
// y detalle de cada evento a un clic. Solo lectura. Lógica pura en ../lib/registro.js.
// `alCambio` añade solo las líneas nuevas (GET /registro?desde=<siguiente>): filtros, selección y scroll no se pierden.

import {
  paramsConsulta, fusionarLineas, estadoCadena, tonoDeLinea, valoresDistintos, filtrarLocal, siguienteDesde, desdeAnterior, lineaComoTexto, chipResultado,
  describirEvento, rotuloEvento, relativoSeguro, tituloIntegridad, contarCategorias, filtrarCategoria, agruparPorDia, detalleTecnicoLinea, CATEGORIAS, EVENTOS, ETAPAS_REGISTRO, LIMITE_PAGINA, MAX_LINEAS_MEMORIA,
} from '../lib/registro.js';
import { COMANDO_VERIFICAR_REGISTRO } from '../lib/resumen.js';

export const meta = { ruta: 'registro', titulo: 'Historial', grupo: 'Cerebro', icono: 'lista', escucha: ['registro', 'empresa'] };

const COMANDO_CREAR = '.venv/bin/python -m engine.orq crear --brief ofertas/<id>/00-brief.yaml';
const PASO_VISIBLES = 120;

// preferencias de la sesión (sobreviven a la navegación dentro de la pestaña)
const prefs = { vista: 'linea' };

const CSS = `
.u1g-sello { display: grid; grid-template-columns: auto minmax(0, 1fr) minmax(260px, 0.9fr); gap: var(--e-5, 24px); align-items: center; padding: var(--e-5, 24px); background: var(--sup); border: 1px solid var(--borde); border-radius: 12px; box-shadow: var(--sombra); }
@media (max-width: 900px) { .u1g-sello { grid-template-columns: auto minmax(0, 1fr); } .u1g-sello__tecnico { grid-column: 1 / -1; } }
@media (max-width: 520px) { .u1g-sello { grid-template-columns: minmax(0, 1fr); } }
.u1g-sello__medalla { position: relative; width: 68px; height: 68px; border-radius: 50%; display: grid; place-items: center; background: var(--neutro-bg); color: var(--neutro); border: 2px solid var(--neutro-borde); }
.u1g-sello[data-tono="ok"] .u1g-sello__medalla { background: var(--ok-bg); color: var(--ok); border-color: var(--ok); }
.u1g-sello[data-tono="error"] .u1g-sello__medalla { background: var(--error-bg); color: var(--error); border-color: var(--error); }
.u1g-sello[data-tono="ok"] { border-color: var(--ok-borde); }
.u1g-sello[data-tono="error"] { border-color: var(--error); background: var(--error-bg); }
.u1g-sello h2 { margin: 0 0 4px; font-size: 20px; font-weight: 600; line-height: 1.25; }
.u1g-sello[data-tono="ok"] h2 { color: var(--ok); }
.u1g-sello[data-tono="error"] h2 { color: var(--error); }
.u1g-sello p { margin: 0 0 4px; font-size: 13.5px; color: var(--txt-2); line-height: 1.5; }
.u1g-sello__meta { font-size: 12.5px; color: var(--txt-3); font-variant-numeric: tabular-nums; }
.u1g-sello__meta .chip { margin-right: 6px; }

.u1g-filtros { display: flex; flex-direction: column; gap: var(--e-3, 12px); }
.u1g-filtros__fila { display: flex; flex-wrap: wrap; gap: var(--e-2, 8px) var(--e-3, 12px); align-items: end; }
.u1g-campo { display: flex; flex-direction: column; gap: 4px; font-size: 12px; font-weight: 500; color: var(--txt-2); min-width: 0; }
.u1g-campo--buscar { flex: 1 1 240px; }
.u1g-campo .campo { min-width: 130px; }
.u1g-campo--buscar .campo { width: 100%; }
.u1g-cats { display: flex; flex-wrap: wrap; gap: 6px; }
.u1g-cat { display: inline-flex; align-items: center; gap: 6px; padding: 5px 12px; border: 1px solid var(--borde); border-radius: 999px; background: var(--sup); color: var(--txt-2); font: inherit; font-size: 13px; cursor: pointer; transition: background .12s ease, border-color .12s ease; }
.u1g-cat:hover { border-color: var(--borde-fuerte); background: var(--sup-2); }
.u1g-cat:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }
.u1g-cat[aria-pressed="true"] { background: var(--acento-bg); border-color: var(--acento); color: var(--acento-fuerte); font-weight: 600; }
.u1g-cat__n { font-variant-numeric: tabular-nums; font-size: 12px; color: var(--txt-3); }
.u1g-cat[aria-pressed="true"] .u1g-cat__n { color: var(--acento-fuerte); }
.u1g-cat[data-id="atencion"] .u1g-cat__n[data-hay="1"] { color: var(--aviso); font-weight: 600; }
.u1g-barra { display: flex; flex-wrap: wrap; gap: var(--e-2, 8px) var(--e-3, 12px); align-items: center; justify-content: space-between; }
.u1g-cuenta { font-size: 12.5px; color: var(--txt-2); font-variant-numeric: tabular-nums; }
.u1g-vista { display: inline-flex; border: 1px solid var(--borde); border-radius: 8px; overflow: hidden; background: var(--sup); }
.u1g-vista button { display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border: 0; background: transparent; color: var(--txt-2); font: inherit; font-size: 13px; cursor: pointer; }
.u1g-vista button + button { border-left: 1px solid var(--borde); }
.u1g-vista button[aria-pressed="true"] { background: var(--acento-bg); color: var(--acento-fuerte); font-weight: 600; }
.u1g-vista button:focus-visible { outline: 2px solid var(--foco); outline-offset: -2px; }

.u1g-dias { display: flex; flex-direction: column; gap: var(--e-5, 24px); margin-top: var(--e-3, 12px); }
@media (max-width: 640px) { .u1g-filtros__fila { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); } .u1g-campo--buscar { grid-column: 1 / -1; } .u1g-campo .campo { min-width: 0; width: 100%; } .u1g-sello__medalla { width: 52px; height: 52px; } }
.u1g-dia h3 { margin: 0 0 var(--e-2, 8px); font-size: 12px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; color: var(--txt-3); display: flex; gap: 8px; align-items: baseline; }
.u1g-dia h3 span { font-weight: 400; letter-spacing: 0; text-transform: none; }
.u1g-lista { list-style: none; margin: 0; padding: 0; position: relative; }
.u1g-lista::before { content: ""; position: absolute; left: 15px; top: 18px; bottom: 18px; width: 2px; background: var(--borde); }
.u1g-ev { position: relative; display: grid; grid-template-columns: 32px minmax(0, 1fr) auto; gap: 12px; align-items: start; padding: 2px 0; }
.u1g-ev__nodo { position: relative; z-index: 1; width: 32px; height: 32px; margin-top: 6px; border-radius: 50%; display: grid; place-items: center; background: var(--neutro-bg); color: var(--neutro); border: 2px solid var(--sup); }
.u1g-ev[data-tono="ok"] .u1g-ev__nodo { background: var(--ok-bg); color: var(--ok); }
.u1g-ev[data-tono="aviso"] .u1g-ev__nodo { background: var(--aviso-bg); color: var(--aviso); }
.u1g-ev[data-tono="error"] .u1g-ev__nodo { background: var(--error-bg); color: var(--error); }
.u1g-ev[data-tono="info"] .u1g-ev__nodo { background: var(--info-bg); color: var(--info); }
.u1g-ev__cuerpo { display: flex; flex-direction: column; gap: 3px; text-align: left; width: 100%; padding: 8px 12px; border: 1px solid transparent; border-radius: 10px; background: transparent; color: inherit; font: inherit; cursor: pointer; min-width: 0; }
.u1g-ev__cuerpo:hover { background: var(--sup); border-color: var(--borde); }
.u1g-ev__cuerpo:focus-visible { outline: 2px solid var(--foco); outline-offset: 1px; }
.u1g-ev__tit { font-size: 14px; line-height: 1.4; color: var(--txt); overflow-wrap: anywhere; }
.u1g-ev__det { font-size: 12.5px; color: var(--txt-2); }
.u1g-ev__meta { display: flex; flex-wrap: wrap; gap: 2px 10px; font-size: 12px; color: var(--txt-2); }
.u1g-ev__meta b { font-weight: 600; color: var(--txt); }
.u1g-ev__lado { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; padding-top: 10px; font-size: 12px; color: var(--txt-3); white-space: nowrap; font-variant-numeric: tabular-nums; }
.u1g-ev.fila-nueva .u1g-ev__cuerpo { background: var(--acento-bg); border-color: var(--acento); }
@media (max-width: 640px) { .u1g-ev { grid-template-columns: 32px minmax(0, 1fr); } .u1g-ev__lado { grid-column: 2; flex-direction: row; align-items: center; padding: 0 12px 6px; } }
.u1g-mas { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; margin-top: var(--e-4, 16px); }
.u1g-detalle { display: flex; flex-direction: column; gap: var(--e-4, 16px); }
.u1g-detalle__frase { margin: 0; font-size: 15px; line-height: 1.5; }
.u1g-detalle__chips { display: flex; flex-wrap: wrap; gap: 6px; }
`;

export async function render(ctx) {
  const U = ctx.ui;
  const { el, fmt, chip, seccion, vacio, vacioConPasos, errorBox, comando, encabezadoPagina, fuente, kv, visorJson, modal, copiar, reemplazar, icono, detalleTecnico, ayuda } = U;
  U.instalarEstilos('u1-registro', CSS);
  if (ctx.params.vista === 'tabla' || ctx.params.vista === 'linea') prefs.vista = ctx.params.vista; // p. ej. #/registro?vista=tabla

  // estado de la pantalla (vive en `ctx`: alCambio lo reutiliza)
  const S = {
    lineas: [], total: 0, siguiente: 1, cadenaOk: null, vacio: false, fuente: [], generado: null, avisos: [],
    filtros: { oferta: ctx.params.oferta || ctx.estado.ofertaActiva || '', etapa: ctx.params.etapa || '', agente: ctx.params.agente || '' },
    locales: { evento: '', resultado: '', texto: '' }, categoria: 'todo', visibles: PASO_VISIBLES,
    vivo: true, nuevas: new Set(), cargando: false, error: null,
  };
  ctx._reg = S;

  const zonaSello = el('div');
  const zonaCats = el('div', { class: 'u1g-cats', role: 'group', 'aria-label': 'Filtro rápido por tipo de evento' });
  const zonaCuenta = el('span', { class: 'u1g-cuenta', 'aria-live': 'polite' });
  const zonaContenido = el('div', { class: 'pila' });
  const zonaPie = el('div');
  const zonaMas = el('div', { class: 'u1g-mas' });
  let tablaEl = null;
  let tablaConFilas = false;

  async function pedirPagina(params) {
    const r = await ctx.api.sobre('/registro', params);
    const d = r.datos && typeof r.datos === 'object' ? r.datos : {};
    return { r, d };
  }

  function aplicarRespuesta({ r, d }, { reemplazarTodo }) {
    const f = fusionarLineas(reemplazarTodo ? [] : S.lineas, d.lineas || []);
    S.lineas = f.lineas;
    S.nuevas = reemplazarTodo ? new Set() : new Set(f.agregadas);
    S.total = Number.isInteger(d.total) ? d.total : S.total;
    S.siguiente = siguienteDesde(S.lineas, d.siguiente);
    S.cadenaOk = d.cadena_ok === undefined ? null : d.cadena_ok;
    S.vacio = r.vacio; S.fuente = r.fuente; S.generado = r.generado_en; S.avisos = r.avisos;
    S.error = null;
  }

  async function cargarInicial() {
    S.cargando = true; S.visibles = PASO_VISIBLES; pintar();
    try {
      aplicarRespuesta(await pedirPagina(paramsConsulta(S.filtros)), { reemplazarTodo: true });
    } catch (err) { S.error = err; }
    S.cargando = false; pintar();
  }

  async function traerNuevas() {
    if (S.cargando) return;
    try {
      const antes = S.lineas.length;
      const habiaNuevas = S.nuevas.size > 0;
      const p = await pedirPagina(paramsConsulta({ ...S.filtros, desde: S.siguiente }));
      // archivo truncado o rotado: lo que había ya no vale
      if (Number.isInteger(p.d.total) && p.d.total < S.total) { aplicarRespuesta(await pedirPagina(paramsConsulta(S.filtros)), { reemplazarTodo: true }); }
      else aplicarRespuesta(p, { reemplazarTodo: false });
      if (S.lineas.length !== antes || S.nuevas.size || habiaNuevas) pintar();
      else pintarSello();
    } catch (err) { S.error = err; pintarSello(); }
  }

  S.traer = traerNuevas;

  async function cargarAnteriores() {
    const desde = desdeAnterior(S.lineas, LIMITE_PAGINA);
    if (desde === null) return;
    S.cargando = true; pintar();
    try {
      const limite = Math.max(1, Math.min(LIMITE_PAGINA, Math.min(...S.lineas.map((l) => l.n)) - desde));
      const p = await pedirPagina(paramsConsulta({ ...S.filtros, desde, limite }));
      const total = S.total; const sig = S.siguiente; const cad = S.cadenaOk;
      aplicarRespuesta(p, { reemplazarTodo: false });
      S.total = total || S.total; S.siguiente = Math.max(sig, S.siguiente); S.nuevas = new Set(); if (p.d.cadena_ok !== undefined) S.cadenaOk = p.d.cadena_ok; else S.cadenaOk = cad;
      S.visibles += LIMITE_PAGINA;
    } catch (err) { U.toast(`No se pudo cargar lo anterior: ${err.mensaje || err.message}`, 'error'); }
    S.cargando = false; pintar();
  }

  // ── detalle de un evento: primero la frase humana; lo técnico (ids, hashes, JSON, comando) a un clic ──
  function abrirDetalle(l) {
    const v = describirEvento(l);
    const r = l.resultado || {};
    const rc = chipResultado(r.estado);
    const costo = l.costo_estimado && Number.isSafeInteger(l.costo_estimado.monto) ? fmt.dinero(l.costo_estimado.monto, l.costo_estimado.moneda) : null;
    modal({
      titulo: `Evento #${l.n} · ${rotuloEvento(l.evento)}`, ancho: '720px',
      cuerpo: el('div', { class: 'u1g-detalle' },
        el('p', { class: 'u1g-detalle__frase' }, v.titulo),
        el('div', { class: 'u1g-detalle__chips' },
          chip(rotuloEvento(l.evento), v.tono, { icono: v.icono }), r.estado ? chip(rc.texto, rc.tono) : null,
          v.live ? chip('En real', 'critico') : (v.simulado ? chip('Simulado', 'info', { icono: false }) : null), v.etapa ? chip(v.etapa, 'neutro', { icono: false }) : null, v.oferta ? chip(v.oferta, 'neutro', { icono: false }) : null),
        kv([
          ['Hora', l.ts ? `${fmt.fecha(l.ts, { segundos: true })} (${fmt.relativo(l.ts)})` : null], ['Quién', v.actor], ['Oferta', l.oferta_id], ['Etapa', v.etapa || l.etapa],
          ['Texto original', l.entrada_resumen], ['Costo estimado', costo],
          ['Texto procesado por la IA', l.tokens ? `${fmt.num(l.tokens.entrada)} de entrada · ${fmt.num(l.tokens.salida)} de salida` : null],
        ]),
        detalleTecnico('Detalle técnico', [
          kv(detalleTecnicoLinea(l).map(([k, val]) => [k, /^(hash|hash_previo|ejecucion_id)$/.test(k) ? el('code', null, String(val)) : String(val)])),
          comando(COMANDO_VERIFICAR_REGISTRO, { titulo: 'Comprobar que todo el historial está intacto', nota: 'Vuelve a calcular las huellas de todo el historial desde cero.' }),
          visorJson(l, { colapsado: true, titulo: `Evento ${l.n}` }),
        ])),
      acciones: [{ texto: 'Copiar los datos del evento', alClick: () => { copiar(lineaComoTexto(l)); return false; } }, { texto: 'Cerrar', tono: 'primario' }],
    });
  }

  // ── sello de integridad ──
  function pintarSello() {
    const c = estadoCadena(S.cadenaOk, { vacio: S.vacio });
    const titulo = tituloIntegridad(c.tono, c.texto);
    const frase = c.tono === 'ok' ? 'Cada evento queda atado al anterior: si alguien editara el historial, se notaría aquí.' : c.detalle;
    reemplazar(zonaSello, el('section', { class: 'u1g-sello', 'data-tono': c.tono, 'aria-label': 'Integridad del historial' },
      el('div', { class: 'u1g-sello__medalla' }, icono(c.tono === 'ok' ? 'cumplimiento' : c.tono === 'error' ? 'alerta' : 'reloj', { tam: 30 })),
      el('div', null,
        el('h2', null, titulo, ' ', ayuda('cadena_ok')),
        el('p', null, frase),
        el('p', { class: 'u1g-sello__meta' },
          [S.vacio ? null : `${fmt.num(S.total)} evento${S.total === 1 ? '' : 's'} en el historial · ${fmt.num(S.lineas.length)} cargado${S.lineas.length === 1 ? '' : 's'}`,
            S.generado && !S.vacio ? `verificado ${fmt.relativo(S.generado)}` : null].filter(Boolean).join(' · '),
          S.error ? [' ', chip(`error al actualizar: ${S.error.mensaje || S.error.message}`, 'error')] : null)),
      el('div', { class: 'u1g-sello__tecnico' },
        detalleTecnico('Comprobación completa desde la terminal', comando(COMANDO_VERIFICAR_REGISTRO, { titulo: 'Cómo comprobarlo', nota: 'Vuelve a calcular todas las huellas del historial. Esta pantalla ya hace una comprobación rápida cada vez que lee el archivo.' })))));
  }

  function pintarPie() {
    reemplazar(zonaPie, U.fuenteInfo({ fuente: S.fuente, generado_en: S.generado, vacio: S.vacio, avisos: S.avisos }));
  }

  function lineasFiltradas() {
    return filtrarCategoria(filtrarLocal(S.lineas, S.locales), S.categoria);
  }

  function pintarCats() {
    const cuenta = contarCategorias(filtrarLocal(S.lineas, S.locales));
    reemplazar(zonaCats, CATEGORIAS.map((c) => el('button', { type: 'button', class: 'u1g-cat', 'data-id': c.id, 'aria-pressed': String(S.categoria === c.id), onclick: () => { S.categoria = c.id; S.visibles = PASO_VISIBLES; pintar(); } },
      c.rotulo, el('span', { class: 'u1g-cat__n', 'data-hay': cuenta[c.id] ? '1' : '0' }, String(cuenta[c.id] || 0)))));
  }

  // ── línea de tiempo ──
  function itemLinea(l) {
    const v = describirEvento(l);
    const rc = chipResultado(l.resultado && l.resultado.estado);
    const notable = ['error', 'bloqueado'].includes(l.resultado && l.resultado.estado);
    return el('li', { class: ['u1g-ev', S.nuevas.has(l.n) && 'fila-nueva'], 'data-tono': v.tono, 'data-n': String(l.n) },
      el('span', { class: 'u1g-ev__nodo', 'aria-hidden': 'true' }, icono(v.icono, { tam: 16 })),
      el('button', { type: 'button', class: 'u1g-ev__cuerpo', onclick: () => abrirDetalle(l), 'aria-label': `Ver el detalle del evento ${l.n}: ${v.titulo}` },
        el('span', { class: 'u1g-ev__tit' }, v.titulo),
        v.detalle ? el('span', { class: 'u1g-ev__det' }, v.detalle) : null,
        el('span', { class: 'u1g-ev__meta' }, v.oferta ? el('span', null, v.oferta) : null, v.etapa ? el('span', null, v.etapa) : null, el('b', null, v.actor), v.simulado && !S.todoSimulado ? el('span', null, 'simulado') : null)),
      el('span', { class: 'u1g-ev__lado' },
        el('span', { title: l.ts ? fmt.fecha(l.ts, { segundos: true }) : null }, l.ts ? relativoSeguro(l.ts) : '—'),
        v.live ? chip('En real', 'critico') : null, notable ? chip(rc.texto, rc.tono) : null));
  }

  function pintarLinea(visibles) {
    tablaEl = null; tablaConFilas = false;
    const cortadas = visibles.slice().sort((a, b) => b.n - a.n).slice(0, S.visibles);
    const grupos = agruparPorDia(cortadas);
    reemplazar(zonaContenido, el('div', { class: 'u1g-dias' }, grupos.map((g) => el('section', { class: 'u1g-dia' },
      el('h3', null, g.rotulo, el('span', null, `${g.lineas.length} evento${g.lineas.length === 1 ? '' : 's'}`)),
      el('ol', { class: 'u1g-lista' }, g.lineas.map(itemLinea))))));
    return visibles.length - cortadas.length;
  }

  // ── tabla técnica ──
  function pintarTabla(visibles) {
    // actualización incremental: conserva el orden elegido y la posición del scroll mientras llegan líneas
    if (tablaEl && tablaEl.parentNode === zonaContenido && visibles.length && tablaConFilas) { tablaEl.actualizarFilas(visibles); return 0; }
    tablaConFilas = visibles.length > 0;
    const nuevo = U.tabla({
      etiqueta: 'Historial de eventos', maxFilas: 300, altoMax: '62vh', ordenInicial: { clave: 'n', dir: 'desc' },
      claseFila: (l) => (S.nuevas.has(l.n) ? 'fila-nueva' : ''),
      columnas: [
        { clave: 'n', titulo: '#', ancho: '52px', alinear: 'der' },
        { clave: 'ts', titulo: 'Hora', ancho: '132px', formato: (v) => fmt.fecha(v) },
        { clave: 'oferta_id', titulo: 'Oferta · etapa', ancho: '150px', formato: (v, l) => (v || l.etapa ? `${v || '—'}${l.etapa ? ' · ' + l.etapa : ''}` : null), orden: (l) => `${l.oferta_id || ''} ${l.etapa || ''}` },
        { clave: 'agente', titulo: 'Agente', ancho: '150px' },
        { clave: 'evento', titulo: 'Evento', ancho: '165px', formato: (v, l) => (l._ilegible ? chip('línea ilegible', 'error') : chip(v ? rotuloEvento(v) : '—', tonoDeLinea(l))) },
        { clave: 'entrada_resumen', titulo: 'Resumen', clase: 'cel-larga', formato: (v, l) => (l._ilegible ? el('span', { class: 'texto-tenue' }, `No se pudo interpretar: ${String(l._texto || '').slice(0, 200)}`) : v ? el('span', { title: l.herramienta ? `Herramienta: ${l.herramienta}` : null }, v) : null) },
        { clave: 'resultado.estado', titulo: 'Resultado', ancho: '150px', formato: (v, l) => { const c = chipResultado(v); return el('span', { class: 'fila-flex' }, chip(c.texto, c.tono), l.modo === 'live' ? chip('En real', 'critico') : null); } },
        { clave: 'costo_estimado', titulo: 'Costo', ancho: '84px', alinear: 'der', formato: (v) => (v && Number.isSafeInteger(v.monto) && v.monto > 0 ? fmt.dinero(v.monto, v.moneda) : null), orden: (l) => (l.costo_estimado && l.costo_estimado.monto) || 0 },
      ],
      filas: visibles, alClick: abrirDetalle,
      vacio: { texto: 'Ninguna línea coincide con los filtros.' },
    });
    reemplazar(zonaContenido, nuevo);
    tablaEl = nuevo;
    return 0;
  }

  function hayFiltros() {
    return Boolean(S.filtros.oferta || S.filtros.etapa || S.filtros.agente || S.locales.evento || S.locales.resultado || S.locales.texto || S.categoria !== 'todo');
  }

  function pintar() {
    pintarSello(); pintarPie(); pintarCats();
    const foco = typeof document !== 'undefined' ? document.activeElement : null;
    if (![selOferta, selEtapa, inAgente].includes(foco)) poblarSelectores();
    const anteriores = desdeAnterior(S.lineas, LIMITE_PAGINA);
    if (S.error && !S.lineas.length) { reemplazar(zonaContenido, errorBox(S.error, { reintentar: cargarInicial })); reemplazar(zonaMas); reemplazar(zonaCuenta); tablaEl = null; return; }
    if (S.cargando && !S.lineas.length) { reemplazar(zonaContenido, U.esqueleto ? U.esqueleto('tabla', 6) : U.cargando('Leyendo el historial…')); reemplazar(zonaMas); tablaEl = null; return; }
    if (S.vacio && !S.lineas.length) {
      reemplazar(zonaContenido, vacioConPasos({
        titulo: 'Aún no hay historial', explicacion: 'El historial lo crea el sistema con la primera acción que anota. Cada acción de un agente o del sistema queda aquí, en orden y protegida contra cambios.',
        pasos: [{ texto: 'Crea una oferta desde su ficha inicial para que el sistema empiece a registrar:', comando: COMANDO_CREAR }, { texto: 'Vuelve aquí: los eventos aparecen solos con la cola en vivo.' }], icono: 'lista',
      }));
      reemplazar(zonaMas); reemplazar(zonaCuenta);
      tablaEl = null;
      return;
    }
    const visibles = lineasFiltradas();
    S.todoSimulado = S.lineas.length > 0 && S.lineas.every((l) => l.modo === 'dry_run');
    reemplazar(zonaCuenta, `Mostrando ${fmt.num(visibles.length)} de ${fmt.num(S.lineas.length)} evento${S.lineas.length === 1 ? '' : 's'} cargado${S.lineas.length === 1 ? '' : 's'}`,
      S.todoSimulado ? [' · todos en simulación ', U.ayuda('dry_run')] : null);
    let ocultas = 0;
    if (!visibles.length) {
      tablaEl = null; tablaConFilas = false;
      reemplazar(zonaContenido, S.lineas.length
        ? vacio('Ningún evento cargado coincide con los filtros.', { pista: 'Quita el filtro rápido, el de evento o resultado, o el texto; también puedes cargar eventos anteriores.', icono: 'filtro' })
        : vacio('No hay eventos con esos filtros.', { pista: 'Cambia o limpia los filtros de oferta, etapa y agente.', icono: 'filtro' }));
    } else if (prefs.vista === 'tabla') ocultas = pintarTabla(visibles);
    else ocultas = pintarLinea(visibles);
    reemplazar(zonaMas,
      ocultas > 0 ? el('button', { type: 'button', class: 'btn btn--chico', onclick: () => { S.visibles += PASO_VISIBLES; pintar(); } }, `Mostrar ${Math.min(ocultas, PASO_VISIBLES)} más recientes (quedan ${fmt.num(ocultas)})`) : null,
      anteriores !== null ? el('button', { type: 'button', class: 'btn btn--chico', disabled: S.cargando ? true : null, onclick: cargarAnteriores }, `Cargar anteriores (${fmt.num(Math.min(...S.lineas.map((l) => l.n)) - 1)} más antiguas)`) : null,
      S.lineas.length >= MAX_LINEAS_MEMORIA ? el('span', { class: 'texto-tenue' }, `Se conservan las últimas ${fmt.num(MAX_LINEAS_MEMORIA)} líneas en pantalla.`) : null);
    limpiarBtn.hidden = !hayFiltros();
  }

  // ── filtros ──
  const opcion = (v, t) => el('option', { value: v }, t ?? v);
  const selOferta = el('select', { class: 'campo campo--chico', 'aria-label': 'Filtrar por oferta', onchange: (e) => { S.filtros.oferta = e.target.value; cargarInicial(); } });
  const selEtapa = el('select', { class: 'campo campo--chico', 'aria-label': 'Filtrar por etapa', onchange: (e) => { S.filtros.etapa = e.target.value; cargarInicial(); } }, opcion('', 'Todas'), ETAPAS_REGISTRO.map((e) => opcion(e)));
  const inAgente = el('input', { class: 'campo campo--chico', type: 'text', list: 'lista-agentes', placeholder: 'nombre interno, p. ej. d3-qa', 'aria-label': 'Filtrar por agente', maxlength: '60' });
  const listaAgentes = el('datalist', { id: 'lista-agentes' });
  inAgente.addEventListener('change', () => { S.filtros.agente = inAgente.value.trim(); cargarInicial(); });
  const selEvento = el('select', { class: 'campo campo--chico', 'aria-label': 'Filtrar por tipo de evento', onchange: (e) => { S.locales.evento = e.target.value; S.visibles = PASO_VISIBLES; pintar(); } }, opcion('', 'Todos'), EVENTOS.map((e) => opcion(e, rotuloEvento(e))));
  const selResultado = el('select', { class: 'campo campo--chico', 'aria-label': 'Filtrar por resultado', onchange: (e) => { S.locales.resultado = e.target.value; S.visibles = PASO_VISIBLES; pintar(); } }, opcion('', 'Todos'), ['ok', 'error', 'bloqueado', 'dry_run'].map((e) => opcion(e, chipResultado(e).texto)));
  const inTexto = el('input', { class: 'campo campo--chico', type: 'search', placeholder: 'Buscar en lo cargado…', 'aria-label': 'Buscar texto en las líneas cargadas', oninput: (e) => { S.locales.texto = e.target.value; S.visibles = PASO_VISIBLES; pintar(); } });
  const limpiarBtn = el('button', { type: 'button', class: 'btn btn--chico', hidden: true, onclick: () => {
    S.locales = { evento: '', resultado: '', texto: '' }; S.categoria = 'todo'; selEvento.value = ''; selResultado.value = ''; inTexto.value = '';
    const serv = Boolean(S.filtros.oferta || S.filtros.etapa || S.filtros.agente);
    S.filtros = { oferta: '', etapa: '', agente: '' };
    if (serv) cargarInicial(); else pintar();
  } }, icono('cerrar', { tam: 13 }), 'Limpiar filtros');

  function poblarSelectores() {
    const ids = new Set((ctx.estado.ofertas || []).map((o) => o.oferta_id).filter(Boolean));
    for (const v of valoresDistintos(S.lineas, 'oferta_id')) ids.add(v);
    if (S.filtros.oferta) ids.add(S.filtros.oferta);
    reemplazar(selOferta, opcion('', 'Todas'), [...ids].sort().map((i) => opcion(i)));
    selOferta.value = S.filtros.oferta;
    selEtapa.value = S.filtros.etapa;
    inAgente.value = S.filtros.agente;
    reemplazar(listaAgentes, valoresDistintos(S.lineas, 'agente').map((a) => el('option', { value: a })));
  }

  const interruptorVivo = U.interruptor({ etiqueta: 'Mostrar eventos nuevos al instante', activo: true, titulo: 'Los eventos nuevos aparecen solos, sin recargar', onCambio: (activo) => { S.vivo = activo; if (S.vivo) traerNuevas(); } });
  const campo = (t, control, clase) => el('label', { class: ['u1g-campo', clase] }, t, control);

  const botonesVista = el('div', { class: 'u1g-vista', role: 'group', 'aria-label': 'Forma de ver el historial' });
  function pintarBotonesVista() {
    reemplazar(botonesVista,
      el('button', { type: 'button', 'aria-pressed': String(prefs.vista === 'linea'), onclick: () => { prefs.vista = 'linea'; pintarBotonesVista(); pintar(); } }, icono('reloj', { tam: 14 }), 'Línea de tiempo'),
      el('button', { type: 'button', 'aria-pressed': String(prefs.vista === 'tabla'), onclick: () => { prefs.vista = 'tabla'; pintarBotonesVista(); pintar(); } }, icono('lista', { tam: 14 }), 'Tabla detallada'));
  }
  pintarBotonesVista();

  const marco = el('div', { class: 'pagina' },
    encabezadoPagina({
      titulo: 'Historial',
      descripcion: 'Todo lo que hicieron el sistema y los agentes, en orden y protegido contra cambios. Solo se mira: nadie puede editarlo sin que se note.',
      acciones: [
        interruptorVivo,
        el('button', { type: 'button', class: 'btn', onclick: cargarInicial }, icono('refrescar', { tam: 14 }), 'Recargar'),
      ],
    }),
    zonaSello,
    seccion('Eventos', [
      el('div', { class: 'u1g-filtros' },
        el('div', { class: 'u1g-filtros__fila' },
          campo('Buscar', inTexto, 'u1g-campo--buscar'), campo('Oferta', selOferta), campo('Etapa', selEtapa), el('label', { class: 'u1g-campo' }, 'Agente', inAgente, listaAgentes),
          campo('Tipo de evento', selEvento), campo('Resultado', selResultado), limpiarBtn),
        el('div', { class: 'u1g-barra' }, zonaCats, botonesVista),
        zonaCuenta),
      zonaContenido, zonaMas, zonaPie,
    ]),
  );

  await cargarInicial();
  poblarSelectores();
  return marco;
}

export async function alCambio(ctx, evento) {
  const S = ctx._reg;
  if (!S || !S.vivo) return;
  if (evento && evento.tipo && !['registro', 'empresa', 'sondeo'].includes(evento.tipo)) return;
  // `traerNuevas` vive en el cierre de render: se dispara con un evento de DOM sobre la propia pantalla
  if (typeof S.traer === 'function') await S.traer();
}
