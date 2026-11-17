// pages/poscompra.js — #/poscompra: «Tienda y poscompra: lo que corre solo después de la venta».
// El embudo (clic → página → comprar → pago → oferta → entrega) con los eventos que existan, lo que corre solo después de pagar con su estado REAL (o «planeado»
// con su prioridad del plan de tienda), las disputas (el sistema prepara, el dueño envía) y el ticket promedio, que «se medirá»: su cifra declarada por el autor del
// método no se muestra como nuestra. Fuentes: GET /operacion/<id> (KPI diarios y ofertas/<id>/10-postcompra/) y 03-oferta/economia.json. SOLO LECTURA.
// La lógica vive en lib/poscompra.js (probada sin DOM).

import { ui, el, icono, fmt, reemplazar } from '../ui.js';
import * as C from '../lib/n2-comun.js';
import * as K from '../lib/poscompra.js';
import * as V from '../lib/n2-vista.js';

export const meta = { ruta: 'poscompra', titulo: 'Después de la venta', grupo: 'Fábrica y tienda', icono: 'bolsa', escucha: ['oferta'] };

let foco = null;
const TITULO = 'Después de la venta';
const DESCRIPCION = 'Lo que corre solo después de la venta: el camino del comprador desde el clic hasta recibir el producto, lo que ocurre solo después de pagar (entrega, correos, atención), cómo se responde a una disputa y cuánto gasta en promedio cada comprador.';

async function cargarTienda(ctx, oferta) {
  const [op, eco] = await Promise.all([C.leer(ctx.api, `/operacion/${encodeURIComponent(oferta.id)}`), C.leerJsonDeOferta(ctx.api, oferta.id, '03-oferta/economia.json')]);
  const d = op.ok && C.esObj(op.datos) ? op.datos : {};
  const pc = C.esObj(d.postcompra) ? d.postcompra : {};
  const kpiDia = C.lista(d.kpi_dia);
  const entregas = C.lista(pc.entregas);
  return {
    oferta, lecturaOperacion: op,
    embudo: K.modeloEmbudo({ kpiDia, entregas }),
    entregas: K.resumenEntregas(entregas),
    entregasLista: entregas,
    disputas: K.modeloDisputas({ senal: pc.senal_pausa, reembolsos: pc.reembolsos }),
    ticket: K.modeloTicket(eco.estado === 'ok' ? eco.dato : null),
    fuentes: [...C.unirFuentes(op, eco)],
  };
}

export async function render(ctx) {
  V.instalar();
  const { lec: lecOfertas, ofertas } = await C.cargarOfertas(ctx);
  if (!lecOfertas.ok && !ofertas.length) {
    return el('div', { class: 'pagina' }, V.cabecera({ titulo: TITULO, descripcion: 'No se pudo leer la lista de ofertas.' }), ui.errorBox(lecOfertas.error, { reintentar: () => ctx.recargar && ctx.recargar() }));
  }
  const [datos, lecSkills] = await Promise.all([Promise.all(ofertas.map((o) => cargarTienda(ctx, o))), C.leer(ctx.api, '/skills')]);
  const skillD10 = lecSkills.ok && Array.isArray(lecSkills.datos) ? { existe: lecSkills.datos.some((s) => C.esObj(s) && /^d10-/.test(String(s.slug))) } : null;
  foco = C.elegirFoco(ofertas, { previa: foco, activa: ctx.estado ? ctx.estado.ofertaActiva : null });
  const fuentes = ['ofertas/*/08-operacion/diario/*/kpi_oferta_dia.json', 'ofertas/*/10-postcompra/', ...datos.flatMap((d) => d.fuentes)];

  const host = el('div', { class: 'n2-pila' });
  const actual = () => datos.find((d) => d.oferta.id === foco) || datos[0] || null;
  const pintar = () => {
    const d = actual();
    reemplazar(host,
      ui.atencion({ items: avisos(d), vacio: 'Nada de la tienda ni de la poscompra requiere tu atención ahora.' }),
      metricas(d),
      seccionEmbudo(d, ofertas, (id) => { foco = id; pintar(); }),
      seccionAutomatismos(d, skillD10),
      seccionDisputas(d),
      seccionTicket(d),
      seccionTecnica(d));
  };
  pintar();

  return el('div', { class: 'pagina' },
    V.cabecera({ titulo: TITULO, descripcion: DESCRIPCION, fuentes: [...new Set(fuentes)], leido: lecOfertas.generado_en }),
    V.bannerDemo(ofertas),
    host);
}

