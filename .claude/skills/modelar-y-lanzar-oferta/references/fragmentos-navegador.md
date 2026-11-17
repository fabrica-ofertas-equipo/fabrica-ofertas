# Fragmentos de JavaScript para el navegador integrado

Probados en la corrida de México (2026-11-10/11) con `mcp__Claude_Browser__javascript_tool`. Son para leer y medir páginas y para pasar archivos al panel de Impultienda; no para cambiar el diseño de nada.

## Índice
1. Medir el orden de los bloques de una sección (referente y nuestra landing)
2. Hoja de contacto de un video (Biblioteca de Anuncios)
3. Pasar un archivo local a un `input[type=file]` (Impultienda)
4. Poner el HTML de la landing en el editor de Impultienda y comprobar la huella
5. Leer interruptores del panel de Impultienda
6. Leer las tarjetas de una búsqueda de la Biblioteca de Anuncios (barrido por forma de funnel)
7. Leer las estadísticas, el neto y los carritos de una tienda (revisión del funnel)
8. Medir una oferta y leer sus anuncios en la Biblioteca (seguimiento e iteraciones)
9. Comparar los videos de los anuncios de una oferta (familias por video y hoja de contacto)

## 1. Medir el orden de los bloques

Emular móvil antes (`resize_window` preset `mobile`) y volver a `desktop` al terminar. Devuelve cada elemento con su posición vertical, alto y texto: así se compara el orden real, no el que uno cree recordar.

```js
await new Promise(r => setTimeout(r, 2000)); scrollTo(0, 0);
const sec = document.querySelector('h1').closest('section') || document.querySelector('h1').parentElement.parentElement;
const walk = (e, d) => { let o = []; for (const c of e.children) { const r = c.getBoundingClientRect(); if (r.height < 4) continue;
  o.push(' '.repeat(d) + c.tagName + '.' + (c.className || '').toString().slice(0, 30) + ' y' + Math.round(r.top + scrollY) + ' h' + Math.round(r.height) + ' | ' + (c.children.length ? '' : (c.innerText || '').replace(/\s+/g, ' ').slice(0, 80)));
  if (d < 3) o = o.concat(walk(c, d + 1)); } return o; };
walk(sec, 0).join('\n') + '\nscrollW ' + document.documentElement.scrollWidth
```

Para la página entera (títulos, videos, imágenes, botones, precios):

```js
const out = []; for (const e of document.querySelectorAll('h1,h2,h3,video,iframe,img,a,button,[class*=price],[class*=timer],[class*=countdown]')) {
  const r = e.getBoundingClientRect(); if (r.width < 40 || r.height < 12) continue;
  const d = e.tagName === 'IMG' ? (e.alt || '') : (e.tagName === 'VIDEO' || e.tagName === 'IFRAME') ? (e.src || e.currentSrc || '').slice(0, 80) : (e.innerText || '').replace(/\s+/g, ' ').slice(0, 90);
  out.push(Math.round(r.top + scrollY) + ' ' + e.tagName + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' ' + d); }
out.sort((a, b) => parseInt(a) - parseInt(b)).join('\n')
```

`scrollW` mayor que el ancho del visor significa desborde horizontal en móvil: hay que arreglarlo antes de publicar.

## 2. Hoja de contacto de un video

En la ficha del anuncio (`facebook.com/ads/library/?id=<ID>`), con el visor emulado a 1600×1000. Hace `seek` del `<video>` y lo dibuja en un lienzo encima de la página; después se toma una captura. No descarga nada. Devuelve la duración exacta.

```js
window.__hoja = async (n = 12, cols = 6, w = 266) => { const v = document.querySelector('video'); v.muted = true; v.pause();
  if (!(v.duration > 0)) { v.load(); await new Promise(r => v.addEventListener('loadedmetadata', r, {once: true})); }
  const paso = (v.duration - 1) / (n - 1); const ts = []; for (let i = 0; i < n; i++) ts.push(0.6 + i * paso);
  const h = Math.round(w * v.videoHeight / v.videoWidth); const c = document.createElement('canvas');
  c.width = cols * w; c.height = Math.ceil(ts.length / cols) * h; c.id = 'hoja-contacto';
  c.style = 'position:fixed;left:0;top:0;z-index:2147483647;background:#000'; const x = c.getContext('2d');
  for (let i = 0; i < ts.length; i++) { v.currentTime = ts[i];
    await new Promise(r => { const f = () => r(); v.addEventListener('seeked', f, {once: true}); setTimeout(f, 2500); });
    await new Promise(r => setTimeout(r, 200)); const X = (i % cols) * w, Y = Math.floor(i / cols) * h;
    x.drawImage(v, X, Y, w, h); x.fillStyle = '#000'; x.fillRect(X, Y, 58, 22); x.fillStyle = '#ff0';
    x.font = 'bold 15px sans-serif'; x.fillText(ts[i].toFixed(0) + ' s', X + 5, Y + 16); }
  document.getElementById('hoja-contacto')?.remove(); document.body.appendChild(c); return {dur: v.duration}; };
await window.__hoja()
```

