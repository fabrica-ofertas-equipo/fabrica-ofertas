// Lógica pura de la pantalla «Skills» (#/skills): GET /skills (de .claude/skills/*/ y .claude/agents/) -> filas,
// cobertura por etapa, checklist del DoD (docs/03 §2.6) y filtros. Sin DOM ni red.
// Se prueba con `node --test` (tests/dashboard/test_web_skills.mjs).

import { ORDEN_ETAPAS, ETAPAS, plano } from './oferta.js';

function esObjeto(x) { return x !== null && typeof x === 'object' && !Array.isArray(x); }
function cad(x) { return typeof x === 'string' ? x : (x == null ? '' : String(x)); }

/** Límites de forma del DoD (docs/03 §2.6 ítem 7). */
export const MAX_LINEAS_SKILL_MD = 500;
export const MAX_CARACTERES_DESCRIPCION = 1024;

/** Estructura obligatoria de una skill (docs/03 §2.5 y .claude/skills/README.md). */
export const ESTRUCTURA = [
  { clave: 'skill', etiqueta: 'SKILL.md', nombre: 'Instrucciones principales' },
  { clave: 'references', etiqueta: 'references/', nombre: 'Material de consulta' },
  { clave: 'rubric', etiqueta: 'rubric.md', nombre: 'Criterios de revisión' },
  { clave: 'templates', etiqueta: 'templates/', nombre: 'Plantillas' },
  { clave: 'scripts', etiqueta: 'scripts/', nombre: 'Programas de apoyo' },
  { clave: 'evals', etiqueta: 'evals/', nombre: 'Casos de prueba' },
  { clave: 'changelog', etiqueta: 'CHANGELOG.md', nombre: 'Historial de cambios' },
];
/** Nombre en palabras de un archivo de la estructura («evals/» → «Casos de prueba»); si no se conoce, el mismo texto. */
export function nombreArchivo(etiqueta) {
  const e = ESTRUCTURA.find((x) => x.etiqueta === etiqueta);
  return e ? e.nombre : cad(etiqueta);
}

/** Los 11 criterios de listo del plan (docs/03 §2.6). `innegociable` según la tabla del plan. */
export const CRITERIOS_DOD = [
  { n: 1, criterio: 'Contrato: salida válida contra su esquema en el 100 % de las corridas', innegociable: true },
  { n: 2, criterio: 'Determinismo: scripts con tests; ejemplos numéricos con diferencia 0', innegociable: true },
  { n: 3, criterio: 'Evals: ≥ 6 casos; con skill > sin skill en cada uno', innegociable: false },
  { n: 4, criterio: 'Estabilidad: 3 corridas del mismo caso, decisión clave igual en ≥ 2 de 3', innegociable: false },
  { n: 5, criterio: 'QA calibrado: 100 % de dorados en PASS, ≥ 90 % de bloqueantes sembrados', innegociable: true },
  { n: 6, criterio: 'Tu aceptación en sombra: ≥ 2 de 3 casos sin edición sustantiva', innegociable: false },
  { n: 7, criterio: 'Forma: SKILL.md < 500 líneas, description < 1.024 caracteres', innegociable: false },
  { n: 8, criterio: 'Seguridad: prueba de inyección pasa; sin secretos; acciones externas tras gate', innegociable: true },
  { n: 9, criterio: 'Costo: dentro del tope por corrida, registrado en costos.jsonl', innegociable: false },
  { n: 10, criterio: 'Sin sobreajuste: el caso de otro idioma pasa sin editar la skill', innegociable: false },
  { n: 11, criterio: 'Cumplimiento (solo D1, D3, D6, X1): 0 falsos verdes en retención', innegociable: true },
];

/** El criterio 11 del DoD (cumplimiento, 0 falsos verdes) solo aplica a estas etapas (docs/03 §2.6). */
export const ETAPAS_CON_CUMPLIMIENTO = ['D1', 'D3', 'D6', 'X1'];

