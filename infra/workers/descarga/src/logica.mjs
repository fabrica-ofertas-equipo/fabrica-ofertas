// Logica pura del Worker `descarga` (docs/06 4.3/4.6: "contador de descargas en KV, entrega desde
// R2, vencimiento y cuota como parametros"). El vencimiento (`venceEn`) y la cuota (`maxDescargas`)
// NUNCA son literales de este archivo: viajan DENTRO del token firmado por `fulfill` (que a su vez
// los toma de `ENTREGA_ENLACE_VENCE_DIAS`/`ENTREGA_ENLACE_MAX_DESCARGAS`, parametros por entorno);
// este Worker solo los LEE del payload verificado y los compara contra el reloj y el contador
// inyectados, sin fijar ningun valor propio.

import { verificarEnlace } from "./enlace.mjs";

const PREFIJO_CONTADOR = "descargas:";

/** Ultimo segmento no vacio de la ruta (`/d/<sessionId>` -> `sessionId`). */
export function sessionIdDeRuta(pathname) {
  const partes = String(pathname || "").split("/").filter(Boolean);
  return partes.length ? partes[partes.length - 1] : "";
}

/**
 * Maneja una descarga. Entradas:
 * - `sessionIdRuta`: segmento de la URL (`/d/<sessionId>`).
 * - `token`: query param `?token=`.
 * - `secreto`: `DESCARGA_HMAC`.
 * - `ahora`: `() => Date` inyectable.
 * - `contador.obtener(sessionId) -> Promise<number>` / `contador.incrementar(sessionId) -> Promise<void>`:
 *   contador de descargas (KV real o fake de prueba).
 * - `bucket.obtener(productoSha256) -> Promise<objeto|null>`: entrega (R2 real o fake de prueba).
 *
 * Devuelve `{ status, cuerpo }` (error JSON) o `{ status: 200, binario, codigo: "entregado" }`.
 */
export async function manejarDescarga({ sessionIdRuta, token, secreto, ahora, contador, bucket }) {
  if (!sessionIdRuta || typeof token !== "string" || !token) {
    return { status: 400, cuerpo: { ok: false, codigo: "parametros_ausentes" } };
  }
  if (!secreto) {
    return { status: 500, cuerpo: { ok: false, codigo: "sin_configuracion" } };
  }
  const descargasHechas = await contador.obtener(sessionIdRuta);
  const payload = await verificarEnlace(token, secreto, { ahora: ahora(), descargasHechas });
  if (!payload) {
    return { status: 403, cuerpo: { ok: false, codigo: "enlace_invalido_o_vencido" } };
  }
  if (payload.sessionId !== sessionIdRuta) {
    return { status: 403, cuerpo: { ok: false, codigo: "enlace_no_corresponde_a_la_sesion" } };
  }
  const objeto = await bucket.obtener(payload.productoSha256);
  if (!objeto) {
    return { status: 404, cuerpo: { ok: false, codigo: "producto_no_encontrado" } };
  }
  // Se incrementa DESPUES de validar y encontrar el objeto (una descarga que falla antes de servir
  // el archivo no debe consumir cuota), pero ANTES de devolver la respuesta (mejor esfuerzo: no hay
  // forma de saber si el cliente recibio el cuerpo completo; ver README "Decisiones" sobre la
  // ausencia de atomicidad del KV frente a descargas concurrentes de la misma sesion).
  await contador.incrementar(sessionIdRuta);
  return { status: 200, binario: objeto, codigo: "entregado" };
}

/** Contador de descargas sobre un KV real o fake (misma interfaz en ambos casos). */
export function crearContadorKv(kv) {
  return {
    async obtener(sessionId) {
      const v = await kv.get(PREFIJO_CONTADOR + sessionId);
      return v ? Number.parseInt(v, 10) : 0;
    },
    async incrementar(sessionId) {
      const v = await kv.get(PREFIJO_CONTADOR + sessionId);
      const actual = v ? Number.parseInt(v, 10) : 0;
      await kv.put(PREFIJO_CONTADOR + sessionId, String(actual + 1));
    },
  };
}

/** Entrega sobre un bucket R2 real o fake (misma interfaz: `get(clave) -> objeto|null`). */
export function crearBucketR2(bucket) {
  return { async obtener(clave) { return bucket.get(clave); } };
}
