# Cómo se construye cada formato de producto

> El formato lo fija `oferta.vehiculo.formato` (D3); D4 elige solo el archivo de cada ítem. D4 **no decide** qué se vende ni cuánto: construye lo que la ficha EU (alcance cerrado) y la matriz de promesas piden.
> Etiquetas: [PENDIENTE] = falta algo por construir o instalar (ver `dependencias.md`) · [SUPUESTO] · [HIPÓTESIS] · [VERIFICAR].

## 0. Método común a todos los formatos (en este orden)

1. **Esqueleto por minutos, no por páginas.** Antes de redactar, el Maker escribe `04-producto/entregables/fuente/esqueleto.json`: una fila por sección/hoja/unidad con `{id, titulo, promesa_id, resultado_comprobable, minutos_lectura, minutos_paso_humano, palabras_max}`. `palabras_max = minutos_lectura × lectura_wpm × factor del locale` (`parametros.yaml#producto.lectura_wpm`). Una sección sin `promesa_id` no se escribe. Σ minutos de lectura + Σ pasos ≤ `promesa.tiempo_prometido_min` (fórmula de `tiempo-y-novato.md`); si no entra, vuelve a D3 (no se recorta en silencio).
2. **Profundidad = alcance cerrado de la ficha EU.** El volumen (páginas, recetas, «N patrones») no es mérito: manda la ficha `candidato.entregable.alcance` y lo que la landing promete. Páginas reales dentro de `producto.paginas_vs_prometido_pct` de lo prometido (si se promete un número de páginas). Se prefiere profundidad útil (ejemplo resuelto, caso borde, «cuándo parar») a más volumen.
3. **La fuente de verdad es texto estructurado** (`entregables/fuente/`: HTML+CSS, Markdown, JSONL de unidades, hoja base) y los entregables se **generan** de ella. Nada se maqueta a mano sobre el binario final. La fuente va con `en_paquete: false`.
4. **Hechos solo desde `respaldo/`** (`respaldo-y-fuentes.md`); ejemplos del método con personas **ficticias rotuladas** («ejemplo ficticio»); nunca cifras de resultado.
5. **Ejecutar el método** (paso 4 del SOP): cada paso se corre **sobre archivos locales** con un caso ficticio (sin sandbox, sin red, sin cuentas); lo que requiere web, cuenta, pago o interfaz gráfica se marca `no_ejecutable_por_agente`.
6. **Maquetar, empaquetar y hashear** (`empaquetar.py`, `render` A/B/C de §10): nombres neutros `slug-vN[-tipo].ext`, `sha256` por ítem en `producto.json`.
7. **Mapa `vehiculo.formato` → `items[].tipo`** (el esquema `producto.schema.json` 1.0.0 no tiene aún tipos `patron`, `biblioteca`, `imagen`, `calculadora`: PEDIDO a CT-1):

| `vehiculo.formato` | Qué es | `items[].tipo` (esquema vigente) | Archivo(s) de entrega | Ruta de construcción |
|---|---|---|---|---|
| `guia_pdf` | ebook, guía, manual corto | `guia_pdf` (o `guia_md`) | PDF (y `.md` si se promete editable) | §1 |
| `plantilla` | plantilla editable, planificador | `plantilla_docx` · `plantilla_md` · `plantilla_xlsx` | DOCX/MD/XLSX (+ PDF imprimible en blanco) | §2, §3 |
| `hoja_de_calculo` | calculadora, presupuesto, costeo | `plantilla_xlsx` | XLSX (maestro) | §4 |
| `biblioteca` | recetario, fichas, patrones, tarjetas, prompts | `guia_pdf` (+ `otro` para el JSONL de unidades si se entrega) | PDF de la biblioteca | §5, §6 |
| `checklist` | lista de verificación | `checklist` | PDF/MD de 1-2 páginas | §7 |
| `minicurso_video_corto` | video corto | `video` | MP4 [PENDIENTE: herramienta; fuera de v0.1] | §8 |
| `pack` | varios ítems (guía + plantilla + bonus + bump) | uno por archivo | cada ítem es un archivo con su hash | §9 |

