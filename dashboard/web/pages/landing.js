// pages/landing.js — #/landing: la landing de la oferta activa (D5: landing, checkout y tracking).
// Vista previa en un marco de dispositivo (móvil / tablet / escritorio) con <iframe sandbox="allow-scripts"> (SIN allow-same-origin) servida
// por /sitio/<id>/…; checklist C01–C17 por grupos con icono de estado y «sin resultado» honesto; coherencia precio/moneda/garantía como tabla
// comparativa; legales, assets, cobro, medición y consentimiento. Lo técnico (rutas, ids de Stripe, hashes, comandos) va en «detalle técnico».
//
// SOLO LECTURA: ningún botón publica, despliega ni cobra. El HTML de la landing es dato no confiable: aquí solo se lee como
// TEXTO (lib/landing.js) y se muestra en el iframe aislado; nunca se inserta en el DOM del panel.

import * as L from '../lib/landing.js';
import { CSS_COMUN, CSS_LANDING } from '../lib/estilos-u3.js';

export const meta = { ruta: 'landing', titulo: 'Página de venta', grupo: 'Fábrica y tienda', icono: 'pagina', escucha: ['oferta'] };

let U = null;
let el; let chip; let seccion; let tabla; let tabs; let kv; let vacio; let errorBox; let comando; let reemplazar;
let fmt = null;

function usar(ctx) {
  U = ctx.ui;
  ({ el, chip, seccion, tabla, tabs, kv, vacio, errorBox, comando, reemplazar } = U);
  fmt = ctx.fmt || U.fmt;
  if (U.instalarEstilos) { U.instalarEstilos('u3-comun', CSS_COMUN); U.instalarEstilos('u3-landing', CSS_LANDING); }
}

const vista = { ancho: 'escritorio', tab: 'comprobaciones' };
let activo = null; // {ctx, raiz, cab, prev, datos, ofertaId, marco}
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

const archivoDe = (ctx, id, ruta) => leer(ctx, `/oferta/${id}/archivo`, { ruta });
const RE_QA = /^qa\/[A-Za-z0-9_.-]+\.json$/;

// ───────────────────────── render ─────────────────────────

export async function render(ctx) {
  usar(ctx);
  const cab = el('div', { class: 'u3-pila' });
  const arriba = el('div', { class: 'u3-pila' });
  const prev = el('div', { class: 'u3-pila' });
  const datos = el('div', { class: 'u3-pila' }, U.esqueleto ? U.esqueleto('pagina') : U.cargando('Leyendo la información de la página de venta…'));
  const raiz = el('div', { class: 'pagina' }, cab, arriba, prev, datos);
  activo = { ctx, raiz, cab, arriba, prev, datos, ofertaId: null, marco: null };
  await construir(ctx, { recargarMarco: true });
  return raiz;
}

export function alSalir() { activo = null; }

export function alCambio(ctx, ev) {
  if (!activo || enRefresco) return undefined;
  const lote = (ev && ev.lote) || (ev ? [ev] : []);
  const id = activo.ofertaId;
  const propios = lote.filter((e) => e && e.tipo !== 'sondeo' && (typeof e.ruta !== 'string' || e.ruta === '' || !id || e.ruta.includes(id)));
  if (!propios.length) return undefined;
  const a = typeof document !== 'undefined' ? document.activeElement : null;
  if (a && activo.raiz.contains(a) && /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName)) return undefined;
  const tocaSitio = propios.some((e) => typeof e.ruta === 'string' && /05-landing\/sitio/.test(e.ruta));
  enRefresco = true;
  construir(activo.ctx, { recargarMarco: tocaSitio }).catch((e) => console.error('refresco de la página de venta falló', e)).finally(() => { enRefresco = false; });
  return undefined;
}

// ───────────────────────── carga ─────────────────────────

function elegirOferta(ctx) {
  const lista = ctx.estado && Array.isArray(ctx.estado.ofertas) ? ctx.estado.ofertas : [];
  const activa = ctx.estado ? ctx.estado.ofertaActiva : null;
  return { activa: typeof activa === 'string' && L.RE_OFERTA_ID.test(activa) ? activa : null, lista, cruda: activa };
}

function cabecera(id) {
  return U.encabezadoPagina({
    titulo: 'Página de venta',
    descripcion: 'La página de venta, el cobro y la medición de la oferta activa: cómo se ve, qué comprobaciones pasa y qué falta. Solo lectura.',
    acciones: id ? [tag(id, 'acento', { titulo: 'Oferta activa' })] : [],
  });
}

function sinOferta(ctx, sel) {
  const botones = sel.lista.filter((o) => o && L.RE_OFERTA_ID.test(String(o.oferta_id))).slice(0, 12).map((o) => el('button', {
    type: 'button', class: 'btn btn--chico', onclick: () => ctx.estado.fijar({ ofertaActiva: o.oferta_id }),
  }, o.oferta_id + (o.demo ? ' (demostración)' : '')));
  return pila(
    U.vacioConPasos({
      titulo: sel.cruda ? `La oferta activa «${String(sel.cruda).slice(0, 40)}» no es un código de oferta válido` : 'No hay una oferta activa',
      explicacion: 'Aquí se ve la página de venta de una oferta: su vista previa, las comprobaciones de calidad, el precio, el cobro y la medición.',
      pasos: [{ texto: 'Elige una oferta en el selector de la barra superior' + (sel.cruda ? ' (el código de la oferta debe tener la forma OF-AAAAMM-NN).' : '.') }],
      icono: 'pagina',
    }),
    botones.length ? el('div', { class: 'u3-fila' }, el('span', { class: 'u3-tenue' }, 'Ofertas disponibles:'), botones) : null);
}

