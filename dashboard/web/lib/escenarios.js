// lib/escenarios.js — el camino al 100 % automático: cada situación que le puede pasar al negocio, qué pasa hoy y qué se propone.
//
// Pedido del dueño (2026-11-13): «qué queda para que el sistema sea 100 % automático… sé creativo en buscar posibles escenarios».
// Estado de cada escenario:
//   cubierto   ya hay regla o automatización que lo resuelve sola
//   propuesta  la regla está escrita y se calcula, pero espera tu firma para ejecutarse
//   construir  se puede automatizar sin pedirte nada: falta construirlo
//   decidir    hace falta una decisión tuya (una regla de negocio) antes de construirlo
//   manos      siempre va a necesitar tus manos (identidad, pagos, tokens, apelaciones): se automatiza el aviso
// `prioridad`: 1 = pierde plata o ventas hoy · 2 = frena crecer · 3 = orden y comodidad. `paso`: clave del flujo (lib/flujo.js).

export const AREAS = ['Búsqueda', 'Lanzamiento', 'Test', 'Escala', 'Backend', 'Poscompra', 'Cuenta y pagos', 'Sistema'];

export const ESTADOS_ESC = {
  cubierto: { texto: 'Cubierto', tono: 'ok', icono: 'check' },
  propuesta: { texto: 'Espera tu firma', tono: 'aviso', icono: 'firma' },
  construir: { texto: 'Por construir', tono: 'info', icono: 'engranaje' },
  decidir: { texto: 'Decides tú', tono: 'aviso', icono: 'usuario' },
  manos: { texto: 'Tus manos', tono: 'neutro', icono: 'usuario' },
};

