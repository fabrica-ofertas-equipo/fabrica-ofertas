// app.js — shell del panel: router por hash, sidebar/topbar, ciclo de vida de páginas, SSE con rebote (CONTRATO §3, §5) + rediseño U0.
//
// Barra superior: selector de oferta · buscador/paleta de comandos (Ctrl/⌘+K) · interruptor «Detalle técnico» · densidad · tema · EN VIVO · PAUSA y freno
// (icono + etiqueta) · «Pausar todo» (con confirmación). Sidebar por piezas (8 grupos: «El sistema», las 6 piezas numeradas y «Dinero y reglas»), con iconos y
// contadores. Atajos: `g` + letra, `/`, `?`.
//
// Página (pages/<ruta>.js):  export const meta = {ruta, titulo, grupo, icono?, escucha?: ['registro','oferta',…]}   // `grupo` = el literal del grupo del menú (sin número de pieza)
//                            export async function render(ctx) → Element
//                            export function alCambio(ctx, evento) {}     // opcional; si falta, el router re-renderiza con rebote de 400 ms
//                            export function alSalir(ctx) {}              // opcional: limpiar temporizadores
//   ctx = {api, ui, fmt, params, estado, ruta, navegar(hash), recargar(), alSalir(fn), pausarTodo(), paginas() → {ruta: 'ok'|'falta'|'error'}, titulos()}
//   ctx.params.id para #/oferta/<id>; los `?clave=valor` del hash llegan también en ctx.params.
//   `evento` de alCambio = último evento {tipo, ruta, ts} más `lote` (todos los eventos del rebote).
// Si el módulo de una página no existe aún, su entrada del sidebar dice «pronto» y la ruta muestra «próximamente» (el router no se rompe).
// Ruta de desarrollo `#/_diseno` (galería de componentes, sin datos reales): no figura en el menú; sale en la paleta solo con el modo técnico.

import { api } from './api.js';
import { ui, el, fmt, icono, limpiar, reemplazar, vacio, errorBox, modal, toast, cerrarModales } from './ui.js';
import { estado } from './estado.js';
import { atajoDeRuta, crearAtajos } from './lib/atajos.js';
import { agruparPorGrupo, buscar, construirEntradas, etiquetaGrupo, moverSeleccion, normalizar } from './lib/paleta.js';
import { banderas } from './lib/negocio-visual.js';
import { CSS_ETAPAS, gruposPorEtapa, marcaBackend, tonoEtapa } from './lib/negocio-etapas.js';
import * as ocultar from './lib/ocultar.js';

// ───────────────────────── navegación: el sidebar por piezas (mapeo.md §1, §9; CONTRATO §3 la ordenaba en dos grupos, ahora son ocho) ─────────────────────────
//
// Seis grupos son las 6 piezas del sistema (`pieza` 1..6, se muestran como «1 · Cerebro»); «El sistema» (la vista de conjunto) y «Dinero y reglas» no llevan número.
// `grupo` es el literal que cada página repite en su `meta.grupo` (sin número). `ayuda`: una frase de negocio que sale como tooltip del título de sección.
// `buscar` (del grupo o de cada pantalla): otras palabras con las que la paleta (Ctrl/⌘+K) también encuentra las pantallas, incluidos sinónimos de todos los días
// («qué hago», «plata», «página de venta»). No se quita ninguna pantalla: solo se ordenan.
// Las rutas cuyo módulo (pages/<ruta>.js) aún no existe se ven como «pronto» y la ruta muestra «se está preparando» (el router no se rompe).

const GRUPOS = [
  {
    grupo: 'El sistema',
    ayuda: 'La vista de conjunto: cómo va todo el negocio y qué necesita tu atención hoy.',
    buscar: ['centro de mando', 'inicio', 'rueda', 'hoy'],
    items: [
      { ruta: 'resumen', titulo: 'Resumen', icono: 'inicio', buscar: ['inicio', 'hoy', 'qué pasa hoy', 'novedades', 'estado general', 'me puedo ausentar', 'ausentarme', 'puedo irme', 'semáforo', 'vacaciones'], desc: 'Qué pasa hoy: si te puedes ausentar, lo que espera tu firma, cuánto se gastó, qué alertas hay y qué se hizo últimamente.' },
      { ruta: 'negocio', titulo: 'Negocio', icono: 'grafico', buscar: ['ganancia', 'ganancia neta', 'estamos ganando', 'perdiendo', 'roas', 'retorno', 'costo por venta', 'cpa', 'kpi', 'tablero', 'dashboard', 'cartera', 'tiendas', 'gastos'], desc: 'Si estamos ganando o perdiendo: gasto, ventas, neto, ganancia y retorno de cada oferta con todas sus tiendas.' },
      { ruta: 'tareas', titulo: 'Mis tareas', icono: 'tareas', buscar: ['qué hago', 'qué hago ahora', 'qué sigue', 'pendientes', 'lista', 'por hacer', 'tareas pendientes', 'próximo paso', 'checklist'], desc: 'Tu lista de cosas por hacer, paso a paso, y lo que ya está hecho.' },
    ],
  },
  {
    grupo: 'Cerebro', pieza: 1,
    ayuda: 'La memoria del negocio: lo aprendido, las reglas vigentes, tus pendientes y el historial de todo lo que pasa.',
    buscar: ['memoria', 'lecciones', 'reglas', 'aprendizajes'],
    items: [
      { ruta: 'cerebro', titulo: 'Cerebro', icono: 'cerebro', desc: 'La memoria del negocio: lo aprendido, las reglas vigentes y los pendientes, todo en un solo lugar.' },
      { ruta: 'pulido', titulo: 'Mejoras pendientes', icono: 'lapiz', buscar: ['pulido', 'corregir', 'errores', 'mejoras', 'arreglar'], desc: 'Tu lista de cosas por corregir en cada paso, hasta que todo funcione casi solo.' },
      { ruta: 'skills', titulo: 'Guías de trabajo', icono: 'chispa', buscar: ['skills', 'skill', 'guías', 'guias', 'instrucciones', 'versión'], desc: 'Las guías de trabajo de cada IA: qué versión tienen, si están listas y qué les falta.' },
      { ruta: 'registro', titulo: 'Historial', icono: 'lista', buscar: ['registro', 'bitácora', 'qué pasó', 'eventos'], desc: 'Todo lo que hizo el sistema, en orden y en vivo, con la comprobación de que nada se alteró.' },
    ],
  },
  {
    grupo: 'Fábrica y tienda', pieza: 2,
    ayuda: 'Donde se preparan los anuncios y se cobra: los anuncios de cada noche, la página de venta y lo que pasa después de pagar.',
    buscar: ['fábrica de creativos', 'creativos', 'anuncios', 'tienda', 'producción', 'página de venta', 'cobrar'],
    items: [
      { ruta: 'fabrica', titulo: 'Fábrica', icono: 'fabrica', buscar: ['anuncios de la noche', 'piezas', 'por aprobar'], desc: 'Los anuncios que se preparan cada noche: cuáles están listos, cuáles esperan tu aprobación y qué tipos probar.' },
      { ruta: 'landing', titulo: 'Página de venta', icono: 'pantalla', buscar: ['landing', 'pagina de venta', 'sitio', 'web'], desc: 'La página de venta de cada oferta: si pasó las revisiones y cómo se ve antes de publicarla.' },
      { ruta: 'poscompra', titulo: 'Después de la venta', icono: 'bolsa', buscar: ['poscompra', 'post-compra', 'después de pagar', 'entrega', 'reembolsos', 'disputas', 'soporte'], desc: 'Lo que pasa después de pagar: entrega del producto, oferta extra, carrito abandonado y soporte.' },
    ],
  },
  {
    grupo: 'Jurado', pieza: 3,
    ayuda: 'Un jurado de clientes simulados con IA vota a ciegas qué anuncio conviene probar, antes de gastar dinero.',
    buscar: ['clientes sintéticos', 'clientes simulados', 'votación', 'predicción', 'a ciegas'],
    items: [
      { ruta: 'jurado', titulo: 'Jurado', icono: 'balanza', desc: 'Clientes simulados con IA que votan a ciegas qué anuncio probar antes de gastar, y cuánto acertaron después.' },
    ],
  },
  {
    grupo: 'Testeo y escala', pieza: 4,
    ayuda: 'Se lanza el paquete completo (oferta, página y anuncios), se decide en un día y lo que vende se agranda.',
    buscar: ['test', 'testeo', 'lanzamiento', 'escalar', 'escala', 'meta', 'prueba'],
    items: [
      { ruta: 'descubrimiento', titulo: 'Radar de ofertas', icono: 'lupa', buscar: ['descubrimiento', 'barrido', 'ideas', 'qué se vende', 'ofertas ajenas'], desc: 'Qué se está vendiendo en tu mercado: ideas de oferta con sus pruebas y el plan de búsqueda.' },
      { ruta: 'ofertas', titulo: 'Ofertas', icono: 'caja', alias: ['oferta'], buscar: ['productos', 'fases', 'avance'], desc: 'Todas las ofertas por fase, con su avance etapa por etapa y el detalle de cada una.' },
      { ruta: 'campanas', titulo: 'Campañas', icono: 'megafono', buscar: ['anuncios en meta', 'activar', 'prender'], desc: 'Las campañas de anuncios: qué se revisó antes de prenderlas, su aprobación y su estado.' },
      { ruta: 'operacion', titulo: 'Resultados', icono: 'pulso', buscar: ['operación', 'operacion', 'ventas', 'día a día', 'números'], desc: 'Cómo va cada oferta día a día: ventas, lo que decidió el sistema y las órdenes.' },
    ],
  },
  {
    grupo: 'Robots', pieza: 5,
    ayuda: 'Los robots que trabajan solos con su horario, vigilados por avisos, controles de pago y un auditor.',
    buscar: ['automático', 'automatización', 'piloto automático', 'vigilancia'],
    items: [
      { ruta: 'robots', titulo: 'Robots', icono: 'rayo', buscar: ['automáticos', 'horarios', 'qué corre solo'], desc: 'Los robots que suben, bajan, prenden y frenan anuncios solos, siempre dentro de tus topes.' },
      { ruta: 'avisos', titulo: 'Avisos', icono: 'campana', buscar: ['alertas', 'notificaciones', 'celular', 'resumen del día', 'informe del día', 'informe diario', 'filtrar alertas'], desc: 'Las alertas (con filtros y a quién le toca cada una) y el informe del día: qué se avisa, cuándo y por qué canal.' },
      { ruta: 'pagos', titulo: 'Pagos', icono: 'tarjeta', buscar: ['cobros', 'stripe', 'tarjeta', 'cuenta publicitaria', 'reembolsos'], desc: 'Las cuentas que cobran y pagan: ventas, reembolsos y disputas, y el vigía que avisa si algo se frena.' },
      { ruta: 'agentes', titulo: 'Equipo de IA', icono: 'robot', buscar: ['agentes', 'ia', 'inteligencia artificial', 'costo de ia', 'qué hizo la ia'], desc: 'Qué hizo cada IA, cuándo lo hizo y cuánto costó.' },
      { ruta: 'sistema', titulo: 'Salud del sistema', icono: 'engranaje', buscar: ['sistema', 'salud', 'funciona', 'pausa', 'freno', 'comprobar'], desc: 'Si todo funciona bien: pausa general, freno de la captura de anuncios y botones para comprobar.' },
    ],
  },
  {
    grupo: 'Países', pieza: 6,
    ayuda: 'Cada idioma o país nuevo: qué falta para lanzarlo y qué exige la ley en cada uno.',
    buscar: ['idiomas', 'mercados', 'lanzamiento de idioma', 'legal'],
    items: [
      { ruta: 'paises', titulo: 'Países', icono: 'mundo', buscar: ['idiomas', 'mercados', 'impuestos', 'iva'], desc: 'Qué idiomas y países están listos para lanzar y qué falta en cada uno.' },
      { ruta: 'cumplimiento', titulo: 'Cumplimiento', icono: 'cumplimiento', buscar: ['políticas', 'permiso', 'aprobación legal', 'sello', 'visto bueno'], desc: 'Las revisiones de cumplimiento que dejan (o no) prender una oferta, con su visto bueno firmado vigente.' },
    ],
  },
  {
    grupo: 'Dinero y reglas',
    ayuda: 'Lo que fijas tú: el dinero que entra y sale, los topes y quién decide qué.',
    buscar: ['dinero', 'reglas', 'topes', 'límites', 'gobierno'],
    items: [
      { ruta: 'finanzas', titulo: 'Finanzas', icono: 'cartera', buscar: ['plata', 'ganancia', 'gastos', 'ingresos', 'libro de movimientos'], desc: 'Cuánto entra, cuánto sale y cuánto queda: libro de movimientos, ganancia real, conciliación y alertas de gasto.' },
      { ruta: 'parametros', titulo: 'Límites y reglas', icono: 'ajustes', buscar: ['parámetros', 'parametros', 'límites', 'topes', 'configuración', 'máximos'], desc: 'Los topes y reglas que fijas tú, los que siguen sin definir y las propuestas que esperan tu firma.' },
      { ruta: 'quien-decide', titulo: 'Quién decide qué', icono: 'escudo', buscar: ['autonomía', 'aprobaciones', 'permisos', 'frenos'], desc: 'Qué decide el sistema solo, qué decides tú y qué frenos no se saltan nunca.' },
    ],
  },
];

