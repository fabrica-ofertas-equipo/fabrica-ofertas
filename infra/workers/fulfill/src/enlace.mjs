// Enlace de descarga firmado (HMAC-SHA256, Web Crypto, sin dependencias): docs/06 4.6, "enlace
// (DESCARGA_HMAC, entrega.enlace_vence_dias, enlace_max_descargas)". El token es
// base64url(payload JSON) + "." + HMAC-SHA256 hex del mismo texto; `verificarEnlace` comprueba la
// firma y que no haya vencido ni se haya agotado la cuota ANTES de devolver el payload.

import { firmarHmacSha256Hex, verificarHmacSha256 } from "./hmac.mjs";

const codificador = new TextEncoder();
const decodificador = new TextDecoder();

function bytesABase64Url(bytes) {
  let binario = "";
  for (const b of bytes) {
    binario += String.fromCharCode(b);
  }
  return btoa(binario).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function base64UrlABytes(texto) {
  const normalizado = texto.replace(/-/g, "+").replace(/_/g, "/");
  const binario = atob(normalizado);
  const bytes = new Uint8Array(binario.length);
  for (let i = 0; i < binario.length; i += 1) {
    bytes[i] = binario.charCodeAt(i);
  }
  return bytes;
}

/**
 * Firma un enlace de descarga. `payload`: `{ sessionId, productoSha256, productoVersion, venceEn,
 * maxDescargas }` (`venceEn` ISO con `Z`). Devuelve el token completo (payload + firma).
 */
export async function firmarEnlace(payload, secreto) {
  const cuerpo = JSON.stringify(payload);
  const cuerpoB64 = bytesABase64Url(codificador.encode(cuerpo));
  const firma = await firmarHmacSha256Hex(secreto, cuerpoB64);
  return `${cuerpoB64}.${firma}`;
}

/**
 * Verifica un token de `firmarEnlace`. Devuelve el payload si la firma es válida, no venció
 * (`ahora < venceEn`) y quedan descargas (`descargasHechas < maxDescargas`); si no, `null`.
 */
export async function verificarEnlace(token, secreto, { ahora, descargasHechas }) {
  if (typeof token !== "string" || !token.includes(".")) {
    return null;
  }
  const [cuerpoB64, firma] = token.split(".");
  const valida = await verificarHmacSha256(secreto, cuerpoB64, firma ?? "");
  if (!valida) {
    return null;
  }
  let payload;
  try {
    payload = JSON.parse(decodificador.decode(base64UrlABytes(cuerpoB64)));
  } catch {
    return null;
  }
  if (typeof payload?.venceEn !== "string" || ahora.getTime() >= new Date(payload.venceEn).getTime()) {
    return null;
  }
  if (typeof payload?.maxDescargas !== "number" || descargasHechas >= payload.maxDescargas) {
    return null;
  }
  return payload;
}
