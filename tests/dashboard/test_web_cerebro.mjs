// Pruebas de la lógica pura de #/cerebro (dashboard/web/lib/cerebro.js) y de la lista única (campos nuevos de lib/pulido.js). Sin DOM, sin red.
// Ejecutar: node --test tests/dashboard/test_web_cerebro.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import * as C from '../../dashboard/web/lib/cerebro.js';
import * as P from '../../dashboard/web/lib/pulido.js';

const AQUI = dirname(fileURLToPath(import.meta.url));
const RAIZ = join(AQUI, '..', '..');
const HOSTIL = "<script>alert('x')</script> <img src=x onerror=alert(1)> ‮gnp.exe";
const AHORA = Date.UTC(2026, 10, 9, 12, 0, 0); // 2026-11-09 12:00 UTC

const alta = (id, extra = {}) => ({
  id, ts: '2026-11-08T10:00:00Z', autor: 'dueno', evento: 'alta', oferta_id: null, etapa: 'O0', titulo: `titulo ${id}`, detalle: '', severidad: 'media',
  tipo: 'pendiente', estado: 'abierta', ...extra,
});
const LINEAS = [
  alta('PUL-0001', { prioridad: 'P1', responsable: 'dueno', bloquea: ['D7', 'activar_campana'], vence: '2026-11-12', origen: 'sesion 2026-11-08', categoria: 'riesgo', severidad: 'alta' }),
  alta('PUL-0002', { prioridad: 'P0', responsable: 'dueno', bloquea: ['gasto'], vence: '2026-11-08', titulo: 'Fijar límites' }),
  alta('PUL-0003', { prioridad: 'P2', responsable: 'ia', ts: '2026-11-08T12:00:00Z' }),
  alta('PUL-0004', { prioridad: 'P3', responsable: 'robot' }),
  alta('PUL-0005', { tipo: 'pulido' }), // sin prioridad ni responsable (como las líneas viejas)
  { id: 'PUL-0006', ts: '2026-11-01T10:00:00Z', autor: 'dueno', evento: 'alta', etapa: 'D3', titulo: 'vieja', detalle: '', severidad: 'alta', tipo: 'observacion', estado: 'abierta' },
  alta('PUL-0007', { tipo: 'decision', titulo: 'Solo español de España' }),
  alta('PUL-0008', { tipo: 'leccion', titulo: 'Medir antes de afirmar' }),
  alta('PUL-0009', { tipo: 'regla_propuesta', titulo: 'Nunca prometer plazos', responsable: 'dueno', prioridad: 'P2' }),
  { id: 'PUL-0001', ts: '2026-11-08T11:00:00Z', autor: 'dueno', evento: 'estado', estado: 'en_curso' },
  alta('PUL-0010', { prioridad: 'P2', responsable: 'otro' }),
  { id: 'PUL-0010', ts: '2026-11-08T11:00:00Z', autor: 'dueno', evento: 'estado', estado: 'resuelta' },
];
const entradas = P.normalizarEntradas({ entradas: LINEAS });
const por = (id) => entradas.find((e) => e.id === id);
const { pendientes, decisiones, lecciones, reglasPropuestas } = C.clasificar(entradas);
const ids = (xs) => xs.map((e) => e.id);

// ───────────────────────── la lista única en lib/pulido.js (aditivo y retrocompatible) ─────────────────────────

test('normalizarEntradas conserva los campos nuevos y los valida; las líneas viejas quedan con valores vacíos', () => {
  const e = por('PUL-0001');
  assert.equal(e.estado, 'en_curso', 'el cambio de estado se pliega');
  assert.deepEqual([e.prioridad, e.responsable, e.categoria, e.origen, e.vence, e.tipo], ['P1', 'dueno', 'riesgo', 'sesion 2026-11-08', '2026-11-12', 'pendiente']);
  assert.deepEqual(e.bloquea, ['D7', 'activar_campana']);
  const v = por('PUL-0006');
  assert.deepEqual([v.prioridad, v.responsable, v.categoria, v.origen, v.vence, v.bloquea, v.tipo], [null, null, null, null, null, [], 'observacion']);
});

