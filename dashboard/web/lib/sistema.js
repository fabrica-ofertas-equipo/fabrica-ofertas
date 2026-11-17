// lib/sistema.js — lógica pura de la pantalla Sistema (salud, PAUSA, freno, preflight, consola de acciones). Sin DOM.
// Fuentes: GET /sistema, GET /acciones, POST /accion, GET /job/<id>?desde=N (CONTRATO §4 y §6).

import { estadoInfra, COMANDO_PREFLIGHT } from './resumen.js';

export { COMANDO_PREFLIGHT };

// El panel NUNCA borra la PAUSA ni el freno (CONTRATO §6): solo explica cómo hacerlo una persona.
export const COMANDO_QUITAR_PAUSA = 'rm empresa/PAUSA';
export const COMANDO_QUITAR_FRENO = 'rm empresa/captura/freno.json';
export const COMANDO_LEER_FRENO = 'cat empresa/captura/freno.json';
export const COMANDO_PAUSAR_A_MANO = '.venv/bin/python -m scripts.pausar';

/** Instrucción para levantar la PAUSA a mano (sin botón de borrado). */
export function instruccionPausa(pausa) {
  if (!pausa || !pausa.activa) return null;
  return {
    titulo: 'Cómo levantar la PAUSA (freno de emergencia): lo haces tú, desde la terminal',
    pasos: [
      `Lee el motivo${pausa.motivo ? ` («${pausa.motivo}»)` : ''} y corrige la causa.`,
      'Comprueba que el chequeo de cuentas y servicios vuelve a estar en VERDE y al día.',
      'Borra el archivo de la pausa a mano. El panel nunca lo hace.',
    ],
    comando: COMANDO_QUITAR_PAUSA,
  };
}

/** Instrucción para revisar y levantar el freno de captura a mano (sin botón de borrado). */
export function instruccionFreno(freno) {
  if (!freno || !freno.activo) return null;
  return {
    titulo: 'Cómo levantar el freno de la captura de anuncios: lo haces tú, desde la terminal',
    pasos: [
      `Revisa el motivo${freno.motivo ? ` («${freno.motivo}»)` : ''}. Si Meta pidió un captcha, puso un límite de consultas o exigió iniciar sesión, no se esquiva ni se reintenta.`,
      'Decide si conviene reanudar: solo una persona puede levantar el freno.',
      'Si conviene, borra el archivo del freno a mano. El panel nunca lo hace.',
    ],
    comando: COMANDO_QUITAR_FRENO,
    comandoLeer: COMANDO_LEER_FRENO,
  };
}

/**
 * Elementos de la franja de salud. Cada uno: {id, titulo, tono, texto, detalle, icono, ayuda?, ruta?, tecnico?}.
 * `tecnico` = lo que antes iba a la vista (rutas de archivo): ahora va a «Detalle técnico».
 * `conexion`: 'sse'|'sondeo'|'sin_conexion'. `latenciaMs`: de la última lectura de /sistema. `cadenaOk`: de /registro (true/false/null/undefined).
 */
