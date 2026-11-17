# Activación: sello de X1, firma H y el expediente que prepara el agente

**El agente nunca activa ni programa un inicio.** Activar = código (`meta.activar`) + sello de X1 + orden firmada del dueño. El agente deja el expediente listo y se detiene.

## 1. Cadena de condiciones (todas, en este orden; la primera que falla frena)

| # | Condición | Quién la produce / verifica |
|---|---|---|
| 1 | `campana.json` sellado (`hash_config`) y `estado = preflight_ok` | Maker (`d7.py sellar`) |
| 2 | `ids_meta.json` con los IDs del borrador `PAUSED` | `meta.crear` (código) |
| 3 | `preflight.json` VERDE, `modo` vivo, `valido_hasta` > ahora (< `campana.preflight_vigencia_h`) y `hash_config` = el de `campana.json` | `meta.preflight` (código) |
| 4 | QA D7 = `PASS` (`qa/d7-v<n>.json`), máx. `orquestador.max_rondas_qa` rondas | agente `d7-qa` |
| 5 | **Sello de X1** sobre `hash_config` + `object_ids` exactos y vigente (`sello.vigencia_hasta`), con dictamen `PASS` | X1 (`compliance.sellar`) → `empresa/compliance/sellos/<hash>.json` |
| 6 | **Gate H**: el dueño lee la tarjeta y firma `accion: activar_campana` (Ed25519, clave privada solo en su equipo, **fuera de la sesión del agente**) con `hash_objetivo = hash_config` | dueño: `python -m engine.orq firmar --oferta … --accion activar_campana --hash-objetivo sha256:… --clave-privada <ruta que fija el dueño> --como dueno`. La ruta de la clave la pone el dueño: nunca en un chat ni en el repositorio. `firmar` aún no admite `--object-ids` `[PENDIENTE: SB-2]` |
| 7 | `aprobacion.json` (la escribe el motor tras verificar la firma; el agente no puede) | motor `[PENDIENTE: SB-2]`: hoy nadie lo escribe |
| 8 | `meta.activar`: sello válido (TOCTOU), 7 pasos de `engine.guard` (entorno, PAUSA, infra < 6 h, límites, topes agregados, credenciales, orden firmada), relectura del árbol vivo = `object_ids` exactos, **relectura del estado vivo comparada campo por campo con `campana.json`**, activa anuncios → conjunto → campaña, relee `effective_status` y pausa lo imprevisto | código (`python -m scripts.meta_activar`, solo dry-run/fixture; `engine.orq activar --live` bloqueado) |

Hooks (`agentes/hooks/pretooluse_activacion.py`): `ads_activate_entity` y todo publish = `deny` salvo sello + `aprobacion.json` + hash + `object_ids`; `ads_update_entity` solo `{"status":"PAUSED"}`; presupuesto o `spend_cap` fuera de límites, cuenta fuera de `cuentas_permitidas`, `PAUSA` o infra no VERDE = `deny`. Los hooks gobiernan las herramientas MCP; los CLI de `meta/` usan `--modo live`/`--ids-meta`, que el hook no ve `[PENDIENTE: SB-1]`. **Hoy no hay `.claude/settings.json` instalado** (solo propuestas): sin él no hay hook (`dependencias.md` A7).

Cualquier cambio posterior al sello (presupuesto, `spend_cap`, evento, targeting, creativo, enlace, textos, DSA, edición en Ads Manager) cambia el hash vivo ⇒ no se activa; vuelve a empezar desde el paso 1. Estructura congelada 72 h tras activar.

## 2. Qué NO está resuelto todavía (citar, no inventar)

- `meta.activar` ya relee el estado vivo y lo compara con `campana.json` (presupuesto, `spend_cap` o candado, evento, targeting, creativo, categorías). Quedan: enlace y textos solo con `--creativos`, y el DSA propio hasta que exista `campana.economia.dsa` (LT-10) `[PENDIENTE: CT-3]`.
- `--modo live` de `meta.crear`/`meta.activar` está bloqueado (sin Transporte real): hasta entonces, la activación humana es en Ads Manager **solo** tras comprobar a mano que el árbol de IDs = `ids_meta.json`, que ningún objeto sobra y que `hash_config` de la tarjeta = el sellado por X1. El agente no la ejecuta.
- **C-04 (abierta, decide el dueño: K-02/D-02):** `limites.acciones_gate_humano` fija `activar_campana` como H **siempre** (no se puede quitar, ni con firma) y `contratos/gates.json` (`accion:activar_campana`) la pone en **S** en N3/N4. **Gate efectivo = el más estricto = H en todo nivel** hasta que el dueño decida D-02. La skill **no elige**: v0.1 se usa en N0–N2. No hay comportamiento N3/N4 definido aquí (nada de «orden por regla»).
- Programar un inicio futuro ya es activar: mismo gate.

## 3. El expediente (lo que el Maker deja en `07-campana/` y entrega al dueño)

1. `campana.json` sellado · 2. `ids_meta.json` · 3. `preflight.json` (+ `modo` en el log) y `lectura_viva.json`, ambos de código · 4. `lanzamiento.log` (cada lectura y llamada, con valores literales) · 5. vistas previas por anuncio y ubicación (referencias del log) · 6. `tarjeta-gate.md` (una página) · 7. plan de vigilancia con las cinco ventanas (T+1, 6, 24, 48, 72 h) calculadas desde el instante de activación · 8. lista de preguntas abiertas / `[SUPUESTO]` · 9. pedido de sello a X1 con `hash_config` + `object_ids`.

### Tarjeta de gate (`templates/tarjeta-gate.md`; el dueño decide en 2 minutos)

Gasto máximo (diario, máximo teórico, `spend_cap` o candado, **con tarifa**, 24 h / 7 d / total) · CPA de equilibrio visto y facturado, objetivo y corte · evento y cuánto falta para PURCHASE · **¿valida o solo refuta?** · nivel de riesgo, reencuadre aplicado y `claims_a_evitar` respetados · `problema_id`/`candidato_ref` · países, idioma, audiencia · DSA (beneficiario y pagador) · `hash_config` · `object_ids` · sello de X1 y QA · riesgos y `[SUPUESTO]` · preguntas abiertas · qué ocurre si dice «no».

## 4. Al firmar

El dueño firma el `hash_config` que ve en la tarjeta. Si la tarjeta y `campana.json` difieren en una cifra, es un defecto BLOQ del Maker. La clave privada nunca pasa por el chat ni por el repositorio. Reactivar tras una pausa (`accion:reactivar_tras_pausa`) es H siempre, aunque la pausa haya sido errónea.
