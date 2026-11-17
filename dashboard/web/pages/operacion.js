// pages/operacion.js — #/operacion: cómo se comporta una oferta en vivo (CONTRATO §3-§5, §7b; criterio B0-17; rediseño U4).
// Orden de lectura: qué requiere atención → métricas grandes con contexto → veredicto (protagonista) → tendencias → qué decidió el motor →
// órdenes de presupuesto → datos por día. Lo técnico (reglas G/K/M, ids, hashes, tablas completas) va en detalles técnicos.
// Fuentes: GET /operacion/<id>, 03-oferta/economia.json (CPA de equilibrio y objetivo), /parametros (topes y umbrales) y /finanzas (cobertura de adid).
// Solo lectura. Todo texto de datos entra por ui.el (textContent). Cifra vieja = tachada con su causa; dato ausente = «sin dato», nunca un 0.

import {
  ayudasVista, instalarEstilos, modeloOperacion, comandosOperacion, FAMILIAS, NOMBRE_DECISION, ARCHIVO_DECISIONES, monedaDeUnidad, textoDuracionH, aNumero,
  describirDecision, describirOrden, atencionOperacion, NOMBRE_KPI,
} from '../lib/operacion.js';
import { rotuloNivel } from '../lib/resumen.js';

/** Punto de control en palabras («Requiere tu firma · Autonomía 2») en vez de las letras sueltas «H · N2». */
const PALABRAS_CONTROL = { A: 'Se aprueba sola', S: 'Solo por excepción', H: 'Requiere tu firma' };
const textoControl = (gate, nivel) => [gate ? (PALABRAS_CONTROL[gate] || gate) : null, nivel ? rotuloNivel(nivel) : null].filter(Boolean).join(' · ') || '—';
import { graficoSerie, lineaMadurez, bulletCpa } from '../lib/graficos.js';

export const meta = { ruta: 'operacion', titulo: 'Resultados', grupo: 'Testeo y escala', icono: 'pulso', escucha: ['oferta', 'empresa'] };

const enc = encodeURIComponent;
// Estado de la interfaz que sobrevive a una actualización en vivo (filtro de decisiones).
const UI = { familia: 'todas' };

/** Formateador de un valor de KPI según su `unidad` (EUR_minor, porcentaje, razon, compras, clics…). */
function formatoDeUnidad(unidad, fmt) {
  const m = monedaDeUnidad(unidad);
  if (m) return (v) => fmt.dinero(v, m);
  if (unidad === 'porcentaje') return (v) => `${String(v).replace('.', ',')} %`;
  if (unidad === 'razon') return (v) => String(v).replace('.', ',');
  if (typeof unidad === 'string' && /^(compras|clics|impresiones)$/.test(unidad)) return (v) => (typeof v === 'number' ? fmt.num(v) : String(v));
  return (v) => String(v);
}

const decimalEs = (n, d = 2) => (n === null ? '—' : n.toFixed(d).replace('.', ','));
const pctEs = (n) => `${String(n).replace('.', ',')} %`;

async function leerOpcional(api, ruta, params) {
  try { return await api.sobre(ruta, params); } catch (_) { return null; }
}

function economiaDeSobre(sobre) {
  if (!sobre || !sobre.datos) return null;
  const c = sobre.datos.contenido;
  if (c && typeof c === 'object') return c;
  if (typeof c === 'string') { try { return JSON.parse(c); } catch (_) { return null; } }
  return null;
}

function hayEdicion() {
  const d = globalThis.document;
  const a = d && d.activeElement;
  return Boolean(a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) || Boolean(d && d.querySelector('.modal-fondo'));
}

const botonActualizar = (ctx) => ctx.ui.el('button', { type: 'button', class: 'btn btn--chico', onclick: () => ctx.recargar() }, ctx.ui.icono('refrescar', { tam: 14 }), 'Actualizar');

// ───────────────────────── sin oferta elegida ─────────────────────────

async function pantallaElegir(ctx) {
  const { api, ui, fmt, estado } = ctx;
  const { el } = ui;
  const ayudas = ayudasVista(ui, fmt);
  let sobre = null;
  let error = null;
  try { sobre = await api.sobre('/ofertas'); } catch (e) { error = e; }
  const ofertas = sobre && Array.isArray(sobre.datos) ? sobre.datos : (estado.ofertas || []);
  const cuerpo = [];
  if (error && !ofertas.length) cuerpo.push(ui.errorBox(error));
  else if (!ofertas.length) {
    cuerpo.push(ayudas.vacioConComandos('Todavía no hay ofertas con operación.', {
      pista: 'Esta pantalla muestra una oferta en vivo: lo que gasta, las compras reales de Stripe, el costo por venta y lo que decide el sistema. Se llena cuando una oferta tiene la campaña activa y se hizo el primer cierre del día.',
      archivo: 'ofertas/<id>/08-operacion/diario/<fecha>/kpi_oferta_dia.json',
      comandos: [{ etiqueta: 'Calcula las cifras de un día (simulacro: no cambia nada)', cmd: comandosOperacion(null, null).kpi }],
    }));
  } else {
    cuerpo.push(el('p', { class: 'p5-sub' }, 'Elige una oferta (también desde el selector de la barra superior) para ver su operación.'));
    cuerpo.push(ui.tabla({
      etiqueta: 'Ofertas', filtro: { placeholder: 'Filtrar ofertas…' }, ordenInicial: { clave: 'oferta_id', dir: 'asc' },
      alClick: (f) => estado.fijar({ ofertaActiva: f.oferta_id }),
      columnas: [
        { clave: 'oferta_id', titulo: 'Oferta', formato: (v, f) => el('span', null, v, f.demo ? [' ', ui.chip('ejemplo', 'info', { icono: false })] : null) },
        { clave: 'fase', titulo: 'Fase', formato: (v) => ui.estadoIcono(v) },
        { clave: 'nivel', titulo: 'Autonomía', formato: (v) => (v ? rotuloNivel(v) : '—') },
        { clave: 'gasto.hoy', titulo: 'Gasto hoy', alinear: 'der', orden: (f) => (f.gasto && f.gasto.hoy ? f.gasto.hoy.monto : null), formato: (v) => (v && Number.isSafeInteger(v.monto) ? fmt.dinero(v.monto, v.moneda) : el('span', { class: 'cifra-sin-dato' }, 'sin dato')) },
        { clave: 'gasto.acumulado', titulo: 'Gasto acumulado', alinear: 'der', orden: (f) => (f.gasto && f.gasto.acumulado ? f.gasto.acumulado.monto : null), formato: (v) => (v && Number.isSafeInteger(v.monto) ? fmt.dinero(v.monto, v.moneda) : el('span', { class: 'cifra-sin-dato' }, 'sin dato')) },
        { clave: 'actualizado_en', titulo: 'Actualizado', formato: (v) => (v ? ui.tiempo(v) : '—') },
      ],
      filas: ofertas, vacio: 'Sin ofertas.',
    }));
  }
  return el('div', { class: 'pagina' },
    ui.encabezadoPagina({ titulo: 'Resultados', descripcion: 'Cómo se comporta una oferta en vivo: gasto frente a topes, compras reales, costo por venta frente al punto de equilibrio, decisiones del sistema y veredicto.', acciones: botonActualizar(ctx) }),
    ui.seccion('Elige una oferta', cuerpo, { ayuda: 'No hay oferta activa en la barra superior.' }),
    ui.fuenteInfo(sobre || { fuente: ['empresa/ofertas'] }));
}

