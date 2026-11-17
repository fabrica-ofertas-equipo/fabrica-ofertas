# 06 — Bases del testeo: plano maestro de construcción y automatización

> Versión 1.1 (incorpora las críticas técnica y de completitud; ver `docs/_historial/bases-registro-de-cambios.md` y el plan final en `docs/_historial/bases-plan-de-construccion.md`) · 2026-11-06 · Subordinado a `docs/_backbone.md` v2.2, que prevalece. Integra y arbitra `docs/contratos.md` y `contratos/` (A2), `docs/07` (A3), `docs/08` y `decision/` (A4), `docs/09` (A5) y `docs/convenciones-de-codigo.md` (A0). Lo usan 10 constructores en paralelo; el dueño lo lee para entender cómo se arma y automatiza un testeo.
> **Alcance (decisión del dueño, 2026-11-06):** las bases de UN testeo. Todo presupuesto, tope y umbral es paramétrico (`empresa/limites.yaml`, `empresa/parametros.yaml`); sin dato de límites nada gasta ni activa. Ningún mercado es prior (Polonia incluida). Pagos locales y régimen fiscal, diferidos. Los hechos externos están citados con URL y fecha en A3 y A5; acá no se agregan nuevos.
> **Estado verificado:** ver `bash scripts/test_all.sh` (el número de pruebas cambia a medida que se agregan componentes y la sesión de D1 Modo D agrega las suyas) y `python -m scripts.validar_esquemas`, que valida los esquemas, sus ejemplos y `ofertas/_ejemplo/`. Existen y están probados `contratos/`, `scripts/validar_esquemas.py` y `decision/` (4 módulos). Todo lo demás (`engine`, `datos`, `landing`, `meta`, `compliance`, `postcompra`, `infra`, `dashboard`, `agentes`, `tracking`) tiene solo README: es lo que se construye.

> **Portada para el dueño.** Esta semana: (1) `git init` y `.claude/settings.json` de piso (docs/09 §6) antes de abrir la ola 0 (30 min); (2) abrir los trámites con espera: verificación del negocio en Meta, diagnóstico de la cuenta deshabilitada, Stripe en prueba; (3) decidir moneda y zona de la cuenta de Meta, primer mercado y topología (D-20); (4) nada más hasta que las olas 0a-0c estén listas. Qué hacen las sesiones: ola 0a-0c → ola 1 → I1/R1/RB. No se toca: `scripts/modelado/` ni el Modo D (otra sesión). Resumen no técnico: `docs/_historial/bases-resumen-para-el-dueno.md`.
>
> **Glosario.** Gate **H** humano, **S** semiautomático, **A** automático. Nivel **N0-N4** de autonomía (hasta N2 en este plano). Nodos **Dn** (departamentos), **Mn**, **Xn** (cumplimiento), **Fn** (finanzas), **O0** (motor). **Bn** constructores, **CT** contratos, **I1/R1/RB** integración, revisión, runbook. **A0-A5** documentos base (convenciones, contratos, 07, 08, 09). **D-nn** decisiones de §11; **C-nn** conflictos de contratos; **B0-nn** criterios del hito; **A-n** pruebas de aceptación de docs/07; **P01-P24** comprobaciones de campaña; **OF-…** id de oferta.

---

## 0. Resumen ejecutivo

1. **Un testeo** va de un candidato elegido a un veredicto con evidencia de Stripe. Son 17 nodos (§2): 9 pares Maker+QA, 4 nodos de código con redacción opcional del LLM y 4 de código puro o humano. Gates H en N2: brief, infra, mercado nuevo, candidato, oferta, publicar landing, armado y activación de campaña; más una compra real mínima propia.
2. **Los LLM proponen, el código dispone.** Dinero, publicación, activación, reembolso, pausa y decisión de matar o escalar son código determinista con límites duros, hooks y sellos por hash (§3). Ningún agente recibe credenciales de dinero ni de Meta.
3. **11 componentes, 10 constructores en paralelo** más integración, revisión y runbook (§4, §8). Cada directorio tiene un dueño; firmas, CLI, endpoints y tablas están fijados acá. Antes de la ola paralela hay una **ola 0** corta con el núcleo de `engine`.
4. **Modo prueba total** (§6): el flujo corre sin gastar ni publicar. **Hito B0 «esqueleto caminante»**: `ofertas/_ejemplo/` recorre D1→cierre en una raíz aislada, con 18 criterios verificables.
5. **Hallazgos críticos** (§11-§12): la economía unitaria tiene dos fórmulas que no coinciden; `decision/` y el runner leen grupos de parámetros que el esquema no admite; con `ANTHROPIC_API_KEY` el runner no carga conectores MCP; los códigos de salida de A3 y A5 chocaban con las convenciones; `infra_estado` no tenía el campo `modo`.
6. **Bloquea un testeo en vivo** (§9): `limites.yaml` completo y sellado, preflight VERDE, una cuenta publicitaria limpia y verificada, claves de Stripe y Meta cargadas por el dueño, dominio, legales y la compra real mínima. **Nada de eso bloquea construir.**

---

## 1. Qué es «un testeo»

**Definición.** Un experimento pagado y acotado que responde: *¿esta oferta, en este idioma/clúster de mercados, produce compras netas de Stripe a un CPA ≤ el objetivo de `economia.json`?* Empieza cuando el dueño firma el brief y elige un candidato; termina con un `veredicto_oferta.json` (`VALIDADA`, `PROMETEDORA`, `FALLIDA` o `INCONCLUSA`, backbone 5.9) y un post-mortem para X2. En el medio: mercado, validación, oferta, producto, landing, checkout, tracking, creativos y campaña; activación con gate; operación diaria con reglas deterministas; entrega, soporte y conciliación. Unidad = **una celda oferta-mercado**: una campaña, un conjunto (`CBO`, 3-6 anuncios), un dataset/píxel, una landing (A4 §6). Comparar mercados (A4 §7) usa la misma maquinaria con ABO y presupuestos iguales y queda fuera de B0.

**Qué NO es** (se conecta por contratos):

| Fuera de alcance | Conexión | Estado |
|---|---|---|
| **D1 radar** (banco de problemas, Modo D oferta-primero) | entrega `candidatos.json`; los parámetros `modelado_*` (propuestos, sin aprobar) irán bajo `grupos.descubrimiento` en un MINOR propio que aplica la otra sesión del dueño (contratos C20); B1 no toca `descubrimiento` y no se integran acá | otra sesión del dueño |
| **D9 escalado**, clones, `ESCALAR` ejecutado | D8 solo **registra** la propuesta | después |
| **D10 avanzado** (soporte IA, prueba social, email de marketing, disputas) | el testeo necesita entrega, reembolso por regla, señal de pausa | después |
| X2, botón `POST /ofertas`, N3/N4, portafolio | `engine` deja ganchos (`origen_version`, registro, post-mortem) | después |
| Pagos locales, fiscal, Managed Payments | `monedas_precio_adicionales[]` (`mercado.json`), `checkout.precios_por_moneda[]` (D5), `metodos_pago`, `impuestos.modo` ya existen | diferido |

**Las 14 bases** y su dueño: (1) contratos y validador — hecho (A2); (2) límites y parámetros paramétricos, (4) motor de estado y registro — `engine`; (3) infra verde y kill switch — `infra`, `meta`; (5) runner y hooks — `agentes`; (6) embudo de cobro — `tracking`, `infra`, `postcompra`; (7) landing y checkout — `landing`; (8) campaña en Meta — `meta`; (9) datos y atribución — `datos`; (10) reglas de decisión — `decision` (núcleo hecho, A4) y `engine`; (11) cumplimiento — `compliance`; (12) post-compra mínima — `postcompra`; (13) dashboard — `dashboard`; (14) modo prueba y B0 — `tests`, todos.

---

## 2. DAG de punta a punta

```
D0.setup ─► [infra VERDE <6 h] ─────────────────────────────────────────────────────────────┐ condición de TODO gasto
O0.brief ─► D1.elegir ─► M1 ─► D2 ─► D3 ─► D4 ─► D5 ─► D6 ─► D7.armar ─► D7.activar ─► D8 ─► veredicto ─► cierre
  H          H          H     S     H     S     H*    S      H           H + script     A
                                  └───── X1: dictamen y sello sobre D3-claims, D5, D6, D7 (veto) ─────┘
                              D4,D5 ─► D10 (en paralelo; entrega desde el primer pedido) ─► señal_pausa ─► D8
                              Stripe, Meta ─► datos (ETL) ─► F1 (ledger, P&L) ─► F2 (KPI) ─► D8
```
Dependencias de aprobación (`contratos/estado`): M1←D1 · D2←D1,M1 · D3←D2 · D4←D3 · D5←D3,D4 · D6←D3,D5 · D7←D5,D6 · D8←D7 · D10←D4,D5. Si una entrada cambia, la etapa pasa a `pendiente` con `obsoleta=true` y, con campaña activa, el motor **pausa**. *H\**: publicar landing y luego activar, ambos con sello vigente de X1.

**Reglas comunes.** *Flujo de una etapa con IA* (lo ejecuta `engine.orq`): preflight (PAUSA, límites, dependencias) → Maker en `claude -p` con staging → validación en código (esquema, invariantes) → promoción atómica a `vN` → QA en proceso nuevo y solo lectura → ≤ `orquestador.max_rondas_qa` rondas → X1 si corresponde → gate → `aprobado`. *Idempotencia:* `clave = sha256(oferta_id + etapa + hashes de entradas + skill_version + ronda_qa + hash de hallazgos previos)`; misma clave reutiliza la salida; los efectos externos se anotan antes (*write-ahead*) y se busca por ID guardado o prefijo `{oferta_id}_{fase}_` antes de crear. *Reintentos:* solo operaciones idempotentes, con espera exponencial y topes de `orquestador.reintentos_tecnicos`; PAUSA, deny, límite o bucle no reintentan. *Registro:* `empresa/registro.jsonl` (cadena de hash, escritor único: el motor) y `empresa/costos.jsonl`. *Tiempos* son hipótesis de arquitectura §4.2. *Costos* se expresan como clase de gasto y tope que lo acota: ningún importe se afirma sin dato, porque los topes están en `null` hasta que el dueño los fije.

**Fichas** (quién · entra → sale · permisos · gate N2/N3 · tiempo · costo · fallas · idempotencia):

**N01 · D0 Fundaciones** (`setup` una vez; `salud` continuo)
- Humano (altas, KYC, 2FA, claves, `spend_cap`), Maker de checklist y runbooks, código (preflight). Entra: decisiones del dueño. Sale: `limites.yaml` sellado, `infra/*.yaml`, **`empresa/infra/estado.json`** (`infra_estado` 1.1.0). El Maker escribe en `empresa/infra/` salvo `estado.json`; el preflight usa claves de lectura y corre fuera del alcance de los agentes. Gate **H siempre**. Setup: 2-4 semanas de calendario, 25-35 h del dueño (A3 §12.2); salud diaria 06:00 UTC y ligera cada `infra.hc_sonda_ligera_min` con campañas activas. Costo fijo ≈ 22-55 USD/mes (A3 §11).
- Fallas: ROJO crítico sin campañas, no se activa; con campañas, tras `hc_reintentos_antes_de_pausa` fallos (inmediato en M-02, M-03, K-01, P-01) crea `PAUSA`, ejecuta `pausar` y alerta. El preflight es de solo lectura: repetirlo no cambia nada. Registro: `healthcheck/AAAAMMDD-HHMM.json`, `fact_conexion`.

**N02 · O0 Brief**
- Maker (entrevista ≤ 10 preguntas con defaults), código (valida), QA, **H firma**. Entra: `limites`, `parametros`, `autonomia`. Sale: `00-brief.yaml` (`brief`, con `hash`) y el `estado.json` de la oferta, creado por el motor. Maker con `Edit` solo en `00-brief*`. Gate H hasta N3. 15-30 min; costo: tokens ≤ `max_budget_por_corrida_agente`.
- Fallas: brief fuera de límites, moneda ≠ `moneda_limites`, PAUSA o infra no verde → no crea nada y lista lo que falta. El `oferta_id` lo asigna el motor bajo bloqueo: `crear` busca el `hash_contenido` del brief (sin `oferta_id`, `familia_id`, `creado_en`; contratos §1) y el mismo contenido devuelve el mismo ID; el `hash` completo es el que firma el dueño.

**N03 · D1 Elegir candidato** (el radar queda fuera)
- Entra `01-descubrimiento/candidatos.json` (de D1, del dueño o, en B0, del ejemplo). Código valida esquema, `macro_nicho ∈ {salud, relaciones, dinero}`, riesgo ≠ rojo, MU/EU presentes. Sale `estado.candidato_elegido`. Gate **H** hasta N3. 30 min + 25 de QA. Candidato rojo o `fuera_de_macro_nicho` no avanza. Cambiar la elección crea versión nueva e invalida lo posterior.

**N04 · M1 Mercado e idioma**
- Maker + código. Entra candidato, brief y `limites.{paises,locales}_permitidos`. Sale `mercado.json`: `locale`, `paises_segmentacion`, `moneda_cobro`, `estado_decision = hipotesis`, `metodos_pago` (tarjeta y billeteras), `fiscal = diferido`, `monedas_precio_adicionales[]` (vacío en el testeo inicial); el precio por moneda vive en `checkout.precios_por_moneda[]` (D5) y el rango de referencia en `mercado.seleccion.json#precio_referencia[]` (D3 lo fija; artefacto de apoyo de M1, sin esquema aún). Su especificación es `departamentos/16-mercados-localizacion.md` (C09 resuelta). Gate **H** (primer lanzamiento en idioma o país nuevo) hasta N2, S en N3. Permisos: `Edit` en `mercado.json`; web solo en `fuentes_permitidas`. País fuera de `paises_permitidos` → 5. El código no contiene país favorito.

**N05 · D2 Validación**
- Maker + QA; la Biblioteca de Anuncios solo por MCP en la sesión Code del dueño (el runner no tiene MCP, A5 H2). Sale `validacion.json` (`veredicto{calculado, propuesto, final}`, saturación, riesgo de políticas, `handoff_d3`); el veredicto calculado sale de un script (`scripts/validacion/veredicto_d2.py`, dueño **B1**). Gate S. 45+25 min. Costo: tokens, `costo_max_validacion`, consultas ≤ `max_consultas_biblioteca`. Falla: evidencia sin URL o fecha, veredicto ambiguo (el esquema lo rechaza).

**N06 · D3 Arquitectura de la oferta**
- Maker + `engine.factibilidad` + QA + X1 (claims). Entra `validacion.json`, tarifas de F1 (≤ 30 días), `parametros.economia`. Sale `oferta.json` (promesa, precio, garantía, bump, `angulos[]`, `avatar`) y `economia.json` (`aov, mc, cpa_be, cpa_obj, cpa_real{pes,central,opt}, razon, veredicto, gasto_test_plan, perdida_max_test, criterios_corte`). `Edit` en `03-oferta/`; Bash solo `factibilidad.py` y `lint_claims.py`. **Economía y `FACTIBLE` los calcula código.** Gate H (N2), S (N3). 20+25 min. Fallas: `NO_FACTIBLE` (≤ 2 ciclos, luego `ESCALAR`); `gasto_test_plan` sobre `gasto_total_test_por_oferta` o `perdida_max_test_por_oferta` → 5 **solo si el límite existe**: con un límite en `null` D3 propone, no bloquea (emite `economia.json` con `limites_pendientes: [claves]`, economía 1.1.0) y el 5 se da siempre en `guard` de D7/activación; el plan se acota por `total_test_max = floor(min(gasto_total_test_por_oferta, perdida_max_test_por_oferta) / campana.spend_cap_factor)` para que el `spend_cap` quede dentro de ambos límites; claim ROJO → veto. Es el último punto barato para frenar una oferta inviable. D3 imprime además `resultado_esperado_central` (`VALIDADA|PROMETEDORA|FALLIDA`, calculado por `factibilidad`) para que el dueño decida sabiendo si el caso central llega a «validada».

