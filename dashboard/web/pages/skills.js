// pages/skills.js — #/skills: el mapa de cobertura por etapa (qué etapas ya tienen skill, cuáles faltan) y una tarjeta por skill con su versión,
// su estado (borrador o v1), el avance de su DoD y QUÉ LE FALTA PARA V1; al abrir una se ve el visor de SKILL.md, sus archivos y agentes.
// La lógica vive en lib/skills.js (probada sin DOM). Lo técnico (rutas, comandos, límites) va en detalle técnico.

import { ui, el, icono, fmt, limpiar, copiar } from '../ui.js';
import * as K from '../lib/skills.js';
import * as P from '../lib/pulido.js';
import * as V from '../lib/oferta.js';
import * as W from '../lib/vistas-ofertas.js';

export const meta = { ruta: 'skills', titulo: 'Guías de trabajo', grupo: 'Cerebro', icono: 'libro', escucha: ['skills'] };

// Estado que sobrevive a los re-render del router.
let filtros = { ...K.FILTROS_VACIOS };
let seleccion = null;
let vista = leerVista();
let ultimaFirma = null;

function leerVista() {
  try { const v = globalThis.localStorage && globalThis.localStorage.getItem('fab.skills.vista'); return v === 'tabla' ? 'tabla' : 'tarjetas'; } catch (_) { return 'tarjetas'; }
}
function guardarVista(v) { try { if (globalThis.localStorage) globalThis.localStorage.setItem('fab.skills.vista', v); } catch (_) { /* sin almacén */ } }

const firma = (datos) => JSON.stringify(K.listaDeSkills(datos).map((s) => [s.slug, s.version, s.estado, s.lineas_skill_md, s.archivos, s.agentes, Array.isArray(s.dod) ? s.dod.length : 0]));
const ICONO_ESTRUCTURA = { skill: 'libro', references: 'carpeta', rubric: 'lista', templates: 'archivo', scripts: 'terminal', evals: 'diana', changelog: 'reloj' };
const ICONO_CELDA = { ...W.ICONO_ETAPA, X1: 'cumplimiento', O0: 'cartera', D0: 'servidor', F1: 'dinero', F2: 'grafico', X2: 'libro' };

