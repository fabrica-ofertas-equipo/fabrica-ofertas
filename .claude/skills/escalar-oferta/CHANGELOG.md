# CHANGELOG · escalar-oferta

## 0.18.0 · 2026-11-17 · Todo en neto, ROAS de 3 días y decidir con el rango

El dueño, al ver que un anuncio puede empatar un día y ser rentable en el tiempo, decidió «usar neto» y aprobó los cuatro puntos de `docs/ruido-y-confianza-2026-11-17.md`.

- `scripts/medir_ruido.py` (nuevo, solo lee) mide cuatro cosas: si un día de un anuncio predice el siguiente, la dispersión de las compras, las decisiones de la escala contra sus 24 h siguientes y las compras de Meta contra la tienda. Primera medición: correlación −0,12 entre un día y el siguiente, y Meta 0,85 de la tienda.
- `dashboard/negocio.py`:
  - `neto_por_comprador_ventana` es el valor por comprador del sistema: neto, 7/14 días o historia, sin cruzar `backend.desde` ni `ficha.cambios_embudo`. La oferta lo expone en `valor_comprador`.
  - `roas_estimado` calcula el ROAS acercado a lo previo, con piso y techo del 80 %.
  - `agregar_roas_3d` arma la columna «ROAS 3 d» del panel.
- `escalar_presupuesto.py` decide en neto: 1,65 / 1,4 / 2,75, con el ROAS acercado a los 3 días anteriores de la campaña (`cpa_previo_de`). Para subir pide además que el piso del rango sea ≥ 1.
- `plan_renovacion.py`: ganador con valor neto (> 1,85).
- `congelamiento.py`: R16 con CPA ≤ 0,54 × valor neto.
- `corte_post_test.py`: R4b con el valor del sistema.
- `reglas.json`: `escala.por_campana`, `renovacion.ganador` y `congelamiento` pasados a neto.
- Tests actualizados en `test_escalar_presupuesto.py` y `test_plan_renovacion.py`; tests nuevos en `test_negocio_neto_ventana.py`.

## 0.17.0 · 2026-11-17 · Renovación en CBO aparte (R9 v2)

Dueño, con los datos de Oferta F ES: los conjuntos de renovación dentro de la CBO madre no funcionaron (R3: US$ 190, 2 compras, CPA 95; en Oferta B Meta casi no les dio gasto) y la CBO aparte de variaciones de B08 sí (US$ 360, 10 compras, CPA 36, y encontró a D4). Criterio de pockets y manuales tomado de Santiago Bilbao (transcripciones en `empresa/investigacion/2026-11-13-bilbao/`).

- `reglas.json` → `renovacion` reescrita (copia en `reglas.antes-cbo-diaria.json`): CBO diaria 3 tickets con corte 1,5; ganador = 3+ compras con ROAS > 2 en 48 h; iteraciones con lectura de 24 h, descanso de 3 días tras 2 rondas sin rendir, fatiga = CPA subiendo 3 días; pocket = máx(2 tickets, 3 × CPA medio), corte 1, por familia hasta 5; manual cada 5 ganadores sostenidos en pocket (cost cap CPA medio × 1,3, bid cap ticket × 1,3).
- `scripts/plan_renovacion.py` nuevo: decide Nuevos, Iteraciones, pockets, manuales y límites a quitar en la madre. Familias por código («VB D4 | B08 …» es hija de B08). Pruebas `tests/escalar_oferta/test_plan_renovacion.py`.
- `fotos_campanas.py`: roles `nuevos`, `iteraciones`, `cost_cap`, `bid_cap`; las campañas diarias detectadas solas llevan su corte (`CORTE_DIARIA`).
- `vigilar_corte.py`: el corte por campaña ahora también rige en post-lanzamiento, solo para las campañas con `corte_tickets` (la madre y las viejas no).
- `05-renovacion-diaria.md` reescrita (§0, §1d iteraciones, §3 campaña nueva, §3b pocket, §3c manuales); tareas `renovacion-diaria` y `vigilancia-ofertas` actualizadas.
- Oferta F: R6 (quedó «produciendo» sin producir desde las 10:34) se canceló; sale R7 como CBO Nuevos el 18-nov.
- Respaldo en la nube genérico: `reglas.json` → `cortes_por_rol` es el único lugar del corte por campaña (`vigilar_corte.corte_tickets_de`, `limites_por_campana`); `plan_corte.py` manda `limites` (una entrada por campaña con su corte, en cualquier fase) y la nube (`corte.mjs` → `decidirLimites`, publicada) solo suma y pausa, sin conocer roles: un tipo de campaña nuevo queda cubierto con su número en `reglas.json`. La nube todavía no tiene `META_GESTION_TOKEN`: anota, no pausa.

## 0.16.0 · 2026-11-17 · Corte de respaldo en la nube y repaso de robustez

La noche del 16 al 17-nov la iMac se pasó a un Wi-Fi público sin internet y ninguna tarea corrió durante 8,5 h: Oferta M gastó US$ 57,08 con corte en 29,85. El dueño eligió «Respaldo si cae la Mac». Repaso completo en `docs/robustez-2026-11-17.md`.

