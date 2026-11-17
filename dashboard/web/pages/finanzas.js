// pages/finanzas.js — #/finanzas: qué entra, qué sale y si las cuentas cuadran (CONTRATO §4 `GET /finanzas`; rediseño U4).
// Orden de lectura: qué requiere atención → métricas (resultado, ingresos, anuncios, IA, conciliación) → conciliación Stripe ↔ libro ↔ Meta con su
// semáforo y su causa → P&L por oferta y consolidado con barras de margen → libro mayor con filtros → costos de IA → alertas.
// Fuentes: empresa/finanzas/{ledger.jsonl, pnl.json, conciliacion.json} y alertas. Solo lectura. Criterio B0-17: conciliación ≠ 0 ⇒ cifra TACHADA con
// su causa; sin dato ⇒ «sin dato», nunca 0. Todo texto de datos va por ui.el (textContent).

import { ayudasVista, instalarEstilos } from '../lib/operacion.js';
import { barraMargen } from '../lib/graficos.js';
import {
  modeloFinanzas, filtrarLedger, totalesLedger, causasDeCelda, LINEAS_PNL, TIPOS_LEDGER, FUENTES_LEDGER, comandosFinanzas,
  NOMBRE_TIPO_LEDGER, NOMBRE_FUENTE_LEDGER, ESTADO_CONCILIACION, margenBp, sumaLineas, atencionFinanzas,
} from '../lib/finanzas.js';

export const meta = { ruta: 'finanzas', titulo: 'Finanzas', grupo: 'Dinero y reglas', icono: 'dinero', escucha: ['empresa'] };

// Estado de la interfaz que sobrevive a una actualización en vivo (filtros del libro mayor).
const FILTROS = { oferta: '', tipo: '', fuente: '', pruebas: false, tecnico: null };

function hayEdicion() {
  const d = globalThis.document;
  const a = d && d.activeElement;
  return Boolean(a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) || Boolean(d && d.querySelector('.modal-fondo'));
}

async function leerOpcional(api, ruta) { try { return await api.sobre(ruta); } catch (_) { return null; } }

const botonActualizar = (ctx) => ctx.ui.el('button', { type: 'button', class: 'btn btn--chico', onclick: () => ctx.recargar() }, ctx.ui.icono('refrescar', { tam: 14 }), 'Actualizar');
const nombreBloque = (id) => (id === 'consolidado' ? 'Todas las ofertas' : id);

// ───────────────────────── métricas ─────────────────────────

function metricas(ctx, m, ayudas) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const pnl = m.pnl;
  const cons = pnl && pnl.bloques.find((b) => b.id === 'consolidado');
  const dato = (clave) => (clave === 'resultado_operativo' ? (cons && cons.resultado) : (cons && cons.lineas[clave]));
  const celda = (clave) => {
    const d = cons ? dato(clave) : null;
    if (!d) return null;
    const causas = causasDeCelda(pnl, cons, clave);
    const txt = fmt.dinero(d.monto, d.moneda);
    return causas.length ? ayudas.cifraTachada(txt, causas[0]) : txt;
  };
  const causasRes = cons ? causasDeCelda(pnl, cons, 'resultado_operativo') : [];
  const bp = cons ? margenBp(cons.resultado, cons.lineas.ingresos_brutos) : null;
  const costo = m.costosIa.find((c) => c.id === 'consolidado');
  const conc = m.conciliacion;
  const infoConc = conc ? (ESTADO_CONCILIACION[conc.estado] || { texto: conc.estado, tono: conc.tono }) : null;
  const periodo = pnl && pnl.periodo ? `${fmt.fecha(pnl.periodo.desde)} a ${fmt.fecha(pnl.periodo.hasta)}` : null;
  return el('div', { class: 'p5-metricas' },
    ui.metrica({
      etiqueta: 'Resultado operativo', valor: celda('resultado_operativo'), ayuda: 'resultado_operativo',
      tono: causasRes.length ? 'critico' : (cons && cons.resultado && cons.resultado.monto < 0 ? 'aviso' : null),
      contexto: el('div', { class: 'p5-ctx' },
        bp !== null && !causasRes.length ? el('span', { class: 'p5-sub' }, el('strong', null, fmt.pct(bp)), ' de margen sobre los ingresos', ui.ayuda('margen_operativo')) : null,
        periodo ? el('span', { class: 'p5-sub' }, `Periodo: ${periodo}`) : (pnl ? null : el('span', { class: 'p5-causa' }, 'Todavía no hay cuenta de resultados')),
        cons && cons.madurez ? ui.chip(cons.madurez === 'maduro' ? 'Compras maduras' : 'Compras aún madurando', cons.madurez === 'maduro' ? 'ok' : 'info') : null),
    }),
    ui.metrica({ etiqueta: 'Ingresos brutos', valor: celda('ingresos_brutos'), contexto: el('span', { class: 'p5-sub' }, 'Lo cobrado en Stripe, impuestos incluidos') }),
    ui.metrica({ etiqueta: 'Gasto en anuncios', valor: celda('gasto_meta'), contexto: el('span', { class: 'p5-sub' }, 'Meta, comparado con el libro de movimientos') }),
    ui.metrica({
      etiqueta: 'Costo de IA', valor: celda('costo_ia'), ayuda: 'costo_ia', tono: costo && costo.estado === 'rojo' ? 'aviso' : null,
      contexto: costo
        ? el('div', { class: 'p5-ctx' }, costo.pctBp === null ? el('span', { class: 'p5-sub' }, 'Sin ingresos: no hay porcentaje') : ayudas.medidor({ bp: costo.topePct !== null ? Math.round((costo.pctBp / (costo.topePct * 100)) * 10000) : Math.min(10000, costo.pctBp), zona: costo.estado === 'rojo' ? 'rojo' : 'ok', texto: `${fmt.pct(costo.pctBp)} de los ingresos${costo.topePct !== null ? ` · máx. ${costo.topePct} %` : ''}`, etiqueta: 'Costo de IA frente al máximo' }))
        : el('span', { class: 'p5-sub' }, 'Sin costo de IA en la cuenta de resultados'),
    }),
    ui.metrica({
      etiqueta: 'Conciliación', valor: infoConc ? infoConc.texto : null, ayuda: 'conciliacion', tono: infoConc ? infoConc.tono : 'aviso',
      contexto: el('span', { class: 'p5-sub' }, conc ? (conc.cifrasTachadas ? 'Hay cifras tachadas hasta explicar la diferencia' : 'Stripe y Meta coinciden con el libro de movimientos') : 'Sin conciliación: las cifras no están verificadas'),
    }));
}

