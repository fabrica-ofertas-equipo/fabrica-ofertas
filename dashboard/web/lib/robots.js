// lib/robots.js — lógica pura (datos → modelo de vista) de #/robots: el catálogo de los 10 robots (know-how §5, mapeo §2), su horario en un día de 24 h,
// la semana tipo (know-how §8), las seis reglas de oro (know-how §9) y la lectura TOLERANTE del registro real (empresa/robots.yaml, formato aún sin fijar).
// Sin DOM: probable con `node --test`. Nada de lo que hay aquí enciende, apaga ni cambia un robot.
import { fmt } from '../ui.js';

// ───────────────────────── catálogo ─────────────────────────

/**
 * Los 10 programas del sistema (el último es el auditor, que controla a los demás).
 *  · `codigo`: 'no_construido' | 'parcial' (algo existe en código; `existe` dice qué). Lo que se apoya en el motor se verifica con `sistema.motor_disponible`
 *    (`verifica: 'motor'`): si el panel no lo puede comprobar, el estado pasa a «planeado» en vez de afirmar que existe.
 *  · `reloj`: cómo se dibuja en la línea de 24 h (ver `segmentosReloj`).
 *  · `tecnico`: lo que va en «Detalle técnico» (acción, gate y nivel, topes, qué falta).
 * Las horas son del reloj del mercado y son HIPÓTESIS hasta calibrarlas (mapeo §2).
 */
export const ROBOTS = [
  {
    id: 'escalera', numero: 1, nombre: 'Escalera de escala', termino: 'robot_escalera', pieza: 'Testeo y escala',
    hace: 'Sube el presupuesto de lo que ya vende y lo baja si no rinde.',
    mas: 'Empieza duplicando el presupuesto (×2); triplicarlo o quintuplicarlo solo cuando el auditor demuestre que las subas aciertan. Si no rinde, lo baja un 30 %. Nunca apaga nada dentro de la campaña de escala.',
    horario: 'Cada 30 min', reloj: { tipo: 'cada', min: 30 },
    codigo: 'parcial', verifica: 'motor',
    existe: 'La operación diaria ya decide si cortar, seguir o esperar, y ya existe la función que sube el presupuesto con topes. Falta el robot en sí: hoy «escalar» queda anotado pero no se ejecuta.',
    tecnico: { ejecuta: 'Código (hoy el bucle de escalado pasa por un agente de IA, demasiado lento para 30 min)', accion: 'reducir y aumentar_presupuesto', nivel: 'Reducir: automático desde el nivel 2. Aumentar: automático solo en el nivel 3, con evidencia y en verde; en los niveles 0 a 2, con tu firma.', topes: 'Paso máximo por subida, horas mínimas entre subidas, techo teórico de Meta (1,75×), cambios por hora, gasto diario, caja y tope de la cuenta.', falta: 'Guías de trabajo de las etapas de operación y optimización, verificación del porcentaje de paso en el control de seguridad del sistema y límites firmados.', codigo: 'engine.d8 · meta.subir_presupuesto · escala.py (por construir)' },
  },
  {
    id: 'salvavidas', numero: 2, nombre: 'Salvavidas', termino: 'robot_salvavidas', pieza: 'Testeo y escala',
    hace: 'Arranca chico y suma a su presupuesto lo vendido en el día, para aprovechar las horas pico de cada país.',
    mas: 'Se calcula sobre el ingreso neto (no el bruto) y con tope; solo después de que la escalera haya dado 15 pasos buenos.',
    horario: 'Cada 15 min', reloj: { tipo: 'cada', min: 15 },
    codigo: 'no_construido', existe: '',
    tecnico: { ejecuta: 'Código', accion: 'aumentar_presupuesto dentro del día', nivel: 'Nivel 3, tras 15 pasos de la escalera con al menos 80 % buenos [hipótesis].', topes: 'Los de la escalera más tope de surfeo y máximo 2 cambios por hora.', falta: 'La escalera en el nivel 3 con acierto medido.' },
  },
  {
    id: 'guardia', numero: 3, nombre: 'Guardia nocturno', termino: 'robot_guardia', pieza: 'Testeo y escala',
    hace: 'De madrugada lee lo que hicieron los demás robots y ajusta el tope de costo de a poco.',
    mas: 'Cuatro vueltas entre 01:30 y 07:30. Las horas exactas de cada vuelta se calculan (no están en el método original) y se van ajustando.',
    horario: '01:30 – 07:30 · 4 vueltas', reloj: { tipo: 'banda', desde: '01:30', hasta: '07:30', vueltas: ['01:30', '03:30', '05:30', '07:30'] },
    codigo: 'no_construido', existe: '',
    tecnico: { ejecuta: 'Código', accion: 'ajustar_costo (operación nueva del guardia)', nivel: 'Nivel 3.', topes: 'Paso máximo del tope de costo, cota inferior y superior.', falta: 'El tope de costo (cost cap) todavía no existe en el formato de las campañas: hoy se crean sin tope.' },
  },
  {
    id: 'cola', numero: 4, nombre: 'Cola de testeo', termino: 'robot_cola', pieza: 'Testeo y escala',
    hace: 'Prende los conjuntos nuevos de cada idioma: es el lanzamiento del día.',
    mas: 'Solo prende lo que tiene el visto bueno de cumplimiento vigente, con la infraestructura en verde y respetando los frenos de la empresa. Si algo falla, no prende nada.',
    horario: '00:10', reloj: { tipo: 'puntos', horas: ['00:10'] },
    codigo: 'no_construido', existe: '',
    tecnico: { ejecuta: 'Un programa prepara y activa; el visto bueno (sello) lo emite el programa de cumplimiento', accion: 'gastar (borrador en pausa) y activar_campana', nivel: 'Activar ya no pide tu firma (decisión J2), pero conserva el visto bueno de cumplimiento (X1) vigente, el chequeo antes de lanzar en verde, la pausa general y los dos frenos de empresa.', topes: 'Objetos exactos del sello, gasto diario global y pérdida acumulada.', falta: 'La fábrica de creativos en tanda y el protocolo de lanzamiento de un día.' },
  },
  {
    id: 'perfil', numero: 5, nombre: 'Perfil por idioma', termino: 'robot_perfil', pieza: 'Testeo y escala',
    hace: 'Calcula la meta, el tope y la fase de cada idioma: crece, estable, se cansa o cae.',
    mas: 'Es de solo lectura: alimenta a los demás robots. Los límites de cada fase todavía no están ajustados.',
    horario: '23:40', reloj: { tipo: 'puntos', horas: ['23:40'] },
    codigo: 'no_construido', existe: '',
    tecnico: { ejecuta: 'Código', accion: 'ninguna (lectura)', nivel: 'Nivel 0, en sombra desde el inicio.', topes: 'No actúa.', falta: 'Medición horaria por idioma.' },
  },
  {
    id: 'alarma', numero: 6, nombre: 'Alarma de cansancio', termino: 'robot_alarma', pieza: 'Fábrica de anuncios',
    hace: 'Compara los últimos 3 días con los 7 anteriores y pide relevo a la fábrica antes de que el ganador caiga.',
    mas: 'Cumple la regla de oro 6. Avisa: el pedido a la fábrica lo redacta una IA y lo revisa cumplimiento.',
    horario: '08:05', reloj: { tipo: 'puntos', horas: ['08:05'] },
    codigo: 'no_construido', existe: 'Está descrita en la operación diaria, pero todavía no tiene código.',
    verifica: 'motor',
    tecnico: { ejecuta: 'Código para detectar; una IA redacta el pedido', accion: 'pedido_creativos a D6', nivel: 'Pedidos a la fábrica: con revisión en el nivel 2, automático en el nivel 3 con tope de créditos.', topes: 'Pedidos abiertos máximos, cantidad máxima por pedido, ángulos permitidos.', falta: 'Programar la detección y ajustar a partir de cuándo se considera «cansado».' },
  },
  {
    id: 'vigia', numero: 7, nombre: 'Vigía de pagos', termino: 'robot_vigia', pieza: 'Robots',
    hace: 'Si una cuenta publicitaria deja de gastar por un pago, avisa al celular. El nuestro, además, pausa.',
    mas: 'Se apoya en una revisión liviana (cada 15 minutos con campañas activas) y en el vigilante de señales de vida. Falta elegir el canal del celular y leer el saldo como número.',
    horario: 'Siempre · revisión cada 15 min', reloj: { tipo: 'siempre' },
    codigo: 'parcial', verifica: 'infra', itemsInfra: ['M-02', 'M-03', 'C-09'],
    existe: 'La revisión liviana del chequeo antes de lanzar (estado de la cuenta, tope de gasto y forma de pago) y el vigilante que pausa ya existen. Falta el aviso al celular y la lectura del saldo.',
    tecnico: { ejecuta: 'Código', accion: 'pausar (la única escritura sin firma)', nivel: 'Nivel 0.', topes: 'Pausa general e interruptor de emergencia de tres capas. Reanudar siempre es humano.', falta: 'Elegir el canal de push (Telegram solo saliente u otro) y una alerta «gasto 0 con presupuesto > 0 por N horas».' },
  },
  {
    id: 'bandeja', numero: 8, nombre: 'Bandeja', termino: 'robot_bandeja', pieza: 'Robots',
    hace: 'Responde comentarios, mensajes y correos con tacto, en cada idioma y con el tono de la marca.',
    mas: 'Solo con modelos de respuesta aprobados por cumplimiento; en salud y dinero, sin consejo médico ni financiero. Hoy solo existen la entrega y el soporte básico de poscompra.',
    horario: '07:00 y 19:00', reloj: { tipo: 'puntos', horas: ['07:00', '19:00'] },
    codigo: 'no_construido', existe: '',
    tecnico: { ejecuta: 'IA para clasificar + plantillas aprobadas', accion: 'responder / ocultar', nivel: 'Nivel 2 o superior, con revisión.', topes: 'Plantillas aprobadas y clave de acceso con los permisos mínimos.', falta: 'Fase tardía: depende de la entrega real y del correo transaccional.' },
  },
  {
    id: 'informe', numero: 9, nombre: 'Informe del día', termino: 'robot_informe', pieza: 'Cerebro y avisos',
    hace: 'Resume ventas, gasto y alertas en un solo mensaje al celular.',
    mas: 'Los importes van en el correo y los porcentajes en el celular; el texto es una plantilla fija. Depende de elegir el canal de avisos.',
    horario: '08:30', reloj: { tipo: 'puntos', horas: ['08:30'] },
    codigo: 'no_construido', existe: '',
    tecnico: { ejecuta: 'Código (cifras por plantilla)', accion: 'ninguna (notificación)', nivel: 'Nivel 0.', topes: 'Cifras por plantilla; informar no mueve dinero.', falta: 'Canal de avisos y el productor de alertas (dashboard.alertas).' },
  },
  {
    id: 'auditor', numero: 10, nombre: 'Auditor', termino: 'robot_auditor', pieza: 'Robots',
    hace: 'Juzga cada decisión de los otros robots con lo que pasó después y baja de nivel al que falla.',
    mas: 'Es el que hace cumplir «todo robot se audita». En el método original, 3 de cada 4 cortes aciertan y solo 1 de cada 3 subas (cifra declarada por su autor, sin verificar). Su frecuencia original va de cada hora a cada 3 h; nuestra ventana de acierto propuesta es de 72 a 96 h.',
    horario: 'Cada hora', reloj: { tipo: 'cada', min: 60 },
    codigo: 'no_construido', existe: 'Las decisiones de la operación diaria ya quedan anotadas con su regla y sus parámetros: es la base sobre la que va a juzgar.',
    tecnico: { ejecuta: 'Código', accion: 'calificar y degradar el nivel de un robot', nivel: 'Nivel 1 en sombra, luego nivel 2.', topes: 'Acierto mínimo propuesto: 50 % en cortes y 60 % en subas [hipótesis].', falta: 'Banco de decisiones con ventana de resultado y acierto medido.' },
  },
];

