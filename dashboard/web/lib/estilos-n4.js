// lib/estilos-n4.js — CSS propio de #/quien-decide (clases `qd-*`). Se instala con `ui.instalarEstilos('n4-quien-decide', ESTILOS_N4_QUIEN_DECIDE)`:
// hoja construida por CSSOM (la CSP `style-src 'self'` no admite <style> ni style="" en línea).
// Usa SOLO tokens de styles.css (--sup, --borde, --info, --acento-bg, --ok, --aviso…): ninguna paleta propia, y por tanto claro y oscuro sin retoques.
//
// LENGUAJE VISUAL DE LA HONESTIDAD (estado honesto): lo que RIGE HOY va con borde continuo y superficie sólida; el OBJETIVO (J2, aún sin implementar)
// va con borde DISCONTINUO y un tinte informativo. Así, a golpe de vista, lo discontinuo nunca es la realidad vigente. El color nunca va solo: cada estado
// lleva icono y etiqueta en el DOM.
// Se adapta al ancho de SU contenedor (container queries sobre `.qd`), no al de la ventana: con el menú lateral abierto o cerrado se ve igual de bien.

export const ESTILOS_N4_QUIEN_DECIDE = `
.qd { container-type: inline-size; container-name: qd; }
/* la cabecera compartida lleva pestañas que no se parten: sin esto su ancho mínimo empuja el título fuera de la pantalla en móvil */
.qd .cab { grid-template-columns: minmax(0, 1fr); }
.qd .cab__pestanas { min-width: 0; }

/* ───────── utilidades ───────── */
.qd-pila { display: grid; gap: var(--e-3); min-width: 0; align-content: start; }
.qd-pila--chica { gap: var(--e-1); }
.qd-fila { display: flex; flex-wrap: wrap; gap: var(--e-2) var(--e-3); align-items: center; min-width: 0; }
.qd-fila--junta { gap: var(--e-1) var(--e-2); }
.qd-sub { color: var(--txt-2); font-size: .86rem; overflow-wrap: anywhere; min-width: 0; }
.qd-tenue { color: var(--txt-3); }
.qd-mono { font-family: var(--mono); font-size: .86em; overflow-wrap: anywhere; }
/* «Cómo leer esta pantalla»: caja plegable con los cinco niveles de autonomía */
.qd-como { padding: 10px 14px; border: 1px solid var(--borde); border-radius: var(--r-3); background: var(--sup); min-width: 0; }
.qd-como > summary { cursor: pointer; font-weight: 600; }
.qd-como > summary:focus-visible { outline: 2px solid var(--acento); outline-offset: 2px; border-radius: var(--r-1); }
.qd-niveles { margin: 0; padding-left: 20px; display: grid; gap: var(--e-1); }
.qd-niveles li { overflow-wrap: anywhere; }
.qd-titulo-chico { font-size: .76rem; text-transform: uppercase; letter-spacing: .06em; color: var(--txt-2); font-weight: 650; }
.qd .chip { white-space: normal; height: auto; min-height: 22px; padding-top: 3px; padding-bottom: 3px; line-height: 1.25; text-align: left; overflow: visible; }

/* ───────── etiquetas HOY / OBJETIVO ───────── */
.qd-etiqueta { display: inline-flex; align-items: center; gap: 6px; min-height: 24px; padding: 2px 10px 2px 8px; border-radius: var(--r-pill); font-size: var(--t-xs); font-weight: 700; letter-spacing: .03em; border: 1px solid; line-height: 1.2; }
.qd-etiqueta--hoy { color: var(--txt); background: var(--sup-3); border-color: var(--borde-fuerte); }
.qd-etiqueta--objetivo { color: var(--info); background: transparent; border: 1px dashed color-mix(in srgb, var(--info) 70%, transparent); }

/* ───────── cartel de arriba: HOY frente a OBJETIVO ───────── */
.qd-banner { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--e-3); }
.qd-bloque { display: grid; gap: var(--e-2); align-content: start; padding: var(--pad-tarjeta); border-radius: var(--r-3); min-width: 0; }
.qd-bloque--hoy { background: var(--sup); border: 1px solid var(--borde); box-shadow: var(--sombra); }
.qd-bloque--objetivo { background: color-mix(in srgb, var(--info-bg) 55%, var(--sup)); border: 1px dashed color-mix(in srgb, var(--info) 55%, transparent); }
.qd-bloque__titulo { font-size: var(--t-md); font-weight: 650; line-height: 1.3; overflow-wrap: anywhere; }
.qd-bloque__texto { color: var(--txt-2); overflow-wrap: anywhere; }
.qd-metricas { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: var(--e-3); }

/* ───────── avisos en caja (siempre con icono) ───────── */
.qd-aviso { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--e-2); align-items: start; border: 1px solid var(--aviso-borde); background: var(--aviso-bg); border-radius: var(--r-2); padding: var(--e-2) var(--e-3); color: var(--txt); font-size: .9rem; overflow-wrap: anywhere; min-width: 0; }
.qd-aviso__icono { color: var(--aviso); display: inline-flex; padding-top: 1px; }
.qd-aviso--info { border-color: var(--info-borde); background: var(--info-bg); }
.qd-aviso--info .qd-aviso__icono { color: var(--info); }
.qd-aviso--objetivo { border: 1px dashed color-mix(in srgb, var(--info) 60%, transparent); background: color-mix(in srgb, var(--info-bg) 55%, var(--sup)); }
.qd-aviso--objetivo .qd-aviso__icono { color: var(--info); }
.qd-aviso__texto { min-width: 0; display: grid; gap: 2px; }

/* ───────── HOY: leyenda, controles y tabla ───────── */
.qd-leyenda { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: var(--e-2) var(--e-4); align-items: start; }
.qd-leyenda__it { display: grid; gap: 4px; justify-items: start; align-content: start; min-width: 0; }
.qd-controles { display: flex; flex-wrap: wrap; gap: var(--e-3); align-items: center; }
.qd-buscar { max-width: 320px; width: 100%; }
.qd .segmentado { max-width: 100%; overflow-x: auto; }
.qd .segmentado__op { white-space: nowrap; }
.qd-nom { display: grid; gap: 2px; min-width: 190px; }
.qd-nom strong { font-weight: 600; }
.qd-nom .qd-sub { font-size: .8rem; }
.qd-quien { display: grid; gap: 4px; justify-items: start; min-width: 150px; max-width: 260px; }
.qd-quien__nota { color: var(--txt-2); font-size: .8rem; display: inline-flex; gap: 4px; align-items: flex-start; overflow-wrap: anywhere; white-space: normal; }
.qd-quien__nota .icono { flex: none; margin-top: 2px; }
.qd-nivel { display: inline-flex; flex-wrap: wrap; align-items: baseline; gap: 4px; font-weight: 600; white-space: nowrap; }
.qd-tira { display: inline-flex; gap: 2px; align-items: center; }
.qd-tira__n { display: inline-flex; align-items: center; justify-content: center; width: 24px; height: 22px; border-radius: 4px; font-size: 11px; font-weight: 700; font-family: var(--mono); border: 1px solid var(--borde); color: var(--txt-2); background: var(--sup-2); }
.qd-tira__n[data-gate="H"] { background: var(--acento-bg); border-color: var(--acento-borde); color: var(--acento-fuerte); }
.qd-tira__n[data-gate="S"] { background: var(--info-bg); border-color: var(--info-borde); color: var(--info); }
.qd-tira__n[data-gate="A"] { background: var(--neutro-bg); border-color: var(--neutro-borde); color: var(--neutro); }
.qd-tira__n[data-gate="NA"] { background: transparent; border-style: dashed; color: var(--txt-3); }
.qd-tira__n.es-actual { outline: 2px solid var(--txt); outline-offset: 1px; }
.qd-topes { list-style: none; margin: 0; padding: 0; display: grid; gap: 2px; min-width: 240px; }
.qd-tope { display: flex; flex-wrap: wrap; gap: 0 8px; align-items: center; justify-content: space-between; font-size: .86rem; overflow-wrap: anywhere; }
.qd-tope__valor { font-variant-numeric: tabular-nums; font-weight: 600; }
.qd-tope__estado { display: inline-flex; gap: 3px; align-items: center; white-space: nowrap; font-size: .8rem; font-weight: 600; }
.qd-tope__estado--falta { color: var(--aviso); }
.qd-tope-aviso { color: var(--aviso); font-size: .8rem; font-weight: 600; margin-top: 2px; display: inline-flex; gap: 4px; align-items: flex-start; white-space: normal; }
.qd-tope-aviso .icono { flex: none; margin-top: 2px; }
.qd-cuenta { color: var(--txt-2); font-size: .86rem; }
.qd-vista-lista { display: none; }
.qd-lista { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-2); }
.qd-ficha { display: grid; gap: 6px; padding: var(--e-3); background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-2); min-width: 0; }
.qd-ficha__cab { display: flex; flex-wrap: wrap; gap: 4px var(--e-2); align-items: center; justify-content: space-between; }
.qd-ficha__cab strong { font-weight: 600; overflow-wrap: anywhere; min-width: 0; }
.qd-ficha .qd-topes { min-width: 0; }

/* ───────── OBJETIVO: las cuatro columnas ───────── */
.qd-cols4 { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--e-3); }
.qd-col { display: grid; gap: var(--e-2); align-content: start; padding: var(--pad-tarjeta); border-radius: var(--r-3); min-width: 0; border: 1px dashed color-mix(in srgb, var(--info) 55%, transparent); background: color-mix(in srgb, var(--info-bg) 40%, var(--sup)); }
.qd-col__cab { display: flex; gap: var(--e-2); align-items: center; font-weight: 650; line-height: 1.25; }
.qd-col__cab .icono { color: var(--info); flex: none; }
.qd-col__lista { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-2); }
.qd-col__item { display: grid; gap: 4px; justify-items: start; padding-top: var(--e-2); border-top: 1px solid var(--borde); min-width: 0; overflow-wrap: anywhere; }
.qd-col__item:first-child { border-top: 0; padding-top: 0; }

/* ───────── OBJETIVO: se conserva por código ───────── */
.qd-conserva { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-2); }
.qd-conserva__it { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: var(--e-2) var(--e-3); align-items: start; padding: var(--e-2) 0; border-top: 1px solid var(--borde); }
.qd-conserva__it:first-child { border-top: 0; padding-top: 0; }
.qd-conserva__texto { display: grid; gap: 2px; min-width: 0; overflow-wrap: anywhere; }
.qd-conserva__texto strong { font-weight: 600; }
.qd-conserva__it > .chip { justify-self: start; }

/* ───────── OBJETIVO: qué falta para llegar ───────── */
.qd-obj { display: grid; border: 1px solid var(--borde); border-radius: var(--r-3); overflow: hidden; background: var(--sup); }
.qd-obj__cab, .qd-obj__fila { display: grid; grid-template-columns: minmax(150px, 1fr) minmax(190px, 1.25fr) minmax(280px, 2.2fr); gap: var(--e-4); padding: var(--e-3) var(--pad-tarjeta); min-width: 0; }
.qd-obj__cab { background: var(--sup-2); border-bottom: 1px solid var(--borde); font-size: .76rem; text-transform: uppercase; letter-spacing: .06em; color: var(--txt-2); font-weight: 650; }
.qd-obj__grupo { display: flex; gap: var(--e-2); align-items: center; padding: 6px var(--pad-tarjeta); background: var(--sup-3); border-top: 1px solid var(--borde); font-weight: 650; font-size: .9rem; }
.qd-obj__fila { border-top: 1px solid var(--borde); }
.qd-obj__celda { display: grid; gap: 4px; align-content: start; justify-items: start; min-width: 0; overflow-wrap: anywhere; }
.qd-obj__celda > * { max-width: 100%; }
.qd-obj__celda strong { font-weight: 600; }
.qd-obj__hoy { list-style: none; margin: 0; padding: 0; display: grid; gap: 4px; font-size: .9rem; }
.qd-falta { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.qd-falta__it { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 8px; align-items: start; font-size: .9rem; }
.qd-falta__ic { display: inline-flex; margin-top: 2px; }
.qd-falta__ic--ok { color: var(--ok); }
.qd-falta__ic--pendiente { color: var(--aviso); }
.qd-falta__ic--plan { color: var(--info); }
.qd-falta__ic--nota { color: var(--txt-3); }
.qd-falta__ic--sin_dato { color: var(--aviso); }
.qd-falta__fuente { color: var(--txt-3); font-size: .78rem; display: block; }
@container qd (max-width: 780px) { .qd-vista-tabla { display: none; } .qd-vista-lista { display: block; } }
@container qd (max-width: 1100px) { .qd-cols4 { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@container qd (max-width: 820px) {
  .qd-obj__cab { display: none; }
  .qd-obj__fila { grid-template-columns: minmax(0, 1fr); gap: var(--e-2); }
  .qd-obj__celda[data-etiqueta]::before { content: attr(data-etiqueta); font-size: .74rem; text-transform: uppercase; letter-spacing: .06em; color: var(--txt-2); font-weight: 650; }
}
@container qd (max-width: 640px) {
  .qd-banner { grid-template-columns: minmax(0, 1fr); }
  .qd-cols4 { grid-template-columns: minmax(0, 1fr); }
  .qd-conserva__it { grid-template-columns: minmax(0, 1fr); }
}

/* ───────── FRENOS DE EMPRESA ───────── */
.qd-frenos { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--e-3); }
.qd-freno { display: grid; gap: var(--e-3); align-content: start; padding: var(--pad-tarjeta); background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); box-shadow: var(--sombra); min-width: 0; }
.qd-freno__cab { display: grid; gap: 2px; }
.qd-freno__titulo { display: flex; gap: var(--e-2); align-items: center; font-size: var(--t-md); font-weight: 650; }
.qd-freno__comparar { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--e-2); }
.qd-caja { display: grid; gap: 6px; align-content: start; padding: var(--e-3); border-radius: var(--r-2); border: 1px solid var(--borde); background: var(--sup-2); min-width: 0; }
.qd-caja--objetivo { border: 1px dashed color-mix(in srgb, var(--info) 60%, transparent); background: color-mix(in srgb, var(--info-bg) 45%, var(--sup)); }
.qd-caja__valor { font-size: var(--t-lg); font-weight: 650; font-variant-numeric: tabular-nums; line-height: 1.2; overflow-wrap: anywhere; }
.qd-caja__valor--vacio { font-size: var(--t-md); font-weight: 600; color: var(--txt-2); }
@container qd (max-width: 880px) { .qd-frenos { grid-template-columns: minmax(0, 1fr); } }
@container qd (max-width: 520px) { .qd-freno__comparar { grid-template-columns: minmax(0, 1fr); } }

/* ───────── SIGUE SIENDO HUMANO ───────── */
.qd-humano { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--e-3); }
.qd-card { display: grid; gap: var(--e-3); align-content: start; padding: var(--pad-tarjeta); background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); box-shadow: var(--sombra); min-width: 0; }
.qd-card__titulo { display: flex; gap: var(--e-2); align-items: center; font-size: var(--t-md); font-weight: 650; line-height: 1.25; }
.qd-card__titulo .icono { color: var(--acento); flex: none; }
.qd-card > .btn { justify-self: start; }
.qd-pasos { margin: 0; padding-left: 1.4em; list-style: decimal outside; display: grid; gap: 3px; color: var(--txt-2); font-size: .9rem; }
.qd-pasos > li { display: list-item; }
@container qd (max-width: 880px) { .qd-humano { grid-template-columns: minmax(0, 1fr); } }
`;
