// Pruebas de la lógica pura de #/oferta/<id> (dashboard/web/lib/oferta.js). Sin DOM, sin red.
// Ejecutar: node --test tests/dashboard/test_web_oferta.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import * as L from '../../dashboard/web/lib/oferta.js';

const AQUI = dirname(fileURLToPath(import.meta.url));
const FIX = join(AQUI, '..', 'fixtures', 'dashboard', 'oferta');
const leer = (n) => JSON.parse(readFileSync(join(FIX, n), 'utf8'));
const ejemplo = leer('oferta_ejemplo.json').datos;
const vacia = leer('oferta_vacia.json').datos;
const hostil = leer('oferta_hostil.json').datos;

test('orden del flujo: D1 antes de M1 (M1 depende de D1) y D9 opcional', () => {
  assert.deepEqual(L.ORDEN_ETAPAS, ['D1', 'M1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10']);
  assert.deepEqual(L.ETAPAS.M1.dependeDe, ['D1']);
  assert.equal(L.ETAPAS.D9.opcional, true);
  // toda dependencia aparece antes en el orden
  for (const id of L.ORDEN_ETAPAS) {
    for (const d of L.ETAPAS[id].dependeDe) assert.ok(L.posicionEtapa(d) < L.posicionEtapa(id), `${d} antes de ${id}`);
  }
});

test('compararEtapas ordena por flujo y deja las desconocidas al final', () => {
  const lista = ['D10', 'XX', 'M1', 'D2', 'D1', 'AA'].sort(L.compararEtapas);
  assert.deepEqual(lista, ['D1', 'M1', 'D2', 'D10', 'AA', 'XX']);
});

test('construirPipeline: ordena aunque la API venga desordenada y rellena lo que falta como «sin datos»', () => {
  const api = [{ id: 'D3', estado: 'aprobado' }, { id: 'D1', estado: 'aprobado' }];
  const p = L.construirPipeline(api);
  assert.equal(p.length, 11);
  assert.deepEqual(p.map((x) => x.id), L.ORDEN_ETAPAS);
  assert.equal(p[0].sinDatos, false);
  assert.equal(p[1].sinDatos, true); // M1 no vino
  assert.equal(p[1].rotulo, 'sin datos');
  assert.equal(p[1].estado, 'pendiente');
});

test('construirPipeline con el ejemplo: estados, gate, versión y gate pendiente en D7', () => {
  const p = L.construirPipeline(ejemplo.etapas);
  const por = Object.fromEntries(p.map((x) => [x.id, x]));
  assert.equal(por.D1.estado, 'aprobado');
  assert.equal(por.D1.version, 'v1');
  assert.equal(por.D1.gate, 'H');
  assert.equal(por.D2.gate, 'S');
  assert.equal(por.D7.estado, 'en_QA');
  assert.equal(por.D7.gatePendiente, true);
  assert.equal(por.D8.gate, 'A');
  assert.equal(por.D8.estado, 'pendiente');
  assert.equal(por.D9.opcional, true);
  assert.equal(por.D3.aprobadoPor.tipo, 'humano');
  assert.equal(por.D2.aprobadoPor.tipo, 'qa_pass');
  assert.ok(por.D3.artefactos.length > 0);
  assert.ok(por.D3.qa.length > 0);
});

test('construirPipeline ignora elementos corruptos de la API sin lanzar', () => {
  const p = L.construirPipeline([null, 5, 'x', { id: 7 }, { id: 'D1', estado: 'inventado', gate: 'Z', ronda_qa: 'dos', artefactos: 'no', qa: null }]);
  assert.equal(p.length, 11);
  assert.equal(p[0].estado, 'pendiente'); // estado inválido -> pendiente
  assert.equal(p[0].gate, null);
  assert.equal(p[0].rondaQa, null);
  assert.deepEqual(p[0].artefactos, []);
  assert.deepEqual(p[0].qa, []);
  assert.equal(L.construirPipeline(undefined).length, 11);
  assert.equal(L.construirPipeline({}).length, 11);
});

test('etapa obsoleta: tono aviso y rótulo «obsoleta»', () => {
  const v = L.vistaEtapa('D3', { id: 'D3', estado: 'pendiente', obsoleta: true, version_aprobada: 'v1' });
  assert.equal(v.obsoleta, true);
  assert.equal(v.tono, 'aviso');
  assert.equal(v.rotulo, 'obsoleta');
});

test('bloqueo: texto, objeto, null y vacío', () => {
  assert.equal(L.textoBloqueo(null), null);
  assert.equal(L.textoBloqueo(''), null);
  assert.equal(L.textoBloqueo('falta clave'), 'falta clave');
  assert.equal(L.textoBloqueo({ motivo: 'falta clave', tipo: 'credencial' }), 'credencial: falta clave');
  assert.equal(L.textoBloqueo({ motivo: 'x' }), 'x');
  assert.equal(L.textoBloqueo({ otro: 1 }), '{"otro":1}');
});

test('resumenPipeline del ejemplo: 7 de 10 aprobadas, D9 no cuenta, gate en D7, etapa actual D7', () => {
  const p = L.construirPipeline(ejemplo.etapas);
  const r = L.resumenPipeline(p);
  assert.equal(r.total, 10); // D9 pendiente (fuera de alcance) no cuenta
  assert.equal(r.aprobadas, 7);
  assert.equal(r.enCurso, 1);
  assert.equal(r.pendientes, 2); // D8 y D10
  assert.equal(r.bloqueadas, 0);
  assert.deepEqual(r.gatesPendientes, ['D7']);
  assert.equal(r.etapaActual, 'D7');
  assert.equal(r.bp, 7000);
  assert.equal(r.completa, false);
  assert.equal(r.sinDatos, false);
});

