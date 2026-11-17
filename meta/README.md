# meta

Cliente y lógica de Meta Ads: nombres y URL de atribución, offset de moneda, borrador de campaña
(todo `PAUSED`), preflight P01-P25, activación (N12), monitoreo post-activación, kill switch de
campaña/cuenta y lectura de insights para el ETL.

Propietario: **B5** (ola 1), con `08-campanas-meta` como especificación (`departamentos/08-campanas-meta.md`).
Una cuenta publicitaria, un dataset por oferta; nada se activa sin límites cargados, sello de X1 vigente
ni `PAUSA` ausente. `ClienteMeta` **solo** corre sobre un `Transporte` inyectado (en esta entrega,
siempre `engine.transporte.TransporteFixture`: ver «Decisiones»).

## Módulos

| Módulo | Qué hace |
|---|---|
| `meta.monedas` | `a_unidad_meta(monto_minor, moneda)`: convierte un importe (unidad menor ISO 4217) a la unidad que espera Meta (offset 1 u offset 100, convenciones §3) |
| `meta.nombres` | `nombre_campana/conjunto/anuncio`, `validar_nombre`, `url_anuncio`, `resolver_url` (backbone §5.2-5.3); CLI propia (A3) |
| `meta.cliente` | `ClienteMeta`: `appsecret_proof`, reintento ante el error 613, ritmo (≥30 s entre ediciones del mismo objeto, ≤4 cambios/hora) |
| `meta.payloads` | `calcular_presupuesto` (Anexo A3/§3.4: aplica `tarifa_meta_bp`, calcula `n_anuncios`/`total`, `spend_cap` o candado alternativo — A6) y los payloads de creación de campaña/conjunto/anuncio; `targeting_payload` expone el sub-objeto `targeting` aparte; CLI `presupuesto` (A3) |
| `meta.crear` | Borrador `PAUSED` (campaña → conjunto → creativos → anuncios), idempotente por nombre |
| `meta.preflight` | P01-P24 (+P25 si `special_ad_categories` no está vacío); cada check es puro sobre `Entradas`; CLI propia (A3). `items_px`/`EntradasPX`: PX1-PX4 (DSA, tarifa de ubicación, riesgo, términos sensibles) en un informe APARTE, nunca en el objeto sellado (A4) |
| `meta.activar` | N12: sello de X1 (TOCTOU) + los 7 pasos de `engine.guard` + relectura del árbol vivo + **re-lectura y comparación del estado vivo** (`leer_estado_vivo`/`diferencias_config_viva`: presupuesto, evento de optimización, targeting, creativo, DSA — A5) + activación anuncios→conjunto→campaña con rollback si falla un `POST` |
| `meta.lectura_viva` | `generar()`: `07-campana/lectura_viva.json`, el estado vivo de la campaña para que el QA de D7 (sin Bash ni `mcp__*`) lo lea sin volver a consultar Meta (A13); reutiliza `meta.activar.leer_estado_vivo` |
| `meta.monitor` | Traspaso T+1/6/24/48/72 h; pausa anuncios `DISAPPROVED`, cuenta `rechazos_7d`, pide revisión a D6/X1; CLI propia (A3) |
| `meta.pausar` | Capa 2 del kill switch: `PAUSED` idempotente con relectura, por campaña o por toda una cuenta |
| `meta.insights` | Lectura de resultados por anuncio y día para `datos.etl_meta` (sin efectos) |
| `meta.subir_presupuesto` | Sube el presupuesto de un conjunto dentro de los topes y el ritmo (la decisión de cuánto es de D8/D9) |
| `meta._cli_comun` | Ayudas compartidas de los CLI con `ClienteMeta` (no es un módulo de dominio) |

## CLI

Los cuatro envoltorios de una línea viven en `scripts/{meta_crear,meta_activar,pausar,subir_presupuesto}.py`.
Todos aceptan `--modo {dry-run,fixture,live}` (por defecto `dry-run`: solo imprime el plan, sin tocar
nada), `--json`, `--raiz` y `--ahora` (los dos últimos solo fuera de producción).

