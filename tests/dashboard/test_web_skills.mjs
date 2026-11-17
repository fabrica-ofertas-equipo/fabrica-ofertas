// Pruebas de la lógica pura de #/skills (dashboard/web/lib/skills.js). Sin DOM, sin red.
// Ejecutar: node --test tests/dashboard/test_web_skills.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import * as L from '../../dashboard/web/lib/skills.js';

const AQUI = dirname(fileURLToPath(import.meta.url));
const FIX = join(AQUI, '..', 'fixtures', 'dashboard', 'skills');
const leer = (n) => JSON.parse(readFileSync(join(FIX, n), 'utf8'));
const datos = leer('skills.json').datos;
const filas = L.filasSkills(datos);
const por = (slug) => filas.find((f) => f.slug === slug);

test('etapaDeSlug: por token de etapa, por palabra clave y desconocidos', () => {
  assert.equal(L.etapaDeSlug('d3-oferta'), 'D3');
  assert.equal(L.etapaDeSlug('d10-postcompra'), 'D10');
  assert.equal(L.etapaDeSlug('oferta-d4'), 'D4');
  assert.equal(L.etapaDeSlug('d3-maker'), 'D3');
  assert.equal(L.etapaDeSlug('x1-qa'), 'X1');
  assert.equal(L.etapaDeSlug('m1-mercados'), 'M1');
  assert.equal(L.etapaDeSlug('validacion'), 'D2');
  assert.equal(L.etapaDeSlug('landing-checkout'), 'D5');
  assert.equal(L.etapaDeSlug('planificador-video'), null);
  assert.equal(L.etapaDeSlug(''), null);
  assert.equal(L.etapaDeSlug(null), null);
  assert.equal(L.etapaDeSlug('d11-x'), null); // no existe D11
});

test('archivosPresentes acepta mapa de bool/número/lista/objeto y lista de rutas', () => {
  const a = L.archivosPresentes({ 'SKILL.md': true, references: 3, 'rubric.md': false, templates: [], scripts: ['a.py'], evals: { existe: true }, 'CHANGELOG.md': 'sí' });
  assert.deepEqual(a, { skill: true, references: true, rubric: false, templates: false, scripts: true, evals: true, changelog: true });
  const b = L.archivosPresentes(['SKILL.md', 'references/guia.md', 'evals/evals.json', 'CHANGELOG.md', 'otro/x']);
  assert.deepEqual(b, { skill: true, references: true, rubric: false, templates: false, scripts: false, evals: true, changelog: true });
  const c = L.archivosPresentes([{ ruta: 'rubric.md' }, { nombre: 'scripts/' }, 5, null]);
  assert.equal(c.rubric, true);
  assert.equal(c.scripts, true);
  assert.deepEqual(Object.values(L.archivosPresentes(null)), [false, false, false, false, false, false, false]);
  assert.deepEqual(Object.values(L.archivosPresentes('x')), [false, false, false, false, false, false, false]);
});

test('agentes: roles Maker y QA desde strings u objetos', () => {
  assert.deepEqual(L.resumenAgentes(['d3-maker', 'd3-qa']), { ids: ['d3-maker', 'd3-qa'], maker: true, qa: true, total: 2 });
  assert.deepEqual(L.resumenAgentes(['d5-maker.md']), { ids: ['d5-maker'], maker: true, qa: false, total: 1 });
  assert.equal(L.resumenAgentes([{ id: 'x', rol: 'qa' }]).qa, true);
  assert.equal(L.resumenAgentes([{ slug: 'x1-qa' }]).qa, true);
  assert.deepEqual(L.resumenAgentes(null), { ids: [], maker: false, qa: false, total: 0 });
  assert.equal(L.rolDeAgente('qa'), 'qa');
  assert.equal(L.rolDeAgente('quality'), 'otro');
});

test('estadoDeSkill: manda el servidor; si falta se deduce de la versión', () => {
  assert.equal(L.estadoDeSkill({ estado: 'v1', version: '0.1.0' }), 'v1');
  assert.equal(L.estadoDeSkill({ version: '1.2.0' }), 'v1');
  assert.equal(L.estadoDeSkill({ version: '0.9.0' }), 'borrador');
  assert.equal(L.estadoDeSkill({}), 'borrador');
});

