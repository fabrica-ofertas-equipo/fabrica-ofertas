// lib/flujo.js — el mapa de procesos del sistema de ofertas (pantalla «Cómo funciona», #/flujo).
//
// Pedido del dueño (2026-11-13): dividir el sistema en procesos, decir cuándo se activa cada uno y qué skill lo hace, y verlo
// como un flujo vivo. Aquí viven los procesos (texto fijo, sacado de las skills `modelar-y-lanzar-oferta` y `escalar-oferta`
// y de las reglas firmadas en `references/00-reglas-del-dueno.md`), las brechas que encontró la revisión del 13-nov y las
// funciones PURAS que reparten las ofertas de /api/negocio entre los pasos. Si una skill cambia de dueño de un paso, se
// cambia `skill` / `guia` del paso; si se cierra una brecha, se borra de BRECHAS.

/** Los pasos del flujo, en el orden de la vida de una oferta. `disparo.tipo`: 'auto' (lo corre una tarea sola) · 'pedido' (cuando lo pides) · 'mixto'. */
export const PROCESOS = [
  {
    clave: 'buscar', n: 1, titulo: 'Buscar ofertas', icono: 'lupa',
    skill: 'buscar-ofertas', guia: 'references/05-radar · 04-vuelta-diaria · 01-elegir-del-banco',
    resumen: 'Radar siempre prendido: busca en 93 mercados, en su idioma y en inglés, ofertas de producto digital que ya venden, y pasa las joyas al banco.',
    disparo: { tipo: 'auto', texto: 'Radar: solo, cada 4 horas, las 24 horas (tarea «radar-ofertas»). Banco: cada mañana a las 08:15. Elegir: cuando pides una oferta.' },
    decide: { quien: 'agente', texto: 'Elige sola con el puntaje: complejidad, antigüedad y anuncios, variando de tipo.' },
    hace: [
      'Radar: 15 búsquedas cada 4 horas de una cola mundial de 711 (plataformas de cobro como Hotmart o Digistore24 y frases de entrega como «descarga inmediata» en 27 idiomas).',
      'Mide las que prometen (por dominio o por código de producto), verifica si se pueden producir y pasa las joyas al banco.',
      'Mide cada día todo el banco: ¿tiene más anuncios que ayer?',
      'Compara los videos del referente para ver cuál está iterando (posible anuncio ganador).',
      'Cada mañana mide en qué países corre la oferta original de cada oferta nuestra (banderas en Negocio): ahí no se pauta.',
    ],
    reglas: ['Piso: 15 anuncios activos y 10 días.', 'Banco: al menos 3 candidatos listos; si no, se barre.', 'Nunca un orden fijo de tipos: los mejores y más complejos, variando.', 'Se dice «el radar no encontró», nunca «no hay».', 'Un bloqueo de la Biblioteca no se esquiva: se espera.'],
    pasa_a: ['lanzar'],
  },
  {
    clave: 'lanzar', n: 2, titulo: 'Modelar y lanzar', icono: 'chispa',
    skill: 'modelar-y-lanzar-oferta', guia: 'fases 2 a 12 (la 1 la hace buscar-ofertas)',
    resumen: 'Copia la estructura de la oferta que vende y la lanza en un país donde no se pauta.',
    disparo: { tipo: 'auto', texto: 'Sola, 2 por día (tarea «lanzar-ofertas», 06:00 y 13:00) si hay cupo y 3 ofertas listas en el banco. También cuando la pides.' },
    decide: { quien: 'agente', texto: 'Lanza y activa sola si pasa el control previo (con el funnel entero probado: landing, quiz y checkouts); con 5 o más anuncios rechazados o un funnel con fallas no activa y te avisa.' },
    hace: [
      'Elige el país entre los 93 donde cobra Impul Pay o Stripe (elegir_mercado.py), nunca por costumbre. Veto: nunca un país donde pauta la oferta original; si pauta en todos, la oferta se descarta.',
      'Desarma el referente: landing, anuncios plano por plano, checkout, subidas de ticket.',
      'Voz del mercado, marca, fan page y píxel; producto en PDF; tienda en Impultienda.',
      'Landing con el mismo orden de bloques y anuncios con la misma mezcla y duración.',
      'Campaña CBO de test programada a las 00:00 del día siguiente, hora del mercado.',
    ],
    reglas: ['Precio del principal = el mayor entre 19 USD y el del referente.', 'Presupuesto del test = 3 tickets del producto completo.', 'País entero; la campaña sale a las 00:00.', 'Subida previa y bump solo si el referente los tiene.'],
    pasa_a: ['test'],
  },
  {
    clave: 'test', n: 3, titulo: 'Test del día 1', icono: 'pulso',
    skill: 'escalar-oferta', guia: 'references/04-vigilancia.md · scripts/vigilar_corte.py',
    resumen: 'El primer día del mercado se vigila cada hora, y cada 15 minutos cuando se acerca al corte; si no se paga sola, se apaga en el momento.',
    disparo: { tipo: 'auto', texto: 'Sola, cada hora, las 24 horas, y cada 15 minutos para los tests a 0,6 ticket del corte o menos (tarea «vigilancia-ofertas»).' },
    decide: { quien: 'agente', texto: 'Apaga sola, sin preguntar. Nunca reactiva ni sube presupuesto.' },
    hace: [
      'Lee gasto y compras en Meta y el Purchase del píxel.',
      'El código (vigilar_corte.py) decide: apagar, cerca, sigue o entrega baja.',
      'Si cruza el corte, confirma ventas en Impul Pay, pausa la campaña y lo anota.',
    ],
    reglas: ['Test = día 1 del mercado, o hasta la primera venta.', 'Corte: gasto ≥ 1,5 × ticket del producto completo × máx(1, ventas). Con niveles, el más caro (13 · 19 · 27 → 27).', 'Termina el día 1 con ventas → pasa a post-lanzamiento y se dispara el backend.'],
    pasa_a: ['apagar', 'backend'],
  },
  {
    clave: 'apagar', n: null, titulo: 'Apagar', icono: 'x-circulo',
    skill: 'escalar-oferta', guia: '04-vigilancia.md «Al apagar» · 02-decidir.md',
    resumen: 'La oferta que no se paga se pausa y queda anotado qué se aprendió.',
    disparo: { tipo: 'auto', texto: 'En el test: sola, en la vuelta en que cruza el corte. Después del día 1: la revisión diaria con la regla R4 (CPA de 3 días ≥ 1,5 × lo que deja cada venta) y la vigilancia de cada hora con la R4b (la misma cuenta sin el día 1, tras backend y una ronda de renovación).' },
    decide: { quien: 'agente', texto: 'Apaga sola en los dos casos. Reactivar es tuyo.' },
    hace: ['Pausa todas las campañas del test y comprueba que quedaron en pausa.', 'Anota la pérdida y lo aprendido (CTR, CPM, checkouts) en el libro y en el expediente.'],
    reglas: ['Apagar no espera a las 00:00: cada hora es gasto.', 'No reactiva sola: si aparece una venta vieja, te avisa.', 'Sin frenos de cuenta: cada oferta se corta por su regla (los quitaste el 13-nov).'],
    pasa_a: ['aprender'],
  },
  {
    clave: 'backend', n: 4, titulo: 'Backend ofensivo', icono: 'escalar',
    skill: 'backend-ofensivo', guia: '01-productos-y-precios · 02-armar-en-impultienda · 03-medir-y-ajustar',
    resumen: 'Cuando la oferta ya vende, se le suman ofertas después de pagar para subir el ticket.',
    disparo: { tipo: 'auto', texto: 'Lo dispara la revisión diaria el día que la oferta pasa el test con ventas (regla R3).' },
    decide: { quien: 'agente', texto: 'Se arma y queda activo sin preguntar.' },
    hace: [
      'Hasta 3 upsells post-compra en Impultienda: complementos, nunca el principal ni sus bonos.',
      'Rebajas si el comprador dice que no, conectadas a la oferta siguiente.',
      'Los mismos upsells en todas las tiendas del funnel (niveles, subida previa).',
      'Lo anota en el libro (campo backend) para que el panel lo muestre.',
      'Mide la aceptación de cada upsell y ajusta el precio con 50 vistas.',
    ],
    reglas: ['Solo después del test, salvo que el referente lo tenga en su estructura.', 'Precio contra el mercado, no más barato que el principal por costumbre.', 'Queda activo apenas se crea.'],
    pasa_a: ['renovar'],
  },
  {
    clave: 'renovar', n: 5, titulo: 'Revisar, renovar y escalar', icono: 'refrescar',
    skill: 'escalar-oferta', guia: '01-revision-diaria · 02-decidir · 05-renovacion-diaria · 09-escala-por-campana',
    resumen: 'Cada día se revisa cómo va; a la que gana se le renuevan creativos y se le sube el presupuesto.',
    disparo: { tipo: 'auto', texto: 'Escala por campaña: sola, cada hora, cada campaña con su ROAS con AOV desde su último cambio (surfeo desde 1,8, bajada bajo 1,5). Renovación de las que pegan: una vez por día, en la mañana de cada mercado (vueltas cada 2 h de 08:35 a 22:35). Revisión: una vez por día.' },
    decide: { quien: 'agente', texto: 'Sube, surfea, baja y renueva sola, sin techo; cada renovación es una CBO aparte (la madre no recibe más conjuntos). Reactivar una oferta apagada sigue siendo tuyo.' },
    hace: [
      'Revisión: Meta anuncio por anuncio, estadísticas y neto de Impultienda, píxel, libro de costos.',
      'Aplica la tabla de reglas: escalar, mantener, adelantar la renovación, volver atrás o apagar.',
      'Renovar cada día a las que pegan, en CBO 1-1-10 aparte que salen a las 00:00: «Nuevos» todos los días (10 conceptos distintos, referente primero, después la landing) e «Iteraciones» solo cuando hay un ganador con la ronda anterior leída y rindiendo (o fatigado).',
      'Pasar cada ganador nuevo (3+ compras, ROAS > 2 en 48 h) a un pocket por familia (máx(2 tickets, 3 CPA medio)) y, cada 5 ganadores sostenidos en pocket, sacar una cost cap y una bid cap 1-1-5.',
      'Escalar en el momento, campaña por campaña (principal, pocket, variaciones, réplicas): surfeo cada 3 h con ROAS con AOV ≥ 1,8 y 2 compras (+20/30/40 % según compras), y −30 % bajo 1,5. Los cambios a mano se registran solos y se ven en la línea de tiempo de la ficha.',
    ],
    reglas: ['ROAS con AOV (compras de Meta de la campaña × AOV de la tienda ÷ gasto) ≥ 1,8 con 2 compras → surfeo cada 3 h: +20 % (2-3 compras), +30 % (4-7), +40 % (8+), +10 con ROAS ≥ 3 (desde 500 USD/día, +30 % cada 24 h); < 1,5 → −30 % (nunca bajo el inicial); no sube si la campaña no gasta su presupuesto ni en las últimas 2 h del día del mercado (dueño, 16-nov).', 'R9 v2 (dueño, 17-nov): CBO Nuevos 1-1-10 todos los días y CBO Iteraciones 1-1-10 según resultados, cada una a 3 tickets con corte de 1,5 por campaña; la madre no recibe más conjuntos.', 'Ganador = 3 o más compras con ROAS de más de 2 en 48 h → pocket por familia (hasta 5) a máx(2 tickets, 3 CPA medio), corte 1 ticket.', 'Cada 5 ganadores sostenidos en pocket: cost cap (CPA medio × 1,3) y bid cap (ticket × 1,3) 1-1-5, en la segunda cuenta si está lista.', 'Iteraciones: esperan 24 h de lectura; 2 rondas sin rendir → la familia descansa 3 días, salvo fatiga.', 'Ningún texto tapa una cara.'],
    pasa_a: ['renovar', 'apagar'],
  },
  {
    clave: 'aprender', n: 6, titulo: 'Aprender', icono: 'cerebro',
    skill: 'todas las skills', guia: 'tropiezos.md · CHANGELOG.md · ofertas/historial-modelado.json',
    resumen: 'Lo que falló y lo que corregiste vuelve a la skill, y el historial decide la próxima oferta.',
    disparo: { tipo: 'auto', texto: 'Al cerrar cada lanzamiento, cada revisión y cada apagado.' },
    decide: { quien: 'agente', texto: 'Lo escribe sola. Tus correcciones pasan a reglas fechadas.' },
    hace: ['Suma lo que falló a tropiezos.md y corrige la guía de la fase.', 'Anota la oferta en el historial: la próxima no repite país ni tipo de funnel por costumbre.', 'Sube la versión de la skill con una fila en el CHANGELOG.'],
    reglas: ['Una corrección tuya que no llega a la skill se va a repetir.'],
    pasa_a: ['buscar'],
  },
];