export async function render(ctx) {
  W.estilos();
  let sobre;
  try { sobre = await ctx.api.sobre('/skills'); } catch (err) {
    return el('div', { class: 'pagina' }, ui.encabezadoPagina({ titulo: 'Guías de trabajo', descripcion: 'No se pudieron leer las guías de trabajo.' }), ui.errorBox(err, { reintentar: () => ctx.recargar() }));
  }
  let pulido = [];
  try { pulido = P.normalizarEntradas((await ctx.api.sobre('/pulido')).datos); } catch (_) { pulido = []; }
  ultimaFirma = firma(sobre.datos);
  const filas = K.filasSkills(sobre.datos);
  const cob = K.resumenCobertura(filas);
  const res = K.resumenSkills(filas);
  const notasDe = (etapa) => P.mapaPulido(pulido).filas.find((c) => c.etapa === etapa) || { total: 0, pendientes: 0, resueltas: 0 };

  const existe = (s) => typeof s === 'string' && filas.some((f) => f.slug === s);
  seleccion = [ctx.params.skill, seleccion].find(existe) || null;

  const cab = ui.encabezadoPagina({
    titulo: 'Guías de trabajo',
    descripcion: 'Las instrucciones que sigue cada IA para hacer su tarea (en el sistema se llaman «skills»). Nacen en borrador (v0.1) y las pules a mano hasta darlas por terminadas (v1). Aquí ves qué etapas todavía no tienen guía y qué le falta a cada una.',
    acciones: [ui.fuente(sobre.fuente, { leido: sobre.generado_en })],
  });

  const metricas = el('div', { class: 'u2-metricas' },
    ui.metrica({ etiqueta: 'Guías creadas', valor: String(res.total), contexto: `${res.borradores} en borrador · ${res.v1} terminadas (v1)`, tono: res.total ? undefined : 'aviso', ayuda: 'skill_borrador' }),
    ui.metrica({
      etiqueta: 'Etapas con guía', valor: `${res.etapasFlujoConSkill} de ${res.etapasFlujoTotal}`, tono: res.sinSkillFlujo.length ? 'aviso' : 'ok',
      contexto: res.sinSkillFlujo.length ? `Faltan: ${res.sinSkillFlujo.map((e) => K.nombreHumanoEtapaSkill(e)).join(', ')}` : 'Todas las etapas del flujo están cubiertas',
    }),
    ui.metrica({ etiqueta: 'Terminadas (v1)', valor: String(res.v1), tono: res.v1 ? 'ok' : undefined, contexto: res.v1 ? 'pasaron todos los criterios y tienen tu aprobación' : 'ninguna todavía: v1 exige una prueba a mano, un repaso y tu firma', ayuda: 'dod_skill' }),
    ui.metrica({ etiqueta: 'Con todos sus archivos', valor: `${res.estructuraCompleta} de ${res.total}`, contexto: 'instrucciones, criterios de revisión, casos de prueba…', tono: res.total && res.estructuraCompleta < res.total ? 'aviso' : (res.total ? 'ok' : undefined) }));

  // ── mapa de cobertura ──
  const hostDetalleAbierto = { panel: null };
  const abrir = (slug) => { seleccion = slug; try { history.replaceState(null, '', `#/skills?skill=${encodeURIComponent(slug)}`); } catch (_) { /* sin history */ } abrirDetalle(ctx, filas, slug, notasDe, hostDetalleAbierto, () => { seleccion = null; }); };
  const celda = (c) => {
    const est = K.estadoCobertura(c);
    const f0 = c.conSkill ? filas.find((f) => f.slug === c.skills[0]) : null;
    const contenido = [
      el('div', { class: 'u2-cob__cab' },
        el('span', { class: 'u2-fila', style: { gap: '8px', flexWrap: 'nowrap' } }, icono(ICONO_CELDA[c.etapa] || 'lista', { tam: 18 }), W.codigo(c.etapa)),
        c.forja ? el('span', { class: 'u2-tenue', style: { fontSize: '.75rem' }, title: c.forja === 'criterio' ? 'Se arma a mano, con tu criterio' : 'Casi todo es programa automático con pruebas; la guía es su manual de uso' }, c.forja === 'criterio' ? 'con tu criterio' : 'casi todo automático') : null),
      el('div', { class: 'u2-cob__nombre' }, K.nombreHumanoEtapaSkill(c.etapa)),
    ];
    if (est === 'sin_skill') contenido.push(el('div', { class: 'u2-cob__skill' }, W.tag('Falta crearla', 'aviso', { icono: 'alerta' })), el('div', { class: 'u2-nota' }, 'Todavía no hay guía ni agentes para esta etapa.'));
    else if (est === 'fuera_alcance') contenido.push(el('div', { class: 'u2-cob__skill' }, W.tag('Fuera de alcance', 'neutro', { suave: true, icono: 'archivar', titulo: 'Queda fuera de la primera prueba: Operación solo registra la propuesta' })));
    else {
      contenido.push(...c.skills.map((s, i) => {
        const f = filas.find((x) => x.slug === s);
        return el('div', { class: 'u2-cob__skill' }, ui.estadoIcono(c.estados[i] === 'v1' ? 'aprobado' : 'borrador'), el('span', { class: 'u2-tenue' }, f && f.version ? `v${f.version}` : 'sin versión'));
      }));
      if (f0) contenido.push(el('div', { class: 'u2-nota' }, K.faltaParaV1(f0).siguiente));
    }
    return c.conSkill
      ? el('button', { type: 'button', class: ['u2-cob__celda', `u2-cob__celda--${est}`], 'aria-label': `${K.nombreHumanoEtapaSkill(c.etapa)}: ver ${c.skills[0]}`, onclick: () => abrir(c.skills[0]) }, contenido)
      : el('div', { class: ['u2-cob__celda', `u2-cob__celda--${est}`] }, contenido);
  };
  const cobertura = el('div', { class: 'u2-pila' },
    el('div', { class: 'u2-cob' }, cob.flujo.map(celda)),
    el('h3', { class: 'u2-subtitulo' }, 'Etapas de la empresa (fuera del flujo de cada oferta)'),
    el('div', { class: 'u2-cob' }, cob.resto.map(celda)),
    cob.sinEtapa.length ? el('p', { class: 'u2-nota' }, `Guías que no corresponden a una etapa del sistema: ${cob.sinEtapa.join(', ')}.`) : null);

  // ── tarjetas / tabla ──
  const hostLista = el('div');
  const conteo = el('span', { class: 'u2-nota', 'aria-live': 'polite' });
  function tarjetaSkill(f) {
    const falta = K.faltaParaV1(f);
    const total = falta.total || 1;
    const nPulido = f.etapa ? notasDe(f.etapa) : { total: 0, pendientes: 0 };
    return el('article', { class: 'u2-skill', 'aria-current': seleccion === f.slug ? 'true' : null },
      el('div', { class: 'u2-fila u2-fila--entre', style: { alignItems: 'flex-start' } },
        el('div', null,
          el('h3', { class: 'u2-skill__titulo' }, el('button', { type: 'button', onclick: () => abrir(f.slug), 'aria-label': `Abrir ${f.titulo}` }, f.titulo)),
          ui.soloTecnico(el('div', { class: 'u2-skill__slug' }, f.slug))),
        el('div', { class: 'u2-fila', style: { gap: '6px', flexWrap: 'nowrap' } }, ui.estadoIcono(f.estado === 'v1' ? 'aprobado' : 'borrador'), f.version ? W.codigo(`v${f.version}`) : null)),
      f.descripcion ? el('p', { class: 'u2-nota' }, K.primeraFrase(f.descripcion)) : el('p', { class: 'u2-aviso' }, 'Esta guía no tiene descripción: sin ella el sistema no sabe cuándo usarla.'),
      el('div', { class: 'u2-prog' },
        el('div', { class: 'u2-prog__barra', role: 'img', 'aria-label': `${falta.cumple.length} criterios cumplen, ${falta.arreglar.length} fallan, ${falta.medir.length} por comprobar` },
          el('i', { class: 'u2-prog__ok', style: { '--p': `${(falta.cumple.length / total) * 100}%` } }), el('i', { class: 'u2-prog__falla', style: { '--p': `${(falta.arreglar.length / total) * 100}%` } }), el('i', { class: 'u2-prog__medir', style: { '--p': `${(falta.medir.length / total) * 100}%` } })),
        el('div', { class: 'u2-prog__leyenda' }, el('span', null, `${falta.cumple.length} cumplen`), falta.arreglar.length ? el('span', { class: 'u2-ic--error' }, `${falta.arreglar.length} fallan`) : null, el('span', null, `${falta.medir.length} por comprobar`), ui.ayuda('dod_skill'))),
      el('div', { class: 'u2-skill__falta' }, icono(falta.congelada ? 'ok' : 'flecha-derecha', { tam: 16 }), el('div', null, el('span', { class: 'u2-rotulo' }, 'Para darla por terminada'), el('div', null, falta.siguiente))),
      el('div', { class: 'u2-fila' },
        W.tag(`Archivos ${K.ESTRUCTURA.length - f.faltan.length}/${K.ESTRUCTURA.length}`, f.faltan.length ? 'aviso' : 'ok', { icono: f.faltan.length ? 'alerta' : 'ok', titulo: f.faltan.length ? `Faltan: ${f.faltan.map(K.nombreArchivo).join(', ')}` : 'Tiene todos sus archivos' }),
        W.tag('IA que prepara', f.agentes.maker ? 'ok' : 'aviso', { icono: f.agentes.maker ? 'ok' : 'alerta', titulo: 'La IA que hace el trabajo' }),
        W.tag('IA que revisa', f.agentes.qa ? 'ok' : 'aviso', { icono: f.agentes.qa ? 'ok' : 'alerta', titulo: 'Una IA independiente que revisa el trabajo' }),
        nPulido.total ? el('a', { class: 'u2-tenue enlace', style: { position: 'relative', zIndex: '1' }, href: `#/pulido?etapa=${f.etapa}` }, nPulido.pendientes ? `${nPulido.pendientes} ${nPulido.pendientes === 1 ? 'mejora pendiente' : 'mejoras pendientes'}` : 'Sin mejoras pendientes') : null));
  }
  function tablaSkills(vistaFilas) {
    return ui.tabla({
      etiqueta: 'Guías de trabajo', filas: vistaFilas, alClick: (f) => abrir(f.slug), vacio: 'Ninguna guía coincide con los filtros.',
      claseFila: (f) => (f.slug === seleccion ? 'fila-aviso' : ''),
      columnas: [
        { clave: 'titulo', titulo: 'Guía', flex: true, formato: (t, f) => el('div', { class: 'u2-celda-titulo' }, el('strong', null, t), ui.soloTecnico(el('span', { class: 'u2-mono' }, f.slug))) },
        { clave: 'etapa', titulo: 'Etapa', ancho: '150px', orden: (f) => V.posicionEtapa(f.etapa), formato: (e) => (e ? el('span', { class: 'u2-fila', style: { flexWrap: 'nowrap' } }, W.codigo(e), el('span', { class: 'u2-tenue' }, K.nombreHumanoEtapaSkill(e))) : el('span', { class: 'texto-tenue' }, '—')) },
        { clave: 'version', titulo: 'Versión', ancho: '90px' },
        { clave: 'estado', titulo: 'Estado', ancho: '140px', formato: (e) => ui.estadoIcono(e === 'v1' ? 'aprobado' : 'borrador') },
        { clave: 'dod', titulo: 'Para terminarla', ancho: '260px', orden: (f) => K.faltaParaV1(f).cumple.length, formato: (_x, f) => { const x = K.faltaParaV1(f); return el('span', { title: x.siguiente }, `${x.cumple.length} cumplen · ${x.arreglar.length} fallan · ${x.medir.length} por comprobar`); } },
        { clave: 'lineas', titulo: 'Instrucciones', ancho: '110px', alinear: 'der', formato: (n) => (n == null ? el('span', { class: 'texto-tenue' }, 'no tiene') : `${fmt.num(n)} líneas`) },
        { clave: 'agentes', titulo: 'Agentes', ancho: '150px', orden: (f) => Number(f.agentes.maker) + Number(f.agentes.qa), formato: (a) => el('span', { class: 'u2-fila', style: { flexWrap: 'nowrap' } }, W.tag('Prepara', a.maker ? 'ok' : 'neutro', { suave: !a.maker, titulo: 'IA que hace el trabajo' }), W.tag('Revisa', a.qa ? 'ok' : 'neutro', { suave: !a.qa, titulo: 'IA independiente que revisa' })) },
      ],
    });
  }
  function pintarLista() {
    limpiar(hostLista);
    const v = K.filtrarSkills(filas, filtros);
    conteo.textContent = v.length === filas.length ? `${filas.length} ${filas.length === 1 ? 'guía' : 'guías'}` : `${v.length} de ${filas.length} guías`;
    if (!v.length) { hostLista.appendChild(ui.vacioConPasos({ titulo: 'Ninguna guía coincide con los filtros', explicacion: 'Prueba a quitar algún filtro o a buscar otra palabra.', icono: 'filtro', pasos: [] })); return; }
    hostLista.appendChild(vista === 'tabla' ? tablaSkills(v) : el('div', { class: 'u2-skills' }, v.map(tarjetaSkill)));
  }
  const selEstado = W.selectDe([{ valor: '', texto: 'Todos' }, { valor: 'borrador', texto: 'Borrador' }, { valor: 'v1', texto: 'Terminada (v1)' }], filtros.estado, { class: 'campo campo--chico', 'aria-label': 'Estado', onchange: (ev) => { filtros = { ...filtros, estado: ev.target.value }; pintarLista(); } });
  const texto = el('input', { class: 'campo campo--chico', type: 'search', placeholder: 'Nombre, etapa o descripción…', 'aria-label': 'Buscar guía', oninput: (ev) => { filtros = { ...filtros, texto: ev.target.value }; pintarLista(); } });
  texto.value = filtros.texto;
  const inc = ui.interruptor({ etiqueta: 'Solo las que tienen archivos faltantes', activo: filtros.soloIncompletas, onCambio: (v) => { filtros = { ...filtros, soloIncompletas: v }; pintarLista(); } });
  const segVista = W.segmentado([{ valor: 'tarjetas', texto: 'Tarjetas', icono: 'caja' }, { valor: 'tabla', texto: 'Tabla', icono: 'lista' }], vista, (v) => { vista = v; guardarVista(v); pintarLista(); }, { etiqueta: 'Vista' });
  const barra = el('div', { class: 'u2-herr' },
    el('label', { class: 'u2-herr__campo u2-herr__campo--busca' }, 'Buscar', texto),
    el('label', { class: 'u2-herr__campo' }, 'Estado', selEstado),
    el('div', { class: 'u2-herr__fin' }, inc, conteo, segVista));
  pintarLista();

  const cuerpoLista = filas.length
    ? el('div', { class: 'u2-pila' }, barra, hostLista)
    : ui.vacioConPasos({
      titulo: 'Todavía no hay ninguna guía de trabajo',
      explicacion: 'Todavía no se creó ninguna. Las guías se arman en la pestaña Code, con el método del plan; cuando exista una, aparece aquí sola.',
      icono: 'libro',
      pasos: [{ texto: 'Crea la primera guía con el método del plan (arranque, pulido a mano, repaso, creación, casos de prueba y cierre).' }, { texto: 'Vuelve aquí: verás su versión, los criterios que cumple y lo que le falta para darla por terminada.' }],
    });

  const pagina = el('div', { class: 'pagina' }, cab, metricas,
    el('section', { class: 'u2-bloque', 'aria-labelledby': 'u2-cob-t' },
      el('div', { class: 'u2-bloque__cab' }, el('h2', { id: 'u2-cob-t' }, 'Qué etapas ya tienen guía'), el('span', { class: 'u2-nota' }, 'Las etapas sin guía están marcadas. Haz clic en una que ya tiene guía para abrirla.')),
      cobertura),
    el('section', { 'aria-labelledby': 'u2-lista-t', class: 'u2-pila' },
      el('div', { class: 'u2-bloque__cab', style: { marginBottom: '0' } }, el('h2', { id: 'u2-lista-t', class: 'u2-subtitulo' }, 'Cada guía y qué le falta para darla por terminada')),
      cuerpoLista));

  ctx.alSalir(() => W.cerrarPanelLateral());
  if (seleccion && ctx.params.skill) setTimeout(() => abrir(seleccion), 0);
  return pagina;
}

