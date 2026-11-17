# scripts/creativos — Código determinista de apoyo a D6 (creativos y anuncios)

Propósito: dar a la skill `d6-creativos` el código que el LLM no debe decidir (preflight, topes de
créditos, OCR contra claims, message match y riesgo por pieza), sin red, sin LLM y sin gastar
créditos (`departamentos/07-creativos.md` §4 y §10.3, `.claude/skills/d6-creativos/references/dependencias.md`).

Propietario y etapa: **B11** (ola 2), D6 (apoyo). Módulos: `preflight_d6.py`, `cost_preflight.py`,
`ocr_check.py`, `match_landing.py`, `riesgo_pieza.py`.

## CLI

```
.venv/bin/python -m scripts.creativos.preflight_d6 --oferta OF-202611-01 --raiz RAIZ \
    --navegador /ruta/a/chrome --fuente /ruta/a/fuente.ttf [--url-landing URL] [--ahora ISO] [--json]

.venv/bin/python -m scripts.creativos.cost_preflight --oferta OF-202611-01 --plan PLAN.json \
    --raiz RAIZ [--aplicar] [--ejecucion-id ID] [--json]

.venv/bin/python -m scripts.creativos.riesgo_pieza --piezas PIEZAS.json --nivel-oferta amarillo \
    [--nivel-max-lanzable amarillo-a] [--json]

.venv/bin/python -m scripts.creativos.match_landing --oferta OF-202611-01 --pieza PIEZA.json \
    --raiz RAIZ [--json]

.venv/bin/python -m scripts.creativos.ocr_check --ad-name c01-hueco_img_h1_v1 --copies COPIES.json \
    --fotogramas DIR_O_VIDEO --locale es-ES [--ffmpeg RUTA] [--json]
```

Ejemplos con los fixtures de este repo (dry-run por diseño: no publican ni gastan nada):

```
.venv/bin/python -m scripts.creativos.preflight_d6 --oferta OF-202611-01 \
    --raiz tests/fixtures/creativos/raiz_prueba --ahora 2026-11-09T07:00:00Z --json

.venv/bin/python -m scripts.creativos.riesgo_pieza --piezas tests/fixtures/creativos/piezas.json \
    --nivel-oferta verde --json
```

Salidas (convenciones §8): 0 ok · 2 uso · 3 validación (esquema, message match, OCR, riesgo
incoherente) · 4 preflight con algún ítem ROJO o NO_DISPONIBLE (`preflight_d6`) · 5 falta o se excede
un tope de créditos (`cost_preflight`) · 6 `ffmpeg` falló al correr (`ocr_check`).

## Entradas y salidas

* `preflight_d6.comprobar(raiz, oferta_id, ...) -> dict`: tabla `{items:[{id,estado,motivo}], semaforo}`.
  `estado` ∈ `VERDE`, `ROJO`, `NO_DISPONIBLE` (nunca verde sin comprobar). Con `--salida RUTA` escribe
  el reporte ahí (pensado como `06-creativos/preflight-d6.json`, la ruta de la spec §4 paso 1).
* `cost_preflight.evaluar_plan(...) -> dict`: por pieza, créditos cotizados + margen y si excede el
  tope de pieza; además el acumulado de la oferta contra `creditos_max_oferta`. Con `--aplicar` (y
  solo si no hay problemas) escribe cada pieza en `empresa/costos.jsonl` vía `engine.registro.costo`
  ANTES de que nada se envíe a generar (regla del flujo, spec §4 paso 6).
* `riesgo_pieza.evaluar_piezas(...) -> dict`: nivel/subnivel/veredicto por pieza
  (`scripts.nivel_riesgo.riesgo_de_candidato`) y su clasificación frente al nivel de la oferta
  (`coherente`, `falso_verde_bloqueante`, `mayor_revisar`, `indeterminado`) y frente a
  `limites.nivel_max_lanzable` si se declara.
* `match_landing.comparar(...) -> list[Diferencia]`: diferencias exactas de precio, moneda, garantía,
  marca y `claim_ids` entre la pieza, `oferta.json` y `05-landing/sitio/index.html`.
* `ocr_check.verificar(...) -> dict`: texto reconocido por fotograma, campos de `copies.json` que no
  coinciden y hallazgos de `compliance.lint_claims` (claims prohibidos del `locale`).

## Variables de entorno

Ninguna nueva: reutiliza las del núcleo (`FABRICA_ENTORNO`, `FABRICA_RAIZ`, `PREFLIGHT_HMAC_KEY`,
`FABRICA_FIRMA_PUBLICA`) a través de `engine.guard`/`engine.limites`/`engine.parametros`.

## Cómo probar

```
.venv/bin/python -m unittest discover -s tests/scripts -t . -p "test_creativos_*.py"
```

Fixtures en `tests/fixtures/creativos/`. `tests/scripts/test_creativos_*.py` reutiliza (solo lectura,
no se edita) `tests.engine.apoyo.crear_empresa`/`par_de_claves` para armar una raíz temporal con
`empresa/` ya verde y firmada (límites sellados, infraestructura firmada con HMAC de prueba), igual
que hacen las pruebas de `engine.guard`; cada prueba de `scripts.creativos` solo agrega lo propio de
la oferta (`mercado.json`, `oferta.json`, `05-landing/sitio/index.html`…) sobre esa base.

## Decisiones

