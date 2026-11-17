# CHANGELOG · modelar-y-lanzar-oferta

## 0.10.12 · 2026-11-17 · qué cuenta como funnel complejo

- Regla del dueño: la complejidad es el recorrido antes de la venta (advertorial, quiz, VSL y similares). Bump, upsell, downsell y subida previa no agregan complejidad porque los tienen todos. El escalonado de precios (niveles) sí suma.
- `scripts/taxonomia_funnels.json`:
  - advertorial pesa 0.60 (antes 0.40), así que advertorial + TSL vale 0.70 y cuenta como complejo;
  - niveles suma 0.35 (antes 0.10): TSL + niveles queda justo en el umbral (0.60), «relativamente compleja» como Oferta F, la única oferta con ganancia; VSL + niveles llega al tope;
  - bump, upsell, downsell y subida previa suman 0 (antes 0.10 cada uno).
- Guías actualizadas: `references/taxonomia-funnels.md` y `buscar-ofertas/references/01-elegir-del-banco.md`. Copia anterior en `scripts/taxonomia_funnels.antes-complejidad-17nov.json`.

## 0.10.11 · 2026-11-15 noche · auditoría de adaptación para toda oferta

- `scripts/auditar_adaptacion.py`: revisa sin dejar rastro todas las tiendas de una oferta como las ve un comprador del país.
  - Portada y título de la pestaña de cada tienda.
  - Vistas de la landing e imágenes de otra tienda.
  - Checkout con `preview_country` (idioma, moneda, bump, textos escritos a mano en otro idioma).
  - Probado en FR, IT, IE y NZ: encontró la landing de España en la raíz de las 4 tiendas Complete, «Oferta F» en el título de FR e IT y la falta de bump en FR e IT.
- `references/13-auditoria-de-adaptacion.md`:
  - criterios A (los mira el script) y B (a mano: ambiente, texto en imágenes, videos, post-compra, downsell, fan page, píxel, leyes del país);
  - diagnóstico C, que compara contra la madre paso por paso, con el **pago completado** (apretó «Pagar» → compró) como métrica nueva;
  - el caso FR/IT.
- Fase 11 (`SKILL.md`) y guía 12 §3: la auditoría va antes del control previo. Con fallas no se activa.
- `escalar-oferta/references/01-revision-diaria.md` paso 4: el checkout → compra se parte en «apretó Pagar» y «pago completado».

## 0.10.10 · 2026-11-15 tarde · réplica adaptada de verdad

- `12-lanzamiento-automatico.md` §3 reescrito (errores de Oferta/NZ). Esquema de oferta validada: pocket 1-1-1 a 1,5 tickets y variaciones 1-1-10 a 3 tickets, con backend desde el día 1. **Inventario visual** antes de producir: se rehace todo plano o foto con ambiente, no solo lo que tiene texto. Revisión ampliada de portadas y páginas. 0 URLs de la madre en la landing. Fan page completa antes de activar. **Control de réplica lista** antes del control previo. Al corregir algo que marcó el dueño, buscar el mismo error en todas las piezas.
- `00-reglas-del-dueno.md`: regla «Réplica: todo adaptado al mercado».
- `tropiezos.md`: sección «Réplica Oferta + NZ» con los errores y lo que no se contempló.
- Scripts de referencia en la oferta: `05-landing/assets/fotos_kie_pais.py` (fotos por país) y `arreglar_texto_fotos.py` (segunda pasada de edición para el texto del idioma de la madre).

## 0.10.9 · 2026-11-14 noche · «libre» tiene que ser pautable

- `ordenar_candidatos.py`: la lista de países lanzables excluye los que Meta bloquea sin anunciante verificado (`elegir_mercado.bloqueados_por_meta()`, `reglas.json → meta`). Con esto Oferta J (referente en 89 de 93 países; 0 solo en SG, TW, TH, IN) sale «VETO» al elegirla en vez de armarse dos veces. Probado con su medición: 0 elegibles.
- `buscar-ofertas/references/01-elegir-del-banco.md` §1.2b: los ceros del referente en países bloqueados por Meta no son hueco; medir siempre hasta países sueltos.
- `04-marca-y-activos-meta.md` §2 bis y `00-reglas-del-dueno.md`: autorización permanente del dueño para aceptar las condiciones de Meta al crear fan page y píxel (también en la tarea `lanzar-ofertas`).
- `01-elegir-oferta-y-mercado.md` §2.1b: países que piden anunciante verificado.
- Tropiezos nuevos en `tropiezos.md` («Oferta J»).