/** Lo que NO es un robot de los 10 pero ya corre (o está listo) como código: leído del último estado de los parámetros cuando existen. */
export const PROGRAMAS_EXISTENTES = [
  { id: 'watchdog', nombre: 'Vigilante de señales de vida', hace: 'Si el sistema deja de dar señales de vida, pausa la cuenta de Meta por su cuenta. No puede activar nada.', param: 'watchdog.latido_cada_min', formato: (v) => `Señal de vida cada ${v} min`, evidencia: ['C-09'] },
  { id: 'sonda', nombre: 'Revisión liviana de cuentas', hace: 'Con campañas activas, comprueba cada pocos minutos que Meta y Stripe sigan funcionando: acceso, estado de la cuenta, tope de gasto y clave de cobros.', param: 'infra.hc_sonda_ligera_min', formato: (v) => `Cada ${v} min con campañas activas`, evidencia: ['M-02', 'M-03', 'S-01'] },
  { id: 'monitor', nombre: 'Vigilancia después de activar', hace: 'Lee Meta, pausa de inmediato cualquier anuncio rechazado y, con dos rechazos en 7 días, pide congelar los lanzamientos.', param: null, formato: () => '1, 6, 24, 48 y 72 h después de activar', evidencia: [] },
  { id: 'd8', nombre: 'Operación diaria', hace: 'Lee los datos de cada anuncio, decide si sigue, se corta o se espera, y solo pausa; no sube ni activa sin firma.', param: 'optimizacion.lectura_horas', param2: 'optimizacion.hora_decision', formato: (v, v2) => `Lectura cada ${v} h${v2 ? ` · decisión a las ${v2}` : ''}`, evidencia: [] },
  { id: 'etl', nombre: 'Carga de datos de Meta y Stripe', hace: 'Trae a la base lo gastado en Meta y lo cobrado en Stripe para que el panel y los robots decidan con lo cobrado de verdad.', param: 'dashboard.etl_meta_cada_h', param2: 'dashboard.etl_stripe_backfill_hora', formato: (v, v2) => `Meta cada ${v} h${v2 ? ` · repaso de Stripe a las ${v2} (hora universal)` : ''}`, evidencia: [] },
];

