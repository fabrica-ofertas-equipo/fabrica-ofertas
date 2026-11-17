// pages/cumplimiento.js — #/cumplimiento: dictámenes de X1 como tarjetas por etapa (semáforo, puntaje, hallazgos citados), sellos con su estado visual
// (vigente / vencido / alterado) y lint de claims por oferta (CONTRATO §4 `GET /cumplimiento`; rediseño U4).
// Fuentes: ofertas/<id>/qa/x1-*.json y empresa/compliance/sellos/<sha256>.json. SOLO LECTURA: sellar y verificar son `python -m compliance.*`.
// X1 es veto transversal: un FAIL o un sello vencido/alterado se muestra con todas sus letras, nunca se suaviza.

import { ayudasVista, instalarEstilos } from '../lib/operacion.js';
import {
  modeloCumplimiento, abreviarHash, comandosCumplimiento, estadoDictamen, textoVigencia, dictamenesAEnriquecer, aplicarDetalles, SEMAFOROS,
  veredictoHumano, estadoHallazgoHumano, SEMAFORO_HUMANO, ICONO_SELLO, nombreEtapaX1, geometriaPuntaje, atencionCumplimiento,
} from '../lib/cumplimiento.js';

export const meta = { ruta: 'cumplimiento', titulo: 'Cumplimiento', grupo: 'Países', icono: 'escudo', escucha: ['empresa', 'oferta'] };

const UI = { oferta: '' };

function hayEdicion() {
  const d = globalThis.document;
  const a = d && d.activeElement;
  return Boolean(a && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) || Boolean(d && d.querySelector('.modal-fondo'));
}

const tonoSemaforo = (s) => SEMAFOROS[s] || 'neutro';
const botonActualizar = (ctx) => ctx.ui.el('button', { type: 'button', class: 'btn btn--chico', onclick: () => ctx.recargar() }, ctx.ui.icono('refrescar', { tam: 14 }), 'Actualizar');
const decimal = (n) => String(n).replace('.', ',');
const humano = (k) => { const t = String(k ?? '').replace(/[_-]+/g, ' ').trim(); return t ? t.charAt(0).toUpperCase() + t.slice(1) : ''; };

// ───────────────────────── métricas ─────────────────────────

function metricas(ctx, m) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const c = m.conteoSellos;
  const vetos = (m.dictamenesPorVeredicto.FAIL || 0) + (m.dictamenesPorVeredicto.ESCALAR || 0);
  const bloqueantes = m.ultimos.reduce((a, d) => a + (d.bloqueantes || 0), 0);
  const sinDetalle = m.ultimos.filter((d) => d.soloResumen).length;
  const aprobadas = m.ultimos.filter((d) => d.veredicto === 'PASS' || d.veredicto === 'PASS_CON_NOTAS').length;
  return el('div', { class: 'p5-metricas' },
    ui.metrica({ etiqueta: 'Etapas revisadas', valor: fmt.num(m.ultimos.length), ayuda: 'dictamen', contexto: el('span', { class: 'p5-sub' }, `${aprobadas} aprobadas · ${m.dictamenes.length} informes en total (se cuenta el más reciente de cada etapa)`) }),
    ui.metrica({ etiqueta: 'Etapas bloqueadas', valor: fmt.num(vetos), tono: vetos ? 'critico' : 'ok', contexto: el('span', { class: 'p5-sub' }, vetos ? 'Cumplimiento las frena: no avanzan hasta corregir' : 'Ninguna etapa bloqueada') }),
    ui.metrica({ etiqueta: 'Hallazgos bloqueantes', valor: fmt.num(bloqueantes), ayuda: 'severidad_hallazgo', tono: bloqueantes ? 'critico' : sinDetalle ? 'aviso' : 'ok', contexto: el('span', { class: 'p5-sub' }, sinDetalle ? `${sinDetalle} informe(s) sin detalle cargado: el recuento puede estar incompleto` : 'Abiertos en los informes más recientes') }),
    ui.metrica({
      etiqueta: 'Vistos buenos vigentes', valor: fmt.num(c.vigente), ayuda: 'vigencia_sello', tono: c.alterado || c.ilegible ? 'critico' : c.vencido ? 'aviso' : c.vigente ? 'ok' : null,
      contexto: el('div', { class: 'p5-fila p5-fila--junta' }, c.vencido ? ui.chip(`${c.vencido} vencido(s)`, 'aviso') : null, c.alterado ? ui.chip(`${c.alterado} alterado(s)`, 'error') : null, c.ilegible ? ui.chip(`${c.ilegible} ilegible(s)`, 'error') : null, c.desconocido ? ui.chip(`${c.desconocido} sin vigencia`, 'neutro', { icono: false }) : null, !c.vencido && !c.alterado && !c.ilegible && !c.desconocido ? el('span', { class: 'p5-sub' }, 'Ninguno vencido ni alterado') : null),
    }),
    ui.metrica({ etiqueta: 'Aprobadas sin firmar', valor: fmt.num(m.sinSello.length), ayuda: 'sello_x1', tono: m.sinSello.length ? 'aviso' : null, contexto: el('span', { class: 'p5-sub' }, m.sinSello.length ? 'Sin visto bueno firmado no se puede activar ni publicar' : 'Todo lo aprobado está firmado') }));
}

