// pages/robots.js — #/robots: «Los robots: qué corre y cuándo». Dos capas: (1) el catálogo de los 10 robots tal como los define el plan (qué hacen, su horario, si hay
// código), con una línea de tiempo de 24 h y la semana tipo; (2) el registro real (empresa/robots.yaml) cuando exista, tolerando campos que falten.
// Más el principio «todo robot se audita» y las seis reglas de oro. Y los robots EN SOMBRA (solo lectura; empresa/robots/estado.json vía GET /robots/sombra): una insignia por robot
// («En sombra hoy» · «Sin versión en sombra» · «Solo S-B»), su última señal de vida y el resultado de su última corrida. En sombra NO es el sistema real. SOLO LECTURA: ningún botón
// enciende, apaga, programa ni cambia un robot; los comandos se muestran copiables.
// Lo técnico (acción, gate, topes, ítems del preflight, rutas) va en «Detalle técnico». La lógica pura vive en ../lib/robots.js.

import { ui, el, icono, fmt } from '../ui.js';
import { CSS_COMUN, CSS_ROBOTS } from '../lib/estilos-n1.js';
import { CSS_SOMBRA } from '../lib/estilos-sombra.js';
import * as L from '../lib/robots.js';

export const meta = { ruta: 'robots', titulo: 'Robots', grupo: 'Robots', icono: 'rayo', escucha: ['empresa'] };

const RUTAS_FUENTE = ['empresa/robots.yaml', 'empresa/parametros.yaml', 'empresa/infra/estado.json', 'empresa/robots/estado.json'];
const ICONO_CODIGO = { no_construido: 'circulo-punteado', parcial: 'progreso', planeado: 'reloj' };
const ROTULO_ESTADO = { vivo: 'Vivo', sombra: 'En sombra', apagado: 'Apagado' };
const TONO_ESTADO = { vivo: 'ok', sombra: 'info', apagado: 'neutro' };
const ICONO_ESTADO = { vivo: 'play', sombra: 'ojo', apagado: 'pausa' };

// Pestaña que sobrevive a las actualizaciones en vivo (la URL puede fijarla con ?vista=registro).
let vista = 'plan';

/** Cabecera de pantalla con la rejilla contenida (en móvil, la lista de pestañas no ensancha la página). */
function cabecera(opciones) {
  const c = ui.encabezadoPagina(opciones);
  c.classList.add('n1-cab');
  return c;
}

async function leer(ctx, ruta) {
  try { return { ok: true, sobre: await ctx.api.sobre(ruta) }; } catch (err) { return { ok: false, err, sobre: null }; }
}

// ───────────────────────── piezas ─────────────────────────

function chipCodigo(est) {
  return ui.chip(est.texto, est.tono, { icono: ICONO_CODIGO[est.clave] || 'circulo-punteado' });
}

function chipRealEstado(real) {
  if (!real.estado) return ui.chip('Estado sin dato', 'neutro', { icono: 'circulo-punteado' });
  return ui.chip(ROTULO_ESTADO[real.estado], TONO_ESTADO[real.estado], { icono: ICONO_ESTADO[real.estado] });
}

function textoMedicion(m) {
  return m.items.map((i) => `${i.id} ${i.estado.toLowerCase() || 'sin estado'}${i.medido_en ? ` (${fmt.relativo(i.medido_en)})` : ''}`).join(' · ');
}

function detalleRobot(r, est, real, ahoraMs) {
  const t = r.tecnico;
  const pares = [
    ['Quién lo ejecuta', t.ejecuta],
    ['Acción que realiza', t.accion],
    ['Nivel de autonomía', t.nivel],
    ['Topes que lo acotan', t.topes],
    ['Qué falta', t.falta],
  ];
  if (t.codigo) pares.push(['Dónde está en el código', t.codigo]);
  if (est.medicion) pares.push(['Última medición del chequeo antes de lanzar', textoMedicion(est.medicion)]);
  if (real) {
    const l = L.estadoLatido(real, ahoraMs);
    pares.push(['En el registro', `${real.id} · ${real.estado || 'estado sin dato'} · ${real.nivel || 'nivel sin dato'} · ${l.texto}`]);
  }
  return ui.detalleTecnico('Detalle técnico', () => el('dl', { class: 'n1-kv' }, pares.map(([k, v]) => [el('dt', null, k), el('dd', null, v)])));
}

