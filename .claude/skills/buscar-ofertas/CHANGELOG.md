# CHANGELOG · buscar-ofertas

## Nota de vuelta · 2026-11-17 · medir: arrancar por el fetch de 0.6.4

- Vuelta del radar (reposición, 30 a medir): medir navegando `url_medir` uno por uno dio 0 resultados en 20 de 30 (Payhip, Gumroad, Stan, Systeme y la mayoría de Kiwify/Hotmart: el código va solo en el enlace del botón, no en el texto). El número de `pagina_url` (6158…) como `view_all_page_id` también da 0. El fetch por ficha de 0.6.4 resolvió los 20 en ~40 s con su `page_id` real: usarlo de entrada, no como respaldo.
- Si el navegador integrado devuelve «denied or failed» o `chrome-error://`, mirar la red antes de avisar: el 17-nov `www.facebook.com` resolvía solo IPv6 sin ruta; a los ~2 min volvió solo. No es un rechazo del sitio.

## 0.6.4 · 2026-11-15 (tarde) · medir 30 por fetch sin navegar

- Vuelta del radar (reposición, 30 a medir): en vez de navegar oferta por oferta, desde una pestaña de la Biblioteca se hace `fetch('/ads/library/?active_status=all&country=ALL&search_type=page&id=<ficha>')` y se lee el JSON incrustado (`search_results_connection` → `collated_results[]` con `ad_archive_id`, `page_id`, `collation_count`, `start_date`, `snapshot.cards[].link_url`); con ese `page_id`, otro fetch a `view_all_page_id=<id>&country=ALL&active_status=active` da `count` (total de la página) y las tarjetas de la primera tanda para contar las que van al destino. 30 ofertas en ~2 min, sin captcha. Si la ficha ya no está activa, la Biblioteca devuelve otra cosa (p. ej. la página de Meesho): comprobar que `ad_archive_id == ficha`.
- Correr el bucle en segundo plano (`window.__run` guarda en `window.__res`) y consultar cada ~40 s: `javascript_tool` corta a los 45 s.
- Resultado: 29 de 30 bajo el piso (casi todas páginas de Hotmart/Kiwify/Gumroad con 1-8 anuncios: el evergreen de 1 anuncio sigue llenando a_medir de afiliados chicos); 1 sobre el piso (Franck Ropers, masterclass-ca, 26+ anuncios) descartada al verificar por marca personal y webinar.
- Para guardar lo que lee `radar_lector.js` sin transcribir JSON largo: devolver una línea TSV por grupo y rearmar el JSON en Python.

## 0.6.3 · 2026-11-15 · medir ofertas de constructores compartidos por página

- Vuelta del radar del 15-nov (modo reposición, 30 a medir): el código de `url_medir` de las ofertas de `inlead.digital` es la ruta del destino (`oxy`, `sdm`, `3-for-99`…) y como frase exacta trae anuncios de cualquiera (`"oxy"` = 23.000); la ruta completa (`"inlead.digital/oxy"`) da 0. Tampoco sirven los códigos de Hotmart en 5 de 6 casos (0 resultados aunque la página tiene anuncios activos con ese enlace).
- Lo que funcionó: tomar la `ficha` del hallazgo (`hallazgos.jsonl`), abrir `ads/library/?id=<ficha>` (redirige con `view_all_page_id`), abrir esa página con `country=ALL`, cargar 3 tandas y contar las tarjetas cuyo enlace contiene el destino (suma de «N anuncios usan este contenido»); días = la tarjeta más vieja de ese destino. Se anota con `--page-id`. Es un mínimo cuando la página tiene más de ~30 tarjetas.
- Los quiz de inlead no responden a `element.click()`: hace falta disparar `pointerdown/mousedown/pointerup/mouseup/click` sobre el botón. El HTML del quiz viene cifrado (`__NEXT_DATA__.q`), el precio y el checkout solo se ven recorriéndolo.

## 0.6.2 · 2026-11-14 noche · reposición por frases de entrega y referente_paises en el banco