// ───────────────────────── dictámenes como tarjetas por etapa ─────────────────────────

function listaHallazgos(ctx, d, ayudas) {
  const { ui } = ctx;
  const { el } = ui;
  if (d.soloResumen) {
    return ayudas.aviso('aviso', `El panel solo recibió el resumen de este informe (${d.nHallazgos === null ? 'nº de hallazgos desconocido' : `${d.nHallazgos} hallazgo(s)`}): no se pudo leer el archivo completo. Ábrelo en `, el('code', null, d.archivo || 'qa/'), '.');
  }
  if (!d.hallazgos.length) {
    return el('div', { class: 'p5-pila p5-pila--chica' }, el('span', { class: 'cifra-sin-dato' }, 'Sin hallazgos'), d.justificacion ? el('span', { class: 'p5-sub' }, `Justificación de la revisión: ${d.justificacion}`) : el('span', { class: 'p5-causa' }, 'Sin hallazgos y sin explicación: la revisión tiene que justificar por qué no encontró nada.'));
  }
  return el('div', { class: 'p5-lista-hallazgos' }, d.hallazgos.map((h) => el('article', { class: `p5-hallazgo p5-hallazgo--${h.tono}` },
    el('div', { class: 'p5-fila p5-fila--junta' }, ui.chip(h.severidad ? h.severidad.charAt(0) + h.severidad.slice(1).toLowerCase() : (h.severidadCruda || 'Sin severidad'), h.tono), h.estado ? ui.chip(estadoHallazgoHumano(h.estado), h.abierto ? 'aviso' : 'ok', { icono: false }) : null, h.patron_clave ? el('span', { class: 'p5-sub' }, humano(h.patron_clave), ui.soloTecnico(el('span', { class: 'p5-mono' }, ` (${h.patron_clave})`))) : null),
    el('div', null, h.descripcion || el('span', { class: 'cifra-sin-dato' }, 'sin descripción')),
    h.cita ? el('div', { class: 'p5-cita', title: 'Texto exacto o archivo que respalda el hallazgo' }, h.cita) : el('span', { class: 'p5-causa' }, 'Sin cita: un hallazgo sin prueba no cuenta'),
    h.correccion ? el('div', { class: 'p5-sub' }, el('strong', null, 'Corrección segura: '), h.correccion) : null,
    ui.detalleTecnico('Identificador del hallazgo', el('span', { class: 'p5-mono' }, h.check_id || '—')))));
}