## 0.10.8 · 2026-11-15 madrugada · prueba del funnel con veredicto

- `scripts/probar_funnel.py` devuelve `ok` y `fallas` por tienda: recorre las vistas `?v=articulo` y `?v=ficha`, el quiz de tarjetas (además del de `.tela`), baja la página para las imágenes diferidas, y en cada checkout mira correo, botón de pagar e **imagen del producto**; marca `{{…}}` a la vista. Países europeos y otros en `--pais`. `probar_varias()` para usarla desde `verificar_funnel.py`.
- Fase 11: antes del control previo, `verificar_funnel.py correr --antes`; su resultado va en la lectura (`funnel`) y sin él no se activa. A los 10-25 min de entregar, la vigilancia verifica de nuevo (paso 8).
- `06-tienda-impultienda.md`: al duplicar una tienda, volver a subir la imagen del producto principal (Oferta H y Oferta I salieron rotas el 14-nov). Réplica (`12-lanzamiento-automatico.md` §3) lo mismo.
- Tropiezo nuevo: revisar a mano con el navegador integrado carga el píxel real; las revisiones van con el script.
- `probar_funnel.py` ya no deja rastro (pedido del dueño: «bloquear lo que detecta Impultienda para no cargar inicio de checkouts falsos»): además del píxel bloquea `rest/v1/visits` (visitas y checkouts de las estadísticas), `rpc/live_session_ping` (visitantes en vivo) y `functions/v1/meta-track-event` (la API de conversiones de Impultienda, que mandaba PageView e InitiateCheckout a Meta desde el servidor aunque el píxel estuviera bloqueado), más Clarity y la medición de Whop. El formulario de pago sigue cargando. Devuelve `bloqueadas` por tipo; `--contar-visitas` deja salir lo de Impultienda. Comprobado con Oferta E: estadísticas sin cambios (17/0 y 0/0) tras la prueba.

## 0.10.7 · 2026-11-14 noche · repaso de fallas del día

- **Países que exigen anunciante verificado:** `elegir_mercado.py` saca del orden SG, TW, TH, MY, AU e IN mientras `reglas.json → meta.anunciante_verificado` sea `false` (Oferta J se armó entera para Singapur y Meta no dejó crear el conjunto).
- **Banco y lanzamiento con el mismo criterio:** `banco_candidatos.py estado` devuelve `listos_simples` (funnel simple, verificado a mano, sobre el piso) y `cupo_lanzamiento.py` los usa cuando no hay complejos, como ya pedía la guía 12 §1b paso 5. Antes el cupo daba BUSCAR_Y_LANZAR con 5 candidatas verificadas en el banco.
- **Píxel:** `06-tienda-impultienda.md` §5: píxel propio siempre, réplicas incluidas; se retira el plan B de prestar el de otra oferta.

## 0.10.6 · 2026-11-14 · Stripe disponible, conectado solo donde hace falta

El dueño: «no me sugieras conectar un método de pago en una tienda que apagamos… hay que tener como válido Stripe y solo conectarlo en las tiendas que vamos a lanzar con método de Stripe». `elegir_mercado.py` v6.1: `STRIPE_DISPONIBLE = True` (el orden cuenta lo que suma Stripe), «REQUIERE STRIPE» cuando el ganador lo necesita, `--sin-stripe` para el plan B. `06-tienda-impultienda.md` §2b (cuándo, dónde, cómo, comprobar, qué hacer si no se puede) y `12-lanzamiento-automatico.md` §2. No se conectó Stripe en ninguna tienda.

## 0.10.5 · 2026-11-14 · 93 países (Impul Pay y Stripe)

El dueño: «57 no son todos los países del mundo… ampliala, revisá qué países tendría sentido correr ofertas teniendo en cuenta Impul Pay (Whop) y Stripe». `elegir_mercado.py` v6 (respaldo `elegir_mercado.antes-v6.py`):
- 36 países más (Europa del Este y Bálticos, Cáucaso, Golfo, Taiwán, Pakistán, Bangladés, Sri Lanka, Mongolia, Ghana, Botsuana, Mauricio, Honduras, El Salvador, Puerto Rico, Jamaica, Trinidad y Tobago). Criterio en la cabecera del script; los que quedan fuera, con el motivo, en `FUERA` (sanciones de Whop, China, control de cambios, mercados chicos, mobile money sin método).
- Cobro releído: lista de 37 métodos de Impul Pay en el panel (14-nov) y documentación de Stripe para cuenta de EE. UU. `STRIPE_MEJORA`: lo que sube cada país con Stripe (Polonia 0,4 → 1 por BLIK y Przelewy24; Corea 0,4 → 1; India 0,4 → 0,9 por UPI; España, Austria, Alemania, Finlandia, Honduras, Panamá). Cuenta solo con `STRIPE_CONECTADO = True` o `--stripe`.
- El radar busca en los 93 (19 idiomas nuevos en `radar_terminos.json`; cola de 711 a 1.045 búsquedas).
- Pruebas en `tests/buscar_ofertas/test_veto_referente.py`.

