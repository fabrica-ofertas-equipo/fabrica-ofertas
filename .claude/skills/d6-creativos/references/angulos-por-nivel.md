# Ángulos, riesgo por pieza y anti-copia

Fuente: `docs/_investigacion/25-marco-salud-relaciones-dinero.md` §2, §4, §5 (marco 25), `docs/_investigacion/11-playbook-anuncios-creativos.md` §2.2 y §5. Si algo cambia en la nota 25, manda la nota. El riesgo se evalúa **por promesa, contenido, encuadre y modelo de negocio, nunca por tema**: una «cura» es rojo; una guía de reinserción laboral es válida; «ganar dinero con manualidades» es válido si el ángulo no promete ingresos.

## 1. Qué exige cada nivel de la oferta

| | VERDE | AMARILLO-A | AMARILLO-B | ROJO |
|---|---|---|---|---|
| Ángulos | Los patrones de §3 | Producto, criterio o herramienta; sin condición del lector | Igual, sin gancho de ruptura, duelo, abuso ni deuda; decisión H | Ninguno hasta reencuadrar |
| Avisos | Alcance; en conflicto de pareja o familia (también verde): «Si temes por tu seguridad, no uses este material» + línea de ayuda del país | Aviso por tipo de producto | Aviso reforzado + bloque «Si necesitas ayuda ahora» con `ayuda_por_pais.yaml` | No corrigen un claim |
| Revisión humana | L1 y muestreo (parámetro `compliance.x1_muestreo_verdes` **[PENDIENTE]**) | **RHS** de la primera pieza de cada ángulo nuevo; las demás pasan por X1 | RHS y decisión H | Abstención |
| Mercado | Matriz país × nivel (X1, `J01`) | Gate H del dueño una vez por país × macro-nicho × nivel | Solo con ayuda verificada del país | No se lanza |

RHS = revisión humana de seguridad: una persona recorre la lista L3 de 22f §4.7 en 30–60 min; no acredita exactitud clínica. El **subnivel** (A/B) lo calcula `scripts.nivel_riesgo` (`subnivel` aparte de `nivel`, que va en minúscula) y no esta skill. Si el snapshot de `oferta.riesgo` no trae `ejes_codigo` (hasta el MINOR de LT-04/LT-20/LT-42), se derivan de los colores: ≥2 amarillos = B `[SUPUESTO]`.

## 2. Tabla única ejes → nivel (la aplica `python -m scripts.nivel_riesgo --P … --C … --E … --N … --json`; esto es solo la definición operativa de los códigos)

Se califica la tupla (oferta, **pieza**, mercado). El candidato fija P, C y N; la pieza fija E y puede **agravar P**. El nivel lo da el código (el **máximo** de los cuatro ejes): el Maker asigna el **código** de cada eje (`ejes_codigo`) y lo justifica con la frase o el fotograma que lo causa; no escribe el nivel a mano. Una pieza puede ser **menor** que la oferta (p. ej. solo producto, sin la promesa central): no es defecto; si **repite la promesa central**, hereda al menos el eje P de la oferta.

| Eje | Código → color | Definición operativa (resumen) |
|---|---|---|
| **P** Promesa | P0 · P1 → verde; P2s → amarillo; P2n · P3 → rojo | P0: el sujeto es el archivo, plan o tabla. P1: beneficio de uso con verbos de la herramienta (registra, ordena, calcula, planifica, compara); el producto no es causa de un cambio en el cuerpo, ánimo, dinero o deuda del lector. **P2s:** cifra reproducible por el lector con supuestos visibles y rótulo «ilustrativo» **en el mismo cuadro o audio**, sujeto = el documento («la tabla suma 1 378»). **P2n:** el producto o la pieza atribuyen al lector un resultado futuro, con o sin cifra o plazo (baja, alivia, calma, reinicia, elimina, multiplica; «sin experiencia», «sin inversión»; estados en el nombre: «Glucosa Estable», «Cero Deudas»). **P3:** cura, ingreso garantizado, control de un tercero, testimonio sintético, antes/después, escasez o precio ficticios |
| **C** Contenido | C0 · C1 → verde; C2 → amarillo; C3 → rojo | C0 plantillas en blanco; C1 método o guion con ejemplo; C2 criterio nutricional, seguridad alimentaria con cifras, calendarios de plazos legales, guion sobre ruptura/duelo, método de pago de deuda propia; C3 dosis, diagnóstico, tratamiento, kcal objetivo, ayuno >24 h, planes de seguridad, vigilancia, documentos legales personalizados |
| **E** Encuadre | E0 · E1 → verde; E2 · E3 → rojo | E0 habla del producto. E1 rol en tercera persona sin atributo, o «tú» sin atributo. **E2:** afirma, implica o **pregunta** un atributo del espectador (edad, sexo, estado familiar, salud, situación financiera vulnerable, «tu ex») o un juicio sobre su valor, cuerpo o aspecto. E3 menores |
| **N** Negocio | N1 → verde; N1s → amarillo; N2 · N3 → rojo | N1 vigilada (hábitos, pareja, presupuesto, empleo, impuestos). N1s: el entregable mide o registra el cuerpo del comprador o este carga datos sensibles en un formulario. N2: exige autorización o conecta personas (citas, telemedicina, inversión, bolsa de vacantes). N3: multinivel, get-rich-quick, reparación de crédito |

