import test from "node:test";
import assert from "node:assert/strict";

import { sha256Hex, sha256Prefijado } from "../src/hash.mjs";
import { jsonCanonico } from "../src/json_canonico.mjs";
import {
  firmarHmacSha256Hex,
  verificarHmacSha256,
  compararHexEnTiempoConstante,
  construirCabecerasInternas,
} from "../src/hmac.mjs";
import { verificarEd25519Cruda } from "../src/ed25519.mjs";
import {
  esOfertaIdValido,
  esVisitorIdValido,
  esIdAtribucionValido,
  esFbpValido,
  esFbcValido,
  esTimestampZValido,
  esConsentMarketingValido,
} from "../src/formatos.mjs";
import { crearAlmacenEnMemoria } from "../src/almacen_memoria.mjs";
import { crearCerrojo } from "../src/cerrojo.mjs";

test("sha256Hex produce 64 hex deterministas", async () => {
  const a = await sha256Hex("hola");
  const b = await sha256Hex("hola");
  assert.equal(a, b);
  assert.match(a, /^[0-9a-f]{64}$/);
});

test("sha256Prefijado antepone sha256:", async () => {
  const valor = await sha256Prefijado("x");
  assert.match(valor, /^sha256:[0-9a-f]{64}$/);
});

test("jsonCanonico ordena claves recursivamente sin espacios", () => {
  const salida = jsonCanonico({ b: 2, a: { d: 4, c: 3 } });
  assert.equal(salida, '{"a":{"c":3,"d":4},"b":2}');
});

test("jsonCanonico rechaza float", () => {
  assert.throws(() => jsonCanonico({ monto: 1.5 }), TypeError);
});

test("HMAC: firma y verifica correctamente", async () => {
  const firma = await firmarHmacSha256Hex("secreto", "mensaje");
  assert.equal(await verificarHmacSha256("secreto", "mensaje", firma), true);
});

test("HMAC: firma falsa no verifica", async () => {
  const firma = await firmarHmacSha256Hex("secreto", "mensaje");
  const falsa = `${firma.slice(0, -1)}${firma.endsWith("0") ? "1" : "0"}`;
  assert.equal(await verificarHmacSha256("secreto", "mensaje", falsa), false);
});

test("HMAC: mensaje alterado no verifica", async () => {
  const firma = await firmarHmacSha256Hex("secreto", "mensaje");
  assert.equal(await verificarHmacSha256("secreto", "otro-mensaje", firma), false);
});

test("compararHexEnTiempoConstante: longitudes distintas no son iguales", () => {
  assert.equal(compararHexEnTiempoConstante("ab", "abcd"), false);
});

test("compararHexEnTiempoConstante: entrada no hexadecimal es falsa", () => {
  assert.equal(compararHexEnTiempoConstante("ab", "zz"), false);
});

test("construirCabecerasInternas firma ts + '.' + cuerpo", async () => {
  const cabeceras = await construirCabecerasInternas("secreto", '{"a":1}', "2026-11-06T00:00:00Z");
  assert.equal(cabeceras["X-Fabrica-Ts"], "2026-11-06T00:00:00Z");
  assert.match(cabeceras["X-Fabrica-Firma"], /^hmac-sha256=[0-9a-f]{64}$/);
  const esperado = await firmarHmacSha256Hex("secreto", "2026-11-06T00:00:00Z.{\"a\":1}");
  assert.equal(cabeceras["X-Fabrica-Firma"], `hmac-sha256=${esperado}`);
});

test("Ed25519: firma válida verifica (par de claves generado en la prueba)", async () => {
  const par = await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"]);
  const mensaje = "orden de prueba";
  const firmaBuffer = await crypto.subtle.sign(
    { name: "Ed25519" },
    par.privateKey,
    new TextEncoder().encode(mensaje),
  );
  const claveRaw = await crypto.subtle.exportKey("raw", par.publicKey);
  const claveB64 = Buffer.from(claveRaw).toString("base64");
  const firmaB64 = Buffer.from(firmaBuffer).toString("base64");
  assert.equal(await verificarEd25519Cruda(claveB64, mensaje, firmaB64), true);
});

test("Ed25519: firma de otro mensaje no verifica", async () => {
  const par = await crypto.subtle.generateKey({ name: "Ed25519" }, true, ["sign", "verify"]);
  const firmaBuffer = await crypto.subtle.sign(
    { name: "Ed25519" },
    par.privateKey,
    new TextEncoder().encode("mensaje A"),
  );
  const claveRaw = await crypto.subtle.exportKey("raw", par.publicKey);
  const claveB64 = Buffer.from(claveRaw).toString("base64");
  const firmaB64 = Buffer.from(firmaBuffer).toString("base64");
  assert.equal(await verificarEd25519Cruda(claveB64, "mensaje B", firmaB64), false);
});

test("Ed25519: entrada malformada no lanza y devuelve falso", async () => {
  assert.equal(await verificarEd25519Cruda("no-es-base64!!", "m", "tampoco"), false);
});

test("formatos: ids y patrones", () => {
  assert.equal(esOfertaIdValido("OF-202611-01"), true);
  assert.equal(esOfertaIdValido("OF-20261-01"), false);
  assert.equal(esVisitorIdValido("a".repeat(16)), true);
  assert.equal(esVisitorIdValido("corto"), false);
  assert.equal(esIdAtribucionValido("123456"), true);
  assert.equal(esIdAtribucionValido("12345"), false);
  assert.equal(esFbpValido("fb.1.1234567890.1234567890"), true);
  assert.equal(esFbpValido("no-fbp"), false);
  assert.equal(esFbcValido("fb.1.1234567890.algo"), true);
  assert.equal(esTimestampZValido("2026-11-06T14:30:00Z"), true);
  assert.equal(esTimestampZValido("2026-11-06T14:30:00"), false);
  assert.equal(esConsentMarketingValido("1"), true);
  assert.equal(esConsentMarketingValido("0"), true);
  assert.equal(esConsentMarketingValido("si"), false);
});

test("almacenEnMemoria: get/put con interfaz async", async () => {
  const almacen = crearAlmacenEnMemoria();
  assert.equal(await almacen.get("x"), undefined);
  await almacen.put("x", 1);
  assert.equal(await almacen.get("x"), 1);
  assert.equal(await almacen.tamano(), 1);
});

test("cerrojo: serializa tareas disparadas al mismo tiempo (sin entrelazado)", async () => {
  const cerrojo = crearCerrojo();
  const orden = [];
  function tarea(id, esperaMs) {
    return cerrojo.ejecutar(async () => {
      orden.push(`inicio:${id}`);
      await new Promise((resolve) => setTimeout(resolve, esperaMs));
      orden.push(`fin:${id}`);
    });
  }
  await Promise.all([tarea("a", 5), tarea("b", 0), tarea("c", 0)]);
  assert.deepEqual(orden, ["inicio:a", "fin:a", "inicio:b", "fin:b", "inicio:c", "fin:c"]);
});

test("cerrojo: una tarea que falla no bloquea las siguientes", async () => {
  const cerrojo = crearCerrojo();
  const resultados = [];
  await assert.rejects(
    cerrojo.ejecutar(async () => {
      throw new Error("falla simulada");
    }),
  );
  await cerrojo.ejecutar(async () => {
    resultados.push("ok");
  });
  assert.deepEqual(resultados, ["ok"]);
});
