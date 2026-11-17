# Textos del servidor del panel — «texto viejo → texto nuevo»

> Decisión del dueño (2026-11-06): *todo término técnico o palabra confusa se explica en simple.* Este archivo lista los textos que **viajan desde el servidor Python** (avisos de cada respuesta de la API, mensajes de error, títulos y descripciones de la consola de acciones) y que se reescribieron siguiendo `dashboard/GUIA_DE_LENGUAJE.md`. Sirve para que el frontend y la documentación sigan los cambios.
>
> **Qué NO cambió (contrato):** los códigos de error (`codigo`), los estados HTTP, las claves de los datos, los ids de las acciones, sus argumentos, la lista blanca y la lógica de ejecución. Tampoco se tocó `dashboard/api.py` ni la API de servicio (/ingesta, /webhooks, /ordenes, /ingresar, /estado, /salud), que son de máquina a máquina.
>
> **Dónde se ve cada cosa:** los `avisos` aparecen en la franja de avisos de cada pantalla; los `mensaje` de error, en el cuadro de error; los `titulo`/`descripcion` de las acciones, en la consola de acciones de «Salud del sistema».

## 1. Consola de acciones (`dashboard/acciones.yaml`)

| id (sin cambios) | Título viejo | Título nuevo |
|---|---|---|
| `barrido_estado` | Barrido: estado de una corrida | Ver cómo va un barrido de anuncios |
| `barrido_plan_ver` | Barrido: ver el plan de consultas | Ver el plan de consultas de un barrido |
| `barrido_rankear` | Barrido: rankear (simulación, sin escribir) | Probar el ranking de temas de un barrido (simulacro) |
| `barrido_fichas` | Barrido: fichas (simulación, sin escribir) | Probar el armado de las fichas de ofertas (simulacro) |
| `validar_esquemas` | Validar esquemas de contratos | Revisar que los formatos de los contratos estén bien |
| `validar_ejemplos` | Validar ejemplos de contratos | Revisar los ejemplos de los contratos |
| `validar_oferta` | Validar una oferta completa | Revisar una oferta completa (solo lectura) |
| `pruebas_paquete` | Pruebas de un paquete | Correr las pruebas de una parte del sistema |
| `landing_validar` | Landing: validar (lint de publicación L1) | Revisar la página de venta de una oferta antes de publicarla |
| `landing_generar` | Landing: generar (simulación) | Armar la página de venta (simulacro) |

| id | Descripción vieja | Descripción nueva |
|---|---|---|
| `barrido_estado` | Panorama de solo lectura de una corrida: plan, consultas ok/con error, páginas, etiquetado, memoria, candidatos, fichas, cupo y freno. | Muestra el estado de un barrido: el plan, las consultas hechas (con y sin error), las páginas, su clasificación, los candidatos y las fichas, el cupo que queda y si el freno de la captura está puesto. Solo mira: no cambia nada. |
| `barrido_plan_ver` | Resumen del plan acumulado vigente (opcionalmente, cada consulta). | Muestra un resumen del plan de consultas que tiene el barrido, y si quieres, el detalle de cada consulta. Solo mira: no cambia nada. |
| `barrido_rankear` | Calcula temas rankeados y matriz tema × país SIN escribir nada (sin --escribir). Imprime el sello de reglas en uso. | Calcula el ranking de temas y el cruce de temas por país como simulacro: muestra el resultado pero no guarda nada. También muestra la huella (marca única) de las reglas de puntaje que se usaron. |
| `barrido_fichas` | Arma y valida el borrador de fichas 2.0.0 SIN escribir nada (sin --escribir). | Arma el borrador de las fichas de ofertas y comprueba que tengan el formato esperado, como simulacro: no guarda nada. |
| `validar_esquemas` | Carga y valida todos los esquemas de contratos/ (scripts.validar_esquemas esquemas). | Carga y comprueba todos los formatos de datos (esquemas) de la carpeta contratos/. Solo mira: no cambia nada. |
| `validar_ejemplos` | Valida los ejemplos válidos e inválidos de contratos/ejemplos/. | Comprueba los ejemplos de contratos/ejemplos/: los correctos tienen que pasar y los incorrectos tienen que fallar. Solo mira: no cambia nada. |
| `validar_oferta` | Valida ofertas/<id>/ contra los esquemas y las reglas cruzadas (solo lectura). | Comprueba que los archivos de una oferta tengan el formato esperado y que sean coherentes entre sí. Solo mira: no cambia nada. |
| `pruebas_paquete` | Corre `unittest discover` de tests/<paquete> (sin red ni credenciales; no toca empresa/ ni ofertas/ reales). | Corre las pruebas automáticas de la parte que elijas, para ver si todo sigue funcionando. No usa internet ni claves, y no toca las ofertas ni los datos reales de la empresa. |
| `landing_validar` | Lint de solo lectura de ofertas/<id>/05-landing/ (precio, moneda, garantía, enlaces, legales, consentimiento, sin datos de salud). | Revisa la página de venta (landing) de una oferta: que el precio, la moneda y la garantía coincidan, que los enlaces y las páginas legales existan, que se pida consentimiento antes de medir y que no haya datos de salud. Solo mira: no cambia nada. |
| `landing_generar` | Generar el sitio de la landing en simulación. | Armaría la página de venta de una oferta como simulacro, sin guardar nada. |
| `landing_generar` (`motivo`, «próximamente») | landing.generar siempre escribe 05-landing/ y no tiene modo de simulación (--dry-run); se habilitará cuando B4 lo agregue. | Todavía no se puede: el comando que arma la página siempre guarda archivos en la carpeta de la oferta y aún no tiene modo simulacro. Se habilitará cuando se agregue ese modo (tarea B4). |

