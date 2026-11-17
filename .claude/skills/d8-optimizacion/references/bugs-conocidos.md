# Bugs y limitaciones conocidas (solo documentadas: esta skill no toca `engine/`, `decision/` ni `tests/` ajenos)

> v0.1 sin pulir (skill 0.1.0). Verificado el 2026-11-07 leyendo el código y corriendo, sin red ni claves, `.venv/bin/python -m pytest tests/engine/test_d8.py tests/decision/test_entradas.py -q -p no:cacheprovider`: **9 pruebas rojas** (2 + 7), las mismas del informe de brechas (§B.4). Los pedidos de arreglo están en `PEDIDOS.md` (P-06, P-16 a P-19); aquí solo el diagnóstico y el texto propuesto, que **nadie ha aplicado**.

## A. Bugs reales

### B-01 · `engine/d8.py:334-337`: `veredicto` consulta una columna que no existe (S-B)

```
334        disputa_abierta = conn.execute(
335            "SELECT COALESCE(SUM(monto_minor), 0) FROM fact_disputa WHERE session_id = ? AND estado = 'abierta'",
336            (session_id,),
337        ).fetchone()[0] if _tabla_existe(conn, "fact_disputa") else 0
```

- **Qué pasa:** `fact_disputa` (`datos/migraciones/0001_inicial.sql:84`) tiene `checkout_session_id`, no `session_id`. `_tabla_existe` devuelve verdadero (la tabla existe), así que la rama `else 0` nunca protege: con la base migrada, `engine.d8.veredicto` lanza `sqlite3.OperationalError: no such column: session_id` **en cuanto la oferta tiene un pedido pagado en la moneda de la economía**. Es decir: el veredicto VALIDADA/FALLIDA no funciona con la base real.
- **Segundo defecto en la misma línea:** `estado = 'abierta'` no es un estado de Stripe. `fact_disputa.estado` guarda el `status` crudo de Stripe (comentario de `datos/migraciones/0003_vistas_d8.sql`: `needs_response`, `warning_needs_response`, `under_review`, …, `won`, `lost`); ninguna fila vale `'abierta'`, así que aun corregida la columna, la suma sería siempre 0 y **las disputas abiertas nunca restarían** del CPA de la cohorte.
- **Pruebas rojas por este bug (2):** `tests/engine/test_d8.py::PruebaVeredicto::test_cohorte_madura_ganadora_es_validada` y `::test_gasto_alto_con_una_sola_compra_mala_es_fallida`.
- **Texto propuesto para S-B** (no aplicado; los estados abiertos de Stripe están `[VERIFICAR]` contra su documentación vigente):

```
"SELECT COALESCE(SUM(monto_minor), 0) FROM fact_disputa WHERE checkout_session_id = ? "
"AND estado IN ('needs_response','under_review','warning_needs_response','warning_under_review')"
```
  y, de fondo, una vista `v_d8_disputa` con el vocabulario de D8 (como el resto de `v_d8_*`), para que `engine.d8` no lea una tabla real por su nombre (regla de `datos/migraciones/0003_vistas_d8.sql`).
- **Cómo se evita en esta skill:** `preparar_expediente.py` cuenta `disputas_abiertas` con la columna y los estados correctos (probado en `tests/skills_d8/test_preparar_expediente.py`).

### B-02 · `tests/decision/test_entradas.py:67-78`: fixture obsoleta (S-B) · 7 pruebas rojas

- **Qué pasa:** la fixture `_db()` crea tablas propias (`dim_anuncio`, `fact_meta_ad_dia` con 4 columnas, `fact_pedido` con `pagado_en`/`interno`/`verificacion`, `fact_meta_conv`) en vez de aplicar `datos/migraciones/0001-0003`. `decision/entradas.py` lee **solo** las vistas `v_d8_*` (`:170`, `:173`, `:178`: `SELECT ad_id FROM v_d8_anuncio …`) y falla con `sqlite3.OperationalError: no such table: v_d8_anuncio`. `fact_meta_conv` ni siquiera existe en el esquema real (`v_d8_conv_meta` sale de `fact_meta_ad_dia.compras_meta`).
- **Pruebas rojas (7), todas de `PruebaEvidenciaCelda`:** `test_agrega_oferta_mercado_y_excluye_dias_inmaduros`, `test_celda_angulo_agrupa_varios_anuncios`, `test_celda_anuncio_filtra_por_un_solo_ad_id`, `test_celda_desconocida_falla_con_validacion`, `test_horas_desde_edicion_inyectada_prevalece`, `test_horas_desde_edicion_usa_el_primer_dia_de_gasto_por_defecto`, `test_tracking_sano_integrado_con_razon_meta_stripe`.
- **Arreglo propuesto:** que `_db()` ejecute `datos/migraciones/*.sql` en orden (como hace `tests/skills_d8/_comun.py::crear_base`) y inserte con las columnas reales (`gasto_minor`, `impresiones`, `clics`, `clics_enlace`, `compras_meta`, `oferta_id`, `campaign_id`, `adset_id`, `tz`, `moneda`, `ingerido_en`; `checkout_session_id`, `adid`, `monto_minor`, `creado_ts`, `es_prueba`, `es_interna`, `estado`).
- **Resultado esperado tras B-01 y B-02:** 521 de 521 en `tests/engine` + `tests/decision` (informe de brechas §D.1).

