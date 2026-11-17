// lib/ausencia.js — lógica pura (datos → modelo de vista) del semáforo «¿Me puedo ausentar?» (Resumen), de las alertas calculadas y del informe de las 08:30 (Avisos).
// Sin DOM: probable con `node --test`. Entradas = lo que devuelven GET /alertas y GET /informe (dashboard/api_alertas.py); todo texto que viene de un archivo es DATO
// no confiable: aquí se recorta y se normaliza, y las páginas lo pintan SIEMPRE con textContent. Solo lectura: nada de esto firma, activa, gasta ni borra la PAUSA.

// ───────────────────────── niveles y responsables ─────────────────────────

/** Los tres colores del semáforo. Cada uno lleva forma (icono) y palabra además del color: el color nunca va solo. */
export const NIVELES = {
  rojo: { clave: 'rojo', tono: 'error', icono: 'octogono', etiqueta: 'Rojo', corta: 'Todavía no', orden: 0 },
  amarillo: { clave: 'amarillo', tono: 'aviso', icono: 'alerta', etiqueta: 'Amarillo', corta: 'Con cuidado', orden: 1 },
  verde: { clave: 'verde', tono: 'ok', icono: 'ok', etiqueta: 'Verde', corta: 'Sí', orden: 2 },
};

/** A quién le toca cada cosa (los mismos códigos que el servidor: dueno · S-A · S-B · S-C). */
export const RESPONSABLES = {
  dueno: { clave: 'dueno', corto: 'Tú', largo: 'Te toca a ti', tono: 'acento' },
  'S-A': { clave: 'S-A', corto: 'Equipo S-A', largo: 'Le toca al equipo de contratos y documentos (S-A)', tono: 'neutro' },
  'S-B': { clave: 'S-B', corto: 'Equipo técnico (S-B)', largo: 'Le toca al equipo técnico (S-B)', tono: 'neutro' },
  'S-C': { clave: 'S-C', corto: 'Equipo del panel (S-C)', largo: 'Le toca al equipo del panel (S-C)', tono: 'neutro' },
};
export const responsableDe = (codigo) => (typeof codigo === 'string' && Object.prototype.hasOwnProperty.call(RESPONSABLES, codigo) ? RESPONSABLES[codigo] : null);

/** Pantallas a las que puede enlazar un paso (lista cerrada: un enlace que llega del servidor solo se usa si cae acá). */
const PANTALLAS = new Set(['resumen', 'tareas', 'cerebro', 'pulido', 'skills', 'registro', 'fabrica', 'landing', 'poscompra', 'jurado', 'descubrimiento', 'ofertas', 'campanas', 'operacion', 'robots', 'avisos', 'pagos', 'agentes', 'sistema', 'paises', 'cumplimiento', 'finanzas', 'parametros', 'quien-decide']);
export function enlaceSeguro(ruta) {
  if (typeof ruta !== 'string' || ruta.length > 60) return null;
  const m = /^#\/([a-z][a-z-]{1,24})$/.exec(ruta);
  if (m && PANTALLAS.has(m[1])) return ruta;
  return /^#\/oferta\/OF-[0-9]{6}-[0-9]{2}$/.test(ruta) ? ruta : null;
}

const NOMBRES_PANTALLA = {
  resumen: 'Resumen', tareas: 'Mis tareas', cerebro: 'Cerebro', pulido: 'Mejoras pendientes', skills: 'Guías de trabajo', registro: 'Historial', fabrica: 'Fábrica', landing: 'Página de venta',
  poscompra: 'Después de la venta', jurado: 'Jurado', descubrimiento: 'Radar de ofertas', ofertas: 'Ofertas', campanas: 'Campañas', operacion: 'Resultados', robots: 'Robots', avisos: 'Avisos',
  pagos: 'Pagos', agentes: 'Equipo de IA', sistema: 'Salud del sistema', paises: 'Países', cumplimiento: 'Cumplimiento', finanzas: 'Finanzas', parametros: 'Límites y reglas', 'quien-decide': 'Quién decide qué',
};
/** «Salud del sistema» para `#/sistema`; «la oferta» para `#/oferta/OF-…`; null si el enlace no es válido. Los nombres son los que ve la persona (GUIA_DE_LENGUAJE §5). */
export function nombrePantalla(enlace) {
  const ok = enlaceSeguro(enlace);
  if (!ok) return null;
  if (ok.startsWith('#/oferta/')) return 'la oferta';
  return NOMBRES_PANTALLA[ok.slice(2)] || null;
}

