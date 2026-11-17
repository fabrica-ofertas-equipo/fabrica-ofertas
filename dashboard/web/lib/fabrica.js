// lib/fabrica.js — lógica pura de #/fabrica («Fábrica de creativos: lo que se produce de noche»). Sin DOM, sin red; probada con node --test.
//
// Qué mezcla: (1) la GUÍA del método (turno de noche, formatos, anatomía del anuncio): texto estático, marcado como guía; (2) los DATOS reales que
// existan en ofertas/<id>/06-creativos/ (paquete.json) y en ofertas/<id>/qa/ (QA de D6 y dictamen de X1): piezas, su estado y el control de calidad.
// Nunca inventa una cifra: lo que falta sale como «sin resultado» con quién lo produce. Las cifras de retorno por formato del autor del método NO se
// usan (son declaradas, sin verificar y su base no está clara): la tabla queda «se medirá con nuestros datos».

import { esObj, lista, texto, entero, plano, etapaDe, ultimoQa, rutaQaSegura, mercadoDe } from './n2-comun.js';

// ───────────────────────── la guía: turno de noche ─────────────────────────

/** Estado de CADA paso en nuestra fábrica HOY (mapeo.md §1 y analisis/creativos-jurado.md §1.1, 2026-11-06; el panel no lo comprueba solo). */
export const ESTADO_PASO = Object.freeze({
  existe: { tono: 'ok', texto: 'Ya existe' },
  parcial: { tono: 'aviso', texto: 'Parcial' },
  falta: { tono: 'neutro', texto: 'Falta construir' },
});

export const TURNO_NOCHE = Object.freeze([
  { id: 'arranque', hora: '00:00', nombre: 'Arranca sola', icono: 'play',
    que: 'Cada idioma pide su encargo. Primero reemplaza los anuncios que se están cansando, después prueba enfoques nuevos y traduce los ganadores.',
    hoy: { estado: 'falta', texto: 'Hoy la etapa de creativos prepara los anuncios cuando se le pide, oferta por oferta; todavía no hay un encargo nocturno programado.' } },
  { id: 'guion', hora: '00 h', nombre: 'Guion', icono: 'lapiz',
    que: 'Una IA arma el guion a partir de lo que ya ganó: enfoque · gancho · promesa · prueba · cierre.',
    hoy: { estado: 'parcial', texto: 'La etapa de creativos ya escribe la tabla de enfoques y los guiones; todavía no existe el banco de ganchos que ganaron (para aprender de lo que se cobró).' } },
  { id: 'imagen', hora: '02 h', nombre: 'Imagen', icono: 'pantalla',
    que: 'Imágenes y video con IA, siempre con el producto real en pantalla.',
    hoy: { estado: 'parcial', texto: 'Los anuncios de imagen fija ya salen solos (sin gastar créditos); el video con IA solo se genera en una sesión tuya.' } },
  { id: 'voz', hora: '02 h', nombre: 'Voz', icono: 'megafono',
    que: 'Voces nativas de cada idioma, nunca traducidas a la fuerza.',
    hoy: { estado: 'parcial', texto: 'Hay voz nativa predefinida (nunca clonada), pero se genera en una sesión tuya, no de noche.' } },
  { id: 'montaje', hora: '', nombre: 'Montaje', icono: 'carpeta',
    que: 'Cortes, música y subtítulos quemados en el video.',
    hoy: { estado: 'falta', texto: 'No hay montaje automático de video todavía; la música solo entra con licencia registrada.' } },
  { id: 'control', hora: '06 h', nombre: 'Control', icono: 'escudo',
    que: 'Control de calidad automático pieza por pieza, con la lista de 6 puntos (más abajo).',
    hoy: { estado: 'parcial', texto: 'El revisor de creativos ya revisa los 6 puntos; todavía no se leen solos los textos dentro de las imágenes ni se revisa el video.' } },
  { id: 'lista', hora: '07:00', nombre: 'Por aprobar', icono: 'check',
    que: 'La tanda espera en la bandeja «por aprobar» hasta que la revises.',
    hoy: { estado: 'existe', texto: 'Esta pantalla muestra lo que haya producido; la aprobación es la firma de la etapa de creativos.' } },
]);