function avisos(d) {
  const items = [];
  if (!d) return items;
  const id = d.oferta.id;
  if (d.embudo.anomalias.length) items.push({ tono: 'aviso', titulo: `El camino del comprador de ${id} no cuadra en: ${d.embudo.anomalias.join(', ')}`, detalle: 'Un paso con más gente que el anterior suele indicar que la medición falló; las cifras no son fiables hasta revisarla.' });
  if (d.entregas.fallidas) items.push({ tono: 'grave', titulo: `${d.entregas.fallidas} ${d.entregas.fallidas === 1 ? 'entrega falló' : 'entregas fallaron'} en ${id}`, detalle: 'Un comprador pagó y no recibió el producto: revisa el registro de entregas.', accion: { texto: 'Ver la oferta', ruta: `/oferta/${id}` } });
  const s = d.disputas.senal;
  if (s && s.nivel && s.nivel !== 'verde') items.push({ tono: s.nivel === 'rojo' ? 'critico' : 'aviso', titulo: `La señal de pausa de ${id} está en ${s.nivel}`, detalle: s.motivo ? `Motivo: ${s.motivo}.` : 'Revisa las disputas y los reembolsos.', accion: { texto: 'Ver la oferta', ruta: `/oferta/${id}` } });
  return items;
}

function metricas(d) {
  const e = d ? d.embudo.etapas : [];
  const pago = e.find((x) => x.id === 'pago');
  const ent = d ? d.entregas : { total: 0, entregadas: 0 };
  const dis = d ? d.disputas : null;
  const suf = dis && dis.senal && dis.senal.muestraSuficiente;
  const sint = d && d.embudo.sintetico;
  return el('div', { class: 'n2-metricas' },
    ui.metrica({ etiqueta: 'Compras', valor: pago && pago.estado === 'dato' ? pago.valor : null, contexto: pago && pago.estado === 'dato' ? `en ${pago.dias} ${pago.dias === 1 ? 'día medido' : 'días medidos'}${sint ? ' · datos de prueba' : ''}` : 'sin compras medidas todavía', ayuda: 'embudo_tienda' }),
    ui.metrica({ etiqueta: 'Entregas', valor: ent.total ? `${ent.entregadas} de ${ent.total}` : null, contexto: ent.total ? (ent.sinteticas === ent.total ? 'entregas de prueba' : 'compradores con el producto en su poder') : 'ninguna entrega registrada', tono: ent.fallidas ? 'grave' : undefined }),
    ui.metrica({ etiqueta: 'Reembolsos ejecutados', valor: dis && dis.reembolsos.total ? dis.reembolsos.ejecutados : null, contexto: dis && dis.reembolsos.total ? `de ${dis.reembolsos.total} registrados${dis.reembolsos.sinteticos === dis.reembolsos.total ? ' · de prueba' : ''}` : 'ninguno registrado' }),
    ui.metrica({ etiqueta: 'Disputas', valor: dis && dis.senal && dis.senal.casos !== null ? dis.senal.casos : null, contexto: dis && dis.senal ? (suf ? `sobre ${dis.senal.pagosVentana} pagos` : 'muestra todavía insuficiente para sacar conclusiones') : 'la señal de pausa aún no se calculó', tono: dis && dis.senal && dis.senal.nivel && dis.senal.nivel !== 'verde' ? 'aviso' : undefined, ayuda: 'disputa_un_clic' }));
}

// ───────────────────────── embudo ─────────────────────────

const pct = (x) => `${fmt.numero(x * 100, { decimales: x * 100 < 10 ? 1 : 0 })} %`;

