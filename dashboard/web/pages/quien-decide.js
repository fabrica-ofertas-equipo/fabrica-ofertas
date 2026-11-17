// pages/quien-decide.js — #/quien-decide «Quién decide qué»: la tabla de decisiones GENERADA de los archivos reales (contratos/gates.json,
// empresa/autonomia.yaml, empresa/limites.yaml) frente al reparto que eligió el dueño (J2, 2026-11-06), con los frenos de empresa y lo que sigue siendo humano.
//
// ESTADO HONESTO: lo vigente (HOY, borde continuo) y el objetivo (J2, borde discontinuo, «aún sin implementar») se ven siempre distintos y nunca se mezclan.
// SOLO LECTURA: el panel nunca cambia gates, límites ni autonomía. Cambiarlos lo hace el dueño con su firma, por línea de comandos (aquí solo se muestra, copiable).
// Fuentes: GET /api/gates (contratos/gates.json), GET /api/parametros (limites + autonomia) y GET /api/sistema (PAUSA y freno de captura). Lógica pura: lib/quien-decide.js.

import { ESTILOS_N4_QUIEN_DECIDE } from '../lib/estilos-n4.js';
import {
  modeloQuienDecide, mensajesBanner, metricasQuienDecide, pestanasQuienDecide, filtrarFilas, comandosFrenos, textoGateNivel,
  GATES_INFO, ORDEN_GATES, FUERZA_GATE, NIVELES, GRUPOS, ESTADO_ITEM, ESTADO_FILA, ESTADO_CONSERVA, COLUMNAS_J2, NIVELES_TEXTO, numeroNivel,
} from '../lib/quien-decide.js';

export const meta = { ruta: 'quien-decide', titulo: 'Quién decide qué', grupo: 'Dinero y reglas', icono: 'escudo', escucha: ['empresa', 'oferta'] };

/** Nombre en palabras de cada archivo que puede faltar (la ruta queda en el detalle técnico). */
const NOMBRE_ARCHIVO = { 'contratos/gates.json': 'la tabla de puntos de control', 'empresa/limites.yaml': 'tus límites', 'empresa/autonomia.yaml': 'los niveles de autonomía' };

/** Estado de la vista que sobrevive a una actualización en vivo (pestaña, filtro de gate y texto buscado). */
const UI = { pestana: 'hoy', gate: 'todo', q: '' };

function hayEdicion() {
  const d = globalThis.document;
  const a = d && d.activeElement;
  return Boolean(a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) || Boolean(d && d.querySelector('.modal-fondo'));
}

// ───────────────────────── piezas pequeñas ─────────────────────────

function etiquetaHoy(ui, corta = false) {
  const { el } = ui;
  return el('span', { class: 'qd-etiqueta qd-etiqueta--hoy' }, ui.icono('archivo', { tam: 13 }), corta ? 'HOY · vigente' : 'HOY · vigente en los archivos');
}
function etiquetaObjetivo(ui, corta = false) {
  const { el } = ui;
  return el('span', { class: 'qd-etiqueta qd-etiqueta--objetivo' }, ui.icono('diana', { tam: 13 }), corta ? 'OBJETIVO · sin implementar' : 'OBJETIVO (J2) · aún sin implementar');
}

function aviso(ui, tono, ...hijos) {
  const { el } = ui;
  const icono = tono === 'objetivo' ? 'diana' : tono === 'info' ? 'info' : 'alerta';
  return el('div', { class: `qd-aviso${tono === 'objetivo' ? ' qd-aviso--objetivo' : tono === 'info' ? ' qd-aviso--info' : ''}`, role: 'note' },
    el('span', { class: 'qd-aviso__icono' }, ui.icono(icono, { tam: 16 })), el('div', { class: 'qd-aviso__texto' }, ...hijos));
}

/** Chip del gate que rige: icono + etiqueta (el color nunca va solo). */
function chipGate(ui, gate) {
  if (!gate) return ui.chip('Sin fila en la tabla de puntos de control', 'neutro', { icono: 'circulo-punteado' });
  const g = GATES_INFO[gate];
  const c = ui.chip(g.etiqueta, g.tono, { icono: g.icono });
  c.setAttribute('title', `${g.etiqueta}: ${g.frase}`);
  return c;
}

/** «Cómo leer esta pantalla»: qué significa cada nivel de autonomía, con un ejemplo corto. */
function comoLeer(ui) {
  const { el } = ui;
  return el('details', { class: 'qd-como' },
    el('summary', null, ui.icono('info', { tam: 14 }), ' Cómo leer esta pantalla: qué significa cada nivel'),
    el('div', { class: 'qd-pila' },
      el('p', { class: 'qd-sub' }, 'Cada etapa tiene un nivel de autonomía, de 0 a 4: cuánto hace sola. En cada decisión se ve quién decide según el nivel en que está esa etapa.'),
      el('ul', { class: 'qd-niveles' }, NIVELES_TEXTO.map(([n, t]) => el('li', null, el('strong', null, `Nivel ${n}: `), t)))));
}

