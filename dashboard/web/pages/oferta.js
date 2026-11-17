// pages/oferta.js — #/oferta/<id>: la pantalla central para ARMAR una oferta a mano y verla en vivo (CONTRATO §2, §5, §6).
// Cabecera con mercado y estado · tarjeta dominante «Próximo paso» (con panel lateral para firmar) · pipeline humano con ui.pasos ·
// panel de la etapa elegida con pestañas: Resumen · Entradas y salidas · Artefactos (visor y diferencias) · Revisión (QA) · Historial · Notas de pulido.
// Lo técnico (hashes, rutas, comandos, JSON crudo) va en detalle técnico. Todo texto de datos entra por textContent (ui.el); nunca HTML en línea.
// El panel NO firma, no publica, no activa ni gasta: solo enseña el comando que corre una persona en su terminal.
// Única dirección externa que se vuelve enlace: la landing ORIGINAL del referente (registrada o de D2), https validada, con clic explícito.

import { ui, el, icono, fmt, limpiar, copiar, toast } from '../ui.js';
import * as V from '../lib/oferta.js';
import * as P from '../lib/pulido.js';
import * as W from '../lib/vistas-ofertas.js';

export const meta = { ruta: 'oferta', titulo: 'Oferta', grupo: 'Testeo y escala', icono: 'caja', escucha: ['oferta', 'registro', 'empresa'] };

// ───────────────────────── estado de la pantalla (sobrevive a los re-render del router) ─────────────────────────

const S = { oferta: null, etapa: null, tab: 'resumen', verRuta: null, cmp: null, toda: false };
const cacheArchivos = new Map();
let ultimaFirma = null;
let recargaPendiente = false;

function reiniciarEstado(id) {
  S.oferta = id; S.etapa = null; S.tab = 'resumen'; S.verRuta = null; S.cmp = null; S.toda = false;
  cacheArchivos.clear(); ultimaFirma = null;
}

/** Firma barata del estado de una oferta: cambia si cambia el estado, un gate, un artefacto o un informe. */
export function firmaDeOferta(datos) {
  const d = datos && typeof datos === 'object' ? datos : {};
  const est = d.estado || {};
  const etapas = Array.isArray(d.etapas) ? d.etapas : [];
  return JSON.stringify([
    est.revision ?? null, est.actualizado_en ?? null,
    etapas.map((e) => [e && e.id, e && e.estado, e && e.gate_pendiente, e && Array.isArray(e.artefactos) ? e.artefactos.map((a) => `${a.ruta}:${a.mtime}:${a.bytes}`).join(',') : '', e && Array.isArray(e.qa) ? e.qa.length : 0]),
  ]);
}

async function leerArchivo(ctx, ofertaId, ruta, huella = '') {
  const k = `${ofertaId}|${ruta}|${huella}`;
  if (cacheArchivos.has(k)) return cacheArchivos.get(k);
  const r = await ctx.api.sobre(`/oferta/${encodeURIComponent(ofertaId)}/archivo`, { ruta });
  const dato = r.datos && typeof r.datos === 'object' ? r.datos : null;
  if (!dato) throw new Error('El servidor no devolvió el archivo.');
  cacheArchivos.set(k, dato);
  while (cacheArchivos.size > 60) cacheArchivos.delete(cacheArchivos.keys().next().value);
  return dato;
}

const huellaDe = (a) => `${a.mtime ?? ''}:${a.bytes ?? ''}`;
const esperando = (texto = 'Cargando…') => (ui.esqueleto ? el('div', { role: 'status', 'aria-live': 'polite' }, ui.esqueleto('texto', 3), el('span', { class: 'u2-sr' }, texto)) : ui.cargando(texto));

// ───────────────────────── render ─────────────────────────

export async function render(ctx) {
  W.estilos();
  const id = ctx.params.id || ctx.estado.ofertaActiva || null;
  if (!id) return paginaSinOferta(ctx);
  if (S.oferta !== id) reiniciarEstado(id);
  W.cerrarPanelLateral();

  const enc = encodeURIComponent(id);
  let sobre;
  try { sobre = await ctx.api.sobre(`/oferta/${enc}`); } catch (err) {
    return el('div', { class: 'pagina' },
      ui.encabezadoPagina({ titulo: `Oferta ${id}`, descripcion: 'No se pudo leer el estado de esta oferta.', migas: [{ texto: 'Ofertas', ruta: '#/ofertas' }, { texto: id }] }),
      ui.errorBox(err, { reintentar: () => ctx.recargar() }));
  }
  const datos = sobre.datos && typeof sobre.datos === 'object' ? sobre.datos : {};
  // El registro identifica la oferta por su oferta_id (en la demo la carpeta es «_ejemplo» y el id es OF-…).
  const idRegistro = (datos.estado && datos.estado.oferta_id) || id;
  const tieneOfertaJson = Array.isArray(datos.etapas) && (datos.etapas.find((e) => e && e.id === 'D3') || { artefactos: [] }).artefactos.some((a) => a && a.ruta === '03-oferta/oferta.json');
  const [rReg, rPul, rNom] = await Promise.allSettled([
    ctx.api.sobre('/registro', { oferta: idRegistro, limite: 200 }),
    ctx.api.sobre('/pulido'),
    tieneOfertaJson ? leerArchivo(ctx, id, '03-oferta/oferta.json') : Promise.reject(new Error('sin oferta.json')),
  ]);
  ultimaFirma = firmaDeOferta(datos);

  const vistas = V.construirPipeline(datos.etapas);
  const resumen = V.resumenPipeline(vistas);
  let nombreComercial = null;
  if (rNom.status === 'fulfilled') {
    try { const o = JSON.parse(rNom.value.contenido); nombreComercial = o && o.promesa && typeof o.promesa.titulo === 'string' ? o.promesa.titulo : (o && typeof o.marca === 'string' ? o.marca : null); } catch (_) { nombreComercial = null; }
  }
  const D = {
    id, ctx, sobre, datos, vistas, resumen, enc,
    estadoJson: datos.estado || {},
    idCmd: (datos.estado && datos.estado.oferta_id) || id, // el motor identifica la oferta por su oferta_id
    motorDisponible: datos.proximo_paso && typeof datos.proximo_paso.motor_disponible === 'boolean' ? datos.proximo_paso.motor_disponible : (typeof datos.motor_disponible === 'boolean' ? datos.motor_disponible : null),
    cab: V.cabeceraOferta(datos.estado),
    mercado: V.fichaMercado(datos),
    titulo: V.tituloDeOferta({ titulo: nombreComercial, brief: datos.brief, estado: datos.estado, id }),
    tieneNombreComercial: Boolean(nombreComercial),
    registro: rReg.status === 'fulfilled' ? rReg.value : null,
    registroError: rReg.status === 'rejected' ? rReg.reason : null,
    pulido: rPul.status === 'fulfilled' ? { sobre: rPul.value, entradas: P.normalizarEntradas(rPul.value.datos) } : { sobre: null, entradas: [], error: rPul.reason },
    ofertasConocidas: (ctx.estado.ofertas || []).map((o) => o && o.oferta_id).filter(Boolean),
    demo: Boolean((ctx.estado.ofertas || []).find((o) => o && o.oferta_id === id && o.demo)) || Boolean(sobre.demo),
  };
  D.proximo = V.proximoPasoHumano(D.idCmd, vistas, resumen, datos.proximo_paso);

  // etapa elegida: ?etapa= del hash > la última elegida en esta oferta > la etapa actual del pipeline
  const valida = (e) => typeof e === 'string' && vistas.some((v) => v.id === e);
  const pestanas = ['resumen', 'io', 'artefactos', 'revision', 'historial', 'notas'];
  S.etapa = [ctx.params.etapa, S.etapa, resumen.etapaActual, 'D1'].find(valida);
  if (pestanas.includes(ctx.params.pestana)) S.tab = ctx.params.pestana;

  const panelHost = el('div');
  const pipelineHost = el('div');
  D.panelHost = panelHost;
  D.pintarPipeline = () => { limpiar(pipelineHost); pipelineHost.appendChild(construirPipeline(D)); };
  D.pintarPanel = () => { limpiar(panelHost); panelHost.appendChild(construirPanel(D)); };
  D.elegir = (etapa, { pestana = null, enfocar = false } = {}) => {
    if (!valida(etapa)) return;
    const cambia = etapa !== S.etapa;
    S.etapa = etapa; if (cambia) { S.verRuta = null; S.cmp = null; }
    if (pestana && pestanas.includes(pestana)) S.tab = pestana; else if (cambia) S.tab = 'resumen';
    try { history.replaceState(null, '', `#/oferta/${enc}?etapa=${encodeURIComponent(etapa)}`); } catch (_) { /* sin history */ }
    D.pintarPipeline(); D.pintarPanel();
    if (enfocar) { const h = panelHost.querySelector('.u2-etapa'); if (h && h.scrollIntoView) h.scrollIntoView({ block: 'start', behavior: 'smooth' }); }
  };
  D.refrescarPulido = async () => {
    try {
      const r = await ctx.api.sobre('/pulido');
      D.pulido = { sobre: r, entradas: P.normalizarEntradas(r.datos) };
    } catch (err) { toast(`No se pudo releer la bitácora: ${err.mensaje || err.message}`, 'error'); }
    D.pintarPanel();
  };
  D.cambiarEstadoPulido = async (idEntrada, estado) => {
    try {
      await ctx.api.post('/pulido', P.cuerpoCambioEstado(idEntrada, estado));
      toast(`Nota marcada como ${P.TITULO_ESTADO[estado].toLowerCase()}.`, 'ok');
    } catch (err) { toast(`No se pudo cambiar el estado: ${err.mensaje || err.message}`, 'error'); return; }
    await D.refrescarPulido();
  };
  D.anotar = (etapa) => W.abrirFormularioObservacion(ctx, { oferta_id: id, etapa, ofertas: [...new Set([id, ...D.ofertasConocidas])], alGuardar: () => D.refrescarPulido() });
  D.abrirFirma = (etapa) => abrirPanelFirma(D, etapa);
  D.quitarPanelDeLaRuta = () => { try { if (/[?&]panel=/.test(location.hash)) history.replaceState(null, '', `#/oferta/${enc}?etapa=${encodeURIComponent(S.etapa)}`); } catch (_) { /* sin history */ } };
  D.abrirEjecucion = (etapa) => abrirPanelEjecucion(D, etapa);
  D.accion = (a) => {
    if (!a) return;
    if (a.modo === 'firmar') D.abrirFirma(a.etapa || D.proximo.etapa);
    else if (a.modo === 'ejecutar') D.abrirEjecucion(a.etapa || D.proximo.etapa);
    else if (a.modo === 'etapa') D.elegir(a.etapa, { pestana: a.pestana || 'resumen', enfocar: true });
  };

  D.pintarPipeline();
  D.pintarPanel();
  ctx.alSalir(() => W.cerrarPanelLateral());

  const pagina = el('div', { class: 'pagina u2-oferta' },
    cabeceraPagina(D),
    fichaOferta(D),
    tarjetaLandingOriginal(D),
    tarjetaProximoPaso(D),
    metricas(D),
    el('section', { class: 'u2-bloque u2-pipeline', 'aria-labelledby': 'u2-pipeline-t' },
      el('div', { class: 'u2-bloque__cab' },
        el('h2', { id: 'u2-pipeline-t' }, 'Etapas de la oferta ', ui.ayuda ? ui.ayuda('pipeline_oferta') : null),
        el('span', { class: 'u2-nota' }, 'Elige una etapa para ver su detalle.')),
      pipelineHost),
    panelHost,
    fichaCompleta(D));
  // si llega ?panel=firmar (desde «Requiere tu atención»), se abre el panel con el comando
  if (ctx.params.panel === 'firmar' && D.proximo.etapa) setTimeout(() => D.abrirFirma(ctx.params.etapa || D.proximo.etapa), 0);
  return pagina;
}

