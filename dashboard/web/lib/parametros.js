// lib/parametros.js — lógica pura de #/parametros (CONTRATO §4 `GET /parametros`). SOLO LECTURA: el panel nunca edita límites,
// parámetros ni autonomía (los escribe el dueño; `engine.limites sellar` firma). Fuentes: empresa/limites.yaml, empresa/parametros.yaml,
// empresa/autonomia.yaml, empresa/propuestas/*.yaml y scripts/modelado/*propuesta.yaml.
// Una clave en `null` significa «nada gasta hasta que se fije» (fail-closed, engine/README): aquí se resalta y se dice QUÉ desbloquea.
// Sin DOM ni red.

import { gruposDeParametros } from './operacion.js';

/** Espejo de scripts/validar_esquemas.py::CLAVES_CRITICAS (qué claves exige cada operación del motor). Una prueba compara ambos. */
export const OPERACIONES = {
  gastar: {
    titulo: 'Gastar (dejar campañas preparadas en Meta)', ayuda: 'Crear las campañas en Meta, todavía apagadas. Ya compromete tu marco de pérdidas y de gasto.',
    claves: ['moneda_limites', 'capital_en_riesgo_total', 'gasto_diario_global', 'gasto_diario_por_oferta', 'gasto_total_test_por_oferta', 'perdida_max_test_por_oferta',
      'perdida_neta_acumulada_max', 'ofertas_en_test_simultaneas_max', 'limite_gasto_cuenta_meta', 'cuentas_permitidas', 'paises_permitidos', 'locales_permitidos'],
  },
  aumentar_presupuesto: {
    titulo: 'Subir el presupuesto', ayuda: 'Subir el presupuesto de una campaña dentro del tamaño de paso y del ritmo permitidos.',
    claves: ['gasto_diario_global', 'gasto_diario_por_oferta', 'aumento_presupuesto_max_pct_por_paso', 'horas_min_entre_aumentos', 'limite_gasto_cuenta_meta'],
  },
  escalar: {
    titulo: 'Escalar una oferta', ayuda: 'Hacer crecer una oferta ya validada, con colchón de caja y un tope de pérdida.',
    claves: ['gasto_diario_global', 'gasto_diario_por_oferta', 'aumento_presupuesto_max_pct_por_paso', 'horas_min_entre_aumentos', 'stop_loss_escala', 'dias_cobertura_caja',
      'perdida_neta_acumulada_max', 'limite_gasto_cuenta_meta'],
  },
  reembolsar_auto: { titulo: 'Reembolsar automáticamente', ayuda: 'Reembolsos hechos solos, con un máximo por pedido y por día.', claves: ['reembolso_auto_max', 'reembolsos_auto_max_por_dia'] },
  descubrir: {
    titulo: 'Descubrir ofertas (barrido de búsqueda)', ayuda: 'Buscar problemas y ofertas en el mercado: cuántas búsquedas, cuántos barridos y cuánto cuestan.',
    claves: ['fuentes_permitidas', 'max_busquedas_por_barrido', 'max_barridos_por_semana', 'max_costo_por_barrido', 'max_consultas_biblioteca'],
  },
  generar_creativos: { titulo: 'Generar anuncios (imágenes y videos)', ayuda: 'Créditos de imagen y video, y costo de la IA en cada tarea.', claves: ['creditos_max_pieza', 'creditos_max_oferta', 'max_budget_por_corrida_agente'] },
  enviar_correo: { titulo: 'Enviar correos a compradores', ayuda: 'Correos de después de la compra, con un tope por día y por semana.', claves: ['correos_max_por_dia', 'correos_max_por_semana'] },
};
OPERACIONES.activar = {
  titulo: 'Activar una campaña (siempre con tu firma)', ayuda: 'Pasar de borrador a gastar plata de verdad. Exige todo lo de «Gastar» más el precio mínimo y las políticas. Además siempre pide tu firma.',
  claves: [...OPERACIONES.gastar.claves, 'precio_neto_minimo', 'politica_divulgacion_ia', 'ratio_disputas_pausa', 'politica_reembolso_dias'],
};
const ORDEN_OPERACIONES = ['gastar', 'activar', 'aumentar_presupuesto', 'escalar', 'reembolsar_auto', 'descubrir', 'generar_creativos', 'enviar_correo'];

