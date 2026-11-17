// pages/negocio.js — #/negocio y #/negocio/<oferta>: el tablero para decidir (pantalla de inicio del panel en el modo «negocio»).
//
// Pedidos del dueño (2026-11-12): centralizar las ofertas con sus números; «simplificá el dashboard a lo mínimo que sea decision maker»;
// métricas típicas por funnel; «que no sea todo gris»; y, al verlo: «esto no se entiende nada, simplificarlo».
// Por eso la pantalla tiene muy poco: 3 cifras grandes (ganancia neta, gasto y ROAS neto) y una FILA por oferta con bandera y nombre,
// una pastilla con el veredicto (Escalar, Mirar, Apagar, Sin pauta o Pausada), 3 números con color (ganancia contra Meta, ROAS neto,
// ventas), una frase corta de por qué y, si lo hay, el próximo cambio programado. Toda la fila abre la ficha.
// Ficha, de lo importante a lo secundario: veredicto y 3 cifras (con un solo medidor: ROAS neto) → métricas del funnel en una tabla de dos
// columnas → embudo simple y anuncios → historial, ventas y documentos.
// Color con significado y nunca solo (siempre con palabra o ícono). Fuente: GET /api/negocio (dashboard/negocio.py). Solo lectura.

import { graficoSerie } from '../lib/graficos.js';
import { instalarEstilos as instalarEstilosP5 } from '../lib/operacion.js';
import {
  usd, moneda, pct, roas, numero, estadoOferta, urlExterna, ordenarOfertas, serieDiaria, estadoCorte, textoCorte, DEFINICIONES, PRODUCCION_Y_ROAS, tonoRoas,
} from '../lib/negocio.js';
import { CSS_VISUAL, banderas, nombresPais, claseIdentidad, medidor, tonoTasa, renglonReferentePaises, modeloReferentePaises, fechaMedicion } from '../lib/negocio-visual.js';
import { CSS_PERIODO, selectorPeriodo, periodoPedido, recordarPeriodo, consultaPeriodo } from '../lib/negocio-periodo.js';
import { refOferta, resolverRef, fijarTerminos, terminosDeOfertas, botonOcultar } from '../lib/ocultar.js';
import { seccionAgenda, seccionLoQueViene, horaAgenda } from '../lib/agenda.js';
import { seccionCampanasMeta } from '../lib/campanas-oferta-vista.js';
import { CSS_ETAPAS, ETAPAS, chipEtapa, chipBackend, contarEtapas, filtrarOfertas, detalleBackend, tonoEtapa } from '../lib/negocio-etapas.js';
import { CSS_DESGLOSE, seccionDesglose } from '../lib/negocio-desglose.js';

export const meta = { ruta: 'negocio', titulo: 'Negocio', grupo: 'El sistema', icono: 'grafico', escucha: ['oferta', 'empresa'] };

/** Veredicto de la pastilla: texto corto, tono e ícono. La clave sale del servidor (accion_sugerida.clave). */
export const PASTILLA = {
  escalar: { texto: 'Escalar', clase: 'escalar', icono: 'tendencia-sube' },
  mirar: { texto: 'Mirar', clase: 'mirar', icono: 'ojo' },
  cortar: { texto: 'Apagar', clase: 'apagar', icono: 'x-circulo' },
  sin_pauta: { texto: 'Sin pauta', clase: 'sin-pauta', icono: 'reloj' },
  pausada: { texto: 'Pausada', clase: 'pausada', icono: 'pausa' },
};
export function pastillaDe(a) {
  const base = PASTILLA[a && a.clave] || { texto: (a && a.texto) || 'Sin dato', clase: 'sin-pauta', icono: 'circulo-punteado' };
  return a && a.clave === 'pausada' && a.texto ? { ...base, texto: a.texto } : base;
}

