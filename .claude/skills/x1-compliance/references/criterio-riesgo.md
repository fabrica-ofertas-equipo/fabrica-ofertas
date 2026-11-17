# Criterio de riesgo: por PROMESA, CONTENIDO, ENCUADRE y MODELO DE NEGOCIO, nunca por tema

Fuente única: `docs/_investigacion/25-marco-salud-relaciones-dinero.md` §1, §2, §4, §5 (y la suite `docs/_historial/hwr-semillas/casos-frontera.yaml`). Si esta página y la nota 25 chocan, manda la nota 25. Decisión 13 del dueño: **ningún tema se excluye por sí mismo**; se excluyen promesas, contenidos y modelos de negocio (las 30 líneas rojas, `lineas-rojas.md`) y se prefiere el **reencuadre seguro** al bloqueo.

## 0. La regla en una frase

> Una «cura» es rojo. Una guía de reinserción laboral para madres es verde. «Ganar dinero con manualidades» es verde si no promete ingresos. El tema (embarazo, deuda, duelo, peso, ganar dinero) **nunca** sube el nivel por sí solo: lo suben la **promesa**, el **contenido**, el **encuadre** y el **modelo de negocio**.

Un filtro por tema (la suite lo mide: 71 legítimos bloqueados y 79 peligrosos que pasan) es el error que X1 existe para no cometer. Antes de dar un nivel, escribe qué **afirma**, qué **instruye**, a **quién le habla** y **cómo se cobra**.

## 1. Orden de evaluación (síguelo siempre)

1. **Macro-nicho por el deseo central** (nota 25 §1.2, lo hace D1; X1 lo comprueba). ¿El comprador dice «funcionó» cuando cambia (S) un estado de su **propio cuerpo o ánimo**, (R) un **vínculo con personas concretas** o (D) algo **medido en dinero**? Si ninguna bandera es sí → `fuera_de_macro_nicho` (bloquea **antes** de calcular riesgo; sin nivel). Se registran las tres banderas; los lints de contenido, ayuda y datos se activan **por cualquier bandera**, no solo por el macro primario.
2. **Unidad evaluada = (candidato, pieza, mercado).** El candidato fija P, C y N; cada pieza (anuncio, creativo, landing, checkout, bump, bono, correo, bot, URL, evento, descriptor, marca) fija E y puede agravar P. **El nivel es el máximo entre activos**: un producto verde con una reseña «ahorré 3.000 €» es rojo. Un bono, un bump o una respuesta automática pertenecen al candidato. Un rojo de pieza bloquea la pieza (X1 veta su hash), no la oferta.
3. **Cadena que se evalúa para P y E:** nombre del producto, del método y de la marca; nombre de la Página y dominio; título, meta-descripción, Open Graph y texto alternativo; texto dentro de imágenes y fotogramas (OCR); audio y subtítulos; ítem del recibo, asunto y remitente de correos. Un atributo o un resultado en cualquiera de ellas vale para todas las piezas que la muestren.
4. **Ejes → colores → nivel** con `python -m scripts.nivel_riesgo --P … --C … --E … --N … [--reencuadre] --json` (la única implementación; `dependencias.md` D-01 resuelto). Devuelve `nivel` en minúscula (`verde|amarillo|rojo`; `null` fuera de macro-nicho), `subnivel` aparte (`A|B|null`), `colores`, `veredicto_riesgo` y, con `riesgo_de_candidato`, `ejes_codigo` y `version_tabla`. **El LLM asigna los códigos de eje; el script calcula el nivel. Nunca escribas «nivel: verde» sin haber corrido el script.** Escritura canónica del nivel que puede lanzarse (`contratos/comunes#nivel_lanzable`): `verde`, `amarillo-a`, `amarillo-b` **en minúsculas con guion**; el campo `subnivel` es otro (`A|B`) y no usa ese enum.
5. **Veredicto de riesgo** (`pasa`, `pasa_con_revision`, `pasa_con_gate`, `reformular`, `bloquea`) y, si es rojo, el **reencuadre** (§4) o la razón de que no exista.

## 2. Los cuatro ejes (códigos y anclas)

