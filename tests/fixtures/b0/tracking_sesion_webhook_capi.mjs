// Arnés de B0-09 (I1): sesión -> webhook -> CAPI de punta a punta sobre los Workers REALES de
// tracking/ (B2), sin red (transporte y almacenes en memoria). Imprime una línea JSON.
import { manejarSolicitudSesion } from "../../../tracking/workers/crear-sesion/src/manejador.mjs";
import { contarSesionYRegistrar } from "../../../tracking/workers/crear-sesion/src/limitador.mjs";
import { manejarWebhookStripe } from "../../../tracking/workers/webhook-stripe/src/manejador.mjs";
import { registrarSiEsNuevo } from "../../../tracking/workers/webhook-stripe/src/dedupe.mjs";
import { crearAlmacenEnMemoria } from "../../../tracking/workers/_lib/src/almacen_memoria.mjs";
import { crearCerrojo } from "../../../tracking/workers/_lib/src/cerrojo.mjs";
import { firmarHmacSha256Hex } from "../../../tracking/workers/_lib/src/hmac.mjs";
import { idPurchase } from "../../../tracking/workers/capi/src/capi.mjs";

const CATALOGO_HMAC_SECRETO = "b0-catalogo-secreto";
const WHSEC = "whsec_b0_prueba"; // lint-estatico: permitir=d (valor ficticio, nunca un secreto real)
const OFERTA_ID = "OF-202611-01";
const AD_ID = "120210000000103";
const ADSET_ID = "120210000000011";
const CAMPAIGN_ID = "120210000000001";
const VISITOR_ID = "v".repeat(20);

const CATALOGO_OBJETO = {
  ofertas: {
    [OFERTA_ID]: {
      price_id: "price_front_v1", price_id_bump: "price_bump_v1", moneda: "EUR",
      success_url: "https://oferta.example/gracias", return_url: "https://oferta.example/landing",
      ids_meta: { campaign_id: CAMPAIGN_ID, adset_ids: [ADSET_ID], ad_ids: [AD_ID] },
    },
  },
};

function crearTransporteFalso() {
  const llamadas = [];
  return {
    llamadas,
    async solicitar(metodo, url, opciones) {
      llamadas.push({ metodo, url, opciones });
      if (url.includes("checkout/sessions")) {
        return { estado: 200, cuerpo: JSON.stringify({ id: "cs_test_b0_e2e", url: "https://checkout.stripe.com/c/pay/cs_test_b0_e2e" }) };
      }
      return { estado: 200, cuerpo: JSON.stringify({ events_received: 1 }) };
    },
  };
}

async function crearSesion() {
  const catalogoJson = JSON.stringify(CATALOGO_OBJETO);
  const catalogoFirma = await firmarHmacSha256Hex(CATALOGO_HMAC_SECRETO, catalogoJson);
  const env = {
    catalogoJson, catalogoFirma, catalogoHmacSecreto: CATALOGO_HMAC_SECRETO, turnstileSecreto: null,
    maxSesionesPorVisitante: 5, stripeRkCheckout: "rk_test_b0", stripeApiVersion: "2026-10-28.endive",
  };
  const almacenCuota = crearAlmacenEnMemoria();
  const transporte = crearTransporteFalso();
  const cuerpo = {
    oferta_id: OFERTA_ID, visitor_id: VISITOR_ID, bump: false, locale: "es-ES",
    consent_marketing: "1", landing_version: "v1",
    params: {
      utm_source: "meta", utm_medium: "paid", utm_campaign: "camp", utm_content: "ad", utm_term: "adset",
      cid: CAMPAIGN_ID, asid: ADSET_ID, adid: AD_ID,
      fbp: "fb.1.1699999999999.1234567890", fbc: "fb.1.1699999999999.abcXYZ",
    },
  };
  const resultado = await manejarSolicitudSesion({
    cuerpo, cabeceraReferer: "https://oferta.example/landing", ipRemota: "203.0.113.5", env,  // lint-estatico: permitir=c (bloque TEST-NET-3, RFC 5737, de documentación)
    verificarCuota: ({ visitorId, diaUtc, limite }) => contarSesionYRegistrar(almacenCuota, { visitorId, diaUtc, limite }),
    ahora: () => new Date("2026-11-12T09:00:00Z"), transporte,
  });
  const llamadaStripe = transporte.llamadas.find((l) => l.url.includes("checkout/sessions"));
  const cuerpoFormulario = new URLSearchParams(llamadaStripe.opciones.cuerpo);
  const metadataEnviada = {};
  for (const [clave, valor] of cuerpoFormulario.entries()) {
    const m = clave.match(/^metadata\[(.+)\]$/);
    if (m) metadataEnviada[m[1]] = valor;
  }
  return { resultado, metadataEnviada };
}

