// lib/negocio-visual.js — visuales del tablero Negocio, hechos a mano con CSS (sin librerías): medidor contra el equilibrio (ROAS neto en la ficha),
// tono de una tasa contra su referencia, banderas del mercado y color de identidad por oferta. (Cascada, embudo con bandas y barras divergentes
// se sacaron el 12-nov: el dueño pidió bajar la densidad.)
// Pedido del dueño (2026-11-12): «que sea entendible más rápido visualmente y que no sea todo gris».
// Reglas: el color tiene significado (verde gana o sobre el equilibrio, rojo pierde o debajo, ámbar mirar, azul información o programado,
// gris solo sin pauta o sin dato) y NUNCA es la única señal: cada visual lleva su número, un texto o un icono.
// Geometría pura (probada en tests/dashboard/test_web_negocio.mjs) + constructores que reciben `ui` (todo el texto entra por textContent).

const esNum = (x) => typeof x === 'number' && Number.isFinite(x);
const r1 = (x) => Math.round(x * 10) / 10;
const lim = (x) => Math.max(0, Math.min(100, x));

/** Colores de identidad por oferta, en orden fijo (sigue a la oferta por su lugar en el libro, nunca por su ranking). */
export const IDENTIDADES = 6;
export function claseIdentidad(indice) { return `ng-id-${(Math.max(0, indice | 0) % IDENTIDADES) + 1}`; }

const NOMBRES_PAIS = { MX: 'México', BR: 'Brasil', AR: 'Argentina', CO: 'Colombia', CL: 'Chile', PE: 'Perú', ES: 'España', US: 'Estados Unidos', PL: 'Polonia', IT: 'Italia', PT: 'Portugal', FR: 'Francia', DE: 'Alemania',
  GB: 'Reino Unido', UK: 'Reino Unido', IE: 'Irlanda', NZ: 'Nueva Zelanda', AU: 'Australia', CA: 'Canadá', NL: 'Países Bajos', TR: 'Turquía', JP: 'Japón' };
// En un texto suelto estos códigos suelen ser palabras o siglas en español: `conPaises` no los toca (igual que paises.py).
const AMBIGUOS = new Set(['NO', 'SI', 'SE', 'CR', 'IS', 'IN', 'ID', 'MA', 'PA', 'AM', 'PM']);
/** «MX» → «🇲🇽» (letras indicadoras regionales); otra cosa → ''. */
export function bandera(cod) {
  let c = String(cod || '').toUpperCase();
  if (c === 'UK') c = 'GB';
  if (!/^[A-Z]{2}$/.test(c)) return '';
  return String.fromCodePoint(...[...c].map((l) => 0x1f1e6 + l.charCodeAt(0) - 65));
}
let nombresIntl = null;
try { nombresIntl = new Intl.DisplayNames(['es'], { type: 'region' }); } catch (_) { nombresIntl = null; }
/** «GB» → «Reino Unido» (tabla propia y, si falta, el nombre en español que trae el navegador); otra cosa → el texto tal cual. */
export function nombrePais(cod) {
  const c = String(cod || '').toUpperCase();
  if (NOMBRES_PAIS[c]) return NOMBRES_PAIS[c];
  if (nombresIntl && /^[A-Z]{2}$/.test(c)) { try { return nombresIntl.of(c) || c; } catch (_) { return c; } }
  return String(cod || '');
}

/** Regla del dueño (17-nov): cada mercado con bandera y nombre. «IE» → «IE (🇮🇪 Irlanda)»; «MX/BR» → «MX (🇲🇽 México) y BR (🇧🇷 Brasil)». */
export function mercadoLargo(mercado) {
  const cods = codigosPais(mercado);
  return cods.length ? cods.map((c) => `${c} (${bandera(c)} ${nombrePais(c)})`).join(' y ') : String(mercado || '');
}

