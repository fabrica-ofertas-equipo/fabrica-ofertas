// pages/avisos.js — #/avisos: «Avisos: lo que te llega al celular y por qué». Las alertas abiertas con su severidad (calculadas ahora con los archivos del proyecto por GET /alertas, con
// filtros simples y a quién le toca cada una; si esa ruta no responde, las guardadas en empresa/datos/alertas.jsonl vía GET /finanzas) y el informe de las 08:30 (GET /informe),
// cómo llegarían al celular según su gravedad, el canal (hoy sin elegir: pendiente del dueño), el resumen diario (hoy no existe) y qué avisa cada robot.
// SOLO LECTURA. Todo texto que viene de los archivos (regla, acción sugerida, valores) entra por textContent. La lógica pura vive en ../lib/avisos.js.

import { ui, el, icono } from '../ui.js';
import { CSS_COMUN, CSS_AVISOS } from '../lib/estilos-n1.js';
import * as L from '../lib/avisos.js';
import * as A from '../lib/ausencia.js';
import { instalar as instalarAusencia, chipQuien, cuerpoInforme } from '../lib/ausencia-vista.js';

export const meta = { ruta: 'avisos', titulo: 'Avisos', grupo: 'Robots', icono: 'campana', escucha: ['empresa', 'registro'] };

const FUENTES = ['empresa/datos/alertas.jsonl', 'empresa/finanzas/ledger.jsonl'];
const MAX_CERRADAS = 10;

/** Cabecera de pantalla con la rejilla contenida (en móvil, la lista de pestañas no ensancha la página). */
function cabecera(opciones) {
  const c = ui.encabezadoPagina(opciones);
  c.classList.add('n1-cab');
  return c;
}

async function leer(ctx, ruta) {
  try { return { ok: true, sobre: await ctx.api.sobre(ruta) }; } catch (err) { return { ok: false, err, sobre: null }; }
}

const sevDe = (clave) => L.SEVERIDADES.find((s) => s.clave === clave) || { etiqueta: 'Sin gravedad', tono: 'neutro', icono: 'circulo' };

function filaAlerta(a, ahoraMs, { cerrada = false } = {}) {
  const sev = sevDe(a.clave);
  const hora = L.horaAlerta(a, ahoraMs);
  const valor = a.calculada ? (a.medida ? `Medida: ${a.medida}` : null) : L.fraseValor(a);
  return el('li', { class: 'n1-alerta', 'data-tono': cerrada ? 'neutro' : a.tono, 'data-severidad': a.clave },
    el('div', { class: 'n1-pila n1-pila--chica' },
      ui.chip(a.etiquetaSeveridad || sev.etiqueta, sev.tono, { icono: sev.icono }),
      ui.chip(a.estadoInfo.texto, a.estadoInfo.tono, { icono: false })),
    el('div', null,
      el('h3', { class: 'n1-alerta__titulo' }, a.titulo),
      a.accion_sugerida ? el('p', { class: 'n1-alerta__accion' }, a.accion_sugerida) : null,
      a.detalle ? el('p', { class: 'n1-alerta__accion' }, el('strong', null, 'Detalle: '), a.detalle) : null,
      a.quien || a.enlace || a.comando ? el('div', { class: 'au-alerta-extra' },
        chipQuien(a.quien),
        a.enlace ? ui.enlace(`Ir a ${A.nombrePantalla(a.enlace) || 'la pantalla'}`, a.enlace, { class: 'btn btn--chico' }) : null,
        a.comando && !cerrada ? ui.comando(a.comando, { titulo: 'Cómo hacerlo', nota: 'Lo ejecutas tú en la Terminal: este panel no lo hace por ti.' }) : null) : null,
      el('div', { class: 'n1-alerta__meta' },
        a.oferta_id ? el('span', null, a.oferta_id) : el('span', null, 'Toda la empresa'),
        valor ? el('span', null, valor) : null,
        a.sinUmbral && !a.calculada ? el('span', null, 'Gris: sin límite fijado, nunca verde') : null),
      ui.detalleTecnico('Detalle técnico', () => el('dl', { class: 'n1-kv' },
        el('dt', null, 'Regla'), el('dd', null, a.regla_id || '—'),
        el('dt', null, 'Id de la alerta'), el('dd', null, a.id === null ? '—' : String(a.id)),
        el('dt', null, 'Origen'), el('dd', null, a.origen || '—'),
        el('dt', null, 'Severidad en el archivo'), el('dd', null, a.severidad === null ? '—' : String(a.severidad)),
        el('dt', null, 'Estado en el archivo'), el('dd', null, a.estado === null ? '—' : String(a.estado)),
        el('dt', null, 'Nivel de riesgo'), el('dd', null, a.nivel || '—'),
        el('dt', null, 'Nicho'), el('dd', null, a.macro_nicho || '—')))),
    el('time', { class: 'n1-alerta__hora', title: hora.absoluta }, hora.relativa));
}