/** Claves cuya lista vacía bloquea (listas exigidas por alguna operación). */
const LISTAS_EXIGIDAS = new Set(Object.values(OPERACIONES).flatMap((o) => o.claves).filter((k) => /_permitid[oa]s$/.test(k) || k === 'cuentas_permitidas'));

/** Metadatos de cada clave de limites.yaml: grupo, tipo para formatear y qué es (de los comentarios del archivo). */
export const LIMITES_META = {
  moneda_limites: { grupo: 'gasto', tipo: 'texto', ayuda: 'Moneda de TODOS los importes de este archivo. Tiene que ser la de tu única cuenta publicitaria de Meta.' },
  capital_en_riesgo_total: { grupo: 'capital', tipo: 'importe', ayuda: 'Todo el dinero que aceptas arriesgar en total (anuncios más reservas).' },
  reserva_no_publicitaria_pct: { grupo: 'capital', tipo: 'pct', ayuda: 'Parte del capital que NO va a anuncios: Stripe, herramientas, créditos de IA y reembolsos.', usos: ['revisar que el capital cuadre'] },
  perdida_max_test_por_oferta: { grupo: 'capital', tipo: 'importe', ayuda: 'Lo máximo que aceptas perder probando una oferta. Lo dejaste para después (2026-11-06): se fijará a partir de los presupuestos de prueba.' },
  perdida_neta_acumulada_max: { grupo: 'capital', tipo: 'importe', ayuda: 'Lo máximo que pueden perder todas las ofertas juntas, restando lo que ganan. Al llegar ahí, el sistema pausa todo.' },
  stop_loss_escala: { grupo: 'capital', tipo: 'importe', ayuda: 'Lo máximo que puede perder UNA oferta mientras se escala (lo que queda después de los costos de cada venta).' },
  limite_gasto_cuenta_meta: { grupo: 'capital', tipo: 'importe', ayuda: 'Segundo candado: un tope de gasto total puesto en la propia cuenta de Meta. Al alcanzarlo, Meta pausa todo.' },
  gasto_diario_global: { grupo: 'gasto', tipo: 'importe', ayuda: 'Tope diario de toda la empresa. Se compara con lo máximo que Meta podría gastar (1,75 veces los presupuestos diarios).' },
  gasto_diario_por_oferta: { grupo: 'gasto', tipo: 'importe', ayuda: 'Tope diario de una sola oferta (también contra lo máximo que Meta podría gastar).' },
  gasto_total_test_por_oferta: { grupo: 'gasto', tipo: 'importe', ayuda: 'Lo máximo que se gasta en total probando una oferta.' },
  ofertas_en_test_simultaneas_max: { grupo: 'gasto', tipo: 'entero', ayuda: 'Cuántas ofertas se pueden probar a la vez.' },
  factor_techo_teorico_diario: { grupo: 'gasto', tipo: 'constante', ayuda: 'Meta puede gastar hasta 1,75 veces el presupuesto diario. Es una regla de Meta, no una decisión tuya.' },
  aumento_presupuesto_max_pct_por_paso: { grupo: 'ritmo', tipo: 'pct', ayuda: 'Cuánto se puede subir el presupuesto de una sola vez, en porcentaje (20 = 20 %).' },
  horas_min_entre_aumentos: { grupo: 'ritmo', tipo: 'entero', ayuda: 'Horas que tienen que pasar entre una subida de presupuesto y la siguiente (referencia: 72 h).' },
  max_cambios_presupuesto_por_hora_por_conjunto: { grupo: 'ritmo', tipo: 'constante', ayuda: 'Límite de Meta para cambiar presupuestos por hora (lo fija la plataforma).' },
  segundos_min_entre_ediciones: { grupo: 'ritmo', tipo: 'constante', ayuda: 'Tiempo mínimo entre dos cambios al mismo elemento (lo fija la plataforma).' },
  cuentas_permitidas: { grupo: 'alcance', tipo: 'lista', ayuda: 'Cuentas publicitarias autorizadas: lista cerrada; por ahora, una sola.' },
  paises_permitidos: { grupo: 'alcance', tipo: 'lista', ayuda: 'Países donde se pueden mostrar los anuncios. Ningún país parte con ventaja.' },
  locales_permitidos: { grupo: 'alcance', tipo: 'lista', ayuda: 'Idioma y país en los que se puede lanzar. Cada idioma es una oferta distinta.' },
  macro_nichos_permitidos: { grupo: 'alcance', tipo: 'constante', ayuda: 'Fijo por decisión tuya: salud, relaciones y dinero.' },
  subnichos_prohibidos: { grupo: 'alcance', tipo: 'lista', opcional: true, ayuda: 'Temas que quedan excluidos por completo. Vacío: ningún tema se descarta por sí solo.' },
  lineas_rojas: { grupo: 'alcance', tipo: 'lista', opcional: true, ayuda: 'Líneas rojas: promesas, contenidos y modelos de negocio que nunca se usan (se mira la promesa, no el tema).' },
  fuentes_permitidas: { grupo: 'alcance', tipo: 'lista', ayuda: 'Fuentes donde el descubrimiento puede buscar. Vacío: no busca en ningún lado.' },
  fuentes_prohibidas: { grupo: 'alcance', tipo: 'lista', opcional: true, ayuda: 'Fuentes donde el descubrimiento no puede buscar.' },
  precio_neto_minimo: { grupo: 'ventas', tipo: 'importe', ayuda: 'Precio neto mínimo por pedido para poder lanzar una oferta.' },
  autoaprobar_hasta: { grupo: 'ventas', tipo: 'importe', ayuda: 'Monto hasta el cual el sistema puede aprobar un gasto sin pedirte permiso (solo desde el nivel 3).', usos: ['aprobar sin ti montos chicos (nivel 3 o más)'] },
  reembolso_auto_max: { grupo: 'ventas', tipo: 'importe', ayuda: 'Reembolso automático máximo por pedido.' },
  reembolsos_auto_max_por_dia: { grupo: 'ventas', tipo: 'entero', ayuda: 'Cuántos reembolsos automáticos se pueden hacer por día (el día se cuenta en hora universal, UTC).' },
  ratio_disputas_pausa: { grupo: 'ventas', tipo: 'decimal', ayuda: 'Pausa total: si las disputas y los reclamos de pago superan esta proporción de los pagos de 30 días (0,006 = 0,6 %), se pausa todo.' },
  cupon_descuento_max_pct: { grupo: 'ventas', tipo: 'pct', ayuda: 'Descuento máximo de un cupón.', usos: ['cupones de descuento'] },
  politica_reembolso_dias: { grupo: 'ventas', tipo: 'entero', ayuda: 'Días de garantía en los que el comprador puede pedir reembolso.' },
  politica_divulgacion_ia: { grupo: 'ventas', tipo: 'texto', ayuda: 'Cómo se avisa que un anuncio se hizo con IA (decisión tuya).' },
  dias_cobertura_caja: { grupo: 'ventas', tipo: 'entero', ayuda: 'Días de caja que tienen que estar cubiertos antes de subir presupuesto (los días que Stripe tarda en pagarte, más 7).' },
  creditos_max_pieza: { grupo: 'costos', tipo: 'entero', ayuda: 'Créditos de generación máximos por anuncio (son créditos, no dinero).' },
  creditos_max_oferta: { grupo: 'costos', tipo: 'entero', ayuda: 'Créditos de generación máximos por oferta.' },
  max_budget_por_corrida_agente: { grupo: 'costos', tipo: 'importe', ayuda: 'Lo máximo que puede costar la IA en una sola tarea (se compara en «Equipo de IA»).' },
  costo_max_validacion: { grupo: 'costos', tipo: 'importe', ayuda: 'Costo máximo de herramientas de pago al validar el mercado.', usos: ['validación del mercado'] },
  costo_max_producto: { grupo: 'costos', tipo: 'importe', ayuda: 'Costo máximo de fabricar un producto (créditos más uso de IA).', usos: ['fabricación del producto'] },
  max_costo_por_barrido: { grupo: 'costos', tipo: 'importe', ayuda: 'Costo máximo de cada barrido de búsqueda de ofertas.' },
  max_consultas_biblioteca: { grupo: 'costos', tipo: 'entero', ayuda: 'Consultas máximas a la Biblioteca de Anuncios de Meta por oferta o por tarea.', usos: ['investigación de anuncios'] },
  max_busquedas_por_barrido: { grupo: 'costos', tipo: 'entero', ayuda: 'Búsquedas web máximas por barrido.' },
  max_barridos_por_semana: { grupo: 'costos', tipo: 'entero', ayuda: 'Barridos máximos por semana.' },
  correos_max_por_dia: { grupo: 'comunicacion', tipo: 'entero', ayuda: 'Correos máximos por día.' },
  correos_max_por_semana: { grupo: 'comunicacion', tipo: 'entero', ayuda: 'Correos máximos por semana.' },
  ventana_veto_min: { grupo: 'comunicacion', tipo: 'entero', ayuda: 'Minutos que tienes para frenar una acción antes de que se haga (solo en el nivel 4).', usos: ['plazo para frenar en el nivel 4'] },
  acciones_gate_humano: { grupo: 'gates', tipo: 'lista', opcional: true, ayuda: 'Acciones que SIEMPRE piden tu firma, en cualquier nivel (se pueden agregar, pero no quitar sin tu firma).' },
  hojas_pausadas: { grupo: 'riesgo', tipo: 'lista', opcional: true, nuloSeguro: true, ayuda: 'Ramas del árbol de nichos pausadas por un motivo operativo (nunca por el tema). Vacío: ninguna.' },
  nivel_max_lanzable: { grupo: 'riesgo', tipo: 'texto', opcional: true, nuloSeguro: true, ayuda: 'Riesgo máximo que se puede lanzar por área: verde, amarillo-a o amarillo-b. Sin fijar: solo verde.', usos: ['ofertas de riesgo amarillo'] },
  cuota_gasto_amarillo_max_pct: { grupo: 'riesgo', tipo: 'pct', opcional: true, nuloSeguro: true, ayuda: 'Parte máxima del gasto diario que puede ir a ofertas de riesgo amarillo (0 a 100). Sin fijar: solo verde.', usos: ['ofertas de riesgo amarillo'] },
  cuota_gasto_amarillo_b_max_pct: { grupo: 'riesgo', tipo: 'pct', opcional: true, nuloSeguro: true, ayuda: 'Parte máxima del gasto diario para amarillo-b (0 a 100, no mayor que la de amarillo). Sin fijar: no hay amarillo-b.', usos: ['ofertas de riesgo amarillo'] },
  envios_amarillo_a_semana: { grupo: 'riesgo', tipo: 'entero', opcional: true, nuloSeguro: true, ayuda: 'Ofertas amarillo-a que se pueden mandar a prueba por semana. Sin fijar: ninguna.', usos: ['ofertas de riesgo amarillo'] },
  envios_amarillo_b_mes: { grupo: 'riesgo', tipo: 'entero', opcional: true, nuloSeguro: true, ayuda: 'Ofertas amarillo-b que se pueden mandar a prueba por mes. Sin fijar: ninguna.', usos: ['ofertas de riesgo amarillo'] },
  dias_limpios_para_subir_cuota: { grupo: 'riesgo', tipo: 'entero', opcional: true, nuloSeguro: true, ayuda: 'Días sin rechazos ni incidentes que hacen falta antes de subir la cuota de amarillo. Sin fijar: no se sube.', usos: ['ofertas de riesgo amarillo'] },
  edad_minima_audiencia: { grupo: 'riesgo', tipo: 'texto', opcional: true, nuloSeguro: true, ayuda: 'Edad mínima por defecto de la audiencia (13 o más). Sin fijar: se usa 18.', usos: ['audiencias de los anuncios'] },
  reserva_dias_stripe: { grupo: 'riesgo', tipo: 'entero', opcional: true, nuloSeguro: true, ayuda: 'Días que Stripe puede retener los cobros: dato de la plataforma, todavía por verificar.', usos: ['caja y cobros'] },
  zonas_grises: { grupo: 'riesgo', tipo: 'texto', opcional: true, nuloSeguro: true, ayuda: 'Casos dudosos del marco de riesgo y lo que decidiste en cada uno. Vacío: ninguno decidido.' },
  sello: { grupo: 'gates', tipo: 'sello', ayuda: 'Tu firma sobre todo este archivo de límites. Sin tu firma, nada gasta ni activa campañas.' },
};
export const GRUPOS_LIMITES = [
  { id: 'capital', titulo: 'Capital y pérdidas' }, { id: 'gasto', titulo: 'Gasto' }, { id: 'ritmo', titulo: 'Cada cuánto se cambia el presupuesto' }, { id: 'alcance', titulo: 'Dónde se puede operar (cuentas, países, temas, fuentes)' }, { id: 'riesgo', titulo: 'Riesgo y temas sensibles' },
  { id: 'ventas', titulo: 'Ventas, reembolsos y políticas' }, { id: 'costos', titulo: 'Costos y créditos' }, { id: 'comunicacion', titulo: 'Correos y plazo para frenar' }, { id: 'gates', titulo: 'Aprobaciones y tu firma' },
  { id: 'otros', titulo: 'Otros datos' },
];