// ───────────────────────── métricas ─────────────────────────

const tonoDeUso = (uso) => (!uso ? null : uso.zona === 'rojo' ? 'critico' : uso.zona === 'aviso' ? 'aviso' : null);
const sinNulos = (serie) => serie.filter((s) => s.y !== null && s.estado !== 'tachada').map((s) => s.y);

function metricaGastoHoy(ctx, m, ayudas) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const u = m.ultima;
  const cifra = u ? u.cifras.gasto_meta : null;
  const moneda = (u && monedaDeUnidad(cifra.unidad)) || m.moneda;
  const valor = u ? ayudas.cifraEl(cifra, (v) => fmt.dinero(v, moneda)) : null;
  const acum = m.acumulado;
  const topeTxt = m.topes && m.topes.diario !== null ? `tope diario por oferta: ${fmt.dinero(m.topes.diario, m.topes.moneda || moneda)}` : null;
  return ui.metrica({
    etiqueta: 'Gasto hoy', valor, ayuda: 'tope', tono: cifra && cifra.estado === 'tachada' ? 'critico' : tonoDeUso(m.usoDiario),
    serie: sinNulos(m.series.gasto),
    contexto: el('div', { class: 'p5-ctx' },
      el('span', { class: 'p5-sub' }, u ? `Último día leído: ${fmt.fecha(u.fecha)}` : 'Todavía no hay cifras diarias'),
      ayudas.barraUso(m.usoDiario, 'Gasto de hoy'),
      topeTxt ? el('span', { class: 'p5-sub' }, topeTxt) : null,
      acum.gasto
        ? el('div', { class: 'p5-ctx' },
          el('span', { class: 'p5-sub' }, el('strong', null, 'Acumulado de la prueba: '), fmt.dinero(acum.gasto.monto, acum.gasto.moneda), !acum.completo ? ' (parcial: faltan días)' : ''),
          m.topes && m.topes.total !== null ? ayudas.barraUso(m.usoTotal, 'Gasto acumulado') : null,
          m.topes && m.topes.total !== null ? el('span', { class: 'p5-sub' }, `tope total de la prueba: ${fmt.dinero(m.topes.total, m.topes.moneda || acum.gasto.moneda)}`) : null)
        : null),
  });
}

function metricaCompras(ctx, m) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const v = m.veredicto;
  const a = m.acumulado;
  const conVeredicto = v && v.evidencia.compras_netas !== null;
  const valor = conVeredicto ? v.evidencia.compras_netas : a.compras;
  return ui.metrica({
    etiqueta: conVeredicto ? 'Compras netas' : 'Compras (Stripe)', valor: valor === null ? null : fmt.num(valor), ayuda: 'compras_netas', serie: sinNulos(m.series.compras),
    contexto: el('div', { class: 'p5-ctx' },
      conVeredicto
        ? el('span', { class: 'p5-sub' }, `${fmt.num(v.evidencia.compras_brutas ?? 0)} compras · ${fmt.num(v.evidencia.reembolsos ?? 0)} reembolsadas`)
        : el('span', { class: 'p5-sub' }, a.compras === null ? 'Aún no hay compras registradas' : 'Todavía sin descontar reembolsos (aún no hay veredicto)'),
      v && v.evidencia.compras_meta_referencia !== null ? el('span', { class: 'p5-sub' }, `Meta cuenta ${fmt.num(v.evidencia.compras_meta_referencia)} (solo referencia)`) : null,
      a.dias ? el('span', { class: 'p5-sub' }, `${a.dias} ${a.dias === 1 ? 'día' : 'días'} con cifras`) : null),
  });
}

function metricaCpa(ctx, m) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const z = m.zonaCpa;
  const eco = m.economia;
  const textoZona = { objetivo: ['Bajo el objetivo', 'ok'], equilibrio: ['Entre el objetivo y el punto de equilibrio', 'aviso'], sobre: ['Sobre el punto de equilibrio', 'error'] }[z.zona];
  const bala = m.cpa && eco && eco.cpa_be ? bulletCpa(ui, { cpa: m.cpa.monto, be: eco.cpa_be.monto, obj: eco.cpa_obj ? eco.cpa_obj.monto : null, formato: (x) => fmt.dinero(x, eco.cpa_be.moneda) }) : null;
  const valor = m.cpa ? fmt.dinero(m.cpa.monto, m.cpa.moneda) : null;
  return ui.metrica({
    etiqueta: 'Costo por venta real', valor, ayuda: 'cpa', tono: z.gris ? 'neutro' : textoZona ? textoZona[1] : null, serie: sinNulos(m.series.cpa),
    contexto: el('div', { class: 'p5-ctx' },
      bala,
      eco && eco.cpa_be
        ? el('span', { class: 'p5-sub' }, 'Punto de equilibrio ', ui.termino('cpa_equilibrio', { texto: fmt.dinero(eco.cpa_be.monto, eco.cpa_be.moneda) }), eco.cpa_obj ? [' · objetivo ', ui.termino('cpa_objetivo', { texto: fmt.dinero(eco.cpa_obj.monto, eco.cpa_obj.moneda) })] : null)
        : el('span', { class: 'p5-sub' }, 'Sin la economía de la oferta no hay punto de equilibrio con el que comparar.'),
      textoZona ? ui.chip(z.gris ? `${textoZona[0]} · poca muestra` : textoZona[0], z.gris ? 'neutro' : textoZona[1]) : null,
      z.gris && z.motivoGris ? el('span', { class: 'p5-sub' }, z.motivoGris) : null,
      m.cpa && m.cpaParcial ? el('span', { class: 'p5-sub' }, `Solo ${m.acumulado.comparables.dias} de ${m.acumulado.dias} días son comparables`) : null,
      !m.cpa ? el('span', { class: 'p5-causa' }, z.causa || 'sin costo por venta') : null),
  });
}

