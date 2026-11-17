// HMAC-SHA256 con Web Crypto, sin dependencias (igual que tracking/workers/_lib/src/hmac.mjs, pero
// este Worker vive en infra/ y se despliega por separado: duplicar este archivo pequeño es más
// barato que acoplar el bundle de `fulfill` al de `tracking`).

const codificador = new TextEncoder();

async function importarClaveHmac(secreto) {
  return crypto.subtle.importKey("raw", codificador.encode(secreto), { name: "HMAC", hash: "SHA-256" }, false, [
    "sign",
  ]);
}

/** Firma `mensaje` con HMAC-SHA256 y devuelve hexadecimal minúscula. */
export async function firmarHmacSha256Hex(secreto, mensaje) {
  const clave = await importarClaveHmac(secreto);
  const firma = await crypto.subtle.sign("HMAC", clave, codificador.encode(mensaje));
  return Array.from(new Uint8Array(firma))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** Compara dos cadenas hex en tiempo constante (no corta al primer byte distinto). */
export function compararHexEnTiempoConstante(esperadoHex, recibidoHex) {
  if (typeof recibidoHex !== "string" || !/^[0-9a-f]+$/i.test(recibidoHex)) {
    return false;
  }
  const a = esperadoHex.toLowerCase();
  const b = recibidoHex.toLowerCase();
  const longitud = Math.max(a.length, b.length);
  let diferencia = a.length === b.length ? 0 : 1;
  for (let i = 0; i < longitud; i += 1) {
    const ca = i < a.length ? a.charCodeAt(i) : 0;
    const cb = i < b.length ? b.charCodeAt(i) : 0;
    diferencia |= ca ^ cb;
  }
  return diferencia === 0;
}

/** Verifica una firma HMAC-SHA256 hexadecimal contra `mensaje`. */
export async function verificarHmacSha256(secreto, mensaje, firmaHex) {
  const esperado = await firmarHmacSha256Hex(secreto, mensaje);
  return compararHexEnTiempoConstante(esperado, firmaHex);
}

/**
 * Cabeceras de autenticacion interna hacia el servicio `api` (docs/06 §4.7): `X-Fabrica-Ts` y
 * `X-Fabrica-Firma: hmac-sha256=<hex>` = HMAC-SHA256 de `ts + "." + cuerpo_exacto` (los bytes EXACTOS que se
 * envian). Mismo formato que `tracking/workers/_lib/src/hmac.mjs` y `infra/firma_servicio.py` (sin contexto:
 * es Worker -> API, no lo que firma el dashboard).
 */
export async function construirCabecerasInternas(secreto, cuerpoExacto, ahoraIso) {
  const firma = await firmarHmacSha256Hex(secreto, `${ahoraIso}.${cuerpoExacto}`);
  return { "X-Fabrica-Ts": ahoraIso, "X-Fabrica-Firma": `hmac-sha256=${firma}` };
}