Rótulos de los datos que pide cada acción (`parametros.*.descripcion`):

| Parámetro (sin cambios) | Texto viejo | Texto nuevo |
|---|---|---|
| `corrida` de `barrido_estado` | Corrida AAAA-MM-DD-<letra>, p. ej. 2026-11-06-a | Qué barrido mirar: escribe su código (fecha y una letra), por ejemplo 2026-11-06-a |
| `corrida` de las otras 3 acciones de barrido | Corrida AAAA-MM-DD-<letra> | Qué barrido usar: su código (fecha y una letra), por ejemplo 2026-11-06-a |
| `consultas` (bandera `--consultas`) | Listar cada consulta | Mostrar también el detalle de cada consulta |
| `oferta` de `validar_oferta` | Oferta existente (OF-AAAAMM-NN o _ejemplo) | Qué oferta revisar: su código (por ejemplo OF-202611-01) o _ejemplo, la oferta de demostración |
| `oferta` de `landing_validar` | Oferta existente | Qué oferta revisar: su código, por ejemplo OF-202611-01 |
| `paquete` | Paquete a probar | Parte del sistema a probar (por ejemplo engine es el sistema automático que mueve las ofertas, y compliance es la revisión de cumplimiento) |

## 2. Errores y avisos de la consola (`dashboard/acciones.py`, `dashboard/servidor.py`)

| Código (no cambia) | Texto viejo | Texto nuevo |
|---|---|---|
| `accion_no_permitida` | Esa acción no está en la lista blanca. | Esa acción no está entre las permitidas de la consola. |
| `accion_proximamente` (sin `motivo`) | Esa acción aún no está disponible. | Esa acción todavía no está disponible. |
| `args_invalidos` | args debe ser un objeto. | Los datos de la acción no tienen la forma esperada. |
| `panel_cerrando` | El panel se está cerrando. | El panel se está cerrando. Ábrelo de nuevo y prueba otra vez. |
| `accion_en_curso` | Esa acción ya está corriendo. | Esa acción ya se está ejecutando. Espera a que termine para lanzarla otra vez. |
| `demasiados_trabajos` | Hay demasiados trabajos en marcha; espera a que termine alguno. | Ya hay varias acciones en marcha. Espera a que termine alguna y prueba de nuevo. |
| `no_se_pudo_lanzar` | No se pudo lanzar el proceso de la acción. | No se pudo iniciar la acción. Prueba de nuevo; si sigue pasando, avisa a quien mantiene el sistema. |
| `args_invalidos` | Argumentos no admitidos: x. | Hay datos que esta acción no acepta: x. |
| `args_invalidos` | Falta el argumento obligatorio x. / Falta el argumento x. | Falta completar un dato obligatorio: x. / Falta completar un dato: x. |
| `args_invalidos` | El argumento x no es válido. | El dato «x» no es válido. |
| `args_invalidos` | El argumento x debe ser un entero entre a y b. | El dato «x» tiene que ser un número entero entre a y b. |
| `args_invalidos` | El argumento x debe tener la forma AAAA-MM-DD-<letra>. | El dato «x» tiene que ser la fecha y una letra, por ejemplo 2026-11-06-a. |
| `args_invalidos` | El argumento x debe ser una oferta existente. | El dato «x» tiene que ser el código de una oferta que exista. |
| `args_invalidos` | El argumento x debe ser uno de: … | El dato «x» tiene que ser uno de estos: … |
| `args_invalidos` | El argumento x no tiene carpeta asociada (v). | No existe la carpeta necesaria para «v» (dato «x»). |
| `job_no_encontrado` | No existe ese trabajo (¿se reinició el panel?). | No se encontró esa ejecución. Si reiniciaste el panel, las ejecuciones anteriores se pierden: vuelve a lanzar la acción. |
| `parametro_invalido` (`desde`) | El parámetro desde debe ser un entero. | El valor de «desde» tiene que ser un número entero. |
| (aviso de `GET /acciones`) | Acción x rechazada: motivos | La acción «x» fue rechazada y no se puede usar (no cumple las reglas de seguridad): motivos. |
| (aviso al cargar) | acciones.yaml no existe: no hay acciones disponibles. | No se encontró la lista de acciones permitidas (acciones.yaml): la consola no tiene nada para ejecutar. |
| (aviso al cargar) | acciones.yaml debe tener la clave «acciones» con una lista. | La lista de acciones permitidas (acciones.yaml) está mal armada: le falta la sección «acciones» con la lista. |
| (`motivo` de «próximamente» por archivo ausente) | Aún no existe: ruta | Todavía no está disponible: falta ruta. |