## B. Limitaciones del motor que afectan a D8 (no son bugs; son diseño anterior a J1-J4)

| ID | Dónde | Qué | Consecuencia |
|---|---|---|---|
| B-03 | `engine/d8.py:66` `_REGLA_DE_ACCION` | toda decisión `MATAR` se registra como regla `K1`, `ESCALAR` como `M1`, `INCONCLUSO` como `G2`, `BLOQUEADO` como `G1`, `SEGUIR` como `M0` (`:297` la usa) | `decisiones.jsonl` no distingue K1 de K3, ni una guardia G de otra, y una baja J3 quedaría como «K1»; el auditor no puede calificar por regla (B2-24). Pedido P-16 |
| B-04 | `engine/d8.py:296` | `"gate": "A"` fijo en cada decisión; `ejecutor.pausar` no consulta `contratos/gates.json` (donde `pausar` es H en N0-N1) | el registro afirma un gate que no es el vigente. Pedido P-17 |
| B-05 | `engine/d8.py:327-329` (`_pedidos_y_dias`) | `if m != moneda: continue`: los pedidos en otra moneda que la de la economía **se descartan en silencio**; y `v_d8_gasto_dia` no trae moneda | una oferta con economía en una moneda y cobro en otra (p. ej. cobro en PLN y economía en USD) vería **0 compras** sin aviso. Leído en el código, **no ejercitado** (`[VERIFICAR]`). Pedido P-18 |
| B-06 | `engine/d8.py:447` | `"estabilidad": None` («sin fórmula especificada todavía») | el criterio de VALIDADA «CPA de la 2.ª mitad ≤ (1 + tol) × `cpa_obj`» (`departamentos/09-optimizacion.md:130`) no se calcula. Pedido P-15 |
| B-07 | `decision/entradas.py:301-303` | excluye los últimos 3 días de gasto y clics | el día 1 es invisible (C-04 de `conflictos-con-la-spec-vieja.md`). Pedido P-04 |
| B-08 | `engine/orq.py:645-653` + `engine/estado.py:125-150` | `orq ciclo-d8` abre la base con `estado.abrir_base`, que **crea la carpeta y aplica migraciones** (`CREATE TABLE/VIEW IF NOT EXISTS`, control del motor) aun en `dry_run` | el «dry-run» del motor no es de solo lectura sobre la base. Por eso el Maker de D8 no lo corre y esta skill trae su propio lector `mode=ro`. Pedido P-19 |
| B-09 | `dashboard/web/lib/operacion.js:581-583` | el panel imprime `python -m engine.d8 reglas|veredicto`; `engine/d8.py` no tiene `__main__` ni CLI | el comando que el panel sugiere no existe (los reales: `python -m engine.orq ciclo-d8|veredicto --oferta`). Es de S-C (otra tarea): anotado en `PEDIDOS.md` §C |
| B-10 | `empresa/datos/fabrica.db` (ruta real de `datos.etl_stripe.ruta_db_por_defecto`) | no existe todavía: no hay datos reales | `preparar_expediente.py` no se ha podido correr contra datos reales; sus pruebas usan bases sintéticas creadas con las **migraciones reales**. `empresa/motor.db` (que sí existe) es el almacén de control del motor, no el de hechos |

## C. Limitaciones propias de esta skill (v0.1)

| ID | Qué | Por qué importa |
|---|---|---|
| L-01 | `proponer.py` es una implementación de referencia **en sombra** (B2-01, B2-12 siguen siendo de S-B) | su resultado es una propuesta; cuando `engine/d8.py` tenga J3 y FT, se contrasta y se retira |
| L-02 | la frecuencia a 7 días no está en `fact_meta_ad_dia` | la señal de frecuencia de la alarma de fatiga solo existe si un ETL futuro la trae (P-10); hoy se evalúan CTR y costo por venta |
| L-03 | con **cero pedidos** no se puede probar que el webhook de Stripe esté vivo | la regla J3 depende de `infra_semaforo` VERDE y del vigía de pagos (B2-21); una baja por un webhook caído sería un falso descarte |
| L-04 | `fact_evento` (primera parte) con banner de consentimiento (UE/UK) puede subcontar vistas de landing | puede disparar `ETAPA_2_CONEXION_BAJA`; cae del lado seguro (no baja) pero retrasa la decisión un día |
| L-05 | «día incompleto» se infiere de `ingerido_en` (la lectura de Meta del día es anterior a su cierre) | `[VERIFICAR]` que el ETL refresque `ingerido_en` en cada upsert (en `datos/db.py` `upsert` lo actualiza); si algún ETL no lo hiciera, la skill caería del lado seguro (`DIA_INCOMPLETO`) |
| L-06 | `estado.json` y `empresa/infra/estado.json`: este último **no existe** hoy (`empresa/infra/` solo trae `centinela_persistencia.json`) | `infra_semaforo` = `null` ⇒ la regla J3 devuelve `CONTEXTO_DESCONOCIDO` hasta que D0/S-B lo produzcan |
| L-07 | los umbrales de `evals/_base/umbrales_prueba.json` son de prueba | nunca se usan en una corrida real; el grupo `lanzamiento` no existe en `parametros.yaml` (P-02) |
