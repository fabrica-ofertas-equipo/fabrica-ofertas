// Validacion de la solicitud de `POST /api/sesion` (docs/06 4.3, checkout.schema.json).
import {
  esOfertaIdValido,
  esVisitorIdValido,
  esIdAtribucionValido,
  esFbpValido,
  esFbcValido,
  esConsentMarketingValido,
} from "../../_lib/src/formatos.mjs";

/**
 * Valida la forma basica del cuerpo. Devuelve `{ ok, errores: string[] }`.
 * No valida pertenencia al catalogo (eso es `catalogo.mjs`, porque requiere
 * el catalogo firmado ya cargado).
 */
export function validarCuerpoSesion(cuerpo) {
  const errores = [];
  if (!cuerpo || typeof cuerpo !== "object") {
    return { ok: false, errores: ["cuerpo_invalido"] };
  }
  if (!esOfertaIdValido(cuerpo.oferta_id)) errores.push("oferta_id_invalido");
  if (!esVisitorIdValido(cuerpo.visitor_id)) errores.push("visitor_id_invalido");
  if (typeof cuerpo.bump !== "boolean") errores.push("bump_invalido");
  if (!esConsentMarketingValido(cuerpo.consent_marketing)) errores.push("consent_marketing_invalido");
  if (typeof cuerpo.landing_version !== "string" || cuerpo.landing_version.length === 0) {
    errores.push("landing_version_invalido");
  }
  const params = cuerpo.params ?? {};
  if (params.fbp !== undefined && params.fbp !== null && !esFbpValido(params.fbp)) {
    errores.push("fbp_invalido");
  }
  if (params.fbc !== undefined && params.fbc !== null && !esFbcValido(params.fbc)) {
    errores.push("fbc_invalido");
  }
  return { ok: errores.length === 0, errores };
}

/**
 * Valida el formato (`^[0-9]{6,20}$`) de cid/asid/adid, SIN comprobar
 * pertenencia al catalogo (eso decide si se reemplaza por "desconocido",
 * no si la solicitud se rechaza: docs/06 4.3).
 */
export function formatoIdAtribucionValido(valor) {
  return valor === undefined || valor === null || esIdAtribucionValido(valor);
}

// --- Modo formulario (docs/_historial/decision-arranque-de-pago.md) ---
// Lista CERRADA de campos: cualquier otro campo en el cuerpo
// `application/x-www-form-urlencoded` -> 400 y no se crea sesion.
export const CAMPOS_FORMULARIO_BASE = Object.freeze(["oferta_id", "locale", "bump", "renuncia_desistimiento"]);
export const CAMPO_FORMULARIO_TURNSTILE = "cf-turnstile-response";

/**
 * Valida que `campos` (objeto plano con los nombres tal cual llegaron del
 * `application/x-www-form-urlencoded`) use SOLO los nombres permitidos y
 * que `oferta_id`/`locale` tengan forma valida. `turnstileHabilitado`
 * decide si `cf-turnstile-response` esta en la lista permitida (Turnstile
 * queda fuera de v1: por defecto esa bandera esta apagada).
 */
export function validarCamposFormulario(campos, { turnstileHabilitado }) {
  const permitidos = turnstileHabilitado
    ? [...CAMPOS_FORMULARIO_BASE, CAMPO_FORMULARIO_TURNSTILE]
    : CAMPOS_FORMULARIO_BASE;
  const nombresRecibidos = Object.keys(campos ?? {});
  const extra = nombresRecibidos.filter((nombre) => !permitidos.includes(nombre));
  if (extra.length > 0) {
    return { ok: false, errores: ["campo_no_permitido"] };
  }
  const errores = [];
  if (!esOfertaIdValido(campos?.oferta_id)) errores.push("oferta_id_invalido");
  if (typeof campos?.locale !== "string" || campos.locale.length === 0) {
    errores.push("locale_invalido");
  }
  return { ok: errores.length === 0, errores };
}

/** `"on"` (casilla marcada) -> `true`; ausente o cualquier otro valor -> `false`. */
export function casillaABooleano(valor) {
  return valor === "on";
}
