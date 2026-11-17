> **v0.2 sin pulir (borrador; v1.0.0 exige corrida manual del dueño, retro de 30-45 min y DoD firmados por el dueño).**

# CHANGELOG — cerebro-cerrar

SemVer. Cada versión: qué cambia, qué falta para la siguiente.

## 0.2.0 — 2026-11-07 — carril de preferencias, jardinero en seco y siembra verificada

Aplica a `/cerebro-cerrar` lo que `docs/_historial/mentor-sistema/brechas/01-cerebro-y-creativos.md` §C.1 asigna a S-C: **B1-05** (carril de preferencias), **B1-08** (jardinero del domingo en dry-run), **B1-02** (siembra: verificada y descrita) y **B1-06/07** en lo que toca al cierre (una sola lista, buscar antes de proponer); costuras con `04-operacion-autonoma.md` B4-21. **Sigue «sin pulir»: ninguna corrida del dueño la respalda** (0 cierres reales con `/cerebro-cerrar`).

**Qué cambia**

- **B1-05 · Clase `preferencia`** en `guardar_pendiente.py`: una corrección **repetida ≥ 2 veces** (`N_MIN_PREFERENCIA`, `[SUPUESTO]` del video 27:30), cada una con su fecha, sobre qué fue, las palabras del dueño (≤ 25) y el archivo con hash si lo hay, se **propone** como regla propuesta de categoría `pref`, abierta, para que la apruebe el dueño. **Nunca se aplica sola:** proponer no escribe el buzón ni cambia lo que leen las skills; la misma corrección copiada dos veces, una sola corrección, una tercera propuesta igual o lo ya rechazado se rechazan (códigos 3 y 5).
- **`preferencia_resolver`:** única función que escribe `aprobada` (también `rechazada` y `revocada`), exige las palabras del dueño y una propuesta abierta; guarda en `empresa/memoria/preferencias.jsonl` (buzón nuevo, ver el PEDIDO frente a X2 en `references/dependencias.md` §B). Solo cuenta lo de autor `dueno` y no revocado.
- **Lectura por D6 y otras skills documentada y lista:** `scripts/cerebro/preferencias.py --etapa D6 --texto` devuelve **solo** las aprobadas (contrato en `references/preferencias.md` §3). Falta que D6 la invoque (una línea en su `SKILL.md`; `§4` de ese archivo) y que el runner la inyecte (S-B, B1-03).
- **B1-08 · Jardinero del domingo en seco:** `scripts/cerebro/jardinero.py` (modo `/cerebro-cerrar jardin`). Propone, con antes, después y cómo aplicarlo: unir duplicados (≥ `sim_dup`), vencidos, recordatorios próximos, dormidos, decisiones posiblemente superadas («revierte/reemplaza J_» en la memoria o en el documento de decisiones), cadenas `reemplaza` rotas, lecciones sin prueba, decisiones del documento sin sembrar, preferencias sin resolver o ya resueltas y pendientes sin prioridad o responsable. No aplica nada; no toca lo protegido (P0, `riesgo`, X1, líneas rojas, vetos, sellos); solo con `--guardar-propuesta --confirmo-dueno` deja UN archivo nuevo en `empresa/memoria/jardin/`.
- **B1-02 · Siembra verificada** (hecha el 2026-11-07 fuera de esta skill): J1-J21 en `empresa/memoria/decisiones_dueno.jsonl` (21 decisiones, cada una con su cita y el hash del documento) y 19 pendientes en `empresa/panel/pulido.jsonl` (3 P0, 8 P1). Descrita en `references/dependencias.md` §A y comprobada por `tests/cerebro/test_siembra.py` (listas blancas, duplicados, secretos, pruebas que existen).
- **B1-07 · Buscar antes de proponer:** el paso 2 sugiere `scripts/cerebro/buscar.py` para saber si algo ya se dijo.
- **`listar`** incluye la clase `preferencia` (propuestas y aprobadas); `_transaccion` factorizada (misma escritura bajo candado para todas las clases).
- **Documentación:** `references/formatos.md` §4-6 (formatos nuevos y códigos), `references/preferencias.md` (nuevo), `references/dependencias.md` (reescrito: estado actual, PEDIDOS a S-A/S-B).
- **Pruebas:** `scripts/test_guardar_pendiente.py` (37, verde; 2 expectativas de `listar` actualizadas por la clase nueva) + `tests/cerebro/` (29 de preferencias, que incluyen que ninguna ruta promueve sin aprobación).

