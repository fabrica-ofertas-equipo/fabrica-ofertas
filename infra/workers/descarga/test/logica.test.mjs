import assert from "node:assert/strict";
import { test } from "node:test";
import { crearBucketR2, crearContadorKv, manejarDescarga, sessionIdDeRuta } from "../src/logica.mjs";
import { firmarEnlace } from "../../fulfill/src/enlace.mjs";

const SECRETO = "secreto-de-prueba-no-real";
const AHORA = () => new Date("2026-11-10T00:00:00Z");

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

class BucketFalso {
  constructor(objetos = {}) {
    this.objetos = objetos;
  }

  async get(clave) {
    return this.objetos[clave] ?? null;
  }
}

async function tokenValido({ sessionId = "cs_test_0001", maxDescargas = 3, venceEn = "2026-11-20T00:00:00Z" } = {}) {
  return firmarEnlace(
    { sessionId, productoSha256: "sha256:" + "a".repeat(64), productoVersion: "v1", venceEn, maxDescargas },
    SECRETO,
  );
}

test("sessionIdDeRuta toma el ultimo segmento de /d/<sessionId>", () => {
  assert.equal(sessionIdDeRuta("/d/cs_test_0001"), "cs_test_0001");
  assert.equal(sessionIdDeRuta("/d/cs_test_0001/"), "cs_test_0001");
  assert.equal(sessionIdDeRuta("/"), "");
});

test("sin sessionId o sin token: 400", async () => {
  const resultado = await manejarDescarga({
    sessionIdRuta: "", token: "", secreto: SECRETO, ahora: AHORA,
    contador: crearContadorKv(new KVFalso()), bucket: crearBucketR2(new BucketFalso()),
  });
  assert.equal(resultado.status, 400);
});

test("sin DESCARGA_HMAC configurado: 500, nunca se trata como invalido silencioso", async () => {
  const resultado = await manejarDescarga({
    sessionIdRuta: "cs_test_0001", token: "x.y", secreto: "", ahora: AHORA,
    contador: crearContadorKv(new KVFalso()), bucket: crearBucketR2(new BucketFalso()),
  });
  assert.equal(resultado.status, 500);
});

test("token invalido o vencido: 403", async () => {
  const resultado = await manejarDescarga({
    sessionIdRuta: "cs_test_0001", token: "invalido.invalido", secreto: SECRETO, ahora: AHORA,
    contador: crearContadorKv(new KVFalso()), bucket: crearBucketR2(new BucketFalso()),
  });
  assert.equal(resultado.status, 403);
  assert.equal(resultado.cuerpo.codigo, "enlace_invalido_o_vencido");
});

test("token valido pero de OTRA sesion: 403, no deja usar el token de otro", async () => {
  const token = await tokenValido({ sessionId: "cs_test_0001" });
  const resultado = await manejarDescarga({
    sessionIdRuta: "cs_test_OTRA", token, secreto: SECRETO, ahora: AHORA,
    contador: crearContadorKv(new KVFalso()), bucket: crearBucketR2(new BucketFalso()),
  });
  assert.equal(resultado.status, 403);
  assert.equal(resultado.cuerpo.codigo, "enlace_no_corresponde_a_la_sesion");
});

test("producto ausente en el bucket: 404 y NO se incrementa el contador", async () => {
  const token = await tokenValido();
  const kv = new KVFalso();
  const resultado = await manejarDescarga({
    sessionIdRuta: "cs_test_0001", token, secreto: SECRETO, ahora: AHORA,
    contador: crearContadorKv(kv), bucket: crearBucketR2(new BucketFalso({})),
  });
  assert.equal(resultado.status, 404);
  assert.equal(await kv.get("descargas:cs_test_0001"), null);
});

test("descarga exitosa: 200, entrega el objeto e incrementa el contador", async () => {
  const token = await tokenValido({ maxDescargas: 3 });
  const kv = new KVFalso();
  const bucket = new BucketFalso({ ["sha256:" + "a".repeat(64)]: { body: "contenido-fake", httpMetadata: { contentType: "application/pdf" } } });
  const resultado = await manejarDescarga({
    sessionIdRuta: "cs_test_0001", token, secreto: SECRETO, ahora: AHORA,
    contador: crearContadorKv(kv), bucket: crearBucketR2(bucket),
  });
  assert.equal(resultado.status, 200);
  assert.equal(resultado.binario.body, "contenido-fake");
  assert.equal(await kv.get("descargas:cs_test_0001"), "1");
});

test("cuota agotada tras maxDescargas usos: la siguiente es 403, no 200", async () => {
  const token = await tokenValido({ maxDescargas: 1 });
  const kv = new KVFalso();
  const bucket = new BucketFalso({ ["sha256:" + "a".repeat(64)]: { body: "contenido-fake" } });
  const args = {
    sessionIdRuta: "cs_test_0001", token, secreto: SECRETO, ahora: AHORA,
    contador: crearContadorKv(kv), bucket: crearBucketR2(bucket),
  };
  const primera = await manejarDescarga(args);
  assert.equal(primera.status, 200);
  const segunda = await manejarDescarga(args);
  assert.equal(segunda.status, 403);
  assert.equal(segunda.cuerpo.codigo, "enlace_invalido_o_vencido");
});

test("crearContadorKv: obtener sin datos previos es 0", async () => {
  const contador = crearContadorKv(new KVFalso());
  assert.equal(await contador.obtener("cs_x"), 0);
});
