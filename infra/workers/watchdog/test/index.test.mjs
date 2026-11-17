import test from "node:test";
import assert from "node:assert/strict";

import { manejarPeticion } from "../src/index.mjs";

class KVFalso {
  constructor(inicial = {}) {
    this.datos = new Map(Object.entries(inicial));
  }

  async get(clave) {
    return this.datos.has(clave) ? this.datos.get(clave) : null;
  }

  async put(clave, valor) {
    this.datos.set(clave, valor);
  }
}

async function firmarHex(secreto, mensaje) {
  const codificador = new TextEncoder();
  const clave = await crypto.subtle.importKey("raw", codificador.encode(secreto), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const firma = await crypto.subtle.sign("HMAC", clave, codificador.encode(mensaje));
  return Array.from(new Uint8Array(firma)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

async function peticionFirmada(url, cuerpoObj, secreto, ts) {
  const cuerpo = JSON.stringify(cuerpoObj);
  const firma = `hmac-sha256=${await firmarHex(secreto, `${ts}.${cuerpo}`)}`;
  return new Request(url, {
    method: "POST", body: cuerpo,
    headers: { "X-Fabrica-Ts": ts, "X-Fabrica-Firma": firma, "content-type": "application/json" },
  });
}

test("ninguna ruta activa nada: /activar no existe (404)", async () => {
  const env = { ESTADO: new KVFalso() };
  const resp = await manejarPeticion(new Request("https://watchdog.ejemplo/activar", { method: "POST" }), env);
  assert.equal(resp.status, 404);
});

test("GET /latido no esta permitido (405)", async () => {
  const env = { ESTADO: new KVFalso() };
  const resp = await manejarPeticion(new Request("https://watchdog.ejemplo/latido", { method: "GET" }), env);
  assert.equal(resp.status, 405);
});

test("POST /latido con firma invalida: 401", async () => {
  const env = { ESTADO: new KVFalso(), LATIDO_HMAC: "clave-real" };
  const ts = new Date().toISOString();
  const req = await peticionFirmada("https://watchdog.ejemplo/latido", { ts, semaforo: "VERDE", pausa: false }, "clave-equivocada", ts);
  const resp = await manejarPeticion(req, env);
  assert.equal(resp.status, 401);
});

test("POST /latido con firma valida: 200 y guarda en KV", async () => {
  const kv = new KVFalso();
  const env = { ESTADO: kv, LATIDO_HMAC: "clave-real" };
  const ts = new Date().toISOString();
  const payload = { ts, semaforo: "VERDE", pausa: false, estado_generado_en: ts, version: "1" };
  const req = await peticionFirmada("https://watchdog.ejemplo/latido", payload, "clave-real", ts);
  const resp = await manejarPeticion(req, env);
  assert.equal(resp.status, 200);
  assert.equal(await kv.get("latido:ultimo"), JSON.stringify(payload));
});

test("POST /latido con ts fuera de tolerancia: 400", async () => {
  const env = { ESTADO: new KVFalso(), LATIDO_HMAC: "clave-real" };
  const tsViejo = "2020-01-01T00:00:00.000Z";
  const req = await peticionFirmada("https://watchdog.ejemplo/latido", { ts: tsViejo }, "clave-real", tsViejo);
  const resp = await manejarPeticion(req, env);
  assert.equal(resp.status, 400);
});

test("GET /estado sin GASTO_DIARIO_MAX_MINOR ni CUENTA_TZ: 503 (nunca se omite)", async () => {
  const env = { ESTADO: new KVFalso() };
  const resp = await manejarPeticion(new Request("https://watchdog.ejemplo/estado", { method: "GET" }), env);
  assert.equal(resp.status, 503);
});

test("GET /estado con variables obligatorias presentes: 200 con visto_hace_min", async () => {
  const ahoraFija = new Date("2026-11-09T08:00:00Z");
  const kv = new KVFalso({ "watchdog:visto": "2026-11-09T07:57:00Z" });
  const env = { ESTADO: kv, GASTO_DIARIO_MAX_MINOR: "1000", CUENTA_TZ: "Europe/Madrid" };
  const resp = await manejarPeticion(new Request("https://watchdog.ejemplo/estado", { method: "GET" }), env, { ahora: () => ahoraFija });
  assert.equal(resp.status, 200);
  const cuerpo = await resp.json();
  assert.equal(cuerpo.visto_hace_min, 3);
  assert.equal(cuerpo.pausa, false);
});

test("POST /pausa con firma valida marca pausa:global", async () => {
  const kv = new KVFalso();
  const env = { ESTADO: kv, LATIDO_HMAC: "clave-real" };
  const ts = new Date().toISOString();
  const req = await peticionFirmada("https://watchdog.ejemplo/pausa", { motivo: "A-1", ts }, "clave-real", ts);
  const resp = await manejarPeticion(req, env);
  assert.equal(resp.status, 200);
  assert.equal(await kv.get("pausa:global"), "true");
});

test("POST /pausa sin firma valida: 401 y no marca nada", async () => {
  const kv = new KVFalso();
  const env = { ESTADO: kv, LATIDO_HMAC: "clave-real" };
  const resp = await manejarPeticion(new Request("https://watchdog.ejemplo/pausa", { method: "POST", body: "{}" }), env);
  assert.equal(resp.status, 401);
  assert.equal(await kv.get("pausa:global"), null);
});