- Reposición para la tanda 15-17 nov: las frases de entrega del catálogo del radar («descarga inmediata», «téléchargement immédiat», «natychmiastowy dostęp»…) en `country=ALL` con fecha tope trajeron 6 listos en una vuelta (operadores con tienda propia o Impultienda en varios idiomas); hasta ahora el radar solo había corrido búsquedas de plataforma.
- `banco_candidatos.py importar` conserva `referente_paises` del candidato (antes se perdía al importar) y `estado` lista también los simples listos en texto (antes solo en `--json`).
- Para sacar `page_id` y destinos sin abrir cada tarjeta: el HTML de la Biblioteca trae el JSON de la primera tanda de resultados (`"page_id"`, `"page_name"`, `"link_url"`); la CSP de Facebook no deja `eval`, el fragmento se pega entero en cada llamada.

## 0.6.1 · 2026-11-14 noche · ceros del referente en países bloqueados

`01-elegir-del-banco.md` §1.2b: un 0 del referente en SG, TW, TH, MY, AU o IN no es hueco mientras el portfolio no tenga anunciante verificado (Meta tampoco deja pautar ahí); `ordenar_candidatos.py` ya los saca de los lanzables. Y un grupo de países con anuncios no se anota como medido: se parte hasta países sueltos. Origen: Oferta J (Maku en 89 de 93 países, 0 solo en esos 4).

## 0.6.0 · 2026-11-14 · Radar en 93 mercados

Con `elegir_mercado.py` v6 (93 países) el radar suma 19 idiomas de entrega (ru, uk, bg, sk, sl, hr, sr, bs, mk, lt, lv, et, ka, hy, az, mn, ur, bn, si); frases escritas por el asistente y sin probar en la Biblioteca. `radar.py cola generar`: 1.045 búsquedas (antes 711), estadísticas conservadas. `paises_referente.py universo` mira los 93.

## 0.5.0 · 2026-11-14 · Veto del referente al elegir

Tras Oferta D (lanzada en México con el original pautando ahí en los 57 países): `01-elegir-del-banco.md` §1.2b mide los países del referente del candidato antes de tomarlo; `ordenar_candidatos.py` deja fuera al que no tiene ningún país libre y la medición pasa a `elegir_mercado.py --medicion` (v5, veto país por país). Detalle en el CHANGELOG de modelar-y-lanzar-oferta 0.10.4.

## 0.4.0 · 2026-11-14 · Países del referente

Pedido del dueño: ver en el panel, con banderas, en qué países corre la oferta original de cada oferta nuestra, para no pautar ahí (acompaña la réplica de las ganadoras).
- `scripts/paises_referente.py`: mide por mitades con `ads_library_search` (page_ids + countries, activos, limit 1) sobre los 57 países de `elegir_mercado.py` y guarda en `ficha.referente_paises` del libro (con candado, vía `libro.py`).
- `04-vuelta-diaria.md` paso 5 y prompt de la tarea «buscar-ofertas» (paso 3): se refresca cada mañana (vencida a las 20 h).
- `elegir_mercado.py ordenar … --oferta "<oferta>"` saca esos países (y los que la oferta ya usa); E6 en `escalar-oferta/references/02-decidir.md` lo pide.
- Panel, Negocio: renglón «Original corre en: 🇬🇧 47 · 🇦🇺 9 · Nosotros: 🇪🇸» en cada oferta y sección «Dónde corre la oferta original» en la ficha; rojo si coincide con nuestro país; banderas desenfocadas en el modo ocultar (Referentes).
- Medido el 14-nov: Oferta F GB 47 · AU 9 (17 países mirados a mano); Oferta B 25 países (Europa, EE. UU., Canadá, Oceanía; 0 en América Latina y Asia); Oferta D los 57 (incluido MX 127, en inglés); Oferta E solo BR 22. Páginas nuevas anotadas: Referente D 100000000000068 (Oferta D), Referente E 100000000000073 (Oferta E).

## 0.3.0 · 2026-11-14 · Verificar y medir antes de buscar