Reglas de la tabla (las aplica `scripts.nivel_riesgo`; en este orden): P ∈ {P2n,P3} **o** C = C3 **o** E ∈ {E2,E3} **o** N ∈ {N2,N3} → **ROJO**. Si no: P2s **o** C2 **o** N1s → **AMARILLO**. El resto → **VERDE**.

**Prueba del espectador ajeno** (E): la frase debe ser verdadera y neutra para cualquier persona que la lea; si solo tiene sentido para quien padece X, afirma X. «Tu ex» es E2; «un ex» es aprobable.

**Quién sube o baja:** D6 puede **subir** el nivel de una pieza sin permiso; **bajar** solo con un reencuadre verificable y lo confirma X1. Un LLM no baja un nivel que el lint subió. El overlay de mercado (X1/M1) solo sube.

**Formato en `matriz.json` (por anuncio):** `riesgo_pieza: {P, C, E, N, nivel, ejes_codigo{P,C,E,N}, lineas_rojas[], repite_promesa_central}` (colores `verde|amarillo|rojo`; `repite_promesa_central` es booleano y sin él no se verifica la regla 3 de L1.4). `lineas_rojas[]` lista ids (`lp-01`…`lm-11`, nota 25 §3.3) tocados; vacío si ninguno.

## 3. Patrones seguros, «nunca decir» y «siempre incluir»

| | Patrones seguros | Nunca decir (L1 bloquea; X1 veta) | Siempre incluir |
|---|---|---|---|
| **Salud** | El producto, no el cuerpo; contenido contable («60 recetas con tabla por porción»); criterio de selección; situación; tiempo de la sesión; formato | Enfermedades de la lista de curas (diabetes, herpes, tiroides, psoriasis, ébola, cáncer, autismo, alzhéimer, párkinson, ELA, VIH) en anuncio, titular o nombre; «cura, sana, revierte»; «X kg en N días»; «detox», «quema grasa», «metabolismo», «cortisol»; «reset», «estable», «equilibrio», «boost»; «sin dieta ni pastillas»; zona del cuerpo + defecto; «¿Sufres de…?»; antes/después; juicios sobre el valor, cuerpo o aspecto | Aviso informativo; fuente de la tabla; alérgenos; «parar si hay dolor»; qué no incluye |
| **Relaciones** | Herramienta + N elementos + uso; mecanismo visible con vista previa; preparación propia; tercera persona genérica | Estado clínico o emocional del lector; juicios sobre su valor; diagnóstico de hijos o terceros; plazo o garantía; «haz que te ame»; «descubre si te engaña»; «narcisista»; rituales; menores; «intimidad» | «Educativo; no es terapia, diagnóstico ni asesoría legal»; 18+; ayuda del país en duelo, ruptura o relaciones dañinas; en conflicto de pareja o familia: «Si temes por tu seguridad, no uses este material» + línea de ayuda |
| **Dinero** | Herramienta con los números del comprador; método con nombre; contenido, no resultado; infinitivo; ejemplos «ilustrativos»; educación sobre estafas y contratos | Cifras de ganancia o ahorro y plazos; «sin inversión», «sin experiencia», «fácil», «rápido», «con poco esfuerzo»; nombres de método con «cero», «libre», «garantizado»; «libertad financiera», «ingresos pasivos», «sin riesgo»; «¿estás endeudado?»; verbos de acción sobre el lector; «borra tus deudas»; «oportunidad de negocio»; marcas de bancos | «No constituye asesoramiento financiero, de inversión, fiscal ni legal»; «cifras ilustrativas»; resultados no garantizados; reembolso, entrega e identidad del vendedor; pago único |

Los avisos delimitan el alcance y **no corrigen un claim**. Un término de riesgo (depresión, ansiedad, TDAH, infidelidad, abuso, deuda, diabetes) como núcleo del nombre del producto en tercera persona o infinitivo es admisible; lo que se bloquea es la **construcción**: con «tú» o posesivo, en pregunta, o con verbo de cura o de plazo. Mientras no haya historial limpio, el titular de un amarillo prefiere el sinónimo neutro («pagos pendientes»). Las 11 enfermedades nunca aparecen (política propia, más estricta que Meta).

## 4. Avisos y bloque de ayuda dentro del anuncio

