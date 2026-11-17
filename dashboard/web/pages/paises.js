// pages/paises.js — #/paises: «Países: del idioma base a todos los idiomas».
// Muestra el mercado e idioma de cada oferta (ofertas/<id>/mercado.json), la ruta de FAMILIA (madre validada → hijas) y el TABLERO DE LANZAMIENTO DE IDIOMA de
// 6 columnas y 25 tarjetas. La lista de tarjetas es una PLANTILLA estática (lib/paises.js); el estado de cada una sale SOLO de ofertas/<id>/lanzamiento_idioma.json,
// que escribe el código (aún no existe): sin él todo es «sin evidencia todavía». El panel nunca marca una tarjeta. También lista las obligaciones por país
// que el método de Mentor no trae (IVA/OSS, desistimiento, consentimiento…). SOLO LECTURA. La lógica vive en lib/paises.js (probada sin DOM).

import { ui, el, icono, fmt, reemplazar } from '../ui.js';
import * as C from '../lib/n2-comun.js';
import * as P from '../lib/paises.js';
import * as V from '../lib/n2-vista.js';

export const meta = { ruta: 'paises', titulo: 'Países', grupo: 'Países', icono: 'mundo', escucha: ['oferta'] };

let foco = null;
const TITULO = 'Países: del idioma base a todos los idiomas';
const DESCRIPCION = 'Se prueba una oferta en un idioma; si funciona, se lleva a los demás con una lista de control que no deja lanzar un idioma hasta que todo está listo. Aquí ves el mercado de cada oferta, qué falta por idioma y qué exige la ley en cada país.';

async function cargarPais(ctx, oferta) {
  const [{ lec, detalle }, tablero] = await Promise.all([C.cargarDetalle(ctx.api, oferta.id), C.leerJsonDeOferta(ctx.api, oferta.id, 'lanzamiento_idioma.json')]);
  const modelo = P.modeloTablero(tablero);
  return { oferta, detalle, mercado: C.mercadoDe(detalle), tablero: modelo, lecturaTablero: tablero, fila: P.filaMercado(oferta, detalle, modelo), fuentes: C.unirFuentes(lec, tablero) };
}

export async function render(ctx) {
  V.instalar();
  const { lec: lecOfertas, ofertas } = await C.cargarOfertas(ctx);
  if (!lecOfertas.ok && !ofertas.length) {
    return el('div', { class: 'pagina' }, V.cabecera({ titulo: TITULO, descripcion: 'No se pudo leer la lista de ofertas.' }), ui.errorBox(lecOfertas.error, { reintentar: () => ctx.recargar && ctx.recargar() }));
  }
  const datos = await Promise.all(ofertas.map((o) => cargarPais(ctx, o)));
  foco = C.elegirFoco(ofertas, { previa: foco, activa: ctx.estado ? ctx.estado.ofertaActiva : null });
  const filas = datos.map((d) => d.fila);
  const res = P.resumenPaises(filas, datos.map((d) => d.tablero));
  const fuentes = ['ofertas/*/mercado.json', 'ofertas/*/lanzamiento_idioma.json', ...datos.flatMap((d) => d.fuentes)];

  const hostFoco = el('div', { class: 'n2-pila' });
  const focoActual = () => datos.find((d) => d.oferta.id === foco) || datos[0] || null;
  const pintarFoco = () => reemplazar(hostFoco, seccionTablero(focoActual(), ofertas, (id) => { foco = id; pintarFoco(); }), seccionObligaciones(focoActual()));
  pintarFoco();

  return el('div', { class: 'pagina' },
    V.cabecera({ titulo: TITULO, descripcion: DESCRIPCION, fuentes: [...new Set(fuentes)], leido: lecOfertas.generado_en }),
    V.bannerDemo(ofertas),
    ui.atencion({ items: avisos(datos), vacio: 'Ningún idioma espera una decisión tuya ahora.' }),
    metricas(res),
    seccionMercados(filas),
    seccionFamilia(filas),
    hostFoco,
    seccionTecnica());
}