Para videos de más de un minuto, subir `n` (un cuadro cada 3-5 s). El «zoom» del navegador recorta en vez de ampliar: si los subtítulos no se leen, usar miniaturas más anchas (`w`) y menos columnas.

### 2.1 Variante para muchos videos, sin salir de la lista de la Biblioteca (`__hoja3`)

En la página del anunciante (`…/ads/library/?active_status=active&ad_type=all&country=ALL&media_type=video&search_type=page&view_all_page_id=<id>`), visor a 1600×1000. `__lista()` devuelve las tarjetas cargadas; `__vid(id)` encuentra el `<video>` de una tarjeta; `__hoja3(id, etiqueta)` pinta un cuadro grande a los 2 s (para leer el gancho) y 18 cuadros repartidos. Una captura por video; las capturas salen a 800 px de ancho, por eso el cuadro grande.

```js
window.__lista = () => document.body.innerText.split('Identificador de la biblioteca: ').slice(1).map(p => ({
  id: (p.match(/^(\d+)/)||[])[1], f: (p.match(/En circulación desde el ([^\n]+)/)||[])[1],
  dom: (p.match(/\n([A-Z0-9.-]+\.(?:ONLINE|PRO|COM|STORE|SHOP|SITE|CO|NET|ORG))\n/)||[])[1] }));
window.__vid = (id) => { for (const v of document.querySelectorAll('video')) { let e = v;
  for (let k = 0; k < 25 && e; k++) { e = e.parentElement; if (!e) break;
    const m = (e.innerText||'').match(/Identificador de la biblioteca: (\d+)/); if (m) { if (m[1] === id) return v; break; } } } return null; };
window.__hoja3 = async (id, etiqueta = '') => { const v = window.__vid(id); if (!v) return 'sin video ' + id;
  v.scrollIntoView({block: 'center'}); v.muted = true; try { v.pause() } catch (e) {}
  if (!(v.duration > 0)) { v.preload = 'auto'; v.load(); await new Promise(r => { v.addEventListener('loadedmetadata', r, {once: true}); setTimeout(r, 8000) }); }
  const d = v.duration, c = document.createElement('canvas'); c.width = 1600; c.height = 1000; c.id = 'hoja-contacto';
  c.style = 'position:fixed;left:0;top:0;z-index:2147483647;background:#111'; const x = c.getContext('2d'); x.fillRect(0, 0, 1600, 1000);
  const ir = async t => { v.currentTime = t; await new Promise(r => { const f = () => r(); v.addEventListener('seeked', f, {once: true}); setTimeout(f, 3000) }); await new Promise(r => setTimeout(r, 250)); };
  await ir(2.0); x.drawImage(v, 0, 40, 506, 900); const n = 18, cols = 6, w = 182, h = 324, x0 = 508, paso = (d - 1) / (n - 1);
  for (let i = 0; i < n; i++) { const t = 0.6 + i * paso; await ir(t); const X = x0 + (i % cols) * w, Y = Math.floor(i / cols) * h;
    x.drawImage(v, X, Y, w, h); x.fillStyle = '#000'; x.fillRect(X, Y, 70, 30); x.fillStyle = '#ff0'; x.font = 'bold 24px sans-serif'; x.fillText(t.toFixed(0) + 's', X + 5, Y + 23); }
  x.fillStyle = '#000'; x.fillRect(0, 0, 506, 40); x.fillStyle = '#0f0'; x.font = 'bold 24px sans-serif'; x.fillText(etiqueta + ' · ' + d.toFixed(1) + ' s', 6, 28);
  document.getElementById('hoja-contacto')?.remove(); document.body.appendChild(c); return {id, dur: +d.toFixed(1)}; };
```

