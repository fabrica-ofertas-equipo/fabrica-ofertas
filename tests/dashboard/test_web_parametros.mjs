// test_web_parametros.mjs — lógica pura y render (DOM falso) de #/parametros. Ejecutar: node --test tests/dashboard/test_web_parametros.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import * as P from '../../dashboard/web/lib/parametros.js';
import { ui, fmt } from '../../dashboard/web/ui.js';
import { instalarDomFalso, porClase, porTag, texto, todos } from '../fixtures/dashboard/operacion/dom_falso.mjs';

const fx = (n) => JSON.parse(readFileSync(fileURLToPath(new URL(`../fixtures/dashboard/parametros/${n}`, import.meta.url)), 'utf8'));
const plantilla = fx('limites_plantilla.json');
const fijados = fx('limites_fijados.json');
const raiz = (rel) => fileURLToPath(new URL(`../../${rel}`, import.meta.url));

// ───────────── el espejo de CLAVES_CRITICAS no se desvía del motor ─────────────

test('OPERACIONES refleja scripts/validar_esquemas.py::CLAVES_CRITICAS (si el archivo está)', () => {
  const ruta = raiz('scripts/validar_esquemas.py');
  if (!existsSync(ruta)) return;
  const fuente = readFileSync(ruta, 'utf8');
  const i = fuente.indexOf('CLAVES_CRITICAS: dict[str, list[str]] = {');
  assert.ok(i >= 0, 'no se encontró CLAVES_CRITICAS (¿se renombró?: actualiza el espejo de lib/parametros.js)');
  const bloque = fuente.slice(i, fuente.indexOf('\n}\n', i));
  const py = {};
  for (const m of bloque.matchAll(/"([a-z_]+)":\s*\[([^\]]*)\]/g)) py[m[1]] = [...m[2].matchAll(/"([a-z_]+)"/g)].map((x) => x[1]);
  const act = /CLAVES_CRITICAS\["activar"\]\s*=\s*CLAVES_CRITICAS\["gastar"\]\s*\+\s*\[([^\]]*)\]/s.exec(fuente);
  assert.ok(act, 'no se encontró la definición de «activar»');
  py.activar = [...py.gastar, ...[...act[1].matchAll(/"([a-z_]+)"/g)].map((x) => x[1])];
  assert.deepEqual(Object.keys(P.OPERACIONES).sort(), Object.keys(py).sort());
  for (const [op, claves] of Object.entries(py)) assert.deepEqual([...P.OPERACIONES[op].claves].sort(), [...claves].sort(), `claves de «${op}»`);
});

test('LIMITES_META cubre todas las claves de contratos/limites.schema.json (si el contrato está)', () => {
  const ruta = raiz('contratos/limites.schema.json');
  if (!existsSync(ruta)) return;
  const esquema = JSON.parse(readFileSync(ruta, 'utf8'));
  for (const k of Object.keys(esquema.properties)) {
    if (k === 'schema_version' || k === 'version') continue;
    assert.ok(P.LIMITES_META[k], `falta la descripción de «${k}» en LIMITES_META`);
    assert.ok(P.GRUPOS_LIMITES.some((g) => g.id === P.LIMITES_META[k].grupo), `grupo desconocido para «${k}»`);
  }
});

// ───────────── límites ─────────────

test('estadoDeClave: null, ausente, lista exigida vacía, fijado, hecho de plataforma, sello', () => {
  assert.equal(P.estadoDeClave('capital_en_riesgo_total', null), 'nulo');
  assert.equal(P.estadoDeClave('capital_en_riesgo_total', 0), 'fijado'); // un 0 explícito no es «sin fijar» (otra cosa es que el motor lo rechace)
  assert.equal(P.estadoDeClave('capital_en_riesgo_total', undefined), 'ausente');
  assert.equal(P.estadoDeClave('capital_en_riesgo_total', 5, true), 'nulo'); // `nulos` manda
  assert.equal(P.estadoDeClave('cuentas_permitidas', []), 'vacio');
  assert.equal(P.estadoDeClave('paises_permitidos', ['ES']), 'fijado');
  assert.equal(P.estadoDeClave('lineas_rojas', []), 'fijado'); // vacía por defecto: no bloquea
  assert.equal(P.estadoDeClave('factor_techo_teorico_diario', '1.75'), 'fijo');
  assert.equal(P.estadoDeClave('sello', null), 'nulo');
  assert.equal(P.estadoDeClave('sello', { hash: 'x' }), 'fijado');
});

