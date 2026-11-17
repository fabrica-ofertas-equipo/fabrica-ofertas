// Validacion del cuerpo de `POST /api/ev` (docs/06 4.3: PageView/ViewContent).
import {
  esOfertaIdValido,
  esVisitorIdValido,
  esIdAtribucionValido,
  esTimestampZValido,
} from "../../_lib/src/formatos.mjs";

const TIPOS_PERMITIDOS = new Set(["PageView", "ViewContent"]);
const FUENTES_PERMITIDAS = new Set(["pixel", "landing"]);

/** Devuelve `{ ok, errores: string[] }`. */
export function validarEvento(cuerpo) {
  const errores = [];
  if (!cuerpo || typeof cuerpo !== "object") {
    return { ok: false, errores: ["cuerpo_invalido"] };
  }
  if (!esOfertaIdValido(cuerpo.oferta_id)) errores.push("oferta_id_invalido");
  if (!TIPOS_PERMITIDOS.has(cuerpo.tipo)) errores.push("tipo_invalido");
  if (!esTimestampZValido(cuerpo.ts)) errores.push("ts_invalido");
  if (!esVisitorIdValido(cuerpo.visitor_id)) errores.push("visitor_id_invalido");
  for (const campo of ["cid", "asid", "adid"]) {
    const valor = cuerpo[campo];
    if (valor !== undefined && valor !== null && !esIdAtribucionValido(valor)) {
      errores.push(`${campo}_invalido`);
    }
  }
  if (!FUENTES_PERMITIDAS.has(cuerpo.fuente)) errores.push("fuente_invalida");
  if (cuerpo.consentimiento !== true && cuerpo.consentimiento !== false) {
    errores.push("consentimiento_invalido");
  }
  // M10 (docs/06 4.3): ningun dato de salud o financiero viaja aqui; este
  // Worker no acepta texto libre, solo los campos tipados de arriba.
  return { ok: errores.length === 0, errores };
}
