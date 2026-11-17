// Pruebas de la lógica pura de #/campanas (dashboard/web/lib/campanas.js) con fixtures propios (copias de ofertas/_ejemplo).
// Sin DOM, sin red, sin tocar ofertas/ ni empresa/ reales:  node --test tests/dashboard/test_web_campanas.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import * as C from '../../dashboard/web/lib/campanas.js';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const FX = path.join(AQUI, '..', 'fixtures', 'dashboard', 'campanas');
const json = (n) => JSON.parse(readFileSync(path.join(FX, n), 'utf8'));
const clon = (o) => JSON.parse(JSON.stringify(o));

const campana = json('campana.json');
const verde = json('preflight_verde.json');
const mixto = json('preflight_mixto.json');
const ids = json('ids_meta.json');
const aprobacion = json('aprobacion.json');
const HASH = campana.hash_config;
// «ahora» fijo para las pruebas: dentro de la vigencia (generado 2026-11-10T09:00Z, vence 2026-11-11T09:00Z)
const DENTRO = Date.parse('2026-11-10T12:00:00Z');
const FUERA = Date.parse('2026-11-12T00:00:00Z');

// ───────────── catálogo P01–P25 ─────────────

test('catálogo del preflight: P01–P24 y P25 condicional', () => {
  assert.equal(C.PREFLIGHT.length, 25);
  assert.deepEqual(C.PREFLIGHT.slice(0, 24).map((p) => p.id), Array.from({ length: 24 }, (_, i) => `P${String(i + 1).padStart(2, '0')}`));
  assert.equal(C.PREFLIGHT[24].id, 'P25');
  assert.equal(C.PREFLIGHT[24].condicional, true);
  assert.ok(C.PREFLIGHT.every((p) => p.titulo.length > 5));
  assert.deepEqual(C.TONO_SEMAFORO, { VERDE: 'ok', AMARILLO: 'aviso', ROJO: 'error', NO_APLICA: 'neutro' });
});

// ───────────── hashes y URL ─────────────

test('hashCorto abrevia solo hashes válidos', () => {
  assert.equal(C.hashCorto(HASH), 'sha256:2be24a1d…57ed');
  assert.equal(C.hashCorto('xyz'), 'xyz');
  assert.equal(C.hashCorto(null), '');
  assert.ok(!C.hashCorto('sha256:' + 'a'.repeat(300)).includes('a'.repeat(100)));
});

test('trozosUrlMacros separa las macros del resto (todo sigue siendo texto)', () => {
  const t = C.trozosUrlMacros(campana.url.plantilla);
  const macros = t.filter((x) => x.macro).map((x) => x.texto);
  assert.deepEqual(macros, ['{{campaign.name}}', '{{ad.name}}', '{{adset.name}}', '{{campaign.id}}', '{{adset.id}}', '{{ad.id}}']);
  assert.equal(t.map((x) => x.texto).join(''), campana.url.plantilla, 'sin pérdida de texto');
  assert.deepEqual(C.trozosUrlMacros(''), []);
  assert.deepEqual(C.trozosUrlMacros(null), []);
  const hostil = C.trozosUrlMacros('https://x.example/?a={{<script>}}&b=‮{{ad.id}}');
  assert.ok(hostil.every((x) => !/[‪-‮]/.test(x.texto)));
  assert.equal(hostil.filter((x) => x.macro).length, 1, 'una «macro» con < > no es macro');
});

