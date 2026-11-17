// glosario-resumen.js — términos de las pantallas Resumen, Sistema y Registro (fragmento del glosario; lo importa
// lib/glosario-indice.js de forma tolerante). Formato: { clave: { nombre?, corto, largo?, tecnico? } }.
//   corto   = una frase en palabras simples para el popover al pasar el cursor.
//   largo   = la definición completa (glosario), también sin jerga.
//   tecnico = cómo se llama en los archivos o en el código (solo se ve con «Detalle técnico» encendido).
// Las claves que ya define glosario.js (gate_h, pausa, freno_captura, preflight, cadena_ok, registro, limites, traccion, oferta…) NO se repiten aquí:
// las pantallas las usan tal cual. Sin dependencias ni DOM: se puede probar con node --test.

export const TERMINOS = {
  estado_sistema: {
    nombre: 'Estado del sistema',
    corto: 'Un veredicto de una palabra: En orden, Revisar, En pausa o En rojo.',
    largo: 'Mira cuatro cosas: si hay pausa general, si el freno de la captura de anuncios está puesto, si las cuentas y servicios están en verde (medidos hace menos de 6 horas y de verdad, no en simulacro) y si el historial de actividad sigue sin alteraciones. Si todo está bien dice «En orden»; si algo necesita tu mano, «Revisar».',
    tecnico: 'GET /api/sistema',
  },
  gasto_hoy: {
    nombre: 'Gasto de hoy',
    corto: 'Lo que las ofertas reales gastaron hoy en anuncios, sumado por moneda (las monedas nunca se mezclan).',
    largo: 'Cada oferta informa cuánto gastó hoy en su moneda. La oferta de demostración nunca suma. Si hay varias monedas, la primera se ve en grande y las demás debajo.',
    tecnico: 'estado.json → gasto.hoy',
  },
  // `costo_ia` vive solo en glosario.js (una sola definición; antes estaba repetida aquí y quedaba tapada por la del glosario base).
  alertas: {
    nombre: 'Alertas recientes',
    corto: 'Bloqueos, avisos y errores de las últimas 72 horas, más las alertas de finanzas que siguen abiertas.',
    largo: 'Salen de los avisos y bloqueos del historial de actividad, de los trabajos que terminaron con error y de las alertas de finanzas todavía abiertas. Un bloqueo no siempre es una falla: a veces es un control que está funcionando.',
    tecnico: 'registro.jsonl · empresa/finanzas',
  },
  preflight_infra: {
    nombre: 'Chequeo de cuentas y servicios',
    corto: 'Revisa de una vez que Meta, Stripe, Cloudflare y las demás cuentas estén listas. Si algo falla, nadie gasta.',
    largo: 'Cada cuenta o servicio se prueba y queda en verde, amarillo o rojo. El semáforo general es verde solo si todo lo importante está en verde, la medición es real (no un simulacro) y tiene menos de 6 horas. Si no, nadie gasta ni activa nada.',
    tecnico: 'empresa/infra/estado.json · infra/preflight.py',
  },
  motor: {
    nombre: 'El sistema automático',
    corto: 'El programa que lleva cada oferta de una etapa a la siguiente y aplica las reglas; el panel solo lo observa.',
    largo: 'Decide qué etapa toca, llama a los asistentes de IA, anota todo y se detiene ante una pausa, un freno o un límite. Mientras se construye, los comandos de firma del panel todavía no se pueden usar.',
    tecnico: 'motor · engine.orq',
  },
  consola_acciones: {
    nombre: 'Acciones seguras',
    corto: 'Una lista cerrada de acciones sin riesgo que el panel puede hacer por ti, mostrando lo que pasa en vivo.',
    largo: 'Solo leen datos o escriben archivos en tu computadora, con opciones fijas y revisadas. Nunca activan, publican, gastan, firman ni levantan la pausa o el freno, y no aceptan texto libre.',
    tecnico: 'dashboard/acciones.yaml',
  },
  riesgo_accion: {
    nombre: 'Riesgo de una acción',
    corto: '«Solo lectura» no cambia nada; «Escribe en local» crea o cambia archivos en esta computadora y pide tu confirmación.',
    tecnico: 'riesgo: lectura | escribe_local',
  },
  dry_run: {
    nombre: 'Simulacro',
    corto: 'La acción se calcula y se anota, pero no toca Meta, Stripe ni nada real.',
    largo: 'Es el modo normal mientras las cuentas y servicios no estén en verde y en modo real. Cuando algo se ejecuta de verdad aparece la etiqueta «En real».',
    tecnico: 'dry-run · modo: dry_run | live',
  },
  barrido: {
    nombre: 'Barrido de descubrimiento',
    corto: 'Una pasada por la Biblioteca de Anuncios de Meta para buscar ofertas de otros que llevan tiempo con anuncios activos.',
    largo: 'Hace las búsquedas planificadas, clasifica las páginas encontradas y puntúa a los candidatos con la fórmula de modelado. Termina en fichas para que tú elijas una.',
    tecnico: 'empresa/barrido/<corrida>',
  },
  corrida: {
    nombre: 'Corrida',
    corto: 'Una pasada completa del barrido, con su propia fecha y su propio máximo de búsquedas.',
    largo: 'Cada vez que planificas y ejecutas el barrido se crea una corrida nueva (por ejemplo 2026-11-06-a). Las anteriores se conservan para comparar.',
    tecnico: 'corrida_id',
  },
  consultas_barrido: {
    nombre: 'Búsquedas del barrido',
    corto: 'Cuántas búsquedas se hicieron frente al máximo permitido para la corrida.',
    tecnico: 'consultas_ok / consultas_tope',
  },
  brief: {
    nombre: 'Ficha inicial (brief)',
    corto: 'Un formulario corto con lo básico de la oferta: qué vendes, a quién, en qué idioma y con qué presupuesto de prueba.',
    largo: 'Es el punto de partida de cada oferta. Se completa con hasta 10 preguntas que tienen respuestas sugeridas, y el sistema crea la oferta a partir de ahí.',
    tecnico: '00-brief.yaml',
  },
  cola_en_vivo: {
    nombre: 'Actualización en vivo',
    corto: 'Cuando está activa, los movimientos nuevos del historial aparecen solos, sin recargar la página.',
    tecnico: 'GET /api/eventos (SSE)',
  },
  evento_registro: {
    nombre: 'Tipos de movimiento',
    corto: 'Acción, cambio de etapa, trabajo de IA, decisión, bloqueo, alerta y aprobación: así se clasifica cada línea del historial.',
    tecnico: 'accion · transicion · llamada_herramienta · decision · bloqueo · alerta · aprobacion',
  },
};