export function elementosSalud({ sistema, conexion, latenciaMs, cadenaOk, ahoraMs } = {}) {
  const sal = [];
  const rotuloConexion = { sse: 'En vivo', sondeo: 'Revisa cada 5 segundos', sin_conexion: 'Sin conexión' };
  if (!sistema) {
    sal.push({ id: 'datos', titulo: 'Estado del sistema', tono: 'error', texto: 'Sin datos', detalle: 'El panel no pudo leer el estado.', icono: 'alerta', tecnico: 'La consulta del estado del sistema no respondió.' });
  }
  const p = sistema && sistema.pausa;
  if (sistema) sal.push({ id: 'pausa', titulo: 'Pausa general', tono: p && p.activa ? 'error' : 'ok', texto: p && p.activa ? 'ACTIVA' : 'Sin pausa', detalle: p && p.activa ? `Nada gasta ni se activa${p.motivo ? `: ${p.motivo}` : ''}` : 'La fábrica puede trabajar con normalidad.', icono: p && p.activa ? 'pausa' : 'ok', ayuda: 'pausa', ruta: '#/sistema', tecnico: 'empresa/PAUSA' });
  const f = sistema && sistema.freno_captura;
  if (sistema) sal.push({ id: 'freno', titulo: 'Freno de la captura de anuncios', tono: f && f.activo ? 'aviso' : 'ok', texto: f && f.activo ? 'PUESTO' : 'Libre', detalle: f && f.activo ? `${f.motivo ? `Meta respondió «${f.motivo}»` : 'Se detectó un bloqueo'}: la captura no sigue sola.` : 'La captura de anuncios puede correr.', icono: f && f.activo ? 'candado' : 'ok', ayuda: 'freno_captura', ruta: '#/sistema', tecnico: 'empresa/captura/freno.json' });
  if (sistema) {
    const inf = estadoInfra(sistema.infra, ahoraMs);
    const semaforo = sistema.infra ? { VERDE: 'Verde', AMARILLO: 'Amarillo', ROJO: 'Rojo' }[String(sistema.infra.semaforo || '').toUpperCase()] || 'Sin semáforo' : 'Sin medir';
    sal.push({ id: 'infra', titulo: 'Cuentas y servicios', tono: inf.tono, texto: semaforo, detalle: sistema.infra ? (inf.ok ? 'Todo en verde, hecho en modo real y al día: se puede gastar y activar.' : inf.tono === 'error' ? 'Hay puntos en rojo: nadie gasta ni activa hasta resolverlos.' : inf.detalle === 'vigente' ? 'Al día, pero con avisos: revisa los puntos en amarillo.' : `${inf.detalle.charAt(0).toUpperCase()}${inf.detalle.slice(1)}.`) : 'Hasta que se haga el chequeo antes de lanzar, nadie gasta ni activa.', icono: inf.ok ? 'ok' : inf.tono === 'error' ? 'alerta' : 'atencion', ayuda: 'preflight_infra', tecnico: 'empresa/infra/estado.json' });
    if (typeof sistema.motor_disponible === 'boolean') {
      sal.push({ id: 'motor', titulo: 'Sistema automático', tono: sistema.motor_disponible ? 'ok' : 'aviso', texto: sistema.motor_disponible ? 'Disponible' : 'Aún no existe', detalle: sistema.motor_disponible ? 'Los comandos para firmar y ejecutar funcionan.' : 'Se está construyendo: los comandos de firma se podrán ejecutar cuando exista.', icono: sistema.motor_disponible ? 'ok' : 'reloj', ayuda: 'motor', tecnico: 'engine.orq' });
    }
  }
  if (cadenaOk !== undefined) {
    sal.push({ id: 'registro', titulo: 'Historial de actividad', tono: cadenaOk === true ? 'ok' : cadenaOk === false ? 'error' : 'neutro', texto: cadenaOk === true ? 'Sin alteraciones' : cadenaOk === false ? 'ALTERADO' : 'Sin verificar', detalle: cadenaOk === false ? 'No uses el historial para decidir hasta revisarlo.' : cadenaOk === true ? 'Cada evento queda atado al anterior.' : 'Aún no hay historial que verificar.', icono: cadenaOk === true ? 'escudo' : cadenaOk === false ? 'alerta' : 'reloj', ayuda: 'cadena_ok', ruta: '#/registro' });
  }
  sal.push({ id: 'panel', titulo: 'Este panel', tono: conexion === 'sse' ? 'ok' : conexion === 'sondeo' ? 'aviso' : 'error', texto: rotuloConexion[conexion] || 'Sin dato', detalle: Number.isFinite(latenciaMs) ? `Responde en ${Math.round(latenciaMs)} ms (milisegundos).` : 'Aún sin medir la respuesta.', icono: conexion === 'sse' ? 'pulso' : conexion === 'sondeo' ? 'refrescar' : 'alerta', tecnico: conexion === 'sse' ? 'SSE (/api/eventos)' : conexion === 'sondeo' ? 'consulta cada 5 s' : null });
  if (sistema) sal.push({ id: 'entorno', titulo: 'Dónde está corriendo', tono: sistema.entorno === 'produccion' ? 'aviso' : 'info', texto: sistema.entorno === 'produccion' ? 'Producción' : sistema.entorno === 'desarrollo' ? 'Desarrollo' : (sistema.entorno || 'Sin dato'), detalle: sistema.entorno === 'produccion' ? 'Cuidado: aquí las acciones son reales.' : 'Modo de pruebas: no afecta nada real.', icono: 'servidor', tecnico: sistema.modo_demo ? 'con la oferta de ejemplo (ofertas/_ejemplo)' : null });
  return sal;
}