test('revisarUrl: macros, ejemplo resuelto y https', () => {
  const r = C.revisarUrl(campana.url);
  assert.equal(r.macrosOk, true);
  assert.deepEqual(r.macrosFaltan, []);
  assert.equal(r.ejemploOk, true);
  assert.equal(r.https, true);
  const sin = C.revisarUrl({ plantilla: 'https://x.example/?utm_source=meta&adid={{ad.id}}', ejemplo_resuelto: 'https://x.example/?utm_source=meta&adid=' });
  assert.equal(sin.macrosOk, false);
  assert.ok(sin.macrosFaltan.includes('{{campaign.name}}'));
  assert.equal(sin.ejemploOk, false, 'adid vacío en el ejemplo');
  assert.equal(C.revisarUrl({ plantilla: 'http://x.example/', ejemplo_resuelto: 'http://x.example/?a={{ad.id}}' }).ejemploOk, false, 'quedó una macro sin resolver');
  assert.equal(C.revisarUrl({}).macrosOk, false);
  assert.equal(C.revisarUrl(null).ejemploOk, null);
  assert.equal(C.revisarUrl({ plantilla: 'http://x' }).https, false);
});

test('revisarNombres: ASCII, sin espacios ni «|»', () => {
  const r = C.revisarNombres(campana.nombres);
  assert.equal(r.ok, true);
  assert.equal(r.items.length, 2 + campana.nombres.anuncios.length);
  const malo = C.revisarNombres({ campana: 'Campaña con ñ', conjunto: 'a|b', anuncios: ['bien_1', 'con espacio', ''] });
  assert.equal(malo.ok, false);
  assert.deepEqual(malo.items.map((i) => i.ok), [false, false, true, false, false]);
  assert.equal(malo.items[4].motivo, 'vacío');
  assert.equal(C.revisarNombres(null).ok, false);
});

// ───────────── presupuesto ─────────────

test('modeloPresupuesto: unidad menor con moneda y decimales; comprobaciones con enteros', () => {
  const p = C.modeloPresupuesto(campana.presupuesto);
  assert.equal(p.diario, '27,60 €');
  assert.equal(p.total, '276,00 €');
  assert.equal(p.spendCap, '303,60 €');
  assert.equal(p.spendCapMinimo, '93,00 €');
  assert.equal(p.maxTeoricoDiario, '48,30 €');
  assert.equal(p.dias, 10);
  assert.ok(p.comprobaciones.every((c) => c.estado === 'ok'), JSON.stringify(p.comprobaciones));
  assert.ok(p.comprobaciones.some((c) => c.id === 'total'));
  assert.ok(p.comprobaciones.some((c) => c.id === 'capmin'));
});

test('modeloPresupuesto: total que no cuadra, spend_cap bajo y candado alternativo', () => {
  const a = clon(campana.presupuesto); a.total_test = 27000;
  assert.equal(C.modeloPresupuesto(a).comprobaciones.find((c) => c.id === 'total').estado, 'aviso');
  const b = clon(campana.presupuesto); b.spend_cap = 20000;
  const mb = C.modeloPresupuesto(b);
  assert.equal(mb.comprobaciones.find((c) => c.id === 'cap').estado, 'error');
  const c = clon(campana.presupuesto); c.spend_cap = null; c.candado_alternativo = null;
  const mc = C.modeloPresupuesto(c);
  assert.equal(mc.spendCap, 'sin tope');
  assert.equal(mc.comprobaciones.find((x) => x.id === 'cap').estado, 'error', 'sin spend_cap y sin candado: no hay tope en Meta');
  const d = clon(c); d.candado_alternativo = { tipo: 'stop_time', stop_time: '2026-11-20T00:00:00Z', lifetime_budget: 27600 };
  const md = C.modeloPresupuesto(d);
  assert.equal(md.comprobaciones.find((x) => x.id === 'cap').estado, 'ok');
  assert.ok(md.candado.length >= 2);
  assert.equal(C.modeloPresupuesto(null), null);
  assert.equal(C.modeloPresupuesto({}), null);
  const flot = C.modeloPresupuesto({ moneda: 'EUR', decimales: 2, diario: 27.6 });
  assert.equal(flot.diario, '—', 'un float no es dinero');
  const clp = C.modeloPresupuesto({ moneda: 'CLP', decimales: 0, diario: 25000, total_test: 250000, dias: 10 });
  assert.equal(clp.diario, '25.000 CLP');
});

// ───────────── campana.json ─────────────