/** alCambio: el router re-renderiza (con su guardia de edición) solo si el evento toca ESTA oferta. Con el panel lateral abierto espera a que se cierre. */
export async function alCambio(ctx, evento) {
  const id = ctx.params.id || ctx.estado.ofertaActiva;
  if (!id) return undefined;
  const lote = Array.isArray(evento && evento.lote) && evento.lote.length ? evento.lote : [evento];
  const recargar = () => { if (W.hayPanelLateral()) { recargaPendiente = true; return; } ctx.recargar(); };
  const toca = lote.some((e) => {
    if (!e || e.tipo === 'sondeo') return false;
    const ruta = String(e.ruta || '');
    if (e.tipo === 'oferta') return ruta === '' || ruta.includes(id);
    if (e.tipo === 'registro') return true;
    if (e.tipo === 'empresa') return ruta.includes('pulido');
    return false;
  });
  if (toca) { recargar(); return undefined; }
  if (lote.some((e) => e && e.tipo === 'sondeo')) {
    // Sin SSE no hay detalle del cambio: se compara una firma barata del estado cada 5 s.
    try {
      const r = await ctx.api.get(`/oferta/${encodeURIComponent(id)}`);
      if (firmaDeOferta(r) !== ultimaFirma) recargar();
    } catch (_) { /* sin conexión: el indicador EN VIVO ya lo muestra */ }
  }
  return undefined;
}

function paginaSinOferta(ctx) {
  const ofs = ctx.estado.ofertas || [];
  return el('div', { class: 'pagina' },
    ui.encabezadoPagina({ titulo: 'Oferta', descripcion: 'Elige una oferta para armarla etapa por etapa.', migas: [{ texto: 'Ofertas', ruta: '#/ofertas' }, { texto: 'Elegir' }] }),
    ofs.length
      ? el('div', { class: 'u2-bloque' }, el('ul', { class: 'u2-lista' }, ofs.map((o) => el('li', null,
        el('a', { class: 'enlace u2-lista__texto', href: `#/oferta/${encodeURIComponent(o.oferta_id)}` }, o.oferta_id), o.demo ? W.tag('Demostración', 'info') : null, W.tagFase(o.fase)))))
      : ui.vacioConPasos({
        titulo: 'Todavía no hay ofertas', explicacion: 'Una oferta nace de una ficha inicial (el «brief») que tú firmas; después el sistema crea la oferta y esta pantalla se llena sola.', icono: 'caja',
        pasos: [{ texto: 'Escribe la ficha inicial de la oferta (idioma, países, precio y presupuesto de prueba).' }, { texto: 'Crea la oferta a partir de esa ficha con este comando:', comando: '.venv/bin/python -m engine.orq crear --brief RUTA_AL_BRIEF' }],
      }));
}

// ───────────────────────── cabecera ─────────────────────────

function cabeceraPagina(D) {
  const acciones = [
    ui.fuente ? ui.fuente(D.sobre.fuente, { leido: D.sobre.generado_en }) : null,
    el('button', { type: 'button', class: 'btn btn--primario', onclick: () => D.anotar(S.etapa) }, icono('lapiz', { tam: 14 }), 'Anotar observación'),
  ].filter(Boolean);
  return ui.encabezadoPagina({
    titulo: D.titulo,
    descripcion: D.tieneNombreComercial && D.cab.ofertaId ? `Oferta ${D.cab.ofertaId}: arma cada etapa, mira qué espera de ti y sigue el avance en vivo.` : 'Arma la oferta etapa por etapa, mira qué espera de ti y sigue el avance en vivo.',
    migas: [{ texto: 'Ofertas', ruta: '#/ofertas' }, { texto: D.titulo }],
    acciones,
  });
}

function fichaOferta(D) {
  const { cab, mercado: m } = D;
  const gates = D.resumen.gatesPendientes;
  const mercadoTxt = m.idioma ? [m.idioma, m.paises.length ? ` · ${m.paises.join(', ')}` : ''] : null;
  return el('div', { class: 'u2-ficha' },
    W.par('Fase', el('span', { class: 'u2-fila' }, W.tagFase(cab.fase), ui.ayuda ? ui.ayuda('fase_oferta') : null, cab.pausa ? W.tag('En pausa', 'error', { icono: 'pausa' }) : null)),
    W.par('Mercado', mercadoTxt
      ? el('span', { class: 'u2-fila' }, mercadoTxt, m.esHipotesis ? (ui.termino ? ui.termino('decision_mercado', { texto: 'hipótesis' }) : 'hipótesis') : null)
      : W.sinDato('Sin definir')),
    W.par('Cobro en', m.moneda || W.sinDato()),
    W.par('Autonomía', cab.nivel ? (ui.termino ? ui.termino('nivel_autonomia', { texto: `Nivel ${String(cab.nivel).replace(/^N/, '')}` }) : `Nivel ${String(cab.nivel).replace(/^N/, '')}`) : W.sinDato()),
    W.par('Atención', gates.length ? W.tag(gates.length === 1 ? 'Espera tu firma' : `${gates.length} esperan tu firma`, 'aviso', { icono: 'firma' }) : W.tag('Nada espera tu firma', 'ok', { icono: 'ok' })),
    W.par('Actividad', cab.actualizadoEn ? W.cuando(cab.actualizadoEn) : W.sinDato()),
    D.demo ? W.par('Origen', ui.termino ? ui.termino('oferta_demo', { texto: 'Demostración' }) : 'Demostración') : null);
}

/** «Landing original»: la página del referente que ya vende, para abrirla y compararla con la nuestra. Se rellena apenas responde el servidor. */
function tarjetaLandingOriginal(D) {
  const cuerpo = el('div', { class: 'u2-pila u2-pila--chica' }, el('span', { class: 'u2-nota' }, 'Buscando la landing original…'));
  const tarjeta = el('section', { class: 'u2-bloque u2-bloque--suave', 'aria-labelledby': 'u2-landing-orig-t' },
    el('div', { class: 'u2-bloque__cab' }, el('h2', { id: 'u2-landing-orig-t' }, 'Landing original del referente')),
    cuerpo);
  D.ctx.api.sobre(`/oferta/${D.enc}/referente`).then((sobre) => {
    const r = V.normalizarReferentesOferta(sobre && sobre.datos);
    limpiar(cuerpo);
    for (const a of (sobre && sobre.avisos) || []) cuerpo.appendChild(el('p', { class: 'u2-aviso' }, String(a)));
    if (r.filas.length) {
      for (const f of r.filas) {
        cuerpo.appendChild(el('div', { class: 'u2-pila u2-pila--chica' },
          el('div', { class: 'u2-fila' },
            el('a', { class: 'btn btn--primario', href: f.url, target: '_blank', rel: 'noopener noreferrer', 'aria-label': `Abrir la landing original en ${f.dominio} (se abre en otra pestaña)` }, icono('globo', { tam: 16 }), `Abrir la landing de ${f.dominio}`)),
          f.nombre ? el('p', { class: 'u2-nota' }, `Anunciante: ${f.nombre}`) : null,
          f.nota ? el('p', { class: 'u2-nota' }, f.nota) : null,
          f.copiaLocal ? el('p', { class: 'u2-nota' }, 'Copia guardada del HTML: ', el('code', null, f.copiaLocal)) : null));
      }
      cuerpo.appendChild(el('p', { class: 'u2-nota' }, 'Se abre en otra pestaña: es la página real del anunciante, no la nuestra. Modelar es partir de ella; la nuestra se ve en «Página de venta».'));
    } else {
      cuerpo.appendChild(el('p', { class: 'u2-nota' }, 'Todavía no está guardada la landing original de esta oferta. El barrido no trae esa dirección: se encuentra una vez (clic en el botón del anuncio del referente) y se registra.'));
      if (r.comando && ui.comando) cuerpo.appendChild(ui.comando(r.comando, { titulo: 'Comando para registrar la landing original (copiar)' }));
    }
  }).catch((err) => {
    limpiar(cuerpo);
    cuerpo.appendChild(el('p', { class: 'u2-aviso' }, `No se pudo consultar la landing original: ${(err && (err.mensaje || err.message)) || 'error desconocido'}`));
  });
  return tarjeta;
}

function dineroTexto(d) {
  return d && Number.isSafeInteger(d.monto) && d.moneda ? fmt.dinero(d.monto, d.moneda) : null;
}

