// pages/pagos.js — #/pagos: «Pagos: que ninguna cuenta se frene por un pago». El último estado de la cuenta publicitaria de Meta y de los cobros de Stripe (ítems del
// preflight, GET /sistema → infra.items) y el dinero que entra y sale (libro y conciliación Stripe ↔ libro ↔ Meta, GET /finanzas). SOLO LECTURA.
// Sin cifras inventadas: el saldo de la cuenta de Meta NO está disponible como número y la pantalla lo dice y explica qué lo producirá (el vigía de pagos).
// Texto de los archivos (mensajes del preflight, motivos) entra por textContent. La lógica pura vive en ../lib/pagos.js.

import { ui, el, icono, fmt } from '../ui.js';
import { CSS_COMUN, CSS_PAGOS } from '../lib/estilos-n1.js';
import * as L from '../lib/pagos.js';

export const meta = { ruta: 'pagos', titulo: 'Pagos', grupo: 'Robots', icono: 'tarjeta', escucha: ['empresa'] };

const FUENTES = ['empresa/infra/estado.json', 'empresa/finanzas/ledger.jsonl', 'empresa/finanzas/conciliacion.json'];

/** Cabecera de pantalla con la rejilla contenida (en móvil, la lista de pestañas no ensancha la página). */
function cabecera(opciones) {
  const c = ui.encabezadoPagina(opciones);
  c.classList.add('n1-cab');
  return c;
}

async function leer(ctx, ruta) {
  try { return { ok: true, sobre: await ctx.api.sobre(ruta) }; } catch (err) { return { ok: false, err, sobre: null }; }
}

const ICONO_ESTADO = { ok: 'ok', aviso: 'alerta', error: 'x-circulo', neutro: 'circulo-punteado' };

function filaPregunta(p, ahoraMs) {
  return el('li', { class: 'n1-pregunta', 'data-item': p.id, 'data-tono': p.tono },
    el('div', null,
      el('h4', null, p.pregunta, p.pago ? el('span', { class: 'n1-tenue' }, ' · frena pagos') : null),
      el('p', null, p.explica),
      p.mensaje ? el('p', null, el('strong', null, 'El chequeo dice: '), p.mensaje) : null),
    el('div', { class: 'n1-pregunta__estado' },
      ui.chip(p.etiqueta, p.tono === 'neutro' ? 'neutro' : p.tono, { icono: ICONO_ESTADO[p.tono] || 'circulo-punteado' }),
      p.medidoEn ? el('small', { title: fmt.fecha(p.medidoEn, { segundos: true }) }, `medido ${fmt.relativo(p.medidoEn, ahoraMs)}`) : el('small', null, 'nunca medido')));
}

function tarjetaCuenta(c, modelo, ahoraMs) {
  const v = c.veredicto;
  const todas = [...c.preguntas, ...c.extras];
  return el('article', { class: 'n1-cuenta', 'data-cuenta': c.id },
    el('div', { class: 'n1-cuenta__cab' },
      el('h3', null, icono(c.icono, { tam: 18 }), ui.termino(c.glosario, { texto: c.nombre })),
      ui.chip(v.etiqueta, v.tono, { icono: ICONO_ESTADO[v.tono] || 'circulo-punteado' })),
    el('p', { class: 'n1-nota' }, c.frena),
    modelo.hayInfra ? el('p', { class: 'n1-nota' }, v.frase, modelo.simulada ? ' (medición simulada)' : '') : null,
    el('ul', { class: 'n1-preguntas', 'aria-label': `Comprobaciones de ${c.nombre}` }, todas.map((p) => filaPregunta(p, ahoraMs))),
    ui.detalleTecnico('Detalle técnico', () => el('dl', { class: 'n1-kv' }, todas.map((p) => [
      el('dt', null, p.id),
      el('dd', null, p.medido ? `${p.estado} · medido ${fmt.fecha(p.medidoEn)} · caduca ${fmt.fecha(p.expiraEn)}${p.critico ? ' · crítico' : ''}${p.evidencia ? ` · evidencia ${p.evidencia}` : ''}` : 'sin medir'),
    ]))));
}

