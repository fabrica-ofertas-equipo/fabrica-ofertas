// Comparar los VIDEOS de los anuncios de una oferta en la Biblioteca de Anuncios (no los textos).
//
// Dónde corre: en la pestaña de la Biblioteca (web.facebook.com, country=ALL, solo activos), en la búsqueda por
// dominio de la oferta o en la página del anunciante. Se pega entero con javascript_tool una vez por pestaña
// (o se guarda en sessionStorage y se hace eval). Solo lectura: no descarga ni envía nada.
//
// Uso, en este orden (cada llamada por separado, porque javascript_tool corta a los 45 s):
//   1. una rueda real del ratón para que carguen más tarjetas (computer → scroll)
//   2. window.__huellas(70)                  // no esperar con await: corre de fondo; tarda ~1 s por video
//   3. window.__H.estado === 'listo'         // consultar hasta que termine
//   4. JSON.stringify(window.__salida())     // → archivo VIDEOS.json para `banco_candidatos.py videos <clave> --archivo`
//   5. await window.__hoja(0, 14)  y captura de pantalla; repetir con (14, 14)… para VER cada familia
//      después: document.getElementById('__hoja').remove()
//
// Qué mide: de cada video, una huella de 64 bits (dHash 9×8 en grises) de 4 fotogramas del arranque
// (0,5 · 2 · 4 · 6 s) y de hasta 16 fotogramas contados DESDE EL FINAL (cada 4 s). Alinear desde el final
// hace que dos videos con el mismo cuerpo y distinto arranque coincidan aunque duren distinto.
// Dos fotogramas son «iguales» si difieren en 10 bits o menos. Un fotograma liso (negro, fundido) no cuenta.
//
// Qué NO mide: el audio. Dos videos de la misma persona en el mismo fondo con guiones distintos pueden parecerse.

const __tarjeta = (s) => {
  let card = s;
  for (let i = 0; i < 12 && card.parentElement; i++) {
    card = card.parentElement;
    if (card.querySelector('a[href*="l.php?u="]') && /Publicidad/.test(card.innerText)) break;
  }
  return card;
};
const __fichas = () => [...document.querySelectorAll('span,div')]
  .filter(e => e.childElementCount === 0 && /^Identificador de la biblioteca: \d+/.test(e.textContent.trim()));
const __esp = ms => new Promise(r => setTimeout(r, ms));
const __abrir = async (src) => {
  const v = document.createElement('video');
  v.crossOrigin = 'anonymous';            // sin esto el lienzo queda «manchado» y no deja leer píxeles
  v.muted = true; v.preload = 'auto'; v.src = src;
  await new Promise((ok, no) => { v.onloadedmetadata = ok; v.onerror = () => no(new Error('carga')); setTimeout(() => no(new Error('tiempo')), 15000); });
  return v;
};
const __ir = async (v, t) => {
  v.currentTime = t;
  await new Promise(ok => { v.onseeked = ok; setTimeout(ok, 10000); });
  await __esp(40);
};