const RANGO_TONO = { error: 3, aviso: 2, neutro: 1, info: 0, ok: 0 };
/** Peor tono de una lista de elementos (para el sello general de la franja). */
export function peorTono(elementos) {
  let peor = 'ok';
  for (const e of Array.isArray(elementos) ? elementos : []) if ((RANGO_TONO[e.tono] ?? 0) > (RANGO_TONO[peor] ?? 0)) peor = e.tono;
  return peor;
}

// ───────────────────────── preflight por ítem ─────────────────────────

export const NOMBRE_BLOQUE = {
  meta: 'Meta (anuncios)', cloudflare: 'Cloudflare (dominios y sitio)', stripe: 'Stripe (cobros)', railway: 'Railway (servidores)', github: 'GitHub (código)',
  seguridad: 'Seguridad', correo: 'Correo', legal: 'Legal', control: 'Control del chequeo',
};
const ORDEN_BLOQUE = ['meta', 'cloudflare', 'stripe', 'railway', 'github', 'seguridad', 'correo', 'legal', 'control'];
const INFO_ESTADO_ITEM = {
  VERDE: { tono: 'ok', etiqueta: 'Verde', icono: 'ok' }, AMARILLO: { tono: 'aviso', etiqueta: 'Amarillo', icono: 'atencion' }, ROJO: { tono: 'error', etiqueta: 'Rojo', icono: 'alerta' },
  PENDIENTE: { tono: 'neutro', etiqueta: 'Pendiente', icono: 'reloj' }, PENDIENTE_EXTERNO: { tono: 'neutro', etiqueta: 'Pendiente de un tercero', icono: 'reloj' },
};
export const infoEstadoItem = (e) => INFO_ESTADO_ITEM[String(e || '').toUpperCase()] || { tono: 'neutro', etiqueta: String(e || 'Sin estado'), icono: 'reloj' };

/**
 * Ítems del preflight agrupados por bloque. `infra` = sistema.infra; usa `infra.items` si el servidor lo trae (campo aditivo, ver PEDIDO).
 * → { hay:bool, total, conteos:{ok,aviso,error,neutro}, criticosRojos, bloques:[{id, nombre, tono, conteos, items:[…]}] }
 */