// ───────────────────────── semana tipo y reglas de oro ─────────────────────────

/** Semana tipo (know-how §8) con el motor nuestro que la implementa (mapeo §2). Índice 0 = lunes. */
export const SEMANA = [
  { dia: 'Lunes', corto: 'Lun', tema: 'Cierre semanal', hace: 'Qué enfoque ganó en cada idioma.', resultado: 'Ranking de enfoques', motor: 'Finanzas y aprendizaje (cuadro de rendimiento)' },
  { dia: 'Martes', corto: 'Mar', tema: 'Tanda nueva', hace: 'Variaciones de los ganadores.', resultado: 'Piezas listas para el testeo', motor: 'Fábrica de creativos, modo tanda (relevos)' },
  { dia: 'Miércoles', corto: 'Mié', tema: 'Jurado', hace: 'El jurado se ajusta con lo cobrado.', resultado: 'Un jurado más preciso', motor: 'Ajuste del jurado' },
  { dia: 'Jueves', corto: 'Jue', tema: 'Países', hace: 'Avanza la lista de control del idioma nuevo.', resultado: 'Un mercado más cerca', motor: 'Mercados y lanzamiento de idioma' },
  { dia: 'Viernes', corto: 'Vie', tema: 'Reglas', hace: 'Lo aprendido con plata se vuelve regla nueva o ajustada.', resultado: 'Reglas actualizadas (las aprueba el dueño)', motor: 'Cerebro: propuesta que firma el dueño' },
  { dia: 'Sábado', corto: 'Sáb', tema: 'Piloto automático', hace: 'Los robots solos, con techo de gasto.', resultado: 'Cero intervención', motor: 'Condiciones para subir de nivel' },
  { dia: 'Domingo', corto: 'Dom', tema: 'Orden del cerebro', hace: 'Se limpia y ordena la memoria.', resultado: 'La semana arranca sabiendo', motor: 'Jardinero del cerebro (propone; el dueño aprueba)' },
];

/** Índice 0–6 (lunes=0) del día de `ahoraMs` en hora local. */
export function indiceDia(ahoraMs = Date.now()) {
  const d = new Date(ahoraMs);
  if (Number.isNaN(d.getTime())) return -1;
  return (d.getDay() + 6) % 7;
}

export const PRINCIPIO_AUDITORIA = {
  titulo: 'Todo robot se audita',
  texto: 'Ninguna decisión automática queda sin control. El auditor juzga cada decisión con lo que pasó después y baja de nivel al robot que falla; las subas de presupuesto se habilitan por etapas, según el acierto medido. Las reglas las escribe y las cambia solo el dueño: el auditor propone, tú apruebas.',
};

/** Las seis reglas de oro (know-how §9, «aprendidas con plata») y cómo las hace cumplir nuestro sistema (mapeo §3.3). */
export const REGLAS_DE_ORO = [
  { n: 1, titulo: 'La escala no se toca por dentro', negocio: 'En la campaña de escala solo se sube o se baja el presupuesto: nunca se apagan conjuntos ni anuncios por dentro.', cumple: 'El robot de escala solo tiene permiso de subir y bajar presupuesto. Salvedad nuestra: la regla de corte de la operación diaria solo actúa con cero compras a 6 veces el punto de equilibrio, y un anuncio rechazado por Meta se pausa igual.' },
  { n: 2, titulo: 'El ganador sigue en testeo', negocio: 'Cuando un anuncio pasa a escala no se saca del testeo: si se lo saca, se pierde la señal.', cumple: 'La graduación copia el anuncio a la escala y deja el original corriendo en el testeo.' },
  { n: 3, titulo: 'Un día sin ventas no dice nada', negocio: 'Se mira la tendencia de 3 días, no un día suelto.', cumple: 'Escalar o bajar exige la tendencia de 3 días. Excepción que decidiste tú (J3): en el lanzamiento, un día sin ninguna venta —con el presupuesto del día gastado— da de baja la oferta; si Meta no entregó, no cuenta.' },
  { n: 4, titulo: 'Ganancia antes que volumen', negocio: 'Gastar mucho solo cuando el retorno es bueno (meta conversada: entre 2 y 3 dólares vendidos por cada dólar gastado en anuncios).', cumple: 'La escala solo corre sobre ofertas con economía factible y validadas. Frenos de empresa propuestos por ti (J4): techo de 300 USD por día y pausa automática a 3.000 USD perdidos; los fijas con tu firma.' },
  { n: 5, titulo: 'Todo robot se audita', negocio: 'Ninguna decisión automática sin control.', cumple: 'El auditor califica cada decisión con lo que pasó después y degrada el nivel del robot que falla. Subir de nivel siempre lo firma el dueño.' },
  { n: 6, titulo: 'Relevo antes del cansancio', negocio: 'El reemplazo se produce antes de que el ganador caiga: siempre hay un banco de suplentes.', cumple: 'La alarma de cansancio (08:05) pide relevo a la fábrica; los suplentes pasan por cumplimiento antes de que hagan falta.' },
];

// ───────────────────────── reloj de 24 horas ─────────────────────────

const RE_HORA = /^([01]?\d|2[0-3]):([0-5]\d)$/;

/** «01:30» → 90 (minutos desde la medianoche); texto inválido → null. */
export function horaAMin(hora) {
  const m = RE_HORA.exec(typeof hora === 'string' ? hora.trim() : '');
  return m ? Number(m[1]) * 60 + Number(m[2]) : null;
}

/** Minutos → % del día con 3 decimales (0–100). */
export function minAPct(min) {
  if (!Number.isFinite(min)) return null;
  return Math.round((Math.max(0, Math.min(1440, min)) / 1440) * 100000) / 1000;
}

/**
 * Cómo se dibuja un robot en la línea de 24 h: [{tipo:'banda'|'marca'|'continuo'|'siempre', izq, ancho?, hora?, inferida?}] con izq/ancho en % del día.
 * `cada` y `siempre` ocupan todo el día (el texto del horario dice cada cuánto). Un reloj inválido no dibuja nada.
 */
