// vistas-ofertas.js — piezas de DOM y estilos compartidos por Ofertas, Oferta, Pulido y Skills (agente U2).
// A diferencia del resto de lib/*, ESTE módulo construye elementos (usa ui.js); no se prueba con node --test: la lógica pura está en
// lib/{oferta,ofertas,pulido,skills}.js. Todo texto de datos entra por ui.el (textContent); nunca HTML en línea.
// Los estilos propios (prefijo .u2-) se instalan con ui.instalarEstilos (la CSP no admite <style> en línea) y usan solo las variables
// del sistema de diseño (--sup, --borde, --acento, --ok…), así que siguen el tema claro/oscuro.

import { ui, el, icono, chip, fmt, limpiar, toast, instalarEstilos } from '../ui.js';
import * as V from './oferta.js';
import * as P from './pulido.js';

// ───────────────────────── estilos ─────────────────────────

export const CSS = `
.u2-pila { display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--e-4); min-width: 0; }
.u2-pila--chica { gap: var(--e-2); }
.u2-pila > .chip, .u2-pila > .u2-codigo, .u2-pila > .u2-segmentado { justify-self: start; }
/* solo en modo ancho: en modo compacto (tarjeta estrecha o teléfono) mandan las reglas de .stepper--compacto en styles.css y las 11 etapas caben sin cortarse */
.u2-pipeline .stepper:not(.stepper--compacto) .stepper__item { flex: 1 0 92px; min-width: 92px; }
.u2-pipeline .stepper__lista { padding-left: 0; padding-right: 0; }
.u2-fila { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e-2) var(--e-3); min-width: 0; }
.u2-fila--entre { justify-content: space-between; }
.u2-nota { color: var(--txt-2); font-size: .9rem; line-height: 1.5; overflow-wrap: anywhere; }
.u2-tenue { color: var(--txt-3); }
.u2-mono { font-family: var(--mono); font-size: .86em; }
.u2-rotulo { font-size: .72rem; text-transform: uppercase; letter-spacing: .07em; font-weight: 650; color: var(--txt-2); }
.u2-subtitulo { font-size: .98rem; font-weight: 650; color: var(--txt); margin: 0; }
.u2-aviso { color: var(--aviso); font-size: .9rem; }
.u2-bloque { background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); padding: var(--e-4); box-shadow: var(--sombra); min-width: 0; }
.u2-bloque--suave { background: var(--sup-2); box-shadow: none; }
.u2-bloque__cab { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e-2) var(--e-3); margin-bottom: var(--e-3); }
.u2-bloque__cab h2, .u2-bloque__cab h3 { margin: 0; font-size: 1rem; font-weight: 650; }
.u2-cols { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--e-4); align-items: start; }
.u2-cols--2-1 { grid-template-columns: minmax(0, 1.7fr) minmax(0, 1fr); }
.u2-cols > * { min-width: 0; }
.u2-rejilla { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: var(--e-3); }
.u2-metricas { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: var(--e-3); }
@media (max-width: 899px) { .u2-cols, .u2-cols--2-1 { grid-template-columns: minmax(0, 1fr); } }
@media (max-width: 599px) { .u2-rapida__fila, .u2-alta-rapida { grid-template-columns: minmax(0, 1fr); } .u2-rapida .u2-segmentado, .u2-alta-rapida .u2-segmentado { width: 100%; grid-auto-columns: 1fr; } .u2-segmentado button { justify-content: center; } }
@media (max-width: 599px) { .u2-metricas { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--e-2); } .u2-ficha { gap: var(--e-3) var(--e-5); } }

/* etiquetas: son ui.chip del sistema; u2-suave las deja sin relleno (datos secundarios) */
.chip.u2-suave { background: transparent; border-color: var(--borde); color: var(--txt-2); font-weight: 550; }
.u2-codigo { display: inline-flex; align-items: center; height: 18px; padding: 0 6px; border-radius: 5px; font-size: .7rem; font-weight: 700; letter-spacing: .03em; color: var(--txt-2); background: var(--sup-3); font-family: var(--mono); }

/* botones propios (se apoyan en .btn del sistema) */
.u2-btn-grande { height: 38px; padding: 0 18px; font-size: 1rem; border-radius: 9px; }
.u2-enlace-boton { all: unset; cursor: pointer; color: var(--acento); font-weight: 550; text-decoration: underline; text-underline-offset: 2px; border-radius: var(--r-1); }
.u2-enlace-boton:hover { color: var(--acento-fuerte); }
.u2-enlace-boton:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }

/* barra de herramientas (búsqueda, filtros, orden, vista) */
.u2-herr { display: flex; flex-wrap: wrap; gap: var(--e-3) var(--e-4); align-items: flex-end; padding: var(--e-3) var(--e-4); background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); box-shadow: var(--sombra); }
.u2-herr__campo { display: grid; gap: 4px; font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; font-weight: 650; color: var(--txt-2); min-width: 0; }
.u2-herr__campo .campo { text-transform: none; letter-spacing: 0; font-weight: 400; font-size: .9rem; min-width: 140px; }
.u2-herr__campo--busca { flex: 1 1 220px; }
.u2-herr__campo--busca .campo { width: 100%; }
.u2-herr__fin { margin-left: auto; display: flex; flex-wrap: wrap; gap: var(--e-2) var(--e-3); align-items: center; }
.u2-interruptores { display: flex; flex-wrap: wrap; gap: var(--e-2) var(--e-4); align-items: center; }

/* tarjetas de ofertas */
.u2-tarjetas { display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: var(--e-4); }
.u2-of { position: relative; display: grid; align-content: start; gap: var(--e-3); padding: var(--e-4); background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); box-shadow: var(--sombra); min-width: 0; transition: border-color .12s ease, box-shadow .12s ease; }
.u2-of:hover { border-color: var(--acento); }
.u2-of:focus-within { border-color: var(--acento); }
.u2-of--firma { border-top: 3px solid var(--acento); }
.u2-of--grave { border-top: 3px solid var(--punto-error); }
.u2-of__cab { display: flex; justify-content: space-between; gap: var(--e-2); align-items: flex-start; }
.u2-of__titulo { margin: 0; font-size: 1.05rem; font-weight: 650; line-height: 1.3; overflow-wrap: anywhere; }
.u2-of__titulo a { color: var(--txt); text-decoration: none; }
.u2-of__titulo a::after { content: ""; position: absolute; inset: 0; border-radius: inherit; }
.u2-of__titulo a:focus-visible { outline: none; }
.u2-of:has(.u2-of__titulo a:focus-visible) { outline: 2px solid var(--foco); outline-offset: 2px; }
.u2-of__sub { color: var(--txt-3); font-size: .82rem; overflow-wrap: anywhere; }
.u2-of__etapas { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e-2) var(--e-3); }
.u2-of__proximo { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px; align-items: start; padding: 9px 11px; border-radius: 9px; background: var(--sup-2); font-size: .9rem; }
.u2-of__proximo strong { display: block; font-weight: 600; }
.u2-of__proximo--acento { background: var(--acento-bg); }
.u2-of__proximo--acento .icono { color: var(--acento-fuerte); }
.u2-of__proximo--grave, .u2-of__proximo--error { background: var(--error-bg); }
.u2-of__proximo--ok .icono { color: var(--ok); }
.u2-of__proximo .u2-btn-in { position: relative; z-index: 1; margin-top: 6px; }
.u2-of__cifras { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--e-2); border-top: 1px solid var(--borde); padding-top: var(--e-3); }
.u2-of__cifra { display: grid; gap: 1px; min-width: 0; }
.u2-of__cifra b { font-variant-numeric: tabular-nums; font-weight: 650; overflow-wrap: anywhere; }
:root[data-densidad="compacta"] .u2-of { padding: var(--e-3); gap: var(--e-2); }
:root[data-densidad="compacta"] .u2-tarjetas { gap: var(--e-3); grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }
@media (max-width: 599px) { .u2-tarjetas { grid-template-columns: minmax(0, 1fr); } .u2-herr__campo .campo { min-width: 0; width: 100%; } .u2-herr__campo { flex: 1 1 140px; } }
.u2-celda-titulo { display: grid; gap: 1px; min-width: 0; }
.u2-celda-titulo a { font-weight: 600; text-decoration: none; overflow: hidden; text-overflow: ellipsis; }
.u2-celda-titulo span { color: var(--txt-3); font-size: .78rem; overflow: hidden; text-overflow: ellipsis; }

/* panel lateral */
.u2-drawer-fondo { position: fixed; inset: 0; background: rgba(8, 12, 18, .5); z-index: 70; display: flex; justify-content: flex-end; }
.u2-drawer { width: min(var(--u2-ancho, 580px), 100vw); height: 100%; background: var(--sup); color: var(--txt); border-left: 1px solid var(--borde); box-shadow: var(--sombra-modal); display: flex; flex-direction: column; animation: u2-entra .16s ease-out; outline: none; }
@keyframes u2-entra { from { transform: translateX(28px); opacity: .5; } to { transform: none; opacity: 1; } }
.u2-drawer__cab { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--e-3); padding: var(--e-4) var(--e-5); border-bottom: 1px solid var(--borde); }
.u2-drawer__titulo { font-size: 1.2rem; font-weight: 700; margin: 0; line-height: 1.25; }
.u2-drawer__sub { color: var(--txt-2); font-size: .9rem; margin-top: 2px; }
.u2-drawer__cuerpo { flex: 1; min-height: 0; overflow: auto; padding: var(--e-5); display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--e-4); align-content: start; }
.u2-drawer__pie { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--e-2); padding: var(--e-3) var(--e-5); border-top: 1px solid var(--borde); background: var(--sup-2); }
@media (max-width: 899px) { .u2-drawer__cuerpo, .u2-drawer__cab, .u2-drawer__pie { padding-left: var(--e-4); padding-right: var(--e-4); } }

/* lista de pasos numerados (cómo hacerlo) */
.u2-pasos { display: grid; gap: var(--e-3); counter-reset: u2p; margin: 0; padding: 0; list-style: none; }
.u2-pasos > li { counter-increment: u2p; display: grid; grid-template-columns: 26px minmax(0, 1fr); gap: var(--e-3); align-items: start; }
.u2-pasos > li::before { content: counter(u2p); display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; background: var(--acento-bg); color: var(--acento-fuerte); font-weight: 700; font-size: .85rem; }
.u2-pasos__cuerpo { display: grid; gap: var(--e-2); min-width: 0; }
.u2-checklist { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.u2-checklist > li { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: var(--e-2); align-items: start; font-size: .92rem; }
.u2-checklist .icono { margin-top: 2px; }
.u2-ic--ok { color: var(--ok); } .u2-ic--aviso { color: var(--aviso); } .u2-ic--error { color: var(--error); } .u2-ic--info { color: var(--info); } .u2-ic--neutro { color: var(--txt-3); }

/* clave / valor */
.u2-kv { display: grid; grid-template-columns: minmax(110px, 190px) minmax(0, 1fr); gap: 0 var(--e-4); margin: 0; font-size: .92rem; }
.u2-kv dt { color: var(--txt-2); padding: 8px 0; border-bottom: 1px solid var(--borde); }
.u2-kv dd { margin: 0; padding: 8px 0; border-bottom: 1px solid var(--borde); overflow-wrap: anywhere; min-width: 0; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.u2-kv dt:last-of-type, .u2-kv dd:last-of-type { border-bottom: 0; }
@media (max-width: 599px) { .u2-kv { grid-template-columns: minmax(0, 1fr); } .u2-kv dt { border-bottom: 0; padding-bottom: 0; } }

/* mini-pipeline (11 segmentos) */
.u2-mini { display: inline-flex; gap: 3px; align-items: center; vertical-align: middle; }
.u2-mini__seg { width: 14px; height: 18px; border-radius: 4px; background: var(--sup-3); border: 1px solid var(--borde-fuerte); box-sizing: border-box; flex: none; }
.u2-mini__seg--ok { background: var(--punto-ok); border-color: var(--punto-ok); }
.u2-mini__seg--info { background: var(--acento); border-color: var(--acento); }
.u2-mini__seg--aviso { background: var(--punto-aviso); border-color: var(--punto-aviso); }
.u2-mini__seg--error { background: var(--punto-error); border-color: var(--punto-error); }
.u2-mini__seg--sin { background: transparent; border-style: dashed; }
.u2-mini__seg--opc { opacity: .5; }
.u2-mini__seg--firma { box-shadow: 0 0 0 2px var(--sup), 0 0 0 4px var(--punto-aviso); background: var(--punto-aviso); border-color: var(--punto-aviso); position: relative; z-index: 1; }
.u2-mini__seg--hoy { background-image: repeating-linear-gradient(135deg, transparent 0 3px, rgba(255,255,255,.35) 3px 5px); }
.u2-mini--compacta { gap: 2px; }
.u2-mini--compacta .u2-mini__seg { width: 11px; height: 16px; border-radius: 3px; }
.u2-mini--compacta .u2-mini__seg--firma { box-shadow: 0 0 0 1.5px var(--sup), 0 0 0 3px var(--punto-aviso); }
.u2-mini--grande .u2-mini__seg { width: 22px; height: 26px; border-radius: 6px; }

/* encabezado de la ficha de una oferta */
.u2-ficha { display: flex; flex-wrap: wrap; gap: var(--e-3) var(--e-6); align-items: flex-start; padding: var(--e-3) var(--e-4); background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); box-shadow: var(--sombra); }
.u2-ficha__item { display: grid; gap: 3px; min-width: 0; }
.u2-ficha__valor { font-weight: 600; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; min-width: 0; }

/* tarjeta dominante «Próximo paso» */
.u2-proximo { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: var(--e-4) var(--e-5); align-items: center; padding: var(--e-5) var(--e-5) var(--e-5) var(--e-5); background: var(--sup); border: 1px solid var(--borde); border-left: 5px solid var(--borde-fuerte); border-radius: var(--r-3); box-shadow: var(--sombra); }
.u2-proximo--ok { border-left-color: var(--punto-ok); }
.u2-proximo--info { border-left-color: var(--acento); }
.u2-proximo--acento { border-left-color: var(--acento); background: linear-gradient(90deg, var(--acento-bg), var(--sup) 55%); }
.u2-proximo--aviso { border-left-color: var(--punto-aviso); background: linear-gradient(90deg, var(--aviso-bg), var(--sup) 55%); }
.u2-proximo--error { border-left-color: var(--punto-error); background: linear-gradient(90deg, var(--error-bg), var(--sup) 55%); }
.u2-proximo__icono { display: grid; place-items: center; width: 52px; height: 52px; border-radius: 14px; background: var(--neutro-bg); color: var(--neutro); }
.u2-proximo--ok .u2-proximo__icono { background: var(--ok-bg); color: var(--ok); }
.u2-proximo--acento .u2-proximo__icono { background: var(--acento); color: var(--sobre-acento); }
.u2-proximo--info .u2-proximo__icono { background: var(--info-bg); color: var(--info); }
.u2-proximo--aviso .u2-proximo__icono { background: var(--aviso-bg); color: var(--aviso); border: 1px solid var(--aviso-borde); }
.u2-proximo--error .u2-proximo__icono { background: var(--error-bg); color: var(--error); border: 1px solid var(--error-borde); }
.u2-proximo__texto { display: grid; gap: 4px; min-width: 0; }
.u2-proximo__titulo { font-size: 1.5rem; font-weight: 700; line-height: 1.2; letter-spacing: -.01em; margin: 0; overflow-wrap: anywhere; }
.u2-proximo__detalle { color: var(--txt-2); max-width: 70ch; }
.u2-proximo__acciones { display: flex; flex-wrap: wrap; gap: var(--e-2); justify-content: flex-end; align-items: center; }
@media (max-width: 899px) { .u2-proximo { grid-template-columns: auto minmax(0, 1fr); padding: var(--e-4); } .u2-proximo__acciones { grid-column: 1 / -1; justify-content: flex-start; } .u2-proximo__titulo { font-size: 1.25rem; } .u2-proximo__icono { width: 42px; height: 42px; } }

/* panel de la etapa elegida */
.u2-etapa { background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); box-shadow: var(--sombra); min-width: 0; }
.u2-etapa__cab { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: var(--e-4); align-items: center; padding: var(--e-4) var(--e-5); border-bottom: 1px solid var(--borde); }
.u2-etapa__icono { display: grid; place-items: center; width: 44px; height: 44px; border-radius: 12px; background: var(--acento-bg); color: var(--acento-fuerte); }
.u2-etapa__titulo { font-size: 1.2rem; font-weight: 700; margin: 0; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.u2-etapa__pregunta { color: var(--txt-2); font-size: .92rem; }
.u2-etapa__estado { display: flex; flex-wrap: wrap; gap: var(--e-2); justify-content: flex-end; align-items: center; }
.u2-etapa__cuerpo { padding: var(--e-3) var(--e-5) var(--e-5); }
.u2-etapa__cuerpo .tabs__lista { margin: 0 calc(-1 * var(--e-5)); padding: 0 var(--e-5); }
@media (max-width: 899px) { .u2-etapa__cab { grid-template-columns: auto minmax(0, 1fr); padding: var(--e-3) var(--e-4); } .u2-etapa__estado { grid-column: 1 / -1; justify-content: flex-start; } .u2-etapa__cuerpo { padding: var(--e-2) var(--e-4) var(--e-4); } .u2-etapa__cuerpo .tabs__lista { margin: 0 calc(-1 * var(--e-4)); padding: 0 var(--e-4); } }

/* gate / firma */
.u2-gate { display: grid; gap: var(--e-3); padding: var(--e-4); border-radius: var(--r-3); border: 1px solid var(--aviso-borde); background: var(--aviso-bg); }
.u2-gate--acento { border-color: var(--acento); background: var(--acento-bg); }
.u2-gate--ok { border-color: var(--ok-borde); background: var(--ok-bg); }
.u2-gate--info { border-color: var(--info-borde); background: var(--info-bg); }
.u2-gate--error { border-color: var(--error-borde); background: var(--error-bg); }
.u2-gate--neutro { border-color: var(--borde); background: var(--sup-2); }
.u2-gate__titulo { display: flex; gap: var(--e-2); align-items: center; font-weight: 700; font-size: 1.02rem; }

/* flujo de entradas → etapa → salidas */
.u2-flujo { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr); gap: var(--e-4); align-items: start; }
.u2-flujo__centro { align-self: center; display: grid; place-items: center; color: var(--txt-3); }
.u2-lista { display: grid; gap: 0; margin: 0; padding: 0; list-style: none; }
.u2-lista > li { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e-2); padding: 8px 0; border-bottom: 1px solid var(--borde); min-width: 0; }
.u2-lista > li:last-child { border-bottom: 0; }
.u2-lista__texto { flex: 1; min-width: 0; overflow-wrap: anywhere; }
@media (max-width: 899px) { .u2-flujo { grid-template-columns: minmax(0, 1fr); } .u2-flujo__centro { transform: rotate(90deg); } }

/* artefactos: lista + visor */
.u2-art { display: grid; grid-template-columns: minmax(240px, 340px) minmax(0, 1fr); gap: var(--e-4); align-items: start; }
.u2-art__lista { display: grid; gap: 2px; max-height: 560px; overflow: auto; padding-right: 2px; }
.u2-art__grupo { font-size: .74rem; text-transform: uppercase; letter-spacing: .06em; color: var(--txt-2); font-weight: 650; padding: 10px 6px 4px; overflow-wrap: anywhere; }
.u2-art__item { display: grid; grid-template-columns: 18px minmax(0, 1fr) auto; gap: 8px; align-items: center; width: 100%; text-align: left; background: none; border: 1px solid transparent; border-radius: 8px; padding: 7px 8px; cursor: pointer; font: inherit; color: var(--txt); }
.u2-art__item:hover { background: var(--sup-2); }
.u2-art__item[aria-current="true"] { background: var(--acento-bg); border-color: var(--acento); }
.u2-art__item:focus-visible { outline: 2px solid var(--foco); outline-offset: -2px; }
.u2-art__nombre { min-width: 0; overflow-wrap: anywhere; font-weight: 550; }
.u2-art__meta { color: var(--txt-3); font-size: .78rem; white-space: nowrap; }
.u2-visor { display: grid; gap: var(--e-3); min-width: 0; }
.u2-visor img { max-width: 100%; height: auto; border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup-2); }
.u2-visor__cab { display: flex; flex-wrap: wrap; gap: var(--e-2) var(--e-3); align-items: center; }
.u2-vacio-visor { display: grid; place-items: center; gap: 6px; text-align: center; padding: var(--e-6) var(--e-4); color: var(--txt-3); border: 1px dashed var(--borde-fuerte); border-radius: var(--r-3); }
.u2-cmp { display: flex; flex-wrap: wrap; gap: var(--e-2); align-items: center; padding: var(--e-3); background: var(--sup-2); border: 1px solid var(--borde); border-radius: var(--r-2); margin-top: var(--e-3); }
.u2-diff { font-family: var(--mono); font-size: .82rem; border: 1px solid var(--borde); border-radius: var(--r-2); overflow: auto; max-height: 520px; background: var(--sup-2); }
.u2-diff__l { display: grid; grid-template-columns: 44px 44px 18px minmax(0, 1fr); white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.45; }
.u2-diff__n { color: var(--txt-3); text-align: right; padding: 0 6px; user-select: none; }
.u2-diff__s { user-select: none; text-align: center; }
.u2-diff__l--mas { background: var(--ok-bg); }
.u2-diff__l--menos { background: var(--error-bg); }
.u2-diff__salto { color: var(--txt-3); text-align: center; padding: 3px; background: var(--sup-3); font-family: var(--fuente); font-size: .78rem; }
@media (max-width: 899px) { .u2-art { grid-template-columns: minmax(0, 1fr); } .u2-art__lista { max-height: 260px; } .u2-diff__l { grid-template-columns: 34px 34px 14px minmax(0, 1fr); } }

/* revisión de calidad */
.u2-veredicto { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: var(--e-4); align-items: center; padding: var(--e-4); border-radius: var(--r-3); border: 1px solid var(--borde); background: var(--sup-2); }
.u2-veredicto--ok { border-color: var(--ok-borde); background: var(--ok-bg); }
.u2-veredicto--aviso { border-color: var(--aviso-borde); background: var(--aviso-bg); }
.u2-veredicto--error { border-color: var(--error-borde); background: var(--error-bg); }
.u2-veredicto__icono { display: grid; place-items: center; width: 44px; height: 44px; border-radius: 50%; background: var(--sup); color: var(--neutro); border: 1px solid var(--borde); }
.u2-veredicto--ok .u2-veredicto__icono { color: var(--ok); border-color: var(--ok-borde); }
.u2-veredicto--aviso .u2-veredicto__icono { color: var(--aviso); border-color: var(--aviso-borde); }
.u2-veredicto--error .u2-veredicto__icono { color: var(--error); border-color: var(--error-borde); }
.u2-veredicto__titulo { font-weight: 700; font-size: 1.1rem; }
.u2-puntaje { text-align: right; font-variant-numeric: tabular-nums; }
.u2-puntaje__n { font-size: 1.7rem; font-weight: 700; line-height: 1; }
.u2-puntaje__de { color: var(--txt-2); font-size: .8rem; }
@media (max-width: 599px) { .u2-veredicto { grid-template-columns: auto minmax(0, 1fr); } .u2-puntaje { grid-column: 1 / -1; text-align: left; } }
.u2-hallazgo { display: grid; gap: 6px; padding: var(--e-3) var(--e-4); border: 1px solid var(--borde); border-left-width: 4px; border-radius: var(--r-2); background: var(--sup); min-width: 0; }
.u2-hallazgo--error { border-left-color: var(--punto-error); }
.u2-hallazgo--aviso { border-left-color: var(--punto-aviso); }
.u2-hallazgo--info { border-left-color: var(--acento); }
.u2-hallazgo__cab { display: flex; flex-wrap: wrap; gap: 6px 8px; align-items: center; }
.u2-cita { margin: 0; padding: 6px 10px; border-left: 3px solid var(--borde-fuerte); background: var(--sup-2); border-radius: 0 var(--r-2) var(--r-2) 0; color: var(--txt-2); font-size: .86rem; overflow-wrap: anywhere; }
.u2-cita code { background: none; border: 0; padding: 0; }
.u2-rubrica { display: grid; gap: 8px; margin: 0; padding: 0; list-style: none; }
.u2-rubrica > li { display: grid; grid-template-columns: minmax(0, 1fr) 150px 38px; gap: var(--e-3); align-items: center; }
.u2-barra { height: 8px; border-radius: 99px; background: var(--sup-3); overflow: hidden; }
.u2-barra > i { display: block; height: 100%; width: var(--p, 0%); background: var(--acento); border-radius: 99px; }
.u2-barra--ok > i { background: var(--punto-ok); } .u2-barra--aviso > i { background: var(--punto-aviso); } .u2-barra--error > i { background: var(--punto-error); }
@media (max-width: 599px) { .u2-rubrica > li { grid-template-columns: minmax(0, 1fr) 90px 30px; gap: var(--e-2); } }

/* historial */
.u2-linea { display: grid; gap: 0; margin: 0; padding: 0; list-style: none; position: relative; }
.u2-linea > li { display: grid; grid-template-columns: 28px minmax(0, 1fr) auto; gap: var(--e-3); padding: 10px 0; position: relative; }
.u2-linea > li::before { content: ""; position: absolute; left: 13px; top: 0; bottom: 0; width: 2px; background: var(--borde); }
.u2-linea > li:first-child::before { top: 18px; } .u2-linea > li:last-child::before { bottom: calc(100% - 18px); }
.u2-linea__punto { position: relative; z-index: 1; display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--sup); border: 2px solid var(--borde-fuerte); color: var(--txt-2); }
.u2-linea__punto--ok { border-color: var(--punto-ok); color: var(--ok); } .u2-linea__punto--error { border-color: var(--punto-error); color: var(--error); }
.u2-linea__punto--aviso { border-color: var(--punto-aviso); color: var(--aviso); } .u2-linea__punto--info { border-color: var(--acento); color: var(--info); }
.u2-linea__texto { min-width: 0; overflow-wrap: anywhere; }
.u2-linea__cuando { color: var(--txt-3); font-size: .82rem; white-space: nowrap; }
@media (max-width: 599px) { .u2-linea > li { grid-template-columns: 28px minmax(0, 1fr); } .u2-linea__cuando { grid-column: 2; } }

/* tarjetas de notas de pulido */
.u2-nota-card { display: grid; gap: 6px; padding: var(--e-3) var(--e-4); border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup); min-width: 0; }
.u2-nota-card--alta { border-left: 4px solid var(--punto-error); }
.u2-nota-card--media { border-left: 4px solid var(--punto-aviso); }
.u2-nota-card--baja { border-left: 4px solid var(--borde-fuerte); }
.u2-nota-card--resuelta { opacity: .78; border-left-color: var(--punto-ok); }
.u2-nota-card__titulo { font-weight: 600; overflow-wrap: anywhere; line-height: 1.35; }
.u2-nota-card__detalle { color: var(--txt-2); font-size: .88rem; overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.u2-nota-card__pie { display: flex; flex-wrap: wrap; gap: 6px 8px; align-items: center; }
.u2-alta-rapida { display: grid; grid-template-columns: minmax(0, 1fr) auto auto auto; gap: var(--e-2); align-items: center; }
.u2-alta-rapida .campo { min-height: 34px; }
@media (max-width: 899px) { .u2-alta-rapida { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); } .u2-alta-rapida > :first-child { grid-column: 1 / -1; } }

/* pulido: alta rápida, mapa por etapa y tablero */
.u2-rapida { display: grid; gap: var(--e-3); padding: var(--e-4); background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); box-shadow: var(--sombra); }
.u2-rapida__fila { display: grid; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr) minmax(0, 1fr) auto auto; gap: var(--e-2); align-items: center; }
.u2-rapida .campo { min-height: 36px; }
@media (max-width: 1100px) { .u2-rapida__fila { grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); } .u2-rapida__fila > :first-child { grid-column: 1 / -1; } }
.u2-mapa { display: grid; grid-template-columns: repeat(auto-fill, minmax(158px, 1fr)); gap: var(--e-2); }
.u2-mapa__celda { text-align: left; background: var(--sup); border: 1px solid var(--borde); border-left-width: 4px; border-radius: var(--r-2); padding: 10px 11px; display: grid; gap: 6px; cursor: pointer; font: inherit; color: inherit; min-width: 0; }
.u2-mapa__celda:hover { border-color: var(--acento); }
.u2-mapa__celda:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }
.u2-mapa__celda[aria-pressed="true"] { border-color: var(--acento); box-shadow: 0 0 0 1px var(--acento); background: var(--acento-bg); }
.u2-mapa__celda--pulir { border-left-color: var(--punto-aviso); }
.u2-mapa__celda--limpia { border-left-color: var(--punto-ok); }
.u2-mapa__celda--sin_notas { border-left-style: dashed; border-left-color: var(--borde-fuerte); }
.u2-mapa__nombre { font-weight: 600; font-size: .92rem; overflow-wrap: anywhere; line-height: 1.25; }
.u2-mapa__estado { font-size: .78rem; color: var(--txt-2); display: flex; align-items: center; gap: 5px; }
.u2-mapa__celda--limpia .u2-mapa__estado { color: var(--ok); } .u2-mapa__celda--pulir .u2-mapa__estado { color: var(--aviso); }
.u2-gravedad { display: flex; flex-wrap: wrap; gap: var(--e-2); }
.u2-gravedad__btn { display: inline-flex; align-items: center; gap: 8px; padding: 6px 12px; border-radius: 99px; border: 1px solid var(--borde-fuerte); background: var(--sup); cursor: pointer; font: inherit; color: var(--txt); font-weight: 550; }
.u2-gravedad__btn b { font-variant-numeric: tabular-nums; font-size: 1.05rem; }
.u2-gravedad__btn:hover { background: var(--sup-2); }
.u2-gravedad__btn[aria-pressed="true"] { border-color: var(--acento); background: var(--acento-bg); color: var(--acento-fuerte); }
.u2-gravedad__btn:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }
.u2-tablero { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--e-4); align-items: start; }
.u2-col { background: var(--sup-2); border: 1px solid var(--borde); border-radius: var(--r-3); padding: var(--e-3); display: grid; gap: var(--e-3); min-height: 180px; align-content: start; min-width: 0; }
.u2-col__cab { display: flex; align-items: center; justify-content: space-between; gap: var(--e-2); }
.u2-col__titulo { margin: 0; font-size: .98rem; font-weight: 650; display: flex; align-items: center; gap: 8px; }
.u2-col__n { min-width: 26px; height: 22px; line-height: 20px; border-radius: 99px; background: var(--sup); border: 1px solid var(--borde-fuerte); text-align: center; font-size: .8rem; font-weight: 650; padding: 0 7px; font-variant-numeric: tabular-nums; }
.u2-col__sub { color: var(--txt-3); font-size: .8rem; margin-top: -6px; }
.u2-col--sobre { outline: 2px dashed var(--acento); outline-offset: -2px; background: var(--acento-bg); }
.u2-col__vacia { color: var(--txt-3); text-align: center; font-size: .88rem; padding: 22px 10px; border: 1px dashed var(--borde-fuerte); border-radius: var(--r-2); }
.u2-carta { cursor: grab; box-shadow: var(--sombra); }
.u2-carta:active { cursor: grabbing; }
.u2-carta--arrastrando { opacity: .45; }
.u2-carta__meta { display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: center; color: var(--txt-3); font-size: .8rem; }
@media (max-width: 1100px) { .u2-tablero { grid-template-columns: minmax(0, 1fr); } .u2-col { min-height: 0; } }

/* skills: mapa de cobertura y tarjetas */
.u2-cob { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: var(--e-3); }
.u2-cob__celda { position: relative; display: grid; align-content: start; gap: 6px; text-align: left; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); padding: var(--e-3) var(--e-3) var(--e-3) var(--e-4); font: inherit; color: inherit; min-width: 0; }
button.u2-cob__celda { cursor: pointer; }
button.u2-cob__celda:hover { border-color: var(--acento); }
button.u2-cob__celda:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }
.u2-cob__celda::before { content: ""; position: absolute; left: 0; top: 10px; bottom: 10px; width: 4px; border-radius: 0 4px 4px 0; background: var(--borde-fuerte); }
.u2-cob__celda--borrador::before { background: var(--acento); }
.u2-cob__celda--v1::before { background: var(--punto-ok); }
.u2-cob__celda--sin_skill { border-style: dashed; border-color: var(--aviso-borde); background: var(--aviso-bg); }
.u2-cob__celda--sin_skill::before { background: var(--punto-aviso); }
.u2-cob__celda--fuera_alcance { border-style: dashed; opacity: .75; background: transparent; }
.u2-cob__cab { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.u2-cob__cab > span:last-child { min-width: 0; text-align: right; }
.u2-cob__nombre { font-weight: 650; overflow-wrap: anywhere; line-height: 1.25; }
.u2-cob__skill { display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: center; font-size: .85rem; }
.u2-skills { display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: var(--e-4); }
.u2-skill { position: relative; display: grid; align-content: start; gap: var(--e-3); padding: var(--e-4); background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); box-shadow: var(--sombra); min-width: 0; }
.u2-skill:hover { border-color: var(--acento); }
.u2-skill[aria-current="true"] { border-color: var(--acento); box-shadow: 0 0 0 1px var(--acento); }
.u2-skill__titulo { margin: 0; font-size: 1.05rem; font-weight: 650; line-height: 1.3; }
.u2-skill__titulo button { all: unset; cursor: pointer; }
.u2-skill__titulo button::after { content: ""; position: absolute; inset: 0; border-radius: inherit; }
.u2-skill__titulo button:focus-visible { outline: none; }
.u2-skill:has(.u2-skill__titulo button:focus-visible) { outline: 2px solid var(--foco); outline-offset: 2px; }
.u2-skill__slug { color: var(--txt-3); font-size: .8rem; font-family: var(--mono); overflow-wrap: anywhere; }
.u2-skill__falta { font-size: .9rem; color: var(--txt-2); display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px; align-items: start; padding: 9px 11px; border-radius: 9px; background: var(--sup-2); }
.u2-skill__falta .icono { margin-top: 2px; color: var(--acento-fuerte); }
.u2-prog { display: grid; gap: 6px; }
.u2-prog__barra { display: flex; height: 8px; border-radius: 99px; overflow: hidden; background: var(--sup-3); gap: 1px; }
.u2-prog__barra i { display: block; height: 100%; flex: 0 0 var(--p); }
.u2-prog__ok { background: var(--punto-ok); } .u2-prog__falla { background: var(--punto-error); } .u2-prog__medir { background: var(--borde-fuerte); }
.u2-prog__leyenda { display: flex; flex-wrap: wrap; gap: 4px 12px; font-size: .8rem; color: var(--txt-2); }
.u2-hitos { display: grid; gap: var(--e-3); margin: 0; padding: 0; list-style: none; counter-reset: h; }
.u2-hitos > li { counter-increment: h; display: grid; grid-template-columns: 28px minmax(0, 1fr); gap: var(--e-3); }
.u2-hitos > li::before { content: counter(h); display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--sup-3); color: var(--txt-2); font-weight: 700; }
.u2-criterio { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: var(--e-2); align-items: start; padding: 8px 0; border-bottom: 1px solid var(--borde); }
.u2-criterio:last-child { border-bottom: 0; }
@media (max-width: 599px) { .u2-skills { grid-template-columns: minmax(0, 1fr); } .u2-cob { grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); } }

/* formulario modal */
.u2-form { display: grid; gap: var(--e-3); }
.u2-form label { display: grid; gap: 4px; font-weight: 600; font-size: .85rem; color: var(--txt-2); }
.u2-form .u2-form__2 { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--e-3); }
@media (max-width: 599px) { .u2-form .u2-form__2 { grid-template-columns: minmax(0, 1fr); } }
.u2-segmentado { display: inline-grid; grid-auto-flow: column; border: 1px solid var(--borde-fuerte); border-radius: 9px; overflow: hidden; background: var(--sup); }
.u2-segmentado button { all: unset; cursor: pointer; padding: 0 12px; height: 32px; display: inline-flex; align-items: center; gap: 5px; font-size: .85rem; font-weight: 550; color: var(--txt-2); box-sizing: border-box; border-right: 1px solid var(--borde); }
.u2-segmentado button:last-child { border-right: 0; }
.u2-segmentado button:hover { background: var(--sup-2); }
.u2-segmentado button[aria-pressed="true"] { background: var(--acento-bg); color: var(--acento-fuerte); font-weight: 650; }
.u2-segmentado button:focus-visible { outline: 2px solid var(--foco); outline-offset: -2px; }
.u2-sr { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
`;

