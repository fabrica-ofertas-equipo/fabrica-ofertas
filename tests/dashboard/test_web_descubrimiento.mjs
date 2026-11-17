// Pruebas de la lógica pura de #/descubrimiento (dashboard/web/lib/descubrimiento.js) con fixtures propios.
// Sin DOM, sin red, sin tocar empresa/ real:  node --test tests/dashboard/test_web_descubrimiento.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import * as L from '../../dashboard/web/lib/descubrimiento.js';

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const FX = path.join(AQUI, '..', 'fixtures', 'dashboard', 'descubrimiento');
const cargar = (n) => JSON.parse(readFileSync(path.join(FX, n), 'utf8'));
const clon = (o) => JSON.parse(JSON.stringify(o));

const cand = cargar('candidatos.json');
const pagDoc = cargar('paginas.json');
const etiq = cargar('etiquetas.json');
const fichas = cargar('fichas.json');
const plan = cargar('plan.json');
const estadoP1 = cargar('estado.json');
const estadoCli = cargar('estado_cli.json');
const corridas = cargar('corridas.json');

// ───────────── texto no confiable ─────────────

test('neutralizar: los controles bidi se hacen visibles, no se interpretan', () => {
  assert.equal(L.neutralizar('abc‮def'), 'abc⟦U+202E⟧def');
  assert.equal(L.neutralizar('⁦x⁩'), '⟦U+2066⟧x⟦U+2069⟧');
  assert.equal(L.neutralizar('a​b﻿c'), 'a⟦U+200B⟧b⟦U+FEFF⟧c');
  assert.equal(L.neutralizar('a\u0000b'), 'a⟦U+0000⟧b');
});

test('neutralizar: colapsa saltos y espacios, acota el largo sin partir emojis y respeta ZWJ', () => {
  assert.equal(L.neutralizar('  a\n\t b   c  '), 'a b c');
  assert.equal(L.neutralizar('😀😀😀😀😀', { max: 3 }), '😀😀…');
  assert.equal(L.neutralizar('👩‍💻'), '👩‍💻', 'ZWJ legítimo en emojis compuestos no se marca');
  assert.equal(L.neutralizar(null), '');
  assert.equal(L.neutralizar(undefined), '');
  assert.equal(L.neutralizar(42), '42');
  assert.equal(L.neutralizar('x'.repeat(50), { max: 10 }).length, 10);
});

test('neutralizar: no escapa HTML (eso lo hace textContent) pero tampoco lo interpreta', () => {
  const s = L.neutralizar('<img src=x onerror=alert(1)>');
  assert.equal(s, '<img src=x onerror=alert(1)>');
});

test('tieneControlBidi', () => {
  assert.equal(L.tieneControlBidi('hola‮'), true);
  assert.equal(L.tieneControlBidi('hola'), false);
  assert.equal(L.tieneControlBidi(null), false);
  // llamadas repetidas con el mismo patrón global no deben alternar el resultado
  assert.equal(L.tieneControlBidi('a‮b'), true);
  assert.equal(L.tieneControlBidi('a‮b'), true);
});

test('urlFichaAnuncio: solo la forma https://www.facebook.com/ads/library/?id=<dígitos>', () => {
  assert.equal(L.urlFichaAnuncio('https://www.facebook.com/ads/library/?id=1736210814961162'), 'https://www.facebook.com/ads/library/?id=1736210814961162');
  assert.equal(L.urlFichaAnuncio('  https://www.facebook.com/ads/library/?id=12  '), 'https://www.facebook.com/ads/library/?id=12');
  for (const mala of ['javascript:alert(1)', 'http://www.facebook.com/ads/library/?id=1', 'https://evil.example/ads/library/?id=1', 'https://www.facebook.com/ads/library/?id=1&x=2',
    'https://www.facebook.com/ads/library/?id=abc', 'https://www.facebook.com/ads/library/?id=1\n<script>', '', null, undefined, 5]) {
    assert.equal(L.urlFichaAnuncio(mala), null, String(mala));
  }
});

// ───────────── números ─────────────

test('formato de números: piso, días, tasas, nulos', () => {
  assert.equal(L.num(0), '0');
  assert.equal(L.num(12345), '12.345');
  assert.equal(L.num(null), '—');
  assert.equal(L.num(NaN), '—');
  assert.equal(L.num(Infinity), '—');
  assert.equal(L.num('7'), '—', 'una cadena no es un número');
  assert.equal(L.conPiso(744, true), `≥ ${L.num(744)}`);
  assert.equal(L.conPiso(744, false), L.num(744));
  assert.equal(L.conPiso(null, true), '—');
  assert.equal(L.diasTexto('36.04890046296296296296296296', false), '36 d');
  assert.equal(L.diasTexto('36.04890046296296296296296296', true), '≥ 36 d');
  assert.equal(L.diasTexto('0.1930324074074074', false), '0,2 d');
  assert.equal(L.diasTexto('0', false), '0 d');
  assert.equal(L.diasTexto('150.7', false), '151 d');
  assert.equal(L.diasTexto(null), '—');
  assert.equal(L.diasTexto('abc'), '—');
  assert.equal(L.diasTexto('NaN'), '—');
  assert.equal(L.tasaTexto('0.9586'), '95,9 %');
  assert.equal(L.tasaTexto(null), '—');
  assert.equal(L.aNumero(''), null);
  assert.equal(L.aNumero('1e999'), null);
});

// ───────────── corridas ─────────────

test('ordenarCorridas y elegirCorrida', () => {
  const ord = L.ordenarCorridas(corridas);
  assert.deepEqual(ord.map((c) => c.corrida_id), ['2026-11-20-b', '2026-11-06-a', '2026-10-01-a']);
  assert.equal(L.elegirCorrida(corridas, '2026-10-01-a').corrida_id, '2026-10-01-a');
  assert.equal(L.elegirCorrida(corridas, 'inexistente').corrida_id, '2026-11-20-b', 'una corrida pedida que no existe cae a la más reciente');
  assert.equal(L.elegirCorrida(corridas, null).corrida_id, '2026-11-20-b');
  assert.equal(L.elegirCorrida([], '2026-11-06-a'), null);
  assert.equal(L.elegirCorrida(null, 'x'), null);
  assert.deepEqual(L.ordenarCorridas([null, {}, { corrida_id: 3 }]), []);
});

test('corridaValida y comandoBarrido nunca interpolan texto no validado', () => {
  assert.equal(L.corridaValida('2026-11-06-a'), true);
  for (const mala of ['2026-11-06-a; rm -rf /', '../etc', '2026-11-06', '', null, '2026-11-06-ab', '2026-11-06-A']) assert.equal(L.corridaValida(mala), false, String(mala));
  const cmd = L.comandoBarrido('rankear', '2026-11-06-a; rm -rf /');
  assert.ok(cmd.includes('<CORRIDA>'));
  assert.ok(!cmd.includes('rm -rf'));
  assert.equal(L.comandoBarrido('estado', '2026-11-06-a'), '.venv/bin/python -m scripts.modelado.barrido estado 2026-11-06-a');
  assert.ok(L.comandoBarrido('rankear', '2026-11-06-a').includes('--sello-esperado <SELLO>'));
  assert.ok(L.comandoBarrido('memoria', '2026-11-06-a').endsWith('--escribir'));
});

// ───────────── freno ─────────────

