// glosario-indice.js — junta el glosario base con los fragmentos que cada página aporte en `lib/glosario-<pagina>.js`.
//
// Cada fragmento exporta `TERMINOS = { clave: { nombre?, corto, largo?, tecnico? } }`. Se importan con TOLERANCIA: si el archivo no existe
// (404), no se puede evaluar o no exporta `TERMINOS`, se ignora sin ruido. En conflicto de claves manda `glosario.js` (el global); las colisiones entre
// fragmentos se anotan en `CONFLICTOS` ({clave, origen, ganador}) y gana el primero en el orden de FRAGMENTOS (la fusión es determinista).
//
// `GLOSARIO_TOTAL` es un objeto VIVO: empieza con el glosario base y se completa cuando llegan los fragmentos (este módulo espera a que
// terminen, con tope de 2,5 s, antes de resolver su top-level await). `buscarTermino` lo consulta siempre en el momento de usarlo.

import { GLOSARIO } from './glosario.js';

// Uno por grupo de pantallas (resumen · ofertas · descubrimiento · operacion · robots · piezas · decisiones · tareas · ausencia). Si una pantalla nueva trae su
// `glosario-<nombre>.js`, se agrega el nombre aquí; si el archivo no existe, se ignora sin ruido.
export const FRAGMENTOS = ['resumen', 'ofertas', 'descubrimiento', 'operacion', 'robots', 'piezas', 'decisiones', 'tareas', 'ausencia'];

export const GLOSARIO_TOTAL = { ...GLOSARIO };
/** Claves repetidas: {clave, origen (el fragmento que quedó fuera), ganador ('global' o el fragmento que ya la tenía)}. */
export const CONFLICTOS = [];
export const CARGADOS = [];
/** clave → quién la aportó ('global' si viene de glosario.js, que no figura aquí). */
export const ORIGENES = {};

/** ¿Es una entrada válida de glosario? (corto obligatorio, texto). */
export function entradaValida(e) {
  return Boolean(e) && typeof e === 'object' && typeof e.corto === 'string' && e.corto.trim() !== '';
}

/**
 * Mezcla un objeto TERMINOS en `destino` sin pisar claves existentes: el global (glosario.js) manda sobre todos los fragmentos y, entre fragmentos,
 * gana el que se mezcla primero. Una clave repetida se descarta y se anota en `conflictos` con su ganador. Mezclar dos veces el mismo origen es
 * inocuo (no cuenta como conflicto). Devuelve las claves añadidas.
 */
export function mezclarTerminos(destino, terminos, origen = 'fragmento', conflictos = CONFLICTOS, origenes = ORIGENES) {
  const anadidas = [];
  if (!terminos || typeof terminos !== 'object') return anadidas;
  for (const [clave, def] of Object.entries(terminos)) {
    if (!/^[a-z0-9_]{1,60}$/.test(clave) || !entradaValida(def)) continue;
    if (Object.prototype.hasOwnProperty.call(destino, clave)) {
      const ganador = Object.prototype.hasOwnProperty.call(origenes, clave) ? origenes[clave] : 'global';
      if (ganador !== origen) conflictos.push({ clave, origen, ganador });
      continue;
    }
    destino[clave] = { nombre: def.nombre, corto: def.corto, largo: def.largo, tecnico: def.tecnico };
    origenes[clave] = origen;
    anadidas.push(clave);
  }
  return anadidas;
}

/**
 * Fusiona fragmentos YA importados, en el orden dado (determinista: no depende de qué importación termine antes).
 * fragmentos: [{nombre, terminos}]. Devuelve [{nombre, claves}] (cuántas claves aportó cada uno).
 */
export function fusionarFragmentos(destino, fragmentos, conflictos = CONFLICTOS, origenes = ORIGENES) {
  return (Array.isArray(fragmentos) ? fragmentos : []).filter(Boolean).map((f) => ({ nombre: f.nombre, claves: mezclarTerminos(destino, f.terminos, f.nombre, conflictos, origenes).length }));
}

/** Término del glosario o null. */
export function buscarTermino(clave, glosario = GLOSARIO_TOTAL) {
  if (typeof clave !== 'string' || !Object.prototype.hasOwnProperty.call(glosario, clave)) return null;
  return glosario[clave];
}

/** Nombre humano de una clave sin entrada: «hash_config» → «hash config». */
export function humanizarClave(clave) {
  const t = String(clave ?? '').replace(/[_-]+/g, ' ').trim();
  return t ? t.charAt(0).toUpperCase() + t.slice(1) : '';
}

async function importarFragmento(nombre) {
  try {
    const mod = await import(`./glosario-${nombre}.js`);
    return { nombre, terminos: mod && mod.TERMINOS };
  } catch (_) { return null; /* no existe todavía o no se pudo evaluar: se ignora */ }
}

async function cargarTodos() {
  const importados = await Promise.all(FRAGMENTOS.map(importarFragmento)); // en paralelo, pero se fusionan en el orden de FRAGMENTOS
  CONFLICTOS.length = 0;
  CARGADOS.length = 0;
  CARGADOS.push(...fusionarFragmentos(GLOSARIO_TOTAL, importados));
}

/** Vuelve a leer los fragmentos (la galería y las pruebas lo usan). Es idempotente. */
export function recargarFragmentos() { return cargarTodos(); }

let reloj = null;
const tope = new Promise((resolver) => { reloj = setTimeout(resolver, 2500); if (reloj && typeof reloj.unref === 'function') reloj.unref(); });
await Promise.race([cargarTodos(), tope]);
if (reloj !== null) clearTimeout(reloj);

export default GLOSARIO_TOTAL;