/** Instala una sola vez los estilos de las cuatro pantallas. Si el navegador no admite hojas construidas la pantalla sigue legible. */
export function estilos() { return instalarEstilos('u2-ofertas', CSS); }

// ───────────────────────── iconos y etiquetas ─────────────────────────

export const ICONO_ETAPA = { D1: 'lupa', M1: 'globo', D2: 'diana', D3: 'dinero', D4: 'caja', D5: 'pantalla', D6: 'chispa', D7: 'megafono', D8: 'pulso', D9: 'tendencia-sube', D10: 'usuario' };
export const iconoEtapa = (id) => ICONO_ETAPA[id] || 'lista';

const ICONO_TONO = { ok: 'ok', aviso: 'alerta', grave: 'rombo-alerta', error: 'x-circulo', critico: 'octogono', info: 'info', acento: 'firma', neutro: 'circulo' };

/**
 * Etiqueta con icono + texto (siempre las dos cosas: el color nunca va solo). Es un `ui.chip` del sistema de diseño.
 * `tono`: ok|aviso|grave|error|critico|info|acento|neutro. `suave`: neutra y sin relleno (para datos secundarios).
 */
export function tag(texto, tono = 'neutro', { icono: nombre, titulo, suave = false } = {}) {
  const t = ui.normalizarTono ? ui.normalizarTono(tono) : tono;
  const c = chip(texto, suave ? 'neutro' : t, { icono: nombre || ICONO_TONO[t] || 'circulo' });
  if (suave) c.classList.add('u2-suave');
  if (titulo) c.title = titulo;
  return c;
}