test('modeloFreno: sin dato, libre, puesto; el motivo es texto no confiable', () => {
  assert.equal(L.modeloFreno(undefined).conocido, false);
  assert.equal(L.modeloFreno(null).activo, false);
  assert.equal(L.modeloFreno({ activo: false }).tono, 'ok');
  const f = L.modeloFreno({ activo: true, ts: '2026-11-06T06:03:43Z', motivo: 'HTTP 403 (Document)‮' });
  assert.equal(f.activo, true);
  assert.equal(f.tono, 'error');
  assert.ok(f.motivo.includes('⟦U+202E⟧'));
  assert.ok(f.instruccion.includes('Solo una persona'));
  assert.ok(f.alcance.includes('ruta A'));
  assert.equal(L.modeloFreno({ activo: true }).motivo, 'sin motivo registrado');
});

// ───────────── estado normalizado ─────────────

test('normalizarEstado: forma del panel y forma de `barrido estado`', () => {
  const a = L.normalizarEstado(estadoP1);
  assert.equal(a.plan.consultas, 5);
  assert.equal(a.plan.tope, 120);
  assert.equal(a.crudos.ok, 5);
  assert.equal(a.crudos.sinCrudo, 0, 'sin_crudo se deduce de plan − ok − error');
  assert.equal(a.paginas.total, 5);
  assert.equal(a.etiquetado.existe, true);
  assert.equal(a.memoria.existe, true);
  assert.equal(a.fichas.total, 2);
  assert.equal(a.freno.activo, true);
  const b = L.normalizarEstado(estadoCli);
  assert.equal(b.plan.tope, 120);
  assert.equal(b.crudos.truncadas, 59);
  assert.equal(b.crudos.anunciosDistintos, 3083);
  assert.equal(b.paginas.medicion.parcial, 23);
  assert.equal(b.etiquetado.cobertura.etiquetadas, 694);
  assert.equal(b.memoria.instantaneas, 1);
  assert.equal(b.fichas.total, 13);
  assert.equal(b.freno.motivo, 'HTTP 403 (Document)');
});

test('normalizarEstado: lo que falta es null (nunca 0) y lo hostil no rompe', () => {
  assert.equal(L.normalizarEstado(null), null);
  assert.equal(L.normalizarEstado([]), null);
  assert.equal(L.normalizarEstado('texto'), null);
  const v = L.normalizarEstado({});
  assert.equal(v.plan.consultas, null);
  assert.equal(v.crudos.ok, null);
  assert.equal(v.crudos.sinCrudo, null);
  assert.equal(v.paginas.total, null);
  assert.equal(v.fichas.total, null);
  assert.equal(v.memoria.instantaneas, null);
  assert.equal(v.freno, undefined);
  const raro = L.normalizarEstado({ plan: 'x', crudo: [], paginas: 5, etiquetas: 7, memoria: null, candidatos: 'a', fichas: 1 });
  assert.equal(raro.plan.consultas, null);
});

// ───────────── resumen ─────────────

test('resumenCorrida: tarjetas, pisos y freno', () => {
  const r = L.resumenCorrida({ corrida: corridas[0], candidatos: cand, estado: estadoCli });
  const por = Object.fromEntries(r.tarjetas.map((t) => [t.id, t]));
  assert.deepEqual(r.tarjetas.map((t) => t.id), ['consultas', 'paginas', 'etiquetadas', 'candidatas', 'traccion', 'fichas', 'freno']);
  assert.ok(por.consultas.valor.includes('/'), 'usadas / tope');
  assert.ok(por.consultas.detalle.includes('quedan'));
  assert.ok(por.paginas.valor.startsWith('≥'), 'las páginas vistas son un piso');
  assert.ok(por.paginas.detalle.startsWith('Mínimo visto'));
  assert.equal(por.traccion.valor, L.num(cand.resumen.temas_pasan_traccion + cand.resumen.sin_tema_pasan_traccion));
  assert.ok(por.traccion.detalle.includes('páginas sin tema'));
  assert.equal(por.freno.valor, 'Puesto');
  assert.equal(por.freno.tono, 'error');
  assert.equal(r.freno.activo, true);
  assert.ok(r.pisos[0].includes('mínimo'));
  assert.ok(r.avisos.length >= 1 && r.avisos.every((a) => typeof a === 'string'));
});

test('resumenCorrida: freno explícito manda sobre el del estado; sin nada, el freno es «—»', () => {
  const libre = L.resumenCorrida({ corrida: corridas[0], candidatos: cand, estado: estadoP1, freno: null });
  assert.equal(libre.tarjetas.find((t) => t.id === 'freno').valor, 'Libre');
  const nada = L.resumenCorrida({ corrida: corridas[1] });
  const f = nada.tarjetas.find((t) => t.id === 'freno');
  assert.equal(f.valor, '—');
  assert.equal(f.tono, 'neutro');
});

test('resumenCorrida: una corrida sin datos no muestra ceros inventados', () => {
  const r = L.resumenCorrida({ corrida: corridas[2] });
  const por = Object.fromEntries(r.tarjetas.map((t) => [t.id, t]));
  assert.equal(por.consultas.valor, '—');
  assert.equal(por.etiquetadas.valor, '—');
  assert.equal(por.candidatas.valor, '—');
  assert.equal(por.traccion.valor, '—');
  assert.equal(por.fichas.valor, '—');
  assert.equal(por.paginas.valor, '—');
});

test('resumenCorrida: tono del cupo (≥ 90 % avisa, > tope es error)', () => {
  const t = (ok, tope) => L.resumenCorrida({ corrida: { consultas_ok: ok, consultas_tope: tope } }).tarjetas[0].tono;
  assert.equal(t(10, 120), 'neutro');
  assert.equal(t(108, 120), 'aviso');
  assert.equal(t(121, 120), 'error');
  assert.equal(t(5, 0), 'neutro');
});

// ───────────── candidatos ─────────────

test('filasTemas: mapeo, pisos, exportador, macro y por verificar', () => {
  const filas = L.filasTemas(cand);
  assert.equal(filas.length, 3);
  const pasa = filas.find((f) => f.slug === 'comprension-lectora');
  assert.equal(pasa.tipo, 'tema');
  assert.equal(pasa.estado, 'pasa');
  assert.equal(pasa.estadoTono, 'ok');
  assert.equal(pasa.anunciantes, 2);
  assert.equal(pasa.anuncios, 18);
  assert.equal(pasa.anunciosEsPiso, true, 'las páginas del tema son de muestra: piso');
  assert.equal(pasa.edadEsPiso, true);
  assert.ok(Math.abs(pasa.edad - 36.0489) < 0.001);
  assert.deepEqual(pasa.paises, ['IT']);
  assert.ok(pasa.huecos.includes('BR'));
  assert.equal(pasa.macro, null);
  assert.equal(pasa.exportador.hay, true);
  assert.ok(pasa.exportador.texto.includes('BRL'));
  assert.deepEqual(pasa.porVerificar, ['modelo_de_cobro']);
  assert.ok(pasa.motivo.includes('cumplen'));
  assert.ok(filas.find((f) => f.estado === 'no_pasa').motivo.includes('no alcanza'));
  const ind = filas.find((f) => f.estado === 'indeterminada_por_muestra');
  assert.equal(ind.macro, 'dinero');
  assert.ok(ind.motivo.includes('pasada 3'));
});

