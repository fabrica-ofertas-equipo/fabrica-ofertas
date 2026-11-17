// lib/paises.js — lógica pura de #/paises («Países: del idioma base a todos los idiomas»). Sin DOM, sin red; probada con node --test.
//
// Tres cosas: (1) el mercado e idioma de cada oferta (ofertas/<id>/mercado.json); (2) el TABLERO DE LANZAMIENTO DE IDIOMA (en pantalla: «lista de control»): 6 columnas y 25 tarjetas cuya
// lista sale tal cual de analisis/paises-mercados-tiendas.md §2.3 (PLANTILLA estática: dice qué hay que verificar y quién lo hace). El ESTADO de cada
// tarjeta solo sale de ofertas/<id>/lanzamiento_idioma.json, que lo escribe el código (scripts.lanzamiento_idioma, aún no existe): sin ese archivo
// todas son «sin evidencia todavía». El panel NUNCA marca una tarjeta; (3) las obligaciones por país que el método de Mentor no trae.

import { esObj, lista, texto, plano, mercadoDe, esMadreValidada } from './n2-comun.js';

export const COLUMNAS = Object.freeze([
  { id: 'TIENDA', nombre: 'Tienda', icono: 'pantalla', que: 'La tienda del idioma: textos, correos y páginas legales traducidos, producto propio y poscompra.' },
  { id: 'DOMINIO', nombre: 'Dominio', icono: 'globo', que: 'Una dirección web propia del idioma, verificada en Meta y sin problemas de seguridad.' },
  { id: 'META', nombre: 'Meta', icono: 'megafono', que: 'Página, cuenta de anuncios, medidor de Meta y filtro de idioma en cada conjunto.' },
  { id: 'COBRO', nombre: 'Cobro', icono: 'dinero', que: 'Precio por país, medios de pago, pantalla de pago traducida, impuestos y desistimiento.' },
  { id: 'CREATIVOS', nombre: 'Anuncios', icono: 'caja', que: 'Los anuncios ganadores traducidos con voz nativa, prueba real y calidad de idioma auditada.' },
  { id: 'LISTO', nombre: 'Listo para lanzar', icono: 'check', que: 'Auditoría completa, apertura del idioma firmada por ti y testeo prendido.' },
]);

export const DUENIOS = Object.freeze({
  codigo: { texto: 'Programa', ayuda: 'Lo comprueba un programa que siempre da el mismo resultado' },
  ia: { texto: 'IA', ayuda: 'Lo redacta o propone una IA y un programa lo comprueba' },
  humano: { texto: 'Tú', ayuda: 'Lo haces o lo firmas tú' },
});

/**
 * origen: 'suya' = tarjeta literal del tablero de Mentor · 'nueva' = la añadimos por una obligación que su método no trae.
 * `evidencia` = qué se comprueba, en palabras de todos los días (es lo que lee el dueño); `tecnica` = lo mismo con los nombres de archivos, comandos y
 * chequeos tal cual (va en «Detalle técnico»). `gate` = quién interviene.
 */