function leyendaGates(ui) {
  const { el } = ui;
  return el('div', { class: 'qd-leyenda' }, ORDEN_GATES.map((id) => {
    const g = GATES_INFO[id];
    return el('div', { class: 'qd-leyenda__it' }, el('span', { class: 'qd-fila qd-fila--junta' }, chipGate(ui, id), ui.ayuda(g.glosario)), el('span', { class: 'qd-sub' }, `En la tira de niveles se ve como «${g.letra}». ${g.frase}`));
  }));
}

function tira(ui, f) {
  const { el } = ui;
  if (!f.porNivel) return el('span', { class: 'qd-tenue' }, '—');
  const resumen = NIVELES.map((n) => textoGateNivel(n, f.porNivel[n])).join('; ');
  return el('span', { class: 'qd-tira', role: 'img', 'aria-label': `Por nivel: ${resumen}${f.nivel ? `. Nivel actual: ${numeroNivel(f.nivel)}` : ''}` },
    NIVELES.map((n) => el('span', { class: ['qd-tira__n', f.nivel === n && 'es-actual'], 'data-gate': f.porNivel[n] || '', title: `${textoGateNivel(n, f.porNivel[n])}${f.nivel === n ? ' · nivel actual' : ''}` }, f.porNivel[n] === 'NA' ? '–' : (f.porNivel[n] || '?'))));
}

function celdaDecision(ui, f) {
  const { el } = ui;
  const grupo = GRUPOS.find((g) => g.id === f.grupo);
  return el('div', { class: 'qd-nom' },
    el('strong', null, f.nombre),
    el('span', { class: 'qd-sub' }, grupo ? grupo.titulo : ''),
    f.sinEntrada && f.nota ? el('span', { class: 'qd-sub' }, f.nota) : null,
    ui.soloTecnico(el('span', { class: 'qd-mono qd-sub' }, f.id, f.descripcion ? ` — ${f.descripcion}` : '')));
}

function celdaQuien(ui, f) {
  const { el } = ui;
  let nota = null;
  let icono = 'info';
  if (f.limitadaPorLista) {
    icono = 'candado';
    nota = `La tabla llega a «${GATES_INFO[f.tablaPermite].etiqueta.toLowerCase()}» en los niveles altos, pero rige tu firma: está entre las acciones que la piden siempre${f.esMinima ? ' (no se quita ni con firma)' : ''}.`;
  } else if (f.enLista) {
    icono = 'candado';
    nota = f.esMinima ? 'Está entre las acciones que piden tu firma en cualquier nivel.' : 'La añadiste a las acciones que piden siempre tu firma.';
  } else if (f.constante && f.gate) {
    nota = 'Igual en los cinco niveles.';
  } else if (f.nivelOrigen === 'minimo' && f.nivel) {
    nota = `Sin etapa propia: se toma el nivel más bajo (nivel ${numeroNivel(f.nivel)}).`;
  }
  return el('div', { class: 'qd-quien' }, chipGate(ui, f.gate), nota ? el('span', { class: 'qd-quien__nota' }, ui.icono(icono, { tam: 12 }), nota) : null);
}

function celdaNivel(ui, f) {
  const { el } = ui;
  if (!f.nivel) return el('span', { class: 'qd-tenue' }, f.constante ? 'Cualquiera' : '—');
  return el('span', { class: 'qd-nivel' },
    ui.termino(`nivel_${f.nivel.toLowerCase()}`, { texto: `Nivel ${numeroNivel(f.nivel)}`, sinTecnico: true }),
    f.etapa && f.tipo === 'accion' ? el('span', { class: 'qd-sub' }, `(${f.etapa})`) : null);
}

function celdaTopes(ui, f) {
  const { el } = ui;
  if (!f.topes.length) return el('span', { class: 'qd-tenue' }, f.tipo === 'etapa' && f.clave === 'X1' ? 'Puede frenar; no gasta' : 'Sin tope propio');
  const sin = f.topes.filter((t) => t.bloquea);
  return el('div', { class: 'qd-pila qd-pila--chica' },
    el('ul', { class: 'qd-topes' }, f.topes.map((t) => el('li', { class: 'qd-tope' },
      ui.termino(`lim_${t.clave}`, { sinTecnico: true }),
      t.estado === 'sin_lectura' ? el('span', { class: 'qd-tope__estado qd-tenue' }, 'sin leer')
        : t.bloquea ? el('span', { class: 'qd-tope__estado qd-tope__estado--falta' }, ui.icono('alerta', { tam: 12 }), t.estado === 'vacio' ? 'lista vacía' : t.clave === 'sello' ? 'sin firma' : 'sin fijar')
          : el('span', { class: 'qd-tope__valor' }, t.texto)))),
    sin.length ? el('span', { class: 'qd-tope-aviso' }, ui.icono('candado', { tam: 12 }), sin.every((t) => t.estado === 'vacio') ? 'Lista vacía: por defecto no se puede gastar' : 'Sin fijar: por defecto no se puede gastar') : null);
}