test('filasTemas: texto hostil neutralizado y sin HTML interpretado', () => {
  const filas = L.filasTemas(cand);
  const h = filas.find((f) => f.estado === 'indeterminada_por_muestra');
  assert.ok(h.nombre.includes('<img src=x onerror=alert(1)>'), 'el HTML queda como texto (textContent lo muestra literal)');
  assert.ok(h.nombre.includes('⟦U+202E⟧'));
  assert.ok(!/[‪-‮]/.test(h.nombre));
  assert.ok(h.nombresPaginas.every((n) => !/[‪-‮]/.test(n)));
});

test('filasSinTema: cada página es su propio candidato y el conteo es un piso', () => {
  const filas = L.filasSinTema(cand);
  assert.equal(filas.length, 2);
  assert.equal(filas[0].tipo, 'sin_tema');
  assert.equal(filas[0].id, '108605787440965');
  assert.equal(filas[0].anunciantes, 1);
  assert.equal(filas[0].anuncios, 744);
  assert.equal(filas[0].anunciosEsPiso, true);
  assert.ok(filas[0].motivo.includes('anuncios'));
  const c = clon(cand);
  c.sin_tema[0].cuenta_como_independiente = false;
  assert.equal(L.filasSinTema(c)[0].anunciantes, 0);
});

test('filasTemas / filasSinTema con datos vacíos o rotos', () => {
  assert.deepEqual(L.filasTemas(null), []);
  assert.deepEqual(L.filasTemas({}), []);
  assert.deepEqual(L.filasTemas({ temas: 'x' }), []);
  assert.deepEqual(L.filasSinTema(undefined), []);
  const f = L.filasTemas({ temas: [{}] })[0];
  assert.equal(f.anunciantes, null, 'sin dato no es 0');
  assert.equal(f.anuncios, null);
  assert.equal(f.edad, null);
  assert.equal(f.estadoTexto, 'Sin estado');
  assert.ok(f.id.startsWith('tema-'));
});

test('ordenarPorDefecto: pasan primero, luego indeterminadas, luego no pasan', () => {
  const filas = [...L.filasTemas(cand), ...L.filasSinTema(cand)];
  const ord = L.ordenarPorDefecto(filas);
  assert.deepEqual(ord.map((f) => f.estado).slice(0, 3), ['pasa', 'pasa', 'pasa']);
  assert.equal(ord.at(-1).estado, 'no_pasa');
  // estable y sin mutar la entrada
  assert.equal(filas[0].tipo, 'tema');
  assert.equal(ord.length, filas.length);
});

test('filtrarFilas: estado, macro, país (presente/hueco), exportador, por verificar, tipo y texto', () => {
  const filas = [...L.filasTemas(cand), ...L.filasSinTema(cand)];
  assert.equal(L.filtrarFilas(filas, {}).length, filas.length);
  assert.equal(L.filtrarFilas(filas, { estado: 'pasa' }).length, 3);
  assert.equal(L.filtrarFilas(filas, { macro: 'dinero' }).length, 1);
  assert.equal(L.filtrarFilas(filas, { macro: 'ninguno' }).length, filas.length - 1);
  assert.equal(L.filtrarFilas(filas, { pais: 'ES' }).length, filas.filter((f) => f.paises.includes('ES')).length);
  const huecoEs = L.filtrarFilas(filas, { pais: 'ES', paisModo: 'hueco' });
  assert.ok(huecoEs.every((f) => !f.paises.includes('ES')));
  assert.equal(L.filtrarFilas(filas, { exportador: true }).every((f) => f.exportador.hay), true);
  assert.ok(L.filtrarFilas(filas, { verificar: true }).every((f) => f.porVerificar.length > 0));
  assert.ok(L.filtrarFilas(filas, { verificar: false }).every((f) => f.porVerificar.length === 0));
  assert.equal(L.filtrarFilas(filas, { tipo: 'sin_tema' }).length, 2);
  assert.equal(L.filtrarFilas(filas, { q: 'COMPRENSION' }).length, 1, 'sin tildes ni mayúsculas');
  assert.equal(L.filtrarFilas(filas, { q: 'picchianti' }).length, 1, 'busca también en el nombre de la página');
  assert.equal(L.filtrarFilas(filas, { q: 'zzzz-no-existe' }).length, 0);
  assert.equal(L.filtrarFilas(filas, { q: '   ' }).length, filas.length);
});

test('opcionesFiltro sale de los datos', () => {
  const o = L.opcionesFiltro(L.filasTemas(cand));
  assert.ok(o.paises.includes('IT') && o.paises.includes('BR'));
  assert.deepEqual(o.macros, ['dinero']);
});

test('ordenarFilas: nulos siempre al final, estable, sentido por defecto y explícito', () => {
  const base = L.filasTemas(cand).map((f, i) => ({ ...f, anunciantes: [3, null, 1][i], rank: i + 1 }));
  assert.deepEqual(L.ordenarFilas(base, { clave: 'anunciantes' }).map((f) => f.anunciantes), [3, 1, null]);
  assert.deepEqual(L.ordenarFilas(base, { clave: 'anunciantes', dir: 'asc' }).map((f) => f.anunciantes), [1, 3, null]);
  assert.deepEqual(L.ordenarFilas(base, { clave: 'rank' }).map((f) => f.rank), [1, 2, 3]);
  assert.equal(L.ordenarFilas(base, { clave: 'nombre' })[0].nombre.localeCompare(L.ordenarFilas(base, { clave: 'nombre' })[1].nombre, 'es') <= 0, true);
  assert.deepEqual(L.ordenarFilas(base, { clave: 'no-existe' }).map((f) => f.rank), [1, 2, 3], 'clave desconocida: orden del ranking');
  assert.equal(base[1].anunciantes, null, 'no muta la entrada');
});

test('paginar: límites y vacío', () => {
  const filas = Array.from({ length: 120 }, (_, i) => i);
  const p = L.paginar(filas, 0, 50);
  assert.equal(p.filas.length, 50);
  assert.equal(p.paginas, 3);
  assert.equal(p.desde, 1);
  assert.equal(p.hasta, 50);
  assert.equal(L.paginar(filas, 99, 50).pagina, 2, 'una página fuera de rango se acota');
  assert.equal(L.paginar(filas, 2, 50).filas.length, 20);
  const v = L.paginar([], 0, 50);
  assert.equal(v.total, 0);
  assert.equal(v.desde, 0);
  assert.equal(v.paginas, 1);
  assert.equal(L.paginar(filas, -5, 0).filas.length, 50, 'por_pagina inválido cae al valor por defecto');
});

// ───────────── detalle ─────────────

test('detalleTema: kv con pisos y huecos como hipótesis', () => {
  const fila = L.filasTemas(cand).find((f) => f.slug === 'comprension-lectora');
  const d = L.detalleTema(fila);
  const kv = Object.fromEntries(d.kv);
  assert.ok(kv['Anuncios medidos'].includes('≥'));
  assert.ok(kv['Anuncios medidos'].includes('(al menos)'));
  assert.ok(kv['Países sin presencia en la muestra'].includes('hipótesis'));
  assert.ok(kv['Anunciantes nuevos en 30 días'].includes('no es cero'));
  assert.equal(d.paginas.length, 2);
  assert.ok(d.paginas.every((p) => p.motivo.includes('anuncios')));
});