const CSS = `
.ng-sub { color: var(--txt-2); font-size: var(--t-sm); }
.ng-pos { color: var(--ok); } .ng-neg { color: var(--error); }
.ng-sale { color: var(--txt-2); }
.ng-nota-ver { color: var(--txt-3); font-size: var(--t-xs); white-space: nowrap; }
.ng-nota { color: var(--txt-2); font-size: var(--t-sm); max-width: 90ch; margin: 0; }
.ng-lista { margin: 0; padding-left: 1.2em; display: grid; gap: 4px; list-style: disc; }
.ng-img { max-width: 100%; height: auto; border-radius: var(--r-2); }

/* las 3 cifras */
.ng-tres { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--e-3); }
.ng-cifra { display: grid; gap: 2px; padding: var(--e-4) var(--e-5); border-radius: var(--r-3); border: 1px solid var(--neutro-borde); background: var(--neutro-bg); min-width: 0; }
.ng-cifra--ok { background: var(--ok-bg); border-color: var(--ok-borde); } .ng-cifra--error { background: var(--error-bg); border-color: var(--error-borde); }
.ng-cifra--info { background: var(--info-bg); border-color: var(--info-borde); }
.ng-cifra__rot { display: flex; align-items: center; gap: 6px; color: var(--txt-2); font-size: var(--t-sm); font-weight: 600; }
.ng-cifra__valor { display: flex; align-items: center; gap: 8px; font-size: clamp(1.7rem, 3vw, 2.5rem); font-weight: 750; letter-spacing: -.015em; font-variant-numeric: tabular-nums; white-space: nowrap; line-height: 1.15; }
.ng-cifra--ok .ng-cifra__valor { color: var(--ok); } .ng-cifra--error .ng-cifra__valor { color: var(--error); }
.ng-cifra__sub { color: var(--txt-2); font-size: var(--t-xs); }
.ng-corte-linea { display: flex; flex-wrap: wrap; align-items: center; gap: 6px var(--e-2); color: var(--txt-2); font-size: var(--t-sm); margin-top: calc(-1 * var(--e-2)); }
.ng-corte-linea strong { color: var(--txt); }
.ng-corte-linea--viejo { color: var(--aviso); }

/* KPIs (AOV, margen, toma de upsells, ganancia del día) */
.ng-kpis { display: grid; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); gap: var(--e-2); }
.ng-kpi { display: grid; gap: 1px; padding: var(--e-3) var(--e-4); border-radius: var(--r-2); border: 1px solid var(--neutro-borde); background: var(--neutro-bg); min-width: 0; }
.ng-kpi--ok { border-color: var(--ok-borde); } .ng-kpi--ok .ng-kpi__valor { color: var(--ok); }
.ng-kpi--error { border-color: var(--error-borde); } .ng-kpi--error .ng-kpi__valor { color: var(--error); }
.ng-kpi--aviso { border-color: var(--aviso-borde); } .ng-kpi--aviso .ng-kpi__valor { color: var(--aviso); }
.ng-kpi__rot { display: flex; align-items: center; gap: 4px; color: var(--txt-2); font-size: var(--t-xs); font-weight: 600; }
.ng-kpi__valor { font-size: var(--t-lg); font-weight: 750; font-variant-numeric: tabular-nums; white-space: nowrap; }
.ng-kpi__sub { color: var(--txt-2); font-size: var(--t-xs); }
.ng-meta-barra { height: 6px; border-radius: var(--r-pill); background: var(--neutro-borde); overflow: hidden; margin-top: 4px; }
.ng-meta-barra__lleno { display: block; height: 100%; background: var(--ok); min-width: 2px; }

/* hoy en Meta, en vivo */
.ng-vivo { display: flex; flex-wrap: wrap; align-items: baseline; gap: 4px var(--e-4); padding: var(--e-2) var(--e-4); border-radius: var(--r-2); border: 1px solid var(--info-borde); background: var(--info-bg); font-size: var(--t-sm); }
.ng-vivo__tit { display: inline-flex; align-items: center; gap: 6px; font-weight: 700; }
.ng-vivo__punto { width: 8px; height: 8px; border-radius: 50%; background: var(--ok); display: inline-block; }
.ng-vivo--viejo .ng-vivo__punto { background: var(--aviso); }
.ng-vivo__dato strong { font-variant-numeric: tabular-nums; }
.ng-vivo__sub { color: var(--txt-2); font-size: var(--t-xs); }

/* pastilla del veredicto */
.ng-pastilla { display: inline-flex; align-items: center; gap: 7px; padding: 6px 14px; border-radius: var(--r-pill); font-weight: 750; font-size: var(--t-md); white-space: nowrap; border: 1px solid transparent; }
.ng-pastilla--escalar { background: var(--ok-bg); color: var(--ok); border-color: var(--ok-borde); }
.ng-pastilla--mirar { background: var(--aviso-bg); color: var(--aviso); border-color: var(--aviso-borde); }
.ng-pastilla--apagar { background: var(--critico-solido); color: var(--sobre-critico); }
.ng-pastilla--sin-pauta { background: var(--neutro-bg); color: var(--txt-2); border-color: var(--neutro-borde); }
.ng-pastilla--pausada { background: #4a5565; color: #ffffff; }
:root[data-tema="oscuro"] .ng-pastilla--pausada { background: #3a4452; color: #e8ecf2; border-color: #566272; }
@media (prefers-color-scheme: dark) { :root[data-tema="auto"] .ng-pastilla--pausada { background: #3a4452; color: #e8ecf2; border-color: #566272; } }
.ng-pastilla--grande { font-size: 1.5rem; padding: 8px 20px; }

/* lista de ofertas */
.ng-filas { display: grid; gap: var(--e-2); }
.ng-fila { position: relative; display: grid; grid-template-columns: minmax(0, 1fr) auto repeat(3, minmax(108px, auto)); grid-template-areas: "nombre pastilla n1 n2 n3" "chips chips n1 n2 n3" "frase frase n1 n2 n3" "ref ref n1 n2 n3"; align-items: center; gap: 4px var(--e-4); padding: var(--e-3) var(--e-4); border: 1px solid var(--borde); border-left: 5px solid var(--ng-id, var(--borde-fuerte)); border-radius: var(--r-3); background: var(--sup); box-shadow: var(--sombra); }
.ng-fila:hover { background: var(--sup-2); }
.ng-fila:focus-within { outline: 2px solid var(--foco); outline-offset: 2px; }
.ng-fila__nombre { grid-area: nombre; display: flex; align-items: center; gap: 8px; min-width: 0; font-size: var(--t-md); font-weight: 700; }
.ng-fila__enlace { color: inherit; text-decoration: none; min-width: 0; }
.ng-fila__enlace::after { content: ''; position: absolute; inset: 0; border-radius: var(--r-3); }
.ng-fila__enlace:focus { outline: none; }
.ng-fila__pastilla { grid-area: pastilla; display: inline-flex; align-items: center; gap: 4px; justify-self: start; }
.ng-fila__pastilla .ayuda-btn, .ng-veredicto .ayuda-btn { position: relative; z-index: 1; }
.ng-fila__chips { grid-area: chips; display: flex; flex-wrap: wrap; gap: 6px; position: relative; z-index: 1; }
.ng-fila__ref { grid-area: ref; position: relative; z-index: 1; }
.ng-fila__frase { grid-area: frase; display: flex; flex-wrap: wrap; gap: 2px var(--e-3); color: var(--txt-2); font-size: var(--t-sm); }
.ng-fila__prog { display: inline-flex; align-items: center; gap: 4px; color: var(--info); font-weight: 600; }
.ng-num { display: grid; gap: 0; text-align: right; }
.ng-num:nth-of-type(1) { grid-area: n1; } .ng-num:nth-of-type(2) { grid-area: n2; } .ng-num:nth-of-type(3) { grid-area: n3; }
.ng-num__valor { font-size: var(--t-lg); font-weight: 750; font-variant-numeric: tabular-nums; white-space: nowrap; }
.ng-num__rot { color: var(--txt-2); font-size: var(--t-xs); white-space: nowrap; }

/* ficha */
.ng-ficha-tit { display: inline-flex; align-items: center; gap: 10px; }
.ng-ficha-tit .ng-id-punto { width: 14px; height: 14px; flex-basis: 14px; }
.ng-veredicto { display: grid; gap: var(--e-2); padding: var(--e-4) var(--e-5); border-radius: var(--r-3); border: 1px solid var(--borde); border-left: 6px solid var(--ng-id, var(--borde-fuerte)); background: var(--sup); box-shadow: var(--sombra); }
.ng-veredicto__fila { display: flex; align-items: center; gap: var(--e-3); flex-wrap: wrap; }
.ng-veredicto__frase { font-size: var(--t-md); font-weight: 600; }
.ng-veredicto__porque { color: var(--txt-2); font-size: var(--t-sm); max-width: 90ch; }
.ng-veredicto__prog { display: inline-flex; align-items: center; gap: 6px; color: var(--info); font-size: var(--t-sm); font-weight: 600; }
.ng-tabla-met { width: 100%; border-collapse: collapse; font-size: var(--t-base); }
.ng-tabla-met th { text-align: left; font-size: var(--t-xs); text-transform: uppercase; letter-spacing: .05em; color: var(--txt-2); padding: var(--e-4) 0 var(--e-1); border-bottom: 1px solid var(--borde-fuerte); }
.ng-tabla-met tr:first-child th { padding-top: 0; }
.ng-tabla-met td { padding: 7px 0; border-bottom: 1px solid var(--borde); }
.ng-tabla-met td:first-child { color: var(--txt-2); }
.ng-tabla-met td:first-child .ayuda-btn { margin-left: 4px; vertical-align: middle; }
.ng-tabla-met td:last-child { text-align: right; font-weight: 650; font-variant-numeric: tabular-nums; white-space: nowrap; }
.ng-tabla-met tr.ng-total td { color: var(--txt); font-weight: 750; }
.ng-tabla-met tr.ng-sub td { padding: 3px 0 3px var(--e-4); border-bottom: 0; font-size: var(--t-sm); }
.ng-tabla-met tr.ng-sub td:last-child { font-weight: 500; color: var(--txt-2); }
.ng-sub__rot { color: var(--txt-2); }
.ng-tabla-met tr.ng-sub--nota td { color: var(--txt-3); font-size: var(--t-xs); font-weight: 400; text-align: left; padding-bottom: 8px; }
.ng-sub__det { margin-left: var(--e-2); color: var(--txt-3); font-size: var(--t-xs); font-variant-numeric: tabular-nums; }
.ng-emb { display: grid; gap: 6px; }
.ng-emb__fila { display: grid; grid-template-columns: 150px minmax(0, 1fr) 64px; align-items: center; gap: var(--e-3); }
.ng-emb__rot { color: var(--txt-2); font-size: var(--t-sm); }
.ng-emb__pista { height: 22px; border-radius: var(--r-1, 4px); background: var(--sup-2); overflow: hidden; }
.ng-emb__lleno { display: block; height: 100%; border-radius: inherit; }
.ng-emb__lleno--1 { background: var(--info); }
.ng-emb__lleno--2 { background: var(--aviso); }
.ng-emb__lleno--3 { background: var(--ok); }
.ng-emb__n { text-align: right; font-weight: 750; font-variant-numeric: tabular-nums; }
.ng-emb__paso { padding-left: 162px; color: var(--txt-2); font-size: var(--t-sm); }
.ng-emb__paso b { display: inline-flex; align-items: center; gap: 3px; }
.ng-emb__ref { color: var(--txt-3); font-size: var(--t-xs); }
.ng-emb__cr { margin-top: var(--e-3); font-size: var(--t-base); }
.ng-emb__det { margin-top: var(--e-3); }
.ng-emb__det summary { cursor: pointer; color: var(--txt-2); font-size: var(--t-sm); }
.ng-emb__tabla { width: 100%; border-collapse: collapse; font-size: var(--t-sm); margin-top: var(--e-2); }
.ng-emb__tabla th { text-align: left; font-size: var(--t-xs); color: var(--txt-2); padding: 4px 0; border-bottom: 1px solid var(--borde-fuerte); }
.ng-emb__tabla td { padding: 5px 0; border-bottom: 1px solid var(--borde); font-variant-numeric: tabular-nums; }
.ng-emb__tabla td:not(:first-child), .ng-emb__tabla th:not(:first-child) { text-align: right; }
@media (max-width: 640px) { .ng-emb__fila { grid-template-columns: 96px minmax(0, 1fr) 48px; } .ng-emb__paso { padding-left: 0; } }
.ng-emb-simple { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--e-3); }
.ng-emb-simple__paso { padding: var(--e-3); border-radius: var(--r-2); background: var(--sup-2); border: 1px solid var(--borde); }
.ng-emb-simple__n { font-size: var(--t-lg); font-weight: 750; font-variant-numeric: tabular-nums; }
.ng-emb-simple__rot { color: var(--txt-2); font-size: var(--t-sm); }
.ng-emb-simple__pct { display: inline-flex; align-items: center; gap: 4px; font-weight: 700; font-size: var(--t-sm); margin-top: 4px; }
.ng-emb-simple__ref { color: var(--txt-3); font-size: var(--t-xs); }
.ng-dos { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: var(--salto); align-items: start; }
.ng-enlaces { display: flex; flex-wrap: wrap; gap: var(--e-2); }
.ng-plegable > summary { cursor: pointer; padding: var(--e-3) var(--pad-tarjeta); font-weight: 650; }
.ng-plegable > .ng-plegable__cuerpo { padding: 0 var(--pad-tarjeta) var(--pad-tarjeta); display: grid; gap: var(--e-3); }
.ng-ad-resumen { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; margin: 0; font-weight: 650; }
.ng-ad-nombre { display: grid; gap: 1px; min-width: 0; }
.ng-ad-fila { display: flex; align-items: center; gap: 8px; min-width: 0; }
.ng-mini { flex: none; display: inline-grid; place-items: center; overflow: hidden; border-radius: 6px; background: var(--neutro-bg); border: 1px solid var(--borde); color: var(--txt-3); }
.ng-mini img { width: 100%; height: 100%; object-fit: cover; display: block; }
.ng-mini--clic { cursor: zoom-in; }
.ng-mini--clic:focus-visible { outline: 2px solid var(--foco, var(--info)); outline-offset: 2px; }
.ng-ad-puesto { color: var(--txt-2); font-variant-numeric: tabular-nums; }
.ng-ad-todos > summary { cursor: pointer; color: var(--txt-2); font-size: var(--t-sm); padding: var(--e-1) 0; }
.ng-ad-todos[open] > summary { margin-bottom: var(--e-2); }
.ng-ad-tabla td.col-flex, .ng-ad-tabla th.col-flex { min-width: 200px; max-width: 320px; }\n.ng-ad-tabla .tabla td, .ng-ad-tabla .tabla th { padding-left: 8px; padding-right: 8px; }
.ng-ad-nombre__t { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ng-ad-nombre__sub { color: var(--txt-3); font-size: var(--t-xs); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ng-vad { display: inline-flex; align-items: center; gap: 4px; padding: 2px 9px; border-radius: var(--r-pill); font-size: var(--t-xs); font-weight: 700; white-space: nowrap; border: 1px solid transparent; }
.ng-vad--ganador { background: var(--ok-bg); color: var(--ok); border-color: var(--ok-borde); }
.ng-vad--promete { background: var(--info-bg); color: var(--info); border-color: var(--info-borde); }
.ng-vad--sin_datos { background: var(--neutro-bg); color: var(--txt-2); border-color: var(--neutro-borde); }
.ng-vad--flojo { background: var(--error-bg); color: var(--error); border-color: var(--error-borde); }
.ng-vad--mirar { background: var(--aviso-bg); color: var(--aviso); border-color: var(--aviso-borde); }
.ng-r3d { display: inline-flex; flex-direction: column; align-items: flex-end; line-height: 1.15; }
.ng-r3d b { font-weight: 600; }
.ng-r3d small { font-size: 10.5px; color: var(--texto-2, #8a8f98); font-variant-numeric: tabular-nums; }
.ng-r3d--ok b { color: var(--ok, #16a34a); }
.ng-r3d--mal b { color: var(--error, #dc2626); }
.ng-r3d--duda b { color: inherit; opacity: .85; }
tr.ng-ad-ganador td { background: var(--ok-bg); }
tr.ng-ad-ganador td:first-child { box-shadow: inset 4px 0 0 var(--punto-ok); }
.ng-ad-tarjetas { display: none; gap: var(--e-2); }
.ng-ad-tarjeta { display: grid; gap: var(--e-2); padding: var(--e-3); border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup); }
.ng-ad-tarjeta.ng-ad-ganador { background: var(--ok-bg); border-color: var(--ok-borde); }
.ng-ad-tarjeta__cab { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--e-2); }
.ng-ad-tarjeta__cab .ng-ad-nombre__t { white-space: normal; }
.ng-ad-tarjeta__cifras { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--e-2); margin: 0; }
.ng-ad-tarjeta__cifras dt { color: var(--txt-2); font-size: var(--t-xs); } .ng-ad-tarjeta__cifras dd { margin: 0; font-weight: 650; font-variant-numeric: tabular-nums; }
.ng-ad-tarjeta__mas summary { cursor: pointer; color: var(--txt-2); font-size: var(--t-sm); }
.ng-ad-tarjeta__mas .ng-ad-tarjeta__cifras { margin-top: var(--e-2); grid-template-columns: repeat(2, minmax(0, 1fr)); }
@media (max-width: 760px) { .pila > .ng-ad-tabla { display: none; } .ng-ad-tarjetas { display: grid; } .ng-ad-tarjeta__cifras { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.ng-parte { display: inline-flex; align-items: center; gap: 6px; justify-content: flex-end; }
.ng-parte__barra { display: inline-block; height: 6px; border-radius: var(--r-pill); background: var(--ng-id, var(--info)); }

@media (max-width: 900px) {
  .ng-fila { grid-template-columns: repeat(3, minmax(0, 1fr)); grid-template-areas: "nombre nombre pastilla" "chips chips chips" "n1 n2 n3" "frase frase frase" "ref ref ref"; gap: var(--e-2); }
  .ng-num { text-align: left; }
  .ng-fila__pastilla { justify-self: end; }
}
@media (max-width: 640px) {
  .ng-tres { grid-template-columns: minmax(0, 1fr); gap: var(--e-2); }
  .ng-cifra { padding: var(--e-3) var(--e-4); }
  .ng-fila__nombre { font-size: var(--t-base); }
  .ng-pastilla { font-size: var(--t-sm); padding: 5px 11px; }
  .ng-pastilla--grande { font-size: 1.2rem; }
  .ng-num__valor { font-size: var(--t-md); }
  .ng-emb-simple { grid-template-columns: minmax(0, 1fr); }
}
`;

let ultimoSobre = null;

function estilos(ui) {
  instalarEstilosP5(ui);
  if (typeof ui.instalarEstilos === 'function') { ui.instalarEstilos('negocio-visual', CSS_VISUAL); ui.instalarEstilos('negocio-periodo', CSS_PERIODO); ui.instalarEstilos('negocio-etapas', CSS_ETAPAS); ui.instalarEstilos('negocio-desglose', CSS_DESGLOSE); ui.instalarEstilos('negocio', CSS); }
}

const signo = (ui, x, texto) => ui.el('span', { class: typeof x === 'number' ? (x > 0 ? 'ng-pos' : x < 0 ? 'ng-neg' : null) : null }, texto);
const signoRoas = (ui, x) => ui.el('span', { class: tonoRoas(x) === 'ok' ? 'ng-pos' : tonoRoas(x) === 'error' ? 'ng-neg' : null }, roas(x));
/** Regla de signo y color (dueño, 12-nov): lo que ENTRA va en verde con «+»; lo que SALE con «−» en tono neutro; los RESULTADOS
 *  con «+» verde o «−» rojo. El signo va siempre: el color nunca es la única señal. */
const entra = (ui, x) => (typeof x === 'number' ? ui.el('span', { class: x > 0 ? 'ng-pos' : null }, usd(x, { signo: true })) : '—');
const sale = (ui, x) => (typeof x === 'number' ? ui.el('span', { class: 'ng-sale' }, x ? usd(-Math.abs(x)) : usd(0)) : '—');
const resultado = (ui, x) => (typeof x === 'number' ? signo(ui, x, usd(x, { signo: true })) : '—');
const tonoDinero = (x) => (typeof x === 'number' && x !== 0 ? (x > 0 ? 'ok' : 'error') : null);

function botonActualizar(ctx) {
  return ctx.ui.el('button', { type: 'button', class: 'btn btn--chico', onclick: () => ctx.recargar() }, ctx.ui.icono('refrescar', { tam: 14 }), 'Actualizar');
}

// período elegido (lo fija render); las direcciones de las fichas lo llevan para que se mantenga al navegar
let RANGO = null;
// con «Ocultar info» de nombres, la dirección lleva el número de la oferta (~2) en vez de su nombre
let IDS = [];
const hrefOferta = (id) => `#/negocio/${encodeURIComponent(refOferta(id, IDS))}${RANGO ? consultaPeriodo(RANGO) : ''}`;
const almacen = () => { try { return globalThis.localStorage || null; } catch (_) { return null; } };