function metricas(D) {
  const { cab, resumen: r } = D;
  const sinEtapas = r.sinDatos;
  const gates = r.gatesPendientes;
  const M = (o) => (ui.metrica ? ui.metrica(o) : ui.tarjeta({ titulo: o.etiqueta, valor: o.valor, detalle: o.contexto, tono: o.tono }));
  return el('div', { class: 'u2-metricas' },
    M({
      etiqueta: 'Avance', valor: sinEtapas ? null : `${r.aprobadas} de ${r.total}`, tono: r.bloqueadas ? 'error' : (r.completa ? 'ok' : undefined),
      contexto: sinEtapas ? 'Sin estado por etapa todavía' : `etapas aprobadas · ${r.enCurso} en marcha o revisión${r.bloqueadas ? ` · ${r.bloqueadas} bloqueadas` : ''}${r.obsoletas ? ` · ${r.obsoletas} obsoletas` : ''}`,
    }),
    M({
      etiqueta: 'Esperan tu firma', valor: String(gates.length), tono: gates.length ? 'aviso' : 'ok', ayuda: 'gate_pendiente',
      contexto: gates.length ? gates.map((g) => V.etiquetaEtapa(g)).join(', ') : 'Nada pendiente de ti',
    }),
    M({ etiqueta: 'Gasto acumulado', valor: dineroTexto(cab.gastoAcumulado), contexto: dineroTexto(cab.gastoHoy) ? `hoy ${dineroTexto(cab.gastoHoy)}` : 'sin lectura de hoy' }),
    M({ etiqueta: 'Costo de IA', valor: dineroTexto(cab.costoIa), contexto: 'acumulado en esta oferta' }),
    M({
      etiqueta: 'Mejoras pendientes', valor: String(P.resumenBitacora(D.pulido.entradas.filter((e) => e.oferta_id === D.id)).pendientes), contexto: 'pendientes en esta oferta', ruta: '#/pulido',
      tono: P.resumenBitacora(D.pulido.entradas.filter((e) => e.oferta_id === D.id)).altasPendientes ? 'aviso' : undefined,
    }));
}

// ───────────────────────── tarjeta «Próximo paso» ─────────────────────────

const ICONO_PROXIMO = { firmar_gate: 'firma', en_qa: 'ojo', en_progreso: 'progreso', bloqueado: 'octogono', escalado: 'escalar', rehacer: 'reloj-alerta', siguiente: 'play', completa: 'ok', sin_estado: 'info', sin_paso: 'info' };

function tarjetaProximoPaso(D) {
  const p = D.proximo;
  const acciones = [];
  if (p.accion) {
    acciones.push(el('button', { type: 'button', class: 'btn btn--primario u2-btn-grande', onclick: () => D.accion(p.accion) }, icono(p.tipo === 'firmar_gate' ? 'firma' : 'flecha-derecha', { tam: 16 }), p.accion.texto));
  }
  if (p.secundaria) acciones.push(el('button', { type: 'button', class: 'btn u2-btn-grande', onclick: () => D.accion(p.secundaria) }, p.secundaria.texto));
  return el('section', { class: ['u2-proximo', `u2-proximo--${p.tono || 'neutro'}`], 'aria-label': 'Próximo paso' },
    el('div', { class: 'u2-proximo__icono', 'aria-hidden': 'true' }, icono(ICONO_PROXIMO[p.tipo] || 'flecha-derecha', { tam: 26 })),
    el('div', { class: 'u2-proximo__texto' },
      el('span', { class: 'u2-rotulo' }, 'Próximo paso'),
      el('h2', { class: 'u2-proximo__titulo' }, p.titulo),
      p.detalle ? el('p', { class: 'u2-proximo__detalle' }, p.detalle) : null,
      avisoMotor(D)),
    el('div', { class: 'u2-proximo__acciones' }, acciones));
}

/** El sistema automático (engine/orq.py) puede no estar construido: se dice en vez de presentar comandos que fallarían como si funcionaran. */
function avisoMotor(D) {
  if (D.motorDisponible !== false) return null;
  return el('p', { class: 'u2-aviso' }, 'El sistema automático todavía no está instalado en esta computadora: los comandos que ves son los que va a usar, pero aún no se pueden correr.');
}

// ───────────────────────── panel lateral: cómo firmar / cómo ejecutar ─────────────────────────

const etapaVista = (D, id) => D.vistas.find((v) => v.id === id);

function abrirPanelFirma(D, etapaId) {
  const v = etapaVista(D, etapaId);
  if (!v) return;
  const qaPrincipal = v.qa.find((q) => !/^x1-/.test(String(q.archivo).split('/').pop())) || v.qa[0] || null;
  const x1 = v.qa.find((q) => /^x1-/.test(String(q.archivo).split('/').pop())) || null;
  const comandoFirma = V.comandoFirmar(D.idCmd, v.id);
  const items = [
    { ok: v.artefactos.length > 0 ? true : null, texto: v.artefactos.length ? `${v.artefactos.length} ${v.artefactos.length === 1 ? 'archivo producido' : 'archivos producidos'}` : 'La etapa no listó archivos' },
    qaPrincipal ? { ok: qaPrincipal.veredicto === 'PASS' ? true : (qaPrincipal.veredicto === 'FAIL' || qaPrincipal.veredicto === 'ESCALAR' ? false : null), texto: `Revisión de calidad: ${V.veredictoCorto(qaPrincipal.veredicto)}`, detalle: V.textoResumenQa(qaPrincipal.resumen) } : { ok: null, texto: 'Sin informe de revisión de calidad' },
  ];
  if (x1) items.push({ ok: x1.veredicto === 'PASS' ? true : (x1.veredicto === 'FAIL' ? false : null), texto: `Cumplimiento: ${V.veredictoCorto(x1.veredicto)}` });
  const cuerpo = el('div', { class: 'u2-pila' },
    el('p', { class: 'u2-nota' }, 'Esta etapa solo avanza con tu firma. Firmar es un acto tuyo: ', el('strong', null, 'el panel nunca firma, publica, activa ni gasta por ti'), '; te enseña qué revisar y el comando que corres tú.'),
    W.listaPasos([
      { texto: el('strong', null, 'Revisa lo producido'), cuerpo: [W.checklist(items), el('div', { class: 'u2-fila' },
        el('button', { type: 'button', class: 'btn btn--chico', onclick: () => { panel.cerrar(); D.elegir(v.id, { pestana: 'artefactos', enfocar: true }); } }, icono('archivo', { tam: 13 }), 'Abrir los archivos'),
        el('button', { type: 'button', class: 'btn btn--chico', onclick: () => { panel.cerrar(); D.elegir(v.id, { pestana: 'revision', enfocar: true }); } }, icono('ojo', { tam: 13 }), 'Ver la revisión'))] },
      { texto: el('strong', null, 'Firma desde tu terminal'), cuerpo: [
        el('p', { class: 'u2-nota' }, 'Pega este comando en la Terminal, dentro de la carpeta del proyecto. Usa tu clave de firma, que no sale de tu equipo.'),
        ui.comando(comandoFirma, { titulo: 'Cómo hacerlo: copia este comando para firmar', nota: 'Registra tu firma en el estado de la oferta y deja la etapa aprobada.', abierto: true }),
        avisoMotor(D)] },
      { texto: el('strong', null, 'Vuelve aquí'), cuerpo: [el('p', { class: 'u2-nota' }, 'Este panel se actualiza solo (EN VIVO) en cuanto la firma queda registrada, y la siguiente etapa pasa a ser tu próximo paso.')] },
    ]),
    ui.detalleTecnico ? ui.detalleTecnico('Detalle técnico del control', [
      W.kvNodo ? W.kvNodo([['Etapa', V.etiquetaEtapa(v.id)], ['Tipo de control', V.gateTexto(v.gate)], ['Huella del resultado', v.hash ? el('code', null, v.hash) : null], ['Origen del próximo paso', D.proximo.origen === 'servidor' ? 'Lo decidió el servidor del panel' : 'Deducido del estado de las etapas']]) : null,
    ].filter(Boolean)) : null);
  const panel = W.panelLateral({
    titulo: `Firmar ${V.etiquetaEtapa(v.id)}`,
    subtitulo: D.titulo,
    cuerpo,
    alCerrar: () => { D.quitarPanelDeLaRuta(); if (recargaPendiente) { recargaPendiente = false; D.ctx.recargar(); } },
    pie: [el('button', { type: 'button', class: 'btn', onclick: () => panel.cerrar() }, 'Cerrar')],
  });
}

function abrirPanelEjecucion(D, etapaId) {
  const v = etapaVista(D, etapaId || D.proximo.etapa);
  const etapa = v ? v.id : 'D1';
  const cmds = V.comandosEtapa(D.idCmd, etapa, v).filter((c) => c.id !== 'firmar');
  const por = (id) => cmds.find((c) => c.id === id);
  const bloque = (c, abierto = false) => (c ? ui.comando(c.comando, { titulo: c.titulo, nota: c.nota, abierto }) : null);
  const pasos = [];
  if (por('ensayo')) pasos.push({ texto: el('strong', null, 'Haz un simulacro'), cuerpo: [el('p', { class: 'u2-nota' }, 'Muestra qué haría, sin gastar, publicar ni activar nada.'), bloque(por('ensayo'), true)] });
  if (por('real')) pasos.push({ texto: el('strong', null, 'Ejecútala con IA'), cuerpo: [el('p', { class: 'u2-nota' }, 'Gasta crédito de IA y exige límites firmados, cuentas y servicios en verde y que no haya PAUSA (el freno de emergencia).'), bloque(por('real'))] });
  if (por('ingresar')) pasos.push({ texto: el('strong', null, 'O ingresa lo que hagas a mano'), cuerpo: [el('p', { class: 'u2-nota' }, 'Se revisa igual que el trabajo de la IA y deja la etapa esperando tu firma.'), bloque(por('ingresar'))] });
  const cuerpo = el('div', { class: 'u2-pila' },
    el('p', { class: 'u2-nota' }, V.DESCRIPCION_HUMANA[etapa] || ''),
    pasos.length ? W.listaPasos(pasos) : null,
    avisoMotor(D),
    ui.detalleTecnico ? ui.detalleTecnico('Comandos de solo lectura', [bloque(por('estado')), bloque(por('siguiente'))].filter(Boolean)) : null);
  const panel = W.panelLateral({
    titulo: `Cómo ejecutar ${V.etiquetaEtapa(etapa)}`, subtitulo: D.titulo, cuerpo,
    alCerrar: () => { if (recargaPendiente) { recargaPendiente = false; D.ctx.recargar(); } },
    pie: [el('button', { type: 'button', class: 'btn', onclick: () => panel.cerrar() }, 'Cerrar')],
  });
}