test('textoMedicion y medicionPorPais: piso vs medido', () => {
  assert.equal(L.textoMedicion('completa').tono, 'ok');
  assert.equal(L.textoMedicion('parcial').tono, 'aviso');
  assert.equal(L.textoMedicion('muestra').texto, 'solo muestra');
  assert.equal(L.textoMedicion(undefined).texto, 'sin medición');
  const parcial = pagDoc.paginas.find((p) => p.medicion.estado === 'parcial');
  const m = L.medicionPorPais(parcial);
  assert.ok(m.length >= 1);
  assert.ok(m.every((x) => typeof x.lectura === 'string'));
  assert.ok(m.some((x) => x.lectura.startsWith('parcial') || x.lectura.startsWith('al menos') || x.lectura.startsWith('exacto')));
  const x = L.medicionPorPais({ medicion: { por_pais: {
    ES: { fuente: 'pagina', anuncios_vistos: 9, total_declarado: 9, completa: true },
    FR: { fuente: 'pagina', anuncios_vistos: 50, total_declarado: 744, completa: false },
    IT: { fuente: 'muestra', anuncios_vistos: 3, total_declarado: null, completa: false },
  } } });
  assert.equal(x.find((r) => r.pais === 'ES').lectura, 'exacto: 9 de 9 anuncios');
  assert.equal(x.find((r) => r.pais === 'FR').lectura, 'parcial: se ven 50 de 744 declarados');
  assert.ok(x.find((r) => r.pais === 'IT').lectura.startsWith('al menos'));
  assert.equal(x.find((r) => r.pais === 'IT').tono, 'aviso');
  assert.deepEqual(L.medicionPorPais(null), []);
  assert.deepEqual(L.medicionPorPais({ medicion: 'x' }), []);
});

test('detallePagina: une ranking, ingesta y etiquetado; títulos hostiles neutralizados', () => {
  const candidata = L.indexarCandidatas(cand).get('614770848385168').pagina;
  const pagina = pagDoc.paginas.find((p) => p.page_id === '614770848385168');
  const etiqueta = L.indexarEtiquetas(etiq).get('614770848385168');
  const d = L.detallePagina({ candidata, pagina, etiqueta, corrida: '2026-11-06-a' });
  assert.equal(d.id, '614770848385168');
  assert.ok(d.nombre.includes('⟦U+202E⟧'));
  assert.ok(!/[‪-‮]/.test(d.nombre));
  assert.equal(d.titulos.length, 3);
  assert.equal(d.titulos[0].bidi, true, 'se avisa que el título traía controles bidi');
  assert.ok(d.titulos[0].texto.includes('<b onmouseover=alert(3)>'), 'el HTML queda como texto');
  assert.ok(d.titulos[0].texto.includes('⟦U+202E⟧'));
  assert.equal(d.titulos[1].bidi, false);
  assert.ok(d.titulos[1].texto.includes('👩‍💻'));
  assert.ok(d.titulos[2].texto.length <= 300, 'los títulos se acotan');
  assert.deepEqual(d.senalesRiesgo, ['promesa_ingresos', 'urgencia_falsa']);
  assert.equal(d.medicionEstado, 'muestra');
  assert.equal(d.anunciosEsPiso, true);
  assert.ok(d.etiqueta.modeloCobro.includes('sin verificar') || d.etiqueta.modeloCobro.includes('pago'));
  assert.ok(d.fichasNota.includes('ad_snapshot_url'), 'sin URLs en los datos, dice dónde están y no inventa enlaces');
  assert.ok(d.fichasNota.includes('empresa/barrido/crudo/2026-11-06-a/'));
  assert.deepEqual(d.fichas, []);
});

test('detallePagina: faltan fuentes → notas honestas, sin inventar', () => {
  const candidata = L.indexarCandidatas(cand).get('108605787440965').pagina;
  const d = L.detallePagina({ candidata });
  assert.ok(d.notas.some((n) => n.includes('títulos')));
  assert.ok(d.notas.some((n) => n.includes('clasific')));
  assert.equal(d.titulos.length, 0);
  assert.equal(d.etiqueta, null);
  assert.equal(d.porPais.length, 0);
  assert.equal(d.anunciosMedidos, 744);
  assert.equal(d.anunciosEsPiso, true);
  const vacio = L.detallePagina({});
  assert.equal(vacio.id, '');
  assert.equal(vacio.anunciosMedidos, null);
});

test('detallePagina: las URL de ficha se aceptan solo con la forma exacta y se muestran como texto', () => {
  const pagina = { page_id: '1', page_name: 'x', anuncios: [
    { ad_snapshot_url: 'https://www.facebook.com/ads/library/?id=123' },
    { ad_snapshot_url: 'javascript:alert(1)' },
    { ad_snapshot_url: 'https://evil.example/?id=1' },
    { url: 'https://www.facebook.com/ads/library/?id=456' },
  ] };
  const d = L.detallePagina({ pagina });
  assert.deepEqual(d.fichas, ['https://www.facebook.com/ads/library/?id=123', 'https://www.facebook.com/ads/library/?id=456']);
  assert.equal(d.fichasNota, null);
});

test('indexarEtiquetas e indexarCandidatas', () => {
  const e = L.indexarEtiquetas(etiq);
  assert.ok(e.size >= 3);
  assert.ok(e.has('108605787440965'));
  assert.equal(L.indexarEtiquetas(null).size, 0);
  const c = L.indexarCandidatas(cand);
  assert.equal(c.get('108605787440965').temaSlug, null, 'una página sin tema no tiene slug');
  assert.equal(c.get('1076938925508814').temaSlug, 'comprension-lectora');
  assert.equal(L.indexarCandidatas({}).size, 0);
});

// ───────────── matriz ─────────────

test('modeloMatriz: presencia/hueco, conteos por país y advertencia', () => {
  const m = L.modeloMatriz(cand);
  assert.equal(m.paises.length, 10);
  assert.equal(m.totalTemas, 3);
  assert.equal(m.filas.length, 3);
  const f = m.filas.find((x) => x.slug === 'comprension-lectora');
  assert.equal(f.celdas.length, 10);
  assert.equal(f.presentes + f.huecos, 10);
  assert.equal(f.celdas.find((c) => c.pais === 'IT').presente, true);
  assert.equal(f.celdas.find((c) => c.pais === 'BR').presente, false);
  assert.ok(m.advertencia.includes('hipótesis'));
  assert.equal(m.estadoAusencia, 'hipotesis_hasta_pasada_3');
  const it = m.porPais.find((p) => p.pais === 'IT');
  assert.equal(it.presentes + it.huecos, 3);
});

test('modeloMatriz: la advertencia siempre existe aunque los datos no la traigan', () => {
  const c = clon(cand);
  delete c.matriz_tema_pais.advertencia;
  assert.equal(L.modeloMatriz(c).advertencia, L.AVISO_MATRIZ_DEFECTO);
  assert.ok(L.AVISO_MATRIZ_DEFECTO.includes('no significa que no exista en ese mercado'));
  const vacia = L.modeloMatriz(null);
  assert.deepEqual(vacia.filas, []);
  assert.deepEqual(vacia.paises, []);
  assert.ok(vacia.advertencia.length > 10);
});

test('modeloMatriz: filtros soloPasan, texto, mínimo de países y tope de filas', () => {
  assert.equal(L.modeloMatriz(cand, { soloPasan: true }).filas.length, 1);
  assert.equal(L.modeloMatriz(cand, { soloPasan: true }).total, 1);
  assert.equal(L.modeloMatriz(cand, { soloPasan: true }).totalTemas, 3);
  assert.equal(L.modeloMatriz(cand, { q: 'CRICUT' }).filas.length, 1);
  assert.equal(L.modeloMatriz(cand, { minPaises: 2 }).filas.length, 0);
  assert.equal(L.modeloMatriz(cand, { max: 2 }).filas.length, 2);
  assert.equal(L.modeloMatriz(cand, { max: 2 }).total, 3);
  assert.equal(L.modeloMatriz(cand, { estado: 'no_pasa' }).filas.length, 1);
});

