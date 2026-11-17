// lib/finanzas.js — lógica pura de #/finanzas (CONTRATO §4 `GET /finanzas`, §7b; criterio B0-17).
// Fuentes: empresa/finanzas/{ledger.jsonl, pnl.json, conciliacion.json, alertas.jsonl} (contratos ledger, pnl, conciliacion).
// Regla de oro: conciliación distinta de 0 ⇒ la cifra afectada se muestra TACHADA con su causa; sin dato ⇒ «sin dato», nunca 0.
// Sin DOM ni red. Dinero: enteros en unidad menor + moneda; todas las sumas son enteras (nunca float).

import { fmt } from '../ui.js';
import { aNumero, dineroValido, parametro, proporcionBp } from './operacion.js';

/** El panel entrega como mucho las últimas 500 líneas del ledger (dashboard/api_empresa.py::_MAX_LEDGER): con 500 o más, los totales pueden ser parciales. */
export const LIMITE_LEDGER_PANEL = 500;
export const TIPOS_LEDGER = ['pedido', 'gasto', 'reembolso', 'disputa', 'comision', 'impuesto', 'costo', 'ajuste'];
export const FUENTES_LEDGER = ['stripe', 'meta', 'costos', 'manual'];
const RE_FECHA = /^\d{4}-\d{2}-\d{2}$/;

/** Líneas del P&L en el orden de la fórmula (docs 13 Anexo A): signo = cómo entra en `resultado_operativo`; origen = de qué conciliación depende. */
export const LINEAS_PNL = [
  { clave: 'ingresos_brutos', etiqueta: 'Ingresos brutos (impuestos incluidos)', signo: 1, origen: 'stripe' },
  { clave: 'impuestos', etiqueta: 'Impuestos (se deben pagar en cada país)', signo: -1, origen: 'stripe' },
  { clave: 'reembolsos', etiqueta: 'Reembolsos', signo: -1, origen: 'stripe' },
  { clave: 'comisiones', etiqueta: 'Comisiones de Stripe', signo: -1, origen: 'stripe' },
  { clave: 'tarifas_disputa', etiqueta: 'Tarifas de disputa', signo: -1, origen: 'stripe' },
  { clave: 'disputas_perdidas', etiqueta: 'Disputas perdidas', signo: -1, origen: 'stripe' },
  { clave: 'gasto_meta', etiqueta: 'Gasto en anuncios (Meta)', signo: -1, origen: 'meta' },
  { clave: 'costo_ia', etiqueta: 'Costo de IA', signo: -1, origen: 'costos' },
  { clave: 'otros_costos', etiqueta: 'Otros costos', signo: -1, origen: 'costos' },
];

// ----------------------------------------------------------------------------------------------------------------
// Ledger
// ----------------------------------------------------------------------------------------------------------------

function lineaLedgerValida(l) {
  return l && typeof l === 'object' && typeof l.clave_natural === 'string' && TIPOS_LEDGER.includes(l.tipo)
    && dineroValido(l.importe) && (l.sentido === 'entrada' || l.sentido === 'salida') && RE_FECHA.test(l.fecha || '');
}

/**
 * El ledger es append-only con upsert: una clave natural que cambia agrega una línea y manda la ÚLTIMA (datos.ledger.leer_vigente).
 * Devuelve {vigentes (orden por fecha desc, ts desc), reemplazadas (n), invalidas (n)}.
 */
export function vigentesLedger(lineas) {
  const porClave = new Map();
  let invalidas = 0;
  let total = 0;
  for (const l of Array.isArray(lineas) ? lineas : []) {
    if (!lineaLedgerValida(l)) { invalidas += 1; continue; }
    total += 1;
    porClave.set(l.clave_natural, l);
  }
  const vigentes = [...porClave.values()].map((l) => ({
    clave_natural: l.clave_natural, tipo: l.tipo, oferta_id: l.oferta_id || null, fecha: l.fecha, ts: l.ts || null, sentido: l.sentido,
    importe: dineroValido(l.importe), fuente: l.fuente || null, es_prueba: l.es_prueba === true, adid: l.adid || null,
    importe_base: dineroValido(l.importe_base), tipo_cambio_id: l.tipo_cambio_id || null,
  }));
  vigentes.sort((a, b) => (b.fecha === a.fecha ? String(b.ts || '').localeCompare(String(a.ts || '')) : b.fecha.localeCompare(a.fecha)));
  return { vigentes, reemplazadas: total - vigentes.length, invalidas };
}