test('resumenPipeline: todo aprobado = completa; bloqueos y obsoletas se cuentan', () => {
  const todas = L.ORDEN_ETAPAS.map((id) => ({ id, estado: 'aprobado' }));
  const r = L.resumenPipeline(L.construirPipeline(todas));
  assert.equal(r.completa, true);
  assert.equal(r.bp, 10000);
  assert.equal(r.etapaActual, null);
  const mezcla = L.construirPipeline([
    { id: 'D1', estado: 'aprobado' }, { id: 'M1', estado: 'bloqueado', bloqueo: 'x' }, { id: 'D2', estado: 'escalado' },
    { id: 'D3', estado: 'pendiente', obsoleta: true },
  ]);
  const m = L.resumenPipeline(mezcla);
  assert.equal(m.bloqueadas, 2);
  assert.equal(m.obsoletas, 1);
  assert.equal(m.etapaActual, 'M1');
  assert.equal(m.completa, false);
});

test('resumenPipeline con oferta sin etapas: sinDatos, 0 %, sin inventar progreso', () => {
  const p = L.construirPipeline(vacia.etapas);
  const r = L.resumenPipeline(p);
  assert.equal(r.sinDatos, true);
  assert.equal(r.aprobadas, 0);
  assert.equal(r.bp, 0);
  assert.equal(r.completa, false);
  assert.ok(p.every((x) => x.sinDatos));
});

test('pipelineDesdeMapa: acepta el mapa de GET /ofertas y estados no válidos como «sin datos»', () => {
  const p = L.pipelineDesdeMapa({ D1: 'aprobado', M1: 'en_QA', D2: 'raro', D3: null, XX: 'pendiente' });
  assert.equal(p.length, 12); // 11 + XX
  assert.equal(p[0].tono, 'ok');
  assert.equal(p[1].tono, 'info');
  assert.equal(p[2].sinDatos, true);
  assert.equal(p[3].sinDatos, true);
  assert.equal(p[11].id, 'XX');
  assert.equal(L.pipelineDesdeMapa(null).length, 11);
});

test('citar: argumentos de shell seguros para comandos copiables', () => {
  assert.equal(L.citar('OF-202611-01'), 'OF-202611-01');
  assert.equal(L.citar("OF-1'; rm -rf / #"), "'OF-1'\\''; rm -rf / #'");
  assert.equal(L.citar(''), "''");
  assert.equal(L.citar('a b'), "'a b'");
  assert.equal(L.citar('$(id)'), "'$(id)'");
  assert.equal(L.citar('`id`'), "'`id`'");
});

test('comandoFirmar usa el CLI documentado y no firma por sí mismo', () => {
  assert.equal(L.comandoFirmar('OF-202611-01', 'D7'), '.venv/bin/python -m engine.orq firmar --oferta OF-202611-01 --etapa D7 --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno');
});

test('comandosEtapa: lectura, ensayo, ingresar y real; «firmar» solo con gate pendiente y va primero', () => {
  const p = L.construirPipeline(ejemplo.etapas);
  const d7 = p.find((x) => x.id === 'D7');
  const lista = L.comandosEtapa('OF-202611-01', 'D7', d7);
  assert.equal(lista[0].id, 'firmar');
  assert.equal(lista[0].riesgo, 'firma');
  assert.match(lista[0].comando, /orq firmar --oferta OF-202611-01 --etapa D7 --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno$/);
  const ids = lista.map((c) => c.id);
  for (const id of ['estado', 'siguiente', 'ensayo', 'ingresar', 'real']) assert.ok(ids.includes(id), id);
  const ensayo = lista.find((c) => c.id === 'ensayo');
  assert.match(ensayo.comando, /--modo dry-run$/);
  assert.equal(ensayo.riesgo, 'lectura');
  const d3 = p.find((x) => x.id === 'D3');
  assert.ok(!L.comandosEtapa('OF-202611-01', 'D3', d3).some((c) => c.id === 'firmar'));
  // etapas de ingeniería: sin comando «real»
  assert.ok(!L.comandosEtapa('OF-202611-01', 'D8', null).some((c) => c.id === 'real'));
  // D9 opcional: solo lectura
  assert.deepEqual(L.comandosEtapa('OF-202611-01', 'D9').map((c) => c.id), ['estado', 'siguiente']);
});