Si la captura sale con la hoja anterior, esperar 1 s y volver a capturar. Al terminar: quitar el lienzo y devolver el visor a `desktop`.

## 3. Pasar un archivo local a un `input[type=file]`

El panel no lee archivos locales ni `127.0.0.1`, y pegar con el teclado no llega. Camino que funciona:

1. `python3 05-landing/assets/pasar.py subir <archivo>` → crea uno o más gists SECRETOS con el archivo en base64 (trozos de 3 MB) y anota los ID en `publicar/pasados.json`.
2. En la página, traer el base64, armar un `File` y entregarlo al `input`. Si el `input` solo aparece al pulsar un botón («Subir imagen»), interceptar el clic:

```js
window.__fi = []; const orig = HTMLInputElement.prototype.click;
HTMLInputElement.prototype.click = function () { if (this.type === 'file') { window.__fi.push(this); return; } return orig.call(this); };
[...document.querySelectorAll('button')].find(x => x.innerText.trim() === 'Subir imagen').click();
await new Promise(r => setTimeout(r, 500));
const todos = [...document.querySelectorAll('input[type=file]')];
const inp = window.__fi[0] || todos.find(i => /image/.test(i.accept)) || todos[0];
const r = await fetch('https://gist.githubusercontent.com/<USUARIO>/<ID>/raw/t.b64');
const bin = atob((await r.text()).trim()); const u = new Uint8Array(bin.length); for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
const dt = new DataTransfer(); dt.items.add(new File([u], '<nombre>.jpg', {type: 'image/jpeg'}));
inp.files = dt.files; inp.dispatchEvent(new Event('change', {bubbles: true})); inp.dispatchEvent(new Event('input', {bubbles: true}));
HTMLInputElement.prototype.click = orig; ({accept: inp.accept, puesto: true})
```

   Archivos de más de 3 MB: traer cada trozo en orden, concatenar los textos base64 y decodificar al final.
3. Guardar en esa pantalla del panel y comprobar que el recurso aparece (las imágenes pasan a `.webp`).
4. `python3 05-landing/assets/pasar.py borrar` → borra todos los gists anotados. Hacerlo siempre, también cuando el paso falla o se queda bloqueado: un gist secreto sigue siendo accesible para quien tenga el enlace.

## 4. Poner el HTML de la landing y comprobar la huella

En `impultienda.ar/dashboard/<tienda>/personalizacion/diseno/contenido`. Primero leer lo que hay, porque puede no ser lo que hay en disco:

```js
const sha = async s => [...new Uint8Array(await crypto.subtle.digest('SHA-1', new TextEncoder().encode(s)))].map(b => b.toString(16).padStart(2, '0')).join('');
const ta = [...document.querySelectorAll('textarea')].find(t => t.value.length > 500);
({largo: ta.value.length, sha: await sha(ta.value)})
```

Comparar con `shasum 05-landing/publicar/landing.html`. Si la huella no coincide con ningún archivo local conocido, alguien cambió la página fuera de estos archivos: guardar copia de lo publicado, decir al dueño qué se perdería y no pisar en silencio.

Poner el valor nuevo (traído del gist, como en el punto 3):

```js
const html = new TextDecoder('utf-8').decode(u);
const set = Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set;
set.call(ta, html); ta.dispatchEvent(new Event('input', {bubbles: true})); ta.dispatchEvent(new Event('change', {bubbles: true}));
({ahora: ta.value.length, sha: await sha(ta.value), acentos: ta.value.includes('í')})
```

La huella del `textarea` tiene que ser igual a la del archivo local antes de pulsar «Guardar cambios». Después, abrir la tienda pública en móvil y medir con el fragmento 1.

## 5. Leer interruptores del panel

Los interruptores son `span.rounded-full`; encendido lleva `bg-primary-500`, apagado `bg-gray-200`. Leer el estado antes de tocar: un clic a ciegas puede apagar algo que el dueño encendió.

## 6. Leer las tarjetas de una búsqueda de la Biblioteca (barrido por forma)

Para `01-elegir-oferta-y-mercado.md` §1.5. URL de búsqueda (los imprime `barrido_por_forma.py terminos`; usar `web.facebook.com`, que es donde termina cargando):

```
https://web.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&media_type=all&q=%22inlead.digital%22&search_type=keyword_exact_phrase&start_date[max]=AAAA-MM-DD
```