export function filtrarLedger(lineas, { oferta, tipo, fuente, incluirPruebas = false, desde, hasta } = {}) {
  return lineas.filter((l) => (incluirPruebas || !l.es_prueba)
    && (!oferta || l.oferta_id === oferta) && (!tipo || l.tipo === tipo) && (!fuente || l.fuente === fuente)
    && (!desde || l.fecha >= desde) && (!hasta || l.fecha <= hasta));
}

/** Suma con signo (entrada +, salida −) por moneda y por tipo. Las pruebas no cuentan. Nunca mezcla monedas. */
export function totalesLedger(lineas) {
  const porMoneda = new Map();
  let pruebas = 0;
  for (const l of lineas) {
    if (l.es_prueba) { pruebas += 1; continue; }
    const m = l.importe.moneda;
    const t = porMoneda.get(m) || { moneda: m, entradas: 0n, salidas: 0n, lineas: 0, porTipo: {} };
    const v = BigInt(l.importe.monto);
    if (l.sentido === 'entrada') t.entradas += v; else t.salidas += v;
    t.porTipo[l.tipo] = (t.porTipo[l.tipo] || 0n) + (l.sentido === 'entrada' ? v : -v);
    t.lineas += 1;
    porMoneda.set(m, t);
  }
  const aSeguro = (b) => (b <= BigInt(Number.MAX_SAFE_INTEGER) && b >= BigInt(-Number.MAX_SAFE_INTEGER) ? Number(b) : null);
  const monedas = [...porMoneda.values()].map((t) => ({
    moneda: t.moneda, lineas: t.lineas, entradas: aSeguro(t.entradas), salidas: aSeguro(t.salidas), neto: aSeguro(t.entradas - t.salidas),
    porTipo: Object.fromEntries(Object.entries(t.porTipo).map(([k, v]) => [k, aSeguro(v)])),
  }));
  return { monedas, pruebasExcluidas: pruebas };
}

/** Totales por oferta y moneda (entrada/salida), para la tabla resumen. */
export function totalesPorOferta(lineas) {
  const mapa = new Map();
  for (const l of lineas) {
    if (l.es_prueba) continue;
    const k = `${l.oferta_id || '—'}|${l.importe.moneda}`;
    const t = mapa.get(k) || { oferta_id: l.oferta_id || '—', moneda: l.importe.moneda, entradas: 0n, salidas: 0n, lineas: 0 };
    if (l.sentido === 'entrada') t.entradas += BigInt(l.importe.monto); else t.salidas += BigInt(l.importe.monto);
    t.lineas += 1;
    mapa.set(k, t);
  }
  return [...mapa.values()].map((t) => ({ oferta_id: t.oferta_id, moneda: t.moneda, lineas: t.lineas, entradas: Number(t.entradas), salidas: Number(t.salidas), neto: Number(t.entradas - t.salidas) }))
    .sort((a, b) => a.oferta_id.localeCompare(b.oferta_id));
}

// ----------------------------------------------------------------------------------------------------------------
// Conciliación triple Stripe ↔ ledger ↔ Meta
// ----------------------------------------------------------------------------------------------------------------

const TONO_CONCILIACION = { CONCILIADO: 'ok', DESCUADRE: 'error', INCOMPLETO: 'aviso' };

function cotejo(par, etiqueta, nombreIzq, nombreDer) {
  const izq = par && dineroValido(par.izquierda);
  const der = par && dineroValido(par.derecha);
  const dif = par && dineroValido(par.diferencia);
  if (!izq || !der || !dif) return { etiqueta, izquierda: izq || null, derecha: der || null, diferencia: dif || null, cuadra: null, causa: `${etiqueta}: el archivo no trae el cotejo completo` };
  const cuadra = dif.monto === 0 && izq.monto === der.monto;
  const causa = cuadra ? null : `${nombreIzq} ${fmt.dinero(izq.monto, izq.moneda)} ≠ ${nombreDer} ${fmt.dinero(der.monto, der.moneda)}: diferencia ${fmt.dinero(dif.monto, dif.moneda)}`;
  return { etiqueta, izquierda: izq, derecha: der, diferencia: dif, cuadra, causa };
}

