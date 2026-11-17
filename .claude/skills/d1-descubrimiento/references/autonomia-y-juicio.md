# Autonomía: del humano en todo al muestreo, y los gates de D1

> Spec §7 y §13; `scripts/modelado/juicio.py`; `contratos/gates.json` (`etapa:D1`, `accion:elegir_candidato`: N0-N3 = **H**, N4 = **S**). Hay **dos escaleras distintas** y no se confunden: (A) el **gate de la elección** del candidato y (B) el **nivel de automatización del juicio** de las puertas del Modo D. Más una tercera: el **nivel de recolección** (qué fuentes puede tocar el sistema sin persona).

## 1. Escalera A: gates de la elección (manda `contratos/gates.json`)
| Nivel | Qué ejecuta D1 | Gate |
|---|---|---|
| N0 | dueño + pestaña Code, a mano, forjando la skill | el dueño decide todo |
| N1 | Maker con skill | el dueño revisa todo y elige |
| N2 | Maker + QA independiente | **H** en la elección |
| N3 | radar periódico alimenta el banco (solo con ruta de recolección aprobada y sellada por X1) | **H**: el dueño elige siempre; **no hay avance tácito**. Nunca se ofrece un amarillo-b ni un ROJO sin H, ni sin Biblioteca/E1 disponibles |
| N4 | el botón «Lanzar nueva oferta» pide candidatos al banco y elige por regla determinista | **S**: veto del dueño durante `limites.ventana_veto_min`; solo con confianza alta, ≥ `cuota_verde_topn_min_pct` de verdes, sin ROJO, (`nivel`, `subnivel`) ≤ `nivel_max_lanzable` y capacidad de test libre; **no autoriza gasto** (los gates H de D3 y D7 siguen) |
`ventana_veto_tacito_h` está **obsoleta** (N3 es H). El nivel efectivo lo da `empresa/autonomia.yaml` (lo cambia el dueño, no el Maker). D1 **no gasta dinero ni publica**. La corrida desatendida (N3/N4) depende de que el conector siga autenticado fuera de la sesión interactiva `[VERIFICAR]`; si no, `evidencia_demanda_pagada` se limita a ≤ 2, la confianza a media y el candidato no se ofrece en N4.
**Ascender** (spec §7; métricas `[HIPÓTESIS]`): N1→N2: ≥ 80 % de candidatos aceptados sin edición en 5 corridas y QA ≥ 90 % de sembrados · N2→N3: elección del dueño ∈ top-3 en ≥ 80 % de ≥ 8 corridas, 100 % de citas verificadas, 0 bloqueantes detectados tarde en D2/X1 · N3→N4: correlación de rangos score vs. resultado ≥ 0,3 con ≥ 10 ofertas testeadas (reportar intervalo; la tasa de éxito del top-1 debe superar la de elecciones manuales previas) y 0 rechazos de política atribuibles a la selección. **Descender:** 3 candidatos seguidos con evidencia que D2 no reproduce, o un reclamo de plataforma por recolección → N1 y se revisan las fuentes.
El **nivel de recolección** es N2 hasta que el dueño elija una ruta desatendida y X1 la selle (hoy ninguna): el conector es interactivo; B (`claude -p`), C (API UE/UK) y D (Chrome, con freno) son decisiones del dueño, no tuyas.

