// lib/estilos-u3.js — estilos propios de Descubrimiento, Landing y Campañas (prefijo `u3-`). Solo datos (una cadena CSS): cada página los instala
// con `ui.instalarEstilos(id, css)` (hoja construida por CSSOM; la CSP del panel no admite <style> ni style="" en línea).
// Solo usa los tokens del sistema (--sup, --borde, --txt…, con valores de respaldo); el color significa estado y el acento marca lo interactivo.

export const CSS_COMUN = `
.u3-pila { display: grid; gap: 16px; grid-template-columns: minmax(0, 1fr); min-width: 0; }
.u3-pila--chica { gap: 8px; }
.u3-fila { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; min-width: 0; }
.u3-fila--entre { justify-content: space-between; }
.u3-tenue { color: var(--txt-3); }
.u3-peq { font-size: .86rem; }
.u3-tarjeta { background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3, 12px); padding: 16px 20px; box-shadow: var(--sombra); min-width: 0; }
.u3-tarjeta--hundida { background: var(--sup-2); box-shadow: none; }
.u3-titulo { font-size: 1.14rem; font-weight: 650; line-height: 1.3; margin: 0; }
.u3-titulo--chico { font-size: 1rem; }
.u3-sobretitulo { font-size: .74rem; font-weight: 650; letter-spacing: .06em; text-transform: uppercase; color: var(--txt-3); margin: 0; }
.u3-parrafo { margin: 0; color: var(--txt-2); line-height: 1.5; max-width: 78ch; }
.u3-parrafo strong { color: var(--txt); font-weight: 650; }

/* etiquetas */
.u3-tag { display: inline-flex; align-items: center; gap: 4px; max-width: 100%; padding: 1px 8px; border-radius: 99px; border: 1px solid var(--borde); background: var(--sup-2); color: var(--txt-2); font-size: .8rem; line-height: 1.5; white-space: nowrap; }
.u3-tag--ok { background: var(--ok-bg); border-color: var(--ok-borde); color: var(--ok); }
.u3-tag--aviso { background: var(--aviso-bg); border-color: var(--aviso-borde); color: var(--aviso); }
.u3-tag--error { background: var(--error-bg); border-color: var(--error-borde); color: var(--error); }
.u3-tag--info { background: var(--info-bg); border-color: var(--info-borde); color: var(--info); }
.u3-tag--acento { background: var(--acento-bg); border-color: transparent; color: var(--acento-fuerte); }
.u3-tag--hipotesis { background: transparent; border-style: dashed; color: var(--txt-3); }
.u3-tag--mono { font-family: var(--mono); font-size: .76rem; letter-spacing: .02em; }
.u3-tags { display: flex; flex-wrap: wrap; gap: 6px; min-width: 0; }

/* estado con icono + etiqueta (nunca solo color) */
.u3-estado { display: inline-flex; align-items: center; gap: 6px; font-size: .86rem; font-weight: 600; line-height: 1.3; }
.u3-estado .icono { flex: none; }
.u3-estado--ok { color: var(--ok); }
.u3-estado--aviso { color: var(--aviso); }
.u3-estado--error { color: var(--error); }
.u3-estado--info { color: var(--info); }
.u3-estado--neutro { color: var(--txt-3); }

/* barra de progreso hacia un umbral */
.u3-barra { display: grid; gap: 4px; min-width: 0; }
.u3-barra__cab { display: flex; align-items: baseline; justify-content: space-between; gap: 8px; font-size: .8rem; color: var(--txt-3); }
.u3-barra__valor { color: var(--txt); font-weight: 650; font-variant-numeric: tabular-nums; font-size: .92rem; display: inline-flex; align-items: center; gap: 4px; }
.u3-barra--supera .u3-barra__valor .icono { color: var(--ok); }
.u3-barra__pista { position: relative; height: 6px; border-radius: 99px; background: var(--sup-3); overflow: hidden; }
.u3-barra__relleno { position: absolute; inset: 0 auto 0 0; width: var(--p, 0%); border-radius: 99px; background: var(--acento); }
.u3-barra--supera .u3-barra__relleno { background: var(--punto-ok, #1f9d55); }
.u3-barra--sin .u3-barra__relleno { width: 0; }
.u3-barra__umbral { font-size: .8rem; font-weight: 400; color: var(--txt-3); }

/* nota (aviso breve con icono) */
.u3-nota { display: flex; gap: 10px; align-items: flex-start; padding: 10px 14px; border-radius: var(--r-2, 8px); border: 1px solid var(--info-borde); background: var(--info-bg); color: var(--txt); font-size: .93rem; line-height: 1.5; }
.u3-nota .icono { flex: none; margin-top: 2px; color: var(--info); }
.u3-nota--aviso { border-color: var(--aviso-borde); background: var(--aviso-bg); }
.u3-nota--aviso .icono { color: var(--aviso); }
.u3-nota--error { border-color: var(--error-borde); background: var(--error-bg); }
.u3-nota--error .icono { color: var(--error); }
.u3-nota--ok { border-color: var(--ok-borde); background: var(--ok-bg); }
.u3-nota--ok .icono { color: var(--ok); }
.u3-nota--neutra { border-color: var(--borde); background: var(--sup-2); }
.u3-nota--neutra .icono { color: var(--txt-3); }
.u3-nota > div { min-width: 0; }
.u3-nota p { margin: 0; }
.u3-nota p + p { margin-top: 4px; }

.u3-bloqueos { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.u3-bloqueos li { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 8px; color: var(--txt-2); line-height: 1.45; }
.u3-bloqueos .icono { margin-top: 2px; color: var(--aviso); }

.u3-grupos { display: grid; gap: 24px; }

/* rejillas de métricas */
.u3-metricas { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(min(100%, 150px), 1fr)); }
.u3-cifras { display: flex; flex-wrap: wrap; gap: 4px 24px; font-size: .88rem; color: var(--txt-3); }
.u3-cifras b { color: var(--txt); font-variant-numeric: tabular-nums; font-weight: 650; }
.u3-dos { display: grid; gap: 16px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
@media (max-width: 900px) { .u3-dos { grid-template-columns: minmax(0, 1fr); } }

/* chips de selección (vistas guardadas) */
.u3-vista { appearance: none; display: inline-flex; align-items: center; gap: 6px; border: 1px solid var(--borde); background: var(--sup); color: var(--txt-2); border-radius: 99px; padding: 3px 12px; font-size: .86rem; cursor: pointer; min-height: 30px; }
.u3-vista:hover { border-color: var(--borde-fuerte); color: var(--txt); }
.u3-vista[aria-pressed="true"] { background: var(--acento-bg); border-color: transparent; color: var(--acento-fuerte); font-weight: 650; }
.u3-vista__quitar { appearance: none; border: 0; background: transparent; color: inherit; padding: 0 0 0 2px; cursor: pointer; display: inline-grid; place-items: center; opacity: .7; }
.u3-vista__quitar:hover { opacity: 1; }

/* controles */
.u3-campo { display: grid; gap: 4px; font-size: .78rem; color: var(--txt-3); min-width: 0; }
.u3-campo select, .u3-campo input[type="search"], .u3-campo input[type="text"] { min-height: 32px; border: 1px solid var(--borde-fuerte); border-radius: var(--r-2, 8px); background: var(--sup); color: var(--txt); padding: 0 10px; font: inherit; font-size: .92rem; min-width: 0; width: 100%; }
.u3-filtros { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(170px, 1fr)); align-items: end; }
.u3-detalles > summary { cursor: pointer; color: var(--txt-2); font-size: .9rem; padding: 4px 0; }
.u3-detalles > summary:hover { color: var(--txt); }
.u3-interruptor { display: inline-flex; align-items: center; gap: 8px; font-size: .9rem; color: var(--txt-2); min-height: 32px; }

/* lista con estado por fila */
.u3-lista { display: grid; gap: 0; border: 1px solid var(--borde); border-radius: var(--r-3, 12px); background: var(--sup); overflow: hidden; }
.u3-lista > * + * { border-top: 1px solid var(--borde); }
.u3-item { display: grid; grid-template-columns: 22px minmax(0, 1fr) auto; gap: 4px 12px; align-items: start; padding: 10px 16px; }
.u3-item__icono { padding-top: 2px; }
.u3-item__titulo { font-weight: 600; line-height: 1.35; }
.u3-item__detalle { color: var(--txt-3); font-size: .88rem; line-height: 1.45; grid-column: 2 / 3; overflow-wrap: anywhere; }
.u3-item__lado { grid-column: 3; grid-row: 1; display: flex; gap: 6px; align-items: center; flex-wrap: wrap; justify-content: flex-end; }
@media (max-width: 640px) {
  .u3-item { grid-template-columns: 22px minmax(0, 1fr); }
  .u3-item__lado { grid-column: 2; grid-row: auto; justify-content: flex-start; }
}
.u3-grupo__cab { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; flex-wrap: wrap; margin-bottom: 8px; }

/* tabla comparativa y de datos */
.u3-tabla-envuelta { overflow-x: auto; border: 1px solid var(--borde); border-radius: var(--r-3, 12px); background: var(--sup); }
.u3-tabla { width: 100%; border-collapse: separate; border-spacing: 0; font-size: .92rem; }
.u3-tabla th, .u3-tabla td { padding: 10px 14px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--borde); }
.u3-tabla thead th { position: sticky; top: 0; background: var(--sup-2); color: var(--txt-3); font-size: .76rem; font-weight: 650; letter-spacing: .04em; text-transform: uppercase; white-space: nowrap; }
.u3-tabla tbody tr:last-child th, .u3-tabla tbody tr:last-child td { border-bottom: 0; }
.u3-tabla tbody th { font-weight: 600; color: var(--txt); }
.u3-tabla .u3-num { text-align: right; font-variant-numeric: tabular-nums; }
.u3-tabla td.u3-dif { background: var(--error-bg); color: var(--txt); }
.u3-tabla td.u3-igual { color: var(--txt-2); }
.u3-tabla td.u3-sin { color: var(--txt-3); font-style: italic; }
.u3-nota-celda { display: block; color: var(--txt-3); font-size: .8rem; font-weight: 400; margin-top: 2px; line-height: 1.35; }
`;