## 0.10.4 · 2026-11-14 · Veto por países del referente

El dueño: «¿por qué Oferta D se modeló y se corrió en el mismo mercado que la oferta original está pautando? Tiene 127 anuncios encendidos». Falla: en `elegir_mercado.py` la presencia del referente era un peso (hueco 0 o 1, 40-45 %); Referente D pautaba en todos los países medidos, el hueco dio 0 en todos y México ganó por cobro. La corrida anotó «ningún país es hueco limpio» y siguió.
- `elegir_mercado.py` v5 (respaldo `elegir_mercado.antes-v5.py`): un país con anuncios activos del referente sale del orden (VETO), también en ofertas nuevas; un país medido sin `referente` no entra. Sin libres → código 3, «DESCARTAR LA OFERTA»; con países sin mirar → código 4. `--medicion` toma la medición de `paises_referente.py`.
- `ordenar_candidatos.py` (respaldo `ordenar_candidatos.antes-veto.py`): campo `referente_paises`; si el referente corre en todos los países lanzables, el candidato queda fuera; sin medir, nota y aviso de medir antes de tomarlo.
- `01-elegir-oferta-y-mercado.md` §2.1, §2.4; `12-lanzamiento-automatico.md` §2 pasos 1-2; tabla de fases.
- Pruebas: `tests/buscar_ofertas/test_veto_referente.py`.
- Oferta D queda marcado en el libro como test inválido (mercado contaminado).

## 0.10.3 · 2026-11-14 · Fan page con 10 publicaciones

El dueño: la fan page es el único activo al que la gente entra desde el anuncio y tiene que verse activa. Antes: 3 publicaciones de golpe. Ahora: 3 al crearla y 7 programadas, una cada 8-12 h en horas del mercado, durante el test; también en cada página nueva de una réplica (`04-marca-y-activos-meta.md` §2.5).

## 0.10.2 · 2026-11-14 · Nunca se espera por el banco

El 14-nov la vuelta de las 06:00 de «lanzar-ofertas» terminó en 15 s con ESPERAR (1 listo de 3) y no salió ninguna oferta. El dueño: «el sistema siempre tiene que tener preparadas ofertas… si no encontramos, sigue buscando».
- `reglas.json`: `lanzamiento.banco_minimo_listos` (3, freno) se reemplaza por `banco_minimo_para_lanzar` (1) y `banco_objetivo_listos` (3, reserva a reponer). Respaldo en `ofertas/_funnels/.respaldos/reglas.antes-buscar-siempre-2026-11-14.json`.
- `cupo_lanzamiento.py`: con 1 listo → LANZAR_NUEVA (con `reponer_banco`); con 0 → BUSCAR_Y_LANZAR; ESPERAR solo por tope del día o de tests. Prueba en `tests/escalar_oferta/test_salud_control_avisos.py`.
- `12-lanzamiento-automatico.md` §1b: con el banco vacío, la misma vuelta verifica, mide y barre hasta conseguir una, sin bajar el piso.
- Tarea «lanzar-ofertas» actualizada; un sitio rechazado por el navegador se avisa y no corta la vuelta.



## 0.10.1 · 2026-11-13 · Revisión de coherencia 2026-11-13

