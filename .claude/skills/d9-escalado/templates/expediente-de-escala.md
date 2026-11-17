# Expediente de escala — <oferta_id> · <locale> · <AAAA-MM-DD>

> v0.1 sin pulir. **Estado: PROPUESTA.** Nada de lo de abajo está ejecutado ni autorizado: lo ejecuta el guard/robot de código o el dueño, con sello de X1 y respetando PAUSA y los frenos. Toda cifra viene de una fuente citada o del dictamen del código; lo que no tiene fuente va como `[SUPUESTO]`, `[SIN DATO]` o `[VERIFICAR]`. Modo: `EVALUAR | SUBIR | GRADUAR | REPLICAR`. Skill 0.1.0.

## Para el dueño (≤ 10 líneas)
- **Qué se propone:** <graduar a una ESCALA nueva | subir la ESCALA de X a Y | reducir 30 % | no proponer nada | replicar a <locale>>.
- **Por qué:** <1-2 líneas con las cifras del dictamen: compras netas, CPA, P, señales>.
- **Dinero en riesgo (peor caso, del dictamen):** <máximo teórico diario tras la propuesta, holgura bajo el techo de 300, pérdida acumulada + spend_cap restante frente a −3.000>.
- **Qué la refutaría:** <dato observable y fecha>.
- **Quién ejecuta y cuándo:** <gate efectivo hoy; comando o clic; sello de X1 pendiente o vigente>.
- **Qué necesito de ti:** <preguntas bloqueantes, máx. 8; «ninguna» si no hay>.

## 0. Puertas
| Puerta | Valor | Fuente (ruta · hash) |
|---|---|---|
| `empresa/PAUSA` | no existe | `<ruta>` |
| Límites completos para `escalar` (`engine.limites estado --operacion escalar`) | exit <0 \| 5> | `<salida>` |
| Fase de la oferta | `<en_test \| validada \| escalando>` | `ofertas/<id>/estado.json` |
| `locale` ∈ `locales_permitidos` | <sí/no> | `empresa/limites.yaml` |
| Nivel de D9 | `<N0..N4>` | `empresa/autonomia.yaml` |
| Gate efectivo (el más estricto) | `<H/S/A>` | `contratos/gates.json` · `limites.acciones_gate_humano` · autonomía |

## 1. Entradas y su origen
| Campo de `entrada-dictamen.json` | Valor | Ruta de origen · hash | Lo produjo |
|---|---|---|---|
| `metricas.compras_netas` | <n> | `<ruta>` | código |
| `metricas.cpa_neto_minor` / `cpa_be_minor` / `cpa_obj_minor` | <…> | `03-oferta/economia.json`, `08-operacion/…` | código |
| `metricas.p_cpa_menor_equilibrio` | <0,xx> | `08-operacion/decisiones.jsonl` (`evidencia.p_cpa_menor_equilibrio`) | D8 |
| `metricas.cpa_7d_minor` / `cpa_3d_minor` / `cpa_72h_minor` | <…> | `<ruta>` | código |
| `metricas.presupuesto_previo_gastado_pct` | <n> | `<ruta>` o `[SIN DATO]` | código (P-16) |
| `elegibilidad.*` (11 banderas) | <…> | sello de X1, preflight, `senal_pausa.json`, `meta.monitor`, D8 | código |
| `cuenta.activas`, `gasto_vitalicio_minor`, `ultimo_aumento` | <…> | `<ruta>` | código (Meta/Stripe) |
| `spend_cap_restante_minor` | <n> | `07-campana/campana.json` (lo define D7) | D7/código |
`entrada-dictamen.json` sha256: `<hash>`. Ninguna cifra fue tecleada de memoria.

## 2. Dictamen del código (pegado literal)
Comando: `.venv/bin/python .claude/skills/d9-escalado/scripts/escala_lectura.py dictamen --entrada entrada-dictamen.json --limites empresa/limites.yaml --parametros empresa/parametros.yaml` · salida sha256 `<hash>`.
```json
<salida literal: estado, codigo, ganador, senales, techo, paso, orden_borrador, motivos>
```

## 3. Ganador y señales
- Nivel: `<SIN_SENAL|VENDIO|RENTABLE|CAMPEON|VALIDADA>` — cumple: <…> — no cumple: <…>. Umbrales en `parametros.yaml` (`<sin firmar → [SUPUESTO]>`).
- Retorno de 7 días: <sí/no> · tendencia de 3 días: <sí/no> · compras de la ventana: <ok/no> · presupuesto previo gastado: <ok/no> · datos maduros: <sí/no>.
- Saturación / fatiga (alerta de D8 o de la alarma de cansancio): <sin alerta | alerta abierta | `[SIN DATO]`>. Estacionalidad del mercado (Black Friday 2026-11-27, Cyber Monday 2026-11-30 `[VERIFICAR]`): <sí/no>.

## 4. Techos y frenos de empresa (J4)
| Freno | Tope | Usado hoy | Tras la propuesta | Holgura |
|---|---|---|---|---|
| `gasto_diario_global` (máx. teórico ×1,75) | <…> | <…> | <…> | <…> |
| `gasto_diario_por_oferta` | <…> | <…> | <…> | <…> |
| `perdida_neta_acumulada_max` (pérdida + spend_cap restante) | <…> | <…> | <…> | <…> |
| `limite_gasto_cuenta_meta` | <…> | <…> | <…> | <…> |
Lectura de «300 US$/día» aplicada: <máximo teórico (código)> — pregunta abierta al dueño. Caja (F1): `[SIN DATO]` (P-10).

## 5. Tesis causal (5 líneas)
1. <por qué el CPA marginal aguantaría> 2. <…> 3. <…> 4. <…> 5. <…>
- **Qué la refutaría:** <dato + fecha de lectura>. **Plan B:** <reducir 30 % / volver al presupuesto anterior / relevo de creativos>.
- Si el dictamen dijo NO: <por qué no y qué lectura cambiaría la respuesta>.

## 6. Palanca
Elegida: <relevo de creativos | vertical (graduar/subir) | otra ESCALA | réplica>. Descartadas y por qué: <…>. Fuera de v0.1: backend, retiro, clon.

## 7. Propuesta
| Objeto | Antes | Después | Δ % | Regla | Recortes del código |
|---|---|---|---|---|---|
| <nombre de campaña> | <…> | <…> | <…> | `<D9-E1 \| D9-R1>` | <…> |
`propuesta-de-suba.json` sha256 `<hash>`; `orden_presupuesto` en estado `propuesta`, `aprobado_por = null`.

## 8. Ejecución y pendientes
- Gate efectivo hoy: `<H>` → ejecuta `<el dueño | guard/robot>`; sello de X1: `<vigente hasta … | pendiente>`; preflight D7 (si hay ESCALA nueva): `<…>`.
- **No ejecutable hasta:** <P-05 cost cap · P-13 filtro de idioma · P-04 J2 …> (ver `PEDIDOS.md`).
- Evaluación a 96 h: <fecha>; la reversión la hace el código si el paso es «malo».

## 9. Supuestos, sin dato, por verificar, preguntas bloqueantes
`[SUPUESTO]` <…> · `[SIN DATO]` <…> · `[VERIFICAR]` <…> · Preguntas: 1. <…>

## 10. Registro de QA
| Ronda | `d9-qa` veredicto | Puntaje | Hallazgos abiertos | Archivo |
|---|---|---|---|---|
| 1 | | | | `qa/d9-v1.json` |
