# Preguntas abiertas y supuestos (bloqueantes primero)

> Forjada el 2026-11-06 sin esperar respuestas: lo que el §10.1 de la spec pide preguntar queda aquí y la skill avanza con `[SUPUESTO]`. Ajustada tras el cierre de la ingesta de S-A (R-C01: el plan no fija primer mercado; un mercado a la vez; lo decide el dueño con la propuesta de M1). **Ninguna de estas decisiones la toma M1.** Cada pregunta dice qué cambia en el resultado. Etiquetas: `[DUEÑO]`, `[SUPUESTO]`, `[VERIFICAR]`, `[HIPÓTESIS]`.

## P1 — BLOQUEANTE `[DUEÑO]`: ¿cuál es el primer mercado que se prueba?
**M1 no tiene un mercado favorito y no lo propone por impresión.** Ningún país es prior: Polonia e Italia son hipótesis, no un par de arranque, y la fuente de la impresión «sobre todo Polonia» (un creador fuera del corpus) no está registrada (P9). **Regla vigente (R-C01, resuelta en `docs/03`, `docs/00`, `_backbone` v2.2.4 y la spec 16; dependencias I1, I2, I14): el plan no fija un primer mercado, se prueba un mercado a la vez (`mercados_test_paralelos_max = 1`) y lo decide el dueño con la propuesta de M1.** La pregunta sigue abierta porque el dueño no ha elegido, y porque R6 excluye a Polonia mientras los métodos locales sigan diferidos. Las opciones A-E son las que M1 puede presentar (ninguna es la «recomendada» por el plan; cada una con lo que exige y la evidencia; todo confianza C salvo indicación):

| Opción | Exige (decisiones/construcción) | Evidencia a favor | Evidencia en contra / lo que no se sabe |
|---|---|---|---|
| **A. Italia (it-IT) sola, fase vigente (K = 1)** | revisor nativo it; contador (IVA 22 % por OSS desde la 1.ª venta); firma de exposición fiscal; aceptar hueco PayPal | pasa R6 con bandera `cobertura_media` (46-50 % en fase vigente, 07h §3.3); `r` entre los 3 mejores del orden económico en `rank.py corregido` (≈ 2,5); creadores: 27 videos con cifras autodeclaradas y fracasos (C-B) | PayPal 24-36 pp inalcanzable; tarifa de ubicación de Meta 3 %; puntaje `corregido` bajo el mínimo (53 con +5 de creadores que pesan 0); crochet ya saturado (396 anuncios); fecha de la función de desistimiento (art. 54-bis) dudosa; con K = 1 **no compara mercados** |
| **B. Polonia (pl-PL), con métodos locales** | decisión del dueño de **levantar el diferido** (BLIK, PLN) + MINOR del contrato `mercado` (S-A); **revisor nativo polaco obligatorio** (Ley del Idioma Polaco: R5); precio en PLN; sin Managed Payments | CPM de referencia más bajo y sin tarifa de ubicación; BLIK sin tarifa de disputa; `r` ≈ 2,5 (similar a IT) | fase vigente ≈ 17 % ⇒ R6 la excluye hoy; BLIK 45-55 % es un rango de trabajo C (fuentes de ~30 % a > 70 %); BLIK sin apelación de disputas y riesgo de medir el Purchase en móvil; **0 lanzamientos y 0 cifras en el corpus** (5 videos); función de desistimiento polaca suspendida al 2026-06-12 `[VERIFICAR]` |
| **C. Comparar dos mercados a la vez (excepción, no el plan)** | decisión estructural del dueño de subir `mercados_test_paralelos_max ≥ 2` (rango 1-3) y presupuestos iguales por mercado sin precio tachado; lo de A o B para cada uno. **No hay par por defecto**: «Italia + Polonia en paralelo» ya no es la ruta del plan (R-C01) y solo sería una de las combinaciones posibles; con Polonia exige además la fase `con_locales` | es la **única** forma de comparar mercados entre sí (docs/08 §7) | doble costo fijo (2 revisores, 2 glosarios, 2 checkouts); comparar exige clics por brazo del orden de `clics_min_decidir_mercado`: ~60-75 USD por país es solo señal de proceso (16 H3); la traducción es variable de confusión. Con el parámetro en 1 esta opción no está disponible: el primer mercado se decide en serie |
| **D. Bloque inglés (CA sin Quebec, NZ, AU, IE)** | OSS en IE; en dinero, regla de parada por la verificación financiera de Meta (AU, IE); revisar el ticket de 27 USD | mayor facilidad operativa (08: CA, NZ, AU en lo alto del orden de facilidad; umbrales de impuesto altos; tarjetas ≈ 60-74 %); sin traducción | el 27 USD **no está observado** en esos países (16 H2); en el orden económico (menor `r`) quedan en el medio/final; hueco PayPal 16-20 pp y BNPL local en AU/NZ; CPM mayor |
| **E. Otro idioma/mercado o esperar a enero** | ficha y desglose que hoy no existen (RO, FR, DE, PT-PT…) o ventana fuera de Q4 | RO/FR son «segunda ola» de 08; enero evita Black Friday y Navidad en el CPM | sin datos puntuables (`rank.py` no los cubre); un test nov-dic se lee «Q4» y no es comparable con enero |