export const CARGA_TARDE = Object.freeze({
  hora: 'A la tarde', nombre: 'Carga a Meta, sin activar',
  que: 'Un conjunto de anuncios por pieza, cargado sin activar.',
  hoy: { estado: 'parcial', texto: 'La campaña se arma como borrador; para activarla hace falta el visto bueno de cumplimiento vigente, y se respetan los frenos de la empresa.' },
});

export const REGLA_HORARIO = 'De noche se produce y a la tarde se carga: hacer las dos cosas a la vez satura la conexión con Meta y frena a los robots.';

// ───────────────────────── la guía: qué creativos venden ─────────────────────────

/** Anatomía del anuncio ganador (método) con su traducción a nuestros nichos. */
export const ANATOMIA = Object.freeze([
  { n: 1, id: 'gancho', nombre: 'Gancho', donde: 'Al inicio', que: 'Algo raro o una pregunta que frena el dedo.', nuestro: 'La pregunta va sobre la tarea o el producto, nunca sobre la persona (nada de «¿por qué no te alcanza la plata?»).' },
  { n: 2, id: 'promesa', nombre: 'Promesa', donde: 'Después', que: 'Un beneficio claro, dicho en simple.', nuestro: 'Se promete lo que el producto contiene o permite hacer, nunca un resultado ni un plazo.' },
  { n: 3, id: 'prueba', nombre: 'Prueba', donde: 'En el medio', que: 'El producto real en pantalla, por dentro.', nuestro: 'Solo lo que el producto realmente entrega; nada de capturas de ingresos ni de reseñas inventadas.' },
  { n: 4, id: 'llamado', nombre: 'Llamado', donde: 'Al final', que: 'Qué hacer ahora, sin precio en el anuncio.', nuestro: 'Si el anuncio muestra un precio, debe coincidir con la página de venta; mostrarlo o no es una variable que se mide aparte.' },
]);

export const LEMA = 'Se copia lo que gana. Lo demás se apaga.';

export const ESTADO_FORMATO = Object.freeze({
  disponible: { tono: 'ok', texto: 'Disponible' },
  adaptado: { tono: 'info', texto: 'Adaptado a nuestras reglas' },
  por_construir: { tono: 'aviso', texto: 'Por construir' },
  diferido: { tono: 'neutro', texto: 'Para más adelante' },
});

export const FORMATOS = Object.freeze([
  { id: 'imagen_pregunta', nombre: 'Imagen con pregunta', rol: 'Según el método: el de mejor costo por venta.',
    nuestro: 'Se hace con la pregunta sobre la tarea («¿Cómo se calcula el precio mínimo de una vela?»). Parte de su efecto puede venir de la pregunta personal, que aquí no se usa: por eso se mide aparte.', estado: 'adaptado' },
  { id: 'ganador_traducido', nombre: 'Ganador traducido', rol: 'Según el método: reaprovechar lo que ya vendió en otros idiomas.',
    nuestro: 'Cada idioma es una oferta propia: el texto se reescribe y se revisa por mercado; una variante de traducción fiel puede probarse junto a la reescrita (aún sin decidir).', estado: 'adaptado' },
  { id: 'relevo', nombre: 'Relevo con otra apertura', rol: 'Según el método: el mismo anuncio con otro gancho, antes de que el ganador se canse.',
    nuestro: 'Ya existe como escalera de variación: se cambia una sola cosa por vez y el anuncio nuevo no hereda las cifras del anterior.', estado: 'disponible' },
  { id: 'reel_3', nombre: 'Reel de 3 experimentos', rol: 'Según el método: se viraliza en orgánico.',
    nuestro: 'Se probaría como video corto que prueba 3 formas de hacer una tarea con el producto real; falta el montaje de video.', estado: 'por_construir' },
  { id: 'cancion', nombre: 'Canción con IA', rol: 'Según el método: en prueba.',
    nuestro: 'Se deja para más adelante, hasta leer las condiciones de uso comercial del generador de música; la letra pasaría por el mismo control que un guion.', estado: 'diferido' },
  { id: 'review_app', nombre: 'Reseña de la app', rol: 'Según el método: prometedor.',
    nuestro: 'Se hace como recorrido del producto real (demostración en pantalla). Quedan fuera las reseñas de estrellas escritas a mano.', estado: 'disponible' },
]);

