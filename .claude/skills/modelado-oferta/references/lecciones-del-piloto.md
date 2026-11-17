# Lecciones del piloto de Polonia, traducidas a reglas

> v0.1 sin pulir. Fuente: `docs/_historial/modelado-piloto/piloto-bitacora-d3.md` (fricciones F-01…F-82, «5 mejoras» y la recomendación de convertir el modelado en skill). Corrida del 2026-11-07, oferta A «mapas mentales de vocabulario inglés para hablantes de polaco» (`ofertas/OF-202611-91`, modo práctica). Cada fila dice qué pasó, **qué regla lo absorbe** y dónde vive. Lo que depende de contratos o de código ajeno va a `PENDIENTES.md`.

## 1. Lo que cambió cómo se modela
| Fricción | Qué pasó | Regla que la absorbe | Dónde |
|---|---|---|---|
| F-40 (D3) | J18 («usar la misma oferta») chocaba con QM-03, QM-08 y R-7, que trataban parecerse como clon | La **oferta se replica y la expresión no se toca**; QM-03 mide fidelidad de estructura y distancia de expresión; QM-08 no bloquea «misma oferta» | `palancas.md` R-7; `derechos-j13.md`; `rubric.md` QM-03/08 |
| J18 (hallazgo) | La oferta del piloto (80 mapas, A1-B2, 4 bonus, 14 días) se apartaba del referente: «eso es otra oferta, no un modelado» | Paso «copiar la oferta» antes de elegir palancas; «mejora pequeña» tiene definición | `palancas.md` §1 |
| F-51 (D5) | PAL-16 era demasiado ancha: quitaba también las palancas de conversión legítimas | PAL-16 = **sin datos inventados**, con su versión legítima (barra con fecha real, comparación citada, contador y reseñas con dato real) | `palancas.md` PAL-16 |
| F-30 | El antes/después tenía una salida fácil: se excluyó justo la dimensión donde la oferta propia salía peor (precio y valor, razón 0,30) | Una dimensión excluida por R-5 no puede ser aquella donde saldríamos peor; cuenta como «peor» hasta que el dueño la acepte | `palancas.md` R-5; `rubric.md` R7 |
| Plan v1 | PAL-04 (errores típicos del hablante de polaco) cayó de 5 elegidas a hipótesis: la voz local no la respaldaba | Una palanca sin respaldo de la voz local baja a `hipotesis` (R-2: respaldo 1) | `palancas.md` PAL-04 |
| Plan v1 | La queja central era «entiendo pero no puedo hablar»; prometerlo habría sido deshonesto | La promesa es **de uso** («tener las palabras de tu nivel listas, en contexto»), nunca de resultado ni de plazo | `palancas.md` PAL-03; D3 |
| J16 | Un barrido de precio dejó 97 zł para forzar la economía (1,6 veces lo que cobra el original) | El frontal es el peldaño 17/19/27 US$ más cercano al original; **no se barre** | `palancas.md` PAL-07 |
| J19 | 520 mapas es una promesa de producción que D3 no puede costear ni comprobar | Lo anunciado = lo entregable: se declara el riesgo de producción y D4 confirma la cifra antes de publicar | D3/D4 (`PENDIENTES.md` A) |
| F-41 | Los 520 mapas, ~300 frases, 5 bonus y ~2600 fiszki salen sin revisor nativo | Las 5 capas del QA lingüístico son el mínimo; la 2.ª es débil en polaco | `inmersion-mercado.md` §6 |

