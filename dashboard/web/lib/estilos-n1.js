// lib/estilos-n1.js — estilos propios de «La rueda» (Resumen), Robots, Avisos y Pagos (prefijo `n1-`). Solo datos (cadenas CSS): cada página los instala con
// `ui.instalarEstilos(id, css)` (hoja construida por CSSOM; la CSP del panel no admite <style> ni style="" en línea).
// Solo usa los tokens del sistema (--sup, --borde, --txt, --ok-bg…, con valores de respaldo): el color significa estado y el acento marca lo interactivo.
// Todo estado lleva además icono y texto: el color nunca va solo.

export const CSS_COMUN = `
.n1-pila { display: grid; gap: var(--e-4, 16px); grid-template-columns: minmax(0, 1fr); min-width: 0; }
.n1-pila--chica { gap: var(--e-2, 8px); }
.n1-fila { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e-2, 8px); min-width: 0; }
.n1-fila--nowrap { flex-wrap: nowrap; align-items: flex-start; }
.n1-fila--nowrap .icono { flex: none; margin-top: 3px; }
.n1-cadencia { flex: 1 1 0; min-width: 0; }
.n1-fila--entre { justify-content: space-between; }
.n1-tenue { color: var(--txt-3); }
.n1-nota { margin: 0; color: var(--txt-2); font-size: var(--t-sm, .93rem); line-height: 1.5; max-width: 80ch; overflow-wrap: anywhere; }
.n1-nota strong { color: var(--txt); font-weight: 650; }
.n1-subtitulo { margin: 0; font-size: 1rem; font-weight: 650; line-height: 1.3; color: var(--txt); }
.n1-sobretitulo { margin: 0; font-size: .74rem; font-weight: 650; letter-spacing: .06em; text-transform: uppercase; color: var(--txt-3); }
.n1-mono { font-family: var(--mono); font-size: .86em; overflow-wrap: anywhere; }
.n1-tarjeta { background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3, 12px); padding: var(--e-4, 16px); box-shadow: var(--sombra); min-width: 0; }
.n1-tarjeta--hundida { background: var(--sup-2); box-shadow: none; }
.n1-cab { grid-template-columns: minmax(0, 1fr); }
.n1-cab .cab__pestanas { min-width: 0; max-width: 100%; }
.n1-metricas { display: grid; gap: var(--e-3, 12px); grid-template-columns: repeat(auto-fit, minmax(min(100%, 210px), 1fr)); }
.n1-aviso { display: flex; gap: var(--e-2, 8px); align-items: flex-start; padding: var(--e-3, 12px); border: 1px solid var(--aviso-borde); background: var(--aviso-bg); color: var(--aviso); border-radius: var(--r-2, 8px); font-size: var(--t-sm, .93rem); line-height: 1.45; }
.n1-aviso .icono { flex: none; margin-top: 2px; }
.n1-aviso--info { border-color: var(--info-borde); background: var(--info-bg); color: var(--info); }
.n1-aviso--neutro { border-color: var(--borde); background: var(--sup-2); color: var(--txt-2); }
.n1-kv { display: grid; grid-template-columns: minmax(110px, max-content) minmax(0, 1fr); gap: 4px var(--e-3, 12px); margin: 0; font-size: var(--t-sm, .93rem); }
.n1-kv dt { color: var(--txt-3); }
.n1-kv dd { margin: 0; color: var(--txt); overflow-wrap: anywhere; }
.n1-lista { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-2, 8px); }
.n1-lista > li { min-width: 0; }
@media (max-width: 520px) { .n1-kv { grid-template-columns: minmax(0, 1fr); gap: 0; } .n1-kv dd { margin-bottom: 8px; } }
`;

// ───────────────────────── Resumen: «La rueda» ─────────────────────────