| Eje | Código → color | Cómo se decide |
|---|---|---|
| **P · Promesa** (qué afirman anuncio, landing y nombre) | P0, P1 verde · P2s amarillo · P2n, P3 rojo | P0: el sujeto es el archivo, plan, tabla o calendario. P1: beneficio de uso con **verbos de la herramienta** (registra, ordena, calcula, planifica, recuerda, compara); «fácil de usar» aplicado al archivo sigue en P1. **P2s:** cifra reproducible por el lector con supuestos visibles y rótulo «ilustrativo» (las 5 condiciones de la nota 25 §2.5; nunca peso, salud, ingresos ganados ni estados de otra persona). **P2n:** el producto, método, marca o pieza atribuye al lector un resultado futuro **con o sin cifra y con o sin plazo**: verbos de cambio con el lector como beneficiario (baja, alivia, calma, equilibra, reinicia, limpia, elimina, multiplica), nombres de estado («Cero Deudas», «Glucosa Estable», «Sleep Reset»), facilidad sobre el resultado («sin experiencia», «sin inversión»), rendimiento pasado como expectativa, reseñas con cifras. **P3:** cura o diagnóstico; ingreso garantizado; control de un tercero; testimonio sintético, antes/después, escasez o precio ficticios; claim fisiológico; camuflaje anuncio-producto. Un descargo **nunca** baja P. |
| **C · Contenido** (qué instruye, qué daño podría causar) | C0, C1 verde · C2 amarillo · C3 rojo | C0: plantillas en blanco, calendarios, listas. C1: método o guion con ejemplo, recetas con tabla pública, anti-estafas. C2: progresión de carga con riesgo de lesión, seguridad alimentaria con cifras, plazos legales y cálculo con tasas, lectura de contratos, guion sobre ruptura/duelo/separación con hijos, método de pago de deuda propia, registro de medicación indicada por el médico, población vulnerable. C3: dosis, diagnóstico, tratamiento, kcal objetivo, ayuno prolongado, planes de seguridad, vigilancia, recomendar instrumentos, documentos legales personalizados, dieta/ejercicio/suplementos **prescritos** a menores, embarazo, lactancia; prácticas de riesgo físico agudo; en Alemania, ayuda fiscal personalizada. **Un tema vigilado cuenta una sola vez, en C.** |
| **E · Encuadre** (cómo se dirige al espectador) | E0, E1 verde · E2, E3 rojo | E0: habla del producto. E1: rol, ocupación o tema en **tercera persona**, sin «tú» + atributo y sin pregunta («freelancers», «cuidadores», «quien vuelve a trabajar tras una pausa»). **E2:** afirma, implica o **pregunta** un atributo del lector (edad numérica, sexo, estado familiar o civil, salud física o mental, situación financiera vulnerable, «tu ex», juicios sobre el propio valor o cuerpo). E3: menores como destinatarios o imagen. **Prueba del espectador ajeno:** la frase debe ser verdadera y neutra para cualquiera que la lea; si solo tiene sentido para quien padece X, afirma X (E2). |
| **N · Negocio** (Meta, Stripe, leyes de consumo, salud y finanzas) | N0, N1 verde · N1s amarillo · N2, N3 rojo | N0 solo existe fuera de macro (todo candidato en macro es al menos N1). N1: nutrición y fitness generales, hábitos, pareja, crianza, presupuesto, empleo, impuestos y deuda propia. **N1s es por FUNCIÓN, no por tema:** el entregable mide o registra el cuerpo del comprador (peso, IMC, medidas, kcal) o el comprador carga datos sensibles suyos en un formulario, quiz, calculadora web o cuenta. N2: exige autorización o conecta personas (citas, telemedicina, inversión, crédito, hipotecas, afiliado financiero, servicio humano, bolsa de empleo con colocación, reventa de trámites oficiales). N3: multinivel, get-rich-quick, CFD, reparación de crédito, consejería de deuda, contenido sexual. |

**Tabla ejes → nivel** (la implementa `scripts/nivel_riesgo.py`): ROJO si P ∈ {P2n,P3} o C = C3 o E ∈ {E2,E3} o N ∈ {N2,N3}; AMARILLO si P = P2s o C = C2 o N = N1s (**B** si dos o más de esos tres; **A** si uno); VERDE en otro caso. Veredictos: verde `pasa`; amarillo-a `pasa_con_revision` (`pasa_con_gate` si es una zona gris cerrada por el dueño); amarillo-b `pasa_con_gate`; rojo `reformular` si existe un reencuadre que conserva el deseo y baja a ≤ amarillo, si no `bloquea`.

## 3. Qué exige cada nivel (sin abogado: decisión 14)