/** Lo que dice el estado en sombra de un robot: insignia, cómo va su última corrida, su última señal de vida y el resultado (sin botones). */
function bloqueSombra(robot, sombra, ahoraMs) {
  const fila = sombra ? sombra.porId[robot.id] || null : null;
  const ins = L.insigniaSombra(robot, fila, Boolean(sombra));
  const partes = [el('div', { class: 'rs-estado__fila' }, ui.chip(ins.texto, ins.tono, { icono: ins.icono }))];
  const corrida = L.corridaSombra(fila);
  if (corrida) {
    partes.push(el('div', { class: 'rs-estado__fila' }, ui.chip(corrida.texto, corrida.tono, { icono: corrida.icono })));
    partes.push(el('span', { class: 'rs-estado__hora' }, fila.ultimoLatido ? `Última señal de vida ${fmt.relativo(fila.ultimoLatido, ahoraMs)}` : 'Sin señal de vida todavía'));
    if (fila.ultimoResultado) partes.push(el('div', { class: 'rs-estado__fila' }, ui.chip(fila.ultimoResultado.texto, fila.ultimoResultado.tono, { icono: fila.ultimoResultado.icono })));
    if (fila.ultimaRazon) partes.push(ui.detalleTecnico('Por qué dio ese resultado', el('p', { class: 'rs-estado__razon' }, fila.ultimaRazon)));
  }
  partes.push(el('p', { class: 'rs-estado__razon' }, ins.detalle));
  return el('div', { class: 'rs-estado', 'data-sombra': ins.clave }, partes);
}

function filaCatalogo({ robot, real }, sistema, ahoraMs, sombra) {
  const est = L.estadoCodigo(robot, sistema);
  const celdaEstado = [chipCodigo(est)];
  if (real) {
    const l = L.estadoLatido(real, ahoraMs);
    celdaEstado.push(el('div', { class: 'n1-fila' }, chipRealEstado(real), real.nivel ? ui.chip(real.nivel, 'neutro', { icono: false }) : null));
    celdaEstado.push(el('small', null, l.texto));
  } else if (est.clave !== 'no_construido') {
    celdaEstado.push(el('small', null, est.clave === 'planeado' ? 'Sin registro todavía' : 'Aún sin registro de ejecuciones'));
  }
  celdaEstado.push(bloqueSombra(robot, sombra, ahoraMs));
  return el('li', { class: 'n1-rb__fila', 'data-robot': robot.id },
    el('span', { class: 'n1-rb__n', 'aria-hidden': 'true' }, String(robot.numero)),
    el('div', null,
      el('h3', { class: 'n1-rb__nombre' }, ui.termino(robot.termino, { texto: robot.nombre })),
      el('p', { class: 'n1-rb__pieza' }, `Pieza: ${robot.pieza}`)),
    el('div', null,
      el('p', { class: 'n1-rb__hace' }, robot.hace),
      el('p', { class: 'n1-rb__mas' }, robot.mas),
      est.detalle ? el('p', { class: 'n1-rb__mas' }, el('strong', null, 'Hoy: '), est.detalle) : null),
    el('div', { class: 'n1-rb__cuando' }, icono('reloj', { tam: 15 }), el('span', null, robot.horario)),
    el('div', { class: 'n1-rb__estado' }, celdaEstado),
    el('div', { class: 'n1-rb__tec' }, detalleRobot(robot, est, real, ahoraMs)));
}