## 2. Lo que cambió cómo se ve el funnel y el HTML
| Fricción | Regla | Dónde |
|---|---|---|
| D5 ronda 1 | Hay que modelar el **funnel completo**, no solo la oferta | `funnel-completo.md` |
| F-47, F-49 | El generador debía aceptar orden configurable, barra superior, CTA entre bloques y selector de niveles | Ya resuelto en el plano `referente` de D5; el modelado entrega el plano ordenado |
| F-50 | Un bloque de «comparación con el mercado» con precios reales citados se bloqueaba como importe ajeno | La comparación se publica solo con **fuente y fecha por cifra** (S16) | `palancas.md` PAL-16 |
| F-64 | Las cifras de mercado venían del dossier sin releer la fuente; el rango mezclaba precio de venta con precio de portada | Marcar `[VERIFICAR]` y releer antes de publicar; sin `capturar_fuente` no hay cifra `visto` | `inmersion-mercado.md` I-2 |
| F-48, F-75 | Sin D4 no hay muestra real: PAL-13 «muestra real» no es implementable; las miniaturas ilustrativas no son muestra | Ilustrativa rotulada hasta que D4 entregue; nunca «muestra real» en producción | `imagenes-kie.md` regla 7 |
| F-58 | No hay petición automática de reseña ni fuente de datos para contador y reseñas | Los componentes de datos reales se omiten sin dato; la canalización de reseñas reales es de D10 | `palancas.md` PAL-16 |
| J20 | El HTML del referente se analizó a mano (¿quedó algo suyo en la plantilla?) | `scripts/analizar_html.py` lo hace de forma repetible, sin ids ni código del referente | `analizar-html.md` |
| Axon (análisis manual) | `lang="pt-BR"` en una página italiana, fecha de oferta sin rellenar, alt repetidos, tipografía declarada y sin cargar | Son **descuidos del referente** y oportunidades de confianza (PAL-14); el script los detecta como alertas | `analizar-html.md` |

## 3. Lo que cambió cómo se hace el idioma
| Fricción | Regla | Dónde |
|---|---|---|
| F-23, F-44 | El lint de X1 para pl-PL deja pasar «płynnie», «w 30 dni», «sekret poliglotów», cifras de prueba social y «Zostało tylko 3» | El verde del lint no basta: el auditor de otro modelo y la cobertura cruzada son parte del mínimo | `inmersion-mercado.md` §6 |
| F-43 (D5) | El término sensible `dlug` marcó «według» (falso positivo por plegar diacríticos) | Los términos sensibles se comparan por palabra entera; si falla, se reformula sin evadir el lint | `PENDIENTES.md` B |
| F-52 | La regla `garantias_absolutas` marca ROJO «zwrot pieniędzy» (reembolso legítimo) | Se usa la fórmula neutra que el lint acepta («zwrot płatności») sin cambiar la garantía; se avisa a X1 | X1 |
| F-32 | La ficha de la oferta pide citas literales de la voz y la regla I-7 las prohíbe en material público | Se rotulan como cita de foros públicos, no como opinión de clientes | `inmersion-mercado.md` I-7 |
| F-13, F-19 | Sin captura de texto crudo no hay cita verificada; los mínimos de voz se medían por dominio y no por diversidad | Citas `parcial` = vocabulario; ≥ 3 clases de fuente y sesgo declarado | `inmersion-mercado.md` I-2, I-4 |

