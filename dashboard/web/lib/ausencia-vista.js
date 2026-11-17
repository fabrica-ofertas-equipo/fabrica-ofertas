// lib/ausencia-vista.js — constructores de DOM de «¿Me puedo ausentar?» (Resumen) y del informe de las 08:30 (Avisos). Todo texto entra por ui.el (textContent):
// nunca como HTML interpretado, porque lo que viene de los archivos es dato no confiable. SOLO LECTURA: ningún botón firma, activa, gasta, envía ni borra la PAUSA o el freno;
// los comandos se muestran copiables (ui.comando) para que los ejecute una persona.

import { ui, el, icono } from '../ui.js';
import { CSS_AUSENCIA } from './estilos-ausencia.js';
import { NIVELES, COMANDO_ALERTAS, COMANDO_INFORME } from './ausencia.js';

/** Instala la hoja `au-` (una vez). */
export const instalar = () => ui.instalarEstilos('au-ausencia', CSS_AUSENCIA);

const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`;

/** Las tres luces del semáforo: solo la del nivel actual está encendida, con su icono (el color no va solo). */
export function luces(nivel) {
  const info = NIVELES[nivel] || NIVELES.rojo;
  return el('div', { class: 'au-luces', role: 'img', 'aria-label': `Semáforo en ${info.etiqueta.toLowerCase()}` },
    ['rojo', 'amarillo', 'verde'].map((n) => el('span', { class: 'au-luz', 'data-nivel': n, 'data-encendida': n === nivel ? '1' : '0' }, icono(NIVELES[n].icono, { tam: 22 }))));
}

/** El chip «Tú» / «Equipo técnico (S-B)»: a quién le toca. */
export function chipQuien(quien) {
  if (!quien) return null;
  return ui.chip(quien.corto, quien.clave === 'dueno' ? 'acento' : 'neutro', { icono: quien.clave === 'dueno' ? 'usuario' : 'engranaje' });
}

/** Un paso de «Qué falta, en orden»: número, color con palabra, título, estado, qué hacer, a quién le toca, enlace a su pantalla y comando copiable. */
export function filaPaso(p) {
  return el('li', { class: 'au-paso', 'data-nivel': p.nivel, 'data-paso': p.id },
    el('span', { class: 'au-paso__n', 'aria-hidden': 'true' }, p.paso === null ? '•' : String(p.paso)),
    el('div', { class: 'au-paso__cuerpo' },
      el('div', { class: 'au-paso__cab' },
        ui.chip(p.info.etiqueta, p.info.tono, { icono: p.info.icono }),
        el('h4', { class: 'au-paso__titulo' }, p.titulo),
        chipQuien(p.quien)),
      p.estado ? el('p', { class: 'au-paso__estado' }, p.estado) : null,
      p.queHacer ? el('p', { class: 'au-paso__hacer' }, el('strong', null, 'Qué hacer: '), p.queHacer) : null,
      p.nota ? el('p', { class: 'au-paso__nota' }, p.nota) : null,
      p.enlace || p.comando ? el('div', { class: 'au-paso__acciones' },
        p.enlace ? ui.enlace(`Ir a ${p.enlaceTexto}`, p.enlace, { class: 'btn btn--chico' }) : null,
        p.comando ? ui.comando(p.comando, { titulo: 'Cómo hacerlo', nota: 'Lo ejecutas tú en la Terminal: este panel no lo hace por ti.' }) : null) : null));
}

/** El bloque completo «¿Me puedo ausentar?» a partir de `modeloSemaforo(...)`. `ahoraMs` para decir «hace X». */
export function bloqueSemaforo(m, { ahoraMs = Date.now(), fuenteLeida = null } = {}) {
  const cuerpo = el('div', { class: 'au-cuerpo' },
    el('div', { class: 'au-bloque', 'data-nivel': m.nivel },
      luces(m.nivel),
      el('div', { class: 'au-cabeza' },
        el('p', { class: 'au-sobre' }, 'Hoy, con lo que hay en tus archivos'),
        el('p', { class: 'au-veredicto', role: 'status' }, m.titulo),
        el('p', { class: 'au-resumen' }, m.resumen),
        el('div', { class: 'au-cuentas' },
          ui.chip(plural(m.conteos.rojo, 'cosa en rojo', 'cosas en rojo'), m.conteos.rojo ? 'error' : 'neutro', { icono: 'octogono' }),
          ui.chip(plural(m.conteos.amarillo, 'cosa en amarillo', 'cosas en amarillo'), m.conteos.amarillo ? 'aviso' : 'neutro', { icono: 'alerta' }),
          ui.chip(plural(m.conteos.verde, 'cosa en orden', 'cosas en orden'), m.conteos.verde ? 'ok' : 'neutro', { icono: 'ok' }),
          m.paraTi ? ui.chip(`${m.paraTi} te ${m.paraTi === 1 ? 'toca' : 'tocan'} a ti`, 'acento', { icono: 'usuario' }) : null))),
    el('h3', { class: 'au-lista-titulo' }, m.pasos.length ? `Qué falta, en orden (${m.pasos.length}) y ` : 'Qué falta y ', ui.termino('a_quien_le_toca', { texto: 'a quién le toca' })),
    m.pasos.length
      ? el('ol', { class: 'au-pasos', 'aria-label': 'Lo que falta, en orden' }, m.pasos.map(filaPaso))
      : ui.vacio('No falta nada: todo lo que protege tu dinero, te avisa y hace funcionar el sistema solo está en orden.', { icono: 'ok' }),
    m.listos.length ? el('details', { class: 'au-listos' },
      el('summary', null, `Lo que ya está en orden (${m.listos.length})`),
      el('ul', null, m.listos.map((p) => el('li', null, ui.chip(p.info.etiqueta, p.info.tono, { icono: p.info.icono }), el('span', null, `${p.titulo}: ${p.estado}`), p.nota ? el('span', { class: 'au-paso__nota' }, `Ojo: ${p.nota}`) : null)))) : null,
    el('p', { class: 'au-pie' },
      `Se calcula leyendo los archivos del proyecto${m.calculadoEn ? ` (${ui.fmt.relativo(m.calculadoEn, ahoraMs)})` : ''}; no cambia nada. `, m.comoSeCalcula),
    el('p', { class: 'au-pie' }, 'Para verlo en la Terminal: ', el('code', null, COMANDO_ALERTAS)));
  return ui.seccion('¿Me puedo ausentar?', cuerpo, {
    glosario: 'semaforo_ausencia', id: 'au-ausentar',
    acciones: [ui.enlace('Ver las alertas', '#/avisos', { class: 'btn btn--chico' }), fuenteLeida].filter(Boolean),
  });
}

/** Cuando no se pudo calcular (la API falló): un aviso honesto, nunca un semáforo inventado. */
export function bloqueSemaforoNoDisponible(err, reintentar) {
  return ui.seccion('¿Me puedo ausentar?', err ? ui.errorBox(err, { reintentar }) : ui.vacio('Todavía no se puede calcular si te puedes ausentar.', { icono: 'info' }), { glosario: 'semaforo_ausencia', id: 'au-ausentar' });
}

// ───────────────────────── informe de las 08:30 ─────────────────────────

/** Estado de una sección o de un «cero»: icono + palabra. */
const estadoInfo = (info) => ui.chip(info.texto, info.tono, { icono: info.icono });

/**
 * El informe del día con sus dos versiones (pestañas Correo / Celular), los 5 avisos, los ceros y lo que te toca. `modelo` = modeloInforme(...).
 * El texto de las versiones se muestra tal cual en un <pre>: es lo que S-B enviaría cuando haya canal. El panel no envía nada.
 */
export function cuerpoInforme(modelo, { ahoraMs = Date.now() } = {}) {
  const pre = el('pre', { class: 'au-texto', tabindex: '0', 'aria-label': 'Texto del informe' });
  const asunto = el('p', { class: 'n1-nota' });
  const pintar = (id) => {
    const v = modelo.versiones[id === 'celular' ? 'celular' : 'correo'];
    pre.textContent = v.texto;
    ui.reemplazar(asunto, id === 'celular'
      ? [el('strong', null, 'Al celular: '), 'solo porcentajes y recuentos, ninguna cifra de dinero.']
      : [el('strong', null, 'Asunto: '), v.asunto, ' · ', el('strong', null, 'Por correo: '), 'con los importes y el detalle.']);
  };
  pintar('correo');
  const pestanas = ui.barraPestanas({ items: [{ id: 'correo', titulo: 'Versión para el correo' }, { id: 'celular', titulo: 'Versión para el celular' }], activo: 'correo', onCambio: pintar, etiqueta: 'Versión del informe' });
  return el('div', { class: 'au-informe' },
    el('div', { class: 'n1-fila' },
      modelo.semaforo ? ui.chip(`${modelo.semaforo.info.etiqueta}: ${modelo.semaforo.titulo}`, modelo.semaforo.info.tono, { icono: modelo.semaforo.info.icono }) : null,
      el('span', { class: 'n1-nota' }, `Informe del ${modelo.fecha ? modelo.fecha.split('-').reverse().join('/') : '—'} (se enviaría a las ${modelo.hora || '08:30'}) · ventas y gasto del ${modelo.diaMedido ? modelo.diaMedido.split('-').reverse().join('/') : '—'}`),
      modelo.generadoEn ? el('span', { class: 'n1-nota' }, `· compuesto ${ui.fmt.relativo(modelo.generadoEn, ahoraMs)}`) : null),
    el('div', { class: 'n1-aviso n1-aviso--info' }, icono('info', { tam: 18 }),
      el('div', null, el('strong', null, 'Todavía no se envía nada. '), 'El informe ya se arma solo con los archivos del proyecto, con una forma fija y sin texto libre. El envío lo hace el equipo técnico (S-B) cuando elijas el canal de avisos.')),
    pestanas, asunto, pre,
    el('div', null,
      el('h3', { class: 'n1-subtitulo' }, 'Los 5 avisos del informe'),
      el('ul', { class: 'au-secciones' }, modelo.avisos.map((a) => el('li', { class: 'au-seccion', 'data-aviso': a.id },
        el('div', { class: 'n1-fila' }, el('strong', null, a.titulo), estadoInfo(a.info)),
        a.lineas.length ? el('ul', null, a.lineas.map((x) => el('li', null, x))) : null)))),
    el('div', null,
      el('h3', { class: 'n1-subtitulo' }, ui.termino('los_ceros', { texto: 'Los ceros que importan (la meta es 0)' })),
      el('ul', { class: 'au-ceros' }, modelo.ceros.map((c) => el('li', { class: 'au-cero', 'data-cero': c.id, 'data-estado': c.estado },
        el('span', { class: 'au-cero__valor' }, c.valor === null ? '—' : String(c.valor)),
        el('div', null, el('div', { class: 'n1-fila' }, el('strong', null, c.texto), estadoInfo(c.info)), el('p', null, c.detalle)))))),
    el('div', null,
      el('h3', { class: 'n1-subtitulo' }, `Lo que te toca a ti (${modelo.teToca.length})`),
      modelo.teToca.length
        ? el('ul', { class: 'au-pendientes' }, modelo.teToca.slice(0, 12).map((t) => el('li', null,
          el('b', null, t.tipo === 'pendiente' ? `${t.prioridad || ''} ${t.id || ''} · ${t.titulo}`.trim() : t.titulo),
          t.queHacer ? el('span', null, t.queHacer) : null,
          t.enlace ? ui.enlace(`Ir a ${t.enlaceTexto}`, t.enlace) : null)))
        : ui.vacio('No te toca nada ahora.', { icono: 'ok' })),
    modelo.sinDatos.length ? el('div', null,
      el('h3', { class: 'n1-subtitulo' }, 'Lo que todavía no se puede medir'),
      el('ul', { class: 'n1-lista' }, modelo.sinDatos.map((x) => el('li', { class: 'n1-nota' }, x)))) : null,
    ui.comando(COMANDO_INFORME, { titulo: 'Cómo componerlo en la Terminal', nota: 'Solo lo muestra en pantalla: no envía nada.' }));
}
