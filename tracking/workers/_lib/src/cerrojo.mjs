// Cerrojo (mutex) asincrono minimo, sin dependencias. Modela la garantia de
// una Durable Object de Cloudflare cuando sus mutaciones de almacenamiento
// se envuelven en `blockConcurrencyWhile` (o `storage.transaction`): las
// tareas puestas en la cola se ejecutan una detras de otra, nunca
// entrelazadas, aunque quien llama las dispare "al mismo tiempo". Se usa
// tanto en produccion (una instancia de cerrojo por Durable Object) como en
// las pruebas de "dos entregas concurrentes" / "dos hilos", donde reemplaza
// a una Durable Object real (que `node --test` no puede instanciar).
export function crearCerrojo() {
  let colaActual = Promise.resolve();
  return {
    ejecutar(tarea) {
      const resultado = colaActual.then(() => tarea());
      colaActual = resultado.then(
        () => undefined,
        () => undefined,
      );
      return resultado;
    },
  };
}
