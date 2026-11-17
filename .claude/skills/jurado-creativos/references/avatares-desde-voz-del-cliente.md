# Avatares desde la voz del cliente

Cómo se construyen los N avatares de un mercado. Lo hace el código (`scripts/jurado/avatares.py`); ninguna IA inventa un perfil.

## 1. Qué dice JPS y qué no

- «25 mercados · 250 jurados»: cada mercado tiene **10 clientes ideales hechos con IA**, con su edad, país, idioma y lo que le preocupa `[P 36:13]`. «25 o 35» y «10 por mercado» frente a «10 en total» quedan `[?]`.
- Perfiles distintos `[V 13:30]`: «uno desconfía de todo, otro compra todo, uno artístico, uno creativo, uno analítico».
- **No se sabe** el prompt de cada avatar, cómo se pondera ni cómo se calcula «acierta». El video remite a «un video específico sobre cómo funciona el jurado de IA» (H-11, `[NO VERIFICADO]`). Nada de eso se completa de memoria: cada decisión de abajo es `[SUPUESTO]` y se calibra.

## 2. Nuestra decisión: una ficha, no una novela

Un avatar es una **ficha estructurada** (`templates/avatar.json`) cuyo contenido sale solo de `02-validacion/voz_cliente.json` (y del dossier de voz del cliente, J12). El votante recibe la ficha, no un relato inventado. Por eso:

- **Edad, género y ocupación son `null` con `origen: sin_dato`.** La voz del cliente del piloto no los trae (el dossier solo menciona «una mujer de 55 años» como un caso suelto en un foro, y dice que «es tarde para mí» no apareció como frase). Si D2/D3 aportan un dato demográfico con cita, se escribe a mano en `demografia` con su `fuente`; `avatares.py validar` rechaza un valor sin cita. El generador **nunca** lo rellena.
- **Sin estereotipos.** No hay «el joven tecnológico» ni «la señora que no sabe de apps» salvo que una frase literal lo respalde (y aun así, se cita la frase, no se infiere el perfil).
- **País e idioma** salen de `locale` y de `pais` de las frases.

## 3. Cómo se construye (determinista)

1. **Frases válidas.** Cada frase necesita `frase_id`, `texto_literal`, `fuente_url`, `tema` y `categoria`, y el mismo `locale` que el panel. Las demás van a `frases_descartadas` con su motivo (una frase sin fuente no respalda a nadie).
2. **Focos = preocupaciones reales.** Se agrupan las frases por `tema`, **excluyendo el `lexico_de_compra`** (vocabulario de vendedores, no voz de cliente). Cada foco lleva `n_frases` y `n_fuentes` (URL distintas) y se ordena por (fuentes, frases, tema).
3. **Techo de N.** `N efectivo = min(N pedido, focos elegibles)`. **No se rellena**: si piden 10 y hay 6 focos, salen 6 y `limite_n` + `advertencias` lo dicen. Parámetros `--min-frases` y `--min-fuentes` suben el listón.
4. **Estilo de decisión** (rotación, vocabulario cerrado `[SUPUESTO]`): `esceptico`, `impulsivo`, `analitico`, `visual`. Es un **rol de lectura** («desconfía de lo comercial», «decide rápido»…), no una biografía; está inspirado en lo que dice JPS y su utilidad se mide, no se supone. Los estilos de JPS «artístico» y «creativo» se fusionan en `visual`.
5. **Preocupación principal.** El escéptico toma el primer foco de categoría `objecion`/`precio`/`alternativa`; los demás, uno de `dolor`; si no queda, el siguiente por evidencia.
6. **Secundarias.** Dos focos más, sorteados con la **semilla registrada** (`random.Random(semilla|i)`): misma semilla, mismo panel.
7. **Objeciones.** Los temas propios del avatar cuya categoría es objeción, precio o alternativa.
8. **`en_sus_palabras`.** Hasta 6 citas: 3 del foco principal y 1 por secundario, cada una con `frase_id`, texto literal (limpiado solo de caracteres de control) y `fuente_url`. `vocabulario`: el `lexico` de la voz del cliente.
9. **`nivel_evidencia`** por fuentes del foco principal `[SUPUESTO]`: ≥ 3 `alta`, 2 `media`, 1 `debil`.
10. **Línea base.** Con `--incluir-baseline-rubrica` se añade `av-<locale>-rubrica`: un juez **sin perfil** que aplica solo gancho, claridad y llamado (como R1-R3 del QA de D6). No cuenta como avatar ni vota en el jurado: es la vara que el jurado debe superar (`calibracion.md`).

## 4. El límite de N, con el piloto

OF-202611-91 (inglés para hablantes de polaco): `voz_cliente.json` tiene **35 frases válidas de 13 fuentes**, 21 temas, de los que **15 son preocupaciones elegibles** (6 son solo léxico de compra). Solo **5** focos están corroborados por ≥ 2 fuentes y **2** por ≥ 3. Con N = 10 salen 10 avatares, pero **5 se apoyan en una sola fuente** (`debil`) y la fuente tiene el sesgo que ella misma declara (Wykop: joven, masculino, tecnológico). Lectura honesta: con esta voz del cliente el panel de 10 es más ancho que la evidencia; N = 5 es lo que el material sostiene sin añadir ruido. Para sostener 10 hay que **ampliar la voz del cliente** (más fuentes, otros foros: J12), no inventar avatares.

## 5. Procedencia y registro

- Cada avatar guarda `procedencia`: ruta y `sha256` de `voz_cliente.json`, versión del generador, semilla y parámetros. Si la voz cambia, se regenera y el hash lo delata.
- `registro_avatares.jsonl` (append-only, junto al panel) anota `generado` y `reemplazo`.
- **Reemplazo** (`avatares.py reemplazar`): solo si la calibración lo propone (`propuestas_reemplazo`, con ≥ `n_min_etiquetas_avatar` etiquetas, mejora ≥ δ repetida en las dos mitades, o AUC propio por debajo del azar con IC completo) o, a mano, con motivo de ≥ 20 caracteres. El avatar retirado **se conserva** (`estado: retirado`, `reemplazado_por`); el nuevo toma una preocupación aún no cubierta y **nunca reutiliza un id**. Si no queda ninguna, el panel baja a N-1. Así no se «cambian avatares hasta que el pasado coincida» sin dejar rastro (JPS: «los que no aciertan salen y vuelven como avatares nuevos» `[P 47:43]`).

## 6. Prohibido

Texto del avatar como cita de un cliente real fuera del jurado; atribuirle un atributo que no está en la fuente; usar las frases del avatar en un anuncio como testimonio (J8: no se construyen); que un avatar «sepa» algo del producto; que el votante reciba `procedencia`, `oferta_id`, `frase_ids` o rutas.