**Qué NO hay / es `[PENDIENTE]`:** X2 completo (ingesta, esquema oficial, QA), aplicación del jardinero con un clic, botón de aprobar/rechazar en el panel, D6 leyendo las preferencias, inyección a los runners, importación de las demás listas de pendientes, esquema JSON de los buzones y del archivo del jardín (`references/dependencias.md`). Sin corrida manual del dueño; sin evals ni rúbrica propias.

## 0.1.0 — 2026-11-06 — borrador (sin pulir)

**Qué hay:** `SKILL.md` (`disable-model-invocation: true`; propone solo lo nuevo, el dueño confirma ítem por ítem, escribe solo con `--escribir`); `scripts/guardar_pendiente.py` (stdlib: valida con las mismas listas blancas que el panel, rechaza claves y tokens, detecta repetidos con `sim_dup` 0,80, exige prueba con hash calculado en las lecciones, solo agrega, nunca sobrescribe ni borra; subcomando `listar`; 37 pruebas, incluidas concurrencia entre procesos y equivalencia byte a byte con la línea del panel); `references/formatos.md`; `references/dependencias.md` (incluye el **PEDIDO a S-A** sobre los nombres frente a X2).

**Origen:** plan del Cerebro v0 en `docs/_historial/mentor-sistema/mapeo.md` §9 y `analisis/cerebro-panel-autonomia.md` (A1, A14, A15). Decisión de principio: una corrección nunca se vuelve regla sola; una regla nueva solo la aprueba el dueño, a mano.

## Checklist de paso de 0.2 a 1.0.0 (cada ítem con evidencia reproducible; nada es «cumple» sin ella)

- [ ] **Corrida manual del dueño:** 3 cierres de sesión reales y retro de 30-45 min (¿propuso solo lo nuevo?; ¿qué repitió?; ¿qué dejó fuera?; ¿propuso alguna preferencia que de verdad se repitió?). El DoD lo firma el dueño.
- [ ] **Determinismo:** `scripts/test_guardar_pendiente.py` y `.venv/bin/python -m unittest discover -s tests/cerebro -t . -p "test_*.py"` en verde.
- [ ] **Nunca escribe sin confirmación:** en las 3 corridas reales, cero escrituras previas al «sí» del dueño (se verifica con el `ts` de cada línea frente a la conversación).
- [ ] **Solo agrega:** el archivo anterior es prefijo del posterior en cada corrida (prueba automática + comprobación en la corrida real).
- [ ] **Seguridad:** el script rechaza claves y tokens sin repetirlos; texto hostil guardado como dato; ninguna escritura fuera de `empresa/panel/pulido.jsonl` y `empresa/memoria/`.
- [ ] **Ninguna corrección se vuelve regla ni preferencia sola:** ninguna corrida escribe en `parametros.yaml`, `limites.yaml`, `autonomia.yaml`, `contratos/**` ni en una skill, y ninguna línea `aprobada` de `preferencias.jsonl` existe sin la cita del dueño en esa sesión.
- [ ] **PEDIDO a S-A resuelto** (nombres frente a X2, colisión con `empresa/decisiones_dueno.jsonl`, esquema de los buzones y del jardín) y D6 leyendo las preferencias.
- [ ] **Forma:** `SKILL.md` < 500 líneas, `description` < 1.024 caracteres.
- [ ] **Congelar:** aprobación del dueño y registro de versión 1.0.0 aquí; desde entonces los cambios solo entran con su aprobación.

## Registro de promoción

| Versión | Estado | Fecha | Corrida manual (oferta_id · locale · modo) | Retro (informe o fecha) | DoD firmado por el dueño | Notas |
|---|---|---|---|---|---|---|
| 0.1.0 | borrador sin pulir | 2026-11-06 | — | — | — | generada desde el plan del Cerebro v0 |
| 0.2.0 | borrador sin pulir | 2026-11-07 | — | — | — | B1-05/08 y siembra B1-02 verificada; sin corrida del dueño |
