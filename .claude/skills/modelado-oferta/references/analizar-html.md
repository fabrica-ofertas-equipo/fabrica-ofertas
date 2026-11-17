# `scripts/analizar_html.py`: uso, qué detecta bien y qué no

> v0.1 sin pulir. Implementa el método de la decisión J20 («analizar todo el HTML del referente y reproducir ese esqueleto con código propio; el contenido es nuestro»). Probado contra los dos HTML reales descargados en el piloto (`docs/_historial/modelado-piloto/referentes/html/axon-mapaspagnolo.html` e `inglesvisual.html`) y contra el análisis hecho a mano de `referentes/analisis-html-axon.md`. Biblioteca estándar, sin red por defecto.

## 1. Uso
```
.venv/bin/python -I .claude/skills/modelado-oferta/scripts/analizar_html.py ARCHIVO.html --no-red --salida ofertas/<id>/modelado/
```
Escribe `esqueleto_html.json` (estructura) y `mapa_ranuras.json` (contenido). Sin `--salida` solo imprime un resumen; no pisa archivos sin `--sobrescribir`. `-I` (modo aislado de Python) es obligatorio al leer HTML descargado. Opciones: `--max-bytes` (defecto 2 MB, tope 10 MB; superarlo es error, no recorte) · `--timeout` · `--host-propio` (separa scripts de terceros al analizar un archivo) · `--sin-muestras` (el mapa no lleva ni el recorte de 60 caracteres) · `--css-externo` (hasta 5 hojas externas; necesita red) · `--freno` · `--no-red`.

Salidas: 0 ok · 2 uso o entrada inválida · 3 red no permitida o bloqueada · 4 tamaño excedido · 5 respuesta no válida.

**Modo URL.** Hoy se trabaja con HTML que **guarda el dueño** (J15). La URL solo se abre si el dueño lo autoriza y no existe `empresa/captura/freno.json`: el script rechaza esquemas no web, credenciales, puertos distintos de 80/443/8080/8443, direcciones privadas, locales o reservadas (también tras cada redirección, máximo 5), respeta `robots.txt`, no usa proxy ni cookies, pide `Accept-Encoding: identity` (no descomprime) y no reintenta ante un 403/429.

## 2. Qué produce
**`esqueleto_html.json`:** `fuente` (tipo, nombre del archivo o URL sin query, `sha256`, bytes, codificación) · `documento` (lang, longitud del título y de la meta descripción, `og`, plataformas detectadas) · `resumen` (orden de tipos, cadencia de fondos, CTA por destino) · `secciones[]` (orden, tag, clases, **tipo inferido con `confianza` y `senales`**, fondo, titulares, nº de palabras, imágenes, CTA, componentes, esquema del DOM con hermanos colapsados «×N») · `ctas[]` (texto y destino: ancla, checkout externo o interno, sin destino…) · `enlaces_checkout[]` (plataforma, host, ruta con `{id}`, **nombres** de parámetros) · `selectores_y_acordeones` (pestañas con paneles encontrados, `<details>`, `aria-expanded`) · `elementos_fijos[]` (sticky/fixed por CSS, `style` o clase utilitaria, con tipo inferido) · `iconos` · `imagenes` (conteo, tamaños **declarados**, formatos, hosts, carga diferida, alt repetidos) · `tokens_diseno` (colores normalizados a hex con frecuencia y uso, variables CSS propias, fuentes declaradas y cargadas, tamaños, pesos, radios, sombras, ancho de contenedor, relleno de sección, breakpoints, animaciones) · `scripts_y_terceros` (scripts externos con host y categoría, píxeles y rastreadores **sin su id**, iframes, firmas de comportamiento JavaScript) · `alertas[]` (señales mecánicas para el desarme) · `limites_conocidos`.

**`mapa_ranuras.json`:** una ranura por texto, imagen o dato que es **contenido** (rol, tipo, `funcion`, longitud en caracteres y palabras, hash, muestra de ≤ 60 caracteres, tamaño declarado, selector corto, `destino_sugerido` en `copy.S0x` de D5, `expresion_protegida: true`) y un `resumen` por rol y por bloque. Las imágenes repetidas de un carril infinito se emiten una vez.

