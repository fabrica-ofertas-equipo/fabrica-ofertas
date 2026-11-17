# El pedido: identificadores, líneas, estados y datos mínimos

> v0.1 sin pulir. «Pedido» en este archivo = una compra (una sesión de Checkout) y todo lo que cuelga de ella. **No confundir con `../PEDIDOS.md`**, que lista lo que esta skill pide a otras sesiones (S-A, S-B, S-C).

## 1. Identificadores

| Id | Qué es | Quién lo asigna | Quién lo ve |
|---|---|---|---|
| `checkout_session_id` (`cs_…`) | la sesión de Stripe; clave de idempotencia de la entrega, el reembolso y la reseña | Stripe | código, Maker (como id, no es dato personal) |
| `pedido_ref` (propuesta `ENT-` + 12 hex derivados del `session_id`) | el número que cita el comprador en el correo y en soporte | código (hoy el correo no lo lleva: P-02) | comprador, Maker |
| `entrega_id` (`ENT-…`) | fila de `entregas.jsonl` (contrato `entrega`) | motor (`/ingesta/entrega`) | código |
| `reembolso_id` (`RF-…`), `idempotency_key` | fila de `reembolsos.jsonl` | `postcompra.reembolsar` | código |
| `resena_id` (`RS-…`) | fila de `resenas.jsonl` | código | código, Maker |
| `mensaje_ref` (`MSG-…`) | mensaje de la bandeja | lector del buzón (P-07) | código, Maker |
| `adid`, `asid`, `cid`, `oferta_id` | atribución (metadata de la sesión) | D5/D7 | código (D8 une por `oferta_id` + `adid`) |

## 2. Líneas del pedido

`principal` (frontal), `bump` (casilla en `/comprar`), y cuando existan `upsell` y `postpago`. Cada línea tiene sus ítems (`producto.items[]`), su precio (`oferta`/`checkout`), su entrega y su reembolso. El reembolso es total por defecto.

## 3. Estados (los del contrato `entrega`) y quién los emite

| Estado | Quién | Hoy |
|---|---|---|
| `pagado` | webhook de Stripe | recibido, sin continuar a `fulfill` |
| `encolado` | `webhook-stripe` → `fulfill` | solo se declara en la respuesta |
| `enviado` | proveedor de correo aceptó el envío | no se emite |
| `entregado` | `fulfill` (hoy lo emite siempre, aunque el correo falle: `entrega-y-correo.md` §1.1) | emitido |
| `descargado` | `descarga` (1.ª descarga) | no se emite |
| `activado` | descarga + clic confirmado (no un escáner) | no se emite |
| `resultado` | respuesta afirmativa a la pregunta de utilidad (sin cifras de cambio) | no se emite |
| `fallido` | envío rechazado tras `entrega_reintentos` | no se emite |

## 4. Reglas de datos

- El **correo del comprador** vive en Stripe y en el proveedor de correo; en el repositorio solo como `email_hmac` o hash. Ni el Maker ni los informes lo llevan.
- **IP y agente de usuario** (evidencia de disputa): tabla restringida de D5, solo hacia Stripe, `evidencia_retencion_dias` (180; BLIK 400).
- `soporte.jsonl`, `senales_propias.jsonl` y `resenas.jsonl` llevan ids y extractos de hasta 200 caracteres **sin** datos personales ni de salud, deuda o ruptura.
- Un pedido de **prueba** (`cs_test_*`, del dueño o `sintetico`) no recibe petición de reseña, no cuenta en `prueba_social_real.json` y no entra en el informe de producción.
- Un pedido **reembolsado** se conserva con su historia: no se borra ni se oculta; deja de recibir correos de reseña.

## 5. Dónde están las cosas

`ofertas/<id>/10-postcompra/`: `entregas.jsonl`, `reembolsos.jsonl`, `senal_pausa.json`, `outbox/` (código) · `paquete/` (`postcompra.publicar_producto`) · `emails/`, `soporte/`, `bandeja/`, `resenas.jsonl`, `resenas_informe.json`, `informe-poscompra-*.md`, `paquete-poscompra.json` (esta skill).
