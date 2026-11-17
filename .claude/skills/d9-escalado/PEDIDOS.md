# Pedidos de la skill D9 (escalado) a S-A y S-B

> Escrito el 2026-11-07 por S-C al crear `d9-escalado` v0.1.0. **No se editó nada fuera de `.claude/skills/d9-escalado/`, `.claude/agents/d9-*.md` y `tests/skills_d9/`.** Cada pedido dice qué, a quién, dónde (archivo:línea verificado hoy) y el texto propuesto. Cómo se comporta la skill mientras tanto: `references/pedidos.md`. Fuentes: `docs/_historial/mentor-sistema/` (J1-J21, `brechas/02` y `03`, `analisis/`), `engine/README.md`.
> **S-A** = contratos, `empresa/*.yaml`, `departamentos/`, `docs/`, `scripts/validar_esquemas.py`. **S-B** = `engine/`, `decision/`, `meta/`, `infra/`, `datos/`, `tracking/`. Todo valor propuesto es `[HIPÓTESIS]` o `[SUPUESTO]`: lo firma el dueño.

**Orden sugerido (los 5 que más destraban):** P-02 (sin ellos el código no propone nada) · P-08 (dos decisiones del dueño que bloquean `escalar`) · P-10 (`engine/escala.py`: pasa lo provisional a oficial) · P-04 (aplicar J2) · P-11 (el guard no verifica el % de paso).

## Para S-A

### P-01 · Paso mayor que 100 % y horas fraccionales (para ×3, ×5 y 30 minutos)
- **Dónde:** `contratos/comunes.schema.json:162` (`porcentaje`, 0-100) · `contratos/limites.schema.json:159` (`aumento_presupuesto_max_pct_por_paso`) y `:170` (`horas_min_entre_aumentos`, entero) · `empresa/limites.yaml:50,53` (comentarios) · (código: P-11).
- **Qué:** hoy ×3 (+200 %) y ×5 (+400 %) son **irrepresentables** y 30 minutos no cabe (brechas 02 B2-09). Ampliar sin tocar la semántica de lo ya firmado.
- **Texto propuesto (MINOR de `limites.schema` 1.4.0):** `aumento_presupuesto_max_pct_por_paso`: `porcentaje_amplio` (entero o decimal en cadena, 0-400, unidades de porcentaje; 100 = ×2) con la descripción «el múltiplo máximo por paso es 1 + pct/100»; `horas_min_entre_aumentos`: `number`/cadena decimal ≥ 0 **o** nueva clave `minutos_min_entre_aumentos` entero (preferible: no cambia el tipo existente). Documentar que solo se usan en la etapa 2-3 de `references/escalera-y-graduacion.md` §4.
- **Por qué:** J1 («su ritmo para todo con nuestros frenos»). Prioridad media: con `gasto_diario_global` leído como máximo teórico de 300, casi no hay holgura para ×3 desde 75 US$/día (`frenos-y-presupuesto.md` §3).

