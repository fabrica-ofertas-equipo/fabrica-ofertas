// lib/avisos.js — lógica pura (datos → modelo de vista) de #/avisos: las alertas abiertas con su severidad, el canal al celular (hoy sin elegir), el resumen diario
// (hoy inexistente) y qué avisa cada robot. Las alertas salen de empresa/datos/alertas.jsonl por GET /finanzas (esquema contratos/alertas.schema.json 1.0.0).
// Sin DOM: probable con `node --test`. Todo texto que viene de un archivo (regla, acción sugerida, valores) es dato no confiable: la página lo pinta con textContent.
import { fmt } from '../ui.js';
import { normalizarAlertas } from './finanzas.js';
import { ROBOTS, estadoCodigo } from './robots.js';
import { NOMBRE_REGLA_AUSENCIA } from './ausencia.js';

// ───────────────────────── severidad ─────────────────────────

/**
 * Los cuatro niveles del esquema de alertas (info · amarilla · naranja · roja), de más a menos grave. `tono` es el de lib/finanzas.js (naranja = «grave»).
 * `donde` es la PROPUESTA de enrutado (hipótesis; el dueño no la ha decidido): hasta que haya canal, todo se ve solo aquí.
 */
export const SEVERIDADES = [
  { clave: 'roja', etiqueta: 'Roja', tono: 'error', icono: 'octogono', significa: 'Algo grave que pide tu decisión ya: un límite roto, una cuenta que dejó de pagar o un dato que no cuadra.', donde: 'Celular y correo además del panel, sin silencio nocturno. Si nadie la reconoce se repite cada 4 horas, hasta 3 veces.' },
  { clave: 'naranja', etiqueta: 'Naranja · pausa', tono: 'grave', icono: 'rombo-alerta', significa: 'Una oferta debería pausarse (por ejemplo, porque hay demasiadas disputas).', donde: 'Celular y panel.' },
  { clave: 'amarilla', etiqueta: 'Amarilla', tono: 'aviso', icono: 'alerta', significa: 'Algo se desvía de lo normal y conviene mirarlo, pero no urge.', donde: 'Resumen diario de las 08:30 y panel.' },
  { clave: 'info', etiqueta: 'Información', tono: 'info', icono: 'info', significa: 'Un dato para que lo sepas; no pide nada.', donde: 'Solo el panel.' },
];

const POR_TONO = { error: 'roja', grave: 'naranja', aviso: 'amarilla', info: 'info', neutro: 'otra' };
/** Clave de severidad de una alerta ya normalizada (por su tono): 'roja' | 'naranja' | 'amarilla' | 'info' | 'otra'. */
export const claveSeveridad = (alerta) => POR_TONO[alerta && alerta.tono] || 'otra';

// ───────────────────────── reglas en lenguaje de negocio ─────────────────────────

/** Nombre humano de las reglas de alerta conocidas (docs/04 §5 y departamentos/12 Anexo A). Las desconocidas se muestran con su código. */
export const NOMBRE_REGLA = {
  'F1-A01': 'Demasiados reembolsos',
  'F1-A02': 'Demasiadas disputas (la oferta debería pausarse)',
  'F1-A03': 'Comisión de cobro fuera de lo normal',
  'F1-A04': 'Gasto cerca de su tope',
  'F1-A05': 'Retorno por debajo del punto de equilibrio',
  'F1-A06': 'Datos viejos o conciliación que no cuadra',
  'F1-A07': 'Saldo de Stripe negativo, pago fallido o caja corta',
  'F1-A08': 'Disputa abierta o tarifas desactualizadas',
  'F2-A01': 'Datos de Meta desactualizados',
  'F2-A02': 'Eventos de Stripe desactualizados',
  'F2-A03': 'Movimientos de saldo de Stripe desactualizados',
  'F2-A04': 'Pedidos que no coinciden con Stripe',
  'F2-A05': 'Gasto distinto del que informa Meta',
  'F2-A06': 'Compras de Meta y de Stripe que no coinciden',
  'F2-A07': 'Pocas ventas atribuidas a un anuncio',
  'F2-A08': 'Gasto del día por encima de lo posible',
  'F2-A09': 'Gasto cerca de su tope o pérdida acumulada alta',
  'F2-A10': 'Costo de IA demasiado alto',
  'F2-A11': 'Reembolsos y disputas',
  'F2-A12': 'Camino del comprador con números incoherentes',
  'F2-A13': 'Calidad de la señal de compra baja',
  'F2-A14': 'Demasiado gasto en nichos de riesgo amarillo',
  'F2-A15': 'Descubrimiento descompensado',
  'F2-A16': 'Conexión crítica caída o estado viejo',
  'F2-A17': 'El panel no recibe señales de vida: datos sin actualizar',
};
export const nombreRegla = (id) => {
  if (typeof id !== 'string') return null;
  if (Object.prototype.hasOwnProperty.call(NOMBRE_REGLA, id)) return NOMBRE_REGLA[id];
  return Object.prototype.hasOwnProperty.call(NOMBRE_REGLA_AUSENCIA, id) ? NOMBRE_REGLA_AUSENCIA[id] : null;   // reglas «F2-AUS-*» del productor de alertas
};