/** Agrega «(🇮🇪 Irlanda)» a los códigos de mercado de un texto libre (avisos, motivos). Misma lógica que paises.py. */
export function conPaises(texto) {
  if (!texto) return texto || '';
  const ok = (c) => NOMBRES_PAIS[c] && !AMBIGUOS.has(c);
  let t = String(texto).replace(/\(([A-Z]{2}(?:[/,]\s*[A-Z]{2})*)\)/g, (m, g) => (g.split(/[/,]\s*/).every(ok) ? mercadoLargo(g) : m));
  t = t.replace(/(^|[^A-Za-z0-9\-_/.#])([A-Z]{2}(?:\/[A-Z]{2})+)(?![A-Za-z0-9$\-_/])/g, (m, pre, g) => (g.split('/').every(ok) ? pre + mercadoLargo(g) : m));
  return t.replace(/(^|[^A-Za-z0-9\-_/.#])([A-Z]{2})(?![A-Za-z0-9$\-_])(\s?\(\S+ )?/g, (m, pre, c, ya) => {
    if (ya && ya.includes(bandera(c))) return m;          // ya tiene su paréntesis
    return ok(c) ? `${pre}${c} (${bandera(c)} ${nombrePais(c)})${ya || ''}` : m;
  });
}

/** «México y Brasil» a partir del mercado. */
export function nombresPais(mercado) { return codigosPais(mercado).map(nombrePais).join(' y ') || 'Sin mercado'; }

/** Códigos de país de un mercado («MX», «MX/BR», «MX, BR») en orden y sin repetir. */
export function codigosPais(mercado) {
  return [...new Set(String(mercado || '').toUpperCase().split(/[^A-Z]+/).filter((c) => /^[A-Z]{2}$/.test(c)))];
}

/**
 * Banderas del mercado: un emoji por país, con el nombre en `title` y `aria-label` (accesible y con respaldo: donde el sistema no dibuja
 * banderas, el navegador muestra las dos letras del código). `conNombre` agrega «México y Brasil» al lado.
 */
export function banderas(ui, mercado, { conNombre = false } = {}) {
  const { el } = ui;
  const cods = codigosPais(mercado);
  const nombres = cods.map(nombrePais);
  return el('span', { class: 'ng-paises' },
    cods.map((c, i) => el('span', { class: 'ng-bandera', role: 'img', 'aria-label': nombres[i], title: nombres[i] }, bandera(c))),
    conNombre && cods.length ? el('span', { class: 'ng-paises__nombre' }, nombres.join(' y ')) : null);
}

/**
 * Medidor contra un equilibrio. `mayorEsMejor` (ROAS) o no (CPA). Escala 0..max con el equilibrio en una marca.
 * → {relleno %, marca %, tono 'ok'|'error'|null, max} ; sin valor → {sinDato: true}.
 */
export function geoMedidor(valor, equilibrio, { mayorEsMejor = true, minimoMax } = {}) {
  if (!esNum(equilibrio) || equilibrio <= 0) return { sinDato: true };
  const max = Math.max(minimoMax || equilibrio * 2, esNum(valor) ? valor * 1.12 : 0);
  if (!esNum(valor)) return { sinDato: true, marca: r1((100 * equilibrio) / max), max };
  const bien = mayorEsMejor ? valor >= equilibrio : valor <= equilibrio;
  return { relleno: r1(lim((100 * valor) / max)), marca: r1((100 * equilibrio) / max), tono: bien ? 'ok' : 'error', max };
}

/** Tono de una tasa contra su banda de referencia [bajo, alto]: ok en o sobre la banda, aviso hasta la mitad del piso, error debajo. */
export function tonoTasa(valor, [bajo]) {
  if (!esNum(valor)) return null;
  if (valor >= bajo) return 'ok';
  return valor >= bajo / 2 ? 'aviso' : 'error';
}

// ───────────────────────── constructores (reciben `ui`) ─────────────────────────

const ICONO_TONO = { ok: 'check', error: 'x-circulo', aviso: 'alerta', info: 'info' };
const TEXTO_TONO_ROAS = { ok: 'sobre el equilibrio', error: 'bajo el equilibrio' };

/** Medidor horizontal de un ROAS (marca en 1,00 ×) o de un CPA (marca en el equilibrio). Lleva valor, icono y frase: el color nunca va solo. */
export function medidor(ui, { titulo, valor, equilibrio = 1, mayorEsMejor = true, formato, textoEquilibrio, ayuda, compacto = false, grande = false } = {}) {
  const { el } = ui;
  const g = geoMedidor(valor, equilibrio, { mayorEsMejor, minimoMax: mayorEsMejor ? 2 : undefined });
  const txt = g.sinDato || !esNum(valor) ? 'sin dato' : formato(valor);
  const frase = g.sinDato ? 'todavía sin datos' : mayorEsMejor ? TEXTO_TONO_ROAS[g.tono] : g.tono === 'ok' ? 'bajo el equilibrio: gana' : 'sobre el equilibrio: pierde';
  return el('div', { class: ['ng-med', compacto && 'ng-med--compacto', grande && 'ng-med--grande', g.tono ? `ng-med--${g.tono}` : 'ng-med--nada'] },
    el('div', { class: 'ng-med__cab' },
      titulo ? el('span', { class: 'ng-med__tit' }, titulo, ayuda ? ui.ayuda(ayuda) : null) : null,
      el('span', { class: 'ng-med__valor' }, g.tono ? ui.icono(ICONO_TONO[g.tono], { tam: grande ? 22 : 15 }) : null, txt)),
    el('div', { class: 'ng-med__pista', role: 'img', 'aria-label': `${titulo || 'Valor'}: ${txt}, ${frase}. Equilibrio ${textoEquilibrio || formato(equilibrio)}.` },
      g.sinDato ? null : el('span', { class: 'ng-med__relleno', style: { width: `${g.relleno}%` } }),
      g.marca !== undefined ? el('span', { class: 'ng-med__marca', style: { left: `${g.marca}%` } }) : null),
    compacto ? null : el('div', { class: 'ng-med__pie' }, el('span', null, frase), el('span', null, `equilibrio ${textoEquilibrio || formato(equilibrio)}`)));
}

/**
 * Dónde corre la oferta ORIGINAL (el referente) de una oferta nuestra: ahí no se pauta (pedido del dueño, 14-nov).
 * Lee `ficha.referente_paises` del libro de tests ({medido, paginas, paises: {GB: 47}, sin_anuncios: [...]}, lo escribe
 * buscar-ofertas/scripts/paises_referente.py). Puro: → {medido, fecha, corre [{cod, n}] de mayor a menor, visibles (tope, con los
 * países que chocan siempre adentro), resto, choque (nuestros países donde también corre), nuestrosSinMirar, sinAnuncios, nuestros}.
 */
export function modeloReferentePaises(ficha, mercado, { tope = 6 } = {}) {
  const nuestros = codigosPais(mercado);
  const rp = ficha && typeof ficha === 'object' ? ficha.referente_paises : null;
  if (!rp || typeof rp !== 'object' || !rp.paises || typeof rp.paises !== 'object') {
    return { medido: false, nuestros, corre: [], visibles: [], resto: 0, choque: [], nuestrosSinMirar: [], sinAnuncios: 0 };
  }
  const corre = Object.entries(rp.paises)
    .map(([c, n]) => ({ cod: String(c).toUpperCase(), n }))
    .filter((x) => /^[A-Z]{2}$/.test(x.cod) && esNum(x.n) && x.n > 0)
    .sort((a, b) => b.n - a.n || a.cod.localeCompare(b.cod));
  const cods = new Set(corre.map((x) => x.cod));
  const sin = new Set((Array.isArray(rp.sin_anuncios) ? rp.sin_anuncios : []).map((c) => String(c).toUpperCase()).filter((c) => /^[A-Z]{2}$/.test(c) && !cods.has(c)));
  const choque = nuestros.filter((c) => cods.has(c));
  const tope2 = Math.max(1, tope | 0);
  const visibles = corre.slice(0, tope2);
  for (const c of choque) if (!visibles.some((x) => x.cod === c)) visibles.push(corre.find((x) => x.cod === c));
  return {
    medido: true, fecha: typeof rp.medido === 'string' ? rp.medido : null, corre, visibles, resto: corre.length - visibles.length,
    choque, nuestrosSinMirar: nuestros.filter((c) => !cods.has(c) && !sin.has(c)), sinAnuncios: sin.size, nuestros,
    paginas: (Array.isArray(rp.paginas) ? rp.paginas : []).filter((p) => p && typeof p === 'object'),
  };
}

/** «14/11 12:40» desde una fecha ISO (la hora tal como se anotó); otra cosa → ''. */
export function fechaMedicion(iso) {
  const m = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/.exec(String(iso || ''));
  return m ? `${m[3]}/${m[2]}${m[4] ? ` ${m[4]}:${m[5]}` : ''}` : '';
}

function banderaConNumero(ui, { cod, n }, choca) {
  const nombre = nombrePais(cod);
  const anuncios = `${n} ${n === 1 ? 'anuncio activo' : 'anuncios activos'}`;
  return ui.el('span', { class: ['ng-ref__pais', choca ? 'ng-ref__pais--choque' : null], title: `${nombre}: ${anuncios}`, 'aria-label': `${nombre}, ${anuncios}` },
    ui.el('span', { class: 'ng-bandera', 'aria-hidden': 'true' }, bandera(cod)), ui.el('span', { class: 'ng-ref__n', 'aria-hidden': 'true' }, String(n)));
}

/**
 * Renglón «Original corre en: 🇬🇧 47 · 🇦🇺 9 · Nosotros: 🇪🇸» para la lista de ofertas (`compacto`) y la ficha. Las banderas del
 * referente llevan `oc--referentes` (se desenfocan en el modo ocultar). Si nuestro país coincide, el renglón va en rojo con un aviso.
 */
export function renglonReferentePaises(ui, ficha, mercado, { compacto = false } = {}) {
  const { el } = ui;
  const m = modeloReferentePaises(ficha, mercado, { tope: 999 });   // el dueño (14-nov): todas las banderas con su número, también en la lista
  const nos = el('span', { class: 'ng-ref__nos' }, el('span', { class: 'ng-ref__rot' }, 'Nosotros:'), banderas(ui, mercado));
  if (!m.medido) {
    return el('div', { class: 'ng-ref ng-ref--sin' },
      el('span', { class: 'ng-ref__rot' }, 'Original corre en:'), el('span', { class: 'texto-tenue' }, 'sin medir todavía'), el('span', { class: 'ng-ref__sep', 'aria-hidden': 'true' }, '·'), nos);
  }
  const choca = new Set(m.choque);
  const lista = m.corre.length
    ? el('span', { class: 'ng-ref__lista oc--referentes' },
      m.visibles.map((x, i) => [i ? el('span', { class: 'ng-ref__sep', 'aria-hidden': 'true' }, '·') : null, banderaConNumero(ui, x, choca.has(x.cod))]),
      m.resto ? el('span', { class: 'ng-ref__mas', title: m.corre.slice(m.visibles.length).map((x) => `${nombrePais(x.cod)} ${x.n}`).join(' · ') }, `y ${m.resto} ${m.resto === 1 ? 'país' : 'países'} más`) : null)
    : el('span', { class: 'texto-tenue' }, 'ningún país');
  return el('div', { class: ['ng-ref', m.choque.length ? 'ng-ref--choque' : null] },
    m.choque.length ? ui.icono('alerta', { tam: 14 }) : null,
    el('span', { class: 'ng-ref__rot' }, 'Original corre en:'), lista,
    el('span', { class: 'ng-ref__sep', 'aria-hidden': 'true' }, '·'), nos,
    m.choque.length ? el('span', { class: 'ng-ref__aviso' }, compacto ? 'también pauta en tu país' : `También pauta en ${m.choque.map(nombrePais).join(' y ')}: ahí compites con el original.`) : null);
}

/** Hoja de estilos de los visuales (tokens del panel: funciona en claro y oscuro). */
export const CSS_VISUAL = `
.ng-paises { display: inline-flex; align-items: center; gap: 4px; white-space: nowrap; }
.ng-bandera { font-size: 1.1em; line-height: 1; font-family: 'Apple Color Emoji', 'Segoe UI Emoji', 'Noto Color Emoji', sans-serif; }
.ng-paises__nombre { margin-left: 2px; }
.ng-ref { display: flex; flex-wrap: wrap; align-items: center; gap: 2px 6px; font-size: var(--t-sm); color: var(--txt-2); min-width: 0; }
.ng-ref__rot { color: var(--txt-3); }
.ng-ref__lista { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 2px 6px; }
.ng-ref__pais { display: inline-flex; align-items: center; gap: 3px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.ng-ref__n { color: var(--txt); font-weight: 600; }
.ng-ref__sep { color: var(--txt-3); }
.ng-ref__nos { display: inline-flex; align-items: center; gap: 4px; }
.ng-ref__mas { color: var(--txt-3); }
.ng-ref--choque { color: var(--error); }
.ng-ref--choque .ng-ref__pais--choque { padding: 0 4px; border-radius: var(--r-1, 4px); background: var(--error-bg); outline: 1px solid var(--error); }
.ng-ref__aviso { color: var(--error); font-weight: 650; }
.ng-txt--ok { color: var(--ok); } .ng-txt--error { color: var(--error); } .ng-txt--aviso { color: var(--aviso); } .ng-txt--info { color: var(--info); }

.ng-med { display: grid; gap: 6px; min-width: 0; }
.ng-med__cab { display: flex; justify-content: space-between; align-items: baseline; gap: var(--e-2); flex-wrap: wrap; }
.ng-med__tit { display: inline-flex; align-items: center; gap: 4px; color: var(--txt-2); font-size: var(--t-sm); }
.ng-med__valor { display: inline-flex; align-items: center; gap: 5px; font-weight: 700; font-size: var(--t-md); font-variant-numeric: tabular-nums; white-space: nowrap; }
.ng-med--grande .ng-med__valor { font-size: 2.1rem; letter-spacing: -.01em; }
.ng-med--ok .ng-med__valor { color: var(--ok); } .ng-med--error .ng-med__valor { color: var(--error); } .ng-med--nada .ng-med__valor { color: var(--txt-3); }
.ng-med__pista { position: relative; height: 12px; border-radius: var(--r-pill); background: var(--sup-3); overflow: visible; }
.ng-med--compacto .ng-med__pista { height: 8px; }
.ng-med__relleno { position: absolute; left: 0; top: 0; bottom: 0; border-radius: var(--r-pill); }
.ng-med--ok .ng-med__relleno { background: var(--punto-ok); } .ng-med--error .ng-med__relleno { background: var(--punto-error); }
.ng-med__marca { position: absolute; top: -4px; bottom: -4px; width: 3px; margin-left: -1.5px; border-radius: 2px; background: var(--txt); }
.ng-med__pie { display: flex; justify-content: space-between; gap: var(--e-2); flex-wrap: wrap; color: var(--txt-2); font-size: var(--t-xs); }

`;