`search_type=keyword_exact_phrase` para frase exacta o dominio; `keyword_unordered` para palabras sueltas (`quiz ebook`). `start_date[max]` = hoy menos 10 días al buscar; sin ese parámetro al medir una oferta por su dominio.

Cargar más tarjetas: una rueda del ratón real (`computer` → `scroll`) y dos o tres `window.scrollTo(0, document.body.scrollHeight)` con 2.5 s entre cada uno. Con ~4 desplazamientos se leen 80-140 tarjetas, ordenadas por impresiones.

Agrupar por página y destino (devuelve total declarado, tarjetas leídas y grupos con anuncios, antigüedad máxima vista e identificador de una ficha):

```js
(() => {
  const meses = {ene:0,feb:1,mar:2,abr:3,may:4,jun:5,jul:6,ago:7,sept:8,sep:8,oct:9,nov:10,dic:11};
  const hoy = new Date();
  const dias = s => { const m = (s||'').match(/(\d+) (\w+) (\d{4})/); return m ? Math.round((hoy - new Date(+m[3], meses[m[2]], +m[1]))/864e5) : null; };
  const ids = [...document.querySelectorAll('span,div')].filter(e => e.childElementCount===0 && /^Identificador de la biblioteca: \d+/.test(e.textContent.trim()));
  const grupos = new Map();
  for (const s of ids) {
    let card = s;
    for (let i=0; i<12 && card.parentElement; i++) { card = card.parentElement; if (card.querySelector('a[href*="l.php?u="]') && /Publicidad/.test(card.innerText)) break; }
    const t = card.innerText;
    const desde = (t.match(/En circulación desde el ([^\n]+)/)||[])[1];
    const usan = +((t.match(/(\d+) anuncios usan este contenido/)||[])[1] || 1);
    const pag = [...card.querySelectorAll('a[href*="facebook.com/"]')].find(a => a.innerText.trim() && !/l\.php|ads\/library/.test(a.href));
    let destino = null;
    for (const a of card.querySelectorAll('a[href]')) { try { const u = new URL(a.href); if (u.hostname.startsWith('l.') && u.searchParams.get('u')) { destino = u.searchParams.get('u').split('?')[0]; break; } } catch (e) {} }
    if (!destino) continue;
    const clave = (pag ? pag.innerText.trim() : '?') + ' | ' + destino;
    const g = grupos.get(clave) || {pagina: pag ? pag.innerText.trim() : '?', pagina_url: pag ? pag.href.split('?')[0] : null, destino, tarjetas: 0, anuncios: 0, max_dias: 0, ficha: s.textContent.match(/\d+/)[0]};
    g.tarjetas++; g.anuncios += usan; g.max_dias = Math.max(g.max_dias, dias(desde) || 0);
    grupos.set(clave, g);
  }
  return {total: (document.body.innerText.match(/~?([\d.,]+)\s+resultados?/)||[])[1], tarjetas: ids.length, grupos: [...grupos.values()].sort((a,b) => b.anuncios - a.anuncios)};
})()
```

Notas:
- El texto es el de la interfaz en español («Identificador de la biblioteca», «En circulación desde el», «Publicidad»). Con la interfaz en otro idioma hay que cambiar esas tres cadenas y los meses.
- `anuncios` suma «N anuncios usan este contenido»; el total de la oferta es el `total` de la búsqueda por dominio, no esa suma (solo cubre las tarjetas leídas).
- `pagina_url` trae un número largo para las páginas nuevas (que no siempre coincide con el `page_id` de la Biblioteca) o el alias. El `page_id` se confirma con el conector.
- `sessionStorage` y `window.name` sobreviven a la navegación dentro de la pestaña y sirven para no reenviar el fragmento; `localStorage` en Facebook se pierde.
- Recorrer un quiz: clic en la primera opción de cada pantalla y anotar titular, si hay video, campo de correo o precio. Parar si pide correo o teléfono, o si continuar implica aceptar términos. Los campos numéricos (edad, altura) de algunos quiz no aceptan valores puestos por script.


## 7. Leer las estadísticas, el neto y los carritos de una tienda (revisión del funnel)

Probado el 2026-11-12 en la pestaña del panel (`impultienda.ar/dashboard/...`). Navega dentro de la aplicación sin recargar. El selector de período es un botón con el texto del período actual («30 días», «Hoy»…).

