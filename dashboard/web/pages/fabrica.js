// pages/fabrica.js — #/fabrica: «Fábrica de creativos: lo que se produce de noche».
// Explica el turno de noche (00:00→07:00) con una línea de tiempo y muestra, de ofertas/<id>/06-creativos/ y qa/, lo que EXISTA: las piezas por oferta, su estado
// y el control de calidad de 6 puntos con su resultado real. «Qué creativos venden» es solo una guía (anatomía y formatos); la tabla de retorno por formato queda
// «se medirá con nuestros datos». SOLO LECTURA: ningún botón aprueba, publica, activa ni gasta. La lógica vive en lib/fabrica.js (probada sin DOM).

import { ui, el, icono, fmt, reemplazar } from '../ui.js';
import * as C from '../lib/n2-comun.js';
import * as F from '../lib/fabrica.js';
import * as V from '../lib/n2-vista.js';

export const meta = { ruta: 'fabrica', titulo: 'Fábrica', grupo: 'Fábrica y tienda', icono: 'fabrica', escucha: ['oferta'] };

let foco = null; // oferta elegida en esta pantalla (sobrevive a los re-render)
const MAX_MINIATURAS = 12;

async function cargarCreativos(ctx, oferta) {
  const { lec, detalle } = await C.cargarDetalle(ctx.api, oferta.id);
  const etapa = C.etapaDe(detalle, 'D6');
  const hayPaquete = Boolean(etapa) && etapa.artefactos.some((a) => /(^|\/)paquete\.json$/.test(a.ruta));
  let lectura = { estado: 'ausente', dato: null, fuente: [] };
  if (hayPaquete) lectura = await C.leerJsonDeOferta(ctx.api, oferta.id, '06-creativos/paquete.json');
  const paquete = lectura.estado === 'ok' ? lectura.dato : null;
  const rutaQa = (paquete && C.rutaQaSegura(paquete.qa_ref)) || (etapa ? C.ultimoQa(etapa.qa, 'd6-') : null);
  const rutaX1 = (paquete && C.rutaQaSegura(paquete.x1_ref)) || (etapa ? C.ultimoQa(etapa.qa, 'x1-d6-') : null);
  const [qa, x1] = await Promise.all([
    rutaQa ? C.leerJsonDeOferta(ctx.api, oferta.id, rutaQa) : Promise.resolve({ estado: 'ausente', dato: null }),
    rutaX1 ? C.leerJsonDeOferta(ctx.api, oferta.id, rutaX1) : Promise.resolve({ estado: 'ausente', dato: null }),
  ]);
  const modelo = F.modeloCreativos(oferta, { detalle, paquete, qaDoc: qa.estado === 'ok' ? qa.dato : null, x1Doc: x1.estado === 'ok' ? x1.dato : null });
  modelo.lecturas = { detalle: lec, paquete: lectura, qa, x1 };
  modelo.fuentes = [...new Set([...C.unirFuentes(lec, lectura, qa, x1)])];
  return modelo;
}

export async function render(ctx) {
  V.instalar();
  const TITULO = 'Fábrica de anuncios: lo que se prepara de noche';
  const DESCRIPCION = 'Cada noche la fábrica prepara una tanda de anuncios por idioma y la deja lista para tu aprobación. Aquí ves cómo funciona el turno de noche, qué hay preparado, si pasó el control de calidad y qué tipos de anuncio conviene probar.';
  const { lec: lecOfertas, ofertas } = await C.cargarOfertas(ctx);
  if (!lecOfertas.ok && !ofertas.length) {
    return el('div', { class: 'pagina' }, V.cabecera({ titulo: TITULO, descripcion: 'No se pudo leer la lista de ofertas.' }), ui.errorBox(lecOfertas.error, { reintentar: () => ctx.recargar && ctx.recargar() }));
  }
  const modelos = await Promise.all(ofertas.map((o) => cargarCreativos(ctx, o)));
  foco = C.elegirFoco(ofertas, { previa: foco, activa: ctx.estado ? ctx.estado.ofertaActiva : null });
  const resumen = F.resumenFabrica(modelos);
  const fuentes = [...new Set(['ofertas/*/06-creativos/paquete.json', 'ofertas/*/qa/d6-*.json', ...modelos.flatMap((m) => m.fuentes)])];

  const hostControl = el('div', { class: 'n2-pila' });
  const seccionControl = () => {
    const m = modelos.find((x) => x.id === foco) || modelos[0] || null;
    return ui.seccion('Control de calidad: los 6 puntos de cada pieza', controlCuerpo(m), {
      glosario: 'control_seis_puntos',
      ayuda: 'Cada anuncio se repasa con esta lista antes de subir nada. Un punto sin resultado no cuenta como aprobado.',
      acciones: V.selectorOferta(ofertas, foco, (id) => { foco = id; pintarControl(); }),
    });
  };
  const pintarControl = () => reemplazar(hostControl, seccionControl());
  pintarControl();

  return el('div', { class: 'pagina' },
    V.cabecera({ titulo: TITULO, descripcion: DESCRIPCION, fuentes, leido: lecOfertas.generado_en }),
    V.bannerDemo(ofertas),
    ui.atencion({ items: F.avisosFabrica(modelos), vacio: 'Ninguna pieza espera tu aprobación ni está rechazada.' }),
    metricas(resumen),
    avisoNoSeProduce(),
    seccionPorAprobar(ctx, modelos, resumen),
    seccionTurno(),
    hostControl,
    seccionVenden(),
    seccionTecnica(modelos));
}

