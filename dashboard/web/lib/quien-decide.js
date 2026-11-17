// lib/quien-decide.js — lógica pura de #/quien-decide («Quién decide qué»). Sin DOM ni red. SOLO LECTURA: el panel nunca cambia gates, límites ni autonomía;
// cambiarlos lo hace el dueño con su firma por línea de comandos, que aquí solo se construye como texto copiable.
//
// ESTADO HONESTO. Todo lo que sale de aquí está etiquetado como una de dos cosas:
//   · HOY: lo que dicen los archivos ahora (contratos/gates.json, empresa/autonomia.yaml, empresa/limites.yaml, /api/sistema). Se calcula, no se escribe a mano.
//   · OBJETIVO (J2, decisión del dueño 2026-11-06, docs/_historial/mentor-sistema/decisiones-del-dueno.md): el reparto al que se quiere llegar. AÚN NO RIGE.
//     Cada fila del objetivo trae «qué falta para llegar»: lo que se puede comprobar en los archivos se comprueba (estado ok|pendiente|sin_dato); lo que solo está en el
//     plan (mapeo.md §4, §8, §9, §10) va marcado `plan` y el panel NO lo puede verificar.
//
// Entradas (los datos de tres lecturas que la página hace en paralelo; cualquiera puede faltar):
//   gates      ← GET /api/gates       → {gates:{schema_version, niveles, entradas:{'etapa:D1'|'accion:x': {descripcion, gate:{N0…N4: A|S|H|NA}}}}|null, acciones_minimas_h:[…]|null}
//   parametros ← GET /api/parametros  → {limites:{valores, nulos}, autonomia:{nivel_por_etapa}, …}
//   sistema    ← GET /api/sistema     → {pausa:{activa, desde, motivo}, freno_captura:{activo, ts, motivo}|null, …}

import { estadoDeClave, textoLimite, NOMBRE_ETAPA, modeloAutonomia } from './parametros.js';

export const NIVELES = ['N0', 'N1', 'N2', 'N3', 'N4'];
const idxNivel = (n) => NIVELES.indexOf(n);
const esObj = (x) => x !== null && typeof x === 'object' && !Array.isArray(x);
const humanizar = (c) => { const t = String(c ?? '').replace(/[_-]+/g, ' ').trim(); return t ? t.charAt(0).toUpperCase() + t.slice(1) : ''; };

// ───────────────────────────────────────── tipos de gate ─────────────────────────────────────────

/** Fuerza de cada gate: el efectivo es el más estricto. NA («aún no se hace») es lo más laxo: no hay nadie que firme porque no se ejecuta. */
export const FUERZA_GATE = { NA: 0, A: 1, S: 2, H: 3 };

export const GATES_INFO = {
  H: { id: 'H', letra: 'H', etiqueta: 'Lo firmas tú', quien: 'Tú', frase: 'Se detiene hasta que lo firmes tú.', tono: 'acento', icono: 'usuario', glosario: 'gate_h' },
  S: { id: 'S', letra: 'S', etiqueta: 'Por excepción', quien: 'El sistema; tú solo si hay una excepción', frase: 'Avanza solo si todo está limpio; si la revisión deja notas, hay un fallo o toca una muestra al azar, te lo consulta.', tono: 'info', icono: 'ojo', glosario: 'gate_s' },
  A: { id: 'A', letra: 'A', etiqueta: 'Automático', quien: 'El sistema, dentro de sus topes', frase: 'Lo decide el sistema comprobando reglas medibles; si algo falla, se detiene y te avisa.', tono: 'neutro', icono: 'engranaje', glosario: 'gate_a' },
  NA: { id: 'NA', letra: '–', etiqueta: 'Aún no se hace', quien: 'Nadie: en este nivel no está disponible', frase: 'En este nivel de autonomía esa acción no se ejecuta.', tono: 'neutro', icono: 'circulo-punteado', glosario: 'gate_na' },
};
export const ORDEN_GATES = ['H', 'S', 'A', 'NA'];

/** «N3» → «3»: los niveles se dicen «nivel 3», nunca solo con la sigla. */
export const numeroNivel = (n) => String(n ?? '').replace(/^N/i, '');

/** Quién decide en una celda de la tira por nivel (para el aria-label y el title): «Nivel 3: por excepción». */
export function textoGateNivel(nivel, gate) {
  const g = GATES_INFO[gate];
  return `Nivel ${numeroNivel(nivel)}: ${g ? g.etiqueta.toLowerCase() : 'sin dato'}`;
}

/** Qué significa cada nivel de autonomía, con un ejemplo corto (mismo sentido que el glosario). */
export const NIVELES_TEXTO = [
  ['0', 'todo lo apruebas tú. El sistema te guía paso a paso.'],
  ['1', 'una IA hace el trabajo y tú revisas todo.'],
  ['2', 'otra IA revisa a la primera; tú firmas solo lo importante (oferta, página de venta, campaña, presupuesto).'],
  ['3', 'el sistema avanza solo, con topes duros de dinero, y te consulta solo cuando hay algo raro.'],
  ['4', 'el sistema lanza una oferta nueva con un botón, con tope diario y una revisión semanal tuya.'],
];

// ───────────────────────────────────────── catálogo de filas ─────────────────────────────────────────