// ───────────────────────── pipeline ─────────────────────────

function construirPipeline(D) {
  const etapas = D.vistas.map((v) => ({ ...V.etapaParaPasos(v, { seleccionada: v.id === S.etapa }), icono: W.iconoEtapa(v.id) }));
  return ui.pasos({ etapas, onElegir: (id) => D.elegir(id) });
}

// ───────────────────────── panel de la etapa elegida ─────────────────────────

function construirPanel(D) {
  const v = etapaVista(D, S.etapa);
  const nNotas = P.entradasDeEtapa(D.pulido.entradas, D.id, v.id).filter((e) => e.estado !== 'resuelta').length;
  const veredicto = v.qa[0] ? v.qa[0].veredicto : null;
  const tabsEl = ui.tabs([
    { id: 'resumen', titulo: 'Resumen', render: () => tabResumen(D, v) },
    { id: 'io', titulo: 'Entradas y salidas', render: () => tabEntradasSalidas(D, v) },
    { id: 'artefactos', titulo: `Archivos${v.artefactos.length ? ` · ${v.artefactos.length}` : ''}`, render: () => tabArtefactos(D, v) },
    { id: 'revision', titulo: `Revisión${veredicto ? ` · ${veredicto === 'PASS' ? 'aprobada' : veredicto.toLowerCase().replace(/_/g, ' ')}` : ''}`, render: () => tabRevision(D, v) },
    { id: 'historial', titulo: 'Historial', render: () => tabHistorial(D, v) },
    { id: 'notas', titulo: `Mejoras pendientes${nNotas ? ` · ${nNotas}` : ''}`, render: () => tabNotas(D, v) },
  ], S.tab);
  const recordar = () => { const a = tabsEl.activo && tabsEl.activo(); if (a) S.tab = a; };
  tabsEl.addEventListener('click', recordar);
  tabsEl.addEventListener('keyup', recordar);

  return el('section', { class: 'u2-etapa', 'aria-label': `Etapa ${V.etiquetaEtapa(v.id)}` },
    el('header', { class: 'u2-etapa__cab' },
      el('div', { class: 'u2-etapa__icono', 'aria-hidden': 'true' }, icono(W.iconoEtapa(v.id), { tam: 22 })),
      el('div', null,
        el('h2', { class: 'u2-etapa__titulo' }, V.nombreHumano(v.id), W.codigo(v.id), v.opcional ? W.tag('Opcional', 'neutro', { suave: true }) : null),
        el('div', { class: 'u2-etapa__pregunta' }, V.PREGUNTAS_ETAPA[v.id] || V.ETAPAS[v.id]?.resumen || '')),
      el('div', { class: 'u2-etapa__estado' },
        W.estadoEtapaTag(v),
        v.gate && !v.gatePendiente ? W.tag(V.GATES_HUMANOS[v.gate].titulo, 'neutro', { icono: 'candado', suave: true, titulo: V.GATES_HUMANOS[v.gate].ayuda }) : null,
        v.version ? W.tag(`Versión ${v.version}`, 'neutro', { icono: 'check', suave: true }) : null)),
    el('div', { class: 'u2-etapa__cuerpo' }, tabsEl));
}

// ── pestaña Resumen ──

function aprobadoPorTexto(ap) {
  if (!ap) return null;
  const quien = ap.tipo === 'humano' ? 'Tú' : (ap.tipo === 'qa_pass' ? `Revisor automático${ap.id ? ` (${ap.id})` : ''}` : [ap.tipo, ap.id].filter(Boolean).join(' · '));
  return ap.fecha ? [quien, ' · ', W.cuando(ap.fecha)] : quien;
}

function bloqueGate(D, v) {
  const mk = (tono, titulo, texto, extra) => el('div', { class: ['u2-gate', `u2-gate--${tono}`] },
    el('div', { class: 'u2-gate__titulo' }, icono({ acento: 'firma', aviso: 'alerta', ok: 'ok', info: 'ojo', error: 'octogono', neutro: 'circulo' }[tono], { tam: 18 }), titulo),
    el('p', { class: 'u2-nota' }, texto), extra || null);
  if (v.gatePendiente) {
    return mk('acento', 'Esta etapa espera tu firma', 'La revisión de calidad terminó. Mira los archivos y el informe antes de firmar; el panel solo te enseña el comando.',
      el('div', { class: 'u2-fila' },
        el('button', { type: 'button', class: 'btn btn--primario', onclick: () => D.abrirFirma(v.id) }, icono('firma', { tam: 15 }), 'Ver cómo firmarlo'),
        el('button', { type: 'button', class: 'btn', onclick: () => D.elegir(v.id, { pestana: 'revision' }) }, 'Ver la revisión')));
  }
  if (v.sinDatos) return mk('neutro', 'Sin datos de esta etapa', 'Todavía no hay datos de esta etapa. Se muestra como pendiente.');
  if (v.obsoleta) return mk('aviso', 'Hay que rehacer esta etapa', 'Cambió algo de lo que depende. La versión aprobada anterior se conserva, pero el flujo no sigue hasta rehacerla.', el('div', { class: 'u2-fila' }, el('button', { type: 'button', class: 'btn', onclick: () => D.abrirEjecucion(v.id) }, 'Ver cómo rehacerla')));
  if (v.estado === 'bloqueado' || v.bloqueo) return mk('error', 'Etapa bloqueada', v.bloqueo ? V.bloqueoHumano(v.bloqueo) : 'Falta un dato, un acceso o un servicio externo.');
  if (v.estado === 'escalado') return mk('error', 'Necesita una decisión tuya', 'Tras dos rondas con hallazgos graves, el sistema la pasó a una persona. Solo sale por orden tuya.', el('div', { class: 'u2-fila' }, el('button', { type: 'button', class: 'btn', onclick: () => D.elegir(v.id, { pestana: 'revision' }) }, 'Ver por qué')));
  if (v.estado === 'en_QA') return mk('info', 'En revisión de calidad', v.rondaQa ? `Va por la ronda ${v.rondaQa}. Todavía no hace falta nada de ti.` : 'Todavía no hace falta nada de ti.');
  if (v.estado === 'aprobado') return mk('ok', 'Etapa aprobada', v.version ? `La versión ${v.version} está vigente.` : 'Sin versión registrada.');
  if (v.estado === 'en_progreso') return mk('info', 'En marcha', 'Si la estás armando a mano, ingrésala cuando termines.', el('div', { class: 'u2-fila' }, el('button', { type: 'button', class: 'btn', onclick: () => D.abrirEjecucion(v.id) }, 'Ver cómo ingresarla')));
  return mk('neutro', 'Todavía no empezó', V.dependenciasHumanas(v.id), el('div', { class: 'u2-fila' }, el('button', { type: 'button', class: 'btn', onclick: () => D.abrirEjecucion(v.id) }, 'Ver cómo ejecutarla')));
}

function tabResumen(D, v) {
  const q = v.qa[0] || null;
  const notas = P.entradasDeEtapa(D.pulido.entradas, D.id, v.id);
  const pend = notas.filter((e) => e.estado !== 'resuelta').length;
  const cmds = V.comandosEtapa(D.idCmd, v.id, v).filter((c) => c.id !== 'firmar');
  const kvPares = [
    ['Estado', W.estadoEtapaTag(v)],
    ['Versión aprobada', v.version || W.sinDato('Todavía ninguna')],
    ['Aprobada por', aprobadoPorTexto(v.aprobadoPor) || W.sinDato('Aún nadie')],
    ['Control', v.gate ? el('span', { class: 'u2-fila' }, V.GATES_HUMANOS[v.gate].titulo, ui.ayuda ? ui.ayuda(`gate_${v.gate.toLowerCase()}`) : null) : null],
    ['Rondas de revisión', v.rondaQa != null ? `${v.rondaQa}${v.intentos != null && v.intentos > 1 ? ` · ${v.intentos} intentos` : ''}` : null],
    ['Bloqueo', v.bloqueo ? el('span', { class: 'u2-aviso' }, V.bloqueoHumano(v.bloqueo)) : W.sinDato('Ninguno')],
  ];
  return el('div', { class: 'u2-cols u2-cols--2-1' },
    el('div', { class: 'u2-pila' },
      bloqueGate(D, v),
      el('div', null, el('h3', { class: 'u2-subtitulo' }, 'Qué hace esta etapa'), el('p', { class: 'u2-nota' }, V.DESCRIPCION_HUMANA[v.id] || (V.ETAPAS[v.id] && V.ETAPAS[v.id].resumen) || '')),
      el('div', null, el('h3', { class: 'u2-subtitulo' }, 'Estado'), W.kvNodo(kvPares))),
    el('div', { class: 'u2-pila' },
      el('div', { class: 'u2-bloque u2-bloque--suave' },
        el('div', { class: 'u2-bloque__cab' }, el('h3', null, 'Revisión de calidad')),
        q
          ? el('div', { class: 'u2-pila u2-pila--chica' },
            W.tag(V.veredictoHumano(q.veredicto), V.tonoVeredicto(q.veredicto), { icono: q.veredicto === 'PASS' ? 'ok' : (q.veredicto === 'PASS_CON_NOTAS' ? 'alerta' : 'rombo-alerta') }),
            q.resumen ? el('p', { class: 'u2-nota' }, V.textoResumenQa(q.resumen)) : null,
            el('button', { type: 'button', class: 'u2-enlace-boton', onclick: () => D.elegir(v.id, { pestana: 'revision' }) }, 'Ver la revisión completa'))
          : el('p', { class: 'u2-nota' }, 'Aún no hay informe de revisión para esta etapa.')),
      el('div', { class: 'u2-bloque u2-bloque--suave' },
        el('div', { class: 'u2-bloque__cab' }, el('h3', null, 'Mejoras pendientes')),
        el('p', { class: 'u2-nota' }, notas.length ? `${pend} pendiente${pend === 1 ? '' : 's'} de ${notas.length}.` : 'Nada anotado todavía para esta etapa.'),
        el('div', { class: 'u2-fila' },
          el('button', { type: 'button', class: 'btn btn--chico', onclick: () => D.elegir(v.id, { pestana: 'notas' }) }, 'Abrir notas'),
          el('button', { type: 'button', class: 'btn btn--chico', onclick: () => D.anotar(v.id) }, icono('lapiz', { tam: 13 }), 'Anotar'))),
      ui.detalleTecnico ? ui.detalleTecnico('Datos técnicos de la etapa', [
        W.kvNodo([
          ['Huella del resultado', v.hash ? el('span', { class: 'u2-fila' }, el('code', { title: v.hash }, String(v.hash)), el('button', { type: 'button', class: 'btn btn--chico', onclick: () => copiar(v.hash) }, icono('copiar', { tam: 12 }), 'Copiar')) : null],
          ['Versión de la guía de trabajo (skill)', D.cab.skillsPin[v.id] ? `v${D.cab.skillsPin[v.id]}` : null],
          ['Tipo de control', V.gateTexto(v.gate)],
          ['Estado interno', v.sinDatos ? null : v.estado],
          ['Bloqueo (código)', v.bloqueo ? el('code', null, v.bloqueo) : null],
          ['Carpeta', V.ETAPAS[v.id] && V.ETAPAS[v.id].carpeta ? el('code', null, `ofertas/${D.id}/${V.ETAPAS[v.id].carpeta}/`) : null],
          ['Especificación', V.ETAPAS[v.id] && V.ETAPAS[v.id].departamento ? el('code', null, V.ETAPAS[v.id].departamento) : null],
        ]),
      ]) : null,
      ui.detalleTecnico ? ui.detalleTecnico('Comandos para trabajar esta etapa', [
        avisoMotor(D),
        ...cmds.map((c) => ui.comando(c.comando, { titulo: c.titulo, nota: c.nota })),
      ].filter(Boolean)) : null));
}

