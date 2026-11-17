# Contratos y rutas de D3: entradas, salidas y de dónde sale cada campo

Todas las rutas son relativas a la raíz del repositorio. Esquemas: `contratos/*.schema.json` (no se editan). Validador: `.venv/bin/python -m scripts.validar_esquemas oferta ofertas/<id>`.

## 1. Entradas (solo lectura)
| Ruta | Esquema | Qué toma D3 | Si falta |
|---|---|---|---|
| `ofertas/<id>/00-brief.yaml` | `brief` | `oferta_id`, `familia_id`, `slug`, `dominio`, `mercado_objetivo{locale, paises_segmentacion, moneda_cobro}`, `precio_rango`, `presupuesto{test_total_max, test_diario_max}`, `ventana_test_dias`, `reembolso_dias`, `nivel_autonomia` | **Detente** (`parada.json`: `detenida_por_dato_faltante`) |
| `ofertas/<id>/mercado.json` | `mercado` | `locale`, `paises_segmentacion`, `moneda_cobro`, `cpm_esperado`, `metodos_pago{fase, activos}`, `fiscal`, `consumo{desistimiento_dias, boton_arrepentimiento}`, `revision_linguistica` | **Detente** (caso C8): no se inventa locale, país, moneda, CPM ni métodos |
| `ofertas/<id>/01-descubrimiento/candidatos.json` | `candidatos` | el candidato elegido (`estado.json.candidato_elegido`; en práctica, `CAND-01`): `problema_id`, `macro_nicho`, `prueba_una_frase`, `mecanismo{…}`, `entregable{…}`, `riesgo{P,C,E,N,nivel,reencuadre_aplicado,claims_a_evitar,angulo_seguro,fuentes,categoria}`, `evidencia[]` (E3 con `cita` literal). `precio_plausible` y `demanda_pagada` son **prior, no evidencia** | **Detente** |
| `ofertas/<id>/02-validacion/validacion.json` | `validacion` | `veredicto.final` (GO o GO_CONDICIONAL con decisión del dueño; NO_GO = no se diseña), `handoff_d3{angulos_candidatos, objeciones_top, rango_precios_por_moneda, entregables_tipicos, prohibido_copiar}`, `huecos`, `saturacion`, `riesgo_politica` | **Detente** |
| `ofertas/<id>/02-validacion/voz_cliente.json` | sin esquema (D2) | `frases[]{frase_id, texto_literal, …}`: de aquí salen las citas del avatar y de `cita_voz_ref` | Usa solo las E3 de `candidatos.json`; anótalo en `supuestos[]` |
| `ofertas/<id>/02-validacion/anuncios_competencia.json` | sin esquema (D2) | competidores y anuncios: copia (n-gramas), sustituto gratis, `prohibido_copiar` | Sigue; L1-09 queda sin ese insumo (anótalo) |
| `empresa/parametros.yaml` | `parametros` | grupos `economia` (incluida `umbral_qa`, que el QA lee), `estadistica` (`meta_eventos_aprendizaje_semana`, `meta_fraccion_min_purchase`: hechos de la plataforma para el evento de optimización), `testeo`, `landing` (`garantia_dias_min`, `bump_pct_precio_min`/`max`: la única fuente del rango del bump), `compliance` (`ngrama_*`), `finanzas.tarifas_antiguedad_max_dias`, `orquestador.max_rondas_qa` | Un umbral ausente = el motor sale 5: **no lo inventes** |
| `empresa/limites.yaml` | `limites` | `perdida_max_test_por_oferta`, `gasto_diario_por_oferta`, `gasto_total_test_por_oferta`, `factor_techo_teorico_diario`, `precio_neto_minimo`, `politica_reembolso_dias`, `locales_permitidos`, `paises_permitidos`, `moneda_limites`, `lineas_rojas`, `macro_nichos_permitidos`, `nivel_max_lanzable` (objeto por macro; `null` = SOLO VERDE, no es un dato faltante) | Un `null` **no impide redactar**: la oferta queda «sin gasto autorizado» (C9) |
| `empresa/finanzas/tarifas.json` (F1) | sin esquema | comisión por (país, método), recargos, `iva_bp`, `recargo_meta_bp`, tarifa de disputa; ≤ `finanzas.tarifas_antiguedad_max_dias` | **No existe hoy**: `[SUPUESTO]` de `docs/_investigacion/03-stripe.md` §4.1 con `tarifas_origen = supuesto` |
| `empresa/compliance/` (X1) | varios | `reglas_claims`, `matriz_pais_nivel.yaml`, `ayuda_por_pais.yaml`, `terminos_sensibles/<locale>.yaml` | **No existen hoy** (salvo `compliance/reglas_sensibles.yaml` con es-ES y en-US): ver `dependencias.md` |
| `empresa/mercados/glosarios/<locale>.md` (M1) | md | vocabulario y tono del locale | No existe hoy: glosario mínimo en `supuestos[]` |
| `empresa/memoria/` (X2) | md/json | fallas conocidas de D3 | Opcional |
| `empresa/PAUSA`, `ofertas/<id>/estado.json` | `estado` | `PAUSA` ausente; `etapas.M1.estado`, `etapas.D2.estado`, `candidato_elegido` | Sin `estado.json` (práctica) sigue marcando `[SUPUESTO]` |
| `ofertas/<id>/03-oferta/entrevista.yaml` | sin esquema | opcionales del dueño | Valores por defecto (ver `templates/entrevista.yaml`) |
| `ofertas/<id>/modelado/{desarme_referente.json, plan_mejora.json, antes_despues.json}` (**solo modo `modelado`**; los produce la skill `modelado-oferta`) | hermanos `0.1.0-borrador` (sin esquema publicado) | oferta del referente (pieza, pack, niveles, tipos de bonus, plazo de garantía, pago único), palancas aprobadas (`plan_mejora.estado = aprobado_por_dueno`) y la tarjeta antes/después | Sin `plan_mejora.json` aprobado no hay modo `modelado`: pide el plan al dueño o sigue en `crear` |