function barraPeriodo(ctx, d, id) {
  const p = d.periodo || {};
  return selectorPeriodo(ctx.ui, {
    rango: RANGO, hoy: p.hoy || new Date().toISOString().slice(0, 10), primerDia: p.primer_dia,
    alElegir: (r) => { recordarPeriodo(r, almacen()); ctx.navegar(`#/negocio${id ? `/${encodeURIComponent(refOferta(id, IDS))}` : ''}${consultaPeriodo(r)}`); },
  });
}

/** Junto a la pastilla, cuando el período no es «Desde el inicio»: el veredicto es una decisión y mira todos los días. */
const notaVeredicto = (ui, d) => (d.periodo && !d.periodo.todo ? ui.el('span', { class: 'ng-nota-ver', title: 'El veredicto se calcula siempre con todos los días desde el inicio: es una decisión, no un dato del período.' }, 'veredicto con todos los días') : null);
function identidades(d) { return Object.fromEntries((d.ofertas || []).map((o, i) => [o.id, claseIdentidad(i)])); }

function lineaCorte(ui, corte, libro, metaLeido = null) {
  const { el } = ui;
  const est = estadoCorte(corte);
  return el('p', { class: ['ng-corte-linea', corte && corte.viejo && 'ng-corte-linea--viejo'], role: 'status' },
    ui.icono('reloj', { tam: 14 }), 'Datos al ', el('strong', null, textoCorte(corte && corte.ultimo)), ` · ${est.texto.toLowerCase()}`,
    metaLeido ? el('span', null, ` · Meta por día leído el ${textoCorte(metaLeido)}`) : null,
    libro && libro.modificado ? el('span', null, ' · libro actualizado ', ui.tiempo(libro.modificado)) : null);
}

function cifra(ui, { etiqueta, valor, tono, sub, ayuda, icono }) {
  const { el } = ui;
  return el('div', { class: ['ng-cifra', tono && `ng-cifra--${tono}`] },
    el('div', { class: 'ng-cifra__rot' }, etiqueta, ayuda ? ui.ayuda(ayuda) : null),
    el('div', { class: 'ng-cifra__valor' }, icono ? ui.icono(icono, { tam: 24 }) : null, valor),
    sub ? el('div', { class: 'ng-cifra__sub' }, sub) : null);
}

const ICONO_TONO = { ok: 'tendencia-sube', error: 'tendencia-baja' };

function pastilla(ui, a, { grande = false } = {}) {
  const { el } = ui;
  const p = pastillaDe(a);
  return el('span', { class: ['ng-pastilla', `ng-pastilla--${p.clase}`, grande && 'ng-pastilla--grande'] }, ui.icono(p.icono, { tam: grande ? 22 : 17 }), p.texto);
}

function ayudaVeredicto(ui, a) {
  const firmada = /firmada por/.test((a && a.regla) || '');
  return ui.ayuda({ titulo: 'Por qué este veredicto', texto: `${(a && a.porque) || ''} Regla ${firmada ? 'firmada' : 'propuesta, todavía sin firmar'}: ${(a && a.regla) || ''}.` });
}

// ───────────────────────── vista de cartera ─────────────────────────

function tresCifras(ui, c, hay = true) {
  if (!hay) {
    return ui.el('section', { class: 'ng-tres', 'aria-label': 'La cartera en tres números' },
      cifra(ui, { etiqueta: 'Ganancia neta', valor: '—', sub: 'Sin datos en este período', ayuda: DEFINICIONES.ganancia_neta }),
      cifra(ui, { etiqueta: 'Gasto en anuncios', valor: '—', tono: 'info', sub: 'Sin datos en este período' }),
      cifra(ui, { etiqueta: 'ROAS neto', valor: '—', sub: 'Sin datos en este período', ayuda: DEFINICIONES.roas_neto }));
  }
  const tg = tonoDinero(c.ganancia_neta);
  const tr = tonoRoas(c.roas_neto);
  return ui.el('section', { class: 'ng-tres', 'aria-label': 'La cartera en tres números' },
    cifra(ui, { etiqueta: 'Ganancia neta', valor: usd(c.ganancia_neta, { signo: true }), tono: tg, icono: ICONO_TONO[tg], sub: tg === 'error' ? 'Perdiendo, con producción y fijos' : 'Ganando, con producción y fijos', ayuda: DEFINICIONES.ganancia_neta }),
    cifra(ui, { etiqueta: 'Gasto en anuncios', valor: usd(-Math.abs(c.gasto_meta || 0)), tono: 'info', sub: 'Meta, todas las ofertas' }),
    cifra(ui, { etiqueta: 'ROAS neto', valor: roas(c.roas_neto), tono: tr, icono: ICONO_TONO[tr], sub: tr === 'ok' ? 'Los anuncios se pagan solos (sobre 1,00 ×)' : 'Los anuncios no se pagan (bajo 1,00 ×)', ayuda: DEFINICIONES.roas_neto }));
}

function numeroFila(ui, rot, valor) {
  return ui.el('span', { class: 'ng-num' }, ui.el('span', { class: 'ng-num__valor' }, valor), ui.el('span', { class: 'ng-num__rot' }, rot));
}

/** Próximo paso de la agenda (sin las tareas que se repiten) para la fila de la cartera, si el libro no trae un «programado». */
function proximoDeAgenda(o) {
  const i = (o.agenda || []).find((x) => (x.tipo === 'proximo' || x.tipo === 'te_toca') && !x.recurrente && x.cuando);
  return i ? { corto: `${horaAgenda(i.cuando)}: ${i.titulo}`, que: i.detalle || i.titulo } : null;
}

function filaOferta(ctx, o, clase, d) {
  const { ui } = ctx;
  const { el } = ui;
  const a = o.accion_sugerida || {};
  const prog = (o.programado || [])[0] || proximoDeAgenda(o);
  const hay = o.con_datos_periodo !== false;
  const conGasto = hay && Boolean(o.gasto_meta);
  return el('article', { class: ['ng-fila', clase], 'aria-label': `${o.nombre}: ${pastillaDe(a).texto}` },
    el('div', { class: 'ng-fila__nombre' },
      el('span', { class: 'ng-id-punto', 'aria-hidden': 'true' }), banderas(ui, o.mercado, { conNombre: true }),
      el('a', { class: 'ng-fila__enlace', href: hrefOferta(o.id) }, o.nombre),
      o.replica_de ? el('span', { class: ['ng-etapa', 'ng-etapa--neutro'], title: `Misma oferta que «${o.replica_de}», llevada a otro mercado` }, `Réplica de ${o.replica_de}`) : null),
    el('div', { class: 'ng-fila__pastilla' }, pastilla(ui, a), ayudaVeredicto(ui, a), notaVeredicto(ui, d)),
    el('div', { class: 'ng-fila__chips' }, chipEtapa(ui, o.etapa), chipBackend(ui, o.backend), chipFrescura(ui, o), chipSinDia(ui, o)),
    numeroFila(ui, 'contra Meta', conGasto ? resultado(ui, o.ganancia_contra_meta) : '—'),
    numeroFila(ui, 'ROAS neto', conGasto ? signoRoas(ui, o.roas_neto) : '—'),
    numeroFila(ui, o.ventas_n === 1 ? 'venta' : 'ventas', hay ? numero(o.ventas_n, 0) : '—'),
    el('div', { class: 'ng-fila__frase' },
      el('span', null, o.frase || a.porque || ''),
      prog ? el('span', { class: 'ng-fila__prog', title: prog.que }, ui.icono('reloj', { tam: 13 }), prog.corto || prog.que) : null),
    el('div', { class: 'ng-fila__ref' }, renglonReferentePaises(ui, o.ficha, o.mercado, { compacto: true })));
}

/** Ficha: dónde corre la oferta original (pedido del dueño, 14-nov) y por qué no se pauta ahí. */
function seccionReferentePaises(ctx, o) {
  const { ui } = ctx;
  const { el } = ui;
  const m = modeloReferentePaises(o.ficha, o.mercado);
  const nota = m.medido
    ? `Anuncios activos del original por país, contados en la Biblioteca de Anuncios de Meta el ${fechaMedicion(m.fecha) || 'sin fecha'}. Donde hay bandera, no pautes: para llevar esta oferta a otro país, elige uno que no esté en la lista.`
    : 'Todavía no se midió en qué países corre el original. Lo mide la vuelta diaria de búsqueda de ofertas cuando la oferta tiene la página del original anotada.';
  const extra = [];
  if (m.medido && m.nuestrosSinMirar.length) extra.push(el('p', { class: 'ng-nota' }, `Tu país (${m.nuestrosSinMirar.map((c) => nombresPais(c)).join(' y ')}) no estaba entre los mirados: la próxima medición lo incluye.`));
  const tecnico = m.paginas && m.paginas.length
    ? ui.detalleTecnico('Detalle técnico', el('p', { class: 'ng-nota oc--referentes' }, `Páginas del original: ${m.paginas.map((p) => `${p.nombre || 'sin nombre'} (${p.page_id})`).join(' · ')}. Campo ficha.referente_paises del libro de tests.`))
    : null;
  return ui.seccion('Dónde corre la oferta original', el('div', { class: 'pila' }, renglonReferentePaises(ui, o.ficha, o.mercado), el('p', { class: 'ng-nota' }, nota), ...extra, tecnico),
    { ayuda: 'La oferta original es la que modelamos. Donde ya pauta, compites con ella por el mismo público.' });
}

function plegable(ui, titulo, cuerpo) {
  return ui.el('details', { class: 'seccion ng-plegable' }, ui.el('summary', null, titulo), ui.el('div', { class: 'ng-plegable__cuerpo' }, cuerpo));
}

function seccionComoSeCalcula(ctx, d, sobre) {
  const { ui } = ctx;
  const { el } = ui;
  const r = d.referencias;
  const c = d.cartera;
  const tc = Object.entries(d.tipos_de_cambio || {}).filter(([k]) => k !== 'USD').map(([k, v]) => `1 ${k} = ${numero(v, 5)} USD`).join(' · ');
  return plegable(ui, 'Cómo se calcula', [
    el('ul', { class: ['ng-nota', 'ng-lista'] },
      el('li', null, el('strong', null, 'Veredicto'), ': «Apagar» sin ventas al gastar 1,5 veces el ticket del producto completo (regla firmada por el dueño el 12-nov; con niveles, el del completo desde el 13-nov); «Escalar» con 3 o más ventas y costo por venta bajo el equilibrio (propuesta, sin firmar); «Sin pauta» si no arrancó; «Pausada» si la campaña está pausada; «Mirar» en lo demás. El «?» de cada pastilla da el detalle.'),
      Object.values(DEFINICIONES).map((def) => el('li', null, el('strong', null, def.titulo), `: ${def.texto}`)),
      el('li', null, el('strong', null, '¿La producción entra en el ROAS? '), PRODUCCION_Y_ROAS),
      el('li', null, 'Colores: verde gana o está sobre el equilibrio; rojo pierde o está debajo; ámbar, mirar; azul, información o programado; gris, sin pauta, pausada o sin dato. La franja de color de cada fila identifica a la oferta, igual que en el menú.'),
      el('li', null, `Referencias del dueño: llega a pagar ${r.checkout[0]}-${r.checkout[1]} % de las visitas; compra ${r.compra[0]}-${r.compra[1]} % de los que llegan a pagar.`),
      el('li', null, 'Costos fijos por mes: ', (c.fijos_mes || []).map((f) => `${f.concepto}: ${f.usd_mes === null ? 'a confirmar (no incluido)' : usd(f.usd_mes)}`).join(' · '), '.'),
      el('li', null, 'Monedas convertidas con los tipos de cambio de Impultienda: ', tc || 'sin dato', '.'),
      el('li', null, 'Los números los carga el agente en cada revisión del funnel. Esta pantalla no cambia nada. Para ver el panel completo de antes, abre la dirección con ', el('code', null, '?modo=completo'), ' antes del #.')),
    ui.detalleTecnico('De dónde salen los datos', () => el('div', { class: 'pila' },
      ui.kv([
        ['Archivo', d.libro ? d.libro.ruta : null],
        ['Modificado', d.libro && d.libro.modificado ? ctx.fmt.fecha(d.libro.modificado, { segundos: true }) : null],
        ['Cálculo', 'dashboard/negocio.py (mismas fórmulas que libro_de_tests.py, más fijos, ROAS Meta y real, equilibrio estimado y veredicto)'],
      ]),
      ui.comando('python3 .claude/skills/escalar-oferta/scripts/libro_de_tests.py --md ofertas/_funnels/libro-de-tests.md', { titulo: 'Imprimir la tabla del libro' }),
      ui.fuenteInfo(sobre))),
  ]);
}