**Qué decisión del dueño mueve más el resultado** (por el cálculo de `puntaje.py`, ver `references/algoritmo.md`): la combinación **Managed Payments × métodos locales** (cambia la cobertura de Polonia de ~17 % a ~67 %; con Managed Payments los locales salen) y **`mercados_test_paralelos_max`** (decide si se puede comparar; hoy 1 por R-C01). El diferencial Italia-Polonia en puntaje es **un empate** (< `empate_puntos`) en ambos sentidos: sin el ajuste de creadores (peso 0) Polonia queda ~3 puntos por encima de Italia en `rank.py`, y ambos quedan bajo `puntaje_minimo` (bandera `bajo_minimo`, no exclusión).

### Evidencia de demanda de los datos propios del barrido (HIPÓTESIS: no medida)
Fuente: `empresa/barrido/candidatos/2026-11-06-a.json` (`temas`, `matriz_tema_pais`), `empresa/barrido/crudo/2026-11-06-a/` (un archivo por consulta, prefijo = país) y `paginas/2026-11-06-a.json`. **Presencia en la MUESTRA del conector de la Biblioteca de Anuncios** (≤ 50 anuncios por consulta; 697 de 724 páginas con muestra truncada: los conteos son un piso; 674 de 724 solo «muestra»). `estado_ausencia = hipotesis_hasta_pasada_3`: **la ausencia en la muestra es una hipótesis hasta medirla** (pasada 3: page_ids × país). **La cobertura de consultas por país no es pareja**, así que la presencia bruta no ordena países.

| País | Temas con presencia (de 391) | Consultas (archivos de captura) | Presencia por consulta | Temas dentro del marco (salud·relaciones·dinero; de 61) | De los 11 temas que pasan tracción |
|---|---|---|---|---|---|
| BR | 87 | 13 | 6,7 | 13 | 0 |
| IT | 67 | 23 | 2,9 | 13 | 5 |
| ES | 62 | 11 | 5,6 | 10 | 3 |
| US | 56 | 9 | 6,2 | 7 | 0 |
| FR | 46 | 12 | 3,8 | 6 | 4 |
| PL | 40 | 8 | 5,0 | 2 | 3 |
| GB | 36 | 3 | 12,0 | 2 | 0 |
| DE | 31 | 11 | 2,8 | 6 | 2 |
| MX | 23 | 3 | 7,7 | 2 | 1 |
| RO | 14 | 6 | 2,3 | 2 | 0 |

Lectura permitida: (1) de 391 temas, **330 son «fuera de marco»** (ni salud, ni relaciones, ni dinero) y **10 de los 11 que pasan la tracción también**: la muestra del barrido casi no mide demanda dentro del marco del dueño; (2) el único tema que pasa dentro del marco es de salud y está en FR; (3) 63 temas están presentes en IT y ausentes de PL, 36 al revés y 4 en ambos (de la muestra): son **hipótesis de transferencia** que piden barrido local, no oportunidades; (4) IT concentra más páginas en la muestra pero también tuvo ~3 veces más consultas que PL (23 vs. 8): por consulta no hay ventaja italiana. Lectura **prohibida**: elegir un mercado por presencia en la muestra o presentar un hueco como oportunidad (`references/interfaz-d1.md` §4).