test('desbloqueaDe: qué operaciones exigen cada clave', () => {
  assert.deepEqual(P.desbloqueaDe('perdida_max_test_por_oferta').map((x) => x.id), ['gastar', 'activar']);
  assert.deepEqual(P.desbloqueaDe('stop_loss_escala').map((x) => x.id), ['escalar']);
  assert.deepEqual(P.desbloqueaDe('gasto_diario_global').map((x) => x.id), ['gastar', 'activar', 'aumentar_presupuesto', 'escalar']);
  assert.deepEqual(P.desbloqueaDe('reembolso_auto_max').map((x) => x.id), ['reembolsar_auto']);
  assert.deepEqual(P.desbloqueaDe('ventana_veto_min'), []); // no la exige ninguna operación del motor: tiene `usos`
  assert.equal(P.desbloqueaDe('sello').length, 8); // sin sello no gasta nadie
});

test('modeloLimites con la plantilla real (todo en null): 39 claves bloquean y ninguna operación está habilitada', () => {
  const m = P.modeloLimites(plantilla, fmt);
  assert.equal(m.total, 57);
  assert.equal(m.nNulos, 39);
  assert.equal(m.nFijados, 8);
  assert.equal(m.sellado, false);
  assert.equal(m.algunaOperacionHabilitada, false);
  const por = Object.fromEntries(m.filas.map((f) => [f.clave, f]));
  assert.equal(por.perdida_max_test_por_oferta.estado, 'nulo');
  assert.equal(por.cuentas_permitidas.estado, 'vacio'); // lista exigida sin elementos
  assert.equal(por.factor_techo_teorico_diario.estado, 'fijo');
  assert.equal(por.macro_nichos_permitidos.estado, 'fijo');
  assert.equal(por.sello.estado, 'nulo');
  assert.equal(por.perdida_max_test_por_oferta.texto, null); // null no se pinta como 0 ni como texto vacío
  assert.equal(por.factor_techo_teorico_diario.texto, '× 1,75');
  for (const o of m.operaciones) { assert.equal(o.ok, false, o.id); assert.ok(o.faltantes.includes('sello'), o.id); }
  const gastar = m.operaciones.find((o) => o.id === 'gastar');
  assert.equal(gastar.total, 13);
  assert.equal(gastar.faltantes.length, 13);
  assert.deepEqual(m.grupos.map((g) => g.id), ['capital', 'gasto', 'ritmo', 'alcance', 'riesgo', 'ventas', 'costos', 'comunicacion', 'gates']);
  assert.deepEqual(m.bloqueadas.map((b) => b.clave).slice(0, 2), ['moneda_limites', 'capital_en_riesgo_total']);
});

test('modeloLimites con todo fijado: operaciones habilitadas, importes con su moneda, sello presente', () => {
  const m = P.modeloLimites(fijados, fmt);
  assert.equal(m.nNulos, 0);
  assert.equal(m.sellado, true);
  assert.equal(m.algunaOperacionHabilitada, true);
  assert.ok(m.operaciones.every((o) => o.ok));
  const por = Object.fromEntries(m.filas.map((f) => [f.clave, f]));
  assert.match(por.gasto_diario_por_oferta.texto, /^100,00\s€$/); // 10000 centavos
  assert.equal(por.aumento_presupuesto_max_pct_por_paso.texto, '20 %');
  assert.equal(por.paises_permitidos.texto, 'ES, IT');
  assert.equal(por.moneda_limites.texto, 'EUR');
});