function metricaReembolsos(ctx, m, ayudas) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const c = m.ultima ? m.ultima.cifras.tasa_reembolso : null;
  const v = m.veredicto;
  let valor = null;
  let contexto;
  if (v && v.evidencia.reembolso_pct !== null) {
    valor = pctEs(decimalEs(v.evidencia.reembolso_pct, v.evidencia.reembolso_pct % 1 ? 1 : 0));
    contexto = `${fmt.num(v.evidencia.reembolsos ?? 0)} de ${fmt.num(v.evidencia.compras_brutas ?? 0)} compras (solo compras ya sin riesgo de reembolso)`;
  } else if (c && c.estado !== 'ausente' && c.valor !== null) {
    valor = ayudas.cifraEl(c, formatoDeUnidad(c.unidad, fmt));
    contexto = 'Solo compras ya sin riesgo de reembolso';
  } else contexto = m.ultima ? 'El último día no incluye la tasa de reembolsos' : 'Sin cifras ni veredicto todavía';
  const req = v && v.requisitos.find((r) => r.id === 'reembolsos');
  return ui.metrica({
    etiqueta: 'Reembolsos', valor, ayuda: 'ratio_reembolsos', tono: req ? (req.cumple ? 'ok' : 'error') : null,
    contexto: el('div', { class: 'p5-ctx' }, el('span', { class: 'p5-sub' }, contexto), req ? el('span', { class: 'p5-sub' }, `Máximo para validar: ${decimalEs(req.minimo, 0)} %`) : null),
  });
}

function metricaCobertura(ctx, m, ayudas) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const c = m.cobertura;
  const min = m.umbralCoberturaPct;
  let valor = null;
  let origen = null;
  let bajo = null;
  if (c && c.valor !== null) {
    valor = ayudas.cifraEl(c, formatoDeUnidad(c.unidad || 'porcentaje', fmt));
    const n = aNumero(c.valor);
    bajo = min !== null && n !== null ? n < min : null;
    origen = 'De las compras del último día';
  } else if (m.coberturaConciliacionBp !== null) {
    valor = fmt.pct(m.coberturaConciliacionBp);
    bajo = min !== null ? m.coberturaConciliacionBp < min * 100 : null;
    origen = 'Del cotejo de cuentas de toda la empresa';
  }
  return ui.metrica({
    etiqueta: 'Compras ligadas a un anuncio', valor, ayuda: 'cobertura_atribucion', tono: bajo === true ? 'critico' : bajo === false ? 'ok' : null,
    contexto: el('div', { class: 'p5-ctx' },
      origen ? el('span', { class: 'p5-sub' }, origen) : el('span', { class: 'p5-causa' }, 'Ni las cifras diarias ni el cotejo de cuentas la traen'),
      min !== null ? el('span', { class: 'p5-sub' }, `Mínimo para decidir: ${decimalEs(min, 0)} %`) : null,
      bajo === true ? ui.chip('Bajo el mínimo: el sistema decide a ciegas', 'error') : null),
  });
}

// ───────────────────────── veredicto (protagonista) ─────────────────────────

const ICONO_VEREDICTO = { VALIDADA: 'ok', PROMETEDORA: 'escalar', FALLIDA: 'x-circulo', INCONCLUSA: 'ayuda' };
const CLAVE_GATE = { A: 'gate_a', S: 'gate_s', H: 'gate_h' };

function requisito(ctx, r) {
  const { ui } = ctx;
  const { el } = ui;
  const ayudas = ayudasVista(ui, ctx.fmt);
  const bp = Math.min(10000, Math.round((r.actual / (r.minimo || 1)) * 10000));
  const zona = r.cumple ? 'ok' : r.sentido === 'min' ? 'aviso' : 'rojo';
  const nombre = r.id === 'compras' ? 'Compras netas' : r.id === 'dias' ? 'Días con datos' : r.etiqueta;
  return el('div', { class: 'p5-req' },
    el('div', { class: 'p5-req__cab' }, el('span', null, nombre), el('span', { class: `p5-req__estado${r.cumple ? ' p5-req__estado--ok' : ''}` }, ui.icono(r.cumple ? 'ok' : (r.sentido === 'max' ? 'alerta' : 'circulo-punteado'), { tam: 13 }), r.cumple ? 'Cumple' : (r.sentido === 'max' ? 'Se pasa del máximo' : 'Falta'))),
    ayudas.medidor({ bp, zona, texto: r.sentido === 'max' ? `${String(r.actual).replace('.', ',')} % · máximo ${String(r.minimo).replace('.', ',')} %` : `${String(r.actual).replace('.', ',')} de ${String(r.minimo).replace('.', ',')} necesarias`, etiqueta: `${nombre}: ${r.actual} de ${r.minimo}` }));
}