test('modeloCampana: estructura, nombres, URL, anuncios, reglas y hash', () => {
  const m = C.modeloCampana(campana);
  assert.equal(m.oferta, 'OF-202611-01');
  assert.equal(m.estado, 'borrador');
  assert.equal(m.estructura, 'CBO');
  assert.equal(m.objetivo, 'VENTAS');
  assert.equal(m.evento, 'PURCHASE');
  assert.deepEqual(m.paises, ['ES']);
  assert.equal(m.nombres.campana, 'OF-202611-01_TEST_VENTAS_CBO_20261110');
  assert.equal(m.nombres.anuncios.length, 5);
  assert.equal(m.anuncios.length, 5);
  assert.equal(m.anuncios[0].claims.length, 2);
  assert.equal(m.economia.cpaMax, '18,30 €');
  assert.equal(m.economia.kCorte, 3);
  assert.equal(m.audiencia.edad, '28–55');
  assert.equal(m.audiencia.excluyeSensibles, true);
  assert.equal(m.reglasParada.pausaGlobalSi.length, 3);
  assert.equal(m.hashConfig, HASH);
  assert.equal(m.revisionNombres.ok, true);
  assert.equal(m.url.macrosOk, true);
  assert.deepEqual(m.specialAdCategories, []);
  assert.equal(m.idsMetaEnCampana, false);
  assert.equal(C.modeloCampana(null), null);
  assert.equal(C.modeloCampana({}), null);
  assert.equal(C.modeloCampana('texto'), null);
});

test('modeloCampana: texto hostil en nombres se neutraliza', () => {
  const c = clon(campana);
  c.nombres.campana = 'x‮y<script>';
  c.anuncios[0].ad_name = 'a‮b';
  const m = C.modeloCampana(c);
  assert.ok(m.nombres.campana.includes('⟦U+202E⟧'));
  assert.ok(!/[‪-‮]/.test(m.anuncios[0].nombre));
  assert.equal(m.revisionNombres.items[0].ok, false, 'un nombre con bidi o « < » en el original no es ASCII válido… ');
});

// ───────────── preflight ─────────────

test('modeloPreflight: todo VERDE y vigente habilita (para el hash actual)', () => {
  const p = C.modeloPreflight({ preflight: verde, campana, ahora: DENTRO });
  assert.equal(p.semaforo, 'VERDE');
  assert.equal(p.tono, 'ok');
  assert.equal(p.filas.length, 24, 'sin special_ad_categories no se exige P25');
  assert.equal(p.resumen.verde, 24);
  assert.equal(p.vigente, true);
  assert.equal(p.hashCoincide, true);
  assert.equal(p.habilita, true);
  assert.deepEqual(p.problemas, []);
  assert.equal(p.horasGenerado, 3);
});

test('modeloPreflight: un ROJO bloquea y cada ítem tiene su semáforo', () => {
  const p = C.modeloPreflight({ preflight: mixto, campana, ahora: DENTRO });
  assert.equal(p.semaforo, 'ROJO');
  assert.equal(p.habilita, false);
  const por = Object.fromEntries(p.filas.map((f) => [f.id, f]));
  assert.equal(por.P12.estado, 'ROJO');
  assert.equal(por.P12.tono, 'error');
  assert.equal(por.P05.tono, 'aviso');
  assert.equal(por.P22.estado, 'NO_APLICA');
  assert.equal(por.P22.tono, 'neutro');
  assert.equal(p.filas.length, 25, 'si el archivo trae P25 se muestra aunque no se exija');
  assert.equal(p.resumen.rojo, 1);
  assert.equal(p.resumen.amarillo, 2);
  assert.equal(p.resumen.noAplica, 2);
  assert.ok(por.P16.evidencia.includes('⟦U+202E⟧'), 'la evidencia es texto no confiable');
});

