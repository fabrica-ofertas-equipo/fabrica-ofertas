// glosario-decisiones.js — términos de «Quién decide qué» (#/quien-decide). Datos puros: SIN imports (lo carga lib/glosario-indice.js de forma tolerante
// y ui.js importa el índice: un import aquí crearía un ciclo). Forma: TERMINOS = { clave_snake_ascii: { nombre, corto (≤ 140), largo?, tecnico? } }.
// En conflicto manda glosario.js (los de base: gate, gate_a/s/h, autonomia, nivel_n0…n4, sello_x1, pausa, freno_captura, preflight, limites, lim_*…
// NO se repiten aquí). Aquí viven solo las ideas nuevas de esta pantalla; todas distinguen lo que RIGE HOY de lo que es OBJETIVO.

export const TERMINOS = {
  hoy_vigente: {
    nombre: 'Hoy (vigente)', corto: 'Lo que dicen ahora los archivos del sistema: es lo que de verdad se aplica.',
    largo: 'Se lee de la tabla de puntos de control, de los niveles de autonomía y de tus límites cada vez que abres la pantalla. Si un archivo cambia, esta columna cambia sola.', tecnico: 'gates.json · autonomia.yaml · limites.yaml',
  },
  objetivo_j2: {
    nombre: 'Objetivo (J2)', corto: 'El reparto que decidiste el 2026-11-06: los robots prenden, suben, apagan y frenan idiomas solos dentro de un techo. Aún no rige.',
    largo: 'Es una decisión tomada, no una realidad: falta cambiar reglas, formatos, comprobaciones y programas antes de que ocurra. Por eso se dibuja con borde discontinuo y siempre con «qué falta para llegar».', tecnico: 'decisiones-del-dueno.md · J2 · mapeo.md §4',
  },
  reparto_decisiones: {
    nombre: 'Reparto de decisiones', corto: 'Quién decide cada cosa: tú, la IA (Claude), los robots (programas automáticos) y qué te llega a ti.',
    largo: 'Tú decides el techo de gasto, las reglas de oro, los idiomas y el régimen fiscal. La IA decide qué se produce, qué se testea y qué se corrige. Los robots prenden y apagan, suben presupuesto y frenan un idioma. A ti te llega el resumen del día y las alertas de pago.', tecnico: 'mapeo.md §4',
  },
  gate_efectivo: {
    nombre: 'Quién decide de verdad', corto: 'Lo más estricto entre la tabla de puntos de control, el nivel de la etapa y las acciones que siempre piden tu firma.',
    largo: 'La tabla puede decir «por excepción» en un nivel alto, pero si la acción está entre las que exigen tu firma en cualquier nivel, rige tu firma. Mientras esa lista exista, la tabla muestra lo más que podría hacerse solo, no lo que se aplica.', tecnico: 'gates.json ∧ autonomia.yaml ∧ limites.acciones_gate_humano ∧ ACCIONES_GATE_MINIMAS',
  },
  gate_na: {
    nombre: 'Aún no se hace', corto: 'En este nivel de autonomía esa acción no está disponible: ni el sistema ni tú la ejecutáis.',
    largo: 'Por ejemplo, el robot de optimización no puede subir presupuesto hasta llegar al nivel 3. En la tabla aparece como «NA» (no aplica).', tecnico: 'NA',
  },
  cierra_por_defecto: {
    nombre: 'Si falta un dato, no se hace nada', corto: 'Un límite sin fijar no significa «sin tope»: significa que nada que dependa de él puede gastar.',
    largo: 'Por seguridad, si falta un dato no se hace nada: si un límite necesario está sin fijar (o una lista exigida está vacía) o falta tu firma, ningún programa gasta ni activa. Los límites de riesgo (nivel máximo lanzable, cuotas de amarillo) son la excepción: sin fijar = solo verde.', tecnico: 'fail-closed · código de salida 5',
  },
  frenos_empresa: {
    nombre: 'Frenos de empresa', corto: 'Dos frenos para toda la empresa (no por oferta): cuánto se gasta como máximo por día y cuánto se pierde antes de pausar todo.',
    largo: 'Decisión J4: techo global de 300 USD al día y pausa automática cuando la pérdida acumulada llega a 3.000 USD. Reemplazan tu clic para activar: son la red de seguridad que queda cuando los robots prenden solos.', tecnico: 'gasto_diario_global · perdida_neta_acumulada_max',
  },
  techo_gasto_diario: {
    nombre: 'Gasto máximo por día', corto: 'Lo máximo que la empresa entera puede llegar a gastar en un día, sumando todas las ofertas.',
    largo: 'Se compara con el máximo teórico: Meta puede gastar hasta 1,75 veces el presupuesto diario. Por eso, con un techo de 300 USD, los presupuestos diarios sumados llegan a unos 171 USD.', tecnico: 'limites.gasto_diario_global × factor_techo_teorico_diario',
  },
  pausa_por_perdida: {
    nombre: 'Pausa por pérdida', corto: 'Cuando la pérdida neta acumulada de toda la cartera llega al tope, el sistema pausa todo solo.',
    largo: 'Solo una persona levanta esa pausa: ningún robot reactiva, ni siquiera tras una pausa errónea.', tecnico: 'limites.perdida_neta_acumulada_max → empresa/PAUSA',
  },
  activar_sin_clic: {
    nombre: 'Activar sin tu clic', corto: 'Que un robot prenda una campaña solo, tras comprobar la firma de cumplimiento, el chequeo antes de lanzar, los frenos y el paso.',
    largo: 'Es el cambio grande D-02 del objetivo J2. Hoy activar una campaña está entre las seis acciones que piden tu firma en cualquier nivel (no se quitan ni con firma, por diseño); para que rija el objetivo hay que cambiar la tabla, el formato de los límites, el validador y la protección que frena el gasto.', tecnico: 'activar_campana · D-02 · engine/guard.py',
  },
  vigia_pagos: {
    nombre: 'Vigía de pagos', corto: 'Un robot que avisa a tu celular si una cuenta publicitaria deja de gastar por un problema de pago.',
    largo: 'Forma parte de lo que se conserva por código aunque los robots prendan solos. El canal de avisos al celular está pendiente de que lo elijas.', tecnico: 'mapeo.md §4 · robots',
  },
  auditor_robots: {
    nombre: 'Auditor', corto: 'Un control que juzga cada decisión de un robot con lo que pasó después y baja de nivel al que falla.',
    largo: 'Es la pieza más valiosa y la más fácil de olvidar: en el método original, solo 1 de cada 3 subas de gasto acertaba. Por eso las subas se habilitan por etapas, según el acierto medido.', tecnico: 'mapeo.md §11 · degradar nivel',
  },
  rechazos_congelan: {
    nombre: 'Rechazos que congelan', corto: 'Dos rechazos de anuncios de Meta en siete días congelan las activaciones nuevas.',
    largo: 'Con una sola cuenta de Meta, el verdadero tope de velocidad no es el dinero sino los rechazos. La regla ya existe y sigue rigiendo cuando los robots prenden solos.', tecnico: 'rechazos_congelar · docs/02 §7.2',
  },
  sigue_humano: {
    nombre: 'Sigue siendo tuyo', corto: 'Lo que sigues decidiendo tú aunque los robots prendan solos: reactivar tras una PAUSA, firmar límites y reglas, levantar el freno.',
    largo: 'Abren un riesgo nuevo, no se pueden deshacer o son vitales para un negocio con una sola cuenta de Meta y una de Stripe. El panel nunca las ejecuta: te muestra el comando exacto para que las hagas tú.', tecnico: 'reactivar_tras_pausa · cambiar_limites · cambiar_skill',
  },
  nivel_de_etapa: {
    nombre: 'Nivel de la etapa', corto: 'Cuánto hace sola hoy esa etapa: del nivel 0 (todo lo apruebas tú) al nivel 4 (casi todo lo hace el sistema).',
    largo: 'Quién decide una etapa o una acción sale de cruzar su fila de la tabla con el nivel en el que está. Las acciones sin etapa propia no dependen del nivel si valen lo mismo en los cinco.', tecnico: 'autonomia.yaml · nivel_por_etapa',
  },
};
