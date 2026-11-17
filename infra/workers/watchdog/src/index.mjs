// Worker `watchdog` (docs/07-puesta-en-marcha.md §9.2; docs/06 §4.6). Dead-man switch: si el motor
// deja de latir, o el latido declara ROJO/pausa, o el gasto/el límite de cuenta se acercan al tope,
// pausa TODAS las campañas ACTIVE de `CUENTAS_PERMITIDAS` y alerta por dos canales.
//
// Únicas rutas: `POST /latido` (recibe el latido firmado), `GET /estado` (solo lectura, para
// `infra.preflight` C-09 y el motor), `POST /pausa` (capa 3 de `infra.kill`: espejo en KV).
// SIN RUTA DE ACTIVACIÓN: cualquier otra cosa es 404; cualquier método no soportado en una ruta
// conocida es 405. Nunca llama a `POST status=ACTIVE`: solo `GET campaigns` y `POST status=PAUSED`.
import { verificarFirmaInterna } from "./hmac.mjs";
import { evaluarCiclo, variablesObligatoriasPresentes } from "./logica.mjs";

const TOLERANCIA_TS_SEG = 120; // tolerancia de reloj al verificar la firma (formato/protocolo, no un umbral de decisión)

function jsonRespuesta(cuerpo, estado = 200) {
  return new Response(JSON.stringify(cuerpo), { status: estado, headers: { "content-type": "application/json" } });
}

async function leerUltimoLatido(kv) {
  const crudo = await kv.get("latido:ultimo");
  return crudo ? JSON.parse(crudo) : null;
}

async function manejarLatido(request, env) {
  if (request.method !== "POST") return jsonRespuesta({ error: "metodo_no_permitido" }, 405);
  const cuerpoExacto = await request.text();
  const ts = request.headers.get("X-Fabrica-Ts");
  const firma = request.headers.get("X-Fabrica-Firma");
  if (!ts || !(await verificarFirmaInterna(env.LATIDO_HMAC || "", cuerpoExacto, ts, firma))) {
    return jsonRespuesta({ error: "firma_invalida" }, 401);
  }
  const diffSeg = Math.abs(Date.now() - Date.parse(ts)) / 1000;
  if (!Number.isFinite(diffSeg) || diffSeg > TOLERANCIA_TS_SEG) {
    return jsonRespuesta({ error: "ts_fuera_de_tolerancia" }, 400);
  }
  let payload;
  try {
    payload = JSON.parse(cuerpoExacto);
  } catch {
    return jsonRespuesta({ error: "cuerpo_invalido" }, 400);
  }
  await env.ESTADO.put("latido:ultimo", JSON.stringify(payload));
  return jsonRespuesta({ ok: true });
}

async function manejarEstado(request, env, ahora) {
  if (request.method !== "GET") return jsonRespuesta({ error: "metodo_no_permitido" }, 405);
  if (!variablesObligatoriasPresentes(env)) {
    return jsonRespuesta({ error: "faltan_variables_obligatorias", faltan: ["GASTO_DIARIO_MAX_MINOR", "CUENTA_TZ"] }, 503);
  }
  const visto = await env.ESTADO.get("watchdog:visto");
  const pausa = (await env.ESTADO.get("pausa:global")) === "true";
  const ultimoLatido = await leerUltimoLatido(env.ESTADO);
  const ahoraMs = ahora().getTime();
  const vistoHaceMin = visto ? Math.round((ahoraMs - Date.parse(visto)) / 60000) : null;
  const latidoHaceMin = ultimoLatido ? Math.round((ahoraMs - Date.parse(ultimoLatido.ts)) / 60000) : null;
  return jsonRespuesta({ visto_hace_min: vistoHaceMin, latido_recibido_hace_min: latidoHaceMin, pausa });
}