/** Etapas que debería cubrir una skill. «criterio» = forja manual; «ingenieria» = código con tests y skill como manual. */
export const ETAPAS_EMPRESA = {
  X1: { nombre: 'Cumplimiento', forja: 'criterio' },
  O0: { nombre: 'Coordinador de la cartera', forja: 'ingenieria' },
  D0: { nombre: 'Cuentas y servicios base', forja: 'ingenieria' },
  F1: { nombre: 'Finanzas', forja: 'ingenieria' },
  F2: { nombre: 'Panel y números del negocio', forja: 'ingenieria' },
  X2: { nombre: 'Memoria y aprendizaje', forja: 'ingenieria' },
};
export const ETAPAS_FLUJO_SKILL = [...ORDEN_ETAPAS, 'X1'];
export const ETAPAS_RESTO_SKILL = ['O0', 'D0', 'F1', 'F2', 'X2'];

export function nombreEtapaSkill(id) {
  if (ETAPAS[id]) return ETAPAS[id].nombre;
  return ETAPAS_EMPRESA[id] ? ETAPAS_EMPRESA[id].nombre : id;
}

const PALABRAS_ETAPA = [
  [/descubr|radar/, 'D1'], [/mercado|locali/, 'M1'], [/valida/, 'D2'], [/oferta/, 'D3'], [/producto/, 'D4'],
  [/landing|checkout/, 'D5'], [/creativ/, 'D6'], [/campan/, 'D7'], [/optimiz|operacion/, 'D8'], [/escal/, 'D9'],
  [/postcompra|entrega/, 'D10'], [/complian|cumplim/, 'X1'], [/orquest/, 'O0'], [/fundac|infra/, 'D0'],
  [/finanz/, 'F1'], [/dashboard|bi$/, 'F2'], [/aprendiz|memoria/, 'X2'],
];

/** Etapa a la que corresponde un slug de skill o de agente («d3-oferta», «d3-maker», «x1-qa»…). null si no se reconoce. */
export function etapaDeSlug(slug) {
  const s = cad(slug).toLowerCase();
  const tokens = s.split(/[^a-z0-9]+/).filter(Boolean);
  for (const t of tokens) {
    if (/^(m1|d(10|[1-9])|x[12]|o0|f[12]|d0)$/.test(t)) return t.toUpperCase();
  }
  for (const [rx, id] of PALABRAS_ETAPA) if (rx.test(s)) return id;
  return null;
}

// ---------------------------------------------------------------------------------------------
// Archivos y agentes: la API puede mandarlos como mapa de booleanos, números, listas o lista de rutas.

function claveArchivo(nombre) {
  const base = cad(nombre).toLowerCase().replace(/\/+$/, '').split('/')[0].replace(/\.[a-z0-9]+$/, '');
  if (base === 'skill') return 'skill';
  return base.replace(/[^a-z0-9]/g, '');
}

function presente(v) {
  if (v === true) return true;
  if (typeof v === 'number') return v > 0;
  if (typeof v === 'string') return v !== '';
  if (Array.isArray(v)) return v.length > 0;
  if (esObjeto(v)) {
    if ('existe' in v) return v.existe === true;
    if ('presente' in v) return v.presente === true;
    if ('n' in v && Number.isFinite(v.n)) return v.n > 0;
    return Object.keys(v).length > 0;
  }
  return false;
}

/** Mapa {skill, references, rubric, templates, scripts, evals, changelog: boolean} (todas las claves siempre presentes). */
export function archivosPresentes(archivos) {
  const mapa = {};
  for (const e of ESTRUCTURA) mapa[e.clave] = false;
  if (Array.isArray(archivos)) {
    for (const a of archivos) {
      const k = claveArchivo(typeof a === 'string' ? a : (esObjeto(a) ? (a.ruta ?? a.nombre ?? a.archivo) : ''));
      if (k in mapa) mapa[k] = true;
    }
  } else if (esObjeto(archivos)) {
    for (const [k, v] of Object.entries(archivos)) {
      const c = claveArchivo(k);
      if (c in mapa && presente(v)) mapa[c] = true;
    }
  }
  return mapa;
}

export function rolDeAgente(a) {
  const id = cad(esObjeto(a) ? (a.id ?? a.slug ?? a.nombre ?? '') : a).toLowerCase().replace(/\.md$/, '');
  const rol = esObjeto(a) ? cad(a.rol).toLowerCase() : '';
  if (rol === 'maker' || rol === 'qa') return rol;
  if (/(^|[-_])maker$/.test(id)) return 'maker';
  if (/(^|[-_])qa$/.test(id)) return 'qa';
  return 'otro';
}

