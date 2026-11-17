// Pruebas de la pantalla Sistema (P2): lib/sistema.js (puro) y pages/sistema.js (DOM y API falsos).
import test from 'node:test';
import assert from 'node:assert/strict';
import { instalar, buscar, buscarTodos } from '../fixtures/dashboard/shell/dom_falso.mjs';
import { cargarSobre, crearApiFalsa, crearCtx, dormir, ErrorApiFalso } from '../fixtures/dashboard/shell/ctx_falso.mjs';

instalar();
const L = await import('../../dashboard/web/lib/sistema.js');
const { ui } = await import('../../dashboard/web/ui.js');
const pagina = await import('../../dashboard/web/pages/sistema.js');

const ofertas = cargarSobre('ofertas').datos;
const sis = cargarSobre('sistema');

// ───────────────────────── lib ─────────────────────────

test('instrucciones para levantar PAUSA y freno: solo texto y comando, nunca una acción del panel', () => {
  assert.equal(L.instruccionPausa({ activa: false }), null);
  assert.equal(L.instruccionPausa(null), null);
  const p = L.instruccionPausa({ activa: true, motivo: 'gasto alto' });
  assert.equal(p.comando, 'rm empresa/PAUSA');
  assert.ok(p.pasos.length >= 3);
  assert.match(p.pasos[0], /gasto alto/);
  assert.equal(L.instruccionFreno(null), null);
  assert.equal(L.instruccionFreno({ activo: false }), null);
  const f = L.instruccionFreno({ activo: true, motivo: 'HTTP 403 (Document)' });
  assert.equal(f.comando, 'rm empresa/captura/freno.json');
  assert.equal(f.comandoLeer, 'cat empresa/captura/freno.json');
  assert.match(f.pasos.join(' '), /HTTP 403/);
  assert.match(f.pasos.join(' '), /solo una persona/);
});