async function manejarPausa(request, env) {
  if (request.method !== "POST") return jsonRespuesta({ error: "metodo_no_permitido" }, 405);
  const cuerpoExacto = await request.text();
  const ts = request.headers.get("X-Fabrica-Ts");
  const firma = request.headers.get("X-Fabrica-Firma");
  if (!ts || !(await verificarFirmaInterna(env.LATIDO_HMAC || "", cuerpoExacto, ts, firma))) {
    return jsonRespuesta({ error: "firma_invalida" }, 401);
  }
  await env.ESTADO.put("pausa:global", "true");
  return jsonRespuesta({ ok: true });
}

/** Despacha una petición HTTP contra la lógica pura de arriba. Sin red real en pruebas: `env.ESTADO` es un KV falso. */
export async function manejarPeticion(request, env, { ahora = () => new Date() } = {}) {
  const url = new URL(request.url);
  if (url.pathname === "/latido") return manejarLatido(request, env);
  if (url.pathname === "/estado") return manejarEstado(request, env, ahora);
  if (url.pathname === "/pausa") return manejarPausa(request, env);
  // Ninguna otra ruta existe: en particular, NINGUNA activa nada (docs/07 §9.2: "sin ruta de activación").
  return jsonRespuesta({ error: "no_encontrado" }, 404);
}

async function alertarDosCanales(env, motivo) {
  const resultados = await Promise.allSettled([
    env.ALERTA_CORREO_API_KEY
      ? fetch("https://api.correo.ejemplo/enviar", { method: "POST", body: JSON.stringify({ motivo }) })
      : Promise.reject(new Error("sin ALERTA_CORREO_API_KEY")),
    env.ALERTA_PUSH_TOKEN
      ? fetch("https://api.push.ejemplo/enviar", { method: "POST", body: JSON.stringify({ motivo }) })
      : Promise.reject(new Error("sin ALERTA_PUSH_TOKEN")),
  ]);
  return resultados.map((r) => r.status);
}

async function pausarCuentasPermitidas(env) {
  // GET campaigns?effective_status + POST status=PAUSED, SOLO sobre CUENTAS_PERMITIDAS. Nunca POST
  // status=ACTIVE (no existe esa ruta en este Worker). Implementación real fuera de esta entrega
  // nocturna (exige META_TOKEN_PAUSA real); ver README "Pedidos".
  return [];
}

export default {
  fetch(request, env) {
    return manejarPeticion(request, env);
  },
  async scheduled(_event, env, ctx) {
    const ahora = () => new Date();
    const ultimoLatido = await leerUltimoLatido(env.ESTADO);
    const cuentasPermitidas = (env.CUENTAS_PERMITIDAS || "").split(",").filter(Boolean);
    const hayActivas = cuentasPermitidas.length > 0; // lectura real de Meta: fuera de esta entrega (sin credenciales)
    const decision = evaluarCiclo({
      ultimoLatidoIso: ultimoLatido ? ultimoLatido.ts : null,
      ahoraIso: ahora().toISOString(),
      latidoMaxMin: Number(env.WATCHDOG_LATIDO_MAX_MIN || 0),
      semaforo: ultimoLatido ? ultimoLatido.semaforo : null,
      pausa: ultimoLatido ? Boolean(ultimoLatido.pausa) : false,
      estadoGeneradoEnIso: ultimoLatido ? ultimoLatido.estado_generado_en : null,
      gastoHoyMinor: null, // ETL del gasto de hoy: fuera de esta entrega (sin credenciales de Meta)
      gastoDiarioMaxMinor: env.GASTO_DIARIO_MAX_MINOR ? Number(env.GASTO_DIARIO_MAX_MINOR) : null,
      amountSpentMinor: null,
      limiteCuentaMinor: env.LIMITE_CUENTA_MINOR ? Number(env.LIMITE_CUENTA_MINOR) : null,
      hayActivas,
    });
    await env.ESTADO.put("watchdog:visto", ahora().toISOString());
    if (decision.pausar && hayActivas) {
      await env.ESTADO.put("pausa:global", "true");
      ctx.waitUntil(Promise.all([pausarCuentasPermitidas(env), alertarDosCanales(env, decision.motivo)]));
    }
  },
};