async function webhook({ eventId, sessionId, consentMarketing = "1", adid, secreto = WHSEC, transporte, registrarDedupe }) {
  const cuerpoCrudo = JSON.stringify({
    id: eventId, type: "checkout.session.completed", created: 1794394800,
    data: { object: {
      id: sessionId, payment_intent: "pi_b0_e2e", payment_status: "paid", amount_total: 1990, currency: "eur",
      metadata: { oferta_id: OFERTA_ID, adid, consent_marketing: consentMarketing, event_source_url: "https://oferta.example/gracias",
                 fbp: "fb.1.1699999999999.1234567890", fbc: "fb.1.1699999999999.abcXYZ" },
    } },
  });
  const tEpoch = 1700000000;
  const firma = await firmarHmacSha256Hex(secreto, `${tEpoch}.${cuerpoCrudo}`);
  return manejarWebhookStripe({
    cabeceraFirma: `t=${tEpoch},v1=${firma}`, cuerpoCrudo, secretoWhsec: WHSEC, toleranciaSeg: 300,
    registrarDedupe, ahora: () => new Date(tEpoch * 1000),
    configCapi: { datasetId: "ds_b0", token: "tok_b0", apiVersion: "v21.0", valorDecimal: "19.90", moneda: "EUR" },
    transporte,
  });
}

const { resultado: resultadoSesion, metadataEnviada } = await crearSesion();

const almacenDedupe = crearAlmacenEnMemoria();
const cerrojo = crearCerrojo();
const registrarDedupe = (claves) => cerrojo.ejecutar(() => registrarSiEsNuevo(almacenDedupe, claves));
const transporteWebhook = crearTransporteFalso();

const sessionId = "cs_test_b0_e2e";
const respuestaFirmaFalsa = await webhook({ eventId: "evt_b0_01", sessionId, adid: AD_ID, secreto: "whsec_incorrecta",  // lint-estatico: permitir=d (valor ficticio)
                                            transporte: transporteWebhook, registrarDedupe });
const respuestaOk = await webhook({ eventId: "evt_b0_01_valida", sessionId, adid: AD_ID, transporte: transporteWebhook, registrarDedupe });
const respuestaDuplicada = await webhook({ eventId: "evt_b0_01_valida", sessionId, adid: AD_ID, transporte: transporteWebhook, registrarDedupe });

const llamadaGraph = transporteWebhook.llamadas.find((l) => l.url.includes("graph.facebook.com"));
const cuerpoGraph = llamadaGraph ? JSON.parse(llamadaGraph.opciones.cuerpo) : null;
const eventIdCapi = cuerpoGraph ? cuerpoGraph.data[0].event_id : null;

console.log(JSON.stringify({
  sesion_status: resultadoSesion.status,
  metadata_adid: metadataEnviada.adid,
  metadata_asid: metadataEnviada.asid,
  metadata_cid: metadataEnviada.cid,
  metadata_consent: metadataEnviada.consent_marketing,
  metadata_visitor_id: metadataEnviada.visitor_id,
  firma_falsa_status: respuestaFirmaFalsa.status,
  firma_falsa_codigo: respuestaFirmaFalsa.cuerpo.codigo,
  ok_status: respuestaOk.status,
  ok_codigo: respuestaOk.cuerpo.codigo,
  duplicada_status: respuestaDuplicada.status,
  duplicada_codigo: respuestaDuplicada.cuerpo.codigo,
  llamadas_graph: transporteWebhook.llamadas.filter((l) => l.url.includes("graph.facebook.com")).length,
  event_id_capi: eventIdCapi,
  event_id_esperado: idPurchase(sessionId),
}));