// ───────────────────────── conciliación ─────────────────────────

function enlaceConciliacion(ctx, k, ayudas) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const dif = k.diferencia ? fmt.dinero(k.diferencia.monto, k.diferencia.moneda) : null;
  const chip = k.cuadra === true ? ui.chip('Cuadra', 'ok') : k.cuadra === false ? ui.chip('No cuadra', 'error') : ui.chip('Sin dato', 'neutro', { icono: 'circulo-punteado' });
  return el('div', { class: 'p5-conc__enlace' }, chip,
    dif === null ? el('span', { class: 'p5-conc__diff cifra-sin-dato' }, 'sin diferencia calculada') : el('span', { class: 'p5-conc__diff' }, k.cuadra === false ? ['Diferencia ', ayudas.cifraTachada(dif, null)] : `Diferencia ${dif}`));
}

function nodoConc(ui, nombre, lineas, extra) {
  const { el } = ui;
  return el('div', { class: ['p5-conc__nodo', extra && `p5-conc__nodo--${extra}`] }, el('span', { class: 'p5-conc__nombre' }, nombre), lineas);
}

function seccionConciliacion(ctx, m, ayudas, sobre) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const c = m.conciliacion;
  if (!c) {
    return ui.seccion('¿Cuadran las cuentas?', ayudas.vacioConComandos('Todavía no hay conciliación.', {
      pista: 'La conciliación compara lo cobrado en Stripe y lo gastado en Meta con el libro de movimientos. Sin ella ninguna cifra de la cuenta de resultados está verificada; si hay una diferencia, esas cifras se tachan.',
      archivo: 'empresa/finanzas/conciliacion.json',
      comandos: [{ etiqueta: 'Concilia una oferta y un periodo (simulacro: no cambia nada)', cmd: comandosFinanzas().ledger }],
    }), { glosario: 'conciliacion' });
  }
  const d = (x) => (x ? fmt.dinero(x.monto, x.moneda) : el('span', { class: 'cifra-sin-dato' }, 'sin dato'));
  const info = ESTADO_CONCILIACION[c.estado] || { texto: c.estado, tono: c.tono, frase: '' };
  const causas = [c.stripe.causa && c.stripe.cuadra === false ? c.stripe.causa : null, c.meta.causa && c.meta.cuadra === false ? c.meta.causa : null, c.tachadas.todo].filter(Boolean);
  const importe = (x, etiqueta) => el('span', { class: 'p5-conc__importe' }, d(x), etiqueta ? el('span', { class: 'p5-sub' }, ` ${etiqueta}`) : null);
  const esquema = el('div', { class: 'p5-conc', role: 'group', 'aria-label': 'Comparación entre Stripe, el libro de movimientos y Meta' },
    nodoConc(ui, 'Stripe · cobrado', importe(c.stripe.izquierda)),
    enlaceConciliacion(ctx, c.stripe, ayudas),
    nodoConc(ui, 'Libro de movimientos', el('div', { class: 'p5-pila p5-pila--chica' }, importe(c.stripe.derecha, 'ingresos'), importe(c.meta.derecha, 'gastos')), 'libro'),
    enlaceConciliacion(ctx, c.meta, ayudas),
    nodoConc(ui, 'Meta · gastado', importe(c.meta.izquierda)));
  const tecnico = ui.kv([
    ['Periodo', c.periodo ? `${c.periodo.desde} a ${c.periodo.hasta}` : null],
    ['Compras Meta / Stripe', c.compras ? `${c.compras.meta ?? '—'} / ${c.compras.stripe ?? '—'}${c.compras.razon !== null ? ` · Meta cuenta ${c.compras.razon.toFixed(2).replace('.', ',')} veces las de Stripe` : ' · sin dato de la comparación'}` : null],
    ['Compras ligadas a un anuncio', c.coberturaBp === null ? el('span', { class: 'cifra-sin-dato' }, 'sin dato') : fmt.pct(c.coberturaBp)],
    ['Excluidos', c.excluidos ? `${c.excluidos.pruebas} pruebas · ${c.excluidos.internas} internas` : null],
    ['Cobros que todavía no llegaron', c.pendientesAsincronos === null ? null : String(c.pendientesAsincronos)],
    ['Estado interno', c.estado],
    ['Generada', c.generado_en ? fmt.fecha(c.generado_en, { segundos: true }) : null],
  ]);
  return ui.seccion('¿Cuadran las cuentas?', el('div', { class: 'p5-pila' },
    el('div', { class: 'p5-fila p5-fila--junta' }, ui.chip(info.texto, info.tono), el('span', { class: 'p5-sub' }, info.frase), c.periodo ? el('span', { class: 'p5-sub' }, `Periodo: ${fmt.fecha(c.periodo.desde)} a ${fmt.fecha(c.periodo.hasta)}`) : null, c.generado_en ? el('span', { class: 'p5-sub' }, 'Calculada ', ui.tiempo(c.generado_en)) : null),
    esquema,
    causas.length ? el('div', { class: 'p5-conc__causas' }, causas.map((x) => ayudas.aviso('error', el('strong', null, 'Por qué no cuadra: '), x))) : null,
    ui.detalleTecnico('Datos de la conciliación', tecnico)),
  { glosario: 'conciliacion', ayuda: 'Si hay una diferencia, las cifras que dependen de esa comparación se tachan en la cuenta de resultados, con su causa. Nunca se muestra un 0 ni un dato viejo sin marca.' });
}