function catalogo(union, sistema, ahoraMs, sombra) {
  return el('ul', { class: 'n1-rb', 'aria-label': 'Los 10 robots del plan' },
    el('li', { class: 'n1-rb__fila n1-rb__fila--cab', 'aria-hidden': 'true' }, el('span'), el('span', null, 'Robot'), el('span', null, 'Qué hace'), el('span', null, 'Cuándo'), el('span', null, 'Estado')),
    union.filas.map((f) => filaCatalogo(f, sistema, ahoraMs, sombra)));
}

function segmento(s) {
  if (s.tipo === 'marca') return el('span', { class: ['n1-marca', s.inferida && 'n1-marca--inferida'], style: { left: `${s.izq}%` }, title: `${s.hora}${s.inferida ? ' (hora calculada)' : ''}` });
  if (s.tipo === 'banda') return el('span', { class: ['n1-banda', s.contexto && 'n1-banda--ctx'], style: { left: `${s.izq}%`, width: `${s.ancho}%` }, title: s.hora });
  if (s.tipo === 'continuo') return el('span', { class: 'n1-banda n1-banda--continuo', title: `Cada ${s.cadaMin} min, todo el día` });
  return el('span', { class: 'n1-banda n1-banda--siempre', title: 'Siempre activo' });
}

function reloj24() {
  const eje = el('div', { class: 'n1-reloj__eje', 'aria-hidden': 'true' }, L.EJE_HORAS.map((h) => el('span', { style: { left: `${h.izq}%` } }, h.hora.slice(0, 2))));
  const carriles = L.carrilesReloj();
  return el('div', null,
    el('div', { class: 'n1-reloj', role: 'group', 'aria-label': 'Línea de tiempo de 24 horas de los robots' },
      el('div', { class: 'n1-reloj__fila n1-reloj__fila--eje' }, el('span'), eje),
      carriles.map((c) => el('div', { class: 'n1-reloj__fila' },
        el('div', { class: ['n1-reloj__nombre', c.contexto && 'n1-reloj__nombre--ctx'] }, el('b', null, c.numero ? el('i', null, String(c.numero)) : null, c.nombre), el('small', null, c.texto)),
        el('div', { class: 'n1-reloj__pista', role: 'img', 'aria-label': L.descripcionCarril(c) }, c.segmentos.map(segmento))))),
    el('ul', { class: 'n1-leyenda', 'aria-label': 'Cómo leer la línea de tiempo' },
      el('li', null, el('i', { class: 'l-marca' }), 'Momento exacto'),
      el('li', null, el('i', { class: 'l-banda' }), 'Franja'),
      el('li', null, el('i', { class: 'l-inferida' }), 'Vuelta con hora calculada'),
      el('li', null, el('i', { class: 'l-continuo' }), 'Se repite todo el día'),
      el('li', null, el('i', { class: 'l-siempre' }), 'Siempre vigilando'),
      el('li', null, el('i', { class: 'l-ctx' }), 'No es un robot (contexto)')));
}

function semana(ahoraMs) {
  const hoy = L.indiceDia(ahoraMs);
  return el('ol', { class: 'n1-semana', 'aria-label': 'Semana tipo' }, L.SEMANA.map((d, i) => el('li', { class: 'n1-dia', 'aria-current': i === hoy ? 'date' : null },
    el('h3', { class: 'n1-dia__nombre' }, d.dia, i === hoy ? ui.chip('Hoy', 'acento', { icono: false }) : null),
    el('p', { class: 'n1-dia__tema' }, d.tema),
    el('p', null, d.hace),
    el('p', null, el('strong', null, 'Resultado: '), d.resultado),
    el('p', { class: 'n1-dia__motor' }, el('strong', null, 'En nuestro sistema: '), d.motor))));
}