export function segmentosReloj(reloj) {
  if (!reloj || typeof reloj !== 'object') return [];
  if (reloj.tipo === 'cada') return Number.isFinite(reloj.min) && reloj.min > 0 ? [{ tipo: 'continuo', izq: 0, ancho: 100, cadaMin: reloj.min }] : [];
  if (reloj.tipo === 'siempre') return [{ tipo: 'siempre', izq: 0, ancho: 100 }];
  if (reloj.tipo === 'puntos') {
    return (Array.isArray(reloj.horas) ? reloj.horas : []).map((h) => ({ h, m: horaAMin(h) })).filter((x) => x.m !== null).map((x) => ({ tipo: 'marca', izq: minAPct(x.m), hora: x.h }));
  }
  if (reloj.tipo === 'banda') {
    const a = horaAMin(reloj.desde); const b = horaAMin(reloj.hasta);
    if (a === null || b === null || b <= a) return [];
    const salida = [{ tipo: 'banda', izq: minAPct(a), ancho: Math.round((minAPct(b) - minAPct(a)) * 1000) / 1000, hora: `${reloj.desde}–${reloj.hasta}` }];
    for (const h of Array.isArray(reloj.vueltas) ? reloj.vueltas : []) { const m = horaAMin(h); if (m !== null) salida.push({ tipo: 'marca', izq: minAPct(m), hora: h, inferida: true }); }
    return salida;
  }
  return [];
}

/** Carriles del reloj: primero lo que no es un robot (fábrica y jurado, de contexto) y luego los 10 robots, cada uno con sus segmentos. */
export function carrilesReloj() {
  const contexto = [
    { id: 'fabrica', nombre: 'Fábrica de anuncios', contexto: true, texto: '00:00 – 07:00', segmentos: [{ tipo: 'banda', izq: 0, ancho: minAPct(420), hora: '00:00–07:00', contexto: true }] },
    { id: 'jurado', nombre: 'Jurado (ordena la tanda)', contexto: true, texto: '07:00', segmentos: [{ tipo: 'marca', izq: minAPct(420), hora: '07:00', contexto: true }] },
  ];
  return [...contexto, ...ROBOTS.map((r) => ({ id: r.id, numero: r.numero, nombre: r.nombre, contexto: false, texto: r.horario, segmentos: segmentosReloj(r.reloj) }))];
}

/** Etiquetas del eje: cada 3 horas. */
export const EJE_HORAS = Array.from({ length: 9 }, (_, i) => ({ hora: `${String(i * 3).padStart(2, '0')}:00`, izq: minAPct(i * 180) }));

/** Texto accesible de un carril: «Escalera de escala: cada 30 min». */
export function descripcionCarril(c) {
  return `${c.nombre}: ${c.texto}`;
}

// ───────────────────────── estado de cada robot (qué hay en código) ─────────────────────────

const RANGO_ESTADO_INFRA = { VERDE: 0, AMARILLO: 1, ROJO: 2 };

/** Ítems del preflight por id: {id → item} (a partir de `sistema.infra.items`). */
export function itemsPorId(sistema) {
  const items = sistema && sistema.infra && Array.isArray(sistema.infra.items) ? sistema.infra.items : [];
  const mapa = {};
  for (const it of items) if (it && typeof it === 'object' && typeof it.id === 'string') mapa[it.id] = it;
  return mapa;
}

/**
 * Estado de un robot según lo que existe en código y lo que el panel puede comprobar.
 * → { clave:'no_construido'|'parcial'|'planeado', texto, tono, detalle, medicion }
 *  · no_construido: no hay código (chip neutro).
 *  · parcial: existe una parte (chip info) y `detalle` dice qué.
 *  · planeado: se describe en el plan, pero el panel no puede comprobar que haya código (por ejemplo, `motor_disponible` es false): no se afirma nada.
 * `medicion`: lo que dice el último preflight de los ítems que miran a este robot (vigía de pagos), o null.
 */
export function estadoCodigo(robot, sistema) {
  const base = { clave: 'no_construido', texto: 'No construido', tono: 'neutro', detalle: robot.existe || '', medicion: null };
  if (!robot || robot.codigo !== 'parcial') return base;
  if (robot.verifica === 'motor' && sistema && sistema.motor_disponible === false) {
    return { clave: 'planeado', texto: 'Planeado', tono: 'neutro', detalle: 'Está en el plan; el panel no encuentra el sistema automático, así que no afirma que ya esté construido.', medicion: null };
  }
  let medicion = null;
  if (robot.verifica === 'infra') {
    const mapa = itemsPorId(sistema);
    const vistos = (robot.itemsInfra || []).map((id) => mapa[id]).filter(Boolean);
    if (vistos.length) {
      const peor = vistos.reduce((a, b) => ((RANGO_ESTADO_INFRA[String(b.estado).toUpperCase()] ?? -1) > (RANGO_ESTADO_INFRA[String(a.estado).toUpperCase()] ?? -1) ? b : a));
      medicion = { items: vistos.map((i) => ({ id: i.id, estado: String(i.estado || ''), medido_en: i.medido_en || null })), peor: String(peor.estado || '') };
    }
  }
  return { clave: 'parcial', texto: 'Parcial', tono: 'info', detalle: robot.existe, medicion };
}

/** Cuántos robots del catálogo tienen algo de código (los «planeados» no cuentan). */
export function conteoCodigo(sistema) {
  const est = ROBOTS.map((r) => estadoCodigo(r, sistema).clave);
  return { total: ROBOTS.length, parciales: est.filter((c) => c === 'parcial').length, planeados: est.filter((c) => c === 'planeado').length, sinConstruir: est.filter((c) => c === 'no_construido').length };
}

// ───────────────────────── parámetros ─────────────────────────

/** Valor de un parámetro por clave «grupo.clave» tolerando la forma `{grupos:{g:{k:{valor}}}}`, `{g:{k:{valor}}}` y `{g:{k}}`. undefined si falta o es null. */
export function valorParametro(parametros, clave) {
  if (!parametros || typeof parametros !== 'object' || typeof clave !== 'string') return undefined;
  const [g, k] = clave.split('.');
  const raiz = parametros.grupos && typeof parametros.grupos === 'object' ? parametros.grupos : parametros;
  const nodo = raiz && raiz[g] && typeof raiz[g] === 'object' ? raiz[g][k] : undefined;
  const v = nodo && typeof nodo === 'object' && !Array.isArray(nodo) && 'valor' in nodo ? nodo.valor : nodo;
  return v === null || v === undefined || typeof v === 'object' ? undefined : v;
}

/** Los programas que ya existen en código con su cadencia leída de los parámetros ('sin dato' si el parámetro no está). */
export function programasExistentes(parametros, sistema) {
  const mapa = itemsPorId(sistema);
  return PROGRAMAS_EXISTENTES.map((p) => {
    const v = p.param ? valorParametro(parametros, p.param) : null;
    const v2 = p.param2 ? valorParametro(parametros, p.param2) : null;
    const tieneValor = p.param === null || v !== undefined;
    return {
      id: p.id, nombre: p.nombre, hace: p.hace,
      cadencia: tieneValor ? p.formato(v, v2 === undefined ? null : v2) : 'Frecuencia: sin dato (no figura en los parámetros)',
      sinDato: !tieneValor,
      medicion: p.evidencia.map((id) => mapa[id]).filter(Boolean).map((i) => ({ id: i.id, estado: String(i.estado || ''), medido_en: i.medido_en || null })),
    };
  });
}