export const CSS_RUEDA = `
.n1-rueda-cab { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--e-3, 12px); margin-bottom: var(--e-3, 12px); }
.n1-rueda-cuenta { display: flex; flex-wrap: wrap; gap: 6px 14px; font-size: var(--t-sm, .93rem); color: var(--txt-2); }
.n1-rueda-cuenta b { color: var(--txt); font-weight: 650; font-variant-numeric: tabular-nums; }
.n1-tira { display: flex; gap: 4px; list-style: none; margin: 0; padding: 0; }
.n1-tira li { width: 22px; height: 22px; display: grid; place-items: center; border-radius: 50%; font-size: 11px; font-weight: 700; border: 1px solid var(--borde-fuerte); color: var(--txt-3); background: transparent; font-variant-numeric: tabular-nums; }
.n1-tira li[data-estado="ok"] { background: var(--ok-bg); border-color: var(--ok-borde); color: var(--ok); }
.n1-tira li[data-estado="aviso"] { background: var(--aviso-bg); border-color: var(--aviso-borde); color: var(--aviso); }
.n1-tira li[data-estado="sin_datos"] { border-style: dashed; }
.n1-rueda { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-3, 12px); grid-template-columns: repeat(auto-fit, minmax(min(100%, 270px), 1fr)); }
@media (min-width: 980px) { .n1-rueda { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
.n1-rueda > li { display: flex; min-width: 0; }
.n1-paso { position: relative; flex: 1; display: flex; flex-direction: column; gap: 8px; padding: 14px 16px; background: var(--sup); border: 1px solid var(--borde); border-left-width: 4px; border-radius: var(--r-3, 12px);
  color: var(--txt); text-decoration: none; box-shadow: var(--sombra); min-width: 0; transition: border-color .14s ease, box-shadow .14s ease; }
.n1-paso:hover { border-color: var(--borde-fuerte); box-shadow: var(--sombra-2); }
.n1-paso:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }
.n1-paso[data-estado="ok"] { border-left-color: var(--punto-ok); }
.n1-paso[data-estado="aviso"] { border-left-color: var(--punto-aviso); }
.n1-paso[data-estado="sin_datos"] { border-left-style: dashed; border-left-color: var(--borde-fuerte); }
.n1-paso__cab { display: flex; align-items: center; gap: 10px; }
.n1-paso__n { flex: none; width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; font-weight: 700; font-size: 13px; background: var(--acento-bg); color: var(--acento-fuerte); font-variant-numeric: tabular-nums; }
.n1-paso__titulo { margin: 0; font-size: 15px; font-weight: 650; line-height: 1.3; min-width: 0; overflow-wrap: anywhere; }
.n1-paso__estado { display: flex; }
.n1-paso__dato { margin: 0; font-size: 14px; line-height: 1.45; color: var(--txt); overflow-wrap: anywhere; }
.n1-paso__nota { margin: 0; font-size: 12.5px; line-height: 1.45; color: var(--txt-2); overflow-wrap: anywhere; }
.n1-paso__ir { margin-top: auto; padding-top: 4px; display: inline-flex; align-items: center; gap: 4px; font-size: 12.5px; color: var(--acento); }
.n1-paso:hover .n1-paso__ir { text-decoration: underline; }
.n1-rueda-vuelta { display: flex; align-items: center; gap: 8px; margin: var(--e-3, 12px) 0 0; color: var(--txt-3); font-size: var(--t-sm, .93rem); }
`;

// ───────────────────────── Robots ─────────────────────────