export const TARJETAS = Object.freeze([
  { id: 'T1', col: 'TIENDA', titulo: 'Tienda del idioma creada desde la plantilla', origen: 'suya', duenio: ['codigo', 'ia'], gate: 'Tú abres el idioma y tú publicas la página de venta.',
    evidencia: 'Existe la versión de la oferta en este idioma, enlazada con la oferta original. El idioma está permitido, la página de venta no tiene errores y tiene su propia dirección web y su propio medidor de Meta, distintos de los de la original.',
    tecnica: 'La oferta hija existe (familia_id y variante_de apuntan a la madre), su idioma está en locales_permitidos, landing.validar no da hallazgos y su dominio y dataset son distintos de los de la madre.' },
  { id: 'T2', col: 'TIENDA', titulo: 'Textos, correos y legales en el idioma', origen: 'suya', duenio: ['ia', 'codigo'], gate: 'Revisión de la página de venta y visto bueno de cumplimiento; sin revisor nativo no se aprueba en polaco ni en francés.',
    evidencia: 'El idioma está dado de alta en los textos de la página y el texto de venta no tiene alertas graves. Las 7 páginas legales y la de desistimiento existen en una variante por país, las reglas del idioma están cargadas y, si la ley exige el idioma local, hay un revisor nativo.',
    tecnica: 'El idioma está en landing.textos.IDIOMAS; lint de copy sin rojos; 7 páginas legales y /desistimiento con variante por cada país; reglas del idioma en compliance/reglas_sensibles.yaml; revisor_nativo = true si hay obligación legal de idioma.' },
  { id: 'T3', col: 'TIENDA', titulo: 'Después de la venta en el idioma: entrega, soporte y reembolso', origen: 'suya', duenio: ['ia', 'codigo'], gate: 'La entrega es automática; tú autorizas la compra real mínima.',
    evidencia: 'Una prueba de punta a punta en modo de prueba salió bien: aviso firmado de la compra, correo, descarga, reembolso simulado, desistimiento y borrado de datos. Hay una política por jurisdicción y el correo de envío está bien configurado para no caer en spam. En la primera versión no hay oferta extra después del pago.',
    tecnica: '10-postcompra/preflight.json en VERDE (prueba de punta a punta en modo test: evento firmado, correo, descarga, reembolso simulado, desistimiento, supresión); política por jurisdicción; SPF, DKIM y DMARC del dominio de envío. Sin oferta tras el pago en v1.' },
  { id: 'T4', col: 'TIENDA', titulo: 'Producto del idioma producido y verificado', origen: 'nueva', duenio: ['ia', 'codigo'], gate: 'Revisión de la etapa de producto.',
    evidencia: 'El producto del idioma está aprobado, con su traducción adaptada. Una prueba de lectura en frío entra en el tiempo prometido, el texto no copia a otros y hay al menos 3 fuentes de primer nivel del país.',
    tecnica: '04-producto/producto.json aprobado con su localización; prueba de lectura en frío dentro del tiempo prometido; similitud de texto OK; al menos 3 fuentes de primer nivel del país.' },
  { id: 'D1', col: 'DOMINIO', titulo: 'Dominio propio comprado y activo', origen: 'suya', duenio: ['humano', 'codigo'], gate: 'La compra del dominio la autorizas tú (es un gasto).',
    evidencia: 'El dominio está dado de alta y responde en internet, y las cuentas de la oferta salen factibles o ajustadas.',
    tecnica: 'infra/alta.json.dominio; infra.dominio verificar (el DNS resuelve); la economía de la oferta es FACTIBLE o AJUSTADA.' },
  { id: 'D2', col: 'DOMINIO', titulo: 'Dominio verificado en Meta', origen: 'suya', duenio: ['humano', 'codigo'], gate: 'La página de venta no se cierra sin esta verificación.',
    evidencia: 'El chequeo antes de lanzar del dominio salió en verde, la medición lo marca como verificado y Meta lo muestra como verificado en la cuenta de la empresa.',
    tecnica: 'Preflight M-06 en VERDE; tracking.json.dominio_verificado = true; el dominio figura como verificado en el portfolio de Meta.' },
  { id: 'D3', col: 'DOMINIO', titulo: 'Sitio sin hallazgos de seguridad', origen: 'suya', duenio: ['codigo'], gate: 'Revisión de la página de venta. Definición provisional: el método no detalla esta tarjeta.',
    evidencia: 'La revisión de la página no encuentra problemas de seguridad ni de formularios, las reglas de seguridad del sitio son las estándar, no hay palabras sensibles en los enlaces y no quedaron claves o secretos olvidados en el código.',
    tecnica: 'landing.validar sin hallazgos de CSP ni de formulario; _headers igual al canónico; sin términos sensibles en URL ni UTM; escaneo de secretos en 0.' },
  { id: 'M1', col: 'META', titulo: 'Página de Facebook publicada (Instagram: no aplica)', origen: 'suya', duenio: ['humano', 'codigo'], gate: 'La decisión sobre la página es tuya.',
    evidencia: 'La página está registrada en el alta de la infraestructura, su chequeo salió en verde y tu decisión de no usar Instagram está anotada.',
    tecnica: 'infra/alta.json.page_id; preflight M-04 en VERDE; la decisión «sin Instagram» figura en decisiones_dueno.jsonl.' },
  { id: 'M2', col: 'META', titulo: 'Reloj del mercado definido (una sola cuenta de anuncios)', origen: 'suya', duenio: ['codigo', 'ia'], gate: 'Sin punto de control propio.',
    evidencia: 'La ficha del país trae una zona horaria válida, hay una única cuenta de anuncios permitida y las tareas diarias usan la hora del mercado. No hay una cuenta por huso horario.',
    tecnica: 'Zona horaria válida en la ficha del país; ad_account_id único y permitido (preflight M-02); los cron de D8 y D9 usan la zona del mercado. No hay una cuenta por huso.' },
  { id: 'M3', col: 'META', titulo: 'Medidor de Meta y conversiones por servidor, con permiso del visitante', origen: 'suya', duenio: ['humano', 'codigo'], gate: 'Crear el medidor no se puede deshacer: pasa por una revisión previa.',
    evidencia: 'El chequeo del medidor salió en verde (con un evento de menos de 24 h). La prueba de eventos muestra el mismo evento en el navegador y en el servidor, sin datos personales, y en la UE y el Reino Unido no se llama a Meta antes del permiso del visitante.',
    tecnica: 'Preflight M-05 en VERDE (evento de menos de 24 h); Test Events con event_id idéntico en navegador y servidor, sin datos personales; en UE/UK, ninguna llamada a Meta antes del consentimiento.' },
  { id: 'M4', col: 'META', titulo: 'Filtro de idioma en cada conjunto de anuncios', origen: 'suya', duenio: ['codigo', 'ia'], gate: 'Tú activas la campaña.',
    evidencia: 'La campaña trae la lista de idiomas de Meta, no vacía. Al volver a leer Meta se confirma que los países y el idioma de cada conjunto son los esperados (la huella de la configuración coincide).',
    tecnica: 'campana.json.locales_meta[] no vacío; la lectura de Meta confirma que los países y el idioma de cada conjunto son los esperados (hash_config).' },
  { id: 'M5', col: 'META', titulo: 'Anunciante declarado (ley europea) y salud de la cuenta', origen: 'nueva', duenio: ['codigo'], gate: 'El chequeo de la campaña, en verde y con menos de 6 horas.',
    evidencia: 'Están declarados el beneficiario y el pagador (UE), los chequeos de la cuenta salen en verde, no hubo anuncios rechazados en los últimos 7 días y el límite de gasto de la cuenta está recalculado.',
    tecnica: 'Preflight M-07 (beneficiario y pagador, UE); M-02 y M-03 en VERDE; rechazos de los últimos 7 días = 0; límite de gasto de la cuenta recalculado.' },
  { id: 'M6', col: 'META', titulo: 'Enlaces de anuncio con etiqueta propia', origen: 'suya', duenio: ['codigo'], gate: 'Revisión de la página de venta.',
    evidencia: 'Un enlace de prueba muestra que se guardan las cookies y que la etiqueta trae todos sus datos (campaña, anuncio y oferta).',
    tecnica: 'C06: enlace simulado, cookies y metadata completa (utm_*, cid, asid, adid, oferta_id).' },
  { id: 'C1', col: 'COBRO', titulo: 'Precio local con IVA y cuentas que cierran', origen: 'suya', duenio: ['codigo', 'ia', 'humano'], gate: 'Tú apruebas la oferta.',
    evidencia: 'Las cuentas de la oferta salen factibles o ajustadas, con tarifas de menos de 30 días. El precio de prueba coincide con el de la pantalla de pago y la ganancia neta cumple el mínimo del límite de precio.',
    tecnica: 'economia.json.veredicto es FACTIBLE o AJUSTADA con tarifas de menos de 30 días; el precio de prueba coincide con checkout.json; el neto cumple el mínimo del límite de precio.' },
  { id: 'C2', col: 'COBRO', titulo: 'Medios de pago coherentes con la moneda', origen: 'suya', duenio: ['codigo'], gate: 'Si la cobertura es media, la decides tú.',
    evidencia: 'Solo hay medios de pago aceptados (tarjeta, Apple Pay, Google Pay o Link), la cobertura de pago llega al menos al 40 % y los medios de pago locales quedan para más adelante.',
    tecnica: 'Métodos activos dentro de {tarjeta, Apple Pay, Google Pay, Link}; cobertura de pago ≥ 40 %; los medios locales quedan diferidos.' },
  { id: 'C3', col: 'COBRO', titulo: 'Pantalla de pago y página de compra en el idioma y la moneda', origen: 'suya', duenio: ['ia', 'codigo'], gate: 'Una compra de prueba manual, hecha por ti.',
    evidencia: 'La pantalla de pago tiene el idioma y los precios por moneda, y una compra de prueba en modo de prueba terminó con correo y descarga.',
    tecnica: 'checkout.json.locale y precios por moneda; compra de prueba en modo test con correo y descarga.' },
  { id: 'C4', col: 'COBRO', titulo: 'Régimen fiscal del grupo de países cubierto', origen: 'nueva', duenio: ['humano', 'codigo'], gate: 'Firmas tú, país por país.',
    evidencia: 'Todos los países del idioma figuran con tu firma (si el régimen es diferido), o el impuesto lo resuelve Stripe Tax o un agente de ventas con registro confirmado del IVA en la UE (OSS) o en el Reino Unido. No se dice «IVA incluido» si el régimen es diferido.',
    tecnica: 'mercado.fiscal.exposicion_aceptada.paises incluye todos los países del idioma, con tu firma (si el régimen es diferido), o régimen Stripe Tax / agente de ventas con registro OSS o HMRC confirmado; sin «IVA incluido» si es diferido.' },
  { id: 'C5', col: 'COBRO', titulo: 'Desistimiento (UE/Reino Unido) y garantía comercial separados', origen: 'nueva', duenio: ['codigo'], gate: 'Visto bueno de cumplimiento.',
    evidencia: 'La función de desistimiento funciona en 2 pasos, la casilla de renuncia es obligatoria y viene sin tildar, y el correo de confirmación queda guardado de forma duradera.',
    tecnica: '/desistimiento en 2 pasos; casilla de renuncia obligatoria y sin premarcar; correo de confirmación en soporte duradero.' },
  { id: 'K1', col: 'CREATIVOS', titulo: 'Ganadores de la oferta original traducidos, con voz nativa y subtítulos', origen: 'suya', duenio: ['ia', 'codigo'], gate: 'Aprobación de la etapa de creativos y veto de cumplimiento.',
    evidencia: 'Existe el paquete de anuncios y los pedidos de escala apuntan a los ganadores de la oferta original. La revisión de promesas no marca nada en rojo, el texto que se lee en pantalla coincide con el guion y los créditos están dentro del tope.',
    tecnica: '06-creativos/paquete.json; pedidos de escala con ad_origen entre los ganadores de la madre; lint de X1 sin rojos; el texto leído en pantalla coincide con el guion; créditos dentro del tope.' },
  { id: 'K2', col: 'CREATIVOS', titulo: 'Prueba social real o ninguna', origen: 'suya', duenio: ['codigo', 'humano'], gate: 'Tu firma de la prueba social y veto de cumplimiento.',
    evidencia: 'Cada testimonio está vinculado a una compra real y al permiso del comprador, o la sección se omite, y hay 0 testimonios simulados. No se inventan testimonios con nombres del idioma.',
    tecnica: 'pruebas_sociales.json con compra_id y permiso del comprador, o la sección omitida; 0 testimonios sintéticos. No se inventan testimonios con nombres del idioma.' },
  { id: 'K3', col: 'CREATIVOS', titulo: 'Incluye el ganador del momento de la oferta original', origen: 'suya', duenio: ['codigo', 'ia'], gate: 'Condición previa: la original está validada y tú lo confirmaste.',
    evidencia: 'Hay al menos un anuncio copiado del mejor de la original por costo neto por venta, y la original está en fase validada, con tu confirmación firmada.',
    tecnica: 'Al menos un anuncio con ad_origen igual al mejor de la madre por costo neto por compra; la madre en fase validada con confirmar_validada firmado.' },
  { id: 'K4', col: 'CREATIVOS', titulo: 'Calidad de idioma auditada', origen: 'suya', duenio: ['ia', 'codigo', 'humano'], gate: 'Revisión de la página de venta y de los anuncios; revisor nativo humano si la ley exige el idioma.',
    evidencia: 'Hay un informe lingüístico completo (retraducción, segunda lectura con otro modelo y nota del auditor nativo) sobre la página de venta, los correos, los textos legales y los subtítulos.',
    tecnica: 'linguistico.json completo (retraducción, segunda lectura con otro modelo, nota del auditor nativo) sobre landing, correos, legales y subtítulos.' },
  { id: 'L1', col: 'LISTO', titulo: 'Auditoría completa: vistos buenos vigentes, revisión aprobada y chequeo en verde', origen: 'suya', duenio: ['codigo'], gate: 'Veto de cumplimiento: no se relaja.',
    evidencia: 'Los vistos buenos de cumplimiento de la página, los anuncios y la campaña están vigentes con la huella actual. La revisión de calidad aprobó desde la oferta hasta la campaña, el chequeo antes de lanzar está en verde y vigente, la infraestructura está en verde (menos de 6 horas), no hay pausa general y las fichas de país no están vencidas.',
    tecnica: 'Sellos de X1 en D5, D6 y D7 con el hash actual; revisión de calidad PASS de D3 a D7; preflight VERDE y vigente; infraestructura VERDE (menos de 6 h); sin PAUSA; fichas de país no vencidas.' },
  { id: 'L2', col: 'LISTO', titulo: 'Apertura del idioma firmada por ti', origen: 'nueva', duenio: ['humano'], gate: 'Es tuya y no se puede quitar, ni con el nivel de autonomía más alto.',
    evidencia: 'La ficha de mercado de la oferta trae tu firma de aprobación y la acción de abrir un idioma nuevo figura en tus decisiones. Se firma al principio y se vuelve a comprobar al final con la huella.',
    tecnica: 'mercado.json con aprobado_por (firma Ed25519); la acción lanzamiento_pais_idioma_nuevo figura en decisiones_dueno.jsonl. Se firma al principio y se revalida al final por hash.' },
  { id: 'L3', col: 'LISTO', titulo: 'Testeo prendido', origen: 'suya', duenio: ['codigo'], gate: 'Tú activas la campaña (si el nivel de autonomía actual lo pide).', poscondicion: true,
    evidencia: 'No es un requisito sino una consecuencia: la campaña queda activa con la estructura aprobada (huella de la configuración, objetos exactos y firma) y al volver a leer Meta se confirman el estado, los países, los idiomas y el presupuesto.',
    tecnica: 'Poscondición, no requisito: la campaña queda ACTIVE con la estructura aprobada (hash_config, object_ids exactos y firma); la relectura de Meta confirma estado, países, idiomas y presupuesto.' },
]);

