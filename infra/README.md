# infra

Fundaciones: preflight de salud (`empresa/infra/estado.json`), kill switch de tres capas, latido
hacia el watchdog, descarga firmada, manifiesto de variables de entorno, verificación de dominio,
alta de oferta (N01b) y simulacro de las pruebas de aceptación A-1…A-12.

Propietario: **B8** (ola 1, continuado por **B8b** en una segunda sesión — construcción nocturna
2026-11-06 — tras un corte de herramientas de escritura a mitad de la primera). Dueño del
directorio: `infra/**` (salvo `infra/workers/fulfill/`, de **B7**), `scripts/preflight.py`,
`.github/**`, `infra/plantillas/`, `.env.example` (regenerado, nunca editado a mano).

## Módulos

- `preflight.py` — catálogo de 44 ítems (`infra/plantillas/preflight-items.yaml`), agregación del
  semáforo, firma HMAC y escritura de `empresa/infra/estado.json` (`infra_estado` 1.1.0). Sondas
  reales sin red ni credenciales de terceros: `K-01` (PAUSA), `P-01` (límites), `R-06` (centinela de
  persistencia), `C-09` (watchdog vía `Transporte` inyectado), `G-03` (gitleaks si el binario existe).
- `kill.py` — capa 1 del kill switch (`empresa/PAUSA` en tres sitios: archivo espejo, almacén del
  motor, KV del watchdog); mejor esfuerzo en las capas 2 (`meta.pausar`, inyectable) y 3 (watchdog).
  Dry-run por defecto; deliberadamente **no** pasa por `engine.guard.comprobar_live`.
- `latido.py` — construcción/firma/envío del latido hacia el watchdog y `evaluar_vencimiento`, la
  misma regla que debe reproducir `infra/workers/watchdog/src/logica.mjs` (ambas se prueban con los
  mismos vectores).
- `firma_servicio.py` — autenticación interna `X-Fabrica-Ts`/`X-Fabrica-Firma` (HMAC-SHA256),
  compartida con `infra/workers/{fulfill,watchdog,descarga}/src/hmac.mjs`.
- `transporte_http.py` — `TransporteUrllib`: implementación real (solo biblioteca estándar) del
  `Transporte` inyectable; nadie la usa en pruebas ni en esta construcción nocturna (sin red).
- `variables.py` **(B8b)** — lee `infra/plantillas/variables-entorno.yaml` y regenera `.env.example`
  (solo nombres y comentarios, nunca valores); `--check` falla (3) si están desincronizados.
- `dominio.py` **(B8b)** — verificación de un dominio en SOLO LECTURA (TXT por DNS-over-HTTPS,
  verificación en el portfolio de Meta); nunca compra ni escribe DNS; dice qué falta.
- `alta_oferta.py` **(B8b)** — nodo N01b: lista los 11 pasos de `infra/plantillas/alta-oferta.yaml`,
  los verifica en solo lectura (con verificadores inyectables; sin uno, "pendiente", nunca verde
  falso) y, solo con `--ejecutar` sobre una raíz de prueba, escribe `ofertas/<id>/infra/alta.json`.
  Incluye `calcular_limite_gasto_cuenta_meta` (la fórmula paramétrica del `spend_cap`, docs/07 §9.1).
- `simulacro.py` **(B8b)** — harness en serie de las pruebas de aceptación A-1…A-12 (docs/07 §9.3)
  contra fixtures; nunca da verde sin ejercitar código real (ver «Decisiones»).

## La máquina principal (`infra/maquina/`)

La iMac que queda siempre prendida corriendo todo y se maneja desde la laptop por Tailscale + Compartir
pantalla, con un vigilante que la devuelve a la red buena si el Wi-Fi se pasa a otra. Guía, incidente
y comandos (`verificar.sh`, `instalar.sh`) en [`maquina/README.md`](maquina/README.md).

## Workers (`infra/workers/`, Cloudflare, JS sin dependencias)

- `watchdog/` — *dead-man switch*: `POST /latido`, `GET /estado`, `POST /pausa`; SIN ruta de
  activación (cualquier otra ruta es 404/405; nunca `POST status=ACTIVE`).
- `descarga/` **(B8b)** — `GET /d/<sessionId>?token=…`: valida el enlace firmado por
  `infra/workers/fulfill/src/enlace.mjs` (formato EXACTO, reutilizado/duplicado), cuenta descargas en
  KV y entrega desde R2 (bindings `CONTADORES`, `BUCKET_PRODUCTOS`); vencimiento y cuota viajan
  DENTRO del token (nunca literales en este Worker: ver «Decisiones»).
- `fulfill/` — de **B7**; `descarga` solo lo consume en solo lectura (verificación del token).

## Plantillas (`infra/plantillas/`)

`preflight-items.yaml` (44 ítems), `variables-entorno.yaml` (manifiesto normativo de TODAS las
variables), `permisos-tokens.yaml`, `registro-verificacion-conexiones.yaml`,
`stripe-eventos-webhook.yaml`, `estado.ejemplo.json` (ilustrativo, no normativo) y
`alta-oferta.yaml` **(B8b)**: los 11 pasos de N01b con quién, cómo se comprueba e ítem de preflight.