async function construir(ctx, { recargarMarco }) {
  const a = activo;
  const sel = elegirOferta(ctx);
  if (!sel.activa) {
    a.ofertaId = null; a.marco = null;
    reemplazar(a.cab, cabecera(null));
    reemplazar(a.arriba); reemplazar(a.prev);
    reemplazar(a.datos, sinOferta(ctx, sel));
    return;
  }
  const id = sel.activa;
  a.ofertaId = id;
  const [det, ofe, chk, ast, trk, rts, dep, idx] = await Promise.all([
    leer(ctx, `/oferta/${id}`),
    archivoDe(ctx, id, '03-oferta/oferta.json'),
    archivoDe(ctx, id, '05-landing/checkout.json'),
    archivoDe(ctx, id, '05-landing/assets.json'),
    archivoDe(ctx, id, '05-landing/tracking.json'),
    archivoDe(ctx, id, '05-landing/rutas.json'),
    archivoDe(ctx, id, '05-landing/despliegue.json'),
    archivoDe(ctx, id, '05-landing/sitio/index.html'),
  ]);
  if (!det.ok) {
    reemplazar(a.cab, cabecera(id));
    reemplazar(a.arriba); reemplazar(a.prev);
    reemplazar(a.datos, det.error && det.error.codigo === 'no_encontrado'
      ? U.vacioConPasos({ titulo: `La oferta ${id} no existe`, explicacion: 'No hay una carpeta con ese nombre dentro de las ofertas.', pasos: [{ texto: 'Elige otra oferta en el selector de la barra superior.' }], icono: 'pagina' })
      : errorBox(det.error, { reintentar: () => ctx.recargar() }));
    return;
  }
  const etapa = L.etapaD5(det.datos);
  const q = L.elegirQaD5(etapa ? etapa.qa : []);
  const rutaQa = (x) => {
    if (!x) return null;
    const r = String(x.archivo ?? x.ruta ?? '');
    const c = r.includes('/') ? r : `qa/${r}`;
    return RE_QA.test(c) ? c : null;
  };
  const rd5 = rutaQa(q.d5);
  const rx1 = rutaQa(q.x1);
  const [qaD5, qaX1] = await Promise.all([rd5 ? archivoDe(ctx, id, rd5) : null, rx1 ? archivoDe(ctx, id, rx1) : null]);

  const d = {
    ctx, id, det, etapa,
    oferta: L.jsonDeArchivo(ofe.ok ? ofe.datos : null),
    checkout: L.jsonDeArchivo(chk.ok ? chk.datos : null),
    assets: L.jsonDeArchivo(ast.ok ? ast.datos : null),
    tracking: L.jsonDeArchivo(trk.ok ? trk.datos : null),
    rutas: L.jsonDeArchivo(rts.ok ? rts.datos : null),
    despliegue: L.jsonDeArchivo(dep.ok ? dep.datos : null),
    html: idx.ok ? L.textoDeArchivo(idx.datos) : null,
    qaD5: qaD5 && qaD5.ok ? L.jsonDeArchivo(qaD5.datos) : null,
    qaX1: qaX1 && qaX1.ok ? L.jsonDeArchivo(qaX1.datos) : null,
    qaD5Ruta: rd5, qaX1Ruta: rx1,
    lecturas: { ofe, chk, ast, trk, rts, dep, idx, qaD5, qaX1 },
  };
  d.sitioExiste = typeof d.html === 'string' && d.html.trim() !== '';
  d.checks = L.estadoChecks({ qa: d.qaD5, x1: d.qaX1 });
  d.coherencia = L.coherencia({ oferta: d.oferta, checkout: d.checkout, html: d.html });
  d.modeloAssets = L.modeloAssets(d.assets);
  d.modeloTracking = L.modeloTracking(d.tracking, d.checkout);
  d.modeloCheckout = L.modeloCheckout(d.checkout);
  d.qaR = L.resumenQa(d.qaD5);
  d.x1R = L.resumenQa(d.qaX1);

  reemplazar(a.cab, cabecera(id));
  reemplazar(a.arriba, atencionLanding(d), metricas(d));
  if (recargarMarco || !a.marco || a.marco.id !== id || a.marco.sitio !== d.sitioExiste) {
    a.marco = { id, sitio: d.sitioExiste };
    reemplazar(a.prev, vistaPrevia(d));
  }
  reemplazar(a.datos, montarTabs(d), pieDeFuentes(d));
}

// ───────────────────────── atención y métricas ─────────────────────────

function atencionLanding(d) {
  const archivos = [
    ['la pantalla de pago', d.checkout], ['las ranuras de imagen', d.assets], ['el plan de medición', d.tracking], ['el mapa de rutas', d.rutas], ['la página de venta', d.sitioExiste ? true : null],
  ];
  const faltan = archivos.filter(([, v]) => !v).map(([n]) => n);
  const items = L.avisosLanding({
    checks: d.checks, coherenciaR: d.coherencia.resumen, assets: d.modeloAssets, trackingProblemas: L.problemasTracking(d.modeloTracking),
    faltan, qaR: d.qaR, x1R: d.x1R, sitioExiste: d.sitioExiste, placeholders: d.modeloAssets.resumen.placeholders,
  }).map((x) => ({
    tono: x.tono, titulo: x.titulo, detalle: x.detalle,
    accion: x.tab ? { texto: 'Ver el detalle', onClick: () => irAPestana(x.tab) } : undefined,
  }));
  return U.atencion({ items, vacio: 'Todo en orden: la página de venta no tiene nada pendiente que requiera tu decisión.' });
}

function irAPestana(id) {
  vista.tab = id;
  const raiz = activo && activo.raiz;
  const boton = raiz ? raiz.querySelector(`[role="tab"][id$="-t-${id}"]`) : null;
  if (boton) { boton.click(); boton.scrollIntoView({ block: 'center', behavior: 'auto' }); }
}

function metricas(d) {
  const e = d.etapa;
  const cs = d.checks.resumen;
  const coh = d.coherencia.resumen;
  const qaR = d.qaR;
  const x1R = d.x1R;
  const estadoEtapa = e && e.estado ? U.infoEstado(e.estado).texto : 'Sin iniciar';
  return el('div', { class: 'u3-metricas' },
    U.metrica({ etiqueta: 'Etapa de la página de venta', ayuda: 'landing_pagina', valor: estadoEtapa, contexto: e && e.estado ? `versión ${t(e.version)}${e.gate_pendiente ? ' · espera tu firma' : ''}${e.ronda_qa ? ` · ronda de revisión ${e.ronda_qa}` : ''}` : 'aún no tiene estado', tono: e && e.estado === 'aprobado' ? 'ok' : e && (e.estado === 'bloqueado' || e.estado === 'escalado') ? 'grave' : e && e.gate_pendiente ? 'acento' : undefined }),
    U.metrica({ etiqueta: 'Comprobaciones C01–C17', valor: d.checks.hayResultadosC ? `${cs.ok} / ${cs.total}` : 'Sin resultados', contexto: d.checks.hayResultadosC ? `${cs.error} fallan · ${cs.aviso} con aviso · ${cs.sinResultado} sin resultado` : 'la revisión de calidad aún no las registró', tono: cs.error ? 'grave' : cs.aviso ? 'aviso' : d.checks.hayResultadosC ? 'ok' : undefined, ayuda: 'checks_c' }),
    U.metrica({ etiqueta: 'Precio y garantía', valor: d.coherencia.htmlDisponible || d.oferta || d.checkout ? (coh.error ? `${coh.error} difieren` : coh.ok ? 'Coinciden' : 'Sin comparar') : 'Sin datos', contexto: `${coh.ok} coinciden · ${coh.sinDato} sin dato suficiente`, tono: coh.error ? 'grave' : coh.ok ? 'ok' : undefined, ayuda: 'coherencia_c02' }),
    U.metrica({ etiqueta: 'Revisión de calidad', valor: qaR ? L.veredictoTexto(qaR.veredicto) : 'Sin informe', contexto: qaR ? `${qaR.puntaje ? `nota ${qaR.puntaje}/${t(qaR.umbral)} · ` : ''}${qaR.hallazgos} hallazgo${qaR.hallazgos === 1 ? '' : 's'}` : 'aún no hay informe de la revisión', ayuda: 'revision_qa', tono: qaR ? ({ ok: 'ok', aviso: 'aviso', error: 'grave' }[L.tonoVeredicto(qaR.veredicto)]) : undefined }),
    U.metrica({ etiqueta: 'Cumplimiento', valor: x1R ? L.veredictoTexto(x1R.veredicto, { cumplimiento: true }) : 'Sin informe', contexto: x1R ? 'informe de cumplimiento' : 'sin él no se publica', ayuda: 'dictamen_cumplimiento', tono: x1R ? ({ ok: 'ok', aviso: 'aviso', error: 'grave' }[L.tonoVeredicto(x1R.veredicto)]) : undefined }));
}

