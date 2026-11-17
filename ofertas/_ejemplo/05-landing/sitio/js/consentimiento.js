/* [EJEMPLO] consentimiento.js - banner propio v1 (sin dependencias). Todo apagado por defecto.
 * Lo servido se hashea por bytes (hash_archivo): no cambiar sin re-sellar la oferta.
 * Reglas: nada de marketing antes de elegir; Aceptar, Rechazar y Personalizar con el mismo peso;
 * la elección vive en una cookie propia con fecha y versión del texto; pixel.js SOLO lo carga este archivo. */
(function () {
  'use strict';

  var CONFIG = {
    version_texto: 'v1',                 // sube al cambiar el texto del banner: obliga a volver a preguntar
    cookie: 'fabrica_consent',
    duracion_segundos: 15552000,         // 180 días
    pixel_src: '/js/pixel.js'            // única forma de llegar al píxel
  };
  var TEXTO = {
    titulo: 'Tus preferencias de cookies',
    cuerpo: 'Usamos una cookie propia para recordar tu elección. Con tu permiso, también medimos el resultado de nuestros anuncios (Meta). Todo lo opcional está desactivado hasta que elijas.',
    aceptar: 'Aceptar',
    rechazar: 'Rechazar',
    personalizar: 'Personalizar',
    guardar: 'Guardar elección',
    necesarias: 'Necesarias (siempre activas): recordar esta elección.',
    marketing: 'Marketing: medir anuncios con el píxel de Meta.',
    mas: 'Más información'
  };

  var estado = { marketing: false, decidido: false, id: null, fecha: null };
  var pixelCargado = false;

  function leerCookie() {
    var pares = document.cookie ? document.cookie.split('; ') : [];
    for (var i = 0; i < pares.length; i++) {
      var k = pares[i].split('=');
      if (k[0] === CONFIG.cookie) {
        try { return JSON.parse(decodeURIComponent(k.slice(1).join('='))); } catch (e) { return null; }
      }
    }
    return null;
  }

  function escribirCookie(valor) {
    var seguro = location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = CONFIG.cookie + '=' + encodeURIComponent(JSON.stringify(valor)) +
      '; Path=/; Max-Age=' + CONFIG.duracion_segundos + '; SameSite=Lax' + seguro;
  }

  // Meta crea _fbp/_fbc en el dominio raíz: se borran con y sin Domain=. Con el píxel ya cargado se recarga (fbq sigue vivo hasta entonces).
  function borrarCookiesDeMarketing() {
    var raiz = location.hostname.replace(/^www\./, '');
    ['_fbp', '_fbc'].forEach(function (n) {
      document.cookie = n + '=; Path=/; Max-Age=0; SameSite=Lax';
      document.cookie = n + '=; Path=/; Domain=.' + raiz + '; Max-Age=0; SameSite=Lax';
    });
  }

  function idAleatorio() {
    var b = new Uint8Array(8);
    (window.crypto || window.msCrypto).getRandomValues(b);
    return Array.prototype.map.call(b, function (x) { return ('0' + x.toString(16)).slice(-2); }).join('');
  }

  function cargarPixel() {
    if (pixelCargado || !estado.marketing) { return; }
    pixelCargado = true;
    var s = document.createElement('script');
    s.src = CONFIG.pixel_src;
    s.async = true;
    document.head.appendChild(s);
  }

  function aplicar(marketing) {
    var previo = estado.marketing;
    estado.marketing = !!marketing;
    estado.decidido = true;
    estado.fecha = new Date().toISOString();
    estado.id = estado.marketing ? (estado.id || idAleatorio()) : null;
    escribirCookie({ v: CONFIG.version_texto, m: estado.marketing ? 1 : 0, t: estado.fecha, id: estado.id });
    document.documentElement.setAttribute('data-consent-marketing', estado.marketing ? '1' : '0');
    if (previo && !estado.marketing) { borrarCookiesDeMarketing(); }
    document.dispatchEvent(new CustomEvent('fabrica:consent', { detail: { marketing: estado.marketing, version: CONFIG.version_texto } }));
    cargarPixel();
    if (previo && !estado.marketing && pixelCargado) { location.reload(); }
  }

  function el(tag, attrs, hijos) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    (hijos || []).forEach(function (h) { n.appendChild(typeof h === 'string' ? document.createTextNode(h) : h); });
    return n;
  }

  function cerrar() {
    var b = document.getElementById('fabrica-consent');
    if (b && b.parentNode) { b.parentNode.removeChild(b); }
  }

  function mostrar() {
    cerrar();
    var casilla = el('input', { type: 'checkbox', id: 'fc-marketing' });
    casilla.checked = false;                                   // apagado por defecto
    var panel = el('div', { id: 'fc-panel', hidden: 'hidden' }, [
      el('p', {}, [TEXTO.necesarias]),
      el('label', {}, [casilla, ' ' + TEXTO.marketing]),
      el('button', { type: 'button', 'class': 'fc-btn', id: 'fc-guardar' }, [TEXTO.guardar])
    ]);
    var banner = el('div', { id: 'fabrica-consent', role: 'dialog', 'aria-labelledby': 'fc-titulo' }, [
      el('h2', { id: 'fc-titulo' }, [TEXTO.titulo]),
      el('p', {}, [TEXTO.cuerpo + ' ', el('a', { href: '/legal/cookies' }, [TEXTO.mas])]),
      el('div', { 'class': 'fc-botones' }, [
        el('button', { type: 'button', 'class': 'fc-btn', id: 'fc-aceptar' }, [TEXTO.aceptar]),
        el('button', { type: 'button', 'class': 'fc-btn', id: 'fc-rechazar' }, [TEXTO.rechazar]),
        el('button', { type: 'button', 'class': 'fc-btn', id: 'fc-personalizar' }, [TEXTO.personalizar])
      ]),
      panel
    ]);
    document.body.appendChild(banner);
    document.getElementById('fc-aceptar').addEventListener('click', function () { aplicar(true); cerrar(); });
    document.getElementById('fc-rechazar').addEventListener('click', function () { aplicar(false); cerrar(); });
    document.getElementById('fc-personalizar').addEventListener('click', function () { panel.removeAttribute('hidden'); });
    document.getElementById('fc-guardar').addEventListener('click', function () { aplicar(casilla.checked); cerrar(); });
  }

  function iniciar() {
    var c = leerCookie();
    if (c && c.v === CONFIG.version_texto && (c.m === 0 || c.m === 1)) {
      estado.marketing = c.m === 1; estado.decidido = true; estado.id = c.id || null; estado.fecha = c.t || null;
      document.documentElement.setAttribute('data-consent-marketing', estado.marketing ? '1' : '0');
      cargarPixel();
    } else {
      document.documentElement.setAttribute('data-consent-marketing', '0');
      mostrar();
    }
    Array.prototype.forEach.call(document.querySelectorAll('[data-consent-abrir]'), function (b) { b.addEventListener('click', mostrar); });
  }

  window.FabricaConsent = {
    marketing: function () { return estado.marketing === true; },
    visitorId: function () { return estado.id; },
    abrir: mostrar
  };

  if (document.readyState === 'loading') { document.addEventListener('DOMContentLoaded', iniciar); } else { iniciar(); }
})();
