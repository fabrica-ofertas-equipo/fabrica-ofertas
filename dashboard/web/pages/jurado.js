// pages/jurado.js — #/jurado: «Jurado: los 10 clientes que votan antes de gastar».
// Explica los 5 pasos del jurado y lee, si existe, ofertas/<id>/06-creativos/jurado.json (esquema aún sin definir: se lee con tolerancia) para mostrar los votos,
// el orden de la tanda y la precisión contra lo cobrado (AUC y Brier cuando existan). Hoy casi seguro está vacío: entonces dice qué lo producirá y la regla de
// apagado. SOLO LECTURA. Los textos de los jurados son datos no confiables (textContent); su salida es interna y nunca se cita en un anuncio.
// La lógica vive en lib/jurado.js (probada sin DOM).

import { ui, el, icono, fmt, reemplazar } from '../ui.js';
import * as C from '../lib/n2-comun.js';
import * as J from '../lib/jurado.js';
import * as V from '../lib/n2-vista.js';

export const meta = { ruta: 'jurado', titulo: 'Jurado', grupo: 'Jurado', icono: 'balanza', escucha: ['oferta'] };

let foco = null;
const TITULO = 'Jurado: los 10 clientes que votan antes de gastar';
const DESCRIPCION = 'Antes de gastar en un anuncio, diez clientes ideales simulados con IA lo votan a ciegas y explican por qué. Sus votos ordenan la tanda y, a los pocos días, se comparan con lo que pasó de verdad para saber si acertaron.';

async function cargarJurado(ctx, oferta) {
  const [{ detalle }, lectura] = await Promise.all([C.cargarDetalle(ctx.api, oferta.id), C.leerJsonDeOferta(ctx.api, oferta.id, '06-creativos/jurado.json')]);
  const mercado = C.mercadoDe(detalle);
  const jurado = J.modeloJurado(lectura);
  return { ...oferta, jurado, locale: jurado.mercado || (mercado ? mercado.locale : null), lectura, fuentes: C.unirFuentes(lectura) };
}

export async function render(ctx) {
  V.instalar();
  const { lec: lecOfertas, ofertas } = await C.cargarOfertas(ctx);
  if (!lecOfertas.ok && !ofertas.length) {
    return el('div', { class: 'pagina' }, V.cabecera({ titulo: TITULO, descripcion: 'No se pudo leer la lista de ofertas.' }), ui.errorBox(lecOfertas.error, { reintentar: () => ctx.recargar && ctx.recargar() }));
  }
  const modelos = await Promise.all(ofertas.map((o) => cargarJurado(ctx, o)));
  foco = C.elegirFoco(ofertas, { previa: foco, activa: ctx.estado ? ctx.estado.ofertaActiva : null });
  const res = J.resumenJurado(modelos);
  const fuentes = ['ofertas/*/06-creativos/jurado.json', ...modelos.flatMap((m) => m.fuentes)];

  const hostPrecision = el('div');
  const pintarPrecision = () => reemplazar(hostPrecision, seccionPrecision(modelos, ofertas));
  pintarPrecision();

  return el('div', { class: 'pagina' },
    V.cabecera({ titulo: TITULO, descripcion: DESCRIPCION, fuentes: [...new Set(fuentes)], leido: lecOfertas.generado_en }),
    V.bannerDemo(ofertas),
    ui.atencion({ items: avisos(modelos), vacio: 'Nada del jurado requiere tu atención ahora.', titulo: 'Requiere tu atención' }),
    metricas(res, J.papelDelJurado(modelos)),
    seccionPasos(),
    seccionRegla(),
    seccionVotos(modelos),
    hostPrecision,
    seccionTecnica());

  function seccionPrecision(ms, os) {
    const m = ms.find((x) => x.id === foco) || ms[0] || null;
    return ui.seccion('Precisión contra lo cobrado', precisionCuerpo(m), {
      glosario: 'etiquetas_jurado',
      ayuda: 'El jurado solo se juzga cuando sus votos ya se pueden comparar con lo que pasó de verdad: antes de 150 votos comprobados, medir el acierto es medir ruido.',
      acciones: V.selectorOferta(os, foco, (id) => { foco = id; pintarPrecision(); }),
    });
  }
}

function avisos(modelos) {
  const items = [];
  for (const m of modelos) {
    const ev = J.evaluarPrecision(m.jurado.precision);
    if (ev.estado === 'apagar') items.push({ tono: 'grave', titulo: `El jurado de ${m.id} no supera al azar: se apaga`, detalle: ev.texto, accion: { texto: 'Ver la oferta', ruta: `/oferta/${m.id}` } });
    if (m.jurado.estado === 'ilegible') items.push({ tono: 'aviso', titulo: `El archivo del jurado de ${m.id} no se pudo leer`, detalle: 'Puede estar cortado o dañado.', accion: { texto: 'Ver la oferta', ruta: `/oferta/${m.id}` } });
  }
  return items;
}