function seccionVeredicto(ctx, m, ayudas, sobre, id) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const v = m.veredicto;
  if (!v) {
    return ui.seccion('Veredicto de la oferta', ayudas.vacioConComandos('Todavía no hay veredicto.', {
      pista: 'El veredicto dice si la oferta es VALIDADA, PROMETEDORA, FALLIDA o INCONCLUSA. Se calcula solo con compras ya sin riesgo de reembolso: las que pasaron la garantía más un margen de seguridad.',
      archivo: `ofertas/${id}/08-operacion/veredicto_oferta.json`,
      comandos: [{ etiqueta: 'Calcula el veredicto (simulacro: no cambia nada)', cmd: comandosOperacion(id, null).veredicto }],
    }), { ayuda: 'Es lo que decide si se sigue, se escala o se cierra.' });
  }
  const e = v.evidencia;
  const d = (x) => (x ? fmt.dinero(x.monto, x.moneda) : null);
  const sinDato = (t) => el('span', { class: 'cifra-sin-dato' }, t);
  const filas = [
    ['Compras (brutas · reembolsadas · netas)', e.compras_brutas === null ? null : `${fmt.num(e.compras_brutas)} · ${fmt.num(e.reembolsos ?? 0)} · ${fmt.num(e.compras_netas ?? 0)}`],
    ['Gasto en anuncios', d(e.gasto)],
    ['Costo por venta neto', d(e.cpa_neto) || sinDato('sin dato: aún no hay compras netas')],
    ['Costo por venta objetivo', d(e.cpa_objetivo)],
    ['Ganancia real por pedido (antes de anuncios)', d(e.mc_real) || sinDato('sin dato')],
    ['Probabilidad de ser rentable', v.p === null ? sinDato('sin dato: pocas compras') : `${String(Math.round(v.p * 100)).replace('.', ',')} %`],
    ['Estabilidad', v.estabilidad ? `${v.estabilidad.estable ? 'estable' : 'inestable'} (±${v.estabilidad.tolerancia_pct} %)` : sinDato('sin dato')],
    ['Meta frente a Stripe', e.razon_ms === null ? sinDato('sin dato') : decimalEs(e.razon_ms, 2)],
  ].filter(([, val]) => val !== null);
  const mad = v.madurez;
  const reqs = v.requisitos.length
    ? el('div', { class: 'p5-pila' }, v.requisitos.map((r) => requisito(ctx, r)))
    : el('p', { class: 'p5-sub' }, 'Los parámetros del veredicto no están cargados: no se pueden mostrar los mínimos para validar.');
  const tecnico = ui.kv([
    ['Regla aplicada', el('span', { class: 'p5-regla' }, v.regla && v.regla.id ? v.regla.id : '—')],
    ['Definición', v.regla && v.regla.definicion],
    ['Versión de las reglas', v.regla && v.regla.version_reglas],
    ['Versión del veredicto', v.version],
    ['Fuente de las compras', e.fuente_compras],
    ['Compras según Meta (referencia)', e.compras_meta_referencia === null ? null : fmt.num(e.compras_meta_referencia)],
    ['Compras brutas / reembolsos / netas', e.compras_brutas === null ? null : `${fmt.num(e.compras_brutas)} / ${fmt.num(e.reembolsos ?? 0)} / ${fmt.num(e.compras_netas ?? 0)}`],
    ['Probabilidad de que el costo por venta esté bajo el punto de equilibrio', v.p === null ? null : decimalEs(v.p, 2)],
    ['Garantía · margen · madurez', mad.garantia === null ? null : `${mad.garantia} d · ${mad.margen ?? '—'} d · ${mad.madurezDias ?? '—'} d`],
    ['Emitido', v.ts ? `${fmt.fecha(v.ts, { segundos: true })}` : null],
  ]);
  return el('section', { class: `p5-vered p5-vered--${v.tono}`, 'aria-label': 'Veredicto de la oferta' },
    el('div', { class: 'p5-vered__cab' },
      el('div', { class: 'p5-vered__titulos' },
        el('span', { class: 'p5-vered__rotulo' }, 'Veredicto de la oferta', ui.ayuda('veredicto')),
        el('div', { class: 'p5-vered__estado' }, el('span', { class: 'p5-vered__icono' }, ui.icono(ICONO_VEREDICTO[v.estado] || 'info', { tam: 24 })), ui.termino(v.estado.toLowerCase(), { texto: v.estado }))),
      el('div', { class: 'p5-vered__chips' }, v.sintetico ? ui.chip('Datos de ejemplo', 'info', { icono: false }) : null, v.ts ? el('span', { class: 'p5-sub' }, 'Emitido ', ui.tiempo(v.ts)) : null)),
    el('p', { class: 'p5-vered__desc' }, v.descripcion),
    v.recomendacionTexto
      ? el('div', { class: 'p5-vered__reco' }, ui.icono('flecha-derecha', { tam: 16 }), el('strong', null, 'El sistema recomienda: '), el('span', null, v.recomendacionTexto), v.gate && CLAVE_GATE[v.gate] ? el('span', { class: 'p5-sub' }, ' · Lo aprueba: ', ui.termino(CLAVE_GATE[v.gate])) : null)
      : null,
    el('div', { class: 'p5-vered__rejilla' },
      el('div', { class: 'p5-vered__col' }, el('h3', { class: 'p5-titulo-chico' }, 'Qué falta para validar ', ui.ayuda('veredicto_madurez')), reqs),
      el('div', { class: 'p5-vered__col' }, el('h3', { class: 'p5-titulo-chico' }, 'Cuándo cuenta una compra ', ui.ayuda('madurez_cohorte')),
        lineaMadurez(ui, { garantia: mad.garantia, margen: mad.margen, total: mad.madurezDias, hasta: mad.cohorteMaduraHasta }),
        mad.diasConDatos === null ? null : el('p', { class: 'p5-sub' }, `${mad.diasConDatos} ${mad.diasConDatos === 1 ? 'día' : 'días'} con datos.`)),
      el('div', { class: 'p5-vered__col' }, el('h3', { class: 'p5-titulo-chico' }, 'La evidencia'),
        el('dl', { class: 'p5-datos' }, filas.map(([k, val]) => [el('dt', null, k), el('dd', null, val)])))),
    ui.detalleTecnico('Regla y datos técnicos del veredicto', tecnico));
}

// ───────────────────────── frescura ─────────────────────────

function franjaFrescura(ctx, m) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  if (!m.ultima) return null;
  const u = m.ultima;
  const items = u.fuentes.map((f) => {
    const tono = f.estado === 'verde' ? 'ok' : f.estado === 'amarillo' ? 'aviso' : f.estado === 'rojo' ? 'error' : 'neutro';
    const quien = { meta: 'Meta', stripe_eventos: 'Stripe (compras)', stripe_balance: 'Stripe (saldo)' }[f.nombre] || f.etiqueta;
    const cuando = f.horas !== null ? `hace ${textoDuracionH(f.horas)}` : 'sin lectura registrada';
    return el('span', { class: 'p5-fresc__fuente', title: f.causa || '' },
      ui.chip(`${quien} · ${cuando}`, tono, { icono: tono === 'neutro' ? 'circulo-punteado' : undefined }),
      f.causa && f.estado !== 'verde' ? el('span', { class: 'p5-causa' }, f.causa) : null);
  });
  return el('section', { class: 'p5-fresc', 'aria-label': 'Frescura de los datos' },
    el('span', { class: 'p5-fresc__titulo' }, ui.icono('reloj', { tam: 16 }), 'Frescura de los datos', ui.ayuda('frescura_datos')),
    items,
    el('span', { class: 'p5-sub' }, `Día de las cifras: ${fmt.fecha(u.fecha)}${u.generado_en ? ` · calculadas ${fmt.relativo(u.generado_en)}` : ''}`),
    u.tachadas ? ui.chip(`${u.tachadas} ${u.tachadas === 1 ? 'cifra tachada' : 'cifras tachadas'}: no decidas con ellas`, 'error') : null);
}