export const SE_MIDE = 'Se medirá con nuestros datos';
export const NOTA_RETORNO = 'No se muestran las cifras de retorno del autor del método: son declaradas, nadie las verificó y no dicen si hablan de ingresos o de ganancia. Cuando haya ventas, el cuadro de rendimiento por formato mostrará lo cobrado (menos reembolsos) por cada euro gastado, con su margen de error.';

export const NO_SE_PRODUCE = Object.freeze([
  { id: 'testimonios', titulo: 'Testimonios inventados con IA',
    texto: 'No se producen testimonios hechos con IA ni con nombres falsos presentados como clientes reales: engañan a quien compra y pueden costar la cuenta de anuncios o de cobro. En su lugar: demostraciones del producto real, la garantía y, cuando haya ventas, testimonios reales con permiso.' },
  { id: 'esquivar', titulo: 'Cambiar de IA para esquivar una negativa',
    texto: 'Si un modelo se niega a escribir algo, se corrige lo que se prometía; no se busca otra herramienta que lo haga.' },
]);

// ───────────────────────── los 6 puntos del control de calidad ─────────────────────────

export const ESTADO_CONTROL = Object.freeze({
  pasa: { tono: 'ok', icono: 'ok', texto: 'Pasa' },
  falla: { tono: 'error', icono: 'x-circulo', texto: 'No pasa' },
  parcial: { tono: 'aviso', icono: 'alerta', texto: 'A medias' },
  no_aplica: { tono: 'neutro', icono: 'menos', texto: 'No aplica' },
  sin_resultado: { tono: 'neutro', icono: 'circulo-punteado', texto: 'Sin resultado' },
});

/** `checks`: ids de comprobación del revisor de D6 (rúbrica d6-creativos) que alimentan cada punto. */
export const PUNTOS_CONTROL = Object.freeze([
  { id: 'audio', n: 1, titulo: 'Audio sin cortes ni desfases', explica: 'La voz suena entera, dice lo mismo que el guion aprobado y los subtítulos van al ritmo.', checks: ['D6-L1-07'] },
  { id: 'idioma', n: 2, titulo: 'Un solo idioma de punta a punta', explica: 'Voz, texto en pantalla y copy están en el idioma del mercado, sin mezclas ni letras rotas (ñ, ł, ß…).', checks: ['D6-L1-06'] },
  { id: 'texto', n: 3, titulo: 'Texto sin errores', explica: 'Lo que se lee en la pieza es exactamente el texto aprobado: sin faltas ni palabras cortadas.', checks: ['D6-L1-06', 'D6-L1-01'] },
  { id: 'caras', n: 4, titulo: 'Caras y manos bien hechas', explica: 'Sin rostros ni manos deformes; si hay una persona generada con IA, va rotulada.', checks: ['D6-L1-07', 'D6-L1-09'] },
  { id: 'ajeno', n: 5, titulo: 'Nada de material ajeno', explica: 'Ni caras, ni imágenes, ni música, ni frases de otros: todo con licencia propia y sin copiar.', checks: ['D6-L1-08', 'D6-L1-09'] },
  { id: 'promesas', n: 6, titulo: 'Sin precios ni promesas prohibidas', explica: 'Ninguna promesa de resultado, plazo o ingreso; el precio, si aparece, coincide con la página de venta.', checks: ['D6-L1-02', 'D6-L1-03', 'D6-L1-05'] },
]);

const OK_QA = new Set(['PASS', 'PASS_CON_NOTAS']);

/** {tono, texto} del veredicto de una revisión (de calidad o de cumplimiento): «Aprobado», «Aprobado con notas», «No aprobado» o «Pasa a tu decisión». */
export function infoVeredicto(v) {
  switch (String(v || '').toUpperCase()) {
    case 'PASS': return { tono: 'ok', texto: 'Aprobado' };
    case 'PASS_CON_NOTAS': return { tono: 'aviso', texto: 'Aprobado con notas' };
    case 'FAIL': return { tono: 'error', texto: 'No aprobado' };
    case 'ESCALAR': return { tono: 'grave', texto: 'Pasa a tu decisión' };
    default: return { tono: 'neutro', texto: v ? String(v) : 'sin veredicto' };
  }
}