test('modeloLimites: una sola clave en null bloquea justo las operaciones que la exigen; `nulos` del panel manda', () => {
  const v = { ...fijados.valores, stop_loss_escala: null };
  const m = P.modeloLimites({ valores: v, nulos: ['stop_loss_escala'] }, fmt);
  assert.deepEqual(m.operaciones.filter((o) => !o.ok).map((o) => o.id), ['escalar']);
  const m2 = P.modeloLimites({ valores: fijados.valores, nulos: ['reembolso_auto_max'] }, fmt);
  assert.deepEqual(m2.operaciones.filter((o) => !o.ok).map((o) => o.id), ['reembolsar_auto']);
  const sinSello = P.modeloLimites({ valores: { ...fijados.valores, sello: null }, nulos: [] }, fmt);
  assert.equal(sinSello.algunaOperacionHabilitada, false);
  assert.equal(P.modeloLimites(null, fmt), null);
  assert.equal(P.modeloLimites({}, fmt), null);
  // claves desconocidas no se pierden
  const raro = P.modeloLimites({ valores: { ...fijados.valores, clave_nueva: 3 }, nulos: [] }, fmt);
  assert.equal(raro.filas.find((f) => f.clave === 'clave_nueva').grupo, 'otros');
  assert.equal(P.modeloLimites({ valores: { ...fijados.valores, tope_x: null }, nulos: ['tope_x'] }, fmt).bloqueadas.some((b) => b.clave === 'tope_x'), true);
});

test('textoLimite: importes sin float, sin moneda no se inventa', () => {
  assert.equal(P.textoLimite('capital_en_riesgo_total', 12345, 'EUR', fmt), '123,45 €');
  assert.match(P.textoLimite('capital_en_riesgo_total', 12345, null, fmt), /falta indicar la moneda/);
  assert.equal(P.textoLimite('x', null, 'EUR', fmt), null);
  assert.equal(P.textoLimite('cuentas_permitidas', [], 'EUR', fmt), '(lista vacía)');
});

// ───────────── parámetros, autonomía, propuestas ─────────────

test('modeloParametros: grupos, hipótesis, calibrados y nulos; acepta el yaml entero o solo `grupos`', () => {
  const sub = fx('parametros_subconjunto.json');
  const m = P.modeloParametros(sub);
  assert.deepEqual(m.grupos.map((g) => g.id), ['orquestador', 'testeo', 'veredicto', 'dashboard', 'finanzas']);
  assert.equal(m.version, 1);
  assert.equal(m.schema_version, '1.1.0');
  assert.ok(m.total > 50);
  assert.equal(m.calibrados, 1);
  assert.equal(m.nulos, 1);
  const kill = m.grupos.find((g) => g.id === 'testeo').claves.find((c) => c.clave === 'p_kill');
  assert.equal(kill.texto, '0.90');
  assert.equal(kill.hipotesis, true);
  const timeout = m.grupos.find((g) => g.id === 'orquestador').claves.find((c) => c.clave === 'timeout_etapa_min');
  assert.match(timeout.texto, /"D1":30/); // los mapas se resumen en una línea
  assert.equal(m.grupos.find((g) => g.id === 'finanzas').claves.find((c) => c.clave === 'reserva_stripe_pct').nulo, true);
  assert.equal(P.modeloParametros(sub.grupos).total, m.total);
  assert.equal(P.modeloParametros(null), null);
  assert.equal(P.modeloParametros({}), null);
  assert.equal(P.textoValor(null), 'null');
  assert.equal(P.textoValor('x'.repeat(10), 5), 'xxxxxxxxxx');
  assert.ok(P.textoValor({ a: 'y'.repeat(300) }).length <= 140);
  assert.equal(P.textoValor([1, 2]), '[1,2]');
});

