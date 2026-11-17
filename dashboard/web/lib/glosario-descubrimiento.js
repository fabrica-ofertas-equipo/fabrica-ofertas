// lib/glosario-descubrimiento.js — términos de dominio de Descubrimiento, Landing y Campañas (U3).
// Fragmento del glosario: `lib/glosario-indice.js` lo importa de forma tolerante (si falta, se ignora). Texto fijo del producto (no viene de datos).
// En conflicto de claves manda `glosario.js` (traccion, exportador, puertas, transferibilidad, freno_captura, preflight, hash_config, gate_h…: no se repiten aquí).
// Forma: { clave: { nombre?, corto, largo?, tecnico? } } — `corto` es una frase para el popover; `largo` amplía; `tecnico` es el nombre en el código/archivo.

export const TERMINOS = {
  // ───────── Descubrimiento: el radar de ofertas ─────────
  piso: {
    nombre: 'Cifra «al menos» (piso)',
    corto: 'Una cifra es «al menos» cuando solo se vio una parte: el total real puede ser mayor, nunca menor.',
    largo: 'La Biblioteca de Anuncios entrega como mucho 50 anuncios por consulta. Si una página tiene más, lo visto es un mínimo («≥ 18»). Una cifra «al menos» que ya supera el mínimo exigido es definitiva; si no lo alcanza, la oferta queda «por medir» y nunca se descarta.',
    tecnico: 'anuncios_activos_medidos_es_piso · edad_es_piso',
  },
  medido: {
    nombre: 'Medido (conteo exacto)',
    corto: 'Medido = se consultó la página directamente y se vieron todos sus anuncios: el conteo es exacto.',
    largo: 'Solo la pasada 3 (una consulta por página) mide de verdad. «Completa» es exacto, «parcial» es un «al menos» con total declarado y «solo muestra» es lo que apareció al buscar por frases.',
    tecnico: 'medicion_estado: completa | parcial | muestra',
  },
  pasada: {
    nombre: 'Pasadas del barrido',
    corto: 'El barrido tiene tres pasadas: 1 barre por forma y país, 2 insiste donde la muestra oculta mucho, 3 mide página por página.',
    largo: 'Las tres comparten un máximo de búsquedas por corrida. Solo la pasada 3 produce cifras medidas; las anteriores producen cifras «al menos».',
    tecnico: 'plan consultas.pasada ∈ {1, 2, 3}',
  },
  muestra_truncada: {
    nombre: 'Muestra truncada',
    corto: 'La Biblioteca devuelve como máximo 50 anuncios por consulta: más allá, no se ve.',
    largo: 'Cuando una consulta llega a ese máximo, se marca como truncada y toda cifra que sale de ella es un «al menos».',
    tecnico: 'truncadas · hay_muestra_truncada',
  },
  anunciante_independiente: {
    nombre: 'Anunciantes independientes',
    corto: 'Anunciantes distintos que venden lo mismo, sin contar páginas que parecen del mismo operador.',
    largo: 'Dos páginas con títulos de anuncio idénticos se consideran un posible mismo operador y cuentan una sola vez. Más anunciantes independientes = más prueba de que el tema funciona.',
    tecnico: 'anunciantes_independientes · posible_mismo_operador · grupo_operador',
  },
  edad_oferta: {
    nombre: 'Edad de la oferta',
    corto: 'Días desde el anuncio más antiguo visto de la oferta. Es un «al menos»: puede haber anuncios más viejos que no se vieron.',
    tecnico: 'edad_oferta_dias · edad_es_piso',
  },
  macro_nicho: {
    nombre: 'Categoría general (macro-nicho)',
    corto: 'Etiqueta del gran mercado (salud, relaciones o dinero) según la IA. Es una etiqueta, no un filtro que descarte.',
    largo: 'Las ofertas «fuera de marco» siguen visibles: la etiqueta solo ayuda a ordenar y a decidir si encaja con las categorías en las que trabaja la fábrica.',
    tecnico: 'macro_nicho: salud | relaciones | dinero | mixto | fuera_de_marco',
  },
  hueco_muestra: {
    nombre: 'Hueco en la muestra',
    corto: 'Un hueco es un país donde el tema no apareció en la muestra. Es una hipótesis, no un hecho.',
    largo: 'Que no se vea en un país no prueba que no exista allí: la muestra es limitada. Hay que medirlo con la pasada 3 (una consulta por página y país) antes de apostar por ese hueco.',
    tecnico: 'matriz_tema_pais.estado_ausencia = hipotesis_hasta_pasada_3',
  },
  por_verificar: {
    nombre: 'Por verificar',
    corto: 'Cosas que la IA no pudo confirmar de la página (por ejemplo, si cobra un pago único). Avanza igual, pero hay que mirarlo.',
    largo: 'Mientras se descubre, un «no sé» no descarta la oferta; antes de lanzar, sí la frena. Por eso queda anotado.',
    tecnico: 'por_verificar: modelo_de_cobro | tema | original',
  },
  modelo_de_cobro: {
    nombre: 'Cómo cobra (modelo de cobro)',
    corto: 'Si la oferta cobra un pago único (producto digital) en lugar de suscripción, servicio o producto físico.',
    tecnico: 'es_oferta_digital_pago_unico: true | false | null',
  },
  ficha_borrador: {
    nombre: 'Ficha borrador',
    corto: 'Resumen de una oferta candidata con lo que se sabe y, sobre todo, lo que aún falta evaluar para puntuarla.',
    largo: 'Las puertas, la transferibilidad, el puntaje del rival y los reencuadres empiezan vacíos (sin evaluar) hasta que los juzga la sesión de descubrimiento. «Sin evaluar» no significa «no».',
    tecnico: 'candidatos/<corrida>/fichas_borrador.json · formato 2.0.0',
  },
  cupo_consultas: {
    nombre: 'Máximo de búsquedas',
    corto: 'Cada corrida puede hacer un número máximo de búsquedas en la Biblioteca; las tres pasadas comparten ese máximo.',
    tecnico: 'consultas_tope · tope_consultas',
  },
  memoria_barrido: {
    nombre: 'Comparación entre corridas',
    corto: 'Una foto guardada de cada corrida sirve para medir novedades (anunciantes nuevos y temas nuevos) en la siguiente.',
    largo: 'Necesita una corrida anterior de entre 25 y 60 días de antigüedad. Sin ella, los anunciantes nuevos quedan «sin dato», nunca en cero.',
    tecnico: 'memoria/<corrida>.json · entrantes_30d',
  },
  entrantes_30d: {
    nombre: 'Anunciantes nuevos en 30 días (entrantes)',
    corto: 'Anunciantes nuevos del tema en los últimos 30 días, comparados con la foto anterior. Sin foto anterior es «sin dato».',
    tecnico: 'entrantes_30d (null = sin foto anterior para comparar)',
  },
  fuera_de_marco: {
    nombre: 'Fuera de marco',
    corto: 'Oferta que no encaja en salud, relaciones ni dinero, las categorías en las que trabaja la fábrica. Sigue visible.',
    largo: 'La IA le pone a cada página una categoría general. «Fuera de marco» significa que no es de ninguna de las tres. No se descarta: solo se marca para que lo tengas en cuenta.',
    tecnico: 'macro_nicho: fuera_de_marco',
  },
  rutas_captura: {
    nombre: 'Rutas de captura (A y D)',
    corto: 'Hay dos formas de traer anuncios: la ruta A usa la herramienta de consulta de Meta; la ruta D abre Chrome. El freno solo detiene la D.',
    largo: 'La ruta A consulta la Biblioteca de Anuncios con una herramienta autorizada y no se ve afectada por el freno de captura. La ruta D abre el navegador Chrome y sí se detiene cuando el freno está puesto.',
    tecnico: 'ruta A (conector ads_library_search) · ruta D (captura.py)',
  },
  puntaje_rival: {
    nombre: 'Puntaje del rival',
    corto: 'Una nota de 0 a 100 de qué tan fuerte es la oferta rival que ya se anuncia en ese mercado.',
    largo: 'Es obligatoria cuando hay uno o dos rivales sostenidos en el mercado. Mientras nadie la audita queda «sin auditar», y la ficha sigue incompleta.',
    tecnico: 'hueco.puntaje_rival',
  },
  ventana_mercado: {
    nombre: 'Ventana del mercado',
    corto: 'Qué tan oportuno es entrar ahora a ese mercado: siempre vigente (evergreen), abierta, cierra pronto o vencida.',
    largo: '«Evergreen» significa que no tiene fecha: sirve en cualquier momento. Si todos los mercados dicen «evergreen» es un valor de relleno y la ventana no está realmente evaluada.',
    tecnico: 'ventana: evergreen | abierta | cierra_pronto | vencida',
  },
  lotes_clasificacion: {
    nombre: 'Lotes de clasificación',
    corto: 'La IA clasifica las páginas en grupos (lotes). Un lote queda «validado» cuando su respuesta cumple el formato esperado.',
    largo: 'Cada lote es una tanda de páginas que una IA clasifica por tema, público y señales de riesgo. Si un lote no responde o responde mal, sus páginas quedan sin clasificar.',
    tecnico: 'etiquetas · lotes_validados · lotes_sin_salida · lotes_salida_invalida',
  },

  // ───────── Landing (D5) ─────────
  checks_c: {
    nombre: 'Comprobaciones de calidad C01–C17',
    corto: 'Las 17 revisiones de calidad de la página de venta: sitio sin errores, precios coherentes, cumplimiento, compra, entrega y medición.',
    largo: 'Las hace el revisor de calidad con programas de comprobación; este panel solo muestra el resultado. «Sin resultado» significa que nadie lo registró, y nunca se cuenta como correcto.',
    tecnico: 'C01–C17 · qa/d5-v<n>.json · checks_l1 · hallazgos',
  },
  coherencia_c02: {
    nombre: 'Coherencia de precio y garantía',
    corto: 'El precio, la moneda, la garantía y la oferta extra al pagar deben ser idénticos en la oferta, la pantalla de pago y la página de venta.',
    largo: 'El dinero se compara en la unidad más chica de la moneda (centavos), con números enteros y sin decimales. Si solo hay una fuente no hay con qué comparar: queda «sin dato suficiente».',
    tecnico: 'C02 · landing.validar L1-PRECIO, L1-MONEDA, L1-GARANTIA',
  },
  legales_d5: {
    nombre: 'Páginas legales',
    corto: 'Siete páginas legales obligatorias: vendedor, términos, privacidad, reembolsos, cookies, aviso legal y entrega.',
    largo: 'Son plantillas generadas, sin revisión de un abogado (decisión del dueño). El panel solo comprueba que existan y respondan.',
    tecnico: 'rutas.json → /legal/<nombre>',
  },
  ranura_asset: {
    nombre: 'Ranuras de imagen',
    corto: 'Cada imagen de la página de venta ocupa un hueco declarado de antemano; ninguna imagen puede ir sin que su ranura esté aprobada.',
    largo: 'Una ranura describe qué imagen va (sección, proporción, peso máximo). Mientras no esté aprobada, la imagen no puede mostrarse en la tienda real.',
    tecnico: 'assets.json → slots[].estado: vacio | asignado | aprobado',
  },
  consentimiento: {
    nombre: 'Consentimiento previo',
    corto: 'Nada se envía a Meta antes de que la persona acepte el aviso de cookies (obligatorio en la Unión Europea y el Reino Unido).',
    largo: 'Mientras la persona no acepta, el sitio no manda a Meta ninguna visita ni compra. Las casillas de aceptación van separadas y nunca vienen marcadas de antemano.',
    tecnico: 'tracking.json → consent_gating · banner_propio_v1',
  },
  event_id: {
    nombre: 'Identificador de evento',
    corto: 'Un código común para cada visita o compra, que viaja por el navegador y por el servidor para que Meta no la cuente dos veces.',
    largo: 'Si Meta recibe el mismo evento por dos caminos con el mismo código, lo cuenta una sola vez. Sin ese código habría ventas duplicadas en las cifras.',
    tecnico: 'event_id · event_id_regla · C09',
  },
  price_live: {
    nombre: 'Precio real en Stripe',
    corto: 'El precio «real» de Stripe se crea al publicar (con tu firma); antes solo existe el precio de prueba, que no cobra.',
    largo: 'Stripe guarda un precio de prueba y otro real. El real solo se crea al publicar la tienda, y por eso aparece como «pendiente» hasta ese momento.',
    tecnico: 'checkout.json → price_ids.test | live',
  },

  // ───────── Campañas (D7) ─────────
  ciclo_campana: {
    nombre: 'Ciclo de la campaña',
    corto: 'La campaña pasa por cuatro estados: borrador, chequeo OK, aprobada y activa. Cada salto lo decide una persona o un chequeo, nunca el panel.',
    largo: 'Borrador: armada pero sin revisar. Chequeo OK: la revisión previa está en verde. Aprobada: tiene tu firma. Activa: está emitiendo anuncios y gastando. «Pausada» y «cerrada» son estados aparte.',
    tecnico: 'campana.estado: borrador | preflight_ok | aprobada | activa (pausada | cerrada aparte)',
  },
  spend_cap: {
    nombre: 'Tope de gasto',
    corto: 'El gasto total máximo que Meta le permite a la campaña. Si no hay, hace falta un freno alternativo (fecha de fin + presupuesto total).',
    largo: 'Meta corta la campaña cuando llega a este tope. Si el tope está vacío, la campaña debe llevar otro freno: una fecha de fin y un presupuesto total, para que nunca gaste sin límite.',
    tecnico: 'presupuesto.spend_cap · candado_alternativo',
  },
  macros_url: {
    nombre: 'Marcadores de la dirección del anuncio',
    corto: 'Huecos que Meta rellena al mostrar cada anuncio (nombres y códigos de campaña, conjunto y anuncio). Unen cada compra con su anuncio.',
    largo: 'La dirección del anuncio lleva marcadores como {{ad.id}}. Meta los reemplaza por los datos reales de cada anuncio, y así sabemos de qué anuncio vino cada compra. (Se llaman «macros».)',
    tecnico: 'macros · {{campaign.name}} {{adset.name}} {{ad.name}} {{campaign.id}} {{adset.id}} {{ad.id}}',
  },
  ids_meta: {
    nombre: 'Códigos de Meta del borrador',
    corto: 'Los códigos que Meta asignó al borrador (campaña, conjuntos, anuncios y piezas). Todo se crea en pausa.',
    largo: 'Cuando se crea el borrador en Meta, cada objeto recibe un código. Esta lista es lo que se encendería al activar, y por eso lo que firmas tiene que coincidir con ella.',
    tecnico: 'ids_meta.json',
  },
  reglas_parada: {
    nombre: 'Reglas de parada',
    corto: 'Condiciones que pausan la campaña solas: por ejemplo, gastar varias veces el costo de equilibrio sin una venta.',
    largo: 'Son reglas fijas que se firmaron junto con la campaña. Si se cumplen, la campaña se corta sin esperar a nadie, para no seguir gastando en algo que no vende.',
    tecnico: 'reglas_parada · k_corte · pausa_global_si',
  },
  special_ad_categories: {
    nombre: 'Categorías especiales de anuncios',
    corto: 'Categorías reguladas por Meta (como crédito o empleo). Si hay alguna, el chequeo antes de lanzar exige el visto bueno de cumplimiento.',
    largo: 'Son temas con reglas más estrictas de publicidad. Si la campaña declara alguna, hace falta el visto bueno firmado de cumplimiento para poder activarla.',
    tecnico: 'special_ad_categories → P25',
  },

  // ───────── Landing y Campañas: términos que usan las pantallas ─────────
  landing_pagina: {
    nombre: 'Página de venta',
    corto: 'La página a la que llega quien hace clic en el anuncio: presenta la oferta y lleva al pago.',
    largo: 'Es la página de venta de una oferta. La arma la etapa «Página de venta y pago» como un sitio estático local; este panel solo la muestra y revisa, no la publica.',
    tecnico: 'landing · ofertas/<id>/05-landing/',
  },
  oferta_extra_pago: {
    nombre: 'Oferta extra al pagar',
    corto: 'Una casilla para sumar un producto más en el mismo pago. Nunca viene marcada de antemano.',
    largo: 'Quien compra puede agregar este producto con un clic, sin pasar por otro pago. Por regla, la casilla jamás viene premarcada: tiene que marcarla la persona.',
    tecnico: 'bump · order bump',
  },
  oferta_post_pago: {
    nombre: 'Oferta después de pagar',
    corto: 'Una propuesta de otro producto que se muestra justo después de completar el pago.',
    largo: 'En la primera versión de las ofertas no se usa: el campo aparece como «ninguno».',
    tecnico: 'upsell',
  },
  etiqueta_utm: {
    nombre: 'Etiqueta del anuncio (UTM)',
    corto: 'Datos que lleva la dirección del anuncio para decir de qué campaña, conjunto y anuncio vino cada visita y cada venta.',
    largo: 'La pantalla de pago debe guardar estas etiquetas junto con la compra; si falta alguna, no se sabría de qué anuncio salió esa venta.',
    tecnico: 'UTM · utm_esquema · metadata del checkout',
  },
  medidor_meta: {
    nombre: 'Medidor de Meta (píxel y dataset)',
    corto: 'Avisa a Meta cuando alguien visita o compra, para que sus anuncios aprendan a quién mostrarse.',
    largo: 'El píxel manda los avisos desde el navegador y el dataset es el lugar de Meta donde se guardan. En modo prueba los avisos no llegan al dataset real.',
    tecnico: 'pixel_id · dataset_id',
  },
  emq_calidad: {
    nombre: 'Calidad de coincidencia (EMQ)',
    corto: 'Una nota de Meta que dice qué tan bien puede reconocer a la persona de cada evento. Más alta es mejor.',
    largo: 'Meta puntúa de 0 a 10 cuánto puede unir un evento con una persona real. La campaña exige llegar a un objetivo mínimo antes de activarse.',
    tecnico: 'EMQ · Event Match Quality · emq_objetivo',
  },
  confirmacion_pago: {
    nombre: 'Aviso automático de Stripe (webhook)',
    corto: 'Stripe avisa solo a la tienda cuando un pago se completa; con ese aviso se entrega el producto.',
    largo: 'Es el único momento en que se confirma una venta. Debe contar un pago una sola vez, rechazar avisos falsos y no entregar si el pago no se cobró.',
    tecnico: 'webhook de Stripe · C07',
  },
  afirmaciones_claims: {
    nombre: 'Afirmaciones (claims)',
    corto: 'Las promesas concretas que hace un anuncio (por ejemplo un resultado o una cifra). Cada una tiene que estar respaldada.',
    largo: 'Cada anuncio declara qué afirmaciones usa. Si un texto dice algo que no está en la lista aprobada, la revisión lo marca.',
    tecnico: 'claim_ids · lint_claims',
  },
  candado_alternativo: {
    nombre: 'Freno alternativo de gasto',
    corto: 'Cuando no hay tope de gasto, la campaña necesita otro freno: una fecha de fin y un presupuesto total.',
    largo: 'Garantiza que, aunque el tope de la cuenta quede vacío, Meta no pueda gastar sin límite en esta campaña.',
    tecnico: 'candado_alternativo (stop_time + lifetime_budget)',
  },
  precio_stripe: {
    nombre: 'Precio en Stripe',
    corto: 'Cada producto tiene un precio creado en Stripe, el servicio que cobra. Hay uno de prueba y uno real.',
    largo: 'La pantalla de pago usa estos precios de Stripe. El de prueba permite ensayar sin cobrar; el real se crea al publicar.',
    tecnico: 'Price de Stripe · price_ids',
  },
  aprobacion_firma: {
    nombre: 'Aprobación firmada',
    corto: 'La orden de activar la campaña, firmada por ti con una firma digital personal que ningún agente de IA tiene.',
    largo: 'Una aprobación escrita a mano no vale. La firma se hace en tu terminal con tu clave, y la verifica el sistema antes de activar. El panel solo muestra si existe.',
    tecnico: 'aprobacion.json · firma Ed25519 · gate H',
  },
  dictamen_cumplimiento: {
    nombre: 'Informe de cumplimiento',
    corto: 'La opinión del revisor de cumplimiento (X1) sobre si la página de venta o la campaña respetan las reglas de Meta y de pagos.',
    largo: 'Sin un informe aprobado y firmado no se publica nada. Revisa lo que se promete, el contenido, el encuadre y el modelo de negocio.',
    tecnico: 'X1 · qa/x1-d5-v<n>.json',
  },
  costo_equilibrio_k: {
    nombre: 'Corte por gasto sin ventas',
    corto: 'La campaña se corta si gasta k veces el costo de equilibrio sin conseguir ninguna venta.',
    largo: 'Por ejemplo, con k = 3 y un costo de equilibrio de 10, la campaña se detiene al gastar 30 sin vender. Ver también la regla K.',
    tecnico: 'k_corte · reglas_parada',
  },
  campana_cbo: {
    nombre: 'Campaña con presupuesto compartido (CBO)',
    corto: 'Una sola bolsa de presupuesto para toda la campaña: Meta reparte el dinero entre los anuncios según cuál rinde mejor.',
    largo: 'En vez de fijar cuánto gasta cada conjunto de anuncios, se fija un presupuesto para toda la campaña y Meta lo mueve solo hacia lo que más vende. (CBO = Campaign Budget Optimization.)',
    tecnico: 'CBO · estructura: CBO',
  },
};

export default TERMINOS;