**Alertas** (`A-…`): `FECHA-VACIA`, `FECHA-DE-HOY-EN-EL-DOM`, `CUENTA-ATRAS`, `PRECIO-TACHADO`, `CIFRA-DE-PRUEBA-SOCIAL`, `RESENAS-SOLO-IMAGEN`, `AVISO-DE-ACTIVIDAD`, `VENTANA-DE-SALIDA`, `ALEATORIEDAD-EN-JS`, `ENLACES-LEGALES-SIN-DESTINO`, `ALT-REPETIDO`, `PIXEL-DEL-REFERENTE`, `TEXTO-OCULTO`, `TEXTO-CON-FORMA-DE-INSTRUCCION`. Son **señales para `practicas_vetadas[]`**: decidir si la práctica es esencial o adorno no es del script.

## 3. Comparación con el análisis hecho a mano (referente principal, 14 bloques)
| Aspecto | A mano (`analisis-html-axon.md`) | Script | ¿Coincide? |
|---|---|---|---|
| Árbol de bloques y orden | barra de oferta + 11 `section` + pie + aviso flotante | 14 bloques en el mismo orden, con tipo: barra · héroe · tira de miniaturas · reseñas · niveles con selector · para quién · bonus · precio · garantía · entrega · FAQ · CTA final · pie · flotante | **Sí** (los 14 tipos coinciden) |
| Cadencia de fondos | crema · oscuro · crema · crema · crema · oscuro · crema · crema · crema · crema · oscuro · pie oscuro | idéntica (también lee `style="background:var(--cream-2)"` y hereda el del `body`) | **Sí** |
| CTA | 8 `.btn-cta`: 6 a `#offerta`, 2 al checkout de Hotmart | 8: 6 ancla interna y 2 `checkout_externo` (Hotmart, ruta `/{id}`, parámetros `off` y `checkoutMode`, **sin los valores**) | **Sí** |
| Imágenes | 51; héroe 875², tira «27 (13 + copia)», 10 capturas de reseña, 5 portadas, 1 de precio, 5 avatares de 40 px | 51; 875×875 ×7 (héroe + 5 bonus + precio); 945×1680 ×11 (10 reseñas + miniatura del aviso); 5 sin tamaño (avatares) | **Sí**; en la tira cuenta **28 = 14 distintas + 14 de copia** (la tira tiene 14 `PREVIA-n`; el análisis manual contó 27 y 13) |
| Selector de niveles | 6 pestañas con panel | 6 pestañas con `data-tab`, 6 paneles encontrados, rótulos de 20-29 caracteres | **Sí** |
| FAQ | 8 filas con «+» que gira (JS) | 8 elementos `aria-expanded`, 0 `<details>`: mecanismo JavaScript propio | **Sí** |
| Elementos fijos | barra pegajosa y aviso de compra | `div.urgency-bar` sticky top; `div#floaty` fixed bottom-left, tipo `aviso_de_actividad` (su ocultación inicial es por CSS y no se calcula) | **Sí** |
| Colores | `--cream #FEFDFA`, `--ink #12141C`, `--yellow #FFDC00`, `--yellow-dark #E0C200`, acentos, `--grey #6B6B6B` | las 19 variables propias con su valor; las 79 variables de plataforma (`--wp-…`, Elementor) se cuentan aparte y los colores de reglas sin elemento en el DOM no entran al ranking | **Sí** |
| Tipografía | `Poppins` declarada, **sin `@font-face` ni Google Fonts**; `Manrope` del tema no usada | `fuentes_declaradas: Poppins`; `fuentes_declaradas_sin_cargar: [Poppins]`; `@font-face` de la plataforma separado | **Sí** |
| Medidas | `.wrap` 1100 px, sección 64 px, radios 18/12-16/24/28/999, sombra `0 10px 30px .10`, botón 3D `0 6px 0 #E0C200…`, un breakpoint de 760 px | 1100px, `64px 0`, radios 18·14·12·24·28·999, las mismas sombras, `min-width:760px` | **Sí** |
| Terceros | `rastreio.js` en un Worker con `data-pixel`, jQuery, Elementor, `cdn-reach.hostinger.com`, `speculationrules` | Worker marcado como tercero desconocido + píxel por `data-pixel` (solo longitud 16), Hostinger Reach, jQuery como propio/biblioteca; `speculationrules` se ignora (es JSON) | **Sí**, sin el id del píxel |
| JavaScript | fecha de hoy en la barra, pestañas, FAQ, carril automático, aviso con nombres de una lista, píxel | firmas: fecha de hoy escrita en el DOM, carril por `requestAnimationFrame`, observador de visibilidad, temporizador, almacenamiento local, cookies, peticiones | **Parcial**: detecta *qué hace*, no *para qué* (no nombra `activateTab` ni `toggleFaq`) |
| Reseñas | capturas de chat sin texto | `A-RESENAS-SOLO-IMAGEN` (≥ 3 imágenes y < 60 palabras en el bloque) | **Sí** |
| Pie sin datos legales, enlaces a `#` | sí | `A-ENLACES-LEGALES-SIN-DESTINO` (3) | **Sí** |
| Meta, `lang` | `pt-BR` en una página italiana, `description` sí, `og:*` no | `lang: pt-BR`, `description` de 158 caracteres, `og_presente: false` | **Parcial**: el script da el atributo, no detecta que el texto está en otro idioma |
| Checkout, reglas legales | externo; sin empresa ni dirección | `enlaces_checkout` Hotmart; sin detección de identidad del vendedor (no es estructura) | n/a |