El radar buscaba primero y se quedaba sin vuelta para medir y verificar: el 14-nov había 509 ofertas sin medir y 4 sin verificar mientras el lanzamiento esperaba candidatos; y dos vueltas murieron en silencio porque el navegador rechazó web.facebook.com y kiwify.app.
- `radar.py plan [--json]`: cuotas de la vuelta desde `reglas.json → radar` (verificar ≤ 10, medir 20 o 30 en reposición, buscar 15 o 5 con atasco ≥ 300 sin medir).
- `05-radar.md`: orden fijo verificar → medir → buscar; con bloqueo se verifica igual; navegador rechazado → seguir y avisar urgente (`permiso-navegador-<sitio>`).
- `04-vuelta-diaria.md`: con el banco bajo la reserva de 3, reponer va antes de medir el banco; prompt vigente copiado.
- Verificadas a mano el 14-nov: BossaColor (LUTs, vsl, al banco), Adesiva Pro (figurinhas, tsl simple: verificada pero no cuenta como compleja), Imersão Low Ticket y Mapa mental C-PRO R (no producibles).

## Nota de la vuelta diaria · 2026-11-14

- Banco medido (18 de 20; inlead mmcsc e ingresos-extra sin poder contarse). Contexto Filosófico pasa a medirse por página; Maku corregido a `tsl` + `bump` (`landing-simple` rompía `estado`).
- Barrido de reposición con 15 términos no usados (5 constructores, 4 «quiz + producto», 6 frases pt/es): entró ReferenteG (quiz+tsl, verificada y producible). El navegador rechazó kiwify.app y, al final, web.facebook.com: quedaron sin hacer las iteraciones de video y el referente S04.

## Nota de la vuelta del radar · 2026-11-13 (tarde)

- Medir: en kiwify.app (`vAKjNZg`, `SZOhdTr`) y en las rutas de inlead.digital (`formulario-de-aplicacao-craf`), el código buscado como frase exacta da 0 resultados. Lo que funcionó: abrir `ads/library/?id=<ficha>`; la Biblioteca redirige con `view_all_page_id=<id>`, y con ese id se abre la página con `country=ALL`. Ahí se lee el total y se cuentan las tarjetas que van al destino. Va con `medir --page-id`.
- `medir --paises` no lleva texto libre: lo toma como códigos de país y altera el hueco. Que se midió por página queda dicho con `--page-id`.
- Con frase exacta, `digistore24.com` (FR, GB), `clickbank.net` (GB), `elopage.com` (ALL, DE) y `monetizze.com.br` (BR) dieron 0. Si siguen en 0 en la próxima pasada, bajarles la prioridad.

## 0.2.2 · 2026-11-13

Pedido del dueño: el radar pasa de cada 2 a cada 4 horas («Sí, cada 4 horas»). Motivo: 12 vueltas por día de 11 a 15 minutos con el navegador, y en las dos primeras ninguna oferta llegó al banco. La cola mundial de 711 búsquedas se recorre en ~8 días en vez de ~4.



## 0.3.0 · 2026-11-13

- `banco_candidatos.py limpiar`: saca del banco las ofertas con dos mediciones seguidas bajo el piso (S03).
- `radar.py referentes` / `referente-medir`: sigue al referente de cada oferta activa y avisa si acelera (S04).
- `radar.py agregar`: ofertas hermanas de un operador que ya tiene una joya (S05).
## 0.2.1 · 2026-11-13 · Revisión de coherencia 2026-11-13

- `SKILL.md`, `01-elegir-del-banco.md`, `02-barrido-por-forma.md`, `04-vuelta-diaria.md` y su prompt: el radar es el camino principal para encontrar y reponer; el barrido por forma queda como complemento (y `clasificar`). La descripción de la skill empieza por el radar.
- `04-vuelta-diaria.md`: elegir y lanzar lo hace la tarea «lanzar-ofertas» (L5 firmada), no «cuando el dueño firme una regla».
- Informe: `docs/_historial/revision-coherencia-2026-11-13.md`.

## 0.2.0 · 2026-11-13 · Radar de ofertas (super buscador)

Pedido del dueño: «quiero armar un SUPER BUSCADOR DE OFERTAS», en todos los mercados, en sus idiomas y en inglés, siempre prendido.

