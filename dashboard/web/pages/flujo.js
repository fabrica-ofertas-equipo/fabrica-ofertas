// pages/flujo.js — #/flujo «Cómo funciona»: el sistema de ofertas como un flujo vivo.
//
// Pedido del dueño (2026-11-13): dividir el sistema en procesos, ver cuándo se activa cada uno y qué skill lo hace, «como un flujo que
// esté vivo», con claridad de dueño de negocio. Arriba, el pulso (vigilancia, banco de candidatos, ofertas en juego y lo que espera tu
// OK); en el medio, el diagrama: cada paso con su disparador, quién decide y las ofertas que están ahí AHORA (se mueven solas cuando
// cambia el libro de tests o corre la vigilancia); al tocar un paso, su detalle; abajo, las brechas que encontró la revisión.
// Fuentes: GET /api/negocio (etapa y backend de cada oferta) y GET /api/flujo (vigilancia, banco, armado, versiones). Solo lectura.

import { banderas, mercadoLargo, conPaises } from '../lib/negocio-visual.js';
import { AREAS, ESCENARIOS, ESTADOS_ESC, contarEscenarios, escenariosDe, ordenarEscenarios } from '../lib/escenarios.js';
import { PROCESOS, POR_CLAVE, FLECHAS, BRECHAS, CERRADAS, REGLAS, reglasDe, contarReglas, brechasOrdenadas, brechasDe, repartir, saludDe, horas, QUIEN, DISPARO } from '../lib/flujo.js';

export const meta = { ruta: 'flujo', titulo: 'Cómo funciona', grupo: 'El sistema', icono: 'pulso', escucha: ['oferta', 'empresa'] };