```bash
# Borrador de campaña (dry-run: imprime el payload de creación, no llama a Meta)
python -m scripts.meta_crear --oferta OF-202611-01 \
  --campana ofertas/OF-202611-01/07-campana/campana.json \
  --creativos creativos.json --ad-account act_100000000000001 --pixel-id PX1 --json

# El mismo comando en modo fixture (sin red; tests/fixtures/meta/reglas_crear.json)
python -m scripts.meta_crear --oferta OF-202611-01 \
  --campana tests/fixtures/meta/campana_borrador.json --creativos tests/fixtures/meta/creativos.json \
  --ad-account act_100000000000001 --pixel-id PX1 \
  --modo fixture --fixture tests/fixtures/meta/reglas_crear.json --salida ids_meta.json --json

# Activación (dry-run: solo muestra qué IDs activaría)
python -m scripts.meta_activar --oferta OF-202611-01 --ids-meta ids_meta.json \
  --hash-config sha256:<64 hex> --cuenta cuenta.json --monto 5000 --moneda EUR --json

# Kill switch de una campaña o de toda una cuenta (dry-run)
python -m scripts.pausar --campana-id 123456 --json
python -m scripts.pausar --ad-account act_100000000000001 --json

# Subir presupuesto de un conjunto (dry-run)
python -m scripts.subir_presupuesto --oferta OF-202611-01 --object-id 222 --monto 600 --moneda EUR --cuenta cuenta.json --json
```

**A3 (ola 2, B5b): `meta.nombres`, `meta.payloads` y `meta.preflight` ya tienen CLI propia** (antes
no existían, ver «Dependencias» de la skill D7). `meta.nombres` y `meta.payloads presupuesto` son
puros (sin `--modo`, sin red); `meta.preflight` y `meta.monitor`/`meta.lectura_viva` sí aceptan
`--modo {dry-run,fixture,live}` (como los 4 de arriba) porque leen `limites`/`parametros` o un
`ClienteMeta`. Se invocan con `python -m meta.<modulo>` (todavía no tienen envoltorio en `scripts/`:
pedido abierto a quien decida los nombres finales).

```bash
# Nombres y URL de Meta (puro; backbone §5.2-5.3)
python -m meta.nombres campana --oferta OF-202611-01 --fase TEST --objetivo VENTAS --estructura CBO --fecha 2026-11-10 --json
python -m meta.nombres url --base https://ofertalanding.com/ir --oferta OF-202611-01 --json

# Presupuesto de D7 (Anexo A3/§3.4): tarifa de Meta, n_anuncios y total, desde economia.json (D3)
python -m meta.payloads presupuesto --economia ofertas/OF-202611-01/03-oferta/economia.json \
  --n-anuncios-paquete 5 --escenario central --json

# Preflight sobre hechos ya leídos (entradas.json los junta quien orquesta; nunca Meta en vivo acá)
python -m meta.preflight --oferta OF-202611-01 --entradas entradas.json \
  --campana ofertas/OF-202611-01/07-campana/campana.json --salida preflight.json --json

# Vigilancia T+Nh tras activar (dry-run: solo muestra qué objetos leería)
python -m meta.monitor --oferta OF-202611-01 --ids-meta ids_meta.json --ventana-h 24 \
  --gasto-real 1000 --gasto-esperado 1200 --moneda EUR --estado-aprendizaje LEARNING \
  --clics-enlace 100 --vistas-landing 90 --json

# Estado vivo de la campaña para el QA de D7 (A13; dry-run: solo muestra qué objetos leería)
python -m meta.lectura_viva --oferta OF-202611-01 --ids-meta ids_meta.json --hash-config sha256:<64 hex> --json
```

Códigos de salida: 0 correcto · 2 uso (argumentos, `--oferta` que no coincide con la campaña) ·
3 validación (esquema, moneda) · 4 bloqueado (`PAUSA`, infra, sello de X1 inválido o ausente, orden
sin firmar, **`--modo live`** — ver «Decisiones») · 5 límite (`limites.yaml`/`parametros.yaml`
faltante o insuficiente) · 6 externo (error de la Marketing API, incl. 613 tras agotar reintentos).