// ───────────────────────── vista previa en marco de dispositivo ─────────────────────────

function resumenSalida(d) {
  const filaEstado = (icono, tono, titulo, detalle) => el('div', { class: 'u3-item', style: { gridTemplateColumns: '22px minmax(0, 1fr)' } },
    el('span', { class: ['u3-item__icono', 'u3-estado', `u3-estado--${tono}`] }, ic(icono, 18)),
    el('div', null, el('div', { class: 'u3-item__titulo' }, titulo), el('div', { class: 'u3-item__detalle', style: { gridColumn: 'auto' } }, detalle)));
  const a = d.modeloAssets;
  const c = d.modeloCheckout;
  const tr = d.modeloTracking;
  const rt = d.rutas ? L.modeloRutas({ rutas: d.rutas, sondas: {}, artefactos: d.etapa ? d.etapa.artefactos : null }) : null;
  const legalesDecl = rt ? rt.legales.filter((x) => x.enRutas).length : null;
  return el('aside', { class: 'u3-lado', 'aria-label': 'Qué hay listo' },
    el('p', { class: 'u3-sobretitulo' }, 'Qué hay listo'),
    el('div', { class: 'u3-lista' },
      filaEstado(d.sitioExiste ? 'ok' : 'circulo', d.sitioExiste ? 'ok' : 'neutro', 'Página de venta', d.sitioExiste ? 'Generada: es lo que ves a la izquierda.' : 'Aún no se ha generado.'),
      filaEstado(c ? 'ok' : 'circulo', c ? 'ok' : 'neutro', 'Cobro', c ? `${c.precio}${c.garantia !== null ? ` · garantía de ${c.garantia} días` : ''}${c.priceLive ? '' : ' · precio real en Stripe pendiente'}` : 'Sin configurar.'),
      filaEstado(tr ? (tr.consentimiento.ok ? 'ok' : 'alerta') : 'circulo', tr ? (tr.consentimiento.ok ? 'ok' : 'aviso') : 'neutro', 'Medición y consentimiento', tr ? (tr.consentimiento.ok ? 'Aviso de cookies propio; nada va a Meta antes de que la persona acepte.' : 'La plataforma de consentimiento no es la prevista.') : 'Sin plan de medición.'),
      filaEstado(rt ? (legalesDecl === rt.legales.length ? 'ok' : 'alerta') : 'circulo', rt ? (legalesDecl === rt.legales.length ? 'ok' : 'aviso') : 'neutro', 'Páginas legales', rt ? `${legalesDecl} de ${rt.legales.length} anotadas en el mapa de rutas.` : 'Sin mapa de rutas.'),
      filaEstado(a.existe ? (a.resumen.pendientes ? 'alerta' : 'ok') : 'circulo', a.existe ? (a.resumen.pendientes ? 'aviso' : 'ok') : 'neutro', 'Imágenes', a.existe ? `${a.resumen.aprobadas} de ${a.resumen.declaradas} ranuras aprobadas.` : 'Sin ranuras declaradas.')));
}

function vistaPrevia(d) {
  if (!d.sitioExiste) {
    return U.vacioConPasos({
      titulo: 'Aún no hay página de venta para esta oferta',
      explicacion: 'La página de venta la prepara la etapa «Página de venta y pago» como un sitio simple guardado en tu computadora. Hasta entonces no hay nada que mostrar; este panel no la genera ni la publica.',
      pasos: [
        { texto: 'Genera el sitio con este comando (solo crea archivos en tu computadora; no publica nada).', comando: `.venv/bin/python -m landing.generar --oferta ${d.id} --json` },
        { texto: 'Después revísalo con la comprobación automática de la etapa y vuelve aquí.' },
      ],
      icono: 'pagina',
    });
  }
  const url = L.urlSitio(d.id, 'index.html');
  const anchoActual = () => L.ANCHOS_PREVIEW.find((x) => x.id === vista.ancho) || L.ANCHOS_PREVIEW[2];
  const marco = el('iframe', { sandbox: 'allow-scripts', src: url, title: `Vista previa de la página de venta de ${d.id}`, referrerpolicy: 'no-referrer' });
  const dispositivo = el('div', { class: 'u3-dispositivo' },
    el('div', { class: 'u3-dispositivo__barra', 'aria-hidden': 'true' }, el('i'), el('i'), el('i'), el('span', null, 'Vista previa local de la página de venta')),
    marco);
  const nota2 = el('span', { class: 'u3-tenue u3-peq' });
  const aplicar = () => {
    const a = anchoActual();
    dispositivo.className = `u3-dispositivo u3-dispositivo--${a.id}`;
    marco.style.height = `${Math.min(a.alto, 820)}px`;
    nota2.textContent = a.ancho ? `${a.ancho} × ${a.alto} px (se limita al ancho disponible)` : 'ancho completo';
  };
  const selectorDisp = U.segmentado({
    opciones: L.ANCHOS_PREVIEW.map((a) => ({ valor: a.id, etiqueta: a.titulo, titulo: a.ancho ? `${a.titulo} (${a.ancho} px)` : `${a.titulo} (ancho completo)` })),
    valor: vista.ancho, etiqueta: 'Tamaño del dispositivo de la vista previa',
    onCambio: (v) => { vista.ancho = v; aplicar(); },
  });
  const recargar = el('button', { type: 'button', class: 'btn btn--chico', onclick: () => { marco.removeAttribute('src'); marco.setAttribute('src', url); } }, ic('refrescar', 14), 'Recargar');
  aplicar();
  return el('section', { class: 'u3-pila', 'aria-label': 'Vista previa de la página de venta' },
    el('div', { class: 'u3-fila u3-fila--entre' },
      el('h2', { class: 'u3-titulo' }, 'Cómo se ve'),
      el('div', { class: 'u3-fila' }, selectorDisp, recargar, nota2)),
    el('div', { class: 'u3-vista-layout' },
      el('div', { class: 'u3-escenario' }, dispositivo),
      resumenSalida(d)),
    tecnico('Cómo se sirve esta vista previa',
      el('p', { class: 'u3-parrafo' }, 'Se sirve desde ', el('code', null, url), ' dentro de un iframe con sandbox="allow-scripts" (sin allow-same-origin: el sitio no puede leer el panel ni su token), con CSP y solo por GET.'),
      el('p', { class: 'u3-parrafo' }, 'Los enlaces a rutas dinámicas (como /comprar) no funcionan aquí: los atiende el servidor de la tienda. Si los estilos, imágenes o programas con ruta absoluta (/css/…, /imagenes/…) no cargan, es una limitación de esta vista local y no un defecto de la página de venta.')));
}