const CSS = `
.fl-pulso { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: var(--e-3); }
.fl-tile { display: grid; gap: 4px; padding: var(--e-4); border-radius: var(--r-3); border: 1px solid var(--neutro-borde); background: var(--neutro-bg); min-width: 0; }
.fl-tile__rot { display: flex; align-items: center; gap: 6px; font-size: var(--t-sm); font-weight: 650; color: var(--txt-2); }
.fl-tile__valor { font-size: var(--t-xl); font-weight: 750; letter-spacing: -.01em; line-height: 1.2; }
.fl-tile__sub { font-size: var(--t-xs); color: var(--txt-2); }
.fl-tile--ok { background: var(--ok-bg); border-color: var(--ok-borde); } .fl-tile--ok .fl-tile__valor { color: var(--ok); }
.fl-tile--aviso { background: var(--aviso-bg); border-color: var(--aviso-borde); } .fl-tile--aviso .fl-tile__valor { color: var(--aviso); }
.fl-tile--error { background: var(--error-bg); border-color: var(--error-borde); } .fl-tile--error .fl-tile__valor { color: var(--error); }

.fl-vivo { display: inline-flex; align-items: center; gap: 6px; font-size: var(--t-xs); color: var(--txt-2); }
.fl-vivo__punto { width: 8px; height: 8px; border-radius: 50%; background: var(--ok); box-shadow: 0 0 0 0 var(--ok); animation: fl-latido 2s infinite; }
.fl-vivo--aviso .fl-vivo__punto { background: var(--aviso); } .fl-vivo--error .fl-vivo__punto { background: var(--error); animation: none; }
@keyframes fl-latido { 0% { box-shadow: 0 0 0 0 color-mix(in srgb, var(--ok) 60%, transparent); } 70% { box-shadow: 0 0 0 8px transparent; } 100% { box-shadow: 0 0 0 0 transparent; } }

/* diagrama */
.fl-mapa { display: grid; gap: 0; align-items: stretch;
  grid-template-columns: minmax(0,1fr) 54px minmax(0,1fr) 54px minmax(0,1fr) 54px minmax(0,1fr) 54px minmax(0,1fr);
  grid-template-areas:
    "buscar c-buscar lanzar c-lanzar test c-test backend c-backend renovar"
    ". . . . v-test . . . ."
    ". . . . apagar . . . ."
    "v-aprender v-aprender v-aprender v-aprender v-aprender v-aprender v-aprender v-aprender v-aprender"
    "aprender aprender aprender aprender aprender aprender aprender aprender aprender"; }
.fl-paso { position: relative; display: grid; grid-template-columns: minmax(0, 1fr); align-content: start; gap: 8px; padding: var(--e-3) var(--e-3) var(--e-4); border-radius: var(--r-3);
  border: 1.5px solid var(--borde); background: var(--sup); cursor: pointer; min-width: 0; transition: border-color var(--t-rapida) var(--ease), box-shadow var(--t-rapida) var(--ease), transform var(--t-rapida) var(--ease); }
.fl-paso:hover { border-color: var(--borde-fuerte); transform: translateY(-1px); box-shadow: var(--sombra); }
.fl-paso[aria-current="true"] { border-color: var(--acento); box-shadow: 0 0 0 3px var(--acento-bg); }
.fl-paso--vivo::after { content: ''; position: absolute; inset: -1.5px; border-radius: var(--r-3); border: 1.5px solid var(--acento); opacity: 0; animation: fl-onda 2.6s infinite; pointer-events: none; }
@keyframes fl-onda { 0% { opacity: .55; transform: scale(1); } 100% { opacity: 0; transform: scale(1.04); } }
.fl-contenido { display: contents; }
.fl-a-buscar { grid-area: buscar; } .fl-a-lanzar { grid-area: lanzar; } .fl-a-test { grid-area: test; } .fl-a-backend { grid-area: backend; }
.fl-a-renovar { grid-area: renovar; } .fl-a-apagar { grid-area: apagar; } .fl-a-aprender { grid-area: aprender; }
.fl-a-c-buscar { grid-area: c-buscar; } .fl-a-c-lanzar { grid-area: c-lanzar; } .fl-a-c-test { grid-area: c-test; } .fl-a-c-backend { grid-area: c-backend; }
.fl-a-v-test { grid-area: v-test; } .fl-a-v-aprender { grid-area: v-aprender; }
.fl-paso__cab { display: flex; align-items: center; gap: 8px; }
.fl-paso__n { flex: none; display: grid; place-items: center; width: 26px; height: 26px; border-radius: 50%; background: var(--acento-bg); color: var(--acento-fuerte); font-weight: 750; font-size: var(--t-sm); }
.fl-paso--apagar .fl-paso__n { background: var(--error-bg); color: var(--error); }
.fl-paso__tit { font-weight: 750; font-size: var(--t-md); line-height: 1.2; }
.fl-paso__skill { font-family: var(--mono); font-size: 11px; color: var(--txt-2); background: var(--neutro-bg); border: 1px solid var(--neutro-borde); border-radius: var(--r-1); padding: 1px 6px; justify-self: start; max-width: 100%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.fl-paso__linea { display: flex; align-items: flex-start; gap: 6px; min-width: 0; overflow-wrap: anywhere; font-size: var(--t-xs); color: var(--txt-2); line-height: 1.35; }
.fl-paso__linea .ico { flex: none; margin-top: 1px; }
.fl-salud { display: inline-flex; align-items: center; gap: 6px; font-size: var(--t-xs); font-weight: 650; }
.fl-salud::before { content: ''; width: 8px; height: 8px; border-radius: 50%; background: var(--txt-3); flex: none; }
.fl-salud--ok { color: var(--ok); } .fl-salud--ok::before { background: var(--ok); }
.fl-salud--aviso { color: var(--aviso); } .fl-salud--aviso::before { background: var(--aviso); }
.fl-salud--error { color: var(--error); } .fl-salud--error::before { background: var(--error); }
.fl-salud--info { color: var(--info); } .fl-salud--info::before { background: var(--info); }
.fl-ofertas { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 2px; }
.fl-of { display: inline-flex; align-items: center; gap: 5px; max-width: 100%; min-width: 0; overflow: hidden; padding: 2px 8px 2px 6px; border-radius: var(--r-pill); font-size: 11.5px; font-weight: 650;
  border: 1px solid var(--neutro-borde); background: var(--neutro-bg); color: var(--txt); text-decoration: none; white-space: nowrap; }
.fl-paso .fl-of { white-space: normal; flex-wrap: wrap; border-radius: var(--r-2); row-gap: 0; line-height: 1.3; padding: 3px 8px 3px 6px; }
.fl-paso .fl-of small { flex-basis: 100%; padding-left: 2px; }
.fl-of span.fl-of__n { overflow: hidden; text-overflow: ellipsis; }
.fl-of small { font-weight: 600; color: var(--txt-2); overflow: hidden; text-overflow: ellipsis; }
a.fl-of:hover { border-color: var(--borde-fuerte); }
.fl-of--ok { background: var(--ok-bg); border-color: var(--ok-borde); } .fl-of--aviso { background: var(--aviso-bg); border-color: var(--aviso-borde); }
.fl-of--error { background: var(--error-bg); border-color: var(--error-borde); } .fl-of--info { background: var(--info-bg); border-color: var(--info-borde); }
.fl-of--pausada { opacity: .65; }
.fl-of--urgente { box-shadow: 0 0 0 2px color-mix(in srgb, var(--aviso) 35%, transparent); }
.fl-vacio { font-size: var(--t-xs); color: var(--txt-3); font-style: italic; }

/* conectores */
.fl-con { display: grid; align-content: center; justify-items: center; gap: 4px; padding: 0 4px; min-width: 0; }
.fl-con__linea { position: relative; width: 100%; height: 2px; background-image: linear-gradient(90deg, var(--borde-fuerte) 50%, transparent 50%); background-size: 10px 2px; animation: fl-corre 1.1s linear infinite; }
.fl-con__linea::after { content: ''; position: absolute; right: -2px; top: -4px; border-left: 8px solid var(--borde-fuerte); border-top: 5px solid transparent; border-bottom: 5px solid transparent; }
.fl-con__txt { font-size: 10.5px; line-height: 1.2; color: var(--txt-3); text-align: center; }
.fl-con--v { padding: 6px 0; grid-auto-flow: column; justify-content: center; align-items: center; gap: 8px; }
.fl-con--v .fl-con__linea { width: 2px; height: 30px; background-image: linear-gradient(180deg, var(--error) 50%, transparent 50%); background-size: 2px 10px; animation-name: fl-baja; }
.fl-con--v .fl-con__linea::after { right: -4px; top: auto; bottom: -2px; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 8px solid var(--error); border-bottom: 0; }
.fl-con--v .fl-con__txt { color: var(--error); text-align: left; }
.fl-con--ret .fl-con__linea { background-image: linear-gradient(180deg, var(--borde-fuerte) 50%, transparent 50%); }
.fl-con--ret .fl-con__linea::after { border-top-color: var(--borde-fuerte); }
.fl-con--ret .fl-con__txt { color: var(--txt-3); }
@keyframes fl-corre { from { background-position: 0 0; } to { background-position: 10px 0; } }
@keyframes fl-baja { from { background-position: 0 0; } to { background-position: 0 10px; } }
.fl-bucle { display: inline-flex; align-items: center; gap: 4px; font-size: 10.5px; color: var(--txt-2); background: var(--neutro-bg); border: 1px dashed var(--borde-fuerte); border-radius: var(--r-pill); padding: 1px 8px; justify-self: start; }
.fl-paso--aprender { grid-template-columns: auto 1fr auto; align-items: center; column-gap: var(--e-4); }
.fl-paso--aprender .fl-paso__det { display: flex; flex-wrap: wrap; gap: 4px var(--e-4); }

/* leyenda */
.fl-leyenda { display: flex; flex-wrap: wrap; gap: 6px var(--e-4); font-size: var(--t-xs); color: var(--txt-2); margin-top: var(--e-3); }
.fl-leyenda span { display: inline-flex; align-items: center; gap: 5px; }

/* detalle */
.fl-det { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); gap: var(--e-5); }
.fl-det h4 { margin: 0 0 6px; font-size: var(--t-sm); color: var(--txt-2); text-transform: uppercase; letter-spacing: .04em; }
.fl-det ul { margin: 0; padding-left: 1.15em; display: grid; gap: 5px; font-size: var(--t-sm); }
.fl-det__bloque { display: grid; gap: 4px; margin-bottom: var(--e-4); }
.fl-det__res { font-size: var(--t-md); margin: 0 0 var(--e-4); max-width: 70ch; }
.fl-det__kv { display: grid; grid-template-columns: max-content 1fr; gap: 6px var(--e-3); font-size: var(--t-sm); margin-bottom: var(--e-4); }
.fl-det__kv dt { color: var(--txt-2); font-weight: 650; display: inline-flex; align-items: center; gap: 5px; } .fl-det__kv dd { margin: 0; }
.fl-mono { font-family: var(--mono); font-size: 12px; }

/* brechas */
.fl-brechas { display: grid; gap: var(--e-2); }
.fl-brecha { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 4px var(--e-3); align-items: start; padding: var(--e-3) var(--e-4); border-radius: var(--r-2); border: 1px solid var(--neutro-borde); background: var(--sup); }
.fl-brecha__g { font-size: 11px; font-weight: 750; padding: 2px 8px; border-radius: var(--r-pill); text-transform: uppercase; letter-spacing: .03em; white-space: nowrap; }
.fl-brecha__g--alta { background: var(--error-bg); color: var(--error); border: 1px solid var(--error-borde); }
.fl-brecha__g--media { background: var(--aviso-bg); color: var(--aviso); border: 1px solid var(--aviso-borde); }
.fl-brecha__g--baja { background: var(--neutro-bg); color: var(--txt-2); border: 1px solid var(--neutro-borde); }
.fl-brecha__t { font-weight: 700; }
.fl-brecha__d { grid-column: 2 / 4; font-size: var(--t-sm); color: var(--txt-2); margin: 0; }
.fl-brecha__c { grid-column: 2 / 4; font-size: var(--t-sm); margin: 0; }
.fl-brecha__c strong { color: var(--ok); }

/* reglas */
.fl-reglas { width: 100%; border-collapse: collapse; font-size: var(--t-sm); }
.fl-reglas th { text-align: left; font-size: var(--t-xs); color: var(--txt-2); font-weight: 650; padding: 6px 8px; border-bottom: 1px solid var(--borde); }
.fl-reglas td { padding: 7px 8px; border-bottom: 1px solid var(--neutro-borde); vertical-align: top; }
.fl-reglas tr:last-child td { border-bottom: 0; }
.fl-reglas__id { font-family: var(--mono); font-size: 12px; color: var(--txt-2); white-space: nowrap; }
.fl-reglas__paso { white-space: nowrap; }
.fl-est { display: inline-flex; align-items: center; gap: 5px; padding: 1px 9px; border-radius: var(--r-pill); font-size: 11px; font-weight: 750; white-space: nowrap; border: 1px solid transparent; }
.fl-est--firmada { background: var(--ok-bg); color: var(--ok); border-color: var(--ok-borde); }
.fl-est--propuesta { background: var(--aviso-bg); color: var(--aviso); border-color: var(--aviso-borde); }
.fl-est--falta { background: var(--error-bg); color: var(--error); border-color: var(--error-borde); }
.fl-reglas-res { display: flex; flex-wrap: wrap; gap: 6px var(--e-3); align-items: center; margin-bottom: var(--e-3); font-size: var(--t-sm); color: var(--txt-2); }
.fl-mini-reglas { display: grid; gap: 6px; font-size: var(--t-sm); }
.fl-mini-reglas div { display: grid; grid-template-columns: auto 1fr; gap: 8px; align-items: start; }
.fl-cerradas { display: grid; gap: 4px; font-size: var(--t-sm); color: var(--txt-2); margin-top: var(--e-3); }
.fl-cerradas strong { color: var(--ok); }
.fl-tabla-scroll { overflow-x: auto; }

/* tus manos */
.fl-manos { display: grid; gap: var(--e-3); }
.fl-mano { display: grid; gap: 6px; padding: var(--e-3) var(--e-4); border: 1px solid var(--aviso-borde); background: var(--aviso-bg); border-radius: var(--r-2); }
.fl-mano--urgente { border-color: var(--error-borde); background: var(--error-bg); }
.fl-mano--verificando { border-color: var(--info-borde); background: var(--info-bg); }
.fl-mano--ok { border-color: var(--ok-borde); background: var(--ok-bg); } .fl-mano--ok strong { color: var(--ok); }
.fl-mano__listo, .fl-mano > .btn { justify-self: start; }
.fl-mano__pasos { margin: 0; padding-left: 1.2em; display: grid; gap: 6px; font-size: var(--t-sm); }
.fl-mano__pasos .btn { margin: 2px 4px 2px 0; }

/* servicios y saldos */
.fl-servicios { display: grid; gap: 8px; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
.fl-servicio { display: grid; gap: 4px; padding: var(--e-3); border: 1px solid var(--borde); border-radius: var(--r-2); align-content: start; }
.fl-servicio--error { border-color: var(--error-borde); background: var(--error-bg); } .fl-servicio--aviso { border-color: var(--aviso-borde); background: var(--aviso-bg); }
.fl-servicio__det { font-size: var(--t-sm); } .fl-servicio .btn { justify-self: start; }

/* dónde se pierde */
.fl-embudo { display: grid; gap: var(--e-3); }
.fl-embudo__fila { display: grid; gap: 6px; padding: var(--e-3); border: 1px solid var(--borde); border-radius: var(--r-2); }
.fl-embudo__tramos { display: flex; flex-wrap: wrap; gap: 6px; }
.fl-embudo__tramo { display: grid; padding: 4px 10px; border-radius: var(--r-2); background: var(--neutro-bg); font-size: var(--t-sm); }
.fl-embudo__tramo small { font-size: var(--t-xs); color: var(--txt-2); }
.fl-embudo__tramo--mal { background: var(--error-bg); } .fl-embudo__tramo--bien { background: var(--ok-bg); }

/* tareas y avisos */
.fl-h4 { margin: 0 0 8px; font-size: var(--t-sm); color: var(--txt-2); text-transform: uppercase; letter-spacing: .04em; }
.fl-tareas { display: grid; gap: 6px; } .fl-tarea { display: grid; gap: 1px; } .fl-tarea__sub { font-size: var(--t-xs); color: var(--txt-2); padding-left: 14px; }
.fl-avisos { margin: 0; padding-left: 1.1em; display: grid; gap: 4px; font-size: var(--t-sm); color: var(--txt-2); } .fl-aviso--urgente { color: var(--error); }

/* camino al 100 % */
.fl-camino { display: grid; gap: 8px; margin-bottom: var(--e-4); }
.fl-camino__pct { display: flex; align-items: baseline; gap: 10px; } .fl-camino__pct strong { font-size: var(--t-xl); font-weight: 800; } .fl-camino__pct span { color: var(--txt-2); font-size: var(--t-sm); }
.fl-barra { display: flex; height: 12px; border-radius: var(--r-pill); overflow: hidden; background: var(--neutro-bg); gap: 2px; }
.fl-barra__tramo { display: block; min-width: 4px; }
.fl-barra__tramo--cubierto { background: var(--ok); } .fl-barra__tramo--propuesta { background: var(--aviso); } .fl-barra__tramo--decidir { background: color-mix(in srgb, var(--aviso) 55%, var(--error)); }
.fl-barra__tramo--construir { background: var(--info); } .fl-barra__tramo--manos { background: var(--txt-3); }
.fl-barra__ley { display: flex; flex-wrap: wrap; gap: 4px var(--e-4); font-size: var(--t-xs); color: var(--txt-2); } .fl-barra__ley span { display: inline-flex; align-items: center; gap: 5px; }
.fl-punto { display: inline-block; width: 9px; height: 9px; border-radius: 50%; }
.fl-filtros { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: var(--e-3); }
.fl-filtro { border: 1px solid var(--neutro-borde); background: var(--sup); color: var(--txt-2); border-radius: var(--r-pill); padding: 4px 12px; font-size: var(--t-xs); font-weight: 650; cursor: pointer; }
.fl-filtro--activo { background: var(--acento-bg); color: var(--acento-fuerte); border-color: var(--acento); }
.fl-escs { display: grid; gap: var(--e-3); }
.fl-esc-grupo { display: grid; gap: 6px; } .fl-esc-grupo h4 { margin: 4px 0 0; font-size: var(--t-sm); color: var(--txt-2); text-transform: uppercase; letter-spacing: .04em; }
.fl-esc { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--e-3); padding: var(--e-3) var(--e-4); border-radius: var(--r-2); border: 1px solid var(--neutro-borde); background: var(--sup); border-left-width: 3px; }
.fl-esc--cubierto { border-left-color: var(--ok); } .fl-esc--propuesta { border-left-color: var(--aviso); } .fl-esc--decidir { border-left-color: color-mix(in srgb, var(--aviso) 55%, var(--error)); }
.fl-esc--construir { border-left-color: var(--info); } .fl-esc--manos { border-left-color: var(--txt-3); }
.fl-esc__id { font-family: var(--mono); font-size: 12px; color: var(--txt-3); padding-top: 2px; }
.fl-esc__cuerpo { display: grid; gap: 3px; min-width: 0; }
.fl-esc__tit { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px; }
.fl-esc__est { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; font-weight: 750; padding: 1px 8px; border-radius: var(--r-pill); border: 1px solid transparent; white-space: nowrap; }
.fl-esc__est--ok { background: var(--ok-bg); color: var(--ok); border-color: var(--ok-borde); } .fl-esc__est--aviso { background: var(--aviso-bg); color: var(--aviso); border-color: var(--aviso-borde); }
.fl-esc__est--info { background: var(--info-bg); color: var(--info); border-color: var(--info-borde); } .fl-esc__est--neutro { background: var(--neutro-bg); color: var(--txt-2); border-color: var(--neutro-borde); }
.fl-esc__p { font-size: 11px; font-weight: 750; color: var(--txt-3); }
.fl-esc__paso { margin-left: auto; }
.fl-esc__hoy, .fl-esc__prop { margin: 0; font-size: var(--t-sm); color: var(--txt-2); } .fl-esc__hoy span, .fl-esc__prop span { font-weight: 700; color: var(--txt); }
.fl-esc__prop span { color: var(--acento-fuerte); }

@media (max-width: 1100px) {
  .fl-reglas thead { display: none; } .fl-reglas, .fl-reglas tbody, .fl-reglas tr, .fl-reglas td { display: block; width: 100%; }
  .fl-reglas tr { padding: 8px 0; border-bottom: 1px solid var(--neutro-borde); } .fl-reglas td { border: 0; padding: 2px 0; }
  .fl-reglas td:nth-child(2) { font-weight: 700; } .fl-reglas td:nth-child(5) { color: var(--txt-2); font-size: var(--t-xs); }
  .fl-mapa { grid-template-columns: minmax(0, 1fr);
    grid-template-areas: "buscar" "c-buscar" "lanzar" "c-lanzar" "test" "v-test" "apagar" "c-test" "backend" "c-backend" "renovar" "v-aprender" "aprender"; }
  .fl-con { grid-auto-flow: column; justify-content: center; padding: 6px 0; gap: 8px; }
  .fl-con .fl-con__linea { width: 2px; height: 26px; background-image: linear-gradient(180deg, var(--borde-fuerte) 50%, transparent 50%); background-size: 2px 10px; animation-name: fl-baja; }
  .fl-con .fl-con__linea::after { right: -4px; top: auto; bottom: -2px; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 8px solid var(--borde-fuerte); border-bottom: 0; }
  .fl-con--v .fl-con__linea { background-image: linear-gradient(180deg, var(--error) 50%, transparent 50%); }
  .fl-con--v .fl-con__linea::after { border-top-color: var(--error); }
  .fl-con__txt { text-align: left; }
  .fl-pulso { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .fl-det { grid-template-columns: minmax(0, 1fr); }
  .fl-paso--aprender { grid-template-columns: auto 1fr; }
}
@media (max-width: 520px) { .fl-pulso { grid-template-columns: minmax(0, 1fr); } .fl-brecha { grid-template-columns: auto minmax(0, 1fr); } .fl-brecha__d, .fl-brecha__c { grid-column: 1 / 3; } }
@media (prefers-reduced-motion: reduce) { .fl-con__linea, .fl-vivo__punto, .fl-paso--vivo::after { animation: none !important; } .fl-paso:hover { transform: none; } }
`;

