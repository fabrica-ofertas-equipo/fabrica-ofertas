// atajos.js — atajos de teclado del panel, lógica PURA (sin DOM): Ctrl/⌘+K abre la paleta, `/` también, `?` la ayuda de atajos y `g` + letra salta de pantalla.
// `crearAtajos().procesar(ev, ahora)` recibe un evento tipo KeyboardEvent ({key, ctrlKey, metaKey, altKey, shiftKey, target}) y devuelve la acción o null.

/**
 * letra → ruta. «g» y luego la letra (en 1,2 s). Reglas: una sola letra a-z, distinta de «g» (es el prefijo), una letra por pantalla y ninguna repetida;
 * el alias `oferta` (detalle) no tiene letra propia: resalta y se abre con la de Ofertas. Documentadas en la ayuda `?`.
 * Las 14 originales no cambian (memoria muscular); las 9 de las piezas nuevas usan letras libres con una regla mnemotécnica entre paréntesis.
 */
export const ATAJOS_IR = {
  // las 14 pantallas originales
  r: 'resumen', o: 'ofertas', d: 'descubrimiento', l: 'landing', c: 'campanas', e: 'operacion', f: 'finanzas',
  a: 'agentes', u: 'cumplimiento', p: 'parametros', s: 'skills', b: 'pulido', h: 'registro', t: 'sistema',
  // las 9 nuevas
  m: 'cerebro', //        (m)emoria
  n: 'fabrica', //        (n)oche: el turno nocturno de producción
  x: 'poscompra', //      e(x)tras tras el pago
  j: 'jurado', //         (j)urado
  w: 'robots', //         (w)orkers: los robots
  v: 'avisos', //         a(v)isos
  y: 'pagos', //          pa(y): cobros
  i: 'paises', //         pa(í)ses
  q: 'quien-decide', //   (q)uién decide qué
  k: 'tareas', //        chec(k)list: la lista de tareas de todo el negocio
  z: 'negocio', //       la última letra libre: el tablero del negocio (ganancia, retorno y costo por venta por oferta)
};

/** ruta → letra del atajo (inverso de ATAJOS_IR). */
export function atajoDeRuta(ruta, mapa = ATAJOS_IR) {
  for (const [letra, r] of Object.entries(mapa)) if (r === ruta) return letra;
  return null;
}

/** ¿El evento viene de un campo donde se escribe? (input, textarea, select, contenteditable): ahí los atajos de una letra no se activan. */
export function esCampoEditable(objetivo) {
  if (!objetivo) return false;
  const tag = String(objetivo.tagName || '').toUpperCase();
  if (tag === 'TEXTAREA' || tag === 'SELECT') return true;
  if (tag === 'INPUT') return !['checkbox', 'radio', 'button', 'submit', 'reset'].includes(String(objetivo.type || '').toLowerCase());
  return Boolean(objetivo.isContentEditable) || objetivo.contentEditable === 'true';
}

/**
 * Máquina de estados del prefijo `g`. Devuelve acciones: {tipo:'paleta'} · {tipo:'ayuda'} · {tipo:'prefijo'} (se pulsó `g`) · {tipo:'ir', ruta, letra}.
 * `ventanaMs`: tiempo máximo entre `g` y la letra. `bloqueado()` (opcional): true si hay un modal abierto (los atajos de una letra se ignoran).
 */
export function crearAtajos({ mapa = ATAJOS_IR, ventanaMs = 1200, bloqueado = () => false } = {}) {
  let t0 = null;
  return {
    procesar(ev, ahora = Date.now()) {
      if (!ev || typeof ev.key !== 'string') return null;
      const tecla = ev.key;
      const mod = Boolean(ev.ctrlKey || ev.metaKey);
      if (mod && !ev.altKey && tecla.toLowerCase() === 'k') { t0 = null; return { tipo: 'paleta' }; }
      if (mod || ev.altKey) { t0 = null; return null; }
      if (esCampoEditable(ev.target) || bloqueado()) { t0 = null; return null; }
      if (tecla === '/' ) { t0 = null; return { tipo: 'paleta' }; }
      if (tecla === '?') { t0 = null; return { tipo: 'ayuda' }; }
      if (ev.shiftKey) { t0 = null; return null; }
      const k = tecla.toLowerCase();
      if (t0 !== null && ahora - t0 <= ventanaMs) {
        t0 = null;
        if (Object.prototype.hasOwnProperty.call(mapa, k)) return { tipo: 'ir', ruta: mapa[k], letra: k };
        if (k !== 'g') return null;
      }
      if (k === 'g') { t0 = ahora; return { tipo: 'prefijo' }; }
      t0 = null;
      return null;
    },
    pendiente(ahora = Date.now()) { return t0 !== null && ahora - t0 <= ventanaMs; },
    reiniciar() { t0 = null; },
  };
}
