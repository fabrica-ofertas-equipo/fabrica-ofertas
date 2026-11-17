// glosario-tareas.js — términos de #/tareas («Mis tareas») para el glosario (fragmento que importa lib/glosario-indice.js de forma tolerante).
// Formato: { clave: { nombre?, corto, largo?, tecnico? } }. Las claves que ya existen en otros glosarios (frenos_empresa, pausa, sello_x1, hoy_vigente, objetivo_j2,
// jurado_sintetico, robot, auditor_robots, resumen_diario, tablero_idioma, ruta_familia, oferta_tras_pago, carrito_abandonado…) NO se repiten aquí: la pantalla las usa tal cual.
// Sin dependencias ni DOM.

export const TERMINOS = {
  tarea_momento: {
    nombre: 'Momento',
    corto: 'Un tramo del camino del negocio: arrancar, preparar la primera oferta, lanzar, lo de cada día, lo de cada semana y crecer.',
    largo: 'Las tareas están ordenadas como se hacen: primero lo que solo puedes decidir tú, después preparar una oferta, lanzarla, y por último las rutinas diarias y semanales que mantienen el negocio en marcha.',
    tecnico: 'mapeo.md §2 y §10',
  },
  tarea_quien: {
    nombre: 'Quién la hace',
    corto: 'Tú (una decisión o una firma tuya), El sistema (un programa que corre solo) o Una IA (la prepara una inteligencia artificial y la revisa un revisor independiente).',
    largo: 'Una tarea que prepara una IA puede terminar esperando tu firma: en ese caso aparece como «Espera tu firma» y cuenta como tuya.',
  },
  tarea_estado: {
    nombre: 'Estado de una tarea',
    corto: 'Se calcula con datos reales del sistema, nunca se inventa: Hecha, Pendiente, En curso, Espera tu firma, Bloqueada por otra tarea, Todavía no existe o No se puede comprobar sola.',
    largo: 'Una tarea solo sale «Hecha» si un archivo o una medición lo demuestra, o si la marcaste tú. Cuando el panel no tiene de dónde leerlo, lo dice: «No se puede comprobar sola».',
  },
  no_comprobable: {
    nombre: 'No se puede comprobar sola',
    corto: 'El panel no tiene ningún archivo ni medición que diga si esta tarea está hecha. Puedes marcarla tú.',
    largo: 'Por ejemplo: «elegir el canal de avisos» es una decisión tuya que todavía no se guarda en ningún lado. En estos casos no se inventa un estado.',
  },
  todavia_no_existe: {
    nombre: 'Todavía no existe',
    corto: 'La tarea depende de algo que todavía no se construyó (un robot, el jurado, el resumen diario…). No hay nada para hacer ni para comprobar todavía.',
    largo: 'Esta lista sale del plan y se comprobó contra el repositorio el 2026-11-06. Cuando se construya cada pieza, la tarea pasa a mostrar su estado real.',
  },
  marca_personal: {
    nombre: 'Marca personal',
    corto: 'Una anotación tuya que queda solo en este navegador. Solo para ti: no cambia el sistema ni la ven otras personas.',
    largo: 'Sirve para llevar tu propia cuenta de lo que ya hiciste cuando el panel no puede comprobarlo. Las tareas de cada día vuelven a quedar pendientes al día siguiente, y las de cada semana a la semana siguiente.',
    tecnico: 'localStorage · fab.tareas.marcas',
  },
  accion_segura: {
    nombre: 'Ejecutar ahora',
    corto: 'Corre una comprobación de solo lectura y te muestra el resultado en palabras simples. No firma, no publica, no activa, no gasta y no envía nada.',
    largo: 'Son las mismas acciones de la lista cerrada de la pantalla Salud del sistema. Si algo falla, el mensaje técnico está en «Detalle técnico».',
    tecnico: 'POST /api/accion · dashboard/acciones.yaml',
  },
  revisor_nativo: {
    nombre: 'Revisor nativo',
    corto: 'Una persona que habla ese idioma desde siempre y revisa que los textos suenen naturales y no tengan errores que una IA no nota.',
    largo: 'Se le paga por hora. Hace falta en el primer lanzamiento de cada idioma, sobre todo en polaco y francés.',
  },
  campana_compartida: {
    nombre: 'Campaña con presupuesto compartido',
    corto: 'Una campaña de Meta donde Meta reparte solo el presupuesto entre los anuncios de la campaña, según cuál rinde mejor.',
    tecnico: 'CBO (Campaign Budget Optimization)',
  },
  regla_baja_dia: {
    nombre: 'Regla de baja del primer día',
    corto: 'Si pasó un día, se gastó todo el presupuesto del día y no hubo ninguna venta, la oferta se da de baja y se prueba otra.',
    largo: 'Si Meta no llegó a gastar el presupuesto, ese día no cuenta. Un día sin ventas puede ser mala suerte, así que el plan pide medir cuántas ofertas se descartaron de más y ajustar la regla con esos datos.',
    tecnico: 'J3 · lanzamiento.baja_dias = 1',
  },
  radar_organico: {
    nombre: 'Radar orgánico',
    corto: 'Cuentas secundarias de videos cortos que muestran, gratis, qué formatos funcionan antes de pagar anuncios con ellos.',
    largo: 'Decidiste adoptarlo el 2026-11-06. Los testimonios inventados con IA no se construyen: engañan a quien compra.',
    tecnico: 'J8',
  },
};