/** NAV con la letra del atajo `g` + letra de cada pantalla (la usan el tooltip del menú, la paleta y la ayuda). */
export const NAV = GRUPOS.map((g) => ({ ...g, items: g.items.map((it) => ({ ...it, atajo: atajoDeRuta(it.ruta) })) }));

/** Todas las entradas planas (para búsquedas por ruta); cada una lleva su `grupo` literal y su `pieza` (1..6, o undefined en los grupos sin número). */
export const ENTRADAS = NAV.flatMap((g) => g.items.map((i) => ({ ...i, grupo: g.grupo, pieza: g.pieza })));
/** Rutas que cargan módulo (incluye alias como `oferta`). */
export const RUTAS_MODULO = [...new Set(ENTRADAS.flatMap((e) => [e.ruta, ...(e.alias || [])]))];
/** Rutas de desarrollo: se cargan pero no aparecen en el menú. */
export const RUTAS_DEV = ['_diseno'];
// «Cómo funciona» (#/flujo, pedido del dueño 2026-11-13): el sistema de ofertas como flujo vivo. Vive solo en el menú del modo «negocio»
// (no entra en las piezas del panel completo ni en sus atajos), pero la ruta se abre en los dos modos.
export const ENTRADA_FLUJO = { ruta: 'flujo', titulo: 'Cómo funciona', icono: 'pulso', grupo: 'El sistema', buscar: ['flujo', 'procesos', 'skills', 'sistema', 'cómo funciona', 'qué corre solo', 'brechas'], desc: 'El sistema de ofertas como un flujo vivo: qué skill hace cada paso, cuándo se activa, quién decide y qué ofertas están ahí ahora.' };
export const RUTAS_EXTRA = [ENTRADA_FLUJO.ruta];
const TITULOS_DEV = { _diseno: 'Galería de componentes' };

// ───────────────────────── modo del panel: «negocio» (por defecto) o «completo» ─────────────────────────
//
// Pedido del dueño (2026-11-12): «simplificá el dashboard a lo mínimo que sea decision maker». Hoy todo se hace desde sesiones de Claude con la
// guía modelar-y-lanzar-oferta; lo único que se mira son los números. Por eso el panel abre en modo «negocio»: solo la pantalla Negocio y un acceso
// por oferta, sin barra de freno, pausa, DEMO ni selector. Nada se borró: con `?modo=completo` en la dirección (antes del #) vuelve el panel entero
// y queda recordado en este navegador; `?modo=negocio` vuelve al modo simple.

export const MODOS = ['negocio', 'completo'];
export const CLAVE_MODO = 'panel.modo';
/** Rutas que se ven en el modo «negocio»; cualquier otra lleva a #/negocio. */
export const RUTAS_MODO_NEGOCIO = ['negocio', 'flujo'];

/** Modo del panel a partir de `location.search` y lo recordado (localStorage). Sin nada: «negocio». */
export function modoDelPanel(search, almacen) {
  let pedido = null;
  try { pedido = new URLSearchParams(String(search || '')).get('modo'); } catch (_) { pedido = null; }
  if (MODOS.includes(pedido)) {
    try { if (almacen) almacen.setItem(CLAVE_MODO, pedido); } catch (_) { /* sin almacenamiento */ }
    return pedido;
  }
  try { if (almacen && almacen.getItem(CLAVE_MODO) === 'completo') return 'completo'; } catch (_) { /* sin almacenamiento */ }
  return 'negocio';
}

/** ¿Se puede abrir esta ruta en este modo? En «negocio» solo Negocio (y sus fichas) y «Cómo funciona». */
export function rutaPermitida(modo, ruta) {
  return modo === 'completo' || RUTAS_MODO_NEGOCIO.includes(ruta);
}

/** Menú del modo «negocio»: un grupo con la pantalla Negocio (las fichas de cada oferta se agregan al cargar los datos). */
export function navDelModo(modo) {
  if (modo === 'completo') return NAV;
  const negocio = ENTRADAS.find((e) => e.ruta === 'negocio');
  return [{ grupo: 'Negocio', ayuda: 'Si estamos ganando o perdiendo, oferta por oferta, y qué conviene hacer con cada una.', buscar: ['negocio'], items: [{ ...negocio, titulo: 'Todas las ofertas' }, { ...ENTRADA_FLUJO }] }];
}

const RE_RUTA = /^_?[a-z][a-z0-9_-]{0,39}$/;

function decodificar(s) { try { return decodeURIComponent(s); } catch (_) { return s; } }

/**
 * '#/oferta/OF-1?x=y' → {ruta:'oferta', params:{id:'OF-1', x:'y'}, segmentos:['OF-1'], valida:true}.
 * Vacío, '#', '#/' → resumen. Los parámetros nunca pisan `id`.
 */