## 1. Ebook o guía (`guia_pdf`)

- **Esqueleto.** Portada (título, subtítulo = `promesa.subtitulo`, tiempo previsto = `prometido_min`, versión y próxima revisión) → interior de portada (aviso de alcance literal del glosario; bloque «Si necesitas ayuda ahora» si aplica; divulgación de IA) → «cómo usar esto en N minutos» → capítulos = **pasos del método** (cada uno con minutos, resultado comprobable, ejemplo ficticio y «cuándo parar» si el tema es de salud, relaciones o dinero) → anexos de consulta (`data-lectura="referencia"`) → fuentes (título, organismo, URL, fecha de consulta) → colofón (autoría honesta, licencia de uso, tipografías OFL).
- **Profundidad.** Un capítulo = una decisión o un resultado, no un tema. Cada paso termina en algo que el comprador **tiene** (tabla rellena, guion, lista). Prohibido el relleno: sin «introducción general», sin repetir el aviso en cada página (ruido), sin teoría que no se use en un paso.
- **Maquetación.** `templates/pdf_base.html` + `pdf_base.css` (A4, `lang` = locale, `<title>` real, pie con número de página, tablas que no parten, `.paso`, `.ayuda`, `.cuando-parar`). Se prueba **en el móvil** (390 px de ancho en PDF/HTML) antes de aprobar.
- **Empaquetado.** HTML→PDF por la ruta A/B/C (§10) → `empaquetar.py --actualizar` (sha256, peso). Metadatos: sin autor por defecto, sin rutas, sin EXIF en imágenes; texto seleccionable; fuentes embebidas.
- **Pruebas.** `tiempo_total.py`, `lint_contenido.py`, `verificar_respaldo.py`, `similitud_ngrama.py`; cold run (`tiempo-y-novato.md`).

## 2. Plantilla editable (`plantilla_docx|md|xlsx`)

- **Esqueleto.** Versión en blanco + **ejemplo resuelto ficticio** (rotulado) + instrucciones de uso de una página («rellena en este orden») + zona de datos del comprador claramente marcada. Los campos que el comprador rellena (`[Nombre y apellidos]`) son legítimos; los placeholders del Maker (`[INSERTAR TEMA]`) son defecto.
- **Formato editable.** XLSX o MD sin dependencias; DOCX **[PENDIENTE]**: no hay biblioteca ni conversor instalados (ni `python-docx` ni LibreOffice); alternativas: **A** entregar MD + PDF imprimible; **B** XLSX; **C** DOCX generado a mano por una persona (paso GUI humano). Hasta que exista, la plantilla DOCX es paso humano.
- **Profundidad.** La plantilla vale por lo que ahorra decidir: campos mínimos, orden lógico, ejemplo real. Cada campo extra se justifica con una promesa.

## 3. Planificador (semanal, mensual, hábitos, comidas, tareas)

- **Esqueleto.** Periodo (semana/mes), casillas, una página de instrucciones, una página de ejemplo ficticio. Versión imprimible (PDF con casillas) + versión editable (XLSX) si se promete.
- **Reglas de contenido seguro.** Registro y organización, **sin metas** (ni peso, ni ingresos, ni deuda objetivo): un planificador con objetivo es amarillo-b o rojo. Planner de comidas: sin kcal objetivo ni dieta prescrita; cualquier cifra nutricional con fuente T1 del país.
- **Empaquetado.** PDF imprimible vía §10 + XLSX con `lint_hoja.py`.

## 4. Calculadora u hoja de cálculo (`hoja_de_calculo`)

