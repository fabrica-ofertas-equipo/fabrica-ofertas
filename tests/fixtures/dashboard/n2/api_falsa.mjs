// api_falsa.mjs — API de solo lectura falsa para probar Fábrica, Jurado, Países y Poscompra sin servidor ni red.
// Reproduce el sobre de dashboard/api_ofertas.py: /ofertas, /oferta/<id>, /oferta/<id>/archivo?ruta=, /operacion/<id> y /skills.
// Un archivo que no está en `archivos` responde «vacío» (datos null), igual que el servidor real.
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

export const fx = (nombre) => JSON.parse(readFileSync(fileURLToPath(new URL(nombre, import.meta.url)), 'utf8'));
export const AHORA = '2026-11-14T10:00:00Z';

/** Detalle de /oferta/<id> a partir de los fixtures de la oferta demo. */
export function detalleDemo({ gatePendiente = false, conPaquete = true, mercado = fx('mercado.json'), d6Estado = 'aprobado', qa = ['qa/d6-v1.json', 'qa/x1-d6-v1.json'] } = {}) {
  const arte = conPaquete ? [{ ruta: '06-creativos/paquete.json', tipo: 'json', bytes: 9342, mtime: '2026-11-13T22:00:00Z' }, { ruta: '06-creativos/assets/c01-hueco_img_h1_v1.png', tipo: 'imagen', bytes: 250, mtime: '2026-11-13T22:00:00Z' }] : [];
  const etapas = ['M1', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10'].map((id) => ({
    id, nombre: id, estado: id === 'D6' ? d6Estado : 'aprobado', gate: id === 'D6' ? 'S' : 'H', gate_pendiente: id === 'D6' ? gatePendiente : false, obsoleta: false,
    artefactos: id === 'D6' ? arte : [], qa: id === 'D6' ? qa.map((a) => ({ archivo: a, veredicto: 'PASS', resumen: '' })) : [],
  }));
  return { estado: { oferta_id: 'OF-202611-01' }, etapas, mercado, brief: null };
}

/**
 * @param {{ofertas?:any[], detalles?:Record<string,any>, archivos?:Record<string,string>, operacion?:Record<string,any>, skills?:any[]|null, falla?:Record<string,boolean>, imagen?:string}} cfg
 * `archivos`: clave `<id>|<ruta>` → texto. `imagen`: data-URL que se devuelve para cualquier .png.
 */
export function apiFalsa({ ofertas = [], detalles = {}, archivos = {}, operacion = {}, skills = [], falla = {}, imagen = null } = {}) {
  const llamadas = [];
  const env = (datos, fuente = [], vacio = false) => ({ datos, fuente, generado_en: AHORA, vacio, avisos: [], demo: false });
  const api = {
    sobre: async (ruta, params = {}) => {
      llamadas.push(params && params.ruta ? `${ruta}?ruta=${params.ruta}` : ruta);
      if (falla[ruta]) throw Object.assign(new Error('x'), { codigo: 'fallo', mensaje: `falló ${ruta}` });
      if (ruta === '/ofertas') return ofertas.length ? env(ofertas, ['ofertas/*/estado.json']) : env([], ['ofertas/*/estado.json'], true);
      if (ruta === '/skills') { if (skills === null) throw Object.assign(new Error('x'), { codigo: 'fallo', mensaje: 'sin skills' }); return env(skills, ['.claude/skills']); }
      let m = /^\/operacion\/([^/]+)$/.exec(ruta);
      if (m) return operacion[m[1]] ? env(operacion[m[1]], [`ofertas/${m[1]}/08-operacion`]) : env({ kpi_dia: [], decisiones: [], ordenes: [], veredicto: null, postcompra: { entregas: [], reembolsos: [], senal_pausa: null }, kpi_blended: null }, [], true);
      m = /^\/oferta\/([^/]+)\/archivo$/.exec(ruta);
      if (m) {
        const id = decodeURIComponent(m[1]);
        if (!detalles[id]) throw Object.assign(new Error('x'), { codigo: 'oferta_no_encontrada', mensaje: 'No existe esa oferta.' });
        const clave = `${id}|${params.ruta}`;
        if (/\.png$/.test(params.ruta || '') && imagen) return env({ ruta: params.ruta, tipo: 'imagen', contenido: imagen, truncado: false, bytes: 250, mtime: AHORA });
        if (!(clave in archivos)) return env(null, [`ofertas/${id}/${params.ruta}`], true);
        return env({ ruta: params.ruta, tipo: 'json', contenido: archivos[clave], truncado: false, bytes: archivos[clave].length, mtime: AHORA }, [`ofertas/${id}/${params.ruta}`]);
      }
      m = /^\/oferta\/([^/]+)$/.exec(ruta);
      if (m) {
        const id = decodeURIComponent(m[1]);
        if (!detalles[id]) throw Object.assign(new Error('x'), { codigo: 'oferta_no_encontrada', mensaje: 'No existe esa oferta.' });
        return env(detalles[id], [`ofertas/${id}/estado.json`]);
      }
      throw Object.assign(new Error('x'), { codigo: 'ruta_no_encontrada', mensaje: `ruta ${ruta}` });
    },
  };
  return { api, llamadas };
}

export const OFERTA_DEMO = { oferta_id: '_ejemplo', oferta_id_estado: 'OF-202611-01', familia_id: 'FAM-202611-01', demo: true, fase: 'en_construccion', nivel: 'N2' };
export const OFERTA_REAL = { oferta_id: 'OF-202701-02', oferta_id_estado: 'OF-202701-02', familia_id: 'FAM-202611-01', demo: false, fase: 'borrador', nivel: 'N2' };

/** ctx mínimo de una página. */
export function ctxDe(ui, fmt, api, { activa = null, ofertas = [] } = {}) {
  return { api, ui, fmt, estado: { ofertas, ofertaActiva: activa }, params: {}, ruta: 'x', recargar() {}, navegar() {}, alSalir() {} };
}