test('campos nuevos inválidos caen a valores seguros y no dejan pasar texto ajeno', () => {
  const [e] = P.normalizarEntradas([alta('PUL-0001', {
    prioridad: 'P9', responsable: 'cualquiera', categoria: 'otra', origen: 'x'.repeat(200), bloquea: ['D3', 5, '', 'y'.repeat(60), ...Array(10).fill('Z')], vence: '10/11/2026', tipo: 'invento',
  })]);
  assert.deepEqual([e.prioridad, e.responsable, e.categoria, e.vence, e.tipo], [null, null, null, null, 'observacion']);
  assert.equal(e.origen.length, 80);
  assert.equal(e.bloquea.length, 8);
  assert.equal(e.bloquea[1].length, 40);
  assert.equal(P.normalizarEntradas([alta('PUL-0002', { vence: '2026-11-12T08:00:00Z' })])[0].vence, '2026-11-12T08:00:00Z');
  assert.equal(P.normalizarEntradas([alta('PUL-0003', { bloquea: 'D3' })])[0].bloquea.length, 0, 'bloquea que no es lista = vacío');
});

test('los tipos nuevos tienen rótulo y los antiguos siguen siendo los de los formularios', () => {
  assert.deepEqual(P.TIPOS, ['observacion', 'nota', 'decision']);
  for (const t of ['pulido', 'pendiente', 'decision', 'leccion', 'regla_propuesta', 'observacion', 'nota']) {
    assert.ok(P.TIPOS_LISTA.includes(t), t);
    assert.ok(P.TITULO_TIPO[t], t);
    assert.ok(P.ROTULO_TIPO[t], t);
  }
  // Pulido valida lo mismo de siempre: el formulario viejo no se ensancha.
  assert.ok(P.validarNueva({ etapa: 'D3', titulo: 'x', tipo: 'pendiente' }).errores.tipo);
});

// ───────────────────────── cabecera: ciclo y principio ─────────────────────────

test('el ciclo de sesión tiene 4 pasos en orden: abrir, trabajar, cerrar, domingo', () => {
  assert.deepEqual(C.CICLO.map((p) => p.id), ['abrir', 'trabajar', 'cerrar', 'domingo']);
  assert.deepEqual(C.CICLO.map((p) => p.numero), [1, 2, 3, 4]);
  assert.equal(C.CICLO[0].comando, '/cerebro-abrir');
  assert.equal(C.CICLO[2].comando, '/cerebro-cerrar');
  assert.equal(C.CICLO[1].ancla, 'pendientes');
  assert.equal(C.CICLO[3].estado, 'sin_construir', 'el jardinero aún no existe y se dice');
  assert.ok(Object.isFrozen(C.CICLO));
  assert.match(C.PRINCIPIO, /sin memoria arranca de cero cada vez/i);
  assert.equal(C.TITULO, 'Cerebro: lo que el sistema recuerda');
});

// ───────────────────────── pendientes ─────────────────────────

test('clasificar reparte por tipo: pendientes, decisiones, lecciones y reglas propuestas', () => {
  assert.deepEqual(ids(pendientes).sort(), ['PUL-0001', 'PUL-0002', 'PUL-0003', 'PUL-0004', 'PUL-0005', 'PUL-0006', 'PUL-0010']);
  assert.deepEqual(ids(decisiones), ['PUL-0007']);
  assert.deepEqual(ids(lecciones), ['PUL-0008']);
  assert.deepEqual(ids(reglasPropuestas), ['PUL-0009']);
  assert.deepEqual(C.clasificar(null), { pendientes: [], decisiones: [], lecciones: [], reglasPropuestas: [] });
  assert.deepEqual(C.clasificar('x'), { pendientes: [], decisiones: [], lecciones: [], reglasPropuestas: [] });
});