- **Pestañas** (nombres en el idioma del locale): `Instrucciones` · `Supuestos` (visibles, con rótulo «ilustrativo», moneda y fecha) · `Entradas` · `Cálculo` · `Resultado` · `Ejemplo` (caso ficticio resuelto).
- **Prohibido (L1-17, BLOQUEANTE):** macros, hojas ocultas, filas/columnas ocultas, enlaces externos o conexiones, funciones `WEBSERVICE/IMPORT*/INDIRECT`, y **fórmulas que puntúan un estado del comprador** («riesgo alto», «obeso», «deuda crítica»). Una calculadora devuelve **números con supuestos visibles**, nunca un diagnóstico ni un IMC interpretado ni «tu nivel de deuda».
- **Casos dorados + segundo cálculo independiente (L1-S18).** El Maker escribe `fuente/pruebas/referencia_calculo.py` (implementación de referencia, sin la hoja) y `casos_dorados` en `autoprueba.json`: el caso típico, un borde inferior, un borde superior y uno inválido [HIPÓTESIS]. La hoja y la referencia deben coincidir al céntimo; redondeo explícito en `Supuestos` (Excel redondea medio hacia arriba; la referencia debe usar la misma regla). Recalcular la hoja **no puede hacerlo un agente hoy**: [PENDIENTE: `scripts/producto/calc_hoja` (recálculo con LibreOffice sin pantalla)]; mientras tanto, una persona carga cada caso dorado en la hoja (checklist).
- **Configuración regional.** Fórmulas guardadas en inglés; separadores y moneda visibles según el locale; abrir con la configuración regional del locale es **paso humano** (GUI). Moneda y formato de número en `Supuestos` coinciden con `oferta.moneda`.
- **Google Sheets.** El **maestro es el `.xlsx` con hash**. Un enlace «hacer una copia» de una hoja en vivo es una dependencia externa que el dueño podría cambiar o borrar (y D4 no entrega nada que exija mantenimiento): no se entrega como ítem. [DUEÑO] decide si se ofrece además; si sí, la crea un humano (GUI).
- **Pruebas.** `lint_hoja.py` + casos dorados + cold run (los pasos con la hoja en GUI son `no_verificado_por_agente`).

## 5. Recetario (biblioteca de recetas)

- **Ficha por receta** (JSONL, `fuente/<id>-unidades.jsonl`): `unidad_id, titulo, contenido{ingredientes[{nombre, cantidad, unidad}], pasos[], porciones, tiempo_min, alergenos[], conservacion}, imagen_id, fuente, licencia_id`. Una plantilla HTML renderiza todas: la uniformidad es de construcción.
- **Unidades del locale.** g/ml; **cucharada ≠ cucharadita** (cucchiaio/cucchiaino, łyżka/łyżeczka…): una unidad cambiada es un defecto BLOQUEANTE (L1-13, sembrado S15). Separadores de número del locale.
- **Tabla nutricional por porción** solo desde base oficial T1 del país (con `afirmaciones.jsonl`); **sin kcal objetivo, sin plan para embarazadas, lactantes o menores, sin dieta por condición** (rojo: se niega). «Sin gluten» y similares con aviso de contaminación cruzada y fuente. Seguridad alimentaria (temperaturas, conservación, huevo crudo) solo con cifra T1 del país.
- **Verificación.** Script de consistencia (porciones × cantidad = total; suma de la tabla) y casos dorados; `n_unidades` prometido = entregado (`cobertura_matriz.py`).
- **Imágenes.** `imagenes-y-creditos.md` (guía de estilo + QA-A con 3 piloto + cotización). Una imagen de IA **nunca** es foto real del plato ni de un resultado.

## 6. Biblioteca de N unidades (patrones, fichas de costeo, tarjetas de conversación, prompts)

