// Pruebas del rediseño (U0): sistema de diseño, piezas comunes de ui.js, glosario, estado (modo técnico y densidad), paleta de comandos,
// atajos, popovers, iconos y tokens CSS. Sin navegador: `node --test` con el DOM mínimo y estricto de tests/fixtures/dashboard/shell/dom_falso.mjs.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import { instalar, buscar, buscarTodos } from '../fixtures/dashboard/shell/dom_falso.mjs';

const AQUI = dirname(fileURLToPath(import.meta.url));
const WEB = join(AQUI, '..', '..', 'dashboard', 'web');
const doc = instalar();

const estadoMod = await import('../../dashboard/web/estado.js');
const ui = await import('../../dashboard/web/ui.js');
const app = await import('../../dashboard/web/app.js');
const glosario = await import('../../dashboard/web/lib/glosario.js');
const indice = await import('../../dashboard/web/lib/glosario-indice.js');
const iconos = await import('../../dashboard/web/lib/iconos.js');
const paleta = await import('../../dashboard/web/lib/paleta.js');
const atajos = await import('../../dashboard/web/lib/atajos.js');
const popover = await import('../../dashboard/web/lib/popover.js');

const { fmt, el } = ui;
const NBSP = ' ';
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));
const leer = (rel) => readFileSync(join(WEB, rel), 'utf8');
function almacenFalso(inicial = {}) {
  const m = new Map(Object.entries(inicial));
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), _m: m };
}

// ───────────────────────── glosario ─────────────────────────

const MINIMOS = [
  'gate_a', 'gate_s', 'gate_h', 'nivel_n0', 'nivel_n1', 'nivel_n2', 'nivel_n3', 'nivel_n4', 'preflight', 'sello_x1', 'pausa', 'freno_captura', 'hash_config',
  'borrador', 'preflight_ok', 'aprobada', 'activa', 'traccion', 'piso_medido', 'indeterminado_muestra', 'pm', 'puertas', 'transferibilidad', 'exportador',
  'cpa', 'cpa_equilibrio', 'compras_netas', 'ratio_reembolsos', 'conciliacion', 'veredicto', 'validada', 'prometedora', 'fallida', 'inconclusa',
  'regla_k', 'regla_g', 'regla_m', 'ronda_qa', 'defectos_sembrados', 'skill_v01', 'skill_v1', 'dod',
];