// ───────────────────────── alertas ─────────────────────────

/**
 * Modelo de las alertas a partir de `GET /finanzas` (`datos.alertas`). Las abiertas (y reconocidas) primero, de más a menos graves; las cerradas aparte.
 * → { hay, total, abiertas:[…], cerradas:[…], conteo:{roja, naranja, amarilla, info, otra} }. Cada alerta suma `clave`, `nombre` y `titulo` (nombre de la regla o su código).
 */
export function modeloAlertas(datos) {
  const crudas = datos && typeof datos === 'object' && Array.isArray(datos.alertas) ? datos.alertas : [];
  const todas = normalizarAlertas(crudas).map((a) => ({ ...a, clave: claveSeveridad(a), nombre: nombreRegla(a.regla_id), titulo: nombreRegla(a.regla_id) || a.regla_id || 'Alerta sin regla' }));
  const abiertas = todas.filter((a) => a.abierta);
  const conteo = { roja: 0, naranja: 0, amarilla: 0, info: 0, otra: 0 };
  for (const a of abiertas) conteo[a.clave] += 1;
  return { hay: crudas.length > 0, total: crudas.length, abiertas, cerradas: todas.filter((a) => !a.abierta), conteo };
}

/** «Valor actual 1,8 · límite 1,75» o «Valor actual 1,8 · sin límite fijado» (nunca se pinta como verde). null si no hay valor. */
export function fraseValor(a) {
  if (!a || a.valor === null || a.valor === undefined) return null;
  return `Valor actual ${a.valor} · ${a.sinUmbral ? 'sin límite fijado' : `límite ${a.umbral}`}`;
}

// ───────────────────────── el canal al celular ─────────────────────────

/** La decisión sigue sin tomar (decisiones-del-dueno, pendiente 3). Cuando exista un archivo con el canal elegido, `estadoCanal(config)` lo reflejará. */
export function estadoCanal(config = null) {
  const elegido = Boolean(config && typeof config === 'object' && config.canal);
  if (elegido) return { elegido: true, tono: 'ok', texto: 'Elegido', titulo: String(config.canal) };
  return { elegido: false, tono: 'aviso', texto: 'Sin elegir', titulo: 'Falta elegir el canal de avisos al celular' };
}

export const EXPLICACION_CANAL = [
  { id: 'dos', titulo: 'Siempre dos canales', texto: 'Un aviso importante nunca depende de un solo camino: va por un canal del celular (Telegram solo de salida u otro servicio) y por correo. Si uno falla, el otro llega.', ayuda: 'dos_canales' },
  { id: 'plantilla', titulo: 'Forma fija, sin texto libre', texto: 'Cada aviso lleva solo gravedad, código de la regla, oferta y hora. Nunca lleva texto escrito por una IA ni por terceros, ni enlaces con clave de acceso, ni identificadores de clientes, ni datos del nicho: así un aviso no puede filtrar nada.', ayuda: 'plantilla_fija' },
  { id: 'importes', titulo: 'Importes por correo, porcentajes al celular', texto: 'Las cifras de dinero viajan en el correo; al celular llega el porcentaje del tope. Telegram, si lo eliges, es solo de salida: no acepta mensajes entrantes ni órdenes.' },
  { id: 'estado', titulo: 'Qué hay hoy', texto: 'El vigilante de señales de vida ya sabe enviar por dos canales, pero con direcciones de ejemplo y sin servicio de avisos al celular elegido. Hasta que lo decidas, nada te avisa fuera de este panel.' },
];

