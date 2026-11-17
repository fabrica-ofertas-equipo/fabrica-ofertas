// pages/resumen.js — centro de mando = «La rueda»: «¿Me puedo ausentar?» (semáforo verde/amarillo/rojo y qué falta, en orden y a quién le toca) → «Requiere tu atención» →
// «La rueda: los 9 pasos de cada día» (estado real de cada paso) → métricas con contexto →
// «Cómo van tus ofertas» (mini-pipeline por oferta) →
// «Descubrimiento» (último barrido) → «Actividad reciente» (registro en lenguaje humano). Lo técnico (rutas, comandos, eventos crudos) va a
// detalle técnico / comando / fuente. Solo lectura: no firma, no pausa (eso es del botón de la barra superior).
// Lógica pura en ../lib/resumen.js y ../lib/registro.js.

import {
  agruparPorFase, alertasUnificadas, itemsAtencion, metricasResumen, estadoPipeline, frasePipeline, resumenDescubrimiento, actividadReciente,
  faltantes, COMANDO_PREFLIGHT, etapaHumana, nombreEtapa, avanceEtapas, pasosRueda, resumenRueda, ofertasConCreativos, rotuloNivel,
} from '../lib/resumen.js';
import { estadoCadena, tonoDeLinea, chipResultado, relativoSeguro } from '../lib/registro.js';
import { normalizarEntradas } from '../lib/pulido.js';
import { normalizarRegistro, clasificarLecturaRegistro, normalizarSombra } from '../lib/robots.js';
import { CSS_COMUN, CSS_RUEDA } from '../lib/estilos-n1.js';
import { modeloAlertasCalculadas } from '../lib/ausencia.js';
import { instalar as instalarAusencia, bloqueSemaforo, bloqueSemaforoNoDisponible } from '../lib/ausencia-vista.js';

export const meta = { ruta: 'resumen', titulo: 'Resumen', grupo: 'El sistema', icono: 'inicio', escucha: ['empresa', 'oferta', 'registro', 'barrido'] };

const COMANDO_CREAR = '.venv/bin/python -m engine.orq crear --brief ofertas/<id>/00-brief.yaml';
const COMANDO_BARRIDO = '.venv/bin/python -m scripts.modelado.barrido plan generar <CORRIDA> --escribir';