function seccionSaldo(modelo) {
  const s = L.SIN_SALDO;
  const v = modelo.saldo.veredicto;
  return el('div', { class: 'n1-pila' },
    el('div', { class: 'n1-sinsaldo' }, icono('info', { tam: 20 }),
      el('div', null,
        el('h3', null, s.titulo),
        el('p', null, s.porque),
        el('p', null, el('strong', null, 'Qué lo producirá: '), s.produce),
        el('p', null, el('strong', null, 'Qué falta: ')),
        el('ul', { class: 'n1-lista' }, s.falta.map((f) => el('li', null, f))))),
    v && v.medido
      ? el('div', { class: 'n1-fila' }, el('span', { class: 'n1-nota' }, 'Lo único que hay hoy sobre el tope y la forma de pago es el veredicto del chequeo antes de lanzar:'), ui.chip(v.etiqueta, v.tono, { icono: ICONO_ESTADO[v.tono] || 'circulo-punteado' }), v.mensaje ? el('span', { class: 'n1-nota' }, `«${v.mensaje}»`) : null)
      : el('p', { class: 'n1-nota' }, 'Tampoco hay un veredicto del chequeo antes de lanzar sobre el tope de gasto: esa comprobación no se midió.'),
    el('div', { class: 'n1-fila' }, ui.enlace('Ver el vigía de pagos en Robots', '#/robots', { class: 'btn btn--chico' }), ui.enlace('Ver cómo te avisarían en Avisos', '#/avisos', { class: 'btn btn--chico' })));
}

function dineroOCero(v, moneda, tachada) {
  if (v === null) return el('span', { class: 'texto-tenue' }, 'sin movimientos');
  return el('span', { class: tachada ? 'n1-tachada' : null, title: tachada || null }, fmt.dinero(v, moneda));
}

function tablaCobros(cobrado, conc) {
  const tStripe = conc && conc.tachadas ? (conc.tachadas.stripe || conc.tachadas.todo) : null;
  const tMeta = conc && conc.tachadas ? (conc.tachadas.meta || conc.tachadas.todo) : null;
  return el('div', { class: 'n1-tabla-caja' },
    el('table', { class: 'n1-ruta' },
      el('caption', { class: 'solo-lectores' }, 'Dinero cobrado y gastado por moneda'),
      el('thead', null, el('tr', null, ['Moneda', 'Cobrado en ventas', 'Gastado en anuncios', 'Reembolsos', 'Disputas'].map((t) => el('th', { scope: 'col' }, t)))),
      el('tbody', null, cobrado.map((f) => el('tr', { 'data-moneda': f.moneda },
        el('td', null, f.moneda),
        el('td', null, dineroOCero(f.cobrado, f.moneda, tStripe)),
        el('td', null, dineroOCero(f.gastado, f.moneda, tMeta)),
        el('td', null, dineroOCero(f.reembolsos, f.moneda, tStripe)),
        el('td', null, dineroOCero(f.disputas, f.moneda, tStripe)))))));
}

function cotejo(c) {
  const par = (d) => (d ? fmt.dinero(d.monto, d.moneda) : '—');
  return el('div', { class: 'n1-cotejo', 'data-cuadra': c.cuadra === null ? 'sin_dato' : (c.cuadra ? 'si' : 'no') },
    el('h4', null, c.etiqueta),
    el('dl', { class: 'n1-kv' },
      el('dt', null, 'Una fuente'), el('dd', null, par(c.izquierda)),
      el('dt', null, 'Otra fuente'), el('dd', null, par(c.derecha)),
      el('dt', null, 'Diferencia'), el('dd', null, par(c.diferencia))),
    c.cuadra === null ? ui.chip('Sin cotejo completo', 'aviso') : (c.cuadra ? ui.chip('Cuadra', 'ok') : ui.chip('No cuadra', 'error')),
    c.causa ? el('p', { class: 'n1-nota' }, c.causa) : null);
}

