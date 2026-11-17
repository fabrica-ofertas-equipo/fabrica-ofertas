# Pedidos de la skill d8-optimizacion (v0.1.0) a S-A y a S-B

> Lo que hace falta **fuera de esta carpeta**. La skill no edita `engine/`, `decision/`, `contratos/`, `empresa/`, `departamentos/`, `docs/`, `meta/`, `infra/` ni otras skills. Cada pedido: qué, a quién, `archivo:línea` (verificado el 2026-11-07), texto propuesto, de dónde sale y su efecto en D8. Prioridad: **P0** bloquea que D8 decida algo en la primera oferta · **P1** necesario para la autonomía de J2 · **P2** mejora. Los pedidos que son decisión del **dueño** van en `references/decisiones-y-umbrales.md` §F. Orden de los pedidos: S-A (§A) · S-B (§B) · otras tareas de S-C y del dueño (§C).

## A. Pedidos a S-A (contratos, parámetros, límites, gates, docs y departamentos)

### P-01 (P1) · `accion:pausar` pasa a automática desde N0 (decisión J2, ya tomada)

- **Dónde:** `contratos/gates.json` → `entradas."accion:pausar".gate` (`N0: H`, `N1: H`); `empresa/autonomia.yaml:51-54` (D8 en N0); `departamentos/09-optimizacion.md:181-185`; `docs/06-bases-del-testeo.md` §5 («pausar nunca espera a un humano», que hoy contradice a `gates.json`).
- **Texto propuesto:** `"accion:pausar": {"N0": "A", "N1": "A", "N2": "A", "N3": "A", "N4": "A"}` con la condición que J2 conserva por código: sello de X1 vigente sobre lo que se opera, preflight en verde, frenos de empresa (J4), `empresa/PAUSA`, vigía de pagos y auditor. `autonomia.yaml`: D8 en N2 desde el inicio (propuesta de `mapeo.md` §4: «N2 para pausar/reducir/relevar»). `reactivar_tras_pausa` **sigue H en todos los niveles**.
- **Efecto en D8:** hoy el gate efectivo es **H** y la skill lo declara en cada propuesta (`gate_efectivo`); con este cambio la baja de J3 la ejecuta el código sin esperar al dueño.

### P-02 (P0) · Grupo `lanzamiento` y claves nuevas en `empresa/parametros.yaml`

- **Dónde:** `empresa/parametros.yaml` (no existe ningún `lanzamiento.*`; `grep` sin resultados). Formato de cada clave: `valor`, `unidad`, `hipotesis: true`, `fuente`, `ultima_calibracion: null`, `rango`.
- **Texto propuesto (valores de `references/decisiones-y-umbrales.md`, todos `[SUPUESTO]` salvo los marcados J3, y a firmar por el dueño):**

```yaml
  lanzamiento:
    baja_dias:                               {valor: 1,    unidad: dias,      hipotesis: false, fuente: "J3"}
    baja_requiere_presupuesto_gastado:       {valor: true, unidad: booleano,  hipotesis: false, fuente: "J3"}
    gasto_cumplido_min_pct:                  {valor: 90,   unidad: porcentaje, hipotesis: true, fuente: "brecha E-01 [HIPÓTESIS]", rango: [80, 100]}
    espera_post_dia_h:                       {valor: 9,    unidad: horas,     hipotesis: true, fuente: "[SUPUESTO] = optimizacion.hora_decision"}
    dias_max_sin_entrega:                    {valor: 2,    unidad: dias,      hipotesis: true, fuente: "[SUPUESTO]"}
    presupuesto_cbo_usd:                     {valor: 75,   unidad: usd,       hipotesis: true, fuente: "J3: 50-100; arranque 75 [HIPÓTESIS]", rango: [50, 100]}
    creativos_por_cbo:                       {valor: 10,   unidad: anuncios,  hipotesis: false, fuente: "J3 (~10)"}
```
  y en `testeo`: `fatiga_ventana_reciente_dias` 3, `fatiga_ventana_previa_dias` 7, `fatiga_lecturas_seguidas` 2, `fatiga_compras_min` 3, `entrega_baja_pct` 50 (renombre de la etapa 0, `09:120`); en `escalado`: `campeon_compras_min` 10 y `campeon_cpa_max_x_be` `"0.40"` (`mapeo.md` §12; **el valor lo decide el dueño**, B2-06).
