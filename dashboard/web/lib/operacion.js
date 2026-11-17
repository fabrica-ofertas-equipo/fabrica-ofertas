// lib/operacion.js — lógica pura de la pantalla #/operacion (CONTRATO §5, §7b; criterio B0-17).
// Sin DOM y sin red: datos → modelo de vista. Se prueba con `node --test` (tests/dashboard/test_web_operacion.mjs).
//
// Fuentes (todas de lectura): ofertas/<id>/08-operacion/diario/<fecha>/kpi_oferta_dia.json, decisiones.jsonl (esquema
// «Decisión de D8»: decision.schema.json), ordenes_presupuesto.jsonl, veredicto_oferta.json; economía de 03-oferta/economia.json;
// topes de empresa/limites.yaml y umbrales de empresa/parametros.yaml.
//
// Criterio B0-17: la cifra vieja o descuadrada se muestra TACHADA con su causa; un dato ausente es «sin dato», jamás un 0.
// Dinero: enteros en unidad menor + moneda (nunca float). Los cálculos de CPA y de proporciones usan aritmética entera (BigInt).

/** Nombre exacto del registro de D8 (decision.schema.json: «Decisión de D8», una línea de 08-operacion/decisiones.jsonl). */
export const ARCHIVO_DECISIONES = '08-operacion/decisiones.jsonl';
export const NOMBRE_DECISION = 'Decisión de D8';
export const ACCIONES_DECISION = ['MATAR', 'SEGUIR', 'ESCALAR', 'INCONCLUSO', 'BLOQUEADO'];

// ----------------------------------------------------------------------------------------------------------------
// Números y dinero
// ----------------------------------------------------------------------------------------------------------------

/** Número desde entero/decimal-cadena (los esquemas dan decimales como cadena). null si no es un número finito. */
export function aNumero(x) {
  if (typeof x === 'number') return Number.isFinite(x) ? x : null;
  if (typeof x === 'string' && /^-?\d+(\.\d+)?$/.test(x.trim())) return Number(x);
  return null;
}

/** {monto, moneda} válido (entero seguro + ISO 4217) o null. */
export function dineroValido(d) {
  if (!d || typeof d !== 'object') return null;
  if (!Number.isSafeInteger(d.monto) || typeof d.moneda !== 'string' || !/^[A-Z]{3}$/.test(d.moneda)) return null;
  return { monto: d.monto, moneda: d.moneda };
}

/** 'EUR_minor' → 'EUR' (unidad de las filas de kpi_oferta_dia). */
export function monedaDeUnidad(unidad) {
  const m = /^([A-Z]{3})_minor$/.exec(typeof unidad === 'string' ? unidad : '');
  return m ? m[1] : null;
}

function divBig(a, b) { // a/b redondeado half-even, a >= 0, b > 0 (BigInt)
  let q = a / b;
  const r2 = (a % b) * 2n;
  if (r2 > b || (r2 === b && q % 2n === 1n)) q += 1n;
  return q;
}

/** a/b entero redondeado half-even (a ≥ 0, b > 0). null si no se puede (nunca 0 por defecto). */
export function dividirRedondeado(a, b) {
  if (!Number.isSafeInteger(a) || !Number.isSafeInteger(b) || a < 0 || b <= 0) return null;
  return Number(divBig(BigInt(a), BigInt(b)));
}

/** a/b en puntos básicos (10000 = 100 %), entero. null si b ≤ 0 o datos inválidos. */
export function proporcionBp(a, b) {
  if (!Number.isSafeInteger(a) || !Number.isSafeInteger(b) || a < 0 || b <= 0) return null;
  return Number(divBig(BigInt(a) * 10000n, BigInt(b)));
}

/** Texto de horas/minutos/días con coma decimal: 1.5 → «1,5 h», 0.25 → «15 min», 50 → «2,1 d». */
export function textoDuracionH(h) {
  if (typeof h !== 'number' || !Number.isFinite(h) || h < 0) return '—';
  const u = (n) => String(Math.round(n * 10) / 10).replace('.', ',');
  if (h < 1) return `${Math.round(h * 60)} min`;
  if (h >= 48) return `${u(h / 24)} d`;
  return `${u(h)} h`;
}

// ----------------------------------------------------------------------------------------------------------------
// Frescura (B0-17)
// ----------------------------------------------------------------------------------------------------------------

export const FUENTES = ['meta', 'stripe_eventos', 'stripe_balance'];
export const NOMBRE_FUENTE = { meta: 'Meta', stripe_eventos: 'Stripe (compras)', stripe_balance: 'Stripe (saldo)' };
const ORDEN_SEMAFORO = { verde: 0, amarillo: 1, rojo: 2 };

/** De qué fuentes depende cada cifra del snapshot. Lo no listado depende de Meta y de los eventos de Stripe (lo más prudente). */
export const DEPENDENCIAS = {
  gasto_meta: ['meta'], impresiones: ['meta'], clics_enlace: ['meta'], ctr_enlace: ['meta'], cpm: ['meta'], cpc_enlace: ['meta'],
  compras_stripe: ['stripe_eventos'], pedidos: ['stripe_eventos'], ingresos_brutos: ['stripe_eventos'], tasa_reembolso: ['stripe_eventos'],
  reembolso_pct: ['stripe_eventos'], tasa_disputa: ['stripe_eventos'], cobertura_atrib: ['stripe_eventos'], aov: ['stripe_eventos'],
  cpa: ['meta', 'stripe_eventos'], cpa_visto: ['meta', 'stripe_eventos'], cpa_neto: ['meta', 'stripe_eventos'],
  razon_meta_stripe: ['meta', 'stripe_eventos'], ratio_recon: ['meta', 'stripe_eventos'], roas_stripe: ['meta', 'stripe_eventos'],
  mer: ['meta', 'stripe_eventos'], saldo_stripe: ['stripe_balance'], payout_pendiente: ['stripe_balance'],
};
/** Nombre en palabras de cada cifra de la foto del día (para los avisos; la clave interna queda en el detalle). */
export const NOMBRE_KPI = {
  gasto_meta: 'gasto en anuncios', impresiones: 'veces que se mostró', clics_enlace: 'clics en el enlace', ctr_enlace: '% que hace clic', cpm: 'costo por mil vistas', cpc_enlace: 'costo por clic',
  compras_stripe: 'compras (Stripe)', pedidos: 'pedidos', ingresos_brutos: 'ingresos brutos', tasa_reembolso: 'tasa de reembolsos', cpa: 'costo por venta', cpa_visto: 'costo por venta visto por Meta',
  cpa_neto: 'costo por venta neto', razon_meta_stripe: 'compras de Meta frente a Stripe', cobertura_atrib: 'compras ligadas a un anuncio',
};
export function dependenciasDe(kpiId) { return DEPENDENCIAS[kpiId] || ['meta', 'stripe_eventos']; }

/** Horas transcurridas entre `generado_en` y `ahora` (≥ 0; un snapshot «del futuro» cuenta 0). null si no hay fecha válida. */
export function edadSnapshotH(snapshot, ahora) {
  const g = Date.parse(snapshot && snapshot.generado_en);
  const a = ahora instanceof Date ? ahora.getTime() : Number(ahora);
  if (!Number.isFinite(g) || !Number.isFinite(a)) return null;
  return Math.max(0, (a - g) / 3600000);
}

/**
 * Estado de una fuente de datos del snapshot.
 * @param nombre 'meta' | 'stripe_eventos' | 'stripe_balance'
 * @param f      {frescura_h, estado} del snapshot (puede faltar)
 * @param opc    {umbrales:{<fuente>:{amarillo,rojo}} (de parametros.dashboard), horasExtra (edad del snapshot respecto al reloj)}
 * @returns {nombre, etiqueta, estado:'verde'|'amarillo'|'rojo'|'desconocido', horas, causa}
 */