function columnasHoy(ui) {
  return [
    { clave: 'nombre', titulo: 'Decisión', ancho: '23%', formato: (_, f) => celdaDecision(ui, f), orden: (f) => f.nombre },
    { clave: 'gate', titulo: 'Quién decide hoy', ancho: '22%', formato: (_, f) => celdaQuien(ui, f), orden: (f) => (f.gate ? FUERZA_GATE[f.gate] : -1) },
    { clave: 'nivel', titulo: 'Nivel de la etapa', ancho: '9%', formato: (_, f) => celdaNivel(ui, f), orden: (f) => f.nivel },
    { clave: 'porNivel', titulo: 'Por nivel (del 0 al 4)', ancho: '13%', ordenable: false, formato: (_, f) => tira(ui, f) },
    { clave: 'topes', titulo: 'Tope que la acota', formato: (_, f) => celdaTopes(ui, f), orden: (f) => f.sinFijar },
  ];
}

/** Misma información que una fila de la tabla, apilada: es lo que se ve cuando el contenedor es estrecho (móvil), donde una tabla de cinco columnas obligaría a desplazarse. */
function fichaHoy(ui, f) {
  const { el } = ui;
  const grupo = GRUPOS.find((g) => g.id === f.grupo);
  return el('li', { class: 'qd-ficha' },
    el('div', { class: 'qd-ficha__cab' }, el('strong', null, f.nombre), chipGate(ui, f.gate)),
    el('div', { class: 'qd-sub qd-fila qd-fila--junta' }, grupo ? grupo.titulo : '', f.nivel ? el('span', null, '· ', celdaNivel(ui, f)) : null),
    f.sinEntrada && f.nota ? el('span', { class: 'qd-sub' }, f.nota) : null,
    (() => { const q = celdaQuien(ui, f); return q.querySelector && q.querySelector('.qd-quien__nota') ? q.querySelector('.qd-quien__nota') : null; })(),
    f.porNivel ? el('div', { class: 'qd-fila qd-fila--junta' }, tira(ui, f), el('span', { class: 'qd-sub' }, 'niveles 0 → 4')) : null,
    celdaTopes(ui, f));
}

// ───────────────────────── pestaña HOY ─────────────────────────

function vacioGates(ui) {
  return ui.vacioConPasos({
    titulo: 'No se pudo leer la tabla de puntos de control',
    explicacion: 'Sin esa tabla no se puede decir quién decide cada paso. Es un archivo del proyecto (contratos/gates.json): el panel solo lo lee, no lo edita.',
    icono: 'escudo',
    pasos: [
      { texto: 'Comprueba que el archivo existe y tiene el formato esperado', comando: '.venv/bin/python -m scripts.validar_esquemas esquemas' },
      { texto: 'Si falta, recupéralo de la copia del proyecto y recarga esta pantalla; se llena sola.' },
    ],
  });
}