/** Estado de una etapa con icono + frase humana («Espera tu firma», «Aprobada»…). */
export function estadoEtapaTag(v) {
  const h = V.estadoHumano(v);
  const icono_ = v.gatePendiente ? 'firma' : (v.sinDatos ? 'circulo-punteado' : ({ aprobado: 'check', en_QA: 'ojo', en_progreso: 'progreso', bloqueado: 'candado', escalado: 'escalar', pendiente: 'circulo-punteado' }[v.estado] || 'circulo'));
  return tag(h.texto, v.gatePendiente ? 'acento' : h.tono, { icono: v.obsoleta ? 'reloj-alerta' : icono_ });
}

export function codigo(id) { return el('span', { class: 'u2-codigo' }, id); }

/** Gravedad de una nota de pulido: alta=grave · media=aviso · baja=neutro, con su icono. */
export function tagSeveridadPulido(s) {
  const tono = { alta: 'grave', media: 'aviso', baja: 'neutro' }[s] || 'neutro';
  return tag(P.TITULO_SEVERIDAD[s] || s, tono, { icono: { alta: 'rombo-alerta', media: 'alerta', baja: 'info' }[s] || 'circulo', titulo: P.AYUDA_SEVERIDAD[s] });
}
export function tagEstadoPulido(e) {
  const tono = { abierta: 'neutro', en_curso: 'info', resuelta: 'ok' }[e] || 'neutro';
  return tag(P.TITULO_ESTADO[e] || e, tono, { icono: { abierta: 'circulo', en_curso: 'progreso', resuelta: 'ok' }[e] || 'circulo', titulo: P.AYUDA_ESTADO[e] });
}
export function tagTipoPulido(t) {
  return tag(P.TITULO_TIPO[t] || t, 'neutro', { icono: { observacion: 'lapiz', nota: 'archivo', decision: 'bandera' }[t] || 'lapiz', suave: true });
}