export function evaluarFuente(nombre, f, opc = {}) {
  const etiqueta = NOMBRE_FUENTE[nombre] || nombre;
  if (!f || typeof f !== 'object') {
    return { nombre, etiqueta, estado: 'desconocido', horas: null, causa: `${etiqueta}: la foto del día no informa de esta fuente` };
  }
  const horas = aNumero(f.frescura_h);
  const horasEf = horas === null ? null : horas + (opc.horasExtra > 0 ? opc.horasExtra : 0);
  const u = opc.umbrales && opc.umbrales[nombre];
  let estado = ORDEN_SEMAFORO[f.estado] === undefined ? 'desconocido' : f.estado;
  if (u && horasEf !== null) {
    const calc = Number.isFinite(u.rojo) && horasEf >= u.rojo ? 'rojo' : Number.isFinite(u.amarillo) && horasEf >= u.amarillo ? 'amarillo' : 'verde';
    if (estado === 'desconocido' || ORDEN_SEMAFORO[calc] > ORDEN_SEMAFORO[estado]) estado = calc;
  }
  let causa = null;
  if (estado === 'rojo') {
    if (horasEf === null) causa = `${etiqueta} sin lectura registrada (estado rojo)`;
    else if (u && Number.isFinite(u.rojo) && horasEf >= u.rojo) causa = `${etiqueta} con ${textoDuracionH(horasEf)} sin actualizar (rojo desde ${textoDuracionH(u.rojo)})`;
    else causa = `${etiqueta} en rojo según la foto del día (${textoDuracionH(horasEf)} sin actualizar)`;
  } else if (estado === 'amarillo') {
    causa = `${etiqueta} con ${textoDuracionH(horasEf)} sin actualizar${u && Number.isFinite(u.amarillo) ? ` (amarillo desde ${textoDuracionH(u.amarillo)})` : ''}`;
  }
  return { nombre, etiqueta, estado, horas: horasEf, causa };
}

/** Umbrales de frescura de parametros.dashboard.frescura_{fuente}_{amarillo,rojo}_h → {<fuente>:{amarillo,rojo}}. */
export function umbralesDeFrescura(parametros) {
  const grupos = gruposDeParametros(parametros);
  const d = (grupos && grupos.dashboard) || {};
  const salida = {};
  for (const f of FUENTES) {
    const a = aNumero(valorDe(d[`frescura_${f}_amarillo_h`]));
    const r = aNumero(valorDe(d[`frescura_${f}_rojo_h`]));
    if (a !== null || r !== null) salida[f] = { amarillo: a, rojo: r };
  }
  return salida;
}

function valorDe(p) { return p && typeof p === 'object' && 'valor' in p ? p.valor : p; }

/** parametros.yaml entero → {grupo:{clave:{valor,…}}}; admite que el panel entregue solo `grupos`. */
export function gruposDeParametros(parametros) {
  if (!parametros || typeof parametros !== 'object') return null;
  if (parametros.grupos && typeof parametros.grupos === 'object') return parametros.grupos;
  return parametros;
}

/** Lee `grupo.clave` de parametros (valor desnudo o null). */
export function parametro(parametros, ruta) {
  const g = gruposDeParametros(parametros);
  if (!g) return null;
  const [grupo, clave] = String(ruta).split('.');
  const p = g[grupo] && g[grupo][clave];
  const v = valorDe(p);
  return v === undefined ? null : v;
}

/**
 * Una cifra del snapshot con su estado de confianza.
 *   estado: 'ok' | 'gris' (datos insuficientes: n bajo) | 'provisional' | 'tachada' (vieja/descuadrada) | 'ausente' (sin dato)
 * Nunca devuelve 0 por falta de dato: sin valor → `valor: null` y `causa`.
 */
export function evaluarCifra(kpiId, fila, snapshot, opc = {}) {
  const base = { kpi_id: kpiId, valor: null, unidad: null, n: null, rango: null, estado: 'ausente', causa: null, causaCorta: null, avisos: [], fuentes: [] };
  if (!fila || typeof fila !== 'object') {
    return { ...base, causa: snapshot ? `la foto del ${snapshot.fecha || 'día'} no incluye «${NOMBRE_KPI[kpiId] || kpiId}»` : 'no hay cifras guardadas para este día' };
  }
  const valor = fila.valor === undefined ? null : fila.valor;
  const horasExtra = opc.relojActivo ? edadSnapshotH(snapshot, opc.ahora) || 0 : 0;
  const fuentes = dependenciasDe(kpiId).map((n) => evaluarFuente(n, snapshot && snapshot.fuentes && snapshot.fuentes[n], { umbrales: opc.umbrales, horasExtra }));
  const rojas = fuentes.filter((f) => f.estado === 'rojo');
  const amarillas = fuentes.filter((f) => f.estado === 'amarillo');
  const salida = { ...base, valor, unidad: fila.unidad ?? null, n: Number.isInteger(fila.n) ? fila.n : null, rango: Array.isArray(fila.rango) ? fila.rango : null, fuentes };
  const causas = [];
  const cortas = [];
  if (fila.estado === 'stale') { causas.push('la foto del día marca esta cifra como vieja (desactualizada)'); cortas.push('dato viejo'); }
  for (const f of rojas) { causas.push(f.causa); cortas.push(f.horas !== null ? `${f.etiqueta} ${textoDuracionH(f.horas)}` : `${f.etiqueta} sin lectura`); }
  if (causas.length) return { ...salida, estado: 'tachada', causa: causas.join('; '), causaCorta: cortas.join('; '), avisos: amarillas.map((f) => f.causa) };
  const avisos = amarillas.map((f) => f.causa);
  if (valor === null) {
    const porN = fila.estado === 'gris' ? `datos insuficientes (muestra de ${salida.n ?? '?'})` : 'la foto del día no trae valor';
    return { ...salida, estado: fila.estado === 'gris' ? 'gris' : 'ausente', causa: porN, avisos };
  }
  if (fila.estado === 'gris') return { ...salida, estado: 'gris', causa: `datos insuficientes (muestra de ${salida.n ?? '?'}): todavía no concluye`, avisos };
  if (fila.estado === 'provisional') return { ...salida, estado: 'provisional', causa: 'provisional: incluye compras recientes que todavía pueden reembolsarse', avisos };
  return { ...salida, estado: 'ok', avisos };
}

// ----------------------------------------------------------------------------------------------------------------
// Snapshots diarios
// ----------------------------------------------------------------------------------------------------------------

const RE_FECHA = /^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/;

/** Snapshots válidos (con `fecha` y `filas`), ordenados por fecha ascendente; el más reciente por `generado_en` gana si hay dos del mismo día. */
export function ordenarSnapshots(lista) {
  const porFecha = new Map();
  for (const s of Array.isArray(lista) ? lista : []) {
    if (!s || typeof s !== 'object' || !RE_FECHA.test(s.fecha || '') || !Array.isArray(s.filas)) continue;
    const previo = porFecha.get(s.fecha);
    if (!previo || String(s.generado_en || '') >= String(previo.generado_en || '')) porFecha.set(s.fecha, s);
  }
  return [...porFecha.values()].sort((a, b) => (a.fecha < b.fecha ? -1 : a.fecha > b.fecha ? 1 : 0));
}

export function filaDe(snapshot, kpiId) {
  return (snapshot && Array.isArray(snapshot.filas) ? snapshot.filas : []).find((f) => f && f.kpi_id === kpiId) || null;
}

const KPIS_TABLA = ['gasto_meta', 'impresiones', 'clics_enlace', 'ctr_enlace', 'compras_stripe', 'cpa', 'razon_meta_stripe', 'tasa_reembolso', 'cobertura_atrib'];

