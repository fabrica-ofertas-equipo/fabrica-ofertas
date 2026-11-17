// lib/campanas-oferta-vista.js — dibujo de «Campañas en Meta» y «Línea de tiempo del presupuesto» en la ficha de cada oferta.
// La lógica (árbol, veredicto, carriles, renglones) está en ./campanas-oferta.js; acá solo DOM. Pide GET /api/meta?oferta=<id>[&desde&hasta].
// 2.ª versión (dueño, 16-nov): «se mezclan los tres» → cada nivel con su ícono (campaña, conjunto) y los anuncios con su miniatura;
// veredicto de rentabilidad por fila; el presupuesto en carriles (uno por campaña) en vez de líneas encimadas; filtros en una barra.

import { arbol, totalArbol, series, carriles, veredicto, estadoCampana, renglones, resumenAutores, rolTexto, tonoRoasAov, UMBRAL, horaEn, medianoches } from './campanas-oferta.js';
import { estadoTexto } from './meta-admin.js';
import { numero, usd, roas } from './negocio.js';

export const CSS_CAMPANAS_OFERTA = `
.co-barra { display: flex; flex-wrap: wrap; gap: 10px 22px; align-items: flex-end; padding: 10px 12px; margin: 0 0 12px; background: var(--sup-2); border: 1px solid var(--borde); border-radius: var(--r-2, 8px); }
.co-grupo { display: flex; flex-direction: column; gap: 5px; }
.co-grupo__t { font-size: 11px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; color: var(--txt-3); }
.co-barra__der { margin-left: auto; display: flex; gap: 8px; align-items: center; }
.co-leyenda-niveles { display: flex; gap: 14px; flex-wrap: wrap; font-size: 12.5px; color: var(--txt-2); }
.co-leyenda-niveles > span { display: inline-flex; align-items: center; gap: 6px; }

.co-tabla-caja { overflow-x: auto; border: 1px solid var(--borde); border-radius: var(--r-2, 8px); }
.co-tabla { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 13px; font-variant-numeric: tabular-nums; }
.co-tabla th { position: sticky; top: 0; z-index: 1; background: var(--sup-2); color: var(--txt-3); font-size: 11.5px; font-weight: 600; text-align: right; padding: 8px 10px; white-space: nowrap; border-bottom: 1px solid var(--borde); }
.co-tabla th:first-child, .co-tabla td:first-child { text-align: left; }
.co-tabla td { padding: 7px 10px; text-align: right; white-space: nowrap; border-bottom: 1px solid var(--borde); vertical-align: middle; }
.co-tabla tr.co-camp td { background: var(--sup-2); border-top: 10px solid var(--bg); }
.co-tabla tr.co-camp td:first-child { box-shadow: inset 4px 0 0 var(--co-borde, var(--neutro)); }
.co-tabla tr.co-conj td:first-child { padding-left: 34px; }
.co-tabla tr.co-ad td:first-child { padding-left: 62px; }
.co-tabla tr.co-conj td:first-child, .co-tabla tr.co-ad td:first-child { box-shadow: inset 4px 0 0 var(--co-borde, var(--neutro)); }
.co-tabla tr.co-ad td { color: var(--txt-2); }
.co-tabla tr.co-ad:hover td, .co-tabla tr.co-conj:hover td { background: var(--fila, var(--sup)); }
.co-tabla tr.co-apagado td:not(:first-child) { opacity: .55; }
.co-tabla tr.co-total td { background: var(--bg); font-weight: 700; border-bottom: 2px solid var(--borde-fuerte, var(--borde)); }
.co-ent { display: flex; align-items: center; gap: 10px; min-width: 280px; max-width: 480px; }
.co-ent__txt { display: flex; flex-direction: column; min-width: 0; gap: 2px; }
.co-ent__t { font-weight: 600; overflow: hidden; text-overflow: ellipsis; color: var(--txt); }
.co-ad .co-ent__t { font-weight: 500; }
.co-ent__sub { font-size: 11.5px; color: var(--txt-3); display: flex; gap: 6px; align-items: center; flex-wrap: wrap; white-space: normal; }
.co-icono { flex: none; width: 30px; height: 30px; border-radius: 8px; display: inline-grid; place-items: center; }
.co-icono--camp { background: var(--acento-bg); color: var(--acento); border: 1px solid var(--acento-borde); }
.co-icono--conj { background: var(--info-bg); color: var(--info); border: 1px solid var(--info-borde); width: 26px; height: 26px; }
.co-mini { flex: none; width: 42px; height: 42px; border-radius: 7px; overflow: hidden; display: inline-grid; place-items: center; background: var(--neutro-bg); border: 1px solid var(--borde); color: var(--txt-3); }
.co-mini img { width: 100%; height: 100%; object-fit: cover; display: block; }
.co-toggle { flex: none; border: 1px solid var(--borde-fuerte, var(--borde)); background: var(--sup); cursor: pointer; color: var(--txt); width: 24px; height: 24px; border-radius: 6px; padding: 0; display: inline-grid; place-items: center; }
.co-toggle svg { transition: transform .15s; }
.co-toggle[aria-expanded="true"] svg { transform: rotate(90deg); }
.co-toggle:hover { color: var(--txt); }
.co-toggle--vacio { visibility: hidden; }
.co-punto { width: 7px; height: 7px; border-radius: 50%; display: inline-block; background: var(--neutro); }
.co-punto--on { background: var(--ok); }
.co-rol { font-size: 11px; font-weight: 600; padding: 1px 7px; border-radius: 999px; background: var(--acento-bg); color: var(--acento); border: 1px solid var(--acento-borde); }
.co-pill { display: inline-flex; align-items: center; font-size: 11.5px; font-weight: 700; padding: 2px 9px; border-radius: 999px; border: 1px solid var(--borde); }
.co-pill--ok { background: var(--ok-bg); color: var(--ok); border-color: var(--ok-borde); }
.co-pill--aviso { background: var(--aviso-bg); color: var(--aviso); border-color: var(--aviso-borde); }
.co-pill--error { background: var(--error-bg); color: var(--error); border-color: var(--error-borde); }
.co-pill--neutro { background: var(--neutro-bg); color: var(--txt-3); }
.co-roas { font-weight: 700; }
.co-roas--ok { color: var(--ok); } .co-roas--aviso { color: var(--aviso); } .co-roas--error { color: var(--error); }
.co-dec { font-size: 11.5px; color: var(--txt-2); cursor: help; }
.co-dec b { color: var(--txt); }
.co-dec--accion b { color: var(--ok); } .co-dec--freno b { color: var(--aviso); }
.co-nota { color: var(--txt-3); font-size: 12.5px; margin: 8px 0 0; }
.co-tabla tr.co-grupo-apagadas td { background: var(--bg); border-top: 10px solid var(--bg); padding: 8px 10px; text-align: left; }
.co-apagadas-btn { display: inline-flex; align-items: center; gap: 8px; border: 1px dashed var(--borde-fuerte, var(--borde)); background: var(--sup); color: var(--txt-2); border-radius: 8px; padding: 6px 12px; cursor: pointer; font: inherit; font-weight: 600; }
.co-apagadas-btn:hover { color: var(--txt); }
.co-apagadas-btn .co-toggle { border: 0; background: none; width: 14px; height: 14px; }

.co-tl { display: grid; grid-template-columns: minmax(180px, 260px) 1fr; column-gap: 14px; margin: 6px 0 4px; }
.co-tl__lbls { display: flex; flex-direction: column; gap: 12px; padding-top: 44px; }
.co-carril__lbl { height: 64px; display: flex; flex-direction: column; justify-content: center; gap: 1px; min-width: 0; }
.co-carril__lbl b { font-size: 13px; }
.co-carril__lbl span { font-size: 11.5px; color: var(--txt-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.co-carril__lbl .co-carril__hoy { font-size: 14px; font-weight: 700; color: var(--txt); }
.co-carril__nom { display: flex; align-items: center; gap: 6px; min-width: 0; }
.co-carril__nom b { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.co-est { flex: none; display: inline-flex; align-items: center; gap: 4px; font-size: 10.5px !important; font-weight: 700; padding: 1px 7px 1px 5px; border-radius: 999px; border: 1px solid var(--borde); cursor: help; white-space: nowrap; }
.co-est svg { flex: none; }
.co-est--ok { background: var(--ok-bg); color: var(--ok) !important; border-color: var(--ok-borde); }
.co-est--info { background: var(--info-bg); color: var(--info) !important; border-color: var(--info-borde); }
.co-est--aviso { background: var(--aviso-bg); color: var(--aviso) !important; border-color: var(--aviso-borde); }
.co-est--error { background: var(--error-bg); color: var(--error) !important; border-color: var(--error-borde); }
.co-est--neutro { background: var(--neutro-bg); color: var(--txt-3) !important; }
.co-est__vivo { width: 7px; height: 7px; border-radius: 50%; background: currentColor; box-shadow: 0 0 0 0 currentColor; animation: co-latido 1.6s infinite; }
@keyframes co-latido { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, currentColor 60%, transparent); } 70% { box-shadow: 0 0 0 5px transparent; } 100% { box-shadow: 0 0 0 0 transparent; } }
@media (prefers-reduced-motion: reduce) { .co-est__vivo { animation: none; } }
.co-carril__lbl .co-carril__razon { font-size: 11px; line-height: 1.25; color: var(--txt-3); cursor: help; white-space: normal; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.co-carril__razon--neutro { color: var(--txt-2) !important; }
.co-carril__razon--error { color: var(--error) !important; }
.co-carril__razon--aviso { color: var(--aviso) !important; }
.co-carril__razon--info { color: var(--info) !important; }
.co-vivo-nota { display: inline-flex; align-items: center; gap: 6px; font-size: 11.5px; color: var(--txt-2); }
.co-vivo-nota .co-est__vivo { color: var(--ok); }
.co-tl__eje-lbl { height: 16px; font-size: 10.5px; font-weight: 700; color: var(--txt-3); text-transform: uppercase; letter-spacing: .03em; display: flex; align-items: center; justify-content: flex-end; }
.co-tl__eje-lbl--mercado { color: var(--acento); }
.co-pistas { position: relative; padding-top: 44px; }
.co-rejilla { position: absolute; left: 0; right: 0; top: 40px; bottom: 36px; pointer-events: none; z-index: 2; }
.co-rejilla i { position: absolute; top: 0; bottom: 0; width: 0; border-left: 1px solid color-mix(in srgb, var(--txt-3) 45%, transparent); }
.co-rejilla i.co-menor { border-left: 1px dashed color-mix(in srgb, var(--txt-3) 22%, transparent); }
.co-rejilla i.co-medianoche { border-left: 2px solid var(--txt-3); }
.co-rejilla i.co-medianoche-m { border-left: 2px dashed var(--acento); }
.co-rejilla i.co-ahora { border-left: 2px solid var(--error); }
.co-rotulos { position: absolute; left: 0; right: 0; top: 0; height: 40px; }
.co-rotulos span { position: absolute; transform: translateX(-50%); font-size: 10.5px; font-weight: 700; white-space: nowrap; padding: 1px 6px; border-radius: 999px; top: 2px; }
.co-rotulos .co-rot-art { background: var(--neutro-bg); color: var(--txt-2); border: 1px solid var(--borde); }
.co-rotulos .co-rot-mer { background: var(--acento-bg); color: var(--acento); border: 1px solid var(--acento-borde); top: 20px; }
.co-rotulos span.co-izq { transform: none; }
.co-rotulos span.co-der { transform: translateX(-100%); }
.co-rotulos .co-rot-ahora { background: var(--error-bg); color: var(--error); border: 1px solid var(--error-borde); }
.co-pistas__filas { display: flex; flex-direction: column; gap: 12px; position: relative; }
.co-carril { position: relative; height: 64px; background: color-mix(in srgb, var(--neutro-bg) 70%, transparent); border-radius: 7px; }
.co-tramo { position: absolute; top: 5px; bottom: 5px; border-radius: 5px; background: color-mix(in srgb, var(--acento) var(--co-int, 60%), var(--sup-2)); border-right: 2px solid var(--sup); display: grid; place-items: center; overflow: hidden; }
.co-tramo span { font-size: 12px; font-weight: 800; color: var(--txt); white-space: nowrap; }
.co-marca { position: absolute; top: -10px; width: 20px; height: 20px; margin-left: -10px; border-radius: 50%; display: grid; place-items: center; font-size: 9px; font-weight: 900; color: #fff; background: var(--neutro); border: 2.5px solid var(--sup); box-shadow: 0 0 0 1px var(--sup); cursor: help; z-index: 5; }
.co-marca--sube { background: var(--ok); }
.co-marca--baja { background: var(--error); }
.co-marca--inicio { background: var(--txt-3); }
.co-marca--sistema { border-color: var(--acento); }
.co-marca--a_mano { border-color: var(--aviso); }
.co-item__t--sube { color: var(--ok); } .co-item__t--baja { color: var(--error); }
.co-eje { position: relative; height: 16px; margin-top: 4px; }
.co-eje span { position: absolute; transform: translateX(-50%); font-size: 10.5px; color: var(--txt-3); white-space: nowrap; font-variant-numeric: tabular-nums; }
.co-eje--mercado span { color: var(--acento); font-weight: 600; }
.co-cursor { position: absolute; top: 44px; bottom: 36px; width: 0; border-left: 1px solid var(--txt-2); pointer-events: none; display: none; z-index: 4; }
.co-cursor span { position: absolute; top: -26px; left: 6px; white-space: nowrap; font-size: 11px; font-weight: 700; background: var(--sup); border: 1px solid var(--borde-fuerte, var(--borde)); border-radius: 6px; padding: 2px 7px; color: var(--txt); box-shadow: 0 2px 8px rgba(0,0,0,.25); }
.co-claves { display: flex; flex-wrap: wrap; gap: 6px 16px; font-size: 12px; color: var(--txt-2); margin: 2px 0 10px; align-items: center; }
.co-claves > span { display: inline-flex; align-items: center; gap: 6px; }
.co-claves .co-marca { position: static; margin: 0; width: 18px; height: 18px; font-size: 8px; box-shadow: none; }
.co-claves i { display: inline-block; width: 0; height: 14px; }
.co-hora-m { color: var(--acento); font-weight: 600; }
.co-resumen { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 10px; }
.co-dia { font-size: 12px; font-weight: 700; color: var(--txt-3); text-transform: uppercase; letter-spacing: .04em; margin: 16px 0 4px; }
.co-lista { list-style: none; margin: 0; padding: 0; border-left: 2px solid var(--borde); }
.co-item { position: relative; padding: 7px 0 9px 18px; }
.co-item::before { content: ''; position: absolute; left: -7px; top: 12px; width: 12px; height: 12px; border-radius: 50%; background: var(--sup); border: 2px solid var(--neutro); }
.co-item--acento::before { border-color: var(--acento); background: var(--acento); }
.co-item--aviso::before { border-color: var(--aviso); background: var(--aviso); }
.co-item--ok::before { border-color: var(--ok); }
.co-item--error::before { border-color: var(--error); background: var(--error-bg); }
.co-item__cab { display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: baseline; }
.co-item__t { font-weight: 600; }
.co-item__meta { color: var(--txt-3); font-size: 12px; }
.co-item__det { color: var(--txt-2); font-size: 12.5px; margin-top: 3px; max-width: 900px; }
.co-quien { font-size: 11px; font-weight: 700; padding: 1px 7px; border-radius: 999px; border: 1px solid var(--borde); }
.co-quien--aviso { background: var(--aviso-bg); border-color: var(--aviso-borde); color: var(--aviso); }
.co-quien--acento { background: var(--acento-bg); border-color: var(--acento-borde); color: var(--acento); }
.co-quien--ok { background: var(--ok-bg); border-color: var(--ok-borde); color: var(--ok); }
.co-quien--error { background: var(--error-bg); border-color: var(--error-borde); color: var(--error); }
.co-quien--neutro { background: var(--neutro-bg); color: var(--txt-2); }
.co-mas { margin-top: 8px; }
`;