- `scripts/radar.py`, `scripts/radar_terminos.json` (27 idiomas, 160 frases de entrega y pago, 58 plataformas y constructores) y `scripts/radar_lector.js`. Datos en `empresa/barrido/radar/`.
- Cola de 711 búsquedas en 57 mercados (los de `elegir_mercado.py`), con el país puesto para que salgan los operadores locales; prioriza lo que rinde y rota.
- Tarea programada «radar-ofertas» cada 2 horas, las 24 horas (`references/05-radar.md`).
- Probado en real el 13-nov: «hotmart.com» en Argentina → 16 ofertas nuevas; medir por el código del producto funciona; el número de `pagina_url` no sirve para medir.
- Arreglos al lector de tarjetas: la fecha se busca en toda la tarjeta (antes quedaban en 0 días) y se descartan destinos que no son una oferta (redes, mensajería).
- Puntaje de joya: hueco de mercado y «escalando» suben hasta un 10 % cada uno en `ordenar_candidatos.py`, sin tocar los pesos del dueño.
- Ruta C (API oficial de la UE y el Reino Unido): `radar.py api` usa el cliente que ya existía; falta el token del dueño.
- Aprendido en la vuelta del 13-nov (tarde): en inlead.digital el slug de la URL (`chao-papada`, `k-food-para-principiantes`) no se encuentra como frase (0 resultados) o trae anuncios ajenos (`chao-papada` → 11 anunciantes, sobre todo clínicas); varios códigos de Hotmart (`J105181807N`, `X89100891M`, `D105211812J`) también dan 0. Esas quedan en a_medir hasta medirlas por la página del anunciante con el id de la Biblioteca (el de `pagina_url` da 0, confirmado otra vez).
- Aprendido en la vuelta del radar del 13-nov (noche, 15 búsquedas): (1) el lector corta la URL en «?», así que todos los hoplinks de ClickBank sin subdominio quedan como `hop.clickbank.net/` y se funden en una sola oferta falsa (8 páginas distintas en CA); conviene conservar el parámetro de producto o usar la página como clave en ese caso. (2) La mejor joya, `H98995146C` (Referente, 28 anuncios vistos en BR, 183 d), y el slug `instituto-cimas-cursos-livres` dan 0 como frase; el conector con el número de `pagina_url` también da 0, y en la Biblioteca el clic en el nombre de la página no abre `view_all_page_id` (el enlace va a la página de Facebook): falta un camino para sacar el id de la Biblioteca. (3) Las joyas siguientes eran evergreen de carrd.co con 1-5 anuncios (sorteos, «crédito gratis»): se midieron y quedaron descartadas; el umbral evergreen (1 anuncio ≥ 30 d) llena a_medir de ese tipo en constructores gratuitos.
- Aprendido en la vuelta del radar del 13-nov (19-20 h): **camino para el id de la Biblioteca resuelto.** Abrir `https://web.facebook.com/ads/library/?id=<ficha>` (la `ficha` está en `hallazgos.jsonl`) redirige sola a `...&view_all_page_id=<id>`; con ese id y `country=ALL` se cuenta cuántos anuncios de la página van al destino de la oferta y se mide con `radar.py medir <clave> --total N --dias D --page-id <id>`. Así se midieron `H98995146C` (47 anuncios, 195 d), `instituto-cimas-cursos-livres` (18, 109 d) y `D103364771K` de El Taller de Maku (142, 67 d), que daban 0 por código o slug. Conviene que `radar.py pendientes` traiga la ficha y que la medición por página sea el camino por defecto en plataformas compartidas. Otro detalle: en la Biblioteca el texto de búsqueda vacía es «No hay ningún anuncio que coincida con los criterios de búsqueda».
## 0.1.0 · 2026-11-13

Pedido del dueño: dividir las skills por proceso y que haya una regla o automatización para cada situación.

- Nace separando la fase 1 de `modelar-y-lanzar-oferta` (0.8.1): §1.1-§1.3 → `references/01-elegir-del-banco.md`, §1.5 → `02-barrido-por-forma.md`, §1.6 → `03-banco-seguimiento-e-iteraciones.md`. El texto se movió sin cambios.
- Nuevo: `references/04-vuelta-diaria.md` y la tarea programada «buscar-ofertas» (08:15 de Argentina, todos los días): medir el banco, reponer si no alcanza, sacar iteraciones de lo que escala, informe diario en `empresa/barrido/banco/diario/`.
- Los scripts siguen en `modelar-y-lanzar-oferta/scripts/` (caja de herramientas compartida).

## Registro de promoción