function etapaEmbudo(e, maximo) {
  const sin = e.estado === 'sin_dato';
  const plan = e.estado === 'planeado';
  const p = e.estado === 'dato' && maximo > 0 ? Math.max(2, Math.min(100, (e.valor / maximo) * 100)) : 0;
  return el('li', { class: ['n2-etapa', sin && 'n2-etapa--sin', plan && 'n2-etapa--plan'] },
    el('div', { class: 'n2-etapa__nombre' }, el('strong', null, e.nombre), el('span', { class: 'n2-tenue n2-peq' }, e.que)),
    el('div', { class: 'n2-etapa__pista', role: 'img', 'aria-label': e.estado === 'dato' ? `${e.nombre}: ${fmt.numero(e.valor)}` : `${e.nombre}: ${plan ? 'planeado' : 'sin dato'}` }, el('i', { class: 'n2-etapa__relleno', style: { '--p': `${p.toFixed(1)}%` } })),
    el('div', { class: 'n2-etapa__valor' },
      e.estado === 'dato' ? [fmt.numero(e.valor), e.convPrevio !== null ? el('span', { class: 'n2-etapa__conv', title: `Sobre «${e.desde}»` }, `${pct(e.convPrevio)} del paso anterior${e.muestraPequena ? ' · no concluyente' : ''}`) : null, e.anomalia ? V.estado({ tono: 'aviso', icono: 'alerta', texto: 'No cuadra' }, { tam: 13 }) : null]
        : [plan ? V.estado({ tono: 'neutro', icono: 'circulo-punteado', texto: 'Planeado' }, { tam: 13 }) : el('span', { class: 'n2-tenue' }, '—'), el('span', { class: 'n2-etapa__conv' }, plan ? e.planeado : `Lo mediría: ${e.fuente}`)]));
}

function seccionEmbudo(d, ofertas, alElegir) {
  const sel = V.selectorOferta(ofertas, d ? d.oferta.id : null, alElegir);
  let cuerpo;
  if (!d) {
    cuerpo = ui.vacioConPasos({ titulo: 'Todavía no hay ofertas', explicacion: 'El camino del comprador se mide por oferta, a partir de su primera campaña.', icono: 'pulso', pasos: [] });
  } else {
    const em = d.embudo;
    const maximo = Math.max(0, ...em.etapas.filter((x) => x.estado === 'dato').map((x) => x.valor));
    cuerpo = el('div', { class: 'n2-pila' },
      d.lecturaOperacion.ok ? null : V.avisoLectura('No se pudo leer la operación de esta oferta.', d.lecturaOperacion.error),
      em.sintetico ? V.nota(el('p', null, el('strong', null, 'Datos de prueba. '), 'Las cifras vienen de archivos marcados como de prueba: sirven para ver la pantalla con datos, no para decidir.'), { tono: 'aviso' }) : null,
      em.hayDatos
        ? el('ol', { class: 'n2-embudo', 'aria-label': 'Camino del comprador' }, em.etapas.map((e) => etapaEmbudo(e, maximo)))
        : ui.vacioConPasos({
          titulo: 'Todavía no se mide ningún paso del camino del comprador',
          explicacion: 'Hace falta que la oferta tenga una campaña corriendo y que el cierre del día deje sus indicadores.',
          icono: 'pulso',
          pasos: [
            { texto: 'Cuando se activa la campaña, cada clic, cada visita y cada pago empiezan a contarse.' },
            { texto: 'El cierre diario deja las cifras del día y el registro de entregas de la oferta. Esta pantalla los lee sola; los archivos exactos, en el detalle técnico.' },
            { texto: 'Ver en qué etapa está la oferta:', comando: `python -m engine.orq estado --oferta ${d.oferta.interno || 'OF-AAAAMM-NN'}` },
          ],
        }),
      em.hayDatos ? el('p', { class: 'n2-tenue n2-peq', style: { margin: 0 } }, `Suma de ${em.dias} ${em.dias === 1 ? 'día' : 'días'} de indicadores${em.ultimoDia ? ` (el último, ${fmt.fecha(em.ultimoDia)})` : ''}. La tasa entre pasos solo se calcula cuando ambos tienen dato, y con menos de 30 personas en el paso anterior no es concluyente.` ) : null,
      em.anomalias.length ? V.nota(el('p', null, 'Un paso con más gente que el anterior no es una buena noticia: indica que la medición falló. Revisa el contador de la página antes de fiarte de estas cifras.'), { tono: 'aviso' }) : null);
  }
  return ui.seccion('El camino del comprador', cuerpo, { glosario: 'embudo_tienda', acciones: sel, ayuda: 'De cuánta gente que toca el anuncio llega a pagar y a recibir el producto. Cada paso con su origen; el que aún no se mide queda como «planeado».' });
}

// ───────────────────────── lo que corre solo ─────────────────────────