### P-02 · Claves nuevas de `escalado.*` en `parametros.yaml` (y su esquema)
- **Dónde:** `empresa/parametros.yaml:1286` (grupo `escalado`; insertar tras `clon_evidencia_min_compras`, ≈ `:1452`) y `contratos/parametros.schema.json:8783` (grupo `escalado`: `additionalProperties: false`, **hay que subir el esquema o el cargador rechaza el archivo con código 3**).
- **Qué:** las claves que el dictamen lee y no existen (sin ellas responde `PARAMETRO_FALTANTE`, 5).
- **Texto propuesto** (formato del archivo; valores de las fuentes, todos `hipotesis: true`, `ultima_calibracion: null`; donde no hay valor, `null`):
```yaml
    # Compras netas mínimas para llamar campeón (graduable) a un creativo/oferta. [mapeo §12; video «≥ 10 ventas»]
    campeon_compras_min: {valor: 10, unidad: compras, hipotesis: true, fuente: "mapeo 3.2 [HIPÓTESIS]", ultima_calibracion: null, rango: [5, 15]}
    # CPA neto máximo del campeón como fracción del CPA de equilibrio. [mapeo §3.2; video ≈ 0,25-0,30 × BE]
    campeon_cpa_max_x_be: {valor: "0.40", unidad: factor, hipotesis: true, fuente: "mapeo 3.2 [HIPÓTESIS]", ultima_calibracion: null, rango: ["0.25", "0.60"]}
    # CPA de 3 días <= factor x (cpa_subir_factor x cpa_obj). [10-escalado §3.4 y 09-optimizacion:113 «1,15 ×»]
    cpa_3d_factor: {valor: "1.15", unidad: factor, hipotesis: true, fuente: "D9 3.4 [HIPÓTESIS]", ultima_calibracion: null, rango: ["1.0", "1.3"]}
    # % del presupuesto previo que Meta debe haber gastado para permitir otra suba. [brechas 02 E-01 / H-01]
    suba_presupuesto_gastado_min_pct: {valor: 90, unidad: porcentaje, hipotesis: true, fuente: "brechas 02 E-01 [HIPÓTESIS]", ultima_calibracion: null, rango: [80, 100]}
    # Múltiplo máximo de la escalera habilitado hoy (2, 3 o 5). Lo cambia el dueño tras medir el acierto (escalera-y-graduacion §4).
    escalera_multiplo_max: {valor: 2, unidad: multiplo, hipotesis: true, fuente: "mapeo 3.3 [HIPÓTESIS]", ultima_calibracion: null, rango: [2, 5]}
    # Reducción si el paso no rinde. [video «baja 30 %»]
    reduccion_pct: {valor: 30, unidad: porcentaje, hipotesis: true, fuente: "video [P] / mapeo §12", ultima_calibracion: null, rango: [10, 50]}
    # Anuncios campeones que entran a una ESCALA nueva. [video «los 10 mejores»]
    top_en_escala: {valor: 10, unidad: anuncios, hipotesis: true, fuente: "video [P]", ultima_calibracion: null, rango: [3, 15]}
```
  Más (grupo nuevo `auditor`, brechas 02 E-11, propuesta de S-C): `acierto_min_cortes` "0.5", `acierto_min_subas` "0.6", `ventana_cortes_h` 72, `ventana_subas_h` 96, `decisiones_min_por_etapa` `null` (lo fija el dueño), `ofertas_min_por_etapa` 2 (`10-escalado.md:171`).
- **Coordinado con** `.claude/skills/d8-optimizacion/references/decisiones-y-umbrales.md` (U-31 a U-34): pide las mismas claves `escalado.campeon_*` y `auditor.acierto_min`; un solo cambio de S-A sirve a D8 y a D9.
- **Por qué:** sin estas claves D9 no puede proponer ni una graduación; con ellas el umbral deja de ser una opinión de la skill y pasa a ser un archivo que el dueño firma.

### P-03 · Grupo `mercados.*` para J5 (réplica)
- **Dónde:** `empresa/parametros.yaml:2265-2295` (grupo `mercados`) y `contratos/parametros.schema.json:15471` (4 claves, `additionalProperties: false`).
- **Texto propuesto** (`mapeo.md` §12): `hija_requiere_madre_validada` `true` · `aperturas_max_por_ventana` 1 · `ventana_dias` 14 · `ganadores_transferidos_max` 10 · `etapa1_dias` 3-4 · `rehab_dias_concentrado` 3 · `rehab_dias_decision` 7. Aclarar con el dueño si `mercados_test_paralelos_max` = 1 (`:2273`) sigue valiendo bajo J5.

