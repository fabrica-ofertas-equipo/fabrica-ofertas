---
name: conectar-tienda
description: "Conecta la fábrica a la plataforma donde se venden las ofertas: Impultienda (la de referencia), una tienda propia con Stripe que se monta en Cloudflare (tienda-propia), o cualquier otra (Hotmart, Kiwify, Gumroad, Lemon Squeezy, Shopify, Mercado Pago, la que use la persona en su país) escribiendo un adaptador contra el contrato de tienda y comprobándolo con las pruebas de conformidad. Úsala cuando alguien diga «quiero vender con X», «no tengo Impultienda», «conectá mi tienda», «usar otra plataforma», «en mi país no anda Impultienda», «armá mi propia tienda», en el paso 6 de instalar-fabrica, o cuando `python3 -m tienda.conformidad` falle, aunque no nombre la skill."
metadata:
  version: "0.1.0"
---

# Conectar la tienda

La fábrica no habla con ninguna plataforma directamente: habla con el **contrato de tienda** (`tienda/contrato.py`, 15 operaciones) y un **adaptador** por plataforma lo traduce (`tienda/adaptadores/<nombre>.py`). La plataforma activa se elige en `tienda/config.json`. Cambiar de plataforma no toca ninguna skill ni script.

Quien conecta no tiene por qué saber programar: vos escribís el adaptador; la persona crea cuentas, acepta términos, pega claves en `.env` y aprueba pagos.

## 1. Elegir la plataforma

Preguntá con opciones (AskUserQuestion):
- **Impultienda** (recomendada si la persona puede usarla: es la mejor probada, tiene conector MCP, upsells post-compra y repesca). → `instalar-fabrica`, guía 06, y `{"plataforma": "impultienda"}`.
- **Tienda propia con Stripe** (gratis salvo comisiones de Stripe; sirve en cualquier país donde Stripe acepte la cuenta). → paso 3.
- **La que ya usa** (Hotmart, Kiwify, Gumroad, Lemon Squeezy, Shopify, Mercado Pago…). → paso 4.

## 2. Comprobar siempre

```bash
python3 -m tienda                         # plataforma activa y cómo se hace cada operación
python3 -m tienda.conformidad             # tiene que decir ✔
.venv/bin/python -m pytest -q tests/tienda
```

## 3. Tienda propia (adaptador `propia`)

Worker de Cloudflare en `infra/workers/tienda-propia/`: landing por tienda en `https://<dominio>/<slug>/`, checkout de Stripe con bump, PDF por correo (Resend), ventas, embudo, carritos y repesca. No tiene oferta después del pago: la fábrica usa el bump en su lugar.

1. La persona crea (o ya tiene): cuenta de Cloudflare con su dominio, cuenta de Stripe activada para cobrar, cuenta de Resend con el dominio verificado.
2. Vos, en `infra/workers/tienda-propia/`: `npx wrangler d1 create fabrica-tienda` → copiar el id a `wrangler.toml`; `npx wrangler d1 execute fabrica-tienda --remote --file schema.sql`; descomentar la ruta con `tienda.<dominio>`; `REMITENTE` con el correo de soporte; `npx wrangler deploy`.
3. Secretos (los pega la persona en la terminal, nunca en el chat): `npx wrangler secret put STRIPE_SECRET`, `STRIPE_WEBHOOK_SECRET`, `API_TOKEN`, `RESEND_KEY`. El webhook se crea en Stripe → Desarrolladores → Webhooks con la URL `https://tienda.<dominio>/stripe/webhook` y los eventos `checkout.session.completed` y `checkout.session.expired`.
4. En `.env`: `FABRICA_TIENDA_URL=https://tienda.<dominio>` y `FABRICA_TIENDA_TOKEN=<el mismo API_TOKEN>`. En `tienda/config.json`: `{"plataforma": "propia"}`.
5. Prueba: `python3 -m tienda.propia cobro` (tiene que decir `puede_cobrar: true`), publicar una tienda de prueba con `python3 -m tienda.propia publicar …` y una compra con la tarjeta de prueba de Stripe usando `sk_test_…` antes de pasar a la clave real.
6. Píxel: `publicar --pixel <id>` manda PageView e InitiateCheckout. Para Purchase, la persona activa la integración de Stripe con Meta (o se suma la API de conversiones al worker más adelante).

## 4. Otra plataforma (adaptador nuevo)

1. **Leer la plataforma**: su conector MCP si existe (buscalo con ToolSearch y en el registro de conectores), si no su API pública, si no qué se puede hacer desde su panel con el navegador. Anotá qué operación del contrato se hace con qué (`python3 -m tienda` muestra la lista).
2. **Copiar la plantilla**: `cp tienda/adaptadores/plantilla.py tienda/adaptadores/<nombre>.py` (nombre en minúsculas, sin espacios) y completar cada método. Mirá `impultienda.py` y `propia.py` como ejemplos.
3. **Muestras reales** en `tienda/muestras/<nombre>/`: pedí a la plataforma una lista de ventas y las estadísticas de un día y guardá las respuestas tal cual en `ventas.json` y `estadisticas.json` (y `cobro.json` si hay), **cambiando números de orden, nombres y cualquier dato de compradores por valores inventados**. Escribí a mano `*.esperado.json` con la forma normal (está en `tienda/contrato.py`) y `urls.json` con una landing real.
4. **Pasar la conformidad**: `python3 -m tienda.conformidad <nombre>` hasta que dé ✔. Si la plataforma no mide visitas, `embudo` devuelve 0 en `landing` y `como("estadisticas")` lo explica en `notas` (la fábrica sigue con las visitas de Meta).
5. **Activar**: `{"plataforma": "<nombre>"}` en `tienda/config.json`.
6. **Compartirlo** (opcional): si la persona quiere, proponé mandar el adaptador como aporte al repositorio público para que otros lo usen (lo revisa el dueño del proyecto).

## Cómo lo usan las demás skills

Las skills de la fábrica están escritas con las herramientas de Impultienda (`impultienda_*`). Con otra plataforma activa, cada paso que nombra una de esas herramientas se hace con lo que diga `python3 -m tienda como <operación>`; la equivalencia está en `tienda/adaptadores/impultienda.py` → `COMO`. Si una operación da `no_aplica`, ese paso se saltea y se anota en el estado de la oferta.