function avisos(datos) {
  const items = [];
  for (const d of datos) {
    if (d.tablero.incoherente) items.push({ tono: 'grave', titulo: `La lista de control de ${d.oferta.id} dice «verde», pero hay tarjetas sin completar`, detalle: 'El archivo se contradice a sí mismo: no hay que activar nada hasta revisarlo.', accion: { texto: 'Ver la oferta', ruta: `/oferta/${d.oferta.id}` } });
    const il = d.mercado ? d.mercado.idiomaLegal : null;
    if (il && il.obligacion === true && il.revisorNativo !== true) items.push({ tono: 'aviso', titulo: `${d.oferta.id}: idioma con obligación legal y sin revisor nativo`, detalle: 'Sin revisor nativo el idioma no se puede aprobar ni lanzar.', accion: { texto: 'Ver la oferta', ruta: `/oferta/${d.oferta.id}` } });
    if (d.tablero.hayArchivo && d.tablero.tarjetas.some((t) => t.estado === 'bloqueada')) items.push({ tono: 'grave', titulo: `${d.tablero.tarjetas.filter((t) => t.estado === 'bloqueada').length} tarjeta(s) bloqueada(s) en ${d.oferta.id}`, detalle: 'Una tarjeta bloqueada impide activar el idioma.', accion: { texto: 'Ver la oferta', ruta: `/oferta/${d.oferta.id}` } });
  }
  return items;
}

function metricas(r) {
  return el('div', { class: 'n2-metricas' },
    ui.metrica({ etiqueta: 'Ofertas con mercado', valor: r.conMercado, contexto: `de ${r.ofertas} ${r.ofertas === 1 ? 'oferta' : 'ofertas'}`, tono: r.ofertas && !r.conMercado ? 'aviso' : undefined }),
    ui.metrica({ etiqueta: 'Idiomas distintos', valor: r.idiomas, contexto: r.idiomas ? 'el idioma base y, si ya hay, sus hijas' : 'ninguna oferta declara su idioma todavía', ayuda: 'idioma_base' }),
    ui.metrica({ etiqueta: 'Listas de control con datos', valor: r.tablerosConEvidencia, contexto: r.tablerosConEvidencia ? 'idiomas con su lista de control calculada' : 'ninguna: el programa que calcula la lista de control todavía no existe', tono: r.tablerosConEvidencia ? undefined : 'aviso', ayuda: 'tablero_idioma' }),
    ui.metrica({ etiqueta: 'Idiomas listos para lanzar', valor: r.idiomasListos, contexto: r.idiomasListos ? 'todas sus tarjetas están en Listo' : 'un idioma se lanza cuando todas sus tarjetas pasan a Listo', tono: r.idiomasListos ? 'ok' : undefined }));
}

// ───────────────────────── mercado de cada oferta ─────────────────────────

const DECISION = { hipotesis: 'Hipótesis: aún sin ventas propias', validado: 'Validado con ventas propias', confirmado: 'Confirmado' };

function seccionMercados(filas) {
  let cuerpo;
  if (!filas.length) {
    cuerpo = ui.vacioConPasos({ titulo: 'Todavía no hay ofertas', explicacion: 'Cada oferta nace con su mercado e idioma elegidos en la etapa de mercado.', icono: 'globo', pasos: [{ texto: 'Crea una oferta con este comando: la etapa de mercado propone el mercado como hipótesis y tú lo apruebas.', comando: 'python -m engine.orq crear --brief ofertas/OF-AAAAMM-NN/00-brief.yaml' }] });
  } else {
    cuerpo = V.tablaPropia(
      [{ titulo: 'Oferta' }, { titulo: 'Idioma' }, { titulo: 'Países' }, { titulo: 'Moneda' }, { titulo: 'Decisión de mercado' }, { titulo: 'Lista de control del idioma' }],
      filas.map((f) => [
        el('div', { class: 'n2-pila n2-pila--chica' }, el('strong', null, f.id), f.demo ? V.etq('demo', { demo: true }) : null, f.fase ? el('span', { class: 'n2-tenue n2-peq' }, ui.infoEstado(f.fase).texto) : null),
        f.hayMercado ? (f.locale || '—') : el('span', { class: 'n2-tenue' }, 'sin mercado definido'),
        f.paises.length ? f.paises.join(', ') : null,
        f.moneda,
        f.hayMercado ? el('div', { class: 'n2-pila n2-pila--chica' }, el('span', null, f.decision ? (DECISION[f.decision] || f.decision.replace(/_/g, ' ')) : '—'), f.primerLanzamiento ? el('span', { class: 'n2-tenue n2-peq' }, 'primer lanzamiento en este idioma') : null) : null,
        f.tablero.hayArchivo ? el('span', null, `${f.tablero.listas} de ${f.tablero.total} listas`) : el('span', { class: 'n2-tenue' }, 'sin evidencia todavía'),
      ]), { etiqueta: 'Mercado e idioma de cada oferta' });
  }
  return ui.seccion('Mercado e idioma de cada oferta', cuerpo, { glosario: 'idioma_base', ayuda: 'Lo que cada oferta tiene decidido: en qué idioma se vende, a qué países y en qué moneda. El idioma base es el del primer testeo y lo eliges tú.' });
}

