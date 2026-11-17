// lib/estilos-t1.js — CSS propio de #/tareas («Mis tareas»; clases `t1-*`). Se instala con `ui.instalarEstilos('t1-tareas', ESTILOS_T1)`:
// hoja construida por CSSOM (la CSP `style-src 'self'` no admite <style> ni style="" en línea).
// Usa SOLO tokens de styles.css (--sup, --borde, --acento-bg, --ok, --aviso…): claro y oscuro salen solos. El color nunca va solo: cada estado lleva icono y palabra.
// Se adapta al ancho de SU contenedor (container queries sobre `.t1`), no al de la ventana: con el menú lateral abierto o cerrado se ve igual de bien.

export const ESTILOS_T1 = `
.t1 { container-type: inline-size; container-name: t1; display: grid; grid-template-columns: minmax(0, 1fr); gap: var(--e-4); min-width: 0; max-width: 100%; align-content: start; }
.t1 .cab { grid-template-columns: minmax(0, 1fr); }
.t1-pila { display: grid; gap: var(--e-2); min-width: 0; }
.t1-fila { display: flex; flex-wrap: wrap; gap: var(--e-2); align-items: center; min-width: 0; }
.t1-tenue { color: var(--txt-3); }
.t1-sub { color: var(--txt-2); font-size: var(--t-sm); overflow-wrap: anywhere; }
.t1 .chip { white-space: normal; height: auto; min-height: 22px; padding-top: 3px; padding-bottom: 3px; line-height: 1.25; text-align: left; overflow: visible; }

/* ───────── arriba: tu siguiente paso + contador ───────── */
.t1-arriba { display: grid; grid-template-columns: minmax(0, 1.9fr) minmax(250px, 1fr); gap: var(--e-3); align-items: stretch; }
@container t1 (max-width: 820px) { .t1-arriba { grid-template-columns: minmax(0, 1fr); } }
.t1-sig { background: var(--sup); border: 1px solid var(--borde); border-left: 4px solid var(--acento); border-radius: var(--r-3); box-shadow: var(--sombra); padding: var(--e-4) var(--e-5); display: grid; gap: var(--e-2); align-content: start; min-width: 0; }
.t1-sig--calma { border-left-color: var(--punto-ok); }
.t1-sig__rotulo { margin: 0; font-size: var(--t-xs); font-weight: 700; letter-spacing: .07em; text-transform: uppercase; color: var(--acento-fuerte); }
.t1-sig--calma .t1-sig__rotulo { color: var(--ok); }
.t1-sig__titulo { margin: 0; font-size: var(--t-lg); font-weight: 650; line-height: 1.25; letter-spacing: -.01em; overflow-wrap: anywhere; }
.t1-sig__texto { margin: 0; color: var(--txt-2); overflow-wrap: anywhere; }
.t1-sig__acciones { display: flex; flex-wrap: wrap; gap: var(--e-2); align-items: center; margin-top: var(--e-1); }
.t1-cuenta { background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); box-shadow: var(--sombra); padding: var(--e-4) var(--e-5); display: grid; gap: var(--e-2); align-content: start; min-width: 0; }
.t1-cuenta__rotulo { margin: 0; font-size: var(--t-xs); font-weight: 700; letter-spacing: .07em; text-transform: uppercase; color: var(--txt-2); }
.t1-cuenta__num { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px; }
.t1-cuenta__valor { font-size: var(--t-2xl); font-weight: 700; letter-spacing: -.02em; line-height: 1; font-variant-numeric: tabular-nums; }
.t1-cuenta__de { color: var(--txt-2); font-size: var(--t-md); }
.t1-cuenta__nota { margin: 0; color: var(--txt-2); font-size: var(--t-sm); }

/* ───────── barra de avance ───────── */
.t1-barra { display: flex; height: 8px; border-radius: var(--r-pill); background: var(--sup-3); overflow: hidden; min-width: 0; }
.t1-barra > i { display: block; height: 100%; width: var(--p, 0%); min-width: 0; }
.t1-barra__datos { background: var(--punto-ok); }
.t1-barra__marca { background: repeating-linear-gradient(135deg, var(--punto-ok) 0 3px, transparent 3px 6px); border-left: 1px solid var(--sup); }

/* ───────── avisos en caja (siempre con icono) ───────── */
.t1-aviso { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--e-2); align-items: start; border: 1px solid var(--info-borde); background: var(--info-bg); border-radius: var(--r-2); padding: var(--e-2) var(--e-3); font-size: var(--t-sm); color: var(--txt); overflow-wrap: anywhere; }
.t1-aviso .icono { color: var(--info); margin-top: 2px; }
.t1-aviso--aviso { border-color: var(--aviso-borde); background: var(--aviso-bg); }
.t1-aviso--aviso .icono { color: var(--aviso); }
.t1-aviso--error { border-color: var(--error-borde); background: var(--error-bg); }
.t1-aviso--error .icono { color: var(--error); }
.t1-aviso--ok { border-color: var(--ok-borde); background: var(--ok-bg); }
.t1-aviso--ok .icono { color: var(--ok); }
.t1-aviso__texto { min-width: 0; display: grid; gap: 2px; }
.t1-aviso select { max-width: 100%; }

/* ───────── herramientas: buscar y filtrar ───────── */
.t1-herr { display: flex; flex-wrap: wrap; gap: var(--e-2) var(--e-4); align-items: center; padding: var(--e-3); background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); }
.t1-herr__busca { flex: 1 1 220px; min-width: 0; max-width: 340px; }
.t1-herr__campo { display: flex; align-items: center; gap: 8px; font-size: var(--t-sm); color: var(--txt-2); min-width: 0; }
.t1-herr__campo .campo { width: auto; max-width: 100%; }
.t1-herr__fin { margin-left: auto; color: var(--txt-3); font-size: var(--t-sm); }
.t1 .segmentado { max-width: 100%; overflow-x: auto; }
.t1 .segmentado__op { white-space: nowrap; }
.t1-vista .segmentado__op { padding: 0 10px; }

/* ───────── lista por momentos ───────── */
.t1-momentos { display: grid; gap: var(--e-4); min-width: 0; }
.t1-momento { background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); box-shadow: var(--sombra); min-width: 0; scroll-margin-top: var(--e-4); }
.t1-mom__cab { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: var(--e-3); align-items: center; padding: var(--e-4); }
.t1-mom__num { width: 36px; height: 36px; border-radius: 50%; display: grid; place-items: center; font-weight: 700; font-variant-numeric: tabular-nums; background: var(--acento-bg); color: var(--acento-fuerte); border: 1px solid var(--acento-borde); }
.t1-mom__titulo { margin: 0; font-size: var(--t-md); font-weight: 650; line-height: 1.3; overflow-wrap: anywhere; }
.t1-mom__resumen { margin: 2px 0 0; color: var(--txt-2); font-size: var(--t-sm); overflow-wrap: anywhere; }
.t1-mom__avance { display: grid; gap: 4px; min-width: 150px; justify-items: end; text-align: right; font-size: var(--t-sm); color: var(--txt-2); font-variant-numeric: tabular-nums; }
.t1-mom__avance .t1-barra { width: 150px; }
@container t1 (max-width: 640px) {
  .t1-mom__cab { grid-template-columns: auto minmax(0, 1fr); }
  .t1-mom__avance { grid-column: 1 / -1; justify-items: stretch; text-align: left; }
  .t1-mom__avance .t1-barra { width: 100%; }
}
.t1-lista { list-style: none; margin: 0; padding: 0; border-top: 1px solid var(--borde); }
.t1-tarea { display: grid; grid-template-columns: 30px minmax(0, 1fr) auto; gap: var(--e-2) var(--e-3); align-items: start; padding: var(--e-3) var(--e-4); border-bottom: 1px solid var(--borde); cursor: pointer; transition: background var(--t-rapida) var(--ease); }
.t1-tarea:last-child { border-bottom: 0; border-radius: 0 0 var(--r-3) var(--r-3); }
.t1-tarea:hover { background: var(--sup-2); }
.t1-tarea[data-abierta="1"] { background: var(--acento-bg); }
.t1-tarea__ic { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; border: 1.5px solid var(--borde-fuerte); color: var(--txt-2); background: var(--sup); flex: none; }
.t1-tarea[data-estado="hecha"] .t1-tarea__ic { background: var(--ok-bg); color: var(--ok); border-color: var(--ok-borde); }
.t1-tarea[data-estado="en_curso"] .t1-tarea__ic { background: var(--info-bg); color: var(--info); border-color: var(--info-borde); }
.t1-tarea[data-estado="espera_firma"] .t1-tarea__ic { background: var(--acento-bg); color: var(--acento-fuerte); border-color: var(--acento); }
.t1-tarea[data-estado="bloqueada"] .t1-tarea__ic { background: var(--aviso-bg); color: var(--aviso); border-color: var(--aviso-borde); }
.t1-tarea[data-estado="no_existe"] .t1-tarea__ic, .t1-tarea[data-estado="no_comprobable"] .t1-tarea__ic { border-style: dashed; }
.t1-tarea__cuerpo { min-width: 0; }
.t1-tarea__titulo { margin: 0; font-size: var(--t-base); font-weight: 600; line-height: 1.35; overflow-wrap: anywhere; }
.t1-tarea[data-estado="hecha"] .t1-tarea__titulo { color: var(--txt-2); }
.t1-tarea__porque { margin: 2px 0 0; color: var(--txt-2); font-size: var(--t-sm); overflow-wrap: anywhere; }
.t1-tarea__evid { margin: 5px 0 0; display: flex; gap: 6px; align-items: flex-start; color: var(--txt-3); font-size: var(--t-sm); overflow-wrap: anywhere; }
.t1-tarea__evid .icono { flex: none; margin-top: 2px; }
.t1-tarea__cuando { display: inline-flex; gap: 4px; align-items: center; color: var(--txt-2); font-size: var(--t-xs); font-weight: 600; }
.t1-tarea__lado { display: grid; gap: var(--e-2); justify-items: end; align-content: start; }
.t1-tarea__chips { display: flex; flex-wrap: wrap; gap: 6px; justify-content: flex-end; }
@container t1 (max-width: 720px) {
  .t1-tarea { grid-template-columns: 30px minmax(0, 1fr); }
  .t1-tarea__lado { grid-column: 2; justify-items: start; }
  .t1-tarea__chips { justify-content: flex-start; }
}
.t1-chip-quien { background: var(--sup-2); border-color: var(--borde-fuerte); color: var(--txt-2); }
.t1-chip-quien--dueno { background: var(--acento-bg); border-color: var(--acento-borde); color: var(--acento-fuerte); }
.t1-chip-demo { border-style: dashed; }
.t1-chip-estado--no_existe, .t1-chip-estado--no_comprobable { border-style: dashed; }

/* ───────── mapa del negocio ───────── */
.t1-mapa { min-width: 0; max-width: 100%; overflow-x: auto; padding-bottom: var(--e-3); scroll-snap-type: x proximity; -webkit-overflow-scrolling: touch; border-radius: var(--r-3); }
.t1-mapa:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }
.t1-camino { display: grid; grid-template-columns: repeat(6, minmax(176px, 1fr)); gap: var(--e-3); min-width: min-content; align-items: start; }
@container t1 (max-width: 700px) { .t1-camino { grid-template-columns: repeat(6, minmax(236px, 1fr)); } }
.t1-col { display: grid; gap: var(--e-2); align-content: start; min-width: 0; scroll-snap-align: start; background: var(--sup-2); border: 1px solid var(--borde); border-radius: var(--r-3); padding: var(--e-2); }
.t1-col__cab { display: grid; grid-template-columns: auto minmax(0, 1fr) auto; gap: 8px; align-items: center; padding: 4px 4px 6px; }
.t1-col__num { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; font-weight: 700; font-size: var(--t-sm); background: var(--acento-bg); color: var(--acento-fuerte); border: 1px solid var(--acento-borde); }
.t1-col__titulo { margin: 0; font-size: var(--t-sm); font-weight: 650; line-height: 1.25; overflow-wrap: anywhere; }
.t1-col__flecha { color: var(--txt-3); }
.t1-col__cuenta { grid-column: 2 / -1; font-size: var(--t-xs); color: var(--txt-2); font-variant-numeric: tabular-nums; display: grid; gap: 4px; }
.t1-col__lista { display: grid; gap: 6px; list-style: none; margin: 0; padding: 0; }
.t1-ficha { display: grid; grid-template-columns: 22px minmax(0, 1fr); gap: 3px 8px; width: 100%; text-align: left; font: inherit; color: var(--txt); cursor: pointer; background: var(--sup); border: 1px solid var(--borde); border-left: 4px solid var(--borde-fuerte); border-radius: var(--r-2); padding: 8px 10px; transition: border-color var(--t-rapida), box-shadow var(--t-rapida), background var(--t-rapida); }
.t1-ficha:hover { box-shadow: var(--sombra-2); border-color: var(--borde-input); }
.t1-ficha:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }
.t1-ficha__ic { color: var(--txt-2); padding-top: 1px; }
.t1-ficha__titulo { font-size: var(--t-sm); font-weight: 600; line-height: 1.3; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; overflow-wrap: anywhere; }
.t1-ficha__pie { grid-column: 2; display: flex; flex-wrap: wrap; gap: 2px 8px; align-items: center; font-size: var(--t-xs); font-weight: 600; color: var(--txt-2); }
.t1-ficha__quien { display: inline-flex; align-items: center; gap: 3px; color: var(--txt-3); font-weight: 550; }
.t1-ficha[data-estado="hecha"] { border-left-color: var(--punto-ok); background: color-mix(in srgb, var(--ok-bg) 55%, var(--sup)); }
.t1-ficha[data-estado="hecha"] .t1-ficha__ic, .t1-ficha[data-estado="hecha"] .t1-ficha__estado { color: var(--ok); }
.t1-ficha[data-estado="en_curso"] { border-left-color: var(--info); }
.t1-ficha[data-estado="en_curso"] .t1-ficha__ic, .t1-ficha[data-estado="en_curso"] .t1-ficha__estado { color: var(--info); }
.t1-ficha[data-estado="espera_firma"] { border-left-color: var(--acento); background: var(--acento-bg); border-color: var(--acento-borde); }
.t1-ficha[data-estado="espera_firma"] .t1-ficha__ic, .t1-ficha[data-estado="espera_firma"] .t1-ficha__estado { color: var(--acento-fuerte); }
.t1-ficha[data-estado="bloqueada"] { border-left-color: var(--punto-aviso); }
.t1-ficha[data-estado="bloqueada"] .t1-ficha__ic, .t1-ficha[data-estado="bloqueada"] .t1-ficha__estado { color: var(--aviso); }
.t1-ficha[data-estado="no_existe"] { border-style: dashed dashed dashed solid; border-left-color: var(--borde-fuerte); background: transparent; }
.t1-ficha[data-estado="no_comprobable"] { border-style: dotted dotted dotted solid; border-left-color: var(--borde-fuerte); }
.t1-ficha[data-abierta="1"] { box-shadow: 0 0 0 2px var(--acento); }

/* ───────── panel lateral «Cómo hacerla» ───────── */
.t1-pan-fondo { position: fixed; inset: 0; z-index: 70; background: var(--velo); display: flex; justify-content: flex-end; }
.t1-pan { width: min(600px, 100vw); height: 100%; background: var(--sup); color: var(--txt); border-left: 1px solid var(--borde); box-shadow: var(--sombra-modal); display: flex; flex-direction: column; outline: none; }
@media (prefers-reduced-motion: no-preference) { .t1-pan { animation: t1-entra .16s ease-out; } }
@keyframes t1-entra { from { transform: translateX(24px); opacity: .4; } to { transform: none; opacity: 1; } }
.t1-pan__cab { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--e-3); padding: var(--e-4) var(--e-5); border-bottom: 1px solid var(--borde); }
.t1-pan__rotulo { font-size: var(--t-xs); font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--acento-fuerte); margin: 0 0 2px; }
.t1-pan__titulo { margin: 0; font-size: var(--t-md); font-weight: 650; line-height: 1.3; overflow-wrap: anywhere; }
.t1-pan__chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.t1-pan__cuerpo { flex: 1; min-height: 0; overflow: auto; padding: var(--e-4) var(--e-5); display: grid; gap: var(--e-4); align-content: start; }
.t1-pan__pie { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: var(--e-2); padding: var(--e-3) var(--e-5); border-top: 1px solid var(--borde); background: var(--sup-2); }
@media (max-width: 599px) { .t1-pan__cab, .t1-pan__cuerpo, .t1-pan__pie { padding-left: var(--e-4); padding-right: var(--e-4); } }
.t1-bloque { display: grid; gap: 6px; min-width: 0; }
.t1-bloque__titulo { margin: 0; font-size: var(--t-xs); font-weight: 700; letter-spacing: .06em; text-transform: uppercase; color: var(--txt-3); }
.t1-bloque p { margin: 0; overflow-wrap: anywhere; }
.t1-estado-caja { display: grid; gap: var(--e-2); border: 1px solid var(--borde); border-radius: var(--r-2); padding: var(--e-3); background: var(--sup-2); }
.t1-estado-caja[data-estado="hecha"] { border-color: var(--ok-borde); background: var(--ok-bg); }
.t1-estado-caja[data-estado="espera_firma"] { border-color: var(--acento-borde); background: var(--acento-bg); }
.t1-estado-caja[data-estado="bloqueada"] { border-color: var(--aviso-borde); background: var(--aviso-bg); }
.t1-estado-caja__frase { display: flex; gap: 8px; align-items: flex-start; margin: 0; overflow-wrap: anywhere; }
.t1-estado-caja__frase .icono { flex: none; margin-top: 3px; }
.t1-marca { display: flex; flex-wrap: wrap; gap: var(--e-2); align-items: center; }
.t1-marca__nota { color: var(--txt-2); font-size: var(--t-sm); }
.t1-pasos { margin: 0; padding: 0; list-style: none; counter-reset: paso; display: grid; gap: var(--e-3); }
.t1-paso { counter-increment: paso; display: grid; grid-template-columns: 26px minmax(0, 1fr); gap: 10px; align-items: start; }
.t1-paso::before { content: counter(paso); width: 26px; height: 26px; border-radius: 50%; display: grid; place-items: center; font-size: var(--t-sm); font-weight: 700; font-variant-numeric: tabular-nums; background: var(--acento-bg); color: var(--acento-fuerte); border: 1px solid var(--acento-borde); }
.t1-paso__cuerpo { display: grid; gap: var(--e-2); min-width: 0; padding-top: 2px; }
.t1-paso__texto { margin: 0; overflow-wrap: anywhere; line-height: 1.5; }
.t1-ho { display: grid; gap: var(--e-2); }
.t1-ho__caja { display: grid; gap: 4px; border: 1px solid var(--borde-fuerte); border-radius: var(--r-2); padding: var(--e-3); background: var(--sup); }
.t1-ho__caja--objetivo { border: 1px dashed color-mix(in srgb, var(--info) 65%, transparent); background: color-mix(in srgb, var(--info-bg) 55%, var(--sup)); }
.t1-ho__etiqueta { display: inline-flex; align-items: center; gap: 6px; width: fit-content; min-height: 24px; padding: 2px 10px 2px 8px; border-radius: var(--r-pill); font-size: var(--t-xs); font-weight: 700; letter-spacing: .03em; border: 1px solid; line-height: 1.2; }
.t1-ho__etiqueta--hoy { color: var(--txt); background: var(--sup-3); border-color: var(--borde-fuerte); }
.t1-ho__etiqueta--objetivo { color: var(--info); background: transparent; border: 1px dashed color-mix(in srgb, var(--info) 70%, transparent); }
.t1-ho__texto { margin: 0; overflow-wrap: anywhere; }
.t1-ho__fuente { margin: 0; color: var(--txt-2); font-size: var(--t-sm); }
.t1-donde { display: flex; flex-wrap: wrap; gap: var(--e-2) var(--e-3); margin: 0; padding: 0; list-style: none; }
.t1-terminos { margin: 0; color: var(--txt-2); font-size: var(--t-sm); }

/* ───────── «Ejecutar ahora» (acción segura) ───────── */
.t1-accion { display: grid; gap: var(--e-2); border: 1px solid var(--borde); border-radius: var(--r-2); padding: var(--e-3); background: var(--sup); }
.t1-accion__quehace { margin: 0; color: var(--txt-2); font-size: var(--t-sm); overflow-wrap: anywhere; }
.t1-accion__fila { display: flex; flex-wrap: wrap; gap: var(--e-2); align-items: center; }
.t1-res { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--e-2); align-items: start; border: 1px solid var(--borde); border-radius: var(--r-2); padding: var(--e-2) var(--e-3); background: var(--sup-2); }
.t1-res[data-clave="ok"] { border-color: var(--ok-borde); background: var(--ok-bg); }
.t1-res[data-clave="error"] { border-color: var(--error-borde); background: var(--error-bg); }
.t1-res[data-clave="aviso"] { border-color: var(--aviso-borde); background: var(--aviso-bg); }
.t1-res[data-clave="corriendo"] { border-color: var(--info-borde); background: var(--info-bg); }
.t1-res .icono { margin-top: 2px; }
.t1-res[data-clave="ok"] .icono { color: var(--ok); }
.t1-res[data-clave="error"] .icono { color: var(--error); }
.t1-res[data-clave="aviso"] .icono { color: var(--aviso); }
.t1-res[data-clave="corriendo"] .icono { color: var(--info); }
@media (prefers-reduced-motion: no-preference) { .t1-res[data-clave="corriendo"] .icono { animation: t1-gira 1.1s linear infinite; } }
@keyframes t1-gira { to { transform: rotate(360deg); } }
.t1-res__titulo { font-weight: 650; margin: 0; }
.t1-res__texto { margin: 0; font-size: var(--t-sm); color: var(--txt-2); overflow-wrap: anywhere; }
.t1-salida { margin: 0; padding: 10px 12px; max-height: 260px; overflow: auto; background: var(--terminal-bg); color: var(--terminal-txt); border-radius: var(--r-2); font-family: var(--mono); font-size: 12.5px; line-height: 1.5; white-space: pre-wrap; word-break: break-word; }

/* ───────── pie ───────── */
.t1-pie { display: grid; gap: var(--e-2); }
`;