Alineado con las decisiones del dueño del 12 y 13-nov (informe: `docs/_historial/revision-coherencia-2026-11-13.md`):
- `SKILL.md`: tabla de fases — fila 2 sin «≥ 6 países» (ahora `elegir_mercado.py` v3, 57 países sin filtro de idioma); fila 7 con la regla 19/27; fila 10 con el presupuesto de 3 tickets; fila 11 sin «visto bueno del dueño» (control previo → mirar la hora → activar sola). La fase 1 nombra el radar como camino principal; `barrido_por_forma.py` queda como complemento. Descripción: «tomar la oferta que eligió buscar-ofertas».
- `00-reglas-del-dueno.md`: fuera «pedir el visto bueno una vez» y «decirlo en la tarjeta del visto bueno»; §4 suma mirar la hora antes de activar.
- `01-elegir-oferta-y-mercado.md`: fuera «peldaño más bajo de la escalera», «17, 19 o 27» y «países del mismo idioma»; precio = regla 19/27; el radar en el índice; quitado el «Hecho cuando» repetido.
- `09-campana-meta.md`: §3-§5 sin visto bueno (control previo, mirar la hora, aviso; la vigila la tarea de cada hora); píxel = `dataset_id` de `ads_get_datasets`.
- `12-lanzamiento-automatico.md`: mirar la hora justo antes de activar.
- `08-creativos.md`: altura de la píldora plano por plano (≈ 20 % / ≈ 62 %); «Hecho cuando» con la etapa del funnel (§1.3) y la regla de caras.
- `06-tienda-impultienda.md`: medios de pago por país con la vista previa y captura (Brasil: Pix y Boleto); ID del píxel desde `ads_get_datasets`.
- `tropiezos.md`: marcada obsoleta la nota «Impul Pay en Brasil cobra solo tarjeta».
- `02-desarme`, `03-inmersion`, `11-ofertas-que-suben-el-ticket`, `caso-mx.md`: precios y presupuesto de antes marcados como históricos.
- `scripts/nueva_oferta.py` (plantilla de `estado.md`) y `scripts/banco_candidatos.py` (cabecera y mensajes): sin «aprobación del dueño» y con el radar antes que el barrido.

## 0.10.0 · 2026-11-13 · Lanzamiento automático

- `references/12-lanzamiento-automatico.md` y tarea «lanzar-ofertas» (06:00 y 13:00): 2 por día si hay cupo (menos de 8 en test) y 3 listas en el banco; activación sola con el control previo; réplica de las ofertas con 7 días de ROAS neto ≥ 1,30.
- `scripts/cupo_lanzamiento.py` decide LANZAR_NUEVA, LANZAR_REPLICA o ESPERAR.
- `00-reglas-del-dueno.md`: activar ya no es pregunta obligatoria.
## 0.9.0 · 2026-11-13

División de skills pedida por el dueño:
- La fase 1 (buscar y elegir la oferta: banco, barrido por forma, seguimiento, iteraciones) pasa a la skill **`buscar-ofertas`**, con tarea diaria propia. `references/01-elegir-oferta-y-mercado.md` queda solo con la fase 2 y un índice de dónde quedó cada sección. Los scripts siguen en `scripts/` (compartidos).
- El backend ofensivo (upsells post-compra) pasa a la skill **`backend-ofensivo`**, disparada por la revisión diaria de `escalar-oferta`. La guía 11 queda con lo que se modela antes de pagar.
## 0.8.1 · 2026-11-13

- `references/08-creativos.md` §5: regla del dueño «no taparle la cabeza» a ninguna persona de la apertura con la píldora ni con el subtítulo; cómo evitarlo y cómo comprobarlo. El detalle está en `escalar-oferta/references/03-renovar-creativos-y-escalar.md`, paso 5.

## 0.7.1 · 2026-11-12

Corrección del dueño a 0.7.0: «tiene que comparar los creativos en video, no los copys; los copys muchas veces van a ser iguales». Las iteraciones ahora se leen por video.

- Nuevo `scripts/biblioteca_videos.js`: en la pestaña de la Biblioteca saca huellas de fotogramas de cada video (arranque, y cuerpo y cierre alineados desde el final), los compara y arma familias con su relación (idéntico, otro corte, mismo arranque con cuerpo distinto, mismo cuerpo con arranque distinto, mismo material con otro montaje); dibuja una hoja de contacto por familia.
- `banco_candidatos.py`: subcomando `videos`; `iteraciones` muestra primero las familias por video, con el formato en palabras, y deja el texto como dato secundario (`--textos`).
- `01-elegir-oferta-y-mercado.md` §1.6 y `fragmentos-navegador.md` §9.
- Probado con dos ofertas (`empresa/barrido/banco/seguimiento-2026-11-12.md`): en Shape em V, 8 videos con el mismo cuerpo y arranques distintos lanzados en 7 tandas durante 96 días (25 de sus videos llevan el mismo texto); en el referente de Oferta C, 32 videos distintos de un solo formato, casi sin variantes.

