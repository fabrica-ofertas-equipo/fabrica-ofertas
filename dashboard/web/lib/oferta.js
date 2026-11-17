// Lógica pura de la pantalla «Oferta» (#/oferta/<id>) y base compartida de las
// pantallas de P3 (ofertas, pulido, skills). Sin DOM, sin red: datos -> modelo de vista.
// Se prueba con `node --test` (tests/dashboard/test_web_oferta.mjs).

/** Orden del flujo. M1 depende de D1 (estado.json: M1.entradas = {D1}; docs/06 §2), por eso D1 va primero. */
export const ORDEN_ETAPAS = ['D1', 'M1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10'];

/** Etapas con carpeta propia que el motor controla por oferta y que el panel dibuja siempre. */
export const ETAPAS_OPCIONALES = ['D9'];

export const ESTADOS_ETAPA = ['pendiente', 'en_progreso', 'en_QA', 'aprobado', 'bloqueado', 'escalado'];
export const SEVERIDADES_QA = ['BLOQUEANTE', 'MAYOR', 'MENOR', 'MEJORA'];
export const GATES = {
  A: { titulo: 'Automático', ayuda: 'Pasa sola si la revisión de calidad la aprueba.' },
  S: { titulo: 'Semiautomático', ayuda: 'Te la pide solo por excepción (la revisión trae notas, la rechaza o cae en una muestra al azar).' },
  H: { titulo: 'Humano', ayuda: 'Requiere tu firma.' },
};

const CMD = '.venv/bin/python -m engine.orq';

/**
 * Qué es cada etapa, de dónde sale y a dónde va. Fuente: docs/06 §2 (dependencias de aprobación),
 * ofertas/_ejemplo/README.md (carpetas) y departamentos/*.md. `forja`: «criterio» = skill de forja manual
 * (docs/03 §0.1); «ingenieria» = código con tests y skill como manual corto.
 */
export const ETAPAS = {
  D1: {
    nombre: 'Descubrimiento', resumen: 'Elegir qué problema atacar, con evidencia citada.',
    carpeta: '01-descubrimiento', dependeDe: [], forja: 'criterio', departamento: 'departamentos/02-descubrimiento.md',
    salidas: ['01-descubrimiento/candidatos.json', '01-descubrimiento/informe.md'],
  },
  M1: {
    nombre: 'Mercado', resumen: 'Idioma, países, moneda, métodos de pago e impuestos: el mercado elegido es una hipótesis.',
    carpeta: null, dependeDe: ['D1'], forja: 'criterio', departamento: 'departamentos/16-mercados-localizacion.md',
    salidas: ['mercado.json'],
  },
  D2: {
    nombre: 'Validación', resumen: '¿Hay demanda y lo gratis no alcanza? Comprobar el candidato con evidencia.',
    carpeta: '02-validacion', dependeDe: ['D1', 'M1'], forja: 'criterio', departamento: 'departamentos/03-validacion.md',
    salidas: ['02-validacion/validacion.json'],
  },
  D3: {
    nombre: 'Oferta', resumen: 'Qué se vende: promesa, precio, mensajes de venta y cuánto gana cada venta.',
    carpeta: '03-oferta', dependeDe: ['D2'], forja: 'criterio', departamento: 'departamentos/04-oferta.md',
    salidas: ['03-oferta/oferta.json', '03-oferta/economia.json', '03-oferta/oferta.md'],
  },
  D4: {
    nombre: 'Producto', resumen: 'El producto terminado, su muestra y de dónde salió cada dato.',
    carpeta: '04-producto', dependeDe: ['D3'], forja: 'criterio', departamento: 'departamentos/05-producto.md',
    salidas: ['04-producto/producto.json', '04-producto/entregables/', '04-producto/trazabilidad.md'],
  },
  D5: {
    nombre: 'Página de venta y pago', resumen: 'La página de venta, las páginas legales, la pantalla de pago y la medición (publicar es otra firma tuya).',
    carpeta: '05-landing', dependeDe: ['D3', 'D4'], forja: 'criterio', departamento: 'departamentos/06-landing-checkout.md',
    salidas: ['05-landing/sitio/', '05-landing/rutas.json', '05-landing/checkout.json', '05-landing/tracking.json', '05-landing/assets.json'],
  },
  D6: {
    nombre: 'Anuncios', resumen: 'Los anuncios: textos, imágenes y el aviso de que se usó IA.',
    carpeta: '06-creativos', dependeDe: ['D3', 'D5'], forja: 'criterio', departamento: 'departamentos/07-creativos.md',
    salidas: ['06-creativos/paquete.json', '06-creativos/assets/'],
  },
  D7: {
    nombre: 'Campaña', resumen: 'Dejar lista la campaña de Meta como borrador. Activarla exige tu firma y el visto bueno de cumplimiento.',
    carpeta: '07-campana', dependeDe: ['D5', 'D6'], forja: 'criterio', departamento: 'departamentos/08-campanas-meta.md',
    salidas: ['07-campana/campana.json'],
  },
  D8: {
    nombre: 'Operación', resumen: 'Mirar las cifras cada día y aplicar reglas fijas: cortar, seguir o escalar. Termina con un veredicto.',
    carpeta: '08-operacion', dependeDe: ['D7'], forja: 'ingenieria', departamento: 'departamentos/09-optimizacion.md',
    salidas: ['08-operacion/diario/', '08-operacion/ordenes_presupuesto.jsonl', '08-operacion/veredicto_oferta.json'],
  },
  D9: {
    nombre: 'Escalado', resumen: 'Copiar y agrandar las ofertas ganadoras. Queda fuera de la primera prueba: Operación solo anota la propuesta.',
    carpeta: null, dependeDe: ['D8'], forja: 'ingenieria', departamento: 'departamentos/10-escalado.md',
    salidas: [], opcional: true,
  },
  D10: {
    nombre: 'Después de la venta', resumen: 'Entrega del producto, reembolsos según reglas y aviso de pausa si algo falla.',
    carpeta: '10-postcompra', dependeDe: ['D4', 'D5'], forja: 'ingenieria', departamento: 'departamentos/11-postcompra.md',
    salidas: ['10-postcompra/entregas.jsonl', '10-postcompra/reembolsos.jsonl', '10-postcompra/senal_pausa.json'],
  },
};

const TONO_ESTADO = {
  aprobado: 'ok', en_QA: 'info', en_progreso: 'info', pendiente: 'neutro', bloqueado: 'error', escalado: 'error',
};
const ROTULO_ESTADO = {
  aprobado: 'aprobada', en_QA: 'en revisión de calidad', en_progreso: 'en progreso', pendiente: 'pendiente', bloqueado: 'bloqueada', escalado: 'escalada',
};

export function tonoEstado(estado) { return TONO_ESTADO[estado] || 'neutro'; }
export function rotuloEstado(estado) { return ROTULO_ESTADO[estado] || String(estado ?? 'sin dato'); }

export function nombreEtapa(id) { return ETAPAS[id] ? ETAPAS[id].nombre : String(id ?? ''); }

/** Posición en el orden del flujo; las etapas desconocidas van al final, ordenadas por texto. */
export function posicionEtapa(id) {
  const i = ORDEN_ETAPAS.indexOf(id);
  return i < 0 ? ORDEN_ETAPAS.length : i;
}
export function compararEtapas(a, b) {
  const d = posicionEtapa(a) - posicionEtapa(b);
  return d !== 0 ? d : String(a).localeCompare(String(b));
}

