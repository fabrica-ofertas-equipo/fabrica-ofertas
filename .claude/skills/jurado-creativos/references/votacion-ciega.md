# Votación ciega

Cómo se arma y se ejecuta la votación de una tanda. Código: `scripts/jurado/paquetes.py` (armar y verificar) y `scripts/jurado/agregar.py` (validar y contar). El agente es `jurado-votante`.

## 1. Qué es «a ciegas»

JPS: el jurado «no sabe qué anuncio ganó antes ni cuál es nuevo» `[P 36:13]`. Aquí se hace cumplir con cuatro reglas **de construcción**, no de buena voluntad:

1. **Una pieza por llamada.** Cada llamada es (un avatar, una pieza) en un contexto limpio: sin memoria de otras piezas ni de otras llamadas.
2. **Orden aleatorio con semilla registrada.** Las llamadas son una permutación completa de avatar × (piezas + anclas), barajada con `random.Random(semilla)` desde un orden canónico (no depende del orden de los archivos de entrada). La semilla y su origen (`explicita` | `derivada` de oferta y tanda) quedan en `privado/manifiesto.json` junto con `hash_orden`. Misma entrada y misma semilla = los mismos bytes.
3. **Anclas.** Cada juez recibe, mezcladas al azar con las piezas, **≥ 1 pieza conocida-ganadora y ≥ 1 conocida-perdedora**, indistinguibles de las demás (§4).
4. **Sin acceso a métricas.** El paquete es una lista blanca: `consigna`, `avatar` (ficha), `pieza` y `formato_de_respuesta`. Ni métricas, ni nombre de anuncio, ni versión, ni ángulo, ni tipo de gancho, ni nombre de formato, ni «nueva/ganadora», ni ruta que delate.

## 2. Qué ve el votante y qué no

| Lo ve | No lo ve nunca |
|---|---|
| `consigna` (versionada y con hash), la ficha del avatar (preocupaciones, objeciones, citas, vocabulario, estilo de lectura) | `ad_name`, `id_origen`, `hook_tipo`, `variante_formato`, versión (`_v1`), ángulo, concepto |
| UNA pieza: `texto_visible` y/o la imagen (copiada con nombre opaco `P-xxxxxxxx.ext`) | CTR, CPA, ROAS, gasto, impresiones, ranking, si ganó o perdió |
| `pieza_id` y `paquete_id` opacos (hash de la semilla) | semilla, orden de las llamadas, si la pieza es ancla, la llave |
| | `oferta_id`, `procedencia` del avatar, rutas del repositorio |

La llave (`privado/llave.json`: `pieza_id → ad_name | ancla`) y el manifiesto viven en `privado/`, que el votante no recibe. El orquestador **pega el contenido** del paquete en la llamada (no le da la ruta del archivo) y solo entrega una ruta absoluta cuando hay imagen.

## 3. Precondiciones y tope

- **Después de QA-A y del lint de promesas**, nunca antes: `paquetes.py armar` rechaza una pieza sin `precondiciones.qa_a` y `.lint` en PASS/PASS_CON_NOTAS (salvo `--demo`). Así el jurado no vota —ni «premia»— un claim prohibido (K-8 del análisis).
- **Tope de llamadas** `max_llamadas` `[SUPUESTO 200]` antes de gastar un token: llamadas = (piezas + anclas) × (avatares + línea base). Con 11 piezas + 2 anclas y 10 avatares + línea base son 143 llamadas por tanda y mercado; con 5 avatares, 78.
- v0.1 vota **texto e imagen**. El video queda fuera (el votante solo tiene `Read`): se rechaza con mensaje.

## 4. Anclas

| Tipo | `origen_resultado` | Qué prueba | Cómo se consigue |
|---|---|---|---|
| Conocida-ganadora / perdedora **medida** | `medida` (con `evidencia.fuente` y `.metrica`) | que el jurado coincide con el mercado en un caso conocido | una pieza ya lanzada y leída; `calibrar.py` las **sugiere** (`anclas_sugeridas`) y una persona las confirma |
| **Control sintético** | `control_sintetico` (con `evidencia.nota`) | solo que el votante distingue lo grosero (buena vs defectuosa) | la escribe una persona a mano. Arranque: antes de la primera tanda lanzada no existen anclas medidas |

