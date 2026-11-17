// HMAC-SHA256 con Web Crypto, sin dependencias. Copia local y mínima para `watchdog` (cada Worker se
// despliega por separado; no se importa `tracking/workers/_lib` de otro dueño). Misma convención que
// `infra/firma_servicio.py` (Python): docs/06 §4.7, `X-Fabrica-Ts` + `X-Fabrica-Firma: hmac-sha256=<hex>`
// sobre `ts + "." + cuerpoExacto`.

const codificador = new TextEncoder();

function bufferAHex(buffer) {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function importarClaveHmac(secreto) {
  return crypto.subtle.importKey("raw", codificador.encode(secreto), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
}

async function firmarHex(secreto, mensaje) {
  const clave = await importarClaveHmac(secreto);
  const firma = await crypto.subtle.sign("HMAC", clave, codificador.encode(mensaje));
  return bufferAHex(firma);
}

/** Compara dos cadenas en tiempo constante (recorre siempre la longitud máxima). */
export function compararEnTiempoConstante(esperado, recibido) {
  if (typeof recibido !== "string") return false;
  const a = esperado;
  const b = recibido;
  const longitud = Math.max(a.length, b.length);
  let diferencia = a.length === b.length ? 0 : 1;
  for (let i = 0; i < longitud; i += 1) {
    const ca = i < a.length ? a.charCodeAt(i) : 0;
    const cb = i < b.length ? b.charCodeAt(i) : 0;
    diferencia |= ca ^ cb;
  }
  return diferencia === 0;
}

/** Verifica `X-Fabrica-Firma: hmac-sha256=<hex>` sobre `ts + "." + cuerpoExacto` (cuerpo = texto EXACTO recibido). */
export async function verificarFirmaInterna(secreto, cuerpoExacto, ts, firmaCabecera) {
  if (typeof firmaCabecera !== "string" || !firmaCabecera.startsWith("hmac-sha256=")) return false;
  const esperado = `hmac-sha256=${await firmarHex(secreto, `${ts}.${cuerpoExacto}`)}`;
  return compararEnTiempoConstante(esperado, firmaCabecera);
}
