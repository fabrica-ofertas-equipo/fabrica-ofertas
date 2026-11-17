import assert from "node:assert/strict";
import { test } from "node:test";
import { manejarEntregaPagada } from "../src/manejador.mjs";

const SECRETO = "secreto-de-prueba-no-real";
const AHORA = new Date("2026-11-12T09:00:00Z");

function crearDedupeEnMemoria() {
  const vistos = new Set();
  return {
    vistos,
    async yaEntregado(sessionId) {
      return vistos.has(sessionId);
    },
    async marcarEntregado(sessionId) {
      vistos.add(sessionId);
    },
  };
}

function entradaBase(overrides = {}) {
  const dedupe = crearDedupeEnMemoria();
  const llamadasCorreo = [];
  const llamadasApi = [];
  return {
    dedupe,
    llamadasCorreo,
    llamadasApi,
    entrada: {
      sessionId: "cs_test_0001",
      ofertaId: "OF-202611-01",
      productoVersion: "v1",
      productoSha256: "sha256:" + "a".repeat(64),
      email: "cliente@ejemplo.com",
      venceDias: 7,
      maxDescargas: 5,
      secretoEnlace: SECRETO,
      yaEntregado: dedupe.yaEntregado,
      marcarEntregado: dedupe.marcarEntregado,
      async enviarCorreo(datos) {
        llamadasCorreo.push(datos);
        return { codigo: "enviado" };
      },
      async postEntregaApi(cuerpo) {
        llamadasApi.push(cuerpo);
        return { codigo: "ok" };
      },
      ahora: () => AHORA,
      ...overrides,
    },
  };
}

test("una sesión nueva entrega: correo enviado, API llamada, enlace con vencimiento y cuota", async () => {
  const { entrada, llamadasCorreo, llamadasApi } = entradaBase();
  const resultado = await manejarEntregaPagada(entrada);
  assert.equal(resultado.status, 200);
  assert.equal(resultado.cuerpo.codigo, "entregado");
  assert.equal(resultado.cuerpo.enlace.max_descargas, 5);
  assert.equal(llamadasCorreo.length, 1);
  assert.equal(llamadasApi.length, 1);
  assert.equal(llamadasApi[0].checkout_session_id, "cs_test_0001");
  assert.equal(llamadasApi[0].estado, "entregado");
  // El cuerpo que llega a /ingesta/entrega no lleva el email (sin datos personales).
  assert.equal("email" in llamadasApi[0], false);
});

test("una sesión ya entregada no reenvía correo ni vuelve a llamar a la API (duplicado)", async () => {
  const { entrada, dedupe, llamadasCorreo, llamadasApi } = entradaBase();
  await manejarEntregaPagada(entrada);
  const segundo = await manejarEntregaPagada(entrada);
  assert.equal(segundo.cuerpo.codigo, "duplicado");
  assert.equal(llamadasCorreo.length, 1);
  assert.equal(llamadasApi.length, 1);
  assert.equal(dedupe.vistos.size, 1);
});

test("sin session_id responde 400", async () => {
  const { entrada } = entradaBase({ sessionId: undefined });
  const resultado = await manejarEntregaPagada(entrada);
  assert.equal(resultado.status, 400);
  assert.equal(resultado.cuerpo.codigo, "session_id_ausente");
});
