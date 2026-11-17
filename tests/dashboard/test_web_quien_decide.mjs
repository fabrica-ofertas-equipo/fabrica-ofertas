// test_web_quien_decide.mjs — lógica pura y render (DOM falso) de #/quien-decide «Quién decide qué».
// Ejecutar: node --test tests/dashboard/test_web_quien_decide.mjs
// Los archivos reales del repositorio (contratos/gates.json, mapeo.md, validar_esquemas.py…) solo se LEEN, y solo si existen, para comprobar que la pantalla los refleja.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import * as Q from '../../dashboard/web/lib/quien-decide.js';
import { ui, fmt } from '../../dashboard/web/ui.js';
import { buscarTermino, FRAGMENTOS, CONFLICTOS, ORIGENES } from '../../dashboard/web/lib/glosario-indice.js';
import { ESTILOS_N4_QUIEN_DECIDE } from '../../dashboard/web/lib/estilos-n4.js';
import { instalarDomFalso, porClase, porTag, texto, todos } from '../fixtures/dashboard/operacion/dom_falso.mjs';

const rutaFx = (dir, n) => fileURLToPath(new URL(`../fixtures/dashboard/${dir}/${n}`, import.meta.url));
const fx = (n) => JSON.parse(readFileSync(rutaFx('quien-decide', n), 'utf8'));
const fxP = (n) => JSON.parse(readFileSync(rutaFx('parametros', n), 'utf8'));
const raiz = (rel) => fileURLToPath(new URL(`../../${rel}`, import.meta.url));
const clonar = (x) => JSON.parse(JSON.stringify(x));

const GATES = fx('api_gates.json');
const SIS_FRENO = fx('sistema_freno.json');
const SIS_PAUSA = fx('sistema_pausa.json');
const PLANTILLA = { limites: fxP('limites_plantilla.json'), autonomia: fxP('autonomia_real.json'), parametros: null, propuestas: [] };
const FIJADOS = { limites: fxP('limites_fijados.json'), autonomia: fxP('autonomia_real.json'), parametros: null, propuestas: [] };

const modelo = (over = {}) => Q.modeloQuienDecide({ gates: GATES, parametros: PLANTILLA, sistema: SIS_FRENO, ...over }, fmt);
const fila = (m, id) => m.hoy.filas.find((f) => f.id === id);
const filaObj = (m, id) => m.objetivo.filas.find((f) => f.id === id);
const autonomiaCon = (cambios) => { const a = clonar(fxP('autonomia_real.json')); for (const [e, n] of Object.entries(cambios)) a.nivel_por_etapa[e].nivel = n; return a; };

// ───────────────────────── la tabla sale de los archivos, no de memoria ─────────────────────────

test('hay una fila por cada entrada de gates.json (más las etapas de autonomia.yaml sin fila): nada escrito a mano', () => {
  const m = modelo();
  const entradas = Object.keys(GATES.gates.entradas);
  for (const k of entradas) assert.ok(fila(m, k), `falta la fila de ${k}`);
  assert.equal(m.hoy.filas.length, entradas.length + 2, 'X1 y X2 no tienen fila en gates.json pero sí nivel en autonomia.yaml');
  assert.deepEqual(m.hoy.filas.filter((f) => f.sinEntrada).map((f) => f.id), ['etapa:X1', 'etapa:X2']);
  assert.equal(fila(m, 'etapa:X1').gate, null);
  assert.match(fila(m, 'etapa:X1').nota, /puede frenar en cualquier nivel/i);
  // las etapas salen en el orden del flujo y detrás van las acciones agrupadas
  const etapas = m.hoy.filas.filter((f) => f.tipo === 'etapa').map((f) => f.clave);
  assert.deepEqual(etapas, ['O0', 'D0', 'M1', 'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10', 'F1', 'F2', 'X1', 'X2']);
  const grupos = m.hoy.filas.filter((f) => f.tipo === 'accion').map((f) => f.grupo);
  assert.deepEqual([...grupos].sort((a, b) => Q.GRUPOS.findIndex((g) => g.id === a) - Q.GRUPOS.findIndex((g) => g.id === b)), grupos, 'acciones ordenadas por grupo');
});

test('una fila nueva en gates.json aparece sola, con un nombre legible aunque no esté en el catálogo', () => {
  const g = clonar(GATES);
  g.gates.entradas['accion:accion_nueva_de_prueba'] = { descripcion: 'x', gate: { N0: 'H', N1: 'H', N2: 'S', N3: 'S', N4: 'A' } };
  g.gates.entradas['etapa:Z9'] = { descripcion: null, gate: { N0: 'A', N1: 'A', N2: 'A', N3: 'A', N4: 'A' } };
  const m = modelo({ gates: g });
  assert.equal(fila(m, 'accion:accion_nueva_de_prueba').nombre, 'Accion nueva de prueba');
  assert.equal(fila(m, 'accion:accion_nueva_de_prueba').grupo, 'reglas');
  assert.equal(fila(m, 'etapa:Z9').nombre, 'Z9 · Etapa');
  assert.ok(fila(m, 'etapa:Z9').gate === 'A');
});

test('contrato real: contratos/gates.json se refleja entero y el catálogo de nombres y grupos lo cubre (si el archivo está)', () => {
  const ruta = raiz('contratos/gates.json');
  if (!existsSync(ruta)) return;
  const real = JSON.parse(readFileSync(ruta, 'utf8'));
  const g = { gates: { schema_version: real.schema_version, niveles: real.niveles, entradas: Object.fromEntries(Object.entries(real.entradas).map(([k, v]) => [k, { descripcion: v.descripcion, gate: v.gate }])) }, acciones_minimas_h: GATES.acciones_minimas_h };
  const m = modelo({ gates: g });
  for (const k of Object.keys(real.entradas)) assert.ok(fila(m, k), `${k} no aparece en la pantalla`);
  for (const k of Object.keys(real.entradas).filter((x) => x.startsWith('accion:'))) {
    const id = k.slice(7);
    assert.ok(Q.NOMBRE_ACCION[id], `falta el nombre en español de la acción ${id}: añádelo a NOMBRE_ACCION`);
    assert.ok(Q.GRUPO_DE_ACCION[id], `falta el grupo de la acción ${id}: añádelo a GRUPO_DE_ACCION`);
    const f = fila(m, k);
    if (!f.constante) assert.ok(Q.ETAPA_DE_ACCION[id], `la acción ${id} cambia con el nivel y no tiene etapa vinculada en ETAPA_DE_ACCION`);
  }
  assert.deepEqual(Object.keys(g.gates.entradas).sort(), Object.keys(GATES.gates.entradas).sort(), 'el fixture api_gates.json debe seguir siendo una copia del contrato: regenéralo si cambió');
});

test('ETAPA_DE_ACCION no contradice scripts/validar_esquemas.py::ETAPA_DE_ACCION (si el archivo está)', () => {
  const ruta = raiz('scripts/validar_esquemas.py');
  if (!existsSync(ruta)) return;
  const fuente = readFileSync(ruta, 'utf8');
  const i = fuente.indexOf('ETAPA_DE_ACCION = {');
  assert.ok(i >= 0, 'no se encontró ETAPA_DE_ACCION en el validador (¿se renombró?)');
  const bloque = fuente.slice(i, fuente.indexOf('}', i));
  const pares = [...bloque.matchAll(/"([a-z_0-9]+)":\s*"([A-Z0-9]+)"/g)];
  assert.ok(pares.length >= 5);
  for (const [, accion, etapa] of pares) assert.equal(Q.ETAPA_DE_ACCION[accion], etapa, `la etapa de ${accion}`);
});

