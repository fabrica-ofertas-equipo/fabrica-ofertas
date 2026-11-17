// lib/pagos.js — lógica pura (datos → modelo de vista) de #/pagos: «que ninguna cuenta se frene por un pago». Usa lo que ya hay: los ítems de Meta y Stripe del
// preflight (GET /sistema → infra.items) y el libro, la conciliación Stripe ↔ libro ↔ Meta (GET /finanzas). Sin DOM: probable con `node --test`.
// REGLA: nunca se inventa una cifra. El panel NO tiene el saldo de la cuenta de Meta como número (el preflight solo guarda verde/amarillo/rojo y un texto breve):
// se dice así y se explica qué lo producirá (el vigía de pagos). Las mediciones simuladas o vencidas no se presentan como reales.
import { fmt } from '../ui.js';
import { estadoInfra, COMANDO_PREFLIGHT } from './resumen.js';
import { agruparPreflight } from './sistema.js';
import { modeloFinanzas, ESTADO_CONCILIACION, comandosFinanzas } from './finanzas.js';

export { COMANDO_PREFLIGHT };

// ───────────────────────── qué pregunta responde cada ítem ─────────────────────────

/**
 * Las comprobaciones de Meta y Stripe que miran dinero y cobros, en lenguaje de negocio (infra/plantillas/preflight-items.yaml). `pago: true` = si falla,
 * algo deja de cobrar o de gastar. El orden es el de lectura: primero lo que frena un pago.
 */
export const PREGUNTAS = [
  { id: 'M-02', cuenta: 'meta', pago: true, pregunta: '¿La cuenta publicitaria está activa y sin bloqueo?', explica: 'Mira el estado de la cuenta y, si está deshabilitada, el motivo; también que sea una cuenta permitida y que su moneda y su zona horaria sean las esperadas.' },
  { id: 'M-03', cuenta: 'meta', pago: true, saldo: true, pregunta: '¿Queda tope de gasto y la forma de pago es la permitida?', explica: 'Compara el tope de la cuenta con lo ya gastado: avisa cuando lo que queda baja del límite de aviso y se pone en rojo si no hay tope, si el tope no está fijado en los límites o si la cuenta usa fondos prepagos.' },
  { id: 'M-01', cuenta: 'meta', pago: false, pregunta: '¿El acceso del sistema a Meta sigue vigente?', explica: 'Comprueba que el permiso funcione, que no tenga permisos de más y que no esté por vencer.' },
  { id: 'S-02', cuenta: 'stripe', pago: true, pregunta: '¿Stripe puede cobrar a tus clientes y pagarte a ti?', explica: 'Comprueba que los cobros y las transferencias a tu banco estén habilitados y que no haya requisitos de verificación pendientes o vencidos.' },
  { id: 'S-07', cuenta: 'stripe', pago: true, pregunta: '¿Las disputas están bajo control?', explica: 'Disputas y alertas de fraude sobre pagos en 30 días, frente a los límites de aviso y de pausa. Si se pasa el de pausa, una oferta debería detenerse.' },
  { id: 'S-01', cuenta: 'stripe', pago: false, pregunta: '¿La llave de lectura de Stripe funciona?', explica: 'Sin ella el sistema no puede ver los pagos ni conciliar.' },
  { id: 'S-03', cuenta: 'stripe', pago: false, pregunta: '¿Stripe le avisa al sistema de cada venta?', explica: 'Verifica que Stripe tenga configurados los avisos automáticos hacia el sistema y que envíen exactamente los eventos esperados.' },
  { id: 'S-04', cuenta: 'stripe', pago: false, pregunta: '¿Llegaron todas las ventas de las últimas 24 horas?', explica: 'Compara los eventos recibidos con los de Stripe y avisa de huecos.' },
  { id: 'S-05', cuenta: 'stripe', pago: false, pregunta: '¿Los precios de Stripe coinciden con los de cada oferta?', explica: 'Contrasta precio, moneda y clave de cada producto activo con lo definido en la pantalla de pago.' },
  { id: 'S-06', cuenta: 'stripe', pago: false, pregunta: '¿Las claves son del modo correcto?', explica: 'Las claves en vivo solo en producción y las de prueba solo en pruebas; una mezcla es roja.' },
  { id: 'S-08', cuenta: 'stripe', pago: false, pregunta: '¿Stripe muestra bien tu negocio al cliente?', explica: 'El nombre que aparece en el cargo de la tarjeta, la política de reembolso y el contacto están configurados.' },
];