let seleccion = null;
let temporizador = null;
let ultimo = null;

function almacen() { try { return globalThis.localStorage || null; } catch (_) { return null; } }
function leerSeleccion() { try { const a = almacen(); return a ? a.getItem('flujo.paso') : null; } catch (_) { return null; } }
function guardarSeleccion(v) { try { const a = almacen(); if (a) a.setItem('flujo.paso', v); } catch (_) { /* sin almacenamiento */ } }

function chipOferta(ui, o) {
  const { el } = ui;
  const hijos = [o.mercado ? banderas(ui, o.mercado) : ui.icono('progreso', { tam: 12 }), el('span', { class: 'fl-of__n' }, o.nombre), o.etiqueta ? el('small', null, o.etiqueta) : null];
  const clase = ['fl-of', `fl-of--${o.tono || 'neutro'}`, o.urgente ? 'fl-of--urgente' : null];
  const titulo = `${o.nombre}${o.etiqueta ? ` — ${o.etiqueta}` : ''}${o.enlace ? ' (abre su ficha)' : ''}`;
  return o.enlace
    ? el('a', { class: clase, href: o.enlace, title: titulo, onclick: (ev) => ev.stopPropagation() }, ...hijos)
    : el('span', { class: clase, title: titulo }, ...hijos);
}