// ───────────────────────── gráficos ─────────────────────────

function seccionGraficos(ctx, m, ayudas, sobre, id) {
  const { ui, fmt } = ctx;
  if (!m.hayKpi) {
    return ui.seccion('Cómo evoluciona', ayudas.vacioConComandos('Esta oferta aún no tiene cifras diarias.', {
      pista: 'Cada día el sistema cierra el gasto, los clics, las compras reales y el costo por venta. Mientras no exista el primer cierre no se dibuja nada: nunca se pinta un cero.',
      archivo: `ofertas/${id}/08-operacion/diario/<fecha>/kpi_oferta_dia.json`,
      comandos: [{ etiqueta: 'Calcula las cifras de un día (simulacro: no cambia nada)', cmd: comandosOperacion(id, null).kpi }],
      fuente: sobre ? sobre.fuente : undefined,
    }));
  }
  const moneda = m.moneda;
  const dinero = (v) => fmt.dinero(Math.round(v), moneda);
  const eje = (v) => dinero(v).replace(',00', '');
  const eco = m.economia;
  const be = eco && eco.cpa_be && eco.cpa_be.moneda === moneda ? eco.cpa_be.monto : null;
  const obj = eco && eco.cpa_obj && eco.cpa_obj.moneda === moneda ? eco.cpa_obj.monto : null;
  const tope = m.topes && m.topes.diario !== null && (!m.topes.moneda || m.topes.moneda === moneda) ? m.topes.diario : null;
  return ui.seccion('Cómo evoluciona', ui.el('div', { class: 'p5-graficos' },
    graficoSerie(ui, {
      titulo: 'Costo por venta por día', subtitulo: 'Lo que cuesta en anuncios cada compra', serie: m.series.cpa, tipo: 'linea', formato: dinero, formatoEje: eje, columna: 'Costo por venta',
      banda: be !== null ? { desde: 0, hasta: be, etiqueta: 'Rentable: por debajo del punto de equilibrio' } : null,
      referencias: obj !== null ? [{ valor: obj, etiqueta: `objetivo ${dinero(obj)}` }] : [],
      vacio: 'Aún no hay compras: sin costo por venta no se dibuja nada.',
    }),
    graficoSerie(ui, { titulo: 'Gasto por día', subtitulo: tope !== null ? 'Frente al tope diario' : 'Sin tope diario fijado', serie: m.series.gasto, tipo: 'barras', formato: dinero, formatoEje: eje, columna: 'Gasto', referencias: tope !== null ? [{ valor: tope, etiqueta: `tope ${dinero(tope)}` }] : [] }),
    graficoSerie(ui, { titulo: 'Compras por día', subtitulo: 'Compras reales de Stripe', serie: m.series.compras, tipo: 'barras', formato: (v) => fmt.num(v), formatoEje: (v) => fmt.num(v), columna: 'Compras' })),
  { ayuda: 'Un punto por día. Pasa el cursor (o usa las flechas) para ver el valor; «Ver tabla» muestra los mismos datos. Un marcador hueco con borde rojo es una cifra tachada: su fuente de datos no era fiable.' });
}

// ───────────────────────── decisiones del sistema ─────────────────────────

const ORDEN_FAMILIAS = ['todas', 'G', 'K', 'M', 'E'];

function tecnicoDecision(ctx, d) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const ev = d.evidencia;
  return ui.kv([
    ['Regla', d.regla ? el('span', { class: 'p5-regla' }, d.regla) : null],
    ['Familia', d.familia ? ui.termino(`regla_${d.familia.toLowerCase()}`, { texto: FAMILIAS[d.familia].titulo }) : null],
    ['Código', d.codigo ? el('span', { class: 'p5-mono' }, d.codigo) : null],
    ['Objeto', d.objeto_id ? el('span', null, `${d.objeto_tipo || ''} `, el('span', { class: 'p5-mono' }, d.objeto_id)) : null],
    ['Evidencia', [ev.gasto ? `gasto ${fmt.dinero(ev.gasto.monto, ev.gasto.moneda)}` : null, ev.clics !== null ? `${fmt.num(ev.clics)} clics` : null, ev.compras !== null ? `${fmt.num(ev.compras)} compras` : null, ev.p !== null ? `probabilidad de estar bajo el punto de equilibrio = ${decimalEs(ev.p, 2)}` : null].filter(Boolean).join(' · ') || null],
    ['Punto de control', d.gate || d.nivel ? textoControl(d.gate, d.nivel) : null],
    ['Lectura de datos', d.lectura_ts ? fmt.fecha(d.lectura_ts, { segundos: true }) : null],
    ['Explicación del sistema', d.explicacion || null],
    ['Versión de las reglas', d.version_reglas],
    ['Huella de los parámetros usados', d.hash_parametros ? el('span', { class: 'p5-mono' }, d.hash_parametros) : null],
    ['Identificador', d.id ? el('span', { class: 'p5-mono' }, d.id) : null],
  ]);
}