- **Efecto en D8:** hoy `proponer.py lanzamiento` devuelve `NO_DECIDIR / UMBRAL_FALTANTE` con los parámetros reales. Con esto y la firma del dueño, empieza a proponer.

### P-03 (P1) · Alinear `departamentos/09-optimizacion.md`, `docs/06`, `docs/08` y `docs/10` con J1-J4

- **Dónde y qué cambiar** (cada fila de `references/conflictos-con-la-spec-vieja.md`, C-01 a C-12):
  - `09-optimizacion.md:45` (ventana): agregar «LANZAMIENTO: 1 día de cuenta sin venta con el presupuesto del día gastado ⇒ baja (J3); CONTINUO: tendencia de 3 días» y quitar «nunca 1 día».
  - `:74` (`ventana_no_decidir_h` 72): «no rige para la baja de lanzamiento de J3».
  - `:83` y `:111` («nunca dejar la campaña a cero sola», «nunca el último anuncio»): «salvo la baja de lanzamiento J3, que pausa la campaña completa».
  - `:105` (G2): añadir la guardia G2b de pérdida neta acumulada de cartera (J4, P-07).
  - `:111` (K1) y `docs/08:157` (orden 2): aclarar que la baja de lanzamiento no es K1 y que no se mide con P ≥ 95 %.
  - `:112` (FT): ver P-09. `:113`, `:130-131`, `:182` y `docs/08:342`: resolver la contradicción PROVISIONAL / PROMETEDORA y el papel de VALIDADA bajo el ritmo diario (P-13).
  - `:181-185`: niveles y gates según P-01; `:185` «(H para activar)» según J2.
  - `:261` (pérdida máxima «diferida»): J3 la sustituye por la regla (P-05).
  - `docs/06` §5 (`MATAR oferta_mercado ⇒ fallida`) y `docs/10:112-121`: ver P-08.
- **Efecto en D8:** hoy la skill sigue a J y declara el choque en cada expediente; la spec dejaría de contradecirla.

### P-05 (P0) · Significado y valores de los tres topes por oferta bajo J3

- **Dónde:** `empresa/limites.yaml` (`gasto_diario_por_oferta`, `gasto_total_test_por_oferta`, `perdida_max_test_por_oferta`, `ofertas_en_test_simultaneas_max`: todos `null`), `contratos/limites.schema.json`, `scripts/validar_esquemas.py` (coherencia: `perdida_max ≤ gasto_total ≤ limite_gasto_cuenta_meta ≤ capital`), `engine/d8.py:254-257` (`ciclo` lee `gasto_total_test_por_oferta` como tope de celda).
- **Problema:** J3 dice «sin tope de pérdida por oferta», pero el motor y el validador exigen los topes no nulos para gastar. Si `gasto_total_test_por_oferta` se pone en «1 día» para cumplir J3, un **ganador** se pausa el día 2 (`INCONCLUSO` por tope).
- **Texto propuesto:** (a) `perdida_max_test_por_oferta` ≈ 1 día de gasto máximo teórico (13.125 con CBO de 75 USD); (b) `gasto_total_test_por_oferta` ≈ 7 × el máximo teórico diario (margen para que un ganador llegue a graduar), o hacerlo opcional cuando exista `lanzamiento.*` y que `ciclo()` use `perdida_max` para el tope; (c) **corrección a la brecha E-04:** el guard suma **máximos teóricos** (× 1,75; `engine/limites.py:268-290`, `docs/06:181`), así que con J4 (300 USD/día) y un CBO de 75 USD caben **2** lanzamientos simultáneos (3 con 50 USD, 1 con 100 USD), no 4 `[cálculo nuestro]`: fijar `ofertas_en_test_simultaneas_max` en consecuencia o subir el techo con una firma «cuando haya resultados» (J4).
- **Efecto en D8:** sin esto `engine.d8.ciclo` lanza `ErrorLimite` y la skill devuelve `NO_DECIDIR`.

