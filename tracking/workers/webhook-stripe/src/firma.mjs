// Verificacion de la firma de webhooks de Stripe (docs/07 2.3; docs/06 4.3):
// cabecera `Stripe-Signature: t=<timestamp>,v1=<hex>[,v1=<hex>...]`, cuerpo
// CRUDO (sin volver a serializar), tolerancia parametrica (`STRIPE_TOLERANCIA_SEG`,
// NUNCA 0). Reimplementa el algoritmo documentado de Stripe con
// `crypto.subtle` (sin dependencias): firma = HMAC-SHA256(whsec, `${t}.${cuerpo}`).

import { firmarHmacSha256Hex, compararHexEnTiempoConstante } from "../../_lib/src/hmac.mjs";

/** Parsea `t=...,v1=...,v1=...` en `{ t, firmas: string[] }`. Null si el formato no sirve. */
export function parsearCabeceraFirma(cabecera) {
  if (typeof cabecera !== "string" || cabecera.length === 0) return null;
  let t = null;
  const firmas = [];
  for (const parte of cabecera.split(",")) {
    const [clave, valor] = parte.split("=", 2).map((s) => (s === undefined ? "" : s.trim()));
    if (clave === "t") t = valor;
    if (clave === "v1" && valor) firmas.push(valor);
  }
  if (!t || firmas.length === 0) return null;
  return { t, firmas };
}

/**
 * Verifica la firma de Stripe contra el cuerpo crudo exacto. `toleranciaSeg`
 * DEBE ser un entero > 0 (convenciones 3: "tolerancia != 0"); si no lo es,
 * se rechaza TODO como configuracion invalida (fail-closed), nunca se asume
 * un valor por defecto en el codigo (convenciones 3, "ningun... fijo").
 *
 * Devuelve `{ valida, motivo? }`.
 */
export async function verificarFirmaStripe({
  cabeceraFirma,
  cuerpoCrudo,
  secretoWhsec,
  ahoraEpochSeg,
  toleranciaSeg,
}) {
  if (!Number.isInteger(toleranciaSeg) || toleranciaSeg <= 0) {
    return { valida: false, motivo: "tolerancia_invalida" };
  }
  const parsed = parsearCabeceraFirma(cabeceraFirma);
  if (!parsed) {
    return { valida: false, motivo: "cabecera_invalida" };
  }
  const { t, firmas } = parsed;
  const tNum = Number(t);
  if (!Number.isFinite(tNum)) {
    return { valida: false, motivo: "timestamp_invalido" };
  }
  const esperado = await firmarHmacSha256Hex(secretoWhsec, `${t}.${cuerpoCrudo}`);
  const algunaCoincide = firmas.some((firma) => compararHexEnTiempoConstante(esperado, firma));
  if (!algunaCoincide) {
    return { valida: false, motivo: "firma_no_coincide" };
  }
  if (Math.abs(ahoraEpochSeg - tNum) > toleranciaSeg) {
    return { valida: false, motivo: "fuera_de_tolerancia" };
  }
  return { valida: true };
}
