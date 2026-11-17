// radar_lector.js — lee las tarjetas de una búsqueda de la Biblioteca de Anuncios (web.facebook.com, interfaz en español)
// y devuelve {total, tarjetas, grupos:[{pagina, pagina_url, destino, tarjetas, anuncios, max_dias, ficha}]} para
// `radar.py registrar <id> --archivo <json>`. Versión del fragmento §6 de fragmentos-navegador.md con dos arreglos
// probados el 2026-11-13: la fecha se busca en toda la tarjeta (no solo tras «En circulación desde el») y se descartan
// destinos que no son una oferta (redes sociales, mensajería).
// Antes de pegarlo: una rueda real del ratón y 3-5 `window.scrollTo(0, document.body.scrollHeight)` con 2,5 s entre cada uno.
(() => {
  const meses = { ene: 0, feb: 1, mar: 2, abr: 3, may: 4, jun: 5, jul: 6, ago: 7, sept: 8, sep: 8, oct: 9, nov: 10, dic: 11 };
  const hoy = new Date();
  const dias = (t) => {
    const m = (t || '').match(/(\d{1,2}) (?:de )?(ene|feb|mar|abr|may|jun|jul|ago|sept?|oct|nov|dic)\w*\.? (?:de )?(\d{4})/i);
    return m ? Math.max(0, Math.round((hoy - new Date(+m[3], meses[m[2].toLowerCase()], +m[1])) / 864e5)) : 0;
  };
  const noOferta = /(^|\.)(instagram\.com|facebook\.com|fb\.me|wa\.me|whatsapp\.com|m\.me|t\.me|telegram\.me|youtube\.com|youtu\.be|tiktok\.com|linktr\.ee|apps\.apple\.com|play\.google\.com)$/i;
  const ids = [...document.querySelectorAll('span,div')].filter((e) => e.childElementCount === 0 && /^Identificador de la biblioteca: \d+/.test(e.textContent.trim()));
  const grupos = new Map();
  let descartadas = 0;
  for (const s of ids) {
    let card = s;
    for (let i = 0; i < 12 && card.parentElement; i++) { card = card.parentElement; if (card.querySelector('a[href*="l.php?u="]') && /Publicidad/.test(card.innerText)) break; }
    const t = card.innerText;
    const desde = (t.match(/En circulación desde el ([^\n]+)/) || [])[1] || t;
    const usan = +((t.match(/(\d+) anuncios usan este contenido/) || [])[1] || 1);
    const pag = [...card.querySelectorAll('a[href*="facebook.com/"]')].find((a) => a.innerText.trim() && !/l\.php|ads\/library/.test(a.href));
    let destino = null;
    for (const a of card.querySelectorAll('a[href]')) {
      try { const u = new URL(a.href); if (u.hostname.startsWith('l.') && u.searchParams.get('u')) { destino = u.searchParams.get('u').split('?')[0]; break; } } catch (e) { /* enlace raro */ }
    }
    if (!destino) continue;
    try { if (noOferta.test(new URL(destino).hostname)) { descartadas++; continue; } } catch (e) { continue; }
    const clave = (pag ? pag.innerText.trim() : '?') + ' | ' + destino;
    const g = grupos.get(clave) || { pagina: pag ? pag.innerText.trim() : '?', pagina_url: pag ? pag.href.split('?')[0] : null, destino, tarjetas: 0, anuncios: 0, max_dias: 0, ficha: s.textContent.match(/\d+/)[0] };
    g.tarjetas++; g.anuncios += usan; g.max_dias = Math.max(g.max_dias, dias(desde));
    grupos.set(clave, g);
  }
  return { total: (document.body.innerText.match(/~?([\d.,]+)\s+resultados?/) || [])[1], tarjetas: ids.length, descartadas, grupos: [...grupos.values()].sort((a, b) => b.anuncios - a.anuncios) };
})()