/** Conciliación → cotejos, estado, y qué cifras tacha (con causa). null si no hay conciliación. */
export function modeloConciliacion(c) {
  if (!c || typeof c !== 'object' || typeof c.estado !== 'string') return null;
  const stripe = cotejo(c.stripe_vs_ledger, 'Stripe ↔ libro de movimientos', 'Stripe', 'libro de movimientos');
  const meta = cotejo(c.gasto_meta_vs_ledger, 'Gasto Meta ↔ libro de movimientos', 'Meta', 'libro de movimientos');
  const compras = c.compras && typeof c.compras === 'object' ? { meta: c.compras.meta ?? null, stripe: c.compras.stripe ?? null, razon: aNumero(c.compras.razon_meta_stripe) } : null;
  const tachadas = { stripe: null, meta: null, todo: null };
  if (stripe.cuadra === false) tachadas.stripe = stripe.causa;
  if (meta.cuadra === false) tachadas.meta = meta.causa;
  if (c.estado === 'INCOMPLETO') tachadas.todo = 'conciliación INCOMPLETA: faltan datos para cerrar el cotejo (por ejemplo, cobros que todavía no llegaron o una fuente sin leer)';
  else if (c.cifras_tachadas === true && !tachadas.stripe && !tachadas.meta) tachadas.todo = `la conciliación marca estas cifras como tachadas (estado: ${c.estado})`;
  return {
    estado: c.estado, tono: TONO_CONCILIACION[c.estado] || 'neutro', periodo: c.periodo || null, generado_en: c.generado_en || null, moneda: c.moneda || null,
    stripe, meta, compras, coberturaBp: Number.isSafeInteger(c.cobertura_adid_bp) ? c.cobertura_adid_bp : null,
    excluidos: c.excluidos && typeof c.excluidos === 'object' ? { pruebas: c.excluidos.pruebas ?? 0, internas: c.excluidos.internas ?? 0 } : null,
    pendientesAsincronos: Number.isSafeInteger(c.pendientes_asincronos) ? c.pendientes_asincronos : null,
    cifrasTachadas: c.cifras_tachadas === true || !!(tachadas.stripe || tachadas.meta || tachadas.todo), tachadas,
  };
}

// ----------------------------------------------------------------------------------------------------------------
// P&L
// ----------------------------------------------------------------------------------------------------------------

/** Resultado operativo esperado desde las 9 líneas (fórmula del Anexo A de departamentos/13) y si coincide con el informado. */
export function verificarResultado(bloque) {
  const l = bloque && bloque.lineas;
  const informado = bloque && dineroValido(bloque.resultado_operativo);
  if (!l || !informado) return { esperado: null, informado: informado || null, coincide: null };
  let suma = 0n;
  for (const d of LINEAS_PNL) {
    const v = dineroValido(l[d.clave]);
    if (!v || v.moneda !== informado.moneda) return { esperado: null, informado, coincide: null };
    suma += BigInt(d.signo) * BigInt(v.monto);
  }
  const esperado = Number(suma);
  return { esperado: { monto: esperado, moneda: informado.moneda }, informado, coincide: esperado === informado.monto };
}

function bloquePnl(b, id) {
  const lineas = {};
  for (const d of LINEAS_PNL) lineas[d.clave] = dineroValido(b && b.lineas && b.lineas[d.clave]);
  const k = (b && b.kpis) || {};
  const verificacion = verificarResultado(b);
  const propias = {};
  if (verificacion.coincide === false) {
    propias.resultado_operativo = `las líneas suman ${fmt.dinero(verificacion.esperado.monto, verificacion.esperado.moneda)} pero el resultado informado es ${fmt.dinero(verificacion.informado.monto, verificacion.informado.moneda)}`;
  }
  return {
    id, lineas, resultado: dineroValido(b && b.resultado_operativo), verificacion, causasPropias: propias, madurez: (b && b.madurez) || null,
    kpis: { pedidos: Number.isSafeInteger(k.pedidos) ? k.pedidos : null, aov: dineroValido(k.aov), mc: dineroValido(k.mc), cpa: dineroValido(k.cpa), roas_neto: aNumero(k.roas_neto), mer: aNumero(k.mer) },
  };
}