function seccionAutomatismos(d, skillD10) {
  const est = K.estadoAutomatismos({ entregas: d ? d.entregasLista : [], skillD10 });
  const lista = el('ul', { class: 'n2-auto', 'aria-label': 'Lo que corre solo después de la venta' }, K.AUTOMATISMOS.map((a) => {
    const e = est[a.id];
    const info = K.ESTADO_AUTOMATISMO[e.clave];
    const claves = { carrito: 'carrito_abandonado', oferta_pago: 'oferta_tras_pago' };
    return el('li', null,
      el('div', { class: 'n2-auto__cab' },
        el('h3', { class: 'n2-auto__nombre' }, claves[a.id] ? ui.termino(claves[a.id], { texto: a.nombre }) : a.nombre),
        el('div', { class: 'n2-fila' }, V.estado(info, { tam: 16 }), V.etq(`Paso ${a.paso} de 7`, { titulo: 'Orden de construcción del plan de tienda (por impacto en la rentabilidad)' }), V.etq(`Esfuerzo: ${a.esfuerzo.toLowerCase()}`))),
      el('p', null, a.que),
      el('p', null, el('strong', null, 'Lo que se ve: '), e.evidencia),
      e.clave === 'en_marcha' ? null : el('p', null, el('strong', null, 'Qué falta: '), a.falta));
  }));
  return ui.seccion('Lo que corre solo después de la venta', el('div', { class: 'n2-pila' },
    V.nota(el('p', null, 'Cada línea dice su estado real. Lo que el panel no puede leer (porque la función todavía no existe) figura como «planeado», con su lugar en el orden de construcción.'), { tono: 'neutra' }),
    lista),
  { ayuda: 'Entrega inmediata, atención, oferta tras el pago y carrito abandonado.' });
}

// ───────────────────────── disputas ─────────────────────────

function seccionDisputas(d) {
  const dis = d ? d.disputas : null;
  const s = dis ? dis.senal : null;
  const u = dis ? dis.umbrales : null;
  const f = K.FLUJO_DISPUTA;
  const tono = s ? { verde: 'ok', amarillo: 'aviso', rojo: 'critico' }[s.nivel] || 'neutro' : 'neutro';
  const cuerpo = el('div', { class: 'n2-pila' },
    el('div', { class: 'n2-dos' },
      el('div', { class: 'n2-caja' }, el('h3', null, 'Lo que hace el sistema solo'), el('ul', null, f.solo.map((x) => el('li', null, x)))),
      el('div', { class: 'n2-caja' }, el('h3', null, 'Lo que haces tú, con un clic'), el('ul', null, f.tu.map((x) => el('li', null, x))), el('p', { class: 'n2-tenue n2-peq', style: { margin: 0 } }, f.porque))),
    s
      ? el('div', { class: 'n2-pila n2-pila--chica' },
        el('div', { class: 'n2-fila' }, el('h3', { class: 'n2-subtitulo' }, 'Cómo va la señal de pausa'), ui.chip(s.nivel ? ui.infoEstado(s.nivel).texto : 'sin nivel', tono), s.sintetico ? V.etq('datos de prueba', { demo: true }) : null),
        ui.kv([
          ['Pagos en el período', s.pagosVentana !== null ? `${fmt.num(s.pagosVentana)} (${s.ventanaDias ?? '—'} días)` : null],
          ['Disputas', s.casos !== null ? `${fmt.num(s.casos)}${s.disputasPct !== null ? ` · ${fmt.numero(s.disputasPct, { decimales: 1 })} %` : ''}` : null],
          ['Reembolsos', s.reembolsosPct !== null ? `${fmt.numero(s.reembolsosPct, { decimales: 1 })} %` : null],
          ['Cantidad de datos', s.muestraSuficiente ? 'suficiente' : 'todavía insuficiente: no se saca ninguna conclusión'],
          ['Se avisa a partir de', u && u.disputasAlertaPct !== null ? `${fmt.numero(u.disputasAlertaPct, { decimales: 1 })} % de disputas · ${u.reembolsosAlertaPct !== null ? `${fmt.numero(u.reembolsosAlertaPct, { decimales: 0 })} % de reembolsos` : '—'}` : null],
          ['Se pausa a partir de', u && u.disputasPausaPct !== null ? `${fmt.numero(u.disputasPausaPct, { decimales: 1 })} % de disputas · ${u.reembolsosPausaPct !== null ? `${fmt.numero(u.reembolsosPausaPct, { decimales: 0 })} % de reembolsos` : '—'}` : null],
        ]))
      : ui.vacioConPasos({ titulo: 'Todavía no hay señal de pausa', explicacion: 'Se calcula cuando haya pagos: compara las disputas y los reembolsos con los límites de aviso y de pausa.', icono: 'escudo', compacto: true, pasos: [{ texto: 'La produce el cierre diario de poscompra y la deja en un archivo de la oferta (la ruta está en el detalle técnico).' }] }),
    dis && dis.reembolsos.total
      ? el('p', { class: 'n2-tenue n2-peq', style: { margin: 0 } }, `Reembolsos registrados: ${dis.reembolsos.total} (${dis.reembolsos.ejecutados} ejecutados${Object.keys(dis.reembolsos.porMoneda).length ? `, por ${Object.entries(dis.reembolsos.porMoneda).map(([m, v]) => fmt.dinero(v, m)).join(' y ')}` : ''}).`)
      : null,
    ui.comando(dis ? dis.comando : K.modeloDisputas().comando, { titulo: 'Preparar el paquete de evidencia de una disputa', nota: 'Solo lee Stripe y arma el paquete (sin datos personales). Enviarlo a Stripe lo haces tú desde su panel, antes de la fecha límite.', abierto: false }));
  return ui.seccion('Disputas: el sistema prepara, tú envías', cuerpo, { glosario: 'disputa_un_clic', ayuda: 'Una disputa es un comprador que reclama el cobro a su banco. Responder a tiempo y con evidencia es lo que la gana.' });
}