function pestanaHoy(ctx, m) {
  const { ui } = ctx;
  const { el } = ui;
  if (!m.hay.gates) return ui.seccion('Quién decide hoy', vacioGates(ui), { glosario: 'hoy_vigente' });
  const filas = m.hoy.filas;
  const r = m.hoy.resumen;
  const tabla = ui.tabla({
    columnas: columnasHoy(ui), filas, etiqueta: 'Quién decide cada paso y cada acción, hoy', maxFilas: 500,
    vacio: { texto: 'Ninguna decisión coincide con el filtro.', pista: 'Prueba otra palabra o elige «Todo».', icono: 'lupa' },
  });
  const cuenta = el('span', { class: 'qd-cuenta', 'aria-live': 'polite' });
  const lista = el('ul', { class: 'qd-lista', 'aria-label': 'Quién decide cada paso y cada acción, hoy (vista en lista)' });
  const aplicar = () => {
    const visibles = filtrarFilas(filas, { gate: UI.gate, texto: UI.q });
    tabla.actualizarFilas(visibles);
    ui.reemplazar(lista, visibles.length ? visibles.map((f) => fichaHoy(ui, f)) : el('li', { class: 'qd-sub' }, 'Ninguna decisión coincide con el filtro.'));
    cuenta.textContent = visibles.length === filas.length ? `${filas.length} decisiones` : `${visibles.length} de ${filas.length} decisiones`;
  };
  const opciones = [{ valor: 'todo', etiqueta: `Todo (${filas.length})`, titulo: 'Todas las decisiones' }]
    .concat(ORDEN_GATES.map((id) => ({ valor: id, etiqueta: `${GATES_INFO[id].etiqueta} (${r.conteo[id]})`, titulo: GATES_INFO[id].frase })).filter((o) => r.conteo[o.valor] > 0))
    .concat(r.conteo.sin ? [{ valor: 'sin', etiqueta: `Sin fila en la tabla (${r.conteo.sin})`, titulo: 'Etapas que no tienen una fila propia en la tabla de puntos de control' }] : []);
  if (!opciones.some((o) => o.valor === UI.gate)) UI.gate = 'todo';
  const buscar = el('input', {
    type: 'search', class: 'campo campo--chico qd-buscar', placeholder: 'Buscar una decisión, una etapa o un límite…', 'aria-label': 'Buscar en las decisiones', value: UI.q,
    oninput: (ev) => { UI.q = ev.target.value; aplicar(); },
  });
  const filtro = ui.segmentado({ opciones, valor: UI.gate, etiqueta: 'Filtrar por quién decide', onCambio: (v) => { UI.gate = v; aplicar(); } });
  aplicar();
  const cuerpo = el('div', { class: 'qd-pila' },
    el('div', { class: 'qd-fila' }, etiquetaHoy(ui), el('span', { class: 'qd-sub' }, 'Leído ahora de la tabla de puntos de control, los niveles de autonomía y tus límites.'), ui.soloTecnico(el('span', { class: 'qd-sub qd-mono' }, 'contratos/gates.json · empresa/autonomia.yaml · empresa/limites.yaml')), ui.ayuda('hoy_vigente')),
    comoLeer(ui),
    leyendaGates(ui),
    r.forzadas.length ? aviso(ui, 'aviso',
      el('strong', null, `${r.forzadas.length === 1 ? 'Una acción seguirá' : `${r.forzadas.length} acciones seguirán`} siendo tuyas aunque subas de nivel.`),
      el('span', null, `${m.hoy.filas.filter((f) => f.limitadaPorLista).map((f) => f.nombre).join(' y ')}: la tabla de puntos de control permite «por excepción» desde el nivel 3, pero `, ui.termino('lim_acciones_gate_humano', { texto: 'la lista de acciones que siempre piden tu firma' }), ' manda (rige lo más estricto). Quitarlas de esa lista es el cambio grande D-02 del objetivo J2; mira la pestaña «Objetivo».')) : null,
    el('div', { class: 'qd-controles' }, filtro, buscar, cuenta),
    el('div', { class: 'qd-vista-tabla' }, tabla),
    el('div', { class: 'qd-vista-lista' }, lista),
    el('p', { class: 'qd-sub' }, 'La tira muestra quién decide en cada nivel, del 0 al 4 (H = lo firmas tú, S = por excepción, A = automático, – = aún no se hace); el recuadro marca el nivel actual de la etapa. Rige lo más estricto entre la tabla, el nivel y la lista de acciones que siempre piden tu firma.'));
  return ui.seccion('Quién decide hoy', cuerpo, { glosario: 'gate_efectivo', ayuda: 'Generado de los archivos reales cada vez que abres la pantalla: no hay nada escrito a mano. Si un archivo cambia, esta tabla cambia sola.' });
}

// ───────────────────────── pestaña OBJETIVO ─────────────────────────

function iconoEstado(ui, meta) { return ui.icono(meta.icono, { tam: 14 }); }

function seccionColumnas(ctx, m) {
  const { ui } = ctx;
  const { el } = ui;
  const porId = Object.fromEntries(m.objetivo.filas.map((f) => [f.id, f]));
  return ui.seccion('El reparto que elegiste', el('div', { class: 'qd-cols4' }, COLUMNAS_J2.map((col) => el('section', { class: 'qd-col', 'aria-label': col.titulo },
    el('h3', { class: 'qd-col__cab' }, ui.icono(col.icono, { tam: 16 }), col.titulo),
    el('ul', { class: 'qd-col__lista' }, col.items.map((item) => {
      const f = porId[`${col.id}.${item.id}`];
      const est = f ? ESTADO_FILA[f.estado] : null;
      return el('li', { class: 'qd-col__item' }, el('span', null, item.texto), est ? ui.chip(est.etiqueta, est.tono, { icono: est.icono }) : null);
    }))))),
  { ayuda: 'Tal como lo definiste (decisión J2, 2026-11-06). El estado de cada decisión sale de comparar este reparto con los archivos de hoy.', glosario: 'reparto_decisiones', clase: 'qd-objetivo' });
}

function seccionConserva(ctx, m) {
  const { ui } = ctx;
  const { el } = ui;
  return ui.seccion('Lo que se sigue cuidando solo, sin pedirte un clic', el('ul', { class: 'qd-conserva' }, m.objetivo.conserva.map((c) => {
    const est = ESTADO_CONSERVA[c.estado] || ESTADO_CONSERVA.sin_dato;
    return el('li', { class: 'qd-conserva__it' },
      el('div', { class: 'qd-conserva__texto' }, el('strong', null, c.texto, ' ', ui.ayuda(c.glosario)), el('span', { class: 'qd-sub' }, c.detalle), c.nota ? el('span', { class: 'qd-sub' }, c.nota) : null),
      ui.chip(est.etiqueta, est.tono, { icono: est.icono }));
  })),
  { ayuda: 'La red de seguridad que reemplaza tu clic cuando los robots prenden solos. Cada línea dice si ya existe o si falta.', glosario: 'frenos_empresa' });
}

function lista(ui, items, clase) {
  const { el } = ui;
  return el('ul', { class: clase }, items.map((x) => el('li', null, x)));
}