Motivos de rechazo de una entrada de `acciones.yaml` (solo los ve quien edita ese archivo):

| Viejo | Nuevo |
|---|---|
| la entrada no es un mapa | una entrada de la lista no tiene el formato esperado |
| id inválido (a-z, 0-9, _; empieza por letra) | el nombre interno (id) no es válido: solo minúsculas, números y guion bajo, y tiene que empezar con una letra |
| id repetido | el nombre interno (id) está repetido |
| falta titulo / falta descripcion | falta el título / falta la descripción |
| riesgo debe ser uno de (…) | el riesgo tiene que ser uno de estos: lectura, escribe_local |
| timeout_s debe ser un entero entre 1 y 900 | el tiempo máximo (timeout_s) tiene que ser un número entero de segundos entre 1 y 900 |
| requiere debe ser una lista de rutas relativas / requiere solo admite rutas relativas dentro de la raíz | «requiere» tiene que ser una lista de rutas relativas / «requiere» solo admite rutas relativas dentro del proyecto |
| parametros debe ser un mapa | «parametros» tiene que ser un mapa (nombre: definición) |
| nombre de parámetro inválido: x | el nombre de dato x no es válido |
| parámetro x: tipo debe ser uno de (…) (no hay texto libre) | dato «x»: el tipo tiene que ser uno de estos: … (no se permite texto libre) |
| parámetro x: entero exige 0 <= minimo <= maximo | dato «x»: un número entero necesita «minimo» y «maximo» (desde 0, con minimo menor o igual que maximo) |
| parámetro x: eleccion exige una lista de valores simples que no empiecen por '-' | dato «x»: una elección necesita una lista de valores simples que no empiecen con «-» |
| parámetro x: flag inválida o prohibida | dato «x»: la opción (flag) no es válida o está prohibida |
| argv debe ser una lista de textos / falta argv | «argv» (el comando) tiene que ser una lista de textos / falta el comando («argv») |
| argv usa {x} sin declararlo en parametros | el comando usa {x} sin declararlo en «parametros» |
| argv contiene un elemento prohibido: … | el comando contiene algo prohibido: … |
| {python} y las banderas deben ocupar un elemento completo del argv | {python} y las opciones (banderas) tienen que ocupar un elemento completo del comando |
| el parámetro x no aparece en argv | el dato «x» no se usa en el comando |
| el primer elemento del argv debe ser {python} | el comando tiene que empezar con {python} |

## 3. Errores generales del panel (`dashboard/servidor.py`, `dashboard/seguridad.py`)

| Código (no cambia) | Texto viejo | Texto nuevo |
|---|---|---|
| `error_interno` | Error interno del panel. | El panel tuvo un problema inesperado. Prueba de nuevo; si sigue pasando, avisa a quien mantiene el sistema. |
| `ruta_invalida` | La ruta no es UTF-8 válido. / La ruta no es válida. | La dirección pedida tiene caracteres que el panel no entiende. / La dirección pedida no es válida. |
| `consulta_invalida` | La consulta es demasiado larga. / La consulta tiene demasiados parámetros. | El pedido es demasiado largo. / El pedido trae demasiados datos. |
| `tipo_contenido_invalido` | El cuerpo debe enviarse como application/json. | Los datos se enviaron en un formato que el panel no entiende. Recarga la página y prueba de nuevo. |
| `cuerpo_demasiado_grande` | El cuerpo supera 64 KB. | Lo que se quiso enviar es demasiado grande (más de 64 KB). |
| `cuerpo_invalido` | El cuerpo no es JSON estricto válido. | Los datos enviados no tienen un formato válido. Recarga la página y prueba de nuevo. |
| `cuerpo_invalido` | El cuerpo debe ser un objeto JSON. | Los datos enviados no tienen la forma esperada. Recarga la página y prueba de nuevo. |
| `campo_no_permitido` (acciones) | Campos no admitidos: x. | Hay datos que no se aceptan: x. |
| `campo_invalido` (pausa) | El campo motivo debe ser texto. | El motivo tiene que ser un texto. |
| `metodo_no_permitido` | Solo se admiten GET y HEAD aquí. / Este recurso solo admite GET. / Método no permitido para este recurso. | Esa operación no está permitida en esta dirección del panel. |
| `no_encontrado` | No existe ese recurso. | No se encontró eso en el panel. |
| `no_encontrado` (página de venta sin oferta) | Falta el identificador de oferta. | Falta indicar de qué oferta es la página de venta. |
| `recurso_demasiado_grande` | El recurso supera el tamaño máximo servible. | Ese archivo es demasiado grande para mostrarlo en el panel. |
| `ruta_no_encontrada` | Esa ruta de la API no existe. | El panel no tiene esa dirección. |
| `demasiadas_conexiones` | Demasiadas conexiones de eventos abiertas. | Hay demasiadas pantallas del panel abiertas a la vez. Cierra alguna y recarga la página. |
| `longitud_requerida` | Falta Content-Length. | Al pedido le falta indicar cuánto pesa. Recarga la página y prueba de nuevo. |
| `longitud_invalida` | Content-Length debe ser un entero decimal sin signo ni separadores. | El tamaño indicado en el pedido no es válido. Recarga la página y prueba de nuevo. |
| `cuerpo_demasiado_lento` | El cuerpo tardó demasiado en llegar. | Los datos tardaron demasiado en llegar. Prueba de nuevo. |
| `cuerpo_incompleto` | El cuerpo llegó incompleto. | Los datos llegaron incompletos. Prueba de nuevo. |
| `host_no_permitido` | El encabezado Host no es el de este panel local. | Esa dirección no es la del panel local. Abre el panel con la dirección que muestra la terminal al arrancarlo (empieza con 127.0.0.1 o localhost y lleva el puerto). |
| `origen_requerido` | Esta operación exige el encabezado Origin del propio panel. | Esta operación solo se puede hacer desde la pantalla del propio panel. |
| `origen_no_permitido` | El origen de la petición no es el de este panel local. / La petición proviene de otro sitio. | Esta operación solo se acepta desde la pantalla del panel local, no desde otra página. / El pedido vino de otra página web y no del panel; por seguridad se rechazó. |
| `token_invalido` | Falta el token de sesión o no es válido; abre la URL que imprime el servidor. | Falta la clave de acceso de esta sesión o ya no sirve. Abre el panel con la dirección completa que muestra la terminal al arrancarlo. |
| (dato `como_reanudar` de `POST /pausa`) | El panel nunca borra empresa/PAUSA: revisa el motivo y, si corresponde, bórrala tú desde la terminal. | El panel nunca borra la pausa: revisa el motivo y, si corresponde, borra tú el archivo empresa/PAUSA desde la terminal. |
| (página provisional si falta `index.html`) | El servidor funciona, pero dashboard/web/index.html todavía no existe. La API está en /api/… (requiere la cabecera X-Panel-Token). | El panel está andando, pero todavía falta su pantalla principal (dashboard/web/index.html). Avisa a quien mantiene el sistema para que la agregue. |