/** Avisos de cuenta (costos fijos que faltan y demás avisos sin oferta): solo si los hay. */
function avisosDeCuenta(ctx, d) {
  const items = (d.atencion || []).filter((it) => it.oferta === null && ['critico', 'grave', 'aviso'].includes(it.tono));
  return items.length ? ctx.ui.atencion({ items: items.map((it) => ({ tono: it.tono, titulo: it.titulo, detalle: it.detalle })) }) : null;
}

function vistaCartera(ctx, sobre) {
  const { ui } = ctx;
  const { el } = ui;
  const d = sobre.datos;
  const ids = identidades(d);
  return el('div', { class: 'pagina' },
    ui.encabezadoPagina({ titulo: 'Negocio', descripcion: 'Qué hacer con cada oferta.', migas: [], acciones: [botonOcultar(ctx.ui), botonActualizar(ctx)] }),
    barraPeriodo(ctx, d, null),
    tresCifras(ui, d.cartera, !d.periodo || d.periodo.con_datos !== false),
    !d.periodo || d.periodo.con_datos !== false ? kpisCartera(ui, d.cartera, conPeriodo(d)) : null,
    !d.periodo || d.periodo.con_datos !== false ? seccionDesglose(ctx, d, hrefOferta) : null,
    franjaVivo(ui, d.en_vivo, d.en_vivo && d.en_vivo.total, null),
    lineaCorte(ui, d.corte, d.libro, d.periodo && !d.periodo.todo ? (d.ofertas || []).map((o) => o.historial_leido).filter(Boolean).sort().pop() || null : null),
    avisosDeCuenta(ctx, d),
    seccionLoQueViene(ctx, d, hrefOferta),
    listaConEtapas(ctx, d, ids),
    seccionComoSeCalcula(ctx, d, sobre),
    sobre.avisos && sobre.avisos.length ? el('ul', { class: ['ng-nota', 'ng-lista'] }, sobre.avisos.map((a) => el('li', null, a))) : null);
}

// Tira de etapas (pedido del dueño, 13-nov): cuántas ofertas hay en cada etapa y cuántas tienen backend; un toque filtra la lista.
// El filtro se recuerda en este navegador (solo comodidad).
const CLAVE_FILTRO = 'negocio.filtroEtapa';
function leerFiltro() { try { return (globalThis.localStorage && globalThis.localStorage.getItem(CLAVE_FILTRO)) || 'todas'; } catch (_) { return 'todas'; } }
function guardarFiltro(f) { try { if (globalThis.localStorage) globalThis.localStorage.setItem(CLAVE_FILTRO, f); } catch (_) { /* sin almacenamiento */ } }

export function botonesTira(ofertas) {
  const c = contarEtapas(ofertas);
  return [
    { clave: 'todas', texto: 'Todas', n: c.todas, tono: null },
    ...ETAPAS.map((e) => ({ clave: e.clave, texto: e.corto || e.texto, n: c[e.clave], tono: tonoEtapa({ clave: e.clave }), ayuda: e.ayuda })),
    { sep: true },
    { clave: 'con_backend', texto: 'Con backend', n: c.con_backend, tono: 'ok', ayuda: 'Ofertas con upsells post-compra activos.' },
    { clave: 'falta_backend', texto: 'Falta backend', n: c.falta_backend, tono: 'aviso', ayuda: 'Pasaron el test y no tienen backend activo.' },
  ];
}

function listaConEtapas(ctx, d, ids) {
  const { ui } = ctx;
  const { el } = ui;
  let filtro = leerFiltro();
  if (!botonesTira(d.ofertas).some((b) => b.clave === filtro)) filtro = 'todas';
  const tira = el('div', { class: 'ng-tira', role: 'toolbar', 'aria-label': 'Filtrar ofertas por etapa o backend' });
  const filas = el('section', { class: 'ng-filas', 'aria-label': 'Ofertas', 'aria-live': 'polite' });
  function pintar() {
    ui.limpiar ? ui.limpiar(tira) : (tira.textContent = '');
    for (const b of botonesTira(d.ofertas)) {
      if (b.sep) { tira.appendChild(el('span', { class: 'ng-tira__sep', 'aria-hidden': 'true' })); continue; }
      tira.appendChild(el('button', { type: 'button', class: ['ng-tira__btn', b.tono && `ng-tira__btn--${b.tono}`, !b.n && b.clave !== 'todas' && 'ng-tira__btn--cero'],
        'aria-pressed': String(filtro === b.clave), title: b.ayuda || '', onclick: () => { filtro = filtro === b.clave ? 'todas' : b.clave; guardarFiltro(filtro); pintar(); } },
      el('span', { class: 'ng-tira__n' }, String(b.n)), b.texto));
    }
    ui.limpiar ? ui.limpiar(filas) : (filas.textContent = '');
    const lista = ordenarOfertas(filtrarOfertas(d.ofertas, filtro));
    if (!lista.length) filas.appendChild(el('p', { class: 'ng-tira__vacio' }, 'Ninguna oferta en esta etapa. Toca «Todas» para ver la lista completa.'));
    for (const o of lista) filas.appendChild(filaOferta(ctx, o, ids[o.id], d));
  }
  pintar();
  return el('div', { class: 'pila' }, tira, filas);
}

/** Ficha: etapa (con sus rondas de creativos) y backend (con sus upsells), uno al lado del otro. */
function bloqueEtapaBackend(ctx, o) {
  const { ui } = ctx;
  const { el } = ui;
  const et = o.etapa || {};
  const b = o.backend || {};
  const renov = o.renovaciones || [];
  const ESTADO_R = { programada: 'programada', activa: 'corriendo', pausada: 'pausada', cancelada: 'cancelada' };
  return el('section', { class: 'ng-eb', 'aria-label': 'Etapa y backend' },
    el('div', { class: 'ng-eb__caja' },
      el('span', { class: 'ng-eb__rot' }, 'Etapa'),
      el('div', null, chipEtapa(ui, et, { corto: false })),
      et.detalle ? el('p', { class: 'ng-eb__det' }, et.detalle) : null,
      renov.length
        ? el('ul', { class: 'ng-eb__lista', 'aria-label': 'Rondas de creativos' }, renov.map((r) => el('li', { title: r.nota || '' },
          `${r.ronda}: ${r.anuncios ? `${r.anuncios} anuncios, ` : ''}${ESTADO_R[r.estado] || r.estado}${r.inicio ? ` desde el ${String(r.inicio).slice(8, 10)}/${String(r.inicio).slice(5, 7)}` : ''}`)))
        : el('p', { class: 'ng-eb__det' }, 'Sin renovaciones de creativos todavía.')),
    el('div', { class: 'ng-eb__caja' },
      el('span', { class: 'ng-eb__rot' }, 'Backend ofensivo'),
      el('div', null, chipBackend(ui, b)),
      (b.upsells || []).length
        ? el('ul', { class: 'ng-eb__lista', 'aria-label': 'Upsells post-compra' }, b.upsells.map((u) => el('li', null, `${u.nombre}${typeof u.precio_usd === 'number' ? ` · ${usd(u.precio_usd)}` : ''}`)))
        : null,
      (b.bumps || []).length
        ? el('ul', { class: 'ng-eb__lista', 'aria-label': 'Order bump del checkout' }, b.bumps.map((u) => el('li', null,
          `Order bump: ${u.nombre}${typeof u.precio_usd === 'number' ? ` · ${usd(u.precio_usd)}` : ''}${u.estado && u.estado !== b.estado ? ` · ${u.estado}` : ''}`)))
        : null,
      el('p', { class: 'ng-eb__det' }, (b.upsells || []).length ? [b.tiendas && b.tiendas.length ? `En ${b.tiendas.length} ${b.tiendas.length === 1 ? 'tienda' : 'tiendas'}. ` : '', b.nota || ''].join('') : detalleBackend(b))));
}

// Confianza en los números (dueño, 14-nov: «el dashboard siempre que lo miro está desactualizado y no me da confianza»):
// cada fila dice de cuándo es su lectura de Meta (en ámbar con más de 2 horas en una oferta activa) y, si en el período hay gasto
// que Meta no repartió por día, lo dice en lugar de mostrar un 0.
export function textoFrescura(horas) {
  if (typeof horas !== 'number' || !Number.isFinite(horas)) return null;
  if (horas < 1) return 'Meta: hace menos de 1 h';
  if (horas < 48) return `Meta: hace ${Math.round(horas)} h`;
  return `Meta: hace ${Math.round(horas / 24)} días`;
}
function chipFrescura(ui, o) {
  const t = textoFrescura(o.corte_horas);
  if (!t) return null;
  const viejo = o.estado === 'activa' && o.corte_horas > 2;
  return ui.el('span', { class: ['ng-etapa', viejo ? 'ng-etapa--aviso' : 'ng-etapa--neutro'],
    title: viejo ? 'La última lectura de Meta tiene más de 2 horas: el gasto real ya es mayor. La vigilancia la actualiza cada hora.' : 'Hora de la última lectura de Meta de esta oferta.' },
  ui.icono('reloj', { tam: 13 }), t);
}
function chipSinDia(ui, o) {
  if (!o.meta_sin_dia) return null;
  return ui.el('span', { class: ['ng-etapa', 'ng-etapa--aviso'], title: 'Meta tiene gasto de esta oferta que todavía no está repartido por día. Para verlo, elegí «Desde el inicio».' },
    ui.icono('alerta', { tam: 13 }), `Meta sin desglose por día: ${usd(o.meta_sin_dia)}`);
}
function avisoSinDia(ui, o) {
  if (!o.meta_sin_dia) return null;
  return ui.atencion({ items: [{ tono: 'aviso', titulo: `Hay ${usd(o.meta_sin_dia)} de gasto en Meta sin repartir por día`,
    detalle: 'En este período el gasto puede figurar más bajo de lo real. «Desde el inicio» lo muestra completo; la vigilancia de cada hora carga el desglose por día.' }] });
}

// ───────────────────────── ficha de una oferta ─────────────────────────

function bloqueVeredicto(ctx, o, d = {}) {
  const { ui } = ctx;
  const { el } = ui;
  const a = o.accion_sugerida || {};
  const prog = (o.programado || [])[0];
  return el('section', { class: 'ng-veredicto', 'aria-label': 'Veredicto' },
    el('div', { class: 'ng-veredicto__fila' }, pastilla(ui, a, { grande: true }), el('span', { class: 'ng-veredicto__frase' }, o.frase || ''), ayudaVeredicto(ui, a), notaVeredicto(ui, d)),
    a.porque ? el('div', { class: 'ng-veredicto__porque' }, a.porque) : null,
    prog ? el('div', { class: 'ng-veredicto__prog' }, ui.icono('reloj', { tam: 14 }), `Programado ${prog.corto || prog.que}`) : null);
}

function kpi(ui, { def, valor, tono, sub, extra }) {
  return ui.el('div', { class: ['ng-kpi', tono && `ng-kpi--${tono}`] },
    ui.el('span', { class: 'ng-kpi__rot' }, def.titulo, ui.ayuda(def)), ui.el('span', { class: 'ng-kpi__valor' }, valor),
    sub ? ui.el('span', { class: 'ng-kpi__sub' }, sub) : null, extra || null);
}
const tonoSigno = (x) => (typeof x === 'number' ? (x >= 0 ? 'ok' : 'error') : null);
const fechaCorta = (f) => (f ? `${f.slice(8, 10)}/${f.slice(5, 7)}` : '');
function barraMeta(ui, valor, meta) {
  const p = typeof valor === 'number' && meta ? Math.max(0, Math.min(1, valor / meta)) : 0;
  const lleno = ui.el('span', { class: 'ng-meta-barra__lleno' });
  lleno.style.width = `${(100 * p).toFixed(2)}%`;
  return ui.el('div', { class: 'ng-meta-barra', role: 'img', 'aria-label': `${numero(100 * p, 1)} % de la meta` }, lleno);
}