Límites: compara la imagen, no el audio; el formato de cada familia lo describe el asistente mirando la hoja de contacto; los umbrales (10 bits por fotograma, 66 % del arranque, 50 % del cuerpo) salieron de dos ofertas y no están calibrados; la función `__hoja` se probó antes de ordenar el archivo y no se volvió a correr tal como quedó escrita.

## 0.8.0 · 2026-11-12

Regla del dueño (13-nov): presupuesto diario del test = 3 tickets del producto principal (el nivel completo si hay niveles). `09-campana-meta.md` §1 y `00-reglas-del-dueno.md` §1. Antes la skill decía «el dueño dice el monto» y se usaba 50 USD/día fijo.

Aprendizajes de lo ejecutado con ventas reales, pedido del dueño («aprende de lo ejecutado en las anteriores ofertas y súmalo a la skill»).

- `08-creativos.md` §1.2: lo que vendió en los tests (gancho de oficio, producto a los ~15 s, anuncios al profesional, compradoras 45-64, el referente itera su ganador) y costo por anuncio de presentadora frente a montaje.
- `07-landing.md` §4.1: primera pantalla liviana (un tercio de los clics no carga la página) y promesa igual a la de los anuncios que venden; §4.2: bloque de opiniones reales solo con compradores reales y su permiso.
- `tropiezos.md`: sección «Lo que enseñaron las primeras ventas», incluida la landing que otro proceso pisaba (comprobar la huella a los 3-5 min de publicar).

Con 8 ventas en dos ofertas, todo lo de §1.2 es pista; la mezcla del referente sigue mandando.

Cuarta corrida («Oferta D», México, `advertorial+tsl` con 3 niveles, 12-13 nov): ID del píxel solo desde `ads_get_datasets` (04 §3); agrupar los anuncios del referente por destino antes de diseñar el producto (01 §1.5); subagentes sin navegador; Recursos acepta subidas múltiples y las URL se leen interceptando el portapapeles (tropiezos). Producto de 13 manuales escrito por 11 agentes en paralelo en ~40 min.

Criterio del dueño tras la cuarta corrida («¿con qué criterio pusiste 3 imágenes BOFU?»): `08-creativos.md` §1.3 y `02-desarme-del-referente.md` (etapa y destino de cada pieza del referente; en el primer test todas las piezas abren con gancho; las de cierre y las de temporada no se copian como cierre). Regla al activar: mirar la hora otra vez (`09-campana-meta.md` §4).

`elegir_mercado.py` v2 (pedido del dueño, 13-nov: «¿con qué criterio se eligió este mercado nuevamente?… aplícalo ya»): cobro medido en Impul Pay (tabla con fecha), castigo ×0,6 por cada repetición en las últimas 4, hueco graduado por idioma, competencia con consulta comparable obligatoria, sensibilidad impresa, 21 candidatos y «r» económico de `scripts/mercados` como dato. Copia de v1 en `scripts/elegir_mercado.antes-v2.py`. Reprocesada la cuarta corrida: México habría salido último.

`elegir_mercado.py` v3 (mismo día, «no dejes afuera países por no producir en esos idiomas»): 57 países sin filtro de idioma; poder de compra (5 %); CPA observado por país desde el libro de tests y castigo más suave (×0,8) si el país ya dio un test rentable; aviso de temporada (`--inicio`); abandono del referente; regla de exploración (mejor país nunca probado). Corrección: Oferta C SÍ tiene Pix y Boleto (la nota del 12-nov estaba mal; los medios se dibujan dentro del cuadro de Whop).

## 0.7.0 · 2026-11-12

Banco de candidatos, seguimiento diario e iteraciones de creativos, pedidos por el dueño («no entiendo: ¿cada vez se hace un barrido nuevo o se fija el último?»; «un barrido solo sobre todas las ofertas encontradas y analizar si están escalando»; «comparar tandas de anuncios… identificar si están iterando algún ángulo o formato… como posible ad winner»).

