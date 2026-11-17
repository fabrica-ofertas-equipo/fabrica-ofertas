// Arnés de B0-10 (I1): ejercita el Worker REAL de infra/workers/fulfill (B7) sin red (dedupe en
// memoria, transporte/correo inyectados) y el enlace firmado REAL de enlace.mjs (verifica
// vencimiento y cuota de verdad, no solo que existan los campos). Imprime una línea JSON.
import { manejarEntregaPagada } from "../../../infra/workers/fulfill/src/manejador.mjs";
import { verificarEnlace } from "../../../infra/workers/fulfill/src/enlace.mjs";

const SECRETO = "secreto-de-prueba-b0-10";
const AHORA = new Date("2026-11-12T09:00:00Z");

function crearDedupeEnMemoria() {
  const vistos = new Set();
  return { vistos, async yaEntregado(id) { return vistos.has(id); }, async marcarEntregado(id) { vistos.add(id); } };
}

function entrada(overrides = {}) {
  const dedupe = crearDedupeEnMemoria();
  const llamadasCorreo = [];
  const llamadasApi = [];
  return {
    dedupe, llamadasCorreo, llamadasApi,
    entrada: {
      sessionId: "cs_test_b0_0001", ofertaId: "OF-202611-01", productoVersion: "v1",
      productoSha256: "sha256:" + "a".repeat(64), email: "cliente@ejemplo.com",  // lint-estatico: permitir=c (dominio .ejemplo, sin dato real)
      venceDias: 7, maxDescargas: 3, secretoEnlace: SECRETO,
      yaEntregado: dedupe.yaEntregado, marcarEntregado: dedupe.marcarEntregado,
      async enviarCorreo(datos) { llamadasCorreo.push(datos); return { codigo: "enviado" }; },
      async postEntregaApi(cuerpo) { llamadasApi.push(cuerpo); return { codigo: "ok" }; },
      ahora: () => AHORA,
      ...overrides,
    },
  };
}

const uno = entrada();
const primero = await manejarEntregaPagada(uno.entrada);
const segundo = await manejarEntregaPagada(uno.entrada); // misma sesión: debe ser "duplicado", sin reenvío

// El token del enlace es REAL (HMAC firmado de verdad); se extrae del propio flujo reconstruyendo
// la firma con los mismos datos que usó manejarEntregaPagada (no hay getter: se repite la llamada a
// firmarEnlace con los mismos insumos para poder verificar vencimiento/cuota de verdad).
import { firmarEnlace } from "../../../infra/workers/fulfill/src/enlace.mjs";
const venceEn = primero.cuerpo.enlace.vence_en;
const token = await firmarEnlace(
  { sessionId: uno.entrada.sessionId, productoSha256: uno.entrada.productoSha256, productoVersion: uno.entrada.productoVersion,
    venceEn, maxDescargas: uno.entrada.maxDescargas },
  SECRETO,
);

const dentroDeCuotaYVigente = await verificarEnlace(token, SECRETO, { ahora: AHORA, descargasHechas: 0 });
const cuotaAgotada = await verificarEnlace(token, SECRETO, { ahora: AHORA, descargasHechas: uno.entrada.maxDescargas });
const vencido = await verificarEnlace(token, SECRETO, { ahora: new Date(new Date(venceEn).getTime() + 1000), descargasHechas: 0 });

console.log(JSON.stringify({
  primero_codigo: primero.cuerpo.codigo,
  primero_enlace: primero.cuerpo.enlace,
  segundo_codigo: segundo.cuerpo.codigo,
  llamadas_correo: uno.llamadasCorreo.length,
  llamadas_api: uno.llamadasApi.length,
  enlace_valido_dentro_de_cuota: dentroDeCuotaYVigente !== null,
  enlace_null_con_cuota_agotada: cuotaAgotada === null,
  enlace_null_si_vencido: vencido === null,
}));