/** Cifra con pie: «7 de 10». */
export function par(etiqueta, valor) {
  return el('div', { class: 'u2-ficha__item' }, el('span', { class: 'u2-rotulo' }, etiqueta), el('div', { class: 'u2-ficha__valor' }, valor));
}

/** Barra de proporción 0-100 (`bp`/100). tono: ok|aviso|error|''. */
export function barra(porcentaje, tono = '', etiqueta = '') {
  const p = Math.max(0, Math.min(100, Number(porcentaje) || 0));
  return el('div', { class: ['u2-barra', tono && `u2-barra--${tono}`], role: 'img', 'aria-label': etiqueta || `${Math.round(p)} %`, style: { '--p': `${p}%` } }, el('i'));
}

// ───────────────────────── mini-pipeline ─────────────────────────

/** Una fila de segmentos, uno por etapa; la que espera tu firma lleva un anillo. `pipeline` = vistas de lib/oferta. */
export function miniPipeline(pipeline, { etiqueta = '', grande = false, compacta = false } = {}) {
  const caja = el('span', { class: ['u2-mini', grande && 'u2-mini--grande', compacta && 'u2-mini--compacta'], role: 'img', 'aria-label': etiqueta || 'Estado de las etapas' });
  for (const v of pipeline) {
    const tono = v.sinDatos ? 'sin' : v.tono;
    const cls = ['u2-mini__seg', `u2-mini__seg--${v.gatePendiente ? 'firma' : tono}`, v.opcional && v.sinDatos && 'u2-mini__seg--opc'];
    const h = V.estadoHumano(v);
    caja.appendChild(el('span', { class: cls, title: `${V.etiquetaEtapa(v.id)}: ${h.texto}` }));
  }
  return caja;
}