## CLI con ejemplos (dry-run y con fixtures)

```bash
# Preflight (de B8)
python -m infra.preflight ejecutar --modo completo --salida /tmp/estado.json --json

# Kill switch (de B8)
python -m infra.kill activar --motivo "simulacro A-1" --raiz /tmp/prueba --json
python -m infra.kill verificar --raiz /tmp/prueba --json

# Latido (de B8)
python -m infra.latido evaluar --ultimo-latido 2026-11-09T07:50:00Z --ahora 2026-11-09T08:25:00Z --max-min 30

# Manifiesto de variables y .env.example (B8b)
python -m infra.variables generar --json
python -m infra.variables generar --check --json

# Verificación de dominio, solo lectura (B8b)
python -m infra.dominio verificar --dominio ejemplo.com --txt-esperado "meta-domain-verification=abc" \
    --fixture-dns tests/fixtures/infra/dns.yaml --json

# Alta de oferta, N01b (B8b)
python -m infra.alta_oferta listar --oferta OF-202611-01 --json
python -m infra.alta_oferta verificar --oferta OF-202611-01 --json
python -m infra.alta_oferta ejecutar --oferta OF-202611-01 --ejecutar --raiz /tmp/prueba --json   # solo en modo prueba
python -m infra.alta_oferta spend-cap --gasto-acumulado-minor 2000 --capital-anuncios-restante-minor 5000 \
    --suma-topes-test-en-curso-minor 1000 --json

# Simulacro A-1…A-12 (B8b)
python -m infra.simulacro ejecutar --raiz /tmp/prueba --ahora 2026-11-09T08:00:00Z --json
```

Códigos de salida: convenciones §8 (0 ok · 2 uso · 3 validación · 4 bloqueado · 5 límite · 6
externo), salvo `infra.simulacro ejecutar` (0 sin ROJO · 1 con algún ROJO, es un informe, no un
guardarraíl) y `infra.preflight ejecutar` (0 VERDE · 4 AMARILLO/ROJO).

Variables de entorno: ver `infra/plantillas/variables-entorno.yaml` (fuente normativa) y el
`.env.example` regenerado en la raíz del repositorio.

## Probar

```bash
.venv/bin/python -m unittest discover -s tests/infra -t .
node --test infra/workers/watchdog/test/*.test.mjs
node --test infra/workers/descarga/test/*.test.mjs
node --test infra/workers/fulfill/test/*.test.mjs   # de B7; descarga depende de su enlace.mjs
```

## Decisiones

### De B8 (primera sesión)

- El catálogo completo (44 ítems) y el motor de preflight están probados; las SONDAS reales solo
  cubren lo verificable sin credenciales ni red (`K-01`, `P-01`, `R-06`, `C-09`, `G-03`); el resto
  queda "no ejecutable" (ROJO si crítico, AMARILLO si no) a propósito: nunca VERDE por omisión.
- `infra.kill` NO pasa por `engine.guard.comprobar_live`: un kill switch debe poder actuar
  precisamente cuando algo ya está roto (límites incompletos, infra ROJO); exigirle los 7 pasos de
  `--live` invertiría su propósito.
- `infra.kill`/`infra.latido` usan `AlmacenNulo`/`EjecutorNulo` (Protocolos) para `engine.estado` y
  `meta.pausar` porque, al escribirse, esos módulos no existían todavía. **Nota de B8b**: en esta
  segunda sesión, `engine.estado`, `engine.orq` y `meta.pausar` SÍ existen (otra sesión los construyó
  en paralelo) — `infra.simulacro` los usa de verdad para las pruebas A-1…A-12, pero **no se tocó**
  `kill.py` ni `latido.py` para inyectarlos ahí: eso es un cambio de comportamiento de B8, no una
  corrección de un defecto, y queda fuera del mandato de esta sesión (ver «Pedidos»).

### De B8b (esta sesión)

- **`infra.alta_oferta`**: no existe un esquema propio en `contratos/` para `alta.json` todavía; se
  escribe con `schema_version: "0.1.0"` propio (sin validar contra `jsonschema`) en vez de bloquear
  la construcción esperando a CT. Dato faltante → se elige lo más seguro: cada paso sin verificador
  inyectado queda `pendiente_verificacion` (nunca `ok` por omisión) y `--ejecutar` exige
  `FABRICA_ENTORNO != produccion` (falla con `ErrorBloqueado`, código 4).
- **`calcular_limite_gasto_cuenta_meta`**: los tres agregados de cartera (`gasto_acumulado`,
  `capital_anuncios_restante`, `Σ topes_de_test_en_curso`) no tienen hoy una fuente propia (el
  portafolio vivo es de O0/B1, no existe todavía); la función los recibe EXPLÍCITOS, nunca los
  inventa ni los deriva de otro archivo. Redondeo hacia abajo (`ROUND_FLOOR`), igual criterio que
  `total_test_max` del validador: el resultado nunca puede superar lo que los agregados permiten.
