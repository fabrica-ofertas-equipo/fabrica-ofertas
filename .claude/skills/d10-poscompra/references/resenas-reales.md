# Reseñas reales: petición automática, permiso y `prueba_social_real.json`

> v0.1 sin pulir. Decisión del dueño (nota tras J19, 2026-11-07): **no se inventan** testimonios, reseñas, cifras de alumnos ni avisos; **sí** se construye la canalización de **reseñas reales automatizada** —petición automática tras cada compra real y componentes de la landing que solo muestran dato real—, **sin beta previa** («el modelo es encontrar ofertas validadas, modelarlas, testearlas rápido y escalar las que funcionan»; las reseñas reales llegan con las primeras ventas del propio test). Contexto: J8 (excepción), `landing/README.md` «Prueba social real», D5 `SKILL.md` «Datos reales». Lo que automatiza el producto del código está en `../PEDIDOS.md` P-08.

## 1. El recorrido (quién hace cada cosa)

| # | Cuándo | Quién | Qué |
|---|---|---|---|
| 1 | Pago confirmado y entrega `entregado` | código | el pedido pasa a ser elegible (§2) |
| 2 | Día 3 tras la compra | código | envía **E1** (`templates/correo-resena.<l>.txt`): cinco enlaces de estrellas, del 1 al 5, sin resaltar ninguno |
| 3 | Clic en una estrella | código (página `/opinia`) | un **GET nunca registra** (los escáneres de correo abren los enlaces): muestra la nota elegida, un comentario opcional (≤ 600 caracteres), tres casillas **no premarcadas** (§3) y un botón de **confirmar**; el `POST` registra |
| 4 | Al confirmar | código | añade una línea a `resenas.jsonl` (§5.1) |
| 5 | Día 7 | código | envía **E2** (único recordatorio) solo si no respondió y sigue elegible (§2) |
| 6 | Cada día | Maker (modo RESENAS) | corre `d10.py construir-prueba-social` en dry-run, revisa el informe, propone qué texto excluir y avisa de sesgos |
| 7 | Tras la revisión | código + X1 | escribe `05-landing/prueba_social_real.json`, X1 sella, se regenera y despliega la landing (`accion:prueba_social`, S desde N1) |

«Un clic» = una estrella elegida en el correo y un botón de confirmar (dos clics reales, sin cuenta ni formulario largo). El **día 3 y el día 7** son la decisión del dueño de esta tarea y aún **no existen en `parametros.yaml`**: propuestos `postcompra.resena_dias_primera = 3`, `resena_dias_recordatorio = 7`, `resena_max_correos = 2`, `resenas_min_para_mostrar = 1` `[HIPÓTESIS]` (PEDIDO A-04). Sin ellos, y con `correos_max_por_dia/semana = null`, el programador **no envía** (fail-closed).

## 2. A quién se le pide (a todos igual) y a quién no

**Elegible:** pago confirmado, entrega `entregado`, pedido real (no `cs_test_*` en producción, no del dueño, no `sintetico`), sin petición previa para ese pedido, correo sin baja de reseñas.

**Se suprime:** reembolsado · disputa o EFW abiertos · ticket de soporte abierto (se atiende primero) · baja pedida · segundo envío si ya respondió · PAUSA (las reseñas se detienen con `PAUSA`).

**Por qué esto no es «filtrar por sentimiento»:** la supresión parte de un **estado objetivo** (hay un reembolso o una disputa), no de la nota que se espera ni de si la persona «puntuó bien». Aun así deja una limitación que hay que decir con honestidad: la media pública **no es la satisfacción global**; los reembolsos y disputas se miden aparte (`r`, `d`, informe y `senal_pausa`) y mueven D8. Por eso: (a) `valoracion.fuente` dice «compradores verificados, con su permiso»; (b) el informe muestra reseñas/compras junto a `r`; (c) **una reseña recibida antes de un reembolso se conserva**, nunca se retira por eso.

## 3. El permiso (tres casillas, no premarcadas, texto versionado)

| Casilla | Campo | Efecto |
|---|---|---|
| «Mi valoración puede contar en la media pública (sin mi nombre)» | `permiso.valoracion` | entra en `prueba_social_real.valoracion` |
| «Pueden mostrar mi comentario en la página de venta» | `permiso.texto` | el comentario es candidato a publicar |
| «…con mi nombre de pila o inicial» | `permiso.nombre` | solo si marcó la anterior |

Sin ninguna casilla, la respuesta sirve **solo como retroalimentación interna** (se avisa en la página) y **no entra en ninguna cifra ni texto público**. Cada permiso guarda `version_texto` (el texto de las casillas, que aprueba X1) y `dado_en`. Es **revocable**: un enlace en el correo y soporte (C8) lo ponen en `retirada: true` y sale en la siguiente generación; la landing se regenera.

## 4. Nunca incentivo, nunca presión, nunca selección por nota

1. Ninguna recompensa, descuento, cupón, regalo, bonus ni sorteo a cambio de opinar (defecto D-04); tampoco «reembolso a cambio de reseña» ni lo contrario. Si el comprador lo propone, se ignora y se registra.
2. No se pide una nota concreta («5 estrellas») ni «solo opiniones positivas» (D-12); no se condiciona la petición a «si te gustó». Los cinco enlaces van en el mismo orden y con el mismo formato.
3. Las negativas **cuentan** en la media y, si hay permiso de texto, **se muestran** (S03 de los sembrados). Elegir qué reseñas mostrar por su nota está prohibido: se muestran todas las publicables, por orden de llegada, o ninguna.
4. **El texto no se edita**: solo se normalizan espacios. Una reseña con cifra de resultado («schudłem 8 kg»), antes/después, datos personales, enlaces, marcado o más de 600 caracteres **no se publica sin revisión humana** (D-19, L1-07, X1). Se propone excluirla con el motivo; no se «arregla».
5. **La pregunta es sobre el material y la compra** («oceń materiały»), nunca sobre resultados ni cambios en la vida del comprador (salud, relaciones, dinero): así la reseña no se vuelve una promesa de resultado.
6. Una reseña con `incentivo` distinto de `false` (incluida la ausencia del campo) **no cuenta ni se publica**; una `sintetico: true` tampoco, salvo con el permiso de pruebas.

