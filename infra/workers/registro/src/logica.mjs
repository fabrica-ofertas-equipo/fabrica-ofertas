// logica.mjs — reglas puras del registro de ofertas tomadas (sin red ni base).

/** Días que dura cada reserva si nadie la renueva. Una oferta lanzada queda tomada un año. */
export const VIGENCIA_DIAS = { banco: 21, modelando: 14, lanzada: 365 };
export const ESTADOS = Object.keys(VIGENCIA_DIAS);
const HUELLA = /^[0-9a-f]{64}$/;
export const MAX_LOTE = 200;

export function huellaValida(h) { return typeof h === "string" && HUELLA.test(h); }

export function vence(estado, ahora) {
  return new Date(ahora.getTime() + VIGENCIA_DIAS[estado] * 86400000).toISOString();
}

/** Una reserva vigente de OTRA instalación bloquea; una vencida o propia, no. */
export function tomadaPorOtra(reserva, instalacion, ahora) {
  return Boolean(reserva) && reserva.instalacion !== instalacion && reserva.vence > ahora.toISOString();
}

/** El estado nunca baja: lanzada > modelando > banco (renovar «banco» no le quita lo lanzado a una oferta propia). */
export function estadoResultante(previo, nuevo) {
  const rango = { banco: 0, modelando: 1, lanzada: 2 };
  if (!previo || !(previo in rango)) return nuevo;
  return rango[nuevo] >= rango[previo] ? nuevo : previo;
}

export async function sha256Hex(texto) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(texto));
  return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

export function tokenDe(cabecera) {
  const m = /^Bearer\s+(.+)$/.exec(String(cabecera || ""));
  return m ? m[1].trim() : null;
}

/** Valida el cuerpo de /reservar: { items: [{ huella, estado }] }. */
export function itemsValidos(cuerpo) {
  const items = cuerpo && Array.isArray(cuerpo.items) ? cuerpo.items : null;
  if (!items || !items.length || items.length > MAX_LOTE) return null;
  for (const it of items) if (!huellaValida(it.huella) || !ESTADOS.includes(it.estado)) return null;
  return items;
}

export function huellasValidas(cuerpo) {
  const h = cuerpo && Array.isArray(cuerpo.huellas) ? cuerpo.huellas : null;
  if (!h || !h.length || h.length > MAX_LOTE || !h.every(huellaValida)) return null;
  return h;
}