export const CSS_ROBOTS = `
.n1-rb { list-style: none; margin: 0; padding: 0; display: grid; gap: 0; border: 1px solid var(--borde); border-radius: var(--r-3, 12px); background: var(--sup); overflow: hidden; box-shadow: var(--sombra); }
.n1-rb__fila { display: grid; grid-template-columns: 34px minmax(0, 1.15fr) minmax(0, 1.7fr) 150px 176px; gap: var(--e-3, 12px) var(--e-4, 16px); align-items: start; padding: 14px 16px; border-top: 1px solid var(--borde); }
.n1-rb__fila:first-child { border-top: 0; }
.n1-rb__fila--cab { padding-block: 8px; background: var(--sup-2); font-size: .78rem; font-weight: 650; letter-spacing: .04em; text-transform: uppercase; color: var(--txt-3); align-items: center; }
.n1-rb__n { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; font-weight: 700; font-size: 13px; background: var(--acento-bg); color: var(--acento-fuerte); font-variant-numeric: tabular-nums; }
.n1-rb__nombre { margin: 0; font-size: 15px; font-weight: 650; line-height: 1.3; }
.n1-rb__pieza { margin: 2px 0 0; font-size: 12.5px; color: var(--txt-3); }
.n1-rb__hace { margin: 0; font-size: 14px; line-height: 1.45; color: var(--txt); }
.n1-rb__mas { margin: 4px 0 0; font-size: 12.5px; line-height: 1.45; color: var(--txt-2); }
.n1-rb__cuando { display: flex; align-items: flex-start; gap: 6px; font-size: 14px; line-height: 1.4; font-variant-numeric: tabular-nums; }
.n1-rb__cuando .icono { flex: none; margin-top: 2px; color: var(--txt-3); }
.n1-rb__estado { display: flex; flex-direction: column; gap: 6px; align-items: flex-start; min-width: 0; }
.n1-rb__estado small { font-size: 12.5px; line-height: 1.4; color: var(--txt-2); overflow-wrap: anywhere; }
.n1-rb__tec { grid-column: 2 / -1; min-width: 0; }
@media (max-width: 1180px) {
  .n1-rb__fila { grid-template-columns: 34px minmax(0, 1fr); }
  .n1-rb__fila--cab { display: none; }
  .n1-rb__fila > :nth-child(n+3) { grid-column: 2; }
  .n1-rb__tec { grid-column: 2; }
}
.n1-existente { display: grid; gap: var(--e-3, 12px); grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); }
.n1-existente > div { display: flex; flex-direction: column; gap: 6px; padding: 12px 14px; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-2, 8px); min-width: 0; }
.n1-existente b { font-weight: 650; }

/* línea de tiempo de 24 horas */
.n1-reloj { background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3, 12px); padding: var(--e-4, 16px); box-shadow: var(--sombra); display: grid; gap: 6px; min-width: 0; }
.n1-reloj__fila { display: grid; grid-template-columns: 170px minmax(0, 1fr); gap: var(--e-3, 12px); align-items: center; min-width: 0; }
.n1-reloj__nombre { font-size: 13px; line-height: 1.25; color: var(--txt); display: flex; flex-direction: column; min-width: 0; }
.n1-reloj__nombre b { font-weight: 600; overflow-wrap: anywhere; }
.n1-reloj__nombre i { font-style: normal; font-weight: 700; color: var(--txt-3); font-variant-numeric: tabular-nums; margin-right: 4px; }
.n1-reloj__nombre small { font-size: 11.5px; color: var(--txt-3); font-variant-numeric: tabular-nums; }
.n1-reloj__nombre--ctx b { color: var(--txt-3); font-style: italic; }
.n1-leyenda { display: flex; flex-wrap: wrap; gap: 6px 18px; margin: 8px 0 0; padding: 0; list-style: none; font-size: 12.5px; color: var(--txt-2); }
.n1-leyenda li { display: flex; align-items: center; gap: 6px; }
.n1-leyenda i { display: inline-block; width: 18px; height: 10px; border-radius: 3px; flex: none; }
.n1-leyenda .l-marca { width: 8px; background: var(--acento); }
.n1-leyenda .l-inferida { width: 8px; border: 2px solid var(--acento); background: transparent; }
.n1-leyenda .l-banda { background: var(--acento-bg); border: 1px solid var(--acento-borde); }
.n1-leyenda .l-ctx { background: var(--neutro-bg); border: 1px dashed var(--neutro-borde); }
.n1-leyenda .l-continuo { background: repeating-linear-gradient(to right, var(--acento-borde) 0, var(--acento-borde) 2px, transparent 2px, transparent 5px); border: 1px solid var(--acento-borde); }
.n1-leyenda .l-siempre { background: var(--ok-bg); border: 1px solid var(--ok-borde); }
.n1-reloj__eje { position: relative; height: 18px; font-size: 11px; color: var(--txt-3); font-variant-numeric: tabular-nums; }
.n1-reloj__eje span { position: absolute; top: 0; transform: translateX(-50%); }
.n1-reloj__eje span:first-child { transform: none; }
.n1-reloj__eje span:last-child { transform: translateX(-100%); }
.n1-reloj__pista { position: relative; height: 20px; border-radius: 6px; background:
  repeating-linear-gradient(to right, transparent 0, transparent calc(12.5% - 1px), var(--borde) calc(12.5% - 1px), var(--borde) 12.5%), var(--sup-2);
  border: 1px solid var(--borde); overflow: hidden; }
.n1-banda { position: absolute; top: 3px; bottom: 3px; border-radius: 4px; background: var(--acento-bg); border: 1px solid var(--acento-borde); }
.n1-banda--ctx { background: var(--neutro-bg); border: 1px dashed var(--neutro-borde); }
.n1-banda--continuo { left: 0; right: 0; border-radius: 4px;
  background: repeating-linear-gradient(to right, var(--acento-borde) 0, var(--acento-borde) 2px, transparent 2px, transparent 7px); border-color: var(--acento-borde); }
.n1-banda--siempre { left: 0; right: 0; background: var(--ok-bg); border: 1px solid var(--ok-borde); }
.n1-marca { position: absolute; top: 3px; bottom: 3px; width: 8px; margin-left: -4px; border-radius: 3px; background: var(--acento); }
.n1-marca--inferida { background: transparent; border: 2px solid var(--acento); }
.n1-reloj__pie { margin: 6px 0 0; }
@media (max-width: 700px) {
  .n1-reloj__fila { grid-template-columns: minmax(0, 1fr); gap: 2px; margin-bottom: 6px; }
  .n1-reloj__fila--eje > :first-child { display: none; }
}

/* semana tipo */
.n1-semana { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-3, 12px); grid-template-columns: repeat(auto-fit, minmax(min(100%, 138px), 1fr)); }
.n1-dia { height: 100%; display: flex; flex-direction: column; gap: 6px; padding: 12px 14px; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3, 12px); min-width: 0; }
.n1-dia[aria-current="date"] { border-color: var(--acento); box-shadow: 0 0 0 1px var(--acento); }
.n1-dia__nombre { display: flex; align-items: center; justify-content: space-between; gap: 6px; margin: 0; font-size: 12px; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--txt-3); }
.n1-dia__tema { margin: 0; font-size: 15px; font-weight: 650; line-height: 1.3; }
.n1-dia p { margin: 0; font-size: 13px; line-height: 1.45; color: var(--txt-2); overflow-wrap: anywhere; }
.n1-dia__motor { margin-top: auto !important; padding-top: 6px; border-top: 1px solid var(--borde); font-size: 12px !important; }

/* reglas de oro */
.n1-principio { display: flex; gap: var(--e-3, 12px); align-items: flex-start; padding: var(--e-4, 16px); background: var(--acento-bg); border: 1px solid var(--acento-borde); border-radius: var(--r-3, 12px); }
.n1-principio .icono { flex: none; color: var(--acento-fuerte); margin-top: 2px; }
.n1-principio h3 { margin: 0 0 4px; font-size: 1.05rem; color: var(--txt); }
.n1-principio p { margin: 0; color: var(--txt-2); line-height: 1.5; }
.n1-reglas { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-3, 12px); counter-reset: regla; grid-template-columns: repeat(auto-fit, minmax(min(100%, 380px), 1fr)); }
.n1-regla { display: grid; grid-template-columns: 32px minmax(0, 1fr); gap: 6px var(--e-3, 12px); padding: 14px 16px; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3, 12px); min-width: 0; }
.n1-regla__n { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; font-weight: 700; font-size: 13px; background: var(--neutro-bg); color: var(--neutro); font-variant-numeric: tabular-nums; }
.n1-regla h3 { margin: 0; font-size: 15px; font-weight: 650; line-height: 1.3; }
.n1-regla p { margin: 4px 0 0; font-size: 14px; line-height: 1.45; color: var(--txt-2); }
.n1-regla > div { min-width: 0; }
.n1-regla .detalle-tecnico { margin-top: 8px; }
`;

