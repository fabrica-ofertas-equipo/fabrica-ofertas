// Utilidades de hash SHA-256 con Web Crypto (sin dependencias; disponible en
// el runtime de Cloudflare Workers y en Node >= 19 como globalThis.crypto).

const codificador = new TextEncoder();

function bufferAHex(buffer) {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

/** SHA-256 en hexadecimal minúscula de una cadena UTF-8. */
export async function sha256Hex(texto) {
  const buffer = await crypto.subtle.digest("SHA-256", codificador.encode(texto));
  return bufferAHex(buffer);
}

/** SHA-256 con el prefijo `sha256:` de comunes.schema.json (idempotency_key, sha256). */
export async function sha256Prefijado(texto) {
  return `sha256:${await sha256Hex(texto)}`;
}