// ───────────── fichas ─────────────

test('modeloFichas: qué falta evaluar; null no es «no»', () => {
  const m = L.modeloFichas(fichas);
  assert.equal(m.total, 2);
  assert.equal(m.version, '2.0.0');
  assert.equal(m.incompletas, 2);
  const a = m.fichas[0];
  assert.ok(a.nombre.length > 0);
  assert.equal(a.puertas.length, 3);
  assert.ok(a.puertas.every((p) => p.valor === null), 'las puertas siguen en null');
  assert.equal(a.completo, false);
  assert.ok(a.faltan > 0 && a.faltan <= a.totalCampos);
  const temas = a.faltantes.map((x) => x.tema);
  for (const esperado of ['Puertas', 'Transferibilidad', 'Reencuadres', 'Ventana', 'Anunciantes nuevos en 30 días', 'Puntaje del rival']) assert.ok(temas.includes(esperado), esperado);
  assert.ok(a.faltantes.find((x) => x.tema === 'Puertas').detalle.includes('3 de 3'));
  assert.ok(a.faltantes.find((x) => x.tema === 'Ventana').detalle.includes('relleno'));
  // la segunda ficha tiene una puerta evaluada y un reencuadre: faltan menos campos y no aparece «Reencuadres»
  const b = m.fichas[1];
  assert.ok(b.faltan < a.faltan);
  assert.ok(b.faltantes.find((x) => x.tema === 'Puertas').detalle.includes('2 de 3'));
  assert.ok(!b.faltantes.some((x) => x.tema === 'Reencuadres'));
  assert.equal(b.puertas[0].valor, false, 'false se conserva: es un dato evaluado');
  assert.ok(a.mercados.length >= 1);
  assert.ok(a.mercados.every((x) => x.originalPresente === false && x.sostenidos === 0));
  assert.ok(a.pendiente.length > 0);
});

test('modeloFichas: ficha totalmente evaluada y entradas vacías', () => {
  const f = clon(fichas);
  const o = f.ofertas[0];
  for (const k of Object.keys(o.puertas)) o.puertas[k] = false;
  o.reencuadres = [{ id: 'r' }];
  for (const mk of o.mercados) {
    for (const k of Object.keys(mk.transferibilidad)) mk.transferibilidad[k] = 3;
    mk.hueco.puntaje_rival = 2; mk.hueco.entrantes_30d = 1; mk.ventana = 'estacional';
  }
  const m = L.modeloFichas(f);
  assert.equal(m.fichas[0].completo, true);
  assert.equal(m.fichas[0].faltan, 0);
  assert.equal(m.fichas[0].faltantes.length, 0);
  assert.equal(m.incompletas, 1);
  assert.equal(L.modeloFichas(null).total, 0);
  assert.equal(L.modeloFichas({}).fichas.length, 0);
  assert.equal(L.modeloFichas({ ofertas: [{}] }).fichas[0].mercados.length, 0);
});

// ───────────── plan y cobertura ─────────────

test('modeloPlan: solo totales (barrido estado) no inventa el reparto por pasada', () => {
  const parcial = clon(estadoCli);
  parcial.crudos.ok = 3; parcial.crudos.sin_crudo = 2;
  const m = L.modeloPlan(plan, parcial);
  assert.equal(m.porPasadaDisponible, false);
  assert.ok(m.avisoSinListas.includes('no se inventa'));
  assert.deepEqual(m.pasadas.map((p) => p.pasada), [1, 3]);
  assert.equal(m.pasadas[0].planificadas, 3);
  assert.equal(m.pasadas[1].planificadas, 2);
  assert.ok(m.pasadas.every((p) => p.ok === null && p.conError === null && p.sinEjecutar === null && p.truncadas === null));
  assert.equal(m.totalesEstado.ok, 3);
  assert.equal(m.totalesEstado.truncadas, 59);
  assert.equal(m.tope, 120);
  assert.equal(m.cupoRestante, 115);
  assert.equal(m.planificadas, 5);
  assert.ok(m.consultas.every((c) => c.estado === null));
});

test('modeloPlan: todo ejecutado y sin errores se deduce y se dice que se dedujo', () => {
  const m = L.modeloPlan(plan, estadoP1);
  assert.equal(m.porPasadaDisponible, true);
  assert.ok(m.avisoSinListas.includes('se deduce'));
  assert.deepEqual(m.pasadas.map((p) => [p.ok, p.conError, p.sinEjecutar]), [[3, 0, 0], [2, 0, 0]]);
  assert.ok(m.pasadas.every((p) => p.truncadas === null), 'las truncadas por pasada no se deducen');
  assert.ok(m.consultas.every((c) => c.estado === 'ok'));
});

test('modeloPlan: nada ejecutado también se deduce', () => {
  const e = clon(estadoP1);
  e.crudo = { existe: false, ok: 0, error: 0 };
  const m = L.modeloPlan(plan, e);
  assert.deepEqual(m.pasadas.map((p) => [p.ok, p.sinEjecutar]), [[0, 3], [0, 2]]);
  assert.ok(m.consultas.every((c) => c.estado === 'sin_ejecutar'));
});

test('modeloPlan: con listas de qids (ingesta.cobertura) el reparto por pasada es exacto', () => {
  const qs = plan.consultas.map((c) => c.qid);
  const e = { cobertura: { consultas_ok: qs.slice(0, 3), con_error: [qs[3]], sin_crudo: [qs[4]], truncadas: [qs[0]] } };
  const m = L.modeloPlan(plan, e);
  assert.equal(m.porPasadaDisponible, true);
  assert.equal(m.avisoSinListas, null);
  assert.deepEqual([m.pasadas[0].ok, m.pasadas[0].truncadas, m.pasadas[0].conError], [3, 1, 0]);
  assert.deepEqual([m.pasadas[1].ok, m.pasadas[1].conError, m.pasadas[1].sinEjecutar], [0, 1, 1]);
  assert.deepEqual(m.consultas.map((c) => c.estado), ['truncada', 'ok', 'ok', 'con_error', 'sin_ejecutar']);
});

test('modeloPlan: ni plan ni estado; la frase de búsqueda (dato de terceros) se neutraliza', () => {
  const vacio = L.modeloPlan(null, null);
  assert.equal(vacio.planificadas, 0);
  assert.deepEqual(vacio.pasadas, []);
  assert.equal(vacio.tope, null);
  assert.equal(vacio.cupoRestante, null);
  const m = L.modeloPlan(plan, null);
  assert.ok(m.consultas[0].frase.includes('⟦U+202E⟧'));
  assert.ok(!/[‪-‮]/.test(m.consultas[0].frase));
  assert.equal(m.avisoSinListas.includes('totales'), true);
  const sobre = clon(plan);
  sobre.consultas.push(...plan.consultas, ...plan.consultas);
  assert.equal(L.modeloPlan(sobre, null).cupoRestante, 120 - 15);
  const exceso = clon(plan); exceso.tope_consultas = 3;
  assert.equal(L.modeloPlan(exceso, null).cupoRestante, -2);
});

// ───────────── etiquetado, descartadas, exportadores ─────────────