function itemFalta(ui, x) {
  const { el } = ui;
  const e = ESTADO_ITEM[x.estado] || ESTADO_ITEM.nota;
  return el('li', { class: 'qd-falta__it' },
    el('span', { class: `qd-falta__ic qd-falta__ic--${x.estado}`, role: 'img', 'aria-label': e.etiqueta, title: e.etiqueta }, ui.icono(e.icono, { tam: 15 })),
    el('span', null, x.texto, x.tecnico ? ui.soloTecnico(el('span', { class: 'qd-falta__fuente qd-mono' }, ` · ${x.tecnico}`)) : null, x.fuente ? ui.soloTecnico(el('span', { class: 'qd-falta__fuente' }, `Según ${x.fuente}`)) : null));
}

function seccionFalta(ctx, m) {
  const { ui } = ctx;
  const { el } = ui;
  const leyenda = el('div', { class: 'qd-fila qd-fila--junta' }, ['ok', 'pendiente', 'plan', 'nota'].map((k) => {
    const e = ESTADO_ITEM[k];
    return el('span', { class: 'qd-sub qd-fila qd-fila--junta' }, el('span', { class: `qd-falta__ic qd-falta__ic--${k}` }, ui.icono(e.icono, { tam: 14 })), e.etiqueta);
  }));
  const filas = [];
  for (const col of COLUMNAS_J2) {
    filas.push(el('div', { class: 'qd-obj__grupo' }, ui.icono(col.icono, { tam: 15 }), col.titulo));
    for (const f of m.objetivo.filas.filter((x) => x.columna === col.id)) {
      const est = ESTADO_FILA[f.estado];
      filas.push(el('div', { class: 'qd-obj__fila' },
        el('div', { class: 'qd-obj__celda', 'data-etiqueta': 'Decisión' }, el('strong', null, f.texto), ui.chip(est.etiqueta, est.tono, { icono: est.icono })),
        el('div', { class: 'qd-obj__celda', 'data-etiqueta': 'Hoy (vigente)' }, lista(ui, f.hoy, 'qd-obj__hoy')),
        el('div', { class: 'qd-obj__celda', 'data-etiqueta': 'Qué falta para llegar' }, el('ul', { class: 'qd-falta' }, f.falta.map((x) => itemFalta(ui, x))))));
    }
  }
  return ui.seccion('Qué falta para llegar', el('div', { class: 'qd-pila' },
    leyenda,
    el('div', { class: 'qd-obj', role: 'group', 'aria-label': 'Qué falta para llegar, por decisión' },
      el('div', { class: 'qd-obj__cab', 'aria-hidden': 'true' }, el('span', null, 'Decisión'), el('span', null, 'Hoy (vigente)'), el('span', null, 'Qué falta para llegar')),
      filas),
    el('p', { class: 'qd-sub' }, 'Lo marcado «comprobado en los archivos» se calcula ahora. Lo marcado «según el plan» viene del plan de trabajo y de tus decisiones (2026-11-06): el panel no puede verificarlo.')),
  { ayuda: 'Para cada decisión del reparto: lo que dicen hoy los archivos y lo que hay que cambiar para llegar al objetivo.', glosario: 'activar_sin_clic' });
}

function pestanaObjetivo(ctx, m) {
  const { ui } = ctx;
  const { el } = ui;
  return el('div', { class: 'qd-pila' },
    aviso(ui, 'objetivo', el('strong', null, 'Esto es el OBJETIVO, no lo que rige hoy.'),
      el('span', null, 'Es la decisión J2 que tomaste el 2026-11-06 («su modelo desde el día 1»). Todavía no está implementada: hoy activar una campaña sigue siendo una decisión tuya. Lo discontinuo es el destino; lo continuo, la realidad. ', ui.ayuda('objetivo_j2'))),
    el('div', { class: 'qd-fila' }, etiquetaObjetivo(ui)),
    seccionColumnas(ctx, m), seccionConserva(ctx, m), seccionFalta(ctx, m));
}

// ───────────────────────── pestaña FRENOS ─────────────────────────

function cajaVigente(ui, f) {
  const { el } = ui;
  const v = f.vigente;
  const relacion = { igual: ['Coincide con el objetivo', 'ok', 'check'], distinto: ['Distinto del objetivo', 'info', 'info'], otra_moneda: ['Otra moneda: no se compara', 'info', 'info'], sin_fijar: ['Sin fijar', 'aviso', 'candado'], sin_lectura: ['Sin lectura', 'neutro', 'info'] }[f.relacion];
  return el('div', { class: 'qd-caja' },
    el('span', { class: 'qd-fila qd-fila--junta' }, etiquetaHoy(ui, true)),
    v.valor !== null
      ? el('div', { class: 'qd-caja__valor' }, v.texto || String(v.valor))
      : el('div', { class: 'qd-caja__valor qd-caja__valor--vacio' }, f.relacion === 'sin_lectura' ? 'No se pudieron leer tus límites' : 'Sin fijar'),
    v.valor === null && f.relacion !== 'sin_lectura' ? el('span', { class: 'qd-sub' }, v.mensaje) : null,
    f.derivado && f.derivado.vigenteTexto ? el('span', { class: 'qd-sub' }, `Equivale a unos ${f.derivado.vigenteTexto} de presupuestos diarios sumados (× ${f.derivado.factor.replace('.', ',')}).`) : null,
    relacion && f.relacion !== 'sin_fijar' && f.relacion !== 'sin_lectura' ? ui.chip(relacion[0], relacion[1], { icono: relacion[2] }) : null);
}