function tarjeta(ctx, p, ofertas, salud, alElegir) {
  const { ui } = ctx;
  const { el } = ui;
  const vivo = ofertas.some((o) => o.tono !== 'pausada');
  const quien = QUIEN[p.decide.quien] || QUIEN.agente;
  const disp = DISPARO[p.disparo.tipo] || DISPARO.pedido;
  const elegir = () => alElegir(p.clave);
  const esAprender = p.clave === 'aprender';
  const cuerpo = [
    el('div', { class: 'fl-paso__cab' },
      el('span', { class: 'fl-paso__n', 'aria-hidden': 'true' }, p.n ? String(p.n) : ui.icono(p.icono, { tam: 14 })),
      el('span', { class: 'fl-paso__tit' }, p.titulo)),
    el('div', { class: esAprender ? 'fl-paso__det' : 'fl-contenido' },
      el('span', { class: 'fl-paso__skill', title: `Skill: ${p.skill} — ${p.guia}` }, p.skill),
      el('span', { class: 'fl-paso__linea', title: p.disparo.texto }, ui.icono(disp.icono, { tam: 13 }), el('span', null, el('strong', null, `${disp.texto}. `), p.disparo.texto)),
      esAprender ? null : el('span', { class: 'fl-paso__linea' }, ui.icono(quien.icono, { tam: 13 }), el('span', null, p.decide.texto))),
    el('span', { class: ['fl-salud', `fl-salud--${salud.tono}`] }, salud.texto),
  ];
  if (!esAprender) {
    cuerpo.push(el('div', { class: 'fl-ofertas', 'aria-label': `Ofertas en ${p.titulo}` },
      ofertas.length ? ofertas.map((o) => chipOferta(ui, o)) : el('span', { class: 'fl-vacio' }, 'Ninguna oferta ahora')));
  }
  if (p.clave === 'renovar') cuerpo.push(el('span', { class: 'fl-bucle', title: 'Cada ronda vuelve a revisarse y a decidirse' }, ui.icono('refrescar', { tam: 11 }), 'vuelve a empezar cada ronda'));
  return el('div', {
    class: ['fl-paso', `fl-paso--${p.clave}`, `fl-a-${p.clave}`, vivo ? 'fl-paso--vivo' : null], role: 'button', tabindex: '0',
    'aria-current': seleccion === p.clave ? 'true' : 'false', 'aria-label': `${p.titulo}: ver el detalle`,
    onclick: elegir, onkeydown: (ev) => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); elegir(); } },
  }, ...cuerpo);
}

function conector(ui, area, texto, clase) {
  const { el } = ui;
  return el('div', { class: ['fl-con', `fl-a-${area}`, clase], 'aria-hidden': 'true' },
    el('span', { class: 'fl-con__linea' }), el('span', { class: 'fl-con__txt' }, texto));
}

function mapa(ctx, reparto, salud, alElegir) {
  const { ui } = ctx;
  const { el } = ui;
  const hijos = PROCESOS.map((p) => tarjeta(ctx, p, reparto[p.clave] || [], salud[p.clave] || { tono: 'neutro', texto: '' }, alElegir));
  for (const f of FLECHAS) {
    if (f.de === 'test' && f.a === 'apagar') hijos.push(conector(ui, 'v-test', f.texto, 'fl-con--v'));
    else hijos.push(conector(ui, `c-${f.de}`, f.texto));
  }
  hijos.push(conector(ui, 'v-aprender', 'lo que se aprende vuelve a la búsqueda y a la skill', 'fl-con--v fl-con--ret'));
  return el('div', null,
    el('div', { class: 'fl-mapa', role: 'group', 'aria-label': 'Flujo del sistema de ofertas' }, ...hijos),
    el('div', { class: 'fl-leyenda' },
      el('span', null, ui.icono('rayo', { tam: 13 }), 'corre solo'),
      el('span', null, ui.icono('usuario', { tam: 13 }), 'corre cuando lo pides'),
      el('span', null, el('span', { class: 'fl-of fl-of--urgente' }, 'oferta'), 'necesita algo'),
      el('span', null, 'El borde que late: hay ofertas en ese paso ahora. Toca un paso para ver el detalle; toca una oferta para abrir su ficha.')));
}

function detalle(ctx, clave, reparto, flujo) {
  const { ui } = ctx;
  const { el } = ui;
  const p = POR_CLAVE[clave] || PROCESOS[0];
  const ofs = reparto[p.clave] || [];
  const sk = (flujo.skills || {})[p.skill];
  const izquierda = el('div', null,
    el('p', { class: 'fl-det__res' }, p.resumen),
    el('dl', { class: 'fl-det__kv' },
      el('dt', null, ui.icono('skill', { tam: 13 }), 'Skill'), el('dd', null, el('span', { class: 'fl-mono' }, p.skill), sk && sk.version ? ` · v${sk.version}` : ''),
      el('dt', null, ui.icono('libro', { tam: 13 }), 'Guía'), el('dd', null, p.guia),
      el('dt', null, ui.icono((DISPARO[p.disparo.tipo] || DISPARO.pedido).icono, { tam: 13 }), 'Cuándo se activa'), el('dd', null, p.disparo.texto),
      el('dt', null, ui.icono((QUIEN[p.decide.quien] || QUIEN.agente).icono, { tam: 13 }), 'Quién decide'), el('dd', null, p.decide.texto),
      el('dt', null, ui.icono('flecha-derecha', { tam: 13 }), 'Pasa a'), el('dd', null, p.pasa_a.map((k) => (POR_CLAVE[k] || {}).titulo).filter(Boolean).join(' · '))),
    el('div', { class: 'fl-det__bloque' }, el('h4', null, 'Qué hace'), el('ul', null, p.hace.map((t) => el('li', null, t)))),
    el('div', { class: 'fl-det__bloque' }, el('h4', null, 'Reglas que manda'), el('ul', null, p.reglas.map((t) => el('li', null, t)))),
    reglasDe(p.clave).length ? el('div', { class: 'fl-det__bloque' }, el('h4', null, 'Situaciones y su regla'),
      el('div', { class: 'fl-mini-reglas' }, reglasDe(p.clave).map((r) => el('div', null, estadoRegla(ui, r.estado), el('span', null, el('strong', null, `${r.situacion}: `), r.regla))))) : null);
  const derecha = el('div', null,
    el('div', { class: 'fl-det__bloque' }, el('h4', null, `Ofertas aquí ahora (${ofs.length})`),
      ofs.length ? el('div', { class: 'fl-ofertas' }, ofs.map((o) => chipOferta(ui, o))) : el('span', { class: 'fl-vacio' }, 'Ninguna.')),
    p.clave === 'test' && flujo.vigilancia && flujo.vigilancia.existe ? bloqueVigilancia(ui, flujo.vigilancia) : null,
    p.clave === 'buscar' ? bloqueRadar(ui, flujo.radar || {}) : null,
    p.clave === 'buscar' ? bloqueBanco(ui, flujo.banco || {}, flujo.buscar_diario || {}) : null,
    (() => {
      const esc = ordenarEscenarios(escenariosDe(p.clave)).filter((e) => e.estado !== 'cubierto');
      return el('div', { class: 'fl-det__bloque' }, el('h4', null, `Lo que falta en este paso (${esc.length})`),
        esc.length ? el('div', { class: 'fl-escs' }, esc.map((e) => filaEscenario(ui, e, false))) : el('span', { class: 'fl-vacio' }, 'Todo cubierto.'));
    })());
  return el('div', { class: 'fl-det' }, izquierda, derecha);
}

const ESTADO_REGLA = { firmada: { texto: 'Firmada', icono: 'check' }, propuesta: { texto: 'Propuesta', icono: 'lapiz' }, falta: { texto: 'Falta', icono: 'alerta' } };
function estadoRegla(ui, estado) {
  const e = ESTADO_REGLA[estado] || ESTADO_REGLA.falta;
  return ui.el('span', { class: ['fl-est', `fl-est--${estado}`] }, ui.icono(e.icono, { tam: 11 }), e.texto);
}

function tablaReglas(ctx) {
  const { ui } = ctx;
  const { el } = ui;
  const c = contarReglas();
  return el('div', null,
    el('div', { class: 'fl-reglas-res' },
      estadoRegla(ui, 'firmada'), `${c.firmada} se ejecutan solas`,
      estadoRegla(ui, 'propuesta'), `${c.propuesta} se calculan y te las informo hasta que las firmes`,
      estadoRegla(ui, 'falta'), `${c.falta} sin regla todavía`),
    el('div', { class: 'fl-tabla-scroll' }, el('table', { class: 'fl-reglas' },
      el('thead', null, el('tr', null, ['', 'Situación', 'Regla', 'Estado', 'Quién la ejecuta', 'Paso'].map((t) => el('th', null, t)))),
      el('tbody', null, REGLAS.map((r) => el('tr', null,
        el('td', { class: 'fl-reglas__id' }, r.id),
        el('td', null, r.situacion),
        el('td', null, r.regla),
        el('td', null, estadoRegla(ui, r.estado)),
        el('td', null, r.ejecuta),
        el('td', { class: 'fl-reglas__paso' }, el('button', { type: 'button', class: 'btn btn--chico', onclick: () => { if (elegirGlobal) elegirGlobal(r.paso); } }, (POR_CLAVE[r.paso] || {}).titulo || r.paso))))))));
}