## 2. Salidas (escribe SOLO en `ofertas/<id>/03-oferta/`; con runner, en el `staging` que indique el encargo)
| Archivo | Esquema | Quién lo escribe | Notas |
|---|---|---|---|
| `oferta.json` | `oferta` (todos los campos son obligatorios) | el Maker | `schema_version` `1.0.0`; `version` `v<n>`; `origen_version` `maker`; `aprobada_por_dueno` **siempre `null`** (lo firma el dueño) |
| `economia.json` | `economia` (1.2.0) | **solo el motor** (`engine.factibilidad`, vía `scripts/economia_por_pais.py` o la CLI) | El Maker nunca lo edita ni lo redacta; si lo escribe a mano, L1-04 lo detecta |
| `oferta.md` | sin esquema | el Maker | Cabecera YAML (cifras que compara L1-02 y hasta 3 `marca_propuesta[]`, que viajan aquí hasta que `oferta.json` admita el campo) + secciones A-F para el dueño (español) + ficha de 12 puntos en el idioma de la oferta, con el encabezado `## … (12 …)` localizado si hace falta (`templates/oferta.md`) |
| `entrevista.yaml` | sin esquema | el Maker | Solo lo que aportó el dueño, con `origen` (`dueno` \| `default`) |
| `parada.json` | sin esquema (PEDIDO) | el Maker | Solo si NO hay oferta lista para el QA (`devuelta_a_d1`, `no_factible_escalar`, `riesgo_rojo_sin_reencuadre`, `detenida_por_dato_faltante`, `fuera_de_mercado_permitido`) |
| `devolucion_d1.json` | sin esquema (PEDIDO) | el Maker | Solo con `devuelta_a_d1` |
| `qa/d3-v<n>.json` | `qa` | el QA (lo persiste el runner; el QA no escribe) | `ofertas/<id>/qa/` |
| `qa/.l1/d3-v<n>.json` | `checks_l1[]` de `qa` | el código, antes del QA (no el Maker ni el QA) | `ofertas/<id>/qa/.l1/` (oculta: X18 solo recorre `qa/*.json`); el Maker no escribe en `qa/` |