| Versión | Estado | Fecha | Corrida manual | Retro | DoD firmado por el dueño | Notas |
|---|---|---|---|---|---|---|
| 0.2.0 | pulida (en uso) | 2026-11-13 | radar: una búsqueda real (hotmart.com · AR) | — | — | radar siempre prendido |
| 0.1.0 | pulida (en uso) | 2026-11-13 | fase 1 de cuatro lanzamientos (11 al 13-nov) | — | — | separada de modelar-y-lanzar-oferta; vuelta diaria sin corrida |

## 2026-11-14 (radar, vuelta de la tarde)
- Medir por página sin el número de `pagina_url`: buscar el nombre del anunciante (`search_type=keyword_unordered`) y leer en el HTML el par `"page_id":"…"` / `"page_name":"…"`; con ese identificador sirve `view_all_page_id`. Hizo falta en 22 de 30 ofertas de `hotm.art` / `go.hotmart.com`, cuyo código no aparece en el texto del anuncio.
- Un anunciante con nombre genérico («Poemas», «Eu Amo», «BM 31») no se ubica así: queda con lo visto en la búsqueda.
- `browser_batch` admite 25 acciones como máximo; la rueda real del ratón necesita una captura previa en cada página nueva.
- Una misma oferta en varios idiomas (Referente P, pack Murphy para niños) entra al radar como una oferta por tienda: se anotó en la nota de cada una que es la misma.

- Aprendido en la vuelta del radar del 14-nov (noche): (1) medir por página en una sola tanda: abrir `ads/library/?id=<ficha>`, leer `view_all_page_id` de la URL (a veces tarda 1-2 s: esperar antes de leer), ir a `search_type=page&view_all_page_id=<id>&country=ALL` y contar las tarjetas cuyo enlace contiene el código o la ruta; el total de la página es el techo (si es < 15, la oferta queda bajo el piso sin más). Con páginas de 150+ anuncios, 3 scrolls cargan 20-25 tarjetas y el conteo es un mínimo. (2) Para guardar lo que devuelve `radar_lector.js` sin copiarlo a mano: `window.name = JSON.stringify(resultado)` y navegar a una página servida en 127.0.0.1 que lo reenvía por POST al mismo servidor (el `fetch` directo desde la Biblioteca lo corta la CSP). (3) La Biblioteca a veces redirige a `www.facebook.com`: sessionStorage es por origen y el lector guardado no está; volver a pegarlo. (4) En el navegador integrado `eval`/`new Function` van antes de cualquier `await`. (5) Convendría que `radar.py pendientes` traiga la `ficha` (hoy se saca de `hallazgos.jsonl`) y que inlead.digital no entre a `a_medir` por evergreen de 1 anuncio: 12 de 30 eran consultorios y captación de clientes.

- Aprendido en la vuelta del radar del 15-nov (noche): (1) `radar.py verificar --funnel` tiene que llevar un **núcleo** de la taxonomía (`tsl`, `quiz`, `vsl`…); «niveles» y «bump» son extras. Con `--funnel niveles` el import al banco pasa pero `banco_candidatos.py estado` se cae (`ErrorTaxonomia`); se corrigió a mano (`funnel: tsl`, `extras: [niveles, bump]`) en las dos de APS. Convendría que `verificar` acepte `--extras` y valide contra `taxonomia_funnels`. (2) Los acortadores (`referente785.com`, `bit.ly`, `rb.gy`) se funden en una sola oferta falsa, como los hoplinks de ClickBank: `referente785-com` quedó en a_medir con 7 anuncios de páginas distintas. (3) Medir por `?id=<ficha>` no siempre redirige con `view_all_page_id` (FrenchNounGender): el `page_id` leído del HTML resultó ser otro anunciante (Mercado Libre); sin redirección, quedarse con lo visto. (4) De 30 medidas, 28 quedaron bajo el piso: las joyas de 1 anuncio evergreen en gumroad/hotmart casi nunca llegan a 15.