// ───────────────────────── P&L ─────────────────────────

const GRUPOS_PNL = [
  { id: 'ingresos', titulo: 'Ingresos brutos', claves: ['ingresos_brutos'] },
  { id: 'impuestos', titulo: 'Impuestos', claves: ['impuestos'] },
  { id: 'reembolsos', titulo: 'Reembolsos', claves: ['reembolsos'] },
  { id: 'comisiones', titulo: 'Comisiones y disputas', claves: ['comisiones', 'tarifas_disputa', 'disputas_perdidas'] },
  { id: 'meta', titulo: 'Anuncios', claves: ['gasto_meta'] },
  { id: 'costos', titulo: 'IA y otros', claves: ['costo_ia', 'otros_costos'] },
];

function seccionPnl(ctx, m, ayudas) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const p = m.pnl;
  if (!p) {
    return ui.seccion('Resultado por oferta', ayudas.vacioConComandos('Todavía no hay cuenta de resultados.', {
      pista: 'Resultado operativo = ingresos brutos − impuestos − reembolsos − comisiones − disputas − anuncios − IA − otros costos. Sin el cálculo no se muestra ninguna cifra, ni ceros.',
      archivo: 'empresa/finanzas/pnl.json',
      comandos: [{ etiqueta: 'Calcula el libro de movimientos y la conciliación', cmd: comandosFinanzas().ledger }, { etiqueta: 'Carga cobros de prueba de Stripe', cmd: comandosFinanzas().etl }],
    }), { glosario: 'pnl' });
  }
  const bloques = p.bloques;
  const causasGrupo = (b, claves) => [...new Set(claves.flatMap((k) => causasDeCelda(p, b, k)))];
  const celdaGrupo = (b, g) => {
    const suma = sumaLineas(b, g.claves);
    if (!suma) return el('span', { class: 'cifra-sin-dato' }, 'sin dato');
    const t = fmt.dinero(suma.monto, suma.moneda);
    const causas = causasGrupo(b, g.claves);
    return causas.length ? ayudas.cifraTachada(t, 'tachada', causas.join('; ')) : el('span', { class: 'p5-num' }, t);
  };
  const filas = [...bloques].sort((a, b) => (a.id === 'consolidado' ? -1 : b.id === 'consolidado' ? 1 : a.id.localeCompare(b.id)));
  const resultado = (b) => {
    if (!b.resultado) return el('span', { class: 'cifra-sin-dato' }, 'sin dato');
    const t = fmt.dinero(b.resultado.monto, b.resultado.moneda);
    const causas = causasDeCelda(p, b, 'resultado_operativo');
    return el('strong', { class: 'p5-num' }, causas.length ? ayudas.cifraTachada(t, 'tachada', causas.join('; ')) : t);
  };
  const columnas = [
    { clave: 'id', titulo: 'Oferta', ordenable: false, formato: (v, b) => el('div', { class: 'p5-pila p5-pila--chica' }, el('strong', null, nombreBloque(v)), b.madurez ? el('span', { class: 'p5-sub' }, b.madurez === 'maduro' ? 'Compras maduras' : 'Compras aún madurando') : null) },
    ...GRUPOS_PNL.map((g) => ({ clave: g.id, titulo: g.titulo, alinear: 'der', ordenable: false, clase: 'p5-cifra', formato: (v, b) => celdaGrupo(b, g) })),
    { clave: 'resultado', titulo: 'Resultado', alinear: 'der', ordenable: false, clase: 'p5-cifra', formato: (v, b) => resultado(b) },
    { clave: 'margen', titulo: 'Margen', ordenable: false, ancho: '210px', formato: (v, b) => {
      if (causasDeCelda(p, b, 'resultado_operativo').length) return el('span', { class: 'cifra-sin-dato', title: 'La cifra está tachada: el margen no es fiable' }, 'no fiable');
      return barraMargen(ui, margenBp(b.resultado, b.lineas.ingresos_brutos));
    } },
  ];
  const tablaPrincipal = ui.tabla({ etiqueta: 'Resultado por oferta', columnas, filas, vacio: 'Sin ofertas.', claseFila: (b) => (b.id === 'consolidado' ? 'p5-pnl-fila--consolidado' : '') });
  // indicadores por oferta (sin barras): pedidos, ticket medio, contribución, costo por venta, retorno neto, eficiencia
  const sd = (t) => el('span', { class: 'cifra-sin-dato' }, t);
  const dn = (x, vacio) => (x ? fmt.dinero(x.monto, x.moneda) : sd(vacio));
  const tablaIndicadores = ui.tabla({
    etiqueta: 'Indicadores por oferta', filas, vacio: 'Sin indicadores.',
    columnas: [
      { clave: 'id', titulo: 'Oferta', ordenable: false, formato: (v) => nombreBloque(v) },
      { titulo: 'Pedidos', alinear: 'der', ordenable: false, formato: (v, b) => (b.kpis.pedidos === null ? sd('sin dato') : fmt.num(b.kpis.pedidos)) },
      { titulo: 'Ticket medio', alinear: 'der', ordenable: false, formato: (v, b) => dn(b.kpis.aov, 'sin pedidos') },
      { titulo: 'Contribución por pedido', alinear: 'der', ordenable: false, formato: (v, b) => dn(b.kpis.mc, 'sin dato') },
      { titulo: 'Costo por venta', alinear: 'der', ordenable: false, formato: (v, b) => dn(b.kpis.cpa, 'sin compras') },
      { titulo: 'Retorno neto de anuncios', alinear: 'der', ordenable: false, formato: (v, b) => (b.kpis.roas_neto === null ? sd('sin dato') : b.kpis.roas_neto.toFixed(2).replace('.', ',')) },
      { titulo: 'Eficiencia de marketing', alinear: 'der', ordenable: false, formato: (v, b) => (b.kpis.mer === null ? sd('sin dato') : b.kpis.mer.toFixed(2).replace('.', ',')) },
    ],
  });
  // desglose completo: las 9 líneas de la fórmula, una columna por oferta (todo el dato original)
  const columnasFull = [
    { clave: 'etiqueta', titulo: 'Concepto', ordenable: false },
    ...bloques.map((b) => ({ clave: `v_${b.id}`, titulo: nombreBloque(b.id), alinear: 'der', ordenable: false, formato: (v, f) => (f.render ? f.render(b) : '') })),
  ];
  const celdaDinero = (b, clave) => {
    const dd = clave === 'resultado_operativo' ? b.resultado : b.lineas[clave];
    if (!dd) return sd('sin dato');
    const t = fmt.dinero(dd.monto, dd.moneda);
    const causas = causasDeCelda(p, b, clave);
    return causas.length ? ayudas.cifraTachada(t, 'tachada', causas.join('; ')) : el('span', null, t);
  };
  const filasFull = [
    ...LINEAS_PNL.map((l) => ({ etiqueta: `${l.signo > 0 ? '+' : '−'} ${l.etiqueta}`, render: (b) => celdaDinero(b, l.clave) })),
    { etiqueta: '= Resultado operativo', render: (b) => el('strong', null, celdaDinero(b, 'resultado_operativo')) },
    { etiqueta: 'La fórmula cuadra', render: (b) => (b.verificacion.coincide === true ? ui.chip('Cuadra', 'ok') : b.verificacion.coincide === false ? ui.chip('No cuadra', 'error') : ui.chip('Sin dato', 'neutro', { icono: 'circulo-punteado' })) },
  ];
  const unicas = new Map();
  for (const b of bloques) for (const k of [...LINEAS_PNL.map((l) => l.clave), 'resultado_operativo', 'kpis']) for (const c of causasDeCelda(p, b, k)) { if (!unicas.has(c)) unicas.set(c, new Set()); unicas.get(c).add(k); }
  const nombreDe = (k) => (k === 'resultado_operativo' ? 'resultado operativo' : k === 'kpis' ? 'indicadores' : (LINEAS_PNL.find((l) => l.clave === k) || { etiqueta: k }).etiqueta.toLowerCase());
  return ui.seccion('Resultado por oferta', el('div', { class: 'p5-pila' },
    ...[...unicas.entries()].map(([causa, claves]) => ayudas.aviso('error', el('strong', null, 'Cifras tachadas: '), causa, el('span', { class: 'p5-sub' }, ` — afecta a: ${[...claves].map(nombreDe).join(', ')}`))),
    ...p.avisos.map((a) => ayudas.aviso('aviso', a)),
    tablaPrincipal,
    el('h3', { class: 'p5-titulo-chico' }, 'Indicadores'),
    tablaIndicadores,
    el('p', { class: 'p5-sub' }, `Moneda base ${p.moneda || '—'}${p.fx_ref ? ` · tipo de cambio ${p.fx_ref}` : ' · sin conversión de moneda'}${p.frescura ? ` · datos hasta ${fmt.fecha(p.frescura.datos_hasta)}` : ''}.`),
    ui.detalleTecnico('Desglose completo línea por línea (la fórmula entera)', () => ui.tabla({ etiqueta: 'Cuenta de resultados completa', columnas: columnasFull, filas: filasFull, vacio: 'Sin líneas.' }))),
  { glosario: 'pnl', ayuda: 'Una fila por oferta más la de todas juntas. La barra de margen va a la derecha del cero si hay ganancia (azul) y a la izquierda si hay pérdida (rojo); el número siempre está al lado.' });
}