- Nuevo `scripts/banco_candidatos.py`: `importar`, `estado` (¿alcanza o hay que barrer?), `seguimiento`, `medir`, `tendencia`, `creativos`, `iteraciones`, `marcar`. Datos en `empresa/barrido/banco/` (`ofertas.json`, `mediciones.jsonl` que solo se añade, `creativos/<oferta>/<fecha>.json`).
- Regla nueva en `01-elegir-oferta-y-mercado.md` §1.1 y §1.6: buscar y elegir van separados; al pedir una oferta se mira el banco y solo se barre si hay menos de 3 candidatos complejos, verificados y producibles, o si el último barrido tiene más de 7 días. Se quitó el párrafo que decía «no se hace un barrido nuevo desde esta skill», que contradecía a §1.5.
- `fragmentos-navegador.md` §8: lector de tarjetas con texto, duración y repeticiones.
- Primera corrida: `empresa/barrido/banco/seguimiento-2026-11-12.md` (21 ofertas medidas dos días; tres leídas anuncio por anuncio).

Umbrales propuestos por el asistente, sin calibrar: 3 listos, 7 días de vigencia del barrido, cambio mínimo de 3 anuncios y 10 %, «escalando» con tres días, familias con parecido de texto ≥ 0.55, tandas a 7 y 30 días.

Sin probar o a medias: «escalando» todavía no pudo salir (hay dos días de datos); las familias dependen de que el anuncio lleve texto y no comparan lo que se ve en el video; el seguimiento es manual (nadie lo corre solo cada día); las ofertas en constructores compartidos se siguen por el total de su página.

## 0.7.0 · 2026-11-12

Pedido del dueño: separar lo de después del lanzamiento en otra skill. La fase 13 (revisión del funnel en marcha), la renovación de creativos y el escalado de presupuesto pasan a `.claude/skills/escalar-oferta/`, junto con `scripts/libro_de_tests.py` y los tropiezos de después del lanzamiento. Esta skill termina en la activación y el cierre; `scripts/probar_funnel.py` se queda aquí porque también se usa antes de activar.

## 0.6.0 · 2026-11-12

Revisión de los funnels en marcha, pedida por el dueño tras 9 horas de pauta en México («revisá ambos funnels… métricas de meta, conversión en impultienda… % de checkout y % de conversión… llevar el control de cuánto en dinero nos salió cada testeo… y cuánto se facturó neto»).

- Nueva fase 13 y guía `references/12-revision-dia-siguiente.md`: orden de lectura (tienda, Impul Pay, carritos, Meta por anuncio, píxel) antes de probar, referencias del dueño (checkout 8-12 %, compra 25-30 %, CPA ≤ neto), prueba sin ensuciar, diagnóstico tramo por tramo, libro de costos y recomendaciones separando lo del agente y lo del dueño.
- Nuevo `scripts/probar_funnel.py`: prueba móvil (4G simulada) de landing, quiz, video y checkouts, con el píxel bloqueado por defecto.
- Nuevo `scripts/libro_de_tests.py` y `ofertas/_funnels/libro-de-tests.json`: producción, Meta, ventas, neto, CPA real y de equilibrio por test.
- `fragmentos-navegador.md` §7: leer estadísticas, neto y carritos de una tienda.
- `10-expediente-del-funnel.md` §3: lo no modelado pasa a una carpeta `no-modelado/` con capturas antes y después marcadas.
- API de conversiones obligatoria en cada funnel (pedido del dueño): `06-tienda-impultienda.md` §5.1 (el dueño genera y pega el token; yo preparo las pantallas y compruebo sin leerlo), fila en el mensaje inicial (`00-reglas-del-dueno.md`), control antes de activar (`09-campana-meta.md`).
- Primera compra real verificada de punta a punta (cobro, correo, Purchase en el píxel) en las dos ofertas de México.

## 0.3.0 · 2026-11-11

Barrido por forma de funnel y taxonomía de funnels que crece sola, pedidos por el dueño tras la segunda corrida («estoy seguro que existen quiz más VSL y otros tipos, que son como mutaciones… encuadrarlo dentro de uno de los que tenemos o crear y decir: este funnel es quiz más TSL»).