export const POR_CLAVE = Object.fromEntries(PROCESOS.map((p) => [p.clave, p]));

/** Flechas del diagrama: de → a, con su condición. */
export const FLECHAS = [
  { de: 'buscar', a: 'lanzar', texto: 'oferta elegida' },
  { de: 'lanzar', a: 'test', texto: 'sale a las 00:00' },
  { de: 'test', a: 'backend', texto: 'vendió bajo el corte' },
  { de: 'test', a: 'apagar', texto: '1,5 tickets sin pagarse' },
  { de: 'backend', a: 'renovar', texto: 'ticket más alto' },
];

/** Brechas que encontró la revisión del 13-nov. `gravedad`: alta · media · baja. `paso`: dónde pega. */
export const BRECHAS = [
  { id: 'B1', paso: 'apagar', gravedad: 'alta', titulo: 'Después del día 1 no hay corte firmado',
    detalle: 'Una oferta que vendió el primer día pasa a post-lanzamiento y la regla de 1,5 tickets deja de correr. Ya no hay frenos de cuenta: si después el CPA se dispara, nada la apaga sola.',
    cierre: 'Firmar la regla R4 propuesta: CPA real de 3 días ≥ 1,5 × equilibrio → apagar.' },
  { id: 'B2', paso: 'test', gravedad: 'alta', titulo: 'La vigilancia depende de la Mac despierta',
    detalle: 'Las campañas salen a las 00:00 del mercado, de madrugada en Argentina. Si la Mac duerme, el test corre sin corte hasta que vuelva.',
    cierre: 'Tú: Mac enchufada y sin reposo automático. El respaldo con reglas automatizadas de Meta quedó en «No por ahora» (15-nov): el único freno es la vigilancia en esta Mac.' },
  { id: 'B3', paso: 'renovar', gravedad: 'media', titulo: 'Quedan reglas propuestas',
    detalle: 'Renovar y escalar ya son automáticos. Quedan como propuesta: pausar anuncios y conjuntos que solo gastan, ajustar el precio de los upsells y qué hacer cuando Meta casi no entrega.',
    cierre: 'Firmarlas (o ajustarlas) en la conversación sobre automatización.' },
  { id: 'B4', paso: 'lanzar', gravedad: 'media', titulo: 'Activar y lanzar dependen de ti',
    detalle: 'Activar la campaña de un lanzamiento pide tu visto bueno, y una oferta nueva solo se lanza cuando la pides. Para que el sistema sea automático hace falta una regla: cuántas ofertas por semana y con qué controles se activa sola.',
    cierre: 'Definir el ritmo de lanzamientos y los controles para activar sin preguntar.' },
  { id: 'B5', paso: 'aprender', gravedad: 'media', titulo: 'Después de la venta no hay proceso',
    detalle: 'Entrega, correos de soporte, reembolsos y disputas no están en ninguna skill. El correo de soporte llega a Gmail y nadie lo revisa por sistema.',
    cierre: 'Un paso de poscompra en la revisión diaria: soporte, reembolsos y disputas.' },
  { id: 'B6', paso: 'renovar', gravedad: 'baja', titulo: 'Los números del panel se cargan una vez por día',
    detalle: 'La vigilancia lee Meta cada hora pero solo escribe el libro cuando apaga. Entre revisiones, «Datos al…» puede tener hasta 24 horas.',
    cierre: 'Que cada vuelta de la vigilancia actualice gasto y compras en el libro.' },
  { id: 'B7', paso: 'lanzar', gravedad: 'baja', titulo: 'Conviven dos juegos de skills',
    detalle: 'Las 19 skills por etapa (D1 a D10, v0.1 sin usar) traen reglas viejas: escalera 17/19/27 y «D8 no apaga». Las que mandan son las cuatro de este flujo.',
    cierre: 'Marcarlas como archivo de consulta para que nadie las siga por error.' },
];