test('modeloPreflight: vencido, de otro hash, o con ítems sin dato NO habilita', () => {
  assert.equal(C.modeloPreflight({ preflight: verde, campana, ahora: FUERA }).vigente, false);
  assert.equal(C.modeloPreflight({ preflight: verde, campana, ahora: FUERA }).habilita, false);
  assert.ok(C.modeloPreflight({ preflight: verde, campana, ahora: FUERA }).problemas[0].includes('venció'));
  const otro = clon(campana); otro.hash_config = 'sha256:' + 'b'.repeat(64);
  const p2 = C.modeloPreflight({ preflight: verde, campana: otro, ahora: DENTRO });
  assert.equal(p2.hashCoincide, false);
  assert.equal(p2.habilita, false);
  assert.ok(p2.problemas.some((x) => x.includes('OTRA versión de la campaña')));
  const roto = clon(verde); delete roto.checks.P07; roto.checks.P08 = { estado: 'AZUL', evidencia: 'x' };
  const p3 = C.modeloPreflight({ preflight: roto, campana, ahora: DENTRO });
  assert.equal(p3.resumen.sinDato, 2);
  assert.equal(p3.habilita, false);
  assert.equal(p3.filas.find((f) => f.id === 'P07').estado, 'sin_dato');
  assert.equal(p3.filas.find((f) => f.id === 'P08').estado, 'sin_dato', 'un semáforo desconocido no es VERDE');
});

test('modeloPreflight: el semáforo declarado VERDE no se cree si hay ítems que no lo son', () => {
  const x = clon(mixto); x.semaforo = 'VERDE';
  const p = C.modeloPreflight({ preflight: x, campana, ahora: DENTRO });
  assert.equal(p.habilita, false);
  assert.ok(p.problemas.some((y) => y.includes('no se confía')));
});

test('modeloPreflight: P25 se exige si hay special_ad_categories; sin preflight devuelve null', () => {
  const conCats = clon(campana); conCats.special_ad_categories = ['EMPLOYMENT'];
  const p = C.modeloPreflight({ preflight: verde, campana: conCats, ahora: DENTRO });
  assert.equal(p.filas.length, 25);
  assert.equal(p.filas.find((f) => f.id === 'P25').estado, 'sin_dato');
  assert.equal(p.habilita, false, 'P25 faltante bloquea');
  assert.equal(C.modeloPreflight({ preflight: null, campana }), null);
  assert.equal(C.modeloPreflight({}), null);
  assert.equal(C.modeloPreflight({ preflight: {}, campana }), null);
  const sinFechas = clon(verde); delete sinFechas.valido_hasta;
  assert.equal(C.modeloPreflight({ preflight: sinFechas, campana, ahora: DENTRO }).vigente, null);
  assert.equal(C.modeloPreflight({ preflight: sinFechas, campana, ahora: DENTRO }).habilita, false, 'sin vigencia conocida no se habilita');
});

// ───────────── ids de Meta ─────────────

test('modeloIdsMeta y objectIdsDe: campaña + conjuntos + anuncios (no creativos)', () => {
  const m = C.modeloIdsMeta(ids, campana);
  assert.equal(m.cuenta, 'act_900000000000001');
  assert.equal(m.campaignId, '120000000000001');
  assert.equal(m.adsetIds.length, 1);
  assert.equal(m.adIds.length, 5);
  assert.equal(m.creativeIds.length, 5);
  assert.equal(m.hashCoincide, true);
  assert.equal(m.objetosActivables, 7);
  const s = C.objectIdsDe(ids);
  assert.equal(s.size, 7);
  assert.ok(!s.has('120000000000013'), 'los creativos no se activan');
  const otro = clon(ids); otro.hash_config = 'sha256:' + 'c'.repeat(64);
  assert.equal(C.modeloIdsMeta(otro, campana).hashCoincide, false);
  assert.equal(C.modeloIdsMeta(null, campana), null);
  assert.equal(C.modeloIdsMeta({}, campana), null);
  assert.equal(C.objectIdsDe(null).size, 0);
});

// ───────────── aprobación y firma ─────────────

