// Pruebas de la lógica pura de #/pulido (dashboard/web/lib/pulido.js). Sin DOM, sin red.
// Ejecutar: node --test tests/dashboard/test_web_pulido.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import * as L from '../../dashboard/web/lib/pulido.js';

const AQUI = dirname(fileURLToPath(import.meta.url));
const FIX = join(AQUI, '..', 'fixtures', 'dashboard', 'pulido');
const crudo = JSON.parse(readFileSync(join(FIX, 'bitacora.json'), 'utf8')).datos;
const entradas = L.normalizarEntradas(crudo);
const por = (id) => entradas.find((e) => e.id === id);

test('normalizarEntradas pliega los cambios de estado sobre cada entrada y descarta basura', () => {
  assert.deepEqual(entradas.map((e) => e.id), ['PUL-0001', 'PUL-0002', 'PUL-0003', 'PUL-0004', 'PUL-0005']);
  assert.equal(por('PUL-0001').estado, 'abierta'); // abierta -> en_curso -> resuelta -> abierta (gana la última)
  assert.equal(por('PUL-0002').estado, 'resuelta');
  assert.equal(por('PUL-0003').estado, 'abierta'); // sin cambios: abierta por defecto
  assert.equal(por('PUL-0001').titulo, 'El precio sugerido no cuadra con la economía'); // el cambio no pisa el título
  assert.equal(por('PUL-0001').actualizado_en, '2026-11-10T09:30:00Z');
  assert.ok(!entradas.some((e) => e.id === 'PUL-9999')); // cambio de una entrada que no se ve: no inventa una fila
});

test('campos inválidos caen a valores seguros', () => {
  const e = por('PUL-0005');
  assert.equal(e.severidad, 'media');
  assert.equal(e.tipo, 'observacion');
  assert.equal(e.titulo, '<b>HTML</b> en título ‮');
  assert.equal(e.detalle, '<script>alert(1)</script>');
});

test('listaCruda acepta varias formas', () => {
  assert.equal(L.listaCruda([1, 2]).length, 2);
  assert.equal(L.listaCruda({ entradas: [1] }).length, 1);
  assert.equal(L.listaCruda({ items: [1, 2, 3] }).length, 3);
  assert.equal(L.listaCruda({ lineas: [1] }).length, 1);
  assert.deepEqual(L.listaCruda(null), []);
  assert.deepEqual(L.listaCruda({}), []);
  assert.deepEqual(L.normalizarEntradas(undefined), []);
});

test('normalizarEntradas: un cambio de estado con valor no válido se ignora', () => {
  const e = L.normalizarEntradas([
    { id: 'A', ts: '2026-11-01T00:00:00Z', titulo: 't', etapa: 'D1' },
    { id: 'A', ts: '2026-11-01T00:01:00Z', estado: 'inventado' },
  ]);
  assert.equal(e.length, 1);
  assert.equal(e[0].estado, 'abierta');
});

test('ordenarEntradas: abiertas antes que resueltas, luego severidad, luego recientes', () => {
  const o = L.ordenarEntradas(entradas).map((e) => e.id);
  assert.equal(o[o.length - 1], 'PUL-0002'); // la resuelta al final
  assert.equal(o[0], 'PUL-0004'); // alta y abierta, la más reciente de las altas
  const altas = o.slice(0, 2);
  assert.deepEqual(altas.sort(), ['PUL-0001', 'PUL-0004']);
  const copia = entradas.slice();
  L.ordenarEntradas(entradas);
  assert.deepEqual(entradas, copia);
});

test('filtrarEntradas: oferta, global, etapa, severidad, estado, tipo, texto y ocultar resueltas', () => {
  assert.equal(L.filtrarEntradas(entradas, {}).length, 5);
  assert.deepEqual(L.filtrarEntradas(entradas, { oferta: 'OF-202611-03' }).map((e) => e.id), ['PUL-0004']);
  assert.deepEqual(L.filtrarEntradas(entradas, { oferta: '_global' }).map((e) => e.id), ['PUL-0003']);
  assert.deepEqual(L.filtrarEntradas(entradas, { etapa: 'D5' }).map((e) => e.id), ['PUL-0002']);
  assert.equal(L.filtrarEntradas(entradas, { severidad: 'alta' }).length, 2);
  assert.deepEqual(L.filtrarEntradas(entradas, { estado: 'resuelta' }).map((e) => e.id), ['PUL-0002']);
  assert.deepEqual(L.filtrarEntradas(entradas, { tipo: 'decision' }).map((e) => e.id), ['PUL-0003']);
  assert.deepEqual(L.filtrarEntradas(entradas, { texto: 'REEMBOLSOS' }).map((e) => e.id), ['PUL-0002']);
  assert.deepEqual(L.filtrarEntradas(entradas, { texto: 'pul-0004' }).map((e) => e.id), ['PUL-0004']);
  assert.equal(L.filtrarEntradas(entradas, { ocultarResueltas: true }).length, 4);
  assert.deepEqual(L.filtrarEntradas(entradas, { etapa: 'D3', severidad: 'baja' }), []);
});