test('filasSkills: ordenadas por etapa del flujo y luego por slug; las sin etapa al final', () => {
  assert.deepEqual(filas.map((f) => f.slug), ['d3-oferta', 'd5-landing-checkout', 'planificador-video']);
  assert.equal(por('d3-oferta').etapa, 'D3');
  assert.equal(por('planificador-video').etapa, null);
  const raro = L.filasSkills([{ slug: 'zzz' }, { slug: 'd1-x' }, { slug: 'x1-cumplimiento' }, { slug: 'f1-finanzas' }, null, 4]);
  assert.deepEqual(raro.map((f) => f.slug), ['d1-x', 'x1-cumplimiento', 'f1-finanzas', 'zzz']);
});

test('fila completa y fila incompleta', () => {
  const d3 = por('d3-oferta');
  assert.equal(d3.estado, 'v1');
  assert.equal(d3.version, '1.0.0');
  assert.equal(d3.lineas, 212);
  assert.equal(d3.estructuraCompleta, true);
  assert.deepEqual(d3.faltan, []);
  assert.equal(d3.agentes.maker && d3.agentes.qa, true);
  const d5 = por('d5-landing-checkout');
  assert.equal(d5.estado, 'borrador');
  assert.equal(d5.estructuraCompleta, false);
  assert.deepEqual(d5.faltan, ['templates/', 'evals/', 'CHANGELOG.md']);
  assert.equal(d5.agentes.qa, false);
  const pv = por('planificador-video');
  assert.equal(pv.lineas, null);
  assert.equal(pv.archivos.skill, false);
});

test('checklistDoD de una skill completa: estructura, líneas, descripción y agentes en verde', () => {
  const items = por('d3-oferta').dod;
  const f = (txt) => items.find((i) => i.criterio.startsWith(txt));
  assert.equal(f('Estructura completa').ok, true);
  assert.equal(f('SKILL.md con menos de 500').ok, true);
  assert.equal(f('SKILL.md con menos de 500').nota, '212 líneas');
  assert.equal(f('description con menos de').ok, true);
  assert.equal(f('Agentes definidos').ok, true);
  assert.equal(f('Versión congelada').ok, true);
  // del servidor
  assert.equal(f('Contrato').ok, true);
  assert.equal(f('Contrato').origen, 'servidor');
  assert.equal(f('Estabilidad').ok, null);
  // el criterio del plan «Contrato» no se duplica; los demás sí aparecen como no comprobables
  assert.equal(items.filter((i) => /^Contrato/.test(i.criterio)).length, 1);
  assert.equal(items.filter((i) => /^Evals/.test(i.criterio)).length, 1);
  const plan = items.filter((i) => i.origen === 'plan');
  assert.ok(plan.length > 0 && plan.every((i) => i.ok === null && /No comprobable/.test(i.nota)));
  assert.ok(!items.some((i) => /^Forma/.test(i.criterio))); // «Forma» ya se comprueba con los archivos
});

test('checklistDoD de una skill con fallos: 540 líneas, descripción larga, falta QA y archivos', () => {
  const items = por('d5-landing-checkout').dod;
  const f = (txt) => items.find((i) => i.criterio.startsWith(txt));
  assert.equal(f('Estructura completa').ok, false);
  assert.match(f('Estructura completa').nota, /Faltan: templates\/, evals\/, CHANGELOG\.md/);
  assert.equal(f('SKILL.md con menos de 500').ok, false);
  assert.equal(f('description con menos de').ok, false);
  assert.match(f('description con menos de').nota, /1\d{3} caracteres/);
  assert.equal(f('Agentes definidos').ok, false);
  assert.match(f('Agentes definidos').nota, /falta el QA/);
  assert.equal(f('Versión congelada').ok, false);
});

test('checklistDoD sin datos: null, nunca true por defecto', () => {
  const items = L.checklistDoD({ slug: 'x' });
  const f = (txt) => items.find((i) => i.criterio.startsWith(txt));
  assert.equal(f('SKILL.md con menos de 500').ok, null);
  assert.equal(f('description con menos de').ok, null);
  assert.equal(f('Estructura completa').ok, false);
  assert.equal(f('Agentes definidos').ok, false);
  const r = L.resumenDoD(items);
  assert.equal(r.ok, 0);
  assert.equal(r.total, items.length);
  assert.equal(r.ok + r.falla + r.sinComprobar, r.total);
  assert.deepEqual(L.checklistDoD(null).length, items.length);
});