test('TOPES_DE_FILA solo cita claves que existen en contratos/limites.schema.json y todas tienen nombre humano en el glosario', () => {
  const claves = [...new Set(Object.values(Q.TOPES_DE_FILA).flat())];
  assert.ok(claves.length > 20);
  const ruta = raiz('contratos/limites.schema.json');
  if (existsSync(ruta)) {
    const esquema = JSON.parse(readFileSync(ruta, 'utf8'));
    for (const k of claves) assert.ok(esquema.properties[k], `«${k}» no es una clave de limites.yaml`);
  }
  for (const k of claves) assert.ok(buscarTermino(`lim_${k}`), `falta el término lim_${k} en el glosario`);
  for (const k of Object.keys(Q.TOPES_DE_FILA)) assert.ok(GATES.gates.entradas[k] || /^etapa:(O0|D0|M1|D\d+|F1)$/.test(k), `${k} no es una fila del contrato`);
});

// ───────────────────────── gate que rige: el más estricto entre la tabla, el nivel y la lista de firmas ─────────────────────────

test('hoy con todo en N0: casi todo lo firmas tú; F1/F2 son automáticos y subir presupuesto (D8) aún no se hace', () => {
  const m = modelo();
  assert.equal(fila(m, 'etapa:D7').gate, 'H');
  assert.equal(fila(m, 'etapa:F1').gate, 'A');
  assert.equal(fila(m, 'accion:aumentar_presupuesto_d8').gate, 'NA');
  assert.equal(fila(m, 'accion:activar_campana').gate, 'H');
  const r = m.hoy.resumen;
  assert.equal(r.total, 41);
  assert.equal(r.conGate, 39);
  assert.deepEqual(r.conteo, { H: 36, S: 0, A: 2, NA: 1, sin: 2 });
  assert.equal(r.firmas, 36);
  assert.equal(r.todasN0, true);
  assert.equal(r.etapasEnN0, 17);
  assert.deepEqual(r.forzadas.sort(), ['activar_campana', 'lanzamiento_pais_idioma_nuevo'], 'la tabla llega a S en N3, pero la lista de firmas manda');
});

test('activar_campana sigue en H aunque D7 suba a N3: la lista de acciones que siempre piden tu firma es más estricta que la tabla', () => {
  const m = modelo({ parametros: { ...PLANTILLA, autonomia: autonomiaCon({ D7: 'N3' }) } });
  const f = fila(m, 'accion:activar_campana');
  assert.equal(f.nivel, 'N3');
  assert.equal(f.gateTabla, 'S', 'la tabla dice «por excepción» en N3');
  assert.equal(f.gate, 'H', 'pero rige tu firma');
  assert.equal(f.forzadoDifiere, true);
  assert.equal(f.limitadaPorLista, true);
  assert.equal(f.esMinima, true);
  assert.equal(f.tablaPermite, 'S');
  // la etapa D7 (armado en borrador) sí pasa a S: no está en la lista
  assert.equal(fila(m, 'etapa:D7').gate, 'S');
});

test('las seis acciones mínimas rigen aunque limites.yaml no las traiga; sin esa lista ni ese archivo, la tabla manda y el panel no inventa un H', () => {
  const sinLista = clonar(PLANTILLA);
  sinLista.limites.valores.acciones_gate_humano = [];
  const conMinimas = modelo({ parametros: { ...sinLista, autonomia: autonomiaCon({ D7: 'N4' }) } });
  assert.equal(fila(conMinimas, 'accion:activar_campana').gate, 'H');
  const sinNada = modelo({ gates: { ...GATES, acciones_minimas_h: null }, parametros: { ...sinLista, autonomia: autonomiaCon({ D7: 'N4' }) } });
  assert.equal(fila(sinNada, 'accion:activar_campana').gate, 'S', 'sin lista y sin mínimas, lo que dice la tabla');
  assert.equal(fila(sinNada, 'accion:activar_campana').enLista, false);
});

test('una acción añadida por el dueño a la lista se marca como tal, sin ser de las mínimas', () => {
  const p = clonar(PLANTILLA);
  p.limites.valores.acciones_gate_humano = [...p.limites.valores.acciones_gate_humano, 'email_marketing'];
  const m = modelo({ parametros: { ...p, autonomia: autonomiaCon({ D10: 'N4' }) } });
  const f = fila(m, 'accion:email_marketing');
  assert.equal(f.gateTabla, 'S');
  assert.equal(f.gate, 'H');
  assert.equal(f.esMinima, false);
  assert.equal(f.enLista, true);
});

test('NA: subir presupuesto (D8) no se hace hasta N3; con D8 en N3 es automático', () => {
  assert.equal(fila(modelo(), 'accion:aumentar_presupuesto_d8').gate, 'NA');
  const m = modelo({ parametros: { ...PLANTILLA, autonomia: autonomiaCon({ D8: 'N3' }) } });
  assert.equal(fila(m, 'accion:aumentar_presupuesto_d8').gate, 'A');
  assert.equal(fila(m, 'accion:pausar').gate, 'A', 'pausar es A desde N2');
});

test('filas iguales en los cinco niveles no dependen del nivel; las que cambian y no tienen etapa usan el nivel más bajo', () => {
  const m = modelo({ parametros: { ...PLANTILLA, autonomia: autonomiaCon({ D7: 'N4' }) } });
  const c = fila(m, 'accion:cambiar_limites');
  assert.equal(c.constante, true);
  assert.equal(c.nivel, null);
  assert.equal(c.gate, 'H');
  assert.equal(fila(m, 'accion:confirmar_validada').nivel, null);
  // sin etapa vinculada y no constante → nivel más bajo de las etapas
  const g = clonar(GATES);
  g.gates.entradas['accion:rara'] = { descripcion: null, gate: { N0: 'H', N1: 'H', N2: 'S', N3: 'S', N4: 'A' } };
  const r = fila(modelo({ gates: g, parametros: { ...PLANTILLA, autonomia: autonomiaCon({ D7: 'N4' }) } }), 'accion:rara');
  assert.equal(r.nivel, 'N0');
  assert.equal(r.nivelOrigen, 'minimo');
  assert.equal(r.gate, 'H');
});

test('sin autonomia.yaml el nivel es desconocido: las filas que cambian con el nivel no inventan un gate', () => {
  const m = modelo({ parametros: { ...PLANTILLA, autonomia: null } });
  assert.equal(m.hay.autonomia, false);
  assert.equal(fila(m, 'etapa:D2').gate, null);
  assert.equal(fila(m, 'etapa:F1').gate, 'A', 'las constantes sí se saben');
  assert.equal(fila(m, 'accion:cambiar_limites').gate, 'H');
  assert.deepEqual(m.faltan, ['empresa/autonomia.yaml']);
});