function metricas(r, papel) {
  return el('div', { class: 'n2-metricas' },
    ui.metrica({ etiqueta: 'Ofertas con jurado', valor: r.conJurado, contexto: r.conJurado ? `de ${r.ofertas} ${r.ofertas === 1 ? 'oferta' : 'ofertas'}` : 'ninguna oferta tiene votos todavía', tono: r.conJurado ? undefined : 'aviso', ayuda: 'jurado_votacion' }),
    ui.metrica({ etiqueta: 'Votos registrados', valor: r.votos, contexto: r.votos ? `sobre ${r.piezas} ${r.piezas === 1 ? 'pieza' : 'piezas'}` : 'el jurado aún no votó nada' }),
    ui.metrica({ etiqueta: 'Votos comprobados con lo cobrado', valor: `${fmt.num(r.etiquetas)} de ${J.PARAMETROS.etiquetas_min}`, contexto: r.etiquetas >= J.PARAMETROS.etiquetas_min ? 'ya se puede juzgar su acierto' : 'hasta llegar a 150 no se juzga su acierto', ayuda: 'etiquetas_jurado' }),
    ui.metrica({ etiqueta: 'Papel del jurado hoy', valor: papel.valor, contexto: papel.contexto, tono: papel.tono, ayuda: 'modo_sombra' }));
}

// ───────────────────────── cómo funciona ─────────────────────────

function seccionPasos() {
  return ui.seccion('Cómo funciona, en 5 pasos', el('ol', { class: 'n2-pasos5', 'aria-label': 'Los 5 pasos del jurado' }, J.PASOS_JURADO.map((p) => el('li', null,
    el('div', { class: 'n2-fila' }, el('span', { class: 'n2-pasos5__num' }, String(p.n)), icono(p.icono, { tam: 18 })),
    el('h3', { class: 'n2-pasos5__titulo' }, p.n === 1 ? el('span', null, ui.termino('voto_a_ciegas', { texto: p.titulo })) : p.titulo),
    el('p', { class: 'n2-pasos5__texto' }, p.texto)))),
  { glosario: 'jurado_votacion', ayuda: 'Cada jurado es un cliente ideal con su edad, su país, su idioma y lo que le preocupa; sus perfiles son distintos a propósito (uno desconfía de todo, otro compra por impulso, otro es analítico).' });
}

function seccionRegla() {
  const p = J.PARAMETROS;
  return ui.seccion('La regla que lo mantiene honesto', el('div', { class: 'n2-pila' },
    el('div', { class: 'n2-regla' },
      el('h3', null, icono('balanza', { tam: 20 }), J.REGLA.titulo),
      el('p', null, J.REGLA.texto),
      el('p', null, J.REGLA.sombra)),
    V.nota(el('p', null, el('strong', null, 'Solo para uso interno. '), 'Los votos son opiniones de una IA: sirven para ordenar la tanda y nunca se citan en un anuncio ni en la página («7 de 10 comprarían» sería una cifra de clientes inventada).'), { tono: 'aviso' }),
    el('div', { class: 'n2-fila' },
      V.etq(`${p.jurados_por_mercado} jurados por mercado`, { hipotesis: true, titulo: 'Valor propuesto, a ajustar' }),
      V.etq(`${p.etiquetas_min} votos comprobados para juzgarlo`, { hipotesis: true, titulo: 'Valor propuesto, a ajustar' }),
      V.etq(`Acierto mínimo para decidir (AUC): ${p.auc_min.toFixed(2).replace('.', ',')}`, { hipotesis: true, titulo: 'Valor propuesto, a ajustar' }),
      el('span', { class: 'n2-tenue n2-peq' }, 'Valores propuestos por el sistema, todavía sin ajustar con datos propios.'))));
}

// ───────────────────────── votos y orden de la tanda ─────────────────────────

function puntoVoto(v) {
  const clase = v.voto === true ? 'n2-voto--si' : v.voto === false ? 'n2-voto--no' : '';
  const nombre = `${v.avatar || 'Jurado'}: ${J.textoVoto(v.voto)}`;
  return el('span', { class: ['n2-voto', clase], title: nombre, role: 'img', 'aria-label': nombre }, icono(v.voto === true ? 'check' : v.voto === false ? 'cerrar' : 'menos', { tam: 12 }));
}