function listaAlertas(items, ahoraMs, etiqueta) {
  return el('ul', { class: 'n1-alertas', 'aria-label': etiqueta }, items.map((a) => filaAlerta(a, ahoraMs)));
}

/** Filtros simples (gravedad y a quién le toca) sobre las alertas abiertas; se repinta solo la lista. */
function abiertasConFiltros(modelo, ahoraMs) {
  const filtro = { gravedad: 'todas', quien: 'todas' };
  const cuentas = A.contarPorGravedad(modelo.abiertas);
  const lista = el('div', { class: 'n1-pila n1-pila--chica', 'data-lista': 'abiertas' });
  const pintar = () => {
    const vistas = A.filtrarAlertas(modelo.abiertas, filtro);
    ui.reemplazar(lista,
      el('p', { class: 'au-conteo', role: 'status' }, vistas.length === modelo.abiertas.length ? `${vistas.length} ${vistas.length === 1 ? 'alerta abierta' : 'alertas abiertas'}` : `Se muestran ${vistas.length} de ${modelo.abiertas.length} alertas abiertas`),
      vistas.length ? listaAlertas(vistas, ahoraMs, 'Alertas abiertas') : ui.vacio('Ninguna alerta abierta con ese filtro.', { icono: 'filtro' }));
  };
  const barra = el('div', { class: 'au-filtros', role: 'group', 'aria-label': 'Filtros de alertas' },
    el('div', { class: 'au-filtros__grupo' }, el('span', { class: 'au-filtros__etiqueta' }, 'Gravedad:'),
      ui.segmentado({ opciones: A.FILTROS_GRAVEDAD.map((o) => ({ ...o, etiqueta: `${o.etiqueta} (${cuentas[o.valor]})` })), valor: 'todas', etiqueta: 'Filtrar por gravedad', onCambio: (v) => { filtro.gravedad = v; pintar(); } })),
    el('div', { class: 'au-filtros__grupo' }, el('span', { class: 'au-filtros__etiqueta' }, 'A quién le toca:'),
      ui.segmentado({ opciones: A.FILTROS_QUIEN, valor: 'todas', etiqueta: 'Filtrar por a quién le toca', onCambio: (v) => { filtro.quien = v; pintar(); } })));
  pintar();
  return el('div', { class: 'n1-pila' }, barra, lista);
}

function estadoArchivo(calc) {
  const e = A.estadoArchivoAlertas(calc.archivo);
  return el('div', { class: 'n1-aviso' + (e.tono === 'ok' ? ' n1-aviso--info' : '') }, icono(e.tono === 'ok' ? 'ok' : 'alerta', { tam: 18 }),
    el('div', null, ui.termino('archivo_alertas', { texto: 'Archivo de alertas guardado' }), el('strong', null, `: ${e.texto.toLowerCase()}. `), e.detalle, ' ',
      !calc.archivo.alDia && calc.archivo.comandoEscribir ? ui.comando(calc.archivo.comandoEscribir, { titulo: 'Cómo guardarlas', nota: 'Lo ejecuta una persona (o el planificador, cuando exista); este panel nunca escribe las alertas.' }) : null));
}

