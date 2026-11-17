# Políticas de Meta y de procesadores que afectan al creativo (destilado)

Fuentes internas (no se pega texto largo textual): `docs/_investigacion/04-meta-ads.md` §4 y §10 (D6), `22a-meta-politicas-salud.md`, `22b-meta-politicas-dinero.md`, `22c-meta-politicas-relaciones.md`, `05-legal.md` §3, §5.3, §7, `25-marco-salud-relaciones-dinero.md` §5.3. Las políticas cambian: `compliance.reverif_plataformas_dias` (relectura de plataformas) y `compliance.edad_max_politica_dias`. **Una política que no se pudo leer en fuente oficial es `[VERIFICAR]`; D6 la trata como bloqueante por prudencia.** Quien relee y actualiza es X1; D6 no decide qué política vale.

## 1. Hechos que condicionan las piezas

| Tema | Qué se sabe | Estado | Check |
|---|---|---|---|
| Atributos personales | Prohíbe afirmar o insinuar atributos del espectador (edad, sexo, salud física o mental, situación financiera vulnerable, estado familiar…), **también en pregunta**; «tú/tu» sin atributo es admisible | Leído (HC 2557868957763449; HC-19) | `X1-E01`, `E02` |
| Salud y bienestar | Sin autoimagen negativa ni resultados de peso o estética irreales; sin «promesas de resultados específicos en un plazo» en salud; antes/después de peso restringido; lista cerrada de 11 enfermedades para curas | Leído (HC 2489235377779939; HC-18) | `X1-P01`, `P02`, `M03` |
| Prácticas comerciales prohibidas | Esquemas de «hacerse rico rápido», recompensa financiera irreal por esfuerzo mínimo, retornos garantizados, rendimiento pasado como expectativa, empleos garantizados, cebo de marca o celebridad | Leído (TC-2) | `X1-P01`, `P02` |
| Afirmaciones de ingresos | Meta las admite con aviso claro de no garantía (HC 2347037582714798); **el marco las prohíbe** por Stripe («fast and easy money») y por prudencia. **Nadie cita a Meta contra LP-03** | Leído | `X1-P01`, `P07` |
| Testimonios y reseñas | Regla de la FTC (16 CFR 465): ningún testimonio sintético ni de avatar; solo reseñas reales con `compra_id` | Leído parcial | `X1-P04a`, `P04b` |
| Urgencia y escasez | Solo cierre real programado, verificable por código; la política específica de Meta no se leyó (404) | `[VERIFICAR]` | `X1-P05` |
| Coincidencia anuncio-landing | El producto del anuncio debe coincidir con el de la página (TC-4); enlace roto = «link failure(s)» (HC-21) | Leído | `X1-K01` |
| Contenido generado con IA | Meta pone la etiqueta «AI info» al detectar C2PA o herramientas propias; autodeclaración en UE, California, Nueva York, India, Taiwán; **no eliminar metadatos**; humano fotorrealista generado → etiqueta junto a «Patrocinado» | Leído (HC-22) | `X1-J06` |
| AI Act art. 50 | Desplegadores de *deepfakes* deben revelarlo, de forma clara a más tardar en la primera exposición; aplica desde 2026-08-02; el calendario del Digital Omnibus no lo pospuso | `[VERIFICAR]` texto oficial | `X1-J06` |
| Mejoras automáticas de Meta | HC-42/HC-43: pueden alterar medios y generar hasta 5 variantes de texto sin revisión → `meta_enhancements` **ambos `false`** en el paquete | Leído (mecanismo) | `D6-L1-10` |
| Elusión | Prohíbe ayudar a eludir la aplicación de políticas (cloaker, cuentas paralelas, re-subir texto rechazado) | Leído (TC-4; HC `3858246497787265`) | `D6-L1-08`, `K02` |
| Edición y revisión | Los anuncios se re-revisan en cualquier momento; ediciones frecuentes de anuncios aprobados disparan nueva revisión; un rechazo revertido en revisión no cuenta como infracción (HC 1210227555661027) | Leído (HC-25) | — |
| Fatiga | Meta recomienda creativos «materialmente diferentes» (HC-30; el formato flexible admite hasta 10 activos) | Leído | — |
| Categorías especiales | Anuncios que Meta clasifica como **empleo** (bolsa/listado de vacantes, colocación garantizada; HC 1537759006681893) o **productos financieros** (HC 567423788405762) exigen declarar la categoría especial y aceptan perder segmentación; la guía general de carrera sin listados y la educación financiera sin producto **no** la requieren | Leído; clasificación de un caso concreto `[VERIFICAR]` | D6 marca `categoria_especial_posible` en el brief; decide X1/D7 |
| Instagram | Sin Instagram: identidad = fan page; Meta no sirve en IG sin cuenta propia `[VERIFICAR]` | Decisión del dueño | — |

## 2. Rechazos y congelación (código, no criterio)

Una sola cuenta de Meta y una de Stripe sostienen todo. Reglas deterministas (X1/D7/D8; D6 solo las respeta):
- Un rechazo de **producto o contenido** (C o N) congela la hoja; uno de **pieza** (P o E) revertido congela el ángulo; dos en `compliance.rechazos_ventana_dias` congelan la cuenta (`compliance.rechazos_congelar`).
- Un anuncio `DISAPPROVED` se pausa, abre pedido a D6/X1 y **nunca se reenvía el mismo hash**; D6 no edita un rechazo en bucle: abre un **concepto nuevo** con otro claim (decisión: `references/dependencias.md` §Pedidos).
- La frase rechazada pasa a `fallas_conocidas` (X2) y a la lista de anti-copia: ni retocada, ni traducida.
- Apelaciones: las decide el dueño; el agente no apela (`compliance.apelaciones_max_por_activo`).

## 3. Qué hace D6 con esto

1. Escribe el copy y el guion dentro de los patrones seguros (`angulos-por-nivel.md` §3); nunca contra una política «porque Meta la permite con aviso».
2. Registra en `paquete.politicas` los `meta_enhancements` apagados y la política de IA; registra la herramienta de cada activo y no toca los metadatos.
3. No sube nada: el anuncio llega a D7 con su sello de X1 y D7 revisa los previews (recortes, copy inyectado).
4. Si una política parece contradecir esta skill o la spec, sigue la **más estricta**, lo anota en el brief (`riesgos`) y lo lleva al pulido.

## 4. Pendientes de lectura (no bloquean la v0.1.x, sí la 1.0.0)

Política vigente de engaño/urgencia/testimonios de Meta (la URL de «misleading claims» respondió 404), zonas seguras 9:16 oficiales, límites de caracteres y enum de CTA vigentes, términos de Higgsfield por plan (uso comercial, C2PA) y existencia de prueba de creativos por API con Advantage+ ventas (HC-12). Cierre: `references/dependencias.md`.
