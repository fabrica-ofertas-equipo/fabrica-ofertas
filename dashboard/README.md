# dashboard
Panel del dueño: agregación de KPIs, estado de ofertas, alertas y cola de aprobaciones.
Propietario: 13-dashboard-bi (más 12-finanzas para costos y márgenes).
Solo lectura sobre empresa/ y ofertas/; no ejecuta acciones con dinero.
CLI: python -m dashboard.<modulo>.
Probar: python3 -m unittest discover -s tests/dashboard -t .

## Alertas, informe de las 08:30 y «¿Me puedo ausentar?» (2026-11-07)
- `python -m dashboard.alertas` (= `python -m scripts.alertas.producir`): calcula las alertas con archivos locales. **No escribe nada** salvo con `--escribir` (`empresa/datos/alertas.jsonl`); `--semaforo` muestra el «¿me puedo ausentar?».
- `python -m scripts.informe.informe_diario`: compone el informe del día (correo con importes y celular con porcentajes). **No envía nada.**
- El panel los muestra con `GET /api/alertas` y `GET /api/informe` (Resumen y Avisos). Detalle: `CONTRATO.md` §12.
- Arranque sin abrir el navegador: `python -m dashboard --puerto 8790 --no-abrir`.

## Landing original del referente (2026-11-08)
- Pedido del dueño: «de cada oferta poder encontrar la landing original». El barrido de la Biblioteca de Anuncios **no trae** la dirección de la landing (solo guarda 7 campos por anuncio), así que se **registra una vez** y el panel la muestra.
- Registrar: `.venv/bin/python -m scripts.referentes.landing registrar <page_id> "<URL>" [--oferta OF-AAAAMM-NN] [--nota …] [--copia-local ruta] --escribir` (sin `--escribir` simula). También `listar`, `ver <page_id>` y `quitar <page_id> --escribir`. Archivo: `empresa/barrido/referentes/landings.json`.
- Dónde se ve: **Radar de ofertas → ficha de la página** (sección «Landing original», con el comando y las direcciones de Meta para copiar si todavía no está registrada) y **Oferta → tarjeta «Landing original del referente»** (junta el registro y los `landing_url` de D2).
- Seguridad: es lo ÚNICO que el panel vuelve enlace externo (botón explícito, `target=_blank`, `rel=noopener noreferrer`, https validada en el servidor y otra vez en el navegador). Las direcciones de Meta siguen siendo texto para copiar. Detalle: `CONTRATO.md` §4 (`/referente`). Pruebas: `tests/referentes/`, `tests/dashboard/test_servidor_referente.py`, `test_web_descubrimiento.mjs`, `test_web_oferta.mjs`.

## Modo «negocio» (por defecto desde el 2026-11-12) y modo «completo»
- Pedido del dueño: «simplificá el dashboard a lo mínimo que sea decision maker». Se trabaja desde sesiones de Claude con la guía `modelar-y-lanzar-oferta`; lo único que se mira son los números.
- El panel abre en `#/negocio`. Menú: «Todas las ofertas» y un acceso por oferta (con un punto del color de su acción sugerida). Sin barra de freno, pausa, DEMO, selector de oferta, buscador ni atajos; cualquier otra ruta lleva a `#/negocio`.
- **Volver al panel completo**: abrir `http://127.0.0.1:8790/?modo=completo#t=<clave>` (el `?modo=` va antes del `#`). Queda recordado en ese navegador (`localStorage` `panel.modo`); `?modo=negocio` vuelve al simple. No se borró ninguna pantalla ni ruta: `modoDelPanel`, `rutaPermitida` y `navDelModo` en `web/app.js`.