function seccionDinero(modelo, rFin) {
  if (!rFin.ok) return ui.errorBox(rFin.err);
  const f = modelo.finanzas;
  if (!f || !f.hayAlgo) {
    return ui.vacioConPasos({
      titulo: 'Todavía no hay libro ni conciliación',
      explicacion: 'El libro de movimientos anota cada venta, gasto, reembolso y disputa; la conciliación compara Stripe, el libro y Meta. Sin ellos no hay forma de comprobar que lo cobrado coincide con lo que dicen las plataformas.',
      icono: 'cartera',
      pasos: [
        { texto: 'Genera el libro de movimientos de una oferta (cuando tenga movimientos):', comando: L.comandosPagos()[1].comando },
        { texto: 'Cuando exista, aquí vas a ver lo cobrado, lo gastado y si Stripe y Meta cuadran con el libro.' },
      ],
    });
  }
  const c = modelo.conciliacion;
  const cuerpo = [];
  cuerpo.push(c ? el('div', { class: 'n1-fila' }, ui.chip((ESTADO_TEXTO[c.estado] || c.estado), { CONCILIADO: 'ok', DESCUADRE: 'error', INCOMPLETO: 'aviso' }[c.estado] || 'neutro'), el('span', { class: 'n1-nota' }, (L_ESTADO[c.estado] || {}).frase || ''))
    : el('div', { class: 'n1-aviso n1-aviso--neutro' }, icono('info', { tam: 16 }), 'Todavía no hay conciliación: nadie comparó Stripe y Meta con el libro de movimientos, así que las cifras de abajo no están verificadas.'));
  if (modelo.cobrado.length) cuerpo.push(tablaCobros(modelo.cobrado, c));
  else cuerpo.push(el('p', { class: 'n1-nota' }, 'El libro todavía no tiene movimientos reales (las líneas de prueba no cuentan).'));
  if (c) cuerpo.push(el('div', { class: 'n1-cotejos' }, cotejo(c.stripe), cotejo(c.meta)));
  if (f.ledger && f.ledger.posibleTruncado) cuerpo.push(el('p', { class: 'n1-nota' }, 'El panel lee solo las últimas 500 líneas del libro: con tantas, los totales pueden ser parciales. El detalle completo está en Finanzas.'));
  cuerpo.push(el('div', { class: 'n1-fila' }, ui.enlace('Abrir Finanzas', '#/finanzas', { class: 'btn btn--chico' })));
  return el('div', { class: 'n1-pila' }, cuerpo);
}
const ESTADO_TEXTO = { CONCILIADO: 'Cuadra', DESCUADRE: 'No cuadra', INCOMPLETO: 'Incompleta' };
const L_ESTADO = { CONCILIADO: { frase: 'Stripe y Meta coinciden con el libro de movimientos.' }, DESCUADRE: { frase: 'Alguna fuente no coincide con el libro: las cifras afectadas se muestran tachadas con su causa.' }, INCOMPLETO: { frase: 'Faltan datos para cerrar el cotejo.' } };

function seccionVigilancia() {
  return el('div', { class: 'n1-canal' },
    el('div', null, el('h3', null, icono('pulso', { tam: 16 }), 'Qué se mira hoy'), el('p', null, 'El chequeo antes de lanzar (la revisión de la infraestructura) mide las cuentas y deja el semáforo. Mientras no esté en verde, vigente (menos de 6 horas) y en modo vivo, nadie gasta ni activa. Con campañas activas, una revisión liviana repite cada 15 minutos las comprobaciones de pago.')),
    el('div', null, el('h3', null, icono('escudo', { tam: 16 }), 'Qué hace el vigía de pagos'), el('p', null, 'Si una cuenta deja de gastar por un pago, avisa al celular por dos canales y pausa. Reanudar siempre es decisión humana. Hoy existe la sonda y la pausa; falta el aviso al celular y la lectura del saldo.')),
    el('div', null, el('h3', null, icono('lista', { tam: 16 }), 'Cuándo se frena una cuenta'), el('p', null, 'Por una cuenta deshabilitada o con motivo de bloqueo, un tope de gasto alcanzado o sin fijar, fondos prepagos, una tarjeta que falla o un cobro de Stripe inhabilitado.')));
}

