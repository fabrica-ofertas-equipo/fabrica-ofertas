# Formatos de anuncio que ya miden bien (según la fuente) y cómo los produce D6

Fuente: marco 5 del video de Juan Pablo Mentor, «4.460 anuncios medidos» `[P 32:27-34:50]`, cifras `[DECL]` (declaradas por él, sin verificar) en `docs/_historial/mentor-sistema/know-how.md` §2 y `brechas/01-cerebro-y-creativos.md` A.2 #8 y N-12. **No se usan como prior** (`mapeo.md` §6): no dicen si el «retorno» es ingreso o beneficio sobre gasto, ni el periodo, ni los mercados; se mide lo nuestro. Lo que sí importa: los tres formatos con mejor medición son **estáticos**, y la Ruta A de D6 (HTML a PNG, 0 créditos, ≈1 s por pieza) los produce hoy.

| Formato (suyo) | Rol que le asigna | Retorno `[DECL]` | En D6 | `variante_formato` propuesta |
|---|---|---|---|---|
| Imagen con pregunta | mejor costo por venta | 1,83 | estático Ruta A, `hook_tipo = pregunta-tarea` | `imagen-pregunta` |
| Ganador traducido | «la mitad de la ganancia» | 1,67 | re-render Ruta A de un ganador **propio** en otro idioma | `ganador-traducido` |
| Relevo con otra apertura | mismo anuncio, otro gancho | 1,39 | escalera 5.8 paso 1, pedido de fatiga | `relevo-otra-apertura` |
| El resto | — | 1,28 | — | — |
| Testimonio hecho con IA | — | 0 | **no se construye** (regla del dueño, J8) | — |