## 2. Escalera B: automatización del juicio de las puertas (Modo D)
**Principio: la IA propone, el código dispone.** La IA juzga lo que solo se puede juzgar mirando (puertas, componentes de transferibilidad, reencuadres), con evidencia; nunca decide el puntaje, nunca toca parámetros y nunca completa un dato medido.
| La IA puede | La IA no puede |
|---|---|
| opinar sobre puertas, transferibilidad y reencuadres **con evidencia** | poner `entrantes_30d`, anuncios, edad ni ningún dato medido |
| vetar (un solo juez alcanza) | liberar una puerta con un solo juez |
| completar lo que está en `null` | pisar lo que ya puso una persona (si discrepa, se informa) |
| proponer reencuadres que sustentan los **dos** jueces | cambiar umbrales, pesos, vocabularios o la fórmula |
**Niveles:**
- **`humano_en_todo`** (nivel de arranque y de descenso): una persona confirma las puertas de **toda** ficha que la IA libere.
- **`muestreo`**: una persona confirma solo una muestra. **Condiciones, todas a la vez** (`juicio.py acuerdo`): ≥ `modelado_calibracion_min_casos` casos con etiqueta humana (propuesta 20) · acuerdo en puertas ≥ `modelado_acuerdo_min` (propuesta 0,90) · **CERO falsos libres** (la IA liberó una puerta que la persona vetó) · la IA nunca más optimista que la persona en transferibilidad (más allá de `modelado_juicio_tolerancia`). **Un solo falso libre devuelve el nivel a `humano_en_todo`.** Los números son `[HIPÓTESIS]` propuestos, sin integrar a `parametros.yaml`.

### Cómo se sube de nivel, paso a paso (lo corre el dueño o el orquestador; tú preparas los archivos)
1. **Etiquetas humanas a ciegas.** Para cada oferta del conjunto de calibración, una persona rellena su propia ficha (`puertas` y `transferibilidad` con evidencia) **antes de ver** la respuesta de los jueces (evita anclaje). Guarda `ficha_humana.json` (formato de ficha 2.0.0).
2. **Ficha de la IA.** Los dos jueces y `juicio consolidar` producen `ficha_ia.json` con las mismas ofertas.
3. **Medir.** `.venv/bin/python -m scripts.modelado.juicio acuerdo ficha_ia.json ficha_humana.json --parametros P` imprime `casos`, `coincidencias`, `falsos_libres`, `falsos_vetos`, `sin_opinion`, `ia_mas_optimista`, `acuerdo_puertas`, `nivel` y `razones`. Solo cuenta lo que la persona evaluó.
4. **Decidir.** Si `nivel = muestreo`, el dueño decide si lo adopta (queda registrado en la bitácora y en `empresa/autonomia.yaml`; nunca lo cambia el Maker). Si hay `razones`, se siguen etiquetando casos (más variedad: otros idiomas y nichos, ofertas con testimonios de ingresos, marca personal sutil, sustitutos gratis).
5. **Guardar la evidencia** en `empresa/barrido/calibracion/AAAA-MM-DD/` (`ficha_ia.json`, `ficha_humana.json`, `resultado.json`) `[SUPUESTO: carpeta propuesta; fuera de `.claude/`]`.
6. **Descenso automático.** Cualquier falso libre posterior (una persona veta lo que la IA liberó) devuelve el nivel a `humano_en_todo` hasta recalibrar.
**Fracción del muestreo** (qué parte de las fichas liberadas se revisa en `muestreo`): no está definida en la spec `[DUEÑO]` (`preguntas-abiertas.md`). Mientras no la fije, usa: **toda** ficha con un veto marcado «para revisión» y al menos 1 de cada 3 de las liberadas `[SUPUESTO]`.

## 3. Lo que no se automatiza nunca (aunque la escalera suba)
`entrantes_30d` (exige una instantánea previa en la memoria de barridos), el `puntaje_rival` (exige auditar la página del rival) y **la decisión de lanzar**. Tampoco la **elección del candidato** hasta N4, y en N4 solo por regla determinista con veto del dueño. Ni el levantamiento del freno de captura, ni límites, ni parámetros, ni el sello de reglas.

## 4. Quién cambia cada cosa
| Cosa | Quién | Cómo |
|---|---|---|
| nivel de autonomía de D1 | el dueño | `empresa/autonomia.yaml` (X2 propone con datos) |
| límites y topes | el dueño | `empresa/limites.yaml` (sellado) |
| parámetros `descubrimiento.*`, sello de reglas | el dueño | `empresa/parametros.yaml`; el sello nuevo se aprueba y se pasa a `--sello-esperado` |
| nichos y fuentes | el dueño (D1 propone, X1 veta fuentes) | `empresa/propuestas/` |
| freno de captura | **solo el dueño** | borrándolo a mano tras revisar si fue falso positivo |
| elección del candidato | el dueño (H) | `estado.json` |