test('masEstricto y textoGateNivel', () => {
  assert.equal(Q.masEstricto('A', 'H', 'S'), 'H');
  assert.equal(Q.masEstricto('NA', 'A'), 'A');
  assert.equal(Q.masEstricto(null, undefined), null);
  assert.equal(Q.masEstricto('X', 'S'), 'S', 'un valor desconocido se ignora');
  assert.equal(Q.textoGateNivel('N3', 'S'), 'Nivel 3: por excepción');
  assert.equal(Q.textoGateNivel('N0', 'NA'), 'Nivel 0: aún no se hace');
  assert.equal(Q.textoGateNivel('N1', undefined), 'Nivel 1: sin dato');
});

test('leerGates descarta lo que no tiene la forma del contrato', () => {
  assert.equal(Q.leerGates(null).hay, false);
  assert.equal(Q.leerGates({ gates: null }).hay, false);
  assert.equal(Q.leerGates({ gates: { entradas: [] } }).hay, false);
  const g = Q.leerGates({ gates: { schema_version: '1.1.0', entradas: { 'etapa:D1': { gate: { N0: 'H', N1: 'Z', N9: 'H', N2: ['A'] } }, 'mala': { gate: { N0: 'H' } }, 'etapa:D2': { gate: 'H' }, 'etapa:D3': { gate: { N0: 'NA' }, descripcion: 7 } } }, acciones_minimas_h: ['a', 3] });
  assert.deepEqual(Object.keys(g.entradas), ['etapa:D1', 'etapa:D3']);
  assert.deepEqual(g.entradas['etapa:D1'].gate, { N0: 'H' });
  assert.equal(g.entradas['etapa:D3'].descripcion, null);
  assert.deepEqual(g.minimas, ['a']);
  assert.equal(g.version, '1.1.0');
});

// ───────────────────────── topes: «sin fijar: por defecto no se puede gastar» ─────────────────────────

test('topes: un límite en null se marca «sin fijar: por defecto no se puede gastar»; una lista vacía y un sello ausente también', () => {
  const m = modelo();
  const d7 = fila(m, 'etapa:D7');
  assert.deepEqual(d7.topes.map((t) => t.clave), ['gasto_diario_global', 'gasto_diario_por_oferta', 'gasto_total_test_por_oferta', 'limite_gasto_cuenta_meta']);
  assert.ok(d7.topes.every((t) => t.estado === 'sin_fijar' && t.bloquea && t.mensaje === 'Sin fijar: por defecto no se puede gastar'));
  assert.equal(d7.sinFijar, 4);
  const m1 = fila(m, 'etapa:M1');
  assert.ok(m1.topes.every((t) => t.estado === 'vacio' && t.mensaje === 'Lista vacía: por defecto no se puede gastar'));
  const sello = fila(m, 'accion:cambiar_limites').topes[0];
  assert.equal(sello.clave, 'sello');
  assert.equal(sello.mensaje, 'Sin tu firma: por defecto no se puede gastar');
  assert.equal(fila(m, 'etapa:F2').topes.length, 0);
  assert.ok(m.hoy.resumen.topesSinFijar.includes('gasto_diario_global'));
});

test('topes: un límite fijado muestra su valor con la moneda de los límites, sin float', () => {
  const m = modelo({ parametros: FIJADOS });
  const t = fila(m, 'etapa:D7').topes.find((x) => x.clave === 'gasto_diario_global');
  assert.equal(t.bloquea, false);
  assert.equal(t.estado, 'fijado');
  assert.equal(t.texto, fmt.dinero(20000, 'EUR'));
  assert.equal(fila(m, 'accion:cambiar_limites').topes[0].mensaje, 'Firmado por ti');
  const sinMoneda = clonar(FIJADOS);
  sinMoneda.limites.valores.moneda_limites = null;
  const t2 = fila(modelo({ parametros: sinMoneda }), 'etapa:D7').topes.find((x) => x.clave === 'gasto_diario_global');
  assert.match(t2.texto, /falta indicar la moneda/);
});

test('topes: sin limites.yaml no se afirma nada (ni «sin fijar» ni valor)', () => {
  const m = modelo({ parametros: { ...PLANTILLA, limites: null } });
  assert.equal(m.hay.limites, false);
  assert.ok(fila(m, 'etapa:D7').topes.every((t) => t.estado === 'sin_lectura' && !t.bloquea && t.mensaje === 'No se pudieron leer tus límites'));
  assert.deepEqual(m.faltan, ['empresa/limites.yaml']);
});

// ───────────────────────── frenos de empresa (J4) ─────────────────────────

test('frenos: hoy sin fijar frente al objetivo 300 / 3.000 USD, con el equivalente en presupuestos diarios', () => {
  const m = modelo();
  assert.equal(m.frenos.total, 2);
  assert.equal(m.frenos.fijados, 0);
  const [gasto, perdida] = m.frenos.frenos;
  assert.equal(gasto.clave, 'gasto_diario_global');
  assert.equal(gasto.vigente.valor, null);
  assert.equal(gasto.relacion, 'sin_fijar');
  assert.equal(gasto.vigente.mensaje, 'Sin fijar: por defecto no se puede gastar');
  assert.deepEqual(gasto.objetivo, { valor: 30000, moneda: 'USD', texto: fmt.dinero(30000, 'USD') });
  assert.equal(perdida.clave, 'perdida_neta_acumulada_max');
  assert.equal(perdida.objetivo.valor, 300000);
  assert.equal(gasto.derivado.objetivo, 17142, '300 USD / 1,75 = 171,42 USD de presupuestos diarios');
  assert.equal(gasto.derivado.vigente, null);
  assert.equal(m.frenos.sello.bloquea, true);
  assert.deepEqual(Q.OBJETIVO_FRENOS, { moneda: 'USD', gasto_diario_global: 30000, perdida_neta_acumulada_max: 300000 });
});

test('frenos: igual, distinto y otra moneda', () => {
  const ponerLimites = (cambios) => { const p = clonar(FIJADOS); Object.assign(p.limites.valores, cambios); return modelo({ parametros: p }).frenos; };
  const igual = ponerLimites({ moneda_limites: 'USD', gasto_diario_global: 30000, perdida_neta_acumulada_max: 300000 });
  assert.deepEqual(igual.frenos.map((f) => f.relacion), ['igual', 'igual']);
  assert.equal(igual.fijados, 2);
  assert.equal(igual.iguales, 2);
  assert.equal(igual.frenos[0].derivado.vigente, 17142);
  const distinto = ponerLimites({ moneda_limites: 'USD', gasto_diario_global: 20000, perdida_neta_acumulada_max: 300000 });
  assert.deepEqual(distinto.frenos.map((f) => f.relacion), ['distinto', 'igual']);
  const eur = ponerLimites({ moneda_limites: 'EUR', gasto_diario_global: 30000, perdida_neta_acumulada_max: 300000 });
  assert.deepEqual(eur.frenos.map((f) => f.relacion), ['otra_moneda', 'otra_moneda'], 'otra moneda: no se compara 300 EUR con 300 USD');
  assert.equal(eur.frenos[0].vigente.texto, fmt.dinero(30000, 'EUR'));
  const mitad = ponerLimites({ moneda_limites: 'USD', gasto_diario_global: 30000, perdida_neta_acumulada_max: null });
  assert.equal(mitad.fijados, 1);
  assert.equal(modelo({ parametros: { ...PLANTILLA, limites: null } }).frenos.frenos[0].relacion, 'sin_lectura');
});

