// Catalogo firmado oferta_id -> price_id (docs/06 4.3: "Precio solo del
// catalogo firmado"; docs/07 2.4: "el precio nunca viene del cliente").
//
// Decision (ver README "Decisiones"): no existe hoy un
// `contratos/catalogo.schema.json` que fije el formato exacto de este
// documento (lo produce `landing.catalogo`, de B4; CT aun no lo modelo).
// Se asume la forma minima necesaria para validar lo que el backbone exige
// (precio de servidor, adid/asid/cid del catalogo firmado). Pedido abierto
// a CT/B4 para fijar un esquema propio.
//
// Forma asumida (JSON ya serializado + firma HMAC aparte, nunca en el mismo
// valor que se firma):
// {
//   "ofertas": {
//     "OF-202611-01": {
//       "price_id": "price_front_v1",
//       "price_id_bump": "price_bump_v1" | null,
//       "moneda": "EUR",
//       "success_url": "https://...",
//       "return_url": "https://...",
//       "ids_meta": { "campaign_id": "123...", "adset_ids": ["456..."], "ad_ids": ["789..."] },
//       "landing_version": "v3",                           // opcional; "desconocida" si falta
//       "renuncia": { "requerido": true, "texto_version": "v1" } // opcional (modo formulario,
//                                                                 // ver formulario.mjs); si falta,
//                                                                 // decide env.localesRenunciaRequerida
//     }
//   }
// }

import { verificarHmacSha256 } from "../../_lib/src/hmac.mjs";

/** Verifica la firma HMAC del catalogo y devuelve el objeto parseado, o null si no es valido. */
export async function cargarCatalogoVerificado(catalogoJson, firmaHex, secretoCatalogoHmac) {
  if (typeof catalogoJson !== "string" || !catalogoJson || !firmaHex || !secretoCatalogoHmac) {
    return null;
  }
  const valida = await verificarHmacSha256(secretoCatalogoHmac, catalogoJson, firmaHex);
  if (!valida) return null;
  try {
    return JSON.parse(catalogoJson);
  } catch {
    return null;
  }
}

/** Entrada del catalogo para una oferta, o null si no existe. */
export function entradaOferta(catalogo, ofertaId) {
  return catalogo?.ofertas?.[ofertaId] ?? null;
}

/** `true` si el id figura en la lista correspondiente de `ids_meta` de la oferta. */
export function idEnCatalogo(entrada, campo, valor) {
  if (!entrada?.ids_meta) return false;
  if (campo === "cid") return entrada.ids_meta.campaign_id === valor;
  if (campo === "asid") return (entrada.ids_meta.adset_ids ?? []).includes(valor);
  if (campo === "adid") return (entrada.ids_meta.ad_ids ?? []).includes(valor);
  return false;
}