test('hayFiltros', () => {
  assert.equal(L.hayFiltros({}), false);
  assert.equal(L.hayFiltros({ etapa: 'D1' }), true);
  assert.equal(L.hayFiltros({ ocultarResueltas: true }), true);
});

test('conteosPorEtapa: siempre las 11 etapas del flujo, en orden, con abiertas/en curso/resueltas', () => {
  const c = L.conteosPorEtapa(entradas);
  assert.deepEqual(c.map((x) => x.etapa), ['D1', 'M1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10']);
  const d3 = c.find((x) => x.etapa === 'D3');
  assert.equal(d3.total, 2);
  assert.equal(d3.abiertas, 2);
  assert.equal(d3.altaPendiente, 1);
  const d5 = c.find((x) => x.etapa === 'D5');
  assert.equal(d5.resueltas, 1);
  assert.equal(d5.abiertas, 0);
  assert.equal(c.find((x) => x.etapa === 'M1').total, 0);
});

test('conteosPorEtapa por oferta, global y con etapas de empresa fuera del flujo', () => {
  const d = L.conteosPorEtapa(entradas, { oferta: '_ejemplo' });
  assert.equal(d.find((x) => x.etapa === 'D3').total, 2);
  assert.equal(d.find((x) => x.etapa === 'D8').total, 0);
  const g = L.conteosPorEtapa(entradas, { oferta: '_global' });
  assert.equal(g.find((x) => x.etapa === 'D1').total, 1);
  const extra = L.normalizarEntradas([{ id: 'X', titulo: 't', etapa: 'X1' }, { id: 'Y', titulo: 't', etapa: 'ZZ' }, { id: 'Z', titulo: 't' }]);
  const c = L.conteosPorEtapa(extra);
  assert.deepEqual(c.slice(-2).map((x) => x.etapa), ['X1', 'ZZ']);
  assert.equal(c.length, 13); // 11 + X1 + ZZ; la entrada sin etapa no cuenta en ninguna
});

test('resumenBitacora', () => {
  const r = L.resumenBitacora(entradas);
  assert.equal(r.total, 5);
  assert.equal(r.abiertas, 4);
  assert.equal(r.resueltas, 1);
  assert.equal(r.enCurso, 0);
  assert.equal(r.pendientes, 4);
  assert.equal(r.altasPendientes, 2);
  assert.equal(r.bpResueltas, 2000);
  assert.deepEqual(L.resumenBitacora([]), { total: 0, abiertas: 0, enCurso: 0, resueltas: 0, altasPendientes: 0, pendientes: 0, bpResueltas: 0 });
});

test('ofertasEnBitacora junta las de la bitácora con las conocidas, sin duplicados', () => {
  assert.deepEqual(L.ofertasEnBitacora(entradas, ['OF-202611-09', '_ejemplo', '', null]), ['OF-202611-03', 'OF-202611-09', '_ejemplo']);
  assert.deepEqual(L.ofertasEnBitacora([], []), []);
});

test('entradasDeEtapa: de la oferta y, si se pide, las globales de esa etapa', () => {
  assert.deepEqual(L.entradasDeEtapa(entradas, '_ejemplo', 'D3').map((e) => e.id).sort(), ['PUL-0001', 'PUL-0005']);
  assert.deepEqual(L.entradasDeEtapa(entradas, '_ejemplo', 'D1').map((e) => e.id), ['PUL-0003']);
  assert.deepEqual(L.entradasDeEtapa(entradas, '_ejemplo', 'D1', { incluirGlobales: false }), []);
  assert.deepEqual(L.entradasDeEtapa(entradas, 'OF-202611-03', 'D3'), []);
});