Solo es válida si el deseo central es salud, relaciones o dinero (p. ej. 40 fichas de costeo para vendedores de manualidades; 60 recetas con tabla por porción). Pasos y verificación por tipo en `imagenes-y-creditos.md §1-§2`:
- **Patrón con conteos** (puntos, vueltas): script de consistencia y **muestra construida por un humano** en el primer lanzamiento del tipo (`producto.biblioteca_muestra_fisica_min` [propuesto]).
- **Hoja de costeo:** casos dorados; sin promesa de ingresos (versión segura: «costeo y precio mínimo»).
- **Tarjetas o guion:** revisión de seguridad (RHS en el primer amarillo-a); en conflicto de pareja/familia, aviso de seguridad y línea de ayuda; sin imágenes de menores.
- **Prompts:** 3 entradas, ≥ `producto.prompts_exito_pct` utilizables; cada prompt con ejemplo real y 3 pruebas en `autoprueba.json`.

## 7. Checklist (`checklist`)

1-2 páginas, casillas, ordenadas por el orden real de uso; sin consejos individuales ni cifras de resultado; una columna «cuándo parar» si el tema lo exige. Imprimible (PDF vía §10) y, si se promete, MD.

## 8. Minicurso en video corto (`minicurso_video_corto`, tipo `video`)

[SUPUESTO] **Fuera del alcance de v0.1.** El video es un archivo con GUI (edición) y créditos; la IA de video **solo ilustra, nunca prueba** un método ni un resultado. Si una oferta lo exige: D4 produce guion + guía en PDF y marca el video como paso humano/otra skill [PENDIENTE: decisión del dueño y herramienta].

## 9. Pack de recursos (`pack`)

Cada ítem es **un archivo autocontenido con su hash** (guía, plantilla, bonus, bump). El **bump es un ítem separable** (archivo propio; va pre-pago con BLIK/Bancontact/EPS/Pix, que no guardan tarjeta). Cada bonus resuelve un problema de **aplicación** y es descargable: **nunca** una sesión 1:1, un grupo privado, una clase en vivo ni una actualización continua (`requiere_servicio` / `requiere_comunidad_o_en_vivo`). Si D10 entrega un ZIP, lo arma D10 desde los ítems `en_paquete`; D4 no sube el ZIP ni lo hashea en `producto.json`.

## 10. Render HTML→PDF: rutas A, B y C

Se aplica la primera ruta disponible; la ruta usada se anota en `trazabilidad.md` (`ruta_pdf`). Entrada: SOLO archivos locales de `entregables/fuente/` (sin recursos remotos, sin scripts externos).

| Ruta | Herramienta | Estado en esta Mac (2026-11-06) | Comando |
|---|---|---|---|
| **A (por defecto)** | Chrome sin pantalla | **Disponible** (Google Chrome 156; también Brave). Probada con `templates/pdf_base.html` (ver `dependencias.md`); **implementada por `scripts/render_pdf.py`** | `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf=RUTA.pdf "file:///RUTA/fuente.html"` |
| **B** | WeasyPrint (`weasyprint entrada.html salida.pdf`; opción `--pdf-variant pdf/ua-1` sin garantía de accesibilidad) | **[PENDIENTE: instalar]** — no está en `requirements.txt` ni en el `.venv`; requiere OK del dueño (y librerías Pango [VERIFICAR]) | `weasyprint fuente.html salida.pdf` |
| **C** | Sin render automático: entregar **plantilla de hoja de cálculo** (XLSX) o `.md`/HTML autocontenido; o que una persona haga «Imprimir → Guardar como PDF» con el mismo CSS | Siempre posible; el paso de imprimir es **GUI humano** | — |

Notas: Chrome emite el hash distinto en cada render (fecha de creación en el PDF): **hashear solo el PDF final aprobado** y volver a hashear (`empaquetar.py --actualizar`) tras cada render. Chrome fija `/Creator` con su cadena de agente (HeadlessChrome/versión) y `/Title`, `/Lang` salen de `<title>` y `<html lang>`: comprobarlo en L1-04. PDF/UA **no se declara** sin veraPDF [VERIFICAR; veraPDF no está instalado]. EXIF/GPS personales fuera de las imágenes antes de incrustarlas, pero **sin quitar el C2PA** de las imágenes de IA en los archivos fuente (y rótulo «IA» visible en el colofón); incrustar la credencial C2PA en el PDF final es [PENDIENTE: `scripts/producto/c2pa`] (Chrome re-codifica las imágenes y la pierde).