export function idAgente(a) {
  return cad(esObjeto(a) ? (a.id ?? a.slug ?? a.nombre ?? '') : a).replace(/\.md$/, '');
}

export function resumenAgentes(agentes) {
  const lista = Array.isArray(agentes) ? agentes : [];
  const ids = lista.map(idAgente).filter(Boolean);
  const roles = lista.map(rolDeAgente);
  return { ids, maker: roles.includes('maker'), qa: roles.includes('qa'), total: ids.length };
}

// ---------------------------------------------------------------------------------------------
// Fila y detalle

/** `estado` del servidor («borrador»|«v1»); si falta, se deduce de la versión (≥ 1.0.0 = v1). */
export function estadoDeSkill(s) {
  if (s.estado === 'v1' || s.estado === 'borrador') return s.estado;
  const m = /^(\d+)\./.exec(cad(s.version));
  return m && Number(m[1]) >= 1 ? 'v1' : 'borrador';
}

export function listaDeSkills(datos) {
  if (Array.isArray(datos)) return datos.filter(esObjeto);
  if (esObjeto(datos) && Array.isArray(datos.skills)) return datos.skills.filter(esObjeto);
  return [];
}

/** Un elemento de GET /skills -> fila de vista. */
export function filaSkill(s) {
  const archivos = archivosPresentes(s.archivos);
  const ag = resumenAgentes(s.agentes);
  const lineas = Number.isFinite(s.lineas_skill_md) ? s.lineas_skill_md : null;
  const descripcion = cad(s.descripcion);
  const dod = checklistDoD(s);
  const slug = cad(s.slug);
  return {
    slug,
    etapa: etapaDeSlug(slug) || etapaDeAgentes(ag.ids),
    version: s.version != null ? cad(s.version) : null,
    estado: estadoDeSkill(s),
    descripcion,
    lineas,
    archivos,
    estructuraCompleta: ESTRUCTURA.every((e) => archivos[e.clave]),
    faltan: ESTRUCTURA.filter((e) => !archivos[e.clave]).map((e) => e.etiqueta),
    agentes: ag,
    dod,
    titulo: tituloSkill(slug),
    conteos: conteosArchivos(s.archivos),
    busqueda: plano(`${slug} ${descripcion} ${tituloSkill(slug)}`),
  };
}

function etapaDeAgentes(ids) {
  for (const id of ids) { const e = etapaDeSlug(id); if (e) return e; }
  return null;
}

export function filasSkills(datos) {
  return listaDeSkills(datos).map(filaSkill).sort((a, b) => {
    const ea = a.etapa ? posicionSkill(a.etapa) : 99;
    const eb = b.etapa ? posicionSkill(b.etapa) : 99;
    return ea - eb || a.slug.localeCompare(b.slug);
  });
}

function posicionSkill(id) {
  const i = ETAPAS_FLUJO_SKILL.indexOf(id);
  if (i >= 0) return i;
  const j = ETAPAS_RESTO_SKILL.indexOf(id);
  return j >= 0 ? ETAPAS_FLUJO_SKILL.length + j : 99;
}

/**
 * Checklist del DoD: lo que se puede comprobar mirando los archivos (estructura, límites de tamaño, agentes),
 * lo que dice el servidor en `dod` y los criterios del plan que solo se comprueban corriendo evals o sombras
 * (ok: null = «no comprobable desde los archivos»).
 */