/** Orden canónico de las etapas del flujo; las que no figuren aquí van detrás, en el orden del archivo. */
export const ORDEN_ETAPAS = ['O0', 'D0', 'M1', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10', 'F1', 'F2', 'X1', 'X2'];

export const NOMBRE_ACCION = {
  elegir_candidato: 'Elegir el candidato de oferta',
  aprobar_oferta: 'Aprobar la oferta (precio y promesa)',
  publicar_landing: 'Publicar la página de venta',
  activar_campana: 'Activar una campaña',
  reactivar_tras_pausa: 'Reactivar tras una pausa',
  pausar: 'Pausar una campaña u oferta',
  aumentar_presupuesto_d8: 'Subir presupuesto (optimización diaria)',
  subir_presupuesto_d9: 'Subir presupuesto (escalado, con plan)',
  subir_presupuesto_sobre_tope: 'Subir presupuesto por encima del tope',
  lanzamiento_pais_idioma_nuevo: 'Lanzar en un país o idioma nuevo',
  reembolso_automatico: 'Reembolsar automáticamente',
  disputa: 'Responder una disputa de pago',
  prueba_social: 'Usar prueba social (con permiso)',
  email_marketing: 'Enviar correo de marketing',
  cambiar_limites: 'Cambiar los límites',
  cambiar_skill: 'Cambiar la guía de trabajo o una regla de un agente',
  retirar_oferta: 'Retirar una oferta',
  asignar_capital: 'Asignar capital',
  confirmar_validada: 'Confirmar una oferta como validada',
  extender_test: 'Extender un test inconcluso',
  cerrar_oferta: 'Cerrar una oferta (post-mortem)',
  compra_real_minima: 'Compra real mínima antes de activar',
  ascender_nivel: 'Subir una etapa de nivel (que haga más sola)',
  reabrir_fallida: 'Reabrir una oferta fallida',
};

/** Etapa cuyo nivel decide el gate de una acción (solo se usa si la fila cambia de un nivel a otro; espejo de scripts/validar_esquemas.py::ETAPA_DE_ACCION + las acciones de D8-D10). */
export const ETAPA_DE_ACCION = {
  elegir_candidato: 'D1', aprobar_oferta: 'D3', publicar_landing: 'D5', activar_campana: 'D7', reactivar_tras_pausa: 'D8', pausar: 'D8',
  aumentar_presupuesto_d8: 'D8', subir_presupuesto_d9: 'D9', subir_presupuesto_sobre_tope: 'D9', lanzamiento_pais_idioma_nuevo: 'M1',
  reembolso_automatico: 'D10', disputa: 'D10', prueba_social: 'D10', email_marketing: 'D10', retirar_oferta: 'D9', cerrar_oferta: 'D9', asignar_capital: 'F1',
};

export const GRUPOS = [
  { id: 'flujo', titulo: 'Paso del recorrido de cada oferta' },
  { id: 'eleccion', titulo: 'Elegir y comunicar' },
  { id: 'dinero', titulo: 'Dinero y campañas' },
  { id: 'reglas', titulo: 'Reglas y niveles' },
];
export const GRUPO_DE_ACCION = {
  elegir_candidato: 'eleccion', aprobar_oferta: 'eleccion', prueba_social: 'eleccion', email_marketing: 'eleccion',
  publicar_landing: 'dinero', activar_campana: 'dinero', pausar: 'dinero', reactivar_tras_pausa: 'dinero', aumentar_presupuesto_d8: 'dinero', subir_presupuesto_d9: 'dinero',
  subir_presupuesto_sobre_tope: 'dinero', lanzamiento_pais_idioma_nuevo: 'dinero', reembolso_automatico: 'dinero', disputa: 'dinero', asignar_capital: 'dinero',
  compra_real_minima: 'dinero', extender_test: 'dinero', retirar_oferta: 'dinero', cerrar_oferta: 'dinero', confirmar_validada: 'dinero',
  cambiar_limites: 'reglas', cambiar_skill: 'reglas', ascender_nivel: 'reglas', reabrir_fallida: 'reglas',
};

/** Claves de limites.yaml que acotan cada decisión (curado a mano; una prueba comprueba que todas existen en limites.yaml). */
export const TOPES_DE_FILA = {
  'etapa:O0': ['capital_en_riesgo_total', 'ofertas_en_test_simultaneas_max'],
  'etapa:D0': ['capital_en_riesgo_total', 'cuentas_permitidas'],
  'etapa:M1': ['paises_permitidos', 'locales_permitidos'],
  'etapa:D1': ['max_costo_por_barrido', 'max_barridos_por_semana', 'max_busquedas_por_barrido'],
  'etapa:D2': ['costo_max_validacion', 'max_consultas_biblioteca'],
  'etapa:D3': ['precio_neto_minimo', 'politica_reembolso_dias'],
  'etapa:D4': ['costo_max_producto'],
  'etapa:D5': ['politica_reembolso_dias', 'cupon_descuento_max_pct'],
  'etapa:D6': ['creditos_max_pieza', 'creditos_max_oferta', 'max_budget_por_corrida_agente'],
  'etapa:D7': ['gasto_diario_global', 'gasto_diario_por_oferta', 'gasto_total_test_por_oferta', 'limite_gasto_cuenta_meta'],
  'etapa:D8': ['aumento_presupuesto_max_pct_por_paso', 'horas_min_entre_aumentos', 'gasto_diario_por_oferta'],
  'etapa:D9': ['stop_loss_escala', 'dias_cobertura_caja', 'aumento_presupuesto_max_pct_por_paso'],
  'etapa:D10': ['reembolso_auto_max', 'reembolsos_auto_max_por_dia', 'correos_max_por_dia'],
  'etapa:F1': ['capital_en_riesgo_total', 'perdida_neta_acumulada_max'],
  'accion:aprobar_oferta': ['precio_neto_minimo'],
  'accion:publicar_landing': ['politica_reembolso_dias'],
  'accion:activar_campana': ['gasto_diario_global', 'gasto_diario_por_oferta', 'gasto_total_test_por_oferta', 'limite_gasto_cuenta_meta'],
  'accion:aumentar_presupuesto_d8': ['aumento_presupuesto_max_pct_por_paso', 'horas_min_entre_aumentos', 'gasto_diario_por_oferta'],
  'accion:subir_presupuesto_d9': ['aumento_presupuesto_max_pct_por_paso', 'horas_min_entre_aumentos', 'stop_loss_escala', 'gasto_diario_por_oferta'],
  'accion:subir_presupuesto_sobre_tope': ['gasto_diario_por_oferta', 'gasto_diario_global'],
  'accion:lanzamiento_pais_idioma_nuevo': ['paises_permitidos', 'locales_permitidos'],
  'accion:reembolso_automatico': ['reembolso_auto_max', 'reembolsos_auto_max_por_dia'],
  'accion:disputa': ['ratio_disputas_pausa'],
  'accion:email_marketing': ['correos_max_por_dia', 'correos_max_por_semana'],
  'accion:cambiar_limites': ['sello'],
  'accion:asignar_capital': ['capital_en_riesgo_total', 'reserva_no_publicitaria_pct'],
  'accion:extender_test': ['gasto_total_test_por_oferta'],
};

/** Aclaración para las etapas que no tienen fila propia en gates.json. */
export const NOTA_SIN_ENTRADA = {
  X1: 'Cumplimiento puede frenar en cualquier nivel; sin su visto bueno firmado no se publica ni se activa.',
  X2: 'No tiene fila propia en la tabla. Cambiar una guía de trabajo o una regla sigue siendo decisión tuya.',
};

export const FRASE_SIN_TOPE_FIJAR = 'Sin fijar: por defecto no se puede gastar';
export const FRASE_LISTA_VACIA = 'Lista vacía: por defecto no se puede gastar';
export const FRASE_SIN_SELLO = 'Sin tu firma: por defecto no se puede gastar';

// ───────────────────────────────────────── acceso a los datos ─────────────────────────────────────────

/** Normaliza lo que devuelve /api/gates. `entradas` = {clave: {descripcion, gate:{N0…}}}; null si no hay tabla. */
export function leerGates(datos) {
  const g = datos && esObj(datos.gates) && esObj(datos.gates.entradas) ? datos.gates : null;
  const entradas = {};
  if (g) {
    for (const [clave, e] of Object.entries(g.entradas)) {
      if (!/^(etapa|accion):[A-Za-z0-9_]+$/.test(clave) || !esObj(e) || !esObj(e.gate)) continue;
      const gate = {};
      for (const n of NIVELES) if (typeof e.gate[n] === 'string' && Object.hasOwn(GATES_INFO, e.gate[n])) gate[n] = e.gate[n];
      if (Object.keys(gate).length) entradas[clave] = { descripcion: typeof e.descripcion === 'string' ? e.descripcion : null, gate };
    }
  }
  const minimas = datos && Array.isArray(datos.acciones_minimas_h) ? datos.acciones_minimas_h.filter((a) => typeof a === 'string') : null;
  return { hay: Boolean(g) && Object.keys(entradas).length > 0, entradas, version: g && typeof g.schema_version === 'string' ? g.schema_version : null, minimas };
}

/** Límites de /api/parametros: valores, claves en null y moneda. */
export function leerLimites(parametros) {
  const L = parametros && esObj(parametros.limites) ? parametros.limites : null;
  const valores = L && esObj(L.valores) ? L.valores : null;
  const nulos = new Set(L && Array.isArray(L.nulos) ? L.nulos.filter((x) => typeof x === 'string') : []);
  const moneda = valores && typeof valores.moneda_limites === 'string' && /^[A-Z]{3}$/.test(valores.moneda_limites) ? valores.moneda_limites : null;
  return { hay: Boolean(valores), valores, nulos, moneda };
}

/** Nivel de autonomía por etapa. */
export function leerAutonomia(parametros) {
  const m = modeloAutonomia(parametros && parametros.autonomia);
  const porEtapa = {};
  if (m) for (const e of m.etapas) porEtapa[e.etapa] = e;
  const niveles = m ? m.etapas.map((e) => e.nivel).filter(Boolean) : [];
  const bajo = niveles.length ? NIVELES.filter((n) => niveles.includes(n))[0] || null : null;
  return { hay: Boolean(m), modelo: m, porEtapa, nivelMasBajo: bajo };
}

const nivelDe = (aut, etapa) => (aut.porEtapa[etapa] && aut.porEtapa[etapa].nivel) || null;
/** ¿La etapa está en `minimo` o más? false si no se sabe. */
export const alcanza = (aut, etapa, minimo) => { const n = nivelDe(aut, etapa); return n !== null && idxNivel(n) >= idxNivel(minimo); };

// ───────────────────────────────────────── topes (limites.yaml) ─────────────────────────────────────────

/** Estado de una clave de limites.yaml como tope de una decisión. */
export function modeloTope(clave, lim, fmt) {
  const nombre = humanizar(clave);
  if (!lim.hay) return { clave, nombre, estado: 'sin_lectura', bloquea: false, texto: null, mensaje: 'No se pudieron leer tus límites' };
  const valor = lim.valores[clave];
  const est = estadoDeClave(clave, valor, lim.nulos.has(clave));
  if (clave === 'sello') {
    const sellado = est === 'fijado';
    return { clave, nombre, estado: sellado ? 'fijado' : 'sin_fijar', bloquea: !sellado, texto: sellado ? 'Firmado por ti' : null, mensaje: sellado ? 'Firmado por ti' : FRASE_SIN_SELLO };
  }
  if (est === 'nulo' || est === 'ausente') return { clave, nombre, estado: est === 'ausente' ? 'ausente' : 'sin_fijar', bloquea: true, texto: null, mensaje: FRASE_SIN_TOPE_FIJAR };
  if (est === 'vacio') return { clave, nombre, estado: 'vacio', bloquea: true, texto: null, mensaje: FRASE_LISTA_VACIA };
  const texto = textoLimite(clave, valor, lim.moneda, fmt);
  return { clave, nombre, estado: est, bloquea: false, texto, mensaje: texto };
}

// ───────────────────────────────────────── filas de «Hoy» ─────────────────────────────────────────

function esConstante(porNivel) {
  const v = NIVELES.map((n) => porNivel[n]);
  return v.every((x) => x !== undefined) && v.every((x) => x === v[0]);
}

/** El más estricto de una lista de gates (ignora null). null si no hay ninguno. */
export function masEstricto(...gates) {
  let mejor = null;
  for (const g of gates) if (g && FUERZA_GATE[g] !== undefined && (mejor === null || FUERZA_GATE[g] > FUERZA_GATE[mejor])) mejor = g;
  return mejor;
}

function nombreDeFila(tipo, id) {
  if (tipo === 'etapa') return `${id} · ${NOMBRE_ETAPA[id] || 'Etapa'}`;
  return NOMBRE_ACCION[id] || humanizar(id);
}

function construirFila(clave, entrada, c) {
  const i = clave.indexOf(':');
  const tipo = clave.slice(0, i);
  const id = clave.slice(i + 1);
  const etapa = tipo === 'etapa' ? id : (ETAPA_DE_ACCION[id] || null);
  const porNivel = entrada ? entrada.gate : null;
  const constante = porNivel ? esConstante(porNivel) : false;
  let nivel = etapa ? nivelDe(c.aut, etapa) : null;
  let nivelOrigen = nivel ? 'etapa' : null;
  if (!nivel && porNivel && !constante && c.aut.nivelMasBajo) { nivel = c.aut.nivelMasBajo; nivelOrigen = 'minimo'; }
  const gateTabla = porNivel ? (nivel && porNivel[nivel]) || (constante ? porNivel.N0 : null) : null;
  const enLista = tipo === 'accion' && c.listaH.has(id);
  const esMinima = tipo === 'accion' && c.minimas.has(id);
  const gate = enLista ? 'H' : gateTabla;
  const forzadoDifiere = Boolean(enLista && gateTabla && gateTabla !== 'H');
  // lo más laxo que la tabla permite en algún nivel (sin contar NA, que es «no se hace»): sirve para decir «la tabla llega a S en N3, pero rige H»
  const tablaPermite = porNivel ? NIVELES.map((n) => porNivel[n]).filter((g) => g && g !== 'NA').reduce((a, g) => (a === null || FUERZA_GATE[g] < FUERZA_GATE[a] ? g : a), null) : null;
  // la lista de acciones que siempre piden tu firma es más estricta que la tabla en algún nivel (aunque hoy, en N0, la tabla también diga H)
  const limitadaPorLista = Boolean(enLista && tablaPermite && tablaPermite !== 'H');
  const grupo = tipo === 'etapa' ? 'flujo' : (GRUPO_DE_ACCION[id] || 'reglas');
  const topes = (TOPES_DE_FILA[clave] || []).map((k) => modeloTope(k, c.lim, c.fmt));
  return {
    id: clave, tipo, clave: id, nombre: nombreDeFila(tipo, id), descripcion: entrada ? entrada.descripcion : null,
    grupo, etapa, nivel, nivelOrigen, porNivel, constante, gateTabla, gate, enLista, esMinima, forzadoDifiere, limitadaPorLista, tablaPermite,
    sinEntrada: !entrada, nota: !entrada ? (NOTA_SIN_ENTRADA[id] || 'Sin fila propia en la tabla de puntos de control.') : null, topes,
    sinFijar: topes.filter((t) => t.bloquea).length,
  };
}

/** Todas las filas de la tabla «Hoy», generadas del contrato (no escritas a mano): una por cada entrada de gates.json, más las etapas de autonomia.yaml sin fila (X1, X2). */
export function filasHoy({ gates, aut, lim, fmt }) {
  const listaH = new Set(lim.hay && Array.isArray(lim.valores.acciones_gate_humano) ? lim.valores.acciones_gate_humano.filter((x) => typeof x === 'string') : []);
  const minimas = new Set(gates.minimas || []);
  for (const m of minimas) listaH.add(m); // las seis mínimas rigen aunque limites.yaml no las traiga
  const c = { aut, lim, fmt, listaH, minimas };
  const claves = Object.keys(gates.entradas);
  const etapas = claves.filter((k) => k.startsWith('etapa:')).map((k) => k.slice(6));
  const sinFila = Object.keys(aut.porEtapa).filter((e) => !etapas.includes(e));
  const todasEtapas = [...etapas, ...sinFila];
  const ordenadas = [...ORDEN_ETAPAS.filter((e) => todasEtapas.includes(e)), ...todasEtapas.filter((e) => !ORDEN_ETAPAS.includes(e))];
  const filasEtapa = ordenadas.map((e) => construirFila(`etapa:${e}`, gates.entradas[`etapa:${e}`] || null, c));
  const filasAccion = claves.filter((k) => k.startsWith('accion:')).map((k) => construirFila(k, gates.entradas[k], c));
  filasAccion.sort((a, b) => GRUPOS.findIndex((g) => g.id === a.grupo) - GRUPOS.findIndex((g) => g.id === b.grupo)); // estable: dentro de cada grupo, el orden del archivo
  return [...filasEtapa, ...filasAccion];
}

/** Conteo por gate vigente y totales para la franja de métricas. */
export function resumenHoy(filas, aut) {
  const conteo = { H: 0, S: 0, A: 0, NA: 0, sin: 0 };
  for (const f of filas) conteo[f.gate || 'sin'] += 1;
  const con = filas.length - conteo.sin;
  const topesBloqueantes = new Set();
  for (const f of filas) for (const t of f.topes) if (t.bloquea) topesBloqueantes.add(t.clave);
  const etapas = aut.modelo ? aut.modelo.etapas.filter((e) => e.nivel) : [];
  return {
    total: filas.length, conGate: con, conteo, firmas: conteo.H,
    etapasConNivel: etapas.length, etapasEnN0: etapas.filter((e) => e.nivel === 'N0').length, todasN0: Boolean(aut.modelo && aut.modelo.todasN0),
    histograma: aut.modelo ? aut.modelo.histograma : {}, topesSinFijar: [...topesBloqueantes],
    forzadas: filas.filter((f) => f.limitadaPorLista).map((f) => f.clave),
  };
}

// ───────────────────────────────────────── frenos de empresa (J4) ─────────────────────────────────────────

/** OBJETIVO (J4, decisión del dueño 2026-11-06): 300 USD al día y pausa automática a 3.000 USD de pérdida acumulada. En unidades menores (centavos). */
export const OBJETIVO_FRENOS = { moneda: 'USD', gasto_diario_global: 30000, perdida_neta_acumulada_max: 300000 };

/** Divide un importe entre un factor decimal «1.75» sin float (BigInt). null si el factor no tiene la forma esperada. */
export function dividirPorFactor(minor, factor) {
  if (!Number.isSafeInteger(minor) || minor < 0) return null;
  const m = /^(\d{1,3})(?:\.(\d{1,2}))?$/.exec(String(factor ?? ''));
  if (!m) return null;
  const centesimas = BigInt(m[1]) * 100n + BigInt((m[2] || '').padEnd(2, '0') || '0');
  if (centesimas <= 0n) return null;
  return Number((BigInt(minor) * 100n) / centesimas);
}

function relacionConObjetivo(clave, valor, moneda) {
  if (valor === null || valor === undefined) return 'sin_fijar';
  if (!Number.isSafeInteger(valor)) return 'sin_fijar';
  if (moneda !== OBJETIVO_FRENOS.moneda) return 'otra_moneda';
  return valor === OBJETIVO_FRENOS[clave] ? 'igual' : 'distinto';
}

/** Los dos frenos de empresa: valor vigente (HOY) frente al objetivo (J4). `fmt.dinero` formatea sin float. */
export function modeloFrenos(lim, fmt) {
  const definicion = [
    { clave: 'gasto_diario_global', titulo: 'Gasto máximo por día', pregunta: 'Cuánto se gasta como máximo cada día (toda la empresa)', glosario: 'techo_gasto_diario', efecto: 'Ningún robot ni persona puede comprometer más que esto en un día.' },
    { clave: 'perdida_neta_acumulada_max', titulo: 'Pérdida antes de pausar todo', pregunta: 'Cuánto se pierde en total antes de que el sistema pause todo solo', glosario: 'pausa_por_perdida', efecto: 'Al llegar a esta pérdida acumulada se activa la PAUSA general (freno de emergencia); solo una persona la levanta.' },
  ];
  const factor = lim.hay && typeof lim.valores.factor_techo_teorico_diario === 'string' ? lim.valores.factor_techo_teorico_diario : null;
  const frenos = definicion.map((d) => {
    const topeEstado = modeloTope(d.clave, lim, fmt);
    const valor = lim.hay && Number.isSafeInteger(lim.valores[d.clave]) ? lim.valores[d.clave] : null;
    const relacion = !lim.hay ? 'sin_lectura' : relacionConObjetivo(d.clave, valor, lim.moneda);
    const objetivoMinor = OBJETIVO_FRENOS[d.clave];
    const derivado = d.clave === 'gasto_diario_global' ? {
      vigente: valor !== null ? dividirPorFactor(valor, factor) : null,
      objetivo: dividirPorFactor(objetivoMinor, factor || '1.75'),
      factor: factor || '1.75',
    } : null;
    return {
      ...d, estado: topeEstado.estado, bloquea: topeEstado.bloquea, relacion,
      vigente: { valor, moneda: lim.moneda, texto: valor !== null && lim.moneda ? fmt.dinero(valor, lim.moneda) : (valor !== null ? topeEstado.texto : null), mensaje: topeEstado.mensaje },
      objetivo: { valor: objetivoMinor, moneda: OBJETIVO_FRENOS.moneda, texto: fmt.dinero(objetivoMinor, OBJETIVO_FRENOS.moneda) },
      derivado: derivado ? { vigente: derivado.vigente, objetivo: derivado.objetivo, factor: derivado.factor, vigenteTexto: derivado.vigente !== null && lim.moneda ? fmt.dinero(derivado.vigente, lim.moneda) : null, objetivoTexto: derivado.objetivo !== null ? fmt.dinero(derivado.objetivo, OBJETIVO_FRENOS.moneda) : null } : null,
    };
  });
  const sello = lim.hay ? modeloTope('sello', lim, fmt) : null;
  return {
    hay: lim.hay, moneda: lim.moneda, frenos, fijados: frenos.filter((f) => f.vigente.valor !== null).length, total: frenos.length,
    iguales: frenos.filter((f) => f.relacion === 'igual').length, sello,
  };
}

const RX_OFERTA = /^(OF-[0-9]{6}-[0-9]{2}|_[a-z0-9][a-z0-9_-]{0,31})$/;

/** Comandos que SOLO muestra el panel (los ejecuta el dueño en su terminal). `oferta` se valida con la misma regla que la API; si no vale, un marcador. */
export function comandosFrenos(oferta) {
  const o = typeof oferta === 'string' && RX_OFERTA.test(oferta) ? oferta : '<id_de_la_oferta>';
  return {
    proponer: `.venv/bin/python -m engine.propuestas proponer --oferta ${o}`,
    ensayo: '.venv/bin/python -m engine.propuestas sellar --como dueno',
    firmar: 'FABRICA_ENTORNO=produccion .venv/bin/python -m engine.propuestas sellar --como dueno --live --clave-privada <ruta_de_tu_clave_privada>',
    estado: '.venv/bin/python -m engine.limites estado --operacion gastar',
  };
}

// ───────────────────────────────────────── objetivo (J2) ─────────────────────────────────────────

/** El reparto de decisiones del dueño, literal de mapeo.md §4 (tabla «Modelo de decisión»). */
export const COLUMNAS_J2 = [
  { id: 'dueno', titulo: 'Decide el dueño', quien: 'Tú', icono: 'usuario', items: [
    { id: 'techo', texto: 'Techo de gasto y capital en riesgo' }, { id: 'reglas', texto: 'Reglas de oro' }, { id: 'fiscal', texto: 'Régimen fiscal por país' },
    { id: 'idioma', texto: 'El primer idioma' }, { id: 'pausa', texto: 'Levantar la PAUSA general' }, { id: 'freno', texto: 'El freno de la captura de anuncios' },
  ] },
  { id: 'ia', titulo: 'Decide la IA (Claude)', quien: 'Claude', icono: 'chispa', items: [
    { id: 'produce', texto: 'Qué se produce' }, { id: 'testea', texto: 'Qué se testea' }, { id: 'corrige', texto: 'Qué se corrige (dentro de las reglas de cumplimiento)' },
  ] },
  { id: 'robots', titulo: 'Deciden los robots (programas automáticos)', quien: 'Robots', icono: 'robot', items: [
    { id: 'prende', texto: 'Prender y apagar' }, { id: 'presupuesto', texto: 'Subir y bajar presupuesto' }, { id: 'idioma_robot', texto: 'Frenar y rehabilitar un idioma' }, { id: 'cola', texto: 'Cargar lanzamientos' },
  ] },
  { id: 'llega', titulo: 'Le llega al dueño', quien: 'Te llega', icono: 'campana', items: [
    { id: 'resumen', texto: 'Resumen del día' }, { id: 'pagos', texto: 'Alertas de pago' }, { id: 'importante', texto: 'Lo importante' },
  ] },
];

/** «Qué se conserva por código, sin pedir clic» (mapeo.md §4). `estado`: lo que de verdad hay hoy se calcula en `modeloObjetivo` (rige | construir | falta_valor). */
export const SE_CONSERVA = [
  { id: 'sello_x1', texto: 'Visto bueno firmado de cumplimiento, vigente y sin alterar, sobre la versión exacta de lo que se activa', detalle: 'Sin esa firma no se activa. El cumplimiento no se negocia cuando se tiene una sola cuenta de Meta y una de Stripe.', glosario: 'sello_x1' },
  { id: 'preflight', texto: 'Chequeo antes de lanzar en verde y nivel de riesgo dentro de lo permitido', detalle: 'Los 26 puntos del chequeo en verde y un riesgo que no pase del nivel máximo permitido (sin fijar = solo verde).', glosario: 'preflight' },
  { id: 'frenos', texto: 'Frenos de empresa: 300 USD por día y pausa a −3.000 USD', detalle: 'Gasto máximo por día y pérdida total acumulada (decisión J4). Al llegar a la pérdida, la PAUSA general se activa sola.', glosario: 'frenos_empresa' },
  { id: 'pausa', texto: 'PAUSA, vigía de pagos y auditor', detalle: 'La PAUSA solo la levanta una persona. El vigía avisa si una cuenta deja de gastar por un pago. El auditor baja de nivel al robot que falla.', glosario: 'auditor_robots' },
  { id: 'rechazos', texto: 'Dos rechazos de anuncios en siete días congelan las activaciones nuevas', detalle: 'Con una sola cuenta de Meta, es el verdadero tope de velocidad (regla «rechazos que congelan»).', glosario: 'rechazos_congelan' },
];

const FUENTE_PLAN = 'mapeo.md';
const it = (estado, texto, fuente, tecnico) => ({ estado, texto, fuente: fuente || null, tecnico: tecnico || null });

/** Etiquetas de los estados de una comprobación (el icono y el texto siempre van juntos; el color nunca solo). */
export const ESTADO_ITEM = {
  ok: { etiqueta: 'Ya está (comprobado en los archivos)', tono: 'ok', icono: 'check' },
  pendiente: { etiqueta: 'Falta (comprobado en los archivos)', tono: 'aviso', icono: 'circulo-punteado' },
  plan: { etiqueta: 'Falta según el plan (el panel no lo puede comprobar)', tono: 'info', icono: 'lista' },
  nota: { etiqueta: 'Aclaración', tono: 'neutro', icono: 'info' },
  sin_dato: { etiqueta: 'No se pudo comprobar: falta leer un archivo', tono: 'aviso', icono: 'alerta' },
};
export const ESTADO_FILA = {
  ya: { etiqueta: 'Ya rige', tono: 'ok', icono: 'check' },
  parcial: { etiqueta: 'Rige en parte', tono: 'aviso', icono: 'progreso' },
  falta: { etiqueta: 'Aún no rige', tono: 'neutro', icono: 'circulo-punteado' },
};

const gDe = (gates, clave, nivel) => (gates.entradas[clave] && gates.entradas[clave].gate[nivel]) || null;
const todosLosNiveles = (gates, clave, valor) => Boolean(gates.entradas[clave]) && NIVELES.every((n) => gDe(gates, clave, n) === valor);

function listaVacia(v) { return Array.isArray(v) && v.length === 0; }
function nPermitidos(lim, clave) { return lim.hay && Array.isArray(lim.valores[clave]) ? lim.valores[clave].length : null; }

/** Resume una lista de comprobaciones en el estado de la fila. */
export function estadoDeFila(falta) {
  const hayFalta = falta.some((x) => x.estado === 'pendiente' || x.estado === 'plan' || x.estado === 'sin_dato');
  const hayOk = falta.some((x) => x.estado === 'ok');
  if (!hayFalta) return 'ya';
  return hayOk ? 'parcial' : 'falta';
}

function gateTexto(g) { return g ? GATES_INFO[g].etiqueta.toLowerCase() : 'sin dato'; }
function dinero(fmt, lim, clave) {
  if (!lim.hay) return 'sin lectura';
  const v = lim.valores[clave];
  return Number.isSafeInteger(v) && lim.moneda ? fmt.dinero(v, lim.moneda) : 'sin fijar';
}

/**
 * Las filas del OBJETIVO: una por cada decisión del reparto, con lo que hay HOY (calculado de los archivos) y «qué falta para llegar»
 * (comprobado donde se puede; `plan` donde solo lo dice el plan). Devuelve también el estado de cada comprobación de «Se conserva por código».
 */
export function modeloObjetivo({ gates, aut, lim, filas, sistema, fmt }) {
  const porClave = Object.fromEntries(filas.map((f) => [f.id, f]));
  const hayG = gates.hay;
  const hayA = aut.hay;
  const hayL = lim.hay;
  const gate = (k) => (porClave[k] ? porClave[k].gate : null);
  const nv = (n) => (n ? `nivel ${numeroNivel(n)}` : 'sin dato'); // «N3» → «nivel 3»
  // Cada comprobación lleva una frase simple (`texto`) y, aparte, su referencia técnica (`tecnico`: archivo o clave), que solo se ve en el detalle técnico.
  const sinG = (texto) => it('sin_dato', `${texto} (no se pudo leer la tabla de puntos de control)`, null, 'contratos/gates.json');
  const sinA = (texto) => it('sin_dato', `${texto} (no se pudieron leer los niveles de autonomía)`, null, 'empresa/autonomia.yaml');
  const sinL = (texto) => it('sin_dato', `${texto} (no se pudieron leer tus límites)`, null, 'empresa/limites.yaml');
  const noLimites = 'No se pudieron leer tus límites';
  const noGates = 'No se pudo leer la tabla de puntos de control';
  const pausa = sistema && esObj(sistema.pausa) ? sistema.pausa : null;
  const freno = sistema && esObj(sistema.freno_captura) ? sistema.freno_captura : null;
  // /api/sistema devuelve freno_captura = null cuando NO hay archivo de freno (libre); sin /api/sistema no se sabe
  const frenoPuesto = esObj(sistema) ? Boolean(freno && freno.activo) : null;
  const defs = {};

  // ───── Dueño ─────
  const gastoFijo = hayL && Number.isSafeInteger(lim.valores.gasto_diario_global);
  const perdidaFija = hayL && Number.isSafeInteger(lim.valores.perdida_neta_acumulada_max);
  const capitalFijo = hayL && Number.isSafeInteger(lim.valores.capital_en_riesgo_total);
  const selloFijado = hayL && esObj(lim.valores.sello);
  defs.techo = {
    hoy: hayL ? [`Gasto máximo por día: ${dinero(fmt, lim, 'gasto_diario_global')}`, `Pérdida antes de pausar todo: ${dinero(fmt, lim, 'perdida_neta_acumulada_max')}`, `Capital en riesgo: ${dinero(fmt, lim, 'capital_en_riesgo_total')}`] : [noLimites],
    falta: hayL ? [
      gastoFijo ? it('ok', 'Gasto máximo por día fijado') : it('pendiente', 'Fijar el gasto máximo por día (objetivo J4: 300 USD por día)', null, 'limites.yaml: fijar gasto_diario_global'),
      perdidaFija ? it('ok', 'Pérdida antes de pausar todo fijada') : it('pendiente', 'Fijar cuánto se puede perder antes de que el sistema pause todo (objetivo J4: 3.000 USD)', null, 'limites.yaml: fijar perdida_neta_acumulada_max'),
      capitalFijo ? it('ok', 'Capital en riesgo fijado') : it('pendiente', 'Fijar cuánto capital aceptas arriesgar (lo decides tú)', null, 'limites.yaml: fijar capital_en_riesgo_total'),
      selloFijado ? it('ok', 'Tus límites están firmados') : it('pendiente', 'Firmar tus límites (solo tú; sin tu firma nada gasta)', null, 'Firmar limites.yaml: python -m engine.propuestas sellar'),
      it('plan', 'Que la propuesta de límites traiga los 300 USD por día y los 3.000 USD de J4 (hoy calcula el gasto y la pérdida máximos de la prueba de cada oferta)', `${FUENTE_PLAN} §4, §10`, 'engine/propuestas.py'),
    ] : [sinL('Fijar los frenos de empresa')],
  };
  const lineas = hayL && Array.isArray(lim.valores.lineas_rojas) ? lim.valores.lineas_rojas.length : null;
  const nivelMax = hayL ? lim.valores.nivel_max_lanzable : undefined;
  defs.reglas = {
    hoy: hayL ? [`Líneas rojas: ${lineas === null ? 'sin dato' : lineas === 0 ? 'ninguna definida' : `${lineas} definidas`}`, `Nivel máximo lanzable: ${nivelMax === null || nivelMax === undefined ? 'sin fijar (solo verde)' : typeof nivelMax === 'string' ? nivelMax : 'fijado por área'}`] : [noLimites],
    falta: hayL ? [
      lineas && lineas > 0 ? it('ok', 'Líneas rojas confirmadas') : it('pendiente', 'Confirmar o recortar las líneas rojas (promesas, contenidos y modelos de negocio prohibidos)', null, 'limites.yaml: lineas_rojas'),
      nivelMax === null || nivelMax === undefined ? it('pendiente', 'Fijar el nivel máximo de riesgo que se puede lanzar (sin fijar = solo verde)', null, 'limites.yaml: nivel_max_lanzable') : it('ok', 'Nivel máximo lanzable fijado'),
      it('plan', 'Las seis reglas de oro aplicadas por el sistema, sin excepciones (una oferta que ya escala no se toca por dentro, el ganador sigue en prueba, se mira la tendencia de 3 días…)', `${FUENTE_PLAN} §3.3`),
    ] : [sinL('Definir las reglas de oro')],
  };
  const clavesFiscales = hayL ? Object.keys(lim.valores).filter((k) => /(^|_)(fiscal|iva|oss|impuestos?|tax)(_|$)/i.test(k)) : null;
  defs.fiscal = {
    hoy: [clavesFiscales === null ? noLimites : clavesFiscales.length ? `Hay datos fiscales en tus límites: ${clavesFiscales.join(', ')}` : 'Se decide fuera del panel, contigo y con el contador: no hay ningún dato fiscal en tus límites.'],
    falta: [it('plan', 'Decidir el régimen fiscal (Stripe Tax y el régimen de IVA de la UE, OSS) con el contador antes del 2.º idioma de la UE o del Reino Unido', 'decisiones-del-dueno.md, pendiente 4')],
  };
  const nLoc = nPermitidos(lim, 'locales_permitidos');
  const nPais = nPermitidos(lim, 'paises_permitidos');
  const nCue = nPermitidos(lim, 'cuentas_permitidas');
  defs.idioma = {
    hoy: hayL ? [`Idiomas permitidos: ${nLoc ? nLoc : 'ninguno'}`, `Países permitidos: ${nPais ? nPais : 'ninguno'}`, `Cuentas publicitarias: ${nCue ? nCue : 'ninguna'}`] : [noLimites],
    falta: hayL ? [
      nLoc ? it('ok', 'Hay al menos un idioma permitido') : it('pendiente', 'Elegir el primer idioma (el análisis de mercados dejó 5 opciones) y cargarlo entre los idiomas permitidos', null, 'limites.yaml: locales_permitidos'),
      nPais ? it('ok', 'Hay al menos un país permitido') : it('pendiente', 'Cargar los países permitidos', null, 'limites.yaml: paises_permitidos'),
      nCue ? it('ok', 'Hay una cuenta publicitaria permitida') : it('pendiente', 'Cargar la cuenta publicitaria permitida (una sola en esta etapa)', null, 'limites.yaml: cuentas_permitidas'),
    ] : [sinL('Elegir el primer idioma')],
  };
  defs.pausa = {
    hoy: [hayG ? `Reactivar tras una pausa: ${todosLosNiveles(gates, 'accion:reactivar_tras_pausa', 'H') ? 'lo firmas tú en los cinco niveles' : gateTexto(gate('accion:reactivar_tras_pausa'))}` : noGates, pausa ? (pausa.activa ? 'Hay una PAUSA activa ahora' : 'No hay ninguna PAUSA activa') : 'Estado de la PAUSA: sin dato'],
    falta: [hayG ? (todosLosNiveles(gates, 'accion:reactivar_tras_pausa', 'H') ? it('ok', 'Reactivar tras una pausa ya es decisión tuya en los cinco niveles, y se mantiene así en el objetivo', null, 'gates.json: reactivar_tras_pausa es H en los cinco niveles') : it('pendiente', 'Que reactivar tras una pausa sea siempre decisión tuya, en los cinco niveles', null, 'gates.json: reactivar_tras_pausa debe ser H en los cinco niveles')) : sinG('Reactivar tras una pausa sigue siendo tuyo')],
  };
  defs.freno = {
    hoy: [frenoPuesto === null ? 'Estado del freno de la captura de anuncios: sin dato' : frenoPuesto ? 'El freno de la captura de anuncios está puesto' : 'El freno de la captura de anuncios está libre'],
    falta: [it('nota', 'Ya rige así: solo una persona lo levanta, y el panel nunca lo borra', 'departamentos/02-descubrimiento.md §14')],
  };

  // ───── IA ─────
  const etapasMakers = ['D4', 'D6'];
  const makersN2 = hayA && etapasMakers.every((e) => alcanza(aut, e, 'N2'));
  defs.produce = {
    hoy: hayA ? [`Etapas en el nivel 0 (todo lo apruebas tú): ${aut.modelo.etapas.filter((e) => e.nivel === 'N0').length} de ${aut.modelo.etapas.filter((e) => e.nivel).length}`] : ['No se pudieron leer los niveles de autonomía'],
    falta: hayA ? [
      makersN2 ? it('ok', 'Producto y anuncios están en el nivel 2 o más') : it('pendiente', `Subir producto (hoy: ${nv(nivelDe(aut, 'D4'))}) y anuncios (hoy: ${nv(nivelDe(aut, 'D6'))}) al nivel 2 cuando cumplan las métricas de ascenso, con tu firma`, null, 'autonomia.yaml: D4 y D6 en N2 o más'),
      it('plan', 'Que los anuncios se produzcan en tandas programadas (imágenes estáticas, sin créditos) y una vista «Por aprobar»', `${FUENTE_PLAN} §6`),
    ] : [sinA('Subir etapas de nivel')],
  };
  defs.testea = {
    hoy: hayG ? [`Elegir el candidato (D1): ${gateTexto(gate('accion:elegir_candidato'))}`, `Activar una campaña: ${gateTexto(gate('accion:activar_campana'))}`] : [noGates],
    falta: [
      it('plan', 'Depende de que los robots puedan prender campañas (fila «Prender y apagar»): hoy probar una oferta es activarla', `${FUENTE_PLAN} §4`),
      hayG ? it('nota', `Hoy, elegir el candidato (D1): ${gateTexto(gate('accion:elegir_candidato'))} (según el nivel de la etapa). El plan de J2 no dice cuándo pasa a la IA: por definir`) : sinG('Elegir el candidato'),
    ],
  };
  defs.corrige = {
    hoy: hayG ? [`Cambiar la guía de trabajo o una regla: ${todosLosNiveles(gates, 'accion:cambiar_skill', 'H') ? 'lo firmas tú en los cinco niveles' : gateTexto(gate('accion:cambiar_skill'))}`, 'Corregir una pieza: la IA que prepara con la que revisa, hasta dos rondas'] : [noGates],
    falta: [
      hayG ? (todosLosNiveles(gates, 'accion:cambiar_skill', 'H') ? it('ok', 'Cambiar una regla o una guía de trabajo sigue siendo decisión tuya (corregir una pieza no lo es)', null, 'gates.json: cambiar_skill es H') : it('pendiente', 'Que cambiar una regla o una guía de trabajo siga siendo decisión tuya', null, 'gates.json: cambiar_skill debe seguir en H')) : sinG('Cambiar una regla o una guía de trabajo sigue siendo tuyo'),
    ],
  };

  // ───── Robots ─────
  const limitesRitmo = hayL && Number.isSafeInteger(lim.valores.aumento_presupuesto_max_pct_por_paso) && Number.isSafeInteger(lim.valores.horas_min_entre_aumentos);
  const activarA = hayG && gDe(gates, 'accion:activar_campana', 'N3') === 'A' && gDe(gates, 'accion:activar_campana', 'N4') === 'A';
  const activarEnLista = porClave['accion:activar_campana'] ? porClave['accion:activar_campana'].enLista : null;
  const pausarA = hayG && gDe(gates, 'accion:pausar', 'N2') === 'A';
  defs.prende = {
    hoy: hayG ? [
      `Activar una campaña: ${gateTexto(gate('accion:activar_campana'))}${porClave['accion:activar_campana'] && porClave['accion:activar_campana'].limitadaPorLista ? ` (la tabla llega a «${gateTexto(porClave['accion:activar_campana'].tablaPermite)}» en los niveles altos, pero rige tu firma)` : ''}`,
      `Pausar: ${gateTexto(gate('accion:pausar'))}`,
    ] : [noGates],
    falta: [
      hayG ? (activarA ? it('ok', 'Activar una campaña ya es automático en los niveles 3 y 4', null, 'contratos/gates.json: activar_campana ya es A en N3 y N4') : it('pendiente', `Cambiar la tabla de puntos de control para que activar una campaña pase de tu firma a automático, con condiciones (hoy en los niveles 3 y 4: ${gateTexto(gDe(gates, 'accion:activar_campana', 'N3'))} y ${gateTexto(gDe(gates, 'accion:activar_campana', 'N4'))})`, null, `contratos/gates.json: activar_campana de H a A con condiciones (hoy en N3 y N4: ${gDe(gates, 'accion:activar_campana', 'N3') || '—'} y ${gDe(gates, 'accion:activar_campana', 'N4') || '—'})`)) : sinG('Cambiar la tabla para que activar una campaña pase de tu firma a automático'),
      hayL || (gates.minimas && gates.minimas.length) ? (activarEnLista === false ? it('ok', 'Activar una campaña ya no está entre las acciones que siempre piden tu firma') : it('pendiente', 'Sacar «activar una campaña» de las seis acciones que siempre piden tu firma (hoy no se saca ni con tu firma; es la decisión D-02)', null, 'limites.yaml, contratos/limites.schema.json y scripts/validar_esquemas.py (ACCIONES_GATE_MINIMAS): quitar activar_campana de las seis acciones que siempre piden tu firma')) : sinL('Sacar «activar una campaña» de las acciones que siempre piden tu firma'),
      hayA ? (alcanza(aut, 'D7', 'N3') ? it('ok', 'Campañas están en el nivel 3 o más') : it('pendiente', `Subir campañas al nivel 3 o más, con tu firma (hoy: ${nv(nivelDe(aut, 'D7'))})`, null, `autonomia.yaml: campañas (D7) en N3 o más, con tu firma (hoy ${nivelDe(aut, 'D7') || 'sin dato'})`)) : sinA('Subir campañas al nivel 3'),
      hayG && hayA ? (pausarA && alcanza(aut, 'D8', 'N2') ? it('ok', 'Apagar solo: la optimización diaria está en el nivel 2 o más (pausar ya es automático desde el nivel 2)') : it('pendiente', `Apagar solo: subir la optimización diaria al nivel 2 o más (hoy: ${nv(nivelDe(aut, 'D8'))}); pausar ya es automático desde el nivel 2`, null, `autonomia.yaml: D8 en N2 o más (hoy ${nivelDe(aut, 'D8') || 'sin dato'}); pausar ya es A desde N2 en gates.json`)) : sinA('Apagar solo'),
      it('plan', 'Que el sistema compruebe por sí mismo, antes de activar sin tu clic: el visto bueno firmado de cumplimiento, el chequeo antes de lanzar, los frenos de empresa y el tamaño del paso', `${FUENTE_PLAN} §4, §10`, 'engine/guard.py y meta/activar'),
    ],
  };
  defs.presupuesto = {
    hoy: hayG ? [
      `Subir presupuesto (optimización diaria): ${gateTexto(gate('accion:aumentar_presupuesto_d8'))}`,
      `Subir presupuesto (escalado): ${gateTexto(gate('accion:subir_presupuesto_d9'))}`,
      `Por encima del tope: ${gateTexto(gate('accion:subir_presupuesto_sobre_tope'))}`,
    ] : [noGates],
    falta: [
      hayG ? (gDe(gates, 'accion:aumentar_presupuesto_d8', 'N3') === 'A' && gDe(gates, 'accion:subir_presupuesto_d9', 'N3') === 'A' ? it('ok', 'Subir presupuesto ya es automático desde el nivel 3, dentro del plan y del tope', null, 'gates.json: subir presupuesto es A desde N3 (D8 y D9)') : it('pendiente', 'Que subir presupuesto sea automático desde el nivel 3, en la optimización diaria y en el escalado', null, 'gates.json: subir presupuesto debe ser A desde N3 (D8 y D9)')) : sinG('Que subir presupuesto sea automático desde el nivel 3'),
      hayA ? (alcanza(aut, 'D8', 'N3') && alcanza(aut, 'D9', 'N3') ? it('ok', 'Optimización diaria y escalado están en el nivel 3 o más') : it('pendiente', `Subir al nivel 3, con tu firma, la optimización diaria (hoy: ${nv(nivelDe(aut, 'D8'))}) y el escalado (hoy: ${nv(nivelDe(aut, 'D9'))})`, null, `autonomia.yaml: D8 (hoy ${nivelDe(aut, 'D8') || 'sin dato'}) y D9 (hoy ${nivelDe(aut, 'D9') || 'sin dato'}) en N3, con tu firma`)) : sinA('Optimización diaria y escalado en el nivel 3'),
      hayL ? (limitesRitmo ? it('ok', 'Tamaño máximo del paso y horas entre subidas fijados') : it('pendiente', 'Fijar el tamaño máximo de cada subida y las horas mínimas entre una y otra (ritmo de las subidas)', null, 'limites.yaml: aumento_presupuesto_max_pct_por_paso y horas_min_entre_aumentos')) : sinL('Fijar el ritmo de las subidas'),
      it('plan', 'Que el sistema verifique el tamaño del paso de cada subida', `${FUENTE_PLAN} §4, §10`, 'engine/guard.py'),
      it('plan', 'Que la orden de ESCALAR se ejecute de verdad (hoy solo se anota) y escalera de ×2 al inicio; ×3 y ×5 solo cuando el auditor demuestre acierto', `${FUENTE_PLAN} §1, §3.3`, 'engine/d8.py'),
    ],
  };
  defs.idioma_robot = {
    hoy: hayG ? [`Frenar (pausar): ${gateTexto(gate('accion:pausar'))}`, `Reactivar tras una pausa: ${gateTexto(gate('accion:reactivar_tras_pausa'))}`, `Idioma nuevo: ${gateTexto(gate('accion:lanzamiento_pais_idioma_nuevo'))}`] : [noGates],
    falta: [
      hayA ? (alcanza(aut, 'D8', 'N2') ? it('ok', 'Frenar un idioma: la optimización diaria está en el nivel 2 o más') : it('pendiente', `Para frenar un idioma solo: subir la optimización diaria al nivel 2 o más (hoy: ${nv(nivelDe(aut, 'D8'))})`, null, `autonomia.yaml: D8 en N2 o más (hoy ${nivelDe(aut, 'D8') || 'sin dato'})`)) : sinA('Frenar un idioma'),
      it('plan', 'Definir el lanzamiento por idioma y filtrar por idioma al cargar campañas (hoy se envían solo países)', `${FUENTE_PLAN} §1, §8`, 'contrato lanzamiento_idioma y filtro de idioma en meta/payloads.py'),
      it('plan', 'Definir cómo se rehabilita un idioma (3 días concentrados y decisión al día 7) sin tocar «reactivar tras una PAUSA general», que sigue siendo tuyo', `${FUENTE_PLAN} §4, §8`, 'contratos/gates.json'),
    ],
  };
  defs.cola = {
    hoy: hayG ? [`Cada lanzamiento lo prendes tú: activar una campaña = ${gateTexto(gate('accion:activar_campana'))}`] : [noGates],
    falta: [
      it('plan', 'Los robots, con sus trabajos programados, su señal de vida y su nivel (la cola de pruebas se carga a las 00:10)', `${FUENTE_PLAN} §1, §2, §10`, 'empresa/robots.yaml'),
      it('plan', 'Cargar a Meta en pausa, un conjunto por pieza, y un auditor que mida el acierto de cada robot', `${FUENTE_PLAN} §2, §11`),
    ],
  };

  // ───── Te llega ─────
  defs.resumen = {
    hoy: ['Lo ves aquí, en el Resumen, cuando abres el panel; no te llega nada solo al celular.'],
    falta: [it('plan', 'Resumen diario a las 08:30 (importes en el correo, porcentajes en el aviso) y un canal de avisos al celular, que aún no elegiste (siempre con dos canales)', `${FUENTE_PLAN} §9`)],
  };
  defs.pagos = {
    hoy: ['Las alertas de dinero se ven en Finanzas; no hay aviso al celular.'],
    falta: [it('plan', 'Vigía de pagos: avisa si una cuenta publicitaria deja de gastar por un problema de pago', `${FUENTE_PLAN} §2, §4`), it('plan', 'Que se generen las alertas y lleguen al celular', `${FUENTE_PLAN} §9`, 'dashboard.alertas')],
  };
  defs.importante = {
    hoy: ['Las alertas existen (con su gravedad y su ciclo de vida) pero no se filtran hacia el celular.'],
    falta: [it('plan', 'Una tabla de gravedad → canal y un máximo de avisos por día; lo demás va al resumen', `${FUENTE_PLAN} §9`)],
  };

  const filasObjetivo = [];
  for (const col of COLUMNAS_J2) {
    for (const item of col.items) {
      const d = defs[item.id];
      const falta = d.falta;
      filasObjetivo.push({ id: `${col.id}.${item.id}`, columna: col.id, quien: col.quien, texto: item.texto, hoy: d.hoy, falta, estado: estadoDeFila(falta) });
    }
  }
  const cuenta = { ya: 0, parcial: 0, falta: 0 };
  for (const f of filasObjetivo) cuenta[f.estado] += 1;

  // «Se conserva por código»: qué hay de verdad hoy
  const frenosOk = gastoFijo && perdidaFija;
  const conserva = SE_CONSERVA.map((c) => {
    let estado = 'rige';
    let nota = null;
    if (c.id === 'frenos') {
      estado = !hayL ? 'sin_dato' : frenosOk ? 'rige' : 'falta_valor';
      nota = !hayL ? 'No se pudieron leer tus límites' : frenosOk ? 'Los dos valores están fijados' : 'Falta fijar los valores (pestaña «Frenos de empresa»)';
    } else if (c.id === 'pausa') {
      estado = 'construir';
      nota = `${pausa ? (pausa.activa ? 'Hay una PAUSA activa ahora. ' : 'La PAUSA existe y hoy no hay ninguna activa. ') : ''}El vigía de pagos y el auditor de acierto están por construir (según el plan, pieza 5)`;
    } else if (c.id === 'preflight') {
      nota = hayL ? (lim.nulos.has('nivel_max_lanzable') || lim.valores.nivel_max_lanzable == null ? 'Nivel máximo lanzable sin fijar: solo se lanza verde' : 'Nivel máximo lanzable fijado') : null;
    } else if (c.id === 'sello_x1') {
      nota = 'Ya se exige para publicar la página de venta y para activar (según la tabla de puntos de control)';
    } else if (c.id === 'rechazos') {
      nota = 'Regla vigente hoy';
    }
    return { ...c, estado, nota };
  });

  return { columnas: COLUMNAS_J2, filas: filasObjetivo, conserva, cuenta, total: filasObjetivo.length };
}

export const ESTADO_CONSERVA = {
  rige: { etiqueta: 'Ya existe hoy', tono: 'ok', icono: 'check' },
  falta_valor: { etiqueta: 'Falta fijar el valor', tono: 'aviso', icono: 'circulo-punteado' },
  construir: { etiqueta: 'En parte por construir', tono: 'info', icono: 'lista' },
  sin_dato: { etiqueta: 'No se pudo comprobar', tono: 'aviso', icono: 'alerta' },
};

// ───────────────────────────────────────── lo que sigue siendo humano ─────────────────────────────────────────

export const COMANDO_QUITAR_PAUSA = 'rm empresa/PAUSA';
export const COMANDO_LEER_FRENO = 'cat empresa/captura/freno.json';
export const COMANDO_QUITAR_FRENO = 'rm empresa/captura/freno.json';

/** Las decisiones que, aunque los robots prendan solos, siguen siendo tuyas. Cada una: gate vigente en la tabla, estado actual y el comando que ejecutarías tú. */
export function modeloHumano({ filas, gates, lim, sistema, fmt }) {
  const pausa = sistema && esObj(sistema.pausa) ? sistema.pausa : null;
  const freno = sistema && esObj(sistema.freno_captura) ? sistema.freno_captura : null;
  const frenoPuesto = esObj(sistema) ? Boolean(freno && freno.activo) : null; // null en /api/sistema = sin archivo de freno = libre
  const porClave = Object.fromEntries((filas || []).map((f) => [f.id, f]));
  // gate que RIGE (el más estricto) de la fila de la tabla «Hoy»; null si no hay tabla
  const g = (clave) => (porClave[clave] ? { gate: porClave[clave].gate, constante: porClave[clave].constante, limitada: porClave[clave].limitadaPorLista, tablaPermite: porClave[clave].tablaPermite, porNivel: porClave[clave].porNivel } : null);
  const selloOk = lim.hay && esObj(lim.valores.sello);
  const lineas = lim.hay && Array.isArray(lim.valores.lineas_rojas) ? lim.valores.lineas_rojas.length : null;
  const nivelMax = lim.hay ? lim.valores.nivel_max_lanzable : undefined;
  const nLoc = nPermitidos(lim, 'locales_permitidos');
  const cmds = comandosFrenos(null);
  const trozoPausa = pausa && pausa.activa ? `Hay una PAUSA activa${typeof pausa.motivo === 'string' && pausa.motivo ? `: ${pausa.motivo}` : ''}` : 'No hay ninguna PAUSA activa ahora';
  return [
    {
      id: 'pausa', titulo: 'Reactivar tras una PAUSA general', icono: 'pausa', glosario: 'pausa', gate: g('accion:reactivar_tras_pausa'),
      porque: 'Ningún robot reactiva, ni siquiera tras una pausa por error: la pausa general es la red de seguridad y solo una persona decide cuándo se levanta.',
      actual: pausa ? { tono: pausa.activa ? 'critico' : 'ok', texto: trozoPausa, icono: pausa.activa ? 'pausa' : 'ok' } : { tono: 'neutro', texto: 'Estado de la PAUSA: sin dato', icono: 'info' },
      pasos: ['Lee el motivo y corrige la causa.', 'Comprueba que el chequeo de cuentas y servicios vuelve a estar en verde y al día.', 'Borra el archivo de la pausa a mano; el panel nunca lo hace.'],
      comandos: [{ titulo: 'Levantar la PAUSA (lo haces tú)', cmd: COMANDO_QUITAR_PAUSA, nota: 'Solo cuando hayas corregido la causa.' }], ruta: '#/sistema', rutaTexto: 'Ver el estado en Salud del sistema',
    },
    {
      id: 'limites', titulo: 'Firmar tus límites', icono: 'firma', glosario: 'lim_sello', gate: g('accion:cambiar_limites'),
      porque: 'Los techos de gasto y de pérdida solo cambian con tu firma. El sistema prepara la propuesta; firmar es cosa tuya.',
      actual: lim.hay ? { tono: selloOk ? 'ok' : 'aviso', texto: selloOk ? 'Tus límites están firmados' : 'Tus límites no están firmados: nada gasta ni activa', icono: selloOk ? 'ok' : 'candado' } : { tono: 'neutro', texto: 'No se pudieron leer tus límites', icono: 'info' },
      pasos: ['Prepara la propuesta (no cambia tus límites).', 'Haz un ensayo: se revisa la propuesta y se calcula la firma, sin guardar nada.', 'Firma y guarda los límites con tu clave.'],
      comandos: [
        { titulo: '1 · Preparar la propuesta', cmd: cmds.proponer, nota: 'Sustituye <id_de_la_oferta> por la oferta que usarás de referencia.' },
        { titulo: '2 · Ensayo (no guarda nada)', cmd: cmds.ensayo },
        { titulo: '3 · Firmar y guardar tus límites', cmd: cmds.firmar, nota: 'Solo tú: necesita tu clave privada y el entorno de producción.' },
      ], ruta: '#/parametros', rutaTexto: 'Ver los límites',
    },
    {
      id: 'reglas', titulo: 'Cambiar las reglas de oro', icono: 'balanza', glosario: 'sigue_humano', gate: g('accion:cambiar_skill'), gate2: g('accion:cambiar_limites'),
      porque: 'Las reglas son el activo: el sistema las aplica, no las inventa. Cambiar las líneas rojas, el nivel máximo lanzable o la guía de trabajo de un agente lo decides tú; un robot nunca escribe las reglas que leen los demás.',
      actual: lim.hay ? { tono: lineas === 0 || nivelMax == null ? 'aviso' : 'ok', texto: `${lineas === 0 ? 'Sin líneas rojas definidas' : lineas === null ? 'Líneas rojas: sin dato' : `${lineas} líneas rojas definidas`} · ${nivelMax == null ? 'nivel máximo lanzable sin fijar (solo verde)' : 'nivel máximo lanzable fijado'}`, icono: lineas === 0 || nivelMax == null ? 'alerta' : 'ok' } : { tono: 'neutro', texto: 'No se pudieron leer tus límites', icono: 'info' },
      pasos: ['Las líneas rojas y el nivel máximo están en tus límites: se cambian con la propuesta y tu firma (ver «Firmar tus límites»).', 'Una guía de trabajo o una regla de un agente cambia solo con tu aprobación (acción «Cambiar la guía de trabajo o una regla de un agente»).'],
      comandos: [], ruta: '#/parametros', rutaTexto: 'Ver los límites',
    },
    {
      id: 'freno', titulo: 'Levantar el freno de la captura de anuncios', icono: 'candado', glosario: 'freno_captura', gate: null,
      porque: 'Si Meta bloquea la captura (pide un captcha, pone un límite de consultas o exige iniciar sesión), el sistema se detiene y no reintenta. Decidir si conviene reanudar es solo tuyo: insistir sería esquivar un bloqueo.',
      actual: frenoPuesto === null ? { tono: 'neutro', texto: 'Estado del freno: sin dato', icono: 'info' } : { tono: frenoPuesto ? 'aviso' : 'ok', texto: frenoPuesto ? `Freno PUESTO${typeof freno.motivo === 'string' && freno.motivo ? `: ${freno.motivo}` : ''}` : 'El freno de la captura de anuncios está libre', icono: frenoPuesto ? 'candado' : 'ok' },
      pasos: ['Lee el motivo con el primer comando.', 'Decide si conviene reanudar.', 'Si conviene, borra el archivo del freno a mano; el panel nunca lo hace.'],
      comandos: [{ titulo: 'Leer el motivo del freno', cmd: COMANDO_LEER_FRENO }, { titulo: 'Levantar el freno (lo haces tú)', cmd: COMANDO_QUITAR_FRENO }], ruta: '#/sistema', rutaTexto: 'Ver el estado en Salud del sistema',
    },
    {
      id: 'idioma', titulo: 'Abrir un idioma o país nuevo', icono: 'mundo', glosario: 'lim_locales_permitidos', gate: g('accion:lanzamiento_pais_idioma_nuevo'),
      porque: 'Un idioma nuevo es una oferta nueva con su marca, su dominio y su régimen fiscal. Elegir el primero y decidir el régimen fiscal por país es tuyo; lo que los robots pueden hacer después es frenarlo.',
      actual: lim.hay ? { tono: nLoc ? 'ok' : 'aviso', texto: nLoc ? `${nLoc} ${nLoc === 1 ? 'idioma permitido' : 'idiomas permitidos'}` : 'Ningún idioma permitido: hoy no se puede lanzar en ninguno', icono: nLoc ? 'ok' : 'candado' } : { tono: 'neutro', texto: 'No se pudieron leer tus límites', icono: 'info' },
      pasos: ['Elige el primer idioma entre las opciones que dejó el análisis de mercados.', 'Cárgalo entre los idiomas, países y cuentas permitidos con la propuesta y tu firma.', 'Decide el régimen fiscal con el contador antes del 2.º idioma de la UE o del Reino Unido.'],
      comandos: [], ruta: '#/parametros', rutaTexto: 'Ver los límites',
    },
  ];
}

// ───────────────────────────────────────── modelo completo ─────────────────────────────────────────

/** Une las lecturas en el modelo de la pantalla. Cada entrada puede faltar (null): la parte que depende de ella dice qué falta. */
export function modeloQuienDecide({ gates: datosGates, parametros, sistema } = {}, fmt) {
  const gates = leerGates(datosGates);
  const lim = leerLimites(parametros);
  const aut = leerAutonomia(parametros);
  const faltan = [];
  if (!gates.hay) faltan.push('contratos/gates.json');
  if (!lim.hay) faltan.push('empresa/limites.yaml');
  if (!aut.hay) faltan.push('empresa/autonomia.yaml');
  const filas = gates.hay ? filasHoy({ gates, aut, lim, fmt }) : [];
  const resumen = gates.hay ? resumenHoy(filas, aut) : null;
  const objetivo = modeloObjetivo({ gates, aut, lim, filas, sistema, fmt });
  const frenos = modeloFrenos(lim, fmt);
  const humano = modeloHumano({ filas, gates, lim, sistema, fmt });
  return { hay: { gates: gates.hay, limites: lim.hay, autonomia: aut.hay, sistema: Boolean(sistema) }, faltan, gates, lim, aut, hoy: { filas, resumen, grupos: GRUPOS }, objetivo, frenos, humano };
}

/** Filtra las filas de «Hoy» por tipo de gate vigente (`todo` o H|S|A|NA) y por texto (nombre, clave, descripción, topes). Puro. */
export function filtrarFilas(filas, { gate = 'todo', texto = '' } = {}) {
  const q = String(texto || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
  return filas.filter((f) => {
    if (gate !== 'todo' && (f.gate || 'sin') !== gate) return false;
    if (!q) return true;
    const pajar = [f.nombre, f.clave, f.descripcion || '', ...f.topes.map((t) => `${t.clave} ${t.nombre}`)].join(' ').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
    return q.split(/\s+/).every((p) => pajar.includes(p));
  });
}

// ───────────────────────────────────────── mensajes de negocio (cartel y métricas) ─────────────────────────────────────────

/** El cartel de arriba: una frase de HOY (de los archivos) y una de OBJETIVO (decisión J2, aún sin implementar). */
export function mensajesBanner(m) {
  const r = m.hoy.resumen;
  let hoy;
  if (r) {
    const partes = [];
    partes.push(m.hay.autonomia
      ? (r.todasN0 ? `Las ${r.etapasConNivel} etapas están en el nivel 0 (todo lo apruebas tú): nada avanza solo.` : `${r.etapasEnN0} de ${r.etapasConNivel} etapas siguen en el nivel 0 (todo lo apruebas tú).`)
      : 'No se pudo leer el nivel de autonomía de las etapas.');
    partes.push(m.hay.limites
      ? (m.frenos.fijados === 0 ? 'Los frenos de empresa están sin fijar: por defecto no se puede gastar.'
        : m.frenos.fijados === m.frenos.total ? 'Los dos frenos de empresa están fijados.' : `Falta fijar ${m.frenos.total - m.frenos.fijados} de los 2 frenos de empresa.`)
      : 'No se pudieron leer tus límites.');
    hoy = { titulo: `Hoy, ${r.firmas} de ${r.conGate} decisiones las firmas tú`, detalle: partes.join(' ') };
  } else {
    hoy = { titulo: 'Hoy: no se pudo leer la tabla de puntos de control', detalle: 'Sin esa tabla no se puede decir quién decide cada paso.' };
  }
  const o = m.objetivo;
  const objetivo = {
    titulo: 'Los robots prenden, suben, apagan y frenan idiomas solos, dentro de frenos de empresa',
    detalle: `Decisión J2 que tomaste el 2026-11-06. Todavía no rige: ${o.cuenta.ya} de ${o.total} decisiones del reparto ya funcionan así, ${o.cuenta.parcial} en parte y ${o.cuenta.falta} aún no.`,
  };
  return { hoy, objetivo };
}

/** Las cuatro métricas de la franja superior (se pintan con ui.metrica). */
export function metricasQuienDecide(m, fmt) {
  const r = m.hoy.resumen;
  const etapasN = m.aut.modelo ? m.aut.modelo.etapas.filter((e) => e.nivel) : [];
  const niv = etapasN.length ? { total: etapasN.length, enN0: etapasN.filter((e) => e.nivel === 'N0').length, todasN0: etapasN.every((e) => e.nivel === 'N0') } : null; // de autonomia.yaml, aunque falte gates.json
  const n = (x) => fmt.numero(x);
  return [
    {
      id: 'firmas', etiqueta: 'Decisiones que hoy firmas tú', ayuda: 'gate_efectivo',
      valor: r ? `${n(r.firmas)} de ${n(r.conGate)}` : null,
      contexto: r ? (r.forzadas.length ? `Incluye ${r.forzadas.length} acciones que seguirán siendo tuyas aunque subas de nivel` : 'Según la tabla de puntos de control y el nivel de cada etapa') : 'Falta leer la tabla de puntos de control',
      tono: null,
    },
    {
      id: 'niveles', etiqueta: 'Etapas en el nivel 0 (todo lo apruebas tú)', ayuda: 'nivel_de_etapa',
      valor: niv ? `${n(niv.enN0)} de ${n(niv.total)}` : null,
      contexto: niv ? (niv.todasN0 ? 'Nada avanza solo: subir de nivel lo firmas tú' : 'Subir de nivel exige buenos resultados medidos y tu firma') : 'Falta leer los niveles de autonomía',
      tono: niv && niv.todasN0 ? 'aviso' : null,
    },
    {
      id: 'frenos', etiqueta: 'Frenos de empresa fijados', ayuda: 'frenos_empresa',
      valor: m.hay.limites ? `${n(m.frenos.fijados)} de ${n(m.frenos.total)}` : null,
      contexto: m.hay.limites ? (m.frenos.fijados === m.frenos.total ? 'Gasto máximo por día y pérdida antes de pausar todo' : 'Sin fijar: por defecto no se puede gastar') : 'Falta leer tus límites',
      tono: m.hay.limites ? (m.frenos.fijados === m.frenos.total ? 'ok' : 'aviso') : null,
    },
    {
      id: 'j2', etiqueta: 'Reparto elegido (J2) que ya rige', ayuda: 'objetivo_j2',
      valor: `${n(m.objetivo.cuenta.ya)} de ${n(m.objetivo.total)}`,
      contexto: 'Objetivo aún sin implementar: falta lo que indica la pestaña «Objetivo»',
      tono: null,
    },
  ];
}

/** Pestañas de la pantalla (id, título y contador). */
export function pestanasQuienDecide(m) {
  return [
    { id: 'hoy', titulo: 'Hoy', contador: m.hay.gates ? m.hoy.filas.length : undefined },
    { id: 'objetivo', titulo: 'Objetivo (J2)', contador: `${m.objetivo.cuenta.ya}/${m.objetivo.total}` },
    { id: 'frenos', titulo: 'Frenos de empresa', contador: m.hay.limites ? `${m.frenos.fijados}/${m.frenos.total}` : undefined },
    { id: 'humano', titulo: 'Sigue siendo tuyo', contador: m.humano.length },
  ];
}