test('filtros: por defecto solo abiertas; prioridad, responsable, bloquea y texto', () => {
  assert.deepEqual(ids(C.filtrarPendientes(pendientes)).sort(), ['PUL-0001', 'PUL-0002', 'PUL-0003', 'PUL-0004', 'PUL-0005', 'PUL-0006']);
  assert.ok(C.filtrarPendientes(pendientes, { verResueltas: true }).some((e) => e.id === 'PUL-0010'));
  assert.deepEqual(ids(C.filtrarPendientes(pendientes, { prioridad: 'P0' })), ['PUL-0002']);
  assert.deepEqual(ids(C.filtrarPendientes(pendientes, { prioridad: 'sin' })).sort(), ['PUL-0005', 'PUL-0006']);
  assert.deepEqual(ids(C.filtrarPendientes(pendientes, { responsable: 'dueno' })).sort(), ['PUL-0001', 'PUL-0002']);
  assert.deepEqual(ids(C.filtrarPendientes(pendientes, { responsable: 'robot' })), ['PUL-0004']);
  assert.deepEqual(ids(C.filtrarPendientes(pendientes, { responsable: 'sin' })).sort(), ['PUL-0005', 'PUL-0006']);
  assert.deepEqual(ids(C.filtrarPendientes(pendientes, { bloquea: '*' })).sort(), ['PUL-0001', 'PUL-0002']);
  assert.deepEqual(ids(C.filtrarPendientes(pendientes, { bloquea: 'D7' })), ['PUL-0001']);
  assert.deepEqual(ids(C.filtrarPendientes(pendientes, { bloquea: 'D9' })), []);
  assert.deepEqual(ids(C.filtrarPendientes(pendientes, { texto: 'LÍMITES' })), ['PUL-0002'], 'sin distinguir mayúsculas ni tildes');
  assert.deepEqual(ids(C.filtrarPendientes(pendientes, { texto: 'activar_campana' })), ['PUL-0001'], 'busca también en bloquea');
  assert.deepEqual(ids(C.filtrarPendientes(pendientes, { prioridad: 'P1', responsable: 'ia' })), [], 'los filtros se combinan');
  assert.equal(C.hayFiltros({}), false);
  assert.equal(C.hayFiltros({ prioridad: 'P1' }), true);
  assert.equal(C.hayFiltros({ verResueltas: true }), true);
});

test('valoresBloquea: ids distintos y ordenados', () => {
  assert.deepEqual(C.valoresBloquea(pendientes), ['activar_campana', 'D7', 'gasto'].sort((a, b) => a.localeCompare(b, 'es')));
  assert.deepEqual(C.valoresBloquea([]), []);
  assert.deepEqual(C.valoresBloquea([null, {}, { bloquea: 'x' }]), []);
});

test('vencimiento: vencido, hoy, próximo, lejano, sin fecha y resueltas', () => {
  const v = (vence, estado = 'abierta') => C.vencimiento({ vence, estado }, AHORA);
  assert.deepEqual(v('2026-11-08'), { estado: 'vencido', dias: -1, texto: 'venció ayer' });
  assert.equal(v('2026-11-01').texto, 'venció hace 8 días');
  assert.deepEqual(v('2026-11-09'), { estado: 'hoy', dias: 0, texto: 'vence hoy' });
  assert.deepEqual(v('2026-11-10'), { estado: 'proximo', dias: 1, texto: 'vence mañana' });
  assert.equal(v('2026-11-16').estado, 'proximo');
  assert.equal(v('2026-11-17').estado, 'lejano');
  assert.equal(v('2026-11-30T08:00:00Z').texto, 'vence el 2026-11-30');
  assert.equal(v(null).estado, 'sin');
  assert.equal(v('basura').estado, 'sin');
  assert.equal(v('2026-11-01', 'resuelta').estado, 'sin', 'una resuelta no figura como vencida');
  assert.equal(C.vencimiento(null, AHORA).estado, 'sin');
});

test('ordenar: en curso y abiertas antes que resueltas, P0 primero, sin prioridad al final; no muta', () => {
  const copia = pendientes.map((e) => e.id);
  const o = ids(C.ordenarPendientes(pendientes, AHORA));
  assert.deepEqual(pendientes.map((e) => e.id), copia, 'no muta la entrada');
  assert.equal(o[0], 'PUL-0001', 'lo que ya está en curso va primero');
  assert.equal(o[1], 'PUL-0002', 'luego P0');
  assert.equal(o[o.length - 1], 'PUL-0010', 'la resuelta al final');
  assert.deepEqual(o.slice(2, 4), ['PUL-0003', 'PUL-0004'], 'P2 antes que P3');
  // entre iguales: gravedad alta antes, y luego lo más cercano a vencer
  const dos = P.normalizarEntradas([alta('A', { prioridad: 'P2', vence: '2026-12-01' }), alta('B', { prioridad: 'P2', vence: '2026-11-10' }), alta('C', { prioridad: 'P2' })]);
  assert.deepEqual(ids(C.ordenarPendientes(dos, AHORA)), ['B', 'A', 'C']);
});