test('elementosSalud: PAUSA, freno, preflight, entorno y cadena con su tono', () => {
  const ahora = Date.parse('2026-11-06T14:00:00Z');
  const s = L.elementosSalud({ sistema: sis.datos, conexion: 'sse', latenciaMs: 12.4, cadenaOk: true, ahoraMs: ahora });
  const por = Object.fromEntries(s.map((x) => [x.id, x]));
  assert.deepEqual([por.panel.tono, por.pausa.tono, por.freno.tono, por.infra.tono, por.entorno.tono, por.registro.tono], ['ok', 'ok', 'aviso', 'aviso', 'info', 'ok']);
  assert.deepEqual(s.map((x) => x.id), ['pausa', 'freno', 'infra', 'motor', 'registro', 'panel', 'entorno'], 'orden de la franja: lo que frena primero');
  assert.ok(s.every((x) => x.icono && x.titulo && x.texto && x.detalle), 'todo elemento lleva icono + etiqueta + frase');
  assert.equal(por.pausa.tecnico, 'empresa/PAUSA', 'la ruta ya no va a la vista: queda como dato técnico');
  assert.doesNotMatch(por.pausa.detalle + por.freno.detalle + por.infra.detalle, /empresa\//);
  assert.match(por.panel.detalle, /12 ms/);
  assert.match(por.freno.detalle, /HTTP 403/);
  assert.deepEqual([por.motor.tono, por.motor.texto], ['aviso', 'Aún no existe'], 'motor_disponible:false se avisa, no se oculta');
  assert.equal(L.elementosSalud({ sistema: { ...sis.datos, motor_disponible: true }, conexion: 'sse' }).find((x) => x.id === 'motor').tono, 'ok');
  assert.equal(L.elementosSalud({ sistema: { ...sis.datos, motor_disponible: undefined }, conexion: 'sse' }).some((x) => x.id === 'motor'), false);
  assert.equal(L.elementosSalud({ sistema: sis.datos, conexion: 'sondeo' }).find((x) => x.id === 'panel').tono, 'aviso');
  assert.equal(L.elementosSalud({ sistema: sis.datos, conexion: 'sin_conexion' }).find((x) => x.id === 'panel').tono, 'error');
  const roto = L.elementosSalud({ sistema: sis.datos, conexion: 'sse', cadenaOk: false }).find((x) => x.id === 'registro');
  assert.deepEqual([roto.tono, roto.texto], ['error', 'ALTERADO']);
  assert.equal(L.elementosSalud({ sistema: sis.datos, conexion: 'sse' }).some((x) => x.id === 'registro'), false, 'sin dato de cadena no se inventa');
  const sinSis = L.elementosSalud({ sistema: null, conexion: 'sin_conexion' });
  assert.equal(sinSis.at(-1).tono, 'error');
  const pausa = L.elementosSalud({ sistema: { ...sis.datos, pausa: { activa: true, desde: 'x', motivo: 'm' } }, conexion: 'sse' }).find((x) => x.id === 'pausa');
  assert.deepEqual([pausa.tono, pausa.texto], ['error', 'ACTIVA']);
  assert.equal(L.elementosSalud({ sistema: { ...sis.datos, entorno: 'produccion' }, conexion: 'sse' }).find((x) => x.id === 'entorno').tono, 'aviso');
});

test('normalizarAcciones: formato real de GET /acciones (tipos, comando, próximamente) y variantes; disponibles primero', () => {
  const a = L.normalizarAcciones(cargarSobre('acciones').datos);
  assert.equal(a.length, 8);
  assert.equal(a.at(-1).id, 'landing_generar');
  assert.equal(a.at(-1).proximamente, true);
  assert.match(a.at(-1).motivo, /B4/);
  assert.equal(a.at(-2).id, 'exportar_local', 'lectura antes que escribe_local, y las disponibles antes que «próximamente»');
  const ps = a.find((x) => x.id === 'pruebas_paquete');
  assert.deepEqual([ps.parametros[0].tipo, ps.parametros[0].requerido], ['eleccion', true]);
  assert.deepEqual(ps.parametros[0].opciones, ['agentes', 'contratos', 'dashboard', 'engine', 'landing', 'scripts']);
  assert.equal(ps.comando, 'python -m unittest discover -s tests/<paquete> -t .');
  assert.equal(ps.timeoutS, 600);
  const plan = a.find((x) => x.id === 'barrido_plan_ver').parametros;
  assert.deepEqual([plan[1].tipo, plan[1].flag, plan[1].requerido], ['bandera', '--consultas', false], 'una bandera sin «requerido» es opcional');
  const ent = a.find((x) => x.id === 'barrido_muestra').parametros[1];
  assert.deepEqual([ent.tipo, ent.minimo, ent.maximo], ['entero', 1, 50]);
  assert.equal(L.normalizarAcciones({ acciones: [{ id: 'z', en_curso: 'job-9', parametros: [] }] })[0].enCurso, 'job-9');
  const v = L.normalizarAcciones({ acciones: [{ id: 'x', params: { oferta: { tipo: 'oferta_id' }, n: 'entero' }, riesgo: 'lectura' }, { sin_id: true }, null, { id: 'y', args: [{ clave: 'p', valores: ['a', 'b'], opcional: true }] }] });
  assert.equal(v.length, 2);
  assert.deepEqual(v[0].parametros.map((p) => [p.nombre, p.tipo]), [['oferta', 'oferta'], ['n', 'entero']], 'alias de tipos antiguos');
  assert.deepEqual(v[1].parametros[0], { nombre: 'p', tipo: 'eleccion', requerido: false, opciones: ['a', 'b'], descripcion: '', porDefecto: null, minimo: null, maximo: null, flag: null });
  assert.deepEqual(L.normalizarAcciones(null), []);
  assert.deepEqual(L.normalizarAcciones('x'), []);
});

test('validarArgs (tipos de la lista blanca): corrida, oferta, eleccion, entero con rango, bandera; nada inválido pasa a args', () => {
  const ps = [
    { nombre: 'paquete', tipo: 'eleccion', requerido: true, opciones: ['engine', 'dashboard'] },
    { nombre: 'oferta', tipo: 'oferta', requerido: true },
    { nombre: 'corrida', tipo: 'corrida', requerido: true },
    { nombre: 'n', tipo: 'entero', requerido: false, minimo: 1, maximo: 50 },
    { nombre: 'consultas', tipo: 'bandera', requerido: false, flag: '--consultas' },
    { nombre: 'nota', tipo: 'texto', requerido: false },
  ];
  const bien = L.validarArgs(ps, { paquete: 'engine', oferta: ' _ejemplo ', corrida: '2026-11-06-a', n: '42', nota: ' hola ', consultas: true });
  assert.deepEqual(bien, { ok: true, errores: {}, args: { paquete: 'engine', oferta: '_ejemplo', corrida: '2026-11-06-a', n: 42, consultas: true, nota: 'hola' } });
  assert.equal(L.validarArgs(ps, { paquete: 'engine', oferta: 'OF-202611-01', corrida: '2026-11-06-a' }).args.consultas, false, 'la bandera sin marcar viaja como false (el servidor exige booleano)');
  const mal = L.validarArgs(ps, { paquete: '--live', oferta: 'OF-1; rm -rf /', corrida: '2026-11-06; x', n: '99', nota: 'x'.repeat(201) });
  assert.equal(mal.ok, false);
  assert.deepEqual(Object.keys(mal.errores).sort(), ['corrida', 'n', 'nota', 'oferta', 'paquete']);
  assert.match(mal.errores.n, /Entre 1 y 50/);
  for (const k of ['paquete', 'oferta', 'corrida', 'n', 'nota']) assert.equal(k in mal.args, false, `${k} inválido no pasa`);
  assert.deepEqual(L.validarArgs(ps, {}).errores, { paquete: 'Obligatorio.', oferta: 'Obligatorio.', corrida: 'Obligatorio.' });
  assert.equal(L.validarArgs([], {}).ok, true);
  assert.equal(L.validarArgs([{ nombre: 'n', tipo: 'entero', requerido: true }], { n: '1234567890' }).ok, false, 'entero de más de 9 cifras');
  assert.equal(L.validarArgs([{ nombre: 'n', tipo: 'entero', requerido: true }], { n: 0 }).args.n, 0, 'el cero es un valor');
  assert.equal(L.validarArgs([{ nombre: 'o', tipo: 'oferta', requerido: true }], { o: '_Mala' }).ok, false, 'mismo patrón que el servidor');
});

test('limpiarSalida y normalizarJob: ANSI fuera, variantes de formato y siguiente offset', () => {
  assert.equal(L.limpiarSalida('\u001b[31mrojo\u001b[0m\r\nlinea\rotra'), 'rojo\nlinea\notra');
  assert.equal(L.limpiarSalida('\u001b]0;título\u0007ok'), 'ok');
  assert.equal(L.limpiarSalida(null), '');
  const a = L.normalizarJob({ estado: 'corriendo', salida: 'hola\n', siguiente: 5 }, 0);
  assert.deepEqual([a.terminado, a.texto, a.siguiente, a.estado], [false, 'hola\n', 5, 'corriendo']);
  const b = L.normalizarJob({ estado: 'terminado', codigo: 0, salida: 'fin\n', siguiente: 9 }, 5);
  assert.deepEqual([b.terminado, b.codigo, b.estado], [true, 0, 'terminado']);
  const c = L.normalizarJob({ terminado: true, codigo_salida: 2, lineas: ['a', { texto: 'b' }] }, 0);
  assert.deepEqual([c.terminado, c.codigo, c.texto, c.estado], [true, 2, 'a\nb\n', 'error']);
  assert.equal(L.normalizarJob({ estado: 'corriendo', salida: 'abc' }, 10).siguiente, 13, 'sin offset del servidor: suma lo recibido');
  assert.deepEqual(L.normalizarJob(null, 7), { estado: 'desconocido', terminado: false, codigo: null, texto: '', siguiente: 7 });
  assert.equal(L.normalizarJob({ estado: 'timeout' }, 0).terminado, true);
  assert.equal(L.veredictoJob({ terminado: false }).tono, 'info');
  assert.deepEqual(L.veredictoJob({ terminado: true, codigo: 0 }), { tono: 'ok', texto: 'Terminó bien', icono: 'ok', clave: 'ok' });
  assert.deepEqual(L.veredictoJob({ terminado: false }), { tono: 'info', texto: 'Corriendo…', icono: 'progreso', clave: 'corriendo' });
  assert.match(L.veredictoJob({ terminado: true, codigo: 3 }).texto, /error \(código 3\)/);
  assert.equal(L.veredictoJob({ terminado: true, codigo: 3 }).tono, 'error');
  assert.equal(L.veredictoJob({ terminado: true, codigo: null }).tono, 'neutro');
  assert.equal(L.veredictoJob({ terminado: true, codigo: null, estadoServidor: 'timeout' }).tono, 'error');
  assert.match(L.veredictoJob({ terminado: true, codigo: null, estadoServidor: 'timeout' }).texto, /tiempo/);
  assert.match(L.veredictoJob({ terminado: true, codigo: 0, estadoServidor: 'tope_salida' }).texto, /256 KB/);
  assert.equal(L.normalizarJob({ estado: 'ok', terminado: true, codigo: 0, comando: 'python -m x', salida: '' }).comando, 'python -m x');
  assert.equal(L.tonoRiesgo('lectura'), 'ok');
  assert.equal(L.tonoRiesgo('escribe_local'), 'aviso');
  assert.equal(L.rotuloRiesgo('escribe_local'), 'Guarda archivos aquí');
  assert.equal(L.rotuloRiesgo('lectura'), 'Solo mira');
  assert.deepEqual([L.iconoRiesgo('lectura'), L.iconoRiesgo('escribe_local')], ['ojo', 'lapiz']);
  assert.match(L.explicacionRiesgo('lectura'), /No cambia nada/);
});

test('agruparPreflight: ítems por bloque con nombre humano, peor estado primero y conteos; sin items no se inventa nada', () => {
  assert.deepEqual(L.agruparPreflight(null), { hay: false, total: 0, conteos: { ok: 0, aviso: 0, error: 0, neutro: 0 }, criticosRojos: 0, bloques: [] });
  assert.equal(L.agruparPreflight({ semaforo: 'VERDE' }).hay, false, 'infra sin items (servidor antiguo)');
  const infra = { items: [
    { id: 'S-02', bloque: 'stripe', estado: 'VERDE', critico: true, medido_en: '2026-11-06T12:00:00Z', expira_en: '2026-11-06T18:00:00Z', mensaje: 'ok', latencia_ms: 85 },
    { id: 'M-02', bloque: 'meta', estado: 'ROJO', critico: true, medido_en: '2026-11-06T12:00:00Z', expira_en: '2026-11-06T13:00:00Z', mensaje: 'cuenta deshabilitada' },
    { id: 'M-01', bloque: 'meta', estado: 'VERDE', critico: true, medido_en: '2026-11-06T12:00:00Z', expira_en: '2026-11-06T18:00:00Z' },
    { id: 'M-10', bloque: 'meta', estado: 'PENDIENTE_EXTERNO', critico: false, medido_en: '2026-11-06T12:00:00Z', expira_en: '2026-11-06T18:00:00Z' },
    { id: 'C-01', bloque: 'cloudflare', estado: 'AMARILLO', critico: false, medido_en: '2026-11-06T12:00:00Z', expira_en: '2026-11-06T18:00:00Z' },
    { id: 'X-01', bloque: 'raro', estado: 'VERDE' }, null, { sin_id: true },
  ] };
  const g = L.agruparPreflight(infra, Date.parse('2026-11-06T14:00:00Z'));
  assert.deepEqual(g.bloques.map((b) => [b.id, b.nombre, b.tono]), [['meta', 'Meta (anuncios)', 'error'], ['cloudflare', 'Cloudflare (dominios y sitio)', 'aviso'], ['stripe', 'Stripe (cobros)', 'ok'], ['raro', 'Raro', 'ok']]);
  assert.deepEqual(g.bloques[0].items.map((i) => i.id), ['M-02', 'M-10', 'M-01'], 'dentro del bloque: rojo, luego pendiente, luego verde');
  assert.deepEqual(g.conteos, { ok: 3, aviso: 1, error: 1, neutro: 1 });
  assert.equal(g.total, 6);
  assert.equal(g.criticosRojos, 1);
  const m02 = g.bloques[0].items[0];
  assert.deepEqual([m02.etiqueta, m02.icono, m02.mensaje, m02.critico, m02.vencido], ['Rojo', 'alerta', 'cuenta deshabilitada', true, true], 'expira_en pasado: vencido');
  assert.equal(g.bloques[2].items[0].latenciaMs, 85);
  assert.deepEqual(L.infoEstadoItem('PENDIENTE'), { tono: 'neutro', etiqueta: 'Pendiente', icono: 'reloj' });
  assert.equal(L.infoEstadoItem('rarisimo').tono, 'neutro');
  assert.equal(L.peorTono([{ tono: 'ok' }, { tono: 'aviso' }, { tono: 'neutro' }]), 'aviso');
  assert.equal(L.peorTono([{ tono: 'ok' }, { tono: 'error' }]), 'error');
  assert.equal(L.peorTono([]), 'ok');
});

test('agruparAcciones y etiquetaParametro: temas con título corto; lo desconocido va a «Otras»', () => {
  const g = L.agruparAcciones(L.normalizarAcciones(cargarSobre('acciones').datos));
  assert.deepEqual(g.map((x) => x.titulo), ['Buscar ofertas en el mercado', 'Revisar que los formatos estén bien', 'Comprobar que el sistema funciona', 'Otras tareas', 'Página de venta']);
  assert.equal(g.flatMap((x) => x.acciones).length, 8, 'no se pierde ninguna acción');
  assert.deepEqual(g[0].acciones.slice(0, 2).map((a) => a.tituloCorto), ['Ver cómo va una búsqueda de ofertas', 'Ver el plan de una búsqueda']);
  assert.deepEqual(L.agruparAcciones(null), []);
  assert.equal(L.etiquetaParametro({ nombre: 'corrida', requerido: true }), 'Búsqueda (fecha y letra) *');
  assert.equal(L.etiquetaParametro({ nombre: 'paquete', requerido: true }), 'Parte del sistema a comprobar *');
  assert.equal(L.etiquetaParametro({ nombre: 'max_filas', requerido: false }), 'Max filas');
  assert.equal(L.etiquetaParametro(null), '');
});

// ───────────────────────── página ─────────────────────────

const ctxDe = (api, extra = {}) => crearCtx({ api, ui, ruta: 'sistema', estado: { ofertas, conectado: 'sse' }, ...extra });
const textoBotones = (raiz) => buscarTodos(raiz, 'button').map((b) => b.textContent.trim());

test('Sistema: franja de salud con veredicto, icono + etiqueta por elemento; PAUSA y freno con instrucciones y SIN botón de borrado', async () => {
  const ctx = ctxDe(crearApiFalsa());
  const raiz = await pagina.render(ctx);
  const texto = raiz.textContent;
  assert.equal(buscar(raiz, 'h1').textContent, 'Salud del sistema');
  for (const t of ['Salud del sistema', 'Pausa general', 'Freno de la captura de anuncios', 'Cuentas y servicios: chequeo antes de lanzar', 'Tareas que puedes ejecutar desde aquí']) assert.match(texto, new RegExp(t));
  // franja: veredicto + una celda por elemento, cada una con icono, etiqueta (chip) y frase
  const ver = buscar(raiz, '.u1s-veredicto');
  assert.equal(ver.getAttribute('data-tono'), 'aviso');
  assert.match(ver.textContent, /La captura de anuncios está frenada/);
  const celdas = buscarTodos(raiz, '.u1s-celda');
  assert.deepEqual(celdas.map((c) => c.getAttribute('data-id')), ['pausa', 'freno', 'infra', 'motor', 'registro', 'panel', 'entorno']);
  for (const c of celdas) {
    assert.ok(buscar(c, 'svg'), `icono en ${c.getAttribute('data-id')}`);
    assert.ok(buscar(c, '.chip'), `etiqueta en ${c.getAttribute('data-id')}`);
  }
  assert.match(texto, /Desarrollo/);
  assert.match(texto, /Responde en \d+ ms/);
  // las rutas de archivo ya no se ven en la franja: van a «Detalle técnico»
  assert.doesNotMatch(buscarTodos(raiz, '.u1s-celda__detalle').map((d) => d.textContent).join('|'), /empresa\//);
  for (const d of buscarTodos(raiz, '.detalle-tecnico')) d.montar();
  assert.match(buscarTodos(raiz, '.detalle-tecnico').map((d) => d.textContent).join('|'), /empresa\/PAUSA/);
  // freno puesto: motivo + instrucción + comandos (cerrados) copiables
  assert.match(texto, /HTTP 403 \(Document\)/);
  assert.match(texto, /Cómo levantar el freno de la captura de anuncios/);
  const cmds = buscarTodos(raiz, '.comando__texto').map((c) => c.textContent);
  assert.ok(cmds.includes('rm empresa/captura/freno.json'));
  assert.ok(cmds.includes('cat empresa/captura/freno.json'));
  assert.ok(cmds.some((c) => c.includes('infra.preflight ejecutar')));
  // ningún botón borra, levanta, reanuda o quita nada
  for (const t of textoBotones(raiz)) assert.doesNotMatch(t, /borrar|eliminar|levantar|quitar|reanudar|desactivar|liberar/i, `botón «${t}»`);
  // PAUSA inactiva: ofrece «Pausar todo» (que delega en la barra) y nada más
  const pausar = buscarTodos(raiz, 'button').find((b) => b.textContent.includes('Pausar todo'));
  assert.ok(pausar);
  pausar.click();
  assert.deepEqual(ctx._navegaciones, ['pausarTodo']);
  assert.match(texto, /Amarillo/);
  assert.match(texto, /no sirve para gastar ni activar de verdad/);
});

test('Sistema: preflight por ítem con icono + etiqueta, agrupado por bloque y con lo que falla abierto', async () => {
  const infra = { semaforo: 'ROJO', modo: 'vivo', generado_en: '2026-11-06T13:00:00Z', valido_hasta: '2026-11-06T19:00:00Z', items: [
    { id: 'M-01', bloque: 'meta', estado: 'VERDE', critico: true, medido_en: '2026-11-06T13:00:00Z', expira_en: '2099-01-01T00:00:00Z', mensaje: 'token válido', latencia_ms: 120 },
    { id: 'M-02', bloque: 'meta', estado: 'ROJO', critico: true, medido_en: '2026-11-06T13:00:00Z', expira_en: '2099-01-01T00:00:00Z', mensaje: 'cuenta deshabilitada' },
    { id: 'S-01', bloque: 'stripe', estado: 'VERDE', critico: true, medido_en: '2026-11-06T13:00:00Z', expira_en: '2099-01-01T00:00:00Z' },
    { id: 'C-01', bloque: 'cloudflare', estado: 'PENDIENTE_EXTERNO', critico: false, medido_en: '2026-11-06T13:00:00Z', expira_en: '2099-01-01T00:00:00Z' },
  ] };
  const raiz = await pagina.render(ctxDe(crearApiFalsa({ '/sistema': { ...sis, datos: { ...sis.datos, infra } } })));
  const bloques = buscarTodos(raiz, '.u1s-bloque');
  assert.deepEqual(bloques.map((b) => buscar(b, 'summary span').textContent), ['Meta (anuncios)', 'Cloudflare (dominios y sitio)', 'Stripe (cobros)']);
  assert.deepEqual(bloques.map((b) => b.hasAttribute('open')), [true, true, false], 'abiertos los que tienen algo rojo, amarillo o pendiente');
  const items = buscarTodos(bloques[0], '.u1s-item');
  assert.deepEqual(items.map((i) => buscar(i, '.u1s-item__id').textContent), ['M-02', 'M-01'], 'primero lo que falla');
  assert.match(items[0].textContent, /Rojo/);
  assert.match(items[0].textContent, /cuenta deshabilitada/);
  assert.ok(buscar(items[0], '.chip svg'), 'el estado lleva icono además de la etiqueta');
  assert.match(items[1].textContent, /120 ms/);
  assert.match(raiz.textContent, /2 de 4 ítems en verde · 1 crítico en rojo/);
  assert.match(raiz.textContent, /Rojo/);
  assert.match(buscar(raiz, '.u1s-veredicto').textContent, /cuentas y servicios están en rojo/);
});

test('Sistema: infra sin `items` (servidor antiguo) no inventa ítems y lo explica', async () => {
  const raiz = await pagina.render(ctxDe(crearApiFalsa()));
  assert.equal(buscarTodos(raiz, '.u1s-item').length, 0);
  assert.match(raiz.textContent, /recibe solo el resultado general/);
});

test('Sistema: con PAUSA activa muestra motivo e instrucción de levantarla a mano, sin botón de pausar ni de borrar', async () => {
  const s = { ...sis, datos: { ...sis.datos, pausa: { activa: true, desde: '2026-11-06T10:00:00Z', motivo: 'revisar gasto' }, freno_captura: null } };
  const raiz = await pagina.render(ctxDe(crearApiFalsa({ '/sistema': s })));
  assert.match(raiz.textContent, /revisar gasto/);
  assert.match(raiz.textContent, /Cómo levantar la PAUSA/);
  assert.equal(buscar(raiz, '.u1s-veredicto').getAttribute('data-tono'), 'error');
  assert.match(buscar(raiz, '.u1s-veredicto').textContent, /en pausa/);
  assert.ok(buscarTodos(raiz, '.comando__texto').some((c) => c.textContent === 'rm empresa/PAUSA'));
  assert.equal(textoBotones(raiz).some((t) => /Pausar todo/.test(t)), false);
  for (const t of textoBotones(raiz)) assert.doesNotMatch(t, /borrar|eliminar|levantar|quitar|reanudar/i);
  assert.match(raiz.textContent, /Libre/, 'freno libre cuando no hay archivo');
  assert.match(raiz.textContent, /ACTIVA/);
  assert.match(raiz.textContent, /No hay botón de borrado a propósito/);
});

test('Sistema sin preflight: estado vacío con pasos y el comando exacto', async () => {
  const s = { ...sis, datos: { ...sis.datos, infra: null } };
  const raiz = await pagina.render(ctxDe(crearApiFalsa({ '/sistema': s })));
  assert.match(raiz.textContent, /Todavía no se hizo el chequeo de cuentas y servicios/);
  assert.ok(buscar(raiz, '.vacio-pasos'));
  assert.ok(buscarTodos(raiz, '.comando__texto').some((c) => c.textContent.startsWith('.venv/bin/python -m infra.preflight ejecutar')));
  assert.match(raiz.textContent, /Sin medir/);
});

test('Sistema: /sistema caído → errorBox; /acciones caído o vacío → mensaje claro y el resto sigue', async () => {
  const caido = new ErrorApiFalso('sin_conexion', 'No hay conexión');
  const r1 = await pagina.render(ctxDe(crearApiFalsa({ '/sistema': caido })));
  assert.ok(buscarTodos(r1, '[role="alert"]').length >= 1);
  assert.match(r1.textContent, /Tareas que puedes ejecutar desde aquí/);
  const r2 = await pagina.render(ctxDe(crearApiFalsa({ '/acciones': caido })));
  assert.match(r2.textContent, /sin_conexion/);
  assert.match(r2.textContent, /Salud/);
  const r3 = await pagina.render(ctxDe(crearApiFalsa({ '/acciones': { ok: true, datos: [], fuente: ['dashboard/acciones.yaml'], vacio: true } })));
  assert.match(r3.textContent, /La lista de tareas todavía no está disponible/);
  assert.ok(buscar(r3, '.vacio-pasos'));
});

test('Consola: lista blanca, formulario validado, POST /accion con args tipados y salida en vivo por /job', async () => {
  let llamadasJob = 0;
  const api = crearApiFalsa({
    'POST /accion': { job_id: 'job-1', accion: 'validar_oferta', comando: 'python -m scripts.validar_esquemas oferta ofertas/_ejemplo' },
    '/job': (params) => {
      llamadasJob += 1;
      if (llamadasJob === 1) return { datos: { estado: 'corriendo', terminado: false, salida: '$ validar\n', siguiente: 10 } };
      return { datos: { estado: 'ok', terminado: true, codigo: 0, salida: 'ok  landing\n\u001b[32mlisto\u001b[0m\n', siguiente: 28 } };
    },
  });
  const ctx = ctxDe(api);
  const raiz = await pagina.render(ctx);
  const items = buscarTodos(raiz, '.u1s-accion');
  assert.equal(items.length, 8);
  assert.match(items.find((i) => i.textContent.includes('Probar la creación de la página de venta')).textContent, /próximamente/);
  assert.match(items.map((i) => i.textContent).join('|'), /Solo mira/);
  assert.match(items.find((i) => i.textContent.includes('Guardar un resumen en tu computadora')).textContent, /Guarda archivos aquí/);
  assert.deepEqual(buscarTodos(raiz, '.u1s-grupo h3').map((h) => h.textContent), ['Buscar ofertas en el mercado', 'Revisar que los formatos estén bien', 'Comprobar que el sistema funciona', 'Otras tareas', 'Página de venta']);
  // elegir «Landing: validar» → select de ofertas conocidas
  items.find((i) => i.textContent.includes('Revisar una oferta completa')).click();
  assert.equal(items.find((i) => i.textContent.includes('Revisar una oferta completa')).getAttribute('aria-pressed'), 'true');
  assert.ok(buscarTodos(raiz, '.comando__texto').some((c) => c.textContent === 'python -m scripts.validar_esquemas oferta ofertas/<oferta>'), 'muestra el comando que se ejecuta');
  assert.match(buscar(raiz, '.u1s-panel').textContent, /Qué se ejecuta por dentro/);
  const form = buscar(raiz, 'form');
  const select = buscar(form, 'select');
  assert.ok(buscarTodos(select, 'option').length >= 5);
  // sin valor → no llama a la API y marca el campo
  form.disparar('submit');
  await dormir(5);
  assert.equal(api.postsA('/accion').length, 0);
  assert.match(form.textContent, /Obligatorio/);
  // valor válido → POST con argumentos tipados y NADA más
  select.value = '_ejemplo'; select.disparar('change');
  form.disparar('submit');
  await dormir(5);
  assert.deepEqual(api.postsA('/accion').map((p) => p.cuerpo), [{ id: 'validar_oferta', args: { oferta: '_ejemplo' } }]);
  assert.match(buscar(raiz, 'button[type="submit"]').textContent, /Ejecutando/);
  assert.equal(buscar(raiz, 'button[type="submit"]').disabled, true, 'un job a la vez por acción');
  await dormir(1500);
  const salida = buscar(raiz, '.u1s-term__salida').textContent;
  assert.match(salida, /^\$ python -m scripts\.validar_esquemas oferta ofertas\/_ejemplo\n/, 'la salida abre con el comando real');
  assert.match(salida, /\$ validar/);
  assert.match(salida, /ok {2}landing\nlisto\n/, 'la salida llega completa y sin códigos ANSI');
  assert.doesNotMatch(salida, /\u001b/);
  assert.match(raiz.textContent, /Terminó bien/);
  assert.equal(buscar(raiz, '.u1s-term__estado').getAttribute('data-clave'), 'ok', 'el estado del job lleva icono y color');
  assert.ok(buscar(buscar(raiz, '.u1s-term__estado'), 'svg'));
  assert.match(buscar(raiz, '.u1s-term__job').textContent, /Tarea job-1/);
  assert.deepEqual(api.llamadas.filter((l) => l.ruta.startsWith('/job/')).map((l) => l.params.desde), [0, 10], 'pide la salida incremental con `desde`');
  assert.equal(llamadasJob, 2);
  ctx._salir();
});

test('Consola: los args hostiles nunca salen; las acciones que escriben en local piden confirmación', async () => {
  const api = crearApiFalsa({ 'POST /accion': { job_id: 'job-2', comando: 'python -m x' }, '/job': { datos: { estado: 'ok', terminado: true, codigo: 0, salida: 'x', siguiente: 1 } } });
  const ctx = ctxDe(api, { estado: { ofertas: [], conectado: 'sse' } }); // sin ofertas conocidas: campo de texto libre validado
  const raiz = await pagina.render(ctx);
  // 1) argumento hostil → bloqueado en el cliente
  buscarTodos(raiz, '.u1s-accion').find((i) => i.textContent.includes('Revisar una oferta completa')).click();
  const form = buscar(raiz, 'form');
  const input = buscar(form, 'input');
  input.value = 'OF-202611-01; rm -rf /'; input.disparar('input');
  form.disparar('submit');
  await dormir(5);
  assert.equal(api.postsA('/accion').length, 0, 'el valor hostil no pasa la validación');
  assert.match(form.textContent, /Escribe el código de la oferta/);
  // 2) acción que escribe en local → confirmación antes del POST
  buscarTodos(raiz, '.u1s-accion').find((i) => i.textContent.includes('Guardar un resumen en tu computadora')).click();
  buscar(raiz, 'form').disparar('submit');
  await dormir(5);
  assert.equal(api.postsA('/accion').length, 0, 'todavía falta confirmar');
  const dlg = buscarTodos(globalThis.document.body, '.modal');
  assert.equal(dlg.length >= 1, true);
  assert.match(dlg.at(-1).textContent, /guarda archivos en este equipo/i);
  buscarTodos(dlg.at(-1), '.modal__pie button').find((b) => b.textContent === 'Ejecutar').click();
  await dormir(20);
  assert.deepEqual(api.postsA('/accion').map((p) => p.cuerpo), [{ id: 'exportar_local', args: {} }]);
  await dormir(450);
  ctx._salir();
});

test('Consola: una acción «próximamente» se explica y no se puede ejecutar', async () => {
  const api = crearApiFalsa();
  const ctx = ctxDe(api);
  const raiz = await pagina.render(ctx);
  buscarTodos(raiz, '.u1s-accion').find((i) => i.textContent.includes('Probar la creación de la página de venta')).click();
  assert.match(raiz.textContent, /Esta tarea aún no está disponible/);
  assert.match(raiz.textContent, /aún no tiene modo simulacro/);
  assert.equal(buscar(raiz, 'button[type="submit"]').disabled, true);
  buscar(raiz, 'form').disparar('submit');
  await dormir(5);
  assert.equal(api.postsA('/accion').length, 0);
  ctx._salir();
});

test('Consola: parámetros de bandera, entero con rango y corrida se renderizan y viajan tipados', async () => {
  const api = crearApiFalsa({ 'POST /accion': { job_id: 'job-5', comando: 'python -m scripts.modelado.barrido plan ver 2026-11-06-a --consultas' }, '/job': { datos: { estado: 'ok', terminado: true, codigo: 0, salida: 'plan', siguiente: 4 } } });
  const ctx = ctxDe(api);
  const raiz = await pagina.render(ctx);
  buscarTodos(raiz, '.u1s-accion').find((i) => i.textContent.includes('Ver el plan de una búsqueda')).click();
  const form = buscar(raiz, 'form');
  const [corrida, bandera] = buscarTodos(form, 'input');
  assert.equal(bandera.getAttribute('type'), 'checkbox');
  assert.match(form.textContent, /Mostrar también el detalle de cada consulta/);
  assert.match(form.textContent, /\(--consultas\)/);
  corrida.value = '2026-11-06-a'; corrida.disparar('input');
  bandera.checked = true; bandera.disparar('change');
  form.disparar('submit');
  await dormir(10);
  assert.deepEqual(api.postsA('/accion')[0].cuerpo, { id: 'barrido_plan_ver', args: { corrida: '2026-11-06-a', consultas: true } });
  await dormir(1000);
  buscarTodos(raiz, '.u1s-accion').find((i) => i.textContent.includes('Ver las primeras filas de un barrido')).click();
  const f2 = buscar(raiz, 'form');
  const num = buscarTodos(f2, 'input').find((i) => i.getAttribute('type') === 'number');
  assert.equal(num.getAttribute('min'), '1');
  assert.equal(num.getAttribute('max'), '50');
  ctx._salir();
});

test('Consola: si ya hay un job de esa acción corriendo en el servidor (en_curso), lo sigue en vez de ofrecer otro', async () => {
  const sobre = cargarSobre('acciones');
  sobre.datos.acciones.find((a) => a.id === 'validar_esquemas').en_curso = 'job-viejo';
  let pedidos = 0;
  const api = crearApiFalsa({ '/acciones': sobre, '/job': () => { pedidos += 1; return { datos: { estado: 'ok', terminado: true, codigo: 0, salida: 'listo\n', siguiente: 6 } }; } });
  const ctx = ctxDe(api);
  const raiz = await pagina.render(ctx);
  await dormir(450);
  assert.ok(pedidos >= 1);
  assert.equal(api.llamadas.find((l) => l.ruta.startsWith('/job/')).ruta, '/job/job-viejo');
  assert.match(buscar(raiz, '.u1s-term__salida').textContent, /listo/);
  ctx._salir();
});

test('Consola: si el servidor rechaza la acción, avisa y no queda un job colgado', async () => {
  const api = crearApiFalsa({ 'POST /accion': new ErrorApiFalso('accion_ocupada', 'Esa acción ya está corriendo.') });
  const ctx = ctxDe(api);
  const raiz = await pagina.render(ctx);
  buscarTodos(raiz, '.u1s-accion').find((i) => i.textContent.includes('Revisar que los formatos estén bien')).click();
  buscar(raiz, 'form').disparar('submit');
  await dormir(10);
  assert.equal(api.postsA('/accion').length, 1);
  assert.match(buscar(globalThis.document.body, '.toasts').textContent, /accion_ocupada|ya está corriendo/);
  assert.equal(buscar(raiz, 'button[type="submit"]').disabled, false);
  ctx._salir();
});

test('Sistema.alCambio repinta solo el estado: la consola (formulario y salida) no se pierde', async () => {
  const ctx = ctxDe(crearApiFalsa());
  const raiz = await pagina.render(ctx);
  const consola = buscar(raiz, '.u1s-consola');
  const salida = buscar(raiz, '.u1s-term__salida');
  assert.ok(consola && salida);
  const s = { ...sis, datos: { ...sis.datos, pausa: { activa: true, desde: '2026-11-06T13:00:00Z', motivo: 'cambio en vivo' } } };
  ctx.api = crearApiFalsa({ '/sistema': s });
  await pagina.alCambio(ctx, { tipo: 'empresa' });
  assert.match(raiz.textContent, /cambio en vivo/);
  assert.equal(buscar(raiz, '.u1s-consola'), consola, 'la consola es el mismo nodo');
  assert.equal(buscar(raiz, '.u1s-term__salida'), salida);
  await pagina.alCambio({}, {}); // sin render previo: no lanza
  ctx._salir();
});

test('Sistema: meta de página', () => {
  assert.deepEqual([pagina.meta.ruta, pagina.meta.grupo, pagina.meta.titulo], ['sistema', 'Robots', 'Salud del sistema']);
});