## 5. Formatos

### 5.1 `resenas.jsonl` (lo escribe el código; una línea por respuesta confirmada; `templates/resenas.ejemplo.jsonl`)
```
{"resena_id":"RS-…","checkout_session_id":"cs_…","compra_verificada":true,"estrellas":1-5,"texto":"… | null","locale":"pl-PL",
 "recibida_en":"…Z","autor_visible":"Anna K. | null","permiso":{"valoracion":true,"texto":true,"nombre":false,"version_texto":"v1","dado_en":"…Z"} | null,
 "retirada":false,"incentivo":false,"sintetico":false}
```
Sin correo, sin IP, sin agente de usuario. `compra_verificada` lo pone el código al unir con el pago; el Maker no lo toca.

### 5.2 `05-landing/prueba_social_real.json` (esquema cerrado de D5; lo escribe el código)
```
{"schema_version":"0.1.0","oferta_id":"OF-…","generado_en":"…Z",
 "ventas":{"total":N,"fuente":"Stripe, pagos completados","al":"AAAA-MM-DD"},
 "descargas_muestra":{"total":N,"fuente":"…","al":"…"},
 "valoracion":{"media_decimas":10-50,"n":≥1,"fuente":"Reseñas de compradores verificados, con su permiso","al":"…"}}
```
Lo que **espera la landing** (`landing/contenido.py:219-235`, `landing/validar.py:431-432,490-501`): claves cerradas; `total` y `n` enteros (no texto ni decimales); fechas reales no futuras; `oferta_id` igual al de la oferta; sin marcado ni caracteres de control; **ninguna cifra en pantalla sin el mismo valor aquí** (`L1-PRUEBA-SOCIAL`); total 0 o bloque ausente = no se muestra. `d10.py validar-prueba-social` lo comprueba además contra `resenas.jsonl` (`--resenas`): una `valoracion` que no coincide con las reseñas que cuentan es un error. `ventas` y `descargas_muestra` los aporta el código (Stripe, registro de descargas): este script no los calcula ni los inventa. Media: décimas con **mitad hacia arriba** (4,25 → 4,3), no redondeo bancario.

### 5.3 Dónde va el texto de las reseñas (conflicto abierto)
Hoy una reseña **de texto** se muestra desde `copy.secciones.S08.resenas[{compra_id, texto, autor?}]` en modo `real`, y `L1-RESENA` exige que `compra_id` figure en `oferta.prueba` como `testimonio_con_permiso` con `consentimiento_ref` (`landing/contenido.py:362-367`, `landing/validar.py:434,499-501`). `oferta.prueba` es de D3 (versión aprobada y sellada): añadir una reseña ahí sería una versión nueva de la oferta que obsoleta D4-D7. **No es «la landing las muestra sola desde `prueba_social_real.json`»** salvo la valoración y el contador. Propuesta (A-01 + C-02): ampliar `prueba_social_real` con `resenas[{compra_id, estrellas, texto, autor, locale, recibida_en, consentimiento_ref}]` (generada por `d10.py`, `informe.publicables`) y que `L1-RESENA` y `S08` lean de ahí; hasta entonces, S08 se queda en modo `honesta` y `resenas_informe.json` es el insumo para cuando el dueño decida.

## 6. Qué mide el informe (con n y ventana)

Pedidas · respondidas (tasa) · con permiso de valoración · con permiso de texto · media de las que cuentan y **media de todas las verificadas** · `brecha_de_autorizacion_decimas` (si ≥ 3 décimas, avisar: la media pública estaría inflada o deprimida por quién autoriza) · distribución de estrellas de todas, de las que cuentan y de las publicables (deben parecerse) · reseñas retiradas · descartes por motivo · `r` de la misma cohorte.

## 7. Riesgos y `[VERIFICAR]`

- **¿Es una petición de reseña un mensaje comercial?** En la UE/UK/PL puede serlo según el país (consentimiento previo salvo relación con cliente y producto similar). Mitigación de v0.1: solo a compradores, sin promoción, máximo 2 envíos, baja de un clic, cuenta contra `correos_max_*`, sin cross-sell. `[RIESGO RESIDUAL aceptado: sin abogado, decisión 14]`; la clasificación como servicio o marketing y su gate (`accion:peticion_resena`) la decide el dueño (PEDIDO A-07). La spec vieja trataba el E4 de utilidad y permiso como marketing con gate H hasta N3: la decisión del dueño la hace automática.
- **Reglas de reseñas de consumidores** (UE: Directiva 2019/2161; UK: DMCC): prohibido publicar o encargar reseñas falsas y puede exigirse informar cómo se comprueba que son de compradores reales. La landing indica «compra verificada» y la fuente; `[VERIFICAR]` redacción por país con X1.
- **Reseñas en otro idioma:** se muestran en el original y solo en la landing de ese idioma; traducirlas es otra decisión `[DUEÑO]` (habría que marcarlas como traducidas).
- **Muestras pequeñas:** con n = 1 la landing mostraría «5,0 (1)»; es dato real y es lo que fija el contrato. Subir el mínimo es del dueño (`resenas_min_para_mostrar`).