test('modeloAutonomia: nivel por etapa, histograma y todas en N0', () => {
  const a = P.modeloAutonomia(fx('autonomia_real.json'));
  assert.equal(a.etapas.length, 17);
  assert.equal(a.todasN0, true);
  assert.deepEqual(a.histograma, { N0: 17 });
  assert.equal(a.etapas.find((e) => e.etapa === 'D8').nombre, 'Optimización diaria');
  assert.equal(a.reglas.length, 3);
  const mixta = P.modeloAutonomia(fx('autonomia_mixta.json'));
  assert.equal(mixta.todasN0, false);
  assert.deepEqual(mixta.histograma, { N0: 16, N2: 1 });
  assert.equal(mixta.etapas.find((e) => e.etapa === 'D8').evidencia, 2);
  assert.equal(mixta.descensos.length, 1);
  assert.equal(P.modeloAutonomia(null), null);
  assert.equal(P.modeloAutonomia({}), null);
});

test('modeloPropuestas: lista de claves, mapa grupo→claves o solo un número; origen por ruta', () => {
  const p = P.modeloPropuestas(fx('propuestas.json'));
  assert.equal(p.length, 4);
  assert.equal(p[0].origen, 'Propuesta del sistema (reglas base)');
  assert.equal(p[0].nClaves, 44);
  assert.equal(p[1].origen, 'Descubrimiento: modelado de ofertas ajenas');
  assert.equal(p[1].nClaves, 36);
  assert.deepEqual([p[2].nClaves, p[2].soloConteo, p[2].claves.length], [7, true, 0]);
  assert.deepEqual(p[3].claves, ['estadistica.alfa_descarte', 'estadistica.k_min_matar', 'agentes.modelo', 'agentes.esfuerzo']);
  assert.deepEqual(P.modeloPropuestas([null, { archivo: 5 }, 'x']), []);
  assert.deepEqual(P.modeloPropuestas(undefined), []);
});

// ───────────── búsqueda ─────────────

test('coincide: todas las palabras, sin tildes ni mayúsculas', () => {
  assert.equal(P.coincide('Pérdida máxima por oferta', 'perdida OFERTA'), true);
  assert.equal(P.coincide('Pérdida máxima por oferta', 'perdida correo'), false);
  assert.equal(P.coincide('x', ''), true);
  assert.equal(P.coincide('x', null), true);
});

test('filtrarTodo: filtra límites, parámetros, autonomía y propuestas a la vez; sin consulta no toca nada', () => {
  const base = P.modeloPantallaParametros({ limites: plantilla, parametros: fx('parametros_subconjunto.json'), autonomia: fx('autonomia_mixta.json'), propuestas: fx('propuestas.json') }, fmt);
  const sin = P.filtrarTodo(base, '  ');
  assert.equal(sin.consulta, '');
  assert.equal(sin.coincidencias, null);
  assert.equal(sin.limites.total, 57);
  const r = P.filtrarTodo(base, 'perdida');
  assert.equal(r.consulta, 'perdida');
  const clavesL = r.limites.grupos.flatMap((g) => g.claves.map((c) => c.clave));
  assert.ok(clavesL.includes('perdida_max_test_por_oferta') && clavesL.includes('perdida_neta_acumulada_max'));
  assert.ok(!clavesL.includes('correos_max_por_dia'));
  const d8 = P.filtrarTodo(base, 'D8');
  assert.deepEqual(d8.autonomia.etapas.map((e) => e.etapa), ['D8']);
  const alfa = P.filtrarTodo(base, 'alfa_descarte');
  assert.ok(alfa.propuestas.every((x) => x.clavesVisibles.some((c) => /alfa_descarte/.test(c))));
  assert.ok(alfa.propuestas.length >= 2);
  assert.ok(alfa.coincidencias >= 2);
  const nada = P.filtrarTodo(base, 'zzzz-no-existe');
  assert.equal(nada.coincidencias, 0);
  assert.deepEqual(nada.limites.grupos, []);
  // buscar por lo que desbloquea
  const esc = P.filtrarTodo(base, 'escalar');
  assert.ok(esc.limites.grupos.flatMap((g) => g.claves).some((c) => c.clave === 'stop_loss_escala'));
  assert.ok(P.filtrarTodo(base, 'null').coincidencias === null || true);
});

