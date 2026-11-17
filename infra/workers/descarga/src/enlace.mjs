// Verificacion del enlace de descarga firmado: MISMO formato que
// infra/workers/fulfill/src/enlace.mjs (duplicado a proposito, docs/06 4.6: "valida el enlace firmado
// HMAC que genera fulfill/src/enlace.mjs ... reutiliza su formato EXACTO"; cada Worker se despliega
// por separado). `descarga` solo necesita verificar (nunca firma un enlace nuevo).

import { verificarHmacSha256 } from "./hmac.mjs";

const decodificador = new TextDecoder();

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
 * Verifica un token de `firmarEnlace` (fulfill). Devuelve el payload si la firma es valida, no
 * vencio (`ahora < venceEn`) y quedan descargas (`descargasHechas < maxDescargas`); si no, `null`.
 * `payload`: `{ sessionId, productoSha256, productoVersion, venceEn, maxDescargas }`.
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