- Nube (`infra/workers/vivo/src/corte.mjs`, publicado): si la vigilancia no late hace más de 30 min, aplica el corte del día 1 (test entero, segunda oportunidad y corte por campaña de las réplicas) con su lectura de Meta y las ventas del webhook, y **solo pausa**. Sin el secreto `META_GESTION_TOKEN` anota lo que habría pausado (`resultado: sin_token`). Pruebas: `test/corte.test.mjs` (caso Zihin).
- Mac: `scripts/plan_corte.py` arma el plan desde el libro; `nube_sync.py` lo sube cada 5 min y avisa por iMessage, en avisos.jsonl y con un pendiente en el libro cada corte que haga la nube (la vigilancia completa «Al apagar»).
- `hay_trabajo.py` deja `pulso_vigilancia.json` al arrancar cada vuelta: las vueltas sin trabajo no dejan latido y la nube habría creído caída una vigilancia sana.
- `fotos_campanas.py`: «variaciones (1-1-10)» salía pocket porque contiene «1-1-1» (DE, 16-nov); las campañas de réplica detectadas solas llevan su corte (pocket 1, variaciones 1,5). Prueba `tests/escalar_oferta/test_rol_campanas.py`.
- Guardián (`infra/cuentas/guardian.py`): comprueba internet antes de culpar a la cuenta de Claude.

## 0.15.1 · 2026-11-16 · Rechazados: solo se apelan

Dueño, al ver que en la pocket de GB se habían creado V1b y copiado E6 cuando rechazaron V1 (y V1 ganó la apelación): «cuando se rechaza un ad, no se crean nuevos de manera automática… a lo sumo el rechazado se apela y listo y si lo rechazan esa campaña no sale (en este caso que era 1 1 1); si rechazan ads en otra campaña donde hay otros, sale igual la campaña».

- `reglas.json` → `lanzamiento.rechazados` (apelar 1 vez, nunca reemplazar, mínimo 1 no rechazado); se elimina `rechazos_para_no_activar` (el «5 o más no se activa»).
- `control_previo.py`: frena solo si no queda ningún anuncio no rechazado; el mínimo de anuncios cuenta los cargados (`anuncios.previstos`, 1 en una pocket 1-1-1). Tests nuevos.
- `salud.py` (`REVISAR_RECHAZOS`), `04-vigilancia.md`, `02-decidir.md` (L3), la tarea `vigilancia-ofertas` y las guías de `modelar-y-lanzar-oferta`: apelar una vez, no corregir ni reenviar.

## 0.15.0 · 2026-11-16 · Escala por campaña con el AOV de la tienda

El dueño escaló a mano todo el día (la escala veía una campaña por oferta y le atribuía el ROAS de toda la tienda). Su regla: «surfeando lo que tiene buen CPA y mantiene también ROAS, ROAS comparado con el AOV de la tienda… por arriba de 1,8… pero a ojo». Análisis en `docs/criterio-de-escala-2026-11-16.md`.

- `escalar_presupuesto.py` reescrito (`--auto`): cada campaña activa se decide sola con ROAS con AOV desde su último cambio; surfeo ≥ 1,8 con dosis por compras (+20/30/40 %, +10 con ROAS ≥ 3); bajada < 1,5; nuevos NO_GASTA, TARDE y EN_TEST. Copia anterior en `escalar_presupuesto.py.antes-por-campana`.
- `fotos_campanas.py` nuevo: fotos de cada campaña cada 5 min y registro de todo cambio de presupuesto o estado con autor (sistema / a mano) en `presupuesto_eventos.jsonl`. Sembrado con el historial de actividad de Meta del 14 al 16-nov.
- `nube_sync.py`: `meta_vivo.json` trae todas las campañas de cada oferta (antes solo la principal) y llama a las fotos.
- `reglas.json` → `escala.por_campana`; referencia `09-escala-por-campana.md`; `04-vigilancia.md` paso 7 y la tarea `vigilancia-ofertas` actualizados; `07` marcada como reemplazada.
- Panel: «Campañas en Meta» y «Línea de tiempo del presupuesto» en la ficha de cada oferta.
- Campañas dinámicas: `nube_sync.py` agrega sola a su oferta cada campaña nueva «MERCADO | oferta | …», pone al día estado y presupuesto de las conocidas y deja en `campanas_sin_oferta.json` las activas que no encajan; el panel oculta las apagadas en un grupo plegado (09 §5).
- Regla del dueño: toda campaña nueva se nombra «PAÍS | Oferta tal cual en el libro | tipo»; `control_previo.py` no activa sin `campana_nombre` que la asigne a su oferta (control 9) y `fotos_campanas.py oferta --nombre` lo comprueba para las que no pasan por el control (pocket, variaciones, réplicas, escala).

## 0.14.0 · 2026-11-15 · R9: renovaciones 100 % nuevas

El dueño: «las renovaciones en la campaña CBO madre ya no son más del 70 % variaciones del que funciona y 30 % nuevos. Haremos 100 % renovaciones nuevas, basándonos primero en los mejores anuncios de la referencia para modelarlos y mejorarlos… y si no, conceptos totalmente nuevos, enfocándonos en los ángulos y problemas que planteamos en la landing».

- `05-renovacion-diaria.md` §1-2 reescritos: 1a referente primero (inventario de la Biblioteca de hoy, `ranking_referente.py`, modelar y mejorar en orden, saltear lo no modelable), 1b conceptos nuevos desde la landing (`angulos.md`, otro ángulo y otro formato cada uno), 1c lo nuestro solo para no repetir. `origen` de cada anuncio en `anuncios.json`; ids usados en `06-creativos/referente-usados.json`.
- `scripts/ranking_referente.py` nuevo (con `--probar`).
- `ganadores.py` ya no se usa en R9 (queda para réplica y pocket). Tarea `renovacion-diaria`, `03`, `02` (R9), `metricas_embudo.py`, mapa del panel y agenda actualizados.

## 0.13.3 · 2026-11-15 · Límites de gasto 10-20 % en los conjuntos nuevos