export const REGLA_SALIDA = 'Un idioma no se lanza hasta que todas las tarjetas pasan a Listo.';
export const REGLA_SALIDA_DETALLE = 'Se cuentan las 24 tarjetas anteriores; la última («Testeo prendido») la marca el sistema cuando activas la campaña. Una tarjeta vencida o bloqueada impide activar.';

// ───────────────────────── estado de una tarjeta ─────────────────────────

export const ESTADO_TARJETA = Object.freeze({
  sin_evidencia: { tono: 'neutro', icono: 'circulo-punteado', texto: 'Sin evidencia todavía', listo: false },
  pendiente: { tono: 'aviso', icono: 'circulo', texto: 'Pendiente', listo: false },
  en_curso: { tono: 'info', icono: 'progreso', texto: 'En curso', listo: false },
  verificada: { tono: 'ok', icono: 'ok', texto: 'Listo', listo: true },
  no_aplica_firmada: { tono: 'ok', icono: 'check', texto: 'No aplica (firmado)', listo: true },
  no_aplica_sin_firma: { tono: 'aviso', icono: 'alerta', texto: 'No aplica, sin firma', listo: false },
  vencida: { tono: 'aviso', icono: 'reloj-alerta', texto: 'Vencida', listo: false },
  bloqueada: { tono: 'error', icono: 'candado', texto: 'Bloqueada', listo: false },
});