| | VERDE | amarillo-a | amarillo-b | ROJO |
|---|---|---|---|---|
| Revisión | lint L1 y muestreo (`x1_muestreo_verdes`, pendiente de MINOR) | **RHS** (revisión humana de seguridad, 30-60 min, una persona recorre la lista L3; no acredita exactitud clínica) solo en el **primer lanzamiento de cada hoja × idioma** o con bandera abierta | igual que A **más** cada hecho en `afirmaciones.jsonl` con **texto fiel a la fuente T1 verificado por script** y **decisión H del dueño** que registra el riesgo residual aceptado | abstención |
| Aviso y ayuda | aviso de alcance; en todo producto de conflicto de pareja o familia (también verde): «Si temes por tu seguridad, no uses este material» + línea de ayuda del país (J02) | aviso por tipo de producto | aviso reforzado + «Si necesitas ayuda ahora» con números de `ayuda_por_pais.yaml` | no corrige un claim |
| Cuota | sin tope | `cuota_gasto_amarillo_*`, `envios_amarillo_*` de limites (pendientes de MINOR) | cuotas más estrictas; pausa del ángulo al primer rechazo | no se lanza |

**Sustitución de la revisión legal.** Donde la nota 25 pide «revisión profesional» o «abogado» (amarillo-b, `mercado_gate`), **no** se agenda a un profesional: se aplica (a) el chequeo automático de X1 (lints, `html_checks`, hechos con fuente), (b) la plantilla generada por el sistema y (c) el **gate H del dueño** con registro en `empresa/decisiones_dueno.jsonl`. Lo fiscal sigue con el contador (`templates/dossier.md`).

## 4. Reencuadre seguro (el reflejo correcto ante un rojo)

Validez: (1) conserva problema y deseo central; (2) el nivel baja a ≤ amarillo; (3) mantiene coherencia anuncio = landing = producto = descriptor. **Máximo dos intentos por candidato.** Cambiar solo palabras es **elusión (LM-08)** y registra el rechazo por **claim**, no por oferta. `deseo_conservado = total` (el comprador reconocería la misma métrica de éxito) o `parcial` (vale **solo** si D1 aporta una cita E3 de que el B reencuadrado también se busca; si no, `bloquea` y lo adyacente es **otro** candidato).

| Id | De → A | Ejemplo |
|---|---|---|
| RE-01 | condición → método | «Bajá tu glucosa» → recetario con tabla de azúcar añadida y fibra por porción |
| RE-02 | cifra → herramienta | «Perdé 8 kg en 30 días» → planificador semanal de comidas con lista de compras |
| RE-03 | diagnóstico → organización | quiz de ansiedad → registro para la consulta |
| RE-04 | ingresos → plantilla de costos | «Ganá USD 500 con velas» → costeo por gramo de cera |
| RE-05 | cura → criterio medible | «Antiinflamatoria» → legumbres con fibra por porción |
| RE-06 | control del otro → preparación propia | «Recupera a tu ex en 7 días» → 10 preguntas antes de decidir |
| RE-07 | plazo del efecto → plazo del formato | «Dormí en 7 días» → planificador nocturno de 14 días |
| RE-08 | 2.ª persona con atributo → rol en 3.ª | «Madres solteras» → planificador del hogar; «madres que vuelven…» → «volver al trabajo tras una pausa» |
| RE-09 | prueba inventada → producto | antes/después → vista previa del PDF; «ahorré 3.000 €» → reseñas verificadas sin cifras |
| RE-10 | servicio → archivo | consulta por mensaje → PDF sin seguimiento |
| RE-11 | dato sensible → evento genérico | `diabetes_menu` → `view_content` |
| RE-12 | recomendación → marco impersonal | «Invertí en estas 5 acciones» → glosario; tres tasas rotuladas |
| RE-13 | menor → adulto responsable | guía para adolescentes → guion para el adulto |
| RE-14 | garantía de resultado → precio único | «Ahorrás o te devolvemos» → 14 días incondicionales |
| RE-15 | vigilancia → acuerdo | «Revisá su celular» → acuerdo de privacidad entre los dos |

**Sin reencuadre** (se bloquea y se abre otro candidato): curar una enfermedad, ingreso pasivo, reconquista garantizada, dosis, plan de salida de un abuso, trading, adicciones, dieta infantil, contenido sexual.

**Por idioma:** polaco sin «cud», «leczy» ni plazos «w 7 dni»; alemán: «gegen» + dolencia es eficacia terapéutica (HWG §3) y «Kurs mit Betreuung» invita a FernUSG; italiano: «senza dieta» y los plazos son el patrón que sancionó la AGCM; rumano sin propiedades de prevención ni curación; francés sin lenguaje terapéutico; español: el RD 1907/1996 aplica con «pretendida finalidad sanitaria» (J04). [VERIFICAR cada una contra su fuente; nota 25 §4].

