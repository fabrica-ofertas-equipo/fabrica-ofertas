// lib/negocio.js — lógica pura de la pantalla #/negocio (cartera de ofertas con sus cuentas). Sin DOM y sin red.
// Los números ya llegan calculados por el servidor (dashboard/negocio.py, desde ofertas/_funnels/libro-de-tests.json);
// aquí solo se formatean, se ordenan y se traducen a palabras. Se prueba con `node --test` (tests/dashboard/test_web_negocio.mjs).

const NBSP = ' ';

const esNum = (x) => typeof x === 'number' && Number.isFinite(x);

/** Miles con punto y decimales con coma: 1234.5 → «1.234,50». */
export function numero(x, decimales = 2) {
  if (!esNum(x)) return '—';
  const [ent, dec] = Math.abs(x).toFixed(decimales).split('.');
  const agrupado = ent.replace(/\B(?=(\d{3})+(?!\d))/g, '.');
  return `${x < 0 && Number(Math.abs(x).toFixed(decimales)) !== 0 ? '−' : ''}${agrupado}${dec ? ',' + dec : ''}`;
}

/** Dólares: 29.2 → «US$ 29,20»; −54.9 → «−US$ 54,90». null → «—». */
export function usd(x, { signo = false } = {}) {
  if (!esNum(x)) return '—';
  const n = numero(Math.abs(x));
  const neg = x < 0 && n !== '0,00';
  return `${neg ? '−' : signo && x > 0 ? '+' : ''}US$${NBSP}${n}`;
}

/** Monto en su moneda: (319, 'MXN') → «MX$ 319,00». */
export function moneda(x, cod) {
  if (!esNum(x)) return '—';
  const sim = { MXN: 'MX$', BRL: 'R$', USD: 'US$', ARS: 'AR$', EUR: '€' }[cod] || cod || '';
  return `${sim}${NBSP}${numero(x)}`;
}

/** Porcentaje con coma: 15.94 → «15,9 %». */
export function pct(x, decimales = 1) { return esNum(x) ? `${numero(x, decimales)}${NBSP}%` : '—'; }

/** Retorno por dólar: 1.73 → «1,73 ×». */
export function roas(x) { return esNum(x) ? `${numero(x)}${NBSP}×` : '—'; }

export const ESTADO_OFERTA = {
  activa: { tono: 'ok', texto: 'Activa', icono: 'play' },
  programada: { tono: 'info', texto: 'Programada', icono: 'reloj' },
  pausada: { tono: 'aviso', texto: 'Pausada', icono: 'pausa' },
  cerrada: { tono: 'neutro', texto: 'Cerrada', icono: 'archivar' },
};
export function estadoOferta(e) { return ESTADO_OFERTA[e] || { tono: 'neutro', texto: e ? String(e) : 'Sin dato', icono: 'circulo-punteado' }; }

export const VEREDICTO = {
  ganando: { tono: 'ok', texto: 'Ganando', icono: 'tendencia-sube' },
  perdiendo: { tono: 'error', texto: 'Perdiendo', icono: 'tendencia-baja' },
  sin_pauta: { tono: 'neutro', texto: 'Todavía sin pauta', icono: 'tendencia-igual' },
};
export function veredicto(v) { return VEREDICTO[v] || { tono: 'neutro', texto: 'Sin dato', icono: 'circulo-punteado' }; }

const MERCADOS = { MX: 'México', BR: 'Brasil', AR: 'Argentina', CO: 'Colombia', CL: 'Chile', PE: 'Perú', ES: 'España', US: 'Estados Unidos', PL: 'Polonia', IT: 'Italia', PT: 'Portugal', FR: 'Francia', DE: 'Alemania' };
export function mercado(cod) {
  if (!cod) return 'Sin mercado';
  return String(cod).split('/').map((c) => MERCADOS[c] || c).join(' y ');
}

const PIEZAS_FUNNEL = [
  [/quiz/, 'cuestionario'], [/vsl/, 'video de venta'], [/tsl/, 'página de venta larga'], [/video/, 'con video'],
  [/niveles/, 'dos niveles de precio'], [/subida-previa/, 'oferta mejor antes de pagar'], [/bump/, 'oferta extra al pagar'], [/upsell/, 'oferta después de pagar'],
];
/** «tsl + niveles + subida-previa» → «Página de venta larga · dos niveles de precio · oferta mejor antes de pagar». */
export function tipoFunnel(tipo) {
  if (!tipo) return 'Sin dato';
  const partes = String(tipo).toLowerCase().split(/\s*[+·,]\s*|-(?=video)/).filter(Boolean);
  const salida = [];
  for (const p of partes) {
    const hits = PIEZAS_FUNNEL.filter(([rx]) => rx.test(p)).map(([, t]) => t);
    salida.push(...(hits.length ? hits : [p]));
  }
  const txt = [...new Set(salida)].join(' · ');
  return txt.charAt(0).toUpperCase() + txt.slice(1);
}

