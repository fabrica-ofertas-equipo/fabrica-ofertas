// corte.mjs — corte de RESPALDO en la nube (dueño, 17-nov: «Respaldo si cae la Mac»).
//
// Por qué: la noche del 16 al 17-nov la Mac quedó 8,5 h sin internet (Wi-Fi público con portal) y nadie cortó
// Oferta M (gastó US$ 57 con corte en 29,85). El corte lo hacía solo Claude, desde la Mac.
//
// Qué hace: la Mac (nube_sync.py → plan_corte.py) sube cada 5 min el «plan de corte» con los tests del día 1 y
// sus campañas. Si la vigilancia no late hace más de LATIDO_MIN, este módulo decide con la lectura de Meta que el
// worker ya guarda cada 5 min (meta_dia) y con las ventas del webhook, igual que vigilar_corte.py:
//   - test entero: gasto ≥ (1,5 [+0,5 si ya tuvo segunda oportunidad]) × ticket × máx(1, ventas) → pausar sus campañas;
//     sin ventas y con anuncio y página que funcionan (CTR ≥ 1 %, ≥ 8 % de las visitas al pago, ≥ 3 pagos), +0,5 ticket una vez;
//   - por campaña (réplicas: pocket 1 ticket, variaciones 1,5): CPA de ESA campaña ≥ corte → pausar esa.
//   - LÍMITES GENÉRICOS (17-nov, plan.limites): una entrada por campaña con su propio corte, en cualquier fase
//     ({test, campana, tickets, ticket_usd, desde, inicio}). La nube no sabe de roles ni de metodología: suma gasto y
//     compras de la campaña desde `desde` y pausa si gasto ≥ tickets × ticket × máx(1, compras). Qué campañas entran y
//     con cuántos tickets lo decide la Mac (plan_corte.py, desde reglas.json → cortes_por_rol): un tipo de campaña nuevo
//     queda cubierto sin tocar este archivo.
// SOLO PAUSA. Nunca prende, nunca cambia presupuestos. Con la vigilancia viva no hace nada.
// Funciones puras: sin red ni base (se prueban en test/corte.test.mjs).

export const LATIDO_MIN = 30;        // minutos sin latido de la vigilancia para que actúe la nube
export const META_FRESCA_MIN = 15;   // la lectura de Meta tiene que ser reciente
export const PLAN_VIEJO_H = 30;      // un plan más viejo no se usa (la Mac lleva más de un día caída)

const num = (x) => (Number.isFinite(Number(x)) ? Number(x) : 0);
const minutos = (a, b) => (a.getTime() - b.getTime()) / 60000;

/** Por qué la nube NO debe actuar ahora (null = puede actuar). */
export function motivoParaNoActuar(plan, metaEstado, ahora) {
  if (!plan || (!Array.isArray(plan.tests) && !Array.isArray(plan.limites))) return "sin_plan";
  const recibido = Date.parse(plan.recibido || plan.generado || "");
  if (!Number.isFinite(recibido) || minutos(ahora, new Date(recibido)) > PLAN_VIEJO_H * 60) return "plan_viejo";
  const latido = Date.parse(plan.latido_vigilancia || "");
  if (Number.isFinite(latido) && minutos(ahora, new Date(latido)) <= LATIDO_MIN) return "vigilancia_viva";
  if (!metaEstado || metaEstado.error) return "meta_con_error";
  const leido = Date.parse(metaEstado.leido || "");
  if (!Number.isFinite(leido) || minutos(ahora, new Date(leido)) > META_FRESCA_MIN) return "meta_vieja";
  return null;
}

/** Gasto, compras y embudo de una campaña desde `desde` (día de la cuenta en que arrancó el test). */
export function sumarCampana(metaDia, id, desde) {
  const s = { gasto: 0, compras: 0, impresiones: 0, clics: 0, visitas: 0, pagos: 0 };
  for (const f of metaDia || []) {
    if (String(f.campana) !== String(id) || String(f.fecha) < String(desde)) continue;
    s.gasto += num(f.gasto); s.compras += num(f.compras); s.impresiones += num(f.impresiones);
    s.clics += num(f.clics); s.visitas += num(f.visitas); s.pagos += num(f.pagos_iniciados);
  }
  s.gasto = Math.round(s.gasto * 100) / 100;
  return s;
}

/** Ventas principales (sin upsells ni bumps) del webhook en las tiendas del test desde su inicio. */
export function ventasWebhook(ventas, tiendas, inicioIso) {
  const set = new Set((tiendas || []).map(String));
  const ini = Date.parse(inicioIso || "");
  const ordenes = new Set();
  for (const v of ventas || []) {
    if (v.prueba || v.post_compra || v.evento !== "order.approved" || !set.has(String(v.tienda))) continue;
    const t = Date.parse(v.creada || v.recibido || "");
    if (Number.isFinite(ini) && Number.isFinite(t) && t < ini) continue;
    ordenes.add(String(v.orden_id));
  }
  return ordenes.size;
}

/**
 * Decide qué campañas pausar. Devuelve [{test, campana, gasto_usd, corte_usd, ventas, porque}] (vacío si nada).
 * plan.tests[]: {test, inicio, fin, desde, ticket_usd, veces, segunda_usada, extra_tickets, ventas_conocidas, tiendas,
 *               campanas: [{id, corte_tickets?}]}
 * estados: {<id campaña>: "ACTIVE" | "PAUSED" | …} (effective_status de la última lectura).
 */
