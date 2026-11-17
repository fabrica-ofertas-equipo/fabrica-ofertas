> **v0.2 sin pulir (borrador; v1.0.0 exige corrida manual del dueño, retro de 30-45 min y DoD firmados por el dueño).**

# CHANGELOG — cerebro-abrir

SemVer. Cada versión: qué cambia, qué falta para la siguiente.

## 0.2.0 — 2026-11-07 — apertura que avisa de lo no aprobado, P0 siempre arriba, buscador y lista única comprobada

Aplica a la apertura lo que el informe de brechas `docs/_historial/mentor-sistema/brechas/01-cerebro-y-creativos.md` §C.1 asigna a S-C (B1-06, B1-07, B1-09; B1-05 en su parte de lectura) y las costuras con `04-operacion-autonoma.md` B4-21 / B4-24. **Sigue «sin pulir»: ninguna corrida del dueño la respalda** (0 aperturas reales, 0 cierres reales).

**Qué cambia**

- **B1-09 · Lo no aprobado.** `resumen_abrir.py` suma `no_aprobado` (firmas esperando, reglas y **preferencias propuestas**, P0/P1 tuyos, y `preparado_sin_ok`: producto, página de venta, anuncios o campaña que una etapa dejó listos sin que `estado.json` los dé por aprobados), `preferencias` (por aprobar, vigentes y propuestas ya resueltas que siguen abiertas), `decisiones.memoria.ultimas` con su antigüedad, `cerebro.ultimo_cierre` (deducido del `origen` «… /cerebro-cerrar»), `cerebro.jardin` (última propuesta) y `primer_paso` (por reglas fijas: PAUSA → firmas → P0 → vencidos → reglas → P1).
- **P0 siempre arriba y completos.** Todo P0 abierto sale, sea cual sea su tipo, responsable o estado, sin el recorte a 12; en `--texto` y `--corto` van justo después del estado del sistema. Una `prioridad` mal escrita a mano (`p0`) se trata como P0 y se avisa. Un tipo de entrada desconocido cuenta como pendiente (como en el panel).
- **`--texto` rehecho:** lenguaje simple y de tú, título primero e id al final, secciones fijas (estado → P0 → lo que espera tu OK → lo que vence → lo que decidiste → el Cerebro → primer paso), ≈ 45 líneas. Nuevas salidas: `--corto` (hook de apertura, ≤ 14 líneas), `--resumen-diario` (celular: texto plano, ≤ 8 líneas, importes enmascarados) y `--noop-si-agente`.
- **B1-07 · Buscador por idea.** `SKILL.md` §5 y `allowed-tools` incorporan `scripts/cerebro/buscar.py` (BM25 con raíces, erratas, etiquetas y fecha/fuente). Solo lectura, sin embeddings.
- **B1-06 · Una sola lista.** Documentada (regla 9) y comprobada: `tests/cerebro/test_lista_unica.py` compara este script con el JavaScript real del panel (`#/cerebro` y «Mis tareas»), con `scripts/alertas/hechos.py` y sobre una copia de la bitácora real. Divergencias conocidas en `references/dependencias.md`.
- **Hook y resumen diario propuestos** (solo texto, nada instalado): `references/hooks-propuestos.md`.
- **Documentos de decisiones:** `contar_decisiones` cuenta también «Decisiones posteriores», no cuenta la cabecera de cada tabla ni las filas «—» (J1-J21 → 21; antes daba 9).
- **Prueba de «solo lectura» robusta:** la prueba contra el repositorio real usa un gancho de auditoría de escrituras del propio proceso en lugar de comparar el árbol de `empresa/` y `ofertas/` (otros agentes escriben en él y la comparación fallaba por lo que hacen ellos). Aviso: el 2026-11-07 se vio fallar esa comparación una vez por esa causa.
- **Pruebas:** `scripts/test_resumen_abrir.py` (19, verde; se actualizaron 3 por el texto nuevo) + `tests/cerebro/` (140 en total: apertura ampliada 30, buscador 23, jardinero 27, preferencias 29, lista única 7, espejos 7, siembra 10, forma de las skills 7).

**Qué NO hay / es `[PENDIENTE]`:** hook instalado y resumen diario enviado (canal sin decidir, `PUL-0003`), registro de cierres, inyección de la memoria y de las preferencias a los agentes que corren solos (S-B, B1-03), X2 completo, botón de aprobar/rechazar una preferencia en el panel. Sin corrida manual del dueño; sin evals ni rúbrica (una skill de solo lectura sin Maker/QA propio).

## 0.1.0 — 2026-11-06 — borrador (sin pulir)

**Qué hay:** `SKILL.md` (`disable-model-invocation: true`; solo lectura; informe de ≤ 25 líneas en lenguaje de negocio con orden del día); `scripts/resumen_abrir.py` (lee la lista única de pendientes P0-P1 y vencimientos, los gates `gate_pendiente` de las ofertas reales, `PAUSA`, el freno de captura y las decisiones vigentes; stdlib; 19 pruebas); `references/dependencias.md`.

**Origen:** plan del Cerebro v0 en `docs/_historial/mentor-sistema/mapeo.md` §9 y `analisis/cerebro-panel-autonomia.md` (A10). Decisiones del dueño que rigen: `docs/_historial/mentor-sistema/decisiones-del-dueno.md`.

## Checklist de paso de 0.2 a 1.0.0 (cada ítem con evidencia reproducible; nada es «cumple» sin ella)

- [ ] **Corrida manual del dueño:** 3 aperturas de sesión reales con `/cerebro-abrir` y retro de 30-45 min (¿el orden del día fue el que habrías elegido?; ¿los P0 estaban todos arriba?; qué sobró; qué faltó). El DoD lo firma el dueño.
- [ ] **Determinismo:** `scripts/test_resumen_abrir.py` y `.venv/bin/python -m unittest discover -s tests/cerebro -t . -p "test_*.py"` en verde.
- [ ] **Solo lectura demostrada:** el gancho de auditoría de `tests/cerebro/_apoyo.py` no ve ninguna escritura en ninguna de las salidas; ninguna escritura en el código del script.
- [ ] **Seguridad:** texto hostil en un pendiente se cita y no se obedece (prueba de inyección y una corrida real); sin secretos en la salida.
- [ ] **Lista única:** `tests/cerebro/test_lista_unica.py` en verde y las tres divergencias de `references/dependencias.md` resueltas o aceptadas por el dueño.
- [ ] **Forma:** `SKILL.md` < 500 líneas, `description` < 1.024 caracteres.
- [ ] **Estados vacíos:** sin lista, sin P0-P1, sin gates y sin ningún cierre se dicen con el siguiente paso.
- [ ] **Hook de apertura** (opcional) solo tras N2 y el `[VERIFICAR]` del runtime, no-op con `AGENT_RUN_ID` (`references/hooks-propuestos.md`).
- [ ] **Congelar:** aprobación del dueño y registro de versión 1.0.0 aquí; desde entonces los cambios solo entran con su aprobación.

## Registro de promoción

| Versión | Estado | Fecha | Corrida manual (oferta_id · locale · modo) | Retro (informe o fecha) | DoD firmado por el dueño | Notas |
|---|---|---|---|---|---|---|
| 0.1.0 | borrador sin pulir | 2026-11-06 | — | — | — | generada desde el plan del Cerebro v0 |
| 0.2.0 | borrador sin pulir | 2026-11-07 | — | — | — | B1-06/07/09 y costuras B4-21; sin corrida del dueño |