/** Una fila de la tabla diaria por snapshot, con cada cifra ya evaluada (tachada/gris/ausente con causa). */
export function filasDiarias(snapshots, opc = {}) {
  const ord = ordenarSnapshots(snapshots);
  return ord.map((s, i) => {
    const ultimo = i === ord.length - 1;
    const ctx = { umbrales: opc.umbrales, ahora: opc.ahora, relojActivo: ultimo && opc.ahora !== undefined };
    const c = {};
    for (const id of KPIS_TABLA) c[id] = evaluarCifra(id, filaDe(s, id), s, ctx);
    const fuentes = FUENTES.map((n) => evaluarFuente(n, s.fuentes && s.fuentes[n], { umbrales: opc.umbrales, horasExtra: ctx.relojActivo ? edadSnapshotH(s, opc.ahora) || 0 : 0 }));
    return {
      fecha: s.fecha, generado_en: s.generado_en || null, run_id: s.run_id || null, sintetico: s.sintetico === true, esUltimo: ultimo,
      fuentes, cifras: c, tachadas: Object.values(c).filter((x) => x.estado === 'tachada').length,
      moneda: monedaDeUnidad(c.gasto_meta.unidad) || monedaDeUnidad(c.cpa.unidad),
    };
  });
}

const USABLES = ['ok', 'gris', 'provisional'];
const usable = (c) => USABLES.includes(c.estado) && Number.isSafeInteger(c.valor);

/**
 * Acumulado de gasto y compras de las filas diarias.
 *  - gasto/compras: suma de los días con cifra usable (tachada o ausente no suma). `completo=false` si algún día no aporta.
 *  - comparables: SOLO los días en que gasto y compras son usables a la vez; de ahí sale el CPA (si un día tiene el gasto tachado
 *    y sus compras no, dividir mezclaría períodos distintos y daría un CPA falso).
 */
export function acumular(filas) {
  let gasto = 0; let compras = 0; let moneda = null; let completo = true; let diasGasto = 0; let diasCompras = 0;
  const excluidos = [];
  const cmp = { gasto: 0, compras: 0, dias: 0 };
  for (const f of filas) {
    const g = f.cifras.gasto_meta;
    const c = f.cifras.compras_stripe;
    const m = monedaDeUnidad(g.unidad);
    const gOk = usable(g) && !(moneda && m && m !== moneda);
    if (usable(g) && !gOk) excluidos.push({ fecha: f.fecha, kpi_id: 'gasto_meta', causa: `moneda distinta (${m}) sin tipo de cambio` });
    else if (!usable(g)) excluidos.push({ fecha: f.fecha, kpi_id: 'gasto_meta', causa: g.causa || 'sin dato' });
    if (!usable(c)) excluidos.push({ fecha: f.fecha, kpi_id: 'compras_stripe', causa: c.causa || 'sin dato' });
    if (gOk) { moneda = moneda || m; gasto += g.valor; diasGasto += 1; } else completo = false;
    if (usable(c)) { compras += c.valor; diasCompras += 1; } else completo = false;
    if (gOk && usable(c)) { cmp.gasto += g.valor; cmp.compras += c.valor; cmp.dias += 1; }
  }
  return {
    gasto: diasGasto ? { monto: gasto, moneda } : null,
    compras: diasCompras ? compras : null,
    comparables: { gasto: cmp.dias && moneda ? { monto: cmp.gasto, moneda } : null, compras: cmp.dias ? cmp.compras : null, dias: cmp.dias },
    completo, excluidos, dias: filas.length,
  };
}

/** CPA = gasto / compras, entero half-even. Sin compras NO hay CPA (null, no 0). */
export function cpaAcumulado(gasto, compras) {
  const g = dineroValido(gasto);
  if (!g || !Number.isSafeInteger(compras) || compras <= 0) return null;
  const m = dividirRedondeado(g.monto, compras);
  return m === null ? null : { monto: m, moneda: g.moneda };
}

/**
 * Dónde cae un CPA frente al equilibrio y al objetivo. zona: 'objetivo' (≤ obj) · 'equilibrio' (≤ BE) · 'sobre' (> BE) · null (sin comparar).
 * `gris` = no concluyente (pocas compras o poco gasto: criterios de parametros.dashboard.pedidos_min_verde y gasto_min_decision_x_cpa).
 */
export function zonaCpa(cpa, equilibrio, objetivo, opc = {}) {
  const c = dineroValido(cpa);
  const be = dineroValido(equilibrio);
  const ob = dineroValido(objetivo);
  const salida = { zona: null, bpEquilibrio: null, bpObjetivo: null, gris: false, motivoGris: null, causa: null };
  if (!c) { salida.causa = 'sin costo por venta: aún no hay compras (no es 0)'; return salida; }
  if (!be) { salida.causa = 'sin punto de equilibrio con el que comparar (falta la economía de la oferta)'; return salida; }
  if (c.moneda !== be.moneda || (ob && ob.moneda !== c.moneda)) { salida.causa = 'monedas distintas: no se compara sin tipo de cambio registrado'; return salida; }
  salida.bpEquilibrio = proporcionBp(c.monto, be.monto);
  if (ob) salida.bpObjetivo = proporcionBp(c.monto, ob.monto);
  salida.zona = ob && c.monto <= ob.monto ? 'objetivo' : c.monto <= be.monto ? 'equilibrio' : 'sobre';
  const minCompras = aNumero(opc.comprasMin);
  const gastoMinX = aNumero(opc.gastoMinX);
  if (minCompras !== null && Number.isSafeInteger(opc.compras) && opc.compras < minCompras) {
    salida.gris = true; salida.motivoGris = `${opc.compras} compras: hacen falta al menos ${minCompras} para concluir`;
  } else if (gastoMinX !== null && ob && opc.gasto && Number.isSafeInteger(opc.gasto.monto) && opc.gasto.monto < gastoMinX * ob.monto) {
    salida.gris = true; salida.motivoGris = `se gastó menos de ${String(gastoMinX).replace('.', ',')} veces el costo por venta objetivo: todavía no concluye`;
  }
  return salida;
}

// ----------------------------------------------------------------------------------------------------------------
// Topes (empresa/limites.yaml)
// ----------------------------------------------------------------------------------------------------------------

/** Topes de gasto aplicables a una oferta. null = «nada gasta hasta que se fije». */
export function topesDeLimites(limites) {
  const v = (limites && typeof limites === 'object' && limites.valores && typeof limites.valores === 'object') ? limites.valores : (limites && typeof limites === 'object' ? limites : null);
  if (!v) return null;
  const ent = (k) => (Number.isSafeInteger(v[k]) ? v[k] : null);
  return {
    moneda: typeof v.moneda_limites === 'string' ? v.moneda_limites : null,
    diario: ent('gasto_diario_por_oferta'),
    total: ent('gasto_total_test_por_oferta'),
    perdida: ent('perdida_max_test_por_oferta'),
  };
}

/** Uso de un tope: {estado:'sin_tope'|'sin_gasto'|'moneda_distinta'|'ok', bp, zona:'ok'|'aviso'|'rojo'}. */
export function usoDeTope(gasto, tope, monedaTope, umbrales = {}) {
  const g = dineroValido(gasto);
  if (!Number.isSafeInteger(tope) || tope <= 0) return { estado: 'sin_tope', bp: null, zona: null };
  if (!g) return { estado: 'sin_gasto', bp: null, zona: null };
  if (monedaTope && g.moneda !== monedaTope) return { estado: 'moneda_distinta', bp: null, zona: null };
  const bp = proporcionBp(g.monto, tope);
  const amarilla = aNumero(umbrales.amarillaPct);
  const roja = aNumero(umbrales.rojaPct) ?? 100;
  const zona = bp >= roja * 100 ? 'rojo' : amarilla !== null && bp >= amarilla * 100 ? 'aviso' : 'ok';
  return { estado: 'ok', bp, zona };
}

// ----------------------------------------------------------------------------------------------------------------
// Decisiones de D8 (decisiones.jsonl, esquema «Decisión de D8»)
// ----------------------------------------------------------------------------------------------------------------

export const FAMILIAS = {
  G: { id: 'G', titulo: 'Frenos de seguridad', corto: 'Frenos de seguridad', ayuda: 'Se aplican primero: pausa general, topes de gasto, falta de datos para saber qué anuncio vende y salud de los datos.' },
  K: { id: 'K', titulo: 'Pausar un anuncio', corto: 'Pausar', ayuda: 'Pausa un anuncio que gastó sin vender, siempre que la medición sea fiable y ya hayan pasado los primeros días.' },
  M: { id: 'M', titulo: 'Mantener', corto: 'Mantener', ayuda: 'Seguir sin tocar: falta evidencia, es muy pronto para juzgar o el resultado está en zona dudosa.' },
  E: { id: 'E', titulo: 'Escalar (subir presupuesto)', corto: 'Escalar', ayuda: 'Propuesta de subir el presupuesto de lo que funciona. Solo si la oferta está validada y tú la firmas.' },
};
const FAMILIA_POR_ACCION = { MATAR: 'K', SEGUIR: 'M', ESCALAR: 'E', INCONCLUSO: 'G', BLOQUEADO: 'G' };