function existentes(lista) {
  return el('div', { class: 'n1-existente' }, lista.map((p) => el('div', { 'data-programa': p.id },
    el('b', null, p.nombre),
    el('p', { class: 'n1-nota' }, p.hace),
    el('div', { class: 'n1-fila n1-fila--nowrap' }, icono('reloj', { tam: 14 }), el('span', { class: ['n1-cadencia', p.sinDato && 'n1-tenue'] }, p.cadencia)),
    p.medicion.length ? ui.detalleTecnico('Detalle técnico', el('p', { class: 'n1-nota' }, `Última medición del chequeo antes de lanzar: ${p.medicion.map((m) => `${m.id} ${m.estado.toLowerCase() || 'sin estado'}`).join(' · ')}.`)) : null)));
}

// ───────────────────────── pestañas ─────────────────────────

/** Los comandos de «Robots en sombra»: se muestran copiables; este panel nunca los ejecuta. Instalar la programación es decisión del dueño. */
function comandosSombra(modelo) {
  const c = (modelo.sombra && modelo.sombra.comandos) || L.COMANDOS_SOMBRA;
  return el('div', { class: 'rs-comandos' },
    ui.comando(c.simular, { titulo: 'Probar los robots sin guardar nada', nota: 'Corre los robots en sombra y muestra qué dirían. No escribe, no envía, no pausa ni gasta.' }),
    ui.comando(c.escribir, { titulo: 'Correrlos y guardar su estado', nota: 'Deja su señal de vida y su estado en la carpeta de robots (y la lista de alertas). Después esta pantalla lo muestra. Sigue siendo solo lectura: no envía, no pausa ni gasta.' }),
    ui.comando(c.programar, { titulo: 'Ver cómo se programarían cada día', nota: 'Solo imprime las líneas para el programador de tu Mac: no instala nada. Instalarlas es decisión tuya: con la Mac dormida los robots pierden vueltas, así que esto no es una red de seguridad.' }));
}

function apoyoSombra(sombra, ahoraMs) {
  return el('ul', { class: 'rs-apoyo', 'aria-label': 'Programas de apoyo en sombra' }, L.APOYO_SOMBRA.map((a) => {
    const fila = sombra.porId[a.id] || null;
    const corrida = L.corridaSombra(fila);
    return el('li', { 'data-apoyo': a.id },
      el('b', null, fila ? fila.nombre : a.nombre),
      el('p', null, a.hace),
      corrida ? el('div', { class: 'rs-estado' },
        el('div', { class: 'rs-estado__fila' }, ui.chip(corrida.texto, corrida.tono, { icono: corrida.icono }), fila.ultimoResultado ? ui.chip(fila.ultimoResultado.texto, fila.ultimoResultado.tono, { icono: fila.ultimoResultado.icono }) : null),
        el('span', { class: 'rs-estado__hora' }, fila.ultimoLatido ? `Última señal de vida ${fmt.relativo(fila.ultimoLatido, ahoraMs)}` : 'Sin señal de vida todavía'),
        fila.ultimaRazon ? ui.detalleTecnico('Por qué dio ese resultado', el('p', { class: 'rs-estado__razon' }, fila.ultimaRazon)) : null) : el('p', { class: 'rs-estado__razon' }, 'Todavía no aparece en el estado guardado.'));
  }));
}