test('modeloEtiquetado: cobertura, sin etiquetar y señales de riesgo', () => {
  const m = L.modeloEtiquetado(etiq);
  assert.equal(m.total, 724);
  assert.equal(m.etiquetadas, 694);
  assert.equal(m.tasaEtiquetadas, '95,9 %');
  assert.equal(m.sinEtiquetarLista.length, 3);
  assert.equal(m.lotes.validados, 37);
  const r = Object.fromEntries(m.riesgos.map((x) => [x.senal, x.n]));
  assert.equal(r.promesa_ingresos >= 1, true);
  assert.equal(L.modeloEtiquetado(null), null);
  assert.equal(L.modeloEtiquetado('x'), null);
});

test('modeloDescartadas y modeloExportadores', () => {
  const d = L.modeloDescartadas(cand);
  assert.equal(d.filas.length, 3);
  assert.ok(d.porMotivo.every((x) => x.n >= 1));
  assert.deepEqual(L.modeloDescartadas(null), { filas: [], porMotivo: [] });
  const e = L.modeloExportadores(cand);
  assert.ok(e.advertencia.includes('no es un hecho'));
  assert.equal(e.evaluadas, 436);
  assert.equal(e.conSenal, 62);
  assert.ok(e.monedas[0].n >= e.monedas[1].n);
  assert.equal(L.modeloExportadores({}), null);
});

// ───────────── memoria ─────────────

test('modeloMemoria: sin base, entrantes null en todas partes (nunca 0)', () => {
  const m = L.modeloMemoria({ corridas, estado: estadoP1, candidatos: cand, corridaId: '2026-11-06-a' });
  assert.equal(m.baseValida, false);
  assert.equal(m.previa, null);
  assert.equal(m.temasConEntrantes, 0);
  assert.equal(m.totalTemas, 3);
  assert.ok(m.explicacion.includes('sin dato'));
  assert.ok(m.explicacion.includes('no son cero'));
  assert.equal(m.instantaneaDeEstaCorrida, true);
  assert.equal(m.instantaneaTs, '2026-11-06T06:09:47Z');
  assert.deepEqual(m.filas.map((f) => f.corrida), ['2026-11-20-b', '2026-11-06-a', '2026-10-01-a']);
  assert.equal(m.filas.find((f) => f.actual).corrida, '2026-11-06-a');
  assert.equal(m.filas.find((f) => f.corrida === '2026-11-06-a').deltaPaginas, 224);
  assert.equal(m.filas[0].deltaPaginas, null, 'sin páginas no hay delta');
  assert.equal(m.filas[0].paginas, null);
});

test('modeloMemoria: con base válida cuenta entrantes y temas nuevos', () => {
  const c = clon(cand);
  c.memoria = { base_valida: true, previa_corrida_id: '2026-10-01-a' };
  c.temas[0].entrantes_30d = { BR: 2, DE: null };
  c.temas[1].novedad = { tema_nuevo: true, paginas_nuevas: 1 };
  const m = L.modeloMemoria({ corridas, estado: estadoCli, candidatos: c, corridaId: '2026-11-06-a' });
  assert.equal(m.baseValida, true);
  assert.equal(m.previa, '2026-10-01-a');
  assert.equal(m.temasConEntrantes, 1);
  assert.equal(m.temasNuevos, 1);
  assert.equal(m.instantaneas, 1);
  const vacio = L.modeloMemoria({});
  assert.equal(vacio.baseValida, false);
  assert.deepEqual(vacio.filas, []);
  assert.equal(vacio.instantaneaDeEstaCorrida, null);
});

// ───────────── pipeline (estado vacío útil) ─────────────

test('modeloPipeline: dice qué comando falta', () => {
  const todo = L.modeloPipeline(estadoP1, '2026-11-06-a');
  assert.equal(todo.pasos.length, 7);
  assert.ok(todo.pasos.every((p) => p.hecho === true));
  assert.equal(todo.siguiente, null);
  const e = clon(estadoP1);
  e.candidatos.existe = false; e.fichas.existe = false;
  const p = L.modeloPipeline(e, '2026-11-06-a');
  assert.equal(p.siguiente.id, 'candidatos');
  assert.ok(p.siguiente.comando.includes('rankear 2026-11-06-a'));
  assert.ok(p.siguiente.comando.includes('<SELLO>'), 'los sellos nunca se inventan');
  const sin = L.modeloPipeline({ plan: { existe: false }, crudo: { existe: false, ok: 0, error: 0 }, paginas: { existe: false } }, '2026-11-06-a');
  assert.equal(sin.siguiente.id, 'plan');
  assert.equal(sin.pasos[1].hecho, false);
});

test('modeloPipeline: sin estado nada se da por hecho; id inválido no se interpola', () => {
  const p = L.modeloPipeline(null, '2026-11-06-a');
  assert.ok(p.pasos.every((x) => x.hecho === null));
  assert.equal(p.siguiente, null);
  const q = L.modeloPipeline(null, 'x; rm -rf /');
  assert.ok(q.pasos.every((x) => x.comando.includes('<CORRIDA>') && !x.comando.includes('rm -rf')));
});

// ───────────── API paginada ─────────────

test('normalizarPaginado y filaPagina', () => {
  const r = L.normalizarPaginado({ paginas: pagDoc.paginas, total: 40, pagina: 2, por_pagina: 6 });
  assert.equal(r.filas.length, 6);
  assert.equal(r.total, 40);
  assert.equal(r.pagina, 2);
  assert.equal(L.normalizarPaginado([1, 2, 3]).total, 3);
  assert.equal(L.normalizarPaginado(null).total, 0);
  assert.equal(L.normalizarPaginado({ items: [{}] }).filas.length, 1);
  const fila = L.filaPagina(pagDoc.paginas.find((p) => p.medicion.estado === 'completa'));
  assert.equal(fila.medicionTexto.texto, 'completa');
  assert.equal(fila.piso, fila.raw.anuncios_activos_medidos_es_piso !== false);
  const sinMed = L.filaPagina({ page_id: 9 });
  assert.equal(sinMed.anuncios, null);
  assert.equal(sinMed.medicionTexto.texto, 'sin medición');
  assert.equal(sinMed.nombre, 'página 9');
});

// ───────────── la página carga como módulo ─────────────

test('pages/descubrimiento.js exporta meta, render y alCambio (y no usa innerHTML)', async () => {
  const ruta = path.join(AQUI, '..', '..', 'dashboard', 'web', 'pages', 'descubrimiento.js');
  const mod = await import(ruta);
  assert.equal(mod.meta.ruta, 'descubrimiento');
  assert.equal(mod.meta.grupo, 'Testeo y escala');
  assert.deepEqual(mod.meta.escucha, ['barrido']);
  assert.equal(typeof mod.render, 'function');
  assert.equal(typeof mod.alCambio, 'function');
  const fuente = readFileSync(ruta, 'utf8');
  assert.ok(!/innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function/.test(fuente), 'sin APIs que interpreten HTML o código');
  assert.ok(!/<a\b[^>]*href/i.test(fuente), 'ningún enlace a la Biblioteca');
  assert.ok(!/ads\/library/.test(fuente.replace(/\/\/.*$/gm, '')), 'la página no construye URLs de Meta');
});

// ───────────── rediseño UX (U3): resumen ejecutivo, barras, vistas guardadas, calor ─────────────