test('plural concuerda en singular y plural, y cada prioridad tiene su versión corta', () => {
  assert.equal(C.plural(1, 'vencido', 'vencidos'), '1 vencido');
  assert.equal(C.plural(0, 'vencido', 'vencidos'), '0 vencidos');
  assert.equal(C.plural(3, 'vencido', 'vencidos'), '3 vencidos');
  for (const p of C.PRIORIDADES) assert.ok(C.CORTO_PRIORIDAD[p] && C.CORTO_PRIORIDAD[p].length <= 14, p);
});

test('accionesEstado: cada estado ofrece solo movimientos válidos y el mismo estado nunca', () => {
  assert.deepEqual(C.accionesEstado('abierta').map((a) => a.a), ['en_curso', 'resuelta']);
  assert.deepEqual(C.accionesEstado('en_curso').map((a) => a.a), ['resuelta', 'abierta']);
  assert.deepEqual(C.accionesEstado('resuelta').map((a) => a.a), ['abierta']);
  for (const estado of P.ESTADOS) for (const a of C.accionesEstado(estado)) {
    assert.notEqual(a.a, estado);
    assert.doesNotThrow(() => C.cuerpoCambioEstado('PUL-0001', a.a));
  }
  assert.deepEqual(C.accionesEstado('rara').map((a) => a.a), ['abierta']);
});

test('resumenPendientes cuenta lo abierto, P0/P1, lo que te espera, vencidos y bloqueantes', () => {
  const r = C.resumenPendientes(pendientes, AHORA);
  assert.deepEqual(r, { abiertos: 6, enCurso: 1, p0: 1, p1: 1, esperanTuDecision: 2, sinResponsable: 2, vencidos: 1, porVencer: 1, bloqueantes: 2, sinPrioridad: 2 });
  assert.equal(C.resumenPendientes([], AHORA).abiertos, 0);
  assert.equal(C.resumenPendientes(null, AHORA).abiertos, 0);
});

// ───────────────────────── alta rápida ─────────────────────────

test('alta rápida mínima: solo título; etapa O0, tipo pendiente, severidad media y origen del panel', () => {
  const r = C.validarAlta({ titulo: '  Elegir canal de avisos  ' });
  assert.equal(r.ok, true);
  assert.deepEqual(r.cuerpo, { etapa: 'O0', titulo: 'Elegir canal de avisos', severidad: 'media', tipo: 'pendiente', origen: 'panel: Cerebro' });
});

test('alta rápida completa: arma cada campo y mapea prioridad a gravedad', () => {
  const r = C.validarAlta({ titulo: 'Firmar límites', detalle: ' con J4 ', tipo: 'pendiente', etapa: 'D0', prioridad: 'P0', responsable: 'dueno', bloquea: 'D7, activar_campana  OF-202611-01,D7', vence: '2026-11-20', oferta_id: '_ejemplo' });
  assert.equal(r.ok, true, JSON.stringify(r.errores));
  assert.deepEqual(r.cuerpo, {
    etapa: 'D0', titulo: 'Firmar límites', severidad: 'alta', tipo: 'pendiente', origen: 'panel: Cerebro', detalle: 'con J4', prioridad: 'P0', responsable: 'dueno',
    oferta_id: '_ejemplo', bloquea: ['D7', 'activar_campana', 'OF-202611-01'], vence: '2026-11-20',
  });
  assert.deepEqual(['P0', 'P1', 'P2', 'P3'].map((p) => C.validarAlta({ titulo: 't', prioridad: p }).cuerpo.severidad), ['alta', 'alta', 'media', 'baja']);
  for (const t of ['pendiente', 'decision', 'regla_propuesta']) assert.equal(C.validarAlta({ titulo: 't', tipo: t }).cuerpo.tipo, t);
});