function tarjetaDictamen(ctx, d, ayudas, ahora) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const v = veredictoHumano(d.veredicto);
  const vig = estadoDictamen(d, ahora);
  const geo = geometriaPuntaje(d.puntaje, d.umbral);
  const resumenSev = ['BLOQUEANTE', 'MAYOR', 'MENOR', 'MEJORA'].map((s) => [s, d.hallazgos.filter((h) => h.severidad === s && h.abierto).length]).filter(([, n]) => n);
  const tonoTarjeta = d.veredicto === 'FAIL' ? 'error' : (d.veredicto === 'ESCALAR' || vig.estado === 'vencido' || d.semaforo === 'amarillo') ? 'aviso' : d.semaforo === 'rojo' ? 'error' : 'ok';
  const claims = d.claims && d.claims.length
    ? el('ul', { class: 'p5-checks' }, d.claims.map((c) => el('li', null, el('span', { class: 'p5-mono' }, c.claim_id), ' → ', el('span', { class: 'p5-mono' }, c.evidencia_ref || 'sin prueba'))))
    : (d.claims === null ? el('span', { class: 'cifra-sin-dato' }, 'sin dato (solo resumen)') : el('span', { class: 'cifra-sin-dato' }, 'sin afirmaciones con prueba citada'));
  const detalle = el('div', { class: 'p5-pila' },
    el('h4', { class: 'p5-titulo-chico' }, `Hallazgos (${d.nHallazgos === null ? '?' : d.nHallazgos})`), listaHallazgos(ctx, d, ayudas),
    el('h4', { class: 'p5-titulo-chico' }, 'Afirmaciones con su prueba ', ui.ayuda('claim')), claims,
    d.riesgos.length ? el('div', { class: 'p5-pila p5-pila--chica' }, el('h4', { class: 'p5-titulo-chico' }, 'Riesgos que quedan'), el('ul', { class: 'p5-checks' }, d.riesgos.map((r) => el('li', null, r)))) : null,
    ui.detalleTecnico('Datos técnicos del informe', ui.kv([
      ['Versión y ronda', `${d.version || '—'}${d.ronda ? ` · ronda ${d.ronda}` : ''}`], ['Archivo revisado', d.artefacto_ref ? el('span', { class: 'p5-mono' }, d.artefacto_ref) : null],
      ['Huella del archivo revisado', d.artefacto_sha256 ? el('span', { class: 'p5-mono', title: d.artefacto_sha256 }, d.artefacto_sha256) : null], ['Versión de las reglas', d.reglas_version], ['Políticas desde', d.politicas_fecha_min ? fmt.fecha(d.politicas_fecha_min) : null],
      ['Vigencia hasta', d.vigencia_hasta ? fmt.fecha(d.vigencia_hasta) : null], ['Creado', d.creado_en ? fmt.fecha(d.creado_en, { segundos: true }) : null], ['Firma del sistema', d.firmado ? 'presente' : 'ausente'], ['Archivo', d.archivo ? el('span', { class: 'p5-mono' }, d.archivo) : null]])));
  return el('article', { class: `p5-dict p5-dict--${tonoTarjeta}` },
    el('div', { class: 'p5-dict__cab' },
      el('div', { class: 'p5-dict__etapa' }, el('span', { class: 'p5-dict__nombre' }, nombreEtapaX1(d.etapa_objetivo)), el('span', { class: 'p5-dict__codigo' }, `${d.etapa_objetivo || '—'}${d.version ? ` · ${d.version}` : ''}${d.ronda ? ` · ronda ${d.ronda}` : ''}`)),
      el('div', { class: 'p5-dict__veredicto' }, ui.chip(v.texto, v.tono, { icono: v.icono }), ui.soloTecnico(el('span', { class: 'p5-dict__codigo', title: 'Código del resultado' }, v.tecnico)))),
    el('div', { class: 'p5-fila p5-fila--junta' },
      d.semaforo ? ui.chip(`Semáforo ${d.semaforo}`, tonoSemaforo(d.semaforo)) : ui.chip('Sin semáforo', 'neutro', { icono: 'circulo-punteado' }),
      d.semaforo ? el('span', { class: 'p5-sub' }, SEMAFORO_HUMANO[d.semaforo]) : null),
    geo
      ? el('div', { class: 'p5-puntaje' }, el('div', { class: 'p5-puntaje__cab' }, el('span', null, 'Puntaje de la revisión'), el('span', null, el('strong', null, decimal(d.puntaje)), ` de 5${d.umbral !== null ? ` · mínimo ${decimal(d.umbral)}` : ''}`)),
        ayudas.medidor({ bp: Math.round(geo.puntaje * 100), zona: geo.aprueba === false ? 'rojo' : 'ok', texto: geo.aprueba === null ? 'sin umbral' : (geo.aprueba ? 'por encima del mínimo' : 'por debajo del mínimo'), etiqueta: `Puntaje ${d.puntaje} de 5`, marca: geo.umbral }))
      : el('span', { class: 'cifra-sin-dato' }, 'Sin puntaje'),
    el('div', { class: 'p5-hallazgos-resumen' },
      d.soloResumen ? ui.chip(`${d.nHallazgos === null ? '?' : d.nHallazgos} hallazgos (sin detalle)`, 'neutro', { icono: 'circulo-punteado' })
        : (resumenSev.length ? resumenSev.map(([s, n]) => ui.chip(`${n} ${s.toLowerCase()}${n === 1 ? '' : 's'} abierto${n === 1 ? '' : 's'}`, s === 'BLOQUEANTE' ? 'error' : s === 'MAYOR' ? 'aviso' : 'info', { icono: s === 'BLOQUEANTE' || s === 'MAYOR' ? undefined : false }))
          : ui.chip(d.hallazgos.length ? 'Todos los hallazgos resueltos' : 'Sin hallazgos', 'ok'))),
    el('div', { class: 'p5-fila p5-fila--junta' }, ui.chip(vig.estado === 'vencido' ? 'Informe vencido' : vig.estado === 'vigente' ? 'Informe vigente' : 'Sin vigencia declarada', vig.tono, { icono: vig.estado === 'vigente' ? 'ok' : vig.estado === 'vencido' ? 'reloj-alerta' : 'circulo-punteado' }), el('span', { class: 'p5-sub', title: d.vigencia_hasta ? fmt.fecha(d.vigencia_hasta) : '' }, vig.estado === 'desconocido' ? '' : vig.texto)),
    el('details', { class: 'p5-expand' }, el('summary', { class: 'p5-expand__cab' }, ui.icono('chevron-derecha', { tam: 14, clase: 'p5-expand__chev' }), `Ver hallazgos y pruebas${d.nHallazgos ? ` (${d.nHallazgos})` : ''}`), detalle));
}