`variante_formato` es un campo libre de `matriz.json` (el esquema `creativos` no lo tiene aún: `PEDIDOS.md` #3); los tres valores son una propuesta de vocabulario y mientras no existan en el contrato viven en `matriz.json` y en `datos/ganchos.jsonl`.

## 1. Imagen con pregunta

**Qué es.** Un estático cuyo gancho es una pregunta. En la fuente: «¿Por qué se te mueren las plantas?» `[P]`.

**Cómo lo hace D6 sin romper la regla de atributo del espectador (E01).** La pregunta es sobre la **tarea**, nunca sobre la persona (`tipos-de-hook.md`, `pregunta-tarea`). El ejemplo de la fuente tiene un atributo escondido («se te mueren»: dice algo del lector) y se reencuadra:

| Fuente | Reencuadre aprobable |
|---|---|
| «¿Por qué se te mueren las plantas?» | «¿Cada cuántos días se riega una planta de interior?» + el entregable: «Calendario de riego por especie» |
| «Rozumiesz, co czytasz, ale gubisz słowa?» (gancho del dossier, riesgo E01 alto) | «Jak układasz słownictwo tematami?» (pregunta sobre cómo ordenar el vocabulario) |

**Receta (Ruta A, 0 créditos).** (1) `ganchos.py rechazar` con el texto, (2) una variable por vez: la pregunta cambia, el cuerpo (apoyo, prueba, aviso) no, (3) la respuesta está en la pieza o en el entregable mostrado, no en una promesa de resultado, (4) `render_estatico.py` en los ratios de la matriz, (5) `qc6.py`. Un par de preguntas por concepto cubre la hipótesis «qué pregunta frena el scroll».

**Qué mide.** `variable_cambiada = hook_tipo` (o el texto del hook); la comparación es entre las preguntas de la misma campaña (CTR de enlace, hook rate), no entre compras (con ~15 compras no se comparan ángulos).

**Estado.** Funciona hoy (plantilla `templates/estatico.html`); nunca corrió con una oferta real.

## 2. Relevo con otra apertura

**Qué es.** El mismo anuncio con **otro gancho** cuando el original se cansa: «testeamos todos los días para que cuando se canse un creativo tengamos uno nuevo esperando» `[V 45:00]`.

**Cómo lo hace D6.** Es la escalera de variación (SKILL §5.8, paso 1): se cambian la **primera escena y el hook verbal** (Meta pide un anuncio «materialmente diferente»: no basta cambiar una palabra), se reescribe el puente de cada hook y se conservan cuerpo, prueba y CTA. Entra por un `pedido_creativos` con `motivo = fatiga` y es la **primera prioridad de la tanda** (`modo-tanda.md`).

**Reglas.** El gancho nuevo debe ser distinto del que reemplaza (`ganchos.py rechazar`, y difiere en `hook_tipo` si es del mismo concepto); no hereda un claim prohibido del original; el relevo se registra con `variante_de = <ad_name original>` (campo propuesto, `PEDIDOS.md` #3; mientras tanto en `variable_cambiada` y `notas`). Un relevo es un anuncio nuevo: otro `ad_name` y `v`.

**Lo que falta (no es de D6).** Nadie emite `pedidos_creativos` (D8 no detecta fatiga todavía, B1-19) ni existe el «banco de suplentes ya probados»: hasta entonces el relevo se pide a mano.

## 3. Ganador traducido

**Qué es.** Un anuncio propio que ya ganó en un idioma, llevado a los demás idiomas encendidos: el ejemplo de la fuente es un **estático** con imagen, texto y botón traducidos (ES→FR) `[P 32:47]`; declara que un solo video traducido trajo «la mitad de la ganancia» del mes `[V][DECL]`. J5 manda replicar a otros idiomas lo que funciona.

**Qué cambia respecto de `localizacion.md`.** Las reglas 1 y 7 prohíben «traducir guiones» y «reutilizar assets con texto». Se leen así: **no se traduce el guion o el anuncio de un tercero** (eso es copia, J13) y **no se reutiliza el PNG** (se re-renderiza). **Sí se traduce un ganador propio**, con el procedimiento de abajo. La contradicción con `docs/08` (:316) y la spec 07 la resuelve S-A (`PEDIDOS.md` #4); esta skill sigue la regla más estricta de los dos lados.

**Procedimiento (variante «traducción fiel + subtítulos + 5 capas + X1 por `locale`»).**

1. **Precondición:** el ganador existe con evidencia en el idioma de origen (lo etiqueta D8/D9; D6 no decide qué ganó) y el idioma destino está en `limites.locales_permitidos`. El destino es otra oferta (`oferta_id` hija, `variante_de`): oferta = concepto × idioma. El origen puede ser **cualquier** idioma (Turquía→español y todos; español→todos).
2. **Traducción fiel** del `texto_en_pieza`, el titular, la descripción y el botón (CTA del enum), con glosario y dossier del idioma destino. Se ajustan: plurales, género, longitud (el titular debe caber en la zona segura), formato de precio y moneda **de la oferta hija** (nunca el precio del origen) y el aviso del nicho. Se conserva la estructura (J17); se cambia lo que en el idioma destino sería un calco.
3. **Claims por jurisdicción:** cada claim lleva `claim_id` de la oferta hija; X1 revalida por `locale`. Un claim permitido en origen puede no serlo en destino.
4. **Re-render Ruta A** con la marca de la oferta hija (no se reutiliza el PNG con texto). Para video: subtítulos traducidos sobre el video original solo si la voz no dice nada del idioma; si hay voz, voz nativa nueva (preset, nunca clonada), y eso es Ruta B.
5. **Las 5 capas de QA lingüístico** (`inmersion-y-derechos.md` §1) con foco en la **retraducción**: debe volver al sentido del original. `linguistico.json` registra el idioma de origen.
6. **Es una hipótesis, no un prior** (SKILL §5.8): el hook ganador en otro idioma se prueba; no se asume que vende. `ganchos.py agregar` con `--origen ganador` y la fuente del original.

**Lo que falta.** Biblioteca de ganadores históricos con estado de sello por idioma, el job de transferencia (S-B), `origen_locale` y `variante_de` en el contrato (S-A) y un ganador real (B1-20). El goteo diario de «ganadores históricos» de la fuente `[V 25:00]` es de esa biblioteca, no de D6.

## 4. Anatomía del anuncio ganador (la estructura que se imita)

Gancho visual (algo raro o una pregunta que frena el dedo) → **promesa** (un beneficio claro, dicho en simple) → **prueba** (el producto real en pantalla, por dentro) → **llamado** (qué hacer ahora). La fuente cierra el anuncio **sin precio**; nuestra skill mantiene `precio_visible` constante en todo el paquete y lo trata como variable de iteración (SKILL §5.6): quitarlo o ponerlo se prueba, no se asume. «Se copia lo que gana. Lo demás se apaga.»: copiar significa heredar la estructura (J13), no el texto.