El aviso corto va en `descripcion` o al pie del estático/video (según el espacio), en el idioma, con la redacción del glosario `[PENDIENTE: glosario]`. Si no cabe sin ocultar el hook, va en la landing (que D5 ya trae) y el anuncio **no** lleva la frase que lo exigiría (p. ej. una cifra «ilustrativa» sin rótulo en el mismo cuadro no se publica). El bloque «si necesitas ayuda ahora» se usa solo con números de `ayuda_por_pais.yaml` verificados `[PENDIENTE: X1]`; sin ellos, un amarillo-b no avanza.

## 5. Fuentes de inspiración y anti-copia

1. **Ficha de formato**, no activo: estructura, ritmo, tipo de hook, ángulo, duración, formato dominante. Ningún clip, imagen, texto, voz, música ni testimonio ajeno entra en un anuncio.
2. **≥3 fuentes por concepto**, de ≥2 tipos: competidor directo (de `anuncios_competencia.json` de D2: D6 no consulta la Biblioteca de Anuncios), competidor indirecto u orgánico en el idioma, voz del cliente. El banco de hooks de X2 solo cuenta si no está vacío. Cada fuente: `{tipo, ref, ficha{estructura, ritmo, hook_tipo, angulo, duracion_s, formato}, se_toma, cambia}`.
3. La Biblioteca (que consulta D2) devuelve 8 campos (sin texto principal, gasto, conversiones, landing ni fecha de fin): no se infiere rendimiento. La cantidad de anuncios activos es un indicador bajo: cuentan conceptos únicos.
4. **Regla única de copia (D2, D6, X1):** ninguna secuencia de ≥ `compliance.ngrama_copia_palabras` palabras idénticas al corpus ni a todo texto rechazado por Meta, Stripe o X1 en cualquier oferta e idioma; la traducción de un guion ajeno es copia; hash de imágenes distinto del corpus.
5. El guion se **reescribe** desde el ángulo, con vocabulario y ejemplos locales; el orgánico se mira para descubrir qué engancha, no para reutilizar: un hook «viral» se recrea con material propio. **Ganchos de un referente modelado:** reglas de reescritura en `inmersion-y-derechos.md` §3 (se descartan los de cifras de clientes o estrellas, urgencia, resultado en un plazo y preguntas sobre la persona; se conservan tipo y ángulo con texto nuevo ligado a una palanca y a una cita del dossier, que pasa el n-grama contra todos los textos del referente y no va en primera persona atribuida); imágenes de ambiente e ilustración: `modelado-oferta/references/imagenes-kie.md`.

## 6. Reencuadres seguros (catálogo de la nota 25 §4)

Máximo **dos** intentos por candidato; cambiar solo palabras es elusión. RE-01 de la condición al método · RE-02 de la cifra a la herramienta · RE-03 del diagnóstico a la organización · RE-04 de los ingresos a la plantilla de costos · RE-05 de la cura al criterio medible · RE-06 del control del otro a la preparación propia · RE-07 del plazo del efecto al del formato («plan de 14 días») · RE-08 de la segunda persona con atributo al rol en tercera · RE-09 de la prueba inventada al producto · RE-10 del servicio al archivo · RE-11 del dato sensible al evento genérico · RE-12 de la recomendación al marco impersonal · RE-13 del menor al adulto responsable · RE-14 de la garantía de resultado al precio único · RE-15 de la vigilancia al acuerdo. **D6 no reencuadra la oferta**: si la oferta es roja, pide el reencuadre a D3/X1; sí aplica RE-02, RE-07 y RE-08 al **texto de una pieza**.

## 7. Matriz de ángulos × conciencia (cada anuncio declara una celda)

Ángulo ∈ {dolor vivido (como **situación**), resultado/uso concreto del artefacto, ahorro de tiempo (verificable: `claim_id`), facilidad de uso del archivo (no del resultado), curiosidad/mecanismo, comparación con la alternativa, objeción anticipada, regalo/hobby/relajación (manualidades)} × nivel ∈ {N1…N4}. **Excluir de entrada:** ingresos, plazos garantizados, atributos del espectador, prueba social inventada, «renta extra». Un concepto = ángulo (`angulo_id` de `oferta.angulos[]`) + nivel + hipótesis medible («el encuadre X aumenta el CTR frente al Y»). Un ángulo por anuncio.

## 8. Lo que NO se toma del corpus de creadores (las cifras son declaraciones de vendedores de cursos; confianza C)

Ingresos prometidos, antes/después, testimonios o prueba social inventados, «sin experiencia» como pilar, burlar la negativa del modelo, clips o música descargados, cloaker, varias cuentas o fan pages, claves pegadas en el chat, urgencia «dejan de entregarse tras N ventas», volumen (70–100 anuncios por semana) como arranque, «avatares IA que ni se notan».