**Entradas y salidas:** `meta.crear` lee `campana.json` (`contratos/campana.schema.json`) y un JSON
`{ad_name: payload_de_adcreatives}`; escribe (con `--salida`) `ids_meta.json`
(`contratos/ids_meta.schema.json`). `meta.preflight.generar` produce un objeto contra
`contratos/preflight.schema.json`. `meta.monitor.monitorear` produce un objeto contra
`contratos/traspaso.schema.json`. `meta.activar` lee `ids_meta.json` y el sello de X1
(`empresa/compliance/sellos/<hash>.json`, o la ruta que dé `--sello`).

**Variables de entorno:** `META_TOKEN_OPERADOR`, `META_APP_SECRET` (con `--modo fixture` son
ficticias; con `--modo live` no se usan aún — ver «Decisiones»). Las credenciales exigidas por
`engine.guard` (`META_TOKEN_OPERADOR`, `META_AD_ACCOUNT_ID`, `META_APP_SECRET`) ya están en
`.env.example` (B8).

## Probar

```bash
.venv/bin/python -m unittest discover -s tests/meta -t .
```

155 pruebas, sin red (`TransporteFixture` en todas; ninguna abre un socket real). Fixtures en
`tests/fixtures/meta/` (campaña de ejemplo, creativos, reglas de `TransporteFixture`).

## Decisiones

- **`ClienteMeta` solo sobre `TransporteFixture` esta noche** (alcance explícito de la entrega):
  `--modo live` existe en los 4 CLI por consistencia de interfaz pero se niega con `ErrorBloqueado`
  (código 4) hasta que un `Transporte` real se conecte. `--modo fixture` corre el mismo código de
  decisión sobre un archivo de reglas (`TransporteFixture.desde_archivo`); es lo que corre
  `engine.guard.comprobar_live(simulacion=True)` también. El único cambio para ir a producción es
  construir un `Transporte` real (stdlib `urllib` o `http.client`) e inyectarlo: ninguna función de
  `meta/` depende de `TransporteFixture` por su tipo salvo el propio `_cli_comun.construir_cliente`.
- **Sello de X1 por archivo, no por `compliance.verificar_sello`**: ese módulo no existe aún (B6 lo
  construye en paralelo, ola 1). `meta.activar.activar()` recibe `verificar_sello` como parámetro
  (inyección de dependencia); el CLI (`--sello RUTA`) lee un JSON de disco. Cuando B6 entregue
  `compliance.verificar_sello(clave, ahora) -> Sello | None`, el CLI solo cambia esa función inyectada.
- **Ritmo de `ClienteMeta` (≥30 s, ≤4/hora) es una segunda defensa, no el tope de negocio**: los
  valores vienen de `limites.yaml` (`segundos_min_entre_ediciones`,
  `max_cambios_presupuesto_por_hora_por_conjunto`), los mismos que `engine.guard` exige en su paso 5
  para `--live`. `ClienteMeta` los aplica también localmente (`cambiar_estado`/`cambiar_presupuesto`)
  para no depender de que cada llamador pase siempre por `guard` (p. ej. `meta.monitor` pausando un
  anuncio rechazado no pasa por `guard`). **Pausar siempre usa `forzar=True`** (salta el ritmo): un
  rollback o un kill switch no puede quedar bloqueado por «hace menos de 30 s que edité este objeto»
  (`contratos/gates.json`, `accion:pausar`: «pausar nunca requiere esperar»).
- **Backoff del error 613 es una constante técnica**, no un parámetro de negocio (`_REINTENTOS_613_MAX`,
  `_ESPERA_613_BASE_S` en `meta/cliente.py`), igual que `engine.comun._TIMEOUT_SUBPROCESO_S`: es la
  política de reintento ante un código de error conocido de la plataforma, no un tope de dinero, plazo
  de decisión ni porcentaje (convenciones §3). `dormir` es inyectable; ninguna prueba duerme de verdad.
  Un paquete nuevo (`requests`, `httpx`) **no** se necesitó: `urlencode`/`hmac`/`hashlib` de la biblioteca
  estándar bastan.
- **Creativos no se suben desde `meta/`**: `meta.crear.crear()` recibe `payloads_creativo` ya armado
  (ad_name → payload de `act_<id>/adcreatives`); subir el asset en sí (D4/D6/postcompra) es de otro
  componente. Esto evita que B5 adivine el formato exacto de `object_story_spec` antes de que exista
  `paquete.json` real.