// ───────────────────────── ticket promedio ─────────────────────────

function seccionTicket(d) {
  const t = d ? d.ticket : K.modeloTicket(null);
  const dinero = (x) => (x ? fmt.dinero(x.monto, x.moneda) : null);
  const cuerpo = el('div', { class: 'n2-pila' },
    el('div', { class: 'n2-ticket' },
      ui.metrica({ etiqueta: 'Ticket promedio medido', valor: null, contexto: 'Se medirá con nuestras ventas: cobrado total (menos reembolsos) dividido por compras.', ayuda: 'ticket_promedio' }),
      ui.metrica({ etiqueta: 'Supuesto de las cuentas de la oferta', valor: t.haySupuesto ? dinero(t.aov) : null,
        contexto: t.haySupuesto ? `Supuesto, no medido${t.precio ? ` · precio ${dinero(t.precio)}` : ''}${t.precioBump && t.tasaBumpBp !== null ? ` + ${fmt.pct(t.tasaBumpBp)} de aceptación de un extra de ${dinero(t.precioBump)}` : ''}` : 'La oferta no tiene las cuentas hechas (etapa de oferta) o no se pudieron leer.', tono: t.haySupuesto ? 'info' : undefined })),
    V.nota(el('p', null, el('strong', null, 'No se usa la cifra del autor del método. '), 'Su ticket declarado (un carrito completo y poscompra) no se ha verificado ni corresponde a nuestro catálogo. La palanca para subir el ticket es el carrito con varios productos y «Añadir todo», que aún no existe (paso 3 del plan).'), { tono: 'neutra' }));
  return ui.seccion('Ticket promedio', cuerpo, { glosario: 'ticket_promedio', ayuda: 'Cuánto gasta en promedio cada comprador. Hoy solo hay un supuesto de la economía de la oferta; el número real llegará con las ventas.' });
}

// ───────────────────────── detalle técnico ─────────────────────────

function seccionTecnica(d) {
  const id = d ? d.oferta.id : '<id>';
  return V.tecnico('Detalle técnico: archivos, comandos y plan de tienda',
    V.listaRutas([`ofertas/${id}/08-operacion/diario/<fecha>/kpi_oferta_dia.json — clics, visitas, inicios de pago y compras`, `ofertas/${id}/10-postcompra/entregas.jsonl — una línea por entrega`, `ofertas/${id}/10-postcompra/reembolsos.jsonl`, `ofertas/${id}/10-postcompra/senal_pausa.json`, `ofertas/${id}/03-oferta/economia.json — ticket supuesto`]),
    el('h4', { class: 'n2-subtitulo' }, 'Orden de construcción de la tienda «como Impulstienda, pero propia»'),
    V.tablaPropia([{ titulo: 'Paso', clase: 'n2-col-estrecha' }, { titulo: 'Qué' }, { titulo: 'Esfuerzo' }, { titulo: 'Nota' }], K.PLAN_TIENDA.map((p) => [String(p.paso), p.nombre, p.esfuerzo, p.nota]), { etiqueta: 'Plan de tienda', compacta: true }));
}
