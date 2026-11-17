# Preflight P01–P25 y extensiones PX1–PX4

Es **código determinista**. El Maker no lo evalúa: reúne los hechos (lecturas `ads_get_*`, D5, D6) en `entradas_preflight.json` (`templates/`) y corre `scripts/d7.py preflight` (equivale a `python -m meta.preflight`). El `preflight.json` que lee el QA es el que escribe el código, no el que resuma el Maker. Un dato ausente es ROJO con evidencia «dato ausente» (fail-closed). `semaforo` = el peor estado; `VERDE` solo si todos son `VERDE` o `NO_APLICA`. `valido_hasta = generado_en + parametros.campana.preflight_vigencia_h` (no confundir con las 6 h de `empresa/infra/estado.json`). El campo `modo` (`fixture`|`vivo`) **no está en el esquema**: va en `lanzamiento.log`; un preflight en fixture **nunca** habilita activar.

| # | Comprueba | Quién aporta el hecho |
|---|---|---|
| P01 | sin `empresa/PAUSA` | script |
| P02 | cuenta `ACTIVE` y consultable | `ads_get_ad_accounts` |
| P03 | método de pago | idem |
| P04 | cuenta «saludable» | idem + `x1_estado_cuenta` |
| P05 | límite diario de Meta ≥ 1,75× diario | lectura de la cuenta |
| P06 | límite de gasto de cuenta fijado por el dueño (prepago: saldo ≤ 3 días de gasto) | lectura |
| P07 | página vinculada y administradores humanos | `ads_get_ad_account_pages` (ver nota decisión 15) |
| P08 | dataset activo con eventos recientes | `ads_get_dataset_stats` |
| P09 | EMQ ≥ `tracking.emq_objetivo` (= `parametros.landing.emq_min_purchase`); Purchase se mide a T+24/72 h, antes basta el payload de prueba completo | `ads_get_dataset_quality` |
| P10 | evento de prueba con el mismo `event_id` en navegador y servidor | D5 |
| P11 | dominio verificado en el portfolio | `tracking.dominio_verificado` |
| P12 | enlace 200 sin redirecciones | D5/`landing` |
| P13 | URL sin vacíos, con macros | `d7.py lint` C05 |
| P14 | `landing_hash`, precio y moneda = paquete y checkout | lint C06 |
| P15 | copys = paquete y `lint_claims` OK | `scripts/lint_claims.py` |
| P16 | mejoras de Meta en `OPT_OUT` | lectura de los anuncios |
| P17 | `self_ai_disclosure` = `limites.politica_divulgacion_ia` | lectura |
| P18 | `locale` y países = `mercado.json` ⊆ `paises_permitidos` | lint C11 |
| P19 | nombres 5.2 | lint C05 |
| P20 | presupuesto y `spend_cap` ≤ límites, con offset de Meta | lint C04 |
| P21 | `active_errors` vacío y 0 objetos ajenos a `ids_meta` | `ads_get_errors` |
| P22 | vistas previas revisadas | `ads_get_ad_preview` |
| P23 | ofertas en test < `ofertas_en_test_simultaneas_max` | estado de la cartera |
| P24 | `hash_config` sellado | `d7.py sellar` |
| P25 | `special_ad_categories` = dictamen de X1 (obligatorio si ≠ `[]`) | X1 |

**Extensiones PX1–PX4** (el esquema `preflight` 1.0.0 rechaza `P26+`, así que **nunca** entran en `preflight.json`; bloquean igual). Existen como informe aparte en `meta.preflight.items_px` (`EntradasPX`, mismo semáforo fail-closed) y se anotan en `lanzamiento.log` hasta el MINOR del esquema (LT-12); `d7.py lint` las cubre en parte:
- **PX1** DSA (beneficiario y pagador = LLC) en cada conjunto con destino UE o «mundial» → lint C14.
- **PX2** tarifa de ubicación incluida en el techo y en la tarjeta → lint C04.
- **PX3** riesgo: nivel, hoja, cuota, envíos, matriz país × nivel → lint C13 (parcial: las claves ya están en `limites` 1.3.0 con `null`; falta la matriz y la cuota en `engine.guard`, `dependencias.md` A12).
- **PX4** sin términos sensibles en nombres, `slug`, URL, UTM ni eventos → lint C15.

**Nota decisión 15 (2026-11-06):** el segundo administrador **no es requisito**. `meta.preflight._p07` ya es informativo respecto de los administradores (S-B, 2026-11-06): solo es ROJO si falta la página vinculada, y el número de administradores se informa sin bloquear. El Maker informa ese número tal cual (nunca falsea el dato) y no escala por él (`dependencias.md`, C.1).

**QA-A (sin ronda)** sobre el plan antes de crear: P14–P19, P25 y PX1–PX4 contra `paquete.json`, porque los creativos son inmutables.