La renovación R3 de Oferta F gastó 96 USD sin ventas (11 checkouts); Meta le dio 94 USD en un día, por encima del mínimo del 20 %. UTM y atribución revisadas: bien (22 ventas, todas del conjunto original). El dueño: «Mín 10 % · máx 20 %».

- Cada conjunto nuevo de una renovación lleva mínimo 10 % y máximo 20 % del presupuesto de la CBO (03 paso 6, 05 pasos 4-6, 04 límites pendientes, 08, SKILL.md, tarea renovacion-diaria, mapa del panel). R9b quita los dos límites a los dos días.
- Aplicado a la R3 de Oferta F: 26,80 y 53,60 USD (CBO 268), comprobado por API.

## 0.13.2 · 2026-11-15 · Limpieza de intermedios y control de disco

El disco tenía 31 GB libres y `ofertas/` había pasado de 19 a 37 GB en un día (cada oferta 1,5-5 GB). El dueño eligió «Borrar intermedios».

- `scripts/limpiar_oferta.py` nuevo (`plan`, `aplicar --papelera|--borrar`, `espacio`), con `tests/escalar_oferta/test_limpiar_oferta.py`.
- «Al cerrar», paso 9: borrar los intermedios de la oferta cerrada. Vigilancia, punto 2e: espacio en disco en toda vuelta completa (bajo 20 GB limpia las cerradas y avisa).
- Primera pasada a mano: 8 ofertas apagadas, 9.616 archivos, 8,5 GB a la Papelera (`~/.Trash/limpieza-20261115-1643/`).
- El respaldo con reglas de Meta queda en «No por ahora» (dueño, 15-nov).

## 0.13.1 · 2026-11-15 · R16 solo en la entrada; régimen propio para las validadas

El dueño aprobó «separarlas» después de simular la R16 sobre Oferta F: con dos días a CPA = 60 % del ticket (ganando ~US$ 200/día) la congelaba y frenaba renovación y escala, y en una fatiga cortaba los creativos y bloqueaba la bajada del 30 %.

- `congelamiento.py`: `validada()` (ya escaló o una ronda entregó 24 h), `ventana_cerrada()` (3 días cerrados de la cuenta, sin el día en curso) y `renovacion()` (la usa `ofertas_que_pegan.py`). Las validadas nunca se congelan: renuevan con ROAS neto ≥ 0,95 y en empate (0,95-1,20) la decisión es BACKEND_AGRESIVO (sumar 2.º bump y hasta 4 upsells sin frenar nada).
- `ofertas_que_pegan.py`: «pega» sale de `renovacion()`; ya no mira el acumulado desde el inicio después del test.
- `reglas.json` → `congelamiento.validada`, `ventana_dias_cerrados`; guía 02; vigilancia paso 3c; panel.

## 0.13.0 · 2026-11-15 · R16 congelamiento en empate

Nació de Oferta G (FR): 3 ventas en el test con CPA ≈ lo que deja (ROAS neto 0,99) y la renovación anticipada ya produciéndose porque bastaba «CPA ≤ equilibrio». Dueño: renovar y escalar «cuando el CPA es la mitad o menos que el AOV»; entre eso y ROAS neto 0,95, con ≥ 3 ventas, congelar un día con backend agresivo; «otro día congelada» si sigue igual.

- `scripts/congelamiento.py` (nuevo): bandas renovar / congelar / normal, ciclo del campo `congelada` del libro (1 día, 2.º día, después el dueño), `evaluar --aplicar`.
- `ofertas_que_pegan.py`: «pega» y la renovación anticipada piden CPA ≤ ticket promedio / 2; una oferta congelada no se renueva.
- `escalar_presupuesto.py`: decisión CONGELADA (no sube ni baja).
- `reglas.json` → `congelamiento`; guía 02 (R16, R7 reemplazada, R9); tarea vigilancia-ofertas paso 3c; panel (`flujo.js`).

## 0.12.3 · 2026-11-15 · ningún cambio en Meta que apague una campaña que corre

Pasó el 15-nov: al surfear Oferta F de 211 a 277 USD/día con `ads_update_entity`, la herramienta pausó la campaña (`status_forced_to_paused`) y se reactivó a los segundos. Dueño: «una campaña que está gastando y está prendida no puedes apagarla y prenderla el mismo día. La puede romper».

- Nueva guía `references/08-cambios-en-meta-sin-pausa.md`: presupuesto de la CBO, mínimos del 20 % y cualquier edición de algo activo se hacen en el Administrador de anuncios y se comprueban por API (`daily_budget` y `ACTIVE`). Sin sesión de Meta, no se cambia el presupuesto en esa vuelta y se avisa.
- Freno en código: hook `.claude/hooks/meta_sin_pausa.py` (registrado en `.claude/settings.json`) rechaza `ads_update_entity` salvo `{"status":"PAUSED"}` (o ARCHIVED/DELETED) y descartar un borrador.
- Guías 03 (subida a las 00:00), 04 (paso 7 escala y paso 8 mínimos) y 05 (quitar mínimos, R9b) apuntan al Administrador. Tropiezos actualizado.

## 0.12.2 · 2026-11-15 madrugada · verificar el funnel tras activar

Pedido del dueño (14-nov, «muchas visitas pero ningún checkout»): revisar todas las landings activas y, de ahí en más, «una vez que se lanza una oferta nueva y… a los 10 minutos o 15 minutos que se activan los anuncios, volver a verificar todo el funnel… desde el anuncio al funnel y al checkout».