test('límites exactos de forma: 499 pasa, 500 no; descripción de 1023 pasa y de 1024 no', () => {
  const base = { archivos: [], agentes: [] };
  const lin = (n) => L.checklistDoD({ ...base, lineas_skill_md: n, descripcion: 'x' }).find((i) => i.criterio.startsWith('SKILL.md con menos de 500')).ok;
  assert.equal(lin(499), true);
  assert.equal(lin(500), false);
  assert.equal(lin(0), true);
  const des = (n) => L.checklistDoD({ ...base, descripcion: 'x'.repeat(n) }).find((i) => i.criterio.startsWith('description con menos de')).ok;
  assert.equal(des(1023), true);
  assert.equal(des(1024), false);
});

test('resumenDoD cuenta ok, fallos y sin comprobar', () => {
  assert.deepEqual(L.resumenDoD([{ ok: true }, { ok: false }, { ok: null }, { ok: undefined }]), { ok: 1, falla: 1, sinComprobar: 2, total: 4 });
});

test('cobertura por etapa: marca las etapas del flujo SIN skill y deja D9 como fuera de alcance', () => {
  const c = L.coberturaPorEtapa(filas);
  assert.equal(c.flujo.length, 12); // 11 etapas + X1
  assert.equal(c.flujo.find((f) => f.etapa === 'D3').conSkill, true);
  assert.deepEqual(c.flujo.find((f) => f.etapa === 'D3').skills, ['d3-oferta']);
  assert.equal(c.flujo.find((f) => f.etapa === 'D5').conSkill, true);
  assert.equal(c.flujo.find((f) => f.etapa === 'D1').conSkill, false);
  assert.ok(c.sinSkillFlujo.includes('D1'));
  assert.ok(!c.sinSkillFlujo.includes('D3'));
  assert.ok(!c.sinSkillFlujo.includes('D9'));
  assert.equal(c.flujo.find((f) => f.etapa === 'D9').fueraDeAlcance, true);
  assert.equal(c.flujo.find((f) => f.etapa === 'D1').forja, 'criterio');
  assert.equal(c.flujo.find((f) => f.etapa === 'D8').forja, 'ingenieria');
  assert.deepEqual(c.resto.map((f) => f.etapa), ['O0', 'D0', 'F1', 'F2', 'X2']);
  assert.deepEqual(c.sinEtapa, ['planificador-video']);
});

test('cobertura sin ninguna skill: todas las etapas del flujo salen sin skill (menos D9)', () => {
  const c = L.coberturaPorEtapa([]);
  assert.equal(c.sinSkillFlujo.length, 11); // 10 etapas + X1, sin D9
  assert.equal(c.sinSkillResto.length, 5);
  const r = L.resumenSkills([]);
  assert.equal(r.total, 0);
  assert.equal(r.etapasFlujoConSkill, 0);
  assert.equal(r.etapasFlujoTotal, 11);
});

test('resumenSkills de la fixture', () => {
  const r = L.resumenSkills(filas);
  assert.equal(r.total, 3);
  assert.equal(r.v1, 1);
  assert.equal(r.borradores, 2);
  assert.equal(r.estructuraCompleta, 1);
  assert.equal(r.etapasFlujoConSkill, 2);
});

test('filtrarSkills por texto, estado y estructura incompleta', () => {
  assert.equal(L.filtrarSkills(filas, {}).length, 3);
  assert.deepEqual(L.filtrarSkills(filas, { texto: 'landing' }).map((f) => f.slug), ['d5-landing-checkout']);
  assert.deepEqual(L.filtrarSkills(filas, { texto: 'VIDEO' }).map((f) => f.slug), ['planificador-video']); // sin tildes ni mayúsculas
  assert.deepEqual(L.filtrarSkills(filas, { estado: 'v1' }).map((f) => f.slug), ['d3-oferta']);
  assert.deepEqual(L.filtrarSkills(filas, { soloIncompletas: true }).map((f) => f.slug), ['d5-landing-checkout', 'planificador-video']);
});