**Inglés Visual (secundario):** 17 bloques (barra, héroe, problema, pasos, comparación `baja`, dos bloques sin tipo, precio, bonus, reseñas, autora `baja`, FAQ, cierre, pie, 3 flotantes); 8 `<details>`; 5 CTA a `/checkout` y anclas; paleta petróleo `#123C3E` / coral `#FF6B5C` (las 17 variables); `Fraunces` + `Inter` (Google Fonts, sin falta de carga); contenedor 1080 px; sección 56 px; alertas de cuenta atrás, ventana de salida (modal `fixed inset-0` con `exit_intent`), `Math.random` (contador «personas viendo»), fecha de hoy y precio tachado. No lo detecta: `history.scrollRestoration` (no hay firma), el relleno 76 px de escritorio (vive dentro de `@media` y el resumen solo lista el base), y dos bloques de contenido sin clases ni titulares reconocibles quedan `texto_generico`.

## 4. Qué detecta bien
Orden de bloques y tipo en landings con clases o titulares reconocibles; CTA y su destino; checkout externo e interno; pestañas, `<details>`, `aria-expanded`; elementos fijos (CSS, `style` y clases utilitarias tipo Tailwind); tokens medidos; conteo y tamaños declarados de imágenes con carga diferida de plugin (`data-src`); terceros y píxeles sin guardar ids; firmas de JavaScript; contenido hostil (se ignora, se señala y no se reproduce). Robusto ante HTML roto, anidado, vacío o enorme (límites de nodos, profundidad, tiempo y bytes).

## 5. Qué no detecta, o solo de forma aproximada
- **El tipo de bloque es inferencia por reglas** (clases, ids, titulares en es/en/it/pl/pt/fr/de y estructura) con `confianza`. Páginas sin clases ni titulares reconocibles dan `texto_generico`. El Maker confirma cada bloque.
- **No renderiza**: sin medidas reales, sin versión móvil, sin capturas, sin lo que los scripts insertan después de cargar, sin estados `:hover`/`:target`. Los colores se cuentan por reglas **con elemento en el DOM**, no por lo que el navegador pinta.
- **CSS**: reglas con combinadores se comparan por su último selector compuesto (aproximado); `@media`, `@supports` y `@layer` se leen pero solo cuentan para breakpoints; las hojas externas solo con `--css-externo` (el campo `hojas_externas_no_leidas` avisa).
- **JavaScript**: solo firmas; no se interpreta, no se sigue ningún enlace ni se bajan imágenes o scripts. No sabe *para qué* se usa un temporizador.
- **Semántica del texto**: no entiende promesas, tono ni idioma. La detección de cifras de prueba social, fechas vacías y texto «con forma de instrucción» es por patrones (puede dar falsos positivos y negativos).
- **Descarga (modo URL)**: la dirección se valida y luego `urllib` resuelve de nuevo (no fija la IP validada, como sí hace `scripts/modelado/enlaces.py`); `robots.txt` se comprueba para el host inicial, no para el destino de una redirección. Por eso hoy no se usa: el dueño guarda el HTML.
- El análisis manual y el script pueden diferir en pequeños conteos (la tira de miniaturas: 27 a mano, 28 por script). Ante una diferencia, vale lo que se pueda comprobar en el HTML guardado.

## 6. Pruebas
`.venv/bin/python -m unittest discover -s tests/modelado -t . -p "test_*.py"` (72 pruebas, sin red): secciones y orden, CTA y destinos, `<details>` y pestañas, elementos fijos, tokens, terceros y píxeles sin ids, mapa de ranuras, contenido hostil (no se reproduce), límites de bytes/nodos/profundidad/tiempo, frenos de red (esquema, puertos, privadas, `robots.txt`, 403/429, compresión, `--no-red`, freno de captura), CLI y comparación con los HTML reales (se omite si no están).