const ALIAS_ESTADO = {
  verificada: 'verificada', verificado: 'verificada', listo: 'verificada', listas: 'verificada', ok: 'verificada', verde: 'verificada', hecho: 'verificada',
  no_aplica_firmada: 'no_aplica_firmada', 'no aplica firmada': 'no_aplica_firmada', no_aplica: 'no_aplica_sin_firma', 'no aplica': 'no_aplica_sin_firma',
  en_curso: 'en_curso', 'en curso': 'en_curso', en_progreso: 'en_curso',
  bloqueada: 'bloqueada', bloqueado: 'bloqueada', rojo: 'bloqueada', fail: 'bloqueada',
  pendiente: 'pendiente', amarillo: 'pendiente', vencida: 'vencida',
};

/** Clave de ESTADO_TARJETA de un valor del archivo (desconocido → 'pendiente'; ausente → 'sin_evidencia'). */
export function claveEstado(valor) {
  if (valor === null || valor === undefined || valor === '') return 'sin_evidencia';
  return ALIAS_ESTADO[plano(valor)] || 'pendiente';
}

function normalizarColumna(c) {
  const k = plano(c).replace(/\s+/g, ' ');
  for (const col of COLUMNAS) if (k === plano(col.id) || k === plano(col.nombre) || (col.id === 'LISTO' && k.startsWith('listo'))) return col.id;
  return null;
}