test('dividirPorFactor: aritmética entera sin float', () => {
  assert.equal(Q.dividirPorFactor(30000, '1.75'), 17142);
  assert.equal(Q.dividirPorFactor(17500, '1.75'), 10000);
  assert.equal(Q.dividirPorFactor(1000, '2'), 500);
  assert.equal(Q.dividirPorFactor(1000, '1.5'), 666);
  assert.equal(Q.dividirPorFactor(0, '1.75'), 0);
  for (const malo of ['0', '0.00', 'x', '', null, undefined, '1.755', '-1.75', '1e3']) assert.equal(Q.dividirPorFactor(1000, malo), null, String(malo));
  for (const malo of [-1, 1.5, NaN, '300', null]) assert.equal(Q.dividirPorFactor(malo, '1.75'), null, String(malo));
});

test('comandosFrenos: los comandos son texto para copiar; una oferta hostil no entra en ellos', () => {
  const c = Q.comandosFrenos('OF-202611-01');
  assert.equal(c.proponer, '.venv/bin/python -m engine.propuestas proponer --oferta OF-202611-01');
  assert.equal(c.ensayo, '.venv/bin/python -m engine.propuestas sellar --como dueno');
  assert.equal(c.firmar, 'FABRICA_ENTORNO=produccion .venv/bin/python -m engine.propuestas sellar --como dueno --live --clave-privada <ruta_de_tu_clave_privada>');
  assert.equal(c.estado, '.venv/bin/python -m engine.limites estado --operacion gastar');
  assert.equal(Q.comandosFrenos('_ejemplo').proponer.endsWith('--oferta _ejemplo'), true);
  for (const hostil of ['OF-202611-01; rm -rf /', '$(id)', 'OF-1', '', null, undefined, 'OF-202611-01\nrm', '../x']) {
    assert.match(Q.comandosFrenos(hostil).proponer, /--oferta <id_de_la_oferta>$/, String(hostil));
  }
  assert.doesNotMatch(c.ensayo, /--live/, 'el ensayo nunca escribe');
});

// ───────────────────────── objetivo (J2) ─────────────────────────

test('objetivo: las cuatro columnas son el literal del reparto del dueño (mapeo.md §4)', () => {
  assert.deepEqual(Q.COLUMNAS_J2.map((c) => c.id), ['dueno', 'ia', 'robots', 'llega']);
  assert.deepEqual(Q.COLUMNAS_J2.map((c) => c.titulo), ['Decide el dueño', 'Decide la IA (Claude)', 'Deciden los robots (programas automáticos)', 'Le llega al dueño']);
  assert.equal(Q.COLUMNAS_J2.flatMap((c) => c.items).length, 16);
  const ruta = raiz('docs/_historial/mentor-sistema/mapeo.md');
  if (!existsSync(ruta)) return;
  const mapeo = readFileSync(ruta, 'utf8').toLowerCase();
  const seccion = mapeo.slice(mapeo.indexOf('## 4. autonomía y frenos'), mapeo.indexOf('## 5. '));
  for (const frase of ['techo de gasto y capital en riesgo', 'reglas de oro', 'régimen fiscal por país', 'el primer idioma', 'pausa global', 'freno de captura', 'qué se produce', 'qué se testea', 'qué se corrige', 'prender y apagar',
    'subir y bajar presupuesto', 'frenar', 'cargar lanzamientos', 'resumen del día', 'alertas de pago', 'sello de x1', 'preflight', '300 usd', '3.000 usd', 'vigía de pagos', 'auditor', 'rechazos']) {
    assert.ok(seccion.includes(frase), `«${frase}» ya no está en mapeo.md §4: revisa el literal`);
  }
});

test('objetivo (J2): los frenos 300 USD/día y pausa a 3.000 USD son los que dejó escritos el dueño (si el registro está)', () => {
  const ruta = raiz('docs/_historial/mentor-sistema/decisiones-del-dueno.md');
  if (!existsSync(ruta)) return;
  const t = readFileSync(ruta, 'utf8');
  assert.match(t, /300 USD\/día/);
  assert.match(t, /3\.000 USD/);
  assert.match(t, /\*\*J2\*\*/);
});

test('objetivo: HOY con todo en N0, ninguna fila del objetivo rige salvo las que ya son así por diseño', () => {
  const m = modelo();
  assert.equal(m.objetivo.total, 16);
  assert.deepEqual(m.objetivo.cuenta, { ya: 3, parcial: 1, falta: 12 });
  const ya = m.objetivo.filas.filter((f) => f.estado === 'ya').map((f) => f.id).sort();
  assert.deepEqual(ya, ['dueno.freno', 'dueno.pausa', 'ia.corrige']);
  assert.equal(filaObj(m, 'robots.prende').estado, 'falta');
  assert.equal(filaObj(m, 'robots.presupuesto').estado, 'parcial', 'la tabla ya dice A desde N3 para D8 y D9, pero faltan niveles, ritmo y código');
});

test('objetivo: «prender y apagar» comprueba gates.json, la lista de firmas y el nivel de D7, y lo demás lo marca como plan sin poder verificarlo', () => {
  const m = modelo();
  const f = filaObj(m, 'robots.prende');
  const estados = f.falta.map((x) => x.estado);
  assert.deepEqual(estados, ['pendiente', 'pendiente', 'pendiente', 'pendiente', 'plan']);
  assert.match(f.falta[0].tecnico, /activar_campana de H a A con condiciones \(hoy en N3 y N4: S y S\)/);
  assert.match(f.falta[1].tecnico, /ACCIONES_GATE_MINIMAS/);
  assert.match(f.falta[2].tecnico, /D7.*hoy N0/);
  assert.match(f.falta[4].tecnico, /engine\/guard\.py/);
  assert.match(f.falta[4].fuente, /mapeo\.md/);
  assert.match(f.hoy[0], /Activar una campaña: lo firmas tú \(la tabla llega a «por excepción» en los niveles altos, pero rige tu firma\)/);
});

test('objetivo: aunque lo comprobable esté hecho, la fila no se da por lograda mientras queden pasos del plan (el panel no presenta el objetivo como si rigiera)', () => {
  const g = clonar(GATES);
  g.gates.entradas['accion:activar_campana'].gate.N3 = 'A';
  g.gates.entradas['accion:activar_campana'].gate.N4 = 'A';
  const p = clonar(FIJADOS);
  p.limites.valores.acciones_gate_humano = ['reactivar_tras_pausa', 'cambiar_limites'];
  p.autonomia = autonomiaCon({ D7: 'N3', D8: 'N3', D9: 'N3' });
  const m = modelo({ gates: { ...g, acciones_minimas_h: [] }, parametros: p });
  const f = filaObj(m, 'robots.prende');
  assert.deepEqual(f.falta.map((x) => x.estado), ['ok', 'ok', 'ok', 'ok', 'plan']);
  assert.equal(f.estado, 'parcial');
  assert.equal(filaObj(m, 'robots.presupuesto').falta.filter((x) => x.estado === 'plan').length, 2);
  assert.notEqual(filaObj(m, 'robots.presupuesto').estado, 'ya');
  assert.equal(filaObj(m, 'llega.resumen').estado, 'falta', 'todo lo que te llega depende del plan');
  for (const o of m.objetivo.filas) if (o.falta.some((x) => x.estado === 'plan')) assert.notEqual(o.estado, 'ya', `${o.id}: tiene pasos del plan sin hacer`);
});