/** Qué claves del P&L se tachan y por qué: frescura stale + conciliación (diferencia ≠ 0). */
export function tachadosDePnl(pnl, conc) {
  const causas = {};
  const poner = (clave, causa) => { if (!causas[clave]) causas[clave] = []; if (!causas[clave].includes(causa)) causas[clave].push(causa); };
  const todas = [...LINEAS_PNL.map((d) => d.clave), 'resultado_operativo', 'kpis'];
  if (pnl && pnl.frescura && pnl.frescura.estado === 'stale') for (const k of todas) poner(k, `cuenta de resultados con datos hasta ${fmt.fecha(pnl.frescura.datos_hasta)} (desactualizada)`);
  if (conc) {
    const stripeKeys = LINEAS_PNL.filter((d) => d.origen === 'stripe').map((d) => d.clave);
    if (conc.tachadas.stripe) for (const k of [...stripeKeys, 'resultado_operativo', 'kpis']) poner(k, conc.tachadas.stripe);
    if (conc.tachadas.meta) for (const k of ['gasto_meta', 'resultado_operativo', 'kpis']) poner(k, conc.tachadas.meta);
    if (conc.tachadas.todo) for (const k of todas) poner(k, conc.tachadas.todo);
  }
  return causas;
}

/** Todas las causas que tachan una celda del P&L (frescura, conciliación y la propia fórmula del bloque). */
export function causasDeCelda(pnl, bloque, clave) {
  return [...((pnl && pnl.causas && pnl.causas[clave]) || []), ...(bloque && bloque.causasPropias && bloque.causasPropias[clave] ? [bloque.causasPropias[clave]] : [])];
}

/** Modelo del P&L: un bloque por oferta + consolidado, con cifras tachadas y verificación de la fórmula. */
export function modeloPnl(pnl, conc) {
  if (!pnl || typeof pnl !== 'object' || !pnl.consolidado) return null;
  const causas = tachadosDePnl(pnl, conc);
  const periodo = pnl.periodo && pnl.periodo.desde ? pnl.periodo : null;
  const avisos = [];
  if (conc && conc.periodo && periodo && (conc.periodo.desde !== periodo.desde || conc.periodo.hasta !== periodo.hasta)) {
    avisos.push(`La conciliación cubre otro periodo (${conc.periodo.desde} a ${conc.periodo.hasta}) que la cuenta de resultados (${periodo.desde} a ${periodo.hasta}).`);
  }
  if (!conc) avisos.push('Sin conciliación: las cifras de la cuenta de resultados no están verificadas contra Stripe ni Meta.');
  const bloques = [bloquePnl(pnl.consolidado, 'consolidado'), ...(Array.isArray(pnl.por_oferta) ? pnl.por_oferta.map((o) => bloquePnl(o && o.bloque, o && o.oferta_id)) : [])];
  return {
    vista: pnl.vista || null, moneda: pnl.moneda_base || null, fx_ref: pnl.fx_ref || null, periodo, generado_en: pnl.generado_en || null,
    frescura: pnl.frescura && typeof pnl.frescura === 'object' ? { datos_hasta: pnl.frescura.datos_hasta || null, estado: pnl.frescura.estado || null } : null,
    bloques, causas, avisos,
  };
}

// ----------------------------------------------------------------------------------------------------------------
// Costos de IA
// ----------------------------------------------------------------------------------------------------------------

/**
 * Costo de IA por oferta: del P&L (`costo_ia`) y del ledger (fuente costos). Porcentaje sobre ingresos brutos solo si hay ingresos
 * (sin ingresos NO hay porcentaje: no se inventa 0 %); contra `dashboard.costo_ia_max_pct` si el parámetro existe.
 */
