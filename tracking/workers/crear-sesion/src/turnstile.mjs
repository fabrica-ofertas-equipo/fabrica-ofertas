// Verificacion de Turnstile en el boton de compra (docs/06 4.3), sin
// cookies de seguimiento. Llama a la API de verificacion de Cloudflare por
// el `transporte` inyectado (nunca `fetch` global): nunca se prueba contra
// la red real.

const URL_VERIFICACION = "https://challenges.cloudflare.com/turnstile/v0/siteverify";

/**
 * Verifica un token de Turnstile. Devuelve `true`/`false`. Fail-closed: sin
 * `secreto` o `token`, o ante cualquier respuesta que no sea JSON con
 * `success === true`, se rechaza.
 */
export async function verificarTurnstile(transporte, { token, secreto, ipRemota }) {
  if (!token || !secreto) return false;
  const cuerpo = new URLSearchParams({ secret: secreto, response: token });
  if (ipRemota) cuerpo.set("remoteip", ipRemota);
  const respuesta = await transporte.solicitar("POST", URL_VERIFICACION, {
    cabeceras: { "content-type": "application/x-www-form-urlencoded" },
    cuerpo: cuerpo.toString(),
  });
  try {
    const datos = JSON.parse(respuesta.cuerpo);
    return datos.success === true;
  } catch {
    return false;
  }
}