## Negocio: qué hacer con cada oferta (2026-11-12)
- Cartera: corte de datos con su antigüedad; una línea con gasto, neto, ganancia neta, retorno neto y ofertas que ganan o pierden; una tarjeta por oferta con la **acción sugerida** (apagar cuando una oferta sin ventas gastó 1,5 × el precio del front, regla firmada por el dueño el 12-nov y aplicada sola por la vigilancia de cada hora; escalar con ≥ 3 ventas y costo por venta bajo el equilibrio, propuesta sin firmar; sin pauta si no arrancó; mirar un día más en lo demás) y su porqué, el embudo contra 8-12 % y 25-30 %, «Qué está vendiendo» (3 anuncios con más compras o gasto) y el próximo cambio programado (campo opcional `programado: [{cuando, que}]` del libro). «Cómo se calcula» plegado al final.
- Ficha `#/negocio/<oferta>`: acción, embudo y próximo cambio; ganancia paso a paso; historial por día; ventas una por una (sin compradores); anuncios; documentos y enlaces (tienda y landing original).
- Datos: `ofertas/_funnels/libro-de-tests.json` con `GET /api/negocio`; documentos con `GET /api/negocio/documento?ruta=` (solo `ofertas/_funnels/…` y `ofertas/_borrador-*/estado.md`). Cálculo en `dashboard/negocio.py` (mismas fórmulas que `libro_de_tests.py`, más fijos prorrateados, ROAS Meta y ROAS real, equilibrio estimado, acción sugerida, anuncios que venden y cambios programados). Script de la tabla: `.claude/skills/escalar-oferta/scripts/libro_de_tests.py`.
- Métricas de cada funnel (ficha, arriba) con las definiciones del dueño: facturación bruta, comisiones, facturación neta, costos (Meta, producción, fijos, total), ganancia contra Meta y neta, ROAS Meta (valor atribuido por Meta ÷ gasto), ROAS bruto real, ROAS neto (neta ÷ Meta) y ROAS real (neta ÷ Meta + producción + fijos), ventas reales y atribuidas, ticket medio, CPA real y de equilibrio. La producción no entra en el ROAS; sí en el ROAS real y la ganancia neta. La cartera muestra ROAS neto y ROAS real; cada tarjeta, ROAS Meta · neto · real.
- Los carga el agente en la revisión del funnel (skill `escalar-oferta`, `references/01-revision-diaria.md`, apartado «Para que el tablero Negocio quede al día»). Pruebas: `tests/dashboard/test_servidor_negocio.py`, `test_web_negocio.mjs` y las del modo en `test_web_shell.mjs`.

## Negocio simplificado (2026-11-12, noche)
- Pedido del dueño: «esto no se entiende nada, simplificarlo». La pantalla queda en 3 cifras (ganancia neta, gasto, ROAS neto), «Datos al …» y una FILA por oferta: bandera y nombre, pastilla con el veredicto (Escalar, Mirar, Apagar, Sin pauta o Pausada; la firma de la regla va en el «?»), ganancia contra Meta, ROAS neto, ventas, una frase de ≤ 80 caracteres y el próximo cambio programado (`programado[].corto`). Toda la fila abre la ficha.
- Una campaña pausada o cerrada tiene veredicto «Pausada» (`dashboard/negocio.py`, `veredicto_de_fila`), nunca «mirar un día más».
- Ficha: veredicto y 3 cifras (un solo medidor: ROAS neto) → métricas del funnel en una tabla de dos columnas → embudo simple → anuncios → historial, ventas y documentos.
- Signo y color en todo el panel: lo que entra en verde con «+», lo que sale con «−» en tono neutro, los resultados con «+» verde o «−» rojo.
- Anuncios: por anuncio, gasto, compras, CPA, ROAS Meta, ROAS neto estimado (compras × neto medio por venta ÷ gasto), CTR, clic → pago, retención del video y veredicto (Ganador, Promete, Sin datos, Flojo, Mirar), con una línea de lectura arriba; en móvil, una tarjeta por anuncio. Datos: `anuncios.lista` de cada test del libro (lectura de Meta por anuncio).

## Filtro de días (2026-11-12)
- Selector arriba en Negocio y en cada ficha: Hoy · Ayer · Últimos 7 · Últimos 14 · Últimos 30 · Este mes · Mes anterior · Desde el inicio (por defecto), y «Elegir días»: calendario propio donde un clic elige un día y un segundo clic arma el rango. El período va en la dirección (`#/negocio?desde=AAAA-MM-DD&hasta=AAAA-MM-DD`, `?periodo=inicio`) y se recuerda en el navegador (`localStorage` `negocio.periodo`). Código: `web/lib/negocio-periodo.js`.
- Servidor: `GET /api/negocio?desde=…&hasta=…` → `dashboard/negocio.py` `calcular_periodo` / `libro_del_periodo`. Días en la zona de la cuenta publicitaria (`zona_horaria_cuenta` del libro). Meta (campaña y anuncio), ventas y embudo se suman por día; la producción entra solo si el día de inicio de la pauta cae en el período; los fijos se reparten por día; el embudo sin lectura de algún día queda «sin dato completo»; sin datos, «—». El veredicto se calcula siempre desde el inicio.