// ── pestaña Entradas y salidas ──

function tabEntradasSalidas(D, v) {
  const entradas = V.entradasDeEtapa(v.id, D.estadoJson);
  const salidas = V.salidasDeEtapa(v.id);
  const usadaPor = V.ORDEN_ETAPAS.filter((id) => (V.ETAPAS[id].dependeDe || []).includes(v.id));
  const colEntradas = el('div', { class: 'u2-pila u2-pila--chica' },
    el('h3', { class: 'u2-subtitulo' }, 'Entradas: lo que necesita'),
    entradas.length
      ? el('ul', { class: 'u2-lista' }, entradas.map((e) => {
        const dep = etapaVista(D, e.etapa);
        const ok = dep && !dep.sinDatos && dep.estado === 'aprobado' && !dep.obsoleta;
        return el('li', null,
          el('span', { class: ok ? 'u2-ic--ok' : 'u2-ic--aviso' }, icono(ok ? 'ok' : 'alerta', { tam: 16 })),
          el('span', { class: 'u2-lista__texto' },
            el('button', { type: 'button', class: 'u2-enlace-boton', onclick: () => D.elegir(e.etapa) }, V.nombreHumano(e.etapa)), ' ', W.codigo(e.etapa),
            ok ? null : el('div', { class: 'u2-aviso' }, 'Sin aprobar: esta etapa no puede avanzar hasta que lo esté.')));
      }))
      : el('p', { class: 'u2-nota' }, v.id === 'D1' ? 'Descubrir abre el flujo: parte del banco de problemas y de la ficha inicial (brief) que firmaste.' : 'Esta etapa no declara entradas.'),
    entradas.some((e) => e.hash) && ui.detalleTecnico ? ui.detalleTecnico('Huellas de las entradas', [W.kvNodo(entradas.map((e) => [V.etiquetaEtapa(e.etapa), e.hash ? el('code', null, e.hash) : null]))]) : null);
  const colSalidas = el('div', { class: 'u2-pila u2-pila--chica' },
    el('h3', { class: 'u2-subtitulo' }, 'Salidas: lo que entrega'),
    salidas.length
      ? el('ul', { class: 'u2-lista' }, salidas.map((s) => {
        const hay = v.artefactos.some((a) => a.ruta === s || (s.endsWith('/') && a.ruta.startsWith(s)));
        return el('li', null,
          el('span', { class: hay ? 'u2-ic--ok' : 'u2-ic--neutro' }, icono(hay ? 'ok' : 'circulo-punteado', { tam: 16 })),
          el('span', { class: 'u2-lista__texto' }, nombreSalida(s), el('div', { class: 'u2-tenue u2-mono' }, s)),
          W.tag(hay ? 'Presente' : 'Aún no existe', hay ? 'ok' : 'neutro', { suave: !hay }));
      }))
      : el('p', { class: 'u2-nota' }, 'Queda fuera de la primera prueba: no tiene salidas.'));
  return el('div', { class: 'u2-pila' },
    el('div', { class: 'u2-flujo' }, colEntradas, el('div', { class: 'u2-flujo__centro', 'aria-hidden': 'true' }, icono('flecha-derecha', { tam: 22 })), colSalidas),
    usadaPor.length ? el('p', { class: 'u2-nota' }, 'La usan después: ', usadaPor.map((id, i) => [i ? ', ' : '', el('button', { type: 'button', class: 'u2-enlace-boton', onclick: () => D.elegir(id) }, V.nombreHumano(id))])) : null);
}

function nombreSalida(ruta) {
  const base = ruta.endsWith('/') ? ruta.slice(0, -1).split('/').pop() : ruta.split('/').pop();
  const t = base.replace(/\.[a-z0-9]+$/i, '').replace(/[-_]+/g, ' ');
  return ruta.endsWith('/') ? `Carpeta «${base}»` : t.charAt(0).toUpperCase() + t.slice(1);
}

// ── pestaña Artefactos (lista + visor + diferencias) ──

function tabArtefactos(D, v) {
  if (!v.artefactos.length) {
    const meta_ = V.ETAPAS[v.id] || {};
    return ui.vacioConPasos({
      titulo: `${V.nombreHumano(v.id)} aún no tiene archivos`,
      explicacion: v.estado === 'pendiente' ? 'La etapa todavía no se ejecutó: los archivos aparecen aquí cuando el sistema los entrega.' : 'El sistema no registró archivos para esta etapa.',
      icono: 'carpeta',
      pasos: [
        { texto: 'Haz un simulacro de la etapa para ver qué produciría:', comando: (V.comandosEtapa(D.idCmd, v.id).find((c) => c.id === 'ensayo') || {}).comando },
        { texto: `Si la haces a mano, deja lo producido en ${meta_.carpeta ? `la carpeta de la etapa (ofertas/${D.id}/${meta_.carpeta}/)` : 'la carpeta de la oferta'} e ingrésalo.` },
      ].filter((p) => p.texto),
    });
  }
  const visor = el('div', { class: 'u2-visor' });
  const pintarVisor = () => {
    limpiar(visor);
    if (S.cmp && S.cmp.a != null && S.cmp.b != null) {
      const g = V.gruposDeVersiones(v.artefactos).find((x) => x.clave === S.cmp.clave);
      const A = g && g.versiones.find((x) => x.n === S.cmp.a);
      const B = g && g.versiones.find((x) => x.n === S.cmp.b);
      if (A && B) { visor.appendChild(vistaDiferencias(D, A, B)); return; }
    }
    const art = S.verRuta ? v.artefactos.find((a) => a.ruta === S.verRuta) : null;
    if (!art) {
      visor.appendChild(el('div', { class: 'u2-vacio-visor' }, icono('archivo', { tam: 26 }), el('strong', null, 'Elige un archivo'), el('span', { class: 'u2-nota' }, 'Se abre aquí para leerlo: documentos, datos, páginas (como código) o imágenes. Desde el panel no se puede editar.')));
      return;
    }
    visor.appendChild(vistaArchivo(D, art));
  };
  const lista = el('div', { class: 'u2-art__lista', role: 'list', 'aria-label': 'Archivos de la etapa' });
  const pintarLista = () => {
    limpiar(lista);
    for (const g of V.agruparPorCarpeta(v.artefactos)) {
      lista.appendChild(el('div', { class: 'u2-art__grupo' }, `${g.carpeta}/`));
      for (const a of g.items) {
        const tipo = V.tipoVisor(a);
        lista.appendChild(el('button', {
          type: 'button', role: 'listitem', class: 'u2-art__item', title: a.ruta, 'aria-current': S.verRuta === a.ruta && !S.cmp ? 'true' : null,
          onclick: () => { S.verRuta = a.ruta; S.cmp = null; pintarLista(); pintarVisor(); },
        }, icono({ json: 'archivo', md: 'libro', yaml: 'ajustes', html: 'pantalla', imagen: 'ojo', texto: 'archivo' }[tipo] || 'archivo', { tam: 16 }),
        el('span', { class: 'u2-art__nombre' }, a.ruta.split('/').pop()),
        el('span', { class: 'u2-art__meta' }, `${V.rotuloTipoArchivo(tipo)} · ${fmt.bytes(a.bytes)}`)));
      }
    }
  };
  pintarLista(); pintarVisor();
  const grupos2 = V.gruposDeVersiones(v.artefactos);
  const total = v.artefactos.reduce((n, x) => n + (Number.isFinite(x.bytes) ? x.bytes : 0), 0);
  return el('div', { class: 'u2-pila' },
    el('div', { class: 'u2-fila u2-fila--entre' },
      el('span', { class: 'u2-nota' }, `${v.artefactos.length} archivo${v.artefactos.length === 1 ? '' : 's'} · ${fmt.bytes(total)}`),
      ui.fuente ? ui.fuente([`ofertas/${D.id}/${(V.ETAPAS[v.id] || {}).carpeta ? `${V.ETAPAS[v.id].carpeta}/` : ''}`], {}) : null),
    el('div', { class: 'u2-art' }, lista, visor),
    grupos2.length ? controlComparar(D, v, grupos2, () => { pintarLista(); pintarVisor(); })
      : el('p', { class: 'u2-nota' }, 'Cuando exista más de una versión del mismo archivo (v1, v2…) podrás compararlas aquí.'));
}

