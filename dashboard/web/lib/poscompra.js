// lib/poscompra.js — lógica pura de #/poscompra («Tienda y poscompra: lo que corre solo después de la venta»). Sin DOM, sin red; probada con node --test.
//
// Fuentes reales (todas por la API de solo lectura, GET /operacion/<id>): los KPI diarios de ofertas/<id>/08-operacion/diario/ (clics, vistas, inicios de pago,
// compras) y ofertas/<id>/10-postcompra/ (entregas.jsonl, reembolsos.jsonl, senal_pausa.json). Lo que no tiene fuente en el panel (carrito abandonado, oferta
// tras el pago, atención) sale «planeado» con su prioridad del mapeo (mapeo.md §7). NUNCA se muestra la cifra de ticket promedio del autor del método como si fuera
// nuestra: el ticket se mide con nuestras ventas; aquí solo se enseña el SUPUESTO de la economía de la oferta, rotulado como supuesto.

import { esObj, lista, texto, numero, entero, plano } from './n2-comun.js';

// ───────────────────────── embudo ─────────────────────────

/** `kpi`: id del KPI en kpi_oferta_dia.json. null = todavía no se mide con evento propio. */
export const ETAPAS_EMBUDO = Object.freeze([
  { id: 'clic', nombre: 'Clic en el anuncio', kpi: ['clics_enlace'], fuente: 'Meta', que: 'Alguien toca el anuncio.' },
  { id: 'pagina', nombre: 'Entra a la página', kpi: ['vistas_landing'], fuente: 'Meta y el contador propio de la página', que: 'La página de venta llega a cargarse.' },
  { id: 'comprar', nombre: 'Toca «comprar»', kpi: ['inicios_pago'], fuente: 'Contador propio de la página', que: 'Empieza el pago.' },
  { id: 'pago', nombre: 'Paga', kpi: ['compras_stripe', 'compras'], fuente: 'Stripe', que: 'El pago queda cobrado.' },
  { id: 'oferta', nombre: 'Ve la oferta extra después de pagar', kpi: null, fuente: 'Todavía no se mide', que: 'Se le muestra una oferta adicional después de pagar.', planeado: 'Se va a medir cuando exista la oferta extra (paso 4 del plan de la tienda).' },
  { id: 'entrega', nombre: 'Recibe el producto', kpi: null, fuente: 'Registro de entregas', que: 'El enlace de descarga le llega y funciona.' },
]);

/** Suma, a lo largo de los días de `kpiDia` (cada uno un kpi_oferta_dia.json), los KPI cuyo id esté en `ids`. → {valor, dias, fechas} | null */
export function sumarKpi(kpiDia, ids) {
  let total = 0; let dias = 0; const fechas = [];
  for (const d of lista(kpiDia)) {
    if (!esObj(d)) continue;
    for (const id of ids) { // el orden de `ids` es la preferencia (compras_stripe antes que compras)
      const f = lista(d.filas).find((x) => esObj(x) && x.kpi_id === id && x.estado !== 'stale');
      const v = f && f.valor !== null && f.valor !== undefined ? numero(f.valor) : null;
      if (v === null) continue;
      total += v; dias += 1; if (typeof d.fecha === 'string') fechas.push(d.fecha);
      break;
    }
  }
  return dias ? { valor: total, dias, fechas } : null;
}

const ESTADOS_ENTREGADA = new Set(['entregado', 'entregada', 'descargado', 'descargada', 'activado', 'activada']);
const ESTADOS_FALLIDA = new Set(['fallido', 'fallida', 'error', 'rebotado', 'rebotada']);

/** Recuento de entregas de entregas.jsonl: {total, entregadas, fallidas, sinteticas}. */
export function resumenEntregas(entregas) {
  const es = lista(entregas).filter(esObj);
  return {
    total: es.length,
    entregadas: es.filter((e) => ESTADOS_ENTREGADA.has(plano(e.estado))).length,
    fallidas: es.filter((e) => ESTADOS_FALLIDA.has(plano(e.estado))).length,
    sinteticas: es.filter((e) => e.sintetico === true).length,
  };
}