### P-04 · Aplicar J2 en `gates.json`/`limites` y claves de gate que faltan
- **Dónde:** `contratos/gates.json:191` (`accion:activar_campana`), `:231` (`accion:subir_presupuesto_d9`), `:251` (`accion:lanzamiento_pais_idioma_nuevo`), `:121` (`etapa:D9`) · `empresa/limites.yaml:153` y `contratos/limites.schema.json` (enum) · `scripts/validar_esquemas.py:637` (`ACCIONES_GATE_MINIMAS`) · `empresa/autonomia.yaml` (D9 en N0).
- **Qué:** J2 sigue sin aplicarse (autonomía total con sello de X1, preflight, `nivel_max_lanzable`, PAUSA, frenos, vigía, auditor). Faltan claves para `reducir` (A desde N2: reduce exposición), `graduar_a_escala`, `pedido_creativos` y `ajustar_costo` (brechas 02 E-17).
- **Texto propuesto:** `gates.json` → `accion:reducir_presupuesto_d9`: `{N0: H, N1: H, N2: A, N3: A, N4: A}`; `accion:graduar_a_escala`: igual que `subir_presupuesto_d9`; `accion:pedido_creativos_d6`: `{H, H, S, A, A}` (spec `10-escalado.md:164`). Para `lanzamiento_pais_idioma_nuevo`, el dueño decide (pregunta 5 de `conflictos…`): H por idioma o condiciones por código.
- **Por qué:** J2 es decisión del dueño; hoy D9 declara H por defecto y no asume nada.

### P-05 · `estrategia_puja`, `cost_cap` y `locales_meta` en el contrato de campaña
- **Dónde:** `contratos/campana.schema.json:82-89` (`paises`, `idioma`) y `:492-493` (`required`) · (payload: P-13).
- **Texto propuesto (MINOR):** `estrategia_puja` enum `LOWEST_COST` | `COST_CAP`; `cost_cap` dinero (obligatorio si `COST_CAP`, ≤ `economia.cpa_be`); `locales_meta` lista BCP-47 (idioma, no solo país); `rol` enum `TEST` | `ESCALA` | `REFRESCO`; y el chequeo correspondiente en `meta.activar`/C02. Nuevo `orden_control_costo` análogo a `orden_presupuesto` (B1, `analisis` B1).

### P-06 · Esquemas nuevos y `variante_de` en brief/estado/mercado
- **Dónde:** `contratos/` (no existen: propuesta de D9 — `plan.json` sigue sin esquema, C13; `lanzamiento_idioma.schema.json`; `banco_creativos`) · `contratos/oferta.schema.json:19` (`variante_de` solo aquí) frente a `brief.schema.json:17`, `estado.schema.json:16`, `mercado.schema.json:17` (solo `familia_id`).
- **Texto propuesto:** adoptar `templates/propuesta-de-suba.json` como base del esquema `propuesta_escala` (su `orden_presupuesto` ya valida contra `orden_presupuesto.schema.json`); el tablero según `templates/kanban-idioma.md` (6 columnas, tarjetas con `id`, `columna`, `evidencia{tipo, ruta, sha256}`, `estado`, `calculado_por`); `variante_de` (anulable) en brief, estado y mercado.

### P-07 · Reescribir `departamentos/10-escalado.md` a J1-J5 y J11
- **Dónde:** `:8, :29, :94` (disparador `VALIDADA`+H), `:72` (paso 10-30 % / 48-96 h), `:102` (ejecución hasta N2 por el dueño), `:107` (réplica con D1 completo y revisor nativo), `:135` (L1-6 revisor nativo), `:161-162` (gates H), `:171` (ascenso de nivel), `:232` (evals 4).
- **Texto propuesto:** sustituir por el contenido de `.claude/skills/d9-escalado/SKILL.md` §§1-9 y `references/conflictos-con-la-spec-vieja.md` (que lista las 14 diferencias con su línea).

