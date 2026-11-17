// glosario-ausencia.js — términos de «¿Me puedo ausentar?» (Resumen) y del informe de las 08:30 (Avisos). Fragmento del glosario: lo importa lib/glosario-indice.js
// de forma tolerante. Formato: { clave: { nombre?, corto, largo?, tecnico? } }. Sin jerga en `corto` ni `largo`; lo técnico va solo en `tecnico`.

export const TERMINOS = {
  semaforo_ausencia: {
    nombre: '¿Me puedo ausentar?',
    corto: 'Un semáforo que dice si puedes dejar de mirar el panel: verde (sí), amarillo (con cuidado) o rojo (todavía no).',
    largo: 'Se calcula leyendo los archivos del proyecto, sin cambiar nada. Es rojo si falta algo de la red de seguridad (pausa y frenos, límites de dinero firmados, chequeo de cuentas, avisos al celular por dos canales) o del trabajo automático (que el sistema se despierte solo y dé señales de vida), o si hay una alerta grave de gasto o ventas abierta. Es amarillo si falta algo para vender (cuenta de Meta, correo, saldo), si hay firmas esperándote o si hay un freno puesto. Un dato que no existe cuenta como falta: nunca se da por bueno algo que no se pudo comprobar. Debajo del semáforo ves qué falta, en orden de importancia, y a quién le toca.',
    tecnico: 'GET /api/alertas → semaforo · scripts/alertas/semaforo.py',
  },
  a_quien_le_toca: {
    nombre: 'A quién le toca',
    corto: 'Cada cosa pendiente dice quién la hace: tú, o el equipo que construye el sistema (S-A, S-B o S-C).',
    largo: 'Lo que lleva «Tú» solo lo puedes hacer tú: elegir, firmar o levantar un freno. El panel nunca firma, activa, gasta ni levanta la pausa por ti. Lo del equipo técnico (S-B) o de contratos (S-A) lo construyen ellos; se anota acá para que sepas qué espera por quién.',
  },
  informe_diario: {
    nombre: 'Informe del día',
    corto: 'Un mensaje por día (a las 08:30) con la misma forma siempre: ventas y gasto, los 5 avisos, los ceros, lo que te toca y lo que todavía no se mide.',
    largo: 'Se arma solo con archivos del proyecto y con frases fijas, sin texto escrito por una IA ni por terceros. Tiene dos versiones: la del correo lleva los importes y el detalle; la del celular lleva solo porcentajes y recuentos, nunca cifras de dinero. Todavía no se envía: falta que elijas el canal de avisos y que el equipo técnico programe el envío.',
    tecnico: 'GET /api/informe · scripts/informe/informe_diario.py',
  },
  los_ceros: {
    nombre: 'Los ceros que importan',
    corto: 'Metas que tienen que dar cero (por ejemplo, pagos frenados sin que te llegara un aviso). Se muestran como «cumple», «no cumple» o «sin medir».',
    largo: 'Un cero solo cuenta si se midió. Si todavía no existe lo que hace falta para medirlo (por ejemplo el vigía de pagos), el informe dice «sin medir» en vez de escribir un cero que parezca bueno.',
  },
  archivo_alertas: {
    nombre: 'Archivo de alertas',
    corto: 'La lista de alertas guardada en tu proyecto. Un programa la calcula y la guarda; este panel solo la lee.',
    largo: 'Mientras nadie guarde el archivo, las alertas que ves se calculan en este momento al abrir la pantalla. Para guardarlas hay un comando que ejecuta una persona (o el planificador, cuando exista). Repetirlo no duplica nada: lo que ya no se cumple se cierra solo.',
    tecnico: 'empresa/datos/alertas.jsonl · python -m scripts.alertas.producir --escribir',
  },
  robots_en_sombra: {
    nombre: 'Robots en sombra',
    corto: 'Robots que miran y proponen, pero no actúan: no envían, no pausan, no gastan. Sirven para ensayar; no son el sistema real.',
    largo: 'Cada uno corre con un comando (a mano o programado en tu Mac cuando tú lo decidas) y deja su señal de vida y el resultado de su última corrida. Un robot solo se espera, y su señal puede estar vencida, si alguien lo programó; una prueba a mano no crea ninguna expectativa. No son el sistema real que construye el equipo técnico (S-B): no vigilan ni frenan nada, y si la Mac duerme se pierden vueltas. Por eso nunca ponen en verde el semáforo «¿Me puedo ausentar?».',
    tecnico: 'python -m scripts.robots.sombra · empresa/robots/estado.json · GET /api/robots/sombra',
  },
};