/**
 * Embudo con lo que haya. Cada etapa: {valor|null, estado:'dato'|'sin_dato'|'planeado', convPrevio (0..1)|null, muestraPequena, anomalia}.
 * La conversión solo se calcula entre etapas que SÍ tienen dato; una etapa mayor que la anterior (más de un 5 %) se marca como anomalía: revisar el rastreo.
 */
export function modeloEmbudo({ kpiDia = [], entregas = [] } = {}) {
  const ent = resumenEntregas(entregas);
  const etapas = ETAPAS_EMBUDO.map((e) => {
    let valor = null; let estado = 'sin_dato'; let dias = 0;
    if (e.id === 'entrega') {
      if (ent.total > 0) { valor = ent.entregadas; estado = 'dato'; dias = null; }
    } else if (e.kpi) {
      const s = sumarKpi(kpiDia, e.kpi);
      if (s) { valor = s.valor; estado = 'dato'; dias = s.dias; }
    } else estado = 'planeado';
    return { id: e.id, nombre: e.nombre, que: e.que, fuente: e.fuente, planeado: e.planeado || null, valor, estado, dias, convPrevio: null, muestraPequena: false, anomalia: false };
  });
  // La tasa se calcula solo contra la etapa MEDIDA inmediatamente anterior (la «planeada» no cuenta como paso): si el paso previo no tiene dato, no hay tasa.
  let previa = null;
  for (const e of etapas) {
    if (e.estado === 'planeado') continue;
    if (e.estado === 'dato' && previa && previa.estado === 'dato' && previa.valor > 0) {
      e.convPrevio = e.valor / previa.valor;
      e.muestraPequena = previa.valor < 30;
      e.anomalia = e.valor > previa.valor * 1.05;
      e.desde = previa.nombre;
    }
    previa = e;
  }
  return {
    etapas,
    conDato: etapas.filter((e) => e.estado === 'dato').length,
    hayDatos: etapas.some((e) => e.estado === 'dato'),
    dias: kpiDia ? lista(kpiDia).filter(esObj).length : 0,
    ultimoDia: lista(kpiDia).filter(esObj).map((d) => texto(d.fecha, 12)).filter(Boolean).sort().pop() || null,
    sintetico: lista(kpiDia).some((d) => esObj(d) && d.sintetico === true) || ent.sinteticas > 0,
    anomalias: etapas.filter((e) => e.anomalia).map((e) => e.nombre),
  };
}

// ───────────────────────── lo que corre solo ─────────────────────────

export const ESTADO_AUTOMATISMO = Object.freeze({
  planeado: { tono: 'neutro', icono: 'circulo-punteado', texto: 'Planeado' },
  disenada: { tono: 'aviso', icono: 'alerta', texto: 'Diseñada, sin probar en vivo' },
  prueba: { tono: 'info', icono: 'info', texto: 'Probada con datos de prueba' },
  en_marcha: { tono: 'ok', icono: 'ok', texto: 'En marcha' },
  con_fallos: { tono: 'error', icono: 'x-circulo', texto: 'Con entregas fallidas' },
  borrador: { tono: 'aviso', icono: 'lapiz', texto: 'Instrucciones en borrador' },
});

/** `paso`: lugar en el orden de construcción de la tienda (mapeo.md §7, por impacto en la rentabilidad). */
export const AUTOMATISMOS = Object.freeze([
  { id: 'entrega', nombre: 'Entrega inmediata', paso: 1, esfuerzo: 'Pequeño + mediano', que: 'Al pagar, el comprador recibe en minutos un enlace de descarga directo y firmado.',
    falta: 'Elegir el proveedor de correo de entrega y probar de punta a punta con un envío real. Bloquea la primera venta.', fuente: 'ofertas/<id>/10-postcompra/entregas.jsonl' },
  { id: 'atencion', nombre: 'Atención con tacto, en su idioma', paso: 1, esfuerzo: 'Mediano', que: 'Responde mails y mensajes con plantillas seguras; en salud, dinero y relaciones, solo plantillas fijas y sin consejo.',
    falta: 'Decidir dónde se reciben los mensajes de soporte y preparar las instrucciones de la IA de poscompra.', fuente: 'guía de trabajo d10-postcompra' },
  { id: 'oferta_pago', nombre: 'Oferta extra después de pagar', paso: 4, esfuerzo: 'Grande', que: 'Después de pagar se ofrece un producto adicional, con el precio visible, en la página de gracias.',
    falta: 'Construirla. La segunda oferta y el cobro con un clic quedan para más adelante, hasta medir las disputas.', fuente: 'sin lectura todavía' },
  { id: 'carrito', nombre: 'Carrito abandonado', paso: 5, esfuerzo: 'Mediano', que: 'Si alguien deja el correo en el checkout y no paga, recibe un mail de Impultienda con el link de pago y 33 % de descuento (una sola vez por carrito). Lo manda la tarea «repesca-carritos» cada hora (dueño, 15-nov).',
    falta: 'Nada: corre solo. Falta medir cuánto recupera (Carritos abandonados → «Facturación recuperada»).', fuente: 'ofertas/_funnels/repesca.json' },
]);