function controlComparar(D, v, grupos, repintar) {
  const cmp = S.cmp && grupos.some((g) => g.clave === S.cmp.clave) ? S.cmp : { clave: grupos[0].clave, a: null, b: null };
  const g = grupos.find((x) => x.clave === cmp.clave);
  const ult = g.versiones[g.versiones.length - 1].n;
  const pen = g.versiones.length > 1 ? g.versiones[g.versiones.length - 2].n : ult;
  const selGrupo = W.selectDe(grupos.map((x) => ({ valor: x.clave, texto: x.clave })), cmp.clave, { class: 'campo campo--chico', 'aria-label': 'Archivo a comparar' });
  const opciones = g.versiones.map((x) => ({ valor: String(x.n), texto: `v${x.n}` }));
  const selA = W.selectDe(opciones, String(cmp.a ?? pen), { class: 'campo campo--chico', 'aria-label': 'Versión anterior' });
  const selB = W.selectDe(opciones, String(cmp.b ?? ult), { class: 'campo campo--chico', 'aria-label': 'Versión nueva' });
  selGrupo.onchange = () => { S.cmp = { clave: selGrupo.value, a: null, b: null }; D.pintarPanel(); };
  return el('div', { class: 'u2-cmp' },
    el('strong', null, 'Comparar versiones'), selGrupo, selA, icono('flecha-derecha', { tam: 14 }), selB,
    el('button', { type: 'button', class: 'btn btn--chico btn--primario', onclick: () => { S.cmp = { clave: selGrupo.value, a: Number(selA.value), b: Number(selB.value) }; S.verRuta = null; repintar(); } }, 'Comparar'));
}

const DATA_IMG = /^data:image\/(png|jpeg|gif|webp|svg\+xml);base64,[A-Za-z0-9+/=]+$/;

/** Cuerpo del visor para un archivo. El contenido siempre entra como texto (visorTexto/visorJson); las imágenes solo como data-URL de imagen. */
function vistaArchivo(D, art) {
  const caja = el('div', { class: 'u2-visor' }, esperando('Cargando archivo…'));
  leerArchivo(D.ctx, D.id, art.ruta, huellaDe(art)).then((r) => {
    limpiar(caja);
    const tipo = r.tipo || V.tipoVisor(art);
    caja.appendChild(el('div', { class: 'u2-visor__cab' },
      el('strong', null, art.ruta.split('/').pop()), W.tag(V.rotuloTipoArchivo(tipo), 'neutro', { suave: true, icono: 'archivo' }), el('span', { class: 'u2-tenue' }, fmt.bytes(r.bytes ?? art.bytes)),
      r.mtime ? el('span', { class: 'u2-tenue' }, 'modificado ', W.cuando(r.mtime)) : null,
      r.truncado ? W.tag('Truncado: solo el principio', 'aviso') : null,
      ui.fuente ? ui.fuente([`ofertas/${D.id}/${r.ruta || art.ruta}`], { leido: r.mtime }) : null,
      el('button', { type: 'button', class: 'btn btn--chico', onclick: () => copiar(`ofertas/${D.id}/${r.ruta || art.ruta}`) }, icono('copiar', { tam: 12 }), 'Copiar ruta')));
    const contenido = typeof r.contenido === 'string' ? r.contenido : '';
    if (tipo === 'imagen') {
      if (DATA_IMG.test(contenido)) {
        const img = el('img', { alt: `Vista previa de ${art.ruta}`, loading: 'lazy' });
        img.src = contenido; // data-URL validada; ui.el no admite data: en src
        caja.appendChild(img);
      } else caja.appendChild(el('p', { class: 'u2-aviso' }, 'No se puede mostrar la imagen: pesa más de 1 MB o no es un formato admitido.'));
    } else if (tipo === 'json') {
      let obj;
      try { obj = JSON.parse(contenido); } catch (_) { obj = undefined; }
      if (obj !== undefined && !r.truncado) caja.appendChild(ui.visorJson(obj, { colapsado: true, titulo: art.ruta }));
      else caja.appendChild(ui.visorTexto(contenido, { tipo: 'json' }));
    } else if (tipo === 'html') {
      caja.appendChild(el('p', { class: 'u2-nota' }, 'La página se muestra como código y nunca se ejecuta aquí. Para verla como la ve el cliente, abre ', el('a', { class: 'enlace', href: '#/landing' }, 'Página de venta'), '.'));
      caja.appendChild(ui.visorTexto(contenido, { tipo: 'html' }));
    } else caja.appendChild(ui.visorTexto(contenido, { tipo }));
  }).catch((err) => { limpiar(caja); caja.appendChild(ui.errorBox(err)); });
  return caja;
}

function normalizarParaDiff(r, ruta) {
  const c = typeof r.contenido === 'string' ? r.contenido : '';
  if (V.tipoVisor({ ruta, tipo: r.tipo }) === 'json' && !r.truncado) {
    try { return JSON.stringify(JSON.parse(c), null, 2); } catch (_) { return c; }
  }
  return c;
}

function vistaDiferencias(D, A, B) {
  const caja = el('div', { class: 'u2-visor' }, esperando('Comparando…'));
  Promise.all([leerArchivo(D.ctx, D.id, A.ruta, huellaDe(A)), leerArchivo(D.ctx, D.id, B.ruta, huellaDe(B))]).then(([ra, rb]) => {
    limpiar(caja);
    caja.appendChild(el('div', { class: 'u2-visor__cab' }, el('strong', null, 'Diferencias'), el('code', null, A.ruta), icono('flecha-derecha', { tam: 14 }), el('code', null, B.ruta),
      ra.truncado || rb.truncado ? W.tag('Alguna versión está truncada: comparación parcial', 'aviso') : null));
    const d = V.diferenciaLineas(normalizarParaDiff(ra, A.ruta), normalizarParaDiff(rb, B.ruta));
    if (d.truncado) { caja.appendChild(el('p', { class: 'u2-aviso' }, `Las versiones superan ${V.TOPE_LINEAS_DIFF} líneas: ábrelas por separado.`)); return; }
    const res = V.resumenDiff(d.lineas);
    caja.appendChild(el('div', { class: 'u2-fila' }, res.igual ? W.tag('Sin diferencias', 'ok') : [W.tag(`+${res.mas} líneas`, 'ok', { icono: 'mas' }), W.tag(`−${res.menos} líneas`, 'error', { icono: 'menos' })]));
    if (res.igual) return;
    const vista = el('div', { class: 'u2-diff', role: 'region', 'aria-label': 'Diferencias', tabindex: '0' });
    for (const l of V.contextoDiff(d.lineas, 3)) {
      if (l.tipo === 'salto') { vista.appendChild(el('div', { class: 'u2-diff__salto' }, `… ${l.n} línea${l.n === 1 ? '' : 's'} sin cambios`)); continue; }
      vista.appendChild(el('div', { class: ['u2-diff__l', l.tipo !== 'igual' && `u2-diff__l--${l.tipo}`] },
        el('span', { class: 'u2-diff__n' }, l.a ?? ''), el('span', { class: 'u2-diff__n' }, l.b ?? ''),
        el('span', { class: 'u2-diff__s', 'aria-label': l.tipo === 'mas' ? 'añadida' : (l.tipo === 'menos' ? 'quitada' : 'igual') }, l.tipo === 'mas' ? '+' : (l.tipo === 'menos' ? '−' : ' ')),
        el('span', null, l.texto === '' ? ' ' : l.texto)));
    }
    caja.appendChild(vista);
  }).catch((err) => { limpiar(caja); caja.appendChild(ui.errorBox(err)); });
  return caja;
}

// ── pestaña Revisión (QA) ──

function tabRevision(D, v) {
  if (!v.qa.length) {
    return ui.vacioConPasos({
      titulo: `${V.nombreHumano(v.id)} aún no tiene revisión de calidad`,
      explicacion: 'La revisión de calidad la hace un revisor independiente después de que se produce el trabajo: solo mira, no corrige. Sus informes aparecen aquí.',
      icono: 'ojo',
      pasos: [
        { texto: 'Ejecuta o ingresa la etapa: al terminar, el sistema lanza la revisión solo.' },
        { texto: 'Cuando exista el informe, verás el veredicto, la nota, los hallazgos por gravedad y su evidencia.' },
      ],
    });
  }
  const raiz = el('div', { class: 'u2-pila' });
  for (const q of v.qa) {
    const ruta = V.rutaInformeQa(q.archivo);
    const esX1 = /^x1-/.test(ruta.split('/').pop());
    const cuerpo = el('div', { class: 'u2-pila' }, esperando('Cargando el informe…'));
    raiz.appendChild(el('section', { class: 'u2-bloque' },
      el('div', { class: 'u2-bloque__cab' },
        el('h3', null, esX1 ? 'Cumplimiento' : 'Revisión de calidad'),
        ui.fuente ? ui.fuente([`ofertas/${D.id}/${ruta}`], {}) : null),
      cuerpo));
    leerArchivo(D.ctx, D.id, ruta, String(D.estadoJson.revision ?? '')).then((r) => {
      let inf = null;
      try { inf = JSON.parse(r.contenido); } catch (_) { inf = null; }
      limpiar(cuerpo);
      if (!inf || r.truncado) { cuerpo.appendChild(el('p', { class: 'u2-aviso' }, 'No se pudo leer el informe (está dañado o incompleto). Ábrelo desde la pestaña Archivos.')); return; }
      cuerpo.appendChild(informeQa(D, V.vistaInformeQa(inf), q, inf, ruta, esX1));
    }).catch((err) => {
      limpiar(cuerpo);
      cuerpo.appendChild(el('div', { class: 'u2-pila u2-pila--chica' },
        W.tag(V.veredictoHumano(q.veredicto), V.tonoVeredicto(q.veredicto)),
        el('p', { class: 'u2-nota' }, V.textoResumenQa(q.resumen)),
        el('p', { class: 'u2-aviso' }, `No se pudo leer el informe completo: ${(err && (err.mensaje || err.message)) || 'error'}`)));
    });
  }
  return raiz;
}