function seccionDictamenes(ctx, m, ayudas, sobre, ahora) {
  const { ui } = ctx;
  const { el } = ui;
  if (!m.ultimos.length) {
    return ui.seccion('Revisión de cumplimiento por etapa', ayudas.vacioConComandos('Cumplimiento todavía no revisó ninguna etapa.', {
      pista: 'Antes de activar una campaña o publicar una página de venta, cumplimiento revisa la etapa (afirmaciones, políticas de Meta y Stripe, líneas rojas) y deja un informe: aprobado o bloqueado, con los problemas que encontró y su cita.',
      archivo: 'ofertas/<id>/qa/x1-<etapa>-v<n>.json',
      comandos: [{ etiqueta: 'Revisar las afirmaciones de una etapa (solo mira, no cambia nada)', cmd: comandosCumplimiento().lint }],
      fuente: sobre ? sobre.fuente : undefined,
    }), { glosario: 'dictamen' });
  }
  const ofertas = [...new Set(m.ultimos.map((d) => d.oferta_id).filter(Boolean))].sort();
  const cont = el('div', { class: 'p5-pila' });
  const pintar = () => {
    const visibles = m.ultimos.filter((d) => !UI.oferta || d.oferta_id === UI.oferta);
    const grupos = new Map();
    for (const d of visibles) { const k = d.oferta_id || 'empresa'; if (!grupos.has(k)) grupos.set(k, []); grupos.get(k).push(d); }
    ui.reemplazar(cont, grupos.size ? [...grupos.entries()].map(([oferta, lista]) => el('div', { class: 'p5-dict-grupo' }, el('h3', { class: 'p5-titulo-chico' }, oferta === 'empresa' ? 'Empresa (sin oferta)' : `Oferta ${oferta}`), el('div', { class: 'p5-dict-grid' }, lista.map((d) => tarjetaDictamen(ctx, d, ayudas, ahora))))) : ui.vacio('Ningún informe con este filtro.'));
  };
  const sel = el('select', { class: 'campo campo--chico', 'aria-label': 'Filtrar por oferta', onchange: (ev) => { UI.oferta = ev.target.value; pintar(); } },
    el('option', { value: '' }, 'Todas las ofertas'), ofertas.map((o) => el('option', { value: o, selected: o === UI.oferta ? true : null }, o)));
  pintar();
  return ui.seccion('Revisión de cumplimiento por etapa', el('div', { class: 'p5-pila' }, ofertas.length > 1 ? el('div', { class: 'p5-filtros' }, el('span', { class: 'p5-filtros__etiqueta' }, ui.icono('filtro', { tam: 14 }), 'Filtrar'), sel) : null, cont),
  { glosario: 'dictamen', ayuda: 'Se muestra el informe más reciente de cada etapa. Un informe vencido deja de valer aunque diga aprobado. Despliega una tarjeta para ver cada hallazgo con su cita.' });
}

