// glosario-ofertas.js — términos de las pantallas Ofertas, Oferta, Pulido y Skills (fragmento del glosario; lo importa
// lib/glosario-indice.js de forma tolerante). Formato: { clave: { nombre, corto, largo, tecnico? } }.
//   corto   = una frase en palabras simples para el popover al pasar el cursor (≤ 140 caracteres).
//   largo   = la definición completa (glosario), también sin jerga.
//   tecnico = cómo se llama en los archivos o en el código, para quien quiera buscarlo (solo se ve con «Detalle técnico»).
// Sin dependencias ni DOM: se puede probar con node --test.

export const TERMINOS = {
  pipeline_oferta: {
    nombre: 'Etapas de la oferta',
    corto: 'Los pasos por los que pasa una oferta, de Descubrir a Después de la venta, cada uno con su estado.',
    largo: 'Cada oferta recorre once etapas en orden: Descubrir (D1), Mercado (M1), Validar (D2), Oferta (D3), Producto (D4), Página de venta y pago (D5), Anuncios (D6), Campaña (D7), Operación (D8), Escalado (D9) y Después de la venta (D10). Una etapa no avanza si las que necesita no están aprobadas.',
    tecnico: 'estado.json → etapas · pipeline',
  },
  fase_oferta: {
    nombre: 'Fase de la oferta',
    corto: 'En qué momento de su vida está la oferta: borrador, en construcción, en prueba, validada…',
    largo: 'La fase resume toda la oferta: borrador, en construcción, lista para activar, en prueba, validada, fallida, inconclusa, escalando, retirada o pausada. La mueve el sistema según el estado de las etapas y tus decisiones; tú solo la lees.',
    tecnico: 'estado.json → fase',
  },
  nivel_autonomia: {
    nombre: 'Nivel de autonomía',
    corto: 'Cuánto hace el sistema solo en esa oferta, de 0 (todo lo apruebas tú) a 4 (casi todo lo hace solo).',
    largo: 'En el nivel 0 firmas todo tú; cada nivel siguiente le da al sistema más margen para avanzar solo, siempre dentro de los límites que fijaste. Un nivel más alto nunca levanta los límites de gasto ni la PAUSA (el freno de emergencia).',
    tecnico: 'estado.json → nivel (N0…N4)',
  },
  gate_pendiente: {
    nombre: 'Espera tu firma',
    corto: 'La etapa ya pasó la revisión de calidad y espera tu firma.',
    largo: 'El trabajo y la revisión de calidad terminaron, y la etapa solo avanza cuando tú firmas. Mira primero los archivos y el informe de la revisión.',
    tecnico: 'gate_pendiente: true',
  },
  firma_dueno: {
    nombre: 'Tu firma',
    corto: 'Tu aprobación, que das pegando un comando en tu terminal; usa tu clave de firma personal.',
    largo: 'Firmar es copiar un comando y pegarlo en la Terminal de tu computadora. El panel nunca firma, publica, activa ni gasta por ti: solo te enseña cómo hacerlo.',
    tecnico: 'engine.orq firmar --como dueno',
  },
  etapa_obsoleta: {
    nombre: 'Etapa para rehacer',
    corto: 'Algo de lo que depende cambió después de aprobarla: hay que rehacerla.',
    largo: 'Una etapa queda para rehacer cuando cambia una de sus entradas después de aprobarla. La versión aprobada anterior se conserva, pero el flujo no sigue hasta rehacerla.',
    tecnico: 'obsoleta: true',
  },
  etapa_escalada: {
    nombre: 'Pasó a tu decisión',
    corto: 'Tras dos rondas con problemas graves, el sistema la pasó a una persona.',
    largo: 'Significa que quien prepara el trabajo y el revisor no lograron un resultado aceptable en dos rondas (o hubo un veto de cumplimiento). Solo sale por una orden tuya.',
    tecnico: 'estado: "escalado"',
  },
  revision_qa: {
    nombre: 'Revisión de calidad',
    corto: 'Un revisor independiente mira el trabajo sin saber cómo se hizo y dice si se puede aprobar.',
    largo: 'Es una IA distinta de la que produjo el trabajo. Solo lee: lo puntúa con una lista de criterios, hace comprobaciones automáticas y anota los problemas con su evidencia. No corrige: devuelve el trabajo a quien lo preparó. (En los archivos se llama QA.)',
    tecnico: 'QA · ofertas/<id>/qa/*.json',
  },
  veredicto_qa: {
    nombre: 'Resultado de la revisión',
    corto: 'Aprobada, aprobada con notas, rechazada o pasada a una persona.',
    largo: 'Aprobada: puede seguir. Aprobada con notas: sigue, pero conviene mirar algunos puntos. Rechazada: vuelve a quien la preparó. Pasada a una persona: la decides tú.',
    tecnico: 'veredicto: PASS | PASS_CON_NOTAS | FAIL | ESCALAR',
  },
  puntaje_umbral: {
    nombre: 'Nota y mínimo',
    corto: 'La nota de la revisión frente a la nota mínima que se exige para aprobar.',
    largo: 'Cada criterio se puntúa de 0 a 5; la nota global tiene que alcanzar el mínimo de la etapa para pasar.',
    tecnico: 'puntaje_global / umbral',
  },
  severidad_qa: {
    nombre: 'Gravedad del problema',
    corto: 'Qué tan grave es un problema que encontró el revisor: bloqueante, mayor, menor o mejora.',
    largo: 'Bloqueante: impide aprobar. Mayor: hay que corregirlo (dos rondas con problemas graves pasan la etapa a tu decisión). Menor: conviene corregirlo. Mejora: idea opcional.',
    tecnico: 'hallazgos[].severidad',
  },
  rubrica_qa: {
    nombre: 'Criterios de la revisión',
    corto: 'La lista de cosas que el revisor mira y puntúa, cada una de 0 a 5.',
    largo: 'Cada guía de trabajo trae su lista de criterios: que el resultado sea coherente, que tenga evidencia citada, que cumpla las reglas de publicidad, que sea claro para la siguiente etapa y que se pueda repetir.',
    tecnico: 'rúbrica · items[] en el informe de QA',
  },
  checks_l1: {
    nombre: 'Comprobaciones automáticas',
    corto: 'Verificaciones hechas por un programa, antes de que el revisor opine: formato correcto, huellas que coinciden.',
    largo: 'Antes de puntuar, un programa comprueba que los archivos tengan el formato esperado y que sus huellas coincidan. Si algo falla ahí, no depende de la opinión de nadie.',
    tecnico: 'checks_l1[] · esquemas y hashes',
  },
  hash_salida: {
    nombre: 'Huella del resultado',
    corto: 'Una marca única del resultado aprobado: si alguien lo toca, la huella cambia.',
    largo: 'La huella identifica exactamente lo que se aprobó. Las etapas siguientes la anotan como entrada; si el contenido cambia, la huella cambia y lo que dependía de él queda para rehacer.',
    tecnico: 'hash_salida (sha256)',
  },
  skill_fijada: {
    nombre: 'Versión de la guía de trabajo',
    corto: 'La versión de la guía de trabajo (skill) con la que se hizo la etapa.',
    largo: 'Cada oferta fija qué versión de cada guía de trabajo usa, para que los resultados se puedan repetir aunque la guía se siga mejorando.',
    tecnico: 'estado.json → skills_pin',
  },
  artefacto: {
    nombre: 'Archivo de la etapa',
    corto: 'Un archivo que produjo una etapa: un informe, un documento de datos, una imagen, una página…',
    largo: 'Los archivos de cada etapa viven dentro de la carpeta de la oferta. El panel los muestra solo para leer; si hay varias versiones del mismo archivo (v1, v2) puedes compararlas.',
    tecnico: 'artefacto · ofertas/<id>/<carpeta>/',
  },
  oferta_demo: {
    nombre: 'Oferta de demostración',
    corto: 'Una oferta de ejemplo con datos inventados, para ver todas las pantallas llenas.',
    largo: 'No es real: sirve para ver cómo se ve cada pantalla con datos. Sus cifras no se suman a los totales de las ofertas reales.',
    tecnico: 'ofertas/_ejemplo · demo: true',
  },
  decision_mercado: {
    nombre: 'Decisión de mercado',
    corto: 'El mercado elegido es una hipótesis hasta que lo confirman datos propios.',
    largo: 'Ningún país es «el correcto» de antemano: la decisión de mercado empieza como hipótesis y solo se confirma con clics y compras reales de la propia oferta.',
    tecnico: 'mercado.json → estado_decision',
  },
  bitacora_pulido: {
    nombre: 'Mejoras pendientes',
    corto: 'Tu lista de qué corregir en cada paso hasta que todo corra solo.',
    largo: 'Mientras armas una oferta a mano anotas cada cosa que corriges. Esas notas, ordenadas por etapa, se convierten en reglas de la guía de trabajo; cuando una etapa deja de generar notas nuevas, está lista para correr sola.',
    tecnico: 'bitácora · empresa/panel/pulido.jsonl',
  },
  severidad_pulido: {
    nombre: 'Gravedad de la nota',
    corto: 'Cuánto impide una nota que la etapa corra sola: alta, media o baja.',
    largo: 'Alta: la etapa no puede correr sola mientras exista. Media: molesta pero no frena. Baja: mejora opcional.',
    tecnico: 'severidad: alta | media | baja',
  },
  regla_de_skill: {
    nombre: 'Regla de la guía de trabajo',
    corto: 'Una corrección tuya convertida en una instrucción permanente para la IA.',
    largo: 'Cuando una observación se repite o se resuelve, se escribe en la guía de trabajo (skill) para que la IA la aplique siempre. Es el paso «lo hago a mano, lo anoto, la IA lo aprende».',
    tecnico: 'regla de skill · SKILL.md, referencias o rúbrica',
  },
  skill_borrador: {
    nombre: 'Guía de trabajo en borrador',
    corto: 'Una guía recién escrita (versión 0.1): funciona, pero todavía no la validaste a mano.',
    largo: 'Ninguna versión 0.1 se promueve sola. La pules haciendo la etapa con una oferta real, anotas lo que corriges en Mejoras pendientes y, cuando cumple los criterios para darla por terminada, queda como v1.',
    tecnico: 'skill en estado "borrador" · versión 0.x',
  },
  dod_skill: {
    nombre: 'Criterios para darla por terminada',
    corto: 'La lista de condiciones que una guía de trabajo debe cumplir para pasar de borrador a v1.',
    largo: 'Son once criterios: resultado válido, cálculos exactos, pruebas de calidad, estabilidad, revisor calibrado, tu aceptación en sombra, tamaño razonable, seguridad, costo, que no esté ajustada a un solo caso y, en algunas etapas, cumplimiento. Algunos se ven en los archivos; el resto solo se mide corriendo pruebas.',
    tecnico: 'DoD · docs/03-plan-de-forja-de-skills.md §2.6',
  },
  skill_maker_qa: {
    nombre: 'Quien lo prepara y quien lo revisa',
    corto: 'Cada etapa tiene una IA que produce el trabajo y otra, independiente, que lo revisa.',
    largo: 'Una IA escribe; la otra solo lee y juzga, sin ver el razonamiento de la primera. Esa separación evita que el trabajo se apruebe a sí mismo. (En los archivos se llaman Maker y QA.)',
    tecnico: 'Maker / QA · .claude/agents/<etapa>-maker.md · <etapa>-qa.md',
  },
  evals_skill: {
    nombre: 'Pruebas de calidad',
    corto: 'Casos de prueba que miden si la guía de trabajo mejora el resultado.',
    largo: 'Comparan el resultado con y sin la guía en casos conocidos (algunos perfectos y otros con errores a propósito). Hacen falta al menos seis casos.',
    tecnico: 'evals/',
  },
  sombra_skill: {
    nombre: 'Aceptación en sombra',
    corto: 'Pruebas en las que el sistema trabaja y tú solo corriges lo que haga falta.',
    largo: 'Mide si, en 2 de cada 3 casos, el resultado del sistema se usa sin que tengas que cambiar nada importante.',
    tecnico: 'aceptación en sombra',
  },
};

export default TERMINOS;