export const CUENTAS = [
  { id: 'meta', bloque: 'meta', nombre: 'Cuenta publicitaria de Meta', glosario: 'cuenta_publicitaria', icono: 'megafono', frena: 'Si esta cuenta se bloquea, llega a su tope o su pago falla, los anuncios dejan de gastar aunque todo lo demás esté bien.' },
  { id: 'stripe', bloque: 'stripe', nombre: 'Cobros con Stripe', glosario: 'cobros_stripe', icono: 'cartera', frena: 'Si Stripe no puede cobrar o pagarte, se pierden ventas o el dinero queda retenido.' },
];

const TONO_PRIORIDAD = { error: 3, aviso: 2, neutro: 1, ok: 0 };

function tonoDeItem(it) {
  if (!it) return 'neutro';
  if (it.vencido && it.tono === 'ok') return 'aviso';
  return it.tono === 'info' ? 'neutro' : it.tono;
}

function etiquetaDeItem(it) {
  if (!it) return 'Sin medir';
  if (it.vencido && it.tono === 'ok') return 'Vencido';
  return it.etiqueta;
}

/** Fila de una pregunta con su ítem del preflight (o «sin medir»). */
function filaPregunta(p, item) {
  return {
    id: p.id, pregunta: p.pregunta, explica: p.explica, pago: p.pago, saldo: Boolean(p.saldo),
    medido: Boolean(item), estado: item ? item.estado : null, tono: tonoDeItem(item), etiqueta: etiquetaDeItem(item),
    mensaje: item && item.mensaje ? item.mensaje : null, medidoEn: item ? item.medidoEn : null, expiraEn: item ? item.expiraEn : null, vencido: Boolean(item && item.vencido),
    critico: Boolean(item && item.critico), evidencia: item ? item.evidencia : null,
  };
}

/** Veredicto de una cuenta: el peor tono de lo medido; «sin medir» si no hay nada; «medido en parte» si faltan ítems que frenan pagos. */
export function veredictoCuenta(preguntas) {
  const medidas = preguntas.filter((p) => p.medido);
  if (!medidas.length) return { clave: 'sin_medir', tono: 'neutro', etiqueta: 'Sin medir', frase: 'Todavía no se midió esta cuenta.' };
  const peor = medidas.reduce((a, b) => (TONO_PRIORIDAD[b.tono] > TONO_PRIORIDAD[a.tono] ? b : a));
  const faltanPago = preguntas.filter((p) => p.pago && !p.medido);
  if (peor.tono === 'error') return { clave: 'rojo', tono: 'error', etiqueta: 'Rojo', frase: `Algo está mal: ${peor.pregunta}` };
  if (peor.tono === 'aviso') return { clave: 'amarillo', tono: 'aviso', etiqueta: peor.etiqueta === 'Vencido' ? 'Vencido' : 'Amarillo', frase: peor.etiqueta === 'Vencido' ? 'La medición caducó: hay que repetirla.' : `Conviene mirarlo: ${peor.pregunta}` };
  if (faltanPago.length) return { clave: 'parcial', tono: 'neutro', etiqueta: 'Medido en parte', frase: `Falta medir: ${faltanPago.map((p) => p.pregunta.replace(/^¿|\?$/g, '')).join(' · ')}.` };
  if (peor.tono === 'neutro') return { clave: 'pendiente', tono: 'neutro', etiqueta: 'Pendiente', frase: 'Alguna comprobación está pendiente.' };
  return { clave: 'verde', tono: 'ok', etiqueta: 'Verde', frase: 'Todas las comprobaciones salieron bien.' };
}

