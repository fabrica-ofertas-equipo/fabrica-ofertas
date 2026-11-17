// Deduplicacion de eventos de Stripe (docs/06 4.3 y 4.8): por `event.id` Y
// por `(tipo, objeto_id)` -- Stripe puede emitir dos `Event` distintos para
// el mismo hecho (reenvios, reintentos). La decision NO se toma en KV (no es
// atomica): vive en una Durable Object por `session_id` (aqui, logica pura
// sobre un `almacen` inyectable con interfaz `{ get(clave), put(clave, valor) }`,
// la misma que expone `DurableObjectStorage` y el `almacenEnMemoria` de
// pruebas). Sin await entre el `get` y el `put`: una Durable Object real
// procesa sus solicitudes una por una (single-threaded), asi que esta forma
// es atomica en produccion y tambien en las pruebas con el almacen en
// memoria (sin ceder el control del bucle de eventos entre ambas lecturas).

/**
 * Registra el evento si es nuevo. Devuelve `{ duplicado: boolean }`.
 * Comprueba PRIMERO ambas claves (event.id y tipo+objeto_id) y solo
 * despues escribe, para no marcar nada si cualquiera ya existia.
 */
export async function registrarSiEsNuevo(almacen, { eventId, tipo, objetoId }) {
  const claveEvento = `evt:${eventId}`;
  const claveTipoObjeto = `to:${tipo}:${objetoId}`;
  const [porEvento, porTipoObjeto] = await Promise.all([
    almacen.get(claveEvento),
    almacen.get(claveTipoObjeto),
  ]);
  if (porEvento || porTipoObjeto) {
    return { duplicado: true };
  }
  await Promise.all([
    almacen.put(claveEvento, true),
    almacen.put(claveTipoObjeto, true),
  ]);
  return { duplicado: false };
}