const ZONA = 'America/Argentina/Buenos_Aires';
const fechaHora = (iso) => {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '—' : d.toLocaleString('es-AR', { timeZone: ZONA, day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false });
};
const hora = (iso) => new Date(iso).toLocaleTimeString('es-AR', { timeZone: ZONA, hour: '2-digit', minute: '2-digit', hour12: false });
const dia = (iso) => new Date(iso).toLocaleDateString('es-AR', { timeZone: ZONA, weekday: 'long', day: 'numeric', month: 'long' });
const ejeTxt = (t, conDia) => new Date(t).toLocaleString('es-AR', { timeZone: ZONA, ...(conDia ? { day: '2-digit', month: '2-digit' } : {}), hour: '2-digit', minute: '2-digit', hour12: false });
const pct = (x, d = 1) => (typeof x === 'number' && Number.isFinite(x) ? `${numero(x, d)} %` : '—');
const usdC = (x) => (typeof x === 'number' && Number.isFinite(x) ? usd(x) : '—');
const TONO_BORDE = { ok: 'var(--ok)', aviso: 'var(--aviso)', error: 'var(--error)', neutro: 'var(--neutro)' };

// Miniaturas: las baja nube_sync a ofertas/_funnels/_miniaturas/ y se piden de a una (el panel no carga imágenes de afuera).
const MINIS = new Map();
const RX_IMG = /^data:image\/(jpeg|png|webp|gif);base64,[A-Za-z0-9+/=]+$/;
function miniatura(ctx, a) {
  const { ui } = ctx;
  const caja = ui.el('span', { class: 'co-mini' }, ui.icono('pantalla', { tam: 16 }));
  if (!a.miniatura || !ctx.api || typeof ctx.api.sobre !== 'function') return caja;
  const poner = (src) => {
    if (!src || !RX_IMG.test(src)) return;
    const img = ui.el('img', { alt: '', loading: 'lazy' });
    img.src = src;
    ui.reemplazar(caja, img);
  };
  const prev = MINIS.get(a.miniatura);
  if (typeof prev === 'string') { poner(prev); return caja; }
  const p = prev || ctx.api.sobre('/negocio/documento', { ruta: a.miniatura }).then((r) => (r && r.datos && r.datos.contenido) || '').catch(() => '');
  MINIS.set(a.miniatura, p);
  p.then((src) => { MINIS.set(a.miniatura, src); try { poner(src); } catch (_) { /* sin DOM */ } });
  return caja;
}

