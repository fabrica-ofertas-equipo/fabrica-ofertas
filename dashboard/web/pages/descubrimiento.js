// pages/descubrimiento.js — #/descubrimiento: el radar de ofertas (barridos de la Biblioteca de anuncios).
// Render (DOM vía ctx.ui; todo texto de datos entra por textContent). La lógica pura está en ../lib/descubrimiento.js.
//
// Orden de lectura: resumen ejecutivo (qué se encontró, cuántas pasan la tracción, qué es medido y qué es muestra) → estado del
// barrido y del freno → nota de «piso» → candidatos como lista escaneable (filtros guardados, panel lateral con la evidencia) →
// páginas, mapa de calor tema × país, fichas borrador, plan y cobertura, etiquetado y memoria. Lo técnico (rutas, ids, qids,
// comandos) va en «detalle técnico».
//
// SOLO LECTURA: ningún botón ejecuta nada. Lo único «accionable» son comandos para COPIAR y correr en una terminal.
// Texto de la Biblioteca (títulos, nombres de página, frases) = dato no confiable: pasa por `neutralizar` y por `el`/textContent;
// los enlaces a Meta (ficha del anuncio, Biblioteca, página) se muestran como TEXTO (nunca un enlace) para no abrir Meta por accidente.
// ÚNICA excepción: la landing original que una persona registró (scripts.referentes.landing), https validada, con un botón explícito
// (target=_blank, rel=noopener noreferrer); nunca se abre sola.

import * as L from '../lib/descubrimiento.js';
import { CSS_COMUN, CSS_DESCUBRIMIENTO } from '../lib/estilos-u3.js';

export const meta = { ruta: 'descubrimiento', titulo: 'Radar de ofertas', grupo: 'Testeo y escala', icono: 'lupa', escucha: ['barrido'] };

let U = null;
let el; let chip; let seccion; let tabla; let tabs; let kv; let vacio; let errorBox; let comando; let reemplazar;
let fmt = null;

function usar(ctx) {
  U = ctx.ui;
  ({ el, chip, seccion, tabla, tabs, kv, vacio, errorBox, comando, reemplazar } = U);
  fmt = ctx.fmt || U.fmt;
  if (U.instalarEstilos) { U.instalarEstilos('u3-comun', CSS_COMUN); U.instalarEstilos('u3-descubrimiento', CSS_DESCUBRIMIENTO); }
}

// Estado de la vista (sobrevive a los refrescos en vivo y a re-renders)
const POR_TANDA = 30;
const CLAVE_VISTAS = 'fab.descubrimiento.vistas';
const vista = {
  corrida: null,
  tab: 'candidatos',
  filtros: { ...L.FILTROS_VACIOS },
  orden: 'defecto',
  mostrar: POR_TANDA,
  vistas: null, // vistas guardadas por el usuario (localStorage), se leen una vez
  matriz: { soloPasan: true, q: '', minPaises: 0 },
  pag: { q: '', pais: '', estado: '', pagina: 1, porPagina: 50 },
};
const cache = new Map(); // corrida → {estado, candidatos, fichas, plan, etiquetas…}
let activo = null; // {ctx, raiz, datos}
let panelActivo = null; // panel lateral abierto
let pendienteRefresco = false;
let enRefresco = false;

// ───────────────────────── lectura ─────────────────────────

/** GET con sobre completo; nunca lanza: {ok, datos, fuente, generado_en, vacio, avisos, error}. */
async function leer(ctx, ruta, params) {
  try {
    const s = await ctx.api.sobre(ruta, params);
    return { ok: true, datos: s.datos, fuente: s.fuente || [], generado_en: s.generado_en || null, vacio: s.vacio === true, avisos: s.avisos || [], error: null };
  } catch (error) {
    return { ok: false, datos: null, fuente: [], generado_en: null, vacio: false, avisos: [], error };
  }
}

const rutaCorrida = (c, parte) => `/descubrimiento/${c}/${parte}`;
const esObjetoNoVacio = (x) => x !== null && typeof x === 'object' && !(Array.isArray(x) && x.length === 0) && Object.keys(x).length > 0;

function cacheDe(c) {
  if (!cache.has(c)) cache.set(c, {});
  return cache.get(c);
}

async function cargado(ctx, c, parte) {
  const k = cacheDe(c);
  if (!k[parte]) k[parte] = await leer(ctx, rutaCorrida(c, parte));
  return k[parte];
}

// ───────────────────────── piezas de interfaz ─────────────────────────

const t = (v) => (v === null || v === undefined || v === '' ? '—' : String(v));
const ic = (nombre, tam = 16) => U.icono(nombre, { tam, tamano: tam });
const pila = (...hijos) => el('div', { class: 'u3-pila' }, ...hijos);
const sub = (texto, clase = 'u3-tenue') => el('div', { class: clase }, texto);
const tag = (texto, variante, { titulo, icono } = {}) => el('span', { class: ['u3-tag', variante && `u3-tag--${variante}`], title: titulo || null }, icono ? ic(icono, 12) : null, texto);
const tags = (items, variante) => (items.length ? el('span', { class: 'u3-tags' }, items.map((x) => tag(x, variante))) : el('span', { class: 'u3-tenue' }, '—'));

function nota(contenido, { tono = 'info', icono = 'info' } = {}) {
  return el('div', { class: ['u3-nota', tono !== 'info' && `u3-nota--${tono}`], role: tono === 'error' ? 'alert' : 'note' }, ic(icono, 18), el('div', null, contenido));
}

function etiquetaCampo(titulo, control) { return el('label', { class: 'u3-campo' }, titulo, control); }

function selector(opciones, valor, alCambiar, { etiqueta } = {}) {
  const s = el('select', { 'aria-label': etiqueta || null, onchange: (ev) => alCambiar(ev.target.value) },
    opciones.map(([v, texto]) => el('option', { value: v, selected: v === valor ? true : null }, texto)));
  s.value = valor;
  return s;
}

function pieFuente(r) {
  return U.fuente
    ? U.fuente(r.fuente || [], { leido: r.generado_en || undefined })
    : U.fuenteInfo({ fuente: r.fuente, generado_en: r.generado_en, vacio: r.vacio, avisos: r.avisos });
}

/** Detalle técnico (rutas, ids, comandos): cerrado salvo modo técnico. */
function tecnico(titulo, ...contenido) { return U.detalleTecnico(titulo, contenido.flat().filter(Boolean)); }

const ESTADO_TRACCION = {
  pasa: { texto: 'Pasa la tracción', tono: 'ok', icono: 'ok', ayuda: 'Cumple el mínimo de anuncios y de antigüedad.' },
  indeterminada_por_muestra: { texto: 'Por medir', tono: 'aviso', icono: 'reloj', ayuda: 'Por medir: lo visto no alcanza el mínimo, pero es solo una muestra.' },
  no_pasa: { texto: 'No alcanza', tono: 'neutro', icono: 'menos', ayuda: 'Medido y por debajo del mínimo.' },
};

function estadoTraccion(estado) {
  const e = ESTADO_TRACCION[estado] || { texto: 'Sin estado', tono: 'neutro', icono: 'menos', ayuda: '' };
  return el('span', { class: ['u3-estado', `u3-estado--${e.tono}`], title: e.ayuda || null }, ic(e.icono, 16), e.texto);
}