- Revisión: las 4 ofertas activas (Oferta F, Oferta G, Oferta H, Oferta I) cargan y llevan al checkout. Falla encontrada: los 6 checkouts de Oferta H y Oferta I (duplicados de Oferta F) mostraban la imagen del producto rota (archivo inexistente en la copia). Se subió el mockup de cada nivel y se comprobó.
- Nuevo `scripts/verificar_funnel.py`: `pendientes` (inicio del test y de cada renovación, de 10 min a 6 h, sin registro en `verificaciones.jsonl`) y `correr` (prueba del funnel con `probar_funnel.py`, píxel bloqueado, más la lectura de Meta e Impultienda: anuncios entregando, URL de los anuncios, clics que no llegan, tiendas que no pueden cobrar). Decide OK, FALLA (aviso urgente y arreglo en la vuelta) o ESPERAR.
- `hay_trabajo.py`: paso 8 «verificar funnel tras activar», también en las vueltas rápidas. Guía 04, punto 11; tarea `vigilancia-ofertas` actualizada.
- `control_previo.py`: control 8, sin la prueba del funnel (`verificar_funnel.py --antes`) o con fallas no se activa.
- Tests: `tests/escalar_oferta/test_verificar_funnel.py`.
- Mapa del panel: regla L3b.
- La prueba ya no altera las estadísticas ni manda eventos a Meta (`probar_funnel.py` bloquea visitas, visitantes en vivo y la API de conversiones de Impultienda): las visitas se pueden leer antes o después.

## 0.12.1 · 2026-11-14 noche · repaso de fallas del día

- **Mínimos pendientes de renovación:** `hay_trabajo.py` buscaba `minimo_pendiente` en la fila del test y el campo vive en cada entrada de `renovaciones`: el 20 % de la R4 de Oferta B nunca se puso. Ahora mira las dos (prueba nueva en `tests/escalar_oferta/test_backend_anticipado.py`).
- **Avisos que no llegan:** las tareas programadas no pueden prender el Control remoto y PushNotification devolvía «not sent», pero `avisos.jsonl` quedaba en `enviado: true` y la ventana anti-repetición trababa el reintento. Nuevo `avisos.py no-llego <clave>` (el próximo intento vuelve a salir) y `avisos.py sin-entregar` (los que no llegaron en 24 h, al resumen diario). El paso está en todas las guías y tareas que avisan.
- **Píxel propio también en réplicas:** `control_previo.py` frena (antes solo avisaba) si el píxel aparece en otra fila del libro; `05-renovacion-diaria.md` ya no prevé píxeles prestados. Oferta H, Oferta I y Oferta G pasaron a su píxel propio con conjuntos nuevos (14-nov 21:50 ART).

## 0.12.0 · 2026-11-14

Pedido del dueño: «agregar a la skill sistema o criterio de cuándo se apaga la campaña y la oferta en sí, también archivar la tienda en Impultienda, para que solo queden las que están activas». Respuestas: «72 h después» y «cortes por regla y a mano».

**R15: apagar no es cerrar (`scripts/cierre_oferta.py`, guía 04 «Al cerrar»)**
- Apagar = pausar la campaña en Meta, en el momento (R1, R1b agotada, R4, R4b o el dueño a mano). Sin cambios.
- Cerrar = 72 h después del apagado: la oferta pasa a `estado: "cerrado"` con `cierre {cuando, regla, tiendas_archivadas}` y cada tienda suya se archiva en Impultienda (Configuración → Zona de peligro → «Eliminar tienda»; archiva, no borra, y el dueño la restaura desde «Tiendas archivadas»). La campaña queda pausada en Meta; fan page y píxel no se tocan.
- No cierran: pausas técnicas (`pausa_tecnica` o `apagado.tecnico`), `cierre.no_archivar`, una venta posterior al apagado (RETENER, se avisa) ni una pausa sin `apagado` (SIN_MOTIVO, se avisa). Una tienda compartida con otro test vivo no se archiva.
- El conector de Impultienda no archiva: se hace con el navegador integrado; se comprueba con `impultienda_listar_tiendas incluir_archivadas`.
- `hay_trabajo.py` da el paso 7 «cerrar y archivar»; la tarea `vigilancia-ofertas` tiene el punto 7. `reglas.json` → `cierre.horas_espera = 72`. Mapa del panel: regla R15.
- «Al apagar» exige `apagado` completo (cuándo, regla, por, motivo) y `pausa_tecnica` para lo que se arregla. Oferta E había quedado sin `apagado`: se completó desde `vigilancia.jsonl`.
- Soporte: un «no me llegó» de una oferta cerrada va al dueño con la ruta del PDF (la tienda archivada ya no abre en su subdominio).
- Pruebas: `tests/escalar_oferta/test_cierre_oferta.py` y `cierre_oferta.py --probar`.
- Calendario al publicar: El Museo se cierra desde el 15-nov 23:20 y Caminho desde el 16-nov 09:08 (sus tiendas ya estaban archivadas a mano: solo se registran); Oferta E, Oferta D y Oferta B, el 17-nov.

## 0.12.0 · 2026-11-14

Pedido del dueño: «en Impultienda, en ofertas de 3 tiendas, no marca por cada una correcto el CR; hay que juntarlas y sacar 1 KPI… y el consolidado de visitas, checkouts y compras, como tiene Impultienda con las barritas».

**Embudo consolidado de las tiendas (`scripts/embudo_tiendas.py`)**
- `pedidos` dice qué tienda y qué día leer (hoy para las ofertas andando; días de pauta que falten o hayan quedado parciales); `cargar` escribe una fila por día con el detalle por tienda y el total desde el inicio.
- Ids de tiendas en `ofertas/_funnels/tiendas_ids.json` (subdominio → store_id, archivadas incluidas).
- La vigilancia lo corre en cada vuelta completa (paso 2 b2). Cargado hacia atrás para todas las ofertas el 14-nov.
- Panel: KPI «CR de la tienda» junto a ventas y facturación, y el embudo con barras arriba, con el detalle por tienda (y el CR que muestra Impultienda de cada una, para ver por qué no sirve).