function tablaDecisiones(ctx, m) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const columnas = [
    { clave: 'ts', titulo: 'Cuándo', formato: (v) => (v ? fmt.fecha(v) : '—') },
    { clave: 'regla', titulo: 'Regla', formato: (v, f) => el('span', { class: 'p5-regla', title: f.familia ? FAMILIAS[f.familia].titulo : '' }, v || '—') },
    { clave: 'familia', titulo: 'Familia', formato: (v) => (v ? FAMILIAS[v].corto : '—') },
    { clave: 'accion', titulo: 'Acción', formato: (v, f) => ui.chip(v, f.conocida ? (describirDecision(f, {}).tono) : 'neutro', { icono: false }) },
    { clave: 'codigo', titulo: 'Código', clase: 'cel-larga', formato: (v) => (v ? el('span', { class: 'p5-mono' }, v) : '—') },
    { clave: 'objeto_id', titulo: 'Objeto', clase: 'cel-larga', formato: (v, f) => (v ? el('span', null, `${f.objeto_tipo || ''} `, el('span', { class: 'p5-mono' }, v)) : '—') },
    { titulo: 'Evidencia', ordenable: false, ancho: '190px', clase: 'cel-larga', formato: (v, f) => {
      const e = f.evidencia;
      const p = [];
      if (e.gasto) p.push(`gasto ${fmt.dinero(e.gasto.monto, e.gasto.moneda)}`);
      if (e.clics !== null) p.push(`${fmt.num(e.clics)} clics`);
      if (e.compras !== null) p.push(`${fmt.num(e.compras)} compras`);
      if (e.p !== null) p.push(`prob. bajo el equilibrio = ${decimalEs(e.p, 2)}`);
      return p.length ? p.join(' · ') : el('span', { class: 'cifra-sin-dato' }, 'sin evidencia');
    } },
    { clave: 'ejecucion.texto', titulo: 'Ejecución', formato: (v, f) => ui.chip(f.ejecucion.texto, f.ejecucion.tono) },
    { clave: 'explicacion', titulo: 'Por qué', ancho: '340px', clase: 'cel-larga', formato: (v) => (v ? el('span', { title: v }, v) : '—') },
  ];
  return ui.tabla({ etiqueta: 'Decisiones del sistema', columnas, filas: m.decisiones, filtro: { placeholder: 'Filtrar por regla, código, objeto…' }, vacio: 'Sin decisiones.' });
}

function seccionDecisiones(ctx, m, ayudas, sobre, id) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const r = m.resumenDecisiones;
  if (!m.decisiones.length) {
    return ui.seccion('Qué ha decidido el sistema', ayudas.vacioConComandos('El sistema todavía no ha registrado decisiones para esta oferta.', {
      pista: 'Cada lectura diaria del sistema de optimización (etapa Operación) deja una línea: qué hizo con cada campaña o anuncio, por qué y si se aplicó. Antes de activar la campaña no hay nada que decidir.',
      archivo: `ofertas/${id}/${ARCHIVO_DECISIONES}`,
      comandos: [{ etiqueta: 'Evalúa las reglas del sistema (simulacro: no cambia nada)', cmd: comandosOperacion(id, null).decisiones }],
      fuente: sobre ? sobre.fuente : undefined,
    }), { ayuda: 'Primero los frenos de seguridad; después mantener, pausar un anuncio o escalar (subir el presupuesto).' });
  }
  const cpaBe = m.economia && m.economia.cpa_be ? m.economia.cpa_be : null;
  const formatoDinero = (x, c) => fmt.dinero(x, c);
  const lista = el('ul', { class: 'p5-feed' });
  const pintar = () => {
    const vistas = m.decisiones.filter((d) => UI.familia === 'todas' || d.familia === UI.familia);
    ui.reemplazar(lista, vistas.length ? vistas.map((d) => {
      const h = describirDecision(d, { cpaBe, formatoDinero });
      return el('li', { class: `p5-feed__item p5-feed__item--${h.tono}` },
        el('span', { class: 'p5-feed__icono' }, ui.icono(h.icono, { tam: 18 })),
        el('div', { class: 'p5-feed__cuerpo' },
          el('p', { class: 'p5-feed__frase' }, h.frase),
          el('div', { class: 'p5-feed__meta' }, d.ts ? ui.tiempo(d.ts) : null, ui.chip(h.accionHumana, h.tono), ui.chip(d.ejecucion.texto, d.ejecucion.tono, { icono: false }), h.pidePermiso ? ui.chip('Espera tu firma', 'acento') : null),
          ui.detalleTecnico('Regla y evidencia', () => tecnicoDecision(ctx, d))));
    }) : el('li', { class: 'p5-sub' }, 'Ninguna decisión de esta familia.'));
  };
  const opciones = ORDEN_FAMILIAS.map((f) => ({ valor: f, etiqueta: f === 'todas' ? `Todas (${r.total})` : `${FAMILIAS[f].corto} (${r.porFamilia[f]})` }));
  const filtro = ui.segmentado({ opciones, valor: UI.familia, etiqueta: 'Filtrar decisiones por tipo', onCambio: (v) => { UI.familia = v; pintar(); } });
  pintar();
  return ui.seccion('Qué ha decidido el sistema', el('div', { class: 'p5-pila' },
    el('div', { class: 'p5-resumen-familias' }, filtro, ui.chip(`${r.ejecutadas} ejecutadas y verificadas`, r.ejecutadas ? 'ok' : 'neutro', { icono: r.ejecutadas ? undefined : false }), ui.chip(`${r.sinEjecutar} sin ejecutar`, 'neutro', { icono: false })),
    lista,
    ui.detalleTecnico('Tabla completa de decisiones (todas las columnas)', () => tablaDecisiones(ctx, m))),
  { ayuda: `Cada línea es una lectura del sistema (en los archivos se llama «${NOMBRE_DECISION}»). «Ejecutada» significa que la acción se aplicó en Meta y se comprobó; el resto son propuestas o no requieren acción. La regla exacta está en el detalle técnico.` });
}

// ───────────────────────── órdenes de presupuesto ─────────────────────────

const ICONO_ORDEN = { aumentar: 'tendencia-sube', reducir: 'tendencia-baja', mantener: 'tendencia-igual' };