test('objetivo: lo que depende de un archivo que no se pudo leer es «sin_dato», no «pendiente» ni «ok»', () => {
  const m = modelo({ gates: null, parametros: { limites: null, autonomia: null } });
  assert.deepEqual(m.faltan, ['contratos/gates.json', 'empresa/limites.yaml', 'empresa/autonomia.yaml']);
  const prende = filaObj(m, 'robots.prende');
  assert.ok(prende.falta.filter((x) => x.estado === 'sin_dato').length >= 3);
  assert.match(prende.falta[0].texto, /no se pudo leer la tabla de puntos de control/);
  assert.match(prende.falta[0].tecnico, /contratos\/gates\.json/);
  assert.ok(filaObj(m, 'dueno.techo').falta.every((x) => x.estado === 'sin_dato'));
  assert.equal(m.hoy.filas.length, 0);
  assert.equal(m.hoy.resumen, null);
  assert.match(Q.mensajesBanner(m).hoy.titulo, /no se pudo leer la tabla de puntos de control/);
});

test('objetivo: «se conserva por código» distingue lo que ya existe, lo que falta fijar y lo que está por construir', () => {
  const m = modelo();
  const c = Object.fromEntries(m.objetivo.conserva.map((x) => [x.id, x.estado]));
  assert.deepEqual(c, { sello_x1: 'rige', preflight: 'rige', frenos: 'falta_valor', pausa: 'construir', rechazos: 'rige' });
  const fijos = modelo({ parametros: (() => { const p = clonar(FIJADOS); return p; })() });
  assert.equal(fijos.objetivo.conserva.find((x) => x.id === 'frenos').estado, 'rige');
  assert.equal(modelo({ parametros: { ...PLANTILLA, limites: null } }).objetivo.conserva.find((x) => x.id === 'frenos').estado, 'sin_dato');
  assert.match(m.objetivo.conserva.find((x) => x.id === 'pausa').nota, /por construir/);
});

test('objetivo: el primer idioma y el régimen fiscal salen de los límites reales (idiomas, países y cuentas vacíos hoy)', () => {
  const m = modelo();
  assert.match(filaObj(m, 'dueno.idioma').hoy.join(' '), /Idiomas permitidos: ninguno/);
  assert.equal(filaObj(m, 'dueno.idioma').falta.filter((x) => x.estado === 'pendiente').length, 3);
  assert.match(filaObj(m, 'dueno.fiscal').hoy[0], /no hay ningún dato fiscal/);
  const p = clonar(FIJADOS);
  p.limites.valores.locales_permitidos = ['pl-PL'];
  p.limites.valores.paises_permitidos = ['PL'];
  p.limites.valores.cuentas_permitidas = ['act_1'];
  const f = filaObj(modelo({ parametros: p }), 'dueno.idioma');
  assert.ok(f.falta.every((x) => x.estado === 'ok'));
  assert.equal(f.estado, 'ya');
});

// ───────────────────────── lo que sigue siendo humano ─────────────────────────

test('humano: reactivar tras PAUSA, firmar límites, reglas de oro, freno de captura e idioma nuevo, con su estado actual y su comando', () => {
  const m = modelo();
  assert.deepEqual(m.humano.map((h) => h.id), ['pausa', 'limites', 'reglas', 'freno', 'idioma']);
  const h = Object.fromEntries(m.humano.map((x) => [x.id, x]));
  assert.equal(h.pausa.gate.gate, 'H');
  assert.equal(h.pausa.gate.constante, true);
  assert.equal(h.pausa.actual.tono, 'ok');
  assert.deepEqual(h.pausa.comandos.map((c) => c.cmd), ['rm empresa/PAUSA']);
  assert.equal(h.limites.gate.gate, 'H');
  assert.equal(h.limites.actual.tono, 'aviso');
  assert.match(h.limites.actual.texto, /no están firmados/);
  assert.deepEqual(h.limites.comandos.map((c) => c.cmd), [Q.comandosFrenos(null).proponer, Q.comandosFrenos(null).ensayo, Q.comandosFrenos(null).firmar]);
  assert.equal(h.reglas.gate.gate, 'H');
  assert.equal(h.reglas.gate2.gate, 'H');
  assert.match(h.reglas.actual.texto, /Sin líneas rojas definidas/);
  assert.equal(h.freno.gate, null);
  assert.equal(h.freno.actual.tono, 'aviso');
  assert.match(h.freno.actual.texto, /HTTP 403/);
  assert.deepEqual(h.freno.comandos.map((c) => c.cmd), ['cat empresa/captura/freno.json', 'rm empresa/captura/freno.json']);
  assert.equal(h.idioma.gate.gate, 'H');
  assert.equal(h.idioma.gate.limitada, true, 'la tabla llega a S, pero rige tu firma');
  assert.match(h.idioma.actual.texto, /Ningún idioma permitido/);
});

test('humano: con PAUSA activa y el freno libre; con limites sellados', () => {
  const m = modelo({ sistema: SIS_PAUSA, parametros: FIJADOS });
  const h = Object.fromEntries(m.humano.map((x) => [x.id, x]));
  assert.equal(h.pausa.actual.tono, 'critico');
  assert.match(h.pausa.actual.texto, /PAUSA activa: perdida neta acumulada alcanzada/);
  assert.equal(h.freno.actual.tono, 'ok');
  assert.equal(h.limites.actual.tono, 'ok');
  assert.equal(modelo({ sistema: null }).humano[0].actual.texto, 'Estado de la PAUSA: sin dato');
});

test('humano: ningún comando que muestra el panel es una acción de gasto o activación; solo firmar escribe limites.yaml y es del dueño', () => {
  const m = modelo();
  const cmds = m.humano.flatMap((h) => h.comandos.map((c) => c.cmd));
  for (const c of cmds) assert.doesNotMatch(c, /activar|reanudar|--live.*activar|publicar|reembols/i, c);
  assert.equal(cmds.filter((c) => /--live/.test(c)).length, 1);
  assert.match(cmds.find((c) => /--live/.test(c)), /--como dueno/);
});

// ───────────────────────── cartel, métricas, filtros ─────────────────────────

test('cartel y métricas: mensaje de negocio primero, HOY y OBJETIVO siempre separados', () => {
  const m = modelo();
  const b = Q.mensajesBanner(m);
  assert.equal(b.hoy.titulo, 'Hoy, 36 de 39 decisiones las firmas tú');
  assert.match(b.hoy.detalle, /Las 17 etapas están en el nivel 0 \(todo lo apruebas tú\): nada avanza solo\./);
  assert.match(b.hoy.detalle, /frenos de empresa están sin fijar: por defecto no se puede gastar/);
  assert.match(b.objetivo.titulo, /prenden, suben, apagan y frenan idiomas solos, dentro de frenos de empresa/);
  assert.match(b.objetivo.detalle, /Todavía no rige: 3 de 16/);
  const mt = Q.metricasQuienDecide(m, fmt);
  assert.deepEqual(mt.map((x) => x.id), ['firmas', 'niveles', 'frenos', 'j2']);
  assert.deepEqual(mt.map((x) => x.valor), ['36 de 39', '17 de 17', '0 de 2', '3 de 16']);
  assert.equal(mt[1].tono, 'aviso');
  assert.equal(mt[2].tono, 'aviso');
  assert.match(mt[0].contexto, /2 acciones que seguirán siendo tuyas aunque subas de nivel/);
  const fijos = Q.metricasQuienDecide(modelo({ parametros: { ...FIJADOS, autonomia: autonomiaCon({ D7: 'N3' }) } }), fmt);
  assert.equal(fijos[1].valor, '16 de 17');
  assert.equal(fijos[1].tono, null);
  assert.equal(fijos[2].valor, '2 de 2');
  assert.equal(fijos[2].tono, 'ok');
  const vacio = Q.metricasQuienDecide(modelo({ gates: null, parametros: null }), fmt);
  assert.deepEqual(vacio.map((x) => x.valor), [null, null, null, '1 de 16'], 'sin datos, «—» y no un cero inventado; el 1 es el freno de captura, una regla ya vigente');
  assert.deepEqual(Q.pestanasQuienDecide(m).map((p) => p.id), ['hoy', 'objetivo', 'frenos', 'humano']);
});