export function checklistDoD(entrada) {
  const s = esObjeto(entrada) ? entrada : {};
  const items = [];
  const archivos = archivosPresentes(s.archivos);
  const faltan = ESTRUCTURA.filter((e) => !archivos[e.clave]).map((e) => e.etiqueta);
  items.push({
    origen: 'archivos', criterio: 'Estructura completa (SKILL.md, references/, rubric.md, templates/, scripts/, evals/, CHANGELOG.md)',
    ok: faltan.length === 0, nota: faltan.length ? `Faltan: ${faltan.join(', ')}` : null,
    corto: 'Tiene todos sus archivos', arreglo: 'Completar los archivos que faltan', explica: 'Instrucciones, material de consulta, criterios de revisión, plantillas, programas de apoyo, casos de prueba e historial de cambios.',
    notaHumana: faltan.length ? `Faltan: ${faltan.map(nombreArchivo).join(', ')}` : null,
  });
  const lineas = Number.isFinite(s.lineas_skill_md) ? s.lineas_skill_md : null;
  items.push({
    origen: 'archivos', criterio: `SKILL.md con menos de ${MAX_LINEAS_SKILL_MD} líneas`,
    ok: lineas == null ? null : lineas < MAX_LINEAS_SKILL_MD, nota: lineas == null ? 'Sin dato de líneas.' : `${lineas} líneas`,
    corto: 'Instrucciones principales cortas', arreglo: 'Acortar las instrucciones principales', explica: `Menos de ${MAX_LINEAS_SKILL_MD} líneas, para que la IA las lea enteras.`,
  });
  const desc = cad(s.descripcion);
  const nDesc = [...desc].length;
  items.push({
    origen: 'archivos', criterio: `description con menos de ${MAX_CARACTERES_DESCRIPCION.toLocaleString('es-ES')} caracteres`,
    ok: desc === '' ? null : nDesc < MAX_CARACTERES_DESCRIPCION, nota: desc === '' ? 'Sin descripción.' : `${nDesc} caracteres`,
    corto: 'Descripción corta', arreglo: 'Acortar la descripción', explica: `Menos de ${MAX_CARACTERES_DESCRIPCION.toLocaleString('es-ES')} caracteres: es lo que usa el sistema para saber cuándo usar esta guía.`,
  });
  const ag = resumenAgentes(s.agentes);
  items.push({
    origen: 'archivos', criterio: 'Agentes definidos: un Maker y un QA independiente',
    ok: ag.maker && ag.qa, nota: ag.total === 0 ? 'Sin agentes en .claude/agents/.' : (ag.maker && ag.qa ? null : `Hay ${ag.ids.join(', ')}; falta ${ag.maker ? 'el QA' : 'el Maker'}.`),
    corto: 'Tiene una IA que prepara y otra que revisa', arreglo: 'Definir la IA que falta', explica: 'La que revisa es independiente: no ve cómo trabajó la primera y nunca aprueba su propio trabajo.',
    notaHumana: ag.total === 0 ? 'Todavía no tiene agentes definidos.' : (ag.maker && ag.qa ? null : `Falta la IA que ${ag.maker ? 'revisa' : 'prepara'}.`),
  });
  items.push({
    origen: 'archivos', criterio: 'Versión congelada (v1.0.0 o superior)', ok: estadoDeSkill(s) === 'v1',
    nota: s.version != null ? `Versión ${cad(s.version)}` : 'Sin versión declarada.',
    corto: 'Dada por terminada (v1)', explica: 'Se da por terminada cuando cumple todo lo anterior y tú la apruebas.',
  });
  const vistos = new Set(items.map((i) => normalizar(i.criterio)));
  const deApi = Array.isArray(s.dod) ? s.dod.filter(esObjeto) : [];
  for (const d of deApi) {
    const c = cad(d.criterio);
    if (!c || vistos.has(normalizar(c))) continue;
    vistos.add(normalizar(c));
    items.push({ origen: 'servidor', criterio: c, ok: d.ok === true ? true : (d.ok === false ? false : null), nota: d.nota != null ? cad(d.nota) : null });
  }
  const textoApi = deApi.map((d) => normalizar(cad(d.criterio))).join(' | ');
  for (const c of CRITERIOS_DOD) {
    if (c.n === 7) continue; // «Forma» ya se comprueba arriba con los archivos
    if (c.n === 11 && !ETAPAS_CON_CUMPLIMIENTO.includes(etapaDeSlug(s.slug))) continue; // «Cumplimiento» solo aplica a D1, D3, D6 y X1
    const clave = normalizar(c.criterio.split(':')[0]);
    if (textoApi.includes(clave)) continue;
    items.push({ origen: 'plan', criterio: c.criterio, ok: null, nota: 'No comprobable desde los archivos: se mide corriendo evals, QA calibrado o corridas en sombra.', innegociable: c.innegociable, n: c.n, corto: CORTO_DOD[c.n] || null, explica: EXPLICA_DOD[c.n] || null });
  }
  return items;
}

function normalizar(t) {
  return cad(t).toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, ' ').trim();
}

export function resumenDoD(items) {
  let ok = 0; let falla = 0; let sinComprobar = 0;
  for (const i of items) { if (i.ok === true) ok += 1; else if (i.ok === false) falla += 1; else sinComprobar += 1; }
  return { ok, falla, sinComprobar, total: items.length };
}