function pendientesDeCalcular(calc) {
  if (!calc.pendientes.length) return null;
  return ui.detalleTecnico(`Reglas que todavía no se calculan (${calc.pendientes.length}): faltan datos de ventas y gasto`, () => el('ul', { class: 'au-pendientes' }, calc.pendientes.map((p) => el('li', null,
    el('b', null, `${p.reglaId} · ${p.nombre}`), el('span', null, `Necesita: ${p.requiere}`), el('span', { class: 'n1-tenue' }, `Se leería de: ${p.archivo} · Le toca a: ${p.de}`)))));
}

function seccionAlertas(rFin, modelo, ahoraMs, calc = null) {
  if (calc) {
    const cuerpo = [estadoArchivo(calc)];
    if (!modelo.abiertas.length) cuerpo.push(ui.vacio('No hay alertas abiertas entre las que se pueden calcular con los archivos. Ojo: las de ventas y gasto todavía no se calculan, así que un cero acá no prueba que todo esté bien.', { icono: 'ok' }));
    else cuerpo.push(abiertasConFiltros(modelo, ahoraMs));
    if (modelo.cerradas.length) {
      const mostrar = modelo.cerradas.slice(0, MAX_CERRADAS);
      cuerpo.push(el('div', { class: 'n1-pila n1-pila--chica' }, el('h3', { class: 'n1-subtitulo' }, `Cerradas (${modelo.cerradas.length})`),
        el('ul', { class: 'n1-alertas', 'aria-label': 'Alertas cerradas' }, mostrar.map((a) => filaAlerta(a, ahoraMs, { cerrada: true })))));
    }
    const pend = pendientesDeCalcular(calc);
    if (pend) cuerpo.push(pend);
    return el('div', { class: 'n1-pila' }, cuerpo);
  }
  if (!rFin.ok) return ui.errorBox(rFin.err);
  if (!modelo.hay) {
    return ui.vacioConPasos({
      titulo: 'Todavía no hay alertas registradas',
      explicacion: 'Las alertas las calcula un programa que las anota en un archivo, una línea por alerta. Mientras ese programa no corra, «cero alertas» no significa «todo en orden»: significa que nadie las está calculando.',
      icono: 'campana',
      pasos: [
        { texto: 'Para calcularlas y guardarlas, ejecuta este comando (sin --escribir solo las muestra):', comando: '.venv/bin/python -m scripts.alertas.producir --escribir' },
        { texto: 'Cuando haya alertas, aquí vas a ver cada una con su gravedad, qué hacer y desde cuándo está abierta.' },
        { texto: 'Mientras tanto, las cifras que no cuadran se ven en Finanzas y los bloqueos en el Historial.' },
      ],
    });
  }
  const cuerpo = [];
  if (!modelo.abiertas.length) cuerpo.push(ui.vacio('No hay alertas abiertas: todas las registradas están cerradas.', { icono: 'ok' }));
  else cuerpo.push(el('ul', { class: 'n1-alertas', 'aria-label': 'Alertas abiertas' }, modelo.abiertas.map((a) => filaAlerta(a, ahoraMs))));
  if (modelo.cerradas.length) {
    const mostrar = modelo.cerradas.slice(0, MAX_CERRADAS);
    cuerpo.push(el('div', { class: 'n1-pila n1-pila--chica' },
      el('h3', { class: 'n1-subtitulo' }, `Cerradas (${modelo.cerradas.length})`),
      el('ul', { class: 'n1-alertas', 'aria-label': 'Alertas cerradas' }, mostrar.map((a) => filaAlerta(a, ahoraMs, { cerrada: true }))),
      modelo.cerradas.length > mostrar.length ? el('p', { class: 'n1-nota' }, `Se muestran las ${mostrar.length} primeras; hay ${modelo.cerradas.length - mostrar.length} más cerradas.`) : null));
  }
  return el('div', { class: 'n1-pila' }, cuerpo);
}