export function agruparPreflight(infra, ahoraMs = Date.now()) {
  const crudos = infra && Array.isArray(infra.items) ? infra.items.filter((i) => i && typeof i === 'object' && typeof i.id === 'string') : [];
  const conteos = { ok: 0, aviso: 0, error: 0, neutro: 0 };
  const mapa = new Map();
  let criticosRojos = 0;
  for (const i of crudos) {
    const inf = infoEstadoItem(i.estado);
    const exp = Date.parse(i.expira_en || '');
    const item = {
      id: i.id, bloque: typeof i.bloque === 'string' ? i.bloque : 'otros', estado: String(i.estado || ''), tono: inf.tono, etiqueta: inf.etiqueta, icono: inf.icono,
      mensaje: typeof i.mensaje === 'string' ? i.mensaje : '', critico: i.critico === true, latenciaMs: Number.isFinite(i.latencia_ms) ? i.latencia_ms : null,
      medidoEn: i.medido_en || null, expiraEn: i.expira_en || null, vencido: Number.isFinite(exp) && Number.isFinite(ahoraMs) ? exp < ahoraMs : false, evidencia: i.evidencia_ruta || null,
    };
    conteos[inf.tono === 'neutro' || inf.tono === 'info' ? 'neutro' : inf.tono] += 1;
    if (item.critico && inf.tono === 'error') criticosRojos += 1;
    if (!mapa.has(item.bloque)) mapa.set(item.bloque, []);
    mapa.get(item.bloque).push(item);
  }
  const ids = [...mapa.keys()].sort((a, b) => {
    const ia = ORDEN_BLOQUE.indexOf(a); const ib = ORDEN_BLOQUE.indexOf(b);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib) || a.localeCompare(b);
  });
  const bloques = ids.map((id) => {
    const items = mapa.get(id).slice().sort((a, b) => (RANGO_TONO[b.tono] ?? 0) - (RANGO_TONO[a.tono] ?? 0) || String(a.id).localeCompare(String(b.id), 'es', { numeric: true }));
    const c = { ok: 0, aviso: 0, error: 0, neutro: 0 };
    for (const it of items) c[it.tono === 'info' ? 'neutro' : it.tono] += 1;
    return { id, nombre: NOMBRE_BLOQUE[id] || id.charAt(0).toUpperCase() + id.slice(1), tono: peorTono(items), conteos: c, items };
  });
  return { hay: crudos.length > 0, total: crudos.length, conteos, criticosRojos, bloques };
}

// ───────────────────────── consola de acciones ─────────────────────────

// mismos patrones que el servidor (dashboard/api_base.py)
const RE_OFERTA = /^(OF-[0-9]{6}-[0-9]{2}|_[a-z0-9][a-z0-9_-]{0,31})$/;
const RE_CORRIDA = /^[0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9]{1,8}$/;
const TONO_RIESGO = { lectura: 'ok', escribe_local: 'aviso' };

export const tonoRiesgo = (r) => TONO_RIESGO[r] || 'neutro';
export const rotuloRiesgo = (r) => (r === 'lectura' ? 'Solo mira' : r === 'escribe_local' ? 'Guarda archivos aquí' : r || 'Sin clasificar');
/** Icono del riesgo: lectura = ojo (no cambia nada); escritura local = lápiz. */
export const iconoRiesgo = (r) => (r === 'lectura' ? 'ojo' : r === 'escribe_local' ? 'lapiz' : 'info');
/** Frase que explica el riesgo, para el panel de detalle de una acción. */
export const explicacionRiesgo = (r) => (r === 'lectura' ? 'No cambia nada: solo lee y te muestra el resultado.' : r === 'escribe_local' ? 'Escribe archivos en este equipo (nunca en producción ni en Meta o Stripe). Te pide confirmación.' : 'Sin clasificar.');

function normalizarParametro(p, clave) {
  if (!p || typeof p !== 'object') return null;
  const nombre = p.nombre || p.clave || p.id || clave;
  if (typeof nombre !== 'string' || !nombre) return null;
  const opciones = Array.isArray(p.valores) ? p.valores : Array.isArray(p.opciones) ? p.opciones : Array.isArray(p.enum) ? p.enum : null;
  let tipo = p.tipo || p.type || (opciones ? 'eleccion' : 'texto');
  if (opciones && tipo !== 'eleccion' && tipo !== 'enum') tipo = 'eleccion';
  if (tipo === 'enum') tipo = 'eleccion';
  if (tipo === 'oferta_id') tipo = 'oferta';
  if (tipo === 'bool' || tipo === 'booleano') tipo = 'bandera';
  if (tipo === 'int' || tipo === 'integer') tipo = 'entero';
  return {
    nombre, tipo, requerido: p.requerido === true && p.opcional !== true, opciones: opciones ? opciones.map(String) : null,
    descripcion: p.descripcion || p.ayuda || '', porDefecto: p.por_defecto ?? p.defecto ?? p.default ?? null,
    minimo: Number.isInteger(p.minimo) ? p.minimo : null, maximo: Number.isInteger(p.maximo) ? p.maximo : null, flag: typeof p.flag === 'string' ? p.flag : null,
  };
}