/** «Hoy en Meta · en vivo» (meta_vivo.py, cada 10 min, sin Claude): gasto, compras y ROAS de Meta de hoy. */
function franjaVivo(ui, cab, h, presupuesto) {
  const { el } = ui;
  if (!cab || !cab.total) {   // sin ninguna lectura buena todavía
    if (cab && ['falta_token', 'token_invalido', 'permiso'].includes(cab.error)) {
      return el('p', { class: 'ng-nota' }, 'Meta en vivo (cada 10 min, sin gastar): ', el('strong', null, cab.error === 'falta_token' ? 'falta el token de lectura' : 'el token de lectura no sirve'), '. Los pasos están en «Cómo funciona» → «Lo que espera tus manos».');
    }
    return null;
  }
  const viejo = typeof cab.edad_min === 'number' && cab.edad_min > 30;
  const dato = (rot, v) => el('span', { class: 'ng-vivo__dato' }, `${rot} `, el('strong', null, v));
  return el('div', { class: ['ng-vivo', viejo && 'ng-vivo--viejo'], role: 'status' },
    el('span', { class: 'ng-vivo__tit' }, el('span', { class: 'ng-vivo__punto', 'aria-hidden': 'true' }), 'Hoy en Meta'),
    h ? dato('gasto', usd(h.gasto)) : el('span', null, 'sin gasto hoy'),
    h ? dato('compras según Meta', numero(h.compras, 0)) : null,
    h ? dato('ROAS Meta', roas(h.roas_meta)) : null,
    h && typeof h.cpa === 'number' ? dato('CPA', usd(h.cpa)) : null,
    h ? dato('pagos iniciados', numero(h.checkouts, 0)) : null,
    typeof presupuesto === 'number' && presupuesto > 0 ? dato('presupuesto', `${usd(presupuesto)}/día`) : null,
    el('span', { class: 'ng-vivo__sub' }, `${typeof cab.edad_min === 'number' ? `leído hace ${cab.edad_min} min` : ''}${!cab.ok ? ' · última lectura buena' : ''} · se actualiza cada 10 min · compras según Meta; las reales, más abajo`));
}

/** Ventas reales y facturación, primeros KPIs (dueño, 14-nov: «arriba tienen que salir bien las compras… un KPI que sea n de ventas,
 *  facturación»): el número de la tienda, con lo que atribuye Meta al lado para que la diferencia se vea y no se confunda. */
function kpisVentas(ui, o) {
  const meta = typeof o.compras_meta === 'number' ? o.compras_meta : null;
  return [
    kpi(ui, { def: DEFINICIONES.ventas_reales, valor: numero(o.ventas_n || 0, 0),
      sub: meta === null ? 'de la tienda' : meta === o.ventas_n ? `de la tienda · Meta atribuye las ${numero(meta, 0)}` : `de la tienda · Meta atribuye ${numero(meta, 0)}` }),
    kpi(ui, { def: DEFINICIONES.facturacion, valor: o.ventas_n ? usd(o.bruto) : '—', sub: o.ventas_n ? `neto ${usd(o.neto)}` : 'sin ventas todavía' }),
    kpiCpa(ui, o),
    kpiCr(ui, o),
  ];
}

/** CPA del período elegido contra el equilibrio (dueño, 15-nov: «el CPA del día marcado»). */
function kpiCpa(ui, o) {
  const cpa = typeof o.cpa === 'number' ? o.cpa : null;
  const eq = typeof o.equilibrio === 'number' ? o.equilibrio : null;
  const eqTxt = eq === null ? '' : `equilibrio ${usd(eq)}${o.equilibrio_fuente === 'estimado' ? ' (estimado)' : ''}`;
  if (cpa === null) {
    return kpi(ui, { def: DEFINICIONES.cpa_periodo, valor: '—', sub: o.gasto_meta ? `sin ventas · gastó ${usd(o.gasto_meta)}${eqTxt ? ` · ${eqTxt}` : ''}` : 'sin gasto en el período' });
  }
  return kpi(ui, { def: DEFINICIONES.cpa_periodo, valor: usd(cpa), tono: eq === null ? null : (cpa <= eq ? 'ok' : 'error'),
    sub: `${usd(o.gasto_meta)} ÷ ${numero(o.ventas_n, 0)} ventas${eqTxt ? ` · ${eqTxt}` : ''}` });
}

/** CR consolidado de todas las tiendas del funnel (dueño, 14-nov: «hay que juntarlas las 3 y sacar 1 KPI»). */
const REF_CR = [2, 3.6];
function kpiCr(ui, o) {
  const e = o.embudo || {};
  const n = (o.por_tienda || []).length;
  if (e.incompleto || !e.visitas) return kpi(ui, { def: DEFINICIONES.cr_tienda, valor: '—', sub: e.incompleto ? 'falta la lectura de algún día' : 'sin visitas leídas todavía' });
  return kpi(ui, { def: DEFINICIONES.cr_tienda, valor: pct(e.pct_compra_visita, 2), tono: e.checkout >= 5 ? tonoTasa(e.pct_compra_visita, REF_CR) : null,
    sub: `${numero(e.compras, 0)} compras ÷ ${numero(e.visitas, 0)} visitas${n > 1 ? ` · ${n} tiendas juntas` : ''}` });
}

/** KPIs de una oferta (dueño, 13-nov: «falta el AOV, el margen neto…»). */
/** Con un período elegido (Hoy, Ayer, un rango) la «Ganancia del último día» no se muestra: confundía (dueño, 15-nov:
 *  «si quiero ver el día anterior, filtro y ya»). Solo queda en «Desde el inicio». */
const conPeriodo = (d) => Boolean(d.periodo && !d.periodo.todo);

function kpisOferta(ui, o, periodo = false) {
  const k = o.kpis || {};
  if (o.con_datos_periodo === false || !o.ventas_n) {
    return ui.el('section', { class: 'ng-kpis', 'aria-label': 'Indicadores' },
      ...kpisVentas(ui, o),
      kpi(ui, { def: DEFINICIONES.aov, valor: '—', sub: k.precio_principal ? `sin ventas todavía · principal ${usd(k.precio_principal)}` : 'sin ventas todavía' }));
  }
  const veces = k.aov_veces_principal;
  return ui.el('section', { class: 'ng-kpis', 'aria-label': 'Indicadores' },
    ...kpisVentas(ui, o),
    kpi(ui, { def: DEFINICIONES.aov, valor: usd(k.aov), tono: typeof veces === 'number' ? (veces >= 1.5 ? 'ok' : veces >= 1 ? 'aviso' : 'error') : null,
      sub: `${typeof veces === 'number' ? `${numero(veces)} × el principal (${usd(k.precio_principal)}) · ref. 1,5 ×` : ''}${typeof k.aov_neto === 'number' ? ` · deja ${usd(k.aov_neto)} neto` : ''}` }),
    kpi(ui, { def: DEFINICIONES.margen_contra_meta, valor: pct(k.margen_contra_meta_pct), tono: tonoSigno(k.margen_contra_meta_pct), sub: 'neto − Meta, sobre lo facturado' }),
    kpi(ui, { def: DEFINICIONES.margen_neto, valor: pct(k.margen_neto_pct), tono: tonoSigno(k.margen_neto_pct), sub: 'con producción y fijos' }),
    kpi(ui, { def: DEFINICIONES.take_rate, valor: pct(k.take_rate_pct), sub: `${numero(k.ventas_extra_n, 0)} extra en ${numero(o.ventas_n, 0)} compradores` }),
    periodo ? null : kpi(ui, { def: DEFINICIONES.ganancia_dia, valor: typeof k.ganancia_ultimo_dia === 'number' ? usd(k.ganancia_ultimo_dia, { signo: true }) : '—', tono: tonoSigno(k.ganancia_ultimo_dia),
      sub: k.ultimo_dia ? `el ${fechaCorta(k.ultimo_dia)}, contra Meta` : 'sin día completo leído' }),
    kpi(ui, { def: DEFINICIONES.comision_pct, valor: pct(k.comision_pct), sub: 'de lo facturado' }));
}

/** KPIs de la cartera, con la meta de 10.000 USD netos por día. */
function kpisCartera(ui, c, periodo = false) {
  if (!c || !c.ventas) return null;
  const meta = c.meta_ganancia_dia || 10000;
  const g = c.ganancia_ultimo_dia;
  return ui.el('section', { class: 'ng-kpis', 'aria-label': 'Indicadores de la cartera' },
    periodo ? null : kpi(ui, { def: DEFINICIONES.ganancia_dia, valor: typeof g === 'number' ? usd(g, { signo: true }) : '—', tono: tonoSigno(g),
      sub: `${c.ultimo_dia_completo ? `el ${fechaCorta(c.ultimo_dia_completo)} · ` : ''}meta ${usd(meta)} por día`, extra: barraMeta(ui, g, meta) }),
    // dueño, 15-nov: «agregar el KPI de facturación neta después de comisiones» y «el CPA del día marcado»
    kpi(ui, { def: DEFINICIONES.facturacion_neta_cartera, valor: usd(c.neto),
      sub: `bruto ${usd(c.bruto)} · comisiones ${usd(c.comisiones)}${c.bruto ? ` (${pct(100 * (c.comisiones || 0) / c.bruto)})` : ''}` }),
    kpi(ui, { def: DEFINICIONES.cpa_periodo, valor: typeof c.cpa_medio === 'number' ? usd(c.cpa_medio) : '—',
      tono: typeof c.cpa_medio === 'number' && typeof c.equilibrio_medio === 'number' ? (c.cpa_medio <= c.equilibrio_medio ? 'ok' : 'error') : null,
      sub: `${numero(c.ventas, 0)} ventas${typeof c.equilibrio_medio === 'number' ? ` · equilibrio ${usd(c.equilibrio_medio)}` : ''}` }),
    kpi(ui, { def: DEFINICIONES.aov, valor: usd(c.aov), sub: 'todas las ofertas' }),
    kpi(ui, { def: DEFINICIONES.margen_contra_meta, valor: pct(c.margen_contra_meta_pct), tono: tonoSigno(c.margen_contra_meta_pct), sub: 'neto − Meta, sobre lo facturado' }),
    kpi(ui, { def: DEFINICIONES.margen_neto, valor: pct(c.margen_neto_pct), tono: tonoSigno(c.margen_neto_pct), sub: 'con producción y fijos' }));
}

function tresCifrasOferta(ui, o) {
  if (o.con_datos_periodo === false) return tresCifras(ui, {}, false);
  const tg = tonoDinero(o.ganancia_neta);
  return ui.el('section', { class: 'ng-tres', 'aria-label': 'La oferta en tres números' },
    cifra(ui, { etiqueta: 'Ganancia neta', valor: usd(o.ganancia_neta, { signo: true }), tono: tg, icono: ICONO_TONO[tg], sub: el2(ui, 'Contra Meta ', resultado(ui, o.ganancia_contra_meta)), ayuda: DEFINICIONES.ganancia_neta }),
    cifra(ui, { etiqueta: 'Gasto en anuncios', valor: usd(-Math.abs(o.gasto_meta || 0)), tono: 'info', sub: `${numero(o.ventas_n, 0)} ventas reales` }),
    ui.el('div', { class: ['ng-cifra', tonoRoas(o.gasto_meta ? o.roas_neto : null) && `ng-cifra--${tonoRoas(o.roas_neto)}`] },
      medidor(ui, { titulo: 'ROAS neto', valor: o.gasto_meta ? o.roas_neto : null, equilibrio: 1, formato: roas, ayuda: DEFINICIONES.roas_neto, grande: true })));
}
const el2 = (ui, ...h) => ui.el('span', null, ...h);

