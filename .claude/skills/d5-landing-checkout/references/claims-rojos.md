# Qué NO se escribe: patrones rojos del marco 25 aplicados a la landing

> v0.2.0 sin pulir (alineada el 2026-11-07: PAL-16 reformulada —«sin datos inventados»—, datos reales y comparación de mercado; no promover a 1.0.0 hasta cumplir el DoD y una corrida manual del dueño).
> Destilado de `docs/_investigacion/25-marco-salud-relaciones-dinero.md` (§2 ejes P/C/E/N, §3.3 líneas rojas, §4 reencuadres, §5 ángulos y claims) y `docs/_historial/hwr-semillas/casos-frontera.yaml`. El riesgo se evalúa **por promesa, contenido, encuadre y categoría de negocio, nunca por tema**: una guía de reinserción laboral para madres o «costeo para vender manualidades» son válidas; una «cura» es rojo. El lint de este skill (`scripts/lint_copy.py`) es una red mínima; la fuente de verdad es `compliance.lint_claims` (B6) y el veto de X1. Un descargo **no corrige** un claim.

## 1. Los cuatro ejes aplicados a la página
| Eje | Qué mira en la landing | Rojo si |
|---|---|---|
| **P** promesa (producto, método, marca, nombre) | H1, subtítulo, S05, S06, S10, S11, bono, bump, CTA | el producto o el método se presentan como **causa de un cambio** en cuerpo, ánimo, dinero o deuda del lector (P2n), curan o garantizan (P3), o hay testimonio sintético, antes/después, escasez o precio ficticios |
| **C** contenido | lo que instruye el entregable | dosis, diagnóstico, kcal objetivo, ayuno prolongado, planes de seguridad ante abuso, prácticas de riesgo físico agudo, asesoría de inversión personalizada, documentos legales «listos para firmar» |
| **E** encuadre | primera pantalla (S01) y anuncio | afirma, implica o **pregunta** un atributo del lector: edad, sexo, estado familiar o civil, salud, situación financiera vulnerable, «tu ex», juicios sobre su valor. El rol va en tercera persona y sin atributo (E1) |
| **N** negocio | modelo | multinivel, reparación de crédito, corretaje, servicios que conectan personas, servicio humano, citas |

El nivel = máximo de ejes (rojo > amarillo > verde). **Un bono, un bump o un FAQ pertenecen al candidato**: si por sí solos serían rojos, todo es rojo hasta quitarlos. La aritmética la hace `python -m scripts.nivel_riesgo` (devuelve `nivel` en minúscula, `subnivel` A o B aparte —«amarillo-b» es `nivel: amarillo` con `subnivel: B`, dos o más ejes amarillos—, `ejes_codigo` y `version_tabla`); si el snapshot no trae `ejes_codigo`, se derivan de los colores `[SUPUESTO]`. El LLM no la reemplaza ni baja un nivel que el lint subió.

## 2. Patrones que el lint bloquea (todos los idiomas, multi-regla)
| Familia | Ejemplos (no exhaustivo) | Regla del lint |
|---|---|---|
| Urgencia y escasez **inventadas** | «quedan 3», «últimas plazas», «X personas viendo», cuenta regresiva (sobre todo la que se reinicia), «solo hoy» sin fecha real, «oferta termina», precio anterior sin historial de 30 días, «stock limitado». **No se bloquea** la urgencia con fecha real: «precio de lanzamiento hasta {fecha}» pinta el generador desde `checkout.precio_programado` | `D5-COPY-URGENCIA` (BLOQ); `L1-BARRA-LANZAMIENTO` |
| Salud | curar, sanar, revertir, adelgazar, «8 kg en 30 días», detox, quema grasa, «sin dieta», metabolismo, cortisol; nombres de las 11 enfermedades de la lista de curas | `D5-COPY-PROMESA-SALUD` (BLOQ) |
| Dinero | ganar dinero o una cifra, ahorro con cifra, «ingresos pasivos», «libertad financiera», «sin inversión», «sin experiencia» como resultado, retorno garantizado, «borra tus deudas» | `D5-COPY-PROMESA-DINERO` (BLOQ) |
| Relaciones | «recupera a tu ex», «hazle que te ame», «descubre si te engaña», «narcisista», plazos de efecto | `D5-COPY-PROMESA-RELACIONES` (BLOQ) |
| Garantía de resultado | «si no consigues trabajo, te devolvemos…», «reconciliación o reembolso» | `D5-COPY-GARANTIA-RESULTADO` (BLOQ) |
| Atributo o pregunta en el hero | «¿Estás endeudado?», «si eres madre…», «tu ex», «inútil», edad numérica | `D5-COPY-HERO-PREGUNTA`, `D5-COPY-HERO-ATRIBUTO` (BLOQ) |
| Prueba social inventada | testimonios, estrellas, valoración, «clientes satisfechos», «+N alumnos», contador, cifras de ventas o clientes, reseñas sin `compra_id`, avatares, capturas de chat, avisos de «compra reciente», demostraciones en un sitio de producción | `D5-COPY-RESENA-SIN-COMPRA`, `D5-COPY-ESTRELLAS` (BLOQ), `D5-COPY-TESTIMONIO` (MAYOR); `L1-DEMO`, `L1-PRUEBA-SOCIAL`, `L1-RESENA` (BLOQ) |
| Ancla inflada | precio tachado, «de 146 € a 12,90 €» (suma de «valores» de bonus), «valor real» sin historial; **sí se admite** la comparación con el mercado con fuente y fecha por cifra (S16) | `D5-COPY-IMPORTE` (BLOQ), `D5-COPY-COMPARACION-SIN-FUENTE` (BLOQ); `L1-PRECIO`, `L1-COMPARACION` |
| Autoridad inventada | certificado, avalado, «recomendado por», médico, psicólogo, abogado, experto | `D5-COPY-CREDENCIAL` (MAYOR; revisión de X1) |
| Fiscal | «IVA incluido» o «+ IVA» con régimen diferido | `D5-COPY-IVA-INCLUIDO` (MAYOR) |
| Sellos de maqueta | `EJEMPLO`, «TESTIMONIOS DE EJEMPLO» | `D5-COPY-EJEMPLO` (BLOQ) |
| Bump y casillas | premarcados | `D5-COPY-BUMP-PREMARCADO`, `D5-COPY-CASILLA-PREMARCADA` (BLOQ) |
| UE/UK | falta la casilla de renuncia o el enlace a `/desistimiento` | `D5-COPY-RENUNCIA`, `D5-COPY-DESISTIMIENTO` (BLOQ) |
| Seguridad personal | producto de conflicto de pareja o familia sin aviso de seguridad y ayuda; amarillo-b sin «Si necesitas ayuda ahora» | `D5-COPY-AVISO-SEGURIDAD`, `D5-COPY-AYUDA` (BLOQ) |
| Datos públicos | `<title>`, `og:*`, `alt`, rutas con términos sensibles | `D5-COPY-DATO-SENSIBLE` (BLOQ) |