test('alta rápida: errores claros y ningún cuerpo inválido sale', () => {
  const casos = [
    [{}, 'titulo'], [{ titulo: '   ' }, 'titulo'], [{ titulo: 'x'.repeat(141) }, 'titulo'], [{ titulo: 't', detalle: 'x'.repeat(4001) }, 'detalle'],
    [{ titulo: 't', tipo: 'leccion' }, 'tipo'], [{ titulo: 't', etapa: 'D99' }, 'etapa'], [{ titulo: 't', prioridad: 'P4' }, 'prioridad'], [{ titulo: 't', responsable: 'yo' }, 'responsable'],
    [{ titulo: 't', oferta_id: '../x' }, 'oferta_id'], [{ titulo: 't', bloquea: 'a/b' }, 'bloquea'], [{ titulo: 't', bloquea: '<img>' }, 'bloquea'],
    [{ titulo: 't', bloquea: Array.from({ length: 9 }, (_, i) => `D${i}`).join(',') }, 'bloquea'], [{ titulo: 't', vence: '2026-02-30' }, 'vence'], [{ titulo: 't', vence: '9/11/2026' }, 'vence'],
  ];
  for (const [f, campo] of casos) {
    const r = C.validarAlta(f);
    assert.equal(r.ok, false, JSON.stringify(f));
    assert.ok(r.errores[campo], `${campo}: ${JSON.stringify(f)}`);
  }
  assert.equal(C.validarAlta({ titulo: 'x'.repeat(140) }).ok, true);
  assert.equal(C.validarAlta({ titulo: 't', vence: '2028-02-29' }).ok, true);
});

test('alta rápida no deja colar campos ajenos ni autor/id/estado', () => {
  const r = C.validarAlta({ titulo: 't', id: 'PUL-0001', autor: 'ia', estado: 'resuelta', ts: '2020-01-01T00:00:00Z', evento: 'estado' });
  assert.deepEqual(Object.keys(r.cuerpo).sort(), ['etapa', 'origen', 'severidad', 'tipo', 'titulo']);
});

test('texto hostil en el título se conserva como dato (el servidor lo guarda íntegro y la página lo muestra como texto)', () => {
  const r = C.validarAlta({ titulo: HOSTIL });
  assert.equal(r.ok, true);
  assert.equal(r.cuerpo.titulo, HOSTIL);
});

test('partirBloquea separa por espacios, comas y punto y coma, sin repetidos', () => {
  assert.deepEqual(C.partirBloquea('D3,D4;D3  gasto'), { items: ['D3', 'D4', 'gasto'], invalidos: [] });
  assert.deepEqual(C.partirBloquea('').items, []);
  assert.deepEqual(C.partirBloquea('ok mal/uno').invalidos, ['mal/uno']);
  assert.deepEqual(C.partirBloquea(null), { items: [], invalidos: [] });
});

test('el cambio de estado reutiliza el cuerpo de Pulido (solo id y estado)', () => {
  assert.deepEqual(C.cuerpoCambioEstado('PUL-0001', 'resuelta'), { id: 'PUL-0001', estado: 'resuelta' });
  assert.throws(() => C.cuerpoCambioEstado('PUL-0001', 'borrada'), RangeError);
  assert.throws(() => C.cuerpoCambioEstado('x', 'resuelta'), RangeError);
});

// ───────────────────────── decisiones ─────────────────────────