/**
 * La lista blanca del servidor (dashboard/acciones.yaml) escribe cada acción como un comando («Validar esquemas de contratos»). Aquí se dicen como tareas.
 * Solo se reescriben las que se conocen por su `id`; cualquier acción nueva conserva el texto del servidor hasta que se agregue aquí.
 */
export const TAREAS_HUMANAS = {
  barrido_estado: { titulo: 'Ver cómo va una búsqueda de ofertas', descripcion: 'Muestra el panorama de una búsqueda: qué consultas se hicieron y cuáles fallaron, qué candidatos salieron y cuánto queda del cupo. Solo mira.' },
  barrido_plan_ver: { titulo: 'Ver el plan de una búsqueda', descripcion: 'Resume qué se va a buscar en la búsqueda elegida (y, si quieres, cada consulta). Solo mira.' },
  barrido_rankear: { titulo: 'Ensayar el ranking de temas', descripcion: 'Calcula qué temas y países convienen más, sin guardar nada. Es solo un ensayo.' },
  barrido_fichas: { titulo: 'Ensayar las fichas de ofertas', descripcion: 'Arma y revisa el borrador de las fichas de ofertas, sin guardar nada. Es solo un ensayo.' },
  validar_esquemas: { titulo: 'Revisar que los formatos estén bien', descripcion: 'Comprueba que todos los formatos de datos del sistema se cargan sin errores.' },
  validar_ejemplos: { titulo: 'Revisar los ejemplos de datos', descripcion: 'Comprueba que los ejemplos buenos pasan y que los malos son rechazados, como debe ser.' },
  validar_oferta: { titulo: 'Revisar una oferta completa', descripcion: 'Comprueba que los archivos de una oferta tienen el formato esperado y son coherentes entre sí. Solo mira.' },
  pruebas_paquete: { titulo: 'Comprobar que una parte del sistema funciona', descripcion: 'Hace las comprobaciones automáticas de la parte que elijas. No usa internet ni claves y no toca tus ofertas reales.' },
  landing_validar: { titulo: 'Revisar la página de venta antes de publicarla', descripcion: 'Revisa precio, moneda, garantía, enlaces, textos legales y consentimiento, y que no pida datos de salud. Solo mira.' },
  landing_generar: { titulo: 'Probar la creación de la página de venta', descripcion: 'Arma la página de venta como ensayo, sin publicar nada.' },
};

/** Acepta `parametros|params|args` como lista o mapa. Ordena: lectura primero, luego por título. */
export function normalizarAcciones(datos) {
  const lista = Array.isArray(datos) ? datos : (datos && Array.isArray(datos.acciones) ? datos.acciones : []);
  const salida = [];
  for (const a of lista) {
    if (!a || typeof a !== 'object' || typeof a.id !== 'string') continue;
    const crudo = a.parametros ?? a.params ?? a.args ?? [];
    const pars = Array.isArray(crudo) ? crudo.map((p) => normalizarParametro(p)) : Object.entries(crudo || {}).map(([k, p]) => normalizarParametro(typeof p === 'object' ? p : { tipo: p }, k));
    const h = TAREAS_HUMANAS[a.id];
    salida.push({
      id: a.id, titulo: h ? h.titulo : (a.titulo || a.id), descripcion: h ? h.descripcion : (a.descripcion || ''), tituloOriginal: a.titulo || a.id, riesgo: a.riesgo || null, parametros: pars.filter(Boolean),
      comando: typeof a.comando === 'string' ? a.comando : null, proximamente: a.proximamente === true || a.disponible === false, motivo: typeof a.motivo === 'string' ? a.motivo : null,
      timeoutS: Number.isInteger(a.timeout_s) ? a.timeout_s : null, enCurso: typeof a.en_curso === 'string' && a.en_curso ? a.en_curso : null,
    });
  }
  // orden: disponibles antes que «próximamente»; lectura antes que escritura; luego por el orden en que las declara la lista blanca
  return salida
    .map((a, i) => ({ a, i }))
    .sort((x, y) => Number(x.a.proximamente) - Number(y.a.proximamente) || (x.a.riesgo === 'lectura' ? 0 : 1) - (y.a.riesgo === 'lectura' ? 0 : 1) || x.i - y.i)
    .map((x) => x.a);
}