test('filtrarFilas: por gate vigente y por texto, sin tildes ni mayúsculas', () => {
  const m = modelo();
  const f = m.hoy.filas;
  assert.equal(Q.filtrarFilas(f, {}).length, 41);
  assert.equal(Q.filtrarFilas(f, { gate: 'H' }).length, 36);
  assert.equal(Q.filtrarFilas(f, { gate: 'A' }).length, 2);
  assert.equal(Q.filtrarFilas(f, { gate: 'NA' }).length, 1);
  assert.equal(Q.filtrarFilas(f, { gate: 'sin' }).length, 2);
  const camp = Q.filtrarFilas(f, { texto: 'campanas' }).map((x) => x.id);
  assert.deepEqual(camp, ['etapa:D7'], 'sin tildes ni mayúsculas: «Campañas Meta»');
  assert.ok(Q.filtrarFilas(f, { texto: 'CAMPAÑA' }).some((x) => x.id === 'accion:activar_campana'));
  assert.ok(Q.filtrarFilas(f, { texto: 'GASTO DIARIO' }).some((x) => x.id === 'accion:activar_campana'), 'busca también en los límites que acotan');
  assert.deepEqual(Q.filtrarFilas(f, { texto: 'zzzz-no-existe' }), []);
  assert.equal(Q.filtrarFilas(f, { gate: 'A', texto: 'campaña' }).length, 0);
});

test('glosario: todos los términos que usa la pantalla existen y no chocan con otros fragmentos', () => {
  assert.ok(FRAGMENTOS.includes('decisiones'), 'glosario-decisiones.js debe estar registrado en glosario-indice.js');
  const usados = ['hoy_vigente', 'objetivo_j2', 'reparto_decisiones', 'gate_efectivo', 'gate_na', 'cierra_por_defecto', 'frenos_empresa', 'techo_gasto_diario', 'pausa_por_perdida', 'activar_sin_clic', 'vigia_pagos',
    'auditor_robots', 'rechazos_congelan', 'sigue_humano', 'nivel_de_etapa', 'gate_h', 'gate_s', 'gate_a', 'nivel_n0', 'nivel_n1', 'nivel_n2', 'nivel_n3', 'nivel_n4', 'lim_acciones_gate_humano', 'sello_x1', 'preflight', 'pausa', 'freno_captura', 'lim_sello',
    ...Object.values(Q.GATES_INFO).map((g) => g.glosario), ...Q.SE_CONSERVA.map((c) => c.glosario)];
  for (const k of new Set(usados)) assert.ok(buscarTermino(k), `falta el término «${k}» en el glosario`);
  const mios = Object.entries(ORIGENES).filter(([, o]) => o === 'decisiones').map(([k]) => k);
  assert.ok(mios.length >= 15);
  assert.deepEqual(CONFLICTOS.filter((c) => c.origen === 'decisiones' || c.ganador === 'decisiones'), []);
  for (const k of mios) assert.ok(buscarTermino(k).corto.length <= 140, `«${k}»: definición corta de más de 140 caracteres`);
});

test('estilos: solo tokens del sistema, sin colores propios ni recursos externos', () => {
  assert.doesNotMatch(ESTILOS_N4_QUIEN_DECIDE, /#[0-9a-fA-F]{3,8}\b/, 'ningún color literal: se usan los tokens de styles.css');
  assert.doesNotMatch(ESTILOS_N4_QUIEN_DECIDE, /url\(|@import|expression\(/);
  assert.match(ESTILOS_N4_QUIEN_DECIDE, /dashed/, 'el objetivo se distingue con borde discontinuo');
});

// ───────────────────────── render con DOM falso ─────────────────────────

let contadorModulo = 0;
async function cargarPagina() { contadorModulo += 1; return import(`../../dashboard/web/pages/quien-decide.js?prueba=${contadorModulo}`); }

function ctxDe({ gates = GATES, parametros = PLANTILLA, sistema = SIS_FRENO, falla = {}, estado = {}, llamadas = [] } = {}) {
  const sobre = (datos, fuente) => ({ datos, fuente, generado_en: '2026-11-06T12:00:00Z', vacio: datos === null, avisos: [] });
  const api = {
    sobre: async (ruta) => {
      llamadas.push(ruta);
      if (falla[ruta]) throw Object.assign(new Error('x'), { codigo: 'sin_conexion', mensaje: 'x' });
      if (ruta === '/gates') return sobre(gates, ['contratos/gates.json']);
      if (ruta === '/parametros') return sobre(parametros, ['empresa/limites.yaml', 'empresa/autonomia.yaml']);
      if (ruta === '/sistema') return sobre(sistema, ['empresa/PAUSA']);
      throw new Error(`ruta inesperada ${ruta}`);
    },
    post() { throw new Error('esta pantalla es de solo lectura: no debe hacer POST'); },
    get() { throw new Error('usa api.sobre'); },
  };
  return { api, ui, fmt, estado, params: {}, ruta: 'quien-decide', recargar() {}, navegar() {}, alSalir() {} };
}
const pestana = (r, titulo) => todos(r, (n) => n.getAttribute('role') === 'tab' && n.textContent.startsWith(titulo))[0];
const abrir = (r, titulo) => { const b = pestana(r, titulo); assert.ok(b, `no hay pestaña «${titulo}»`); b.dispararEvento('click'); return texto(r); };

test('render: la pantalla pide solo lecturas y arranca con la pestaña Hoy, el cartel HOY frente a OBJETIVO y las cuatro métricas', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await cargarPagina();
    assert.deepEqual({ ruta: pagina.meta.ruta, grupo: pagina.meta.grupo, icono: pagina.meta.icono, titulo: pagina.meta.titulo }, { ruta: 'quien-decide', grupo: 'Dinero y reglas', icono: 'escudo', titulo: 'Quién decide qué' });
    const llamadas = [];
    const r = await pagina.render(ctxDe({ llamadas }));
    assert.deepEqual([...llamadas].sort(), ['/gates', '/parametros', '/sistema']);
    const t = texto(r);
    assert.match(t, /Quién decide qué/);
    assert.match(t, /HOY · vigente en los archivos/);
    assert.match(t, /OBJETIVO \(J2\) · aún sin implementar/);
    assert.match(t, /Hoy, 36 de 39 decisiones las firmas tú/);
    assert.match(t, /36 de 39/);
    assert.match(t, /17 de 17/);
    assert.match(t, /0 de 2/);
    assert.match(t, /3 de 16/);
    assert.equal(todos(r, (n) => n.getAttribute('role') === 'tab').length, 4);
    assert.equal(porClase(r, 'qd-bloque--objetivo').length, 1);
    assert.equal(porClase(r, 'qd-bloque--hoy').length, 1);
    assert.match(t, /Quién decide hoy/);
    assert.match(t, /Lo firmas tú/);
    assert.match(t, /2 acciones seguirán siendo tuyas aunque subas de nivel/);
    assert.match(t, /Sin fijar: por defecto no se puede gastar/);
    assert.ok(porClase(r, 'qd-tira').length >= 39, 'una tira N0→N4 por cada fila con tabla (más las fichas de la vista estrecha)');
    assert.equal(porTag(r, 'table').length, 1);
  } finally { restaurar(); }
});

test('render Hoy: la tira por nivel marca el nivel vigente y lleva el gate de cada nivel en texto', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await cargarPagina();
    const r = await pagina.render(ctxDe({ parametros: { ...PLANTILLA, autonomia: autonomiaCon({ D7: 'N3' }) } }));
    abrir(r, 'Hoy');
    const tiras = porClase(r, 'qd-tira');
    const conActual = tiras.filter((t) => porClase(t, 'es-actual').length === 1);
    assert.ok(conActual.length >= 30);
    const t = tiras.find((x) => (x.getAttribute('aria-label') || '').includes('Nivel 3: por excepción') && (x.getAttribute('aria-label') || '').includes('Nivel actual: 3'));
    assert.ok(t, 'activar_campana con D7 en N3 muestra S en N3 como nivel vigente');
    assert.equal(porClase(t, 'qd-tira__n').map((n) => n.textContent).join(''), 'HHHSS');
    assert.match(texto(r), /rige tu firma/);
  } finally { restaurar(); }
});