// ───────────────────────── panel lateral ─────────────────────────

let panelAbierto = null;

/** ¿Hay un panel lateral abierto? (las pantallas aplazan su re-render mientras tanto). */
export function hayPanelLateral() { return Boolean(panelAbierto); }

/** Cierra el panel lateral abierto (si hay uno). */
export function cerrarPanelLateral() { if (panelAbierto) panelAbierto.cerrar(); }

/**
 * Panel lateral accesible (Esc, clic fuera y botón cierran; foco atrapado; devuelve el foco).
 * opts: {titulo, subtitulo?, cuerpo, pie?:Element[], ancho?:'580px', alCerrar?}. Devuelve {cerrar, elemento, cuerpo}.
 */
export function panelLateral({ titulo, subtitulo, cuerpo, pie, ancho, alCerrar } = {}) {
  cerrarPanelLateral();
  const previo = document.activeElement;
  let cerrado = false;
  const tid = `u2-drawer-t-${Math.random().toString(36).slice(2, 8)}`;
  const cuerpoEl = el('div', { class: 'u2-drawer__cuerpo' }, cuerpo);
  const caja = el('aside', { class: 'u2-drawer', role: 'dialog', 'aria-modal': 'true', 'aria-labelledby': tid, tabindex: '-1', style: ancho ? { '--u2-ancho': ancho } : null },
    el('header', { class: 'u2-drawer__cab' },
      el('div', null, el('h2', { class: 'u2-drawer__titulo', id: tid }, titulo), subtitulo ? el('div', { class: 'u2-drawer__sub' }, subtitulo) : null),
      el('button', { type: 'button', class: 'btn btn--icono', 'aria-label': 'Cerrar el panel', onclick: () => cerrar() }, icono('cerrar'))),
    cuerpoEl,
    pie && pie.length ? el('footer', { class: 'u2-drawer__pie' }, pie) : null);
  const fondo = el('div', { class: 'u2-drawer-fondo', onmousedown: (ev) => { if (ev.target === fondo) cerrar(); } }, caja);
  const FOCALIZABLES = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), summary, [tabindex]:not([tabindex="-1"])';
  function alTecla(ev) {
    if (ev.key === 'Escape') {
      // si hay un modal del sistema encima, no lo cierres tú: él ya atrapa Esc
      if (document.querySelector('.modal-fondo')) return;
      ev.stopPropagation(); cerrar(); return;
    }
    if (ev.key !== 'Tab' || document.querySelector('.modal-fondo')) return;
    const f = [...caja.querySelectorAll(FOCALIZABLES)].filter((x) => x.offsetParent !== null);
    if (!f.length) { ev.preventDefault(); caja.focus(); return; }
    const primero = f[0]; const ultimo = f[f.length - 1];
    if (ev.shiftKey && (document.activeElement === primero || document.activeElement === caja)) { ev.preventDefault(); ultimo.focus(); }
    else if (!ev.shiftKey && document.activeElement === ultimo) { ev.preventDefault(); primero.focus(); }
  }
  function cerrar() {
    if (cerrado) return;
    cerrado = true;
    document.removeEventListener('keydown', alTecla, true);
    if (fondo.parentNode) fondo.parentNode.removeChild(fondo);
    if (panelAbierto && panelAbierto.elemento === fondo) panelAbierto = null;
    if (previo && typeof previo.focus === 'function') { try { previo.focus(); } catch (_) { /* nodo ya no existe */ } }
    if (typeof alCerrar === 'function') alCerrar();
  }
  document.addEventListener('keydown', alTecla, true);
  document.body.appendChild(fondo);
  try { caja.focus(); } catch (_) { /* sin foco */ }
  panelAbierto = { cerrar, elemento: fondo };
  return { cerrar, elemento: fondo, cuerpo: cuerpoEl };
}