const CSS = `
.u1r-metricas { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--e-3, 12px); }
@media (min-width: 720px) { .u1r-metricas { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (min-width: 1360px) { .u1r-metricas { grid-template-columns: repeat(6, minmax(0, 1fr)); } }
@media (max-width: 340px) { .u1r-metricas { grid-template-columns: minmax(0, 1fr); } }
.u1r-cols { display: grid; grid-template-columns: minmax(0, 1.7fr) minmax(300px, 1fr); gap: var(--e-5, 24px); align-items: start; }
.u1r-col { display: flex; flex-direction: column; gap: var(--e-5, 24px); min-width: 0; }
.u1r-estrecha .vacio-pasos { grid-template-columns: minmax(0, 1fr); justify-items: start; padding: var(--e-4, 16px); gap: var(--e-3, 12px); }
.u1r-estrecha .vacio-pasos__ilus { display: none; }
@media (max-width: 1100px) { .u1r-cols { grid-template-columns: minmax(0, 1fr); } }

.u1r-ofertas { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: var(--e-3, 12px); }
.u1r-oferta { display: flex; flex-direction: column; gap: var(--e-3, 12px); padding: var(--e-4, 16px); background: var(--sup); border: 1px solid var(--borde); border-radius: 12px;
  color: var(--txt); text-decoration: none; box-shadow: var(--sombra); transition: border-color .14s ease, box-shadow .14s ease; min-width: 0; }
.u1r-oferta:hover { border-color: var(--borde-fuerte); }
.u1r-oferta:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }
.u1r-oferta[aria-current="true"] { border-color: var(--acento); box-shadow: 0 0 0 1px var(--acento); }
.u1r-oferta__cab { display: flex; align-items: flex-start; justify-content: space-between; gap: var(--e-2, 8px); flex-wrap: wrap; }
.u1r-oferta__id { font-weight: 600; font-size: 15px; overflow-wrap: anywhere; }
.u1r-oferta__etiquetas { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.u1r-pipe { display: flex; gap: 3px; margin: 0; padding: 0; list-style: none; }
.u1r-pipe li { flex: 1 1 0; min-width: 0; height: 24px; display: flex; align-items: center; justify-content: center; border-radius: 6px; font-size: 10px; font-weight: 600;
  letter-spacing: 0; font-variant-numeric: tabular-nums; border: 1px solid var(--borde); color: var(--txt-3); background: transparent; }
@media (max-width: 480px) { .u1r-pipe { gap: 2px; } .u1r-pipe li { font-size: 9px; border-radius: 5px; overflow: hidden; } }
.u1r-pipe li[data-estado="aprobado"] { background: var(--ok-bg); border-color: var(--ok-borde); color: var(--ok); }
.u1r-pipe li[data-estado="en_QA"], .u1r-pipe li[data-estado="en_progreso"] { background: var(--acento-bg); border-color: var(--acento); color: var(--acento-fuerte); }
.u1r-pipe li[data-estado="bloqueado"] { background: var(--error-bg); border-color: var(--error-borde); color: var(--error); }
.u1r-pipe li[data-estado="escalado"] { background: var(--aviso-bg); border-color: var(--aviso-borde); color: var(--aviso); }
.u1r-pipe li[data-estado="pendiente"] { border-style: dashed; }
.u1r-pipe li[data-actual="1"] { box-shadow: 0 0 0 2px var(--acento-bg), 0 0 0 3px var(--acento); }
.u1r-pipe li[data-firma="1"] { background: var(--aviso-bg); border-color: var(--aviso); color: var(--aviso); box-shadow: 0 0 0 2px var(--aviso-bg), 0 0 0 3px var(--aviso); }
.u1r-oferta__ahora { display: flex; gap: 8px; align-items: flex-start; font-size: 13px; color: var(--txt); line-height: 1.4; }
.u1r-oferta__ahora .icono { flex: none; margin-top: 2px; color: var(--txt-3); }
.u1r-oferta__ahora[data-espera="1"] .icono { color: var(--aviso); }
.u1r-oferta__prog { font-size: 12px; color: var(--txt-2); font-variant-numeric: tabular-nums; }
.u1r-oferta__pie { display: flex; flex-wrap: wrap; gap: 4px 14px; font-size: 12px; color: var(--txt-2); border-top: 1px solid var(--borde); padding-top: var(--e-2, 8px); font-variant-numeric: tabular-nums; }
.u1r-oferta__aviso { font-size: 12px; color: var(--aviso); display: flex; gap: 6px; align-items: center; }

.u1r-fase { display: flex; flex-direction: column; gap: var(--e-3, 12px); }
.u1r-fase__cab { display: flex; align-items: center; gap: var(--e-2, 8px); font-size: 12px; color: var(--txt-2); }
.u1r-fase__n { font-variant-numeric: tabular-nums; color: var(--txt-3); }

.u1r-desc { display: flex; flex-direction: column; gap: var(--e-4, 16px); }
.u1r-desc__metricas { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: var(--e-3, 12px); }
.u1r-barra { height: 6px; border-radius: 999px; background: var(--sup-3); overflow: hidden; }
.u1r-barra > i { display: block; height: 100%; background: var(--acento); border-radius: 999px; }
.u1r-desc__pie { display: flex; flex-wrap: wrap; gap: 6px 16px; align-items: center; justify-content: space-between; font-size: 13px; color: var(--txt-2); }
.u1r-desc__aviso { display: flex; gap: 8px; align-items: flex-start; padding: var(--e-3, 12px); border: 1px solid var(--aviso-borde); background: var(--aviso-bg); color: var(--aviso); border-radius: 8px; font-size: 13px; }

.u1r-actividad { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; }
.u1r-ev { display: grid; grid-template-columns: 28px minmax(0, 1fr) auto; gap: 10px; padding: 10px 0; border-bottom: 1px solid var(--borde); align-items: start; }
.u1r-ev:last-child { border-bottom: 0; }
.u1r-ev__ic { width: 28px; height: 28px; border-radius: 50%; display: grid; place-items: center; background: var(--neutro-bg); color: var(--neutro); }
.u1r-ev__ic[data-tono="ok"] { background: var(--ok-bg); color: var(--ok); }
.u1r-ev__ic[data-tono="aviso"] { background: var(--aviso-bg); color: var(--aviso); }
.u1r-ev__ic[data-tono="error"] { background: var(--error-bg); color: var(--error); }
.u1r-ev__ic[data-tono="info"] { background: var(--info-bg); color: var(--info); }
.u1r-ev__tit { font-size: 13.5px; line-height: 1.4; color: var(--txt); overflow-wrap: anywhere; }
.u1r-ev__meta { display: flex; flex-wrap: wrap; gap: 2px 8px; font-size: 12px; color: var(--txt-2); margin-top: 2px; }
.u1r-ev__hora { font-size: 12px; color: var(--txt-3); white-space: nowrap; font-variant-numeric: tabular-nums; }
.u1r-sello { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; font-size: 13px; color: var(--txt-2); margin-bottom: var(--e-2, 8px); }
.u1r-falta { display: flex; flex-direction: column; gap: var(--e-3, 12px); }
.u1r-falta ul { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: var(--e-3, 12px); align-items: start; }
.u1r-falta li { display: flex; flex-direction: column; gap: 6px; padding: var(--e-3, 12px); border: 1px solid var(--borde); border-radius: 10px; background: var(--sup); }
.u1r-falta h3 { margin: 0 0 var(--e-2, 8px); font-size: 13px; font-weight: 600; color: var(--txt-2); }
.u1r-modal p { margin: 0 0 var(--e-3, 12px); line-height: 1.5; }
.u1r-modal ol { list-style: decimal; margin: 0 0 var(--e-3, 12px); padding-left: 20px; display: flex; flex-direction: column; gap: 6px; line-height: 1.45; }
.u1r-modal__datos { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: var(--e-3, 12px); }
`;

