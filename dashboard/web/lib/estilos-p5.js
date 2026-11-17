// lib/estilos-p5.js — CSS propio de Operación, Finanzas, Agentes, Cumplimiento y Parámetros y límites (clases `p5-*`, cifras y gráficos).
// Se instala con `ui.instalarEstilos('u4', ESTILOS_P5)`: hoja construida por CSSOM (la CSP `style-src 'self'` no admite <style> ni style="" en línea).
// Usa SOLO tokens de styles.css (--sup, --borde, --txt-2, --ok, --grave, --serie-1/8, --viz-*…): ninguna paleta propia. Colores de gráfico validados con
// validate_palette.js (claro #2a78d6/#e34948 sobre #fff; oscuro #3987e5/#e66767 sobre #161b22: ΔE adyacente ≥ 29, contraste ≥ 3:1).
// Los estados (ok / aviso / error) SIEMPRE llevan icono y etiqueta en el DOM: el color nunca va solo.

export const ESTILOS_P5 = `
/* ───────── tokens de gráfico: los comunes de styles.css (--serie-1 azul y --serie-8 rojo, polos opuestos validados; --viz-grid / --viz-eje) ───────── */
.p5-viz, .p5-margen, .p5-bullet, .p5-medidor, .p5-madurez, .p5-ranking { --p5-serie: var(--serie-1); --p5-serie-tenue: color-mix(in srgb, var(--serie-1) 16%, transparent); --p5-polo: var(--serie-8); --p5-banda: color-mix(in srgb, var(--punto-ok) 15%, transparent); }

/* ───────── utilidades ───────── */
.p5-pila { display: grid; gap: var(--e-3); min-width: 0; align-content: start; }
.p5-pila--chica { gap: var(--e-1); }
.p5-fila { display: flex; flex-wrap: wrap; gap: var(--e-2) var(--e-4); align-items: center; min-width: 0; }
.p5-fila--junta { gap: var(--e-1) var(--e-2); }
.p5-fila--sin-corte { flex-wrap: nowrap; }
.p5-sub { color: var(--txt-2); font-size: .86rem; overflow-wrap: anywhere; min-width: 0; }
.p5-causa { color: var(--error); font-size: .82rem; overflow-wrap: anywhere; min-width: 0; }
.p5-mono { font-family: var(--mono); font-size: .86em; }
.p5-titulo-chico { font-size: .76rem; text-transform: uppercase; letter-spacing: .06em; color: var(--txt-2); font-weight: 650; margin-bottom: 2px; }
.p5-regla { display: inline-block; font-family: var(--mono); font-size: .8rem; font-weight: 700; padding: 0 6px; border: 1px solid var(--borde-fuerte); border-radius: var(--r-1); background: var(--sup-2); }
.p5-rutas { display: grid; gap: 4px; }
.p5-selectores { display: flex; flex-wrap: wrap; gap: var(--e-3); align-items: center; }
.p5-buscar { max-width: 520px; width: 100%; }
.p5-ancho-completo { grid-column: 1 / -1; }

/* cifras: tachada con su causa, sin dato, pocos datos (B0-17) */
.cifra-tachada { display: inline-flex; flex-wrap: wrap; align-items: baseline; gap: 2px 6px; }
.cifra-vieja { text-decoration: line-through; text-decoration-thickness: 2px; text-decoration-color: var(--error); color: var(--txt-3); }
.cifra-causa { color: var(--error); font-size: .76rem; font-weight: 600; white-space: normal; overflow-wrap: anywhere; line-height: 1.2; text-align: right; }
.cifra-sin-dato { font-style: italic; } /* el color ya viene de styles.css */
.cifra-gris { color: var(--txt-2); }
.uso-sin-tope { display: inline-flex; gap: 6px; align-items: center; flex-wrap: wrap; color: var(--txt-2); font-size: .82rem; }

/* avisos en caja, siempre con icono */
.p5-aviso { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--e-2); align-items: start; border: 1px solid var(--aviso-borde); background: var(--aviso-bg); border-radius: var(--r-2); padding: var(--e-2) var(--e-3); color: var(--txt); font-size: .9rem; overflow-wrap: anywhere; min-width: 0; }
.p5-aviso__icono { color: var(--aviso); display: inline-flex; padding-top: 1px; }
.p5-aviso--error { border-color: var(--error-borde); background: var(--error-bg); }
.p5-aviso--error .p5-aviso__icono { color: var(--error); }
.p5-aviso--info { border-color: var(--info-borde); background: var(--info-bg); }
.p5-aviso--info .p5-aviso__icono { color: var(--info); }
.p5-aviso__texto { min-width: 0; }

/* ───────── métricas con contexto ───────── */
.p5-metricas { display: grid; grid-template-columns: repeat(auto-fit, minmax(214px, 1fr)); gap: var(--e-3); }
.p5-ctx { display: grid; gap: var(--e-2); min-width: 0; width: 100%; }
.metrica .chip, .p5-vered .chip, .p5-feed .chip { white-space: normal; height: auto; min-height: 20px; padding-top: 2px; padding-bottom: 2px; line-height: 1.25; text-align: left; overflow: visible; }
.metrica__valor .cifra-tachada, .metrica__valor .cifra-sin-dato { font-size: 1rem; font-weight: 600; }
.metrica__valor .cifra-vieja { font-size: 1.4rem; }

/* medidor: pista = tono claro de la misma rampa; el relleno lleva la gravedad (acento → aviso → error) */
.p5-medidor { display: grid; gap: 4px; min-width: 110px; }
.p5-medidor__pista { position: relative; height: 8px; border-radius: 99px; background: var(--p5-serie-tenue); overflow: hidden; }
.p5-medidor__relleno { height: 100%; border-radius: 99px; background: var(--p5-serie); }
.p5-medidor.zona-aviso .p5-medidor__relleno { background: var(--punto-aviso); }
.p5-medidor.zona-rojo .p5-medidor__relleno, .p5-medidor.zona-error .p5-medidor__relleno { background: var(--punto-error); }
.p5-medidor.zona-ok .p5-medidor__relleno { background: var(--p5-serie); }
.p5-medidor.zona-bien .p5-medidor__relleno { background: var(--punto-ok); }
.p5-medidor__marca { position: absolute; top: -1px; bottom: -1px; width: 2px; background: var(--txt); opacity: .75; }
.p5-medidor__texto { font-size: .78rem; color: var(--txt-2); font-variant-numeric: tabular-nums; }

/* CPA frente a equilibrio y objetivo: tres zonas y una marca */
.p5-bullet { display: grid; gap: 4px; min-width: 0; }
.p5-bullet__pista { position: relative; height: 12px; border-radius: 99px; overflow: hidden; display: flex; background: var(--sup-3); }
.p5-bullet__zona { height: 100%; }
.p5-bullet__zona--objetivo { background: color-mix(in srgb, var(--punto-ok) 38%, transparent); }
.p5-bullet__zona--equilibrio { background: color-mix(in srgb, var(--punto-aviso) 38%, transparent); }
.p5-bullet__zona--sobre { background: color-mix(in srgb, var(--punto-error) 34%, transparent); flex: 1; }
.p5-bullet__marca { position: absolute; top: 0; bottom: 0; width: 4px; margin-left: -2px; border-radius: 2px; background: var(--txt); box-shadow: 0 0 0 2px var(--sup); }

/* ───────── veredicto: bloque protagonista ───────── */
.p5-vered { background: var(--sup); border: 1px solid var(--borde); border-left: 5px solid var(--borde-fuerte); border-radius: var(--r-3); box-shadow: var(--sombra); padding: var(--e-5); display: grid; gap: var(--e-4); min-width: 0; }
.p5-vered--ok { border-left-color: var(--punto-ok); }
.p5-vered--info { border-left-color: var(--acento); }
.p5-vered--aviso { border-left-color: var(--punto-aviso); }
.p5-vered--error { border-left-color: var(--punto-error); }
.p5-vered__cab { display: flex; flex-wrap: wrap; gap: var(--e-3) var(--e-5); align-items: center; justify-content: space-between; }
.p5-vered__titulos { display: grid; gap: 2px; min-width: 0; }
.p5-vered__rotulo { font-size: .76rem; text-transform: uppercase; letter-spacing: .07em; color: var(--txt-2); font-weight: 650; display: flex; gap: 6px; align-items: center; }
.p5-vered__estado { display: flex; align-items: center; gap: var(--e-3); font-size: 2rem; line-height: 1.1; font-weight: 750; letter-spacing: -.01em; }
.p5-vered__icono { display: inline-grid; place-items: center; width: 44px; height: 44px; border-radius: 50%; background: var(--neutro-bg); color: var(--neutro); flex: none; }
.p5-vered--ok .p5-vered__icono { background: var(--ok-bg); color: var(--ok); }
.p5-vered--info .p5-vered__icono { background: var(--info-bg); color: var(--info); }
.p5-vered--aviso .p5-vered__icono { background: var(--aviso-bg); color: var(--aviso); }
.p5-vered--error .p5-vered__icono { background: var(--error-bg); color: var(--error); }
.p5-vered__desc { color: var(--txt-2); max-width: 70ch; }
.p5-vered__reco { display: flex; flex-wrap: wrap; gap: var(--e-2) var(--e-3); align-items: center; background: var(--sup-2); border-radius: var(--r-2); padding: var(--e-2) var(--e-3); }
.p5-vered__chips { display: flex; flex-wrap: wrap; gap: var(--e-2); align-items: center; }
.p5-vered__rejilla { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: var(--e-5); align-items: start; }
.p5-vered__col { display: grid; gap: var(--e-3); min-width: 0; align-content: start; }
.p5-req { display: grid; gap: 4px; font-size: .9rem; }
.p5-req__cab { display: flex; justify-content: space-between; gap: var(--e-2); align-items: baseline; flex-wrap: wrap; }
.p5-req__estado { font-size: .78rem; color: var(--txt-2); display: inline-flex; gap: 4px; align-items: center; }
.p5-req__estado--ok { color: var(--ok); }
.p5-datos { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 0 var(--e-3); font-size: .9rem; }
.p5-datos dt { color: var(--txt-2); padding: 6px 0; border-bottom: 1px solid var(--borde); }
.p5-datos dd { padding: 6px 0; border-bottom: 1px solid var(--borde); text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; min-width: 0; overflow-wrap: anywhere; }
.p5-datos dt:last-of-type, .p5-datos dd:last-of-type { border-bottom: 0; }

/* ventana de madurez */
.p5-madurez { display: grid; gap: 6px; }
.p5-madurez__tramos { display: flex; gap: 2px; min-width: 0; }
.p5-madurez__tramo { display: grid; gap: 0; padding: 8px 10px; min-width: 0; font-size: .8rem; line-height: 1.25; }
.p5-madurez__tramo strong { font-size: 1rem; font-variant-numeric: tabular-nums; }
.p5-madurez__tramo span { color: var(--txt-2); overflow-wrap: anywhere; }
.p5-madurez__tramo--garantia { background: var(--p5-serie-tenue); border-radius: 8px 0 0 8px; }
.p5-madurez__tramo--margen { background: var(--sup-3); border-radius: 0 8px 8px 0; }
.p5-madurez__tramo:only-child { border-radius: 8px; }
.p5-madurez__pie { display: flex; justify-content: space-between; gap: var(--e-2); font-size: .78rem; color: var(--txt-2); }
.p5-madurez__fin { font-weight: 650; color: var(--txt); }

/* frescura */
.p5-fresc { display: flex; flex-wrap: wrap; align-items: center; gap: var(--e-2) var(--e-4); background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); padding: var(--e-3) var(--e-4); }
.p5-fresc__titulo { font-weight: 650; display: inline-flex; gap: 6px; align-items: center; }
.p5-fresc__fuente { display: inline-flex; gap: 6px; align-items: center; flex-wrap: wrap; }
.p5-fresc__fuente .chip { white-space: normal; height: auto; min-height: 20px; line-height: 1.25; padding-top: 2px; padding-bottom: 2px; }

/* ───────── gráficos propios ───────── */
.p5-graficos { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: var(--e-4); }
.p5-graficos--2 { grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); }
.p5-viz { margin: 0; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-3); padding: var(--e-3) var(--e-4) var(--e-3); display: grid; gap: var(--e-2); min-width: 0; align-content: start; box-shadow: var(--sombra); }
.p5-viz:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }
.p5-viz__cab { display: flex; justify-content: space-between; align-items: flex-start; gap: var(--e-2); }
.p5-viz__titulos { display: grid; gap: 1px; min-width: 0; }
.p5-viz__titulo { font-size: .95rem; font-weight: 650; }
.p5-viz__sub { font-size: .8rem; color: var(--txt-2); }
.p5-viz__lienzo { position: relative; min-width: 0; }
.p5-viz__svg { display: block; width: 100%; height: auto; overflow: visible; }
.p5-viz__rejilla { stroke: var(--viz-grid); stroke-width: 1; }
.p5-viz__eje { stroke: var(--viz-eje); stroke-width: 1; }
.p5-viz__tick { fill: var(--txt-3); font-size: 11px; font-variant-numeric: tabular-nums; font-family: var(--fuente); }
.p5-viz__linea { fill: none; stroke: var(--p5-serie); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.p5-viz__punto { fill: var(--p5-serie); stroke: var(--sup); stroke-width: 2; }
.p5-viz__punto--gris { fill: var(--sup); stroke: var(--p5-serie); stroke-width: 2; }
.p5-viz__punto--tachada { fill: var(--sup); stroke: var(--error); stroke-width: 2; }
.p5-viz__punto--ultimo { stroke-width: 2; }
.p5-viz__sel { stroke: var(--txt); }
.p5-viz__barra { fill: var(--p5-serie); }
.p5-viz__barra.p5-viz__sel { fill: color-mix(in srgb, var(--p5-serie) 80%, var(--txt)); stroke: none; }
.p5-viz__barra--gris { fill: color-mix(in srgb, var(--p5-serie) 45%, transparent); }
.p5-viz__barra--tachada { fill: color-mix(in srgb, var(--error) 30%, transparent); }
.p5-viz__banda { fill: var(--p5-banda); }
.p5-viz__rotulo-banda { fill: var(--txt-2); font-size: 11px; font-family: var(--fuente); }
.p5-viz__ref { stroke: var(--txt-2); stroke-width: 1; }
.p5-viz__rotulo-ref { fill: var(--txt-2); font-size: 11px; font-family: var(--fuente); }
.p5-viz__rotulo { fill: var(--viz-tinta); font-size: 12px; font-weight: 650; font-variant-numeric: tabular-nums; font-family: var(--fuente); }
.p5-viz__cruz { stroke: var(--txt-3); stroke-width: 1; }
.p5-viz__capa { cursor: crosshair; }
.p5-viz__tip { position: absolute; top: 4px; transform: translateX(-50%); z-index: 3; background: var(--sup); color: var(--txt); border: 1px solid var(--borde-fuerte); border-radius: var(--r-2); box-shadow: var(--sombra-modal); padding: 6px 10px; pointer-events: none; display: grid; gap: 2px; min-width: 110px; max-width: 240px; }
.p5-viz__tip-valor { font-size: 1.05rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.p5-viz__tip-fila { display: flex; gap: 6px; align-items: center; color: var(--txt-2); font-size: .8rem; }
.p5-viz__llave { width: 14px; height: 0; border-top: 2px solid var(--p5-serie); border-radius: 2px; }
.p5-viz__tip-aviso { font-size: .76rem; color: var(--txt-2); }
.p5-viz__tip-aviso--error { color: var(--error); font-weight: 600; }
.p5-viz__vacio { display: grid; place-items: center; min-height: 100px; color: var(--txt-2); font-size: .88rem; text-align: center; padding: var(--e-3); border: 1px dashed var(--borde-fuerte); border-radius: var(--r-2); }
.p5-viz__leyenda { display: flex; flex-wrap: wrap; gap: 4px var(--e-4); font-size: .8rem; color: var(--txt-2); }
.p5-viz__ley { display: inline-flex; gap: 6px; align-items: center; }
.p5-viz__ley-banda { width: 14px; height: 10px; border-radius: 2px; background: var(--p5-banda); border: 1px solid color-mix(in srgb, var(--punto-ok) 45%, transparent); }
.p5-viz__ley-linea { width: 14px; height: 0; border-top: 1px solid var(--txt-2); }
.p5-viz__nota { color: var(--txt-2); font-size: .8rem; }
.p5-viz__tabla { max-height: 260px; }
.p5-viz__vista[aria-pressed="true"] { background: var(--acento-bg); border-color: var(--acento); color: var(--acento-fuerte); }

/* ───────── decisiones y órdenes en lenguaje humano ───────── */
.p5-feed { display: grid; gap: 0; }
.p5-feed__item { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--e-3); padding: var(--e-3) 0; border-top: 1px solid var(--borde); align-items: start; }
.p5-feed__item:first-child { border-top: 0; padding-top: 0; }
.p5-feed__icono { display: inline-grid; place-items: center; width: 32px; height: 32px; border-radius: 50%; background: var(--neutro-bg); color: var(--neutro); flex: none; }
.p5-feed__item--ok .p5-feed__icono { background: var(--ok-bg); color: var(--ok); }
.p5-feed__item--info .p5-feed__icono { background: var(--info-bg); color: var(--info); }
.p5-feed__item--aviso .p5-feed__icono { background: var(--aviso-bg); color: var(--aviso); }
.p5-feed__item--error .p5-feed__icono { background: var(--error-bg); color: var(--error); }
.p5-feed__cuerpo { display: grid; gap: 6px; min-width: 0; }
.p5-feed__frase { font-size: 1rem; font-weight: 600; line-height: 1.35; overflow-wrap: anywhere; }
.p5-feed__meta { display: flex; flex-wrap: wrap; gap: 4px var(--e-3); align-items: center; font-size: .82rem; color: var(--txt-2); }
.p5-feed__porque { color: var(--txt-2); font-size: .88rem; overflow-wrap: anywhere; }
.p5-resumen-familias { display: flex; flex-wrap: wrap; gap: var(--e-2); align-items: center; }

/* ───────── margen (P&L) ───────── */
.p5-margen { display: inline-grid; grid-template-columns: minmax(80px, 140px) auto; gap: 8px; align-items: center; min-width: 0; }
.p5-margen__pista { position: relative; display: block; height: 10px; border-radius: 99px; background: var(--sup-3); overflow: hidden; }
.p5-margen__cero { position: absolute; top: 0; bottom: 0; width: 1px; background: var(--borde-fuerte); }
.p5-margen__barra { position: absolute; top: 1px; bottom: 1px; border-radius: 99px; }
.p5-margen__barra--pos { background: var(--p5-serie); }
.p5-margen__barra--neg { background: var(--p5-polo); }
.p5-margen__valor { font-variant-numeric: tabular-nums; font-weight: 650; font-size: .88rem; white-space: nowrap; }

/* ───────── conciliación Stripe ↔ libro ↔ Meta ───────── */
.p5-conc { display: grid; grid-template-columns: minmax(0, 1fr) minmax(150px, auto) minmax(0, 1fr) minmax(150px, auto) minmax(0, 1fr); gap: 0; align-items: stretch; }
.p5-conc__nodo { border: 1px solid var(--borde-fuerte); border-radius: var(--r-3); background: var(--sup); padding: var(--e-3) var(--e-4); display: grid; gap: 2px; align-content: center; min-width: 0; }
.p5-conc__nodo--libro { background: var(--sup-2); }
.p5-conc__nombre { font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; color: var(--txt-2); font-weight: 650; }
.p5-conc__importe { font-size: 1.35rem; font-weight: 700; font-variant-numeric: tabular-nums; overflow-wrap: anywhere; }
.p5-conc__enlace { display: grid; gap: 4px; justify-items: center; align-content: center; padding: 0 var(--e-3); text-align: center; position: relative; min-width: 0; }
.p5-conc__enlace::before { content: ""; position: absolute; left: 0; right: 0; top: 50%; border-top: 2px solid var(--borde-fuerte); z-index: 0; }
.p5-conc__enlace > * { position: relative; z-index: 1; }
.p5-conc__enlace .chip { background-color: var(--sup); }
.p5-conc__diff { font-size: .8rem; font-variant-numeric: tabular-nums; background: var(--sup); padding: 0 4px; }
.p5-conc__causas { display: grid; gap: var(--e-2); margin-top: var(--e-3); }

/* ───────── P&L, libro mayor y costos ───────── */
.p5-pnl-fila--consolidado td { font-weight: 650; background: var(--sup-2); }
.p5-num { font-variant-numeric: tabular-nums; white-space: nowrap; }
.texto-salida { color: var(--txt); }
.p5-totales { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: var(--e-3); }
.p5-total { display: grid; gap: 1px; padding: var(--e-2) var(--e-3); border: 1px solid var(--borde); border-radius: var(--r-2); background: var(--sup-2); }
.p5-total__etiqueta { font-size: .74rem; text-transform: uppercase; letter-spacing: .05em; color: var(--txt-2); font-weight: 650; }
.p5-total__valor { font-size: 1.15rem; font-weight: 700; font-variant-numeric: tabular-nums; }
.p5-filtros { display: flex; flex-wrap: wrap; gap: var(--e-2) var(--e-3); align-items: center; padding: var(--e-2) var(--e-3); background: var(--sup-2); border: 1px solid var(--borde); border-radius: var(--r-2); }
.p5-filtros__etiqueta { display: inline-flex; gap: 6px; align-items: center; color: var(--txt-2); font-size: .82rem; font-weight: 650; }
.p5-costo { display: grid; gap: 4px; min-width: 150px; }

/* ───────── agentes ───────── */
.p5-ranking { display: grid; gap: 6px; }
.p5-ranking__fila { display: grid; grid-template-columns: minmax(90px, 36%) minmax(0, 1fr) auto; gap: var(--e-3); align-items: center; font-size: .88rem; }
.p5-ranking__nombre { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.p5-ranking__pista { display: block; height: 14px; border-radius: 0 4px 4px 0; }
.p5-ranking__barra { display: block; height: 100%; background: var(--p5-serie); border-radius: 0 4px 4px 0; }
.p5-ranking__valor { font-variant-numeric: tabular-nums; font-weight: 650; text-align: right; min-width: 56px; }
.p5-mini { display: inline-grid; gap: 2px; min-width: 130px; }
.p5-ejecs { display: grid; gap: 0; }
.p5-linea-tiempo { display: grid; gap: 0; border-left: 2px solid var(--borde-fuerte); margin-left: 6px; }
.p5-evento { position: relative; padding: 6px 0 10px var(--e-4); display: grid; gap: 3px; min-width: 0; }
.p5-evento::before { content: ""; position: absolute; left: -7px; top: 12px; width: 12px; height: 12px; border-radius: 50%; background: var(--sup); border: 2px solid var(--borde-fuerte); }
.p5-evento--ok::before { border-color: var(--punto-ok); }
.p5-evento--error::before { border-color: var(--punto-error); background: var(--error-bg); }
.p5-evento--aviso::before { border-color: var(--punto-aviso); }
.p5-evento__cab { display: flex; flex-wrap: wrap; gap: 4px 10px; align-items: center; }
.p5-evento__texto { color: var(--txt); overflow-wrap: anywhere; font-size: .9rem; }
.p5-rondas { display: inline-flex; gap: 3px; align-items: center; }
.p5-ronda { width: 9px; height: 9px; border-radius: 50%; background: var(--p5-serie, var(--serie-1)); }
.p5-ronda--vacia { background: transparent; border: 1.5px solid var(--borde-fuerte); }
.p5-checks { display: grid; gap: var(--e-1); }
.p5-detalle { border: 1px solid var(--borde); border-radius: var(--r-3); padding: var(--e-3) var(--e-4); background: var(--sup); display: grid; gap: var(--e-3); min-width: 0; }
.p5-detalle--acento { border-color: var(--acento); }

/* ───────── cumplimiento ───────── */
.p5-dict-grupo { display: grid; gap: var(--e-3); }
.p5-dict-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--e-3); align-items: start; }
.p5-dict { background: var(--sup); border: 1px solid var(--borde); border-top: 4px solid var(--borde-fuerte); border-radius: var(--r-3); padding: var(--e-3) var(--e-4); display: grid; gap: var(--e-3); min-width: 0; align-content: start; box-shadow: var(--sombra); }
.p5-dict--ok { border-top-color: var(--punto-ok); }
.p5-dict--aviso { border-top-color: var(--punto-aviso); }
.p5-dict--error { border-top-color: var(--punto-error); }
.p5-dict__cab { display: flex; justify-content: space-between; gap: var(--e-2); align-items: flex-start; }
.p5-dict__etapa { display: grid; gap: 0; min-width: 0; }
.p5-dict__nombre { font-weight: 650; font-size: 1rem; }
.p5-dict__codigo { font-size: .76rem; color: var(--txt-2); font-family: var(--mono); }
.p5-dict__veredicto { display: flex; gap: 6px; flex-wrap: wrap; align-items: center; justify-content: flex-end; }
.p5-puntaje { display: grid; gap: 4px; }
.p5-puntaje__cab { display: flex; justify-content: space-between; gap: var(--e-2); font-size: .84rem; color: var(--txt-2); }
.p5-puntaje__cab strong { color: var(--txt); font-variant-numeric: tabular-nums; font-size: 1rem; }
.p5-hallazgos-resumen { display: flex; flex-wrap: wrap; gap: var(--e-2); }
.p5-lista-hallazgos { display: grid; gap: var(--e-2); }
.p5-hallazgo { border: 1px solid var(--borde); border-left-width: 3px; border-radius: var(--r-2); padding: var(--e-2) var(--e-3); display: grid; gap: 3px; background: var(--sup); min-width: 0; }
.p5-hallazgo--error { border-left-color: var(--punto-error); }
.p5-hallazgo--aviso { border-left-color: var(--punto-aviso); }
.p5-hallazgo--info { border-left-color: var(--acento); }
.p5-hallazgo--ok { border-left-color: var(--punto-ok); }
.p5-cita { font-family: var(--mono); font-size: .82rem; background: var(--sup-2); border: 1px solid var(--borde); border-radius: var(--r-1); padding: 3px 6px; overflow-wrap: anywhere; white-space: pre-wrap; }
.p5-sellos { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: var(--e-3); }
.p5-sello { background: var(--sup); border: 1px solid var(--borde); border-left: 5px solid var(--borde-fuerte); border-radius: var(--r-3); padding: var(--e-3) var(--e-4); display: grid; gap: var(--e-2); min-width: 0; }
.p5-sello--ok { border-left-color: var(--punto-ok); }
.p5-sello--aviso { border-left-color: var(--punto-aviso); }
.p5-sello--error { border-left-color: var(--punto-error); }
.p5-sello__cab { display: flex; justify-content: space-between; gap: var(--e-2); align-items: center; flex-wrap: wrap; }

.p5-expand { border-top: 1px solid var(--borde); padding-top: var(--e-2); }
.p5-expand__cab { cursor: pointer; display: flex; gap: 6px; align-items: center; font-weight: 600; font-size: .88rem; list-style: none; border-radius: var(--r-1); padding: 2px 0; }
.p5-expand__cab::-webkit-details-marker { display: none; }
.p5-expand__chev { transition: transform .15s ease; flex: none; }
.p5-expand[open] .p5-expand__chev { transform: rotate(90deg); }
.p5-expand > :not(summary) { margin-top: var(--e-3); }

/* ───────── parámetros y límites ───────── */
.p5-op-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: var(--e-3); }
.p5-op { border: 1px solid var(--borde); border-radius: var(--r-3); padding: var(--e-3) var(--e-4); display: grid; gap: var(--e-2); background: var(--sup); min-width: 0; align-content: start; box-shadow: var(--sombra); }
.p5-op--ok { border-color: var(--ok-borde); background: var(--ok-bg); }
.p5-op__cab { display: flex; justify-content: space-between; gap: var(--e-2); align-items: flex-start; }
.p5-op__nombre { font-weight: 650; min-width: 0; flex: 1 1 auto; }
.p5-op__cab > .chip { flex: none; white-space: nowrap; }   /* el título largo se parte en líneas; la etiqueta «Faltan N» nunca se recorta */
.p5-op__faltan { display: flex; flex-wrap: wrap; gap: 2px var(--e-4); font-size: .86rem; color: var(--txt); }
.p5-faltan { font-family: var(--mono); font-size: .78rem; color: var(--txt-2); overflow-wrap: anywhere; }
.p5-prioridad { display: grid; gap: 0; }
.p5-prioridad__fila { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1.6fr) auto; gap: var(--e-3); align-items: center; padding: var(--e-2) 0; border-top: 1px solid var(--borde); }
.p5-prioridad__fila:first-child { border-top: 0; }
.p5-prioridad__nombre { display: grid; gap: 0; min-width: 0; }
.p5-lim-clave { font-family: var(--mono); font-size: .78rem; color: var(--txt-3); overflow-wrap: anywhere; }
.p5-lim-grupo { display: grid; gap: 0; }
.p5-lim { display: grid; grid-template-columns: minmax(0, 1.1fr) minmax(0, 1.5fr) minmax(0, 1fr); gap: var(--e-2) var(--e-4); padding: var(--e-2) var(--e-3); border-top: 1px solid var(--borde); align-items: start; }
.p5-lim:first-child { border-top: 0; }
.p5-lim--nulo { background: color-mix(in srgb, var(--aviso-bg) 55%, transparent); box-shadow: inset 3px 0 0 var(--punto-aviso); }
.p5-lim__nombre { display: grid; gap: 0; min-width: 0; font-weight: 600; }
.p5-lim__valor { display: flex; flex-wrap: wrap; gap: 4px 8px; align-items: center; min-width: 0; overflow-wrap: anywhere; }
.p5-lim__ayuda { color: var(--txt-2); font-size: .86rem; grid-column: 1 / -1; }
.p5-niveles { display: flex; gap: var(--e-2); flex-wrap: wrap; align-items: center; }
.p5-aut-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: var(--e-2); }
.p5-aut { border: 1px solid var(--borde); border-radius: var(--r-2); padding: var(--e-2) var(--e-3); background: var(--sup); display: grid; gap: 2px; min-width: 0; }
.p5-aut__cab { display: flex; justify-content: space-between; gap: var(--e-2); align-items: center; }
.p5-aut__etapa { font-family: var(--mono); font-size: .78rem; color: var(--txt-2); font-weight: 700; }
.p5-resalta { background: var(--aviso-bg); border-radius: 2px; }

.tabla tr.fila-grave td { background: var(--grave-bg) !important; }
.tabla td.p5-cifra { white-space: normal; overflow-wrap: anywhere; line-height: 1.25; padding-top: 4px; padding-bottom: 4px; min-width: 92px; }

@media (max-width: 1100px) {
  .p5-vered__rejilla { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .p5-conc { grid-template-columns: minmax(0, 1fr); gap: var(--e-2); }
  .p5-conc__enlace { padding: var(--e-1) 0; }
  .p5-conc__enlace::before { left: 50%; right: auto; top: 0; bottom: 0; border-top: 0; border-left: 2px solid var(--borde-fuerte); }
}
@media (max-width: 899px) {
  .p5-vered { padding: var(--e-4); }
  .p5-vered__rejilla { grid-template-columns: minmax(0, 1fr); }
  .p5-vered__estado { font-size: 1.5rem; }
  .p5-lim { grid-template-columns: minmax(0, 1fr); }
  .p5-prioridad__fila { grid-template-columns: minmax(0, 1fr); gap: var(--e-1); }
  .p5-graficos, .p5-graficos--2 { grid-template-columns: minmax(0, 1fr); }
  .p5-metricas { grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); }
  .p5-margen { grid-template-columns: minmax(60px, 100px) auto; }
  .p5-dict-grid, .p5-sellos, .p5-op-grid { grid-template-columns: minmax(0, 1fr); }
  .p5-viz__tip { max-width: 200px; }
}
`;
