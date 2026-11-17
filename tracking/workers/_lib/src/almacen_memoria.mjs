// Almacén clave->valor en memoria con la misma interfaz async que
// `DurableObjectStorage` (get/put). Lo usan las pruebas como doble de la
// Durable Object real (sin red, sin `node:` fuera de pruebas) y lo pueden
// reutilizar otros Workers que necesiten un Map inyectable.

export function crearAlmacenEnMemoria() {
  const mapa = new Map();
  return {
    async get(clave) {
      return mapa.has(clave) ? mapa.get(clave) : undefined;
    },
    async put(clave, valor) {
      mapa.set(clave, valor);
    },
    // Utilidad solo de pruebas: inspeccionar el tamaño sin exponer el Map.
    async tamano() {
      return mapa.size;
    },
  };
}
