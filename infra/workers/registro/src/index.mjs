// index.mjs — worker «fabrica-registro»: registro compartido de ofertas tomadas entre instalaciones de la fábrica.
//
// Rutas (todas con Authorization: Bearer <token de la instalación>, salvo /salud):
//   POST /consultar  { huellas: [...] }            → { tomadas: [...] }  las que tiene OTRA instalación (sin decir cuál)
//   POST /reservar   { items: [{huella, estado}] } → { resultado: { huella: "ok" | "tomada" } }  el primero que llega se la queda
//   POST /liberar    { huellas: [...] }            → { liberadas: n }   solo las propias
//   GET  /salud                                     → { ok: true }       público, sin datos
// Estados: banco (21 días), modelando (14), lanzada (365). Renovar una reserva propia la extiende.
// La instalación sale del token (tabla instalaciones, guardado como sha256), nunca del cuerpo.

import { tomadaPorOtra, estadoResultante, vence, sha256Hex, tokenDe, itemsValidos, huellasValidas } from "./logica.mjs";

const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });

export function almacenD1(db) {
  return {
    async instalacionDe(tokenHash) {
      const r = await db.prepare("SELECT id FROM instalaciones WHERE token_hash = ? AND activa = 1").bind(tokenHash).first();
      return r ? r.id : null;
    },
    async reservas(huellas) {
      if (!huellas.length) return new Map();
      const filas = (await db.prepare(`SELECT * FROM reservas WHERE huella IN (${huellas.map(() => "?").join(",")})`).bind(...huellas).all()).results || [];
      return new Map(filas.map((f) => [f.huella, f]));
    },
    async guardar(filas) {
      if (!filas.length) return;
      await db.batch(filas.map((f) => db.prepare(`INSERT INTO reservas (huella, instalacion, estado, creada, actualizada, vence) VALUES (?,?,?,?,?,?)
        ON CONFLICT(huella) DO UPDATE SET instalacion=excluded.instalacion, estado=excluded.estado, actualizada=excluded.actualizada, vence=excluded.vence`)
        .bind(f.huella, f.instalacion, f.estado, f.creada, f.actualizada, f.vence)));
    },
    async liberar(huellas, instalacion) {
      let n = 0;
      for (const h of huellas) {
        const r = await db.prepare("DELETE FROM reservas WHERE huella = ? AND instalacion = ?").bind(h, instalacion).run();
        n += (r && r.meta && r.meta.changes) || (r && r.changes) || 0;
      }
      return n;
    },
  };
}

export async function manejarPeticion(req, env, almacen, { ahora = new Date() } = {}) {
  const url = new URL(req.url);
  if (url.pathname === "/salud") return json({ ok: true });
  if (!["/consultar", "/reservar", "/liberar"].includes(url.pathname)) return json({ error: "no_existe" }, 404);
  if (req.method !== "POST") return json({ error: "metodo" }, 405);
  const token = tokenDe(req.headers.get("authorization"));
  const instalacion = token ? await almacen.instalacionDe(await sha256Hex(token)) : null;
  if (!instalacion) return json({ error: "no_autorizado" }, 401);
  let cuerpo;
  try { cuerpo = await req.json(); } catch (_) { return json({ error: "json" }, 400); }

  if (url.pathname === "/consultar") {
    const huellas = huellasValidas(cuerpo);
    if (!huellas) return json({ error: "huellas" }, 400);
    const rs = await almacen.reservas(huellas);
    return json({ tomadas: huellas.filter((h) => tomadaPorOtra(rs.get(h), instalacion, ahora)) });
  }
  if (url.pathname === "/reservar") {
    const items = itemsValidos(cuerpo);
    if (!items) return json({ error: "items" }, 400);
    const rs = await almacen.reservas([...new Set(items.map((i) => i.huella))]);
    const resultado = {}, filas = [], iso = ahora.toISOString();
    for (const it of items) {
      const previa = rs.get(it.huella);
      if (tomadaPorOtra(previa, instalacion, ahora)) { resultado[it.huella] = "tomada"; continue; }
      const propia = previa && previa.instalacion === instalacion && previa.vence > iso;
      const estado = propia ? estadoResultante(previa.estado, it.estado) : it.estado;
      const fila = { huella: it.huella, instalacion, estado, creada: propia ? previa.creada : iso, actualizada: iso, vence: vence(estado, ahora) };
      rs.set(it.huella, fila); filas.push(fila); resultado[it.huella] = "ok";
    }
    await almacen.guardar(filas);
    return json({ resultado });
  }
  const huellas = huellasValidas(cuerpo);
  if (!huellas) return json({ error: "huellas" }, 400);
  return json({ liberadas: await almacen.liberar(huellas, instalacion) });
}

export default {
  async fetch(req, env) {
    return manejarPeticion(req, env, almacenD1(env.DB));
  },
};