const CEREBRO = {
  memoria: {
    carpeta: { ruta: 'empresa/memoria', existe: true },
    archivos: [{ clave: 'decisiones_dueno', ruta: 'empresa/memoria/decisiones_dueno.jsonl', titulo: 'Decisiones del dueño', existe: true, lineas: 2, bytes: 300, sha256: 'a'.repeat(64) },
      { clave: 'lecciones', ruta: 'empresa/memoria/lecciones.jsonl', titulo: 'Lecciones', existe: false, lineas: 0, bytes: null, sha256: null }],
  },
  decisiones: {
    fuentes: [
      { clave: 'decisiones_y_tareas', titulo: 'Decisiones y tareas del dueño', ruta: 'docs/00-decisiones-y-tareas-del-dueno.md', existe: true, decisiones: 11, tareas_abiertas: 31, tareas_hechas: 5, bytes: 36366, sha256: 'b'.repeat(64), modificado: '2026-11-06T15:15:24Z' },
      { clave: 'decisiones_adopcion', titulo: 'Decisiones de la adopción (J1-J9)', ruta: 'docs/_historial/mentor-sistema/decisiones-del-dueno.md', existe: true, decisiones: 9, tareas_abiertas: 0, tareas_hechas: 0, bytes: 7128, sha256: 'c'.repeat(64) },
    ],
    memoria: { ruta: 'empresa/memoria/decisiones_dueno.jsonl', existe: true, total: 2, vigentes: 1, ultimas: [{ id: 'DEC-0001', titulo: 'Vieja', vigente: false }, { id: 'DEC-0002', titulo: 'Nueva', vigente: true }] },
  },
  reglas: {
    parametros: { ruta: 'empresa/parametros.yaml', existe: true, sha256: 'd'.repeat(64), claves: 332, hipotesis: 331, sin_valor: 18, grupos: 25 },
    limites: { ruta: 'empresa/limites.yaml', existe: true, sha256: 'e'.repeat(64), sellado: false, claves: 55, sin_valor: 42 },
    autonomia: { ruta: 'empresa/autonomia.yaml', existe: true, sha256: 'f'.repeat(64), etapas: 17, por_nivel: { N0: 17 } },
    sellos_compliance: { ruta: 'empresa/compliance/sellos', archivos: 0 },
  },
  lecciones: {
    qa: {
      archivos: 3, truncado: false,
      hallazgos: [
        { oferta_id: 'OF-202611-01', demo: false, etapa: 'D3', patron_clave: 'formato', severidad: 'MENOR', descripcion: 'Mayúsculas', check_id: 'H1' },
        { oferta_id: 'OF-202611-01', demo: false, etapa: 'D4', patron_clave: 'formato', severidad: 'MENOR', descripcion: 'Otro formato', check_id: 'H2' },
        { oferta_id: 'OF-202611-02', demo: false, etapa: 'D3', patron_clave: 'evidencia', severidad: 'MAYOR', descripcion: 'Falta fuente', check_id: 'H3' },
        { oferta_id: 'OF-202611-02', demo: false, etapa: 'D3', patron_clave: null, severidad: null, descripcion: null, check_id: 'H4' },
      ],
      aprendizajes: [{ oferta_id: 'OF-202611-01', demo: false, etapa: 'D4', texto: 'Medir el tiempo antes de afirmarlo' }],
    },
    postmortems: [{ oferta_id: 'OF-202611-01', demo: false, ruta: 'ofertas/OF-202611-01/08-operacion/postmortem.json', veredicto: 'FALLIDA', causa_principal: 'creativo-debil', aprendizajes: ['Probar el gancho'], sha256: '1'.repeat(64) }],
    memoria: { ruta: 'empresa/memoria/lecciones.jsonl', existe: false, total: 0, ultimas: [] },
  },
  jardin: { ruta: 'empresa/memoria/jardin', existe: false, propuestas: 0, ultima: null },
};

test('decisiones: documentos enlazados y contados, guardadas vigentes y anotadas en la bitácora', () => {
  const d = C.resumenDecisiones(CEREBRO, entradas);
  assert.equal(d.fuentes.length, 2);
  assert.equal(d.enDocumentos, 20);
  assert.equal(d.tareasAbiertasDocumentos, 31);
  assert.equal(d.fuentes[0].ruta, 'docs/00-decisiones-y-tareas-del-dueno.md');
  assert.equal(d.fuentes[0].sha256, 'b'.repeat(64));
  assert.deepEqual(d.guardadas.map((x) => x.id), ['DEC-0002'], 'solo las vigentes');
  assert.equal(d.vigentesGuardadas, 1);
  assert.deepEqual(ids(d.anotadas), ['PUL-0007']);
  assert.equal(d.sinDatos, false);
  assert.equal(d.hayDocumentos, true);
});

test('decisiones sin nada: vacío honesto y ningún cero inventado', () => {
  const d = C.resumenDecisiones({ decisiones: { fuentes: [{ clave: 'a', ruta: 'docs/x.md', existe: false }], memoria: { existe: false, ultimas: [] } } }, []);
  assert.equal(d.sinDatos, true);
  assert.equal(d.hayDocumentos, false);
  assert.equal(d.fuentes[0].decisiones, null);
  assert.equal(C.resumenDecisiones(null, null).sinDatos, true);
  assert.equal(C.resumenDecisiones(undefined).fuentes.length, 0);
});

// ───────────────────────── reglas ─────────────────────────