## 0.11.0 · 2026-11-14

Pedido del dueño: «puede ser que tengamos muchos winners y tengamos que iterar entre todos… más winners que anuncios que vamos a sacar… hacerlo robusto, pero seguir dándole con fuerza a iterar sobre lo que más está funcionando».

**Reparto de las iteraciones entre ganadores (`scripts/ganadores.py`, guía 05 §1-2)**
- Antes: un solo ganador = más compras en 3 días (1 compra contra 0 alcanzaba) y las 7 iteraciones iban ahí.
- Ganador = 2+ compras con CPA ≤ equilibrio; promete = 1 compra bajo el equilibrio o 2+ hasta 1,2 × equilibrio. Puntaje = compras × eficiencia (equilibrio / CPA, tope 2).
- Un ganador: 5 + 2 al mejor que promete. Varios: hasta 4 ramas según puntaje^1,5, el primero con al menos 3 y nunca menos que otro. Más ganadores que lugares: los 4 de más puntaje; el resto sigue corriendo sin tocar. Sin ganador: 4 + 3 entre los que más prometen.
- Con menos de 3 compras en 3 días mira desde el inicio; un anuncio en varios conjuntos suma.
- Pruebas: `tests/escalar_oferta/test_ganadores.py` y `ganadores.py --probar`.

## 0.10.0 · 2026-11-14

Pedido del dueño: «Oferta F va 100 %… hasta las 00 que pasa a la siguiente fase no renueva… el criterio es 2 o 3 horas antes, si claramente ya cumplió las expectativas, ya preparar las renovaciones y cargarlas». Respuestas: «3+ ventas y CPA bajo equilibrio» y «apenas esté listo».

**Renovación anticipada (`scripts/ofertas_que_pegan.py`)**
- Una oferta en test con 3 o más ventas y CPA ≤ equilibrio ya pega (`anticipada`).
- Su primera ronda se produce en las 16 h previas al fin del test y sale a la 00:00 en que termina el test.
- Si ya no llega a esa hora (`salida_inmediata`), sale apenas está lista.
- Si el test terminó sin ninguna ronda hecha, la primera también sale apenas está lista, sin esperar la 00:00 siguiente.
- La tarea `renovacion-diaria` aplica `salida_inmediata` en el start_time. Primera corrida: Oferta F, 14-nov 19:10 ART.

**Panel**
- Ficha con los KPI primero: cifras, indicadores, Meta de hoy y hora de los datos. Después vienen la decisión, las métricas, la agenda y el historial.
- KPI nuevos «Ventas» (las reales, con lo que atribuye Meta al lado) y «Facturación».
- La franja de Meta dice «compras según Meta».
- El backend muestra el order bump (`backend.bump`).

## 0.9.4 · 2026-11-14

Pedido del dueño, con Oferta B: «primer día ROAS 1.7, luego renovamos con backend y nunca más ROAS positivo… no tiene más sentido que apagarla». La apagó a mano y firmó la regla con 2 días («me parece bien con dos días»).

- **R4b «el día 1 no se repite»**: la R4 medida sin el día 1 del test. Se apaga si se cumplen las tres cosas:
  - hay backend activo y al menos una ronda de renovación con 24 h de entrega;
  - los días después del test (como mínimo 2; el día en curso cuenta desde el 70 % del presupuesto) suman CPA ≥ 1,5 × lo que deja cada venta;
  - ningún conjunto nuevo vende con ROAS ≥ 1 y 2 compras.
- Motivo: la ventana de 3 días de la R4 incluía el día 1 y tapaba la caída. En Oferta B daba 1,31 × y no cortaba; sin el día 1 da 2,1 ×.
- `scripts/corte_post_test.py` (decide; `--probar` corre 8 casos), `reglas.json` → `post_test.caida_tras_dia1`, guía 04 paso 7b, tarea `vigilancia-ofertas` punto 3b, 02-decidir y el mapa del panel.

## 0.9.3 · 2026-11-14

Pedido del dueño: «el gasto de Claude de 88 % sigue desactualizado… no es en tiempo real en muchos lados».

- El uso de Claude y el estado de la cuenta de Meta se anotaban a mano una vez por día, y el 14-nov la revisión no lo hizo: el panel mostraba 88 %, cuando el uso real era 7 %.
- Ahora la vigilancia los anota en cada vuelta completa (punto 2c). Claude se anota aunque no haya ofertas, con una sola llamada.
- `servicios.json` → `cada_horas`: el panel muestra «leído hace …» y «se lee cada …» en cada servicio, y lo marca «desactualizado» si pasa el doble sin lectura.

## 0.9.2 · 2026-11-14

Pedido del dueño: «en la oferta Oferta F aparecen las ventas pero no el gasto de Meta… siento que el dashboard siempre que lo miro está desactualizado y no me da confianza».

**Causas**
- El panel arma «Hoy» con `historial_diario`, que solo cargaba la revisión diaria. Las ofertas nuevas mostraban ventas con gasto 0.
- Las ventas también entraban solo en la revisión: faltaba 1 de Oferta B y 1 de Oferta F.
- `meta_vivo.py`, la lectura cada 10 min, sigue sin token del dueño.

**Cambios**
- `scripts/historial_meta.py`: carga el gasto por día de Meta (time_increment=1). Si los días cubren toda la pauta, pone también los totales.
- `scripts/ventas_impultienda.py`: suma las órdenes de Impultienda que falten, con neto estimado (`reglas.json` → `impulpay.neto_estimado` 0,919).
- La vigilancia corre los dos en el paso 2 de cada vuelta completa (cada hora).
- Panel:
  - si hay gasto de Meta que no está repartido por día, muestra «Meta sin desglose por día» en lugar de 0;
  - cada fila dice de cuándo es su lectura de Meta, en ámbar con más de 2 h en una oferta activa.

