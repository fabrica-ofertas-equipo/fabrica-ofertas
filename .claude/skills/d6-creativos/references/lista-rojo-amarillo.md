# Lista de ROJO y AMARILLO para el texto de los anuncios (guía de revisión a mano)

Destilada de `docs/_investigacion/05-legal.md` §10 (español), de la nota 25 §5.1, §10.3 (checks `X1-P01…`, `E01`, `M01–M03`, semillas por idioma) y de `docs/_historial/hwr-semillas/casos-frontera.yaml` (ruta definitiva **[PENDIENTE]**). **Es una ayuda para el Maker y el QA, no el lint oficial**: las listas oficiales por idioma viven (o vivirán) en `empresa/compliance/terminos_sensibles/<locale>.yaml` **[PENDIENTE: X1]** y el lint determinista en `compliance/reglas_sensibles.yaml`, que hoy cubre `es-ES` y `en-US` (salud y finanzas) y unas pocas reglas generales (urgencia falsa, garantías absolutas, prueba social fabricada). **Para `it-IT`, `pl-PL`, `ro-RO`, `fr-FR`, `de-DE`, relaciones y los patrones de las tablas de abajo, el lint falla cerrado o no cubre: se revisa a mano y se anota.** Lo que no está en esta lista no es «verde»: se aplica la prueba del espectador ajeno y se escala a X1 ante la duda.

Semáforo: **ROJO** = 0 permitido (bloquea; X1 veta); **AMARILLO** = solo con evidencia, aviso y decisión humana o X1; **VERDE** = el resto.

## 1. Patrones por categoría (cualquier idioma; ejemplos en español)

| Categoría | ROJO | AMARILLO | Alternativa segura |
|---|---|---|---|
| Ingresos / ahorro / retorno (X1-P01/P02, LP-03) | Cifra, plazo o promesa de ganar, ahorrar o devolver dinero («ganá 3.000 al mes», «ahorrá 1.378 € en un año», «facturá 10K»); «pasivo», «dinero mientras dormís», «libertad financiera», «dejá tu empleo y vivite de esto» | Cifra reproducible con supuestos visibles y «ilustrativo» **en el mismo cuadro o audio**, con la tabla como sujeto (P2s) | «Hoja de costeo: costo, precio mínimo y margen» |
| Plazo de **resultado** | «en 7 días», «en 30 días», «en 24 horas» sobre un cambio en el lector | Plazo del **formato** con sujeto el producto («plan de 14 días», «52 semanas», «se lee en 20 minutos» con `claim_id`) | «Plan de 14 días» |
| Garantía | «resultados garantizados», «100 % garantizado», «garantizamos entrevistas/clientes», garantía atada a un resultado | «Garantía de devolución de 14 días» (sin letra chica, con `claim_id`) | «Si no te sirve, pides el reembolso en 14 días» |
| Facilidad / esfuerzo (P07) | «sin experiencia», «sin inversión», «sin esfuerzo», «fácil», «rápido», «automático», «a prueba de tontos» aplicados al **resultado** | «Plantilla lista para completar» (acotado al artefacto) | «Plantilla lista para completar» |
| Salud (LP-01/02/07) | Cura, sana, revierte, previene una enfermedad; las 11 de la lista de curas en el anuncio; kilos, ritmo o plazo de peso; «detox», «quema grasa», «metabolismo», «cortisol»; «reset», «estable», «equilibrio», «boost» en el nombre; claims fisiológicos | Seguridad alimentaria con cifras (C2) con fuente T1 | «Recetario con tabla de azúcar añadida y fibra por porción» |
| Atributo del espectador (E01, LP-06) | «Si estás endeudado…», «¿Sufres de ansiedad?», «madre soltera», «mamás agotadas», «tu hijo con TDAH», «tu ex», edad numérica, **también en pregunta** | Rol en tercera persona sin atributo («quien vuelve a trabajar tras una pausa»; E1) | Beneficio del producto sin atributo |
| Autopercepción negativa (E01) | «inútil», «insuficiente», «fracasada», «vergüenza», «deja de sentirte…», «gorda» | — | Hablar de la tarea, no de la persona |
| Escasez / urgencia (P05) | «quedan 3 cupos», «solo hoy», «últimas plazas», contadores que se reinician, precio tachado inventado | Cierre real programado verificable por código | Sin urgencia o fecha real |
| Prueba social (P04, P08) | «+10.000 compradores», «miles de personas ya…», estrellas escritas a mano, reseñas sin `compra_id`, testimonios de transformación, avatar «yo gané/bajé/uso» | Reseña real con `compra_id` y sin cifras de resultado (D10) | Ninguna cifra |
| Autoridad falsa (LP-08) | «aprobado por Meta/Google/Stripe», «recomendado por [famoso]», logos de medios, aval médico o financiero aparente | «Usamos herramientas de [marca]» solo descriptivo | Omitir |
| Antes/después y transformación (P04b, M03) | Antes/después de peso, cuerpo, ingresos; «día 1 vs. día 21»; báscula, cinta métrica, píldoras, glucómetro, pilas de efectivo en un fotograma | «Hoja en blanco» frente a «hoja completa» del mismo entregable | Producto, hojas o manos |
| Relaciones (LP-04, LC-04/05) | «recupera a tu ex en 7 días», «descubre si te engaña», «haz que te ame», rituales, vigilancia, plan de salida de un abuso, «narcisista» como diagnóstico | Guion de límites con aviso de seguridad (amarillo-a) | «10 preguntas para ordenar tus ideas antes de decidir si escribir a un ex» |
| Menores (E03, LM-07) | Menores en imagen o como destinatarios | — | Manos adultas, objetos |
| Marcas / celebridades | «estilo Chanel», logos, nombres de famosos, voz o rostro clonados | Mención nominativa descriptiva | Omitir |
| Verbo de cambio con el producto como sujeto (P07) | baja, alivia, calma, equilibra, reinicia, limpia, activa, elimina, multiplica + cuerpo, ánimo, dinero o deuda del lector; sustantivos de estado en nombre de producto, método, marca, Página o dominio | — | Verbos de la herramienta: registra, ordena, calcula, planifica, compara |
| Plataforma | «link en la bio», Instagram, métodos de pago locales | — | «Más información» / enlace del anuncio |