window.__huellas = async (maxVideos) => {
  for (let i = 0; i < 3; i++) { window.scrollTo(0, document.body.scrollHeight); await __esp(2500); }
  const cola = [];
  for (const s of __fichas()) {
    const card = __tarjeta(s);
    let v = card.querySelector('video');
    if (!v || !(v.src || v.currentSrc)) { card.scrollIntoView(); await __esp(700); v = card.querySelector('video'); }
    cola.push({ id: s.textContent.match(/\d+/)[0], src: v ? (v.src || v.currentSrc) : null });
  }
  window.__H = { estado: 'corriendo', total: cola.length, hechos: 0, datos: {}, fallos: [] };
  const c = document.createElement('canvas'); c.width = 9; c.height = 8;
  const x = c.getContext('2d', { willReadFrequently: true });
  const huella = (v) => {
    x.drawImage(v, 0, 0, 9, 8);
    const d = x.getImageData(0, 0, 9, 8).data, g = [];
    for (let i = 0; i < 72; i++) g.push(0.299 * d[i * 4] + 0.587 * d[i * 4 + 1] + 0.114 * d[i * 4 + 2]);
    const med = g.reduce((a, b) => a + b, 0) / 72;
    if (g.reduce((a, b) => a + (b - med) * (b - med), 0) / 72 < 40) return '-';      // fotograma liso
    let h = '';
    for (let f = 0; f < 8; f++) { let b = 0; for (let k = 0; k < 8; k++) b = (b << 1) | (g[f * 9 + k] > g[f * 9 + k + 1] ? 1 : 0); h += b.toString(16).padStart(2, '0'); }
    return h;
  };
  const uno = async (it) => {
    if (!it.src) { window.__H.datos[it.id] = null; return; }                          // imagen o carrusel
    const v = await __abrir(it.src), dur = v.duration, ini = [], fin = [];
    for (const t of [0.5, 2, 4, 6]) if (t < dur - 1) { await __ir(v, t); ini.push(huella(v)); }
    for (let k = 0; k < 16; k++) { const t = dur - 0.7 - 4 * k; if (t <= 7) break; await __ir(v, t); fin.push(huella(v)); }
    window.__H.datos[it.id] = { dur: Math.round(dur * 10) / 10, w: v.videoWidth, h: v.videoHeight, ini, fin };
    v.removeAttribute('src'); v.load();
  };
  const trabajos = cola.slice(0, maxVideos); let i = 0;
  const obrero = async () => { while (i < trabajos.length) { const it = trabajos[i++]; try { await uno(it); } catch (e) { window.__H.fallos.push(it.id + ':' + e.message); } window.__H.hechos++; } };
  await Promise.all([obrero(), obrero(), obrero()]);
  window.__H.estado = 'listo';
};

window.__comparar = (UMBRAL) => {
  UMBRAL = UMBRAL || 10;
  const D = window.__H.datos, ids = Object.keys(D).filter(k => D[k]);
  const pc = n => { let c = 0; while (n) { c += n & 1; n >>>= 1; } return c; };
  const ham = (a, b) => { if (a === '-' || b === '-') return 99; let d = 0; for (let i = 0; i < 16; i += 4) d += pc(parseInt(a.substr(i, 4), 16) ^ parseInt(b.substr(i, 4), 16)); return d; };
  const alin = (x, y) => { const n = Math.min(x.length, y.length); if (!n) return 0; let m = 0; for (let i = 0; i < n; i++) if (ham(x[i], y[i]) <= UMBRAL) m++; return m / n; };
  const conj = (x, y) => { const v = x.filter(h => h !== '-'); return v.length ? v.filter(h => y.some(g => ham(h, g) <= UMBRAL)).length / v.length : 0; };
  const padre = {}, igual = {};
  ids.forEach(i => { padre[i] = i; igual[i] = i; });
  const raiz = (p, i) => p[i] === i ? i : (p[i] = raiz(p, p[i]));
  const rel = [];
  for (let i = 0; i < ids.length; i++) for (let j = i + 1; j < ids.length; j++) {
    const a = D[ids[i]], b = D[ids[j]];
    const ini = alin(a.ini, b.ini), fin = alin(a.fin, b.fin);                 // arranque alineado desde el inicio; cuerpo y cierre, desde el final
    const ta = a.ini.concat(a.fin), tb = b.ini.concat(b.fin);
    const cj = Math.min(conj(ta, tb), conj(tb, ta));                           // material compartido en cualquier posición
    let tipo = null;
    if (Math.abs(a.dur - b.dur) <= 1.5 && ini >= 0.75 && fin >= 0.8) { tipo = 'identico'; igual[raiz(igual, ids[i])] = raiz(igual, ids[j]); }
    else if ((ini >= 0.66 && fin >= 0.5) || (ini >= 0.5 && cj >= 0.8)) tipo = 'mismo-video-otro-corte';
    else if (ini >= 0.66) tipo = 'mismo-arranque-cuerpo-distinto';
    else if (fin >= 0.5) tipo = 'mismo-cuerpo-arranque-distinto';
    else if (cj >= 0.5) tipo = 'mismo-material-otro-montaje';
    else if (cj >= 0.15) tipo = 'comparten-tramo';
    if (tipo && tipo !== 'comparten-tramo') padre[raiz(padre, ids[i])] = raiz(padre, ids[j]);
    if (tipo && tipo !== 'identico') rel.push([ids[i], ids[j], tipo, Math.round(ini * 100), Math.round(fin * 100), Math.round(cj * 100)]);
  }
  const fams = {};
  ids.forEach(i => { (fams[raiz(padre, i)] = fams[raiz(padre, i)] || []).push(i); });
  window.__F = Object.values(fams).sort((x, y) => y.length - x.length);
  window.__R = rel; window.__I = (i) => raiz(igual, i);
  return { videos: ids.length, sin_video: Object.keys(D).length - ids.length, familias: window.__F.length };
};