## 0.9.1 · 2026-11-13

Pedido del dueño: «no pusiste cuánto crédito queda en Gemini, no sé cuándo y cómo recargarlo antes de que se quede sin».
- `chequeos_diarios.py`: la prueba de Gemini pasa de «la clave responde» (lista de modelos) a una voz real de una palabra. La lista respondía aunque el saldo prepago estuviera en cero. Los errores se traducen a qué hacer (`motivo_error_gemini`).
- Saldo de Gemini: `chequeos_diarios.py gemini-saldo --usd N`, porque Google no lo da por API. Aviso bajo 5 USD (`reglas.json` → `gemini.saldo_minimo_usd`) o con más de 7 días sin mirarlo.
- Panel, «Servicios y saldos»: cada servicio muestra «Cómo recargar» (`recarga` en `servicios.json`).

## 0.8.2 · 2026-11-13

Pedido del dueño: «¿no sería mejor que sepa cuándo hay un test corriendo? Ahora no tenemos ninguna en test y sigue gastando tokens».
- `scripts/hay_trabajo.py`: filtro previo sin red. Dice qué pasos de la vuelta tocan (0 verificar, 1 corte, 2 salud, 3 escala, 4 mínimos, 5 revisión) o «NADA».
- La tarea `vigilancia-ofertas` lo corre primero. Con NADA deja el latido y termina sin cargar la skill. Con TRABAJO hace solo los pasos nombrados; por ejemplo, sin tests en día 1 no lee el píxel ni corre el corte.
- `references/04-vigilancia.md`: el filtro, al principio de «Cada vuelta».








## 0.10.0 · 2026-11-13 · Reglas centrales, segunda oportunidad y pendientes del dueño

- **`ofertas/_funnels/reglas.json`**: todos los números de las reglas en un solo lugar; los leen `scripts/reglas.py` (vigilar_corte, escalar_presupuesto, control_previo, salud, avisos, chequeos_diarios, cupo_lanzamiento) y `dashboard/negocio.py`. Una prueba comprueba que coinciden.
- **R1b, segunda oportunidad del test** (firmada): +0,5 ticket una sola vez si llega al corte sin ventas con CTR ≥ 1 %, ≥ 8 % al pago y ≥ 3 pagos iniciados. `vigilar_corte.py` decide `SEGUNDA_OPORTUNIDAD`.
- **Píxel sin doble conteo:** la vigilancia usa solo el Purchase del navegador (con CAPI el total cuenta doble: 10 para 6 reales el 13-nov).
- **Tirón:** confirma con la tienda, nunca baja del presupuesto inicial, números redondos.
- `scripts/diagnostico_test.py`: en qué tramo del embudo se cayó cada test que se apaga (solo registra; la búsqueda no se recalibra hasta tener una oferta con ≥ 1.000 USD de ganancia por día).
- `scripts/capi_estado.js` y panel «Lo que espera tus manos»: qué tiendas no tienen el token CAPI, con los enlaces directos a Meta y a cada tienda.
## 0.9.0 · 2026-11-13 · El resto del camino al 100 %

- `scripts/libro.py`: el libro de tests se escribe solo con candado, copia previa y escritura atómica (S38). Probado con 20 escrituras a la vez.
- `scripts/chequeos_diarios.py`: saldo de Kie (S10), comisiones y tipo de cambio (S34), cartera por ROAS neto de 7 días (S23).
- `salud.py`: fan page y píxel restringidos (S12) y sesiones vencidas en el navegador (S37).
- Renovación diaria: si el referente acelera, sus anuncios nuevos son los 3 nuevos del día (S04).
## 0.8.1 · 2026-11-13 · Revisión de coherencia 2026-11-13

Alineado con las decisiones del dueño del 13-nov (informe: `docs/_historial/revision-coherencia-2026-11-13.md`):
- `SKILL.md`: activar un lanzamiento es automático (L3); reactivar sigue siendo del dueño (R12). La tabla de tareas separa la escala por ROAS (vigilancia, paso 7) del cómo de cada renovación.
- `02-decidir.md`: «Lo que todavía no tiene regla» marcado obsoleto (L3, L5, P1-P3 ya existen); ejemplo con R7 en vez de la R5 retirada.
- `03-renovar-creativos-y-escalar.md`: fuera el «+30 % a la CBO» y «R5 propuesta» (lo hace E1-E3 en el momento); los 3 nuevos abren con gancho (etapa del funnel, 08 §1.3); corregido el caso de la ronda 3 (sí se rehicieron 7 anuncios esa noche) y la altura de la píldora (≈ 20 % / ≈ 62 %).
- `04-vigilancia.md`: el paso 9 ya no dice que escalar necesita visto bueno; «no sube presupuestos» salvo E1-E3; cortes de ejemplo con la regla 19/27; el prompt corto nombra salud y escala.
- `05-renovacion-diaria.md`: nombre del conjunto con `<PAÍS>`; presupuesto lo sube la vigilancia (no «R5 propuesta»); etapa del funnel en los 3 nuevos; hoja de contacto densa.
- `01-revision-diaria.md`: «Renovando» dura 1 día (como `negocio.py`); acción sugerida con el ticket del completo y la escala por ROAS firmada; §6b sin «R4 a R9 propuestas».
- `tropiezos.md`: dos enlaces a `12-revision-dia-siguiente.md` (ya no existe) apuntan a sus guías actuales.