export async function alCambio(ctx, evento) {
  const lote = Array.isArray(evento && evento.lote) && evento.lote.length ? evento.lote : [evento];
  if (lote.some((e) => e && e.tipo === 'skills')) { if (!W.hayPanelLateral()) ctx.recargar(); return undefined; }
  if (lote.some((e) => e && e.tipo === 'sondeo')) {
    try {
      const d = await ctx.api.get('/skills');
      if (firma(d) !== ultimaFirma && !W.hayPanelLateral()) ctx.recargar();
    } catch (_) { /* sin conexión */ }
  }
  return undefined;
}

// ───────────────────────── detalle de una skill (panel lateral) ─────────────────────────

function criterio(i) {
  const ic = i.ok === true ? 'ok' : (i.ok === false ? 'x-circulo' : 'circulo-punteado');
  const tono = i.ok === true ? 'ok' : (i.ok === false ? 'error' : 'neutro');
  return el('div', { class: 'u2-criterio' },
    el('span', { class: `u2-ic--${tono}` }, icono(ic, { tam: 16 })),
    el('div', null,
      el('div', null, i.corto || i.criterio, i.innegociable ? [' ', W.tag('obligatorio', 'aviso', { suave: true, icono: 'candado', titulo: 'No se puede dar por terminada sin cumplirlo' })] : null),
      i.explica ? el('div', { class: 'u2-nota' }, i.explica) : null,
      i.notaHumana ? el('div', { class: 'u2-nota' }, i.notaHumana) : null,
      i.corto && i.criterio ? ui.soloTecnico(el('div', { class: 'u2-nota' }, i.criterio)) : null,
      i.nota && !i.corto ? el('div', { class: 'u2-nota' }, i.nota) : null));
}