test('validarNueva: campos mínimos, límites y cuerpo del POST sin campos de más', () => {
  const ok = L.validarNueva({ etapa: 'D3', titulo: '  Algo falla  ', detalle: ' detalle ', severidad: 'alta', tipo: 'nota', oferta_id: '_ejemplo' });
  assert.equal(ok.ok, true);
  assert.deepEqual(ok.cuerpo, { etapa: 'D3', titulo: 'Algo falla', detalle: 'detalle', severidad: 'alta', tipo: 'nota', oferta_id: '_ejemplo' });
  const sinOferta = L.validarNueva({ etapa: 'D3', titulo: 'x' });
  assert.equal(sinOferta.ok, true);
  assert.ok(!('oferta_id' in sinOferta.cuerpo));
  assert.equal(sinOferta.cuerpo.severidad, 'media'); // valores por defecto
  assert.equal(sinOferta.cuerpo.tipo, 'observacion');
  assert.equal(sinOferta.cuerpo.detalle, '');
  const conExtra = L.validarNueva({ etapa: 'D3', titulo: 'x', autor: 'otro', id: 'PUL-1', estado: 'resuelta', ts: 'hoy' });
  assert.deepEqual(Object.keys(conExtra.cuerpo).sort(), ['detalle', 'etapa', 'severidad', 'tipo', 'titulo']); // no deja colar id/autor/ts/estado
});

test('validarNueva: errores por campo', () => {
  const e = L.validarNueva({}).errores;
  assert.ok(e.etapa && e.titulo);
  assert.ok(L.validarNueva({ etapa: 'Q9', titulo: 'x' }).errores.etapa);
  assert.ok(L.validarNueva({ etapa: 'D3', titulo: '   ' }).errores.titulo);
  assert.ok(L.validarNueva({ etapa: 'D3', titulo: 'a'.repeat(L.LIMITES.titulo + 1) }).errores.titulo);
  assert.equal(L.validarNueva({ etapa: 'D3', titulo: 'a'.repeat(L.LIMITES.titulo) }).ok, true);
  assert.ok(L.validarNueva({ etapa: 'D3', titulo: 'x', detalle: 'a'.repeat(L.LIMITES.detalle + 1) }).errores.detalle);
  assert.ok(L.validarNueva({ etapa: 'D3', titulo: 'x', severidad: 'critica' }).errores.severidad);
  assert.ok(L.validarNueva({ etapa: 'D3', titulo: 'x', tipo: 'queja' }).errores.tipo);
  assert.ok(L.validarNueva({ etapa: 'D3', titulo: 'x', oferta_id: '../../etc' }).errores.oferta_id);
  assert.ok(L.validarNueva({ etapa: 'D3', titulo: 'x', oferta_id: 'oferta-uno' }).errores.oferta_id); // el servidor solo admite OF-AAAAMM-NN o _carpeta
  assert.equal(L.validarNueva({ etapa: 'D3', titulo: 'x', oferta_id: '_ejemplo' }).ok, true);
  assert.ok(L.validarNueva({ etapa: 'D3', titulo: 'x', oferta_id: 'a b' }).errores.oferta_id);
  assert.equal(L.validarNueva({ etapa: 'X1', titulo: 'x' }).ok, true); // etapas de empresa permitidas
  assert.equal(L.validarNueva(undefined).ok, false);
  // emoji: se cuenta por caracteres, no por unidades UTF-16
  assert.equal(L.validarNueva({ etapa: 'D3', titulo: '😀'.repeat(L.LIMITES.titulo) }).ok, true);
});

test('cuerpoCambioEstado solo admite los tres estados y exige id', () => {
  assert.deepEqual(L.cuerpoCambioEstado('PUL-0001', 'resuelta'), { id: 'PUL-0001', estado: 'resuelta' });
  assert.throws(() => L.cuerpoCambioEstado('PUL-0001', 'cerrada'), RangeError);
  assert.throws(() => L.cuerpoCambioEstado('PUL-1', 'abierta'), RangeError); // el servidor exige PUL-0001
  assert.throws(() => L.cuerpoCambioEstado('', 'abierta'), RangeError);
  assert.throws(() => L.cuerpoCambioEstado(null, 'abierta'), RangeError);
});

test('ciclo de estados y etiquetas', () => {
  assert.equal(L.siguienteEstado('abierta'), 'en_curso');
  assert.equal(L.siguienteEstado('en_curso'), 'resuelta');
  assert.equal(L.siguienteEstado('resuelta'), 'abierta');
  assert.equal(L.etiquetaSiguiente('abierta'), 'Empezar');
  assert.equal(L.etiquetaSiguiente('en_curso'), 'Resolver');
  assert.equal(L.etiquetaSiguiente('resuelta'), 'Reabrir');
});

test('catálogos: etapas de pulido y nombres', () => {
  assert.equal(L.ETAPAS_PULIDO.length, 17);
  assert.equal(new Set(L.ETAPAS_PULIDO).size, 17);
  assert.equal(L.nombreEtapaPulido('X1'), 'Cumplimiento');
  assert.equal(L.nombreEtapaPulido('D3'), 'Oferta');
  assert.equal(L.compararEtapasPulido('D1', 'X1') < 0, true);
  assert.equal(L.compararEtapasPulido('X1', 'D1') > 0, true);
  assert.equal(L.compararEtapasPulido('ZZ', 'D1') > 0, true);
});

