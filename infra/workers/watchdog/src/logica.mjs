// Lógica PURA del watchdog (docs/07-puesta-en-marcha.md §9.2). Sin `fetch`, sin KV, sin reloj del
// sistema: todo instante entra como parámetro. `src/index.mjs` es la envoltura de efectos (KV, fetch a
// Meta, cron); aquí solo hay decisiones, para poder probarlas con `node --test` sin un Worker real.
//
// Espejo de `infra/latido.evaluar_vencimiento` (Python): MISMOS vectores en ambos lados
// (`tests/infra/test_latido.py` y `test/logica.test.mjs`).

// Hecho de plataforma (Meta puede gastar hasta ~1,75x el presupuesto diario), no una decisión del
// dueño: misma constante que `empresa/limites.yaml: factor_techo_teorico_diario` y
// `scripts/validar_esquemas.py: FACTOR_META_MIN` (investigación 04, HC-26 [VERIFICAR texto oficial]).
export const FACTOR_TECHO_TEORICO_DIARIO = 1.75;
// Umbral de alerta de `account.amount_spent` contra `LIMITE_CUENTA_MINOR` (docs/07 §9.2.2): "pausando al 90 %".
export const UMBRAL_LIMITE_CUENTA_FRACCION = 0.9;
const MS_POR_MIN = 60000;
const MS_SEIS_HORAS = 6 * 60 * MS_POR_MIN;

/**
 * ¿Debe pausar el watchdog según el latido? Devuelve `{ pausar, motivo }`. Nunca lanza: una fecha
 * ilegible cuenta como "sin latido" (fail-closed).
 */
export function debePausarPorLatido({
  ultimoLatidoIso,
  ahoraIso,
  latidoMaxMin,
  semaforo,
  pausa,
  estadoGeneradoEnIso,
  cicloMaxMin,
  ultimoCicloD8Iso,
}) {
  const ahora = Date.parse(ahoraIso);
  if (!ultimoLatidoIso) return { pausar: true, motivo: "sin latido registrado todavía" };
  const ultimo = Date.parse(ultimoLatidoIso);
  if (Number.isNaN(ahora) || Number.isNaN(ultimo)) return { pausar: true, motivo: "fecha ilegible (fail-closed)" };
  if (ahora - ultimo > latidoMaxMin * MS_POR_MIN) {
    return { pausar: true, motivo: `sin latido hace más de ${latidoMaxMin} min` };
  }
  if (pausa) return { pausar: true, motivo: "el latido declara pausa=true" };
  if (semaforo === "ROJO") return { pausar: true, motivo: "el latido declara semaforo=ROJO" };
  if (estadoGeneradoEnIso) {
    const gen = Date.parse(estadoGeneradoEnIso);
    if (!Number.isNaN(gen) && ahora - gen > MS_SEIS_HORAS) {
      return { pausar: true, motivo: "estado_generado_en de más de 6 h" };
    }
  }
  if (cicloMaxMin != null && ultimoCicloD8Iso) {
    const ciclo = Date.parse(ultimoCicloD8Iso);
    if (!Number.isNaN(ciclo) && ahora - ciclo > cicloMaxMin * MS_POR_MIN) {
      return { pausar: true, motivo: "ultimo_ciclo_d8_ts vencido: D8 colgado con el latido vivo" };
    }
  }
  return { pausar: false, motivo: "latido vigente" };
}

/** ¿Están `GASTO_DIARIO_MAX_MINOR` y `CUENTA_TZ` configuradas? Sin ellas, `/estado` responde 503 (nunca se omite la barrera). */
export function variablesObligatoriasPresentes(env) {
  return Boolean(env && env.GASTO_DIARIO_MAX_MINOR && env.CUENTA_TZ);
}

/** Gasto de "hoy" (día de `CUENTA_TZ`, lo resuelve `index.mjs`) contra el tope x el factor de Meta. */
export function debePausarPorGastoDiario({ gastoHoyMinor, gastoDiarioMaxMinor }) {
  if (gastoHoyMinor == null || gastoDiarioMaxMinor == null) return false;
  return gastoHoyMinor > gastoDiarioMaxMinor * FACTOR_TECHO_TEORICO_DIARIO;
}

/** `account.amount_spent` contra `LIMITE_CUENTA_MINOR`, pausando al 90 % (docs/07 §9.2.2). */
export function debePausarPorLimiteCuenta({ amountSpentMinor, limiteCuentaMinor }) {
  if (amountSpentMinor == null || limiteCuentaMinor == null) return false;
  return amountSpentMinor >= limiteCuentaMinor * UMBRAL_LIMITE_CUENTA_FRACCION;
}

/** Decisión agregada de una evaluación de cron (docs/07 §9.2.2, paso 2). `hayActivas` = campañas ACTIVE. */
export function evaluarCiclo(entrada) {
  const { hayActivas } = entrada;
  const porLatido = debePausarPorLatido(entrada);
  if (!hayActivas) {
    return { pausar: false, motivo: "sin campañas ACTIVE: nada que pausar", detalle: porLatido };
  }
  if (porLatido.pausar) return { pausar: true, motivo: porLatido.motivo, detalle: porLatido };
  if (debePausarPorGastoDiario(entrada)) return { pausar: true, motivo: "gasto de hoy supera el tope x factor de Meta" };
  if (debePausarPorLimiteCuenta(entrada)) return { pausar: true, motivo: "amount_spent al 90 % o más de LIMITE_CUENTA_MINOR" };
  return { pausar: false, motivo: "todo dentro de los topes" };
}