Sin cambio a propósito: el motivo por defecto de la pausa («Pausa manual desde el panel (sin motivo)»), que ya era claro.

## 4. Códigos y nombres que se dicen igual en varias pantallas (`dashboard/api_base.py`)

| Código (no cambia) | Texto viejo | Texto nuevo |
|---|---|---|
| `oferta_invalida` | El identificador de oferta no es válido. | El código de la oferta no es válido. Tiene que verse así: OF-202611-01. |
| `oferta_no_encontrada` | No existe esa oferta. | No encontramos esa oferta. Revisa el código o elígela desde la lista de ofertas. |
| `corrida_invalida` | El identificador de corrida debe ser AAAA-MM-DD-<letra>. | El código del barrido (corrida) no es válido. Tiene que ser la fecha y una letra, por ejemplo 2026-11-06-a. |
| (campo `nombre` de cada etapa en `GET /api/oferta/<id>`) D3 | Arquitectura de la oferta | Diseño de la oferta |
| ídem D5 | Landing, checkout y tracking | Página de venta, pago y medición |
| ídem D6 | Creativos y anuncios | Anuncios (imágenes, videos y textos) |
| ídem D7 | Campañas Meta | Campañas en Meta |
| ídem D8 | Optimización diaria | Ajuste diario de las campañas |
| ídem D9 | Escalado | Crecimiento (subir el presupuesto) |
| ídem D10 | Post-compra | Entrega y soporte al comprador |

(M1, D1, D2 y D4 no cambiaron. El frontend usa sus propios nombres cortos; el del servidor queda como respaldo.)

## 5. Avisos de cada pantalla

