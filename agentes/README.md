# agentes

Runtime de ejecución desatendida de Makers y QA con mínimo privilegio: un proceso `claude -p` por
rol y por corrida, hooks fail-closed, y validación de la salida **fuera** del modelo (docs/09,
docs/06 §4.6). Propietario: **B9** (ola 1). Aceptación: **B0-08**.

## Estado

Construido en una sesión nocturna de B0 (modo prueba): `runner`, `hooks/*`, `perfil`, `contexto`,
`sonda_hooks`, 10 fixtures de `tests/fixtures/agentes/`, plantillas de `.claude/agents/` y
`settings.propuesto.json` (B9 no tiene permiso de escribir `.claude/**`: ver «Pedidos»). Probado en
modo `FIXTURE`/`DRY_RUN`; el modo `LIVE` tiene preflight y ejecución de proceso implementados pero
**nunca** se ejecutó esta noche (sin red, sin credenciales, sin `--live`, reglas de la construcción).

## Módulos

| Módulo | Qué hace |
|---|---|
| `tipos.py` | `Modo`, `Presupuesto`, `EspecCorrida`, `ResultadoCorrida`, `PlanCorrida` (docs/09 §12.1, firmas congeladas) y `espec_desde_mapa` (deserialización de `--espec`). |
| `runner.py` | `preparar(espec) -> PlanCorrida` (puro) y `ejecutar(espec, *, modo, fixture_dir=None, raiz=None, env=None, ahora=None) -> ResultadoCorrida`. Valida la salida igual en `FIXTURE` y `LIVE` (§12.6): esquema, artefactos dentro de `rutas_escribibles`, anti-sello-de-goma del QA, bucles (§12.5), y el preflight de 7 pasos antes de cualquier `--live` (§12.3). |
| `perfil.py` | `construir_settings_efectivo` (allow/deny del rol), `construir_entorno` (entorno MÍNIMO del hijo, construido desde cero) y `construir_argv` (invocación canónica, reutiliza las banderas de `scripts/lanzar_hijos.py`). |
| `contexto.py` | Cuarentena de texto no confiable para el QA (`construir_claim(s)`: cita ≤ 200 caracteres entre `<<DATO_NO_CONFIABLE>> … <<FIN>>`, nunca `crudo/**`) y `TABLA_ETAPAS` (lecturas, rutas escribibles, scripts permitidos y esquema de salida por etapa; primer borrador, ver «Decisiones»). |
| `sonda_hooks.py` | Banco de entradas sintéticas que **deben** dar `exit 2` en cada hook (docs/09 §14.6); construye su propia «empresa» desechable (nunca `empresa/` real). CLI y función `correr()` reutilizable desde pruebas. |
| `prueba_s1.py` | `EspecCorrida` de la prueba **S-1** (docs/06 §8 ola 3): corrida real mínima con una skill de humo y presupuesto de centavos. Esta sesión solo construye el script; la corrida real (`--live`) la hacen el dueño/I1 más adelante. |
| `hooks/_comun.py` | Envoltorio fail-closed: `ejecutar` (deny por stderr/exit 2) y `ejecutar_con_salida` (decisión estructurada por stdout, para `Stop`). Cualquier excepción, JSON roto o timeout interno → `exit 2`. |
| `hooks/herramientas.yaml` | Clasificación lectura/neutra/escritura/créditos (lo desconocido es **escritura**) y lista blanca de scripts `Bash` con sus flags. |
| `hooks/pretooluse_gasto.py` | Bloquea gasto/escritura si hay `PAUSA`, falta `max_budget_por_corrida_agente`, la infra no está VERDE/fresca, falta cotización de créditos, la ruta de escritura está fuera del staging o hay un patrón de secreto. |
| `hooks/pretooluse_activacion.py` | Activar/pausar solo con sello de X1 y `object_ids` exactos; dos ramas (MCP en borrador y Marketing API por `Bash --live`, crítica M07); `ads_delete_*`/`ads_catalog_*` siempre prohibidas. |
| `hooks/pretooluse_bash.py` | Argumentos de `Bash` (crítica M12): rechaza metacaracteres de shell, exige script en lista blanca, flags en lista blanca por script y rutas dentro de `ofertas/<id>/`. |
| `hooks/posttooluse_registro.py` | Anota cada llamada en `$AGENT_SPOOL` (tamaño y hash, nunca contenido ni `tool_response`). |
| `hooks/stop_verificacion.py` | Exige que la salida del Maker valide contra su contrato antes de terminar; en el QA, solo que el mensaje mencione «veredicto». Cortesía: el runner revalida siempre. |