// ───────────────────────── ruta de familia ─────────────────────────

function cajaFamilia(f, rol) {
  const fase = f.fase ? ui.infoEstado(f.fase) : null;
  return el('div', { class: ['n2-familia__caja', rol === 'madre' && 'n2-familia__caja--madre'] },
    el('span', { class: 'n2-sobretitulo' }, rol === 'madre' ? 'Oferta original' : 'Versión en otro idioma'),
    el('strong', null, f.id), el('span', { class: 'n2-tenue' }, f.locale || 'idioma sin declarar'),
    el('div', { class: 'n2-fila' }, f.demo ? V.etq('demo', { demo: true }) : null, fase ? ui.chip(fase.texto, fase.tono) : null));
}

function seccionFamilia(filas) {
  const familias = P.agruparFamilias(filas);
  const cuerpo = el('div', { class: 'n2-pila' },
    el('p', { class: 'n2-parrafo' }, 'La ', ui.termino('ruta_familia', { texto: 'ruta de familia' }), ' lleva una idea ganadora a varios idiomas: una ', el('strong', null, 'oferta original'), ' en el idioma base y una ', el('strong', null, 'versión'), ' por cada idioma nuevo, cada una con sus cuentas, su revisión de idioma y su propia lista de control.'),
    V.nota(el('p', null, el('strong', null, 'Orden de las cosas: '), 'primero la ', ui.termino('madre_validada', { texto: 'oferta original tiene que estar validada' }), ' (y tú lo confirmas); solo entonces se crean las versiones en otros idiomas. Cada versión reusa el problema, el mecanismo y el producto, pero reescribe textos, promesas y precios; no hereda el dominio, el visto bueno de cumplimiento ni las cuentas.')),
    familias.length
      ? familias.map((fam) => el('div', { class: 'n2-pila n2-pila--chica' },
        el('h3', { class: 'n2-subtitulo' }, fam.familia ? `Familia ${fam.familia}` : `Oferta sin familia: ${fam.madre.id}`),
        el('div', { class: 'n2-familia' },
          cajaFamilia(fam.madre, 'madre'),
          fam.hijas.length ? fam.hijas.map((h) => [el('span', { class: 'n2-familia__flecha', 'aria-hidden': 'true' }, icono('flecha-derecha', { tam: 20 })), cajaFamilia(h, 'hija')]) : [
            el('span', { class: 'n2-familia__flecha', 'aria-hidden': 'true' }, icono('flecha-derecha', { tam: 20 })),
            el('div', { class: 'n2-familia__caja' }, el('span', { class: 'n2-sobretitulo' }, 'Versiones en otros idiomas'), el('strong', null, 'Ninguna todavía'), el('span', { class: 'n2-tenue' }, fam.puedeCrearHijas ? 'La original está validada: ya se pueden crear.' : 'La original todavía no está validada: no se puede crear ninguna.'))]),
        fam.hijas.length === 0 ? null : (fam.puedeCrearHijas ? null : V.nota(el('p', null, 'Hay versiones en otros idiomas, pero la original no figura como validada: revisa el orden.'), { tono: 'aviso' }))))
      : V.nota(el('p', null, 'Sin ofertas no hay familias.'), { tono: 'neutra' }));
  return ui.seccion('Del idioma base a todos los idiomas', cuerpo, { glosario: 'ruta_familia', ayuda: 'Una oferta original validada en su idioma base y sus versiones en los demás.' });
}

// ───────────────────────── tablero de lanzamiento ─────────────────────────

