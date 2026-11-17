// capi_estado.js — en el navegador integrado, con sesión de Impultienda (cualquier página de impultienda.ar/dashboard):
// recorre las tiendas y dice si el campo «Token de CAPI» tiene contenido. NUNCA lee el valor del token: solo su largo > 0.
// Cambiar la lista SLUGS por las tiendas a revisar. Resultado → libro.py set <test> ficha.tiendas.<i>.capi '{"ok": true|false, "revisado": "<fecha>"}'.
(async () => {
  const SLUGS = ['tu-tienda', 'tu-tienda', 'tu-tienda'];
  const esperar = (ms) => new Promise((r) => setTimeout(r, ms));
  const res = {};
  for (const slug of SLUGS) {
    // pasar antes por otra ruta: si ya se estaba en esa tienda, la página no recarga el formulario y el campo se lee vacío (13-nov)
    history.pushState({}, '', `/dashboard/${slug}/markets`);
    window.dispatchEvent(new PopStateEvent('popstate'));
    await esperar(1500);
    history.pushState({}, '', `/dashboard/${slug}/configuracion`);
    window.dispatchEvent(new PopStateEvent('popstate'));
    await esperar(3500);
    const b = [...document.querySelectorAll('button')].find((x) => /Meta \/ Tracking/.test(x.innerText));
    if (b) { b.click(); await esperar(1500); }
    const capi = [...document.querySelectorAll('input')].find((x) => /CAPI/i.test(x.placeholder || ''));
    const px = [...document.querySelectorAll('input')].find((x) => /1234567890123456/.test(x.placeholder || ''));
    res[slug] = { capi: capi ? capi.value.length > 0 : null, pixel: px ? px.value : null };
  }
  return res;
})()