test('el filtro de texto ignora tildes y mayúsculas', () => {
  assert.deepEqual(L.filtrarEntradas(entradas, { texto: 'ECONOMIA' }).map((e) => e.id), ['PUL-0001']); // «economía»
});

// ───────────────────────── rediseño UX: tablero, severidad y madurez ─────────────────────────

test('columnasTablero: una columna por estado, alta primero, y el filtro de estado no aplica', () => {
  const cols = L.columnasTablero(entradas, {});
  assert.deepEqual(cols.map((c) => c.estado), ['abierta', 'en_curso', 'resuelta']);
  assert.deepEqual(cols.map((c) => c.titulo), ['Abierta', 'En curso', 'Resuelta']);
  assert.equal(cols.reduce((n, c) => n + c.items.length, 0), entradas.length);
  for (const c of cols) assert.ok(c.items.every((e) => e.estado === c.estado));
  const sev = { alta: 0, media: 1, baja: 2 };
  for (const c of cols) for (let i = 1; i < c.items.length; i += 1) assert.ok(sev[c.items[i - 1].severidad] <= sev[c.items[i].severidad]);
  // un filtro de estado se ignora (si no, dos columnas quedarían vacías); los demás sí filtran
  assert.equal(L.columnasTablero(entradas, { estado: 'resuelta' }).reduce((n, c) => n + c.items.length, 0), entradas.length);
  const solo = L.columnasTablero(entradas, { severidad: 'alta' });
  assert.ok(solo.every((c) => c.items.every((e) => e.severidad === 'alta')));
  assert.equal(L.columnasTablero(entradas, { ocultarResueltas: true })[2].items.length, cols[2].items.length); // en el tablero no se esconde la columna
});

test('conteosPorSeveridad: pendientes y resueltas por gravedad', () => {
  const c = L.conteosPorSeveridad(entradas);
  assert.equal(c.alta.total + c.media.total + c.baja.total, entradas.length);
  assert.equal(c.alta.pendientes + c.media.pendientes + c.baja.pendientes, L.resumenBitacora(entradas).pendientes);
  assert.deepEqual(L.conteosPorSeveridad([]).alta, { pendientes: 0, resueltas: 0, total: 0 });
});

test('madurez por etapa: sin notas, por pulir o limpia', () => {
  assert.equal(L.madurezEtapa({ total: 0, abiertas: 0, enCurso: 0 }), 'sin_notas');
  assert.equal(L.madurezEtapa({ total: 3, abiertas: 1, enCurso: 0 }), 'pulir');
  assert.equal(L.madurezEtapa({ total: 3, abiertas: 0, enCurso: 1 }), 'pulir');
  assert.equal(L.madurezEtapa({ total: 3, abiertas: 0, enCurso: 0, resueltas: 3 }), 'limpia');
  assert.equal(L.madurezEtapa(null), 'sin_notas');
  const m = L.mapaPulido(entradas);
  assert.equal(m.filas.length >= 11, true);
  assert.equal(m.maxPendientes, Math.max(...m.filas.map((f) => f.pendientes)));
  assert.equal(m.conNotas, m.filas.filter((f) => f.total > 0).length);
  assert.ok(m.filas.every((f) => ['sin_notas', 'pulir', 'limpia'].includes(f.madurez)));
});

test('alta rápida: solo hace falta título y etapa; usa los mismos límites que el servidor', () => {
  const ok = L.validarRapida({ titulo: '  Precio mal calculado ', etapa: 'D3', severidad: 'alta', oferta_id: '_ejemplo' });
  assert.equal(ok.ok, true);
  assert.deepEqual(ok.cuerpo, { etapa: 'D3', titulo: 'Precio mal calculado', detalle: '', severidad: 'alta', tipo: 'observacion', oferta_id: '_ejemplo' });
  assert.equal(L.validarRapida({ titulo: 'x' }).errores.etapa.length > 0, true);
  assert.equal(L.validarRapida({ etapa: 'D3' }).errores.titulo.length > 0, true);
  assert.equal(L.validarRapida({ titulo: 'x', etapa: 'D3', oferta_id: 'no valida!' }).ok, false);
});

test('mover entre columnas: solo a otro estado válido', () => {
  const e = { estado: 'abierta' };
  assert.equal(L.puedeMover(e, 'en_curso'), true);
  assert.equal(L.puedeMover(e, 'abierta'), false);
  assert.equal(L.puedeMover(e, 'cerrada'), false);
  assert.equal(L.puedeMover(null, 'resuelta'), false);
  assert.match(L.resumenEntrada({ severidad: 'alta', estado: 'en_curso', titulo: 'Algo' }), /^Alta, en curso: Algo$/);
});