function seccionOrdenes(ctx, m, ayudas, sobre, id) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  if (!m.ordenes.length) {
    return ui.seccion('Órdenes de presupuesto', ayudas.vacioConComandos('No hay órdenes de presupuesto.', {
      pista: 'Una orden es la ÚNICA forma de cambiar un presupuesto: el sistema propone (mantener, subir o bajar), se aprueba y un programa la aplica y comprueba en Meta que quedó bien.',
      archivo: `ofertas/${id}/08-operacion/ordenes_presupuesto.jsonl`,
      comandos: [{ etiqueta: 'El sistema las emite al evaluar las reglas (simulacro)', cmd: comandosOperacion(id, null).ordenes }],
    }), { ayuda: 'Solo lectura.' });
  }
  const dinero = (x, c) => fmt.dinero(x, c);
  const lista = el('ul', { class: 'p5-feed' }, m.ordenes.map((o) => {
    const h = describirOrden(o, dinero);
    return el('li', { class: `p5-feed__item p5-feed__item--${h.estadoTono}` },
      el('span', { class: 'p5-feed__icono' }, ui.icono(ICONO_ORDEN[o.accion] || 'info', { tam: 18 })),
      el('div', { class: 'p5-feed__cuerpo' },
        el('p', { class: 'p5-feed__frase' }, h.frase),
        el('div', { class: 'p5-feed__meta' }, o.ts ? ui.tiempo(o.ts) : null, ui.chip(h.estadoTexto, h.estadoTono), o.verificada === true ? ui.chip('Comprobada en Meta', 'ok') : null),
        ui.detalleTecnico('Detalle de la orden', () => ui.kv([
          ['Orden', el('span', { class: 'p5-mono' }, o.orden_id)],
          ['Regla', o.regla_id ? el('span', { class: 'p5-regla' }, o.regla_id) : null],
          ['Punto de control', o.gate ? `${textoControl(o.gate.gate, o.gate.nivel)}${o.gate.accion_gate ? ` · ${o.gate.accion_gate}` : ''}` : null],
          ['Ejecutor', o.ejecutor],
          ['Aprobó', o.aprobado_por ? `${o.aprobado_por.tipo || ''} ${o.aprobado_por.id || ''}`.trim() : null],
          ['Emisor', o.emisor],
          ['Nota del sistema', o.nota || null],
          ['Horas desde el último aumento', o.horas_desde_ultimo_aumento === null ? null : fmt.num(o.horas_desde_ultimo_aumento, 1)],
          ['Versión de las reglas', o.version_reglas],
          ['Huella de los parámetros usados', o.hash_parametros ? el('span', { class: 'p5-mono' }, o.hash_parametros) : null],
          ['Clave contra órdenes repetidas', o.idempotency_key ? el('span', { class: 'p5-mono' }, o.idempotency_key) : null],
        ]))));
  }));
  const d = (x) => (x ? fmt.dinero(x.monto, x.moneda) : '—');
  const columnas = [
    { clave: 'ts', titulo: 'Cuándo', formato: (v) => (v ? fmt.fecha(v) : '—') },
    { clave: 'orden_id', titulo: 'Orden', clase: 'cel-larga', formato: (v) => el('span', { class: 'p5-mono' }, v) },
    { clave: 'accion', titulo: 'Acción', formato: (v) => ui.chip(v || '—', v === 'aumentar' ? 'info' : v === 'reducir' ? 'aviso' : 'neutro', { icono: false }) },
    { clave: 'objeto.nombre', titulo: 'Objeto', ancho: '230px', clase: 'cel-larga', formato: (v, f) => (f.objeto ? `${f.objeto.tipo || ''} ${f.objeto.nombre || ''}` : '—') },
    { titulo: 'Presupuesto', ordenable: false, clase: 'cel-larga', formato: (v, f) => `${d(f.antes)} → ${d(f.despues)}` },
    { clave: 'delta_pct', titulo: 'Δ %', alinear: 'der', formato: (v) => (v === null ? '—' : `${decimalEs(v, v % 1 ? 1 : 0)} %`) },
    { clave: 'regla_id', titulo: 'Regla', formato: (v) => el('span', { class: 'p5-regla' }, v || '—') },
    { clave: 'estado', titulo: 'Estado', formato: (v, f) => ui.chip(v || '—', f.tono) },
    { titulo: 'Punto de control', ordenable: false, clase: 'cel-larga', formato: (v, f) => (f.gate ? textoControl(f.gate.gate, f.gate.nivel) : '—') },
    { clave: 'ejecutor', titulo: 'Ejecutor', clase: 'cel-larga', formato: (v, f) => `${v || '—'}${f.aprobado_por ? ` · aprobó ${f.aprobado_por.id || f.aprobado_por.tipo}` : ''}` },
    { clave: 'nota', titulo: 'Nota', ancho: '260px', clase: 'cel-larga', formato: (v) => v || '—' },
  ];
  return ui.seccion('Órdenes de presupuesto', el('div', { class: 'p5-pila' }, lista,
    ui.detalleTecnico('Tabla completa de órdenes (todas las columnas)', () => ui.tabla({ etiqueta: 'Órdenes de presupuesto', columnas, filas: m.ordenes, vacio: 'Sin órdenes.' }))),
  { ayuda: 'Solo lectura: las órdenes se aprueban y ejecutan con el sistema automático, no desde el panel.' });
}

// ───────────────────────── datos por día ─────────────────────────

/** [[fecha, [causas únicas]]] de los días con cifras tachadas (la causa completa se dice una vez; en la celda va la corta). */
function causasPorDia(m) {
  return m.filas.filter((f) => f.tachadas).map((f) => [f.fecha, [...new Set(Object.values(f.cifras).filter((c) => c.estado === 'tachada').map((c) => c.causa))]]);
}