- Nuevo `references/taxonomia-funnels.md` y `scripts/taxonomia_funnels.json` (+ `taxonomia_funnels.py`): componentes de núcleo y extras con sus señales, tipos como combinación ordenada (`quiz+vsl`), complejidad derivada de los componentes (un híbrido vale más que sus partes) y regla de encuadre (tipo existente o tipo nuevo «a confirmar por el dueño», con el ejemplo que lo originó; nunca forzar).
- `scripts/ordenar_candidatos.py` lee la taxonomía. Los nombres del historial (`tsl-video`, `tsl-basica`) y `varios-pasos` siguen valiendo y dan la misma complejidad que antes. **Cambio de comportamiento:** la variación compara el tipo canónico, así que `tsl-video` y `tsl-basica` cuentan como el mismo tipo (`tsl`); con el historial actual, una tercera TSL pasa de ×0.85 a ×0.70. Es lectura del asistente de «ir variando»; si el dueño no lo quiere así, se cambia en `puntuar()`.
- Nuevo `scripts/barrido_por_forma.py` (`terminos`, `clasificar`, `encuadrar`, `informe`) y `scripts/terminos_forma_funnel.json` (frases por forma en es, en, it, de, fr y pt, y señales de destino). El clasificador descarga el destino en solo lectura, sigue hasta el checkout sin enviar formularios y devuelve tipo, evidencia, no observado y confianza.
- `01-elegir-oferta-y-mercado.md` §1.5 pasa de «pendiente de automatizar» a procedimiento; §1.2 remite a la taxonomía. `02-desarme-del-referente.md` §1 y §1b empiezan por el tipo y añaden el apartado de híbridos. `fragmentos-navegador.md` §6: lectura de tarjetas de la Biblioteca.
- Primera corrida real: `empresa/barrido/candidatos/2026-11-11-por-forma.json` y `.md` (21 candidatos). Tipos nuevos registrados: `quiz+vsl`, `quiz+tsl`, `advertorial+quiz`, `registro`.

Lo que se aprendió: el conector no sirve para encontrar funnels (sin texto ni destino); la frase de forma sola trae sobre todo suscripciones y servicios; lo que mejor rinde es buscar el dominio de un constructor de quiz y medir cada oferta por su dominio de destino. Los quiz con más volumen son casi todos aplicaciones por suscripción.

Sin probar o a medias: el clasificador no ve los quiz dibujados con JavaScript (confianza baja, hay que recorrerlos a mano) y no ordena bien dos componentes en una misma página; las frases de advertorial y de registro y los demás constructores de quiz de la lista no se buscaron; los pesos por componente son lectura del asistente; ningún funnel híbrido se ha construido todavía con esta skill.

## 0.1.2 · 2026-11-11

El dueño corrigió el criterio de 0.1.1: no un orden fijo de tipos de funnel (llevaría a hacer siempre quiz), sino una relación entre complejidad, antigüedad («sobre todo») y anuncios encendidos, variando de tipo entre ofertas. Nuevo `scripts/ordenar_candidatos.py` (puntaje 40/35/25, los tres funnels complejos valen igual, penalización por repetir tipo o tema) y `ofertas/historial-modelado.json` con la oferta de México. Los pesos son lectura del asistente; probado solo con candidatos de ejemplo.

## 0.1.1 · 2026-11-11

Regla nueva del dueño para elegir oferta: por encima del piso de 15 anuncios y 10 días, preferir el funnel más complejo (quiz, VSL, varios pasos) y la mayor cantidad de anuncios encendidos (50, 60, 100 o más), siempre que haya disponibles. Cambios: `01-elegir-oferta-y-mercado.md` §1.2 (tabla de tipos de funnel, cómo clasificar y qué presentar), `02-desarme-del-referente.md` §1b (mapa de quiz, VSL y funnels de varios pasos; cómo leer muchos anuncios) y `00-reglas-del-dueno.md`.

Sin probar: ningún funnel complejo se ha construido con esta skill; la corrida de México fue una TSL corta. No se tocó la fórmula de puntaje del barrido (`scripts/modelado/`), que tiene sello de reglas.

## 0.1.0 · 2026-11-11

Primera versión. Escrita al terminar la corrida a mano de «Oferta A» (México, modelada de ReferenteA), con lo que se hizo, lo que el dueño corrigió y lo que falló. Incluye el código de esa corrida en `ejemplo-mx/` y un generador de carpeta (`scripts/nueva_oferta.py`).

Sin probar todavía: ninguna oferta se ha hecho siguiendo la skill. Los scripts de `ejemplo-mx/` corrieron en la oferta de México; adaptados a otro producto no se han corrido.

No incluye, a propósito: ejecutar `cro-polish` como paso final (pedido por el dueño el 2026-11-11). Motivo en `references/00-reglas-del-dueno.md` §2. La skill termina con la landing publicada y verificada.

## Registro de promoción