/** Barra de progreso hacia el umbral: «valor / umbral» y una barra; alcanzado = icono de check + barra verde (nunca solo color). */
function barra(etiqueta, prog, minimo) {
  return el('div', { class: ['u3-barra', prog.sinDato && 'u3-barra--sin', prog.supera && 'u3-barra--supera'], style: { '--p': `${prog.pct}%` } },
    el('div', { class: 'u3-barra__cab' },
      el('span', null, etiqueta),
      el('span', { class: 'u3-barra__valor', title: `${prog.piso ? 'Al menos esa cifra: puede ser más. ' : ''}${prog.supera ? 'Alcanza el mínimo.' : prog.sinDato ? 'Sin dato.' : 'No alcanza el mínimo con lo visto.'}` },
        prog.supera ? ic('check', 12) : null, prog.texto, el('span', { class: 'u3-barra__umbral' }, ` / ${minimo}`))),
    el('div', { class: 'u3-barra__pista', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': prog.pct, 'aria-label': `${etiqueta}: ${prog.texto} frente a un mínimo de ${minimo}` }, el('div', { class: 'u3-barra__relleno' })));
}

function numero(valor, etiqueta) { return el('div', { class: 'u3-numero' }, el('b', null, valor), el('span', null, etiqueta)); }

// ───────────────────────── render ─────────────────────────

export async function render(ctx) {
  usar(ctx);
  const raiz = el('div', { class: 'pagina' }, U.esqueleto ? U.esqueleto('pagina') : U.cargando('Leyendo el barrido…'));
  activo = { ctx, raiz };
  await reconstruir(ctx, raiz);
  const p = ctx.params || {};
  if (p.tema || p.pagina) setTimeout(() => abrirDesdeParams(ctx), 0);
  return raiz;
}

export function alSalir() {
  activo = null;
  pendienteRefresco = false;
  cerrarPanel();
}

/** Actualización en vivo (SSE `barrido`): relee y repinta SIN perder filtros ni pestaña; no interrumpe a quien está escribiendo. */
export function alCambio(ctx) {
  if (!activo) return undefined;
  const a = typeof document !== 'undefined' ? document.activeElement : null;
  if (a && activo.raiz.contains(a) && /^(INPUT|SELECT|TEXTAREA)$/.test(a.tagName)) {
    pendienteRefresco = true;
    a.addEventListener('blur', () => { if (pendienteRefresco) setTimeout(() => alCambio(ctx), 200); }, { once: true });
    return undefined;
  }
  if (enRefresco) return undefined;
  pendienteRefresco = false;
  cache.clear();
  enRefresco = true;
  reconstruir(activo.ctx, activo.raiz).catch((e) => console.error('refresco de descubrimiento falló', e)).finally(() => { enRefresco = false; });
  return undefined;
}

function cabecera(acciones) {
  return U.encabezadoPagina({
    titulo: 'Radar de ofertas',
    descripcion: 'El radar de ofertas: qué ofertas digitales de pago único se anuncian, con qué fuerza, en qué países y dónde falta el original. Aquí solo miras: no se cambia nada.',
    acciones: acciones || [],
  });
}

async function reconstruir(ctx, raiz) {
  const rc = await leer(ctx, '/descubrimiento/corridas');
  if (!rc.ok) {
    reemplazar(raiz, cabecera(), errorBox(rc.error, { reintentar: () => ctx.recargar() }));
    return;
  }
  const corridas = L.ordenarCorridas(Array.isArray(rc.datos) ? rc.datos : []);
  if (!corridas.length) {
    reemplazar(raiz, cabecera(), U.vacioConPasos({
      titulo: 'Aún no hay ninguna corrida del barrido',
      explicacion: 'El barrido recorre la Biblioteca de Anuncios de Meta con muchas búsquedas pequeñas (una frase de oferta en un país). Agentes de IA hacen las búsquedas y el sistema carga los datos, clasifica las páginas, las ordena y arma las fichas. Aquí verás el resultado en cuanto exista la primera corrida (una pasada completa del barrido).',
      pasos: [
        { texto: 'Genera el plan de la primera pasada. Este comando guarda el resultado (--escribir); sin esa opción solo simula y no guarda nada.', comando: L.comandoBarrido('plan', `${new Date().toISOString().slice(0, 10)}-a`) },
        { texto: 'Después sigue los pasos que explica el README del barrido: datos sin procesar de los agentes, carga de datos, clasificación, ranking y fichas.' },
      ],
      icono: 'lupa',
    }), pieFuente(rc));
    return;
  }
  const pedida = ctx.params && typeof ctx.params.c === 'string' ? ctx.params.c : null;
  const corrida = L.elegirCorrida(corridas, pedida || vista.corrida);
  if (vista.corrida !== corrida.corrida_id) vista.corrida = corrida.corrida_id;
  const id = corrida.corrida_id;
  if (!L.corridaValida(id)) {
    reemplazar(raiz, cabecera(), errorBox({ codigo: 'corrida_invalida', mensaje: 'El código de la corrida que llegó no tiene el formato esperado (AAAA-MM-DD-letra), así que no se usa.' }));
    return;
  }
  const [est, cand, sis] = await Promise.all([cargado(ctx, id, 'estado'), cargado(ctx, id, 'candidatos'), leer(ctx, '/sistema')]);
  const d = { corridas, corrida, id, rc, est, cand, sis, ctx };
  if (activo) activo.datos = d;
  reemplazar(raiz, ...armarPagina(ctx, d));
}

// ───────────────────────── cabecera, resumen ejecutivo, barrido y freno ─────────────────────────

function selectorCorrida(ctx, d) {
  const opciones = d.corridas.map((c) => [c.corrida_id, `${c.corrida_id}${L.esNumero(c.paginas) ? ` · ${L.num(c.paginas)} páginas` : ' · sin páginas'}${c.actualizado_en ? ` · ${fmt.relativo(c.actualizado_en)}` : ''}`]);
  return el('div', { style: { minWidth: '260px', maxWidth: '380px' } }, etiquetaCampo(el('span', null, 'Corrida ', U.ayuda ? U.ayuda('corrida') : null), selector(opciones, d.id, (v) => {
    vista.corrida = v;
    ctx.navegar(`#/descubrimiento?c=${encodeURIComponent(v)}`);
  }, { etiqueta: 'Corrida del barrido' })));
}

function armarPagina(ctx, d) {
  const sistema = d.sis.ok && d.sis.datos ? d.sis.datos : null;
  const frenoSistema = sistema ? (sistema.freno_captura === undefined ? undefined : sistema.freno_captura) : undefined;
  const estadoDatos = d.est.ok && esObjetoNoVacio(d.est.datos) ? d.est.datos : null;
  const candDatos = d.cand.ok && esObjetoNoVacio(d.cand.datos) ? d.cand.datos : null;
  const res = L.resumenCorrida({ corrida: d.corrida, candidatos: candDatos, estado: estadoDatos, freno: frenoSistema });
  const ejec = L.resumenEjecutivo({ corrida: d.corrida, candidatos: candDatos, estado: estadoDatos, freno: frenoSistema });
  d.res = res; d.ejec = ejec; d.estadoDatos = estadoDatos; d.candDatos = candDatos;

  return [
    cabecera([selectorCorrida(ctx, d)]),
    tarjetaResumen(d),
    el('div', { class: 'u3-estado-barrido' }, tarjetaBarrido(d), tarjetaFreno(ejec.freno)),
    notaPiso(d),
    montarTabs(ctx, d),
  ];
}

function tarjetaResumen(d) {
  const r = d.ejec;
  const lineas = r.lineas.filter((l) => l.id === 'vistas' || l.id === 'medido');
  const cifras = d.res.tarjetas.filter((c) => ['paginas', 'etiquetadas', 'candidatas', 'fichas'].includes(c.id));
  return el('section', { class: ['u3-tarjeta', 'u3-resumen'], 'aria-label': 'Resumen de la corrida' },
    pila(
      el('p', { class: 'u3-sobretitulo' }, 'Qué se encontró'),
      el('h2', { class: 'u3-resumen__titular' }, r.titular),
      el('p', { class: 'u3-parrafo' }, 'Mínimo exigido para la ', U.termino('traccion', { texto: 'tracción' }), `: ${r.textoUmbral} (lo fijaste tú).`)),
    lineas.length ? el('ul', { class: 'u3-resumen__lineas' }, lineas.map((l) => el('li', null, ic(l.id === 'medido' ? 'grafico' : 'lupa', 16), el('span', null, l.texto)))) : null,
    el('div', { class: 'u3-metricas' }, r.metricas.map((m) => U.metrica({ etiqueta: m.etiqueta, valor: m.valor === null ? '—' : m.valor, contexto: m.contexto, tono: m.tono, ayuda: m.ayuda }))),
    cifras.length ? el('div', { class: 'u3-cifras' }, cifras.map((c) => el('span', { title: c.detalle || null }, `${c.titulo} `, el('b', null, c.valor)))) : null);
}

const ESTADO_PASO = (p) => (p.hecho === true ? 'terminado' : 'pendiente');
const etapasBarrido = (pasos, siguiente) => pasos.map((p) => ({ id: p.id, nombre: p.corto, estado: ESTADO_PASO(p), destacada: Boolean(siguiente && p.id === siguiente.id) }));

function tarjetaBarrido(d) {
  const b = d.ejec.barrido;
  return el('section', { class: 'u3-tarjeta u3-pila', 'aria-label': 'Estado del barrido' },
    el('div', { class: 'u3-pila u3-pila--chica' }, el('p', { class: 'u3-sobretitulo' }, 'Estado del barrido'), el('h3', { class: 'u3-titulo u3-titulo--chico' }, b.texto)),
    b.conocido ? U.pasos({ etapas: etapasBarrido(b.pasos, b.siguiente), etiqueta: 'Pasos del barrido' }) : null,
    b.conocido && b.pasos.some((p) => p.detalle) ? el('div', { class: 'u3-cifras' }, b.pasos.filter((p) => p.detalle).map((p) => el('span', null, `${p.corto} `, el('b', null, p.detalle)))) : null,
    b.siguiente ? comando(b.siguiente.comando, { titulo: `Cómo seguir: ${b.siguiente.titulo}`, nota: 'Este comando guarda el resultado; sin --escribir solo simularía. Lo ejecutas tú en la Terminal.' }) : null);
}

function tarjetaFreno(f) {
  const etiqueta = !f.conocido ? 'Sin dato' : f.activo ? 'Puesto' : 'Libre';
  const icono = !f.conocido ? 'info' : f.activo ? 'candado' : 'ok';
  return el('section', { class: ['u3-tarjeta', 'u3-freno', `u3-freno--${f.tono}`], 'aria-label': 'Freno de la captura de anuncios' },
    el('div', { class: 'u3-fila' }, el('p', { class: 'u3-sobretitulo' }, 'Freno de la captura de anuncios'), U.ayuda('freno_captura')),
    el('div', { class: 'u3-freno__estado' }, ic(icono, 20), etiqueta),
    el('p', { class: 'u3-parrafo' }, f.consecuencia, ' ', U.ayuda('rutas_captura')),
    f.activo ? el('p', { class: 'u3-parrafo' }, el('strong', null, 'Motivo: '), f.motivo, f.ts ? ` (desde ${fmt.fecha(f.ts)})` : '') : null,
    f.activo ? tecnico('Cómo se levanta', el('p', { class: 'u3-parrafo' }, f.instruccion), el('p', { class: 'u3-parrafo' }, f.alcance)) : null);
}

function notaPiso(d) {
  const r = d.ejec;
  const detalles = [
    ...r.pisos.map((p) => el('p', { class: 'u3-parrafo' }, p)),
    ...r.avisos.map((a) => el('p', { class: 'u3-parrafo' }, a)),
  ];
  return pila(
    nota(el('p', null,
      el('strong', null, 'Qué cifras son «al menos». '),
      'Los números con «≥» significan ', U.termino('piso', { texto: '«al menos»' }), ': es lo que se vio en una muestra (la Biblioteca entrega como mucho 50 anuncios por consulta), así que el total real puede ser mayor. Solo lo ',
      U.termino('medido', { texto: 'medido' }), ' (pasada 3) es exacto. Una cifra «al menos» que ya supera el mínimo exigido cuenta; si no lo supera, queda «por medir» y nunca se descarta.')),
    detalles.length ? tecnico(`Advertencias del barrido (${detalles.length})`, detalles) : null);
}

function montarTabs(ctx, d) {
  const items = [
    { id: 'candidatos', titulo: 'Candidatos', render: () => tabCandidatos(ctx, d) },
    { id: 'matriz', titulo: 'Mapa tema × país', render: () => tabMatriz(ctx, d) },
    { id: 'fichas', titulo: 'Fichas en borrador', render: () => tabFichas(ctx, d) },
    { id: 'paginas', titulo: 'Páginas', render: () => tabPaginas(ctx, d) },
    { id: 'plan', titulo: 'Plan y cobertura', render: () => tabPlan(ctx, d) },
    { id: 'etiquetado', titulo: 'Clasificación y descartes', render: () => tabEtiquetado(ctx, d) },
    { id: 'memoria', titulo: 'Comparación entre corridas', render: () => tabMemoria(ctx, d) },
  ];
  const activa = items.some((i) => i.id === vista.tab) ? vista.tab : 'candidatos';
  const tb = tabs(items, activa);
  const sincronizar = () => setTimeout(() => { const a = tb.activo && tb.activo(); if (a) vista.tab = a; }, 0);
  tb.addEventListener('click', sincronizar);
  tb.addEventListener('keydown', sincronizar);
  return tb;
}

// ───────────────────────── pestaña: candidatos ─────────────────────────

function vacioCandidatos(d) {
  return pila(
    U.vacioConPasos({
      titulo: 'Esta corrida aún no tiene candidatos',
      explicacion: 'Los candidatos salen del ranking: antes hacen falta la carga de datos, la clasificación y el visto bueno firmado de las reglas. Sin eso no hay lista: nada se inventa.',
      pasos: [{ texto: 'Calcula el ranking. Este comando guarda el resultado (--escribir); sin esa opción solo simula y no guarda nada. Cambia <SELLO> y <SELLO_LIMITES> por los códigos del visto bueno firmado de las reglas y de los límites.', comando: L.comandoBarrido('rankear', d.id) }],
      icono: 'lupa',
    }));
}

function leerVistas() {
  if (vista.vistas) return vista.vistas;
  let crudo = [];
  try { crudo = JSON.parse(globalThis.localStorage.getItem(CLAVE_VISTAS) || '[]'); } catch (_) { crudo = []; }
  vista.vistas = L.normalizarVistas(crudo);
  return vista.vistas;
}

function guardarVistas(lista) {
  vista.vistas = lista;
  try { globalThis.localStorage.setItem(CLAVE_VISTAS, JSON.stringify(lista)); } catch (_) { /* sin almacenamiento: la vista vive solo en esta sesión */ }
}

/** Fila rica de un candidato (tema o página sin tema). */
function filaCandidata(fila, umbral, alAbrir, posicion) {
  const pa = L.progresoUmbral(fila.anuncios, umbral.anuncios, { piso: fila.anunciosEsPiso });
  const pe = L.progresoUmbral(fila.edad, umbral.edad, { piso: fila.edadEsPiso, unidad: 'd' });
  const paises = fila.paises.slice(0, 8);
  const ex = fila.exportador;
  const abrir = (ev) => { if (ev.type === 'keydown' && ev.key !== 'Enter' && ev.key !== ' ') return; ev.preventDefault(); alAbrir(fila, ev.currentTarget); };
  return el('div', {
    class: ['u3-cand', fila.estado === 'pasa' && 'u3-cand--pasa'], role: 'button', tabindex: '0', 'data-id': fila.id,
    'aria-label': `Abrir el detalle de ${fila.nombre}`, onclick: abrir, onkeydown: abrir,
  },
  el('div', { class: 'u3-cand__rank', title: `Posición en esta lista (en el ranking del barrido: ${fila.tipo === 'sin_tema' ? 's' : '#'}${fila.rank})` }, String(posicion)),
  el('div', { class: 'u3-cand__principal' },
    el('div', null,
      el('h3', { class: 'u3-cand__tema' }, fila.nombre),
      fila.tipo === 'sin_tema' ? el('div', { class: 'u3-cand__sub' }, 'Página cuyo tema la IA no pudo determinar') : (fila.publicos[0] ? el('div', { class: 'u3-cand__sub' }, fila.publicos[0]) : null)),
    el('div', { class: 'u3-tags' },
      fila.tipo === 'sin_tema' ? tag('Sin tema', 'hipotesis', { titulo: 'Cada página sin tema es su propio candidato' }) : null,
      fila.macro ? tag(fila.macro, 'acento', { titulo: 'Categoría general (macro-nicho): solo una etiqueta, no descarta nada' }) : null,
      paises.map((p) => tag(p, 'mono', { titulo: `Visto en ${p}` })),
      fila.paises.length > paises.length ? tag(`+${fila.paises.length - paises.length}`, null, { titulo: fila.paises.slice(8).join(' ') }) : null,
      ex.hay ? tag(`Exportador · ${ex.monedas.join(' ')}${ex.paisesAnuncio.length ? ` → ${ex.paisesAnuncio.join(' ')}` : ''}`, 'info', { icono: 'globo', titulo: 'Indicio (moneda de un país que anuncia en otro idioma): no es un hecho ni entra en la tracción.' }) : null)),
  el('div', { class: 'u3-cand__nums' },
    el('div', { class: 'u3-cand__indep', title: 'Anunciantes independientes: no cuenta páginas que parecen del mismo operador' }, el('b', null, L.num(fila.anunciantes)), el('span', null, fila.anunciantes === 1 ? 'anunciante independiente' : 'anunciantes independientes')),
    barra('Anuncios', pa, L.num(umbral.anuncios)),
    barra('Edad', pe, `${L.num(umbral.edad)} d`)),
  el('div', { class: 'u3-cand__estado' },
    estadoTraccion(fila.estado),
    el('p', { class: 'u3-cand__explicacion' }, fila.explicacion),
    fila.porVerificarTexto.length ? el('div', { class: 'u3-tags', title: 'Avanza igual, pero hay que mirarlo antes de lanzar' }, fila.porVerificarTexto.map((x) => tag(x, 'aviso', { icono: 'alerta' }))) : null));
}

function tabCandidatos(ctx, d) {
  if (!d.candDatos) return d.cand.ok ? vacioCandidatos(d) : errorBox(d.cand.error, { reintentar: () => ctx.recargar() });
  const base = [...L.filasTemas(d.candDatos), ...L.filasSinTema(d.candDatos)];
  const filas = L.ordenarPorDefecto(base);
  const opciones = L.opcionesFiltro(filas);
  const f = vista.filtros;
  const umbral = d.res.umbral;
  const ctrl = {};

  const conteo = el('span', { class: 'u3-tenue u3-peq', 'aria-live': 'polite' });
  const lista = el('div', { class: 'u3-cands', role: 'list', 'aria-label': 'Candidatos del barrido' });
  const filasVistas = el('div', { class: 'u3-fila' });
  const resumenFiltros = el('span', { class: 'u3-tenue u3-peq' });

  const visibles = () => {
    const vis = L.filtrarFilas(filas, {
      q: f.q, estado: f.estado, macro: f.macro, pais: f.pais, paisModo: f.paisModo,
      exportador: f.exportador ? true : undefined, verificar: f.verificar === 'con' ? true : f.verificar === 'sin' ? false : undefined, tipo: f.tipo,
    });
    return vista.orden === 'defecto' ? vis : L.ordenarFilas(vis, { clave: vista.orden });
  };

  const pintarLista = () => {
    const vis = visibles();
    const tope = Math.min(vis.length, vista.mostrar);
    conteo.textContent = `${L.num(vis.length)} de ${L.num(filas.length)} candidatos (${L.num(filas.filter((r) => r.tipo === 'tema').length)} temas + ${L.num(filas.filter((r) => r.tipo === 'sin_tema').length)} páginas sin tema)`;
    const n = L.filtrosActivos(f);
    resumenFiltros.textContent = n ? `${n} filtro${n === 1 ? '' : 's'} activo${n === 1 ? '' : 's'}` : '';
    const hijos = vis.slice(0, tope).map((fila, i) => filaCandidata(fila, umbral, (x, nodo) => abrirDetalle(ctx, d, x, undefined, nodo), i + 1));
    if (!vis.length) hijos.push(vacio('Ningún candidato coincide con los filtros.', { pista: 'Prueba otra vista o limpia los filtros.', icono: 'filtro' }));
    if (vis.length > tope) {
      hijos.push(el('div', { class: 'u3-mas' }, el('button', { type: 'button', class: 'btn', onclick: () => { vista.mostrar += POR_TANDA; pintarLista(); } }, `Mostrar ${L.num(Math.min(POR_TANDA, vis.length - tope))} más · ${L.num(vis.length - tope)} sin mostrar`)));
    }
    reemplazar(lista, ...hijos);
  };

  const sincronizar = () => {
    ctrl.q.value = f.q; ctrl.estado.value = f.estado; ctrl.macro.value = f.macro; ctrl.pais.value = f.pais;
    ctrl.paisModo.value = f.paisModo; ctrl.verificar.value = f.verificar; ctrl.tipo.value = f.tipo; ctrl.exportador.checked = !!f.exportador;
  };

  const aplicarVista = (v) => {
    Object.assign(f, L.FILTROS_VACIOS, L.normalizarFiltros(v.filtros));
    vista.mostrar = POR_TANDA;
    sincronizar(); pintarVistas(); pintarLista();
  };

  let formulario = null;
  function pintarVistas() {
    const propias = leerVistas();
    const chipVista = (v, propia) => el('span', { class: 'u3-fila', style: { gap: '0' } },
      el('button', { type: 'button', class: 'u3-vista', 'aria-pressed': L.mismosFiltros(f, v.filtros) ? 'true' : 'false', title: propia ? 'Vista guardada por ti' : null, onclick: () => aplicarVista(v) }, v.titulo,
        propia ? el('span', {
          class: 'u3-vista__quitar', role: 'button', tabindex: '0', 'aria-label': `Quitar la vista ${v.titulo}`, title: 'Quitar esta vista',
          onclick: (ev) => { ev.stopPropagation(); guardarVistas(L.quitarVista(vista.vistas, v.id)); pintarVistas(); },
          onkeydown: (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); ev.stopPropagation(); guardarVistas(L.quitarVista(vista.vistas, v.id)); pintarVistas(); } },
        }, ic('cerrar', 12)) : null));
    reemplazar(filasVistas,
      el('span', { class: 'u3-sobretitulo' }, 'Vistas'),
      L.VISTAS_BASE.map((v) => chipVista(v, false)),
      propias.map((v) => chipVista(v, true)),
      el('button', { type: 'button', class: 'btn btn--chico', onclick: () => { formulario.hidden = false; ctrl.nombreVista.focus(); } }, ic('mas', 14), 'Guardar esta vista'));
  }

  const guardar = () => {
    const nombre = ctrl.nombreVista.value;
    if (!L.neutralizar(nombre)) return;
    guardarVistas(L.agregarVista(leerVistas(), nombre, f));
    ctrl.nombreVista.value = '';
    formulario.hidden = true;
    pintarVistas();
  };
  ctrl.nombreVista = el('input', { type: 'text', maxlength: 40, placeholder: 'Nombre de la vista', 'aria-label': 'Nombre de la vista', onkeydown: (ev) => { if (ev.key === 'Enter') { ev.preventDefault(); guardar(); } if (ev.key === 'Escape') formulario.hidden = true; } });
  formulario = el('div', { class: 'u3-fila', hidden: true }, etiquetaCampo('Nombre', ctrl.nombreVista), el('button', { type: 'button', class: 'btn btn--chico', onclick: guardar }, 'Guardar'), el('button', { type: 'button', class: 'btn btn--chico', onclick: () => { formulario.hidden = true; } }, 'Cancelar'));

  let reloj = null;
  const cambio = (campo, valor) => { f[campo] = valor; vista.mostrar = POR_TANDA; pintarVistas(); pintarLista(); };
  ctrl.q = el('input', { type: 'search', placeholder: 'Buscar tema o página…', 'aria-label': 'Buscar tema o página', value: f.q, oninput: (ev) => { f.q = ev.target.value; clearTimeout(reloj); reloj = setTimeout(() => { vista.mostrar = POR_TANDA; pintarVistas(); pintarLista(); }, 150); } });
  ctrl.estado = selector([['', 'Todas'], ['pasa', 'Pasa la tracción'], ['indeterminada_por_muestra', 'Por medir'], ['no_pasa', 'No alcanza']], f.estado, (v) => cambio('estado', v), { etiqueta: 'Estado de tracción' });
  ctrl.tipo = selector([['', 'Todos'], ['tema', 'Temas'], ['sin_tema', 'Páginas sin tema']], f.tipo, (v) => cambio('tipo', v), { etiqueta: 'Tipo de candidato' });
  ctrl.macro = selector([['', 'Todos'], ...opciones.macros.map((m) => [m, m]), ['ninguno', 'fuera de marco']], f.macro, (v) => cambio('macro', v), { etiqueta: 'Categoría general' });
  ctrl.pais = selector([['', 'Todos'], ...opciones.paises.map((p) => [p, p])], f.pais, (v) => cambio('pais', v), { etiqueta: 'País' });
  ctrl.paisModo = selector([['presente', 'presente'], ['hueco', 'hueco (hipótesis)']], f.paisModo, (v) => cambio('paisModo', v), { etiqueta: 'Presencia en el país' });
  ctrl.verificar = selector([['', 'Todos'], ['con', 'Con pendientes'], ['sin', 'Sin pendientes']], f.verificar, (v) => cambio('verificar', v), { etiqueta: 'Por verificar' });
  ctrl.exportador = el('input', { type: 'checkbox', checked: f.exportador ? true : null, onchange: (ev) => cambio('exportador', ev.target.checked) });
  ctrl.orden = selector([['defecto', 'Recomendado (pasan primero)'], ...L.ORDENES.map((o) => [o.clave, o.titulo])], vista.orden, (v) => { vista.orden = v; vista.mostrar = POR_TANDA; pintarLista(); }, { etiqueta: 'Ordenar por' });

  const filtros = el('details', { class: 'u3-detalles' },
    el('summary', null, 'Más filtros ', resumenFiltros),
    el('div', { class: 'u3-filtros', style: { paddingTop: '8px' } },
      etiquetaCampo('Estado de tracción', ctrl.estado), etiquetaCampo('Tipo', ctrl.tipo), etiquetaCampo('Categoría general (macro-nicho)', ctrl.macro),
      etiquetaCampo('País', ctrl.pais), etiquetaCampo('Con el país…', ctrl.paisModo), etiquetaCampo('Por verificar', ctrl.verificar),
      el('label', { class: 'u3-interruptor' }, ctrl.exportador, 'Solo con indicio de exportador'),
      el('button', { type: 'button', class: 'btn btn--chico', onclick: () => aplicarVista({ filtros: {} }) }, 'Limpiar filtros')));
  if (L.filtrosActivos(f) > 0 && !L.VISTAS_BASE.concat(leerVistas()).some((v) => L.mismosFiltros(f, v.filtros))) filtros.open = true;

  pintarVistas();
  pintarLista();

  const ex = L.modeloExportadores(d.candDatos);
  return pila(
    el('div', { class: 'u3-tarjeta u3-pila u3-pila--chica' },
      filasVistas, formulario,
      el('div', { class: 'u3-fila u3-fila--entre' },
        el('div', { class: 'u3-fila', style: { flex: '1 1 320px' } }, el('div', { style: { flex: '1 1 220px' } }, etiquetaCampo('Buscar', ctrl.q)), el('div', { style: { flex: '0 1 260px' } }, etiquetaCampo('Ordenar por', ctrl.orden))),
        conteo),
      filtros),
    lista,
    nota(el('p', null, 'Haz clic en un candidato para ver su detalle en el panel lateral: países, medición por página, títulos de los anuncios y señales de riesgo. «≥» significa «al menos» (', U.termino('piso', { texto: 'qué quiere decir' }), ').'), { tono: 'neutra', icono: 'info' }),
    ex ? bloqueExportadores(ex) : null,
    pieFuente(d.cand));
}

function bloqueExportadores(ex) {
  return seccion('Probables exportadores (indicio)', pila(
    el('p', { class: 'u3-parrafo' }, ex.advertencia),
    el('div', { class: 'u3-metricas' },
      U.metrica({ etiqueta: 'Páginas evaluadas', valor: L.num(ex.evaluadas) }),
      U.metrica({ etiqueta: 'Con indicio', valor: L.num(ex.conSenal), contexto: `${L.num(ex.temasConSenal)} temas`, ayuda: 'exportador' }),
      U.metrica({ etiqueta: 'Sin dato', valor: L.num(ex.sinDato), contexto: 'no se pudo evaluar' })),
    ex.monedas.length ? el('div', { class: 'u3-tags' }, ex.monedas.map((m) => tag(`${m.moneda} × ${m.n}`, 'info'))) : null));
}

// ───────────────────────── panel lateral (detalle) ─────────────────────────

function cerrarPanel() {
  if (panelActivo) { const p = panelActivo; panelActivo = null; p.cerrar(); }
}

/** Panel lateral accesible (no es un modal gigante): Escape y clic fuera lo cierran; devuelve el contenedor del cuerpo. */
function abrirPanel({ titulo, subtitulo, alCerrar, origen }) {
  cerrarPanel();
  const foco = origen || (typeof document !== 'undefined' ? document.activeElement : null);
  const fondo = el('div', { class: 'u3-panel-fondo', onclick: () => cerrar() });
  const cuerpo = el('div', { class: 'u3-panel__cuerpo' });
  const h = el('h2', { id: 'u3-panel-titulo' }, titulo);
  const subEl = el('div', { class: 'u3-tenue u3-peq' }, subtitulo || '');
  const volver = el('button', { type: 'button', class: 'btn btn--chico u3-atras', hidden: true }, ic('flecha', 14), 'Volver al tema');
  const botonCerrar = el('button', { type: 'button', class: 'btn btn--chico', 'aria-label': 'Cerrar el panel', onclick: () => cerrar() }, ic('cerrar', 16));
  const aside = el('aside', { class: 'u3-panel', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': 'u3-panel-titulo' },
    el('header', { class: 'u3-panel__cab' }, el('div', { class: 'u3-panel__titulos' }, volver, h, subEl), botonCerrar), cuerpo);
  document.body.append(fondo, aside);
  const tecla = (ev) => {
    if (ev.key === 'Escape') { ev.preventDefault(); cerrar(); return; }
    if (ev.key !== 'Tab') return;
    const foco2 = [...aside.querySelectorAll('button, [href], input, select, [tabindex]:not([tabindex="-1"])')].filter((x) => !x.hidden && !x.disabled);
    if (!foco2.length) return;
    const primero = foco2[0]; const ultimo = foco2[foco2.length - 1];
    if (ev.shiftKey && document.activeElement === primero) { ev.preventDefault(); ultimo.focus(); } else if (!ev.shiftKey && document.activeElement === ultimo) { ev.preventDefault(); primero.focus(); }
  };
  document.addEventListener('keydown', tecla);
  let cerrado = false;
  function cerrar() {
    if (cerrado) return;
    cerrado = true;
    document.removeEventListener('keydown', tecla);
    fondo.remove(); aside.remove();
    if (panelActivo && panelActivo.aside === aside) panelActivo = null;
    if (alCerrar) alCerrar();
    if (foco && foco.isConnected && foco.focus) { try { foco.focus(); } catch (_) { /* sin foco */ } }
  }
  botonCerrar.focus();
  const api = {
    aside, cuerpo, cerrar,
    poner({ titulo: tt, subtitulo: ss, atras }) {
      h.textContent = U.neutralizarTexto(tt); subEl.textContent = U.neutralizarTexto(ss || '');
      volver.hidden = !atras; volver.onclick = atras || null;
    },
  };
  panelActivo = api;
  return api;
}

function abrirDetalle(ctx, d, fila, paginaId, origen) {
  const marcar = (nodo, v) => { if (nodo && nodo.setAttribute) { if (v) nodo.setAttribute('aria-selected', 'true'); else nodo.removeAttribute('aria-selected'); } };
  marcar(origen, true);
  const panel = abrirPanel({ titulo: fila.nombre, subtitulo: fila.tipo === 'sin_tema' ? 'Página sin tema' : 'Tema', origen, alCerrar: () => marcar(origen, false) });
  if (fila.tipo === 'sin_tema') { mostrarPagina(ctx, d, panel, fila.raw, null); return; }
  if (paginaId) {
    const p = (fila.raw.paginas || []).find((x) => String(x.page_id) === String(paginaId));
    if (p) { mostrarPagina(ctx, d, panel, p, () => mostrarTema(ctx, d, panel, fila)); return; }
  }
  mostrarTema(ctx, d, panel, fila);
}

function abrirDesdeParams(ctx) {
  if (!activo || !activo.raiz.isConnected) return;
  const d = activo.datos;
  if (!d || !d.candDatos) return;
  const p = ctx.params || {};
  const filas = [...L.filasTemas(d.candDatos), ...L.filasSinTema(d.candDatos)];
  if (typeof p.tema === 'string') {
    const f = filas.find((x) => x.tipo === 'tema' && x.id === p.tema);
    if (f) abrirDetalle(ctx, d, f, typeof p.pagina === 'string' ? p.pagina : undefined);
  } else if (typeof p.pagina === 'string') {
    const f = filas.find((x) => x.tipo === 'sin_tema' && x.id === p.pagina);
    if (f) abrirDetalle(ctx, d, f);
    else {
      const ind = L.indexarCandidatas(d.candDatos).get(p.pagina);
      const tema = ind && ind.temaSlug ? filas.find((x) => x.tipo === 'tema' && x.id === ind.temaSlug) : null;
      if (tema) abrirDetalle(ctx, d, tema, p.pagina);
    }
  }
}

const secc = (titulo, ...contenido) => el('section', { class: 'u3-panel__secc' }, el('h3', null, titulo), ...contenido);

function mostrarTema(ctx, d, panel, fila) {
  const umbral = d.res.umbral;
  const det = L.detalleTema(fila, umbral);
  const pa = L.progresoUmbral(fila.anuncios, umbral.anuncios, { piso: fila.anunciosEsPiso });
  const pe = L.progresoUmbral(fila.edad, umbral.edad, { piso: fila.edadEsPiso, unidad: 'd' });
  const pags = (fila.raw.paginas || []).map((p) => L.filaPaginaDeTema(p, umbral));
  const ex = fila.exportador;
  panel.poner({ titulo: fila.nombre, subtitulo: fila.publicos.length ? fila.publicos.join(' · ') : 'Tema del barrido' });
  reemplazar(panel.cuerpo,
    el('div', { class: 'u3-pila u3-pila--chica' },
      el('div', { class: 'u3-fila' }, estadoTraccion(fila.estado), fila.macro ? tag(fila.macro, 'acento') : tag('fuera de marco', 'hipotesis', { titulo: 'Fuera de las categorías en las que trabaja la fábrica (salud, relaciones o dinero)' }), ex.hay ? tag('Exportador (indicio)', 'info', { icono: 'globo' }) : null),
      el('p', { class: 'u3-parrafo' }, fila.explicacion)),
    secc('Fuerza del tema', el('div', { class: 'u3-panel__nums' },
      numero(L.num(fila.anunciantes), fila.anunciantes === 1 ? 'anunciante independiente' : 'anunciantes independientes'),
      numero(L.num(fila.paginas), fila.paginas === 1 ? 'página' : 'páginas'),
      numero(L.num(fila.paises.length), fila.paises.length === 1 ? 'país con presencia' : 'países con presencia')),
    barra('Anuncios activos', pa, L.num(umbral.anuncios)), barra('Edad de la oferta', pe, `${L.num(umbral.edad)} d`)),
    secc('Dónde se anuncia', tags(fila.paises, 'mono'),
      fila.huecos.length ? el('div', { class: 'u3-pila u3-pila--chica' }, el('div', { class: 'u3-tenue u3-peq' }, 'Sin presencia en la muestra (una hipótesis hasta medirla con la pasada 3):'), el('div', { class: 'u3-tags' }, fila.huecos.map((p) => tag(p, 'hipotesis')))) : null),
    fila.porVerificarTexto.length ? secc('Qué falta confirmar', el('ul', { class: 'u3-bloqueos' }, fila.porVerificarTexto.map((x) => el('li', null, ic('alerta', 16), x))),
      el('div', { class: 'u3-tenue u3-peq' }, `${t(fila.paginasPorVerificar)} de ${t(fila.paginas)} páginas con pendientes. Mientras se descubre, un «no sé» no descarta la oferta; antes de lanzar sí la frena.`)) : null,
    ex.hay ? secc('Indicio de exportador', el('p', { class: 'u3-parrafo' }, `${ex.conSenal} de ${ex.evaluadas} páginas anuncian en un país con la moneda de otro: ${ex.texto}. Es un indicio, no un hecho.`)) : null,
    secc(`Páginas del tema (${pags.length})`, pags.length
      ? el('div', { class: 'u3-pila u3-pila--chica' }, pags.map((p) => el('button', { type: 'button', class: 'u3-pag', onclick: () => mostrarPagina(ctx, d, panel, p.raw, () => mostrarTema(ctx, d, panel, fila)) },
        el('span', { class: 'u3-pag__nombre' }, p.nombre), estadoTraccion(p.estado),
        el('span', { class: 'u3-pag__meta' }, `${L.conPiso(p.anuncios, p.anunciosEsPiso)} anuncios · ${L.diasTexto(p.edad, p.edadEsPiso)} · ${p.paises.join(' ') || 'sin país'} · medición ${L.textoMedicion(p.medicion).texto}`))))
      : el('p', { class: 'u3-tenue' }, 'Este tema no trae páginas en el ranking.')),
    tecnico('Detalle técnico del tema',
      kv([
        ['Identificador del tema', el('code', null, det.slug)],
        ['Posición en el ranking del barrido', `${fila.tipo === 'sin_tema' ? 's' : '#'}${fila.rank}`],
        ['Formatos', Object.entries(fila.formatos).map(([k, n]) => `${L.neutralizar(k, { max: 30 })}×${n}`).join(' · ') || null],
        ['Posible mismo operador', fila.mismoOperador ? `${fila.mismoOperador} página(s)` : 'no'],
        ['Anunciantes nuevos en 30 días', (det.kv.find((x) => x[0] === 'Anunciantes nuevos en 30 días') || [])[1] || null],
        ['Categoría general: conteo por etiqueta', fila.macroConteo ? Object.entries(fila.macroConteo).map(([k, n]) => `${k} ${n}`).join(' · ') : null],
        ['Fuente', el('code', null, `empresa/barrido/candidatos/${d.id}.json`)],
      ])));
}

async function mostrarPagina(ctx, d, panel, pagRaw, volver) {
  panel.poner({ titulo: L.neutralizar(pagRaw.page_name, { max: 120 }) || `Página ${L.neutralizar(pagRaw.page_id, { max: 30 })}`, subtitulo: 'Página de anunciante', atras: volver });
  reemplazar(panel.cuerpo, U.esqueleto ? U.esqueleto('texto') : U.cargando('Leyendo la página…'));
  const pid = String(pagRaw.page_id ?? '');
  const [busq, etiq] = await Promise.all([buscarPagina(ctx, d.id, pid, typeof pagRaw.page_name === 'string' ? pagRaw.page_name : ''), cargarEtiquetas(ctx, d.id)]);
  if (panelActivo !== panel) return;
  const etiqueta = etiq.indice ? etiq.indice.get(pid) || null : null;
  const det = L.detallePagina({ candidata: pagRaw, pagina: busq.pagina, etiqueta, corrida: d.id, umbral: d.res.umbral });
  const avisos = [];
  if (busq.error) avisos.push(`No se pudieron leer los datos cargados de las páginas: ${busq.error.mensaje || busq.error.message}`);
  panel.poner({ titulo: det.nombre || `Página ${det.id}`, subtitulo: 'Página de anunciante', atras: volver });
  reemplazar(panel.cuerpo, ...cuerpoPagina(ctx, panel, d, det, avisos));
}

/** Pide al servidor los enlaces y la landing registrada de la página y los pinta en `zona` (si el panel sigue abierto en esa página). */
async function cargarReferente(ctx, panel, corrida, pageId, zona) {
  const r = await leer(ctx, `${rutaCorrida(corrida, 'referente')}/${encodeURIComponent(pageId)}`);
  if (panelActivo !== panel || !zona.isConnected) return;
  if (!r.ok) {
    reemplazar(zona, nota(el('p', null, `No se pudo consultar la landing original: ${(r.error && (r.error.mensaje || r.error.message)) || 'error desconocido'}`), { tono: 'aviso', icono: 'alerta' }));
    return;
  }
  const ref = L.normalizarReferente(r.datos);
  if (!ref) { reemplazar(zona, el('p', { class: 'u3-tenue' }, 'No hay datos de la landing original de esta página.')); return; }
  const piezas = [];
  for (const a of r.avisos || []) piezas.push(nota(el('p', null, a), { tono: 'aviso', icono: 'alerta' }));
  if (ref.landing) {
    const l = ref.landing;
    piezas.push(el('div', { class: 'u3-fila' },
      el('a', { class: 'btn btn--primario', href: l.url, target: '_blank', rel: 'noopener noreferrer', 'aria-label': `Abrir la landing original en ${l.dominio} (se abre en otra pestaña)` }, ic('globo', 16), 'Abrir la landing original'),
      tag(l.dominio, 'mono', { titulo: 'Dominio de la landing, tal como lo ve el navegador' })));
    piezas.push(el('div', { class: 'u3-tenue u3-peq' }, `Registrada ${l.registradaEn ? `el ${l.registradaEn.slice(0, 10)}` : 'sin fecha'}${l.ofertaId ? ` · la modela la oferta ${l.ofertaId}` : ''}. Se abre en otra pestaña: es la página real del anunciante, no la nuestra.`));
    if (l.nota) piezas.push(el('p', { class: 'u3-parrafo' }, l.nota));
    if (l.copiaLocal) piezas.push(kv([['Copia guardada del HTML (para analizar)', el('code', null, l.copiaLocal)]]));
  } else {
    piezas.push(nota(el('div', null,
      el('p', null, el('strong', null, 'Todavía no está registrada la landing de esta página.')),
      el('p', null, 'El barrido de la Biblioteca de Anuncios no trae esa dirección (solo guarda el anuncio, no a dónde lleva el botón). Se encuentra una vez y queda guardada aquí para siempre:'),
      el('ol', { class: 'u3-titulos' },
        el('li', null, '1. Abre un anuncio de esta página: copia una de las fichas de abajo y pégala en el navegador (o busca la página en la Biblioteca de Anuncios).'),
        el('li', null, '2. Haz clic en el botón del anuncio («Scopri di più», «Zobacz więcej»…): se abre la landing. Copia su dirección de la barra del navegador.'),
        el('li', null, '3. Pásasela a Claude («esta es la landing de la página …: …») o corre el comando de abajo. Al refrescar, aparece el botón «Abrir la landing original».'))),
    { tono: 'info', icono: 'info' }));
    piezas.push(comando(ref.comando || 'python -m scripts.referentes.landing registrar <id> "<URL>" --escribir', { titulo: 'Comando para registrar la landing (copiar)' }));
  }
  if (ref.anuncios.length || ref.meta.biblioteca || ref.meta.pagina) {
    const enlaces = [];
    ref.anuncios.forEach((a, i) => enlaces.push(comando(a.ficha, { titulo: `Ficha del anuncio ${i + 1}${a.inicio ? ` · desde ${a.inicio}` : ''}${a.titulo ? ` · «${a.titulo}»` : ''}`, etiqueta: 'Copiar la dirección' })));
    if (ref.meta.biblioteca) enlaces.push(comando(ref.meta.biblioteca, { titulo: 'Todos los anuncios activos de esta página (Biblioteca de Anuncios)', etiqueta: 'Copiar la dirección' }));
    if (ref.meta.pagina) enlaces.push(comando(ref.meta.pagina, { titulo: 'La página en Facebook', etiqueta: 'Copiar la dirección' }));
    piezas.push(el('div', { class: 'u3-pila u3-pila--chica' }, el('div', { class: 'u3-tenue u3-peq' }, 'Direcciones de Meta (solo texto: cópialas y pégalas tú; el panel nunca abre Meta por su cuenta):'), ...enlaces));
  }
  reemplazar(zona, ...piezas);
}

async function buscarPagina(ctx, corrida, pageId, nombre) {
  let error = null;
  for (const q of [pageId, nombre]) {
    if (!q) continue;
    const r = await leer(ctx, rutaCorrida(corrida, 'paginas'), { q, por_pagina: q === pageId ? 5 : 100, pagina: 1 });
    if (!r.ok) { error = r.error; break; }
    const hit = L.normalizarPaginado(r.datos).filas.find((p) => String(p.page_id) === String(pageId));
    if (hit) return { pagina: hit, error: null };
  }
  return { pagina: null, error };
}

async function cargarEtiquetas(ctx, corrida) {
  const k = cacheDe(corrida);
  if (!k.etiquetas) {
    const r = await leer(ctx, rutaCorrida(corrida, 'etiquetas'));
    k.etiquetas = { ...r, indice: r.ok && r.datos ? L.indexarEtiquetas(r.datos) : null };
  }
  return k.etiquetas;
}

function cuerpoPagina(ctx, panel, d, det, avisos) {
  const umbral = d.res.umbral;
  const piso = det.anunciosEsPiso;
  const pa = L.progresoUmbral(det.anunciosMedidos, umbral.anuncios, { piso });
  const pe = L.progresoUmbral(det.edad, umbral.edad, { piso: det.edadEsPiso, unidad: 'd' });
  const out = [];
  out.push(el('div', { class: 'u3-pila u3-pila--chica' },
    el('div', { class: 'u3-fila' },
      det.estadoTraccion ? estadoTraccion(det.estadoTraccion.estado) : null,
      det.medicionEstado ? el('span', { title: det.medicionTexto.ayuda }, tag(`medición ${det.medicionTexto.texto}`, det.medicionTexto.tono === 'ok' ? 'ok' : 'aviso')) : null,
      det.exportador && det.exportador.hay ? tag(`Exportador (indicio) · ${det.exportador.texto}`, 'info', { icono: 'globo' }) : null),
    det.estadoTraccion ? el('p', { class: 'u3-parrafo' }, det.estadoTraccion.explicacion) : null));
  for (const n of [...avisos, ...det.notas]) out.push(nota(el('p', null, n), { tono: 'aviso', icono: 'alerta' }));

  // Landing original: lo primero que se quiere ver de una oferta que ya vende. Se rellena apenas responde el servidor.
  const zonaLanding = el('div', { class: 'u3-pila u3-pila--chica' }, U.cargando ? U.cargando('Buscando la landing original…') : null);
  out.push(secc('Landing original', zonaLanding));
  if (det.id) cargarReferente(ctx, panel, d.id, det.id, zonaLanding);

  out.push(secc('Fuerza de la página', el('div', { class: 'u3-panel__nums' },
    numero(det.anunciosMedidos === null ? '—' : L.conPiso(det.anunciosMedidos, piso), piso ? 'anuncios (al menos: puede ser más)' : 'anuncios (exacto)'),
    numero(det.anunciosEnMuestra === null ? '—' : L.num(det.anunciosEnMuestra), 'vistos en la muestra'),
    numero(det.conceptos === null ? '—' : L.num(det.conceptos), 'conceptos distintos')),
  barra('Anuncios activos', pa, L.num(umbral.anuncios)), barra('Edad de la oferta', pe, `${L.num(umbral.edad)} d`),
  el('div', { class: 'u3-tenue u3-peq' }, `Edad ${L.diasTexto(det.edad, det.edadEsPiso)}${det.edadMax !== null ? ` · anuncio más viejo visto ${L.diasTexto(det.edadMax, det.edadEsPiso)}` : ''}${det.edadEsPiso ? ' (al menos)' : ''}.`)));

  out.push(secc('Dónde se anuncia', tags(det.paises, 'mono'),
    det.monedas.length ? el('div', { class: 'u3-tenue u3-peq' }, `Monedas de los anuncios: ${det.monedas.join(', ')}`) : null,
    det.ausenciaMedida.length ? el('div', { class: 'u3-tenue u3-peq' }, `Ausencia medida (la pasada 3 la comprobó) en: ${det.ausenciaMedida.join(', ')}`) : null));

  out.push(secc('Medición por país: «al menos» o medida', det.porPais.length
    ? tabla({
      etiqueta: 'Medición por país', maxFilas: 30, filas: det.porPais,
      columnas: [
        { clave: 'pais', titulo: 'País', ancho: '70px' },
        { clave: 'vistos', titulo: 'Vistos', alinear: 'der', formato: (v) => L.num(v) },
        { clave: 'total', titulo: 'Declarado', alinear: 'der', formato: (v) => (v === null ? el('span', { class: 'u3-tenue', title: 'la herramienta de consulta no declaró un total: buscar por frases nunca prueba que no haya más' }, 'desconocido') : L.num(v)) },
        { clave: 'lectura', titulo: 'Lectura', clase: 'cel-larga', formato: (v, r) => el('span', null, tag(r.completa ? 'exacto' : 'al menos', r.completa ? 'ok' : 'aviso'), ' ', v) },
      ],
    })
    : el('p', { class: 'u3-tenue' }, 'Sin detalle por país (no se pudieron leer los datos cargados de esta página).')));

  if (det.etiqueta) {
    out.push(secc('Qué dice la IA de esta página', kv([
      ['Tema', `${det.etiqueta.tema}`], ['Público', det.etiqueta.publico], ['Formato', det.etiqueta.formato],
      ['Categoría general (macro-nicho)', `${det.etiqueta.macro || 'fuera de marco'}${det.etiqueta.macroMotivo ? ` — ${det.etiqueta.macroMotivo}` : ''}`],
      ['Cómo cobra (modelo de cobro)', det.etiqueta.modeloCobro], ['Confianza', det.etiqueta.confianza !== null ? String(det.etiqueta.confianza).replace('.', ',') : null],
    ])));
  }

  if (det.porVerificar.length) {
    out.push(secc('Qué falta confirmar', el('div', { class: 'u3-tags' }, det.porVerificar.map((x) => tag(L.porVerificarHumano(x), 'aviso', { icono: 'alerta' })))));
  }
  if (det.mismoOperador) out.push(nota(el('p', null, 'Esta página tiene títulos idénticos a los de otra: podría ser del mismo operador y cuenta una sola vez como anunciante independiente.'), { tono: 'neutra' }));

  out.push(secc('Señales de riesgo en los títulos', det.senalesRiesgo.length || det.avisosEtiqueta.length
    ? pila(tags(det.senalesRiesgo, 'aviso'), ...det.avisosEtiqueta.map((a) => el('p', { class: 'u3-parrafo' }, a)))
    : el('p', { class: 'u3-tenue' }, det.etiqueta ? 'La IA no marcó señales de riesgo en los títulos.' : 'Sin clasificar: no hay señales de riesgo evaluadas.')));

  out.push(secc(`Títulos de los anuncios (${det.titulos.length})`,
    el('div', { class: 'u3-tenue u3-peq' }, 'Texto escrito por terceros: se muestra tal cual. Los caracteres invisibles que cambian el sentido del texto se hacen visibles (⟦U+202E⟧) y nunca se toman como instrucción.'),
    det.titulos.length
      ? el('ol', { class: 'u3-titulos' }, det.titulos.map((x) => el('li', null, x.texto, x.bidi ? el('span', null, ' ', tag('caracteres invisibles hechos visibles', 'aviso')) : null)))
      : el('p', { class: 'u3-tenue' }, 'Los datos cargados de esta página no traen títulos.')));

  if (det.evidencia.length) {
    out.push(secc(`Evidencia citada por la IA (${det.evidencia.length})`, el('ul', { class: 'u3-titulos' }, det.evidencia.map((x) => el('li', null, x)))));
  }

  out.push(tecnico('Detalle técnico de la página',
    kv([
      ['Identificador de la página', el('code', null, det.id)],
      ['Consultas que la vieron', det.qids.length ? el('span', { class: 'u3-tags' }, det.qids.map((q) => el('code', null, q))) : null],
      ['Ficha del anuncio en la Biblioteca (solo texto)', det.fichas.length ? pila(det.fichas.map((u) => comando(u, { titulo: 'Copiar la dirección (URL) de la ficha' }))) : el('span', { class: 'u3-tenue' }, det.fichasNota)],
    ]),
    el('p', { class: 'u3-tenue u3-peq' }, 'La URL nunca se abre ni se enlaza automáticamente: cópiala y pégala tú si quieres ver el anuncio en Meta.')));
  return out;
}

// ───────────────────────── pestaña: páginas (paginado en el servidor) ─────────────────────────

function tabPaginas(ctx, d) {
  const p = vista.pag;
  const paisesOpc = d.candDatos && d.candDatos.matriz_tema_pais ? (d.candDatos.matriz_tema_pais.paises || []) : [];
  const buscarInput = el('input', {
    type: 'search', placeholder: 'Nombre de la página…', 'aria-label': 'Buscar página', value: p.q,
    onkeydown: (ev) => { if (ev.key === 'Enter') { p.q = ev.target.value; p.pagina = 1; cargarPaginas(); } },
  });
  const controles = el('div', { class: 'u3-tarjeta u3-filtros' },
    etiquetaCampo('Buscar (Enter)', buscarInput),
    etiquetaCampo('País', selector([['', 'Todos'], ...paisesOpc.map((x) => [x, x])], p.pais, (v) => { p.pais = v; p.pagina = 1; cargarPaginas(); }, { etiqueta: 'País' })),
    etiquetaCampo('Medición', selector([['', 'Todas'], ['completa', 'Completa'], ['parcial', 'Parcial'], ['muestra', 'Solo muestra']], p.estado, (v) => { p.estado = v; p.pagina = 1; cargarPaginas(); }, { etiqueta: 'Medición' })),
    el('button', { type: 'button', class: 'btn', onclick: () => { p.q = buscarInput.value; p.pagina = 1; cargarPaginas(); } }, ic('lupa', 14), 'Buscar'));
  const zona = pila(U.cargando('Leyendo páginas…'));

  async function cargarPaginas() {
    reemplazar(zona, U.esqueleto ? U.esqueleto('tabla') : U.cargando('Leyendo páginas…'));
    const r = await leer(ctx, rutaCorrida(d.id, 'paginas'), { q: p.q, pais: p.pais, estado: p.estado, pagina: p.pagina, por_pagina: p.porPagina });
    if (!r.ok) { reemplazar(zona, errorBox(r.error)); return; }
    const pg = L.normalizarPaginado(r.datos);
    if (!pg.filas.length) {
      const filtrando = p.q || p.pais || p.estado;
      reemplazar(zona, filtrando
        ? vacio('Ninguna página coincide con los filtros.', { pista: 'Cambia o borra los filtros.', icono: 'filtro' })
        : U.vacioConPasos({ titulo: 'Esta corrida todavía no tiene páginas cargadas', explicacion: 'Las páginas salen de cargar los datos sin procesar de las consultas.', pasos: [{ texto: 'Carga los datos sin procesar. Este comando guarda el resultado (--escribir); sin esa opción solo simula y no guarda nada.', comando: L.comandoBarrido('ingestar', d.id) }], icono: 'lupa' }),
      pieFuente(r));
      return;
    }
    const filas = pg.filas.map(L.filaPagina);
    const paginas = Math.max(1, Math.ceil(pg.total / (pg.porPagina || p.porPagina)));
    const nav = el('div', { class: 'u3-fila u3-fila--entre' },
      el('span', { class: 'u3-tenue' }, `Página ${L.num(pg.pagina)} de ${L.num(paginas)} · ${L.num(pg.total)} páginas del barrido (al menos esa cantidad: el total real puede ser mayor)`),
      el('span', { class: 'u3-fila' },
        el('button', { type: 'button', class: 'btn btn--chico', disabled: p.pagina <= 1 ? true : null, onclick: () => { p.pagina -= 1; cargarPaginas(); } }, '← Anterior'),
        el('button', { type: 'button', class: 'btn btn--chico', disabled: p.pagina >= paginas ? true : null, onclick: () => { p.pagina += 1; cargarPaginas(); } }, 'Siguiente →')));
    const t2 = tabla({
      etiqueta: 'Páginas del barrido', filas, maxFilas: 100, altoMax: '600px',
      columnas: [
        { clave: 'nombre', titulo: 'Página', clase: 'cel-larga', formato: (v, r) => el('div', null, el('strong', null, v), r.tema ? sub(r.tema) : null) },
        { clave: 'paises', titulo: 'Países', orden: (r) => r.paises.length, formato: (v) => (v.length ? el('span', { class: 'u3-tags' }, v.slice(0, 6).map((x) => tag(x, 'mono'))) : '—') },
        { clave: 'monedas', titulo: 'Moneda', formato: (v) => v.join(' ') || '—' },
        { clave: 'anuncios', titulo: 'Anuncios', alinear: 'der', formato: (v, r) => el('span', { title: r.piso ? 'Al menos esa cifra: muestra truncada o medición parcial' : null }, L.conPiso(v, r.piso)) },
        { clave: 'edad', titulo: 'Edad', alinear: 'der', formato: (v, r) => el('span', { title: r.edadPiso ? 'Al menos esa cifra' : null }, L.diasTexto(v, r.edadPiso)) },
        { clave: 'conceptos', titulo: 'Conceptos', alinear: 'der', formato: (v) => L.num(v) },
        { clave: 'medicion', titulo: 'Medición', formato: (v, r) => el('span', { title: r.medicionTexto.ayuda }, tag(r.medicionTexto.texto, r.medicionTexto.tono === 'ok' ? 'ok' : 'aviso')) },
        { clave: 'exportador', titulo: 'Exportador', orden: (r) => (r.exportador.hay ? 1 : 0), formato: (v, r) => (r.exportador.hay ? tag(r.exportador.texto, 'info', { icono: 'globo' }) : el('span', { class: 'u3-tenue' }, '—')) },
      ],
      alClick: (fila) => abrirPaginaSuelta(ctx, d, fila),
    });
    reemplazar(zona, nav, t2, pieFuente(r));
  }
  cargarPaginas();
  return pila(controles, zona);
}

function abrirPaginaSuelta(ctx, d, fila) {
  const panel = abrirPanel({ titulo: fila.nombre, subtitulo: 'Página de anunciante' });
  const ind = d.candDatos ? L.indexarCandidatas(d.candDatos).get(fila.id) : null;
  const candidata = ind ? ind.pagina : null;
  (async () => {
    reemplazar(panel.cuerpo, U.esqueleto ? U.esqueleto('texto') : U.cargando('Leyendo la página…'));
    const etiq = await cargarEtiquetas(ctx, d.id);
    if (panelActivo !== panel) return;
    const etiqueta = etiq.indice ? etiq.indice.get(fila.id) || null : null;
    const det = L.detallePagina({ candidata, pagina: fila.raw, etiqueta, corrida: d.id, umbral: d.res.umbral });
    const avisos = candidata ? [] : ['Esta página no está entre los candidatos del ranking (no avanzó o se descartó): se muestra solo lo de la carga de datos y la clasificación.'];
    reemplazar(panel.cuerpo, ...cuerpoPagina(ctx, panel, d, det, avisos));
  })();
}

// ───────────────────────── pestaña: mapa de calor tema × país ─────────────────────────

function tabMatriz(ctx, d) {
  if (!d.candDatos) return d.cand.ok ? vacioCandidatos(d) : errorBox(d.cand.error);
  const m = vista.matriz;
  const zona = pila();
  const advertencia = L.modeloMatriz(d.candDatos).advertencia;
  const filasTemas = new Map(L.filasTemas(d.candDatos).map((x) => [x.id, x]));
  const pintar = () => {
    const mod = L.modeloMatriz(d.candDatos, { soloPasan: m.soloPasan, q: m.q, minPaises: m.minPaises });
    const cabecera2 = el('tr', null,
      el('th', { scope: 'col' }, 'Tema'),
      mod.paises.map((p, i) => el('th', { scope: 'col', title: `${mod.porPais[i].presentes} de ${mod.totalTemas} temas con presencia en ${p}` }, p, el('small', null, `${mod.porPais[i].presentes}/${mod.totalTemas}`))));
    const cuerpo = mod.filas.map((f) => {
      const fila = filasTemas.get(f.slug);
      const abrir = () => { if (fila) abrirDetalle(ctx, d, fila); };
      return el('tr', { tabindex: fila ? '0' : null, onclick: abrir, onkeydown: (ev) => { if (ev.key === 'Enter') abrir(); }, 'aria-label': `Abrir el detalle de ${f.nombre}` },
        el('th', { scope: 'row' }, el('div', { class: 'u3-calor__tema' }, estadoIconoTraccion(f.estado), el('span', { class: 'u3-calor__nombre', title: f.nombre }, f.nombre))),
        f.celdas.map((c) => (c.presente
          ? el('td', { class: `n${c.nivel}`, title: `${c.paginas} página(s) vistas en ${c.pais}` }, String(c.paginas))
          : el('td', { class: 'n0', title: `No visto en la muestra de ${c.pais}: es una hipótesis, no una ausencia medida` }, '·'))));
    });
    reemplazar(zona,
      el('div', { class: 'u3-calor-envuelto' }, el('table', { class: 'u3-calor', 'aria-label': 'Mapa de calor: páginas vistas por tema y país' }, el('thead', null, cabecera2), el('tbody', null, cuerpo))),
      el('div', { class: 'u3-leyenda', 'aria-label': 'Leyenda del mapa de calor' },
        el('span', null, el('i', { class: 'n0' }), 'no visto (hipótesis)'), el('span', null, el('i', { class: 'n1' }), '1 página'), el('span', null, el('i', { class: 'n2' }), '2'), el('span', null, el('i', { class: 'n3' }), '3–4'), el('span', null, el('i', { class: 'n4' }), '5 o más')),
      el('p', { class: 'u3-tenue u3-peq' }, `${L.num(mod.total)} de ${L.num(mod.totalTemas)} temas · los temas sin tema («indeterminado») no entran en el mapa. Clic en un tema para ver su detalle.`));
  };
  const controles = el('div', { class: 'u3-tarjeta u3-fila', style: { alignItems: 'flex-end', gap: '20px' } },
    el('label', { class: 'u3-interruptor' }, el('input', { type: 'checkbox', checked: m.soloPasan ? true : null, onchange: (ev) => { m.soloPasan = ev.target.checked; pintar(); } }), 'Solo temas que pasan la tracción'),
    etiquetaCampo('Buscar tema', el('input', { type: 'search', value: m.q, 'aria-label': 'Buscar tema', oninput: (ev) => { m.q = ev.target.value; pintar(); } })),
    etiquetaCampo('Presente en al menos', selector([['0', 'cualquier nº de países'], ['2', '2 países'], ['3', '3 países'], ['4', '4 países']], String(m.minPaises), (v) => { m.minPaises = Number(v); pintar(); }, { etiqueta: 'Mínimo de países' })));
  pintar();
  return pila(
    nota(el('p', null, el('strong', null, 'Un hueco es una hipótesis, no un hecho. '), advertencia, ' ', U.termino('hueco_muestra', { texto: 'Qué es un hueco' }), '.'), { tono: 'aviso', icono: 'alerta' }),
    controles, zona, pieFuente(d.cand));
}

function estadoIconoTraccion(estado) {
  const e = ESTADO_TRACCION[estado] || { tono: 'neutro', icono: 'menos', texto: 'Sin estado' };
  return el('span', { class: ['u3-estado', `u3-estado--${e.tono}`], title: e.texto, role: 'img', 'aria-label': e.texto }, ic(e.icono, 14));
}

// ───────────────────────── pestaña: fichas borrador ─────────────────────────

async function tabFichas(ctx, d) {
  const r = await cargado(ctx, d.id, 'fichas');
  if (!r.ok) return errorBox(r.error, { reintentar: () => ctx.recargar() });
  if (!esObjetoNoVacio(r.datos) || !(r.datos.ofertas || []).length) {
    return U.vacioConPasos({
      titulo: 'Esta corrida no tiene fichas borrador',
      explicacion: 'Las fichas salen después del ranking: una por cada candidato con tracción, con las puertas y la transferibilidad todavía sin evaluar (las evalúa la sesión de descubrimiento). Si ningún candidato pasa, no se escribe ninguna.',
      pasos: [{ texto: 'Arma las fichas. Este comando guarda el resultado (--escribir); sin esa opción solo simula y no guarda nada. Cambia <SELLO> y <SELLO_LIMITES> por los códigos del visto bueno firmado de las reglas y de los límites.', comando: L.comandoBarrido('fichas', d.id) }], icono: 'lista',
    });
  }
  const mod = L.modeloFichas(r.datos);
  const tarjetas = mod.fichas.map((f) => el('button', { type: 'button', class: 'u3-ficha', onclick: (ev) => abrirFicha(f, ev.currentTarget), 'aria-label': `Abrir la ficha de ${f.nombre}` },
    el('div', { class: 'u3-pila u3-pila--chica' },
      el('h3', null, f.nombre || f.id),
      el('div', { class: 'u3-tags' }, f.macro ? tag(f.macro, 'acento') : tag('fuera de marco', 'hipotesis', { titulo: 'Fuera de las categorías en las que trabaja la fábrica (salud, relaciones o dinero)' }), f.pais ? tag(`${f.pais}${f.idioma ? ` · ${f.idioma}` : ''}`, 'mono', { titulo: 'País e idioma de origen' }) : null, tag(`${f.mercados.length} mercado${f.mercados.length === 1 ? '' : 's'}`, null))),
    el('div', { class: 'u3-tenue u3-peq' }, `${t(f.traccion.anuncios)} anuncios · ${L.diasTexto(f.traccion.edad, true)} · ${t(f.traccion.conceptos)} concepto${f.traccion.conceptos === 1 ? '' : 's'}`),
    el('div', { class: ['u3-barra', f.completo && 'u3-barra--supera'], style: { '--p': `${f.pctEvaluado}%` } },
      el('div', { class: 'u3-barra__cab' }, el('span', null, 'Evaluado'), el('span', { class: 'u3-barra__valor' }, `${f.evaluados} de ${f.totalCampos} campos`)),
      el('div', { class: 'u3-barra__pista', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': f.pctEvaluado, 'aria-label': `Campos evaluados de ${f.nombre}` }, el('div', { class: 'u3-barra__relleno' }))),
    f.faltantes.length ? el('div', { class: 'u3-tags', title: 'Qué falta evaluar' }, f.faltantes.map((x) => tag(x.tema, 'aviso'))) : tag('Completa', 'ok', { icono: 'ok' })));
  return pila(
    nota(el('p', null, el('strong', null, 'Fichas con el puntaje incompleto. '),
      `${L.num(mod.incompletas)} de ${L.num(mod.total)} aún no se pueden puntuar: las `, U.termino('puertas', { texto: 'puertas' }), ', la ', U.termino('transferibilidad', { texto: 'transferibilidad' }),
      ', el puntaje del rival y los ', U.termino('diferenciacion', { texto: 'reencuadres' }), ' están sin evaluar (sin evaluar nunca significa «no»). El hueco de cada mercado sale de la ausencia en la muestra: una hipótesis hasta medir con la pasada 3.'), { tono: 'aviso', icono: 'alerta' }),
    el('div', { class: 'u3-fichas' }, tarjetas),
    comando(`.venv/bin/python -m scripts.modelado.puntaje_modelar puntuar empresa/barrido/candidatos/${d.id}/fichas_borrador.json --parametros scripts/modelado/parametros_modelado.propuesta.yaml --sello-esperado <SELLO> --json`, { titulo: 'Cómo puntuarlas cuando estén evaluadas', nota: `Versión del formato de la ficha: ${t(mod.version)}. Lo ejecutas tú en la Terminal. Cambia <SELLO> por el código del visto bueno firmado de las reglas.` }),
    pieFuente(r));
}

function abrirFicha(f, origen) {
  const panel = abrirPanel({ titulo: f.nombre || f.id, subtitulo: 'Ficha borrador', origen });
  const pt = (v) => (v === null || v === undefined ? tag('sin evaluar', 'aviso') : tag(String(v), v === true ? 'error' : 'ok'));
  reemplazar(panel.cuerpo,
    el('div', { class: 'u3-fila' }, f.macro ? tag(f.macro, 'acento') : tag('fuera de marco', 'hipotesis', { titulo: 'Fuera de las categorías en las que trabaja la fábrica (salud, relaciones o dinero)' }), tag(f.completo ? 'Completa' : `Faltan ${f.faltan} de ${f.totalCampos} campos`, f.completo ? 'ok' : 'aviso')),
    secc('Qué falta evaluar', f.faltantes.length ? el('ul', { class: 'u3-bloqueos' }, f.faltantes.map((x) => el('li', null, ic('alerta', 16), el('span', null, el('strong', null, x.tema), ' — ', x.detalle)))) : el('p', { class: 'u3-parrafo' }, 'Nada: la ficha está completa.')),
    secc(U.termino('traccion', { texto: 'Tracción observada' }), kv([
      ['Origen', `${t(f.pais)} · ${t(f.idioma)}`], ['Anuncios activos', `${t(f.traccion.anuncios)} (de la muestra: al menos esa cifra)`], ['Edad de la oferta', L.diasTexto(f.traccion.edad, true)],
      ['Conceptos únicos', t(f.traccion.conceptos)], ['Anuncios que llevan a la misma página de venta (indicio)', t(f.traccion.paginasMismaLanding)], ['Anunciantes independientes, mismo ángulo (indicio)', t(f.traccion.independientes)],
      ['Reencuadres', f.reencuadres ? String(f.reencuadres) : 'sin diseñar'],
    ])),
    secc(U.termino('puertas', { texto: 'Puertas' }), kv(f.puertas.map((p) => [L.neutralizar(p.id.replace(/_/g, ' ')), pt(p.valor)]))),
    secc(`Mercados (${f.mercados.length}): el hueco es una hipótesis`, el('div', { class: 'u3-pila u3-pila--chica' }, f.mercados.map((m) => el('div', { class: 'u3-tarjeta u3-tarjeta--hundida u3-pila u3-pila--chica' },
      el('div', { class: 'u3-fila u3-fila--entre' }, el('strong', null, `${m.mercado} (${t(m.idioma)})`), m.ventana === 'evergreen' ? tag('ventana «evergreen» (sin fecha): relleno', 'aviso') : tag(`ventana ${t(m.ventana)}`, null, { titulo: 'Qué tan oportuno es entrar ahora a ese mercado' })),
      el('div', { class: 'u3-tags' },
        m.originalPresente === false ? tag('original no visto (hipótesis)', 'aviso') : m.originalPresente === true ? tag('original presente', 'ok') : tag('original: sin dato', null),
        tag(`${t(m.sostenidos)} anunciantes sostenidos`, null),
        m.puntajeRival === null || m.puntajeRival === undefined ? tag('rival sin auditar', 'aviso', { titulo: 'Puntaje del rival: nota de 0 a 100 de qué tan fuerte es la oferta rival que ya se anuncia en ese mercado' }) : tag(`puntaje del rival ${m.puntajeRival}`, null),
        m.entrantes === null || m.entrantes === undefined ? tag('anunciantes nuevos: sin dato', 'hipotesis', { titulo: 'Sin dato: no hay una corrida anterior para comparar (no es cero)' }) : tag(`${m.entrantes} anunciantes nuevos en 30 días`, null),
        tag(`transferibilidad: ${m.faltanTransfer}/${m.transfer.length} sin evaluar`, m.faltanTransfer ? 'aviso' : 'ok')))))),
    f.pendiente.length ? secc('Pendiente (según el borrador)', el('ul', { class: 'u3-bloqueos' }, f.pendiente.map((x) => el('li', null, ic('alerta', 16), el('span', null, x))))) : null,
    tecnico('Detalle técnico de la ficha', kv([['Identificador de la ficha', el('code', null, f.id)]])));
}

// ───────────────────────── pestaña: plan y cobertura ─────────────────────────

async function tabPlan(ctx, d) {
  const rp = await cargado(ctx, d.id, 'plan');
  if (!rp.ok) return errorBox(rp.error, { reintentar: () => ctx.recargar() });
  if (!esObjetoNoVacio(rp.datos) || !(rp.datos.consultas || []).length) {
    return pila(
      U.vacioConPasos({
        titulo: 'Esta corrida no tiene plan de consultas',
        explicacion: 'El plan de la pasada 1 (una frase en cada país) se genera sin conectarse a internet. Se guarda con --escribir; sin esa opción solo simula y no guarda nada.',
        pasos: [{ texto: 'Genera el plan.', comando: L.comandoBarrido('plan', d.id) }], icono: 'lista',
      }));
  }
  const mod = L.modeloPlan(rp.datos, d.estadoDatos);
  const hayEj = mod.porPasadaDisponible;
  const tot = mod.totalesEstado;
  const tarjetasPasada = mod.pasadas.map((p) => {
    const seg = [{ valor: p.ok || 0, tono: 'ok', titulo: 'ejecutadas' }, { valor: p.conError || 0, tono: 'error', titulo: 'con error' }, { valor: p.sinEjecutar || 0, tono: 'neutro', titulo: 'sin ejecutar' }];
    return el('div', { class: 'u3-pasada' },
      el('h3', null, p.nombre),
      hayEj ? U.barraApilada(seg, { etiqueta: `${p.nombre}: ${p.ok} ejecutadas, ${p.conError} con error, ${p.sinEjecutar} sin ejecutar` }) : el('div', { class: 'u3-tenue u3-peq' }, 'Sin detalle de ejecución por pasada.'),
      el('div', { class: 'u3-pasada__cifras' },
        el('span', null, el('b', null, L.num(p.planificadas)), ' planificadas'),
        hayEj ? el('span', null, el('b', null, L.num(p.ok)), ' ejecutadas') : null,
        hayEj && p.conError ? el('span', null, el('b', null, L.num(p.conError)), ' con error') : null,
        hayEj ? el('span', null, el('b', null, L.num(p.sinEjecutar)), ' sin ejecutar') : null,
        hayEj && p.truncadas !== null ? el('span', { title: 'llegaron al límite de 50 anuncios y había más resultados: la cifra es de al menos esa' }, el('b', null, L.num(p.truncadas)), ' truncadas') : null),
      p.paises ? el('div', { class: 'u3-tenue u3-peq' }, `Países: ${p.paises}`) : null);
  });
  const consultasTabla = tabla({
    etiqueta: 'Consultas del plan', filas: mod.consultas, maxFilas: 60, altoMax: '420px',
    columnas: [
      { clave: 'qid', titulo: 'Identificador', formato: (v) => el('code', null, v) },
      { clave: 'pasada', titulo: 'Pasada', alinear: 'der' },
      { clave: 'pais', titulo: 'País' },
      { clave: 'idioma', titulo: 'Idioma' },
      { clave: 'forma', titulo: 'Forma', clase: 'cel-larga' },
      { clave: 'frase', titulo: 'Frase (escrita por terceros)', clase: 'cel-larga' },
      { clave: 'paginas', titulo: 'Páginas', alinear: 'der', formato: (v) => (v ? L.num(v) : '—') },
      ...(hayEj ? [{ clave: 'estado', titulo: 'Estado', formato: (v) => chip({ ok: 'ok', truncada: 'truncada', con_error: 'con error', sin_ejecutar: 'sin ejecutar' }[v] || '—', { ok: 'ok', truncada: 'aviso', con_error: 'error', sin_ejecutar: 'aviso' }[v] || 'neutro') }] : []),
    ],
  });
  return pila(
    el('div', { class: 'u3-metricas' },
      U.metrica({ etiqueta: 'Consultas planificadas', valor: `${L.num(mod.planificadas)}${mod.tope !== null ? ` / ${L.num(mod.tope)}` : ''}`, contexto: mod.cupoRestante !== null ? `quedan ${L.num(mod.cupoRestante)} (las 3 pasadas cuentan juntas)` : 'máximo sin dato', tono: mod.cupoRestante !== null && mod.cupoRestante < 0 ? 'error' : 'neutro', ayuda: 'cupo_consultas' }),
      tot ? U.metrica({ etiqueta: 'Ejecutadas', valor: L.num(tot.ok), contexto: `con error ${tot.conError === null ? 'n/d' : L.num(tot.conError)} · sin ejecutar ${tot.sinCrudo === null ? 'n/d' : L.num(tot.sinCrudo)}`, tono: tot.conError ? 'error' : 'neutro' }) : null,
      tot ? U.metrica({ etiqueta: 'Truncadas', valor: tot.truncadas === null ? 'n/d' : L.num(tot.truncadas), contexto: 'llegaron al máximo de 50 anuncios: la cifra es de al menos esa', ayuda: 'muestra_truncada' }) : null,
      tot && tot.anunciosDistintos !== null ? U.metrica({ etiqueta: 'Anuncios distintos vistos', valor: L.num(tot.anunciosDistintos), contexto: 'al menos esa cifra: hasta 50 por consulta' }) : null),
    mod.avisoSinListas ? nota(el('p', null, mod.avisoSinListas), { tono: 'neutra' }) : null,
    seccion('Cobertura por pasada', el('div', { class: 'u3-pasadas' }, tarjetasPasada), { ayuda: 'La pasada 1 barre por forma de oferta y país; la 2 insiste donde la muestra oculta mucho; la 3 mide de verdad página por página (la única cuya cifra no es un «al menos»).' }),
    tecnico(`Consultas del plan (${L.num(mod.planificadas)})`,
      el('p', { class: 'u3-tenue u3-peq' }, `Plan ${t(mod.corrida)} · creado ${mod.creadoEn ? fmt.fecha(mod.creadoEn) : '—'}. Las frases las escribieron agentes o el banco del barrido: se muestran como texto.`),
      consultasTabla),
    pieFuente(rp));
}

// ───────────────────────── pestaña: etiquetado y descartes ─────────────────────────

async function tabEtiquetado(ctx, d) {
  const e = await cargarEtiquetas(ctx, d.id);
  if (!e.ok) return errorBox(e.error, { reintentar: () => ctx.recargar() });
  if (!esObjetoNoVacio(e.datos)) {
    return U.vacioConPasos({
      titulo: 'Esta corrida todavía no tiene la clasificación reunida',
      explicacion: 'La IA clasifica las páginas por lotes (les pone tema, público y señales de riesgo). Después se «consolida»: se revisa que cada clasificación cite como evidencia un título textual del anuncio.',
      pasos: [{ texto: 'Prepara y reúne las clasificaciones. Este comando guarda el resultado (--escribir); sin esa opción solo simula y no guarda nada.', comando: L.comandoBarrido('etiquetas', d.id) }], icono: 'lista',
    });
  }
  const mod = L.modeloEtiquetado(e.datos);
  const desc = d.candDatos ? L.modeloDescartadas(d.candDatos) : null;
  return pila(
    el('div', { class: 'u3-metricas' },
      U.metrica({ etiqueta: 'Clasificadas por IA', valor: `${L.num(mod.etiquetadas)} / ${L.num(mod.total)}`, contexto: `${mod.tasaEtiquetadas} de las páginas · ${mod.tasaConTema} con tema` }),
      U.metrica({ etiqueta: 'Sin clasificar', valor: L.num(mod.sinEtiquetar), contexto: `en disputa (clasificaciones que no coinciden) ${L.num(mod.enDisputa)} · rechazadas ${L.num(mod.rechazadas)}`, tono: mod.sinEtiquetar ? 'aviso' : 'ok' }),
      U.metrica({ etiqueta: 'Avanzan a candidata', valor: L.num(mod.avanzan), contexto: `${L.num(mod.indeterminadas)} de tema indeterminado avanzan solo con tracción` }),
      U.metrica({ etiqueta: 'Lotes validados', ayuda: 'lotes_clasificacion', valor: `${L.num(mod.lotes.validados)} / ${L.num(mod.lotes.total)}`, contexto: `sin respuesta ${L.num(mod.lotes.sinSalida)} · respuesta inválida ${L.num(mod.lotes.invalidos)}`, tono: mod.lotes.sinSalida || mod.lotes.invalidos ? 'aviso' : 'ok' })),
    el('div', { class: 'u3-dos' },
      seccion('Señales de riesgo en los títulos', mod.riesgos.length
        ? el('div', { class: 'u3-lista' }, mod.riesgos.map((s) => el('div', { class: 'u3-item', style: { gridTemplateColumns: 'minmax(0, 1fr) auto' } }, el('span', null, tag(s.senal, 'aviso')), el('span', { class: 'u3-tenue' }, `${L.num(s.n)} página${s.n === 1 ? '' : 's'}`))))
        : el('p', { class: 'u3-tenue' }, 'La IA no marcó señales de riesgo.'),
      { ayuda: 'Las marca la IA leyendo títulos (urgencia falsa, promesas de ingresos…). Orientan; no descartan por sí solas.' }),
      seccion(`Sin clasificar (${L.num(mod.sinEtiquetarLista.length)})`, mod.sinEtiquetarLista.length
        ? tabla({
          etiqueta: 'Páginas sin clasificar', filas: mod.sinEtiquetarLista, maxFilas: 30, altoMax: '260px',
          columnas: [{ clave: 'nombre', titulo: 'Página', clase: 'cel-larga' }, { clave: 'motivo', titulo: 'Motivo', formato: (v) => tag(v || '—', null) }],
        }) : el('p', { class: 'u3-tenue' }, 'Todas las páginas con títulos están clasificadas.'))),
    seccion(`Descartadas (${L.num(desc ? desc.filas.length : 0)}) y su motivo`, desc && desc.filas.length ? pila(
      el('div', { class: 'u3-tags' }, desc.porMotivo.map((m) => tag(`${m.motivo} × ${m.n}`, null))),
      tabla({
        etiqueta: 'Páginas descartadas', filas: desc.filas, maxFilas: 50, altoMax: '360px', filtro: { placeholder: 'filtrar descartadas…' },
        columnas: [
          { clave: 'nombre', titulo: 'Página', clase: 'cel-larga' },
          { clave: 'paises', titulo: 'Países', formato: (v) => v.join(' ') || '—' },
          { clave: 'enMuestra', titulo: 'Anuncios (muestra)', alinear: 'der', formato: (v) => L.num(v) },
          { clave: 'formato', titulo: 'Formato' },
          { clave: 'motivos', titulo: 'Motivo', clase: 'cel-larga', formato: (v) => el('span', { class: 'u3-tags' }, v.map((x) => tag(x, null))) },
        ],
      })) : el('p', { class: 'u3-tenue' }, d.candDatos ? 'Ninguna página descartada.' : 'Sin candidatos: no hay descartes que mostrar.'),
    { ayuda: 'Se descartan por formato (comunidad, servicio, producto físico) o porque la IA dice que no es pago único. Un «no sé» (sin dato) NO descarta: la página avanza y queda «por verificar».' }),
    pieFuente(e));
}

// ───────────────────────── pestaña: memoria entre corridas ─────────────────────────

function tabMemoria(ctx, d) {
  const mod = L.modeloMemoria({ corridas: d.corridas, estado: d.estadoDatos, candidatos: d.candDatos, corridaId: d.id });
  return pila(
    nota(el('p', null, el('strong', null, mod.baseValida ? 'Hay con qué comparar. ' : 'No hay con qué comparar. '), mod.explicacion, ' ', U.termino('memoria_barrido', { texto: 'Cómo funciona la comparación' }), '.'), { tono: mod.baseValida ? 'ok' : 'aviso', icono: mod.baseValida ? 'ok' : 'alerta' }),
    el('div', { class: 'u3-metricas' },
      U.metrica({ etiqueta: 'Corrida anterior para comparar', valor: mod.baseValida ? 'sí hay' : 'no hay', contexto: mod.previa ? `anterior: ${mod.previa}` : 'ninguna de entre 25 y 60 días atrás', tono: mod.baseValida ? 'ok' : 'aviso' }),
      U.metrica({
        etiqueta: 'Foto de esta corrida',
        valor: mod.instantaneaDeEstaCorrida === true ? 'guardada' : mod.instantaneaDeEstaCorrida === false ? 'no guardada' : (mod.instantaneas !== null ? L.num(mod.instantaneas) : '—'),
        contexto: mod.problemas.length ? `${mod.problemas.length} problema(s)` : (mod.instantaneaTs ? `guardada ${fmt.relativo(mod.instantaneaTs)}` : 'se guarda con el comando de abajo'),
        tono: mod.problemas.length ? 'error' : mod.instantaneaDeEstaCorrida === false ? 'aviso' : 'neutro',
      }),
      U.metrica({ etiqueta: 'Temas con anunciantes nuevos medidos', valor: `${L.num(mod.temasConEntrantes)} / ${L.num(mod.totalTemas)}`, contexto: 'sin dato = no hay con qué comparar; nunca es cero', ayuda: 'entrantes_30d' }),
      U.metrica({ etiqueta: 'Temas nuevos', valor: mod.baseValida ? L.num(mod.temasNuevos) : '—', contexto: mod.baseValida ? 'frente a la foto previa' : 'requiere una foto previa' })),
    mod.problemas.length ? nota(el('p', null, el('strong', null, 'Problemas con las fotos guardadas: '), mod.problemas.join(' · ')), { tono: 'error', icono: 'alerta' }) : null,
    seccion('Corridas: comparación entre barridos', tabla({
      etiqueta: 'Corridas del barrido', filas: mod.filas, maxFilas: 50,
      columnas: [
        { clave: 'corrida', titulo: 'Corrida', formato: (v, r) => el('span', null, el('code', null, v), r.actual ? el('span', null, ' ', tag('esta', 'acento')) : null) },
        { clave: 'consultas', titulo: 'Consultas', alinear: 'der', formato: (v) => L.num(v) },
        { clave: 'paginas', titulo: 'Páginas (al menos)', alinear: 'der', formato: (v, r) => (v === null ? '—' : `${L.num(v)}${r.deltaPaginas !== null ? ` (${r.deltaPaginas >= 0 ? '+' : ''}${L.num(r.deltaPaginas)})` : ''}`) },
        { clave: 'candidatas', titulo: 'Candidatas', alinear: 'der', formato: (v) => L.num(v) },
        { clave: 'pasanTraccion', titulo: 'Pasan tracción', alinear: 'der', formato: (v) => L.num(v) },
        { clave: 'fichas', titulo: 'Fichas', alinear: 'der', formato: (v) => L.num(v) },
        { clave: 'actualizadoEn', titulo: 'Actualizada', formato: (v) => (v ? el('span', { title: fmt.fecha(v) }, fmt.relativo(v)) : '—') },
      ],
      vacio: 'Sin corridas.',
    }), { ayuda: mod.nota }),
    comando(L.comandoBarrido('memoria', d.id), { titulo: 'Cómo guardar la foto de esta corrida', nota: 'Hazlo después de la última carga de datos: guarda una foto que no se puede modificar (empresa/barrido/memoria/<corrida>.json). El panel no lo ejecuta por ti.' }),
    d.est.ok ? pieFuente(d.est) : null);
}