- **Worker `descarga`**: el vencimiento y la cuota de descargas NUNCA son literales de este Worker:
  viajan DENTRO del token que firma `fulfill` (que a su vez los toma de variables de entorno
  paramétricas). `descarga` solo los LEE del payload verificado contra el reloj y el contador
  inyectados. Esto es intencional y coincide con `infra/plantillas/variables-entorno.yaml`, que ya
  no define variables de vencimiento/cuota propias para `descarga`.
- El contador de descargas en KV no es atómico (KV no tiene incremento atómico): dos descargas
  concurrentes de la misma sesión podrían, en el peor caso, superar la cuota por una unidad. Se
  documenta como riesgo (ver «Pedidos»/«Riesgos» del informe), no se resuelve en esta entrega.
- **`infra.variables`**: un nombre de variable con un espacio (p. ej. `"BUCKET_PRODUCTOS (binding
  R2)"`) se interpreta como un *binding* de Cloudflare, no como una variable de entorno: no genera
  línea `NOMBRE=` en `.env.example` (se configura en `wrangler.toml`). Un *placeholder* `<oferta_id>`
  se normaliza a `_EJEMPLO` (misma convención que el `.env.example` anterior).
- **`.env.example` real regenerado** con `python -m infra.variables generar` contra el manifiesto
  vigente (56 variables agrupadas); el archivo anterior (manual, con nombres ya retirados como
  `STRIPE_RESTRICTED_KEY_*` o `DOWNLOAD_SIGNING_SECRET`) queda reemplazado por completo.
- **`infra.dominio`**: usa DNS-over-HTTPS (RFC 8484, JSON) por un `Transporte` inyectable en vez de
  abrir un socket DNS propio (convenciones §11: sin red real en pruebas; y de noche, sin red real en
  ninguna corrida). Sin transporte inyectado, cada comprobación queda `pendiente` (nunca verde falso).
- **`infra.simulacro`**: de las 12 pruebas de aceptación, 7 ejercitan código REAL con fixtures
  (A-1, A-2 vía `engine.guard.comprobar_live`; A-3, A-4 vía `meta.pausar` real; A-8 vía
  `meta.cliente.ClienteMeta` real ante un 403; A-10 vía `infra.latido.evaluar_vencimiento` +
  `infra.preflight.sonda_c09_watchdog`; A-12 vía `engine.orq.reanudar` real) y 5 quedan `PENDIENTE`
  con un motivo explícito (A-6 ya cubierta por `node --test` del Worker `watchdog`, no reimplementada
  aquí; A-7, A-9, A-11 exigen credenciales o plataformas reales de la ola 3; A-5 es parcial: la
  decisión de pausar y la pausa efectiva SÍ se verifican, el envío de alertas por los dos canales —
  que hace el Worker `watchdog` en JavaScript— no tiene puente desde este harness de Python).
- **CI** (`.github/workflows/ci.yml`): sin secretos, `permissions: contents: read` a nivel de
  workflow; corre `validar_esquemas`, `test_all.sh`, `lint.sh`, `lint_estatico` y
  `agentes.sonda_hooks`. `python-version: "3.13"` y `node-version: "22"` son `[VERIFICAR]`: el repo
  fija 3.15/v26, que `actions/setup-python`/`actions/setup-node` no ofrecían al escribir esto; el job
  de `gitleaks` usa la acción pública `gitleaks/gitleaks-action@v2` con `continue-on-error: true`
  hasta confirmar su licencia para repos privados (no usa ningún secreto tal como está).

## Pedidos

- **A CT**: un esquema `alta.schema.json` para `ofertas/<id>/infra/alta.json` (hoy `infra.alta_oferta`
  escribe con `schema_version: "0.1.0"` propio, sin contrato).
- **A B1 o quien integre**: decidir si `infra.kill`/`infra.latido` deben inyectar ahora
  `engine.estado`/`meta.pausar` reales en vez de `AlmacenNulo`/`EjecutorNulo` (ya existen, construidos
  en paralelo); no se tocó en esta sesión para no exceder el mandato de B8b (corregir defectos, no
  rediseñar lo de B8).
- **A quien reciba el watchdog real**: considerar mover el contador de descargas de `descarga` a un
  Durable Object (atómico) si la cuota exacta importa; hoy es KV (no atómico, ver «Decisiones»).
- **A quien active CI de verdad**: confirmar la licencia de `gitleaks-action` para este repositorio
  (público/privado) antes de quitar `continue-on-error`, y fijar `python-version`/`node-version`
  reales (3.15/v26) cuando `setup-python`/`setup-node` los ofrezcan.
- **De B8 (sigue abierto)**: capa 2 del kill switch (`meta.pausar`, ya existe) no estaba inyectada en
  `infra.kill` al escribirse; `infra.simulacro` demuestra que FUNCIONA por fixture, pero `kill.py`
  sigue con `EjecutorNulo` por defecto — decisión de integración, no de B8b.