function tablaGravedad() {
  return el('div', { class: 'n1-tabla-caja' },
    el('table', { class: 'n1-ruta' },
      el('caption', { class: 'solo-lectores' }, 'Cómo llegaría cada gravedad (propuesta sin decidir)'),
      el('thead', null, el('tr', null, el('th', { scope: 'col' }, 'Gravedad'), el('th', { scope: 'col' }, 'Qué significa'), el('th', { scope: 'col' }, 'Adónde llegaría (propuesta)'))),
      el('tbody', null, L.SEVERIDADES.map((s) => el('tr', { 'data-severidad': s.clave },
        el('td', null, ui.chip(s.etiqueta, s.tono, { icono: s.icono })),
        el('td', null, s.significa),
        el('td', null, s.donde))))));
}

function seccionCanal(canal) {
  return el('div', { class: 'n1-pila' },
    el('div', { class: 'n1-aviso' }, icono('alerta', { tam: 18 }),
      el('div', null, el('strong', null, `${DECISION().titulo}: `), `${canal.texto.toLowerCase()}. `, 'Opciones: ', DECISION().opciones.join(' · '), '. ', DECISION().siguiente)),
    el('div', { class: 'n1-canal' }, L.EXPLICACION_CANAL.map((e) => el('div', { 'data-canal': e.id },
      el('h3', null, e.titulo, e.ayuda ? ui.ayuda(e.ayuda) : null),
      el('p', null, e.texto)))),
    el('div', { class: 'n1-pila n1-pila--chica' },
      el('h3', { class: 'n1-subtitulo' }, ui.termino('plantilla_fija', { texto: 'Así sería un aviso (la forma, no un aviso real)' })),
      el('pre', { class: 'n1-muestra' }, L.PLANTILLA.muestra),
      el('div', { class: 'n1-canal' },
        el('div', null, el('h3', null, 'Lleva siempre'), el('ul', { class: 'n1-lista' }, L.PLANTILLA.campos.map((c) => el('li', null, c)))),
        el('div', null, el('h3', null, 'Nunca lleva'), el('ul', { class: 'n1-lista' }, L.PLANTILLA.prohibido.map((c) => el('li', null, c)))))));
}
const DECISION = () => L.DECISION_PENDIENTE;

function seccionResumen() {
  const r = L.RESUMEN_DIARIO;
  return ui.vacioConPasos({
    titulo: 'Todavía no hay resumen diario',
    explicacion: `Cada día a las ${r.hora} te llegaría un solo mensaje con ${r.contiene.map((c) => c.toLowerCase()).join(', ')}. ${r.produce} lo generaría con un programa (cifras armadas con una forma fija, sin texto libre). Hoy no existe: no hay ningún resumen enviado ni programado.`,
    icono: 'campana',
    pasos: [
      ...r.falta.map((f) => ({ texto: `${f}.` })),
      { texto: 'Cuando exista, aquí vas a ver el último resumen enviado, a qué hora y por qué canal.' },
    ],
  });
}

function seccionAvisadores(lista) {
  return el('ul', { class: 'n1-avisadores' }, lista.map((a) => el('li', { class: 'n1-avisador', 'data-aviso': a.id },
    el('div', { class: 'n1-fila n1-fila--entre' },
      el('h3', null, a.robot ? ui.termino(`robot_${{ vigia: 'vigia', alarma: 'alarma', informe: 'informe' }[a.id]}`, { texto: a.quien }) : a.quien),
      ui.chip(a.estado.texto, a.estado.tono, { icono: a.estado.clave === 'parcial' ? 'progreso' : (a.estado.clave === 'planeado' ? 'reloj' : 'circulo-punteado') })),
    el('p', null, a.avisa),
    el('div', { class: 'n1-fila n1-fila--nowrap' }, icono('reloj', { tam: 14 }), el('span', { class: 'n1-nota n1-cadencia' }, a.cuando)),
    el('div', { class: 'n1-fila' }, el('span', { class: 'n1-nota' }, 'Gravedad:'), ui.chip(a.sev.etiqueta, a.sev.tono, { icono: a.sev.icono })),
    a.detalle ? el('p', { class: 'n1-nota' }, el('strong', null, 'Hoy: '), a.detalle) : null)));
}

