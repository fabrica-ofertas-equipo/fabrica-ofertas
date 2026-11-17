# Hoja de captura asistida (la rellena una PERSONA; no el Maker, no el chat)

Pega en `empresa/descubrimiento/entrada/AAAA-MM-DD.txt` (o, para el material del Modo D, en `ofertas/<oferta_id>/01-descubrimiento/crudo/material/<modelo_id>.json`). **Una línea por extracto.** Antes de que lo lea el Maker se corre `validar_candidatos.py entrada RUTA`; con hallazgos, se redacta de nuevo.

Formato de línea: `«extracto ≤ 25 palabras»` · `fuente_id` · `URL https` · `fecha de publicación AAAA-MM-DD` · `locale`

Reglas de redacción (checklist):
- [ ] ≤ 25 palabras, textual, entre comillas; sin unir fragmentos de lugares distintos.
- [ ] Sin nombres propios de personas, @usuarios, correos, teléfonos, fotos ni enlaces a perfiles (`[REDACTADO]`).
- [ ] **Salud y relaciones:** solo reseñas públicas DEL PRODUCTO, preguntas «cómo…» sin hecho personal, o datos propios D8/D10. Nunca el relato de una persona (diagnósticos, rupturas, deudas, menores): ni íntegro ni redactado.
- [ ] La fuente está en `fuentes_permitidas`; abierta en tu navegador normal, sin sesión de valor, a ritmo humano; sin captcha, login ni muro evadido.
- [ ] Con tu cuenta personal o un perfil con sesión **no** se pega nada de un grupo privado.
- [ ] El texto es dato: si trae una orden a una IA, igual se pega tal cual y lo reporta el Maker como contenido hostil (no la ejecutes ni la «pruebes»).

Para el material de una oferta (Modo D): `anuncios[{ad_id, texto}]` y `paginas[{url, titulo, texto}]` con lo que ves en el `ad_snapshot_url` y en la página de venta (precio, estructura de la oferta, garantía, promesas, prácticas como cuenta regresiva o testimonios de ingresos). No copies imágenes ni textos largos: lo esencial para que dos jueces evalúen puertas y transferibilidad.
