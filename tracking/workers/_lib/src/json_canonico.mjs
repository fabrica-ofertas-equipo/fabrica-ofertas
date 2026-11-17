// JSON canónico (convenciones de código §5): claves ordenadas recursivamente,
// sin espacios, sin float. Implementación mínima para Workers (sin dependencias).

function ordenarClaves(valor) {
  if (Array.isArray(valor)) {
    return valor.map(ordenarClaves);
  }
  if (valor !== null && typeof valor === "object") {
    const claves = Object.keys(valor).sort();
    const salida = {};
    for (const clave of claves) {
      salida[clave] = ordenarClaves(valor[clave]);
    }
    return salida;
  }
  if (typeof valor === "number" && !Number.isInteger(valor)) {
    throw new TypeError("json_canonico: prohibido un float; use entero o cadena decimal");
  }
  return valor;
}

/** Serializa un valor a JSON canónico (claves ordenadas, sin espacios, sin float). */
export function jsonCanonico(valor) {
  return JSON.stringify(ordenarClaves(valor));
}
