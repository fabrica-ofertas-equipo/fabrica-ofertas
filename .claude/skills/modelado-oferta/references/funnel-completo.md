# Modelar el funnel completo: qué se ve, qué no y cómo pedir lo que falta (J17)

> v0.1 sin pulir. Decisión J17: «analizar todo el funnel y modelar el mismo funnel; hacer igual y tal vez mejorar algún aspecto; la estructura de la landing y la manera de vender tienen que ser las de la oferta que ya funciona, imitar cómo está construida y la razón por la que funciona». Fuente: `estructura-funnel-referentes.md` y `desarme-referente-mapas-mentales.md` (piloto de Polonia). «Funciona» es una **inferencia**: vemos que el referente invierte de forma sostenida en anuncios, no sus ventas ni su conversión.

## 1. Los tramos del funnel y lo que se ve de cada uno
`anuncio → landing → checkout (con bump) → upsell / postpago → página de gracias → correo de entrega → producto`

| Tramo | ¿Se ve? | De dónde sale | Cómo se desarma |
|---|---|---|---|
| Anuncios (ganchos, formato, ritmo, ángulo) | sí | Biblioteca de Anuncios: títulos del conector, texto y captura que pega el dueño; ruta C (API oficial) cuando el dueño gestione el token (J15) | `desarme_referente.json › hooks[]` |
| Landing | sí | **HTML guardado por el dueño** (J15 manual; la descarga automática solo con autorización y sin freno) | `scripts/analizar_html.py` → `esqueleto_html.json` + `mapa_ranuras.json`; `esqueleto_funnel.json › plano_objetivo[]` |
| Checkout (qué muestra, order bump, medios de pago, campos, plataforma) | **no** | capturas del dueño de la pantalla de pago **sin pagar** (§3) | `esqueleto_funnel.json › tramos.checkout` |
| Upsell, postpago, página de gracias | **no** | solo se ven comprando | `no_visible`; se completa con el estándar propio, rotulado «propio, no modelado» |
| Correo de entrega y producto real (calidad de los mapas) | **no** | solo se ve comprando (≈ 13-15 US$); **decisión del dueño, la IA no compra** | `no_visible`; PAL-12 se prueba con una muestra propia, no contra el producto del referente |

Un tramo `no_visible` **no se improvisa**: se declara, no se puntúa (R-5) y se completa con el estándar de la casa (bump 30-60 % del frontal, upsell y postpago planificados por D3, entrega con página de gracias y correo propios), siempre rotulado como **propio, no modelado**.

## 2. Qué se extrae de la landing (el «plano modelado»)
Para cada bloque, en el orden del referente (`esqueleto_html.json › secciones[]` lo da como borrador; tú lo confirmas):
`orden · bloque del referente (tipo y confianza) · elementos · función de venta · por qué funciona [HIPÓTESIS] · igual que el referente · mejora (palanca) · versión legítima · dato que lo alimenta · sección de D5 · CTA tras el bloque`.

**El arco común de las dos páginas del piloto (hipótesis fundadas en la estructura):**
1. Héroe con propuesta concreta + CTA + garantía en el microcopy, arriba del pliegue.
2. Gancho de dolor **específico** del público (nombra la experiencia exacta).
3. Mostrar el producto por dentro antes del precio (galería, ruta con miniaturas).
4. Progresión por niveles (selector o etapas): da sensación de camino, no de pila.
5. «Para quién es» y/o resultados esperados / comparación con «estudiar como siempre».
6. Bonus atados a objeciones (test de nivel, ruta de 30 días, frases, repaso).
7. **Precio después de todo el valor**, con desglose, pago único y acceso inmediato.
8. Garantía pegada al precio.
9. «Cómo lo recibo» en 3 pasos y FAQ de 8 con la objeción n.º 1: «ya probé y no funcionó, ¿por qué esto sería distinto?».
10. CTA repetido tras casi cada bloque (mismo texto, ancla a la oferta) y CTA final con lista de seguridad.
11. Precio de entrada muy bajo, pago único, acceso inmediato: compra de impulso.