/** Familia de una decisión: por la letra de `regla` (G1, K1, M2…); si falta, por la acción (docs/08 §4.1). */
export function familiaDeRegla(regla, accion) {
  const l = typeof regla === 'string' ? regla.trim().charAt(0).toUpperCase() : '';
  if (FAMILIAS[l]) return l;
  if (l === 'F') return 'M'; // FT (fatiga) solo genera pedidos a D6: no toca el anuncio vivo
  return FAMILIA_POR_ACCION[accion] || null;
}

export function tonoAccion(accion) {
  return { MATAR: 'error', BLOQUEADO: 'error', INCONCLUSO: 'aviso', ESCALAR: 'info', SEGUIR: 'neutro' }[accion] || 'neutro';
}

/** Si la acción se ejecutó de verdad (ejecutada=true: aplicada en Meta y verificada). */
export function etiquetaEjecucion(d) {
  if (d.ejecutada === true) return { texto: 'ejecutada y verificada', tono: 'ok', ejecutada: true };
  if (d.accion === 'SEGUIR') return { texto: 'sin efecto (se mantiene)', tono: 'neutro', ejecutada: false };
  if (d.accion === 'BLOQUEADO') return { texto: 'bloqueada: no se gasta', tono: 'error', ejecutada: false };
  return { texto: 'propuesta: no ejecutada', tono: 'aviso', ejecutada: false };
}

export function normalizarDecisiones(lista) {
  const salida = [];
  for (const d of Array.isArray(lista) ? lista : []) {
    if (!d || typeof d !== 'object' || typeof d.accion !== 'string') continue;
    const ev = d.evidencia && typeof d.evidencia === 'object' ? d.evidencia : {};
    salida.push({
      id: typeof d.decision_id === 'string' ? d.decision_id : null,
      ts: d.ts || d.lectura_ts || null,
      lectura_ts: d.lectura_ts || null,
      familia: familiaDeRegla(d.regla, d.accion),
      regla: typeof d.regla === 'string' ? d.regla : null,
      codigo: typeof d.codigo === 'string' ? d.codigo : null,
      accion: d.accion,
      conocida: ACCIONES_DECISION.includes(d.accion),
      objeto_tipo: d.objeto_tipo || null,
      objeto_id: d.objeto_id || null,
      nivel: d.nivel || null,
      gate: d.gate || null,
      version_reglas: d.version_reglas || null,
      hash_parametros: typeof d.hash_parametros === 'string' ? d.hash_parametros : null,
      ejecutada: d.ejecutada === true,
      ejecucion: etiquetaEjecucion(d),
      explicacion: typeof d.explicacion === 'string' ? d.explicacion : '',
      evidencia: { gasto: dineroValido(ev.gasto), clics: Number.isSafeInteger(ev.clics) ? ev.clics : null, compras: Number.isSafeInteger(ev.compras) ? ev.compras : null, p: aNumero(ev.p_cpa_menor_equilibrio) },
      sintetico: d.sintetico === true,
    });
  }
  return salida.sort((a, b) => String(b.ts || '').localeCompare(String(a.ts || '')));
}

export function resumenDecisiones(decisiones) {
  const porFamilia = { G: 0, K: 0, M: 0, E: 0 };
  let ejecutadas = 0;
  for (const d of decisiones) {
    if (d.familia && porFamilia[d.familia] !== undefined) porFamilia[d.familia] += 1;
    if (d.ejecutada) ejecutadas += 1;
  }
  return { total: decisiones.length, porFamilia, ejecutadas, sinEjecutar: decisiones.length - ejecutadas };
}

// ----------------------------------------------------------------------------------------------------------------
// Órdenes de presupuesto
// ----------------------------------------------------------------------------------------------------------------

const TONO_ORDEN = { ejecutada: 'ok', aprobada: 'info', propuesta: 'aviso', bloqueada: 'error', rechazada: 'error' };

export function normalizarOrdenes(lista) {
  const salida = [];
  for (const o of Array.isArray(lista) ? lista : []) {
    if (!o || typeof o !== 'object' || typeof o.orden_id !== 'string') continue;
    const ver = o.verificacion_post && typeof o.verificacion_post === 'object' ? o.verificacion_post : null;
    salida.push({
      orden_id: o.orden_id, ts: o.ts || null, emisor: o.emisor || null, accion: o.accion || null,
      objeto: o.objeto && typeof o.objeto === 'object' ? { tipo: o.objeto.tipo || null, nombre: o.objeto.nombre || null, id_meta: o.objeto.id_meta || null } : null,
      antes: dineroValido(o.antes), despues: dineroValido(o.despues),
      delta_pct: aNumero(o.delta_pct), regla_id: o.regla_id || null, estado: o.estado || null, tono: TONO_ORDEN[o.estado] || 'neutro',
      ejecutor: o.ejecutor || null, gate: o.gate && typeof o.gate === 'object' ? { accion_gate: o.gate.accion_gate || null, nivel: o.gate.nivel || null, gate: o.gate.gate || null } : null,
      aprobado_por: o.aprobado_por && typeof o.aprobado_por === 'object' ? { tipo: o.aprobado_por.tipo || null, id: o.aprobado_por.id || null } : null,
      nota: o.evidencia && typeof o.evidencia === 'object' && typeof o.evidencia.nota === 'string' ? o.evidencia.nota : '',
      verificada: ver ? ver.leido_de_meta === true : null, version_reglas: o.version_reglas || null, hash_parametros: typeof o.hash_parametros === 'string' ? o.hash_parametros : null,
      idempotency_key: typeof o.idempotency_key === 'string' ? o.idempotency_key : null, horas_desde_ultimo_aumento: aNumero(o.horas_desde_ultimo_aumento),
      sintetico: o.sintetico === true,
    });
  }
  return salida.sort((a, b) => String(b.ts || '').localeCompare(String(a.ts || '')));
}

// ----------------------------------------------------------------------------------------------------------------
// Veredicto de la oferta (veredicto_oferta.json, backbone 5.9)
// ----------------------------------------------------------------------------------------------------------------

export const VEREDICTOS = {
  VALIDADA: { tono: 'ok', texto: 'Mirando solo compras ya sin riesgo de reembolso y descontando los reembolsos: el costo por venta queda por debajo del punto de equilibrio, con evidencia suficiente.' },
  PROMETEDORA: { tono: 'info', texto: 'Cumple casi todo; el costo por venta está entre el objetivo y el punto de equilibrio reales.' },
  FALLIDA: { tono: 'error', texto: 'Se gastó lo suficiente y la probabilidad de que el costo por venta esté por debajo del punto de equilibrio es demasiado baja: no hay negocio.' },
  INCONCLUSA: { tono: 'aviso', texto: 'Todavía no se puede decidir: faltan compras, días con datos o que maduren las compras recientes.' },
};
export const RECOMENDACIONES = { seguir_test: 'seguir la prueba', escalar: 'escalar (subir presupuesto; necesita tu firma)', cerrar: 'cerrar la oferta', extender_test: 'extender la prueba una vez', corregir_antes: 'corregir antes de seguir' };