// ───────────────────────── pestañas ─────────────────────────

function montarTabs(d) {
  const items = [
    { id: 'comprobaciones', titulo: 'Comprobaciones', render: () => tabComprobaciones(d) },
    { id: 'coherencia', titulo: 'Precio y garantía', render: () => tabCoherencia(d) },
    { id: 'rutas', titulo: 'Legales y rutas', render: () => tabRutas(d) },
    { id: 'assets', titulo: 'Imágenes', render: () => tabAssets(d) },
    { id: 'checkout', titulo: 'Cobro', render: () => tabCheckout(d) },
    { id: 'tracking', titulo: 'Medición y consentimiento', render: () => tabTracking(d) },
    { id: 'despliegue', titulo: 'Publicación', render: () => tabDespliegue(d) },
  ];
  const activa = items.some((i) => i.id === vista.tab) ? vista.tab : 'comprobaciones';
  const tb = tabs(items, activa);
  const sincronizar = () => setTimeout(() => { const x = tb.activo && tb.activo(); if (x) vista.tab = x; }, 0);
  tb.addEventListener('click', sincronizar);
  tb.addEventListener('keydown', sincronizar);
  return tb;
}

const ESTADO_CHECK = {
  ok: { tono: 'ok', icono: 'ok', texto: 'Correcto' },
  error: { tono: 'error', icono: 'octogono', texto: 'Falla' },
  aviso: { tono: 'aviso', icono: 'alerta', texto: 'Con aviso' },
  no_aplica: { tono: 'neutro', icono: 'menos', texto: 'No aplica' },
  sin_resultado: { tono: 'neutro', icono: 'circulo', texto: 'Sin resultado' },
};

const ETIQUETA_RESUMEN = { ok: 'correctas', error: 'fallan', aviso: 'con aviso', sin_resultado: 'sin resultado', no_aplica: 'no aplican' };

/** Etiqueta de texto del estado (el icono va aparte, a la izquierda de la fila). */
function etiquetaCheck(estado) {
  const e = ESTADO_CHECK[estado] || ESTADO_CHECK.sin_resultado;
  return el('span', { class: ['u3-estado', `u3-estado--${e.tono}`] }, e.texto);
}

function filaCheck(f) {
  const detalle = f.detalle || '';
  return el('div', { class: ['u3-check', f.estado === 'error' && 'u3-check--error', f.estado === 'aviso' && 'u3-check--aviso'] },
    el('span', { class: ['u3-estado', `u3-estado--${(ESTADO_CHECK[f.estado] || ESTADO_CHECK.sin_resultado).tono}`], role: 'img', 'aria-label': (ESTADO_CHECK[f.estado] || ESTADO_CHECK.sin_resultado).texto }, ic((ESTADO_CHECK[f.estado] || ESTADO_CHECK.sin_resultado).icono, 20)),
    el('span', { class: 'u3-check__id' }, f.id),
    el('div', null, el('div', { class: 'u3-check__nombre' }, f.nombre)),
    el('div', { class: 'u3-check__lado' }, f.severidad.id !== 'otra' ? tag(f.severidad.texto, f.severidad.id === 'bloqueante' ? 'aviso' : null, { titulo: f.severidad.detalle }) : null, etiquetaCheck(f.estado)),
    el('div', { class: 'u3-check__texto' }, f.titulo),
    detalle ? el('div', { class: 'u3-check__detalle' }, detalle) : null);
}