// ---------------------------------------------------------------------------------------------
// Cobertura por etapa y resumen

/**
 * Para cada etapa que debería tener skill: {etapa, nombre, forja, skills:[slug], conSkill, fueraDeAlcance}.
 * `sinSkill` son las etapas del flujo sin ninguna skill (D9 se marca fuera de alcance, no «sin skill»).
 */
export function coberturaPorEtapa(filas) {
  const por = new Map();
  for (const f of filas) { if (f.etapa) { if (!por.has(f.etapa)) por.set(f.etapa, []); por.get(f.etapa).push(f); } }
  const fila = (id) => {
    const skills = por.get(id) || [];
    const forja = (ETAPAS[id] && ETAPAS[id].forja) || (ETAPAS_EMPRESA[id] && ETAPAS_EMPRESA[id].forja) || null;
    return {
      etapa: id, nombre: nombreEtapaSkill(id), forja, skills: skills.map((s) => s.slug),
      estados: skills.map((s) => s.estado), conSkill: skills.length > 0,
      fueraDeAlcance: !!(ETAPAS[id] && ETAPAS[id].opcional),
    };
  };
  const flujo = ETAPAS_FLUJO_SKILL.map(fila);
  const resto = ETAPAS_RESTO_SKILL.map(fila);
  return {
    flujo,
    resto,
    sinSkillFlujo: flujo.filter((f) => !f.conSkill && !f.fueraDeAlcance).map((f) => f.etapa),
    sinSkillResto: resto.filter((f) => !f.conSkill).map((f) => f.etapa),
    sinEtapa: filas.filter((f) => !f.etapa).map((f) => f.slug),
  };
}

export function resumenSkills(filas) {
  const cob = coberturaPorEtapa(filas);
  return {
    total: filas.length,
    v1: filas.filter((f) => f.estado === 'v1').length,
    borradores: filas.filter((f) => f.estado === 'borrador').length,
    estructuraCompleta: filas.filter((f) => f.estructuraCompleta).length,
    etapasFlujoConSkill: cob.flujo.filter((f) => f.conSkill).length,
    etapasFlujoTotal: cob.flujo.filter((f) => !f.fueraDeAlcance).length,
    sinSkillFlujo: cob.sinSkillFlujo,
  };
}

export const FILTROS_VACIOS = Object.freeze({ texto: '', estado: '', soloIncompletas: false });

export function filtrarSkills(filas, filtros = {}) {
  const f = { ...FILTROS_VACIOS, ...filtros };
  const t = plano(String(f.texto || '').trim());
  return filas.filter((r) => {
    if (t && !r.busqueda.includes(t)) return false;
    if (f.estado && r.estado !== f.estado) return false;
    if (f.soloIncompletas && r.estructuraCompleta) return false;
    return true;
  });
}

/** Comandos de solo lectura para mirar una skill desde la terminal (copiables). */
export function comandosSkill(slug) {
  const s = /^[A-Za-z0-9_.-]+$/.test(cad(slug)) ? cad(slug) : null;
  if (!s) return [];
  return [
    { titulo: 'Abrir SKILL.md', comando: `less .claude/skills/${s}/SKILL.md` },
    { titulo: 'Listar la estructura', comando: `ls -R .claude/skills/${s}` },
    { titulo: 'Ver el CHANGELOG', comando: `cat .claude/skills/${s}/CHANGELOG.md` },
  ];
}

export function rutaSkillMd(slug) { return `.claude/skills/${cad(slug)}/SKILL.md`; }

// ---------------------------------------------------------------------------------------------
// Rediseño UX: títulos humanos, camino a v1 («qué le falta») y estado de cobertura por etapa.

