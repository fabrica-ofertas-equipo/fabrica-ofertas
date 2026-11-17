// pages/parametros.js — #/parametros: SOLO LECTURA de los límites del dueño (con el panel «Esto desbloquea gasto»: qué operación habilita cada clave en null
// y qué falta fijar), los parámetros ajustables por grupo, la autonomía por etapa y las propuestas aún sin integrar. Con búsqueda.
// SIN edición: los límites los escribe y firma el dueño (`engine.limites`). CONTRATO §4 `GET /parametros` → {limites:{valores, nulos}, parametros, autonomia, propuestas}.

import { ayudasVista, instalarEstilos } from '../lib/operacion.js';
import {
  modeloPantallaParametros, filtrarTodo, comandosParametros, NOMBRE_ETAPA, prioridadLimites, resumenDesbloqueo, formaDeValor, LIMITES_META, NOMBRE_CORTO_OPERACION,
} from '../lib/parametros.js';

export const meta = { ruta: 'parametros', titulo: 'Límites y reglas', grupo: 'Dinero y reglas', icono: 'ajustes', escucha: ['empresa'] };

const UI = { q: '', verTodas: false };

function hayEdicion() {
  const d = globalThis.document;
  const a = d && d.activeElement;
  return Boolean(a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) || Boolean(d && d.querySelector('.modal-fondo'));
}

const botonActualizar = (ctx) => ctx.ui.el('button', { type: 'button', class: 'btn btn--chico', onclick: () => ctx.recargar() }, ctx.ui.icono('refrescar', { tam: 14 }), 'Actualizar');
const humano = (id) => String(id).replace(/[_-]+/g, ' ').replace(/^./, (c) => c.toUpperCase());
/** «N3» → «3»: los niveles se dicen «nivel 3», nunca con la sigla. */
const nivelNum = (n) => String(n).replace(/^N/i, '');
/** Qué significa cada nivel de autonomía, en una frase (mismo sentido que el glosario). */
const NIVELES_EXPLICADOS = [
  ['0', 'todo lo apruebas tú; el sistema te guía paso a paso.'],
  ['1', 'una IA hace el trabajo y tú revisas todo.'],
  ['2', 'otra IA revisa el trabajo de la primera y tú firmas solo lo importante (oferta, página de venta, campaña, presupuesto).'],
  ['3', 'el sistema avanza solo, con topes duros de dinero, y te consulta solo si hay una excepción.'],
  ['4', 'el sistema lanza ofertas nuevas con un botón, con tope diario y una revisión semanal tuya.'],
];

/** Chip de estado de una clave: icono + etiqueta (el color nunca va solo). */
function chipEstadoClave(ui, c) {
  if (c.seguroPorDefecto) return ui.chip('Sin fijar · se usa el valor más prudente', 'neutro', { icono: 'circulo-punteado' });
  switch (c.estado) {
    case 'nulo': return ui.chip('Sin fijar', 'aviso');
    case 'ausente': return ui.chip('Falta en el archivo', 'aviso');
    case 'vacio': return ui.chip('Lista vacía', 'aviso');
    case 'fijado': return ui.chip('Fijado', 'ok');
    default: return ui.chip('Lo define la plataforma', 'neutro', { icono: 'candado' });
  }
}

// ───────────────────────── «Esto desbloquea gasto» ─────────────────────────

function tarjetaOperacion(ctx, o) {
  const { ui } = ctx;
  const { el } = ui;
  const ayudas = ayudasVista(ui, ctx.fmt);
  const falt = o.faltantes;
  return el('article', { class: `p5-op${o.ok ? ' p5-op--ok' : ''}` },
    el('div', { class: 'p5-op__cab' }, el('span', { class: 'p5-op__nombre' }, o.titulo), o.ok ? ui.chip('Habilitada', 'ok') : ui.chip(`Faltan ${falt.length}`, 'aviso')),
    el('span', { class: 'p5-sub' }, o.ayuda),
    ayudas.medidor({ bp: Math.round((o.fijadas / o.total) * 10000), zona: o.ok ? 'bien' : 'aviso', texto: `${o.fijadas} de ${o.total} requisitos fijados`, etiqueta: `${o.titulo}: ${o.fijadas} de ${o.total}` }),
    falt.length ? el('div', { class: 'p5-pila p5-pila--chica' }, el('strong', { class: 'p5-sub' }, 'Falta fijar:'), el('ul', { class: 'p5-op__faltan' }, falt.slice(0, 6).map((k) => el('li', null, ui.termino(`lim_${k}`))), falt.length > 6 ? el('li', { class: 'p5-sub' }, `… y ${falt.length - 6} más`) : null)) : null);
}

