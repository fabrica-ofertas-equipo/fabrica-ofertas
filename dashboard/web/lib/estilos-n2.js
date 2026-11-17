// lib/estilos-n2.js — CSS propio de Fábrica, Jurado, Países y Poscompra (clases `n2-*`). Solo datos (una cadena CSS): cada página lo instala con
// `ui.instalarEstilos('n2', CSS_N2)` (hoja construida por CSSOM; la CSP del panel no admite <style> ni style="" en línea).
// Usa SOLO tokens de styles.css (--sup, --borde, --txt, --ok, --aviso…): ninguna paleta propia. El color significa estado y el acento marca lo interactivo;
// los estados SIEMPRE llevan icono y etiqueta en el DOM (el color nunca va solo). Responsive: las rejillas se apilan a una columna en ~390 px.

export const CSS_N2 = `
/* ───────── utilidades ───────── */
.n2-pila { display: grid; gap: var(--e-4); grid-template-columns: minmax(0, 1fr); min-width: 0; align-content: start; }
.n2-pila--chica { gap: var(--e-2); }
.n2-pila > .n2-etq, .n2-pila > .n2-estado, .n2-pila > .chip { justify-self: start; }
.n2-fila { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e-2); min-width: 0; }
.n2-fila--entre { justify-content: space-between; }
.n2-fila--arriba { align-items: flex-start; }
.n2-tenue { color: var(--txt-3); }
.n2-peq { font-size: var(--t-sm); }
.n2-mono { font-family: var(--mono); font-size: .86em; overflow-wrap: anywhere; }
.n2-parrafo { margin: 0; color: var(--txt-2); line-height: 1.5; max-width: 80ch; }
.n2-parrafo strong { color: var(--txt); font-weight: 650; }
.n2-sobretitulo { margin: 0; font-size: .78rem; font-weight: 650; letter-spacing: .06em; text-transform: uppercase; color: var(--txt-3); }
.n2-subtitulo { margin: 0; font-size: var(--t-base); font-weight: 650; color: var(--txt); }
.n2-metricas { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: var(--e-3); }
.n2-etq { display: inline-flex; align-items: center; gap: 4px; padding: 1px 8px; border-radius: var(--r-pill); border: 1px solid var(--borde); background: var(--sup-2); color: var(--txt-2); font-size: .82rem; line-height: 1.5; max-width: 100%; }
.n2-etq--demo { border-style: dashed; border-color: var(--aviso-borde); background: var(--aviso-bg); color: var(--aviso); font-weight: 600; }
.n2-etq--hipotesis { border-style: dashed; background: transparent; color: var(--txt-3); }
.n2-etq--mono { font-family: var(--mono); font-size: .78rem; }
.n2-selector { display: inline-flex; align-items: center; gap: var(--e-2); flex-wrap: wrap; }
.n2-selector label { color: var(--txt-2); font-size: var(--t-sm); font-weight: 550; }

/* ───────── nota (mensaje breve con icono) ───────── */
.n2-nota { display: flex; gap: 10px; align-items: flex-start; padding: 10px 14px; border-radius: var(--r-2); border: 1px solid var(--info-borde); background: var(--info-bg); color: var(--txt); line-height: 1.5; min-width: 0; }
.n2-nota > .icono { flex: none; margin-top: 2px; color: var(--info); }
.n2-nota > div { min-width: 0; }
.n2-nota strong { font-weight: 650; }
.n2-nota p { margin: 0; }
.n2-nota p + p { margin-top: 4px; }
.n2-nota--aviso { border-color: var(--aviso-borde); background: var(--aviso-bg); }
.n2-nota--aviso > .icono { color: var(--aviso); }
.n2-nota--error { border-color: var(--error-borde); background: var(--error-bg); }
.n2-nota--error > .icono { color: var(--error); }
.n2-nota--ok { border-color: var(--ok-borde); background: var(--ok-bg); }
.n2-nota--ok > .icono { color: var(--ok); }
.n2-nota--neutra { border-color: var(--borde); background: var(--sup-2); }
.n2-nota--neutra > .icono { color: var(--txt-3); }

/* estado con icono + texto (nunca solo color) */
.n2-estado { display: inline-flex; align-items: center; gap: 6px; font-size: .9rem; font-weight: 600; line-height: 1.3; }
.n2-estado .icono { flex: none; }
.n2-estado--ok { color: var(--ok); }
.n2-estado--aviso { color: var(--aviso); }
.n2-estado--grave { color: var(--grave); }
.n2-estado--error { color: var(--error); }
.n2-estado--info { color: var(--info); }
.n2-estado--acento { color: var(--acento-fuerte); }
.n2-estado--neutro { color: var(--txt-3); }

/* ───────── tablas propias (texto largo que debe verse entero) ───────── */
.n2-scroll { overflow-x: auto; border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup); }
.n2-tabla { width: 100%; border-collapse: collapse; font-size: var(--t-sm); min-width: 620px; }
.n2-tabla th { text-align: left; font-weight: 650; font-size: .78rem; letter-spacing: .04em; text-transform: uppercase; color: var(--txt-3); padding: 8px 12px; background: var(--sup-2); border-bottom: 1px solid var(--borde); white-space: nowrap; }
.n2-tabla td { padding: 10px 12px; vertical-align: top; border-bottom: 1px solid var(--borde); color: var(--txt-2); line-height: 1.45; }
.n2-tabla tr:last-child td { border-bottom: 0; }
.n2-tabla td strong { color: var(--txt); font-weight: 650; }
.n2-tabla .n2-col-estrecha { width: 1%; white-space: nowrap; }
.n2-tabla--compacta { min-width: 0; }

/* ───────── línea de tiempo del turno de noche ───────── */
.n2-tiempo { list-style: none; margin: 0; padding: 0; display: grid; gap: 0; container-type: inline-size; }
.n2-paso { position: relative; display: grid; grid-template-columns: 56px 28px minmax(0, 1fr); column-gap: var(--e-3); padding-bottom: var(--e-4); }
.n2-paso:last-child { padding-bottom: 0; }
.n2-paso__hora { font-variant-numeric: tabular-nums; font-weight: 650; color: var(--txt-2); text-align: right; padding-top: 3px; font-size: var(--t-sm); }
.n2-paso__riel { position: relative; display: flex; justify-content: center; }
.n2-paso__riel::after { content: ''; position: absolute; top: 30px; bottom: calc(-1 * var(--e-4)); width: 2px; background: var(--borde-fuerte); border-radius: 2px; }
.n2-paso:last-child .n2-paso__riel::after { display: none; }
.n2-paso__nodo { z-index: 1; width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; background: var(--sup); border: 2px solid var(--borde-fuerte); color: var(--txt-2); }
.n2-paso--ok .n2-paso__nodo { border-color: var(--punto-ok); color: var(--ok); }
.n2-paso--aviso .n2-paso__nodo { border-color: var(--punto-aviso); color: var(--aviso); }
.n2-paso__cuerpo { display: grid; gap: 6px; min-width: 0; }
.n2-paso__nombre { margin: 0; font-size: var(--t-base); font-weight: 650; }
.n2-paso__que { margin: 0; color: var(--txt-2); line-height: 1.45; max-width: 70ch; }
.n2-paso__hoy { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: flex-start; padding: 8px 10px; border-radius: var(--r-2); background: var(--sup-2); font-size: var(--t-sm); color: var(--txt-2); line-height: 1.4; }
.n2-paso__hoy .n2-estado { flex: none; }
.n2-paso__hoy span:last-child { min-width: 0; flex: 1 1 240px; }
.n2-tarde { margin-top: var(--e-3); }
@container (max-width: 480px) {
  .n2-paso { grid-template-columns: 28px minmax(0, 1fr); }
  .n2-paso__hora { grid-column: 2; grid-row: 1; text-align: left; padding: 0 0 2px; }
  .n2-paso__riel { grid-column: 1; grid-row: 1 / span 2; }
  .n2-paso__cuerpo { grid-column: 2; grid-row: 2; }
}

/* ───────── piezas por aprobar ───────── */
.n2-oferta { display: grid; gap: var(--e-3); padding: var(--e-4); border: 1px solid var(--borde); border-radius: var(--r-3); background: var(--sup-2); min-width: 0; }
.n2-oferta__cab { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e-2) var(--e-3); justify-content: space-between; }
.n2-oferta__id { font-weight: 650; font-size: var(--t-md); overflow-wrap: anywhere; }
.n2-oferta__estados { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.n2-piezas { display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 300px), 1fr)); gap: var(--e-3); }
.n2-pieza { display: grid; grid-template-columns: 72px minmax(0, 1fr); gap: var(--e-3); padding: var(--e-3); border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup); min-width: 0; }
.n2-pieza__img { width: 72px; height: 90px; border-radius: var(--r-1); border: 1px solid var(--borde); background: var(--sup-3); object-fit: cover; display: grid; place-items: center; color: var(--txt-3); overflow: hidden; }
.n2-pieza__img img { width: 100%; height: 100%; object-fit: cover; display: block; }
.n2-pieza__cuerpo { display: grid; gap: 4px; min-width: 0; align-content: start; }
.n2-pieza__titulo { margin: 0; font-weight: 650; line-height: 1.3; overflow-wrap: anywhere; }
.n2-pieza__texto { margin: 0; color: var(--txt-2); font-size: var(--t-sm); line-height: 1.4; overflow-wrap: anywhere; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.n2-pieza__meta { display: flex; flex-wrap: wrap; gap: 4px; }

/* ───────── control de calidad (lista de 6) ───────── */
.n2-control { list-style: none; margin: 0; padding: 0; display: grid; gap: 0; border: 1px solid var(--borde); border-radius: var(--r-2); overflow: hidden; }
.n2-punto { display: grid; grid-template-columns: 32px minmax(0, 1.2fr) minmax(0, 1fr); gap: var(--e-3); padding: 12px 14px; border-bottom: 1px solid var(--borde); background: var(--sup); align-items: start; }
.n2-punto:last-child { border-bottom: 0; }
.n2-punto__n { width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; background: var(--sup-3); color: var(--txt-2); font-weight: 650; font-size: .86rem; font-variant-numeric: tabular-nums; }
.n2-punto__titulo { margin: 0; font-weight: 650; }
.n2-punto__explica { margin: 2px 0 0; color: var(--txt-2); font-size: var(--t-sm); line-height: 1.4; }
.n2-punto__res { display: grid; gap: 3px; min-width: 0; }
.n2-punto__evid { margin: 0; color: var(--txt-2); font-size: var(--t-sm); line-height: 1.4; overflow-wrap: anywhere; }
@container (max-width: 560px) { .n2-punto { grid-template-columns: 32px minmax(0, 1fr); } .n2-punto__res { grid-column: 2; } }
.n2-control-wrap { container-type: inline-size; }

/* ───────── anatomía y formatos ───────── */
.n2-anatomia { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: var(--e-3); counter-reset: ana; }
.n2-anatomia > li { display: grid; gap: 4px; align-content: start; padding: var(--e-3) var(--e-4); border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup-2); position: relative; }
.n2-anatomia__n { font-size: .74rem; font-weight: 650; letter-spacing: .06em; text-transform: uppercase; color: var(--txt-3); }
.n2-anatomia__nombre { margin: 0; font-size: var(--t-md); font-weight: 650; }
.n2-anatomia__nuestro { margin: 4px 0 0; padding-top: 6px; border-top: 1px dashed var(--borde-fuerte); color: var(--txt-2); font-size: var(--t-sm); line-height: 1.4; }
.n2-lema { margin: 0; padding: 10px 14px; border-left: 3px solid var(--acento); background: var(--acento-bg); border-radius: 0 var(--r-2) var(--r-2) 0; font-weight: 650; color: var(--txt); }
.n2-prohibido { display: grid; gap: var(--e-2); padding: var(--e-3) var(--e-4); border-radius: var(--r-2); border: 1px solid var(--error-borde); background: var(--error-bg); }
.n2-prohibido h3 { margin: 0; font-size: var(--t-base); font-weight: 650; color: var(--error); display: flex; align-items: center; gap: 6px; }
.n2-prohibido p { margin: 0; color: var(--txt); line-height: 1.5; }
.n2-prohibido > div { display: grid; gap: 2px; }

/* ───────── jurado ───────── */
.n2-pasos5 { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: var(--e-3); }
.n2-pasos5 > li { display: grid; gap: 6px; align-content: start; padding: var(--e-3) var(--e-4); border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup-2); }
.n2-pasos5__num { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; background: var(--acento-bg); color: var(--acento-fuerte); font-weight: 700; font-variant-numeric: tabular-nums; }
.n2-pasos5__titulo { margin: 0; font-weight: 650; font-size: var(--t-base); }
.n2-pasos5__texto { margin: 0; color: var(--txt-2); font-size: var(--t-sm); line-height: 1.45; }
.n2-regla { display: grid; gap: var(--e-2); padding: var(--e-4); border: 1px solid var(--acento-borde); border-radius: var(--r-3); background: var(--acento-bg); }
.n2-regla h3 { margin: 0; font-size: var(--t-md); font-weight: 650; display: flex; align-items: center; gap: 8px; color: var(--txt); }
.n2-regla p { margin: 0; color: var(--txt); line-height: 1.5; max-width: 80ch; }
.n2-barra { display: grid; gap: 4px; min-width: 0; }
.n2-barra__cab { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; font-size: .82rem; color: var(--txt-2); }
.n2-barra__valor { color: var(--txt); font-weight: 650; font-variant-numeric: tabular-nums; }
.n2-barra__pista { position: relative; height: 8px; border-radius: 99px; background: var(--sup-3); overflow: hidden; }
.n2-barra__relleno { position: absolute; inset: 0 auto 0 0; width: var(--p, 0%); border-radius: 99px; background: var(--acento); }
.n2-barra--ok .n2-barra__relleno { background: var(--punto-ok); }
.n2-barra--aviso .n2-barra__relleno { background: var(--punto-aviso); }
.n2-barra--error .n2-barra__relleno { background: var(--punto-error); }
.n2-tanda { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-2); }
.n2-tanda > li { display: grid; grid-template-columns: 36px minmax(0, 1fr); gap: var(--e-3); padding: var(--e-3); border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup); align-items: start; }
.n2-tanda__pos { width: 30px; height: 30px; border-radius: 50%; display: grid; place-items: center; background: var(--sup-3); font-weight: 700; font-variant-numeric: tabular-nums; }
.n2-tanda__cuerpo { display: grid; gap: 6px; min-width: 0; }
.n2-tanda__nombre { font-weight: 650; overflow-wrap: anywhere; }
.n2-votos { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.n2-voto { width: 22px; height: 22px; border-radius: 50%; display: grid; place-items: center; border: 1px solid var(--borde-fuerte); background: var(--sup-2); color: var(--txt-3); }
.n2-voto--si { background: var(--ok-bg); border-color: var(--ok-borde); color: var(--ok); }
.n2-voto--no { background: var(--error-bg); border-color: var(--error-borde); color: var(--error); }
.n2-motivos { margin: 0; padding: 0; list-style: none; display: grid; gap: 4px; font-size: var(--t-sm); color: var(--txt-2); }
.n2-motivos li { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 6px; align-items: baseline; }
details.n2-detalle > summary { cursor: pointer; color: var(--acento-fuerte); font-size: var(--t-sm); font-weight: 550; padding: 2px 0; }
details.n2-detalle[open] > summary { margin-bottom: 6px; }

/* ───────── tablero de lanzamiento de idioma ───────── */
.n2-semaforo { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e-3); padding: var(--e-3) var(--e-4); border: 1px solid var(--borde); border-radius: var(--r-3); background: var(--sup-2); }
.n2-semaforo__valor { font-size: var(--t-lg); font-weight: 700; font-variant-numeric: tabular-nums; }
.n2-tablero { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 168px), 1fr)); gap: var(--e-3); align-items: start; }
.n2-col { display: grid; gap: var(--e-2); align-content: start; min-width: 0; padding: var(--e-2); border: 1px solid var(--borde); border-radius: var(--r-3); background: var(--sup-2); }
.n2-col__cab { display: grid; gap: 2px; padding: 4px 6px 6px; }
.n2-col__nombre { display: flex; align-items: center; justify-content: space-between; gap: 6px; margin: 0; font-size: .8rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--txt); }
.n2-col__cuenta { font-variant-numeric: tabular-nums; color: var(--txt-3); font-weight: 650; }
.n2-col__que { margin: 0; font-size: .78rem; color: var(--txt-3); line-height: 1.35; }
.n2-tj { display: grid; gap: 6px; padding: 10px; border: 1px solid var(--borde); border-left-width: 3px; border-radius: var(--r-2); background: var(--sup); min-width: 0; }
.n2-tj--ok { border-left-color: var(--punto-ok); }
.n2-tj--aviso { border-left-color: var(--punto-aviso); }
.n2-tj--error { border-left-color: var(--punto-error); }
.n2-tj--info { border-left-color: var(--acento); }
.n2-tj--neutro { border-left-color: var(--borde-fuerte); }
.n2-tj__cab { display: flex; align-items: baseline; gap: 6px; }
.n2-tj__id { font-family: var(--mono); font-size: .74rem; font-weight: 700; color: var(--txt-3); }
.n2-tj__titulo { margin: 0; font-size: var(--t-sm); font-weight: 600; line-height: 1.3; color: var(--txt); overflow-wrap: anywhere; }
.n2-tj__duenios { display: flex; flex-wrap: wrap; gap: 4px; }
.n2-tj details { font-size: .8rem; color: var(--txt-2); }
.n2-tj summary { cursor: pointer; color: var(--acento-fuerte); font-weight: 550; }
.n2-tj details p { margin: 4px 0 0; line-height: 1.4; overflow-wrap: anywhere; }
.n2-familia { display: flex; flex-wrap: wrap; align-items: stretch; gap: var(--e-3); }
.n2-familia__caja { flex: 1 1 220px; display: grid; gap: 4px; align-content: start; padding: var(--e-3) var(--e-4); border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup-2); min-width: 0; }
.n2-familia__caja--madre { border-color: var(--acento-borde); background: var(--acento-bg); }
.n2-familia__flecha { align-self: center; color: var(--txt-3); }

/* ───────── poscompra ───────── */
.n2-embudo { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-2); container-type: inline-size; }
.n2-etapa { display: grid; grid-template-columns: minmax(140px, 220px) minmax(0, 1fr) minmax(90px, auto); gap: var(--e-3); align-items: center; padding: 10px 12px; border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup); }
.n2-etapa__nombre { display: grid; gap: 2px; min-width: 0; }
.n2-etapa__nombre strong { font-weight: 650; }
.n2-etapa__pista { position: relative; height: 14px; border-radius: 99px; background: var(--sup-3); overflow: hidden; }
.n2-etapa__relleno { position: absolute; inset: 0 auto 0 0; width: var(--p, 0%); min-width: 4px; border-radius: 99px; background: var(--serie-1); }
.n2-etapa--sin .n2-etapa__relleno, .n2-etapa--plan .n2-etapa__relleno { display: none; }
.n2-etapa--plan { border-style: dashed; }
.n2-etapa__valor { text-align: right; font-weight: 700; font-variant-numeric: tabular-nums; display: grid; gap: 2px; }
.n2-etapa__conv { font-weight: 500; font-size: .8rem; color: var(--txt-3); }
@container (max-width: 560px) { .n2-etapa { grid-template-columns: minmax(0, 1fr); gap: var(--e-2); } .n2-etapa__valor { text-align: left; } }
.n2-auto { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-3); }
.n2-auto > li { display: grid; gap: 6px; padding: var(--e-3) var(--e-4); border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup); }
.n2-auto__cab { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; justify-content: space-between; }
.n2-auto__nombre { margin: 0; font-weight: 650; font-size: var(--t-base); }
.n2-auto p { margin: 0; color: var(--txt-2); line-height: 1.45; font-size: var(--t-sm); max-width: 78ch; }
.n2-dos { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr)); gap: var(--e-3); }
.n2-caja { display: grid; gap: var(--e-2); align-content: start; padding: var(--e-3) var(--e-4); border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup-2); min-width: 0; }
.n2-caja h3 { margin: 0; font-size: var(--t-base); font-weight: 650; }
.n2-caja ul { margin: 0; padding-left: 18px; display: grid; gap: 4px; color: var(--txt-2); font-size: var(--t-sm); line-height: 1.4; }
.n2-ticket { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 240px), 1fr)); gap: var(--e-3); }
`;