## Etapa y backend de cada oferta (2026-11-13)
- Pedido del dueño: con 15-20 ofertas en test, ver de un vistazo si cada una tiene backend ofensivo (upsells post-compra) y en qué etapa está.
- Etapas (las calcula `negocio.py` → `etapa_de`): Programada · En test · Para renovar (pasó el test sin ronda corriendo) · Renovación programada · Renovando (3 días desde el inicio de la ronda) · Para apagar (corte de 1,5 tickets) · Apagada. Backend (`backend_de`): activo · en pausa · en armado · sin backend; «Falta backend» si pasó el test sin backend activo (también va a «Requiere tu atención»).
- Dónde se ve: tira de filtros con conteos sobre la lista (se recuerda en `localStorage` `negocio.filtroEtapa`), chips en cada fila, caja «Etapa / Backend ofensivo» en la ficha, y en el menú lateral las ofertas agrupadas por etapa (lo urgente arriba) con la marca «B» (verde activo, «B!» ámbar falta, punteada sin backend). La lista se ordena por urgencia de la etapa.
- Datos: campos `renovaciones` y `backend` de cada test del libro (skill `escalar-oferta`, `01-revision-diaria.md`). Código del navegador: `web/lib/negocio-etapas.js`. Fixture: `tests/fixtures/dashboard/negocio/generar_fixture.py`.

## «Cómo funciona»: el sistema como flujo vivo (2026-11-13)
- Pedido del dueño: dividir el sistema en procesos, ver cuándo se activa cada uno y qué skill lo hace, «como un flujo que esté vivo».
- Ruta `#/flujo` («Cómo funciona»), en el menú del modo «negocio» debajo de «Todas las ofertas»; también se abre en el modo completo, pero no entra en sus piezas ni en sus atajos (`ENTRADA_FLUJO` / `RUTAS_EXTRA` en `web/app.js`).
- Pantalla: pulso (última vuelta de la vigilancia, banco de candidatos, ofertas en juego, lo que espera tu OK) → diagrama Buscar → Lanzar → Test del día 1 → (Apagar | Backend ofensivo → Revisar, renovar y escalar) → Aprender, con las ofertas que están en cada paso AHORA (salen de la etapa del libro) → detalle del paso tocado → brechas encontradas en la revisión de las skills.
- Datos: `GET /api/negocio` (etapa y backend) y `GET /api/flujo` (`dashboard/api_flujo.py`: última vuelta de `ofertas/_funnels/vigilancia.jsonl`, `banco_candidatos.py estado --json`, carpetas `_borrador-*` que aún no están en el libro, versión de las skills y `historial-modelado.json`). Solo lectura.
- Textos de los pasos y lista de brechas: `web/lib/flujo.js` (`PROCESOS`, `BRECHAS`). Si una skill cambia de dueño de un paso, se cambia `skill`/`guia`; si se cierra una brecha, se borra de `BRECHAS`.
- Pruebas: `tests/dashboard/test_web_flujo.mjs`, `tests/dashboard/test_api_flujo.py` y las del modo en `test_web_shell.mjs`.
- Ronda 2 (13-nov, noche): el diagrama sigue la división en cuatro skills (`buscar-ofertas`, `modelar-y-lanzar-oferta`, `backend-ofensivo`, `escalar-oferta`); nueva sección «Una regla por situación» (`REGLAS` en `web/lib/flujo.js`, espejo de `escalar-oferta/references/02-decidir.md`, con estado firmada · propuesta · falta), «Lo que falta para que sea automático» (`BRECHAS`) y lo cerrado (`CERRADAS`). `/api/flujo` suma `buscar_diario` (último informe de `empresa/barrido/banco/diario/`).
- Negocio: el corte usa el ticket del producto completo (`negocio.ticket_corte`) y ya no hay frenos de cuenta (los eliminó el dueño el 13-nov).