**N07 · D4 Producto**
- Maker + scripts de render, lint y empaquetado + QA (novato cronometrado; los pasos con interfaz gráfica los hace un humano). Sale `producto.json` (`items[sha256]`, `matriz_promesas`, `tiempos.prometido_min` = el de D3) y `04-producto/entregables/`. `Edit` en `04-producto/`; Bash solo `scripts/producto/*` (dueño: **B1**; render, lint, empaquetado; la subida a R2 con `producto_sha256` es de **B7**, `postcompra.publicar_producto`); créditos de generación con cotización previa y `creditos_max_*`. Gate S. 60+25 min más pasos humanos. Fallas: promesa sin entregable (vuelve a D3), tiempo medido > `cold_run_tolerancia × prometido`, similitud ≥ `ngrama_copia_palabras`. Nunca se sobrescribe un `vN` aprobado.

**N08 · D5 Landing, checkout y tracking**
- Maker (copy y brief) + **código** (`landing.generar/validar`, Workers de cobro) + QA + X1 + **H publicar**. Sale `05-landing/`: `sitio/`, `assets.json`, `checkout.json` (`price_ids.{test,live}`, `metadata_esquema`, `sesion_en_servidor`), `tracking.json` (`pixel_id`, `dataset_id`, `consent_gating`, `datos_sensibles.permitidos=false`). El Maker configura, no escribe, las funciones de dinero. Gate H antes de publicar (N2), sello de X1 en todos los niveles. 60+25 min; 1-2 días de calendario con DNS, dominio y compra de prueba.
- Secuencia: preview → compra manual de prueba (la página de Stripe no se automatiza) → H publicar → `Price` live idénticos → **compra real mínima propia con reembolso**. Fallas: precio, moneda o garantía distintos entre `oferta`, `checkout` y HTML (bloqueante); píxel antes del consentimiento; legales ausentes. `lookup_key = OF-…_{rol}_v{n}`: un `Price` usado no se modifica, nace `v{n+1}`. Rollback: `landing.desplegar --rollback-a`.

**N09 · X1 Compliance (veto y sello)**
- Maker (checklist, simulación de revisor) + QA + **código** (`lint_claims`, `html_checks`, `sellar`). Se invoca sobre D3, D5, D6 y D7. Sale `qa/x1-<etapa>-v<n>.json` y, con PASS y aprobaciones H, un **sello** `empresa/compliance/sellos/<hash>.json` (`artefacto_sha256`, `reglas_version`, `vigencia_hasta`, `object_ids` en D7), firmado con una clave que ningún agente tiene. **Veto en todos los niveles.** Fallas: `reglas_sensibles.yaml` ≠ su `hash_contenido` (el lint no corre); cambiar el artefacto o vencer invalida el sello. Un dictamen escrito por un LLM sin sello no vale.

**N10 · D6 Creativos**
- Maker + QA-A (texto, antes de gastar créditos) + QA-B + X1. Sale `06-creativos/paquete.json` (≥ `campana.n_anuncios_min` anuncios, `destino.landing_hash`, `claim_ids`, `lint_x1`) y `assets/`. `Edit` en `06-creativos/`; cotizar antes de generar. En el runner no hay MCP: **semiasistido** (Maker en la sesión Code con Higgsfield, o piezas HTML→PNG con un navegador sin interfaz (Chrome, Chromium o Brave; Playwright como motor alternativo), a 0 créditos). Gate S. 90+25 min. Costo: créditos ≤ `creditos_max_pieza`/`creditos_max_oferta`, registrados **antes** de generar. Falla: claim no autorizado en OCR o transcripción.

**N11 · D7 Armado de campaña (borrador)**
- Maker (estructura, audiencia) + **código** (`meta.nombres/payloads/crear/preflight`) + QA + X1. Sale `07-campana/`: `campana.json` (`estado: borrador → preflight_ok → aprobada`, nombres, URL con macros, `hash_config`), `ids_meta.json`, `preflight.json` (P01-P24), `aprobacion.json`. Todo en `PAUSED`/borrador por Marketing API con el token **operador**; si falta un dato de `limites`, no crea. Gate H (firma). 30+25 min. Costo 0. Fallas: cuenta ∉ `cuentas_permitidas`, anuncios < mínimo, presupuesto diario × 1,75 > `gasto_diario_por_oferta`. Busca por prefijo `{oferta_id}_TEST_` y reutiliza: no duplica.

**N12 · D7 Activación** (acción `activar_campana`; script, no Maker)
- `meta.activar`, tras firma H, exige en orden: `FABRICA_ENTORNO=produccion` · sin `PAUSA` · infra VERDE `modo=vivo` y < 6 h · límites válidos y **agregados** para `activar` (§4.2) · sello de X1 vigente · `aprobacion.json` firmada · **relectura de Meta**: `hash_config` vivo = aprobado = preflight (< `campana.preflight_vigencia_h`). Luego (D-19, Marketing API; `allow_partial_publish`/`ignore_validation_errors` son del conector MCP y solo viven en el hook de esa rama): (1) lee el árbol vivo campaña → conjuntos → anuncios por `GET`; (2) compara el conjunto de IDs con `sello.object_ids` e `ids_meta.json` (igualdad exacta; un extra o una falta → no activa); (3) activa **anuncios → conjunto → campaña** (la campaña al final: nunca hay entrega a medias), cada `POST status=ACTIVE` con clave local `activar:<id>:<hash_config>`; (4) relee `effective_status` de los tres y, si algo no queda `ACTIVE` o hay un objeto `ACTIVE` imprevisto, `pausar` y `ErrorExterno`. Gate H (N2), S con regla pre-aprobada (N3). Deriva de hash → no activa y alerta; activar lo ya `ACTIVE` es un no-op registrado. Pruebas con `TransporteFixture`, incluida «falla el segundo POST».
- **Monitoreo posterior** (`meta.monitor`, B5; `--oferta --ventana-h {1,6,24,48,72}`): lee `effective_status` por anuncio, errores, gasto vs esperado, `adid` capturado, vistas/clics y escribe `07-campana/traspaso.json` (esquema `traspaso` 1.0.0). Un anuncio `DISAPPROVED` se pausa, cuenta en `rechazos_7d`, abre pedido a D6/X1 y **nunca se reenvía el mismo `hash`**; con `rechazos_7d ≥ compliance.rechazos_congelar` el motor pone `PAUSA` de lanzamientos y baja D5-D9 a N1. Sin esto un rechazo silencioso se confunde con `tope_sin_clics`.

**N13 · D8 Operación y veredicto** (continuo)
- **Código** (`engine.d8`, `decision`) + Maker de diagnóstico que solo redacta sobre salidas del motor + QA. Cada `optimizacion.lectura_horas`: ETL → KPI → guardarraíles G → matar K → mantener M → `decisiones.jsonl` → ejecutor (pausar anuncio u oferta, la única escritura viva sin gate) → `veredicto_oferta.json`. Decide con **compras netas de Stripe**, nunca las de Meta. Gate A desde N2. Tiempo: ventana `veredicto.dias_min`-`dias_max` (7-14 d) + madurez garantía + `madurez_dias_extra`: la última compra madura entre el día **28 y el 35** desde la activación, no el 21. Al agotarse `campana.presupuesto.dias` o el tope sin veredicto final, el motor **pausa y cierra la campaña** (`campana.estado = cerrada`), pone `espera_madurez.activa = true` con `hasta`, y sigue leyendo (ETL, KPI, veredicto) **sin gasto**; el dashboard muestra «VALIDADA posible el <fecha>»; al llegar `hasta` emite el veredicto y, si faltan compras netas, `INCONCLUSA`. Costo: gasto publicitario ≤ topes y tokens del diagnóstico. Modo ciego, datos inmaduros o desfase Meta↔Stripe → `SEGUIR` o `INCONCLUSO` con responsable, nunca `MATAR`. `decision_id = hash(oferta, objeto, lectura_ts)`: repetir la lectura no duplica acciones.

**N14 · D10 Post-compra mínima** (desde el primer pedido)
- **Código** (Worker `fulfill`, `descarga`, `postcompra.reembolsar/metricas`) + triage opcional. Entra el webhook firmado. Sale `entregas.jsonl`, `reembolsos.jsonl`, `senal_pausa.json`. Entrega A en todos los niveles; **no la detiene `PAUSA`** (R17). Reembolso automático solo dentro de garantía, ≤ `reembolso_auto_max` y `reembolsos_auto_max_por_dia`, con `Idempotency-Key = sha256("reembolso", session_id, monto_minor)` (**sin el motivo**: es dato del registro); con disputa abierta, nunca. Algoritmo (`postcompra.reembolsar`, §4.8): reserva atómica, tope sobre el **acumulado** del pedido, reintento tardío que lista antes los `refunds`. Sin `entregado` pasado `postcompra.entrega_alerta_min` → reintento y alerta. Idempotencia por `checkout_session_id` y `(tipo, objeto_id)` además de `event.id`. **Fuera de regla** (fuera de plazo, mayor importe, disputa abierta): el dueño responde desde `soporte@` con `postcompra.reembolso_manual` (acción H, `ejecutor=humano`, respeta `PAUSA`) y `postcompra.evidencia --session cs_… --salida DIR` arma el paquete de disputa sin datos personales; `charge.dispute.created` alerta por los dos canales con `postcompra.disputa_contestar_min`.

**N01b · D0 Alta de oferta** (humano + `infra.alta_oferta`, entre D4 y D5; D5 ← alta)
- Por cada oferta alguien debe: elegir y **comprar el dominio** (cuesta dinero; nunca lo hace un agente), crear zona y proyecto Pages, crear el dataset `DS_<oferta_id>` (irreversible, máx. 100), generar el token CAPI y cargarlo como secreto del Worker, verificar el dominio en el portfolio, dar de alta el dominio de envío en el proveedor de correo (SPF/DKIM/DMARC), crear `Product`/`Price` de prueba y luego vivos, añadir la ruta `/api/sesion*`, cargar secretos por oferta y **recalcular y subir el `spend_cap`**. `infra.alta_oferta` (dry-run) imprime la lista de `infra/plantillas/alta-oferta.yaml` (11 pasos con «quién», «cómo se comprueba» e ítem de preflight) y verifica en solo lectura. Sale `ofertas/<id>/infra/alta.json` (IDs, sin secretos). Gate H. `[HIPÓTESIS]` 2-3 h del dueño por oferta. D5 necesita `pixel_id`, `dataset_id` y `dominio_verificado` para cerrar.

**N15 · F1 Finanzas** — **código** (ledger, conciliación triple, P&L) + Maker que interpreta desvíos + QA. Entra Stripe (destino `finanzas`), gasto de Meta, `costos.jsonl`, tipos de cambio registrados. Sale `empresa/finanzas/{ledger.jsonl, pnl.json, conciliacion.json, alertas.jsonl}`. Gate A; el capital es H. Conciliación ≠ 0 → cifra tachada; compras de prueba o internas excluidas; upsert por clave natural.

**N16 · F2 Dashboard y KPI** — **código** (`datos.kpi`, `dashboard.build`) + Maker de lectura semanal que recibe solo números e IDs. Sale `empresa/datos/kpi_oferta_dia.json` y `empresa/dashboard/index.html` con todo texto escapado. Gate A. Frescura roja → cifra tachada con causa, nunca 0 ni dato viejo sin marca.

**N17 · O0 Cierre** — código (fase final `validada | fallida | inconclusa`) + Maker de `postmortem.json` para X2 + H. Si hay `VALIDADA`, deja una propuesta para D9 sin ejecutarla. La fase final no se reescribe.

---

## 3. Matriz código · LLM · humano

| Función | Código determinista | LLM | Humano | Qué acota al LLM |
|---|---|---|---|---|
| Límites, topes, kill switch | cargador con sello, `guard`, `PAUSA`, `pausar`, watchdog | nada | fija y sella `limites`, `spend_cap` | `Edit` denegado; usuario SO sin permisos; sin credenciales |
| Estado, gates, idempotencia | `engine.estado`, `orq`, registro encadenado | nada | firma gates H | solo el motor escribe `estado.json` (permisos del SO, no solo `deny`) |
| Economía y presupuesto | `factibilidad`, `plan_celda`, topes | propone precio, bump, garantía, ángulos | aprueba la oferta | `economia.json` lo genera un script |
| Medición y atribución | Workers, CAPI, ETL, unión `oferta_id`+`adid`, ledger, KPI | nada | — | no ve texto libre de clientes ni UTM |
| Matar, seguir, veredicto | `decision.*`, reglas G/K/M, ejecutor de pausas | redacta diagnóstico y pedidos a D6 | confirma `VALIDADA` | cifras por plantilla; la regla manda |
| Publicar y activar | `landing.desplegar`, `meta.activar` | nada | firma H | hook, sello de X1, `hash_config`, `object_ids`; `ads_activate_entity` en `deny` |
| Cobro, entrega, reembolso | Workers, `fulfill`, `descarga`, `reembolsar` | triage opcional | compra real mínima; disputas | sin claves `rk_*`; el servicio revalida contra Stripe |
| Contenido | render, lint, empaquetado, esquemas | **genera** (mercado, producto, copy, guiones, ángulos) | revisa por gate | esquema, lint, QA independiente, X1; todo texto externo es dato |
| Juicio de calidad y cumplimiento | scripts L1, `lint_claims`, sellos | QA L2 (0-5 con cita), L3, checklist de X1 | muestreo; H en casos | evidencia citada; defectos sembrados ≥ 90 %; veto |

**Cuánto LLM queda:** 9 pares Maker+QA (brief, M1, D2, D3, D4, D5, D6, D7, X1), 4 lectores (D8, F1, F2, post-mortem) y 1 triage opcional; cada corrida está acotada por `limites.max_budget_por_corrida_agente`, `agentes.turnos_max` y `agentes.tiempo_s_max`, con 2 rondas como máximo. **Invariantes que las pruebas comprueban:** (1) el entorno de un agente no contiene claves de Stripe, Meta, `SELLO_*` ni `GITHUB_TOKEN`; (2) nada gasta, activa, reembolsa o pausa sin pasar por `engine.guard.comprobar_live`; (3) ningún número de dinero, plazo o porcentaje de decisión está fijo en el código (búsqueda estática: `scripts/lint_estatico.py`, dueño I1, invocado desde `lint.sh`; hoy `lint.sh` solo hace `compileall` y `node --check`); (4) un hook que falla bloquea.

---

## 4. Interfaces entre componentes

### 4.1 Propiedad y convenciones de interfaz