function filaPrioridad(ctx, c, moneda) {
  const { ui } = ctx;
  const { el } = ui;
  const meta2 = LIMITES_META[c.clave] || {};
  return el('li', { class: 'p5-prioridad__fila' },
    el('div', { class: 'p5-prioridad__nombre' }, el('strong', null, ui.termino(`lim_${c.clave}`)), ui.soloTecnico(el('span', { class: 'p5-lim-clave' }, c.clave))),
    el('div', { class: 'p5-pila p5-pila--chica' },
      el('span', { class: 'p5-sub' }, el('strong', null, 'Falta fijar: '), formaDeValor(meta2.tipo, c.clave).replace('la moneda de los límites', moneda || 'la moneda de los límites')),
      el('span', { class: 'p5-fila p5-fila--junta' }, el('span', { class: 'p5-sub' }, 'Habilita:'), c.desbloquea.map((d) => ui.chip(NOMBRE_CORTO_OPERACION[d.id] || d.titulo, 'info', { icono: false })))),
    chipEstadoClave(ui, c));
}

function panelDesbloqueo(ctx, m, ayudas, redibujar) {
  const { ui } = ctx;
  const { el } = ui;
  const L = m.limites;
  const r = resumenDesbloqueo(L);
  const { criticas, otras } = prioridadLimites(L);
  const mostrar = UI.verTodas ? criticas : criticas.slice(0, 8);
  const titular = r.puedeGastar
    ? 'Los límites alcanzan para gastar'
    : (r.sinSello && r.faltanParaGastar === 1 ? 'Solo falta tu firma para poder gastar' : `Todavía no se puede gastar: faltan ${r.faltanParaGastar} requisitos para «Gastar»`);
  return ui.seccion('Esto desbloquea gasto', el('div', { class: 'p5-pila' },
    el('div', { class: `p5-aviso ${r.puedeGastar ? 'p5-aviso--info' : 'p5-aviso--aviso'}` },
      el('span', { class: 'p5-aviso__icono' }, ui.icono(r.puedeGastar ? 'ok' : 'candado', { tam: 18 })),
      el('div', { class: 'p5-aviso__texto' }, el('strong', null, titular), el('div', { class: 'p5-sub' },
        r.puedeGastar ? 'Aun así, activar una campaña siempre pide tu firma.' : 'Por seguridad, si falta un dato no se hace nada: mientras falte un límite necesario, nada gasta ni activa campañas. Los límites los fijas tú y quedan aprobados con tu firma.'))),
    el('div', { class: 'p5-op-grid' }, L.operaciones.map((o) => tarjetaOperacion(ctx, o))),
    criticas.length
      ? el('div', { class: 'p5-pila' },
        el('h3', { class: 'p5-titulo-chico' }, `Por dónde empezar · ${criticas.length} ${criticas.length === 1 ? 'límite bloquea' : 'límites bloquean'} operaciones`),
        el('ul', { class: 'p5-prioridad' }, mostrar.map((c) => filaPrioridad(ctx, c, L.moneda))),
        criticas.length > 8 ? el('button', { type: 'button', class: 'btn btn--chico', onclick: () => { UI.verTodas = !UI.verTodas; redibujar(); } }, UI.verTodas ? 'Mostrar menos' : `Mostrar los ${criticas.length - 8} restantes`) : null)
      : null,
    otras.length ? el('p', { class: 'p5-sub' }, `Además hay ${otras.length} ${otras.length === 1 ? 'límite sin fijar que hoy no necesita' : 'límites sin fijar que hoy no necesita'} ninguna operación; se ${otras.length === 1 ? 'lista' : 'listan'} abajo, en su grupo.`) : null,
    ui.comando(comandosParametros().estado, { titulo: 'Cómo comprobar si los límites alcanzan', nota: 'Solo mira, no cambia nada: dice qué falta para poder gastar.' }),
    el('p', { class: 'p5-sub' }, 'Aquí no se revisa si los topes tienen sentido entre sí ni si tu firma es válida: eso lo comprueba el sistema cada vez que va a gastar.')),
  { ayuda: 'Cada límite sin fijar deja frenadas una o varias operaciones. Aquí ves qué habilita cada uno y qué valor falta. Esta pantalla no edita nada.' });
}