// ───────────────────────── registro real (empresa/robots.yaml, formato sin fijar) ─────────────────────────

const quitarAcentos = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '');
/** Clave de comparación: minúsculas, sin acentos ni signos. */
export const plano = (s) => quitarAcentos(s).toLowerCase().replace(/[^a-z0-9]+/g, '');

function elegir(o, claves) {
  for (const k of claves) {
    if (o && Object.prototype.hasOwnProperty.call(o, k) && o[k] !== null && o[k] !== undefined && o[k] !== '') return o[k];
  }
  return undefined;
}

const ESTADOS_ROBOT = { apagado: 'apagado', off: 'apagado', desactivado: 'apagado', sombra: 'sombra', shadow: 'sombra', vivo: 'vivo', live: 'vivo', activo: 'vivo', encendido: 'vivo' };

/** «sombra» → 'sombra'; sinónimos admitidos; desconocido → null (se muestra «sin dato», no se inventa). */
export function normalizarEstadoRobot(v) {
  return typeof v === 'string' ? (ESTADOS_ROBOT[plano(v)] ?? null) : null;
}

/** «N2» / «n2» / 2 → 'N2'; fuera de N0–N4 → null. */
export function normalizarNivel(v) {
  const m = /^n?([0-4])$/i.exec(String(v ?? '').trim());
  return m ? `N${m[1]}` : null;
}

const aEnteroPositivo = (v) => (Number.isFinite(Number(v)) && v !== null && v !== '' && Number(v) >= 0 ? Math.round(Number(v)) : null);

/** Acierto en puntos básicos a partir de las formas razonables: acierto_bp · acierto_pct (0–100) · acierto (0–1 o 0–100). null si no hay dato válido. */
export function aciertoEnBp(r) {
  if (!r || typeof r !== 'object') return null;
  const bp = r.acierto_bp;
  if (Number.isFinite(bp) && bp >= 0 && bp <= 10000) return Math.round(bp);
  const pct = r.acierto_pct;
  if (Number.isFinite(pct) && pct >= 0 && pct <= 100) return Math.round(pct * 100);
  const a = r.acierto;
  if (Number.isFinite(a) && a >= 0) { if (a <= 1) return Math.round(a * 10000); if (a <= 100) return Math.round(a * 100); }
  return null;
}

function aMs(v) { const t = typeof v === 'string' ? Date.parse(v) : NaN; return Number.isFinite(t) ? t : null; }

/** Nombre para mostrar: el del registro, o el del catálogo si el id coincide con uno de los 10, o el id tal cual. */
export function nombreVisible(r) {
  if (r && r.nombre) return r.nombre;
  const id = plano(r && r.id);
  const c = id ? ROBOTS.find((x) => id === plano(x.id) || id.includes(plano(x.id))) : null;
  return c ? c.nombre : String((r && r.id) ?? '');
}

/** Lista cruda de robots desde: array · {robots:[…]} · {robots:{id:{…}}} · {id:{…}}. */
function listaRobots(datos) {
  if (Array.isArray(datos)) return datos;
  if (!datos || typeof datos !== 'object') return [];
  const r = datos.robots !== undefined ? datos.robots : datos;
  if (Array.isArray(r)) return r;
  if (r && typeof r === 'object') return Object.entries(r).filter(([, v]) => v && typeof v === 'object').map(([id, v]) => ({ id, ...v }));
  return [];
}

/**
 * Normaliza el registro de robots TOLERANDO ausencias: cada campo que falta queda en null (la pantalla dice «sin dato»).
 * → { robots:[{id, nombre, cadencia, nivel, estado, ultimoLatido, latidoMaxMin, aciertoBp, aciertoCortesBp, aciertoSubasBp, extra}], total, conteos }
 */
export function normalizarRegistro(datos) {
  const robots = [];
  for (const r of listaRobots(datos)) {
    if (!r || typeof r !== 'object') continue;
    const id = elegir(r, ['id', 'robot_id', 'robot', 'clave', 'nombre']);
    if (id === undefined) continue;
    const latido = r.latido && typeof r.latido === 'object' ? r.latido : null;
    const ultimo = elegir(r, ['ultimo_latido', 'ultimo_latido_en', 'latido_ts', 'latido_en', 'ultima_corrida']) ?? (latido ? elegir(latido, ['ts', 'ultimo', 'en']) : undefined);
    const maxMin = elegir(r, ['latido_max_min', 'latido_max']) ?? (latido ? elegir(latido, ['max_min']) : undefined);
    const horario = elegir(r, ['horario', 'cadencia', 'cron', 'programacion']);
    robots.push({
      id: String(id), nombre: typeof r.nombre === 'string' && r.nombre ? r.nombre : null,
      cadencia: typeof horario === 'string' ? horario : (horario !== undefined && typeof horario !== 'object' ? String(horario) : null),
      nivel: normalizarNivel(elegir(r, ['nivel', 'nivel_autonomia'])),
      estado: normalizarEstadoRobot(elegir(r, ['estado', 'modo'])),
      ultimoLatido: typeof ultimo === 'string' ? ultimo : null,
      latidoMaxMin: aEnteroPositivo(maxMin),
      aciertoBp: aciertoEnBp(r),
      aciertoCortesBp: Number.isFinite(r.acierto_cortes_bp) ? Math.round(r.acierto_cortes_bp) : null,
      aciertoSubasBp: Number.isFinite(r.acierto_subas_bp) ? Math.round(r.acierto_subas_bp) : null,
    });
  }
  const conteos = { vivo: 0, sombra: 0, apagado: 0, sinEstado: 0 };
  for (const r of robots) conteos[r.estado || 'sinEstado'] += 1;
  return { robots, total: robots.length, conteos };
}

/**
 * Estado del latido de un robot: { clave:'sin_latido'|'al_dia'|'vencido'|'sin_limite', tono, texto, minutos }.
 * Sin fecha: «sin latido todavía» (neutro). Con límite: vencido si pasó más; sin límite: solo se muestra la edad (neutro).
 */
export function estadoLatido(robot, ahoraMs = Date.now()) {
  const t = aMs(robot && robot.ultimoLatido);
  if (t === null) return { clave: 'sin_latido', tono: 'neutro', texto: 'Sin señal de vida todavía', minutos: null };
  const minutos = Math.max(0, Math.round((ahoraMs - t) / 60000));
  const edad = fmt.relativo(robot.ultimoLatido, ahoraMs);
  if (!robot.latidoMaxMin) return { clave: 'sin_limite', tono: 'neutro', texto: `Última señal de vida ${edad}`, minutos };
  return minutos > robot.latidoMaxMin
    ? { clave: 'vencido', tono: robot.estado === 'vivo' ? 'critico' : 'aviso', texto: `Sin señal de vida ${edad} (máximo ${robot.latidoMaxMin} min)`, minutos }
    : { clave: 'al_dia', tono: 'ok', texto: `Al día · ${edad}`, minutos };
}