/** Valida los valores del formulario contra los parámetros. Devuelve {ok, errores:{nombre:mensaje}, args:{nombre:valor}}. */
export function validarArgs(parametros, valores) {
  const errores = {};
  const args = {};
  for (const p of parametros || []) {
    const crudo = valores ? valores[p.nombre] : undefined;
    const v = typeof crudo === 'string' ? crudo.trim() : crudo;
    if (p.tipo === 'bandera') { args[p.nombre] = v === true || v === 'true'; continue; }
    if (v === undefined || v === null || v === '') {
      if (p.requerido) errores[p.nombre] = 'Obligatorio.';
      continue;
    }
    if (p.tipo === 'eleccion') {
      if (!p.opciones || !p.opciones.includes(String(v))) { errores[p.nombre] = 'Elige una de las opciones.'; continue; }
      args[p.nombre] = String(v);
    } else if (p.tipo === 'oferta') {
      if (!RE_OFERTA.test(String(v))) { errores[p.nombre] = 'Escribe el código de la oferta, por ejemplo OF-202611-01 (o _ejemplo).'; continue; }
      args[p.nombre] = String(v);
    } else if (p.tipo === 'corrida') {
      if (!RE_CORRIDA.test(String(v))) { errores[p.nombre] = 'Escribe la fecha y una letra, por ejemplo 2026-11-06-a.'; continue; }
      args[p.nombre] = String(v);
    } else if (p.tipo === 'entero') {
      const n = Number(v);
      if (!/^-?\d{1,9}$/.test(String(v))) { errores[p.nombre] = 'Debe ser un número entero.'; continue; }
      if ((p.minimo !== null && n < p.minimo) || (p.maximo !== null && n > p.maximo)) { errores[p.nombre] = `Entre ${p.minimo ?? '-∞'} y ${p.maximo ?? '∞'}.`; continue; }
      args[p.nombre] = n;
    } else if (p.tipo === 'bandera') {
      args[p.nombre] = v === true || v === 'true';
    } else {
      if (String(v).length > 200) { errores[p.nombre] = 'Demasiado largo (máx. 200).'; continue; }
      args[p.nombre] = String(v);
    }
  }
  return { ok: Object.keys(errores).length === 0, errores, args };
}

// eslint-disable-next-line no-control-regex
const RE_ANSI = /\u001B\[[0-9;?]*[ -/]*[@-~]|\u001B\][^\u0007\u001B]*(?:\u0007|\u001B\\)|\u001B[@-Z\\-_]/g;

/** Quita secuencias ANSI y retornos de carro de la salida de un proceso (se muestra como texto plano). */
export function limpiarSalida(texto) {
  return String(texto ?? '').replace(RE_ANSI, '').replace(/\r\n?/g, '\n');
}

/** Normaliza la respuesta de GET /job/<id>?desde=N a {estado, terminado, codigo, texto, siguiente}. Tolera variantes de nombres. */
export function normalizarJob(d, desdePrevio = 0) {
  if (!d || typeof d !== 'object') return { estado: 'desconocido', terminado: false, codigo: null, texto: '', siguiente: desdePrevio };
  let texto = '';
  if (typeof d.salida === 'string') texto = d.salida;
  else if (typeof d.texto === 'string') texto = d.texto;
  else if (Array.isArray(d.lineas)) texto = d.lineas.map((x) => (typeof x === 'string' ? x : (x && x.texto) || '')).join('\n') + (d.lineas.length ? '\n' : '');
  else if (typeof d.stdout === 'string') texto = d.stdout;
  const estadoCrudo = typeof d.estado === 'string' ? d.estado : '';
  const codigo = [d.codigo, d.codigo_salida, d.returncode, d.salio_con].find((x) => Number.isInteger(x)) ?? null;
  const terminado = d.terminado === true || d.finalizado === true || ['terminado', 'finalizado', 'ok', 'error', 'fallo', 'timeout', 'cancelado', 'completado'].includes(estadoCrudo) || (codigo !== null && estadoCrudo !== 'corriendo');
  const sig = [d.siguiente, d.hasta, d.offset, d.next].find((x) => Number.isInteger(x));
  return {
    estado: terminado ? (codigo === null || codigo === 0 ? 'terminado' : 'error') : 'corriendo', estadoServidor: estadoCrudo || null, terminado, codigo,
    texto: limpiarSalida(texto), siguiente: sig !== undefined ? sig : desdePrevio + texto.length, truncado: d.truncado === true, comando: typeof d.comando === 'string' ? d.comando : null,
  };
}