```js
window.__stats = async (slug, rango) => {            // rango: 'Hoy' | 'Ayer' | '7 días' | '30 días'
  history.pushState({}, '', '/dashboard/' + slug + '/estadisticas'); window.dispatchEvent(new PopStateEvent('popstate'));
  await new Promise(r => setTimeout(r, 5000));
  const b = [...document.querySelectorAll('button')].find(b => /^(30 días|Hoy|Ayer|7 días|Todo|90 días)$/.test(b.innerText.trim()));
  b.click(); await new Promise(r => setTimeout(r, 700));
  [...document.querySelectorAll('button')].find(x => x.innerText.trim() === rango).click();
  await new Promise(r => setTimeout(r, 4000));
  const t = document.querySelector('main').innerText;
  const g = (k, n) => { const i = t.indexOf(k); return i < 0 ? '' : t.slice(i, i + n).replace(/\n+/g, ' | '); };
  return {slug, rango, kpis: g('Ingresos\n', 120), embudo: g('Embudo de conversión', 220), pagos: g('Métodos de pago', 120)};
};
const ir = async (p) => { history.pushState({}, '', p); window.dispatchEvent(new PopStateEvent('popstate'));
  await new Promise(r => setTimeout(r, 5000)); return document.querySelector('main').innerText.replace(/\n{2,}/g, '\n').slice(0, 2500); };
// Neto por venta (bruto, «comisiones e impuestos», neto): await ir('/dashboard/<slug>/impulpay')  → «Últimos movimientos»
// Carritos abandonados (solo cuentan si el comprador escribió el correo): await ir('/dashboard/<slug>/ventas/carritos-abandonados')
```

- El embudo devuelve «Landing N | Checkout N | x % | Compra N | y %».
- Las tiendas de niveles (básico, completo) dan 0 visitas, porque no tienen landing propia, pero sí checkouts: sumarlos al funnel.
- Impul Pay es una sola cuenta para todas las tiendas: «Últimos movimientos» lista las ventas de todas, con el nombre de la tienda.
- No copiar al informe los correos ni los nombres de los compradores; basta el número de orden.

## 8. Medir una oferta y leer sus anuncios (seguimiento e iteraciones)

Para `01-elegir-oferta-y-mercado.md` §1.6. Mismas búsquedas que §6 (`web.facebook.com`, `country=ALL`, activos), sin fecha tope. Por dominio: `search_type=keyword_exact_phrase&q=%22dominio%22`. Por página: `search_type=page&view_all_page_id=<page_id>`.

Guardar el lector una vez en `sessionStorage` (sobrevive a la navegación dentro de la pestaña) y llamarlo en cada página con `eval(sessionStorage.getItem('__c')); await window.__leer(2)`:

```js
window.__leer = async (scrolls) => {
  const esp = ms => new Promise(r => setTimeout(r, ms));
  await esp(3500);
  for (let i = 0; i < scrolls; i++) { window.scrollTo(0, document.body.scrollHeight); await esp(2600); }
  const meses = {ene:0,feb:1,mar:2,abr:3,may:4,jun:5,jul:6,ago:7,sept:8,sep:8,oct:9,nov:10,dic:11};
  const hoy = new Date(); hoy.setHours(0,0,0,0);
  const dias = s => { const m = (s||'').match(/(\d+) (\w+) (\d{4})/); return m ? Math.round((hoy - new Date(+m[3], meses[m[2]], +m[1]))/864e5) : null; };
  const ids = [...document.querySelectorAll('span,div')].filter(e => e.childElementCount===0 && /^Identificador de la biblioteca: \d+/.test(e.textContent.trim()));
  const tarjetas = [];
  for (const s of ids) {
    let card = s;
    for (let i=0; i<12 && card.parentElement; i++) { card = card.parentElement; if (card.querySelector('a[href*="l.php?u="]') && /Publicidad/.test(card.innerText)) break; }
    const t = card.innerText;
    let ds = null;
    for (const a of card.querySelectorAll('a[href]')) { try { const u = new URL(a.href); if (u.hostname.startsWith('l.') && u.searchParams.get('u')) { ds = u.searchParams.get('u').split('?')[0].replace(/^https?:\/\/(www\.)?/, ''); break; } } catch (e) {} }
    const lineas = t.split('\n').map(x => x.trim()).filter(Boolean);
    let resto = lineas.slice(lineas.indexOf('Publicidad') + 1);
    let seg = null; const iv = resto.findIndex(l => /^0:00 \/ \d+:\d\d$/.test(l));
    if (iv >= 0) { const m = resto[iv].match(/(\d+):(\d\d)$/); seg = (+m[1]*60 + +m[2]) || null; resto.splice(iv, 1); }
    const ic = resto.findIndex(l => /^[A-Z0-9.\-]+\.[A-Z]{2,}(\/\S*)?$/.test(l));        // línea del dominio en mayúsculas
    tarjetas.push({id: s.textContent.match(/\d+/)[0], d: dias((t.match(/En circulación desde el ([^\n]+)/)||[])[1]),
      u: +((t.match(/(\d+) anuncios usan este contenido/)||[])[1] || 1), seg, v: iv >= 0 || !!card.querySelector('video'), ds: (ds||'').slice(0, 70),
      ti: ic >= 0 ? (resto[ic+1]||'').slice(0, 60) : '', tx: (ic >= 0 ? resto.slice(0, ic) : resto.slice(0, 4)).join(' ').slice(0, 170)});
  }
  const p = new URL(location.href).searchParams;
  const q = (p.get('q') || p.get('view_all_page_id') || 'x').replace(/"/g, '');
  const total = (document.body.innerText.match(/~?([\d.,]+)\s+resultados?/)||[])[1] || null;
  try { sessionStorage.setItem('__t_' + q, JSON.stringify({total, tarjetas})); } catch (e) {}
  const ds = tarjetas.map(c => c.d).filter(x => x !== null);
  return `${q} · total ${total} · tarjetas ${tarjetas.length} · más viejo ${Math.max(0, ...ds)} d · iniciados ≤7 d: ${tarjetas.filter(c => c.d !== null && c.d <= 7).length}`;
};
```