### P-08 (P1) · Estado de una oferta dada de baja en el lanzamiento (a S-A y S-B)

- **Dónde:** `docs/06-bases-del-testeo.md` §5 (`MATAR oferta_mercado ⇒ fase fallida`; `fallida → en_construccion` = `accion:reabrir_fallida`, H), `contratos/estado.schema.json`, `engine/estado.py`; `engine/d8.py:278-280` (hoy solo llama a `ejecutor.pausar`).
- **Problema:** J3 pide seguir «todos los días» con nuevas variantes. Si cada baja deja la oferta en `fallida` y relanzar exige una firma, el ritmo lo frena el dueño.
- **Opciones (decide S-A con el dueño):** (1) una causa o fase propia `apagada_lanzamiento` que admite `→ en_construccion` sin firma cuando entra una versión nueva (`origen_version` ≠ la anterior); (2) cada variante nueva es una oferta nueva (nuevo `oferta_id`, `variante_de`) y la baja es final para la anterior. Recomendación: (2), coherente con `variante_de` de J5.

### P-09 (P2) · Fatiga: ¿se pausa el anuncio fatigado o sigue en testeo?

- **Dónde:** `departamentos/09-optimizacion.md:112` («el viejo se pausa solo cuando el reemplazo entrega y su CPA 7 d ≥ 2·`cpa_obj`»).
- **Texto propuesto:** «FT no pausa el anuncio mientras venda (reglas de oro 1 y 2 de JPS): el relevo entra como anuncio nuevo en la tanda siguiente; las bajas siguen las reglas K». Mientras no se decida, la skill no propone pausar el fatigado.

### P-11 (P0, parte de S-A) · El paquete de ~10 creativos no cabe en lo armado

- **Dónde:** `empresa/parametros.yaml:917` (`campana.n_anuncios_tope` = 6, `rango: [3, 8]`), `:932` (`dias_test_defecto` 10, `rango: [7, 14]`), `:940` `dias_test_min` 7.
- **Texto propuesto:** subir el tope y el rango para el lanzamiento J3 (≥ 10) y definir que el lanzamiento de 1 día no usa `dias_test_*` (la regla de baja es de `lanzamiento.baja_dias`). Parte de S-B en P-04/B2-02 (`meta/payloads.py` baja `n_anuncios` por `k_corte × cpa_max`). La skill D7 la actualiza S-C aparte (§C).

### P-12 (P1) · Ofertas en paralelo

- **Dónde:** `empresa/parametros.yaml:82` (`orquestador.paralelas_max_por_nivel` = {N0:1, N1:1, N2:1, N3:2, N4:3}); `limites.ofertas_en_test_simultaneas_max` (`null`).
- **Texto propuesto:** con lanzamientos diarios que viven ≥ 1 día y se evalúan a las 09:00, hacen falta ≥ 2 en paralelo ya en N0-N2; el tope real lo da J4 (P-05 c). Valores a decidir con el dueño.

### P-13 (P0 para graduar) · Un solo criterio de «ganador / campeón / escala / VALIDADA» (B2-06; decide el dueño)

- **Dónde:** conviven `testeo.n_dec` 15 + `testeo.p_escala` 0,80 (`parametros.yaml`), `escalado.promocion_min_compras` 5 (`:1399`), `mapeo.md` §3.2 (≥ 10 compras y CPA ≤ 0,40 × BE `[HIPÓTESIS]`) y JPS (≥ 10 ventas a CPA 6-7 con producto de 27 USD `[V][DECL]`).
- **Texto propuesto:** la tabla de 4 niveles de `references/estadistica-honesta.md` §4 como borrador para que el dueño elija; incluir el papel de VALIDADA (portafolio, cohorte madura) frente al ritmo de J1.
- **Efecto en D8:** sin firma, `GRADUAR` devuelve `NO_DECIDIR / CRITERIO_CAMPEON_SIN_FIRMA`.

