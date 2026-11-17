import { test } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { aCentavos, cuerpoSesionStripe, firmaStripeValida, interpretarEvento, renderCheckout, renderLanding } from "../src/logica.mjs";

const T = { slug: "mi-guia", nombre: "Mi guía", html: "<html><body><p>{{price}} <s>{{original_price}}</s></p><a href='{{checkout_url}}'>x</a></body></html>",
  precio: 19, precio_original: 55, moneda: "USD", idioma: "en", pixel: "123456789", bump: JSON.stringify({ nombre: "Extra", precio: 7 }) };

test("landing reemplaza precio y suma la medición antes de </body>", () => {
  const h = renderLanding(T);
  assert.match(h, /\$19/);
  assert.match(h, /\$55/);
  assert.match(h, /href='\/mi-guia\/checkout'/);
  assert.match(h, /sendBeacon\("\/_m\/mi-guia\/landing"\)/);
  assert.match(h, /fbq\('init','123456789'\)/);
  assert.ok(h.indexOf("_m/mi-guia") < h.indexOf("</body>"));
});

test("checkout muestra el bump y mide el inicio de pago", () => {
  const h = renderCheckout(T);
  assert.match(h, /name="bump"/);
  assert.match(h, /\/_m\/mi-guia\/checkout/);
  assert.match(h, /InitiateCheckout/);
});

test("sesión de Stripe con y sin bump", () => {
  const con = cuerpoSesionStripe(T, { conBump: true, origen: "https://t.x" });
  assert.equal(con.get("line_items[0][price_data][unit_amount]"), "1900");
  assert.equal(con.get("line_items[1][price_data][unit_amount]"), "700");
  assert.equal(con.get("metadata[bump]"), "1");
  const sin = cuerpoSesionStripe(T, { conBump: false, origen: "https://t.x" });
  assert.equal(sin.get("line_items[1][quantity]"), null);
  assert.equal(aCentavos(1500, "JPY"), 1500);
});

test("firma de Stripe: válida, vencida y falsa", async () => {
  const cuerpo = '{"a":1}';
  const ts = 1_700_000_000;
  const v1 = createHmac("sha256", "whsec_x").update(`${ts}.${cuerpo}`).digest("hex");
  assert.equal(await firmaStripeValida(cuerpo, `t=${ts},v1=${v1}`, "whsec_x", ts + 10), true);
  assert.equal(await firmaStripeValida(cuerpo, `t=${ts},v1=${v1}`, "whsec_x", ts + 1000), false);
  assert.equal(await firmaStripeValida(cuerpo, `t=${ts},v1=00`, "whsec_x", ts), false);
});

test("eventos: venta pagada, carrito vencido y ajeno", () => {
  const v = interpretarEvento({ type: "checkout.session.completed", created: 1_700_000_000, data: { object: {
    id: "cs_1", payment_status: "paid", amount_total: 2600, currency: "usd", metadata: { tienda: "mi-guia", bump: "1" },
    customer_details: { email: "a@b.c" }, created: 1_700_000_000 } } });
  assert.deepEqual([v.tipo, v.total, v.moneda, v.con_bump], ["venta", 26, "USD", 1]);
  const c = interpretarEvento({ type: "checkout.session.expired", created: 1, data: { object: { id: "cs_2", metadata: { tienda: "mi-guia" },
    customer_details: { email: "a@b.c" }, after_expiration: { recovery: { url: "https://pay/r" } } } } });
  assert.deepEqual([c.tipo, c.recuperar_url], ["carrito", "https://pay/r"]);
  assert.equal(interpretarEvento({ type: "checkout.session.completed", data: { object: { metadata: {} } } }).tipo, "ignorar");
});
