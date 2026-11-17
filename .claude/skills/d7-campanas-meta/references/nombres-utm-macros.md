# Nombres, UTM y macros (backbone 5.2 y 5.3)

Se construyen con `scripts/d7.py nombres ...` (envoltorio de `meta.nombres`), nunca a mano. Los patrones salen de `contratos/comunes.schema.json` (`nombre_meta_campana`, `nombre_meta_conjunto`, `nombre_meta_anuncio`).

## Convención

| Objeto | Forma | Ejemplo (`evals/_base`) |
|---|---|---|
| Campaña | `{oferta_id}_{fase}_{objetivo}_{estructura}_{AAAAMMDD}` (fase TEST/ESCALA/REFRESCO; objetivo `VENTAS`; estructura `CBO`/`ABO`) | `OF-202611-02_TEST_VENTAS_CBO_20261116` |
| Conjunto | `{audiencia}_{ubicaciones}_{idioma}` (idioma = `locale`) | `Amplia-IT_Automaticas_it-IT` |
| Anuncio | `{concepto_id}_{formato}_{hook_id}_v{n}` (= `ad_name` del paquete de D6) | `c01-menu_img_h1_v1` |

Reglas: solo ASCII; separador de campos `_`; guion `-` dentro de cada campo (los campos no llevan `_`); **nunca `|`** (en macros se codifica `%7C`). `campana.nombres.anuncios` = `anuncios[].ad_name` sin duplicados. Las uniones de datos **no** dependen de nombres sino de IDs (`oferta_id` + `adid`).

## URL de anuncio

`{paquete.destino.url_base}?utm_source=meta&utm_medium=paid&utm_campaign={{campaign.name}}&utm_content={{ad.name}}&utm_term={{adset.name}}&oferta_id=<id>&cid={{campaign.id}}&asid={{adset.id}}&adid={{ad.id}}`

- Las macros `{{…}}` van literales (Meta las expande al clic); `d7.py nombres url <base> <oferta_id>` la arma.
- `ejemplo_resuelto` se obtiene con `d7.py nombres resolver …` y **no puede tener parámetros vacíos** (sembrado S1: `&asid=` vacío rompe la unión por IDs).
- Las macros de nombre se **congelan al publicar** y los parámetros de URL son **inmutables tras el primer publish** (cambiarlos reinicia el aprendizaje, HC-16).
- `{{campaign.name}}` y `{{adset.name}}` viajan a la URL: ningún nombre, `slug`, `concepto_id` ni `hook_id` puede contener términos sensibles (salud, ciclo, deuda, ruptura, ingresos, impuestos; X1-D01). El lint C15 lo comprueba contra `terminos_sensibles/<locale>.yaml` (lo entrega X1; sin ese archivo el lint **falla cerrado**).
- Las macros dentro de `link_url` o `url_tags` con el MCP son `[VERIFICAR]`; por Marketing API se usa `url_tags`.

## Verificación de captura (D5/D8)

D5 captura `adid`, `asid`, `cid`, `oferta_id`, `utm_*`, `fbp/fbc`; la captura de `adid` en la landing ≥ `parametros.landing.captura_adid_min_pct` y las compras de Stripe con `adid` ≥ `parametros.testeo.cobertura_adid_min_pct` son **dos medidas distintas**. D7 las lee en la vigilancia (`traspaso.adid_capturado_bp`).
