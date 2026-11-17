# compliance

Control determinista de cumplimiento (X1): lint de claims, lints de HTML, carga autosellada de
reglas sensibles, y el sello de X1 (emisión y verificación justo antes de usarlo).

- **Propietario:** B6 (ola 1) + B6b (ola 2) + B6c (ola 2, continuación nocturna 2026-11-06, D-04:
  `compliance/salud.py`). **Alcance de esta entrega:** `compliance/**`, `scripts/lint_claims.py` y
  `scripts/html_checks.py` (envoltorios) y el esqueleto de `empresa/compliance/`. Criterios de
  aceptación: B0-11 (parcial, ver «Decisiones»), B0-13. La ola 2 amplió cobertura de locale/categoría
  (D-02), la exclusión de `claves_lista_negra` (Decisión 1b), el cargador aditivo de
  `empresa/compliance/terminos_sensibles/` (D-02b), `--etapa D5` incluyendo el sitio servido (D-02c)
  y dos checks de `html_checks` (escasez fija, plantilla sin reemplazar); midió contra
  `.claude/skills/x1-compliance/scripts/correr_evals.py codigo` (solo lectura, oráculo de otra
  sesión). **B6c** cerró lo único que quedaba pendiente de D-04: `compliance.salud`
  (`x1_salud`/`x1_pausa`), con `.claude/skills/x1-compliance/scripts/regla_salud.py` y sus 21 series
  (`evals/salud/series.json`) como oráculo de paridad.
- **Falla cerrado:** ante regla alterada, locale desconocido, archivo ilegible, firma que no
  verifica o sello vencido, la respuesta es bloquear (nunca se asume que algo no comprobado está
  bien).

## Módulos