export function modeloVeredicto(v, parametros) {
  if (!v || typeof v !== 'object' || typeof v.estado !== 'string') return null;
  const ev = v.evidencia && typeof v.evidencia === 'object' ? v.evidencia : {};
  const info = VEREDICTOS[v.estado] || { tono: 'neutro', texto: 'Resultado que el panel no reconoce.' };
  const garantia = Number.isSafeInteger(ev.garantia_dias) ? ev.garantia_dias : null;
  const madurez = Number.isSafeInteger(ev.madurez_dias) ? ev.madurez_dias : null;
  const requisitos = [];
  const comprasMin = aNumero(parametro(parametros, 'veredicto.compras_min'));
  const diasMin = aNumero(parametro(parametros, 'veredicto.dias_min'));
  const reembMax = aNumero(parametro(parametros, 'veredicto.reembolso_max_pct'));
  if (comprasMin !== null && Number.isSafeInteger(ev.compras_netas)) requisitos.push({ id: 'compras', etiqueta: 'Compras netas', actual: ev.compras_netas, minimo: comprasMin, cumple: ev.compras_netas >= comprasMin, sentido: 'min' });
  if (diasMin !== null && Number.isSafeInteger(ev.dias_con_datos)) requisitos.push({ id: 'dias', etiqueta: 'Días con datos', actual: ev.dias_con_datos, minimo: diasMin, cumple: ev.dias_con_datos >= diasMin, sentido: 'min' });
  const reemb = aNumero(ev.reembolso_pct);
  if (reembMax !== null && reemb !== null) requisitos.push({ id: 'reembolsos', etiqueta: 'Reembolsos', actual: reemb, minimo: reembMax, cumple: reemb <= reembMax, sentido: 'max' });
  return {
    estado: v.estado, tono: info.tono, descripcion: info.texto, ts: v.ts || null, version: v.version || null,
    regla: v.regla && typeof v.regla === 'object' ? { id: v.regla.id || null, definicion: v.regla.definicion || null, version_reglas: v.regla.version_reglas || null } : null,
    recomendacion: v.recomendacion || null, recomendacionTexto: RECOMENDACIONES[v.recomendacion] || null, gate: v.gate || null,
    p: aNumero(v.p), estabilidad: v.estabilidad && typeof v.estabilidad === 'object' ? { tolerancia_pct: v.estabilidad.tolerancia_pct ?? null, estable: v.estabilidad.estable === true } : null,
    evidencia: {
      fuente_compras: ev.fuente_compras || null, compras_brutas: ev.compras_brutas ?? null, reembolsos: ev.reembolsos ?? null, compras_netas: ev.compras_netas ?? null,
      compras_meta_referencia: ev.compras_meta_referencia ?? null, gasto: dineroValido(ev.gasto), cpa_neto: dineroValido(ev.cpa_neto), cpa_objetivo: dineroValido(ev.cpa_objetivo),
      mc_real: dineroValido(ev.mc_real), razon_ms: aNumero(ev.razon_ms), reembolso_pct: reemb,
    },
    madurez: { garantia, margen: garantia !== null && madurez !== null ? madurez - garantia : null, madurezDias: madurez, cohorteMaduraHasta: ev.cohorte_madura_hasta || null, diasConDatos: ev.dias_con_datos ?? null },
    requisitos, sintetico: v.sintetico === true,
  };
}

// ----------------------------------------------------------------------------------------------------------------
// Sparklines (SVG propio; aquí solo la geometría)
// ----------------------------------------------------------------------------------------------------------------

/**
 * Geometría de una sparkline. `serie` = [{x:etiqueta, y:number|null, estado?}]. Los huecos (null/tachada) cortan la línea.
 * Devuelve {segmentos:['M x y L x y …'], puntos:[{x,y,etiqueta,valor,estado}], min, max, n}; sin ≥1 punto numérico, puntos=[].
 */
export function geometriaSparkline(serie, { ancho = 120, alto = 32, margen = 3 } = {}) {
  const validos = serie.map((s, i) => ({ ...s, i })).filter((s) => typeof s.y === 'number' && Number.isFinite(s.y));
  if (!validos.length) return { segmentos: [], puntos: [], min: null, max: null, n: 0 };
  let min = Math.min(...validos.map((s) => s.y));
  let max = Math.max(...validos.map((s) => s.y));
  if (min === max) { min -= 1; max += 1; } // serie plana: línea al centro
  const dx = serie.length > 1 ? (ancho - 2 * margen) / (serie.length - 1) : 0;
  const px = (i) => (serie.length > 1 ? margen + dx * i : ancho / 2);
  const py = (y) => margen + (alto - 2 * margen) * (1 - (y - min) / (max - min));
  const r = (n) => Math.round(n * 100) / 100;
  const puntos = validos.map((s) => ({ x: r(px(s.i)), y: r(py(s.y)), etiqueta: s.x, valor: s.y, estado: s.estado || 'ok' }));
  const segmentos = [];
  let actual = [];
  serie.forEach((s, i) => {
    if (typeof s.y === 'number' && Number.isFinite(s.y) && s.estado !== 'tachada') actual.push(`${r(px(i))} ${r(py(s.y))}`);
    else if (actual.length) { segmentos.push(actual); actual = []; }
  });
  if (actual.length) segmentos.push(actual);
  return {
    segmentos: segmentos.filter((s) => s.length > 1).map((s) => `M${s.join(' L')}`),
    puntos, min: validos.length ? Math.min(...validos.map((s) => s.y)) : null, max: Math.max(...validos.map((s) => s.y)), n: validos.length,
  };
}

/** Serie numérica para sparkline desde filas diarias: gasto, compras o CPA (en unidad menor / unidades). */
export function serieDe(filas, clave) {
  return filas.map((f) => {
    const c = f.cifras[clave];
    const y = c && c.estado !== 'ausente' && aNumero(c.valor) !== null ? aNumero(c.valor) : null;
    return { x: f.fecha, y, estado: c ? c.estado : 'ausente', causa: c && c.estado === 'tachada' ? (c.causaCorta || c.causa) : null };
  });
}

// ----------------------------------------------------------------------------------------------------------------
// Modelo completo de la pantalla
// ----------------------------------------------------------------------------------------------------------------

/** Economía mínima desde 03-oferta/economia.json (cpa_be, cpa_obj, aov, mc). */
export function economiaDe(e) {
  if (!e || typeof e !== 'object') return null;
  const o = { cpa_be: dineroValido(e.cpa_be_visto) || dineroValido(e.cpa_be), cpa_obj: dineroValido(e.cpa_obj), aov: dineroValido(e.aov), mc: dineroValido(e.mc) };
  return o.cpa_be || o.cpa_obj ? o : null;
}

/** Normaliza lo que entrega GET /operacion/<id> (tolera claves ausentes). */
export function normalizarOperacion(datos) {
  const d = datos && typeof datos === 'object' ? datos : {};
  return {
    kpi_dia: Array.isArray(d.kpi_dia) ? d.kpi_dia : [],
    decisiones: Array.isArray(d.decisiones) ? d.decisiones : [],
    ordenes: Array.isArray(d.ordenes) ? d.ordenes : [],
    veredicto: d.veredicto && typeof d.veredicto === 'object' ? d.veredicto : null,
  };
}

/**
 * Todo lo que pinta la pantalla de una oferta.
 * @param entrada {operacion, economia, limites, parametros, conciliacion}
 * @param opc {ahora: Date|number}
 */