### Ofertas y detalle de oferta (`api_ofertas.py`)
| Viejo | Nuevo |
|---|---|
| estado.json aún no existe (lo crea el motor con `python -m engine.orq crear`) — campo `aviso` de cada fila | Esta oferta todavía no tiene su registro de avance. Lo crea el sistema automático con el comando `python -m engine.orq crear` (archivo estado.json). |
| No hay ofertas en ofertas/. Crea una con `python -m engine.orq crear --brief <ruta>`. | Todavía no hay ofertas (carpeta ofertas/). Crea la primera con el comando `python -m engine.orq crear --brief <ruta>`, donde <ruta> es el archivo con la descripción de la oferta (el brief). |
| estado.json aún no existe: se muestran solo los artefactos que haya en disco. | Esta oferta todavía no tiene su registro de avance (estado.json), así que solo se ven los archivos que ya existen. |
| Próximo paso `sin_estado`: Todavía no hay estado.json: la oferta no se creó con el motor. | Esta oferta todavía no se registró en el sistema automático. El comando de abajo la registra. |
| Próximo paso `pausada`: La oferta está en pausa: hay que revisar el motivo antes de reactivar. | Esta oferta está en pausa. Revisa el motivo antes de reanudarla. |
| Próximo paso `firmar_gate`: D3 (…) espera tu firma (gate H). | D3 (…) espera tu firma (punto de control H). |
| Próximo paso `bloqueado`: D3 (…) está bloqueado: revisa el bloqueo. | D3 (…) está bloqueada: el sistema se frenó. Mira el motivo del bloqueo. |
| Próximo paso `escalado`: D3 (…) está escalado: revisa el bloqueo. | D3 (…) necesita que intervengas: el sistema no pudo seguir solo. Mira el motivo. |
| Próximo paso `en_curso`: D3 (…) está en_progreso. / está en_QA. | D3 (…) está en marcha. / está en revisión de calidad. |
| Falta el parámetro ruta. (`ruta_requerida`) | Falta indicar qué archivo abrir. |
| Ese tipo de archivo no se muestra desde el panel. (`extension_no_permitida`) | El panel no muestra ese tipo de archivo. |
| {ruta}: no existe en ofertas/<id>/ | Ese archivo no existe (ofertas/<id>/{ruta}). |
| La ruta es una carpeta; pide un archivo. (`no_es_archivo`) | Eso es una carpeta, no un archivo. Elige un archivo para abrirlo. |
| Aquí solo se pueden leer archivos de texto. (`solo_texto`) | Aquí solo se pueden abrir archivos de texto, no imágenes. |
| {ruta}: la imagen supera 1 MB y no se incrusta | La imagen pesa más de 1 MB y no se muestra en el panel ({ruta}). |
| El archivo es binario y no se puede mostrar como texto. (`archivo_binario`) | Este archivo no es de texto (es un archivo binario) y no se puede mostrar aquí. |
| {ruta}: recortado a 400 KB | Archivo muy grande: se muestran solo los primeros 400 KB ({ruta}). |
| 07-campana/ aún no tiene campana.json (lo arma D7). | Todavía no hay una campaña armada para esta oferta. La prepara la etapa D7 (carpeta 07-campana/). |
| Solo se muestran los últimos 60 días de KPI (hay N). | Se muestran solo los últimos 60 días de indicadores (hay N días en total). |
| 08-operacion/ no tiene datos todavía (KPI diarios, decisiones de D8, órdenes de presupuesto o veredicto). | Todavía no hay datos de operación: ni indicadores diarios, ni decisiones de D8, ni órdenes de presupuesto, ni veredicto (carpeta 08-operacion/). |
| Esa oferta aún no tiene landing generada. (`sitio_no_encontrado`) | Esa oferta todavía no tiene su página de venta (landing) generada. |

### Descubrimiento / barrido (`api_descubrimiento.py`)
| Viejo | Nuevo |
|---|---|
| …/{c}.json no existe: se muestra la etapa «solo-pasada1». | Todavía no está el resultado completo del barrido, así que se muestra el de la primera pasada (falta empresa/barrido/…/{c}.json). |
| Aún no hay corridas de barrido. Genera un plan con `python -m scripts.modelado.barrido plan generar <AAAA-MM-DD-a> --escribir`. | Todavía no hay ningún barrido de anuncios. Para empezar uno, crea su plan con el comando `python -m scripts.modelado.barrido plan generar <AAAA-MM-DD-a> --escribir` (cambia <AAAA-MM-DD-a> por la fecha de hoy y una letra, por ejemplo 2026-11-06-a). |
| {ruta} aún no existe. (candidatos, fichas, etiquetas) | Todavía no existe este resultado del barrido: aparece cuando el barrido avanza hasta ese paso ({ruta}). |
| …/planes/{c}.json aún no existe. | Todavía no hay un plan de consultas para este barrido. Se crea con el comando `python -m scripts.modelado.barrido plan generar {c} --escribir` (empresa/barrido/planes/{c}.json). |
| plan ilegible | No se pudo leer el plan de consultas de este barrido. |
| No hay ningún artefacto de la corrida {c}. | Todavía no hay nada del barrido {c}: ni plan, ni consultas, ni resultados. |
| {ruta} aún no existe (se genera con `barrido ingestar`). | Todavía no hay páginas para mostrar. Se generan con el comando `python -m scripts.modelado.barrido ingestar {c} --escribir` ({ruta}). |
| El parámetro x debe ser un entero. (`parametro_invalido`; también en el registro) | El valor de «x» tiene que ser un número entero. |