function informeQa(D, vi, q, crudo, ruta, esX1 = false) {
  const caja = el('div', { class: 'u2-pila' });
  const icoVer = { ok: 'ok', aviso: 'alerta', error: 'rombo-alerta', neutro: 'circulo' }[vi.tono] || 'circulo';
  const nota = V.puntajeTexto(vi.puntaje);
  const umbral = V.puntajeTexto(vi.umbral);
  caja.appendChild(el('div', { class: ['u2-veredicto', `u2-veredicto--${vi.tono}`] },
    el('div', { class: 'u2-veredicto__icono', 'aria-hidden': 'true' }, icono(icoVer, { tam: 22 })),
    el('div', null,
      el('div', { class: 'u2-veredicto__titulo' }, esX1 ? V.veredictoCumplimiento(vi.veredicto) : V.veredictoHumano(vi.veredicto), ' ', ui.ayuda ? ui.ayuda('veredicto_qa') : null),
      el('div', { class: 'u2-nota' }, [vi.ronda != null ? `Ronda ${vi.ronda}` : null, vi.version, vi.creadoEn ? fmt.fecha(vi.creadoEn) : null].filter(Boolean).join(' · '))),
    nota ? el('div', { class: 'u2-puntaje' }, el('div', { class: 'u2-puntaje__n' }, nota), el('div', { class: 'u2-puntaje__de' }, umbral ? `mínimo ${umbral} · sobre 5` : 'sobre 5')) : null));
  // hallazgos por gravedad
  const conteo = V.SEVERIDADES_QA.map((s) => W.tag(`${V.SEVERIDAD_QA_HUMANA[s]} ${vi.conteo[s]}`, vi.conteo[s] === 0 ? 'neutro' : V.tonoSeveridadQa(s), { suave: vi.conteo[s] === 0, titulo: V.AYUDA_SEVERIDAD_QA[s] }));
  caja.appendChild(el('div', { class: 'u2-fila' }, el('span', { class: 'u2-rotulo' }, 'Hallazgos', ' ', ui.ayuda ? ui.ayuda('severidad_qa') : null), conteo,
    vi.abiertos ? W.tag(`${vi.abiertos} sin resolver`, 'error') : W.tag('Ninguno sin resolver', 'ok', { icono: 'ok' }),
    vi.checksFallidos ? W.tag(`${vi.checksFallidos} comprobación${vi.checksFallidos === 1 ? '' : 'es'} automática${vi.checksFallidos === 1 ? '' : 's'} en fallo`, 'error') : null));
  const todos = [...V.SEVERIDADES_QA.flatMap((s) => vi.porSeveridad[s]), ...vi.otros];
  if (todos.length) {
    caja.appendChild(el('div', { class: 'u2-pila u2-pila--chica' }, todos.map((h) => {
      const tono = V.tonoSeveridadQa(h.severidad);
      const est = V.estadoHallazgo(h.estado);
      return el('article', { class: ['u2-hallazgo', `u2-hallazgo--${tono}`] },
        el('div', { class: 'u2-hallazgo__cab' },
          W.tag(V.SEVERIDAD_QA_HUMANA[h.severidad] || h.severidad || '—', tono, { icono: h.severidad === 'BLOQUEANTE' || h.severidad === 'MAYOR' ? 'rombo-alerta' : (h.severidad === 'MENOR' ? 'alerta' : 'info') }),
          W.tag(est.texto, est.tono, { icono: est.abierto ? 'circulo' : 'ok', suave: true }),
          h.check_id ? el('span', { class: 'u2-tenue u2-mono' }, h.check_id) : null),
        el('div', null, h.descripcion || ''),
        h.evidencia ? el('blockquote', { class: 'u2-cita' }, 'Evidencia: ', el('code', null, String(h.evidencia))) : null,
        h.correccion ? el('div', { class: 'u2-nota' }, `Corrección: ${h.correccion}`) : null);
    })));
  } else caja.appendChild(el('p', { class: 'u2-nota' }, vi.justificacion ? `Sin hallazgos. Justificación del revisor: ${vi.justificacion}` : 'El informe no lista hallazgos.'));
  // rúbrica
  if (vi.items.length) {
    caja.appendChild(el('div', { class: 'u2-pila u2-pila--chica' }, el('h4', { class: 'u2-subtitulo' }, 'Criterios de la revisión ', ui.ayuda ? ui.ayuda('rubrica_qa') : null),
      el('ul', { class: 'u2-rubrica' }, vi.items.map((it) => {
        const n = Number(it.puntaje);
        const tono = n >= 4 ? 'ok' : (n >= 3 ? 'aviso' : 'error');
        return el('li', null, el('span', { title: it.evidencia ? String(it.evidencia) : null }, it.nombre || it.item_id || '—'), W.barra((n / 5) * 100, Number.isFinite(n) ? tono : '', `${it.puntaje ?? '—'} sobre 5`), el('strong', { class: 'u2-puntaje' }, Number.isFinite(n) ? `${n}/5` : '—'));
      }))));
  }
  const extras = [];
  if (Array.isArray(crudo.riesgos_residuales) && crudo.riesgos_residuales.length) extras.push(el('div', null, el('h4', { class: 'u2-subtitulo' }, 'Riesgos que quedan'), el('ul', { class: 'u2-lista' }, crudo.riesgos_residuales.map((r) => el('li', null, icono('alerta', { tam: 15 }), el('span', { class: 'u2-lista__texto' }, String(r)))))));
  if (Array.isArray(crudo.mejoras_propuestas) && crudo.mejoras_propuestas.length) extras.push(el('div', null, el('h4', { class: 'u2-subtitulo' }, 'Mejoras propuestas'), el('ul', { class: 'u2-lista' }, crudo.mejoras_propuestas.map((m) => el('li', null, icono('chispa', { tam: 15 }), el('span', { class: 'u2-lista__texto' }, m && m.descripcion ? m.descripcion : String(m)), m && m.impacto ? W.tag(`impacto ${m.impacto}`, 'neutro', { suave: true }) : null, m && m.esfuerzo ? W.tag(`esfuerzo ${m.esfuerzo}`, 'neutro', { suave: true }) : null)))));
  if (Array.isArray(crudo.aprendizajes_para_skill) && crudo.aprendizajes_para_skill.length) extras.push(el('div', null, el('h4', { class: 'u2-subtitulo' }, 'Para sumar a la guía de trabajo ', ui.ayuda ? ui.ayuda('regla_de_skill') : null), el('ul', { class: 'u2-lista' }, crudo.aprendizajes_para_skill.map((m) => el('li', null, icono('libro', { tam: 15 }), el('span', { class: 'u2-lista__texto' }, typeof m === 'string' ? m : (m && (m.descripcion || m.texto)) || JSON.stringify(m)))))));
  if (extras.length) caja.appendChild(el('div', { class: 'u2-cols' }, extras));
  if (vi.x1) caja.appendChild(el('p', { class: 'u2-nota' }, `Incluye el informe de cumplimiento: ${V.veredictoCorto(vi.x1.veredicto)}.`));
  if (vi.semaforo) caja.appendChild(el('div', { class: 'u2-fila' }, 'Semáforo de cumplimiento:', W.tag(String(vi.semaforo), String(vi.semaforo) === 'verde' ? 'ok' : (String(vi.semaforo) === 'rojo' ? 'error' : 'aviso')), vi.vigenciaHasta ? el('span', { class: 'u2-tenue' }, `vigente hasta ${fmt.fecha(vi.vigenciaHasta)}`) : null));
  if (ui.detalleTecnico) {
    const tecnico = [W.kvNodo([
      ['Informe', el('code', null, ruta)],
      ['Archivo revisado', crudo.artefacto_ref ? el('code', null, crudo.artefacto_ref) : null],
      ['Huella del archivo revisado', crudo.artefacto_sha256 ? el('code', null, crudo.artefacto_sha256) : null],
      ['Versión de la guía de trabajo (quien lo preparó / el revisor)', [crudo.skill_version_maker, crudo.skill_version_qa].filter(Boolean).join(' / ') || null],
    ])];
    if (vi.checks.length) tecnico.push(el('div', { class: 'u2-pila u2-pila--chica' }, el('h4', { class: 'u2-subtitulo' }, 'Comprobaciones automáticas ', ui.ayuda ? ui.ayuda('checks_l1') : null),
      el('ul', { class: 'u2-lista' }, vi.checks.map((c) => el('li', null, el('span', { class: c.resultado === 'pass' ? 'u2-ic--ok' : 'u2-ic--error' }, icono(c.resultado === 'pass' ? 'ok' : 'x-circulo', { tam: 15 })), el('span', { class: 'u2-mono' }, c.check_id || '—'), el('span', { class: 'u2-nota u2-lista__texto' }, c.detalle || ''))))));
    tecnico.push(ui.visorJson(crudo, { colapsado: true, titulo: ruta }));
    caja.appendChild(ui.detalleTecnico('Informe completo y datos técnicos', tecnico));
  }
  void q;
  return caja;
}

// ── pestaña Historial ──

const ICONO_EVENTO = { accion: 'chispa', transicion: 'flecha-derecha', llamada_herramienta: 'engranaje', decision: 'bandera', bloqueo: 'octogono', alerta: 'alerta', aprobacion: 'ok' };