test('render Hoy: el filtro por quién decide y la búsqueda filtran tabla y fichas a la vez sin cambiar de campo', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await cargarPagina();
    const r = await pagina.render(ctxDe());
    abrir(r, 'Hoy');
    const filasTabla = () => porTag(r, 'tbody')[0].children.length;
    const fichas = () => porClase(r, 'qd-ficha').length;
    assert.equal(filasTabla(), 41);
    assert.equal(fichas(), 41);
    const opcion = (rotulo) => todos(r, (n) => n.getAttribute('role') === 'radio' && n.textContent.startsWith(rotulo))[0];
    opcion('Automático').dispararEvento('click');
    assert.equal(filasTabla(), 2);
    assert.equal(fichas(), 2);
    assert.match(texto(r), /2 de 41 decisiones/);
    opcion('Todo').dispararEvento('click');
    const buscar = porTag(r, 'input')[0];
    buscar.value = 'reembolso';
    buscar.dispararEvento('input');
    assert.equal(filasTabla(), Q.filtrarFilas(modelo().hoy.filas, { texto: 'reembolso' }).length);
    assert.ok(filasTabla() > 1 && filasTabla() < 41, 'busca en el nombre, la clave y los límites que acotan');
    assert.equal(porTag(r, 'input')[0], buscar, 'el campo sigue siendo el mismo nodo');
    buscar.value = 'zzzz-no-existe';
    buscar.dispararEvento('input');
    assert.match(texto(r), /Ninguna decisión coincide con el filtro/);
    buscar.value = '';
    buscar.dispararEvento('input');
    assert.equal(filasTabla(), 41);
  } finally { restaurar(); }
});

test('render Objetivo: avisa de que es el destino y no lo vigente; cuatro columnas, «se conserva por código» y «qué falta» con fuente del plan', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await cargarPagina();
    const r = await pagina.render(ctxDe());
    const t = abrir(r, 'Objetivo (J2)');
    assert.match(t, /Esto es el OBJETIVO, no lo que rige hoy/);
    assert.match(t, /Todavía no está implementada: hoy activar una campaña sigue siendo una decisión tuya/);
    for (const titulo of ['Decide el dueño', 'Decide la IA (Claude)', 'Deciden los robots (programas automáticos)', 'Le llega al dueño']) assert.ok(t.includes(titulo), titulo);
    assert.equal(porClase(r, 'qd-col').length, 4);
    for (const lit of ['Techo de gasto y capital en riesgo', 'Régimen fiscal por país', 'Prender y apagar', 'Subir y bajar presupuesto', 'Frenar y rehabilitar un idioma', 'Resumen del día', 'Alertas de pago']) assert.ok(t.includes(lit), lit);
    assert.match(t, /Lo que se sigue cuidando solo, sin pedirte un clic/);
    assert.match(t, /Visto bueno firmado de cumplimiento, vigente y sin alterar/);
    assert.match(t, /Frenos de empresa: 300 USD por día y pausa a −3\.000 USD/);
    assert.match(t, /Falta fijar el valor/);
    assert.match(t, /Qué falta para llegar/);
    assert.match(t, /contratos\/gates\.json: activar_campana de H a A con condiciones/);
    assert.match(t, /engine\/guard\.py/);
    assert.match(t, /Según mapeo\.md §4, §10/);
    assert.match(t, /el panel no lo puede comprobar/);
    assert.equal(porClase(r, 'qd-obj__fila').length, 16);
    assert.ok(porClase(r, 'qd-aviso--objetivo').length >= 1);
    assert.equal(porClase(r, 'qd-col').every((c) => /dashed/.test(ESTILOS_N4_QUIEN_DECIDE)), true);
  } finally { restaurar(); }
});

test('render Frenos: vigente sin fijar frente a 300 / 3.000 USD y los tres comandos exactos para proponer y firmar', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await cargarPagina();
    const r = await pagina.render(ctxDe({ estado: { ofertaActiva: 'OF-202611-01' } }));
    const t = abrir(r, 'Frenos de empresa');
    assert.match(t, /Gasto máximo por día/);
    assert.match(t, /Pérdida antes de pausar todo/);
    assert.match(t, /Sin fijar/);
    assert.match(t, /300,00\s?US\$ por día/);
    assert.match(t, /3\.000,00\s?US\$ de pérdida/);
    assert.match(t, /171,42\s?US\$ de presupuestos diarios sumados/);
    assert.match(t, /Tus límites no están firmados/);
    assert.match(t, /\.venv\/bin\/python -m engine\.propuestas proponer --oferta OF-202611-01/);
    assert.match(t, /\.venv\/bin\/python -m engine\.propuestas sellar --como dueno/);
    assert.match(t, /FABRICA_ENTORNO=produccion \.venv\/bin\/python -m engine\.propuestas sellar --como dueno --live --clave-privada <ruta_de_tu_clave_privada>/);
    assert.match(t, /El panel nunca cambia tus límites ni firma por ti/);
    assert.match(t, /Para que la propuesta traiga los 300 y los 3\.000 de J4 falta implementar/);
    assert.ok(porClase(r, 'comando').length >= 4);
    assert.equal(porClase(r, 'qd-caja--objetivo').length, 2);
    // con una oferta activa hostil el comando no la copia
    const r2 = await pagina.render(ctxDe({ estado: { ofertaActiva: 'OF-1; rm -rf /' } }));
    assert.doesNotMatch(abrir(r2, 'Frenos de empresa'), /rm -rf/);
  } finally { restaurar(); }
});