// ---------------------------------------------------------------------------------------------
// Entrada de shell: citar argumentos para comandos copiables (los ids vienen de datos).

const SEGURO = /^[A-Za-z0-9_./:=@%+,-]+$/;
export function citar(arg) {
  const s = String(arg ?? '');
  if (s !== '' && SEGURO.test(s)) return s;
  return "'" + s.replace(/'/g, "'\\''") + "'";
}

// ---------------------------------------------------------------------------------------------
// Normalización de la respuesta de GET /oferta/<id>

function esObjeto(x) { return x !== null && typeof x === 'object' && !Array.isArray(x); }

/** Minúsculas sin tildes, para filtrar texto («economia» encuentra «economía»). */
export function plano(t) {
  return String(t ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
}
function texto(x) { return typeof x === 'string' ? x : (x == null ? '' : String(x)); }

/** Quita el código técnico del principio de un bloqueo («falta_insumo: Falta la plantilla» → «Falta la plantilla»). El código queda en el detalle técnico. */
export function bloqueoHumano(t) {
  const s = texto(t).trim();
  const m = /^[a-z][a-z0-9_]{2,40}:\s+(.+)$/s.exec(s);
  return m ? m[1] : s;
}

/** Convierte el bloqueo (texto, objeto o null) en una frase corta, o null si no hay. */
export function textoBloqueo(b) {
  if (b == null || b === false) return null;
  if (typeof b === 'string') return b.trim() === '' ? null : b;
  if (esObjeto(b)) {
    const m = b.motivo ?? b.mensaje ?? b.causa ?? b.razon ?? b.descripcion;
    const que = b.tipo ?? b.codigo;
    if (m != null && que != null) return `${que}: ${m}`;
    if (m != null) return texto(m);
    if (que != null) return texto(que);
    return JSON.stringify(b);
  }
  return texto(b);
}

/**
 * Una etapa de la API -> nodo de vista. `raw` puede ser undefined (la API no devolvió la etapa:
 * se dibuja como «sin datos», nunca como cero).
 */
export function vistaEtapa(id, raw) {
  const meta = ETAPAS[id] || { nombre: id, resumen: '', carpeta: null, dependeDe: [], salidas: [], forja: null };
  // La API devuelve siempre las 11 etapas; sin estado.json o sin esa etapa vienen con estado null: eso es «sin datos», no «pendiente».
  const sinEstado = !raw || raw.estado == null;
  const base = {
    id,
    nombre: meta.nombre || (raw && raw.nombre) || id, // nombres cortos del panel; el del servidor queda como respaldo
    opcional: !!meta.opcional,
    sinDatos: sinEstado,
    estado: 'pendiente',
    tono: 'neutro',
    rotulo: 'sin datos',
    version: null,
    gate: null,
    gatePendiente: false,
    rondaQa: null,
    intentos: null,
    hash: null,
    aprobadoPor: null,
    bloqueo: null,
    obsoleta: false,
    artefactos: [],
    qa: [],
  };
  if (!raw) return base;
  const estado = ESTADOS_ETAPA.includes(raw.estado) ? raw.estado : 'pendiente';
  const obsoleta = raw.obsoleta === true;
  const ap = esObjeto(raw.aprobado_por) ? raw.aprobado_por : null;
  return {
    ...base,
    sinDatos: sinEstado,
    estado,
    tono: sinEstado ? 'neutro' : (obsoleta ? 'aviso' : tonoEstado(estado)),
    rotulo: sinEstado ? 'sin datos' : (obsoleta ? 'obsoleta' : rotuloEstado(estado)),
    version: raw.version ?? raw.version_aprobada ?? null,
    gate: ['A', 'S', 'H'].includes(raw.gate) ? raw.gate : null,
    gatePendiente: !sinEstado && raw.gate_pendiente === true,
    rondaQa: Number.isInteger(raw.ronda_qa) ? raw.ronda_qa : null,
    intentos: Number.isInteger(raw.intentos) ? raw.intentos : null,
    hash: raw.hash ?? raw.hash_salida ?? null,
    aprobadoPor: ap ? { tipo: ap.tipo ?? null, id: ap.id ?? null, fecha: ap.fecha ?? null } : null,
    bloqueo: textoBloqueo(raw.bloqueo),
    obsoleta,
    artefactos: Array.isArray(raw.artefactos) ? raw.artefactos.filter(esObjeto) : [],
    qa: Array.isArray(raw.qa) ? raw.qa.filter(esObjeto) : [],
  };
}

/**
 * Pipeline ordenado. Siempre devuelve las 11 etapas del flujo (las que la API no trae, como «sin datos»)
 * más cualquier etapa extra desconocida al final.
 */
export function construirPipeline(etapasApi) {
  const lista = Array.isArray(etapasApi) ? etapasApi : [];
  const porId = new Map();
  for (const e of lista) if (esObjeto(e) && typeof e.id === 'string') porId.set(e.id, e);
  const ids = [...ORDEN_ETAPAS];
  for (const id of porId.keys()) if (!ids.includes(id)) ids.push(id);
  return ids.map((id) => vistaEtapa(id, porId.get(id)));
}

/** Pipeline a partir del mapa `etapas: {M1: "aprobado", …}` que trae GET /ofertas (sin detalle). */
export function pipelineDesdeMapa(mapa) {
  const m = esObjeto(mapa) ? mapa : {};
  const ids = [...ORDEN_ETAPAS];
  for (const id of Object.keys(m)) if (!ids.includes(id)) ids.push(id);
  return ids.map((id) => {
    const v = m[id];
    const estado = typeof v === 'string' ? v : (esObjeto(v) ? v.estado : null);
    const sin = !ESTADOS_ETAPA.includes(estado);
    return {
      id, nombre: nombreEtapa(id), opcional: !!(ETAPAS[id] && ETAPAS[id].opcional),
      sinDatos: sin, estado: sin ? 'pendiente' : estado, tono: sin ? 'neutro' : tonoEstado(estado),
      rotulo: sin ? 'sin datos' : rotuloEstado(estado),
    };
  });
}

/** Resumen del pipeline para cabecera y para la barra compacta de la lista. */
export function resumenPipeline(vistas, gatesPendientes = null) {
  const contables = vistas.filter((v) => !(v.opcional && (v.sinDatos || v.estado === 'pendiente')));
  const cuenta = { aprobado: 0, en_progreso: 0, en_QA: 0, pendiente: 0, bloqueado: 0, escalado: 0 };
  let obsoletas = 0;
  for (const v of contables) {
    if (v.sinDatos) { cuenta.pendiente += 1; continue; }
    cuenta[v.estado] += 1;
    if (v.obsoleta) obsoletas += 1;
  }
  const total = contables.length;
  const actual = contables.find((v) => v.estado !== 'aprobado' || v.obsoleta) || null;
  const gates = gatesPendientes
    ? [...gatesPendientes].sort(compararEtapas)
    : vistas.filter((v) => v.gatePendiente).map((v) => v.id);
  return {
    total,
    aprobadas: cuenta.aprobado,
    enCurso: cuenta.en_progreso + cuenta.en_QA,
    bloqueadas: cuenta.bloqueado + cuenta.escalado,
    pendientes: cuenta.pendiente,
    obsoletas,
    gatesPendientes: gates,
    etapaActual: actual ? actual.id : null,
    completa: total > 0 && cuenta.aprobado === total && obsoletas === 0,
    bp: total === 0 ? 0 : Math.round((cuenta.aprobado * 10000) / total),
    sinDatos: vistas.every((v) => v.sinDatos),
  };
}

// ---------------------------------------------------------------------------------------------
// Comandos copiables. El panel NUNCA firma ni ejecuta: solo muestra qué correr en la terminal.

export function comandoFirmar(ofertaId, etapa) {
  return `${CMD} firmar --oferta ${citar(ofertaId)} --etapa ${citar(etapa)} --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno`;
}

/** Lista de comandos para trabajar una etapa a mano. `vista` es el nodo de vista de la etapa (opcional). */
export function comandosEtapa(ofertaId, etapa, vista = null) {
  const o = citar(ofertaId);
  const e = citar(etapa);
  const meta = ETAPAS[etapa] || {};
  const lista = [];
  lista.push({
    id: 'estado', titulo: 'Ver el estado y la firma pendiente', comando: `${CMD} estado --oferta ${o}`,
    riesgo: 'lectura', nota: 'Solo muestra información; no cambia nada.',
  });
  lista.push({
    id: 'siguiente', titulo: 'Ver qué etapa toca ahora', comando: `${CMD} siguiente --oferta ${o}`,
    riesgo: 'lectura', nota: 'Solo muestra información; no cambia nada.',
  });
  if (meta.opcional) return lista;
  lista.push({
    id: 'ensayo', titulo: `Hacer un simulacro de ${etapa}`, comando: `${CMD} ejecutar --oferta ${o} --etapa ${e} --modo dry-run`,
    riesgo: 'lectura', nota: 'Simulacro: no gasta, no publica y no activa nada.',
  });
  lista.push({
    id: 'ingresar', titulo: `Ingresar lo hecho a mano en ${etapa}`,
    comando: `${CMD} ingresar --oferta ${o} --etapa ${e} --desde <CARPETA_CON_LO_HECHO> --origen humano`,
    riesgo: 'escribe', nota: 'Se revisa igual que el trabajo de la IA y deja la etapa esperando tu firma. Cambia <CARPETA_CON_LO_HECHO> por la carpeta con tu trabajo.',
  });
  if (meta.forja === 'criterio') {
    lista.push({
      id: 'real', titulo: `Ejecutar ${etapa} con IA (una IA la prepara y otra la revisa)`, comando: `${CMD} ejecutar --oferta ${o} --etapa ${e} --modo live`,
      riesgo: 'consume', nota: 'Gasta crédito de IA y exige límites firmados, cuentas y servicios en verde y que no haya PAUSA (el freno de emergencia).',
    });
  }
  if (vista && vista.gatePendiente) {
    lista.unshift({
      id: 'firmar', titulo: `Firmar la etapa ${etapa}`, comando: comandoFirmar(ofertaId, etapa),
      riesgo: 'firma', nota: 'Se pega en tu terminal y usa tu clave de firma. El panel no firma por ti.',
    });
  }
  return lista;
}

/** Texto y tono de «próximo paso». Usa lo que dice la API si lo trae; si no, lo deduce del pipeline. */
export function proximoPaso(ofertaId, vistas, resumen, apiProximo = null) {
  const deApi = normalizarProximoApi(apiProximo);
  const calc = proximoPasoLocal(ofertaId, vistas, resumen);
  if (!deApi) return { ...calc, motorDisponible: null, origen: 'calculado' };
  // Si el servidor ya decidió (su etapa manda, incluso null = «ninguna»), el cálculo local solo aporta el tono y, si coincide la etapa, el comando.
  const mismaEtapa = deApi.etapa == null || deApi.etapa === calc.etapa;
  return {
    ...calc, ...deApi,
    comando: deApi.comando || (mismaEtapa ? calc.comando : null),
    tono: TONO_TIPO_PROXIMO[deApi.tipo] || calc.tono,
    origen: 'servidor',
  };
}

const TONO_TIPO_PROXIMO = {
  firmar_gate: 'aviso', bloqueado: 'error', escalado: 'error', pausada: 'error', en_curso: 'info', siguiente: 'neutro', completa: 'ok', sin_estado: 'aviso',
};

function normalizarProximoApi(p) {
  if (p == null) return null;
  if (typeof p === 'string') return p.trim() === '' ? null : { titulo: p, detalle: null };
  if (esObjeto(p)) {
    const titulo = p.titulo ?? p.texto ?? p.mensaje ?? p.accion ?? p.descripcion ?? null;
    if (titulo == null && p.etapa == null) return null;
    return {
      titulo: titulo != null ? texto(titulo) : `Etapa ${texto(p.etapa)}`,
      detalle: p.detalle != null ? texto(p.detalle) : null,
      etapa: typeof p.etapa === 'string' ? p.etapa : null,
      tipo: typeof p.tipo === 'string' ? p.tipo : null,
      comando: typeof p.comando === 'string' && p.comando.trim() !== '' ? p.comando.replace(/^python3? -m /, '.venv/bin/python -m ') : null,
      motorDisponible: typeof p.motor_disponible === 'boolean' ? p.motor_disponible : null,
    };
  }
  return null;
}

export function proximoPasoLocal(ofertaId, vistas, resumen) {
  if (!vistas.length || resumen.sinDatos) {
    return {
      etapa: null, tono: 'aviso', titulo: 'Esta oferta aún no tiene estado por etapa',
      detalle: 'El sistema todavía no registró las etapas de esta oferta. Se crean al dar de alta la oferta desde su ficha inicial (brief) firmada.',
      comando: `${CMD} crear --brief ofertas/${citar(ofertaId)}/00-brief.yaml`,
    };
  }
  if (resumen.completa) {
    return { etapa: null, tono: 'ok', titulo: 'Todas las etapas están aprobadas', detalle: 'Revisa los resultados del día a día y lo que pasa después de la venta.', comando: null };
  }
  const v = vistas.find((x) => x.id === resumen.etapaActual);
  if (!v) return { etapa: null, tono: 'neutro', titulo: 'Sin próximo paso', detalle: null, comando: null };
  const nombre = `${v.id} ${v.nombre}`;
  if (v.obsoleta) {
    return { etapa: v.id, tono: 'aviso', titulo: `Rehacer ${nombre}`, detalle: 'Una entrada cambió: la versión aprobada quedó obsoleta (se conserva la anterior).', comando: `${CMD} ejecutar --oferta ${citar(ofertaId)} --etapa ${citar(v.id)} --modo dry-run` };
  }
  switch (v.estado) {
    case 'en_QA':
      if (v.gatePendiente) {
        return { etapa: v.id, tono: 'aviso', titulo: `Firmar ${nombre}`, detalle: 'La revisión de calidad terminó y falta tu firma. Mira los archivos y los hallazgos antes.', comando: comandoFirmar(ofertaId, v.id) };
      }
      return { etapa: v.id, tono: 'info', titulo: `Revisión de calidad de ${nombre} en curso`, detalle: v.rondaQa != null ? `Ronda de revisión ${v.rondaQa}.` : null, comando: `${CMD} estado --oferta ${citar(ofertaId)}` };
    case 'en_progreso':
      return { etapa: v.id, tono: 'info', titulo: `${nombre} en progreso`, detalle: 'Si la haces a mano, ingrésala cuando termines.', comando: `${CMD} estado --oferta ${citar(ofertaId)}` };
    case 'bloqueado':
      return { etapa: v.id, tono: 'error', titulo: `Resolver el bloqueo de ${nombre}`, detalle: v.bloqueo || 'Falta un dato, un acceso o un servicio externo.', comando: `${CMD} estado --oferta ${citar(ofertaId)}` };
    case 'escalado':
      return { etapa: v.id, tono: 'error', titulo: `${nombre} escalada a una persona`, detalle: 'Dos rondas con hallazgos graves, o un veto de cumplimiento. Solo sale por orden de una persona.', comando: `${CMD} estado --oferta ${citar(ofertaId)}` };
    default:
      return { etapa: v.id, tono: 'neutro', titulo: `Ejecutar ${nombre}`, detalle: dependenciasTexto(v.id), comando: `${CMD} ejecutar --oferta ${citar(ofertaId)} --etapa ${citar(v.id)} --modo dry-run` };
  }
}

function dependenciasTexto(id) {
  const d = (ETAPAS[id] && ETAPAS[id].dependeDe) || [];
  return d.length ? `Necesita aprobadas: ${d.join(', ')}.` : 'No depende de otra etapa.';
}

/** Entradas de una etapa: dependencias del flujo + hashes que dice el estado (si los hay). */
export function entradasDeEtapa(id, estadoJson) {
  const deps = (ETAPAS[id] && ETAPAS[id].dependeDe) || [];
  const hashes = estadoJson && estadoJson.etapas && esObjeto(estadoJson.etapas[id]) && esObjeto(estadoJson.etapas[id].entradas)
    ? estadoJson.etapas[id].entradas : {};
  const lista = deps.map((d) => ({ etapa: d, hash: hashes[d] || null }));
  for (const k of Object.keys(hashes)) if (!deps.includes(k)) lista.push({ etapa: k, hash: hashes[k] });
  return lista;
}

export function salidasDeEtapa(id) { return ((ETAPAS[id] && ETAPAS[id].salidas) || []).slice(); }

// ---------------------------------------------------------------------------------------------
// Artefactos: tipo de visor, versiones vN y diferencias

const EXT_TIPO = {
  json: 'json', jsonl: 'texto', md: 'md', markdown: 'md', yaml: 'yaml', yml: 'yaml', html: 'html', htm: 'html',
  png: 'imagen', jpg: 'imagen', jpeg: 'imagen', gif: 'imagen', webp: 'imagen', svg: 'imagen',
  txt: 'texto', css: 'texto', js: 'texto', csv: 'texto', log: 'texto',
};

export function extension(ruta) {
  const base = texto(ruta).split('/').pop();
  const i = base.lastIndexOf('.');
  return i <= 0 ? '' : base.slice(i + 1).toLowerCase();
}

/** Tipo de visor: confía en `tipo` del servidor si es uno conocido; si no, deduce de la extensión. */
export function tipoVisor(art) {
  const t = art && art.tipo;
  if (['json', 'md', 'yaml', 'html', 'imagen', 'texto'].includes(t)) return t;
  return EXT_TIPO[extension(art && art.ruta)] || 'texto';
}

const RX_VERSION = /(^|[\/_.-])v([1-9][0-9]*)(?=[\/_.-]|$)/;

/** Número de versión (vN) en la ruta, o null. Reconoce `v2/` y `-v2.` / `_v2.` / `-v2-`. */
export function versionDeRuta(ruta) {
  const m = RX_VERSION.exec(texto(ruta));
  return m ? Number(m[2]) : null;
}

/** Ruta con el token de versión reemplazado por «v*» (clave de agrupación). */
export function claveSinVersion(ruta) {
  return texto(ruta).replace(RX_VERSION, (_t, pre) => `${pre}v*`);
}

/**
 * Agrupa artefactos que solo difieren en el número de versión. Devuelve solo los grupos con ≥ 2 versiones:
 * [{clave, versiones:[{n, ruta, bytes, mtime}]}] ordenadas de menor a mayor.
 */
export function gruposDeVersiones(artefactos) {
  const mapa = new Map();
  for (const a of artefactos || []) {
    if (!a || typeof a.ruta !== 'string') continue;
    const n = versionDeRuta(a.ruta);
    if (n == null) continue;
    const k = claveSinVersion(a.ruta);
    if (!mapa.has(k)) mapa.set(k, new Map());
    mapa.get(k).set(n, { n, ruta: a.ruta, bytes: a.bytes ?? null, mtime: a.mtime ?? null });
  }
  const grupos = [];
  for (const [clave, vs] of mapa) {
    if (vs.size < 2) continue;
    grupos.push({ clave, versiones: [...vs.values()].sort((x, y) => x.n - y.n) });
  }
  grupos.sort((a, b) => a.clave.localeCompare(b.clave));
  return grupos;
}

/** Agrupa artefactos por carpeta inmediata para listarlos sin desbordar la pantalla. */
export function agruparPorCarpeta(artefactos) {
  const mapa = new Map();
  for (const a of artefactos || []) {
    if (!a || typeof a.ruta !== 'string') continue;
    const partes = a.ruta.split('/');
    partes.pop();
    const carpeta = partes.join('/') || '.';
    if (!mapa.has(carpeta)) mapa.set(carpeta, []);
    mapa.get(carpeta).push(a);
  }
  return [...mapa.entries()]
    .sort((x, y) => x[0].localeCompare(y[0]))
    .map(([carpeta, items]) => ({ carpeta, items: items.slice().sort((p, q) => p.ruta.localeCompare(q.ruta)) }));
}

export const TOPE_LINEAS_DIFF = 2000;

/**
 * Diferencia por líneas (LCS). Devuelve [{tipo:'igual'|'mas'|'menos', texto, a, b}], con `a`/`b` = número de línea
 * en cada versión. Si algún lado supera TOPE_LINEAS_DIFF devuelve {truncado:true}.
 */
export function diferenciaLineas(antes, despues) {
  const A = texto(antes).replace(/\r\n/g, '\n').split('\n');
  const B = texto(despues).replace(/\r\n/g, '\n').split('\n');
  if (A.length > TOPE_LINEAS_DIFF || B.length > TOPE_LINEAS_DIFF) return { truncado: true, lineas: [] };
  const n = A.length;
  const m = B.length;
  // Recorta prefijo y sufijo comunes para que el LCS sea pequeño en la práctica.
  let ini = 0;
  while (ini < n && ini < m && A[ini] === B[ini]) ini += 1;
  let finA = n;
  let finB = m;
  while (finA > ini && finB > ini && A[finA - 1] === B[finB - 1]) { finA -= 1; finB -= 1; }
  const a = A.slice(ini, finA);
  const b = B.slice(ini, finB);
  const filas = a.length + 1;
  const cols = b.length + 1;
  const t = new Uint32Array(filas * cols);
  for (let i = a.length - 1; i >= 0; i -= 1) {
    for (let j = b.length - 1; j >= 0; j -= 1) {
      t[i * cols + j] = a[i] === b[j] ? t[(i + 1) * cols + j + 1] + 1 : Math.max(t[(i + 1) * cols + j], t[i * cols + j + 1]);
    }
  }
  const out = [];
  for (let i = 0; i < ini; i += 1) out.push({ tipo: 'igual', texto: A[i], a: i + 1, b: i + 1 });
  let i = 0;
  let j = 0;
  while (i < a.length || j < b.length) {
    if (i < a.length && j < b.length && a[i] === b[j]) {
      out.push({ tipo: 'igual', texto: a[i], a: ini + i + 1, b: ini + j + 1 }); i += 1; j += 1;
    } else if (i < a.length && (j === b.length || t[(i + 1) * cols + j] >= t[i * cols + j + 1])) {
      out.push({ tipo: 'menos', texto: a[i], a: ini + i + 1, b: null }); i += 1; // las bajas van antes que las altas
    } else {
      out.push({ tipo: 'mas', texto: b[j], a: null, b: ini + j + 1 }); j += 1;
    }
  }
  for (let k = finA; k < n; k += 1) out.push({ tipo: 'igual', texto: A[k], a: k + 1, b: finB + (k - finA) + 1 });
  return { truncado: false, lineas: out };
}

/** Colapsa las líneas iguales lejos de un cambio; deja `contexto` líneas alrededor. {tipo:'salto', n} marca lo omitido. */
export function contextoDiff(lineas, contexto = 3) {
  const cambia = lineas.map((l) => l.tipo !== 'igual');
  const cerca = new Array(lineas.length).fill(false);
  for (let i = 0; i < lineas.length; i += 1) {
    if (!cambia[i]) continue;
    for (let k = Math.max(0, i - contexto); k <= Math.min(lineas.length - 1, i + contexto); k += 1) cerca[k] = true;
  }
  const out = [];
  let omitidas = 0;
  for (let i = 0; i < lineas.length; i += 1) {
    if (cerca[i]) {
      if (omitidas) { out.push({ tipo: 'salto', n: omitidas }); omitidas = 0; }
      out.push(lineas[i]);
    } else omitidas += 1;
  }
  if (omitidas) out.push({ tipo: 'salto', n: omitidas });
  return out;
}

export function resumenDiff(lineas) {
  let mas = 0;
  let menos = 0;
  for (const l of lineas) { if (l.tipo === 'mas') mas += 1; else if (l.tipo === 'menos') menos += 1; }
  return { mas, menos, igual: mas === 0 && menos === 0 };
}

// ---------------------------------------------------------------------------------------------
// QA

const TONO_VEREDICTO = { PASS: 'ok', PASS_CON_NOTAS: 'aviso', FAIL: 'error', ESCALAR: 'error' };
export function tonoVeredicto(v) { return TONO_VEREDICTO[v] || 'neutro'; }

/** Ruta relativa a ofertas/<id>/ del informe de QA. El servidor puede mandar «d3-v1.json» o «qa/d3-v1.json». */
export function rutaInformeQa(archivo) {
  const a = texto(archivo).replace(/^\/+/, '');
  if (a === '') return '';
  return a.startsWith('qa/') ? a : `qa/${a}`;
}

/** Texto corto del `resumen` del QA, venga como texto o como objeto. */
export function textoResumenQa(r) {
  if (r == null) return '';
  if (typeof r === 'string') return r;
  if (esObjeto(r)) {
    const partes = [];
    if (r.puntaje_global != null) partes.push(`nota ${r.puntaje_global}${r.umbral != null ? ` (mínimo ${r.umbral})` : ''}`);
    if (r.hallazgos != null && !esObjeto(r.hallazgos)) partes.push(`${r.hallazgos} hallazgos`);
    if (partes.length) return partes.join(' · ');
    return Object.entries(r).map(([k, v]) => `${k}: ${esObjeto(v) || Array.isArray(v) ? JSON.stringify(v) : v}`).join(' · ');
  }
  return texto(r);
}

/** Informe de QA completo (contenido del JSON) -> modelo de vista. Tolera JSON parcial. */
export function vistaInformeQa(informe) {
  const inf = esObjeto(informe) ? informe : {};
  const hallazgos = Array.isArray(inf.hallazgos) ? inf.hallazgos.filter(esObjeto) : [];
  const porSeveridad = {};
  for (const s of SEVERIDADES_QA) porSeveridad[s] = [];
  const otros = [];
  for (const h of hallazgos) (porSeveridad[h.severidad] || otros).push(h);
  const abiertos = hallazgos.filter((h) => h.estado === 'abierto' || h.estado === 'devuelto_al_maker');
  return {
    veredicto: inf.veredicto ?? null,
    tono: tonoVeredicto(inf.veredicto),
    ronda: inf.ronda ?? null,
    version: inf.version ?? null,
    puntaje: inf.puntaje_global ?? null,
    umbral: inf.umbral ?? null,
    creadoEn: inf.creado_en ?? null,
    items: Array.isArray(inf.items) ? inf.items.filter(esObjeto) : [],
    checks: Array.isArray(inf.checks_l1) ? inf.checks_l1.filter(esObjeto) : [],
    checksFallidos: Array.isArray(inf.checks_l1) ? inf.checks_l1.filter((c) => esObjeto(c) && c.resultado === 'fail').length : 0,
    hallazgos,
    porSeveridad,
    otros,
    abiertos: abiertos.length,
    conteo: Object.fromEntries(SEVERIDADES_QA.map((s) => [s, porSeveridad[s].length])),
    justificacion: typeof inf.justificacion_sin_hallazgos === 'string' ? inf.justificacion_sin_hallazgos : null,
    x1: esObjeto(inf.x1) ? inf.x1 : null,
    semaforo: inf.semaforo ?? null,
    vigenciaHasta: inf.vigencia_hasta ?? null,
  };
}

// ---------------------------------------------------------------------------------------------
// Línea de tiempo a partir del registro (GET /registro?oferta=…)

const ICONO_EVENTO = {
  accion: '•', transicion: '→', llamada_herramienta: '⚙', decision: '◆', bloqueo: '■', alerta: '!', aprobacion: '✓',
};
const TONO_EVENTO = { bloqueo: 'error', alerta: 'aviso', aprobacion: 'ok', transicion: 'info', decision: 'info', accion: 'neutro', llamada_herramienta: 'neutro' };

/** Una línea del registro -> evento de vista. Tolera campos ausentes. */
export function vistaEventoRegistro(l) {
  const r = esObjeto(l.resultado) ? l.resultado : {};
  const estadoRes = r.estado ?? null;
  const tono = estadoRes === 'bloqueado' || estadoRes === 'error' ? 'error' : (TONO_EVENTO[l.evento] || 'neutro');
  return {
    n: l.n ?? null,
    ts: l.ts ?? null,
    etapa: l.etapa ?? null,
    agente: l.agente ?? null,
    evento: l.evento ?? null,
    icono: ICONO_EVENTO[l.evento] || '•',
    tono,
    texto: texto(l.entrada_resumen ?? l.resumen ?? ''),
    herramienta: l.herramienta ?? null,
    estado: estadoRes,
    codigo: r.codigo ?? null,
    modo: l.modo ?? null,
    costo: esObjeto(l.costo_estimado) ? l.costo_estimado : null,
    ejecucionId: l.ejecucion_id ?? null,
  };
}

/** Línea de tiempo: más reciente primero, filtrable por etapa y evento. */
export function lineaDeTiempo(lineas, { etapa = null, evento = null, limite = 200 } = {}) {
  const lista = (Array.isArray(lineas) ? lineas : []).filter(esObjeto).map(vistaEventoRegistro)
    .filter((e) => (!etapa || e.etapa === etapa) && (!evento || e.evento === evento));
  lista.sort((a, b) => {
    const ta = a.ts || '';
    const tb = b.ts || '';
    if (ta !== tb) return ta < tb ? 1 : -1;
    return (b.n ?? 0) - (a.n ?? 0);
  });
  return lista.slice(0, limite);
}

/** El registro puede llegar como {lineas:[…]} (API) o como array. */
export function lineasDeRegistro(datos) {
  if (Array.isArray(datos)) return datos;
  if (esObjeto(datos) && Array.isArray(datos.lineas)) return datos.lineas;
  return [];
}

// ---------------------------------------------------------------------------------------------
// Cabecera de la oferta

/** Datos clave/valor de la cabecera a partir de estado.json (sin formateo de dinero: lo hace la página). */
export function cabeceraOferta(estado) {
  const e = esObjeto(estado) ? estado : {};
  return {
    ofertaId: e.oferta_id ?? null,
    familiaId: e.familia_id ?? null,
    fase: e.fase ?? null,
    nivel: e.nivel ?? null,
    pausa: e.pausa === true,
    revision: e.revision ?? null,
    gastoHoy: esObjeto(e.gasto) ? (e.gasto.hoy ?? null) : null,
    gastoAcumulado: esObjeto(e.gasto) ? (e.gasto.acumulado ?? null) : null,
    costoIa: esObjeto(e.costo_ia) ? e.costo_ia : null,
    actualizadoEn: e.actualizado_en ?? null,
    candidato: esObjeto(e.candidato_elegido) ? e.candidato_elegido : null,
    skillsPin: esObjeto(e.skills_pin) ? e.skills_pin : {},
  };
}

const TONO_FASE = {
  borrador: 'neutro', en_construccion: 'info', listo_para_activar: 'aviso', en_test: 'info', validada: 'ok',
  fallida: 'error', inconclusa: 'aviso', escalando: 'ok', retirada: 'neutro', pausada: 'error',
};
const ROTULO_FASE = {
  borrador: 'borrador', en_construccion: 'en construcción', listo_para_activar: 'lista para activar', en_test: 'en prueba',
  validada: 'validada', fallida: 'fallida', inconclusa: 'inconclusa', escalando: 'escalando', retirada: 'retirada', pausada: 'pausada',
};
export function tonoFase(fase) { return TONO_FASE[fase] || 'neutro'; }
export function rotuloFase(fase) { return ROTULO_FASE[fase] || (fase == null ? 'sin dato' : String(fase)); }

export const FASES = Object.keys(ROTULO_FASE);

/** Rótulo del gate («H · Humano»). */
export function gateTexto(gate) {
  return gate && GATES[gate] ? `${gate} · ${GATES[gate].titulo}` : 'sin gate';
}

// ---------------------------------------------------------------------------------------------
// Lenguaje de negocio (rediseño UX). El nombre técnico y el código (D1…) quedan como etiqueta secundaria.

/** Nombre humano de cada etapa del flujo (el código D1… se muestra pequeño al lado). */
export const NOMBRES_HUMANOS = {
  D1: 'Descubrir', M1: 'Mercado', D2: 'Validar', D3: 'Oferta', D4: 'Producto', D5: 'Página de venta y pago',
  D6: 'Anuncios', D7: 'Campaña', D8: 'Operación', D9: 'Escalado', D10: 'Después de la venta',
};

/** La pregunta de negocio que responde cada etapa. */
export const PREGUNTAS_ETAPA = {
  D1: '¿Qué problema vale la pena atacar?',
  M1: '¿En qué idioma y países se vende, y cómo se cobra?',
  D2: '¿Hay demanda real y lo gratis no alcanza?',
  D3: '¿Qué se vende exactamente, a qué precio y con qué promesa?',
  D4: '¿Está terminado el producto que recibe el cliente?',
  D5: '¿Dónde se ve la oferta y cómo se paga?',
  D6: '¿Qué anuncios se van a mostrar?',
  D7: '¿Cómo queda configurada la campaña en Meta?',
  D8: '¿Está funcionando? Seguir, pausar o escalar',
  D9: '¿Se duplica lo que gana?',
  D10: '¿Cómo se entrega y se atiende al comprador?',
};

/** Qué hace la etapa, en una frase sin siglas. */
export const DESCRIPCION_HUMANA = {
  D1: 'Elegir qué problema atacar: el sistema propone candidatos con evidencia citada y tú eliges uno.',
  M1: 'Decidir idioma, países, moneda y métodos de cobro del mercado donde se prueba la oferta.',
  D2: 'Comprobar con evidencia que hay demanda y que las alternativas gratis no resuelven el problema.',
  D3: 'Definir qué se vende: promesa, precio, regalos extra, garantía y si cada venta deja ganancia.',
  D4: 'Producir el entregable terminado, con su muestra y las fuentes que lo respaldan.',
  D5: 'Montar la página de venta, el cobro y el seguimiento de visitas y compras.',
  D6: 'Preparar los anuncios: textos, imágenes y la declaración de uso de IA.',
  D7: 'Dejar lista la campaña de Meta como borrador. Activarla exige tu firma y el visto bueno de cumplimiento.',
  D8: 'Leer cada día las cifras y aplicar reglas fijas para seguir, pausar o escalar.',
  D9: 'Clonar y escalar lo que gana. Queda fuera del primer testeo: solo se registra la propuesta.',
  D10: 'Entregar el producto, gestionar reembolsos por regla y frenar si algo falla.',
};

/** «N2» → «Autonomía 2» (el nivel de autonomía va del 0 al 4); otro valor se muestra tal cual. */
export function rotuloNivel(n) { return typeof n === 'string' && /^N[0-4]$/.test(n) ? `Autonomía ${n.slice(1)}` : String(n ?? '—'); }

/** Nombre en palabras del tipo de archivo que usa el visor (json, md, yaml, html, imagen, texto). */
const ROTULO_TIPO_ARCHIVO = { json: 'Datos', md: 'Documento', yaml: 'Datos', html: 'Página web', imagen: 'Imagen', texto: 'Texto' };
export function rotuloTipoArchivo(tipo) { return ROTULO_TIPO_ARCHIVO[tipo] || 'Archivo'; }

export function nombreHumano(id) { return NOMBRES_HUMANOS[id] || nombreEtapa(id); }
/** «D7 · Campaña». */
export function etiquetaEtapa(id) { return `${id} · ${nombreHumano(id)}`; }

/**
 * Lo que `ui.pasos` necesita de una etapa: estado, aviso y nombre humano (el código D1… va aparte, en `codigo`).
 * La etapa que espera tu firma va con estado `espera_firma` (el stepper la resalta con el acento).
 */
export function etapaParaPasos(v, { seleccionada = false } = {}) {
  const estado = v.sinDatos ? 'pendiente' : (v.gatePendiente ? 'espera_firma' : (v.obsoleta ? 'obsoleta' : v.estado));
  let aviso = null;
  if (v.gatePendiente) aviso = null; // el estado «Espera tu firma» ya lo dice
  else if (v.bloqueo || v.estado === 'bloqueado') aviso = v.bloqueo || 'Bloqueada';
  else if (v.estado === 'escalado') aviso = 'Escalada a ti';
  else if (v.obsoleta) aviso = 'Hay que rehacerla';
  else if (v.sinDatos) aviso = 'Sin datos';
  return { id: v.id, nombre: nombreHumano(v.id), codigo: v.id, estado, seleccionada, destacada: v.gatePendiente === true, aviso };
}

/** Texto humano del estado de una etapa («Aprobada», «Espera tu firma»…) con su tono. */
export function estadoHumano(v) {
  if (v.sinDatos) return { texto: 'Sin datos', tono: 'neutro' };
  if (v.gatePendiente) return { texto: 'Espera tu firma', tono: 'aviso' };
  if (v.obsoleta) return { texto: 'Obsoleta: hay que rehacerla', tono: 'aviso' };
  switch (v.estado) {
    case 'aprobado': return { texto: 'Aprobada', tono: 'ok' };
    case 'en_QA': return { texto: 'En revisión de calidad', tono: 'info' };
    case 'en_progreso': return { texto: 'En marcha', tono: 'info' };
    case 'bloqueado': return { texto: 'Bloqueada', tono: 'error' };
    case 'escalado': return { texto: 'Escalada a una persona', tono: 'error' };
    default: return { texto: 'Pendiente', tono: 'neutro' };
  }
}

export const GATES_HUMANOS = {
  A: { titulo: 'Se aprueba sola', ayuda: 'Pasa sola si la revisión de calidad la aprueba.' },
  S: { titulo: 'Tú solo por excepción', ayuda: 'Te la pide solo si la revisión trae notas, falla o cae en muestreo.' },
  H: { titulo: 'Requiere tu firma', ayuda: 'Nada avanza sin tu firma: el sistema no puede saltarse este control.' },
};

/**
 * Próximo paso en lenguaje de negocio, para la tarjeta dominante. Parte de `proximoPaso` (lo que diga el servidor o la deducción
 * local) y lo reescribe: «D7 · Campaña espera tu firma». `accion.modo` dice qué abre el botón primario:
 * firmar → panel lateral con el comando · ver → ir a la etapa · rehacer/ejecutar → panel con el comando de ejecución.
 */
export function proximoPasoHumano(ofertaId, vistas, resumen, apiProximo = null) {
  const base = proximoPaso(ofertaId, vistas, resumen, apiProximo);
  const v = base.etapa ? vistas.find((x) => x.id === base.etapa) : null;
  const et = v ? etiquetaEtapa(v.id) : null;
  const out = {
    etapa: v ? v.id : null, tono: base.tono || 'neutro', origen: base.origen, motorDisponible: base.motorDisponible ?? null,
    comando: base.comando || null, tipo: 'sin_paso', titulo: base.titulo, detalle: base.detalle, accion: null, secundaria: null,
  };
  if (!vistas.length || resumen.sinDatos) {
    return { ...out, tipo: 'sin_estado', tono: 'aviso', titulo: 'Esta oferta todavía no tiene etapas', detalle: 'Todavía no se registraron las etapas de esta oferta. Se crean cuando el sistema da de alta la oferta desde su ficha inicial (brief) firmada.', accion: { texto: 'Ver cómo crearla', modo: 'ejecutar' } };
  }
  if (resumen.completa) {
    return { ...out, tipo: 'completa', tono: 'ok', titulo: 'Todas las etapas están aprobadas', detalle: 'Revisa los resultados del día a día y lo que pasa después de la venta.', accion: { texto: 'Ver Resultados', modo: 'etapa', etapa: 'D8' } };
  }
  if (!v) return { ...out, tipo: 'sin_paso', titulo: 'No hay un próximo paso claro', detalle: null };
  if (v.obsoleta) {
    return { ...out, tipo: 'rehacer', tono: 'aviso', titulo: `Rehacer ${et}`, detalle: 'Cambió algo de lo que depende: la versión aprobada quedó obsoleta (se conserva la anterior).', accion: { texto: 'Ver cómo rehacerla', modo: 'ejecutar' }, secundaria: { texto: 'Abrir la etapa', modo: 'etapa', etapa: v.id } };
  }
  if (v.gatePendiente) {
    return { ...out, tipo: 'firmar_gate', tono: 'acento', titulo: `${et} espera tu firma`, detalle: 'La revisión de calidad terminó y falta tu aprobación. Mira lo producido y el informe antes de firmar.', accion: { texto: 'Ver cómo firmarlo', modo: 'firmar' }, secundaria: { texto: 'Ver la revisión', modo: 'etapa', etapa: v.id, pestana: 'revision' } };
  }
  switch (v.estado) {
    case 'en_QA':
      return { ...out, tipo: 'en_qa', tono: 'info', titulo: `${et} está en revisión de calidad`, detalle: v.rondaQa != null && v.rondaQa > 0 ? `Va por la ronda ${v.rondaQa}. No hace falta que hagas nada todavía.` : 'No hace falta que hagas nada todavía.', accion: { texto: 'Ver la revisión', modo: 'etapa', etapa: v.id, pestana: 'revision' } };
    case 'en_progreso':
      return { ...out, tipo: 'en_progreso', tono: 'info', titulo: `${et} está en marcha`, detalle: 'Si la estás armando a mano, ábrela para ver qué entradas tiene y cómo ingresar lo que hagas.', accion: { texto: 'Abrir la etapa', modo: 'etapa', etapa: v.id } };
    case 'bloqueado':
      return { ...out, tipo: 'bloqueado', tono: 'error', titulo: `${et} está bloqueada`, detalle: v.bloqueo ? bloqueoHumano(v.bloqueo) : 'Falta un dato, un acceso o un servicio externo.', accion: { texto: 'Ver el bloqueo', modo: 'etapa', etapa: v.id } };
    case 'escalado':
      return { ...out, tipo: 'escalado', tono: 'error', titulo: `${et} necesita una decisión tuya`, detalle: 'Tras dos rondas con hallazgos graves el sistema la pasó a una persona. Solo sale por orden tuya.', accion: { texto: 'Ver por qué', modo: 'etapa', etapa: v.id, pestana: 'revision' } };
    default:
      return { ...out, tipo: 'siguiente', tono: 'neutro', titulo: `Siguiente: ${et}`, detalle: dependenciasHumanas(v.id), accion: { texto: 'Ver cómo ejecutarla', modo: 'ejecutar' }, secundaria: { texto: 'Abrir la etapa', modo: 'etapa', etapa: v.id } };
  }
}

export function dependenciasHumanas(id) {
  const d = (ETAPAS[id] && ETAPAS[id].dependeDe) || [];
  if (!d.length) return 'No depende de ninguna otra etapa.';
  return `Necesita aprobadas: ${d.map((x) => nombreHumano(x)).join(', ')}.`;
}

// ── revisión de calidad (QA) ──

export const SEVERIDAD_QA_HUMANA = { BLOQUEANTE: 'Bloqueante', MAYOR: 'Mayor', MENOR: 'Menor', MEJORA: 'Mejora' };
export const AYUDA_SEVERIDAD_QA = {
  BLOQUEANTE: 'Impide aprobar la etapa hasta que se corrija.',
  MAYOR: 'Debe corregirse; con dos rondas de graves la etapa pasa a una persona.',
  MENOR: 'Conviene corregirlo; no frena la aprobación.',
  MEJORA: 'Idea para mejorar; opcional.',
};
export function tonoSeveridadQa(s) { return s === 'BLOQUEANTE' ? 'error' : (s === 'MAYOR' ? 'grave' : (s === 'MENOR' ? 'aviso' : 'info')); }

const VEREDICTO_HUMANO = { PASS: 'Aprobada por la revisión', PASS_CON_NOTAS: 'Aprobada con notas', FAIL: 'Rechazada por la revisión', ESCALAR: 'Escalada a una persona' };
export function veredictoHumano(v) { return VEREDICTO_HUMANO[v] || 'Sin veredicto'; }

const VEREDICTO_CORTO = { PASS: 'aprobada', PASS_CON_NOTAS: 'aprobada con notas', FAIL: 'rechazada', ESCALAR: 'escalada a una persona' };
/** Veredicto en una palabra para listas («aprobada»). */
export function veredictoCorto(v) { return VEREDICTO_CORTO[v] || 'sin veredicto'; }
const VEREDICTO_X1 = { PASS: 'Cumplimiento sin objeciones', PASS_CON_NOTAS: 'Cumplimiento con notas', FAIL: 'Cumplimiento: no pasa', ESCALAR: 'Cumplimiento: lo decide una persona' };
/** Veredicto del dictamen de cumplimiento (X1) en palabras. */
export function veredictoCumplimiento(v) { return VEREDICTO_X1[v] || 'Sin informe de cumplimiento'; }

const ESTADO_HALLAZGO = {
  abierto: ['Abierto', 'error'], devuelto_al_maker: ['Devuelto a quien lo preparó', 'error'], corregido_por_qa: ['Corregido por la revisión', 'ok'],
  corregido: ['Corregido', 'ok'], resuelto: ['Resuelto', 'ok'], aceptado_con_nota: ['Aceptado con nota', 'neutro'], descartado: ['Descartado', 'neutro'],
};
/** Estado de un hallazgo en palabras, con su tono. Desconocido → el texto original sin guiones bajos. */
export function estadoHallazgo(e) {
  const hit = ESTADO_HALLAZGO[e];
  if (hit) return { texto: hit[0], tono: hit[1], abierto: e === 'abierto' || e === 'devuelto_al_maker' };
  return { texto: String(e ?? '—').replace(/_/g, ' '), tono: 'neutro', abierto: false };
}

/** Nota 0-5 → «4,4 de 5». Admite números y textos numéricos («4.40»). */
export function puntajeTexto(p) {
  const n = typeof p === 'number' ? p : (typeof p === 'string' && p.trim() !== '' ? Number(p.replace(',', '.')) : NaN);
  if (!Number.isFinite(n)) return null;
  return String(Math.round(n * 100) / 100).replace('.', ',');
}

// ── historial (registro) ──

const EVENTO_HUMANO = {
  accion: 'Acción', transicion: 'Cambio de estado', llamada_herramienta: 'Trabajo de IA', decision: 'Decisión', bloqueo: 'Bloqueo', alerta: 'Alerta', aprobacion: 'Aprobación',
};
export function eventoHumano(e) { return EVENTO_HUMANO[e] || String(e ?? 'Evento').replace(/_/g, ' '); }

// ── nombre y mercado de la oferta ──

function mayuscula(t) { const s = texto(t).trim(); return s ? s.charAt(0).toUpperCase() + s.slice(1) : ''; }

/** Texto de un slug («reinsercion-laboral-madres» → «Reinsercion laboral madres»). Último recurso: no puede recuperar tildes. */
export function humanizarSlug(slug) { return mayuscula(texto(slug).replace(/[-_]+/g, ' ')); }

/**
 * Título legible de una oferta. Orden: nombre comercial (promesa.titulo de oferta.json, si se leyó) > tema semilla del brief >
 * slug > id. `extra.titulo` es el nombre comercial leído aparte.
 */
export function tituloDeOferta({ brief = null, estado = null, id = '', titulo = null } = {}) {
  if (typeof titulo === 'string' && titulo.trim()) return titulo.trim();
  const b = esObjeto(brief) ? brief : {};
  if (typeof b.tema_semilla === 'string' && b.tema_semilla.trim()) return mayuscula(b.tema_semilla);
  if (typeof b.slug === 'string' && b.slug.trim()) return humanizarSlug(b.slug);
  const e = esObjeto(estado) ? estado : {};
  return texto(e.oferta_id || id);
}

let _idiomas = null;
let _paises = null;
function displayNames(tipo) {
  try {
    if (typeof Intl !== 'undefined' && typeof Intl.DisplayNames === 'function') return new Intl.DisplayNames(['es'], { type: tipo });
  } catch (_) { /* sin ICU */ }
  return null;
}
/** «es-ES» → «Español (España)». Si el entorno no sabe el nombre, devuelve el código tal cual. */
export function nombreIdioma(locale) {
  const l = texto(locale).trim();
  if (!l) return null;
  if (_idiomas === null) _idiomas = displayNames('language') || false;
  try {
    const n = _idiomas ? _idiomas.of(l) : null;
    if (n && n !== l) return mayuscula(n);
  } catch (_) { /* código inválido */ }
  return l;
}
/** «ES» → «España». */
export function nombrePais(codigo) {
  const c = texto(codigo).trim().toUpperCase();
  if (!c) return null;
  if (_paises === null) _paises = displayNames('region') || false;
  try {
    const n = _paises ? _paises.of(c) : null;
    if (n && n !== c) return n;
  } catch (_) { /* código inválido */ }
  return c;
}

/** Mercado de una oferta a partir de `mercado` (mercado.json) o, si falta, del brief. */
export function fichaMercado(datos) {
  const d = esObjeto(datos) ? datos : {};
  const m = esObjeto(d.mercado) ? d.mercado : {};
  const b = esObjeto(d.brief) ? d.brief : {};
  const mo = esObjeto(b.mercado_objetivo) ? b.mercado_objetivo : {};
  const locale = m.locale || mo.locale || null;
  const paisesCod = Array.isArray(m.paises_segmentacion) && m.paises_segmentacion.length ? m.paises_segmentacion : (Array.isArray(mo.paises_segmentacion) ? mo.paises_segmentacion : []);
  return {
    locale, idioma: nombreIdioma(locale), paisesCodigos: paisesCod, paises: paisesCod.map(nombrePais),
    moneda: m.moneda_cobro || mo.moneda_cobro || null, esHipotesis: m.estado_decision ? m.estado_decision === 'hipotesis' : (mo.es_hipotesis === true ? true : null),
  };
}

/**
 * Respuesta de `GET /oferta/<id>/referente` → filas para la tarjeta «Landing original» (puro). Una dirección solo se acepta si es
 * https sin espacios ni caracteres invisibles (el servidor ya la validó; aquí se comprueba otra vez): es lo ÚNICO que se vuelve enlace.
 */
export function normalizarReferentesOferta(datos) {
  const limpio = (v, max) => (typeof v === 'string' ? v.replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, max) : '');
  const HTTPS_LIMPIO = /^https:\/\/[^\s\u0000-\u001f\u007f-\u009f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]+$/i;
  const d = datos && typeof datos === 'object' ? datos : {};
  const filas = (Array.isArray(d.referentes) ? d.referentes : [])
    .filter((f) => f && typeof f === 'object' && typeof f.url === 'string' && f.url.length <= 500 && HTTPS_LIMPIO.test(f.url))
    .map((f) => ({
      url: f.url, dominio: limpio(f.dominio, 120), nombre: limpio(f.nombre, 120), nota: limpio(f.nota, 300),
      copiaLocal: limpio(f.copia_local, 300), origen: f.origen === 'registro' ? 'registro' : 'validacion', registradaEn: limpio(f.registrada_en, 40),
    }));
  return { filas, comando: limpio(d.comando_registrar, 300) };
}