function tabHistorial(D, v) {
  const host = el('div', { class: 'u2-pila' });
  const lineas = D.registro ? V.lineasDeRegistro(D.registro.datos) : [];
  const total = D.registro && D.registro.datos && typeof D.registro.datos.total === 'number' ? D.registro.datos.total : lineas.length;
  const toda = el('input', { type: 'checkbox', id: 'u2-toda', onchange: (ev) => { S.toda = ev.target.checked; pintar(); } });
  toda.checked = S.toda;
  function pintar() {
    limpiar(host);
    host.appendChild(el('div', { class: 'u2-fila u2-fila--entre' },
      el('span', { class: 'u2-nota' }, S.toda ? 'Todo lo que pasó en la oferta, lo más reciente primero.' : `Lo que pasó en ${V.nombreHumano(v.id)}, lo más reciente primero.`),
      el('label', { class: 'interruptor', for: 'u2-toda' }, toda, 'Ver toda la oferta')));
    if (D.registroError) { host.appendChild(ui.errorBox(D.registroError, { reintentar: () => D.ctx.recargar() })); return; }
    if (!lineas.length) {
      host.appendChild(ui.vacioConPasos({
        titulo: 'Todavía no hay historial de esta oferta', explicacion: 'Cada vez que el sistema ejecuta o cambia de estado una etapa, queda un movimiento aquí, en vivo.', icono: 'reloj',
        pasos: [{ texto: 'Haz un simulacro de una etapa para ver cómo aparece su primer movimiento:', comando: (V.comandosEtapa(D.idCmd, v.id).find((c) => c.id === 'ensayo') || {}).comando }],
      }));
      return;
    }
    const eventos = V.lineaDeTiempo(lineas, { etapa: S.toda ? null : v.id, limite: 200 });
    if (!eventos.length) { host.appendChild(el('p', { class: 'u2-nota' }, `No hay movimientos de ${V.nombreHumano(v.id)} en las últimas ${lineas.length} líneas del historial.`)); }
    else {
      host.appendChild(el('ol', { class: 'u2-linea' }, eventos.slice(0, 60).map((e) => el('li', null,
        el('span', { class: ['u2-linea__punto', `u2-linea__punto--${e.tono === 'neutro' ? '' : e.tono}`], 'aria-hidden': 'true' }, icono(ICONO_EVENTO[e.evento] || 'circulo', { tam: 14 })),
        el('div', { class: 'u2-linea__texto' },
          el('div', null, el('strong', null, V.eventoHumano(e.evento)), e.texto ? ` · ${e.texto}` : '', e.estado ? ` · ${e.estado}` : ''),
          el('div', { class: 'u2-tenue', style: { fontSize: '.82rem' } }, [e.etapa ? V.etiquetaEtapa(e.etapa) : null, e.agente].filter(Boolean).join(' · '))),
        el('span', { class: 'u2-linea__cuando' }, W.cuando(e.ts))))));
      if (eventos.length > 60) host.appendChild(el('p', { class: 'u2-nota' }, `Se muestran 60 de ${eventos.length}; la tabla completa está en el detalle técnico.`));
    }
    if (ui.detalleTecnico) {
      host.appendChild(ui.detalleTecnico('Historial completo (tabla)', [
        ui.tabla({
          etiqueta: 'Historial de la oferta', altoMax: '380px', filas: eventos,
          columnas: [
            { clave: 'ts', titulo: 'Cuándo', ancho: '120px', formato: (t) => W.cuando(t) },
            { clave: 'etapa', titulo: 'Etapa', ancho: '70px', formato: (e) => (e ? el('code', null, e) : '—') },
            { clave: 'evento', titulo: 'Evento', ancho: '150px', formato: (e, f) => ui.chip(String(e ?? '—').replace(/_/g, ' '), f.tono) },
            { clave: 'agente', titulo: 'Agente', ancho: '150px' },
            { clave: 'texto', titulo: 'Qué pasó', flex: true },
            { clave: 'estado', titulo: 'Resultado', ancho: '120px', formato: (e, f) => (e ? [ui.chip(e, e === 'ok' ? 'ok' : (e === 'bloqueado' ? 'error' : 'neutro')), f.codigo != null ? el('span', { class: 'u2-tenue' }, ` ${f.codigo}`) : null] : '—') },
          ],
        }),
        el('p', { class: 'u2-nota' }, `Mostrando ${eventos.length} de ${lineas.length} línea${lineas.length === 1 ? '' : 's'} leída${lineas.length === 1 ? '' : 's'}${total > lineas.length ? ` (el historial tiene ${total} en total)` : ''}. La cadena de huellas se verifica en la pantalla Historial.`),
      ]));
    }
  }
  pintar();
  return host;
}

// ── pestaña Notas de pulido ──

function tabNotas(D, v) {
  if (D.pulido.error && !D.pulido.sobre) return ui.errorBox(D.pulido.error, { reintentar: () => D.refrescarPulido() });
  const entradas = P.entradasDeEtapa(D.pulido.entradas, D.id, v.id);
  const pend = entradas.filter((e) => e.estado !== 'resuelta').length;
  // alta rápida: una línea
  const campo = el('input', { class: 'campo', type: 'text', maxlength: String(P.LIMITES.titulo), placeholder: `Qué corregirías en ${V.nombreHumano(v.id)}…`, 'aria-label': 'Anotación rápida' });
  let sev = 'media';
  const segSev = W.segmentado([{ valor: 'alta', texto: 'Alta', icono: 'rombo-alerta' }, { valor: 'media', texto: 'Media', icono: 'alerta' }, { valor: 'baja', texto: 'Baja', icono: 'info' }], sev, (x) => { sev = x; }, { etiqueta: 'Gravedad' });
  const enviar = async () => {
    const r = P.validarRapida({ titulo: campo.value, etapa: v.id, oferta_id: D.id, severidad: sev });
    if (!r.ok) { toast(Object.values(r.errores).join(' '), 'aviso'); campo.focus(); return; }
    try { await D.ctx.api.post('/pulido', r.cuerpo); toast('Anotado en Mejoras pendientes.', 'ok'); campo.value = ''; await D.refrescarPulido(); } catch (err) { toast(`No se pudo guardar: ${err.mensaje || err.message}`, 'error'); }
  };
  campo.addEventListener('keydown', (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); enviar(); } });
  const caja = el('div', { class: 'u2-pila' },
    el('div', { class: 'u2-fila u2-fila--entre' },
      el('span', { class: 'u2-nota' }, entradas.length ? `${pend} pendiente${pend === 1 ? '' : 's'} de ${entradas.length} · ` : 'Aquí va lo que corriges mientras armas esta etapa a mano. ', ui.termino ? ui.termino('bitacora_pulido', { texto: '¿Para qué sirve?' }) : null),
      el('a', { class: 'enlace', href: '#/pulido' }, 'Ver todo el pulido')),
    el('div', { class: 'u2-alta-rapida' }, campo, segSev,
      el('button', { type: 'button', class: 'btn btn--primario', onclick: enviar }, icono('mas', { tam: 14 }), 'Anotar'),
      el('button', { type: 'button', class: 'btn', onclick: () => D.anotar(v.id) }, 'Con detalle…')));
  if (!entradas.length) {
    caja.appendChild(ui.vacioConPasos({
      titulo: `Nada anotado en ${V.nombreHumano(v.id)} todavía`,
      explicacion: 'Cada corrección que haces a mano sirve para mejorar la guía de trabajo (skill) de la etapa. Anótala aquí en cuanto la veas.', icono: 'lapiz',
      pasos: [{ texto: 'Revisa los archivos de la etapa y la revisión de calidad.' }, { texto: 'Escribe arriba qué corregirías y pulsa «Anotar».' }, { texto: 'Cuando esté corregido, márcala como resuelta: así se ve qué pasos ya están pulidos.' }],
    }));
    return caja;
  }
  caja.appendChild(el('div', { class: 'u2-pila u2-pila--chica' }, entradas.map((e) => tarjetaNota(e, D))));
  return caja;
}

function tarjetaNota(e, D) {
  const sig = P.siguienteEstado(e.estado);
  const boton = el('button', {
    type: 'button', class: ['btn btn--chico', e.estado === 'abierta' && 'btn--primario'], onclick: async (ev) => {
      const b = ev.currentTarget; b.disabled = true;
      try { await D.cambiarEstadoPulido(e.id, sig); } finally { b.disabled = false; }
    },
  }, P.etiquetaSiguiente(e.estado));
  return el('article', { class: ['u2-nota-card', `u2-nota-card--${e.severidad}`, e.estado === 'resuelta' && 'u2-nota-card--resuelta'] },
    el('div', { class: 'u2-nota-card__titulo' }, e.titulo || '(sin título)'),
    e.detalle ? el('div', { class: 'u2-nota-card__detalle' }, e.detalle) : null,
    el('div', { class: 'u2-nota-card__pie' },
      W.tagEstadoPulido(e.estado), W.tagSeveridadPulido(e.severidad), W.tagTipoPulido(e.tipo),
      e.oferta_id ? null : W.tag('General', 'info', { suave: true, icono: 'globo' }),
      el('span', { class: 'u2-tenue' }, W.cuando(e.ts)), el('span', { style: { flex: '1' } }), boton));
}

// ───────────────────────── ficha completa (mercado y brief) ─────────────────────────

function fichaCompleta(D) {
  const { cab, mercado: m } = D;
  const brief = D.datos.brief && typeof D.datos.brief === 'object' ? D.datos.brief : null;
  const mercadoJson = D.datos.mercado && typeof D.datos.mercado === 'object' ? D.datos.mercado : null;
  const pares = [
    ['Candidato elegido', cab.candidato ? [cab.candidato.candidato_id, cab.candidato.fecha ? ` · ${fmt.fecha(cab.candidato.fecha)}` : ''].join('') : null],
    ['Por qué se eligió', cab.candidato ? cab.candidato.motivo : null],
    ['Idioma', m.idioma || null],
    ['Países', m.paises.length ? m.paises.join(', ') : null],
    ['Moneda de cobro', m.moneda],
    ['Tema de partida', brief && brief.tema_semilla ? W.mayus(brief.tema_semilla) : null],
    ['Riesgo que aceptas', brief ? brief.apetito_riesgo : null],
    ['Duración de la prueba', brief && brief.ventana_test_dias != null ? `${brief.ventana_test_dias} días` : null],
  ];
  const hay = pares.some((p) => p[1] != null && p[1] !== '');
  return el('section', { class: 'u2-bloque', 'aria-labelledby': 'u2-ficha-t' },
    el('div', { class: 'u2-bloque__cab' }, el('h2', { id: 'u2-ficha-t' }, 'Ficha de la oferta'),
      ui.fuente ? ui.fuente([`ofertas/${D.id}/00-brief.yaml`, `ofertas/${D.id}/mercado.json`], {}) : null),
    el('div', { class: 'u2-pila' },
      hay ? W.kvNodo(pares) : ui.vacioConPasos({
        titulo: 'Todavía no hay ficha inicial, mercado ni candidato', explicacion: 'Esta ficha se llena cuando existen la ficha inicial (brief) que firmas, la decisión de mercado y el candidato elegido en Descubrir.', icono: 'libro',
        pasos: [{ texto: 'Escribe la ficha inicial de la oferta.' }, { texto: 'Elige el mercado y el candidato en las dos primeras etapas.' }],
      }),
      ui.detalleTecnico && (brief || mercadoJson) ? ui.detalleTecnico('Ficha inicial y mercado completos', [
        brief ? el('div', { class: 'u2-pila u2-pila--chica' }, el('h4', { class: 'u2-subtitulo' }, 'Brief'), ui.visorJson(brief, { colapsado: true, titulo: 'brief' })) : null,
        mercadoJson ? el('div', { class: 'u2-pila u2-pila--chica' }, el('h4', { class: 'u2-subtitulo' }, 'Mercado'), ui.visorJson(mercadoJson, { colapsado: true, titulo: 'mercado' })) : null,
      ].filter(Boolean)) : null));
}
