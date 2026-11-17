// api.js — cliente del panel (CONTRATO §4-§5). Solo `fetch` y la biblioteca estándar del navegador; sin dependencias.
//
//   api.get(ruta, params?)      → Promise<datos>        (ruta SIN /api: '/sistema', '/oferta/OF-202611-01'; lanza ErrorApi)
//   api.getSobre(ruta, params?) → Promise<{datos, demo, fuente, avisos, vacio, generado_en}>   (el sobre completo, para mostrar «fuente» y «leído a las»;
//                                  `demo` = true si el servidor marcó la respuesta como datos de demostración). `api.sobre` es el mismo método (alias anterior).
//   api.post(ruta, cuerpo)      → Promise<datos>
//   api.conectarEventos(onEvento, onEstado?) → {cerrar()}
//        onEvento({tipo:'empresa|oferta|registro|skills|barrido|sondeo', ruta, ts})   (SSE `cambio`; 'sondeo' = pulso de 5 s si SSE no está)
//        onEstado('sse'|'sondeo'|'sin_conexion')                                      (indicador EN VIVO)
//   api.token()                 → token de sesión (de `#t=` en la URL → sessionStorage; se quita de la barra)
//
// `vacio`: cuando la fuente no existe, el servidor responde ok con `vacio:true`; `get` devuelve entonces `datos` tal cual
// (puede ser null/[]/{}), y `sobre` deja ver `fuente` (qué archivo se esperaba) para armar el estado vacío.
// ErrorApi{codigo, mensaje, estado}: `sin_conexion`, `token_invalido`, `respuesta_invalida`, `tiempo_agotado` o el código del servidor.

export class ErrorApi extends Error {
  constructor(codigo, mensaje, extra = {}) {
    super(mensaje);
    this.name = 'ErrorApi';
    this.codigo = codigo;
    this.mensaje = mensaje;
    this.estado = extra.estado ?? null; // HTTP
    this.sobre = extra.sobre ?? null;
  }
}