// ───────────────────────── libro de movimientos ─────────────────────────

function seccionLedger(ctx, m, ayudas) {
  const { ui, fmt, estado } = ctx;
  const { el } = ui;
  const led = m.ledger;
  if (!led.vigentes.length) {
    return ui.seccion('Libro de movimientos', ayudas.vacioConComandos('El libro de movimientos está vacío o aún no existe.', {
      pista: 'Una línea por venta, gasto, reembolso, disputa, comisión o costo. Es el registro contable de referencia: ingresos de Stripe, gasto de Meta y costos de cada oferta.',
      archivo: 'empresa/finanzas/ledger.jsonl',
      comandos: [{ etiqueta: 'Carga cobros de prueba de Stripe', cmd: comandosFinanzas().etl }, { etiqueta: 'Arma el libro de movimientos de una oferta', cmd: comandosFinanzas().ledger }],
    }), { glosario: 'ledger' });
  }
  if (FILTROS.tecnico === null) FILTROS.tecnico = Boolean(estado && estado.modoTecnico);
  const opciones = (lista, actual, etiqueta, nombre) => [el('option', { value: '' }, etiqueta), ...lista.map((x) => el('option', { value: x, selected: x === actual ? true : null }, nombre ? (nombre[x] || x) : x))];
  const resumen = el('div', { class: 'p5-pila' });
  const pintarResumen = (lineas) => {
    const t = totalesLedger(lineas);
    ui.reemplazar(resumen,
      t.monedas.length
        ? t.monedas.map((x) => el('div', { class: 'p5-totales' },
          el('div', { class: 'p5-total' }, el('span', { class: 'p5-total__etiqueta' }, `Entradas (${x.moneda})`), el('span', { class: 'p5-total__valor' }, x.entradas === null ? '—' : fmt.dinero(x.entradas, x.moneda))),
          el('div', { class: 'p5-total' }, el('span', { class: 'p5-total__etiqueta' }, `Salidas (${x.moneda})`), el('span', { class: 'p5-total__valor' }, x.salidas === null ? '—' : fmt.dinero(x.salidas, x.moneda))),
          el('div', { class: 'p5-total' }, el('span', { class: 'p5-total__etiqueta' }, `Neto (${x.moneda})`), el('span', { class: 'p5-total__valor' }, x.neto === null ? '—' : fmt.dinero(x.neto, x.moneda))),
          el('div', { class: 'p5-total' }, el('span', { class: 'p5-total__etiqueta' }, 'Líneas'), el('span', { class: 'p5-total__valor' }, fmt.num(x.lineas)))))
        : el('span', { class: 'cifra-sin-dato' }, 'Sin líneas con estos filtros: no hay totales (no es un cero).'),
      t.pruebasExcluidas ? el('span', { class: 'p5-sub' }, `${t.pruebasExcluidas} líneas de prueba excluidas de los totales`) : null);
  };
  const aplicar = () => filtrarLedger(led.vigentes, { oferta: FILTROS.oferta, tipo: FILTROS.tipo, fuente: FILTROS.fuente, incluirPruebas: FILTROS.pruebas });
  const contenedorTabla = el('div');
  const construirTabla = () => {
    const columnas = [
      { clave: 'fecha', titulo: 'Fecha', formato: (v) => fmt.fecha(v) },
      { clave: 'oferta_id', titulo: 'Oferta', formato: (v) => v || el('span', { class: 'texto-tenue' }, 'empresa') },
      { clave: 'tipo', titulo: 'Tipo', formato: (v) => ui.chip(NOMBRE_TIPO_LEDGER[v] || v, 'neutro', { icono: false }) },
      { clave: 'importe', titulo: 'Importe', alinear: 'der', orden: (f) => (f.sentido === 'entrada' ? 1 : -1) * f.importe.monto, formato: (v, f) => el('span', { class: ['p5-num', f.sentido === 'salida' ? 'texto-salida' : ''] }, `${f.sentido === 'entrada' ? '+' : '−'}${fmt.dinero(v.monto, v.moneda)}`) },
      { clave: 'fuente', titulo: 'Origen', formato: (v) => NOMBRE_FUENTE_LEDGER[v] || fmt.texto(v) },
      { clave: 'es_prueba', titulo: 'Prueba', formato: (v) => (v ? ui.chip('prueba', 'aviso', { icono: false }) : '') },
      ...(FILTROS.tecnico ? [
        { clave: 'adid', titulo: 'Anuncio (identificador)', formato: (v) => (v ? el('span', { class: 'p5-mono' }, v) : el('span', { class: 'texto-tenue' }, '—')) },
        { clave: 'clave_natural', titulo: 'Identificador de la línea', formato: (v) => el('span', { class: 'p5-mono' }, v) },
      ] : []),
    ];
    const tabla = ui.tabla({ etiqueta: 'Libro de movimientos', filtro: { placeholder: 'Buscar por oferta, tipo, anuncio…' }, maxFilas: 200, filas: aplicar(), ordenInicial: { clave: 'fecha', dir: 'desc' }, vacio: 'Ninguna línea con estos filtros.', columnas });
    ui.reemplazar(contenedorTabla, tabla);
    return tabla;
  };
  let tabla = construirTabla();
  const refrescar = () => { const l = aplicar(); tabla.actualizarFilas(l); pintarResumen(l); };
  const sel = (etiquetaAria, clave, lista, etiqueta, nombre) => el('select', { class: 'campo campo--chico', 'aria-label': etiquetaAria, onchange: (ev) => { FILTROS[clave] = ev.target.value; refrescar(); } }, opciones(lista, FILTROS[clave], etiqueta, nombre));
  pintarResumen(aplicar());
  const porOferta = m.porOferta;
  return ui.seccion('Libro de movimientos', el('div', { class: 'p5-pila' },
    led.posibleTruncado ? ayudas.aviso('aviso', el('strong', null, 'Totales posiblemente parciales: '), 'el panel lee solo las últimas 500 líneas del libro y hay 500 o más. La cuenta de resultados sí cubre todo el periodo.') : null,
    el('div', { class: 'p5-filtros' },
      el('span', { class: 'p5-filtros__etiqueta' }, ui.icono('filtro', { tam: 14 }), 'Filtrar'),
      sel('Filtrar por oferta', 'oferta', m.ofertas, 'Todas las ofertas'), sel('Filtrar por tipo', 'tipo', TIPOS_LEDGER, 'Todos los tipos', NOMBRE_TIPO_LEDGER), sel('Filtrar por origen', 'fuente', FUENTES_LEDGER, 'Todos los orígenes', NOMBRE_FUENTE_LEDGER),
      ui.interruptor({ etiqueta: 'Incluir pruebas', activo: FILTROS.pruebas, onCambio: (v) => { FILTROS.pruebas = v; refrescar(); } }),
      ui.interruptor({ etiqueta: 'Columnas técnicas', activo: FILTROS.tecnico, titulo: 'Muestra el identificador del anuncio y el identificador de cada línea', onCambio: (v) => { FILTROS.tecnico = v; tabla = construirTabla(); } })),
    resumen,
    porOferta.length > 1 ? ui.detalleTecnico('Totales por oferta', () => ui.tabla({
      etiqueta: 'Totales por oferta', filas: porOferta, vacio: 'Sin totales.',
      columnas: [
        { clave: 'oferta_id', titulo: 'Oferta' }, { clave: 'moneda', titulo: 'Moneda' }, { clave: 'lineas', titulo: 'Líneas', alinear: 'der' },
        { clave: 'entradas', titulo: 'Entradas', alinear: 'der', formato: (v, f) => fmt.dinero(v, f.moneda) }, { clave: 'salidas', titulo: 'Salidas', alinear: 'der', formato: (v, f) => fmt.dinero(v, f.moneda) },
        { clave: 'neto', titulo: 'Neto', alinear: 'der', formato: (v, f) => fmt.dinero(v, f.moneda) },
      ],
    }), { abierto: false }) : null,
    contenedorTabla,
    el('p', { class: 'p5-sub' }, `${fmt.num(led.vigentes.length)} líneas vigentes${led.reemplazadas ? ` · ${led.reemplazadas} reemplazadas por una corrección (se ve la última)` : ''}${led.invalidas ? ` · ${led.invalidas} descartadas por no tener el formato esperado` : ''}. Las sumas nunca mezclan monedas.`)),
  { glosario: 'ledger', ayuda: 'Entradas (+) y salidas (−) tal como se registraron; las líneas de prueba no cuentan en ningún total.' });
}