/**
 * Estado REAL de cada automatismo con lo que el panel puede leer. Sin lectura posible → «planeado».
 * @param {{entregas?:any[], skillD10?:{existe:boolean, estado?:string}|null}} datos
 */
export function estadoAutomatismos({ entregas = [], skillD10 = null } = {}) {
  const ent = resumenEntregas(entregas);
  const salida = {};
  if (!ent.total) salida.entrega = { clave: 'disenada', evidencia: 'Todavía no hay ninguna entrega registrada.' };
  else if (ent.sinteticas === ent.total) salida.entrega = { clave: 'prueba', evidencia: `${ent.total} ${ent.total === 1 ? 'entrega de prueba' : 'entregas de prueba'}; ninguna real.` };
  else if (ent.fallidas > 0) salida.entrega = { clave: 'con_fallos', evidencia: `${ent.entregadas} de ${ent.total} entregadas; ${ent.fallidas} ${ent.fallidas === 1 ? 'falló' : 'fallaron'}.` };
  else salida.entrega = { clave: 'en_marcha', evidencia: `${ent.entregadas} de ${ent.total} entregadas.` };
  if (skillD10 && skillD10.existe) salida.atencion = { clave: 'borrador', evidencia: 'Las instrucciones de la IA existen, pero aún no hay bandeja de entrada ni respuestas registradas.' };
  else salida.atencion = { clave: 'planeado', evidencia: skillD10 ? 'Las instrucciones de la IA de poscompra aún no existen.' : 'El panel no tiene lectura de la bandeja de soporte.' };
  salida.oferta_pago = { clave: 'planeado', evidencia: 'Sin lectura en el panel: la función aún no existe.' };
  salida.carrito = { clave: 'en_marcha', evidencia: 'Tarea «repesca-carritos» cada hora con 33 % (desde el 15-nov); registro en ofertas/_funnels/repesca.json.' };
  return salida;
}

// ───────────────────────── disputas y reembolsos ─────────────────────────

export const FLUJO_DISPUTA = Object.freeze({
  solo: ['Te avisa por dos canales en menos de una hora.', 'Arma el paquete de evidencia (sin datos personales) y un borrador de respuesta.', 'No reembolsa nunca una compra que ya tiene disputa abierta.'],
  tu: ['Revisar el paquete y el borrador.', 'Enviarlo desde Stripe con un clic, antes de la fecha límite.'],
  porque: 'Enviarlo por su cuenta exigiría una clave de escritura de Stripe, que hoy está negada a las IA.',
});

const pctDe = (v) => { const n = numero(v); return n === null ? null : n; };

