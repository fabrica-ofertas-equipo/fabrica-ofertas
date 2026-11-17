// Modo formulario de `POST /api/sesion` (docs/_historial/decision-arranque-de-pago.md):
// la landing envia `<form method="post" action="/api/sesion">` SIN JavaScript.
// `visitor_id`/`params` NO van en el cuerpo (no se conocen al construir la
// pagina estatica): se leen de cookies del MISMO origen. Exito -> 303 a
// Stripe Checkout (nunca 200 JSON); error -> pagina/estado 4xx simple SIN
// reflejar ningun dato de la solicitud (sin XSS: el `codigo` que se expone
// sale siempre de un enum interno fijo, nunca de la entrada del usuario).

import { validarCamposFormulario, casillaABooleano } from "./validacion.mjs";
import { verificarTurnstile } from "./turnstile.mjs";
import { cargarCatalogoVerificado, entradaOferta } from "./catalogo.mjs";
import { crearSesionCheckout } from "./manejador.mjs";
import {
  parsearCabeceraCookie,
  visitorIdDeCookie,
  paramsDeCookie,
  fbpDeCookie,
  fbcDeCookie,
  generarVisitorIdAleatorio,
} from "./cookies.mjs";

const ORIGEN_STRIPE_CHECKOUT = "https://checkout.stripe.com";

/** `true` solo si `url` es `https://checkout.stripe.com/...` (nunca otro host). */
function esUrlStripeValida(url) {
  try {
    return new URL(url).origin === ORIGEN_STRIPE_CHECKOUT;
  } catch {
    return false;
  }
}

/**
 * Exige `Sec-Fetch-Site: same-origin`; si la cabecera falta, exige que
 * `Origin` figure en la lista configurada (`env.origenesPermitidos`).
 * El `Host` de la peticion NUNCA es, por si solo, la fuente de verdad.
 */
export function mismoOrigenValido(secFetchSite, origin, origenesPermitidos) {
  if (secFetchSite) return secFetchSite === "same-origin";
  if (!origin) return false;
  return (origenesPermitidos ?? []).includes(origin);
}

/**
 * Decide si la renuncia de desistimiento es obligatoria para esta oferta y
 * `locale`. Orden (docs): (1) el campo `renuncia.requerido` del catalogo
 * firmado, si lo lleva ("el campo equivalente que ya lleve el catalogo");
 * (2) si no, la lista de locales UE/UK de la CONFIGURACION del Worker
 * (`env.localesRenunciaRequerida`), nunca un literal en esta funcion.
 */
export function renunciaEsRequerida(entrada, locale, localesRenunciaRequerida) {
  if (entrada?.renuncia && typeof entrada.renuncia.requerido === "boolean") {
    return entrada.renuncia.requerido;
  }
  return (localesRenunciaRequerida ?? []).includes(locale);
}

/** Version del texto de renuncia citada en la evidencia (catalogo o "desconocida"). */
function renunciaTextoVersion(entrada) {
  return entrada?.renuncia?.texto_version ?? "desconocida";
}

/** `AAAA-MM-DDTHH:MM:SSZ` (sin milisegundos: formato comun de `esTimestampZValido`). */
function isoZSegundos(fecha) {
  return fecha.toISOString().replace(/\.\d{3}Z$/, "Z");
}

/**
 * Maneja `POST /api/sesion` en modo formulario. Entradas:
 * - `campos`: objeto plano ya parseado de `application/x-www-form-urlencoded`
 *   (nombres SIN decodificar de mas: el llamador solo hace `URLSearchParams`).
 * - `cabeceraCookie`, `cabeceraSecFetchSite`, `cabeceraOrigin`, `cabeceraReferer`.
 * - `env`: lo mismo que `manejarSolicitudSesion` mas `origenesPermitidos`
 *   (array) y `localesRenunciaRequerida` (array).
 * - `verificarCuota`, `ahora`, `transporte`: igual que el modo JSON.
 *
 * Devuelve `{ status, location }` en exito (303) o `{ status, codigo }` en
 * error (4xx/5xx; `codigo` es siempre un valor de un enum interno fijo).
 */
