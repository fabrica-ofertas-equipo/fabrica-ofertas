// Arnés de SOLO LECTURA para tests/datos/test_contrato_workers.py (B3). Ejecuta el Worker REAL
// `infra/workers/fulfill` (de B7; este archivo NO lo modifica) de punta a punta: construye una petición
// HTTP firmada (igual que `webhook-stripe`), intercepta el `fetch` global (sin red, sin tocar
// `infra/workers/fulfill`) y captura lo que el Worker manda de verdad a `POST /ingesta/entrega`.
// Entrada por stdin: {"secreto","ahora","cuerpoWebhook"} (JSON).
import { firmarHmacSha256Hex } from "../../../tracking/workers/_lib/src/hmac.mjs";

const capturas = [];
globalThis.fetch = async (url, opciones) => {
  capturas.push({
    url: String(url),
    metodo: opciones?.method ?? null,
    cabeceras: opciones?.headers ?? null,
    cuerpo: opciones?.body ?? null,
  });
  return new Response("{}", { status: 200, headers: { "content-type": "application/json" } });
};

const fulfillDefault = (await import("../../../infra/workers/fulfill/src/index.mjs")).default;

function leerStdin() {
  return new Promise((resolve, reject) => {
    let datos = "";
    process.stdin.setEncoding("utf8");
    process.stdin.on("data", (c) => { datos += c; });
    process.stdin.on("end", () => resolve(datos));
    process.stdin.on("error", reject);
  });
}

async function main() {
  const entrada = JSON.parse(await leerStdin());
  const cuerpoCrudo = JSON.stringify(entrada.cuerpoWebhook);
  const ts = entrada.ahora;
  const firmaHex = await firmarHmacSha256Hex(entrada.secreto, `${ts}.${cuerpoCrudo}`);
  const request = new Request("http://local/fulfill", {
    method: "POST",
    headers: { "X-Fabrica-Ts": ts, "X-Fabrica-Firma": `hmac-sha256=${firmaHex}` },
    body: cuerpoCrudo,
  });
  const kvAlmacen = new Map();
  const kv = {
    async get(k) { return kvAlmacen.has(k) ? kvAlmacen.get(k) : null; },
    async put(k, v) { kvAlmacen.set(k, v); },
  };
  const env = {
    INGEST_HMAC_SECRET: entrada.secreto,
    ENTREGA_KV: kv,
    ENTREGA_ENLACE_VENCE_DIAS: "14",
    ENTREGA_ENLACE_MAX_DESCARGAS: "5",
    DESCARGA_HMAC: "clave-enlace-de-prueba-arnes",
    API_BASE_URL: "http://local/api",
  };
  const respuesta = await fulfillDefault.fetch(request, env);
  const cuerpoRespuesta = await respuesta.text();
  process.stdout.write(JSON.stringify({ status: respuesta.status, cuerpo: cuerpoRespuesta, capturas }));
}

main().catch((e) => {
  process.stderr.write(String((e && e.stack) || e));
  process.exit(1);
});
