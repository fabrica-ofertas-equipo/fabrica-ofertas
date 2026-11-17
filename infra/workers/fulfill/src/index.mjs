// Worker `fulfill` (docs/06 4.6/4.7). Entrada HTTP real: delega toda la decision a `manejador.mjs`
// (logica pura, probada con `node --test` sin red). Lo encola `webhook-stripe` (pendiente de
// conectar: ver README "Pedidos" a B2) con un cuerpo interno firmado HMAC (`X-Fabrica-Firma`, igual
// autenticacion que docs/06 4.7). El dedupe real es KV (`ENTREGA_KV`, una clave por `session_id`).

import { manejarEntregaPagada } from "./manejador.mjs";
import { construirCabecerasInternas, verificarHmacSha256 } from "./hmac.mjs";

const SEGUNDOS_POR_MINUTO = 60;
const TOLERANCIA_FIRMA_SEG = 5 * SEGUNDOS_POR_MINUTO;
const PREFIJO_DEDUPE = "entregado:";

function crearDedupeKv(kv) {
  return {
    async yaEntregado(sessionId) {
      return (await kv.get(PREFIJO_DEDUPE + sessionId)) !== null;
    },
    async marcarEntregado(sessionId) {
      await kv.put(PREFIJO_DEDUPE + sessionId, "1");
    },
  };
}

function crearTransporteFetch() {
  return {
    async solicitar(metodo, url, opciones) {
      const respuesta = await fetch(url, { method: metodo, headers: opciones?.cabeceras, body: opciones?.cuerpo });
      return { estado: respuesta.status, cuerpo: await respuesta.text() };
    },
  };
}

async function firmaValida(cuerpoCrudo, cabeceraFirma, cabeceraTs, secreto, ahoraDate) {
  if (!cabeceraFirma || !cabeceraTs || !secreto) {
    return false;
  }
  const tsSeg = Math.floor(new Date(cabeceraTs).getTime() / 1000);
  if (!Number.isFinite(tsSeg) || Math.abs(Math.floor(ahoraDate.getTime() / 1000) - tsSeg) > TOLERANCIA_FIRMA_SEG) {
    return false;
  }
  const firmaHex = cabeceraFirma.replace(/^hmac-sha256=/, "");
  return verificarHmacSha256(secreto, `${cabeceraTs}.${cuerpoCrudo}`, firmaHex);
}

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("method not allowed", { status: 405 });
    }
    const cuerpoCrudo = await request.text();
    const ahoraDate = new Date();
    const valida = await firmaValida(
      cuerpoCrudo,
      request.headers.get("X-Fabrica-Firma"),
      request.headers.get("X-Fabrica-Ts"),
      env.INGEST_HMAC_SECRET,
      ahoraDate,
    );
    if (!valida) {
      return new Response(JSON.stringify({ ok: false, codigo: "firma_invalida" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      });
    }

    let cuerpo;
    try {
      cuerpo = JSON.parse(cuerpoCrudo);
    } catch {
      return new Response(JSON.stringify({ ok: false, codigo: "cuerpo_invalido" }), {
        status: 400,
        headers: { "content-type": "application/json" },
      });
    }

    const transporte = crearTransporteFetch();
    const resultado = await manejarEntregaPagada({
      sessionId: cuerpo.session_id,
      ofertaId: cuerpo.oferta_id,
      productoVersion: cuerpo.producto_version,
      productoSha256: cuerpo.producto_sha256,
      email: cuerpo.email,
      venceDias: Number.parseInt(env.ENTREGA_ENLACE_VENCE_DIAS ?? "", 10),
      maxDescargas: Number.parseInt(env.ENTREGA_ENLACE_MAX_DESCARGAS ?? "", 10),
      secretoEnlace: env.DESCARGA_HMAC,
      ...crearDedupeKv(env.ENTREGA_KV),
      async enviarCorreo({ email, sessionId, token, venceEn }) {
        if (!env.CORREO_API_KEY || !email) {
          return { codigo: "sin_configuracion_correo" };
        }
        const resp = await transporte.solicitar("POST", "https://api.resend.com/emails", {
          cabeceras: { Authorization: `Bearer ${env.CORREO_API_KEY}`, "content-type": "application/json" },
          cuerpo: JSON.stringify({
            from: env.CORREO_REMITENTE,
            to: [email],
            subject: "Tu descarga está lista",
            text: `Descarga tu producto: ${env.DESCARGA_BASE_URL}/${sessionId}?token=${token} (vence ${venceEn})`,
          }),
        });
        return { codigo: resp.estado < 300 ? "enviado" : "error_proveedor" };
      },
      async postEntregaApi(cuerpoEntrega) {
        // El servicio `api` rechaza con 401 todo POST sin firma (docs/06 §4.7): jamas se envia sin firmar.
        if (!env.INGEST_HMAC_SECRET || !env.API_BASE_URL) {
          return { codigo: "error_api" };
        }
        const cuerpoExacto = JSON.stringify(cuerpoEntrega);
        const ts = ahoraDate.toISOString().replace(/\.\d{3}Z$/, "Z");
        const firmadas = await construirCabecerasInternas(env.INGEST_HMAC_SECRET, cuerpoExacto, ts);
        const resp = await transporte.solicitar("POST", `${env.API_BASE_URL}/ingesta/entrega`, {
          cabeceras: { "content-type": "application/json", ...firmadas },
          cuerpo: cuerpoExacto,
        });
        return { codigo: resp.estado < 300 ? "ok" : "error_api" };
      },
      ahora: () => ahoraDate,
    });

    return new Response(JSON.stringify(resultado.cuerpo), {
      status: resultado.status,
      headers: { "content-type": "application/json" },
    });
  },
};