export function costosIa(pnl, ledgerVigente, parametros) {
  const maxPct = aNumero(parametro(parametros, 'dashboard.costo_ia_max_pct'));
  const filas = [];
  const bloques = pnl && pnl.consolidado ? [{ id: 'consolidado', b: pnl.consolidado }, ...(Array.isArray(pnl.por_oferta) ? pnl.por_oferta.map((o) => ({ id: o.oferta_id, b: o.bloque })) : [])] : [];
  const delLedger = new Map();
  for (const l of ledgerVigente || []) {
    if (l.es_prueba || l.fuente !== 'costos') continue;
    const k = `${l.oferta_id}|${l.importe.moneda}`;
    delLedger.set(k, (delLedger.get(k) || 0n) + BigInt(l.importe.monto));
  }
  for (const { id, b } of bloques) {
    const costo = dineroValido(b && b.lineas && b.lineas.costo_ia);
    const bruto = dineroValido(b && b.lineas && b.lineas.ingresos_brutos);
    if (!costo) continue;
    const pctBp = bruto && bruto.moneda === costo.moneda && bruto.monto > 0 ? proporcionBp(costo.monto, bruto.monto) : null;
    const lg = delLedger.get(`${id}|${costo.moneda}`);
    filas.push({
      id, costo, ingresos: bruto, pctBp, topePct: maxPct,
      estado: pctBp === null ? 'sin_ingresos' : maxPct !== null && pctBp > maxPct * 100 ? 'rojo' : 'ok',
      ledger: lg === undefined ? null : { monto: Number(lg), moneda: costo.moneda },
      descuadreConLedger: lg !== undefined && Number(lg) !== costo.monto,
    });
  }
  return filas;
}

// ----------------------------------------------------------------------------------------------------------------
// Alertas (empresa/finanzas/alertas.jsonl; formato unificado F1/F2)
// ----------------------------------------------------------------------------------------------------------------

/**
 * Severidad del archivo (alertas.schema.json 1.0.0: info · amarilla · naranja · roja) → tono del chip. Cada nivel lleva icono y etiqueta propios:
 * info (círculo «i») · amarilla = aviso (triángulo) · NARANJA = grave (rombo; F1-A02: pausa de oferta) · roja = error (círculo con X).
 * El orden de las comprobaciones importa: «naranja» antes que «alta/grave» y «roja» después. Admite además sinónimos antiguos (crítica, media, baja…).
 */
export function tonoSeveridad(s) {
  const t = String(s || '').toLowerCase();
  if (/naranj|orange/.test(t)) return 'grave';
  if (/(roj|crit|alta|grave|error|bloq)/.test(t)) return 'error';
  if (/(amar|media|aviso|warn|atenc)/.test(t)) return 'aviso';
  if (/(info|baja|verde|menor)/.test(t)) return 'info';
  return 'neutro';
}
const PESO_TONO = { error: 0, grave: 1, aviso: 2, info: 3, neutro: 4 };

/** Etiqueta humana de la severidad (la clave técnica del archivo va aparte, en el detalle). */
export function etiquetaSeveridad(s) {
  const t = String(s ?? '').toLowerCase();
  if (/naranj|orange/.test(t)) return 'Naranja · pausa';
  if (/(roj|crit|alta|grave|error|bloq)/.test(t)) return 'Roja';
  if (/(amar|media|aviso|warn|atenc)/.test(t)) return 'Amarilla';
  if (/(info|baja|verde|menor)/.test(t)) return 'Información';
  return s === null || s === undefined || s === '' ? 'Sin gravedad' : String(s);
}

/** Estado de una alerta (abierta · reconocida · cerrada; antiguos: resuelta…). Reconocida sigue viva: alguien la vio pero el valor no volvió al rango. */
export function estadoAlerta(estado) {
  const e = typeof estado === 'string' ? estado.toLowerCase() : '';
  if (/(cerrad|resuel|descart|ignor|atendid)/.test(e)) return { texto: 'Cerrada', abierta: false, tono: 'ok', clave: 'cerrada' };
  if (/reconoc/.test(e)) return { texto: 'Reconocida', abierta: true, tono: 'info', clave: 'reconocida' };
  return { texto: 'Abierta', abierta: true, tono: 'aviso', clave: 'abierta' };
}

function textoCorto(v) {
  if (v === null || v === undefined) return null;
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (dineroValido(v)) return fmt.dinero(v.monto, v.moneda);
  try { const s = JSON.stringify(v); return s.length > 120 ? `${s.slice(0, 117)}…` : s; } catch (_) { return null; }
}