let filtroEsc = 'pendiente';
function filaEscenario(ui, e, conPaso) {
  const { el } = ui;
  const est = ESTADOS_ESC[e.estado] || ESTADOS_ESC.construir;
  return el('div', { class: ['fl-esc', `fl-esc--${e.estado}`] },
    el('span', { class: 'fl-esc__id' }, e.id),
    el('div', { class: 'fl-esc__cuerpo' },
      el('div', { class: 'fl-esc__tit' }, el('strong', null, e.escenario), el('span', { class: ['fl-esc__est', `fl-esc__est--${est.tono}`] }, ui.icono(est.icono, { tam: 11 }), est.texto),
        el('span', { class: 'fl-esc__p', title: { 1: 'Pierde plata o ventas hoy', 2: 'Frena crecer', 3: 'Orden y comodidad' }[e.prioridad] }, `P${e.prioridad}`),
        conPaso ? el('button', { type: 'button', class: 'btn btn--chico fl-esc__paso', onclick: () => { if (elegirGlobal) elegirGlobal(e.paso); } }, (POR_CLAVE[e.paso] || {}).titulo || e.paso) : null),
      el('p', { class: 'fl-esc__hoy' }, el('span', null, 'Hoy: '), e.hoy),
      e.propuesta && e.propuesta !== '—' ? el('p', { class: 'fl-esc__prop' }, el('span', null, 'Propuesta: '), e.propuesta) : null));
}

function caminoAutomatico(ctx) {
  const { ui } = ctx;
  const { el } = ui;
  const c = contarEscenarios();
  const orden = ['cubierto', 'propuesta', 'construir', 'decidir', 'manos'];
  const barra = el('div', { class: 'fl-barra', role: 'img', 'aria-label': `${c.pct} % de las situaciones ya se resuelven solas` },
    orden.filter((k) => c[k]).map((k) => el('span', { class: ['fl-barra__tramo', `fl-barra__tramo--${k}`], title: `${ESTADOS_ESC[k].texto}: ${c[k]}`, style: { flexGrow: String(c[k]) } })));
  const lista = el('div', { class: 'fl-escs' });
  const filtros = el('div', { class: 'fl-filtros', role: 'group', 'aria-label': 'Filtrar situaciones' });
  const opciones = [['pendiente', 'Lo que falta', c.total - c.cubierto], ['decidir', 'Decides tú', c.decidir], ['propuesta', 'Espera tu firma', c.propuesta], ['construir', 'Por construir', c.construir], ['manos', 'Tus manos', c.manos], ['cubierto', 'Cubierto', c.cubierto], ['todos', 'Todas', c.total]];
  const pintar = () => {
    const sel = ordenarEscenarios().filter((e) => filtroEsc === 'todos' || (filtroEsc === 'pendiente' ? e.estado !== 'cubierto' : e.estado === filtroEsc));
    const grupos = AREAS.map((a) => [a, sel.filter((e) => e.area === a)]).filter(([, l]) => l.length);
    ui.reemplazar(lista, grupos.length ? grupos.map(([a, l]) => el('div', { class: 'fl-esc-grupo' }, el('h4', null, `${a} · ${l.length}`), l.map((e) => filaEscenario(ui, e, true)))) : el('span', { class: 'fl-vacio' }, 'Nada en este filtro.'));
    ui.reemplazar(filtros, opciones.map(([k, t, n]) => el('button', { type: 'button', class: ['fl-filtro', filtroEsc === k ? 'fl-filtro--activo' : null], 'aria-pressed': filtroEsc === k ? 'true' : 'false', onclick: () => { filtroEsc = k; pintar(); } }, `${t} · ${n}`)));
  };
  pintar();
  return el('div', null,
    el('div', { class: 'fl-camino' },
      el('div', { class: 'fl-camino__pct' }, el('strong', null, `${c.pct} %`), el('span', null, `${c.cubierto} de ${c.total} situaciones se resuelven solas`)),
      barra,
      el('div', { class: 'fl-barra__ley' }, orden.map((k) => el('span', null, el('i', { class: ['fl-punto', `fl-barra__tramo--${k}`] }), `${ESTADOS_ESC[k].texto} ${c[k]}`)))),
    filtros, lista);
}

const NOMBRE_TAREA = { 'vigilancia-ofertas': 'Vigilancia (cada hora)', 'radar-ofertas': 'Radar (cada 2 h)', 'renovacion-diaria': 'Renovación diaria', 'buscar-ofertas': 'Banco de ofertas', 'lanzar-ofertas': 'Lanzamientos (2 por día)', 'revision-diaria': 'Revisión diaria', 'soporte-clientes': 'Soporte (2 por día)' };
function copiar(ui, texto, etiqueta) {
  return ui.el('button', { type: 'button', class: 'btn btn--chico', onclick: async (ev) => {
    try { await navigator.clipboard.writeText(texto); ev.currentTarget.textContent = 'Copiado ✓'; } catch (_) { ev.currentTarget.textContent = texto; }
  } }, ui.icono('copiar', { tam: 12 }), etiqueta);
}
// Ventanas que abrió «Lo que espera tus manos», por oferta: «Listo» las cierra (pedido del dueño, 13-nov: «que se cierren esas pantallas»).
// Se abren con window.open (no con un enlace) para poder cerrarlas después; se corta el vínculo `opener` antes de cargar la página ajena.
const ventanas = new Map();
function abrirVentana(grupo, url) {
  const w = window.open('about:blank', '_blank');
  if (!w) { window.open(url, '_blank', 'noopener'); return; }
  try { w.opener = null; } catch (_) { /* nada */ }
  w.location.href = url;
  if (!ventanas.has(grupo)) ventanas.set(grupo, []);
  ventanas.get(grupo).push(w);
}
function cerrarVentanas(grupo) {
  for (const w of ventanas.get(grupo) || []) { try { w.close(); } catch (_) { /* ya cerrada */ } }
  ventanas.delete(grupo);
}
function enlace(ui, url, texto, grupo) {
  if (!grupo) return ui.el('a', { class: 'btn btn--chico', href: url, target: '_blank', rel: 'noopener noreferrer' }, ui.icono('enlace-externo', { tam: 12 }), texto);
  return ui.el('button', { type: 'button', class: 'btn btn--chico', onclick: () => abrirVentana(grupo, url) }, ui.icono('enlace-externo', { tam: 12 }), texto);
}
function tusManos(ctx, flujo) {
  const { ui } = ctx;
  const { el } = ui;
  const items = [...(flujo.manos || []), ...(flujo.servicios || []).filter((s) => s.critico && s.id !== 'kie' && (s.estado === 'error' || s.estado === 'aviso'))
    .map((s) => ({ tipo: 'servicio', urgente: s.estado === 'error', nombre: s.nombre, detalle: s.detalle, para: s.para, url: s.url, recarga: s.recarga }))];
  if (!items.length) return el('span', { class: 'fl-vacio' }, 'Nada pendiente de tu lado ahora.');
  return el('div', { class: 'fl-manos' }, items.map((m) => {
    if (m.tipo === 'capi' && m.estado === 'verificado') {
      return el('div', { class: 'fl-mano fl-mano--ok' },
        el('strong', null, '✓ ', `${m.oferta}: token de la API de conversiones verificado`),
        el('span', { class: 'fl-tarea__sub' }, `Comprobado en todas sus tiendas el ${String(m.verificado).slice(8, 10)}/${String(m.verificado).slice(5, 7)} a las ${String(m.verificado).slice(11, 16)}.`));
    }
    if (m.tipo === 'capi') {
      const grupo = `capi-${m.oferta}`;
      const verificando = m.estado === 'verificando';
      const boton = el('button', { type: 'button', class: ['btn', 'btn--primario', 'fl-mano__listo'], disabled: verificando,
        onclick: async (ev) => {
          const b = ev.currentTarget;
          b.disabled = true;
          b.textContent = 'Enviando…';
          cerrarVentanas(grupo);
          try { await ctx.api.post('/flujo/verificar', { tipo: 'capi', oferta: m.oferta }); ctx.recargar(); } catch (err) { b.disabled = false; b.textContent = 'No se pudo avisar: reintentar'; }
        } }, ui.icono('check', { tam: 13 }), verificando ? 'Verificando…' : 'Listo, ya lo cargué');
      return el('div', { class: ['fl-mano', verificando ? 'fl-mano--verificando' : 'fl-mano--urgente'] },
        el('strong', null, verificando ? `${m.oferta}: verificando el token de la API de conversiones…` : `${m.oferta}: falta el token de la API de conversiones`),
        verificando
          ? el('span', { class: 'fl-tarea__sub' }, 'La vigilancia lo comprueba en su próxima vuelta (cada hora, a los :02) y esto pasa a «verificado» solo. Mira solo si el campo quedó lleno, nunca el token.')
          : el('ol', { class: 'fl-mano__pasos' },
            el('li', null, 'Abre Meta, baja a «API de conversiones» → «Configurar integración directa» → marca «Configurar sin Dataset Quality API» → «Generar token de acceso» → copia el token. ', enlace(ui, m.url_meta, 'Abrir Meta', grupo), ' ', copiar(ui, m.pixel, `Píxel ${m.pixel}`)),
            el('li', null, 'Pégalo en el campo «Token de CAPI» de cada tienda (pestaña «Meta / Tracking») y guarda: ', ...m.tiendas.map((t) => enlace(ui, t.url, t.tienda, grupo))),
            el('li', null, 'Cuando termines, toca el botón: se cierran las pestañas que abriste desde aquí y el sistema lo verifica. ', boton)),
        verificando ? boton : null);
    }
    if (m.tipo === 'meta_token') {
      const grupo = 'meta-token';
      return el('div', { class: 'fl-mano' },
        el('strong', null, m.error === 'falta_token' ? 'Meta en vivo: falta el token de lectura (una sola vez, no vence)' : 'Meta en vivo: el token de lectura dejó de servir'),
        el('span', { class: 'fl-tarea__sub' }, 'Con este token el panel lee gasto, compras y ROAS de Meta cada 10 minutos sin usar Claude ni gastar tokens. Solo puede leer: no toca campañas.'),
        el('ol', { class: 'fl-mano__pasos' },
          el('li', null, 'En la configuración del negocio, «Apps» → «Agregar» → «Conectar un identificador de app» y pega el de tu app «tu app de Meta». ', enlace(ui, m.url_apps, 'Abrir Apps', grupo), ' ', copiar(ui, m.app, `App ${m.app}`)),
          el('li', null, '«Usuarios del sistema» → «Agregar» → nombre «lector-panel», rol Empleado. Después «Asignar activos» → Cuentas publicitarias → tu cuenta → solo «Ver rendimiento». ', enlace(ui, m.url_usuarios, 'Abrir usuarios del sistema', grupo), ' ', copiar(ui, m.cuenta, `Cuenta ${m.cuenta}`)),
          el('li', null, '«Generar token» → app tu app de Meta → vencimiento «Nunca» → permiso ads_read → copia el token.'),
          m.nube
            // capa en la nube (14-nov): el token vive como secreto del worker «fabrica-vivo», no en la Mac
            ? el('li', null, 'Abre la Terminal, pega este comando y Enter; cuando pida el valor, pega el token y Enter (no se ve al escribir). ',
              copiar(ui, 'cd "$HOME/Digital Products/infra/workers/vivo" && npx wrangler secret put META_ACCESS_TOKEN', 'Copiar el comando'))
            : el('li', null, 'Abre el archivo .env de la carpeta del proyecto y agrega una línea con META_ACCESS_TOKEN= seguido del token. Guarda. ', copiar(ui, 'META_ACCESS_TOKEN=', 'Copiar el comienzo de la línea')),
          el('li', null, m.nube ? 'Listo: la nube lo usa en la próxima vuelta (5 minutos) y este aviso desaparece.' : 'Listo: el panel lo detecta solo en menos de 10 minutos y este aviso desaparece.')));
    }
    if (m.tipo === 'servicio') {
      return el('div', { class: ['fl-mano', m.urgente ? 'fl-mano--urgente' : null] },
        el('strong', null, `${m.nombre}: ${m.detalle}`), el('span', { class: 'fl-tarea__sub' }, `Lo usa: ${m.para}. ${m.recarga ? `Cómo: ${m.recarga}` : ''}`), m.url ? enlace(ui, m.url, 'Resolver') : null);
    }
    if (m.tipo === 'kie') {
      return el('div', { class: ['fl-mano', m.urgente ? 'fl-mano--urgente' : null] },
        el('strong', null, `Kie: quedan ${Math.round(m.saldo).toLocaleString('es-AR')} créditos`),
        el('span', { class: 'fl-tarea__sub' }, 'Alcanza para menos de 2 rondas de renovación. '), enlace(ui, m.url, 'Recargar en Kie'));
    }
    return null;
  }));
}