function tabComprobaciones(d) {
  const c = d.checks;
  const cs = c.resumen;
  const grupos = L.agruparChecks(c.filas);
  const indicios = L.indiciosHtml(d.html, { dominio: d.oferta && d.oferta.marca ? d.oferta.marca.dominio : null });
  const otros = [...c.otros.map((o) => ({ id: o.id, tipo: 'check', estado: o.resultado, detalle: o.detalle, quien: o.quien })),
    ...c.otrosHallazgos.map((h) => ({ id: h.id, tipo: `hallazgo ${h.severidad}`, estado: h.abierto ? 'abierto' : 'cerrado', detalle: `${h.descripcion} (${h.estado})`, quien: h.quien }))];
  return pila(
    el('div', { class: 'u3-resumen-checks', role: 'group', 'aria-label': 'Resumen de comprobaciones' },
      [['ok', cs.ok], ['error', cs.error], ['aviso', cs.aviso], ['sin_resultado', cs.sinResultado], ['no_aplica', cs.noAplica]].map(([e, n]) => el('span', { class: ['u3-estado', `u3-estado--${ESTADO_CHECK[e].tono}`] }, ic(ESTADO_CHECK[e].icono, 18), el('b', null, String(n)), ETIQUETA_RESUMEN[e]))),
    !c.hayResultadosC ? nota(el('p', null, el('strong', null, 'Todavía no hay resultados C01–C17. '),
      d.qaD5 ? 'La revisión de calidad registró sus comprobaciones con otros códigos (más abajo, tal cual). ' : 'No existe el informe de la revisión de calidad de esta etapa. ',
      '«Sin resultado» significa que nadie lo registró; nunca equivale a «correcto». ', U.termino('checks_c', { texto: 'Qué son estas comprobaciones' }), '.'), { tono: 'aviso', icono: 'alerta' }) : null,
    el('div', { class: 'u3-grupos' }, grupos.map((g) => el('section', { 'aria-label': g.titulo },
      el('div', { class: 'u3-grupo__cab' }, el('h3', { class: 'u3-titulo u3-titulo--chico' }, g.titulo),
        el('span', { class: 'u3-tenue u3-peq' }, g.resumen.sinResultado === g.resumen.total ? `${g.resumen.total} sin resultado` : `${g.resumen.ok} de ${g.resumen.total} correctas${g.resumen.error ? ` · ${g.resumen.error} fallan` : ''}${g.resumen.sinResultado ? ` · ${g.resumen.sinResultado} sin resultado` : ''}`)),
      el('div', { class: 'u3-lista' }, g.filas.map(filaCheck))))),
    nota(el('p', null, 'Las comprobaciones de velocidad, navegadores, aviso automático de Stripe, entrega y vuelta atrás necesitan herramientas externas (Lighthouse, un navegador real y Stripe en modo de prueba): este panel no las hace, solo muestra su resultado. ', U.termino('confirmacion_pago', { texto: '¿Qué es el aviso automático de Stripe?' })), { tono: 'neutra' }),
    indicios.length ? seccion('Lo que este panel ve en la página (no reemplaza la revisión de calidad)', el('div', { class: 'u3-lista' }, indicios.map((i) => el('div', { class: 'u3-item' },
      el('span', { class: ['u3-item__icono', 'u3-estado', `u3-estado--${i.estado === 'ok' ? 'ok' : i.estado === 'error' ? 'error' : 'aviso'}`] }, ic(i.estado === 'ok' ? 'ok' : i.estado === 'error' ? 'octogono' : 'alerta', 18)),
      el('div', null, el('div', { class: 'u3-item__titulo' }, i.titulo), el('div', { class: 'u3-item__detalle', style: { gridColumn: 'auto' } }, i.detalle)),
      el('div', { class: 'u3-item__lado' }, tag(i.id, 'mono'))))),
    { ayuda: 'Lectura simple de la página principal. La comprobación completa, sobre todas las páginas, la hace un programa aparte (ver «Cómo hacerlo» más abajo).' }) : null,
    otros.length ? tecnico(`Otras comprobaciones y hallazgos de la revisión de calidad (${otros.length})`, tabla({
      etiqueta: 'Otras comprobaciones de la revisión de calidad', filas: otros, maxFilas: 30,
      columnas: [
        { clave: 'id', titulo: 'Identificador', formato: (v) => el('code', null, v) },
        { clave: 'tipo', titulo: 'Tipo' },
        { clave: 'estado', titulo: 'Estado', formato: (v) => chip(v === 'ok' ? 'ok' : v === 'fail' || v === 'error' ? 'falla' : v, v === 'ok' || v === 'cerrado' ? 'ok' : v === 'fail' || v === 'error' || v === 'abierto' ? 'error' : 'neutro') },
        { clave: 'detalle', titulo: 'Detalle', clase: 'cel-larga' },
        { clave: 'quien', titulo: 'Quién' },
      ],
    })) : null,
    comando(`.venv/bin/python -m landing.validar --oferta ${d.id} --json`, { titulo: 'Cómo hacerlo: comprobar toda la página de venta', nota: 'Revisa todas las páginas del sitio sin cambiar nada; termina con código 3 si encuentra problemas. Lo ejecutas tú en la terminal.' }),
    tecnico('Informes de donde salen los resultados', kv([
      ['Informe de la revisión de calidad', d.qaD5Ruta ? el('code', null, d.qaD5Ruta) : null], ['Informe de cumplimiento', d.qaX1Ruta ? el('code', null, d.qaX1Ruta) : null],
      ['Cómo se leen', 'campos checks_l1 y hallazgos con identificador «C01»…«C17»'],
    ])));
}

const ESTADO_FILA = {
  ok: { tono: 'ok', icono: 'ok', texto: 'Coincide' },
  error: { tono: 'error', icono: 'octogono', texto: 'Difiere' },
  aviso: { tono: 'aviso', icono: 'alerta', texto: 'Revisar' },
  sin_dato: { tono: 'neutro', icono: 'circulo', texto: 'Sin dato suficiente' },
};

function tabCoherencia(d) {
  const c = d.coherencia;
  const faltan = [];
  if (!d.oferta) faltan.push('la oferta');
  if (!d.checkout) faltan.push('la pantalla de pago');
  if (!d.sitioExiste) faltan.push('la página de venta');
  const celda = (v, fila, otras) => {
    const presentes = otras.filter((x) => x.valor !== null);
    const ref = presentes.length ? presentes[0].valor : null;
    const difiere = fila.estado === 'error' && v.valor !== null && ref !== null && v.valor !== ref;
    const clase = v.valor === null ? 'u3-sin' : difiere ? 'u3-dif' : 'u3-igual';
    return el('td', { class: clase }, v.texto, difiere ? el('span', { class: 'u3-nota-celda' }, 'no coincide con los demás') : null);
  };
  const filas = c.filas.map((f) => {
    const e = ESTADO_FILA[f.estado] || ESTADO_FILA.sin_dato;
    const vals = [f.oferta, f.checkout, f.html];
    return el('tr', null,
      el('th', { scope: 'row' }, f.campo, el('span', { class: 'u3-nota-celda' }, f.nota)),
      vals.map((v) => celda(v, f, vals)),
      el('td', null, el('span', { class: ['u3-estado', `u3-estado--${e.tono}`] }, ic(e.icono, 18), e.texto)));
  });
  return pila(
    faltan.length ? nota(el('p', null, el('strong', null, 'Comparación incompleta: '), `no se pudo leer ${faltan.join(', ')}. Una sola fuente no es una comparación: queda «sin dato suficiente».`), { tono: 'aviso', icono: 'alerta' }) : null,
    el('p', { class: 'u3-parrafo' }, 'El precio, la moneda, la garantía, la oferta extra al pagar y el idioma deben ser idénticos en la oferta, la pantalla de pago y la página de venta. ', U.termino('coherencia_c02', { texto: 'Qué se comprueba' }), '.'),
    el('div', { class: 'u3-tabla-envuelta' }, el('table', { class: 'u3-tabla', 'aria-label': 'Coherencia entre la oferta, la pantalla de pago y la página de venta' },
      el('thead', null, el('tr', null, ['Campo', 'Oferta', 'Pantalla de pago', 'Página de venta', 'Resultado'].map((h) => el('th', { scope: 'col' }, h)))),
      el('tbody', null, filas))),
    tecnico('De dónde sale cada columna', kv([
      ['Oferta', el('code', null, 'ofertas/<id>/03-oferta/oferta.json')], ['Pantalla de pago', el('code', null, 'ofertas/<id>/05-landing/checkout.json')],
      ['Página de venta', el('span', null, 'atributos data-precio-minor, data-moneda y data-garantia-dias del <body> y los importes escritos en el texto de ', el('code', null, 'sitio/index.html'))],
      ['Dinero', 'se compara en unidad menor entera (céntimos), sin decimales flotantes'],
      ['Programa de comprobación completa', el('span', null, el('code', null, 'landing.validar'), ' (reglas L1-PRECIO, L1-MONEDA y L1-GARANTIA)')],
    ])),
    el('p', { class: 'u3-tenue u3-peq' }, 'La comprobación completa, sobre todas las páginas, la hace un programa aparte. La compra de prueba y el total de la sesión de Stripe los comprueba la revisión de calidad, no el panel.'));
}

// ───────────────────────── rutas y legales (sondeo HTTP) ─────────────────────────