/**
 * Empareja cada robot del catálogo con su fila del registro real (si la hay) por id, número («R1»/«1») o nombre. Lo que sobra del registro va en `sueltos`.
 * → { filas:[{robot, real|null}], sueltos:[robotRegistro] }
 */
export function unirConRegistro(registro, catalogo = ROBOTS) {
  const lista = registro && Array.isArray(registro.robots) ? registro.robots : [];
  const usados = new Set();
  const filas = catalogo.map((robot) => {
    const claves = new Set([plano(robot.id), plano(robot.nombre), `r${robot.numero}`, `robot${robot.numero}`]);
    const real = lista.find((x, i) => !usados.has(i) && (claves.has(plano(x.id)) || (x.nombre && claves.has(plano(x.nombre))) || plano(x.id).includes(plano(robot.id))));
    if (real) usados.add(lista.indexOf(real));
    return { robot, real: real || null };
  });
  return { filas, sueltos: lista.filter((_, i) => !usados.has(i)) };
}

// ───────────────────────── métricas y atención ─────────────────────────

/** Estado de la lectura del registro: 'ok' · 'vacio' (no hay robots.yaml) · 'sin_ruta' (el servidor no sabe leerlo) · 'error'. */
export function clasificarLecturaRegistro({ error, sobre } = {}) {
  if (error) {
    const est = error.estado ?? null;
    const cod = String(error.codigo || '');
    return est === 404 || cod === 'ruta_no_encontrada' || cod === 'no_existe' ? 'sin_ruta' : 'error';
  }
  if (!sobre) return 'vacio';
  const n = normalizarRegistro(sobre.datos).total;
  return sobre.vacio === true || n === 0 ? 'vacio' : 'ok';
}

/** Métricas de la cabecera. `valor` null = «—» (sin dato), nunca un 0 inventado. */
export function metricasRobots({ sistema, registro, estadoRegistro, ahoraMs = Date.now(), sombra } = {}) {
  const c = conteoCodigo(sistema);
  const reg = estadoRegistro === 'ok' && registro ? registro : null;
  const auditor = reg ? reg.robots.find((r) => plano(r.id).includes('auditor')) : null;
  const vivos = reg ? reg.conteos.vivo : null;
  const vencidos = reg ? reg.robots.filter((r) => estadoLatido(r, ahoraMs).clave === 'vencido').length : 0;
  return [
    { id: 'plan', etiqueta: 'Robots en el plan', valor: c.total, contexto: 'cada uno con una sola tarea y su horario', tono: null, ayuda: 'robot' },
    { id: 'codigo', etiqueta: 'Con algo ya construido', valor: c.parciales, contexto: c.parciales ? `${c.parciales} parcial${c.parciales === 1 ? '' : 'es'} · ${c.sinConstruir} sin construir${c.planeados ? ` · ${c.planeados} ${c.planeados === 1 ? 'planeado' : 'planeados'}` : ''}` : `ninguno todavía · ${c.sinConstruir} sin construir`, tono: null },
    { id: 'registrados', etiqueta: 'Registrados y vivos', valor: reg ? vivos : null, contexto: reg ? `${reg.total} en el registro · ${reg.conteos.sombra} en sombra · ${reg.conteos.apagado} ${reg.conteos.apagado === 1 ? 'apagado' : 'apagados'}${vencidos ? ` · ${vencidos} sin señal de vida` : ''}` : 'el registro todavía no existe', tono: vencidos ? 'aviso' : null, ayuda: 'registro_robots' },
    { id: 'auditor', etiqueta: 'Acierto del auditor', valor: auditor && auditor.aciertoBp !== null ? fmt.pct(auditor.aciertoBp) : null, contexto: auditor && auditor.aciertoBp !== null ? 'decisiones correctas, juzgadas con lo que pasó después' : 'sin medir: el auditor aún no existe', tono: null, ayuda: 'acierto_auditor' },
    // `sombra` (undefined = la pantalla no lo pidió; null = pedido pero todavía no hay estado guardado)
    ...(sombra === undefined ? [] : [metricaSombra(sombra)]),
  ];
}

function metricaSombra(sombra) {
  if (!sombra) return { id: 'sombra', etiqueta: 'Robots en sombra', valor: null, contexto: 'todavía no corrió ninguno: no hay estado guardado', tono: null, ayuda: 'robots_en_sombra' };
  const n = sombra.resumen.conSombra.length;
  if (!sombra.deHoy) return { id: 'sombra', etiqueta: 'Robots en sombra', valor: null, contexto: `el estado guardado es de hace ${textoEdad(sombra.edadMin)}: no cuenta como hoy`, tono: 'aviso', ayuda: 'robots_en_sombra' };
  const vencidos = sombra.resumen.vencidos.length;
  return { id: 'sombra', etiqueta: 'Robots en sombra', valor: sombra.resumen.corrieronHoy.length, contexto: `corrieron hoy, de ${n} con versión en sombra · solo lectura${vencidos ? ` · ${vencidos} sin señal de vida a tiempo` : ''}`, tono: vencidos ? 'aviso' : null, ayuda: 'robots_en_sombra' };
}

/** Avisos de la pantalla (crítico → aviso → info). Con registro, avisa de robots sin latido; sin registro, lo dice como información. */
export function atencionRobots({ sistema, registro, estadoRegistro, ahoraMs = Date.now(), sombra = null } = {}) {
  const items = [];
  if (sombra && sombra.situacion === 'vencido') {
    const n = sombra.resumen.vencidos.length;
    items.push({ tono: 'aviso', titulo: `${n === 1 ? 'Un robot en sombra' : `${n} robots en sombra`} no ${n === 1 ? 'dio' : 'dieron'} señal de vida a su hora`, detalle: `Latido vencido: ${sombra.resumen.vencidos.slice(0, 4).map((id) => (sombra.porId[id] ? sombra.porId[id].nombre : id)).join(', ')}. Puede ser que tu Mac estuviera dormida o que se haya quitado la programación. Son de solo lectura: no vigilan ni frenan nada.` });
  }
  if (sombra && !sombra.deHoy) items.push({ tono: 'info', titulo: 'El estado de los robots en sombra no es de hoy', detalle: `Se guardó hace ${textoEdad(sombra.edadMin)} y no se actualiza solo: lo que dice de «hoy» no vale. Vuelve a guardarlo con el comando de «Robots en sombra».` });
  if (estadoRegistro === 'ok' && registro) {
    for (const r of registro.robots) {
      const l = estadoLatido(r, ahoraMs);
      if (l.clave === 'vencido') items.push({ tono: r.estado === 'vivo' ? 'critico' : 'aviso', titulo: `${nombreVisible(r)} no da señales de vida`, detalle: `${l.texto}. Un robot vivo sin señal de vida se considera caído: el vigilante pausa la cuenta si todo el sistema se detiene.` });
    }
    const bajos = registro.robots.filter((r) => (r.aciertoCortesBp !== null && r.aciertoCortesBp < 5000) || (r.aciertoSubasBp !== null && r.aciertoSubasBp < 6000));
    for (const r of bajos) items.push({ tono: 'aviso', titulo: `${nombreVisible(r)} acierta menos de lo exigido`, detalle: 'El auditor debería bajarle el nivel; subirlo de nuevo lo firmas tú.' });
  } else {
    const c = conteoCodigo(sistema);
    items.push({ tono: 'info', titulo: 'Todavía no hay ningún robot encendido', detalle: `El plan tiene ${c.total} robots; ${c.parciales ? `${c.parciales} tienen una parte ya construida` : 'ninguno está construido todavía'} y el registro real no existe, así que no hay nada que vigilar.` });
  }
  return items;
}

