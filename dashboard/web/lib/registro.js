// lib/registro.js — lógica pura de la pantalla Registro (auditoría de empresa/registro.jsonl). Sin DOM.
// GET /registro?desde=&limite=&oferta=&etapa=&agente= → {lineas:[{n, ts, ejecucion_id, oferta_id, etapa, agente, evento, herramienta,
//   entrada_resumen, resultado:{estado,codigo}, costo_estimado:{monto,moneda}, modo, hash_previo, hash, …}], total, siguiente, cadena_ok}

import { fmt } from '../ui.js';

export const MAX_LINEAS_MEMORIA = 2000;
export const LIMITE_PAGINA = 200;
export const EVENTOS = ['accion', 'transicion', 'llamada_herramienta', 'decision', 'bloqueo', 'alerta', 'aprobacion'];
export const ETAPAS_REGISTRO = ['O0', 'D0', 'M1', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10', 'F1', 'F2', 'X1', 'X2'];

/** Parámetros de consulta: solo valores no vacíos (el servidor valida de nuevo). */
export function paramsConsulta({ desde, limite = LIMITE_PAGINA, oferta, etapa, agente } = {}) {
  const p = { limite };
  if (Number.isInteger(desde) && desde >= 1) p.desde = desde; // el servidor numera desde 1
  if (oferta) p.oferta = oferta;
  if (etapa) p.etapa = etapa;
  if (agente) p.agente = agente;
  return p;
}

/** Una línea del registro como la usa la vista; descarta lo que no sea objeto con `n` entero. */
export function normalizarLinea(l) {
  if (!l || typeof l !== 'object' || !Number.isInteger(l.n)) return null;
  const r = l.resultado && typeof l.resultado === 'object' ? l.resultado : {};
  return { ...l, resultado: { estado: r.estado ?? null, codigo: Number.isInteger(r.codigo) ? r.codigo : null } };
  // `_ilegible: true` + `_texto`: línea que el servidor no pudo interpretar (señal de integridad: se muestra en rojo)
}

/** Fusiona líneas nuevas con las que ya hay: sin duplicados por `n`, orden ascendente, tope de memoria (se descartan las más viejas). */
export function fusionarLineas(actuales, nuevas, max = MAX_LINEAS_MEMORIA) {
  const mapa = new Map();
  for (const l of Array.isArray(actuales) ? actuales : []) { const x = normalizarLinea(l); if (x) mapa.set(x.n, x); }
  const agregadas = [];
  for (const l of Array.isArray(nuevas) ? nuevas : []) {
    const x = normalizarLinea(l);
    if (!x) continue;
    if (!mapa.has(x.n)) agregadas.push(x.n);
    mapa.set(x.n, x);
  }
  let lineas = [...mapa.values()].sort((a, b) => a.n - b.n);
  if (lineas.length > max) lineas = lineas.slice(lineas.length - max);
  return { lineas, agregadas };
}

/** Historial sin alteraciones / alterado / sin verificar (la «cadena» de huellas, dicha en palabras de todos los días). `vacio` = no existe el archivo aún. */
export function estadoCadena(cadenaOk, { vacio = false } = {}) {
  if (vacio) return { tono: 'neutro', texto: 'Sin historial aún', detalle: 'Todavía no hay historial: aparece cuando el sistema anota su primera acción.' };
  if (cadenaOk === true) return { tono: 'ok', texto: tituloIntegridad('ok'), detalle: 'Cada línea queda atada a la anterior: si alguien tocara una, se notaría.' };
  if (cadenaOk === false) return { tono: 'error', texto: tituloIntegridad('error'), detalle: 'Alguna línea no coincide con la anterior: el historial pudo alterarse. No uses estos datos para decidir.' };
  return { tono: 'neutro', texto: 'Sin verificar', detalle: 'No se pudo comprobar si el historial está intacto.' };
}

/** Título en palabras de todos los días para el estado de la cadena (lo usan la pantalla Historial y el Resumen, vía `estadoCadena().texto`). */
export function tituloIntegridad(tono, textoOriginal = '') {
  return { ok: 'Historial sin alteraciones', error: 'Historial alterado' }[tono] || textoOriginal;
}

/** Tono de una línea para la fila: error del resultado, bloqueo o alerta. */
export function tonoDeLinea(l) {
  const est = l && l.resultado && l.resultado.estado;
  if (l && l._ilegible) return 'error';
  if (est === 'error') return 'error';
  if (est === 'bloqueado' || l.evento === 'bloqueo') return 'aviso';
  if (l.evento === 'alerta') return 'aviso';
  if (est === 'ok') return 'ok';
  if (est === 'dry_run') return 'info';
  return 'neutro';
}

/** Chip del resultado de una línea del registro: {tono, texto}. `bloqueado` (un guard frenó algo) es aviso, no error. */
export function chipResultado(estado) {
  switch (estado) {
    case 'ok': return { tono: 'ok', texto: 'OK' };
    case 'error': return { tono: 'error', texto: 'Error' };
    case 'bloqueado': return { tono: 'aviso', texto: 'Bloqueado' };
    case 'dry_run': return { tono: 'info', texto: 'Simulado' };
    case null: case undefined: case '': return { tono: 'neutro', texto: '—' };
    default: return { tono: 'neutro', texto: String(estado) };
  }
}

/** Valores distintos (ordenados, sin nulos) de un campo, para poblar los selectores. */
export function valoresDistintos(lineas, campo) {
  const s = new Set();
  for (const l of Array.isArray(lineas) ? lineas : []) { const v = l && l[campo]; if (typeof v === 'string' && v) s.add(v); }
  return [...s].sort((a, b) => a.localeCompare(b, 'es', { numeric: true }));
}

/** Filtro local (sobre lo cargado): evento exacto, resultado y texto libre en resumen/herramienta/agente/ids. */
export function filtrarLocal(lineas, { evento, resultado, texto, oferta, etapa, agente } = {}) {
  const q = String(texto || '').trim().toLowerCase();
  return (Array.isArray(lineas) ? lineas : []).filter((l) => {
    if (evento && l.evento !== evento) return false;
    if (resultado && !(l.resultado && l.resultado.estado === resultado)) return false;
    if (oferta && l.oferta_id !== oferta) return false;
    if (etapa && l.etapa !== etapa) return false;
    if (agente && l.agente !== agente) return false;
    if (q) {
      const pajar = [l.entrada_resumen, l.herramienta, l.agente, l.oferta_id, l.etapa, l.ejecucion_id, l.evento, String(l.n)].filter(Boolean).join(' ').toLowerCase();
      if (!pajar.includes(q)) return false;
    }
    return true;
  });
}

/** Desde qué `n` pedir lo nuevo: el mayor visto + 1 (o `siguiente` del servidor si es mayor). */
export function siguienteDesde(lineas, siguienteServidor) {
  const maxN = (Array.isArray(lineas) ? lineas : []).reduce((m, l) => (l && Number.isInteger(l.n) && l.n > m ? l.n : m), 0);
  return Math.max(maxN + 1, Number.isInteger(siguienteServidor) ? siguienteServidor : 0);
}

/** Desde qué `n` pedir lo anterior a lo cargado (null si ya estamos en el principio). */
export function desdeAnterior(lineas, limite = LIMITE_PAGINA) {
  const minN = (Array.isArray(lineas) ? lineas : []).reduce((m, l) => (l && Number.isInteger(l.n) && (m === null || l.n < m) ? l.n : m), null);
  if (minN === null || minN <= 1) return null;
  return Math.max(1, minN - limite);
}

/** Texto plano de una línea (para copiar). */
export function lineaComoTexto(l) {
  return JSON.stringify(l);
}

/** Pares clave/valor ordenados para el detalle de un evento (lo importante primero, hashes al final). */
export function paresDetalle(l) {
  if (!l) return [];
  const orden = ['n', 'ts', 'ejecucion_id', 'oferta_id', 'etapa', 'agente', 'skill_version', 'evento', 'herramienta', 'modo', 'hash_previo', 'hash'];
  return orden.filter((k) => k in l).map((k) => [k, l[k]]);
}

// ───────────────────────── lenguaje humano (rediseño UX) ─────────────────────────
// El registro sigue siendo la fuente de verdad: aquí solo se TRADUCE cada línea a una frase y a metadatos de presentación.
// Lo técnico (evento, herramienta, ids, hashes, JSON) no se pierde: lo recoge `detalleTecnicoLinea` para la sección desplegable.

/** Etapas con nombre humano (corto): el código queda como etiqueta secundaria. */
export const NOMBRE_ETAPA = {
  M1: 'Mercado', D1: 'Descubrir', D2: 'Validar', D3: 'Oferta', D4: 'Producto', D5: 'Página de venta y pago', D6: 'Anuncios', D7: 'Campaña',
  D8: 'Operación', D9: 'Escalado', D10: 'Después de la venta', O0: 'Coordinador general', D0: 'Cuentas y servicios base', F1: 'Finanzas', F2: 'Panel y números', X1: 'Cumplimiento', X2: 'Aprendizaje',
};
export const nombreEtapa = (c) => (typeof c === 'string' && NOMBRE_ETAPA[c]) || (c ? String(c) : '');
/** «Campaña (D7)»; sin nombre conocido devuelve el código tal cual. */
export const etapaHumana = (c) => (typeof c === 'string' && NOMBRE_ETAPA[c] ? `${NOMBRE_ETAPA[c]} (${c})` : (c ? String(c) : ''));

const ESTADO_HUMANO = {
  aprobado: 'Aprobado', en_QA: 'En revisión', en_qa: 'En revisión', en_progreso: 'En progreso', pendiente: 'Pendiente', bloqueado: 'Bloqueado', escalado: 'Escalado', obsoleta: 'Obsoleta', obsoleto: 'Obsoleta',
};
const estadoHumano = (e) => ESTADO_HUMANO[e] || String(e || '').replace(/_/g, ' ');

/** Rótulos humanos de cada tipo de evento del registro. */
export const ROTULO_EVENTO = {
  accion: 'Acción', transicion: 'Cambio de etapa', llamada_herramienta: 'Trabajo de IA', decision: 'Decisión', bloqueo: 'Bloqueo', alerta: 'Alerta', aprobacion: 'Aprobación',
};
export const rotuloEvento = (e) => ROTULO_EVENTO[e] || (e ? String(e).replace(/_/g, ' ').replace(/^./, (c) => c.toUpperCase()) : 'Evento');

/** Icono (nombre de lib/iconos.js; si no existe, ui.icono cae a uno neutro) por tipo de evento. */
export const ICONO_EVENTO = { accion: 'engranaje', transicion: 'flecha', llamada_herramienta: 'chispa', decision: 'escudo', bloqueo: 'candado', alerta: 'alerta', aprobacion: 'firma' };

/** Quién actuó, en palabras: «d5-qa» → «IA que revisa (Página de venta y pago)»; «motor» → «El sistema»; «script:activar» → «Tarea automática: activar». */
export function actorHumano(agente) {
  if (typeof agente !== 'string' || !agente) return 'Alguien';
  if (agente === 'motor') return 'El sistema';
  if (agente === 'dueno' || agente === 'dueño') return 'Tú';
  const m = /^([a-z]\d{1,2}|o0|x\d)-(maker|qa)$/i.exec(agente);
  if (m) {
    const cod = m[1].toUpperCase();
    return `${m[2].toLowerCase() === 'qa' ? 'IA que revisa' : 'IA que prepara'} (${nombreEtapa(cod)})`;
  }
  const s = /^script:(.+)$/.exec(agente);
  if (s) return `Tarea automática: ${s[1].replace(/_/g, ' ')}`;
  return agente;
}

const NOTA_GATE = [[/gate H pendiente/i, 'espera tu firma'], [/gate H firmado/i, 'firmado por ti']];
const VEREDICTO_QA = { PASS: 'aprobó', PASS_CON_NOTAS: 'aprobó con notas', FAIL: 'rechazó', BLOCK: 'bloqueó', REVISAR: 'pidió revisar' };
const RE_TRANSICION = /^([A-Z][A-Z0-9]{0,3})\s+([A-Za-z_]+)\s*(?:→|->)\s*([A-Za-z_]+)\s*(?:\((.*)\))?\s*$/;
const RE_APROBACION = /^([A-Z][A-Z0-9]{0,3})\s+aprobado\s+por\s+(\S+)/i;
const RE_VEREDICTO = /^(PASS_CON_NOTAS|PASS|FAIL|BLOCK|REVISAR)\s*:?\s*(.*)$/;

const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);
const ts = (l) => l && l.ts;