export const ESCENARIOS = [
  // Búsqueda
  { id: 'S01', area: 'Búsqueda', paso: 'buscar', prioridad: 2, estado: 'cubierto', escenario: 'El banco se queda sin candidatos', hoy: 'El radar repone cada 2 horas en 57 mercados.', propuesta: '—' },
  { id: 'S02', area: 'Búsqueda', paso: 'buscar', prioridad: 3, estado: 'cubierto', escenario: 'La Biblioteca bloquea al radar', hoy: 'Pausa de 6 horas y sigue solo.', propuesta: '—' },
  { id: 'S03', area: 'Búsqueda', paso: 'buscar', prioridad: 2, estado: 'cubierto', escenario: 'Una oferta del banco se apaga antes de elegirla', hoy: 'La vuelta diaria del banco saca las que quedaron bajo el piso dos mediciones seguidas (banco_candidatos.py limpiar).', propuesta: '—' },
  { id: 'S04', area: 'Búsqueda', paso: 'renovar', prioridad: 2, estado: 'cubierto', escenario: 'El referente de una oferta nuestra lanza un ángulo nuevo o crece fuerte', hoy: 'La vuelta diaria mide al referente de cada oferta activa; si acelera, sus anuncios nuevos son los 3 nuevos de la renovación de ese día. También cuenta en qué países corre (14-nov): el panel lo muestra con banderas y la réplica no va a esos países.', propuesta: '—' },
  { id: 'S05', area: 'Búsqueda', paso: 'buscar', prioridad: 3, estado: 'cubierto', escenario: 'Un operador grande exporta la misma oferta a varios idiomas', hoy: 'Al verificar una joya, el radar suma las otras ofertas de la misma página del anunciante (radar.py agregar).', propuesta: '—' },
  // Lanzamiento
  { id: 'S06', area: 'Lanzamiento', paso: 'lanzar', prioridad: 1, estado: 'cubierto', escenario: 'Lanzar una oferta nueva sin que la pidas', hoy: 'Tarea «lanzar-ofertas» (06:00 y 13:00): 2 por día; lanza con 1 listo y, con el banco vacío, busca en la misma vuelta hasta conseguir una (14-nov). El radar repone la reserva de 3 verificando y midiendo antes de buscar.', propuesta: '—' },
  { id: 'S07', area: 'Lanzamiento', paso: 'lanzar', prioridad: 1, estado: 'cubierto', escenario: 'Activar la campaña sin tu visto bueno', hoy: 'Control previo automático (control_previo.py): si pasa, se activa sola; con 5 o más rechazados, no y avisa.', propuesta: '—' },
  { id: 'S08', area: 'Lanzamiento', paso: 'lanzar', prioridad: 2, estado: 'manos', escenario: 'Precio «antes» vacío en la tienda', hoy: 'Lo cargas tú.', propuesta: 'El sistema calcula el precio «antes» del referente en la moneda local y te deja la pantalla lista; el guardado es tuyo (un precio tachado que nunca se cobró no lo cargo yo).' },
  { id: 'S09', area: 'Lanzamiento', paso: 'lanzar', prioridad: 1, estado: 'cubierto', escenario: 'Meta rechaza anuncios', hoy: 'La vigilancia corrige y reenvía cada anuncio rechazado una vez; el que vuelve a caer se archiva.', propuesta: '—' },
  { id: 'S10', area: 'Lanzamiento', paso: 'lanzar', prioridad: 2, estado: 'cubierto', escenario: 'No alcanzan los créditos de Kie para producir', hoy: 'La revisión diaria lee el saldo de Kie y avisa si no alcanza para 2 rondas; la recarga es tuya.', propuesta: '—' },
  { id: 'S11', area: 'Lanzamiento', paso: 'lanzar', prioridad: 2, estado: 'manos', escenario: 'Falta el token de la API de conversiones en una tienda', hoy: 'Lo pega el dueño; a veces queda pendiente días.', propuesta: 'Aviso diario hasta que esté, con la pantalla ya abierta.' },
  { id: 'S12', area: 'Lanzamiento', paso: 'lanzar', prioridad: 2, estado: 'cubierto', escenario: 'La fan page o el píxel nuevos quedan restringidos', hoy: 'La revisión diaria lee el estado de la fan page y del píxel de cada oferta y avisa en el momento si se restringen.', propuesta: '—' },
  // Test
  { id: 'S13', area: 'Test', paso: 'test', prioridad: 1, estado: 'cubierto', escenario: 'El test gasta 1,5 tickets por venta', hoy: 'La vigilancia lo apaga en la hora.', propuesta: '—' },
  { id: 'S14', area: 'Test', paso: 'test', prioridad: 1, estado: 'cubierto', escenario: 'La landing o el checkout se caen con la campaña prendida', hoy: 'La vigilancia prueba landing y checkout cada hora: 2 caídas seguidas → pausa; vuelve a prender sola cuando responden.', propuesta: '—' },
  { id: 'S15', area: 'Test', paso: 'test', prioridad: 1, estado: 'cubierto', escenario: 'Hay pagos iniciados pero ninguna compra', hoy: '10 pagos iniciados sin compra en el día → prueba el checkout y avisa.', propuesta: '—' },
  { id: 'S16', area: 'Test', paso: 'test', prioridad: 2, estado: 'cubierto', escenario: 'Meta casi no entrega en el día 1', hoy: 'Decidido (13-nov): solo avisar, una vez.', propuesta: '—' },
  // Escala
  { id: 'S17', area: 'Escala', paso: 'apagar', prioridad: 1, estado: 'cubierto', escenario: 'Después del día 1 cada venta cuesta mucho más de lo que deja', hoy: 'R4 firmada (13-nov): costo por venta de 3 días ≥ 1,5 × lo que deja cada venta, con el backend incluido → la revisión diaria la apaga.', propuesta: '—' },
  { id: 'S18', area: 'Escala', paso: 'renovar', prioridad: 2, estado: 'cubierto', escenario: 'Una oferta gana con margen', hoy: 'Escala por ROAS firmada (13-nov): +30 % cada 24 h con ROAS 1,75-2,5, surfeo cada 3 h sobre 2,5, tirón −30 % si cae; sin techo.', propuesta: '—' },
  { id: 'S19', area: 'Escala', paso: 'renovar', prioridad: 1, estado: 'cubierto', escenario: 'La oferta que pega se queda sin creativos nuevos', hoy: 'Renovación diaria de 10.', propuesta: '—' },
  { id: 'S20', area: 'Escala', paso: 'renovar', prioridad: 3, estado: 'cubierto', escenario: 'Anuncios que solo gastan', hoy: 'Decidido (13-nov): no se pausa nada; la CBO reparte sola.', propuesta: '—' },
  { id: 'S21', area: 'Escala', paso: 'renovar', prioridad: 2, estado: 'cubierto', escenario: 'Una oferta gana fuerte una semana entera', hoy: 'Réplica sola con 7 días de ROAS neto ≥ 1,30 (cupo_lanzamiento.py + tarea de lanzamiento).', propuesta: '—' },
  { id: 'S22', area: 'Escala', paso: 'renovar', prioridad: 3, estado: 'cubierto', escenario: 'El presupuesto de una CBO crece mucho', hoy: 'Decidido (13-nov): sin techo; la sostiene el surfeo y la frena el tirón.', propuesta: '—' },
  { id: 'S23', area: 'Escala', paso: 'renovar', prioridad: 2, estado: 'cubierto', escenario: 'Cuánta plata va a cada oferta cuando hay muchas', hoy: 'La revisión arma la cartera por ROAS neto de 7 días; la plata la mueve la escala por ROAS de cada oferta.', propuesta: '—' },
  // Backend
  { id: 'S24', area: 'Backend', paso: 'backend', prioridad: 1, estado: 'cubierto', escenario: 'Pasa el test y no tiene upsells', hoy: 'La revisión diaria arranca backend-ofensivo.', propuesta: '—' },
  { id: 'S25', area: 'Backend', paso: 'backend', prioridad: 2, estado: 'cubierto', escenario: 'Un upsell no lo acepta nadie o está mal de precio', hoy: 'Precio que aprende solo (13-nov): prueba por tandas y se queda con el que más deja por comprador; si nadie acepta ni barato, pide cambiar el producto.', propuesta: '—' },
  { id: 'S26', area: 'Backend', paso: 'backend', prioridad: 1, estado: 'cubierto', escenario: 'El embudo post-compra se rompe', hoy: 'Ventas sin vistas en el embudo → prueba el demo y avisa.', propuesta: '—' },
  // Poscompra
  { id: 'S27', area: 'Poscompra', paso: 'aprender', prioridad: 1, estado: 'cubierto', escenario: 'Un cliente escribe que no le llegó o no abre el PDF', hoy: 'Tarea «soporte-clientes» (09:30 y 18:30) con Gmail: responde «no me llegó», «no abre» y dudas; reembolsos y casos raros quedan en borrador para ti.', propuesta: '—' },
  { id: 'S28', area: 'Poscompra', paso: 'aprender', prioridad: 1, estado: 'manos', escenario: 'Un cliente pide reembolso', hoy: 'Decidido (13-nov): lo decides tú en cada caso.', propuesta: 'El sistema prepara la respuesta y la devolución, te avisa al celular y espera tu sí. Necesita leer el correo de soporte (S27).' },
  { id: 'S29', area: 'Poscompra', paso: 'aprender', prioridad: 1, estado: 'cubierto', escenario: 'Llega una disputa o contracargo', hoy: 'La revisión diaria responde las disputas con la prueba de entrega y avisa.', propuesta: '—' },
  { id: 'S30', area: 'Poscompra', paso: 'aprender', prioridad: 3, estado: 'manos', escenario: 'Hay compradores contentos pero ninguna reseña', hoy: 'Necesita mandar correos a los compradores: depende de que conectes Gmail.', propuesta: 'Pedir reseña por correo a los 3 días y mostrar las reales en la landing.' },
  // Cuenta y pagos
  { id: 'S31', area: 'Cuenta y pagos', paso: 'test', prioridad: 1, estado: 'manos', escenario: 'La cuenta publicitaria queda restringida', hoy: 'Todo se frena y no hay plan B.', propuesta: 'Aviso urgente y apelación (tuya). Tener una segunda cuenta lista para mover las campañas (decides tú).' },
  { id: 'S32', area: 'Cuenta y pagos', paso: 'test', prioridad: 1, estado: 'manos', escenario: 'Meta no puede cobrar (tarjeta rechazada)', hoy: 'La vigilancia lee el estado de la cuenta cada hora y avisa en el momento si no está activa.', propuesta: 'La vigilancia lee el estado de la cuenta cada hora y avisa al celular en el momento.' },
  { id: 'S33', area: 'Cuenta y pagos', paso: 'test', prioridad: 2, estado: 'cubierto', escenario: 'La cuenta llega a su límite de gasto', hoy: 'Aviso al 80 % del límite de gasto de la cuenta.', propuesta: '—' },
  { id: 'S34', area: 'Cuenta y pagos', paso: 'aprender', prioridad: 3, estado: 'cubierto', escenario: 'Cambia la comisión de Impul Pay o el tipo de cambio', hoy: 'La revisión compara el neto de cada venta con el habitual y avisa si se mueve más de 1 punto o si el tipo de cambio tiene más de 7 días.', propuesta: '—' },
  // Sistema
  { id: 'S35', area: 'Sistema', paso: 'test', prioridad: 1, estado: 'manos', escenario: 'La Mac se duerme o la app se cierra', hoy: 'Nada corre hasta que vuelve.', propuesta: 'Tú: sin reposo con el cargador. Respaldo: regla automática de Meta que apaga un test a los 2 tickets sin compras.' },
  { id: 'S36', area: 'Sistema', paso: 'test', prioridad: 1, estado: 'cubierto', escenario: 'Se desconecta el conector de Meta', hoy: '3 vueltas sin leer Meta → aviso urgente al celular.', propuesta: '—' },
  { id: 'S37', area: 'Sistema', paso: 'test', prioridad: 2, estado: 'cubierto', escenario: 'Se vence la sesión de Impultienda o de Facebook en el navegador', hoy: 'Si una pantalla pide iniciar sesión, la tarea no la inicia: avisa al celular y sigue con lo que puede.', propuesta: '—' },
  { id: 'S38', area: 'Sistema', paso: 'aprender', prioridad: 2, estado: 'cubierto', escenario: 'Dos tareas escriben el libro de tests a la vez', hoy: 'El libro de tests se escribe solo con libro.py: candado, copia previa y escritura atómica.', propuesta: '—' },
  { id: 'S39', area: 'Sistema', paso: 'aprender', prioridad: 2, estado: 'cubierto', escenario: 'Una tarea falla varias veces seguidas', hoy: 'Cada tarea deja su latido; a la tercera falla seguida, aviso urgente; el panel la pone en rojo.', propuesta: '—' },
  { id: 'S40', area: 'Sistema', paso: 'aprender', prioridad: 2, estado: 'cubierto', escenario: 'Te enteras de lo importante solo si abres el panel', hoy: 'Avisos urgentes en el momento (sin repetir) y resumen del día al celular.', propuesta: '—' },
];

export function contarEscenarios(lista = ESCENARIOS) {
  const c = { total: lista.length, cubierto: 0, propuesta: 0, construir: 0, decidir: 0, manos: 0 };
  for (const e of lista) c[e.estado] = (c[e.estado] || 0) + 1;
  c.pct = lista.length ? Math.round((100 * c.cubierto) / lista.length) : 0;
  return c;
}

export function escenariosDe(paso, lista = ESCENARIOS) { return lista.filter((e) => e.paso === paso); }

/** Ordenados para mostrar: primero lo urgente que todavía no está cubierto. */
export function ordenarEscenarios(lista = ESCENARIOS) {
  const peso = { decidir: 0, propuesta: 1, construir: 2, manos: 3, cubierto: 4 };
  return [...lista].sort((a, b) => (a.prioridad - b.prioridad) || (peso[a.estado] - peso[b.estado]) || a.id.localeCompare(b.id));
}