## Ocultar info (2026-11-13)
- Pedido del dueño, para grabar la pantalla para YouTube: «no quiero dar a conocer el nombre de las ofertas pero sí que se vea la bandera», como el botón «Ocultar info» de Impultienda.
- Botón «Ocultar info» junto a «Actualizar» en Negocio y en cada ficha (en el modo completo, en la barra superior). Menú con casillas: nombres de ofertas (y tiendas, fan page, píxel), productos y upsells, anuncios y campañas, referentes, montos de dinero. Prendido dice «Info oculta» en ámbar. Se recuerda en el navegador (`localStorage` `panel.ocultar`).
- Difumina el texto en todo el panel (también menú lateral, migas, avisos y gráficos) y tapa con «•••» lo que aparece al pasar el cursor y el título de la pestaña. Con los nombres ocultos, la dirección de la ficha usa el número de la oferta (`#/negocio/~2`). Banderas, colores, íconos, ROAS y porcentajes siempre se ven.
- 15-nov (dueño: «que también se pongan borrosas las imágenes, los anuncios y lo que pueda delatar la oferta»): casilla nueva «Imágenes y creativos», prendida por defecto (lo ya guardado la recibe prendida: `version` 2 en `panel.ocultar`), que difumina toda imagen, video, iframe o lienzo (miniaturas del top de creativos, imagen grande, piezas). Además se tapan: las carpetas de trabajo (`_borrador-oferta-f`, `kit herencia`… de `/api/ofertas`, en el selector y en las pantallas por etapa), los IDs de fan page, píxel, cuenta, campañas, conjuntos, anuncios y creativos, las partes del nombre del referente («ReferenteA»), las opciones del selector y la dirección de los enlaces externos (la barra de estado muestra «•••»; el clic abre el destino real). Palabras del panel como «oferta» nunca se tapan aunque un dato las traiga como nombre.
- Código: `web/lib/ocultar.js` (textos sensibles sacados de `/api/negocio` y `/api/ofertas`, observador del DOM y CSS por categoría). Pruebas: `tests/dashboard/test_web_ocultar.mjs`.

## Siempre prendido y con dirección fija (2026-11-13)
- Pedido del dueño: «tenerlo fijado y no pedirte siempre que lo abras».
- Agente de inicio `~/Library/LaunchAgents/com.fabrica.panel.plist`: arranca el panel al iniciar sesión en la Mac (puerto 8790) y lo vuelve a levantar si se cae. Registro en `~/Library/Logs/fabrica-panel.log`.
- `--clave-fija`: la clave se guarda en `~/.config/fabrica-panel/clave` (permisos 600) y no cambia entre arranques, así la dirección se guarda como marcador en Chrome.
- Reiniciar tras cambiar código de Python: `launchctl kickstart -k gui/$(id -u)/com.fabrica.panel`. Quitarlo: `launchctl bootout gui/$(id -u)/com.fabrica.panel` y borrar el plist. Cambiar la clave: borrar el archivo de la clave y reiniciar (los marcadores viejos dejan de servir).
- Las sesiones de Claude NO deben levantar otro panel con `nohup` en el 8790: el puerto ya está ocupado por este.

## Agenda de cada oferta y «Lo que viene» (2026-11-14)
- Pedido del dueño: «que se agregue al dashboard en cada oferta los siguientes pasos (en tiempo real) de lo que está programado… para saber qué se programó, qué se está aplicando, qué se está por hacer, qué se hizo».
- Ficha `#/negocio/<oferta>` → sección «Agenda: qué está pasando y qué viene»: **Ahora** (en curso, con «hasta»), **Te toca a vos**, **Lo que viene** (con hora de Argentina y «en 2 h»; las tareas que se repiten llevan «se repite»), **Lo que hoy no va a pasar** (p. ej. «sin renovación: CPA > equilibrio», «armada, sin activar») y **Lo que ya se hizo** (últimos 14). Cartera `#/negocio` → «Lo que viene» de todas las ofertas y «Tareas automáticas» (próxima corrida, última y su resultado). Cada fila de la cartera muestra el próximo paso si el libro no trae un `programado`.
- Servidor: `dashboard/agenda.py` (`agregar_agendas`, llamado desde `/api/negocio`). Fuentes: el libro (inicio, fin del test, `backend` con `activar_desde`/`bump_al_activar`, `renovaciones`, `presupuesto_cambios`, `programado`, `apagado` y el campo nuevo **`pendientes: [{que, desde, porque, hecho}]`** para lo que le toca al dueño), `vigilancia.jsonl`, `escala.jsonl`, `avisos.jsonl`, `latidos.json`, `vigilancia_vuelta.json` y **`ofertas/_funnels/tareas.json`** (horario de cada tarea; lo refresca la vigilancia en cada vuelta completa con `.claude/skills/escalar-oferta/scripts/tareas_snapshot.py`, punto 2d de su tarea). La próxima corrida se calcula con el cron en cada pedido, así no envejece. Las zonas de los mercados salen de la tabla `ZONA` de `control_previo.py`, leída como texto.
- En vivo: se vuelve a pintar cuando cambia algo en `ofertas/_funnels/` (eventos del servidor); los «en …» se actualizan cada 30 s y, cuando llega la hora de algo que viene, la página se recarga (`web/lib/agenda.js`).
- Pruebas: `tests/dashboard/test_agenda.py`.