// ───────────────────────── métricas ─────────────────────────

function metricas(r) {
  return el('div', { class: 'n2-metricas' },
    ui.metrica({ etiqueta: 'Anuncios preparados', valor: r.piezas, contexto: r.ofertasConPaquete ? `en ${r.ofertasConPaquete} ${r.ofertasConPaquete === 1 ? 'oferta' : 'ofertas'}${r.soloDemo ? ' (demo)' : ''}` : 'ninguna oferta tiene anuncios preparados todavía', tono: r.piezas ? undefined : 'aviso', ayuda: 'por_aprobar' }),
    ui.metrica({ etiqueta: 'Esperan tu aprobación', valor: r.esperanFirma, contexto: r.esperanFirma ? 'esperan tu firma en la etapa de creativos' : 'ninguno espera tu firma', tono: r.esperanFirma ? 'acento' : undefined }),
    ui.metrica({ etiqueta: 'Listos para la campaña', valor: r.listas, contexto: r.listas ? 'aprobados por la revisión de calidad y por cumplimiento' : 'se cuentan cuando la revisión de calidad y la de cumplimiento los aprueban', tono: r.listas ? 'ok' : undefined }),
    ui.metrica({ etiqueta: 'Última producción', valor: r.ultimaProduccion ? fmt.relativo(r.ultimaProduccion) : null, contexto: r.ultimaProduccion ? fmt.fecha(r.ultimaProduccion) : 'todavía no se preparó ninguna tanda', ayuda: 'turno_noche' }));
}

function avisoNoSeProduce() {
  return el('section', { class: 'n2-prohibido', 'aria-label': 'Lo que no se produce' },
    el('h3', null, icono('octogono', { tam: 18 }), 'Lo que esta fábrica NO produce'),
    F.NO_SE_PRODUCE.map((n) => el('div', null, el('strong', null, n.titulo), el('p', null, n.texto))));
}

// ───────────────────────── por aprobar ─────────────────────────

function tarjetaPieza(ctx, m, p, pedirImagen) {
  const info = F.ESTADO_PIEZA[p.estado] || F.ESTADO_PIEZA.en_revision;
  const nombre = [p.concepto && `Idea «${p.concepto}»`, p.hookTipo && `gancho: ${p.hookTipo}`].filter(Boolean).join(' · ') || p.adName || 'Anuncio';
  return el('article', { class: 'n2-pieza' },
    V.miniatura(pedirImagen ? ctx : null, m.id, p.archivo),
    el('div', { class: 'n2-pieza__cuerpo' },
      el('h4', { class: 'n2-pieza__titulo' }, p.titular || nombre),
      p.titular ? el('p', { class: 'n2-tenue n2-peq', style: { margin: 0 } }, nombre) : null,
      p.texto ? el('p', { class: 'n2-pieza__texto', title: p.texto }, p.texto) : null,
      el('div', null, V.estado(info, { tam: 14 })),
      el('div', { class: 'n2-pieza__meta' },
        p.formato ? V.etq(p.formato) : null, p.ratio ? V.etq(p.ratio) : null, p.idioma ? V.etq(p.idioma) : null,
        p.lint ? V.etq(`Promesas: ${F.infoVeredicto(p.lint).texto.toLowerCase()}`, { titulo: 'Revisión de promesas prohibidas (la hace cumplimiento) sobre este anuncio' }) : null,
        p.iaGenerado ? V.etq('Hecha con IA') : null)));
}