function seccionSombra(modelo) {
  const { sombra, ahoraMs } = modelo;
  const aviso = el('div', { class: 'n1-aviso n1-aviso--info' }, icono('info', { tam: 18 }),
    el('div', null, el('strong', null, 'En sombra: el robot mira y propone, pero no actúa. '), 'No son el sistema real: no vigilan ni frenan nada. Eso lo hará el planificador que construye el equipo técnico (S-B), cuando tú elijas dónde corre el sistema. Por eso esto nunca pone en verde el semáforo «¿Me puedo ausentar?».'));
  if (!sombra) {
    return el('div', { class: 'n1-pila' }, aviso, ui.vacioConPasos({
      titulo: 'Todavía no corrió ningún robot en sombra',
      explicacion: 'Cinco de los diez robots y dos programas de apoyo ya tienen una versión de solo lectura. Cuando la corras y guardes su estado, aquí vas a ver quién corrió hoy, quién falta y quién dejó de dar señal de vida.',
      icono: 'robot',
      pasos: [
        { texto: 'Para ver qué dirían, sin guardar nada:', comando: L.COMANDOS_SOMBRA.simular },
        { texto: 'Para dejar su estado guardado (esta pantalla lo muestra sola):', comando: L.COMANDOS_SOMBRA.escribir },
        { texto: 'Para ver cómo se programarían cada día (solo imprime: instalar es decisión tuya):', comando: L.COMANDOS_SOMBRA.programar },
      ],
    }));
  }
  const t = L.titularSombra(sombra);
  const r = sombra.resumen;
  const cuentas = [
    ui.chip(`${r.conSombra.length} con versión en sombra`, 'neutro', { icono: 'ojo' }),
    sombra.deHoy ? ui.chip(`${r.corrieronHoy.length} corrieron hoy`, r.corrieronHoy.length ? 'ok' : 'neutro', { icono: 'ok' }) : null,
    sombra.deHoy && r.faltanHoy.length ? ui.chip(`${r.faltanHoy.length} todavía no corrieron hoy`, 'aviso', { icono: 'reloj' }) : null,
    r.vencidos.length ? ui.chip(`${r.vencidos.length} con latido vencido`, 'aviso', { icono: 'reloj-alerta' }) : null,
    r.soloManual.length ? ui.chip(`${r.soloManual.length} solo a mano`, 'neutro', { icono: 'circulo-punteado' }) : null,
    ui.chip(`${r.sinVersion.length} sin versión en sombra`, 'neutro', { icono: 'circulo-punteado' }),
  ];
  return el('div', { class: 'n1-pila' }, aviso,
    el('div', { class: 'rs-titular', 'data-situacion': t.clave },
      el('span', { class: 'rs-titular__icono', 'aria-hidden': 'true' }, icono(t.icono, { tam: 22 })),
      el('div', { class: 'rs-titular__cuerpo' },
        el('h3', { class: 'rs-titular__titulo' }, t.texto),
        el('p', { class: 'rs-titular__texto' }, t.detalle),
        el('div', { class: 'rs-cuentas' }, cuentas),
        el('p', { class: 'rs-estado__hora' }, sombra.generadoEn ? `Estado guardado ${fmt.relativo(sombra.generadoEn, ahoraMs)}` : 'Estado guardado sin fecha'),
        !sombra.deHoy ? el('p', { class: 'rs-titular__texto' }, el('strong', null, 'Ojo: '), 'este estado no es de hoy y no se actualiza solo, así que lo que dice de «hoy» no vale. Vuelve a guardarlo con el segundo comando de abajo.') : null,
        sombra.avisos.length ? el('ul', { class: 'n1-lista' }, sombra.avisos.map((a) => el('li', { class: 'n1-nota' }, a))) : null)),
    el('h3', { class: 'n1-subtitulo' }, 'Programas de apoyo'),
    apoyoSombra(sombra, ahoraMs),
    comandosSombra(modelo));
}

function cuerpoPlan(ctx, modelo) {
  const { sistema, union, ahoraMs, programas, sombra } = modelo;
  return el('div', { class: 'n1-pila' },
    ui.seccion('Robots en sombra: qué corrió hoy', seccionSombra(modelo), {
      glosario: 'robots_en_sombra',
      ayuda: 'Los robots que ya tienen una versión de solo lectura. Corren a mano o programados en tu Mac cuando tú decides, y dejan su señal de vida. No envían mensajes, no pausan, no gastan.',
    }),
    ui.seccion('Los 10 robots y su horario', catalogo(union, sistema, ahoraMs, sombra), {
      glosario: 'robot',
      ayuda: 'Cada uno hace una sola cosa. «No construido» significa que todavía no hay nada programado; «Parcial», que existe una parte y se explica cuál. Las horas son del reloj del mercado y son hipótesis hasta ajustarlas.',
    }),
    ui.seccion('Un día de 24 horas', reloj24(), { glosario: 'reloj_mercado', ayuda: 'Qué corre a qué hora. Se lee de izquierda a derecha, de medianoche a medianoche.' }),
    ui.seccion('Una semana tipo', semana(ahoraMs), { glosario: 'semana_tipo', ayuda: 'El ritmo semanal. Cada día tiene un trabajo; el sábado los robots corren solos y el domingo se ordena el cerebro.' }),
    ui.seccion('Lo que ya funciona hoy', existentes(programas), { ayuda: 'No son los 10 robots: son programas que ya vigilan o cargan datos y que los robots van a usar como base. La frecuencia sale de los parámetros.' }));
}