// ─────────────────────────────── Descubrimiento ───────────────────────────────

export const CSS_DESCUBRIMIENTO = `
.u3-resumen { display: grid; gap: 16px; }
.u3-resumen__titular { font-size: 1.5rem; font-weight: 700; line-height: 1.2; margin: 0; letter-spacing: -.01em; }
.u3-resumen__lineas { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.u3-resumen__lineas li { display: grid; grid-template-columns: 18px minmax(0, 1fr); gap: 8px; color: var(--txt-2); line-height: 1.5; }
.u3-resumen__lineas .icono { margin-top: 3px; color: var(--txt-3); }
.u3-estado-barrido { display: grid; gap: 16px; grid-template-columns: minmax(0, 2fr) minmax(0, 1fr); align-items: start; }
@media (max-width: 1000px) { .u3-estado-barrido { grid-template-columns: minmax(0, 1fr); } }
.u3-freno { display: grid; gap: 8px; }
.u3-freno__estado { display: flex; align-items: center; gap: 10px; font-weight: 650; font-size: 1.05rem; }
.u3-freno__estado .icono { flex: none; }
.u3-freno--ok .u3-freno__estado { color: var(--ok); }
.u3-freno--error .u3-freno__estado { color: var(--error); }
.u3-freno--neutro .u3-freno__estado { color: var(--txt-3); }

/* candidatos: filas ricas */
.u3-cands { display: grid; gap: 8px; }
.u3-cand { display: grid; grid-template-columns: 40px minmax(0, 1.5fr) minmax(0, 1.25fr) minmax(0, 1.25fr); gap: 8px 20px; align-items: start; padding: 14px 16px; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3, 12px); cursor: pointer; transition: border-color .14s ease, box-shadow .14s ease; min-width: 0; }
.u3-cand:hover { border-color: var(--borde-fuerte); box-shadow: var(--sombra); }
.u3-cand:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }
.u3-cand[aria-selected="true"] { border-color: var(--acento); box-shadow: 0 0 0 1px var(--acento) inset; }
.u3-cand--pasa { border-left: 3px solid var(--punto-ok, #1f9d55); }
.u3-cand__rank { font-variant-numeric: tabular-nums; color: var(--txt-3); font-size: .86rem; font-weight: 650; padding-top: 2px; }
.u3-cand__tema { margin: 0; font-size: 1.02rem; font-weight: 650; line-height: 1.3; overflow-wrap: anywhere; }
.u3-cand__sub { color: var(--txt-3); font-size: .86rem; line-height: 1.4; margin-top: 2px; overflow-wrap: anywhere; }
.u3-cand__principal { display: grid; gap: 8px; min-width: 0; }
.u3-cand__nums { display: grid; gap: 8px; min-width: 0; }
.u3-cand__indep { display: flex; align-items: baseline; gap: 8px; }
.u3-cand__indep b { font-size: 1.35rem; font-weight: 700; font-variant-numeric: tabular-nums; line-height: 1; }
.u3-cand__indep span { color: var(--txt-3); font-size: .82rem; }
.u3-cand__estado { display: grid; gap: 6px; min-width: 0; align-content: start; }
.u3-cand__explicacion { color: var(--txt-2); font-size: .88rem; line-height: 1.45; margin: 0; }
@media (max-width: 1180px) {
  .u3-cand { grid-template-columns: 34px minmax(0, 1fr) minmax(0, 1fr); }
  .u3-cand__estado { grid-column: 2 / 4; }
}
@media (max-width: 700px) {
  .u3-cand { grid-template-columns: minmax(0, 1fr); gap: 10px; }
  .u3-cand__estado { grid-column: auto; }
  .u3-cand__rank { display: none; }
}
.u3-mas { display: flex; justify-content: center; padding-top: 4px; }

/* panel lateral */
.u3-panel-fondo { position: fixed; inset: 0; background: rgba(8, 12, 20, .32); z-index: 80; }
.u3-panel { position: fixed; top: 0; right: 0; bottom: 0; width: min(620px, 100vw); background: var(--sup); border-left: 1px solid var(--borde); box-shadow: -18px 0 48px rgba(8, 12, 20, .22); z-index: 81; display: grid; grid-template-rows: auto minmax(0, 1fr); }
.u3-panel__cab { display: flex; gap: 12px; align-items: flex-start; padding: 16px 20px; border-bottom: 1px solid var(--borde); background: var(--sup); }
.u3-panel__titulos { min-width: 0; flex: 1; display: grid; gap: 4px; }
.u3-atras { justify-self: start; }
.u3-atras .icono { transform: rotate(180deg); }
.u3-panel__titulos h2 { margin: 0; font-size: 1.18rem; font-weight: 700; line-height: 1.3; overflow-wrap: anywhere; }
.u3-panel__cuerpo { overflow-y: auto; padding: 16px 20px 32px; display: grid; gap: 20px; align-content: start; min-width: 0; }
.u3-panel__cuerpo > * { min-width: 0; }
.u3-panel__secc { display: grid; gap: 10px; min-width: 0; }
.u3-panel__secc > h3 { margin: 0; font-size: .74rem; font-weight: 650; letter-spacing: .06em; text-transform: uppercase; color: var(--txt-3); }
.u3-panel__nums { display: grid; gap: 14px; grid-template-columns: repeat(3, minmax(0, 1fr)); }
@media (max-width: 520px) { .u3-panel__nums { gap: 8px; } .u3-numero b { font-size: 1.3rem; } .u3-numero span { font-size: .76rem; line-height: 1.3; } }
.u3-numero { display: grid; gap: 2px; }
.u3-numero b { font-size: 1.6rem; font-weight: 700; line-height: 1.1; font-variant-numeric: tabular-nums; }
.u3-numero span { color: var(--txt-3); font-size: .82rem; }
.u3-pag { display: grid; gap: 4px 12px; grid-template-columns: minmax(0, 1fr) auto; padding: 10px 12px; border: 1px solid var(--borde); border-radius: var(--r-2, 8px); background: var(--sup); cursor: pointer; text-align: left; font: inherit; color: inherit; width: 100%; }
.u3-pag:hover { border-color: var(--borde-fuerte); background: var(--sup-2); }
.u3-pag__nombre { font-weight: 600; overflow-wrap: anywhere; }
.u3-pag__meta { color: var(--txt-3); font-size: .84rem; grid-column: 1 / -1; }
.u3-titulos { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none; }
.u3-titulos li { padding: 8px 12px; border-left: 3px solid var(--borde-fuerte); background: var(--sup-2); border-radius: 0 var(--r-2, 8px) var(--r-2, 8px) 0; font-size: .92rem; line-height: 1.4; overflow-wrap: anywhere; }

/* matriz tema × país (mapa de calor) */
.u3-calor-envuelto { overflow: auto; max-height: 640px; border: 1px solid var(--borde); border-radius: var(--r-3, 12px); background: var(--sup); }
.u3-calor { border-collapse: separate; border-spacing: 2px; width: 100%; font-size: .88rem; }
.u3-calor thead th { position: sticky; top: 0; z-index: 2; background: var(--sup); padding: 8px 6px; text-align: center; font-weight: 650; color: var(--txt); }
.u3-calor thead th small { display: block; font-weight: 400; color: var(--txt-3); font-size: .72rem; font-variant-numeric: tabular-nums; }
.u3-calor thead th:first-child { text-align: left; left: 0; z-index: 3; min-width: 220px; }
.u3-calor tbody th { position: sticky; left: 0; z-index: 1; background: var(--sup); text-align: left; font-weight: 500; padding: 6px 10px; min-width: 220px; max-width: 320px; }
.u3-calor tbody tr { cursor: pointer; }
.u3-calor tbody tr:hover th { background: var(--sup-2); }
.u3-calor__tema { display: flex; gap: 8px; align-items: center; }
.u3-calor__tema span.u3-calor__nombre { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.u3-calor td { text-align: center; min-width: 52px; height: 34px; border-radius: 6px; font-variant-numeric: tabular-nums; font-weight: 650; }
.u3-calor td.n1 { background: color-mix(in srgb, var(--acento) 14%, var(--sup)); color: var(--txt); }
.u3-calor td.n2 { background: color-mix(in srgb, var(--acento) 28%, var(--sup)); color: var(--txt); }
.u3-calor td.n3 { background: color-mix(in srgb, var(--acento) 44%, var(--sup)); color: var(--txt); }
.u3-calor td.n4 { background: color-mix(in srgb, var(--acento) 76%, var(--sup)); color: var(--sobre-acento); }
.u3-calor td.n0 { background: transparent; border: 1px dashed var(--borde); color: var(--txt-3); font-weight: 400; }
@media (max-width: 700px) {
  .u3-calor thead th:first-child, .u3-calor tbody th { min-width: 140px; max-width: 150px; }
  .u3-calor td { min-width: 44px; }
}
.u3-leyenda { display: flex; flex-wrap: wrap; gap: 6px 14px; align-items: center; font-size: .82rem; color: var(--txt-3); }
.u3-leyenda i { display: inline-block; width: 22px; height: 14px; border-radius: 4px; vertical-align: -2px; margin-right: 4px; }
.u3-leyenda i.n0 { border: 1px dashed var(--borde-fuerte); }
.u3-leyenda i.n1 { background: color-mix(in srgb, var(--acento) 14%, var(--sup)); }
.u3-leyenda i.n2 { background: color-mix(in srgb, var(--acento) 28%, var(--sup)); }
.u3-leyenda i.n3 { background: color-mix(in srgb, var(--acento) 44%, var(--sup)); }
.u3-leyenda i.n4 { background: color-mix(in srgb, var(--acento) 76%, var(--sup)); }

/* fichas */
.u3-fichas { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); }
.u3-ficha { display: grid; gap: 10px; align-content: start; padding: 16px; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3, 12px); cursor: pointer; text-align: left; font: inherit; color: inherit; min-width: 0; }
.u3-ficha:hover { border-color: var(--borde-fuerte); box-shadow: var(--sombra); }
.u3-ficha h3 { margin: 0; font-size: 1.02rem; font-weight: 650; line-height: 1.3; overflow-wrap: anywhere; }

/* cobertura por pasada */
.u3-pasadas { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); }
.u3-pasada { display: grid; gap: 8px; padding: 14px 16px; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3, 12px); align-content: start; }
.u3-pasada h3 { margin: 0; font-size: .98rem; font-weight: 650; }
.u3-pasada__cifras { display: flex; gap: 4px 16px; flex-wrap: wrap; font-size: .86rem; color: var(--txt-3); }
.u3-pasada__cifras b { color: var(--txt); font-variant-numeric: tabular-nums; }
`;