// ───────────────────────── sellos ─────────────────────────

const FIRMAS = { ed25519: ['Firma digital', 'ok'], hmac: ['Firma de pruebas (no vale en real)', 'aviso'], otra: ['Firma desconocida', 'error'] };
const TIPO_FIRMA = { ed25519: 'Ed25519', hmac: 'HMAC', otra: 'desconocida' };

function tarjetaSello(ctx, s, ahora) {
  const { ui, fmt } = ctx;
  const { el } = ui;
  const vig = s.vigencia;
  const textos = { vigente: 'Vigente', vencido: 'Vencido', alterado: 'Alterado', ilegible: 'Ilegible', desconocido: 'Sin vigencia' };
  return el('article', { class: `p5-sello p5-sello--${vig.tono === 'neutro' ? '' : vig.tono}` },
    el('div', { class: 'p5-sello__cab' },
      el('div', { class: 'p5-dict__etapa' }, el('span', { class: 'p5-dict__nombre' }, s.ilegible ? 'Visto bueno ilegible' : nombreEtapaX1(s.etapa_objetivo)), el('span', { class: 'p5-dict__codigo' }, s.ilegible ? (s.archivo || '') : `${s.oferta_id || 'empresa'} · ${s.etapa_objetivo || '—'}`)),
      ui.chip(textos[vig.estado] || vig.texto, vig.tono, { icono: ICONO_SELLO[vig.estado] })),
    vig.causa ? el('p', { class: vig.estado === 'vigente' ? 'p5-sub' : 'p5-causa' }, vig.causa) : null,
    s.ilegible ? null : el('div', { class: 'p5-fila p5-fila--junta' },
      s.vigencia_hasta ? el('span', { class: 'p5-sub', title: fmt.fecha(s.vigencia_hasta) }, `Vale hasta ${fmt.fecha(s.vigencia_hasta)} · ${textoVigencia(s.vigencia_hasta, ahora)}`) : el('span', { class: 'cifra-sin-dato' }, 'sin fecha de vigencia'),
      s.firma ? ui.chip(FIRMAS[s.firma][0], FIRMAS[s.firma][1]) : el('span', { class: 'cifra-sin-dato', title: 'El panel no lee la firma; el comando de comprobación sí la verifica' }, 'firma no informada'),
      s.emitido_en ? el('span', { class: 'p5-sub' }, 'Emitido ', ui.tiempo(s.emitido_en)) : null),
    vig.estado === 'vigente' ? null : ui.comando(comandosCumplimiento(s.oferta_id || 'OF-AAAAMM-NN', s.etapa_objetivo || 'D5').sellar, { titulo: 'Cómo renovar este visto bueno', nota: 'Lo ejecutas tú: la firma la emite el código con una clave que ninguna IA tiene.' }),
    ui.detalleTecnico('Datos técnicos de la firma', ui.kv([
      ['Tipo de firma', s.firma ? TIPO_FIRMA[s.firma] : null], ['Huella del archivo revisado', s.artefacto_sha256 ? el('span', { class: 'p5-mono' }, s.artefacto_sha256) : null], ['Informe citado', s.dictamen_ref ? el('span', { class: 'p5-mono' }, s.dictamen_ref) : null],
      ['Elementos firmados', s.object_ids && s.object_ids.length ? String(s.object_ids.length) : null], ['Versión de las reglas', s.reglas_version], ['Archivo', s.archivo ? el('span', { class: 'p5-mono' }, s.archivo) : null]])));
}

