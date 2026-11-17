# scripts/validacion — Veredicto calculado de D2

Propósito: calcular, sin LLM y sin red, `validacion.json#veredicto.calculado` (GO | GO_CONDICIONAL | NO_GO)
a partir de los agregados de saturación, convergencia, riesgo de políticas y evidencia que describe
`departamentos/03-validacion.md` §3.4, cumpliendo siempre `contratos/validacion.schema.json`.

Propietario y etapa: **B1** (ola 2, B1c), D2. Módulo: `scripts/validacion/veredicto_d2.py`.

## Por qué la entrada NO es `validacion.json`

`contratos/parametros.schema.json#grupos.validacion` hoy solo tiene 14 claves fijas (`additionalProperties:
false` por grupo): `max_consultas_qa, umbral_ss, sim_concepto, n_competidores_profundos, min_frases_voz,
min_fuentes_voz, umbral_hueco_ausencia, n_ind_sost_go, is_go_max, is_nogo_min, relectura_dias,
max_palabras_cita, max_iteraciones_refinar, muestreo_no_go_pct`. Los pesos que la skill
`.claude/skills/d2-validacion/scripts/metricas.py` usa para derivar `SS_a`/`IS`/saturación de mecanismo desde
anunciantes crudos (`ss_peso_*`, `is_peso_*`, `mecanismo_share_*`, `confianza_puntos_por_criterio`, …) viven
SOLO en la propuesta no aprobada de esa skill (`.claude/skills/d2-validacion/references/parametros_d2.propuesta.yaml`)
y **no están en el esquema** de `empresa/parametros.yaml`: agregarlas ahí es cambiar un contrato (`contratos/**`,
intocable para esta sesión) y no está en el roadmap aprobado (`docs/contratos.md` §5: la 1.2.0 solo trae
`modelado_*`). Por eso este módulo **no recalcula esos agregados**: los recibe ya calculados (por quien arme
`candidatos.json`/la lectura de D2, hoy el Maker con apoyo de la skill) y decide el veredicto con los 5
umbrales que SÍ son oficiales: `n_ind_sost_go, is_go_max, is_nogo_min, min_frases_voz, min_fuentes_voz`.

Formato de `ENTRADA.json` (propio de este script, no es un contrato de `contratos/`):

* **Pasan tal cual** a `validacion.json` (deben cumplir ya la forma de cada campo del esquema): `schema_version,
  oferta_id, version, origen_version, version_script, candidato_id, macro_nicho, consultas, metricas_mercado,
  saturacion{indice, n_ind_sostenidos, saturacion_mecanismo, detalle}, convergencia{estado, detalle}, huecos[]
  (huecos YA confirmados como sustentados; `hueco_sustentado = huecos no vacío`), senales_demanda_organica[],
  restricciones_originalidad[], riesgo_politica (forma de `contratos/candidatos.schema.json#/$defs/riesgo`),
  no_inferible[], hipotesis_para_d7[], handoff_d3`.
* **Solo para decidir** (el esquema de salida no los guarda): `lectura_snapshots, voz{frases_total,
  fuentes_distintas}, evidencia_locale_e1_o_e2, sustituto_gratis, angulo_seguro_existe,
  reencuadre_verificable_x1, x1_dictamen, confianza{puntos, nivel}, n_competidores, riesgo_subnivel` (`"A"`,
  `"B"` o `null`; el subnivel amarillo-A/B de la nota 25 §2.3 tampoco está en el esquema de `riesgo_politica`).

Ejemplo completo en `tests/fixtures/validacion/entrada-go.json`.

## CLI

```
.venv/bin/python -m scripts.validacion.veredicto_d2 calcular ENTRADA.json [--parametros empresa/parametros.yaml] [--salida validacion.json]
.venv/bin/python -m scripts.validacion.veredicto_d2 comprobar ENTRADA.json validacion.json [--parametros empresa/parametros.yaml]
```

Sin `--parametros` se usa `empresa/parametros.yaml` de la raíz (`engine.parametros.cargar_parametros`). Salida:
0 ok · 2 uso (archivo inexistente, argumentos) · 3 entrada inválida o incoherencia · 5 falta un parámetro oficial
(`n_ind_sost_go`, `is_go_max`, `is_nogo_min`, `min_frases_voz` o `min_fuentes_voz` en `null` o ausente).

## Decisiones (fail-closed ante lo que no está parametrizado hoy)

1. **Riesgo amarillo sin `riesgo_subnivel`** se trata como NO apto para GO (igual que amarillo-B): el dato no
  está en el contrato de salida y asumir el subnivel favorable (A) sería optimista. Pedido: si el dueño aprueba
  guardar el subnivel en `riesgo_politica` (cambio de esquema, fuera de alcance de B1), este módulo puede dejar
  de necesitar `riesgo_subnivel` como entrada aparte.
2. **`hueco_sustentado`** = `len(huecos) > 0` (la lista ya contiene solo huecos CONFIRMADOS como sustentados,
  no candidatos crudos): la fórmula de `umbral_hueco_ausencia` (ausencia en ≥ X % de sostenidos con ≥ N
  anuncios leídos) queda en quien arma `huecos[]`, no en este script.
3. **`NO_GO` con 0 sostenidos y pocas frases** usa `min_frases_voz` como umbral (no existe `nogo_frases_min`
  oficial, solo en la propuesta de la skill). Pedido: agregar `validacion.nogo_frases_min` a
  `contratos/parametros.schema.json` y `empresa/parametros.yaml` cuando el dueño calibre D2.
2. **"0 competidores nunca es GO"** (departamentos/03-validacion.md §3.4) se implementa como una condición más
  de `GO` (`al_menos_un_competidor`) y de `NO_GO` (`cero_competidores`): con 0 competidores el resultado es
  siempre `NO_GO`, no `GO_CONDICIONAL`.
4. El **hueco de localización** (`<3 sostenidos locales pero ≥3 del mismo concepto en país de referencia`,
  nunca GO) y la saturación de mecanismo por `share` quedan fuera: sin `hueco_localizacion_min_ref` ni
  `mecanismo_share_*` oficiales no hay cómo derivarlos aquí; quien arma `saturacion.saturacion_mecanismo` y
  `huecos[]` ya debe reflejarlos antes de llamar a este script.
5. `veredicto.propuesto` y `veredicto.final` de `calcular_validacion` salen iguales a `calculado` (es el punto
  de partida determinista); el Maker los puede DEGRADAR después editando el archivo, y `comprobar` verifica
  que nunca los mejore sin `origen_version=humano` (S11, igual que la skill).

## Paridad con la skill

`tests/scripts/test_validacion_veredicto_d2.py::PruebaParidadConLaSkill` corre
`.claude/skills/d2-validacion/scripts/{metricas,veredicto}.py` (SOLO LECTURA, nunca se edita) sobre una de sus
entradas sintéticas, toma los agregados que la skill ya calculó (`IS`, `n_ind_sostenidos`,
`saturacion_mecanismo`, `convergencia`, `hueco_sustentado`, `confianza`) y verifica que, a partir de ESOS
mismos números, `scripts.validacion.veredicto_d2` llega al mismo `calculado`.

## Cómo probar

```
.venv/bin/python -m unittest discover -s tests/scripts -t . -p "test_validacion_*.py"
```