async function sondear(id, archivos) {
  const res = {};
  const cola = [...archivos];
  const trabajador = async () => {
    while (cola.length) {
      const a = cola.shift();
      const url = L.urlSitio(id, a);
      if (!url) { res[a] = 'error'; continue; }
      try {
        const r = await fetch(url, { method: 'GET', cache: 'no-store', credentials: 'omit', headers: { Accept: 'text/html' } });
        res[a] = r.status;
        try { if (r.body && r.body.cancel) await r.body.cancel(); } catch (_) { /* ya consumido */ }
      } catch (_) { res[a] = 'error'; }
    }
  };
  await Promise.all(Array.from({ length: 4 }, trabajador));
  return res;
}

const NOMBRE_LEGAL = { vendedor: 'Datos del vendedor', terminos: 'Términos de venta', privacidad: 'Política de privacidad', reembolsos: 'Reembolsos', cookies: 'Cookies', aviso: 'Aviso legal', entrega: 'Entrega del producto' };

async function tabRutas(d) {
  if (!d.rutas) {
    return U.vacioConPasos({
      titulo: 'Esta oferta aún no tiene mapa de rutas',
      explicacion: 'El mapa de rutas dice qué dirección web lleva a cada página de la página de venta (incluido cada ángulo de venta). Lo escribe la etapa de la página de venta junto al sitio. Sin él no se pueden comprobar las siete páginas legales.',
      pasos: [{ texto: 'Genera el sitio, que incluye el mapa de rutas.', comando: `.venv/bin/python -m landing.generar --oferta ${d.id} --json` }], icono: 'lista',
    });
  }
  const archivos = L.archivosASondear(d.rutas);
  const sondas = d.sitioExiste ? await sondear(d.id, archivos) : {};
  const m = L.modeloRutas({ rutas: d.rutas, sondas, artefactos: d.etapa ? d.etapa.artefactos : null });
  const estadoLegal = (l) => (l.estado === 'ok' ? { tono: 'ok', icono: 'ok', texto: 'Responde bien (200)' } : l.estado === 'sin_comprobar' ? { tono: 'neutro', icono: 'circulo', texto: 'Sin comprobar' } : { tono: 'error', icono: 'octogono', texto: l.texto === 'falta la ruta en el mapa de rutas' ? 'Falta en el mapa' : /^HTTP \d+$/.test(l.texto) ? `No responde bien (código ${l.texto.slice(5)})` : l.texto });
  return pila(
    !d.sitioExiste ? nota(el('p', null, 'No hay sitio que comprobar: los estados salen solo del mapa de rutas y de los archivos de la etapa.'), { tono: 'neutra' }) : null,
    seccion(`Siete páginas legales obligatorias (${m.resumen.legalesOk} de ${m.resumen.legalesTotal} responden)`, el('div', { class: 'u3-legales' }, m.legales.map((l) => {
      const e = estadoLegal(l);
      return el('div', { class: 'u3-legal' }, el('b', null, NOMBRE_LEGAL[l.id] || l.id), el('span', { class: ['u3-estado', `u3-estado--${e.tono}`] }, ic(e.icono, 16), e.texto));
    })), { ayuda: 'Son plantillas generadas, sin revisión de un abogado (decisión del dueño). El panel pide cada página al sitio local (solo para leerla) y muestra el código de respuesta que recibe.' }),
    tecnico(`Mapa de rutas (${m.filas.length})`, tabla({
      etiqueta: 'Rutas de la página de venta', filas: m.filas, maxFilas: 40,
      columnas: [
        { clave: 'ruta', titulo: 'Ruta', formato: (v) => el('code', null, v) },
        { clave: 'destino', titulo: 'Destino', clase: 'cel-larga' },
        { clave: 'archivo', titulo: 'Archivo en sitio/', formato: (v) => (v ? el('code', null, v) : el('span', { class: 'u3-tenue' }, '—')) },
        { clave: 'estado', titulo: 'HTTP', orden: (r) => r.estado, formato: (v, r) => chip(r.texto, v === 'ok' ? 'ok' : v === 'error' ? 'error' : 'neutro') },
      ],
      claseFila: (r) => (r.estado === 'error' ? 'fila-error' : null),
    })));
}

// ───────────────────────── imágenes, cobro, medición, despliegue ─────────────────────────

