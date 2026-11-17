// Validadores de formato compartidos (docs/06 §4.3; contratos/comunes.schema.json).
// Todos usan coincidencia COMPLETA (equivalente a re.fullmatch): sin ^$ no bastaría
// con .test() si hubiera saltos de línea, por eso las cadenas se validan tal cual.

export const PATRON_OFERTA_ID = /^OF-[0-9]{6}-[0-9]{2}$/;
export const PATRON_VISITOR_ID = /^[A-Za-z0-9_-]{16,64}$/;
export const PATRON_ID_ATRIBUCION = /^[0-9]{6,20}$/; // cid, asid, adid
export const PATRON_FBP = /^fb\.[0-9]\.[0-9]{10,13}\.[0-9]+$/;
export const PATRON_FBC = /^fb\.[0-9]\.[0-9]{10,13}\..+$/;
export const PATRON_TIMESTAMP_Z = /^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])T([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]Z$/;

export function esOfertaIdValido(valor) {
  return typeof valor === "string" && PATRON_OFERTA_ID.test(valor);
}

export function esVisitorIdValido(valor) {
  return typeof valor === "string" && PATRON_VISITOR_ID.test(valor);
}

export function esIdAtribucionValido(valor) {
  return typeof valor === "string" && PATRON_ID_ATRIBUCION.test(valor);
}

export function esFbpValido(valor) {
  return typeof valor === "string" && PATRON_FBP.test(valor);
}

export function esFbcValido(valor) {
  return typeof valor === "string" && PATRON_FBC.test(valor);
}

export function esTimestampZValido(valor) {
  return typeof valor === "string" && PATRON_TIMESTAMP_Z.test(valor);
}

export function esConsentMarketingValido(valor) {
  return valor === "1" || valor === "0";
}
