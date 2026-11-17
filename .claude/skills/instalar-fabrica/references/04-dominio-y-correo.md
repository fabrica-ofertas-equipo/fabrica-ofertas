# 4 · Dominio y correo de soporte

El correo de soporte aparece en cada tienda y landing; los clientes escriben ahí y la tarea de soporte los contesta sola desde Gmail.

1. **Dominio.** Si no tiene, que compre uno corto y neutro (no el nombre de una oferta: se usa para todas). Recomendado: comprarlo en Cloudflare (cuenta gratis en dash.cloudflare.com → Registrar dominios), porque ahí mismo se arma el reenvío de correo. Si ya lo tiene en otro lado, que lo agregue a Cloudflare (Agregar un sitio) y cambie los servidores DNS donde lo compró; abrile las dos pantallas.
2. **Reenvío de correo** (Cloudflare → el dominio → Correo electrónico → Enrutamiento de correo): crear la dirección `soporte@<dominio>` que reenvíe a su Gmail. Cloudflare manda un correo de verificación a ese Gmail: que lo confirme.
3. **Conector de Gmail en Claude:** Configuración → Conectores → Gmail → conectar con esa misma cuenta. Comprobá con una búsqueda (`search_threads` con `newer_than:1d`).
4. **Responder como soporte** (opcional pero recomendado): en Gmail → Configuración → Cuentas → «Enviar como» → agregar `soporte@<dominio>`. Mientras no lo haga, las respuestas salen desde su Gmail.
5. Si el dominio no estaba al correr el paso 3, corré ahora `personalizar.py` con el dominio y el correo.

Marcá: `estado_instalacion.py marcar conector-gmail --nota "soporte@… reenvía a Gmail"`.