/** Valida y fija la pestaña inicial desde `?vista=`. */
export const VISTAS_ROBOTS = ['plan', 'registro', 'reglas'];
export const vistaValida = (v) => (VISTAS_ROBOTS.includes(v) ? v : 'plan');

// ───────────────────────── robots en sombra (empresa/robots/estado.json, vía GET /robots/sombra) ─────────────────────────
//
// «En sombra» = el robot mira los archivos y PROPONE, pero no actúa (no envía, no pausa, no gasta). NO es el sistema real (planificador, reintentos, controles) que construye S-B:
// por eso nada de lo de acá cuenta como «hay un planificador», y el semáforo «¿Me puedo ausentar?» nunca se pone verde por esto.

/**
 * Quién construye cada robot del plan y si ya hay una versión en sombra. Es lo que el panel SABE sin leer nada (docs/_historial/mentor-sistema/robots-sombra.md §2); cuando hay
 * estado guardado manda `ejecutor_hoy` de ese estado. `solo_sb`: mover presupuesto o prender campañas no se puede ensayar sin ejecutarlo, así que es solo del equipo técnico.
 */
export const SOMBRA_CATALOGO = {
  escalera: { version: false, quien: 'solo_sb' }, salvavidas: { version: false, quien: 'solo_sb' }, guardia: { version: false, quien: 'solo_sb' }, cola: { version: false, quien: 'solo_sb' },
  perfil: { version: true }, alarma: { version: true }, vigia: { version: true }, informe: { version: true }, auditor: { version: true },
  bandeja: { version: false, quien: 'sc_sb' },
};

/** Los dos programas de apoyo que también corren en sombra (no son de los 10 robots). */
export const APOYO_SOMBRA = [
  { id: 'alertas', nombre: 'Productor de alertas', hace: 'Calcula las alertas con los archivos del proyecto y las guarda en una lista. No envía nada.' },
  { id: 'baja_j3', nombre: 'Baja del día 1 (J3)', hace: 'Propone dar de baja el lanzamiento que no vendió con el presupuesto gastado. No pausa nada.' },
];

export const COMANDOS_SOMBRA = {
  estado: '.venv/bin/python -m scripts.robots.sombra estado',
  simular: '.venv/bin/python -m scripts.robots.sombra ejecutar --todos --simular',
  escribir: '.venv/bin/python -m scripts.robots.sombra ejecutar --todos --escribir',
  programar: '.venv/bin/python -m scripts.robots.sombra programar',
};

const ESTADOS_LATIDO_SOMBRA = ['al_dia', 'vencido', 'manual', 'sin_latido', 'apagado', 'no_aplica'];
const RESULTADOS_SOMBRA = {
  ok: { texto: 'Todo medido y en orden', tono: 'ok', icono: 'ok' },
  parcial: { texto: 'Parcial: algo no se pudo medir', tono: 'aviso', icono: 'alerta' },
  sin_datos: { texto: 'Sin datos todavía', tono: 'neutro', icono: 'circulo-punteado' },
  sin_decidir: { texto: 'Sin decidir: faltan límites por fijar', tono: 'neutro', icono: 'circulo-punteado' },
  alerta: { texto: 'Encontró una alerta', tono: 'aviso', icono: 'alerta' },
  error: { texto: 'Falló al correr', tono: 'error', icono: 'x-circulo' },
};
/** Cómo se dice el último resultado de una corrida en sombra (vocabulario cerrado; lo desconocido es null). */
export const resultadoSombra = (r) => (typeof r === 'string' && Object.prototype.hasOwnProperty.call(RESULTADOS_SOMBRA, r) ? { clave: r, ...RESULTADOS_SOMBRA[r] } : null);

const SITUACIONES_SOMBRA = {
  sin_programar: { tono: 'neutro', icono: 'circulo-punteado', texto: 'No hay nada programado' },
  corriendo: { tono: 'info', icono: 'ojo', texto: 'Robots en sombra corriendo (solo lectura)' },
  vencido: { tono: 'aviso', icono: 'reloj-alerta', texto: 'Latido vencido' },
};

const esObjeto = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const txt = (v, max) => (typeof v === 'string' ? v.slice(0, max) : '');
const idsDe = (v) => (Array.isArray(v) ? v.filter((x) => typeof x === 'string' && /^[a-z][a-z0-9_]{0,23}$/.test(x)).slice(0, 24) : []);
const enteroONull = (v) => (Number.isSafeInteger(v) ? v : null);

/** «3 h» · «2 d» · «40 min» a partir de minutos (para decir «hace …»). */
export function textoEdad(min) {
  if (!Number.isFinite(min)) return 'un tiempo desconocido';
  if (min < 90) return `${Math.max(0, Math.round(min))} min`;
  if (min < 48 * 60) return `${Math.round(min / 60)} h`;
  return `${Math.round(min / 1440)} d`;
}

function filaSombra(r) {
  if (!esObjeto(r) || typeof r.id !== 'string' || !/^[a-z][a-z0-9_]{0,23}$/.test(r.id)) return null;
  const vencido = r.vencido === true;
  const estadoLatido = ESTADOS_LATIDO_SOMBRA.includes(r.estado_latido) ? r.estado_latido : 'desconocido';
  return {
    id: r.id, nombre: txt(r.nombre, 80) || r.id, tipo: r.tipo === 'apoyo' ? 'apoyo' : 'robot', horario: txt(r.horario, 60), ejecutorHoy: r.ejecutor_hoy === 'sombra' ? 'sombra' : 'ninguno',
    estadoLatido: vencido && estadoLatido === 'al_dia' ? 'vencido' : estadoLatido, esperado: r.esperado === true, vencido, motivo: txt(r.motivo, 200),
    ultimoLatido: typeof r.ultimo_latido === 'string' && Number.isFinite(Date.parse(r.ultimo_latido)) ? r.ultimo_latido : null, ultimoResultado: resultadoSombra(r.ultimo_resultado),
    ultimaRazon: txt(r.ultima_razon, 200), edadMin: enteroONull(r.edad_min), latidoMaxMin: enteroONull(r.latido_max_min), corrioHoy: r.corrio_hoy === true,
    debiaCorrerHoy: r.debia_correr_hoy === true,
  };
}