const TONO_SERVICIO = { ok: 'ok', aviso: 'aviso', error: 'error', sin_dato: 'neutro' };
function servicios(ctx, flujo) {
  const { ui } = ctx;
  const { el } = ui;
  const lista = flujo.servicios || [];
  if (!lista.length) return el('span', { class: 'fl-vacio' }, 'Sin registro de servicios (ofertas/_funnels/servicios.json).');
  const orden = { error: 0, aviso: 1, sin_dato: 2, ok: 3 };
  return el('div', { class: 'fl-servicios' }, [...lista].sort((a, b) => (orden[a.estado] ?? 2) - (orden[b.estado] ?? 2)).map((s) => el('div', { class: ['fl-servicio', s.estado === 'error' || s.estado === 'aviso' ? `fl-servicio--${s.estado}` : null] },
    el('span', { class: ['fl-salud', `fl-salud--${TONO_SERVICIO[s.estado] || 'neutro'}`] }, s.nombre),
    el('span', { class: 'fl-servicio__det' }, s.estado === 'sin_dato' ? 'todavía sin lectura' : s.detalle || s.estado),
    s.recarga ? el('span', { class: 'fl-tarea__sub' }, `Cómo recargar: ${s.recarga}`) : null,
    s.viejo ? el('span', { class: ['fl-salud', 'fl-salud--aviso'], title: `Se tiene que leer cada ${horasTexto(s.cada_horas)} y la última lectura es de hace ${horasTexto(s.edad_horas)}: el número de arriba puede no ser el de ahora.` }, 'desactualizado') : null,
    el('span', { class: 'fl-tarea__sub' }, `${s.para}${s.renueva ? ` · renueva el ${s.renueva}` : ''}${typeof s.edad_horas === 'number' ? ` · leído hace ${horasTexto(s.edad_horas)}` : ''}${s.cada_horas ? ` · se lee cada ${horasTexto(s.cada_horas)}` : ''}`),
    s.url ? enlace(ui, s.url, s.estado === 'error' || s.estado === 'aviso' ? 'Resolver' : 'Abrir') : null)));
}

/** 0,4 → «menos de 1 h»; 5 → «5 h»; 30 → «1 día»; 168 → «7 días». */
export function horasTexto(h) {
  if (typeof h !== 'number' || !Number.isFinite(h)) return '—';
  if (h < 1) return 'menos de 1 h';
  if (h < 36) return `${Math.round(h)} h`;
  const d = Math.round(h / 24);
  return `${d} ${d === 1 ? 'día' : 'días'}`;
}

const LADO = { anuncios: 'el problema está en los anuncios (subió el costo por visita): lo arregla la renovación', pagina_y_cobro: 'el problema está en la página o el cobro (bajó el ingreso por visita)', ambos: 'subió el costo por visita y bajó el ingreso por visita', estable: 'estable contra los 3 días anteriores', poca_muestra: 'todavía poca muestra para comparar' };
const ACCION_ANUNCIO = { NO_TOCAR: 'no tocar', REHACER_CUERPO: 'rehacer cuerpo', REHACER_CTA: 'rehacer llamado', REHACER_IMAGEN: 'rehacer imagen', POCA_MUESTRA: 'poca muestra' };
function dondeSePierde(ctx, flujo) {
  const { ui } = ctx;
  const { el } = ui;
  const filas = flujo.embudo || [];
  if (!filas.length) return el('span', { class: 'fl-vacio' }, 'Sin lecturas todavía: aparece después de la próxima vuelta de la vigilancia.');
  const tramo = (rot, valor, sufijo, estado) => el('span', { class: ['fl-embudo__tramo', estado ? `fl-embudo__tramo--${estado}` : null] },
    el('small', null, rot), el('strong', null, typeof valor === 'number' ? `${valor.toLocaleString('es-AR')}${sufijo}` : '—'));
  const umbral = (v, min) => (typeof v === 'number' ? (v < min ? 'mal' : 'bien') : null);
  return el('div', { class: 'fl-embudo' }, filas.map((f) => el('div', { class: 'fl-embudo__fila' },
    el('strong', null, f.oferta),
    el('div', { class: 'fl-embudo__tramos' },
      tramo('Costo por visita', f.costo_por_visita, ' USD'),
      tramo('Llega a la página', f.carga_pct, ' %', umbral(f.carga_pct, 60)),
      tramo('Página → pago', f.pagina_a_pago_pct, ' %', umbral(f.pagina_a_pago_pct, 8)),
      tramo('Pago → compra', f.pago_a_compra_pct, ' %', umbral(f.pago_a_compra_pct, 25)),
      tramo('Ingreso por visita', f.ingreso_por_visita, ' USD', typeof f.ingreso_por_visita === 'number' && typeof f.costo_por_visita === 'number' ? (f.ingreso_por_visita < f.costo_por_visita ? 'mal' : 'bien') : null)),
    f.lado ? el('span', { class: 'fl-tarea__sub' }, `Últimos 3 días: ${LADO[f.lado] || f.lado}${f.clon === 'sospecha' ? ' · sospecha de clon' : ''}${f.cpm_estado === 'ANORMAL' ? ' · CPM al doble de lo normal' : ''}.`) : null,
    Object.keys(f.anuncios || {}).length ? el('span', { class: 'fl-tarea__sub' }, `Anuncios: ${Object.entries(f.anuncios).map(([k, n]) => `${n} ${ACCION_ANUNCIO[k] || k}`).join(' · ')}.`) : null,
    ...(f.avisos || []).map((m) => el('span', { class: 'fl-tarea__sub fl-aviso--urgente' }, m)))));
}