// ───────────────────────── modelo de la pantalla ─────────────────────────

/**
 * → { infra (estadoInfra), hayInfra, modo, real, cuentas:[{…, preguntas, veredicto, extras}], saldo, finanzas (modeloFinanzas), conciliacion, cobrado }
 *  · `real`: la medición es del modo «vivo» y está vigente. Si no, se avisa y no se presenta como lectura de las cuentas reales.
 *  · `saldo.disponible` es siempre false hoy: el panel no recibe el número; `saldo.veredicto` es lo único que hay (M-03).
 */
export function modeloPagos({ sistema, finanzas, ahoraMs = Date.now() } = {}) {
  const infraCruda = sistema && sistema.infra ? sistema.infra : null;
  const infra = estadoInfra(infraCruda, ahoraMs);
  const agr = agruparPreflight(infraCruda, ahoraMs);
  const porId = {};
  for (const b of agr.bloques) for (const it of b.items) porId[it.id] = { ...it, bloque: b.id };
  const cuentas = CUENTAS.map((c) => {
    const preguntas = PREGUNTAS.filter((p) => p.cuenta === c.id).map((p) => filaPregunta(p, porId[p.id]));
    const conocidos = new Set(PREGUNTAS.map((p) => p.id));
    const extras = (agr.bloques.find((b) => b.id === c.bloque) || { items: [] }).items.filter((it) => !conocidos.has(it.id)).map((it) => filaPregunta({ id: it.id, cuenta: c.id, pago: false, pregunta: `Comprobación ${it.id}`, explica: 'Comprobación del chequeo antes de lanzar que el panel todavía no describe.' }, it));
    const veredicto = veredictoCuenta([...preguntas, ...extras]);
    if (veredicto.clave === 'sin_medir' && infraCruda) veredicto.frase = 'El último chequeo antes de lanzar no trae el detalle de esta cuenta.';
    return { ...c, preguntas, extras, veredicto };
  });
  const m03 = cuentas[0].preguntas.find((p) => p.id === 'M-03');
  const fin = finanzas ? modeloFinanzas(finanzas, null) : null;
  // «real»: medición del modo vivo y vigente (el color del semáforo es otra cosa: una medición real puede salir amarilla)
  const real = Boolean(infraCruda) && infraCruda.modo === 'vivo' && infra.edadH !== null && infra.edadH <= 6;
  return {
    infra, hayInfra: Boolean(infraCruda), hayItems: agr.hay, generadoEn: infraCruda && infraCruda.generado_en ? infraCruda.generado_en : null, modo: infraCruda ? (infraCruda.modo || null) : null,
    simulada: Boolean(infraCruda) && infraCruda.modo !== 'vivo', real,
    cuentas,
    saldo: { disponible: false, veredicto: m03 && m03.medido ? m03 : null, mensaje: m03 && m03.mensaje ? m03.mensaje : null },
    finanzas: fin, conciliacion: fin ? fin.conciliacion : null, cobrado: fin ? resumenCobros(fin) : [],
    // ¿hay libro, P&L o conciliación? (las alertas solas no cuentan: esas se ven en Avisos)
    hayLibro: Boolean(fin && (fin.ledger.vigentes.length > 0 || fin.pnl || fin.conciliacion)),
  };
}

/** Por moneda, del libro (sin pruebas): cobrado en ventas, gastado en anuncios, reembolsos y disputas. Un tipo sin movimientos queda null («—»), no 0. */
export function resumenCobros(fin) {
  const monedas = fin && fin.totales && Array.isArray(fin.totales.monedas) ? fin.totales.monedas : [];
  const abs = (v) => (Number.isSafeInteger(v) ? Math.abs(v) : null);
  return monedas.map((t) => ({
    moneda: t.moneda, lineas: t.lineas,
    cobrado: abs(t.porTipo.pedido ?? null), gastado: abs(t.porTipo.gasto ?? null), reembolsos: abs(t.porTipo.reembolso ?? null), disputas: abs(t.porTipo.disputa ?? null),
  }));
}