**No es ROJO** describir el artefacto con su `claim_id` («plan de 14 días», «plantilla lista para completar», «incluye guion de 30 segundos», «se lee en 20 minutos»). Las paráfrasis no caen por patrón: las detectan el clasificador y la simulación L3(a) del QA («revisor de políticas de Meta»).

## 2. Semillas por idioma (verbos de cambio y frases de riesgo; no exhaustivas)

| Locale | P07 verbos de cambio · estados · facilidad | Plazo/peso/ingresos | Autopercepción negativa (E01) |
|---|---|---|---|
| es | baja, alivia, calma, equilibra, reinicia, limpia, activa, elimina · estable, cero, libre, total · sin experiencia, sin inversión | «en 7 días», «X kg», «al mes» + cifra | inútil, insuficiente, fracasada, vergüenza |
| en | lowers, relieves, resets, cleanses · stable, zero, free · no experience, no investment | «in 7 days», «lose X lbs», «$X a month» | not good enough, worthless, ashamed |
| it | abbassa, allevia, riequilibra, azzera · senza esperienza · «senza dieta» y los plazos son el patrón sancionado por la AGCM | *in 30 giorni*, *Perdi 8 kg*, *Guadagna 2.000 € al mese* | inutile, insufficiente, vergogna |
| pl | obniża, łagodzi, resetuje, oczyszcza · bez doświadczenia · sin «cud» ni «leczy» ni plazos «w 7 dni» | *Schudnij 10 kg w miesiąc*, *3000 zł miesięcznie* | beznadziejna, niewystarczająca, wstyd |
| ro | scade, calmează, resetează, curăță · fără experiență · sin propiedades de prevención o curación | *Câștigă 3.000 de lei pe lună* | nepriceput, insuficient, rușine |
| fr | abaisse, soulage, réinitialise · sans expérience · sin lenguaje terapéutico | *Sortez-en en 90 jours*, *soulagez définitivement* | nulle, pas assez, honte |
| de | senkt, lindert, setzt zurück · ohne Erfahrung · «gegen» + dolencia = eficacia terapéutica (HWG §3); «Kurs mit Betreuung» invita a FernUSG | *Steuern sparen durch Absetzen* | wertlos, nicht gut genug, Scham |

Atributo del espectador por idioma (E01), ejemplos de construcción bloqueada: es «¿Estás endeudado?», en «Are you broke?», it «Sei indebitato?», pl «Jesteś zadłużony?», ro «Te înșală partenerul?», fr «Vous êtes surendetté ?», de «Sind Sie verschuldet?» (ejemplos de pares de la nota 25 §5.2).

## 3. Pares rechazable → aprobable (nota 25 §5.2; [SUPUESTO], ninguno probado ante Meta)

| Idioma | Salud | Relaciones | Dinero |
|---|---|---|---|
| es | «¿Tienes diabetes? Estas recetas bajan tu glucosa» → «Recetario con tabla de azúcar añadida y fibra por porción» | «Recupera a tu ex en 7 días» → «10 preguntas para ordenar tus ideas antes de decidir si escribir a un ex» | «¿Estás endeudado? Sal en 90 días» → «Método de 4 pasos para ordenar pagos pendientes en una hoja» |
| it | *Perdi 8 kg in 30 giorni senza dieta* → *Planner settimanale dei pasti* | *Fai in modo che si innamori di te* → *Quaderno di 20 domande per conoscersi in coppia* | *Guadagna 2.000 € al mese da casa* → *Modello Excel per costi, prezzo e margine* |
| pl | *Schudnij 10 kg w miesiąc* → *Tygodniowy planer posiłków* | *Odzyskaj byłego w 7 dni* → *Arkusz 10 pytań przed decyzją* | *Jesteś zadłużony? Pozbądź się długów w 3 miesiące* → *Metoda w 4 krokach do uporządkowania zobowiązań* |
| en | «Lose 15 lbs in 2 weeks» → «Weekly meal-prep planner with grocery lists» | «Is your partner cheating? Find out now» → «Checklist to prepare a hard conversation» | «Are you broke? Fix your finances today» → «Zero-based budget template» |

## 4. Cómo se usa

- **Antes de escribir** (paso 4): el Maker consulta la fila del idioma y del macro-nicho; escribe desde el §3.
- **Checkpoint QA-A** (paso 5): el Maker corre `scripts/lint_claims.py --archivo … --locale <locale>` (cubre es-ES y en-US parcialmente) y completa **a mano** esta lista para el resto; todo hallazgo se anota con la frase y la categoría.
- **QA**: usa estas filas para sus 7 simulaciones L3 y para `check_id` (`X1-P01`, `X1-P02`, `X1-P05`, `X1-P07`, `X1-P08`, `X1-E01`, `X1-E03`, `X1-M01`…`M03`).
- **Si un modelo se niega a generar un claim** de esta lista: se corrige el claim; no se reformula el prompt para esquivar la negativa (LM-08).
- **Al pulir:** cada frase que el dueño o X1 rechacen pasa a esta lista y a un caso de `evals/sembrados/`.
