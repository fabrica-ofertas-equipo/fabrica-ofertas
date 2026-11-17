# Worker `crear-sesion`

`POST <dominio_oferta>/api/sesion`: crea la Checkout Session de Stripe con el
precio del catalogo firmado (nunca del cliente). Acepta DOS modos (docs/06
§4.3; `docs/_historial/decision-arranque-de-pago.md`):

- **JSON** (`application/json`): `{oferta_id, visitor_id, bump, locale, consent_marketing, landing_version, params{...}}` -> `200 {url}`. Sin cambios de comportamiento.
- **Formulario** (`application/x-www-form-urlencoded`, landing sin JavaScript): campos CERRADOS `oferta_id`, `locale`, `bump`, `renuncia_desistimiento` (y `cf-turnstile-response` solo si Turnstile esta habilitado); `visitor_id`/`params` se leen de las cookies `fab_vid`/`fab_attr`/`_fbp`/`_fbc` del mismo origen -> `303` a Stripe Checkout o una pagina de error 4xx simple.

Propietario: B2 (ola 1) + B2b (ola 2, modo formulario). Ver `tracking/README.md` para la tabla de variables de entorno y el resto de los Workers.

## Modulos

- cookies.mjs: parseo de Cookie y fab_vid/fab_attr/_fbp/_fbc (malformada se ignora, nunca 500).
- formulario.mjs: manejarSolicitudSesionFormulario orquesta campos cerrados, mismo origen, Turnstile opcional, catalogo, renuncia de desistimiento, cookies y crearSesionCheckout; valida que la url final sea de checkout.stripe.com antes del 303.
- manejador.mjs: ahora exporta tambien crearSesionCheckout (nucleo: catalogo, cuota, ids, metadata, Stripe) usado por los dos modos; manejarSolicitudSesion (JSON) no cambio de firma ni comportamiento.

## Probar

```bash
cd tracking/workers/crear-sesion && node --test
```

test/manejador.test.mjs (modo JSON, sin cambios), test/formulario.test.mjs (modo formulario: campos cerrados, mismo origen, renuncia de desistimiento, cookies, bump, redireccion solo a Stripe) y test/index.test.mjs (extremo a extremo contra el fetch real del Worker: GET -> 405, formulario completo -> 303, origen cruzado -> 403 sin reflejar la entrada).

## Decisiones (modo formulario, 2026-11-06)
1. Renuncia de desistimiento: checkout.schema.json 1.2.0 no tiene compra.renuncia_requerida. Se lee primero un campo opcional renuncia.requerido/texto_version en el catalogo firmado (documentado en catalogo.mjs); si falta, se usa env.LOCALES_RENUNCIA_REQUERIDA (lista de locales UE/UK en la configuracion del Worker, nunca un literal en el codigo de decision). Pedido abierto a CT/B4 para fijar el campo real.
2. Mismo origen: se usa env.ORIGENES_PERMITIDOS (lista de origenes exactos) cuando falta Sec-Fetch-Site, nunca el Host de la peticion. No se intento derivar el origen desde return_url del catalogo para evitar acoplar el chequeo de seguridad a un campo pensado para otra cosa.
3. Cookie fab_attr: no hay contrato para su forma; se asume JSON codificado con encodeURIComponent sobre {utm_source,utm_medium,utm_campaign,utm_content,utm_term,cid,asid,adid} (documentado en cookies.mjs). Cualquier otra forma real que escriba consentimiento.js (B4) rompe la atribucion en modo formulario: pedido abierto a B4.
4. landing_version en modo formulario: no viene del cliente (no hay JS). Se lee de un campo opcional landing_version del catalogo firmado; si falta, "desconocida". No se intento como literal fijo en el codigo.
5. consent_marketing en modo formulario se deriva de la presencia de una cookie fab_vid valida (consentimiento.js solo la escribe tras el consentimiento de marketing, decision-arranque-de-pago.md 2.3): con cookie valida, consent_marketing="1"; sin ella (ausente o malformada), "0" y visitor_id aleatorio sin atribucion.
6. CSP de la pagina del formulario (la define landing/B4, no este Worker): form-action 'self' https://checkout.stripe.com [VERIFICAR en Chrome: Chromium aplica form-action tambien a las redirecciones posteriores al envio, decision-arranque-de-pago.md 2.5]. Turnstile queda fuera de v1 (protege /api/sesion solo el limite de tasa del WAF de Cloudflare); por eso cf-turnstile-response no esta en la lista cerrada de campos salvo que env.TURNSTILE_SECRET este configurado, y esta probado apagado.

## Pedidos (modo formulario)
- CT/B4: fijar compra.renuncia_requerida (o equivalente) en checkout.schema.json / el catalogo que produce landing.catalogo, y la forma exacta de la cookie fab_attr que escribe consentimiento.js.
- B8: agregar ORIGENES_PERMITIDOS (ya citada en wrangler.toml pero sin uso hasta ahora) y LOCALES_RENUNCIA_REQUERIDA a infra/plantillas/variables-entorno.yaml.
- B4: landing/comprar.html debe enviar exactamente los campos cerrados (oferta_id, locale, bump, renuncia_desistimiento) con method=post action=/api/sesion, sin campos extra (ver decision-arranque-de-pago.md 2.2) y la pagina donde vive el formulario debe calzar con alguno de los origenesPermitidos.