/** Documento de QA (qa/d6-vN.json o qa/x1-d6-vN.json) → {archivo, veredicto, puntaje, umbral, ronda, creadoEn, hallazgos, abiertos, checks}. */
export function modeloQa(doc, archivo = null) {
  if (!esObj(doc)) return null;
  const hallazgos = lista(doc.hallazgos).filter(esObj);
  const cerrados = new Set(['corregido_por_qa', 'aceptado_con_nota', 'corregido', 'descartado']);
  return {
    archivo,
    veredicto: texto(doc.veredicto, 20),
    puntaje: texto(doc.puntaje_global, 12),
    umbral: texto(doc.umbral, 12),
    ronda: entero(doc.ronda),
    creadoEn: texto(doc.creado_en, 30),
    hallazgos: hallazgos.length,
    abiertos: hallazgos.filter((h) => !cerrados.has(String(h.estado || ''))).length,
    checks: lista(doc.checks_l1).filter(esObj).map((c) => ({ id: texto(c.check_id, 60), resultado: plano(c.resultado), detalle: texto(c.detalle, 300) })).filter((c) => c.id),
  };
}

/** Lo que se muestra de una comprobación del revisor: su detalle en palabras (el identificador técnico queda para el «Detalle técnico»). */
const RESULTADO_PALABRAS = { pass: 'pasó', fail: 'no pasó', no_aplica: 'no aplica' };
const fraseCheck = (c, porDefecto) => c.detalle || RESULTADO_PALABRAS[c.resultado] || porDefecto;
const frasesUnicas = (lista, porDefecto) => [...new Set(lista.map((c) => fraseCheck(c, porDefecto)))].join(' · ');

const coincideCheck = (idCheck, buscado) => {
  const a = String(idCheck || '').toUpperCase();
  return a === buscado || a.startsWith(`${buscado}-`) || a.startsWith(`${buscado}_`);
};

/**
 * Evalúa los 6 puntos con lo que HAY: primero el resultado de las comprobaciones del revisor (D6-L1-0x); si no está, lo que se deduce del propio paquete
 * (idioma del texto, lint de X1, si hay video o imágenes con IA); si tampoco, «sin resultado». Cada punto dice de dónde sale.
 * @param {object|null} m modelo de la oferta (modeloCreativos) @param {object|null} qa modeloQa del revisor de D6
 */