test('glosario: contiene todos los términos mínimos del contrato y cada entrada tiene definición legible', () => {
  for (const k of MINIMOS) assert.ok(glosario.GLOSARIO[k], `falta el término «${k}»`);
  for (const [k, d] of Object.entries(glosario.GLOSARIO)) {
    assert.match(k, /^[a-z0-9_]+$/, `clave ${k}: snake_case ASCII`);
    assert.equal(typeof d.corto, 'string', k);
    assert.ok(d.corto.length >= 12 && d.corto.length <= 200, `${k}: «corto» entre 12 y 200 caracteres (${d.corto.length})`);
    if (d.largo !== undefined) assert.ok(d.largo.length > d.corto.length / 2, `${k}: «largo» no es más corto que «corto»`);
    if (d.nombre !== undefined) assert.ok(d.nombre.length <= 60, `${k}: nombre largo`);
    assert.doesNotMatch(d.corto, /<|>|\{\{/, `${k}: sin marcado`);
  }
  assert.equal(glosario.CLAVES_GLOSARIO.length, Object.keys(glosario.GLOSARIO).length);
});

test('glosario: el texto principal es de negocio y el nombre técnico queda como término secundario', () => {
  assert.equal(glosario.GLOSARIO.gate_h.nombre, 'Espera tu firma');
  assert.equal(glosario.GLOSARIO.gate_h.tecnico, 'gate H');
  assert.match(glosario.GLOSARIO.traccion.corto, /15 anuncios/);
  assert.match(glosario.GLOSARIO.traccion.corto, /10 días/);
  assert.equal(glosario.GLOSARIO.hash_config.tecnico.split(' ')[0], 'hash_config');
});

test('glosario: el nombre y la definición corta (lo que se lee primero) no usan jerga; lo técnico va en `tecnico`', async () => {
  const piezas = await import('../../dashboard/web/lib/glosario-piezas.js');
  const robots = await import('../../dashboard/web/lib/glosario-robots.js');
  const JERGA = /\b(gate|preflight|hash|sello|sellad[oa]|QA|Maker|motor|CBO|CPA|ROAS|checkout|bump|ledger|dry-run|JSON|YAML|latidos?|locale|SSE|token|snapshot|DoD|skills?|payload|script)\b/i;
  for (const [origen, t] of [['glosario', glosario.GLOSARIO], ['piezas', piezas.TERMINOS], ['robots', robots.TERMINOS]]) {
    for (const [k, d] of Object.entries(t)) {
      assert.doesNotMatch(`${d.nombre || ''} ${d.corto}`, JERGA, `${origen}.${k}: jerga en el primer renglón`);
      if (d.largo) assert.doesNotMatch(d.largo, JERGA, `${origen}.${k}: jerga en la definición larga`);
    }
  }
});

test('glosario-indice: incluye el base, mezcla fragmentos sin pisar y descarta entradas inválidas (importación tolerante)', () => {
  for (const k of MINIMOS) assert.ok(indice.GLOSARIO_TOTAL[k], k);
  const destino = { a: { corto: 'definición base de a' } };
  const conflictos = [];
  const anadidas = indice.mezclarTerminos(destino, {
    a: { corto: 'intento de pisar a' },
    b: { nombre: 'B', corto: 'definición de b', tecnico: 'campo_b' },
    'Mala Clave': { corto: 'clave inválida' },
    c: { largo: 'sin corto' },
    d: null,
    e: 'texto',
  }, 'prueba', conflictos);
  assert.deepEqual(anadidas, ['b']);
  assert.equal(destino.a.corto, 'definición base de a', 'el base manda');
  assert.deepEqual(conflictos, [{ clave: 'a', origen: 'prueba', ganador: 'global' }]);
  assert.deepEqual(indice.mezclarTerminos({}, null), []);
  assert.deepEqual(indice.mezclarTerminos({}, 'x'), []);
  assert.equal(indice.buscarTermino('gate_h').nombre, 'Espera tu firma');
  assert.equal(indice.buscarTermino('no_existe'), null);
  assert.equal(indice.buscarTermino('__proto__'), null);
  assert.equal(indice.buscarTermino(42), null);
  assert.equal(indice.humanizarClave('hash_config'), 'Hash config');
  assert.equal(indice.humanizarClave(''), '');
  assert.ok(Array.isArray(indice.CARGADOS));
  // un fragmento por agente de página: los cuatro de siempre abren la lista y las pantallas nuevas (robots, decisiones…) añaden el suyo sin romper este orden
  assert.deepEqual(indice.FRAGMENTOS.slice(0, 4), ['resumen', 'ofertas', 'descubrimiento', 'operacion']);
  assert.equal(new Set(indice.FRAGMENTOS).size, indice.FRAGMENTOS.length, 'ningún fragmento repetido');
  for (const f of indice.FRAGMENTOS) assert.match(f, /^[a-z][a-z0-9-]*$/, `fragmento «${f}»`);
});

// ───────────────────────── formato ─────────────────────────

test('fmt.numero: es-ES, decimales, compacto, signo; inválido → «—»; el cero es un dato', () => {
  assert.equal(fmt.numero(0), '0');
  assert.equal(fmt.numero(1234567), '1.234.567');
  assert.equal(fmt.numero(1234.5, { decimales: 1 }), '1.234,5');
  assert.equal(fmt.numero(-1000), '-1.000');
  assert.equal(fmt.numero(12345, { compacto: true }), `12,3${NBSP}k`);
  assert.equal(fmt.numero(1500000, { compacto: true }), `1,5${NBSP}M`);
  assert.equal(fmt.numero(2000, { compacto: true }), `2${NBSP}k`);
  assert.equal(fmt.numero(950, { compacto: true }), '950');
  assert.equal(fmt.numero(5, { signo: true }), '+5');
  assert.equal(fmt.numero(-5, { signo: true }), '-5');
  assert.equal(fmt.numero(0, { signo: true }), '0');
  for (const malo of [null, undefined, NaN, Infinity, '12', {}]) assert.equal(fmt.numero(malo), '—', String(malo));
  assert.equal(fmt.num(1234), '1.234', 'fmt.num sigue igual');
});

test('fmt.relativo y fmt.pct conservan su contrato; ui.tiempo pone la fecha absoluta en el title', () => {
  const t = Date.parse('2026-11-06T14:00:00Z');
  assert.equal(fmt.relativo('2026-11-06T14:00:00Z', t + 3 * 3600000), 'hace 3 h');
  assert.equal(fmt.pct(1250), `12,5${NBSP}%`);
  const n = ui.tiempo('2026-11-06T14:00:00Z', { ahora: t + 5 * 60000 });
  assert.equal(n.tagName, 'TIME');
  assert.equal(n.textContent, 'hace 5 min');
  assert.match(n.getAttribute('title'), /\d{2}\/\d{2}\/2026/);
  assert.equal(n.getAttribute('datetime'), '2026-11-06T14:00:00.000Z');
  assert.equal(ui.tiempo('basura').textContent, '—');
  assert.equal(ui.tiempo(null).textContent, '—');
});

// ───────────────────────── estado: modo técnico y densidad ─────────────────────────

test('estado: modoTecnico (apagado) y densidad (cómoda) por defecto; claves fab.* y suscripción', () => {
  const al = almacenFalso();
  const e = estadoMod.crearEstado(al);
  assert.equal(e.modoTecnico, false);
  assert.equal(e.densidad, 'comoda');
  const avisos = [];
  e.suscribir((_s, cambios) => avisos.push(cambios));
  assert.deepEqual(e.fijar({ modoTecnico: true }), ['modoTecnico']);
  assert.deepEqual(e.fijar({ modoTecnico: true }), [], 'sin cambio no notifica');
  assert.deepEqual(e.fijar({ densidad: 'compacta' }), ['densidad']);
  assert.deepEqual(avisos, [['modoTecnico'], ['densidad']]);
  assert.equal(al._m.get('fab.modoTecnico'), 'true');
  assert.equal(al._m.get('fab.densidad'), '"compacta"');
  assert.equal(al._m.has('panel.modoTecnico'), false, 'las claves nuevas no llevan el prefijo panel.');
  const e2 = estadoMod.crearEstado(al);
  assert.equal(e2.modoTecnico, true);
  assert.equal(e2.densidad, 'compacta');
  assert.equal(estadoMod.CLAVES_ALMACEN.modoTecnico, 'fab.modoTecnico');
  assert.equal(estadoMod.CLAVES_ALMACEN.densidad, 'fab.densidad');
});

test('estado: valores a mano, corruptos o fuera de dominio no rompen nada', () => {
  assert.equal(estadoMod.crearEstado(almacenFalso({ 'fab.modoTecnico': 'true', 'fab.densidad': 'compacta' })).modoTecnico, true, 'sin comillas también vale');
  assert.equal(estadoMod.crearEstado(almacenFalso({ 'fab.densidad': 'compacta' })).densidad, 'compacta');
  const malo = estadoMod.crearEstado(almacenFalso({ 'fab.modoTecnico': '{roto', 'fab.densidad': '"gigante"' }));
  assert.equal(malo.modoTecnico, false);
  assert.equal(malo.densidad, 'comoda');
  const e = estadoMod.crearEstado(null);
  assert.deepEqual(e.fijar({ densidad: 'enorme' }), []);
  assert.deepEqual(e.fijar({ modoTecnico: 'sí' }), [], 'solo true/«true»/1 encienden el modo');
  assert.deepEqual(e.fijar({ modoTecnico: 'true' }), ['modoTecnico']);
  assert.deepEqual(estadoMod.DENSIDADES, ['comoda', 'compacta']);
});

test('modo técnico: detalleTecnico y comando siguen el interruptor global; `abierto: true` y el contenido diferido se respetan', () => {
  estadoMod.estado.fijar({ modoTecnico: false });
  let montajes = 0;
  const cerrado = ui.detalleTecnico('Rutas', () => { montajes += 1; return el('p', null, 'ruta/archivo.json'); });
  const fijo = ui.detalleTecnico('Siempre abierto', el('p', null, 'x'), { abierto: true });
  const cmd = ui.comando('python -m x');
  const cmdAbierto = ui.comando('python -m y', { abierto: true });
  doc.body.append(cerrado, fijo, cmd, cmdAbierto);
  assert.equal(cerrado.open, false, 'apagado = resumen');
  assert.equal(fijo.open, true);
  assert.equal(cmd.open, false, 'un comando no se muestra abierto salvo que sea LA acción');
  assert.equal(cmdAbierto.open, true);
  assert.equal(montajes, 0, 'cerrado no construye el contenido');
  assert.equal(buscar(cerrado, '.detalle-tecnico__marca').textContent, 'técnico');

  estadoMod.estado.fijar({ modoTecnico: true });
  assert.equal(cerrado.open, true, 'encendido = todo expandido');
  assert.equal(cmd.open, true);
  assert.equal(montajes, 1, 'se construye al abrir');
  assert.match(cerrado.textContent, /ruta\/archivo\.json/);
  assert.equal(doc.documentElement.dataset.tecnico, 'true');

  estadoMod.estado.fijar({ modoTecnico: false });
  assert.equal(cerrado.open, false);
  assert.equal(cmd.open, false);
  assert.equal(fijo.open, true, 'lo marcado `abierto` no se cierra');
  assert.equal(cmdAbierto.open, true);
  assert.equal(doc.documentElement.dataset.tecnico, 'false');
  assert.equal(montajes, 1, 'el contenido ya construido no se repite');

  const nuevo = ui.detalleTecnico('Creado con el modo encendido', el('p', null, 'x'));
  estadoMod.estado.fijar({ modoTecnico: true });
  const creado = ui.detalleTecnico('Nace abierto', el('p', null, 'y'));
  assert.equal(creado.open, true);
  assert.equal(nuevo.open, false, 'no estaba en el DOM: no lo toca la sincronización');
  estadoMod.estado.fijar({ modoTecnico: false });
});

test('densidad: se refleja en <html data-densidad> y vuelve a cómoda', () => {
  estadoMod.estado.fijar({ densidad: 'compacta' });
  assert.equal(doc.documentElement.dataset.densidad, 'compacta');
  estadoMod.estado.fijar({ densidad: 'comoda' });
  assert.equal(doc.documentElement.dataset.densidad, 'comoda');
  assert.equal(ui.instalarPreferencias(), false, 'segunda instalación: no duplica el suscriptor');
});

test('comando: Copiar visible sin abrir, texto exacto, nota y compatibilidad con la firma anterior', () => {
  const c = ui.comando('.venv/bin/python -m engine.orq firmar --oferta X', { nota: 'Lo firmas tú.', titulo: 'Cómo firmar' });
  assert.equal(c.tagName, 'DETAILS');
  assert.equal(buscar(c, '.comando__titulo').textContent, 'Cómo firmar');
  assert.equal(buscar(c, '.comando__texto').textContent, '.venv/bin/python -m engine.orq firmar --oferta X');
  assert.equal(buscar(c, '.comando__nota').textContent, 'Lo firmas tú.');
  assert.match(buscar(c, 'button').getAttribute('aria-label'), /^Copiar comando: \.venv/);
  assert.equal(buscar(ui.comando('x'), '.comando__titulo').textContent, 'Cómo hacerlo');
  const ev = buscar(c, 'button').click();
  assert.equal(ev.defaultPrevented, true, 'copiar no abre ni cierra el bloque');
  assert.match(ui.comando('x', { etiqueta: 'Copiar' }).html, /aria-label="Copiar: x"/);
});

// ───────────────────────── iconos ─────────────────────────

test('iconos: set propio completo, trazo de 1,75 px y currentColor; alias y nombres desconocidos', () => {
  const requeridos = ['check', 'reloj', 'alerta', 'candado', 'flecha', 'copiar', 'info', 'lupa', 'cerrar', 'filtro', 'enlace-externo', 'carpeta', 'archivo', 'chispa', 'pausa', 'play',
    'usuario', 'firma', 'grafico', 'cartera', 'globo', 'caja', 'pantalla', 'megafono', 'escudo', 'engranaje', 'cumplimiento',
    'robot', 'cerebro', 'fabrica', 'bolsa', 'balanza', 'campana', 'tarjeta', 'mundo']; // los 7 últimos: las piezas del sistema en el sidebar
  for (const n of requeridos) assert.ok(iconos.NOMBRES_ICONOS.includes(n), `falta el icono «${n}»`);
  const svg = ui.icono('check', { tamano: 20 });
  assert.equal(svg.getAttribute('stroke-width'), '1.75');
  assert.equal(svg.getAttribute('stroke'), 'currentColor');
  assert.equal(svg.getAttribute('width'), '20');
  assert.equal(svg.getAttribute('aria-hidden'), 'true');
  assert.equal(ui.icono('check', { tam: 12 }).getAttribute('height'), '12', 'tam sigue valiendo');
  assert.equal(ui.icono('check').getAttribute('width'), '16');
  const con = ui.icono('info', { etiqueta: 'Información' });
  assert.equal(con.getAttribute('role'), 'img');
  assert.equal(con.getAttribute('aria-label'), 'Información');
  assert.equal(con.hasAttribute('aria-hidden'), false);
  for (const n of iconos.NOMBRES_ICONOS) assert.ok(ui.icono(n).querySelector('*'), n);
  assert.equal(iconos.resolverIcono('buscar'), 'lupa');
  assert.equal(iconos.resolverIcono('producto'), 'caja');
  assert.equal(iconos.resolverIcono('constructor'), null, 'sin heredar del prototipo');
  assert.equal(iconos.resolverIcono(null), null);
  assert.deepEqual(iconos.trazosDe('no-existe'), iconos.ICONOS.lista, 'desconocido → icono de reserva');
  for (const e of app.ENTRADAS) assert.ok(iconos.NOMBRES_ICONOS.includes(e.icono), `${e.ruta}: ${e.icono}`);
  for (const [nombre, trazos] of Object.entries(iconos.ICONOS)) {
    for (const [tag, atr] of trazos) { assert.ok(['path', 'circle', 'line', 'polyline', 'polygon', 'rect', 'ellipse'].includes(tag), `${nombre}: etiqueta ${tag}`); assert.equal(typeof atr, 'object'); }
  }
  for (const [alias, destino] of Object.entries(iconos.ALIAS)) assert.ok(Object.prototype.hasOwnProperty.call(iconos.ICONOS, destino), `el alias «${alias}» apunta a «${destino}», que no existe`);
});

// Límites de un trazo dentro del lienzo de 24×24 (puro): círculo, rect, línea, elipse, polilínea y path (M L H V C S Q T A Z, absolutos y relativos; de los arcos solo se miran los extremos).
function limitesDeTrazo([tag, a]) {
  const xs = []; const ys = [];
  const punto = (x, y) => { xs.push(x); ys.push(y); };
  if (tag === 'circle') { punto(a.cx - a.r, a.cy - a.r); punto(a.cx + a.r, a.cy + a.r); }
  else if (tag === 'ellipse') { punto(a.cx - a.rx, a.cy - a.ry); punto(a.cx + a.rx, a.cy + a.ry); }
  else if (tag === 'rect') { punto(a.x, a.y); punto(a.x + a.width, a.y + a.height); }
  else if (tag === 'line') { punto(a.x1, a.y1); punto(a.x2, a.y2); }
  else if (tag === 'polyline' || tag === 'polygon') { const n = a.points.trim().split(/[\s,]+/).map(Number); for (let i = 0; i < n.length; i += 2) punto(n[i], n[i + 1]); }
  else if (tag === 'path') {
    const partes = a.d.match(/[a-zA-Z]|-?\d*\.?\d+(?:e-?\d+)?/g);
    const largo = { m: 2, l: 2, h: 1, v: 1, c: 6, s: 4, q: 4, t: 2, a: 7, z: 0 };
    let x = 0; let y = 0; let x0 = 0; let y0 = 0; let cmd = null; let i = 0;
    while (i < partes.length) {
      if (/[a-zA-Z]/.test(partes[i])) { cmd = partes[i]; i += 1; if (cmd === 'z' || cmd === 'Z') { x = x0; y = y0; continue; } }
      const k = cmd.toLowerCase(); const rel = cmd === k;
      const v = partes.slice(i, i + largo[k]).map(Number); i += largo[k];
      if (k === 'h') x = rel ? x + v[0] : v[0];
      else if (k === 'v') y = rel ? y + v[0] : v[0];
      else {
        const pares = k === 'a' ? [[v[5], v[6]]] : v.reduce((acc, n, j) => (j % 2 === 0 ? [...acc, [n, v[j + 1]]] : acc), []);
        for (const [px, py] of pares) punto(rel ? x + px : px, rel ? y + py : py);
        const [ex, ey] = pares[pares.length - 1];
        x = rel ? x + ex : ex; y = rel ? y + ey : ey;
        if (k === 'm') { x0 = x; y0 = y; cmd = rel ? 'l' : 'L'; }
      }
      punto(x, y);
    }
  }
  return { x0: Math.min(...xs), x1: Math.max(...xs), y0: Math.min(...ys), y1: Math.max(...ys) };
}

test('iconos de las piezas (cerebro, fabrica, bolsa, balanza, campana, tarjeta, mundo): trazo de 1,75 px, solo contorno, caben en 24×24 con margen y no copian a otro', () => {
  const nuevos = ['cerebro', 'fabrica', 'bolsa', 'balanza', 'campana', 'tarjeta', 'mundo'];
  for (const n of nuevos) {
    assert.ok(Object.prototype.hasOwnProperty.call(iconos.ICONOS, n), `${n}: existe como icono propio`);
    assert.equal(iconos.resolverIcono(n), n, `${n}: se resuelve a sí mismo, no a un alias`);
    const svg = ui.icono(n, { tam: 18 });
    assert.equal(svg.getAttribute('stroke-width'), '1.75', `${n}: trazo de 1,75 px como el resto`);
    assert.equal(svg.getAttribute('stroke'), 'currentColor');
    assert.equal(svg.getAttribute('fill'), 'none', `${n}: contorno, no relleno`);
    assert.equal(svg.getAttribute('viewBox'), '0 0 24 24');
    assert.equal(svg.getAttribute('aria-hidden'), 'true');
    assert.ok(buscarTodos(svg, 'path, circle, line, rect, ellipse').length >= 1, `${n}: dibuja algo`);
    for (const trazo of iconos.ICONOS[n]) {
      assert.equal('fill' in trazo[1], false, `${n}: ningún trazo con relleno propio`);
      const b = limitesDeTrazo(trazo);
      for (const v of Object.values(b)) assert.ok(Number.isFinite(v), `${n}: coordenadas válidas`);
      assert.ok(b.x0 >= 1 && b.y0 >= 1 && b.x1 <= 23 && b.y1 <= 23, `${n}: se sale del lienzo (${JSON.stringify(b)}) y el trazo de 1,75 px se recortaría`);
    }
    const firma = JSON.stringify(iconos.ICONOS[n]);
    for (const [otro, trazos] of Object.entries(iconos.ICONOS)) if (otro !== n) assert.notEqual(JSON.stringify(trazos), firma, `${n} es idéntico a ${otro}`);
  }
  assert.equal(iconos.resolverIcono('campana'), 'campana', 'la campana de aviso ya no es un alias de megáfono');
  assert.equal(iconos.resolverIcono('campaña'), 'megafono', 'la campaña de anuncios sigue siendo el megáfono');
  assert.equal(iconos.resolverIcono('mercado'), 'globo');
  assert.notDeepEqual(iconos.ICONOS.mundo, iconos.ICONOS.globo);
  // el medidor de límites funciona (no da por buenos trazos fuera del lienzo)
  assert.deepEqual(limitesDeTrazo(['path', { d: 'M2 3L10 4h5v6' }]), { x0: 2, x1: 15, y0: 3, y1: 10 });
  assert.deepEqual(limitesDeTrazo(['path', { d: 'M2 3l8 1h5v6z' }]), { x0: 2, x1: 15, y0: 3, y1: 10 });
  assert.equal(limitesDeTrazo(['circle', { cx: 12, cy: 12, r: 14 }]).x0, -2);
  assert.equal(limitesDeTrazo(['path', { d: 'M12 12a3 3 0 0 0 30 0' }]).x1, 42);
  // y las 14 pantallas de antes conservan su icono, y las nueve nuevas usan los pedidos
  for (const e of app.ENTRADAS) assert.ok(iconos.NOMBRES_ICONOS.includes(e.icono), `${e.ruta}: ${e.icono}`);
  const por = Object.fromEntries(app.ENTRADAS.map((e) => [e.ruta, e.icono]));
  assert.deepEqual([por.cerebro, por.fabrica, por.poscompra, por.jurado, por.robots, por.avisos, por.pagos, por.paises, por['quien-decide']], ['cerebro', 'fabrica', 'bolsa', 'balanza', 'rayo', 'campana', 'tarjeta', 'mundo', 'escudo']);
});

// ───────────────────────── popovers ─────────────────────────

test('popover (geometría): debajo por defecto, vuelca arriba si no cabe, se queda dentro de la ventana y la flecha apunta al ancla', () => {
  const vista = { width: 1000, height: 700 };
  const pop = { width: 300, height: 120 };
  const centro = popover.posicionarPopover({ left: 450, top: 100, width: 100, height: 30 }, pop, vista);
  assert.equal(centro.lado, 'abajo');
  assert.equal(centro.top, 138);
  assert.equal(centro.left, 350);
  assert.equal(centro.flecha, 150);
  const abajoJusto = popover.posicionarPopover({ left: 450, top: 650, width: 100, height: 30 }, pop, vista);
  assert.equal(abajoJusto.lado, 'arriba', 'no cabe debajo y arriba hay más sitio');
  assert.equal(abajoJusto.top, 650 - 8 - 120);
  const izq = popover.posicionarPopover({ left: 2, top: 100, width: 20, height: 20 }, pop, vista);
  assert.equal(izq.left, 8, 'margen de 8 px');
  assert.equal(izq.flecha, 12, 'la flecha nunca se sale del popover');
  const der = popover.posicionarPopover({ left: 990, top: 100, width: 8, height: 20 }, pop, vista);
  assert.equal(der.left, 1000 - 300 - 8);
  assert.ok(der.flecha <= 288);
  const pref = popover.posicionarPopover({ left: 450, top: 300, width: 100, height: 30 }, pop, vista, { preferido: 'arriba' });
  assert.equal(pref.lado, 'arriba');
  const diminuta = popover.posicionarPopover({ left: 10, top: 10, width: 10, height: 10 }, { width: 900, height: 900 }, { width: 400, height: 300 });
  assert.ok(diminuta.left >= 8 && diminuta.top >= 8, 'un popover mayor que la ventana no sale por arriba/izquierda');
  assert.deepEqual(popover.normalizarRect({ left: 5, top: 6, right: 25, bottom: 46 }), { left: 5, top: 6, width: 20, height: 40, right: 25, bottom: 46 });
  assert.equal(popover.cierraConTecla('Escape'), true);
  assert.equal(popover.cierraConTecla('Enter'), false);
});

test('popover (estados): hover efímero, clic fija, segundo clic/Esc/fuera cierran', () => {
  const t = popover.transicionPopover;
  assert.deepEqual(t({ abierto: false, fijo: false }, 'entra'), { abierto: true, fijo: false, accion: 'abrir' });
  assert.equal(t({ abierto: true, fijo: false }, 'sale').accion, 'programar_cierre');
  assert.equal(t({ abierto: true, fijo: true }, 'sale').accion, null, 'fijado: salir no lo cierra');
  assert.equal(t({ abierto: true, fijo: false }, 'entra').accion, 'cancelar_cierre');
  assert.deepEqual(t({ abierto: true, fijo: false }, 'clic'), { abierto: true, fijo: true, accion: 'cancelar_cierre' });
  assert.deepEqual(t({ abierto: true, fijo: true }, 'clic'), { abierto: false, fijo: false, accion: 'cerrar' });
  assert.deepEqual(t({ abierto: false, fijo: false }, 'clic'), { abierto: true, fijo: true, accion: 'abrir' });
  assert.equal(t({ abierto: true, fijo: true }, 'esc').accion, 'cerrar');
  assert.equal(t({ abierto: true, fijo: true }, 'fuera').accion, 'cerrar');
  assert.equal(t({ abierto: false, fijo: false }, 'esc').accion, null);
  assert.equal(t(null, 'inventado').accion, null);
});

test('popover (DOM): foco abre, Esc cierra y devuelve el foco, clic fija, clic fuera cierra y solo hay uno abierto', () => {
  const a = el('button', { type: 'button' }, 'A'); const b = el('button', { type: 'button' }, 'B'); const fuera = el('p', null, 'fuera');
  doc.body.append(a, b, fuera);
  const pa = ui.popover(a, () => el('p', null, 'contenido A'), { retardo: 0 });
  const pb = ui.popover(b, el('p', null, 'contenido B'), { retardo: 0, rol: 'dialog', etiqueta: 'Panel B' });
  const nodo = () => doc.body.querySelector('.popover');

  a.disparar('focus');
  assert.equal(nodo().hidden, false);
  assert.equal(nodo().getAttribute('role'), 'tooltip');
  assert.match(nodo().textContent, /contenido A/);
  assert.equal(a.getAttribute('aria-describedby'), nodo().id);
  assert.equal(pa.abierto(), true);
  assert.equal(doc.escuchas.get('keydown').length >= 1, true);

  b.disparar('focus');
  assert.match(nodo().textContent, /contenido B/, 'abrir otro cierra el anterior');
  assert.equal(pa.abierto(), false);
  assert.equal(a.hasAttribute('aria-describedby'), false);
  assert.equal(nodo().getAttribute('role'), 'dialog');
  assert.equal(nodo().getAttribute('aria-label'), 'Panel B');
  assert.equal(b.getAttribute('aria-expanded'), 'true');

  b.disparar('click');
  assert.equal(pb.fijo(), true);
  b.disparar('blur');
  assert.equal(nodo().hidden, false, 'fijado: perder el foco no lo cierra');
  doc.teclado('Escape');
  assert.equal(nodo().hidden, true);
  assert.equal(doc.activeElement, b, 'Esc devuelve el foco al ancla');
  assert.equal(b.getAttribute('aria-expanded'), 'false');

  a.disparar('click');
  assert.equal(pa.fijo(), true);
  for (const fn of [...doc.escuchas.get('mousedown')]) fn({ target: fuera });
  assert.equal(nodo().hidden, true, 'clic fuera cierra');
  a.disparar('click'); a.disparar('click');
  assert.equal(nodo().hidden, true, 'segundo clic cierra');
  assert.equal((doc.escuchas.get('keydown') || []).length, 0, 'cerrado no deja escuchas colgadas');
  assert.equal((doc.escuchas.get('mousedown') || []).length, 0);
});

test('termino / ayuda / fuente: nombre humano visible, definición en el popover, técnico solo con el modo técnico', () => {
  estadoMod.estado.fijar({ modoTecnico: false });
  const t = ui.termino('gate_h');
  doc.body.appendChild(t);
  assert.match(t.firstChild.textContent, /Espera tu firma/);
  assert.equal(t.getAttribute('tabindex'), '0');
  assert.equal(buscar(t, '.termino__tecnico').className.includes('solo-tecnico'), true, 'el nombre técnico queda para el modo técnico');
  assert.equal(ui.termino('gate_h', { texto: 'gate H' }).firstChild.textContent, 'gate H');
  assert.equal(ui.termino('gate_h', { sinTecnico: true }).querySelector('.termino__tecnico'), null);
  t.disparar('focus');
  const pop = doc.body.querySelector('.popover');
  assert.match(pop.textContent, /solo puedes aprobar tú/);
  assert.match(pop.textContent, /Nombre técnico:/);
  assert.match(pop.textContent, /gate H/);
  doc.teclado('Escape');

  const sin = ui.termino('termino_inventado');
  assert.equal(sin.textContent, 'Termino inventado');
  assert.match(sin.className, /sin-definicion/);
  sin.disparar('focus');
  assert.match(doc.body.querySelector('.popover').textContent, /Todavía no hay una explicación/);
  doc.teclado('Escape');

  const ay = ui.ayuda('ratio_reembolsos');
  assert.equal(ay.tagName, 'BUTTON');
  assert.match(ay.getAttribute('aria-label'), /Tasa de reembolsos/);
  ay.disparar('focus');
  assert.match(doc.body.querySelector('.popover').textContent, /compras que se devolvieron/);
  doc.teclado('Escape');

  const f = ui.fuente(['ofertas/_ejemplo/estado.json', 'empresa/registro.jsonl'], { leido: '2026-11-06T14:00:00Z', ahora: Date.parse('2026-11-06T14:03:00Z') });
  doc.body.appendChild(f);
  const boton = buscar(f, 'button');
  assert.equal(boton.getAttribute('aria-label'), 'Origen de los datos');
  boton.disparar('focus');
  const pf = doc.body.querySelector('.popover');
  assert.match(pf.textContent, /ofertas\/_ejemplo\/estado\.json/);
  assert.match(pf.textContent, /Leído hace 3 min/);
  assert.equal(pf.getAttribute('role'), 'dialog');
  doc.teclado('Escape');
  const vacia = ui.fuente([]);
  buscar(vacia, 'button').disparar('focus');
  assert.match(doc.body.querySelector('.popover').textContent, /No se indicó de dónde salen/);
  doc.teclado('Escape');
});

test('fuenteInfo (heredada): conserva el texto de siempre pero las rutas solo se ven con el modo técnico', () => {
  const f = ui.fuenteInfo({ fuente: ['empresa/a.json'], generado_en: '2026-11-06T14:00:00Z' }, Date.parse('2026-11-06T14:05:00Z'));
  assert.match(f.textContent, /Fuente: empresa\/a\.json/);
  assert.match(f.textContent, /leído hace 5 min/);
  assert.equal(buscar(f, '.fuente-info__rutas').className.includes('solo-tecnico'), true);
  assert.ok(buscar(f, '.fuente-btn'), 'icono «i» con popover');
  assert.match(ui.fuenteInfo({}).textContent, /sin fuente declarada/);
});

// ───────────────────────── piezas comunes ─────────────────────────

test('chip y estadoIcono: los estados llevan icono + etiqueta, neutro no; tonos nuevos y alias', () => {
  assert.ok(buscar(ui.chip('Listo', 'ok'), 'svg'), 'ok: icono');
  assert.ok(buscar(ui.chip('Ojo', 'aviso'), 'svg'));
  assert.ok(buscar(ui.chip('Mal', 'error'), 'svg'));
  assert.ok(buscar(ui.chip('Grave', 'grave'), 'svg'));
  assert.ok(buscar(ui.chip('Crítico', 'critico'), 'svg'));
  assert.equal(buscar(ui.chip('Nada', 'neutro'), 'svg'), null);
  assert.equal(buscar(ui.chip('Dato', 'info'), 'svg'), null, 'info lleva punto (CSS), no icono');
  assert.equal(buscar(ui.chip('Sin', 'ok', { icono: false }), 'svg'), null);
  assert.match(ui.chip('x', 'bien').className, /chip--ok/, 'bien es alias de ok');
  assert.match(ui.chip('x', 'critico').className, /chip--critico/);
  assert.match(ui.chip('x', 'grave').className, /chip--grave/);
  assert.match(ui.chip('x', 'acento').className, /chip--acento/);
  assert.match(ui.chip('x', 'ok').className, /chip--con-icono/);
  for (const [estado, texto, tono] of [['aprobado', 'Aprobado', 'ok'], ['en_QA', 'En revisión', 'info'], ['en_progreso', 'En progreso', 'info'], ['pendiente', 'Pendiente', 'neutro'], ['bloqueado', 'Bloqueado', 'error'],
    ['escalado', 'Pasó a tu decisión', 'aviso'], ['obsoleta', 'Desactualizada', 'aviso'], ['vigente', 'Vigente', 'ok'], ['vencido', 'Vencido', 'error'], ['espera_firma', 'Espera tu firma', 'acento']]) {
    const c = ui.estadoIcono(estado);
    assert.equal(c.textContent, texto, estado);
    assert.match(c.className, new RegExp(`chip--${tono}`), estado);
    assert.ok(buscar(c, 'svg'), `${estado}: con icono propio`);
    assert.equal(c.dataset.estado, estado);
  }
  assert.deepEqual(ui.infoEstado('aprobado'), { tono: 'ok', texto: 'Aprobado' }, 'infoEstado no cambia de forma');
  assert.equal(ui.iconoDeEstado('bloqueado'), 'candado');
  assert.equal(ui.iconoDeEstado('algo_raro'), 'circulo');
  assert.equal(ui.normalizarTono('serious'), 'grave');
  assert.equal(ui.normalizarTono('inventado'), 'neutro');
  assert.equal(ui.normalizarTono('inventado', null), null);
});

test('encabezadoPagina: migas, título, descripción, acciones y pestañas; migas del shell por defecto y [] para ninguna', () => {
  const botones = [el('button', null, 'A'), el('button', null, 'B')];
  const pest = el('div', { class: 'mis-pestanas' }, 'pestañas');
  ui.fijarContexto({ migas: [{ texto: 'Testeo y escala' }, { texto: 'Ofertas', ruta: 'ofertas' }] });
  const h = ui.encabezadoPagina({ titulo: 'Ofertas', descripcion: 'Qué es esto', acciones: botones, pestanas: pest });
  assert.equal(buscar(h, 'h1').textContent, 'Ofertas');
  assert.equal(buscar(h, '.cab__desc').textContent, 'Qué es esto');
  assert.equal(buscarTodos(h, '.cab__acciones button').length, 2);
  assert.ok(buscar(h, '.cab__pestanas .mis-pestanas'));
  assert.match(h.className, /cab--con-pestanas/);
  assert.equal(buscarTodos(h, '.migas__item').length, 2, 'migas del shell por defecto');
  assert.equal(buscar(h, '.migas__item--actual').textContent, 'Ofertas');

  const propias = ui.encabezadoPagina({ titulo: 'OF-1', migas: [{ texto: 'Ofertas', ruta: 'ofertas' }, { texto: 'OF-1' }] });
  assert.equal(buscar(propias, '.migas__enlace').getAttribute('href'), '#/ofertas');
  assert.equal(buscar(propias, '[aria-current="page"]').textContent, 'OF-1');
  assert.equal(buscar(propias, 'nav').getAttribute('aria-label'), 'Ubicación');
  assert.equal(buscar(ui.encabezadoPagina({ titulo: 'X', migas: [] }), '.migas'), null);
  const sin = ui.encabezadoPagina({ titulo: 'Solo título' });
  assert.equal(buscar(sin, '.cab__acciones'), null);
  assert.equal(buscar(sin, '.cab__desc'), null);
  ui.fijarContexto({});
  assert.equal(buscar(ui.encabezadoPagina({ titulo: 'Sin contexto' }), '.migas'), null);
  assert.equal(buscar(ui.encabezadoPagina({ titulo: '<b>x</b>' }), 'b'), null, 'el título entra como texto');
});

test('atencion: ordena crítico → grave → aviso → información, un botón por aviso, vacío explícito', () => {
  const orden = ui.ordenarAtencion([
    { tono: 'info', titulo: 'i1' }, { tono: 'aviso', titulo: 'a1' }, { tono: 'critico', titulo: 'c1' }, { tono: 'aviso', titulo: 'a2' }, { tono: 'error', titulo: 'c2' }, { tono: 'grave', titulo: 'g1' }, { tono: 'raro', titulo: 'i2' }, null,
  ]);
  assert.deepEqual(orden.map((x) => x.titulo), ['c1', 'c2', 'g1', 'a1', 'a2', 'i1', 'i2']);
  assert.deepEqual(orden.map((x) => x.tono), ['critico', 'critico', 'grave', 'aviso', 'aviso', 'info', 'info']);
  const original = [{ tono: 'info', titulo: 'x' }, { tono: 'critico', titulo: 'y' }];
  ui.ordenarAtencion(original);
  assert.equal(original[0].titulo, 'x', 'no muta');

  let clics = 0;
  const p = ui.atencion({ items: [
    { tono: 'aviso', titulo: 'Límites sin fijar', detalle: 'No se puede gastar', accion: { texto: 'Abrir límites', ruta: 'parametros' } },
    { tono: 'critico', titulo: 'Freno activo', accion: { texto: 'Revisar freno', onClick: () => { clics += 1; } } },
  ] });
  assert.equal(p.cantidad, 2);
  assert.equal(buscar(p, 'h2').textContent, 'Requiere tu atención');
  const items = buscarTodos(p, '.atencion__item');
  assert.match(items[0].className, /atencion__item--critico/);
  assert.match(items[1].className, /atencion__item--aviso/);
  assert.equal(items[0].querySelector('.atencion__item-titulo').textContent, 'Freno activo');
  assert.ok(items[0].querySelector('svg'), 'icono de gravedad');
  assert.equal(items[0].querySelector('.atencion__icono').getAttribute('aria-label'), 'Crítico');
  assert.equal(items[0].querySelectorAll('.atencion__boton').length, 1, 'un único botón por aviso');
  assert.equal(items[1].querySelector('a.atencion__boton').getAttribute('href'), '#/parametros');
  items[0].querySelector('button').click();
  assert.equal(clics, 1);
  assert.equal(buscar(p, '.atencion__cuenta').textContent, '2');
  assert.match(p.className, /atencion--critico/);

  const vacio = ui.atencion({ items: [] });
  assert.equal(vacio.cantidad, 0);
  assert.match(vacio.className, /atencion--vacia/);
  assert.match(vacio.textContent, /Todo en orden/);
  assert.match(ui.atencion({ items: [], vacio: 'Nada pendiente' }).textContent, /Nada pendiente/);
  assert.equal(buscar(ui.atencion({ items: [{ tono: 'info', titulo: '<i>x</i>' }] }), 'i'), null);
});

test('metrica: número grande, «—» sin dato, cero válido, tono con icono, tendencia, mini-serie, ayuda y enlace', () => {
  const m = ui.metrica({ etiqueta: 'Gasto de hoy', valor: '12,00 €', contexto: 'de 300,00 €', tono: 'ok', tendencia: { valor: '+12 %', sentido: 'sube', bueno: false }, serie: [1, 3, 2, 5], ayuda: 'tope' });
  assert.equal(m.tagName, 'ARTICLE');
  assert.match(m.className, /metrica--ok/);
  assert.equal(buscar(m, '.metrica__etiqueta').textContent, 'Gasto de hoy');
  assert.equal(buscar(m, '.metrica__valor').textContent, '12,00 €');
  assert.equal(buscar(m, '.metrica__contexto').textContent, 'de 300,00 €');
  assert.ok(buscar(m, '.metrica__estado svg'), 'el estado lleva icono');
  assert.equal(buscar(m, '.metrica__estado').getAttribute('aria-label'), 'En orden');
  assert.match(buscar(m, '.tendencia').className, /tendencia--error/, 'sube pero es desfavorable');
  assert.match(buscar(m, '.tendencia').textContent, /\+12 %/);
  assert.match(buscar(m, '.tendencia .solo-lectores').textContent, /desfavorable/);
  assert.ok(buscar(m, '.metrica__serie svg polyline'));
  assert.ok(buscar(m, '.ayuda-btn'));

  assert.equal(buscar(ui.metrica({ etiqueta: 'x', valor: 0 }), '.metrica__valor').textContent, '0', 'el cero es un dato');
  assert.equal(buscar(ui.metrica({ etiqueta: 'x', valor: 1234 }), '.metrica__valor').textContent, '1.234');
  const sin = ui.metrica({ etiqueta: 'x', valor: null });
  assert.equal(buscar(sin, '.metrica__valor').textContent, '—');
  assert.match(sin.className, /sin-valor/);
  assert.equal(buscar(sin, '.metrica__pie'), null);
  assert.match(buscar(ui.metrica({ etiqueta: 'x', valor: 1, tendencia: { valor: '-3', sentido: 'baja', bueno: true } }), '.tendencia').className, /tendencia--ok/);
  assert.match(buscar(ui.metrica({ etiqueta: 'x', valor: 1, tendencia: { valor: '=', sentido: 'igual' } }), '.tendencia').className, /tendencia--neutro/);
  assert.equal(buscar(ui.metrica({ etiqueta: 'x', valor: 1, tono: 'neutro' }), '.metrica__estado'), null);
  const enlace = ui.metrica({ etiqueta: 'Ofertas', valor: 3, ruta: 'ofertas' });
  assert.equal(enlace.tagName, 'A');
  assert.equal(enlace.getAttribute('href'), '#/ofertas');
  assert.match(enlace.className, /metrica--enlace/);
  assert.match(ui.metrica({ etiqueta: 'x', valor: 'a'.repeat(40) }).className, /valor-muy-largo/);
  assert.equal(buscar(ui.metrica({ etiqueta: '<b>x</b>', valor: '<i>1</i>' }), 'b'), null);
  assert.ok(buscar(ui.tarjeta({ titulo: 'Heredada', valor: 1 }), '.tarjeta__valor'), 'tarjeta sigue existiendo como alias');
});

test('pasos (pipeline): modelo, estado = icono + etiqueta, etapa que espera tu firma destacada, teclado accesible', () => {
  const etapas = [
    { id: 'D1', nombre: 'Descubrir', codigo: 'D1', estado: 'aprobado' },
    { id: 'D2', nombre: 'Validar', codigo: 'D2', estado: 'espera_firma', seleccionada: true, aviso: 'El QA dejó notas' },
    { id: 'D3', nombre: 'Oferta', codigo: 'D3', estado: 'pendiente' },
    { id: 'D4', nombre: 'Producto', codigo: 'D4', estado: 'bloqueado', icono: 'caja' },
  ];
  const modelo = ui.modeloPasos(etapas);
  assert.equal(modelo.length, 4);
  assert.equal(modelo[1].destacada, true);
  assert.equal(modelo[1].etiqueta, 'Espera tu firma');
  assert.equal(modelo[0].icono, 'check');
  assert.equal(modelo[3].icono, 'caja', 'icono propio de la etapa');
  assert.equal(ui.modeloPasos(null).length, 0);
  assert.equal(ui.modeloPasos([null, { id: 1 }]).length, 1);

  const elegidas = [];
  const p = ui.pasos({ etapas, onElegir: (id) => elegidas.push(id), etiqueta: 'Etapas de OF-1' });
  doc.body.appendChild(p);
  assert.equal(p.tagName, 'NAV');
  assert.equal(p.getAttribute('aria-label'), 'Etapas de OF-1');
  const items = buscarTodos(p, '.stepper__item');
  const botones = buscarTodos(p, '.stepper__paso');
  assert.equal(items.length, 4);
  assert.match(items[1].className, /es-destacada/);
  assert.match(items[1].className, /es-seleccionada/);
  assert.match(items[1].className, /stepper__item--acento/);
  assert.match(items[3].className, /stepper__item--error/);
  assert.match(botones[1].getAttribute('aria-label'), /^Validar \(D2\): Espera tu firma\. El QA dejó notas$/);
  assert.equal(botones[1].getAttribute('aria-current'), 'step');
  assert.equal(botones[0].hasAttribute('aria-current'), false);
  assert.equal(botones[0].querySelector('.stepper__estado').textContent, 'Aprobado', 'estado como texto, no solo color');
  assert.ok(botones[0].querySelector('svg'));
  assert.equal(botones[0].querySelector('.stepper__codigo').textContent, 'D1');
  assert.deepEqual(botones.map((b) => b.getAttribute('tabindex')), ['-1', '0', '-1', '-1'], 'una sola parada de Tab (la etapa seleccionada)');

  botones[1].disparar('keydown', { key: 'ArrowRight' });
  assert.equal(doc.activeElement, botones[2]);
  assert.deepEqual(botones.map((b) => b.getAttribute('tabindex')), ['-1', '-1', '0', '-1']);
  botones[2].disparar('keydown', { key: 'End' });
  assert.equal(doc.activeElement, botones[3]);
  botones[3].disparar('keydown', { key: 'ArrowRight' });
  assert.equal(doc.activeElement, botones[3], 'no da la vuelta');
  botones[3].disparar('keydown', { key: 'Home' });
  assert.equal(doc.activeElement, botones[0]);
  botones[0].disparar('keydown', { key: 'ArrowLeft' });
  assert.equal(doc.activeElement, botones[0]);
  const ev = botones[0].disparar('keydown', { key: 'a' });
  assert.equal(ev.defaultPrevented, false, 'otras teclas no se interceptan');
  botones[2].click();
  assert.deepEqual(elegidas, ['D3']);

  assert.equal(ui.indiceFoco(1, 'ArrowDown', 5), 2);
  assert.equal(ui.indiceFoco(0, 'ArrowUp', 5), 0);
  assert.equal(ui.indiceFoco(2, 'x', 5), 2);
  assert.equal(ui.indiceFoco(0, 'End', 0), -1);

  const lectura = ui.pasos({ etapas: etapas.slice(0, 1) });
  assert.match(buscar(lectura, '.stepper__paso').className, /stepper__paso--lectura/);
  buscar(lectura, '.stepper__paso').click();
  assert.equal(buscarTodos(ui.pasos({}), '.stepper__item').length, 0);
});

test('pasos compacto: automático según el ancho del contenedor, forzado u omitido; sin perder el estado accesible', () => {
  assert.equal(ui.debeCompactar(1100, 11), false, '100 px por etapa caben');
  assert.equal(ui.debeCompactar(900, 11), true, '82 px por etapa: compacta');
  assert.equal(ui.debeCompactar(96 * 4, 4), false);
  assert.equal(ui.debeCompactar(380, 4), true);
  assert.equal(ui.debeCompactar(380, 4, 90), false, 'mínimo configurable');
  assert.equal(ui.debeCompactar(0, 4), false, 'sin ancho medido no compacta');
  assert.equal(ui.debeCompactar(500, 0), false);
  assert.equal(ui.debeCompactar(NaN, 3), false);
  const etapas = Array.from({ length: 11 }, (_, i) => ({ id: `E${i}`, nombre: `Etapa ${i}`, codigo: `D${i}`, estado: i === 3 ? 'espera_firma' : 'aprobado' }));
  const auto = ui.pasos({ etapas });
  assert.equal(auto.getAttribute('data-compacto'), 'auto');
  assert.doesNotMatch(auto.className, /compacto/, 'automático: arranca normal y el ResizeObserver decide en el navegador');
  const forzado = ui.pasos({ etapas, compacto: true });
  assert.match(forzado.className, /stepper--compacto/);
  assert.equal(forzado.getAttribute('data-compacto'), 'true');
  assert.doesNotMatch(ui.pasos({ etapas, compacto: false }).className, /compacto/);
  assert.equal(buscarTodos(forzado, '.stepper__paso').length, 11, 'mismas etapas');
  assert.match(buscarTodos(forzado, '.stepper__paso')[3].getAttribute('aria-label'), /Espera tu firma/, 'el estado sigue en el nombre accesible aunque el CSS oculte la línea');
  assert.equal(buscarTodos(forzado, '.stepper__estado')[3].textContent, 'Espera tu firma');
  assert.match(buscarTodos(forzado, '.stepper__paso')[3].getAttribute('title'), /^Etapa 3: Espera tu firma$/, 'nombre y estado también en el title (tooltip nativo)');
  assert.equal(buscarTodos(ui.pasos({ etapas: [{ id: 'a', nombre: 'Sin código', estado: 'pendiente' }, { id: 'b', nombre: 'Con', codigo: 'D2', estado: 'pendiente' }] }), '.stepper__item--sin-codigo').length, 1);
  // con ResizeObserver disponible (navegador) se conecta y alterna la clase según el ancho
  const previo = globalThis.ResizeObserver;
  let cb = null; let observado = null;
  globalThis.ResizeObserver = class { constructor(f) { cb = f; } observe(n) { observado = n; } };
  const viva = ui.pasos({ etapas });
  assert.equal(observado, viva);
  Object.defineProperty(viva, 'clientWidth', { value: 700, configurable: true });
  cb();
  assert.match(viva.className, /stepper--compacto/);
  Object.defineProperty(viva, 'clientWidth', { value: 1300, configurable: true });
  cb();
  assert.doesNotMatch(viva.className, /stepper--compacto/);
  globalThis.ResizeObserver = class { observe() { throw new Error('no debe observar'); } };
  assert.doesNotThrow(() => ui.pasos({ etapas, compacto: true }), 'forzado no necesita observador');
  if (previo === undefined) delete globalThis.ResizeObserver; else globalThis.ResizeObserver = previo;
});

test('vacioConPasos: variante compacta y adaptación al contenedor (CSS container queries)', () => {
  const normal = ui.vacioConPasos({ titulo: 'T' });
  assert.doesNotMatch(normal.className, /compacto/);
  assert.ok(buscar(normal, '.vacio-pasos__rejilla .vacio-pasos__ilus'), 'rejilla interior separada del contenedor (el contenedor no puede consultarse a sí mismo)');
  assert.ok(buscar(normal, '.vacio-pasos__rejilla .vacio-pasos__cuerpo'));
  const c = ui.vacioConPasos({ titulo: 'T', compacto: true, pasos: [{ texto: 'a' }] });
  assert.match(c.className, /vacio-pasos--compacto/);
  assert.equal(c.getAttribute('role'), 'status');
  assert.equal(buscarTodos(c, '.pasos-lista__item').length, 1);
  const css = leer('styles.css');
  assert.match(css, /\.vacio-pasos \{[^}]*container-type:\s*inline-size/);
  assert.match(css, /@container vacio \(max-width:\s*\d+px\)\s*\{[^@]*\.vacio-pasos__rejilla \{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/);
  assert.match(css, /\.vacio-pasos--compacto \.vacio-pasos__rejilla \{[^}]*grid-template-columns:\s*minmax\(0, 1fr\)/);
  assert.match(css, /\.stepper--compacto \.stepper__item \{[^}]*min-width:\s*40px/);
  assert.match(css, /\.stepper--compacto \.stepper__nombre \{ display: none; \}/);
  assert.match(css, /\.stepper--compacto \.stepper__estado \{\s*display:\s*none/);
});

test('migas sin repeticiones: un grupo que se llama como su pantalla («Cerebro › Cerebro») y un único elemento igual al título se descartan', () => {
  assert.deepEqual(app.migasDeRuta('sistema'), [{ texto: 'Robots' }, { texto: 'Salud del sistema' }], 'Salud del sistema vive en Robots: ya no se repite');
  for (const [ruta, titulo] of [['cerebro', 'Cerebro'], ['jurado', 'Jurado'], ['robots', 'Robots'], ['paises', 'Países']]) {
    assert.deepEqual(app.migasDeRuta(ruta), [{ texto: titulo }], `${ruta}: el grupo se llama igual que la pantalla y no se repite`);
    assert.deepEqual(ui.limpiarMigas(app.migasDeRuta(ruta), titulo), [], `${ruta}: la cabecera no pinta una miga que repite el título`);
  }
  assert.deepEqual(app.migasDeRuta('jurado', { id: 'ronda-1' }), [{ texto: 'Jurado', ruta: 'jurado' }, { texto: 'ronda-1' }], 'con id: enlace a la pantalla y luego el id, sin repetir el grupo');
  assert.deepEqual(app.migasDeRuta('resumen'), [{ texto: 'El sistema' }, { texto: 'Resumen' }], 'la pantalla de conjunto cuelga de «El sistema»');
  assert.deepEqual(app.migasDeRuta('pulido'), [{ texto: 'Cerebro' }, { texto: 'Mejoras pendientes' }], 'el grupo va con su literal, sin el número de pieza');
  assert.deepEqual(app.migasDeRuta('quien-decide'), [{ texto: 'Dinero y reglas' }, { texto: 'Quién decide qué' }]);
  assert.deepEqual(app.migasDeRuta('oferta', { id: 'OF-1' }).length, 3);
  for (const e of app.ENTRADAS) {
    const textos = app.migasDeRuta(e.ruta, { id: 'X-1' }).map((m) => m.texto.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase());
    textos.forEach((t, i) => { if (i > 0) assert.notEqual(t, textos[i - 1], `${e.ruta}: miga repetida «${t}»`); });
    assert.deepEqual(app.migasDeRuta(e.ruta).at(-1), { texto: e.titulo }, `${e.ruta}: la última miga es la pantalla`);
  }
  const l = ui.limpiarMigas;
  assert.deepEqual(l([{ texto: 'Sistema' }, { texto: 'Sistema' }]), [{ texto: 'Sistema' }]);
  assert.deepEqual(l([{ texto: 'Sistema' }, { texto: 'sistema ', ruta: 'sistema' }]), [{ texto: 'sistema ', ruta: 'sistema' }], 'conserva la que tiene enlace');
  assert.deepEqual(l([{ texto: 'Sistema' }, { texto: 'Sistema' }], 'Sistema'), [], 'una sola migas igual al título: ninguna');
  assert.deepEqual(l([{ texto: 'Operar' }, { texto: 'Resumen' }], 'Resumen'), [{ texto: 'Operar' }, { texto: 'Resumen' }], 'con grupo sí aporta');
  assert.deepEqual(l([{ texto: 'Parámetros' }], 'Parametros'), [], 'sin tildes ni mayúsculas');
  assert.deepEqual(l([{ texto: 'Ofertas' }, { texto: 'OF-1' }, { texto: 'OF-1' }]), [{ texto: 'Ofertas' }, { texto: 'OF-1' }]);
  assert.deepEqual(l([{ texto: 'A' }, null, { texto: '' }, { texto: 'B' }]), [{ texto: 'A' }, { texto: 'B' }], 'descarta vacíos');
  assert.deepEqual(l(null), []);
  ui.fijarContexto({ migas: app.migasDeRuta('cerebro') });
  assert.equal(buscar(ui.encabezadoPagina({ titulo: 'Cerebro' }), '.migas'), null, 'la cabecera no pinta una miga que repite el título');
  ui.fijarContexto({ migas: app.migasDeRuta('sistema') });
  assert.deepEqual(buscarTodos(ui.encabezadoPagina({ titulo: 'Salud del sistema' }), '.migas__item').map((m) => m.textContent), ['Robots', 'Salud del sistema'], 'Salud del sistema cuelga de Robots: aquí la miga sí aporta');
  assert.equal(buscarTodos(ui.encabezadoPagina({ titulo: 'Sistema', migas: [{ texto: 'Sistema' }, { texto: 'Sistema' }] }), '.migas__item').length, 0);
  ui.fijarContexto({});
});

test('vacioConPasos: ilustración, qué falta, pasos numerados y comando abierto; sin pasos sigue siendo válido', () => {
  const v = ui.vacioConPasos({ titulo: 'Todavía no hay candidatos', explicacion: 'Falta correr el barrido.', icono: 'lupa', pasos: [{ texto: 'Mira el estado.', comando: 'python -m x estado' }, { texto: 'Pídelo al asistente.' }, null, {}] });
  assert.equal(v.getAttribute('role'), 'status');
  assert.equal(buscar(v, 'h3').textContent, 'Todavía no hay candidatos');
  assert.equal(buscar(v, '.vacio-pasos__texto').textContent, 'Falta correr el barrido.');
  assert.ok(buscar(v, '.ilus'), 'ilustración SVG propia');
  assert.equal(buscar(v, '.ilus').getAttribute('aria-hidden'), 'true');
  assert.equal(buscarTodos(v, '.pasos-lista__item').length, 2, 'los pasos vacíos se descartan');
  const cmd = buscar(v, '.comando');
  assert.equal(cmd.open, true, 'aquí el comando ES la acción');
  assert.equal(buscar(cmd, '.comando__texto').textContent, 'python -m x estado');
  assert.equal(buscar(ui.vacioConPasos({ titulo: 'Sin pasos' }), '.pasos-lista'), null);
  assert.equal(buscar(ui.vacioConPasos({ titulo: '<b>x</b>' }), 'b'), null);
  const vacio = ui.vacio('Nada', { comando: 'ls', fuente: ['empresa/x.json'] });
  assert.equal(buscar(vacio, '.comando').open, true, 'vacio() conserva su comando visible');
  assert.equal(buscar(vacio, '.vacio__fuente').className.includes('solo-tecnico'), true, 'la ruta esperada queda para el modo técnico');
  assert.match(buscar(vacio, '.vacio__fuente').textContent, /empresa\/x\.json/);
});

test('esqueleto: cuatro tipos, accesible (estado «Cargando…», decoración oculta) y con tamaños', () => {
  for (const [tipo, clase] of [['tarjetas', 'esq--tarjetas'], ['tabla', 'esq--tabla'], ['texto', 'esq--texto'], ['pagina', 'esq--pagina'], ['raro', 'esq--pagina']]) {
    const e = ui.esqueleto(tipo);
    assert.match(e.className, new RegExp(clase), tipo);
    assert.equal(e.getAttribute('role'), 'status');
    assert.equal(e.getAttribute('aria-busy'), 'true');
    assert.match(buscar(e, '.solo-lectores').textContent, /Cargando/);
    assert.equal(buscar(e, '.esq__marco').getAttribute('aria-hidden'), 'true');
  }
  assert.equal(buscarTodos(ui.esqueleto('tarjetas', 3), '.esq__tarjeta').length, 3);
  assert.equal(buscarTodos(ui.esqueleto('tarjetas'), '.esq__tarjeta').length, 4);
  assert.equal(buscarTodos(ui.esqueleto('tabla', 5), '.esq__fila').length, 6, 'cabecera + 5 filas');
  assert.equal(buscarTodos(ui.esqueleto('texto', 7), '.esq__barra').length, 7);
  assert.ok(buscar(ui.esqueleto('pagina'), '.esq__tarjetas'));
});

test('interruptor, segmentado y kbd: accesibles y con valores', () => {
  const cambios = [];
  const sw = ui.interruptor({ etiqueta: 'Detalle técnico', activo: false, onCambio: (v) => cambios.push(v) });
  assert.equal(sw.getAttribute('role'), 'switch');
  assert.equal(sw.getAttribute('aria-checked'), 'false');
  assert.equal(sw.getAttribute('aria-label'), 'Detalle técnico', 'conserva el nombre aunque el texto se oculte en pantallas pequeñas');
  sw.click(); sw.click();
  assert.deepEqual(cambios, [true, false]);
  sw.fijar(true);
  assert.equal(sw.getAttribute('aria-checked'), 'true');

  const vistos = [];
  const sg = ui.segmentado({ etiqueta: 'Densidad', valor: 'comoda', opciones: [{ valor: 'comoda', etiqueta: 'Cómoda', icono: 'menu' }, { valor: 'compacta', etiqueta: 'Compacta', icono: 'densidad' }], onCambio: (v) => vistos.push(v) });
  doc.body.appendChild(sg);
  const ops = buscarTodos(sg, '[role="radio"]');
  assert.equal(sg.getAttribute('role'), 'radiogroup');
  assert.deepEqual(ops.map((o) => o.getAttribute('aria-checked')), ['true', 'false']);
  assert.deepEqual(ops.map((o) => o.getAttribute('tabindex')), ['0', '-1']);
  ops[0].disparar('keydown', { key: 'ArrowRight' });
  assert.deepEqual(vistos, ['compacta']);
  assert.deepEqual(ops.map((o) => o.getAttribute('aria-checked')), ['false', 'true']);
  ops[1].disparar('keydown', { key: 'ArrowRight' });
  assert.deepEqual(vistos, ['compacta', 'comoda'], 'da la vuelta');
  sg.fijar('compacta');
  assert.equal(ops[1].getAttribute('aria-checked'), 'true');
  assert.equal(ui.kbd('⌘', 'K').querySelectorAll('kbd').length, 2);
});

test('barraPestanas: tablist sin paneles, flechas/Inicio/Fin, contador y valor activo', () => {
  const vistos = [];
  const b = ui.barraPestanas({ etiqueta: 'Secciones de la oferta', items: [{ id: 'a', titulo: 'Resumen' }, { id: 'b', titulo: 'Etapas', contador: 11, icono: 'lista' }, { id: 'c', titulo: 'Archivos' }, null], activo: 'b', onCambio: (id) => vistos.push(id) });
  doc.body.appendChild(b);
  const tabs = buscarTodos(b, '[role="tab"]');
  assert.equal(b.getAttribute('role'), 'tablist');
  assert.equal(b.getAttribute('aria-label'), 'Secciones de la oferta');
  assert.equal(tabs.length, 3);
  assert.deepEqual(tabs.map((t) => t.getAttribute('aria-selected')), ['false', 'true', 'false']);
  assert.deepEqual(tabs.map((t) => t.getAttribute('tabindex')), ['-1', '0', '-1']);
  assert.equal(buscar(tabs[1], '.tabs__contador').textContent, '11');
  assert.ok(buscar(tabs[1], 'svg'));
  assert.equal(buscarTodos(b, '[role="tabpanel"]').length, 0, 'sin paneles: la página decide qué mostrar');
  tabs[1].disparar('keydown', { key: 'ArrowRight' });
  assert.deepEqual(vistos, ['c']);
  assert.equal(doc.activeElement, tabs[2]);
  tabs[2].disparar('keydown', { key: 'ArrowRight' });
  assert.deepEqual(vistos, ['c', 'a'], 'da la vuelta');
  tabs[0].disparar('keydown', { key: 'End' });
  assert.deepEqual(vistos, ['c', 'a', 'c']);
  tabs[0].click();
  assert.equal(tabs[0].getAttribute('aria-selected'), 'true');
  assert.deepEqual(vistos, ['c', 'a', 'c', 'a']);
  b.fijar('b');
  assert.equal(tabs[1].getAttribute('aria-selected'), 'true');
  assert.equal(buscarTodos(ui.barraPestanas({ items: [{ id: 'x', titulo: 'X' }] }), '[aria-selected="true"]').length, 1, 'sin `activo`, la primera');
});

test('seccion con glosario, tabla numérica y vacio: extensiones compatibles', () => {
  const s = ui.seccion('Tracción', el('p', null, 'x'), { glosario: 'traccion', ayuda: 'texto de ayuda' });
  assert.equal(buscar(s, 'h2').textContent, 'Tracción');
  assert.equal(s.getAttribute('aria-labelledby'), buscar(s, 'h2').id);
  assert.ok(buscar(s, '.seccion__tit .ayuda-btn'));
  assert.equal(buscar(s, '.seccion__ayuda').textContent, 'texto de ayuda');
  assert.equal(buscar(ui.seccion('Sin ayuda', 'x'), '.ayuda-btn'), null);
  const t = ui.tabla({ columnas: [{ clave: 'a', titulo: 'A' }, { clave: 'n', titulo: 'N', numerico: true }], filas: [{ a: 'x', n: 5 }] });
  const ths = buscarTodos(t, 'th');
  assert.equal(ths[1].classList.contains('alinea-der'), true);
  assert.equal(buscarTodos(t, 'tbody td')[1].classList.contains('alinea-der'), true);
  assert.equal(ths[0].classList.contains('alinea-der'), false);
});

// ───────────────────────── paleta de comandos ─────────────────────────

test('paleta: normalizar, puntuar y buscar (sin tildes, todas las palabras, prefijo antes que contiene)', () => {
  assert.equal(paleta.normalizar('Campañas ÁÉÍ'), 'campanas aei');
  assert.equal(paleta.normalizar(null), '');
  const e = (titulo, extra = {}) => ({ titulo, ...extra });
  assert.equal(paleta.puntuar('', e('Resumen')), 0);
  assert.equal(paleta.puntuar('zzz', e('Resumen')), -1);
  assert.ok(paleta.puntuar('res', e('Resumen')) > paleta.puntuar('sum', e('Resumen')), 'prefijo > contiene');
  assert.ok(paleta.puntuar('registro', e('Registro')) > paleta.puntuar('regis', e('Registro')), 'coincidencia exacta gana');
  assert.ok(paleta.puntuar('campanas', e('Campañas')) > 0, 'sin tildes');
  assert.ok(paleta.puntuar('param lim', e('Parámetros y límites')) > 0, 'varias palabras, en cualquier parte');
  assert.equal(paleta.puntuar('param xyz', e('Parámetros y límites')), -1, 'todas las palabras deben coincidir');
  assert.ok(paleta.puntuar('dark', e('Cambiar tema', { palabras: ['oscuro', 'dark'] })) > 0, 'alias');
  assert.ok(paleta.puntuar('barrido', e('Descubrimiento', { detalle: 'Barridos de la Biblioteca' })) > 0, 'detalle');
  assert.ok(paleta.puntuar('rsm', e('Resumen')) > 0, 'subsecuencia (tolerancia a erratas)');
  assert.ok(paleta.puntuar('res', e('Resumen')) > paleta.puntuar('res', e('Resumen largo de la oferta de ejemplo')), 'a igualdad, el título más corto');
  const entradas = [e('Skills', { id: 1 }), e('Resumen', { id: 2 }), e('Registro', { id: 3 }), e('Parámetros', { id: 4, detalle: 'registro de límites' })];
  assert.deepEqual(paleta.buscar(entradas, '').map((x) => x.id), [1, 2, 3, 4], 'sin consulta: el orden original');
  assert.deepEqual(paleta.buscar(entradas, 'reg').map((x) => x.id), [3, 4], 'el título que empieza antes que el detalle');
  assert.deepEqual(paleta.buscar(entradas, 'nada de nada'), []);
  assert.equal(paleta.buscar(entradas, '', { limite: 2 }).length, 2);
  assert.deepEqual(paleta.buscar(null, 'x'), []);
  assert.equal(entradas.length, 4, 'no muta');
});

test('paleta: construirEntradas (pantallas, ofertas, skills, acciones) y agrupado con índices', () => {
  const entradas = paleta.construirEntradas({
    nav: app.NAV,
    ofertas: [{ oferta_id: 'OF-1', fase: 'en_test', nivel: 'N2' }, { oferta_id: '_ejemplo', demo: true }, null, {}],
    skills: [{ slug: 'd3-arquitectura-oferta', descripcion: 'Arquitectura de la oferta', estado: 'v1' }, { slug: 'x', estado: 'borrador', version: '0.1' }, null],
    acciones: [{ id: 'tecnico', accion: 'tecnico', titulo: 'Alternar detalle técnico' }, { id: 'galeria', accion: 'galeria', titulo: 'Galería', soloTecnico: true }, { titulo: 'sin acción' }],
  });
  const por = (tipo) => entradas.filter((x) => x.tipo === tipo);
  assert.equal(por('pantalla').length, 25);
  assert.deepEqual(por('pantalla').map((x) => x.ruta.slice(2)), app.ENTRADAS.map((e) => e.ruta), 'una entrada por pantalla del menú, en su orden');
  assert.equal(por('pantalla').find((x) => x.titulo === 'Resumen').ruta, '#/resumen');
  assert.deepEqual(por('pantalla').find((x) => x.titulo === 'Resumen').atajo, ['g', 'r']);
  assert.equal(por('oferta').length, 2);
  assert.equal(por('oferta')[0].ruta, '#/oferta/OF-1');
  assert.equal(por('oferta')[0].detalle, 'en test · nivel 2', 'la fase y el nivel se leen en palabras');
  assert.match(por('oferta')[1].detalle, /demo/);
  assert.equal(por('skill').length, 2);
  assert.equal(por('skill')[0].ruta, '#/skills?slug=d3-arquitectura-oferta');
  assert.equal(por('accion').length, 1, 'la galería solo sale con el modo técnico; sin `accion` se descarta');
  assert.equal(paleta.construirEntradas({ acciones: [{ accion: 'galeria', titulo: 'G', soloTecnico: true }] }, { tecnico: true }).length, 1);
  const grupos = paleta.agruparPorGrupo(entradas);
  assert.deepEqual(grupos.map((g) => g.grupo), ['Pantallas', 'Ofertas', 'Guías de trabajo', 'Acciones']);
  assert.deepEqual(grupos.flatMap((g) => g.items.map((i) => i.indice)), entradas.map((_, i) => i), 'índices correlativos en la lista plana');
  assert.deepEqual(paleta.agruparPorGrupo([]), []);
  assert.equal(paleta.construirEntradas().length, 0);
});

test('paleta: también busca por el nombre y el número de la pieza («jurado», «pieza 4», «3 · Jurado», «testeo», «memoria»…)', () => {
  const entradas = paleta.construirEntradas({ nav: app.NAV });
  const rutas = (q) => paleta.buscar(entradas, q).map((x) => x.ruta.slice(2));
  const conjunto = (q) => rutas(q).sort(); // dentro de un mismo grupo el orden lo da el largo del título (a igualdad, el más corto primero): se compara el conjunto
  const grupoDe = (ruta) => app.ENTRADAS.find((e) => e.ruta === ruta);
  // nombre de la pieza: devuelve sus pantallas (la que se llama igual, primero)
  assert.equal(rutas('cerebro')[0], 'cerebro', 'la pantalla que se llama igual que la pieza va primero');
  assert.deepEqual(conjunto('cerebro'), ['cerebro', 'pulido', 'registro', 'skills']);
  assert.deepEqual(rutas('jurado'), ['jurado']);
  assert.deepEqual(conjunto('fabrica y tienda'), ['fabrica', 'landing', 'poscompra'], 'sin tildes, nombre completo del grupo');
  assert.deepEqual(conjunto('Fábrica de creativos'), ['fabrica', 'landing', 'poscompra'], 'el nombre que le da el dueño a la pieza 2');
  assert.deepEqual(conjunto('testeo'), ['campanas', 'descubrimiento', 'ofertas', 'operacion']);
  assert.deepEqual(conjunto('escala'), ['campanas', 'descubrimiento', 'ofertas', 'operacion']);
  assert.equal(rutas('robots')[0], 'robots', 'la pantalla que se llama igual va primero');
  assert.deepEqual(conjunto('robots'), ['agentes', 'avisos', 'pagos', 'robots', 'sistema']);
  assert.deepEqual(conjunto('dinero y reglas'), ['finanzas', 'parametros', 'quien-decide']);
  assert.equal(rutas('el sistema')[0], 'sistema', 'la pantalla «Salud del sistema» lleva esas palabras en su título y va primero');
  assert.ok(rutas('el sistema').includes('resumen'), 'el grupo «El sistema» sigue encontrando su pantalla (Resumen)');
  // número de pieza
  assert.deepEqual(conjunto('pieza 4'), ['campanas', 'descubrimiento', 'ofertas', 'operacion']);
  assert.deepEqual(conjunto('pieza 6'), ['cumplimiento', 'paises']);
  assert.deepEqual(rutas('3 · Jurado'), ['jurado']);
  assert.deepEqual(conjunto('5 robots'), ['agentes', 'avisos', 'pagos', 'robots', 'sistema']);
  for (let n = 1; n <= 6; n += 1) {
    const esperadas = app.ENTRADAS.filter((e) => e.pieza === n).map((e) => e.ruta).sort();
    assert.deepEqual(conjunto(`pieza ${n}`), esperadas, `pieza ${n}`);
  }
  assert.equal(rutas('pieza 7').length, 0);
  // palabras del dueño
  assert.ok(rutas('memoria').includes('cerebro'));
  assert.ok(rutas('clientes sinteticos').includes('jurado'));
  assert.ok(rutas('idiomas').includes('paises'));
  assert.ok(rutas('topes').includes('parametros'));
  // el detalle de cada resultado enseña dónde vive la pantalla, con el mismo rótulo del sidebar
  for (const x of entradas) assert.ok(x.detalle.startsWith(`${app.etiquetaGrupo(app.NAV.find((g) => g.grupo === grupoDe(x.ruta.slice(2)).grupo))} · `), x.detalle);
  assert.match(entradas.find((x) => x.ruta === '#/jurado').detalle, /^3 · Jurado · /);
  assert.match(entradas.find((x) => x.ruta === '#/resumen').detalle, /^El sistema · /);
  // buscar por el título sigue ganando: «Pagos» y «Países» no se pierden entre los que solo comparten grupo
  assert.equal(rutas('pagos')[0], 'pagos');
  assert.equal(rutas('paises')[0], 'paises');
  assert.equal(rutas('agentes')[0], 'agentes');
  // robusto a grupos sin `buscar` ni pieza
  const sola = paleta.construirEntradas({ nav: [{ grupo: 'G', items: [{ ruta: 'x', titulo: 'X', desc: 'una pantalla' }] }] });
  assert.equal(sola[0].detalle, 'G · una pantalla');
  assert.deepEqual(sola[0].palabras, ['G', 'G', 'x']);
  assert.equal(paleta.etiquetaGrupo({ grupo: 'G', pieza: 2 }), '2 · G');
});

test('paleta: palabras de todos los días encuentran la pantalla correcta («qué hago», «pendientes», «plata», «página de venta», «corregir»…)', () => {
  const entradas = paleta.construirEntradas({ nav: app.NAV });
  const primera = (q) => (paleta.buscar(entradas, q)[0] || { ruta: '' }).ruta.slice(2);
  assert.equal(primera('qué hago'), 'tareas');
  assert.ok(paleta.buscar(entradas, 'pendientes').slice(0, 2).some((x) => x.ruta === '#/tareas'), '«pendientes» también lleva a Mis tareas (y a Mejoras pendientes)');
  assert.equal(primera('lista'), 'tareas');
  assert.equal(primera('plata'), 'finanzas');
  assert.equal(primera('corregir'), 'pulido');
  assert.equal(primera('guías de trabajo'), 'skills');
  assert.equal(primera('pausa'), 'sistema');
  assert.ok(paleta.buscar(entradas, 'página de venta').some((x) => x.ruta === '#/landing'));
  assert.ok(paleta.buscar(entradas, 'después de pagar').some((x) => x.ruta === '#/poscompra'));
  // las acciones del shell también se encuentran con palabras simples
  const acciones = paleta.construirEntradas({ acciones: [{ id: 'pausar', accion: 'pausar', titulo: 'Pausar todo…', palabras: ['pausa', 'freno', 'emergencia', 'detener', 'parar', 'frenar'] }] });
  assert.ok(paleta.buscar(acciones, 'parar').length === 1 && paleta.buscar(acciones, 'frenar').length === 1);
});

test('app: el menú y la ayuda no traen jerga en el texto principal (descripciones, ayudas de grupo y atajos)', () => {
  const JERGA = /\b(gate|preflight|hash|sello|QA|Maker|motor|CBO|CPA|ROAS|UTM|checkout|bump|ledger|dry-run|JSON|YAML|latido|locale|SSE|token|snapshot|DoD)\b/i;
  for (const g of app.NAV) {
    assert.doesNotMatch(g.ayuda, JERGA, `${g.grupo}: ayuda del grupo`);
    for (const it of g.items) assert.doesNotMatch(it.desc, JERGA, `${it.ruta}: descripción`);
  }
  for (const b of app.gruposAtajos()) for (const f of b.filas) assert.doesNotMatch(f.texto, JERGA, f.texto);
});

test('paleta: los nombres de antes (landing, skills, pulido, registro, descubrimiento, operación, agentes, parámetros, poscompra) siguen encontrando su pantalla', () => {
  const entradas = paleta.construirEntradas({ nav: app.NAV });
  const primera = (q) => (paleta.buscar(entradas, q)[0] || { ruta: '' }).ruta.slice(2);
  const VIEJO = { landing: 'landing', skills: 'skills', pulido: 'pulido', registro: 'registro', descubrimiento: 'descubrimiento', 'operación': 'operacion', agentes: 'agentes', 'parámetros': 'parametros', poscompra: 'poscompra', sistema: 'sistema' };
  for (const [q, ruta] of Object.entries(VIEJO)) assert.equal(primera(q), ruta, `«${q}» lleva a ${ruta}`);
  // y los nombres nuevos, en el título que ve el dueño
  const NUEVO = { 'página de venta': 'landing', 'guías de trabajo': 'skills', 'mejoras pendientes': 'pulido', historial: 'registro', 'radar de ofertas': 'descubrimiento', resultados: 'operacion', 'equipo de ia': 'agentes', 'límites y reglas': 'parametros', 'después de la venta': 'poscompra', 'salud del sistema': 'sistema' };
  for (const [q, ruta] of Object.entries(NUEVO)) assert.equal(primera(q), ruta, `«${q}» lleva a ${ruta}`);
});

test('paleta: moverSeleccion con flechas, Inicio, Fin y páginas', () => {
  assert.equal(paleta.moverSeleccion(0, 5, 'ArrowDown'), 1);
  assert.equal(paleta.moverSeleccion(4, 5, 'ArrowDown'), 0, 'da la vuelta');
  assert.equal(paleta.moverSeleccion(0, 5, 'ArrowUp'), 4);
  assert.equal(paleta.moverSeleccion(2, 5, 'Home'), 0);
  assert.equal(paleta.moverSeleccion(2, 5, 'End'), 4);
  assert.equal(paleta.moverSeleccion(1, 20, 'PageDown'), 6);
  assert.equal(paleta.moverSeleccion(18, 20, 'PageDown'), 19);
  assert.equal(paleta.moverSeleccion(3, 20, 'PageUp'), 0);
  assert.equal(paleta.moverSeleccion(2, 5, 'x'), 2);
  assert.equal(paleta.moverSeleccion(0, 0, 'ArrowDown'), -1);
});

// ───────────────────────── atajos ─────────────────────────

test('atajos: g + letra salta de pantalla, con ventana de tiempo; ? y Ctrl/⌘+K y / abren ayuda y paleta', () => {
  const a = atajos.crearAtajos({ ventanaMs: 1000 });
  const k = (key, extra = {}) => ({ key, target: { tagName: 'BODY' }, ...extra });
  assert.deepEqual(a.procesar(k('g'), 0), { tipo: 'prefijo' });
  assert.equal(a.pendiente(500), true);
  assert.deepEqual(a.procesar(k('r'), 500), { tipo: 'ir', ruta: 'resumen', letra: 'r' });
  assert.equal(a.pendiente(500), false);
  assert.deepEqual(a.procesar(k('g'), 0), { tipo: 'prefijo' });
  assert.equal(a.procesar(k('o'), 2000), null, 'fuera de la ventana no salta');
  a.procesar(k('g'), 0);
  assert.deepEqual(a.procesar(k('o'), 100), { tipo: 'ir', ruta: 'ofertas', letra: 'o' });
  a.procesar(k('g'), 0);
  assert.deepEqual(a.procesar(k('d'), 10), { tipo: 'ir', ruta: 'descubrimiento', letra: 'd' });
  a.procesar(k('g'), 0);
  assert.equal(a.procesar(k('1'), 10), null, 'tecla sin pantalla (todas las letras ya tienen la suya)');
  assert.equal(a.pendiente(10), false);
  assert.deepEqual(a.procesar(k('r'), 20), null, 'sin `g` antes, una letra suelta no hace nada');
  assert.deepEqual(a.procesar(k('?', { shiftKey: true })), { tipo: 'ayuda' });
  assert.deepEqual(a.procesar(k('k', { ctrlKey: true })), { tipo: 'paleta' });
  assert.deepEqual(a.procesar(k('K', { metaKey: true })), { tipo: 'paleta' });
  assert.deepEqual(a.procesar(k('/')), { tipo: 'paleta' });
  assert.equal(a.procesar(k('r', { ctrlKey: true })), null, 'Ctrl+R (recargar) no se roba');
  a.procesar(k('g'), 0);
  assert.equal(a.procesar(k('r', { altKey: true }), 5), null);
  assert.equal(a.procesar(k('Shift')), null);
  assert.equal(a.procesar(null), null);
  assert.equal(a.procesar({}), null);
  a.procesar(k('g'), 0);
  assert.deepEqual(a.procesar(k('g'), 10), { tipo: 'prefijo' }, '«g g» reinicia la espera');
});

test('atajos: no se activan al escribir en campos ni con un modal abierto (Ctrl/⌘+K sí funciona en campos)', () => {
  const a = atajos.crearAtajos({ bloqueado: () => bloqueado });
  let bloqueado = false;
  for (const objetivo of [{ tagName: 'INPUT', type: 'text' }, { tagName: 'TEXTAREA' }, { tagName: 'SELECT' }, { tagName: 'DIV', isContentEditable: true }, { tagName: 'INPUT', type: 'search' }]) {
    assert.equal(a.procesar({ key: 'g', target: objetivo }, 0), null, JSON.stringify(objetivo));
  }
  assert.deepEqual(a.procesar({ key: 'g', target: { tagName: 'INPUT', type: 'checkbox' } }, 0), { tipo: 'prefijo' }, 'una casilla no es un campo de texto');
  assert.equal(atajos.esCampoEditable({ tagName: 'INPUT', type: 'radio' }), false);
  assert.equal(atajos.esCampoEditable({ tagName: 'BUTTON' }), false);
  assert.equal(atajos.esCampoEditable(null), false);
  assert.deepEqual(a.procesar({ key: 'k', ctrlKey: true, target: { tagName: 'INPUT', type: 'text' } }), { tipo: 'paleta' });
  bloqueado = true;
  assert.equal(a.procesar({ key: 'g', target: { tagName: 'BODY' } }, 0), null);
  assert.equal(a.procesar({ key: '?', shiftKey: true, target: { tagName: 'BODY' } }), null);
});

test('atajos: un atajo por pantalla, sin repetirse, y todas las pantallas del menú tienen el suyo', () => {
  const letras = Object.keys(atajos.ATAJOS_IR);
  assert.equal(new Set(letras).size, letras.length);
  assert.equal(new Set(Object.values(atajos.ATAJOS_IR)).size, letras.length, 'una pantalla, una letra');
  assert.equal(atajos.ATAJOS_IR.r, 'resumen');
  assert.equal(atajos.ATAJOS_IR.o, 'ofertas');
  assert.equal(atajos.ATAJOS_IR.d, 'descubrimiento');
  assert.ok(letras.every((l) => /^[a-z]$/.test(l) && l !== 'g'));
  for (const e of app.ENTRADAS) assert.ok(e.atajo, `${e.ruta} sin atajo`);
  assert.equal(atajos.atajoDeRuta('resumen'), 'r');
  assert.equal(atajos.atajoDeRuta('nada'), null);
});

test('atajos g + letra: las 25 pantallas del menú (sin colisiones), las 14 de antes conservan su letra y las 11 nuevas tienen la suya', () => {
  const viejas = { r: 'resumen', o: 'ofertas', d: 'descubrimiento', l: 'landing', c: 'campanas', e: 'operacion', f: 'finanzas', a: 'agentes', u: 'cumplimiento', p: 'parametros', s: 'skills', b: 'pulido', h: 'registro', t: 'sistema' };
  const nuevas = { m: 'cerebro', n: 'fabrica', x: 'poscompra', j: 'jurado', w: 'robots', v: 'avisos', y: 'pagos', i: 'paises', q: 'quien-decide', k: 'tareas', z: 'negocio' };
  for (const [letra, ruta] of Object.entries(viejas)) assert.equal(atajos.ATAJOS_IR[letra], ruta, `${ruta}: memoria muscular, la letra no cambia`);
  for (const [letra, ruta] of Object.entries(nuevas)) assert.equal(atajos.ATAJOS_IR[letra], ruta, `${ruta}: letra ${letra}`);
  assert.equal(Object.keys(atajos.ATAJOS_IR).length, 25);
  assert.deepEqual(Object.values(atajos.ATAJOS_IR).sort(), app.ENTRADAS.map((e) => e.ruta).sort(), 'exactamente las rutas del menú: ni sobra ni falta ninguna');
  assert.equal(Object.values(atajos.ATAJOS_IR).includes('oferta'), false, 'el alias del detalle no necesita letra: se abre con la de Ofertas');
  assert.equal(Object.keys(atajos.ATAJOS_IR).includes('g'), false, '«g» es el prefijo');
  // el mapa de ENTRADAS (letra de cada entrada) coincide con el mapa y todos los atajos funcionan de extremo a extremo
  for (const e of app.ENTRADAS) {
    assert.equal(atajos.ATAJOS_IR[e.atajo], e.ruta, `${e.ruta}: su letra lleva a su ruta`);
    const a = atajos.crearAtajos();
    assert.deepEqual(a.procesar({ key: 'g', target: { tagName: 'BODY' } }, 0), { tipo: 'prefijo' });
    assert.deepEqual(a.procesar({ key: e.atajo, target: { tagName: 'BODY' } }, 100), { tipo: 'ir', ruta: e.ruta, letra: e.atajo }, `g ${e.atajo} → ${e.ruta}`);
    assert.deepEqual(a.procesar({ key: e.atajo.toUpperCase(), target: { tagName: 'BODY' } }, 200), null, 'sin prefijo, la letra suelta no hace nada');
  }
  // las teclas especiales del shell no se pisan
  for (const especial of ['/', '?', 'k']) assert.ok(especial === 'k' || !(especial in atajos.ATAJOS_IR));
  assert.equal(atajos.ATAJOS_IR.k, 'tareas', '«g k» lleva a Mis tareas; la paleta sigue siendo Ctrl/⌘+K (no se pisan: uno lleva prefijo, el otro modificador)');
  // las reglas de atajos.js las cumple cada letra
  for (const l of Object.keys(atajos.ATAJOS_IR)) assert.match(l, /^[a-z]$/);
  assert.equal(atajos.atajoDeRuta('quien-decide'), 'q');
  assert.equal(atajos.atajoDeRuta('cerebro'), 'm');
});

// ───────────────────────── shell (partes puras) ─────────────────────────

test('app: migas del shell, contadores del menú, ayuda de atajos y ruta de desarrollo', () => {
  assert.deepEqual(app.migasDeRuta('resumen'), [{ texto: 'El sistema' }, { texto: 'Resumen' }]);
  assert.deepEqual(app.migasDeRuta('oferta', { id: 'OF-1' }), [{ texto: 'Testeo y escala' }, { texto: 'Ofertas', ruta: 'ofertas' }, { texto: 'OF-1' }]);
  assert.deepEqual(app.migasDeRuta('parametros'), [{ texto: 'Dinero y reglas' }, { texto: 'Límites y reglas' }]);
  assert.deepEqual(app.migasDeRuta('_diseno'), [{ texto: 'Desarrollo' }, { texto: 'Galería de componentes' }]);
  assert.deepEqual(app.migasDeRuta('nada'), []);

  assert.deepEqual(app.contadoresNav({ ofertas: [{ gates_pendientes: ['D3', 'D7'] }, { gates_pendientes: [] }], sistema: { pausa: { activa: false }, freno_captura: { activo: false } }, nuevosRegistro: 3 }),
    { resumen: 2, ofertas: 2, registro: 3, sistema: null });
  assert.equal(app.contadoresNav({ sistema: { pausa: { activa: true } } }).sistema, 'critico');
  assert.equal(app.contadoresNav({ sistema: { freno_captura: { activo: true } } }).sistema, 'critico');
  assert.deepEqual(app.contadoresNav(), { resumen: 0, ofertas: 0, registro: 0, sistema: null });
  assert.equal(app.contadoresNav({ nuevosRegistro: -4 }).registro, 0);

  const grupos = app.gruposAtajos();
  assert.equal(grupos.length, 9, 'un bloque por grupo del menú y el «General»');
  assert.deepEqual(grupos.slice(0, 8).map((g) => g.titulo), ['El sistema', '1 · Cerebro', '2 · Fábrica y tienda', '3 · Jurado', '4 · Testeo y escala', '5 · Robots', '6 · Países', 'Dinero y reglas'], 'mismos rótulos y orden que el sidebar');
  assert.equal(grupos.slice(0, 8).reduce((n, g) => n + g.filas.length, 0), 25);
  assert.deepEqual(grupos[0].filas[0], { texto: 'Resumen', teclas: ['g', 'r'] });
  assert.deepEqual(grupos[1].filas.map((f) => f.teclas.join(' ')), ['g m', 'g b', 'g s', 'g h'], 'Cerebro, Pulido, Skills, Registro');
  assert.deepEqual(grupos[3].filas, [{ texto: 'Jurado', teclas: ['g', 'j'] }]);
  assert.equal(grupos[8].titulo, 'General');
  assert.ok(grupos[8].filas.some((f) => f.teclas.includes('?')));
  assert.ok(grupos[8].filas.some((f) => f.teclas[1] === 'K'));

  assert.deepEqual(app.RUTAS_DEV, ['_diseno']);
  assert.equal(app.parsearHash('#/_diseno?seccion=tokens').ruta, '_diseno');
  assert.equal(app.parsearHash('#/_diseno?seccion=tokens').valida, true);
  assert.equal(app.parsearHash('#/__x').valida, false);
  assert.equal(app.parsearHash('#/_1').valida, false);
  assert.equal(app.parsearHash('#/_').valida, false);
  assert.equal(app.entradaDeRuta('_diseno'), null, 'no figura en el menú');
  assert.deepEqual(app.NAV.map((g) => g.grupo), ['El sistema', 'Cerebro', 'Fábrica y tienda', 'Jurado', 'Testeo y escala', 'Robots', 'Países', 'Dinero y reglas'], 'el menú por piezas (mapeo.md §9)');
});

// ───────────────────────── CSS: tokens, contraste, modos ─────────────────────────

function bloque(css, inicio) { const i = css.indexOf(inicio); assert.ok(i !== -1, `no está «${inicio}»`); return css.slice(i, css.indexOf('\n}', i)); }
const variables = (txt) => Object.fromEntries([...txt.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]));
const lum = (hex) => { const c = hex.replace('#', '').match(/../g).map((x) => parseInt(x, 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)); return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]; };
const contraste = (a, b) => { const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p); return (x + 0.05) / (y + 0.05); };

test('CSS: el tema oscuro automático repite exactamente los tokens del oscuro explícito (no se desincronizan)', () => {
  const css = leer('styles.css');
  const oscuro = bloque(css, ':root[data-tema="oscuro"] {');
  const i = css.indexOf('prefers-color-scheme: dark) {');
  const auto = css.slice(i, css.indexOf('\n  }', i));
  const a = variables(oscuro); const b = variables(auto);
  assert.ok(Object.keys(a).length > 40);
  assert.deepEqual(b, a);
  const tokensCompletos = (txt) => [...txt.matchAll(/--([\w-]+):/g)].map((m) => m[1]).sort();
  assert.deepEqual(tokensCompletos(auto), tokensCompletos(oscuro), 'también los que no son hex (sombras, velo…)');
});

test('CSS: los estados (bien, aviso, grave, crítico) y el acento cumplen AA en claro y oscuro', () => {
  const css = leer('styles.css');
  const modos = { claro: variables(bloque(css, ':root {')), oscuro: variables(bloque(css, ':root[data-tema="oscuro"] {')) };
  for (const [nombre, t] of Object.entries(modos)) {
    const pares = [['ok', 'ok-bg'], ['aviso', 'aviso-bg'], ['grave', 'grave-bg'], ['error', 'error-bg'], ['info', 'info-bg'], ['neutro', 'neutro-bg'], ['acento-fuerte', 'acento-bg'], ['sobre-acento', 'acento'],
      ['sobre-critico', 'critico-solido'], ['txt', 'bg'], ['txt', 'sup'], ['txt', 'sup-2'], ['txt-2', 'sup'], ['txt-2', 'sup-2'], ['txt-3', 'sup'], ['txt-3', 'sup-2'], ['acento', 'sup'], ['ok', 'sup'], ['aviso', 'sup'], ['grave', 'sup'], ['error', 'sup'],
      ['txt', 'elev'], ['terminal-txt', 'terminal-bg']];
    for (const [fg, bg] of pares) {
      assert.ok(t[fg] && t[bg], `${nombre}: falta --${fg} o --${bg}`);
      const r = contraste(t[fg], t[bg]);
      assert.ok(r >= 4.5, `${nombre}: --${fg} sobre --${bg} = ${r.toFixed(2)}:1 (< 4,5)`);
    }
    for (const [fg, bg] of [['borde-input', 'sup'], ['punto-ok', 'sup'], ['punto-error', 'sup'], ['acento', 'sup']]) {
      if (nombre === 'claro' && (fg === 'punto-ok')) continue; // 3,27:1 documentado en la guía dataviz
      const r = contraste(t[fg], t[bg]);
      assert.ok(r >= 3, `${nombre}: --${fg} sobre --${bg} = ${r.toFixed(2)}:1 (< 3, componentes de interfaz)`);
    }
  }
});

test('CSS: tres niveles de superficie distintos en ambos modos, oscuro sin negro puro, un solo acento y estados fijos de la guía dataviz', () => {
  const css = leer('styles.css');
  for (const [nombre, t] of [['claro', variables(bloque(css, ':root {'))], ['oscuro', variables(bloque(css, ':root[data-tema="oscuro"] {'))]]) {
    const niveles = new Set([t.bg, t.sup, t['sup-2'], t['sup-3']]);
    assert.equal(niveles.size, 4, `${nombre}: superficies distintas`);
    assert.ok(t.elev, `${nombre}: superficie elevada`);
    assert.deepEqual([t['punto-ok'], t['punto-aviso'], t['punto-grave'], t['punto-error']], ['#0ca30c', '#fab219', '#ec835a', '#d03b3b'], `${nombre}: paleta de estado fija`);
    for (let i = 1; i <= 8; i += 1) assert.ok(t[`serie-${i}`], `${nombre}: serie-${i}`);
  }
  const oscuro = variables(bloque(css, ':root[data-tema="oscuro"] {'));
  for (const k of ['bg', 'sup', 'sup-2', 'sup-3']) assert.notEqual(oscuro[k].toLowerCase(), '#000000', 'no es negro puro');
  assert.ok(lum(oscuro.bg) < lum(oscuro.sup) && lum(oscuro.sup) < lum(oscuro['sup-2']) && lum(oscuro['sup-2']) < lum(oscuro['sup-3']), 'oscuro: cada nivel más claro que el anterior');
  const claro = variables(bloque(css, ':root {'));
  assert.deepEqual([claro['serie-1'], claro['serie-2'], claro['serie-3'], claro['serie-4']], ['#2a78d6', '#eb6834', '#1baf7a', '#eda100'], 'categorías de la guía, en su orden');
});

test('CSS: densidad compacta de 28 px, modo técnico, movimiento reducido, escala 12–32 px y componentes nuevos', () => {
  const css = leer('styles.css');
  assert.match(css, /--fila:\s*38px/);
  assert.match(css, /:root\[data-densidad="compacta"\]\s*\{[^}]*--fila:\s*28px/);
  assert.match(css, /html:not\(\[data-tecnico="true"\]\) \.solo-tecnico\s*\{\s*display:\s*none/);
  assert.match(css, /@media \(prefers-reduced-motion: reduce\)\s*\{[^}]*animation:\s*none !important[^}]*transition:\s*none !important/);
  for (const t of ['--t-xs: .857rem', '--t-sm: .929rem', '--t-base: 1rem', '--t-md: 1.143rem', '--t-lg: 1.43rem', '--t-xl: 1.714rem', '--t-2xl: 2.286rem']) assert.ok(css.includes(t), t);
  assert.match(css, /--r-3:\s*12px/);
  assert.match(css, /--r-2:\s*8px/);
  assert.match(css, /--ancho-contenido:\s*1320px/);
  for (const clase of ['.cab', '.migas', '.atencion', '.metrica', '.detalle-tecnico', '.popover', '.termino', '.stepper', '.vacio-pasos', '.esq', '.paleta', '.sw', '.segmentado', '.kbd', '.btn--fantasma', '.btn--peligro', '.chip--grave', '.chip--critico', '.chip--acento', '.ayuda-btn', '.fuente-btn', '.comando__cab']) {
    assert.ok(css.includes(`${clase} `) || css.includes(`${clase}{`) || css.includes(`${clase},`) || css.includes(`${clase}:`) || css.includes(`${clase}[`) || css.includes(`${clase}__`) || css.includes(`${clase}--`), `sin estilos para ${clase}`);
  }
  assert.match(css, /\.tabla thead th \{[^}]*position:\s*sticky/, 'cabecera fija');
  assert.match(css, /\.tabla \{[^}]*font-variant-numeric:\s*tabular-nums/, 'cifras tabulares');
  assert.match(css, /:focus-visible \{[^}]*outline:\s*2px solid var\(--foco\)/, 'foco visible');
  assert.doesNotMatch(css, /@import|url\(\s*['"]?https?:|@font-face/);
  assert.doesNotMatch(css, /https?:\/\//);
});

// ───────────────────────── seguridad estática de lo nuevo ─────────────────────────

const sinComentarios = (src) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:\\'"`])\/\/.*$/gm, '$1');

test('seguridad estática: las piezas nuevas no usan innerHTML, eval, document.write ni orígenes externos', () => {
  const archivos = ['ui.js', 'app.js', 'estado.js', 'lib/iconos.js', 'lib/glosario.js', 'lib/glosario-indice.js', 'lib/paleta.js', 'lib/atajos.js', 'lib/popover.js', 'pages/_diseno.js', 'index.html', 'styles.css'];
  const prohibido = /\.(innerHTML|outerHTML)\b|insertAdjacentHTML\s*\(|document\.write(ln)?\s*\(|\beval\s*\(|new\s+Function\s*\(|\bsetTimeout\s*\(\s*['"`]|\bimportScripts\s*\(/;
  for (const rel of archivos) {
    const src = leer(rel);
    const limpio = rel.endsWith('.js') ? sinComentarios(src) : src;
    assert.doesNotMatch(limpio, prohibido, `${rel} usa una API prohibida`);
    assert.doesNotMatch(limpio, /https?:\/\/(?!127\.0\.0\.1|localhost|www\.w3\.org)/, `${rel} referencia un origen externo`);
  }
});

test('seguridad: el texto de datos nunca se interpreta como HTML en las piezas nuevas', () => {
  const hostil = '<img src=x onerror=alert(1)>';
  const piezas = [
    ui.atencion({ items: [{ tono: 'aviso', titulo: hostil, detalle: hostil, accion: { texto: hostil, ruta: 'x' } }] }),
    ui.metrica({ etiqueta: hostil, valor: hostil, contexto: hostil }),
    ui.pasos({ etapas: [{ id: 'a', nombre: hostil, codigo: hostil, estado: 'aprobado', aviso: hostil }] }),
    ui.vacioConPasos({ titulo: hostil, explicacion: hostil, pasos: [{ texto: hostil, comando: hostil }] }),
    ui.encabezadoPagina({ titulo: hostil, descripcion: hostil, migas: [{ texto: hostil, ruta: 'x' }, { texto: hostil }] }),
    ui.detalleTecnico(hostil, el('p', null, hostil)),
    ui.comando(hostil, { nota: hostil, titulo: hostil }),
    ui.termino('gate_h', { texto: hostil }),
    ui.chip(hostil, 'ok'),
    ui.tiempo('2026-11-06T14:00:00Z', { clase: hostil }),
  ];
  for (const p of piezas) {
    assert.equal(buscarTodos(p, 'img').length, 0);
    assert.ok(p.html.includes('&lt;img src=x onerror=alert(1)&gt;') || p.html.includes('&lt;img'), 'el HTML hostil se muestra como texto');
  }
  const peligrosa = ui.atencion({ items: [{ tono: 'aviso', titulo: 'x', accion: { texto: 'y', ruta: 'javascript:alert(1)' } }] });
  assert.equal(buscar(peligrosa, 'a.atencion__boton').getAttribute('href'), '#/javascript:alert(1)', 'una ruta con esquema peligroso queda como ancla inerte (#/…)');
  assert.equal(ui.hrefDeRuta('ofertas'), '#/ofertas');
  assert.equal(ui.hrefDeRuta('/ofertas'), '#/ofertas');
  assert.equal(ui.hrefDeRuta('#/x'), '#/x');
  assert.equal(ui.hrefDeRuta(''), '#/resumen');
});

test('index.html: la CSP no cambia, sin recursos externos y con la hoja de estilos del sistema de diseño', () => {
  const html = leer('index.html');
  assert.match(html, /default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; base-uri 'none'; form-action 'none'/);
  assert.match(html, /<link rel="stylesheet" href="styles\.css">/);
  assert.doesNotMatch(html, /\sstyle=|<style|\son[a-z]+\s*=/i);
});

// ───────────────────────── pedidos de U3 y U1: pasos con title, ayuda directa, desborde de pestañas, dedupe del glosario ─────────────────────────

test('pasos: cada etapa lleva title «<nombre>: <estado>» (también en modo compacto, donde el nombre se trunca)', () => {
  const etapas = [
    { id: 'a', nombre: 'Etiquetado de anuncios', estado: 'en_progreso' },
    { id: 'b', nombre: 'Validar', codigo: 'D2', estado: 'espera_firma', aviso: 'El QA dejó notas' },
    { id: 'c', nombre: 'Oferta', estado: 'aprobado' },
  ];
  for (const compacto of [true, false, 'auto']) {
    const botones = buscarTodos(ui.pasos({ etapas, compacto }), '.stepper__paso');
    assert.equal(botones[0].getAttribute('title'), 'Etiquetado de anuncios: En progreso', `compacto=${compacto}`);
    assert.equal(botones[2].getAttribute('title'), 'Oferta: Aprobado');
    assert.match(botones[1].getAttribute('title'), /^Validar: Espera tu firma/, 'con aviso se añade al final');
    assert.match(botones[1].getAttribute('title'), /El QA dejó notas$/);
  }
  assert.equal(buscarTodos(ui.pasos({ etapas: [{ id: 'x', nombre: '<b>x</b>', estado: 'pendiente' }] }), 'b').length, 0);
  assert.equal(buscar(ui.pasos({ etapas: [{ id: 'x', nombre: 'Sin estado' }] }), '.stepper__paso').getAttribute('title'), 'Sin estado: —');
});

test('resolverAyuda: clave del glosario, texto directo (string u objeto) y valores vacíos', () => {
  const r = ui.resolverAyuda;
  assert.deepEqual(r('gate_h'), { tipo: 'glosario', clave: 'gate_h' });
  assert.deepEqual(r('termino_que_no_existe'), { tipo: 'glosario', clave: 'termino_que_no_existe' }, 'con aspecto de clave y sin definición: el popover avisa (se nota el error de tecleo)');
  assert.deepEqual(r('Cuántas compras hubo en el periodo.'), { tipo: 'texto', texto: 'Cuántas compras hubo en el periodo.' });
  assert.deepEqual(r('  Total acumulado  '), { tipo: 'texto', texto: 'Total acumulado' }, 'mayúscula inicial: texto aunque sea una palabra');
  assert.deepEqual(r('lo que pasó hoy'), { tipo: 'texto', texto: 'lo que pasó hoy' }, 'con espacios: texto');
  assert.deepEqual(r({ texto: 'Mide X', titulo: 'Gasto' }), { tipo: 'texto', texto: 'Mide X', titulo: 'Gasto', largo: undefined });
  assert.deepEqual(r({ texto: 'a', largo: 'b' }), { tipo: 'texto', texto: 'a', titulo: undefined, largo: 'b' });
  assert.deepEqual(r({ clave: 'pm' }), { tipo: 'glosario', clave: 'pm' });
  assert.deepEqual(r({ texto: 'x', clave: 'pm' }).tipo, 'texto', 'el texto manda sobre la clave');
  for (const nada of [null, undefined, '', '   ', {}, { texto: '  ' }, 42, [], true]) assert.equal(r(nada), null, JSON.stringify(nada));
  assert.deepEqual(r('mi_clave', { mi_clave: { corto: 'x' } }), { tipo: 'glosario', clave: 'mi_clave' }, 'glosario inyectable');
  assert.deepEqual(r('Otra Cosa', { 'Otra Cosa': { corto: 'x' } }), { tipo: 'glosario', clave: 'Otra Cosa' });
});

test('ayuda y metrica: texto corto directo sin crear una clave por métrica; la clave del glosario sigue funcionando', () => {
  const texto = 'Cuántas veces se repitió la prueba <b>hoy</b>.';
  const m = ui.metrica({ etiqueta: 'Repeticiones', valor: 7, ayuda: texto });
  const boton = buscar(m, '.ayuda-btn');
  assert.ok(boton, 'hay botón «?»');
  assert.equal(boton.getAttribute('aria-label'), 'Qué es: Repeticiones', 'el nombre accesible usa la etiqueta de la métrica');
  assert.equal(boton.hasAttribute('data-termino'), false, 'no es un término del glosario');
  assert.match(boton.className, /ayuda-btn--texto/);
  boton.disparar('focus');
  const pop = doc.body.querySelector('.popover');
  assert.equal(pop.hidden, false);
  assert.match(pop.textContent, /Cuántas veces se repitió la prueba/);
  assert.equal(buscarTodos(pop, 'b').length, 0, 'el texto entra como texto, nunca como HTML');
  assert.equal(buscarTodos(pop, 'code').length, 0, 'sin «término técnico»');
  doc.teclado('Escape');
  assert.equal(pop.hidden, true);

  const obj = ui.metrica({ etiqueta: 'M', valor: 1, ayuda: { texto: 'Explicación corta', titulo: 'Nombre propio', largo: 'Detalle largo.' } });
  buscar(obj, '.ayuda-btn').disparar('focus');
  const p2 = doc.body.querySelector('.popover');
  assert.match(p2.textContent, /Nombre propio/);
  assert.match(p2.textContent, /Explicación corta/);
  assert.match(p2.textContent, /Detalle largo\./);
  doc.teclado('Escape');

  const g = ui.metrica({ etiqueta: 'M', valor: 1, ayuda: 'gate_h' });
  assert.equal(buscar(g, '.ayuda-btn').getAttribute('data-termino'), 'gate_h');
  buscar(g, '.ayuda-btn').disparar('focus');
  assert.match(doc.body.querySelector('.popover').textContent, /solo puedes aprobar tú/);
  doc.teclado('Escape');

  assert.equal(buscar(ui.metrica({ etiqueta: 'M', valor: 1 }), '.ayuda-btn'), null, 'sin ayuda, sin botón');
  assert.equal(buscar(ui.metrica({ etiqueta: 'M', valor: 1, ayuda: '' }), '.ayuda-btn'), null);
  assert.equal(ui.ayuda(''), null);
  assert.equal(ui.ayuda('Texto suelto').getAttribute('aria-label'), 'Más información', 'sin título ni etiqueta de métrica');
  assert.equal(ui.ayuda('Texto suelto', { titulo: 'Gasto' }).getAttribute('aria-label'), 'Qué es: Gasto');
  assert.equal(ui.ayuda('Texto suelto', { etiqueta: 'Aclaración' }).getAttribute('aria-label'), 'Aclaración');
  const sec = ui.seccion('Mi sección', el('p', null, 'x'), { glosario: 'Texto directo en la sección.' });
  assert.equal(buscar(sec, '.seccion__tit .ayuda-btn').getAttribute('aria-label'), 'Qué es: Mi sección');
});

test('estadoDesborde (puro): ninguno, der, izq y ambos con tolerancia de subpíxeles', () => {
  const d = ui.estadoDesborde;
  assert.deepEqual(d(0, 400, 400), { izq: false, der: false, valor: 'ninguno' }, 'cabe justo');
  assert.deepEqual(d(0, 400, 401), { izq: false, der: false, valor: 'ninguno' }, 'tolerancia de 2 px');
  assert.deepEqual(d(0, 390, 640), { izq: false, der: true, valor: 'der' }, 'al inicio, hay más a la derecha');
  assert.deepEqual(d(100, 390, 640), { izq: true, der: true, valor: 'ambos' });
  assert.deepEqual(d(250, 390, 640), { izq: true, der: false, valor: 'izq' }, 'al final');
  assert.deepEqual(d(249, 390, 640), { izq: true, der: false, valor: 'izq' }, 'a 1 px del final cuenta como final');
  assert.deepEqual(d(-5, 390, 640), { izq: false, der: true, valor: 'der' }, 'rebote negativo');
  assert.equal(d(0, 0, 640).valor, 'ninguno', 'sin ancho medido (aún no montado)');
  assert.equal(d(0, NaN, NaN).valor, 'ninguno');
  assert.equal(d(undefined, 300, 900).valor, 'der');
});

test('desborde de pestañas: tabs y barraPestanas marcan data-desborde al desplazar y al medirse; el CSS pinta el degradado', () => {
  const previo = globalThis.ResizeObserver;
  const observadores = [];
  globalThis.ResizeObserver = class { constructor(f) { this.f = f; observadores.push(this); } observe(n) { this.nodo = n; } };
  const medir = (nodo, { izq = 0, cliente = 390, total = 640 } = {}) => {
    nodo.scrollLeft = izq;
    Object.defineProperty(nodo, 'clientWidth', { value: cliente, configurable: true });
    Object.defineProperty(nodo, 'scrollWidth', { value: total, configurable: true });
  };
  try {
    const barra = ui.barraPestanas({ items: ['a', 'b', 'c', 'd', 'e', 'f'].map((id) => ({ id, titulo: `Sección ${id}` })) });
    assert.equal(barra.dataset.desborde, 'ninguno', 'recién creada: sin medir');
    const obs = observadores.find((o) => o.nodo === barra);
    assert.ok(obs, 'observa el cambio de tamaño de la lista');
    medir(barra);
    obs.f();
    assert.equal(barra.dataset.desborde, 'der', 'al montarse y medirse, hay más a la derecha');
    medir(barra, { izq: 120 });
    barra.disparar('scroll');
    assert.equal(barra.dataset.desborde, 'ambos');
    medir(barra, { izq: 250 });
    barra.disparar('scroll');
    assert.equal(barra.dataset.desborde, 'izq');
    medir(barra, { cliente: 800 });
    obs.f();
    assert.equal(barra.dataset.desborde, 'ninguno', 'si cabe, sin degradado');

    const t = ui.tabs(['a', 'b', 'c'].map((id) => ({ id, titulo: `Pestaña ${id}`, render: () => el('p', null, id) })));
    const lista = buscar(t, '.tabs__lista');
    const obs2 = observadores.find((o) => o.nodo === lista);
    assert.ok(obs2, 'ui.tabs también lo vigila');
    medir(lista, { total: 900 });
    obs2.f();
    assert.equal(lista.dataset.desborde, 'der');
    // elegir una pestaña la trae a la vista
    let vistas = 0;
    const tab = buscarTodos(t, '[role="tab"]')[2];
    tab.scrollIntoView = (opc) => { vistas += 1; assert.deepEqual(opc, { block: 'nearest', inline: 'nearest' }); };
    tab.click();
    assert.equal(vistas, 1);
  } finally {
    if (previo === undefined) delete globalThis.ResizeObserver; else globalThis.ResizeObserver = previo;
  }
  // sin ResizeObserver (p. ej. un navegador antiguo) tampoco lanza y deja el valor seguro
  const sin = ui.barraPestanas({ items: [{ id: 'x', titulo: 'X' }] });
  assert.equal(sin.dataset.desborde, 'ninguno');
  const css = leer('styles.css');
  assert.match(css, /\.tabs__lista\[data-desborde="der"\] \{[^}]*mask-image:\s*linear-gradient\(to right, #000 calc\(100% - 40px\), transparent\)/);
  assert.match(css, /\.tabs__lista\[data-desborde="izq"\] \{[^}]*mask-image:\s*linear-gradient\(to left/);
  assert.match(css, /\.tabs__lista\[data-desborde="ambos"\] \{[^}]*mask-image:\s*linear-gradient\(to right, transparent, #000 40px/);
  assert.match(css, /\.tabs__tab \{[^}]*flex:\s*none/, 'las pestañas no se encogen: desbordan y se desplazan');
});

test('glosario-indice: deduplica claves repetidas (el global manda, luego el primer fragmento) y la fusión es determinista', () => {
  const base = { costo_ia: { corto: 'definición global del costo de IA' }, a: { corto: 'definición base de a' } };
  const conflictos = []; const origenes = {};
  const destino = { ...base };
  const hechos = indice.fusionarFragmentos(destino, [
    { nombre: 'resumen', terminos: { costo_ia: { corto: 'versión de resumen' }, solo_resumen: { corto: 'solo en resumen' } } },
    null,
    { nombre: 'operacion', terminos: { costo_ia: { corto: 'versión de operación' }, solo_resumen: { corto: 'otra versión' }, solo_operacion: { corto: 'solo en operación' } } },
  ], conflictos, origenes);
  assert.equal(destino.costo_ia.corto, 'definición global del costo de IA', 'el global manda');
  assert.equal(destino.solo_resumen.corto, 'solo en resumen', 'entre fragmentos, el primero del orden');
  assert.equal(destino.solo_operacion.corto, 'solo en operación');
  assert.deepEqual(hechos, [{ nombre: 'resumen', claves: 1 }, { nombre: 'operacion', claves: 1 }]);
  assert.deepEqual(conflictos, [
    { clave: 'costo_ia', origen: 'resumen', ganador: 'global' },
    { clave: 'costo_ia', origen: 'operacion', ganador: 'global' },
    { clave: 'solo_resumen', origen: 'operacion', ganador: 'resumen' },
  ]);
  // idempotente: volver a mezclar el mismo origen no inventa conflictos ni cambia nada
  const antes = JSON.stringify(destino);
  const n = conflictos.length;
  indice.fusionarFragmentos(destino, [{ nombre: 'resumen', terminos: { solo_resumen: { corto: 'solo en resumen' } } }], conflictos, origenes);
  assert.equal(conflictos.length, n);
  assert.equal(JSON.stringify(destino), antes);
  // el orden lo marca la lista, no el de llegada
  const alReves = { ...base };
  indice.fusionarFragmentos(alReves, [
    { nombre: 'operacion', terminos: { x: { corto: 'versión de operación' } } },
    { nombre: 'resumen', terminos: { x: { corto: 'versión de resumen' } } },
  ], [], {});
  assert.equal(alReves.x.corto, 'versión de operación');
  assert.deepEqual(indice.fusionarFragmentos({}, null), []);
});

test('glosario real: costo_ia vive en el global y los fragmentos que lo repiten no lo pisan; ningún conflicto tiene un ganador desconocido', async () => {
  assert.ok(glosario.GLOSARIO.costo_ia, 'costo_ia está en glosario.js');
  assert.equal(indice.GLOSARIO_TOTAL.costo_ia, glosario.GLOSARIO.costo_ia, 'la entrada total es la global');
  assert.match(indice.GLOSARIO_TOTAL.costo_ia.corto, /agentes/);
  assert.equal(indice.ORIGENES.costo_ia, undefined, 'sin origen de fragmento: viene del global');
  assert.ok(!indice.CONFLICTOS.some((c) => c.clave === 'costo_ia'), 'costo_ia ya no está repetido en ningún fragmento (una sola definición)');
  const validos = new Set(['global', ...indice.FRAGMENTOS]);
  for (const c of indice.CONFLICTOS) {
    assert.ok(validos.has(c.ganador), `ganador desconocido: ${c.ganador}`);
    assert.ok(validos.has(c.origen) && c.origen !== 'global', `origen desconocido: ${c.origen}`);
    assert.notEqual(c.ganador, c.origen);
    assert.ok(indice.GLOSARIO_TOTAL[c.clave], c.clave);
  }
  const antes = JSON.stringify(indice.GLOSARIO_TOTAL);
  const conflictosAntes = JSON.stringify(indice.CONFLICTOS);
  await indice.recargarFragmentos();
  assert.equal(JSON.stringify(indice.GLOSARIO_TOTAL), antes, 'recargar es idempotente');
  assert.equal(JSON.stringify(indice.CONFLICTOS), conflictosAntes, 'y no duplica los conflictos');
  for (const k of Object.keys(indice.GLOSARIO_TOTAL)) assert.match(k, /^[a-z0-9_]+$/);
});

test('el esperar() del arnés no deja temporizadores: todo termina', async () => { await esperar(5); });