test('comandos y rutas de skills: solo slugs seguros', () => {
  assert.equal(L.rutaSkillMd('d3-oferta'), '.claude/skills/d3-oferta/SKILL.md');
  assert.deepEqual(L.comandosSkill('d3-oferta').map((c) => c.comando), [
    'less .claude/skills/d3-oferta/SKILL.md', 'ls -R .claude/skills/d3-oferta', 'cat .claude/skills/d3-oferta/CHANGELOG.md',
  ]);
  assert.deepEqual(L.comandosSkill('x; rm -rf /'), []);
  assert.deepEqual(L.comandosSkill('../x'), []); // la barra no está en la lista blanca de caracteres
});

test('lista vacía o con basura no rompe nada', () => {
  assert.deepEqual(L.filasSkills(leer('skills_vacio.json').datos), []);
  assert.deepEqual(L.filasSkills(null), []);
  assert.deepEqual(L.listaDeSkills({ skills: [{ slug: 'a' }] }).length, 1);
  assert.deepEqual(L.nombreEtapaSkill('X1'), 'Cumplimiento');
  assert.deepEqual(L.nombreEtapaSkill('D4'), 'Producto');
  assert.deepEqual(L.nombreEtapaSkill('ZZ'), 'ZZ');
});

test('texto hostil en slug y descripción se conserva literal (el render lo escapa)', () => {
  const f = L.filaSkill({ slug: '<img src=x onerror=1>', descripcion: '<script>alert(1)</script>', version: '0.1.0' });
  assert.equal(f.slug, '<img src=x onerror=1>');
  assert.equal(f.descripcion, '<script>alert(1)</script>');
  assert.deepEqual(L.comandosSkill(f.slug), []);
});

// ───────────────────────── rediseño UX: títulos humanos y camino a v1 ─────────────────────────

test('títulos humanos de las skills conocidas y respaldo para las demás', () => {
  assert.equal(L.tituloSkill('d3-arquitectura-oferta'), 'Armar la oferta');
  assert.equal(L.tituloSkill('x1-compliance'), 'Cumplimiento');
  assert.equal(L.tituloSkill('d8-optimizacion-diaria'), 'Optimizacion diaria'); // sin el prefijo de etapa
  assert.equal(L.tituloSkill('planificador-video'), 'Planificador video');
  assert.equal(L.tituloSkill(''), '');
});

test('el criterio 11 (cumplimiento) solo aplica a D1, D3, D6 y X1', () => {
  const tiene = (slug) => L.checklistDoD({ slug }).some((i) => /^Cumplimiento/.test(i.criterio));
  assert.equal(tiene('d3-oferta'), true);
  assert.equal(tiene('d1-descubrimiento'), true);
  assert.equal(tiene('x1-compliance'), true);
  assert.equal(tiene('d6-creativos'), true);
  assert.equal(tiene('d2-validacion'), false);
  assert.equal(tiene('d7-campanas-meta'), false);
});

test('faltaParaV1: separa lo que se arregla, lo que se mide y lo que ya cumple (sin contar «versión congelada»)', () => {
  const completa = L.filaSkill({ slug: 'd2-validacion', version: '0.1.0', estado: 'borrador', descripcion: 'x', lineas_skill_md: 90, archivos: { 'SKILL.md': true, 'rubric.md': true, 'CHANGELOG.md': true, references: 2, templates: 1, scripts: 1, evals: 3 }, agentes: ['d2-maker', 'd2-qa'] });
  const f = L.faltaParaV1(completa);
  assert.equal(f.arreglar.length, 0);
  assert.equal(f.cumple.length, 4);
  assert.ok(f.medir.length >= 8 && f.medir.every((i) => i.ok === null));
  assert.equal(f.total, f.cumple.length + f.medir.length + f.arreglar.length);
  assert.match(f.siguiente, /^Pulirla a mano y medir \d+ criterios \(\d+ innegociables\)\.$/);
  assert.equal(f.congelada, false);
  // con fallos: lo primero es arreglar
  const rota = L.filaSkill({ slug: 'd5-landing-checkout', version: '0.1.0', estado: 'borrador', descripcion: 'x', lineas_skill_md: 540, archivos: { 'SKILL.md': true }, agentes: ['d5-maker'] });
  const g = L.faltaParaV1(rota);
  assert.ok(g.arreglar.length >= 3);
  assert.match(g.siguiente, /^Arreglar primero: /);
  // v1: nada que arreglar, aviso de que cambiarla exige aprobación
  const v1 = L.faltaParaV1({ ...completa, estado: 'v1' });
  assert.equal(v1.congelada, true);
  assert.match(v1.siguiente, /exige tu aprobación/);
  // sin datos no revienta
  assert.equal(L.faltaParaV1(null).total, 0);
  assert.equal(L.faltaParaV1(null).bpCumple, 0);
});