test('modeloAprobacion: vigente, mismo hash y mismos object_ids es válida', () => {
  const a = C.modeloAprobacion({ aprobacion, campana, idsMeta: ids, ahora: DENTRO });
  assert.equal(a.valida, true);
  assert.equal(a.hashCoincide, true);
  assert.equal(a.idsCoinciden, true);
  assert.equal(a.vigente, true);
  assert.equal(a.aprobadoPor.tipo, 'humano');
  assert.equal(a.aprobadoPor.firmada, true);
  assert.ok(a.aprobadoPor.firmaCorta.endsWith('…'));
  assert.ok(a.aprobadoPor.firmaCorta.length < 30, 'la firma no se vuelca entera');
  assert.deepEqual(a.problemas, []);
  assert.equal(a.objectIds.length, 7);
});

test('modeloAprobacion: vencida, otro hash, ids distintos, sin firma humana → no es válida', () => {
  assert.equal(C.modeloAprobacion({ aprobacion, campana, idsMeta: ids, ahora: FUERA }).valida, false);
  assert.ok(C.modeloAprobacion({ aprobacion, campana, idsMeta: ids, ahora: FUERA }).problemas.some((x) => x.includes('venció')));
  const otroHash = clon(aprobacion); otroHash.hash_objetivo = 'sha256:' + 'd'.repeat(64);
  const a2 = C.modeloAprobacion({ aprobacion: otroHash, campana, idsMeta: ids, ahora: DENTRO });
  assert.equal(a2.valida, false);
  assert.equal(a2.hashCoincide, false);
  const extra = clon(aprobacion); extra.object_ids.push('999999999999');
  const a3 = C.modeloAprobacion({ aprobacion: extra, campana, idsMeta: ids, ahora: DENTRO });
  assert.equal(a3.idsCoinciden, false);
  assert.equal(a3.valida, false);
  const regla = clon(aprobacion); regla.aprobado_por.tipo = 'regla';
  assert.equal(C.modeloAprobacion({ aprobacion: regla, campana, idsMeta: ids, ahora: DENTRO }).valida, false, 'gate H sin humano');
  const sinFirma = clon(aprobacion); sinFirma.aprobado_por.firma = null;
  const a5 = C.modeloAprobacion({ aprobacion: sinFirma, campana, idsMeta: ids, ahora: DENTRO });
  assert.equal(a5.valida, false);
  assert.equal(a5.aprobadoPor.firmada, false);
  assert.equal(C.modeloAprobacion({ aprobacion: null, campana }), null);
  assert.equal(C.modeloAprobacion({}), null);
});

test('comandoFirmar usa el id REAL de la oferta, no el de la carpeta demo', () => {
  assert.equal(C.comandoFirmar('_ejemplo'), null);
  const m = C.modeloCampanas({ campana }, { ofertaId: '_ejemplo', ahora: DENTRO });
  assert.equal(m.firma.comando, '.venv/bin/python -m engine.orq firmar --oferta OF-202611-01 --accion activar_campana --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno');
  assert.equal(C.comandoPreflight('_ejemplo'), '.venv/bin/python -m meta.preflight --oferta _ejemplo');
});

test('comandoFirmar / comandoPreflight: solo con un id de oferta válido', () => {
  assert.equal(C.comandoFirmar('OF-202611-01'), '.venv/bin/python -m engine.orq firmar --oferta OF-202611-01 --accion activar_campana --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno');
  assert.equal(C.comandoPreflight('OF-202611-01'), '.venv/bin/python -m meta.preflight --oferta OF-202611-01');
  for (const malo of ['OF-202611-01; rm -rf /', '../x', 'OF-1', '', null, undefined, 'OF-202611-01 --live']) {
    assert.equal(C.comandoFirmar(malo), null, String(malo));
    assert.equal(C.comandoPreflight(malo), null, String(malo));
  }
});

// ───────────── ciclo ─────────────