export function parsearHash(hash) {
  let h = String(hash || '');
  if (h.startsWith('#')) h = h.slice(1);
  const iq = h.indexOf('?');
  const camino = iq === -1 ? h : h.slice(0, iq);
  const consulta = iq === -1 ? '' : h.slice(iq + 1);
  const segmentos = camino.split('/').filter(Boolean).map(decodificar);
  const params = {};
  if (consulta) {
    for (const par of consulta.split('&')) {
      if (!par) continue;
      const ie = par.indexOf('=');
      const k = decodificar(ie === -1 ? par : par.slice(0, ie));
      const v = ie === -1 ? '' : decodificar(par.slice(ie + 1).replace(/\+/g, ' '));
      if (k && k !== '__proto__' && k !== 'constructor' && k !== 'prototype') params[k] = v;
    }
  }
  if (segmentos.length === 0) return { ruta: 'resumen', params, segmentos: [], valida: true };
  const [ruta, ...resto] = segmentos;
  const valida = RE_RUTA.test(ruta);
  if (resto.length) params.id = resto[0];
  if (resto.length > 1) params.resto = resto.slice(1);
  return { ruta: valida ? ruta : 'invalida', params, segmentos: resto, valida };
}

/** Rótulo del título de sección del sidebar: «3 · Jurado» (las 6 piezas) o «El sistema» / «Dinero y reglas» (sin número). */
export { etiquetaGrupo };

/** Texto del tooltip de un grupo: su frase de negocio, con «Pieza N de 6» delante si es una de las seis piezas. */
export function ayudaDeGrupo(g) {
  const n = Number(g && g.pieza);
  const frase = String((g && g.ayuda) || '');
  return Number.isInteger(n) && n > 0 ? `Pieza ${n} de 6. ${frase}` : frase;
}

/** Id estable y válido para el título de un grupo («Fábrica y tienda» → «nav-g-fabrica-y-tienda»). */
export function idGrupo(grupo) {
  return `nav-g-${normalizar(grupo).replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '')}`;
}

/** Entrada del sidebar que debe resaltarse para una ruta (oferta → ofertas). */
export function entradaDeRuta(ruta) {
  return ENTRADAS.find((e) => e.ruta === ruta || (e.alias || []).includes(ruta)) || (ruta === ENTRADA_FLUJO.ruta ? ENTRADA_FLUJO : null);
}

/**
 * Migas del shell para una ruta: «Testeo y escala › Ofertas › OF-1». La última es la pantalla actual (sin enlace). El grupo va con su nombre literal
 * (sin el número de pieza) y se omite cuando se llama igual que la pantalla («Cerebro › Cerebro», «Jurado › Jurado», «Robots › Robots», «Países › Países»).
 */
export function migasDeRuta(ruta, params = {}) {
  const ent = entradaDeRuta(ruta);
  if (!ent) return TITULOS_DEV[ruta] ? [{ texto: 'Desarrollo' }, { texto: TITULOS_DEV[ruta] }] : [];
  const migas = normalizar(ent.grupo) === normalizar(ent.titulo) ? [] : [{ texto: ent.grupo }];
  if (params && params.id) { migas.push({ texto: ent.titulo, ruta: ent.ruta }); migas.push({ texto: String(params.id) }); } else migas.push({ texto: ent.titulo });
  return migas;
}

/**
 * Construye el <nav> del sidebar (sin estado ni red; con el DOM falso también se prueba): un bloque por grupo con su título de sección
 * («1 · Cerebro»… o «El sistema»), la frase de la pieza como tooltip (y para lectores de pantalla) y un enlace por pantalla con icono, `desc` y atajo.
 * Devuelve {nav, itemsNav: Map(ruta → {a, badge, pronto})}; el shell rellena después los contadores y los «pronto».
 */
export function construirNav(grupos = NAV) {
  const nav = el('nav', { class: 'nav', 'aria-label': 'Navegación principal' });
  const itemsNav = new Map();
  for (const g of grupos) {
    const gid = idGrupo(g.grupo);
    const lista = el('ul', { class: 'nav__lista', 'aria-labelledby': gid, 'aria-describedby': `${gid}-ayuda` });
    for (const it of g.items) {
      const badge = el('span', { class: 'nav__badge', hidden: true });
      const pronto = el('span', { class: 'nav__pronto', hidden: true, title: 'Próximamente: esta pantalla todavía se está preparando', role: 'img', 'aria-label': 'próximamente' }, icono('reloj', { tam: 12 }));
      const a = el('a', { class: 'nav__item', href: `#/${it.ruta}`, title: `${it.titulo}${it.atajo ? ` (g ${it.atajo})` : ''} — ${it.desc}`, 'data-ruta': it.ruta },
        icono(it.icono, { tam: 18, clase: 'nav__icono' }), el('span', { class: 'nav__texto' }, it.titulo),
        badge, pronto);
      itemsNav.set(it.ruta, { a, badge, pronto });
      lista.appendChild(el('li', null, a));
    }
    // título de sección = «3 · Jurado» (las seis piezas) o «El sistema» / «Dinero y reglas»; el tooltip explica la pieza en una frase y los lectores de pantalla la oyen en la lista
    nav.appendChild(el('div', { class: 'nav__grupo', 'data-grupo': g.grupo },
      el('h2', { class: 'nav__grupo-titulo', id: gid, title: ayudaDeGrupo(g) }, etiquetaGrupo(g)),
      el('p', { class: 'solo-lectores', id: `${gid}-ayuda` }, ayudaDeGrupo(g)),
      lista));
  }
  return { nav, itemsNav };
}

/** Cuenta gates pendientes (suma de `gates_pendientes`) en el listado de ofertas. */
export function contarGates(ofertas) {
  let n = 0;
  for (const o of Array.isArray(ofertas) ? ofertas : []) if (Array.isArray(o && o.gates_pendientes)) n += o.gates_pendientes.length;
  return n;
}

/**
 * Contadores del menú lateral (puro): {resumen, ofertas, registro, sistema}. `resumen` = gates que esperan tu firma; `ofertas` = ofertas listadas;
 * `registro` = eventos nuevos desde tu última visita; `sistema` = 'critico' si hay PAUSA o freno activos (null si no).
 */
export function contadoresNav({ ofertas = [], sistema = null, nuevosRegistro = 0 } = {}) {
  const lista = Array.isArray(ofertas) ? ofertas : [];
  const pausa = Boolean(sistema && sistema.pausa && sistema.pausa.activa);
  const freno = Boolean(sistema && sistema.freno_captura && sistema.freno_captura.activo);
  return {
    resumen: contarGates(lista),
    ofertas: lista.length,
    registro: Math.max(0, Number(nuevosRegistro) || 0),
    sistema: pausa || freno ? 'critico' : null,
  };
}

/** Rebote: junta eventos y llama a `fn(lote)` tras `ms` sin eventos nuevos. */
export function crearRebote(fn, ms = 400, { poner = (f, t) => setTimeout(f, t), quitar = (h) => clearTimeout(h) } = {}) {
  let lote = [];
  let h = null;
  return {
    empujar(ev) { lote.push(ev); if (h !== null) quitar(h); h = poner(() => { h = null; const l = lote; lote = []; fn(l); }, ms); },
    pendiente() { return lote.length; },
    cancelar() { if (h !== null) quitar(h); h = null; lote = []; },
  };
}

/** ¿Debe una página con `meta.escucha` reaccionar a este evento? (sin `escucha`: a todos). */
export function escuchaEvento(meta, ev) {
  const lista = meta && Array.isArray(meta.escucha) ? meta.escucha : null;
  if (!lista || lista.length === 0) return true;
  if (!ev || ev.tipo === 'sondeo') return true;
  return lista.includes(ev.tipo);
}

/** Grupos de la ayuda de atajos (`?`): datos puros para la vista y para las pruebas. Un bloque por grupo del menú (mismo orden y mismos rótulos) y uno «General». */
export function gruposAtajos() {
  return [
    ...NAV.map((g) => ({ titulo: etiquetaGrupo(g), filas: g.items.filter((e) => e.atajo).map((e) => ({ texto: e.titulo, teclas: ['g', e.atajo] })) })).filter((b) => b.filas.length),
    {
      titulo: 'General',
      filas: [
        { texto: 'Buscar una pantalla, una oferta o una acción', teclas: ['Ctrl/⌘', 'K'] },
        { texto: 'Buscar (otra forma)', teclas: ['/'] },
        { texto: 'Ver esta ayuda', teclas: ['?'] },
        { texto: 'Cerrar paneles y ventanas', teclas: ['Esc'] },
      ],
    },
  ];
}

// ───────────────────────── arranque (solo en el navegador) ─────────────────────────

const navegador = typeof window !== 'undefined' && typeof document !== 'undefined';
if (navegador) {
  iniciar();
}