- **`object_ids` que compara `meta.activar`** = campaña + conjuntos + anuncios (`meta.activar.ids_de`);
  los `creative_ids` no se activan (son activos estáticos) y no entran en la comparación con el sello.
- **P01-P24 de `meta.preflight` son puros sobre `Entradas`**: este módulo no llama a Meta, a la landing
  ni a `compliance`; quien orquesta junta los hechos (de Meta, del dataset, de `lint_claims`, etc.) en
  un objeto `Entradas` y los pasa. Un campo ausente es `ROJO` con evidencia «dato ausente» (fail-closed):
  nunca se asume que algo no comprobado está bien. `P25` no es parte de `CHECKS` (24, igual que el
  esquema): se agrega al resultado solo si `special_ad_categories` no está vacío.
- **`meta.subir_presupuesto` no decide cuánto subir**: solo ejecuta, dentro de lo que `engine.guard`
  aprueba para `aumentar_presupuesto`, la subida que ya decidió D8/D9 (`decision.*`, B1).
- **A5 (re-lectura del estado vivo en `meta.activar`):** `diferencias_config_viva` compara, campo por
  campo, lo que `campana.json` sellado declara contra lo que `leer_estado_vivo` lee de Meta (vía
  `ClienteMeta`): `presupuesto`/`spend_cap` o `candado_alternativo`, `evento_optimizacion` (por
  `promoted_object.custom_event_type`, no por `optimization_goal`: ese campo es el MISMO para
  `PURCHASE` e `INITIATE_CHECKOUT` en `meta.payloads._EVENTO_OPTIMIZACION_META`, así que no
  distinguiría nada), `targeting` (vía `meta.payloads.targeting_payload`, ahora pública) y `creativo`
  (que el `creative_id` en vivo de cada anuncio siga siendo el de `ids_meta.creative_ids`: los
  creativos son inmutables, un cambio ahí es un reemplazo silencioso). `enlace` y `textos` (dentro de
  `object_story_spec.link_data` del creativo) solo se comprueban si se pasa `payloads_creativo`
  (`--creativos`, el mismo `{ad_name: payload}` de `meta.crear`): sin él, el resultado trae un aviso
  («sin --creativos: no se comprobaron enlace ni textos») en vez de bloquear, porque esos dos campos
  no tienen hoy un valor «esperado» derivable de ningún contrato (no existen en `campana.schema.json`).
  DSA se aproxima con `special_ad_categories` (lo único que el esquema trae hoy): es un proxy, no el
  campo `dsa` real que pide el Anexo A1 (pedido abajo). Cualquier diferencia es `ErrorBloqueado` (4)
  con el nombre del campo; no hay forma de forzarlo con `--live` porque `--modo live` sigue bloqueado.
- **A6 (tarifa y `n_anuncios` en `calcular_presupuesto`):** la firma cambió (rompe compatibilidad
  hacia atrás a propósito): ya no recibe `gasto_test_plan_minor` sino `tarifa_meta_bp`,
  `cpa_max_minor`, `cpa_esperado_minor` y `n_anuncios_paquete`, y calcula `n_anuncios`/`corte`/
  `validar`/`solo_refuta`/`facturado_plan` internamente (Anexo A3/§3.4). Los campos nuevos del
  resultado (`n_anuncios`, `k_corte`, `cpa_max`, `corte`, `validar`, `solo_refuta`, `tarifa_meta_bp`,
  `facturado_plan`, `techo_necesario_para_validar`) **no** van a `campana.presupuesto`
  (`additionalProperties: false`, solo los 9 de `CAMPOS_PRESUPUESTO_SCHEMA`): son diagnóstico para la
  tarjeta de gate y para `campana.economia`. Esto deja a `.claude/skills/d7-campanas-meta/scripts/d7.py
  presupuesto` (ajena) reimplementando lo mismo por su cuenta (ver «Pedidos»).
- **A8 (lista blanca de D7):** no existía ningún `agentes/plantillas_agentes/d7-{maker,qa}.md`, así
  que no había dónde declarar el permiso de D7. Se crearon ambos: el Maker solo lee Meta
  (`ads_get_*`/`ads_insights_*`, documentado; el runner automatizado de esta ola bloquea TODO
  `mcp__*` por diseño, `agentes/perfil.py construir_argv`) y tiene en `disallowedTools` cada patrón de
  escritura de Meta de `herramientas.yaml#escritura`; el QA no tiene `Bash` ni ningún `mcp__*`. Ninguno
  de los dos tiene `allow` para `meta_crear.py`/`meta_activar.py`/`pausar.py`/`subir_presupuesto.py`
  (son código post-QA, nunca algo que un Maker invoque) ni para `--modo live`.