function filaTanda(fila, pieza) {
  const aFavor = pieza ? `${pieza.si} de ${pieza.total} a favor` : 'sin votos';
  return el('li', null,
    el('span', { class: 'n2-tanda__pos', title: 'Lugar en la tanda' }, String(fila.posicion)),
    el('div', { class: 'n2-tanda__cuerpo' },
      el('div', { class: 'n2-fila n2-fila--entre' }, el('span', { class: 'n2-tanda__nombre' }, fila.ad), el('span', { class: 'n2-fila' }, V.etq(aFavor), (fila.puntaje ?? (pieza && pieza.puntaje)) !== null && (fila.puntaje ?? (pieza && pieza.puntaje)) !== undefined ? V.etq(`puntaje ${fmt.num(fila.puntaje ?? pieza.puntaje, 1)}`) : null)),
      pieza && pieza.motivos.length ? el('div', { class: 'n2-votos', 'aria-label': 'Votos de cada jurado' }, pieza.motivos.map(puntoVoto)) : null,
      pieza && pieza.motivos.some((x) => x.motivo)
        ? el('details', { class: 'n2-detalle' }, el('summary', null, 'Por qué votaron así'), el('ul', { class: 'n2-motivos' }, pieza.motivos.filter((x) => x.motivo).map((x) => el('li', null, el('strong', null, `${x.avatar || 'Jurado'} (${J.textoVoto(x.voto)}):`), el('span', null, x.motivo)))))
        : null));
}

function bloqueJurado(m) {
  const j = m.jurado;
  const filas = j.orden.map((o) => ({ fila: o, pieza: j.piezas.find((p) => p.ad === o.ad) || null }));
  return el('article', { class: 'n2-oferta' },
    el('div', { class: 'n2-oferta__cab' },
      el('div', { class: 'n2-fila' }, el('span', { class: 'n2-oferta__id' }, m.id), m.demo ? V.etq('demo', { demo: true }) : null, m.locale ? V.etq(m.locale) : null),
      el('div', { class: 'n2-oferta__estados' },
        V.etq(`${j.avatares.length || '—'} ${j.avatares.length === 1 ? 'jurado' : 'jurados'}`), V.etq(`${j.votos.length} ${j.votos.length === 1 ? 'voto' : 'votos'}`),
        j.modo ? V.etq(`modo: ${j.modo}`) : null, j.generadoEn ? el('span', { class: 'n2-tenue n2-peq' }, `generado ${fmt.relativo(j.generadoEn)}`) : null)),
    j.orden.length
      ? el('div', { class: 'n2-pila n2-pila--chica' },
        el('h3', { class: 'n2-subtitulo' }, 'Orden de la tanda'),
        el('p', { class: 'n2-tenue n2-peq', style: { margin: 0 } }, j.ordenOrigen === 'archivo' ? 'Orden que dejó el jurado: los primeros salen antes a la prueba.' : 'El jurado no dejó un orden: el panel ordena por votos a favor (no es el orden oficial).'),
        el('ol', { class: 'n2-tanda' }, filas.map((x) => filaTanda(x.fila, x.pieza))))
      : V.nota(el('p', null, 'Hay un archivo del jurado, pero todavía no trae votos ni orden de la tanda.'), { tono: 'neutra' }),
    j.ideas.length ? el('div', { class: 'n2-pila n2-pila--chica' }, el('h3', { class: 'n2-subtitulo' }, 'Ideas que propuso el jurado'), el('ul', { class: 'n2-motivos' }, j.ideas.map((i) => el('li', null, icono('chispa', { tam: 14 }), el('span', null, i))))) : null);
}

const PASOS_VACIOS = [
  { texto: 'La etapa de creativos deja el paquete de anuncios aprobado por el revisor y por cumplimiento: es lo que el jurado vota.' },
  { texto: 'Después, el jurado vota a ciegas, con diez clientes por mercado, y deja el resultado en un archivo de la oferta. Todavía no existe el programa que hace esto: está planeado como la pieza 3 del sistema. Los archivos exactos están en el detalle técnico.' },
  { texto: 'A los pocos días, una tarea semanal compara cada voto con lo que pasó de verdad y mide el acierto. Tampoco existe todavía.' },
];