function tarjetaTablero(t) {
  const info = t.info;
  const evidencias = t.evidenciaReal;
  return el('article', { class: ['n2-tj', `n2-tj--${info.tono}`] },
    el('div', { class: 'n2-tj__cab' }, el('span', { class: 'n2-tj__id' }, t.id), t.origen === 'nueva' ? V.etq('añadida', { hipotesis: true, titulo: 'El método de Mentor no trae esta tarjeta: la agregamos por una obligación legal o de seguridad' }) : null, t.poscondicion ? V.etq('automática', { hipotesis: true, titulo: 'La marca el sistema cuando se activa la campaña' }) : null),
    el('h4', { class: 'n2-tj__titulo' }, t.titulo),
    V.estado({ tono: info.tono, icono: info.icono, texto: info.texto }, { tam: 14 }),
    t.estado === 'vencida' ? el('span', { class: 'n2-tenue n2-peq' }, `venció ${fmt.relativo(t.validoHasta)}`) : null,
    t.duenio && t.duenio.length ? el('div', { class: 'n2-tj__duenios', 'aria-label': 'Quién la resuelve' }, t.duenio.map((d) => V.etq(P.DUENIOS[d].texto, { titulo: P.DUENIOS[d].ayuda }))) : null,
    t.evidencia || evidencias.length
      ? el('details', null, el('summary', null, evidencias.length ? 'Evidencia y cómo se comprueba' : 'Cómo se comprueba'),
        evidencias.length ? el('ul', { class: 'n2-motivos' }, evidencias.map((e) => el('li', null, el('span', null, e.tipo || 'evidencia'), el('span', null, [e.ref, e.detalle].filter(Boolean).join(' · '))))) : null,
        t.evidencia ? el('p', null, el('strong', null, 'Qué se comprueba: '), t.evidencia) : null,
        t.gate ? el('p', null, el('strong', null, 'Quién interviene: '), t.gate) : null,
        t.tecnica ? ui.detalleTecnico('Detalle técnico', el('p', { class: 'n2-parrafo' }, t.tecnica)) : null)
      : null);
}

function seccionTablero(d, ofertas, alElegir) {
  const t = d ? d.tablero : P.modeloTablero(null);
  const sel = V.selectorOferta(ofertas, d ? d.oferta.id : null, alElegir);
  const sinArchivo = !t.hayArchivo;
  const cuerpo = el('div', { class: 'n2-pila' },
    el('div', { class: 'n2-semaforo' },
      el('div', { class: 'n2-pila n2-pila--chica' },
        el('span', { class: 'n2-sobretitulo' }, d ? `Idioma de ${d.oferta.id}${d.mercado && d.mercado.locale ? ` · ${d.mercado.locale}` : ''}` : 'Idioma'),
        el('span', { class: 'n2-semaforo__valor' }, `${t.requisitosListos} de ${t.requisitosTotal} listas`)),
      el('div', { style: { flex: '1 1 220px', minWidth: 0 } }, V.barra({ valor: t.requisitosListos, max: t.requisitosTotal, etiqueta: 'Tarjetas en Listo', texto: `${t.requisitosListos} de ${t.requisitosTotal}`, tono: t.listoParaLanzar ? 'ok' : null })),
      V.estado(t.listoParaLanzar ? { tono: 'ok', icono: 'ok', texto: 'Puede lanzarse' } : { tono: 'neutro', icono: 'candado', texto: 'No puede lanzarse todavía' })),
    el('p', { class: 'n2-lema' }, P.REGLA_SALIDA),
    el('p', { class: 'n2-tenue n2-peq', style: { margin: 0 } }, P.REGLA_SALIDA_DETALLE),
    sinArchivo
      ? V.nota(el('div', null, el('p', null, el('strong', null, t.estadoLectura === 'ilegible' || t.estadoLectura === 'truncado' ? 'No se pudo leer la lista de control de este idioma: ' : 'Todas las tarjetas salen «sin evidencia todavía». '),
        t.estadoLectura === 'ilegible' || t.estadoLectura === 'truncado' ? 'el archivo está cortado o dañado.' : 'El estado de cada tarjeta lo escribe un programa (ni tú ni una IA) y ese programa todavía no existe. La lista que ves es el modelo de lo que habrá que comprobar. El archivo y el comando están en el detalle técnico.')), { tono: 'neutra' })
      : null,
    t.incoherente ? V.nota(el('p', null, el('strong', null, 'Contradicción: '), 'el archivo dice «verde», pero hay tarjetas que no están en Listo. Vale lo que dicen las tarjetas.'), { tono: 'error' }) : null,
    el('div', { class: 'n2-tablero', role: 'list', 'aria-label': 'Lista de control para lanzar un idioma' }, t.columnas.map((c) => el('section', { class: 'n2-col', role: 'listitem', 'aria-label': c.nombre },
      el('header', { class: 'n2-col__cab' },
        el('h3', { class: 'n2-col__nombre' }, el('span', { class: 'n2-fila' }, icono(c.icono, { tam: 14 }), c.nombre), el('span', { class: 'n2-col__cuenta' }, `${c.listas}/${c.total}`)),
        el('p', { class: 'n2-col__que' }, c.que)),
      c.tarjetas.map(tarjetaTablero)))));
  return ui.seccion('Lista de control para lanzar un idioma', cuerpo, {
    glosario: 'tablero_idioma', acciones: sel,
    ayuda: 'La lista de control de un idioma nuevo: seis columnas y 25 tarjetas. Cada una dice quién la resuelve y qué la prueba. Aquí solo se mira: el panel no marca nada.',
  });
}