// Desglose de la producción (17-nov): de dónde sale cada dólar. Kie (créditos), renovación (lo producido desde la salida),
// imágenes y voces de Gemini. «medido» = barrido de los gasto*.jsonl y del audio; «cargado» = lo anotado a mano.
function desgloseProduccion(ui, p) {
  if (!p || typeof p !== 'object') return [];
  const { el } = ui;
  const nota = el('tr', { class: 'ng-sub ng-sub--nota' }, el('td', { colspan: '2' },
    'Sale de los registros de gasto de cada carpeta (Kie e imágenes de Gemini) y del audio de las voces; si lo anotado a mano es mayor, manda lo anotado.'));
  const n0 = (x) => numero(x || 0, 0);
  const sub = (txt, valor, detalle) => el('tr', { class: 'ng-sub' },
    el('td', null, el('span', { class: 'ng-sub__rot' }, txt), detalle ? el('span', { class: 'ng-sub__det' }, detalle) : null),
    el('td', null, valor));
  const filas = [];
  if (p.kie_usd) {
    const fuente = p.kie_barrido && p.kie_manual && Math.abs(p.kie_barrido - p.kie_manual) > 50
      ? ` · medido ${n0(p.kie_barrido)}, cargado ${n0(p.kie_manual)}` : '';
    filas.push(sub('Kie (imágenes, clips, música)', sale(ui, p.kie_usd), `${n0(p.kie_creditos)} créditos${fuente}`));
  }
  if (p.renovacion_kie) filas.push(sub('· de eso, renovación y backend', sale(ui, p.kie_creditos ? (p.kie_usd * p.renovacion_kie) / p.kie_creditos : 0), `${n0(p.renovacion_kie)} créditos desde la salida`));
  if (p.gemini_usd) filas.push(sub('Imágenes de Gemini', sale(ui, p.gemini_usd), `${n0(p.gemini_imagenes)} imágenes`));
  if (p.voces_usd || p.voces_min) filas.push(sub('Voces de Gemini (TTS)', sale(ui, p.voces_usd), `${numero(p.voces_min || 0, 1)} min de audio`));
  if (p.otros_usd) filas.push(sub('Otros', sale(ui, p.otros_usd)));
  return filas.length ? filas.concat(nota) : filas;
}

// Fijos abiertos por concepto (17-nov): cuánto le tocó a la oferta de cada plan o servicio mensual.
function desgloseFijos(ui, o) {
  const det = Array.isArray(o.fijos_detalle) ? o.fijos_detalle : [];
  if (!det.length) return [];
  const { el } = ui;
  return det.map((x) => el('tr', { class: 'ng-sub' },
    el('td', null, el('span', { class: 'ng-sub__rot' }, String(x.concepto || '').split(' (')[0]), el('span', { class: 'ng-sub__det' }, `${usd(x.usd_mes)} por mes`)),
    el('td', null, sale(ui, x.usd))))
    .concat(el('tr', { class: 'ng-sub ng-sub--nota' }, el('td', { colspan: '2' },
      `Cada día se divide el total mensual por 30 y se reparte entre las ofertas que pautaron ese día · ${numero(o.dias_pauta || 0, 0)} días de pauta.`)));
}

function tablaMetricas(ctx, o) {
  const { ui } = ctx;
  const { el } = ui;
  const D = DEFINICIONES;
  const k = o.costos || {};
  const conGasto = Boolean(o.gasto_meta);
  const eqTxt = o.equilibrio === null ? '—' : `${usd(o.equilibrio)}${o.equilibrio_fuente === 'estimado' ? ' (estimado)' : ''}`;
  const grupo = (t) => el('tr', null, el('th', { colspan: '2', scope: 'colgroup' }, t));
  const fila = (def, valor, { total = false } = {}) => el('tr', { class: total ? 'ng-total' : null }, el('td', null, def.titulo, ui.ayuda(def)), el('td', null, valor));
  const roasCel = (x) => (conGasto ? signoRoas(ui, x) : '—');
  const cpaTono = o.cpa !== null && o.equilibrio ? (o.cpa <= o.equilibrio ? 'ng-pos' : 'ng-neg') : null;
  return ui.seccion('Métricas del funnel', el('div', { class: 'pila' },
    el('table', { class: 'ng-tabla-met' }, el('tbody', null,
      grupo('Facturación'),
      fila(D.facturacion_bruta, usd(o.bruto)),
      fila(D.comisiones, sale(ui, o.comisiones)),
      fila(D.facturacion_neta, entra(ui, o.neto), { total: true }),
      grupo('Costos'),
      fila(D.costo_meta, sale(ui, k.meta)),
      fila(D.costo_produccion, sale(ui, k.produccion)),
      ...desgloseProduccion(ui, o.produccion),
      fila(D.costo_fijos, sale(ui, k.fijos)),
      ...desgloseFijos(ui, o),
      fila(D.costo_total, sale(ui, k.total), { total: true }),
      grupo('Ganancia'),
      fila(D.ganancia_contra_meta, conGasto ? resultado(ui, o.ganancia_contra_meta) : '—'),
      fila(D.ganancia_neta, resultado(ui, o.ganancia_neta), { total: true }),
      grupo('ROAS (equilibrio 1,00 ×)'),
      fila(D.roas_meta, roasCel(o.roas_meta)),
      fila(D.roas_bruto, roasCel(o.roas_bruto)),
      fila(D.roas_neto, roasCel(o.roas_neto), { total: true }),
      fila(D.roas_real, signoRoas(ui, o.roas_real)),
      grupo('Ventas'),
      fila(D.ventas, `${numero(o.ventas_n, 0)} reales · ${numero(o.compras_meta, 0)} según Meta`),
      fila(D.ticket_medio, usd(o.ticket_medio)),
      fila(D.take_rate, pct((o.kpis || {}).take_rate_pct)),
      fila(D.cpa_real, el('span', { class: cpaTono }, usd(o.cpa))),
      fila(D.cpa_equilibrio, eqTxt),
      grupo('Margen (sobre facturación bruta)'),
      fila(D.margen_contra_meta, pct((o.kpis || {}).margen_contra_meta_pct)),
      fila(D.margen_neto, pct((o.kpis || {}).margen_neto_pct), { total: true }))),
    el('p', { class: 'ng-nota' }, 'La producción no entra en el ROAS; sí en el ROAS real y en la ganancia neta. ', ui.ayuda({ titulo: '¿La producción entra en el ROAS?', texto: PRODUCCION_Y_ROAS }))));
}

function seccionEmbudo(ctx, o, ref) {
  const { ui } = ctx;
  const { el } = ui;
  const e = o.embudo || {};
  const tiendas = (o.por_tienda || []).filter((x) => x.embudo);
  const titulo = `Embudo de la tienda${tiendas.length > 1 ? ` · ${tiendas.length} tiendas juntas` : ''}`;
  if (e.incompleto) return ui.seccion(titulo, el('p', { class: 'ng-nota' }, 'Sin dato completo para este período: falta la lectura de Impultienda de algún día. No se inventa.'));
  if (!e.visitas && !e.checkout) return ui.seccion(titulo, el('p', { class: 'ng-nota' }, 'Todavía no hay visitas leídas de la tienda en este período.'));
  const ICON = { ok: 'check', aviso: 'alerta', error: 'x-circulo' };
  const base = Math.max(e.visitas || 0, e.checkout || 0, 1);
  const barra = (n, rot, clase) => {
    const lleno = el('span', { class: ['ng-emb__lleno', clase] });
    lleno.style.width = `${Math.max(0.6, (100 * (n || 0)) / base).toFixed(2)}%`;
    return el('div', { class: 'ng-emb__fila' },
      el('span', { class: 'ng-emb__rot' }, rot),
      el('span', { class: 'ng-emb__pista', role: 'img', 'aria-label': `${rot}: ${numero(n, 0)}` }, lleno),
      el('span', { class: 'ng-emb__n' }, numero(n, 0)));
  };
  const paso = (p, texto, banda) => {
    const tono = banda && e.checkout >= 5 ? tonoTasa(p, banda) : null;
    return el('div', { class: 'ng-emb__paso' }, '↓ ',
      el('b', { class: tono && `ng-txt--${tono}` }, tono ? ui.icono(ICON[tono], { tam: 13 }) : null, pctTxt(p)), ` ${texto}`,
      banda ? el('span', { class: 'ng-emb__ref' }, ` · referencia ${banda[0]}-${banda[1]} %`) : null);
  };
  const cuerpo = [
    el('div', { class: 'ng-emb' },
      barra(e.visitas, 'Visitas a la landing', 'ng-emb__lleno--1'),
      paso(e.pct_checkout, 'llegan a pagar', ref.checkout),
      barra(e.checkout, 'Checkouts', 'ng-emb__lleno--2'),
      paso(e.pct_compra, 'compran', ref.compra),
      barra(e.compras, 'Compras', 'ng-emb__lleno--3')),
    el('p', { class: 'ng-emb__cr' }, 'CR de la tienda: ', el('b', {}, pctTxt(e.pct_compra_visita, 2)), ` (${numero(e.compras, 0)} compras ÷ ${numero(e.visitas, 0)} visitas)`),
  ];
  if (tiendas.length > 1) {
    const crImpul = (x) => (x.landing ? pct((100 * x.compras) / x.landing, 2) : '—');
    cuerpo.push(el('details', { class: 'ng-emb__det' },
      el('summary', {}, 'Por tienda (lo que muestra Impultienda por separado)'),
      el('table', { class: 'ng-emb__tabla' },
        el('thead', {}, el('tr', {}, el('th', {}, 'Tienda'), el('th', {}, 'Visitas'), el('th', {}, 'Checkouts'), el('th', {}, 'Compras'), el('th', {}, 'CR en Impultienda'))),
        el('tbody', {}, ...tiendas.map((x) => el('tr', {}, el('td', {}, x.nombre || x.slug), el('td', {}, numero(x.embudo.landing, 0)),
          el('td', {}, numero(x.embudo.checkout, 0)), el('td', {}, numero(x.embudo.compras, 0)), el('td', {}, crImpul(x.embudo)))))),
      el('p', { class: 'ng-nota' }, 'La landing está en una tienda y los botones de cada nivel llevan al checkout de las otras: por eso el CR de cada una por separado no sirve. El que vale es el de arriba.')));
  }
  return ui.seccion(titulo, cuerpo,
    { ayuda: [e.parcial ? 'Hoy todavía no terminó: es la lectura de Impultienda a esa hora.' : null, e.pocos_datos && e.checkout ? `Con ${numero(e.checkout, 0)} checkouts, una venta mueve el porcentaje varios puntos: es una pista.` : null].filter(Boolean).join(' ') || null });
}

function vistaFicha(ctx, sobre, id) {
  const { ui } = ctx;
  const { el } = ui;
  const d = sobre.datos;
  const real = resolverRef(id, IDS);
  const o = (d.ofertas || []).find((x) => x.id === real);
  const migas = [{ texto: 'Negocio', ruta: 'negocio' }, { texto: o ? o.nombre : id }];
  if (!o) {
    return el('div', { class: 'pagina' },
      ui.encabezadoPagina({ titulo: 'Oferta no encontrada', descripcion: 'Esa oferta no está en el libro de tests.', migas }),
      ui.vacio('Vuelve a Negocio y elige una de la lista.', { icono: 'caja' }));
  }
  const clase = identidades(d)[o.id];
  const est = estadoOferta(o.estado);
  return el('div', { class: ['pagina', clase] },
    ui.encabezadoPagina({
      titulo: el('span', { class: 'ng-ficha-tit' }, el('span', { class: 'ng-id-punto', 'aria-hidden': 'true' }), o.nombre, banderas(ui, o.mercado, { conNombre: true })),
      descripcion: `${nombresPais(o.mercado)} · ${est.texto.toLowerCase()}${o.por_tienda.length > 1 ? ` · ${o.por_tienda.length} tiendas` : ''}`,
      migas,
      acciones: [botonOcultar(ctx.ui), botonActualizar(ctx)],
    }),
    barraPeriodo(ctx, d, o.id),
    // dueño, 14-nov: «cuando entrás a cada oferta, primero tiene que estar todo el container de los KPIs, no el historial y demás».
    // Orden: KPIs (cifras, indicadores con el CR, embudo de las tiendas juntas, Meta en vivo, hora de los datos) → decisión (veredicto, etapa y backend) → métricas, embudo y
    // anuncios → agenda, países del original, historial y ventas → enlaces.
    tresCifrasOferta(ui, o),
    kpisOferta(ui, o, conPeriodo(d)),
    // dueño, 14-nov: el embudo consolidado de las tiendas (visitas, checkouts, compras y CR) va con los KPIs, arriba
    o.con_datos_periodo === false ? null : seccionEmbudo(ctx, o, d.referencias),
    franjaVivo(ui, d.en_vivo, o.en_vivo && o.en_vivo.hoy, o.en_vivo && o.en_vivo.presupuesto),
    lineaCorte(ui, { ultimo: o.corte, horas: o.corte_horas, viejo: o.corte_horas !== null && o.corte_horas > d.referencias.horas_datos_viejos }, d.libro, d.periodo && !d.periodo.todo ? o.historial_leido : null),
    avisoSinDia(ui, o),
    bloqueVeredicto(ctx, o, d),
    bloqueEtapaBackend(ctx, o),
    ...(o.con_datos_periodo === false
      ? [ui.seccion('Sin datos en este período', el('p', { class: 'ng-nota' }, 'Esta oferta no tuvo gasto ni ventas en los días elegidos. Elige otro período o «Desde el inicio».'))]
      : [tablaMetricas(ctx, o)]),
    // dueño, 16-nov: campañas, conjuntos y anuncios como en Meta + la línea de tiempo del presupuesto (qué se subió, qué se bajó, quién y por qué)
    seccionCampanasMeta(ctx, o, RANGO, aovEscala(o, d)),
    ...(o.con_datos_periodo === false ? [] : [seccionAnuncios(ctx, o, clase)]),
    seccionAgenda(ctx, o),
    seccionReferentePaises(ctx, o),
    ...(o.con_datos_periodo === false ? [] : [seccionHistorial(ctx, o), seccionVentas(ctx, o)]),
    seccionEnlaces(ctx, o));
}