test('modeloCiclo: borrador → preflight_ok → aprobada → activa', () => {
  const c = C.modeloCiclo('preflight_ok');
  assert.deepEqual(c.pasos.map((p) => p.estado), ['hecho', 'actual', 'pendiente', 'pendiente']);
  assert.equal(c.conocido, true);
  assert.deepEqual(C.modeloCiclo('activa').pasos.map((p) => p.estado), ['hecho', 'hecho', 'hecho', 'actual']);
  assert.deepEqual(C.modeloCiclo('borrador').pasos.map((p) => p.estado), ['actual', 'pendiente', 'pendiente', 'pendiente']);
  const p = C.modeloCiclo('pausada');
  assert.equal(p.fueraDeCiclo, 'pausada');
  assert.equal(p.conocido, true);
  assert.ok(p.pasos.every((x) => x.estado === 'pendiente'));
  const raro = C.modeloCiclo('inventado');
  assert.equal(raro.conocido, false);
  assert.equal(C.modeloCiclo(null).conocido, false);
});

// ───────────── modelo completo ─────────────

test('modeloCampanas: borrador sin ids ni preflight ni aprobación → firma pendiente y bloqueos claros', () => {
  const m = C.modeloCampanas({ campana, preflight: null, ids_meta: null, aprobacion: null, estado: 'borrador' }, { ofertaId: 'OF-202611-01', ahora: DENTRO });
  assert.equal(m.hayCampana, true);
  assert.equal(m.ciclo.actual, 'borrador');
  assert.equal(m.preflight, null);
  assert.equal(m.idsMeta, null);
  assert.equal(m.aprobacion, null);
  assert.equal(m.firma.pendiente, true);
  assert.equal(m.firma.comando, '.venv/bin/python -m engine.orq firmar --oferta OF-202611-01 --accion activar_campana --hash-objetivo <HUELLA_DE_LO_QUE_FIRMAS> --clave-privada <RUTA_A_TU_CLAVE> --como dueno');
  assert.equal(m.firma.hashObjetivo, HASH);
  assert.deepEqual(m.firma.objectIds, []);
  assert.ok(m.paso.bloqueos.some((b) => b.includes('borrador en Meta')));
  assert.ok(m.paso.bloqueos.some((b) => b.includes('chequeo')));
  assert.ok(m.paso.bloqueos.some((b) => b.includes('aprobación')));
  assert.ok(m.paso.texto.includes('borrador'));
  assert.equal(m.paso.tono, 'aviso');
  assert.ok(m.firma.nota.includes('no firma'));
});

test('modeloCampanas: todo en regla → aprobación vigente y la activación la hace meta.activar, no el panel', () => {
  const datos = { campana: { ...campana, estado: 'aprobada' }, preflight: verde, ids_meta: ids, aprobacion, estado: 'aprobada' };
  const m = C.modeloCampanas(datos, { ofertaId: 'OF-202611-01', ahora: DENTRO });
  assert.equal(m.preflight.habilita, true);
  assert.equal(m.aprobacion.valida, true);
  assert.equal(m.firma.pendiente, false);
  assert.deepEqual(m.paso.bloqueos, []);
  assert.equal(m.paso.tono, 'ok');
  assert.ok(m.paso.texto.includes('sistema automático'));
  assert.equal(m.firma.objectIds.length, 7);
  assert.deepEqual(m.ciclo.pasos.map((p) => p.estado), ['hecho', 'hecho', 'actual', 'pendiente']);
});

test('modeloCampanas: preflight verde sin firma → «Siguiente (tuyo): firmar»', () => {
  const m = C.modeloCampanas({ campana, preflight: verde, ids_meta: ids, aprobacion: null, estado: 'preflight_ok' }, { ofertaId: 'OF-202611-01', ahora: DENTRO });
  assert.ok(m.paso.texto.includes('firmar'));
  assert.equal(m.firma.pendiente, true);
});