Reglas: mismo `locale` que la tanda (otro idioma se delataría), mismo formato de paquete, mismo tipo de identificador. **Nunca entran al orden ni a `votos`**; se resumen en `anclas` (`share_si_ganadoras`, `share_si_perdedoras`, `discrimina`, `sesgo_de_aprobacion`). `discrimina` = las ganadoras sacan ≥ `anclas_margen_min` (0,2) puntos más de «sí» que las perdedoras. Si el jurado aprueba la perdedora (≥ 50 % de «sí»), es **sesgo de aprobación** y el archivo lo avisa: no uses ese orden. Con anclas solo sintéticas no se puede promover (`sombra-y-promocion.md`).

## 5. La pregunta y el voto

`voto = true` ⇔ «harías clic para saber más». Es la pregunta que se puede contrastar con una etiqueta temprana y abundante (CTR del enlace), no una pregunta de compra que a 3 días casi no tiene etiquetas (`calibracion.md`). Además: `puntaje_gancho`, `puntaje_claridad`, `puntaje_cta` (o `null`), `puntaje_general` (enteros 0-10), `motivo` y `idea` (≤ 25 palabras, en español) y `alerta_ceguera`. JPS pide «sí/no y una frase de por qué» y puntaje de gancho, ritmo, CTA y general `[V 14:00]`; el **ritmo** solo tiene sentido en video y queda fuera en v0.1.

## 6. Cómo corre el orquestador (el código nunca llama a un LLM)

1. `paquetes.py armar …` (verifica la ceguera solo; si falla, no hay tanda).
2. Para cada entrada de `orden_llamadas` del manifiesto, en ese orden: invocar `jurado-votante` con el contenido de `<tanda>/<archivo>`; guardar su respuesta **tal cual** en `<tanda>/votos/<mismo nombre>.json`. Las llamadas son independientes: pueden ir en paralelo.
3. Respuesta que no es JSON válido: **un** reintento con el mismo paquete (nunca un paquete distinto). Si vuelve a fallar, se guarda tal cual y `agregar.py` la rechaza.
4. `agregar.py agregar …` y `agregar.py verificar …`.
5. `jurado-qa` revisa. Mientras tanto nadie corrige un voto a mano: un voto rechazado queda rechazado.

## 7. Qué hace `agregar.py` con los votos

- **Valida cada voto**: tipos estrictos (`voto` booleano, puntajes enteros 0-10, sin bool disfrazado de número), motivo e idea ≤ 25 palabras, sin campos de más, `paquete_id`/`avatar_id`/`pieza_id` que coinciden con el manifiesto, sin duplicado, sin voto sintético fuera de demostración. Lo malformado → `rechazados[]` con motivos y **no cuenta**. Con `alerta_ceguera` → `cuarentena`.
- **Por pieza**: `share_si`, puntaje medio/mediana/desvío, acuerdo, **banda de Wilson 95 %** del `share_si` y **rango de puestos** (bootstrap sobre avatares, 1000 réplicas con la semilla). `confianza` alta/media/baja por el ancho del rango `[SUPUESTO]`.
- **Orden**: por `share_si`; el puntaje general solo desempata (`score = share_si + 0,001 × puntaje/10`); el empate restante se rompe con la semilla, no con el nombre. `separable_del_siguiente` dice si la banda de una pieza queda por encima de la de la siguiente: con 10 jueces, 7 de 10 y 6 de 10 **no** se distinguen.
- **Entre jueces**: kappa de Fleiss, acuerdo medio por pieza, tasa de aprobación global y dispersión entre piezas; avisa si aprueba casi todo o casi no varía.
- **Pesos iguales** para todos los jueces hasta que la calibración lo permita (`calibracion.md` §6).

## 8. Límites que no se arreglan con código

- **Los jueces son el mismo modelo con perfiles distintos**: sus errores están correlacionados, no son N observaciones independientes. La banda de Wilson supone independencia y por eso es **optimista**; el sesgo común del modelo solo lo mide la calibración con lo cobrado.
- El estilo de una ancla o los metadatos de una imagen (EXIF, C2PA) pueden delatarla; el QA lo prueba (L3-a) pero el código no lo borra.
- La ceguera es del paquete; no impide que el modelo reconozca un estilo visual que ya vio en otra llamada.