/** Lista numerada de pasos: [{texto, cuerpo?:Node|Node[]}]. */
export function listaPasos(pasos) {
  return el('ol', { class: 'u2-pasos' }, pasos.map((p) => el('li', null, el('div', { class: 'u2-pasos__cuerpo' }, p.texto ? el('div', null, p.texto) : null, p.cuerpo || null))));
}

/** Lista de comprobaciones con icono: [{ok:true|false|null, texto, detalle?}]. */
export function checklist(items) {
  return el('ul', { class: 'u2-checklist' }, items.map((i) => {
    const tono = i.ok === true ? 'ok' : (i.ok === false ? 'error' : 'neutro');
    const ic = i.ok === true ? 'ok' : (i.ok === false ? 'x-circulo' : 'circulo-punteado');
    return el('li', null, el('span', { class: `u2-ic--${tono}` }, icono(ic, { tam: 16 })), el('div', null, i.texto, i.detalle ? el('div', { class: 'u2-nota' }, i.detalle) : null));
  }));
}

// ───────────────────────── formulario «Anotar observación» ─────────────────────────

export const OPCIONES_ETAPA = P.ETAPAS_PULIDO.map((e) => ({ valor: e, texto: `${e} · ${P.nombreEtapaPulido(e)}` }));
export const OPCIONES_SEVERIDAD = [
  { valor: 'alta', texto: 'Alta · impide que corra solo' }, { valor: 'media', texto: 'Media' }, { valor: 'baja', texto: 'Baja · mejora opcional' },
];
export const OPCIONES_TIPO = [
  { valor: 'observacion', texto: 'Observación (algo a corregir)' }, { valor: 'nota', texto: 'Nota' }, { valor: 'decision', texto: 'Decisión o regla mía' },
];

