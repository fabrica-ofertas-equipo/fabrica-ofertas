// Cookies del modo formulario (docs/_historial/decision-arranque-de-pago.md §2.3):
// `fab_vid` (visitor_id), `fab_attr` (utm_*, cid, asid, adid), `_fbp`, `_fbc`.
// Todas son del MISMO origen (las escribe `consentimiento.js`, B4) y se leen
// tal cual estan: una cookie malformada se IGNORA (nunca 500).
//
// Formato CANONICO de `fab_attr` (decision de S-A, 2026-11-06; lo escribe consentimiento.js):
// `k=v&k=v` percent-encoded (application/x-www-form-urlencoded), claves `utm_source`, `utm_medium`,
// `utm_campaign`, `utm_content`, `utm_term`, `cid`, `asid`, `adid` (IDs `^[0-9]{6,20}$`) y `fbclid`
// opcional; MAXIMO 400 bytes (si lo excede se ignora la cookie entera); cualquier otra clave se
// descarta (un campo ausente o invalido se trata por campo, no rechaza la cookie completa).
// `fab_vid` = 128 bits aleatorios en hexadecimal (32 caracteres; cumple `esVisitorIdValido`).

import { esVisitorIdValido, esFbpValido, esFbcValido, esIdAtribucionValido } from "../../_lib/src/formatos.mjs";

/** Parsea la cabecera `Cookie` a un mapa `{nombre: valor}` (valores SIN decodificar). */
export function parsearCabeceraCookie(cabeceraCookie) {
  const mapa = {};
  if (typeof cabeceraCookie !== "string" || cabeceraCookie.length === 0) return mapa;
  for (const parte of cabeceraCookie.split(";")) {
    const i = parte.indexOf("=");
    if (i === -1) continue;
    const nombre = parte.slice(0, i).trim();
    const valor = parte.slice(i + 1).trim();
    if (nombre) mapa[nombre] = valor;
  }
  return mapa;
}

/** `fab_vid` valido, o `null` si esta ausente o malformado (nunca lanza). */
export function visitorIdDeCookie(mapaCookies) {
  const valor = mapaCookies.fab_vid;
  if (valor === undefined) return null;
  try {
    const decodificado = decodeURIComponent(valor);
    return esVisitorIdValido(decodificado) ? decodificado : null;
  } catch {
    return null;
  }
}

/** Tope en BYTES de la cookie `fab_attr` (formato canonico de S-A). */
export const FAB_ATTR_MAX_BYTES = 400;
const CLAVES_UTM = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"];
const CLAVES_ID = ["cid", "asid", "adid"];

/**
 * `fab_attr` (`k=v&k=v` percent-encoded) a `{utm_*, cid, asid, adid}`. `fbclid` se acepta pero NO se
 * propaga (el click id de Meta llega por `_fbc`). Cada campo invalido o ajeno se omite; una cookie de mas de
 * 400 bytes se ignora entera (`{}`); nunca lanza. Con una clave repetida manda la primera.
 */
export function paramsDeCookie(mapaCookies) {
  const valor = mapaCookies.fab_attr;
  if (typeof valor !== "string" || valor.length === 0) return {};
  if (new TextEncoder().encode(valor).length > FAB_ATTR_MAX_BYTES) return {};
  let pares;
  try {
    pares = new URLSearchParams(valor);
  } catch {
    return {};
  }
  const resultado = {};
  for (const clave of CLAVES_UTM) {
    const v = pares.get(clave);
    if (typeof v === "string" && v.length > 0) resultado[clave] = v;
  }
  for (const clave of CLAVES_ID) {
    const v = pares.get(clave);
    if (esIdAtribucionValido(v)) resultado[clave] = v;
  }
  return resultado;
}

/** `_fbp` valido o `undefined` (nunca rechaza la solicitud por esto). */
export function fbpDeCookie(mapaCookies) {
  const valor = mapaCookies._fbp;
  if (valor === undefined) return undefined;
  try {
    const decodificado = decodeURIComponent(valor);
    return esFbpValido(decodificado) ? decodificado : undefined;
  } catch {
    return undefined;
  }
}

/** `_fbc` valido o `undefined` (nunca rechaza la solicitud por esto). */
export function fbcDeCookie(mapaCookies) {
  const valor = mapaCookies._fbc;
  if (valor === undefined) return undefined;
  try {
    const decodificado = decodeURIComponent(valor);
    return esFbcValido(decodificado) ? decodificado : undefined;
  } catch {
    return undefined;
  }
}

/**
 * `visitor_id` aleatorio criptografico cuando no hay `fab_vid` (o esta
 * malformada): NO se pone cookie alguna (docs/_historial/decision-arranque-de-pago.md).
 * `crypto.randomUUID()` sin guiones cumple `^[A-Za-z0-9_-]{16,64}$` (32 hex).
 */
export function generarVisitorIdAleatorio() {
  return globalThis.crypto.randomUUID().replace(/-/g, "");
}
