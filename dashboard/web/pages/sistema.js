// pages/sistema.js — salud en una franja clara (PAUSA, freno, infraestructura, motor, registro, panel), preflight por ítem y consola de acciones de lista blanca.
// El panel NUNCA borra la PAUSA ni el freno: solo muestra la instrucción para que una persona lo haga (CONTRATO §6).
// La consola ejecuta únicamente acciones de dashboard/acciones.yaml (POST /accion) y muestra la salida en vivo (GET /job/<id>?desde=N).
// Lógica pura en ../lib/sistema.js. `alCambio` repinta solo la parte de estado: la consola (formulario, salida) no se pierde.

import { estadoInfra, COMANDO_PREFLIGHT, veredictoSistema } from '../lib/resumen.js';
import {
  elementosSalud, instruccionPausa, instruccionFreno, normalizarAcciones, validarArgs, normalizarJob, veredictoJob, tonoRiesgo, rotuloRiesgo, iconoRiesgo, explicacionRiesgo,
  agruparPreflight, agruparAcciones, etiquetaParametro,
} from '../lib/sistema.js';

export const meta = { ruta: 'sistema', titulo: 'Salud del sistema', grupo: 'Robots', icono: 'servidor', escucha: ['empresa', 'registro'] };

// Sobrevive a la navegación dentro de la sesión: acción elegida, valores del formulario y última ejecución.
const sesion = { accionId: null, valores: {}, jobId: null, desde: 0, texto: '', terminado: true, codigo: null, estado: null, estadoServidor: null, truncado: false };
const MAX_SALIDA = 300000;
const INTERVALO_JOB_MS = 800;
const MAX_FALLOS_JOB = 4;