| Componente | Constructor | Dueño de |
|---|---|---|
| `engine` | **B1** | `engine/**` (incluye `engine/propuestas.py` con `proponer` y `sellar`; `engine/limites.py` es núcleo congelado y no los tiene), `decision/entradas.py`, `scripts/factibilidad.py`, `scripts/producto/*`, `scripts/validacion/veredicto_d2.py`, `empresa/propuestas/parametros-b0.yaml` |
| `contratos` | **CT** (ola 0b) | `contratos/**`, `scripts/validar_esquemas.py`, `docs/contratos.md`, `ofertas/_ejemplo/` (regenerar y re-sellar) |
| `decision` | A4 (hecho) | `decision/{estadistica,presupuesto,reglas,simulacion}.py`; cambios solo vía B1 con revisión de R1 |
| `tracking` | **B2** | `tracking/workers/{crear-sesion,webhook-stripe,capi,eventos,_lib}/` |
| `datos` | **B3** | `datos/**` |
| `landing` | **B4** | `landing/**` |
| `meta` | **B5** | `meta/**` (incluye `meta/monedas.py` y `meta.monitor`), `scripts/{meta_crear,meta_activar,pausar,subir_presupuesto}.py` |
| `compliance` | **B6** | `compliance/**`, `scripts/lint_claims.py`, esqueleto de `empresa/compliance/` |
| `postcompra` | **B7** | `postcompra/**` (incluye `evidencia`, `reembolso_manual`, `publicar_producto`), `infra/workers/fulfill/` |
| `infra` | **B8** | `infra/**` (salvo `fulfill`; incluye `infra.dominio`, `infra.alta_oferta`, `infra/plantillas/alta-oferta.yaml`), `scripts/preflight.py`, `.github/**`, `infra/plantillas/`, regenerar `.env.example` |
| `agentes` | **B9** | `agentes/**`, `.claude/settings.json`, `.claude/agents/_plantillas/` |
| `dashboard` | **B10** | `dashboard/**` |
| integración | **I1** | `tests/integracion/**`, `scripts/b0_e2e.py`, `scripts/verificar_propiedad.py`, `scripts/lint_estatico.py`, `tests/fixtures/engine/escenarios/`, `tests/fixtures/{meta,datos}/reales/` |

Pruebas en `tests/<componente>/` (Node, junto al Worker en `test/`) y fixtures en `tests/fixtures/<componente>/`, del mismo dueño. Los nombres fijados por las convenciones (`factibilidad.py`, `lint_claims.py`, `preflight.py`) son **envoltorios de una línea** en `scripts/`; la lógica vive en el paquete del dueño. `contratos/**` cambia solo por `docs/contratos.md` §8. **Nombre en la especificación → módulo vigente (dueño):** `activar_campana.py` (07, 02, D7) → `meta.activar` / `scripts/meta_activar.py` (B5) · `x1_sello` (02, 09, X1) → `compliance.sellar` (B6) · `d8_ejecutar` (09) → `engine.d8` + ejecutor (B1) · `validar_nombres` (D0) → `meta.nombres.validar_nombre` (B5) · `stripe_catalogo.py` (07) → `landing.catalogo` (B4) · `dominio_alta.py` (07) → `infra.dominio` (B8) · `secretos_cargar.py` → B8 · `scripts/<nombre>.py` es un envoltorio de una línea. Intocables: `scripts/modelado/`, `departamentos/02-descubrimiento.md`, `tests/scripts/test_puntaje_modelar.py`, `tests/fixtures/modelado/` (otra sesión del dueño). `verificar_propiedad.py` falla si un diff toca archivos de otro dueño.

**Reglas de interfaz.**
- **CLI:** `python -m <paquete>.<modulo> <subcomando> [--oferta OF-AAAAMM-NN] [--live] [--json] [--raiz RUTA] [--ahora ISO]`. `--raiz` y `--ahora` solo existen con `FABRICA_ENTORNO != produccion`. Con `--json`, stdout es **una** línea `{"ok","modo":"dry_run|fixture|live","codigo","datos","avisos"}`; la traza va a stderr sin secretos. Salidas 0-6 de convenciones §8, sin excepciones.
- **Modos:** `dry_run` (defecto), `fixture` (sin red, lee `tests/fixtures`) y `live` (solo con `--live`, `FABRICA_ENTORNO=produccion` y `engine.guard.comprobar_live`). Dry-run y live ejecutan el mismo código de decisión; difiere la última llamada.
- **Dinero:** enteros en unidad menor + ISO 4217 en JSON, base y firmas. `float` solo como **tasa en memoria** dentro de `decision/`; lo persistido usa enteros, puntos básicos o cadenas decimales (D-05).
- **Red:** todo cliente recibe un `Transporte` inyectado; las pruebas usan `TransporteFixture` y bloquean `socket.socket`.
- **Núcleo sin ciclos:** `engine/{errores,comun,limites,parametros,guard,registro,transporte}.py` no importa otros paquetes del proyecto (salvo `scripts.validar_esquemas` para hashes y validación); los demás importan el núcleo, nunca al revés.

### 4.2 `engine` (B1)

Núcleo (ola 0), firmas congeladas:
```python
# errores.py   ErrorFabrica(codigo_salida): ErrorUso 2 · ErrorValidacion 3 · ErrorBloqueado 4 · ErrorLimite 5 · ErrorExterno 6
# comun.py
def raiz() -> Path;  def entorno() -> Literal["desarrollo", "prueba", "produccion"]
def ahora_utc() -> datetime;  def iso_z(d: datetime) -> str;  def parsear_z(s: str) -> datetime
def escribir_atomico(ruta: Path, datos: bytes) -> None;  def anexar_jsonl(ruta: Path, obj: Mapping) -> None;  def leer_jsonl(ruta: Path) -> list[dict]
#   re-exporta sin reimplementar (scripts.validar_esquemas): json_canonico, hash_objeto, hash_archivo, hash_directorio, clave_idempotencia, firma_hmac, comparar_hash
# limites.py     def cargar_limites(ruta=None) -> Limites;  def exigir_operacion(lim: Limites, operacion: str) -> None   # evaluar_limites (incluye coherencia); ErrorLimite (5);  def exigir_agregados(lim, activas) -> None
# parametros.py  def cargar_parametros(ruta=None) -> Parametros;  .valor("grupo.clave") -> Any (ErrorLimite si falta);  .aplanar() -> dict[str, Mapping]
# guard.py — la ÚNICA función de comprobaciones de --live (convenciones §9)
#   (el hash vigente de limites.yaml se compara con LIMITES_HASH_ANCLA, fuera del volumen; las firmas son Ed25519 con clave PÚBLICA: D-23)
def comprobar_live(operacion: str, *, oferta_id: str | None = None, monto_minor: int | None = None, moneda: str | None = None,
                   sello: str | None = None, ahora: Callable[[], datetime] = ahora_utc, simulacion: bool = False) -> ContextoLive
#   orden: entorno=produccion → PAUSA → infra VERDE (firma del estado.json verificada ANTES; modo=vivo, ítems todos VERDE, no futuro, <= min(parametro, 6) h con reloj propio) → límites de la operación (coherentes) → topes AGREGADOS, hora y rate limit → credenciales → aprobación o sello
#   simulacion=True (solo B0): exige TransporteFixture; reemplaza SOLO el paso 1 por entorno ∈ {prueba, desarrollo} y el paso 3 por modo ∈ {prueba, simulado} con valido_hasta vigente; los pasos 2, 4, 5, 6 (credenciales ficticias) y 7 (sello y firma de prueba) no cambian;
#   devuelve ContextoLive(modo="fixture") y se NIEGA (4) con entorno=produccion. Los 7 pasos reales se prueban en tests/engine/ con reloj y entorno INYECTADOS, no por variable de entorno.
#   Agregados (M05): engine.limites.exigir_agregados(lim, activas) lee TODAS las campañas ACTIVE de la cuenta: Σ max_teorico_diario(activas) + nuevo ≤ gasto_diario_global; n_activas + 1 ≤ ofertas_en_test_simultaneas_max;
#   Σ perdida_acumulada_oferta + Σ (spend_cap − gasto)_activas ≤ perdida_neta_acumulada_max; limite_gasto_cuenta_meta ≥ gasto_vitalicio + Σ spend_cap_restante. Casos límite: suma = tope, tope + 1.
# registro.py (escritor único de la cadena)  def registrar(evento: Mapping) -> dict;  def ingerir_spool(ruta: Path) -> int
#   def costo(oferta_id, origen, monto_minor, moneda, **meta) -> dict;  def verificar_cadena(ruta=None) -> list[str]
# transporte.py  class Transporte(Protocol): def solicitar(self, metodo, url, *, cabeceras, cuerpo, timeout_s) -> Respuesta
```
Resto del motor:
```python
# estado.py   cargar(oferta_id) -> dict · guardar(oferta_id, estado, *, revision_esperada) -> dict (bloqueo optimista)
#   transicionar(oferta_id, etapa, a, *, actor, causa, firma=None) · aprobar(oferta_id, etapa, *, version, aprobado_por)
#   propagar_obsolescencia(oferta_id, etapa_cambiada) -> list[str]  (pausa la campaña si estaba activa) · gate_de(oferta_id, clave) -> "A"|"S"|"H"
# factibilidad.py  calcular(entradas: Mapping, parametros: Parametros) -> dict   # única economía; Decimal/enteros, ROUND_HALF_EVEN; produce economia.json
# d8.py       ciclo(oferta_id, *, conn, ahora, par, lim, ejecutor, modo) -> list[dict] · veredicto(oferta_id, *, conn, ahora, par) -> dict
# ejecutor.py class Ejecutor(Protocol): pausar(objeto_id, *, motivo) -> Resultado     # única escritura viva sin gate
```
| `python -m engine.orq …` | Flags | Efecto | Salida |
|---|---|---|---|
| `crear` | `--brief RUTA` | valida el brief, crea `OF-…` y `estado.json` | 0, 3, 4, 5 |
| `estado` · `siguiente` | `--oferta` | etapa y gate pendientes; próxima etapa ejecutable | 0, 3 |
| `ejecutar` | `--oferta --etapa Dn --modo {dry-run,fixture,live} [--fixture DIR]` | Maker → validación → promoción → QA → X1 → gate | 0, 3-6 |
| `firmar` | `--oferta (--etapa X \| --accion A) --como dueno` | firma **Ed25519** de un gate H con la clave privada del dueño (su terminal); genera una **orden firmada** `{accion, oferta_id, etapa?, hash_objetivo, ts, nonce}` que `POST api /ordenes` entrega al motor (verifica con la pública, rechaza `nonce` repetido, solo registra la firma que `guard` consumirá) | 0, 3, 4 |
| `ingresar` | `--oferta --etapa Dn --desde DIR [--origen {humano,sesion_code}]` | para lo hecho a mano (método del dueño, N0-N1, etapas con MCP): copia `DIR` a `.staging/`, ejecuta la **misma** validación que el flujo con IA (esquema, invariantes, rutas, hashes, diff), promueve a `vN` con `origen_version=humano`, registra, pasa a `en_QA` (QA opcional en N0-N1) y deja el gate pendiente | 0, 3, 4 |
| `nivel` | `--etapa Dn --a N1\|N2 --evidencia RUTA --como dueno` | asciende una etapa solo con firma H (`accion:ascender_nivel`); el descenso es automático. Una skill `v1.0.0` se registra aquí y su hash entra a `skills_pin`; sin esa entrada el motor solo acepta `ingresar` | 0, 3, 4 |
| `activar` | `--oferta --object-ids … --hash-config … [--live]` | `guard` y `meta.activar` | 0, 4-6 |
| `ciclo-d8` · `veredicto` · `cerrar` | `--oferta [--live]` | lectura diaria; veredicto; fase final y post-mortem | 0, 4, 5 |
| `pausar` · `reanudar` | `[--oferta]` | crea `PAUSA` y llama a `pausar`; reanudar exige firma, preflight VERDE y hashes | 0, 4 |

| `python -m engine.propuestas …` | Flags | Efecto | Salida |
|---|---|---|---|
| `proponer` | `--oferta OF [--multiplos 10 15 25] [--corridas N] [--semilla N]` | lee `economia.json` y `decision.simulacion` y escribe `empresa/propuestas/limites.propuesta.yaml` (solo claves de `gastar`/`activar`, enteros en `moneda_limites`) más una tabla: para cada múltiplo del equilibrio, % de corridas MATAR/ESCALAR/INCONCLUSO y gasto medio en ganador en el objetivo, ganador justo, equilibrio, perdedor moderado y severo. **No modifica `limites.yaml`**: es la herramienta con la que el dueño fija la pérdida máxima desde los presupuestos de testeo | 0, 3 |
| `sellar` | `[--propuesta RUTA] --como dueno [--live] [--clave-privada RUTA]` | verifica con `evaluar_limites(…, "activar")`, calcula `sello.hash` y `sello.firma` (Ed25519) y es el **único** escritor de `empresa/limites.yaml`, que solo escribe con `--live` y `FABRICA_ENTORNO=produccion`; corre en el terminal del dueño; imprime el hash para la variable `LIMITES_HASH_ANCLA` | 0, 3, 4, 5 |

`decision/entradas.py` (B1): `evidencia_celda` aplica `compras_corregidas = round(compras_atribuidas × 10000 / cobertura_adid_bp)` del mismo periodo, `tracking_sano = cobertura ≥ mínimo ∧ razón Meta/Stripe en rango` y excluye de la evidencia los últimos `estadistica.dias_madurez_compra` días (docs/08 §5.3); es el único sitio que convierte `*_pct` de `limites` (unidades de porcentaje) a fracción (`LimitesMeta` ya rechaza `paso_max_pct > 1`). `parametros_decision(par, economia) -> ParametrosDecision` (aplana `grupos.<g>.<k>` y deriva `conv_central`, `cpc_esperado`, `cpa_equilibrio_visto` si faltan); `evidencia_celda(conn, oferta_id, nivel, celda_id, ahora) -> EvidenciaCelda`; `serializar(d: Decision) -> dict` sin `float`.

### 4.3 `tracking` (B2) — Workers de Cloudflare, JS sin dependencias

| Worker | Ruta | Entrada → salida | Secretos |
|---|---|---|---|
| `crear-sesion` | `POST <dominio>/api/sesion` | `{oferta_id, visitor_id, bump, locale, params{utm_*, cid, asid, adid, fbp, fbc}}` → `200 {url}` o `4xx`. Precio **solo** del catálogo firmado; `client_reference_id = visitor_id`; `metadata` = `checkout.metadata_esquema`; `Idempotency-Key = sha256(operacion, oferta_id, visitor_id, price_id, bump, bucket)` | `STRIPE_RK_CHECKOUT`, `CATALOGO_HMAC` |
| `webhook-stripe` | `POST hooks.<infra>/stripe` | cuerpo crudo + `Stripe-Signature`; tolerancia `STRIPE_TOLERANCIA_SEG` (nunca 0); firma falsa → 400; `event.id` único en KV; `2xx` en < `infra.webhook_respuesta_max_ms`; encola a `fulfill` | `STRIPE_WHSEC_LIVE/TEST` |
| `capi` | módulo interno | `enviarPurchase`, `enviarIC` → Graph `/{dataset}/events` con `event_id = purchase_<session_id>` o `ic_<visitor_id>_<ts>`, email con hash, `test_event_code` en prueba; sin datos de salud | `META_CAPI_TOKEN__<oferta>` |
| `eventos` | `POST <dominio>/api/ev` | `PageView`/`ViewContent` → valida y reenvía firmado a `api /ingesta/evento` | `INGEST_HMAC_SECRET` |