export async function manejarSolicitudSesionFormulario({
  campos,
  cabeceraCookie,
  cabeceraSecFetchSite,
  cabeceraOrigin,
  cabeceraReferer,
  env,
  verificarCuota,
  ahora,
  transporte,
}) {
  const turnstileHabilitado = Boolean(env.turnstileSecreto);
  const validacion = validarCamposFormulario(campos, { turnstileHabilitado });
  if (!validacion.ok) {
    return { status: 400, codigo: "validacion" };
  }

  if (!mismoOrigenValido(cabeceraSecFetchSite, cabeceraOrigin, env.origenesPermitidos)) {
    return { status: 403, codigo: "origen_invalido" };
  }

  if (turnstileHabilitado) {
    const turnstileOk = await verificarTurnstile(transporte, {
      token: campos["cf-turnstile-response"],
      secreto: env.turnstileSecreto,
      ipRemota: null,
    });
    if (!turnstileOk) {
      return { status: 400, codigo: "turnstile_invalido" };
    }
  }

  const catalogo = await cargarCatalogoVerificado(env.catalogoJson, env.catalogoFirma, env.catalogoHmacSecreto);
  if (!catalogo) {
    return { status: 500, codigo: "catalogo_invalido" };
  }
  const entrada = entradaOferta(catalogo, campos.oferta_id);
  if (!entrada || !entrada.price_id) {
    return { status: 404, codigo: "oferta_no_en_catalogo" };
  }

  const bump = casillaABooleano(campos.bump);
  const renunciaAceptada = casillaABooleano(campos.renuncia_desistimiento);
  if (renunciaEsRequerida(entrada, campos.locale, env.localesRenunciaRequerida) && !renunciaAceptada) {
    return { status: 400, codigo: "renuncia_requerida" };
  }

  const mapaCookies = parsearCabeceraCookie(cabeceraCookie);
  const visitorIdCookie = visitorIdDeCookie(mapaCookies);
  const visitorId = visitorIdCookie ?? generarVisitorIdAleatorio();
  // Consentimiento implicito: `consentimiento.js` (B4) solo escribe `fab_vid`/
  // `fab_attr` tras el consentimiento de marketing (ver decision del arranque
  // de pago); sin esa cookie no hay atribucion ni envio a CAPI.
  const consentMarketing = visitorIdCookie ? "1" : "0";
  const params = { ...paramsDeCookie(mapaCookies) };
  const fbp = fbpDeCookie(mapaCookies);
  const fbc = fbcDeCookie(mapaCookies);
  if (fbp) params.fbp = fbp;
  if (fbc) params.fbc = fbc;

  const landingVersion =
    typeof entrada.landing_version === "string" && entrada.landing_version.length > 0
      ? entrada.landing_version
      : "desconocida";

  const metadataExtra = renunciaAceptada
    ? { renuncia_ts: isoZSegundos(ahora()), renuncia_texto_version: renunciaTextoVersion(entrada) }
    : undefined;

  const resultado = await crearSesionCheckout({
    ofertaId: campos.oferta_id,
    visitorId,
    bump,
    locale: campos.locale,
    consentMarketing,
    landingVersion,
    params,
    cabeceraReferer,
    metadataExtra,
    env,
    verificarCuota,
    ahora,
    transporte,
  });

  if (resultado.status !== 200) {
    return { status: resultado.status, codigo: resultado.cuerpo?.codigo ?? "error" };
  }
  if (!esUrlStripeValida(resultado.cuerpo.url)) {
    return { status: 502, codigo: "respuesta_stripe_invalida" };
  }
  return { status: 303, location: resultado.cuerpo.url };
}