### 10.1 Prueba en frío cronometrada del render (antes de dar por buena la ruta; spec §4.4)
1. Render de una **muestra** con **perfil de navegador temporal y sin caché**: `PERFIL=$(mktemp -d)` y añadir `--user-data-dir="$PERFIL" --disk-cache-size=1 --media-cache-size=1` al comando de la ruta A; cronometrar el render completo (salida del proceso incluida) y borrar el perfil.
2. Comprobar: el PDF **abre**; el **texto se selecciona** (objetos `/ToUnicode`); las **fuentes van embebidas** (`/FontFile*`); `/Title` y `/Lang` salen de `<title>` y `<html lang>` = `oferta.locale` (L1-04); el **peso** queda bajo `producto.peso_max_mb_pdf`; páginas y orden esperados. Hoy, sin `lint_pdf`, lo hace una persona o un script ad hoc de lectura de bytes.
3. Anotar en el informe del QA (y en `trazabilidad.md`): versión del navegador, segundos de pared, peso y resultado de cada comprobación.
4. Resultado de referencia con `templates/pdf_base.html` (2026-11-06; detalle en `dependencias.md`): Chrome 156, perfil temporal, 0,68 s, 136.740 bytes, 5 páginas, 14 fuentes embebidas, `/Title` y `/Lang` de la plantilla.
`scripts/render_pdf.py --cronometrar` hace los pasos 1 y 2 (salvo `lang` = locale y el peso frente a `peso_max_mb_pdf`, que comprueba la persona o `empaquetar.py`) y emite el JSON del paso 3: `{segundos, paginas, bytes, fuentes_embebidas, navegador, …}`. **`segundos` no se compara con `tiempo_prometido_min`** (son los minutos del comprador, `tiempo-y-novato.md §5`): el QA lo registra aparte como la prueba del render. El procedimiento manual de arriba sigue valiendo para B/C o si el script no puede correr.

## 11. Imágenes del PRODUCTO para la landing (las produce D4; spec §4.4)

D5 declara las ranuras en `05-landing/assets.json` (20 de imagen y 1 enlace de compra). **D4 produce las imágenes del producto**: portada, mockups y páginas de muestra (hero con mockup, galería de muestras, portadas de bonus, imagen de la tarjeta de compra), **siempre sobre el entregable real**: capturas veraces, **nunca un mockup de contenido inexistente** (X05 lo marca como error). **D6** produce las de ambiente e ilustración; lo que aporte el dueño entra con origen «dueño».
- Se guardan en `04-producto/entregables/muestras/` (`en_paquete: false`) y D5 las referencia desde su ranura (`assets.json`: `origen` = `producto_muestra`, `licencia_ref`).
- Cada una se registra en `licencias.json` con `productor` (`D4`), `slot_id` sugerido, herramienta y plan, URL de licencia, prompt si es IA y `etiqueta_ia_visible` (los campos opcionales `productor` ∈ {D4, D6, dueño}, `herramienta` y `etiqueta_ia_visible` aún no están en el esquema `assets`: pedido a CT-3, LT-24/LT-32; el literal `dueño`/`dueno` lo fija CT; hasta entonces constan solo en `licencias.json`).
- Se generan **desde el PDF/HTML final aprobado** (captura del render de la ruta A de páginas reales), no desde un diseño aparte; si cambia el producto, se regeneran.
- **Sin testimonios inventados:** no se generan reseñas ni avatares como si fueran clientes; las ranuras de opiniones se **omiten**. Sustituto honesto: páginas de muestra, la garantía y cifras verificables del método (la matriz de promesas y los tiempos medidos), con traza.
- Si la imagen es de IA (la produce D6 o la aporta el dueño; D4 no genera): `etiqueta_ia_visible`, C2PA preservado y la cotización previa de créditos que hace D6 (`imagenes-y-creditos.md`). Una imagen de IA nunca es la «foto» de un resultado.

