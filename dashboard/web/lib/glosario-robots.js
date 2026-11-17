// glosario-robots.js — términos de «La rueda» (Resumen), Robots, Avisos y Pagos (fragmento del glosario; lo importa lib/glosario-indice.js de forma tolerante).
// Formato: { clave: { nombre?, corto, largo?, tecnico? } }. Las claves que ya definen glosario.js y los demás fragmentos (autonomia, nivel_n0…nivel_n4, pausa,
// preflight, conciliacion, spend_cap, alertas, alerta_finanzas…) NO se repiten aquí: las pantallas las usan tal cual. Sin dependencias ni DOM.
// Redacción según dashboard/GUIA_DE_LENGUAJE.md: palabras de todos los días; el nombre técnico va solo en `tecnico`.

export const TERMINOS = {
  rueda_9_pasos: {
    nombre: 'La rueda de 9 pasos',
    corto: 'El ciclo diario de la fábrica: recordar, producir, votar, probar, escalar, vigilar, auditar, clonar y aprender, y vuelta a empezar.',
    largo: 'Es una forma de leer el sistema entero en nueve pasos que giran todos los días: 1 el cerebro recuerda · 2 la fábrica hace los anuncios · 3 el jurado elige los mejores · 4 se prueban con poca plata · 5 el que vende se agranda · 6 los robots trabajan 24 h · 7 un auditor controla · 8 el ganador viaja a otro país · 9 lo aprendido vuelve al cerebro. Cada paso muestra su estado real, nunca uno supuesto: si falta el dato dice «sin datos todavía» y qué lo producirá.',
    tecnico: 'docs/_historial/mentor-sistema/know-how.md §0',
  },
  paso_sin_datos: {
    nombre: 'Sin datos todavía',
    corto: 'El paso existe en el plan, pero todavía no hay ningún archivo que permita medirlo. No es un cero: es un dato que falta.',
    largo: 'El panel nunca inventa una cifra. Cuando falta el archivo que alimentaría un paso, lo marca «sin datos todavía» y explica qué lo va a producir. En cuanto el archivo aparece, el paso cambia solo a verde o ámbar.',
  },
  cerebro: {
    nombre: 'El cerebro',
    corto: 'La memoria que no se borra: reglas, lecciones y pendientes que leen todas las sesiones y todos los robots.',
    largo: 'Es la pieza 1 del sistema: lo que se decide trabajando, los resultados y cada corrección («así no») quedan escritos para que la próxima sesión arranque sabiendo. Hoy existe solo una parte: la lista única de pendientes (Mejoras pendientes). La memoria con reglas y lecciones todavía no está construida.',
    tecnico: 'empresa/panel/pulido.jsonl',
  },
  jurado_sintetico: {
    nombre: 'El jurado',
    corto: 'Clientes ideales simulados con IA que votan a ciegas los anuncios antes de gastar; después se comparan con lo cobrado de verdad.',
    largo: 'Cada mercado tiene un grupo de unos 10 jurados con su edad, su país, su idioma y sus preocupaciones. Votan sí o no con una frase que explica por qué, se ordena la tanda y a los 3 días se compara cada voto con lo que se cobró: el que acierta pesa más. Se apaga solo si no le gana al azar. Todavía no existe.',
    tecnico: 'mapeo.md §6',
  },
  robot: {
    nombre: 'Robot',
    corto: 'Un programa simple con una sola tarea y su horario: decide con lo que se cobró de verdad, dentro de topes, y deja registro.',
    largo: 'Los robots no «piensan»: son programas que siguen reglas fijas. Leen datos, aplican reglas y topes y actúan (o avisan). La IA propone y el programa decide. Cada robot tiene un horario, un nivel de autonomía (de 0 a 4), un estado (apagado, en sombra o vivo) y un auditor que juzga sus decisiones. Desde esta pantalla no se enciende ni se apaga ninguno.',
    tecnico: 'empresa/robots.yaml',
  },
  robot_escalera: {
    nombre: 'Escalera de escala',
    corto: 'Cada 30 minutos sube el presupuesto de lo que vende y lo baja un 30 % si no rinde.',
    largo: 'Sube por escalones según lo que rindió el día. Al inicio solo duplica (×2); triplicar (×3) y quintuplicar (×5) se habilitan cuando el auditor demuestre que las subas aciertan. Nunca toca por dentro la campaña de escala: solo sube o baja el presupuesto.',
  },
  robot_salvavidas: {
    nombre: 'Salvavidas',
    corto: 'Cada 15 minutos arranca con poco y suma a su presupuesto lo vendido en el día, para aprovechar las horas pico de cada país.',
  },
  robot_guardia: {
    nombre: 'Guardia nocturno',
    corto: 'Entre 01:30 y 07:30 (4 vueltas) lee lo que hicieron los demás robots y ajusta de a poco el costo máximo por venta.',
    largo: 'Las cuatro horas exactas no están en el método original: se calculan cada dos horas (01:30, 03:30, 05:30, 07:30) y se ajustan por mercado.',
  },
  robot_cola: {
    nombre: 'Cola de testeo',
    corto: 'A las 00:10 prende los conjuntos de anuncios nuevos de cada idioma: es el lanzamiento del día.',
    largo: 'Antes de prender algo exige el visto bueno de cumplimiento vigente, la infraestructura en verde y que se respeten los frenos de la empresa. Si falla cualquiera, no prende nada.',
  },
  robot_perfil: {
    nombre: 'Perfil por idioma',
    corto: 'A las 23:40 calcula la meta, el tope y la fase de cada idioma: crece, estable, se cansa o cae.',
  },
  robot_alarma: {
    nombre: 'Alarma de cansancio',
    corto: 'A las 08:05 compara los últimos 3 días con los 7 anteriores y pide un relevo a la fábrica antes de que el anuncio ganador se caiga.',
    largo: 'Cumple la regla de oro 6: el reemplazo se produce antes de que el anuncio ganador se canse. Todavía no está ajustado a partir de cuándo se considera «cansado».',
  },
  robot_vigia: {
    nombre: 'Vigía de pagos',
    corto: 'Si una cuenta publicitaria deja de gastar por un problema de pago, avisa al celular. Aquí además pausa.',
    largo: 'Mientras haya campañas activas, cada 15 minutos mira el estado de la cuenta de Meta, su tope de gasto y su forma de pago. Si algo falla, pausa y avisa por dos canales. Reanudar después de una pausa siempre es decisión humana.',
    tecnico: 'chequeo M-02 · M-03 · watchdog',
  },
  robot_bandeja: {
    nombre: 'Bandeja',
    corto: 'A las 07:00 y a las 19:00 responde comentarios, mensajes y correos con tacto, en cada idioma y con modelos de respuesta aprobados.',
  },
  robot_informe: {
    nombre: 'Informe del día',
    corto: 'A las 08:30 resume ventas, gasto y alertas en un solo mensaje al celular.',
  },
  robot_auditor: {
    nombre: 'Auditor',
    corto: 'Juzga cada decisión de los otros robots con lo que pasó después y le baja el nivel al que falla.',
    largo: 'Es la pieza más valiosa y la más fácil de olvidar. En el método original, 3 de cada 4 cortes de gasto aciertan, pero solo 1 de cada 3 subas: por eso las subas piden más pruebas. Esas cifras las declara el autor del método y nadie las verificó.',
  },
  acierto_auditor: {
    nombre: 'Acierto',
    corto: 'Qué parte de las decisiones de un robot resultó correcta, juzgada con lo que pasó después. Si no se midió, se ve «—», nunca 0 %.',
    largo: 'Se mide por separado para los cortes (bajar o apagar) y para las subas de presupuesto. El mínimo propuesto es 50 % para los cortes y 60 % para las subas; por debajo de eso, el auditor le baja el nivel al robot.',
  },
  latido_robot: {
    nombre: 'Señal de vida',
    corto: 'La última vez que el robot corrió. Si se atrasa más de lo permitido, se lo da por caído.',
    tecnico: 'latido · latido_max_min',
  },
  estado_robot: {
    nombre: 'Estado del robot',
    corto: 'Apagado (no corre), en sombra (corre y anota lo que haría, pero no actúa) o vivo (actúa de verdad, dentro de sus topes).',
    largo: 'Los robots entran de a uno: primero en sombra, comparando sus decisiones con lo que pasó; pasan a vivo recién cuando acierta.',
  },
  nivel_robot: {
    nombre: 'Nivel del robot',
    corto: 'Cuánta autonomía tiene este robot, del nivel 0 (solo mira) al 4. El auditor lo baja si falla; subirlo siempre lo firmas tú.',
    tecnico: 'N0 a N4',
  },
  registro_robots: {
    nombre: 'Registro de robots',
    corto: 'La lista real de lo que corre: horario, nivel, estado, última señal de vida y acierto de cada robot.',
    largo: 'Es un archivo único que todavía no existe. Cuando se construya el marco de robots, esta pantalla lo va a leer sola; si le faltan campos, los muestra como «sin dato».',
    tecnico: 'empresa/robots.yaml',
  },
  reloj_mercado: {
    nombre: 'Hora del mercado',
    corto: 'Todas las horas están en el reloj del mercado de cada idioma. Hay una sola cuenta de Meta; lo que cambia por país es el huso horario, no la cuenta.',
    largo: 'Las horas exactas son hipótesis hasta ajustarlas por mercado (la hora pico de cada país).',
  },
  regla_de_oro: {
    nombre: 'Regla de oro',
    corto: 'Una de las seis reglas que se aprendieron perdiendo plata. Se hacen cumplir con programas, no con buenas intenciones.',
    tecnico: 'know-how.md §9',
  },
  todo_robot_se_audita: {
    nombre: 'Todo robot se audita',
    corto: 'Ninguna decisión automática queda sin control: el auditor la juzga después y le baja el nivel al robot que falla.',
  },
  semana_tipo: {
    nombre: 'Semana tipo',
    corto: 'El ritmo semanal: lunes cierre, martes tanda nueva, miércoles jurado, jueves países, viernes reglas, sábado piloto automático, domingo orden del cerebro.',
    tecnico: 'know-how.md §8',
  },
  severidad_alerta: {
    nombre: 'Gravedad de una alerta',
    corto: 'Información, amarilla, naranja (una oferta debería pausarse) o roja. Cada nivel tiene forma, color y texto propios.',
    largo: 'Información: solo se ve en el panel. Amarilla: va al resumen diario. Naranja: llega al celular y pide pausar la oferta afectada. Roja: llega por todos los canales, sin silencio de noche. Esta forma de enviarlas es una propuesta todavía sin decidir.',
    tecnico: 'contratos/alertas.schema.json',
  },
  estado_alerta: {
    nombre: 'Estado de una alerta',
    corto: 'Abierta (nadie la vio), reconocida (alguien la vio pero el valor sigue fuera de lo normal) o cerrada (volvió a lo normal).',
    tecnico: 'abierta · reconocida · cerrada',
  },
  resumen_diario: {
    nombre: 'Resumen diario',
    corto: 'Un solo mensaje por día (a las 08:30) con ventas, gasto y alertas; los importes van en el correo y los porcentajes, en el celular.',
    largo: 'Ya existe el programa que lo compone (en dos versiones: correo con importes y celular con porcentajes), pero todavía no se envía: falta que elijas el canal de avisos y que el equipo técnico programe el envío diario.',
  },
  canal_avisos: {
    nombre: 'Canal al celular',
    corto: 'Por dónde te llegan los avisos importantes. Siempre son dos canales; hoy no hay ninguno elegido.',
    largo: 'Tienes que elegir el canal para el celular (Telegram solo de salida, que no acepta mensajes entrantes, u otro) y un segundo canal (correo). El sistema ya sabe enviar por dos canales, pero con direcciones de ejemplo.',
    tecnico: 'ALERTA_PUSH_TOKEN · ALERTA_DESTINO',
  },
  dos_canales: {
    nombre: 'Dos canales',
    corto: 'Todo aviso importante sale por un canal del celular y por correo: si uno falla, llega por el otro.',
    largo: 'Es una exigencia del sistema (y su prueba de entrega se hace por los dos). Elegir cuál será el canal del celular es una decisión que te toca a ti.',
  },
  plantilla_fija: {
    nombre: 'Aviso con forma fija',
    corto: 'Los avisos tienen una forma cerrada: gravedad, código de la regla, oferta y hora. Nunca llevan texto libre de una IA ni de terceros.',
    largo: 'Así un aviso no puede filtrar datos del nicho (salud, relaciones, dinero), identificadores de clientes ni enlaces con clave de acceso. Los importes viajan por correo; al celular llegan porcentajes del tope.',
    tecnico: 'plantilla fija',
  },
  cuenta_publicitaria: {
    nombre: 'Cuenta publicitaria',
    corto: 'La cuenta de Meta desde la que se pagan los anuncios. Si se bloquea o su pago falla, deja de gastar aunque todo lo demás esté bien.',
    tecnico: 'account_status · disable_reason',
  },
  forma_de_pago: {
    nombre: 'Forma de pago de la cuenta',
    corto: 'La tarjeta o el método con el que Meta cobra los anuncios. La regla del sistema es no usar fondos prepagos.',
    tecnico: 'funding_source',
  },
  saldo_cuenta: {
    nombre: 'Saldo de la cuenta',
    corto: 'Cuánto queda por gastar bajo el tope de la cuenta (tope menos lo ya gastado). Hoy el panel no tiene ese número, solo el resultado del chequeo.',
    largo: 'El chequeo compara el tope con lo gastado y guarda verde, amarillo o rojo con un texto breve, pero no la cifra. La lectura con el número la dará el vigía de pagos.',
    tecnico: 'spend_cap − amount_spent',
  },
  cobros_stripe: {
    nombre: 'Cobros con Stripe',
    corto: 'Si Stripe puede cobrar a tus clientes y pagarte a tu cuenta, y si las ventas le llegan al sistema.',
    tecnico: 'charges_enabled · payouts_enabled',
  },
  item_preflight: {
    nombre: 'Comprobación del chequeo antes de lanzar',
    corto: 'Una comprobación concreta, de solo lectura (por ejemplo, el tope de gasto de Meta). Cada una sale verde, amarilla o roja, y caduca.',
    tecnico: 'ítem del preflight · infra/plantillas/preflight-items.yaml',
  },
};