// ───────────────────────── obligaciones por país ─────────────────────────

const APLICA = { true: { texto: 'Sí', tono: 'aviso' }, false: { texto: 'No', tono: 'neutro' }, null: { texto: 'Depende', tono: 'neutro' } };

function seccionObligaciones(d) {
  const paises = d && d.mercado ? d.mercado.paises : [];
  const filas = P.filasObligaciones(paises, d ? d.mercado : null);
  const tabla = V.tablaPropia(
    [{ titulo: 'Obligación' }, { titulo: 'Qué exige' }, { titulo: paises.length ? `¿Aplica a ${paises.join(', ')}?` : '¿Aplica?' }, { titulo: 'Lo que declara la oferta' }, { titulo: 'Tarjeta' }],
    filas.map((f) => {
      const ap = APLICA[String(f.aplica)];
      return [
        el('strong', null, f.glosario ? ui.termino(f.glosario, { texto: f.nombre }) : f.nombre),
        f.exige,
        ui.chip(ap.texto, ap.tono, { icono: false }),
        f.declara ? V.estado({ tono: f.declara.tono, icono: { ok: 'ok', error: 'x-circulo', aviso: 'alerta', neutro: 'info' }[f.declara.tono] || 'info', texto: f.declara.texto }, { tam: 14 }) : el('span', { class: 'n2-tenue' }, 'No lo declara'),
        f.tarjeta ? V.etq(f.tarjeta, { mono: true }) : el('span', { class: 'n2-tenue' }, 'sin tarjeta'),
      ];
    }), { etiqueta: 'Obligaciones por país' });
  return ui.seccion('Lo que exige la ley en cada país (y el método de Mentor no trae)', el('div', { class: 'n2-pila' },
    V.nota(el('p', null, 'La lista de control del método no incluye ninguna de estas tarjetas: aquí se agregan porque cada país del grupo las exige. Se resuelven una vez por régimen y se reutilizan. Es un resumen de nuestra investigación interna, ', el('strong', null, 'no es asesoría legal ni fiscal'), ': el régimen fiscal se decide con el contador antes del segundo idioma de la UE.'), { tono: 'aviso' }),
    tabla,
    el('p', { class: 'n2-tenue n2-peq', style: { margin: 0 } }, 'La columna «Lo que declara la oferta» muestra lo que dice su ficha de mercado: declarar no es verificar; lo verifica la lista de control.')),
  { ayuda: 'Impuestos, desistimiento, consentimiento y reglas de idioma por país.' });
}

// ───────────────────────── detalle técnico ─────────────────────────

function seccionTecnica() {
  return V.tecnico('Detalle técnico: archivos y comandos',
    V.listaRutas(['ofertas/<id>/mercado.json — mercado e idioma de la oferta (lo escribe la etapa de mercado)', 'ofertas/<id>/lanzamiento_idioma.json — estado de cada tarjeta de la lista de control (lo escribirá scripts.lanzamiento_idioma; aún no existe)', 'empresa/familias/<familia_id>.json — índice de la familia: madre, hijas y ganadores (aún no existe)']),
    ui.comando('python -m engine.orq estado --oferta OF-AAAAMM-NN', { titulo: 'Ver en qué etapa está una oferta', abierto: false }),
    el('p', { class: 'n2-tenue n2-peq' }, 'El programa que calculará la lista de control se va a lanzar así (aún no existe): ', el('code', { class: 'n2-mono' }, 'python -m scripts.lanzamiento_idioma --oferta OF-AAAAMM-NN')),
    el('p', { class: 'n2-tenue n2-peq' }, 'Una tarjeta solo cuenta como Listo si su estado es «verificada» o «no_aplica_firmada» y su evidencia no ha vencido (valido_hasta). Los estados que acepta el archivo: pendiente, en_curso, verificada, no_aplica_firmada, bloqueada.'));
}