function cajaObjetivo(ui, f) {
  const { el } = ui;
  return el('div', { class: 'qd-caja qd-caja--objetivo' },
    el('span', { class: 'qd-fila qd-fila--junta' }, etiquetaObjetivo(ui, true)),
    el('div', { class: 'qd-caja__valor' }, f.clave === 'gasto_diario_global' ? `${f.objetivo.texto} por día` : `${f.objetivo.texto} de pérdida`),
    el('span', { class: 'qd-sub' }, f.clave === 'gasto_diario_global' ? 'Techo para toda la empresa, no por oferta (decisión J4).' : 'Al llegar a esa pérdida acumulada: PAUSA general automática (decisión J4).'),
    f.derivado && f.derivado.objetivoTexto ? el('span', { class: 'qd-sub' }, `Equivale a unos ${f.derivado.objetivoTexto} de presupuestos diarios sumados, porque el techo se compara con el máximo teórico (× ${f.derivado.factor.replace('.', ',')}).`) : null);
}

function tarjetaFreno(ctx, f) {
  const { ui } = ctx;
  const { el } = ui;
  return el('article', { class: 'qd-freno' },
    el('div', { class: 'qd-freno__cab' }, el('h3', { class: 'qd-freno__titulo' }, ui.icono(f.clave === 'gasto_diario_global' ? 'dinero' : 'pausa', { tam: 18 }), f.titulo, ui.ayuda(f.glosario)), el('span', { class: 'qd-sub' }, f.pregunta)),
    el('div', { class: 'qd-freno__comparar' }, cajaVigente(ui, f), cajaObjetivo(ui, f)),
    el('span', { class: 'qd-sub' }, f.efecto),
    ui.soloTecnico(el('span', { class: 'qd-sub qd-mono' }, `limites.yaml · ${f.clave}`)));
}

function pestanaFrenos(ctx, m) {
  const { ui, estado } = ctx;
  const { el } = ui;
  if (!m.hay.limites) {
    return ui.seccion('Frenos de empresa', ui.vacioConPasos({
      titulo: 'No se pudieron leer tus límites', explicacion: 'Sin los límites no se pueden mostrar los frenos de empresa. El archivo (empresa/limites.yaml) viene en la plantilla; el panel lo lee sin modificarlo.', icono: 'candado',
      pasos: [{ texto: 'Comprueba si los límites alcanzan para gastar', comando: comandosFrenos(null).estado }],
    }), { glosario: 'frenos_empresa' });
  }
  const c = comandosFrenos(estado && estado.ofertaActiva);
  const F = m.frenos;
  return el('div', { class: 'qd-pila' },
    aviso(ui, 'info', el('strong', null, 'Los dos frenos que quedan cuando los robots prenden solos.'),
      el('span', null, 'Valen para toda la empresa, no por oferta. Hoy muestran lo que dicen tus límites; el objetivo (decisión J4, 2026-11-06) todavía no está firmado. ', ui.ayuda('frenos_empresa'))),
    ui.seccion('Cuánto se puede gastar y cuánto se puede perder', el('div', { class: 'qd-pila' },
      el('div', { class: 'qd-frenos' }, F.frenos.map((f) => tarjetaFreno(ctx, f))),
      F.moneda ? null : el('p', { class: 'qd-sub' }, 'Tus límites todavía no dicen en qué moneda están: el sistema la completa en la propuesta, a partir de la oferta.'),
      F.sello && F.sello.bloquea ? aviso(ui, 'aviso', el('strong', null, 'Tus límites no están firmados.'), el('span', null, 'Aunque los dos valores estuvieran escritos, sin tu firma nada gasta ni se activa. ', ui.termino('cierra_por_defecto', { texto: '¿Qué significa «sin fijar»?' }))) : null),
    { glosario: 'frenos_empresa' }),
    ui.seccion('Cómo proponerlos y firmarlos (lo haces tú)', el('div', { class: 'qd-pila' },
      el('p', { class: 'qd-sub' }, 'El sistema prepara la propuesta; la firma es solo tuya. El panel nunca cambia tus límites ni firma por ti: aquí solo ves los comandos exactos para que los copies y los ejecutes en tu terminal.'),
      ui.comando(c.proponer, { titulo: '1 · Preparar la propuesta', abierto: true, nota: 'No cambia tus límites: guarda la propuesta en un archivo aparte (empresa/propuestas/limites.propuesta.yaml).' }),
      ui.comando(c.ensayo, { titulo: '2 · Ensayo de la firma (no guarda nada)', abierto: true, nota: 'Revisa que la propuesta tenga el formato esperado y calcula la firma, sin guardar tus límites.' }),
      ui.comando(c.firmar, { titulo: '3 · Firmar y guardar tus límites', abierto: true, nota: 'Solo tú: necesita tu clave privada y el entorno de producción (FABRICA_ENTORNO=produccion). Es la única forma de guardar tus límites.' }),
      aviso(ui, 'objetivo', el('strong', null, 'Para que la propuesta traiga los 300 y los 3.000 de J4 falta implementar.'),
        el('span', null, 'Hoy la propuesta calcula el gasto y la pérdida máximos de la prueba de cada oferta; cargar el gasto máximo por día y la pérdida acumulada de J4 en la propuesta antes de firmar está pendiente (mira «Objetivo»). Si hace falta, edita esos dos valores en la propuesta antes del paso 2.')),
      ui.comando(c.estado, { titulo: 'Comprobar si los límites alcanzan para gastar', nota: 'Solo lectura.' })),
    { ayuda: 'Cambiar un límite es una decisión tuya, con tu firma, en los cinco niveles.', glosario: 'lim_sello' }));
}