| Versión | Estado | Fecha | Corrida manual (oferta · locale · modo) | Retro | DoD firmado por el dueño | Notas |
|---|---|---|---|---|---|---|
| 0.1.0 | nacida de corrida real, sin pulir como skill | 2026-11-11 | `_borrador-oferta-a` · es-MX · a mano | — | — | falta la primera corrida siguiendo la skill |
| 0.2.0 | primera corrida completa siguiendo la skill | 2026-11-11 | `_borrador-oferta-b` · es-MX · skill de punta a punta, campaña activa | `references/tropiezos.md` (segunda corrida) | — | añadido: producto de texto por código (05 §8), dos tiendas para dos niveles (06), crear página desde Business (04), todos los países en la Biblioteca y búsqueda a propósito de funnels complejos (01 §1.5, pedido del dueño, pendiente de automatizar) |
| 0.2.1 | corrección del dueño | 2026-11-11 | las dos ofertas de México | `references/tropiezos.md` | — | bonus siempre como bonos de Impultienda, valor percibido vacío, upsells post-compra solo tras el test (06 §3.1, 05 §6) |
| 0.3.0 | barrido por forma de funnel y taxonomía, con una búsqueda real | 2026-11-11 | sin oferta: solo lista, taxonomía y método | — | — | no se eligió oferta ni se empezó ningún modelado; falta que el dueño confirme los tipos nuevos |
| 0.3.1 | corrección del dueño | 2026-11-11 | `_borrador-oferta-b` · segunda tanda de anuncios | `references/tropiezos.md` | — | muestra de 13-15 anuncios del referente por tandas (02 §2.0), reglas y medición de diversidad creativa (08 §1.1), `__hoja3` para hojas de contacto en lote (fragmentos §2.1) |
| 0.3.2 | pedido del dueño | 2026-11-11 | las dos ofertas de México | `references/tropiezos.md` | — | fase 8 bis: expediente del funnel en `ofertas/_funnels/<Nombre en tienda>/` (10-expediente-del-funnel.md, `scripts/expediente_funnel.py`); el desarme lee los scripts del referente |
| 0.4.0 | pedido del dueño | 2026-11-11 | `_borrador-oferta-b` · subida antes de pagar | `references/tropiezos.md` | — | extra `subida-previa` en la taxonomía; guía 11 sobre ofertas que suben el ticket (antes, durante y después del pago); tercera tienda para la subida |
| 0.5.0 | tercera corrida completa, de noche y sin el dueño | 2026-11-12 | `_borrador-oferta-c` · pt-BR · quiz+vsl, Brasil | `references/tropiezos.md` (tercera corrida) | — | primer quiz+vsl y primer mercado fuera de México; `scripts/elegir_mercado.py` (pedido del dueño: no repetir mercado por defecto); landing quiz en el HTML de la tienda (07 §quiz+vsl); presentadora con Kling Avatar estándar en colas paralelas; verificación de PDF por bytes en la tienda |
| 0.8.0 | cuarta corrida completa, la primera `advertorial+tsl` con 3 niveles | 2026-11-13 | `_borrador-oferta-d` · es-MX · campaña activa con inicio 13-nov 00:00 | `references/tropiezos.md` (cuarta corrida) | — | México ganó la comparación de 8 países por cobro; aprendizajes de ventas reales en 08 §1.2 y 07 §4.1-4.2 |
| 0.6.0 | revisión de funnels en marcha, pedida por el dueño | 2026-11-12 | Oferta A y Oferta B (9 h de pauta) · Oferta C probado antes de salir | `references/tropiezos.md` (revisión del 12-nov) | — | fase 13, `probar_funnel.py`, `libro_de_tests.py`; regla de corte y anuncios en dos tandas propuestas, sin decidir |
| 0.10.9 | corrida DOM-A de la tanda 15-17 nov (agente paralelo) | 2026-11-15 | `_borrador-oferta-o` · ja · tsl+bump, Japón (modelada de Adesiva Pro BR) | `references/tropiezos.md` (corrida DOM-A) | — | primer producto de muchos PNG entregado como PDF con enlaces a Recursos; primer mercado asiático (JP); page_id de Business ≠ id de página; bonos vacíos auto-creados se borran |
| 0.10.10 | tanda de 6 ofertas en paralelo (15-17 nov), 6 agentes + orquestador | 2026-11-15 | JP, CA, TR, BR, MX, NL · inicios lun 16, mar 17 y mié 18 a las 00:00 del mercado | `references/tropiezos.md` (tanda 15-17 nov) | — | posts con imagen en Business Suite: método DataTransfer + change e input; un agente no puede publicar en la página de otra oferta; corte de red se retoma con SendMessage; avatar/lip-sync quema subtítulos falsos |