## 0.8.0 · 2026-11-13 · Salud, control previo y avisos

- `scripts/salud.py` en cada vuelta de la vigilancia: landing y checkouts caídos 2 vueltas → pausa (y reactiva sola solo lo que pausó por caída), píxel ausente, 10 pagos iniciados sin compra, anuncios rechazados (se corrigen una vez), embudo post-compra sin vistas, cuenta no activa, 80 % del límite de gasto, 3 vueltas sin leer Meta.
- `scripts/control_previo.py`: regla L3, activar sola si pasa (inicio 00:00 en la zona del mercado, con 57 zonas; menos de 5 rechazados; presupuesto de 3 tickets; precio ≥ 19; píxel; fila en el libro).
- `scripts/avisos.py`: avisos al celular sin repetir (urgentes cada 3 h, normales cada 24 h) y latido de cada tarea; resumen del día al celular en la revisión.
- Disputas (P2) en la revisión diaria.
## 0.7.0 · 2026-11-13 · Escala por ROAS y decisiones del dueño

- **Escala por ROAS (E1-E5, firmadas):** +30 % cada 24 h con ROAS 1,75-2,5; surfeo cada 3 h sobre 2,5 (+30 % a +50 %); tirón −30 %; sin techo. `scripts/escalar_presupuesto.py` decide y la vigilancia de cada hora lo aplica en el momento (`04-vigilancia.md` paso 6). Reemplaza las propuestas R5, R6 y R8.
- **R4 firmada** con lo que deja cada venta dinámico: ventas con `tipo` upsell/bump/downsell suman al neto y no cuentan como compradores (`dashboard/negocio.py`, `vigilar_corte.py`).
- **Lanzamiento (L3, L5) firmado:** 2 ofertas nuevas por día mientras el banco tenga 3 listas y haya menos de 8 en test; activar sola si pasa el control previo (inicio 00:00 en la zona del mercado; con 5 o más anuncios rechazados no se activa). La tarea de lanzamiento y el control previo están por construir.
## 0.6.1 · 2026-11-13

Correcciones del dueño a la renovación diaria:
- **Sin tope de créditos por ronda:** «capaz limitamos a crear buenos creativos tan solo por no gastar un poco de créditos más». Se anota el gasto; si el saldo no alcanza, se avisa.
- **R9b: cada conjunto conserva el 20 % dos días enteros** (antes, poco más de uno): «darle solo un día 20 % capaz es poco presupuesto». En el día corren dos con mínimo (40 %) y el 60 % queda libre para lo que vende.
- Si Meta rechaza el mínimo, se marca `minimo_pendiente` y lo pone la vigilancia de cada hora después de las 00:00 (una tarea programada no puede crear otra sin el dueño delante).
## 0.6.0 · 2026-11-13

Regla del dueño: «las ofertas que en principio pegan, como la de Oferta B, hay que renovarle creativos todos los días, 10, … iterar lo que mejor funcionó un % y nuevos otro %, con la regla del 20 % de gasto mínimo en el adset, dentro de la misma CBO».

- **R9 firmada:** renovación diaria de 10 (7 iteraciones del ganador de 3 días + 3 nuevos del referente) en un conjunto nuevo de la misma CBO, mínimo 20 %, a las 00:00. Guía nueva `references/05-renovacion-diaria.md`, script `scripts/ofertas_que_pegan.py` y tarea programada «renovacion-diaria» (10:30 de Argentina).
- **R9b:** solo los dos conjuntos más nuevos llevan el mínimo del 20 % (si no, con un conjunto por día los mínimos pasan el 100 % al quinto día).
- R4 ya no espera a las rondas nuevas (con una por día, nunca cortaría). R7: seguir renovando cada día mientras no llegue a R4. R14 propuesta: pausar conjuntos viejos que ya no reciben gasto.
- Panel: «Renovando» dura un día (antes 3).
## 0.5.0 · 2026-11-13

Pedidos del dueño: «la regla debería tomar en estos casos el del producto principal o completo, que en este es el de 27, para cortar»; «los frenos de 300 y 3000 eliminarlos»; dividir las skills por proceso; «que haya una regla o automatización para cada situación».

- **Ticket del corte = producto completo** (el precio en USD más alto entre las tiendas del funnel). `scripts/vigilar_corte.py` (`ticket_corte`, campo `ticket_corte_usd`) y `dashboard/negocio.py` (`ticket_corte`). Oferta D: corte sin ventas de US$ 19,50 a US$ 40,50.
- **Sin frenos de cuenta:** fuera de la skill, del libro (`frenos_cuenta`) y del tablero (avisos y referencias).
- `references/02-decidir.md` reescrita: tabla R1-R13, una regla por situación, con estado firmada o propuesta. Propuestas nuevas: corte post-test (CPA de 3 días ≥ 1,5 × equilibrio), escalar (+30 % con CPA ≤ 0,8 × equilibrio, una suba cada 72 h), volver atrás tras una suba que empeora, renovar cada 3 días o por fatiga, ajuste de precio de upsells.
- `references/01-revision-diaria.md` §6b: la revisión dispara la skill nueva `backend-ofensivo` cuando una oferta pasa el test con ventas y no tiene backend (R3, firmada).
- `references/04-vigilancia.md`: riesgo de la Mac dormida y respaldo propuesto con una regla automatizada de Meta.
- Buscar ofertas es ahora la skill `buscar-ofertas`, con tarea diaria propia.
## 0.4.0 · 2026-11-13

Pedido del dueño: «cuando estemos testeando 15, 20 ofertas juntas será muy difícil ver si ya le pusimos backend… y en qué estado está: si sigue en testeo, si ya están programadas las renovaciones, si está aprobada para renovaciones, si está para pausarla y apagarla».