### P-14 (P2) · Pedidos a D6 vs ritmo diario

- **Dónde:** `empresa/parametros.yaml:1262-1278` (`optimizacion.max_pedidos_abiertos` 1, `dias_entre_pedidos` 5, `cantidad_max_pedido` 5).
- **Texto propuesto:** revisar con el ritmo de J (~10 creativos por lanzamiento, relevos diarios); mientras tanto la skill respeta los valores actuales (sin cupo ⇒ solo avisa).

### P-15 (P2) · Contratos de salida de D8

- **Dónde:** `contratos/` (no existen `pedidos_creativos`, `anomalias`, `kpis_nivel`: pedido ya hecho en `departamentos/09-optimizacion.md:266`, item 6; ni `entrada_d8` ni `propuesta_d8`); `engine/d8.py:447` (`veredicto_oferta.estabilidad` = `None`).
- **Texto propuesto:** adoptar como contratos `templates/propuesta-de-decision.json` y la forma de `scripts/preparar_expediente.py` (campos y tipos; sin `float`; dinero en enteros de unidad menor); definir la fórmula de `estabilidad` («CPA de la 2.ª mitad ≤ (1 + `estabilidad_tol_pct`) × `cpa_obj`», `09:130`).

### P-20 (P1) · El auditor necesita el resultado posterior en `decisiones.jsonl` (B2-24, H-12)

- **Dónde:** `contratos/decision.schema.json` (`additionalProperties: false`; no tiene resultado posterior ni acierto), `engine/d8.py:293-304`.
- **Texto propuesto:** campo opcional `resultado_posterior` (ventana 72-96 h; cortes y subas calificados por separado) y su escritor (el auditor, no D8). Efecto: sin esto las subas «que piden más pruebas» (1 de 3, JPS) no se pueden medir por nuestra cuenta.

## B. Pedidos a S-B (engine, decision, infra, meta, tests de ellos)

### P-04 (P0) · Regla J3 en `engine/d8.py` (B2-01)

- **Dónde:** `engine/d8.py` (`ciclo`, `:225-306`), `decision/entradas.py:279-328` (`evidencia_celda`), `decision/reglas.py`.
- **Qué:** una función `baja_lanzamiento(...)` con la tabla de verdad de `references/protocolo-j3.md` §4 (guardias → venta → pendientes → días → **gasto cumplido** → conexión → baja); **leer el gasto del día cerrado sin la exclusión de 3 días de madurez** (`decision/entradas.py:301-303`: la madurez de 3 días es de las compras **de Meta**, no del gasto ni de las ventas de Stripe); **usar el gasto leído, no el `gasto_efectivo`** (`engine/d8.py:114`, que suma `1,75 × diario × horas_sin_lectura / 24` y **inflaría** el «presupuesto gastado», falseando la salvaguarda y provocando bajas indebidas); ignorar `ventana_no_decidir_h` para esta regla; registrar `regla: "J3"` y el `codigo` (P-16).
- **Aceptación:** los mismos casos que `tests/skills_d8/test_proponer.py` (24 pruebas de la regla de lanzamiento) y los dorados `.claude/skills/d8-optimizacion/evals/dorados/D01.json` y `D02.json`, más la propiedad «con ≥ 1 venta pagada nunca se propone la baja». Cuando exista, `proponer.py` se retira o queda como contraste.

### P-06 (P0) · Arreglar el bug de `veredicto` y la fixture (B2-05)

- **Dónde y texto:** `references/bugs-conocidos.md` B-01 (`engine/d8.py:334-337`) y B-02 (`tests/decision/test_entradas.py:67-78`). Deja la suite en 521 de 521.

### P-07 (P0) · Vigilante continuo de la pérdida acumulada (J4, B2-04)