function seccionSellos(ctx, m, ayudas, sobre, ahora) {
  const { ui } = ctx;
  const { el } = ui;
  const sin = m.sinSello.length
    ? ayudas.aviso('aviso', el('strong', null, 'Aprobadas sin visto bueno firmado: '), m.sinSello.map((d) => `${d.oferta_id || 'empresa'} · ${nombreEtapaX1(d.etapa_objetivo)} (${d.version})`).join(' · '), el('span', { class: 'p5-sub' }, ' — sin esa firma no se activa ni se publica.'),
      ui.comando(comandosCumplimiento(m.sinSello[0].oferta_id || 'OF-AAAAMM-NN', m.sinSello[0].etapa_objetivo || 'D5').sellar, { titulo: 'Cómo firmarlo (lo haces tú)' }))
    : null;
  if (!m.sellos.length) {
    return ui.seccion('Vistos buenos firmados', el('div', { class: 'p5-pila' }, sin, ayudas.vacioConComandos('Todavía no hay vistos buenos firmados.', {
      pista: 'Un visto bueno firmado liga lo revisado (por su huella) a un informe aprobado y a una fecha de vencimiento. Si lo revisado cambia o el plazo vence, deja de valer. Lo emite el código con una clave que ninguna IA tiene.',
      archivo: 'empresa/compliance/sellos/<sha256>.json',
      comandos: [{ etiqueta: 'Firmar una etapa con su informe (lo haces tú)', cmd: comandosCumplimiento().sellar }, { etiqueta: 'Comprobar un visto bueno antes de usarlo', cmd: comandosCumplimiento().verificar }],
      fuente: sobre ? sobre.fuente : undefined,
    })), { glosario: 'sello_x1' });
  }
  return ui.seccion('Vistos buenos firmados', el('div', { class: 'p5-pila' }, sin, el('div', { class: 'p5-sellos' }, m.sellos.map((s) => tarjetaSello(ctx, s, ahora))),
    el('p', { class: 'p5-sub' }, 'El panel marca «alterado» cuando lo revisado (o el informe citado) ya no es igual a lo que se firmó. Que la firma sea auténtica lo comprueba el comando de abajo.'),
    ui.comando(comandosCumplimiento().verificar, { titulo: 'Cómo comprobar un visto bueno' })),
  { glosario: 'vigencia_sello', ayuda: 'Vigente: dentro de plazo y sin cambios. Vencido: se renueva firmando de nuevo. Alterado: el contenido o el informe ya no son los que se firmaron; no lo uses.' });
}

// ───────────────────────── lint de claims ─────────────────────────

