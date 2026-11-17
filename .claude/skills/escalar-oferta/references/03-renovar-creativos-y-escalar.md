# Renovar creativos y escalar presupuesto (pedido del dueño, 2026-11-12)

**Ritmo (regla R9, 13-nov):** a las ofertas que pegan se les hace una ronda de 10 **todos los días**, sola, con la tarea «renovacion-diaria» (`05-renovacion-diaria.md`). Esta guía es el cómo de cada paso. El presupuesto ya no se sube en la renovación: desde el 13-nov lo sube la vigilancia de cada hora por ROAS (E1-E3, `04-vigilancia.md` paso 7, en el momento). Las R5, R6 y R8 propuestas quedaron reemplazadas.

Cuando una oferta gana (Oferta B: CPA de US$ 7,62 contra un equilibrio de 13,22), el dueño pide:
- **10 creativos 100 % nuevos** (dueño, 15-nov; antes 7 iteraciones del ganador + 3 del referente): primero los mejores anuncios del referente modelados y mejorados (`ranking_referente.py`), después conceptos totalmente nuevos desde los ángulos y problemas de la landing. El detalle está en `05-renovacion-diaria.md` §1.
- ~~**Presupuesto:** +30 % a la CBO.~~ (Obsoleto: lo decide la escala por ROAS, E1-E3.)
- **Un conjunto nuevo** en la misma CBO con los 10 anuncios y **siempre límites de gasto: mínimo 10 % y máximo 20 %** del presupuesto de la campaña (dueño, 15-nov; antes, solo mínimo del 20 %), para que Meta le dé presupuesto y los anuncios viejos no se lleven todo. Regla del dueño (13-nov): en toda renovación que agregue un conjunto a una CBO. Lo deja puesto el agente; nunca queda como pendiente del dueño (paso 6).
- **El conjunto nuevo sale a las 00:00 del mercado.** (Los cambios de presupuesto por ROAS van en el momento: regla E1-E3.)

Modelo: `ofertas/_borrador-oferta-b/06-creativos/revision-r3/por-que-gano-B01.md` y los scripts `*_r3.py`.

1. **Desarmar el ganador con datos de Meta:**
   - gasto, compras y retención (25/50/75/100 %) contra el segundo;
   - edad y sexo de quien compra (`breakdowns: ["age","gender"]`);
   - su esqueleto, tramo por tramo: gancho, consecuencia, mecanismo, momento del producto, páginas, cierre.
2. **Mirar qué itera el referente.** En la Biblioteca (web.facebook.com, orden por impresiones), bajar los 5 anuncios de su producto con más impresiones que no estén en la muestra:
   - transcribirlos con `whisper-cli`;
   - armar una hoja de fotogramas con ffmpeg.
   - El 12-nov, su anuncio con más impresiones reusaba la misma píldora que nuestro ganador con otra locución: confirmó el plan.
3. **Iteraciones: cambiar una cosa grande por video:**
   - el gancho (sin salir del tema del ganador), la voz o la píldora, o el formato (lista);
   - mantener el esqueleto y la duración;
   - abrir siempre con video, nunca con una imagen quieta: imagen inicial con Nano Banana y clip con Kling.
   - Si el ganador ya tiene una buena apertura, una o dos iteraciones pueden reutilizarla.