/** Qué operaciones del motor exigen cada clave. */
export function desbloqueaDe(clave) {
  if (clave === 'sello') return ORDEN_OPERACIONES.map((id) => ({ id, titulo: OPERACIONES[id].titulo })); // sin sello, ninguna operación gasta
  return ORDEN_OPERACIONES.filter((id) => OPERACIONES[id].claves.includes(clave)).map((id) => ({ id, titulo: OPERACIONES[id].titulo }));
}

/** Estado de una clave: 'nulo' (bloquea) · 'ausente' (no está en el archivo: bloquea) · 'vacio' (lista exigida sin elementos: bloquea) · 'fijado' · 'fijo' (hecho de plataforma). */
export function estadoDeClave(clave, valor, enNulos = false) {
  const meta = LIMITES_META[clave] || {};
  if (clave === 'sello') return valor && typeof valor === 'object' ? 'fijado' : 'nulo';
  if (enNulos || valor === null) return 'nulo';
  if (valor === undefined) return 'ausente';
  if (meta.tipo === 'constante') return 'fijo';
  if (Array.isArray(valor)) return valor.length === 0 && LISTAS_EXIGIDAS.has(clave) ? 'vacio' : 'fijado';
  return 'fijado';
}

/** Texto de un valor de límites según su tipo (importes con la moneda del archivo, sin float). */
export function textoLimite(clave, valor, moneda, fmt) {
  const meta = LIMITES_META[clave] || {};
  if (valor === null || valor === undefined) return null;
  if (clave === 'sello') return valor && typeof valor === 'object' ? 'firmado por ti' : null;
  if (Array.isArray(valor)) return valor.length ? valor.join(', ') : '(lista vacía)';
  if (meta.tipo === 'importe' && Number.isSafeInteger(valor)) return moneda ? fmt.dinero(valor, moneda) : `${valor} (falta indicar la moneda)`;
  if (meta.tipo === 'pct' && typeof valor === 'number') return `${String(valor).replace('.', ',')} %`;
  if (meta.tipo === 'constante' && typeof valor === 'string') return `× ${valor.replace('.', ',')}`;
  if (typeof valor === 'object') return JSON.stringify(valor);
  return String(valor);
}