## 4. Lo que cambió cómo se corre en modo práctica
| Fricción | Regla | Dónde |
|---|---|---|
| F-01, F-12, F-45 (D5) | El cuarto macro-nicho (habilidades y hobbies, J6/J9) no existe en contratos, `macro.py`, X1 ni los lint | Hasta que lo cierren S-A y S-B, el piloto corre en modo práctica con el macro `[SUPUESTO]`; los validadores fallarán con ese valor y es esperado. No se disfraza de otro macro en el artefacto real | `PENDIENTES.md` D |
| F-07, F-42 | Copiar `ofertas/_ejemplo/` arrastra etapas ajenas; `validar_esquemas oferta` valida todo lo presente | Validar por etapa en una copia con solo `00-brief`, `mercado`, `limites`, 01, 02 y 03 | `PENDIENTES.md` B |
| F-11, F-14 | El par que eligió el dueño no pasa el L1 de D1 (PM nulo, sin `ads_library_search` en el snapshot) | Vía «oferta elegida por el dueño con par incompleto» marcada `provisional`; **no se inventa** el dato | `PENDIENTES.md` D |
| F-15 | La bandera `viabilidad_cpa` roja no frenaba nada hasta D3 | Aviso al dueño en el informe de D1 cuando la bandera es roja | `PENDIENTES.md` A |
| F-26, F-39 | El motor diseña el test estadístico viejo y entrega un veredicto, no el «CPA máximo a pagar» del test de 1 día (J3) | El umbral del test es el `cpa_be` del motor; **la parada por NO_FACTIBLE es de D3**, no de esta skill | `PENDIENTES.md` B |
| F-17, F-18 | D2: dos rutas para el veredicto; el piso de «sostenido» no está definido para una oferta que se replica | Fuera de alcance: se anota, no se esquiva | `PENDIENTES.md` D |
| F-56, F-62 | Los generadores asumen rutas fijas | Para pruebas, una raíz de trabajo en el scratchpad; nunca se tocan carpetas ajenas | — |

## 5. Lo que cambió cómo se hacen las imágenes
Ver `imagenes-kie.md` §5: composición por código para texto pequeño (F-77), boceto de composición (F-78), tope por créditos medidos y no por estimados (F-68), clave compartida (F-69, F-82), texto en imagen solo desde referencia plana propia y con OCR verde (F-70), etiqueta de IA visible (F-81), OCR con Vision de macOS como motor real (F-73), tipografía de las portadas distinta de la de la web hasta subir los `.woff2` (F-74).

## 6. Las cinco mejoras del piloto, ya incorporadas o pedidas
1. **Modo práctica verdadero** para D1/M1/D2/D3: plantilla mínima de oferta, límites de prueba, vía del par incompleto y validación por etapa → `PENDIENTES.md` B y D.
2. **Cerrar el 4.º macro-nicho** de punta a punta y hacer ejecutable J11 → `PENDIENTES.md` D.
3. **Llevar la economía al principio** (D1 con `viabilidad_cpa`, motor con el test de 1 día y BLIK/P24, escalera J16 con redondeo local, upsell y postpago) → `PENDIENTES.md` B.
4. **Evidencia verificable**: `capturar_fuente` con hash, `barrido_ref`, ruta C, un solo CLI para el veredicto de D2 → `PENDIENTES.md` B.
5. **Dientes a la defensa de idioma y al antes/después**: reglas pl-PL, capas 3-5, y `antes_despues.json` con dos jueces a ciegas y la salvaguarda de R-5 → esta skill (`rubric.md` R7) y `PENDIENTES.md` B.

## 7. Qué se puede automatizar hoy y qué pide criterio humano (tabla del piloto)
| Paso | ¿Automatizable? | Falta o necesita criterio |
|---|---|---|
| MOD-1 desarmar | **Parcial**: el HTML sí (`analizar_html.py`); el desarme de oferta y anuncios es de la IA con cita | material del dueño (capturas del checkout sin pagar) o ruta C; **criterio humano:** qué referente «funciona» (no se ven ventas) |
| MOD-2 / MOD-4 plan | **Sí** el puntaje R-2/R-3 en código (pendiente) | elegir 3-5 palancas y leer la voz; PAL-16 ya corregida |
| MOD-3 inmersión | Sí, con evidencia débil | segunda familia de fuentes, auditor de IA, reglas pl-PL |
| MOD-5 oferta | ya es D3 | — |
| MOD-6 antes/después y QM | **No aún** | script de similitud compartido, dos jueces a ciegas |
| MOD-7 herencia | **Sí, de punta a punta** con el esqueleto del funnel y el plano `referente` | muestra real de D4, identidad del vendedor, `prueba_social_real.json` |
| MOD-8/9 | código mide, X2 propone | requiere ventas; la prueba es por ángulo y página |