export function modeloOperacion(entrada, opc = {}) {
  const op = normalizarOperacion(entrada && entrada.operacion);
  const umbrales = umbralesDeFrescura(entrada && entrada.parametros);
  const filas = filasDiarias(op.kpi_dia, { umbrales, ahora: opc.ahora });
  const acum = acumular(filas);
  const economia = economiaDe(entrada && entrada.economia);
  const topes = topesDeLimites(entrada && entrada.limites);
  const ultima = filas.length ? filas[filas.length - 1] : null;
  const umbralTope = { amarillaPct: parametro(entrada && entrada.parametros, 'finanzas.gasto_vs_tope_amarilla_pct'), rojaPct: parametro(entrada && entrada.parametros, 'finanzas.gasto_vs_tope_roja_pct') };
  const gastoHoy = ultima && Number.isSafeInteger(ultima.cifras.gasto_meta.valor) && ultima.cifras.gasto_meta.estado !== 'tachada' && ultima.cifras.gasto_meta.estado !== 'ausente'
    ? { monto: ultima.cifras.gasto_meta.valor, moneda: monedaDeUnidad(ultima.cifras.gasto_meta.unidad) || (acum.gasto && acum.gasto.moneda) } : null;
  const cpa = cpaAcumulado(acum.comparables.gasto, acum.comparables.compras);
  const zona = zonaCpa(cpa, economia && economia.cpa_be, economia && economia.cpa_obj, {
    comprasMin: parametro(entrada && entrada.parametros, 'dashboard.pedidos_min_verde'),
    gastoMinX: parametro(entrada && entrada.parametros, 'dashboard.gasto_min_decision_x_cpa'),
    compras: acum.comparables.compras, gasto: acum.comparables.gasto,
  });
  const decisiones = normalizarDecisiones(op.decisiones);
  const veredicto = modeloVeredicto(op.veredicto, entrada && entrada.parametros);
  const concil = entrada && entrada.conciliacion && typeof entrada.conciliacion === 'object' ? entrada.conciliacion : null;
  return {
    hayKpi: filas.length > 0,
    filas, acumulado: acum, ultima, moneda: (acum.gasto && acum.gasto.moneda) || (ultima && ultima.moneda) || null,
    gastoHoy, cpa, cpaParcial: acum.comparables.dias < acum.dias, zonaCpa: zona, economia, topes, umbralTope,
    usoDiario: topes ? usoDeTope(gastoHoy, topes.diario, topes.moneda, umbralTope) : { estado: 'sin_tope', bp: null, zona: null },
    usoTotal: topes ? usoDeTope(acum.gasto, topes.total, topes.moneda, umbralTope) : { estado: 'sin_tope', bp: null, zona: null },
    cobertura: ultima && ultima.cifras.cobertura_atrib.estado !== 'ausente' ? ultima.cifras.cobertura_atrib : null,
    coberturaConciliacionBp: concil && Number.isSafeInteger(concil.cobertura_adid_bp) ? concil.cobertura_adid_bp : null,
    umbralCoberturaPct: aNumero(parametro(entrada && entrada.parametros, 'testeo.cobertura_adid_min_pct')),
    series: { gasto: serieDe(filas, 'gasto_meta'), compras: serieDe(filas, 'compras_stripe'), cpa: serieDe(filas, 'cpa') },
    decisiones, resumenDecisiones: resumenDecisiones(decisiones),
    ordenes: normalizarOrdenes(op.ordenes), veredicto,
    sintetico: filas.some((f) => f.sintetico) || decisiones.some((d) => d.sintetico) || (veredicto && veredicto.sintetico) === true,
  };
}

/** Comandos exactos (copiables) para llenar cada bloque vacío de la pantalla (README de datos, departamentos/09 §4). */
export function comandosOperacion(ofertaId, fecha) {
  const id = /^OF-\d{6}-\d{2}$/.test(ofertaId || '') ? ofertaId : 'OF-AAAAMM-NN';
  const f = RE_FECHA.test(fecha || '') ? fecha : 'AAAA-MM-DD';
  return {
    kpi: `.venv/bin/python -m datos.kpi --oferta ${id} --fecha ${f}`,
    decisiones: `.venv/bin/python -m engine.d8 reglas --oferta ${id}`,
    veredicto: `.venv/bin/python -m engine.d8 veredicto --oferta ${id}`,
    ordenes: `.venv/bin/python -m engine.d8 reglas --oferta ${id}`,
  };
}

// ----------------------------------------------------------------------------------------------------------------
// Lenguaje de negocio: decisiones y órdenes en una frase (la regla técnica va aparte, en el detalle)
// ----------------------------------------------------------------------------------------------------------------

const NOMBRE_OBJETO = { anuncio: 'el anuncio', campana: 'la campaña', conjunto: 'el conjunto de anuncios', adset: 'el conjunto de anuncios', oferta: 'la oferta', celda: 'la celda de prueba', creativo: 'el creativo' };

/** Id largo de Meta (15+ dígitos) → «…0003»; los ids cortos o con letras se dejan tal cual. */
export function idCorto(id) {
  const t = String(id ?? '');
  return t.length > 14 && /^\d+$/.test(t) ? `…${t.slice(-6)}` : t;
}

/** «3,4×» a partir de un gasto y un CPA de equilibrio (enteros en unidad menor). null si no hay con qué comparar. */
export function multiploDeEquilibrio(gasto, cpaBe) {
  const g = dineroValido(gasto);
  const be = dineroValido(cpaBe);
  if (!g || !be || g.moneda !== be.moneda) return null;
  const bp = proporcionBp(g.monto, be.monto);
  if (bp === null) return null;
  return `${String(Math.round(bp / 1000) / 10).replace('.', ',')}×`;
}

const pctDeP = (p) => (p === null ? null : `${String(Math.round(p * 1000) / 10).replace('.', ',')} %`);

/**
 * Una decisión del motor en lenguaje humano. Devuelve {frase, icono, tono, accionHumana, objeto, ejecutadaTexto, porque, pidePermiso}.
 * `frase` es lo primero que lee el dueño; la regla (G1, K1…), el código y la evidencia cruda se muestran aparte, en el detalle técnico.
 * @param d    decisión normalizada (normalizarDecisiones)
 * @param ctx  {cpaBe: dinero de equilibrio, formatoDinero(monto, moneda) → texto}
 */
export function describirDecision(d, ctx = {}) {
  const fd = ctx.formatoDinero || ((m, c) => `${m} ${c}`);
  const objeto = `${NOMBRE_OBJETO[d.objeto_tipo] || 'el objeto'}${d.objeto_id ? ` ${idCorto(d.objeto_id)}` : ''}`;
  const e = d.evidencia || {};
  const gasto = e.gasto ? fd(e.gasto.monto, e.gasto.moneda) : null;
  const mult = multiploDeEquilibrio(e.gasto, ctx.cpaBe);
  const cod = String(d.codigo || '').toLowerCase();
  const ya = d.ejecutada === true;
  const pCorto = pctDeP(e.p);
  let frase = null;
  let icono = 'info';
  let tono = 'neutro';
  let accionHumana = 'Sin acción';
  let pidePermiso = false;
  switch (d.accion) {
    case 'MATAR': {
      icono = 'pausa'; tono = 'aviso'; accionHumana = ya ? 'Pausado' : 'Pausa propuesta';
      const verbo = ya ? 'Se pausó' : 'Se propone pausar';
      if (/sin_compras/.test(cod)) frase = `${verbo} ${objeto} por 0 compras${mult ? ` tras gastar ${mult} el máximo que se puede pagar por una venta` : gasto ? ` tras gastar ${gasto}` : ''}.`;
      else if (/cpa_peor|peor_que/.test(cod)) frase = `${verbo} ${objeto}: su costo por venta supera el punto de equilibrio${pCorto ? ` (solo ${pCorto} de probabilidad de ser rentable)` : ''}.`;
      else frase = `${verbo} ${objeto}.`;
      break;
    }
    case 'SEGUIR': {
      icono = 'check'; tono = 'neutro'; accionHumana = 'Se mantiene';
      const sujeto = `Se mantiene ${objeto}`;
      if (/ventana/.test(cod)) frase = `${sujeto}: es muy pronto para juzgarlo (durante los primeros días no se evalúa el rendimiento).`;
      else if (/sin_evidencia/.test(cod)) frase = `${sujeto}: todavía no hay evidencia suficiente para decidir${gasto ? ` (gastó ${gasto})` : ''}.`;
      else if (/tracking/.test(cod)) frase = `${sujeto}: el seguimiento de compras no es fiable y no se decide con datos dudosos.`;
      else if (/prometedora/.test(cod)) frase = `${sujeto}: va bien, pero la evidencia aún no es concluyente.`;
      else if (/zona_gris/.test(cod)) frase = `${sujeto}: la evidencia aún no dice si su costo por venta está por encima o por debajo del punto de equilibrio.`;
      else frase = `${sujeto}.`;
      break;
    }
    case 'ESCALAR': {
      icono = 'escalar'; tono = 'info'; accionHumana = 'Escalado propuesto'; pidePermiso = true;
      frase = `El sistema propone escalar ${objeto} (subirle el presupuesto)${e.compras !== null && e.compras !== undefined ? `: ${e.compras} compras` : ''}${pCorto ? ` y ${pCorto} de probabilidad de que el costo por venta esté por debajo del punto de equilibrio` : ''}. Espera tu firma.`;
      break;
    }
    case 'INCONCLUSO': {
      icono = 'reloj-alerta'; tono = 'aviso'; accionHumana = 'Sin veredicto';
      if (/tope_sin_clics/.test(cod)) frase = `La prueba llegó a su tope de gasto sin clics: ${objeto} no genera visitas.`;
      else if (/datos_dudosos/.test(cod)) frase = 'La prueba llegó a su tope de gasto con datos dudosos: no se puede dar un veredicto.';
      else frase = `La prueba llegó a su tope de gasto${gasto ? ` (${gasto})` : ''} sin un veredicto claro.`;
      break;
    }
    case 'BLOQUEADO': {
      icono = 'candado'; tono = 'error'; accionHumana = 'Bloqueado';
      if (/sin_limites/.test(cod)) frase = 'No se decide ni se gasta: faltan los topes de gasto en tus límites.';
      else if (/moneda/.test(cod)) frase = 'No se decide: la moneda de los datos no coincide con la de la economía de la oferta.';
      else if (/datos_invalidos/.test(cod)) frase = 'No se decide: los datos son inconsistentes (cifras negativas o más compras que clics).';
      else if (/pull|incompleto/.test(cod)) frase = 'No se decide el rendimiento: la lectura de Meta llegó incompleta o con retraso.';
      else if (/cobertura|ciego/.test(cod)) frase = 'No se decide el rendimiento: hay pocas compras ligadas a un anuncio concreto, así que no se sabe cuál vende.';
      else frase = 'El sistema frenó la decisión por seguridad.';
      break;
    }
    default:
      frase = null;
  }
  const porque = d.explicacion || null;
  if (!frase) frase = porque || `Decisión «${d.accion}» (regla ${d.regla || '—'}).`;
  return { frase, icono, tono, accionHumana, objeto, porque, pidePermiso, ejecutada: ya };
}