/** Modelo de limites.yaml: grupos, claves en null con lo que desbloquean y estado por operación. */
export function modeloLimites(limites, fmt) {
  const v = limites && typeof limites === 'object' && limites.valores && typeof limites.valores === 'object' ? limites.valores : null;
  if (!v) return null;
  const enNulos = new Set(Array.isArray(limites.nulos) ? limites.nulos : []);
  const moneda = typeof v.moneda_limites === 'string' ? v.moneda_limites : null;
  const claves = [...new Set([...Object.keys(LIMITES_META), ...Object.keys(v), ...enNulos])].filter((k) => !['schema_version', 'version'].includes(k));
  const filas = claves.map((clave) => {
    const meta = LIMITES_META[clave] || { grupo: 'otros', tipo: 'texto', ayuda: 'Clave sin descripción en el panel.' };
    const estado = estadoDeClave(clave, v[clave], enNulos.has(clave));
    const sinValor = estado === 'nulo' || estado === 'ausente' || estado === 'vacio';
    const seguro = sinValor && meta.nuloSeguro === true; // null = «solo verde» / valor por defecto prudente: no bloquea ninguna operación
    return {
      clave, grupo: meta.grupo, tipo: meta.tipo, ayuda: meta.ayuda, estado, bloquea: sinValor && !seguro, seguroPorDefecto: seguro, opcional: meta.opcional === true,
      valor: v[clave] === undefined ? null : v[clave], texto: textoLimite(clave, v[clave], moneda, fmt || { dinero: (m, c) => `${m} ${c}` }), desbloquea: desbloqueaDe(clave), usos: meta.usos || [],
    };
  });
  const operaciones = ORDEN_OPERACIONES.map((id) => {
    const exigidas = [...OPERACIONES[id].claves, 'sello']; // además de sus claves, todo exige el sello del dueño
    const faltantes = exigidas.filter((k) => { const f = filas.find((x) => x.clave === k); return !f || f.bloquea; });
    return { id, titulo: OPERACIONES[id].titulo, ayuda: OPERACIONES[id].ayuda, total: exigidas.length, fijadas: exigidas.length - faltantes.length, faltantes, ok: faltantes.length === 0 };
  });
  const grupos = GRUPOS_LIMITES.map((g) => ({ ...g, claves: filas.filter((f) => f.grupo === g.id) })).filter((g) => g.claves.length);
  const bloqueadas = filas.filter((f) => f.bloquea);
  return {
    moneda, sellado: v.sello !== null && v.sello !== undefined, filas, grupos, operaciones, bloqueadas,
    nNulos: bloqueadas.length, nFijados: filas.filter((f) => f.estado === 'fijado' || f.estado === 'fijo').length, total: filas.length,
    algunaOperacionHabilitada: operaciones.some((o) => o.ok),
  };
}