/** Título de negocio de cada skill conocida. El slug técnico queda como etiqueta pequeña. */
export const TITULOS_SKILL = {
  'd1-descubrimiento': 'Descubrir candidatos', 'm1-mercados-localizacion': 'Mercado, idioma y moneda', 'd2-validacion': 'Validar la demanda',
  'd3-arquitectura-oferta': 'Armar la oferta', 'd4-producto': 'Producir el producto', 'd5-landing-checkout': 'Página de venta y pago',
  'd6-creativos': 'Anuncios', 'd7-campanas-meta': 'Campaña en Meta', 'x1-compliance': 'Cumplimiento',
  'o0-lanzar-oferta': 'Lanzar una oferta (paso a paso)', 'o0-orquestador-portafolio': 'Coordinador de la cartera',
};
export function tituloSkill(slug) {
  const s = cad(slug);
  if (TITULOS_SKILL[s]) return TITULOS_SKILL[s];
  const sinPrefijo = s.replace(/^(m1|o0|x[12]|f[12]|d(10|[0-9]))[-_]/, '');
  const t = sinPrefijo.replace(/[-_]+/g, ' ').trim();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : s;
}

/** Nombre corto (sin jerga) de cada criterio para darla por terminada (por su número en CRITERIOS_DOD). */
export const CORTO_DOD = {
  1: 'Siempre entrega el formato correcto', 2: 'Los cálculos dan siempre lo mismo', 3: 'Rinde más con la guía que sin ella', 4: 'Resultado estable entre repeticiones',
  5: 'La IA que revisa es confiable', 6: 'Tu aceptación en pruebas en sombra', 7: 'Tamaño y forma', 8: 'Seguridad', 9: 'Costo dentro del tope',
  10: 'Funciona también en otros idiomas', 11: 'Cumplimiento sin falsos aprobados',
};

/** Una frase que explica cada criterio sin jerga (la redacción original queda como detalle técnico). */
export const EXPLICA_DOD = {
  1: 'En todas las pruebas, lo que produce cumple el formato esperado.',
  2: 'Los programas de apoyo tienen pruebas y los ejemplos con números dan diferencia cero.',
  3: 'Con al menos 6 casos de prueba: en cada uno, el resultado con la guía es mejor que sin ella.',
  4: 'Repetida 3 veces con el mismo caso, toma la misma decisión clave en al menos 2 de las 3.',
  5: 'La IA que revisa aprueba todos los casos ejemplares y detecta al menos el 90 % de los errores puestos a propósito.',
  6: 'En al menos 2 de 3 casos, tú usas el resultado sin cambios importantes (el sistema trabaja y tú corriges).',
  7: 'Las instrucciones principales tienen menos de 500 líneas y la descripción menos de 1.024 caracteres.',
  8: 'No se deja engañar por textos con órdenes ocultas, no guarda secretos y toda acción hacia afuera espera una aprobación.',
  9: 'Cada ejecución cuesta menos que el tope y el costo queda anotado.',
  10: 'Un caso en otro idioma sale bien sin tocar la guía.',
  11: 'En las pruebas, la revisión de cumplimiento no deja pasar nada indebido.',
};

/** Hitos que el README de skills exige para pasar de borrador a v1 (nunca se promueve sola). */
export const CAMINO_V1 = [
  { id: 'pulir', titulo: 'Pulir a mano', detalle: 'Corre la etapa con una oferta real y anota cada corrección en Mejoras pendientes hasta que el resultado sea el buscado.' },
  { id: 'retro', titulo: 'Repaso de 30 a 45 minutos', detalle: 'Qué se corrigió, qué se repite y qué pasa a ser una regla de la guía.' },
  { id: 'dod', titulo: 'Criterios para darla por terminada, firmados por ti', detalle: 'Los criterios de listo, comprobados con casos de prueba, una IA que revisa y es confiable, y pruebas en sombra.' },
];

/**
 * Qué le falta a una skill para v1, separado en: `arreglar` (se ve en los archivos y no cumple), `medir` (solo se mide corriendo evals,
 * revisor o sombras) y `cumple`. «Versión congelada» no cuenta: es el resultado, no un requisito.
 */