// ───────────────────────── pestaña SIGUE SIENDO HUMANO ─────────────────────────

function chipsGateHumano(ui, h) {
  const { el } = ui;
  const una = (g, rotulo) => {
    if (!g) return null;
    if (!g.gate) return el('span', { class: 'qd-sub' }, `${rotulo ? `${rotulo}: ` : ''}sin leer la tabla de puntos de control`);
    const detalle = g.constante ? 'igual en los cinco niveles' : g.limitada ? `la tabla llega a «${GATES_INFO[g.tablaPermite].etiqueta.toLowerCase()}» en los niveles altos, pero rige tu firma` : 'según el nivel de la etapa';
    return el('span', { class: 'qd-fila qd-fila--junta' }, chipGate(ui, g.gate), el('span', { class: 'qd-sub' }, `${rotulo ? `${rotulo}: ` : ''}${detalle}`));
  };
  if (!h.gate && !h.gate2) return el('span', { class: 'qd-fila qd-fila--junta' }, ui.chip('No pasa por la tabla de puntos de control', 'neutro', { icono: 'circulo-punteado' }), el('span', { class: 'qd-sub' }, 'solo tú borras el archivo'));
  return el('div', { class: 'qd-pila qd-pila--chica' }, una(h.gate, h.gate2 ? 'Cambiar la guía de trabajo o una regla' : ''), una(h.gate2, h.gate2 ? 'Cambiar los límites' : ''));
}

function tarjetaHumano(ctx, h) {
  const { ui } = ctx;
  const { el } = ui;
  return el('article', { class: 'qd-card' },
    el('h3', { class: 'qd-card__titulo' }, ui.icono(h.icono, { tam: 18 }), h.titulo, ui.ayuda(h.glosario)),
    chipsGateHumano(ui, h),
    el('p', { class: 'qd-sub' }, h.porque),
    ui.chip(h.actual.texto, h.actual.tono, { icono: h.actual.icono }),
    el('ol', { class: 'qd-pasos' }, h.pasos.map((p) => el('li', null, p))),
    h.comandos.length ? el('div', { class: 'qd-pila' }, h.comandos.map((c) => ui.comando(c.cmd, { titulo: c.titulo, nota: c.nota }))) : null,
    h.ruta ? el('a', { class: 'btn btn--chico', href: h.ruta }, h.rutaTexto, ui.icono('flecha-derecha', { tam: 13 })) : null);
}

function pestanaHumano(ctx, m) {
  const { ui } = ctx;
  const { el } = ui;
  return el('div', { class: 'qd-pila' },
    aviso(ui, 'info', el('strong', null, 'Aunque los robots prendan y apaguen solos, estas decisiones seguirán siendo tuyas.'),
      el('span', null, 'Son decisiones que abren un riesgo nuevo o que no se pueden deshacer, en un negocio con una sola cuenta de Meta y una de Stripe. El panel nunca las ejecuta: te muestra el estado de hoy y el comando exacto. ', ui.ayuda('sigue_humano'))),
    el('div', { class: 'qd-fila' }, etiquetaHoy(ui), el('span', { class: 'qd-sub' }, 'Estas reglas rigen hoy y se mantienen en el objetivo J2.')),
    el('div', { class: 'qd-humano' }, m.humano.map((h) => tarjetaHumano(ctx, h))));
}

// ───────────────────────── cabecera y página ─────────────────────────

const botonActualizar = (ctx) => ctx.ui.el('button', { type: 'button', class: 'btn btn--chico', onclick: () => ctx.recargar() }, ctx.ui.icono('refrescar', { tam: 14 }), 'Actualizar');