1. **`preflight_d6` reutiliza `engine.guard.comprobar_live("generar_creativos", simulacion=...)`** para
   PAUSA, infraestructura y límites, en vez de copiar esas reglas (convenciones §9: "las
   comprobaciones viven en una sola función compartida"). Fuera de `produccion` llama con
   `simulacion=True` y un `TransporteFixture()` vacío (la operación `generar_creativos` no necesita
   transporte real: no tiene tope agregado ni acción de gate). El resultado de cada paso del guard se
   traduce a un ítem de la tabla; un paso que no se alcanza (porque uno anterior bloqueó) queda
   `NO_DISPONIBLE`, nunca `VERDE` por omisión.
2. **El cliente HTTP de "landing responde 200" es un parámetro inyectable sin implementación de red
   en esta entrega.** La noche de construcción prohíbe peticiones de red; sin un cliente inyectado el
   ítem queda `NO_DISPONIBLE` (nunca se inventa un `200`). **Pedido**: quien integre D7/D0 en vivo debe
   inyectar un cliente `https` SSRF-safe (reutilizando el lector de `scripts/modelado/enlaces.py`:
   `validar_destino` + `abrir_fijo`, que ya resuelven DNS y rechazan IPs no públicas) restringido a los
   hosts declarados en `ofertas/<id>/`.
3. **`cost_preflight` no repite PAUSA/infraestructura/entorno.** Asume que `preflight_d6` ya corrió
   (paso 1 del flujo) y solo repite lo que cambia pieza a pieza: los topes de créditos. Evitar la
   doble comprobación mantiene cada script enfocado en una responsabilidad y más fácil de probar.
4. **`creativos.margen_regeneracion_pct` no existe en `contratos/parametros.schema.json`** (el grupo
   `creativos` es `additionalProperties:false` con una lista fija de claves que no lo incluye).
   `contratos/**` es intocable para esta sesión. `cost_preflight.main` lo pide con
   `parametros.valor(...)` y por eso **falla cerrado con código 5 en cualquier raíz real hasta que CT
   amplíe el esquema** (MINOR, análogo a los grupos opcionales de CT-3). La aritmética del margen
   (`con_margen`) está probada por separado pasándole `margen_pct` explícito, para que quede
   verificada aunque el parámetro todavía no exista. **Pedido a CT**: agregar `margen_regeneracion_pct`
   (y, si se quiere, los mínimos de rúbrica R4/R9 y el factor «3» de `n_anuncios_max` que
   `references/dependencias.md` también pide) al grupo `creativos` de `parametros.schema.json`.
5. **`riesgo_pieza` no inventa un esquema de `matriz.json`.** `contratos/creativos.schema.json` 1.0.0
   no tiene `anuncios[].riesgo_pieza` (pedido ya registrado por la skill D6 en
   `docs/_historial/coordinacion-sesiones.md`); mientras tanto esta CLI acepta un archivo propio
   `{"piezas":[{"id","ejes"}]}` (ver ejemplo en `tests/fixtures/creativos/piezas.json`) en vez de leer
   un campo que no existe. Cuando el MINOR 1.1.0 llegue, quien integre puede alimentar `evaluar_piezas`
   directamente con `paquete.json["anuncios"]` sin tocar la función.
6. **`match_landing` lee atributos `data-*` del `<body>`, no texto formateado por `locale`.** Comparar
   contra una cadena como «19,90 €» exigiría una tabla de formatos por `locale` y sería frágil ante
   cambios de plantilla; los atributos máquina-legibles que ya escribe `landing.generar`
   (`data-precio-minor`, `data-moneda`, `data-garantia-dias`, ver `ofertas/_ejemplo/05-landing/sitio/index.html`)
   son la fuente exacta. La comparación de `claim_ids` es contra `oferta.json` (los permitidos por D3),
   no contra el HTML: la landing no lista `claim_id` por pieza.
7. **`ocr_check` no instala ni invoca Tesseract** (coherente con `references/dependencias.md`: «no hay
   OCR instalado»). El `Protocol` `MotorOCR` y el parámetro `motor` de `main()` dejan el adaptador real
   como una pieza inyectable para quien lo tenga disponible; sin uno, la CLI sale con 2 y dice por qué
   (nunca un verde falso). `verificar()`/`comparar_texto()` sí están probados con un motor falso.
8. **Decisión de la noche (fail-closed genérico):** ante cualquier dato de límites o parámetro
   ausente, los cinco scripts se niegan a avanzar (código 5) en vez de asumir un valor por defecto,
   siguiendo la regla de convenciones §3 y §9.

## Pedidos (no se editan desde aquí)

* **CT** (`contratos/parametros.schema.json`): agregar `creativos.margen_regeneracion_pct` (y, de
  paso, los demás `[HIPÓTESIS]` de `references/dependencias.md` §2 que hoy no tienen hogar en el
  esquema: mínimos de rúbrica R4/R9, factor «3» de `n_anuncios_max`).
* **CT** (`contratos/creativos.schema.json`): el MINOR 1.1.0 con `anuncios[].riesgo_pieza` ya está
  pedido por la skill D6; cuando exista, `riesgo_pieza.evaluar_piezas` puede alimentarse directo de
  `paquete.json` sin cambios de firma.
* **Quien integre D0/D7 en vivo**: inyectar en `preflight_d6.comprobar` un `cliente_get` real
  (SSRF-safe, solo `https` a los hosts de `ofertas/<id>/`) y, en `ocr_check.main`, un `MotorOCR` real.
* **Dueño**: fijar `creditos_max_pieza`, `creditos_max_oferta`, `max_budget_por_corrida_agente` y
  `locales_permitidos` en `empresa/limites.yaml` (hoy en `null`/vacío: ningún script de este paquete
  puede pasar de ROJO/5 contra la raíz real hasta entonces; es el comportamiento esperado, no un bug).