| Módulo | Qué hace |
|---|---|
| `reglas.py` | Carga y autentica `reglas_sensibles.yaml` (autosellado por hash): `cargar_reglas()`, `categorias_de_locale()`. Si el archivo fue editado sin recalcular `hash_contenido`, **el lint no corre** (docs/06 N09). Ola 2: `cargar_terminos_adicionales()` + `combinar_categorias()` (D-02b, aditivo y sin poder debilitar); `Reglas.claves_lista_negra` y `Reglas.revision_nativa`. |
| `hallazgos.py` | `Hallazgo` compartido (nivel verde/amarillo/rojo) y `peor_nivel()` (el semáforo de un conjunto). |
| `lint_claims.py` | `lint_texto`, `lint_artefacto` (recorre cualquier JSON/YAML, excluye `claves_lista_negra`), `lint_claims` (CLI-ready sobre un archivo), `extraer_textos`. `--oferta --etapa D5` ya incluye `05-landing/sitio` (D-02c). |
| `html_checks.py` | `verificar_html`: casillas premarcadas, píxel antes/sin condición de consentimiento, enlaces legales (ausentes o rotos), temporizadores sin fecha verificable, escasez/urgencia fija sin marcador verificable y texto de plantilla sin reemplazar (ola 2); `verificar_metadatos`: términos sensibles en dominio/rutas/`title`/`og:*`/eventos/parámetros (D01). |
| `sellar.py` | `sellar()` (puro, no escribe) + CLI que sí escribe con `--live`. Solo sella con lint sin ROJO y QA `PASS`/`PASS_CON_NOTAS`. |
| `verificar.py` | **`verificar_sello(clave_sello, ahora) -> dict \| None`**: la firma congelada que esperan `meta.activar` y `landing.desplegar` (nunca lanza). `verificar_sello_o_fallar(...)` y la CLI añaden el chequeo de uso (TOCTOU) para uso humano. |
| `salud.py` (B6c, D-04) | `decidir(estado, params) -> dict`: traducción literal a parámetros reales del oráculo `regla_salud.py` (cuenta/calidad de Meta, avisos de Stripe, rechazos, disputas, reembolsos, frescura; la más grave manda). `construir_senal_pausa(...)`: arma (sin escribir) un artefacto con la forma de `contratos/senal_pausa.schema.json` a partir de un resultado de `decidir`. `escribir_senal_pausa(datos, destino)`: escritura atómica en la ruta que indique quien llama (nunca una ruta fija: ver «Decisiones» #17). `validar_estado`, `cargar_parametros_salud`. **No pausa nada, no llama a Meta/Stripe, no lee credenciales; reanudar es siempre humano.** |

## CLI

```bash
# Lint de un texto/artefacto (dry-run siempre; es una lectura)
.venv/bin/python -m compliance.lint_claims --archivo ofertas/_ejemplo/03-oferta/oferta.json --locale es-ES --macro-nicho salud --json
.venv/bin/python -m compliance.lint_claims --oferta OF-202611-01 --etapa D3 --locale es-ES --json   # 0 verde/amarillo, 3 si hay ROJO

# Lint de HTML servido o de sitio/<pagina>.html (envoltorio: scripts/html_checks.py)
.venv/bin/python -m compliance.html_checks --archivo 05-landing/sitio/index.html --locale es-ES --macro-nicho salud --json

# Sellar (dry-run por defecto: imprime el sello, no escribe)
.venv/bin/python -m compliance.sellar --oferta OF-202611-01 --etapa-objetivo D3 \
  --artefacto 03-oferta/oferta.json --dictamen qa/x1-d3-v1.json --locale es-ES --json
# --live (prueba, firma HMAC de SELLO_X1_CLAVE o --clave-privada; produccion exige --clave-privada Ed25519)
SELLO_X1_CLAVE=clave-de-prueba .venv/bin/python -m compliance.sellar --oferta OF-202611-01 --etapa-objetivo D3 \
  --artefacto 03-oferta/oferta.json --dictamen qa/x1-d3-v1.json --locale es-ES --raiz /tmp/prueba --live --json

# Verificar un sello justo antes de usarlo (solo lectura; sale 4 si no es válido/vigente)
.venv/bin/python -m compliance.verificar --hash sha256:<hex> --raiz /tmp/prueba --json

# Salud de cuentas (B6c, D-04): decide, nunca pausa (envoltorio: scripts/x1_salud.py)
.venv/bin/python -m compliance.salud evaluar --estado empresa/compliance/salud_actual.json --json
# Propuesta de senal_pausa.json: dry-run por defecto (imprime el plan, no escribe)
.venv/bin/python -m compliance.salud pausa --estado empresa/compliance/salud_actual.json \
  --oferta OF-202611-01 --salida ofertas/OF-202611-01/10-postcompra/senal_pausa_x1.json --json
# --aplicar escribe de verdad (siempre dentro de ofertas/<oferta>/; convenciones §9)
.venv/bin/python -m compliance.salud pausa --estado empresa/compliance/salud_actual.json \
  --oferta OF-202611-01 --salida ofertas/OF-202611-01/10-postcompra/senal_pausa_x1.json --aplicar --json
```

Con `--json`, stdout es una línea `{"ok","modo","codigo","datos","avisos"}` (docs/06 §4.1); la traza
va a stderr sin secretos.

## Códigos de salida

0 correcto (verde/amarillo, o sello vigente) · 2 uso (argumentos, `--oferta` sin `--etapa`,
`--dictamen`/`--artefacto` inexistentes) · 3 validación (semáforo **rojo**; esquema de reglas o
sello inválido; reglas alteradas) · 4 bloqueado (`compliance.verificar`/`verificar_sello_o_fallar`:
sin sello, vencido, firma inválida, uso que no coincide; `compliance.sellar`: lint ROJO o QA sin
PASS) · 5 falta `compliance.vigencia_dictamen_dias` en `parametros.yaml`.

`compliance.salud` (B6c): 0 correcto (`evaluar` sale 0 aunque la acción propuesta sea `PAUSA`: es
una lectura, informa, no bloquea su propia salida) · 2 uso (`--estado` inexistente o ausente,
`--salida` fuera de `ofertas/<oferta>/`, `--raiz`/`--ahora` con `FABRICA_ENTORNO=produccion`) · 3
dato inválido (`--estado` con forma incorrecta o campo obligatorio ausente; un `senal_pausa`
construido que no cumple su esquema) · 5 falta un parámetro de `compliance.*`/`salud_operativa.*`
en `parametros.yaml` o `limites.ratio_disputas_pausa` (hoy `null`: el dueño no lo fijó, D-04).

## Entradas y salidas

| Archivo | Quién lo escribe | Contrato |
|---|---|---|
| `compliance/reglas_sensibles.yaml` | el dueño/X1 a mano + `compliance.reglas.resellar` (herramienta de mantenimiento, no una CLI pública) | formato propio, autosellado por `hash_contenido` |
| `empresa/compliance/sellos/<hex>.json` | `compliance.sellar --live` (único escritor) | `contratos/sello.schema.json` |
| `--estado` de `compliance.salud` (p. ej. `empresa/compliance/salud_actual.json`) | lo escribe otra pieza (sin herramienta de lectura hoy: `[SUPUESTO]`, ver «Decisiones» #17) | **sin esquema propio todavía** (D-04): `{account_status, calidad_cuenta_meta?, calidad_edad_dias?, stripe_aviso?, rechazos?[{hace_dias,tipo,revertido}], pagos_30d, disputas_30d, reembolsos_n, reembolsos_pct, edad_salud_h}` |
| `<cualquier ruta bajo ofertas/<oferta>/>` (nunca fija) | `compliance.salud pausa --aplicar` (único escritor de esa ruta puntual) | `contratos/senal_pausa.schema.json` |

## Variables de entorno

`SELLO_X1_CLAVE` (HMAC de prueba/servicio a servicio; **nunca** en el entorno de los agentes, A5
H7), `FABRICA_FIRMA_PUBLICA` (verificación Ed25519, ya en `.env.example` de B8),
`FABRICA_ENTORNO`/`FABRICA_RAIZ` (comunes). Ninguna variable nueva que no estuviera ya prevista.

## Cómo probar

```bash
.venv/bin/python -m unittest discover -s tests/compliance -t .
```

131 pruebas (74 de las olas 1-2 + 53 de `test_salud.py`, B6c), sin red (`socket.socket` bloqueado en
`setUp`). `test_salud.py`: paridad con el oráculo sobre las 21 series de
`evals/salud/series.json` (cargado con `importlib` desde el `.py` real, no copiado: si el oráculo
cambia, la prueba de control `test_el_oraculo_coincide_con_sus_propias_series` avisa antes que la de
paridad); una pareja tope-exacto/tope+1 por cada uno de los 13 umbrales de `regla_salud.CLAVES_PARAMS`
(convenciones §11); `validar_estado` (campo ausente, tipo de rechazo desconocido, aviso de Stripe
desconocido, entero negativo); `construir_senal_pausa` contra `contratos/senal_pausa.schema.json`
(verde/amarillo/rojo, `ninguno/disputas/reembolsos/otro`, `sintetico`); `ParametroFaltante`/
`ErrorLimite` (código 5) con `empresa/limites.yaml` REAL (`ratio_disputas_pausa: null` hoy: el
dueño no lo fijó); la CLI `evaluar`/`pausa` (dry-run que no escribe, `--aplicar` que sí, y las dos
rutas de `ErrorUso`: fuera de `ofertas/<oferta>/` y con `--raiz`/`--ahora` en producción). Corpus
adversarial de claims (salud y finanzas, es-ES/en-US, más garantías/urgencia/prueba social) en
`tests/compliance/test_lint_claims.py`; corpus de ola 2 (it-IT/pl-PL/ro-RO/fr-FR/de-DE/es-AR/es-MX +
`relaciones`, con el `--locale` real, no el proxy del oráculo) en `PruebaCorpusOla2Locales`;
`claves_lista_negra` (clave exacta no lintea, misma frase en clave parecida o array anidado distinto
sigue ROJO) en `PruebaClavesListaNegra`; `--etapa D5` incluye el sitio en
`PruebaRutaOfertaEtapaD5IncluyeSitio`; reglas alteradas y D-02b (`cargar_terminos_adicionales`,
`combinar_categorias`, sin poder debilitar una regla base) en `test_reglas.py`; las 4 mutaciones de
HTML que le tocan a B6 dentro de B0-11 más escasez fija y plantilla sin reemplazar (con su caso
verde: "todo"/"ejemplo" en minúscula no disparan) en `test_html_checks.py`; sello vencido/alterado/
sin firma y el camino Ed25519 real (`ssh-keygen`) en `test_sellar_verificar.py`.

Medición independiente (oráculo de otra sesión, solo lectura):
`.venv/bin/python .claude/skills/x1-compliance/scripts/correr_evals.py codigo`. Antes de la ola 2:
`it-IT/pl-PL/ro-RO/fr-FR/de-DE/es-AR/es-MX` fallaban cerrado (ningún locale propio), 10/62 rojos del
corpus adversarial es-*/en-* detectados (proxy es-ES/en-US), 1 FALSO POSITIVO (`comida sana`, L08) y
8/14 sembrados sin cazar. Después: es-ES 17/18 (94 %) y es-AR 18/18 (100 %) de las frases rojas del
corpus adversarial (≥ 90 % pedido), 50/52 rojos es-*/en-* totales, 0 FALSOS POSITIVOS, 8/14 sembrados
detectados (los 4 restantes son BRECHA declarada: requieren criterio de dominio — afiliados
financieros, tasas históricas como expectativa, reseñas con cifra, slugs de URL — que no se puede
cazar con regex sin abrir un hueco en el corpus verde; 2 más quedan "SIN REGLAS" por una limitación
del propio oráculo, ver «Riesgos»).

## Decisiones (fail-closed ante dato faltante o conflicto de documentos)

1. **Autosellado de `reglas_sensibles.yaml` por hash, no por `reglas_version` firmada aparte.**
   Docs/06 N09 dice "`reglas_claims.yaml` ≠ `reglas_version` firmada → el lint no corre" pero no hay
   un esquema de contrato para ese archivo (es interno de X1, no de `contratos/`). En vez de inventar
   una firma externa, el archivo se autentica como un sello: `hash_contenido` = hash del resto del
   archivo (`engine.comun.hash_objeto`, igual que un sello real). Editarlo sin recalcular ese campo
   (`compliance.reglas.resellar`, herramienta manual) lo invalida: `ErrorValidacion` (3), el lint no
   corre. Más simple de verificar que una firma Ed25519 para un archivo que el propio X1 edita.
2. **`macro_nicho="dinero"` del backbone se mapea a la categoría `finanzas` del archivo.** El plan
   de esta entrega dice "por locale (salud y finanzas)"; el enumerado de `macro_nicho` (backbone)
   usa `salud, relaciones, dinero`. Se documenta el mapeo en `compliance.reglas.MACRO_A_CATEGORIA`
   en vez de renombrar el enumerado compartido (que no es mío: `contratos/comunes.schema.json`).
   `"relaciones"` no tiene categoría propia todavía (pedido abajo); solo le aplican las reglas
   `generales`.
3. **Sin `macro_nicho`, se miran TODAS las categorías del locale.** Ante duda (etapa que no sabe
   aún el macro_nicho, o que cubre varios) se prefiere sobre-detectar a dejar pasar un claim de
   salud en una oferta clasificada como "dinero" por error.
4. **Alcance de B0-11: 4 de las 8 mutaciones son mías.** `html_checks.verificar_html` cubre
   `legal ausente`, `enlace roto`, `píxel en <head> sin condición` y `casilla premarcada` (más
   términos sensibles en `title`/`og:*`, D01, que no es una de las 8 pero es parte del encargo).
   Precio/moneda/garantía distintos entre `oferta`/`checkout`/HTML y datos de salud en
   `tracking.json` son del L1 de `landing.generar/validar` (B4), que ya construyó su propio oráculo
   (`tests/contratos/aplicar_mutacion_landing.py`) sin depender de este paquete; no se duplica ese
   esquema aquí.
5. **`_enlaces_legales` distingue "ausente" de "roto" por `data-legal="<clave>"`, con fallback al
   fragmento de ruta.** Sin un atributo estable, un `href="#"` es indistinguible de "no hay enlace"
   (ambos no contienen el fragmento canónico). Si la landing real no usa `data-legal`, esta función
   degrada a reportar "ausente" también para los rotos (sigue siendo ROJO, solo cambia la etiqueta).
6. **Un píxel gateado por su propia condición JS inline cuenta como "guardado".** El patrón real
   descrito en docs/07 (banner propio que inyecta el script del píxel solo si
   `consentimiento.aceptado`) pone el `<script>` del píxel DENTRO de un `if` que menciona
   "consentimiento" en el mismo bloque, no en un script separado antes/después. Exigir
   `type="text/plain"`/`data-consent` habría marcado ROJO ese patrón correcto (falso positivo).
7. **`sellar()` es puro (no escribe); la CLI escribe solo con `--live`.** Igual que el resto de la
   fábrica (dry-run por defecto, convenciones §9): sin `--live` se ve el sello completo (firmado con
   una clave de prueba) sin tocar `empresa/compliance/sellos/`.
8. **Dry-run de `sellar` firma con una clave de relleno (`CLAVE_DE_PRUEBA`), no deja `firma` vacía.**
   `sello.schema.json` exige `firma`; dejarla fuera habría obligado a una forma distinta solo para la
   vista previa. La vista previa nunca se escribe ni se puede verificar con una clave real.
9. **`verificar_sello(clave_sello, ahora) -> dict | None` es la firma pública principal** (coincide
   con el pedido de `meta/README.md` y el comentario de `meta/activar.py`): resuelve la raíz con
   `engine.comun.raiz()` y las claves desde el entorno, nunca lanza. `verificar_sello_o_fallar` (que
   SÍ lanza y admite `--artefacto-sha256`/`--object-ids` explícitos) es para la CLI humana; no es lo
   que se inyecta en `meta.activar`.
10. **Reusa `scripts.validar_esquemas.payload_firma`/`problemas_firma`/`problemas_uso_sello` tal
    cual (CT), no los reimplementa.** Consecuencia observada en las pruebas: fuera de producción,
    una firma HMAC bien formada pero SIN una `SELLO_X1_CLAVE` para contrastarla pasa por forma (no
    es una brecha: producción exige Ed25519 igual, y HMAC es explícitamente "solo pruebas/servicio a
    servicio", convenciones §5).

**Ola 2 (B6b, 2026-11-06, continuación nocturna):**

11. **`claves_lista_negra` excluye por nombre de clave EXACTO, a cualquier profundidad — no por
    ruta absoluta.** `claims_prohibidos` vive en `oferta.promesa.claims_prohibidos` y
    `claims_a_evitar` en `oferta.riesgo.claims_a_evitar` (rutas distintas, mismo propósito): exigir
    una ruta absoluta habría obligado a listar cada ruta posible por esquema. El riesgo (que alguien
    "blanquee" un claim real metiéndolo en una clave con ESE nombre exacto en un lugar inocuo) se
    cierra con la comprobación de fuga: la MISMA frase, textual, en cualquier OTRA clave o array del
    mismo artefacto sigue dando ROJO (`lista_negra:fuga`). Solo tres claves, declaradas en el propio
    archivo (`claves_lista_negra`), nunca a ciegas: `claims_prohibidos`, `claims_a_evitar` y, desde la
    petición de S-C (2026-11-06), `campos_prohibidos` (`tracking.json › datos_sensibles`: enumera los campos
    que NO se envían a Meta; mismo criterio y mismas pruebas sembradas).
12. **D-02b (`empresa/compliance/terminos_sensibles/<locale>.yaml`) es aditivo por construcción, no
    por disciplina.** `combinar_categorias()` solo UNE listas de patrones; no hay ninguna operación
    de "quitar" o "mover a un nivel más débil" en su API. Si el archivo del Maker de X1 repite un
    patrón que la base ya tiene en OTRO nivel, se ignora y se informa (nunca se mueve lo que ya
    existe); si lo repite en el MISMO nivel, es un no-op silencioso. `categorias_de_locale()` sigue
    siendo pura por defecto (`incluir_adicionales=False`, lo que esperan las pruebas que inspeccionan
    solo la base); `lint_texto`/`verificar_metadatos` la llaman con `incluir_adicionales=True`.
13. **`revision_nativa: {it-IT, pl-PL, ro-RO, fr-FR, de-DE}: false` vive en el propio archivo, no en
    código.** Son locales sin hablante nativo que los revise (`preguntas-abiertas.md`); el léxico es
    `[HIPÓTESIS]`, deliberadamente amplio (prefiere falso positivo). `lint_claims.main`/
    `html_checks.main` añaden un aviso en `"avisos"` cuando se usa uno de estos locales: la señal
    para "aún no confiar en esto para bloquear sin revisión humana" viaja con la respuesta, no solo
    en un comentario que nadie lee en modo `--json`.
14. **El proxy `LOCALE_REGLAS = {"es": "es-ES", "en": "en-US"}` del oráculo (de otra sesión, solo
    lectura: `.claude/skills/x1-compliance/scripts/correr_evals.py`) prueba TODO texto "es-\*"
    (es-AR, es-MX…) contra el ruleset de `es-ES`, y no tiene entrada para "it"/"pl"/"ro"/"fr"/"de" en
    absoluto.** Esto tiene dos consecuencias que documento para que no se lean como un defecto del
    código: (a) `locales.es-ES` de `reglas_sensibles.yaml` incluye a propósito las formas de voseo
    (perdé, ganá, curá…) y de slang mexicano, ADEMÁS de sus propias entradas `es-AR`/`es-MX` (que sí
    se usan cuando se pasa `--locale es-AR`/`es-MX` explícitamente, sin pasar por el proxy); (b) por
    diseño del oráculo, `it-IT`/`pl-PL`/`ro-RO`/`fr-FR`/`de-DE` SIEMPRE se reportan como "sin reglas
    de locale" en `correr_evals.py codigo`, aunque el código SÍ tenga reglas reales para esos cinco
    locales (verificable con `--locale it-IT` directo, o con `PruebaCorpusOla2Locales` en
    `tests/compliance/test_lint_claims.py`, que no pasa por el proxy). Pedido abajo.
15. **El bug de pluralización `"X?"` (`meses?`, `lugares?`, `unidades?`, `dólares?`) se corrigió a
    `"X(es)?"` donde el plural agrega "es", no solo "s".** `"meses?"` en regex significa literalmente
    "mese" + una "s" opcional: NUNCA matchea el singular real "mes" (3 letras, sin "e" final). Costó
    casi la mitad de la cobertura de `peso-plazo`/`urgencia-falsa` hasta que se aisló con pruebas
    directas del patrón (no solo contra el oráculo). Revisar cualquier patrón nuevo con esta forma.
16. **Las 4 "BRECHA" restantes de los sembrados (afiliado financiero, tasa histórica como
    expectativa, reseña "verificada" con cifra, slug de URL con término sensible) se dejan
    declaradas, no se fuerzan con regex.** Cada una necesita o bien una lista cerrada de dominios de
    afiliados/comparadores (no existe, no es dato de X1) o arriesga un patrón tan amplio (p. ej. la
    palabra suelta "deuda" o "diabetes" en cualquier URL) que abriría un hueco en el corpus verde
    (presupuestos, guías de deudas, calendarios fiscales legítimos SÍ mencionan "deuda"/"crédito").
    Spec: "lo que solo puede cazar el QA con criterio queda como BRECHA declarada, no se fuerza con
    reglas que bloqueen lo legítimo".

**Ola 2, B6c (2026-11-06, D-04: `compliance/salud.py`):**

17. **`senal_pausa.json` se escribe SOLO en la ruta que indique quien llama, nunca en
    `10-postcompra/senal_pausa.json` por defecto.** Esa ruta canónica ya tiene un escritor propio:
    `postcompra.metricas.escribir_senal_pausa` (B7, construido en esta misma noche), que cubre
    disputas y reembolsos y es lo único que `engine.d8._procesar_senal_pausa` lee hoy. Si
    `compliance.salud pausa --aplicar` escribiera ahí por defecto, pisaría el artefacto de B7 en
    cualquier corrida donde los dos detecten algo el mismo día. En vez de inventar una fusión (no es
    mía: decisión del motor/integración), la CLI exige `--salida` explícito, validado contra
    `contratos/senal_pausa.schema.json` y contra "cae dentro de `ofertas/<oferta>/`" (`ErrorUso`, 2),
    y deja la integración con D8 como pedido (ver abajo). Mientras no se integre, `compliance.salud`
    es utilizable hoy mismo para decidir y para alimentar el dossier/dashboard de X1.
18. **El contrato `senal_pausa.schema.json` es más angosto que las causas reales de X1.** Su
    `motivo` solo distingue `disputas`/`reembolsos` de `otro`; su `accion_solicitada` solo tiene
    `ninguna/alertar/pausar`, sin un escalón para "congelar un ángulo" o "congelar una hoja" (que no
    implican pausar la oferta activa, solo bloquear lanzamientos nuevos). `compliance.salud` mapea
    cualquier acción distinta de `seguir` a `accion_solicitada="pausar"` (más conservador que
    `alertar`) y todo lo que no sea disputas/reembolsos a `motivo="otro"`; el detalle fino
    (`congelar_angulo` vs. `congelar_hoja` vs. `pausar_oferta` vs. `PAUSA`, y el `alcance`) viaja en
    `datos.decision` de la salida de la CLI, no en el artefacto del contrato. Pedido a CT abajo.
19. **`muestra_suficiente` del artefacto exige las DOS muestras** (`pagos_30d >=
    disputas_muestra_min_pagos` Y `reembolsos_n >= reembolsos_n_min`), no solo la que disparó la
    decisión. El campo es uno solo para dos métricas (disputas y reembolsos) que `decidir` evalúa
    por separado: ante la duda, se prefiere subestimar la confianza (`false`) a sobreestimarla.
20. **`motivo_ganador`** (interno, no es parte del contrato) es el motivo de la ÚLTIMA escalada que
    de verdad subió la severidad de `accion` (no de cualquier condición que se probó), a diferencia
    del oráculo (`regla_salud.py`), cuyo `motivos` acumula TODO lo que pasó por `subir()` aunque no
    haya cambiado `accion`. La diferencia no afecta la paridad (`accion`/`alcance`/`alertas`/
    `lanzamientos_bloqueados` son idénticos): es solo para elegir un `motivo` único y determinista
    para el artefacto cuando varias causas coinciden (`SAL-21`: rechazo de pieza + disputas → gana
    disputas, que es la causa real de `pausar_oferta`).
21. **El estado de entrada (`--estado`) es `[SUPUESTO]`: no tiene esquema en `contratos/`** (no hay
    herramienta de lectura de `calidad_cuenta_meta` ni `account_status` en este entorno, igual que
    dice `references/salud-de-cuentas.md`). `validar_estado` hace de esquema de hecho (campos
    obligatorios, tipos, enumerados) y falla cerrado (`ErrorValidacion`, 3) ante cualquier forma
    rara; no inventa un esquema JSON porque ese archivo lo define quien lo produzca (D0/F1/el dueño,
    pedido abajo).
22. **No se construyó el sello de recolección (VC-01…16, D-08):** fuera de alcance explícito de este
    encargo (depende de D-07d, corrección de contratos pendiente de CT).

## Pedidos (cambios que necesito de otros componentes; no los edité)

- **B4 (`landing`):** `landing/desplegar.py::_sello_vigente_para` hoy solo comprueba esquema/hash/
  vigencia a mano (dice explícitamente "la verificación criptográfica... es de `compliance.verificar`,
  B6, aún no construido"). Ya existe: `compliance.verificar.verificar_sello(clave_sello, ahora)`.
  Cuando se integre, sustituye esa función interna.
- **B5 (`meta`):** `meta/activar.py` ya está preparado para recibir `verificar_sello` inyectado con
  esta firma exacta (`meta/README.md` «Pedidos»). Listo para conectar.
- **CT (`contratos`):** `qa.schema.json` no tiene un campo para citar el `reglas_version` de
  `compliance/reglas_sensibles.yaml` usado en el lint de una etapa (solo `sello.schema.json` lo
  tiene). Hoy `lint_claims` lo devuelve en `ResultadoLint` pero no hay dónde anotarlo en el QA mismo.
- **X1 (forja de skills):** categoría `relaciones` ya tiene léxico propio (es-ES/en-US/es-AR/es-MX/
  it-IT/pl-PL, `[HIPÓTESIS]`, pedido original de D-02 §B de `dependencias.md`); sigue sin ejemplos
  reales rechazados por Meta/Stripe para calibrarla (D-10b). Pedido nuevo: `LOCALE_REGLAS` en
  `.claude/skills/x1-compliance/scripts/correr_evals.py` (línea ~39) solo mapea `{"es": "es-ES",
  "en": "en-US"}`; si se le agregan `"it": "it-IT", "pl": "pl-PL", "ro": "ro-RO", "fr": "fr-FR", "de":
  "de-DE"}` (y, si se quiere medir sin proxy, usar `variante` en vez de `loc` en el `lint_texto`
  interno), el oráculo dejaría de reportar "sin reglas de locale" para los cinco locales que esta
  entrega ya cubre en código (ver Decisión 14). No lo edité: es de otra sesión y de solo lectura.
- **B9 (`agentes/hooks/herramientas.yaml`):** `bash_scripts["scripts/lint_claims.py"].flags` solo
  tiene `["--archivo", "--oferta", "--etapa", "--locale"]`; falta `--macro-nicho` y `--json` (el CLI
  real ya los admite desde la ola 1). `scripts/html_checks.py` (nuevo en esta entrega) no está en la
  allowlist: necesitaría una entrada `"scripts/html_checks.py": {flags: ["--archivo", "--locale",
  "--macro-nicho", "--reglas", "--json"]}`. Los tres scripts de la skill X1
  (`.claude/skills/x1-compliance/scripts/{nivel_ejes,validar_dictamen,ngrama_copia}.py`) tampoco
  están; no son míos, solo lo anoto para quien pueda tocar ese archivo.
- **D4/producto, D0/infra:** `04-producto/respaldo/{afirmaciones.jsonl, fuentes/}` y
  `empresa/infra/perfil_stripe.yaml` (D-03c de `dependencias.md`) no existen; no bloquean este lint
  pero los necesitará el futuro `compliance.salud`/sello de recolección.
- **S-A/dueño:** matriz país×nivel, las 30 líneas rojas aprobadas y el conjunto de retención (D-01d,
  D-05, D-14) siguen pendientes; no son de este componente.
- **Dueño (D-04):** `empresa/limites.yaml: ratio_disputas_pausa` sigue en `null`. Mientras no se
  fije, `compliance.salud` (y `postcompra.metricas`) fallan cerrado con código 5 en cualquier
  llamada real (sin `--limites` de prueba): nada decide ni pausa sin ese dato.
- **I1/motor (integración D8 ↔ X1):** decidir si/cómo la señal de `compliance.salud pausa` llega a
  `engine.d8` sin pisar la de `postcompra.metricas` (Decisión 17). Alternativas que no me
  corresponde elegir: (a) un segundo archivo que `_procesar_senal_pausa` también lea y combine con
  la "más grave manda"; (b) que X1 escriba a una ruta propia (`ofertas/<id>/empresa-x1/...`) y el
  propio `meta.pausar`/`infra.kill` la consuma por su cuenta (coherente con
  `departamentos/14-compliance.md` §4 paso 8: "la pausa es de `meta.pausar`/`infra.kill`, no de
  D8"); (c) fusionar ambas fuentes en `postcompra.metricas` antes de escribir (requiere que B7 lea
  el estado de salud de X1, hoy no existe ese cableado).
- **CT (`contratos`):** `senal_pausa.schema.json` no tiene un escalón para "congelar un ángulo/una
  hoja" (bloquear lanzamientos nuevos sin pausar la oferta activa) ni una categoría de `motivo` para
  causas de cuenta de Meta/Stripe que no son disputas ni reembolsos (D-04, Decisión 18); hoy
  `compliance.salud` las aproxima a `pausar`/`otro`, que pierde matiz.
- **D0/F1/dueño:** `--estado` de `compliance.salud` (`account_status`, `calidad_cuenta_meta`,
  `stripe_aviso`…) no tiene productor automático ni esquema (Decisión 21): alguien tiene que decidir
  quién escribe `empresa/compliance/salud_actual.json` y con qué forma (hoy `[SUPUESTO]`, documentado
  en `validar_estado`).

## Riesgos y límites conocidos

- Los patrones de `reglas_sensibles.yaml` son `[HIPÓTESIS]` (sin casos reales rechazados todavía):
  es intencionalmente amplio (prefiere falsos positivos a falsos negativos) y DEBE calibrarse con
  rechazos reales de Meta/Stripe antes de confiar en él para bloquear sin revisión humana.
  `compliance/reglas_sensibles.yaml` describe ya el proceso para resellar tras editar.
  `compliance.reglas.resellar` es una herramienta local del dueño/X1, no una CLI de agentes.
- `html_checks.verificar_html` nunca abre una conexión: "enlace roto" es un `href` vacío/`#`/
  `javascript:void(0)`, no un 200/404 real (esa prueba de verdad es de B4 con el sitio servido).
- `problemas_firma`/`problemas_uso_sello` son de `scripts.validar_esquemas` (CT): si CT cambia su
  forma, estas pruebas lo seguirían (dependencia intencional, documentada en Decisión 10).
- **`it-IT`, `pl-PL`, `ro-RO`, `fr-FR`, `de-DE` son `[HIPÓTESIS]` sin revisor nativo**
  (`revision_nativa: false` en el propio archivo; `preguntas-abiertas.md`). No bloquear sin revisión
  humana con estos cinco hasta que alguien que hable el idioma los confirme; el primer lanzamiento
  en italiano o polaco lo exige explícitamente la lista de pendientes del dueño.
- `compliance.salud` (B6c, D-04) decide y, con `--aplicar`, escribe un `senal_pausa.json` **a la
  ruta que indique quien llama**, nunca a `10-postcompra/senal_pausa.json` (eso lo escribe
  `postcompra.metricas`, B7): hasta que I1/el motor decida cómo integrarla con `engine.d8`
  («Pedidos»), la señal de X1 **no pausa nada por sí sola**. Sigue siendo útil hoy para el dossier,
  el dashboard o una corrida manual del dueño.
- El estado de entrada de `compliance.salud` (`--estado`) **no tiene productor automático ni
  esquema de contrato** (D-04, Decisión 21): hoy hay que armarlo a mano (o desde `meta.monitor`/
  `postcompra.metricas`/la declaración semanal del dueño) en el formato que documenta
  `validar_estado`.
- `ratio_disputas_pausa` sigue en `null` en `empresa/limites.yaml` (el dueño no lo fijó): cualquier
  llamada real a `compliance.salud` (sin `--limites` de prueba) falla cerrado con código 5. Es el
  comportamiento correcto (D-04: "sin dato de límites no se decide"), no un defecto.
- OCR/transcripción/visión/rastreo del sitio vivo (K03) y M04/M05 (XLSX/PDF) **no se construyeron**
  (D-10 de `dependencias.md`): no hay herramienta disponible en este entorno. Queda una brecha
  declarada, no una interfaz `Protocol` vacía (no se encontró un punto de extensión en este paquete
  donde una interfaz vacía fuera más que un placeholder sin consumidor).