/** Pide un endpoint sin lanzar: {ok, datos, fuente, generado_en, vacio, avisos, err}. */
async function pedir(ctx, ruta, params) {
  try { return { ok: true, ...(await ctx.api.sobre(ruta, params)) }; } catch (err) { return { ok: false, err, datos: null, fuente: [], generado_en: null, vacio: false, avisos: [] }; }
}

export async function render(ctx) {
  const U = ctx.ui;
  const { el, fmt, chip, estadoChip, seccion, tabla, vacio, errorBox, comando, encabezadoPagina, atencion, metrica, detalleTecnico, vacioConPasos, enlace, icono, fuente, modal } = U;
  U.instalarEstilos('u1-resumen', CSS);
  U.instalarEstilos('n1-comun', CSS_COMUN);
  U.instalarEstilos('n1-rueda', CSS_RUEDA);

  const [rSis, rOfe, rReg, rFin, rPar, rDes, rPul, rRob, rAle, rSom] = await Promise.all([
    pedir(ctx, '/sistema'), pedir(ctx, '/ofertas'), pedir(ctx, '/registro', { limite: 100 }), pedir(ctx, '/finanzas'), pedir(ctx, '/parametros'), pedir(ctx, '/descubrimiento/corridas'),
    pedir(ctx, '/pulido'), pedir(ctx, '/robots'), pedir(ctx, '/alertas'), pedir(ctx, '/robots/sombra'),
  ]);
  // Piezas de creativos: el detalle de cada oferta que ya pasó de «pendiente» en la etapa D6 (GET /oferta/<id>); lo que falle queda como «no se pudo contar».
  const idsCreativos = rOfe.ok && Array.isArray(rOfe.datos) ? ofertasConCreativos(rOfe.datos) : [];
  const detallesLista = await Promise.all(idsCreativos.map((id) => pedir(ctx, `/oferta/${encodeURIComponent(id)}`)));
  const detalles = Object.fromEntries(idsCreativos.map((id, i) => [id, detallesLista[i].ok ? detallesLista[i].datos : null]));
  const ahora = Date.now();
  const cabecera = encabezadoPagina({
    titulo: 'Resumen',
    descripcion: 'Qué pasa ahora en la fábrica, qué espera de ti y cómo se comporta el sistema.',
    acciones: [el('button', { type: 'button', class: 'btn', onclick: () => ctx.recargar() }, icono('refrescar', { tam: 14 }), 'Actualizar')],
  });

  if (!rSis.ok && !rOfe.ok) {
    return el('div', { class: 'pagina' }, cabecera, errorBox(rSis.err, { reintentar: () => ctx.recargar() }));
  }

  const sistema = rSis.ok ? rSis.datos : null;
  const hayOfertas = rOfe.ok && Array.isArray(rOfe.datos);
  const ofertas = hayOfertas ? rOfe.datos : [];
  const registro = rReg.ok && rReg.datos && typeof rReg.datos === 'object' ? rReg.datos : null;
  const finanzas = rFin.ok && rFin.datos && typeof rFin.datos === 'object' ? rFin.datos : null;
  const parametros = rPar.ok && rPar.datos && typeof rPar.datos === 'object' ? rPar.datos : null;
  const corridas = rDes.ok && Array.isArray(rDes.datos) ? rDes.datos : [];

  const alertas = alertasUnificadas({ registro, finanzas, limite: 8, ventanaH: 72, ahoraMs: ahora });
  const cadenaOk = registro && !rReg.vacio ? registro.cadena_ok : undefined;
  const items = itemsAtencion({ sistema, ofertas, parametros, alertas: rReg.ok || rFin.ok ? alertas : [], cadenaOk, ahoraMs: ahora });
  const motorFalta = sistema && sistema.motor_disponible === false;

  // ── modales de «cómo hacerlo» (el panel no firma ni ejecuta: muestra el comando exacto) ──
  function abrirFirma(g) {
    modal({
      titulo: `Cómo firmar: ${etapaHumana(g.etapa)} de ${g.oferta_id}`, ancho: '640px',
      cuerpo: el('div', { class: 'u1r-modal' },
        el('div', { class: 'u1r-modal__datos' }, chip(etapaHumana(g.etapa), 'acento'), g.fase ? estadoChip(g.fase) : null, g.nivel ? chip(rotuloNivel(g.nivel), 'neutro', { icono: false }) : null, g.demo ? chip('demostración', 'info') : null),
        el('p', null, 'Esta etapa ya pasó la revisión de calidad. El sistema no avanza hasta que tú la apruebes con tu firma. Este panel no firma por ti.'),
        el('ol', null,
          el('li', null, 'Revisa lo que produjo la etapa en la ficha de la oferta.'),
          el('li', null, 'Si estás de acuerdo, copia el comando y pégalo en la Terminal de tu computadora. Tu clave de firma no sale de tu equipo.'),
          el('li', null, 'Esta pantalla se actualiza sola cuando quede registrada tu firma.')),
        g.comando ? comando(g.comando, { titulo: 'Cómo hacerlo: copia este comando para firmar', abierto: true, etiqueta: `Copiar el comando para firmar ${g.etapa} de ${g.oferta_id}` })
          : el('p', { class: 'texto-tenue' }, 'El nombre de la oferta o de la etapa tiene un formato inesperado, así que no se puede armar el comando.'),
        motorFalta ? el('p', { class: 'texto-tenue' }, 'Ojo: el sistema automático todavía no está construido; el comando se podrá usar cuando lo esté.') : null),
      acciones: [{ texto: 'Abrir la oferta', alClick: () => { ctx.navegar(`#/oferta/${encodeURIComponent(g.oferta_id)}`); } }, { texto: 'Cerrar', tono: 'primario' }],
    });
  }
  function abrirPreflight() {
    modal({
      titulo: 'Cómo hacer el chequeo antes de lanzar', ancho: '640px',
      cuerpo: el('div', { class: 'u1r-modal' },
        el('p', null, 'Este chequeo revisa de una vez las cuentas y servicios (Meta, Stripe, Cloudflare…) y deja un semáforo. Mientras no esté en verde, tenga menos de 6 horas y sea una medición real (no un simulacro), nadie gasta ni activa.'),
        comando(COMANDO_PREFLIGHT, { titulo: 'Cómo hacerlo: copia este comando', abierto: true }),
        el('p', { class: 'texto-tenue' }, 'Cuando termine, esta pantalla se actualiza sola.')),
      acciones: [{ texto: 'Ver Salud del sistema', alClick: () => { ctx.navegar('#/sistema'); } }, { texto: 'Cerrar', tono: 'primario' }],
    });
  }
  const accionDe = (a) => (a.tipo === 'firmar' ? { texto: a.texto, onClick: () => abrirFirma(a.gate) } : a.tipo === 'preflight' ? { texto: a.texto, onClick: abrirPreflight } : { texto: a.texto, ruta: a.ruta });

  // ── 0) ¿me puedo ausentar? (semáforo calculado de los archivos por GET /alertas; si falla, no se inventa uno) ──
  instalarAusencia();
  const semaforo = rAle.ok ? (modeloAlertasCalculadas(rAle.datos) || {}).semaforo || null : null;
  const panelAusencia = semaforo
    ? bloqueSemaforo(semaforo, { ahoraMs: ahora, fuenteLeida: fuente(rAle.fuente || [], { leido: rAle.generado_en }) })
    : bloqueSemaforoNoDisponible(rAle.ok ? null : rAle.err, () => ctx.recargar());

  // ── 1) requiere tu atención ──
  const panelAtencion = atencion({
    items: items.map((i) => ({ tono: i.tono, titulo: i.titulo, detalle: i.detalle, accion: accionDe(i.accion), ayuda: i.ayuda })),
    vacio: sistema ? 'Nada requiere tu atención ahora: sin firmas pendientes, sin pausa y sin alertas recientes.' : 'No se pudo leer el estado del sistema.',
  });

  // ── 1b) la rueda: los 9 pasos de cada día, cada uno con su estado real ──
  const estadoRobots = clasificarLecturaRegistro({ error: rRob.err, sobre: rRob.ok ? rRob : null });
  const pasos = pasosRueda({
    pulido: rPul.ok ? normalizarEntradas(rPul.datos) : null, ofertas: hayOfertas ? ofertas : null, detalles,
    robots: estadoRobots === 'ok' ? normalizarRegistro(rRob.datos) : null, sombra: rSom.ok ? normalizarSombra(rSom) : null, paginas: ctx.paginas ? ctx.paginas() : {}, ahoraMs: ahora,
  });
  const cuenta = resumenRueda(pasos);
  const tarjetaPaso = (p) => el('li', null, el('a', { class: 'n1-paso', href: p.ruta, 'data-estado': p.estado, 'data-paso': String(p.n), 'aria-label': `Paso ${p.n}: ${p.titulo}. ${p.etiqueta}. ${p.dato}` },
    el('div', { class: 'n1-paso__cab' },
      el('span', { class: 'n1-paso__n', 'aria-hidden': 'true' }, String(p.n)),
      el('h3', { class: 'n1-paso__titulo' }, p.titulo)),
    el('div', { class: 'n1-paso__estado' }, chipPaso(p)),
    el('p', { class: 'n1-paso__dato' }, p.dato),
    p.nota ? el('p', { class: 'n1-paso__nota' }, p.nota) : null,
    el('span', { class: 'n1-paso__ir' }, p.verbo, icono('flecha-derecha', { tam: 13 }))));
  function chipPaso(p) {
    const c = U.chip(p.etiqueta, p.tono, { icono: p.icono });
    c.dataset.estado = p.estado;
    return c;
  }
  const panelRueda = seccion('La rueda: los 9 pasos de cada día', el('div', null,
    el('div', { class: 'n1-rueda-cab' },
      el('div', { class: 'n1-rueda-cuenta', 'aria-label': 'Resumen de la rueda' },
        el('span', null, el('b', null, String(cuenta.ok)), ' en marcha'), el('span', null, el('b', null, String(cuenta.aviso)), ' requieren atención'), el('span', null, el('b', null, String(cuenta.sin_datos)), ' sin datos todavía')),
      el('ol', { class: 'n1-tira', 'aria-hidden': 'true' }, pasos.map((p) => el('li', { 'data-estado': p.estado, title: `${p.n}. ${p.titulo}: ${p.etiqueta}` }, String(p.n))))),
    el('ol', { class: 'n1-rueda', 'aria-label': 'Los 9 pasos de la rueda' }, pasos.map(tarjetaPaso)),
    el('p', { class: 'n1-rueda-vuelta' }, icono('refrescar', { tam: 14 }), 'Del paso 9 se vuelve al paso 1, todos los días.')),
  { glosario: 'rueda_9_pasos', ayuda: 'Así gira el sistema entero. Cada paso muestra el dato real que hay; si falta, dice «sin datos todavía» y qué lo producirá.' });

  // ── 2) métricas ──
  const ms = metricasResumen({ ofertas: hayOfertas ? ofertas : null, sistema, alertas: rReg.ok || rFin.ok ? alertas : null, ahoraMs: ahora, cadenaOk });
  const panelMetricas = el('div', { class: 'u1r-metricas' }, ms.map((m) => metrica({
    etiqueta: m.etiqueta, valor: m.valor, contexto: m.contexto, tono: m.tono, ayuda: m.ayuda, ruta: m.ruta,
  })));

  // ── 3) cómo van tus ofertas ──
  const tarjetaOferta = (o) => {
    const p = estadoPipeline(o);
    const av = avanceEtapas(o.etapas);
    const activa = ctx.estado.ofertaActiva === o.oferta_id;
    const pipe = el('ol', { class: 'u1r-pipe', 'aria-label': `Etapas de ${o.oferta_id}: ${av.aprobadas} de ${av.total} aprobadas` },
      p.etapas.map((e) => el('li', { 'data-estado': e.estado, 'data-actual': e.seleccionada ? '1' : null, 'data-firma': e.aviso ? '1' : null, title: `${nombreEtapa(e.codigo)} (${e.codigo}): ${fmt.texto(infoRotulo(e.estado))}${e.aviso ? ` — ${e.aviso.toLowerCase()}` : ''}` }, e.codigo)));
    return el('a', { class: 'u1r-oferta', href: `#/oferta/${encodeURIComponent(o.oferta_id)}`, 'aria-current': activa ? 'true' : null },
      el('div', { class: 'u1r-oferta__cab' },
        el('span', { class: 'u1r-oferta__id' }, o.oferta_id),
        el('span', { class: 'u1r-oferta__etiquetas' }, o.demo ? chip('demostración', 'info') : null, o.nivel ? chip(rotuloNivel(o.nivel), 'neutro', { icono: false }) : null, o.pausa ? chip('pausada', 'aviso') : null)),
      p.etapas.length ? pipe : el('p', { class: 'texto-tenue' }, 'Sin etapas todavía'),
      el('div', { class: 'u1r-oferta__ahora', 'data-espera': p.espera ? '1' : null }, icono(p.espera ? 'firma' : (p.actual ? 'flecha' : 'ok'), { tam: 14 }), el('span', null, frasePipeline(o))),
      el('div', { class: 'u1r-oferta__prog' }, `${av.aprobadas} de ${av.total} etapas aprobadas`),
      o.aviso ? el('div', { class: 'u1r-oferta__aviso' }, icono('alerta', { tam: 13 }), o.aviso) : null,
      el('div', { class: 'u1r-oferta__pie' },
        el('span', null, 'Gasto hoy ', o.gasto && o.gasto.hoy ? fmt.dinero(o.gasto.hoy.monto, o.gasto.hoy.moneda) : '—'),
        el('span', null, 'IA ', o.costo_ia ? fmt.dinero(o.costo_ia.monto, o.costo_ia.moneda) : '—'),
        o.actualizado_en ? el('span', { title: fmt.fecha(o.actualizado_en) }, `actualizada ${relativoSeguro(o.actualizado_en, ahora)}`) : null));
  };
  const infoRotulo = (e) => U.infoEstado(e).texto;
  const porFase = agruparPorFase(ofertas);
  const cuerpoOfertas = !rOfe.ok ? errorBox(rOfe.err)
    : ofertas.length === 0 ? vacioConPasos({
      titulo: 'Todavía no hay ofertas', explicacion: 'Una oferta nace de una ficha inicial (el «brief»): qué vendes y a quién. La guía /o0-lanzar-oferta te acompaña con preguntas; después el sistema crea la oferta con el estado de cada etapa.',
      pasos: [{ texto: 'Escribe la ficha inicial con /o0-lanzar-oferta (hasta 10 preguntas, con respuestas sugeridas).' }, { texto: 'Crea la oferta con este comando:', comando: COMANDO_CREAR }], icono: 'caja',
    })
      : el('div', { class: 'u1r-col' }, porFase.map(({ fase, ofertas: lista }) => el('div', { class: 'u1r-fase' },
        el('div', { class: 'u1r-fase__cab' }, estadoChip(fase), el('span', { class: 'u1r-fase__n' }, `${lista.length} ${lista.length === 1 ? 'oferta' : 'ofertas'}`)),
        el('div', { class: 'u1r-ofertas' }, lista.map(tarjetaOferta)))));

  // ── 4) descubrimiento ──
  const d = resumenDescubrimiento(corridas);
  const freno = sistema && sistema.freno_captura && sistema.freno_captura.activo;
  const cuerpoDesc = !rDes.ok ? errorBox(rDes.err)
    : !d ? vacioConPasos({
      titulo: 'Todavía no hay ningún barrido', explicacion: 'El barrido recorre la Biblioteca de Anuncios de Meta y deja candidatos de oferta, ordenados por cuántos anuncios sostienen. Empieza planificando una corrida (una pasada de búsqueda).',
      pasos: [{ texto: 'Planifica las búsquedas de la corrida con este comando:', comando: COMANDO_BARRIDO }, { texto: 'Cuando haya datos, aquí verás los candidatos que muestran tracción (anuncios que se sostienen).' }], icono: 'lupa',
    })
      : el('div', { class: 'u1r-desc' },
        el('div', { class: 'u1r-desc__metricas' },
          metrica({ etiqueta: 'Candidatos que pasan tracción', valor: d.pasan_traccion === null ? '—' : String(d.pasan_traccion), contexto: d.pasan_temas !== null ? `${d.pasan_temas} con tema · ${d.pasan_sin_tema ?? 0} sin tema` : `de ${d.candidatas ?? '—'} candidatas`, tono: d.pasan_traccion ? 'ok' : 'neutro', ayuda: 'traccion', ruta: '#/descubrimiento' }),
          metrica({ etiqueta: 'Consultas usadas', valor: d.consultas_ok === null ? '—' : `${d.consultas_ok}${d.consultas_tope ? ` / ${d.consultas_tope}` : ''}`, contexto: d.pctConsultas !== null ? `${d.pctConsultas} % del máximo de la corrida` : 'sin máximo definido', tono: 'neutro', ayuda: 'consultas_barrido' }),
          metrica({ etiqueta: 'Páginas analizadas', valor: d.paginas === null ? '—' : fmt.num(d.paginas), contexto: `${d.etiquetadas === null ? '—' : fmt.num(d.etiquetadas)} etiquetadas · ${d.fichas === null ? '—' : d.fichas} fichas listas`, tono: 'neutro' })),
        d.pctConsultas !== null ? el('div', { class: 'u1r-barra', role: 'img', 'aria-label': `${d.pctConsultas} % de las consultas permitidas` }, el('i', { style: { width: `${d.pctConsultas}%` } })) : null,
        freno ? el('div', { class: 'u1r-desc__aviso' }, icono('candado', { tam: 16 }), el('span', null, 'La captura de anuncios está frenada: el barrido no puede seguir hasta que revises el freno. ', enlace('Revisar el freno', '#/sistema'))) : null,
        el('div', { class: 'u1r-desc__pie' },
          el('span', null, `Última corrida: `, el('strong', null, d.corrida_id), d.actualizado_en ? ` · actualizada ${fmt.relativo(d.actualizado_en, ahora)}` : '', d.total > 1 ? ` · ${d.total} corridas en total` : ''),
          enlace('Abrir Radar de ofertas', '#/descubrimiento', { class: 'btn btn--chico' })));

  // ── 5) actividad reciente ──
  const lineas = registro && Array.isArray(registro.lineas) ? registro.lineas : [];
  const cadena = estadoCadena(registro ? registro.cadena_ok : null, { vacio: rReg.vacio });
  const act = actividadReciente(lineas, 8);
  const cuerpoActividad = !rReg.ok ? errorBox(rReg.err)
    : act.length === 0 ? vacioConPasos({
      titulo: 'El historial aún no tiene actividad', explicacion: 'Cada acción del sistema y de los agentes de IA queda anotada aquí, en orden y protegida contra cambios. Se llena en cuanto corre algo.',
      pasos: [{ texto: 'Crea una oferta para que el sistema empiece a registrar:', comando: COMANDO_CREAR }], icono: 'lista',
    })
      : el('div', null,
        el('div', { class: 'u1r-sello' }, chip(cadena.texto, cadena.tono), el('span', null, registro ? `${fmt.num(registro.total || 0)} eventos en total` : ''), enlace('Ver todo el historial', '#/registro')),
        el('ul', { class: 'u1r-actividad' }, act.map(({ linea, vista }) => el('li', { class: 'u1r-ev' },
          el('span', { class: 'u1r-ev__ic', 'data-tono': vista.tono }, icono(vista.icono, { tam: 15 })),
          el('div', null,
            el('div', { class: 'u1r-ev__tit' }, vista.titulo),
            el('div', { class: 'u1r-ev__meta' },
              vista.oferta ? el('span', null, vista.oferta) : null, vista.etapa ? el('span', null, vista.etapa) : null, el('span', null, vista.actor),
              vista.live ? chip('En real', 'critico') : null, vista.fallo ? chip('falló', 'error') : null)),
          el('span', { class: 'u1r-ev__hora', title: fmt.fecha(linea.ts, { segundos: true }) }, relativoSeguro(linea.ts, ahora))))),
        detalleTecnico('Eventos técnicos del historial (últimas 15 líneas)', tabla({
          etiqueta: 'Últimas líneas del historial', maxFilas: 15, ordenInicial: { clave: 'n', dir: 'desc' },
          columnas: [
            { clave: 'n', titulo: '#', ancho: '52px', alinear: 'der' },
            { clave: 'ts', titulo: 'Hora', ancho: '132px', formato: (v) => fmt.fecha(v) },
            { clave: 'oferta_id', titulo: 'Oferta', ancho: '120px' },
            { clave: 'etapa', titulo: 'Etapa', ancho: '64px' },
            { clave: 'agente', titulo: 'Agente', ancho: '150px' },
            { clave: 'evento', titulo: 'Evento', ancho: '150px', formato: (v, f) => chip(v || '—', tonoDeLinea(f)) },
            { clave: 'entrada_resumen', titulo: 'Resumen', flex: true },
            { clave: 'resultado.estado', titulo: 'Resultado', ancho: '110px', formato: (v) => { const c = chipResultado(v); return chip(c.texto, c.tono); } },
          ],
          filas: lineas.slice(-15), alClick: () => ctx.navegar('#/registro'),
          vacio: { texto: 'El historial aún no tiene líneas.' },
        })));

  // ── 6) lo que falta ──
  const falt = faltantes({
    fuentes: {
      Ofertas: { vacio: rOfe.vacio, fuente: rOfe.fuente, comando: COMANDO_CREAR }, 'Historial de actividad': { vacio: rReg.vacio, fuente: rReg.fuente, comando: COMANDO_CREAR },
      Finanzas: { vacio: rFin.vacio, fuente: rFin.fuente }, 'Chequeo de cuentas y servicios': { vacio: sistema && !sistema.infra, fuente: ['empresa/infra/estado.json'], comando: COMANDO_PREFLIGHT },
    },
    paginas: ctx.paginas ? ctx.paginas() : {}, titulos: ctx.titulos ? ctx.titulos() : {},
  });
  const cuerpoFalta = (falt.datos.length + falt.pantallas.length) === 0
    ? vacio('No falta nada: todos los datos y pantallas están disponibles.', { icono: 'escudo' })
    : el('div', { class: 'u1r-falta' },
      falt.datos.length ? el('div', null, el('h3', null, 'Datos que aún no existen'), el('ul', null, falt.datos.map((x) => el('li', null,
        el('strong', null, x.nombre),
        el('span', { class: 'texto-tenue' }, 'Se llena cuando el sistema lo genera.'),
        x.fuente.length ? el('span', { class: 'solo-tecnico texto-tenue' }, 'Se esperaba: ', el('code', null, x.fuente.join(', '))) : null,
        x.comando ? comando(x.comando, { titulo: 'Cómo generarlo' }) : null)))) : null,
      falt.pantallas.length ? el('div', null, el('h3', null, 'Pantallas en construcción'), el('div', { class: 'fila-flex' }, falt.pantallas.map((p) => enlace(p.nombre, `#/${p.ruta}`, { class: 'btn btn--chico' })))) : null);

  const botonFuente = (r) => fuente(r.fuente || [], { leido: r.generado_en });

  return el('div', { class: 'pagina' },
    cabecera,
    panelAusencia,
    panelAtencion,
    panelRueda,
    panelMetricas,
    el('div', { class: 'u1r-cols' },
      el('div', { class: 'u1r-col' },
        seccion('Cómo van tus ofertas', cuerpoOfertas, { acciones: [botonFuente(rOfe), enlace('Ver todas', '#/ofertas', { class: 'btn btn--chico' })] }),
        seccion('Radar de ofertas', cuerpoDesc, { acciones: [botonFuente(rDes)] })),
      el('div', { class: 'u1r-col u1r-estrecha' },
        seccion('Actividad reciente', cuerpoActividad, { acciones: [botonFuente(rReg)] }))),
    seccion('Lo que falta por construir', cuerpoFalta),
  );
}
