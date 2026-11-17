<!-- Plantilla de guion D6. Un archivo por anuncio: ofertas/<oferta_id>/06-creativos/guiones/<ad_name>.md
     Escribir en el idioma del locale (reescrito desde la motivación local, no traducido). Cada afirmación factual lleva [claim: <claim_id>]
     con un claim_id de oferta.promesa.claims_permitidos. Sin cara, sin atributo del espectador, sin cifras de clientes. -->
---
ad_name: {{c01-hueco_img_h1_v1}}
concepto_id: {{c01-hueco}}
angulo_id: {{hueco-como-relato}}
nivel_conciencia: {{N2}}
hook_tipo: {{escena-pov}}
formato: {{imagen | video | carrusel}}
variante_formato: {{estatico-html | demo-pantalla | voz-en-off-broll | pov-proceso | presentador-ia | vsl-45-90s}}
presentador: {{sin_rostro | locucion_ia | avatar_ia}}
duracion_s: {{null para imagen; número para video}}
idioma: {{es-ES}}
variable_cambiada: {{ninguna (padre) | hook_tipo | angulo | formato | presentador | duracion | cta}}
claim_id_principal: {{claim_id}}
estado: {{borrador | congelado}}   # congelado = hash de textos sellado en QA-A
---

## Gancho (0–3 s) — los tres componentes se complementan y se entienden sin sonido
| Componente | Contenido |
|---|---|
| Acción visual | {{qué se ve literalmente en 0–3 s: manos, hoja, producto; sin rostros ni cuerpos}} |
| Línea hablada (o titular, si es estático) | {{primeras palabras de la voz en off; no repite el texto en pantalla}} [claim: {{claim_id}}] |
| Texto en pantalla | {{palabra o frase clave; nombra el entregable}} |

## Puente (≈3–15 s)
{{continúa la premisa del hook: si el hook promete «el orden para contarlo», aquí empieza a mostrarlo. No es un pitch de marca.}}

## Desarrollo
{{qué es el entregable, para qué sirve, qué incluye; verbos de la herramienta (ordena, calcula, planifica, compara); nada de cambio en el cuerpo, el ánimo, el dinero o la deuda del lector}} [claim: {{claim_id}}]

## Prueba
{{el producto mostrado: página real de 04-producto/entregables/, hoja rellenada con números «ilustrativos» (el rótulo en el mismo cuadro o audio). Sin testimonios, sin capturas de terceros.}}

## CTA
{{una línea; coherente con copy.cta ({{LEARN_MORE | SHOP_NOW | DOWNLOAD}}); precio visible = {{sí/no}}: «{{19,90 €}}»}} [claim: {{claim_id}}]

## Aviso
{{aviso del nicho en el idioma, del glosario: p. ej. «Contenido informativo. No garantiza …»}}

## Subtítulos y audio (solo video)
- Subtítulos: {{texto exacto = línea hablada; sincronizados ≤0,3 s}}
- Audio: {{locucion_ia | sin voz}}; voz preset nativa `{{voice_id}}`; **el texto enviado al generador es exactamente la «Línea hablada» de arriba, sin añadidos**.
- Etiqueta de IA visible: {{sí/no según limites.politica_divulgacion_ia}} — texto: «{{…}}»

## Notas de producción
- Ruta: {{A (HTML→PNG) | B (Higgsfield)}} · ratios: {{4:5, 1:1, 9:16}} · zona segura 9:16 respetada
- Piloto aprobado: {{sí/no/n.a.}}

## Autoverificación del Maker (≥3 observaciones o justificación)
1. {{p. ej. «el hook se entiende sin sonido en 3 s»}}
2. {{p. ej. «ningún atributo del espectador; prueba del espectador ajeno superada»}}
3. {{p. ej. «todos los números salen de claims_permitidos o de oferta.precio»}}