function seccionLint(ctx, m, ayudas) {
  const { ui } = ctx;
  const { el } = ui;
  if (!m.lint.length) {
    return ui.seccion('Revisión de afirmaciones por oferta', ayudas.vacioConComandos('Sin informes ni revisión de afirmaciones que mostrar.', {
      pista: 'La revisión automática busca promesas de cura o plazo (salud), ingresos garantizados o cambios del cuerpo o del dinero, garantías absolutas, urgencia falsa y prueba social fabricada.',
      archivo: 'ofertas/<id>/qa/x1-*.json (claims_trazados) y la salida de compliance.lint_claims',
      comandos: [{ etiqueta: 'Revisar una etapa', cmd: comandosCumplimiento().lint }],
    }), { glosario: 'lint_claims' });
  }
  const tarjetas = m.lint.map((o) => el('article', { class: 'p5-detalle' },
    el('div', { class: 'p5-fila p5-fila--junta' }, el('strong', null, o.oferta_id), o.semaforo ? ui.chip(`Semáforo ${o.semaforo}`, tonoSemaforo(o.semaforo)) : ui.chip('Sin semáforo', 'neutro', { icono: 'circulo-punteado' }), el('span', { class: 'p5-sub' }, `Etapas: ${o.etapas.map(nombreEtapaX1).join(', ') || '—'}`),
      ...['BLOQUEANTE', 'MAYOR', 'MENOR', 'MEJORA'].filter((s) => o.porSeveridad[s]).map((s) => ui.chip(`${o.porSeveridad[s]} ${s.toLowerCase()}${o.porSeveridad[s] === 1 ? '' : 's'} abierto${o.porSeveridad[s] === 1 ? '' : 's'}`, s === 'BLOQUEANTE' ? 'error' : s === 'MAYOR' ? 'aviso' : 'info', { icono: s === 'BLOQUEANTE' || s === 'MAYOR' ? undefined : false }))),
    o.sinTrazar.length ? ayudas.aviso('aviso', `Sin afirmaciones con prueba citada en ${o.sinTrazar.map(nombreEtapaX1).join(', ')}: cada afirmación de la página de venta o del anuncio debe citar su prueba.`) : null,
    o.sinDetalle.length ? ayudas.aviso('aviso', `Solo hay resumen (sin afirmaciones) de ${o.sinDetalle.map(nombreEtapaX1).join(', ')}: no se pudo leer el informe completo.`) : null,
    o.claims.length
      ? ui.tabla({ etiqueta: `Afirmaciones de ${o.oferta_id}`, filas: o.claims, vacio: 'Sin afirmaciones.', columnas: [{ clave: 'claim_id', titulo: 'Afirmación', formato: (v) => el('span', { class: 'p5-mono' }, v) }, { clave: 'etapa', titulo: 'Etapa', formato: (v) => nombreEtapaX1(v) }, { clave: 'evidencia_ref', titulo: 'Prueba citada', clase: 'cel-larga', formato: (v) => (v ? el('span', { class: 'p5-mono' }, v) : el('span', { class: 'p5-causa' }, 'sin prueba')) }] })
      : el('span', { class: 'cifra-sin-dato' }, 'sin afirmaciones con prueba citada'),
    ...o.lints.map((l) => el('div', { class: 'p5-pila' }, el('h3', { class: 'p5-titulo-chico' }, `Revisión automática · etapa ${nombreEtapaX1(l.etapa)} · reglas ${l.reglas_version || '—'}`),
      l.hallazgos.length ? el('div', { class: 'p5-lista-hallazgos' }, l.hallazgos.map((h) => el('article', { class: `p5-hallazgo p5-hallazgo--${tonoSemaforo(h.nivel)}` }, el('div', { class: 'p5-fila p5-fila--junta' }, ui.chip(h.nivel ? `Riesgo ${h.nivel}` : 'sin nivel', tonoSemaforo(h.nivel)), el('span', { class: 'p5-sub' }, humano(h.categoria), h.categoria ? ui.soloTecnico(el('span', { class: 'p5-mono' }, ` (${h.categoria})`)) : null), h.locale ? ui.chip(h.locale, 'neutro', { icono: false }) : null), el('div', null, h.descripcion), h.evidencia ? el('div', { class: 'p5-cita' }, h.evidencia) : null))) : el('span', { class: 'cifra-sin-dato' }, 'la revisión automática no encontró nada')))));
  return ui.seccion('Revisión de afirmaciones por oferta', el('div', { class: 'p5-pila' }, ...tarjetas),
    { glosario: 'lint_claims', ayuda: 'Semáforo = el peor de los informes más recientes. Ninguna afirmación sobre salud, ingresos o resultados pasa sin una prueba citada.' });
}