### P-08 · Dos decisiones del dueño que bloquean `escalar`
- **Dónde:** `scripts/validar_esquemas.py:603-605` (`CLAVES_CRITICAS["escalar"]` incluye `stop_loss_escala`) · `contratos/limites.schema.json:112` · `empresa/limites.yaml:38` · `empresa/limites.yaml:23` y `contratos/limites.schema.json` (`gasto_diario_global`: «MÁXIMO TEÓRICO»).
- **Qué:** (a) J3/J4 dicen «no hay tope de pérdida por oferta», pero `escalar` exige `stop_loss_escala` no nulo: **o se firma, o se quita de `CLAVES_CRITICAS["escalar"]`** (decide el dueño; D9 no recomienda crearlo). (b) «300 US$/día» de J4: ¿máximo teórico (≤ 171 US$ de presupuestos) o suma de presupuestos? Anotarlo en el comentario de `limites.yaml:23` y en el esquema.
- **Por qué:** `references/frenos-y-presupuesto.md` §3 y §5.

### P-09 · Cuarto nicho en `macro_nichos_permitidos` (J6/J9)
- **Dónde:** `scripts/validar_esquemas.py:134` (`MACRO_NICHOS`) y `:769` · `empresa/limites.yaml` (`macro_nichos_permitidos`, «el esquema no admite otro valor»).
- **Qué:** sin esto una oferta de «habilidades y hobbies» nunca pasa la bandera `macro_nicho_permitido` de E0. Ya es parte de J6; se anota por su efecto en D9.

## Para S-B

### P-10 · `engine/escala.py` (elegibilidad, ganador, señales, paso, reducir, caja)
- **Dónde:** `engine/d8.py:66` (`_REGLA_DE_ACCION[ESCALAR]="M1"`) y `:277-292` (solo `MATAR` e `INCONCLUSO` se ejecutan; `ESCALAR` se anota) · `scripts/escala.py` no existe (brechas 02 B2-08, B2-10) · `engine/cerrar.py:116-126` (nota `09-escalado/propuesta-d9.md`).
- **Qué:** convertir `.claude/skills/d9-escalado/scripts/escala_lectura.py` (provisional, solo lectura, más de 50 pruebas en `tests/skills_d9/`) en `engine/escala.py` con CLI `elegibilidad | ganador | dictamen`; que produzca las banderas `elegibilidad` (hoy las copia quien arma la entrada) y la **caja** (F1: `dias_cobertura_caja`, payouts, reserva de Stripe de 120 días). Debe usar las mismas funciones (`exigir_agregados_del_efecto`, `exigir_ritmo`, `limites_meta_desde`, `proponer_aumento_presupuesto`).
- **Texto propuesto (firma):** `dictamen(oferta_id, *, conn, ahora, par, lim, raiz) -> dict` con el mismo JSON de salida que `escala_lectura.py dictamen` (`estado`, `codigo`, `ganador`, `senales`, `techo`, `paso`, `orden_borrador`). `ESCALAR` sigue siendo propuesta; ejecuta el guard.

### P-11 · El guard no verifica el % de paso ni el gate de `aumentar_presupuesto`/`escalar`
- **Dónde:** `engine/guard.py:125-127` (`accion_gate` = None) · `meta/subir_presupuesto.py:36-50` (solo recibe un monto) · `decision/reglas.py:415` (`paso_max_pct` ≤ 1,0, par de P-01) · `engine/README.md:138` (dice que lo comprueba `subir_presupuesto`; no lo hace) y su pedido pendiente (`:186`).
- **Texto propuesto:** `limites.exigir_paso(lim, actual_minor, nuevo_minor)` llamada desde el paso 5 del guard (defensa en profundidad) y `accion_gate` condicionada al nivel de D9 (`subir_presupuesto_d9`), y condiciones de J2 (sello de X1 + preflight + frenos) para ejecutar sin orden firmada cuando P-04 lo permita. Tope exacto pasa, tope + 1 no.

### P-12 · Vigilante continuo de pérdida (−3.000) y de gasto diario
- **Dónde:** `engine/limites.py:342-343` (solo al activar o subir) · `infra/workers/watchdog/src/index.mjs:97` (`pausarCuentasPermitidas` devuelve `[]`), `:116` (`gastoHoyMinor: null`), `:118` (`amountSpentMinor: null`) (brechas 02 B2-04, B2-21).
- **Qué:** que algo dispare `empresa/PAUSA` cuando la pérdida realizada alcance `perdida_neta_acumulada_max` y cuando el gasto del día pase `gasto_diario_global`; hoy J4 («pausa automática a los 3.000») no tiene quién la dispare.