// ───────────────────────── Avisos ─────────────────────────

export const CSS_AVISOS = `
.n1-alertas { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-2, 8px); }
.n1-alerta { display: grid; grid-template-columns: minmax(120px, auto) minmax(0, 1fr) auto; gap: 6px var(--e-3, 12px); align-items: start; padding: 12px 14px; background: var(--sup); border: 1px solid var(--borde); border-left-width: 4px; border-radius: var(--r-2, 8px); min-width: 0; }
.n1-alerta[data-tono="error"] { border-left-color: var(--punto-error); }
.n1-alerta[data-tono="grave"] { border-left-color: var(--punto-grave); }
.n1-alerta[data-tono="aviso"] { border-left-color: var(--punto-aviso); }
.n1-alerta[data-tono="info"] { border-left-color: var(--info); }
.n1-alerta[data-tono="neutro"] { border-left-style: dashed; }
.n1-alerta__titulo { margin: 0; font-size: 14.5px; font-weight: 650; line-height: 1.35; overflow-wrap: anywhere; }
.n1-alerta__accion { margin: 2px 0 0; font-size: 13.5px; line-height: 1.45; color: var(--txt-2); overflow-wrap: anywhere; }
.n1-alerta__meta { display: flex; flex-wrap: wrap; gap: 2px 12px; margin-top: 4px; font-size: 12.5px; color: var(--txt-3); }
.n1-alerta__hora { font-size: 12.5px; color: var(--txt-3); white-space: nowrap; font-variant-numeric: tabular-nums; }
@media (max-width: 720px) { .n1-alerta { grid-template-columns: minmax(0, 1fr); } .n1-alerta__hora { white-space: normal; } }
.n1-ruta { width: 100%; border-collapse: collapse; font-size: var(--t-sm, .93rem); }
.n1-ruta th, .n1-ruta td { text-align: left; vertical-align: top; padding: 8px 10px; border-top: 1px solid var(--borde); }
.n1-ruta thead th { border-top: 0; background: var(--sup-2); font-size: .78rem; letter-spacing: .04em; text-transform: uppercase; color: var(--txt-3); font-weight: 650; }
.n1-ruta td { color: var(--txt-2); line-height: 1.45; }
.n1-ruta td:first-child { white-space: nowrap; }
.n1-tabla-caja { overflow-x: auto; border: 1px solid var(--borde); border-radius: var(--r-3, 12px); background: var(--sup); box-shadow: var(--sombra); }
.n1-tabla-caja .n1-ruta { min-width: 560px; }
.n1-canal { display: grid; gap: var(--e-3, 12px); grid-template-columns: repeat(auto-fit, minmax(min(100%, 220px), 1fr)); }
.n1-canal > div { display: flex; flex-direction: column; gap: 6px; padding: 14px 16px; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3, 12px); min-width: 0; }
.n1-canal h3 { margin: 0; font-size: 15px; font-weight: 650; display: flex; gap: 8px; align-items: center; }
.n1-canal p { margin: 0; font-size: 14px; line-height: 1.5; color: var(--txt-2); }
.n1-muestra { margin: 0; padding: 10px 12px; background: var(--sup-2); border: 1px dashed var(--borde-fuerte); border-radius: var(--r-2, 8px); font-family: var(--mono); font-size: .84rem; line-height: 1.6; color: var(--txt); overflow-wrap: anywhere; white-space: pre-wrap; }
.n1-avisadores { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-3, 12px); grid-template-columns: repeat(auto-fit, minmax(min(100%, 330px), 1fr)); }
.n1-avisador { display: flex; flex-direction: column; gap: 8px; padding: 14px 16px; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3, 12px); min-width: 0; }
.n1-avisador h3 { margin: 0; font-size: 15px; font-weight: 650; line-height: 1.3; }
.n1-avisador p { margin: 0; font-size: 14px; line-height: 1.5; color: var(--txt-2); }
`;