const ms = (v) => { const t = typeof v === 'string' ? Date.parse(v) : NaN; return Number.isNaN(t) ? null : t; };

function evidencias(t) {
  return lista(t.evidencia).map((e) => {
    if (typeof e === 'string') return { tipo: null, ref: texto(e, 200), detalle: null };
    if (!esObj(e)) return null;
    return { tipo: texto(e.tipo, 20), ref: texto(e.ref ?? e.archivo ?? e.comando, 200), detalle: texto(e.resultado ?? e.sha256 ?? e.detalle, 120) };
  }).filter((e) => e && (e.ref || e.detalle));
}

/**
 * Tablero de lanzamiento de un idioma. `doc` = contenido de lanzamiento_idioma.json (o null si no existe). Une la PLANTILLA con el estado del archivo.
 * `lectura` = {estado:'ok'|'ausente'|'ilegible'|…, dato}. Devuelve las 6 columnas con sus tarjetas, el recuento y si el idioma puede lanzarse.
 */
export function modeloTablero(lectura, { ahora = Date.now() } = {}) {
  const estadoLectura = lectura ? lectura.estado : 'ausente';
  const doc = lectura && lectura.estado === 'ok' && esObj(lectura.dato) ? lectura.dato : null;
  const delArchivo = new Map();
  const extras = [];
  if (doc) {
    for (const t of lista(doc.tarjetas)) {
      if (!esObj(t)) continue;
      const id = texto(t.id, 12);
      if (!id) continue;
      const plantilla = TARJETAS.find((x) => x.id.toUpperCase() === id.toUpperCase());
      if (plantilla) delArchivo.set(plantilla.id, t);
      else extras.push(t);
    }
  }
  const construir = (base, t) => {
    let clave = t ? claveEstado(t.estado) : 'sin_evidencia';
    const vence = t ? ms(t.valido_hasta) : null;
    if (t && ESTADO_TARJETA[clave].listo && vence !== null && vence < ahora) clave = 'vencida';
    return {
      ...base,
      estado: clave, info: ESTADO_TARJETA[clave], estadoCrudo: t ? texto(t.estado, 40) : null,
      evidenciaReal: t ? evidencias(t) : [], validoHasta: t ? texto(t.valido_hasta, 30) : null,
      bloquea: t ? lista(t.bloquea).map((x) => texto(x, 12)).filter(Boolean) : [], dueniosArchivo: t ? texto(t.duenio, 20) : null,
    };
  };
  const tarjetas = TARJETAS.map((b) => construir(b, delArchivo.get(b.id)));
  for (const t of extras) {
    const col = normalizarColumna(t.columna) || 'LISTO';
    tarjetas.push(construir({ id: texto(t.id, 12), col, titulo: texto(t.titulo, 120) || 'Tarjeta sin título', origen: 'archivo', duenio: [], gate: null, evidencia: null, poscondicion: false }, t));
  }
  const columnas = COLUMNAS.map((c) => {
    const tj = tarjetas.filter((t) => t.col === c.id);
    return { ...c, tarjetas: tj, listas: tj.filter((t) => t.info.listo).length, total: tj.length };
  });
  const requisitos = tarjetas.filter((t) => !t.poscondicion);
  const listasReq = requisitos.filter((t) => t.info.listo).length;
  const listoParaLanzar = requisitos.length > 0 && listasReq === requisitos.length;
  const semaforoArchivo = doc ? texto(doc.semaforo, 12) : null;
  const incoherente = Boolean(semaforoArchivo) && plano(semaforoArchivo) === 'verde' && !listoParaLanzar;
  return {
    estadoLectura, hayArchivo: Boolean(doc),
    columnas, tarjetas,
    listas: tarjetas.filter((t) => t.info.listo).length, total: tarjetas.length,
    requisitosListos: listasReq, requisitosTotal: requisitos.length,
    listoParaLanzar,
    pendientes: requisitos.filter((t) => !t.info.listo).map((t) => t.id),
    semaforoArchivo, incoherente,
    locale: doc ? texto(doc.locale, 16) : null,
    paises: doc ? lista(doc.paises_segmentacion).map((p) => texto(p, 4)).filter(Boolean) : [],
    generadoEn: doc ? texto(doc.generado_en, 30) : null, hash: doc ? texto(doc.hash, 90) : null,
    varianteDe: doc ? texto(doc.variante_de, 40) : null,
  };
}