// ----------------------------------------------------------------------------------------------------------------
// parametros.yaml
// ----------------------------------------------------------------------------------------------------------------

/** Texto corto de un valor de parámetro (escalares, listas y mapas). */
export function textoValor(v, max = 140) {
  if (v === null || v === undefined) return 'null';
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  let s;
  try { s = JSON.stringify(v); } catch (_) { s = String(v); }
  return s.length > max ? `${s.slice(0, max - 1)}…` : s;
}

/** parametros.yaml → grupos con sus claves {valor, unidad, hipotesis, fuente, ultima_calibracion, rango}. */
export function modeloParametros(parametros) {
  const g = gruposDeParametros(parametros);
  if (!g || typeof g !== 'object') return null;
  const grupos = [];
  for (const [id, claves] of Object.entries(g)) {
    if (!claves || typeof claves !== 'object' || Array.isArray(claves)) continue;
    const filas = [];
    for (const [clave, p] of Object.entries(claves)) {
      const esObj = p && typeof p === 'object' && !Array.isArray(p) && 'valor' in p;
      const valor = esObj ? p.valor : p;
      filas.push({
        grupo: id, clave, ruta: `${id}.${clave}`, valor, texto: textoValor(valor), unidad: esObj && p.unidad ? String(p.unidad) : null, hipotesis: esObj ? p.hipotesis === true : null,
        fuente: esObj && typeof p.fuente === 'string' ? p.fuente : null, ultima: esObj ? (p.ultima_calibracion ?? null) : null, rango: esObj && Array.isArray(p.rango) ? p.rango : null,
        nulo: valor === null || valor === undefined,
      });
    }
    if (filas.length) grupos.push({ id, claves: filas });
  }
  if (!grupos.length) return null;
  const todas = grupos.flatMap((x) => x.claves);
  return {
    version: parametros && parametros.version !== undefined ? parametros.version : null, schema_version: parametros && parametros.schema_version ? parametros.schema_version : null,
    grupos, total: todas.length, hipotesis: todas.filter((x) => x.hipotesis).length, calibrados: todas.filter((x) => x.ultima).length, nulos: todas.filter((x) => x.nulo).length,
  };
}

