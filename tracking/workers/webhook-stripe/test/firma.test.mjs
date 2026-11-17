import test from "node:test";
import assert from "node:assert/strict";

import { firmarHmacSha256Hex } from "../../_lib/src/hmac.mjs";
import { verificarFirmaStripe, parsearCabeceraFirma } from "../src/firma.mjs";

const SECRETO = "whsec_prueba";
const CUERPO = '{"id":"evt_1","type":"checkout.session.completed"}';

async function construirCabecera(t, cuerpo = CUERPO, secreto = SECRETO) {
  const firma = await firmarHmacSha256Hex(secreto, `${t}.${cuerpo}`);
  return `t=${t},v1=${firma}`;
}

test("parsearCabeceraFirma: formato valido", () => {
  const parsed = parsearCabeceraFirma("t=12345,v1=abcd");
  assert.deepEqual(parsed, { t: "12345", firmas: ["abcd"] });
});

test("parsearCabeceraFirma: formato invalido devuelve null", () => {
  assert.equal(parsearCabeceraFirma("sin-formato"), null);
  assert.equal(parsearCabeceraFirma(""), null);
  assert.equal(parsearCabeceraFirma(null), null);
});

test("firma valida: verifica true", async () => {
  const t = "1000";
  const cabecera = await construirCabecera(t);
  const resultado = await verificarFirmaStripe({
    cabeceraFirma: cabecera,
    cuerpoCrudo: CUERPO,
    secretoWhsec: SECRETO,
    ahoraEpochSeg: 1000,
    toleranciaSeg: 300,
  });
  assert.equal(resultado.valida, true);
});

test("firma falsa (secreto distinto): rechaza con firma_no_coincide", async () => {
  const t = "1000";
  const cabecera = await construirCabecera(t, CUERPO, "whsec_otro");
  const resultado = await verificarFirmaStripe({
    cabeceraFirma: cabecera,
    cuerpoCrudo: CUERPO,
    secretoWhsec: SECRETO,
    ahoraEpochSeg: 1000,
    toleranciaSeg: 300,
  });
  assert.equal(resultado.valida, false);
  assert.equal(resultado.motivo, "firma_no_coincide");
});

test("firma vencida (fuera de tolerancia): rechaza con fuera_de_tolerancia", async () => {
  const t = "1000";
  const cabecera = await construirCabecera(t);
  const resultado = await verificarFirmaStripe({
    cabeceraFirma: cabecera,
    cuerpoCrudo: CUERPO,
    secretoWhsec: SECRETO,
    ahoraEpochSeg: 1000 + 301,
    toleranciaSeg: 300,
  });
  assert.equal(resultado.valida, false);
  assert.equal(resultado.motivo, "fuera_de_tolerancia");
});

test("cuerpo alterado tras firmar: rechaza con firma_no_coincide", async () => {
  const t = "1000";
  const cabecera = await construirCabecera(t);
  const resultado = await verificarFirmaStripe({
    cabeceraFirma: cabecera,
    cuerpoCrudo: CUERPO.replace("evt_1", "evt_2"),
    secretoWhsec: SECRETO,
    ahoraEpochSeg: 1000,
    toleranciaSeg: 300,
  });
  assert.equal(resultado.valida, false);
  assert.equal(resultado.motivo, "firma_no_coincide");
});

test("tolerancia 0 o ausente: rechaza TODO (fail-closed), nunca asume un valor", async () => {
  const t = "1000";
  const cabecera = await construirCabecera(t);
  const conCero = await verificarFirmaStripe({
    cabeceraFirma: cabecera,
    cuerpoCrudo: CUERPO,
    secretoWhsec: SECRETO,
    ahoraEpochSeg: 1000,
    toleranciaSeg: 0,
  });
  assert.equal(conCero.valida, false);
  assert.equal(conCero.motivo, "tolerancia_invalida");

  const sinTolerancia = await verificarFirmaStripe({
    cabeceraFirma: cabecera,
    cuerpoCrudo: CUERPO,
    secretoWhsec: SECRETO,
    ahoraEpochSeg: 1000,
    toleranciaSeg: NaN,
  });
  assert.equal(sinTolerancia.valida, false);
  assert.equal(sinTolerancia.motivo, "tolerancia_invalida");
});

test("cabecera ausente: rechaza con cabecera_invalida", async () => {
  const resultado = await verificarFirmaStripe({
    cabeceraFirma: null,
    cuerpoCrudo: CUERPO,
    secretoWhsec: SECRETO,
    ahoraEpochSeg: 1000,
    toleranciaSeg: 300,
  });
  assert.equal(resultado.valida, false);
  assert.equal(resultado.motivo, "cabecera_invalida");
});