function filasRegistro(registro, ahoraMs) {
  return registro.robots.map((r) => {
    return { ...r, titulo: L.nombreVisible(r), latido: L.estadoLatido(r, ahoraMs) };
  });
}

function tablaRegistro(registro, ahoraMs) {
  return ui.tabla({
    etiqueta: 'Robots del registro', filas: filasRegistro(registro, ahoraMs), vacio: 'El registro no trae ningún robot.',
    columnas: [
      { clave: 'titulo', titulo: 'Robot', flex: true, formato: (v, f) => el('div', null, el('strong', null, v), f.titulo !== f.id ? el('div', { class: 'n1-tenue n1-mono' }, f.id) : null) },
      { clave: 'cadencia', titulo: 'Cuándo', ancho: '150px', formato: (v) => (v ? el('span', null, v) : el('span', { class: 'texto-tenue' }, 'sin dato')) },
      { clave: 'nivel', titulo: 'Nivel', ancho: '90px', formato: (v) => (v ? ui.chip(v, 'neutro', { icono: false }) : el('span', { class: 'texto-tenue' }, 'sin dato')) },
      { clave: 'estado', titulo: 'Estado', ancho: '140px', formato: (v, f) => chipRealEstado(f) },
      { clave: 'latido', titulo: 'Última señal de vida', ancho: '230px', orden: (f) => f.latido.minutos ?? 1e12, formato: (v) => (v.clave === 'sin_latido' ? el('span', { class: 'texto-tenue' }, v.texto) : ui.chip(v.texto, v.tono === 'critico' ? 'critico' : v.tono, { icono: v.clave === 'vencido' ? 'reloj-alerta' : (v.clave === 'al_dia' ? 'ok' : false) })) },
      { clave: 'aciertoBp', titulo: 'Acierto', ancho: '110px', alinear: 'der', formato: (v) => (v === null ? el('span', { class: 'texto-tenue' }, 'sin medir') : fmt.pct(v)) },
    ],
  });
}