// ----------------------------------------------------------------------------------------------------------------
// autonomia.yaml
// ----------------------------------------------------------------------------------------------------------------

export const NOMBRE_ETAPA = {
  O0: 'Coordinación de la cartera de ofertas', D0: 'Cuentas y servicios base', M1: 'Mercados e idiomas', D1: 'Descubrimiento', D2: 'Validación del mercado', D3: 'Diseño de la oferta', D4: 'Producto',
  D5: 'Página de venta, pago y medición', D6: 'Anuncios', D7: 'Campañas en Meta', D8: 'Optimización diaria', D9: 'Escalar lo que funciona', D10: 'Después de la venta', F1: 'Finanzas', F2: 'Panel y números del negocio',
  X1: 'Cumplimiento', X2: 'Memoria y aprendizaje',
};

export function modeloAutonomia(a) {
  const n = a && typeof a === 'object' ? (a.nivel_por_etapa && typeof a.nivel_por_etapa === 'object' ? a.nivel_por_etapa : null) : null;
  if (!n) return null;
  const etapas = Object.entries(n).map(([etapa, x]) => ({
    etapa, nombre: NOMBRE_ETAPA[etapa] || null, nivel: x && typeof x === 'object' ? (x.nivel || null) : (typeof x === 'string' ? x : null),
    desde: x && typeof x === 'object' ? (x.desde || null) : null, evidencia: x && typeof x === 'object' && Array.isArray(x.evidencia) ? x.evidencia.length : 0,
  }));
  const histograma = {};
  for (const e of etapas) if (e.nivel) histograma[e.nivel] = (histograma[e.nivel] || 0) + 1;
  return {
    version: a.version ?? null, etapas, histograma, descensos: Array.isArray(a.descensos) ? a.descensos : [], reglas: Array.isArray(a.reglas_descenso) ? a.reglas_descenso.filter((r) => typeof r === 'string') : [],
    todasN0: etapas.length > 0 && etapas.every((e) => e.nivel === 'N0'),
  };
}