Tampoco se escribe (los revisa el QA, no el lint): comunidad, soporte personalizado, mentorías, clases en vivo, certificados, suscripciones o pruebas con cobro posterior, rituales o esoterismo de resultado, contenido sexual, menores como destinatarios o su imagen, logos o marcas de bancos o de terceros, referencia a «datos de salud» del comprador, y cualquier afirmación sobre la situación personal del espectador.

## 2b. PAL-16 reformulada: «sin datos inventados» (F-51), no «sin palancas de conversión»

La regla anterior ("quitar lo vetado") era demasiado ancha: quitaba también palancas de conversión legítimas. Lo vetado es el **dato inventado mostrado al comprador** (engaña, y X1 y Meta/Stripe lo castigan); la palanca en sí tiene una versión legítima con dato real, y sin el dato se omite. Decisión del dueño (J8 y nota de J19, 2026-11-07): no se construyen testimonios, reseñas, cifras de alumnos, avisos de compra ni urgencias inventados, aunque él «corra el riesgo de baneo»; sí se construye todo lo que se alimenta de datos reales.

| Palanca | Inventada (veto) | Legítima (única fuente) | Sin el dato |
|---|---|---|---|
| Urgencia | «solo hoy» con la fecha de hoy, cuenta atrás que se reinicia por sesión, «quedan N», «N personas viendo» | «precio de lanzamiento hasta {fecha}» con `checkout.precio_programado` real (Black Friday 27/11/2026, Cyber Monday 30/11, propósitos de enero), `Price` programado creado en Stripe, precio de después mayor | barra informativa |
| Ancla de precio | precio tachado inventado, suma de «valores», «de 146 € a 12,90 €» | comparación con el mercado (S16): precios reales de terceros de la misma categoría con `fuente` y `fecha`; el precio de después de `precio_programado`; un precio anterior solo si se cobró de verdad ≥ 30 días (el generador no lo construye) | fila omitida |
| Prueba social | «+3.482 alumnos», 4,9/5, reseñas en captura sin texto, nombres falsos, toast de «compra reciente», testimonios hechos con IA | pastilla de valoración y contador desde `prueba_social_real.json` (con `fuente` y fecha, total ≥ 1); reseñas de texto con `compra_id` y permiso; las primeras llegan con las ventas del propio test (sin beta previa) | omitidos; S08 `honesta` |
| Garantía | «sin preguntas» sin procedimiento, atada a un resultado | garantía incondicional con procedimiento (cómo y a dónde escribir) | — |
| Demostración | opiniones de ejemplo en el sitio | `--vista-previa` con cinta «DEMO», solo para que el dueño vea el diseño; `L1-DEMO` la bloquea y producción la rechaza | no existe en producción |

**Comparación con el mercado, reglas de juego limpio (F-64, F-65):** misma categoría que el producto comparado (no un curso en vídeo frente a un PDF sin decirlo), fuente verificable y fecha de LECTURA por cifra (no la del dossier), vigencia ≤ 30 días `[HIPÓTESIS]`, rango que no mezcle precio de venta y de portada, y la cifra como entero en unidad menor (nunca dentro de un texto). Si no se pudo releer, `[VERIFICAR]` y no sale a producción. El juicio de «es justa» es del QA y de X1; ningún código lo comprueba hoy.