export async function render(ctx) {
  ui.instalarEstilos('n1-comun', CSS_COMUN);
  ui.instalarEstilos('n1-avisos', CSS_AVISOS);
  instalarAusencia();
  const ahoraMs = Date.now();
  const [rFin, rSis, rAle, rInf] = await Promise.all([leer(ctx, '/finanzas'), leer(ctx, '/sistema'), leer(ctx, '/alertas'), leer(ctx, '/informe')]);
  const sistema = rSis.ok ? rSis.sobre.datos : null;
  // Las alertas se calculan ahora con los archivos del proyecto (GET /alertas); si esa ruta no responde, se usan las guardadas (GET /finanzas).
  const calc = rAle.ok ? A.modeloAlertasCalculadas(rAle.sobre.datos) : null;
  const informe = rInf.ok ? A.modeloInforme(rInf.sobre.datos) : null;
  let modelo = L.modeloAlertas(calc ? { alertas: calc.crudas } : (rFin.ok ? rFin.sobre.datos : null));
  if (calc) modelo = { ...modelo, abiertas: A.enriquecerAlertas(modelo.abiertas, calc.extras), cerradas: A.enriquecerAlertas(modelo.cerradas, calc.extras) };
  const canal = A.canalDesdeSemaforo(calc && calc.semaforo) || L.estadoCanal(null);

  const atencion = ui.atencion({ items: L.atencionAvisos(modelo, canal), vacio: 'Sin alertas abiertas y con el canal listo.' });
  const metricas = el('div', { class: 'n1-metricas' }, L.metricasAvisos(modelo, canal, rFin.ok || Boolean(calc), informe).map((m) => ui.metrica({
    etiqueta: m.etiqueta, valor: m.valor, contexto: m.contexto, tono: m.tono || undefined, ayuda: m.ayuda,
  })));
  const fuentes = calc && rAle.sobre.fuente.length ? rAle.sobre.fuente : (rFin.ok ? (rFin.sobre.fuente.length ? rFin.sobre.fuente : FUENTES) : FUENTES);
  const leidoEn = calc ? rAle.sobre.generado_en : (rFin.ok ? rFin.sobre.generado_en : null);

  return el('div', { class: 'pagina' },
    cabecera({
      titulo: 'Avisos: lo que te llega al celular y por qué',
      descripcion: 'Qué alertas hay abiertas, cuáles te llegarían al celular según su gravedad y qué falta para que te avisen de verdad. Hoy nada sale del panel: el canal al celular está pendiente de que lo elijas.',
      acciones: [ui.fuente(fuentes, { leido: leidoEn }),
        el('button', { type: 'button', class: 'btn btn--chico', onclick: () => ctx.recargar() }, icono('refrescar', { tam: 14 }), 'Actualizar')],
    }),
    atencion, metricas,
    ui.seccion('Alertas abiertas', seccionAlertas(rFin, modelo, ahoraMs, calc), { glosario: 'severidad_alerta', acciones: [ui.enlace('Ver si te puedes ausentar', '#/resumen', { class: 'btn btn--chico' }), ui.enlace('Ver Finanzas', '#/finanzas', { class: 'btn btn--chico' })] }),
    ui.seccion('Cómo te avisarían según la gravedad', tablaGravedad(), { ayuda: 'Propuesta sin decidir: hoy ninguna sale del panel. Cada nivel tiene forma, color y texto propios; el color nunca va solo.' }),
    ui.seccion('El canal al celular', seccionCanal(canal), { glosario: 'canal_avisos', acciones: [ui.chip(canal.texto, canal.tono, { icono: 'alerta' })] }),
    ui.seccion('El resumen diario', informe ? cuerpoInforme(informe, { ahoraMs }) : seccionResumen(), { glosario: 'resumen_diario' }),
    ui.seccion('Qué avisa cada robot', seccionAvisadores(L.avisadores(sistema)), { ayuda: 'Quién te avisaría de qué, a qué hora y con qué gravedad. «Parcial» significa que existe una parte del código; ninguno puede salir al celular mientras no haya canal.' }));
}