/**
 * Describe una línea del registro en lenguaje de negocio.
 * → { tono, icono, categoria, rotulo, titulo, detalle, actor, etapa, etapaCodigo, oferta, simulado, live, fallo }
 * `titulo` es la frase principal; `detalle` una nota breve opcional. Nunca devuelve HTML.
 */
export function describirEvento(l) {
  if (!l || typeof l !== 'object') return { tono: 'neutro', icono: 'lista', categoria: 'otro', rotulo: 'Evento', titulo: 'Evento sin datos', detalle: '', actor: '', etapa: '', etapaCodigo: '', oferta: '', simulado: false, live: false, fallo: false };
  const ev = l.evento;
  const res = l.resultado && l.resultado.estado;
  const resumen = typeof l.entrada_resumen === 'string' ? l.entrada_resumen.trim() : '';
  const actor = actorHumano(l.agente);
  let titulo = resumen || rotuloEvento(ev);
  let detalle = '';
  const tono = tonoDeLinea(l);
  let categoria = 'trabajo';

  if (l._ilegible) {
    return { tono: 'error', icono: 'alerta', categoria: 'atencion', rotulo: 'Línea ilegible', titulo: 'Una línea del historial no se pudo interpretar', detalle: 'Puede ser señal de que el historial fue alterado: comprueba que esté intacto.', actor: '', etapa: '', etapaCodigo: '', oferta: '', simulado: false, live: false, fallo: true };
  }

  if (ev === 'transicion') {
    categoria = 'cambios';
    const m = RE_TRANSICION.exec(resumen);
    if (m) {
      const [, cod, antes, despues, nota] = m;
      titulo = despues === 'aprobado' ? `La etapa «${nombreEtapa(cod)}» quedó aprobada` : `La etapa «${nombreEtapa(cod)}» pasó a «${estadoHumano(despues)}»`;
      const notas = [`antes: ${estadoHumano(antes)}`];
      if (nota) notas.push((NOTA_GATE.find(([re]) => re.test(nota)) || [null, nota])[1]);
      detalle = notas.join(' · ');
    }
  } else if (ev === 'aprobacion') {
    categoria = 'decisiones';
    const m = RE_APROBACION.exec(resumen);
    if (m) titulo = /^due[nñ]o$/i.test(m[2]) ? `Aprobaste la etapa «${nombreEtapa(m[1])}»` : `La etapa «${nombreEtapa(m[1])}» fue aprobada por ${m[2]}`;
    else titulo = `Aprobación: ${resumen || 'sin detalle'}`;
  } else if (ev === 'decision') {
    categoria = 'decisiones';
    const m = RE_VEREDICTO.exec(resumen);
    if (m) titulo = `${actor.startsWith('IA que revisa') ? actor : 'La IA que revisa'} ${VEREDICTO_QA[m[1]] || m[1].toLowerCase()}${m[2] ? `: ${m[2]}` : ''}`;
    else titulo = `Decisión: ${resumen || 'sin detalle'}`;
  } else if (ev === 'bloqueo') {
    categoria = 'atencion';
    titulo = `Se frenó una acción: ${resumen || 'sin detalle'}`;
  } else if (ev === 'alerta') {
    categoria = 'atencion';
    titulo = `Alerta: ${resumen || 'sin detalle'}`;
  } else {
    titulo = cap(resumen) || rotuloEvento(ev);
  }
  if (res === 'error' || res === 'bloqueado') categoria = 'atencion';
  const fallo = res === 'error';
  const actorFinal = ev === 'aprobacion' && RE_APROBACION.test(resumen) && /^due[nñ]o$/i.test(RE_APROBACION.exec(resumen)[2]) ? 'Tú' : actor;
  return {
    tono, icono: ICONO_EVENTO[ev] || 'lista', categoria, rotulo: rotuloEvento(ev), titulo, detalle, actor: actorFinal,
    etapa: l.etapa ? etapaHumana(l.etapa) : '', etapaCodigo: l.etapa || '', oferta: l.oferta_id || '',
    simulado: l.modo === 'dry_run', live: l.modo === 'live', fallo,
  };
}