export function selectDe(opciones, valor, attrs = {}) {
  const s = el('select', { class: 'campo', ...attrs }, opciones.map((o) => el('option', { value: o.valor }, o.texto)));
  s.value = valor ?? '';
  return s;
}

function campoConEtiqueta(texto, control, error) {
  return el('label', null, texto, control, error ? el('span', { class: 'campo-error', role: 'alert' }, error) : null);
}

/**
 * Formulario modal «Anotar observación» (POST /pulido). Compartido por Oferta y Pulido.
 * opts: {oferta_id?, etapa?, ofertas?:[ids], alGuardar?(entrada)}
 */
export function abrirFormularioObservacion(ctx, opts = {}) {
  const ofertas = Array.isArray(opts.ofertas) ? opts.ofertas : [];
  const selOferta = selectDe([{ valor: '', texto: '(general: no es de una oferta)' }, ...ofertas.map((o) => ({ valor: o, texto: o }))], opts.oferta_id || '', { 'aria-label': 'Oferta' });
  const selEtapa = selectDe([{ valor: '', texto: 'Elige la etapa…' }, ...OPCIONES_ETAPA], opts.etapa || '', { 'aria-label': 'Etapa' });
  const selSev = selectDe(OPCIONES_SEVERIDAD, 'media', { 'aria-label': 'Gravedad' });
  const selTipo = selectDe(OPCIONES_TIPO, 'observacion', { 'aria-label': 'Tipo' });
  const titulo = el('input', { class: 'campo', type: 'text', maxlength: String(P.LIMITES.titulo), placeholder: 'Qué hay que corregir, en una línea', 'aria-label': 'Título' });
  const detalle = el('textarea', { class: 'campo', rows: '5', maxlength: String(P.LIMITES.detalle), placeholder: 'Qué viste, qué esperabas y en qué archivo. Opcional.', 'aria-label': 'Detalle' });
  const errores = el('div', { class: 'u2-nota', role: 'alert' });
  const cuerpo = el('div', { class: 'u2-form' },
    el('p', { class: 'u2-nota' }, 'Queda en tus mejoras pendientes: la lista de lo que falta corregir en cada paso hasta que todo corra solo. ', ui.termino ? ui.termino('bitacora_pulido', { texto: '¿Qué es?' }) : null),
    el('div', { class: 'u2-form__2' }, campoConEtiqueta('Oferta', selOferta), campoConEtiqueta('Etapa', selEtapa)),
    el('div', { class: 'u2-form__2' }, campoConEtiqueta('Gravedad', selSev), campoConEtiqueta('Tipo', selTipo)),
    campoConEtiqueta('Título', titulo),
    campoConEtiqueta('Detalle', detalle),
    errores);
  return ui.modal({
    titulo: 'Anotar observación',
    cuerpo,
    ancho: '620px',
    acciones: [
      { texto: 'Cancelar' },
      {
        texto: 'Guardar', tono: 'primario',
        alClick: async () => {
          const r = P.validarNueva({ oferta_id: selOferta.value, etapa: selEtapa.value, titulo: titulo.value, detalle: detalle.value, severidad: selSev.value, tipo: selTipo.value });
          limpiar(errores);
          if (!r.ok) { errores.appendChild(el('span', { class: 'campo-error' }, Object.values(r.errores).join(' '))); return false; }
          try {
            const guardada = await ctx.api.post('/pulido', r.cuerpo);
            toast('Observación anotada en Mejoras pendientes.', 'ok');
            if (typeof opts.alGuardar === 'function') await opts.alGuardar(guardada);
            return true;
          } catch (err) {
            errores.appendChild(el('span', { class: 'campo-error' }, `No se pudo guardar: ${(err && (err.mensaje || err.message)) || 'error desconocido'}`));
            return false;
          }
        },
      },
    ],
  });
}

