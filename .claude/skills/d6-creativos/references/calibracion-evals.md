# Calibración y formato de los evals

Fuente: spec §10.5 y Anexo B; `docs/03` §2.5; nota 25 §11. Los evals prueban que la skill y el QA siguen la rúbrica, **no** que el anuncio venda ni que Meta lo apruebe (el único dato real son los rechazos propios). Los textos son `[SUPUESTO]`: ninguno se probó ante Meta ni lo revisó un nativo.

## 1. Qué hay

| Carpeta | Contenido | Qué comprueba |
|---|---|---|
| `evals/dorados/e01…e10-*.json` | Los 10 casos del Maker (§10.5): dinero verde, salud verde, relaciones verde, dinero rojo, amarillo-a, otro idioma (it/pl), pedido de fatiga, `n_anuncios_max` < 3, falta de claims o `locale`, rechazo o claim heredado | Comportamiento del Maker: entrada → salida esperada y criterios de aprobación |
| `evals/dorados/qa-pass.json` | 17 piezas aprobables en es-ES, es-AR, it-IT, pl-PL, en-US, fr-FR, ro-RO, de-DE (Anexo B dorados + pares de la nota 25; g16: pieza menor que la oferta, que NO es defecto; **g17 (0.2.0): pl-PL sin revisor nativo y con `obligacion_legal_idioma`, que NO es defecto por J11**) | El QA da PASS (0 falsos bloqueos) |
| `evals/sembrados/s01…s11-*.json` | 55 variantes (50 bloqueantes ★) de los 10 grupos del Anexo B más el grupo 11 de 0.2.0 (derechos J13, datos inventados y gancho repetido) en es, it, pl, en, fr, ro, de | El QA detecta el defecto con el `check_id`, `patron_clave` y severidad esperados y devuelve FAIL |

## 2. Formato

**Caso del Maker** (`dorados/eNN-*.json`): `caso_id`, `titulo`, `tipo: "maker"`, `macro_nicho`, `locale`, `entrada` (oferta resumida, economía, límites, pedido), `salida_esperada` (qué hace y qué no), `aprobacion[]` (criterios de la spec: 0 ROJO y 0 claims sin `claim_id`; riesgo por pieza (nivel declarado ≥ el recalculado con `scripts.nivel_riesgo`; recalculado ≤ el de la oferta; una pieza menor que la oferta no es defecto; si repite la promesa central, su eje P ≥ el de la oferta); `n_anuncios ≤ n_anuncios_max`; ≥3 ángulos y 0 pares iguales; precio igual a la landing; OCR y retraducción limpios; costo ≤ tope; ≥3 hallazgos). El caso 4 exige **cero promesas monetarias**.

**Pieza dorada** (`qa-pass.json › piezas[]`): `pieza_id`, `locale`, `macro_nicho`, `nivel_oferta`, `texto{hook_tipo, texto_principal, titular, descripcion}`, `claims_permitidos[]`, `veredicto_esperado: "PASS"`, `falsos_bloqueos_a_evitar`.

**Variante sembrada** (`sembrados/*.json › variantes[]`): `variante_id`, `grupo`, `locale`, `macro_nicho`, `nivel_oferta`, `pieza` (texto, o `descripcion_visual`, `asset`, `guion`/`audio_transcrito`, `riesgo_pieza_declarado` con `ejes_codigo`, según el defecto), `defecto`, `check_id_esperado` (uno de `CHECKS_CONOCIDOS` de `validar_d6.py`), `severidad_esperada`, `patron_clave_esperado` (kebab), `veredicto_qa_esperado: "FAIL"`, `hallazgo_esperado`, `bloqueante` (★) y, si hace falta, `contexto` (claims prohibidos, corpus, landing).

## 3. Cómo se ejecutan hoy (manual; no hay runner de evals)

1. **Estructura:** `.venv/bin/python .claude/skills/d6-creativos/scripts/validar_d6.py evals` (JSON válidos, ≥10 casos, ≥10 dorados del QA, ≥ `creativos.calibracion_bloqueantes_sembrados_min` bloqueantes y ≥4 idiomas, `check_id` conocidos).
2. **Maker:** en una sesión limpia, entrega la `entrada` de cada caso al `d6-maker` **con** la skill y **sin** ella (línea base de `docs/03` §2.4) y compara con la `salida_esperada`; con skill debe superar a la línea base en cada caso. Estabilidad: 3 corridas del mismo caso, misma decisión clave en ≥2 de 3.
3. **QA:** entrega cada pieza (dorada o sembrada) a `d6-qa` en contexto limpio, dentro de un paquete mínimo que la contenga, y compara su informe con `check_id`, `patron_clave`, severidad y veredicto esperados. Rota el juego de sembrados para que no se memorice.
4. **Métricas** (informar siempre n y la cota): % de bloqueantes sembrados detectados (≥90 %); falsos bloqueos en dorados (0); **falsos verdes de nivel = 0** sobre `docs/_historial/hwr-semillas/casos-frontera.yaml` y sobre un **conjunto de retención** (≥30 % de los casos, sellado por hash, que el Maker y el QA no ven; ≥60 positivos; cota superior ≤5 %: con 63 positivos y 0 errores es 4,8 %). Los 30 casos `RT-*` son el primer lote de retención y **no se usan para ajustar los lints**.

## 4. Mantenimiento

Cada defecto que el dueño o X1 encuentre en una corrida real pasa a variante sembrada; cada frase que Meta rechace, a una variante y a `lista-rojo-amarillo.md`. Cambia la skill o la rúbrica → se repite la calibración. Un eval nunca se borra: se marca `vigente_hasta` si una política cambia (como en la nota 25 §11).

## 5. Código que calibra el control de calidad (0.2.0)

`tests/creativos/test_qc6.py` es el equivalente de código de los sembrados para `qc6.py` (ok · revisar · falla por punto); `tests/creativos/test_ganchos.py` comprueba la semilla de ganchos contra sus fuentes. Un falso positivo o negativo de `qc6.py` que encuentre el dueño pasa a una prueba ahí y, si es de promesas, a `scripts/qc6_reglas.py` (`PRUEBAS_ROJO` / `PRUEBAS_VERDE`).