- Aprendido en la vuelta del radar del 16-nov (madrugada, 30 medidas, 5 verificadas, 5 búsquedas): (1) medir por página en un solo lote de `browser_batch` por oferta (hasta 3 por lote): `?id=<ficha>` → 3 s → JS que lee `view_all_page_id` y navega a `search_type=page&country=ALL` → un scroll → JS que agrupa las tarjetas por destino (anuncios y días por destino). Sirve igual para lpages, Hotmart y Kiwify y muestra de paso las hermanas del anunciante. Las 30 fichas redirigieron bien. (2) Una página sin anuncios activos responde «No hay ningún anuncio…»: se mide con total 0. (3) Los slugs genéricos de lpages (`intervention`) no sirven como frase: medir siempre por página. (4) El receptor local en 127.0.0.1 (window.name → página que hace POST) funcionó desde el navegador integrado para guardar lo que devuelve `radar_lector.js`. (5) De los 5 que pasaron el piso, 4 eran servicios o marca personal (gimnasio, clínica, coaching por Typeform, curso en video de influencer): el piso de anuncios en lpages.co trae sobre todo negocios locales. (6) `banco_candidatos.py importar` descartó la única producible (intervención lectora de Kristine Nannini) porque «ya la tenía otra instalación» (registro de territorio).

- Aprendido en la vuelta del radar del 16-nov (mañana, 30 medidas, 1 verificada, 5 búsquedas): (1) la Biblioteca redirige siempre a `www.facebook.com`; guardar el medidor y el lector una sola vez en `sessionStorage` de ese origen (`sessionStorage.m`, `.go`, `.l`) y llamarlos con `eval(sessionStorage.x)` acorta cada lote a 7 acciones por oferta (3 ofertas por `browser_batch`). (2) De 30 joyas «evergreen» de netlify, myclickfunnels, kajabi y Kiwify, 29 quedaron bajo el piso (consultorios, comercios, apps): el umbral de 1 anuncio ≥ 30 d sigue llenando a_medir de negocios locales. (3) Mi Cuentito (libro infantil en PDF personalizado por pedido, quiz → checkout de Impultienda, página con 410 anuncios) se marcó no producible: el entregable se arma por pedido con los datos del quiz. Si el dueño quiere esa línea, hace falta un armado por pedido.
- Aprendido en la vuelta del radar del 16-nov (mediodía, 30 medidas, 2 verificadas, 5 búsquedas): (1) al medir por página, un scroll carga ~25 tarjetas: en páginas con total > 30 hacer 4-5 scrolls antes de contar, porque el primer conteo de Santafé Agroinstituto dio 10 y 3 anuncios para dos ofertas que con 72 tarjetas leídas eran 18 y 20 (pasaban el piso). (2) Ambas resultaron ebooks técnicos B2B vendidos por la autoridad de un experto con nombre (Dr. Mike Hutjens): no producibles. (3) Las frases `payt.com.br`, `perfectpay.com.br` (ALL) y `buygoods.com` (US) dan «No hay ningún anuncio»: esos dominios no aparecen en el texto de los anuncios; convendría bajar su prioridad o buscarlos por otra vía. (4) `perspective.co` trae sobre todo al propio SaaS (signup, workshop): la nueva mejor joya `perspective-co-start-signup` (26 anuncios, 629 d) es un registro de software, no una oferta producible; se descartará al verificar. (5) Las 28 joyas de 1 anuncio evergreen medidas en payhip/hotmart/kiwify quedaron todas bajo el piso (0-2 anuncios por página).

- Aprendido en la vuelta del radar del 16-nov (tarde, 30 medidas, 1 verificada, 5 búsquedas): (1) el receptor en 127.0.0.1 dejó de servir: el navegador vacía `window.name` al pasar de facebook.com a 127.0.0.1 (el POST llegó con 0 bytes). Se volvió a devolver el JSON de `radar_lector.js` como resultado de `javascript_tool` y guardarlo desde Bash; con lecturas chicas alcanza. (2) En la vista por página, `window.scrollTo` solo no carga más tarjetas: hace falta antes una rueda real del ratón (Perspective.co pasó de 30 a 134 tarjetas). Y la rueda pide una captura previa en cada página nueva (`screenshot` a escala 0,2 basta). (3) Las 30 joyas de esta tanda (Perspective, systeme.io, gumroad, payhip, hotmart de 1-4 anuncios evergreen) quedaron todas bajo el piso o eran el propio SaaS (registro de Perspective, 31 anuncios, no producible). (4) `clickbank.net` (US) y `quizell.com` (ALL) dan «No hay ningún anuncio»: el dominio no aparece en el texto de los anuncios; `podia.com` trae solo al propio Podia.