test('resumenEjecutivo: titular, líneas, métricas y qué es piso/medido (sin inventar)', () => {
  const r = L.resumenEjecutivo({ corrida: corridas[0], candidatos: cand, estado: estadoP1, freno: { activo: true, ts: '2026-11-06T06:03:43Z', motivo: 'HTTP 403' } });
  const pasan = cand.resumen.temas_pasan_traccion + cand.resumen.sin_tema_pasan_traccion;
  assert.ok(r.titular.startsWith(String(pasan)), 'el titular dice cuántas pasan la tracción');
  assert.ok(r.titular.includes('mínimo de tracción'));
  assert.deepEqual(r.metricas.map((m) => m.id), ['pasan', 'por_medir', 'no_pasan', 'medido', 'consultas']);
  const m = Object.fromEntries(r.metricas.map((x) => [x.id, x]));
  assert.equal(m.pasan.valor, L.num(pasan));
  assert.equal(m.por_medir.valor, L.num(cand.resumen.temas_indeterminados_por_muestra + cand.resumen.sin_tema_indeterminadas_por_muestra));
  assert.equal(m.medido.valor, L.num(cand.resumen.paginas_por_medicion.completa));
  assert.ok(m.medido.contexto.includes('solo muestra'));
  const medido = r.lineas.find((l) => l.id === 'medido');
  assert.ok(medido.texto.includes('mínimo'), 'dice que lo que es muestra es un mínimo (al menos esa cifra)');
  assert.equal(r.freno.activo, true);
  assert.ok(r.freno.consecuencia.includes('No afecta al barrido con la herramienta de consulta'), 'la consecuencia real del freno');
  assert.ok(r.barrido.pasos.length === 7 && r.barrido.pasos.every((p) => typeof p.corto === 'string'));
  assert.ok(r.textoUmbral.includes('15') && r.textoUmbral.includes('10'));
});

test('resumenEjecutivo: sin ranking ni estado no muestra ceros ni afirma nada', () => {
  const r = L.resumenEjecutivo({ corrida: { corrida_id: '2026-11-06-b' } });
  assert.equal(r.hayRanking, false);
  assert.ok(r.titular.includes('aún no tiene ranking'));
  assert.ok(r.metricas.find((x) => x.id === 'pasan').valor === null);
  assert.ok(r.metricas.find((x) => x.id === 'consultas').valor === null);
  assert.equal(r.barrido.conocido, false);
  assert.ok(r.freno.consecuencia.includes('ruta A'), 'incluso sin dato, el freno nunca afecta al barrido por conector');
  const ninguna = L.resumenEjecutivo({ corrida: corridas[0], candidatos: { resumen: { temas_pasan_traccion: 0, sin_tema_pasan_traccion: 0 }, temas: [], sin_tema: [] } });
  assert.ok(ninguna.titular.startsWith('Ninguna oferta pasa'));
});

test('modeloFreno: la consecuencia real está siempre (libre, puesto y sin dato)', () => {
  for (const f of [undefined, null, { activo: true, motivo: 'x' }]) assert.ok(L.modeloFreno(f).consecuencia.includes('ruta A'));
  assert.ok(L.modeloFreno({ activo: true }).consecuencia.includes('ruta D'));
});

test('progresoUmbral: barra hacia 15 anuncios · 10 días, piso y sin dato (nunca 0)', () => {
  const a = L.progresoUmbral(18, 15, { piso: true });
  assert.equal(a.pct, 100); assert.equal(a.supera, true); assert.equal(a.texto, '≥ 18');
  const b = L.progresoUmbral(8, 15, { piso: true });
  assert.equal(b.pct, 53); assert.equal(b.supera, false);
  const c = L.progresoUmbral('36.0489', 10, { piso: true, unidad: 'd' });
  assert.equal(c.texto, '≥ 36 d');
  const d = L.progresoUmbral(null, 15);
  assert.equal(d.sinDato, true); assert.equal(d.supera, null); assert.equal(d.texto, '—');
  assert.equal(L.progresoUmbral(5, 0).sinDato, true, 'sin umbral válido no hay barra');
  assert.equal(L.progresoUmbral(0, 15).pct, 0, 'un cero medido sí es un cero');
});

test('explicacionTraccion y porVerificarHumano: lenguaje claro, sin ids crudos', () => {
  const u = L.normalizarUmbral(cand.umbrales_traccion);
  const t = cand.temas.find((x) => x.estado_traccion === 'pasa');
  assert.ok(L.explicacionTraccion('tema', t, u).includes('cumple'));
  assert.ok(L.explicacionTraccion('tema', { estado_traccion: 'indeterminada_por_muestra' }, u).includes('solo una muestra'));
  assert.ok(L.explicacionTraccion('tema', { estado_traccion: 'no_pasa' }, u).includes('no alcanza'));
  assert.ok(L.explicacionTraccion('pagina', { estado_traccion: 'indeterminada_por_muestra', traccion_detalle: { anuncios: 'indeterminada', edad: 'cumple' } }, u).includes('al menos'));
  assert.equal(L.explicacionTraccion('tema', {}, u), 'Sin estado de tracción.');
  assert.equal(L.porVerificarHumano('modelo_de_cobro'), 'Confirmar que cobra un pago único');
  assert.equal(L.porVerificarHumano('cosa_rara'), 'cosa rara');
  const filas = L.filasTemas(cand);
  assert.ok(filas.every((f) => typeof f.explicacion === 'string' && Array.isArray(f.porVerificarTexto)));
  assert.ok(L.filasSinTema(cand).every((f) => typeof f.explicacion === 'string'));
});

test('vistas guardadas: saneado, tope, reemplazo por nombre y filtros activos', () => {
  const v1 = L.agregarVista([], '  Mi vista  ', { estado: 'pasa', pais: 'IT', exportador: true, basura: 1 }, () => 'abc123');
  assert.equal(v1.length, 1);
  assert.equal(v1[0].titulo, 'Mi vista');
  assert.equal(v1[0].id, 'u-abc123');
  assert.deepEqual(v1[0].filtros, { q: '', estado: 'pasa', macro: '', pais: 'IT', paisModo: 'presente', exportador: true, verificar: '', tipo: '' });
  const v2 = L.agregarVista(v1, 'mi VISTA', { estado: 'no_pasa' }, () => 'zzzzzz');
  assert.equal(v2.length, 1, 'mismo nombre (sin distinguir mayúsculas) reemplaza');
  assert.equal(v2[0].filtros.estado, 'no_pasa');
  assert.equal(v2[0].id, 'u-abc123');
  assert.deepEqual(L.quitarVista(v2, 'u-abc123'), []);
  assert.deepEqual(L.agregarVista(v2, '   ', {}), v2, 'un nombre vacío no añade nada');
  // lo que venga del almacenamiento local no es de fiar
  const sucio = L.normalizarVistas([null, 5, { id: 'todos', titulo: 'x' }, { id: 'u-aaa111', titulo: 'ok‮', filtros: { estado: 'hackeado', pais: 'xx', tipo: 'tema' } }, { id: 'sin-prefijo', titulo: 'y' }]);
  assert.equal(sucio.length, 1);
  assert.ok(sucio[0].titulo.includes('⟦U+202E⟧'), 'el nombre de una vista es texto no confiable');
  assert.equal(sucio[0].filtros.estado, ''); assert.equal(sucio[0].filtros.pais, ''); assert.equal(sucio[0].filtros.tipo, 'tema');
  const muchas = Array.from({ length: 30 }, (_, i) => ({ id: `u-v${String(i).padStart(3, '0')}`, titulo: `v${i}`, filtros: {} }));
  assert.equal(L.normalizarVistas(muchas).length, 12);
  assert.equal(L.filtrosActivos({ estado: 'pasa', q: 'x', paisModo: 'hueco' }), 2, 'el modo de país solo no cuenta como filtro');
  assert.equal(L.mismosFiltros({}, L.FILTROS_VACIOS), true);
  assert.equal(L.mismosFiltros({ estado: 'pasa' }, {}), false);
  for (const v of L.VISTAS_BASE) assert.ok(typeof v.titulo === 'string' && v.id);
  // la vista «Pasan tracción» filtra de verdad
  const filas = [...L.filasTemas(cand), ...L.filasSinTema(cand)];
  const pasa = L.VISTAS_BASE.find((v) => v.id === 'pasan');
  assert.ok(L.filtrarFilas(filas, L.normalizarFiltros(pasa.filtros)).every((f) => f.estado === 'pasa'));
});