/** El AOV que usa la escala por campaña (escalar_presupuesto.py): el de la oferta con 5 compradores o más; si no, el de la madre (réplicas). */
function aovEscala(o, d) {
  const propio = o.kpis && typeof o.kpis.aov === 'number' ? o.kpis.aov : null;
  if ((o.ventas_n || 0) >= 5 || !o.replica_de) return propio;
  const madre = (d.ofertas || []).find((x) => x.nombre === o.replica_de);
  return (madre && madre.kpis && typeof madre.kpis.aov === 'number') ? madre.kpis.aov : propio;
}

const ESTADO_AD = { ACTIVE: 'activo', PAUSED: 'en pausa', ADSET_PAUSED: 'conjunto en pausa', CAMPAIGN_PAUSED: 'campaña en pausa', IN_PROCESS: 'en revisión', WITH_ISSUES: 'con problemas', DISAPPROVED: 'rechazado' };
const ICONO_VAD = { ganador: 'tendencia-sube', promete: 'chispa', sin_datos: 'circulo-punteado', flojo: 'x-circulo', mirar: 'ojo' };

function pastillaAnuncio(ui, v) {
  return ui.el('span', { class: ['ng-vad', `ng-vad--${(v && v.clave) || 'mirar'}`] }, ui.icono(ICONO_VAD[v && v.clave] || 'ojo', { tam: 13 }), (v && v.texto) || 'Mirar');
}

const pctTxt = (x, d = 1) => (typeof x === 'number' ? pct(x, d) : '—');

// Miniaturas de los creativos: las baja nube_sync a ofertas/_funnels/_miniaturas/ (el panel no carga imágenes de afuera) y se piden de a una.
const MINIATURAS = new Map();
const RX_DATA_IMG = /^data:image\/(jpeg|png|webp|gif);base64,[A-Za-z0-9+/=]+$/;
/** <img> con una data-URL de imagen del propio panel (ui.el no acepta «data:» en src; se valida acá y se asigna aparte). */
function imagenData(ui, src, attrs) {
  const img = ui.el('img', attrs);
  if (typeof src === 'string' && RX_DATA_IMG.test(src)) img.src = src;
  return img;
}
function miniatura(ctx, a, tam = 44) {
  const { ui } = ctx;
  const caja = ui.el('span', { class: 'ng-mini', style: { width: `${tam}px`, height: `${tam}px` }, 'aria-hidden': a.miniatura ? null : 'true' });
  if (!a.miniatura) { caja.appendChild(ui.icono('pantalla', { tam: 16 })); return caja; }
  const poner = (src) => { if (src) { ui.reemplazar(caja, imagenData(ui, src, { alt: `Miniatura de ${a.nombre || 'el anuncio'}`, loading: 'lazy' })); } else ui.reemplazar(caja, ui.icono('pantalla', { tam: 16 })); };
  const prev = MINIATURAS.get(a.miniatura);
  if (typeof prev === 'string') poner(prev);
  else {
    const p = prev || ctx.api.sobre('/negocio/documento', { ruta: a.miniatura }).then((r) => (r && r.datos && r.datos.contenido) || null).catch(() => null);
    MINIATURAS.set(a.miniatura, p);
    p.then((src) => { MINIATURAS.set(a.miniatura, src || ''); poner(src); });
  }
  caja.classList.add('ng-mini--clic');
  caja.setAttribute('role', 'button');
  caja.setAttribute('tabindex', '0');
  caja.setAttribute('title', 'Ver la miniatura grande');
  const abrir = () => {
    const src = MINIATURAS.get(a.miniatura);
    if (typeof src === 'string' && src) ui.modal({ titulo: a.nombre || 'Creativo', cuerpo: imagenData(ui, src, { alt: a.nombre || '', class: 'ng-img' }), ancho: '420px' });
  };
  caja.addEventListener('click', abrir);
  caja.addEventListener('keydown', (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); abrir(); } });
  return caja;
}

const usdTxt = (v) => (typeof v === 'number' ? usd(v) : '—');

/** Columnas con todos los KPIs de un creativo o anuncio (pedido del dueño, 15-nov). */
/** ROAS de 3 días (50/30/20, acercado a la oferta) con su rango: verde si hasta el piso gana, rojo si ni el techo empata. */
function roas3d(ui, r) {
  const { el } = ui;
  if (!r || typeof r.roas !== 'number') return '—';
  const f = (x) => x.toFixed(2).replace('.', ',');
  const tono = r.piso >= 1 ? 'ng-r3d--ok' : r.techo < 1 ? 'ng-r3d--mal' : 'ng-r3d--duda';
  return el('span', { class: ['ng-r3d', tono], title: `Últimos 3 días pesando hoy 50 %, ayer 30 %, anteayer 20 % (${numero(r.compras, 0)} compras, US$ ${f(r.gasto)}), acercado al CPA de la oferta en 7 días. Visto: ${f(r.crudo)}. Rango probable (80 %): ${f(r.piso)} a ${f(r.techo)}. Verde: hasta el piso gana · rojo: ni el techo empata · gris: todavía no se sabe.` },
    el('b', null, `${f(r.roas)} ×`), el('small', null, `${f(r.piso)}–${f(r.techo)}`));
}

function columnasKpis(ctx, { conPuesto, nombreCel, roasCel }) {
  const { ui } = ctx;
  const { el } = ui;
  return [
    conPuesto ? { clave: 'puesto', titulo: '#', numerico: true, formato: (v) => el('b', null, v) } : null,
    { clave: 'nombre', titulo: conPuesto ? 'Creativo' : 'Anuncio', flex: true, formato: (_v, a) => nombreCel(a) },
    { clave: 'veredicto.texto', titulo: 'Veredicto', formato: (_v, a) => pastillaAnuncio(ui, a.veredicto) },
    { clave: 'gasto_usd', titulo: 'Gasto', numerico: true, formato: (v) => sale(ui, v) },
    { clave: 'compras_meta', titulo: 'Compras', numerico: true, formato: (v) => numero(v, 0) },
    { clave: 'cpa', titulo: 'CPA', numerico: true, formato: usdTxt },
    { clave: 'roas_meta', titulo: 'ROAS Meta', numerico: true, formato: (v, a) => roasCel(v, a) },
    { clave: 'roas_neto_estimado', titulo: 'ROAS neto est.', numerico: true, formato: (v, a) => roasCel(v, a) },
    { clave: 'roas_3d.roas', titulo: 'ROAS 3 d', numerico: true, formato: (_v, a) => roas3d(ui, a.roas_3d) },
    { clave: 'inicios_pago_meta', titulo: 'Pagos inic.', numerico: true, formato: (v) => numero(v, 0) },
    { clave: 'costo_pago', titulo: 'Costo pago inic.', numerico: true, formato: usdTxt },
    { clave: 'pago_compra_pct', titulo: 'Pago → compra', numerico: true, formato: (v) => pctTxt(v) },
    { clave: 'clic_pago_pct', titulo: 'Clic → pago', numerico: true, formato: (v) => pctTxt(v) },
    { clave: 'ctr_pct', titulo: 'CTR', numerico: true, formato: (v) => pctTxt(v, 2) },
    { clave: 'cpc', titulo: 'CPC', numerico: true, formato: usdTxt },
    { clave: 'cpm', titulo: 'CPM', numerico: true, formato: usdTxt },
    { clave: 'hook_pct', titulo: 'Gancho 3 s', numerico: true, formato: (v) => pctTxt(v) },
    { clave: 'retencion_25_pct', titulo: 'Ven 25 %', numerico: true, formato: (v) => pctTxt(v) },
    { clave: 'retencion_50_pct', titulo: 'Ven 50 %', numerico: true, formato: (v) => pctTxt(v) },
    { clave: 'retencion_pct', titulo: 'Ven todo', numerico: true, formato: (v) => pctTxt(v) },
    { clave: 'impresiones', titulo: 'Impresiones', numerico: true, formato: (v) => numero(v, 0) },
    { clave: 'clics_enlace', titulo: 'Clics', numerico: true, formato: (v) => numero(v, 0) },
  ].filter(Boolean);
}