function ofertaCreativos(ctx, m, contador) {
  const qa = m.qa ? F.infoVeredicto(m.qa.veredicto) : null;
  const x1 = m.x1 ? F.infoVeredicto(m.x1.veredicto) : null;
  const gate = m.etapa ? (m.etapa.gatePendiente ? { tono: 'acento', icono: 'usuario', texto: 'Espera tu aprobación' } : { tono: m.etapa.estado === 'aprobado' ? 'ok' : 'neutro', icono: m.etapa.estado === 'aprobado' ? 'ok' : 'circulo', texto: `Etapa de creativos: ${ui.infoEstado(m.etapa.estado).texto.toLowerCase()}` }) : null;
  return el('article', { class: 'n2-oferta' },
    el('div', { class: 'n2-oferta__cab' },
      el('div', { class: 'n2-fila' }, el('span', { class: 'n2-oferta__id' }, m.id), m.demo ? V.etq('demo', { demo: true }) : null, m.locale ? V.etq(m.locale) : null),
      el('div', { class: 'n2-oferta__estados' },
        gate ? V.estado(gate, { tam: 14 }) : null,
        qa ? V.etq(`Revisión de calidad: ${qa.texto.toLowerCase()}`) : null, x1 ? V.etq(`Cumplimiento: ${x1.texto.toLowerCase()}`) : null,
        m.reserva ? V.etq(`${m.reserva} de reserva`) : null)),
    m.piezas.length
      ? el('div', { class: 'n2-piezas' }, m.piezas.map((p) => tarjetaPieza(ctx, m, p, contador.n++ < MAX_MINIATURAS)))
      : V.nota(el('p', null, m.tienePaquete ? 'Hay un paquete de anuncios, pero no trae ninguna pieza.' : 'Esta oferta todavía no tiene anuncios preparados.'), { tono: 'neutra' }),
    m.piezas.length ? el('a', { class: 'enlace', href: `#/oferta/${encodeURIComponent(m.id)}` }, 'Ver la oferta completa y sus archivos') : null);
}

function seccionPorAprobar(ctx, modelos, resumen) {
  const conPiezas = modelos.filter((m) => m.piezas.length);
  let cuerpo;
  if (!conPiezas.length) {
    cuerpo = ui.vacioConPasos({
      titulo: 'Todavía no hay piezas por aprobar',
      explicacion: 'Cuando la etapa de creativos prepara un paquete de anuncios, cada pieza aparece aquí con su imagen, su texto y su estado. Hoy ninguna oferta llegó a esa etapa con piezas.',
      icono: 'pantalla',
      pasos: [
        { texto: 'La oferta tiene que tener producto, página de venta y cobro aprobados. Este comando te dice cuál es la siguiente etapa:', comando: 'python -m engine.orq siguiente --oferta OF-AAAAMM-NN', nota: 'Cambia OF-AAAAMM-NN por el identificador de tu oferta.' },
        { texto: 'La etapa de creativos prepara el paquete y el revisor deja su informe de calidad. Esta pantalla los lee sola.' },
        { texto: 'Si el paquete queda esperando tu firma, aparece arriba en «Requiere tu atención».' },
      ],
    });
  } else {
    const contador = { n: 0 };
    cuerpo = el('div', { class: 'n2-pila' }, conPiezas.map((m) => ofertaCreativos(ctx, m, contador)),
      modelos.length > conPiezas.length ? el('p', { class: 'n2-tenue n2-peq', style: { margin: 0 } }, `${modelos.length - conPiezas.length} ${modelos.length - conPiezas.length === 1 ? 'oferta más no tiene' : 'ofertas más no tienen'} anuncios preparados todavía.`) : null);
  }
  return ui.seccion(`Por aprobar${resumen.piezas ? ` (${resumen.piezas})` : ''}`, cuerpo, {
    glosario: 'por_aprobar',
    ayuda: 'Los anuncios que existen en cada oferta, con el estado que les dan el paquete, la revisión de calidad y el informe de cumplimiento. El panel no aprueba nada: la aprobación es tu firma.',
  });
}

// ───────────────────────── turno de noche ─────────────────────────

function pasoTurno(p) {
  const h = F.ESTADO_PASO[p.hoy.estado] || F.ESTADO_PASO.falta;
  return el('li', { class: ['n2-paso', p.hoy.estado === 'existe' && 'n2-paso--ok', p.hoy.estado === 'parcial' && 'n2-paso--aviso'] },
    el('div', { class: 'n2-paso__hora' }, p.hora || ''),
    el('div', { class: 'n2-paso__riel' }, el('span', { class: 'n2-paso__nodo' }, icono(p.icono, { tam: 15 }))),
    el('div', { class: 'n2-paso__cuerpo' },
      el('h3', { class: 'n2-paso__nombre' }, p.nombre),
      el('p', { class: 'n2-paso__que' }, p.que),
      el('div', { class: 'n2-paso__hoy' }, V.estado({ tono: h.tono, icono: p.hoy.estado === 'existe' ? 'ok' : p.hoy.estado === 'parcial' ? 'alerta' : 'circulo-punteado', texto: h.texto }, { tam: 14 }), el('span', null, p.hoy.texto))));
}