const ESTADO_ORDEN = {
  ejecutada: ['Ejecutada y verificada', 'ok'], aprobada: ['Aprobada, falta ejecutarla', 'info'], propuesta: ['Propuesta: espera aprobación', 'aviso'],
  bloqueada: ['Bloqueada', 'error'], rechazada: ['Rechazada', 'error'],
};

/** Una orden de presupuesto en una frase: «Subir el presupuesto de X de 27,60 € a 33,12 € (+20 %)». */
export function describirOrden(o, formatoDinero = (m, c) => `${m} ${c}`) {
  const nombre = o.objeto && (o.objeto.nombre || o.objeto.id_meta) ? (o.objeto.nombre || o.objeto.id_meta) : 'el objeto';
  const tipo = o.objeto && o.objeto.tipo ? `${NOMBRE_OBJETO[o.objeto.tipo] ? NOMBRE_OBJETO[o.objeto.tipo].replace(/^(el|la) /, '') : o.objeto.tipo} ` : '';
  const antes = o.antes ? formatoDinero(o.antes.monto, o.antes.moneda) : null;
  const despues = o.despues ? formatoDinero(o.despues.monto, o.despues.moneda) : null;
  const delta = o.delta_pct === null || o.delta_pct === undefined ? null : `${o.delta_pct > 0 ? '+' : ''}${String(o.delta_pct).replace('.', ',')} %`;
  let frase;
  if (o.accion === 'aumentar') frase = `Subir el presupuesto de ${tipo}${nombre}${antes && despues ? ` de ${antes} a ${despues}` : ''}${delta ? ` (${delta})` : ''}`;
  else if (o.accion === 'reducir') frase = `Bajar el presupuesto de ${tipo}${nombre}${antes && despues ? ` de ${antes} a ${despues}` : ''}${delta ? ` (${delta})` : ''}`;
  else if (o.accion === 'mantener') frase = `Mantener el presupuesto de ${tipo}${nombre}${despues ? ` en ${despues}` : ''}`;
  else frase = `Orden «${o.accion || '—'}» sobre ${nombre}`;
  const [estadoTexto, estadoTono] = ESTADO_ORDEN[o.estado] || [o.estado || 'Sin estado', 'neutro'];
  return { frase: `${frase}.`, estadoTexto, estadoTono, antes, despues, delta };
}

/**
 * Lo que requiere atención en la pantalla de Operación, de más a menos urgente.
 * @returns [{tono:'critico'|'aviso'|'info', titulo, detalle?, accion?:{texto, ruta}}]
 */
export function atencionOperacion(m, { ofertaId, formatoDinero = (x, c) => `${x} ${c}` } = {}) {
  const items = [];
  const u = m.ultima;
  const diasTachados = (m.filas || []).filter((f) => f.tachadas);
  if (u && u.tachadas) {
    items.push({ tono: 'critico', titulo: `${u.tachadas} ${u.tachadas === 1 ? 'cifra del último día está tachada' : 'cifras del último día están tachadas'}`, detalle: 'Su fuente de datos está en rojo: no decidas con ellas hasta que se actualice.' });
  } else if (diasTachados.length) {
    const f = diasTachados[diasTachados.length - 1];
    items.push({ tono: 'aviso', titulo: `Hay cifras tachadas de días anteriores (${f.fecha.slice(8)}/${f.fecha.slice(5, 7)})`, detalle: 'Su fuente de datos estaba en rojo: el acumulado no las cuenta y el costo por venta solo usa los días comparables.' });
  }
  if (m.veredicto) {
    const v = m.veredicto;
    if (v.estado === 'FALLIDA') items.push({ tono: 'critico', titulo: 'Veredicto FALLIDA: no hay negocio con esta oferta', detalle: 'El sistema recomienda cerrar la oferta o corregirla antes de gastar más.', accion: ofertaId ? { texto: 'Ver la oferta', ruta: `#/oferta/${ofertaId}` } : undefined });
    else if (v.recomendacion === 'escalar' || v.estado === 'VALIDADA') items.push({ tono: 'info', titulo: `Veredicto ${v.estado}: el sistema propone escalar (subir el presupuesto)`, detalle: 'Escalar es decisión tuya: necesita tu firma.', accion: ofertaId ? { texto: 'Ver la oferta', ruta: `#/oferta/${ofertaId}` } : undefined });
  }
  const escalar = m.decisiones.filter((d) => d.accion === 'ESCALAR' && !d.ejecutada);
  if (escalar.length) items.push({ tono: 'info', titulo: `El sistema propone escalar ${escalar.length === 1 ? 'una campaña' : `${escalar.length} campañas`}`, detalle: 'Espera tu firma: el panel no la da por ti.', accion: ofertaId ? { texto: 'Ver cómo firmar', ruta: `#/oferta/${ofertaId}` } : undefined });
  const bloqueos = m.decisiones.filter((d) => d.accion === 'BLOQUEADO');
  if (bloqueos.length) items.push({ tono: 'aviso', titulo: `El sistema frenó ${bloqueos.length === 1 ? 'una decisión' : `${bloqueos.length} decisiones`} por seguridad`, detalle: describirDecision(bloqueos[0], { formatoDinero }).frase });
  if (!m.topes || (m.topes.diario === null && m.topes.total === null)) {
    items.push({ tono: 'aviso', titulo: 'Los topes de gasto aún no están fijados', detalle: 'Mientras sigan sin fijar, ninguna operación puede gastar. Lo fijas tú en los límites.', accion: { texto: 'Abrir límites', ruta: '#/parametros' } });
  } else {
    for (const [uso, que] of [[m.usoDiario, 'el tope diario'], [m.usoTotal, 'el tope total del test']]) {
      if (uso && uso.zona === 'rojo') items.push({ tono: 'critico', titulo: `El gasto llegó a ${que}`, detalle: 'No se puede subir el gasto sin tu firma.' });
      else if (uso && uso.zona === 'aviso') items.push({ tono: 'aviso', titulo: `El gasto se acerca a ${que}` });
    }
  }
  if (m.umbralCoberturaPct !== null) {
    const c = m.cobertura && aNumero(m.cobertura.valor) !== null ? aNumero(m.cobertura.valor) : (m.coberturaConciliacionBp !== null ? m.coberturaConciliacionBp / 100 : null);
    if (c !== null && c < m.umbralCoberturaPct) items.push({ tono: 'critico', titulo: `Pocas compras se pueden ligar a un anuncio (${String(c).replace('.', ',')} %)`, detalle: `Con menos de ${String(m.umbralCoberturaPct).replace('.', ',')} % el sistema decide a ciegas: no pausa ni escala anuncios.` });
  }
  if (m.zonaCpa && m.zonaCpa.zona === 'sobre' && !m.zonaCpa.gris) items.push({ tono: 'aviso', titulo: 'El costo por venta real supera el punto de equilibrio', detalle: 'Cada compra cuesta más en anuncios de lo que deja: conviene revisar antes de gastar más.' });
  const req = m.veredicto && m.veredicto.requisitos.find((r) => r.id === 'reembolsos');
  if (req && !req.cumple) items.push({ tono: 'aviso', titulo: 'Los reembolsos superan el máximo para validar', detalle: `Van ${String(req.actual).replace('.', ',')} % frente a un máximo de ${String(req.minimo).replace('.', ',')} %.` });
  const orden = { critico: 0, aviso: 1, info: 2 };
  return items.sort((a, b) => orden[a.tono] - orden[b.tono]);
}