/** Lo que se cerró en la ronda del 13-nov (se muestra plegado, para que se vea el avance). */
export const CERRADAS = [
  { titulo: 'Corte con niveles', texto: 'El corte usa el ticket del producto completo (Oferta D: 27 → US$ 40,50).' },
  { titulo: 'Frenos de cuenta', texto: 'Eliminados por decisión tuya; cada oferta se corta por su regla.' },
  { titulo: 'Backend sin disparador', texto: 'Skill propia «backend-ofensivo», disparada por la revisión diaria (R3).' },
  { titulo: 'Búsqueda a mano', texto: 'Skill propia «buscar-ofertas» con tarea diaria a las 08:15.' },
  { titulo: 'Super buscador', texto: 'Radar de ofertas siempre prendido: 1.045 búsquedas en 93 mercados y 46 idiomas, cada 4 horas.' },
  { titulo: 'Ritmo de renovación', texto: 'R9 firmada: 10 creativos por día a las ofertas que pegan, con su tarea diaria.' },
];

/** Una regla por situación (espejo de escalar-oferta/references/02-decidir.md y de las reglas de lanzamiento). estado: firmada · propuesta · falta. */
export const REGLAS = [
  { id: 'B1', paso: 'buscar', situacion: 'Siempre', regla: 'Radar: 15 búsquedas de la cola mundial, medir 10 y verificar 3 por vuelta', estado: 'firmada', ejecuta: 'Tarea «radar-ofertas», cada 4 horas' },
  { id: 'B2', paso: 'buscar', situacion: 'Una oferta pasa el piso y se puede producir', regla: 'Entra al banco con su hueco de mercado (suma hasta +10 % al elegir)', estado: 'firmada', ejecuta: 'Radar' },
  { id: 'B3', paso: 'buscar', situacion: 'La Biblioteca bloquea', regla: 'Pausa de 6 horas; no se esquiva', estado: 'firmada', ejecuta: 'Radar' },
  { id: 'L1', paso: 'lanzar', situacion: 'Precio del producto principal', regla: 'El mayor entre 19 USD y el del referente', estado: 'firmada', ejecuta: 'modelar-y-lanzar-oferta' },
  { id: 'L2', paso: 'lanzar', situacion: 'Presupuesto del test', regla: '3 tickets del producto completo, país entero, sale a las 00:00', estado: 'firmada', ejecuta: 'modelar-y-lanzar-oferta' },
  { id: 'L3', paso: 'lanzar', situacion: 'Activar la campaña de un lanzamiento', regla: 'Sola si pasa el control previo (inicio 00:00 en la zona del mercado y funnel entero probado con verificar_funnel.py); con 5 o más anuncios rechazados o fallas en landing o checkout no se activa y avisa', estado: 'firmada', ejecuta: 'Control previo automático' },
  { id: 'L3b', paso: 'test', situacion: 'A los 10-15 min de activar una campaña o una renovación', regla: 'Volver a verificar el funnel entero: anuncios entregando, clics que llegan a la tienda, landing, quiz y cada checkout (correo, botón, imagen del producto) y que cada tienda pueda cobrar; si falla, aviso urgente y se arregla en la vuelta', estado: 'firmada', ejecuta: 'Vigilancia cada 15 min (paso 8, verificar_funnel.py)' },
  { id: 'L5', paso: 'lanzar', situacion: 'Ritmo de lanzamientos', regla: '2 ofertas nuevas por día, mientras el banco tenga 3 listas y haya menos de 8 en test', estado: 'firmada', ejecuta: 'Tarea de lanzamiento (por construir)' },
  { id: 'R1', paso: 'test', situacion: 'Día 1: el CPA llega a 1,5 tickets del completo', regla: 'Apagar en el momento', estado: 'firmada', ejecuta: 'Vigilancia, cada hora (cada 15 min cerca del corte)' },
  { id: 'R1b', paso: 'test', situacion: 'Llega al corte sin ventas, pero el anuncio y la página funcionan', regla: 'Segunda oportunidad: +0,5 ticket una sola vez (CTR ≥ 1 %, ≥ 8 % al pago, ≥ 3 pagos iniciados)', estado: 'firmada', ejecuta: 'Vigilancia, cada hora (cada 15 min cerca del corte)' },
  { id: 'R2', paso: 'test', situacion: 'Termina el día 1 sin ventas ni corte', regla: 'Sigue en test y te avisa: Meta casi no entregó', estado: 'firmada', ejecuta: 'Vigilancia' },
  { id: 'R3', paso: 'backend', situacion: 'Pasa el test con ventas', regla: 'Armar el backend ofensivo ese día y dejarlo activo', estado: 'firmada', ejecuta: 'Revisión diaria → backend-ofensivo' },
  { id: 'R3b', paso: 'backend', situacion: 'En el test, con ventas y el corte ya imposible antes del cierre', regla: 'Armar el backend ya, con el embudo apagado, y prenderlo al cierre del test (ninguna venta de backend dentro del test)', estado: 'firmada', ejecuta: 'Vigilancia de cada hora → backend-ofensivo; paso 6 lo prende' },
  { id: 'R4', paso: 'apagar', situacion: 'Post-test: CPA de 3 días ≥ 1,5 × lo que deja cada venta (AOV neto con backend)', regla: 'Apagar (se mide la oferta entera: las rondas diarias no frenan el corte)', estado: 'firmada', ejecuta: 'Revisión diaria' },
  { id: 'R4b', paso: 'apagar', situacion: 'Post-test: el día 1 no se repite (backend activo y ≥ 1 ronda de renovación con 24 h)', regla: 'Apagar si los días después del test suman CPA ≥ 1,5 × lo que deja cada venta (≥ 2 días; el último cuenta con 70 % del presupuesto gastado) y ningún conjunto nuevo vende con ROAS ≥ 1', estado: 'firmada', ejecuta: 'Vigilancia de cada hora' },
  { id: 'E1', paso: 'renovar', situacion: 'Post-test, ROAS entre 1,75 y 2', regla: '+30 % de presupuesto cada 24 h (ROAS de Meta desde el último cambio, 2 compras como mínimo)', estado: 'firmada', ejecuta: 'Vigilancia, cada hora' },
  { id: 'E2', paso: 'renovar', situacion: 'Post-test, ROAS mayor a 2', regla: 'Surfeo: cada 3 h, +30 % (ROAS 2) a +50 % (ROAS 6,5 o más), sin techo; desde 500 USD/día, +30 % cada 24 h. Con 200 USD/día y ROAS ≥ 1,75, aviso de crear la segunda cuenta', estado: 'firmada', ejecuta: 'Vigilancia, cada hora' },
  { id: 'E3', paso: 'renovar', situacion: 'ROAS con AOV de la campaña desde su último cambio bajo 1,5', regla: 'Bajada −30 % de esa campaña (≥ 3 h y ≥ 2 compras o 1,5 tickets); nunca bajo el presupuesto inicial; sin bloqueo del día; números redondos', estado: 'firmada', ejecuta: 'Vigilancia, cada hora' },
  { id: 'E5', paso: 'renovar', situacion: 'Meta y la tienda no coinciden', regla: 'Manda la tienda: se lee antes de bajar; la revisión diaria compara la ganancia del día con la del escalón anterior', estado: 'firmada', ejecuta: 'Revisión diaria' },
  { id: 'R7', paso: 'renovar', situacion: 'Post-test: CPA entre 1,0 y 1,5 × equilibrio', regla: 'Reemplazada por R16 (15-nov): sin renovar; actúan los cortes', estado: 'reemplazada', ejecuta: '—' },
  { id: 'R16', paso: 'renovar', situacion: 'Empate con ≥ 3 ventas: CPA > ticket promedio / 2 y ROAS neto ≥ 0,95', regla: 'Solo en la entrada: congelar un día sin renovar ni tocar presupuesto, con backend agresivo (2 bumps + 4 upsells); si sigue en la banda, un 2.º día; después decide el dueño. Las validadas (ya escalaron o una ronda entregó 24 h) nunca se congelan: renuevan con ROAS neto de 3 días cerrados ≥ 0,95 y en empate suman backend agresivo', estado: 'firmada', ejecuta: 'Vigilancia de cada hora (paso 3c)' },
  { id: 'R9', paso: 'renovar', situacion: 'La oferta pega (entrada: CPA ≤ ticket promedio / 2; validadas: ROAS neto 3 días cerrados ≥ 0,95)', regla: '10 creativos por día, 100 % nuevos (dueño, 15-nov): primero los mejores anuncios del referente modelados y mejorados, después conceptos nuevos desde la landing; conjunto nuevo en la misma CBO con límites de 10 % a 20 %, sale a las 00:00', estado: 'firmada', ejecuta: 'Tarea «renovacion-diaria», en la mañana de cada mercado' },
  { id: 'R9b', paso: 'renovar', situacion: 'Los límites de los conjuntos nuevos se apilan', regla: 'Cada conjunto conserva mínimo 10 % y máximo 20 % dos días enteros y después se le quitan: en el día, entre 20 % y 40 % para lo nuevo y el resto libre para lo que vende', estado: 'firmada', ejecuta: 'Tarea «renovacion-diaria»' },
  { id: 'R14', paso: 'renovar', situacion: 'Anuncios y conjuntos que solo gastan', regla: 'No se pausa nada: la CBO reparte sola', estado: 'firmada', ejecuta: '—' },
  { id: 'E6', paso: 'renovar', situacion: '7 días con ROAS neto ≥ 1,30', regla: 'Réplica sola en el siguiente mejor país donde no corre la oferta original: backend desde el día 1, pocket 1-1-1 del ganador (1,5 tickets, corte 1) y variaciones 1-1-10 (3 tickets, corte 1,5), todo rehecho al mercado (también casas y cocinas de videos y landing) y fan page completa antes de activar', estado: 'firmada', ejecuta: 'Tarea de lanzamiento (por construir)' },
  { id: 'P1', paso: 'aprender', situacion: 'Un cliente pide reembolso', regla: 'Se prepara la devolución y se espera tu sí en cada caso', estado: 'firmada', ejecuta: 'Tú' },
  { id: 'R10', paso: 'renovar', situacion: 'Conjunto nuevo en una CBO', regla: 'Límites de gasto: mínimo 10 % y máximo 20 % (dueño, 15-nov), puestos y comprobados', estado: 'firmada', ejecuta: 'Quien crea el conjunto' },
  { id: 'R12', paso: 'apagar', situacion: 'Reactivar una oferta apagada', regla: 'Lo decides tú (cerrada: restauras sus tiendas desde «Tiendas archivadas»)', estado: 'firmada', ejecuta: 'Tú' },
  { id: 'R15', paso: 'apagar', situacion: 'Oferta apagada hace 72 h por un corte (R1, R4, R4b) o a mano', regla: 'Se cierra y se archivan sus tiendas en Impultienda, para que solo queden las vivas; no se cierran las pausas técnicas ni las que vendieron después del apagado', estado: 'firmada', ejecuta: 'Vigilancia de cada hora' },
  { id: 'R17', paso: 'backend', situacion: 'Alguien deja el correo en el checkout y no paga (carrito abandonado o pago rechazado)', regla: 'Se le manda la repesca de Impultienda: un mail con el link de pago y 33 % de descuento, una sola vez por carrito, en todas las tiendas de la fábrica', estado: 'firmada', ejecuta: 'Tarea «repesca-carritos», cada hora' },
  { id: 'R13', paso: 'backend', situacion: 'Precio de los upsells', regla: 'Aprende solo: prueba precios por tandas y se queda con el que más deja por comprador', estado: 'firmada', ejecuta: 'Revisión diaria' },
  { id: 'P2', paso: 'aprender', situacion: 'Llega una disputa', regla: 'Responder solo con la prueba de entrega y avisarte', estado: 'firmada', ejecuta: 'Por construir' },
  { id: 'P3', paso: 'aprender', situacion: 'Mails de clientes', regla: 'Responder solos «no me llegó» y «no abre»; reembolsos a ti', estado: 'firmada', ejecuta: 'Falta conectar Gmail' },
];
export function reglasDe(paso, lista = REGLAS) { return lista.filter((r) => r.paso === paso); }
export function contarReglas(lista = REGLAS) {
  return lista.reduce((a, r) => ({ ...a, [r.estado]: (a[r.estado] || 0) + 1 }), { firmada: 0, propuesta: 0, falta: 0 });
}