- **Panel:** etapa por oferta (Programada, En test, Para renovar, Renovación programada, Renovando, Para apagar, Apagada) y backend (activo, en pausa, en armado, sin backend, falta). Se ven en una tira de filtros con conteos sobre la lista, en un chip de cada fila, en la ficha y en el menú lateral (ofertas agrupadas por etapa con la marca «B»). Aviso «pasó el test y no tiene backend».
- **Libro:** campos nuevos `renovaciones` y `backend` por test (`01-revision-diaria.md`); el paso 7 de `03-renovar-creativos-y-escalar.md` y el paso 7 de la guía 11 de modelar-y-lanzar-oferta los cargan.
- Código: `dashboard/negocio.py` (`etapa_de`, `backend_de`, `renovaciones_de`), `dashboard/web/lib/negocio-etapas.js`. Pruebas al día; el fixture del navegador se regenera con `tests/fixtures/dashboard/negocio/generar_fixture.py`.

## 0.3.2 · 2026-11-13

Pedido del dueño: «siempre que renovemos y agreguemos un adset en una CBO, ponerle 20 % de gasto mínimo para que Meta le otorgue presupuesto». El conjunto R3 de Oferta B había quedado sin mínimo porque la API lo rechazó, y el dueño lo puso a mano.

- `03-renovar-creativos-y-escalar.md`, paso 6 (Meta): mínimo de gasto del 20 % obligatorio, puesto en el Administrador de anuncios (la API lo rechaza) y comprobado por API.
- `SKILL.md` y `tropiezos.md`: la regla y el tropiezo.

## 0.3.1 · 2026-11-13

Pedido del dueño al ver la ronda 3 de Oferta B: «cuando se incluye un abridor que contiene una cara o una persona, no taparle la cabeza… revisa este tipo de cosas y criterios para dejarlo anotado (no rehagas todos los ads, déjalos así)».

- `references/03-renovar-creativos-y-escalar.md`, paso 5 nuevo: ningún texto (píldora ni subtítulo) tapa la cabeza de nadie ni lo que nombra la voz. Indica cómo evitarlo (prompt de la imagen inicial, mover la píldora o cambiar la toma, subtítulo fuera de boca y barbilla) y cómo comprobarlo (hoja de contacto densa de la apertura). Incluye el caso: 6 de 10 anuncios de la ronda 3 tapaban una cabeza y uno la rozaba; quedan como están.
- Meta y Anotar pasan a ser los pasos 6 y 7.

## 0.3.0 · 2026-11-12

Pedidos del dueño: el test es el primer día después del lanzamiento, y «también tendría que ser cuando el CPA del testeo, el primer día, se va a un ticket y medio… puede ser que tenga dos ventas pero que el CPA se haya ido a las nubes».

- **Fases:** test = día 1 del mercado (de 00:00 a 00:00). Al cerrarlo, con ventas pasa a post-lanzamiento; sin ventas sigue en test hasta vender o llegar al corte, con aviso de entrega baja.
- **Corte del test por CPA:** gasto ≥ 1,5 × ticket del front × máx(1, ventas). Reemplaza «solo sin ventas».
- `scripts/vigilar_corte.py`: decisiones nuevas `ENTREGA_BAJA`, `POST_LANZAMIENTO` y `SIN_PAUTA`; `--ahora` para pruebas; `ventas_tienda` en la lectura.
- Panel: `fase`, `fin_test`, corte por CPA del día 1 y aviso crítico. Pruebas al día.

## 0.2.0 · 2026-11-12

Pedido del dueño: «tiene que estar prendido siempre, y cuando una oferta nueva está corriendo, cuando ya gastó en Meta 1 ticket y medio del front, apagarla».

- **Siempre prendida:** tarea programada `vigilancia-ofertas`, cada hora. Guía nueva `references/04-vigilancia.md`.
- **Regla de corte firmada:** 1,5 × el precio del front gastado sin ventas (tienda, Meta y píxel en 0) → se apaga en la misma vuelta, sin preguntar. Reemplaza la propuesta de 3 × el equilibrio.
- **Nuevo:** `scripts/vigilar_corte.py` decide por test y registra cada vuelta en `ofertas/_funnels/vigilancia.jsonl`.
- **Panel:** `dashboard/negocio.py` usa la misma regla (`ticket_front`, `corte_usd`, zona `sin_ventas_corte`, acción «Apagar»). Pruebas al día.
- Escalar sigue siendo propuesta sin firmar.

## 0.1.0 · 2026-11-12

Separada de `modelar-y-lanzar-oferta` por pedido del dueño. Sus palabras: «tenemos una skill que es literalmente desde el testeo hasta que están programados los anuncios, pero luego de que se lanza la oferta ya esa skill no se utiliza más… lo de lanzar las renovaciones, escalar y demás es una nueva skill».

- **Movido:**
  - `modelar-y-lanzar-oferta/references/12-revision-dia-siguiente.md` §1-7 pasó a `references/01-revision-diaria.md`, y §8 a `references/03-renovar-creativos-y-escalar.md`;
  - `scripts/libro_de_tests.py`;
  - los tropiezos de después del lanzamiento.
- **Nuevo:** `references/02-decidir.md`, con la regla propuesta de escalar, mirar o cortar (sin firmar por el dueño) y los frenos.
- **Primera corrida:** la renovación de Oferta B del 12-nov. Fueron 7 iteraciones de B01 y 3 anuncios nuevos del referente, en un conjunto nuevo con mínimo de 13 USD, más la CBO de 50 a 65 USD a las 00:00 de México.