// ───────────────────────── costos de IA y alertas ─────────────────────────

function seccionCostosIa(ctx, m, ayudas) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  if (!m.costosIa.length) {
    return ui.seccion('Costos de IA', ayudas.vacioConComandos('Sin costos de IA en la cuenta de resultados.', {
      pista: 'Lo que cuestan los agentes se asigna a cada oferta y aparece como costo de IA en la cuenta de resultados. El detalle por agente y por ejecución está en Equipo de IA.',
      archivo: 'empresa/costos.jsonl',
      comandos: [{ etiqueta: 'Comprueba el registro de ejecuciones (solo lee: no cambia nada)', cmd: '.venv/bin/python -m engine.registro verificar --json' }],
    }), { glosario: 'costo_ia' });
  }
  return ui.seccion('Costos de IA', ui.tabla({
    etiqueta: 'Costos de IA', filas: m.costosIa, vacio: 'Sin costos.',
    columnas: [
      { clave: 'id', titulo: 'Oferta', formato: (v) => nombreBloque(v) },
      { clave: 'costo', titulo: 'Costo de IA', alinear: 'der', formato: (v) => fmt.dinero(v.monto, v.moneda) },
      { clave: 'ingresos', titulo: 'Ingresos brutos', alinear: 'der', formato: (v) => (v ? fmt.dinero(v.monto, v.moneda) : el('span', { class: 'cifra-sin-dato' }, 'sin dato')) },
      { clave: 'pctBp', titulo: 'Frente al máximo', ancho: '230px', formato: (v, f) => (v === null
        ? el('span', { class: 'cifra-sin-dato' }, 'sin ingresos: no hay porcentaje')
        : ayudas.medidor({ bp: f.topePct !== null ? Math.round((v / (f.topePct * 100)) * 10000) : Math.min(10000, v), zona: f.estado === 'rojo' ? 'rojo' : 'ok', texto: `${fmt.pct(v)} de los ingresos${f.topePct !== null ? ` · máx. ${f.topePct} %` : ''}`, etiqueta: 'Costo de IA frente al máximo' })) },
      { clave: 'estado', titulo: 'Estado', formato: (v) => (v === 'rojo' ? ui.chip('Sobre el máximo', 'error') : v === 'ok' ? ui.chip('Dentro del máximo', 'ok') : ui.chip('Sin base', 'neutro', { icono: 'circulo-punteado' })) },
      { clave: 'ledger', titulo: 'En el libro de movimientos', alinear: 'der', clase: 'cel-larga', formato: (v, f) => (v ? (f.descuadreConLedger ? ayudas.cifraTachada(fmt.dinero(v.monto, v.moneda), 'no coincide con la cuenta de resultados') : fmt.dinero(v.monto, v.moneda)) : el('span', { class: 'cifra-sin-dato' }, 'sin líneas')) },
    ],
  }), { glosario: 'costo_ia', ayuda: 'Costo de IA frente a los ingresos brutos, con el máximo permitido según tus parámetros.' });
}