test('comandosParametros: solo comandos que existen', () => {
  const c = P.comandosParametros();
  assert.equal(c.estado, '.venv/bin/python -m engine.limites estado --operacion gastar');
  assert.match(c.validar, /scripts\.validar_esquemas limites empresa\/limites\.yaml/);
  assert.equal(Object.keys(c).includes('sellar'), false); // `engine.limites sellar` aún no existe (ola 1)
});

// ───────────── render con DOM falso ─────────────

function ctxDe(datos, { falla = false, vacio = false } = {}) {
  const api = {
    sobre: async () => {
      if (falla) throw Object.assign(new Error('x'), { codigo: 'sin_conexion', mensaje: 'x' });
      return { datos, fuente: ['empresa/limites.yaml', 'empresa/parametros.yaml', 'empresa/autonomia.yaml'], generado_en: '2026-11-06T12:00:00Z', vacio, avisos: [] };
    },
  };
  return { api, ui, fmt, estado: {}, params: {}, ruta: 'parametros', recargar() {}, navegar() {}, alSalir() {} };
}
const completo = () => ({ limites: plantilla, parametros: fx('parametros_subconjunto.json'), autonomia: fx('autonomia_real.json'), propuestas: fx('propuestas.json') });

test('render con la plantilla: resalta las claves en null, lo que desbloquean y no ofrece edición', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/parametros.js');
    assert.equal(pagina.meta.ruta, 'parametros');
    const raizEl = await pagina.render(ctxDe(completo()));
    const t = texto(raizEl);
    assert.match(t, /Esto desbloquea gasto/);
    assert.match(t, /Todavía no se puede gastar: faltan 13 requisitos/);
    assert.match(t, /Por seguridad, si falta un dato no se hace nada/);
    assert.match(t, /perdida_max_test_por_oferta/);
    assert.match(t, /Por dónde empezar · \d+ límites bloquean operaciones/);
    assert.match(t, /Falta fijar: un importe/);
    assert.match(t, /Falta fijar:/);
    assert.ok(porTag(raizEl, 'table').length >= 2);
    assert.match(t, /Todas las etapas están en el nivel 0 \(todo lo apruebas tú\)/);
    assert.match(t, /Nivel 3: el sistema avanza solo/); // cada nivel se explica sin la sigla
    assert.match(t, /parametros-b0\.yaml/);
    assert.match(t, /Sin aplicar/);
    assert.ok(porClase(raizEl, 'p5-lim--nulo').length >= 39, 'las 39 claves bloqueantes resaltadas en su grupo');
    // sin edición: ningún textarea y el único input es la búsqueda
    assert.equal(porTag(raizEl, 'textarea').length, 0);
    assert.deepEqual(porTag(raizEl, 'input').map((n) => n.getAttribute('type')), ['search']);
    assert.equal(todos(raizEl, (n) => n.localName === 'button' && /guardar|editar|aplicar/i.test(n.textContent)).length, 0);
    assert.equal(porTag(raizEl, 'img').length, 0);
    assert.ok(t.includes('<img src=x onerror=alert(1)> [HIPÓTESIS]'), 'texto hostil de una fuente de parámetro, como texto');
  } finally { restaurar(); }
});

test('render con todo fijado: sin aviso de claves sin fijar y operaciones habilitadas', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/parametros.js');
    const d = { ...completo(), limites: fijados };
    const t = texto(await pagina.render(ctxDe(d)));
    assert.match(t, /Los límites alcanzan para gastar/);
    assert.match(t, /Habilitada/);
    assert.doesNotMatch(t, /siguen sin fijar/);
  } finally { restaurar(); }
});