// ───────────────────────── obligaciones por país que el método no trae ─────────────────────────

const UE = new Set(['AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU', 'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE']);
const UK = new Set(['GB', 'UK']);
const algun = (paises, conjunto) => lista(paises).some((p) => conjunto.has(String(p).toUpperCase()));

export const OBLIGACIONES = Object.freeze([
  { id: 'B01', nombre: 'IVA de la UE (régimen OSS)', glosario: 'oss_iva', tarjeta: 'C4', aplica: (p) => algun(p, UE),
    exige: 'Un vendedor de fuera de la UE declara el IVA de todas sus ventas a consumidores desde un solo país miembro, sin mínimo de ventas y desde la primera venta. Stripe Tax calcula el impuesto pero no lo presenta.' },
  { id: 'B02', nombre: 'IVA del Reino Unido', glosario: 'oss_iva', tarjeta: 'C4', aplica: (p) => algun(p, UK), exige: 'Registro ante la agencia tributaria británica desde la primera venta.' },
  { id: 'B03', nombre: 'Suiza, Quebec e India', glosario: null, tarjeta: null, aplica: (p) => algun(p, new Set(['CH', 'IN', 'CA'])),
    exige: 'Suiza pide representante fiscal; Quebec exige francés; India pide registro desde la primera venta. No se listan como idioma permitido hasta tener su ficha de mercado y de cumplimiento.' },
  { id: 'B04', nombre: 'Desistimiento (14 días)', glosario: 'desistimiento_ue', tarjeta: 'C5', aplica: (p) => algun(p, UE) || algun(p, UK),
    exige: 'En la UE el comprador puede desistir en 14 días; en un producto digital solo se pierde con su consentimiento previo en una casilla aparte y sin premarcar, más un correo de confirmación. La UE exige además una función de desistimiento en 2 pasos.' },
  { id: 'B05', nombre: 'Consentimiento y medición', glosario: 'consentimiento_marketing', tarjeta: 'M3', aplica: (p) => algun(p, UE) || algun(p, UK),
    exige: 'En la UE y el Reino Unido, el medidor de Meta y el envío de conversiones por servidor solo se activan después de que el visitante da su permiso. Por eso nunca se va a poder saber de qué anuncio vino el 100 % de las ventas.' },
  { id: 'B06', nombre: 'Anunciante y pagador (ley europea DSA)', glosario: 'anunciante_dsa', tarjeta: 'M5', aplica: (p) => algun(p, UE), exige: 'Todo anuncio nuevo o editado hacia la UE necesita beneficiario y pagador declarados.' },
  { id: 'B07', nombre: 'Idioma legal obligatorio', glosario: null, tarjeta: 'T2', aplica: (p) => algun(p, new Set(['PL', 'FR', 'CA'])),
    exige: 'Polonia, Francia y Quebec exigen textos, garantías y contratos en el idioma local. Sin revisor nativo el idioma no se aprueba; la auditoría automática de calidad no lo sustituye.' },
  { id: 'B08', nombre: 'Datos legales del vendedor (Impressum)', glosario: null, tarjeta: 'T2', aplica: (p) => algun(p, new Set(['DE', 'AT', 'FR'])),
    exige: 'Alemania y Austria exigen el Impressum (los datos legales del vendedor); Francia pide las menciones legales. La identidad de la empresa vendedora debe verse en cada sitio.' },
  { id: 'B09', nombre: 'Tarifa de ubicación de Meta', glosario: null, tarjeta: 'C1', aplica: (p) => algun(p, new Set(['FR', 'IT', 'ES', 'AT', 'GB', 'UK', 'TR'])),
    exige: 'Meta cobra un recargo por país que varía, se anota aparte del gasto y lleva IVA. «Francés Europa» mezcla países con tarifas distintas: se calcula por país, no por idioma.' },
  { id: 'B10', nombre: 'Ayuda por país y avisos', glosario: null, tarjeta: null, aplica: () => null,
    exige: 'En relaciones y salud, una línea de ayuda del país vigente (menos de 180 días). Rumanía tiene bloqueado el tema emocional. Depende del nicho de la oferta.' },
  { id: 'B11', nombre: 'Divulgación de IA', glosario: null, tarjeta: 'K1', aplica: () => true,
    exige: 'Meta y la ley de IA de la UE piden rotular las voces y los personajes simulados con IA de los anuncios.' },
  { id: 'B12', nombre: 'Promesas permitidas por idioma', glosario: null, tarjeta: 'T2', aplica: () => true,
    exige: 'Lo que se puede prometer cambia por idioma («cura», plazos, atributos): traducir un anuncio ganador arrastra su promesa, por eso cada idioma tiene su propia revisión.' },
  { id: 'B13', nombre: 'Verificación financiera de Meta', glosario: null, tarjeta: null, aplica: (p) => algun(p, new Set(['AU', 'GB', 'UK', 'IE', 'ES'])),
    exige: 'Australia, Reino Unido, Irlanda y España piden verificación o un aviso «pagado por» según el producto (sobre todo en dinero).' },
  { id: 'B14', nombre: 'Nombre del cargo en la tarjeta con varios dominios', glosario: null, tarjeta: null, aplica: () => null,
    exige: 'Varios sitios bajo una sola cuenta de cobro pueden provocar reclamos de «no reconozco este cargo». Hay que preguntar a Stripe y al contador antes del segundo dominio activo.' },
]);

