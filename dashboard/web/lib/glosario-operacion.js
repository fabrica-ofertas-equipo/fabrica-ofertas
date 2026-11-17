// glosario-operacion.js — términos de Operación, Finanzas, Agentes, Cumplimiento y Parámetros y límites (U4). Datos puros: SIN imports
// (lo carga lib/glosario-indice.js de forma tolerante y ui.js importa el índice: un import aquí crearía un ciclo).
// Forma: TERMINOS = { clave_snake_ascii: { nombre, corto (≤ 140), largo?, tecnico? } }. Todo en palabras simples; el nombre técnico va en `tecnico`
// (solo se ve con «Detalle técnico» encendido). En conflicto manda glosario.js (los términos de base: cpa, cpa_equilibrio, compras_netas,
// ratio_reembolsos, conciliacion, ledger, roas, regla_g/k/m, veredicto, limites, tope… NO se repiten aquí).
// Las claves `lim_<clave de limites.yaml>` dan el nombre humano de cada límite del dueño (se usan con ui.termino en Parámetros y límites).

export const TERMINOS = {
  // ───────── Operación: cómo se comporta una oferta en vivo ─────────
  cpa_objetivo: {
    nombre: 'Costo por venta objetivo', corto: 'Lo que quieres pagar en anuncios por cada venta: deja una ganancia sana después de todos los costos.',
    largo: 'Es más exigente que el punto de equilibrio: si el costo por venta queda por debajo del objetivo, cada venta deja una ganancia holgada. Sale de la economía de la oferta, que calculó el sistema al diseñarla. (En los archivos se llama CPA objetivo.)', tecnico: 'CPA objetivo · cpa_obj · 03-oferta/economia.json',
  },
  cobertura_atribucion: {
    nombre: 'Compras ligadas a un anuncio', corto: 'De cada 100 compras de Stripe, cuántas se pueden ligar a un anuncio concreto (a eso se le llama atribución).',
    largo: 'Si el número es bajo, el sistema no sabe qué anuncio vendió y no puede juzgar el rendimiento: por seguridad no pausa ni escala anuncios a ciegas. Se mide con el identificador del anuncio que viaja en el enlace de compra.', tecnico: 'cobertura de atribución · cobertura_adid · cobertura_atrib · G4',
  },
  razon_meta_stripe: {
    nombre: 'Compras de Meta frente a Stripe', corto: 'Las compras que dice Meta dividido entre las compras reales de Stripe. Cerca de 1 es sano.',
    largo: 'Meta suele contar de más o de menos según cómo reparte el mérito de cada venta. Stripe es la fuente de verdad del dinero; Meta solo se usa como referencia de qué anuncio rinde.', tecnico: 'razon_meta_stripe',
  },
  madurez_cohorte: {
    nombre: 'Cuándo cuenta una compra', corto: 'Una compra solo cuenta para el veredicto cuando ya pasó la garantía más un margen de seguridad.',
    largo: 'Si se contara antes, un reembolso posterior cambiaría el resultado. Por eso el veredicto mira solo las compras que ya «maduraron»: las más recientes todavía no pesan.', tecnico: 'cohorte madura · madurez_dias = garantia_dias + margen',
  },
  ventana_no_decidir: {
    nombre: 'Primeros días sin juzgar', corto: 'Los primeros días de un anuncio no se juzga su rendimiento: solo rigen los frenos de seguridad.',
    largo: 'Con pocos datos cualquier decisión sería azar. Durante esos primeros días el sistema solo aplica los frenos de seguridad y la regla de pausar un anuncio que gastó sin ninguna compra.', tecnico: 'ventana de no decidir · M1 · 72 h · guardarraíles (G) · regla K1',
  },
  orden_presupuesto: {
    nombre: 'Orden de presupuesto', corto: 'La única forma de cambiar un presupuesto: un registro que un programa aplica y comprueba en Meta.',
    largo: 'El sistema propone (mantener, subir o bajar), el punto de control correspondiente la aprueba y un programa la ejecuta y vuelve a leer en Meta que quedó bien. Ninguna IA toca el presupuesto directamente. El panel solo las muestra.', tecnico: 'ordenes_presupuesto.jsonl',
  },
  regla_e: {
    nombre: 'Escalar', corto: 'Propuesta de subir el presupuesto de una oferta ganadora; necesita que esté validada y tu firma.',
    largo: 'Escalar es la decisión de más riesgo: el sistema solo la propone cuando hay compras suficientes y una alta probabilidad de que el costo por venta esté por debajo del punto de equilibrio.', tecnico: 'regla E1 · etapa Escalado (D9) · gate H',
  },
  decision_d8: {
    nombre: 'Decisión del sistema', corto: 'Una lectura diaria: qué se hace con cada campaña o anuncio, por qué regla y si ya se aplicó.',
    largo: 'Cada lectura queda anotada con la regla que saltó, la evidencia (gasto, clics, compras) y la acción. «Ejecutada» significa que se aplicó en Meta y se comprobó; el resto son propuestas o no requieren acción.', tecnico: 'Decisión de D8 · decisiones.jsonl · decision.schema.json',
  },
  cifra_tachada: {
    nombre: 'Cifra tachada', corto: 'Un número que no es fiable (su fuente está desactualizada o no cuadra): se muestra tachado con su causa.',
    largo: 'Nunca verás un cero inventado ni un dato viejo sin marca. Si una fuente de datos está en rojo, la cifra se tacha y no se decide con ella hasta que se actualice.', tecnico: 'criterio B0-17',
  },
  frescura_datos: {
    nombre: 'Qué tan nuevos son los datos', corto: 'Hace cuánto se leyó cada fuente: Meta, las compras de Stripe y el saldo de Stripe.',
    largo: 'Verde: al día. Amarillo: empieza a ser viejo. Rojo: demasiado viejo; las cifras que dependen de esa fuente se tachan.', tecnico: 'frescura · parametros.dashboard.frescura_*_h',
  },
  n_bajo: {
    nombre: 'Pocos datos', corto: 'Muestra pequeña: la cifra se muestra, pero no alcanza para sacar una conclusión.',
    largo: 'Con muy pocas compras o clics, un costo por venta bueno o malo puede ser casualidad. El sistema espera a tener la muestra mínima antes de decidir.', tecnico: 'estado «gris» · n bajo',
  },
  veredicto_madurez: {
    nombre: 'Qué falta para validar', corto: 'Los mínimos que deben cumplir las compras ya maduras para que la oferta quede VALIDADA.',
    largo: 'Compras netas mínimas (ya descontados los reembolsos), días con datos mínimos y reembolsos por debajo del máximo. Salen de los parámetros del veredicto y se miden solo sobre compras ya maduras.', tecnico: 'parametros.veredicto.*',
  },
  foto_del_dia: {
    nombre: 'Foto del día', corto: 'Las cifras de un día cerradas y guardadas: gasto, clics, compras y costo por venta.',
    largo: 'Cada día el sistema guarda una «foto» de las cifras de la oferta con cuándo se leyó cada fuente. Si una fuente está desactualizada, las cifras que dependen de ella se tachan.', tecnico: 'snapshot · kpi_oferta_dia.json',
  },
  ctr_clic: {
    nombre: '% que hace clic', corto: 'De cada 100 veces que se muestra un anuncio, en cuántas alguien hace clic en el enlace.',
    largo: 'Un porcentaje bajo suele significar que el anuncio no llama la atención; uno alto con pocas compras suele significar que la página de venta no convence.', tecnico: 'CTR · ctr_enlace',
  },
  costo_mil_vistas: {
    nombre: 'Costo por mil vistas', corto: 'Lo que cuesta que Meta muestre tu anuncio mil veces.',
    largo: 'Sube cuando hay mucha competencia por esa audiencia. Sirve para entender si un anuncio es caro de mostrar, no si vende.', tecnico: 'CPM · cpm',
  },
  clave_orden_repetida: {
    nombre: 'Clave contra órdenes repetidas', corto: 'Un código que evita que la misma orden de presupuesto se aplique dos veces.',
    largo: 'Si una orden se reenvía por error, el sistema reconoce el código y no la vuelve a ejecutar. Así un reintento nunca gasta ni cambia de más.', tecnico: 'idempotency_key · idempotencia',
  },
  stripe: {
    nombre: 'Stripe', corto: 'El servicio que cobra los pagos de los clientes y registra cada compra, reembolso y disputa.',
    largo: 'Es la fuente de verdad del dinero que entra. Lo que dice Stripe manda sobre lo que dice Meta cuando no coinciden.', tecnico: 'Stripe',
  },
  meta_ads: {
    nombre: 'Meta', corto: 'La plataforma (Facebook e Instagram) donde se publican los anuncios y se paga por mostrarlos.',
    largo: 'Meta informa cuánto se gastó, cuántas veces se mostró cada anuncio y cuántos clics tuvo. Para las compras reales se usa Stripe; Meta es solo referencia.', tecnico: 'Meta Ads',
  },

  // ───────── Finanzas ─────────
  pnl: {
    nombre: 'Cuenta de resultados', corto: 'Ingresos menos todos los costos del periodo: lo que realmente queda. (En contabilidad se llama P&L.)',
    largo: 'Resultado operativo = ingresos brutos − impuestos − reembolsos − comisiones − tarifas y disputas perdidas − gasto en anuncios − costo de IA − otros costos. Una columna por oferta y una con todas juntas.', tecnico: 'P&L · pnl.json',
  },
  resultado_operativo: {
    nombre: 'Resultado operativo', corto: 'Lo que queda después de impuestos, reembolsos, comisiones, anuncios e IA. Negativo = pérdida.',
    largo: 'Es la cifra que manda para saber si el negocio funciona. Si la conciliación no cuadra, se muestra tachada.', tecnico: 'resultado_operativo',
  },
  margen_operativo: {
    nombre: 'Margen operativo', corto: 'Qué parte de los ingresos brutos se queda como resultado operativo (en porcentaje).',
    largo: 'Un margen negativo significa que se gasta más de lo que se ingresa. En una oferta en prueba es normal ver margen negativo: se está pagando por aprender.', tecnico: 'resultado_operativo / ingresos_brutos',
  },
  aov: { nombre: 'Ticket medio', corto: 'Lo que paga de media cada comprador por pedido.', tecnico: 'AOV' },
  contribucion_mc: {
    nombre: 'Contribución por pedido', corto: 'Lo que deja cada pedido después de impuestos, comisiones y reembolsos, antes de pagar anuncios.',
    largo: 'Es el techo del costo por venta: si cada compra cuesta más en anuncios de lo que contribuye, se pierde dinero en cada venta.', tecnico: 'MC',
  },
  mer: { nombre: 'Eficiencia de marketing', corto: 'Ingresos totales divididos entre el gasto total en anuncios. Más alto es mejor.', tecnico: 'MER' },
  roas_neto: {
    nombre: 'Retorno neto de anuncios', corto: 'Lo que vuelve en ventas (sin contar reembolsos) por cada euro o dólar gastado en anuncios.',
    largo: 'Por encima de 1, los anuncios devuelven más de lo que cuestan antes de otros costos; el punto de equilibrio real depende de los márgenes.', tecnico: 'ROAS neto',
  },
  descuadre: {
    nombre: 'Descuadre', corto: 'Las dos fuentes no dicen lo mismo: la diferencia no es cero.',
    largo: 'Cuando Stripe o Meta no coinciden con el libro de movimientos, las cifras que dependen de esa comparación se tachan hasta que se explique la diferencia. Suele ser un pago pendiente, un reembolso tardío o una moneda distinta.', tecnico: 'diferencia ≠ 0',
  },
  alerta_finanzas: {
    nombre: 'Alerta de finanzas', corto: 'Una regla de finanzas que saltó: gasto sobre el tope, costo de IA alto, cuentas que no cuadran, poca caja…',
    largo: 'Las anota el sistema de finanzas al revisar las reglas. Que no haya alertas solo da tranquilidad si esa revisión corrió; si no corrió, nadie las miró.', tecnico: 'alertas.jsonl · F1',
  },

  // ───────── Agentes ─────────
  ejecucion_agente: {
    nombre: 'Ejecución de un agente de IA', corto: 'Una pasada de uno o varios agentes de IA en una etapa: qué hicieron, cuánto costó y cómo terminó.',
    largo: 'Se agrupan las líneas del historial por ejecución. La duración va de la primera a la última línea; el costo es el estimado que anota el historial.', tecnico: 'ejecucion_id · registro.jsonl',
  },
  tope_corrida: {
    nombre: 'Tope por ejecución', corto: 'El costo máximo de IA que puede gastar una ejecución de un agente; lo fijas tú en los límites.',
    largo: 'Sin tope fijado ningún agente puede gastar. Cada ejecución se compara con este máximo.', tecnico: 'max_budget_por_corrida_agente',
  },
  modo_fixture: { nombre: 'Datos de prueba', corto: 'La ejecución usó datos de demostración (oferta de ejemplo), no datos reales.', tecnico: 'modo fixture' },
  modo_dry_run: { nombre: 'Simulacro', corto: 'La ejecución se simuló: calculó qué haría pero no cambió nada fuera del panel.', tecnico: 'modo dry-run' },
  modo_live: { nombre: 'En real', corto: 'La ejecución tuvo efectos reales: gasto, publicación o cambios en cuentas.', tecnico: 'modo live' },

  // ───────── Cumplimiento ─────────
  dictamen: {
    nombre: 'Informe de cumplimiento', corto: 'La revisión de cumplimiento de una etapa: resultado, problemas con su cita y hasta cuándo vale.',
    largo: 'Cumplimiento revisa las afirmaciones, las políticas de Meta y Stripe y las líneas rojas. Un informe vencido o sin visto bueno firmado no autoriza nada, aunque diga que pasa.', tecnico: 'X1 · ofertas/<id>/qa/x1-*.json',
  },
  claim: {
    nombre: 'Afirmación (claim)', corto: 'Una promesa o dato que aparece en la página de venta o el anuncio y que necesita evidencia citada.',
    largo: 'Cada afirmación de salud, de ingresos o de resultados necesita una referencia al producto, a la oferta o a una fuente. Sin evidencia, el problema se marca como bloqueante.', tecnico: 'claims_trazados',
  },
  severidad_hallazgo: {
    nombre: 'Gravedad del problema', corto: 'De más a menos grave: bloqueante, mayor, menor y mejora. Solo el bloqueante veta la etapa.',
    largo: 'Bloqueante: no se puede avanzar. Mayor: hay que corregir. Menor: conviene corregir. Mejora: sugerencia opcional.', tecnico: 'BLOQUEANTE · MAYOR · MENOR · MEJORA',
  },
  semaforo_x1: {
    nombre: 'Semáforo de cumplimiento', corto: 'Verde: sin riesgo relevante. Amarillo: con reservas. Rojo: cumplimiento frena la etapa.',
    largo: 'Se calcula según la promesa, el contenido, el encuadre y el modelo de negocio, nunca según el tema. Una etapa en rojo no avanza hasta corregirla.', tecnico: 'X1 · verde · amarillo · rojo',
  },
  vigencia_sello: {
    nombre: 'Vigencia del visto bueno', corto: 'El visto bueno firmado vale hasta su fecha y solo para el contenido exacto que se revisó.',
    largo: 'Vigente: dentro de plazo y sin cambios. Vencido: se renueva firmando de nuevo. Alterado: el contenido o el informe ya no son los que se firmaron; no se debe usar.', tecnico: 'sello · vigente · vencido · alterado',
  },
  lint_claims: {
    nombre: 'Revisión automática de afirmaciones', corto: 'Una pasada automática que busca promesas de cura, ingresos garantizados, urgencia falsa y opiniones de clientes inventadas.',
    largo: 'Es solo una primera red: lo que encuentra se corrige o se justifica con evidencia. No reemplaza al informe de cumplimiento.', tecnico: 'compliance.lint_claims',
  },

  // ───────── Parámetros y límites ─────────
  sin_fijar: {
    nombre: 'Sin fijar', corto: 'Un límite que todavía no definiste: mientras esté así, nada que dependa de él gasta ni se activa.',
    largo: 'Por seguridad, si falta un tope necesario el sistema se niega a gastar (sale con el código 5). Fijar un límite es decisión tuya y se confirma con tu firma.', tecnico: 'null · fail-closed',
  },
  parametro_hipotesis: {
    nombre: 'Valor de partida', corto: 'Un valor inicial razonable que todavía no se ajustó con datos propios.',
    largo: 'Los parámetros nacen como suposiciones y se ajustan con resultados reales; el sistema propone el cambio y tú lo apruebas.', tecnico: 'hipotesis: true',
  },
  propuesta_parametros: {
    nombre: 'Propuesta de parámetros', corto: 'Valores nuevos que alguien propuso y que todavía no están en vigor.',
    largo: 'Viven en un archivo aparte hasta que tú los apruebes y los incorpores a los parámetros. El panel no incorpora nada.', tecnico: 'empresa/propuestas · *.propuesta.yaml',
  },

  lim_moneda_limites: { nombre: 'Moneda de los límites', corto: 'La moneda de todos los importes; debe ser la de la cuenta publicitaria de Meta.', tecnico: 'moneda_limites' },
  lim_capital_en_riesgo_total: { nombre: 'Capital en riesgo total', corto: 'Todo lo que aceptas arriesgar: anuncios más reservas.', tecnico: 'capital_en_riesgo_total' },
  lim_reserva_no_publicitaria_pct: { nombre: 'Reserva fuera de los anuncios', corto: 'Parte del capital que no va a anuncios: Stripe, herramientas, IA y reembolsos.', tecnico: 'reserva_no_publicitaria_pct' },
  lim_perdida_max_test_por_oferta: { nombre: 'Pérdida máxima por prueba', corto: 'Cuánto puedes perder, como mucho, probando una oferta.', tecnico: 'perdida_max_test_por_oferta' },
  lim_perdida_neta_acumulada_max: { nombre: 'Pérdida total máxima', corto: 'Pérdida máxima de toda la cartera antes de parar todo.', tecnico: 'perdida_neta_acumulada_max' },
  lim_stop_loss_escala: { nombre: 'Freno de pérdida al escalar', corto: 'Pérdida máxima de una oferta que ya se está escalando antes de frenarla.', tecnico: 'stop_loss_escala (stop-loss)' },
  lim_limite_gasto_cuenta_meta: { nombre: 'Límite de gasto en Meta', corto: 'Segundo candado: un tope de por vida puesto en la propia cuenta de Meta, que pausa todo al alcanzarlo.', tecnico: 'limite_gasto_cuenta_meta' },
  lim_gasto_diario_global: { nombre: 'Gasto diario de toda la empresa', corto: 'Techo del gasto máximo posible por día, sumando todas las ofertas.', tecnico: 'gasto_diario_global' },
  lim_gasto_diario_por_oferta: { nombre: 'Gasto diario por oferta', corto: 'Techo del gasto máximo posible por día en una sola oferta.', tecnico: 'gasto_diario_por_oferta' },
  lim_gasto_total_test_por_oferta: { nombre: 'Gasto total de la prueba por oferta', corto: 'Lo máximo que se gasta en anuncios para probar una oferta.', tecnico: 'gasto_total_test_por_oferta' },
  lim_ofertas_en_test_simultaneas_max: { nombre: 'Ofertas en prueba a la vez', corto: 'Cuántas ofertas pueden estar probándose al mismo tiempo.', tecnico: 'ofertas_en_test_simultaneas_max' },
  lim_factor_techo_teorico_diario: { nombre: 'Factor del techo diario', corto: 'Meta puede gastar hasta 1,75 veces el presupuesto diario: lo decide la plataforma, no tú.', tecnico: 'factor_techo_teorico_diario' },
  lim_aumento_presupuesto_max_pct_por_paso: { nombre: 'Aumento máximo por paso', corto: 'Cuánto puede subir el presupuesto de golpe, en porcentaje (20 = 20 %).', tecnico: 'aumento_presupuesto_max_pct_por_paso' },
  lim_horas_min_entre_aumentos: { nombre: 'Horas entre aumentos', corto: 'Tiempo mínimo entre dos subidas de presupuesto, para no desordenar el aprendizaje de Meta.', tecnico: 'horas_min_entre_aumentos' },
  lim_max_cambios_presupuesto_por_hora_por_conjunto: { nombre: 'Cambios de presupuesto por hora', corto: 'Límite que pone Meta a los cambios de presupuesto: no es una decisión tuya.', tecnico: 'max_cambios_presupuesto_por_hora_por_conjunto (límite de la API de Meta)' },
  lim_segundos_min_entre_ediciones: { nombre: 'Pausa entre ediciones', corto: 'Separación mínima entre dos ediciones del mismo elemento en Meta: lo exige la plataforma.', tecnico: 'segundos_min_entre_ediciones' },
  lim_cuentas_permitidas: { nombre: 'Cuentas publicitarias permitidas', corto: 'La lista cerrada de cuentas de Meta donde se puede gastar (una sola en esta fase).', tecnico: 'cuentas_permitidas' },
  lim_paises_permitidos: { nombre: 'Países permitidos', corto: 'Países donde se puede anunciar. Ninguno es favorito de partida.', tecnico: 'paises_permitidos' },
  lim_locales_permitidos: { nombre: 'Idiomas y mercados permitidos', corto: 'Los idiomas y mercados en los que se puede lanzar: el idioma es la unidad de lanzamiento.', tecnico: 'locales_permitidos' },
  lim_macro_nichos_permitidos: { nombre: 'Áreas permitidas', corto: 'Salud, relaciones y dinero: quedó fijado por una decisión de fondo.', tecnico: 'macro_nichos_permitidos' },
  lim_subnichos_prohibidos: { nombre: 'Temas prohibidos', corto: 'Temas excluidos por completo. Vacío: ningún tema queda excluido por sí mismo.', tecnico: 'subnichos_prohibidos' },
  lim_lineas_rojas: { nombre: 'Líneas rojas', corto: 'Promesas, contenidos y modelos de negocio prohibidos (nunca por el tema).', tecnico: 'lineas_rojas' },
  lim_fuentes_permitidas: { nombre: 'Fuentes de investigación permitidas', corto: 'De dónde puede leer el radar de descubrimiento. Vacío: no recoge nada.', tecnico: 'fuentes_permitidas' },
  lim_fuentes_prohibidas: { nombre: 'Fuentes prohibidas', corto: 'Fuentes de investigación que nunca se usan.', tecnico: 'fuentes_prohibidas' },
  lim_precio_neto_minimo: { nombre: 'Precio neto mínimo', corto: 'El precio más bajo, sin impuestos, al que se puede lanzar una oferta.', tecnico: 'precio_neto_minimo' },
  lim_autoaprobar_hasta: { nombre: 'Importe que se aprueba solo', corto: 'Hasta qué importe una acción de dinero puede aprobarse sin ti (solo desde la autonomía 3).', tecnico: 'autoaprobar_hasta · nivel N3' },
  lim_reembolso_auto_max: { nombre: 'Reembolso automático máximo', corto: 'El mayor reembolso que el sistema puede hacer solo, por pedido.', tecnico: 'reembolso_auto_max' },
  lim_reembolsos_auto_max_por_dia: { nombre: 'Reembolsos automáticos por día', corto: 'Cuántos reembolsos automáticos se permiten al día.', tecnico: 'reembolsos_auto_max_por_dia' },
  lim_ratio_disputas_pausa: { nombre: 'Disputas que pausan todo', corto: 'Proporción de disputas sobre los pagos de 30 días a partir de la cual se pausa todo (0,006 = 0,6 %).', tecnico: 'ratio_disputas_pausa' },
  lim_cupon_descuento_max_pct: { nombre: 'Descuento máximo de un cupón', corto: 'El mayor descuento que puede ofrecer un cupón.', tecnico: 'cupon_descuento_max_pct' },
  lim_politica_reembolso_dias: { nombre: 'Días de garantía', corto: 'Días durante los que se puede pedir un reembolso.', tecnico: 'politica_reembolso_dias' },
  lim_politica_divulgacion_ia: { nombre: 'Aviso de que se usó IA', corto: 'Cómo se avisa de que un anuncio usa IA: decisión tuya.', tecnico: 'politica_divulgacion_ia' },
  lim_dias_cobertura_caja: { nombre: 'Días de caja cubiertos', corto: 'Días de gasto que debe cubrir la caja antes de subir presupuesto.', tecnico: 'dias_cobertura_caja' },
  lim_creditos_max_pieza: { nombre: 'Créditos máximos por pieza', corto: 'Créditos de generación de imagen o vídeo que puede gastar una sola pieza de anuncio.', tecnico: 'creditos_max_pieza' },
  lim_creditos_max_oferta: { nombre: 'Créditos máximos por oferta', corto: 'Créditos de generación que puede gastar una oferta en total.', tecnico: 'creditos_max_oferta' },
  lim_max_budget_por_corrida_agente: { nombre: 'Costo máximo de IA por ejecución', corto: 'Lo máximo que puede costar una ejecución de un agente de IA; se compara en la pantalla Equipo de IA.', tecnico: 'max_budget_por_corrida_agente' },
  lim_costo_max_validacion: { nombre: 'Costo máximo de validar', corto: 'Tope de herramientas de pago en la validación de mercado (etapa Validar).', tecnico: 'costo_max_validacion · D2' },
  lim_costo_max_producto: { nombre: 'Costo máximo del producto', corto: 'Tope de producción de un producto: créditos y uso de IA (etapa Producto).', tecnico: 'costo_max_producto · D4' },
  lim_max_costo_por_barrido: { nombre: 'Costo máximo por barrido', corto: 'Lo máximo que puede costar un barrido del radar de descubrimiento.', tecnico: 'max_costo_por_barrido' },
  lim_max_consultas_biblioteca: { nombre: 'Consultas a la Biblioteca de Anuncios', corto: 'Máximo de consultas a la Biblioteca de Anuncios por oferta o por corrida del barrido.', tecnico: 'max_consultas_biblioteca' },
  lim_max_busquedas_por_barrido: { nombre: 'Búsquedas por barrido', corto: 'Búsquedas web máximas en cada barrido de descubrimiento.', tecnico: 'max_busquedas_por_barrido' },
  lim_max_barridos_por_semana: { nombre: 'Barridos por semana', corto: 'Cuántos barridos de descubrimiento se permiten por semana.', tecnico: 'max_barridos_por_semana' },
  lim_correos_max_por_dia: { nombre: 'Correos por día', corto: 'Máximo de correos de post-compra al día.', tecnico: 'correos_max_por_dia' },
  lim_correos_max_por_semana: { nombre: 'Correos por semana', corto: 'Máximo de correos de post-compra a la semana.', tecnico: 'correos_max_por_semana' },
  lim_ventana_veto_min: { nombre: 'Tiempo para vetar', corto: 'Minutos que tienes para frenar una acción antes de que se ejecute (solo con autonomía 4).', tecnico: 'ventana_veto_min · nivel N4' },
  lim_acciones_gate_humano: { nombre: 'Acciones que siempre piden tu firma', corto: 'Acciones que exigen tu aprobación en cualquier nivel de autonomía.', tecnico: 'acciones_gate_humano' },
  lim_hojas_pausadas: { nombre: 'Nichos pausados', corto: 'Ramas del árbol de nichos pausadas por un motivo operativo (nunca por el tema).', tecnico: 'hojas_pausadas' },
  lim_nivel_max_lanzable: { nombre: 'Nivel de riesgo máximo para lanzar', corto: 'Hasta qué nivel de riesgo puede lanzarse cada área. Sin fijar: solo verde.', tecnico: 'nivel_max_lanzable' },
  lim_cuota_gasto_amarillo_max_pct: { nombre: 'Cuota de gasto en riesgo amarillo', corto: 'Parte máxima del gasto diario que puede ir a ofertas de riesgo amarillo. Sin fijar: solo verde.', tecnico: 'cuota_gasto_amarillo_max_pct' },
  lim_cuota_gasto_amarillo_b_max_pct: { nombre: 'Cuota de gasto en riesgo amarillo-b', corto: 'Parte máxima del gasto diario para el amarillo más delicado. Sin fijar: nada.', tecnico: 'cuota_gasto_amarillo_b_max_pct' },
  lim_envios_amarillo_a_semana: { nombre: 'Ofertas amarillo-a por semana', corto: 'Cuántas ofertas de riesgo amarillo-a pueden pasar a prueba cada semana.', tecnico: 'envios_amarillo_a_semana' },
  lim_envios_amarillo_b_mes: { nombre: 'Ofertas amarillo-b por mes', corto: 'Cuántas ofertas de riesgo amarillo-b pueden pasar a prueba cada mes.', tecnico: 'envios_amarillo_b_mes' },
  lim_dias_limpios_para_subir_cuota: { nombre: 'Días limpios para subir la cuota', corto: 'Días sin rechazos ni incidentes exigidos antes de ampliar la cuota de amarillo.', tecnico: 'dias_limpios_para_subir_cuota' },
  lim_edad_minima_audiencia: { nombre: 'Edad mínima de la audiencia', corto: 'Edad mínima por defecto de las audiencias (13 o más). Sin fijar: se usa 18.', tecnico: 'edad_minima_audiencia' },
  lim_reserva_dias_stripe: { nombre: 'Días de reserva de Stripe', corto: 'Días que Stripe puede retener parte de los cobros: lo decide la plataforma.', tecnico: 'reserva_dias_stripe' },
  lim_zonas_grises: { nombre: 'Casos dudosos ya decididos', corto: 'Casos dudosos del marco de riesgo y la decisión que tomaste sobre cada uno.', tecnico: 'zonas_grises' },
  lim_sello: { nombre: 'Tu firma de los límites', corto: 'Tu firma sobre todo el archivo de límites. Sin ella, nada gasta ni se activa aunque todo esté fijado.', tecnico: 'sello · engine.limites sellar' },
};