// ───────────────────────── atención y métricas ─────────────────────────

const PREGUNTA_POR_ID = Object.fromEntries(PREGUNTAS.map((p) => [p.id, p]));

/** Lo que pide atención, de más a menos grave. Los ítems que frenan un pago pesan más que el resto. */
export function atencionPagos(modelo) {
  const items = [];
  if (!modelo.hayInfra) {
    items.push({ tono: 'aviso', titulo: 'Falta medir las cuentas de Meta y Stripe', detalle: 'Sin el chequeo antes de lanzar (la revisión de la infraestructura) nadie sabe si las cuentas pueden gastar o cobrar, y mientras no esté en verde nadie gasta ni activa.', accion: { texto: 'Cómo medirlas', ruta: '#/sistema' } });
  } else {
    if (modelo.simulada) items.push({ tono: 'aviso', titulo: 'La última medición no es de las cuentas reales', detalle: `Se hizo en modo ${modelo.modo || 'desconocido'}: no mira Meta ni Stripe de verdad, así que ninguna fila de abajo prueba que una cuenta esté al día.` });
    if (modelo.infra.edadH !== null && /vencido/.test(modelo.infra.detalle)) items.push({ tono: 'aviso', titulo: 'La medición de las cuentas ya caducó', detalle: modelo.infra.detalle });
    for (const c of modelo.cuentas) {
      for (const p of [...c.preguntas, ...c.extras]) {
        if (!p.medido) continue;
        if (p.tono === 'error') items.push({ tono: p.pago ? 'critico' : 'grave', titulo: `${c.nombre}: ${p.pregunta.replace(/^¿|\?$/g, '')} → en rojo`, detalle: p.mensaje || undefined, accion: { texto: 'Ver el chequeo', ruta: '#/sistema' } });
        else if (p.tono === 'aviso' && !p.vencido) items.push({ tono: 'aviso', titulo: `${c.nombre}: ${p.pregunta.replace(/^¿|\?$/g, '')} → en amarillo`, detalle: p.mensaje || undefined });
      }
    }
  }
  const c = modelo.conciliacion;
  if (modelo.hayLibro) {
    if (c && c.estado === 'DESCUADRE') items.push({ tono: 'critico', titulo: 'Stripe o Meta no cuadran con el libro de movimientos', detalle: [c.tachadas.stripe, c.tachadas.meta].filter(Boolean).join(' · ') || ESTADO_CONCILIACION.DESCUADRE.frase, accion: { texto: 'Abrir Finanzas', ruta: '#/finanzas' } });
    else if (c && c.estado === 'INCOMPLETO') items.push({ tono: 'aviso', titulo: 'La conciliación está incompleta', detalle: ESTADO_CONCILIACION.INCOMPLETO.frase, accion: { texto: 'Abrir Finanzas', ruta: '#/finanzas' } });
    else if (!c) items.push({ tono: 'info', titulo: 'Nadie comparó Stripe y Meta con el libro de movimientos', detalle: 'Falta la conciliación: hasta entonces las cifras de cobro y de gasto no están verificadas.', accion: { texto: 'Abrir Finanzas', ruta: '#/finanzas' } });
  }
  return items;
}

const FRASE_CONC = { CONCILIADO: 'Cuadra', DESCUADRE: 'No cuadra', INCOMPLETO: 'Incompleta' };