/** Lo que la oferta YA declara en su mercado.json para cada obligación (declarar no es verificar). → { B01: {texto, tono}, … } */
export function declaradoPorMercado(m) {
  const salida = {};
  if (!m) return salida;
  const f = m.fiscal || {};
  if (f.regimen) {
    const firmado = f.firmadaPor && f.paisesFirmados.length;
    const diferido = plano(f.regimen) === 'diferido';
    salida.B01 = diferido
      ? { texto: firmado ? `Régimen diferido; exposición firmada para ${f.paisesFirmados.join(', ')}` : 'Régimen diferido, sin firma de exposición', tono: firmado ? 'aviso' : 'error' }
      : { texto: `Régimen: ${String(f.regimen).replace(/_/g, ' ')}`, tono: 'ok' };
    salida.B02 = salida.B01;
  } else { salida.B01 = { texto: 'No declara régimen fiscal', tono: 'neutro' }; salida.B02 = salida.B01; }
  const c = m.consumo || {};
  if (c.desistimientoDias !== null && c.desistimientoDias !== undefined) {
    salida.B04 = { texto: `Desistimiento de ${c.desistimientoDias} días${c.botonArrepentimiento ? ' · con botón de arrepentimiento' : ''}`, tono: 'ok' };
  }
  if (c.consentimientoCookies !== null && c.consentimientoCookies !== undefined) {
    salida.B05 = { texto: c.consentimientoCookies ? `Consentimiento de cookies activo${c.leyPrivacidad ? ` (${c.leyPrivacidad})` : ''}` : 'Sin consentimiento de cookies', tono: c.consentimientoCookies ? 'ok' : 'error' };
  }
  const il = m.idiomaLegal || {};
  if (il.obligacion !== null && il.obligacion !== undefined) {
    if (il.obligacion && il.revisorNativo !== true) salida.B07 = { texto: 'Idioma con obligación legal y sin revisor nativo: no se puede dar el visto bueno', tono: 'error' };
    else if (il.obligacion) salida.B07 = { texto: 'Idioma con obligación legal y con revisor nativo', tono: 'ok' };
    else salida.B07 = { texto: `Sin obligación legal de idioma${il.revisorNativo === true ? ' · con revisor nativo' : ' · sin revisor nativo'}`, tono: 'neutro' };
  }
  return salida;
}