/** Solo https, sin espacios ni comillas → {url, dominio}; cualquier otra cosa → null (no se vuelve enlace). */
export function urlExterna(u) {
  if (typeof u !== 'string' || !/^https:\/\/[^\s"'<>\\]+$/.test(u)) return null;
  try {
    const p = new URL(u);
    if (p.protocol !== 'https:') return null;
    return { url: p.href, dominio: p.hostname.replace(/^www\./, '') };
  } catch (_) { return null; }
}

const ORDEN_ESTADO = { activa: 0, programada: 1, pausada: 2, cerrada: 3 };
/** Con etapa (servidor, 13-nov): por urgencia de la etapa (para apagar, para renovar, en test, renovando, renovación programada,
 *  programada, apagada). Sin etapa: activas primero, después programadas y pausadas. Dentro, la que más gana arriba. No muta la entrada. */
const ordenEtapa = (o) => (o && o.etapa && typeof o.etapa.orden === 'number' ? o.etapa.orden : null);
export function ordenarOfertas(ofertas) {
  const orden = (Array.isArray(ofertas) ? ofertas : []).slice().sort((a, b) =>
    (ordenEtapa(a) !== null && ordenEtapa(b) !== null ? ordenEtapa(a) - ordenEtapa(b) : (ORDEN_ESTADO[a.estado] ?? 9) - (ORDEN_ESTADO[b.estado] ?? 9))
    || (b.ganancia_neta ?? -Infinity) - (a.ganancia_neta ?? -Infinity));
  // Las réplicas van pegadas debajo de su oferta madre (pedido del dueño, 14-nov); si la madre no está en la lista, quedan donde caen.
  const nombres = new Set(orden.map((o) => o.nombre));
  const hijas = orden.filter((o) => o.replica_de && nombres.has(o.replica_de));
  if (!hijas.length) return orden;
  const salida = [];
  for (const o of orden) {
    if (hijas.includes(o)) continue;
    salida.push(o, ...hijas.filter((h) => h.replica_de === o.nombre));
  }
  return salida;
}

/** Serie para graficoSerie: [{x: fecha, y: valor}] (null = sin dato, nunca 0 inventado). */
export function serieDiaria(diario, clave) {
  return (Array.isArray(diario) ? diario : []).map((d) => ({ x: d.fecha, y: esNum(d[clave]) ? d[clave] : null }));
}

/** Medidor 0..1 del gasto contra el freno: {fraccion, zona: ok|aviso|error}. */
export function usoFreno(gasto, freno) {
  if (!esNum(gasto) || !esNum(freno) || freno <= 0) return null;
  const f = gasto / freno;
  return { fraccion: Math.min(1, Math.max(0, f)), zona: f >= 1 ? 'error' : f >= 0.8 ? 'aviso' : 'ok', pct: 100 * f };
}

/** Posición de la marca del CPA en la barra del equilibrio (0-100 %) con la escala hasta 1,6 × el equilibrio. */
export function posicionCpa(cpa, equilibrio) {
  if (!esNum(cpa) || !esNum(equilibrio) || equilibrio <= 0) return null;
  const max = Math.max(equilibrio * 1.6, cpa * 1.1);
  return { marca: Math.min(100, (100 * cpa) / max), equilibrio: (100 * equilibrio) / max };
}

/** Avisos del servidor → ítems de ui.atencion, con un botón que abre la ficha de la oferta. */
export function itemsAtencion(items, { abrir, soloOferta } = {}) {
  return (Array.isArray(items) ? items : [])
    .filter((it) => !soloOferta || it.oferta === soloOferta || it.oferta === null)
    .map((it) => ({
      tono: it.tono, titulo: it.titulo, detalle: it.detalle,
      accion: it.oferta && typeof abrir === 'function' && it.oferta !== soloOferta ? { texto: 'Ver la oferta', onClick: () => abrir(it.oferta) } : undefined,
    }));
}

/** Texto del corte: «12/11/2026 20:00» + antigüedad en horas. `viejo` si pasa del umbral. */
export function estadoCorte(corte) {
  const h = corte && esNum(corte.horas) ? corte.horas : null;
  if (h === null) return { tono: 'aviso', texto: 'Sin fecha de corte' };
  if (corte.viejo) return { tono: 'aviso', texto: `Datos de hace ${Math.round(h)} horas: conviene actualizarlos` };
  return { tono: 'ok', texto: h < 1 ? 'Datos de hace menos de una hora' : `Datos de hace ${Math.round(h)} ${Math.round(h) === 1 ? 'hora' : 'horas'}` };
}

/** Fecha y hora en la zona del corte (la del libro) para no confundir: «12/11/2026 20:00 (UTC−03:00)». */
export function textoCorte(iso) {
  if (typeof iso !== 'string') return '—';
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::\d{2})?(?:\.\d+)?([+-]\d{2}:\d{2}|Z)?$/.exec(iso);
  if (!m) return iso;
  const zona = !m[6] || m[6] === 'Z' || m[6] === '+00:00' ? 'UTC' : `UTC${m[6].replace('-', '−')}`;
  const nombre = { 'UTC−03:00': 'hora de Argentina y Brasil', 'UTC−06:00': 'hora del centro de México' }[zona];
  return `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]} (${nombre || zona})`;
}

/** Acción sugerida (regla propuesta, sin firmar): icono por clave. */
export const ICONO_ACCION = { escalar: 'tendencia-sube', cortar: 'x-circulo', mirar: 'ojo', sin_pauta: 'reloj' };
export function accion(a) {
  if (!a || typeof a !== 'object') return { clave: 'sin_dato', texto: 'Sin dato', tono: 'neutro', icono: 'circulo-punteado', porque: '', regla: '' };
  return { ...a, icono: ICONO_ACCION[a.clave] || 'circulo-punteado' };
}

/** «en 6 h» / «en 2 días» / «ahora» para un cambio programado. */
export function faltaPara(horas) {
  if (!esNum(horas)) return '';
  if (horas < 1) return 'en menos de una hora';
  if (horas < 48) return `en ${Math.round(horas)} h`;
  return `en ${Math.round(horas / 24)} días`;
}

/** Definiciones del dueño (2026-11-12): nombre y fórmula de cada número. Se usan en el «?» de cada cifra y en «Cómo se calcula». */
export const DEFINICIONES = {
  facturacion_bruta: { titulo: 'Facturación bruta', texto: 'Suma del bruto de las ventas reales de la tienda: lo que pagó el comprador.' },
  comisiones: { titulo: 'Comisiones e impuestos', texto: 'Bruto − neto: lo que se queda Impul Pay.' },
  facturacion_neta: { titulo: 'Facturación neta', texto: 'Suma del neto que informa Impul Pay de cada venta, después de comisiones e impuestos.' },
  costo_meta: { titulo: 'Meta', texto: 'Gasto en anuncios de Meta al corte.' },
  costo_produccion: { titulo: 'Producción', texto: 'Kie (créditos × US$ 0,005, renovaciones incluidas) + Gemini (imágenes y voces) + otros. Sale del barrido diario de los registros de gasto de cada carpeta y del audio de las voces; si lo anotado a mano es mayor, manda lo anotado. La transcripción (whisper) es local y no cuesta. Se gastó una vez para armar el funnel y se imputa al día de inicio de la pauta: con un período elegido, entra en la ganancia neta y en el ROAS real solo si ese día cae dentro.' },
  costo_fijos: { titulo: 'Fijos repartidos', texto: 'Costos fijos por mes (plan de Impultienda, dominio) ÷ 30 × días de pauta del período ÷ ofertas de la cartera.' },
  costo_total: { titulo: 'Costos totales', texto: 'Meta + producción + fijos repartidos.' },
  ganancia_contra_meta: { titulo: 'Ganancia contra Meta (contribución)', texto: 'Facturación neta − gasto en Meta. Dice si los anuncios se pagan solos.' },
  ganancia_neta: { titulo: 'Ganancia neta', texto: 'Facturación neta − Meta − producción − fijos repartidos. Dice si el funnel completo ya recuperó lo que costó.' },
  roas_meta: { titulo: 'ROAS Meta', texto: 'Valor de compras que atribuye Meta ÷ gasto en Meta. Es el que muestra el administrador de anuncios.' },
  roas_bruto: { titulo: 'ROAS bruto real', texto: 'Facturación bruta real ÷ gasto en Meta.' },
  roas_neto: { titulo: 'ROAS neto', texto: 'Facturación neta ÷ gasto en Meta. Equilibrio contra anuncios: 1,00 ×. No incluye la producción: mide solo lo que rinde cada dólar de anuncios, para decidir si escalar.' },
  roas_real: { titulo: 'ROAS real (retorno total)', texto: 'Facturación neta ÷ (Meta + producción + fijos repartidos). Equilibrio: 1,00 ×. Dice si el funnel completo ya recuperó lo que costó armarlo.' },
  ventas: { titulo: 'Ventas', texto: 'Reales: las que registró la tienda. Atribuidas: las que Meta se adjudica a sus anuncios.' },
  ticket_medio: { titulo: 'Ticket medio por comprador (AOV)', texto: 'Facturación bruta ÷ compradores: el principal más los upsells, bumps y downsells de esos mismos compradores.' },
  ventas_reales: { titulo: 'Ventas', texto: 'Ventas aprobadas en la tienda (Impultienda), sin contar upsells ni bumps como compradores. Es el número real; Meta solo ve las que puede atribuir a un anuncio, por eso suele mostrar menos.' },
  cr_tienda: { titulo: 'CR de la tienda', texto: 'Compras ÷ visitas a la landing, con TODAS las tiendas del funnel juntas. Impultienda calcula el CR de cada tienda por separado: la de la landing tiene las visitas y las de los otros niveles solo el checkout, así que una marca 0,5 % y otra 600 %. Acá se suman. Referencia: 2-3,6 % (checkout 8-12 % × compra 25-30 %).' },
  facturacion: { titulo: 'Facturación', texto: 'Lo que pagaron los compradores (bruto), en USD, con upsells y bumps. Debajo, lo que queda neto después de comisiones e impuestos.' },
  aov: { titulo: 'AOV', texto: 'Lo que paga en promedio cada comprador: facturación bruta ÷ compradores (principal + upsells, bumps y downsells). Referencia con backend: 1,5 × el precio del principal o más.' },
  margen_neto: { titulo: 'Margen neto', texto: 'Ganancia neta ÷ facturación bruta: de cada dólar que paga el cliente, cuánto queda después de comisiones, Meta, producción y fijos.' },
  margen_contra_meta: { titulo: 'Margen de la operación', texto: '(Facturación neta − Meta) ÷ facturación bruta: el margen del día a día, sin la producción que se pagó una sola vez. Es el que tiene que ser positivo para escalar.' },
  take_rate: { titulo: 'Toma de upsells', texto: 'Ventas extra (upsell, downsell, bump) ÷ compradores. Con backend activo, la referencia es 20-40 %.' },
  ganancia_dia: { titulo: 'Ganancia del último día', texto: 'Facturación neta − Meta del último día completo con gasto leído (sin producción). Es siempre el mismo número, elijas el período que elijas. Es lo que suma cada día hacia la meta de 10.000 USD netos por día.' },
  facturacion_neta_cartera: { titulo: 'Facturación neta', texto: 'Lo que entra de verdad en el período: la suma del neto que informa Impul Pay de cada venta, ya descontadas comisiones, impuestos y cambio. Debajo, el bruto que pagaron los compradores y lo que se quedó en comisiones.' },
  cpa_periodo: { titulo: 'CPA del período', texto: 'Gasto en Meta ÷ ventas reales (compradores) del período elegido. En verde si está por debajo del equilibrio (facturación neta ÷ ventas): cada venta deja más de lo que cuesta en anuncios.' },
  comision_pct: { titulo: 'Comisiones', texto: '(Bruto − neto) ÷ bruto: lo que se queda Impul Pay con impuestos y cambio.' },
  cpa_real: { titulo: 'CPA real', texto: 'Gasto en Meta ÷ ventas reales: lo que cuesta cada venta en anuncios.' },
  cpa_equilibrio: { titulo: 'CPA de equilibrio', texto: 'Facturación neta ÷ ventas: lo máximo que se puede pagar por venta sin perder contra Meta. Equivale a un ROAS neto de 1,00 ×.' },
};

/** Respuesta del dueño que queda escrita en pantalla: dónde entra la producción. */
export const PRODUCCION_Y_ROAS = 'La producción no entra en el ROAS: el ROAS mide solo lo que rinde cada dólar de anuncios, para decidir si escalar. Entra en el ROAS real y en la ganancia neta, que dicen si el funnel completo ya recuperó lo que costó armarlo.';

/** Tono de un ROAS contra su equilibrio de 1,00 ×: ok por encima o igual, error por debajo, null sin dato. */
export function tonoRoas(x) { return esNum(x) ? (x >= 1 ? 'ok' : 'error') : null; }