## CLI (ejemplos que funcionan con los fixtures)

```bash
# Plan (dry-run): construye argv/settings/entorno y los imprime; NO ejecuta nada.
.venv/bin/python -m agentes.runner --espec tests/fixtures/agentes/D3_maker_ok/espec.json

# FIXTURE: reproduce una corrida grabada, sin procesos ni red.
.venv/bin/python -m agentes.runner --espec tests/fixtures/agentes/D3_maker_ok/espec.json \
    --fixture tests/fixtures/agentes/D3_maker_ok

# Perfil: imprime settings.efectivo.json y el entorno del hijo (secretos enmascarados).
.venv/bin/python -m agentes.perfil --espec tests/fixtures/agentes/D3_maker_ok/espec.json

# Sonda de hooks: 0 si el 100 % de los casos dio exit 2; 1 si alguno se filtró.
.venv/bin/python -m agentes.sonda_hooks

# Prueba S-1 (dry-run; con --live exige producción + ANTHROPIC_API_KEY real, NO usar esta noche).
.venv/bin/python -m agentes.prueba_s1
```

Códigos de salida de `agentes.runner` (convenciones §8; docs/09 §12.1): 0 ok · 1 interno ·
2 uso · 3 inválido · 4 bloqueado/pausa/preflight · 5 presupuesto/turnos · 6 timeout/bucle/error.

## Entradas, salidas y variables de entorno

- Entrada: un `espec.json` (`EspecCorrida` serializada). Salida: JSON de `ResultadoCorrida` en stdout.
- El entorno del HIJO (`agentes.perfil.construir_entorno`) se construye desde cero; solo copia del
  proceso externo `ANTHROPIC_API_KEY` y `FABRICA_FIRMA_PUBLICA` (pública, no es secreto). Nunca
  contiene claves de Stripe, Meta, `SELLO_*` ni `GITHUB_TOKEN` (probado en `tests/agentes/test_runner.py`
  y `test_perfil.py`).
- Variables nuevas (ver `.env.example`, pedido a A0/infra): `FABRICA_FIRMA_PUBLICA` (ya documentada
  por convenciones §5), `AGENT_HOOK_PLAZO_S` (opcional; plazo interno de los hooks, por defecto 10 s).

## Cómo probar

```bash
.venv/bin/python -m unittest discover -s tests/agentes -t .
```

86 pruebas (ninguna abre `socket`). Incluye los 10 casos de `FIXTURE` (§12.8), la sonda de hooks
completa (15 casos, 100 % `exit 2`), casos límite de cada hook (tope exacto de edad, PAUSA, límites
ausentes, secretos, créditos) y la construcción de `settings.efectivo.json`/entorno.

## Decisiones

1. **Sin permiso para `.claude/**`**: en vez de ampliar `.claude/settings.json`, se entrega
   `agentes/settings.propuesto.json` (contenido exacto del piso de docs/09 §6, con los tres hooks
   `PreToolUse` separados por claridad) y las plantillas de `.claude/agents/` en
   `agentes/plantillas_agentes/` (`d3-maker.md`, `d3-qa.md` como ejemplo; el patrón se repite por
   etapa). El dueño los instala a mano.