- **A13 (`meta.lectura_viva`):** sin esquema propio en `contratos/` (pedido abajo), el objeto que
  produce no lleva `schema_version` (agregar uno sin que exista un esquema que versionar sería
  afirmar una validación que no corrió). Reutiliza `meta.activar.leer_estado_vivo` tal cual: el
  mismo código que ya lee el estado vivo para A5, ahora expuesto como artefacto propio para el QA.

## Pedidos

- A **B6** (`compliance`): `verificar_sello(clave_sello, ahora) -> Sello | None` con la forma exacta
  de `contratos/sello.schema.json`; hoy `meta.activar` lo recibe inyectado y el CLI lo simula leyendo
  un archivo (`--sello RUTA`).
- A **B8**/quien conecte infraestructura real: un `Transporte` real (stdlib) para que `--modo live`
  deje de estar bloqueado; hoy estos 4 CLI solo corren en `dry-run` o `fixture` (alcance explícito de
  esta entrega, ver «Decisiones»).
- A **CT**: `contratos/preflight.schema.json` fija `P01..P24` (sin `PX1-PX4` del Anexo A1 de
  `departamentos/08`); esas cuatro extensiones (DSA, tarifa de ubicación, riesgo por candidato,
  términos sensibles) hoy no tienen dónde vivir en el esquema. **A4 (ola 2, B5b): ya implementadas**
  como `meta.preflight.items_px`/`EntradasPX` (informe aparte, nunca en el objeto sellado); siguen sin
  esquema propio, así que `items_px` no es un artefacto versionado, solo diagnóstico para
  `lanzamiento.log`/la tarjeta de gate. Mismo pedido para **A13**: `meta.lectura_viva.generar()` no
  tiene `contratos/lectura_viva.schema.json` (se usa la forma de `traspaso` como referencia, sin
  afirmar cumplirla). También sigue pendiente `campana.economia.dsa` (copia de lo que D3 decida sobre
  el beneficiario/pagador): hoy `meta.activar.diferencias_config_viva` aproxima DSA con
  `special_ad_categories` porque es lo único que el esquema trae.
- A **B1** (`engine.limites`/`decision`): `meta.subir_presupuesto` asume que `cuenta.ultimo_aumento` y
  `cuenta.ediciones_recientes` los persiste quien llama (no hay almacén propio en `meta/`); confirmar
  que ese almacén vive en `datos`/`engine.estado` cuando exista.
- A **quien mantiene `.claude/skills/d7-campanas-meta/scripts/d7.py`** (ajena, no se toca esta noche):
  su subcomando `presupuesto` reimplementa `n_anuncios`/tarifa/`total_visible_max` con su propia
  aritmética y LUEGO llama a `meta.payloads.calcular_presupuesto` solo para el desglose diario/
  `spend_cap`. Ahora que `calcular_presupuesto` hace las dos cosas (A6), ese código queda duplicado:
  sugerido que la próxima pasada de esa skill delegue todo en `calcular_presupuesto` y borre su propia
  copia de la fórmula (debería dar los mismos números: mismo `techo_total`, mismo
  `total_visible_max`, mismo criterio de reducción de `n`).
- A **quien decida los nombres finales de `scripts/`**: `meta.nombres`, `meta.payloads`, `meta.preflight`,
  `meta.monitor` y `meta.lectura_viva` (A3/A13) todavía no tienen envoltorio de una línea en
  `scripts/` (se invocan con `python -m meta.<modulo>` directo); si se quiere el mismo patrón que los
  4 de arriba, faltan `scripts/meta_nombres.py`, `scripts/meta_payloads.py`, `scripts/meta_preflight.py`,
  `scripts/meta_monitor.py`, `scripts/meta_lectura_viva.py` (una línea cada uno) y sus entradas en
  `agentes/hooks/herramientas.yaml#bash_scripts`.