function seccionKpi(ctx, m, ayudas) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  if (!m.hayKpi) return null;
  const celda = (id2, extra) => (v, f) => ayudas.cifraEl(f.cifras[id2], extra || formatoDeUnidad(f.cifras[id2].unidad, fmt), { corta: true });
  const columnas = [
    { clave: 'fecha', titulo: 'Día', formato: (v, f) => el('span', null, fmt.fecha(v), f.sintetico ? [' ', ui.chip('ejemplo', 'info', { icono: false })] : null) },
    { clave: 'cifras.gasto_meta.valor', titulo: 'Gasto', alinear: 'der', clase: 'p5-cifra', formato: celda('gasto_meta') },
    { clave: 'cifras.impresiones.valor', titulo: 'Impresiones', alinear: 'der', clase: 'p5-cifra', formato: celda('impresiones', (v) => fmt.num(v)) },
    { clave: 'cifras.clics_enlace.valor', titulo: 'Clics', alinear: 'der', clase: 'p5-cifra', formato: celda('clics_enlace', (v) => fmt.num(v)) },
    { clave: 'cifras.ctr_enlace.valor', titulo: '% que hace clic', alinear: 'der', clase: 'p5-cifra', orden: (f) => aNumero(f.cifras.ctr_enlace.valor), formato: celda('ctr_enlace') },
    { clave: 'cifras.compras_stripe.valor', titulo: 'Compras', alinear: 'der', clase: 'p5-cifra', formato: celda('compras_stripe', (v) => fmt.num(v)) },
    { clave: 'cifras.cpa.valor', titulo: 'Costo por venta', alinear: 'der', clase: 'p5-cifra', formato: celda('cpa') },
    { clave: 'cifras.razon_meta_stripe.valor', titulo: 'Compras Meta / Stripe', alinear: 'der', clase: 'p5-cifra', orden: (f) => aNumero(f.cifras.razon_meta_stripe.valor), formato: celda('razon_meta_stripe') },
    { titulo: 'Antigüedad de los datos', ordenable: false, ancho: '270px', formato: (v, f) => el('span', { class: 'p5-fila p5-fila--sin-corte p5-fila--junta' }, f.fuentes.map((x) => ui.chip(`${x.nombre === 'meta' ? 'Meta' : x.nombre === 'stripe_eventos' ? 'Stripe compras' : 'Stripe saldo'} ${x.horas !== null ? textoDuracionH(x.horas) : '—'}`, x.estado === 'verde' ? 'ok' : x.estado === 'amarillo' ? 'aviso' : x.estado === 'rojo' ? 'error' : 'neutro', { icono: false }))) },
  ];
  const filas = [...m.filas].reverse();
  return ui.seccion('Datos por día', el('div', { class: 'p5-pila' },
    ui.tabla({ etiqueta: 'Cifras diarias', columnas, filas, vacio: 'Sin días.', ordenInicial: { clave: 'fecha', dir: 'desc' } }),
    ...causasPorDia(m).map(([fecha, causas]) => ayudas.aviso('error', el('strong', null, `Cifras tachadas del ${fmt.fecha(fecha)}: `), causas.join('; '))),
    m.acumulado.excluidos.length ? ayudas.aviso('aviso', `El acumulado excluye ${m.acumulado.excluidos.length} cifra(s) tachadas o sin dato: ${m.acumulado.excluidos.slice(0, 4).map((x) => `${fmt.fecha(x.fecha)} ${NOMBRE_KPI[x.kpi_id] || x.kpi_id}`).join(', ')}.`) : null),
  { ayuda: 'Un día por fila. Tachado = la fuente de esa cifra no era fiable; «sin dato» = no existe (no es un cero); «pocos datos» = muestra demasiado chica para concluir.' });
}

// ───────────────────────── página ─────────────────────────

export async function render(ctx) {
  const { api, ui, fmt, estado } = ctx;
  const { el } = ui;
  instalarEstilos(ui);
  const id = estado.ofertaActiva;
  if (!id) return pantallaElegir(ctx);

  const ayudas = ayudasVista(ui, fmt);
  const [op, eco, par, fin] = await Promise.allSettled([
    api.sobre(`/operacion/${enc(id)}`),
    leerOpcional(api, `/oferta/${enc(id)}/archivo`, { ruta: '03-oferta/economia.json' }),
    leerOpcional(api, '/parametros'),
    leerOpcional(api, '/finanzas'),
  ]);
  const ofertaResumen = (estado.ofertas || []).find((o) => o && o.oferta_id === id);
  const nombre = ofertaResumen && ofertaResumen.demo ? 'la oferta de ejemplo' : id;
  const cab = ui.encabezadoPagina({
    titulo: 'Resultados',
    descripcion: `Cómo se comporta ${nombre} en vivo: lo que gasta, lo que vende y lo que decide el sistema.`,
    acciones: [botonActualizar(ctx)],
  });
  if (op.status === 'rejected') {
    return el('div', { class: 'pagina' }, cab, ui.errorBox(op.reason, { reintentar: () => ctx.recargar() }));
  }
  const sobre = op.value;
  const parSobre = par.status === 'fulfilled' ? par.value : null;
  const finSobre = fin.status === 'fulfilled' ? fin.value : null;
  const m = modeloOperacion({
    operacion: sobre.datos,
    economia: economiaDeSobre(eco.status === 'fulfilled' ? eco.value : null),
    limites: parSobre && parSobre.datos ? parSobre.datos.limites : null,
    parametros: parSobre && parSobre.datos ? parSobre.datos.parametros : null,
    conciliacion: finSobre && finSobre.datos ? finSobre.datos.conciliacion : null,
  }, { ahora: new Date() });

  const avisos = [];
  if (!parSobre || !parSobre.datos || !parSobre.datos.limites) avisos.push('No se pudieron leer los topes de gasto: no se compara el gasto con ningún tope.');
  if (!m.economia) avisos.push('No se pudo leer la economía de la oferta: sin punto de equilibrio ni costo por venta objetivo con los que comparar.');
  const atencion = atencionOperacion(m, { ofertaId: id, formatoDinero: (x, c) => fmt.dinero(x, c) });

  return el('div', { class: 'pagina' }, cab,
    el('div', { class: 'p5-fila p5-fila--junta' },
      ui.chip(id, 'neutro', { icono: false }), ofertaResumen && ofertaResumen.demo ? ui.chip('Oferta de ejemplo', 'info', { icono: false }) : null, m.sintetico && !(ofertaResumen && ofertaResumen.demo) ? ui.chip('Datos de ejemplo', 'info', { icono: false }) : null,
      ofertaResumen && ofertaResumen.fase ? ui.estadoIcono(ofertaResumen.fase) : null,
      ofertaResumen && ofertaResumen.nivel ? el('span', { class: 'p5-sub' }, ui.termino(`nivel_${String(ofertaResumen.nivel).toLowerCase()}`, { texto: rotuloNivel(ofertaResumen.nivel) })) : null,
      ofertaResumen && ofertaResumen.pausa ? ui.chip('En pausa', 'aviso') : null),
    ...avisos.map((a) => ayudas.aviso('aviso', a)),
    ui.atencion({ items: atencion, vacio: 'Todo en orden: ninguna cifra, tope o decisión espera tu atención.' }),
    el('div', { class: 'p5-metricas' }, metricaGastoHoy(ctx, m, ayudas), metricaCompras(ctx, m), metricaCpa(ctx, m), metricaReembolsos(ctx, m, ayudas), metricaCobertura(ctx, m, ayudas)),
    seccionVeredicto(ctx, m, ayudas, sobre, id),
    franjaFrescura(ctx, m),
    seccionGraficos(ctx, m, ayudas, sobre, id),
    seccionDecisiones(ctx, m, ayudas, sobre, id),
    seccionOrdenes(ctx, m, ayudas, sobre, id),
    seccionKpi(ctx, m, ayudas),
    ui.fuenteInfo(sobre));
}

/** Actualización en vivo: re-renderiza (con la oferta activa) salvo que la persona esté escribiendo en un filtro. */
export async function alCambio(ctx) {
  if (hayEdicion()) return undefined;
  return render(ctx);
}