/** Señal de pausa + reembolsos → lo que el panel muestra de disputas. */
export function modeloDisputas({ senal = null, reembolsos = [] } = {}) {
  const s = esObj(senal) ? senal : null;
  const m = s && esObj(s.metricas) ? s.metricas : {};
  const u = s && esObj(s.umbrales_usados) ? s.umbrales_usados : {};
  const reem = lista(reembolsos).filter(esObj);
  const porMoneda = {};
  for (const r of reem) {
    if (plano(r.estado) !== 'ejecutado' || !esObj(r.monto)) continue;
    const mon = texto(r.monto.moneda, 4); const monto = entero(r.monto.monto);
    if (mon && monto !== null) porMoneda[mon] = (porMoneda[mon] || 0) + monto;
  }
  const ratioPausa = numero(u.ratio_disputas_pausa);
  return {
    haySenal: Boolean(s),
    senal: s ? {
      nivel: texto(s.nivel, 12), emitida: s.emitida === true, motivo: texto(s.motivo, 80), accion: texto(s.accion_solicitada, 40), ts: texto(s.ts, 30), sintetico: s.sintetico === true,
      muestraSuficiente: m.muestra_suficiente === true, pagosVentana: entero(m.pagos_ventana), casos: entero(m.casos_disputa_efw), disputasPct: pctDe(m.disputas_efw_pct), reembolsosPct: pctDe(m.reembolsos_pct), ventanaDias: entero(m.ventana_dias),
    } : null,
    umbrales: s ? { disputasAlertaPct: pctDe(u.disputas_alerta_pct), disputasPausaPct: ratioPausa === null ? null : Math.round(ratioPausa * 10000) / 100, reembolsosAlertaPct: pctDe(u.reembolsos_alerta_pct), reembolsosPausaPct: pctDe(u.reembolsos_pausa_pct) } : null,
    reembolsos: { total: reem.length, ejecutados: reem.filter((r) => plano(r.estado) === 'ejecutado').length, porMoneda, sinteticos: reem.filter((r) => r.sintetico === true).length },
    comando: 'python -m postcompra.evidencia --session cs_… --oferta OF-AAAAMM-NN --salida <carpeta>',
  };
}

// ───────────────────────── ticket promedio ─────────────────────────

/** Supuesto de la economía de la oferta (economia.json, etapa D3). El ticket MEDIDO no existe hasta que haya ventas. */
export function modeloTicket(economia) {
  const e = esObj(economia) ? economia : null;
  const ent = e && esObj(e.entradas_usadas) ? e.entradas_usadas : {};
  const dinero = (x) => (esObj(x) && entero(x.monto) !== null && typeof x.moneda === 'string' ? { monto: x.monto, moneda: x.moneda } : null);
  const aov = e ? dinero(e.aov) : null;
  return {
    medido: null,
    haySupuesto: Boolean(aov),
    aov, precio: dinero(ent.precio), precioBump: dinero(ent.precio_bump), tasaBumpBp: entero(ent.tasa_bump_bp), origen: texto(ent.tarifas_origen, 30),
    version: e ? texto(e.version, 12) : null, veredicto: e ? texto(e.veredicto, 20) : null,
  };
}

/** Pasos del plan de tienda «como Impulstienda pero in-house» (mapeo.md §7), en orden de prioridad por impacto en la rentabilidad. */
export const PLAN_TIENDA = Object.freeze([
  { paso: 1, nombre: 'Entrega inmediata + correo de entrega + bandeja de soporte', esfuerzo: 'Decisión + mediano', nota: 'Bloquea la primera venta.' },
  { paso: 2, nombre: 'Saber de qué anuncio viene cada venta (etiqueta propia, en tiempo real) + eventos del camino del comprador', esfuerzo: 'Mediano', nota: 'Base de la medición hora por hora. Esta pantalla ya lee el camino del comprador con lo que existe.' },
  { paso: 3, nombre: 'Carrito con varios productos y botón «Añadir todo»', esfuerzo: 'Grande', nota: 'Es la palanca del ticket promedio: hasta 3 complementos del mismo tema.' },
  { paso: 4, nombre: 'Oferta extra después de pagar', esfuerzo: 'Grande', nota: 'Una sola oferta, con el precio visible; la segunda y el cobro con un clic quedan para más adelante.' },
  { paso: 5, nombre: 'Carrito abandonado', esfuerzo: 'Mediano', nota: 'Solo con permiso del comprador y en ofertas sin tema sensible.' },
  { paso: 6, nombre: 'Disputas con un clic', esfuerzo: 'Pequeño a mediano', nota: 'El sistema prepara el paquete; tú lo envías.' },
  { paso: 7, nombre: 'Panel en vivo: ganancia, anuncios, pagos', esfuerzo: 'Mediano', nota: 'Depende de la lectura horaria.' },
]);