// ─────────────────────────────── Landing ───────────────────────────────

export const CSS_LANDING = `
.u3-vista-layout { display: grid; gap: 20px; grid-template-columns: minmax(0, 1fr) minmax(0, 340px); align-items: start; }
@media (max-width: 1100px) { .u3-vista-layout { grid-template-columns: minmax(0, 1fr); } }
.u3-escenario { background: var(--sup-2); border: 1px solid var(--borde); border-radius: var(--r-3, 12px); padding: 24px 16px; display: grid; justify-items: center; overflow: hidden; }
.u3-dispositivo { position: relative; background: #11161d; padding: 12px; border-radius: 28px; box-shadow: 0 10px 30px rgba(8, 12, 20, .28), 0 0 0 1px rgba(255, 255, 255, .06) inset; max-width: 100%; transition: width .18s ease; }
.u3-dispositivo--movil { width: 414px; border-radius: 38px; padding: 12px 10px 14px; }
.u3-dispositivo--movil::before { content: ""; display: block; width: 84px; height: 6px; border-radius: 99px; background: #2b333f; margin: 0 auto 8px; }
.u3-dispositivo--tablet { width: 792px; border-radius: 26px; padding: 14px; }
.u3-dispositivo--escritorio { width: 100%; padding: 0; border-radius: 10px; background: var(--sup); box-shadow: 0 8px 24px rgba(8, 12, 20, .2); border: 1px solid var(--borde-fuerte); overflow: hidden; }
.u3-dispositivo__barra { display: none; align-items: center; gap: 6px; padding: 8px 12px; background: var(--sup-3); border-bottom: 1px solid var(--borde); }
.u3-dispositivo--escritorio .u3-dispositivo__barra { display: flex; }
.u3-dispositivo__barra i { width: 10px; height: 10px; border-radius: 50%; background: var(--borde-fuerte); display: inline-block; }
.u3-dispositivo__barra span { margin-left: 10px; flex: 1; background: var(--sup); border: 1px solid var(--borde); border-radius: 99px; padding: 2px 12px; font-size: .78rem; color: var(--txt-3); text-align: center; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.u3-dispositivo iframe { display: block; width: 100%; border: 0; background: #ffffff; border-radius: 12px; }
.u3-dispositivo--escritorio iframe { border-radius: 0; }
.u3-dispositivo--movil iframe { border-radius: 24px; }
.u3-dispositivo--tablet iframe { border-radius: 14px; }
.u3-lado { display: grid; gap: 12px; align-content: start; min-width: 0; }

/* comprobaciones C01–C17 */
.u3-check { display: grid; grid-template-columns: 24px 54px minmax(0, 1fr) auto; gap: 4px 12px; align-items: start; padding: 12px 16px; }
.u3-check__id { font-family: var(--mono); font-size: .8rem; color: var(--txt-3); padding-top: 2px; }
.u3-check__nombre { font-weight: 600; line-height: 1.35; }
.u3-check__texto { grid-column: 3; color: var(--txt-3); font-size: .86rem; line-height: 1.45; }
.u3-check__detalle { grid-column: 3; font-size: .86rem; line-height: 1.45; color: var(--txt-2); overflow-wrap: anywhere; }
.u3-check__lado { grid-column: 4; grid-row: 1; display: flex; gap: 8px; align-items: center; justify-content: flex-end; flex-wrap: wrap; }
@media (max-width: 700px) {
  .u3-check { grid-template-columns: 24px minmax(0, 1fr); }
  .u3-check__id { display: none; }
  .u3-check__texto, .u3-check__detalle { grid-column: 2; }
  .u3-check__lado { grid-column: 2; grid-row: auto; justify-content: flex-start; }
}
.u3-check--error { background: color-mix(in srgb, var(--error-bg) 55%, var(--sup)); }
.u3-check--aviso { background: color-mix(in srgb, var(--aviso-bg) 55%, var(--sup)); }
.u3-resumen-checks { display: flex; flex-wrap: wrap; gap: 8px 20px; }
.u3-legales { display: grid; gap: 10px; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); }
.u3-legal { display: grid; gap: 4px; padding: 12px 14px; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-2, 8px); }
.u3-legal b { font-weight: 650; }
.u3-ranuras { display: grid; gap: 8px; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); }
.u3-ranura { display: grid; gap: 4px; padding: 10px 12px; background: var(--sup); border: 1px dashed var(--aviso-borde); border-radius: var(--r-2, 8px); }
.u3-ranura b { font-weight: 600; line-height: 1.3; }
`;