- **Seguimiento:** basta `__leer(1)` o `__leer(2)` y anotar `total` (la línea que devuelve). Varias ofertas seguidas en un solo `browser_batch` (navegar + leer por cada una).
- **Iteraciones:** primero una rueda real del ratón (`computer` → `scroll`, tras una captura) y `__leer(3)`; luego `JSON.parse(sessionStorage.getItem('__t_<consulta>'))` da `{total, tarjetas}` con el formato que espera `banco_candidatos.py creativos`. Campos: `id` (ficha), `d` (días activo), `u` (anuncios que repiten el creativo), `seg` (duración del video; nulo si no cargó), `v` (es video), `ds` (destino), `ti` (título), `tx` (comienzo del texto).
- El texto de los anuncios se guarda en archivo con Write, nunca pasándolo por la línea de comandos.
- Una duración `0:00 / 0:00` significa que el video no llegó a cargar, no que sea una imagen.

## 9. Comparar los videos de los anuncios de una oferta

Para `01-elegir-oferta-y-mercado.md` §1.6. El código está en `scripts/biblioteca_videos.js` (se pega entero con `javascript_tool`; la cabecera del archivo trae el orden de las llamadas). Corre en la pestaña de la Biblioteca, sobre la búsqueda por dominio de la oferta o la página del anunciante.

Lo que hay que saber:

- **Los píxeles del video se pueden leer** si el `<video>` se crea aparte con `crossOrigin = 'anonymous'` y la misma `src` de la tarjeta. Con el `<video>` de la propia tarjeta el lienzo queda bloqueado (`SecurityError`).
- `__huellas(70)` corre de fondo (no esperar con `await`: `javascript_tool` corta a los 45 s). Consultar `window.__H.estado` hasta que diga `listo`. Unos 30 s para 40 videos.
- `JSON.stringify(window.__salida())` da `{familias, relaciones}` con el formato de `banco_candidatos.py videos`. Son solo identificadores y números: se puede guardar directo.
- `await window.__hoja(0, 14)` dibuja encima de la página una hoja con 14 familias (fotograma a los 2 s y a mitad del video) y entonces se toma la captura. Con más familias, `__hoja(14, 14)`. Para ver todos los arranques de una familia: `window.__F = window.__F[0].map(id => [id])` antes. Al terminar, `document.getElementById('__hoja').remove()`.
- Tras ver las hojas, añadir a mano al JSON: `formatos` (letra → descripción), `formato_por_familia` (número → letra) y `lectura`.
- Las huellas se alinean desde el final: por eso dos videos con el mismo cuerpo y distinto arranque coinciden aunque duren distinto.
- No oye el audio. No descarga ni guarda los videos.