function seccionAlertas(ctx, m, ayudas, sobre) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  if (!m.alertas.length) {
    return ui.seccion('Alertas', ayudas.vacioConComandos('No hay alertas registradas.', {
      pista: 'Finanzas anota una línea cada vez que salta una regla: gasto sobre el tope, costo de IA alto, cuentas que no cuadran, poca caja… Si todavía no corrió, este vacío significa que nadie las revisó, no que todo esté bien.',
      archivo: 'empresa/datos/alertas.jsonl',
      comandos: [{ etiqueta: 'Las reglas se revisan al conciliar, con este comando', cmd: comandosFinanzas().ledger }],
    }), { glosario: 'alerta_finanzas' });
  }
  const filaDe = (f) => (!f.abierta ? '' : f.tono === 'error' ? 'fila-error' : f.tono === 'grave' ? 'fila-grave' : f.tono === 'aviso' ? 'fila-aviso' : '');
  return ui.seccion('Alertas', ui.tabla({
    etiqueta: 'Alertas de finanzas', filas: m.alertas, filtro: { placeholder: 'Buscar alertas…' }, vacio: 'Sin alertas.', claseFila: filaDe,
    columnas: [
      { clave: 'ts', titulo: 'Cuándo', formato: (v) => (v ? ui.tiempo(v) : '—') },
      // la gravedad es SIEMPRE icono + etiqueta: info (i) · amarilla (triángulo) · naranja (rombo) · roja (círculo con X); sin umbral fijado queda gris
      { clave: 'severidad', titulo: 'Gravedad', orden: (f) => ({ error: 0, grave: 1, aviso: 2, info: 3, neutro: 4 }[f.tono]), formato: (v, f) => (f.sinUmbral
        ? ui.chip(`${f.etiquetaSeveridad} · sin límite`, 'neutro', { icono: 'circulo-punteado' })
        : ui.chip(f.etiquetaSeveridad, f.tono, f.tono === 'info' ? { icono: 'info' } : undefined)) },
      { clave: 'regla_id', titulo: 'Regla', formato: (v) => (v ? el('span', { class: 'p5-regla' }, v) : '—') },
      { clave: 'oferta_id', titulo: 'Oferta', formato: (v) => v || 'empresa' },
      { clave: 'valor', titulo: 'Valor', alinear: 'der' },
      { clave: 'umbral', titulo: 'Límite', alinear: 'der', formato: (v, f) => (f.sinUmbral ? el('span', { class: 'cifra-sin-dato', title: 'Sin límite fijado: la alerta no puede ponerse en verde' }, 'sin límite fijado') : v) },
      { clave: 'accion_sugerida', titulo: 'Qué hacer', clase: 'cel-larga' },
      { clave: 'estado', titulo: 'Estado', orden: (f) => f.estadoInfo.clave, formato: (v, f) => ui.chip(f.estadoInfo.texto, f.estadoInfo.tono, f.estadoInfo.clave === 'reconocida' ? { icono: 'ojo' } : undefined) },
    ],
  }), { glosario: 'alerta_finanzas', ayuda: 'Las abiertas primero, de más a menos graves: roja, naranja (pide pausar una oferta), amarilla e información. El panel solo las muestra: no pausa ni corrige nada.' });
}

