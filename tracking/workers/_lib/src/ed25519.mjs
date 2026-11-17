// Verificación Ed25519 con crypto.subtle (sin dependencias; soportado por el
// runtime de Cloudflare Workers: https://developers.cloudflare.com/workers/runtime-apis/web-crypto/,
// leída 2026-11-06).
//
// Decisión (ver README "Decisiones"): esta utilidad verifica una firma Ed25519
// CRUDA (clave pública raw de 32 bytes + firma raw de 64 bytes, ambas en
// base64 estándar), no el blob SSHSIG (`ed25519:U1NIU0lH...`) que usan las
// aprobaciones humanas y el sello de X1 (comunes.schema.json `$defs.ed25519`):
// ese formato lo firma `ssh-keygen -Y sign` y lo verifica `engine.guard` en
// Python (motor), que es quien tiene la clave pública del dueño. Ningún
// Worker de este alcance necesita verificar ese blob en tiempo de ejecución;
// esta función queda disponible para cuando un Worker reciba una firma
// Ed25519 cruda (p. ej. una orden firmada reenviada ya verificada por el
// motor, o un futuro uso de `_lib` por otro componente).

function base64ABytes(base64) {
  const binario = atob(base64);
  const bytes = new Uint8Array(binario.length);
  for (let i = 0; i < binario.length; i += 1) {
    bytes[i] = binario.charCodeAt(i);
  }
  return bytes;
}

/**
 * Verifica una firma Ed25519 cruda. `clavePublicaBase64` y `firmaBase64` son
 * base64 estándar (no SSHSIG). `mensaje` es una cadena UTF-8. Nunca lanza:
 * ante cualquier formato inválido devuelve `false` (fail-closed).
 */
export async function verificarEd25519Cruda(clavePublicaBase64, mensaje, firmaBase64) {
  try {
    const claveBytes = base64ABytes(clavePublicaBase64);
    const firmaBytes = base64ABytes(firmaBase64);
    const clave = await crypto.subtle.importKey(
      "raw",
      claveBytes,
      { name: "Ed25519" },
      false,
      ["verify"],
    );
    const mensajeBytes = new TextEncoder().encode(mensaje);
    return await crypto.subtle.verify({ name: "Ed25519" }, clave, firmaBytes, mensajeBytes);
  } catch {
    return false;
  }
}
