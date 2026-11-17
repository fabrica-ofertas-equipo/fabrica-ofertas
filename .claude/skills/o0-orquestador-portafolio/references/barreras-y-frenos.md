# Barreras de seguridad, kill switch y descensos (lo que la skill debe saber decir)

Todo lo que mueve dinero, publica o afecta reputación o cumplimiento tiene guardarraíl **determinista** (hooks, `limites.yaml`, scripts) en todo nivel; el gate decide *quién aprueba*, no *si hay topes*. Esta skill **no implementa** nada de esto: lo explica y lo respeta.

## 1. Kill switch de tres capas
1. `empresa/PAUSA` (archivo; fuente = almacén del motor, espejo en el KV del watchdog): bloquea toda herramienta de agente con efecto, detiene barridos de D1, pausa campañas en ≤ `parametros.orquestador.pausa_global_max_min`, y detiene gasto, activación, publicación, correo de marketing y reembolsos **automáticos** (estos pasan a la cola humana). **No detiene** la entrega del producto ya pagado (webhook, `fulfill`, `descarga`) ni los correos transaccionales (cortarlos genera disputas; R17). **Borrarla no reactiva nada**; solo el dueño la levanta, y reactivar una campaña pausada es H en todo nivel.
2. Script de pausa por API de Meta (`scripts.pausar`).
3. Límite de gasto de la cuenta en Meta (`limites.limite_gasto_cuenta_meta`) y tarjeta con tope: último freno del dueño.
Con el motor caído, el runbook pausa a mano en Ads Manager. Watchdog independiente (Cloudflare Worker): sin latido más de `parametros.watchdog.latido_max_min`, pausa campañas.

## 2. Hooks `PreToolUse` (fail-closed) y rutas protegidas
`pausa`, `gasto` (matcher `mcp__.*`: el `.*` es obligatorio), `creditos`, `protegidos` (escritura y borrado de `limites.yaml`, `parametros.yaml`, `.claude/**`, `contratos/**`, `scripts/**`, `.env`, `estado.json`, `registro.jsonl`, `costos.jsonl`, `autonomia.yaml`, `portafolio.json`, `decisiones_dueno.jsonl`, `.lock`; nadie borra `PAUSA`), `secretos` (`sk_`, `rk_`, `whsec_`, `EAA…`). Implementados en `agentes/hooks/`; `[VERIFICAR]` que reconozcan los conectores claude.ai y corran en `claude -p` (hasta probarlo: sin MCP de escritura y activar por script).

## 3. Descenso y frenos automáticos (umbrales en `parametros.yaml`; el LLM no los toca)

| Disparador | Acción | Claves |
|---|---|---|
| Gasto del día ≥ `freno_pct` o libro de gasto > límite | pausar campañas + `PAUSA` + alerta | `parametros.orquestador.freno_pct`, `gasto_alarma_pct` |
| Clics sin vistas de landing; compras sin evento servidor (24 h); regla de corte de `decision/` | pausar la oferta, revisión H | `testeo.k_corte`, `orquestador.p_viable_descartar` |
| Reembolsos o disputas sobre el umbral de la oferta (un escalón menos en amarillos) | pausar la oferta; sobre el umbral del macro-nicho: **pausa del macro-nicho; levanta solo el dueño** | `parametros.salud_operativa.*` |
| Rechazo de Meta de producto o contenido | congelar la hoja; de pieza revertido en revisión, solo el ángulo | `compliance.rechazos_congelar` |
| Cuenta ≠ ACTIVE, advertencias o rechazos repetidos; Stripe con monitoreo VAMP, suspensión o cierre | `PAUSA` global (y baja a N1 en el primer caso) | `compliance.rechazos_ventana_dias` |
| BLOQ escapado, 2 escalamientos seguidos o ≥ 3 `deny` de dinero en 24 h | la etapa baja un nivel (en el tercer caso, global a N2) | — |
| Pérdida neta acumulada ≥ `limites.perdida_neta_acumulada_max` | `PAUSA` global; solo el dueño levanta | `limites.perdida_neta_acumulada_max` |
| Latido ausente | el watchdog pausa campañas (dead-man) | `watchdog.latido_max_min` |

## 4. Secretos y firmas
Solo el motor tiene los secretos. Stripe con clave restringida; Meta con usuario de sistema mínimo sobre **una** cuenta. Toda aprobación H se firma con la clave Ed25519 del dueño (`orq firmar --hash-objetivo … --clave-privada <RUTA>`; la ruta la pone él), fuera del alcance de los agentes. **Riesgos aceptados por el dueño** (decisiones 14 y 15): sin revisión legal humana y sin gestor de contraseñas, llaves físicas ni segundo administrador; los frenos de software no cambian. La skill no los presenta como tareas pendientes.

## 5. Qué dice el agente ante cada frenazo
Primera línea de la respuesta: «PAUSA activa desde <ts> por <motivo>: no se ejecuta ni se activa nada». Luego: qué quedó pausado, qué **no** se detiene (entrega), quién levanta y con qué: `reanudar` **no está en la CLI de `engine.orq`** (solo existe la función de Python, que exige `firma_verificada` e `infra_verde`) `[PENDIENTE]`; reactivar una campaña pausada es H en todo nivel.