`crear-sesion` es un endpoint público: **limitación de tasa** de Cloudflare (WAF) por IP y por zona sobre `/api/sesion` y Turnstile en el botón de compra (sin cookies de seguimiento); `cid/asid/adid` `^[0-9]{6,20}$` y **solo se aceptan los que figuren en el catálogo firmado** (`ids_meta.{campaign,adset,ad}` de la oferta; cualquier otro se reemplaza por `adid="desconocido"` y cuenta en `cobertura_adid`); `visitor_id` `^[A-Za-z0-9_-]{16,64}$`; `fbp` `^fb\.[0-9]\.[0-9]{10,13}\.[0-9]+$` y `fbc` `^fb\.[0-9]\.[0-9]{10,13}\..+$`; cuerpo ≤ `ingesta.cuerpo_max_bytes`; cuota diaria `max_sesiones_por_visitante` en el Durable Object; alerta si `sesiones_creadas / PageView` supera el umbral de `parametros.landing`. La metadata incluye `visitor_id`, `consent_marketing`, `landing_version`, `event_source_url` (contratos, checkout 1.1.0). `webhook-stripe`: dedupe por `(tipo, objeto_id)` en un **Durable Object por `session_id`** (no en KV), 2xx tras escribir `encolado`, regla WAF con IPs de Stripe + firma. `capi`: `enviarPurchase` solo si `consent_marketing == "1"`; `fbp/fbc` sin hash y solo si existen; `em`/`ph` normalizados y con SHA-256 antes de enviar; no reenvía eventos de más de 6 días. `_lib/` aporta HMAC con `crypto.subtle` y comparación en tiempo constante, y verificación Ed25519. Pruebas con `fetch`, KV, Durable Object y reloj falsos: firma válida, falsa y vencida; duplicado; **mismo `session_id` con dos `event.id`** y dos entregas concurrentes; precio manipulado; metadata sin `adid`; `adid` fuera del catálogo; `cmp=r` no produce llamada a Graph. Prueba de CPU del Worker `crear-sesion` bajo el límite del plan Paid y `wrangler.toml` con `limits.cpu_ms` explícito `[VERIFICAR en https://developers.cloudflare.com/workers/platform/limits/; no releído]`.

### 4.4 `datos` (B3)

| Comando | Flags | Efecto |
|---|---|---|
| `python -m datos.db migrar` | `--url` | aplica `datos/migraciones/NNNN_*.sql` (SQL portable) |
| `python -m datos.etl_meta` | `--oferta --desde --hasta [--live]` | insights por anuncio y día (reproceso `dashboard.meta_ventana_reproceso_dias`) → `raw_`, `fact_meta_*` por upsert |
| `python -m datos.etl_stripe` | `--desde [--live]` | backfill por cursor → `fact_pedido`, `fact_reembolso`, `fact_disputa`, `stripe_evento` |
| `python -m datos.ledger` · `datos.kpi` | `--oferta --periodo` · `--oferta --fecha` | `ledger.jsonl`, `pnl.json`, `conciliacion.json` · `kpi_oferta_dia.json` |

Funciones: `conectar(url) -> Conexion` (`sqlite:///…` o `postgresql://…`; marcador `?` traducido); `aplicar_evento(conn, evento) -> "nuevo" | "duplicado"`; `aplicar_entrega`; `aplicar_stripe`; `evidencia_celda`; `cobertura_adid(conn, oferta_id, desde, hasta) -> int` (bp); `razon_meta_stripe`; `pedidos_cohorte(conn, oferta_id, hasta) -> list[PedidoStripe]`; y controladores puros `manejar_ingesta_evento(cuerpo: bytes, cabeceras, conn, ahora) -> (status, dict)`. Se excluyen siempre las compras `verificacion=1` o internas.

### 4.5 `landing`, `meta`, `compliance` (B4, B5, B6)

| Comando | Flags | Efecto |
|---|---|---|
| `landing.generar` · `landing.validar` | `--oferta` | `oferta`+`producto`+`mercado`+plantillas → `sitio/`, `assets.json`, `rutas.json` · L1: precio, moneda y garantía iguales en `oferta`, `checkout` y HTML; enlaces y legales con 200; sin datos de salud; consentimiento antes del píxel; pesos |
| `landing.catalogo` · `landing.desplegar` | `--oferta [--live]` · `--entorno {preview,produccion} [--rollback-a TAG]` | catálogo firmado `oferta_id → price_id` y `Product/Price` de **prueba** · despliegue; producción exige sello y gate |
| `meta.crear` (`meta_crear.py`) · `meta.preflight` | `--oferta [--live]` | campaña → conjunto → creativos → anuncios en `PAUSED`, `ids_meta.json`, reutiliza por prefijo · P01-P24, `preflight.json`, `hash_config` |
| `meta.activar` (`meta_activar.py`) | `--oferta --object-ids … --hash-config … [--live]` | las condiciones de N12 |
| `meta.pausar` (`pausar.py`) · `meta.insights` | `[--oferta] [--live]` · `--oferta --desde --hasta` | `PAUSED` en toda campaña `ACTIVE` de `cuentas_permitidas`, idempotente y con relectura · lectura para el ETL |
| `compliance.lint_claims` · `html_checks` | `lint_claims`: `(--archivo F \| --oferta OF --etapa E) --locale L [--macro-nicho M]` (`--locale` obligatorio, sin default: falla cerrado) · `html_checks`: `--archivo F.html [--locale L]` | claims, atributos personales, urgencia, garantías, precio (3 si hay ROJO) · temporizadores falsos, casillas premarcadas, enlaces legales, píxel antes del consentimiento |
| `compliance.sellar` · `verificar` | `--oferta OF --etapa-objetivo E --artefacto RUTA --dictamen qa/x1-<etapa>-v<n>.json --locale L [--object-ids …]` · `--hash H [--object-ids …]` | sello solo con lint sin ROJO, QA PASS y firmas H · imprime el sello vigente o sale 4 |

Funciones: `generar_sitio(dir_oferta, plantillas) -> dict[str, str]`, `validar_sitio(dir_oferta) -> list[Hallazgo]`, `construir_catalogo(checkout) -> bytes`; `nombre_campana(oferta_id, fase, objetivo, estructura, fecha)` (y conjunto/anuncio), `validar_nombre(tipo, s)`, `url_anuncio(base, oferta_id)`, `payload_campana(campana) -> dict`, `validar_payload(payload) -> list[str]` (sin red), `hash_config(campana)`, `ClienteMeta(transporte, token, version)` con `appsecret_proof`, retroceso ante el error 613, ≥ 30 s entre ediciones de un objeto y ≤ 4 cambios de presupuesto por hora; `lint_texto(texto, reglas, locale)`, `cargar_reglas(ruta)` (rechaza si `reglas_version` no coincide), `sellar(dictamen, artefacto_sha256, *, object_ids=None, clave) -> Sello`, `verificar_sello(clave_sello, ahora) -> Sello | None`. El nombre usa `objetivo = VENTAS` y `estructura = CBO|ABO` (D-10). `SELLO_X1_CLAVE` no está en el entorno de los agentes y el registro de sellos es de solo lectura para ellos (A5 H7).

### 4.6 `postcompra`, `infra`, `agentes`, `dashboard` (B7-B10)

| Pieza | Interfaz |
|---|---|
| Worker `infra/workers/fulfill` (B7) | encolado por `webhook-stripe`: si `paid` y sin entrega previa (KV por `session_id`) → enlace (`DESCARGA_HMAC`, `entrega.enlace_vence_dias`, `enlace_max_descargas`), correo transaccional y `POST api /ingesta/entrega` |
| `postcompra.reembolsar` · `metricas` (B7) | `--session cs_… --motivo M [--live]`: revalida contra Stripe (`rk_reembolso`), garantía, `reembolso_auto_max`, `reembolsos_auto_max_por_dia`, disputa abierta · `--oferta`: si reembolsos o disputas superan `salud_operativa.*` o `ratio_disputas_pausa`, escribe `senal_pausa.json`. `ProveedorCorreo` con `ResendCorreo` y `SimuladoCorreo` (outbox local) |
| `scripts.preflight` → `infra.preflight` (B8) | `--modo {completo,ligero,e2e_prueba}`: 43 ítems de `infra/plantillas/preflight-items.yaml`; escribe y firma `estado.json`; **0 VERDE · 4 AMARILLO/ROJO · 3 entradas inválidas** (D-08) |
| `infra.latido` · `kill` · `simulacro` · `variables` · `respaldo` (B8) | latido firmado (`LATIDO_HMAC`) cada `watchdog.latido_cada_min` · `PAUSA` + `pausar` + alerta por dos canales · harness de A-1…A-12 · compara el manifiesto de variables con el entorno y regenera `.env.example` (D-13) · `pg_dump` cifrado a R2 |
| `infra/workers/{watchdog,descarga}` (B8) | cron `*/5`; **solo** `GET campaigns` y `POST status=PAUSED`, sin ruta de activación (404/405) · token HMAC y contador KV de descargas. CI en `.github/workflows/`: pruebas, `gitleaks`, sonda de hooks; nada que mueva dinero corre en Actions |
| `agentes.runner` · `sonda_hooks` · `perfil` (B9) | `--espec espec.json [--fixture DIR] [--live]` (un proceso `claude -p` por rol, A5 §3.1) · entradas sintéticas que **deben** dar `exit 2` · imprime `settings.efectivo.json` y el entorno sin secretos. `preparar(espec) -> PlanCorrida` (puro), `ejecutar(espec, *, modo, fixture_dir) -> ResultadoCorrida`. Hooks en `agentes/hooks/`: `pretooluse_gasto`, `pretooluse_activacion`, `posttooluse_registro`, `stop_verificacion`, `_comun`, `herramientas.yaml` (lo desconocido es escritura). `contexto.py` fija por etapa: lecturas, rutas escribibles, scripts permitidos, esquema de salida |
| `dashboard.build` · `alertas` · `api` (B10) | `--salida empresa/dashboard [--oferta OF]` (HTML estático escapado) · evalúa `dashboard.*` y `salud_operativa.*` → `alertas.jsonl` · WSGI de la biblioteca estándar que monta los controladores de `datos`; `GET /salud`, `GET /estado` firmado. El botón `POST /ofertas` no se construye |

`infra_estado.modo` ∈ `vivo|prueba|simulado`; los hooks y `guard` rechazan los dos últimos para gastar o activar. Los hooks escriben en un *spool* que el motor ingiere (D-14).

### 4.7 Endpoints Worker ↔ motor (servicio `api`)

Autenticación interna: `X-Fabrica-Ts` (UTC ISO con `Z`) y `X-Fabrica-Firma: hmac-sha256=<hex>` = HMAC-SHA256 de `ts + "." + cuerpo_exacto` con `INGEST_HMAC_SECRET`, comparación en tiempo constante. Se rechazan marcas fuera de `ingesta.tolerancia_seg` (400), firma inválida (401), `event_id` repetido con contenido distinto (409) y cuerpos sobre `ingesta.cuerpo_max_bytes`; idéntico → 200 `duplicado`. Stripe usa su propia firma.

| Endpoint | Origen | Cuerpo | Efecto |
|---|---|---|---|
| `POST /ingesta/evento` | Workers `eventos`, `capi` | `{event_id, oferta_id, tipo ∈ PageView·ViewContent·InitiateCheckout·Purchase, ts, visitor_id, cid, asid, adid, fuente ∈ pixel·capi·landing, consentimiento, valor_minor?, moneda?}`, sin datos personales | `INSERT … ON CONFLICT(event_id) DO NOTHING` en `fact_evento` |
| `POST /ingesta/entrega` | `fulfill` | `{checkout_session_id, oferta_id, estado ∈ encolado·enviado·entregado·fallido, intento, producto_sha256, ts}` | upsert en `fact_entrega` → `entregas.jsonl` |
| `POST /webhooks/stripe` | Stripe, destino `finanzas` | snapshot de los eventos de A3 §2.3 | verifica firma, `stripe_evento` único por `event.id`, `aplicar_stripe` |
| `POST /ordenes` | `orq firmar` (terminal del dueño) | `{accion, oferta_id, etapa?, hash_objetivo, ts, nonce}` firmado Ed25519 | verifica con la pública, rechaza `nonce` repetido, registra la firma; no activa nada por sí |
| `POST /ingresar` | `orq ingresar` remoto (alternativa: `railway run`) | lo mismo que el CLI | validación idéntica al flujo con IA |
| `GET /estado` · `GET /salud` | watchdog · Railway · hooks · dueño | — | firmado · mínimo; los hooks lo leen con *fail-closed* si no responde en < `agentes.hook_timeout_s` |
| `POST /latido` (en el **watchdog**) | motor | `{ts, estado_generado_en, semaforo, pausa, version}` con `LATIDO_HMAC` | KV `latido:ultimo` |

### 4.8 Base de datos