function abrirDetalle(ctx, filas, slug, notasDe, host, alCerrar) {
  const f = filas.find((x) => x.slug === slug);
  if (!f) return;
  const falta = K.faltaParaV1(f);
  const notas = f.etapa ? notasDe(f.etapa) : { total: 0, pendientes: 0, resueltas: 0 };
  const hitoEstado = {
    pulir: notas.total ? `${notas.resueltas} ${notas.resueltas === 1 ? 'resuelta' : 'resueltas'} · ${notas.pendientes} ${notas.pendientes === 1 ? 'pendiente' : 'pendientes'} en Mejoras pendientes` : 'Todavía sin notas en Mejoras pendientes para esta etapa',
    retro: 'Se hace después de la prueba a mano; no queda registrada en los archivos',
    dod: `${falta.cumple.length} de ${falta.total} criterios cumplen · ${falta.medir.length} por comprobar`,
  };
  const tabsEl = ui.tabs([
    {
      id: 'v1', titulo: 'Para darla por terminada', render: () => el('div', { class: 'u2-pila' },
        el('p', { class: 'u2-nota' }, falta.siguiente),
        el('ol', { class: 'u2-hitos' }, K.CAMINO_V1.map((h) => el('li', null, el('div', null, el('strong', null, h.titulo), el('div', { class: 'u2-nota' }, h.detalle), el('div', { class: 'u2-tenue', style: { fontSize: '.84rem' } }, hitoEstado[h.id]),
          h.id === 'pulir' && f.etapa ? el('a', { class: 'enlace', href: `#/pulido?etapa=${f.etapa}` }, 'Abrir las notas de esta etapa') : null)))),
        falta.arreglar.length ? el('div', null, el('h3', { class: 'u2-subtitulo' }, `Arreglar (${falta.arreglar.length})`), falta.arreglar.map(criterio)) : null,
        el('div', null, el('h3', { class: 'u2-subtitulo' }, `Por comprobar (${falta.medir.length})`), el('p', { class: 'u2-nota' }, 'No se ven en los archivos: se comprueban con casos de prueba, la IA que revisa y pruebas en sombra (el sistema trabaja y tú corriges).'), falta.medir.map(criterio)),
        falta.cumple.length ? el('div', null, el('h3', { class: 'u2-subtitulo' }, `Ya cumple (${falta.cumple.length})`), falta.cumple.map(criterio)) : null),
    },
    { id: 'skillmd', titulo: 'Instrucciones', render: () => visorSkillMd(ctx, f) },
    {
      id: 'archivos', titulo: 'Archivos y agentes', render: () => el('div', { class: 'u2-pila' },
        el('div', null, el('h3', { class: 'u2-subtitulo' }, 'Estructura'),
          el('ul', { class: 'u2-lista' }, K.ESTRUCTURA.map((e) => el('li', null,
            el('span', { class: f.archivos[e.clave] ? 'u2-ic--ok' : 'u2-ic--error' }, icono(f.archivos[e.clave] ? 'ok' : 'x-circulo', { tam: 16 })), icono(ICONO_ESTRUCTURA[e.clave] || 'archivo', { tam: 15 }),
            el('span', { class: 'u2-lista__texto' }, e.nombre, ui.soloTecnico(el('span', { class: 'u2-mono' }, ` (${e.etiqueta})`))), el('span', { class: 'u2-tenue' }, f.archivos[e.clave] ? (f.conteos[e.clave] != null ? `${f.conteos[e.clave]} ${f.conteos[e.clave] === 1 ? 'elemento' : 'elementos'}` : 'presente') : 'falta'))))),
        el('div', null, el('h3', { class: 'u2-subtitulo' }, 'Agentes ', ui.ayuda('skill_maker_qa')),
          f.agentes.ids.length
            ? el('ul', { class: 'u2-lista' }, f.agentes.ids.map((a) => el('li', null, icono('robot', { tam: 15 }), el('span', { class: 'u2-lista__texto' }, K.rolDeAgente(a) === 'maker' ? 'IA que prepara' : (K.rolDeAgente(a) === 'qa' ? 'IA que revisa' : 'Otro agente'), ui.soloTecnico(el('span', { class: 'u2-mono' }, ` (${a})`))), W.tag(K.rolDeAgente(a) === 'maker' ? 'Prepara' : (K.rolDeAgente(a) === 'qa' ? 'Revisa' : 'Otro'), K.rolDeAgente(a) === 'otro' ? 'neutro' : 'ok', { suave: K.rolDeAgente(a) === 'otro' }))))
            : el('p', { class: 'u2-aviso' }, 'Esta guía no tiene agentes definidos (el plan pide una IA que prepara y otra, independiente, que revisa, por etapa).')),
        el('div', null, el('h3', { class: 'u2-subtitulo' }, 'Tamaño'),
          W.kvNodo([
            ['Instrucciones principales', f.lineas == null ? null : el('span', { class: 'u2-fila' }, `${fmt.num(f.lineas)} líneas`, f.lineas < K.MAX_LINEAS_SKILL_MD ? W.tag('dentro del límite', 'ok', { suave: true, icono: 'ok' }) : W.tag('demasiado larga', 'error'))],
            ['Descripción', f.descripcion ? el('span', { class: 'u2-fila' }, `${fmt.num([...f.descripcion].length)} caracteres`, [...f.descripcion].length < K.MAX_CARACTERES_DESCRIPCION ? W.tag('dentro del límite', 'ok', { suave: true, icono: 'ok' }) : W.tag('demasiado larga', 'error')) : null],
          ])),
        ui.detalleTecnico('Comandos y rutas', [
          W.kvNodo([['Carpeta', el('code', null, `.claude/skills/${f.slug}/`)], ['Archivo principal', el('code', null, K.rutaSkillMd(f.slug))], ['Estado en archivos', f.estado], ['Versión', f.version]]),
          ...K.comandosSkill(f.slug).map((c) => ui.comando(c.comando, { titulo: c.titulo })),
        ])),
    },
  ], 'v1');

  host.panel = W.panelLateral({
    titulo: f.titulo,
    subtitulo: [f.version ? `v${f.version}` : null, f.etapa ? `etapa ${K.nombreHumanoEtapaSkill(f.etapa)}` : null].filter(Boolean).join(' · ') || f.titulo,
    ancho: '640px',
    cuerpo: el('div', { class: 'u2-pila' },
      el('div', { class: 'u2-fila' }, ui.estadoIcono(f.estado === 'v1' ? 'aprobado' : 'borrador'), ui.termino(f.estado === 'v1' ? 'skill_v1' : 'skill_borrador', { texto: f.estado === 'v1' ? 'Terminada (v1)' : 'En borrador, sin pulir' })),
      f.descripcion ? el('p', { class: 'u2-nota' }, K.primeraFrase(f.descripcion, 260)) : null,
      tabsEl),
    alCerrar: () => { alCerrar(); try { history.replaceState(null, '', '#/skills'); } catch (_) { /* sin history */ } },
    pie: [el('button', { type: 'button', class: 'btn', onclick: () => copiar(K.rutaSkillMd(f.slug)) }, icono('copiar', { tam: 14 }), 'Copiar la ruta de las instrucciones'), el('button', { type: 'button', class: 'btn', onclick: () => host.panel && host.panel.cerrar() }, 'Cerrar')],
  });
}

