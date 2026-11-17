import test from "node:test";
import assert from "node:assert/strict";

import {
  debePausarPorGastoDiario,
  debePausarPorLatido,
  debePausarPorLimiteCuenta,
  evaluarCiclo,
  variablesObligatoriasPresentes,
} from "../src/logica.mjs";

const AHORA = "2026-11-09T08:00:00Z";

test("sin latido previo: pausar (fail-closed)", () => {
  const r = debePausarPorLatido({ ultimoLatidoIso: null, ahoraIso: AHORA, latidoMaxMin: 30 });
  assert.equal(r.pausar, true);
});

test("latido vigente: no pausar", () => {
  const r = debePausarPorLatido({ ultimoLatidoIso: "2026-11-09T07:50:00Z", ahoraIso: AHORA, latidoMaxMin: 30 });
  assert.equal(r.pausar, false);
});

test("latido vencido: pausar", () => {
  const r = debePausarPorLatido({ ultimoLatidoIso: "2026-11-09T07:00:00Z", ahoraIso: AHORA, latidoMaxMin: 30 });
  assert.equal(r.pausar, true);
});

test("latido declara pausa=true: pausar aunque esté vigente", () => {
  const r = debePausarPorLatido({ ultimoLatidoIso: "2026-11-09T07:59:00Z", ahoraIso: AHORA, latidoMaxMin: 30, pausa: true });
  assert.equal(r.pausar, true);
});

test("semaforo ROJO en el latido: pausar", () => {
  const r = debePausarPorLatido({ ultimoLatidoIso: "2026-11-09T07:59:00Z", ahoraIso: AHORA, latidoMaxMin: 30, semaforo: "ROJO" });
  assert.equal(r.pausar, true);
});

test("estado_generado_en de mas de 6h: pausar", () => {
  const r = debePausarPorLatido({
    ultimoLatidoIso: "2026-11-09T07:59:00Z", ahoraIso: AHORA, latidoMaxMin: 30,
    estadoGeneradoEnIso: "2026-11-09T01:00:00Z",
  });
  assert.equal(r.pausar, true);
});

test("fecha ilegible: pausar (fail-closed, no lanza)", () => {
  const r = debePausarPorLatido({ ultimoLatidoIso: "no-es-una-fecha", ahoraIso: AHORA, latidoMaxMin: 30 });
  assert.equal(r.pausar, true);
});

test("ciclo D8 vencido con latido vivo: pausar", () => {
  const r = debePausarPorLatido({
    ultimoLatidoIso: "2026-11-09T07:59:00Z", ahoraIso: AHORA, latidoMaxMin: 30,
    cicloMaxMin: 60, ultimoCicloD8Iso: "2026-11-09T06:00:00Z",
  });
  assert.equal(r.pausar, true);
});

test("variables obligatorias: ambas presentes", () => {
  assert.equal(variablesObligatoriasPresentes({ GASTO_DIARIO_MAX_MINOR: "1000", CUENTA_TZ: "Europe/Madrid" }), true);
});

test("variables obligatorias: falta una -> false", () => {
  assert.equal(variablesObligatoriasPresentes({ GASTO_DIARIO_MAX_MINOR: "1000" }), false);
  assert.equal(variablesObligatoriasPresentes({}), false);
});

test("gasto diario: por debajo del tope x factor no pausa", () => {
  assert.equal(debePausarPorGastoDiario({ gastoHoyMinor: 1000, gastoDiarioMaxMinor: 1000 }), false);
});

test("gasto diario: por encima del tope x 1.75 pausa", () => {
  assert.equal(debePausarPorGastoDiario({ gastoHoyMinor: 1800, gastoDiarioMaxMinor: 1000 }), true);
});

test("limite de cuenta: al 90% pausa", () => {
  assert.equal(debePausarPorLimiteCuenta({ amountSpentMinor: 900, limiteCuentaMinor: 1000 }), true);
});

test("limite de cuenta: por debajo de 90% no pausa", () => {
  assert.equal(debePausarPorLimiteCuenta({ amountSpentMinor: 899, limiteCuentaMinor: 1000 }), false);
});

test("evaluarCiclo: sin campañas activas nunca pausa aunque falte el latido", () => {
  const r = evaluarCiclo({ ultimoLatidoIso: null, ahoraIso: AHORA, latidoMaxMin: 30, hayActivas: false });
  assert.equal(r.pausar, false);
});

test("evaluarCiclo: con activas y latido vencido, pausa", () => {
  const r = evaluarCiclo({ ultimoLatidoIso: null, ahoraIso: AHORA, latidoMaxMin: 30, hayActivas: true });
  assert.equal(r.pausar, true);
});