function iniciar() {
  api.iniciarToken();
  const raiz = document.getElementById('app');
  if (!raiz) return;
  ui.instalarPreferencias();
  aplicarTema();

  // ── estructura ──
  const hijosIniciales = document.getElementById('arranque');
  if (hijosIniciales) hijosIniciales.remove();

  const modulos = new Map(); // ruta → {estado: 'ok'|'falta'|'error', mod, error}
  let pagina = null; // {ruta, mod, ctx, salidas:[]}
  let tokenNav = 0;
  let pendienteRerender = false;
  let nuevosRegistro = 0;
  let rutaActual = 'resumen';
  const esMac = /Mac|iPhone|iPad/i.test((navigator && (navigator.platform || navigator.userAgent)) || '');
  const teclaMod = esMac ? '⌘' : 'Ctrl';

  const modo = modoDelPanel(location.search, (() => { try { return window.localStorage; } catch (_) { return null; } })());
  raiz.dataset.modo = modo;
  const { nav, itemsNav } = construirNav(navDelModo(modo));
  const navOfertas = el('ul', { class: 'nav__lista', 'aria-label': 'Fichas de las ofertas' });
  const itemsOfertas = new Map(); // id de oferta → <a>
  if (modo === 'negocio') {
    nav.appendChild(el('div', { class: 'nav__grupo', 'data-grupo': 'Ofertas' }, el('h2', { class: 'nav__grupo-titulo' }, 'Ofertas'), navOfertas));
  }

  const botonColapsar = el('button', { type: 'button', class: 'btn btn--fantasma btn--icono nav__colapsar', onclick: () => estado.fijar({ sidebarColapsada: !estado.sidebarColapsada }) }, icono('panel'));
  const botonAtajos = el('button', { type: 'button', class: 'btn btn--fantasma btn--icono', 'aria-label': 'Atajos de teclado', title: 'Ver los atajos de teclado (?)', onclick: () => abrirAyudaAtajos() }, icono('teclado'));
  const versionEl = el('span', { class: 'texto-tenue sidebar__version' });
  const sidebar = el('aside', { class: 'sidebar', id: 'sidebar' },
    el('div', { class: 'sidebar__marca' }, el('span', { class: 'marca__logo', 'aria-hidden': 'true' }, icono('pulso', { tam: 16 })), el('span', { class: 'marca__texto' }, 'Fábrica de ofertas')),
    nav,
    el('div', { class: 'sidebar__pie' }, botonColapsar, versionEl, modo === 'completo' ? botonAtajos : null));

  // topbar
  const botonMenu = el('button', { type: 'button', class: 'btn btn--icono topbar__menu', 'aria-label': 'Abrir menú', 'aria-controls': 'sidebar', onclick: () => alternarMenu() }, icono('menu'));
  const tituloEl = el('div', { class: 'topbar__titulo', role: 'presentation' }, 'Panel');
  const selector = el('select', { class: 'campo campo--chico selector-oferta', id: 'oferta-activa', 'aria-label': 'Oferta activa', title: 'Oferta activa: las pantallas que lo permiten muestran los datos de la oferta que elijas aquí.', onchange: (ev) => estado.fijar({ ofertaActiva: ev.target.value || null }) });
  const buscador = el('button', { type: 'button', class: 'buscador', 'aria-label': `Buscar o ir a… (${teclaMod} K)`, 'aria-haspopup': 'dialog', title: `Buscar una pantalla, una oferta o una acción (${teclaMod} K o /)`, onclick: () => abrirPaleta() },
    icono('lupa', { tam: 15 }), el('span', { class: 'buscador__texto' }, 'Buscar…'), ui.kbd(teclaMod, 'K'));
  const vivoPunto = el('span', { class: 'vivo__punto', 'aria-hidden': 'true' });
  const vivoTexto = el('span', { class: 'vivo__texto' }, 'SIN CONEXIÓN');
  const vivo = el('span', { class: 'vivo vivo--sin_conexion', role: 'status', 'aria-live': 'polite' }, vivoPunto, vivoTexto);
  const pausaEl = el('a', { class: 'estado-pill', href: '#/sistema' });
  const frenoEl = el('a', { class: 'estado-pill', href: '#/sistema' });
  const demoEl = el('span', { class: 'chip chip--info', hidden: true, title: 'Estás viendo datos de demostración (una oferta de ejemplo), no datos reales.' }, 'DEMO');
  const botonPausar = el('button', { type: 'button', class: 'btn btn--peligro-suave', 'aria-label': 'Pausar todo', onclick: () => pausarTodo() }, icono('pausa', { tam: 14 }), el('span', { class: 'btn__texto' }, 'Pausar todo'));
  const botonTema = el('button', { type: 'button', class: 'btn btn--fantasma btn--icono', onclick: () => ciclarTema() });
  const swTecnico = ui.interruptor({
    etiqueta: 'Detalle técnico', activo: estado.modoTecnico,
    titulo: 'Detalle técnico: muestra de una vez, en todas las pantallas, los archivos, las huellas, los comandos y los datos en bruto.',
    onCambio: (v) => { estado.fijar({ modoTecnico: v }); anunciar(v ? 'Detalle técnico activado' : 'Detalle técnico desactivado'); },
  });
  const segDensidad = ui.segmentado({
    etiqueta: 'Espacio entre filas', valor: estado.densidad,
    opciones: [{ valor: 'comoda', etiqueta: 'Filas amplias', icono: 'menu' }, { valor: 'compacta', etiqueta: 'Filas compactas', icono: 'densidad' }],
    onCambio: (v) => { estado.fijar({ densidad: v }); anunciar(v === 'compacta' ? 'Filas compactas' : 'Filas amplias'); },
  });
  // modo «negocio»: barra mínima (menú en el celular, título y tema); el selector, DEMO, buscador, freno, pausa y «Pausar todo» solo en el modo completo
  const topbar = modo === 'completo'
    ? el('header', { class: 'topbar' },
      botonMenu, tituloEl,
      el('div', { class: 'topbar__ctl' },
        el('label', { class: 'selector', for: 'oferta-activa' }, icono('caja', { tam: 15 }), el('span', { class: 'solo-lectores' }, 'Oferta activa'), selector),
        demoEl, buscador,
        el('div', { class: 'topbar__prefs' }, swTecnico, segDensidad, ocultar.botonOcultar(ui), botonTema)),
      el('div', { class: 'topbar__der' },
        el('div', { class: 'topbar__estados' }, vivo, pausaEl, frenoEl),
        botonPausar))
    : el('header', { class: 'topbar topbar--negocio' }, botonMenu, tituloEl, el('div', { class: 'topbar__der' }, botonTema));

  const principal = el('main', { class: 'principal', id: 'contenido', tabindex: '-1' });
  const anuncio = el('div', { class: 'solo-lectores', role: 'status', 'aria-live': 'polite' });
  const telon = el('div', { class: 'telon', onclick: () => alternarMenu(false) });
  const saltar = el('button', { type: 'button', class: 'saltar', onclick: () => principal.focus() }, 'Saltar al contenido');

  raiz.append(saltar, sidebar, telon, topbar, principal, anuncio);
  // «Ocultar info» (dueño, 13-nov, para grabar la pantalla): difumina nombres, productos, anuncios, referentes o dinero en todo el panel.
  // Al prender o apagar los nombres, la dirección de la ficha pasa de #/negocio/<nombre> a #/negocio/~N (o al revés) y se repinta.
  ocultar.instalar(ui);
  let idsNav = [];
  ocultar.alCambiar(() => {
    const { ruta, params } = parsearHash(location.hash);
    if (ruta === 'negocio' && params.id && idsNav.length) {
      const real = ocultar.resolverRef(params.id, idsNav);
      const ref = ocultar.refOferta(real, idsNav);
      if (ref !== params.id) {
        const q = location.hash.includes('?') ? location.hash.slice(location.hash.indexOf('?')) : '';
        history.replaceState(null, '', `${location.pathname}${location.search}#/negocio/${encodeURIComponent(ref)}${q}`);
      }
    }
    pintarOfertasNav();
    recargarPagina({ conservar: true });
  });

  function anunciar(texto) { anuncio.textContent = texto; }

  // ── tema, sidebar, menú móvil ──
  function temaEfectivo() {
    if (estado.tema !== 'auto') return estado.tema;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'oscuro' : 'claro';
  }
  function aplicarTema() {
    document.documentElement.dataset.tema = estado.tema;
  }
  function pintarBotonTema() {
    const ef = temaEfectivo();
    limpiar(botonTema);
    botonTema.appendChild(icono(ef === 'oscuro' ? 'luna' : 'sol'));
    const nombre = { auto: 'automático', claro: 'claro', oscuro: 'oscuro' }[estado.tema];
    botonTema.setAttribute('aria-label', `Tema ${nombre}. Cambiar tema`);
    botonTema.title = `Tema: ${nombre} (clic para cambiar)`;
  }
  function ciclarTema() {
    const orden = ['claro', 'oscuro', 'auto'];
    const sig = orden[(orden.indexOf(estado.tema) + 1) % orden.length];
    estado.fijar({ tema: sig });
  }
  function pintarSidebar() {
    raiz.dataset.colapsada = String(estado.sidebarColapsada);
    botonColapsar.setAttribute('aria-label', estado.sidebarColapsada ? 'Ensanchar el menú lateral' : 'Achicar el menú lateral');
    botonColapsar.setAttribute('aria-expanded', String(!estado.sidebarColapsada));
    botonColapsar.title = estado.sidebarColapsada ? 'Ensanchar el menú' : 'Achicar el menú';
  }
  function alternarMenu(forzar) {
    const abrir = forzar === undefined ? raiz.dataset.menu !== 'abierto' : forzar;
    raiz.dataset.menu = abrir ? 'abierto' : 'cerrado';
    botonMenu.setAttribute('aria-expanded', String(abrir));
  }
  if (window.matchMedia) {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    (mq.addEventListener ? mq.addEventListener.bind(mq, 'change') : mq.addListener.bind(mq))(() => pintarBotonTema());
  }
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape' && raiz.dataset.menu === 'abierto') alternarMenu(false); });

  // ── indicadores globales (PAUSA, freno, EN VIVO, selector, badges) ──
  const ROTULOS_VIVO = { sse: 'EN VIVO', sondeo: 'CADA 5 s', sin_conexion: 'SIN CONEXIÓN' };
  const TITULOS_VIVO = {
    sse: 'Conectado: los cambios aparecen en el momento en que ocurren.',
    sondeo: 'La conexión en vivo no está disponible: el panel pregunta por novedades cada 5 segundos, así que los cambios pueden tardar un poco.',
    sin_conexion: 'El panel no logra comunicarse con el programa que corre en tu computadora. Está reintentando…',
  };

  function pintarVivo() {
    const c = estado.conectado;
    vivo.className = `vivo vivo--${c}`;
    vivoTexto.textContent = ROTULOS_VIVO[c];
    vivo.title = TITULOS_VIVO[c];
    vivo.setAttribute('aria-label', `Conexión: ${ROTULOS_VIVO[c]}. ${TITULOS_VIVO[c]}`);
  }

  function pintarPill(nodo, { tono, icon, texto, corto, titulo }) {
    nodo.className = `estado-pill estado-pill--${tono}`;
    limpiar(nodo);
    nodo.append(icono(icon, { tam: 14 }), el('span', { class: 'pill__largo' }, texto), el('span', { class: 'pill__corto' }, corto || texto));
    nodo.title = titulo;
    nodo.setAttribute('aria-label', `${texto}. ${titulo}`);
  }

  function pintarSistema() {
    const s = estado.sistema;
    const pausa = s && s.pausa;
    const freno = s && s.freno_captura;
    // PAUSA: icono + etiqueta (crítico si está activa)
    if (!s) pintarPill(pausaEl, { tono: 'neutro', icon: 'circulo-punteado', texto: 'PAUSA: sin dato', corto: 'Pausa: ?', titulo: 'Pausa general (freno de emergencia): todavía no se pudo saber si está puesta. Toca para ir a la pantalla Salud del sistema.' });
    else if (pausa && pausa.activa) pintarPill(pausaEl, { tono: 'critico', icon: 'octogono', texto: 'PAUSA ACTIVA', corto: 'PAUSA', titulo: `Pausa general (freno de emergencia) puesta desde ${fmt.fecha(pausa.desde)}${pausa.motivo ? ' — ' + pausa.motivo : ''}. El sistema no gasta ni activa nada hasta que una persona la levante. Toca para ver cómo.` });
    else pintarPill(pausaEl, { tono: 'ok', icon: 'ok', texto: 'Pausa: no', corto: 'Pausa: no', titulo: 'Pausa general (freno de emergencia): no está puesta, así que el sistema puede trabajar dentro de sus límites. Toca para ir a la pantalla Salud del sistema.' });
    // freno de captura
    const frenoActivo = Boolean(freno && freno.activo);
    if (!s) pintarPill(frenoEl, { tono: 'neutro', icon: 'circulo-punteado', texto: 'Freno: sin dato', corto: 'Freno: ?', titulo: 'Freno de la captura de anuncios: todavía no se pudo saber si está puesto. Toca para ir a la pantalla Salud del sistema.' });
    else if (frenoActivo) pintarPill(frenoEl, { tono: 'critico', icon: 'octogono', texto: 'FRENO ACTIVO', corto: 'FRENO', titulo: `El sistema frenó la captura de anuncios desde ${fmt.fecha(freno.ts)}${freno.motivo ? ' — ' + freno.motivo : ''}. Solo una persona puede levantar este freno.` });
    else pintarPill(frenoEl, { tono: 'ok', icon: 'ok', texto: 'Freno: libre', corto: 'Freno: no', titulo: 'Freno de la captura de anuncios: libre. La captura puede seguir; el sistema la frena solo si una fuente bloquea una visita.' });
    demoEl.hidden = !(s && s.modo_demo);
    // botón pausar
    const yaPausa = Boolean(pausa && pausa.activa);
    botonPausar.disabled = yaPausa;
    botonPausar.title = yaPausa ? 'La pausa ya está puesta; solo una persona puede levantarla, a mano.' : 'Pausar todo: frena de inmediato todo el gasto y toda activación nueva. Te pide confirmar y escribir un motivo; solo tú puedes levantar la pausa después.';
    versionEl.textContent = s && s.panel && s.panel.version ? `v${s.panel.version}` : '';
    pintarBadges();
  }

  function pintarSelector() {
    const ofs = estado.ofertas || [];
    limpiar(selector);
    selector.appendChild(el('option', { value: '' }, ofs.length ? 'Todas las ofertas' : 'Sin ofertas'));
    const ids = new Set();
    for (const o of ofs) {
      if (!o || !o.oferta_id) continue;
      ids.add(o.oferta_id);
      selector.appendChild(el('option', { value: o.oferta_id }, `${o.oferta_id}${o.demo ? ' (demo)' : ''}`));
    }
    if (estado.ofertaActiva && !ids.has(estado.ofertaActiva)) selector.appendChild(el('option', { value: estado.ofertaActiva }, `${estado.ofertaActiva} (no listada)`));
    selector.value = estado.ofertaActiva || '';
  }

  function fijarBadge(ruta, { texto, clase, titulo }) {
    const it = itemsNav.get(ruta);
    if (!it) return;
    it.badge.hidden = texto === null || texto === undefined || texto === '';
    it.badge.className = `nav__badge${clase ? ` ${clase}` : ''}`;
    it.badge.textContent = texto === null || texto === undefined ? '' : String(texto);
    it.badge.title = titulo || '';
  }

  function pintarBadges() {
    const c = contadoresNav({ ofertas: estado.ofertas, sistema: estado.sistema, nuevosRegistro });
    fijarBadge('resumen', { texto: c.resumen || null, titulo: `${c.resumen} paso(s) esperan tu firma` });
    fijarBadge('ofertas', { texto: c.ofertas || null, clase: 'nav__badge--suave', titulo: `${c.ofertas} oferta(s) en el panel` });
    fijarBadge('registro', { texto: c.registro ? (c.registro > 99 ? '99+' : c.registro) : null, clase: 'nav__badge--suave', titulo: `${c.registro} evento(s) nuevo(s) desde tu última visita` });
    fijarBadge('sistema', { texto: c.sistema ? '!' : null, clase: 'nav__badge--critico', titulo: 'Hay una pausa general o un freno de la captura de anuncios puestos' });
  }

  function pintarModulos() {
    for (const e of ENTRADAS) {
      const it = itemsNav.get(e.ruta);
      if (!it) continue; // modo «negocio»: las pantallas ocultas no tienen entrada en el menú
      const m = modulos.get(e.ruta);
      const falta = Boolean(m && m.estado === 'falta');
      it.pronto.hidden = !falta;
      it.a.classList.toggle('nav__item--pronto', falta);
    }
  }

  function marcarActivo(ruta) {
    const ent = entradaDeRuta(ruta);
    for (const [r, it] of itemsNav) {
      if (ent && ent.ruta === r) it.a.setAttribute('aria-current', 'page'); else it.a.removeAttribute('aria-current');
    }
    // con ocho grupos el menú puede ser más alto que la ventana: la pantalla actual (p. ej. tras `g` + letra) debe verse sin desplazarlo a mano
    const activo = ent && itemsNav.get(ent.ruta);
    if (activo && typeof activo.a.scrollIntoView === 'function') activo.a.scrollIntoView({ block: 'nearest' });
    if (modo === 'negocio') {
      const id = ocultar.resolverRef(parsearHash(location.hash).params.id || null, idsNav);
      for (const [oid, a] of itemsOfertas) { if (ruta === 'negocio' && id === oid) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); }
      const base = itemsNav.get('negocio');
      if (base && id) base.a.removeAttribute('aria-current');
      // una apagada plegada que se abre desde la tabla: se repinta el menú para que aparezca marcada
      if (ruta === 'negocio' && id && !itemsOfertas.has(id) && idsNav.includes(id)) pintarOfertasNav();
    }
  }

  const APAGADAS_VISIBLES = 3;   // cuántas apagadas recientes quedan a la vista en el menú lateral

  // modo «negocio»: un acceso por oferta en el menú lateral (de /negocio; si falla, el menú queda solo con «Todas las ofertas»)
  async function pintarOfertasNav() {
    if (modo !== 'negocio') return;
    let lista = [];
    try { const d = await api.get('/negocio'); lista = d && Array.isArray(d.ofertas) ? d.ofertas : []; } catch (_) { lista = []; }
    limpiar(navOfertas); itemsOfertas.clear();
    idsNav = lista.map((o) => o && o.id);
    ocultar.fijarTerminos(ocultar.terminosDeOfertas(lista));
    // pedido del dueño (13-nov): con 15-20 ofertas, ver de un vistazo en qué etapa está cada una y si tiene backend.
    // Las ofertas van agrupadas por etapa (lo urgente arriba) y cada una lleva su marca «B» de backend; el color de identidad sigue al libro.
    if (typeof ui.instalarEstilos === 'function') ui.instalarEstilos('negocio-etapas', CSS_ETAPAS);
    const indice = new Map(lista.map((o, i) => [o && o.id, i]));
    if (lista.length) {
      navOfertas.appendChild(el('li', { class: 'nav__leyenda', 'aria-hidden': 'true' },
        el('span', null, marcaBackend(ui, { estado: 'activo' }), ' backend'), el('span', null, marcaBackend(ui, { falta: true }), ' falta')));
    }
    // pedido del dueño (17-nov): las apagadas van a ser cientos; se ven solo las últimas (por la hora REAL del apagado,
    // `apagado_cuando` del servidor, nunca el corte) y el resto se despliega desde el título del grupo.
    const idActual = ocultar.resolverRef(parsearHash(location.hash).params.id || null, idsNav);
    const ahoraMs = Date.now();
    const haceCorto = (iso) => {
      const t = Date.parse(iso || '');
      if (!t) return '';
      const h = Math.max(0, (ahoraMs - t) / 36e5);
      return h < 1 ? `${Math.max(1, Math.round(h * 60))} min` : h < 24 ? `${Math.floor(h)} h` : `${Math.floor(h / 24)} d`;
    };
    for (const g of gruposPorEtapa(lista)) {
      const esApagada = g.etapa.clave === 'apagada';
      const cuando = (o) => Date.parse((o && o.apagado_cuando) || '') || 0;
      const ofertasG = esApagada ? g.ofertas.slice().sort((a, b) => cuando(b) - cuando(a)) : g.ofertas;
      const plegable = esApagada && ofertasG.length > APAGADAS_VISIBLES + 1;
      const abiertas = plegable && localStorage.getItem('nav.apagadas.todas') === '1';
      const visibles = !plegable || abiertas ? ofertasG : ofertasG.filter((o, k) => k < APAGADAS_VISIBLES || (o && o.id === idActual));
      const ocultas = ofertasG.length - visibles.length;
      const titulo = el('li', { class: ['nav__sub', `nav__sub--${tonoEtapa(g.etapa)}`, esApagada && 'nav__sub--apagadas'], title: g.etapa.ayuda || '' },
        el('span', null, g.etapa.texto), el('span', { class: 'nav__sub-n' }, `· ${g.ofertas.length}`));
      if (plegable) {
        const alternar = el('button', { type: 'button', class: 'nav__plegar', 'aria-expanded': String(abiertas),
          title: abiertas ? 'Mostrar solo las últimas apagadas' : `Mostrar las ${ofertasG.length} apagadas` },
          el('span', null, abiertas ? 'menos' : 'todas'), ui.icono(abiertas ? 'chevron-arriba' : 'chevron-abajo', { tam: 12 }));
        alternar.addEventListener('click', () => { localStorage.setItem('nav.apagadas.todas', abiertas ? '0' : '1'); pintarOfertasNav(); });
        titulo.appendChild(alternar);
      }
      navOfertas.appendChild(titulo);
      for (const o of visibles) {
        if (!o || typeof o.id !== 'string') continue;
        const ac = o.accion_sugerida || {};
        const et = o.etapa || {};
        const i = indice.get(o.id) || 0;
        const a = el('a', { class: ['nav__item', 'nav__item--oferta', esApagada && 'nav__item--apagada', `ng-id-${(i % 6) + 1}`], href: `#/negocio/${encodeURIComponent(ocultar.refOferta(o.id, idsNav))}`,
          title: [o.nombre, et.corto || et.texto, esApagada && o.apagado_cuando ? `apagada el ${new Date(o.apagado_cuando).toLocaleString('es-AR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}` : null, ac.texto, o.backend && o.backend.texto].filter(Boolean).join(' — ') },
          el('span', { class: 'ng-id-punto', 'aria-hidden': 'true' }), banderas(ui, o.mercado), el('span', { class: 'nav__texto' }, String(o.nombre || o.id)),
          esApagada ? el('span', { class: 'nav__hace' }, haceCorto(o.apagado_cuando)) : marcaBackend(ui, o.backend));
        itemsOfertas.set(o.id, a);
        navOfertas.appendChild(el('li', null, a));
      }
      if (plegable && ocultas > 0) {
        const mas = el('button', { type: 'button', class: 'nav__mas', 'aria-expanded': 'false' },
          el('span', { class: 'nav__texto' }, `+ ${ocultas} más antiguas`));
        mas.addEventListener('click', () => { localStorage.setItem('nav.apagadas.todas', '1'); pintarOfertasNav(); });
        navOfertas.appendChild(el('li', null, mas));
      }
    }
    marcarActivo(rutaActual);
  }

  estado.suscribir((_e, cambios) => {
    if (cambios.includes('tema')) { aplicarTema(); pintarBotonTema(); }
    if (cambios.includes('sidebarColapsada')) pintarSidebar();
    if (cambios.includes('conectado')) pintarVivo();
    if (cambios.includes('sistema')) pintarSistema();
    if (cambios.includes('ofertas')) { pintarSelector(); pintarBadges(); }
    if (cambios.includes('modoTecnico')) swTecnico.fijar(estado.modoTecnico);
    if (cambios.includes('densidad')) segDensidad.fijar(estado.densidad);
    if (cambios.includes('ofertaActiva')) { pintarSelector(); recargarPagina({ conservar: true }); }
  });

  async function refrescarGlobal() {
    const [s, o] = await Promise.allSettled([api.get('/sistema'), api.get('/ofertas')]);
    const parche = {};
    if (s.status === 'fulfilled' && s.value && typeof s.value === 'object') parche.sistema = s.value;
    if (o.status === 'fulfilled' && Array.isArray(o.value)) { parche.ofertas = o.value; ocultar.fijarTerminos(ocultar.terminosDeCarpetas(o.value), 'carpetas'); }
    estado.fijar(parche);
    pintarSistema(); pintarSelector(); pintarBadges();
    return { s, o };
  }

  // ── Pausar todo (§6): crea empresa/PAUSA; nunca la borra ──
  function pausarTodo() {
    const motivo = el('textarea', { class: 'campo', rows: '3', 'aria-label': 'Motivo de la pausa', placeholder: 'Motivo (obligatorio): por qué se pausa todo', maxlength: '300' });
    const errorEl = el('p', { class: 'campo-error', role: 'alert', hidden: true });
    modal({
      titulo: 'Pausar todo',
      cuerpo: [
        el('p', null, 'Esto frena de inmediato todo el gasto: el sistema deja de gastar, de activar campañas y de subir presupuestos hasta que una persona levante la pausa.'),
        el('p', { class: 'texto-tenue' }, 'El panel no puede levantar la pausa. Para reanudar, borra a mano el archivo ', el('code', null, 'empresa/PAUSA'), ' (la pantalla Salud del sistema explica cómo).'),
        el('label', { class: 'etiqueta-campo' }, 'Motivo', motivo), errorEl,
      ],
      acciones: [
        { texto: 'Cancelar' },
        {
          texto: 'Pausar todo', tono: 'peligro',
          alClick: async () => {
            const m = motivo.value.trim();
            if (m.length < 3) { errorEl.hidden = false; errorEl.textContent = 'Escribe un motivo de al menos 3 letras.'; motivo.focus(); return false; }
            try {
              await api.post('/pausa', { motivo: m });
              toast('Pausa puesta: el sistema quedó detenido.', 'ok');
              await refrescarGlobal();
              recargarPagina({ conservar: true });
            } catch (err) {
              errorEl.hidden = false; errorEl.textContent = `No se pudo pausar: ${err.mensaje || err.message}`;
              return false;
            }
            return true;
          },
        },
      ],
    });
  }

  // ── ayuda de atajos (?) ──
  function abrirAyudaAtajos() {
    const cuerpo = el('div', { class: 'atajos' }, gruposAtajos().map((g) => el('section', { class: 'atajos__grupo' },
      el('h3', { class: 'atajos__titulo' }, g.titulo),
      g.filas.map((f) => el('div', { class: 'atajos__fila' }, el('span', null, f.texto), ui.kbd(...f.teclas))))));
    modal({
      titulo: 'Atajos de teclado',
      cuerpo: [el('p', { class: 'texto-tenue' }, 'Para ir a una pantalla, aprieta ', ui.kbd('g'), ' y enseguida la letra que figura junto a su nombre.'), cuerpo],
      acciones: [{ texto: 'Cerrar', tono: 'primario' }], ancho: '640px',
    });
  }

  // ── paleta de comandos (Ctrl/⌘+K) ──
  let paletaCerrar = null;
  let skillsCache = { t: 0, lista: [] };

  const ACCIONES_PALETA = [
    { id: 'tecnico', accion: 'tecnico', titulo: 'Mostrar u ocultar el detalle técnico', detalle: 'Muestra u oculta archivos, huellas, comandos y datos en bruto en todas las pantallas', icono: 'terminal', palabras: ['modo', 'tecnico', 'avanzado', 'detalle', 'archivos', 'comandos'] },
    { id: 'densidad', accion: 'densidad', titulo: 'Cambiar el espacio entre filas (amplias o compactas)', detalle: 'Filas de las tablas más altas o más bajas', icono: 'densidad', palabras: ['compacta', 'comoda', 'filas', 'densidad', 'tamaño'] },
    { id: 'tema', accion: 'tema', titulo: 'Cambiar el tema (claro, oscuro o automático)', icono: 'sol', palabras: ['oscuro', 'claro', 'dark', 'light', 'colores', 'modo noche'] },
    { id: 'atajos', accion: 'atajos', titulo: 'Ver los atajos de teclado', detalle: 'Las teclas para moverte más rápido por el panel', icono: 'teclado', atajo: ['?'], palabras: ['ayuda', 'teclas', 'atajos'] },
    { id: 'colapsar', accion: 'colapsar', titulo: 'Achicar o ensanchar el menú lateral', icono: 'panel', palabras: ['sidebar', 'menu', 'colapsar', 'expandir'] },
    { id: 'pausar', accion: 'pausar', titulo: 'Pausar todo…', detalle: 'Frena todo el gasto y toda activación nueva (te pide confirmar y escribir un motivo)', icono: 'pausa', palabras: ['pausa', 'freno', 'emergencia', 'detener', 'parar', 'frenar'] },
    { id: 'galeria', accion: 'galeria', titulo: 'Galería de componentes', detalle: 'Solo desarrollo: sin datos reales', icono: 'chispa', palabras: ['diseno', 'ui', 'componentes'], soloTecnico: true },
  ];

  function ejecutarAccion(clave) {
    switch (clave) {
      case 'tecnico': estado.fijar({ modoTecnico: !estado.modoTecnico }); anunciar(estado.modoTecnico ? 'Detalle técnico activado' : 'Detalle técnico desactivado'); break;
      case 'densidad': estado.fijar({ densidad: estado.densidad === 'comoda' ? 'compacta' : 'comoda' }); anunciar(`Densidad ${estado.densidad === 'compacta' ? 'compacta' : 'cómoda'}`); break;
      case 'tema': ciclarTema(); break;
      case 'atajos': abrirAyudaAtajos(); break;
      case 'colapsar': estado.fijar({ sidebarColapsada: !estado.sidebarColapsada }); break;
      case 'pausar': pausarTodo(); break;
      case 'galeria': location.hash = '#/_diseno'; break;
      default: break;
    }
  }

  function entradasPaleta() {
    return construirEntradas({ nav: NAV, ofertas: estado.ofertas, skills: skillsCache.lista, acciones: ACCIONES_PALETA }, { tecnico: estado.modoTecnico });
  }

  function abrirPaleta() {
    if (paletaCerrar) return;
    cerrarModales();
    const previo = document.activeElement;
    let entradas = entradasPaleta();
    let resultados = buscar(entradas, '');
    let sel = 0;
    const input = el('input', {
      class: 'paleta__input', type: 'text', role: 'combobox', 'aria-expanded': 'true', 'aria-controls': 'paleta-lista', 'aria-autocomplete': 'list', autocomplete: 'off', spellcheck: 'false',
      placeholder: 'Escribe lo que buscas: una pantalla, una oferta o una acción…', 'aria-label': 'Buscar o ir a',
      oninput: () => { resultados = buscar(entradas, input.value); sel = 0; pintar(); },
    });
    const lista = el('div', { class: 'paleta__lista', role: 'listbox', id: 'paleta-lista', 'aria-label': 'Resultados' });
    const caja = el('div', { class: 'paleta', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Paleta de comandos' },
      el('div', { class: 'paleta__campo' }, icono('lupa', { tam: 18 }), input, ui.kbd('Esc')),
      lista,
      el('div', { class: 'paleta__pie' },
        el('span', null, ui.kbd('↑', '↓'), 'moverse'), el('span', null, ui.kbd('↵'), 'abrir'), el('span', null, ui.kbd('Esc'), 'cerrar'), el('span', null, 'Escribe para filtrar. Prueba con «qué hago» o «plata».')));
    const fondo = el('div', { class: 'paleta-fondo', onmousedown: (ev) => { if (ev.target === fondo) cerrar(); } }, caja);

    function elegir(entrada) {
      cerrar();
      if (!entrada) return;
      if (entrada.ruta) location.hash = entrada.ruta;
      else if (entrada.accion) ejecutarAccion(entrada.accion);
    }
    function pintar() {
      limpiar(lista);
      if (!resultados.length) { lista.appendChild(el('div', { class: 'paleta__vacio' }, `No encontré nada para «${input.value}». Prueba con el nombre de una pantalla o de una oferta, o con una palabra como «tareas», «plata» o «pausa».`)); input.removeAttribute('aria-activedescendant'); return; }
      for (const g of agruparPorGrupo(resultados)) {
        lista.appendChild(el('div', { class: 'paleta__grupo', role: 'presentation' }, g.grupo));
        for (const it of g.items) {
          const fila = el('div', {
            class: 'paleta__item', role: 'option', id: `paleta-op-${it.indice}`, 'aria-selected': String(it.indice === sel),
            onmousemove: () => { if (sel !== it.indice) { sel = it.indice; marcar(); } },
            onclick: () => elegir(resultados[it.indice]),
          },
          el('span', { class: 'paleta__icono' }, icono(it.icono || 'flecha-derecha', { tam: 17 })),
          el('span', { class: 'paleta__texto' }, el('span', { class: 'paleta__titulo' }, it.titulo), it.detalle ? el('span', { class: 'paleta__detalle' }, it.detalle) : null),
          it.atajo ? ui.kbd(...it.atajo) : el('span'));
          lista.appendChild(fila);
        }
      }
      marcar();
    }
    function marcar() {
      for (const f of lista.querySelectorAll('.paleta__item')) {
        const activa = f.id === `paleta-op-${sel}`;
        f.setAttribute('aria-selected', String(activa));
        if (activa) { input.setAttribute('aria-activedescendant', f.id); if (typeof f.scrollIntoView === 'function') f.scrollIntoView({ block: 'nearest' }); }
      }
    }
    function alTecla(ev) {
      if (ev.key === 'Escape') { ev.preventDefault(); ev.stopPropagation(); cerrar(); return; }
      if (ev.key === 'Enter') { ev.preventDefault(); elegir(resultados[sel]); return; }
      if (['ArrowDown', 'ArrowUp', 'Home', 'End', 'PageDown', 'PageUp'].includes(ev.key)) {
        if ((ev.key === 'Home' || ev.key === 'End') && input.value) return; // dentro del texto, Inicio/Fin mueven el cursor
        ev.preventDefault(); sel = moverSeleccion(sel, resultados.length, ev.key); marcar(); return;
      }
      if (ev.key === 'Tab') { ev.preventDefault(); input.focus(); }
    }
    function cerrar() {
      if (!paletaCerrar) return;
      paletaCerrar = null;
      document.removeEventListener('keydown', alTecla, true);
      if (fondo.parentNode) fondo.parentNode.removeChild(fondo);
      if (previo && typeof previo.focus === 'function') { try { previo.focus(); } catch (_) { /* el nodo ya no existe */ } }
    }
    paletaCerrar = cerrar;
    document.addEventListener('keydown', alTecla, true);
    document.body.appendChild(fondo);
    pintar();
    input.focus();
    // las skills llegan de la API la primera vez (y se refrescan a los 60 s); si falla, la paleta sigue sirviendo para lo demás
    if (Date.now() - skillsCache.t > 60000) {
      api.get('/skills').then((lista2) => {
        skillsCache = { t: Date.now(), lista: Array.isArray(lista2) ? lista2 : [] };
        if (!paletaCerrar) return;
        entradas = entradasPaleta();
        resultados = buscar(entradas, input.value);
        sel = 0;
        pintar();
      }).catch(() => { skillsCache = { t: Date.now(), lista: skillsCache.lista }; });
    }
  }

  // ── atajos globales ──
  const atajos = crearAtajos({ bloqueado: () => Boolean(paletaCerrar) || Boolean(document.querySelector('.modal-fondo')) });
  document.addEventListener('keydown', (ev) => {
    if (ev.defaultPrevented) return;
    const a = atajos.procesar(ev);
    if (!a) return;
    if (modo === 'negocio' && !(a.tipo === 'ir' && rutaPermitida(modo, a.ruta))) return; // modo simple: sin paleta ni saltos a pantallas ocultas
    if (a.tipo === 'paleta') { ev.preventDefault(); abrirPaleta(); }
    else if (a.tipo === 'ayuda') { ev.preventDefault(); abrirAyudaAtajos(); }
    else if (a.tipo === 'ir') { ev.preventDefault(); location.hash = `#/${a.ruta}`; }
  });

  // ── módulos de página ──
  async function sondearModulo(ruta, { forzar = false } = {}) {
    const previo = modulos.get(ruta);
    if (previo && previo.estado === 'ok') return previo;
    if (previo && !forzar && previo.estado === 'error') return previo;
    const url = `./pages/${ruta}.js`;
    let r;
    try {
      const res = await fetch(url, { cache: 'no-store', credentials: 'omit', headers: { Accept: 'text/javascript' } });
      const tipo = res.headers.get('content-type') || '';
      if (!res.ok || !/javascript|ecmascript/i.test(tipo)) r = { estado: 'falta' };
      else {
        try {
          const mod = await import(url);
          r = typeof mod.render === 'function' ? { estado: 'ok', mod } : { estado: 'error', error: new Error(`La pantalla «${ruta}» está incompleta: le falta la parte que la dibuja (pages/${ruta}.js)`) };
        } catch (err) { r = { estado: 'error', error: err }; }
      }
    } catch (err) { r = { estado: 'falta' }; }
    modulos.set(ruta, r);
    return r;
  }

  async function sondearTodos() {
    await Promise.all(RUTAS_MODULO.map((r) => sondearModulo(r)));
    pintarModulos();
  }

  // ── ciclo de vida de páginas ──
  function crearCtx(ruta, params) {
    const salidas = [];
    const ctx = {
      api, ui, fmt, params, estado, ruta,
      navegar: (h) => { location.hash = h.startsWith('#') ? h : '#' + h; },
      recargar: () => recargarPagina({ conservar: true }),
      alSalir: (fn) => { if (typeof fn === 'function') salidas.push(fn); },
      pausarTodo: () => pausarTodo(),
      paginas: () => Object.fromEntries([...modulos].map(([k, v]) => [k, v.estado])), // {ruta: 'ok'|'falta'|'error'}
      titulos: () => Object.fromEntries(ENTRADAS.map((e) => [e.ruta, e.titulo])),
    };
    return { ctx, salidas };
  }

  function salirDePagina() {
    if (!pagina) return;
    const p = pagina;
    pagina = null;
    for (const fn of p.salidas.splice(0)) { try { fn(); } catch (e) { console.error('alSalir falló', e); } }
    if (p.mod && typeof p.mod.alSalir === 'function') { try { p.mod.alSalir(p.ctx); } catch (e) { console.error('alSalir falló', e); } }
  }

  function pantallaProxima(entrada, ruta) {
    const e = entrada || { titulo: ruta, desc: '' };
    const lugar = entrada ? (entrada.pieza ? `la pieza ${entrada.pieza} del sistema («${entrada.grupo}»)` : `«${entrada.grupo}»`) : null;
    return el('div', { class: 'pagina' },
      ui.encabezadoPagina({ titulo: e.titulo, descripcion: e.desc }),
      ui.vacioConPasos({
        titulo: 'Esta pantalla aún se está preparando',
        explicacion: `${lugar ? `Forma parte de ${lugar}. ` : ''}El resto del panel funciona con normalidad; esta sección aparecerá aquí en cuanto esté lista, sin reiniciar nada.`,
        icono: 'reloj',
        pasos: [{ texto: 'No tienes que hacer nada: cuando esté disponible, recarga la página y la vas a ver en este mismo lugar.' }],
      }),
      ui.detalleTecnico('Cómo aparece', el('p', null, 'La pantalla aparece sola en cuanto existe el archivo ', el('code', null, `dashboard/web/pages/${ruta}.js`), '.')),
      el('p', null, ui.enlace('← Volver al resumen', '#/resumen')));
  }

  function pantallaNoExiste(h) {
    return el('div', { class: 'pagina' },
      ui.encabezadoPagina({ titulo: 'No existe esa pantalla', descripcion: `La dirección ${h || ''} no corresponde a ninguna pantalla del panel.`, migas: [] }),
      vacio('Elige una pantalla del menú lateral o aprieta Ctrl/⌘+K para buscarla.', { icono: 'lupa' }),
      el('p', null, ui.enlace('← Volver al resumen', '#/resumen')));
  }

  async function navegar({ conservar = false } = {}) {
    const yo = ++tokenNav;
    if (!rutaPermitida(modo, parsearHash(location.hash).ruta)) { history.replaceState(null, '', location.pathname + location.search + '#/negocio'); }
    const { ruta, params, valida } = parsearHash(location.hash);
    const entrada = entradaDeRuta(ruta);
    const scrollPrevio = conservar ? principal.scrollTop : 0;
    if (!conservar) { cerrarModales(); salirDePagina(); reemplazar(principal, el('div', { class: 'pagina' }, ui.esqueleto('pagina'))); } // un modal de la pantalla anterior no sobrevive a la navegación
    else if (pagina) { const p = pagina; pagina = null; for (const fn of p.salidas.splice(0)) { try { fn(); } catch (e) { console.error(e); } } }

    marcarActivo(ruta);
    alternarMenu(false);
    rutaActual = ruta;
    if (ruta === 'registro' && nuevosRegistro) { nuevosRegistro = 0; pintarBadges(); }
    const titulo = entrada ? entrada.titulo : (TITULOS_DEV[ruta] || (ruta === 'invalida' ? 'No existe' : ruta));
    tituloEl.textContent = titulo;
    document.title = `${titulo} · Panel de la fábrica`;
    ui.fijarContexto({ migas: migasDeRuta(ruta, params) });

    let nodo; let modulo = null; let ctxPar = null;
    if (!valida || (!entrada && !RUTAS_MODULO.includes(ruta) && !RUTAS_DEV.includes(ruta) && !RUTAS_EXTRA.includes(ruta))) {
      nodo = pantallaNoExiste(location.hash);
    } else {
      let m = await sondearModulo(ruta, { forzar: true });
      if (yo !== tokenNav) return;
      pintarModulos();
      if (m.estado === 'falta') nodo = pantallaProxima(entrada || { titulo }, ruta);
      else if (m.estado === 'error') nodo = el('div', { class: 'pagina' }, errorBox({ codigo: 'modulo', mensaje: `No se pudo abrir la pantalla «${ruta}». Recarga la página; si sigue igual, pásale este detalle a quien mantiene el panel: ${m.error && m.error.message}` }));
      else {
        modulo = m.mod;
        ctxPar = crearCtx(ruta, params);
        ui.fijarContexto({ migas: migasDeRuta(ruta, params) });
        try { nodo = await modulo.render(ctxPar.ctx); } catch (err) { nodo = el('div', { class: 'pagina' }, errorBox(err, { reintentar: () => recargarPagina({ conservar: true }) })); }
        if (!nodo || typeof nodo.nodeType !== 'number') nodo = el('div', { class: 'pagina' }, errorBox({ codigo: 'render', mensaje: `La pantalla «${ruta}» no devolvió nada para mostrar. Recarga la página; si sigue igual, avísale a quien mantiene el panel.` }));
      }
    }
    if (yo !== tokenNav) { if (ctxPar) for (const fn of ctxPar.salidas) { try { fn(); } catch (_) { /* ya no importa */ } } return; }
    reemplazar(principal, nodo);
    principal.scrollTop = scrollPrevio;
    if (!conservar) { principal.classList.remove('entra'); void principal.offsetWidth; principal.classList.add('entra'); } // transición sobria de 160 ms (CSS la anula con prefers-reduced-motion)
    if (modulo) pagina = { ruta, mod: modulo, ctx: ctxPar.ctx, salidas: ctxPar.salidas };
    if (!conservar) { anuncio.textContent = `Pantalla ${titulo}`; principal.focus({ preventScroll: true }); }
  }

  function hayEdicionEnCurso() {
    const a = document.activeElement;
    if (document.querySelector('.modal-fondo') || document.querySelector('.paleta-fondo')) return true;
    return Boolean(a && principal.contains(a) && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName));
  }

  function recargarPagina({ conservar = true } = {}) {
    if (hayEdicionEnCurso()) { pendienteRerender = true; return; }
    pendienteRerender = false;
    navegar({ conservar });
  }
  principal.addEventListener('focusout', () => { if (pendienteRerender) setTimeout(() => { if (pendienteRerender && !hayEdicionEnCurso()) recargarPagina({ conservar: true }); }, 250); });

  // ── eventos en vivo: rebote de 400 ms ──
  const rebote = crearRebote(async (lote) => {
    const ultimo = lote[lote.length - 1];
    refrescarGlobal();
    if (modo === 'negocio' && lote.some((e) => e && (!e.ruta || /libro-de-tests\.json$/.test(e.ruta)))) pintarOfertasNav();
    if (!pagina) return;
    const relevantes = lote.filter((e) => escuchaEvento(pagina.mod.meta, e));
    if (!relevantes.length) return;
    if (typeof pagina.mod.alCambio === 'function') {
      try {
        const r = await pagina.mod.alCambio(pagina.ctx, { ...relevantes[relevantes.length - 1], lote: relevantes });
        if (r && typeof r.nodeType === 'number') reemplazar(principal, r);
      } catch (err) { console.error('alCambio falló', err); }
    } else if (ultimo) {
      recargarPagina({ conservar: true });
    }
  }, 400);

  const conexion = api.conectarEventos((ev) => {
    if (ev && ev.tipo === 'registro' && rutaActual !== 'registro') { nuevosRegistro += 1; pintarBadges(); }
    rebote.empujar(ev);
  }, (modo) => { estado.fijar({ conectado: modo }); });

  window.addEventListener('hashchange', () => navegar());
  window.addEventListener('beforeunload', () => conexion.cerrar());

  // ── primer pintado ──
  pintarSidebar(); pintarVivo(); pintarSistema(); pintarSelector(); pintarBadges(); pintarBotonTema();
  if (!location.hash || location.hash === '#') history.replaceState(null, '', location.pathname + location.search + (modo === 'completo' ? '#/resumen' : '#/negocio'));
  navegar();
  pintarOfertasNav();
  refrescarGlobal();
  sondearTodos();
}
