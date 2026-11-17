# Conflictos con la fuente, lo que no se sabe de JPS y pedidos

## 1. Lo que la fuente NO da (no se inventa: va marcado y se calibra)

| Qué falta | Qué hicimos | Marca |
|---|---|---|
| El **prompt de cada avatar** | Ficha estructurada desde `voz_cliente.json` + estilo de lectura de un vocabulario cerrado + consigna fija con hash | `[SUPUESTO]` |
| **Edad** de los avatares (JPS dice «edad, país, idioma, lo que le preocupa») | `null` / `sin_dato`; se completa solo con cita | no se inventa |
| **25 o 35 mercados** y «10 por mercado» vs «10 en total» | un mercado a la vez, 10 como tope, N limitado por evidencia (no 250) | `[?]` de la fuente |
| **Cómo se pondera** «el que acierta pesa más» | pesos iguales; informe por avatar; ponderación futura con validación cruzada | `[SUPUESTO]` |
| **Cómo se calcula «acierta»** | AUC contra etiquetas por madurez, IC de DeLong, Brier, comparación con azar y rúbrica | nuestro |
| «A los 3 días, la verdad» | a 3 días y ~15 USD casi no hay compras: se etiqueta con inversión/gancho/clics/pago y solo `ventas` cuando haya gasto mínimo y muestra | H-10 |
| Cuánto **acierta hoy** | no hay dato: ni AUC ni Brier. Ejemplo «7/10 comprarían» y la anécdota «canción con IA» | `[DECL]` |
| **3 videos suyos** (jurado, surfeo, creativos) | pendientes del dueño (B2-33, H-11); probable fuente del prompt y la ponderación | `[NO VERIFICADO]` |
| Frecuencia exacta (07:00 todos los días; miércoles recalibra) | adoptada tal cual; el disparo es del scheduler de S-B | `[P 47:43]` |

## 2. Dónde chocamos con su método y qué hicimos en su lugar

| Su práctica | Conflicto | Qué hacemos |
|---|---|---|
| El jurado «propone correcciones» e **«ir a internet a buscar tendencias»** `[V]` | mínimo privilegio y reglas de recolección; D6 no tiene web (P3-09) | el votante no tiene red; sus `ideas` entran como hipótesis (QA-A + lint + X1) y no crean claims. Un «explorador de formatos» asistido es otra pieza |
| «7/10 comprarían» como resultado | sería una cifra de clientes inventada si sale al público (P08) | `aviso_uso`, salida solo interna; el QA busca la cifra en `copies.json`, `paquete.json` y `05-landing/` (JQ-11) |
| Optimizar «qué se compra» y recalibrar contra ventas | un panel así **premia los claims prohibidos** (en la práctica convierten) y derivaría hacia ellos (K-8) | el jurado va **después** de QA-A y del lint; no vota cumplimiento; su calibración nunca realimenta la generación de claims (X2:94) |
| 250 jurados = 250 votos | los 250 son un solo modelo: errores correlacionados | se avisa en cada archivo; la banda es optimista y la calibración lo mide; N por mercado = el que sostiene la evidencia |
| Ponderar por mercado | con ~35 piezas/semana/idioma es ajustar ruido | pesos iguales hasta ≥ 150 etiquetas y validación cruzada |
| Avatares «hechos con IA» con perfil completo | edad, oficio y gustos serían inventados | solo lo citado de la voz del cliente |
| Los avatares como «clientes» | nunca son testimonios (J8: no se construyen testimonios con IA ni avatares presentados como clientes) | su salida es interna; ninguna frase de un avatar sale como cita |

## 3. Reglas de la casa que se respetan

J8 (sin testimonios ni cambiar de modelo para esquivar una negativa: si el votante se niega a puntuar algo, se registra y no se reintenta con otro pretexto), J11 (sin revisor nativo: las frases de los avatares son las de la fuente, no se «mejoran»), J12 (la voz del cliente es la materia prima), J13 (las anclas de otras ofertas se usan como control interno, nunca se publican ni se reutilizan sus textos), "la IA propone, el código dispone", sellos por hash, y nada de gasto, red, claves ni Meta/Stripe/Kie en ninguna parte de esta pieza.

## 4. Pedidos

Los pedidos a S-A, S-B, a la pantalla y al dueño están numerados en `PEDIDOS.md` de la skill, y resumidos en `docs/_historial/coordinacion-sesiones.md` («Avisos de S-C — jurado»). En una línea: contrato `jurado.schema.json`, grupo `jurado.*` en `parametros.yaml`, etapa del jurado en `qa.schema.json`, que la pantalla lea `modo`/`aplica_orden`/`precision.estado`, allowlist de `scripts.jurado.*`, productor de `metricas.jsonl` por anuncio, scheduler 07:00 + miércoles, las anclas, y los 3 videos de JPS.