export function evaluarControl(m, qa) {
  const piezas = m ? m.piezas : [];
  const checks = qa ? qa.checks : [];
  const hayPiezas = piezas.length > 0;
  const salida = PUNTOS_CONTROL.map((p) => {
    const dados = checks.filter((c) => p.checks.some((b) => coincideCheck(c.id, b)));
    const falla = dados.filter((c) => c.resultado === 'fail');
    if (falla.length) return { ...p, estado: 'falla', evidencia: frasesUnicas(falla, 'no pasó'), origen: 'Revisor de creativos' };
    const pasa = dados.filter((c) => c.resultado === 'pass');
    if (dados.length && pasa.length === dados.length) return { ...p, estado: 'pasa', evidencia: frasesUnicas(pasa, 'pasó'), origen: 'Revisor de creativos' };
    if (dados.length && dados.every((c) => c.resultado === 'no_aplica')) return { ...p, estado: 'no_aplica', evidencia: frasesUnicas(dados, 'no aplica'), origen: 'Revisor de creativos' };
    if (dados.length && pasa.length) return { ...p, estado: 'parcial', evidencia: frasesUnicas(dados.map((c) => ({ resultado: c.resultado })), 'sin resultado'), origen: 'Revisor de creativos' };

    // sin resultado del revisor: lo que se deduce del paquete
    if (!hayPiezas) return { ...p, estado: 'sin_resultado', evidencia: 'Todavía no hay piezas que revisar.', origen: null };
    if (p.id === 'audio') {
      const videos = piezas.filter((x) => x.formato === 'video').length;
      if (!videos) return { ...p, estado: 'no_aplica', evidencia: 'Ninguna pieza lleva audio: todas son imágenes.', origen: 'Paquete de creativos' };
    }
    if (p.id === 'caras') {
      const ia = piezas.filter((x) => x.iaGenerado).length;
      if (!ia) return { ...p, estado: 'no_aplica', evidencia: 'Ninguna pieza usa imágenes generadas con IA.', origen: 'Paquete de creativos' };
      return { ...p, estado: 'sin_resultado', evidencia: `${ia} ${ia === 1 ? 'pieza usa' : 'piezas usan'} imágenes hechas con IA: falta que el revisor las mire.`, origen: null };
    }
    if (p.id === 'idioma') {
      const esperado = m.locale;
      const idiomas = piezas.map((x) => x.idioma);
      const sinDato = idiomas.filter((i) => !i).length;
      if (esperado && idiomas.some((i) => i && i !== esperado)) {
        const otros = [...new Set(idiomas.filter((i) => i && i !== esperado))].join(', ');
        return { ...p, estado: 'falla', evidencia: `Hay texto en ${otros} y el mercado es ${esperado}.`, origen: 'Paquete de creativos' };
      }
      if (esperado && !sinDato) return { ...p, estado: 'parcial', evidencia: `El texto de las ${piezas.length} piezas está marcado como ${esperado}; falta comprobar la imagen y la voz.`, origen: 'Paquete de creativos' };
      return { ...p, estado: 'sin_resultado', evidencia: 'El paquete de anuncios no indica el idioma de todas las piezas.', origen: null };
    }
    if (p.id === 'promesas') {
      const fallan = piezas.filter((x) => x.lint === 'FAIL').length;
      const notas = piezas.filter((x) => x.lint === 'PASS_CON_NOTAS').length;
      const pasan = piezas.filter((x) => x.lint === 'PASS').length;
      const x1 = m.x1 && m.x1.veredicto ? String(m.x1.veredicto).toUpperCase() : null;
      const x1Texto = x1 ? infoVeredicto(x1).texto.toLowerCase() : null;
      if (fallan || x1 === 'FAIL') return { ...p, estado: 'falla', evidencia: fallan ? `${fallan} ${fallan === 1 ? 'pieza no pasa' : 'piezas no pasan'} la revisión de promesas.` : 'El informe de cumplimiento no pasa.', origen: 'Paquete de creativos' };
      if (pasan === piezas.length && (x1 === null || OK_QA.has(x1))) return { ...p, estado: 'pasa', evidencia: `Las ${piezas.length} piezas pasan la revisión de promesas${x1 ? ` y el dictamen de cumplimiento está «${x1Texto}»` : ''}.`, origen: 'Paquete de creativos' };
      if (pasan + notas === piezas.length) return { ...p, estado: 'parcial', evidencia: `${notas} ${notas === 1 ? 'pieza pasa' : 'piezas pasan'} con notas.`, origen: 'Paquete de creativos' };
      return { ...p, estado: 'sin_resultado', evidencia: 'El paquete de anuncios no trae el resultado de la revisión de promesas de todas las piezas.', origen: null };
    }
    return { ...p, estado: 'sin_resultado', evidencia: 'El revisor de creativos aún no dejó el resultado de este punto.', origen: null };
  });
  return salida;
}

/** Cuenta los puntos por estado. */
export function resumenControl(puntos) {
  const c = { pasa: 0, falla: 0, parcial: 0, no_aplica: 0, sin_resultado: 0 };
  for (const p of lista(puntos)) if (p && c[p.estado] !== undefined) c[p.estado] += 1;
  return { ...c, total: lista(puntos).length };
}

// ───────────────────────── piezas por aprobar ─────────────────────────

export const ESTADO_PIEZA = Object.freeze({
  espera_firma: { tono: 'acento', icono: 'usuario', texto: 'Espera tu aprobación' },
  lista: { tono: 'ok', icono: 'ok', texto: 'Lista para la campaña' },
  borrador: { tono: 'neutro', icono: 'lapiz', texto: 'Borrador' },
  en_revision: { tono: 'info', icono: 'ojo', texto: 'En revisión' },
  rechazada: { tono: 'error', icono: 'x-circulo', texto: 'No pasa el control' },
});

/** «promesa-de-claridad» → «promesa de claridad». */
export const humanizar = (s) => { const t = texto(s, 80); return t ? t.replace(/[_-]+/g, ' ') : null; };
/** «c01-hueco» → «hueco». */
export const nombreConcepto = (id) => { const t = texto(id, 80); return t ? t.replace(/^c\d+[-_]/i, '').replace(/[_-]+/g, ' ') : null; };