const CSS = `
.u1s-salud { display: flex; flex-direction: column; background: var(--sup); border: 1px solid var(--borde); border-radius: 12px; box-shadow: var(--sombra); overflow: hidden; }
.u1s-veredicto { display: flex; gap: 14px; align-items: center; padding: var(--e-4, 16px) var(--e-5, 24px); border-bottom: 1px solid var(--borde); background: var(--sup-2); }
.u1s-veredicto__ic { flex: none; width: 44px; height: 44px; border-radius: 50%; display: grid; place-items: center; background: var(--neutro-bg); color: var(--neutro); }
.u1s-veredicto[data-tono="ok"] { background: var(--ok-bg); }
.u1s-veredicto[data-tono="aviso"] { background: var(--aviso-bg); }
.u1s-veredicto[data-tono="error"] { background: var(--error-bg); }
.u1s-veredicto[data-tono="ok"] .u1s-veredicto__ic { background: var(--sup); color: var(--ok); }
.u1s-veredicto[data-tono="aviso"] .u1s-veredicto__ic { background: var(--sup); color: var(--aviso); }
.u1s-veredicto[data-tono="error"] .u1s-veredicto__ic { background: var(--sup); color: var(--error); }
.u1s-veredicto h2 { margin: 0 0 2px; font-size: 17px; font-weight: 600; line-height: 1.3; }
.u1s-veredicto p { margin: 0; font-size: 13px; color: var(--txt-2); line-height: 1.45; }
.u1s-celdas { display: grid; grid-template-columns: minmax(0, 1fr); }
@media (min-width: 640px) { .u1s-celdas { grid-template-columns: repeat(2, minmax(0, 1fr)); } .u1s-celdas[data-impar="1"] .u1s-celda:last-child { grid-column: span 2; } }
@media (min-width: 1100px) { .u1s-celdas { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  .u1s-celdas[data-impar="1"] .u1s-celda:last-child { grid-column: auto; }
  .u1s-celdas[data-resto="3"] .u1s-celda:last-child { grid-column: span 2; } .u1s-celdas[data-resto="2"] .u1s-celda:nth-last-child(-n+2) { grid-column: span 2; } .u1s-celdas[data-resto="1"] .u1s-celda:last-child { grid-column: span 4; } }
.u1s-celda { display: flex; flex-direction: column; gap: 6px; padding: var(--e-4, 16px); border-right: 1px solid var(--borde); border-bottom: 1px solid var(--borde); margin: 0 -1px -1px 0; min-width: 0; }
.u1s-celda__cab { display: flex; align-items: center; gap: 8px; font-size: 12.5px; color: var(--txt-2); font-weight: 500; }
.u1s-celda__cab .icono { color: var(--txt-3); flex: none; }
.u1s-celda__detalle { font-size: 12.5px; color: var(--txt-2); line-height: 1.4; }
.u1s-celda .chip { align-self: flex-start; }

.u1s-duo { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: var(--e-5, 24px); align-items: stretch; }
@media (max-width: 1000px) { .u1s-duo { grid-template-columns: minmax(0, 1fr); } }
.u1s-estado { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; margin-bottom: var(--e-3, 12px); }
.u1s-estado__meta { font-size: 13px; color: var(--txt-2); }
.u1s-card p { margin: 0 0 var(--e-3, 12px); font-size: 13.5px; line-height: 1.5; color: var(--txt-2); }
.u1s-lista-ayuda { list-style: none; margin: 0 0 var(--e-4, 16px); padding: 0; display: flex; flex-direction: column; gap: 6px; font-size: 13px; color: var(--txt-2); }
.u1s-lista-ayuda li { display: flex; gap: 8px; align-items: center; }
.u1s-lista-ayuda .icono { color: var(--txt-3); flex: none; }
.u1s-pasos { list-style: decimal; margin: 0 0 var(--e-3, 12px); padding-left: 20px; display: flex; flex-direction: column; gap: 6px; font-size: 13.5px; line-height: 1.45; }
.u1s-instruccion { border: 1px solid var(--borde); border-radius: 10px; padding: var(--e-4, 16px); background: var(--sup-2); display: flex; flex-direction: column; gap: var(--e-2, 8px); }
.u1s-instruccion[data-tono="error"] { border-color: var(--error-borde); background: var(--error-bg); }
.u1s-instruccion[data-tono="aviso"] { border-color: var(--aviso-borde); background: var(--aviso-bg); }
.u1s-instruccion strong { font-size: 13.5px; }

.u1s-pf-res { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; margin-bottom: var(--e-4, 16px); font-size: 13px; color: var(--txt-2); }
.u1s-pf-bloques { display: flex; flex-direction: column; gap: var(--e-2, 8px); margin-bottom: var(--e-4, 16px); }
.u1s-bloque { border: 1px solid var(--borde); border-radius: 10px; background: var(--sup); }
.u1s-bloque > summary { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; padding: 10px 14px; cursor: pointer; list-style: none; font-weight: 600; font-size: 13.5px; }
.u1s-bloque > summary::-webkit-details-marker { display: none; }
.u1s-bloque > summary .u1s-chev { color: var(--txt-3); transition: transform .14s ease; }
.u1s-bloque[open] > summary .u1s-chev { transform: rotate(90deg); }
.u1s-bloque__cuentas { display: flex; gap: 6px; margin-left: auto; }
.u1s-items { list-style: none; margin: 0; padding: 0 14px 10px; }
.u1s-item { display: grid; grid-template-columns: 152px minmax(0, 1fr) auto; gap: 8px 12px; align-items: baseline; padding: 8px 0; border-top: 1px solid var(--borde); font-size: 13px; }
.u1s-item__id { font-family: var(--mono); font-size: 12px; color: var(--txt-2); }
.u1s-item__msg { color: var(--txt); overflow-wrap: anywhere; }
.u1s-item__msg .texto-tenue { margin-left: 8px; }
.u1s-item__meta { font-size: 12px; color: var(--txt-3); white-space: nowrap; font-variant-numeric: tabular-nums; }
@media (max-width: 700px) { .u1s-item { grid-template-columns: minmax(0, 1fr); } .u1s-item__meta { white-space: normal; } }

.u1s-consola { display: grid; grid-template-columns: minmax(260px, 0.9fr) minmax(0, 2fr); gap: var(--e-5, 24px); align-items: start; }
@media (max-width: 1000px) { .u1s-consola { grid-template-columns: minmax(0, 1fr); } }
.u1s-lista { display: flex; flex-direction: column; gap: var(--e-4, 16px); }
.u1s-grupo h3 { margin: 0 0 2px; font-size: 12px; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; color: var(--txt-3); }
.u1s-grupo > p { margin: 0 0 var(--e-2, 8px); font-size: 12.5px; color: var(--txt-3); }
.u1s-grupo__acciones { display: flex; flex-direction: column; gap: 6px; }
.u1s-accion { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 10px; align-items: start; text-align: left; width: 100%; padding: 9px 12px; border: 1px solid var(--borde); border-radius: 10px; background: var(--sup); color: var(--txt); cursor: pointer; font: inherit;
  transition: border-color .12s ease, background .12s ease; }
.u1s-accion:hover { border-color: var(--borde-fuerte); background: var(--sup-2); }
.u1s-accion:focus-visible { outline: 2px solid var(--foco); outline-offset: 2px; }
.u1s-accion[aria-pressed="true"] { border-color: var(--acento); background: var(--acento-bg); box-shadow: 0 0 0 1px var(--acento); }
.u1s-accion__titulo { font-weight: 600; font-size: 13.5px; line-height: 1.35; }
.u1s-accion__desc { grid-column: 1 / -1; font-size: 12.5px; color: var(--txt-2); line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.u1s-accion__pie { display: flex; gap: 6px; flex-wrap: wrap; grid-column: 2; grid-row: 1; justify-content: flex-end; }
.u1s-panel { display: flex; flex-direction: column; gap: var(--e-4, 16px); min-width: 0; }
.u1s-panel__cab { display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center; }
.u1s-panel__cab h3 { margin: 0; font-size: 16px; font-weight: 600; }
.u1s-panel__desc { margin: 0; color: var(--txt-2); font-size: 13.5px; line-height: 1.5; }
.u1s-form { display: flex; flex-direction: column; gap: var(--e-3, 12px); }
.u1s-form__campos { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: var(--e-3, 12px); }
.u1s-form__botones { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }
.u1s-term { border-radius: 10px; overflow: hidden; background: #070a0f; border: 1px solid #2f3b4c; color: #d4dbe6; }
.u1s-term__cab { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; padding: 8px 12px; background: #111720; border-bottom: 1px solid #2f3b4c; font-size: 12.5px; }
.u1s-term__cab .btn { background: transparent; color: #d4dbe6; border-color: #384455; }
.u1s-term__cab .btn:hover { background: #222c3a; }
.u1s-term__estado { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; color: #aeb9c8; }
.u1s-term__estado[data-clave="ok"] { color: #6fdc98; }
.u1s-term__estado[data-clave="error"] { color: #ff9c92; }
.u1s-term__estado[data-clave="aviso"] { color: #f1b95c; }
.u1s-term__estado[data-clave="corriendo"] { color: #9db8ff; }
.u1s-term__estado[data-clave="corriendo"] .icono { animation: u1s-gira 1.1s linear infinite; }
@keyframes u1s-gira { to { transform: rotate(360deg); } }
@media (prefers-reduced-motion: reduce) { .u1s-term__estado[data-clave="corriendo"] .icono { animation: none; } }
.u1s-term__job { color: #7f8b9c; font-family: var(--mono); font-size: 11.5px; }
.u1s-term__sep { flex: 1 1 auto; }
.u1s-term__salida { margin: 0; padding: 12px 14px; min-height: 140px; max-height: 360px; overflow: auto; font-family: var(--mono); font-size: 12.5px; line-height: 1.55; white-space: pre-wrap; word-break: break-word; color: #d4dbe6; background: transparent; }
.u1s-term__salida:focus-visible { outline: 2px solid var(--foco); outline-offset: -2px; }
.u1s-term__salida[data-vacia="1"] { color: #7f8b9c; }
.u1s-reglas { display: flex; gap: 8px; align-items: flex-start; font-size: 12.5px; color: var(--txt-3); margin-top: var(--e-3, 12px); }
.u1s-reglas .icono { flex: none; margin-top: 2px; }
`;

