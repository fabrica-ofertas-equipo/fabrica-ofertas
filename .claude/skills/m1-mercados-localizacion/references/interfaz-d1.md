# Interfaz con el radar de D1 (SOP pasos 13-15) y datos propios del barrido

> Fuente: `departamentos/16` Anexo B y §3.3; `docs/_historial/d1-v2-interfaces.md` (v1.1 de S-A) §4.2: **documento normativo** en nombres de D1 (su l.3: cuando una spec y ese archivo difieran, manda ese archivo); **confirma** los nombres de M1 y añade `presupuesto_exploracion.max_consultas_biblioteca`, `mecanismo_traducible ∈ si·parcial·no` y el archivo de transferencias `empresa/descubrimiento/transferencias/AAAA-MM-DD.jsonl` (append-only, D1). `departamentos/02-descubrimiento.md` ya no es v1: es la versión radar (v1.1 según S-A) y lista `locales_activos.yaml` y `terminos_busqueda/<locale>.yaml` como entradas de M1 (l.8, l.30-33). **[PENDIENTE: esquemas `locales_activos`, `terminos_busqueda`, `emparejamientos`, `hipotesis_transferencia` (CT-4, LT-18/LT-19, clase S).]** Pendiente menor: `templates/emparejamiento.json` con el enum `mecanismo_traducible` y la ruta de transferencias de D1.

## 1. Qué publica M1 para D1
| Artefacto | Ruta | Regla |
|---|---|---|
| Locales activos | `empresa/mercados/locales_activos.yaml` (`templates/locales_activos.yaml`) | un locale entra si ∈ `limites.locales_permitidos`, tiene ficha vigente, glosario y `terminos_busqueda`. `prioridad` 1-5 sale del puntaje medio del locale, evidencia propia y si hay oferta activa |
| Presupuesto de exploración | dentro del anterior | M1 **reparte** los topes de D1 (`max_busquedas_por_barrido`, `max_costo_por_barrido`, `modelado_max_consultas_por_corrida`) y **nunca los amplía**: `w_l = score_medio_l · (1 + 0,5·oferta_activa)`, `cuota_l = tope_global · w_l / Σw`; mínimo 1 barrido mensual por locale activo; ≤ 20 % para locales sin ficha completa. `max_barridos_por_semana` sigue siendo global. Con los topes en `null` ⇒ `null`, nada se reparte |
| Términos de búsqueda | `empresa/mercados/terminos_busqueda/<locale>.yaml` | `dolor[]`, `sustitutos[]`, `sitios_site[]`, `fuente_id_candidatos[]` (**los ids los fija D1** en `fuentes.yaml`; M1 no los inventa), `revisado_por`. Término sin revisión nativa = `[VERIFICAR]` y no entra al barrido programado |
| Veredicto de viabilidad por locale | respuesta a cada transferencia | `{viable, bloqueos[], barrido_local_solicitado, requisitos[]}` |

## 2. Transferencia entre idiomas (paso 14) — la regla que no se rompe
D1 envía `{problema_id, locale_origen, locale_destino, mecanismo_traducible ∈ si·parcial·no}` (+ `macro_nicho`, `banderas`, `riesgo_nivel`, `via`). M1 responde `viable`/`bloqueos`/`barrido_local_solicitado`/`requisitos` (¿ficha?, ¿glosario?, ¿revisor?, ¿ley del idioma?) en `empresa/mercados/emparejamientos/<fecha>.json`.
- **M1 NUNCA declara válido un problema en otro idioma**: la evidencia es por `locale` (backbone 3.2). Un par sin evidencia local (E1-E4 en el destino) queda `hipotesis_de_transferencia` y **no pasa a D2** sin barrido local con paridad de evidencia (≥ `evidencia_min_fuentes` fuentes y ≥ `evidencia_min_tipos` tipos en ese locale, con al menos una E3 y una E1 o E2).
- La ausencia de rivales en el destino es evidencia de **oferta** (E2), no de demanda ni de dolor.
- Chequeo: MQ-22; sembrado D16.

## 3. Emparejamiento y botón «Lanzar nueva oferta» (paso 15)
`S(c, m) = Σ w_k · score_k(m | c)`: CAC con el `precio_plausible` de c; EXPO con el `riesgo` de c (por bandera); LOC con el tipo de contenido. Entrega a O0 el top 3 de pares por candidato (`emparejamientos/<fecha>.json`, `templates/emparejamiento.json`). **No elige**: el dueño elige (gate H hasta N3). No pasa ningún par rojo.

## 4. Datos propios del barrido (`empresa/barrido/…`) — cómo se usan
El barrido (Modo D de D1; corrida `2026-11-06-a`) deja datos propios que M1 **lee** (no escribe): `candidatos/<corrida>.json` (`matriz_tema_pais`, `idiomas_por_pais`, `exportadores`, `temas[].paises/huecos`), `paginas/<corrida>.json`, `planes/<corrida>.json`.
| Dato | Qué es | Cómo lo trata M1 |
|---|---|---|
| `matriz_tema_pais.presencia` / `huecos` | en qué países aparece (o no) un tema en la **muestra** del conector de la Biblioteca | **hipótesis** de brecha/transferencia, con `estado_ausencia = hipotesis_hasta_pasada_3`: ausencia en la muestra no es ausencia en el mercado (≤ 50 anuncios por consulta, 697 de 724 páginas con muestra truncada: los conteos son un **piso**) |
| `exportadores` | cuenta publicitaria en una moneda que no es la del idioma del anuncio | pista para M1 (moneda/país), **no** evidencia de demanda |
| consultas por país | la cobertura de consultas NO es pareja entre países | **normalizar o no comparar**: presencia bruta por país sin ajustar por consultas realizadas no ordena países |
| `paginas_por_medicion` | completa / parcial / muestra | solo `completa` sirve para tracción; `muestra` queda `indeterminada_por_muestra` |
Uso permitido: (a) proponer a D1 **dónde pedir un barrido local** (pasada 3, page_ids × país); (b) alimentar COMP con señal de demanda, nunca con «poca competencia = oportunidad» (16 H7); (c) explicar al dueño qué evidencia propia hay y cuál falta. Uso **prohibido**: elegir un mercado por presencia en la muestra, o presentar un hueco como oportunidad. La evidencia de demanda por país se detalla, con cifras, como hipótesis en `preguntas-abiertas.md` (pregunta P1). El plan no fija un primer mercado ni un par de arranque (R-C01): estos datos orientan **dónde pedir un barrido local**, no qué mercado se prueba.