2. **Ruta de staging**: `ruta_staging_relativa` usa el CÓDIGO de etapa (`D3`) tal cual como nombre
   de carpeta bajo `ofertas/<id>/.../D3/.staging/<run_id>/`, no el nombre numerado del backbone
   (`03-oferta`). Mapear uno a otro es tarea de quien integre con `engine.orq` (B1); hasta entonces,
   el runner es consistente consigo mismo (sonda, fixtures y pruebas usan el mismo código).
3. **`run_id` determinista**: hash de `(etapa, rol, oferta_id, agente, ronda, prompt_base[:200])`
   en vez de UUID, para que `preparar()` sea reproducible y testeable sin inyectar un generador.
4. **`contrato_salida` == contrato del artefacto** en etapas de un solo archivo (p. ej. D3: el
   `structured_output` del Maker es el mismo `oferta.json` que se valida y promueve). Evita inventar
   un esquema de «manifiesto» que no existe en `contratos/` (soy B9, no puedo crear esquemas nuevos).
5. **Pretooluse_activacion sin `hash_config` en la rama MCP**: el esquema real de
   `ads_activate_entity` no trae ese campo (no es nuestro, es del conector). El hook busca, entre los
   sellos VIGENTES y FIRMADOS de `AGENT_OFERTA_ID`, uno cuyo `object_ids` sea EXACTAMENTE
   `{entity_id} ∪ object_ids` del `tool_input`; ninguno o más de uno que empate deniega (regla 5 de
   §14.3, «cualquier ambigüedad deniega»). La rama `Bash` (Marketing API real) sí usa `--hash-config`.
6. **`pretooluse_gasto` no verifica criptográficamente la firma de `estado.json`**: los hooks corren
   en el mismo proceso/entorno que el agente (H7) y no reciben `PREFLIGHT_HMAC_KEY` (sería un secreto
   expuesto al modelo). Solo comprueba que el campo `firma` esté presente, el modo, el semáforo, los
   ítems y la edad. La verificación criptográfica completa vive en `engine.guard` (de B1), que el
   motor corre fuera del proceso del agente antes de cualquier efecto real.
7. **`agentes.sonda_hooks` reutiliza, solo de LECTURA, los fixtures de límites/parámetros de B1**
   (`tests/fixtures/engine/empresa_prueba/{limites,parametros}.yaml`) para no reinventar ~40 claves
   obligatorias del esquema de límites; les copia y ajusta solo lo que cada caso necesita en una
   carpeta temporal propia. Nunca escribe ahí ni depende de `tests/engine/` en tiempo de ejecución
   (genera sus propias claves Ed25519 efímeras con `ssh-keygen`, igual técnica que `tests/engine/apoyo.py`
   pero sin importar el paquete de pruebas desde código de producción).
8. **`TABLA_ETAPAS` de `contexto.py` es un primer borrador** (D1-D7, X1): cubre las columnas pedidas
   por docs/06 §4.6 pero los patrones de ruta (`<run_id>`, `<etapa_objetivo>`) los resuelve quien
   arma el `EspecCorrida` real (el motor/orquestador de B1), no este módulo.
9. **LIVE implementado pero nunca ejecutado esta noche**: el preflight (7 pasos, §12.3) y el
   lanzamiento de proceso están escritos y se prueban SOLO hasta el punto en que fallan cerrado (p.
   ej. `FABRICA_ENTORNO != produccion`, o falta el grupo `parametros.agentes`, que hoy no existe en
   `empresa/parametros.yaml` real). Nunca se invocó `claude -p` de verdad ni se usó `--live`.

### Añadido tras la ola 2 (constructor principal, 2026-11-06)