/** Métricas de la cabecera: `valor` null = «—» (sin dato). Nunca un número inventado. */
export function metricasPagos(modelo, ahoraMs = Date.now()) {
  const [meta, stripe] = modelo.cuentas;
  const s2 = stripe.preguntas.find((p) => p.id === 'S-02');
  const conc = modelo.conciliacion;
  const sufijo = modelo.hayInfra && modelo.simulada ? ' · medición simulada' : '';
  return [
    { id: 'meta', etiqueta: 'Cuenta de Meta', valor: modelo.hayInfra ? meta.veredicto.etiqueta : null, tono: modelo.hayInfra ? meta.veredicto.tono : null, contexto: modelo.hayInfra ? `${meta.veredicto.frase}${sufijo}` : 'sin medir (falta el chequeo antes de lanzar)', ayuda: 'cuenta_publicitaria' },
    { id: 'saldo', etiqueta: 'Saldo de la cuenta de Meta', valor: null, tono: null, contexto: 'sin cifra: la dará el vigía de pagos', ayuda: 'saldo_cuenta' },
    { id: 'stripe', etiqueta: 'Stripe cobra y paga', valor: s2 && s2.medido ? s2.etiqueta : null, tono: s2 && s2.medido ? s2.tono : null, contexto: s2 && s2.medido ? `${stripe.veredicto.clave === 'verde' ? 'todas las comprobaciones de Stripe en verde' : (s2.tono === 'ok' ? 'cobra y paga; otra comprobación de Stripe pide mirar (abajo)' : stripe.veredicto.frase)}${sufijo}` : 'sin medir', ayuda: 'cobros_stripe' },
    { id: 'conciliacion', etiqueta: 'Conciliación', valor: conc ? FRASE_CONC[conc.estado] || conc.estado : null, tono: conc ? ({ CONCILIADO: 'ok', DESCUADRE: 'critico', INCOMPLETO: 'aviso' }[conc.estado] || null) : null, contexto: conc ? (ESTADO_CONCILIACION[conc.estado] || { frase: '' }).frase : 'sin conciliación: nadie comparó Stripe y Meta con el libro de movimientos', ayuda: 'conciliacion' },
    { id: 'medicion', etiqueta: 'Última medición', valor: modelo.hayInfra && modelo.generadoEn && fmt.relativo(modelo.generadoEn, ahoraMs) !== '—' ? fmt.relativo(modelo.generadoEn, ahoraMs) : null, tono: modelo.hayInfra ? (modelo.real ? 'ok' : 'aviso') : null, contexto: modelo.hayInfra ? (modelo.real ? 'vigente y en modo vivo' : (modelo.infra.detalle === 'vigente' ? 'no es una medición real y vigente' : modelo.infra.detalle)) : 'el chequeo antes de lanzar no se corrió', ayuda: 'preflight_infra' },
  ];
}

/** Qué produciría el saldo y por qué hoy no hay cifra. */
export const SIN_SALDO = {
  titulo: 'El saldo de la cuenta de Meta no está disponible como cifra',
  porque: 'El chequeo antes de lanzar compara el tope de gasto con lo ya gastado y guarda solo un veredicto (verde, amarillo o rojo) y un texto breve; no guarda el número. Y todavía no hay una lectura de la cuenta que se lo entregue al panel.',
  produce: 'Lo producirá el vigía de pagos: leerá cada 15 minutos, con campañas activas, el estado de la cuenta, el tope y lo gastado, y avisará por dos canales si la cuenta deja de gastar por un pago.',
  falta: ['Una lectura numérica del tope y de lo gastado de la cuenta de Meta.', 'Elegir el canal de avisos al celular (ver Avisos).', 'Construir el vigía de pagos (robot 7).'],
};

export const comandosPagos = () => [
  { titulo: 'Medir las cuentas (chequeo antes de lanzar)', comando: COMANDO_PREFLIGHT },
  { titulo: 'Generar el libro de movimientos y la conciliación', comando: comandosFinanzas().ledger },
];

/** Ítem por id (para pruebas y para la página). */
export const preguntaDe = (id) => PREGUNTA_POR_ID[id] || null;