async function pedir(ctx, ruta, params) {
  const t0 = typeof performance !== 'undefined' ? performance.now() : Date.now();
  try {
    const r = await ctx.api.sobre(ruta, params);
    return { ok: true, ...r, ms: (typeof performance !== 'undefined' ? performance.now() : Date.now()) - t0 };
  } catch (err) { return { ok: false, err, datos: null, fuente: [], generado_en: null, vacio: false, avisos: [], ms: null }; }
}

async function cargarEstado(ctx) {
  const [sis, reg] = await Promise.all([pedir(ctx, '/sistema'), pedir(ctx, '/registro', { limite: 1 })]);
  return { sis, reg };
}

function vistaEstado(ctx, { sis, reg }) {
  const { el, fmt, chip, seccion, kv, vacioConPasos, errorBox, comando, fuente, icono, termino, detalleTecnico, enlace } = ctx.ui;
  const ahora = Date.now();
  if (!sis.ok) return [errorBox(sis.err, { reintentar: () => ctx.recargar() })];
  const s = sis.datos || {};
  const pausa = s.pausa || { activa: false };
  const freno = s.freno_captura || null;
  const infra = estadoInfra(s.infra, ahora);
  const cadenaOk = reg.ok && reg.datos && typeof reg.datos === 'object' ? (reg.vacio ? undefined : reg.datos.cadena_ok) : undefined;
  const botonFuente = fuente(sis.fuente, { leido: sis.generado_en });

  // ── franja de salud ──
  const elementos = elementosSalud({ sistema: s, conexion: ctx.estado.conectado, latenciaMs: sis.ms, cadenaOk, ahoraMs: ahora });
  const ver = veredictoSistema({ sistema: s, ahoraMs: ahora, cadenaOk });
  const iconoVer = { ok: 'ok', aviso: 'atencion', error: 'alerta', neutro: 'info' }[ver.tono] || 'info';
  const celda = (i) => el('div', { class: 'u1s-celda', 'data-id': i.id, 'data-tono': i.tono },
    el('div', { class: 'u1s-celda__cab' }, icono(i.icono, { tam: 16 }), i.ayuda ? termino(i.ayuda, { texto: i.titulo }) : el('span', null, i.titulo)),
    chip(i.texto, i.tono),
    el('div', { class: 'u1s-celda__detalle' }, i.detalle));
  const tecnicos = elementos.filter((i) => i.tecnico).map((i) => [i.titulo, el('code', null, i.tecnico)]);
  const salud = seccion('Salud del sistema', [
    el('div', { class: 'u1s-salud' },
      el('div', { class: 'u1s-veredicto', 'data-tono': ver.tono }, el('span', { class: 'u1s-veredicto__ic' }, icono(iconoVer, { tam: 24 })), el('div', null, el('h2', null, ver.titulo), el('p', null, ver.detalle))),
      el('div', { class: 'u1s-celdas', 'data-impar': elementos.length % 2 ? '1' : null, 'data-resto': elementos.length % 4 ? String(elementos.length % 4) : null }, elementos.map(celda))),
    tecnicos.length ? detalleTecnico('Detalle técnico de la salud', kv(tecnicos)) : null,
  ], { acciones: [botonFuente] });

  // ── PAUSA ──
  const ip = instruccionPausa(pausa);
  const bloquePausa = seccion('Pausa general (freno de emergencia)', el('div', { class: 'u1s-card' },
    el('div', { class: 'u1s-estado' },
      chip(pausa.activa ? 'ACTIVA' : 'Sin pausa', pausa.activa ? 'error' : 'ok'),
      pausa.activa ? el('span', { class: 'u1s-estado__meta', title: fmt.fecha(pausa.desde) }, `desde ${fmt.relativo(pausa.desde, ahora)}${pausa.motivo ? ` · ${pausa.motivo}` : ''}`) : null),
    pausa.activa
      ? el('div', { class: 'u1s-instruccion', 'data-tono': 'error' }, el('strong', null, ip.titulo), el('ol', { class: 'u1s-pasos' }, ip.pasos.map((p) => el('li', null, p))),
        comando(ip.comando, { titulo: 'Cómo levantarla' }), el('span', { class: 'texto-tenue' }, 'No hay botón de borrado a propósito: levantar la pausa es una decisión humana.'))
      : [el('p', null, 'Con la pausa puesta, el sistema deja de gastar y de activar cualquier cosa hasta que una persona la levante a mano. Úsala si algo no te cuadra.'),
        el('ul', { class: 'u1s-lista-ayuda' }, ['El gasto en anuncios y las subidas de presupuesto', 'La activación de campañas nuevas', 'Cualquier acción del sistema que mueva dinero'].map((t) => el('li', null, icono('pausa', { tam: 13 }), t))),
        el('button', { type: 'button', class: 'btn btn--peligro-suave', onclick: () => ctx.pausarTodo() }, icono('pausa', { tam: 14 }), 'Pausar todo')],
    detalleTecnico('Detalle técnico', kv([['Archivo', el('code', null, 'empresa/PAUSA')]]))),
  { glosario: 'pausa' });

  // ── Freno ──
  const ifr = instruccionFreno(freno);
  const bloqueFreno = seccion('Freno de la captura de anuncios', el('div', { class: 'u1s-card' },
    el('div', { class: 'u1s-estado' },
      chip(freno && freno.activo ? 'PUESTO' : 'Libre', freno && freno.activo ? 'aviso' : 'ok'),
      freno && freno.activo ? el('span', { class: 'u1s-estado__meta', title: fmt.fecha(freno.ts) }, `desde ${fmt.relativo(freno.ts, ahora)}${freno.motivo ? ` · Meta respondió «${freno.motivo}»` : ''}`) : null),
    freno && freno.activo
      ? el('div', { class: 'u1s-instruccion', 'data-tono': 'aviso' }, el('strong', null, ifr.titulo), el('ol', { class: 'u1s-pasos' }, ifr.pasos.map((p) => el('li', null, p))),
        comando(ifr.comandoLeer, { titulo: 'Leer el motivo' }), comando(ifr.comando, { titulo: 'Levantarlo (solo tú, si procede)' }),
        el('span', { class: 'texto-tenue' }, 'El panel no tiene botón para esto ni lo tendrá: si Meta pide un captcha o pone un límite, la captura no se reintenta ni se esquiva.'))
      : el('p', null, 'La captura de anuncios (de la Biblioteca de Anuncios de Meta) puede correr. Si Meta pide un captcha, pone un límite o exige iniciar sesión, el sistema pone el freno y se detiene solo.'),
    detalleTecnico('Detalle técnico', kv([['Archivo', el('code', null, 'empresa/captura/freno.json')]]))),
  { glosario: 'freno_captura' });

  // ── Infraestructura y preflight ──
  const sem = s.infra ? String(s.infra.semaforo || '').toUpperCase() : null;
  const pf = agruparPreflight(s.infra, ahora);
  const itemPf = (i) => el('li', { class: 'u1s-item', 'data-tono': i.tono },
    el('span', null, chip(i.etiqueta, i.tono, { icono: i.icono })),
    el('div', { class: 'u1s-item__msg' }, el('span', { class: 'u1s-item__id' }, i.id), i.critico ? [' ', chip('crítico', 'neutro', { icono: false })] : null, i.mensaje ? el('span', { class: 'texto-tenue' }, i.mensaje) : null),
    el('span', { class: 'u1s-item__meta', title: i.medidoEn ? fmt.fecha(i.medidoEn, { segundos: true }) : null },
      [i.latenciaMs !== null ? `${Math.round(i.latenciaMs)} ms` : null, i.vencido ? 'vencido' : (i.medidoEn ? `medido ${fmt.relativo(i.medidoEn, ahora)}` : null)].filter(Boolean).join(' · ')));
  const bloquePf = (b) => {
    const det = el('details', { class: 'u1s-bloque', 'data-tono': b.tono },
      el('summary', null, icono('flecha', { tam: 14, clase: 'u1s-chev' }), el('span', null, b.nombre),
        el('span', { class: 'u1s-bloque__cuentas' },
          b.conteos.error ? chip(`${b.conteos.error} en rojo`, 'error') : null, b.conteos.aviso ? chip(`${b.conteos.aviso} en amarillo`, 'aviso') : null,
          b.conteos.neutro ? chip(`${b.conteos.neutro} pendiente${b.conteos.neutro === 1 ? '' : 's'}`, 'neutro', { icono: 'reloj' }) : null, b.conteos.ok ? chip(`${b.conteos.ok} en verde`, 'ok') : null)),
      el('ul', { class: 'u1s-items' }, b.items.map(itemPf)));
    if (b.tono !== 'ok') det.open = true;
    return det;
  };
  const cuerpoInfra = !s.infra
    ? vacioConPasos({
      titulo: 'Todavía no se hizo el chequeo de cuentas y servicios',
      explicacion: 'Hasta que el chequeo salga en verde, esté al día (menos de 6 horas) y se haya hecho en modo real, nadie gasta ni activa. Lo hace el chequeo antes de lanzar.',
      pasos: [{ texto: 'Haz el chequeo completo:', comando: COMANDO_PREFLIGHT }, { texto: 'Revisa que tus límites estén fijados en Límites y reglas.' }], icono: 'servidor',
    })
    : [
      el('div', { class: 'u1s-pf-res' },
        chip({ VERDE: 'Verde', AMARILLO: 'Amarillo', ROJO: 'Rojo' }[sem] || 'Sin semáforo', infra.tono),
        s.infra.modo ? chip(s.infra.modo === 'vivo' ? 'Hecho en modo real' : `Modo ${s.infra.modo}`, s.infra.modo === 'vivo' ? 'ok' : 'aviso') : null,
        chip(infra.detalle === 'vigente' ? 'Chequeo al día' : infra.detalle.charAt(0).toUpperCase() + infra.detalle.slice(1), infra.detalle === 'vigente' ? 'ok' : 'aviso'),
        s.infra.generado_en ? el('span', { title: fmt.fecha(s.infra.generado_en, { segundos: true }) }, `medido ${fmt.relativo(s.infra.generado_en, ahora)}`) : null,
        s.infra.valido_hasta ? el('span', null, `válido hasta ${fmt.fecha(s.infra.valido_hasta)}`) : null,
        pf.hay ? el('span', null, `${pf.conteos.ok} de ${pf.total} ítems en verde${pf.criticosRojos ? ` · ${pf.criticosRojos} crítico${pf.criticosRojos === 1 ? '' : 's'} en rojo` : ''}`) : null),
      pf.hay ? el('div', { class: 'u1s-pf-bloques' }, pf.bloques.map(bloquePf))
        : el('p', { class: 'texto-tenue' }, 'Por ahora el panel recibe solo el resultado general (el semáforo); el detalle de cada servicio (Meta, Stripe, Cloudflare, Railway, GitHub, correo) se verá aquí cuando esté disponible.'),
      comando(COMANDO_PREFLIGHT, { titulo: 'Cómo repetir el chequeo' }),
      el('p', { class: 'texto-tenue', style: { margin: '12px 0 0' } }, 'Los límites firmados y las cuentas operativas se administran en ', enlace('Límites y reglas', '#/parametros'), '.'),
    ];
  const bloqueInfra = seccion('Cuentas y servicios: chequeo antes de lanzar', cuerpoInfra, { glosario: 'preflight_infra' });

  return [salud, el('div', { class: 'u1s-duo' }, bloquePausa, bloqueFreno), bloqueInfra];
}