// Salida con el formato que espera `banco_candidatos.py videos` (añadir a mano «formatos», «formato_por_familia» y «lectura» tras ver las hojas).
window.__salida = () => {
  window.__comparar(10);
  const D = window.__H.datos;
  return {
    metodo: 'huella de 64 bits por fotograma (4 del arranque: 0,5-6 s; hasta 16 desde el final, cada 4 s); iguales con 10 bits o menos de diferencia',
    familias: window.__F.map(m => m.map(i => Object.assign({ id: i, dur: D[i].dur, f: D[i].w > D[i].h ? 'horizontal' : (D[i].w === D[i].h ? '1:1' : '9:16') }, window.__I(i) !== i ? { igual_a: window.__I(i) } : {}))),
    relaciones: window.__R.filter(r => r[2] !== 'comparten-tramo').map(r => r.map(String)),
  };
};

// Hoja de contacto: por familia, el fotograma a los 2 s (arriba) y el de mitad del video (abajo), con «número · duración ×miembros».
// Para ver los arranques de UNA familia: window.__F = window.__F[0].map(id => [id]) antes de llamar.
window.__hoja = async (desde, cuantas) => {
  const buscar = async (id) => {
    const s = __fichas().find(e => e.textContent.trim() === 'Identificador de la biblioteca: ' + id);
    if (!s) return null;
    const card = __tarjeta(s); card.scrollIntoView(); await __esp(900);
    const v = card.querySelector('video');
    return v ? (v.src || v.currentSrc) : null;
  };
  let c = document.getElementById('__hoja'); if (c) c.remove();
  c = document.createElement('canvas'); c.id = '__hoja'; c.width = 800; c.height = 600;
  c.style.cssText = 'position:fixed;left:0;top:0;width:100vw;height:100vh;z-index:2147483647;background:#111';
  document.body.appendChild(c);
  const x = c.getContext('2d'); x.fillStyle = '#111'; x.fillRect(0, 0, 800, 600);
  const fams = window.__F.slice(desde, desde + cuantas), cols = 7, cw = 114, ch = 300;
  for (let n = 0; n < fams.length; n++) {
    const ox = (n % cols) * cw, oy = Math.floor(n / cols) * ch;
    x.font = 'bold 12px sans-serif';
    try {
      const v = await __abrir(await buscar(fams[n][0]));
      const dib = async (t, y) => { await __ir(v, t); const r = Math.min(110 / v.videoWidth, 138 / v.videoHeight), w = v.videoWidth * r, h = v.videoHeight * r; x.drawImage(v, ox + 2 + (110 - w) / 2, y + (138 - h) / 2, w, h); };
      await dib(2, oy + 16); await dib(v.duration * 0.5, oy + 158);
      x.fillStyle = '#fff'; x.fillText((desde + n + 1) + ' · ' + Math.round(v.duration) + 's ×' + fams[n].length, ox + 4, oy + 12);
    } catch (e) { x.fillStyle = '#f66'; x.fillText((desde + n + 1) + ' falla', ox + 4, oy + 12); }
  }
  return 'hoja con ' + fams.length + ' familias';
};