test('modeloCampanas: activa/pausada/cerrada no piden firma', () => {
  for (const est of ['activa', 'pausada', 'cerrada']) {
    const m = C.modeloCampanas({ campana: { ...campana, estado: est }, preflight: verde, ids_meta: ids, aprobacion, estado: est }, { ofertaId: 'OF-202611-01', ahora: DENTRO });
    assert.equal(m.firma.pendiente, false, est);
  }
});

test('modeloCampanas: sin campaña explica qué falta; ids_meta puede venir dentro de campana', () => {
  const v = C.modeloCampanas({ campana: null, preflight: null, ids_meta: null, aprobacion: null, estado: null }, { ofertaId: 'OF-202611-01' });
  assert.equal(v.hayCampana, false);
  assert.equal(v.firma.pendiente, false, 'sin campaña no hay nada que firmar');
  assert.ok(v.paso.texto.includes('Todavía no hay campaña'));
  assert.equal(C.modeloCampanas(null).hayCampana, false);
  assert.equal(C.modeloCampanas('x').hayCampana, false);
  const dentro = C.modeloCampanas({ campana: { ...campana, ids_meta: { ad_account_id: 'act_900000000000001', campaign_id: '120000000000001', adset_ids: ['120000000000002'], ad_ids: ['120000000000003'] } } }, { ofertaId: 'OF-202611-01', ahora: DENTRO });
  assert.equal(dentro.idsMeta.campaignId, '120000000000001');
});

test('modeloCampanas: el estado devuelto puede ser objeto y se avisa si contradice campana.json', () => {
  const m = C.modeloCampanas({ campana, estado: { estado: 'aprobada' } }, { ofertaId: 'OF-202611-01', ahora: DENTRO });
  assert.equal(m.ciclo.actual, 'aprobada');
  assert.equal(m.avisos.length, 1);
  assert.ok(m.avisos[0].includes('no coincide'));
  const sin = C.modeloCampanas({ campana, estado: null }, { ofertaId: 'OF-202611-01', ahora: DENTRO });
  assert.equal(sin.ciclo.actual, 'borrador', 'cae al estado de campana.json');
  assert.deepEqual(sin.avisos, []);
});

test('modeloCampanas: el estado del panel {etapa, gate_pendiente, campana, fase} se entiende', () => {
  const m = C.modeloCampanas({ campana, estado: { etapa: 'en_QA', gate_pendiente: true, campana: 'preflight_ok', fase: 'en_construccion' } }, { ofertaId: 'OF-202611-01', ahora: DENTRO });
  assert.equal(m.ciclo.actual, 'preflight_ok');
  assert.deepEqual(m.etapaD7, { estado: 'en_QA', gatePendiente: true, fase: 'en_construccion' });
  assert.equal(m.avisos.length, 1, 'campana.json dice «borrador» y el panel «preflight_ok»: se avisa');
  const sin = C.modeloCampanas({ campana, estado: { etapa: null, gate_pendiente: null, campana: null, fase: null } }, { ofertaId: 'OF-202611-01', ahora: DENTRO });
  assert.equal(sin.ciclo.actual, 'borrador');
  assert.deepEqual(sin.etapaD7, { estado: null, gatePendiente: null, fase: null });
  assert.equal(C.modeloCampanas({ campana, estado: 'borrador' }, { ahora: DENTRO }).etapaD7, null);
});

test('modeloCampanas: sin ofertaId usa el de campana.json y con uno inválido no arma comando', () => {
  assert.ok(C.modeloCampanas({ campana }, { ahora: DENTRO }).firma.comando.includes('OF-202611-01'));
  const mala = clon(campana); mala.oferta_id = 'OF-1; rm -rf /';
  assert.equal(C.modeloCampanas({ campana: mala }, { ahora: DENTRO }).firma.comando, null);
});

// ───────────── la página carga como módulo ─────────────