4. **Nuevos:** el gancho y la estructura de un anuncio del referente no modelado, con nuestra voz. Si el referente habla en primera persona («yo perdía pacientes»), pasarlo a segunda persona. Clasificar antes la etapa de esa pieza del referente (`modelar-y-lanzar-oferta/references/08-creativos.md` §1.3): mientras el conjunto nuevo sea abierto (público frío), abre con gancho aunque el original sea de cierre («nombre + precio»); el precio va en el texto.
5. **Revisar los fotogramas antes de subir: ningún texto tapa una cara.** Regla del dueño del 12-nov: «cuando se incluye un abridor que contiene una cara o una persona, no taparle la cabeza».
   - **Qué no se tapa nunca:**
     - la cabeza de nadie: la psicóloga hablando, el adolescente, alguien de espaldas o con capucha, una persona chica al fondo;
     - ni con el gancho (la píldora) ni con el subtítulo.
   - **Por qué pasa:** la píldora va fija con su centro al 40 % de la altura (`PILD_Y` en `montar.py`). En un encuadre vertical, ahí quedan casi siempre los ojos. Y como dura toda la apertura, cruza dos a cuatro planos.
   - **Cómo se evita, en este orden:**
     1. **Al escribir el prompt de la imagen inicial (Nano Banana),** cuando el plano de apertura tiene una persona: pedir que la cabeza quede en la mitad de abajo, o fuera de la franja del 30 al 50 %, y que quede pared, ventana o estante libre detrás del texto. Lo mismo en todos los planos que cruza la píldora.
     2. **Al montar,** si un plano igual tiene la cara en esa franja: mover la píldora de ese plano a un hueco libre, arriba (≈ 20 %) o abajo (≈ 62 %) con una píldora de dos líneas. La zona permitida va del 14 % de arriba hasta el subtítulo. Si no hay hueco, cambiar el plano por otra toma de la apertura.
     3. **El subtítulo (centro en 1400 px, ≈ 73 %):** no puede caer sobre la boca ni la barbilla. En un primer plano de alguien hablando, la cara entera va por encima del 60 %.
   - **Lo mismo con lo que nombra la voz:** el texto no tapa la hoja, la tarjeta ni las manos que la muestran mientras se habla de eso.
   - **Cómo se comprueba:**
     - Hoja de contacto de la apertura más densa que la de siempre: un cuadro cada 0,5 s en los primeros 3 s y cada 1,5 s hasta que aparece el producto. Con un cuadro cada 3 s se escapan cortes enteros.
     - Mirar cada cuadro en el que hay una persona: ojos y boca tienen que verse enteros.
     - Anotar en `revision-r<n>/cortes.md` una línea por anuncio (ok, o qué plano se corrigió).
     - Si se quiere automatizar: el detector de caras de OpenCV (ya está en el `.venv` del montaje) sobre esos cuadros, cruzado con la caja de la píldora y la del subtítulo. Es una ayuda; la mirada sigue siendo obligatoria.
   - **Caso real: la ronda 3 de Oferta B (12-nov).** En 6 de los 10 anuncios la píldora tapaba la cabeza de alguien en la apertura, y en otro la rozaba:
     - C06 es el peor: a los 3 s hay un primer plano de la psicóloga hablando, con la píldora sobre los ojos; a los 6 s tapa al adolescente;
     - C01 y C02: la cara de la psicóloga a los 6 s;
     - C03: el adolescente en el auto (0-3 s) y la mujer en la puerta (6 s);
     - C08: la mujer a los 6 y a los 9 s;
     - C10: el adolescente con capucha a los 3 s y la mujer a los 6 s;
     - C04: la píldora roza las cabezas de los dos, al fondo, a los 6 s.
     - Esa misma noche el dueño pidió rehacerlos «si te da el tiempo» y dejarlos programados igual: se rehicieron C01-C04, C06, C08 y C10 sin regenerar video, solo moviendo la píldora plano por plano (`AJUSTE_PILDORA` en `montar_r3.py`: arriba ≈ 20 % o abajo ≈ 62 %, píldora de dos líneas). (Antes decía «no rehacerlos»: obsoleto.)
6. **Meta:**
   - subir videos y miniaturas con `ads_create_upload_url` + POST + `ads_finalize_upload`; esperar a que el video esté `ready`;
   - miniatura propia (primer cuadro, 1080×1920), porque la de Meta sale de 160 px;
   - crear el conjunto copiando la segmentación y el objetivo del conjunto ganador, con `start_time` a las 00:00 del mercado.
   - **Límites de gasto: mínimo 10 % y máximo 20 % (obligatorio; dueño, 15-nov: «Mín 10 % · máx 20 %»).** El máximo evita lo de la R3 de Oferta F del 15-nov: con señales tempranas (clics y checkouts) Meta le dio 94 USD en un día al conjunto nuevo, por encima del mínimo, y no vendió. El mínimo Por API (`daily_min_spend_target` en USD), Meta lo rechazó siempre: «Minimum Spend Limit Is Higher Than Campaign Budget», con 13 y con 10 USD, aun con 53 USD libres del día. Se pone en el **Administrador de anuncios**, en el navegador donde esté abierta la sesión de Meta:
     1. abrir el conjunto (Editar);
     2. ir a «Presupuesto y calendario» → «Límites de gasto de conjuntos de anuncios»;
     3. tildar «Define un límite de gasto mínimo o máximo para este conjunto de anuncios»;
     4. elegir valores porcentuales;
     5. «Mínimo diario promedio» **10 %** y «Máximo diario promedio» **20 %**;
     6. **Publicar**.
   - Comprobar por API: `ads_get_ad_entities` del conjunto con `daily_min_spend_target` y `daily_spend_cap`. Tienen que dar el 10 % y el 20 % del presupuesto de la CBO (6,50 y 13 USD con 65). Anotarlo en `anuncios.json`.
   - Si el presupuesto del día ya se gastó, Meta puede rechazar el mínimo hasta las 00:00. En ese caso: activar los anuncios (entran en revisión), dejar el conjunto en pausa y, a las 00:00, subir el presupuesto y poner los límites (10 % y 20 %), las dos cosas en el Administrador (`08-cambios-en-meta-sin-pausa.md`: por `ads_update_entity` la campaña se pausa), y activar el conjunto.
   - Programar las dos cosas con una tarea de la sesión (CronCreate, una sola vez, hora local).
7. **Anotar** IDs, gasto de Kie y estado en `07-campana/anuncios.json`, `estado.md` y el libro de tests. En el libro, sumar la ronda a `renovaciones` del test (ronda, inicio a las 00:00 del mercado, estado, anuncios, conjunto, nota): de eso sale la etapa «Renovación programada» → «Renovando» del panel (`01-revision-diaria.md`).