### P-13 · `meta/payloads.py`: tope de costo, filtro de idioma, `ajustar_costo`
- **Dónde:** `meta/payloads.py:199` (`geo_locations.countries` solo) y `:215` (`bid_strategy` fijo `LOWEST_COST_WITHOUT_CAP`) · `meta.subir_presupuesto` (agregar `reducir`).
- **Qué:** emitir `locales` en el targeting (idioma) y `bid_strategy` `COST_CAP` con `bid_amount` desde el contrato de P-05; operación `reducir` (−30 %) con guard; `ajustar_costo` con orden registrada y conciliación con `activity_log`.

### P-14 · Auditor de acierto y descenso automático de etapa
- **Dónde:** `engine/d8.py:293-305` (la línea de `decisiones.jsonl` no tiene `resultado` posterior) · `empresa/autonomia.yaml` (`reglas_descenso` es texto) (brechas 02 B2-24, B2-25).
- **Qué:** que cada decisión (suba/baja) reciba su resultado a 96 h/72 h y se calcule el acierto **por tipo**; que el motor baje una etapa/un nivel cuando cae bajo `auditor.acierto_min_*` (P-02) y publique el acierto a F2/`#/robots`. Es la pieza que habilita ×3/×5.

### P-15 · Bug de D8 que impide `VALIDADA` sobre la base real
- **Dónde:** `engine/d8.py:334-337` (`WHERE session_id = ?`; la columna se llama `checkout_session_id`, `datos/migraciones/0001_inicial.sql:86`, y `'abierta'` no es un estado de Stripe) · `tests/decision/test_entradas.py` (fixture sin `v_d8_anuncio`).
- **Por qué:** D9 se dispara con `veredicto_oferta.json` (brechas 02 B2-05). El mismo defecto lo documenta `.claude/skills/d8-optimizacion/references/bugs-conocidos.md` B-01 con el texto de corrección (`checkout_session_id` y los estados abiertos reales de Stripe `[VERIFICAR]`).

### P-16 · Medición horaria y `presupuesto_previo_gastado_pct`
- **Dónde:** `meta/insights.py` (anuncio × día), `datos/etl_meta.py`; no existe `v_venta_hora` (B2-11).
- **Qué:** un productor de código para (a) el % del presupuesto previo que Meta efectivamente gastó (condición H-01 de la suba) y (b) compras Stripe por `adid` por hora y por idioma, sin esperar al píxel (que tarda hasta 4 h). Hoy la entrada del dictamen la arma quien cita la fuente.

### P-17 · `engine.orq`: ingreso de la propuesta de D9
- **Dónde:** `engine/orq.py` (subcomandos; no hay `escalar`/`ingresar` para D9).
- **Qué:** que el motor tome `09-escalado/propuesta-de-suba.json`, valide la `orden_presupuesto` contra su esquema, verifique el hash de QA PASS y el sello de X1, y la entregue al guard/robot (spec `10-escalado.md:102`, «ejecutar sin confiar en el plan»).

### P-18 · `engine.orq` familia/hija y P26 en el preflight
- **Dónde:** `engine/orq.py:269` (crea `FAM-…` nueva por cada oferta) · `meta/preflight.py:304-306` (P01-P24; no hay P26).
- **Qué:** comando de hija (`variante_de`, reutiliza `familia_id` de la madre, exige madre `VALIDADA`); P26 = «tablero de lanzamiento de idioma completo» (brechas 03 B3-18/19; `mapeo.md` §8).

## Lo que NO se pide (a propósito)
Ningún valor para `limites.yaml` (lo fija y firma el dueño); ninguna cifra de J4 cargada por S-A/S-B sin la firma (`engine.propuestas sellar`); ningún cambio a las seis acciones de gate mínimas fuera de la decisión estructural D-02 que ya tomó el dueño (J2).