export const PLANTILLA = {
  muestra: '<gravedad> · <código de la regla> · <oferta> · <hora> · <% del tope>',
  campos: ['Gravedad', 'Código de la regla', 'Oferta', 'Hora', 'Porcentaje del tope (celular) o importe (correo)'],
  prohibido: ['Texto libre de una IA o de terceros', 'Claves de acceso ni enlaces con clave', 'Identificadores de clientes o de sesiones de Stripe', 'Texto del nicho o nombres de producto'],
};

/** Qué decide el dueño para que los avisos existan (decisiones-del-dueno.md, pendiente 3). */
export const DECISION_PENDIENTE = {
  titulo: 'Elegir el canal de avisos al celular',
  opciones: ['Telegram solo de salida (recomendado: una clave que solo puede enviar mensajes)', 'Otro servicio de avisos al celular'],
  siguiente: 'Con el canal elegido se prueba la entrega por los dos canales y recién entonces se encienden el vigía de pagos y el informe diario.',
};

// ───────────────────────── resumen diario ─────────────────────────

export const RESUMEN_DIARIO = {
  hora: '08:30',
  contiene: ['Ventas del día', 'Gasto en anuncios', 'Alertas abiertas'],
  produce: 'El robot «Informe del día»',
  falta: ['Elegir el canal de avisos al celular', 'Programar el informe para que se componga y se envíe cada día (lo hace el equipo técnico, S-B)'],
};

// ───────────────────────── qué avisa cada robot ─────────────────────────

const AVISADORES_BASE = [
  { id: 'vigia', robot: 'vigia', quien: 'Vigía de pagos', avisa: 'Cuando una cuenta publicitaria deja de gastar por un pago: cuenta bloqueada, tope de gasto alcanzado o forma de pago que falla. Además pausa.', cuando: 'Al momento (una revisión liviana mira cada 15 minutos con campañas activas)', severidad: 'roja' },
  { id: 'alarma', robot: 'alarma', quien: 'Alarma de cansancio', avisa: 'Cuando un anuncio ganador se cansa (los últimos 3 días rinden peor que los 7 anteriores) y pide relevo a la fábrica antes de que caiga.', cuando: 'A las 08:05', severidad: 'amarilla' },
  { id: 'informe', robot: 'informe', quien: 'Informe del día', avisa: 'Un solo mensaje con ventas, gasto y alertas del día.', cuando: 'A las 08:30', severidad: 'info' },
  { id: 'watchdog', robot: null, quien: 'Vigilante de señales de vida', avisa: 'Cuando el sistema deja de dar señales de vida: pausa la cuenta de Meta y avisa por correo y al celular.', cuando: 'Revisa cada pocos minutos', severidad: 'roja', existe: 'Ya existe; falta elegir el servicio de avisos al celular y poner direcciones reales.' },
];

/** Lo que avisa cada robot, con el estado de su código (comprobado como en #/robots). `severidad` apunta a una entrada de SEVERIDADES. */
export function avisadores(sistema = null) {
  return AVISADORES_BASE.map((a) => {
    const robot = a.robot ? ROBOTS.find((r) => r.id === a.robot) : null;
    const est = robot ? estadoCodigo(robot, sistema) : { clave: 'parcial', texto: 'Parcial', tono: 'info', detalle: a.existe || '', medicion: null };
    return { ...a, sev: SEVERIDADES.find((s) => s.clave === a.severidad), estado: est, detalle: robot ? (est.detalle || '') : (a.existe || '') };
  });
}

// ───────────────────────── atención y métricas ─────────────────────────

