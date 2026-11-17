// HMAC-SHA256 con Web Crypto, para autenticación servicio a servicio
// (convenciones de código §5: "quien verifica puede firmar, aceptable ahí").
// Comparación en tiempo constante (equivalente a hmac.compare_digest de Python).

const codificador = new TextEncoder();

function bufferAHex(buffer) {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function importarClaveHmac(secreto) {
  return crypto.subtle.importKey(
    "raw",
    codificador.encode(secreto),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
}

/** Firma `mensaje` con HMAC-SHA256 y devuelve hexadecimal minúscula. */
export async function firmarHmacSha256Hex(secreto, mensaje) {
  const clave = await importarClaveHmac(secreto);
  const firma = await crypto.subtle.sign("HMAC", clave, codificador.encode(mensaje));
  return bufferAHex(firma);
}

/**
 * Compara dos cadenas hexadecimales en tiempo constante (no corta al primer
 * byte distinto; si la longitud difiere, igual recorre la cadena recibida
 * para no filtrar la longitud por temporización).
 */
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
 * Construye las cabeceras de autenticación interna del backbone (docs/06 §4.7):
 * X-Fabrica-Ts y X-Fabrica-Firma = hmac-sha256=<hex> de `ts + "." + cuerpo`.
 */
export async function construirCabecerasInternas(secreto, cuerpoExacto, ahoraIso) {
  const firma = await firmarHmacSha256Hex(secreto, `${ahoraIso}.${cuerpoExacto}`);
  return {
    "X-Fabrica-Ts": ahoraIso,
    "X-Fabrica-Firma": `hmac-sha256=${firma}`,
  };
}