test('render Frenos: con los límites fijados enseña el valor vigente y lo compara con el objetivo', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await cargarPagina();
    const p = clonar(FIJADOS);
    Object.assign(p.limites.valores, { moneda_limites: 'USD', gasto_diario_global: 30000, perdida_neta_acumulada_max: 250000 });
    const t = abrir(await pagina.render(ctxDe({ parametros: p })), 'Frenos de empresa');
    assert.match(t, /Coincide con el objetivo/);
    assert.match(t, /Distinto del objetivo/);
    assert.match(t, /2\.500,00\s?US\$/);
    assert.doesNotMatch(t, /Tus límites no están firmados/);
  } finally { restaurar(); }
});

test('render Sigue siendo tuyo: estado actual y comando de cada decisión; el panel no ofrece botones que cambien nada', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await cargarPagina();
    const r = await pagina.render(ctxDe());
    const t = abrir(r, 'Sigue siendo tuyo');
    for (const titulo of ['Reactivar tras una PAUSA general', 'Firmar tus límites', 'Cambiar las reglas de oro', 'Levantar el freno de la captura de anuncios', 'Abrir un idioma o país nuevo']) assert.ok(t.includes(titulo), titulo);
    assert.match(t, /rm empresa\/PAUSA/);
    assert.match(t, /rm empresa\/captura\/freno\.json/);
    assert.match(t, /cat empresa\/captura\/freno\.json/);
    assert.match(t, /No hay ninguna PAUSA activa ahora/);
    assert.match(t, /Freno PUESTO: HTTP 403 \(Document\)/);
    assert.match(t, /Sin líneas rojas definidas/);
    assert.match(t, /la tabla llega a «por excepción» en los niveles altos, pero rige tu firma/);
    assert.match(t, /Aunque los robots prendan y apaguen solos, estas decisiones seguirán siendo tuyas/);
    // sin escritura: ningún formulario, ningún botón de acción (solo Actualizar, Copiar, pestañas y filtros)
    for (const titulo of ['Hoy', 'Objetivo (J2)', 'Frenos de empresa', 'Sigue siendo tuyo']) abrir(r, titulo);
    assert.equal(porTag(r, 'textarea').length, 0);
    assert.equal(porTag(r, 'form').length, 0);
    const permitidos = /^(Actualizar|Copiar|Hoy|Objetivo|Frenos|Sigue|Todo|Lo firmas|Por excepción|Automático|Aún no|Sin fila)/;
    for (const b of porTag(r, 'button')) {
      const rotulo = b.textContent.trim();
      if (b.getAttribute('aria-label') && !rotulo) continue; // iconos de ayuda
      assert.match(rotulo, permitidos, `botón inesperado «${rotulo}»`);
      assert.doesNotMatch(rotulo, /guardar|editar|aplicar|activar|sellar|borrar|levantar|firmar|pausar/i);
    }
  } finally { restaurar(); }
});

test('render: texto hostil de un archivo se muestra como texto, nunca como HTML', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await cargarPagina();
    const hostil = '<img src=x onerror=alert(1)> ‮gnp.exe <script>x()</script>';
    const g = clonar(GATES);
    g.gates.entradas['etapa:D2'].descripcion = hostil;
    g.gates.entradas['accion:hostil_xss'] = { descripcion: hostil, gate: { N0: 'H', N1: 'H', N2: 'H', N3: 'H', N4: 'H' } };
    const s = { pausa: { activa: true, desde: null, motivo: hostil }, freno_captura: { activo: true, ts: null, motivo: hostil } };
    const p = clonar(PLANTILLA);
    p.limites.valores.politica_divulgacion_ia = hostil;
    const r = await pagina.render(ctxDe({ gates: g, sistema: s, parametros: p }));
    const t = [texto(r), abrir(r, 'Sigue siendo tuyo'), abrir(r, 'Hoy')].join('\n');
    assert.ok(t.includes('<img src=x onerror=alert(1)>'), 'el texto hostil aparece literal');
    assert.equal(porTag(r, 'img').length, 0);
    assert.equal(porTag(r, 'script').length, 0);
    assert.ok(t.includes('⟦U+202E⟧'), 'los controles bidireccionales se hacen visibles');
    assert.match(t, /Hostil xss/);
  } finally { restaurar(); }
});

test('render: sin contratos/gates.json la pestaña Hoy explica qué falta con el comando que lo comprueba; el resto sigue con lo que sí se leyó', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await cargarPagina();
    const r = await pagina.render(ctxDe({ gates: { gates: null, acciones_minimas_h: null } }));
    const t = abrir(r, 'Hoy');
    assert.match(t, /No se pudo leer la tabla de puntos de control/);
    assert.match(t, /contratos\/gates\.json/);
    assert.match(t, /\.venv\/bin\/python -m scripts\.validar_esquemas esquemas/);
    assert.match(t, /No se pudo leer la tabla de puntos de control\./);
    assert.match(t, /no se pudo comprobar/i);
    assert.equal(porTag(r, 'table').length, 0);
    assert.match(texto(r), /Hoy: no se pudo leer la tabla de puntos de control/);
    assert.match(abrir(r, 'Frenos de empresa'), /Gasto máximo por día/, 'los frenos no dependen de gates.json');
    assert.match(abrir(r, 'Objetivo (J2)'), /Esto es el OBJETIVO/);
  } finally { restaurar(); }
});

test('render: sin limites.yaml la pestaña Frenos explica qué falta; con la API de gates caída el resto se pinta', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await cargarPagina();
    const sinLimites = await pagina.render(ctxDe({ parametros: { ...PLANTILLA, limites: null } }));
    const t = abrir(sinLimites, 'Frenos de empresa');
    assert.match(t, /No se pudieron leer tus límites/);
    assert.match(t, /\.venv\/bin\/python -m engine\.limites estado --operacion gastar/);
    assert.match(texto(sinLimites), /No se pudo leer tus límites\./);
    const gatesCaida = await pagina.render(ctxDe({ falla: { '/gates': true } }));
    assert.match(abrir(gatesCaida, 'Hoy'), /No se pudo leer la tabla de puntos de control/);
    assert.match(texto(gatesCaida), /17 de 17/, 'los niveles de autonomía sí se leyeron');
  } finally { restaurar(); }
});

test('render: si no responde ninguna lectura, un error con reintento y sin datos inventados', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await cargarPagina();
    const r = await pagina.render(ctxDe({ falla: { '/gates': true, '/parametros': true, '/sistema': true } }));
    assert.equal(porClase(r, 'error-box').length, 1);
    assert.doesNotMatch(texto(r), /36 de 39/);
    assert.equal(todos(r, (n) => n.getAttribute('role') === 'tab').length, 0);
  } finally { restaurar(); }
});

test('render: la pestaña y el filtro sobreviven a una actualización en vivo', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await cargarPagina();
    const r1 = await pagina.render(ctxDe());
    abrir(r1, 'Frenos de empresa');
    const r2 = await pagina.alCambio(ctxDe());
    assert.match(texto(r2), /Cuánto se puede gastar y cuánto se puede perder/, 'sigue en la pestaña Frenos de empresa');
    assert.equal(pestana(r2, 'Frenos de empresa').getAttribute('aria-selected'), 'true');
  } finally { restaurar(); }
});