// ───────────────────────── consola de acciones ─────────────────────────

function consola(ctx, rAcc) {
  const { el, chip, seccion, vacio, vacioConPasos, errorBox, copiar, toast, confirmar, fuente, icono, reemplazar, comando } = ctx.ui;
  if (!rAcc.ok) return seccion('Tareas que puedes ejecutar desde aquí', errorBox(rAcc.err, { reintentar: () => ctx.recargar() }), { glosario: 'consola_acciones' });
  const acciones = normalizarAcciones(rAcc.datos);
  const botonFuente = fuente(rAcc.fuente && rAcc.fuente.length ? rAcc.fuente : ['dashboard/acciones.yaml'], { leido: rAcc.generado_en });
  const reglas = el('p', { class: 'u1s-reglas' }, icono('escudo', { tam: 14 }), 'Lista cerrada de tareas seguras: solo miran o guardan archivos en este equipo. Ninguna activa, publica, gasta, firma ni borra la pausa o el freno, y no aceptan texto libre.');
  if (acciones.length === 0) {
    return seccion('Tareas que puedes ejecutar desde aquí', [vacioConPasos({
      titulo: 'La lista de tareas todavía no está disponible', explicacion: 'Si la lista no existe o está vacía, no hay nada que ejecutar desde aquí.', pasos: [{ texto: 'Revisa que el panel se haya abierto completo y recarga esta pantalla.' }], icono: 'terminal',
    }), reglas], { acciones: [botonFuente], glosario: 'consola_acciones' });
  }

  const detalle = el('div', { class: 'u1s-panel' });
  const salidaEl = el('pre', { class: 'u1s-term__salida', role: 'log', 'aria-live': 'off', tabindex: '0', 'aria-label': 'Resultado de la tarea' });
  const estadoEl = el('span', { class: 'u1s-term__estado' });
  const jobEl = el('span', { class: 'u1s-term__job' });
  let temporizador = null;
  let fallos = 0;
  let activo = true;
  ctx.alSalir(() => { activo = false; clearTimeout(temporizador); });

  const botones = new Map();
  const lista = el('div', { class: 'u1s-lista', role: 'group', 'aria-label': 'Tareas disponibles' });
  for (const g of agruparAcciones(acciones)) {
    const cont = el('div', { class: 'u1s-grupo__acciones' });
    for (const a of g.acciones) {
      const b = el('button', { type: 'button', class: 'u1s-accion', 'aria-pressed': 'false', onclick: () => seleccionar(a.id) },
        el('span', { class: 'u1s-accion__titulo' }, a.tituloCorto),
        el('span', { class: 'u1s-accion__desc' }, a.descripcion || a.id),
        el('span', { class: 'u1s-accion__pie' }, a.proximamente ? chip('próximamente', 'neutro', { icono: 'reloj' }) : chip(rotuloRiesgo(a.riesgo), tonoRiesgo(a.riesgo), { icono: iconoRiesgo(a.riesgo) })));
      botones.set(a.id, b);
      cont.appendChild(b);
    }
    lista.appendChild(el('div', { class: 'u1s-grupo' }, el('h3', null, g.titulo), g.descripcion ? el('p', null, g.descripcion) : null, cont));
  }

  function pintarEstadoJob() {
    const v = veredictoJob({ terminado: sesion.terminado, codigo: sesion.codigo, estadoServidor: sesion.estadoServidor });
    estadoEl.setAttribute('data-clave', sesion.jobId ? v.clave : 'neutro');
    reemplazar(estadoEl, icono(sesion.jobId ? v.icono : 'terminal', { tam: 14 }), sesion.jobId ? v.texto : 'Sin ejecutar todavía');
    reemplazar(jobEl, sesion.jobId ? `Tarea ${sesion.jobId}` : '');
  }

  function pintarSalida() {
    const hay = Boolean(sesion.texto);
    salidaEl.setAttribute('data-vacia', hay ? '0' : '1');
    salidaEl.textContent = sesion.texto || (sesion.jobId ? '' : 'El resultado de la tarea aparecerá aquí, en vivo.');
  }

  function anexar(texto) {
    if (!texto) return;
    const cerca = salidaEl.scrollHeight - salidaEl.scrollTop - salidaEl.clientHeight < 40;
    sesion.texto += texto;
    if (sesion.texto.length > MAX_SALIDA) sesion.texto = '… (salida anterior recortada)\n' + sesion.texto.slice(-MAX_SALIDA);
    salidaEl.setAttribute('data-vacia', '0');
    salidaEl.textContent = sesion.texto;
    if (cerca) salidaEl.scrollTop = salidaEl.scrollHeight;
  }

  async function sondear() {
    if (!activo || !sesion.jobId || sesion.terminado) return;
    try {
      const d = await ctx.api.get(`/job/${encodeURIComponent(sesion.jobId)}`, { desde: sesion.desde });
      fallos = 0;
      const j = normalizarJob(d, sesion.desde);
      anexar(j.texto);
      sesion.desde = j.siguiente;
      if (j.terminado) { sesion.terminado = true; sesion.codigo = j.codigo; sesion.estado = j.estado; sesion.estadoServidor = j.estadoServidor; }
      if (j.truncado && !sesion.truncado) { sesion.truncado = true; }
    } catch (err) {
      fallos += 1;
      if (fallos >= MAX_FALLOS_JOB) { sesion.terminado = true; sesion.codigo = null; anexar(`\n[el panel perdió el seguimiento de la tarea: ${err.mensaje || err.message}]\n`); }
    }
    pintarEstadoJob();
    if (!sesion.terminado && activo) temporizador = setTimeout(sondear, INTERVALO_JOB_MS);
    else pintarDetalle();
  }

  async function ejecutar(accion, form) {
    if (accion.proximamente) { toast(accion.motivo || 'Esa tarea aún no está disponible.', 'aviso'); return; }
    const r = validarArgs(accion.parametros, sesion.valores[accion.id] || {});
    reemplazar(form.errores, []);
    if (!r.ok) {
      for (const [k, m] of Object.entries(r.errores)) { const nodo = form.errorDe.get(k); if (nodo) { nodo.textContent = m; nodo.hidden = false; } }
      toast('Revisa los campos marcados.', 'aviso');
      return;
    }
    if (accion.riesgo && accion.riesgo !== 'lectura') {
      const ok = await confirmar({ titulo: `Ejecutar «${accion.titulo}»`, mensaje: 'Esta tarea guarda archivos en este equipo (nunca en producción). ¿Seguro?', textoOk: 'Ejecutar' });
      if (!ok) return;
    }
    try {
      const d = await ctx.api.post('/accion', { id: accion.id, args: r.args });
      const id = d && (d.job_id || d.id);
      if (!id) throw new Error('El servidor no confirmó que la tarea empezó.');
      Object.assign(sesion, { jobId: String(id), desde: 0, texto: d.comando ? `$ ${d.comando}\n` : '', terminado: false, codigo: null, estado: 'corriendo', estadoServidor: null });
      fallos = 0;
      pintarSalida(); pintarEstadoJob(); pintarDetalle();
      clearTimeout(temporizador);
      temporizador = setTimeout(sondear, 250);
    } catch (err) {
      toast(`No se pudo ejecutar: ${err.mensaje || err.message}`, 'error');
      const enCurso = err && err.sobre && err.sobre.error && typeof err.sobre.error.job_id === 'string' ? err.sobre.error.job_id : null;
      if (err && err.codigo === 'accion_en_curso' && enCurso) { Object.assign(sesion, { jobId: enCurso, desde: 0, texto: '', terminado: false, codigo: null }); fallos = 0; pintarSalida(); pintarEstadoJob(); pintarDetalle(); clearTimeout(temporizador); temporizador = setTimeout(sondear, 200); }
    }
  }

  function campo(accion, p, errorDe) {
    const valor = sesion.valores[accion.id] && sesion.valores[accion.id][p.nombre] !== undefined ? sesion.valores[accion.id][p.nombre] : (p.porDefecto ?? '');
    const poner = (v) => { (sesion.valores[accion.id] ||= {})[p.nombre] = v; };
    poner(valor);
    let control;
    if (p.tipo === 'eleccion') {
      control = el('select', { class: 'campo', onchange: (e) => poner(e.target.value) }, el('option', { value: '' }, '— elige —'), (p.opciones || []).map((o) => el('option', { value: o }, o)));
      control.value = String(valor);
    } else if (p.tipo === 'oferta') {
      const ids = (ctx.estado.ofertas || []).map((o) => o.oferta_id).filter(Boolean);
      control = ids.length
        ? el('select', { class: 'campo', onchange: (e) => poner(e.target.value) }, el('option', { value: '' }, '— elige una oferta —'), ids.map((i) => el('option', { value: i }, i)))
        : el('input', { class: 'campo', type: 'text', placeholder: 'OF-AAAAMM-NN', maxlength: '40', oninput: (e) => poner(e.target.value) });
      control.value = String(valor || ctx.estado.ofertaActiva || '');
      if (!valor && ctx.estado.ofertaActiva) poner(ctx.estado.ofertaActiva);
    } else if (p.tipo === 'bandera') {
      control = el('input', { type: 'checkbox', onchange: (e) => poner(e.target.checked) });
      control.checked = valor === true;
    } else if (p.tipo === 'entero') {
      control = el('input', { class: 'campo', type: 'number', min: p.minimo ?? null, max: p.maximo ?? null, step: '1', oninput: (e) => poner(e.target.value) });
      control.value = String(valor);
    } else {
      control = el('input', { class: 'campo', type: 'text', maxlength: '200', placeholder: p.tipo === 'corrida' ? '2026-11-06-a' : null, oninput: (e) => poner(e.target.value) });
      control.value = String(valor);
    }
    const err = el('span', { class: 'campo-error', role: 'alert', hidden: true });
    errorDe.set(p.nombre, err);
    const etiqueta = etiquetaParametro(p);
    return el('label', { class: ['etiqueta-campo', p.tipo === 'bandera' && 'etiqueta-campo--check'] }, etiqueta, control, p.descripcion ? el('span', { class: 'texto-tenue campo-ayuda' }, p.flag && p.tipo === 'bandera' ? `${p.descripcion} (${p.flag})` : p.descripcion) : null, err);
  }

  function pintarDetalle() {
    const a = acciones.find((x) => x.id === sesion.accionId);
    for (const [id, b] of botones) b.setAttribute('aria-pressed', String(id === sesion.accionId));
    if (!a) {
      reemplazar(detalle, vacioConPasos({
        titulo: 'Elige una tarea', explicacion: 'Cada tarea se ejecuta con datos fijos y revisados; el resultado llega en vivo. Las que solo miran no cambian nada.',
        pasos: [{ texto: 'Elige una tarea de la lista.' }, { texto: 'Completa los datos que pida (si hace falta) y pulsa Ejecutar.' }, { texto: 'Mira el resultado en el panel de abajo; puedes copiarlo.' }], icono: 'terminal',
      }));
      return;
    }
    const errorDe = new Map();
    const form = { errores: el('div'), errorDe };
    const corriendo = Boolean(sesion.jobId && !sesion.terminado);
    reemplazar(detalle,
      el('div', { class: 'u1s-panel__cab' }, el('h3', null, a.titulo), chip(rotuloRiesgo(a.riesgo), tonoRiesgo(a.riesgo), { icono: iconoRiesgo(a.riesgo) })),
      el('p', { class: 'u1s-panel__desc' }, a.descripcion || '', ' ', el('span', { class: 'texto-tenue' }, explicacionRiesgo(a.riesgo))),
      a.proximamente ? el('div', { class: 'u1s-instruccion', 'data-tono': 'aviso' }, el('strong', null, 'Esta tarea aún no está disponible'), el('span', null, a.motivo || 'Todavía no se puede ejecutar desde el panel.')) : null,
      a.comando ? comando(a.comando, { titulo: 'Qué se ejecuta por dentro (comando exacto)', nota: `Con datos fijos${a.timeoutS ? `; se corta a los ${a.timeoutS} segundos` : ''}. Nombre en la lista técnica: «${a.tituloOriginal}» (${a.id}).` }) : null,
      el('form', { class: 'u1s-form', onsubmit: (e) => { e.preventDefault(); ejecutar(a, form); }, novalidate: true },
        a.parametros.length ? el('div', { class: 'u1s-form__campos' }, a.parametros.map((p) => campo(a, p, errorDe))) : null,
        el('div', { class: 'u1s-form__botones' },
          el('button', { type: 'submit', class: 'btn btn--primario', disabled: corriendo || a.proximamente ? true : null }, icono('play', { tam: 13 }), corriendo ? 'Ejecutando…' : 'Ejecutar')),
        form.errores),
      el('div', { class: 'u1s-term' },
        el('div', { class: 'u1s-term__cab' }, estadoEl, jobEl, el('span', { class: 'u1s-term__sep' }),
          el('button', { type: 'button', class: 'btn btn--chico', onclick: () => copiar(sesion.texto || '') }, icono('copiar', { tam: 13 }), 'Copiar resultado'),
          el('button', { type: 'button', class: 'btn btn--chico', disabled: corriendo ? true : null, onclick: () => { Object.assign(sesion, { jobId: null, texto: '', terminado: true, codigo: null, desde: 0 }); pintarSalida(); pintarEstadoJob(); } }, 'Limpiar')),
        salidaEl));
  }

  function seleccionar(id) {
    if (sesion.accionId !== id && sesion.terminado) Object.assign(sesion, { jobId: null, texto: '', codigo: null, desde: 0 });
    sesion.accionId = id;
    pintarDetalle(); pintarSalida(); pintarEstadoJob();
    if (typeof window !== 'undefined' && window.innerWidth < 1000 && typeof detalle.scrollIntoView === 'function') detalle.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  if (!acciones.some((a) => a.id === sesion.accionId)) sesion.accionId = null;
  // un job de esta acción ya corre en el servidor (p. ej. tras recargar la página): seguirlo
  const viva = acciones.find((a) => a.enCurso && a.id === sesion.accionId) || acciones.find((a) => a.enCurso);
  if (viva && (!sesion.jobId || sesion.terminado)) Object.assign(sesion, { accionId: viva.id, jobId: viva.enCurso, desde: 0, texto: '', terminado: false, codigo: null });
  pintarDetalle(); pintarSalida(); pintarEstadoJob();
  if (sesion.jobId && !sesion.terminado) temporizador = setTimeout(sondear, 200); // retoma el seguimiento tras volver a la pantalla

  return seccion('Tareas que puedes ejecutar desde aquí', [el('div', { class: 'u1s-consola' }, lista, detalle), reglas], { acciones: [botonFuente], glosario: 'consola_acciones' });
}

export async function render(ctx) {
  const { el, encabezadoPagina, icono } = ctx.ui;
  ctx.ui.instalarEstilos('u1-sistema', CSS);
  const [est, rAcc] = await Promise.all([cargarEstado(ctx), pedir(ctx, '/acciones')]);
  const contenedor = el('div', { class: 'pila' });
  ctx.ui.reemplazar(contenedor, vistaEstado(ctx, est));
  ctx._sistema = { contenedor };
  return el('div', { class: 'pagina' },
    encabezadoPagina({
      titulo: 'Salud del sistema',
      descripcion: 'Si todo funciona bien: la pausa general, el freno de la captura de anuncios, las cuentas y servicios, y una lista de tareas seguras que puedes ejecutar desde aquí.',
      acciones: [el('button', { type: 'button', class: 'btn', onclick: () => ctx.recargar() }, icono('refrescar', { tam: 14 }), 'Actualizar')],
    }),
    contenedor,
    consola(ctx, rAcc),
  );
}

export async function alCambio(ctx) {
  if (!ctx._sistema) return;
  const est = await cargarEstado(ctx);
  ctx.ui.reemplazar(ctx._sistema.contenedor, vistaEstado(ctx, est));
}