function cartel(ctx, m) {
  const { ui } = ctx;
  const { el } = ui;
  const msg = mensajesBanner(m);
  return el('div', { class: 'qd-banner' },
    el('section', { class: 'qd-bloque qd-bloque--hoy', 'aria-label': 'Hoy' }, etiquetaHoy(ui), el('div', { class: 'qd-bloque__titulo' }, msg.hoy.titulo), el('p', { class: 'qd-bloque__texto' }, msg.hoy.detalle)),
    el('section', { class: 'qd-bloque qd-bloque--objetivo', 'aria-label': 'Objetivo' }, etiquetaObjetivo(ui), el('div', { class: 'qd-bloque__titulo' }, msg.objetivo.titulo), el('p', { class: 'qd-bloque__texto' }, msg.objetivo.detalle)));
}

function franjaMetricas(ctx, m) {
  const { ui, fmt } = ctx;
  return ui.el('div', { class: 'qd-metricas' }, metricasQuienDecide(m, fmt).map((x) => ui.metrica({ etiqueta: x.etiqueta, valor: x.valor, contexto: x.contexto, tono: x.tono, ayuda: x.ayuda })));
}

/** Junta los tres sobres en uno para el pie «leído hace…» (fuentes, hora más reciente y avisos). */
function sobreCombinado(sobres) {
  const ok = sobres.filter(Boolean);
  const fuente = [...new Set(ok.flatMap((s) => (Array.isArray(s.fuente) ? s.fuente : [])))];
  const horas = ok.map((s) => s.generado_en).filter(Boolean).sort();
  return { fuente, generado_en: horas.length ? horas[horas.length - 1] : undefined, vacio: false, avisos: [...new Set(ok.flatMap((s) => (Array.isArray(s.avisos) ? s.avisos : [])))].slice(0, 6) };
}

export async function render(ctx) {
  const { api, ui, fmt } = ctx;
  const { el } = ui;
  ui.instalarEstilos('n4-quien-decide', ESTILOS_N4_QUIEN_DECIDE);
  const cabecera = (pestanas) => ui.encabezadoPagina({
    titulo: 'Quién decide qué',
    descripcion: 'Quién decide cada paso hoy (tú, el sistema o los programas automáticos), leído de los archivos reales, y el reparto al que quieres llegar: los robots prenden, suben, apagan y frenan solos dentro de frenos de empresa. Aquí solo se mira.',
    acciones: [botonActualizar(ctx)], pestanas,
  });
  const [rg, rp, rs] = await Promise.allSettled([api.sobre('/gates'), api.sobre('/parametros'), api.sobre('/sistema')]);
  const sg = rg.status === 'fulfilled' ? rg.value : null;
  const sp = rp.status === 'fulfilled' ? rp.value : null;
  const ss = rs.status === 'fulfilled' ? rs.value : null;
  if (!sg && !sp && !ss) {
    return el('div', { class: 'pagina qd' }, cabecera(null), ui.errorBox(rg.reason || rp.reason || rs.reason, { reintentar: () => ctx.recargar() }));
  }
  const m = modeloQuienDecide({ gates: sg ? sg.datos : null, parametros: sp ? sp.datos : null, sistema: ss ? ss.datos : null }, fmt);
  const panel = el('div', { class: 'qd-pila', role: 'tabpanel', 'aria-live': 'polite' });
  const pintar = () => {
    const f = { hoy: pestanaHoy, objetivo: pestanaObjetivo, frenos: pestanaFrenos, humano: pestanaHumano }[UI.pestana] || pestanaHoy;
    ui.reemplazar(panel, f(ctx, m));
  };
  if (!['hoy', 'objetivo', 'frenos', 'humano'].includes(UI.pestana)) UI.pestana = 'hoy';
  const barra = ui.barraPestanas({ items: pestanasQuienDecide(m), activo: UI.pestana, etiqueta: 'Secciones de Quién decide qué', onCambio: (id) => { UI.pestana = id; pintar(); } });
  pintar();
  const faltan = m.faltan.length ? aviso(ui, 'aviso', el('strong', null, `No se pudo leer ${m.faltan.map((f) => NOMBRE_ARCHIVO[f] || f).join(', ')}.`), ui.soloTecnico(el('span', { class: 'qd-mono' }, ` (${m.faltan.join(', ')})`)), el('span', null, ' '), el('span', null, 'Lo que depende de ese archivo se marca como «no se pudo comprobar»; el resto de la pantalla sigue siendo fiel a lo que sí se leyó.')) : null;
  return el('div', { class: 'pagina qd' },
    cabecera(barra), cartel(ctx, m), franjaMetricas(ctx, m), faltan, panel,
    ui.fuenteInfo(sobreCombinado([sg, sp, ss])),
    el('p', { class: 'qd-sub' }, 'Esta pantalla no cambia nada: los puntos de control, los límites y los niveles de autonomía los cambias tú, con tu firma, desde la terminal.'));
}

/** Actualización en vivo: vuelve a leer conservando la pestaña, el filtro y la búsqueda, salvo que se esté escribiendo. */
export async function alCambio(ctx) {
  if (hayEdicion()) return undefined;
  return render(ctx);
}