const txt = (v, max = 300) => (typeof v === 'string' ? v.slice(0, max) : '');
const entero = (v) => (Number.isSafeInteger(v) ? v : null);
const lista = (v) => (Array.isArray(v) ? v : []);
const esObjeto = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
/** Un comando solo se muestra (copiable) si es una línea de texto razonable; nunca se ejecuta desde acá. */
export const comandoSeguro = (c) => (typeof c === 'string' && c.length > 0 && c.length <= 400 && !/[\u0000-\u001f\u007f‪-‮⁦-⁩]/.test(c) ? c : null);

// ───────────────────────── semáforo ─────────────────────────

function normalizarPaso(p) {
  if (!esObjeto(p) || !NIVELES[p.nivel]) return null;
  const quien = responsableDe(p.responsable);
  return {
    paso: entero(p.paso), id: txt(p.id, 40), titulo: txt(p.titulo, 160), nivel: p.nivel, info: NIVELES[p.nivel], estado: txt(p.estado, 300), queHacer: txt(p.que_hacer, 400),
    responsable: quien ? quien.clave : null, quien, enlace: enlaceSeguro(p.enlace), enlaceTexto: txt(p.enlace_texto, 60) || 'Abrir', comando: comandoSeguro(p.comando), nota: txt(p.nota, 300) || null,
  };
}

/**
 * El semáforo «¿Me puedo ausentar?» listo para pintar, o null si el servidor no lo trajo (entonces la página no inventa uno).
 * → { nivel, info, titulo, resumen, conteos:{rojo, amarillo, verde}, faltan, paraTi, pasos:[…lo que falta, en orden…], listos:[…lo que ya está…], comoSeCalcula, calculadoEn }
 */
export function modeloSemaforo(datos) {
  const s = esObjeto(datos) ? datos.semaforo : null;
  if (!esObjeto(s) || !NIVELES[s.nivel]) return null;
  const pasos = lista(s.pasos).map(normalizarPaso).filter(Boolean).slice(0, 30);
  const listos = lista(s.comprobaciones).filter((c) => esObjeto(c) && c.nivel === 'verde').map(normalizarPaso).filter(Boolean).slice(0, 30);
  const c = esObjeto(s.conteos) ? s.conteos : {};
  return {
    nivel: s.nivel, info: NIVELES[s.nivel], titulo: txt(s.titulo, 120), resumen: txt(s.resumen, 500),
    conteos: { rojo: entero(c.rojo) ?? pasos.filter((p) => p.nivel === 'rojo').length, amarillo: entero(c.amarillo) ?? pasos.filter((p) => p.nivel === 'amarillo').length, verde: entero(c.verde) ?? listos.length },
    faltan: entero(s.faltan) ?? pasos.length, paraTi: entero(s.para_ti) ?? pasos.filter((p) => p.responsable === 'dueno').length,
    pasos, listos, comoSeCalcula: txt(s.como_se_calcula, 700), calculadoEn: txt(s.calculado_en, 30) || null,
  };
}

/**
 * El estado del canal de avisos tal como lo ve el semáforo (`{elegido, tono, texto, titulo}`, la misma forma que lib/avisos.js › estadoCanal), o null si no hay semáforo.
 * Verde = dos canales probados · amarillo = hay canal pero falta el segundo o probarlo · rojo = ninguno elegido.
 */
export function canalDesdeSemaforo(modelo) {
  if (!modelo) return null;
  if (modelo.listos.some((p) => p.id === 'canal')) return { elegido: true, tono: 'ok', texto: 'Elegido', titulo: 'Dos canales, probados' };
  const paso = modelo.pasos.find((p) => p.id === 'canal');
  if (!paso) return null;
  if (paso.nivel === 'amarillo') return { elegido: true, tono: 'aviso', texto: 'Incompleto', titulo: paso.estado || 'Falta el segundo canal o probar la entrega' };
  return { elegido: false, tono: 'aviso', texto: 'Sin elegir', titulo: 'Falta elegir el canal de avisos al celular' };
}