function pill(ui, v) {
  return ui.el('span', { class: ['co-pill', `co-pill--${v.tono}`], title: v.porque || null }, v.texto);
}
function celdaRoasAov(ui, x) {
  const t = tonoRoasAov(x);
  return t ? ui.el('span', { class: ['co-roas', `co-roas--${t}`] }, roas(x)) : '—';
}
function lineaDecision(ui, u) {
  if (!u) return null;
  const accion = ['SURFEAR', 'SUBIR_24H', 'BAJAR'].includes(u.decision);
  const freno = ['NO_GASTA', 'TARDE', 'CONGELADA', 'EN_TEST'].includes(u.decision);
  return ui.el('span', { class: ['co-dec', accion ? 'co-dec--accion' : freno ? 'co-dec--freno' : null], title: u.porque || '' },
    'Escala: ', ui.el('b', null, `${u.texto}${accion && u.nuevo ? ` → ${usd(u.nuevo)}` : ''}`), ` · ${hora(u.cuando)}`);
}

/** Tabla tipo Administrador de anuncios: campaña ▸ conjunto ▸ anuncio, cada nivel con su ícono y los anuncios con su miniatura. */
function tablaArbol(ctx, camps, aov) {
  const { ui } = ctx;
  const { el } = ui;
  const abiertos = new Set(camps.filter((c) => c.activo).map((c) => c.id));
  const estado = { verApagadas: false };
  const activas = camps.filter((c) => c.activo);
  const apagadas = camps.filter((c) => !c.activo);
  const cuerpo = el('tbody');
  const cols = ['Campaña · conjunto · anuncio', 'Resultado', 'Presupuesto', 'Gasto', 'Compras', 'CPA', 'ROAS con AOV', 'ROAS Meta', 'Pagos inic.', 'CTR', 'CPM'];
  const toggle = (id, n) => (n ? el('button', {
    type: 'button', class: 'co-toggle', 'aria-expanded': String(abiertos.has(id)), 'aria-label': abiertos.has(id) ? 'Cerrar' : 'Abrir',
    onclick: () => { if (abiertos.has(id)) abiertos.delete(id); else abiertos.add(id); pintar(); },
  }, ui.el('svg', { viewBox: '0 0 16 16', width: 12, height: 12, 'aria-hidden': 'true' }, ui.el('path', { d: 'M6 3l5 5-5 5', fill: 'none', stroke: 'currentColor', 'stroke-width': 2.2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }))) : el('span', { class: 'co-toggle co-toggle--vacio' }));
  const numeros = (f) => [
    el('td', null, usdC(f.gasto_usd)), el('td', null, numero(f.compras_meta, 0)), el('td', null, usdC(f.cpa)),
    el('td', null, celdaRoasAov(ui, f.roas_aov)), el('td', null, typeof f.roas === 'number' ? roas(f.roas) : '—'),
    el('td', null, numero(f.inicios_pago_meta, 0)), el('td', null, pct(f.ctr, 2)), el('td', null, usdC(f.cpm))];
  const apagado = (f) => (!f.activo && !(f.gasto_usd > 0) ? 'co-apagado' : null);
  const filaCamp = (c, v) => {
    const nAds = c.hijos.reduce((s, x) => s + x.hijos.length, 0);
    return el('tr', { class: ['co-camp', apagado(c)], style: { '--co-borde': TONO_BORDE[v.tono] } },
      el('td', null, el('div', { class: 'co-ent' }, toggle(c.id, c.hijos.length),
        el('span', { class: 'co-icono co-icono--camp', title: 'Campaña' }, ui.icono('megafono', { tam: 16 })),
        el('div', { class: 'co-ent__txt' },
          el('span', { class: 'co-ent__t', title: c.nombre }, c.nombre),
          el('span', { class: 'co-ent__sub' }, el('span', { class: ['co-punto', c.activo ? 'co-punto--on' : null] }), estadoTexto(c.estado),
            rolTexto(c.rol) ? el('span', { class: 'co-rol' }, rolTexto(c.rol)) : null,
            `${c.hijos.length} conjunto${c.hijos.length === 1 ? '' : 's'} · ${nAds} anuncio${nAds === 1 ? '' : 's'}`),
          lineaDecision(ui, c.ultima)))),
      el('td', null, pill(ui, v)),
      el('td', null, typeof c.presupuesto === 'number' ? el('b', null, `${usd(c.presupuesto)}/día`) : '—'),
      ...numeros(c));
  };
  const filaConj = (s, borde) => el('tr', { class: ['co-conj', apagado(s)], style: { '--co-borde': borde } },
    el('td', null, el('div', { class: 'co-ent' }, toggle(s.id, s.hijos.length),
      el('span', { class: 'co-icono co-icono--conj', title: 'Conjunto de anuncios' }, ui.icono('carpeta', { tam: 14 })),
      el('div', { class: 'co-ent__txt' },
        el('span', { class: 'co-ent__t', title: s.nombre }, s.nombre),
        el('span', { class: 'co-ent__sub' }, el('span', { class: ['co-punto', s.activo ? 'co-punto--on' : null] }), `Conjunto · ${estadoTexto(s.estado).toLowerCase()} · ${s.hijos.length} anuncio${s.hijos.length === 1 ? '' : 's'}`)))),
    el('td', null, pill(ui, veredicto(s, aov))), el('td'), ...numeros(s));
  const filaAd = (a, borde) => el('tr', { class: ['co-ad', apagado(a)], style: { '--co-borde': borde } },
    el('td', null, el('div', { class: 'co-ent' }, miniatura(ctx, a),
      el('div', { class: 'co-ent__txt' },
        el('span', { class: 'co-ent__t', title: a.nombre }, a.nombre),
        el('span', { class: 'co-ent__sub' }, el('span', { class: ['co-punto', a.activo ? 'co-punto--on' : null] }), `Anuncio · ${estadoTexto(a.estado).toLowerCase()}${a.video ? ' · video' : ''}`)))),
    el('td', null, pill(ui, veredicto(a, aov))), el('td'), ...numeros(a));
  const pintarCamp = (c) => {
    const v = veredicto(c, aov);
    const borde = TONO_BORDE[v.tono];
    cuerpo.appendChild(filaCamp(c, v));
    if (!abiertos.has(c.id)) return;
    for (const sj of c.hijos) {
      cuerpo.appendChild(filaConj(sj, borde));
      if (abiertos.has(sj.id)) for (const a of sj.hijos) cuerpo.appendChild(filaAd(a, borde));
    }
  };
  const pintar = () => {
    ui.limpiar(cuerpo);
    const t = totalArbol(camps, aov);
    cuerpo.appendChild(el('tr', { class: 'co-total' },
      el('td', null, `Total de la oferta · ${activas.length} activa${activas.length === 1 ? '' : 's'}${apagadas.length ? ` + ${apagadas.length} apagada${apagadas.length === 1 ? '' : 's'}` : ''}`),
      el('td', null, pill(ui, veredicto({ ...t, nivel: 'campana' }, aov))),
      el('td', null, `${usd(activas.reduce((s, c) => s + (c.presupuesto || 0), 0))}/día`),
      ...numeros(t)));
    activas.forEach(pintarCamp);
    if (!activas.length) cuerpo.appendChild(el('tr', null, el('td', { colspan: cols.length, class: 'co-nota' }, 'Ninguna campaña activa en esta oferta.')));
    if (apagadas.length) {
      const gasto = apagadas.reduce((s, c) => s + (c.gasto_usd || 0), 0);
      cuerpo.appendChild(el('tr', { class: 'co-grupo-apagadas' }, el('td', { colspan: cols.length },
        el('button', { type: 'button', class: 'co-apagadas-btn', 'aria-expanded': String(estado.verApagadas), onclick: () => { estado.verApagadas = !estado.verApagadas; pintar(); } },
          el('span', { class: 'co-toggle' }, ui.el('svg', { viewBox: '0 0 16 16', width: 12, height: 12, 'aria-hidden': 'true', style: { transform: estado.verApagadas ? 'rotate(90deg)' : null } }, ui.el('path', { d: 'M6 3l5 5-5 5', fill: 'none', stroke: 'currentColor', 'stroke-width': 2.2, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }))),
          ui.icono('pausa', { tam: 14 }),
          `${apagadas.length} campaña${apagadas.length === 1 ? '' : 's'} apagada${apagadas.length === 1 ? '' : 's'} (${estado.verApagadas ? 'tocá para ocultar' : `oculta${apagadas.length === 1 ? '' : 's'}: tocá para ver${apagadas.length === 1 ? 'la' : 'las'}`})`,
          gasto > 0 ? el('span', { class: 'co-nota', style: { margin: 0 } }, ` · gastaron ${usd(gasto)} en el período`) : null))));
      if (estado.verApagadas) apagadas.forEach(pintarCamp);
    }
  };
  pintar();
  const todos = () => [...camps.map((c) => c.id), ...camps.flatMap((c) => c.hijos.map((x) => x.id))];
  const barra = el('div', { class: 'co-barra' },
    el('div', { class: 'co-grupo' }, el('span', { class: 'co-grupo__t' }, 'Cómo leer la tabla'),
      el('div', { class: 'co-leyenda-niveles' },
        el('span', null, el('span', { class: 'co-icono co-icono--camp' }, ui.icono('megafono', { tam: 14 })), 'Campaña'),
        el('span', null, el('span', { class: 'co-icono co-icono--conj' }, ui.icono('carpeta', { tam: 13 })), 'Conjunto'),
        el('span', null, el('span', { class: 'co-mini', style: { width: '26px', height: '26px' } }, ui.icono('pantalla', { tam: 13 })), 'Anuncio'),
        el('span', null, pill(ui, { texto: 'Rentable', tono: 'ok' }), `ROAS con AOV ≥ ${numero(UMBRAL.surf, 1)}`),
        el('span', null, pill(ui, { texto: 'Justo', tono: 'aviso' }), `${numero(UMBRAL.bajar, 1)} a ${numero(UMBRAL.surf, 1)}`),
        el('span', null, pill(ui, { texto: 'Pierde', tono: 'error' }), `bajo ${numero(UMBRAL.bajar, 1)}`))),
    el('div', { class: 'co-barra__der' },
      el('button', { type: 'button', class: 'boton boton--chico', onclick: () => { todos().forEach((id) => abiertos.add(id)); pintar(); } }, 'Abrir todo'),
      el('button', { type: 'button', class: 'boton boton--chico', onclick: () => { abiertos.clear(); pintar(); } }, 'Cerrar todo')));
  return el('div', null, barra, el('div', { class: 'co-tabla-caja' }, el('table', { class: 'co-tabla' },
    el('thead', null, el('tr', null, ...cols.map((c) => el('th', null, c)))), cuerpo)));
}