function seccionTurno() {
  const tarde = F.CARGA_TARDE;
  const th = F.ESTADO_PASO[tarde.hoy.estado];
  return ui.seccion('El turno de noche, de 00:00 a 07:00', el('div', { class: 'n2-pila' },
    el('ol', { class: 'n2-tiempo', 'aria-label': 'Pasos del turno de noche' }, F.TURNO_NOCHE.map(pasoTurno)),
    el('div', { class: 'n2-tarde' }, el('ol', { class: 'n2-tiempo', 'aria-label': 'Carga a la tarde' }, el('li', { class: 'n2-paso n2-paso--aviso' },
      el('div', { class: 'n2-paso__hora' }, tarde.hora),
      el('div', { class: 'n2-paso__riel' }, el('span', { class: 'n2-paso__nodo' }, icono('megafono', { tam: 15 }))),
      el('div', { class: 'n2-paso__cuerpo' },
        el('h3', { class: 'n2-paso__nombre' }, tarde.nombre), el('p', { class: 'n2-paso__que' }, tarde.que),
        el('div', { class: 'n2-paso__hoy' }, V.estado({ tono: th.tono, icono: 'alerta', texto: th.texto }, { tam: 14 }), el('span', null, tarde.hoy.texto)))))),
    V.nota(el('p', null, el('strong', null, 'Regla de horario: '), F.REGLA_HORARIO)),
    el('p', { class: 'n2-tenue n2-peq', style: { margin: 0 } }, 'El estado de cada paso («Ya existe», «Parcial», «Falta construir») es el que tenía la fábrica el 6 de noviembre de 2026, según el plan del sistema. El panel no lo comprueba solo, así que puede quedar desactualizado.')),
  { glosario: 'turno_noche', ayuda: 'Mientras duermes, la fábrica prepara una tanda nueva para cada idioma. Primero reemplaza lo que se cansa, después prueba enfoques nuevos y traduce los ganadores. Esto es cómo funciona el método y qué parte de él existe hoy.' });
}

// ───────────────────────── control de calidad ─────────────────────────

function controlCuerpo(m) {
  if (!m) return ui.vacioConPasos({ titulo: 'No hay ofertas todavía', explicacion: 'El control de calidad se muestra por oferta cuando exista su paquete de anuncios.', icono: 'escudo', pasos: [] });
  const res = F.resumenControl(m.control);
  const qa = m.qa;
  const resumen = [
    res.pasa ? `${res.pasa} ${res.pasa === 1 ? 'pasa' : 'pasan'}` : null,
    res.parcial ? `${res.parcial} a medias` : null,
    res.falla ? `${res.falla} ${res.falla === 1 ? 'falla' : 'fallan'}` : null,
    res.no_aplica ? `${res.no_aplica} no ${res.no_aplica === 1 ? 'aplica' : 'aplican'}` : null,
    res.sin_resultado ? `${res.sin_resultado} sin resultado` : null,
  ].filter(Boolean).join(' · ');
  return el('div', { class: 'n2-pila' },
    el('div', { class: 'n2-fila n2-fila--entre' },
      el('div', { class: 'n2-fila' }, el('strong', null, m.id), m.demo ? V.etq('demo', { demo: true }) : null, el('span', { class: 'n2-tenue' }, resumen)),
      qa && qa.veredicto ? el('div', { class: 'n2-fila' }, el('span', { class: 'n2-tenue n2-peq' }, 'Veredicto del revisor:'), ui.chip(F.infoVeredicto(qa.veredicto).texto, F.infoVeredicto(qa.veredicto).tono), qa.puntaje ? el('span', { class: 'n2-tenue n2-peq' }, `puntaje ${qa.puntaje}${qa.umbral ? ` de un mínimo de ${qa.umbral}` : ''}`) : null) : null),
    el('div', { class: 'n2-control-wrap' }, el('ol', { class: 'n2-control' }, m.control.map((p) => {
      const info = F.ESTADO_CONTROL[p.estado];
      return el('li', { class: 'n2-punto' },
        el('span', { class: 'n2-punto__n' }, String(p.n)),
        el('div', null, el('h3', { class: 'n2-punto__titulo' }, p.titulo), el('p', { class: 'n2-punto__explica' }, p.explica)),
        el('div', { class: 'n2-punto__res' }, V.estado(info, { tam: 16 }), el('p', { class: 'n2-punto__evid' }, p.evidencia), p.origen ? el('span', { class: 'n2-tenue n2-peq' }, `Origen: ${p.origen}`) : null));
    }))),
    !qa ? V.nota(el('p', null, 'Esta oferta no tiene informe del revisor de creativos, por eso los puntos que dependen de él salen «sin resultado». Los que se deducen del propio paquete (idioma del texto, revisión de promesas, si hay video o imágenes hechas con IA) se muestran con su origen.'), { tono: 'neutra' }) : null,
    V.tecnico('Comprobaciones automáticas del revisor',
      qa && qa.checks.length
        ? V.tablaPropia([{ titulo: 'Comprobación' }, { titulo: 'Resultado' }, { titulo: 'Detalle' }], qa.checks.map((c) => [el('code', { class: 'n2-mono' }, c.id), c.resultado, c.detalle]), { etiqueta: 'Comprobaciones del revisor', compacta: true })
        : el('p', { class: 'n2-tenue' }, 'Sin comprobaciones registradas.'),
      el('p', { class: 'n2-tenue n2-peq' }, 'Cada punto se alimenta de estas comprobaciones: audio D6-L1-07 · idioma D6-L1-06 · texto D6-L1-06 y 01 · caras y manos D6-L1-07 y 09 · material ajeno D6-L1-08 y 09 · promesas D6-L1-02, 03 y 05.')));
}