/**
 * La respuesta de GET /robots/sombra lista para pintar, o null si no hay estado guardado (o no tiene la forma esperada: no se inventa nada).
 * → { generadoEn, edadMin, deHoy, situacion, zonaHoy, filas, porId, resumen:{conSombra, esperados, vencidos, corrieronHoy, faltanHoy, soloManual, sinArrancar, sinVersion}, auditoria, avisos, comandos }
 */
export function normalizarSombra(sobre) {
  const d = sobre && sobre.vacio !== true && esObjeto(sobre.datos) ? sobre.datos : null;
  if (!d || d.existe !== true || !Array.isArray(d.robots)) return null;
  const filas = d.robots.map(filaSombra).filter(Boolean).slice(0, 24);
  const porId = Object.fromEntries(filas.map((f) => [f.id, f]));
  const r = esObjeto(d.resumen) ? d.resumen : {};
  const aud = esObjeto(d.auditoria) ? Object.fromEntries(Object.entries(d.auditoria).filter(([k, v]) => /^[a-z][a-z0-9_]{0,29}$/.test(k) && Number.isSafeInteger(v)).slice(0, 8)) : null;
  return {
    generadoEn: txt(d.generado_en, 30) || null, edadMin: enteroONull(d.edad_min), deHoy: d.de_hoy === true, zonaHoy: txt(d.zona_hoy, 40), situacion: Object.prototype.hasOwnProperty.call(SITUACIONES_SOMBRA, d.situacion) ? d.situacion : 'sin_programar',
    filas, porId,
    resumen: { conSombra: idsDe(r.con_sombra), esperados: idsDe(r.esperados), vencidos: idsDe(r.vencidos), corrieronHoy: idsDe(r.corrieron_hoy), faltanHoy: idsDe(r.faltan_hoy), soloManual: idsDe(r.solo_manual), sinArrancar: idsDe(r.sin_arrancar), sinVersion: idsDe(r.sin_version) },
    auditoria: aud && Object.keys(aud).length ? aud : null,
    avisos: (Array.isArray(d.avisos) ? d.avisos : []).filter((a) => typeof a === 'string').slice(0, 5).map((a) => a.slice(0, 200)),
    comandos: COMANDOS_SOMBRA,
  };
}

/**
 * La insignia de un robot del plan: «En sombra hoy» · «Sin versión en sombra» · «Solo S-B». Con estado guardado manda `ejecutor_hoy` de ese estado; sin él, lo que el panel sabe
 * del plan (y entonces no afirma que ya corra: «Tiene versión en sombra»).
 */
export function insigniaSombra(robot, fila, hayEstado = Boolean(fila)) {
  const cat = SOMBRA_CATALOGO[robot && robot.id] || { version: false, quien: 'sc_sb' };
  const tiene = fila ? fila.ejecutorHoy === 'sombra' : cat.version;
  if (tiene) {
    return hayEstado
      ? { clave: 'en_sombra', texto: 'En sombra hoy', tono: 'info', icono: 'ojo', detalle: 'Mira y propone, pero no actúa: es solo lectura.' }
      : { clave: 'con_version', texto: 'Tiene versión en sombra', tono: 'info', icono: 'ojo', detalle: 'Mira y propone, pero no actúa. Todavía no corrió: falta guardar su estado.' };
  }
  if (cat.quien === 'solo_sb') return { clave: 'solo_sb', texto: 'Solo S-B', tono: 'neutro', icono: 'engranaje', detalle: 'Mover presupuesto o prender campañas no se puede ensayar sin hacerlo de verdad: lo construye el equipo técnico (S-B).' };
  return { clave: 'sin_version', texto: 'Sin versión en sombra', tono: 'neutro', icono: 'circulo-punteado', detalle: 'Todavía no hay una versión de solo lectura. Dependen del correo y de las plantillas aprobadas.' };
}

/** Cómo va la última corrida en sombra de un robot: { clave, tono, icono, texto } (o null si no aplica). */
export function corridaSombra(fila) {
  if (!fila || fila.estadoLatido === 'no_aplica') return null;
  const t = {
    al_dia: { tono: 'ok', icono: 'ok', texto: fila.corrioHoy ? 'Al día · corrió hoy' : 'Al día' },
    vencido: { tono: 'aviso', icono: 'reloj-alerta', texto: 'Latido vencido: no dio señal de vida a tiempo' },
    manual: { tono: 'neutro', icono: 'circulo-punteado', texto: 'Corrió solo a mano: no se espera su señal de vida' },
    sin_latido: { tono: 'neutro', icono: 'circulo-punteado', texto: 'Todavía no corrió' },
    apagado: { tono: 'neutro', icono: 'pausa', texto: 'Apagado en el registro' },
    desconocido: { tono: 'neutro', icono: 'circulo-punteado', texto: 'Estado sin dato' },
  }[fila.estadoLatido];
  return { clave: fila.estadoLatido, ...t };
}

/** El titular de la foto de los robots en sombra: uno de los tres estados de siempre. { tono, icono, texto, detalle } */
export function titularSombra(sombra) {
  if (!sombra) return null;
  const base = SITUACIONES_SOMBRA[sombra.situacion];
  const n = sombra.resumen.esperados.length;
  const nombres = (ids) => ids.slice(0, 4).map((id) => (sombra.porId[id] ? sombra.porId[id].nombre : id)).join(', ');
  const detalle = {
    sin_programar: sombra.resumen.corrieronHoy.length || sombra.resumen.soloManual.length
      ? 'Los robots en sombra solo corrieron cuando alguien los ejecutó a mano. Una prueba a mano no crea ninguna expectativa: nadie espera ni avisa nada. Nada se despierta solo.'
      : 'Ningún robot en sombra corrió todavía y nadie programó ninguno. Nada se despierta solo.',
    corriendo: `${n} ${n === 1 ? 'robot programado dio' : 'robots programados dieron'} señal de vida a su hora. Miran y proponen, pero no vigilan ni frenan nada: no son el sistema real.`,
    vencido: `${sombra.resumen.vencidos.length} ${sombra.resumen.vencidos.length === 1 ? 'robot programado no dio' : 'robots programados no dieron'} señal de vida a su hora (${nombres(sombra.resumen.vencidos)}). Puede ser que tu Mac estuviera dormida o que se haya quitado la programación.`,
  }[sombra.situacion];
  return { ...base, detalle, clave: sombra.situacion };
}
