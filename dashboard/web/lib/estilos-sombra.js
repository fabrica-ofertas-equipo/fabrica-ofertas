// lib/estilos-sombra.js — estilos de «Robots en sombra» (pantalla Robots). Prefijo `rs-`. Solo datos (cadenas CSS): la página los instala con `ui.instalarEstilos(id, css)`
// (hoja construida por CSSOM; la CSP del panel no admite <style> ni style="" en línea). Solo tokens del sistema; todo estado lleva icono y palabra, el color nunca va solo.

export const CSS_SOMBRA = `
.rs-titular { display: grid; grid-template-columns: auto minmax(0, 1fr); gap: var(--e-4, 16px); align-items: start; padding: var(--e-4, 16px); background: var(--sup); border: 1px solid var(--borde); border-left-width: 5px; border-radius: var(--r-3, 12px); box-shadow: var(--sombra); min-width: 0; }
.rs-titular[data-situacion="corriendo"] { border-left-color: var(--info); }
.rs-titular[data-situacion="vencido"] { border-left-color: var(--punto-aviso); }
.rs-titular[data-situacion="sin_programar"] { border-left-style: dashed; border-left-color: var(--borde-fuerte); }
.rs-titular__icono { width: 40px; height: 40px; border-radius: 50%; display: grid; place-items: center; background: var(--sup-3); color: var(--txt-2); }
.rs-titular[data-situacion="corriendo"] .rs-titular__icono { background: var(--info-bg); color: var(--info); }
.rs-titular[data-situacion="vencido"] .rs-titular__icono { background: var(--aviso-bg); color: var(--aviso); }
.rs-titular__cuerpo { display: grid; gap: 6px; min-width: 0; }
.rs-titular__titulo { margin: 0; font-size: 1.15rem; font-weight: 700; line-height: 1.25; overflow-wrap: anywhere; }
.rs-titular__texto { margin: 0; color: var(--txt-2); line-height: 1.5; max-width: 76ch; overflow-wrap: anywhere; }
.rs-cuentas { display: flex; flex-wrap: wrap; gap: 6px 8px; margin-top: 2px; }
.rs-apoyo { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--e-2, 8px); grid-template-columns: repeat(auto-fit, minmax(min(100%, 320px), 1fr)); }
.rs-apoyo > li { display: grid; gap: 6px; padding: 12px 14px; background: var(--sup); border: 1px solid var(--borde); border-radius: var(--r-2, 8px); min-width: 0; }
.rs-apoyo b { font-size: 14.5px; }
.rs-apoyo p { margin: 0; font-size: 13.5px; line-height: 1.45; color: var(--txt-2); overflow-wrap: anywhere; }
.rs-estado { display: grid; gap: 6px; margin-top: 4px; }
.rs-estado__fila { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.rs-estado__razon { margin: 0; font-size: 12.5px; line-height: 1.4; color: var(--txt-2); overflow-wrap: anywhere; }
.rs-estado__hora { font-size: 12.5px; color: var(--txt-3); }
.rs-comandos { display: grid; gap: var(--e-2, 8px); }
@media (max-width: 560px) { .rs-titular { grid-template-columns: minmax(0, 1fr); } }
`;