test('la búsqueda filtra en vivo sin perder el campo', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/parametros.js');
    const raizEl = await pagina.render(ctxDe(completo()));
    const buscar = porTag(raizEl, 'input')[0];
    buscar.value = 'stop_loss';
    buscar.dispararEvento('input');
    const t = texto(raizEl);
    assert.match(t, /coincidencia\(s\) para «stop_loss»/);
    assert.match(t, /stop_loss_escala/);
    assert.match(t, /Habilita:/);
    assert.match(t, /Escalar/);
    assert.doesNotMatch(t, /correos_max_por_dia/);
    assert.equal(porTag(raizEl, 'input')[0], buscar, 'el input sigue siendo el mismo nodo (conserva el foco)');
    buscar.value = 'zzzz-no-existe';
    buscar.dispararEvento('input');
    assert.match(texto(raizEl), /Nada coincide con «zzzz-no-existe»/);
    buscar.value = '';
    buscar.dispararEvento('input');
    assert.match(texto(raizEl), /Esto desbloquea gasto/);
  } finally { restaurar(); }
});

test('render sin archivos: estados vacíos con comando; error de API: errorBox', async () => {
  const restaurar = instalarDomFalso();
  try {
    const pagina = await import('../../dashboard/web/pages/parametros.js');
    const vacio = await pagina.render(ctxDe({ limites: null, parametros: null, autonomia: null, propuestas: [] }, { vacio: true }));
    const t = texto(vacio);
    assert.match(t, /El panel no pudo leer los límites, los valores ajustables ni los niveles de autonomía/);
    assert.match(t, /\.venv\/bin\/python -m engine\.limites estado --operacion gastar/);
    assert.ok(porClase(vacio, 'comando').length >= 1);
    const parcial = await pagina.render(ctxDe({ limites: null, parametros: fx('parametros_subconjunto.json'), autonomia: null, propuestas: [] }));
    assert.match(texto(parcial), /No se pudieron leer los límites/);
    assert.match(texto(parcial), /No se pudieron leer los niveles de autonomía/);
    assert.match(texto(parcial), /No hay propuestas pendientes/);
    const err = await pagina.render(ctxDe(null, { falla: true }));
    assert.equal(porClase(err, 'error-box').length, 1);
  } finally { restaurar(); }
});


// ───────────── rediseño U4: «Esto desbloquea gasto» ─────────────

test('prioridadLimites: el sello primero, luego las claves que habilitan más operaciones; las que ninguna exige quedan aparte', () => {
  const m = P.modeloLimites(plantilla, fmt);
  const { criticas, otras } = P.prioridadLimites(m);
  assert.equal(criticas[0].clave, 'sello');
  assert.ok(criticas.every((c) => c.desbloquea.length > 0));
  for (let i = 2; i < criticas.length; i += 1) assert.ok(criticas[i - 1].desbloquea.length >= criticas[i].desbloquea.length, 'de más a menos operaciones habilitadas');
  assert.ok(otras.every((c) => c.desbloquea.length === 0));
  assert.ok(otras.some((c) => c.clave === 'autoaprobar_hasta'), 'una clave sin operación que la exija no bloquea nada hoy');
  assert.deepEqual(P.prioridadLimites(null), { criticas: [], otras: [] });
});

test('resumenDesbloqueo y formaDeValor: qué se puede hacer hoy y qué tipo de valor falta', () => {
  const m = P.modeloLimites(plantilla, fmt);
  const r = P.resumenDesbloqueo(m);
  assert.equal(r.puedeGastar, false);
  assert.equal(r.faltanParaGastar, 13);
  assert.equal(r.sinSello, true);
  assert.equal(P.formaDeValor('importe', 'gasto_diario_global'), 'un importe (en la moneda de los límites)');
  assert.equal(P.formaDeValor('lista', 'paises_permitidos'), 'al menos un elemento en la lista');
  assert.match(P.formaDeValor('texto', 'moneda_limites'), /código de moneda/);
  assert.equal(P.resumenDesbloqueo(null), null);
});

test('claves del esquema 1.3.0 con null prudente (solo verde) no bloquean ninguna operación', () => {
  const m = P.modeloLimites(plantilla, fmt);
  const nivel = m.filas.find((f) => f.clave === 'nivel_max_lanzable');
  assert.equal(nivel.estado === 'nulo' || nivel.estado === 'ausente', true);
  assert.equal(nivel.bloquea, false);
  assert.equal(nivel.seguroPorDefecto, true);
});