// ----------------------------------------------------------------------------------------------------------------
// Ayudas de render compartidas por las cinco pantallas de U4 (reciben `ui`/`fmt` por inyección: este archivo no importa DOM)
// ----------------------------------------------------------------------------------------------------------------

import { ESTILOS_P5 } from './estilos-p5.js';
export { ESTILOS_P5 };

/** Instala el CSS de las cinco pantallas (hoja construida por CSSOM: la CSP no admite <style>). Seguro de llamar en cada render. */
export function instalarEstilos(ui) {
  return ui && typeof ui.instalarEstilos === 'function' ? ui.instalarEstilos('u4', ESTILOS_P5) : false;
}

/** Ayudas de vista: cifra tachada con causa, medidor de tope, avisos con icono y estado vacío con pasos (comandos copiables). */
export function ayudasVista(ui, fmt) {
  const { el } = ui;

  /** El valor viejo tachado + su causa VISIBLE (no solo en tooltip). */
  function cifraTachada(textoValor, causa, causaLarga) {
    return el('span', { class: 'cifra-tachada', title: causaLarga || causa || '' },
      el('s', { class: 'cifra-vieja' }, textoValor),
      el('span', { class: 'cifra-causa' }, causa ? `(${causa})` : '(cifra no fiable)'));
  }

  /** Cifra evaluada → elemento: ok normal; gris atenuada «pocos datos»; provisional; tachada con causa; ausente «sin dato» con causa. */
  function cifraEl(cifra, formato, { corta = false } = {}) {
    const f = formato || ((v) => String(v));
    if (!cifra || cifra.estado === 'ausente' || cifra.valor === null || cifra.valor === undefined) {
      return el('span', { class: 'cifra-sin-dato', title: cifra && cifra.causa ? cifra.causa : 'sin dato' }, 'sin dato');
    }
    const t = f(cifra.valor);
    if (cifra.estado === 'tachada') return cifraTachada(t, corta && cifra.causaCorta ? cifra.causaCorta : cifra.causa, cifra.causa);
    if (cifra.estado === 'gris') return el('span', { class: 'cifra-gris', title: cifra.causa || '' }, t, ' ', ui.chip('pocos datos', 'neutro', { icono: false }));
    if (cifra.estado === 'provisional') return el('span', { title: cifra.causa || '' }, t, ' ', ui.chip('provisional', 'info', { icono: false }));
    return el('span', { class: 'cifra' }, t);
  }

  /** Medidor de una sola magnitud: la pista es un tono claro de la misma rampa y el relleno lleva la gravedad (acento → aviso → error). */
  function medidor({ bp, zona = 'ok', texto, etiqueta, marca }) {
    const ancho = Math.min(100, Math.max(0, Math.round(bp / 100)));
    return el('div', { class: `p5-medidor zona-${zona}`, role: 'img', 'aria-label': etiqueta || texto },
      el('div', { class: 'p5-medidor__pista' },
        el('div', { class: 'p5-medidor__relleno', style: { width: `${Math.max(bp > 0 ? 2 : 0, ancho)}%` } }),
        marca !== undefined && marca !== null ? el('span', { class: 'p5-medidor__marca', style: { left: `${Math.min(100, Math.max(0, marca))}%` }, title: 'Umbral' }) : null),
      el('span', { class: 'p5-medidor__texto' }, texto));
  }

  /** Barra de uso de un tope (bp). Nunca pinta barra sin tope ni sin gasto: dice por qué. */
  function barraUso(uso, etiqueta) {
    if (!uso || uso.estado === 'sin_tope') return el('span', { class: 'uso-sin-tope' }, ui.chip('sin tope fijado', 'aviso'), 'nada gasta hasta que se fije');
    if (uso.estado === 'sin_gasto') return el('span', { class: 'cifra-sin-dato' }, 'sin gasto leído');
    if (uso.estado === 'moneda_distinta') return el('span', { class: 'cifra-sin-dato' }, 'moneda distinta al tope: no se compara');
    return medidor({ bp: uso.bp, zona: uso.zona, texto: `${fmt.pct(uso.bp)} del tope`, etiqueta: `${etiqueta || 'Uso'}: ${fmt.pct(uso.bp)} del tope` });
  }

  /**
   * Estado vacío con pasos: qué falta y qué hacer (los comandos van en el bloque `comando`, abiertos porque son LA acción de la pantalla).
   * `archivo`/`fuente` (rutas) pasan a un detalle técnico: no se muestran abiertos salvo con el modo técnico.
   * `compacto` (por defecto sí): dentro de una tarjeta/sección; `compacto: false` para el vacío que ocupa toda la pantalla.
   */
  function vacioConComandos(texto, { archivo, pista, comandos = [], fuente, pasos: extra = [], icono: nombreIcono, compacto = true } = {}) {
    const pasos = [...extra, ...comandos.map((c) => ({ texto: String(c.etiqueta || 'Ejecuta este comando').replace(/:\s*$/, ''), comando: c.cmd }))];
    if (!pasos.length) pasos.push({ texto: 'No hay nada que hacer desde aquí: la pantalla se llena sola cuando existan los datos.' });
    const raiz = ui.vacioConPasos({ titulo: texto, explicacion: pista, pasos, icono: nombreIcono || 'caja', compacto });
    const rutas = [archivo, ...(Array.isArray(fuente) ? fuente : (fuente ? [fuente] : []))].filter(Boolean);
    const cuerpo = raiz.querySelector ? raiz.querySelector('.vacio-pasos__cuerpo') : null;
    if (cuerpo && rutas.length) cuerpo.appendChild(ui.detalleTecnico('Dónde se guardan estos datos', el('ul', { class: 'p5-rutas' }, rutas.map((r) => el('li', null, el('code', null, r))))));
    return raiz;
  }

  /** Aviso en caja (info/aviso/error) con icono y texto o nodos. */
  function aviso(tono, ...hijos) {
    const t = tono === 'error' || tono === 'critico' ? 'error' : tono === 'info' ? 'info' : 'aviso';
    const ic = ui.iconoDeTono ? ui.iconoDeTono(t === 'error' ? 'critico' : t) : null;
    return el('div', { class: `p5-aviso p5-aviso--${t}`, role: t === 'error' ? 'alert' : 'note' }, ic ? el('span', { class: 'p5-aviso__icono' }, ui.icono(ic, { tam: 16 })) : null, el('div', { class: 'p5-aviso__texto' }, ...hijos));
  }

  return { cifraTachada, cifraEl, medidor, barraUso, vacioConComandos, aviso };
}