/** Categorías de la barra de filtros rápidos (cuentan sobre lo cargado). `atencion` = errores, bloqueos y alertas. */
export const CATEGORIAS = [
  { id: 'todo', rotulo: 'Todo' },
  { id: 'atencion', rotulo: 'Requieren revisión' },
  { id: 'cambios', rotulo: 'Cambios de etapa' },
  { id: 'decisiones', rotulo: 'Decisiones y firmas' },
  { id: 'trabajo', rotulo: 'Trabajo de agentes' },
];

export const categoriaDeLinea = (l) => describirEvento(l).categoria;

/** Conteo por categoría de las líneas dadas (para los números de los filtros rápidos). */
export function contarCategorias(lineas) {
  const cuenta = { todo: 0, atencion: 0, cambios: 0, decisiones: 0, trabajo: 0, otro: 0 };
  for (const l of Array.isArray(lineas) ? lineas : []) {
    cuenta.todo += 1;
    const c = categoriaDeLinea(l);
    cuenta[c] = (cuenta[c] || 0) + 1;
  }
  return cuenta;
}

/** Filtra por categoría rápida (`todo` o vacío = sin filtro). */
export function filtrarCategoria(lineas, categoria) {
  const arr = Array.isArray(lineas) ? lineas : [];
  if (!categoria || categoria === 'todo') return arr;
  return arr.filter((l) => categoriaDeLinea(l) === categoria);
}