const ORDEN_GRAVEDAD = { alta: 0, media: 1, baja: 2 };
export function brechasOrdenadas(lista = BRECHAS) {
  return [...lista].sort((a, b) => (ORDEN_GRAVEDAD[a.gravedad] ?? 9) - (ORDEN_GRAVEDAD[b.gravedad] ?? 9));
}
export function brechasDe(paso, lista = BRECHAS) { return lista.filter((b) => b.paso === paso); }

/** Etapa del tablero → paso del flujo. Las que pasaron el test aparecen además en «backend» con su estado de backend. */
export const PASO_DE_ETAPA = {
  programada: 'lanzar', test: 'test', apagar: 'apagar', apagada: 'apagar',
  aprobada: 'renovar', renovacion_programada: 'renovar', renovando: 'renovar',
};
const POST_TEST = new Set(['aprobada', 'renovacion_programada', 'renovando']);

/**
 * Reparte las ofertas del tablero (y las que se están armando) entre los pasos.
 * → {clave: [{id, nombre, mercado, etiqueta, tono, urgente, enlace}]}
 */
export function repartir(ofertas = [], armado = []) {
  const out = Object.fromEntries(PROCESOS.map((p) => [p.clave, []]));
  for (const a of armado || []) {
    if (!a || !a.carpeta) continue;
    const n = a.fases_total ? ` · ${a.fases_hechas}/${a.fases_total}` : '';
    out.lanzar.push({ id: a.carpeta, nombre: a.titulo || a.carpeta, mercado: null, etiqueta: `armando${n}`, tono: 'info', urgente: false, enlace: null });
  }
  for (const o of ofertas || []) {
    if (!o || typeof o.id !== 'string') continue;
    const et = o.etapa || {};
    const paso = PASO_DE_ETAPA[et.clave];
    const accion = (o.accion_sugerida || {}).clave;
    const base = { id: o.id, nombre: o.nombre || o.id, mercado: o.mercado || null, enlace: `#/negocio/${encodeURIComponent(o.id)}` };
    if (paso) {
      let etiqueta = et.corto || et.texto || '';
      let tono = et.tono || 'neutro';
      let urgente = et.clave === 'apagar';
      if (accion === 'escalar' && paso === 'renovar') { etiqueta = 'escalando sola'; tono = 'ok'; }
      if (et.clave === 'apagada') tono = 'pausada';
      out[paso].push({ ...base, etapa: et.clave, etiqueta, tono, urgente });
    }
    if (POST_TEST.has(et.clave)) {
      const b = o.backend || {};
      const activo = b.estado === 'activo';
      out.backend.push({ ...base, etiqueta: activo ? 'backend activo' : (b.estado === 'armando' ? 'armando' : 'falta backend'), tono: activo ? 'ok' : 'aviso', urgente: !activo });
    }
  }
  return out;
}