// ----------------------------------------------------------------------------------------------------------------
// Propuestas pendientes de integrar
// ----------------------------------------------------------------------------------------------------------------

/** `propuestas:[{archivo, claves}]`; `claves` puede ser lista de rutas, mapa grupo→claves o solo un número. */
export function modeloPropuestas(lista) {
  const salida = [];
  for (const p of Array.isArray(lista) ? lista : []) {
    if (!p || typeof p !== 'object' || typeof p.archivo !== 'string') continue;
    let claves = [];
    let n = null;
    if (Array.isArray(p.claves)) claves = p.claves.map(String);
    else if (p.claves && typeof p.claves === 'object') claves = Object.entries(p.claves).flatMap(([g, ks]) => (Array.isArray(ks) ? ks.map((k) => `${g}.${k}`) : (ks && typeof ks === 'object' ? Object.keys(ks).map((k) => `${g}.${k}`) : [g])));
    else if (Number.isSafeInteger(p.claves)) n = p.claves;
    salida.push({
      archivo: p.archivo, claves, nClaves: n !== null ? n : claves.length, soloConteo: n !== null,
      origen: p.archivo.startsWith('scripts/modelado') ? 'Descubrimiento: modelado de ofertas ajenas' : p.archivo.startsWith('empresa/propuestas') ? 'Propuesta del sistema (reglas base)' : 'Otra propuesta',
    });
  }
  return salida;
}

// ----------------------------------------------------------------------------------------------------------------
// Búsqueda
// ----------------------------------------------------------------------------------------------------------------

const sinTildes = (s) => String(s).normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/** Todas las palabras de `q` deben aparecer (sin tildes ni mayúsculas) en el pajar. */
export function coincide(pajar, q) {
  const palabras = sinTildes(q || '').trim().split(/\s+/).filter(Boolean);
  if (!palabras.length) return true;
  const p = sinTildes(pajar);
  return palabras.every((w) => p.includes(w));
}