export function decidirCortes({ plan, metaDia, ventas, estados, ahora }) {
  const pausar = [];
  const SEG = plan.segunda || { extra_tickets: 0.5, ctr_min_pct: 1, pagina_a_pago_min_pct: 8, checkouts_min: 3 };
  for (const t of plan.tests || []) {
    const ini = Date.parse(t.inicio || ""), fin = Date.parse(t.fin || "");
    const ticket = num(t.ticket_usd);
    if (!Number.isFinite(ini) || !Number.isFinite(fin) || ahora.getTime() < ini || ahora.getTime() >= fin || ticket <= 0) continue;
    const camps = (t.campanas || []).filter((c) => c && c.id);
    const datos = camps.map((c) => ({ ...c, ...sumarCampana(metaDia, c.id, t.desde), activa: String(estados[String(c.id)] || "") === "ACTIVE" }));
    if (!datos.some((d) => d.activa)) continue;
    const porCampana = datos.some((d) => d.corte_tickets != null);
    if (porCampana) {
      for (const d of datos) {
        const k = d.corte_tickets != null ? num(d.corte_tickets) : num(t.veces) || 1.5;
        const corte = Math.round(k * ticket * Math.max(1, d.compras) * 100) / 100;
        if (d.activa && d.gasto >= corte) {
          pausar.push({ test: t.test, campana: String(d.id), gasto_usd: d.gasto, corte_usd: corte, ventas: d.compras,
            porque: `Corte por campaña (${k} tickets de US$ ${ticket}): US$ ${d.gasto.toFixed(2)} gastados, ${d.compras} compras, corte US$ ${corte.toFixed(2)}.` });
        }
      }
      continue;
    }
    const tot = datos.reduce((a, d) => ({ gasto: a.gasto + d.gasto, compras: a.compras + d.compras, impresiones: a.impresiones + d.impresiones,
      clics: a.clics + d.clics, visitas: a.visitas + d.visitas, pagos: a.pagos + d.pagos }), { gasto: 0, compras: 0, impresiones: 0, clics: 0, visitas: 0, pagos: 0 });
    tot.gasto = Math.round(tot.gasto * 100) / 100;
    const v = Math.max(num(t.ventas_conocidas), tot.compras, ventasWebhook(ventas, t.tiendas, t.inicio));
    let veces = (num(t.veces) || 1.5) + (t.segunda_usada ? num(t.extra_tickets ?? SEG.extra_tickets) : 0);
    let corte = Math.round(veces * ticket * Math.max(1, v) * 100) / 100;
    if (tot.gasto < corte) continue;
    let nota = "";
    if (!t.segunda_usada && v === 0) {
      const ctr = tot.impresiones ? (tot.clics / tot.impresiones) * 100 : 0;
      const alPago = tot.visitas ? (tot.pagos / tot.visitas) * 100 : 0;
      if (ctr >= SEG.ctr_min_pct && alPago >= SEG.pagina_a_pago_min_pct && tot.pagos >= SEG.checkouts_min) {
        veces += num(SEG.extra_tickets);
        corte = Math.round(veces * ticket * 100) / 100;
        nota = ` Segunda oportunidad aplicada (CTR ${ctr.toFixed(1)} %, ${alPago.toFixed(1)} % al pago, ${tot.pagos} pagos): corte US$ ${corte.toFixed(2)}.`;
        if (tot.gasto < corte) continue;
      }
    }
    for (const d of datos.filter((x) => x.activa)) {
      pausar.push({ test: t.test, campana: String(d.id), gasto_usd: tot.gasto, corte_usd: corte, ventas: v,
        porque: `Corte del test: US$ ${tot.gasto.toFixed(2)} gastados, ${v} ${v === 1 ? "venta" : "ventas"}, corte US$ ${corte.toFixed(2)} (${veces} tickets de US$ ${ticket}).${nota}` });
    }
  }
  return [...pausar, ...decidirLimites({ plan, metaDia, estados, ahora, yaPausadas: new Set(pausar.map((p) => p.campana)) })];
}

/** Límites genéricos por campaña (plan.limites). Devuelve [{test, campana, gasto_usd, corte_usd, ventas, porque}]. */
export function decidirLimites({ plan, metaDia, estados, ahora, yaPausadas = new Set() }) {
  const pausar = [];
  for (const l of (plan && plan.limites) || []) {
    const id = String((l && l.campana) || "");
    const ticket = num(l.ticket_usd), k = num(l.tickets);
    if (!id || ticket <= 0 || k <= 0 || yaPausadas.has(id)) continue;
    const ini = Date.parse(l.inicio || "");
    if (Number.isFinite(ini) && ahora.getTime() < ini) continue;
    if (String(estados[id] || "") !== "ACTIVE") continue;
    const s = sumarCampana(metaDia, id, l.desde || "0000-00-00");
    const corte = Math.round(k * ticket * Math.max(1, s.compras) * 100) / 100;
    if (s.gasto >= corte) {
      yaPausadas.add(id);
      pausar.push({ test: l.test, campana: id, gasto_usd: s.gasto, corte_usd: corte, ventas: s.compras,
        porque: `Corte por campaña${l.rol ? ` (${l.rol})` : ""}: US$ ${s.gasto.toFixed(2)} gastados, ${s.compras} compras, corte US$ ${corte.toFixed(2)} (${k} tickets de US$ ${ticket}).` });
    }
  }
  return pausar;
}
