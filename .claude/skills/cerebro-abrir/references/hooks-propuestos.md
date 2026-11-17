# Hooks y avisos propuestos del Cerebro (NADA de esto está instalado)

> Propuesta de S-C (2026-11-07) para B1-09 y B4-21. Este archivo es **texto**: no toca los ajustes del proyecto (`.claude/settings.json` todavía no existe), no programa ningún trabajo y no envía nada. Lo que se instale lo decide el dueño (o S-B, para el planificador y el canal de avisos). `[VERIFICAR]` marca lo que hay que comprobar en la versión instalada de Claude Code antes de activarlo.

## 1. Hook de apertura (`SessionStart`)

Imprime al abrir una sesión el resumen corto (los P0 completos más conteos de lo no aprobado, lo que vence, el último cierre y el primer paso):

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "startup|resume",
        "hooks": [
          {
            "type": "command",
            "command": ".venv/bin/python \"$CLAUDE_PROJECT_DIR\"/.claude/skills/cerebro-abrir/scripts/resumen_abrir.py --corto --noop-si-agente"
          }
        ]
      }
    ]
  }
}
```

Condiciones, todas comprobadas por la prueba `tests/cerebro/test_abrir_ampliado.py`:

- **Solo lectura:** el script no escribe nada (la prueba lo vigila con un gancho de auditoría).
- **No-op para agentes:** con `--noop-si-agente` no imprime nada si existe `AGENT_RUN_ID` (los runners de `agentes/perfil.py` lo ponen y usan `--setting-sources project`; un agente que corre solo no debe recibir el resumen del dueño).
- **Los P0 nunca se recortan:** el resumen corto lista todos, uno por línea.
- `[VERIFICAR]` que en la versión instalada la salida estándar de un `SessionStart` se agrega al contexto de la sesión (así lo documenta Claude Code para este evento) y que el hook corre con el directorio del proyecto como directorio de trabajo.
- Debe esperar a **N2** y al `[VERIFICAR]` anterior (`CHANGELOG.md`, checklist a 1.0.0).

## 2. Hook de cierre: NO se propone uno que escriba

Un hook al terminar la sesión (`SessionEnd`/`Stop`) no puede preguntarle nada al dueño, y `/cerebro-cerrar` no guarda nada sin su confirmación ítem por ítem. Por eso **no** se propone ningún hook que guarde decisiones, pendientes, lecciones o preferencias al cerrar.

Lo que sí hay para que el cierre no se olvide:

- La apertura dice cuándo fue el **último cierre** (`cerebro.ultimo_cierre`, deducido del `origen` «… /cerebro-cerrar» de las líneas guardadas) y, si nunca hubo uno, lo dice.
- El resumen diario (abajo) repite «Último cierre de sesión: hace N días / nunca».
- `[PENDIENTE: registro de cierres]`: un archivo propio con cada cierre (con X2). Hoy se deduce de las líneas guardadas.

## 3. Resumen diario al celular (08:30)

`resumen_abrir.py --resumen-diario` imprime ≤ 8 líneas de texto plano: estado de PAUSA y freno, conteos (P0, P1, firmas, reglas por aprobar), los títulos de los P0 (≤ 4), lo que vence, el último cierre y el primer paso. **Sin importes** (se enmascaran como `[importe]`): regla del mapeo §9, «importes en el correo, porcentajes en el celular».

Línea de ejemplo para un planificador (la hora, el host y el canal los decide el dueño: `PUL-0002` y `PUL-0003`):

```
30 8 * * *  cd "<raíz del proyecto>" && .venv/bin/python .claude/skills/cerebro-abrir/scripts/resumen_abrir.py --resumen-diario --noop-si-agente | <productor de avisos del canal elegido>
```

- **Quién envía:** el productor de avisos de S-B, cuando exista el canal (`docs/_historial/mentor-sistema/brechas/04-operacion-autonoma.md` B4-24: componer lo hace S-C, enviar lo hace S-B). Este script solo da el texto.
- **El informe completo de las 08:30** (ventas, gasto y alertas) es el informe diario de `scripts/informe`; este resumen es la parte del Cerebro que se le puede sumar.

## 4. Domingo: el jardinero en seco

```
0 20 * * 0  cd "<raíz del proyecto>" && .venv/bin/python scripts/cerebro/jardinero.py | <productor de avisos>
```

Un robot puede **mandar la propuesta al celular**, pero no puede guardarla ni aplicarla: `--guardar-propuesta` exige `--confirmo-dueno` con las palabras del dueño, y el jardinero nunca cambia una línea de la memoria (`/cerebro-cerrar jardin`, y `tests/cerebro/test_jardinero.py`).
