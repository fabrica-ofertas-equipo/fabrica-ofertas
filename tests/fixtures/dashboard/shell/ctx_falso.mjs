// ctx_falso.mjs — API y `ctx` falsos para probar las páginas del panel sin servidor ni navegador.
// La API falsa sirve los sobres de tests/fixtures/dashboard/shell/api/*.json (los mismos que la maqueta) y registra las llamadas.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const AQUI = dirname(fileURLToPath(import.meta.url));
export const RUTA_API = join(AQUI, 'api');

export const cargarSobre = (nombre) => JSON.parse(readFileSync(join(RUTA_API, `${nombre}.json`), 'utf8'));

export class ErrorApiFalso extends Error {
  constructor(codigo, mensaje) { super(mensaje); this.name = 'ErrorApi'; this.codigo = codigo; this.mensaje = mensaje; }
}

/** Filtra el registro como lo hace el servidor: oferta/etapa/agente, `desde` (n >= desde) y `limite` (cola si no hay desde). */
export function filtrarRegistro(sobre, params = {}, extra = []) {
  const d = sobre.datos;
  let lineas = [...d.lineas, ...extra];
  lineas = lineas.filter((l) => (!params.oferta || l.oferta_id === params.oferta) && (!params.etapa || l.etapa === params.etapa) && (!params.agente || l.agente === params.agente));
  const limite = Number(params.limite || 200);
  const sel = params.desde === undefined ? lineas.slice(-limite) : lineas.filter((l) => l.n >= Number(params.desde)).slice(0, limite);
  return { ...sobre, datos: { lineas: sel, total: lineas.length, siguiente: sel.length ? sel[sel.length - 1].n + 1 : (params.desde ?? 1), cadena_ok: d.cadena_ok } };
}

/**
 * overrides: {'/ruta': sobre | Error | (params) => sobre}. Por defecto: sistema, ofertas, registro, finanzas, parametros, acciones.
 * `api.llamadas` guarda [{metodo, ruta, params|cuerpo}].
 */
export function crearApiFalsa(overrides = {}) {
  const base = {
    '/sistema': cargarSobre('sistema'), '/ofertas': cargarSobre('ofertas'), '/finanzas': cargarSobre('finanzas'),
    '/parametros': cargarSobre('parametros'), '/acciones': cargarSobre('acciones'), '/registro': (p) => filtrarRegistro(cargarSobre('registro'), p, api.extraRegistro),
  };
  const rutas = { ...base, ...overrides };
  const api = {
    llamadas: [], extraRegistro: [],
    async sobre(ruta, params) {
      api.llamadas.push({ metodo: 'GET', ruta, params });
      let r = rutas[ruta];
      if (r === undefined && ruta.startsWith('/job/')) r = rutas['/job'];
      if (typeof r === 'function') r = r(params, ruta);
      if (r === undefined) throw new ErrorApiFalso('no_existe', `Ruta de API desconocida: ${ruta}`);
      if (r instanceof Error) throw r;
      const { ok: _ok, ...resto } = r;
      return { datos: null, fuente: [], generado_en: null, vacio: false, avisos: [], ...resto };
    },
    async get(ruta, params) { return (await api.sobre(ruta, params)).datos; },
    async post(ruta, cuerpo) {
      api.llamadas.push({ metodo: 'POST', ruta, cuerpo });
      const r = rutas[`POST ${ruta}`];
      if (r === undefined) throw new ErrorApiFalso('no_existe', `POST desconocido: ${ruta}`);
      if (r instanceof Error) throw r;
      return typeof r === 'function' ? r(cuerpo) : r;
    },
    postsA(ruta) { return api.llamadas.filter((l) => l.metodo === 'POST' && l.ruta === ruta); },
  };
  return api;
}

/** ctx como lo arma app.js. `ui` y `fmt` se pasan desde la prueba (ya con el DOM falso instalado). */
export function crearCtx({ api, ui, ruta, params = {}, estado = {}, paginas = {}, titulos = {} }) {
  const salidas = [];
  const navegaciones = [];
  const st = { ofertaActiva: null, conectado: 'sse', ofertas: [], sistema: null, tema: 'auto', sidebarColapsada: false, ...estado };
  const ctx = {
    api, ui, fmt: ui.fmt, params, estado: st, ruta,
    navegar: (h) => navegaciones.push(h), recargar: () => navegaciones.push('recargar'),
    alSalir: (fn) => salidas.push(fn), pausarTodo: () => navegaciones.push('pausarTodo'),
    paginas: () => paginas, titulos: () => titulos,
    _navegaciones: navegaciones, _salir: () => { for (const f of salidas.splice(0)) f(); },
  };
  return ctx;
}

export const dormir = (ms) => new Promise((r) => setTimeout(r, ms));