/** Top 20 creativos de la oferta (dueño, 15-nov) con todos sus KPIs, y debajo todos los anuncios conjunto por conjunto. */
function seccionAnuncios(ctx, o, clase) {
  const { ui } = ctx;
  const { el } = ui;
  const A = o.anuncios || { lista: [] };
  const lista = A.lista || [];
  const top = A.top || [];
  if (!lista.length) return ui.seccion('Creativos', el('p', { class: 'ng-nota' }, 'Todavía no hay lectura de Meta por anuncio para esta oferta: la nube la trae sola cada 5 minutos en cuanto la campaña tiene impresiones.'));
  const variosConjuntos = (A.conjuntos || []).length > 1;
  const V = A.neto_ventana;
  const fechaCorta = (iso) => (iso ? `${Number(iso.slice(8, 10))}-${['ene', 'feb', 'mar', 'abr', 'may', 'jun', 'jul', 'ago', 'sep', 'oct', 'nov', 'dic'][Number(iso.slice(5, 7)) - 1]}` : '');
  const ventanaTxt = V ? `${V.dias ? `últimos ${V.dias} días` : 'toda la historia'} (${fechaCorta(V.desde)} al ${fechaCorta(V.hasta)}) · ${numero(V.compradores, 0)} compradores` : null;
  const ayudaRoasEst = { titulo: 'ROAS neto estimado', texto: `Compras que Meta atribuye al anuncio × neto medio por comprador de la oferta (${usd(A.neto_por_venta)}${A.neto_estimado ? ', estimado' : ''}) ÷ gasto del anuncio.${ventanaTxt ? ` El neto por comprador sale de los ${ventanaTxt}, no del período elegido: así un día con muchos o pocos upsells no mueve el número. Ventana: 7 días; con menos de 50 compradores, 14; si tampoco llega, toda la historia. Upsells y bumps suman al neto pero no cuentan como compradores.` : ''} Es estimado: Meta reparte las compras entre anuncios, pero el neto real es de la oferta entera.` };
  const ayudaVeredicto = { titulo: 'Veredicto por anuncio', texto: 'Ganador: ROAS neto estimado ≥ 1 con 2 o más compras. Promete: 1 compra y ROAS neto estimado ≥ 1. Sin datos: gastó menos de US$ 2. Flojo: gastó 1,5 veces el ticket del front sin compras (la regla firmada, aplicada por anuncio). Mirar: lo demás.' };
  const ayudaTop = { titulo: 'Cómo se ordena el top', texto: '«ROAS 3 d» = los últimos 3 días del creativo pesando hoy 50 %, ayer 30 %, anteayer 20 %, acercado al CPA de la oferta en 7 días; abajo, el rango probable (80 %). Verde: hasta el piso gana; rojo: ni el techo empata; gris: todavía no se sabe. Un creativo es el mismo anuncio (mismo nombre) sumado en todos los conjuntos donde corre. Orden: más compras primero; a igualdad, menor CPA; sin compras, primero los que ya gastaron US$ 2 (los «Sin datos» van al final) y entre ellos más pagos iniciados, mejor CTR y más gasto. Puedes reordenar por cualquier columna tocando su título. Gancho 3 s = reproducciones de 3 segundos ÷ impresiones; «Ven 25 %», «Ven 50 %» y «Ven todo» = % de las impresiones que llegan a esa parte del video.' };
  const sub = (a, creativo) => [ESTADO_AD[a.estado] || (a.estado || '').toLowerCase(),
    creativo ? ((a.conjuntos || []).length > 1 ? `en ${a.conjuntos.length} conjuntos` : (a.conjuntos || [])[0]) : (variosConjuntos ? a.conjunto : null)].filter(Boolean).join(' · ');
  const nombreCon = (creativo) => (a) => el('span', { class: 'ng-ad-fila' }, miniatura(ctx, a),
    el('span', { class: 'ng-ad-nombre' },
      el('span', { class: 'ng-ad-nombre__t', title: a.nombre }, a.nombre),
      el('span', { class: 'ng-ad-nombre__sub', title: creativo ? (a.conjuntos || []).join('\n') : null }, sub(a, creativo))));
  // con menos de US$ 2 gastados el ROAS no dice nada: se muestra apagado, sin verde ni rojo
  const roasCel = (x, a) => (typeof x !== 'number' ? '—' : a && a.veredicto && a.veredicto.clave === 'sin_datos' ? el('span', { class: 'ng-sale' }, roas(x)) : signoRoas(ui, x));
  const claseFila = (a) => (a.veredicto && a.veredicto.clave === 'ganador' ? 'ng-ad-ganador' : null);
  const tablaTop = ui.tabla({
    etiqueta: `Top ${top.length} creativos`, claseFila,
    columnas: columnasKpis(ctx, { conPuesto: true, nombreCel: nombreCon(true), roasCel }),
    filas: top, maxFilas: 20, ordenInicial: { clave: 'puesto', dir: 'asc' },
  });
  const tarjeta = (a) => el('div', { class: ['ng-ad-tarjeta', claseFila(a)] },
    el('div', { class: 'ng-ad-tarjeta__cab' }, el('b', { class: 'ng-ad-puesto' }, `#${a.puesto}`), nombreCon(true)(a), pastillaAnuncio(ui, a.veredicto)),
    el('dl', { class: 'ng-ad-tarjeta__cifras' },
      ...[['Gasto', sale(ui, a.gasto_usd)], ['Compras', numero(a.compras_meta, 0)], ['CPA', usdTxt(a.cpa)], ['ROAS neto est.', roasCel(a.roas_neto_estimado, a)]]
        .map(([k, v]) => el('div', null, el('dt', null, k), el('dd', null, v)))),
    el('details', { class: 'ng-ad-tarjeta__mas' }, el('summary', null, 'Todos los KPIs'),
      el('dl', { class: 'ng-ad-tarjeta__cifras' },
        ...[['ROAS Meta', roasCel(a.roas_meta, a)], ['Pagos iniciados', numero(a.inicios_pago_meta, 0)], ['Costo pago inic.', usdTxt(a.costo_pago)], ['Pago → compra', pctTxt(a.pago_compra_pct)],
          ['Clic → pago', pctTxt(a.clic_pago_pct)], ['CTR', pctTxt(a.ctr_pct, 2)], ['CPC', usdTxt(a.cpc)], ['CPM', usdTxt(a.cpm)],
          ['Gancho 3 s', pctTxt(a.hook_pct)], ['Ven 25 %', pctTxt(a.retencion_25_pct)], ['Ven 50 %', pctTxt(a.retencion_50_pct)], ['Ven todo', pctTxt(a.retencion_pct)]]
          .map(([k, v]) => el('div', null, el('dt', null, k), el('dd', null, v))))));
  const todos = el('details', { class: 'ng-ad-todos' },
    el('summary', null, `Todos los anuncios, conjunto por conjunto (${lista.length})`),
    el('div', { class: 'ng-ad-tabla' }, ui.tabla({
      etiqueta: 'Todos los anuncios', claseFila,
      columnas: columnasKpis(ctx, { conPuesto: false, nombreCel: nombreCon(false), roasCel }),
      filas: lista, maxFilas: 60, ordenInicial: { clave: 'gasto_usd', dir: 'desc' },
    })));
  const titulo = top.length ? `Top ${top.length} creativos${A.n_creativos > top.length ? ` de ${A.n_creativos}` : ''}` : 'Creativos';
  return ui.seccion(titulo, el('div', { class: ['pila', clase] },
    el('p', { class: 'ng-ad-resumen' }, A.resumen || '', ui.ayuda(ayudaVeredicto)),
    el('p', { class: 'ng-nota' }, 'Orden del top ', ui.ayuda(ayudaTop), ` · «ROAS neto est.» con ${usd(A.neto_por_venta)} por comprador${V ? ` (${V.dias ? `${V.dias} días` : 'historia'}, ${numero(V.compradores, 0)} compradores)` : ''} `, ui.ayuda(ayudaRoasEst), ` · leído de Meta ${A.leido ? `el ${textoCorte(A.leido)}` : 'sin fecha'}.`),
    top.length ? el('div', { class: 'ng-ad-tabla' }, tablaTop) : el('p', { class: 'ng-nota' }, 'Ningún creativo tuvo impresiones en este período.'),
    el('div', { class: 'ng-ad-tarjetas' }, top.map(tarjeta)),
    todos));
}
function seccionHistorial(ctx, o) {
  const { ui } = ctx;
  const { el } = ui;
  const diario = o.diario || [];
  if (!diario.length) return ui.seccion('Historial por día', el('p', { class: 'ng-nota' }, 'Todavía no hay días con pauta.'));
  const cifra = (f) => (v) => (v === null || v === undefined ? el('span', { class: 'texto-tenue' }, 'sin dato') : f(v));
  return ui.seccion('Historial por día', el('div', { class: 'pila' },
    graficoSerie(ui, {
      titulo: 'Resultado del día contra Meta', subtitulo: 'Neto cobrado − gasto en anuncios, en dólares', tipo: 'barras', serie: serieDiaria(diario, 'resultado'),
      formato: (v) => usd(v, { signo: true }), referencias: [{ valor: 0, etiqueta: 'Equilibrio' }], columna: 'Resultado',
    }),
    ui.tabla({
      etiqueta: 'Historial por día',
      columnas: [
        { clave: 'fecha', titulo: 'Día', formato: (v) => v.split('-').reverse().join('/') },
        { clave: 'gasto', titulo: 'Anuncios', numerico: true, formato: cifra((v) => sale(ui, v)) },
        { clave: 'ventas', titulo: 'Ventas', numerico: true },
        { clave: 'neto', titulo: 'Neto', numerico: true, formato: cifra((v) => entra(ui, v)) },
        { clave: 'resultado', titulo: 'Neto − Meta', numerico: true, formato: cifra((v) => resultado(ui, v)) },
      ],
      filas: diario, ordenInicial: { clave: 'fecha', dir: 'desc' },
    }),
    o.historial_vs_corte ? el('p', { class: 'ng-nota' }, `El gasto por día se leyó de Meta ${o.historial_leido ? `el ${textoCorte(o.historial_leido)}` : 'después'} y suma ${usd(o.historial_vs_corte, { signo: true })} más que el corte; los totales usan el corte.`) : null));
}
function seccionVentas(ctx, o) {
  const { ui } = ctx;
  const nombres = Object.fromEntries((o.por_tienda || []).map((t) => [t.slug, t.nombre]));
  const niveles = Object.fromEntries(((o.ficha && o.ficha.tiendas) || []).map((t) => [t.slug, t.nivel]));
  const filas = (o.ventas || []).map((v) => ({ ...v, tienda_nombre: nombres[v.tienda] || v.tienda, nivel_txt: v.nivel || niveles[v.tienda] || null }));
  return ui.seccion(`Ventas (${filas.length})`, filas.length ? ui.tabla({
    etiqueta: 'Ventas',
    columnas: [
      { clave: 'orden', titulo: 'Orden' },
      { clave: 'fecha', titulo: 'Día', formato: (v) => (v ? v.split('-').reverse().join('/') : '—') },
      { clave: 'tienda_nombre', titulo: 'Tienda', flex: true },
      { clave: 'nivel_txt', titulo: 'Nivel' },
      { clave: 'bruto', titulo: 'Pagó', numerico: true, formato: (v, f) => moneda(v, f.moneda) },
      { clave: 'neto_usd', titulo: 'Neto', numerico: true, formato: (v) => entra(ui, v) },
    ],
    filas,
  }) : ui.el('p', { class: 'ng-nota' }, 'Todavía no hay ventas.'), { ayuda: 'Sin datos de compradores: solo orden, tienda y montos.' });
}
function abrirDocumento(ctx, doc) {
  const { ui } = ctx;
  const cuerpo = ui.el('div', null, ui.cargando('Abriendo el documento…'));
  ui.modal({ titulo: doc.titulo, cuerpo, ancho: '960px' });
  ctx.api.sobre('/negocio/documento', { ruta: doc.ruta }).then((s) => {
    const d = s.datos;
    if (!d) { ui.reemplazar(cuerpo, ui.vacio('No se encontró el documento.')); return; }
    if (d.tipo === 'imagen' && d.contenido) ui.reemplazar(cuerpo, imagenData(ui, d.contenido, { alt: doc.titulo, class: 'ng-img' }));
    else ui.reemplazar(cuerpo, ui.visorTexto(d.contenido, { tipo: 'markdown' }));
  }).catch((err) => ui.reemplazar(cuerpo, ui.errorBox(err)));
}
function botonExterno(ui, url, texto) {
  const u = urlExterna(url);
  if (!u) return null;
  return ui.el('a', { class: 'btn btn--chico', href: u.url, target: '_blank', rel: 'noopener noreferrer', 'aria-label': `${texto}: ${u.dominio} (se abre en otra pestaña)` }, ui.icono('enlace-externo', { tam: 13 }), texto);
}
function seccionEnlaces(ctx, o) {
  const { ui } = ctx;
  const { el } = ui;
  const f = o.ficha || {};
  const tienda = (f.tiendas || [])[0];
  return ui.seccion('Documentos y enlaces', el('div', { class: 'ng-enlaces' },
    (o.documentos || []).map((d) => el('button', { type: 'button', class: 'btn btn--chico', onclick: () => abrirDocumento(ctx, d) }, ui.icono('archivo', { tam: 13 }), d.titulo)),
    tienda ? botonExterno(ui, tienda.url, 'Abrir la tienda') : null,
    botonExterno(ui, f.landing_original, 'Abrir la landing original')));
}
export async function render(ctx) {
  const { ui } = ctx;
  const { el } = ui;
  estilos(ui);
  let sobre;
  const params = ctx.params || {};
  RANGO = periodoPedido(params, almacen());
  if (params.periodo === 'inicio' || (params.desde && params.hasta)) recordarPeriodo(RANGO, almacen());
  try { sobre = await ctx.api.sobre('/negocio', RANGO ? { desde: RANGO.desde, hasta: RANGO.hasta } : undefined); } catch (err) {
    return el('div', { class: 'pagina' }, ui.encabezadoPagina({ titulo: 'Negocio', descripcion: 'No se pudieron leer las cuentas de las ofertas.', migas: [] }), ui.errorBox(err, { reintentar: () => ctx.recargar() }));
  }
  ultimoSobre = sobre;
  if (sobre.datos && Array.isArray(sobre.datos.ofertas)) { IDS = sobre.datos.ofertas.map((o) => o && o.id); fijarTerminos(terminosDeOfertas(sobre.datos.ofertas)); }
  if (sobre.vacio || !sobre.datos || !Array.isArray(sobre.datos.ofertas) || !sobre.datos.ofertas.length) {
    return el('div', { class: 'pagina' },
      ui.encabezadoPagina({ titulo: 'Negocio', descripcion: 'Si estamos ganando o perdiendo, oferta por oferta.', migas: [] }),
      ui.vacioConPasos({
        titulo: 'Todavía no hay ofertas con números',
        explicacion: 'El tablero se arma con el libro de tests, que crea el agente al lanzar la primera oferta y actualiza en cada revisión del funnel.',
        pasos: [{ texto: 'Lanza una oferta con la guía «modelar y lanzar».' }, { texto: 'Pide la revisión del funnel al día siguiente: ahí se cargan los números de Meta y de Impultienda.' }],
        icono: 'grafico',
      }));
  }
  return ctx.params && ctx.params.id ? vistaFicha(ctx, sobre, String(ctx.params.id)) : vistaCartera(ctx, sobre);
}

/** Actualización en vivo: solo si cambió el libro de tests o los límites (no en cada archivo de ofertas/). */
export function alCambio(ctx, evento) {
  const lote = (evento && evento.lote) || [evento];
  const toca = lote.some((e) => e && (!e.ruta || /libro-de-tests\.json$|limites\.yaml$|_funnels\//.test(e.ruta)));
  if (!toca && ultimoSobre) return undefined;
  if (globalThis.document && globalThis.document.querySelector('.modal-fondo')) return undefined;
  return render(ctx);
}