/** Filas de la tabla de obligaciones para unos países y lo que declara la oferta. */
export function filasObligaciones(paises, mercado) {
  const decl = declaradoPorMercado(mercado);
  return OBLIGACIONES.map((o) => {
    const aplica = paises && paises.length ? o.aplica(paises) : null;
    return { id: o.id, nombre: o.nombre, exige: o.exige, glosario: o.glosario, tarjeta: o.tarjeta, aplica, declara: decl[o.id] || null };
  });
}

// ───────────────────────── mercado de cada oferta y rutas de familia ─────────────────────────

/** Fila de «Mercado e idioma de cada oferta». */
export function filaMercado(oferta, detalle, tablero) {
  const m = mercadoDe(detalle);
  return {
    id: oferta.id, demo: Boolean(oferta.demo), interno: oferta.interno || null, fase: oferta.fase || null,
    hayMercado: Boolean(m), locale: m ? m.locale : null, paises: m ? m.paises : [], moneda: m ? m.moneda : null, decision: m ? m.decision : null,
    regimen: m && m.fiscal ? m.fiscal.regimen : null, revisorNativo: m && m.idiomaLegal ? m.idiomaLegal.revisorNativo : null, obligacionLegal: m && m.idiomaLegal ? m.idiomaLegal.obligacion : null,
    primerLanzamiento: m ? m.primerLanzamiento : null,
    familia: oferta.familia || (m ? m.familia : null), varianteDe: m ? m.varianteDe : null,
    tablero: tablero ? { hayArchivo: tablero.hayArchivo, listas: tablero.listas, total: tablero.total, listo: tablero.listoParaLanzar } : { hayArchivo: false, listas: 0, total: TARJETAS.length, listo: false },
  };
}

/**
 * Agrupa las ofertas por familia (un concepto en N idiomas). La madre es la que no es variante de otra; las hijas apuntan a ella con variante_de.
 * Regla: una hija solo puede crearse cuando la madre está validada (mercados.hija_requiere_madre_validada).
 */
export function agruparFamilias(filas) {
  const porFamilia = new Map();
  for (const f of lista(filas)) {
    const k = f.familia || `(sin familia) ${f.id}`;
    if (!porFamilia.has(k)) porFamilia.set(k, []);
    porFamilia.get(k).push(f);
  }
  return [...porFamilia.entries()].map(([familia, miembros]) => {
    const apuntadas = new Set(miembros.map((x) => x.varianteDe).filter(Boolean));
    const madre = miembros.find((x) => !x.varianteDe && (apuntadas.has(x.id) || apuntadas.has(x.interno))) || miembros.find((x) => !x.varianteDe) || miembros[0];
    const hijas = miembros.filter((x) => x !== madre);
    return {
      familia: familia.startsWith('(sin familia)') ? null : familia, madre, hijas,
      madreValidada: esMadreValidada(madre.fase), puedeCrearHijas: esMadreValidada(madre.fase),
      idiomas: [...new Set(miembros.map((x) => x.locale).filter(Boolean))],
    };
  });
}

/** Totales de las métricas. */
export function resumenPaises(filas, tableros) {
  const fs = lista(filas);
  const conMercado = fs.filter((f) => f.hayMercado);
  return {
    ofertas: fs.length, conMercado: conMercado.length,
    idiomas: new Set(conMercado.map((f) => f.locale).filter(Boolean)).size,
    tablerosConEvidencia: lista(tableros).filter((t) => t && t.hayArchivo).length,
    idiomasListos: lista(tableros).filter((t) => t && t.listoParaLanzar).length,
  };
}