### Cumplimiento, finanzas, parámetros, gates y skills (`api_empresa.py`)
| Viejo | Nuevo |
|---|---|
| El ledger se corta a sus últimas 500 líneas (tiene N). | Del libro de movimientos se muestran solo los últimos 500 (hay N en total). |
| Las alertas se cortan a sus últimas 200 líneas (hay N). | Se muestran solo las últimas 200 alertas (hay N en total). |
| empresa/finanzas/ aún no existe: lo producen `python -m datos.ledger` (ledger, P&L y conciliación) y `python -m dashboard.alertas`. | Todavía no hay datos de finanzas. El libro de movimientos, las ganancias y pérdidas y la conciliación (que lo cobrado, lo registrado y lo gastado en anuncios cuadren) se generan con `python -m datos.ledger`; las alertas, con `python -m dashboard.alertas` (carpeta empresa/finanzas/). |
| Aún no hay dictámenes de X1 (ofertas/*/qa/x1-*.json) ni sellos (empresa/compliance/sellos/): los emite X1 al sellar (`compliance.sellar`). | Todavía no hay informes de cumplimiento (dictámenes) ni vistos buenos firmados (sellos). Los produce el revisor de cumplimiento (X1) cuando firma una aprobación con `compliance.sellar` (archivos ofertas/*/qa/x1-*.json y empresa/compliance/sellos/). |
| No hay empresa/limites.yaml, parametros.yaml ni autonomia.yaml. | Todavía no están cargados los límites de seguridad, los parámetros ni los niveles de autonomía (faltan los archivos empresa/limites.yaml, parametros.yaml y autonomia.yaml). |
| No se pudo leer contratos/gates.json, la tabla única de gates por etapa y nivel. | No se pudo leer la tabla de puntos de control: quién aprueba cada paso según el nivel de autonomía (archivo contratos/gates.json). |
| contratos/gates.json no trae el mapa «entradas» con la forma del contrato. | La tabla de puntos de control está mal armada: falta la lista «entradas» con el formato esperado (contratos/gates.json). |
| Se omitieron N entradas de contratos/gates.json que no tienen la forma del contrato. | Se omitieron N entradas de la tabla de puntos de control porque no tienen el formato esperado (contratos/gates.json). |
| contratos/gates.json no trae ninguna entrada válida. | La tabla de puntos de control no tiene ninguna entrada válida (contratos/gates.json). |
| Aún no hay skills forjadas: .claude/skills/ solo trae su README (se forjan en la pestaña Code). | Todavía no hay guías de trabajo (skills) creadas: la carpeta .claude/skills/ solo tiene su README. Se crean desde la pestaña Code. |
| El identificador de skill no es válido. | El nombre de la guía de trabajo (skill) no es válido. |
| De .claude/agents/ solo se leen <id>-maker.md y <id>-qa.md. | De esa carpeta solo se pueden ver las instrucciones de la IA que prepara (<nombre>-maker.md) y de la que revisa (<nombre>-qa.md). |
| No existe esa skill. | No encontramos esa guía de trabajo (skill). |

Campo `verificacion` de cada sello de cumplimiento:

| Viejo | Nuevo |
|---|---|
| la oferta del sello no existe en ofertas/: no se puede recalcular | La oferta de este visto bueno no existe en la carpeta ofertas/: no se puede comprobar si lo revisado cambió. |
| el sello no cita un dictamen | Este visto bueno firmado no cita ningún informe de cumplimiento (dictamen): no se puede comprobar. |
| el dictamen citado no existe o no es legible | El informe de cumplimiento (dictamen) que cita el visto bueno no existe o no se puede leer. |
| el dictamen no declara artefacto_ref: no se puede recalcular el artefacto | El informe de cumplimiento no dice qué archivos revisó: no se puede comprobar si cambiaron. |
| el artefacto del dictamen no existe o queda fuera de la oferta | Lo que revisó el informe de cumplimiento no existe o queda fuera de la oferta. |
| el artefacto contiene enlaces simbólicos: no se recalcula | Lo revisado contiene enlaces simbólicos (accesos directos a otros lugares): por seguridad no se vuelve a calcular su huella. |
| el artefacto es demasiado grande para recalcular su hash aquí | Lo revisado es demasiado grande para volver a calcular su huella desde el panel. |
| el artefacto ya no existe | Lo revisado ya no existe. |
| no se pudo recalcular el hash del artefacto | No se pudo volver a calcular la huella de lo revisado. |

### Registro y agentes (`api_registro.py`)
| Viejo | Nuevo |
|---|---|
| {archivo} aún no existe: lo escribe `engine.registro.registrar` cuando el motor ejecuta algo. | Todavía no hay historial de actividad ({archivo}): lo va escribiendo el sistema automático cada vez que ejecuta algo. |
| {archivo} aún no existe: la oferta demo no trae registro propio. | Todavía no hay historial de actividad ({archivo}): la oferta de demostración no trae uno propio. |
| Datos de DEMOSTRACIÓN (carpeta/)[: aún no existe empresa/registro.jsonl]. | Son datos de DEMOSTRACIÓN, no reales (carpeta carpeta/).[ Todavía no existe el historial real (empresa/registro.jsonl).] |
| CADENA ROTA en {archivo}: {motivo} | Historial alterado: el historial pudo haberse modificado ({archivo}). Motivo: {motivo}. No uses estos datos para decidir. |
| No se pudo comprobar la cadena: {motivo} | No se pudo comprobar que el historial esté intacto: {motivo} |
| Motivo: hay líneas sin hash o hash_previo | Motivo: hay líneas sin su huella (hash) o sin la huella de la línea anterior |
| Motivo: no se pudo importar el verificador de cadena (…) | Motivo: no se pudo cargar el verificador de la cadena (…) |
| Motivo: cadena no verificable | Motivo: no se pudo verificar la cadena |
| Se muestran las N ejecuciones más recientes de M. | Se muestran las N ejecuciones más recientes (hay M en total). |
| El identificador de ejecución no es válido. (`ejecucion_invalida`) | El código de la ejecución no es válido. |
| No hay una ejecución con ese identificador en la cola leída del registro. (`ejecucion_no_encontrada`) | No encontramos esa ejecución entre las más recientes del historial. |

