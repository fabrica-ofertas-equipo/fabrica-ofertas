// Cuota diaria por visitante (docs/06 4.3: "cuota diaria max_sesiones_por_visitante
// en el Durable Object"). Logica pura sobre un almacen `{get,put}` inyectable
// (Durable Object real en produccion, Map en memoria en pruebas), igual
// patron que `dedupe.mjs` de `webhook-stripe`.

/**
 * Cuenta y registra una sesion nueva para `visitorId` en el bucket `diaUtc`
 * (cadena `AAAA-MM-DD`, UTC). `limite` DEBE ser un entero > 0 (parametro de
 * `parametros.landing.max_sesiones_por_visitante`; nunca fijo en el codigo).
 * Devuelve `{ permitido, conteo }`.
 */
export async function contarSesionYRegistrar(almacen, { visitorId, diaUtc, limite }) {
  if (!Number.isInteger(limite) || limite <= 0) {
    return { permitido: false, conteo: 0, motivo: "limite_invalido" };
  }
  const clave = `cuota:${visitorId}:${diaUtc}`;
  const actual = (await almacen.get(clave)) ?? 0;
  if (actual >= limite) {
    return { permitido: false, conteo: actual, motivo: "cuota_excedida" };
  }
  await almacen.put(clave, actual + 1);
  return { permitido: true, conteo: actual + 1 };
}

/** Bucket de dia UTC `AAAA-MM-DD` a partir de un `Date`. */
export function diaUtc(fecha) {
  return fecha.toISOString().slice(0, 10);
}