test('pages/campanas.js: meta, render, sin escritura ni activación', async () => {
  const ruta = path.join(AQUI, '..', '..', 'dashboard', 'web', 'pages', 'campanas.js');
  const mod = await import(ruta);
  assert.equal(mod.meta.ruta, 'campanas');
  assert.equal(mod.meta.grupo, 'Testeo y escala');
  assert.equal(typeof mod.render, 'function');
  assert.equal(typeof mod.alCambio, 'function');
  const fuente = readFileSync(ruta, 'utf8');
  assert.ok(!/innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function|srcdoc/.test(fuente));
  assert.ok(!/api\.post|\.post\(/.test(fuente), 'la página no hace POST');
  assert.ok(!/ads_activate|ads_create|activar_entity|--live/.test(fuente.replace(/\/\/.*$/gm, '')), 'ninguna llamada ni comando que active o gaste');
});

// ───────────── rediseño UX (U3): cuadrícula de semáforos por grupo, ciclo humano ─────────────

test('agruparPreflight: P01–P25 en siete grupos, cada punto una vez y con nombre humano', () => {
  const p = C.modeloPreflight({ preflight: mixto, campana: { ...campana, special_ad_categories: ['CREDIT'] }, ahora: DENTRO });
  const g = C.agruparPreflight(p.filas);
  assert.deepEqual(g.map((x) => x.id), ['cuenta', 'medicion', 'landing', 'creativos', 'limites', 'campana', 'cumplimiento']);
  const ids = g.flatMap((x) => x.filas.map((f) => f.id));
  assert.equal(ids.length, 25);
  assert.equal(new Set(ids).size, 25);
  assert.ok(g.every((x) => x.filas.every((f) => f.nombre && f.nombre !== f.titulo || f.nombre)));
  const total = g.reduce((a, x) => a + x.resumen.verde + x.resumen.amarillo + x.resumen.rojo + x.resumen.sinDato + x.resumen.noAplica, 0);
  assert.equal(total, 25, 'cada punto cuenta en un único semáforo');
  assert.equal(Object.keys(C.NOMBRE_PREFLIGHT).length, 25);
  // sin special_ad_categories el P25 condicional no entra (24 puntos) salvo que el archivo lo traiga
  const sin = C.agruparPreflight(C.modeloPreflight({ preflight: verde, campana, ahora: DENTRO }).filas);
  assert.ok(sin.reduce((a, x) => a + x.filas.length, 0) >= 24);
  assert.deepEqual(C.agruparPreflight(null), []);
});

test('ciclo: cada paso tiene su descripción humana y los bloqueos no llevan nombres de archivo', () => {
  const c = C.modeloCiclo('preflight_ok');
  assert.ok(c.pasos.every((x) => typeof x.detalle === 'string' && x.detalle));
  const m = C.modeloCampanas({ campana, estado: 'borrador' }, { ofertaId: 'OF-202611-01', ahora: DENTRO });
  assert.ok(m.paso.bloqueos.length >= 3);
  assert.ok(m.paso.bloqueos.every((b) => !/\.json/.test(b)), 'ningún .json en el texto principal');
  const conPf = C.modeloCampanas({ campana, preflight: mixto, ids_meta: ids, estado: 'borrador' }, { ofertaId: 'OF-202611-01', ahora: DENTRO });
  assert.ok(conPf.paso.texto.includes('en verde'), 'la frase del paso no usa MAYÚSCULAS técnicas');
  assert.ok(conPf.paso.bloqueos.some((b) => b.includes('rojo')));
});

test('pages/campanas.js: la firma es un comando para copiar, nunca un botón que firme', () => {
  const fuente = readFileSync(path.join(AQUI, '..', '..', 'dashboard', 'web', 'pages', 'campanas.js'), 'utf8');
  assert.ok(fuente.includes('Cómo firmar la activación'));
  assert.ok(/comando\(f\.comando/.test(fuente));
  assert.ok(!/api\.(post|get)\('\/(accion|pausa)/.test(fuente), 'sin acciones del servidor');
  assert.ok(fuente.includes('visorJson') && fuente.includes('campana.json completo'), 'el JSON crudo va en el detalle técnico');
});