function modeloPieza(a) {
  const copy = esObj(a.copy) ? a.copy : {};
  const assets = lista(a.assets).filter(esObj);
  const a0 = assets[0] || {};
  return {
    adName: texto(a.ad_name, 120),
    conceptoId: texto(a.concepto_id, 80),
    concepto: nombreConcepto(a.concepto_id),
    formato: plano(a.formato) || null,
    hookTipo: humanizar(a.hook_tipo),
    hookId: texto(a.hook_id, 20),
    titular: texto(copy.titular, 120),
    texto: texto(copy.texto_principal, 360),
    descripcion: texto(copy.descripcion, 120),
    cta: texto(copy.cta, 30),
    idioma: texto(copy.idioma, 16),
    ratio: texto(a0.ratio, 8),
    archivo: texto(a0.archivo, 200),
    iaGenerado: assets.some((x) => x.ia_generado === true),
    herramienta: texto(a0.herramienta, 60),
    costoCreditos: entero(a.costo_creditos),
    lint: texto(a.lint_x1, 20) ? String(a.lint_x1).toUpperCase() : null,
    claims: lista(a.claim_ids).length,
    estado: 'en_revision',
  };
}

/** Estado de una pieza según la etapa D6, el paquete y los veredictos. */
export function estadoDePieza(pieza, m) {
  if (pieza.lint === 'FAIL') return 'rechazada';
  if (m.etapa && m.etapa.gatePendiente) return 'espera_firma';
  const qaOk = m.qa && OK_QA.has(String(m.qa.veredicto || '').toUpperCase());
  const x1Ok = m.x1 && OK_QA.has(String(m.x1.veredicto || '').toUpperCase());
  if (m.estadoPaquete === 'listo_para_d7' && qaOk && x1Ok) return 'lista';
  if (m.estadoPaquete === 'borrador') return 'borrador';
  return 'en_revision';
}

/**
 * Modelo de los creativos de UNA oferta.
 * @param {{id:string, demo?:boolean, interno?:string|null}} oferta fila de /ofertas
 * @param {{detalle?:object|null, paquete?:object|null, qaDoc?:object|null, x1Doc?:object|null}} datos
 */
export function modeloCreativos(oferta, { detalle = null, paquete = null, qaDoc = null, x1Doc = null } = {}) {
  const etapa = etapaDe(detalle, 'D6');
  const mercado = mercadoDe(detalle);
  const p = esObj(paquete) ? paquete : null;
  const qaArchivo = (p && rutaQaSegura(p.qa_ref)) || (etapa ? ultimoQa(etapa.qa, 'd6-') : null);
  const x1Archivo = (p && rutaQaSegura(p.x1_ref)) || (etapa ? ultimoQa(etapa.qa, 'x1-d6-') : null);
  const m = {
    id: oferta.id, interno: oferta.interno || null, demo: Boolean(oferta.demo),
    tienePaquete: Boolean(p),
    etapa,
    locale: mercado && mercado.locale ? mercado.locale : (p && p.anuncios && esObj(p.anuncios[0]) && esObj(p.anuncios[0].copy) ? texto(p.anuncios[0].copy.idioma, 16) : null),
    estadoPaquete: p ? texto(p.estado, 30) : null,
    version: p ? texto(p.version, 12) : null,
    qa: modeloQa(qaDoc, qaArchivo) || (qaArchivo ? { archivo: qaArchivo, veredicto: null, checks: [], hallazgos: 0, abiertos: 0 } : null),
    x1: modeloQa(x1Doc, x1Archivo) || (x1Archivo ? { archivo: x1Archivo, veredicto: null, checks: [], hallazgos: 0, abiertos: 0 } : null),
    piezas: [],
    reserva: p ? lista(p.reserva).length : 0,
    creditos: p ? entero(p.costo_total_creditos) : null,
    divulgacionIa: p && esObj(p.politicas) ? texto(p.politicas.divulgacion_ia, 40) : null,
    conceptos: p ? lista(p.conceptos).length : 0,
    ultimaProduccion: null,
    totalAnuncios: p ? lista(p.anuncios).length : 0,
  };
  // el veredicto de la etapa lo trae también la lista de QA de la API cuando el documento no se pudo leer
  if (etapa) {
    const aqui = etapa.qa.find((q) => q.archivo === qaArchivo);
    if (aqui && m.qa && !m.qa.veredicto) m.qa.veredicto = texto(aqui.veredicto, 20);
    const ax = etapa.qa.find((q) => q.archivo === x1Archivo);
    if (ax && m.x1 && !m.x1.veredicto) m.x1.veredicto = texto(ax.veredicto, 20);
    const arts = etapa.artefactos;
    const pq = arts.find((a) => /(^|\/)paquete\.json$/.test(a.ruta));
    const mt = (pq || arts.slice().sort((a, b) => String(b.mtime || '').localeCompare(String(a.mtime || '')))[0] || {}).mtime;
    m.ultimaProduccion = texto(mt, 30);
  }
  m.piezas = p ? lista(p.anuncios).filter(esObj).slice(0, 60).map(modeloPieza) : [];
  m.piezas.forEach((z) => { z.estado = estadoDePieza(z, m); });
  m.control = evaluarControl(m, m.qa);
  return m;
}

