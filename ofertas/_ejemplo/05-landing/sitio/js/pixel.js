/* [EJEMPLO] pixel.js - píxel de Meta. NO se enlaza desde ningún HTML: lo inyecta consentimiento.js
 * y solo después de que la persona acepte marketing. Sin consentimiento este archivo no se pide.
 * Eventos (lista cerrada de tracking.json): PageView y ViewContent con content_ids, value y currency; nada de salud ni de datos personales.
 * ViewContent solo en páginas de producto (las que traen data-oferta-id y data-precio-minor): nunca en legales ni en /gracias.
 * El valor se formatea con ENTEROS (data-decimales = exponente ISO 4217 de la moneda): el dinero no se divide en coma flotante. */
(function () {
  'use strict';
  if (!window.FabricaConsent || window.FabricaConsent.marketing() !== true) { return; }   // defensa en profundidad

  var PIXEL_ID = '999000000000001';   // = tracking.json.pixel_id (ficticio)
  var cuerpo = document.body;
  var ahora = Date.now();
  var visitante = window.FabricaConsent.visitorId() || 'anon';

  !function (f, b, e, v, n, t, s) {
    if (f.fbq) { return; }
    n = f.fbq = function () { n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments); };
    if (!f._fbq) { f._fbq = n; }
    n.push = n; n.loaded = true; n.version = '2.0'; n.queue = [];
    t = b.createElement(e); t.async = true; t.src = v;
    s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s);
  }(window, document, 'script', 'https://connect.facebook.net/en_US/fbevents.js');

  // Unidad menor entera -> decimal como cadena ("1990", 2 -> "19.90"; "1990", 0 -> "1990"); null si el dato no es un entero.
  function valorDecimal(minor, decimales) {
    if (minor === null || !/^[0-9]+$/.test(minor) || !/^[0-9]$/.test(String(decimales))) { return null; }
    var n = Number(decimales), m = minor;
    if (n === 0) { return m; }
    while (m.length <= n) { m = '0' + m; }
    return m.slice(0, m.length - n) + '.' + m.slice(m.length - n);
  }

  var idOferta = cuerpo.getAttribute('data-oferta-id');
  var valor = valorDecimal(cuerpo.getAttribute('data-precio-minor'), cuerpo.getAttribute('data-decimales'));
  var moneda = cuerpo.getAttribute('data-moneda');

  window.fbq('init', PIXEL_ID);
  window.fbq('track', 'PageView', {}, { eventID: 'pv_' + visitante + '_' + ahora });
  if (idOferta && valor !== null && moneda) {
    window.fbq('track', 'ViewContent', {
      content_ids: [idOferta],
      content_type: 'product',
      value: valor,
      currency: moneda
    }, { eventID: 'vc_' + visitante + '_' + ahora });
  }
})();