export function normalizarAlertas(lineas) {
  const salida = [];
  for (const a of Array.isArray(lineas) ? lineas : []) {
    if (!a || typeof a !== 'object') continue;
    const est = estadoAlerta(a.estado);
    salida.push({
      id: a.id ?? null, ts: a.ts || null, severidad: a.severidad ?? null, tono: tonoSeveridad(a.severidad), etiquetaSeveridad: etiquetaSeveridad(a.severidad), regla_id: a.regla_id || null, origen: a.origen || null,
      oferta_id: a.oferta_id || null, macro_nicho: a.macro_nicho || null, nivel: a.nivel || null, valor: textoCorto(a.valor), umbral: textoCorto(a.umbral),
      // umbral null = «sin umbral fijado»: la alerta queda gris, nunca verde (alertas.schema.json)
      sinUmbral: a.umbral === null || a.umbral === undefined,
      accion_sugerida: a.accion_sugerida || null, estado: typeof a.estado === 'string' ? a.estado : null, estadoInfo: est, abierta: est.abierta,
    });
  }
  return salida.sort((x, y) => (x.abierta === y.abierta ? (PESO_TONO[x.tono] - PESO_TONO[y.tono]) || String(y.ts || '').localeCompare(String(x.ts || '')) : x.abierta ? -1 : 1));
}

// ----------------------------------------------------------------------------------------------------------------
// Modelo completo
// ----------------------------------------------------------------------------------------------------------------

/** Normaliza lo que entrega GET /finanzas (tolera claves ausentes). */
export function normalizarFinanzas(datos) {
  const d = datos && typeof datos === 'object' ? datos : {};
  return { ledger: Array.isArray(d.ledger) ? d.ledger : [], pnl: d.pnl && typeof d.pnl === 'object' ? d.pnl : null, conciliacion: d.conciliacion && typeof d.conciliacion === 'object' ? d.conciliacion : null, alertas: Array.isArray(d.alertas) ? d.alertas : [] };
}

export function modeloFinanzas(datos, parametros) {
  const d = normalizarFinanzas(datos);
  const led = vigentesLedger(d.ledger);
  const conc = modeloConciliacion(d.conciliacion);
  const pnl = modeloPnl(d.pnl, conc);
  const alertas = normalizarAlertas(d.alertas);
  return {
    ledger: { ...led, posibleTruncado: d.ledger.length >= LIMITE_LEDGER_PANEL }, totales: totalesLedger(led.vigentes), porOferta: totalesPorOferta(led.vigentes),
    conciliacion: conc, pnl, costosIa: costosIa(d.pnl, led.vigentes, parametros), alertas,
    alertasAbiertas: alertas.filter((a) => a.abierta).length,
    hayAlgo: led.vigentes.length > 0 || !!pnl || !!conc || alertas.length > 0,
    ofertas: [...new Set(led.vigentes.map((l) => l.oferta_id).filter(Boolean))].sort(),
  };
}

// ----------------------------------------------------------------------------------------------------------------
// Rediseño U4: lenguaje de negocio, margen y atención
// ----------------------------------------------------------------------------------------------------------------

export const NOMBRE_TIPO_LEDGER = { pedido: 'Venta', gasto: 'Gasto', reembolso: 'Reembolso', disputa: 'Disputa', comision: 'Comisión', impuesto: 'Impuesto', costo: 'Costo', ajuste: 'Ajuste' };
export const NOMBRE_FUENTE_LEDGER = { stripe: 'Stripe', meta: 'Meta', costos: 'Costos de IA', manual: 'Manual' };
export const ESTADO_CONCILIACION = {
  CONCILIADO: { texto: 'Cuadra', tono: 'ok', frase: 'Stripe y Meta coinciden con el libro de movimientos.' },
  DESCUADRE: { texto: 'No cuadra', tono: 'error', frase: 'Alguna fuente no coincide con el libro de movimientos: las cifras afectadas se muestran tachadas.' },
  INCOMPLETO: { texto: 'Incompleta', tono: 'aviso', frase: 'Faltan datos para cerrar el cotejo (pendientes por llegar o una fuente sin leer).' },
};

/** Margen = resultado / ingresos en puntos básicos (negativo si hay pérdida). null sin ingresos positivos: no se inventa un 0 %. */
export function margenBp(resultado, ingresos) {
  const r = dineroValido(resultado);
  const i = dineroValido(ingresos);
  if (!r || !i || r.moneda !== i.moneda || i.monto <= 0) return null;
  const q = proporcionBp(Math.abs(r.monto), i.monto);
  if (q === null) return null;
  return r.monto < 0 ? -q : q;
}