// ───────────────────────── límites por grupo ─────────────────────────

function filaLimite(ctx, c) {
  const { ui } = ctx;
  const { el } = ui;
  return el('div', { class: `p5-lim${c.bloquea ? ' p5-lim--nulo' : ''}` },
    el('div', { class: 'p5-lim__nombre' }, ui.termino(`lim_${c.clave}`), ui.soloTecnico(el('span', { class: 'p5-lim-clave' }, c.clave))),
    el('div', { class: 'p5-lim__valor' }, chipEstadoClave(ui, c), c.texto !== null && c.estado !== 'nulo' ? el('span', { class: c.tipo === 'lista' || c.tipo === 'texto' ? '' : 'p5-mono' }, c.texto) : (c.estado === 'ausente' ? el('span', { class: 'cifra-sin-dato' }, 'falta definirlo') : null)),
    el('div', { class: 'p5-pila p5-pila--chica' },
      el('span', { class: 'p5-sub' }, c.ayuda),
      c.bloquea && c.desbloquea.length ? el('span', { class: 'p5-fila p5-fila--junta' }, el('span', { class: 'p5-sub' }, 'Habilita:'), c.desbloquea.map((d) => ui.chip(NOMBRE_CORTO_OPERACION[d.id] || d.titulo, 'info', { icono: false })))
        : (c.bloquea && c.usos.length ? el('span', { class: 'p5-sub' }, `Se usa para: ${c.usos.join(', ')}`) : (c.bloquea ? el('span', { class: 'p5-sub' }, 'Hoy ninguna operación lo necesita.') : null))));
}

function seccionLimites(ctx, m, ayudas, sobre) {
  const { ui } = ctx;
  const { el } = ui;
  const L = m.limites;
  if (!L) {
    return ui.seccion('Tus límites', ayudas.vacioConComandos('No se pudieron leer los límites.', {
      pista: 'Sin límites, el sistema no gasta ni activa nada. El archivo viene en la plantilla; el panel lo lee sin modificarlo.',
      archivo: 'empresa/limites.yaml',
      comandos: [{ etiqueta: 'Comprueba si los límites alcanzan para gastar', cmd: comandosParametros().estado }, { etiqueta: 'Revisa que el archivo tenga el formato esperado', cmd: comandosParametros().validar }],
      fuente: sobre.fuente,
    }), { glosario: 'limites' });
  }
  const buscando = Boolean(m.consulta);
  const grupos = m.limitesVista.grupos;
  if (buscando && !grupos.length) return null;
  const cuerpo = grupos.length ? grupos.map((g) => {
    const faltan = g.claves.filter((c) => c.bloquea).length;
    return el('details', { class: 'p5-expand p5-grupo', open: buscando || faltan ? true : null },
      el('summary', { class: 'p5-expand__cab' }, ui.icono('chevron-derecha', { tam: 14, clase: 'p5-expand__chev' }), g.titulo, ' ',
        el('span', { class: 'p5-sub' }, `${g.claves.length} ${g.claves.length === 1 ? 'límite' : 'límites'}`), faltan ? ui.chip(`${faltan} sin fijar`, 'aviso') : ui.chip('Todo fijado', 'ok')),
      el('div', { class: 'p5-lim-grupo' }, g.claves.map((c) => filaLimite(ctx, c))));
  }) : el('span', { class: 'cifra-sin-dato' }, 'Ningún límite coincide con la búsqueda.');
  return ui.seccion('Tus límites', el('div', { class: 'p5-pila' }, cuerpo),
    { glosario: 'limites', ayuda: 'Techos duros que solo tú escribes. «Sin fijar» = nada que dependa de ese límite gasta hasta que lo fijes. El panel no edita nada: para cambiar un límite se edita el archivo y se vuelve a firmar.' });
}

// ───────────────────────── parámetros ─────────────────────────

