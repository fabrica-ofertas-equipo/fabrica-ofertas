// glosario.js — términos de dominio con definición en lenguaje de negocio. Datos puros (sin DOM, sin dependencias).
//
// GLOSARIO = { clave: { nombre?, corto, largo, tecnico? } }
//   nombre   nombre humano que se muestra en pantalla (lo que ve el dueño). Si falta, ui.termino usa `texto` o la clave humanizada.
//   corto    una o dos frases (≤ 200 caracteres): qué es, en palabras de todos los días. Es lo primero que se lee en el popover.
//   largo    2-4 frases: para qué sirve, cuándo importa, qué hacer.
//   tecnico  el nombre técnico / campo / siglas tal cual aparecen en archivos y comandos («gate H», `hash_config`). Va pequeño al pie.
// Reglas de redacción: dashboard/GUIA_DE_LENGUAJE.md (primero qué es y qué hacer; sin siglas en el texto principal; lo técnico, en `tecnico`).
// Las claves son snake_case ASCII, sin tildes. Cada página puede aportar las suyas en `lib/glosario-<pagina>.js` (`export const TERMINOS = {…}`);
// `lib/glosario-indice.js` las junta con tolerancia (las que falten se ignoran). En conflicto manda este archivo.

export const GLOSARIO = {
  // ───────── puntos de control y niveles ─────────
  gate: {
    nombre: 'Punto de control',
    corto: 'Un paso donde el sistema se frena y espera una aprobación antes de seguir.',
    largo: 'Cada etapa termina en un punto de control. Según el nivel de autonomía, lo aprueba una regla automática, una revisión parcial o tú. Con el dinero, la publicación y el cumplimiento siempre hay topes, aunque el control sea automático.',
    tecnico: 'gate',
  },
  gate_a: {
    nombre: 'Control automático',
    corto: 'Se aprueba solo cuando el sistema comprueba que se cumplen las reglas; no hace falta que intervenga nadie.',
    largo: 'El sistema revisa condiciones que se pueden medir (formato correcto, topes, pruebas aprobadas) y avanza. Si algo falla, se detiene y te avisa.',
    tecnico: 'gate A',
  },
  gate_s: {
    nombre: 'Control semiautomático',
    corto: 'Lo propone el sistema y solo te llega a ti si hay una excepción: una nota del revisor, un fallo o una muestra al azar.',
    largo: 'Es el punto intermedio. La etapa avanza sola cuando todo está limpio y se frena para que la mires cuando el revisor deja notas, hay un fallo o toca revisar una muestra al azar.',
    tecnico: 'gate S',
  },
  gate_h: {
    nombre: 'Espera tu firma',
    corto: 'Un paso que solo puedes aprobar tú: el sistema se frena hasta que lo firmes.',
    largo: 'Elegir la idea, aprobar la oferta, activar una campaña o subir el presupuesto son decisiones tuyas. El panel te muestra qué revisar y el comando para firmar, pero no firma por ti.',
    tecnico: 'gate H',
  },
  autonomia: {
    nombre: 'Nivel de autonomía',
    corto: 'Cuánto hace el sistema solo en cada etapa: del nivel 0 (todo lo apruebas tú) al nivel 4 (casi todo lo hace solo).',
    largo: 'El nivel se da etapa por etapa y baja solo si hay un error grave o un problema de gasto. El sistema recomienda subir de nivel, pero lo firmas tú.',
    tecnico: 'empresa/autonomia.yaml',
  },
  nivel_n0: { nombre: 'Nivel 0 · Todo lo apruebas tú', corto: 'Haces el paso a mano con ayuda del asistente; nada avanza sin tu firma.', largo: 'Es el punto de partida de cada etapa: el método se aprende a mano y de ahí sale la guía de trabajo que después sigue la IA.', tecnico: 'N0' },
  nivel_n1: { nombre: 'Nivel 1 · Una IA prepara, tú revisas todo', corto: 'Una IA prepara el trabajo siguiendo su guía de trabajo y tú revisas y firmas cada paso.', largo: 'La guía de la etapa ya está terminada y con sus pruebas aprobadas. Sigues firmando todo.', tecnico: 'N1' },
  nivel_n2: { nombre: 'Nivel 2 · Otra IA revisa, tú firmas lo importante', corto: 'Una IA prepara y otra revisa; tú firmas solo los puntos críticos: oferta, página de venta, campaña y presupuesto.', largo: 'Una segunda IA revisa el trabajo de la primera sin saber cómo lo hizo. Las decisiones de dinero y de publicación siguen siendo tuyas.', tecnico: 'N2' },
  nivel_n3: { nombre: 'Nivel 3 · Solo te consulta si hay una excepción', corto: 'El sistema avanza solo, con topes de dinero que no puede pasar, y te consulta únicamente cuando surge una excepción.', largo: 'Pide varias ofertas completas, ningún problema de gasto y un simulacro de freno aprobado.', tecnico: 'N3' },
  nivel_n4: { nombre: 'Nivel 4 · Casi todo lo hace solo', corto: 'Lanzas una oferta nueva con un botón, con un tope por día y una revisión semanal tuya.', largo: 'Tú fijas los límites y revisas una vez por semana; el sistema maneja la fila de trabajo, los frenos y los reintentos.', tecnico: 'N4' },
  maker_qa: {
    nombre: 'Quien prepara y quien revisa',
    corto: 'Una IA prepara el trabajo y otra, independiente, lo revisa. Ninguna aprueba lo suyo.',
    largo: 'El revisor solo lee: no corrige ni mejora lo que revisa. Devuelve un informe con el resultado y los defectos; quien prepara el trabajo lo rehace, y así hasta llegar al máximo de rondas.',
    tecnico: '<etapa>-maker / <etapa>-qa',
  },
  ronda_qa: {
    nombre: 'Ronda de revisión',
    corto: 'Cada vez que el revisor mira y quien prepara el trabajo lo rehace, cuenta como una ronda. Hay un máximo antes de pasarte la decisión.',
    largo: 'Si después de las rondas permitidas siguen los defectos graves, la etapa pasa a tu decisión en vez de repetirse sin fin.',
    tecnico: 'ronda_qa',
  },
  defectos_sembrados: {
    nombre: 'Errores puestos a propósito',
    corto: 'Errores que se ponen a propósito en una prueba para comprobar que el revisor los encuentra.',
    largo: 'Si el revisor deja pasar uno, no está bien ajustado: la etapa no sube de nivel de autonomía hasta corregirlo.',
    tecnico: 'canarios / sembrados',
  },
  dod: {
    nombre: 'Criterios para darla por terminada',
    corto: 'La lista de condiciones que debe cumplir una guía de trabajo para considerarse terminada.',
    largo: 'Cada guía tiene su lista (formato correcto, pruebas aprobadas, ejemplos revisados). Cuando cumple todo, pasa de borrador a v1.',
    tecnico: 'DoD',
  },
  skill_v01: { nombre: 'Guía de trabajo en borrador', corto: 'Una guía recién armada: funciona, pero todavía no cumplió todos los criterios para darla por terminada.', largo: 'Úsala con revisión humana completa. Queda marcada como «v0.1 sin pulir» hasta que cumple todos los criterios.', tecnico: 'skill v0.1' },
  skill_v1: { nombre: 'Guía de trabajo terminada', corto: 'Una guía terminada: cumplió sus criterios y sus pruebas.', largo: 'Puede subir de nivel de autonomía según las medidas de confianza de la etapa.', tecnico: 'skill v1' },

  // ───────── etapas ─────────
  etapa_d1: { nombre: 'Descubrir', corto: 'Buscar ideas de oferta, con pruebas a la vista, para que elijas una.', tecnico: 'D1' },
  etapa_m1: { nombre: 'Mercado', corto: 'Decidir el idioma, los países, la moneda y los medios de pago donde se prueba la oferta.', tecnico: 'M1' },
  etapa_d2: { nombre: 'Validar', corto: 'Comprobar con pruebas que la idea tiene mercado: competidores, voz del cliente y huecos libres.', tecnico: 'D2' },
  etapa_d3: { nombre: 'Oferta', corto: 'Diseñar la oferta: nombre, promesa, bonus, garantía, precio local y cuentas por país.', tecnico: 'D3' },
  etapa_d4: { nombre: 'Producto', corto: 'Fabricar el producto digital que se entrega, revisado y en el idioma de la oferta.', tecnico: 'D4' },
  etapa_d5: { nombre: 'Página de venta y pago', corto: 'Armar la página de venta, la pantalla de pago y la medición de las ventas.', tecnico: 'D5' },
  etapa_d6: { nombre: 'Anuncios', corto: 'Producir los anuncios (guiones, textos, imágenes y videos) para Meta.', tecnico: 'D6' },
  etapa_d7: { nombre: 'Campaña', corto: 'Armar la campaña de prueba en Meta, con su chequeo antes de lanzar y su plan de vigilancia.', tecnico: 'D7' },
  etapa_d8: { nombre: 'Operación', corto: 'Mirar los números todos los días y proponer qué pausar, mantener o escalar.', tecnico: 'D8' },
  etapa_d9: { nombre: 'Optimización', corto: 'Ajustar anuncios, públicos y presupuesto según lo que muestran los datos.', tecnico: 'D9' },
  etapa_d10: { nombre: 'Después de la venta', corto: 'Entrega del producto al comprador, soporte y reembolsos.', tecnico: 'D10' },
  etapa_x1: { nombre: 'Cumplimiento', corto: 'Revisión de las políticas de Meta y de Stripe sobre cada promesa y cada pieza.', tecnico: 'X1' },
  oferta: {
    nombre: 'Oferta',
    corto: 'Un producto en un idioma o en un grupo de países concretos: es la unidad que se prueba y se escala.',
    largo: 'Una misma idea puede dar varias ofertas (una por idioma o mercado). Cada oferta tiene su carpeta, su estado, sus cuentas y su pausa.',
    tecnico: 'oferta_id · ofertas/<id>/',
  },
  demo: {
    nombre: 'Datos de demostración',
    corto: 'Una oferta de ejemplo para ver todas las pantallas con datos; no es dinero ni información real.',
    tecnico: 'ofertas/_ejemplo',
  },

  // ───────── campaña y chequeo antes de lanzar ─────────
  preflight: {
    nombre: 'Chequeo antes de lanzar',
    corto: 'La lista de comprobaciones que una campaña debe pasar antes de poder activarse.',
    largo: 'Revisa que el cumplimiento esté firmado, que se respeten los topes de gasto, que la medición de ventas funcione y que la configuración no haya cambiado desde la firma. Si algo falla, la campaña no se activa.',
    tecnico: 'preflight',
  },
  preflight_ok: {
    nombre: 'Lista para activar',
    corto: 'El chequeo salió bien: solo falta tu firma para activar la campaña.',
    tecnico: 'preflight_ok',
  },
  borrador: { nombre: 'Borrador', corto: 'La campaña está escrita, pero todavía no pasó el chequeo antes de lanzar.', tecnico: 'borrador' },
  aprobada: { nombre: 'Aprobada', corto: 'Tú firmaste la campaña; todavía no muestra anuncios.', tecnico: 'aprobada' },
  activa: { nombre: 'Activa', corto: 'La campaña está mostrando anuncios y gastando dinero real.', largo: 'Solo una persona puede activarla. Si está puesta la pausa general o el freno de captura, el sistema no la reactiva.', tecnico: 'activa' },
  hash_config: {
    nombre: 'Huella de la configuración',
    corto: 'Una marca única de la configuración que firmaste: si cambia algo, la huella cambia.',
    largo: 'Sirve para asegurar que lo que se activa es lo mismo que revisaste. Si la huella de la campaña no coincide con la firmada, el chequeo antes de lanzar falla.',
    tecnico: 'hash_config (sha256)',
  },
  sello_x1: {
    nombre: 'Visto bueno de cumplimiento',
    corto: 'La aprobación firmada de cumplimiento. La emite el sistema (no una IA) cuando la revisión sale bien.',
    largo: 'Una revisión sin esa firma no vale. La emite el sistema con una clave que ninguna IA tiene, y deja de valer si cambia el contenido que se revisó.',
    tecnico: 'sello · compliance.sellar · X1',
  },

  // ───────── frenos y pausa ─────────
  pausa: {
    nombre: 'Pausa general',
    corto: 'Un archivo que frena al sistema: mientras exista, no gasta, no activa nada ni sube presupuestos.',
    largo: 'El panel puede crearla («Pausar todo») pero nunca borrarla: reanudar es siempre una decisión tuya, a mano.',
    tecnico: 'empresa/PAUSA',
  },
  freno_captura: {
    nombre: 'Freno de la captura de anuncios',
    corto: 'Detiene la recolección de anuncios y foros cuando una fuente bloquea la visita o cambia sus condiciones.',
    largo: 'Se activa solo ante un bloqueo, un captcha o un aviso de la plataforma. Solo una persona lo levanta, después de revisar la fuente.',
    tecnico: 'empresa/captura/freno.json',
  },
  kill_switch: {
    nombre: 'Interruptor de emergencia',
    corto: 'Una pausa automática cuando el gasto se descontrola, hay compras sin registrar o los reembolsos pasan el límite.',
    tecnico: 'kill switch',
  },
  tope: { nombre: 'Tope de gasto', corto: 'Lo máximo que el sistema puede gastar (por día, por oferta o en total). Es un límite firme, no una sugerencia.', tecnico: 'limites.yaml' },
  limites: {
    nombre: 'Límites del dueño',
    corto: 'Los topes de dinero que solo puedes fijar tú. Mientras no tengan valor, el sistema no gasta.',
    tecnico: 'empresa/limites.yaml',
  },

  // ───────── descubrimiento y modelado ─────────
  traccion: {
    nombre: 'Tracción',
    corto: 'Señal de que una oferta ajena funciona: al menos 15 anuncios activos y 10 días de vida de la oferta.',
    largo: 'Prueba que la oferta se sostiene, no que sea rentable: tener muchos anuncios no prueba que venda. Por eso es solo un factor más del puntaje.',
    tecnico: '≥ 15 anuncios · ≥ 10 días',
  },
  pm: {
    nombre: 'Puntaje de modelado',
    corto: 'Una nota de 0 a 100 que dice cuánto conviene copiar una oferta ajena: puertas, tracción, hueco, transferibilidad y diferenciación.',
    largo: 'La calcula una fórmula fija (no la decide una IA): puertas × tracción × hueco × transferibilidad × diferenciación. La oferta pasa si llega al mínimo vigente.',
    tecnico: 'PM = G·T^wT·H^wH·X^wX·D^wD·100',
  },
  pm_incompleto: {
    nombre: 'Ficha incompleta',
    corto: 'Faltan datos que solo se ven mirando el anuncio, así que el puntaje todavía no es definitivo.',
    largo: 'Lo que no se vio queda vacío a propósito: no se adivina. El «piso» cuenta lo que falta como cero y el «techo», como el máximo posible.',
    tecnico: 'PM incompleto',
  },
  piso_techo: {
    nombre: 'Piso y techo',
    corto: 'Con la ficha incompleta, el piso es lo mínimo que valdría y el techo, lo máximo posible.',
    largo: 'Si hasta el techo queda por debajo del mínimo, la ficha se descarta sin más trabajo; si el piso ya lo supera, solo faltan confirmaciones.',
    tecnico: 'piso / techo',
  },
  piso_medido: {
    nombre: 'Piso frente a medido',
    corto: 'Piso: cifra mínima estimada con lo que se ve. Medido: dato contado de verdad en la fuente.',
    largo: 'Un piso nunca se presenta como si fuera una medición: el panel los distingue siempre para no inflar cifras.',
    tecnico: 'piso vs medido',
  },
  indeterminado_muestra: {
    nombre: 'Sin datos suficientes',
    corto: 'Todavía no hay datos suficientes para afirmar nada; no es «bien» ni «mal».',
    largo: 'Decidir con pocos datos produce falsos ganadores. El sistema espera a tener la cantidad mínima antes de dar un veredicto.',
    tecnico: 'INDETERMINADO',
  },
  puertas: {
    nombre: 'Puertas',
    corto: 'Vetos que descartan una oferta como modelo: marca personal, sustituto gratis o práctica prohibida.',
    largo: 'Si cualquier puerta está abierta, el puntaje es 0; si no se pudo comprobar, la ficha queda incompleta.',
    tecnico: 'G · puertas',
  },
  transferibilidad: {
    nombre: 'Transferibilidad',
    corto: 'Qué tan bien se lleva una oferta a otro idioma o país: dolor universal, precio viable y poco riesgo de políticas.',
    tecnico: 'X · transferibilidad',
  },
  exportador: {
    nombre: 'Exportador',
    corto: 'Anunciante que vende la misma oferta en varios países; es señal de que el modelo se puede llevar a otros lados.',
    tecnico: 'exportadores',
  },
  hueco: { nombre: 'Hueco de mercado', corto: 'Si en el país de destino la oferta original no existe o tiene pocos rivales sostenidos, hay lugar para entrar.', tecnico: 'H · hueco' },
  diferenciacion: { nombre: 'Diferenciación', corto: 'Cuántas formas distintas hay de replantear la oferta para no ser un clon.', tecnico: 'D · reencuadres M1-M10' },
  anuncios_sostenidos: { nombre: 'Anuncios sostenidos', corto: 'Anuncios que siguen activos durante semanas: indican que a su anunciante le sigue conviniendo.', tecnico: 'ad_snapshot / sostenidos' },
  candidato: { nombre: 'Candidato', corto: 'Una idea de oferta con su evidencia, su riesgo y lo que la mataría; tú eliges cuál sigue.', tecnico: 'candidatos.json' },
  riesgo_pcen: {
    nombre: 'Riesgo por promesa, contenido, encuadre y negocio',
    corto: 'El riesgo de políticas se mide por lo que se promete y cómo se dice, nunca por el tema (salud, relaciones o dinero).',
    tecnico: 'riesgo{P,C,E,N}',
  },
  mecanismo_unico: { nombre: 'Mecanismo único', corto: 'La razón concreta por la que esta oferta logra el resultado, distinta de la de la competencia.', tecnico: 'MU' },
  entregable_unico: { nombre: 'Entregable único', corto: 'Lo que recibe el comprador y que no encuentra igual en otro lado.', tecnico: 'EU' },

  // ───────── veredictos y cuentas ─────────
  veredicto: {
    nombre: 'Veredicto',
    corto: 'La conclusión de una prueba: validada, prometedora, fallida o inconclusa.',
    largo: 'Lo calcula el sistema con la muestra y las cuentas de la oferta; la IA solo lo explica. «Inconclusa» significa que faltan datos, no que haya fallado.',
    tecnico: 'VALIDADA · PROMETEDORA · FALLIDA · INCONCLUSA',
  },
  validada: { nombre: 'Validada', corto: 'La oferta cumplió el objetivo de rentabilidad con suficientes datos: puede escalar.', tecnico: 'VALIDADA' },
  prometedora: { nombre: 'Prometedora', corto: 'Va por buen camino, pero todavía no llega a la cantidad de datos o al margen que se exige.', tecnico: 'PROMETEDORA' },
  fallida: { nombre: 'Fallida', corto: 'No alcanzó el objetivo con la cantidad mínima de datos: se pausa y se aprende de ella.', tecnico: 'FALLIDA' },
  inconclusa: { nombre: 'Inconclusa', corto: 'Todavía no hay datos para decidir: hay que seguir midiendo o ajustar la prueba.', tecnico: 'INCONCLUSA' },
  factibilidad: {
    nombre: 'Factibilidad',
    corto: 'Si las cuentas de la oferta cierran en un país: factible, ajustada o no factible.',
    largo: 'La calcula el sistema con el precio, los impuestos, las comisiones, el costo del producto y el costo máximo por venta. Ninguna IA la calcula a mano.',
    tecnico: 'FACTIBLE · AJUSTADA · NO_FACTIBLE',
  },
  cpa: { nombre: 'Costo por venta', corto: 'Lo que cuesta, en promedio, conseguir una venta con anuncios.', tecnico: 'CPA' },
  cpa_equilibrio: {
    nombre: 'Punto de equilibrio por venta',
    corto: 'Lo máximo que puedes pagar por una venta sin perder plata: por encima pierdes, por debajo ganas.',
    largo: 'Es el precio menos los impuestos, las comisiones de cobro y el costo del producto.',
    tecnico: 'CPA de equilibrio / CPA_max',
  },
  compras_netas: { nombre: 'Compras netas', corto: 'Las compras confirmadas, menos los reembolsos y las disputas.', tecnico: 'compras netas' },
  ratio_reembolsos: {
    nombre: 'Tasa de reembolsos',
    corto: 'El porcentaje de compras que se devolvieron. Si pasa el límite, la oferta se pausa para revisarla.',
    tecnico: 'ratio_reembolsos',
  },
  conciliacion: {
    nombre: 'Conciliación',
    corto: 'Comparar lo que dicen Meta y Stripe con el libro de movimientos para encontrar diferencias.',
    largo: 'Si la diferencia pasa el límite, salta una alerta: o falta registrar una venta o hay un cobro sin explicar.',
    tecnico: 'conciliacion.json',
  },
  ledger: { nombre: 'Libro de movimientos', corto: 'El registro de cada movimiento de dinero. Solo se le agregan líneas: nunca se borran ni se cambian.', tecnico: 'ledger.jsonl' },
  costo_ia: {
    nombre: 'Costo de IA',
    corto: 'Lo que cuesta el trabajo de los agentes de IA (asistentes de inteligencia artificial): consultas, créditos y herramientas, repartido por oferta.',
    largo: 'Es lo que se gasta en inteligencia artificial para escribir, revisar y generar piezas; no incluye el gasto en anuncios. Se suma por moneda (nunca se mezclan) y se compara con un máximo de porcentaje sobre las ventas. Sin ventas no hay porcentaje: no se inventa un cero.',
    tecnico: 'costos.jsonl · estado.json → costo_ia · parametros.dashboard.costo_ia_max_pct',
  },
  roas: { nombre: 'Retorno por dólar invertido', corto: 'Cuánto se vende por cada dólar (o euro) gastado en anuncios.', tecnico: 'ROAS' },
  cobertura_pago: { nombre: 'Cobertura de pago', corto: 'Qué porcentaje de los compradores del país puede pagar con los medios de pago que ofreces.', tecnico: 'M1 · R6' },

  // ───────── reglas, registro y trazabilidad ─────────
  regla_k: { nombre: 'Regla K', corto: 'Regla de parada por costo: corta una prueba cuando seguir gastando sin resultados ya no se justifica.', tecnico: 'reglas K' },
  regla_g: { nombre: 'Regla G', corto: 'Regla de aprobación: la prueba se da por ganadora cuando cumple los límites exigidos con la cantidad mínima de datos.', tecnico: 'reglas G' },
  regla_m: { nombre: 'Regla M', corto: 'Regla de seguimiento: define cuándo seguir midiendo en lugar de decidir.', tecnico: 'reglas M' },
  registro: {
    nombre: 'Historial de todo lo que pasa',
    corto: 'La bitácora de todo lo que hace el sistema, encadenada para que nadie la pueda alterar sin que se note.',
    tecnico: 'empresa/registro.jsonl',
  },
  cadena_ok: {
    nombre: 'Cadena sin alteraciones',
    corto: 'Cada línea del historial lleva la huella de la anterior: si alguien edita una, la cadena se rompe y se nota.',
    tecnico: 'hash_previo → hash',
  },
  sha256: { nombre: 'Huella (SHA-256)', corto: 'Una marca única del contenido de un archivo: si el archivo cambia, la huella cambia.', tecnico: 'sha256' },
  estado_json: { nombre: 'Estado de la oferta', corto: 'El archivo donde el sistema anota en qué etapa va cada oferta y qué está esperando.', tecnico: 'ofertas/<id>/estado.json' },
  obsoleta: { nombre: 'Etapa desactualizada', corto: 'Una etapa anterior cambió, así que esta quedó vieja y hay que repetirla.', tecnico: 'obsoleta' },
  escalado: { nombre: 'Pasó a tu decisión', corto: 'La etapa no se resolvió sola y quedó en tus manos.', tecnico: 'escalado' },
  bloqueado: { nombre: 'Bloqueado', corto: 'La etapa no puede seguir hasta que se resuelva un problema: un dato que falta, un riesgo alto o un límite sin fijar.', tecnico: 'bloqueado' },
  aprobado: { nombre: 'Aprobado', corto: 'La etapa pasó su control y quedó fija, con su huella.', tecnico: 'aprobado' },
  propuesta_semanal: { nombre: 'Propuesta semanal', corto: 'El resumen semanal que prepara el sistema: dónde está el dinero y qué tienes que decidir.', tecnico: 'empresa/propuestas/' },
  modo_tecnico: {
    nombre: 'Detalle técnico',
    corto: 'Un interruptor que muestra de una vez, en todas las pantallas, las rutas de archivos, las huellas, los comandos y los datos en bruto.',
    largo: 'Apagado, el panel muestra resúmenes y deja el detalle a un clic. Encendido, lo despliega todo para quien quiere verlo completo.',
    tecnico: 'fab.modoTecnico',
  },
};

/** Claves del glosario (orden de declaración). */
export const CLAVES_GLOSARIO = Object.keys(GLOSARIO);