/** Frase para el número grande del semáforo en una métrica o en la paleta: «Todavía no» · «Con cuidado» · «Sí». */
export const fraseCorta = (modelo) => (modelo ? modelo.info.corta : 'Sin dato');

// ───────────────────────── alertas calculadas ─────────────────────────

/** Nombres en lenguaje simple de las reglas NUEVAS «F2-AUS-*» (docs/04 §5 trae F2-A01…A17; estas se piden a S-A en coordinacion-sesiones.md). */
export const NOMBRE_REGLA_AUSENCIA = {
  'F2-AUS-PLAN': 'Todavía no hay planificador',
  'F2-AUS-PAUSA': 'PAUSA (freno de emergencia) puesta',
  'F2-AUS-FRENO': 'Freno de la captura de anuncios puesto',
  'F2-AUS-LIM': 'Límites de dinero sin fijar',
  'F2-AUS-SELLO': 'Límites sin tu firma',
  'F2-AUS-CANAL': 'Avisos al celular sin dos canales',
  'F2-AUS-META': 'Cuenta de Meta sin dejar lista',
  'F2-AUS-CORREO': 'Correo para entregar el producto sin dejar listo',
  'F2-AUS-SALDO': 'Saldo de la cuenta de anuncios bajo',
  'F2-AUS-GATE': 'Firma que espera por ti',
  'F2-AUS-VENCE': 'Pendiente tuyo vencido',
};

/**
 * Lo que trae GET /alertas, sin perder las filas del esquema: `crudas` (se normalizan con lib/finanzas.js › normalizarAlertas, como las de Finanzas) y
 * `extras` por id (título, a quién le toca, enlace, comando, detalle: lo que el archivo de alertas no guarda). null si no hay datos de alertas.
 * → { crudas, extras:{id: extra}, resumen, archivo, pendientes, calculadas, semaforo }
 */
export function modeloAlertasCalculadas(datos) {
  if (!esObjeto(datos) || !Array.isArray(datos.alertas)) return null;
  const extras = {};
  const crudas = [];
  for (const a of datos.alertas.slice(0, 200)) {
    if (!esObjeto(a) || typeof a.id !== 'string') continue;
    crudas.push(a);
    const r = responsableDe(a.responsable);
    extras[a.id] = {
      titulo: txt(a.titulo, 160) || null, responsable: r ? r.clave : null, quien: r, area: txt(a.area, 20) || null, enlace: enlaceSeguro(a.enlace), comando: comandoSeguro(a.comando),
      detalle: txt(a.detalle, 160) || null, medida: txt(a.medida, 120) || null, fuente: a.fuente === 'archivo' ? 'archivo' : 'calculada',
    };
  }
  const r = esObjeto(datos.resumen) ? datos.resumen : {};
  const ar = esObjeto(datos.archivo) ? datos.archivo : {};
  return {
    crudas, extras,
    resumen: { abiertas: entero(r.abiertas) ?? 0, cerradas: entero(r.cerradas) ?? 0, rojas: entero(r.rojas) ?? 0, naranjas: entero(r.naranjas) ?? 0, amarillas: entero(r.amarillas) ?? 0, info: entero(r.info) ?? 0, paraTi: entero(r.para_ti) ?? 0 },
    archivo: { ruta: txt(ar.ruta, 80), existe: ar.existe === true, actualizadoEn: txt(ar.actualizado_en, 30) || null, lineas: entero(ar.lineas) ?? 0, alDia: ar.al_dia === true, ilegible: ar.ilegible === true, comandoEscribir: comandoSeguro(ar.comando_escribir) },
    pendientes: lista(datos.reglas && datos.reglas.pendientes).filter(esObjeto).slice(0, 30).map((p) => ({ reglaId: txt(p.regla_id, 20), nombre: txt(p.nombre, 100), requiere: txt(p.requiere, 200), archivo: txt(p.archivo, 200), de: txt(p.de, 6) })),
    calculadas: lista(datos.reglas && datos.reglas.calculadas).filter((x) => typeof x === 'string').slice(0, 40),
    semaforo: modeloSemaforo(datos),
  };
}

