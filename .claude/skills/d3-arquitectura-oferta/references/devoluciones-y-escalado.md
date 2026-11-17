# Devoluciones, paradas, escalado y gates

## 1. Resultados posibles de una corrida del Maker
| Resultado | Cuándo | Qué escribe en `03-oferta/` | Estado de la etapa (lo decide el motor) |
|---|---|---|---|
| **Oferta lista para el QA** | todo OK (aunque `AJUSTADA` o `NO_FACTIBLE` con evidencia) | `oferta.json`, `economia.json`, `oferta.md`, `entrevista.yaml` | `en_QA` |
| **Devuelta a D1** | la ficha MU/EU no se sostiene: causa raíz distinta, segundo mecanismo, `requiere_servicio`, `fuera_de_macro_nicho`… | `parada.json` (`devuelta_a_d1`) + `devolucion_d1.json`; **sin** `oferta.json` | vuelve al banco de D1 |
| **NO_FACTIBLE tras 2 ciclos** | `economia.veredicto = NO_FACTIBLE` agotadas las palancas (`economia-factibilidad.md` §5-6) | los 4 archivos (mejor intento, `puntaje.total ≤ 59`) + `parada.json` (`no_factible_escalar`) | `ESCALAR` al dueño (H) |
| **Riesgo ROJO sin reencuadre** | ROJO y no existe reencuadre que conserve el deseo, o 2 intentos fallaron | `parada.json` (`riesgo_rojo_sin_reencuadre`) + `devolucion_d1.json` si el candidato debe bajar al banco | `ESCALAR` o devolución |
| **Dato de contrato ausente** | falta `mercado.json` aprobado, `candidatos.json`, validación favorable, brief, o el motor sale 5 | `parada.json` (`detenida_por_dato_faltante`) con el dato exacto; nada más | `bloqueado` |
| **Mercado no permitido** | locale/país/macro fuera de `limites.*_permitidos` (con listas no vacías), país sin ayuda verificada de la categoría central, nivel > `limites.nivel_max_lanzable[macro_nicho]` (`null` = SOLO VERDE: todo amarillo se para) | `parada.json` (`fuera_de_mercado_permitido`) | `escalado` |
`parada.json` y `devolucion_d1.json` no tienen esquema todavía (`dependencias.md`); usa `templates/parada.json` y `templates/devolucion_d1.json`. **El Maker no pregunta**: se detiene y lo dice con evidencia.

## 2. Motivos canónicos de devolución (`rechazo.motivo`, backbone 5.11 y `comunes.motivo_rechazo`)
`sin_mecanismo` · `multi_mecanismo` · `requiere_servicio` · `requiere_comunidad_o_en_vivo` · `no_producible_o_sin_licencia` · `sustituto_gratis_dominante` · `claim_de_salud_o_ingresos` · `dependencia_de_marca_personal` · `mercado_demasiado_estrecho` · `fuera_de_macro_nicho` · `linea_roja_de_contenido_o_negocio` (el contenido o el modelo de negocio cae en una línea roja: dosis, asesoría personalizada de inversión, multinivel, coaching uno a uno…). **Ojo:** el esquema `comunes` aún NO incluye `linea_roja_de_contenido_o_negocio` (backbone v2.2.2 sí): PEDIDO a contratos. Hasta entonces, si el candidato cae en una línea roja de contenido o de modelo de negocio, **no inventes un motivo fuera del enum**: escribe `parada.json` (`riesgo_rojo_sin_reencuadre`) con la línea roja (`lc-xx`/`lm-xx`) en `motivo` y escala.
Redención (`redencion`): `dividir` · `reformular` · `bajar_al_banco` · `descartar`.
**Cuándo devolver y cuándo reformular dentro de D3:** si el problema, el deseo central o el mecanismo cambian → **devuelve a D1**; si solo cambia el encuadre, el nombre o el ángulo (RE-xx) → **reencuadra tú** (máx. 2 intentos). D3 **no re-elige el problema**.

## 3. Ronda Maker ↔ QA y `ESCALAR`
- Máximo `orquestador.max_rondas_qa` (2) rondas Maker↔QA por etapa. El QA no corrige: devuelve la `correccion` de cada hallazgo (`devuelto_al_maker`) y el Maker aplica el parche en la ronda siguiente. Ronda 2 con BLOQUEANTE o MAYOR abierto ⇒ el QA devuelve `ESCALAR` (X18 lo exige) y decide una persona.
- Un mismo defecto que reaparece tras la corrección (p. ej. nombre con sufijo) ⇒ `ESCALAR`: es un hallazgo sobre la skill, no sobre el caso (bitácora `Pulido`: título con prefijo `[error]`).
- `PASS` = 0 BLOQUEANTES, 0 MAYORES abiertos, puntaje ciego ≥ `economia.puntaje_min_oferta` y ninguna dimensión < `economia.puntaje_dim_min_oferta`. `PASS_CON_NOTAS` = 0 BLOQUEANTES y 0 MAYORES con notas MENOR/MEJORA. `FAIL` = devolver al Maker (ronda < 2). `ESCALAR` = al dueño.

## 4. Gates y autonomía (`contratos/gates.json`; spec §7)
| Nivel de autonomía | D3 | Gate |
|---|---|---|
| N0-N1 | el dueño o el Maker con skill; el dueño revisa todo | H total |
| N2 | Maker + QA + scripts L1 | **H siempre** sobre la oferta |
| N3 | gate **S** solo si VERDE, país y nivel admitidos por la matriz de X1, 0 amarillos abiertos, `razon ≥ 1,5`, locale ya lanzado y QA `PASS` sin notas; **H** si cambia macro-nicho, locale/país, garantía o precio fuera de rango, hay override, el nivel es AMARILLO-B o ROJO reencuadrado, o salta una bandera L1/L2 | S / H |
| N4 | el botón dispara D3; muestreo semanal | S + revisión semanal; **H en `AJUSTADA`** |
El **veto y el sello por hash de X1 no se relajan con el nivel**. Un ROJO escapado baja la etapa. `AJUSTADA`: el dueño decide explícitamente (apetito por `AJUSTADA`: pregunta abierta n.º 5).
**Siempre determinista (código, no LLM):** economía y veredicto, linters de claims y de nombre, nivel de riesgo, tope de pérdida, precio mínimo, vigencia de tarifas, países y locales permitidos, `PAUSA`.

## 5. A quién escala cada cosa
| Situación | A quién |
|---|---|
| Oferta lista; `AJUSTADA`; amarillo; override | gate **H del dueño** (lee `oferta.md` §A y §E) |
| NO_FACTIBLE agotado; `ESCALAR` del QA; ronda 2 con BLOQUEANTE | **dueño** (con `parada.json` y la tabla de ciclos) |
| Ficha MU/EU que no se sostiene; fuera de macro | **D1** (`devolucion_d1.json`) |
| Reglas de claims por locale ausentes; ayuda del país; matriz país × nivel; `lineas_rojas` | **X1** (pedido en `dependencias.md`) |
| CPM, métodos de pago, IVA, mercado sin aprobar | **M1** / **F1** |
| Contrato sin forma para lo que hay que decir (`parada.json`, `codigos de eje`) | **contratos** (pedido) |
| Cambiar `parametros.yaml` o `limites.yaml` | **nadie en D3**: solo el dueño (D3 puede dejar una **propuesta** en `oferta.md` §E) |