// ───────────────────────── qué creativos venden ─────────────────────────

function seccionVenden() {
  const anatomia = el('ol', { class: 'n2-anatomia', 'aria-label': 'Anatomía del anuncio que gana' }, F.ANATOMIA.map((a) => el('li', null,
    el('span', { class: 'n2-anatomia__n' }, `${a.n} · ${a.donde}`),
    el('h4', { class: 'n2-anatomia__nombre' }, a.nombre),
    el('p', { class: 'n2-parrafo' }, a.que),
    el('p', { class: 'n2-anatomia__nuestro' }, el('strong', null, 'Aquí: '), a.nuestro))));
  const formatos = V.tablaPropia(
    [{ titulo: 'Formato' }, { titulo: 'Qué se espera de él' }, { titulo: 'Cómo lo hacemos aquí' }, { titulo: 'En la práctica' }, { titulo: 'Retorno en nuestras ventas' }],
    F.FORMATOS.map((f) => {
      const e = F.ESTADO_FORMATO[f.estado];
      return [el('strong', null, f.nombre), f.rol, f.nuestro, ui.chip(e.texto, e.tono), V.etq(F.SE_MIDE, { hipotesis: true })];
    }), { etiqueta: 'Formatos de anuncio' });
  return ui.seccion('Qué anuncios venden: una guía', el('div', { class: 'n2-pila' },
    V.nota(el('p', null, el('strong', null, 'Es una guía, no un resultado. '), 'Describe lo que enseña el método que adoptamos; todavía no hay ventas propias que lo confirmen. Cuando las haya, lo que rinde cada formato se medirá con nuestros datos.'), { tono: 'neutra' }),
    el('h3', { class: 'n2-subtitulo' }, 'Cómo es un anuncio que gana'),
    anatomia,
    el('p', { class: 'n2-lema' }, F.LEMA),
    el('h3', { class: 'n2-subtitulo' }, 'Los formatos'),
    formatos,
    V.tecnico('Por qué no se muestran cifras de retorno por formato', el('p', { class: 'n2-parrafo' }, F.NOTA_RETORNO))),
  { glosario: 'retorno_por_formato', ayuda: 'Cómo es un buen anuncio y qué formatos se prueban, adaptados a nuestras reglas. La columna de retorno queda vacía a propósito.' });
}

// ───────────────────────── detalle técnico ─────────────────────────

function seccionTecnica(modelos) {
  const m = modelos.find((x) => x.id === foco) || modelos[0] || null;
  const t = F.detalleTecnicoFabrica(m);
  return V.tecnico('Detalle técnico: archivos y comandos',
    el('h4', { class: 'n2-subtitulo' }, 'De qué archivos salen los datos'), V.listaRutas(t.archivos),
    el('h4', { class: 'n2-subtitulo' }, 'Comandos que puedes copiar (el panel solo los muestra)'),
    t.comandos.map((c) => ui.comando(c.comando, { titulo: c.titulo, abierto: false })));
}
