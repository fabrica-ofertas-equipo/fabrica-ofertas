# Modo «tanda» (manual): 5-10 estáticos candidatos por día y por idioma, 0 créditos

Brecha B1-16 del informe `docs/_historial/mentor-sistema/brechas/01-cerebro-y-creativos.md`. En la fuente, el «turno noche» arranca a las 00:00, cada idioma pide su encargo (relevos, ángulos, traducciones) y a las 07:00 la tanda espera en una carpeta «por aprobar»; de noche se produce y a la tarde se carga (hacer las dos cosas a la vez satura la API de Meta). Aquí se construye la parte que se puede hoy: **la tanda manual**, que el dueño o una sesión lanzan a mano. El disparo nocturno automático (planificador, paralelismo, ventanas) es de S-B (`PEDIDOS.md` #10).

**Qué es y qué no es.** Es un modo de D6 que produce un **banco de candidatos** de estáticos por la Ruta A (HTML a PNG, 0 créditos, ≈1 s por pieza). **No** sube nada a Meta, **no** gasta créditos, **no** usa Higgsfield ni video, **no** aprueba nada y **no** cambia promesa, precio ni claims. Las reglas duras de la SKILL §1 valen íntegras.

## 1. Candidatos vs anuncios que entran al test

El informe (B1-14) mide que D6 produce hoy 0,4-1,1 piezas por día (6-8 cada 7-14 días) y que J3 pide ~10 creativos en una CBO de 50-100 US$. Son dos números distintos y la skill los separa:

| | **Candidatos** (la tanda) | **Anuncios del test** (el paquete de lanzamiento) |
|---|---|---|
| Qué son | Estáticos baratos producidos cada día por idioma | Los ~10 creativos de la CBO de lanzamiento (J3) |
| Cuántos | 5-10 por idioma y día `[SUPUESTO]` | `n_anuncios_max` (SKILL §5.1) |
| Costo | 0 créditos, ≈1 s por pieza | 0 en Ruta A; créditos solo en Ruta B |
| Quién los aprueba | El régimen de aprobación de §5 | QA-A, QA-B y X1 sobre el hash del paquete |
| Destino | Banco de relevos y suplentes; los aprobados entran a `paquete.json v(n+1)` | D7 |

## 2. Topes de diseño que chocan con J3 (propuesta `[SUPUESTO]`)

Mientras S-A no cambie `parametros.yaml`, **manda el tope vigente** (la regla más estricta) y la tanda produce candidatos extra que no entran al test. Valores propuestos (pedido #1 de `PEDIDOS.md`):

| Clave | Hoy (rango) | Propuesta `[SUPUESTO]` | Por qué |
|---|---|---|---|
| `creativos.n_anuncios_max` | 8 ([2, 8]) | **10** ([2, 12]) | J3: ~10 creativos en una CBO |
| `campana.n_anuncios_tope` | 6 ([3, 8]) | **10** ([3, 12]) | idem; hoy es el tope que manda |
| `creativos.n_conceptos_test` | 4 ([3, 6]) | **5** ([3, 8]) | 5 conceptos × 2 hooks = 10 |
| `creativos.hooks_por_concepto` | 2 ([1, 3]) | 2 | sin cambio |
| `creativos.reserva_conceptos` | 2 ([1, 4]) | 2 | sin cambio; la reserva son conceptos sin assets |
| factor «3» de `floor(gasto_test_plan / (3 × cpa_obj))` | 3 | **no limita** el paquete de lanzamiento | con 50-100 US$ y un CPA de 15-18 US$ el factor da 1 anuncio; en J3 la unidad de decisión es la campaña (1 día sin venta con el presupuesto gastado → baja), no cada anuncio. Decisión de S-A y S-B (`engine.guard`, D7/D8) |
| nuevas: `creativos.candidatos_por_dia_min` / `_max` (por idioma) | — | **5 / 10** | la fuente no da la cifra (la ilustración «tanda de hoy» es una cuadrícula 3×3 sin número) |
| nueva: `creativos.tandas_por_semana` | — | **7** | turno noche diario; la fuente se contradice («5 por día», «cada semana») |
| nueva: `creativos.muestreo_tanda_pct` | — | **20** | solo para el régimen B |

## 3. Procedimiento (una tanda = un idioma = un día)

Carpeta de trabajo: `ofertas/<id>/06-creativos/tandas/AAAA-MM-DD_<locale>/` (`encargo.json`, `matriz.json`, `copies.json`, `guiones/`, `assets/`, `qc6.json`, `por-aprobar.json`). Plantillas en `templates/tanda-*.json`.

| Paso | Qué se hace | Herramienta | Listo cuando |
|---|---|---|---|
| T0 · Precondiciones | Oferta aprobada (D3, M1, D5), `locale` en `limites.locales_permitidos`, preflight D6 verde (SKILL paso 1), existe un paquete base `v1` aprobado o al menos QA-A de texto, motores a la vista | `qc6.py motores`, `scripts.creativos.preflight_d6` | 0 chequeos en rojo y se sabe qué motores faltan |
| T1 · Encargo | Se cuenta cuántos relevos (creativos cansados con `pedidos_creativos`, motivo `fatiga`), ángulos nuevos (de `oferta.angulos[]` aún sin probar) y traducciones (ganadores propios por traducir) hay y se reparten. **Prioridad: primero reemplazar lo que se cansa; después ángulos nuevos y traducciones, que se alternan.** No se inventan pedidos: si hay menos que el mínimo, la tanda es más corta | `tanda.py plan --locale … --objetivo N --relevos R --angulos-nuevos A --traducciones T --salida …/encargo.json` | `encargo.json` con la composición |
| T2 · Ganchos | Cada pieza parte de una cita del dossier o de un ganador (J12) y de una palanca; el texto del gancho se comprueba **antes de redactar el resto** | `ganchos.py rechazar --texto … --locale … --oferta-id …`; luego `ganchos.py agregar` | 0 rechazados por repetido o por copia del referente |
| T3 · Matriz y copies de la tanda | `matriz.json` (un `ad_name` con `v` nuevo por pieza, una variable por vez, `variante_formato`: `imagen-pregunta`, `relevo-otra-apertura`, `ganador-traducido`, `estatico-html`), `copies.json` con `texto_en_pieza`, guion corto por pieza si hace falta; riesgo por pieza con `scripts.nivel_riesgo` | `validar_d6.py matriz` | sale 0 sobre los textos de la tanda |
| T4 · QA-A del texto | El QA (otro proceso) revisa los textos de la tanda y congela su hash; el lint por idioma y el anti-copia corren antes | `compliance.lint_claims`, `x1-compliance/scripts/ngrama_copia.py`, `d6-qa` tramo A | PASS o PASS_CON_NOTAS sobre el hash |
| T5 · Render | HTML a PNG en los ratios de la matriz, con las WOFF2 de D5 | `render_estatico.py` | cada PNG con su HTML en `assets/src/` y salida 0 |
| T6 · Control de calidad | Los 6 puntos sobre cada pieza; lo que da `falla` se corrige o se descarta; lo que da `revisar` queda para una persona | `qc6.py lote --oferta-dir … --salida …/qc6.json` | 0 `falla` abiertas |
| T7 · Bandeja «por aprobar» | Se arma la lista con el régimen elegido por el dueño (§5) | `tanda.py bandeja --tanda-dir … --regimen total\|muestreo [--confirmado-por-dueno --sellos …]` | `por-aprobar.json` |
| T8 · Mañana (07:00) | El dueño aprueba según el régimen; X1 sella lo que corresponda; lo aprobado entra a `paquete.json v(n+1)` (o al banco de suplentes). **Nada se carga a Meta desde la tanda**: D7 carga por la tarde, en pausado | `validar_d6.py todo`, `ganchos.py marcar --estado aprobado\|usado --x1 …` | piezas aprobadas con `x1_ref` |

Regla de horario `[P 30:41]`: **de noche se produce, a la tarde se carga.** La tanda termina en «por aprobar»; la carga (D7) es otro proceso en otra ventana.

## 4. Qué entra en una tanda y qué no

Entra: estáticos Ruta A (imagen con pregunta, relevo con otra apertura, ganador traducido, variantes de ángulo con el cuerpo ya aprobado). No entra: video, voz, avatar, música, cualquier cosa que gaste créditos, ángulos que `oferta.angulos[]` no traiga (se piden a D3), claims nuevos, ofertas en rojo, y salud o relaciones sin las reglas de su nicho. Si `n_anuncios_max < campana.n_anuncios_min` (SKILL paso 3), la tanda no corre.

## 5. Régimen de aprobación (lo elige el dueño; este documento no lo decide)

El informe (B1-15) deja dos opciones. `tanda.py bandeja` implementa las dos y **no tiene valor por defecto**: `muestreo` se rechaza sin `--confirmado-por-dueno`.

| | **Opción A · Aprobación total** | **Opción B · Muestreo con sello de X1 por plantilla** |
|---|---|---|
| Quién mira | El dueño ve **cada** pieza en «por aprobar» (la pantalla de la fuente lo muestra `[P 30:37]`) | El dueño ve lo que `qc6` marca (`revisar`), las piezas de plantillas sin sello vigente y una muestra (`muestreo_tanda_pct`); el resto queda `lista_para_sello_x1` |
| Lo que habilita activar | Aprobación del dueño + sello de X1 del paquete | El sello **vigente** de X1 sobre la **plantilla** (verificado por el motor, no por este script) + `qc6` en ok + lint de claims verde |
| Ventaja | Cero riesgo de rechazo por algo no visto | Noche sin humano; coherente con J2 (autonomía) y con «de los creativos ya ni me los muestra» `[V 49:00]` (ilegible) |
| Riesgo | El dueño se vuelve el cuello de botella (5-10 piezas por idioma y por día) | Se aprueba sin ver: un defecto que `qc6` no detecta (cara mal hecha, logo en una imagen, matiz torpe del idioma) llega a Meta con la cuenta única |
| Falta construir | Nada (hoy funciona) | `gates.json` (gate de la tanda), qué cubre exactamente el sello por plantilla (S-A y X1), verificación en `engine/guard.py` (S-B) |
| Recomendación de S-C | **Empezar por A.** Pasar a B cuando haya varias tandas seguidas con `qc6` sin falsos y el dueño haya visto qué se le escapa | |

**El pedido al dueño** (copiar y pegar; también en `PEDIDOS.md` #2): *«¿Cómo quieres aprobar la tanda diaria? A) la veo toda cada mañana; B) solo veo lo que el control automático marca y una muestra (indica el %), y lo demás sale con el sello de X1 por plantilla. ¿Y cuántos candidatos por idioma y por día (entre 5 y 10)?»* Mientras no responda: **A**.

## 6. Límites y estado

Todo es `[SUPUESTO]` hasta una corrida real: el número de piezas por tanda y la proporción entre relevos, ángulos y traducciones (la fuente no las da: A.4), el umbral de «cansado» y quién lo dispara (D8, B1-19), y si la carpeta exige clic del dueño. Ruta A necesita Chrome en la máquina que corra (SB-18 en `dependencias.md`). La tanda nunca corrió con una oferta real (B1-24); `tanda.py`, `qc6.py` y `ganchos.py` están probados en `tests/creativos/`.