/**
 * Agrupa líneas por día (más reciente primero) con etiqueta «Hoy», «Ayer» o «viernes, 6 de noviembre». `ahoraMs` y `tz` inyectables.
 * Cada grupo: { clave:'2026-11-06', rotulo, lineas:[…más reciente primero] }. Líneas sin fecha válida van al final en «Sin fecha».
 */
export function agruparPorDia(lineas, { ahoraMs = Date.now(), tz = undefined } = {}) {
  const dia = (ms) => new Intl.DateTimeFormat('en-CA', { timeZone: tz, year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(ms));
  const hoy = dia(ahoraMs);
  const ayer = dia(ahoraMs - 86400000);
  const grupos = new Map();
  const ordenadas = (Array.isArray(lineas) ? lineas : []).slice().sort((a, b) => (b.n || 0) - (a.n || 0) || (Date.parse(ts(b)) || 0) - (Date.parse(ts(a)) || 0)); // el historial es append-only: `n` manda, la hora solo desempata
  for (const l of ordenadas) {
    const ms = Date.parse(ts(l));
    const clave = Number.isFinite(ms) ? dia(ms) : 'sin-fecha';
    if (!grupos.has(clave)) grupos.set(clave, { clave, ms: Number.isFinite(ms) ? ms : null, lineas: [] });
    grupos.get(clave).lineas.push(l);
  }
  const salida = [...grupos.values()].map((g) => {
    let rotulo = 'Sin fecha';
    if (g.ms !== null) {
      rotulo = g.clave === hoy ? 'Hoy' : g.clave === ayer ? 'Ayer' : new Intl.DateTimeFormat('es-ES', { timeZone: tz, weekday: 'long', day: 'numeric', month: 'long', year: g.clave.slice(0, 4) === hoy.slice(0, 4) ? undefined : 'numeric' }).format(new Date(g.ms));
    }
    return { clave: g.clave, rotulo, lineas: g.lineas };
  });
  return salida.sort((a, b) => (a.clave === 'sin-fecha') - (b.clave === 'sin-fecha') || b.clave.localeCompare(a.clave));
}

/** Pares [clave, valor] técnicos de una línea, para `detalleTecnico` (nada se pierde: ids, herramienta, modo, hashes, tokens, costo). */
export function detalleTecnicoLinea(l) {
  if (!l) return [];
  const sal = [];
  const add = (k, v) => { if (v !== null && v !== undefined && v !== '') sal.push([k, v]); };
  add('n', l.n);
  add('evento', l.evento);
  add('herramienta', l.herramienta);
  add('ejecucion_id', l.ejecucion_id);
  add('skill_version', l.skill_version);
  add('modo', l.modo);
  add('resultado', l.resultado && l.resultado.estado ? `${l.resultado.estado}${Number.isInteger(l.resultado.codigo) ? ` (código ${l.resultado.codigo})` : ''}` : null);
  if (l.tokens && typeof l.tokens === 'object') add('tokens', `${l.tokens.entrada ?? '—'} entrada · ${l.tokens.salida ?? '—'} salida`);
  add('hash_previo', l.hash_previo);
  add('hash', l.hash);
  return sal;
}

/** «hace 3 h»; una fecha del futuro (reloj distinto o datos de demostración) no se dice «en 2 d»: se muestra la fecha. */
export function relativoSeguro(iso, ahoraMs = Date.now()) {
  const t = Date.parse(iso || '');
  if (!Number.isFinite(t)) return '—';
  return t - ahoraMs > 60000 ? fmt.fecha(iso) : fmt.relativo(iso, ahoraMs);
}