const CLAVE_TOKEN = 'panel.token';
const RE_TOKEN = /(?:^#|[?&])t=([A-Za-z0-9._~%-]{8,256})/;

/** Extrae el token de un fragmento de URL (`#t=…`, también `#/ruta&t=…`). null si no hay. */
export function tokenDeHash(hash) {
  const m = RE_TOKEN.exec(String(hash || ''));
  if (!m) return null;
  try { return decodeURIComponent(m[1]); } catch (_) { return null; }
}

/** Quita `t=` del fragmento y devuelve el resto ('' si no queda nada). */
export function hashSinToken(hash) {
  let h = String(hash || '');
  h = h.replace(/^#t=[^&]*&?/, '#').replace(/([?&])t=[^&]*&?/, '$1');
  h = h.replace(/[?&]$/, '');
  return h === '#' ? '' : h;
}

/** Construye `/api<ruta>?a=b` ignorando parámetros null/undefined/''. */
export function construirUrl(ruta, params, base = '/api') {
  let r = String(ruta || '');
  if (!r.startsWith('/')) r = '/' + r;
  const q = [];
  for (const [k, v] of Object.entries(params || {})) {
    if (v === null || v === undefined || v === '') continue;
    q.push(`${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  }
  return base + r + (q.length ? '?' + q.join('&') : '');
}

/** Parser incremental de `text/event-stream`. `push(texto)` devuelve los eventos completos {evento, datos(string), id}. */
export class ParserSSE {
  constructor() { this.resto = ''; this.evento = ''; this.datos = []; this.id = null; }
  push(texto) {
    this.resto += texto;
    const salida = [];
    let pos;
    while ((pos = this.resto.search(/\r\n|\n|\r/)) !== -1) {
      const m = /\r\n|\n|\r/.exec(this.resto);
      const linea = this.resto.slice(0, m.index);
      this.resto = this.resto.slice(m.index + m[0].length);
      if (linea === '') {
        if (this.datos.length || this.evento) {
          salida.push({ evento: this.evento || 'message', datos: this.datos.join('\n'), id: this.id });
        }
        this.evento = ''; this.datos = [];
        continue;
      }
      if (linea.startsWith(':')) continue;
      const i = linea.indexOf(':');
      const campo = i === -1 ? linea : linea.slice(0, i);
      let valor = i === -1 ? '' : linea.slice(i + 1);
      if (valor.startsWith(' ')) valor = valor.slice(1);
      if (campo === 'event') this.evento = valor;
      else if (campo === 'data') this.datos.push(valor);
      else if (campo === 'id') this.id = valor;
    }
    return salida;
  }
}

// La clave se guarda en la pestaña (sessionStorage) Y en este navegador (localStorage). Pedido del dueño (13-nov): el panel corre con
// clave fija (`--clave-fija`) y lo abre desde un marcador o un acceso directo, que guardan la dirección SIN `#t=` (se quita de la barra
// al entrar). Con la clave recordada, cualquier `http://127.0.0.1:8790/` abre sin pedirla. Solo vale para ese origen local; si la clave
// cambia, la dirección completa nueva la reemplaza.
function almacenSesion() {
  const pila = [];
  try { if (typeof sessionStorage !== 'undefined') pila.push(sessionStorage); } catch (_) { /* denegado */ }
  try { if (typeof localStorage !== 'undefined') pila.push(localStorage); } catch (_) { /* denegado */ }
  if (!pila.length) return null;
  return {
    getItem(k) { for (const a of pila) { try { const v = a.getItem(k); if (v) return v; } catch (_) { /* sigue */ } } return null; },
    setItem(k, v) { for (const a of pila) { try { a.setItem(k, v); } catch (_) { /* sigue */ } } },
  };
}

/** Fábrica (las pruebas inyectan fetch/almacén falsos; el panel usa `api`). */
export function crearApi({ fetchFn, almacen, base = '/api', tiempoMs = 20000, intervaloSondeoMs = 5000, reintentoSseMs = 30000, silencioMaxMs = 45000, esperaBaseMs = 1000 } = {}) {
  const sesion = almacen === undefined ? almacenSesion() : almacen;
  let tokenMem = null;
  const hacerFetch = (...a) => (fetchFn || globalThis.fetch)(...a);

  function token() {
    if (tokenMem) return tokenMem;
    try { tokenMem = sesion ? sesion.getItem(CLAVE_TOKEN) : null; } catch (_) { tokenMem = null; }
    return tokenMem;
  }
  function fijarToken(t) {
    tokenMem = t || null;
    try { if (sesion && t) sesion.setItem(CLAVE_TOKEN, t); } catch (_) { /* sin persistencia */ }
  }
  /** Lee `#t=` de la URL, lo guarda y lo quita de la barra. Devuelve el token vigente (o null). */
  function iniciarToken(ubicacion = globalThis.location, historial = globalThis.history) {
    if (ubicacion) {
      const t = tokenDeHash(ubicacion.hash);
      if (t) {
        fijarToken(t);
        try {
          const nuevo = hashSinToken(ubicacion.hash);
          historial.replaceState(null, '', ubicacion.pathname + (ubicacion.search || '') + nuevo);
        } catch (_) { /* sin history */ }
      }
    }
    return token();
  }

  async function pedir(metodo, ruta, params, cuerpo) {
    const url = construirUrl(ruta, params, base);
    const cab = { Accept: 'application/json' };
    const t = token();
    if (t) cab['X-Panel-Token'] = t;
    const init = { method: metodo, headers: cab, cache: 'no-store', credentials: 'omit' };
    if (cuerpo !== undefined) { cab['Content-Type'] = 'application/json'; init.body = JSON.stringify(cuerpo); }
    const ctl = typeof AbortController !== 'undefined' ? new AbortController() : null;
    let venció = false;
    const reloj = ctl ? setTimeout(() => { venció = true; ctl.abort(); }, tiempoMs) : null;
    if (ctl) init.signal = ctl.signal;
    let res;
    try {
      res = await hacerFetch(url, init);
    } catch (err) {
      if (venció) throw new ErrorApi('tiempo_agotado', 'El panel tardó demasiado en responder.');
      throw new ErrorApi('sin_conexion', 'No se pudo conectar con el panel local. ¿Sigue corriendo `python -m dashboard`?');
    } finally {
      if (reloj) clearTimeout(reloj);
    }
    let sobre = null;
    try { sobre = await res.json(); } catch (_) { sobre = null; }
    if (!sobre || typeof sobre !== 'object') {
      if (res.status === 401 || res.status === 403) throw new ErrorApi('token_invalido', 'Sesión no válida: abre de nuevo la URL que imprime `python -m dashboard`.', { estado: res.status });
      throw new ErrorApi('respuesta_invalida', `Respuesta no válida del panel (HTTP ${res.status}).`, { estado: res.status });
    }
    if (!res.ok || sobre.ok === false) {
      const e = sobre.error || {};
      let codigo = typeof e.codigo === 'string' ? e.codigo : `http_${res.status}`;
      if ((res.status === 401 || res.status === 403) && !e.codigo) codigo = 'token_invalido';
      throw new ErrorApi(codigo, typeof e.mensaje === 'string' ? e.mensaje : `Error HTTP ${res.status}.`, { estado: res.status, sobre });
    }
    return {
      datos: sobre.datos === undefined ? null : sobre.datos,
      fuente: Array.isArray(sobre.fuente) ? sobre.fuente : [],
      generado_en: sobre.generado_en || null,
      vacio: sobre.vacio === true,
      avisos: Array.isArray(sobre.avisos) ? sobre.avisos : [],
      demo: sobre.demo === true, // el servidor lo añade en algunas rutas: los datos salen de la oferta demo (ofertas/_ejemplo)
    };
  }

  const get = async (ruta, params) => (await pedir('GET', ruta, params)).datos;
  const sobre = (ruta, params) => pedir('GET', ruta, params);
  const getSobre = sobre; // alias con el nombre que piden las pantallas: {datos, demo, fuente, avisos, vacio, generado_en}
  const post = async (ruta, cuerpo) => (await pedir('POST', ruta, null, cuerpo === undefined ? {} : cuerpo)).datos;

  /** SSE sobre fetch (EventSource no permite la cabecera X-Panel-Token), con reintento y caída a sondeo cada 5 s. */
  function conectarEventos(onEvento, onEstado) {
    let cerrado = false;
    let actual = null;
    let ctl = null;
    let temporizadorSondeo = null;
    let temporizadorReintento = null;
    let fallos = 0;
    let modo = 'sin_conexion';
    let vigilante = null;
    let lectorActual = null;

    const avisar = (m) => { if (m !== modo) { modo = m; try { onEstado && onEstado(m); } catch (e) { console.error(e); } } };
    const emitir = (ev) => { try { onEvento && onEvento(ev); } catch (e) { console.error(e); } };

    async function sondear() {
      if (cerrado || modo === 'sse') return;
      try {
        await pedir('GET', '/sistema');
        if (modo !== 'sse') avisar('sondeo');
        emitir({ tipo: 'sondeo', ruta: '', ts: new Date().toISOString() });
      } catch (err) {
        if (err.codigo === 'sin_conexion' || err.codigo === 'tiempo_agotado') avisar('sin_conexion');
        else avisar('sondeo'); // el servidor responde (p. ej. 403): hay conexión, no sesión
      }
    }
    function iniciarSondeo() {
      if (temporizadorSondeo || cerrado) return;
      sondear();
      temporizadorSondeo = setInterval(sondear, intervaloSondeoMs);
    }
    function detenerSondeo() { if (temporizadorSondeo) { clearInterval(temporizadorSondeo); temporizadorSondeo = null; } }
    function programar(ms) {
      if (cerrado) return;
      clearTimeout(temporizadorReintento);
      temporizadorReintento = setTimeout(abrir, ms);
    }

    async function abrir() {
      if (cerrado) return;
      ctl = typeof AbortController !== 'undefined' ? new AbortController() : null;
      const cab = { Accept: 'text/event-stream' };
      const t = token();
      if (t) cab['X-Panel-Token'] = t;
      try {
        const res = await hacerFetch(base + '/eventos', { headers: cab, cache: 'no-store', credentials: 'omit', signal: ctl ? ctl.signal : undefined });
        if (!res.ok || !res.body) throw new ErrorApi('http_' + res.status, 'SSE no disponible', { estado: res.status });
        fallos = 0;
        detenerSondeo();
        avisar('sse');
        const lector = res.body.getReader();
        lectorActual = lector;
        const dec = new TextDecoder();
        const parser = new ParserSSE();
        const rearmar = () => {
          clearTimeout(vigilante);
          vigilante = setTimeout(() => { try { ctl && ctl.abort(); } catch (_) { /* nada */ } }, silencioMaxMs);
        };
        rearmar();
        for (;;) {
          const { value, done } = await lector.read();
          if (done) break;
          rearmar();
          const texto = typeof value === 'string' ? value : dec.decode(value, { stream: true });
          for (const ev of parser.push(texto)) {
            if (ev.evento !== 'cambio') continue; // 'ping' solo mantiene viva la conexión
            let d = null;
            try { d = JSON.parse(ev.datos); } catch (_) { d = null; }
            if (d && typeof d === 'object') emitir(d);
          }
        }
      } catch (err) {
        if (cerrado) return;
      } finally {
        clearTimeout(vigilante);
      }
      if (cerrado) return;
      fallos += 1;
      if (modo === 'sse') avisar('sin_conexion');
      if (fallos >= 2) {
        iniciarSondeo();
        programar(reintentoSseMs);
      } else {
        programar(Math.min(esperaBaseMs * 2 ** fallos, 8000));
      }
    }

    abrir();
    actual = {
      cerrar() {
        cerrado = true;
        detenerSondeo();
        clearTimeout(temporizadorReintento);
        clearTimeout(vigilante);
        try { ctl && ctl.abort(); } catch (_) { /* nada */ }
        try { lectorActual && lectorActual.cancel(); } catch (_) { /* nada */ }
      },
    };
    return actual;
  }

  return { get, sobre, getSobre, post, conectarEventos, token, iniciarToken, fijarToken };
}

export const api = crearApi();
export default api;