/** Salud de cada paso con los datos vivos. → {clave: {tono: 'ok'|'aviso'|'error'|'neutro', texto}} */
export function saludDe(reparto, flujo = {}) {
  const v = flujo.vigilancia || {};
  const banco = flujo.banco || {};
  const r = reparto || {};
  const s = {};
  const diario = flujo.buscar_diario || {};
  const radar = flujo.radar || {};
  if (radar.existe && radar.bloqueo) s.buscar = { tono: 'aviso', texto: `Radar en pausa por bloqueo hasta ${String(radar.bloqueo.hasta).slice(11, 16)}` };
  else if (radar.existe && typeof radar.edad_min === 'number' && radar.edad_min > 300) s.buscar = { tono: 'error', texto: `El radar no corre hace ${horas(radar.edad_min)}` };
  else if (radar.existe && radar.edad_min !== null && radar.edad_min !== undefined) s.buscar = { tono: 'ok', texto: `Radar · ${radar.hoy} búsquedas hoy · ${radar.ofertas} ofertas` };
  else if (banco.error) s.buscar = { tono: 'neutro', texto: 'Sin lectura del banco' };
  else if (!diario.fecha) s.buscar = { tono: banco.veredicto === 'ALCANZA' ? 'ok' : 'aviso', texto: `${banco.veredicto === 'ALCANZA' ? 'Alcanza' : 'Hay que barrer'} · la vuelta diaria todavía no corrió` };
  else if (banco.veredicto === 'ALCANZA') s.buscar = { tono: 'ok', texto: `Banco con ${(banco.listos || []).length} listos` };
  else s.buscar = { tono: 'aviso', texto: 'Hay que barrer' };
  s.lanzar = (r.lanzar || []).some((x) => x.etiqueta && x.etiqueta.startsWith('armando'))
    ? { tono: 'info', texto: 'Hay ofertas armándose' } : { tono: 'ok', texto: 'Lista para usar' };
  if (!v.existe) s.test = { tono: 'error', texto: 'La vigilancia no registró vueltas' };
  else if (v.salud === 'ok') s.test = { tono: 'ok', texto: `Vigilando · hace ${v.edad_min} min` };
  else if (v.salud === 'aviso') s.test = { tono: 'aviso', texto: `Última vuelta hace ${v.edad_min} min` };
  else s.test = { tono: 'error', texto: `Sin vueltas hace ${horas(v.edad_min)}` };
  const porApagar = (r.apagar || []).filter((x) => x.urgente).length;
  s.apagar = porApagar ? { tono: 'error', texto: `${porApagar} cruzó el corte y sigue activa` } : { tono: 'ok', texto: 'Nada cruzado sin apagar' };
  const faltan = (r.backend || []).filter((x) => x.urgente).length;
  s.backend = faltan ? { tono: 'aviso', texto: `${faltan} sin backend: se arma en la próxima revisión` } : { tono: (r.backend || []).length ? 'ok' : 'neutro', texto: (r.backend || []).length ? 'Todas con backend' : 'Ninguna pasó el test' };
  const escalar = 0;
  const para = (r.renovar || []).filter((x) => x.etapa === 'aprobada' && !x.urgente).length;
  s.renovar = escalar ? { tono: 'aviso', texto: `${escalar} para escalar: espera tu OK` }
    : para ? { tono: 'aviso', texto: `${para} para renovar` } : { tono: 'ok', texto: 'Al día' };
  s.aprender = { tono: 'ok', texto: `${(flujo.lanzamientos || []).length} lanzamientos en el historial` };
  return s;
}

export function horas(min) {
  if (typeof min !== 'number') return '—';
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  return h < 48 ? `${h} h` : `${Math.floor(h / 24)} días`;
}

/** Texto de quién decide, corto, para la tarjeta. */
export const QUIEN = { agente: { texto: 'Lo decide el sistema', icono: 'robot' }, mixto: { texto: 'Sistema y tú', icono: 'balanza' }, dueno: { texto: 'Lo decides tú', icono: 'usuario' } };
export const DISPARO = { auto: { texto: 'Automático', icono: 'rayo' }, pedido: { texto: 'A pedido', icono: 'usuario' }, mixto: { texto: 'Automático y a pedido', icono: 'reloj' } };