function seccionParametros(ctx, m, ayudas, sobre) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const P = m.parametros;
  if (!P) {
    return ui.seccion('Valores ajustables', ayudas.vacioConComandos('No se pudieron leer los valores ajustables.', {
      pista: 'Son los umbrales que se afinan con los resultados: los propone el sistema y los apruebas tú. Cada uno dice su valor, su unidad, si es una hipótesis y de dónde sale.',
      archivo: 'empresa/parametros.yaml', fuente: sobre.fuente,
    }), { glosario: 'parametro_hipotesis' });
  }
  const buscando = Boolean(m.consulta);
  const grupos = m.parametrosVista.grupos;
  if (buscando && !grupos.length) return null;
  const cuerpo = grupos.length ? grupos.map((g) => el('details', { class: 'p5-expand p5-grupo', open: buscando ? true : null },
    el('summary', { class: 'p5-expand__cab' }, ui.icono('chevron-derecha', { tam: 14, clase: 'p5-expand__chev' }), humano(g.id), ' ', el('span', { class: 'p5-sub' }, `${g.claves.length} ${g.claves.length === 1 ? 'valor' : 'valores'}`)),
    ui.tabla({
      etiqueta: `Valores ajustables del grupo ${g.id}`, filas: g.claves, maxFilas: 300, vacio: 'Sin parámetros.',
      columnas: [
        { clave: 'clave', titulo: 'Nombre interno', formato: (v) => el('span', { class: 'p5-mono' }, v) },
        { clave: 'texto', titulo: 'Valor', clase: 'cel-larga', formato: (v, f) => (f.nulo ? ui.chip('Sin valor', 'aviso') : el('span', { class: 'p5-mono' }, v)) },
        { clave: 'unidad', titulo: 'Unidad' },
        { clave: 'hipotesis', titulo: 'Estado', formato: (v) => (v === null ? '—' : v ? ui.chip('Hipótesis', 'neutro', { icono: false }) : ui.chip('Confirmado', 'ok')) },
        { clave: 'ultima', titulo: 'Último ajuste con datos reales', formato: (v) => (v ? fmt.fecha(v) : el('span', { class: 'texto-tenue' }, 'sin ajustar todavía')) },
        { clave: 'rango', titulo: 'Rango posible', formato: (v) => (v ? `${v[0]} … ${v[1]}` : '—') },
        { clave: 'fuente', titulo: 'De dónde sale', clase: 'cel-larga' },
      ],
    }))) : el('span', { class: 'cifra-sin-dato' }, 'Ningún valor ajustable coincide con la búsqueda.');
  return ui.seccion('Valores ajustables', el('div', { class: 'p5-pila' },
    el('div', { class: 'p5-fila p5-fila--junta' }, ui.chip(`${P.total} valores`, 'neutro', { icono: false }), ui.chip(`${P.hipotesis} son hipótesis`, 'neutro', { icono: false }), ui.chip(`${P.calibrados} ajustados con datos reales`, P.calibrados ? 'ok' : 'neutro', { icono: P.calibrados ? undefined : false }), P.nulos ? ui.chip(`${P.nulos} sin valor`, 'aviso') : null,
      P.version !== null ? el('span', { class: 'p5-sub' }, `versión ${P.version}${P.schema_version ? ` · formato ${P.schema_version}` : ''}`) : null),
    cuerpo),
  { glosario: 'parametro_hipotesis', ayuda: 'Agrupados por área. «Hipótesis» = valor inicial que todavía hay que afinar con tus propios resultados; «sin ajustar» = aún no se afinó con datos reales.' });
}

// ───────────────────────── autonomía ─────────────────────────