function visorSkillMd(ctx, f) {
  const caja = el('div', { class: 'u2-pila' }, ui.esqueleto('texto', 6));
  ctx.api.get(`/skills/${encodeURIComponent(f.slug)}/archivo`, { ruta: 'SKILL.md' }).then((d) => {
    limpiar(caja);
    const contenido = d && typeof d.contenido === 'string' ? d.contenido : '';
    if (!contenido) throw Object.assign(new Error('El servidor no devolvió contenido.'), { codigo: 'sin_contenido' });
    caja.appendChild(el('div', { class: 'u2-fila u2-fila--entre' },
      el('span', { class: 'u2-nota' }, `${fmt.num(contenido.split('\n').length)} líneas · solo lectura`),
      ui.fuente([K.rutaSkillMd(f.slug)], {})));
    caja.appendChild(ui.visorTexto(contenido, { tipo: 'md' }));
  }).catch((err) => {
    limpiar(caja);
    caja.appendChild(el('p', { class: 'u2-aviso' }, err && (err.codigo === 'sin_contenido' || err.estado === 404)
      ? 'El panel aún no puede mostrar las instrucciones de esta guía. Ábrelas desde la terminal con el comando de «Archivos y agentes».'
      : `No se pudieron leer las instrucciones: ${(err && (err.mensaje || err.message)) || 'error'}`));
  });
  return caja;
}