/** Totales para las métricas de la pantalla. */
export function resumenFabrica(modelos) {
  const ms = lista(modelos);
  const piezas = ms.flatMap((m) => m.piezas);
  const conteo = (e) => piezas.filter((p) => p.estado === e).length;
  const fechas = ms.map((m) => m.ultimaProduccion).filter(Boolean).sort();
  return {
    ofertas: ms.length,
    ofertasConPaquete: ms.filter((m) => m.tienePaquete).length,
    piezas: piezas.length,
    esperanFirma: conteo('espera_firma'),
    listas: conteo('lista'),
    rechazadas: conteo('rechazada'),
    enRevision: conteo('en_revision') + conteo('borrador'),
    ultimaProduccion: fechas.length ? fechas[fechas.length - 1] : null,
    soloDemo: ms.length > 0 && ms.every((m) => m.demo),
  };
}

/** Avisos para «Requiere tu atención»: firmas pendientes, piezas que no pasan y revisiones no aprobadas. */
export function avisosFabrica(modelos) {
  const items = [];
  for (const m of lista(modelos)) {
    const quien = `${m.id}${m.demo ? ' (demo)' : ''}`;
    if (m.etapa && m.etapa.gatePendiente) {
      items.push({ tono: 'aviso', titulo: `Los creativos de ${quien} esperan tu aprobación`, detalle: `${m.piezas.length} ${m.piezas.length === 1 ? 'pieza' : 'piezas'} en la bandeja «por aprobar».`, accion: { texto: 'Ver la oferta', ruta: `/oferta/${m.id}` } });
    }
    const rech = m.piezas.filter((p) => p.estado === 'rechazada').length;
    if (rech) items.push({ tono: 'grave', titulo: `${rech} ${rech === 1 ? 'pieza no pasa' : 'piezas no pasan'} el control en ${quien}`, detalle: 'La revisión de promesas las marcó como no válidas: no pueden pasar a campaña.', accion: { texto: 'Ver la oferta', ruta: `/oferta/${m.id}` } });
    const fallos = m.control.filter((c) => c.estado === 'falla');
    if (fallos.length) items.push({ tono: 'grave', titulo: `El control de calidad de ${quien} tiene ${fallos.length} ${fallos.length === 1 ? 'punto que falla' : 'puntos que fallan'}`, detalle: fallos.map((f) => f.titulo).join(' · '), accion: { texto: 'Ver la oferta', ruta: `/oferta/${m.id}` } });
    const v = m.qa && m.qa.veredicto ? String(m.qa.veredicto).toUpperCase() : null;
    if (v === 'FAIL' || v === 'ESCALAR') items.push({ tono: 'grave', titulo: `La revisión de creativos de ${quien} terminó como «${infoVeredicto(v).texto}»`, detalle: 'Se le devuelve a quien lo prepara o lo decide una persona.', accion: { texto: 'Ver la oferta', ruta: `/oferta/${m.id}` } });
  }
  return items;
}

/** Rutas y comandos para el bloque «Detalle técnico» (el panel solo los muestra). */
export function detalleTecnicoFabrica(m) {
  const base = m ? `ofertas/${m.id}` : 'ofertas/<id>';
  return {
    archivos: [`${base}/06-creativos/paquete.json`, `${base}/06-creativos/assets/`, `${base}/qa/d6-v<n>.json`, `${base}/qa/x1-d6-v<n>.json`],
    comandos: [
      { titulo: 'Ver en qué etapa está la oferta', comando: `python -m engine.orq estado --oferta ${m && m.interno ? m.interno : 'OF-AAAAMM-NN'}` },
      { titulo: 'Validar la oferta (incluido el paquete de anuncios) contra el formato esperado', comando: `python -m scripts.validar_esquemas oferta ${base}` },
    ],
  };
}