/** Suma de varias líneas de un bloque del P&L (con el signo de cada una). null si falta alguna: sin dato no se suma como 0. */
export function sumaLineas(bloque, claves) {
  let total = 0n;
  let moneda = null;
  for (const k of claves) {
    const d = bloque && bloque.lineas ? bloque.lineas[k] : null;
    if (!d || (moneda && d.moneda !== moneda)) return null;
    moneda = d.moneda;
    total += BigInt(d.monto);
  }
  return moneda && total <= BigInt(Number.MAX_SAFE_INTEGER) ? { monto: Number(total), moneda } : null;
}

/**
 * Lo que requiere atención en Finanzas, de más a menos urgente.
 * @returns [{tono:'critico'|'aviso'|'info', titulo, detalle?, accion?}]
 */
export function atencionFinanzas(m) {
  const items = [];
  const c = m.conciliacion;
  if (!m.hayAlgo) return items;
  if (!c) items.push({ tono: 'aviso', titulo: 'Las cifras no están verificadas', detalle: 'Falta la conciliación: nadie ha comparado Stripe y Meta con el libro de movimientos.' });
  else if (c.estado === 'DESCUADRE') {
    items.push({ tono: 'critico', titulo: 'Stripe o Meta no cuadran con el libro de movimientos', detalle: [c.tachadas.stripe, c.tachadas.meta].filter(Boolean).join(' · ') || ESTADO_CONCILIACION.DESCUADRE.frase });
  } else if (c.estado === 'INCOMPLETO') items.push({ tono: 'aviso', titulo: 'La conciliación está incompleta', detalle: ESTADO_CONCILIACION.INCOMPLETO.frase });
  const abiertas = m.alertas.filter((a) => a.abierta);
  const rojas = abiertas.filter((a) => a.tono === 'error');
  const naranjas = abiertas.filter((a) => a.tono === 'grave');
  const amarillas = abiertas.filter((a) => a.tono === 'aviso');
  if (rojas.length) items.push({ tono: 'critico', titulo: `${rojas.length} ${rojas.length === 1 ? 'alerta roja abierta' : 'alertas rojas abiertas'}`, detalle: rojas[0].accion_sugerida || (rojas[0].regla_id ? `Regla ${rojas[0].regla_id}` : undefined) });
  if (naranjas.length) items.push({ tono: 'grave', titulo: `${naranjas.length} ${naranjas.length === 1 ? 'alerta naranja abierta' : 'alertas naranjas abiertas'}: una oferta debería pausarse`, detalle: naranjas[0].accion_sugerida || (naranjas[0].regla_id === 'F1-A02' ? 'Una regla de finanzas (F1-A02) pide pausar la oferta afectada.' : undefined) });
  if (amarillas.length) items.push({ tono: 'aviso', titulo: `${amarillas.length} ${amarillas.length === 1 ? 'alerta amarilla abierta' : 'alertas amarillas abiertas'}`, detalle: amarillas[0].accion_sugerida || undefined });
  const caro = m.costosIa.filter((x) => x.estado === 'rojo');
  if (caro.length) items.push({ tono: 'aviso', titulo: 'El costo de IA supera el máximo permitido', detalle: `Afecta a ${caro.map((x) => (x.id === 'consolidado' ? 'el consolidado' : x.id)).join(', ')}.` });
  if (m.pnl && m.pnl.frescura && m.pnl.frescura.estado === 'stale') items.push({ tono: 'aviso', titulo: 'La cuenta de resultados está desactualizada', detalle: 'Sus cifras se muestran tachadas hasta que se recalcule.' });
  if (m.ledger.posibleTruncado) items.push({ tono: 'info', titulo: 'El libro de movimientos puede estar incompleto en pantalla', detalle: 'El panel lee solo las últimas 500 líneas; la cuenta de resultados sí cubre todo el periodo.' });
  const orden = { critico: 0, grave: 1, aviso: 2, info: 3 };
  return items.sort((a, b) => orden[a.tono] - orden[b.tono]);
}

/** Comandos copiables para llenar cada bloque vacío (README de datos; departamentos/12 §3.3). */
export function comandosFinanzas() {
  return {
    ledger: '.venv/bin/python -m datos.ledger --oferta OF-AAAAMM-NN --periodo AAAA-MM-DD:AAAA-MM-DD --moneda EUR',
    etl: '.venv/bin/python -m datos.etl_stripe --fixture tests/fixtures/datos/stripe_eventos_OF-202611-01.json',
  };
}