export async function render(ctx) {
  ui.instalarEstilos('n1-comun', CSS_COMUN);
  ui.instalarEstilos('n1-pagos', CSS_PAGOS);
  const ahoraMs = Date.now();
  const [rSis, rFin] = await Promise.all([leer(ctx, '/sistema'), leer(ctx, '/finanzas')]);
  const sistema = rSis.ok ? rSis.sobre.datos : null;
  const modelo = L.modeloPagos({ sistema, finanzas: rFin.ok ? rFin.sobre.datos : null, ahoraMs });

  if (!rSis.ok && !rFin.ok) {
    return el('div', { class: 'pagina' }, cabecera({ titulo: 'Pagos: que ninguna cuenta se frene por un pago', descripcion: 'No se pudo leer el estado de las cuentas.' }), ui.errorBox(rSis.err, { reintentar: () => ctx.recargar() }));
  }

  const atencion = ui.atencion({ items: L.atencionPagos(modelo), vacio: 'Ninguna cuenta pide atención: la última medición salió en verde y Stripe y Meta cuadran con el libro de movimientos.' });
  const metricas = el('div', { class: 'n1-metricas' }, L.metricasPagos(modelo, ahoraMs).map((m) => ui.metrica({
    etiqueta: m.etiqueta, valor: m.valor, contexto: m.contexto, tono: m.tono || undefined, ayuda: m.ayuda,
  })));
  const fuentes = [...new Set([...(rSis.ok ? rSis.sobre.fuente : []), ...(rFin.ok ? rFin.sobre.fuente : [])])];
  const comandos = L.comandosPagos();

  return el('div', { class: 'pagina' },
    cabecera({
      titulo: 'Pagos: que ninguna cuenta se frene por un pago',
      descripcion: 'Si la cuenta publicitaria se bloquea, llega a su tope o su pago falla, los anuncios dejan de gastar; si Stripe no puede cobrar, se pierden ventas. Aquí ves el último estado de cada cuenta y qué falta para vigilarlo en tiempo real.',
      acciones: [ui.fuente(fuentes.length ? fuentes : FUENTES, { leido: rSis.ok ? rSis.sobre.generado_en : null }), el('button', { type: 'button', class: 'btn btn--chico', onclick: () => ctx.recargar() }, icono('refrescar', { tam: 14 }), 'Actualizar')],
    }),
    atencion,
    metricas,
    !modelo.hayInfra
      ? ui.vacioConPasos({
        titulo: 'Todavía no se han medido las cuentas',
        explicacion: 'El chequeo antes de lanzar (la revisión de la infraestructura) es el que mira Meta y Stripe. Sin él, las filas de abajo aparecen «sin medir» y nadie puede gastar ni activar.',
        icono: 'servidor',
        pasos: [{ texto: 'Corre el chequeo de la infraestructura:', comando: comandos[0].comando }, { texto: 'Cuando termine, esta pantalla se actualiza sola con el estado de cada cuenta.' }],
      })
      : (modelo.simulada ? el('div', { class: 'n1-aviso' }, icono('alerta', { tam: 18 }), el('div', null, el('strong', null, 'Medición simulada: '), `la última revisión se hizo en modo ${modelo.modo || 'desconocido'}, así que no mira las cuentas reales. Sirve para ver la pantalla, no para saber si una cuenta está al día.`)) : null),
    ui.seccion('Las cuentas que pagan y cobran', el('div', { class: 'n1-cuentas' }, modelo.cuentas.map((c) => tarjetaCuenta(c, modelo, ahoraMs))), { glosario: 'item_preflight', ayuda: 'Cada pregunta es una comprobación de solo lectura. El color nunca va solo: lleva icono y texto, y una medición caducada no se muestra como verde.' }),
    ui.seccion('El saldo de la cuenta de Meta', seccionSaldo(modelo), { glosario: 'saldo_cuenta' }),
    ui.seccion('El dinero que entra y sale', seccionDinero(modelo, rFin), { glosario: 'conciliacion', ayuda: 'Cobrado en Stripe, gastado en Meta y si ambos cuadran con el libro de movimientos. Una cifra que no cuadra se muestra tachada con su causa.' }),
    ui.seccion('Cómo se vigila', seccionVigilancia(), { glosario: 'robot_vigia' }),
    ui.detalleTecnico('Cómo medir las cuentas y el libro', el('div', { class: 'n1-pila n1-pila--chica' }, comandos.map((c) => ui.comando(c.comando, { titulo: c.titulo })))));
}