- Aprendido en la vuelta del radar del 16-nov (noche, 30 medidas, 1 verificada, 5 búsquedas): (1) la medición por `fetch` de 0.6.4 (`?id=<ficha>` → `page_id` del `collated_results` con `ad_archive_id == ficha` → `view_all_page_id` con `country=ALL`) volvió a medir 30 en ~2 min sin captcha; correr el bucle en segundo plano y abrir otra pestaña para verificar mientras tanto. (2) Las 29 joyas de payhip de 1 anuncio evergreen quedaron todas bajo el piso (0-2 por página): payhip, como gumroad y hotmart, llena a_medir de vendedores chicos. (3) La única que pasó (`samcart-com-mystore2457-e-book`, 15 anuncios, 99 d) era un ebook de contratos federales de EE. UU. vendido por la autoridad de una ex oficial con nombre: no producible. (4) `eval(sessionStorage.l)` funcionó en una página de la Biblioteca y en la siguiente la CSP lo cortó: pegar el lector entero en cada búsqueda. (5) En `hop.clickbank.net` se conservó el parámetro `vendor` en el destino (`hop.clickbank.net/vendor/<v>`) para que los hoplinks no se fundan en una sola oferta; convendría pasarlo a `radar_lector.js`. (6) `scoreapp.com` trae sobre todo al propio SaaS (lead magnets y waitlist de ScoreApp): la nueva mejor joya `scoreapp-com-pages-1mil-lead-gen-sys` (50 anuncios, 427 d) es probablemente un imán de leads del software, no una oferta producible. `stan.store` (ALL) rindió 107 ofertas nuevas, casi todas creadores con marca personal.

- Aprendido en la vuelta del radar del 17-nov (madrugada, 30 medidas, 2 verificadas, 5 búsquedas): (1) **el medidor por `fetch` sobrecontaba**: en `collated_results` cada colación aparece con un anuncio con `collation_count: N` y los demás miembros con `collation_count: null`; sumar `collation_count || 1` por entrada cuenta dos veces. Lo correcto es contar entradas (cada una es un anuncio; coincide con `count` de la página). La guía de namesets de We Fix Kits había dado 19 y eran 13 (bajo el piso). Las descartadas de vueltas anteriores siguen descartadas (el error solo inflaba). (2) `radar.py medir` sobre una oferta ya en `a_verificar` no la baja aunque el nuevo total quede bajo el piso (`_avanzar` solo mira `medida`): se cerró con `verificar --producible no` y la nota; convendría que `medir` re-evalúe el piso. (3) Algunas páginas devolvieron `count` vacío en la primera tanda y bien al reintentar: si da 0 tarjetas con la ficha activa, repetir. (4) `teachable.com` (ALL) da «No hay ningún anuncio»; `kajabi.com` (US) trae solo al propio Kajabi; `stan.store` sigue rindiendo creadores chicos (28 de 28 bajo el piso). (5) Mejor joya nueva: `systeme-io-eliasvi756-d7dafeb3` (Bee's for Shop, 16 anuncios vistos, 111 d), para medir en la próxima vuelta.

- Aprendido en la vuelta del radar del 17-nov (mediodía, 32 medidas, 2 verificadas, 5 búsquedas): (1) para guardar lo que devuelve `radar_lector.js` sirve un receptor en 127.0.0.1 que recibe el JSON **por GET en la query** (`location.href='http://127.0.0.1:<puerto>/?f=<nombre>&d='+encodeURIComponent(JSON.stringify(r))`): llegaron lecturas de hasta 27 KB sin perder nada (el `window.name` se vaciaba; la query no). Cargar el lector como `<script src="http://127.0.0.1…">` no anda (contenido mixto) y `eval(sessionStorage.l)` lo cortó la CSP: pegar el lector entero. (2) Las 30 joyas medidas (tryinteract, Kiwify, Gumroad, hoplinks de ClickBank, Hotmart, inlead, Stan) quedaron todas bajo el piso (1-9 anuncios por página). (3) `vercel.app` (ALL) trajo las dos joyas de la vuelta y ninguna era digital: Nevroslim (jarabe físico en Uzbekistán, 47 anuncios) y BLACKWOLVES (canal gratis de Telegram con señales de opciones binarias en árabe, 33). `typeform.com` (ALL) trae sobre todo consultorios, reclutamiento y encuestas; `podia.com` (US) solo al propio Podia (0 nuevas).