// ───────────────────────── página ─────────────────────────

export async function render(ctx) {
  const { api, ui } = ctx;
  const { el } = ui;
  instalarEstilos(ui);
  const ayudas = ayudasVista(ui, ctx.fmt);
  const [fin, par] = await Promise.allSettled([api.sobre('/finanzas'), leerOpcional(api, '/parametros')]);
  const cab = ui.encabezadoPagina({
    titulo: 'Finanzas',
    descripcion: 'Lo que entra, lo que sale y si las cuentas cuadran: resultado por oferta, comparación de Stripe y Meta con el libro de movimientos, costos de IA y alertas. Una cifra que no cuadra se muestra tachada con su causa.',
    acciones: [botonActualizar(ctx)],
  });
  if (fin.status === 'rejected') return el('div', { class: 'pagina' }, cab, ui.errorBox(fin.reason, { reintentar: () => ctx.recargar() }));
  const sobre = fin.value;
  const parametros = par.status === 'fulfilled' && par.value && par.value.datos ? par.value.datos.parametros : null;
  const m = modeloFinanzas(sobre.datos, parametros);
  if (!m.hayAlgo) {
    return el('div', { class: 'pagina' }, cab,
      ayudas.vacioConComandos('Todavía no hay datos de finanzas.', {
        compacto: false,
        pista: 'Finanzas guarda el libro de movimientos, la cuenta de resultados, la conciliación y las alertas. Hasta entonces no se muestra ninguna cifra, ni ceros: llegarán con la primera oferta que venda.',
        archivo: 'empresa/finanzas/{ledger.jsonl, pnl.json, conciliacion.json, alertas.jsonl}',
        comandos: [{ etiqueta: 'Carga cobros de prueba de Stripe', cmd: comandosFinanzas().etl }, { etiqueta: 'Arma el libro de movimientos de una oferta', cmd: comandosFinanzas().ledger }],
        fuente: sobre.fuente,
      }),
      ui.fuenteInfo(sobre));
  }
  return el('div', { class: 'pagina' }, cab,
    ui.atencion({ items: atencionFinanzas(m), vacio: 'Todo en orden: las cuentas cuadran y no hay alertas abiertas.' }),
    metricas(ctx, m, ayudas),
    seccionConciliacion(ctx, m, ayudas, sobre),
    seccionPnl(ctx, m, ayudas),
    seccionLedger(ctx, m, ayudas),
    seccionCostosIa(ctx, m, ayudas),
    seccionAlertas(ctx, m, ayudas, sobre),
    ui.fuenteInfo(sobre));
}

/** Actualización en vivo: re-renderiza salvo que la persona esté escribiendo en un filtro. */
export async function alCambio(ctx) {
  if (hayEdicion()) return undefined;
  return render(ctx);
}
