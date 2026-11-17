// Arnés de B0-14 (I1): ejercita el Worker REAL de infra/workers/watchdog (B8) con un KV falso y un
// `fetch` global reemplazado (nunca sale a la red de verdad: ninguna URL se resuelve, solo se
// registra que se llamó). Imprime UNA línea JSON en stdout para que scripts/b0/infra.py la lea.
//
// Escenario: sin latido registrado ("sin latido registrado todavía") y con campañas activas
// (CUENTAS_PERMITIDAS no vacío) -> el ciclo programado (`scheduled`) debe marcar pausa:global y
// llamar a los DOS canales de alerta (correo y push).
import watchdog from "../../../infra/workers/watchdog/src/index.mjs";

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

const llamadasFetch = [];
globalThis.fetch = async (url, opciones) => {
  llamadasFetch.push(String(url));
  return new Response(JSON.stringify({ ok: true }), { status: 200 });
};

const kv = new KVFalso(); // sin "latido:ultimo": "sin latido registrado todavía"
const env = {
  ESTADO: kv,
  CUENTAS_PERMITIDAS: "act_100000000000001",
  WATCHDOG_LATIDO_MAX_MIN: "30",
  GASTO_DIARIO_MAX_MINOR: "100000",
  ALERTA_CORREO_API_KEY: "clave-de-prueba-correo",
  ALERTA_PUSH_TOKEN: "clave-de-prueba-push",
};

const ctx = { waitUntil: (p) => p }; // sin background real en el arnés: se espera inline

await watchdog.scheduled({}, env, ctx);
await Promise.resolve(); // deja correr el microtask de ctx.waitUntil antes de leer resultados

// Pequeña espera para que las promesas internas de alertarDosCanales() (Promise.allSettled) terminen.
await new Promise((r) => setTimeout(r, 50));

const pausaGlobal = await kv.get("pausa:global");

// Ruta de activación: NINGUNA ruta de fetch() del Worker la ofrece (comprobado también por
// infra/workers/watchdog/test/index.test.mjs, de B8); aquí solo confirmamos que `manejarPeticion`
// sigue rechazando /activar con 404 en este mismo módulo cargado.
const respActivar = await watchdog.fetch(new Request("https://watchdog.ejemplo/activar", { method: "POST" }), env);

console.log(JSON.stringify({
  pausa_global: pausaGlobal,
  llamadas_fetch: llamadasFetch,
  activar_status: respActivar.status,
}));