/** Control segmentado (botones exclusivos). opciones: [{valor, texto, icono?}]. `alCambiar(valor)`. Devuelve el Element con `.valor`. */
export function segmentado(opciones, valor, alCambiar, { etiqueta = '' } = {}) {
  const raiz = el('div', { class: 'u2-segmentado', role: 'group', 'aria-label': etiqueta || null });
  let actual = valor;
  const botones = opciones.map((o) => el('button', {
    type: 'button', 'aria-pressed': String(o.valor === actual),
    onclick: () => { actual = o.valor; raiz.valor = actual; for (const b of botones) b.setAttribute('aria-pressed', String(b.dataset.v === String(actual))); alCambiar(actual); },
    dataset: { v: o.valor },
  }, o.icono ? icono(o.icono, { tam: 14 }) : null, o.texto));
  raiz.append(...botones);
  raiz.valor = actual;
  return raiz;
}

export { fmt };

/** «hace 2 h» con la fecha exacta en el `title`. */
export function cuando(iso) {
  return el('span', { class: 'u2-cuando', title: fmt.fecha(iso, { segundos: true }) }, fmt.relativo(iso));
}

/** Texto tenue «—» para lo que no hay. */
export function sinDato(texto = '—') { return el('span', { class: 'u2-tenue' }, texto); }

/** Capitaliza la primera letra de un rótulo («en construcción» → «En construcción»). */
export function mayus(t) { const s = String(t ?? ''); return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }

const ICONO_FASE = {
  borrador: 'lapiz', en_construccion: 'engranaje', listo_para_activar: 'play', en_test: 'diana', validada: 'ok', fallida: 'x-circulo',
  inconclusa: 'info', escalando: 'tendencia-sube', retirada: 'archivar', pausada: 'pausa',
};
/** Fase de la oferta con icono + texto humano («En construcción»). */
export function tagFase(fase) {
  return tag(mayus(V.rotuloFase(fase)), V.tonoFase(fase), { icono: ICONO_FASE[fase] || 'circulo' });
}

/** Lista clave/valor de dos columnas. `pares`: [[clave, valor]]; valor vacío → «—». */
export function kvNodo(pares) {
  const dl = el('dl', { class: 'u2-kv' });
  for (const [k, v] of pares) {
    dl.appendChild(el('dt', null, k));
    dl.appendChild(el('dd', null, v === null || v === undefined || v === '' ? sinDato() : v));
  }
  return dl;
}