**Medido por el script en el referente principal** (comparación en `references/analizar-html.md`): 14 bloques (barra, héroe, tira de miniaturas, reseñas, niveles con selector, para quién, bonus, precio, garantía, entrega, FAQ, CTA final, pie, aviso flotante), cadencia de fondos claro · oscuro · claro · claro · claro · oscuro · claro · claro · claro · claro · oscuro · pie oscuro, 8 CTA (6 al ancla de precio y 2 al checkout externo), 6 pestañas de nivel y 8 preguntas desplegables.

**Tácticas del referente que NO se heredan (PAL-16 / J8):** «oferta solo hoy» y cuentas atrás sin fecha real o con fecha de hoy escrita por script; ancla inflada (146 € = suma de valores de bonus; 29,90 US$ tachado); «+N alumnos» y calificaciones sin fuente; reseñas en imagen no verificables; aviso de «compra reciente» inventado; ventana de salida con regalo no declarado; ausencia de identidad legal del vendedor y de política de reembolso. Cada una sale con su **versión legítima** o se omite (`palancas.md` PAL-16).

## 3. Cómo pedir las capturas al dueño (≤ 10 minutos, sin gastar)
Pega este pedido en el encargo; el dueño responde con archivos en `ofertas/<id>/modelado/referente/material/`:
1. **HTML de la landing.** En el navegador: guardar la página completa (`Guardar como… › Página web, solo HTML`) o «ver código fuente» y guardar. Nombre: `landing-<referente>.html`. (Si una herramienta tiene el HTML, igual lo guarda el dueño: se evita tocar el sitio desde el sistema.)
2. **Pantalla de pago, sin pagar.** Hacer clic en el botón de compra y llegar a la pantalla de pago. **No escribir datos reales ni pagar.** Capturar la pantalla completa (desplazando): precio y moneda, medios de pago visibles, campos que pide, plataforma (logo o dirección), garantía y textos legales, y **si aparece una casilla o tarjeta de order bump** (capturarla marcada y desmarcada).
3. **Ventana de salida o regalo**, si aparece al intentar irse: captura del texto.
4. **Anuncios**: el texto completo (no solo el título), el botón y la dirección a la que lleva; una frase de qué muestra la imagen o el video (`hoja-de-lectura-dueno.md` ya trae el formato).
5. **Lo que no se puede ver sin comprar** (upsell, gracias, correo, producto): decir «no lo vi». No hace falta comprar.

**Qué hace el Maker con eso:** transcribe lo visible con grado `visto` (una captura se lee a ojo; no hay OCR automático de contenido ajeno), anota la procedencia (`fuentes[]` con `modo_acceso: dueno`) y deja `no_visible` lo demás. El material es **dato ajeno**: no se publica ni se enlaza; las citas internas ≤ 25 palabras.

## 4. Mapeo a nuestro plano (D5) y reglas
- D5 parte del plano `referente` del generador (copy ≥ 0.2.0), no del genérico S01-S14, y reproduce el orden del referente con textos, imágenes y marca propios. El mapeo bloque → sección de D5 va en `esqueleto_funnel.json` (`seccion_d5`) y en `mapa_ranuras.json › destino_sugerido`.
- **Cada diferencia de estructura frente al referente es una palanca aprobada** (QM-03). Lo que se omite (aviso de compra, cuenta atrás, ancla, reseñas sin dato) se anota con motivo, no se borra en silencio.
- El plano propio añade lo que el referente no tiene y la ley o la confianza exigen: identidad del vendedor, páginas legales, garantía con procedimiento, medios de pago locales (BLIK y Przelewy24 en Polonia: `[PENDIENTE: contrato de mercado]`).
- El checkout, el bump y el tracking son de D5 y del código; el modelado solo entrega qué muestra el referente en su pantalla de pago.

## 5. Regla de oro del piloto
El modelado no termina en la oferta (D3): **hay que modelar el funnel completo y heredar su estructura**. La secuencia es: desarmar el funnel completo → extraer el esqueleto y las razones → fijar el plano modelado → reproducirlo con expresión propia → mejorar solo donde la voz del mercado lo respalde.