/** Filtra el modelo completo con una búsqueda: devuelve la misma forma con solo lo que coincide (y conteos). */
export function filtrarTodo(m, q) {
  if (!q || !String(q).trim()) return { ...m, consulta: '', coincidencias: null };
  const limites = m.limites ? { ...m.limites, grupos: m.limites.grupos.map((g) => ({ ...g, claves: g.claves.filter((c) => coincide(`${c.clave} ${c.ayuda} ${c.texto || ''} ${c.estado} ${c.desbloquea.map((d) => d.titulo + ' ' + d.id).join(' ')} ${c.usos.join(' ')}`, q)) })).filter((g) => g.claves.length) } : null;
  const parametros = m.parametros ? { ...m.parametros, grupos: m.parametros.grupos.map((g) => ({ ...g, claves: g.claves.filter((c) => coincide(`${c.ruta} ${c.texto} ${c.unidad || ''} ${c.fuente || ''}`, q)) })).filter((g) => g.claves.length) } : null;
  const autonomia = m.autonomia ? { ...m.autonomia, etapas: m.autonomia.etapas.filter((e) => coincide(`${e.etapa} ${e.nombre || ''} ${e.nivel || ''}`, q)) } : null;
  const propuestas = m.propuestas.map((p) => ({ ...p, clavesVisibles: p.claves.filter((c) => coincide(c, q)), visible: coincide(`${p.archivo} ${p.origen}`, q) })).filter((p) => p.visible || p.clavesVisibles.length);
  const cuenta = (limites ? limites.grupos.reduce((a, g) => a + g.claves.length, 0) : 0) + (parametros ? parametros.grupos.reduce((a, g) => a + g.claves.length, 0) : 0) + (autonomia ? autonomia.etapas.length : 0) + propuestas.length;
  return { ...m, limites, parametros, autonomia, propuestas, consulta: String(q).trim(), coincidencias: cuenta };
}

/** Normaliza lo que entrega GET /parametros. */
export function modeloPantallaParametros(datos, fmt) {
  const d = datos && typeof datos === 'object' ? datos : {};
  return {
    limites: modeloLimites(d.limites, fmt), parametros: modeloParametros(d.parametros), autonomia: modeloAutonomia(d.autonomia), propuestas: modeloPropuestas(d.propuestas),
  };
}

// ----------------------------------------------------------------------------------------------------------------
// Rediseño U4: «Esto desbloquea gasto»
// ----------------------------------------------------------------------------------------------------------------

/** Qué hay que escribir en cada tipo de clave (lenguaje humano). */
export const FORMA_DE_VALOR = {
  importe: 'un importe (en la moneda de los límites)', entero: 'un número entero', pct: 'un porcentaje', decimal: 'un número decimal', lista: 'al menos un elemento en la lista',
  texto: 'un texto', constante: 'nada: lo define la plataforma', sello: 'tu firma sobre todo el archivo',
};
/** Nombre corto de cada operación del motor (para chips compactos). */
export const NOMBRE_CORTO_OPERACION = { gastar: 'Gastar', activar: 'Activar campaña', aumentar_presupuesto: 'Subir presupuesto', escalar: 'Escalar', reembolsar_auto: 'Reembolsar', descubrir: 'Descubrir', generar_creativos: 'Anuncios', enviar_correo: 'Correos' };
export function formaDeValor(tipo, clave) {
  if (clave === 'moneda_limites') return 'el código de moneda (por ejemplo EUR)';
  return FORMA_DE_VALOR[tipo] || 'un valor';
}

/**
 * Claves sin fijar que BLOQUEAN alguna operación, de más a menos útiles (cuántas operaciones desbloquea cada una; el sello va siempre el primero).
 * Las claves en null que no exige ninguna operación hoy quedan aparte (`otras`).
 */
export function prioridadLimites(L) {
  if (!L) return { criticas: [], otras: [] };
  const criticas = L.bloqueadas.filter((f) => f.desbloquea.length > 0)
    .sort((a, b) => (b.clave === 'sello') - (a.clave === 'sello') || b.desbloquea.length - a.desbloquea.length || a.clave.localeCompare(b.clave));
  const otras = L.bloqueadas.filter((f) => f.desbloquea.length === 0);
  return { criticas, otras };
}

/** Frase de cabecera del panel: lo que se puede y no se puede hacer hoy. */
export function resumenDesbloqueo(L) {
  if (!L) return null;
  const ok = L.operaciones.filter((o) => o.ok);
  const bloqueadas = L.operaciones.filter((o) => !o.ok);
  const gastar = L.operaciones.find((o) => o.id === 'gastar');
  return {
    puedeGastar: Boolean(gastar && gastar.ok),
    habilitadas: ok.map((o) => o.titulo), bloqueadas: bloqueadas.map((o) => o.titulo),
    faltanParaGastar: gastar ? gastar.faltantes.length : null, sinSello: !L.sellado,
  };
}

export function comandosParametros() {
  return {
    estado: '.venv/bin/python -m engine.limites estado --operacion gastar',
    validar: '.venv/bin/python -m scripts.validar_esquemas limites empresa/limites.yaml --operacion gastar',
  };
}