function seccionAutonomia(ctx, m, ayudas, sobre) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const A = m.autonomia;
  if (!A) {
    return ui.seccion('Cuánto hace solo cada etapa', ayudas.vacioConComandos('No se pudieron leer los niveles de autonomía.', {
      pista: 'Cuánto hace sola cada etapa, del nivel 0 (todo lo apruebas tú) al nivel 4 (casi todo lo hace el sistema). Subir de nivel exige buenos resultados y tu aprobación; bajar es automático si algo sale mal.',
      archivo: 'empresa/autonomia.yaml', fuente: sobre.fuente,
    }), { glosario: 'autonomia' });
  }
  const vista = m.autonomiaVista;
  if (m.consulta && !vista.etapas.length) return null;
  return ui.seccion('Cuánto hace solo cada etapa', el('div', { class: 'p5-pila' },
    el('div', { class: 'p5-niveles' }, ...Object.entries(A.histograma).sort().map(([n, c]) => ui.chip(`Nivel ${nivelNum(n)}: ${c} ${c === 1 ? 'etapa' : 'etapas'}`, n === 'N0' ? 'neutro' : 'info', { icono: false })), A.todasN0 ? el('span', { class: 'p5-sub' }, 'Todas las etapas están en el nivel 0 (todo lo apruebas tú): nada se hace solo.') : null),
    el('details', { class: 'p5-expand' }, el('summary', { class: 'p5-expand__cab' }, ui.icono('chevron-derecha', { tam: 14, clase: 'p5-expand__chev' }), 'Qué significa cada nivel'),
      el('ul', { class: 'p5-checks' }, NIVELES_EXPLICADOS.map(([n, t]) => el('li', null, el('strong', null, `Nivel ${n}: `), t)))),
    vista.etapas.length
      ? el('div', { class: 'p5-aut-grid' }, vista.etapas.map((e) => el('article', { class: 'p5-aut' },
        el('div', { class: 'p5-aut__cab' }, el('span', { class: 'p5-aut__etapa' }, e.etapa), e.nivel ? el('span', null, ui.termino(`nivel_${e.nivel.toLowerCase()}`, { texto: `Nivel ${nivelNum(e.nivel)}`, sinTecnico: true })) : el('span', { class: 'cifra-sin-dato' }, 'sin dato')),
        el('strong', null, e.nombre || NOMBRE_ETAPA[e.etapa] || 'Sin descripción'),
        el('span', { class: 'p5-sub' }, `Desde ${e.desde ? fmt.fecha(e.desde) : '—'} · ${e.evidencia ? `${e.evidencia} ${e.evidencia === 1 ? 'prueba' : 'pruebas'} que lo respaldan` : 'sin pruebas todavía'}`))))
      : el('span', { class: 'cifra-sin-dato' }, 'Ninguna etapa coincide con la búsqueda.'),
    A.descensos.length ? el('div', { class: 'p5-pila' }, el('h3', { class: 'p5-titulo-chico' }, `Veces que una etapa bajó de nivel (${A.descensos.length})`), el('ul', { class: 'p5-checks' }, A.descensos.map((d) => el('li', null, typeof d === 'string' ? d : JSON.stringify(d))))) : el('span', { class: 'p5-sub' }, 'Ninguna etapa bajó de nivel.'),
    A.reglas.length ? ui.detalleTecnico('Reglas para bajar de nivel automáticamente', el('ul', { class: 'p5-checks' }, A.reglas.map((r) => el('li', null, r)))) : null),
  { glosario: 'autonomia', ayuda: 'Solo lectura. Para subir de nivel hacen falta buenos resultados medidos en esa etapa y tu aprobación. Bajar de nivel es automático si algo sale mal.' });
}

// ───────────────────────── propuestas ─────────────────────────

function seccionPropuestas(ctx, m, ayudas) {
  const { ui } = ctx;
  const { el } = ui;
  const lista = m.propuestasVista;
  if (!m.propuestas.length) {
    return ui.seccion('Cambios propuestos que esperan tu aprobación', ayudas.vacioConComandos('No hay propuestas pendientes.', {
      pista: 'Son valores nuevos que alguien propuso y que todavía no aprobaste ni pasaste a los valores ajustables.',
      archivo: 'empresa/propuestas/*.yaml · scripts/modelado/*propuesta.yaml',
    }), { glosario: 'propuesta_parametros' });
  }
  if (!lista.length) return null; // con una búsqueda sin coincidencias aquí, la sección se oculta
  return ui.seccion('Cambios propuestos que esperan tu aprobación', el('div', { class: 'p5-pila' }, lista.map((p) => {
    const claves = p.clavesVisibles && m.consulta ? p.clavesVisibles : p.claves;
    return el('details', { class: 'p5-expand p5-grupo', open: m.consulta ? true : null },
      el('summary', { class: 'p5-expand__cab' }, ui.icono('chevron-derecha', { tam: 14, clase: 'p5-expand__chev' }), p.origen, ' ', ui.chip(`${p.nClaves} ${p.nClaves === 1 ? 'cambio' : 'cambios'}`, 'neutro', { icono: false }), ui.chip('Sin aplicar', 'aviso'), ui.soloTecnico(el('span', { class: 'p5-mono' }, p.archivo))),
      el('div', { class: 'p5-pila' }, claves.length ? el('ul', { class: 'p5-checks' }, claves.map((c) => el('li', { class: 'p5-mono' }, c))) : el('span', { class: 'p5-sub' }, p.soloConteo ? 'El panel solo sabe cuántos cambios trae, no cuáles.' : 'Sin cambios listados.'), ui.detalleTecnico('Archivo de la propuesta', el('span', { class: 'p5-mono' }, p.archivo))));
  })), { glosario: 'propuesta_parametros', ayuda: 'Todavía no rigen. Para aplicarlos: aprueba los valores y pásalos a los valores ajustables (si son datos nuevos, también hay que sumarlos al formato esperado). El panel no aplica nada.' });
}

