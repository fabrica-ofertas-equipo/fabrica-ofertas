# Carril de preferencias: «con 2-3 correcciones aprende» (sin aprender sola)

> Brecha B1-05 del informe `docs/_historial/mentor-sistema/brechas/01-cerebro-y-creativos.md` (fuente `[V 27:30]` del video: con 2 o 3 correcciones aprende a hacer los creativos «como a vos te gusta»). Esta skill pone la parte que le toca (guardar y proponer); **leer las preferencias** es de cada skill de etapa, con el contrato de abajo. v0.2 sin pulir: ninguna corrida real.

## 1. El ciclo (quién hace qué y qué cambia en cada paso)

| # | Paso | Quién | Qué cambia en el sistema |
|---|---|---|---|
| 1 | El dueño corrige lo mismo (otra fecha u otra pieza, otras palabras) ≥ 2 veces | el dueño | nada |
| 2 | `/cerebro-cerrar` reúne las correcciones (fecha, sobre qué, sus palabras, archivo si hay) y **propone** la preferencia | la IA, con su confirmación | `guardar_pendiente.py preferencia --escribir` agrega **una línea abierta** en `empresa/panel/pulido.jsonl`: regla propuesta, categoría `pref`, responsable `dueno`. **Ninguna skill la lee.** |
| 3 | El dueño decide, con sus palabras | el dueño | — |
| 4a | **Aprueba** | `/cerebro-cerrar`, con su cita | `preferencia_resolver` agrega `estado: aprobada` en `empresa/memoria/preferencias.jsonl`. **Desde aquí rige** como criterio. |
| 4b | **Rechaza** | ídem | `estado: rechazada`: no se vuelve a proponer lo parecido (≥ 0,80). |
| 5 | **Revoca** (cambió de idea) | ídem | `estado: revocada` con `revoca: PRF-…`; deja de leerse y se puede volver a proponer con correcciones nuevas. |
| 6 | Cierra la propuesta en la lista | el dueño, en el panel | la lista única no se reescribe sola; la apertura y el jardinero se lo recuerdan |

**Por qué no hay forma de que se aplique sola.** (1) La propuesta es una línea de la lista única sin ningún campo de estado de aprobación: solo dice «abierta». (2) Aprobar es **otra función** (`resolver_preferencia`), con su propio subcomando, que exige las palabras del dueño y una propuesta abierta que exista; ninguna otra ruta del script escribe `aprobada`. (3) El lector (`scripts/cerebro/preferencias.py`) devuelve solo lo aprobado por el dueño y no revocado; una línea del buzón con otro autor, otro tipo o sin criterio no cuenta. (4) Proponer lo mismo una tercera vez no la promueve: el script lo rechaza como repetido. `tests/cerebro/test_preferencias.py` lo comprueba (incluida una revisión del código fuente). Lo que no puede impedir el código —que un agente ejecute `preferencia_resolver` por su cuenta— lo impide la regla 5 de la skill y que el comando exige `--escribir` y la cita.

## 2. Qué es y qué no es una preferencia

- **Es** un criterio del dueño sobre *cómo le gusta* algo: estilo de los estáticos, tono de los correos, largo de un titular, orden de las secciones. Con fecha y con las correcciones que lo respaldan.
- **No es** una regla ni un límite: no cambia `parametros.yaml`, `limites.yaml`, `autonomia.yaml`, `contratos/**` ni una rúbrica; no sustituye compliance (X1), la regla J13 (la idea se hereda, la forma se transforma, la expresión no se toca), J8 (nada de testimonios ni urgencias inventados) ni un veto. Si choca con alguno, **manda el otro** y la skill que la lee lo anota en su informe.
- **No es** un hecho del mercado ni un resultado («este gancho vende»): eso es de X2/D8 con evidencia.
- En la terminología de X2 (`departamentos/15-memoria-aprendizaje.md`): corresponde a `perfil_dueno.md` («preferencias y criterios de elección con fecha; nunca regla ni límite»), con `motivo_edicion: preferencia` que cuenta en el KPI pero **no alimenta patrones** de skill. Hasta que exista X2, el buzón es `empresa/memoria/preferencias.jsonl` (`dependencias.md` §B).

## 3. Contrato de lectura (para D6 y cualquier skill de etapa)

Antes de redactar su brief, una skill (o su Maker) pide **solo** las aprobadas de su etapa:

```
.venv/bin/python scripts/cerebro/preferencias.py --etapa D6 [--oferta OF-AAAAMM-NN] --texto
```

- **JSON** (sin `--texto`): `{etapa, oferta_id, preferencias: [{id, desde, etapa, alcance, oferta_id, criterio, correcciones, respaldo, aprobada_con, propuesta}], n, recortadas, propuestas_sin_aprobar, aviso, avisos, solo_lectura}`. `propuestas_sin_aprobar` es solo un conteo: **una propuesta no se lee ni se cita como criterio.**
- Máximo 12 preferencias (cabe holgado en `memoria.max_tokens_ficha` = 1.500); las de `alcance: oferta` solo valen para su oferta (`--oferta`); más recientes primero.
- Sin ninguna aprobada: «todavía no hay ninguna aprobada. No inventes ninguna». La skill sigue con su método normal.
- **Cómo la usa la skill:** como una guía de estilo con fecha, **no como una regla**. Cita en su informe cuáles usó (`preferencias_usadas: ["PRF-0001"]`) para que el dueño y el QA vean qué influyó; si una choca con su rúbrica, compliance, un límite o J13, no la aplica y lo anota; nunca la presenta como dato del mercado.
- **Solo lectura y sin red.** El script no escribe nada (la prueba lo vigila). Un runner de agentes la recibirá por inyección (`PEDIDO a S-B`, B1-03) en lugar de ejecutarla.

## 4. Pendiente de otras skills (no se toca desde aquí)

- **D6 (`d6-creativos`)**: hoy su `SKILL.md` dice que lee `empresa/memoria/` «si existe» (hooks, `fallas_conocidas`, rechazos por claim, X2). Falta **una línea** en su paso de entradas: «ejecuta `scripts/cerebro/preferencias.py --etapa D6 --texto` y úsalo como guía de estilo con fecha (contrato de `cerebro-cerrar/references/preferencias.md` §3)». Quien edita D6 la añade en su próxima pasada; el contrato está listo y probado.
- **D5, D4, D3, D10** (estilo de landing, tono del producto, voz de los correos): mismo comando con su etapa.
- **Runner de agentes (S-B, B1-03):** inyectar la salida de este comando en el contexto del Maker de la etapa, junto con la ficha de contexto.
- **Panel (S-A/S-C):** mostrar la propuesta con sus correcciones y los botones Aprobar/Rechazar que escriban `preferencias.jsonl` con las palabras del dueño.
- **X2:** cuando exista `ingesta.py`, consumir `preferencias.jsonl` hacia `perfil_dueno.md`.