function tareasYAvisos(ctx, flujo) {
  const { ui } = ctx;
  const { el } = ui;
  const tareas = flujo.tareas || [];
  const avisos = flujo.avisos || [];
  const tono = { ok: 'ok', aviso: 'aviso', error: 'error', sin_dato: 'neutro' };
  return el('div', { class: 'fl-det' },
    el('div', null, el('h4', { class: 'fl-h4' }, 'Tareas que corren solas'),
      el('div', { class: 'fl-tareas' }, tareas.map((t) => el('div', { class: 'fl-tarea' },
        el('span', { class: ['fl-salud', `fl-salud--${tono[t.salud] || 'neutro'}`] }, NOMBRE_TAREA[t.tarea] || t.tarea),
        el('span', { class: 'fl-tarea__sub' }, t.salud === 'sin_dato' ? 'todavía sin latido' : `hace ${horas(t.edad_min)}${t.fallas_seguidas ? ` · ${t.fallas_seguidas} fallas seguidas` : ''}${t.detalle ? ` · ${t.detalle}` : ''}`))))),
    el('div', null, el('h4', { class: 'fl-h4' }, 'Últimos avisos a tu celular'),
      avisos.length ? el('ul', { class: 'fl-avisos' }, avisos.map((x) => el('li', { class: x.urgente ? 'fl-aviso--urgente' : null }, `${String(x.cuando).slice(5, 16).replace('T', ' ')} · ${conPaises(x.mensaje)}`)))
        : el('span', { class: 'fl-vacio' }, 'Ninguno todavía.')));
}

function bloqueVigilancia(ui, v) {
  const { el } = ui;
  return el('div', { class: 'fl-det__bloque' }, el('h4', null, 'Última vuelta de la vigilancia'),
    el('ul', null,
      el('li', null, `Hace ${horas(v.edad_min)} · ${v.vueltas_24h} vueltas en las últimas 24 h.`),
      ...(v.tests || []).map((t) => el('li', null, `${t.test}${t.mercado ? ` · ${mercadoLargo(t.mercado)}` : ''}: ${textoDecision(t.decision)}${typeof t.gasto_usd === 'number' ? ` · gastó US$ ${t.gasto_usd.toFixed(2)}` : ''}${typeof t.ventas === 'number' ? ` · ${t.ventas} ventas` : ''}`))));
}
const DECISIONES = { APAGAR: 'apagar ahora', CERCA: 'cerca del corte', SIGUE: 'sigue en test', ENTREGA_BAJA: 'Meta casi no entregó', POST_LANZAMIENTO: 'pasó el test', SIN_PAUTA: 'todavía no arrancó', SIN_PRECIO: 'falta el precio', SIN_LECTURA: 'sin lectura' };
function textoDecision(d) { return DECISIONES[d] || String(d || '—').toLowerCase(); }

const ESTADO_RADAR = { a_medir: 'por medir', a_verificar: 'por verificar', verificada: 'verificada', exportada: 'en el banco', medida: 'medida' };
function bloqueRadar(ui, r) {
  const { el } = ui;
  if (!r.existe) return el('div', { class: 'fl-det__bloque' }, el('h4', null, 'Radar de ofertas'), el('span', { class: 'fl-vacio' }, 'Todavía no corrió.'));
  const pe = r.por_estado || {};
  return el('div', { class: 'fl-det__bloque' }, el('h4', null, 'Radar de ofertas'),
    el('ul', null,
      el('li', null, `${r.hoy} búsquedas hoy · ${r.cubiertas_7_dias} de ${r.busquedas} en 7 días (${String(r.cobertura_pct).replace('.', ',')} %) · ${r.paises} mercados tocados.`),
      el('li', null, `${r.ofertas} ofertas encontradas: ${pe.a_medir || 0} por medir, ${pe.a_verificar || 0} por verificar, ${(pe.verificada || 0) + (pe.exportada || 0)} verificadas, ${pe.descartada || 0} descartadas.`),
      r.bloqueo ? el('li', null, `En pausa por bloqueo hasta ${String(r.bloqueo.hasta).slice(0, 16).replace('T', ' ')}.`) : null,
      ...(r.mejores || []).map((m) => el('li', null, `Joya ${String(m.joya).replace('.', ',')} · ${m.pagina} · ${m.anuncios} anuncios · ${m.dias} días · ${ESTADO_RADAR[m.estado] || m.estado}`))));
}

function bloqueBanco(ui, b, d = {}) {
  const { el } = ui;
  const diarioTexto = d.fecha ? `Última vuelta diaria: ${d.fecha}${d.resumen ? ` · ${d.resumen}` : ''}.` : 'La vuelta diaria (08:15) todavía no corrió.';
  if (b.error) return el('div', { class: 'fl-det__bloque' }, el('h4', null, 'Banco de candidatos'), el('span', { class: 'fl-vacio' }, b.error));
  return el('div', { class: 'fl-det__bloque' }, el('h4', null, 'Banco de candidatos'),
    el('ul', null,
      el('li', null, `${b.veredicto === 'ALCANZA' ? 'Alcanza para elegir sin barrer' : 'Hay que barrer antes de elegir'}.`),
      el('li', null, `${b.ofertas ?? 0} ofertas en el banco, ${b.usadas ?? 0} ya usadas; ${(b.listos || []).length} listas para elegir.`),
      b.ultimo_barrido ? el('li', null, `Último barrido: ${b.ultimo_barrido}.`) : null,
      el('li', null, diarioTexto),
      ...(b.motivos || []).map((m) => el('li', null, `Motivo: ${m}.`))));
}

function brecha(ui, b, conPaso) {
  const { el } = ui;
  const paso = POR_CLAVE[b.paso];
  return el('div', { class: 'fl-brecha' },
    el('span', { class: ['fl-brecha__g', `fl-brecha__g--${b.gravedad}`] }, b.gravedad),
    el('span', { class: 'fl-brecha__t' }, b.titulo),
    conPaso && paso ? el('button', { type: 'button', class: 'btn btn--chico', onclick: () => { elegirGlobal && elegirGlobal(b.paso); } }, paso.titulo) : el('span'),
    el('p', { class: 'fl-brecha__d' }, b.detalle),
    el('p', { class: 'fl-brecha__c' }, el('strong', null, 'Cómo se cierra: '), b.cierre));
}
let elegirGlobal = null;

function radarTile(tile, r, b) {
  if (!r.existe) return tile(b.error ? 'neutro' : b.veredicto === 'ALCANZA' ? 'ok' : 'aviso', 'lupa', 'Radar de ofertas', 'sin correr', `Banco: ${b.veredicto === 'ALCANZA' ? 'alcanza' : 'hay que barrer'}`);
  const pe = r.por_estado || {};
  const tono = r.bloqueo ? 'aviso' : (typeof r.edad_min === 'number' && r.edad_min > 300) ? 'error' : 'ok';
  return tile(tono, 'lupa', 'Radar de ofertas', `${r.ofertas} ofertas`,
    `${r.hoy} búsquedas hoy · ${pe.a_verificar || 0} por verificar · banco: ${b.veredicto === 'ALCANZA' ? 'alcanza' : 'hay que barrer'}`);
}