function cuerpoRegistro(ctx, modelo) {
  const { estadoRegistro, registro, union, ahoraMs, errorRegistro } = modelo;
  const leyenda = el('dl', { class: 'n1-kv' },
    el('dt', null, ui.termino('estado_robot')), el('dd', null, 'Apagado no corre · en sombra registra lo que haría sin actuar · vivo actúa dentro de sus topes.'),
    el('dt', null, ui.termino('nivel_robot')), el('dd', null, 'Del nivel 0 (solo mira) al 4. Subir de nivel siempre lo firmas tú; el auditor lo baja solo si el robot falla.'),
    el('dt', null, ui.termino('latido_robot')), el('dd', null, 'Si un robot vivo pasa su límite sin dar señales de vida, se lo considera caído y se avisa.'),
    el('dt', null, ui.termino('acierto_auditor')), el('dd', null, 'Se muestra «sin medir» mientras el auditor no exista; nunca un 0 % inventado.'));
  let principal;
  if (estadoRegistro === 'ok') {
    const faltan = union.filas.filter((f) => !f.real).length;
    principal = el('div', { class: 'n1-pila' },
      tablaRegistro(registro, ahoraMs),
      faltan ? el('p', { class: 'n1-nota' }, `${faltan} de los ${L.ROBOTS.length} robots del plan todavía no aparecen en el registro: en el catálogo siguen como «no construido» o «parcial».`) : null);
  } else if (estadoRegistro === 'error') {
    principal = ui.errorBox(errorRegistro, { reintentar: () => ctx.recargar() });
  } else {
    principal = ui.vacioConPasos({
      titulo: 'Todavía no hay registro de robots',
      explicacion: 'Cuando se construya el marco de robots, cada robot va a quedar anotado en un registro único con su horario, su nivel (de 0 a 4), su estado (apagado, en sombra o vivo), su última señal de vida y su acierto. Esta pantalla lo va a leer sola en cuanto exista; hasta entonces, la pestaña «Plan y horarios» muestra qué se planea y qué ya tiene algo construido.',
      icono: 'robot',
      pasos: [
        { texto: 'El registro lo va a escribir el marco de robots del sistema (horario, nivel y señal de vida de cada robot). Todavía no hay un comando para generarlo.' },
        ...(modelo.sombra ? [{ texto: 'Mientras tanto, los robots en sombra dejan su propio estado guardado: míralo en la pestaña «Plan y horarios», sección «Robots en sombra».' }] : []),
        { texto: 'Todavía no está definido cómo se escribe ese archivo: esta pantalla acepta que falten campos y los muestra como «sin dato».' },
        { texto: 'Los robots entran de a uno, primero en sombra; cuando aciertan pasan a vivo. El auditor los vigila desde el primer día.' },
      ],
    });
  }
  return el('div', { class: 'n1-pila' },
    ui.seccion('Lo que corre de verdad', principal, { glosario: 'registro_robots', ayuda: 'La lista real, leída del registro. Aquí nunca hay botones para encender, apagar ni cambiar un robot.' }),
    ui.seccion('Cómo se lee', leyenda),
    ui.detalleTecnico('Detalle técnico del registro', () => el('div', { class: 'n1-pila n1-pila--chica' },
      el('dl', { class: 'n1-kv' },
        el('dt', null, 'Archivo esperado'), el('dd', null, el('code', null, 'empresa/robots.yaml')),
        el('dt', null, 'Estado de la lectura'), el('dd', null, { ok: 'Leído', vacio: 'El archivo no existe todavía', sin_ruta: 'Este servidor aún no expone el registro de robots (ruta /api/robots)', error: 'Error al leerlo' }[estadoRegistro] || estadoRegistro),
        el('dt', null, 'Forma tolerada'), el('dd', null, 'Lista de robots o diccionario por id, con campos como id, nombre, horario, nivel, estado, ultimo_latido, latido_max_min y acierto (acierto_bp, acierto_pct o acierto).')),
      ui.comando('cat empresa/robots.yaml', { titulo: 'Cómo mirarlo a mano (solo lectura)' }))));
}

function cuerpoReglas() {
  return el('div', { class: 'n1-pila' },
    el('div', { class: 'n1-principio' }, icono('escudo', { tam: 22 }),
      el('div', null, el('h3', null, ui.termino('todo_robot_se_audita', { texto: L.PRINCIPIO_AUDITORIA.titulo })), el('p', null, L.PRINCIPIO_AUDITORIA.texto))),
    ui.seccion('Las seis reglas de oro', el('ol', { class: 'n1-reglas' }, L.REGLAS_DE_ORO.map((r) => el('li', { class: 'n1-regla', 'data-regla': String(r.n) },
      el('span', { class: 'n1-regla__n', 'aria-hidden': 'true' }, String(r.n)),
      el('div', null,
        el('h3', null, r.titulo),
        el('p', null, r.negocio),
        ui.detalleTecnico('Cómo lo hace cumplir el sistema', el('p', { class: 'n1-nota' }, r.cumple)))))),
    { glosario: 'regla_de_oro', ayuda: 'Aprendidas perdiendo plata. Se hacen cumplir con programas, no con buenas intenciones; cambiarlas es decisión tuya.' }));
}