**Cómo se responde:** el dueño elige la opción (o pide otra, un mercado a la vez) y las decisiones P2-P7 que esa opción exige; M1 reejecuta `puntaje.py seleccionar` con ese `limites`/fase y redacta `mercado.json` + `mercado.seleccion.json` con la elección como **hipótesis** (`estado_decision = hipotesis`).

## P2-P8 — Bloqueantes del §10.1 (sin respuesta ⇒ la skill no avanza o avanza con `[SUPUESTO]`)
| # | Pregunta | `[SUPUESTO]` con el que avanza la skill | Qué cambia |
|---|---|---|---|
| P2 | `limites.paises_permitidos` y `locales_permitidos` (hoy `[]`) | ninguno: **vacío ⇒ salida 5, nada se evalúa** | todo (R1) |
| P3 | ¿Managed Payments sí / no? `[DUEÑO + contador]` | `no_decidido` ⇒ se calcula Stripe estándar y se informa la otra rama | PAGO, neto, FISC, R8; con «sí» Polonia queda ~17-23 % |
| P4 | ¿Métodos locales diferidos o se levantan? (+ MINOR 1.2.0 del contrato) | diferidos (fase vigente) | R6, valor de desbloqueo, monedas |
| P5 | Captura de las pestañas «Deshabilitado» (24) y «requiere acción» (1) de Stripe | lo conocido de la captura del 2026-11-05 `[VERIFICAR]` | qué métodos existen (iDEAL, Przelewy24, Bizum, Multibanco…) |
| P6 | `mercados_test_paralelos_max` (hoy 1) | 1 (manda el parámetro; subirlo a 2 es decisión del dueño, `docs/00` ítem 8) | si se puede comparar mercados (I1, resuelta por R-C01) |
| P7 | Revisor nativo **del idioma del primer mercado** (it o pl solo si salen elegidos; `docs/00` ítem 6) | ninguno contratado ⇒ R5 en pl-PL; it-IT sin obligación legal pero sin glosario aprobado | R5, gate H, costo fijo |
| P8 | Fecha prevista del test: ¿antes o después del 1-ene? (define `mult_cpm`) | ventana nov-dic ⇒ central y estrés informados | CPM, R9, presupuesto |

## P9-P14 — Otras abiertas `[DUEÑO]`
P9 Fuente de la impresión «sobre todo Polonia» (video, canal o cifra) para registrarla como evidencia C (hasta entonces es una hipótesis sin fuente). P10 Umbrales de cobertura (duro/blando) y puntaje mínimo: ¿se aceptan como arrancan o se prefiere otra regla? (cambian qué países entran). P11 ¿Aceptar el hueco PayPal en Italia/UK/CA o evaluar PayPal propio? P12 Quebec y Brasil: ¿proyectos aparte con idioma y régimen propios? P13 Contador: tipo de IVA de un PDF (¿tasa de e-book o general?), OSS no-Unión y quién presenta, registro UK, representante GDPR. P14 Refrescar los CPM de `scripts/mercados/datos/mercados.json` (todos del 2026-07-27): ¿quién opera la búsqueda y con qué fuente?

## Supuestos hechos por la skill (`[SUPUESTO]`; revisar al pulir)
S1 Pesos y umbrales de la spec §3.4 como fallback (`scripts/parametros_m1.fallback.json`). S2 Matriz de exposición = semilla del Anexo D (`scripts/semilla_exposicion.json`); NZ hereda de CA y PT de IT. S3 `nivel_max_lanzable` ausente o `null` = SOLO VERDE (contrato limites 1.3.0; antes se suponía amarillo-a). S4 Subnivel amarillo = A con un eje amarillo, B con dos o más. S5 Puntaje de bloque = media simple de sus países. S6 `mult_cpm_efectivo` = central (1,2) con CPM vencido etiquetado `[SUPUESTO]` y bandera `cpm_vencido`; el 1,5 es sensibilidad (decidido por la spec, dependencias I7 resuelta). S7 R8: firma pendiente = bandera; firma decidida que no cubre el país = exclusión. S8 Fichas de `evals/dorados/fixtures/` son ejemplo, con revisor nativo supuesto contratado. S9 `mercado.seleccion.json` sigue la propuesta `scripts/mercado_seleccion.schema.propuesta.json`.