test('reglas: tarjetas de solo lectura con su ruta y hash, y las propuestas esperando tu aprobación', () => {
  const r = C.resumenReglas(CEREBRO, entradas);
  assert.deepEqual(r.tarjetas.map((t) => t.clave), ['parametros', 'limites', 'autonomia', 'sellos']);
  const [par, lim, aut, sel] = r.tarjetas;
  assert.equal(par.valor, '332 valores');
  assert.match(par.detalle, /331 son hipótesis/);
  assert.equal(lim.valor, 'Sin tu firma');
  assert.equal(lim.tono, 'aviso');
  assert.match(lim.detalle, /42 de 55 datos sin fijar/);
  assert.match(aut.detalle, /17 en el nivel 0/);
  assert.equal(sel.valor, '0 firmados');
  assert.equal(par.sha256, 'd'.repeat(64));
  assert.deepEqual(ids(r.propuestas), ['PUL-0009']);
  assert.equal(r.hayArchivos, true);
  const sellado = C.resumenReglas({ reglas: { limites: { existe: true, sellado: true, claves: 5, sin_valor: 0 } } }, []);
  assert.deepEqual([sellado.tarjetas[1].valor, sellado.tarjetas[1].tono], ['Firmados por ti', 'ok']);
});

test('reglas sin archivos: lo dice y no inventa números', () => {
  const r = C.resumenReglas({}, []);
  assert.equal(r.hayArchivos, false);
  assert.equal(r.tarjetas[0].valor, null);
  assert.match(r.tarjetas[0].detalle, /No se encontró/);
  assert.deepEqual(r.propuestas, []);
  assert.equal(C.resumenReglas(null).tarjetas.length, 4);
});

test('una regla propuesta resuelta ya no espera tu aprobación', () => {
  const l = [...LINEAS, { id: 'PUL-0009', ts: '2026-11-09T09:00:00Z', autor: 'dueno', evento: 'estado', estado: 'resuelta' }];
  assert.deepEqual(C.resumenReglas(CEREBRO, P.normalizarEntradas(l)).propuestas, []);
});

// ───────────────────────── lecciones ─────────────────────────

test('lecciones: patrones de QA más repetidos, aprendizajes, post-mortems y las anotadas', () => {
  const l = C.resumenLecciones(CEREBRO, entradas);
  assert.equal(l.hallazgos, 4);
  assert.deepEqual(l.top.map((t) => [t.patron, t.n]), [['formato', 2], ['(sin patrón)', 1], ['evidencia', 1]].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'es')));
  assert.equal(l.top[0].ofertas, 1);
  assert.deepEqual(l.top[0].etapas, ['D3', 'D4']);
  assert.equal(l.porSeveridad.MENOR, 2);
  assert.equal(l.porSeveridad['sin severidad'], 1);
  assert.equal(l.aprendizajes.length, 1);
  assert.equal(l.postmortems[0].veredicto, 'FALLIDA');
  assert.deepEqual(ids(l.anotadas), ['PUL-0008']);
  assert.equal(l.todosDemo, false);
  assert.equal(l.vacio, false);
});

test('lecciones: todo de la oferta de ejemplo se marca como demostración; sin nada es vacío', () => {
  const demo = C.resumenLecciones({ lecciones: { qa: { archivos: 1, hallazgos: [{ oferta_id: '_ejemplo', demo: true, patron_clave: 'a', descripcion: 'x' }], aprendizajes: [] }, postmortems: [], memoria: { ultimas: [] } } }, []);
  assert.equal(demo.todosDemo, true);
  assert.equal(demo.vacio, false);
  const nada = C.resumenLecciones({ lecciones: { qa: { archivos: 0, hallazgos: [], aprendizajes: [] }, postmortems: [], memoria: { ultimas: [] } } }, []);
  assert.deepEqual([nada.vacio, nada.todosDemo, nada.hallazgos, nada.top], [true, false, 0, []]);
  assert.equal(C.resumenLecciones(null, null).vacio, true);
  assert.equal(C.resumenLecciones('x').vacio, true);
});

// ───────────────────────── jardín y detalle técnico ─────────────────────────

test('jardín: hoy sin datos; si hubiera propuestas, dice cuántas esperan tu clic', () => {
  const hoy = C.estadoJardin(CEREBRO);
  assert.deepEqual([hoy.propuestas, hoy.tono], [0, 'neutro']);
  assert.match(hoy.titulo, /Sin datos/);
  const con = C.estadoJardin({ jardin: { propuestas: 3, ultima: '2026-W46.json', ruta: 'empresa/memoria/jardin' } });
  assert.deepEqual([con.propuestas, con.tono, con.ultima], [3, 'acento', '2026-W46.json']);
  assert.match(C.estadoJardin({ jardin: { propuestas: 1 } }).titulo, /1 propuesta espera/);
  assert.equal(C.estadoJardin(null).propuestas, 0);
  assert.equal(C.JARDIN_PASOS.length, 4);
  assert.ok(C.JARDIN_PASOS.some((p) => /simulacro/.test(p)));
  assert.ok(C.JARDIN_PASOS.some((p) => /nada se borra/i.test(p)));
});