test('camino a v1 y cobertura: estado de cada celda', () => {
  assert.deepEqual(L.CAMINO_V1.map((h) => h.id), ['pulir', 'retro', 'dod']);
  const cob = L.resumenCobertura([L.filaSkill({ slug: 'd3-oferta', version: '1.0.0', estado: 'v1', archivos: {}, agentes: [] }), L.filaSkill({ slug: 'd4-producto', version: '0.1.0', estado: 'borrador', archivos: {}, agentes: [] })]);
  const por = (id) => cob.celdas.find((c) => c.etapa === id);
  assert.equal(L.estadoCobertura(por('D3')), 'v1');
  assert.equal(L.estadoCobertura(por('D4')), 'borrador');
  assert.equal(L.estadoCobertura(por('D1')), 'sin_skill');
  assert.equal(L.estadoCobertura(por('D9')), 'fuera_alcance');
  assert.equal(L.estadoCobertura(null), 'sin_skill');
  assert.equal(cob.conSkill, 2);
  assert.ok(cob.sinSkillTotal >= 8);
});

test('primeraFrase y conteos de archivos: texto corto para tarjetas, sin inventar números', () => {
  assert.equal(L.primeraFrase('Valida con evidencia el candidato. Úsala cuando el motor lo pida.'), 'Valida con evidencia el candidato. Úsala cuando el motor lo pida.'); // una frase corta sola no basta
  assert.equal(L.primeraFrase('Mercados, idiomas y monedas (M1). Decide en qué idioma, países y moneda se testea cada oferta y hace nativo el texto. Más cosas.'), 'Mercados, idiomas y monedas (M1). Decide en qué idioma, países y moneda se testea cada oferta y hace nativo el texto.');
  assert.equal(L.primeraFrase('[v0.1 sin pulir] X1, Cumplimiento: veto y sello transversal.'), 'X1, Cumplimiento: veto y sello transversal.');
  assert.equal(L.primeraFrase('v0.1 sin pulir. Construye la landing de una oferta.'), 'Construye la landing de una oferta.');
  assert.equal(L.primeraFrase(''), '');
  assert.equal(L.primeraFrase(null), '');
  const larga = `${'palabra '.repeat(60)}fin.`;
  const t = L.primeraFrase(larga, 60);
  assert.ok([...t].length <= 62 && t.endsWith('…'));
  assert.equal(L.primeraFrase('Sin punto final y corta'), 'Sin punto final y corta');
  const c = L.conteosArchivos({ 'SKILL.md': true, 'rubric.md': true, references: 14, templates: 13, scripts: 3, evals: 46, 'CHANGELOG.md': true });
  assert.equal(c.references, 14);
  assert.equal(c.evals, 46);
  assert.equal(c.skill, null); // solo sabe que existe, no cuántos
  assert.equal(L.conteosArchivos(null).references, null);
  assert.equal(L.conteosArchivos({ evals: ['a', 'b'] }).evals, 2);
});

test('la fila trae título humano y conteos; la etapa humana cubre flujo y empresa', () => {
  const f = L.filaSkill({ slug: 'd3-arquitectura-oferta', version: '0.1.0', archivos: { references: 3, evals: 6 }, agentes: [] });
  assert.equal(f.titulo, 'Armar la oferta');
  assert.equal(f.conteos.evals, 6);
  assert.equal(L.nombreHumanoEtapaSkill('D7'), 'Campaña');
  assert.equal(L.nombreHumanoEtapaSkill('X1'), 'Cumplimiento');
  assert.equal(L.nombreHumanoEtapaSkill('ZZ'), 'ZZ');
  assert.match(f.busqueda, /armar la oferta/); // el título también se busca (sin tildes ni mayúsculas)
});
