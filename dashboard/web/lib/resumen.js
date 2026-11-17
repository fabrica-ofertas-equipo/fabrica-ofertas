// lib/resumen.js — lógica pura (datos → modelo de vista) de la pantalla Resumen. Sin DOM: probable con `node --test`.
import { fmt } from '../ui.js';
import { describirEvento, etapaHumana, nombreEtapa, NOMBRE_ETAPA } from './registro.js';
import { resumenBitacora } from './pulido.js';
import { plano as planoRobot, estadoLatido, resultadoSombra } from './robots.js';

export { NOMBRE_ETAPA, nombreEtapa, etapaHumana };

// Entradas = lo que devuelven GET /ofertas, /sistema, /registro, /finanzas, /parametros (CONTRATO §4).

export const FASES = ['borrador', 'en_construccion', 'listo_para_activar', 'en_test', 'escalando', 'validada', 'inconclusa', 'fallida', 'pausada', 'retirada'];
export const ETAPAS = ['M1', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10'];
const RE_OFERTA = /^OF-[0-9]{6}-[0-9]{2}$/;
const RE_ETAPA = /^[A-Z][A-Z0-9]{0,3}$/;

/** «N2» → «Autonomía 2» (nivel de autonomía del 0 al 4); cualquier otro valor se muestra tal cual. */
export const rotuloNivel = (n) => (typeof n === 'string' && /^N[0-4]$/.test(n) ? `Autonomía ${n.slice(1)}` : String(n ?? '—'));

/** true si el id de oferta tiene la forma OF-AAAAMM-NN (así nunca metemos texto hostil en un comando copiable). */
export const ofertaIdValido = (id) => typeof id === 'string' && RE_OFERTA.test(id);
export const etapaValida = (e) => typeof e === 'string' && RE_ETAPA.test(e);

/**
 * Comando exacto para firmar un gate (CONTRATO §6: el panel NO firma, solo lo muestra copiable).
 * Devuelve null si oferta o etapa no tienen la forma esperada. Ver PEDIDO: `engine.orq` aún no fija el nombre de la acción de gate.
 */
export function comandoFirmar(ofertaId, etapa) {
  if (!ofertaIdValido(ofertaId) || !etapaValida(etapa)) return null;
  return `.venv/bin/python -m engine.orq firmar --oferta ${ofertaId} --etapa ${etapa} --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno`;
}

export const COMANDO_PREFLIGHT = '.venv/bin/python -m infra.preflight ejecutar --modo completo';
export const COMANDO_VERIFICAR_REGISTRO = '.venv/bin/python -m engine.registro verificar --json';

/** Ofertas agrupadas por fase en orden de ciclo de vida; fases desconocidas al final; sin columnas vacías. */
export function agruparPorFase(ofertas) {
  const lista = Array.isArray(ofertas) ? ofertas.filter((o) => o && typeof o === 'object') : [];
  const mapa = new Map();
  for (const o of lista) {
    const f = typeof o.fase === 'string' && o.fase ? o.fase : 'sin_fase';
    if (!mapa.has(f)) mapa.set(f, []);
    mapa.get(f).push(o);
  }
  const orden = [...FASES, ...[...mapa.keys()].filter((k) => !FASES.includes(k)).sort()];
  return orden.filter((f) => mapa.has(f)).map((f) => ({ fase: f, ofertas: mapa.get(f).slice().sort((a, b) => String(a.oferta_id).localeCompare(String(b.oferta_id))) }));
}

/**
 * Un gate pendiente por (oferta, etapa), con su comando de firma. Las ofertas demo se marcan pero se incluyen.
 * `oferta_id` es el nombre de la carpeta (para el enlace #/oferta/<id>; la demo es `_ejemplo`); el comando usa `oferta_id_estado`
 * (el id real de estado.json, p. ej. OF-202611-01) si el servidor lo trae.
 */
export function gatesPendientes(ofertas) {
  const filas = [];
  for (const o of Array.isArray(ofertas) ? ofertas : []) {
    if (!o || !Array.isArray(o.gates_pendientes)) continue;
    const idComando = o.oferta_id_estado || o.oferta_id;
    for (const etapa of o.gates_pendientes) {
      filas.push({ oferta_id: o.oferta_id, id_estado: o.oferta_id_estado || null, etapa, demo: Boolean(o.demo), fase: o.fase || null, nivel: o.nivel || null, actualizado_en: o.actualizado_en || null, comando: comandoFirmar(idComando, etapa) });
    }
  }
  return filas.sort((a, b) => Number(a.demo) - Number(b.demo) || String(a.oferta_id).localeCompare(String(b.oferta_id)) || String(a.etapa).localeCompare(String(b.etapa), 'es', { numeric: true }));
}

const montoValido = (m) => m && typeof m === 'object' && Number.isSafeInteger(m.monto) && typeof m.moneda === 'string' && /^[A-Za-z]{3}$/.test(m.moneda);

/** Suma entera por moneda (nunca mezcla monedas, nunca float). Entradas inválidas se ignoran y se cuentan en `ignorados`. */
export function sumarPorMoneda(montos) {
  const acc = new Map();
  let ignorados = 0;
  for (const m of Array.isArray(montos) ? montos : []) {
    if (!montoValido(m)) { if (m !== null && m !== undefined) ignorados += 1; continue; }
    const mon = m.moneda.toUpperCase();
    acc.set(mon, (acc.get(mon) || 0n) + BigInt(m.monto));
  }
  const filas = [...acc.entries()].map(([moneda, v]) => ({ moneda, monto: v >= BigInt(Number.MIN_SAFE_INTEGER) && v <= BigInt(Number.MAX_SAFE_INTEGER) ? Number(v) : v.toString() }));
  filas.sort((a, b) => a.moneda.localeCompare(b.moneda));
  return { filas, ignorados };
}

/** Gasto de hoy y costo de IA. Las ofertas demo NO suman (se cuentan aparte). */
export function totalesDia(ofertas) {
  const lista = Array.isArray(ofertas) ? ofertas : [];
  const reales = lista.filter((o) => o && !o.demo);
  const gastoHoy = sumarPorMoneda(reales.map((o) => o.gasto && o.gasto.hoy));
  const gastoAcum = sumarPorMoneda(reales.map((o) => o.gasto && o.gasto.acumulado));
  const costoIa = sumarPorMoneda(reales.map((o) => (o.costo_ia && o.costo_ia.hoy ? o.costo_ia.hoy : o.costo_ia)));
  return {
    gastoHoy: gastoHoy.filas, gastoAcumulado: gastoAcum.filas, costoIa: costoIa.filas,
    ignorados: gastoHoy.ignorados + gastoAcum.ignorados + costoIa.ignorados,
    reales: reales.length, demo: lista.length - reales.length,
  };
}

const TONO_ETAPA = { aprobado: 'ok', en_QA: 'info', en_progreso: 'info', pendiente: 'neutro', bloqueado: 'error', escalado: 'aviso' };

/** Avance de una oferta por etapa: conteos y segmentos para la barra apilada. */
export function avanceEtapas(etapas) {
  const conteos = {};
  let total = 0;
  for (const v of Object.values(etapas && typeof etapas === 'object' ? etapas : {})) {
    const k = typeof v === 'string' ? v : (v && v.estado) || 'pendiente';
    conteos[k] = (conteos[k] || 0) + 1;
    total += 1;
  }
  const orden = ['aprobado', 'en_QA', 'en_progreso', 'escalado', 'bloqueado', 'pendiente'];
  const segmentos = orden.filter((k) => conteos[k]).map((k) => ({ valor: conteos[k], tono: TONO_ETAPA[k] || 'neutro', titulo: k }));
  return { total, aprobadas: conteos.aprobado || 0, conteos, segmentos };
}

/** Etapa «actual»: la primera que no está aprobada (en el orden M1…D10); null si todas aprobadas o sin datos. */
export function etapaActual(etapas) {
  if (!etapas || typeof etapas !== 'object') return null;
  const claves = [...ETAPAS.filter((e) => e in etapas), ...Object.keys(etapas).filter((e) => !ETAPAS.includes(e))];
  for (const k of claves) {
    const v = etapas[k];
    const est = typeof v === 'string' ? v : v && v.estado;
    if (est !== 'aprobado') return { etapa: k, estado: est || 'pendiente' };
  }
  return null;
}

/** Alertas unificadas de registro (alerta/bloqueo/error) y finanzas (abiertas). Más recientes primero. */
export function alertasUnificadas({ registro, finanzas, limite = 8, ventanaH = null, ahoraMs = Date.now() } = {}) {
  const salida = [];
  const lineas = registro && Array.isArray(registro.lineas) ? registro.lineas : [];
  for (const l of lineas) {
    if (!l || typeof l !== 'object') continue;
    const est = l.resultado && l.resultado.estado;
    if (l.evento === 'alerta' || l.evento === 'bloqueo' || est === 'error' || est === 'bloqueado') {
      salida.push({ ts: l.ts || null, tono: est === 'error' ? 'error' : 'aviso', titulo: l.entrada_resumen || l.evento, origen: l.agente || 'registro', oferta_id: l.oferta_id || null, etapa: l.etapa || null, fuente: 'registro', n: l.n });
    }
  }
  const fin = finanzas && Array.isArray(finanzas.alertas) ? finanzas.alertas : [];
  for (const a of fin) {
    if (!a || typeof a !== 'object') continue;
    if (['cerrada', 'resuelta', 'descartada'].includes(a.estado)) continue;
    const tono = a.severidad === 'alta' || a.severidad === 'critica' ? 'error' : a.severidad === 'baja' ? 'info' : 'aviso';
    salida.push({ ts: a.ts || null, tono, titulo: a.accion_sugerida ? `${a.regla_id || 'alerta'}: ${a.accion_sugerida}` : (a.regla_id || 'alerta'), origen: a.origen || 'finanzas', oferta_id: a.oferta_id || null, etapa: null, fuente: 'finanzas', id: a.id });
  }
  // `ventanaH`: las del registro más viejas que la ventana ya no cuentan como «recientes» (las de finanzas abiertas siempre cuentan)
  const dentro = (a) => {
    if (!ventanaH || a.fuente !== 'registro') return true;
    const t = Date.parse(a.ts || '');
    return Number.isFinite(t) ? ahoraMs - t <= ventanaH * 3600000 : false;
  };
  const vigentes = salida.filter(dentro);
  vigentes.sort((x, y) => String(y.ts || '').localeCompare(String(x.ts || '')));
  return vigentes.slice(0, limite);
}

/** Antigüedad del preflight y veredicto de frescura (el guard exige VERDE, modo vivo y ≤ 6 h). */
export function estadoInfra(infra, ahoraMs, vigenciaH = 6) {
  if (!infra || typeof infra !== 'object') return { tono: 'neutro', texto: 'Sin chequeo', detalle: 'Todavía no se midieron las cuentas y servicios (Meta, Stripe y demás).', edadH: null, ok: false };
  const t = Date.parse(infra.generado_en || '');
  const edadH = Number.isFinite(t) && Number.isFinite(ahoraMs) ? Math.max(0, (ahoraMs - t) / 3600000) : null;
  const sem = String(infra.semaforo || '').toUpperCase();
  const vencido = edadH !== null && edadH > vigenciaH;
  const vivo = infra.modo === 'vivo';
  let tono = sem === 'VERDE' ? 'ok' : sem === 'AMARILLO' ? 'aviso' : sem === 'ROJO' ? 'error' : 'neutro';
  if (tono === 'ok' && (vencido || !vivo)) tono = 'aviso';
  const partes = [];
  if (!vivo) partes.push(`modo ${infra.modo || 'sin dato'}: no sirve para gastar ni activar de verdad`);
  if (vencido) partes.push(`vencido (medido hace ${Number.isInteger(edadH) ? edadH : edadH.toFixed(1).replace('.', ',')} h; máximo ${vigenciaH} h)`);
  return { tono, texto: sem || 'Sin semáforo', detalle: partes.join(' · ') || 'vigente', edadH, ok: tono === 'ok' };
}

/**
 * Cosas que dependen del dueño y se ven en el Resumen. SOLO lo vigente: PAUSA, freno de captura, límites en null,
 * preflight de infraestructura y gates. (No incluye gestor de contraseñas, llaves/2FA, segundo administrador ni revisión legal.)
 */
/**
 * Claves de `limites` que siguen en `null` y SÍ bloquean el gasto. Se descuentan las de riesgo 1.3.0 que con `null` significan
 * «solo verde» (`limites.nulos_solo_verde`, que calcula el servidor): no son un dato faltante. `null` si no hay datos de límites.
 */
export function nulosQueBloquean(parametros) {
  const lim = parametros && parametros.limites;
  if (!lim || !Array.isArray(lim.nulos)) return null;
  const seguros = new Set(Array.isArray(lim.nulos_solo_verde) ? lim.nulos_solo_verde : []);
  return lim.nulos.filter((c) => !seguros.has(c));
}

export function pendientesDueno({ sistema, ofertas, parametros, ahoraMs } = {}) {
  const sal = [];
  const pausa = sistema && sistema.pausa;
  if (pausa && pausa.activa) sal.push({ id: 'pausa', tono: 'error', titulo: 'PAUSA (freno de emergencia) activa', detalle: `Desde ${fmt.fecha(pausa.desde)}${pausa.motivo ? ': ' + pausa.motivo : ''}. Solo una persona la levanta a mano.`, enlace: '#/sistema' });
  const freno = sistema && sistema.freno_captura;
  if (freno && freno.activo) sal.push({ id: 'freno', tono: 'aviso', titulo: 'Freno de la captura de anuncios puesto', detalle: `${freno.motivo || 'sin motivo'} (${fmt.fecha(freno.ts)}). Revísalo y, si corresponde, levántalo a mano.`, enlace: '#/sistema' });
  const nulos = nulosQueBloquean(parametros);
  if (nulos && nulos.length) sal.push({ id: 'limites', tono: 'aviso', titulo: 'Fijar y firmar límites', detalle: `Faltan ${nulos.length} límite${nulos.length === 1 ? '' : 's'} de seguridad. Sin ellos el semáforo no llega a verde y no se puede gastar.`, enlace: '#/parametros' });
  if (sistema) {
    const inf = estadoInfra(sistema.infra, ahoraMs);
    if (!sistema.infra) sal.push({ id: 'infra', tono: 'aviso', titulo: 'Falta el chequeo de cuentas y servicios', detalle: 'Hasta que se haga, nadie gasta ni activa.', comando: COMANDO_PREFLIGHT, enlace: '#/sistema' });
    else if (!inf.ok) sal.push({ id: 'infra', tono: inf.tono, titulo: `Cuentas y servicios: ${inf.texto}`, detalle: inf.detalle, comando: COMANDO_PREFLIGHT, enlace: '#/sistema' });
  }
  const gates = gatesPendientes(ofertas);
  if (gates.length) sal.push({ id: 'gates', tono: 'info', titulo: `${gates.length} firma${gates.length === 1 ? '' : 's'} esperan por ti`, detalle: gates.slice(0, 3).map((g) => `${g.oferta_id} ${g.etapa}`).join(', ') + (gates.length > 3 ? '…' : ''), enlace: '#/resumen' });
  const rango = { error: 0, aviso: 1, info: 2, neutro: 3, ok: 4 };
  return sal.sort((a, b) => rango[a.tono] - rango[b.tono]);
}

/** Qué falta: fuentes vacías (con el archivo esperado) y pantallas aún sin módulo. `fuentes`: {nombre: {vacio, fuente, comando?}}; `paginas`: {ruta: 'ok'|'falta'|'error'}. */
export function faltantes({ fuentes = {}, paginas = {}, titulos = {} } = {}) {
  const datos = Object.entries(fuentes).filter(([, f]) => f && f.vacio).map(([nombre, f]) => ({ tipo: 'dato', nombre, fuente: f.fuente || [], comando: f.comando || null }));
  const pantallas = Object.entries(paginas).filter(([, e]) => e === 'falta').map(([ruta]) => ({ tipo: 'pantalla', nombre: titulos[ruta] || ruta, ruta }));
  return { datos, pantallas };
}

// ───────────────────────── rediseño UX: centro de mando ─────────────────────────

export const FASE_ROTULO = {
  borrador: 'en borrador', en_construccion: 'en construcción', listo_para_activar: 'listas para activar', en_test: 'en prueba', escalando: 'escalando', validada: 'validadas',
  inconclusa: 'inconclusas', fallida: 'fallidas', pausada: 'en pausa', retirada: 'retiradas', sin_fase: 'sin fase',
};

/** «1 en construcción · 1 en test · 1 en borrador» — solo ofertas reales (la demo se cuenta aparte). */
export function textoPorFase(ofertas) {
  const reales = (Array.isArray(ofertas) ? ofertas : []).filter((o) => o && !o.demo);
  return agruparPorFase(reales).map(({ fase, ofertas: l }) => `${l.length} ${FASE_ROTULO[fase] || String(fase).replace(/_/g, ' ')}`).join(' · ');
}

/** Primera etapa no aprobada y su estado: base del «ahora» de cada tarjeta. */
export function estadoPipeline(oferta) {
  const etapas = oferta && oferta.etapas && typeof oferta.etapas === 'object' ? oferta.etapas : {};
  const gates = new Set(Array.isArray(oferta && oferta.gates_pendientes) ? oferta.gates_pendientes : []);
  const actual = etapaActual(etapas);
  const claves = [...ETAPAS.filter((e) => e in etapas), ...Object.keys(etapas).filter((e) => !ETAPAS.includes(e))];
  const lista = claves.map((cod) => {
    const v = etapas[cod];
    const estado = (typeof v === 'string' ? v : v && v.estado) || 'pendiente';
    return { id: cod, nombre: nombreEtapa(cod), codigo: cod, estado, seleccionada: Boolean(actual && actual.etapa === cod), aviso: gates.has(cod) ? 'Espera tu firma' : null };
  });
  return { etapas: lista, actual, espera: actual ? gates.has(actual.etapa) : false };
}

/** Texto de «dónde está» una oferta: «Campaña (D7) · en QA — espera tu firma». */
export function frasePipeline(oferta) {
  const p = estadoPipeline(oferta);
  if (!p.etapas.length) return 'Sin etapas todavía';
  if (!p.actual) return 'Todas las etapas aprobadas';
  const est = { en_QA: 'en revisión de calidad', en_progreso: 'en progreso', pendiente: 'por empezar', bloqueado: 'bloqueada', escalado: 'escalada' }[p.actual.estado] || String(p.actual.estado).replace(/_/g, ' ');
  return `${etapaHumana(p.actual.etapa)} · ${est}${p.espera ? ' — espera tu firma' : ''}`;
}

const EST_INFRA_ROJO = (infra) => String((infra && infra.semaforo) || '').toUpperCase() === 'ROJO';

/**
 * Lo que requiere atención del dueño, ya priorizado (crítico → aviso → info). Cada ítem:
 * { id, tono:'critico'|'aviso'|'info', titulo, detalle, accion:{texto, tipo:'ruta'|'firmar'|'preflight', ruta?, gate?}, ayuda? }
 * SOLO lo vigente: PAUSA, integridad del registro, infraestructura, firmas, etapas bloqueadas, freno de captura, límites sin fijar y alertas recientes.
 * (No incluye gestor de contraseñas, llaves/2FA, segundo administrador ni revisión legal: decisiones 14 y 15 del dueño.)
 */
export function itemsAtencion({ sistema, ofertas, parametros, alertas, cadenaOk, ahoraMs = Date.now(), maxGates = 6 } = {}) {
  const sal = [];
  const pausa = sistema && sistema.pausa;
  if (pausa && pausa.activa) {
    sal.push({ id: 'pausa', tono: 'critico', titulo: 'La fábrica está en pausa', detalle: `Nada gasta ni se activa mientras exista la pausa (desde ${fmt.relativo(pausa.desde, ahoraMs)}${pausa.motivo ? `: ${pausa.motivo}` : ''}). Solo una persona la levanta a mano.`, accion: { texto: 'Ver estado', tipo: 'ruta', ruta: '#/sistema' }, ayuda: 'pausa' });
  }
  if (cadenaOk === false) {
    sal.push({ id: 'cadena', tono: 'critico', titulo: 'El historial de actividad ya no es confiable', detalle: 'Alguna línea no coincide con su huella: la cambiaron o se dañó. No uses el historial para decidir hasta revisarlo.', accion: { texto: 'Revisar el historial', tipo: 'ruta', ruta: '#/registro' }, ayuda: 'cadena_ok' });
  }
  const infraEst = sistema ? estadoInfra(sistema.infra, ahoraMs) : null;
  if (sistema && sistema.infra && EST_INFRA_ROJO(sistema.infra)) {
    sal.push({ id: 'infra', tono: 'critico', titulo: 'Las cuentas y servicios están en rojo', detalle: 'Mientras no vuelvan a verde, nadie gasta ni activa. Mira cuál falló.', accion: { texto: 'Ver el chequeo', tipo: 'ruta', ruta: '#/sistema' }, ayuda: 'preflight_infra' });
  }
  const gates = gatesPendientes(ofertas);
  const reales = gates.filter((g) => !g.demo);
  const demo = gates.filter((g) => g.demo);
  for (const g of reales.slice(0, maxGates)) {
    sal.push({ id: `gate:${g.oferta_id}:${g.etapa}`, tono: 'aviso', titulo: `Espera tu firma: ${etapaHumana(g.etapa)} de ${g.oferta_id}`, detalle: 'La etapa ya pasó la revisión de calidad. El sistema no sigue hasta que la apruebes.', accion: { texto: 'Ver cómo firmar', tipo: 'firmar', gate: g }, ayuda: 'gate_h' });
  }
  if (reales.length > maxGates) sal.push({ id: 'gates-mas', tono: 'aviso', titulo: `${reales.length - maxGates} firmas más esperan en otras ofertas`, detalle: 'Abre Ofertas para verlas todas.', accion: { texto: 'Abrir ofertas', tipo: 'ruta', ruta: '#/ofertas' }, ayuda: 'gate_h' });
  for (const o of Array.isArray(ofertas) ? ofertas : []) {
    if (!o || o.demo || !o.etapas || typeof o.etapas !== 'object') continue;
    const bloq = Object.entries(o.etapas).filter(([, v]) => (typeof v === 'string' ? v : v && v.estado) === 'bloqueado').map(([k]) => k);
    if (bloq.length) sal.push({ id: `bloqueo:${o.oferta_id}`, tono: 'aviso', titulo: `Etapa bloqueada: ${bloq.map(etapaHumana).join(', ')} en ${o.oferta_id}`, detalle: 'El sistema no puede avanzar esta oferta hasta que se resuelva el bloqueo.', accion: { texto: 'Abrir la oferta', tipo: 'ruta', ruta: `#/oferta/${encodeURIComponent(o.oferta_id)}` } });
  }
  const freno = sistema && sistema.freno_captura;
  if (freno && freno.activo) {
    sal.push({ id: 'freno', tono: 'aviso', titulo: 'La captura de anuncios está frenada', detalle: `${freno.motivo ? `Meta respondió «${freno.motivo}»` : 'Se detectó un bloqueo'} ${fmt.relativo(freno.ts, ahoraMs)}. El sistema no insiste: solo tú puedes levantar el freno, si corresponde.`, accion: { texto: 'Revisar el freno', tipo: 'ruta', ruta: '#/sistema' }, ayuda: 'freno_captura' });
  }
  const nulos = nulosQueBloquean(parametros);
  if (nulos && nulos.length) {
    sal.push({ id: 'limites', tono: 'aviso', titulo: `Faltan por fijar ${nulos.length} límite${nulos.length === 1 ? '' : 's'} de seguridad`, detalle: 'Sin límites firmados el semáforo no llega a verde y no se puede gastar.', accion: { texto: 'Abrir límites', tipo: 'ruta', ruta: '#/parametros' }, ayuda: 'limites' });
  }
  if (sistema) {
    if (!sistema.infra) sal.push({ id: 'preflight', tono: 'aviso', titulo: 'Falta el chequeo de cuentas y servicios', detalle: 'Hasta que se haga y salga en verde, nadie gasta ni activa.', accion: { texto: 'Ver cómo hacer el chequeo', tipo: 'preflight' }, ayuda: 'preflight_infra' });
    else if (!EST_INFRA_ROJO(sistema.infra) && infraEst && !infraEst.ok) sal.push({ id: 'preflight', tono: 'aviso', titulo: `Cuentas y servicios en ${String(infraEst.texto).toLowerCase()}`, detalle: infraEst.detalle, accion: { texto: 'Ver cómo hacer el chequeo', tipo: 'preflight' }, ayuda: 'preflight_infra' });
  }
  const al = Array.isArray(alertas) ? alertas : [];
  if (al.length) {
    const hayGrave = al.some((a) => a.tono === 'error' && a.fuente === 'finanzas');
    const nErr = al.filter((a) => a.tono === 'error').length;
    sal.push({ id: 'alertas', tono: hayGrave ? 'critico' : 'aviso', titulo: `${al.length} alerta${al.length === 1 ? '' : 's'} reciente${al.length === 1 ? '' : 's'}${nErr ? ` (${nErr} con error)` : ''}`, detalle: `La última: ${al[0].titulo}`, accion: { texto: 'Ver el historial', tipo: 'ruta', ruta: '#/registro' } });
  }
  if (demo.length) {
    sal.push({ id: 'gates-demo', tono: 'info', titulo: `${demo.length === 1 ? 'La oferta de demostración tiene una firma pendiente' : `La demostración tiene ${demo.length} firmas pendientes`}`, detalle: 'Es solo de práctica: no afecta a ofertas reales.', accion: { texto: 'Ver cómo firmar', tipo: 'firmar', gate: demo[0] }, ayuda: 'gate_h' });
  }
  const rango = { critico: 0, aviso: 1, info: 2 };
  return sal.map((x, i) => ({ x, i })).sort((a, b) => rango[a.x.tono] - rango[b.x.tono] || a.i - b.i).map((o) => o.x);
}

/** {valor, extra} de una lista por moneda: la primera moneda es el valor; las demás van como contexto (nunca se mezclan). */
export function dineroResumen(filas) {
  const lista = Array.isArray(filas) ? filas : [];
  if (!lista.length) return { valor: null, extra: '' };
  const f = (x) => fmt.dinero(x.monto, x.moneda);
  return { valor: f(lista[0]), extra: lista.slice(1).map(f).join(' · ') };
}

/** Veredicto único del sistema: {tono, texto (corto, para el número grande), titulo (frase), detalle}. */
export function veredictoSistema({ sistema, ahoraMs = Date.now(), cadenaOk } = {}) {
  if (!sistema) return { tono: 'neutro', texto: 'Sin datos', titulo: 'No se pudo leer el estado del sistema', detalle: 'Reintenta en unos segundos.' };
  const infra = estadoInfra(sistema.infra, ahoraMs);
  const pausa = sistema.pausa && sistema.pausa.activa;
  const freno = sistema.freno_captura && sistema.freno_captura.activo;
  const partes = [pausa ? 'en pausa' : 'sin pausa', freno ? 'freno de captura puesto' : 'sin freno de captura', `cuentas y servicios ${sistema.infra ? String(infra.texto).toLowerCase() : 'sin medir'}`];
  const detalle = partes.join(' · ');
  if (pausa) return { tono: 'error', texto: 'En pausa', titulo: 'La fábrica está en pausa: nada gasta ni se activa', detalle };
  if (cadenaOk === false) return { tono: 'error', texto: 'Revisar', titulo: 'El historial de actividad ya no es confiable', detalle };
  if (sistema.infra && infra.tono === 'error') return { tono: 'error', texto: 'En rojo', titulo: 'Las cuentas y servicios están en rojo: nadie gasta ni activa', detalle };
  if (freno) return { tono: 'aviso', texto: 'Revisar', titulo: 'La captura de anuncios está frenada', detalle };
  if (!infra.ok) return { tono: 'aviso', texto: 'Revisar', titulo: sistema.infra ? 'Hay que volver a medir las cuentas y servicios' : 'Falta medir las cuentas y servicios', detalle };
  return { tono: 'ok', texto: 'En orden', titulo: 'Todo en orden: sin pausa, sin freno y con las cuentas y servicios en verde', detalle };
}

/**
 * Métricas del encabezado. `datos`: { ofertas|null, sistema|null, alertas|null, finanzasOk, ahoraMs, cadenaOk }.
 * Cada una: { id, etiqueta, valor, contexto, tono, ayuda?, ruta? }. `valor` null = sin datos («—»), nunca un 0 inventado.
 */
export function metricasResumen({ ofertas, sistema, alertas, ahoraMs = Date.now(), cadenaOk } = {}) {
  const hayOfertas = Array.isArray(ofertas);
  const tot = totalesDia(hayOfertas ? ofertas : []);
  const gates = gatesPendientes(hayOfertas ? ofertas : []);
  const gatesReales = gates.filter((g) => !g.demo);
  const porFase = hayOfertas ? textoPorFase(ofertas) : '';
  const enTest = hayOfertas ? ofertas.filter((o) => !o.demo && o.fase === 'en_test').length : 0;
  const gasto = dineroResumen(tot.gastoHoy);
  const ia = dineroResumen(tot.costoIa);
  const ver = veredictoSistema({ sistema, ahoraMs, cadenaOk });
  const al = Array.isArray(alertas) ? alertas : null;
  const nErr = al ? al.filter((a) => a.tono === 'error').length : 0;
  const demoTxt = tot.demo ? `más ${tot.demo} de demostración` : '';
  return [
    { id: 'ofertas', etiqueta: 'Ofertas', valor: hayOfertas ? tot.reales : null, contexto: !hayOfertas ? 'sin datos' : [porFase || (tot.reales ? '' : 'ninguna todavía'), demoTxt].filter(Boolean).join(' · '), tono: 'neutro', ruta: '#/ofertas', enTest },
    { id: 'firma', etiqueta: 'Esperan tu firma', valor: hayOfertas ? gatesReales.length : null, contexto: !hayOfertas ? 'sin datos' : gatesReales.length ? gatesReales.slice(0, 2).map((g) => `${nombreEtapa(g.etapa)} · ${g.oferta_id}`).join(' · ') + (gatesReales.length > 2 ? ` y ${gatesReales.length - 2} más` : '') : (gates.length ? `nada real pendiente (${gates.length} en la demo)` : 'nada pendiente'), tono: gatesReales.length ? 'aviso' : 'ok', ayuda: 'gate_h' },
    { id: 'gasto', etiqueta: 'Gasto de hoy', valor: gasto.valor, contexto: !hayOfertas ? 'sin datos' : [gasto.extra, tot.reales ? `${tot.reales} oferta${tot.reales === 1 ? '' : 's'} real${tot.reales === 1 ? '' : 'es'}` : (tot.demo ? 'solo hay demostración (no suma)' : 'sin ofertas')].filter(Boolean).join(' · '), tono: 'neutro', ayuda: 'gasto_hoy' },
    { id: 'ia', etiqueta: 'Costo de IA', valor: ia.valor, contexto: !hayOfertas ? 'sin datos' : [ia.extra, 'por oferta, sin mezclar monedas'].filter(Boolean).join(' · '), tono: 'neutro', ayuda: 'costo_ia' },
    { id: 'alertas', etiqueta: 'Alertas', valor: al ? al.length : null, contexto: !al ? 'sin datos' : nErr ? `${nErr} con error · últimas 72 h` : al.length ? 'bloqueos y avisos · últimas 72 h' : 'sin alertas en las últimas 72 h', tono: nErr ? 'error' : al && al.length ? 'aviso' : 'ok', ruta: '#/registro' },
    { id: 'sistema', etiqueta: 'Estado del sistema', valor: sistema ? ver.texto : null, contexto: sistema ? ver.detalle : 'sin datos', tono: ver.tono, ruta: '#/sistema', ayuda: 'estado_sistema', textual: true },
  ];
}

/** Resumen de la corrida de descubrimiento más reciente: {…, pctConsultas} o null si no hay ninguna. */
export function resumenDescubrimiento(corridas) {
  const lista = (Array.isArray(corridas) ? corridas : []).filter((c) => c && typeof c === 'object' && typeof c.corrida_id === 'string');
  if (!lista.length) return null;
  const c = lista.slice().sort((a, b) => String(b.actualizado_en || '').localeCompare(String(a.actualizado_en || '')) || String(b.corrida_id).localeCompare(String(a.corrida_id)))[0];
  const ok = Number.isInteger(c.consultas_ok) ? c.consultas_ok : null;
  const tope = Number.isInteger(c.consultas_tope) && c.consultas_tope > 0 ? c.consultas_tope : null;
  return {
    corrida_id: c.corrida_id, actualizado_en: c.actualizado_en || null, total: lista.length,
    consultas_ok: ok, consultas_tope: tope, pctConsultas: ok !== null && tope ? Math.max(0, Math.min(100, Math.round((ok / tope) * 100))) : null,
    paginas: Number.isInteger(c.paginas) ? c.paginas : null, etiquetadas: Number.isInteger(c.etiquetadas) ? c.etiquetadas : null, candidatas: Number.isInteger(c.candidatas) ? c.candidatas : null,
    pasan_traccion: Number.isInteger(c.pasan_traccion) ? c.pasan_traccion : null, pasan_temas: Number.isInteger(c.pasan_traccion_temas) ? c.pasan_traccion_temas : null, pasan_sin_tema: Number.isInteger(c.pasan_traccion_sin_tema) ? c.pasan_traccion_sin_tema : null,
    fichas: Number.isInteger(c.fichas) ? c.fichas : null,
  };
}

/** Últimos `n` eventos del registro en lenguaje humano (más reciente primero): [{linea, vista}]. */
export function actividadReciente(lineas, n = 8) {
  const arr = (Array.isArray(lineas) ? lineas : []).filter((l) => l && typeof l === 'object' && Number.isInteger(l.n));
  return arr.slice().sort((a, b) => b.n - a.n).slice(0, n).map((l) => ({ linea: l, vista: describirEvento(l) }));
}


// ───────────────────────── La rueda: los 9 pasos de cada día (know-how §0) ─────────────────────────

/**
 * Los 9 pasos que giran todos los días. `ruta` es la pantalla de cada uno; `alternativa`, la que existe hoy si esa aún no se ha construido (el shell avisa con
 * ctx.paginas(): 'falta' → alternativa). El paso 9 vuelve al 1.
 */
export const PASOS_RUEDA = [
  { n: 1, id: 'cerebro', titulo: 'El cerebro recuerda', glosario: 'cerebro', ruta: '#/cerebro', alternativa: '#/pulido', verbo: 'Ver el cerebro' },
  { n: 2, id: 'fabrica', titulo: 'La fábrica hace los anuncios', ruta: '#/fabrica', alternativa: '#/ofertas', verbo: 'Ver la fábrica' },
  { n: 3, id: 'jurado', titulo: 'El jurado elige los mejores', glosario: 'jurado_sintetico', ruta: '#/jurado', alternativa: '#/ofertas', verbo: 'Ver el jurado' },
  { n: 4, id: 'prueba', titulo: 'Se prueban con poca plata', ruta: '#/campanas', alternativa: '#/ofertas', verbo: 'Ver las campañas' },
  { n: 5, id: 'escala', titulo: 'El que vende se agranda', ruta: '#/operacion', alternativa: '#/ofertas', verbo: 'Ver la operación' },
  { n: 6, id: 'robots', titulo: 'Los robots trabajan 24 h', ruta: '#/robots', alternativa: '#/sistema', verbo: 'Ver los robots' },
  { n: 7, id: 'auditor', titulo: 'Un auditor controla', ruta: '#/robots?vista=reglas', alternativa: '#/sistema', verbo: 'Ver cómo se audita' },
  { n: 8, id: 'pais', titulo: 'El ganador viaja a otro país', ruta: '#/paises', alternativa: '#/ofertas', verbo: 'Ver los países' },
  { n: 9, id: 'aprende', titulo: 'Lo aprendido vuelve al cerebro', ruta: '#/cerebro', alternativa: '#/pulido', verbo: 'Ver lo aprendido' },
];

const ESTADO_RUEDA = {
  ok: { tono: 'ok', texto: 'En marcha', icono: 'ok' },
  aviso: { tono: 'aviso', texto: 'Requiere atención', icono: 'alerta' },
  sin_datos: { tono: 'neutro', texto: 'Sin datos todavía', icono: 'circulo-punteado' },
};
export const infoEstadoRueda = (clave) => ESTADO_RUEDA[clave] || ESTADO_RUEDA.sin_datos;

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;
const listaCorta = (xs, max = 3) => (xs.length > max ? `${xs.slice(0, max).join(' · ')} y ${xs.length - max} más` : xs.join(' · '));

/** Ofertas cuyo detalle hace falta para contar piezas: las que ya pasaron de «pendiente» en la etapa de creativos (D6). Tope para no saturar la API. */
export function ofertasConCreativos(ofertas, tope = 12) {
  return (Array.isArray(ofertas) ? ofertas : [])
    .filter((o) => o && typeof o.oferta_id === 'string' && o.etapas && o.etapas.D6 !== undefined && (typeof o.etapas.D6 === 'string' ? o.etapas.D6 : (o.etapas.D6 && o.etapas.D6.estado)) !== 'pendiente')
    .slice(0, tope).map((o) => o.oferta_id);
}

/** Piezas de creativos de una oferta según `GET /oferta/<id>` (archivos bajo 06-creativos/assets/ de la etapa D6): { piezas, estado } o null si el detalle no trae D6. */
export function piezasDeCreativos(detalle) {
  const etapas = detalle && Array.isArray(detalle.etapas) ? detalle.etapas : null;
  const d6 = etapas ? etapas.find((e) => e && e.id === 'D6') : null;
  if (!d6) return null;
  const arts = Array.isArray(d6.artefactos) ? d6.artefactos : [];
  return { piezas: arts.filter((a) => a && typeof a.ruta === 'string' && a.ruta.startsWith('06-creativos/assets/')).length, estado: typeof d6.estado === 'string' ? d6.estado : null };
}

/** Ruta a la que enlaza un paso: la suya, o la alternativa si el shell dice que la pantalla aún no existe (`paginas`: {ruta: 'ok'|'falta'|'error'}). */
export function rutaDelPaso(paso, paginas = {}) {
  const nombre = String(paso.ruta).replace(/^#\//, '').split('?')[0];
  const est = paginas && typeof paginas === 'object' ? paginas[nombre] : undefined;
  return (est === 'falta' || est === 'error') && paso.alternativa ? paso.alternativa : paso.ruta;
}

function pasoPulido(pulido, tipo) {
  const base = { dato: '', nota: '', estado: 'sin_datos' };
  if (!Array.isArray(pulido)) return { ...base, dato: 'No se pudo leer la lista de pendientes.', nota: 'Reintenta en unos segundos.' };
  const r = resumenBitacora(pulido);
  if (tipo === 'abiertos') {
    if (r.total === 0) return { ...base, dato: 'La lista de pendientes está vacía.', nota: 'El cerebro (reglas y lecciones) aún no existe: hoy la única memoria es la lista de Mejoras pendientes.' };
    const nota = 'El cerebro completo (reglas y lecciones) aún no existe: hoy la memoria es la lista de Mejoras pendientes.';
    if (r.pendientes === 0) return { estado: 'ok', dato: `Sin pendientes abiertos (${plural(r.resueltas, 'resuelto', 'resueltos')}).`, nota };
    return { estado: r.altasPendientes ? 'aviso' : 'ok', dato: `${plural(r.pendientes, 'pendiente abierto', 'pendientes abiertos')}${r.altasPendientes ? ` (${r.altasPendientes} de gravedad alta)` : ''}.`, nota };
  }
  if (r.resueltas === 0) return { ...base, dato: 'Todavía no se ha resuelto ninguna lección ni corrección.', nota: 'Cada mejora pendiente que se resuelve es algo aprendido que vuelve a las guías de trabajo; el cerebro con reglas aún no existe.' };
  return { estado: 'ok', dato: `${plural(r.resueltas, 'lección o corrección ya resuelta', 'lecciones o correcciones ya resueltas')} de ${r.total} en Mejoras pendientes.`, nota: 'Cuando exista el cerebro, aquí se verán las reglas nuevas que dejó lo aprendido.' };
}

function pasoCreativos(ofertas, detalles) {
  if (!Array.isArray(ofertas)) return { estado: 'sin_datos', dato: 'No se pudo leer la lista de ofertas.', nota: 'Reintenta en unos segundos.' };
  const reales = ofertas.filter((o) => o && !o.demo);
  const det = detalles && typeof detalles === 'object' ? detalles : {};
  const estadoD6 = (o) => (o.etapas && o.etapas.D6 !== undefined ? (typeof o.etapas.D6 === 'string' ? o.etapas.D6 : (o.etapas.D6 && o.etapas.D6.estado)) : 'pendiente');
  // Una etapa D6 todavía «pendiente» no tiene piezas (0 seguro); si ya avanzó y el detalle no llegó, NO se sabe: no se afirma un cero.
  const filas = reales.map((o) => {
    const conteo = piezasDeCreativos(det[o.oferta_id]);
    const pendiente = estadoD6(o) === 'pendiente';
    return { id: o.oferta_id, piezas: conteo ? conteo.piezas : (pendiente ? 0 : null), estado: conteo ? conteo.estado : null };
  });
  const conPiezas = filas.filter((f) => f.piezas > 0);
  const sinContar = filas.filter((f) => f.piezas === null);
  const demoPiezas = ofertas.filter((o) => o && o.demo).map((o) => piezasDeCreativos(det[o.oferta_id])).filter((p) => p && p.piezas > 0).reduce((a, p) => a + p.piezas, 0);
  const notaDemo = demoPiezas ? `La oferta de demostración tiene ${plural(demoPiezas, 'pieza', 'piezas')}, pero no cuenta.` : '';
  if (conPiezas.length) {
    const bloqueada = filas.some((f) => f.estado === 'bloqueado' || f.estado === 'escalado');
    return { estado: bloqueada ? 'aviso' : 'ok', dato: `${listaCorta(conPiezas.map((f) => `${f.id}: ${plural(f.piezas, 'pieza', 'piezas')}`))}.`, nota: [bloqueada ? 'Hay una oferta con la etapa de anuncios bloqueada o a la espera de tu decisión.' : '', sinContar.length ? `No se pudieron contar las piezas de ${plural(sinContar.length, 'oferta', 'ofertas')}.` : '', notaDemo].filter(Boolean).join(' ') };
  }
  if (sinContar.length) return { estado: 'sin_datos', dato: `No se pudieron contar las piezas de ${plural(sinContar.length, 'oferta', 'ofertas')}: ${listaCorta(sinContar.map((f) => f.id))}.`, nota: ['Reintenta en unos segundos.', notaDemo].filter(Boolean).join(' ') };
  if (reales.length) return { estado: 'sin_datos', dato: 'Ninguna oferta real tiene piezas de anuncios todavía.', nota: [`${plural(reales.length, 'oferta real', 'ofertas reales')}; todavía no se prepararon piezas de anuncios.`, notaDemo].filter(Boolean).join(' ') };
  return { estado: 'sin_datos', dato: 'Todavía no hay ofertas reales.', nota: ['La fábrica trabaja sobre una oferta aprobada.', notaDemo].filter(Boolean).join(' ') };
}

function pasoFase(ofertas, fase, textos) {
  if (!Array.isArray(ofertas)) return { estado: 'sin_datos', dato: 'No se pudo leer la lista de ofertas.', nota: 'Reintenta en unos segundos.' };
  const reales = ofertas.filter((o) => o && !o.demo);
  const lista = reales.filter((o) => o.fase === fase).map((o) => o.oferta_id);
  const listas = fase === 'en_test' ? reales.filter((o) => o.fase === 'listo_para_activar').map((o) => o.oferta_id) : [];
  if (lista.length) return { estado: 'ok', dato: `${plural(lista.length, textos.uno, textos.varios)}: ${listaCorta(lista)}.`, nota: listas.length ? `Además, ${plural(listas.length, 'lista para activar', 'listas para activar')}.` : '' };
  if (listas.length) return { estado: 'aviso', dato: `${textos.ninguna} ${plural(listas.length, 'oferta lista para activar', 'ofertas listas para activar')}: ${listaCorta(listas)}.`, nota: textos.nota };
  return { estado: 'sin_datos', dato: textos.ninguna, nota: textos.nota };
}

/** Lo que se sabe de los robots EN SOMBRA (solo lectura; no son el sistema real): una línea honesta para la rueda, o null si no hay estado guardado. */
function pasoSombra(sombra) {
  if (!sombra) return null;
  const r = sombra.resumen;
  const nota = 'Son de solo lectura: miran y proponen, pero no vigilan ni frenan nada. El sistema real lo construye el equipo técnico (S-B).';
  if (sombra.situacion === 'vencido') return { estado: 'aviso', dato: `Latido vencido: ${plural(r.vencidos.length, 'robot en sombra no dio señal de vida a su hora', 'robots en sombra no dieron señal de vida a su hora')}.`, nota: `Puede ser que tu Mac estuviera dormida. ${nota}` };
  if (sombra.situacion === 'corriendo') return { estado: 'sin_datos', dato: sombra.deHoy ? `Robots en sombra corriendo (solo lectura): ${r.corrieronHoy.length} de ${r.conSombra.length} corrieron hoy.` : 'Hay robots en sombra programados, pero el estado guardado no es de hoy.', nota };
  return { estado: 'sin_datos', dato: r.corrieronHoy.length || r.soloManual.length ? 'No hay nada programado: los robots en sombra solo corrieron a mano.' : 'No hay nada programado: ningún robot en sombra corrió todavía.', nota };
}

function pasoRobots(robots, ahoraMs, sombra = null) {
  if (!robots || !Array.isArray(robots.robots) || robots.total === 0) {
    const som = pasoSombra(sombra);
    if (som) return som;
  }
  if (!robots || !Array.isArray(robots.robots) || robots.total === 0) return { estado: 'sin_datos', dato: 'Aún no hay registro de robots.', nota: 'Los 10 robots del plan existen solo en el catálogo; el registro real aparecerá cuando se construya el sistema de robots.' };
  const sinLatido = robots.robots.filter((r) => estadoLatido(r, ahoraMs).clave === 'vencido').length;
  const c = robots.conteos;
  const partes = [plural(robots.total, 'robot registrado', 'robots registrados'), `${c.vivo} en vivo`, `${c.sombra} en sombra (miran sin actuar)`, plural(c.apagado, 'apagado', 'apagados')];
  return { estado: sinLatido ? 'aviso' : 'ok', dato: `${partes.join(' · ')}.`, nota: sinLatido ? `${plural(sinLatido, 'robot sin señal de vida reciente', 'robots sin señal de vida reciente')}.` : '' };
}

function pasoAuditor(robots, sombra = null) {
  const enSombra = sombra && sombra.porId ? sombra.porId.auditor : null;
  if (!robots && enSombra && enSombra.estadoLatido !== 'no_aplica') {
    const res = enSombra.ultimoResultado || resultadoSombra(null);
    const acierto = sombra.auditoria && Number.isSafeInteger(sombra.auditoria.acierto_bp) ? sombra.auditoria.acierto_bp : null;
    return acierto !== null
      ? { estado: 'sin_datos', dato: `En sombra (solo lectura), el auditor midió un acierto de ${fmt.pct(acierto)}.`, nota: 'Todavía no es el auditor real: no baja de nivel a nadie.' }
      : { estado: 'sin_datos', dato: `El auditor corre en sombra (solo lectura): ${res ? res.texto.toLowerCase() : 'sin resultado todavía'}.`, nota: 'Todavía no mide acierto ni baja de nivel a nadie.' };
  }

  const a = robots && Array.isArray(robots.robots) ? robots.robots.find((r) => planoRobot(r.id).includes('auditor')) : null;
  if (a && a.aciertoBp !== null && a.aciertoBp !== undefined) return { estado: 'ok', dato: `Acierto medido: ${fmt.pct(a.aciertoBp)}.`, nota: 'Qué parte de las decisiones de los robots resultó correcta, juzgada con lo que pasó después.' };
  if (a) return { estado: 'sin_datos', dato: 'El auditor está registrado, pero aún no mide acierto.', nota: 'Lo producirá el auditor de resultados al juzgar cada decisión con lo que pasó después.' };
  return { estado: 'sin_datos', dato: 'No hay ningún auditor midiendo todavía.', nota: 'Lo producirá el auditor de resultados: juzgará cada decisión de los robots con lo que pasó después y bajará de nivel al que falle.' };
}

/**
 * Los 9 pasos con su estado REAL y una línea con el dato que haya (nunca una cifra inventada: sin archivo, «sin datos todavía» y qué lo producirá).
 * Entradas (todas opcionales; null = no se pudo leer): `pulido` (entradas normalizadas de la bitácora), `ofertas` (GET /ofertas), `detalles` ({oferta_id: GET /oferta/<id>}),
 * `robots` (registro normalizado de lib/robots.js), `paginas` (ctx.paginas()).
 * → [{ n, id, titulo, glosario?, estado:'ok'|'aviso'|'sin_datos', tono, etiqueta, icono, dato, nota, produce, ruta, verbo }]
 */
export function pasosRueda({ pulido = null, ofertas = null, detalles = null, robots = null, paginas = {}, ahoraMs = Date.now(), sombra = null } = {}) {
  const resultado = {
    cerebro: () => pasoPulido(pulido, 'abiertos'),
    fabrica: () => pasoCreativos(ofertas, detalles),
    jurado: () => ({ estado: 'sin_datos', dato: 'El jurado todavía no existe.', nota: 'Lo producirá el jurado: clientes ideales hechos con IA que votan a ciegas cada anuncio antes de gastar.' }),
    prueba: () => pasoFase(ofertas, 'en_test', { uno: 'campaña en prueba', varios: 'campañas en prueba', ninguna: 'Ninguna campaña en prueba todavía.', nota: 'Una oferta entra en prueba cuando su campaña se activa con poca plata.' }),
    escala: () => pasoFase(ofertas, 'escalando', { uno: 'oferta en escala', varios: 'ofertas en escala', ninguna: 'Ninguna oferta en escala todavía.', nota: 'Una oferta pasa a escala cuando vende de verdad en la prueba.' }),
    robots: () => pasoRobots(robots, ahoraMs, sombra),
    auditor: () => pasoAuditor(robots, sombra),
    pais: () => ({ estado: 'sin_datos', dato: 'Ningún ganador ha viajado a otro país todavía.', nota: 'Lo producirá la ruta de familia: una oferta original ya validada, con una versión por idioma y su tablero de lanzamiento.' }),
    aprende: () => pasoPulido(pulido, 'resueltos'),
  };
  return PASOS_RUEDA.map((p) => {
    const r = resultado[p.id]();
    const inf = infoEstadoRueda(r.estado);
    return { n: p.n, id: p.id, titulo: p.titulo, glosario: p.glosario || null, estado: r.estado, tono: inf.tono, etiqueta: inf.texto, icono: inf.icono, dato: r.dato, nota: r.nota || '', ruta: rutaDelPaso(p, paginas), verbo: p.verbo };
  });
}

/** Cuántos pasos hay en cada estado: { ok, aviso, sin_datos, total }. */
export function resumenRueda(pasos) {
  const lista = Array.isArray(pasos) ? pasos : [];
  const c = { ok: 0, aviso: 0, sin_datos: 0 };
  for (const p of lista) c[p.estado in c ? p.estado : 'sin_datos'] += 1;
  return { ...c, total: lista.length };
}