- **SB-1 (seguridad): la rama Bash de `pretooluse_activacion.py` gobierna los CLI REALES.** Cubre `scripts/meta_activar.py`,
  `meta_crear.py`, `subir_presupuesto.py`, `python -m meta.{activar,crear,subir_presupuesto}` y `python -m engine.orq activar`;
  cuenta como VIVO `--live`, `--modo live`, `--modo=live`, `--modo` sin valor o con un valor que no sea `dry-run`/`fixture`
  (o repetido con valores distintos); los `object_ids` salen de `--object-ids` (separados por comas o por espacios) y/o del
  archivo de `--ids-meta` (`{campaign_id} ∪ adset_ids ∪ ad_ids`, el mismo conjunto que activa `meta.activar`; debe estar dentro de
  `ofertas/<id>/`) y, si vienen de las dos fuentes, deben coincidir; sin ids en modo vivo se deniega. Pausar (`meta.pausar`,
  `scripts/pausar.py`) NO se gobierna: es la acción segura. La sonda suma 4 casos (19 en total, todos exit 2).
- **SB-11 (QA previo):** mientras `scripts/validar_esquemas.py` (X18) exija que `qa/*.json` se llame `<etapa>-<version>.json`
  (LT-43 pendiente de CT), el runner NO debe escribir el QA-A previo en `qa/`: va en `qa/.previo/<etapa>-v<n>-previo.json`
  (fuera del glob). Hoy el runner no lo produce; la regla queda fijada para quien lo construya.

## Pedidos

- **Al dueño / A0**: rellenar el grupo `agentes.*` de `empresa/parametros.yaml` (el esquema YA lo
  admite en `contratos/parametros.schema.json`, confirmado esta noche) y `max_budget_por_corrida_agente`,
  `creditos_max_pieza`, `creditos_max_oferta` de `empresa/limites.yaml` (hoy en `null`: sin ellos,
  `agentes.runner` en modo `LIVE` siempre da `preflight` — correcto y esperado, fail-closed). Instalar
  `agentes/settings.propuesto.json` como `.claude/settings.json` y copiar las plantillas de
  `agentes/plantillas_agentes/` a `.claude/agents/` (repitiendo el patrón por cada etapa con Maker/QA).
- **A B1 (`engine.orq`, cuando exista)**: resolver `ruta_staging_relativa` con el nombre numerado real
  de carpeta de cada etapa (hoy uso el código de etapa tal cual, Decisión 2) y los patrones de
  `contexto.TABLA_ETAPAS` con el `oferta_id`/`run_id` reales antes de armar el `EspecCorrida`.
- **A X1 / B1 (sellos)**: confirmar si `ads_activate_entity` vía MCP debería llevar un campo propio
  de `hash_config` (hoy no existe en el esquema del conector); si se agrega, `pretooluse_activacion.py`
  puede dejar de buscar por `object_ids` entre todos los sellos vigentes de la oferta y comparar
  directo por hash, simplificando la Decisión 5.
- **A CT (contratos)**: si en el futuro se quiere validar el manifiesto de un Maker (artefactos +
  supuestos + riesgos) por separado del artefacto de negocio, falta un `contratos/manifiesto.schema.json`;
  hoy `agentes.runner` asume que, en etapas de un solo artefacto, `contrato_salida` es el contrato de
  ese artefacto (Decisión 4).

## Riesgos conocidos (no resueltos esta noche)

- El modo `LIVE` nunca se ejecutó contra un proceso `claude` real: los pasos de §12.4 (verificación
  del evento `system/init`, detección de bucles sobre un stream real) están escritos pero no
  probados contra el binario real. La **prueba S-1** (`agentes/prueba_s1.py`) es exactamente para
  cerrar esa brecha, pero la ejecuta el dueño/I1, no esta sesión.
- `pretooluse_activacion.py` (Decisión 5) depende de que, en la práctica, nunca haya dos sellos
  vigentes con el mismo `object_ids` para la misma oferta; si alguna vez eso ocurre, el hook deniega
  por ambigüedad (fail-closed) en vez de elegir uno — correcto, pero puede bloquear una activación
  legítima hasta que se archive el sello viejo.