// ───────────────────────── Pagos ─────────────────────────

export const CSS_PAGOS = `
.n1-cuentas { display: grid; gap: var(--e-4, 16px); grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr)); align-items: start; }
.n1-cuenta { display: flex; flex-direction: column; gap: var(--e-3, 12px); padding: var(--e-4, 16px); background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3, 12px); box-shadow: var(--sombra); min-width: 0; }
.n1-cuenta__cab { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px; }
.n1-cuenta__cab h3 { margin: 0; font-size: 1.05rem; font-weight: 650; display: flex; gap: 8px; align-items: center; }
.n1-preguntas { list-style: none; margin: 0; padding: 0; display: grid; gap: 0; }
.n1-pregunta { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 4px var(--e-3, 12px); padding: 10px 0; border-top: 1px solid var(--borde); align-items: start; }
.n1-pregunta:first-child { border-top: 0; padding-top: 0; }
.n1-pregunta h4 { margin: 0; font-size: 14px; font-weight: 600; line-height: 1.35; color: var(--txt); }
.n1-pregunta p { margin: 2px 0 0; font-size: 13px; line-height: 1.45; color: var(--txt-2); overflow-wrap: anywhere; }
.n1-pregunta__estado { display: flex; flex-direction: column; align-items: flex-end; gap: 4px; }
.n1-pregunta__estado small { font-size: 12px; color: var(--txt-3); white-space: nowrap; }
@media (max-width: 520px) { .n1-pregunta { grid-template-columns: minmax(0, 1fr); } .n1-pregunta__estado { align-items: flex-start; } }
.n1-cotejos { display: grid; gap: var(--e-3, 12px); grid-template-columns: repeat(auto-fit, minmax(min(100%, 300px), 1fr)); }
.n1-cotejo { display: flex; flex-direction: column; gap: 6px; padding: 12px 14px; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-2, 8px); min-width: 0; }
.n1-cotejo h4 { margin: 0; font-size: 14px; font-weight: 650; }
.n1-cotejo dl { margin: 0; }
.n1-sinsaldo { display: flex; gap: var(--e-3, 12px); align-items: flex-start; padding: var(--e-4, 16px); background: var(--sup-2); border: 1px dashed var(--borde-fuerte); border-radius: var(--r-3, 12px); }
.n1-sinsaldo .icono { flex: none; color: var(--txt-3); margin-top: 2px; }
.n1-sinsaldo h3 { margin: 0 0 4px; font-size: 1rem; }
.n1-sinsaldo p { margin: 0 0 6px; font-size: 14px; line-height: 1.5; color: var(--txt-2); }
.n1-tachada { text-decoration: line-through; text-decoration-thickness: 2px; color: var(--txt-3); }
`;