// ───────── estado de cada campaña, en vivo (dueño, 17-nov: «cuando dice apagada, que diga la razón en tiempo real… y que los estados sean dinámicos») ─────────
const svgIco = (ui, d) => ui.el('svg', { viewBox: '0 0 16 16', width: 11, height: 11, 'aria-hidden': 'true' }, ...d.map((x) => ui.el(x[0], x[1])));
const ICONOS_ESTADO = {
  programada: [['circle', { cx: 8, cy: 8, r: 6.2, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.8 }], ['path', { d: 'M8 4.6V8l2.4 1.6', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round' }]],
  pausada: [['rect', { x: 4, y: 3.5, width: 2.6, height: 9, rx: 0.8, fill: 'currentColor' }], ['rect', { x: 9.4, y: 3.5, width: 2.6, height: 9, rx: 0.8, fill: 'currentColor' }]],
  revision: [['circle', { cx: 7, cy: 7, r: 4.3, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.8 }], ['path', { d: 'M10.2 10.2L13.5 13.5', stroke: 'currentColor', 'stroke-width': 2, 'stroke-linecap': 'round' }]],
  proceso: [['path', { d: 'M13 8a5 5 0 1 1-1.5-3.5M13 3v2.6h-2.6', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round', 'stroke-linejoin': 'round' }]],
  problemas: [['path', { d: 'M8 2L14.5 13.5h-13z', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.6, 'stroke-linejoin': 'round' }], ['path', { d: 'M8 6.5v3.2M8 11.6v.1', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round' }]],
  rechazada: [['circle', { cx: 8, cy: 8, r: 6.2, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.8 }], ['path', { d: 'M5.6 5.6l4.8 4.8M10.4 5.6l-4.8 4.8', stroke: 'currentColor', 'stroke-width': 1.8, 'stroke-linecap': 'round' }]],
  archivada: [['rect', { x: 2, y: 3, width: 12, height: 3.2, rx: 0.8, fill: 'none', stroke: 'currentColor', 'stroke-width': 1.5 }], ['path', { d: 'M3.2 6.2V13h9.6V6.2M6.4 8.8h3.2', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linecap': 'round' }]],
};

/** «hace 5 min», «hace 2 h 10 min», «hace 3 días». */
export function haceTexto(t, ahora = Date.now()) {
  const min = Math.max(0, Math.round((ahora - t) / 60e3));
  if (min < 1) return 'recién';
  if (min < 60) return `hace ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 48) return `hace ${h} h${min % 60 && h < 6 ? ` ${min % 60} min` : ''}`;
  return `hace ${Math.floor(h / 24)} días`;
}
/** «en 3 h 20 min», «en 12 min». */
export function faltaTexto(t, ahora = Date.now()) {
  const min = Math.max(0, Math.ceil((t - ahora) / 60e3));
  if (min < 60) return `en ${min} min`;
  const h = Math.floor(min / 60);
  if (h < 48) return `en ${h} h${min % 60 ? ` ${min % 60} min` : ''}`;
  return `en ${Math.floor(h / 24)} días`;
}

/** Repinta, dentro de `raiz`, el icono, la razón y el presupuesto de cada campaña con los datos vivos (`vivo`: Map id → campaña de /api/meta). */
function pintarEstados(ctx, raiz, vivo, merc) {
  const { ui } = ctx;
  const { el } = ui;
  if (!raiz || !vivo) return;
  const ahora = Date.now();
  const zm = merc && merc.zona && merc.zona !== ZONA ? merc.zona : null;
  const ciudad = zm ? merc.ciudad : null;
  const fecha = (t) => { const h = horaEn(t, ZONA); return h ? `${h.dia} ${h.texto}` : ''; };
  for (const nodo of raiz.querySelectorAll('[data-estado]')) {
    const id = nodo.getAttribute('data-estado');
    const c = vivo.get(id);
    if (!c) continue;
    const e = estadoCampana(c, ahora);
    const m = c.motivo_estado || null;
    const tm = m && m.cuando ? Date.parse(m.cuando) : NaN;
    let razon = '';
    let detalle = e.titulo;
    if (e.clave === 'programada') {
      const hm = zm ? horaEn(e.inicio, zm) : null;
      razon = `arranca ${faltaTexto(e.inicio, ahora)} (${fecha(e.inicio)}${hm ? ` · ${hm.texto} ${ciudad}` : ''})`;
      detalle = `Activa en Meta; arranca el ${fecha(e.inicio)} de Argentina${hm ? ` (${hm.texto} en ${ciudad})` : ''}`;
    } else if (m) {
      const cuando = Number.isFinite(tm) ? haceTexto(tm, ahora) : '';
      if (e.clave === 'activa') razon = [m.corto ? `prendida ${m.corto}` : 'prendida', cuando].filter(Boolean).join(' · ');
      else razon = [m.corto, cuando].filter(Boolean).join(' · ');
      detalle = [`${e.texto}${m.corto ? `: ${m.corto}` : ''}`, m.detalle, m.por ? `Quién: ${m.por}` : null, Number.isFinite(tm) ? `Desde el ${fecha(tm)} Argentina (${haceTexto(tm, ahora)})` : null].filter(Boolean).join('\n');
    }
    const ico = e.clave === 'activa' ? el('span', { class: 'co-est__vivo' }) : ICONOS_ESTADO[e.clave] ? svgIco(ui, ICONOS_ESTADO[e.clave]) : null;
    const titulo = `${detalle}\nEstado en Meta: ${estadoTexto(c.estado)}`;
    ui.reemplazar(nodo, el('span', { class: ['co-est', `co-est--${e.tono}`], title: titulo }, ico, e.texto));
    const rz = raiz.querySelector(`[data-razon="${id}"]`);
    if (rz) { rz.textContent = razon; rz.title = titulo; rz.className = `co-carril__razon co-carril__razon--${e.tono}`; }
    const pr = raiz.querySelector(`[data-presupuesto="${id}"]`);
    if (pr && typeof c.presupuesto === 'number') pr.textContent = `${usd(c.presupuesto)}/día`;
  }
}

/** Presupuesto en carriles: una franja por campaña con cada tramo y su US$/día, sobre una rejilla de horas y medias horas;
 *  abajo la hora de Argentina y la del mercado (dueño, 16-nov: «son las 12 de Argentina pero las 4 o 5 de España»). */
function carrilesVista(ctx, lista, merc, vivo) {
  const { ui } = ctx;
  const { el } = ui;
  const g = carriles(lista);
  if (!g) return el('p', { class: 'co-nota' }, 'Todavía no hay cambios de presupuesto registrados para estas campañas.');
  const zm = merc && merc.zona && merc.zona !== ZONA ? merc.zona : null;
  const ciudad = zm ? merc.ciudad : null;
  const span = g.t1 - g.t0;
  const horaArt = (t) => horaEn(t, ZONA);
  const horaMer = (t) => (zm ? horaEn(t, zm) : null);
  const dobleHora = (t) => { const a = horaArt(t); const m = horaMer(t); return `${a ? a.texto : ''} Argentina${m ? ` · ${m.texto} ${ciudad}` : ''}`; };
  const marca = (m) => el('span', {
    class: ['co-marca', `co-marca--${m.autor}`, m.inicio ? 'co-marca--inicio' : m.sube ? 'co-marca--sube' : m.baja ? 'co-marca--baja' : null], style: { left: `${m.pos}%` },
    title: `${horaArt(Date.parse(m.cuando)).dia} · ${dobleHora(Date.parse(m.cuando))}\n${m.inicio ? `Arranca con US$ ${m.a}/día` : `US$ ${m.de} → US$ ${m.a}`} · ${m.autor === 'sistema' ? 'sistema' : 'a mano'}${m.motivo ? `\n${m.motivo}` : ''}`,
  }, m.inicio ? '●' : m.sube ? '▲' : m.baja ? '▼' : '•');
  // cada cuántas marcas mayores se escribe la hora (que no se encimen: ~1 rótulo cada 48 px en un ancho típico de 700 px)
  const mayores = g.ticks.filter((t) => t.mayor);
  const cadaN = Math.max(1, Math.ceil(mayores.length / 14));
  const rotular = new Set(mayores.filter((_, i) => i % cadaN === 0).map((t) => t.t));
  const medArt = medianoches(g.t0, g.t1, ZONA);
  const medMer = zm ? medianoches(g.t0, g.t1, zm) : [];
  const ahoraPos = 100;
  const lado = (p) => (p < 9 ? 'co-izq' : p > 91 ? 'co-der' : null);   // que el rótulo no se corte en los bordes
  const rejilla = el('div', { class: 'co-rejilla' },
    ...g.ticks.map((t) => el('i', { class: t.mayor ? null : 'co-menor', style: { left: `${t.pos}%` } })),
    ...medArt.map((m) => el('i', { class: 'co-medianoche', style: { left: `${m.pos}%` } })),
    ...medMer.map((m) => el('i', { class: 'co-medianoche-m', style: { left: `${m.pos}%` } })),
    el('i', { class: 'co-ahora', style: { left: `${ahoraPos}%` } }));
  const rotulos = el('div', { class: 'co-rotulos' },
    ...medArt.map((m) => el('span', { class: ['co-rot-art', lado(m.pos)], style: { left: `${m.pos}%` }, title: 'Medianoche en Argentina: arranca el día de la cuenta de Meta (presupuesto diario)' }, `${m.dia} · 00:00 AR`)),
    ...medMer.map((m) => el('span', { class: ['co-rot-mer', lado(m.pos)], style: { left: `${m.pos}%` }, title: `Medianoche en ${ciudad}: arranca el día del mercado` }, `${m.dia} · 00:00 ${ciudad}`)),
    el('span', { class: ['co-rot-ahora', 'co-der'], style: { left: '100%' } }, 'ahora'));
  const eje = (zona, clase) => el('div', { class: ['co-eje', clase] },
    ...g.ticks.filter((t) => t.mayor && rotular.has(t.t)).map((t) => {
      const h = horaEn(t.t, zona);
      return el('span', { style: { left: `${t.pos}%` } }, h ? (span <= 30 * 3600e3 ? h.texto : `${h.dia} ${h.texto}`) : '');
    }));
  const cursor = el('div', { class: 'co-cursor' }, el('span'));
  const filas = el('div', { class: 'co-pistas__filas' },
    ...g.carriles.map((c) => el('div', { class: 'co-carril' },
      ...c.tramos.map((t) => el('div', { class: 'co-tramo', style: { left: `${t.izq}%`, width: `${t.ancho}%`, '--co-int': `${Math.round(t.intensidad * 100)}%` } },
        t.ancho > 5 ? el('span', null, `$${Math.round(t.v)}`) : null)),
      ...c.marcas.map(marca))));
  const pistas = el('div', { class: 'co-pistas' }, rotulos, filas, rejilla, eje(ZONA, null), zm ? eje(zm, 'co-eje--mercado') : null, cursor);
  // cursor: al pasar el mouse, la hora exacta en Argentina y en el mercado
  pistas.addEventListener('mousemove', (ev) => {
    const r = pistas.getBoundingClientRect();
    const x = Math.max(0, Math.min(r.width, ev.clientX - r.left));
    const t = g.t0 + (x / r.width) * span;
    cursor.style.display = 'block';
    cursor.style.left = `${x}px`;
    cursor.firstChild.textContent = `${horaArt(t).dia} · ${dobleHora(t)}`;
    cursor.firstChild.style.left = x > r.width - 230 ? 'auto' : '6px';
    cursor.firstChild.style.right = x > r.width - 230 ? '6px' : 'auto';
  });
  pistas.addEventListener('mouseleave', () => { cursor.style.display = 'none'; });
  const lbls = el('div', { class: 'co-tl__lbls' },
    ...g.carriles.map((c) => el('div', { class: 'co-carril__lbl' },
      el('div', { class: 'co-carril__nom' }, el('b', { title: c.nombre || null }, rolTexto(c.rol) || 'Campaña'), el('span', { 'data-estado': c.id })),
      el('span', { class: 'co-carril__hoy', 'data-presupuesto': c.id }, `${usd(c.actual)}/día`),
      el('span', { class: 'co-carril__razon', 'data-razon': c.id }))),
    el('div', { class: 'co-tl__eje-lbl', style: { marginTop: '-8px' } }, 'Hora Argentina'),
    zm ? el('div', { class: 'co-tl__eje-lbl co-tl__eje-lbl--mercado', style: { marginTop: '-12px' } }, `Hora ${ciudad}`) : null);
  pintarEstados(ctx, lbls, vivo, merc);
  return el('div', null,
    el('div', { class: 'co-claves' },
      el('span', null, el('span', { class: 'co-marca co-marca--sube co-marca--sistema' }, '▲'), 'subió'),
      el('span', null, el('span', { class: 'co-marca co-marca--baja co-marca--sistema' }, '▼'), 'bajó'),
      el('span', null, el('span', { class: 'co-marca co-marca--inicio co-marca--sistema' }, '●'), 'arrancó'),
      el('span', null, el('span', { class: 'co-marca co-marca--sube co-marca--sistema' }, ''), 'borde violeta: lo hizo el sistema'),
      el('span', null, el('span', { class: 'co-marca co-marca--sube co-marca--a_mano' }, ''), 'borde amarillo: a mano'),
      el('span', null, el('i', { style: { borderLeft: '1px solid var(--borde)' } }), `líneas: cada ${g.mayorH === 1 ? 'hora' : `${g.mayorH} h`} (punteadas: cada ${g.menorH === 0.5 ? 'media hora' : `${g.menorH} h`})`),
      el('span', null, el('i', { style: { borderLeft: '2px solid var(--txt-3)' } }), 'medianoche en Argentina (día de la cuenta)'),
      zm ? el('span', null, el('i', { style: { borderLeft: '2px dashed var(--acento)' } }), `medianoche en ${ciudad} (día del mercado)`) : null,
      el('span', null, 'Pasá el mouse por las franjas para ver la hora exacta en los dos lugares, y por las marcas para ver el porqué.')),
    el('div', { class: 'co-tl' }, lbls, pistas));
}

function lineaDeTiempo(ctx, d, camps, notaVivo = null) {
  const { ui } = ctx;
  const { el } = ui;
  const esc = d.escala || {};
  const estado = { ventana: 24, campana: null, filtro: 'todo', todos: false };
  const r = resumenAutores(esc);
  const caja = el('div');
  const pintar = () => {
    ui.limpiar(caja);
    const ahora = Date.now();
    const desde = estado.ventana ? ahora - estado.ventana * 3600e3 : null;
    // apagadas fuera, salvo que hayan tenido un cambio dentro de la ventana (dueño, 16-nov: «las apagadas, ocultas»)
    const conMov = new Set(((esc.cambios || []).filter((x) => !desde || Date.parse(x.cuando) >= desde)).map((x) => x.campana));
    const visibles = camps.filter((c) => (c.activo || conMov.has(c.id)) && (!estado.campana || c.id === estado.campana));
    caja.appendChild(carrilesVista(ctx, series(esc, visibles, ahora, desde), d.mercado, d._vivo));
    const items = renglones(esc, { campana: estado.campana, filtro: estado.filtro }).filter((x) => !desde || Date.parse(x.cuando) >= desde);
    const mostrar = estado.todos ? items : items.slice(0, 25);
    if (!items.length) { caja.appendChild(el('p', { class: 'co-nota' }, 'Nada en esta ventana.')); return; }
    let diaActual = null;
    let lista = null;
    for (const x of mostrar) {   // agrupado por día, más nuevo arriba
      const d0 = dia(x.cuando);
      if (d0 !== diaActual) {
        diaActual = d0;
        caja.appendChild(el('div', { class: 'co-dia' }, d0));
        lista = el('ol', { class: 'co-lista' });
        caja.appendChild(lista);
      }
      const rol = rolTexto((camps.find((c) => c.id === x.campana) || {}).rol) || x.campana_nombre || '';
      const zm = d.mercado && d.mercado.zona && d.mercado.zona !== ZONA ? d.mercado.zona : null;
      const hm = (iso) => (zm ? (horaEn(Date.parse(iso), zm) || {}).texto : null);
      const cuando = x.clase === 'decision' && x.veces > 1 ? `${hora(x.desde)} a ${hora(x.hasta)}` : hora(x.cuando);
      const cuandoM = zm ? (x.clase === 'decision' && x.veces > 1 ? `${hm(x.desde)} a ${hm(x.hasta)}` : hm(x.cuando)) : null;
      lista.appendChild(el('li', { class: ['co-item', `co-item--${x.tono}`] },
        el('div', { class: 'co-item__cab' },
          el('span', { class: ['co-quien', `co-quien--${x.tono}`] }, x.sin_aplicar ? 'Escala · sin aplicar' : x.quien),
          el('span', { class: ['co-item__t', x.sube ? 'co-item__t--sube' : x.baja ? 'co-item__t--baja' : null] }, `${x.sube ? '▲ ' : x.baja ? '▼ ' : ''}${x.titulo}`),
          el('span', { class: 'co-item__meta' }, `${rol} · ${cuando} Argentina`, cuandoM ? el('span', { class: 'co-hora-m' }, ` · ${cuandoM} ${d.mercado.ciudad}`) : null)),
        x.detalle ? el('div', { class: 'co-item__det' }, x.detalle) : null));
    }
    if (items.length > mostrar.length) caja.appendChild(el('button', { type: 'button', class: 'boton boton--chico co-mas', onclick: () => { estado.todos = true; pintar(); } }, `Ver los ${items.length} renglones`));
  };
  const grupo = (titulo, control) => el('div', { class: 'co-grupo' }, el('span', { class: 'co-grupo__t' }, titulo), control);
  const filtros = el('div', { class: 'co-barra' },
    grupo('Ventana', ui.segmentado({ etiqueta: 'Ventana', valor: 24, opciones: [{ valor: 24, etiqueta: '24 h' }, { valor: 72, etiqueta: '3 días' }, { valor: 168, etiqueta: '7 días' }, { valor: 0, etiqueta: 'Todo' }], onCambio: (v) => { estado.ventana = v; estado.todos = false; pintar(); } })),
    grupo('Mostrar', ui.segmentado({ etiqueta: 'Qué mostrar', valor: 'todo', opciones: [{ valor: 'todo', etiqueta: 'Todo' }, { valor: 'cambios', etiqueta: 'Cambios aplicados' }, { valor: 'decisiones', etiqueta: 'Decisiones de la escala' }, { valor: 'a_mano', etiqueta: 'Solo a mano' }], onCambio: (v) => { estado.filtro = v; estado.todos = false; pintar(); } })),
    camps.filter((c) => c.activo).length > 1 ? grupo('Campaña', ui.segmentado({ etiqueta: 'Campaña', valor: null, opciones: [{ valor: null, etiqueta: 'Todas' }, ...camps.filter((c) => c.activo).map((c) => ({ valor: c.id, etiqueta: rolTexto(c.rol) || c.nombre, titulo: c.nombre }))], onCambio: (v) => { estado.campana = v; estado.todos = false; pintar(); } })) : null);
  const resumen = el('div', { class: 'co-resumen' },
    notaVivo,
    ui.chip(`${r.sistema} cambio${r.sistema === 1 ? '' : 's'} del sistema`, 'acento', { icono: false }),
    ui.chip(`${r.a_mano} a mano`, r.a_mano ? 'aviso' : 'neutro', { icono: false }),
    r.sin_aplicar ? ui.chip(`${r.sin_aplicar} decisión${r.sin_aplicar === 1 ? '' : 'es'} sin aplicar`, 'error', { icono: false }) : ui.chip('Todo lo decidido se aplicó', 'ok', { icono: false }));
  pintar();
  return ui.seccion('Línea de tiempo del presupuesto', el('div', null, resumen, filtros, caja), {
    ayuda: 'Cada suba, bajada y arranque de las campañas de esta oferta, con quién lo hizo (el sistema o a mano en el Administrador) y por qué; y lo que decidió la escala en cada vuelta, incluido lo que eligió NO hacer. Una decisión de subir o bajar sin un cambio igual en las 2 h siguientes queda «sin aplicar». Los cambios se detectan solos cada 5 minutos.',
  });
}

/** Sección completa (se llena cuando llega /api/meta?oferta=). `rango` = {desde, hasta} del período de la ficha o null. */
export function seccionCampanasMeta(ctx, o, rango, aovDado = undefined) {
  const { ui } = ctx;
  const { el } = ui;
  if (typeof ui.instalarEstilos === 'function') ui.instalarEstilos('campanas-oferta', CSS_CAMPANAS_OFERTA);
  const aov = typeof aovDado === 'number' ? aovDado : (o && o.kpis && typeof o.kpis.aov === 'number' ? o.kpis.aov : null);
  const caja = el('div', null, ui.cargando('Leyendo las campañas…'));
  const params = { oferta: o.id, ...(rango ? { desde: rango.desde, hasta: rango.hasta } : {}) };
  const pedido = ctx.api && typeof ctx.api.sobre === 'function' ? ctx.api.sobre('/meta', params) : Promise.reject(new Error('sin api'));
  // en vivo: cada 30 s se repintan estados, razones y cuentas regresivas; cada 60 s se vuelve a leer /api/meta (la nube lee Meta cada 5 min)
  // y, si cambió qué campañas hay o cuáles están prendidas, se rearma la sección entera.
  const vivo = new Map();
  let merc = null;
  let leido = null;
  let huella = '';
  const huellaDe = (d) => (d.campanas || []).map((c) => `${c.id}:${c.estado}:${c.presupuesto}`).sort().join('|');
  const notaVivo = el('span', { class: 'co-vivo-nota', role: 'status' });
  const pintarNota = () => {
    const t = leido ? Date.parse(leido) : NaN;
    ui.reemplazar(notaVivo, el('span', { class: 'co-est__vivo' }), `Estados en vivo · Meta leído ${Number.isFinite(t) ? haceTexto(t) : 'sin dato'} · se actualiza solo`);
  };
  const cargarVivo = (d) => {
    vivo.clear();
    for (const c of d.campanas || []) vivo.set(c.id, c);
    merc = d.mercado || null;
    leido = d.vivo_leido || null;
    d._vivo = vivo;
  };
  const armar = (d) => {
    cargarVivo(d);
    huella = huellaDe(d);
    const camps = arbol(d, aov);
    if (!camps.length) { ui.reemplazar(caja, ui.vacio('Esta oferta todavía no tiene campañas con lectura de Meta.')); return; }
    const tabla = ui.seccion('Campañas en Meta', el('div', null,
      tablaArbol(ctx, camps, aov),
      el('p', { class: 'co-nota' },
        `ROAS con AOV = compras de Meta × AOV de la tienda (${aov ? usd(aov) : 'sin dato'}, con bump y upsells) ÷ gasto: la misma vara con la que decide la escala. `,
        `«Pierde» sin compras = gastó 1,5 veces el AOV sin vender. ${rango ? `Período ${rango.desde} a ${rango.hasta}` : 'Desde el inicio'}; presupuesto y estado, en vivo. Debajo de cada campaña, lo último que decidió la escala (pasá el mouse para ver el porqué).`)), {
      ayuda: 'Como el Administrador de anuncios: abrí cada campaña para ver sus conjuntos, y cada conjunto para ver sus anuncios. La nube lee Meta cada 5 minutos.',
    });
    pintarNota();
    ui.reemplazar(caja, tabla, lineaDeTiempo(ctx, d, camps, notaVivo));
  };
  let reloj = null;
  let vueltas = 0;
  const latir = () => {
    if (!caja.isConnected) { clearInterval(reloj); return; }
    vueltas += 1;
    pintarEstados(ctx, caja, vivo, merc);
    pintarNota();
    if (vueltas % 2) return;
    ctx.api.sobre('/meta', params).then((s2) => {
      const d2 = (s2 && s2.datos) || {};
      if (!caja.isConnected || !(d2.campanas || []).length) return;
      if (huellaDe(d2) !== huella) { armar(d2); return; }
      cargarVivo(d2);
      pintarEstados(ctx, caja, vivo, merc);
      pintarNota();
    }).catch(() => { /* sin red: queda lo último */ });
  };
  pedido.then((s) => {
    armar((s && s.datos) || {});
    if (typeof globalThis.setInterval === 'function' && !reloj) reloj = globalThis.setInterval(latir, 30e3);
  }).catch((e) => { try { ui.reemplazar(caja, ui.errorBox(e)); } catch (_) { /* la ficha ya no está (o pruebas sin DOM) */ } });
  return caja;
}