- **Dónde:** `engine/limites.py:343` (solo al activar o subir), `infra/workers/watchdog/src/index.mjs:116-118` (`gastoHoyMinor: null`, ETL del gasto «fuera de esta entrega»), `departamentos/09-optimizacion.md:105` (G2).
- **Qué:** guardia G2b en `ciclo()` (o un job horario): si la pérdida neta acumulada de la cartera ≥ `limites.perdida_neta_acumulada_max` ⇒ escribir `empresa/PAUSA` global y avisar por dos canales; y que el watchdog reciba gasto real. Levantar la pausa sigue siendo humano.

### P-10 (P1) · Datos que faltan para FT y para las lecturas horarias (B2-11, B2-12)

- **Qué:** (a) ETL de `reach` y `frequency` por anuncio a 7 días (no aditivos: se piden con el rango) y su vista `v_d8_*`; (b) reglas FT del motor que consuman `testeo.fatiga_*` (hoy sin consumidor); (c) `v_venta_hora` (ventas de Stripe con `adid` por hora y mercado) para los robots de 15-30 min. Aceptación de (b): `tests/skills_d8/test_proponer.py::PruebaFatiga`.

### P-11 (parte de S-B) · Payload del lanzamiento J3

- `meta/payloads.py` (baja `n_anuncios` por `k_corte × cpa_max`; `LOWEST_COST_WITHOUT_CAP` fijo): aceptar ~10 anuncios en una CBO para el lanzamiento y mantener el candado (`spend_cap` o `stop_time`). B2-02.

### P-16 (P1) · `regla` real en cada decisión

- **Dónde:** `engine/d8.py:66` (`_REGLA_DE_ACCION`) y `:297`. **Texto propuesto:** que `evaluar_celda` devuelva el id de la regla que disparó (K1, K2, K3, G*, J3, M*) y `ciclo()` lo registre en `regla`, en vez de mapear la acción a una letra fija.

### P-17 (P1) · Gate real en el registro y en la pausa (B2-25)

- **Dónde:** `engine/d8.py:296` (`"gate": "A"` fijo), `engine/ejecutor.py` (`pausar` no consulta `contratos/gates.json`). **Texto propuesto:** leer `engine.estado.gate_de(oferta_id, "accion:pausar")` y registrar ese gate; si es H, dejar la pausa como orden pendiente de firma en vez de ejecutarla.

### P-18 (P2) · No descartar pedidos de otra moneda en silencio

- **Dónde:** `engine/d8.py:327-329`. **Texto propuesto:** contarlos y levantar `ErrorValidacion` (o convertirlos con `tipo_cambio_id`, F1) en lugar de `continue`; y agregar moneda a `v_d8_gasto_dia`.

### P-19 (P2) · Un «dry-run» de solo lectura y el CLI que el panel nombra

- **Dónde:** `engine/orq.py:645-653` y `engine/estado.py:125-150` (`abrir_base` migra y crea carpetas incluso en `dry_run`); `engine/d8.py` no tiene `__main__`. **Texto propuesto:** una conexión `mode=ro` para `ciclo-d8` en `dry_run`, y `python -m engine.d8 {ciclo,veredicto}` como envoltorio (o corregir el texto del panel, §C).

## C. Fuera de lo que puedo cambiar hoy

- **S-C (otras tareas):** (1) actualizar la skill `d7-campanas-meta` al paquete J3 (CBO de ~10 creativos, 1 día, `n_anuncios_tope`) y a la alineación con J2; (2) `dashboard/web/lib/operacion.js:581-583` imprime `python -m engine.d8 reglas|veredicto` (comandos que no existen; usar `python -m engine.orq ciclo-d8|veredicto --oferta`); (3) cuando S-B tenga J3 y FT, retirar `scripts/proponer.py` o dejarlo como contraste; (4) sembrados del QA (`rubric.md` §5).
- **Dueño:** firmar `limites.yaml` con J4, moneda y topes por oferta; confirmar los `[SUPUESTO]` de J3 y el criterio de campeón; decidir el control de falsos descartes; conseguir los 3 videos de JPS que remite (brechas B2-33) con los umbrales de la escalera y de «cansado».
