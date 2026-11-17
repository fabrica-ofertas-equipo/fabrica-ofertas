// estado.js — estado global mínimo del panel (CONTRATO §5). Sin dependencias; funciona también en Node (pruebas).
//
// Campos:
//   ofertaActiva      string|null   oferta elegida en la barra superior (persistida)
//   tema              'auto'|'claro'|'oscuro'  (persistido; 'auto' sigue prefers-color-scheme)
//   sidebarColapsada  boolean       sidebar de 232 px (false) o 56 px (true) (persistido)
//   modoTecnico       boolean       «Detalle técnico»: abre rutas, huellas, comandos y JSON crudo en todas las pantallas (persistido en `fab.modoTecnico`, por defecto apagado)
//   densidad          'comoda'|'compacta'  altura de filas y espaciado (persistido en `fab.densidad`, por defecto cómoda)
//   conectado         'sse'|'sondeo'|'sin_conexion'   estado del indicador EN VIVO
//   sistema           objeto|null   último GET /sistema (pausa, freno_captura, infra…)
//   ofertas           array         último GET /ofertas (para selector y contadores)
//
// Uso:  import { estado, suscribir } from './estado.js';
//       const baja = estado.suscribir((e, cambios) => …);   // idéntico a suscribir(fn)
//       estado.fijar({ tema: 'oscuro' });                    // notifica solo si algo cambió
//       estado.ofertaActiva                                  // lectura directa

const CLAVES_PERSISTENTES = ['ofertaActiva', 'tema', 'sidebarColapsada', 'modoTecnico', 'densidad'];
const PREFIJO = 'panel.';
/** Claves de localStorage: las históricas llevan `panel.`; las del rediseño (U0) usan `fab.` tal como fija la especificación. */
export const CLAVES_ALMACEN = { modoTecnico: 'fab.modoTecnico', densidad: 'fab.densidad' };
export const claveAlmacen = (clave) => CLAVES_ALMACEN[clave] || PREFIJO + clave;
const TEMAS = ['auto', 'claro', 'oscuro'];
export const DENSIDADES = ['comoda', 'compacta'];
const CONEXIONES = ['sse', 'sondeo', 'sin_conexion'];

function almacenPorDefecto() {
  try {
    if (typeof localStorage !== 'undefined' && localStorage) return localStorage;
  } catch (_) { /* acceso denegado: sin persistencia */ }
  return null;
}

function leerPersistido(almacen) {
  const salida = {};
  if (!almacen) return salida;
  for (const clave of CLAVES_PERSISTENTES) {
    try {
      const crudo = almacen.getItem(claveAlmacen(clave));
      if (crudo === null || crudo === undefined) continue;
      try { salida[clave] = JSON.parse(crudo); }
      catch (e) {
        // `fab.*` también se acepta sin comillas (`true`, `compacta`) por si se edita a mano en las herramientas del navegador
        if (clave === 'modoTecnico' || clave === 'densidad') salida[clave] = String(crudo).trim();
      }
    } catch (_) { /* valor corrupto: se ignora */ }
  }
  return salida;
}

/** Normaliza un parche: descarta valores de tipo/dominio inválido (nunca lanza). */
export function sanearParche(parche) {
  const limpio = {};
  if (!parche || typeof parche !== 'object') return limpio;
  for (const [clave, valor] of Object.entries(parche)) {
    switch (clave) {
      case 'ofertaActiva':
        if (valor === null || (typeof valor === 'string' && valor.length <= 80)) limpio[clave] = valor || null;
        break;
      case 'tema':
        if (TEMAS.includes(valor)) limpio[clave] = valor;
        break;
      case 'sidebarColapsada':
        limpio[clave] = Boolean(valor);
        break;
      case 'modoTecnico':
        limpio[clave] = valor === true || valor === 'true' || valor === 1;
        break;
      case 'densidad':
        if (DENSIDADES.includes(valor)) limpio[clave] = valor;
        break;
      case 'conectado':
        if (CONEXIONES.includes(valor)) limpio[clave] = valor;
        break;
      case 'sistema':
        if (valor === null || typeof valor === 'object') limpio[clave] = valor;
        break;
      case 'ofertas':
        if (Array.isArray(valor)) limpio[clave] = valor;
        break;
      default:
        break; // claves desconocidas: se ignoran (estado mínimo)
    }
  }
  return limpio;
}

/** Crea una instancia de estado (la del panel es `estado`; las pruebas crean la suya con un almacén falso). */
export function crearEstado(almacen = almacenPorDefecto()) {
  const datos = {
    ofertaActiva: null,
    tema: 'auto',
    sidebarColapsada: false,
    modoTecnico: false,
    densidad: 'comoda',
    conectado: 'sin_conexion',
    sistema: null,
    ofertas: [],
    ...sanearParche(leerPersistido(almacen)),
  };
  const oyentes = new Set();

  const api = {
    /** Copia superficial de los valores actuales. */
    leer() { return { ...datos }; },
    /** Aplica un parche; devuelve las claves que cambiaron. Notifica a los suscriptores. */
    fijar(parche) {
      const limpio = sanearParche(parche);
      const cambios = [];
      for (const [clave, valor] of Object.entries(limpio)) {
        if (datos[clave] === valor) continue;
        datos[clave] = valor;
        cambios.push(clave);
        if (almacen && CLAVES_PERSISTENTES.includes(clave)) {
          try { almacen.setItem(claveAlmacen(clave), JSON.stringify(valor)); } catch (_) { /* cuota/privado */ }
        }
      }
      if (cambios.length) {
        for (const fn of [...oyentes]) {
          try { fn(api, cambios); } catch (err) { console.error('suscriptor de estado falló', err); }
        }
      }
      return cambios;
    },
    /** fn(estado, clavesCambiadas) en cada cambio. Devuelve la función para darse de baja. */
    suscribir(fn) {
      if (typeof fn !== 'function') throw new TypeError('suscribir exige una función');
      oyentes.add(fn);
      return () => oyentes.delete(fn);
    },
  };
  for (const clave of Object.keys(datos)) {
    Object.defineProperty(api, clave, { get: () => datos[clave], enumerable: true });
  }
  return api;
}

export const estado = crearEstado();
export const suscribir = (fn) => estado.suscribir(fn);
export const fijar = (parche) => estado.fijar(parche);
export default estado;