export function faltaParaV1(fila) {
  const items = (fila && Array.isArray(fila.dod) ? fila.dod : []).filter((i) => !/^versi[oó]n congelada/i.test(cad(i.criterio)));
  const arreglar = items.filter((i) => i.ok === false);
  const medir = items.filter((i) => i.ok === null || i.ok === undefined);
  const cumple = items.filter((i) => i.ok === true);
  const innegociablesPorMedir = medir.filter((i) => i.innegociable).length;
  const congelada = fila && fila.estado === 'v1';
  let siguiente;
  if (congelada) siguiente = 'Terminada (v1): cambiarla exige tu aprobación.';
  else if (arreglar.length) siguiente = `Arreglar primero: ${arreglar.slice(0, 2).map((i) => { const nombre = i.arreglo || i.corto || i.criterio.split(':')[0].replace(/\s*\(.*$/, ''); const nota = i.notaHumana || i.nota; return nota ? `${nombre} (${nota.replace(/\.$/, '')})` : nombre; }).join('; ')}${arreglar.length > 2 ? ` y ${arreglar.length - 2} más` : ''}.`;
  else if (medir.length) siguiente = `Pulirla a mano y medir ${medir.length} criterios (${innegociablesPorMedir} innegociables).`;
  else siguiente = 'Lista para que la des por terminada (v1).';
  return {
    arreglar, medir, cumple, innegociablesPorMedir, congelada, siguiente,
    total: items.length, bpCumple: items.length === 0 ? 0 : Math.round((cumple.length * 10000) / items.length),
  };
}

/** Estado de una celda de cobertura: sin_skill · borrador · v1 · fuera_alcance. Con varias skills manda la menos avanzada. */
export function estadoCobertura(celda) {
  if (!celda) return 'sin_skill';
  if (celda.fueraDeAlcance && !celda.conSkill) return 'fuera_alcance';
  if (!celda.conSkill) return 'sin_skill';
  return (celda.estados || []).every((e) => e === 'v1') ? 'v1' : 'borrador';
}

/** Resumen para las métricas: cuántas skills por estado y cuántas etapas del flujo siguen sin skill. */
export function resumenCobertura(filas) {
  const cob = coberturaPorEtapa(filas);
  const celdas = [...cob.flujo, ...cob.resto];
  return {
    ...cob,
    conSkill: celdas.filter((c) => c.conSkill).length,
    sinSkillTotal: celdas.filter((c) => !c.conSkill && !c.fueraDeAlcance).length,
    celdas,
  };
}

/**
 * Resumen de una descripción larga para tarjetas: quita etiquetas del tipo «[v0.1 sin pulir]», reúne frases hasta pasar de ~90 caracteres
 * (una frase muy corta como «Mercados, idiomas y monedas (M1).» no basta sola) y corta en `max` con «…».
 */
export function primeraFrase(t, max = 170) {
  let s = cad(t).replace(/\s+/g, ' ').trim().replace(/^(\[[^\]]{0,40}\]\s*)+/, '').replace(/^v0\.\d sin pulir\.\s*/i, '');
  if (!s) return '';
  const frases = s.match(/[^.!?]+[.!?]+(?=\s|$)/g);
  let acc = '';
  if (frases) {
    for (const f of frases) { acc = `${acc} ${f.trim()}`.trim(); if ([...acc].length >= 90) break; }
  }
  if (!acc) acc = s;
  if ([...acc].length <= max) return acc;
  const corte = [...acc].slice(0, max).join('');
  return `${corte.slice(0, corte.lastIndexOf(' ') > 40 ? corte.lastIndexOf(' ') : corte.length).replace(/[,;:(\s]+$/, '')}…`;
}

/** Cantidad de elementos de cada parte de la estructura cuando el servidor la manda como número o lista (`references: 14`); null si solo sabe si existe. */
export function conteosArchivos(archivos) {
  const out = {};
  for (const e of ESTRUCTURA) out[e.clave] = null;
  if (esObjeto(archivos)) {
    for (const [k, v] of Object.entries(archivos)) {
      const c = claveArchivo(k);
      if (!(c in out)) continue;
      if (typeof v === 'number' && Number.isFinite(v)) out[c] = v;
      else if (Array.isArray(v)) out[c] = v.length;
      else if (esObjeto(v) && Number.isFinite(v.n)) out[c] = v.n;
    }
  }
  return out;
}

/** Nombre humano de una etapa de skill: los 11 del flujo en lenguaje de negocio; las de empresa con su nombre. */
export function nombreHumanoEtapaSkill(id) {
  const humanos = { D1: 'Descubrir', M1: 'Mercado', D2: 'Validar', D3: 'Oferta', D4: 'Producto', D5: 'Página de venta y pago', D6: 'Anuncios', D7: 'Campaña', D8: 'Operación', D9: 'Escalado', D10: 'Después de la venta' };
  return humanos[id] || nombreEtapaSkill(id);
}