### Cerebro (`api_cerebro.py`)
| Viejo | Nuevo |
|---|---|
| Todavía no existe empresa/memoria/: se crea la primera vez que /cerebro-cerrar guarda una decisión o una lección. | Todavía no hay memoria guardada. Se crea sola la primera vez que cierras una sesión con /cerebro-cerrar y se guarda una decisión o una lección (carpeta empresa/memoria/). |
| {ruta}: supera 400 KB; no se cuenta. | Un documento de decisiones es demasiado grande (supera 400 KB) y no se cuenta ({ruta}). |
| Libro de eventos de X2 (lo escribe el motor, no las skills del Cerebro) — `titulo` de `eventos.jsonl` | Libro de eventos del aprendizaje (lo escribe el sistema automático, no las guías de trabajo del Cerebro) |
| Decisiones de la adopción del sistema (J1-J9) — `titulo` de la fuente | Decisiones tomadas al adoptar el sistema (J1 a J9) |

### Robots y sistema (`api_robots.py`, `api_sistema.py`)
| Viejo | Nuevo |
|---|---|
| empresa/robots.yaml aún no existe: lo definirá el marco de robots (mapeo.md §10). | Todavía no existe el registro de robots. Lo va a definir el marco de robots (archivo empresa/robots.yaml; ver mapeo.md §10). |
| empresa/robots.yaml: contenido no interpretable | No se pudo entender el contenido del registro de robots (empresa/robots.yaml). |
| empresa/captura/freno.json: contenido no interpretable | El freno de la captura de anuncios está puesto, pero no se pudo leer su motivo; por seguridad se muestra como activo (detalle). |
| empresa/infra/estado.json aún no existe (lo escribe scripts/preflight.py) | Todavía no se hizo el chequeo antes de lanzar, así que no hay semáforo de infraestructura. Se hace con el comando `python -m infra.preflight ejecutar --modo completo` (el resultado se guarda en empresa/infra/estado.json). |
| empresa/infra/estado.json: contenido no interpretable | No se pudo leer el resultado del chequeo antes de lanzar; vuelve a hacerlo con `python -m infra.preflight ejecutar --modo completo` (detalle). |
| El vigía alcanzó su tope de N archivos: los archivos nuevos o más allá del tope ya NO generan eventos en vivo (el panel puede mostrar datos viejos hasta recargar). Reduce lo observado o sube el tope. | El vigía alcanzó su límite de N archivos (el vigía es el que avisa al panel cuando algo cambia). Los archivos nuevos o más allá del límite ya no se actualizan en vivo: si ves datos viejos, recarga la página. Para solucionarlo, vigila menos archivos o sube el límite. |

### Alertas, semáforo e informe (`api_alertas.py`, `scripts/alertas/*`, `scripts/informe/*`) — texto nuevo (2026-11-07)
Textos que viajan desde Python en `GET /api/alertas` y `GET /api/informe`. Son **plantillas fijas** en tuteo: la acción de cada alerta empieza por quién la hace («Te toca a ti», «Le toca al equipo técnico (S-B)»), no copia texto de ningún archivo y no pasa de 300 caracteres.

| Dónde | Texto |
|---|---|
| Aviso si el archivo guardado no se puede leer | El archivo de alertas guardado no se pudo leer entero; se muestran solo las alertas calculadas ahora. |
| Veredicto del semáforo | Todavía no te puedes ausentar · Te puedes ausentar, con cuidado · Sí, te puedes ausentar |
| Resumen del semáforo (rojo) | Faltan N cosas (K importantes; M te tocan a ti). Hasta que las K importantes estén listas, si te ausentas nadie te avisa de un problema o el sistema no puede trabajar solo. |
| Cada paso del semáforo | título · estado · «Qué hacer» · a quién le toca (Tú · Equipo técnico (S-B) · Equipo S-A) · enlace a su pantalla · comando copiable (que ejecuta una persona) |
| Alertas nuevas (`titulo`) | La PAUSA (freno de emergencia) está puesta · La captura de anuncios está frenada · Faltan N límites de dinero por fijar · Los límites de dinero no están firmados · Falta el chequeo de cuentas y servicios · Los avisos al celular no tienen dos canales · Todavía no hay planificador: nada corre solo · Falta una cuenta de Meta lista para lanzar · Falta dejar listo el correo para entregar el producto · Espera tu firma: <etapa> · Un pendiente tuyo está vencido |
| Informe (correo) | `INFORME DEL DÍA — <fecha> · 08:30` · `1. VENTAS Y GASTO` · `2. LOS 5 AVISOS` (pagos, lo importante, cansancio de anuncios, mercado nuevo, lo que no aprobaste) · `3. LOS CEROS QUE IMPORTAN (la meta es 0)` · `4. LO QUE TE TOCA A TI` · `5. LO QUE TODAVÍA NO SE PUDO MEDIR` |
| Informe sin datos | Todavía no hay datos de ventas ni de gasto del <fecha>: no hay ninguna campaña en prueba ni en escala. |
| Un «cero» que no se midió | `sin medir` + por qué (nunca un 0 que parezca bueno) |
| Pie del informe | Este informe lo arma un programa con una plantilla fija y solo lee archivos de tu proyecto. No contiene texto escrito por una IA ni por terceros. |