Versiones: **nunca se sobrescribe una versión aprobada**; una corrección es `v<n+1>` con `origen_version: maker` (o `humano` si la editó el dueño). Dinero: enteros en la unidad menor + moneda ISO 4217, **nunca `float`**; tasas en puntos básicos (`1000` = 10 %) o cadena decimal.

## 3. De dónde sale cada campo de `oferta.json`
| Campo | Fuente | Regla |
|---|---|---|
| `schema_version`, `version`, `origen_version`, `aprobada_por_dueno` | constantes | `1.0.0`, `v1` (o `v<n+1>`), `maker`, `null` |
| `oferta_id`, `familia_id`, `slug`, `marca.dominio` | brief | idénticos al brief. Si el brief no trae `dominio`, propón uno neutro marcado `[SUPUESTO]` (disponibilidad no verificada; no se compra) |
| `variante_de` | brief / orquestador | `null` salvo modo `variante` (= `oferta_id` de la madre) |
| `marca.nombre` | D3 | neutra: sin condición, resultado, estado ni cifra; sin Studio/Academy/Master/Pro/Lab/Creative (`nombre-promesa-bonus.md`). Provisional: la primera de `marca_propuesta[]`; la que el dueño elija en el gate H entra en `v<n+1>` |
| `marca_propuesta[]` | D3 (no está en `oferta.json`) | hasta 3 `{nombre, dominio}` neutras en la cabecera de `oferta.md` y en §E; X1 las revisa; el dueño elige una en el gate H **antes** de comprar el dominio; D3 no compra dominio ni crea dataset |
| `candidato_ref`, `macro_nicho` | candidatos.json | heredados; D3 no re-elige el problema |
| `locale`, `paises_segmentacion`, `moneda` | mercado.json | únicos por oferta; la economía se calcula por país del clúster |
| `riesgo` | candidatos.json, **re-verificado** | máximo de P, C, E, N sobre todos los activos con `python -m scripts.nivel_riesgo` (`riesgo-y-reencuadres.md`); `requiere_gate_humano_legal = true` si el nivel es AMARILLO (nombre heredado: es el gate H del dueño, no un abogado) |
| `cliente_ideal` | candidatos.json | tercera persona de rol o situación; sin «tú» + atributo ni pregunta |
| `prueba_una_frase`, `mecanismo{nombre, como_funciona}` | candidatos.json | se **heredan**; si no se sostienen, devuelve a D1 |
| `promesa{titulo, subtitulo, tiempo_prometido_min, claims_permitidos[], claims_prohibidos[]}` | D3 | `nombre-promesa-bonus.md`; `tiempo_prometido_min` es la **única fuente** del tiempo (R10) |
| `vehiculo{formato, tiempo_consumo_min, palabras_max}` | entregable de D1 | `formato` del enum del esquema; `tiempo_consumo_min = ⌈palabras_max / economia.lectura_wpm_diseno⌉ + minutos de ejecución` y `≤ economia.tiempo_diseno_max_factor × tiempo_prometido_min` |
| `entregables[]`, `bonus[]` | D1 + D3 | un entregable único; 3-5 bonus |
| `garantia{tipo, dias, texto_visible}` | brief, limites, mercado, parametros | `garantia-desistimiento-mercados.md` |
| `urgencia`, `prueba[]` | D3 | `precio-bump-urgencia-prueba.md` |
| `precio{lista, tax_behavior, anclaje}`, `bump`, `upsell` | D3 + motor | precio local con IVA incluido; `anclaje = null` en v1; `upsell = null` |
| `angulos[]`, `avatar` | D2 + D3 | `angulos-avatar-puntaje.md` |
| `puntaje{total, dimension_min}` | auto-puntaje del Maker | 0-100 y mínimo 0-5; honesto: el QA puntúa a ciegas y vale el menor |
| `supuestos[]` | D3 | toda decisión de alto impacto y todo dato inferido, con `[SUPUESTO]`/`[VERIFICAR]`/`[HIPÓTESIS]` |
| `hipotesis_test[]` | D3 | métrica **distinguible con el volumen** (con ~15 compras: CTR de enlace y costo por checkout iniciado) |

`cliente_ideal` y `marca` figuran en el esquema aunque la spec §3.3 no los liste: se rellenan igual.