**Falsas alarmas que se ven en la práctica (no las evadas: reescribe).** `D5-COPY-TESTIMONIO` (MAYOR) salta con una frase honesta que nombre las opiniones («aparecerán cuando sean reales», F-63): se redacta sin la palabra. «zwrot pieniędzy» (reembolso) lo marca ROJO el control de X1 como garantía absoluta (F-52): en la práctica se usó «zwrot płatności». «według» contiene `dlug` una vez quitados los diacríticos (F-43): reformula el `alt`. Estas calibraciones son de X1/S-B; mientras no lleguen, el Maker evita la frase y lo anota; **nunca** cambia solo palabras para esquivar un claim real (LM-08).


## 3. «Siempre incluir» por macro-nicho
| Macro | Siempre |
|---|---|
| Salud | aviso informativo; fuente de la tabla; alérgenos si hay recetas; «parar si hay dolor»; qué no incluye |
| Relaciones | «educativo; no es terapia, diagnóstico ni asesoría legal»; 18+; ayuda del país en duelo, ruptura o relaciones dañinas; en conflicto de pareja o familia (también verde): «Si temes por tu seguridad, no uses este material» + línea de ayuda |
| Dinero | «no constituye asesoramiento financiero, de inversión, fiscal ni legal»; «cifras ilustrativas»; resultados no garantizados; reembolso, entrega e identidad del vendedor; pago único |
| Habilidades y hobbies (4.º nicho, J6/J9) | aviso informativo; **sin promesa de ingresos ni de salud**; qué no incluye; los avisos finos (p. ej. riesgo físico en deportes u oficios) los fija X1, que debe cubrir el 4.º nicho antes de gastar `[SUPUESTO]` |

**Cifras ilustrativas (P2s):** solo si la cifra es salida de una cuenta que el lector reproduce en menos de 5 minutos con supuestos visibles, describe **el documento** (sujeto: el plan, la tabla; verbo descriptivo, nunca segunda persona ni futuro), si viene de fuera consta con fuente y fecha, y lleva el rótulo «ilustrativo» **en el mismo bloque** (it *illustrativo*, pl *ilustracyjnie*, ro *ilustrativ*, fr *à titre d'exemple*, de *beispielhaft*). Nunca para peso, salud ni ingresos ganados. «Risparmia 1.378 € in un anno» es P2n.

## 4. Pares «rechazable → aprobable» (marco 25 §5.2; [SUPUESTO], ninguno probado ante Meta)
| Idioma | Rechazable | Aprobable |
|---|---|---|
| es | «¿Tenés diabetes? Estas recetas bajan tu glucosa» | «Recetario con tabla de azúcar añadida y fibra por porción» |
| es | «Recupera a tu ex en 7 días o te devolvemos el dinero» | «10 preguntas para ordenar tus ideas antes de decidir si escribir a un ex» |
| es | «¿Estás endeudado? Salí en 90 días» | «Método de 4 pasos para ordenar pagos pendientes en una hoja» |
| en | «Lose 15 lbs in 2 weeks» | «Weekly meal-prep planner with grocery lists» |
| it | *Perdi 8 kg in 30 giorni senza dieta* | *Planner settimanale dei pasti* |
| pl | *Odzyskaj byłego w 7 dni* | *Arkusz 10 pytań przed decyzją* |
| fr | *Vous êtes surendetté ? Sortez-en en 90 jours* | *Méthode en 4 étapes pour ordonner des échéances de paiement* |
| de | *Steuern sparen durch Absetzen* | *Fristenkalender und Belegordner* |

Un término de riesgo (depresión, ansiedad, TDAH, infidelidad, abuso, deuda, diabetes) **solo** se bloquea con «tú» o posesivo, con pregunta o con verbo de cura o de plazo; como núcleo del nombre del producto en tercera persona o infinitivo se admite, pero mientras no haya historial limpio el titular prefiere el sinónimo neutro («pagos pendientes»).

## 5. Reencuadres seguros (RE-01…RE-15, resumen)
De la condición al método · de la cifra a la herramienta · del diagnóstico a la organización · de los ingresos a la plantilla de costos · de la cura al criterio medible · del control del otro a la preparación propia · del plazo del efecto al del formato · de la segunda persona con atributo al rol en tercera · de la prueba inventada al producto (vista previa) · del servicio al archivo · del dato sensible al evento genérico · de la recomendación al marco impersonal · del menor al adulto responsable · de la garantía de resultado al precio único con garantía incondicional · de la vigilancia al acuerdo. D5 solo **sube** el nivel por su cuenta; para **bajarlo** aplica un reencuadre verificable y X1 lo aprueba (desde rojo o amarillo-b). Máximo dos intentos; cambiar solo palabras es elusión (LM-08).