function tabAssets(d) {
  const m = d.modeloAssets;
  if (!m.existe) {
    return U.vacioConPasos({
      titulo: 'Esta oferta aún no tiene ranuras de imagen',
      explicacion: 'Las ranuras declaran qué imágenes lleva la página de venta (portada, galería, regalos extra, compra, redes). Ninguna imagen puede ir sin una ranura aprobada.',
      pasos: [{ texto: 'Las declara la etapa de la página de venta al generar el sitio.' }], icono: 'caja',
    });
  }
  const r = m.resumen;
  const pct = r.declaradas ? Math.round((r.aprobadas / r.declaradas) * 100) : 0;
  const pendientes = m.slots.filter((s) => s.pendiente);
  return pila(
    el('div', { class: 'u3-metricas' },
      U.metrica({ etiqueta: 'Ranuras aprobadas', valor: `${r.aprobadas} / ${r.declaradas}`, contexto: r.pendientes ? `${r.pendientes} pendientes` : 'todas aprobadas', tono: r.pendientes ? 'aviso' : 'ok', ayuda: 'ranura_asset' }),
      U.metrica({ etiqueta: 'Marcadores de ejemplo', valor: String(r.placeholders), contexto: 'nunca pueden ir a la tienda real', tono: r.placeholders ? 'aviso' : 'ok' }),
      U.metrica({ etiqueta: 'Generadas con IA', valor: String(r.ia), contexto: 'se avisa que son de IA, según la política' })),
    el('div', { class: ['u3-barra', pct === 100 && 'u3-barra--supera'], style: { '--p': `${pct}%` } },
      el('div', { class: 'u3-barra__cab' }, el('span', null, 'Progreso de imágenes aprobadas'), el('span', { class: 'u3-barra__valor' }, `${pct} %`)),
      el('div', { class: 'u3-barra__pista', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': pct, 'aria-label': 'Progreso de imágenes aprobadas' }, el('div', { class: 'u3-barra__relleno' }))),
    pendientes.length ? seccion(`Ranuras pendientes (${pendientes.length})`, el('div', { class: 'u3-ranuras' }, pendientes.map((s) => el('div', { class: 'u3-ranura' },
      el('b', null, s.proposito || s.id),
      el('div', { class: 'u3-tags' }, tag(s.estado === 'asignado' ? 'asignada, sin aprobar' : s.estado === 'vacio' ? 'vacía' : 'estado desconocido', s.estado === 'desconocido' ? 'error' : 'aviso'), s.placeholder ? tag('marcador de ejemplo', 'aviso') : null, tag(`${s.seccion} · ${s.tipo}`, null)),
      el('span', { class: 'u3-tenue u3-peq' }, `${s.ratio ? `proporción ${s.ratio}` : ''}${s.pesoMaxKb !== null ? ` · máx. ${s.pesoMaxKb} KB` : ''}`)))), { ayuda: 'Una ranura sin aprobar no puede mostrarse en la tienda real.' })
      : nota(el('p', null, 'Todas las ranuras están aprobadas.'), { tono: 'ok', icono: 'ok' }),
    tecnico(`Todas las ranuras (${m.slots.length})`, tabla({
      etiqueta: 'Ranuras de la página de venta', filas: m.slots, maxFilas: 40,
      columnas: [
        { clave: 'id', titulo: 'Ranura', formato: (v) => el('code', null, v) },
        { clave: 'seccion', titulo: 'Sección · tipo', formato: (v, r2) => `${v} · ${r2.tipo}` },
        { clave: 'ratio', titulo: 'Proporción' },
        { clave: 'estado', titulo: 'Estado', formato: (v) => chip(v === 'aprobado' ? 'aprobada' : v === 'asignado' ? 'asignada, sin aprobar' : v === 'vacio' ? 'vacía' : 'desconocido', v === 'aprobado' ? 'ok' : v === 'desconocido' ? 'error' : 'aviso') },
        { clave: 'archivo', titulo: 'Archivo', formato: (v) => (v ? el('code', null, v) : el('span', { class: 'u3-tenue' }, 'sin archivo')) },
        { clave: 'origen', titulo: 'Origen', formato: (v, r2) => (r2.placeholder ? chip('marcador de ejemplo', 'aviso') : (v || '—')) },
        { clave: 'pesoMaxKb', titulo: 'Peso máx.', alinear: 'der', formato: (v) => (v === null ? '—' : `${v} KB`) },
        { clave: 'proposito', titulo: 'Propósito', clase: 'cel-larga' },
      ],
      claseFila: (r2) => (r2.pendiente ? 'fila-aviso' : null),
    })));
}

function tabCheckout(d) {
  const m = d.modeloCheckout;
  if (!m) {
    return U.vacioConPasos({
      titulo: 'Esta oferta aún no tiene pantalla de pago configurada',
      explicacion: 'La pantalla de pago (precio, precio en Stripe, oferta extra al pagar, métodos de pago, garantía y consentimientos) la configura la etapa de la página de venta.',
      pasos: [{ texto: 'Lo prepara la IA de la etapa; aquí aparecerá en cuanto exista.' }], icono: 'dinero',
    });
  }
  return pila(
    el('div', { class: 'u3-metricas' },
      U.metrica({ etiqueta: 'Precio de lista', valor: m.precio, contexto: m.impuestos ? `impuestos: modo ${m.impuestos.modo}${m.impuestos.pais ? ` · ${m.impuestos.pais}` : ''}` : undefined }),
      U.metrica({ etiqueta: 'Garantía', valor: m.garantia === null ? '—' : `${m.garantia} días`, contexto: 'devolución del dinero' }),
      U.metrica({ etiqueta: 'Oferta extra al pagar', valor: m.bump ? m.bump.precio : 'Sin oferta extra', contexto: m.bump ? 'la casilla nunca viene marcada de antemano' : 'la oferta no la incluye', ayuda: 'oferta_extra_pago' }),
      U.metrica({ etiqueta: 'Precio real en Stripe', valor: m.priceLive ? 'Creado' : 'Pendiente', contexto: m.priceLive ? 'listo para publicar' : 'se crea al publicar, con tu firma; no se inventa', tono: m.priceLive ? 'ok' : 'aviso', ayuda: 'price_live' })),
    el('div', { class: 'u3-dos' },
      seccion('Cómo se cobra', kv([
        ['Métodos de pago', m.metodos.length ? el('span', { class: 'u3-tags' }, m.metodos.map((x) => tag(x, null))) : null],
        [U.termino('oferta_post_pago', { texto: 'Oferta después de pagar' }), m.upsell ? m.upsell.precio : 'ninguna en la primera versión'],
        ['Texto de la oferta extra al pagar', m.bump ? m.bump.copy : null],
        ['Nombre en el extracto', m.descriptor],
        ['Tipo de pantalla de pago', m.uiMode], ['La sesión de pago se crea en el servidor', m.sesionEnServidor ? tag('sí', 'ok', { icono: 'ok' }) : tag('no', 'error', { icono: 'octogono' })],
        ['Caduca a los', m.expiraMin === null ? null : `${m.expiraMin} min`],
      ])),
      seccion('Consentimientos del comprador', m.consentimientos.length ? el('div', { class: 'u3-lista' }, m.consentimientos.map((c) => el('div', { class: 'u3-item', style: { gridTemplateColumns: 'minmax(0, 1fr) auto' } }, el('span', null, c.id.replace(/[_-]/g, ' ')), el('span', { class: 'u3-tags' }, tag(`versión ${c.version}`, null), c.obligatorio ? tag('obligatorio', 'info') : null)))) : el('p', { class: 'u3-tenue' }, 'Sin consentimientos declarados.'))),
    tecnico('Detalle técnico de la pantalla de pago', kv([
      [U.termino('precio_stripe', { texto: 'Price de Stripe (prueba)' }), m.priceTest ? el('code', null, m.priceTest) : null],
      ['Price de Stripe (live)', m.priceLive ? el('code', null, m.priceLive) : tag('pendiente', 'aviso')],
      ['Price de la oferta extra', m.bump && m.bump.priceId ? el('code', null, m.bump.priceId) : null],
      ['Modo de la oferta extra', m.bump && m.bump.modo ? el('code', null, m.bump.modo) : null],
      ['Comportamiento de impuestos', m.impuestos ? el('code', null, m.impuestos.tax_behavior) : null],
      ['URL de éxito', m.successUrl ? el('code', null, m.successUrl) : null], ['URL de retorno', m.returnUrl ? el('code', null, m.returnUrl) : null],
      ['Metadata de la sesión', m.metadata.length ? el('span', { class: 'u3-tags' }, m.metadata.map((x) => el('code', null, x))) : null],
      ['Versión / formato esperado', `${t(m.version)} · formato ${t(m.schema)}`],
      ['Archivo', el('code', null, `ofertas/${d.id}/05-landing/checkout.json`)],
    ])));
}

function tabTracking(d) {
  const m = d.modeloTracking;
  if (!m) {
    return U.vacioConPasos({
      titulo: 'Esta oferta aún no tiene plan de medición',
      explicacion: 'El plan define el medidor de Meta (píxel y dataset), los eventos con su identificador, el consentimiento y los datos sensibles que están prohibidos.',
      pasos: [{ texto: 'Lo escribe la etapa de la página de venta; aquí aparecerá en cuanto exista.' }], icono: 'pulso',
    });
  }
  const problemas = L.problemasTracking(m);
  const fila = (ok, tonoNo, titulo, detalle) => el('div', { class: 'u3-item' },
    el('span', { class: ['u3-item__icono', 'u3-estado', `u3-estado--${ok ? 'ok' : tonoNo}`] }, ic(ok ? 'ok' : tonoNo === 'error' ? 'octogono' : 'alerta', 18)),
    el('div', null, el('div', { class: 'u3-item__titulo' }, titulo), el('div', { class: 'u3-item__detalle', style: { gridColumn: 'auto' } }, detalle)));
  return pila(
    problemas.length ? nota(el('p', null, el('strong', null, 'A revisar: '), problemas.join(' ')), { tono: 'error', icono: 'octogono' }) : null,
    el('div', { class: 'u3-dos' },
      seccion('Consentimiento y datos', el('div', { class: 'u3-lista' },
        fila(m.consentimiento.ok, 'error', 'Aviso de cookies propio', m.consentimiento.plataforma ? `Plataforma: ${m.consentimiento.plataforma}.` : 'Sin plataforma de consentimiento declarada.'),
        fila(m.consentimiento.requeridoUeUk, 'aviso', 'Obligatorio en la Unión Europea y el Reino Unido', m.consentimiento.requeridoUeUk ? 'Nada se envía a Meta antes de que la persona acepte.' : 'No se exige el consentimiento previo en la Unión Europea ni el Reino Unido.'),
        fila(!m.datosSensiblesPermitidos, 'error', 'Datos sensibles prohibidos', m.datosSensiblesPermitidos ? 'El plan los permite: debe prohibirlos.' : `${m.camposProhibidos.length} campos prohibidos en los eventos.`),
        fila(!m.modoPrueba, 'aviso', m.modoPrueba ? 'Modo prueba activo' : 'Modo prueba apagado', m.modoPrueba ? 'Los eventos no llegan al dataset real de Meta.' : 'Los eventos llegan al dataset real de Meta.')),
      { ayuda: 'Las visitas sin consentimiento ' + (m.consentimiento.toleraSinConsentimiento ? 'se toleran (Stripe es la fuente de verdad de las ventas).' : 'no se toleran.') }),
      seccion('Qué se mide', pila(
        el('div', { class: 'u3-tags' }, m.eventos.map((e) => tag(e.nombre, e.enListaCerrada ? 'info' : 'error', { icono: e.enListaCerrada ? null : 'octogono', titulo: e.enListaCerrada ? `Canal ${e.canal}` : 'Fuera de la lista permitida' }))),
        el('p', { class: 'u3-tenue u3-peq' }, 'Eventos permitidos: PageView (visita), ViewContent (ver la oferta), InitiateCheckout (empezar a pagar) y Purchase (compra). El mismo identificador viaja por el navegador y por el servidor para no contar dos veces; ', U.termino('event_id', { texto: 'qué es el identificador de evento' }), '. La compra solo se avisa desde el servidor, cuando Stripe la confirma y la persona dio su consentimiento.'),
        el('p', { class: 'u3-tenue u3-peq' }, U.termino('consentimiento', { texto: 'Qué es el consentimiento previo' }))), { ayuda: 'medidor_meta' })),
    tecnico('Detalle técnico de la medición', pila(
      kv([
        [U.termino('medidor_meta', { texto: 'Medidor de Meta (píxel / dataset)' }), m.pixelId ? el('code', null, `${m.pixelId} / ${t(m.datasetId)}`) : null],
        ['Dominio verificado', m.dominio], [U.termino('emq_calidad', { texto: 'Calidad de coincidencia (EMQ) objetivo' }), m.emq],
        ['Campos prohibidos', m.camposProhibidos.length ? el('span', { class: 'u3-tags' }, m.camposProhibidos.map((x) => el('code', null, x))) : null],
        [U.termino('etiqueta_utm', { texto: 'Plantilla de la etiqueta del anuncio (UTM)' }), m.utm.plantilla ? el('code', null, m.utm.plantilla) : null],
        ['Etiquetas del anuncio obligatorias (UTM)', m.utm.obligatorios.length ? el('span', { class: 'u3-tags' }, m.utm.obligatorios.map((x) => el('code', null, x))) : null],
        ['Guardadas en la pantalla de pago', m.utm.faltanEnMetadata === null ? 'sin pantalla de pago: no se compara' : m.utm.faltanEnMetadata.length ? tag(`faltan ${m.utm.faltanEnMetadata.join(', ')}`, 'error') : tag('todos', 'ok', { icono: 'ok' })],
      ]),
      tabla({
        etiqueta: 'Eventos de medición', filas: m.eventos, maxFilas: 20,
        columnas: [
          { clave: 'nombre', titulo: 'Evento', formato: (v, r) => el('span', null, v, r.enListaCerrada ? null : el('span', null, ' ', chip('fuera de la lista', 'error'))) },
          { clave: 'canal', titulo: 'Canal' },
          { clave: 'eventId', titulo: 'Regla del identificador', formato: (v) => el('code', null, v) },
          { clave: 'parametros', titulo: 'Parámetros permitidos', clase: 'cel-larga', formato: (v) => v.join(', ') || '—' },
        ],
      }))));
}

function tabDespliegue(d) {
  const m = L.modeloDespliegue(d.despliegue);
  if (!m) {
    return U.vacioConPasos({
      titulo: 'Esta oferta todavía no se publicó',
      explicacion: 'La publicación la hace un programa aparte, que puede subir la página a una vista previa o a la tienda real. Por defecto solo hace un simulacro; para la tienda real exige el visto bueno firmado de cumplimiento. Este panel no publica.',
      pasos: [{ texto: 'Haz un simulacro de publicación en la vista previa (no publica de verdad).', comando: `.venv/bin/python -m landing.desplegar --oferta ${d.id} --entorno preview --json` }], icono: 'servidor',
    });
  }
  return pila(kv(m.kv), m.lighthouse.length ? seccion('Velocidad en el celular (Lighthouse)', kv(m.lighthouse)) : null);
}

// ───────────────────────── fuentes ─────────────────────────

function pieDeFuentes(d) {
  const L2 = d.lecturas;
  const fuentes = [];
  let generado = null;
  for (const l of [d.det, L2.ofe, L2.chk, L2.ast, L2.trk, L2.rts, L2.dep, L2.idx, L2.qaD5, L2.qaX1]) {
    if (!l) continue;
    for (const f of l.fuente || []) if (!fuentes.includes(f)) fuentes.push(f);
    if (l.generado_en && (!generado || l.generado_en > generado)) generado = l.generado_en;
  }
  if (!fuentes.length) fuentes.push(`ofertas/${d.id}/05-landing/`);
  return U.fuente(fuentes.slice(0, 12), { leido: generado || undefined });
}