// ───────────────────────── página ─────────────────────────

export async function render(ctx) {
  ui.instalarEstilos('n1-comun', CSS_COMUN);
  ui.instalarEstilos('n1-robots', CSS_ROBOTS);
  const ahoraMs = Date.now();
  ui.instalarEstilos('rs-sombra', CSS_SOMBRA);
  const [rSis, rPar, rReg, rSom] = await Promise.all([leer(ctx, '/sistema'), leer(ctx, '/parametros'), leer(ctx, '/robots'), leer(ctx, '/robots/sombra')]);
  const sombra = rSom.ok ? L.normalizarSombra(rSom.sobre) : null;     // sin estado guardado (o servidor sin la ruta) = null: no se inventa nada
  const sistema = rSis.ok ? rSis.sobre.datos : null;
  const parametros = rPar.ok && rPar.sobre.datos && typeof rPar.sobre.datos === 'object' ? (rPar.sobre.datos.parametros || null) : null;
  const estadoRegistro = L.clasificarLecturaRegistro({ error: rReg.err, sobre: rReg.sobre });
  const registro = estadoRegistro === 'ok' ? L.normalizarRegistro(rReg.sobre.datos) : { robots: [], total: 0, conteos: { vivo: 0, sombra: 0, apagado: 0, sinEstado: 0 } };
  const union = L.unirConRegistro(registro);
  const modelo = { sistema, union, registro, estadoRegistro, ahoraMs, programas: L.programasExistentes(parametros, sistema), errorRegistro: rReg.err, sombra };

  if (ctx.params && ctx.params.vista) vista = L.vistaValida(ctx.params.vista);
  const host = el('div');
  const pintar = () => {
    ui.reemplazar(host, vista === 'registro' ? cuerpoRegistro(ctx, modelo) : vista === 'reglas' ? cuerpoReglas() : cuerpoPlan(ctx, modelo));
  };
  const pestanas = ui.barraPestanas({
    etiqueta: 'Secciones de Robots', activo: vista,
    items: [
      { id: 'plan', titulo: 'Plan y horarios', icono: 'reloj' },
      { id: 'registro', titulo: 'Registro real', icono: 'robot', contador: estadoRegistro === 'ok' ? registro.total : undefined },
      { id: 'reglas', titulo: 'Reglas de oro', icono: 'escudo', contador: L.REGLAS_DE_ORO.length },
    ],
    onCambio: (id) => { vista = L.vistaValida(id); pintar(); },
  });
  pintar();

  const atencion = ui.atencion({
    items: L.atencionRobots({ sistema, registro, estadoRegistro, ahoraMs, sombra }),
    vacio: 'Todos los robots registrados dan señales de vida y aciertan lo exigido.',
  });
  const metricas = el('div', { class: 'n1-metricas' }, L.metricasRobots({ sistema, registro, estadoRegistro, ahoraMs, sombra }).map((m) => ui.metrica({
    etiqueta: m.etiqueta, valor: m.valor, contexto: m.contexto, tono: m.tono || undefined, ayuda: m.ayuda,
  })));

  return el('div', { class: 'pagina' },
    cabecera({
      titulo: 'Los robots: qué corre y cuándo',
      descripcion: 'Diez programas simples, cada uno con una sola tarea y su horario, que deciden con lo que se cobró de verdad. Aquí ves cuáles están construidos, cuándo corren y cómo se controlan. Desde esta pantalla no se enciende ni se apaga ninguno.',
      acciones: [ui.fuente(RUTAS_FUENTE, { leido: rSis.ok ? rSis.sobre.generado_en : null }), el('button', { type: 'button', class: 'btn btn--chico', onclick: () => ctx.recargar() }, icono('refrescar', { tam: 14 }), 'Actualizar')],
      pestanas,
    }),
    atencion, metricas, host);
}
