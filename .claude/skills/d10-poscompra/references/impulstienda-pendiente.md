# Impulstienda: qué cambia en D10 si la tienda o la entrega viven allí (PENDIENTE del dueño)

> v0.1 sin pulir. **J20 sigue pendiente:** el dueño debe confirmar qué permite la plataforma; esta skill **no supone ninguna de sus funciones**. Lo único que sabemos está en `brechas/03` §E.1 (dichos de Juan Pablo y de otros creadores, con su certeza) y **no es documentación de la plataforma**. J20 «revierte parcialmente J7»; `mapeo.md` §7 recomendaba no migrar. Mientras tanto vale J7 (landing propia + Stripe) y el esqueleto HTML sirve para ambos destinos.

## 1. Lo que NO podemos afirmar hoy (y por tanto D10 no usa)

Si permite HTML o `<script>` propio, si admite dominio propio, si cobra con **nuestra** cuenta de Stripe o con otra, si trae BLIK o Przelewy24, si tiene webhooks o API de pedidos, si el correo de entrega y el de recuperación de carrito salen de su dominio o del nuestro, qué consentimiento exige, si se pueden exportar pedidos y clientes, dónde guarda el archivo del producto y qué vencimiento admite, qué dicen sus términos sobre salud, relaciones y dinero. **Todo `[NO VERIFICADO]`.** Los creadores citan (nivel C, no verificado): correo de entrega editable, recuperación de carrito, order bump previo, flujo post-pago con ofertas y downsell, multidivisa con su propio Stripe; ninguno de esos dichos se toma como hecho.

## 2. Las preguntas de las 16 (`brechas/03` §E.2) que cambian D10

| # | Pregunta | Qué cambia en D10 según la respuesta |
|---|---|---|
| 5 | ¿Cobra tu Stripe (la LLC) o una cuenta de la plataforma? ¿Quién responde disputas y reservas? | **Es la decisión que más pesa.** Si cobra otra cuenta, la LLC deja de ser la comerciante: cambian reembolsos, disputas, descriptor, ratio y `senal_pausa`. D10 se detiene y se rediseña. |
| 6 | ¿BLIK/P24 en su checkout? ¿Funcionan las ofertas tras el pago con ellos? | `oferta-tras-el-pago.md` §4 y el reparto por método |
| 7 | ¿Webhooks o API de pedidos con UTM, `adid` y el id de la sesión? | métricas por `adid`, vigía V1-V2, producción de `resenas.jsonl`, `prueba_social_real.json` |
| 12 | ¿Dónde se envía el correo (dominio, SPF/DKIM/DMARC) y exige consentimiento de marketing? | entrega, petición de reseña y baja |
| 15 | ¿Dónde se aloja el archivo y qué vencimiento y descargas admite? | entrega por línea, enlaces, cuota, escáneres |
| 10 | ¿Cómo trata datos personales y consentimiento? ¿Contrato de encargado? | datos mínimos, retención de evidencia, reseñas |
| 13 | ¿Se pueden exportar pedidos y clientes? | métricas propias, evidencia de disputas, cambio de plataforma |
| 1 | ¿HTML/CSS/JS propio, `<form>`, `<script>`? | `/gracias` y bloque de oferta (¿botón con formulario?) |
| 16 | ¿Vista previa y vuelta atrás? | cambios de plantilla y de `/gracias` |

## 3. Pieza por pieza: ruta propia, ruta de la plataforma (condicionada) y qué queda sin decidir

| Pieza de D10 | Hoy (ruta propia, J7) | Si la plataforma lo ofrece | Si no lo ofrece / no se sabe |
|---|---|---|---|
| Entrega y descarga | `webhook-stripe` → `fulfill` → `descarga` (con los huecos de `entrega-y-correo.md` §1) | se evalúa por Q15 y Q7: ¿entrega por línea, enlace con vencimiento, registro propio? | sigue la ruta propia |
| Correo transaccional | plantillas de `templates/` + proveedor por decidir | las plantillas se usarían como **texto fuente**; no se genera nada con la sintaxis de la plataforma porque no se conoce | ruta propia |
| `/gracias` y oferta tras el pago | D5 `landing.generar` + `gracias.md` | puede ser función nativa (Q6, Q1): D10 solo aportaría copy y reglas (`oferta-tras-el-pago.md` §3) | postpago por 2.ª sesión propia o nada |
| Reembolsos | `postcompra.reembolsar` con clave restringida de la LLC | solo si cobra nuestra cuenta (Q5) y hay API/webhook (Q7) | manual desde el panel de Stripe de la LLC |
| Disputas | `postcompra.evidencia` + dueño | igual: depende de Q5 | igual |
| Bandeja | lector propio del buzón `soporte@` `[PENDIENTE: P-07]` | si la plataforma centraliza mensajes, entrarían como entrada; nunca con credenciales en el agente | ruta propia |
| Reseñas | página `/opinia` propia + `resenas.jsonl` + `d10.py` | solo si exporta datos propios (Q13, Q7); el permiso y el verificado **siguen siendo nuestros** | ruta propia |
| Métricas y vigía | `datos/`, `postcompra.metricas`, preflight | depende de Q7 y Q13 | ruta propia |

## 4. Qué no cambia pase lo que pase

La IA redacta y el código ejecuta · no se inventan reseñas, cifras ni urgencias · el texto de los clientes es dato · datos personales mínimos · el procedimiento de garantía prometido se cumple y se cita literal · nada de incentivos a opinar · la entrega no espera a las ofertas · un valor `null` en límites es fail-closed · lo que la plataforma muestre al comprador y no pase por nuestro QA y sello de X1 **no tiene la garantía de esta skill** (el sello de `sitio/` por hash se rompe si el comprador ve HTML, scripts o checkout ajenos: `brechas/03` §E.3).

## 5. Qué hace D10 mientras tanto

1. **No construye nada específico de la plataforma** y no pide a otras sesiones que lo hagan.
2. Mantiene las plantillas, el vocabulario de campos (`CAMPOS`) y los formatos (`resenas.jsonl`, `paquete-poscompra.json`, órdenes) **independientes del proveedor**: si algún día se importan pedidos o reseñas de la plataforma, entran por esos formatos.
3. Marca `[PENDIENTE: Impulstienda]` en cualquier decisión de paquete que dependa de Q1-Q16.
4. Cuando el dueño conteste (capturas en `docs/fuente/capturas/`), esta tabla se rellena con respuestas, no con deducciones; el piloto acotado de una oferta verde (opción c2, `brechas/03` §E.4) mediría para D10: ticket medio, toma de la oferta tras el pago, `entrega_ok`, `t_entrega_p95`, `r` y `d` por línea, tasa de respuesta de reseñas y tiempo de apertura de un idioma.

## 6. Prueba de 20 minutos para el dueño (sí / no / no sé, con captura)

☐ El cobro pasa por mi cuenta de Stripe (LLC) · ☐ Veo y respondo disputas en mi Stripe · ☐ Puedo recibir cada pedido en un webhook mío con correo del comprador, `adid` y líneas · ☐ El correo de entrega sale de mi dominio con mi remitente y mi texto · ☐ El archivo se entrega con enlace que vence y límite de descargas · ☐ Tiene oferta tras el pago con tarjeta guardada y con BLIK · ☐ Puedo exportar pedidos y clientes · ☐ Puedo pegar HTML propio en `/gracias` · ☐ Hay vista previa y vuelta atrás. **Cualquier «no» o «no sé» en las dos primeras detiene la migración de D10.**