/** Suma a las filas ya normalizadas (`modeloAlertas().abiertas/cerradas`) lo que solo trae el servidor: título específico, a quién le toca, enlace, comando y detalle. */
export function enriquecerAlertas(filas, extras) {
  const mapa = esObjeto(extras) ? extras : {};
  return lista(filas).map((a) => {
    const e = a && typeof a.id === 'string' && Object.prototype.hasOwnProperty.call(mapa, a.id) ? mapa[a.id] : null;
    if (!e) return a;
    // En las calculadas «valor / umbral» son una marca de presencia (1 contra 0): se muestra la `medida` en palabras en su lugar.
    return { ...a, titulo: e.titulo || a.titulo, quien: e.quien, responsable: e.responsable, area: e.area, enlace: e.enlace, comando: e.comando, detalle: e.detalle, medida: e.medida, deArchivo: e.fuente === 'archivo', calculada: e.fuente !== 'archivo' };
  });
}

export const FILTROS_GRAVEDAD = [
  { valor: 'todas', etiqueta: 'Todas' },
  { valor: 'graves', etiqueta: 'Rojas y naranjas', titulo: 'Las que piden decisión ya' },
  { valor: 'amarilla', etiqueta: 'Amarillas' },
  { valor: 'info', etiqueta: 'Información' },
];
export const FILTROS_QUIEN = [
  { valor: 'todas', etiqueta: 'De todos' },
  { valor: 'mias', etiqueta: 'Me tocan a mí' },
  { valor: 'equipo', etiqueta: 'Del equipo técnico' },
];

/** Filtra alertas ya enriquecidas por gravedad (`clave`: roja·naranja·amarilla·info) y por a quién le toca. Filtros desconocidos = «todas». */
export function filtrarAlertas(filas, { gravedad = 'todas', quien = 'todas' } = {}) {
  return lista(filas).filter((a) => {
    if (!a) return false;
    if (gravedad === 'graves' && !(a.clave === 'roja' || a.clave === 'naranja')) return false;
    if ((gravedad === 'amarilla' || gravedad === 'info') && a.clave !== gravedad) return false;
    if (quien === 'mias' && a.responsable !== 'dueno') return false;
    if (quien === 'equipo' && !(a.responsable && a.responsable !== 'dueno')) return false;
    return true;
  });
}

/** Cuántas alertas habría con cada filtro de gravedad (para mostrar el número en el botón). */
export function contarPorGravedad(filas) {
  const l = lista(filas);
  return { todas: l.length, graves: l.filter((a) => a.clave === 'roja' || a.clave === 'naranja').length, amarilla: l.filter((a) => a.clave === 'amarilla').length, info: l.filter((a) => a.clave === 'info').length };
}

/** ¿Está guardado el archivo de alertas y al día? → { tono, texto, detalle }. El panel no lo escribe: lo escribe el productor con --escribir. */
export function estadoArchivoAlertas(archivo) {
  const a = archivo || {};
  if (a.ilegible) return { tono: 'error', texto: 'Ilegible', detalle: 'El archivo de alertas guardado no se pudo leer entero; abajo se ven las alertas calculadas en este momento.' };
  if (!a.existe) return { tono: 'aviso', texto: 'Sin guardar', detalle: 'Todavía nadie guardó el archivo de alertas, así que no hay nada que enviar al celular. Las de abajo se calculan en este momento.' };
  if (a.alDia) return { tono: 'ok', texto: 'Al día', detalle: 'El archivo guardado coincide con lo que se calcula ahora.' };
  return { tono: 'aviso', texto: 'Desactualizado', detalle: 'Cambió algo desde la última vez que se guardó el archivo de alertas. Las de abajo se calculan en este momento.' };
}

// ───────────────────────── informe de las 08:30 ─────────────────────────