### Robots en sombra (`api_robots.py › sombra`, `robots_sombra.py`) — texto nuevo (2026-11-07)
| Dónde | Texto |
|---|---|
| Aviso si no hay foto (`vacio`) | Todavía no corrió ningún robot en sombra con la opción de guardar, así que no hay foto de su estado (empresa/robots/estado.json). Se genera con el comando `…sombra ejecutar --todos --escribir`; para probar sin guardar nada: `…sombra ejecutar --todos --simular`. |
| Aviso si el archivo no se puede usar | El estado de los robots en sombra (empresa/robots/estado.json) no tiene la forma esperada; se ignora. (o el aviso de lectura del archivo: dañado, demasiado grande…) |
| Motivo de un robot que la foto daba al día | último latido hace N min (máximo M); la foto lo daba al día |
| Los tres estados (pantalla y semáforo) | **No hay nada programado** · **Robots en sombra corriendo (solo lectura)** · **Latido vencido** |
| Fila del semáforo (planificador), sin planificador real | Todavía no hay nada programado: nada se despierta solo y no hay señales de vida… / Robots en sombra corriendo (solo lectura): N programados y al día. Ensayan el trabajo, pero no son el sistema real… / Latido vencido: N robots en sombra programados dejaron de dar señal de vida a su hora (nombres)… |
| Alerta `F2-A17:sombra` (amarilla) | N robots en sombra programados no dieron señal de vida a su hora. Revisa si tu Mac estaba dormida o si se quitó la programación; mira cuáles en Robots. |
| Advertencia de `programar` | Solo imprime las líneas para el programador de tu Mac: no instala nada. Instalarlas es decisión tuya: con la Mac dormida los robots pierden vueltas, así que esto no es una red de seguridad. |

## 6. Pendientes fuera de mi área (PEDIDOS)

Estos archivos también producen texto visible, pero no estaban en el alcance de este trabajo. Quedan con jerga y conviene reescribirlos con el mismo criterio (las pruebas de `tests/dashboard` comprueban algunas de estas frases, así que habría que actualizar esas aserciones a la vez):

| Archivo | Texto actual (ejemplos) | Propuesta |
|---|---|---|
| `dashboard/archivos.py` (los avisos de lectura que casi todas las pantallas repiten) | {ruta}: JSON inválido (JSONDecodeError) | El archivo está dañado o mal escrito y no se pudo leer ({ruta}). |
| ídem | {ruta}: supera el tope de N KB y no se interpreta | El archivo es demasiado grande (más de N KB) y no se lee ({ruta}). |
| ídem | {ruta}: archivo grande; solo se lee la cola (últimos N KB) | El archivo es muy grande: se leen solo los últimos N KB ({ruta}). |
| ídem | {ruta}: N línea(s) ilegibles (¿corrupción o escritura a medias?) | {ruta}: N línea(s) no se pudieron leer (el archivo pudo dañarse o quedar a medias). |
| ídem | {ruta}: no se pudo leer | No se pudo leer el archivo ({ruta}). |
| ídem (errores de ruta) | La ruta no es válida. / Solo se admiten rutas relativas. / La ruta intenta salir de su carpeta. | La dirección del archivo no es válida. / Solo se admiten direcciones relativas. / La dirección intenta salir de su carpeta. |
| ídem | La bitácora alcanzó su tamaño máximo. | La bitácora está llena: no admite más anotaciones. |
| `dashboard/pulido.py` | La bitácora aún no existe: se crea con la primera anotación (empresa/panel/pulido.jsonl). | Todavía no hay anotaciones: la bitácora se crea con la primera (empresa/panel/pulido.jsonl). |
| ídem | El campo X debe ser texto. / es obligatorio. / debe ser uno de: … | «X» tiene que ser un texto. / es obligatorio. / tiene que ser uno de estos: … |
| ídem | No existe una entrada con ese id en la bitácora. | No encontramos esa anotación en la bitácora. |
| ídem | El campo etapa debe ser una etapa válida (M1, D1…D10, O0, D0, F1, F2, X1, X2). | La etapa no es válida. Elige una de la lista (M1, D1 a D10, O0, D0, F1, F2, X1, X2). |
| `dashboard/web/lib/sistema.js` (`GRUPOS_ACCION.quitar`) | Quita los prefijos «Barrido: », «Validar » y «Landing: » del título de cada acción. | Borrada (2026-11-06): los títulos nuevos ya no empiezan así, así que la expresión no coincidía con nada. Se muestra el título completo. |
| `tests/fixtures/dashboard/shell/api/acciones.json` | Instantánea de `GET /api/acciones` con los títulos viejos. | Regenerada (2026-11-06) leyendo `dashboard/acciones.yaml` con el mismo cargador del servidor: trae los títulos, descripciones y avisos actuales de las acciones que las pruebas necesitan, más dos acciones de prueba (una con parámetro numérico y otra que escribe en local). |
