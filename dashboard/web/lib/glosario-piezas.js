// glosario-piezas.js — términos de Fábrica, Jurado, Países y Poscompra (fragmento del glosario; lo importa lib/glosario-indice.js de forma tolerante).
// Formato: { clave: { nombre, corto, largo?, tecnico? } }. corto = una frase para el popover; largo = la definición completa; tecnico = cómo se llama en archivos o código.
// Redacción según dashboard/GUIA_DE_LENGUAJE.md: palabras de todos los días; el nombre técnico va solo en `tecnico`.
// Claves sin colisión con glosario.js ni con los demás fragmentos (la prueba tests/dashboard/test_web_fabrica.mjs lo comprueba). Sin dependencias ni DOM.

export const TERMINOS = {
  turno_noche: {
    nombre: 'Turno de noche',
    corto: 'De 00:00 a 07:00 la fábrica produce una tanda de anuncios nuevos por idioma, sin que tengas que estar.',
    largo: 'Cada idioma pide su encargo a medianoche: primero reemplaza los anuncios que se están cansando, después prueba ideas nuevas y traduce los ganadores. A las 07:00 la tanda espera en «por aprobar». La carga a Meta se hace a la tarde, sin activarla.',
    tecnico: 'etapa de creativos (D6) en modo tanda (pendiente de construir)',
  },
  por_aprobar: {
    nombre: 'Por aprobar',
    corto: 'La bandeja donde espera la tanda ya producida y revisada, antes de pasar a campaña.',
    largo: 'Son las piezas que ya pasaron la revisión automática y esperan tu visto bueno. Aprobarlas es firmar la etapa de creativos; el panel solo te las muestra y nunca las aprueba ni las publica.',
    tecnico: 'ofertas/<id>/06-creativos/ · punto de control (gate) de D6',
  },
  control_seis_puntos: {
    nombre: 'Control de calidad de 6 puntos',
    corto: 'La lista que se repasa en cada pieza: audio, idioma, texto, caras y manos, material ajeno, precios y promesas.',
    largo: 'Es la revisión pieza por pieza antes de subir nada: (1) audio sin cortes ni desfases, (2) un solo idioma, (3) texto sin errores, (4) caras y manos bien hechas, (5) nada de material ajeno, (6) sin precios ni promesas prohibidas. Un punto sin resultado no se da por aprobado.',
    tecnico: 'comprobaciones D6-L1-01…10 de la rúbrica d6-creativos',
  },
  retorno_por_formato: {
    nombre: 'Retorno por formato',
    corto: 'Cuánto se cobra por cada dólar (o euro) gastado, según el tipo de anuncio.',
    largo: 'Se medirá con nuestras ventas: dinero cobrado (menos reembolsos) dividido por lo gastado en anuncios, por formato y con su margen de error. No se usan cifras de terceros porque no se sabe si hablan de ingresos o de ganancia.',
    tecnico: 'rendimiento_formato (pendiente)',
  },
  jurado_votacion: {
    nombre: 'Jurado de clientes simulados',
    corto: 'Diez clientes ideales simulados con IA que votan cada anuncio a ciegas, antes de gastar un peso.',
    largo: 'Cada jurado tiene su edad, su país, su idioma y sus preocupaciones, y todos son distintos (uno desconfía de todo, otro compra por impulso, otro analiza). Sus votos ordenan la tanda y después se comparan con lo que pasó de verdad. Son opiniones de una IA: nunca se citan en un anuncio.',
    tecnico: 'ofertas/<id>/06-creativos/jurado.json',
  },
  voto_a_ciegas: {
    nombre: 'Voto a ciegas',
    corto: 'El jurado ve cada anuncio sin saber cuál ganó antes ni cuál es nuevo.',
    largo: 'Cada jurado vota por separado, una pieza por vez y en orden al azar, sin nombres ni historial. A veces se mezclan piezas que ya tienen resultado (una ganadora y una perdedora) para detectar si el jurado aprueba todo.',
  },
  modo_sombra: {
    nombre: 'Modo sombra',
    corto: 'El jurado predice y se compara con lo cobrado, pero todavía no decide nada.',
    largo: 'Mientras no haya votos comprobados suficientes, su orden no manda: solo se anota y se compara. Pasa a ordenar la tanda únicamente si supera el mínimo de acierto; si no le gana al azar, se apaga solo.',
  },
  etiquetas_jurado: {
    nombre: 'Votos comprobados (etiquetas)',
    corto: 'Votos del jurado que ya se compararon con lo que pasó de verdad (clics, pagos iniciados o compras).',
    largo: 'Cada uno es un anuncio que ya tuvo resultado real. Con menos de 150 por mercado, medir el acierto es medir ruido; por eso el jurado no se juzga antes.',
  },
  auc_jurado: {
    nombre: 'Acierto al ordenar (AUC)',
    corto: 'Qué tan bien ordena el jurado: 0,5 es como tirar una moneda y 1 es acertar siempre.',
    largo: 'Es la probabilidad de que el jurado dé más votos a un anuncio que vendió que a uno que no vendió. Por debajo de 0,5 es peor que el azar; el mínimo propuesto para usar su orden es 0,60.',
    tecnico: 'AUC (área bajo la curva ROC)',
  },
  brier_jurado: {
    nombre: 'Error de las probabilidades (Brier)',
    corto: 'Cuánto se equivocan las probabilidades del jurado: menos es mejor; apostar siempre 50/50 da 0,25.',
    largo: 'Mide cuánto se alejan sus probabilidades de lo que pasó. Se mira junto con el acierto al ordenar: un jurado puede ordenar bien y aun así tener mal calculadas las probabilidades.',
    tecnico: 'Brier score',
  },
  tablero_idioma: {
    nombre: 'Lista de control de un idioma nuevo',
    corto: 'Una lista de 6 columnas que cada idioma nuevo tiene que completar antes de lanzarse.',
    largo: 'Tienda, dominio, Meta, cobro, creativos y listo para lanzar, con 25 tarjetas. Cada una dice quién la resuelve y qué la prueba. La calcula un programa: ni tú ni una IA marcan tarjetas a mano. Un idioma no se lanza hasta que todas estén en Listo.',
    tecnico: 'ofertas/<id>/lanzamiento_idioma.json',
  },
  idioma_base: {
    nombre: 'Idioma base',
    corto: 'El idioma del primer testeo; si funciona, se repite en los demás.',
    largo: 'La oferta, la página y los anuncios se prueban en un solo idioma. Solo si esa oferta original queda validada se crean las versiones en otros idiomas, cada una con sus cuentas, su revisión y su lista de control.',
  },
  ruta_familia: {
    nombre: 'Ruta de familia',
    corto: 'Una misma idea ganadora llevada a varios idiomas: una oferta original y sus versiones en otros idiomas.',
    largo: 'Cada versión reusa el problema, el mecanismo y el producto de la original, pero reescribe textos, promesas y precios para su idioma y pasa por su propia revisión. No hereda el dominio, el visto bueno de cumplimiento ni las cuentas.',
    tecnico: 'familia_id · variante_de (oferta madre e hijas)',
  },
  madre_validada: {
    nombre: 'Oferta original validada',
    corto: 'La oferta original ya demostró que vende; recién entonces se crean las versiones en otros idiomas.',
    largo: 'No se crea una versión nueva hasta que la original esté validada y tú lo hayas confirmado. Así no se multiplican el trabajo ni el riesgo sobre algo que todavía no funciona.',
    tecnico: 'mercados.hija_requiere_madre_validada',
  },
  oss_iva: {
    nombre: 'IVA de la UE (OSS)',
    corto: 'Régimen para declarar, desde un solo país, el IVA de las ventas digitales a consumidores de la UE.',
    largo: 'Un vendedor de fuera de la UE tiene que declarar el IVA de todas sus ventas a consumidores, desde la primera venta y sin mínimo. Stripe Tax calcula el importe pero no presenta la declaración. El régimen se decide con el contador antes del segundo idioma de la UE.',
    tecnico: 'mercado.fiscal.regimen',
  },
  desistimiento_ue: {
    nombre: 'Desistimiento (UE/Reino Unido)',
    corto: 'El derecho del comprador a echarse atrás en 14 días. En un producto digital se pierde solo si él lo acepta antes.',
    largo: 'Para perderlo, el comprador debe aceptarlo antes en una casilla aparte y sin tildar de antemano, y recibir un correo de confirmación. Además, la UE pide una función para desistir en 2 pasos.',
    tecnico: '/desistimiento · mercado.consumo',
  },
  consentimiento_marketing: {
    nombre: 'Permiso para medir la visita',
    corto: 'El permiso del visitante para medirlo con el medidor de Meta antes de enviarle datos.',
    largo: 'En la UE y el Reino Unido, sin permiso no se envía nada a Meta. Por eso, en esos países, nunca se puede saber de qué anuncio vino el 100 % de las ventas.',
    tecnico: 'consent_marketing',
  },
  anunciante_dsa: {
    nombre: 'Anunciante y pagador (ley europea DSA)',
    corto: 'Meta exige declarar quién se beneficia y quién paga cada anuncio dirigido a la UE.',
    largo: 'Es un dato de la empresa que se carga una sola vez en la cuenta de anuncios; sin él, los anuncios hacia la UE no se pueden crear ni editar.',
    tecnico: 'chequeo M-07 · DSA (Ley de Servicios Digitales)',
  },
  embudo_tienda: {
    nombre: 'Camino del comprador (embudo)',
    corto: 'Los pasos desde el clic en el anuncio hasta recibir el producto, con cuánta gente pasa de uno al siguiente.',
    largo: 'Clic en el anuncio, entrada a la página, tocar «comprar», pagar, ver la oferta extra después de pagar y recibir el producto. Si un paso tiene más gente que el anterior no es buena noticia: significa que la medición falló.',
  },
  utm_propio: {
    nombre: 'Etiqueta propia del anuncio (UTM)',
    corto: 'Marcas en el enlace del anuncio que dicen de qué anuncio vino cada venta, sin depender del medidor de Meta.',
    largo: 'El medidor de Meta puede tardar hasta 4 horas en registrar una venta; con las marcas propias se sabe al instante qué anuncio la originó. En la UE y el Reino Unido solo cubre a quien aceptó el permiso de medición.',
    tecnico: 'utm_* · cid · asid · adid',
  },
  carrito_abandonado: {
    nombre: 'Carrito abandonado',
    corto: 'Correo que se envía a quien empezó a pagar y no terminó, solo si dio su permiso.',
    largo: 'Como máximo dos correos (a la hora y a las 24 h), con asunto neutro y solo en ofertas sin tema sensible. Hoy la pantalla de pago no pide el correo, así que todavía no puede funcionar.',
  },
  oferta_tras_pago: {
    nombre: 'Oferta extra después de pagar',
    corto: 'Un producto adicional que se ofrece justo después de pagar, con el precio a la vista.',
    largo: 'Se muestra en la página de gracias como una segunda compra. Una segunda oferta y el cobro con un clic con la tarjeta guardada se dejan para más adelante, hasta medir cuántas disputas generan.',
  },
  disputa_un_clic: {
    nombre: 'Disputa con un clic',
    corto: 'El sistema arma el paquete de pruebas y un borrador de respuesta; tú lo envías desde Stripe.',
    largo: 'El envío no es automático porque exigiría una clave de escritura de Stripe que hoy está negada a las IA. Cuanto antes se responda, mejor: hay una fecha límite.',
    tecnico: 'python -m postcompra.evidencia',
  },
  ticket_promedio: {
    nombre: 'Ticket promedio',
    corto: 'Cuánto gasta en promedio cada comprador por compra, sumando los extras.',
    largo: 'Se medirá con nuestras ventas. Mientras no las haya, solo existe el supuesto de las cuentas de la oferta (el precio más la parte que se espera que acepte el extra), y siempre se rotula como supuesto.',
    tecnico: 'economia.json → aov',
  },
};