const ESTADO_SECCION = {
  con_novedades: { tono: 'aviso', texto: 'Hay novedades', icono: 'alerta' },
  sin_novedades: { tono: 'ok', texto: 'Sin novedades', icono: 'ok' },
  sin_medir: { tono: 'neutro', texto: 'Todavía no se mide', icono: 'circulo-punteado' },
};
const ESTADO_CERO = {
  cumple: { tono: 'ok', texto: 'Cumple', icono: 'ok' },
  no_cumple: { tono: 'error', texto: 'No cumple', icono: 'octogono' },
  sin_medir: { tono: 'neutro', texto: 'Sin medir', icono: 'circulo-punteado' },
};

/**
 * El informe de las 08:30 listo para pintar, o null. Las dos versiones se muestran como texto plano (textContent): el correo con importes y el celular con
 * porcentajes. El panel NO lo envía; el envío es del equipo técnico (S-B) cuando el dueño elija el canal.
 */
export function modeloInforme(datos) {
  if (!esObjeto(datos) || datos.tipo !== 'informe_diario' || !esObjeto(datos.versiones)) return null;
  const v = datos.versiones;
  const correo = esObjeto(v.correo) ? { asunto: txt(v.correo.asunto, 200), texto: txt(v.correo.texto, 20000) } : null;
  const celular = esObjeto(v.celular) ? { texto: txt(v.celular.texto, 2000) } : null;
  if (!correo || !celular) return null;
  const sem = esObjeto(datos.semaforo) && NIVELES[datos.semaforo.nivel] ? { nivel: datos.semaforo.nivel, info: NIVELES[datos.semaforo.nivel], titulo: txt(datos.semaforo.titulo, 120) } : null;
  return {
    fecha: txt(datos.fecha, 10), diaMedido: txt(datos.dia_medido, 10), hora: txt(datos.hora_objetivo, 5), generadoEn: txt(datos.generado_en, 30) || null, semaforo: sem,
    versiones: { correo, celular },
    avisos: lista(datos.avisos).filter(esObjeto).slice(0, 8).map((a) => ({ id: txt(a.id, 30), titulo: txt(a.titulo, 80), estado: ESTADO_SECCION[a.estado] ? a.estado : 'sin_medir', info: ESTADO_SECCION[a.estado] || ESTADO_SECCION.sin_medir, lineas: lista(a.correo).filter((x) => typeof x === 'string').slice(0, 20).map((x) => x.slice(0, 400)) })),
    ceros: lista(datos.ceros).filter(esObjeto).slice(0, 10).map((c) => ({ id: txt(c.id, 30), texto: txt(c.texto, 120), estado: ESTADO_CERO[c.estado] ? c.estado : 'sin_medir', info: ESTADO_CERO[c.estado] || ESTADO_CERO.sin_medir, valor: entero(c.valor), detalle: txt(c.detalle, 300) })),
    teToca: lista(datos.te_toca).filter(esObjeto).slice(0, 30).map((t) => ({ tipo: ['semaforo', 'firma', 'pendiente'].includes(t.tipo) ? t.tipo : 'semaforo', id: txt(t.id, 20) || null, prioridad: txt(t.prioridad, 2) || null, titulo: txt(t.titulo, 140), queHacer: txt(t.que_hacer, 300), enlace: enlaceSeguro(t.enlace), enlaceTexto: txt(t.enlace_texto, 60) || 'Abrir', comando: comandoSeguro(t.comando) })),
    sinDatos: lista(datos.sin_datos).filter((x) => typeof x === 'string').slice(0, 20).map((x) => x.slice(0, 200)),
    ventasGasto: esObjeto(datos.ventas_gasto) ? { hayDatos: datos.ventas_gasto.hay_datos === true, lineas: lista(datos.ventas_gasto.correo).filter((x) => typeof x === 'string').slice(0, 6).map((x) => x.slice(0, 300)) } : null,
  };
}

export const COMANDO_INFORME = '.venv/bin/python -m scripts.informe.informe_diario';
export const COMANDO_ALERTAS = '.venv/bin/python -m scripts.alertas.producir --semaforo';