function seccionVotos(modelos) {
  const con = modelos.filter((m) => m.jurado.estado === 'ok' || m.jurado.estado === 'vacio');
  const rotos = modelos.filter((m) => m.jurado.estado === 'ilegible' || m.jurado.estado === 'error');
  let cuerpo;
  if (!con.length && !rotos.length) {
    cuerpo = ui.vacioConPasos({
      titulo: 'El jurado todavía no votó nada',
      explicacion: 'Ninguna oferta tiene todavía el archivo del jurado. Cuando exista, aquí vas a ver qué votó cada cliente, por qué, y en qué orden salen los anuncios a la prueba.',
      icono: 'balanza', pasos: PASOS_VACIOS,
    });
  } else {
    cuerpo = el('div', { class: 'n2-pila' },
      con.map(bloqueJurado),
      rotos.map((m) => V.avisoLectura(`No se pudo leer el jurado de ${m.id}.`, m.lectura.error)),
      modelos.length > con.length + rotos.length ? el('p', { class: 'n2-tenue n2-peq', style: { margin: 0 } }, `${modelos.length - con.length - rotos.length} ${modelos.length - con.length - rotos.length === 1 ? 'oferta más no tiene' : 'ofertas más no tienen'} jurado todavía.`) : null);
  }
  return ui.seccion('Lo que votó el jurado', cuerpo, { glosario: 'voto_a_ciegas', ayuda: 'Los votos de cada cliente simulado y el orden en que salen los anuncios a la prueba.' });
}

// ───────────────────────── precisión ─────────────────────────

const numEs = (n, d = 2) => fmt.num(n, d);

function precisionCuerpo(m) {
  const p = m ? m.jurado.precision : null;
  const ev = J.evaluarPrecision(p);
  const min = J.PARAMETROS.etiquetas_min;
  return el('div', { class: 'n2-pila' },
    el('div', { class: 'n2-metricas' },
      ui.metrica({ etiqueta: 'Acierto al ordenar (AUC)', valor: p && p.auc !== null ? numEs(p.auc) : null, contexto: p && p.auc !== null ? '0,50 es tirar una moneda; 1 es acertar siempre' : 'se calcula cuando haya votos comprobados', ayuda: 'auc_jurado', tono: ev.estado === 'util' ? 'ok' : ev.estado === 'apagar' ? 'critico' : ev.estado === 'sombra' ? 'aviso' : undefined }),
      ui.metrica({ etiqueta: 'Error de las probabilidades (Brier)', valor: p && p.brier !== null ? numEs(p.brier) : null, contexto: p && p.brier !== null ? 'menos es mejor; apostar siempre 50/50 da 0,25' : 'se calcula cuando haya votos comprobados', ayuda: 'brier_jurado' }),
      ui.metrica({ etiqueta: 'Votos comprobados', valor: `${fmt.num(ev.etiquetas)} de ${min}`, contexto: ev.falta > 0 ? `faltan ${fmt.num(ev.falta)} para juzgarlo` : 'ya se puede juzgar', ayuda: 'etiquetas_jurado' })),
    V.barra({ valor: ev.etiquetas, max: min, etiqueta: 'Votos comprobados reunidos', texto: `${fmt.num(ev.etiquetas)} de ${min}`, tono: ev.estado === 'util' ? 'ok' : ev.estado === 'apagar' ? 'error' : null }),
    V.nota(el('div', null, el('p', null, el('strong', null, ev.titulo)), el('p', null, ev.texto)), { tono: { ok: 'ok', error: 'error', aviso: 'aviso', info: 'info', neutro: 'neutra' }[ev.tono] || 'neutra', icono: ev.estado === 'util' ? 'ok' : ev.estado === 'apagar' ? 'octogono' : 'info' }),
    p && p.baselines.length
      ? el('div', { class: 'n2-pila n2-pila--chica' }, el('h3', { class: 'n2-subtitulo' }, 'Contra qué se compara'),
        V.tablaPropia([{ titulo: 'Referencia' }, { titulo: 'Acierto al ordenar (AUC)' }], p.baselines.map((b) => [b.nombre, b.auc !== null ? numEs(b.auc) : null]), { etiqueta: 'Referencias de comparación', compacta: true }))
      : null,
    !p ? el('p', { class: 'n2-tenue n2-peq', style: { margin: 0 } }, 'Lo producirá la tarea semanal que ajusta al jurado (todavía por construir) y compara cada voto con lo cobrado.') : null);
}

// ───────────────────────── detalle técnico ─────────────────────────

function seccionTecnica() {
  return V.tecnico('Detalle técnico: archivos que lee esta pantalla',
    V.listaRutas(['ofertas/<id>/06-creativos/jurado.json — votos, orden de la tanda y medición (esquema aún sin definir)', 'empresa/jurado/calibracion/AAAA-Sww.json — AUC y Brier semanales (planeado)', 'empresa/jurado/avatares/<idioma>.yaml — los clientes sintéticos de cada mercado (planeado)']),
    el('p', { class: 'n2-tenue n2-peq' }, 'Se aceptan varias formas del archivo: una lista de votos, un objeto con «votos» o con las piezas y sus votos; el orden en «orden», «tanda» o «ranking»; y la medición en «precision», «calibracion» o «metricas» (auc, brier, etiquetas). Lo que falte sale como «—».'));
}