test('mapa de calor: nivelCalor discreto y celdas con nivel; ausencia = 0 (hipótesis)', () => {
  assert.deepEqual([1, 2, 3, 4, 5, 9].map(L.nivelCalor), [1, 2, 3, 3, 4, 4]);
  const m = L.modeloMatriz(cand);
  for (const f of m.filas) for (const c of f.celdas) assert.equal(c.nivel, c.presente ? L.nivelCalor(c.paginas) : 0);
});

test('fichas y plan: progreso evaluado y porcentaje ejecutado', () => {
  const f = L.modeloFichas(fichas);
  for (const x of f.fichas) {
    assert.equal(x.evaluados, Math.max(0, x.totalCampos - x.faltan));
    assert.ok(x.pctEvaluado >= 0 && x.pctEvaluado <= 100);
  }
  const p = L.modeloPlan(plan, estadoCli);
  assert.ok(p.pasadas.every((x) => x.pctOk === null || (x.pctOk >= 0 && x.pctOk <= 100)));
});

test('glosario-descubrimiento: entradas válidas y todas las claves que usan las tres pantallas existen', async () => {
  const idx = await import(path.join(AQUI, '..', '..', 'dashboard', 'web', 'lib', 'glosario-indice.js'));
  const frag = await import(path.join(AQUI, '..', '..', 'dashboard', 'web', 'lib', 'glosario-descubrimiento.js'));
  for (const [k, def] of Object.entries(frag.TERMINOS)) {
    assert.match(k, /^[a-z0-9_]{1,60}$/);
    assert.ok(idx.entradaValida(def), `entrada ${k}`);
    assert.ok(!idx.CONFLICTOS.some((c) => c.clave === k), `${k} no debe repetirse con otro glosario`);
  }
  const dir = path.join(AQUI, '..', '..', 'dashboard', 'web');
  const claves = new Set();
  for (const f of ['pages/descubrimiento.js', 'pages/landing.js', 'pages/campanas.js', 'lib/descubrimiento.js']) {
    const src = readFileSync(path.join(dir, f), 'utf8');
    for (const m of src.matchAll(/(?:termino|ayuda)\('([a-z0-9_]+)'/g)) claves.add(m[1]);
    for (const m of src.matchAll(/ayuda: '([a-z0-9_]+)'/g)) claves.add(m[1]);
  }
  assert.ok(claves.size >= 10);
  for (const k of claves) assert.ok(idx.buscarTermino(k), `falta en el glosario: ${k}`);
});

test('pages/descubrimiento.js: panel lateral, sin APIs peligrosas ni enlaces a Meta', () => {
  const fuente = readFileSync(path.join(AQUI, '..', '..', 'dashboard', 'web', 'pages', 'descubrimiento.js'), 'utf8');
  assert.ok(fuente.includes('role: \'dialog\'') && fuente.includes('Escape'), 'panel lateral accesible, cierra con Escape');
  assert.ok(!/innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function/.test(fuente));
});

// ───────────── landing original de una página (referente) ─────────────

const refBase = () => ({
  page_id: '700000000000001', page_name: 'ReferenteA',
  landing: { url: 'https://referentea.example/colora', dominio: 'referentea.example', registrada_en: '2026-11-08T10:00:00Z', nota: 'desde el botón del anuncio', oferta_id: null, copia_local: null },
  meta: { biblioteca_pagina: 'https://www.facebook.com/ads/library/?active_status=active&ad_type=all&country=ALL&view_all_page_id=700000000000001', pagina: 'https://www.facebook.com/700000000000001' },
  anuncios: [{ id: '2303787473801185', inicio: '2026-11-06', titulo: '100 Capolavori', ficha: 'https://www.facebook.com/ads/library/?id=2303787473801185' }],
  comando_registrar: '.venv/bin/python -m scripts.referentes.landing registrar 700000000000001 "<URL de la landing>" --escribir',
});

test('normalizarReferente: la landing registrada pasa y lo demás de Meta queda como texto', () => {
  const r = L.normalizarReferente(refBase());
  assert.equal(r.landing.url, 'https://referentea.example/colora');
  assert.equal(r.landing.dominio, 'referentea.example');
  assert.equal(r.anuncios.length, 1);
  assert.ok(r.meta.biblioteca.startsWith('https://www.facebook.com/ads/library/'));
  assert.equal(L.normalizarReferente(null), null);
  assert.equal(L.normalizarReferente({ page_id: '123456' }).landing, null, 'sin registro, sin landing');
});

test('normalizarReferente: una dirección que no es https limpia se DESCARTA (nunca se vuelve enlace)', () => {
  for (const mala of ['javascript:alert(1)', 'http://referentea.example/x', 'data:text/html,<b>x</b>', 'https://a.example/x y', 'https://a.example/‮gnp', '//a.example/x', 'ftp://a.example', '']) {
    const d = refBase(); d.landing.url = mala;
    assert.equal(L.normalizarReferente(d).landing, null, `se descarta: ${mala}`);
  }
});

test('normalizarReferente: direcciones de Meta fuera de facebook.com y anuncios sin ficha válida se descartan', () => {
  const d = refBase();
  d.meta.biblioteca_pagina = 'https://evil.example/ads/library/?id=1';
  d.meta.pagina = 'javascript:alert(1)';
  d.anuncios = [{ id: '1', ficha: 'https://evil.example/x' }, { id: '2', ficha: 'https://www.facebook.com/ads/library/?id=2' }, null, 'x'];
  const r = L.normalizarReferente(d);
  assert.equal(r.meta.biblioteca, null);
  assert.equal(r.meta.pagina, null);
  assert.deepEqual(r.anuncios.map((a) => a.id), ['2']);
});

test('normalizarReferente: el texto de un tercero se neutraliza (caracteres invisibles hechos visibles)', () => {
  const d = refBase(); d.page_name = 'Pitto‮lino'; d.landing.nota = 'nota\u0007';
  const r = L.normalizarReferente(d);
  assert.ok(!r.nombre.includes('‮') && !r.landing.nota.includes('\u0007'));
});

test('pages/descubrimiento.js: el ÚNICO enlace real es la landing registrada, con target=_blank y rel=noopener noreferrer', () => {
  const fuente = readFileSync(path.join(AQUI, '..', '..', 'dashboard', 'web', 'pages', 'descubrimiento.js'), 'utf8');
  const hrefs = fuente.match(/href\s*:/g) || [];
  assert.equal(hrefs.length, 1, 'solo un href en toda la pantalla (la landing original registrada)');
  assert.match(fuente, /href: l\.url, target: '_blank', rel: 'noopener noreferrer'/);
  assert.ok(!/href\s*:\s*ref\.(meta|anuncios)/.test(fuente) && !/href\s*:\s*a\.ficha/.test(fuente), 'Meta sigue siendo solo texto para copiar');
});