## 5. Patrones seguros, «nunca decir» y «siempre incluir» (nota 25 §5.1)

| | Patrones seguros | Nunca decir (L1 bloquea; X1 veta) | Siempre incluir |
|---|---|---|---|
| Salud | el producto, no el cuerpo; contenido contable («60 recetas con tabla por porción»); formato | «cura, sana, revierte»; «X kg en N días»; «detox», «quema grasa», «metabolismo», «cortisol»; nombres con «reset», «estable», «equilibrio», «boost»; «¿Sufrís de…?»; antes/después; juicios sobre el cuerpo o valor del lector | aviso informativo; fuente de la tabla; alérgenos; «parar si hay dolor»; qué no incluye |
| Relaciones | herramienta + N elementos + uso; preparación propia; tercera persona genérica | estado clínico o emocional del lector; diagnóstico de hijos o terceros; plazo o garantía; «hacé que te ame»; «descubrí si te engaña»; imagen de menores | «Educativo; no es terapia, diagnóstico ni asesoría legal»; 18+; ayuda del país; el aviso de seguridad en todo conflicto de pareja o familia |
| Dinero | herramienta con los números del comprador; método con nombre neutro; infinitivo; ejemplos «ilustrativos»; educación sobre estafas y contratos | cifras de ganancia o ahorro y plazos; «sin inversión», «sin experiencia», «fácil», «rápido»; «cero», «libre», «garantizado» en nombres; «libertad financiera», «ingresos pasivos»; «¿estás endeudado?»; marcas de bancos | «No constituye asesoramiento financiero, de inversión, fiscal ni legal»; «cifras ilustrativas»; resultados no garantizados; reembolso, entrega e identidad del vendedor |

Los avisos delimitan el alcance y **no corrigen un claim**. **El lint bloquea la construcción, no la palabra:** un término de riesgo (depresión, deuda, diabetes, ansiedad, TDAH, infidelidad…) con «tú»/posesivo, con pregunta o con verbo de cura o de plazo es rojo; como núcleo del nombre en tercera persona o infinitivo («planificador de pagos de deudas», «diario para llevar a la consulta») se permite porque Meta lo permite.

## 6. Quién puede subir o bajar un nivel

D1 propone; D3/D4/D5/D6 re-verifican su activo y **pueden subir** sin permiso; solo **bajan** aplicando un reencuadre verificable. **X1** veta, aprueba toda bajada desde rojo o desde amarillo-b y puede subir cualquier nivel. **Un LLM no baja un nivel que el lint subió.** El overlay de mercado solo sube. El dueño decide líneas rojas y tolerancia, **no el nivel de un candidato**; reclasifica una **regla**, no un caso; todo override va a la bitácora encadenada.

## 7. Errores típicos (los que la suite mide)

| Error | Síntoma | Corrección |
|---|---|---|
| **Sobre-bloqueo** | sube a rojo por «embarazo», «madres», «deuda», «prestiti», «duelo», «comida sana» | volver a los cuatro ejes: ¿qué promete, qué instruye, a quién le habla, cómo se cobra? Si ningún eje es rojo, no es rojo |
| **Falso verde** | pasa «Perdé 8 kg» (voseo), «Ganá USD 500», «Cero Deudas», «¿Estás endeudado?», «Quedan 7 cupos», «Ahorré 3.200 USD» | P2n/P3 con o sin cifra, nombre de estado, atributo en pregunta, escasez ficticia, testimonio con cifra |
| **Confiar en el linter** | «el lint dio verde» | el lint es una **condición necesaria**; cubre es-ES, es-AR, es-MX, en-US, it-IT, pl-PL, ro-RO, fr-FR y de-DE (`[HIPÓTESIS]`, sin revisor nativo en it/pl/ro/fr/de) pero deja pasar parte de las paráfrasis (79 de 86 del corpus; `dependencias.md` D-02): el QA (L2/L3) es la segunda red |
| **Reencuadre cosmético** | cambia «bajá» por «reducí» | elusión LM-08: no se reenvía |
| **Asignar el nivel a ojo** | escribe «verde» sin script | correr `python -m scripts.nivel_riesgo` y citar su salida |
| **Atribuir a Meta lo que es prudencia propia** | «Meta prohíbe X» sin texto oficial | separar norma / política oficial / prudencia propia (R6) |
