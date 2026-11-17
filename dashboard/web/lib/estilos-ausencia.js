// lib/estilos-ausencia.js — estilos del bloque «¿Me puedo ausentar?» (Resumen), de las alertas con filtros y del informe de las 08:30 (Avisos). Prefijo `au-`.
// Solo datos (cadenas CSS): cada página los instala con `ui.instalarEstilos(id, css)` (hoja construida por CSSOM; la CSP del panel no admite <style> ni style="" en línea).
// Solo usa los tokens del sistema (claro/oscuro): el color significa estado y SIEMPRE va con icono y palabra.

export const CSS_AUSENCIA = `
.au-bloque { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--e-5, 24px); align-items: center; padding: var(--e-5, 24px); background: var(--sup); border: 1px solid var(--borde); border-left-width: 6px; border-radius: var(--r-3, 12px); box-shadow: var(--sombra); min-width: 0; }
.au-bloque[data-nivel="rojo"] { border-left-color: var(--punto-error); }
.au-bloque[data-nivel="amarillo"] { border-left-color: var(--punto-aviso); }
.au-bloque[data-nivel="verde"] { border-left-color: var(--punto-ok); }
.au-luces { display: flex; flex-direction: column; gap: 8px; padding: 10px; background: var(--sup-3); border: 1px solid var(--borde-fuerte); border-radius: 999px; }
.au-luz { width: 44px; height: 44px; border-radius: 50%; display: grid; place-items: center; border: 2px solid var(--borde-fuerte); color: var(--txt-3); opacity: .45; }
.au-luz[data-encendida="1"] { opacity: 1; color: #fff; border-color: transparent; }
.au-luz[data-nivel="rojo"][data-encendida="1"] { background: var(--critico-solido); }
.au-luz[data-nivel="amarillo"][data-encendida="1"] { background: var(--punto-aviso); color: #231600; }
.au-luz[data-nivel="verde"][data-encendida="1"] { background: var(--punto-ok); color: #031403; }
.au-cabeza { display: grid; gap: var(--e-2, 8px); min-width: 0; }
.au-sobre { margin: 0; font-size: .78rem; font-weight: 650; letter-spacing: .06em; text-transform: uppercase; color: var(--txt-3); }
.au-veredicto { margin: 0; font-size: var(--t-xl, 1.7rem); line-height: 1.15; font-weight: 700; color: var(--txt); overflow-wrap: anywhere; }
.au-bloque[data-nivel="rojo"] .au-veredicto { color: var(--error); }
.au-bloque[data-nivel="amarillo"] .au-veredicto { color: var(--aviso); }
.au-bloque[data-nivel="verde"] .au-veredicto { color: var(--ok); }
.au-resumen { margin: 0; color: var(--txt-2); line-height: 1.5; max-width: 72ch; overflow-wrap: anywhere; }
.au-cuentas { display: flex; flex-wrap: wrap; gap: 6px 10px; margin-top: 4px; }
.au-lista-titulo { margin: var(--e-5, 24px) 0 var(--e-3, 12px); font-size: 1rem; font-weight: 650; color: var(--txt); }
.au-pasos { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-3, 12px); }
.au-paso { display: grid; grid-template-columns: 32px minmax(0, 1fr); gap: 6px var(--e-3, 12px); align-items: start; padding: 12px 14px; background: var(--sup); border: 1px solid var(--borde); border-left-width: 4px; border-radius: var(--r-2, 8px); min-width: 0; }
.au-paso[data-nivel="rojo"] { border-left-color: var(--punto-error); }
.au-paso[data-nivel="amarillo"] { border-left-color: var(--punto-aviso); }
.au-paso[data-nivel="verde"] { border-left-color: var(--punto-ok); }
.au-paso__n { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; font-weight: 700; font-size: 13px; background: var(--acento-bg); color: var(--acento-fuerte); font-variant-numeric: tabular-nums; }
.au-paso__cuerpo { display: grid; gap: 6px; min-width: 0; }
.au-paso__cab { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; }
.au-paso__titulo { margin: 0; font-size: 14.5px; font-weight: 650; line-height: 1.35; overflow-wrap: anywhere; }
.au-paso__estado { margin: 0; font-size: 13.5px; line-height: 1.45; color: var(--txt-2); overflow-wrap: anywhere; }
.au-paso__hacer { margin: 0; font-size: 13.5px; line-height: 1.45; color: var(--txt); overflow-wrap: anywhere; }
.au-paso__hacer strong { font-weight: 650; }
.au-paso__nota { margin: 0; font-size: 12.5px; color: var(--txt-3); overflow-wrap: anywhere; }
.au-paso__acciones { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 2px; }
.au-listos { margin-top: var(--e-3, 12px); }
.au-listos ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.au-listos li { display: flex; flex-wrap: wrap; gap: 6px 10px; align-items: center; font-size: 13.5px; color: var(--txt-2); }
.au-pie { margin: var(--e-3, 12px) 0 0; font-size: 12.5px; color: var(--txt-3); line-height: 1.5; max-width: 90ch; overflow-wrap: anywhere; }
.au-filtros { display: flex; flex-wrap: wrap; align-items: center; gap: 8px var(--e-4, 16px); margin-bottom: var(--e-3, 12px); }
.au-filtros__grupo { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 8px; }
.au-filtros__etiqueta { font-size: 12.5px; color: var(--txt-3); }
.au-conteo { margin: 0 0 var(--e-2, 8px); font-size: 13px; color: var(--txt-2); }
.au-alerta-extra { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; margin-top: 6px; }
.au-informe { display: grid; gap: var(--e-4, 16px); min-width: 0; }
.au-texto { margin: 0; padding: 12px 14px; background: var(--sup-2); border: 1px solid var(--borde); border-radius: var(--r-2, 8px); font-family: var(--mono); font-size: 12.5px; line-height: 1.55; white-space: pre-wrap; overflow-wrap: anywhere; max-height: 440px; overflow: auto; color: var(--txt); }
.au-ceros { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.au-cero { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 4px 10px; align-items: start; padding: 10px 12px; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-2, 8px); }
.au-cero__valor { min-width: 2.2ch; text-align: center; font-weight: 700; font-variant-numeric: tabular-nums; color: var(--txt); }
.au-cero p { margin: 0; font-size: 13.5px; line-height: 1.45; color: var(--txt-2); overflow-wrap: anywhere; }
.au-cero strong { color: var(--txt); font-weight: 650; }
.au-secciones { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.au-seccion { padding: 10px 12px; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-2, 8px); display: grid; gap: 4px; }
.au-seccion ul { margin: 0; padding-left: 18px; font-size: 13.5px; line-height: 1.45; color: var(--txt-2); }
.au-pendientes { margin: 0; padding: 0; list-style: none; display: grid; gap: 6px; }
.au-pendientes li { display: grid; gap: 2px; padding: 8px 10px; background: var(--sup-2); border: 1px solid var(--borde); border-radius: var(--r-2, 8px); font-size: 13px; }
.au-pendientes b { font-weight: 650; }
@media (max-width: 640px) {
  .au-bloque { grid-template-columns: minmax(0, 1fr); padding: var(--e-4, 16px); }
  .au-luces { flex-direction: row; justify-self: start; }
  .au-luz { width: 38px; height: 38px; }
  .au-veredicto { font-size: var(--t-lg, 1.4rem); }
}
@media (prefers-reduced-motion: no-preference) { .au-luz { transition: opacity .2s ease; } }
`;