// ───────────────────────── página ─────────────────────────

export async function render(ctx) {
  const { api, ui, fmt } = ctx;
  const { el } = ui;
  instalarEstilos(ui);
  const ayudas = ayudasVista(ui, fmt);
  const cab = ui.encabezadoPagina({
    titulo: 'Cumplimiento',
    descripcion: 'Antes de publicar o activar algo, cumplimiento revisa promesas, anuncios y páginas. Aquí ves el resultado de cada etapa, los problemas que encontró y hasta cuándo vale cada visto bueno firmado. Puede frenar cualquier etapa: aquí se ve por qué.',
    acciones: [botonActualizar(ctx)],
  });
  let sobre;
  try { sobre = await api.sobre('/cumplimiento'); } catch (e) { return el('div', { class: 'pagina' }, cab, ui.errorBox(e, { reintentar: () => ctx.recargar() })); }
  const ahora = Date.now();
  // El panel entrega resúmenes de los dictámenes: se pide el archivo completo de los más recientes (hallazgos, citas, claims).
  const pedidos = dictamenesAEnriquecer(sobre.datos);
  const detalles = new Map();
  await Promise.all(pedidos.map(async (p) => {
    try {
      const r = await api.sobre(`/oferta/${encodeURIComponent(p.oferta_id)}/archivo`, { ruta: p.ruta });
      const c = r && r.datos ? r.datos.contenido : null;
      const obj = c && typeof c === 'object' ? c : (typeof c === 'string' ? JSON.parse(c) : null);
      if (obj && typeof obj === 'object') detalles.set(`${p.oferta_id}|${p.ruta}`, obj);
    } catch (_) { /* queda el resumen y la pantalla lo dice */ }
  }));
  const m = modeloCumplimiento(aplicarDetalles(sobre.datos, detalles), { ahora });
  if (!m.hay) {
    return el('div', { class: 'pagina' }, cab,
      ayudas.vacioConComandos('Todavía no hay informes ni vistos buenos de cumplimiento.', {
        compacto: false,
        pista: 'Cumplimiento deja un informe por etapa y una firma por cada versión aprobada. Hasta entonces no hay nada que mostrar: nunca se da nada por aprobado por defecto.',
        archivo: 'ofertas/<id>/qa/x1-*.json · empresa/compliance/sellos/*.json',
        comandos: [{ etiqueta: 'Revisar las afirmaciones de una etapa', cmd: comandosCumplimiento().lint }, { etiqueta: 'Firmar una etapa con su informe (lo haces tú)', cmd: comandosCumplimiento().sellar }],
        fuente: sobre.fuente,
      }), ui.fuenteInfo(sobre));
  }
  return el('div', { class: 'pagina' }, cab,
    ui.atencion({ items: atencionCumplimiento(m, ahora), vacio: 'Todo en orden: ninguna etapa bloqueada ni visto bueno vencido o alterado.' }),
    metricas(ctx, m),
    seccionDictamenes(ctx, m, ayudas, sobre, ahora), seccionSellos(ctx, m, ayudas, sobre, ahora), seccionLint(ctx, m, ayudas),
    ui.fuenteInfo(sobre));
}

/** Actualización en vivo: re-renderiza conservando el filtro, salvo que se esté escribiendo. */
export async function alCambio(ctx) {
  if (hayEdicion()) return undefined;
  return render(ctx);
}