test('comandosEtapa cita ids hostiles (sin inyección de shell)', () => {
  const lista = L.comandosEtapa("OF-1'; rm -rf / #", 'D3', null);
  for (const c of lista) assert.ok(!/ rm -rf \/ #(?!')/.test(c.comando.replace(/'[^']*'/g, '')), c.comando);
  assert.match(lista[0].comando, /--oferta 'OF-1'\\''; rm -rf \/ #'/);
});

test('proximoPaso: prefiere lo que dice el servidor, y deduce el resto del pipeline', () => {
  const p = L.construirPipeline(ejemplo.etapas);
  const r = L.resumenPipeline(p);
  const conApi = L.proximoPaso('OF-202611-01', p, r, ejemplo.proximo_paso);
  assert.equal(conApi.origen, 'servidor');
  assert.equal(conApi.titulo, 'D7 (Campañas Meta) espera tu firma (gate H).');
  assert.equal(conApi.etapa, 'D7');
  // el comando del servidor («python -m …») se normaliza al intérprete del proyecto
  assert.equal(conApi.comando, '.venv/bin/python -m engine.orq firmar --oferta OF-202611-01 --etapa D7 --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno');
  assert.equal(conApi.motorDisponible, false); // engine/orq.py aún no existe: la pantalla avisa que los comandos son «por contrato»
  const local = L.proximoPaso('OF-202611-01', p, r, null);
  assert.equal(local.origen, 'calculado');
  assert.equal(local.etapa, 'D7');
  assert.equal(local.tono, 'aviso');
  assert.match(local.titulo, /Firmar D7 Campaña/);
});

test('proximoPaso con objeto del servidor y con basura', () => {
  const p = L.construirPipeline(ejemplo.etapas);
  const r = L.resumenPipeline(p);
  const o = L.proximoPaso('OF-202611-01', p, r, { titulo: 'Hacer X', etapa: 'D8', comando: 'echo hola', detalle: 'porque sí' });
  assert.equal(o.titulo, 'Hacer X');
  assert.equal(o.etapa, 'D8');
  assert.equal(o.comando, 'echo hola');
  assert.equal(L.proximoPaso('OF-202611-01', p, r, 42).origen, 'calculado');
  assert.equal(L.proximoPaso('OF-202611-01', p, r, '   ').origen, 'calculado');
  assert.equal(L.proximoPaso('OF-202611-01', p, r, {}).origen, 'calculado');
});

test('proximoPasoLocal: cada estado de la máquina de estados tiene un próximo paso', () => {
  const caso = (etapas) => {
    const p = L.construirPipeline(etapas);
    return L.proximoPasoLocal('OF-1', p, L.resumenPipeline(p));
  };
  assert.match(caso([]).titulo, /aún no tiene estado/);
  assert.match(caso([]).comando, /orq crear --brief/);
  assert.match(caso([{ id: 'D1', estado: 'pendiente' }]).titulo, /Ejecutar D1 Descubrimiento/);
  assert.match(caso([{ id: 'D1', estado: 'en_progreso' }]).titulo, /en progreso/);
  assert.match(caso([{ id: 'D1', estado: 'en_QA', ronda_qa: 2 }]).detalle, /Ronda de revisión 2/);
  assert.match(caso([{ id: 'D1', estado: 'en_QA', gate: 'H', gate_pendiente: true }]).titulo, /Firmar D1 Descubrimiento/);
  const b = caso([{ id: 'D1', estado: 'bloqueado', bloqueo: 'falta API' }]);
  assert.equal(b.tono, 'error');
  assert.equal(b.detalle, 'falta API');
  assert.equal(caso([{ id: 'D1', estado: 'escalado' }]).tono, 'error');
  assert.match(caso([{ id: 'D1', estado: 'pendiente', obsoleta: true }]).titulo, /Rehacer D1/);
  const todas = L.ORDEN_ETAPAS.map((id) => ({ id, estado: 'aprobado' }));
  assert.equal(caso(todas).tono, 'ok');
});

test('entradas y salidas de etapa', () => {
  const e = L.entradasDeEtapa('D5', ejemplo.estado);
  assert.deepEqual(e.map((x) => x.etapa), ['D3', 'D4']);
  assert.match(e[0].hash, /^sha256:/);
  assert.deepEqual(L.entradasDeEtapa('D1', ejemplo.estado), []);
  assert.deepEqual(L.entradasDeEtapa('D5', null).map((x) => x.hash), [null, null]);
  assert.ok(L.salidasDeEtapa('D3').includes('03-oferta/oferta.json'));
  assert.deepEqual(L.salidasDeEtapa('ZZ'), []);
  // modificar el resultado no altera la tabla
  L.salidasDeEtapa('D3').push('x');
  assert.ok(!L.salidasDeEtapa('D3').includes('x'));
});

test('tipoVisor: confía en el servidor y deduce por extensión', () => {
  assert.equal(L.tipoVisor({ ruta: 'a/b.json', tipo: 'json' }), 'json');
  assert.equal(L.tipoVisor({ ruta: 'a/b.md' }), 'md');
  assert.equal(L.tipoVisor({ ruta: 'a/b.YAML' }), 'yaml');
  assert.equal(L.tipoVisor({ ruta: 'a/b.htm' }), 'html');
  assert.equal(L.tipoVisor({ ruta: 'a/b.PNG' }), 'imagen');
  assert.equal(L.tipoVisor({ ruta: 'a/b.jsonl' }), 'texto');
  assert.equal(L.tipoVisor({ ruta: 'a/sin_extension' }), 'texto');
  assert.equal(L.tipoVisor({ ruta: 'a/b.json', tipo: 'raro' }), 'json');
  assert.equal(L.tipoVisor(null), 'texto');
  assert.equal(L.extension('.oculto'), '');
});

test('versiones vN: detección y clave de agrupación', () => {
  assert.equal(L.versionDeRuta('03-oferta/v2/oferta.json'), 2);
  assert.equal(L.versionDeRuta('04-producto/entregables/puente-de-la-pausa-v1-guia.md'), 1);
  assert.equal(L.versionDeRuta('06-creativos/assets/c01-hueco_img_h1_v3.png'), 3);
  assert.equal(L.versionDeRuta('qa/d3-v12.json'), 12);
  assert.equal(L.versionDeRuta('03-oferta/oferta.json'), null);
  assert.equal(L.versionDeRuta('03-oferta/valores.json'), null); // «v» dentro de una palabra no es versión
  assert.equal(L.versionDeRuta('x/v0/a.json'), null); // v0 no es versión válida
  assert.equal(L.claveSinVersion('x/guia-v2.md'), 'x/guia-v*.md');
  assert.equal(L.claveSinVersion('x/v10/a.json'), 'x/v*/a.json');
});

test('gruposDeVersiones: solo grupos con ≥ 2 versiones, ordenados', () => {
  const arts = [
    { ruta: '04-producto/entregables/guia-v2.md', bytes: 20 },
    { ruta: '04-producto/entregables/guia-v1.md', bytes: 10 },
    { ruta: '04-producto/entregables/guia-v10.md', bytes: 30 },
    { ruta: '04-producto/entregables/plantilla-v1.md', bytes: 5 },
    { ruta: '04-producto/producto.json', bytes: 5 },
    { ruta: 7 },
    null,
  ];
  const g = L.gruposDeVersiones(arts);
  assert.equal(g.length, 1);
  assert.equal(g[0].clave, '04-producto/entregables/guia-v*.md');
  assert.deepEqual(g[0].versiones.map((v) => v.n), [1, 2, 10]);
  assert.deepEqual(L.gruposDeVersiones([]), []);
  assert.deepEqual(L.gruposDeVersiones(undefined), []);
});

test('gruposDeVersiones con el ejemplo real: ninguna etapa tiene dos versiones todavía', () => {
  const todos = ejemplo.etapas.flatMap((e) => e.artefactos);
  assert.ok(todos.length > 20);
  assert.deepEqual(L.gruposDeVersiones(todos), []);
});

test('agruparPorCarpeta agrupa y ordena', () => {
  const g = L.agruparPorCarpeta([{ ruta: 'b/z.json' }, { ruta: 'a/y.md' }, { ruta: 'a/x.md' }, { ruta: 'raiz.json' }]);
  assert.deepEqual(g.map((x) => x.carpeta), ['.', 'a', 'b']);
  assert.deepEqual(g[1].items.map((i) => i.ruta), ['a/x.md', 'a/y.md']);
});

test('diferenciaLineas: iguales, cambios, altas y bajas con números de línea', () => {
  const d = L.diferenciaLineas('uno\ndos\ntres\ncuatro', 'uno\nDOS\ntres\ncuatro\ncinco');
  assert.equal(d.truncado, false);
  const tipos = d.lineas.map((l) => l.tipo);
  assert.deepEqual(tipos, ['igual', 'menos', 'mas', 'igual', 'igual', 'mas']);
  assert.deepEqual(L.resumenDiff(d.lineas), { mas: 2, menos: 1, igual: false });
  const menos = d.lineas.find((l) => l.tipo === 'menos');
  assert.equal(menos.texto, 'dos');
  assert.equal(menos.a, 2);
  assert.equal(menos.b, null);
  const ultima = d.lineas[d.lineas.length - 1];
  assert.equal(ultima.texto, 'cinco');
  assert.equal(ultima.b, 5);
});

test('diferenciaLineas: textos idénticos, vacíos y CRLF', () => {
  assert.equal(L.resumenDiff(L.diferenciaLineas('a\nb', 'a\nb').lineas).igual, true);
  assert.equal(L.resumenDiff(L.diferenciaLineas('a\r\nb', 'a\nb').lineas).igual, true);
  const d = L.diferenciaLineas('', 'x');
  assert.deepEqual(d.lineas.map((l) => l.tipo), ['menos', 'mas']); // '' es una línea vacía frente a 'x'
  assert.equal(L.diferenciaLineas(null, undefined).truncado, false);
});

test('diferenciaLineas: mover un bloque y reordenar no pierde líneas', () => {
  const a = 'a\nb\nc\nd\ne';
  const b = 'a\nd\nb\nc\ne';
  const d = L.diferenciaLineas(a, b).lineas;
  const sinMas = d.filter((l) => l.tipo !== 'mas').map((l) => l.texto).join('\n');
  const sinMenos = d.filter((l) => l.tipo !== 'menos').map((l) => l.texto).join('\n');
  assert.equal(sinMas, a);
  assert.equal(sinMenos, b);
});

test('diferenciaLineas: reconstruye ambos textos en un caso grande y respeta el tope', () => {
  const A = Array.from({ length: 800 }, (_, i) => `linea ${i}`);
  const B = A.slice();
  B[100] = 'cambiada'; B.splice(300, 5); B.splice(500, 0, 'nueva 1', 'nueva 2');
  const d = L.diferenciaLineas(A.join('\n'), B.join('\n'));
  assert.equal(d.lineas.filter((l) => l.tipo !== 'mas').map((l) => l.texto).join('\n'), A.join('\n'));
  assert.equal(d.lineas.filter((l) => l.tipo !== 'menos').map((l) => l.texto).join('\n'), B.join('\n'));
  const enorme = Array.from({ length: L.TOPE_LINEAS_DIFF + 1 }, (_, i) => String(i)).join('\n');
  const t = L.diferenciaLineas(enorme, 'x');
  assert.equal(t.truncado, true);
  assert.deepEqual(t.lineas, []);
});

test('contextoDiff: colapsa lo igual lejos de los cambios y cuenta lo omitido', () => {
  const A = Array.from({ length: 30 }, (_, i) => `l${i}`);
  const B = A.slice(); B[15] = 'X';
  const d = L.diferenciaLineas(A.join('\n'), B.join('\n')).lineas;
  const c = L.contextoDiff(d, 2);
  assert.equal(c[0].tipo, 'salto');
  assert.equal(c[0].n, 13); // líneas 0..12 omitidas
  const visibles = c.filter((l) => l.tipo !== 'salto');
  assert.equal(visibles.length, 6); // 2 antes + menos + más + 2 después
  assert.equal(visibles.filter((l) => l.tipo === 'menos').length, 1);
  assert.deepEqual(c[c.length - 1], { tipo: 'salto', n: 12 });
  assert.deepEqual(L.contextoDiff([], 3), []);
  // sin cambios: todo se colapsa en un solo salto
  const igual = L.contextoDiff(L.diferenciaLineas('a\nb\nc', 'a\nb\nc').lineas, 1);
  assert.deepEqual(igual, [{ tipo: 'salto', n: 3 }]);
});

test('QA: tono de veredicto, ruta del informe y resumen en texto u objeto', () => {
  assert.equal(L.tonoVeredicto('PASS'), 'ok');
  assert.equal(L.tonoVeredicto('PASS_CON_NOTAS'), 'aviso');
  assert.equal(L.tonoVeredicto('FAIL'), 'error');
  assert.equal(L.tonoVeredicto('ESCALAR'), 'error');
  assert.equal(L.tonoVeredicto('raro'), 'neutro');
  assert.equal(L.rutaInformeQa('d3-v1.json'), 'qa/d3-v1.json');
  assert.equal(L.rutaInformeQa('qa/d3-v1.json'), 'qa/d3-v1.json');
  assert.equal(L.rutaInformeQa('/qa/d3-v1.json'), 'qa/d3-v1.json');
  assert.equal(L.rutaInformeQa(''), '');
  assert.equal(L.textoResumenQa('todo bien'), 'todo bien');
  assert.equal(L.textoResumenQa(null), '');
  assert.equal(L.textoResumenQa({ puntaje_global: '4.40', umbral: '3.8', hallazgos: 3 }), 'nota 4.40 (mínimo 3.8) · 3 hallazgos');
  assert.equal(L.textoResumenQa({ a: 1, b: { c: 2 } }), 'a: 1 · b: {"c":2}');
});

test('vistaInformeQa con el informe real de D3: veredicto, ítems, checks y hallazgos por severidad', () => {
  const v = L.vistaInformeQa(leer('qa_d3_v1.json'));
  assert.equal(v.veredicto, 'PASS');
  assert.equal(v.tono, 'ok');
  assert.equal(v.ronda, 1);
  assert.equal(v.puntaje, '4.40');
  assert.equal(v.items.length, 5);
  assert.ok(v.checks.length >= 1);
  assert.equal(v.checksFallidos, 0);
  assert.deepEqual(Object.keys(v.conteo), ['BLOQUEANTE', 'MAYOR', 'MENOR', 'MEJORA']);
  assert.equal(v.hallazgos.length, Object.values(v.conteo).reduce((a, b) => a + b, 0) + v.otros.length);
});

test('vistaInformeQa: severidades, abiertos y tolerancia a basura', () => {
  const v = L.vistaInformeQa({
    veredicto: 'FAIL',
    hallazgos: [
      { severidad: 'BLOQUEANTE', estado: 'abierto', descripcion: 'a' },
      { severidad: 'MAYOR', estado: 'devuelto_al_maker', descripcion: 'b' },
      { severidad: 'MENOR', estado: 'corregido_por_qa', descripcion: 'c' },
      { severidad: 'RARA', estado: 'abierto', descripcion: 'd' },
      null,
      7,
    ],
    checks_l1: [{ resultado: 'fail' }, { resultado: 'pass' }],
    justificacion_sin_hallazgos: 5,
  });
  assert.deepEqual(v.conteo, { BLOQUEANTE: 1, MAYOR: 1, MENOR: 1, MEJORA: 0 });
  assert.equal(v.otros.length, 1);
  assert.equal(v.abiertos, 3);
  assert.equal(v.checksFallidos, 1);
  assert.equal(v.justificacion, null);
  const vacio = L.vistaInformeQa(null);
  assert.equal(vacio.veredicto, null);
  assert.equal(vacio.hallazgos.length, 0);
  assert.equal(L.vistaInformeQa([]).abiertos, 0);
});

test('línea de tiempo: más reciente primero, filtra por etapa y evento, tolera campos ausentes', () => {
  const lineas = L.lineasDeRegistro(leer('registro_oferta.json'));
  assert.ok(lineas.length >= 3);
  const t = L.lineaDeTiempo(lineas);
  for (let i = 1; i < t.length; i += 1) assert.ok((t[i - 1].ts || '') >= (t[i].ts || ''));
  assert.ok(t.every((e) => e.icono && e.tono));
  const d1 = L.lineaDeTiempo(lineas, { etapa: 'D1' });
  assert.ok(d1.length > 0 && d1.every((e) => e.etapa === 'D1'));
  const bloqueos = L.lineaDeTiempo(lineas, { evento: 'bloqueo' });
  assert.ok(bloqueos.length > 0);
  assert.equal(bloqueos[0].tono, 'error');
  assert.equal(L.lineaDeTiempo(lineas, { limite: 1 }).length, 1);
  const raro = L.lineaDeTiempo([{}, { ts: 'x' }, null, 5, { evento: 'inventado', resultado: 'no objeto' }]);
  assert.equal(raro.length, 3);
  assert.equal(raro[0].texto, '');
  assert.deepEqual(L.lineasDeRegistro(null), []);
  assert.deepEqual(L.lineasDeRegistro([{ a: 1 }]), [{ a: 1 }]);
  assert.deepEqual(L.lineaDeTiempo(undefined), []);
});

test('línea de tiempo: desempata por n y marca los resultados bloqueados en rojo', () => {
  const t = L.lineaDeTiempo([
    { n: 1, ts: '2026-11-06T10:00:00Z', evento: 'accion', resultado: { estado: 'ok' } },
    { n: 2, ts: '2026-11-06T10:00:00Z', evento: 'accion', resultado: { estado: 'bloqueado', codigo: 5 } },
  ]);
  assert.equal(t[0].n, 2);
  assert.equal(t[0].tono, 'error');
  assert.equal(t[0].codigo, 5);
  assert.equal(t[1].tono, 'neutro');
});

test('cabeceraOferta del ejemplo y de un estado vacío', () => {
  const c = L.cabeceraOferta(ejemplo.estado);
  assert.equal(c.ofertaId, 'OF-202611-01');
  assert.equal(c.fase, 'en_construccion');
  assert.equal(c.nivel, 'N2');
  assert.equal(c.pausa, false);
  assert.deepEqual(c.gastoAcumulado, { monto: 0, moneda: 'EUR' });
  assert.deepEqual(c.costoIa, { monto: 412, moneda: 'EUR' });
  assert.equal(c.candidato.candidato_id, 'CAND-01');
  assert.equal(c.skillsPin.D3, '0.1.0');
  const v = L.cabeceraOferta(null);
  assert.equal(v.ofertaId, null);
  assert.equal(v.gastoHoy, null);
  assert.deepEqual(v.skillsPin, {});
});

test('fases: rótulo y tono; desconocidas no revientan', () => {
  assert.equal(L.rotuloFase('en_construccion'), 'en construcción');
  assert.equal(L.rotuloFase('pausada'), 'pausada');
  assert.equal(L.rotuloFase(null), 'sin dato');
  assert.equal(L.rotuloFase('inventada'), 'inventada');
  assert.equal(L.tonoFase('validada'), 'ok');
  assert.equal(L.tonoFase('fallida'), 'error');
  assert.equal(L.tonoFase('x'), 'neutro');
  assert.equal(L.FASES.length, 10);
  assert.equal(L.gateTexto('H'), 'H · Humano');
  assert.equal(L.gateTexto(null), 'sin gate');
});

test('datos hostiles: el modelo de vista conserva el texto tal cual (el escape lo hace la capa de render)', () => {
  const p = L.construirPipeline(hostil.etapas);
  const m1 = p.find((x) => x.id === 'M1');
  assert.match(m1.bloqueo, /<img src=x onerror=alert\(1\)>/);
  assert.ok(m1.bloqueo.includes(String.fromCharCode(0x202e)));
  assert.equal(L.cabeceraOferta(hostil.estado).ofertaId, "OF-1'; rm -rf / #");
  const prox = L.proximoPaso(hostil.estado.oferta_id, p, L.resumenPipeline(p), hostil.proximo_paso);
  assert.equal(prox.titulo, '<script>alert(1)</script>');
  // el comando generado con el id hostil queda entrecomillado
  assert.match(L.comandoFirmar(hostil.estado.oferta_id, 'D1'), /--oferta 'OF-1'\\''; rm -rf \/ #' --etapa D1/);
});

test('sin estado.json el servidor manda las 11 etapas con estado null: todas «sin datos», aunque haya artefactos', () => {
  const p = L.construirPipeline(vacia.etapas);
  assert.equal(p.length, 11);
  assert.ok(p.every((x) => x.sinDatos && x.rotulo === 'sin datos' && x.tono === 'neutro' && x.gatePendiente === false));
  assert.equal(L.resumenPipeline(p).sinDatos, true);
  const conArtefactos = L.vistaEtapa('D3', { id: 'D3', estado: null, gate_pendiente: true, artefactos: [{ ruta: '03-oferta/oferta.json', tipo: 'json', bytes: 5, mtime: 'x' }], qa: [] });
  assert.equal(conArtefactos.sinDatos, true);
  assert.equal(conArtefactos.gatePendiente, false); // sin estado no hay gate que firmar
  assert.equal(conArtefactos.artefactos.length, 1); // pero los archivos que hay en disco sí se listan
  const prox = L.proximoPaso('OF-202611-02', p, L.resumenPipeline(p), vacia.proximo_paso);
  assert.match(prox.titulo, /Todavía no hay estado\.json/);
  assert.match(prox.comando, /^\.venv\/bin\/python -m engine\.orq crear --brief /);
});

test('el servidor puede mandar el próximo paso sin comando o con comando vacío', () => {
  const p = L.construirPipeline(ejemplo.etapas);
  const r = L.resumenPipeline(p);
  const a = L.proximoPaso('OF-1', p, r, { tipo: 'completa', etapa: null, texto: 'Todas aprobadas', comando: '   ' });
  assert.equal(a.titulo, 'Todas aprobadas');
  assert.match(a.comando, /orq firmar/); // cae al comando calculado
  assert.equal(L.proximoPaso('OF-1', p, r, { tipo: 'x', etapa: 'D2', texto: 'T', comando: 'python3 -m engine.orq estado --oferta OF-1' }).comando, '.venv/bin/python -m engine.orq estado --oferta OF-1');
});

test('próximo paso del servidor: su etapa y su tipo mandan (pausa = sin etapa y en rojo); el cálculo local no lo contradice', () => {
  const p = L.construirPipeline(ejemplo.etapas);
  const r = L.resumenPipeline(p);
  const pausa = L.proximoPaso('OF-1', p, r, { tipo: 'pausada', etapa: null, texto: 'La oferta está en pausa', comando: 'python -m engine.orq estado --oferta OF-1', motor_disponible: true });
  assert.equal(pausa.etapa, null);
  assert.equal(pausa.tono, 'error');
  assert.equal(pausa.motorDisponible, true);
  assert.equal(pausa.comando, '.venv/bin/python -m engine.orq estado --oferta OF-1');
  const otraEtapa = L.proximoPaso('OF-1', p, r, { tipo: 'siguiente', etapa: 'D8', texto: 'Sigue D8' });
  assert.equal(otraEtapa.etapa, 'D8');
  assert.equal(otraEtapa.comando, null); // el comando calculado era para D7: no se mezcla
  assert.equal(otraEtapa.tono, 'neutro');
  const firmar = L.proximoPaso('OF-1', p, r, { tipo: 'firmar_gate', etapa: 'D7', texto: 'T' });
  assert.match(firmar.comando, /orq firmar --oferta OF-1 --etapa D7/); // misma etapa: sí se reutiliza
  assert.equal(firmar.tono, 'aviso');
});

// ───────────────────────── rediseño UX: lenguaje de negocio ─────────────────────────

test('nombres humanos de etapa: los 11 del flujo, con el código como etiqueta secundaria', () => {
  assert.deepEqual(L.ORDEN_ETAPAS.map((id) => L.nombreHumano(id)), [
    'Descubrir', 'Mercado', 'Validar', 'Oferta', 'Producto', 'Página de venta y pago', 'Anuncios', 'Campaña', 'Operación', 'Escalado', 'Después de la venta']);
  assert.equal(L.etiquetaEtapa('D7'), 'D7 · Campaña');
  assert.equal(L.nombreHumano('ZZ'), 'ZZ'); // desconocida: no inventa
  for (const id of L.ORDEN_ETAPAS) {
    assert.ok(L.PREGUNTAS_ETAPA[id] && L.DESCRIPCION_HUMANA[id], `falta texto humano de ${id}`);
    assert.doesNotMatch(L.DESCRIPCION_HUMANA[id], /\bgate\b|preflight|hash/i); // sin jerga en la frase principal
  }
});

test('etapaParaPasos: estado, aviso y nombre humano para ui.pasos', () => {
  const p = L.construirPipeline(ejemplo.etapas);
  const d7 = L.etapaParaPasos(p.find((x) => x.id === 'D7'), { seleccionada: true });
  assert.deepEqual({ id: d7.id, nombre: d7.nombre, codigo: d7.codigo, estado: d7.estado, aviso: d7.aviso, seleccionada: d7.seleccionada, destacada: d7.destacada },
    { id: 'D7', nombre: 'Campaña', codigo: 'D7', estado: 'espera_firma', aviso: null, seleccionada: true, destacada: true });
  const d6 = L.etapaParaPasos(p.find((x) => x.id === 'D6'));
  assert.deepEqual([d6.estado, d6.destacada], ['aprobado', false]);
  const sin = L.etapaParaPasos(L.vistaEtapa('D9', undefined));
  assert.equal(sin.estado, 'pendiente');
  assert.equal(sin.aviso, 'Sin datos');
  const obs = L.etapaParaPasos(L.vistaEtapa('D3', { id: 'D3', estado: 'aprobado', obsoleta: true }));
  assert.equal(obs.estado, 'obsoleta');
  assert.equal(obs.aviso, 'Hay que rehacerla');
});

test('estadoHumano: palabras de negocio con tono', () => {
  const v = (raw) => L.estadoHumano(L.vistaEtapa('D4', { id: 'D4', ...raw }));
  assert.deepEqual(v({ estado: 'aprobado' }), { texto: 'Aprobada', tono: 'ok' });
  assert.deepEqual(v({ estado: 'en_QA', gate_pendiente: true }), { texto: 'Espera tu firma', tono: 'aviso' });
  assert.deepEqual(v({ estado: 'en_QA' }), { texto: 'En revisión de calidad', tono: 'info' });
  assert.deepEqual(v({ estado: 'bloqueado' }), { texto: 'Bloqueada', tono: 'error' });
  assert.equal(L.estadoHumano(L.vistaEtapa('D4', undefined)).texto, 'Sin datos');
});

test('proximoPasoHumano: «D7 · Campaña espera tu firma» con el botón «Ver cómo firmarlo»', () => {
  const vistas = L.construirPipeline(ejemplo.etapas);
  const resumen = L.resumenPipeline(vistas);
  const p = L.proximoPasoHumano('OF-202611-01', vistas, resumen, { tipo: 'firmar_gate', etapa: 'D7', texto: 'D7 (Campañas Meta) espera tu firma (gate H).', comando: 'python -m engine.orq firmar --oferta OF-202611-01 --etapa D7 --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno' });
  assert.equal(p.tipo, 'firmar_gate');
  assert.equal(p.titulo, 'D7 · Campaña espera tu firma');
  assert.equal(p.tono, 'acento'); // lo que espera al dueño lleva el acento
  assert.equal(p.accion.texto, 'Ver cómo firmarlo');
  assert.equal(p.accion.modo, 'firmar');
  assert.match(p.comando, /engine\.orq firmar --oferta OF-202611-01 --etapa D7 --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno/);
  assert.equal(p.secundaria.pestana, 'revision');
  assert.doesNotMatch(p.titulo, /gate|Meta/i);
});

test('proximoPasoHumano: cada situación tiene su frase y su botón', () => {
  const con = (raw) => {
    const vistas = L.construirPipeline([{ id: 'D1', estado: 'aprobado' }, { id: 'M1', estado: 'aprobado' }, { id: 'D2', ...raw }]);
    return L.proximoPasoHumano('OF-1', vistas, L.resumenPipeline(vistas));
  };
  assert.equal(con({ estado: 'en_QA', ronda_qa: 2 }).titulo, 'D2 · Validar está en revisión de calidad');
  assert.match(con({ estado: 'en_QA', ronda_qa: 2 }).detalle, /ronda 2/);
  assert.equal(con({ estado: 'en_progreso' }).accion.texto, 'Abrir la etapa');
  assert.equal(con({ estado: 'bloqueado', bloqueo: 'falta la API' }).tono, 'error');
  assert.equal(con({ estado: 'bloqueado', bloqueo: 'falta la API' }).detalle, 'falta la API');
  assert.equal(con({ estado: 'escalado' }).titulo, 'D2 · Validar necesita una decisión tuya');
  assert.equal(con({ estado: 'pendiente' }).titulo, 'Siguiente: D2 · Validar');
  assert.equal(con({ estado: 'pendiente' }).accion.modo, 'ejecutar');
  assert.equal(con({ estado: 'aprobado', obsoleta: true }).titulo, 'Rehacer D2 · Validar');
  const vacias = L.construirPipeline([]);
  const sin = L.proximoPasoHumano('OF-1', vacias, L.resumenPipeline(vacias));
  assert.equal(sin.tipo, 'sin_estado');
  const todas = L.construirPipeline(L.ORDEN_ETAPAS.filter((x) => x !== 'D9').map((id) => ({ id, estado: 'aprobado' })));
  const fin = L.proximoPasoHumano('OF-1', todas, L.resumenPipeline(todas));
  assert.equal(fin.tipo, 'completa');
  assert.equal(fin.tono, 'ok');
});

test('revisión de calidad en palabras: veredicto, gravedad, estado del hallazgo, puntaje', () => {
  assert.equal(L.veredictoHumano('PASS'), 'Aprobada por la revisión');
  assert.equal(L.veredictoHumano('FAIL'), 'Rechazada por la revisión');
  assert.equal(L.veredictoHumano(null), 'Sin veredicto');
  assert.deepEqual(['BLOQUEANTE', 'MAYOR', 'MENOR', 'MEJORA'].map(L.tonoSeveridadQa), ['error', 'grave', 'aviso', 'info']);
  assert.equal(L.SEVERIDAD_QA_HUMANA.BLOQUEANTE, 'Bloqueante');
  assert.deepEqual(L.estadoHallazgo('corregido_por_qa'), { texto: 'Corregido por la revisión', tono: 'ok', abierto: false });
  assert.deepEqual(L.estadoHallazgo('abierto'), { texto: 'Abierto', tono: 'error', abierto: true });
  assert.equal(L.estadoHallazgo('algo_raro').texto, 'algo raro');
  assert.equal(L.puntajeTexto('4.40'), '4,4');
  assert.equal(L.puntajeTexto(3.8), '3,8');
  assert.equal(L.puntajeTexto('x'), null);
  assert.equal(L.puntajeTexto(null), null);
});

test('título y mercado de la oferta en lenguaje humano', () => {
  assert.equal(L.tituloDeOferta({ titulo: 'El Puente de la Pausa', brief: { tema_semilla: 'otra cosa' } }), 'El Puente de la Pausa');
  assert.equal(L.tituloDeOferta({ brief: { tema_semilla: 'reincorporación laboral tras una pausa larga' } }), 'Reincorporación laboral tras una pausa larga');
  assert.equal(L.tituloDeOferta({ brief: { slug: 'reinsercion-laboral' } }), 'Reinsercion laboral');
  assert.equal(L.tituloDeOferta({ estado: { oferta_id: 'OF-1' }, id: '_x' }), 'OF-1');
  assert.equal(L.tituloDeOferta({ id: '_x' }), '_x');
  assert.equal(L.tituloDeOferta({}), '');
  assert.match(L.nombreIdioma('es-ES'), /^Español/);
  assert.equal(L.nombrePais('ES'), 'España');
  assert.equal(L.nombreIdioma(''), null);
  assert.equal(L.nombrePais(null), null);
  const m = L.fichaMercado(ejemplo);
  assert.equal(m.locale, 'es-ES');
  assert.deepEqual(m.paisesCodigos, ['ES']);
  assert.deepEqual(m.paises, ['España']);
  assert.equal(m.moneda, 'EUR');
  assert.equal(m.esHipotesis, true);
  const vacia2 = L.fichaMercado(null);
  assert.equal(vacia2.locale, null);
  assert.deepEqual(vacia2.paises, []);
});

test('historial: nombres humanos de evento', () => {
  assert.equal(L.eventoHumano('transicion'), 'Cambio de estado');
  assert.equal(L.eventoHumano('llamada_herramienta'), 'Trabajo de IA');
  assert.equal(L.eventoHumano('algo_nuevo'), 'algo nuevo');
  assert.equal(L.eventoHumano(null), 'Evento');
});

test('veredicto en palabras cortas y de cumplimiento', () => {
  assert.equal(L.veredictoCorto('PASS'), 'aprobada');
  assert.equal(L.veredictoCorto('PASS_CON_NOTAS'), 'aprobada con notas');
  assert.equal(L.veredictoCorto('x'), 'sin veredicto');
  assert.equal(L.veredictoCumplimiento('PASS'), 'Cumplimiento sin objeciones');
  assert.equal(L.veredictoCumplimiento(null), 'Sin informe de cumplimiento');
});

test('bloqueoHumano quita el código técnico del principio y deja el motivo', () => {
  assert.equal(L.bloqueoHumano('falta_insumo: Falta la plantilla base'), 'Falta la plantilla base');
  assert.equal(L.bloqueoHumano('Falta la API de Meta'), 'Falta la API de Meta');
  assert.equal(L.bloqueoHumano('  sin_dato: x y '), 'x y');
  assert.equal(L.bloqueoHumano(null), '');
  assert.equal(L.bloqueoHumano('Nota: algo'), 'Nota: algo'); // solo códigos en minúsculas con guion bajo o letras
  const vistas = L.construirPipeline([{ id: 'D1', estado: 'aprobado' }, { id: 'M1', estado: 'bloqueado', bloqueo: { tipo: 'falta_insumo', motivo: 'Falta el brief' } }]);
  const p = L.proximoPasoHumano('OF-1', vistas, L.resumenPipeline(vistas));
  assert.equal(p.detalle, 'Falta el brief');
});

test('glosario de Ofertas: claves válidas, nombre y definición corta (≤ 140), sin pisar el glosario base', async () => {
  const { TERMINOS } = await import('../../dashboard/web/lib/glosario-ofertas.js');
  const { GLOSARIO } = await import('../../dashboard/web/lib/glosario.js');
  const claves = Object.keys(TERMINOS);
  assert.ok(claves.length >= 20);
  for (const k of claves) {
    assert.match(k, /^[a-z0-9_]{1,60}$/);
    assert.ok(TERMINOS[k].nombre && TERMINOS[k].corto && TERMINOS[k].largo, `${k} sin nombre, corto o largo`);
    assert.ok(TERMINOS[k].corto.length <= 140, `${k}: corto de ${TERMINOS[k].corto.length} caracteres`);
    assert.ok(!(k in GLOSARIO), `${k} ya existe en glosario.js (mandaría el base)`);
  }
  // los términos que usan las cuatro pantallas existen (en el fragmento o en el glosario base)
  for (const k of ['bitacora_pulido', 'nivel_autonomia', 'oferta_demo', 'pipeline_oferta', 'dod_skill', 'skill_maker_qa', 'severidad_pulido', 'decision_mercado', 'fase_oferta', 'gate_pendiente', 'veredicto_qa', 'severidad_qa', 'rubrica_qa', 'checks_l1', 'regla_de_skill', 'skill_borrador', 'skill_v1', 'gate_a', 'gate_s', 'gate_h']) {
    assert.ok(k in TERMINOS || k in GLOSARIO, `falta el término ${k}`);
  }
});

// ───────────── landing original del referente ─────────────

test('normalizarReferentesOferta: pasan solo las direcciones https limpias; el resto del texto se limpia', () => {
  const r = L.normalizarReferentesOferta({
    comando_registrar: '.venv/bin/python -m scripts.referentes.landing registrar <id> "<URL>" --oferta OF-202611-91 --escribir',
    referentes: [
      { origen: 'validacion', url: 'https://axondigital.site/mapaspagnolo/', dominio: 'axondigital.site', nombre: 'Axon‮', nota: null },
      { origen: 'registro', url: 'javascript:alert(1)', dominio: 'x' },
      { origen: 'registro', url: 'http://a.example/x' },
      { origen: 'registro', url: 'https://a.example/x y' },
      { origen: 'registro', url: 'https://a.example/‮gnp' },
      null, 'x', { url: 5 },
    ],
  });
  assert.equal(r.filas.length, 1);
  assert.equal(r.filas[0].url, 'https://axondigital.site/mapaspagnolo/');
  assert.ok(!r.filas[0].nombre.includes('‮'));
  assert.equal(r.filas[0].origen, 'validacion');
  assert.ok(r.comando.includes('--oferta OF-202611-91'));
  assert.deepEqual(L.normalizarReferentesOferta(null), { filas: [], comando: '' });
  assert.deepEqual(L.normalizarReferentesOferta({ referentes: 'no es lista' }).filas, []);
});

test('pages/oferta.js: la landing original es el único enlace externo y lleva target=_blank con rel=noopener noreferrer', () => {
  const fuente = readFileSync(join(AQUI, '..', '..', 'dashboard', 'web', 'pages', 'oferta.js'), 'utf8');
  assert.match(fuente, /href: f\.url, target: '_blank', rel: 'noopener noreferrer'/);
  assert.equal((fuente.match(/target: '_blank'/g) || []).length, 1, 'un solo enlace que abre otra pestaña');
});