/** Resumen de una ejecución: {tono, texto, icono, clave}. `clave`: corriendo|ok|error|aviso|neutro (para estilos y para estadoIcono). */
export function veredictoJob(job) {
  if (!job.terminado) return { tono: 'info', texto: 'Corriendo…', icono: 'progreso', clave: 'corriendo' };
  if (job.estadoServidor === 'timeout') return { tono: 'error', texto: 'Se agotó el tiempo y la tarea se detuvo', icono: 'alerta', clave: 'error' };
  if (job.estadoServidor === 'tope_salida') return { tono: 'aviso', texto: 'Resultado cortado: superó el tamaño máximo (256 KB)', icono: 'atencion', clave: 'aviso' };
  if (job.codigo === 0) return { tono: 'ok', texto: 'Terminó bien', icono: 'ok', clave: 'ok' };
  if (job.codigo === null) return { tono: 'neutro', texto: 'Terminó', icono: 'ok', clave: 'neutro' };
  return { tono: 'error', texto: `Terminó con error (código ${job.codigo})`, icono: 'alerta', clave: 'error' };
}

// ───────────────────────── agrupar y rotular acciones ─────────────────────────

const GRUPOS_ACCION = [
  { id: 'barrido', prefijo: 'barrido_', titulo: 'Buscar ofertas en el mercado', descripcion: 'Mira cómo va la búsqueda de ofertas, o la ensaya, sin guardar nada.' },
  { id: 'validar', prefijo: 'validar_', titulo: 'Revisar que los formatos estén bien', descripcion: 'Comprueba que los archivos tienen el formato esperado.' },
  { id: 'pruebas', prefijo: 'pruebas_', titulo: 'Comprobar que el sistema funciona', descripcion: 'Hace las comprobaciones automáticas de una parte del sistema.' },
  { id: 'landing', prefijo: 'landing_', titulo: 'Página de venta', descripcion: 'Revisa la página de venta o la ensaya sin publicar nada.' },
];

/** Agrupa las acciones normalizadas por tema, conservando el orden. Lo que no encaja va a «Otras». Cada una gana `tituloCorto`. */
export function agruparAcciones(acciones) {
  const salida = new Map();
  for (const a of Array.isArray(acciones) ? acciones : []) {
    const g = GRUPOS_ACCION.find((x) => a.id.startsWith(x.prefijo)) || { id: 'otras', titulo: 'Otras tareas', descripcion: '' };
    if (!salida.has(g.id)) salida.set(g.id, { id: g.id, titulo: g.titulo, descripcion: g.descripcion, acciones: [] });
    const corto = a.titulo;
    salida.get(g.id).acciones.push({ ...a, tituloCorto: corto ? corto.charAt(0).toUpperCase() + corto.slice(1) : a.titulo });
  }
  return [...salida.values()];
}

const ETIQUETA_PARAMETRO = { corrida: 'Búsqueda (fecha y letra)', oferta: 'Oferta', paquete: 'Parte del sistema a comprobar', consultas: 'Mostrar cada consulta' };
/** Etiqueta humana de un parámetro del formulario (el nombre técnico queda en la ayuda). */
export function etiquetaParametro(p) {
  if (!p) return '';
  const base = ETIQUETA_PARAMETRO[p.nombre] || (p.nombre ? p.nombre.charAt(0).toUpperCase() + p.nombre.slice(1).replace(/[_-]+/g, ' ') : '');
  return `${base}${p.requerido ? ' *' : ''}`;
}