test('rutas técnicas: cada lectura con su ruta y hash', () => {
  const filas = C.rutasTecnicas(CEREBRO);
  const rutas = filas.map((f) => f.ruta);
  for (const r of ['empresa/panel/pulido.jsonl', 'empresa/memoria/decisiones_dueno.jsonl', 'empresa/memoria/lecciones.jsonl', 'docs/00-decisiones-y-tareas-del-dueno.md',
    'empresa/parametros.yaml', 'empresa/limites.yaml', 'empresa/autonomia.yaml', 'empresa/memoria/jardin']) assert.ok(rutas.includes(r), r);
  assert.equal(filas.find((f) => f.ruta === 'empresa/parametros.yaml').sha256, 'd'.repeat(64));
  assert.equal(C.rutasTecnicas(null).length, 1, 'sin datos del Cerebro queda al menos la lista única');
});

test('firmaDatos cambia cuando cambia algo que se ve y no por ruido', () => {
  const a = C.firmaDatos({ entradas: LINEAS }, CEREBRO);
  assert.equal(a, C.firmaDatos({ entradas: LINEAS }, JSON.parse(JSON.stringify(CEREBRO))));
  assert.notEqual(a, C.firmaDatos({ entradas: [...LINEAS, alta('PUL-0099')] }, CEREBRO));
  const otro = JSON.parse(JSON.stringify(CEREBRO));
  otro.memoria.archivos[0].sha256 = 'z'.repeat(64);
  assert.notEqual(a, C.firmaDatos({ entradas: LINEAS }, otro));
  assert.doesNotThrow(() => C.firmaDatos(null, null));
});

// ───────────────────────── tolerancia y seguridad ─────────────────────────

test('ninguna función lanza con datos basura', () => {
  for (const basura of [null, undefined, 5, 'texto', [], {}, [null, 5, 'x'], { a: 1 }]) {
    assert.doesNotThrow(() => {
      C.clasificar(basura); C.filtrarPendientes(basura); C.ordenarPendientes(basura); C.resumenPendientes(basura); C.valoresBloquea(basura);
      C.resumenDecisiones(basura, basura); C.resumenReglas(basura, basura); C.resumenLecciones(basura, basura); C.estadoJardin(basura);
      C.rutasTecnicas(basura); C.vencimiento(basura); C.validarAlta(basura === null || basura === undefined ? undefined : { titulo: basura });
    });
  }
});

test('el código de la pantalla nunca usa innerHTML, eval ni escribe fuera de la bitácora', () => {
  for (const archivo of ['dashboard/web/pages/cerebro.js', 'dashboard/web/lib/cerebro.js']) {
    const fuente = readFileSync(join(RAIZ, archivo), 'utf8');
    for (const prohibido of [/\binnerHTML\b/, /\bouterHTML\b/, /\binsertAdjacentHTML\b/, /document\.write/, /\beval\s*\(/, /new Function/, /\bsetAttribute\(\s*['"]on/]) {
      assert.doesNotMatch(fuente, prohibido, `${archivo}: ${prohibido}`);
    }
  }
  const pagina = readFileSync(join(RAIZ, 'dashboard/web/pages/cerebro.js'), 'utf8');
  const posts = [...pagina.matchAll(/api\.post\(\s*([^,)]+)/g)].map((m) => m[1].trim());
  assert.ok(posts.length > 0);
  for (const p of posts) assert.match(p, /^['"]\/pulido['"]$/, 'la única escritura del panel aquí es la bitácora de pulido');
  assert.doesNotMatch(pagina, /api\.(post|get|sobre)\(\s*['"]\/(pausa|accion|parametros|job|freno)/, 'no hay llamada que toque pausa, acciones ni reglas');
});

test('la página declara su ruta, grupo y que escucha los cambios de empresa y ofertas', async () => {
  const fuente = readFileSync(join(RAIZ, 'dashboard/web/pages/cerebro.js'), 'utf8');
  assert.match(fuente, /export const meta = \{[^}]*ruta: 'cerebro'/);
  assert.match(fuente, /grupo: 'Cerebro'/);
  assert.match(fuente, /escucha: \[[^\]]*'empresa'/);
});