/** Avisos de la pantalla, de más a menos graves. El canal sin elegir pesa como «aviso» (decisión pendiente tuya). */
export function atencionAvisos(modelo, canal = estadoCanal()) {
  const items = [];
  const c = modelo ? modelo.conteo : { roja: 0, naranja: 0, amarilla: 0 };
  const primera = (clave) => (modelo && modelo.abiertas.find((a) => a.clave === clave)) || null;
  const plural = (n, s, p) => (n === 1 ? s : p);
  if (c.roja) items.push({ tono: 'critico', titulo: `${c.roja} ${plural(c.roja, 'alerta roja abierta', 'alertas rojas abiertas')}`, detalle: (primera('roja') && (primera('roja').accion_sugerida || primera('roja').titulo)) || undefined });
  if (c.naranja) items.push({ tono: 'grave', titulo: `${c.naranja} ${plural(c.naranja, 'alerta naranja abierta', 'alertas naranjas abiertas')}: una oferta debería pausarse`, detalle: (primera('naranja') && (primera('naranja').accion_sugerida || primera('naranja').titulo)) || undefined });
  if (c.amarilla) items.push({ tono: 'aviso', titulo: `${c.amarilla} ${plural(c.amarilla, 'alerta amarilla abierta', 'alertas amarillas abiertas')}`, detalle: (primera('amarilla') && (primera('amarilla').accion_sugerida || primera('amarilla').titulo)) || undefined });
  if (!canal.elegido) items.push({ tono: 'aviso', titulo: DECISION_PENDIENTE.titulo, detalle: 'Sin canal, nada te avisa fuera de este panel: ni el vigía de pagos ni el informe del día pueden salir al celular. Es una decisión tuya pendiente y necesita dos canales (celular y correo).' });
  return items;
}

/** Métricas de la cabecera. `valor` null = «—» (sin dato). */
export function metricasAvisos(modelo, canal = estadoCanal(), leido = true, informe = null) {
  const m = modelo || { abiertas: [], conteo: { roja: 0, naranja: 0, amarilla: 0, info: 0 } };
  const graves = m.conteo.roja + m.conteo.naranja;
  const peor = m.conteo.roja ? 'critico' : m.conteo.naranja ? 'grave' : m.conteo.amarilla ? 'aviso' : null;
  return [
    { id: 'abiertas', etiqueta: 'Alertas abiertas', valor: leido ? m.abiertas.length : null, tono: peor || (leido ? 'ok' : null), contexto: !leido ? 'sin datos' : m.abiertas.length ? [[m.conteo.roja, 'roja', 'rojas'], [m.conteo.naranja, 'naranja', 'naranjas'], [m.conteo.amarilla, 'amarilla', 'amarillas']].map(([n, uno, varios]) => `${n} ${n === 1 ? uno : varios}`).concat(`${m.conteo.info} de información`).join(' · ') : (m.hay ? 'ninguna abierta' : 'ninguna registrada: un cero no prueba que todo esté bien'), ayuda: 'estado_alerta' },
    { id: 'graves', etiqueta: 'Rojas y naranjas', valor: leido ? graves : null, tono: graves ? (m.conteo.roja ? 'critico' : 'grave') : null, contexto: graves ? 'piden decisión' : 'ninguna pide decisión', ayuda: 'severidad_alerta' },
    { id: 'canal', etiqueta: 'Canal al celular', valor: canal.texto, tono: canal.tono, contexto: canal.elegido ? canal.titulo : 'decisión pendiente tuya', ayuda: 'canal_avisos' },
    informe
      ? { id: 'resumen', etiqueta: 'Resumen diario', valor: 'Compuesto', tono: null, contexto: `las ${informe.hora || RESUMEN_DIARIO.hora}: todavía no se envía, falta el canal y quien lo programe`, ayuda: 'resumen_diario' }
      : { id: 'resumen', etiqueta: 'Resumen diario', valor: 'No existe', tono: null, contexto: `lo enviará el robot Informe del día a las ${RESUMEN_DIARIO.hora}`, ayuda: 'resumen_diario' },
  ];
}

/** Hora legible de una alerta: «hace 5 min» (con la absoluta en el title). */
export const horaAlerta = (a, ahoraMs = Date.now()) => (a && a.ts ? { relativa: fmt.relativo(a.ts, ahoraMs), absoluta: fmt.fecha(a.ts, { segundos: true }) } : { relativa: '—', absoluta: '—' });