function pulso(ui, flujo, reparto, ofertas, atencion) {
  const { el } = ui;
  const v = flujo.vigilancia || {};
  const b = flujo.banco || {};
  const enJuego = ofertas.filter((o) => o.etapa && !['apagada'].includes(o.etapa.clave)).length;
  // lo que solo tú puedes destrabar: hoy, ofertas que cruzaron el corte y siguen activas (escalar ya es automático)
  const pendientes = [...(reparto.apagar || []).filter((x) => x.urgente).map((x) => `${x.nombre}: apagar`)];
  const esperan = pendientes.length;
  const avisos = (atencion || []).filter((a) => a && ['critico', 'grave'].includes(a.tono)).length;
  const tVig = !v.existe ? 'error' : v.salud;
  const cr = contarReglas();
  const tile = (tono, icono, rot, valor, sub) => el('div', { class: ['fl-tile', `fl-tile--${tono}`] },
    el('span', { class: 'fl-tile__rot' }, ui.icono(icono, { tam: 14 }), rot), el('span', { class: 'fl-tile__valor' }, valor), el('span', { class: 'fl-tile__sub' }, sub));
  return el('div', { class: 'fl-pulso' },
    tile(tVig === 'ok' ? 'ok' : tVig === 'aviso' ? 'aviso' : 'error', 'pulso', 'Vigilancia de cada hora',
      v.existe ? `hace ${horas(v.edad_min)}` : 'sin vueltas', v.existe ? `${v.vueltas_24h} vueltas en 24 h · corta los tests solos` : 'No hay registro de la tarea'),
    radarTile(tile, flujo.radar || {}, b),
    tile('neutro', 'caja', 'Ofertas en juego', String(enJuego), `${(reparto.lanzar || []).length} lanzándose · ${(reparto.test || []).length} en test · ${(reparto.renovar || []).length} después del test`),
    (() => { const ce = contarEscenarios(); return tile(ce.pct >= 80 ? 'ok' : 'aviso', 'escudo', 'Automático', `${ce.pct} %`, `${ce.cubierto} de ${ce.total} situaciones · ${ce.decidir + ce.propuesta} esperan tu decisión · ${ce.construir} por construir`); })(),
    tile(esperan ? 'aviso' : 'ok', 'usuario', 'Esperan tu decisión', String(esperan),
      `${esperan ? pendientes.join(' · ') : 'Ninguna decisión pendiente'}${avisos ? ` · ${avisos} avisos en Negocio` : ''}`),
    (() => {
      const sv = flujo.servicios || [];
      const mal = sv.filter((x) => x.estado === 'error' || x.estado === 'aviso');
      const tono = sv.some((x) => x.estado === 'error' && x.critico) ? 'error' : mal.length ? 'aviso' : 'ok';
      return tile(sv.length ? tono : 'neutro', 'check', 'Servicios y saldos', `${sv.filter((x) => x.estado === 'ok').length} de ${sv.length}`,
        mal.length ? `revisar: ${mal.map((x) => x.nombre.split(' (')[0]).join(' · ')}` : 'todo pago, cargado y conectado');
    })());
}

export async function render(ctx) {
  const { ui } = ctx;
  const { el } = ui;
  ui.instalarEstilos('flujo', CSS);
  if (!seleccion) seleccion = leerSeleccion() || 'test';
  let neg = null;
  let flujo = null;
  const [rn, rf] = await Promise.allSettled([ctx.api.sobre('/negocio'), ctx.api.sobre('/flujo')]);
  if (rf.status === 'rejected') {
    return el('div', { class: 'pagina' }, ui.encabezadoPagina({ titulo: 'Cómo funciona', descripcion: 'No se pudo leer el estado del sistema.', migas: [] }),
      ui.errorBox(rf.reason, { reintentar: () => ctx.recargar() }));
  }
  flujo = rf.value.datos || {};
  neg = rn.status === 'fulfilled' && rn.value.datos ? rn.value.datos : { ofertas: [], atencion: [] };
  const ofertas = Array.isArray(neg.ofertas) ? neg.ofertas : [];
  const reparto = repartir(ofertas, flujo.armado || []);
  const salud = saludDe(reparto, flujo);
  ultimo = { reparto, flujo };

  const zonaDetalle = el('div');
  const zonaMapa = el('div');
  const pintar = () => {
    ui.reemplazar(zonaMapa, mapa(ctx, reparto, salud, elegir));
    ui.reemplazar(zonaDetalle, ui.seccion(`Detalle · ${(POR_CLAVE[seleccion] || PROCESOS[0]).titulo}`, detalle(ctx, seleccion, reparto, flujo), { id: 'fl-detalle' }));
  };
  function elegir(clave) {
    seleccion = clave;
    guardarSeleccion(clave);
    pintar();
    const d = globalThis.document && globalThis.document.getElementById('fl-detalle');
    if (d && typeof d.scrollIntoView === 'function' && globalThis.innerWidth < 1100) d.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  elegirGlobal = elegir;
  pintar();

  const v = flujo.vigilancia || {};
  const tonoVivo = !v.existe ? 'error' : v.salud === 'ok' ? 'ok' : v.salud === 'aviso' ? 'aviso' : 'error';
  if (temporizador) clearInterval(temporizador);
  temporizador = setInterval(() => { if (!(globalThis.document && globalThis.document.querySelector('.modal-fondo'))) ctx.recargar(); }, 5 * 60 * 1000);
  ctx.alSalir(() => { if (temporizador) { clearInterval(temporizador); temporizador = null; } });

  return el('div', { class: 'pagina' },
    ui.encabezadoPagina({
      titulo: 'Cómo funciona',
      descripcion: 'El sistema de ofertas paso a paso: qué skill hace cada paso, cuándo se activa, quién decide y qué ofertas están ahí ahora.',
      migas: [],
      acciones: [el('span', { class: ['fl-vivo', `fl-vivo--${tonoVivo}`], title: 'Se actualiza solo cuando cambia el libro de tests o corre la vigilancia, y cada 5 minutos' },
        el('span', { class: 'fl-vivo__punto', 'aria-hidden': 'true' }), `En vivo · ${new Date().toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })}`)],
    }),
    pulso(ui, flujo, reparto, ofertas, neg.atencion),
    ui.seccion('Lo que espera tus manos', tusManos(ctx, flujo), { ayuda: 'Lo único que el sistema no puede hacer solo, con los enlaces para hacerlo en un minuto.' }),
    ui.seccion('Servicios y saldos', servicios(ctx, flujo), { ayuda: 'Todo lo que tiene que estar pago, cargado o conectado para que el sistema funcione. Se lee solo: Kie y Gemini cada mañana; Meta, Claude e Impul Pay en la revisión diaria. En rojo o amarillo también aparece arriba, en «Lo que espera tus manos».' }),
    ui.seccion('Dónde se pierde cada oferta', dondeSePierde(ctx, flujo), { ayuda: 'Cada tramo del embudo de hoy: en rojo lo que está bajo la referencia (llega a la página 60 %, página → pago 8 %, pago → compra 25 %, ingreso por visita mayor al costo). Lo calcula la vigilancia cada hora; la comparación de 3 días y el diagnóstico de anuncios, la revisión y la renovación diarias.' }),
    ui.seccion('Tareas y avisos', tareasYAvisos(ctx, flujo), { ayuda: 'Cada tarea deja un latido al terminar: en rojo si falla 3 veces seguidas o si no corre hace el doble de su ritmo.' }),
    ui.seccion('El flujo', zonaMapa, { ayuda: 'Cada caja es un proceso. Las ofertas se mueven solas de caja en caja según su etapa en el libro de tests.' }),
    zonaDetalle,
    ui.seccion('Camino al 100 % automático', caminoAutomatico(ctx), { ayuda: 'Cada situación que le puede pasar al negocio: si ya se resuelve sola, si espera tu firma, si falta construirla o si siempre necesita tus manos.' }),
    ui.seccion('Una regla por situación', tablaReglas(ctx), { ayuda: 'Las firmadas se ejecutan solas; las propuestas se calculan y se informan hasta que las firmes. Fuente: escalar-oferta/references/02-decidir.md.' }),
    el('div', { class: 'fl-cerradas' }, el('strong', null, `Cerrado el 13-nov (${CERRADAS.length}):`), CERRADAS.map((c) => el('span', null, `✓ ${c.titulo}: ${c.texto}`))));
}

/** En vivo: se vuelve a dibujar cuando cambia el libro, la vigilancia, el historial o el banco. */
export function alCambio(ctx, evento) {
  const lote = (evento && evento.lote) || [evento];
  const toca = lote.some((e) => e && (!e.ruta || /libro-de-tests\.json$|vigilancia\.jsonl$|verificaciones\.jsonl$|servicios(_estado)?\.json$|embudo\.json$|meta_vivo\.json$|historial-modelado\.json$|barrido\/banco\/|_borrador-[^/]+\/estado\.md$/.test(e.ruta)));
  if (!toca && ultimo) return undefined;
  if (globalThis.document && globalThis.document.querySelector('.modal-fondo')) return undefined;
  return render(ctx);
}

export function alSalir() { if (temporizador) { clearInterval(temporizador); temporizador = null; } }
