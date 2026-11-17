// El POST de fulfill a /ingesta/entrega debe ir FIRMADO como pide docs/06 §4.7 (B3b lo detecto: sin firma, 401).
import test from "node:test";
import assert from "node:assert/strict";
import { construirCabecerasInternas, firmarHmacSha256Hex } from "../src/hmac.mjs";
import worker from "../src/index.mjs";

test("vector del contrato (sin contexto): secreto-de-ejemplo, ts y cuerpo fijos", async () => {
  const cuerpo = '{"etapa":"D1","oferta_id":"OF-202611-01"}';
  const cab = await construirCabecerasInternas("secreto-de-ejemplo", cuerpo, "2026-11-09T12:00:00Z");
  assert.equal(cab["X-Fabrica-Ts"], "2026-11-09T12:00:00Z");
  assert.equal(cab["X-Fabrica-Firma"], "hmac-sha256=d37d04267ad3153664bc993ac36a40ea09d854920339d5f6674d70b2d0594749");
});

test("el cuerpo distinto o el ts distinto cambian la firma", async () => {
  const a = await construirCabecerasInternas("k", "{}", "2026-11-09T12:00:00Z");
  const b = await construirCabecerasInternas("k", "{ }", "2026-11-09T12:00:00Z");
  const c = await construirCabecerasInternas("k", "{}", "2026-11-09T12:00:01Z");
  assert.notEqual(a["X-Fabrica-Firma"], b["X-Fabrica-Firma"]);
  assert.notEqual(a["X-Fabrica-Firma"], c["X-Fabrica-Firma"]);
});

async function entrada(secreto, cuerpo) {
  const ts = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  const firma = await firmarHmacSha256Hex(secreto, `${ts}.${cuerpo}`);
  return new Request("https://fulfill.example/", {
    method: "POST",
    headers: { "content-type": "application/json", "X-Fabrica-Ts": ts, "X-Fabrica-Firma": `hmac-sha256=${firma}` },
    body: cuerpo,
  });
}

test("el Worker firma el POST a /ingesta/entrega y el servicio api puede verificarlo", async () => {
  const envio = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, opciones) => {
    envio.push({ url: String(url), opciones });
    return new Response("{}", { status: 200 });
  };
  try {
    const secreto = "secreto-ingesta-de-prueba";
    const cuerpo = JSON.stringify({ session_id: "cs_test_1", oferta_id: "OF-202611-01", producto_version: "v1", producto_sha256: "sha256:" + "a".repeat(64), email: "a@b.co" });
    const kv = new Map();
    const env = {
      INGEST_HMAC_SECRET: secreto, API_BASE_URL: "https://api.example", DESCARGA_HMAC: "d", DESCARGA_BASE_URL: "https://d.example",
      ENTREGA_ENLACE_VENCE_DIAS: "7", ENTREGA_ENLACE_MAX_DESCARGAS: "3",
      ENTREGA_KV: { get: async (k) => kv.get(k) ?? null, put: async (k, v) => { kv.set(k, v); } },
    };
    const resp = await worker.fetch(await entrada(secreto, cuerpo), env);
    assert.ok(resp.status < 500, "estado " + resp.status);
    const aEntrega = envio.find((e) => e.url === "https://api.example/ingesta/entrega");
    assert.ok(aEntrega, "debe haber llamado a /ingesta/entrega");
    const h = aEntrega.opciones.headers || aEntrega.opciones.cabeceras;
    const ts = h["X-Fabrica-Ts"];
    assert.match(ts, /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/);
    const esperada = await firmarHmacSha256Hex(secreto, `${ts}.${aEntrega.opciones.body}`);
    assert.equal(h["X-Fabrica-Firma"], `hmac-sha256=${esperada}`);
  } finally {
    globalThis.fetch = original;
  }
});

test("sin INGEST_HMAC_SECRET el Worker NO envia nada sin firmar a /ingesta/entrega", async () => {
  const envio = [];
  const original = globalThis.fetch;
  globalThis.fetch = async (url, opciones) => { envio.push(String(url)); return new Response("{}", { status: 200 }); };
  try {
    const cuerpo = JSON.stringify({ session_id: "cs_test_2", oferta_id: "OF-202611-01", producto_version: "v1", producto_sha256: "sha256:" + "a".repeat(64), email: "a@b.co" });
    const kv = new Map();
    const env = { API_BASE_URL: "https://api.example", DESCARGA_HMAC: "d", DESCARGA_BASE_URL: "https://d.example", ENTREGA_KV: { get: async (k) => kv.get(k) ?? null, put: async (k, v) => { kv.set(k, v); } } };
    // Sin secreto tampoco puede autenticarse la entrada: el Worker rechaza antes (fail-closed) y no llama a la API.
    await worker.fetch(await entrada("otro", cuerpo), env);
    assert.equal(envio.filter((u) => u.includes("/ingesta/entrega")).length, 0);
  } finally {
    globalThis.fetch = original;
  }
});