// ───────────────────────── página ─────────────────────────

export async function render(ctx) {
  const { api, ui, fmt } = ctx;
  const { el } = ui;
  instalarEstilos(ui);
  const ayudas = ayudasVista(ui, fmt);
  const cab = ui.encabezadoPagina({
    titulo: 'Límites y reglas',
    descripcion: 'Los topes de dinero y las reglas del negocio. Aquí solo se mira: ves qué falta fijar para que el sistema pueda gastar, cuánto hace solo cada etapa y qué cambios esperan tu aprobación.',
    acciones: [botonActualizar(ctx)],
  });
  let sobre;
  try { sobre = await api.sobre('/parametros'); } catch (e) { return el('div', { class: 'pagina' }, cab, ui.errorBox(e, { reintentar: () => ctx.recargar() })); }
  const base = modeloPantallaParametros(sobre.datos, fmt);
  if (!base.limites && !base.parametros && !base.autonomia && !base.propuestas.length) {
    return el('div', { class: 'pagina' }, cab, ayudas.vacioConComandos('El panel no pudo leer los límites, los valores ajustables ni los niveles de autonomía.', {
        compacto: false,
      pista: 'Son archivos que escribes tú. Si no aparecen, revisa que el panel se haya abierto desde la carpeta del proyecto.',
      archivo: 'empresa/{limites,parametros,autonomia}.yaml',
      comandos: [{ etiqueta: 'Comprueba si los límites alcanzan', cmd: comandosParametros().estado }],
      fuente: sobre.fuente,
    }), ui.fuenteInfo(sobre));
  }
  const cuerpo = el('div', { class: 'p5-pila' });
  const pintar = () => {
    const m = filtrarTodo(base, UI.q);
    m.limitesVista = m.limites ? { grupos: m.limites.grupos } : { grupos: [] };
    m.parametrosVista = m.parametros ? { grupos: m.parametros.grupos } : { grupos: [] };
    m.autonomiaVista = m.autonomia ? { etapas: m.autonomia.etapas } : { etapas: [] };
    m.propuestasVista = m.propuestas;
    // las secciones usan `m.limites` completo para el resumen; con búsqueda se oculta el panel y se muestran solo las claves que coinciden
    const completo = { ...m, limites: base.limites, parametros: base.parametros, autonomia: base.autonomia, propuestas: base.propuestas };
    completo.propuestasVista = m.propuestas;
    ui.reemplazar(cuerpo,
      m.consulta ? el('p', { class: 'p5-sub', role: 'status' }, `${m.coincidencias} coincidencia(s) para «${m.consulta}».`) : null,
      base.limites && !m.consulta ? panelDesbloqueo(ctx, completo, ayudas, pintar) : null,
      m.consulta && m.coincidencias === 0 ? ui.vacio(`Nada coincide con «${m.consulta}».`, { pista: 'Prueba con otra palabra: por ejemplo «gasto diario», «reembolso» o el código de una etapa (D5).', icono: 'lupa' }) : null,
      seccionLimites(ctx, completo, ayudas, sobre), seccionParametros(ctx, completo, ayudas, sobre), seccionAutonomia(ctx, completo, ayudas, sobre), seccionPropuestas(ctx, { ...completo, propuestas: base.propuestas }, ayudas));
  };
  const buscar = el('input', {
    type: 'search', class: 'campo p5-buscar', placeholder: 'Buscar un límite, un valor, una etapa o una propuesta…', 'aria-label': 'Buscar en límites, valores ajustables, niveles de autonomía y propuestas', value: UI.q,
    oninput: (ev) => { UI.q = ev.target.value; pintar(); },
  });
  pintar();
  return el('div', { class: 'pagina' }, cab, el('div', { class: 'p5-selectores' }, buscar), cuerpo,
    ui.fuenteInfo(sobre),
    el('p', { class: 'p5-sub' }, 'Esta pantalla no cambia nada: los límites los escribes y firmas tú, y los valores ajustables los propone el sistema y los apruebas tú.'));
}

/** Actualización en vivo: re-renderiza conservando la búsqueda, salvo que se esté escribiendo en ella. */
export async function alCambio(ctx) {
  if (hayEdicion()) return undefined;
  return render(ctx);
}
