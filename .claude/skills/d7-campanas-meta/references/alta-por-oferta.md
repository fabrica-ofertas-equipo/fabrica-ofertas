# Alta por oferta en Meta: lo que hace el dueño (dominio, TXT, dataset, token CAPI, spend_cap)

**Hueco documentado:** cada oferta necesita, antes de que D7 pueda armar nada, un dominio verificado en el portfolio, un dataset propio (`DS_<oferta_id>`) y un token CAPI. **El MCP de Meta no crea datasets** (`ads_get_datasets*` solo lee; `ads_pixel_*` y `ads_catalog_*` escriben reglas y están en `deny`) y ningún agente recibe credenciales de Meta. Son **pasos del dueño** (decisión 8: un portfolio, una cuenta, un dataset por oferta, sin Instagram). Fuentes: `docs/06-bases-del-testeo.md` (N01b y tabla de tareas del dueño), `infra/plantillas/{alta-oferta,preflight-items,permisos-tokens,variables-entorno}.yaml`.

## 1. Lo que ya existe (verificado en el repositorio, 2026-11-06)

`python -m infra.alta_oferta` **existe** (`infra/alta_oferta.py`; plantilla normativa `infra/plantillas/alta-oferta.yaml` con **11 pasos**, no 10):

```
python -m infra.alta_oferta listar    --oferta OF-… [--json]     # los 11 pasos, en seco
python -m infra.alta_oferta verificar --oferta OF-… [--json]     # solo lectura; sin transporte = «pendiente de verificar», nunca verde falso
python -m infra.alta_oferta ejecutar  --oferta OF-… --ejecutar   # solo en modo prueba; escribe ofertas/<id>/infra/alta.json
python -m infra.alta_oferta spend-cap --gasto-acumulado-minor N --capital-anuncios-restante-minor N --suma-topes-test-en-curso-minor N
```

El dato del alta es **`ofertas/<id>/infra/alta.json`** (no `alta-oferta.yaml`, que es solo la lista de pasos): `schema_version "0.1.0"`, `completo`, `pasos[]` con `{id, estado ∈ ok|falta|pendiente_verificacion, mensaje, evidencia}`. Sin esquema en `contratos/` todavía `[PENDIENTE: CT-3, LT-30/LT-36]`. D0 no tiene `scripts/dominio_alta.py`.

## 2. Los 11 pasos de la plantilla y lo que D7 exige

| # | `id` del paso | Qué (quién) | Lo usa D7 |
|---|---|---|---|
| 1 | `dominio-compra` | comprar el dominio (dueño; cuesta dinero, nunca un agente) | — |
| 2 | `cloudflare-zona-pages` | zona de Cloudflare y proyecto Pages (dueño) | — |
| 3 | `meta-dataset` | **crear el dataset `DS_<oferta_id>`** (irreversible; máx. 100 por portfolio `[VERIFICAR]`; no reutilizar el de la madre ni el píxel viejo) | **puerta**; P08; sus IDs deben coincidir con `tracking.json` |
| 4 | `meta-capi-token` | token CAPI del dataset, solo como secreto `META_CAPI_TOKEN__<oferta_id>` del Worker `capi`; **nunca** en un chat, archivo del repositorio ni salida de un agente (dueño) | **puerta**; P09, P10 |
| 5 | `meta-dominio-verificado` | TXT `facebook-domain-verification=…` en el DNS de Cloudflare y «Verificar» en Seguridad de la marca → Dominios (dueño) | **puerta**; P11 |
| 6 | `correo-envio` | dominio de envío con SPF, DKIM y DMARC (dueño) | — |
| 7 | `stripe-catalogo-prueba` | Product y Price de prueba (dueño) | — |
| 8 | `stripe-catalogo-vivo` | Product y Price vivos tras la compra de prueba (dueño) | — |
| 9 | `ruta-sesion` | ruta `/api/sesion*` en el Worker `crear-sesion` (dueño) | — |
| 10 | `secretos-por-oferta` | secretos por oferta en cada Worker (por nombre, nunca valores) | — |
| 11 | `spend-cap` | recalcular `limite_gasto_cuenta_meta` y subir el `spend_cap` de la cuenta (máx. 10 cambios/día, solo administradores) | **puerta**; P06 |

**Puerta de entrada de D7** (spec 08 §4 paso 1): `alta.json` con `completo = true` y los pasos `meta-dataset`, `meta-capi-token`, `meta-dominio-verificado` y `spend-cap` en `ok`; los IDs de `tracking.json` deben coincidir con los de la `evidencia` del alta. Si falta cualquiera, D7 **no arma**: el Maker lo declara como bloqueo de entrada y no inventa IDs ni pide credenciales. Los pasos 3–5 son irreversibles o costosos: no se repiten «para probar».

## 3. Lo que D7 necesita y la plantilla no cubre (también del dueño)

| Qué | Dónde se comprueba |
|---|---|
| Asignar el dataset a la cuenta publicitaria **y** al usuario de sistema «operador» (no admin) | `ads_get_datasets` ve el dataset |
| Fan page vinculada a la cuenta (sin Instagram) | preflight **P07** |
| Nombre público del **beneficiario y pagador DSA** si hay UE (queda visible un año), en `empresa/infra/meta.yaml` (`default_dsa_beneficiary/payor`) `[PENDIENTE: D0, SA-1: la carpeta `empresa/infra/` no existe]` | lint C14 / PX1 |
| `estado.json` VERDE (< 6 h): `python -m infra.preflight` | P01–P02 |

Los nombres de menú de Meta son `[VERIFICAR]` en cada cuenta: cambian.