// ─────────────────────────────── Campañas ───────────────────────────────

export const CSS_CAMPANAS = `
.u3-siguiente { display: grid; gap: 12px; }
.u3-siguiente__texto { font-size: 1.08rem; font-weight: 600; line-height: 1.4; margin: 0; }

/* preflight: cuadrícula de semáforos por grupo */
.u3-semaforos { display: grid; gap: 8px; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
.u3-sema { display: grid; grid-template-columns: 22px minmax(0, 1fr); gap: 2px 10px; align-items: start; padding: 10px 12px; border: 1px solid var(--borde); border-radius: var(--r-2, 8px); background: var(--sup); min-width: 0; }
.u3-sema__icono { grid-row: 1 / 3; padding-top: 1px; }
.u3-sema__id { font-family: var(--mono); font-size: .76rem; color: var(--txt-3); margin-right: 6px; }
.u3-sema__titulo { font-size: .9rem; line-height: 1.35; overflow-wrap: anywhere; }
.u3-sema__evidencia { grid-column: 2; font-size: .8rem; color: var(--txt-3); line-height: 1.4; overflow-wrap: anywhere; }
.u3-sema--VERDE { border-color: var(--ok-borde); background: color-mix(in srgb, var(--ok-bg) 45%, var(--sup)); }
.u3-sema--VERDE .u3-sema__icono { color: var(--ok); }
.u3-sema--AMARILLO { border-color: var(--aviso-borde); background: var(--aviso-bg); }
.u3-sema--AMARILLO .u3-sema__icono { color: var(--aviso); }
.u3-sema--ROJO { border-color: var(--error-borde); background: var(--error-bg); }
.u3-sema--ROJO .u3-sema__icono { color: var(--error); }
.u3-sema--NO_APLICA, .u3-sema--sin_dato { background: var(--sup-2); border-style: dashed; }
.u3-sema--NO_APLICA .u3-sema__icono, .u3-sema--sin_dato .u3-sema__icono { color: var(--txt-3); }

/* detalle de campaña legible */
.u3-url { padding: 12px 14px; background: var(--sup-2); border: 1px solid var(--borde); border-radius: var(--r-2, 8px); font-family: var(--mono); font-size: .88rem; line-height: 1.7; overflow-wrap: anywhere; word-break: break-all; }
.u3-url mark { background: var(--acento-bg); color: var(--acento-fuerte); border-radius: 4px; padding: 1px 5px; font-weight: 600; }
.u3-presupuesto { display: grid; gap: 12px; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
.u3-anuncios { display: grid; gap: 8px; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); }
.u3-anuncio { display: grid; gap: 6px; padding: 12px 14px; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-2, 8px); min-width: 0; }
.u3-anuncio b { overflow-wrap: anywhere; font-weight: 600; }
.u3-regla { display: grid; grid-template-columns: 20px minmax(0, 1fr); gap: 8px; align-items: start; padding: 8px 0; }
.u3-regla + .u3-regla { border-top: 1px solid var(--borde); }
.u3-regla .icono { color: var(--aviso); margin-top: 2px; }
.u3-firma { display: grid; gap: 12px; }
`;