SQLite en desarrollo y pruebas; Postgres en producción (Railway, red privada, sin proxy público). Dialecto portable: `TEXT`, enteros de 64 bits, booleanos `INTEGER 0/1`, instantes `TEXT` ISO con `Z`, JSON como `TEXT`, **ningún `FLOAT`**, `INSERT … ON CONFLICT`. Controlador de Postgres: `pg8000` (puro Python), declarado en `datos/requirements-extra.txt` `[VERIFICAR en Python 3.15 antes de entregar]`. **El estado vivo del motor (PAUSA, estado de las ofertas, registro encadenado, spool) vive en UN almacén propiedad del motor desde el día 1** (D-21): tablas `control(clave PK, valor, version)`, `fact_estado_oferta`, `registro(seq PK, hash, hash_previo, json)`. Para el primer testeo basta **SQLite en un volumen de Railway** del servicio `motor` (una réplica, `RAILWAY_RUN_UID` fijo; Postgres desde N3); `ofertas/<id>/` y `empresa/` en disco son una **vista exportada** y Git es el libro de versiones aprobadas. Hechos verificados (https://docs.railway.com/reference/volumes, 2026-11-06): las réplicas no pueden usar volúmenes y hay una breve caída al redesplegar un servicio con volumen; que el sistema de archivos sin volumen se borre en cada despliegue es lo que supone la crítica y queda `[VERIFICAR]`. `PAUSA` = fila `control('pausa')` + KV del watchdog + archivo espejo (se escriben y verifican los tres); ítem de preflight `R-06`: «el almacén persiste tras un redeploy» (centinela, redespliegue en `pruebas`), crítico. `pg_dump` no respalda archivos: el respaldo cubre el almacén. El registro encadenado se ancla: el motor firma el hash de cabeza cada 100 líneas o cada hora (HMAC `REGISTRO_HMAC`, clave que el runner no tiene) y lo publica en el KV del watchdog (`registro:cabeza`).

| Tabla | Clave | Columnas principales | Índices |
|---|---|---|---|
| `dim_oferta`, `dim_campana`, `dim_conjunto`, `dim_anuncio` | `oferta_id` · `campaign_id` · `adset_id` · `ad_id` | locale, moneda, macro_nicho · nombre, fase, estructura · · `ad_name, concepto_id, hook_id, formato, version` | `(oferta_id)` |
| `fact_meta_ad_dia` | `(ad_id, fecha)` | `moneda, tz, gasto_minor, impresiones, clics_enlace, lpv, pull_ts` (`fecha` = día de la zona `tz` de la cuenta; convenciones §4) | `(fecha)` |
| `fact_meta_conv` | `(ad_id, fecha, ventana)` | `compras_meta, valor_meta_minor` (aparte: el gasto no depende de la ventana) | — |
| `fact_evento` | `event_id` | `oferta_id, adid, asid, cid, visitor_id, tipo, fuente, ts, consentimiento, valor_minor` | `(oferta_id, ts)`, `(visitor_id)` |
| `stripe_evento` | `event_id`, `UNIQUE(tipo, objeto_id)` para `checkout.session.completed`, `charge.refunded`, `charge.dispute.*` | `tipo, livemode, objeto_id, destino, recibido_en, procesado_en, payload_sha256` | `(objeto_id)` |
| `fact_pedido` | `session_id` | `oferta_id, cid, asid, adid, visitor_id, bruto_minor, impuesto_minor, fee_minor, moneda, bump_tomado, metodo, pais, email_hmac, estado, interno, livemode, verificacion, pagado_en` | `(oferta_id, pagado_en)`, `(adid)` |
| `fact_reembolso`, `fact_disputa`, `fact_entrega` | `refund_id` (con `UNIQUE(session_id)` para el reservado), `dispute_id`, `session_id` | `session_id, monto_minor, moneda, regla, ts, dia_utc, estado ∈ reservado·ejecutado` · estado, intentos, `producto_sha256` | `(session_id)`, `(dia_utc, estado)` |
| `fact_costo`, `fact_decision` | `costo_id`, `decision_id` | `oferta_id, origen, monto_minor, ts` · `objeto_id, accion, codigo, regla, ejecutada` | `(oferta_id, ts)` |
| `fact_estado_oferta`, `fact_conexion`, `fact_qa` | compuestas | estado por etapa; semáforo por componente; veredictos de QA | `(oferta_id, ts)` |
| `raw_meta_insights`, `tipo_cambio` | `pull_id` · `(par, fecha)` | cuerpo y `hash_contenido` (append-only) · `tasa` (cadena), `fuente`, `tipo_cambio_id` | `(oferta_id, pull_ts)` |

**Reembolso automático (algoritmo de `postcompra.reembolsar`, B04):** (a) una transacción (`BEGIN IMMEDIATE` en SQLite; `SERIALIZABLE` o `pg_advisory_xact_lock` en Postgres) inserta `fact_reembolso(session_id, estado='reservado', monto_minor, dia_utc)` con `UNIQUE(session_id)` y cuenta `WHERE dia_utc = :hoy AND estado IN ('reservado','ejecutado')`; si supera `reembolsos_auto_max_por_dia`, `ErrorLimite`; el día es **UTC**; (b) lee `charge.amount_refunded` en Stripe y rechaza si `amount_refunded + monto > min(charge.amount, reembolso_auto_max)` (el tope aplica al acumulado del pedido) y compara monedas antes de importes; (c) llama a Stripe con la clave de §N14; (d) marca `ejecutado` con `refund_id`; si el proceso muere entre (c) y (d), el reintento lista los `refunds` del `payment_intent` antes de crear otro (Stripe puede podar claves de idempotencia a partir de 24 h; verificado 2026-11-06). Pruebas: dos reembolsos paralelos con motivo distinto → uno; reintento tras 25 h simulado → ninguno nuevo; contador diario con 2 hilos.

La unión Meta↔Stripe es siempre `oferta_id` + `adid`; `email_hmac` usa HMAC con clave propia. `fact_balance_tx` y `fact_payout` (F1) no hacen falta en B0.

### 4.9 Dependencias y orden

Todos importan el núcleo de `engine`. `engine.orq` usa `agentes.runner`, `compliance.verificar_sello`, `meta.activar`, `datos` y `decision` por Protocolos inyectables (en pruebas, fakes). `meta.*` y `landing.desplegar` consultan `compliance.verificar_sello`. `datos` usa `meta.insights`, `decision.PedidoStripe` y los mensajes de `postcompra`. `dashboard` lee `datos` y `engine.estado`. `infra.kill` invoca `meta.pausar`; `watchdog`, `tracking` y `infra/workers/*` son JS puro y dependen solo de contratos JSON. **Orden:** ola 0 (B1-núcleo, ≤ 1 sesión) → ola 1 (10 constructores en paralelo contra estas firmas) → ola 2 (I1, R1, RB) → ola 3 (pruebas con el dueño, §9).

### 4.10 Topología N0-N2 (D-20; propuesta a confirmar por el dueño)

| Pregunta | Respuesta propuesta |
|---|---|
| ¿Dónde corre el motor? | Servicio `motor` de Railway desde el primer testeo (el latido exige un proceso siempre encendido: un Mac dormido pausaría las campañas cada `watchdog.latido_max_min`). El Mac es cliente. |
| ¿Dónde viven `ofertas/` y `empresa/` vivos? | Almacén del motor (§4.8) en un volumen; Git es el libro de versiones aprobadas (rama `datos` sin secretos) y la fuente de código, skills y plantillas. |
| ¿Cómo firma el dueño? | `orq firmar` en su terminal con la clave **privada** Ed25519 y `POST api /ordenes` (§4.7). |
| ¿Cómo entra lo hecho en la pestaña Code? | `orq ingresar` (§4.2) o `railway run`. |
| ¿Cómo ve el estado? | `GET api /estado` firmado, `orq estado --exportar` y, mientras no haya login, el HTML de `dashboard.build` descargado. |
| ¿Cómo se entera de una pausa? | Dos canales independientes (correo + push; proveedor push = decisión pendiente del dueño, §9). |

Alternativa válida si el dueño prefiere **motor local** en el primer testeo: sin latido automático sino **latido del operador** (`orq presente`, firmado, una vez por jornada; sin latido en `latido_max_h` horas se pausa), con `spend_cap` y tope diario como candados duros. Una de las dos debe quedar escrita antes de la ola 1: B3, B8 y B10 construyen cosas distintas según la respuesta.

---

## 5. Máquina de estados de una oferta

Coherente con `contratos/estado.schema.json` y `docs/contratos.md` §3. **Solo el motor escribe** `estado.json` (bloqueo optimista por `revision`; permisos del SO, no solo `deny`).

**Etapa.** `pendiente → en_progreso → en_QA → aprobado`; `bloqueado` (falta input, credencial o API; vuelve a `en_progreso` al resolverse) y `escalado` (2 rondas con BLOQUEANTE o MAYOR, `ESCALAR` o veto de X1; sale solo por orden humana). «Gate pendiente» es un booleano dentro de `en_QA`. `en_progreso → en_QA` exige salida válida; `en_QA → en_progreso` con FAIL o MAYOR abierto y `ronda_qa < max_rondas_qa`; `aprobado → pendiente` con `obsoleta=true` si una entrada cambia (se conserva la versión previa). *Reintentos:* técnicos hasta `orquestador.reintentos_tecnicos` con espera `espera_reintento_min`; salida inválida hasta `agentes.reintentos_validacion_max` reparaciones (no cuentan como ronda de QA); `timeout_etapa_min` marca `bloqueado`. *Gate efectivo* = `contratos/gates.json` con el **menor** nivel entre oferta, etapa y `autonomia.yaml`.

**Fase de la oferta.**

| De → a | Guarda | Quién |
|---|---|---|
| `borrador → en_construccion` | brief firmado y primera etapa `en_progreso` | motor |
| `en_construccion → listo_para_activar` | D1-D7 `aprobado` y vigentes (hashes), `campana.estado = aprobada`, sello de X1 vigente, infra VERDE `vivo` | motor |
| `listo_para_activar → en_test` | acción `activar_campana` con gate, `guard` y relectura de Meta | `meta.activar` |
| `en_test → pausada` | `PAUSA`, `infra.kill`, guardarraíl G2/G3 de D8, `senal_pausa`, deriva detectada por X1, watchdog | automático: pausar nunca espera a un humano |
| `pausada → en_test` | `reactivar_tras_pausa` (**H en todos los niveles**), preflight VERDE, hashes y límites revalidados | humano |
| `en_test → fallida` | FALLIDA de `evaluar_oferta_validada` (gasto ≥ `k_min_fallida` × equilibrio y P(CPA ≤ equilibrio real) ≤ 0,05) | motor; cierra la campaña |
| `en_test → inconclusa` | tope de la celda alcanzado sin veredicto (`tope_sin_veredicto`, `tope_con_datos_dudosos`, `tope_sin_clics`) | motor |
| `inconclusa → en_test` | extender **una** vez, con tope nuevo dentro de `limites` | humano (H) |
| `en_test → validada` | VALIDADA sobre cohorte **madura** (último pedido considerado + garantía + `madurez_dias_extra`, no antes de `espera_madurez.hasta`) y confirmación H (`accion:confirmar_validada`) | motor + humano |
| `fallida → en_construccion` | reabrir con evidencia nueva (`accion:reabrir_fallida`, `origen_version=humano`) | humano (H) |
| `validada → escalando` | fuera de alcance (D9) | — |
| cualquiera `→ retirada` | decisión del dueño; cierra campaña | humano |

Solo `retirada` es final; `fallida` admite reapertura firmada (un FALLIDA con vista provisional puede ser falso). **PROMETEDORA no es una fase**: la oferta sigue `en_test` hasta madurez o tope (D-11). **Campaña:** `borrador → preflight_ok → aprobada → activa ↔ pausada → cerrada`; crear es borrador (nunca entrega), `preflight_ok` = P01-P24 verdes con `hash_config`, `aprobada` = firma H + sello X1, `activa` solo por `meta.activar`.

| Acción de `decision` | Efecto determinista |
|---|---|
| `MATAR` (anuncio) | pausar el anuncio y registrar `decision_id`; no toca la oferta |
| `MATAR` (`oferta_mercado`) | fase `fallida` y campaña `cerrada` |
| `INCONCLUSO` | **pausar la campaña** (`ejecutor.pausar`; una oferta inconclusa al tope no puede seguir gastando hasta el `spend_cap`), fase `inconclusa` con responsable (entrega, embudo u oferta) y señal al dueño |
| `ESCALAR` | solo se **registra** la propuesta |
| `SEGUIR` · `BLOQUEADO` | nada (salvo la regla siguiente); `BLOQUEADO` (sin tope, moneda distinta, datos inválidos) ni gasta ni decide |

**Gasto efectivo y tope de la celda (B05).** El tope de la celda (D-12) es un umbral de **decisión**, no un freno: el gasto leído llega con atraso (lectura cada `optimizacion.lectura_horas`, resultados maduros a ~48 h) y Meta puede gastar hasta 1,75 × el diario en un día. Por eso `en_tope` usa `gasto_efectivo = gasto_leído + 1,75 × diario × (horas_sin_lectura / 24)`, nunca el gasto leído, y D8 pausa al llegar a `tope − 1,75 × diario` si no hay lectura fresca. El freno real es el `spend_cap` de la campaña, que `meta.payloads` fija ≤ ambos límites por construcción (`total_test_max`, N06); si el `spend_cap` calculado queda por debajo del mínimo de Meta para campañas (≈ 100 USD «o equivalente local», y `922337203685478` para quitarlo; https://developers.facebook.com/docs/marketing-api/reference/ad-campaign-group, leída 2026-11-06 — monto exacto `[VERIFICAR]` como `campana.spend_cap_minimo_meta`), el borrador usa `stop_time` + `lifetime_budget` del conjunto como candado y registra `spend_cap = null` explícito (`candado_alternativo`; cambio de esquema pendiente en CT).

**Pausa, kill y rollback.** `empresa/PAUSA` (capa 1; fuente = almacén del motor, espejo en KV del watchdog y archivo, D-21) detiene gasto, activación, publicación, marketing y reembolsos automáticos; **no** la entrega ni los correos transaccionales (R17); borrarla no reactiva nada. Capa 2: `meta.pausar` (≤ `orquestador.pausa_global_max_min`). Capa 3: `spend_cap` fijado por el dueño en Meta. `infra.kill` encadena las tres y avisa por dos canales. Los artefactos aprobados no se sobrescriben: volver atrás es crear `v(n+1)` copia de `v(n-1)` con `origen_version=humano`, lo que vuelve obsoletas a las dependientes. Landing: `--rollback-a landing-v<n>`. Meta: los creativos son inmutables; rollback = pausar el anuncio y crear otro. En este alcance no se edita presupuesto en vivo.

---

## 6. Modo prueba y hito B0

### 6.1 Interruptores y sustitutos

`FABRICA_ENTORNO=prueba` rechaza `--live` (código 4); `FABRICA_RAIZ` apunta a una carpeta temporal con copia de `ofertas/_ejemplo`, `tests/fixtures/engine/empresa_prueba/` y las plantillas, así el `empresa/` real **no se toca** (se comprueba por hash); `--modo fixture` evita procesos `claude` y red; `MODO=prueba` en los Workers usa `STRIPE_WHSEC_TEST` y `test_event_code` y rechaza claves `live`; `infra_estado.modo=prueba` es no vivo (por eso el caso positivo de B0-13 usa `comprobar_live(simulacion=True)`, §4.2); el reloj se inyecta y avanza por escenario: latido, ventana de 72 h y madurez (hasta `fin + 21` días tras cerrar la campaña) corren en segundos.

| Real | Sustituto | Demuestra | No demuestra |
|---|---|---|---|
| `claude -p` por rol | fixture de A5 §12.8 (10 casos) | validación, promoción atómica, rondas, escalado, bucles, PAUSA a mitad, costos, hooks cargados | calidad del contenido; costo real |
| Stripe | eventos `checkout.session.completed`, `charge.refunded` y duplicados **firmados** con un `whsec_` ficticio; opcional `stripe trigger` en el sandbox del dueño | firma, tolerancia, deduplicación, entrega única, atribución, ledger, reembolso por regla | la página de pago, 3DS, métodos reales |
| Meta | `ClienteMeta` con `TransporteFixture`: borradores `PAUSED` con ids sintéticos, insights de 14 días, error 613 | nombres y UTM, payloads, borrador sin entrega, preflight, hash y `object_ids`, pausa idempotente, ETL | aprobación de anuncios, aprendizaje, entrega real (prueba A-9 con el dueño) |
| Correo, R2, KV, cron, Railway | `SimuladoCorreo` (outbox), carpeta local, dict, llamada directa con reloj, SQLite | plantilla, enlace con vencimiento y cuota, latido y watchdog, upserts | entregabilidad (SPF/DKIM/DMARC), cuotas de plataforma |
| Consentimiento | `html_checks` y Playwright opcional `[VERIFICAR]` | ningún pedido a Meta antes de aceptar | cada navegador |
| Mercado | datos sintéticos del ejemplo (es-ES, EUR) | que el código no depende de un país | rentabilidad de un mercado |

### 6.2 Hito B0 «esqueleto caminante»

`python -m scripts.b0_e2e` (I1) copia `ofertas/_ejemplo/` y las fixtures a una raíz temporal; el motor, con agentes en modo fixture, recorre D1→D7, activa en un Meta simulado, opera 14 días simulados con compras sintéticas, emite veredicto y cierra, verificando estado, registro e invariantes en cada paso. Corre en < 5 minutos, sin red ni credenciales, dentro de `scripts/test_all.sh`. **B0 se logra solo si pasan los 25 criterios (B0-01…25):**

| # | Criterio | Verificación |
|---|---|---|
| B0-01 | `test_all.sh` y `lint.sh` salen 0; ninguna prueba abre un socket | ejecución con `socket` bloqueado |
| B0-02 | `validar_esquemas` 0 con `_ejemplo` re-sellado; `engine.factibilidad.calcular` reproduce su `economia.json` y los vectores 24,42 · 16,25 · 11,54 de A4 | vectores (D-01) |
| B0-03 | límites en `null` → 5; `PAUSA` → 4; `estado.json` de 7 h → 4; `modo≠vivo` → 4; `--live` fuera de producción → 4; dry-run → 0 y árbol sin cambios | casos límite × {dry-run, live simulado} en cada CLI con efecto |
| B0-04 | el `empresa/` real queda intacto | hash antes y después |
| B0-05 | M1→D7 `aprobado` con gates H firmados con la clave de prueba; un FAIL→ronda 2→PASS y un caso de 2 rondas fallidas → `escalado` | `estado.json` válido tras cada paso |
| B0-06 | cada etapa ejecutada dos veces da los mismos hashes y la segunda dice «reutilizado» | `hash_salida` y registro |
| B0-07 | cambiar `oferta.json` vuelve obsoletas D4-D7 y pausa la campaña activa | propagación |
| B0-08 | los 10 casos del runner; sonda de hooks 100 % `exit 2`; el entorno del hijo sin claves prohibidas | `tests/agentes/` |
| B0-09 | sesión con `metadata` completa y precio solo del catálogo; firma falsa → 400; duplicado → una entrega; `event_id` correcto en CAPI | `node --test` |
| B0-10 | pago simulado → `entregas.jsonl` en `entregado`, correo en outbox, enlace con vencimiento y cuota; el duplicado no reenvía | `tests/postcompra/` |
| B0-11 | `landing.validar` pasa en el ejemplo (con las **siete** páginas legales, banner y `pixel.js` cargado solo por `consentimiento.js`, ver §8 CT) y falla el 100 % de las **12 mutaciones** del catálogo `tests/fixtures/contratos/mutaciones_landing/catalogo.json` (8 base `ML-01…08` + 4 complementarias `MC-01…04`; `aplicar_mutacion_landing.mutaciones(True)`; cada una dispara la regla que el catálogo declara): precio distinto en HTML, moneda distinta, garantía distinta, legal ausente (1 de 7), enlace roto, píxel en `<head>` sin condición, dato de salud en `tracking.json` o en el título, casilla premarcada, script de terceros, enlace externo no declarado en `rutas.json` y la palabra EJEMPLO visible | defectos sembrados |
| B0-12 | `meta.crear` deja todo `PAUSED` y es idempotente; `meta.preflight` detecta cada P rojo | fixtures de Meta |
| B0-13 | `meta.activar` rechaza sin sello, con hash distinto, con `object_ids` de más, sin firma y con `PAUSA`; acepta el caso correcto en `modo=fixture`; los siete pasos reales de `guard` tienen una prueba por paso con entorno y reloj inyectados; falla el segundo POST → pausa | 5 negativos + 1 positivo + 7 pasos |
| B0-14 | latido detenido → pausa simulada y alerta por ambos canales; el watchdog no tiene ruta de activación | `node --test` + reloj |
| B0-15 | ETL de 14 días dos veces → tablas idénticas; cobertura de `adid` ≥ `landing.captura_adid_min_pct`; Stripe↔ledger = 0 | `tests/datos/` |
| B0-16 | tres escenarios con el desenlace esperado y tasas dentro de A4 §5.3 (incluidos los escenarios con cobertura 95 % + retraso, docs/08 §5.3); una celda con diagnóstico «CPM alto» que **no** mata; el reloj simulado avanza hasta `fin + 21` | §6.3 |
| B0-17 | el dashboard refleja las cifras de la base, escapa todo texto y tacha las viejas | HTML contra valores esperados |
| B0-18 | `verificar_cadena` sin roturas; costos = suma de corridas; 0 datos personales en registros y logs | patrones de correo, IP y tarjeta |
| B0-19 | `senal_pausa` por reembolsos > `salud_operativa.reembolsos_pausa_pct` → D8 pausa y `consumida_por` se llena | escenario |
| B0-20 | con disputa abierta el reembolso automático se rechaza; `postcompra.evidencia` produce el paquete; dos disputas empujan `senal_pausa` sobre `ratio_disputas_pausa` y D8 pausa | escenario |
| B0-21 | un anuncio `DISAPPROVED` simulado produce pausa del anuncio, registro, pedido a D6 y ninguna recreación idéntica; dos en 7 días congelan lanzamientos | `meta.monitor` |
| B0-22 | tras cerrar la campaña: gasto = 0, ETL y veredicto continúan y `VALIDADA` no aparece antes de `espera_madurez.hasta` | reloj simulado |
| B0-23 | `orq ingresar` con los artefactos grabados de una etapa produce el mismo `hash_salida`, el mismo `estado.json` (salvo `origen_version=humano`) y el mismo registro que `orq ejecutar --modo fixture`; un archivo fuera de ruta se rechaza (3) | fixtures |
| B0-24 | los parsers de `datos` y `meta` pasan con fixtures de **forma real** capturadas (lectura, sin gasto) con el MCP de Meta y el sandbox de Stripe (`tests/fixtures/{meta,datos}/reales/`, recortadas, sin datos personales, con fecha) | captura MA-20 |
| B0-25 | una orden firmada recibida por `POST /ordenes` produce el mismo estado que `orq firmar` local; `nonce` repetido → rechazo | `tests/engine/` |

### 6.3 Escenario de punta a punta sobre `ofertas/_ejemplo/`

El ejemplo («Mi Regreso Laboral», es-ES, EUR; caso verde de dinero) ya trae artefactos válidos de D1-D7 y un borrador de campaña. I1 agrega un generador determinista de insights de Meta y eventos de Stripe (semilla fija).

1. **Preparar** la raíz temporal con `limites` de prueba firmados, infra VERDE `modo=prueba` y `autonomia` N2. *Primero los negativos:* con `limites` de plantilla (todo `null`), `orq ejecutar --live` sale 5.
2. **Recorrer** D1, M1, D2…D7 con salidas grabadas y gates H firmados con la clave de prueba. Inyecciones: un FAIL reparado en la ronda 2; un Maker que escribe fuera del staging (corrida descartada); una salida con `float` (rechazada).
3. **Sellar y armar:** X1 sella D5, D6 y D7; `meta.crear` produce el borrador; `meta.preflight` da `hash_config`.
4. **Activar:** sin sello, con hash alterado y con un `object_id` extra → rechazados; el intento correcto deja `ACTIVE` en el simulador y fase `en_test`.
5. **Operar 14 días simulados**, una lectura diaria con ETL doble: pedidos con `adid`, un reembolso, una compra de prueba excluida, un webhook duplicado y uno de firma falsa.
6. **Tres desenlaces** (mismo código, tres semillas): **A** perdedor severo → `MATAR` tras ≈ 3-4 × CPA de equilibrio de gasto y fase `fallida`; **B** ganador fuerte → `ESCALAR` registrado, `PROMETEDORA` y, con la cohorte madura (último pedido + garantía + 7 días; el reloj avanza hasta `fin + 21`), `VALIDADA` con confirmación H; **C** intermedio → `INCONCLUSA` al tope. Cada uno corre además 160 réplicas de `decision.simulacion`.
7. **Fallas en operación:** `PAUSA` a mitad de ventana (nada gasta, la entrega sigue); latido detenido; `estado.json` vencido (D8 no actúa); ETL caído (cifra tachada).
8. **Cerrar:** `orq cerrar`, post-mortem, dashboard, `verificar_cadena`, `empresa/` real sin cambios.

---

## 7. Niveles de autonomía y ejecución de los agentes

### 7.1 Qué se automatiza en cada nivel (este plano construye hasta N2)

| Nodo | N0 | N1 | **N2** | N3 | N4 |
|---|---|---|---|---|---|
| D0 infra | dueño a mano | Maker genera checklist; dueño ejecuta | preflight diario por script; **H** firma «infra verde» | preflight habilita activar dentro de topes | + revisión semanal |
| O0 brief, M1, D1 | dueño en Code | Maker con skill; dueño revisa todo | Maker + QA; **H** | S (H si país o idioma nuevo) | botón |
| D2, D4, D6 | dueño en Code | Maker; dueño revisa | Maker + QA + X1; **S** | S | A |
| D3, D5 | dueño | H | código genera y valida; **H** (oferta; publicar con sello) | S | S |
| D7 | dueño | H | borrador por script; **H** firma y activa | activa con regla pre-aprobada | A con ventana de veto |
| D8, D10, F1, F2 | manual | revisión diaria a mano | **A**: pausa y reembolso por regla, ETL y KPI | A | A |
| Kill switch | `PAUSA` manual | igual | tres capas y watchdog | igual | igual |

El **runner no carga conectores MCP** (`ANTHROPIC_API_KEY`, A5 H2): «MCP hasta N2» vale solo para la sesión Code del dueño. Por eso D2 (Biblioteca de Anuncios) y D6 (Higgsfield) son **semiasistidos**: su Maker corre en esa sesión o con insumos grabados, y el resto del pipeline es idéntico.

### 7.2 Cómo se ejecuta un agente (A5)

El motor arma una `EspecCorrida` (etapa, rol, lecturas, rutas escribibles, scripts permitidos, esquema de salida, presupuesto) y llama a `agentes.runner`: preflight (PAUSA, infra, límites, versión de Claude Code, hashes de hooks y skills) → `claude -p --agent <id>-<rol>` con `dontAsk`, herramientas listadas, `--disallowedTools "mcp__*"`, `--json-schema`, tope de turnos y de presupuesto y entorno mínimo (solo `ANTHROPIC_API_KEY`) → vigilancia de timeout, bucles y PAUSA → **validación vinculante fuera del modelo** (esquema, hashes, diff del árbol) → promoción atómica de `staging` a `vN`. El QA es **otro proceso**, `Read, Grep, Glob`, sin `Write` ni acceso al razonamiento del Maker; el runner persiste su informe. Máximo 2 rondas; `ESCALAR` pasa a H. Un hook que falla bloquea (`exit 2`); `Stop` es una cortesía, no una garantía.

### 7.3 Qué se forja a mano y qué se construye como software

| Skills de criterio, forjadas en la pestaña Code | Software, construido acá |
|---|---|
| D3 oferta, D5 copy y brief de landing, D4 producto, D6 creativos, D7 estructura y audiencia, D2 validación, M1 mercado, X1 checklist y simulación de revisor, D1 | D0 (preflight, kill, watchdog), O0 (motor, estado, gates), F1 (ledger), F2 (KPI, dashboard), hooks, runner, ETL, Workers, `factibilidad`, `lint_claims`, reglas de matar y escalar, sellos |

Cada skill sigue el plan de forja: N0 a mano → pulir → `skill-creator` → evals con defectos sembrados → `v1.0.0` fijada en `skills_pin`. Orden para llegar antes a un testeo: **D3 → D5 → D4 → D6 → D7 → X1 formal → D2 → M1 → D1**, mientras B1-B10 construyen lo determinista. Hasta que cada skill exista, B0 usa salidas grabadas y el primer testeo real se opera en N0-N1 **entrando por `orq ingresar`**. Forjar D5 antes que D4 solo se hace con el producto de `_ejemplo` como entrada (D5 ← D4 sigue vigente en el DAG). Cada tabla de nivel se acompaña de una métrica mínima por etapa para pasar N0→N1→N2, tomada de §7 de cada especificación (`accion:ascender_nivel`).

---

## 8. Plan de construcción por olas

**Listo (común):** `test_all.sh` y `lint.sh` salen 0; README con CLI que funciona con fixtures; sin `float` de dinero ni números de dinero, plazo o porcentaje fijos; dry-run por defecto; casos límite (cero, tope, tope + 1, faltante, `PAUSA`, infra vencida) en dry-run y live simulado; variables nuevas pedidas a B8 en «Pedidos» del README. Tamaño: S ≈ 1 sesión, M ≈ 2-3, L ≈ 4+.

| Ola | Quién | Tareas | Depende de | Listo = | Pruebas exigidas |
|---|---|---|---|---|---|
| **−1 (hoy)** | dueño / A0 | `git init` y primer commit (línea base de `verificar_propiedad` y de `hash_scripts`); `.claude/settings.json` de piso (docs/09 §6: `deny` de las escrituras de Meta, Shopify y `Edit` de `limites`, `parametros`, `contratos`, `.claude`; `ask` de los `generate_*` de Higgsfield). Hoy las sesiones de construcción ya tienen conectores con escritura viva y ningún hook | — | sin esto no se abre la ola 0 | el dueño comprueba con `/permissions` (que la regla de servidor `mcp__claude_ai_Shopify` deniega todas sus herramientas y la forma de `Edit(...)` relativa o `//ruta`: `[VERIFICAR]`) |
| **0a** | **B1-núcleo** (S) | `engine/{errores,comun,limites,parametros,guard,registro,transporte}.py` + `tests/fixtures/engine/empresa_prueba/` | −1 | firmas de §4.2 importables; los 7 pasos de `guard` en orden | un caso por paso; cadena del registro; `guard(simulacion=True)` |
| **0b** | **CT** contratos (M) | `parametros` 1.1.0 (grupos **opcionales** `estadistica`, `agentes`, `ingesta`, `watchdog`), `economia` 1.1.0 (D-02, `limites_pendientes`, `resultado_esperado_central`, `recargos_bp`/`conversion_bp`, tarifas de LLC con `[SUPUESTO]`), esquemas de C13 (`aprobacion`, `ids_meta`, `preflight`, `sello`, `decision`, `ledger`, `conciliacion`, `tipo_cambio`, `postmortem`, `orden_firmada`, `traspaso`), `brief` (renombrar `presupuesto.test_*` a `test_total_max`, `test_diario_max` y exigir plan ≤ techo), `mercado` 1.1.0 (`fiscal.exposicion_aceptada`, MA-06), `campana` (`spend_cap` nullable con `candado_alternativo`, `edad_sugerida`/`edad_dura`), `engine.factibilidad.calcular` única y X14 que la llama; **regenerar y re-sellar `ofertas/_ejemplo/`** (economía, landing con siete páginas legales + banner + `pixel.js` + `rutas.json` + `consent_gating.plataforma = "banner_propio_v1"`) | 0a | `validar_esquemas` 0 con el ejemplo nuevo; vectores 24,42 · 16,25 · 11,54 | ejemplo válido/inválido por esquema con `.motivo.txt` |
| **0c** | I1 (S) + RB | esqueleto de `scripts/b0_e2e.py` con todos los componentes como fakes (falla hoy y se pone verde por criterio); `scripts/lint_estatico.py`; **RB adelantado**: `docs/10-runbook-testeo.md` (mañana, diario ≈ 20 min, semanal ≈ 1 h, incidentes, cierre) | 0a | los 25 criterios aparecen como pruebas rojas con nombre | `lint_estatico`: caso verde y rojo por regla |
| 1 | **B1** (L) | `estado`, `orq` (incl. `ingresar`, `nivel`, `/ordenes`), `python -m engine.propuestas {proponer,sellar}`, `factibilidad` única (con `null` no sale 5), `decision/entradas.py`, `d8` (espera de madurez), `ejecutor`, `cerrar`, `scripts/producto/*`, `scripts/validacion/veredicto_d2.py` | 0a-0c; fakes de `agentes`, `meta`, `datos` | B0-02, 03, 05, 06, 07, 16, 19, 22, 23, 25 | transiciones exhaustivas; vectores de economía; idempotencia; Maker fuera de staging |
| 1 | **B2** (M) | 4 Workers y `_lib` | contratos | B0-09 | `node --test`: firma, tolerancia, duplicado, precio manipulado |
| 1 | **B3** (L) | migraciones, `db`, ETL Meta y Stripe, ingesta, atribución, consultas, ledger, KPI | núcleo | B0-15 | doble ETL = tablas idénticas; SQLite (mismo SQL con marcador traducido para Postgres) |
| 1 | **B4** (M) | `generar`, `validar`, `catalogo`, `desplegar` (dry-run y rollback), plantilla desde `_ejemplo`, banner de consentimiento sin dependencias | contratos | B0-11 | mutaciones sembradas 100 %; ningún script de terceros antes del consentimiento |
| 1 | **B5** (L) | `nombres`, `payloads`, `monedas` (offset de Meta), `ClienteMeta`, `crear`, `preflight` P01-P24 (+ P: categoría especial coincide con X1), `activar` (N12), `monitor`, `pausar`, `insights` | núcleo; fake de `verificar_sello` | B0-12, 13, 21 | nombres y UTM contra `campana.schema`; 5 negativos de activación; «falla el segundo POST»; una prueba por moneda de la tabla de offsets; idempotencia; 613 |
| 1 | **B6** (M) | `lint_claims`, `html_checks`, `sellar`, `verificar`, cargador de reglas con `reglas_version` | contratos | B0-11, 13 | corpus adversarial; reglas alteradas → no corre; sello vencido o alterado |
| 1 | **B7** (M) | Worker `fulfill`, `reembolsar` (§4.8), `reembolso_manual`, `evidencia`, `publicar_producto`, `metricas`, `correo` (con texto de confirmación de renuncia al desistimiento cuando aplique) | núcleo | B0-10, 20 | duplicado, rebote, disputa abierta, tope diario, `PAUSA` (la entrega sigue, el reembolso automático no) |
| 1 | **B8** (L) | preflight (críticos primero: M-01…M-03, S-01, S-03, S-04, C-08, C-09, K-01, P-01), watchdog, descarga, `kill`, `latido`, `simulacro`, `variables`, `respaldo`, CI | núcleo | B0-03, 14 | A-1…A-12 simuladas; sondas fail-closed; `gitleaks` |
| 1 | **B9** (L) | `runner`, `hooks/*` (incl. `pretooluse_bash`), `perfil`, `sonda_hooks`, tabla de etapas, ampliar `.claude/settings.json`, 10 fixtures, prueba S-1 | núcleo | B0-08 | sonda 100 % deny; JSON roto o excepción → `exit 2`; entorno sin secretos; bucle y PAUSA |
| 1 | **B10** (M) | `build`, `alertas`, `api` WSGI, glosario de KPI | fakes de `datos` | B0-17 | HTML escapado; cifra vieja tachada; endpoints firmados |
| 2 | **I1** (M) | `b0_e2e` completo, generador de escenarios, captura de fixtures reales (B0-24), `verificar_propiedad`, `tests/integracion/` | ola 1 | B0-01…25 | B0 completo |
| 2 | **R1** (M) | revisión independiente: fail-closed, secretos, inyección, `float`, números fijos, propiedad; reconstruye B0 desde cero | I1 | informe sin BLOQUEANTES | revisión adversarial |
| 2 | **RB** (S) | completar `docs/10-runbook-testeo.md` (adelantado en 0c): rutina diaria, incidentes (PAUSA, token filtrado, cuenta restringida, webhook caído, deriva de hash), checklists de A3 §13 | I1 | el dueño ejecuta un simulacro con él | lectura guiada |
| 3 | dueño + I1 | A-1…A-12 en cuenta aislada, compra real mínima, **S-1** (corrida real mínima del runner con una skill de humo de 3 líneas y presupuesto de centavos: `system/init` lista hooks, `tools` sin `mcp__*`, la skill se invoca, el staging se valida; antes, actualizar Claude Code ≥ `agentes.claude_version_min`) y **E-1** (`e2e_prueba` de docs/07 §10.3), primer testeo en N0-N1 | §9 | §9 completo | evidencia en `empresa/infra/` |

### 8.1 Corte mínimo del primer testeo en vivo (N0-N1)

| Imprescindible | Puede esperar |
|---|---|
| `engine` núcleo + `ingresar` + `engine.propuestas {proponer,sellar}`; `decision` (hecho); `landing.generar/validar/desplegar`; `tracking` (crear-sesion, webhook, capi); `postcompra` (fulfill, descarga, reembolsar); `meta.crear/preflight/activar/pausar/monitor`; `compliance` (lint, sellos); `infra` preflight núcleo (≈ 20 ítems críticos), watchdog, `kill`; `datos` ETL mínimo + KPI; `.claude/settings.json` + hooks de gasto y activación | runner desatendido (`agentes.runner`, 10 fixtures), Postgres (SQLite en el volumen del motor), `api` pública con login, dashboard HTML (basta `orq estado`), preflight completo de 43 ítems, nivel *Full* de Meta, `respaldo` a R2 (copiar el volumen a mano al inicio), 6 de las 12 pruebas A (las críticas A-1, A-2, A-4, A-5, A-7 —puerta—, A-9 antes de gastar; las demás mensuales) |

**Queda para después:** D1 radar y Modo D, D9 y aumentos de presupuesto, soporte con IA y prueba social, email de marketing, comparación de mercados en vivo, métodos locales y fiscal, N3 con *Full* y usuarios separados, botón, X2, F1 con cierre mensual, panel web con login.

---

## 9. Qué le toca al dueño (en paralelo, sin pegar secretos en chats)

Los valores van desde donde el dueño los guarde (decisión suya; el sistema no los guarda ni los ve) al panel o a un terminal **propio** (`wrangler secret put`, `gh secret set`, panel de Railway; ayudante opcional `scripts/secretos_cargar.py`), nunca por una conversación con un modelo. Orden y tiempos: A3 §12.2 (ruta crítica 1→4→8→9→10→14→15→16; 23-33 h repartidas en 2-4 semanas `[HIPÓTESIS]`). Riesgo residual aceptado por el dueño (decisión 15): sin gestor de contraseñas, llaves físicas ni segundo administrador; los frenos de software no cambian. El 2FA que exija cada plataforma para crear credenciales sigue vigente, con el método que el dueño use.

| Acción del dueño | Desbloquea | ¿Bloquea construir? | ¿Bloquea testeo en vivo? |
|---|---|---|---|
| Meta: diagnosticar la cuenta deshabilitada, **una** cuenta limpia en portfolio verificado de la LLC, fan page, app, usuario operador, dataset por oferta, dominio verificado, token CAPI, `spend_cap`, DSA si hay UE | borradores, medición, capa 3 | no | **sí** |
| Stripe: claves restringidas por función (sin `sk_`), destinos de prueba y vivo con los eventos exactos, descriptor, catálogo de prueba; luego vivo y **compra real mínima con reembolso** | cobro, entrega, conciliación | no | **sí** |
| Cloudflare (zona por oferta, tokens, secretos de Workers), Railway (proyecto, variables), GitHub (organización y reglas) | despliegue, ETL, CI | no | **sí** |
| Correo transaccional (dominio, SPF/DKIM/DMARC, buzón de soporte); páginas legales (siete) y banner de consentimiento: plantilla generada por el sistema (D5/X1), el preflight comprueba que existan y respondan 200. Riesgo residual aceptado por el dueño (decisión 14): sin revisión legal humana; lo verificable lo automatiza X1 y lo fiscal lo cubre el contador | entrega; publicar landing | no | **sí** |
| Anthropic: workspace de Console con límite mensual y clave propia; Claude Code ≥ `agentes.claude_version_min` (la máquina tiene 2.1.205; el diseño exige 2.1.314, A5 H1) | runner en vivo | no | **sí** para etapas con IA desatendidas |
| **`limites.yaml`**, operación `gastar`: `moneda_limites`, `gasto_diario_global`, `gasto_diario_por_oferta`, `gasto_total_test_por_oferta`, `perdida_max_test_por_oferta`, `perdida_neta_acumulada_max`, `ofertas_en_test_simultaneas_max`, `limite_gasto_cuenta_meta`, `cuentas_permitidas`, `paises_permitidos`, `locales_permitidos`; para `activar`, además `precio_neto_minimo`, `politica_divulgacion_ia`, `ratio_disputas_pausa`, `politica_reembolso_dias`; `reembolso_auto_max*`, `creditos_max_*`, `max_budget_por_corrida_agente`; firmado con el sello (C07) | gastar y activar | no | **sí** (sin ellos, exit 5) |
| Aprobar los parámetros nuevos (`estadistica`, `ingesta`) tras ver B0; fijar la clave HMAC de firmas fuera del alcance de los agentes (C07) | gates firmados | no | **sí** |
| Forjar las skills en Code (≈ 40-45 h en D1-D7 y X1, plan de forja §4.3) | Makers reales | no | sí, o se opera a mano en N0-N1 |
| Decidir **moneda y zona de la cuenta de Meta** (irreversibles), primer mercado y primer idioma, antes de crear la cuenta y de generar las páginas legales (docs/07 paso 1b); decidir topología (D-20) y proveedor de alertas push | cuenta, legales, `moneda_limites` | no | **sí** |
| Por oferta: dominio (lo compra el dueño), zona, Pages, dataset, token CAPI, verificación, correo, `Product/Price`, secretos y **subir el `spend_cap`** (`alta-oferta.yaml`, 11 pasos) | D5 cerrable | no | **sí** |
| Fiscal: si el primer mercado cobra IVA a consumidores, firmar la exposición de ese país (`mercado.fiscal.exposicion_aceptada`) o no lanzar ahí; revisor nativo del idioma si hay obligación legal | M1 | no | **sí** en esos mercados |
| Responder disputas y reembolsos fuera de regla desde `soporte@` (y la bandeja de la fan page); guardar la clave privada Ed25519 solo en su equipo (se genera y queda ahí) y firmar con `orq firmar` | operación | no | **sí** |

**Tiempo total del dueño para el primer testeo `[HIPÓTESIS]`:** infra 23-33 h + D2-D7 a mano 48-72 h + operación 1-2 h por día durante la ventana + 4-5 semanas de espera de madurez (no 21 días). El «≈ 40-45 h» de arriba es solo la forja de la fase 2 del plan de forja y no incluye la fase 1 (≈ 85 h de pulido en docs/03).

**No bloquean** construir ni el primer testeo: régimen fiscal y Managed Payments **solo si el primer mercado no cobra IVA a consumidores o el dueño firma la exposición de ese país** (MA-06), métodos locales, una o varias fan pages, marca y dominio por oferta, líneas rojas (C04; `lineas_rojas` queda vacío), firma del brief por clic en N4 (C03), alertas push, nivel *Full* de Meta y qué mercado probar primero (se decide con datos propios). **Sí bloquean** un testeo en vivo los valores de `limites.yaml` listados (la pérdida máxima se fija desde los presupuestos de testeo: A4 §5 da un gasto medio de un perdedor severo ≈ 3,5 × el CPA de equilibrio, uno moderado ≈ 10 × y uno en el equilibrio ≈ 13 ×), la cuenta de Meta, los días de garantía y la moneda de los límites, que debe coincidir con la de la cuenta (C02).

---

## 10. Riesgos de la construcción

| # | Riesgo | Señal | Mitigación |
|---|---|---|---|
| 1 | Diez constructores divergen en interfaces | imports rotos al integrar | firmas congeladas, ola 0, Protocolos con fakes, `verificar_propiedad`, integración diaria de I1 |
| 2 | Dos economías (ya pasó: 1830 vs 1840) | falla la prueba de vectores | `engine.factibilidad` única; X14 la llama |
| 3 | Guardarraíl «de papel»: hook que falla abierto, `deny` esquivado por Bash | sonda de hooks < 100 % | `exit 2` ante toda excepción; permisos del SO; diff del árbol; sonda tras cada actualización de Claude Code |
| 4 | Una prueba toca red o credenciales reales | el socket bloqueado la rompe | `Transporte` inyectado; `FABRICA_ENTORNO`; CI sin secretos |
| 5 | Fixtures optimistas hacen creer que algo anda | B0 verde y fallos en vivo | columna «no demuestra» de §6.1; A-1…A-12 y compra real son obligatorias (ola 3) |
| 6 | Costo de IA descontrolado en pruebas | `costos.jsonl` crece | fixture por defecto; `max_budget_por_corrida_agente`; límite mensual en Console |
| 7 | La ruta crítica es de espera (verificación de Meta, primer pago de Stripe 7-14 días) | termina la construcción y no hay cuenta | el dueño arranca §9 hoy; la construcción no depende de ella |
| 8 | Sobreingeniería (Postgres, panel, N3); Python 3.15 sin ruedas para un controlador; 10 ms de CPU en Workers Free | el alcance crece; `pip` falla | estado en archivos hasta N3; `pg8000`; Workers Paid y `crypto.subtle` |
| 9 | Claves de parámetros duplicadas entre grupos; datos personales en logs o fixtures | prueba de claves únicas; patrón de correo o IP en el repositorio | `estadistica` solo contiene lo que no existe en `testeo` ni `veredicto` (D-03); `lint.sh` busca patrones; B0-18 |
| 10 | Secretos: el watchdog guarda una copia del token del **operador** y el motor la verificadora de firmas | un Worker comprometido gasta | A-7 es **puerta**; firmas asimétricas (D-23); token propio del watchdog; tarjeta virtual como capa 3 si el operador puede cambiar `spend_cap` |

---

## 11. Decisiones de integración

Contradicciones entre A2 (contratos), A3, A4, A5, A0 y el backbone, resueltas con una decisión explícita. Precedencia: backbone en **decisiones y principios**; para **nombres de claves, archivos y valores** manda `contratos/` + `empresa/*.yaml` (tabla de errata D-25 hasta que el coordinador aplique C08); luego convenciones > especificaciones de departamento (v1) > notas A3/A4/A5. «Hecho» = edición quirúrgica ya aplicada.

| ID | Conflicto | Decisión | Edición |
|---|---|---|---|
| **D-01** | **Dos fórmulas de economía.** `decision.presupuesto.economia_por_pedido` y D3 §3.4 usan `d·(neto + tarifa)` con IVA y Stripe Tax; la regla X14 de `validar_esquemas.py` y `_ejemplo/economia.json` usan `d·tarifa` sin ambos. Mismos insumos: MC 1830 frente a 1840 (EUR, centavos). A4 además calcula en `float` (convenciones §3) | Manda la especificación de D3. **Una sola implementación**, `engine.factibilidad.calcular` (enteros/`Decimal`, `ROUND_HALF_EVEN`); `economia_por_pedido` la envuelve, X14 la llama y `_ejemplo` se regenera y re-sella | Pendiente B1 + I1 (C14) |
| **D-02** | `parametros_desde_mapeo` exige `cpa_equilibrio_visto_minor`, `cpc_esperado_minor`, `conv_central`; `economia.schema` no los tiene | `economia` 1.1.0 agrega, opcionales, `tasa_iva_bp`, `stripe_tax`, `tarifa_meta_bp` (entradas) y `conv_central`, `cpc_esperado`, `cpa_be_visto` (salidas, cadenas). Mientras tanto `decision/entradas.py` los deriva del escenario central: `cpc = cpm / (1000·ctr)`, `conv = clic_compra_bp / 10000` | Pendiente B1 ola 0 (C16) |
| **D-03** | `decision/reglas.py` lee `estadistica.*` y A5 usa `parametros.agentes.*`; `parametros.schema` 1.0.0 es cerrado y no tiene esos grupos; `testeo.*` ya tiene `p_escala`, `n_dec`, `ventana_no_decidir_h`, `p_cierre_tope` y el esquema prohíbe repetir una clave entre grupos | Esquema 1.1.0 con grupos **`estadistica`** (solo lo que no existe: fuerzas de prior, `alfa_descarte`, `k_min_matar`, `nodos_cpc`, `potencia`, `precision_relativa`, `control_*`, `mercados_*`, `k_min_fallida`), **`agentes`** (claves de A5 §12.2; `null` hasta calibrar: el runner en vivo falla cerrado), **`ingesta`** (`tolerancia_seg`, `cuerpo_max_bytes`) y **`watchdog`** (`latido_cada_min`, `latido_max_min`). `decision/entradas.py` toma de `testeo` `p_escala`, `ventana_no_decidir_h`, `n_dec` (= `n_min_escala`) y `alfa_descarte_tope = 1 − p_cierre_tope`, y de `veredicto` las compras mínimas, la madurez y el reembolso máximo | Pendiente B1 ola 0 (C15) |
| **D-04** | Arquitectura §4.1 separa M1-a y M1-b; `contratos/estado` define M1←D1 y D2←D1,M1 | Una sola etapa M1 antes de D2, como en el contrato ejecutable; precios por moneda y métodos se confirman en D3/D5 y se validan con X14 y `checkout`. M1 no tenía especificación al decidirse (C09; hoy existe `departamentos/16-mercados-localizacion.md`) | Aquí |
| **D-05** | Convenciones §3 prohíben `float` para dinero; A4 usa CPC y probabilidades `float` y `Decision.a_dict()` los emite | `float` solo como tasa en memoria dentro de `decision/`; lo persistido (`decisiones.jsonl`, `economia.json`, base) usa enteros, puntos básicos o cadenas, vía `decision.entradas.serializar` y comprobado con `buscar_floats` | Pendiente B1 |
| **D-06** | `FABRICA_ENTORNO` (convenciones) frente a `MODO` (Workers, A3) frente a `infra_estado.modo` | `FABRICA_ENTORNO` ∈ `desarrollo·prueba·produccion` rige los CLI; `MODO` ∈ `vivo·prueba` rige los Workers (`produccion` ↔ `vivo`); `infra_estado.modo` ∈ `vivo·prueba·simulado`. `--live` exige los tres coherentes | **Hecho** (convenciones §9) |
| **D-07** | A3 exige `modo`, `commit`, `hash_scripts` y campos por ítem en `estado.json`; `infra_estado` 1.0.0 no los tenía; A3 escribía `version_esquema` y `infra-estado.schema.json` | `infra_estado` **1.1.0** con esos campos opcionales (`modo` ausente = no vivo, falla cerrado); nombre `infra_estado.schema.json`, campo `schema_version` | **Hecho** (C17) |
| **D-08** | Códigos de salida: preflight de A3 (0/1/2/3) y runner de A5 (0/10-14/20/30) chocan con convenciones §8 | Prevalecen las convenciones. Preflight: **0 VERDE · 4 AMARILLO o ROJO · 3 entradas inválidas · 2 uso · 1 interno**. Runner: 0 ok · 1 interno · 2 uso · 3 salida inválida · 4 bloqueado, PAUSA o preflight · 5 presupuesto, turnos o límite · 6 timeout, bucle o error externo; el detalle va en `estado` del JSON | **Hecho** (docs/07, docs/09) |
| **D-09** | A5 ubica el runner en `engine/agent_runner.py`; la propiedad por directorio (README de `agentes/`) lo asigna a `agentes/`; arquitectura §3 da `Write` en `qa/` al QA y A5 no le da `Write` | Runner en **`agentes/runner.py`**; el QA no escribe: el runner persiste `qa/<etapa>-v<n>.json` | **Hecho** (docs/09) |
| **D-10** | Nombre de campaña: A3 `…_SALES_CBO1_…`; `campana.schema` fija `objetivo = VENTAS`, `estructura ∈ CBO·ABO`; A4 dice «CBO_1AS» | Manda el esquema: `{oferta_id}_TEST_VENTAS_CBO_{AAAAMMDD}`; «un conjunto» es una propiedad (`n_conjuntos = 1`), no parte del nombre | **Hecho** (docs/07) |
| **D-11** | A4 propone el veredicto `PROVISIONAL`; `veredicto_oferta.estado` admite cuatro valores; «validar en ≤ 14 días» choca con garantía + 7 | Sin valor nuevo: `PROVISIONAL` = `PROMETEDORA` con `evidencia.cohorte_madura_hasta` anterior al corte; la fase sigue `en_test`; `VALIDADA` solo con cohorte madura: entre el día 28 y el 35 desde la activación (último pedido + garantía + 7 días), con la campaña cerrada y en `espera_madurez` mientras tanto (D-22). El primer test suele terminar `FALLIDA`, `INCONCLUSA` o `PROMETEDORA` | **Hecho** (docs/08) |
| **D-12** | `LimitesCelda.tope_gasto_celda_minor` no tiene origen en `limites.yaml` | Sin clave nueva: tope de la celda `oferta_mercado` = mínimo entre `economia.gasto_test_plan`, `limites.gasto_total_test_por_oferta` y `limites.perdida_max_test_por_oferta`; los anuncios no tienen tope propio; si falta alguno, `BLOQUEADO` | **Hecho** (docs/08) |
| **D-13** | `.env.example` (A0) usa `STRIPE_RESTRICTED_KEY_*`, `META_ACCESS_TOKEN`, `DOWNLOAD_SIGNING_SECRET`; el manifiesto de A3 usa `STRIPE_RK_*`, `META_TOKEN_*`, `DESCARGA_HMAC` y separa un token por función | Manda `infra/plantillas/variables-entorno.yaml`; `.env.example` se regenera con `infra.variables`. B8 agrega al manifiesto `INGEST_HMAC_SECRET` y `SELLO_X1_CLAVE` | Pendiente B8 |
| **D-14** | Convenciones: toda acción se anota con bloqueo; A5: el motor es el único escritor de `registro.jsonl`, pero en N0-N2 el spool sería `registro.jsonl` | La cadena de hash exige un solo escritor: los hooks escriben en `AGENT_SPOOL` (en sesión interactiva, `empresa/runs/_interactivo/spool.jsonl`) y `registro.ingerir_spool` lo incorpora en el siguiente comando | Aquí |
| **D-15** | `evaluar_limites('enviar_correo')` exige `correos_max_por_dia/semana`; con `null` bloquearía el correo de entrega | Aplica **solo a correo que no es transaccional**; entrega, recibo y reenvío siguen (R17) y los acota `postcompra.entrega_*` | Aquí |
| **D-16** | A3 §9.1: `limite_gasto_cuenta_meta = gasto_acumulado + min(capital_restante, 1,10 × Σ topes)` con un 1,10 fijo | El factor es `campana.spend_cap_factor` (ya existe, `"1.10"`); ningún literal en el código; el valor final lo fija el dueño. Además `spend_cap` ≤ `gasto_total_test_por_oferta` y ≤ `perdida_max_test_por_oferta` (regla X10; antes solo se comparaba con `limite_gasto_cuenta_meta`) | **Hecho** (validador) |
| **D-17** | `agentes.estado_max_edad_h` (A5) frente a las 6 h del backbone | `estado_max_edad_h` ≤ `min(infra.hc_preflight_vigencia_horas, 6)`; el esquema impone el tope y los hooks miden con su propio reloj | Pendiente B1/B9 |
| **D-18** | El plan de forja §4.2 fija Polonia e Italia como oferta #1; el dueño (2026-11-06) hace de todo mercado una hipótesis | Superado: sin país favorito en el código (`mercados.prior_de_mercado = ninguno`); B0 usa es-ES/EUR por ser el ejemplo; el mercado del primer testeo real lo decide el dueño con M1 y datos propios | Aquí |
| **D-19** | MCP «hasta N2» (backbone 5.5) frente a que el runner con API key no carga conectores (A5 H2) | La automatización del testeo usa **scripts con Marketing API desde N2**; el MCP queda para la sesión Code del dueño (forja, lecturas, prueba A-9). Exige un token de usuario operador desde el inicio | Aquí |
| **D-20** | La topología N0-N2 se contradice (arquitectura: «hasta N2 en Claude Code»; latido: motor siempre encendido; estado en archivos locales) | §4.10: motor en Railway desde el primer testeo, Mac como cliente, firma por `POST /ordenes`; alternativa de latido del operador. **Propuesta: el dueño confirma** | Aquí (§4.10) |
| **D-21** | `PAUSA`, `estado.json` y `registro.jsonl` son archivos locales pero el motor corre en Railway (disco efímero sin volumen; réplicas no usan volúmenes) y el dueño/hooks en otra máquina | El estado vivo es del motor, en un almacén (SQLite en volumen → Postgres en N3); archivos = vista exportada; `PAUSA` en tres sitios verificados; ítem `R-06`. Árbitro: la crítica técnica pide Postgres desde el día 1, la de completitud SQLite en volumen para el primer testeo; **vale SQLite en volumen con el mismo esquema** (portable) | Aquí (§4.8) |
| **D-22** | «VALIDADA ≈ día 21» es falso y no hay estado de espera | Plazo 28-35 días, campaña cerrada + `espera_madurez`, B0-22; `campana.presupuesto.dias ≤ veredicto.dias_max` como invariante del **artefacto** (X30). El choque `campana.dias_test_max = 30` vs `veredicto.dias_max = 14` en `parametros.yaml` queda para el dueño | **Hecho** (docs, validador, `estado` 1.1.0) |
| **D-23** | Sello y firmas H con HMAC simétrico: quien verifica puede falsificar (B01); la crítica de completitud propone HMAC con «verificadora» | **Gana la asimetría**: Ed25519, privada solo en el equipo del dueño, pública en motor, hooks y Workers; `ssh-keygen -Y` o `crypto.subtle`; `LIMITES_HASH_ANCLA` fuera del volumen; HMAC solo para pruebas y servicio a servicio. El validador exige `sello.firma` en producción; la verificación criptográfica es de `engine.guard` | **Parcial** (esquemas y validador); pendiente B1 |
| **D-24** | Faltan acciones de gate y artefactos sin esquema | `gates.json` 1.1.0 (+6 acciones); esquemas de C13 a la ola 0b; `postmortem` con `retraso_clic_compra`; `orq crear` por `hash_contenido` | gates y hash: **Hecho**; esquemas: ola 0b |
| **D-25** | Los nombres del backbone y de las especificaciones v1 chocan con `contratos/` | Tabla de errata (abajo) normativa. Cada `departamentos/*.md` (menos `02-descubrimiento.md`) debe llevar la línea `> **Errata v2 (2026-11-06):** esta especificación es v1. Nombres, claves y fórmulas vigentes: tabla de errata de docs/06 §11 y docs/contratos.md §4; ante duda manda contratos/.` | tabla **Hecha**; línea en cada departamento: pedido al coordinador |
| **D-26** | `fallida` era final aunque se decida con una vista inmadura | `fallida → en_construccion` con gate H; `retirada` es final | **Hecho** |
| **D-27** | `activar` con parámetros del conector que no existen en la Marketing API | N12 reescrito (árbol vivo, igualdad de IDs, anuncios → conjunto → campaña, relectura); esos parámetros solo en el hook de la rama MCP | Aquí |

**Errata de nombres (D-25).**

| Backbone / v1 dice | Vigente |
|---|---|
| `reembolso_auto_max_usd`, `max_budget_usd_por_corrida_agente`, `costo_max_validacion_usd`, `max_costo_por_barrido_usd` | `reembolso_auto_max`, `max_budget_por_corrida_agente`, `costo_max_validacion`, `max_costo_por_barrido` (unidad menor de `moneda_limites`) |
| `mercados_permitidos`, `nichos_prohibidos`, `m_kill`, `N_dec`, `p_kill` de O0 | `paises_permitidos`, `subnichos_prohibidos`, `testeo.k_corte`, `testeo.n_dec`, `orquestador.p_viable_descartar` |
| `gasto_test_oferta`, `ofertas_test_simultaneas`, `horas_entre_aumentos` | `gasto_total_test_por_oferta`, `ofertas_en_test_simultaneas_max`, `horas_min_entre_aumentos` |
| `CBO_1AS`, `…_SALES_CBO1_…` | `{oferta_id}_TEST_VENTAS_CBO_{AAAAMMDD}`; «un conjunto» = `n_conjuntos = 1` |
| `angulos.json`, `avatar.json` | `oferta.json.angulos[]`, `oferta.json.avatar` |
| `compliance/veto`, `run_id`, `prev_hash` | `empresa/compliance/`, `ejecucion_id`, `hash_previo` |
| `agent_runner.py`, `engine/agent_runner.py` | `agentes/runner.py` |
| `docs/03` fija Polonia + Italia y 225 USD | superado por D-18 y §7.3: la oferta #1 no está fijada; los importes de docs/03 §6.4 son ilustrativos, no límites |

**Ediciones realizadas (v1):** `docs/09` (nombre `max_budget_por_corrida_agente`, ubicación del runner, códigos, ruta de pruebas) · `docs/07` (nombre del esquema de infra, `schema_version` y `modo`, códigos del preflight, nombre de campaña, `reembolso_auto_max`) · `docs/08` (notas D-11 y D-12) · `docs/convenciones-de-codigo.md` (valores de `FABRICA_ENTORNO`) · `docs/contratos.md` (C14-C17) · `contratos/infra_estado.schema.json` (1.1.0). Después: toda la suite OK (366 pruebas) y `validar_esquemas` sin errores. **No se editaron** el backbone (los pedidos de C08 siguen abiertos: §5.6 aún dice `reembolso_auto_max_usd` y `max_budget_usd_por_corrida_agente`), `parametros.yaml`, `limites.yaml` ni nada de la otra sesión del dueño.

## 12. Hallazgos críticos y pendientes

**Críticos.** (1) D-01: dos economías; con la equivocada el CPA de equilibrio, base de toda regla de matar, sale mal. (2) D-03: hoy `decision/reglas.py` no puede correr contra el `parametros.yaml` real (falla cerrado con `ParametroFaltante`): es correcto, pero bloquea D8 hasta la ola 0. (3) D-19: la automatización de Meta depende de un token de Marketing API que genera el dueño. (4) D-07: sin `modo`, un preflight simulado podía pasar por vivo. (5) D-15: un `null` en una clave de correo habría bloqueado la entrega de lo ya pagado. (6) Claude Code 2.1.205 no tiene `--permission-prompts`, `onFailure` ni los bloqueos fuera del directorio de trabajo que supone el diseño de hooks: hasta actualizarlo, el runner en vivo no debe correr.

**Pendientes.** Ejecutar las olas −1, 0a, 0b y 0c antes de abrir la ola 1; confirmar D-20; ver el registro de cambios para lo rechazado y lo diferido; resolver D-01, D-02, D-03, D-05, D-13 y D-17 en las tareas indicadas; el dueño completa §9; (la especificación de M1, C09, ya existe en `departamentos/16`); contenido de las reglas de claims por X1 (propuestas en `empresa/compliance/reglas_claims.yaml` que se incorporan a `compliance/reglas_sensibles.yaml` y se re-sellan; B6 solo construye el mecanismo); valores de `agentes.*` y de `limites.yaml`.

**Fuentes:** solo archivos internos (backbone, contratos y validador, A3, A4, A5, convenciones, arquitectura, plan de forja, decisiones del dueño, `departamentos/` 00, 01 y 04-14, investigación 16, `ofertas/_ejemplo/`, `empresa/*.yaml`, `infra/plantillas/`). No se consultó ninguna fuente externa ni se ejecutó ninguna herramienta con efecto externo.
